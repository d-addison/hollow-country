from pathlib import Path
import sys,collections,json
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source-copy'))
from tests.unit import test_interior_sampler as m
from tools.audit import interior_points as p
hook=m.default_hook()
for label,overrides in [('default',{}),('path0',{'m_HCProbePathLimit':0}),('path3',{'m_HCProbePathLimit':3}),('step3',{'m_HCProbeStepLimit':3}),('floor2',{'m_HCProbeHitLimit':2}),('ray0',{'m_HCProbeBuildingRayLimit':0})]:
 b=m.flat_building();nav=m.nav_for(b);run=m.HookRun(hook,b,m.storey_planes(b),nav=nav,overrides=overrides).run();row=run.row()
 print(label,'control',row['reach']['state'],row['reach']['player']['state'],'codes',dict(collections.Counter(h[5] for h in row['hits'])),'player',dict(collections.Counter(row['player_codes'])),'paths',row['stats']['paths'],row['stats']['player_paths'],'mesh_calls',len(nav.filters),'ray_capped',row['stats']['ray_capped'])
 if label=='default':
  print('diagnostics bytes',len(json.dumps(row['reach_diag'],separators=(',',':'))),'max samples',max(len(e['samples']) for v in row['reach_diag'].values() for e in v.values()))
  print('diagnostic counts equal candidates:',{v:sum(e['count'] for e in row['reach_diag'][v].values()) for v in ('strict','player')},'candidates',len(m.candidates(row)))
b=m.flat_building();run=m.HookRun(hook,b,m.storey_planes(b),nav=m.inside_nav(b,gap_x=.3)).run()
model=run.model;floor=b.to_world((-3.5,0,.5))
model.m_HCProbeBuildingRayLimit=model.m_HCProbeBuildingRays
print('unknown direct baseline Blocked:',model.HCProbeBlocked(floor,floor),'row-capped:',model.m_HCProbeRayCapped)
model.HCProbeBlocked=lambda a,b: model.HCProbeRay(a,b)>0
print('unknown-ray-clear mutant hit code:',model.HCProbeReachHit(0,floor,2.8,0),'row-capped:',model.m_HCProbeRayCapped)
# Unknown *geometry* does not become a free roofed candidate.
