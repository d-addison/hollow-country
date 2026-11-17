"""Compare native weather probe observations to a cfgweather.xml candidate's limits; offline and read-only.

The weather probe (tools/setup/weather_probe.py) samples the server's native weather state while a stock or a
candidate cfgweather.xml is staged. This report answers one narrow question per run and per pair of runs: do the
observed actual values stay inside the limits that cfgweather.xml declares, or does something (world script,
engine) move them elsewhere? It is evidence for #35 only. It never establishes how DayZ behaves on its own: the
observations come from a run the operator performed, runtime acceptance stays "pending" and feature_complete
stays False in every result.

Per phenomenon the status is one of:
  within_candidate       every actual value is inside the candidate limits (small boundary tolerance)
  violates_candidate     at least one actual value is outside them; the violating sample numbers are listed
  insufficient_samples   fewer valid samples than min_samples, or the run itself is pending
A run is pending (every phenomenon insufficient_samples) when anything is missing, duplicated, out of order,
malformed, non-finite, incomplete (no complete end record or no complete sentinel), reports write errors, or
disagrees with its plan or cfgweather.xml. The forecast is reported but never decides a status because it is
not a value the weather has taken yet. mission_weather and update_frozen are reported per run; whether the
engine sets mission_weather for enable="1" is unobserved and only these samples can say.

Pair comparison (compare) needs a stock run and a candidate run staged from the same runtime with different
cfgweather.xml bytes. Per phenomenon the evidence is:
  script_or_engine_overrides  the candidate run left the candidate's limits
  candidate_governs           the candidate run stayed inside them and the stock run's actual values were
                              entirely outside them (the limits changed the outcome)
  weakly_discriminating       the stock run was only partly outside the candidate's limits
  not_discriminating          the stock run was inside them as well, so the pair cannot tell
  pending                     either run is pending or has too few samples
A single pair of runs is a sample of random weather, not proof; candidate_governs is evidence, not acceptance.

Usage:
  python3 tools/audit/weather_report.py single --runtime RUNTIME_DIR
  python3 tools/audit/weather_report.py compare --stock RUNTIME_DIR --candidate RUNTIME_DIR
Exit codes: 0 complete, 3 pending, 2 unreadable input. Input is read through
RUNTIME/weather-probe-plan.json, the staged cfgweather.xml, profiles/HCWeatherProbe/observations.json and
complete.txt; symlinks are refused. Numbers are accepted as JSON numbers or as strictly formatted decimal
strings (the hook writes floats as strings because float.ToString formatting is unobserved).
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import xml.etree.ElementTree as ET

OBSERVATIONS_KIND = "weather-probe-observations"
PLAN_KIND = "weather-probe"
PLAN_NAME = "weather-probe-plan.json"
MISSION_RELATIVE = "mpmissions/dayzOffline.chernarusplus/cfgweather.xml"
OUTPUT_RELATIVE = "profiles/HCWeatherProbe/observations.json"
SENTINEL_RELATIVE = "profiles/HCWeatherProbe/complete.txt"
PHENOMENA = ("overcast", "fog", "rain", "windMagnitude", "windDirection", "snowfall")
HEADER_KEYS = ("schema", "kind", "world", "version", "planned_samples", "interval_ms", "cap_ms")
SAMPLE_KEYS = ("seq", "game_ms", "weather_time", "mission_weather", "update_frozen", "year", "month", "day",
               "hour", "minute", "wind_speed", "wind_max_speed", "volfog_enabled", "volfog_distance_density",
               "volfog_height_density", "volfog_height_bias")
PHENOMENON_KEYS = ("actual", "forecast", "next_change", "limit_min", "limit_max", "change_min", "change_max",
                   "time_min", "time_max")
END_KEYS = ("status", "samples", "write_errors", "end_ms")
SAMPLE_INT_KEYS = ("seq", "game_ms", "year", "month", "day", "hour", "minute")
SAMPLE_BOOL_KEYS = ("mission_weather", "update_frozen", "volfog_enabled")
SAMPLE_NUMBER_KEYS = tuple(key for key in SAMPLE_KEYS if key not in SAMPLE_INT_KEYS + SAMPLE_BOOL_KEYS)
SCHEMA = 1
MAX_OBSERVATION_BYTES = 4 * 1024 * 1024
MAX_XML_BYTES = 65536
MAX_ISSUES = 40
DEFAULT_MIN_SAMPLES = 6
TOLERANCE = 0.001
LIMIT_BOUND = 1000000.0
EXIT_COMPLETE, EXIT_ERROR, EXIT_PENDING = 0, 2, 3
_DECIMAL = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")
_SENTINEL = re.compile(r"^status=(\w+) samples=(\d+)(?: write_errors=(\d+))?\s*$")
_NOT_CHECKED = object()


# ---------------------------------------------------------------------------
# Strict value parsing
# ---------------------------------------------------------------------------


def _number(value):
    """A finite float from a JSON number or a strictly formatted decimal string; ValueError otherwise."""
    if isinstance(value, bool):
        raise ValueError("a boolean is not a number")
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str) and _DECIMAL.match(value):
        result = float(value)
    else:
        raise ValueError(f"not a number: {str(value)[:30]!r}")
    if not math.isfinite(result):
        raise ValueError("number is not finite")
    return result


def _integer(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"not an integer: {str(value)[:30]!r}")
    return value


def _boolean(value):
    if not isinstance(value, bool):
        raise ValueError(f"not a boolean: {str(value)[:30]!r}")
    return value


def _text(value):
    if not isinstance(value, str):
        raise ValueError(f"not a string: {str(value)[:30]!r}")
    return value


def _tolerance(bound):
    return TOLERANCE * max(1.0, abs(bound))


def _reject_constant(name):
    raise ValueError(f"non-finite JSON constant {name}")


# ---------------------------------------------------------------------------
# cfgweather.xml
# ---------------------------------------------------------------------------


def _attribute_flag(node, name):
    value = node.get(name)
    if value is None:
        return False
    if value not in ("0", "1", "true", "false"):
        raise ValueError(f"cfgweather.xml {name} must be 0 or 1")
    return value in ("1", "true")


def _pair(node, name, parent):
    if node is None:
        raise ValueError(f"cfgweather.xml {parent} lacks {name}")
    low, high = (_number(node.get(key)) for key in ("min", "max"))
    if low > high or abs(low) > LIMIT_BOUND or abs(high) > LIMIT_BOUND:
        raise ValueError(f"cfgweather.xml {parent}/{name} limits {low}..{high} are reversed or out of range")
    return (low, high)


def parse_cfgweather(data):
    """Read the flags and per-phenomenon limits of a cfgweather.xml; ValueError on anything unexpected."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ValueError("cfgweather.xml is empty")
    if len(data) > MAX_XML_BYTES:
        raise ValueError("cfgweather.xml is too large")
    lowered = bytes(data).lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ValueError("cfgweather.xml must not carry a DOCTYPE or entities")
    try:
        root = ET.fromstring(bytes(data))
    except ET.ParseError as error:
        raise ValueError(f"cfgweather.xml is not well-formed: {error}") from error
    if root.tag != "weather":
        raise ValueError("cfgweather.xml root is not weather")
    result = {"enable": _attribute_flag(root, "enable"), "reset": _attribute_flag(root, "reset"), "phenomena": {}}
    for name in PHENOMENA:
        node = root.find(name)
        if node is None:
            raise ValueError(f"cfgweather.xml lacks {name}")
        current = node.find("current")
        result["phenomena"][name] = {
            "limits": _pair(node.find("limits"), "limits", name),
            "change_limits": _pair(node.find("changelimits"), "changelimits", name),
            "time_limits": _pair(node.find("timelimits"), "timelimits", name),
            "current": {key: _number(value) for key, value in (current.attrib.items() if current is not None else ())},
        }
    return result


# ---------------------------------------------------------------------------
# Observation stream
# ---------------------------------------------------------------------------


def _header(row):
    if set(row) != set(HEADER_KEYS) | {"type"}:
        raise ValueError("header keys differ from the documented set")
    return {"schema": _integer(row["schema"]), "kind": _text(row["kind"]), "world": _text(row["world"]),
            "version": _text(row["version"]), "planned_samples": _integer(row["planned_samples"]),
            "interval_ms": _integer(row["interval_ms"]), "cap_ms": _integer(row["cap_ms"])}


def _end(row):
    if set(row) != set(END_KEYS) | {"type"}:
        raise ValueError("end record keys differ from the documented set")
    return {"status": _text(row["status"]), "samples": _integer(row["samples"]),
            "write_errors": _integer(row["write_errors"]), "end_ms": _integer(row["end_ms"])}


def _sample(row):
    if set(row) != set(SAMPLE_KEYS) | {"type", "phenomena"}:
        raise ValueError("sample keys differ from the documented set")
    result = {}
    for key in SAMPLE_INT_KEYS:
        result[key] = _integer(row[key])
    for key in SAMPLE_BOOL_KEYS:
        result[key] = _boolean(row[key])
    for key in SAMPLE_NUMBER_KEYS:
        result[key] = _number(row[key])
    if result["seq"] < 0:
        raise ValueError("negative sequence number")
    phenomena = row["phenomena"]
    if not isinstance(phenomena, dict) or set(phenomena) != set(PHENOMENA):
        raise ValueError("phenomena differ from the documented set")
    result["phenomena"] = {}
    for name in PHENOMENA:
        values = phenomena[name]
        if not isinstance(values, dict) or set(values) != set(PHENOMENON_KEYS):
            raise ValueError(f"{name} keys differ from the documented set")
        result["phenomena"][name] = {key: _number(values[key]) for key in PHENOMENON_KEYS}
    return result


def _parse_stream(text):
    """(header, samples, end, issues) from the JSON-lines text; samples keep file order."""
    issues, header, end, samples = [], None, None, []
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not any(line.strip() for line in lines):
        return None, [], None, ["observations are empty"]
    seen, expected, highest = set(), 0, -1
    for number, raw in enumerate(lines, 1):
        line = raw.rstrip("\r")
        if not line.strip():
            issues.append(f"blank line {number} inside the observation stream (malformed)")
            continue
        try:
            row = json.loads(line, parse_constant=_reject_constant)
        except ValueError as error:
            issues.append(f"malformed JSON on line {number}: {str(error)[:60]}")
            continue
        if not isinstance(row, dict) or not isinstance(row.get("type"), str):
            issues.append(f"malformed record on line {number}: no record type")
            continue
        kind = row["type"]
        if end is not None:
            issues.append(f"record on line {number} after the end record")
            continue
        try:
            if kind == "header":
                if header is not None:
                    issues.append(f"extra header record on line {number}")
                    continue
                header = _header(row)
                if samples:
                    issues.append(f"header on line {number} is not the first record")
            elif kind == "sample":
                if header is None and not samples:
                    issues.append(f"missing header record; the first record is a sample (line {number})")
                sample = _sample(row)
                seq = sample["seq"]
                if seq in seen:
                    issues.append(f"duplicate sample seq {seq} on line {number}")
                    continue
                if seq < highest:
                    issues.append(f"sample sequence out of order: seq {seq} after seq {highest} (line {number})")
                elif seq > expected:
                    issues.append(f"missing sample(s) seq {expected}..{seq - 1} before line {number}")
                seen.add(seq)
                highest = max(highest, seq)
                expected = highest + 1
                samples.append(sample)
            elif kind == "end":
                end = _end(row)
            else:
                issues.append(f"unknown record type {kind[:20]!r} on line {number}")
        except ValueError as error:
            issues.append(f"malformed {kind} record on line {number}: {str(error)[:70]}")
    if header is None and not any("missing header" in issue for issue in issues):
        issues.append("missing header record")
    return header, samples, end, issues


def _structure_issues(header, samples, end, plan, cfgweather_sha):
    issues = []
    if header is not None:
        if header["kind"] != OBSERVATIONS_KIND:
            issues.append(f"header kind {header['kind'][:40]!r} is not {OBSERVATIONS_KIND}")
        if header["schema"] != SCHEMA:
            issues.append(f"header schema {header['schema']} is not supported (expected {SCHEMA})")
        if header["world"].lower() != "chernarusplus":
            issues.append(f"header world {header['world'][:30]!r} is not ChernarusPlus")
        if header["planned_samples"] != len(samples):
            issues.append(f"header planned_samples {header['planned_samples']} differs from "
                          f"{len(samples)} samples observed")
    if end is None:
        issues.append("end record missing; the run did not finish")
    else:
        if end["status"] != "complete":
            issues.append(f"end record status {end['status']!r} is not complete (partial or failed run)")
        if end["samples"] != len(samples):
            issues.append(f"end record samples {end['samples']} differs from {len(samples)} samples observed")
        if end["write_errors"] > 0:
            issues.append(f"end record reports {end['write_errors']} write errors")
    if plan is not None:
        issues.extend(_plan_issues(plan, header, samples, cfgweather_sha))
    return issues


def _plan_issues(plan, header, samples, cfgweather_sha):
    probe = plan.get("probe") if isinstance(plan, dict) else None
    if not isinstance(probe, dict):
        return ["plan is malformed: no probe section"]
    issues = []
    if plan.get("kind") != PLAN_KIND:
        issues.append(f"plan kind {str(plan.get('kind'))[:30]!r} is not {PLAN_KIND}")
    if probe.get("samples") != len(samples):
        issues.append(f"plan samples {probe.get('samples')!r} differs from {len(samples)} samples observed")
    if probe.get("observations_kind") != OBSERVATIONS_KIND:
        issues.append("plan observations_kind differs from the report's")
    if header is not None and isinstance(probe.get("interval_s"), int) and probe["interval_s"] * 1000 != header["interval_ms"]:
        issues.append("plan interval_s differs from the header interval_ms")
    staged = (probe.get("cfgweather") or {}).get("staged_sha256") if isinstance(probe.get("cfgweather"), dict) else None
    if staged != cfgweather_sha:
        issues.append("plan staged cfgweather.xml sha256 differs from the supplied cfgweather.xml")
    return issues


def _sentinel_issues(sentinel, samples):
    if sentinel is None:
        return ["sentinel complete.txt is missing; the run did not finish"]
    match = _SENTINEL.match(sentinel)
    if not match:
        return ["sentinel complete.txt is empty or malformed"]
    issues = []
    if match.group(1) != "complete":
        issues.append(f"sentinel status {match.group(1)!r} is not complete")
    if int(match.group(2)) != samples:
        issues.append(f"sentinel samples {match.group(2)} differs from {samples} samples observed")
    if match.group(3) and int(match.group(3)) > 0:
        issues.append(f"sentinel reports {match.group(3)} write errors")
    return issues


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def _matching(values, bounds):
    low, high = bounds
    hits = sum(1 for lo, hi in values if abs(lo - low) <= _tolerance(low) and abs(hi - high) <= _tolerance(high))
    return {"matching": hits, "total": len(values)}


def _range(values):
    return {"min": min(values), "max": max(values)}


def _outside(value, bounds):
    low, high = bounds
    return value < low - _tolerance(low) or value > high + _tolerance(high)


def _phenomenon_result(name, samples, parsed, min_samples):
    limits = parsed["limits"]
    result = {"status": "insufficient_samples", "candidate_limits": {"min": limits[0], "max": limits[1]},
              "actual_range": None, "actual_violations": 0, "violating_samples": [], "forecast_range": None,
              "forecast_outside_limits": 0, "engine_limits": None}
    if not samples:
        return result
    rows = [(sample["seq"], sample["phenomena"][name]) for sample in samples]
    actual = [row["actual"] for _seq, row in rows]
    forecast = [row["forecast"] for _seq, row in rows]
    violating = [seq for seq, row in rows if _outside(row["actual"], limits)]
    live = [(row["limit_min"], row["limit_max"]) for _seq, row in rows]
    result.update({
        "actual_range": _range(actual), "actual_violations": len(violating), "violating_samples": violating,
        "forecast_range": _range(forecast),
        "forecast_outside_limits": sum(1 for value in forecast if _outside(value, limits)),
        "distinct_actual_values": len({round(value, 6) for value in actual}),
        "engine_limits": {
            "limits": _matching(live, limits),
            "distinct_live_limits": sorted([list(pair) for pair in {(round(lo, 6), round(hi, 6)) for lo, hi in live}]),
            "change_limits": _matching([(row["change_min"], row["change_max"]) for _seq, row in rows],
                                       parsed["change_limits"]),
            "time_limits": _matching([(row["time_min"], row["time_max"]) for _seq, row in rows],
                                     parsed["time_limits"])},
    })
    if len(samples) >= min_samples:
        result["status"] = "violates_candidate" if violating else "within_candidate"
    return result


def _flag(samples, key):
    if not samples:
        return None
    values = sorted({sample[key] for sample in samples})
    return {"values": values, "any_true": True in values, "all_true": values == [True], "consistent": len(values) == 1}


def evaluate(observations, cfgweather_bytes, *, plan=None, min_samples=DEFAULT_MIN_SAMPLES, sentinel=_NOT_CHECKED):
    """Evaluate one run's observations (text or bytes) against the cfgweather.xml it ran with."""
    if isinstance(min_samples, bool) or not isinstance(min_samples, int) or min_samples < 1:
        raise ValueError("min_samples must be a positive integer")
    raw = observations.encode("utf-8") if isinstance(observations, str) else bytes(observations)
    if len(raw) > MAX_OBSERVATION_BYTES:
        raise ValueError("observations are too large")
    parsed = parse_cfgweather(cfgweather_bytes)
    cfgweather_sha = hashlib.sha256(bytes(cfgweather_bytes)).hexdigest()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    if text is None:
        header, samples, end, issues = None, [], None, ["malformed observations: not valid UTF-8"]
    else:
        header, samples, end, issues = _parse_stream(text)
        if not any(issue.startswith("observations are empty") for issue in issues):
            issues.extend(_structure_issues(header, samples, end, plan, cfgweather_sha))
    if sentinel is not _NOT_CHECKED:
        issues.extend(_sentinel_issues(sentinel, len(samples)))
    pending = bool(issues)
    usable = [] if pending else samples
    variant = None
    if isinstance(plan, dict) and isinstance(plan.get("probe"), dict) and isinstance(plan["probe"].get("cfgweather"), dict):
        variant = plan["probe"]["cfgweather"].get("variant")
    result = {
        "kind": "weather-probe-report", "status": "pending" if pending else "complete",
        "issues": issues[:MAX_ISSUES] + ([f"{len(issues) - MAX_ISSUES} further issues omitted"] if len(issues) > MAX_ISSUES else []),
        "samples": len(samples), "min_samples": min_samples,
        "header": None if header is None else {"world": header["world"], "version": header["version"],
                                                "interval_ms": header["interval_ms"]},
        "cfgweather": {"sha256": cfgweather_sha, "variant": variant, "enable": parsed["enable"], "reset": parsed["reset"]},
        "mission_weather": _flag(usable, "mission_weather"), "update_frozen": _flag(usable, "update_frozen"),
        "volfog_enabled": _flag(usable, "volfog_enabled"),
        "weather_time_advanced": bool(usable) and len({sample["weather_time"] for sample in usable}) > 1,
        "phenomena": {name: _phenomenon_result(name, usable, parsed["phenomena"][name], min_samples) for name in PHENOMENA},
        "runtime_acceptance": "pending", "feature_complete": False,
    }
    return result


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def _evidence(stock, candidate):
    if "insufficient_samples" in (stock["status"], candidate["status"]):
        return "pending"
    if candidate["status"] == "violates_candidate":
        return "script_or_engine_overrides"
    bounds = (candidate["candidate_limits"]["min"], candidate["candidate_limits"]["max"])
    low, high = stock["actual_range"]["min"], stock["actual_range"]["max"]
    if high < bounds[0] - _tolerance(bounds[0]) or low > bounds[1] + _tolerance(bounds[1]):
        return "candidate_governs"
    if _outside(low, bounds) or _outside(high, bounds):
        return "weakly_discriminating"
    return "not_discriminating"


def compare(stock_result, candidate_result):
    """Compare a stock run's result with a candidate run's result (both from evaluate/load_run)."""
    issues = [f"stock run: {issue}" for issue in stock_result["issues"]]
    issues += [f"candidate run: {issue}" for issue in candidate_result["issues"]]
    if stock_result["cfgweather"]["sha256"] == candidate_result["cfgweather"]["sha256"]:
        issues.append("both runs used the same cfgweather.xml; stage the candidate run with a different one")
    if stock_result["cfgweather"]["variant"] not in (None, "stock") or candidate_result["cfgweather"]["variant"] not in (None, "candidate"):
        issues.append("the plans do not describe a stock run and a candidate run (variant mismatch)")
    pending = bool(issues)
    phenomena = {}
    for name in PHENOMENA:
        stock, candidate = stock_result["phenomena"][name], candidate_result["phenomena"][name]
        phenomena[name] = {
            "evidence": "pending" if pending else _evidence(stock, candidate),
            "candidate_limits": candidate["candidate_limits"], "candidate_status": candidate["status"],
            "stock_actual_range": stock["actual_range"], "candidate_actual_range": candidate["actual_range"]}
    return {
        "kind": "weather-probe-comparison", "status": "pending" if pending else "complete", "issues": issues,
        "phenomena": phenomena,
        "mission_weather": {"stock": stock_result["mission_weather"], "candidate": candidate_result["mission_weather"]},
        "update_frozen": {"stock": stock_result["update_frozen"], "candidate": candidate_result["update_frozen"]},
        "notes": ["Two single runs sample random weather; candidate_governs is evidence, never acceptance.",
                  "Whether the engine sets mission_weather for enable=1 is read from the flags above only."],
        "runtime_acceptance": "pending", "feature_complete": False,
    }


# ---------------------------------------------------------------------------
# Runtime directory loading
# ---------------------------------------------------------------------------


def _read(root, relative, limit, required=True):
    """Bytes of a regular, non-symlink file below root; None when optional and absent."""
    path = root
    for part in Path(relative).parts:
        path = path / part
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            if required:
                raise ValueError(f"{relative} is missing from {root}") from None
            return None
        if stat.S_ISLNK(info.st_mode):
            raise ValueError(f"{relative} passes through a symlink; refusing")
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"{relative} is not a regular file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{relative} is too large")
    return data


def load_run(runtime_dir):
    """Evaluate a staged and run runtime directory through its plan; ValueError when unreadable."""
    root = Path(runtime_dir)
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"{runtime_dir} is not a runtime directory")
    try:
        plan = json.loads(_read(root, PLAN_NAME, MAX_XML_BYTES * 4).decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{PLAN_NAME} is not valid JSON: {error}") from error
    cfgweather = _read(root, MISSION_RELATIVE, MAX_XML_BYTES)
    observations = _read(root, OUTPUT_RELATIVE, MAX_OBSERVATION_BYTES, required=False)
    sentinel = _read(root, SENTINEL_RELATIVE, 4096, required=False)
    result = evaluate(b"" if observations is None else observations, cfgweather, plan=plan,
                      sentinel=None if sentinel is None else sentinel.decode("utf-8", "replace"))
    if observations is None:
        result["issues"].insert(0, "observations.json is missing")
    return result


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def _emit(result):
    print(json.dumps(result, indent=2, sort_keys=True))
    return EXIT_COMPLETE if result["status"] == "complete" else EXIT_PENDING


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    single = commands.add_parser("single", help="evaluate one run")
    single.add_argument("--runtime", required=True)
    pair = commands.add_parser("compare", help="compare a stock run with a candidate run")
    pair.add_argument("--stock", required=True)
    pair.add_argument("--candidate", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "single":
            return _emit(load_run(args.runtime))
        return _emit(compare(load_run(args.stock), load_run(args.candidate)))
    except (OSError, ValueError) as error:
        print(f"weather_report: {error}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
