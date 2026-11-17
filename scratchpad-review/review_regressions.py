"""Expected safety behaviors absent from 93a3042; synthetic data only."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent/'source-copy'))
import old_points_fixtures as f
from tests.unit import test_interior_sampler as m
from tools.audit import interior_points as p
from review_fixtures import room_without_filtered_mesh


class ReviewRegressions(unittest.TestCase):
    def test_unknown_reachability_refuses_treatment(self):
        with self.assertRaises(ValueError):
            p.build_treatment(f.encode(f.full_census()), f.STOCK, 0.4)

    def test_mesh_snap_across_wall_does_not_prove_reachability(self):
        b, nav, floor, nearest = room_without_filtered_mesh()
        run = m.HookRun(m.default_hook(), b, m.storey_planes(b), nav=nav).run()
        self.assertEqual(2, run.model.HCProbeReachHit(floor))
        original_sample = nav.sample
        def snap(position, radius):
            if position == floor:
                return True, nearest
            return original_sample(position, radius)
        run.model.HCProbeSampleMesh.__globals__['HCMockSample'] = snap
        self.assertNotEqual(1, run.model.HCProbeReachHit(floor))

    def test_internal_door_on_isolated_mesh_cannot_validate_exterior_control(self):
        b = m.SampBuilding('Land_Tenement_Big', (3000.0, 20.0, 5000.0),
                          clip=((-20.0, -1.0, -20.0), (20.0, 5.0, 20.0)))
        b.doors = [b.to_world((5.0, 0.0, 0.0))]
        planes = [m.Plane(b, 0, -20, 20, -20, 20, 'floor'),
                  m.Plane(b, 3, -20, 20, -20, 20, 'roof')]
        nav = m.NavMesh(b, [m.Zone('isolated-interior', -20, 20, -20, 20, 0.0)])
        run = m.HookRun(m.default_hook(), b, planes, nav=nav).run()
        self.assertNotEqual('tested', run.row()['reach']['state'])

    def test_staircase_cannot_make_average_between_two_floors_eligible(self):
        rows = []
        for i in range(4):
            lo, hi = ((3.0, 2.8) if i % 2 == 0 else (2.8, 3.0))
            hits = f.cells(0.0, f.XS0, f.ZS, clearance=lo, reach=1)
            hits += f.cells(3.0, f.XS0, f.ZS, clearance=hi, reach=1)
            hits += [[-0.5, y, -0.5, 2.8, 1, 1] for y in (0.5, 1, 1.5, 2, 2.5)]
            rows.append(f.placement('Land_Tenement_Small', hits, index=i))
        candidates = f.candidates_of(rows)
        accepted = p.eligible(candidates['candidates'], candidates['reach_mode'], 0.75)
        self.assertEqual([], [c for c in accepted if c['x'] < -1.0 and c['y'] not in (0.0, 3.0)])

    def test_calibration_with_zero_vertical_coverage_refuses(self):
        document = f.full_census()
        for row in document['placements']:
            if row['class'] in p.CALIBRATION_CLASSES:
                for hit in row['hits']:
                    hit[1] += 100
        stock = f.STOCK.replace(b'-4.5 0.0 3.5', b'-4.5 0.0 -3.5')
        with self.assertRaises(p.CoverageError):
            p.build_treatment(f.encode(document), stock, 0.6)

    def test_missing_barracks_calibration_refuses(self):
        barracks = b'''<group name="Land_Mil_Barracks2" lootmax="1">
<container name="lootFloor" lootmax="1">
<point pos="-4.5 0 -3.5" range="0.4" height="1" />
</container></group>'''
        stock = f.STOCK.replace(b'</lootmax>', barracks + b'</lootmax>')
        with self.assertRaises(p.CoverageError):
            p.build_treatment(f.encode(f.full_census()), stock, 0.4)

    def test_zero_path_budget_includes_control_queries(self):
        b = m.storey_building()
        nav = m.nav_for(b)
        m.HookRun(m.default_hook(path_limit=0), b, m.storey_planes(b), nav=nav).run()
        self.assertEqual(0, nav.paths)


if __name__ == '__main__':
    unittest.main(verbosity=2)
