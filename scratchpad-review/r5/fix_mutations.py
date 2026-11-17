"""Reverse round-5 fixes only inside the archived source, using the committed weather tests."""
import difflib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE / 'baseline'
path = BASE / 'tools/audit/weather_report.py'
original = path.read_text()
early_violation = ('    if candidate["status"] == "violates_candidate" or candidate["forecast_outside_limits"]:\n'
                   '        return "candidate_values_outside_limits", None, None\n')
MUTATIONS = [
    ('W1_ignore_first_entry', 'if not _outside(actual, limits):', 'if False:'),
    ('W2_excuse_entry_sample', 'return index, "actual_entered_limits"', 'return index + 1, "actual_entered_limits"'),
    ('W3_raw_boolean_follows_status', 'candidate["raw_actual_outside_limits"] == 0',
     'candidate["status"] == "within_candidate"'),
    ('W4_cycle_gate_masks_violations', None, None),
    ('W5_ignore_forecast_violations',
     'if candidate["status"] == "violates_candidate" or candidate["forecast_outside_limits"]:',
     'if candidate["status"] == "violates_candidate":'),
    ('W6_excuse_nonending_window', '    return 0, None\n\n\ndef _current_readback',
     '    return len(points), None\n\n\ndef _current_readback'),
    ('W7_excuse_scheduled_change_sample', 'return index, "first_scheduled_change"',
     'return index + 1, "first_scheduled_change"'),
]
results = []
for name, old, new in MUTATIONS:
    if old is None:
        assert original.count(early_violation) == 1
        marker = '    labels, reasons, live_negative = {}, [], False\n'
        mutant = original.replace(early_violation, '').replace(marker, early_violation + marker)
    else:
        assert original.count(old) == 1, (name, original.count(old))
        mutant = original.replace(old, new)
    try:
        path.write_text(mutant)
        proc = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests/unit',
                               '-p', 'test_weather*.py', '-v'], cwd=BASE,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(HERE/'tmp')),
                              capture_output=True, text=True)
        output = proc.stdout + proc.stderr
        (HERE/(name+'.log')).write_text(output)
        (HERE/(name+'.diff')).write_text(''.join(difflib.unified_diff(
            original.splitlines(True), mutant.splitlines(True), fromfile='original', tofile=name)))
        result = dict(mutation=name, exit=proc.returncode, result='KILLED' if proc.returncode else 'SURVIVED',
                      summary=[line for line in output.splitlines() if line.startswith(('Ran ', 'FAILED', 'OK'))])
        results.append(result)
        print(json.dumps(result), flush=True)
    finally:
        path.write_text(original)
(HERE/'fix-mutations.json').write_text(json.dumps(results, indent=2)+'\n')
assert all(item['exit'] for item in results), results
