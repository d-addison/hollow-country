"""Synthetic counterexamples, not native evidence. Writes nothing outside scratchpad-review."""
import sys, math, copy
from pathlib import Path
from collections import Counter
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.unit import test_interior_sampler as m
from tests.unit import test_interior_points as f
from tools.audit import interior_points as p
from tools.setup import interior_sampler as s, ce_probe

b=m.flat_building(); planes=m.storey_planes(b)
wall=m.Wall(b,'x',-0.2,-3,2,0,3)
mask=m.Wall(m.CRATE,'x',-0.3,-3,2,0,3)
for label,walls in [('building-wall',[wall]),('same-wall-masked-by-other-object',[wall,mask])]:
 r=m.HookRun(m.default_hook(),b,planes,nav=m.snap_nav(b),walls=walls).run()
 print(label, 'state',r.row()['reach']['state'],'floor (-.5,0,.5) reach',m.mesh_code(r.row(),-.5,.5))

# A 4 cm snap across a thin wall takes the branch that omits the wall ray.
nav=m.snap_nav(b,east_from=-0.46)
r=m.HookRun(m.default_hook(),b,planes,nav=nav,walls=[m.Wall(b,'x',-0.48,-3,2,0,3)]).run()
print('four-centimetre-snap-across-wall:',m.mesh_code(r.row(),-.5,.5))

# Same allowed short/partial path model as the worker's tests, but a wall lies in the final gap.
class Truncated(m.NavMesh):
 def path(self,start,end,waypoints):
  local=self.building.CoordToLocal(end)
  if local[0]>-5:
   self.paths+=1
   waypoints.Insert(start);waypoints.Insert(self.building.to_world((local[0]+.4,local[1],local[2])))
   return True
  return super().path(start,end,waypoints)
nav=Truncated(b,m.nav_for(b).zones,links=[('out','g'),('g','f')])
r=m.HookRun(m.default_hook(),b,planes,nav=nav,walls=[m.Wall(b,'x',-3.3,-3,2,0,3)]).run()
print('endpoint-stops-40cm-away-across-wall:',r.row()['reach']['state'],m.mesh_code(r.row(),-3.5,.5))

# An overhead object other than the sampled building is skipped by the 'open sky' check.
nav=m.nav_for(b)
r=m.HookRun(m.default_hook(),b,planes+[m.Plane(m.CRATE,2,-30,-5,-30,30,'other-roof')],nav=nav).run()
print('seed-under-other-object-roof:',r.row()['reach']['state'])

# Original mixed unknown reproduction.
rows=f.four_placements(p.TENEMENT_CLASSES[0])
for i,row in enumerate(rows):
 for h in row['hits']:h[5]=1 if i==0 else -1
c=f.candidates_of(rows)
print('one-yes-three-unknown-eligible:',len(p.eligible(c['candidates'],c['reach_mode'],.75)))
# Actual stock writer checks, with explicit synthetic selections only (no native census).
stock=Path('/mnt/d/HollowCountryLocal/vanilla-p0-001/stock-backup/mpmissions/dayzOffline.chernarusplus/mapgroupproto.xml').read_bytes()
sel={n:[{'x':float(i)+.5,'y':0.,'z':.5} for i in range(5)] for n in p.TENEMENT_CLASSES}
a=p.write_treatment(stock,sel);z=p.write_treatment(stock,sel)
print('stock syntax attribute counts:',dict(Counter(tuple(sorted(x.attrib)) for x in ET.fromstring(stock).iter('point'))))
print('real-stock parses:',ET.fromstring(a).tag,'outside bytes identical:',p._outside_groups(stock,sel)==p._outside_groups(a,sel),'deterministic:',a==z)
for g in ET.fromstring(a).iter('group'):
 if g.get('name') in sel:print('stock treatment',g.get('name'),'group lootmax',g.get('lootmax'),'containers',[(x.get('name'),x.get('lootmax'),len(x.findall('point'))) for x in g.findall('container')])
print('lootmax boundaries:',[(n,p._lootmax_for(n,.25,12)) for n in (1,4,5,48,49,100)])
print('native type lint:',s.lint_sampler_hook(m.default_hook(),ce_probe.native_type_names(Path('/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289'))))

# End-to-end treatment from the masked-wall census, with explicit synthetic calibration fixtures.
r=m.HookRun(m.default_hook(),b,planes,nav=m.snap_nav(b),walls=[wall,mask]).run()
d=f.full_census();d['placements']=[row for row in d['placements'] if row['class']!=p.TENEMENT_CLASSES[0]]
for i in range(4):
 row=copy.deepcopy(r.row());row['i']=i;d['placements'].append(row)
_,report=p.build_treatment(f.encode(d),f.STOCK,.4)
print('masked-wall selected point coordinates:',[(v['x'],v['y'],v['z']) for v in report['classes'][p.TENEMENT_CLASSES[0]]['points']])

# Recheck refusals without allowing another missing-calibration gate to mask the behavior.
d=f.full_census()
for row in d['placements']:
 if row['class'] in p.TENEMENT_CLASSES:
  for h in row['hits']:h[5]=-1
try:p.build_treatment(f.encode(d),f.STOCK,.4)
except ValueError as e:print('unknown-tenements-only refusal:',type(e).__name__,str(e))
d=f.full_census()
for row in d['placements']:
 if row['class'] in p.CALIBRATION_CLASSES:
  for h in row['hits']:h[1]+=100
try:p.build_treatment(f.encode(d),f.STOCK,.6)
except ValueError as e:print('vertical-only refusal:',type(e).__name__,str(e))
d=f.full_census();d['placements']=[row for row in d['placements'] if row['class']!=p.CALIBRATION_CLASSES[1]]
try:p.build_treatment(f.encode(d),f.STOCK,.4)
except ValueError as e:print('missing-barracks refusal:',type(e).__name__,str(e))
rows=[]
for i in range(4):
 lo,hi=(3.,2.8) if i%2==0 else (2.8,3.)
 hits=f.cells(0.,f.XS0,f.ZS,clearance=lo)+f.cells(3.,f.XS0,f.ZS,clearance=hi)
 hits += [[-.5,y,-.5,2.8,1,1] for y in (.5,1.,1.5,2.,2.5)]
 rows.append(f.placement(p.TENEMENT_CLASSES[0],hits,index=i))
c=f.candidates_of(rows)
print('stair-bridge eligible physical heights:',sorted({v['y'] for v in p.eligible(c['candidates'],c['reach_mode'],.75) if v['x'] < -1.}))
