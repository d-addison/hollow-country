"""Expected safety refusals; all geometry and path results are synthetic, not native evidence."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.unit import test_interior_sampler as m

class SafetyRegressions(unittest.TestCase):
 def test_a_wall_hidden_by_a_nearer_object_does_not_allow_snap(self):
  b=m.flat_building()
  walls=[m.Wall(b,'x',-.2,-3,2,0,3),m.Wall(m.CRATE,'x',-.3,-3,2,0,3)]
  r=m.HookRun(m.default_hook(),b,m.storey_planes(b),nav=m.snap_nav(b),walls=walls).run()
  self.assertNotEqual(1,m.mesh_code(r.row(),-.5,.5))
 def test_a_small_snap_does_not_skip_a_real_wall(self):
  b=m.flat_building()
  r=m.HookRun(m.default_hook(),b,m.storey_planes(b),nav=m.snap_nav(b,east_from=-.46),
              walls=[m.Wall(b,'x',-.48,-3,2,0,3)]).run()
  self.assertNotEqual(1,m.mesh_code(r.row(),-.5,.5))
 def test_final_waypoint_gap_across_a_wall_is_not_reached(self):
  b=m.flat_building()
  class Partial(m.NavMesh):
   def path(self,start,end,waypoints):
    local=self.building.CoordToLocal(end)
    if local[0]>-5:
     self.paths+=1;waypoints.Insert(start)
     waypoints.Insert(self.building.to_world((local[0]+.4,local[1],local[2])))
     return True
    return super().path(start,end,waypoints)
  nav=Partial(b,m.nav_for(b).zones,links=[('out','g'),('g','f')])
  r=m.HookRun(m.default_hook(),b,m.storey_planes(b),nav=nav,
              walls=[m.Wall(b,'x',-3.3,-3,2,0,3)]).run()
  self.assertNotEqual(1,m.mesh_code(r.row(),-3.5,.5))
 def test_a_seed_under_another_objects_roof_is_not_open_sky(self):
  b=m.flat_building()
  planes=m.storey_planes(b)+[m.Plane(m.CRATE,2,-30,-5,-30,30,'other-roof')]
  r=m.HookRun(m.default_hook(),b,planes,nav=m.nav_for(b)).run()
  self.assertNotEqual('tested',r.row()['reach']['state'])

if __name__=='__main__':unittest.main(verbosity=2)
