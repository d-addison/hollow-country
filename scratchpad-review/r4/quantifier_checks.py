"""Check the supplemental tests against correct HEAD and the two surviving quantifier mutants."""
import json
import os
from pathlib import Path
import subprocess
import sys
HERE = Path(__file__).resolve().parent
path = HERE / 'baseline/tools/audit/weather_report.py'
original = path.read_text()
mutants = [
    ('HEAD', None, None),
    ('R7', 'matches = bool(theirs) and all(_close(pair, wanted) for pair in theirs)',
     'matches = bool(theirs) and any(_close(pair, wanted) for pair in theirs)'),
    ('R8', 'differs = bool(ours) and not any(_close(pair, wanted) for pair in ours)',
     'differs = bool(ours) and not all(_close(pair, wanted) for pair in ours)'),
]
for name, old, new in mutants:
    try:
        if old is not None:
            assert original.count(old) == 1
            path.write_text(original.replace(old, new))
        proc = subprocess.run([sys.executable, '-B', str(HERE / 'round3_cases.py'), 'ReadbackQuantifiers'],
                              capture_output=True, text=True,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(HERE / 'tmp')))
        (HERE / ('quantifier-' + name + '.log')).write_text(proc.stdout + proc.stderr)
        print(json.dumps({'version': name, 'exit': proc.returncode}), flush=True)
    finally:
        path.write_text(original)
