"""Run review-only authored placement checks and the existing perception suite."""
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
rows = json.loads((HERE / 'mutation-results.json').read_text())
for row in rows:
    if row['outcome'] not in ('PASS', 'SURVIVED'):
        continue
    dest = HERE / 'mutants-validated' / row['id']
    proc = subprocess.run(['python3', str(HERE / 'test_review_behavior.py'), '-v'], cwd=ROOT,
                          env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'REVIEW_ROOT': str(dest)},
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (dest / 'review-behavior.log').write_text(proc.stdout.replace(str(Path.home()), '~'))
    row['review_behavior_exit'] = proc.returncode
    row['review_behavior_failed_tests'] = [s for s in proc.stdout.splitlines() if s.startswith(('FAIL:', 'ERROR:'))]
    print(row['id'] + ': review placement ' + ('PASS' if proc.returncode == 0 else 'KILLED'))
    if row['id'] == 'baseline' or row['id'].startswith('a1_'):
        shutil.copy2(ROOT / 'tests/unit/test_interiors_contract.py', dest / 'tests/unit/test_interiors_contract.py')
        (dest / 'tests/fixtures/runtime').mkdir(parents=True, exist_ok=True)
        for filename in ('interiors-synthetic.json', 'interiors-completion-synthetic.json'):
            shutil.copy2(ROOT / 'tests/fixtures/runtime' / filename, dest / 'tests/fixtures/runtime' / filename)
        proc = subprocess.run(['python3', '-m', 'unittest', 'discover', '-s', 'tests/unit',
                               '-p', 'test_interiors_contract.py', '-v'], cwd=dest,
                              env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (dest / 'existing-interiors.log').write_text(proc.stdout.replace(str(Path.home()), '~'))
        row['existing_interiors_exit'] = proc.returncode
        print(row['id'] + ': existing interiors ' + ('PASS' if proc.returncode == 0 else 'KILLED'))
    if row['id'] not in ('baseline', 'a17_invert_visual_gate'):
        continue
    for filename in ('test_infected_routes.py', 'test_infected_perception.py'):
        shutil.copy2(ROOT / 'tests/unit' / filename, dest / 'tests/unit' / filename)
    proc = subprocess.run(['python3', '-m', 'unittest', 'discover', '-s', 'tests/unit',
                           '-p', 'test_infected_perception.py', '-v'], cwd=dest,
                          env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (dest / 'existing-perception.log').write_text(proc.stdout.replace(str(Path.home()), '~'))
    row['existing_perception_exit'] = proc.returncode
    row['existing_perception_failed_tests'] = [s for s in proc.stdout.splitlines() if s.startswith(('FAIL:', 'ERROR:'))]
    print(row['id'] + ': existing perception ' + ('PASS' if proc.returncode == 0 else 'KILLED'))
(HERE / 'mutation-results.json').write_text(json.dumps(rows, indent=2) + '\n')
