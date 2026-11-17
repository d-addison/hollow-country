from pathlib import Path
import sys,json,hashlib,collections
sys.path.insert(0,str(Path(__file__).resolve().parent/'source-copy'))
from tools.audit import interior_points as p
from tools.setup import interior_sampler as s
root=Path('/mnt/d/HollowCountryLocal/interior-sampler-002');path=root/'profiles/HCInteriorSampler/census.json';raw=path.read_bytes();d=json.loads(raw)
plan=json.loads((root/'interior-sampler-plan.json').read_bytes());keys=('run_ray_limit','building_ray_limit','hit_limit','step_limit','path_limit','output_limit','intersect')
hook=s.render_hook(plan['targets'],sample_delay_s=plan['probe']['sample_delay_s'],**{k:plan['sampler'][k] for k in keys})
print('native regenerated hook matches plan hash:',hashlib.sha256(hook).hexdigest()==plan['probe']['hook_sha256'])
print('native init contains exact hook:',hook in (root/'mpmissions/dayzOffline.chernarusplus/init.c').read_bytes())
print('census bytes/hash:',len(raw),hashlib.sha256(raw).hexdigest())
obs=json.loads(next(root.glob('interior-sampler-observation-*.json')).read_bytes());print('observation:',obs['status'],obs['outcome'],'crash logs:',len(obs['crash_logs']),'server exit:',obs['exit_code'])
print('summary:',d['summary'])
print('reach states:',dict(collections.Counter(r['reach']['state'] for r in d['placements'])))
print('reach stages:',dict(collections.Counter(a[2] for r in d['placements'] for a in r['reach']['attempts'])))
print('relation counts:',{key:sum(r['stats']['hit_relations'][key] for r in d['placements']) for key in ('none','building','proxy','other')})
print('totals:',{key:sum(r['stats'][key] for r in d['placements']) for key in ('interior_hits','rehits','step_capped_columns','floor_capped_columns','clearance_capped')})
print('sample owner capped column: placement 4, column 0:',d['placements'][4]['diag']['columns'][0])
for cls in p.TENEMENT_CLASSES+p.CALIBRATION_CLASSES:
 c=p.class_candidates(p.parse_census(raw),cls)
 print(cls,'usable:',c['usable_placements'],'eligible:',len(p.eligible(c['candidates'],c['reach_mode'],.75)))
try:p.build_treatment(raw,Path('/mnt/d/HollowCountryLocal/vanilla-p0-001/stock-backup/mpmissions/dayzOffline.chernarusplus/mapgroupproto.xml').read_bytes(),.6)
except ValueError as exc:print('treatment refusal:',type(exc).__name__,str(exc))
