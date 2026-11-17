"""Compare native weather probe observations to a cfgweather.xml candidate's limits; offline and read-only.

The weather probe (tools/setup/weather_probe.py) samples the server's native weather state while a stock or a
candidate cfgweather.xml is staged. This report answers one narrow question per run and per pair of runs: do the
observed actual values stay inside the limits that cfgweather.xml declares, or does something (world script,
engine) move them elsewhere? It is evidence for #35 only. It never establishes how DayZ behaves on its own: the
observations come from a run the operator performed, runtime acceptance stays "pending" and feature_complete
stays False in every result.

Per phenomenon the status is one of:
  within_candidate       every actual value after the initial transition is inside the candidate limits (small
                         boundary tolerance); raw_actual_outside_limits and the pair's values_in_range count and
                         describe every raw actual, including the excused transition
  violates_candidate     at least one actual value is outside them after the initial transition; the violating
                         sample numbers are listed
  insufficient_samples   fewer valid samples than min_samples, or the run itself is pending
A run is pending (every phenomenon insufficient_samples) when anything is missing, duplicated, out of order,
malformed (including duplicate JSON object keys and numbers that overflow), non-finite, incomplete (no complete
end record or no complete sentinel), reports write errors, has timestamps that do not increase by about the
sampling interval, or disagrees with its plan or cfgweather.xml. mission_weather and update_frozen are reported per
run; whether the engine sets mission_weather for enable="1" is unobserved and only these samples can say.

Initial transition. A run can start from a pre-existing weather state (the first native candidate run: overcast
0.2877 and fog 0.0312 at weather_time 5.30 with forecasts already at the <current> targets .98 and .75). The samples
before the actual first reaches the first sample's forecast, before it first enters the candidate limits, or before the
first scheduled change (a forecast change, or a countdown that ran out or jumped up), whichever comes first, form the
initial_transition window. Actual values outside the limits inside that window are reported
(initial_transition.actual_outside_limits) and are not violations; the first in-limits sample and every later one are
assessed, so an excursion after the first entry is a violation. A window that ends in none of these ways is not a
transition and is not excused. A forecast outside the limits is never excused: it is counted in
forecast_outside_limits and gives candidate_values_outside_limits in a pair. That verdict, like a violating actual,
is reported as soon as there are enough usable samples, before the countdown and cycle gates (those stay
diagnostics in boundary_crossed and cycle_observed).

next_change semantics. Installed 3_Game/Weather.c:51 describes GetNextChange as "the time in seconds when" the
phenomenon changes next. The first native run (weather-probe-001-stock, observation only, one run) shows a
COUNTDOWN of the remaining seconds instead: fog 294.987 at weather_time 5.30, 234.57 at 65.3, 3.907 shortly before
a jump up to 898.934 at 301.47 together with a new forecast; overcast 0.00096 at the first sample then 1582.11 with
a new forecast; windMagnitude 294.987 then a jump up to 876.111 that did not follow a countdown that had run out
(a reschedule, not a crossing); rain 30 then 60, constant. The countdown also ran 0.97 to 1.03 of the weather
clock per phenomenon. So a deadline is crossed when a countdown near its end (within one sample interval, plus
10 percent and 0.05 s) reads zero or less, or jumps up; a jump up from a countdown that was not near its end is a
reschedule or cancel, never a crossing; and a constant countdown is never crossed. The report applies exactly this
and nothing about the native scheduler beyond these observed lexemes.

Every run also reports its progression: whether the weather clock advanced, whether update was ever frozen,
whether cfgweather.xml is enabled and, per phenomenon, whether a forecast countdown (next_change) was crossed and rescheduled and
whether the actual or forecast value changed. Observed compliance with limits means nothing when nothing moved.

Pair comparison (compare) needs a stock run and a candidate run staged from the same runtime with different
cfgweather.xml bytes. The runs must agree on engine version, world, plan source hashes, hook hash and sampling
(start delay, interval, sample count); the candidate must have been generated from the stock run's
cfgweather.xml. Otherwise the comparison is pending.

Only the treated phenomena are gated: those whose limits, change limits or time limits differ between the two
cfgweather.xml files. The rest are not_treated: reported, never blocking (an inert zero snowfall or a slow wind
cycle cannot make a targeted comparison inconclusive). The treated attributes are limits, change limits, time limits
and current. A differing <current> is read back (current_readback) when it carries actual, time and duration:
the first forecast equals current.actual, the first countdown is about time + duration - weather_time (within
CURRENT_COUNTDOWN_TOLERANCE_S), the actual equals current.actual by about time (plus CURRENT_CONVERGENCE_SLACK_S),
and the stock run's first forecast did not already equal it. Both tolerances are provisional. A <current> without
those keys is treated_unsupported: listed under unsupported_treatments with coverage pending (so the comparison is
pending); a supported result for the same phenomenon is kept apart under supported_attribute_evidence. Each treated
attribute also gets its own label under attribute_evidence. For a treated phenomenon the evidence is:
  pending                         a run is pending, frozen or not ticking, the candidate xml is disabled, too few
                                  samples, no countdown (next_change) that ran out in the candidate run,
                                  no fresh countdown or new forecast observed after that (interpolation toward an
                                  unchanged forecast is not a cycle; a jump up from a countdown that was not near
                                  its end was a reschedule or cancel, not a crossing), or nothing observed changing
  candidate_values_outside_limits the candidate run's actual values left the candidate's limits after the initial
                                  transition, or a forecast was outside them at any time
  inconclusive_readback           processing completed but the live limit readings were not the candidate's in every
                                  candidate reading and in no stock reading. No native conclusion: delayed loading
                                  or a measurement defect can produce this; it never says the engine ignored them
  candidate_live_limits_read_back every candidate reading equalled the candidate's xml values and no stock reading
                                  did. Nothing more: the stock run's values relative to the limits are reported in
                                  stock_values_vs_candidate_limits (entirely_outside, partly_outside, inside)
  current_inconclusive            the candidate's <current> was not read back as above (or the stock run already
                                  started there). No native conclusion; it never says the engine ignored <current>
  candidate_current_read_back     the three <current> checks held in the candidate run and the stock run's first
                                  forecast was not already the candidate's current actual. Nothing more
When limits and current are both treated the evidence field takes the first non-positive label (inconclusive_readback,
then current_inconclusive); otherwise candidate_live_limits_read_back, or candidate_current_read_back when only
<current> is treated (a <current>-only treatment needs no forecast cycle).
The whole comparison is pending when any treated phenomenon is pending, when a treatment is unsupported, or when
nothing supported is treated; inconclusive labels are complete, not pending. Every result carries the fixed NON_CLAIMS list: nothing here establishes precedence of
cfgweather.xml, native non-application, the stock run's controller behaviour or runtime acceptance.

Usage:
  python3 tools/audit/weather_report.py single --runtime RUNTIME_DIR
  python3 tools/audit/weather_report.py compare --stock RUNTIME_DIR --candidate RUNTIME_DIR
Exit codes: 0 complete, 3 pending, 2 unreadable input or an unexpected failure (never a traceback). Input is read through
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
_ATTRIBUTES = ("limits", "change_limits", "time_limits")
_CURRENT_KEYS = ("actual", "time", "duration")
EVIDENCE_LABELS = ("pending", "not_treated", "treated_unsupported", "candidate_values_outside_limits",
                   "inconclusive_readback", "candidate_live_limits_read_back", "current_inconclusive",
                   "candidate_current_read_back")
NON_CLAIMS = (
    "This is a descriptive comparison of two sampled runs. It does not establish that cfgweather.xml takes "
    "precedence over world scripts or engine defaults.",
    "inconclusive_readback does not establish that the engine ignored or failed to apply the candidate's limits; "
    "delayed loading, a measurement defect or different getter semantics can produce it. It carries no native "
    "conclusion.",
    "candidate_live_limits_read_back states only that the candidate's live limits were read back in every candidate "
    "reading and in no stock reading; it does not show why, or that the values follow from them.",
    "The stock run is not required to show a forecast cycle; its controller behaviour is not characterised.",
    "Values inside or outside the limits, and forecasts outside them, do not show a cause; engine limits and "
    "world-script forecasts can coexist.",
    "candidate_current_read_back states only that, in the candidate run, the first forecast equalled the candidate's "
    "<current> actual, the first countdown was about time plus duration minus the weather time, and the actual reached "
    "that value by about time, while the stock run's first forecast did not equal it. current_inconclusive carries no "
    "native conclusion and does not mean the engine ignored <current>. The tolerances are provisional.",
    "Actual values outside the limits in the initial transition are reported, not counted as violations. The excused "
    "prefix ends at the earliest of the actual reaching the first forecast, the actual first enters the limits, or "
    "the first scheduled change; the sample that ends it is assessed, and a window that never ends is not excused. "
    "This does not show how the engine starts from a pre-existing state.",
    "Two single runs sample random weather. Nothing here is runtime acceptance; runtime acceptance and feature "
    "enablement stay pending.",
)
TOLERANCE = 0.001
COUNTDOWN_TOLERANCE_S = 0.05
COUNTDOWN_SLACK = 0.1
# Provisional tolerances for reading <current> back; chosen against one native candidate run (first countdown within
# 0.29 s of time + duration - weather_time, actual at the target at weather time 120.25 for time 120), not measured.
CURRENT_COUNTDOWN_TOLERANCE_S = 1.0
CURRENT_CONVERGENCE_SLACK_S = 10.0
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
    try:
        if isinstance(value, (int, float)):
            result = float(value)
        elif isinstance(value, str) and _DECIMAL.match(value):
            result = float(value)
        else:
            raise ValueError(f"not a number: {str(value)[:30]!r}")
    except OverflowError:
        raise ValueError("number is out of range") from None
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


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {str(key)[:30]!r}")
        result[key] = value
    return result


def _loads(text):
    """json.loads that refuses non-finite constants, duplicate object keys and absurd nesting."""
    try:
        return json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_no_duplicates)
    except RecursionError:
        raise ValueError("JSON nesting is too deep") from None


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
            row = _loads(line)
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
    issues.extend(_timing_issues(header, samples))
    if plan is not None:
        issues.extend(_plan_issues(plan, header, samples, cfgweather_sha))
    return issues


def _timing_issues(header, samples):
    issues = []
    interval = header["interval_ms"] if header is not None else 0
    if header is not None and interval <= 0:
        issues.append(f"header interval_ms {interval} is not positive")
    pairs = list(zip(samples, samples[1:]))
    steps = [(before, after, after["game_ms"] - before["game_ms"]) for before, after in pairs]
    flat = [(b, a) for b, a, step in steps if step <= 0]
    if flat:
        issues.append(f"game_ms does not increase between seq {flat[0][0]['seq']} and seq {flat[0][1]['seq']} "
                      "(repeated or reversed timestamps)")
    elif interval > 0 and any(step < interval // 2 for _b, _a, step in steps):
        issues.append(f"samples are spaced by less than half the header interval_ms {interval}")
    if any(after["weather_time"] < before["weather_time"] for before, after in pairs):
        issues.append("weather_time went backwards between samples")
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
              "forecast_outside_limits": 0, "raw_actual_outside_limits": 0, "engine_limits": None, "boundary_crossed": False,
              "cycle_observed": False, "change_observed": False,
              "xml": dict({key: list(parsed[key]) for key in _ATTRIBUTES}, current=dict(parsed["current"])),
              "live_pairs": None, "initial_transition": None, "current_readback": None, "first_forecast": None}
    if not samples:
        return result
    rows = [(sample["seq"], sample["phenomena"][name]) for sample in samples]
    actual = [row["actual"] for _seq, row in rows]
    forecast = [row["forecast"] for _seq, row in rows]
    points = [(sample["weather_time"], sample["phenomena"][name]["actual"], sample["phenomena"][name]["forecast"],
               sample["phenomena"][name]["next_change"]) for sample in samples]
    length, ended_by = _initial_transition(points, limits)
    outside = [seq for seq, row in rows if _outside(row["actual"], limits)]
    window = [seq for seq, _row in rows[:length]]
    violating = [seq for seq in outside if seq not in window]
    live = [(row["limit_min"], row["limit_max"]) for _seq, row in rows]
    result.update({
        "actual_range": _range(actual), "actual_violations": len(violating), "violating_samples": violating,
        "raw_actual_outside_limits": len(outside),
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
    result["live_pairs"] = {
        "limits": _distinct(live),
        "change_limits": _distinct([(row["change_min"], row["change_max"]) for _seq, row in rows]),
        "time_limits": _distinct([(row["time_min"], row["time_max"]) for _seq, row in rows])}
    result["initial_transition"] = {
        "samples": length, "ended_by": ended_by, "last_seq": window[-1] if window else None,
        "actual_outside_limits": sum(1 for seq in outside if seq in window),
        "outside_samples": [seq for seq in outside if seq in window]}
    result["current_readback"] = _current_readback(parsed["current"], points)
    result["first_forecast"] = points[0][2]
    result["boundary_crossed"], result["cycle_observed"] = _deadline_progress(
        [(time, left, forecast) for time, _actual, forecast, left in points])
    result["change_observed"] = (len({round(value, 6) for value in actual}) > 1
                                 or len({round(value, 6) for value in forecast}) > 1)
    if len(samples) >= min_samples:
        result["status"] = "violates_candidate" if violating else "within_candidate"
    return result


def _initial_transition(points, limits):
    """(samples, ended_by) of the initial transition from (weather_time, actual, forecast, next_change) per sample.

    The window is the run of samples before the actual first reaches the first sample's forecast, before the actual
    first enters the candidate limits, or before the first scheduled change (a forecast change, or a countdown that
    ran out or jumped up), whichever comes first. The first in-limits sample and every later one are assessed, so an
    excursion after the first entry is a violation. A window that ends in none of these ways is not a transition: it
    is not excused, (0, None).
    """
    target = points[0][2]
    for index, (_time, actual, forecast, left) in enumerate(points):
        if _same(actual, target):
            return index, "actual_reached_initial_forecast"
        if not _outside(actual, limits):
            return index, "actual_entered_limits"
        if index:
            before = points[index - 1][3]
            if not _same(forecast, target) or left > before + COUNTDOWN_TOLERANCE_S or left <= 0 < before:
                return index, "first_scheduled_change"
    return 0, None


def _current_readback(current, points):
    """Whether the run's first samples read back the xml's <current actual time duration> (candidate runs only matter).

    Three checks, with explicit provisional tolerances: the first forecast equals current.actual; the first
    countdown is about time + duration - weather_time (CURRENT_COUNTDOWN_TOLERANCE_S); the actual equals
    current.actual at some sample no later than time + CURRENT_CONVERGENCE_SLACK_S of weather time.
    """
    if not all(key in current for key in _CURRENT_KEYS):
        return {"assessable": False, "matches": False}
    target, time, duration = (current[key] for key in _CURRENT_KEYS)
    first_time, _actual, first_forecast, first_left = points[0]
    expected_left = time + duration - first_time
    reached = next((moment for moment, actual, _forecast, _left in points if _same(actual, target)), None)
    checks = {
        "first_forecast_equals_current_actual": _same(first_forecast, target),
        "first_countdown_is_time_plus_duration_minus_weather_time":
            abs(first_left - expected_left) <= CURRENT_COUNTDOWN_TOLERANCE_S,
        "actual_reaches_current_actual_by_time_plus_slack":
            reached is not None and reached <= time + CURRENT_CONVERGENCE_SLACK_S}
    return {"assessable": True, "expected": {"actual": target, "time": time, "duration": duration},
            "observed": {"first_weather_time": first_time, "first_forecast": first_forecast,
                         "first_countdown": first_left, "expected_first_countdown": expected_left,
                         "actual_reached_weather_time": reached},
            "checks": checks, "matches": all(checks.values()),
            "tolerances": {"countdown_s": CURRENT_COUNTDOWN_TOLERANCE_S, "convergence_slack_s": CURRENT_CONVERGENCE_SLACK_S,
                           "provisional": True}}


def _distinct(pairs):
    return sorted([list(pair) for pair in {(round(low, 6), round(high, 6)) for low, high in pairs}])


def _same(left, right):
    return abs(left - right) <= _tolerance(left)


def _deadline_progress(points):
    """(deadline_crossed, cycle_observed) from (weather_time, next_change, forecast) per sample.

    next_change is a COUNTDOWN: the remaining seconds until the next forecast, not an absolute time (see the module
    docstring). A deadline is crossed when a countdown that was close enough to its end to run out before the next
    sample (remaining within one sample interval, plus a small slack) then reads zero or less, or jumps UP to a fresh
    countdown. A jump up from a countdown that was not near its end is a reschedule or a cancel, never a crossing,
    and a constant countdown (script managed) is never crossed. Crossing is not enough: a cycle is observed only
    when, at or after the crossing, the countdown jumped up again or the forecast differs from the one before the
    crossing. Actual values drifting toward an unchanged forecast are interpolation, not a new cycle.
    """
    crossed, before = False, None
    for (time_a, left_a, forecast_a), (time_b, left_b, forecast_b) in zip(points, points[1:]):
        if not crossed:
            near_end = 0 < left_a <= (time_b - time_a) * (1 + COUNTDOWN_SLACK) + COUNTDOWN_TOLERANCE_S
            if not (near_end and (left_b <= 0 or left_b > left_a + COUNTDOWN_TOLERANCE_S)):
                continue
            crossed, before = True, forecast_a
        if left_b > left_a + COUNTDOWN_TOLERANCE_S or not _same(forecast_b, before):
            return True, True
    return crossed, False


def _progression(samples, enabled):
    times = [sample["weather_time"] for sample in samples]
    return {"time_advanced": bool(times) and max(times) > min(times),
            "unfrozen": bool(samples) and not any(sample["update_frozen"] for sample in samples),
            "xml_enabled": enabled}


def _scalar(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    return value[:80] if isinstance(value, str) else value


def _plan_provenance(plan):
    probe = plan.get("probe") if isinstance(plan, dict) else None
    if not isinstance(probe, dict):
        return None
    cfg = probe.get("cfgweather") if isinstance(probe.get("cfgweather"), dict) else {}
    source = plan.get("source") if isinstance(plan.get("source"), dict) else {}
    return {"variant": _scalar(cfg.get("variant")), "staged_sha256": _scalar(cfg.get("staged_sha256")),
            "stock_sha256": _scalar(cfg.get("stock_sha256")), "samples": _scalar(probe.get("samples")),
            "interval_s": _scalar(probe.get("interval_s")), "start_delay_s": _scalar(probe.get("start_delay_s")),
            "hook_sha256": _scalar(probe.get("hook_sha256")),
            "observations_kind": _scalar(probe.get("observations_kind")),
            "launch_plan_sha256": _scalar(source.get("launch_plan_sha256")),
            "config_sha256": _scalar(source.get("config_sha256")),
            "battleye_sha256": _scalar(source.get("battleye_sha256"))}


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
        "progression": _progression(usable, parsed["enable"]),
        "provenance": {"world": None if header is None else header["world"],
                       "version": None if header is None else header["version"],
                       "interval_ms": None if header is None else header["interval_ms"],
                       "planned_samples": None if header is None else header["planned_samples"],
                       "plan": _plan_provenance(plan)},
        "phenomena": {name: _phenomenon_result(name, usable, parsed["phenomena"][name], min_samples) for name in PHENOMENA},
        "non_claims": list(NON_CLAIMS),
        "runtime_acceptance": "pending", "feature_complete": False,
    }
    return result


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def _close(left, right):
    return all(abs(one - two) <= _tolerance(two) for one, two in zip(left, right))


def _current_differs(stock, candidate):
    ours, theirs = stock["xml"]["current"], candidate["xml"]["current"]
    return set(ours) != set(theirs) or any(not _same(ours[key], theirs[key]) for key in ours if key in theirs)


def _current_assessable(candidate):
    return all(key in candidate["xml"]["current"] for key in _CURRENT_KEYS)


def _treated(stock, candidate):
    """The attributes (limits, changelimits, timelimits, current) whose cfgweather.xml values differ between the
    runs; a differing <current> is listed only when it carries actual, time and duration (otherwise unsupported)."""
    attributes = [key for key in _ATTRIBUTES if not _close(stock["xml"][key], candidate["xml"][key])]
    if _current_differs(stock, candidate) and _current_assessable(candidate):
        attributes.append("current")
    return attributes


def _unsupported(stock, candidate):
    """Treatments this report cannot assess: a differing <current> without actual, time and duration."""
    return ["current"] if _current_differs(stock, candidate) and not _current_assessable(candidate) else []


def _readback(stock, candidate, attributes):
    """Live engine readings against the candidate's xml: (per attribute detail, whether all show the differential).

    The differential needs every candidate reading to equal the candidate's xml values and no stock reading to;
    values that merely fall inside the limits prove nothing about which limits the engine holds. The mismatch
    counts keep a mixed early/late readback visible instead of only its verdict.
    """
    detail, applied = {}, True
    for key in attributes:
        wanted = candidate["xml"][key]
        theirs, ours = candidate["live_pairs"][key], stock["live_pairs"][key]
        matches = bool(theirs) and all(_close(pair, wanted) for pair in theirs)
        differs = bool(ours) and not any(_close(pair, wanted) for pair in ours)
        detail[key] = {"candidate_live_matches_candidate_xml": matches, "stock_live_differs_from_candidate_xml": differs,
                       "candidate_readings_matching_candidate_xml": candidate["engine_limits"][key],
                       "candidate_live": theirs, "stock_live": ours}
        applied = applied and matches and differs
    return detail, applied


def _stock_values_vs_candidate_limits(stock, candidate):
    """Where the stock run's actual values lay relative to the candidate's limits; descriptive only."""
    if not stock["actual_range"] or not candidate["actual_range"]:
        return None
    bounds = (candidate["candidate_limits"]["min"], candidate["candidate_limits"]["max"])
    low, high = stock["actual_range"]["min"], stock["actual_range"]["max"]
    if high < bounds[0] - _tolerance(bounds[0]) or low > bounds[1] + _tolerance(bounds[1]):
        return "entirely_outside"
    if _outside(low, bounds) or _outside(high, bounds):
        return "partly_outside"
    return "inside"


_CHECK_NAMES = {"first_forecast_equals_current_actual": "the first forecast did not equal current actual",
                "first_countdown_is_time_plus_duration_minus_weather_time":
                    "the first countdown was not about time plus duration minus the weather time",
                "actual_reaches_current_actual_by_time_plus_slack":
                    "the actual did not reach current actual by about time"}


def _current_evidence(stock, candidate):
    """(label, reason) for the candidate's <current>: read back in the candidate run and not already in the stock run."""
    detail = candidate["current_readback"]
    failed = [text for key, text in _CHECK_NAMES.items() if not detail["checks"][key]]
    target = candidate["xml"]["current"]["actual"]
    if stock["first_forecast"] is not None and _same(stock["first_forecast"], target):
        failed.append("the stock run's first forecast already equalled the candidate's current actual")
    if failed:
        return "current_inconclusive", (
            f"the candidate's <current> was not read back ({'; '.join(failed)}); processing completed with no native "
            f"conclusion, and this does not mean the engine ignored <current>")
    return "candidate_current_read_back", None


def _evidence(stock, candidate, attributes):
    """(evidence label, reason, per attribute labels) for one phenomenon's treatment in a pair of usable runs; a
    reason is given for the labels pending, inconclusive_readback and current_inconclusive only.

    A forecast outside the candidate's limits counts like an actual value outside them (the initial transition only
    excuses actual values). The countdown and cycle gates apply to the live limits, not to a <current>-only treatment.
    """
    live = [key for key in attributes if key != "current"]
    if "insufficient_samples" in (stock["status"], candidate["status"]):
        return "pending", "a run has too few valid samples for this phenomenon", None
    if candidate["status"] == "violates_candidate" or candidate["forecast_outside_limits"]:
        return "candidate_values_outside_limits", None, None
    if live and not candidate["boundary_crossed"]:
        return "pending", "no forecast countdown (next_change) ran out in the candidate run", None
    if live and not candidate["cycle_observed"]:
        return "pending", ("a countdown ran out in the candidate run but next_change never jumped to a fresh countdown "
                           "and the forecast never changed afterwards; interpolation alone is not a new cycle"), None
    if live and not candidate["change_observed"]:
        return "pending", "nothing was observed changing in the candidate run", None
    labels, reasons, live_negative = {}, [], False
    if live:
        detail, _applied = _readback(stock, candidate, live)
        for key in live:
            ok = detail[key]["candidate_live_matches_candidate_xml"] and detail[key]["stock_live_differs_from_candidate_xml"]
            labels[key] = "candidate_live_limits_read_back" if ok else "inconclusive_readback"
        live_negative = "inconclusive_readback" in labels.values()
        if live_negative:
            counts = ", ".join(f"{key} {entry['candidate_readings_matching_candidate_xml']['matching']}/"
                               f"{entry['candidate_readings_matching_candidate_xml']['total']}"
                               for key, entry in detail.items())
            reasons.append(
                f"the candidate's live limits were not read back in every candidate reading and in no stock reading "
                f"(candidate readings matching its xml: {counts}); processing completed with no native conclusion, as "
                f"delayed loading or a measurement defect can produce this")
    if "current" in attributes:
        labels["current"], current_reason = _current_evidence(stock, candidate)
        if current_reason:
            reasons.append(current_reason)
    if live_negative:
        return "inconclusive_readback", "; ".join(reasons), labels
    if labels.get("current") == "current_inconclusive":
        return "current_inconclusive", "; ".join(reasons), labels
    return ("candidate_live_limits_read_back" if live else "candidate_current_read_back"), None, labels


def _short(value):
    return str(value)[:24]


def _provenance_issues(stock, candidate):
    """Reasons the two runs may not be compared: provenance and sampling parameters must match."""
    issues = []
    left, right = stock["provenance"], candidate["provenance"]
    for key in ("world", "version", "interval_ms", "planned_samples"):
        if left[key] is None or right[key] is None or left[key] != right[key]:
            issues.append(f"header {key} differs or is unknown: stock {_short(left[key])!r}, candidate {_short(right[key])!r}")
    one, two = left["plan"], right["plan"]
    if one is None or two is None:
        return issues + ["a run has no usable plan; its provenance cannot be verified (plan required)"]
    for key in ("samples", "interval_s", "start_delay_s", "hook_sha256", "observations_kind", "launch_plan_sha256",
                "config_sha256", "battleye_sha256"):
        if one[key] is None or two[key] is None or one[key] != two[key]:
            issues.append(f"plan {key} differs or is unknown: stock {_short(one[key])!r}, candidate {_short(two[key])!r}")
    if (one["variant"], two["variant"]) != ("stock", "candidate"):
        issues.append("the plans do not describe a stock run and a candidate run (variant mismatch)")
    if one["staged_sha256"] is None or one["staged_sha256"] != one["stock_sha256"]:
        issues.append("the stock run was not staged with the stock cfgweather.xml")
    if two["stock_sha256"] is None or two["stock_sha256"] != one["staged_sha256"]:
        issues.append("the candidate was not generated from the stock run's stock cfgweather.xml "
                      "(stock cfgweather.xml sha256 differs)")
    return issues


def _progression_issues(stock, candidate):
    issues = []
    for label, run in (("stock", stock), ("candidate", candidate)):
        if run["status"] != "complete":
            continue
        progress = run["progression"]
        if not progress["unfrozen"]:
            issues.append(f"{label} run: weather update was frozen in at least one sample")
        if not progress["time_advanced"]:
            issues.append(f"{label} run: the weather clock did not advance")
    if candidate["status"] == "complete" and not candidate["progression"]["xml_enabled"]:
        issues.append("candidate run: cfgweather.xml has enable=0, so its limits are not applied by the engine")
    return issues


def compare(stock_result, candidate_result):
    """Compare a stock run's result with a candidate run's result (both from evaluate/load_run).

    Only the treated phenomena (those whose cfgweather.xml limits differ between the runs) are gated. Phenomena
    whose <current> differs are treated_unsupported: listed, with coverage pending, never silently dropped. The
    others are reported as informational and never block the comparison.
    """
    issues = [f"stock run: {issue}" for issue in stock_result["issues"]]
    issues += [f"candidate run: {issue}" for issue in candidate_result["issues"]]
    if stock_result["cfgweather"]["sha256"] == candidate_result["cfgweather"]["sha256"]:
        issues.append("both runs used the same cfgweather.xml; stage the candidate run with a different one")
    issues += _provenance_issues(stock_result, candidate_result)
    issues += _progression_issues(stock_result, candidate_result)
    treated = {name: _treated(stock_result["phenomena"][name], candidate_result["phenomena"][name])
               for name in PHENOMENA}
    unsupported = {name: _unsupported(stock_result["phenomena"][name], candidate_result["phenomena"][name])
                   for name in PHENOMENA}
    if not any(treated.values()):
        issues.append("the candidate's cfgweather.xml changes no phenomenon's limits, change limits or time limits; "
                      "there is no supported treatment to compare")
    blocked = bool(issues)
    for name in PHENOMENA:
        if unsupported[name]:
            issues.append(f"{name}: the candidate changes its {', '.join(unsupported[name])} values, which this report "
                          f"does not assess; treatment coverage is pending")
    phenomena = {}
    for name in PHENOMENA:
        stock, candidate = stock_result["phenomena"][name], candidate_result["phenomena"][name]
        attributes = treated[name]
        reason, readback, supported, by_attribute = None, None, None, None
        live = [key for key in attributes if key != "current"]
        if not attributes:
            evidence = "treated_unsupported" if unsupported[name] else "not_treated"
        elif blocked:
            evidence = "pending"
        else:
            evidence, reason, by_attribute = _evidence(stock, candidate, attributes)
            if evidence == "pending":
                issues.append(f"{name}: {reason}")
        if attributes and unsupported[name]:
            supported, evidence = evidence, "treated_unsupported"
        if live and candidate["live_pairs"] and stock["live_pairs"]:
            readback = _readback(stock, candidate, live)[0]
        phenomena[name] = {
            "evidence": evidence, "reason": reason, "treated_attributes": attributes,
            "unsupported_treatments": unsupported[name], "supported_attribute_evidence": supported,
            "attribute_evidence": by_attribute,
            "current_readback": ({"stock": stock["current_readback"], "candidate": candidate["current_readback"]}
                                 if "current" in attributes else None),
            "initial_transition": candidate["initial_transition"],
            "stock_initial_transition": stock["initial_transition"],
            "candidate_limits": candidate["candidate_limits"], "candidate_status": candidate["status"],
            "values_in_range": None if not candidate["actual_range"] else candidate["raw_actual_outside_limits"] == 0,
            "values_in_range_after_initial_transition": (
                None if not candidate["actual_range"] else candidate["actual_violations"] == 0),
            "raw_actual_outside_limits": candidate["raw_actual_outside_limits"],
            "stock_values_vs_candidate_limits": _stock_values_vs_candidate_limits(stock, candidate),
            "live_readback": readback,
            "candidate_forecast_outside_limits": candidate["forecast_outside_limits"],
            "stock_actual_range": stock["actual_range"], "candidate_actual_range": candidate["actual_range"],
            "boundary_crossed": {"stock": stock["boundary_crossed"], "candidate": candidate["boundary_crossed"]},
            "cycle_observed": {"stock": stock["cycle_observed"], "candidate": candidate["cycle_observed"]},
            "change_observed": {"stock": stock["change_observed"], "candidate": candidate["change_observed"]}}
    unsupported = {name: values for name, values in unsupported.items() if values}
    pending = bool(issues)
    return {
        "kind": "weather-probe-comparison", "status": "pending" if pending else "complete", "issues": issues,
        "treated": [name for name in PHENOMENA if treated[name]],
        "unsupported_treatments": unsupported, "coverage": "pending" if unsupported else "complete",
        "phenomena": phenomena,
        "progression": {"stock": stock_result["progression"], "candidate": candidate_result["progression"]},
        "mission_weather": {"stock": stock_result["mission_weather"], "candidate": candidate_result["mission_weather"]},
        "update_frozen": {"stock": stock_result["update_frozen"], "candidate": candidate_result["update_frozen"]},
        "notes": ["values_in_range describes every raw actual of the candidate run; "
                  "values_in_range_after_initial_transition and candidate_status describe the samples after the "
                  "initial transition only, not whole-run compliance. Both are reported separately from the live "
                  "limit readback; world-script forecasts and engine limits can coexist.",
                  "Phenomena the candidate does not change are not_treated: reported, never gating.",
                  "Whether the engine sets mission_weather for enable=1 is read from the flags above only."],
        "non_claims": list(NON_CLAIMS),
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
        plan = _loads(_read(root, PLAN_NAME, MAX_XML_BYTES * 4).decode("utf-8"))
    except ValueError as error:
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
    except Exception as error:  # the CLI contract is exit 0, 3 or 2; never a traceback
        print(f"weather_report: unexpected {type(error).__name__}: {str(error)[:80]}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
