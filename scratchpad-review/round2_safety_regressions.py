"""Safety expectations against explicit synthetic geometry, never engine acceptance."""
from pathlib import Path
import sys,unittest,copy
sys.path.insert(0,str(Path(__file__).resolve().parent/'source-copy'))
from tests.unit import test_interior_sampler as m,test_interior_points as f
from tools.audit import interior_points as p

class Round2Safety(unittest.TestCase):
 def test_a_twenty_centimetre_waist_slot_does_not_make_a_wall_player_passable(self):
  b=m.flat_building()
  walls=[m.Wall(b,'x',-.2,-3,2,0,.9),m.Wall(b,'x',-.2,-3,2,1.1,3),m.Wall(b,'x',-1,-3,2,0,3),m.Wall(b,'z',-3,-1,-.2,0,3),m.Wall(b,'z',2,-1,-.2,0,3)]
  row=m.HookRun(m.default_hook(),b,m.storey_planes(b),nav=m.snap_nav(b),walls=walls).run().row()
  self.assertNotEqual(1,m.mesh_code(row,-.5,.5))
 def test_a_solid_foreign_obstruction_is_not_free_player_clearance(self):
  b=m.flat_building()
  solid=m.Plane(m.CRATE,2.4,-5,7,-4,3,'solid-block',thick=2.3)
  row=m.HookRun(m.default_hook(),b,m.storey_planes(b)+[solid],nav=m.nav_for(b)).run().row()
  self.assertNotEqual(1,m.mesh_code(row,-3.5,.5))
 def test_start_inside_owner_rehits_are_not_new_floor_surfaces(self):
  b=m.tiny_building()
  roof=m.Plane(b,3.5,-5,5,-5,5,'owner-solid',thick=3.)
  row=m.HookRun(m.default_hook(),b,[roof,m.Plane(b,0,-5,5,-5,5,'floor')],ai=False).run().row()
  self.assertEqual({0.0},{round(h[1],3) for h in row['hits']})

if __name__=='__main__':unittest.main(verbosity=2)
