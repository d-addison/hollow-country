"""Explicit synthetic counterexamples. They do not establish native collision/navigation behavior."""
from pathlib import Path
import sys,copy,json,collections
sys.path.insert(0,str(Path(__file__).resolve().parent/'source-copy'))
from tests.unit import test_interior_sampler as m,test_interior_points as f
from tools.audit import interior_points as p

def code(row,x=-.5,z=.5): return m.mesh_code(row,x,z)
b=m.flat_building();base=m.storey_planes(b)
# A full wall except for a 20 cm horizontal slot at waist height; no player can cross the slot.
walls=[m.Wall(b,'x',-.2,-3,2,0,.9),m.Wall(b,'x',-.2,-3,2,1.1,3),m.Wall(b,'x',-1,-3,2,0,3),m.Wall(b,'z',-3,-1,-.2,0,3),m.Wall(b,'z',2,-1,-.2,0,3)]
r=m.HookRun(m.default_hook(),b,base,nav=m.snap_nav(b),walls=walls).run()
print('waist-slot-wall: reach state',r.row()['reach']['state'],'floor(-.5,0,.5) reach',code(r.row()))
d=f.full_census();d['placements']=[row for row in d['placements'] if row['class']!=p.TENEMENT_CLASSES[0]]
for i in range(4):row=copy.deepcopy(r.row());row['i']=i;d['placements'].append(row)
_,rep=p.build_treatment(f.encode(d),f.STOCK,.4)
print('waist-slot-wall selected:',[(v['x'],v['y'],v['z']) for v in rep['classes'][p.TENEMENT_CLASSES[0]]['points']])
# Owner floor is under a solid foreign object spanning 0.1..2.4 m. It has no player headroom.
crate=m.Plane(m.CRATE,2.4,-5,7,-4,3,'solid-block',thick=2.3)
r=m.HookRun(m.default_hook(),b,base+[crate],nav=m.nav_for(b)).run()
print('foreign-solid-at-loot-point: reach state',r.row()['reach']['state'],'floor(-3.5,0,.5) reach',code(r.row(),-3.5),'floor row',[h for h in r.row()['hits'] if h[0]==-3.5 and h[2]==.5])
d=f.full_census();d['placements']=[row for row in d['placements'] if row['class']!=p.TENEMENT_CLASSES[0]]
for i in range(4):row=copy.deepcopy(r.row());row['i']=i;d['placements'].append(row)
_,rep=p.build_treatment(f.encode(d),f.STOCK,.4)
print('foreign-solid selected:',[(v['x'],v['y'],v['z']) for v in rep['classes'][p.TENEMENT_CLASSES[0]]['points']])
# Ground-plane 30 m away can cover a neighboring structure that extends above the finite own-height sky ray.
foreign_roof=m.Plane(m.CRATE,20,-40,-5,-30,30,'high-foreign-roof')
r=m.HookRun(m.default_hook(),b,base+[foreign_roof],nav=m.nav_for(b)).run()
print('foreign-roof-above-sky-ray: state',r.row()['reach']['state'],'attempts',r.row()['reach']['attempts'])
# Water/bounds are not queried by the hook. Explicitly synthetic mesh responses outside map/on water.
for label,pos in [('near-west-map-edge',(1.,20.,5000.)),('synthetic-water',(3000.,20.,5000.))]:
 b=m.SampBuilding('Land_Tenement_Small',pos,clip=m.BOX);b.doors=[b.to_world((-4.9,1.,-.5))]
 r=m.HookRun(m.default_hook(),b,m.storey_planes(b),nav=m.nav_for(b)).run()
 print(label,'state',r.row()['reach']['state'],'seed world',r.model.m_HCProbeSeedWorld)
# Re-hit positions inside an owner solid must not be interpreted as newly crossed surfaces.
b=m.tiny_building();roof=m.Plane(b,3.5,-5,5,-5,5,'thick-owner',thick=3.0)
r=m.HookRun(m.default_hook(),b,[roof,m.Plane(b,0,-5,5,-5,5,'floor')],ai=False).run()
print('owner-start-inside-rehits: stat',r.row()['stats'],'distinct emitted heights',sorted({round(h[1],3) for h in r.row()['hits']}))
print('owner-start-inside-rehits records',r.row()['hits'][:8])
