from pathlib import Path
import json,collections,hashlib,sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'source-copy'))
from tools.audit import interior_points as p
roots=[Path('/home/david/.cache/hollow-country/experiments/interior-sampler-001'),Path('/mnt/d/HollowCountryLocal/interior-sampler-002')]
for root in roots:
 path=root/'census.json' if (root/'census.json').exists() else root/'profiles/HCInteriorSampler/census.json'
 data=path.read_bytes();d=json.loads(data)
 print('\nRUN',root.name,'bytes',len(data),'sha256',hashlib.sha256(data).hexdigest(),'summary',d['summary'])
 print('i class reach stages hits(reach codes) stats')
 for r in d['placements']:
  print(r['i'],r['class'],r['reach']['state'],[a[2] for a in r['reach'].get('attempts',[])],len(r['hits']),dict(collections.Counter(h[5] for h in r['hits'])),r['stats'])
  if root.name.endswith('002'):
   print(' ATTEMPTS',r['reach']['attempts'])
   for c in r['diag']['columns']:
    print(' COLUMN',c['x'],c['z'],'steps',c['steps'],'floors',c['floors'],'cap',c['cap'],'first',c['seq'][:3],'last',c['seq'][-3:])
 if root.name.endswith('002'):
  print('all stages',dict(collections.Counter(a[2] for r in d['placements'] for a in r['reach']['attempts'])))
  print('relations',dict(sum((collections.Counter(r['stats']['hit_relations']) for r in d['placements']),collections.Counter())))
  for cls in p.TENEMENT_CLASSES+p.CALIBRATION_CLASSES:
   try:
    c=p.class_candidates(p.parse_census(data),cls)
    e=p.eligible(c['candidates'],c['reach_mode'],.75)
    print('CANDIDATES',cls,'usable',c['usable_placements'],'reach',c['reach_mode'],'total',len(c['candidates']),'eligible',len(e))
   except Exception as exc: print('CANDIDATES',cls,type(exc).__name__,str(exc))
  stock=Path('/mnt/d/HollowCountryLocal/vanilla-p0-001/stock-backup/mpmissions/dayzOffline.chernarusplus/mapgroupproto.xml').read_bytes()
  try:
   out,rep=p.build_treatment(data,stock,.6)
   print('NATIVE TREATMENT',len(out),rep)
  except Exception as exc:print('NATIVE TREATMENT REFUSAL',type(exc).__name__,str(exc))
