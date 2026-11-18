"""W5 #70: print PROVISIONAL cap reductions from log_metrics JSON; never edit CE.

Thresholds are conservative operator heuristics, not calibrated DayZ budgets.
At least ten FPS samples, each carrying 3-6 players, and calibrated HC windows
are needed. Missing/invalid evidence holds caps. A low FPS p10 (<20) or HC work
p95 >5 ms suggests at most ten percent fewer infected/animals. Loot never rises.
No engine API or runtime tick; bounded to one 64 MiB input document.
"""
import argparse
import json
import math
from pathlib import Path
import sys


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1000000


def propose(report, infected_cap, animal_cap):
    if report.get('schema') != 1:
        raise ValueError('unsupported schema')
    fps = report['fps_samples']
    windows = report['perf_windows']
    if not isinstance(fps, list) or not isinstance(windows, list):
        raise ValueError('invalid sample arrays')
    if any(not _number(row['fps']) for row in fps):
        raise ValueError('invalid fps')
    errors = {key: report['errors'][key] for key in ('script_e', 'vm_exception')}
    if any(type(value) is not int or not 0 <= value <= 1000000 for value in errors.values()):
        raise ValueError('invalid error counts')
    calibrated = [row for row in windows if row.get('calibration_valid') is True]
    if any(not _number(row['work_p95']) for row in calibrated):
        raise ValueError('invalid timing')
    target = bool(fps) and all(type(row.get('players')) is int and 3 <= row['players'] <= 6 for row in fps)
    target = target and bool(windows) and all(3 <= row['players_min'] <= row['players_max'] <= 6 for row in windows)
    adequate = len(fps) >= 10 and target and len(calibrated) == len(windows)
    adequate = adequate and not report['truncated'] and report['malformed_perf_lines'] == 0
    sorted_fps = sorted(row['fps'] for row in fps)
    p10 = sorted_fps[max(0, math.ceil(len(fps) * 0.1) - 1)] if fps else None
    worst_work = max((row['work_p95'] for row in calibrated), default=None)
    pressure = adequate and (p10 < 20 or worst_work > 5)
    reason = 'hold: insufficient or invalid evidence at 3-6 players'
    if adequate:
        reason = 'hold: no provisional threshold crossed'
    if pressure:
        reason = 'trial reduction: FPS p10 <20 or HC work_p95 >5 ms; repeat identical load'
    # Feature diagnostics may contain multipliers (escalation infected=1) or
    # local site counts. Only RPT monitor counts describe the sizing population.
    counts = [row['counts'] for row in report['entity_samples'] if row.get('scope') == 'monitor']
    result = dict(schema=1, provisional=True, runtime_acceptance='pending', loot_delta=0,
                  reason=reason, fps_p10=p10, worst_hc_work_p95_ms=worst_work,
                  errors=errors, caution='errors need investigation; reductions do not qualify a build')
    for key, field, cap in (('infected', 'infected', infected_cap), ('animals', 'animals', animal_cap)):
        observed = max((row[field] for row in counts if field in row), default=None)
        if observed is not None and not _number(observed):
            raise ValueError('invalid population')
        delta = 0
        if pressure and observed is not None and observed > 0 and cap is not None:
            delta = -(cap // 10)
        proposed = cap + delta if cap is not None else None
        result[key] = dict(current_cap=cap, delta=delta, proposed_cap=proposed, observed_max=observed)
    return result


def _cap(text):
    value = int(text)
    if value < 0 or value > 100000:
        raise argparse.ArgumentTypeError('cap must be between 0 and 100000')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('metrics', type=Path, help='JSON stdout saved from log_metrics')
    parser.add_argument('--infected-cap', type=_cap, help='current CE infected cap; omitted means hold')
    parser.add_argument('--animal-cap', type=_cap, help='current CE animal cap; omitted means hold')
    args = parser.parse_args(argv)
    try:
        if args.metrics.stat().st_size > 64 * 1024 * 1024:
            raise ValueError('oversized input')
        report = json.loads(args.metrics.read_text(encoding='utf-8-sig'))
        result = propose(report, args.infected_cap, args.animal_cap)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
        print('right_size: unreadable or invalid log_metrics JSON', file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
