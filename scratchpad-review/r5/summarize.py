"""Summarize saved CLI output and independently read native raw values; read-only evidence access."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
result = json.loads((HERE/'real-pair.log').read_text())
print(json.dumps({key: result[key] for key in ('status', 'coverage', 'issues', 'runtime_acceptance', 'feature_complete')}))
samples = [row for row in map(json.loads, (Path('/mnt/d/HollowCountryLocal/weather-probe-001-candidate') /
            'profiles/HCWeatherProbe/observations.json').read_text().splitlines()) if row['type'] == 'sample']
for name in ('fog', 'overcast'):
    e = result['phenomena'][name]
    bounds = e['candidate_limits']['min'], e['candidate_limits']['max']
    inside = lambda value: bounds[0]-.001 <= float(value) <= bounds[1]+.001
    first_in = next(row['seq'] for row in samples if inside(row['phenomena'][name]['actual']))
    end = e['initial_transition']['samples']
    outside_assessed = [row['seq'] for row in samples[end:] if not inside(row['phenomena'][name]['actual'])]
    forecasts_outside = [row['seq'] for row in samples if not inside(row['phenomena'][name]['forecast'])]
    assert not outside_assessed and not forecasts_outside
    print(name, json.dumps({key: e[key] for key in ('evidence', 'attribute_evidence', 'candidate_status',
          'values_in_range', 'values_in_range_after_initial_transition', 'raw_actual_outside_limits',
          'initial_transition', 'candidate_actual_range')}))
    print('independent', name, json.dumps(dict(first_actual_inside=first_in,
          endpoint_sample=samples[end]['phenomena'][name], assessed_actual_outside=outside_assessed,
          forecasts_outside=forecasts_outside)))

for filename in ('mutations.json', 'fix-mutations.json'):
    path = HERE/filename
    if not path.exists():
        continue
    for mutation in json.loads(path.read_text()):
        lines = (HERE/(mutation['mutation']+'.log')).read_text().splitlines()
        summary = [line for line in lines if line.startswith(('Ran ', 'FAILED', 'OK'))]
        print(mutation['mutation'], mutation['result'], *summary, sep=' | ')
