from pathlib import Path
import sys,json,hashlib,collections
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source-copy'))
from tools.audit import interior_points as p
stock=Path('/mnt/d/HollowCountryLocal/vanilla-p0-001/stock-backup/mpmissions/dayzOffline.chernarusplus/mapgroupproto.xml').read_bytes()
for n in (1,2):
 root=Path.home()/f'.cache/hollow-country/experiments/interior-sampler-{n:03}'
 plan=json.loads((root/'interior-sampler-plan.json').read_bytes());data=(root/'census.json').read_bytes();d=p.parse_census(data)
 print('ARCHIVE',n,'census',len(data),hashlib.sha256(data).hexdigest(),'plan hook',plan['probe']['hook_sha256'])
 print('summary',d['summary'],'states',dict(collections.Counter(r['reach']['state'] for r in d['placements'])),'player_codes present',sum('player_codes' in r for r in d['placements']))
 for key in ('rays','rehits','step_capped_columns','floor_capped_columns','clearance_capped'):
  print(key,sum(r.get('stats',{}).get(key,0) for r in d['placements']))
 try:p.build_treatment(data,stock,.6)
 except ValueError as e:print('current builder REFUSED',e)
 for name in p.TENEMENT_CLASSES+p.CALIBRATION_CLASSES:
  c=p.class_candidates(d,name);print(name,'usable',c['usable_placements'],'eligible',len(p.eligible(c['candidates'],c['reach_mode'],.75)))
 print('script sentinels',[(line.strip()) for file in root.glob('script*.log') for line in file.read_text(errors='replace').splitlines() if any(x in line for x in ('LOADED','BEGIN','COMPLETE','rows='))])
 for file in root.glob('*observation*.json'):
  obs=json.loads(file.read_bytes());print('observation',json.dumps(obs)[:2500])
