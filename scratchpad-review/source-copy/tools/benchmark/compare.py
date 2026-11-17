"""Compare repeated, paired CSV benchmark summaries using only the standard library.

Manifest run contexts support hardware, mission, warmup_seconds, sample_seconds
and optional pair_id only. Unsupported run fields are invalid rather than silently
ignored: additional controls need an explicit schema/pairing policy before use.
"""
import argparse
import csv
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path
import statistics
import sys

# Versioned copy of metrics/benchmark-template.csv, including the notes column.
REQUIRED_FIELDS = (
    "run_id", "game_build", "git_commit", "scenario", "seed", "player_count",
    "active_infected", "active_hordes", "active_interiors", "active_objects",
    "avg_server_fps", "p01_server_fps", "p95_server_frame_ms", "p99_server_frame_ms",
    "client_avg_fps", "client_1pct_low_fps", "peak_ram_mb", "script_ms_per_frame",
    "allocations_per_min", "network_kbps", "errors", "notes",
)
COUNT_FIELDS = {"seed", "player_count", "active_infected", "active_hordes",
                "active_interiors", "active_objects", "errors"}
NUMERIC_FIELDS = ("seed",) + REQUIRED_FIELDS[5:21]
POSITIVE_FIELDS = {"avg_server_fps", "p01_server_fps", "p95_server_frame_ms",
                   "p99_server_frame_ms", "client_avg_fps", "client_1pct_low_fps"}
PAIR_FIELDS = ("scenario", "seed", "game_build", "player_count", "active_infected",
               "active_hordes", "active_interiors", "active_objects")
CONTEXT_FIELDS = ("hardware", "mission", "warmup_seconds", "sample_seconds")
METRICS = {"p95_server_frame_ms": "lower", "p99_server_frame_ms": "lower",
           "client_1pct_low_fps": "higher"}
SCOPE = ("Offline comparison of supplied CSV summaries and declared manifests only. "
         "Does not execute or validate DayZ, authenticate measurements, or establish "
         "runtime, release, or statistical-significance claims.")
EXIT_CODES = {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2, "INVALID": 2}


class EvidenceError(ValueError):
    """Evidence is malformed or cannot be paired comparably."""


def _finite(value, label):
    if not math.isfinite(value):
        raise EvidenceError(f"{label}: must be finite (including computed results)")
    return value


def _number(value, label, *, positive=False, integer=False):
    try:
        if isinstance(value, bool):
            raise ValueError("boolean is not a measurement")
        # Check the supplied sign before binary conversion can underflow to -0.0.
        exact = Decimal(str(value))
        if not exact.is_finite() or exact < 0 or (positive and exact == 0):
            raise ValueError("out of range")
        number = _finite(float(value), label)
        if positive and number == 0:
            raise ValueError("out of range")
        if integer:
            if exact != exact.to_integral_value():
                raise ValueError("fractional count")
            return int(exact)
        return number
    except (ValueError, TypeError, OverflowError, InvalidOperation) as exc:
        qualifier = "positive" if positive else "nonnegative"
        if integer:
            qualifier += " integer"
        raise EvidenceError(f"{label}: expected a finite {qualifier} number") from exc


def _read_csv(path):
    rows = []
    seen_ids = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)):
            raise EvidenceError(f"{path}: duplicate CSV columns")
        missing = sorted(set(REQUIRED_FIELDS) - set(fields))
        if missing:
            raise EvidenceError(f"{path}: missing required CSV fields: {', '.join(missing)}")
        for line, raw in enumerate(reader, 2):
            label = f"{path}: row {line}"
            if None in raw or any(value is None for value in raw.values()):
                raise EvidenceError(f"{label}: wrong number of CSV fields")
            row = {key: value.strip() for key, value in raw.items()}
            for field in ("run_id", "game_build", "git_commit", "scenario", "seed"):
                if not row[field]:
                    raise EvidenceError(f"{label}: empty {field}")
            if row["run_id"] in seen_ids:
                raise EvidenceError(f"{label}: duplicate run_id {row['run_id']!r}")
            seen_ids.add(row["run_id"])
            for field in NUMERIC_FIELDS:
                row[field] = _number(row[field], f"{label}: {field}",
                                     positive=field in POSITIVE_FIELDS,
                                     integer=field in COUNT_FIELDS)
            if row["errors"] != 0:
                raise EvidenceError(f"{label}: errors must be zero")
            if row["p95_server_frame_ms"] > row["p99_server_frame_ms"]:
                raise EvidenceError(f"{label}: p95_server_frame_ms must not exceed p99_server_frame_ms")
            rows.append(row)
    if not rows:
        raise EvidenceError(f"{path}: no benchmark rows")
    if len({row["git_commit"] for row in rows}) != 1:
        raise EvidenceError(f"{path}: mixed git_commit values; compare one revision per file")
    return rows


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"manifest contains duplicate JSON key {key!r}")
        result[key] = value
    return result


def _read_manifest(csv_path, explicit_path, rows, reasons):
    path = Path(explicit_path) if explicit_path is not None else Path(str(csv_path) + ".manifest.json")
    if not path.exists() and explicit_path is None:
        reasons.append(f"{csv_path}: manifest absent; hardware, mission, warmup and sample duration unverified")
        return {}, path
    with path.open(encoding="utf-8") as stream:
        # Preserve tiny signed numeric tokens until _number validates their range.
        data = json.load(stream, object_pairs_hook=_unique_object, parse_float=Decimal)
    if not isinstance(data, dict) or not isinstance(data.get("runs"), dict) or not data["runs"]:
        raise EvidenceError(f"{path}: manifest must contain a nonempty 'runs' object keyed by run_id")
    contexts = {}
    for row in rows:
        run_id = row["run_id"]
        if run_id not in data["runs"]:
            reasons.append(f"{path}: manifest has no context for run_id {run_id!r}")
            continue
        raw = data["runs"][run_id]
        if not isinstance(raw, dict):
            raise EvidenceError(f"{path}: context for {run_id!r} must be an object")
        unsupported = sorted(set(raw) - set(CONTEXT_FIELDS) - {"pair_id"})
        if unsupported:
            raise EvidenceError(f"{path}: run {run_id}: unsupported manifest context fields: "
                                + ", ".join(unsupported))
        context = {}
        for field in CONTEXT_FIELDS:
            label = f"{path}: run {run_id}: {field}"
            if field not in raw:
                reasons.append(f"{label} absent from manifest; unverified")
            elif field in ("hardware", "mission"):
                if not isinstance(raw[field], str) or not raw[field].strip():
                    raise EvidenceError(f"{label}: expected a nonempty context identifier")
                context[field] = raw[field].strip()
            else:
                context[field] = _number(raw[field], label, positive=field == "sample_seconds")
        if "pair_id" in raw:
            if not isinstance(raw["pair_id"], str) or not raw["pair_id"].strip():
                raise EvidenceError(f"{path}: pair_id for {run_id!r} must be a nonempty string")
            context["pair_id"] = raw["pair_id"].strip()
        contexts[run_id] = context
    return contexts, path


def _index(rows, contexts, fields, label):
    result = {}
    for row in rows:
        context = contexts.get(row["run_id"], {})
        key = tuple(row[field] for field in fields) + (context.get("pair_id"),)
        if key in result:
            raise EvidenceError(f"{label}: ambiguous pairing; supply distinct shared manifest pair_id "
                                "values for repeated runs with identical CSV pairing fields")
        result[key] = row
    return result


def _paired_regression(baseline, candidate, direction):
    # Decimal avoids a false failure at a decimal threshold boundary (e.g. 30 -> 30.6).
    before, after = Decimal(str(baseline)), Decimal(str(candidate))
    change = (after - before) / before * 100
    if direction == "higher":
        change = -change
    return _finite(float(change), "paired percentage regression")


def _summarize(baseline, candidate, direction, threshold):
    regressions = [_paired_regression(before, after, direction)
                   for before, after in zip(baseline, candidate)]
    mean = _finite(statistics.mean(regressions), "mean paired percentage regression")
    return {
        "direction": direction + " is better",
        "baseline_mean": _finite(statistics.mean(baseline), "baseline mean"),
        "candidate_mean": _finite(statistics.mean(candidate), "candidate mean"),
        "paired_regression_pct": regressions,
        "mean_paired_regression_pct": mean,
        "min_paired_regression_pct": min(regressions),
        "max_paired_regression_pct": max(regressions),
        "stdev_paired_regression_pct": (
            _finite(statistics.stdev(regressions), "paired percentage standard deviation")
            if len(regressions) > 1 else None),
        "status": ("UNASSESSED" if threshold is None else "FAIL" if mean > threshold else "PASS"),
    }


def compare_files(baseline, candidate, *, max_regression_pct=None,
                  baseline_manifest=None, candidate_manifest=None, allow_object_count_change=False):
    """Return a report, raising EvidenceError/OSError for unusable evidence.

    A supplied threshold is the caller's explicit calibrated gate; no default is inferred.
    PASS applies only to the reported aggregate rule on supplied evidence.
    """
    baseline, candidate = Path(baseline), Path(candidate)
    threshold = (None if max_regression_pct is None else
                 _number(max_regression_pct, "max_regression_pct"))
    before, after = _read_csv(baseline), _read_csv(candidate)
    reasons = []
    baseline_contexts, _ = _read_manifest(baseline, baseline_manifest, before, reasons)
    candidate_contexts, _ = _read_manifest(candidate, candidate_manifest, after, reasons)
    context_verified = not reasons
    fields = tuple(field for field in PAIR_FIELDS
                   if not (allow_object_count_change and field == "active_objects"))
    baseline_index = _index(before, baseline_contexts, fields, "baseline")
    candidate_index = _index(after, candidate_contexts, fields, "candidate")
    if baseline_index.keys() != candidate_index.keys():
        missing = len(baseline_index.keys() - candidate_index.keys())
        extra = len(candidate_index.keys() - baseline_index.keys())
        raise EvidenceError(f"incomparable pairing: {missing} baseline and {extra} candidate "
                            "runs unmatched on scenario, seed, build, players, active population/objects "
                            "and optional manifest pair_id")
    pairs = []
    changes = []
    grouped = {}
    for key, left in baseline_index.items():
        right = candidate_index[key]
        left_id, right_id = left["run_id"], right["run_id"]
        if left["git_commit"] == right["git_commit"]:
            raise EvidenceError(f"pair {left_id}/{right_id}: git_commit must differ")
        left_context = baseline_contexts.get(left_id, {})
        right_context = candidate_contexts.get(right_id, {})
        for field in CONTEXT_FIELDS:
            if field in left_context and field in right_context and left_context[field] != right_context[field]:
                raise EvidenceError(f"pair {left_id}/{right_id}: manifest {field} differs")
        pair = {
            "baseline_run_id": left_id, "candidate_run_id": right_id,
            "pairing_context": {field: left[field] for field in fields},
            "pair_id": left_context.get("pair_id"),
            "baseline_git_commit": left["git_commit"], "candidate_git_commit": right["git_commit"],
            "baseline_active_objects": left["active_objects"],
            "candidate_active_objects": right["active_objects"],
            "baseline_manifest_context": {field: left_context.get(field) for field in CONTEXT_FIELDS},
            "candidate_manifest_context": {field: right_context.get(field) for field in CONTEXT_FIELDS},
            "metrics": {metric: {"baseline": left[metric], "candidate": right[metric],
                                   "regression_pct": _paired_regression(left[metric], right[metric], direction)}
                        for metric, direction in METRICS.items()},
        }
        pairs.append(pair)
        if left["active_objects"] != right["active_objects"]:
            changes.append({"baseline_run_id": left_id, "candidate_run_id": right_id,
                            "baseline": left["active_objects"], "candidate": right["active_objects"]})
        # Seeds identify paired repeats, not distinct aggregate scenarios. Pair IDs also
        # stay out of grouping. Every other controlled context remains in the group.
        group_context = {field: left[field] for field in fields if field != "seed"}
        group_context.update(baseline_active_objects=left["active_objects"],
                             candidate_active_objects=right["active_objects"],
                             baseline_manifest_context=pair["baseline_manifest_context"],
                             candidate_manifest_context=pair["candidate_manifest_context"])
        group_key = json.dumps(group_context, sort_keys=True, allow_nan=False)
        grouped.setdefault(group_key, {"context": group_context, "pairs": []})["pairs"].append(pair)
    groups = []
    for group in grouped.values():
        group_pairs = group["pairs"]
        count = len(group_pairs)
        if count < 2:
            reasons.append(f"scenario {group['context']['scenario']!r}: repeated comparable runs required; "
                           "aggregate group has fewer than two pairs")
        groups.append({
            "context": group["context"], "repeat_count": count,
            "pair_run_ids": [[pair["baseline_run_id"], pair["candidate_run_id"]] for pair in group_pairs],
            "metrics": {metric: _summarize(
                [pair["metrics"][metric]["baseline"] for pair in group_pairs],
                [pair["metrics"][metric]["candidate"] for pair in group_pairs], direction, threshold)
                for metric, direction in METRICS.items()},
        })
    if threshold is None:
        reasons.append("No calibrated regression threshold supplied; specify --max-regression-pct after calibration")
    failed = any(metric["status"] == "FAIL" for group in groups for metric in group["metrics"].values())
    status = "INCOMPLETE" if reasons else "FAIL" if failed else "PASS"
    return {
        "status": status, "scope": SCOPE, "reasons": reasons, "errors": [],
        "max_regression_pct": threshold, "context_verified": context_verified,
        "baseline_file": str(baseline), "candidate_file": str(candidate),
        "pair_count": len(pairs), "pairs": pairs, "groups": groups,
        "allow_object_count_change": allow_object_count_change, "object_count_changes": changes,
        "aggregation": ("Within each comparable context, arithmetic mean of paired per-run percentage "
                        "regressions; positive means worse. Gate each of the three metrics separately. "
                        "CSV quantiles are per-run summaries, not pooled sample quantiles. "
                        "Spread is descriptive; no confidence interval or significance claim."),
    }


def _check_output(output, evidence_paths):
    if output is None:
        return
    for path in evidence_paths:
        if output.resolve() == path.resolve() or (output.exists() and path.exists() and output.samefile(path)):
            raise EvidenceError("output must not overwrite CSV or manifest evidence")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--max-regression-pct", help="explicit caller-calibrated nonnegative percentage gate")
    parser.add_argument("--output", type=Path, help="also write the JSON report to this file")
    parser.add_argument("--baseline-manifest", type=Path, help="default: BASELINE.csv.manifest.json")
    parser.add_argument("--candidate-manifest", type=Path, help="default: CANDIDATE.csv.manifest.json")
    parser.add_argument("--allow-object-count-change", action="store_true",
                        help="explicitly permit and report intentional active_objects changes")
    args = parser.parse_args(argv)
    output_safe = False
    try:
        evidence_paths = [args.baseline, args.candidate]
        evidence_paths.extend([args.baseline_manifest or Path(str(args.baseline) + ".manifest.json"),
                               args.candidate_manifest or Path(str(args.candidate) + ".manifest.json")])
        _check_output(args.output, evidence_paths)
        output_safe = True
        report = compare_files(args.baseline, args.candidate, max_regression_pct=args.max_regression_pct,
                               baseline_manifest=args.baseline_manifest,
                               candidate_manifest=args.candidate_manifest,
                               allow_object_count_change=args.allow_object_count_change)
    except (ValueError, OSError, csv.Error, OverflowError) as exc:
        report = {"status": "INVALID", "scope": SCOPE, "errors": [str(exc)]}
    if args.output is not None and output_safe:
        try:
            args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        except OSError as exc:
            report = {"status": "INVALID", "scope": SCOPE, "errors": [f"cannot write output: {exc}"]}
    print(json.dumps(report, indent=2, allow_nan=False))
    return EXIT_CODES[report["status"]]


if __name__ == "__main__":
    sys.exit(main())
