"""Read archived native evidence; retain aggregates only, never native source/assets."""
from pathlib import Path
from collections import Counter
import hashlib, json, os, subprocess, sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'head'))
from tools.setup import taped_light_probe as p
from tools.audit import taped_light_report as r
CACHE = Path('/home/david/.cache/hollow-country/experiments')
classification = CACHE / 'taped-light-probe-003/classification.json'
run = CACHE / 'taped-light-probe-006'
o = json.loads((run / 'observations.json').read_text())
plan = json.loads((run / 'taped-light-probe-plan.json').read_text())
capture = json.loads(next(run.glob('taped-light-probe-observation-*.json')).read_text())
c = json.loads(classification.read_text())
hook = p.render_hook(p.select_targets(c))
print('GENERATED_HOOK', json.dumps(dict(bytes=len(hook), sha256=hashlib.sha256(hook).hexdigest())))
print('PLAN_PROBE', json.dumps(plan['probe'], sort_keys=True))
print('PLAN_RUN', json.dumps({k: plan[k] for k in ['variant', 'port', 'mission', 'staged_utc']}))
print('CAPTURE', json.dumps({k: capture[k] for k in ['outcome', 'status', 'server_exited', 'exit_code']}))
print('SENTINEL', (run / 'complete.txt').read_text().strip())
print('OBS', json.dumps(dict(world=o['world'], version=o['version'], observed=o['observed'], counters=o['counters'])))
script = next(run.glob('script_*.log')).read_text()
errors = Counter(line.strip() for line in script.splitlines() if line.startswith('Reason:'))
print('COMPILE_ERRORS', script.count("Can't compile"))
print('SCRIPT_ERROR_REASONS', json.dumps(errors, sort_keys=True))
out = ROOT / 'native-report.json'
argv = ['python3', '-B', '-m', 'tools.audit.taped_light_report', '--classification', str(classification),
        '--observations', str(run / 'observations.json'), '--out', str(out)]
result = subprocess.run(argv, cwd=ROOT / 'head', env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT/'tmp')),
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
print('COMMAND', json.dumps(dict(argv=argv, cwd=str(ROOT/'head'), exit=result.returncode)))
print(result.stdout.strip())
assert result.returncode == 0
report = json.loads(out.read_text())
archived = json.loads((run / 'report-182db38.json').read_text())
print('ARCHIVED_REPORT_COMPARISON', {key: report[key] == archived[key] for key in report if key != 'provenance'})
print('DENOMINATORS', json.dumps(report['denominators'], sort_keys=True))
print('INTEGRITY', json.dumps(report['integrity'], sort_keys=True))
print('ACCEPTANCE', report['acceptance'], report['unobserved_axes'])
hosts = [h for h in o['hosts'] if h['spawned']]
print('RES_LOD_TUPLES', sorted(Counter((l['name'], l['list_ok'], bool(l['selection_count'])) for h in hosts for l in h['res_lods']).items()))
print('HOSTS_WITH_LISTABLE_RES', sum(any(l['list_ok'] for l in h['res_lods']) for h in hosts))
print('PROXY_PARSE_KINDS', Counter(r._proxies(h)[0] for h in hosts))
print('LEGACY_SLOT_FLAGS', Counter((s['selection_on_model'], s['memory_point'], s['bone_index']) for h in hosts for s in h['slots']))
print('BASE_HOST_SLOT_ATTACH', Counter((h['root'], s['slot'], s['can_add'], s['attach_ok'])
      for h in hosts for light in h['lights'] for s in light.get('per_slot', [])
      if light['light'] == 'UniversalLight' and next(x for x in h['slots'] if x['slot'] == s['slot'])['host_has_slot']))
variants = [h for h in hosts if h['prereq_variant']['performed']]
print('VARIANT_COUNTS', Counter((h['prereq_variant']['handguard'], h['prereq_variant']['handguard_attached'], h['prereq_variant']['handguard_rail_functional']) for h in variants))
print('VARIANT_LIGHT_ATTACH', Counter((h['prereq_variant']['handguard'], s['can_add'], s['attach_ok'], s['found_type']) for h in variants for light in h['prereq_variant']['lights'] for s in light['per_slot'] if s['slot'] == 'weaponFlashlight'))
for name in ['AK101','AK74','AKM','ASVAL','Aug','M4A1','SCAR','FNX45','Glock19','CZ75','1911','MP5K','UMP45','FNX45_arrow']:
    matches = [h for h in hosts if h['class'].casefold() == name.casefold()]
    for h in matches:
        rh = next(x for x in report['hosts'] if x['class'] == h['class'])
        print('NATIVE_HOST', json.dumps(dict(name=h['class'], res_lods=h['res_lods'],
              base=[{'light': x['light'], 'attempt': [s for s in x.get('per_slot',[]) if s['slot'] in ['weaponFlashlight','pistolFlashlight']]} for x in h['lights']],
              variant=h['prereq_variant'], report_lights=rh['lights'], aliases=rh['diagnostics']['proxy_alias_collapsed']), sort_keys=True))
# No native observation/model or generated full report is retained in the review artifacts.
out.unlink()
