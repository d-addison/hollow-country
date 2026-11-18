"""Summarise `[HC Perf]` window lines from server RPT files against PROVISIONAL budgets.

This is a measurement tool, not an acceptance gate. Runtime acceptance is always `pending`.
A budget is never reported as accepted: the best verdict is `within_provisional_budget`, and only for
windows recorded with 3 to 6 players. Fewer players is `insufficient_load`; more is `above_target_load`
(reported, not counted as evidence for the 3-6 player target).

Line format (written by HCPerfSampler.c, times in milliseconds). The sampler converts engine ticks to
milliseconds with a per-window calibration (ticks_per_ms) measured against the server clock:
  [HC Perf] window=<n> samples=<k> tick_p50=<ms> tick_p95=<ms> tick_p99=<ms> tick_max=<ms>
            work_p50=<ms> work_p95=<ms> work_max=<ms> players_min=<n> players_max=<n> ticks_per_ms=<rate>
Optional breakdown: slowest_module=<name> slowest_module_max_ms=<ms> slow_ticks=<n>
mod_max=<name>:<ms>,... (up to 32 modules, sorted by name). slow_ticks counts module-loop
samples strictly over 10 ms. These calibrated fields are omitted on invalid calibration.
players_min/players_max are the lowest and highest player counts seen at the window's samples. The older form
with one `players=<count>` (taken at window end) is still read as min == max.
A window whose calibration failed carries no work_* values and ends `players_min=<n> players_max=<n>
calibration=invalid`. Such windows are reported separately and can never produce a within_provisional_budget
verdict.
The same line may sit behind the engine's variable-declaration wrapper (`SCRIPT : string report = '[HC Perf] ...'`,
the closing quote possibly missing) because earlier sampler builds used Print(variable); both forms are read.
A malformed or impossible `[HC Perf]` line is counted and makes the verdict `malformed_input` (exit 1).
"""
import argparse
import json
import math
from pathlib import Path
import re
import sys

MARKER = "[HC Perf]"
INT_FIELDS = ("window", "samples")
PLAYER_FIELDS = ("players_min", "players_max")
TICK_FIELDS = ("tick_p50", "tick_p95", "tick_p99", "tick_max")
WORK_FIELDS = ("work_p50", "work_p95", "work_max")
WORST_FIELDS = ("tick_p95", "tick_p99", "tick_max", "work_p95", "work_max")
DEFAULT_BUDGETS = {"work_p95_ms": 5.0, "work_max_ms": 20.0}
OPTIONAL_BUDGETS = ("tick_p95_ms", "tick_p99_ms", "tick_max_ms")
BUDGET_KEYS = tuple(DEFAULT_BUDGETS) + OPTIONAL_BUDGETS
# Budget name -> the window field it limits.
BUDGET_FIELD = {"work_p95_ms": "work_p95", "work_max_ms": "work_max", "tick_p95_ms": "tick_p95",
                "tick_p99_ms": "tick_p99", "tick_max_ms": "tick_max"}
TARGET_PLAYERS = (3, 6)
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_BUDGET_FILE_BYTES = 65536
MAX_LINE_CHARS = 2000
MAX_EXAMPLES = 5
EXAMPLE_CHARS = 200
PAIR = re.compile(r"([a-z0-9_]+)=(\S+)")
INT_TEXT = re.compile(r"[0-9]{1,9}\Z")
MODULE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
MODULE_FIELDS = ("slowest_module", "slowest_module_max_ms", "slow_ticks", "mod_max")
WRAPPER = re.compile(r"string\s+report\s*=\s*'\s*\Z")


def parse_line(text):
    """Return a record dict for a `[HC Perf]` line, None for any other line, ValueError if malformed."""
    index = text.find(MARKER)
    if index < 0:
        return None
    tail = text[index + len(MARKER):]
    if len(tail) > MAX_LINE_CHARS:
        raise ValueError("line too long")
    if WRAPPER.search(text[:index]):
        # Print(variable) wrapper: the closing quote is part of the wrapper, and may be missing.
        tail = tail.rstrip()
        if tail.endswith("'"):
            tail = tail[:-1]
    values = {}
    for name, raw in PAIR.findall(tail):
        if name in values:
            raise ValueError("duplicate field " + name)
        values[name] = raw
    invalid = values.get("calibration")
    if invalid is not None and invalid != "invalid":
        raise ValueError("bad calibration value")
    if invalid is not None and ("ticks_per_ms" in values or any(name in values for name in WORK_FIELDS)):
        raise ValueError("calibration=invalid line carries calibrated values")
    required = INT_FIELDS + TICK_FIELDS
    if invalid is None:
        required = required + WORK_FIELDS + ("ticks_per_ms",)
    missing = [name for name in required if name not in values]
    if missing:
        raise ValueError("missing field " + missing[0])
    has_old = "players" in values
    has_new = [name for name in PLAYER_FIELDS if name in values]
    if has_old and has_new:
        raise ValueError("players mixed with players_min/players_max")
    if has_old:
        values["players_min"] = values["players_max"] = values["players"]
    elif len(has_new) != len(PLAYER_FIELDS):
        raise ValueError("missing field " + ("players_min" if "players_min" not in values else "players_max"))
    record = {"calibration_valid": invalid is None}
    for name in INT_FIELDS + PLAYER_FIELDS:
        if not INT_TEXT.match(values[name]):
            raise ValueError("bad integer " + name)
        record[name] = int(values[name])
    if has_old:
        record["players"] = record["players_min"]
    if record["window"] < 1:
        raise ValueError("out of range window")
    if record["samples"] < 1:
        raise ValueError("out of range samples")
    if record["players_min"] > record["players_max"]:
        raise ValueError("players_min above players_max")
    for name in required[len(INT_FIELDS):]:
        try:
            number = float(values[name])
        except ValueError:
            raise ValueError("bad number " + name) from None
        if not math.isfinite(number) or number < 0:
            raise ValueError("out of range " + name)
        if name == "ticks_per_ms" and number <= 0:
            raise ValueError("out of range " + name)
        record[name] = number
    for chain in (TICK_FIELDS, WORK_FIELDS):
        if not record["calibration_valid"] and chain is WORK_FIELDS:
            continue
        # tick_p50 <= tick_p95 <= tick_p99 <= tick_max and work_p50 <= work_p95 <= work_max.
        for low, high in zip(chain, chain[1:]):
            if record[low] > record[high]:
                raise ValueError("%s above %s" % (low, high))
    if invalid is not None and any(name in values for name in MODULE_FIELDS):
        raise ValueError("calibration=invalid line carries module values")
    if "slow_ticks" in values:
        raw_count = values["slow_ticks"]
        if not INT_TEXT.fullmatch(raw_count) or int(raw_count) > record["samples"]:
            raise ValueError("out of range slow_ticks")
        record["slow_ticks"] = int(raw_count)
    if "slowest_module" in values:
        if not MODULE_NAME.fullmatch(values["slowest_module"]):
            raise ValueError("bad slowest_module")
        record["slowest_module"] = values["slowest_module"]
    if "slowest_module_max_ms" in values:
        record["slowest_module_max_ms"] = _module_ms(values["slowest_module_max_ms"])
    if "mod_max" in values:
        modules = {}
        entries = values["mod_max"].split(",")
        if len(entries) > 32:
            raise ValueError("too many modules")
        for entry in entries:
            parts = entry.split(":")
            if len(parts) != 2 or not MODULE_NAME.fullmatch(parts[0]) or parts[0] in modules:
                raise ValueError("bad mod_max entry")
            modules[parts[0]] = _module_ms(parts[1])
        if list(modules) != sorted(modules):
            raise ValueError("mod_max not sorted by name")
        record["mod_max"] = modules
    return record


def _module_ms(raw):
    try:
        value = float(raw)
    except ValueError:
        raise ValueError("bad module milliseconds") from None
    if not math.isfinite(value) or value < 0:
        raise ValueError("out of range module milliseconds")
    return value


def _module_stats(records):
    maxima = {}
    candidates = {}
    for record in records:
        for name, value in record.get("mod_max", {}).items():
            maxima[name] = max(maxima.get(name, 0.), value)
        if "slowest_module" in record and "slowest_module_max_ms" in record:
            name = record["slowest_module"]
            candidates[name] = max(candidates.get(name, 0.), record["slowest_module_max_ms"])
    for name, value in maxima.items():
        candidates[name] = max(candidates.get(name, 0.), value)
    slowest = min(candidates, key=lambda name: (-candidates[name], name)) if candidates else None
    slow_counts = [r["slow_ticks"] for r in records if "slow_ticks" in r]
    return {"mod_max": dict(sorted(maxima.items())),
            "module_windows": sum("mod_max" in r for r in records),
            "slow_ticks": sum(slow_counts) if slow_counts else None,
            "slow_tick_windows": len(slow_counts),
            "slowest_module": slowest,
            "slowest_module_max_ms": candidates[slowest] if slowest is not None else None}


def _worst(records):
    """Worst value per field; work_* only from calibrated windows (None when there are none)."""
    worst = {}
    for name in WORST_FIELDS:
        pool = records
        if name.startswith("work_"):
            pool = [r for r in records if r["calibration_valid"]]
        worst[name] = max((r[name] for r in pool), default=None)
    return worst


def _violations(worst, budgets):
    found = []
    for budget_name, field in BUDGET_FIELD.items():
        limit = budgets.get(budget_name)
        if limit is not None and worst[field] is not None and worst[field] > limit:
            found.append(budget_name)
    return found


def _group_key(record):
    if record["players_min"] == record["players_max"]:
        return str(record["players_min"])
    return "%d-%d" % (record["players_min"], record["players_max"])


def _group_verdict(players_min, players_max, violations, invalid_windows):
    # Load must stay inside the target for the whole window: any sample below 3 or above 6 disqualifies it.
    if players_min < TARGET_PLAYERS[0]:
        return "insufficient_load"
    if players_max > TARGET_PLAYERS[1]:
        return "above_target_load"
    if violations:
        return "over_budget"
    if invalid_windows:
        return "calibration_invalid"
    return "within_provisional_budget"


def _key_order(key):
    return tuple(int(part) for part in key.split("-"))


def _stats(records):
    return {"windows": len(records), "samples": sum(r["samples"] for r in records), "worst": _worst(records),
            "calibration_invalid_windows": sum(1 for r in records if not r["calibration_valid"]),
            **_module_stats(records)}


def read_run(path):
    """Parse one RPT file. Returns (records, malformed_count, malformed_examples)."""
    path = Path(path)
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ValueError("%s: file larger than %d bytes" % (path.name, MAX_FILE_BYTES))
    records = []
    malformed = 0
    examples = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for number, row in enumerate(handle, 1):
            try:
                record = parse_line(row.rstrip("\n"))
            except ValueError as error:
                malformed += 1
                if len(examples) < MAX_EXAMPLES:
                    examples.append({"line": number, "reason": str(error),
                                     "text": row.strip()[:EXAMPLE_CHARS]})
                continue
            if record is not None:
                records.append(record)
    return records, malformed, examples


def build_report(paths, budgets):
    runs = []
    everything = []
    malformed_total = 0
    for path in paths:
        records, malformed, examples = read_run(path)
        everything.extend(records)
        malformed_total += malformed
        run = _stats(records)
        rates = [r["ticks_per_ms"] for r in records if r["calibration_valid"]]
        run.update({"ticks_per_ms": {"min": min(rates), "max": max(rates)} if rates else None,
                    "file": Path(path).name, "malformed_lines": malformed, "malformed_examples": examples,
                    "players_seen": sorted({_group_key(r) for r in records}, key=_key_order)})
        runs.append(run)
    by_players = {}
    for key in sorted({_group_key(r) for r in everything}, key=_key_order):
        group_records = [r for r in everything if _group_key(r) == key]
        group = _stats(group_records)
        group["violations"] = _violations(group["worst"], budgets)
        group["verdict"] = _group_verdict(group_records[0]["players_min"], group_records[0]["players_max"],
                                          group["violations"], group["calibration_invalid_windows"])
        by_players[key] = group
    verdicts = [g["verdict"] for g in by_players.values()]
    if "over_budget" in verdicts:
        verdict = "over_budget"
    elif malformed_total:
        # A line that could not be read may have been the over-budget one: never pass on partial evidence.
        verdict = "malformed_input"
    elif not everything:
        verdict = "no_data"
    elif "calibration_invalid" in verdicts:
        verdict = "calibration_invalid"
    elif "within_provisional_budget" in verdicts:
        verdict = "within_provisional_budget"
    else:
        verdict = "insufficient_load"
    return {
        "schema_version": 1,
        "runtime_acceptance": "pending",
        "budgets_provisional": True,
        "budgets": {name: budgets.get(name) for name in BUDGET_KEYS},
        "target_players": {"min": TARGET_PLAYERS[0], "max": TARGET_PLAYERS[1]},
        "verdict": verdict,
        "malformed_lines": malformed_total,
        "calibration_invalid_windows": sum(r["calibration_valid"] is False for r in everything),
        "overall": _stats(everything),
        "by_players": by_players,
        "runs": runs,
    }


def load_budgets(path, overrides):
    """Defaults, then an optional JSON file, then explicit overrides (CLI flags)."""
    budgets = dict(DEFAULT_BUDGETS)
    if path:
        file_path = Path(path)
        if file_path.stat().st_size > MAX_BUDGET_FILE_BYTES:
            raise ValueError("budget file too large")
        try:
            loaded = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("budget file is not valid JSON: " + str(error)) from None
        if not isinstance(loaded, dict):
            raise ValueError("budget file must be a JSON object")
        budgets.update(loaded)
    budgets.update({k: v for k, v in overrides.items() if v is not None})
    for name, value in budgets.items():
        if name not in BUDGET_KEYS:
            raise ValueError("unknown budget " + name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("budget %s must be a number" % name)
        if not math.isfinite(value) or value <= 0:
            raise ValueError("budget %s must be positive" % name)
        budgets[name] = float(value)
    return budgets


def render_text(report):
    lines = ["HC performance capture (budgets PROVISIONAL, not calibrated)",
             "runtime_acceptance: pending",
             "verdict: " + report["verdict"],
             "target load: %d-%d players" % (report["target_players"]["min"], report["target_players"]["max"]),
             "budgets: " + ", ".join("%s<=%s" % (k, v) for k, v in report["budgets"].items() if v is not None),
             "windows: %d, malformed lines: %d" % (report["overall"]["windows"], report["malformed_lines"])]
    lines.append("calibration_invalid windows: %d (work_* unknown; never counted as within budget)"
                 % report["calibration_invalid_windows"])
    module_stats = report["overall"]
    if module_stats["slow_ticks"] is not None:
        lines.append("slow_ticks=%d (reported in %d windows)" % (
            module_stats["slow_ticks"], module_stats["slow_tick_windows"]))
    if module_stats["slowest_module"] is not None:
        lines.append("slowest_module=%s slowest_module_max_ms=%.2f" % (
            module_stats["slowest_module"], module_stats["slowest_module_max_ms"]))
    if module_stats["module_windows"]:
        lines.append("mod_max=" + ",".join("%s:%.2f" % pair for pair in module_stats["mod_max"].items())
                     + " (reported in %d windows)" % module_stats["module_windows"])
    for players, group in report["by_players"].items():
        worst = group["worst"]
        work_p95 = "n/a" if worst["work_p95"] is None else "%.2f" % worst["work_p95"]
        work_max = "n/a" if worst["work_max"] is None else "%.2f" % worst["work_max"]
        lines.append("players=%s windows=%d calibration_invalid=%d verdict=%s worst work_p95=%s work_max=%s "
                     "tick_p95=%.1f tick_p99=%.1f tick_max=%.1f%s"
                     % (players, group["windows"], group["calibration_invalid_windows"], group["verdict"], work_p95,
                        work_max, worst["tick_p95"], worst["tick_p99"], worst["tick_max"],
                        (" violations=" + ",".join(group["violations"])) if group["violations"] else ""))
    for run in report["runs"]:
        lines.append("run %s: windows=%d calibration_invalid=%d malformed=%d" % (
            run["file"], run["windows"], run["calibration_invalid_windows"], run["malformed_lines"]))
        for example in run["malformed_examples"]:
            lines.append("  malformed line %d (%s)" % (example["line"], example["reason"]))
    if report["verdict"] == "insufficient_load":
        lines.append("note: no window recorded with 3-6 players; nothing can be said about the target load")
    if report["verdict"] == "calibration_invalid":
        lines.append("note: target-load windows exist but at least one had no tick calibration; re-run before judging")
    if report["verdict"] == "no_data":
        lines.append("note: no valid [HC Perf] lines found")
    if report["verdict"] == "malformed_input":
        lines.append("note: malformed_input: at least one [HC Perf] line was unreadable or impossible; "
                     "fix or remove it and re-run before judging")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Summarise [HC Perf] lines from server RPT files (provisional budgets).")
    parser.add_argument("rpt", nargs="+", help="server RPT file(s)")
    parser.add_argument("--budgets", help="JSON file of provisional budgets")
    parser.add_argument("--max-work-p95-ms", type=float, dest="work_p95_ms")
    parser.add_argument("--max-work-max-ms", type=float, dest="work_max_ms")
    parser.add_argument("--max-tick-p95-ms", type=float, dest="tick_p95_ms",
                        help="optional; the tick interval is a cadence, so this is off by default")
    parser.add_argument("--json-out", help="write the JSON report here")
    parser.add_argument("--text-out", help="write the text summary here")
    args = parser.parse_args(argv)
    overrides = {name: getattr(args, name) for name in ("work_p95_ms", "work_max_ms", "tick_p95_ms")}
    try:
        budgets = load_budgets(args.budgets, overrides)
        report = build_report(args.rpt, budgets)
    except (OSError, ValueError) as error:
        print("perf_capture: " + str(error), file=sys.stderr)
        return 2
    text = render_text(report)
    try:
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.text_out:
            Path(args.text_out).write_text(text, encoding="utf-8")
    except OSError as error:
        print("perf_capture: " + str(error), file=sys.stderr)
        return 2
    sys.stdout.write(text)
    if report["verdict"] == "no_data":
        return 2
    return 1 if report["verdict"] in ("over_budget", "calibration_invalid", "malformed_input") else 0


if __name__ == "__main__":
    sys.exit(main())
