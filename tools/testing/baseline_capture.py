"""Single-client baseline capture: startup time, tick percentiles, peak memory and storage write slope.

Reads the server RPT and script log, plus the CSV written by tools/testing/sample-server-process.ps1, and writes
one row in the shape of metrics/benchmark-template.csv together with a JSON manifest (inputs and sha256, warm or
cold label, tool versions) that tools/benchmark/compare.py can read.

This is a measurement tool, not an acceptance gate. Budgets stay PROVISIONAL: the manifest and the summary carry
no pass or fail verdict, and runtime acceptance is always `pending`.

Log formats (read from a real server run; every marker below was observed, none is assumed):
  RPT header     `Current time:  2026/03/04 21:07:38` and `Version 1.30.164289.70`: the server process start.
  Log lines      `HH:MM:SS.mmm ...`. The millisecond field is NOT zero padded: `21:07:40.91` is 91 ms, so it is
                 read as an integer, never as a decimal fraction.
  HC ready       `SCRIPT : [HollowCountry] Server initialized; ...` (printed once by the server, after every module
                 start was requested). Startup time is this marker's time minus the RPT start.
  Other phases   `Module: Mission;`, `[CE][Hive] :: Initializing` and `PROFILING : Loading landscape took: <n> ms`.
  Tick windows   `[HC Perf] window=...` lines, parsed by perf_capture.py. The tick fields are the interval of the
                 HC tick timer, not engine frame time. Windows only carry percentiles, so a pooled percentile is
                 not recoverable; the worst window's p95/p99 is reported, which is an upper bound on the pooled
                 value (if every window has at most 5% of ticks above X, so does their union).

Sampler CSV columns: see SAMPLER_COLUMNS. Memory is WorkingSet64 and PrivateMemorySize64 in bytes. The storage
write slope is the least-squares slope of total storage bytes against time, in bytes per minute: a net-growth
figure, so a file rewritten in place at the same size contributes nothing; `storage_write_events` counts the
samples where the newest last-write time moved.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import platform
import re
import sys
import tempfile

if __package__:
    from . import perf_capture
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import perf_capture

SCHEMA_VERSION = 1
LABELS = ("warm", "cold")
ROW_FIELDS = (
    "run_id", "game_build", "git_commit", "scenario", "seed", "player_count",
    "active_infected", "active_hordes", "active_interiors", "active_objects",
    "avg_server_fps", "p01_server_fps", "p95_server_frame_ms", "p99_server_frame_ms",
    "client_avg_fps", "client_1pct_low_fps", "peak_ram_mb", "script_ms_per_frame",
    "allocations_per_min", "network_kbps", "errors", "notes",
)
# Row fields this tool cannot measure from the logs or the sampler. The operator may supply them from another
# source; any left out are written as empty cells and listed as unmeasured, which compare.py rejects. The
# engine frame-time columns are here too: the HC module timer interval is not an engine frame time, so it is
# kept in the notes and the manifest perf block only.
OPERATOR_FIELDS = (
    "p95_server_frame_ms", "p99_server_frame_ms", "avg_server_fps", "p01_server_fps", "client_avg_fps", "client_1pct_low_fps", "script_ms_per_frame",
    "allocations_per_min", "network_kbps", "active_infected", "active_hordes", "active_interiors",
    "active_objects",
)
COUNT_FIELDS = ("active_infected", "active_hordes", "active_interiors", "active_objects")
SAMPLER_COLUMNS = ("timestamp_utc", "process_alive", "working_set_bytes", "private_bytes", "storage_bytes",
                   "storage_files", "storage_last_write_utc")
MARKERS = {
    "hc_ready": "[HollowCountry] Server initialized;",
    "perf_sampler_started": "[HollowCountry] Perf sampler started",
}
MAX_STARTUP_SECONDS = 6 * 3600
ROLLOVER_MS = 3600 * 1000
MAX_HEADER_LINES = 200
MAX_SAMPLER_BYTES = 64 * 1024 * 1024
BYTES_PER_MIB = 1024 * 1024
HEADER_START = re.compile(r"Current time:\s+(\d{4})/(\d{2})/(\d{2}) (\d{2}):(\d{2}):(\d{2})\s*\Z")
HEADER_VERSION = re.compile(r"Version\s+(\d+(?:\.\d+){1,5})\s*\Z")
SCRIPT_HEADER_START = re.compile(r"Log .* started at (\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\b")
LINE_TIME = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})\.(\d{1,3})(?=\s|\Z)")
LANDSCAPE = re.compile(r"PROFILING\s*:\s*Loading landscape took:\s*([0-9]+(?:\.[0-9]+)?) ms")
MISSION_MODULE = re.compile(r"SCRIPT\s*:\s*Module: Mission;")
CE_HIVE = re.compile(r"\[CE\]\[Hive\] :: Initializing\b")
SAMPLER_TIME = re.compile(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,7}))?Z\Z")
SAMPLER_INT = re.compile(r"[0-9]{1,15}\Z")
GIT_COMMIT = re.compile(r"[0-9A-Za-z._-]{1,64}\Z")
SCOPE = ("Single-client baseline from supplied logs and sampler output only. Budgets are provisional and carry "
         "no pass or fail verdict; nothing here establishes DayZ runtime acceptance.")


class BaselineError(ValueError):
    """Input is malformed, incomplete or not comparable."""


def parse_time_ms(text):
    """Milliseconds since midnight for a leading `HH:MM:SS.mmm` stamp, else None. The ms field is an integer."""
    match = LINE_TIME.match(text.lstrip())
    if match is None:
        return None
    hours, minutes, seconds, millis = (int(part) for part in match.groups())
    if hours > 23 or minutes > 59 or seconds > 60:
        return None
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def _lines(path):
    path = Path(path)
    if path.stat().st_size > perf_capture.MAX_FILE_BYTES:
        raise BaselineError("%s: file larger than %d bytes" % (path.name, perf_capture.MAX_FILE_BYTES))
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for text in handle:
            yield text.rstrip("\r\n")


def _header(path, pattern):
    for number, text in enumerate(_lines(path)):
        if number >= MAX_HEADER_LINES:
            return None
        match = pattern.match(text.strip())
        if match:
            return match
    return None


def _datetime(parts):
    try:
        return datetime(*(int(part) for part in parts))
    except ValueError as error:
        raise BaselineError("bad header date/time: %s" % error) from None


def _timed_lines(path, base, previous_ms):
    """Yield (absolute naive datetime, text after the stamp) for every stamped line, following midnight."""
    day = datetime(base.year, base.month, base.day)
    for text in _lines(path):
        stripped = text.lstrip()
        match = LINE_TIME.match(stripped)
        millis = parse_time_ms(stripped)
        if match is None or millis is None:
            continue
        if millis < previous_ms - ROLLOVER_MS:
            day += timedelta(days=1)
        previous_ms = millis
        yield day + timedelta(milliseconds=millis), stripped[match.end():].lstrip()


def _marker(body, marker):
    return re.match(r"SCRIPT\s*:\s*" + re.escape(marker), body) is not None


def _ms_of_day(moment):
    return ((moment.hour * 60 + moment.minute) * 60 + moment.second) * 1000


def _first_events(path, base, previous_ms, with_landscape):
    found = {}
    for moment, body in _timed_lines(path, base, previous_ms):
        for name, marker in MARKERS.items():
            if name not in found and _marker(body, marker):
                found[name] = moment
        if "mission_module" not in found and MISSION_MODULE.match(body):
            found["mission_module"] = moment
        if "ce_hive" not in found and CE_HIVE.search(body):
            found["ce_hive"] = moment
        if with_landscape and "landscape_ms" not in found:
            match = LANDSCAPE.match(body)
            if match:
                found["landscape_ms"] = float(match.group(1))
    return found


def read_startup(rpt_path, script_path):
    """Startup facts from the RPT header and the first observed markers. Raises BaselineError if absent."""
    start_match = _header(rpt_path, HEADER_START)
    if start_match is None:
        raise BaselineError("%s: no 'Current time:' start header in the first %d lines"
                            % (Path(rpt_path).name, MAX_HEADER_LINES))
    version = _header(rpt_path, HEADER_VERSION)
    if version is None:
        raise BaselineError("%s: no 'Version' header in the first %d lines" % (Path(rpt_path).name, MAX_HEADER_LINES))
    start = _datetime(start_match.groups())
    rpt_events = _first_events(rpt_path, start, _ms_of_day(start), with_landscape=True)
    script_start_match = _header(script_path, SCRIPT_HEADER_START)
    script_base = _datetime(script_start_match.groups()) if script_start_match else start
    script_events = _first_events(script_path, script_base, _ms_of_day(script_base), with_landscape=False)
    ready = script_events.get("hc_ready")
    source = "script_log"
    if ready is None:
        ready = rpt_events.get("hc_ready")
        source = "rpt"
    if ready is None:
        raise BaselineError("no HC ready marker %r in the RPT or the script log" % MARKERS["hc_ready"])
    startup_ms = round((ready - start).total_seconds() * 1000)
    if startup_ms < 0:
        raise BaselineError("HC ready marker is before the server start")
    if startup_ms > MAX_STARTUP_SECONDS * 1000:
        raise BaselineError("implausible startup time %.1f s (limit %d s); check the log pairing"
                            % (startup_ms / 1000, MAX_STARTUP_SECONDS))
    phases = {}
    for key, name in (("mission_module", "mission_module_loaded_seconds"), ("ce_hive", "ce_hive_initializing_seconds"),
                      ("perf_sampler_started", "perf_sampler_started_seconds")):
        moment = rpt_events.get(key) or script_events.get(key)
        if moment is not None:
            phases[name] = round((moment - start).total_seconds() * 1000) / 1000
    return {
        "server_start": start.isoformat(),
        "startup_seconds": startup_ms / 1000,
        "hc_ready_marker": MARKERS["hc_ready"],
        "ready_source": source,
        "start_precision_seconds": 1,
        "game_build": version.group(1),
        "phases": phases,
        "loading_landscape_ms": rpt_events.get("landscape_ms"),
    }


def read_perf(script_path, skip_windows=0):
    """Tick-window summary from the `[HC Perf]` lines of one log. Percentiles are worst-window upper bounds."""
    if skip_windows < 0:
        raise BaselineError("skip_windows must not be negative")
    records, malformed, examples = perf_capture.read_run(script_path)
    kept = records[skip_windows:]
    if not kept:
        raise BaselineError("%s: no [HC Perf] windows after skipping %d" % (Path(script_path).name, skip_windows))
    samples = sum(record["samples"] for record in kept)

    def weighted(field):
        return sum(record[field] * record["samples"] for record in kept) / samples

    calibrated = [record for record in kept if record["calibration_valid"]]
    return {
        "windows": len(kept),
        "windows_skipped": min(skip_windows, len(records)),
        "samples": samples,
        "tick_p95_ms_worst_window": max(record["tick_p95"] for record in kept),
        "tick_p99_ms_worst_window": max(record["tick_p99"] for record in kept),
        "tick_max_ms": max(record["tick_max"] for record in kept),
        "tick_p95_ms_sample_weighted_mean": round(weighted("tick_p95"), 3),
        "tick_p99_ms_sample_weighted_mean": round(weighted("tick_p99"), 3),
        "work_p95_ms_worst_window": max((record["work_p95"] for record in calibrated), default=None),
        "players_min_seen": min(record["players_min"] for record in kept),
        "players_max_seen": max(record["players_max"] for record in kept),
        "calibration_invalid_windows": len(kept) - len(calibrated),
        "malformed_lines": malformed,
        "malformed_examples": [{"line": item["line"], "reason": item["reason"]} for item in examples],
        "tick_unit_note": "HC tick timer interval, not engine frame time",
    }


def _sampler_seconds(text, label):
    match = SAMPLER_TIME.match(text)
    if match is None:
        raise BaselineError("%s: bad timestamp %r" % (label, text))
    year, month, day, hour, minute, second = (int(part) for part in match.groups()[:6])
    fraction = match.group(7) or "0"
    try:
        moment = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    except ValueError as error:
        raise BaselineError("%s: bad timestamp %r (%s)" % (label, text, error)) from None
    return moment.timestamp() + int(fraction) / 10 ** len(fraction)


def _sampler_int(text, label, field, required):
    if text == "":
        if required:
            raise BaselineError("%s: empty %s" % (label, field))
        return None
    if not SAMPLER_INT.match(text):
        raise BaselineError("%s: %s must be a non-negative integer, got %r" % (label, field, text[:40]))
    return int(text)


def _slope_per_minute(points):
    if len(points) < 2:
        return None
    origin = points[0][0]
    xs = [(second - origin) / 60 for second, _ in points]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(value for _, value in points) / len(points)
    spread = sum((x - mean_x) ** 2 for x in xs)
    if spread <= 0:
        return None
    covariance = sum((x - mean_x) * (value - mean_y) for x, (_, value) in zip(xs, points))
    return covariance / spread


def read_sampler(path):
    """Peak memory and storage write figures from one sampler CSV."""
    path = Path(path)
    if path.stat().st_size > MAX_SAMPLER_BYTES:
        raise BaselineError("%s: file larger than %d bytes" % (path.name, MAX_SAMPLER_BYTES))
    seconds = []
    alive_rows = []
    without_process = 0
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader, None)
        if header is None or tuple(header) != SAMPLER_COLUMNS:
            raise BaselineError("%s: header must be %s" % (path.name, ",".join(SAMPLER_COLUMNS)))
        for number, fields in enumerate(reader, 2):
            label = "%s: row %d" % (path.name, number)
            if not fields:
                continue
            if len(fields) != len(SAMPLER_COLUMNS):
                raise BaselineError("%s: expected %d fields" % (label, len(SAMPLER_COLUMNS)))
            stamp, alive, working_set, private, storage_bytes, storage_files, last_write = fields
            moment = _sampler_seconds(stamp, label)
            if seconds and moment <= seconds[-1]:
                raise BaselineError("%s: timestamps must strictly increase" % label)
            seconds.append(moment)
            if alive not in ("0", "1"):
                raise BaselineError("%s: process_alive must be 0 or 1" % label)
            if alive == "0":
                without_process += 1
                continue
            alive_rows.append({
                "second": moment,
                "working_set": _sampler_int(working_set, label, "working_set_bytes", True),
                "private": _sampler_int(private, label, "private_bytes", True),
                "storage": _sampler_int(storage_bytes, label, "storage_bytes", False),
                "last_write": _sampler_seconds(last_write, label) if last_write else None,
            })
    if not alive_rows:
        raise BaselineError("%s: no sample with the server process alive" % path.name)
    storage = [(row["second"], row["storage"]) for row in alive_rows if row["storage"] is not None]
    stamps = [row["last_write"] for row in alive_rows if row["last_write"] is not None]
    return {
        "samples": len(seconds),
        "samples_without_process": without_process,
        "span_seconds": seconds[-1] - seconds[0],
        "peak_working_set_bytes": max(row["working_set"] for row in alive_rows),
        "peak_private_bytes": max(row["private"] for row in alive_rows),
        "storage_samples": len(storage),
        "storage_first_bytes": storage[0][1] if storage else None,
        "storage_last_bytes": storage[-1][1] if storage else None,
        "storage_write_slope_bytes_per_min": _slope_per_minute(storage),
        "storage_write_events": sum(1 for before, after in zip(stamps, stamps[1:]) if after != before),
    }


def sha256_of(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _input_entry(role, path):
    path = Path(path)
    return {"role": role, "name": path.name, "bytes": path.stat().st_size, "sha256": sha256_of(path)}


def _tool_versions(game_build):
    here = Path(__file__).resolve()
    versions = {
        "python": platform.python_version(),
        "game_build": game_build,
        "baseline_capture_sha256": sha256_of(here),
        "perf_capture_sha256": sha256_of(perf_capture.__file__),
    }
    sampler = here.with_name("sample-server-process.ps1")
    if sampler.exists():
        versions["sample_server_process_ps1_sha256"] = sha256_of(sampler)
    return versions


def _check_measured(measured):
    checked = {}
    for name, value in measured.items():
        if name not in OPERATOR_FIELDS:
            raise BaselineError("unknown measured field %r" % name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise BaselineError("%s: expected a finite non-negative number" % name)
        if name in COUNT_FIELDS:
            if value != int(value):
                raise BaselineError("%s: expected a whole number" % name)
            value = int(value)
        checked[name] = value
    if "p95_server_frame_ms" in checked and "p99_server_frame_ms" in checked \
            and checked["p95_server_frame_ms"] > checked["p99_server_frame_ms"]:
        raise BaselineError("p95_server_frame_ms must not exceed p99_server_frame_ms")
    return checked


# Resolved output destinations under these repository trees are refused: they ship in the packages.
SHIPPED_TREES = ("mods", "mission", "config")


def _refuse_shipped_destination(path):
    repo = Path(__file__).resolve().parents[2]
    resolved = Path(path).resolve()
    for tree in SHIPPED_TREES:
        root = repo / tree
        if resolved == root or root in resolved.parents:
            raise BaselineError("refusing to write %s inside the shipped %s/ tree" % (resolved.name, tree))


def _count(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BaselineError("%s: expected a non-negative integer" % name)
    return value


def build_capture(rpt, script_log, sampler_csv, label, git_commit, run_id=None, scenario=None, seed=0,
                  player_count=1, measured=None, skip_windows=0, hardware=None, mission=None,
                  warmup_seconds=None, sample_seconds=None):
    """Read every input and return the benchmark row, the manifest entries and the unmeasured field list."""
    if label not in LABELS:
        raise BaselineError("label must be one of %s" % ", ".join(LABELS))
    if not GIT_COMMIT.match(git_commit or ""):
        raise BaselineError("git_commit must be 1 to 64 characters of [0-9A-Za-z._-]")
    seed = _count(seed, "seed")
    player_count = _count(player_count, "player_count")
    measured = _check_measured(measured or {})
    startup = read_startup(rpt, script_log)
    perf = read_perf(script_log, skip_windows)
    sampler = read_sampler(sampler_csv)
    scenario = scenario or "single-client-baseline-" + label
    if run_id is None:
        run_id = "%s-%s" % (scenario, re.sub(r"[^0-9T]", "", startup["server_start"]))
    unmeasured = [name for name in OPERATOR_FIELDS if name not in measured]
    peak_mib = round(sampler["peak_working_set_bytes"] / BYTES_PER_MIB, 3)
    slope = sampler["storage_write_slope_bytes_per_min"]
    notes = ["single-client baseline", "label=" + label, "budgets provisional, no verdict",
             "runtime acceptance pending",
             "hc_tick_p95_ms_worst_window=%s" % perf["tick_p95_ms_worst_window"],
             "hc_tick_p99_ms_worst_window=%s" % perf["tick_p99_ms_worst_window"],
             "HC tick intervals are not engine frame time and never fill the frame_ms columns",
             "peak_ram_mb is peak WorkingSet in MiB",
             "startup_seconds=%s" % startup["startup_seconds"],
             "storage_write_slope_bytes_per_min=%s" % ("n/a" if slope is None else "%.1f" % slope)]
    if unmeasured:
        notes.append("unmeasured=" + "|".join(unmeasured))
    values = {name: "" for name in OPERATOR_FIELDS}
    values.update(measured)
    row = {
        "run_id": run_id, "game_build": startup["game_build"], "git_commit": git_commit, "scenario": scenario,
        "seed": seed, "player_count": player_count,
        "peak_ram_mb": peak_mib, "errors": perf["malformed_lines"], "notes": "; ".join(notes),
        **values,
    }
    row = {name: row[name] for name in ROW_FIELDS}
    context = {}
    if hardware:
        context["hardware"] = hardware
    if mission:
        context["mission"] = mission
    if warmup_seconds is not None:
        context["warmup_seconds"] = warmup_seconds
    sample_source = "operator"
    if sample_seconds is None and sampler["span_seconds"] > 0:
        sample_seconds, sample_source = round(sampler["span_seconds"]), "sampler_span"
    if sample_seconds is not None:
        context["sample_seconds"] = sample_seconds
    entry = {
        "schema_version": SCHEMA_VERSION,
        "label": label,
        "runtime_acceptance": "pending",
        "budgets": {"status": "provisional", "verdict": "unassessed"},
        "scope": SCOPE,
        "inputs": [_input_entry("server_rpt", rpt), _input_entry("script_log", script_log),
                   _input_entry("sampler_csv", sampler_csv)],
        "tool_versions": _tool_versions(startup["game_build"]),
        "startup": startup,
        "perf": perf,
        "sampler": sampler,
        "unmeasured": unmeasured,
        "sample_seconds_source": sample_source,
        "units": {"peak_ram_mb": "MiB of peak WorkingSet64",
                  "perf.tick_p95_ms_worst_window": "worst-window HC tick interval p95, not engine frame time",
                  "perf.tick_p99_ms_worst_window": "worst-window HC tick interval p99, not engine frame time"},
    }
    return {"row": row, "context": context, "entry": entry, "unmeasured": unmeasured}


def _replace_text(path, text):
    handle, name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
        os.replace(name, str(path))
    except BaseException:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def _csv_text(rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    for row in rows:
        writer.writerow([row[name] for name in ROW_FIELDS])
    return buffer.getvalue()


def write_outputs(out_csv, capture):
    """Write the row and manifest, or merge them into an existing pair. Nothing is written on any error."""
    out_csv = Path(out_csv)
    _refuse_shipped_destination(out_csv)
    manifest_path = Path(str(out_csv) + ".manifest.json")
    row = capture["row"]
    rows, manifest = [], {"schema_version": SCHEMA_VERSION, "runs": {}, "captures": {}}
    if out_csv.exists():
        with out_csv.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            if tuple(reader.fieldnames or ()) != ROW_FIELDS:
                raise BaselineError("%s: existing header is not the benchmark template" % out_csv.name)
            rows = [dict(existing) for existing in reader]
        if not manifest_path.exists():
            raise BaselineError("%s exists without its manifest; refusing to merge" % out_csv.name)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest.get("runs"), dict) or not isinstance(manifest.get("captures"), dict):
            raise BaselineError("%s: manifest lacks runs/captures objects" % manifest_path.name)
        if any(existing["run_id"] == row["run_id"] for existing in rows) or row["run_id"] in manifest["runs"]:
            raise BaselineError("run_id %r is already in %s" % (row["run_id"], out_csv.name))
        if any(existing["git_commit"] != row["git_commit"] for existing in rows):
            raise BaselineError("%s holds another git_commit; compare.py needs one revision per file"
                                % out_csv.name)
    rows.append(row)
    manifest["runs"][row["run_id"]] = capture["context"]
    manifest["captures"][row["run_id"]] = capture["entry"]
    _replace_text(out_csv, _csv_text(rows))
    _replace_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def render_text(capture, out_csv):
    row, entry = capture["row"], capture["entry"]
    startup, perf, sampler = entry["startup"], entry["perf"], entry["sampler"]
    slope = sampler["storage_write_slope_bytes_per_min"]
    lines = [
        "baseline capture, single client, label=%s (budgets provisional: no pass/fail verdict; "
        "runtime acceptance pending)" % entry["label"],
        "run_id: " + row["run_id"],
        "game_build: " + row["game_build"],
        "startup_seconds: %s (RPT 'Current time' to %r, from the %s; start precision 1 s)"
        % (startup["startup_seconds"], startup["hc_ready_marker"], startup["ready_source"].replace("_", " ")),
    ]
    for name, value in sorted(startup["phases"].items()):
        lines.append("  %s: %s" % (name, value))
    if startup["loading_landscape_ms"] is not None:
        lines.append("  loading_landscape_ms: %s" % startup["loading_landscape_ms"])
    lines += [
        "tick windows: %d (%d skipped), samples %d, players seen %d-%d"
        % (perf["windows"], perf["windows_skipped"], perf["samples"], perf["players_min_seen"],
           perf["players_max_seen"]),
        "  tick_p95_ms (worst window, upper bound): %s" % perf["tick_p95_ms_worst_window"],
        "  tick_p99_ms (worst window, upper bound): %s" % perf["tick_p99_ms_worst_window"],
        "  malformed [HC Perf] lines: %d" % perf["malformed_lines"],
        "peak_working_set_mib: %s (private peak %s MiB)"
        % (row["peak_ram_mb"], round(sampler["peak_private_bytes"] / BYTES_PER_MIB, 3)),
        "storage_write_slope_bytes_per_min: %s (net growth over %s s, %d samples, %d last-write changes)"
        % ("n/a" if slope is None else round(slope, 3), round(sampler["span_seconds"], 1), sampler["samples"],
           sampler["storage_write_events"]),
    ]
    if capture["unmeasured"]:
        flags = " ".join("--" + name.replace("_", "-") for name in capture["unmeasured"])
        lines.append("unmeasured: " + ", ".join(capture["unmeasured"]))
        lines.append("  written as empty cells; compare.py rejects the row until supplied with: " + flags)
    name = Path(out_csv).name
    lines.append("wrote: %s and %s.manifest.json" % (name, name))
    return "\n".join(lines) + "\n"


def _number_arg(text):
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError("not a number: %r" % text) from None
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError("expected a finite non-negative number, got %r" % text)
    return value


def _build_parser():
    parser = argparse.ArgumentParser(
        description="Single-client baseline: startup, tick percentiles, peak memory, storage write slope. "
                    "Writes one benchmark row plus a manifest; budgets stay provisional.")
    parser.add_argument("--rpt", required=True, help="server RPT (start header, markers, landscape time)")
    parser.add_argument("--script-log", required=True, help="server script log ([HC Perf] windows, markers)")
    parser.add_argument("--sampler-csv", required=True, help="CSV from sample-server-process.ps1")
    parser.add_argument("--label", required=True, choices=LABELS, help="warm or cold run, as the operator ran it")
    parser.add_argument("--git-commit", required=True, help="revision the server package was built from")
    parser.add_argument("--out-csv", required=True, help="benchmark CSV to create or extend; manifest beside it")
    parser.add_argument("--run-id", help="default: scenario plus the server start stamp")
    parser.add_argument("--scenario", help="default: single-client-baseline-<label>")
    parser.add_argument("--seed", type=int, default=0, help="default 0 (nothing is seeded)")
    parser.add_argument("--player-count", type=int, default=1)
    parser.add_argument("--skip-windows", type=int, default=0, help="leading [HC Perf] windows to leave out")
    parser.add_argument("--hardware", help="manifest hardware identifier")
    parser.add_argument("--mission", help="manifest mission identifier")
    parser.add_argument("--warmup-seconds", type=_number_arg)
    parser.add_argument("--sample-seconds", type=_number_arg, help="default: the sampler's first-to-last span")
    for name in OPERATOR_FIELDS:
        parser.add_argument("--" + name.replace("_", "-"), dest=name, type=_number_arg,
                            help="measured elsewhere; left out, the cell is written empty and listed unmeasured")
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)
    measured = {name: getattr(args, name) for name in OPERATOR_FIELDS if getattr(args, name) is not None}
    try:
        capture = build_capture(
            args.rpt, args.script_log, args.sampler_csv, args.label, args.git_commit, run_id=args.run_id,
            scenario=args.scenario, seed=args.seed, player_count=args.player_count, measured=measured,
            skip_windows=args.skip_windows, hardware=args.hardware, mission=args.mission,
            warmup_seconds=args.warmup_seconds, sample_seconds=args.sample_seconds)
        write_outputs(args.out_csv, capture)
    except (BaselineError, OSError, ValueError) as error:
        sys.stderr.write("baseline_capture: error: %s\n" % error)
        return 2
    sys.stdout.write(render_text(capture, args.out_csv))
    return 0


if __name__ == "__main__":
    sys.exit(main())
