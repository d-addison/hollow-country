"""Reviewer scenarios use explicit synthetic geometry/census; never native acceptance."""
from pathlib import Path
import sys,copy,json,hashlib,unittest,io
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source-copy'))
from tests.unit import test_interior_sampler as m,test_interior_points as f
from tools.audit import interior_points as p
from tools.setup import interior_sampler as s
hook=m.default_hook()
def build(label,d):
 try:
  out,rep=p.build_treatment(f.encode(d),f.STOCK,.4,reach_source=label.split(':')[0] if ':' in label else 'strict')
  print(label,'ACCEPTED',len(out),'bytes; selected',{n:rep['classes'][n]['selected'] for n in p.TENEMENT_CLASSES},'control_states',{n:rep['funnel'][n]['control_states'] for n in p.TENEMENT_CLASSES})
 except ValueError as e: print(label,'REFUSED',str(e))
def row_to_treatment(label,row):
 d=f.full_census();d['placements']=[r for r in d['placements'] if r['class']!=p.TENEMENT_CLASSES[0]]
 for i in range(4):r=copy.deepcopy(row);r['i']=i;d['placements'].append(r)
 try:
  _,rep=p.build_treatment(f.encode(d),f.STOCK,.4)
  print(label,'selected',[(v['x'],v['y'],v['z']) for v in rep['classes'][p.TENEMENT_CLASSES[0]]['points']])
 except ValueError as e:print(label,'REFUSED',str(e))
b=m.flat_building();base=m.storey_planes(b)
for label,walls in [('owner-wall',[m.Wall(b,'x',-.2,-3,2,0,3)]),('masked-owner-wall',[m.Wall(b,'x',-.2,-3,2,0,3),m.Wall(m.CRATE,'x',-.3,-3,2,0,3)])]:
 r=m.HookRun(hook,b,base,nav=m.snap_nav(b),walls=walls).run().row();print(label,m.mesh_code(r,-.5,.5))
print('four-centimetre-wall-snap',m.mesh_code(m.run_small_snap(hook),-.5,.5))
print('40cm-final-gap-wall',m.mesh_code(m.run_final_gap_wall(hook),-3.5,.5))
print('foreign-roof-low',m.run_other_roof(hook)['reach']['state'])
r=m.run_waist_slot(hook);print('r3-waist-slot',m.mesh_code(r,-.5,.5));row_to_treatment('r3-waist-slot',r)
solid=m.Plane(m.CRATE,2.4,-5,7,-4,3,'solid-block',thick=2.3)
r=m.HookRun(hook,b,base+[solid],nav=m.nav_for(b)).run().row()
print('r3-solid-block',m.mesh_code(r,-3.5,.5));row_to_treatment('r3-solid-block',r)
b=m.tiny_building();r=m.HookRun(hook,b,[m.Plane(b,3.5,-5,5,-5,5,'owner-solid',thick=3),m.Plane(b,0,-5,5,-5,5,'floor')],ai=False).run().row()
print('r3-owner-rehits','heights',sorted({round(h[1],3) for h in r['hits']}),'rehits',r['stats']['rehits'])
print('prior snap-wall codes', [m.mesh_code(r,-.5,.5) for r in m.run_snap_wall(hook)])
print('prior snap-distance codes', [m.mesh_code(r,-.5,.5) for r in m.run_snap_distance(hook)])
print('prior internal-island control',m.run_isolated_mesh(hook)[0]['reach']['state'])
print('prior projected-inside control',m.run_seed_projection(hook)['reach']['state'])
r,nav=m.run_zero_paths(hook);print('prior zero-budget','samples',nav.samples,'paths',nav.paths,'variant counters',r['stats']['paths'],r['stats']['player_paths'])
d=f.full_census()
for row in d['placements']:
 if row['class'] in p.TENEMENT_CLASSES:
  for h in row['hits']:h[5]=-1
build('unknown-tenements',d)
rows=f.four_placements(p.TENEMENT_CLASSES[0])
for i,row in enumerate(rows):
 for h in row['hits']:h[5]=1 if i==0 else -1
c=f.candidates_of(rows);print('one-yes-three-unknown',len(p.eligible(c['candidates'],c['reach_mode'],.75)))
d=f.full_census()
for row in d['placements']:
 if row['class'] in p.CALIBRATION_CLASSES:
  for h in row['hits']:h[1]+=100
build('vertical-calibration+100',d)
d=f.full_census();d['placements']=[r for r in d['placements'] if r['class']!=p.CALIBRATION_CLASSES[1]];build('missing-barracks',d)
rows=[]
for i in range(4):
 lo,hi=(3,2.8) if i%2==0 else (2.8,3)
 hits=f.cells(0,f.XS0,f.ZS,clearance=lo)+f.cells(3,f.XS0,f.ZS,clearance=hi)+[[-.5,y,-.5,2.8,1,1] for y in (.5,1,1.5,2,2.5)]
 rows.append(f.placement(p.TENEMENT_CLASSES[0],hits,index=i))
c=f.candidates_of(rows);print('stair-bridge',sorted({v['y'] for v in p.eligible(c['candidates'],c['reach_mode'],.75) if v['x']<-1}))
for source in ('strict','player'):
 for state in ('control-failed','unavailable',None):
  d=f.full_census()
  for row in d['placements']:
   row['player_codes']=[h[5] for h in row['hits']]
   row['reach']['player']={'state':'tested'}
   if row['class'] in p.TENEMENT_CLASSES:
    target=row['reach'] if source=='strict' else row['reach']['player']
    if state is None:target.pop('state',None)
    else:target['state']=state
  build(source+':'+str(state),d)
# Original remaining exterior-control limitations, no actual engine mesh is asserted.
b=m.flat_building();r=m.HookRun(hook,b,m.storey_planes(b)+[m.Plane(m.CRATE,20,-40,-5,-30,30,'high-foreign-roof')],nav=m.nav_for(b)).run().row()
print('foreign-roof-above-finite-sky',r['reach']['state'],[a[2] for a in r['reach']['attempts']])
b=m.SampBuilding('Land_Tenement_Small',(1.,20.,5000.),clip=m.BOX);b.doors=[b.to_world((-4.9,1.,-.5))]
r=m.HookRun(hook,b,m.storey_planes(b),nav=m.nav_for(b)).run();print('map-edge-mocked-mesh',r.row()['reach']['state'],r.model.m_HCProbeSeedWorld)
