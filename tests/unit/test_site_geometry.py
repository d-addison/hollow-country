"""Class geometry table: synthetic models and the committed file; no installed PBOs needed."""
import json
import math
from pathlib import Path
from types import SimpleNamespace
import unittest

from tools.package import site_geometry as sg

ROOT = Path(__file__).resolve().parents[2]


def box_points(sx, sz, y=1.0):
    """Eight corners of a centred box, as (x, y, z)."""
    return [(x * sx / 2, y * h, z * sz / 2) for x in (-1, 1) for z in (-1, 1) for h in (0, 1)]


def fake_model(points, doors=None):
    geometry_lod = SimpleNamespace(resolution=1e13, index=0, vertices=points, named_selections=[])
    lods = [geometry_lod]
    if doors is not None:
        vertices, selections = [], []
        for name, (x, z) in doors.items():
            selections.append(SimpleNamespace(name=name, vertices=[len(vertices)]))
            vertices.append((x, 1.0, z))
        lods.append(SimpleNamespace(resolution=sg.MEMORY_LOD, index=1, vertices=vertices,
                                    named_selections=selections))
    return SimpleNamespace(lods=lods, bounding_center=(0.0, 0.0, 0.0))


def info(sx, sz):
    return {'min_m': [-sx / 2, 0.0, -sz / 2], 'max_m': [sx / 2, 1.0, sz / 2], 'size_m': [sx, 1.0, sz],
            'footprint_m': [sx, sz], 'source': 'geometry'}


class AngleTests(unittest.TestCase):
    def test_bearing_is_clockwise_from_plus_z(self):
        self.assertEqual(sg.front_yaw_deg(0, 1), 0.0)
        self.assertEqual(sg.front_yaw_deg(1, 0), 90.0)
        self.assertEqual(sg.front_yaw_deg(0, -1), 180.0)
        self.assertEqual(sg.front_yaw_deg(-1, 0), 270.0)
        self.assertEqual(sg.normalise_deg(-90), 270.0)
        self.assertEqual(sg.normalise_deg(450.04), 90.0)

    def test_axis_info(self):
        self.assertEqual(sg.axis_info([2.0, 6.0]), ('z', 3.0))
        self.assertEqual(sg.axis_info([6.0, 2.0]), ('x', 3.0))
        self.assertEqual(sg.axis_info([2.0, 2.1])[0], None)


class SymmetryTests(unittest.TestCase):
    def test_box_is_symmetric_and_wedge_is_not(self):
        box = [(p[0], p[2]) for p in box_points(2.0, 6.0)]
        scores = sg.asymmetry(box, (0.0, 0.0))
        self.assertEqual(max(scores.values()), 0.0)
        wedge = box + [(0.0, 5.0)]
        self.assertGreater(sg.asymmetry(wedge, (0.0, 0.0))['r180'], 0.05)

    def test_door_ends_ignore_side_doors(self):
        self.assertIsNone(sg.door_ends([(1.0, 0.1)], (0.0, 0.0), [2.5, 6.0]))
        self.assertEqual(sg.door_ends([(0.0, -3.0)], (0.0, 0.0), [2.5, 6.0]), ('z', [-1]))
        self.assertEqual(sg.door_ends([(0.0, -3.0), (0.0, 3.0)], (0.0, 0.0), [2.5, 6.0]), ('z', [-1, 1]))
        self.assertIsNone(sg.door_ends([(0.0, -3.0)], (0.0, 0.0), [2.5, 2.5]))


class MeasureTests(unittest.TestCase):
    def test_measure_model_reads_geometry_and_door_centroids(self):
        model = fake_model(box_points(2.0, 6.0), doors={'Doors1': (0.2, -3.0), 'doors1_axis': (1.0, -3.0)})
        box = ((-1.0, 0.0, -3.0), (1.0, 1.0, 3.0))
        result = sg.measure_model(model, box)
        self.assertEqual(result['door_points'], [[0.2, -3.0]])
        self.assertEqual(result['asymmetry'], {'mx': 0.0, 'mz': 0.0, 'r180': 0.0})


class AssembleTests(unittest.TestCase):
    catalog = {
        'Land_Box': {'kind': 'prop'},
        'Land_Tent': {'kind': 'tent'},
        'Land_Wide': {'kind': 'prop'},
        'Land_Tiny': {'kind': 'prop'},
        'Land_DoorOne': {'kind': 'container'},
        'Land_DoorBoth': {'kind': 'container'},
        'Land_Decal': {'kind': 'prop', 'footprint_reserve_m': [3, 3]},
        'StaticObj_Misc_Pallets1': {'kind': 'prop'},
    }

    def document(self, calibrated=None):
        bounds = {'Land_Box': info(2.0, 2.0), 'Land_Tent': info(6.0, 4.0), 'Land_Wide': info(1.0, 5.0),
                  'Land_Tiny': info(0.3, 0.4), 'Land_DoorOne': info(2.5, 6.0), 'Land_DoorBoth': info(2.5, 6.0),
                  'StaticObj_Misc_Pallets1': info(1.4, 1.8)}
        lopsided = {'mx': 0.0, 'mz': 0.2, 'r180': 0.2}
        flat = {'mx': 0.0, 'mz': 0.0, 'r180': 0.0}
        measures = {
            'Land_Box': {'asymmetry': flat, 'door_points': []},
            'Land_Tent': {'asymmetry': flat, 'door_points': []},
            'Land_Wide': {'asymmetry': lopsided, 'door_points': []},
            'Land_Tiny': {'asymmetry': lopsided, 'door_points': []},
            'Land_DoorOne': {'asymmetry': flat, 'door_points': [[0.0, -3.0]]},
            'Land_DoorBoth': {'asymmetry': flat, 'door_points': [[0.0, -3.0], [0.0, 3.0]]},
            'StaticObj_Misc_Pallets1': {'asymmetry': lopsided, 'door_points': []},
        }
        return sg.assemble(self.catalog, bounds, measures, calibrated)

    def test_classification(self):
        rows = self.document()['classes']
        self.assertEqual((rows['Land_Box']['symmetric'], rows['Land_Box']['symmetry']), (True, 'two_fold'))
        self.assertEqual(rows['Land_Tiny']['symmetry'], 'small')
        self.assertEqual(rows['Land_Tent']['front_source'], 'calibration_pending')
        self.assertIsNone(rows['Land_Tent']['front_yaw_deg'])
        self.assertEqual(rows['Land_Tent']['front_candidates_deg'], [90.0, 270.0])
        self.assertEqual(rows['Land_Wide']['front_source'], 'calibration_pending')
        self.assertEqual(rows['StaticObj_Misc_Pallets1']['symmetry'], 'front_agnostic')
        self.assertEqual(rows['Land_DoorBoth']['symmetry'], 'two_fold_doors')
        self.assertEqual((rows['Land_DoorOne']['front_source'], rows['Land_DoorOne']['front_yaw_deg']),
                         ('odol_memory', 180.0))

    def test_unmeasured_class_uses_reserve_and_is_listed(self):
        document = self.document()
        row = document['classes']['Land_Decal']
        self.assertEqual(document['unmeasured'], ['Land_Decal'])
        self.assertEqual(row['bounds']['source'], 'reserve_unmeasured')
        self.assertEqual(row['symmetry'], 'reserve_square')

    def test_pending_list_is_sorted_directional_classes_only(self):
        document = self.document()
        self.assertEqual(document['calibration_pending'], ['Land_Tent', 'Land_Wide'])

    def test_calibration_wins_and_is_idempotent(self):
        document = self.document({'Land_Tent': 90, 'Land_Box': 'symmetric', 'Land_Wide': 450.0})
        rows = document['classes']
        self.assertEqual((rows['Land_Tent']['front_source'], rows['Land_Tent']['front_yaw_deg']),
                         ('calibrated', 90.0))
        self.assertEqual(rows['Land_Wide']['front_yaw_deg'], 90.0)
        self.assertEqual(rows['Land_Box']['symmetry'], 'calibrated')
        self.assertNotIn('front_candidates_deg', rows['Land_Tent'])
        self.assertEqual(document['calibration_pending'], [])
        again = sg.overlay_calibration(dict(rows['Land_Tent']), 90.0)
        self.assertEqual(again, rows['Land_Tent'])

    def test_set_front_matches_rebuild_with_calibrated_input(self):
        updates = {'Land_Tent': 270.0, 'Land_Wide': 'symmetric'}
        edited = sg.set_front(json.loads(sg.render(self.document())), updates)
        self.assertEqual(sg.render(edited), sg.render(self.document(updates)))

    def test_set_front_rejects_unknown_class(self):
        with self.assertRaises(KeyError):
            sg.set_front(self.document(), {'Land_Missing': 0.0})
        self.assertEqual(sg.parse_set_front(['A=-90', 'B=symmetric']), {'A': 270.0, 'B': 'symmetric'})
        with self.assertRaises(ValueError):
            sg.parse_set_front(['A'])

    def test_render_is_deterministic(self):
        self.assertEqual(sg.render(self.document()), sg.render(self.document()))
        self.assertTrue(sg.render(self.document()).endswith('}\n'))

    def test_calibration_text_lists_pending(self):
        text = sg.calibration_text(self.document())
        self.assertIn('2 classes need a front', text)
        self.assertIn('Land_Tent', text)


class CommittedFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads((ROOT / sg.OUTPUT).read_text(encoding='utf-8'))
        cls.catalog = json.loads((ROOT / sg.CATALOG).read_text(encoding='utf-8'))['classes']

    def test_every_catalogue_class_has_a_row(self):
        self.assertEqual(sorted(self.document['classes']), sorted(self.catalog))

    def test_rows_are_symmetric_or_have_a_front_source(self):
        for name, row in self.document['classes'].items():
            self.assertEqual(len(row['bounds']['footprint_m']), 2, name)
            self.assertGreater(min(row['bounds']['footprint_m']), 0.0, name)
            if row['symmetric']:
                self.assertNotIn('front_yaw_deg', row, name)
            else:
                self.assertIn(row['front_source'], ('odol_memory', 'calibration_pending', 'calibrated'), name)
                if row['front_source'] == 'calibration_pending':
                    self.assertIsNone(row['front_yaw_deg'], name)
                else:
                    self.assertTrue(0.0 <= row['front_yaw_deg'] < 360.0, name)

    def test_pending_list_matches_rows(self):
        self.assertEqual(self.document['calibration_pending'], sg.pending_list(self.document['classes']))

    def test_unmeasured_matches_reserve_rows(self):
        reserve = sorted(n for n, r in self.document['classes'].items()
                         if r['bounds']['source'] == 'reserve_unmeasured')
        self.assertEqual(self.document['unmeasured'], reserve)

    def test_file_is_canonical_and_numbers_only(self):
        text = (ROOT / sg.OUTPUT).read_text(encoding='utf-8')
        self.assertEqual(text, sg.render(json.loads(text)))
        self.assertNotIn('.p3d', text.lower())
        for row in self.document['classes'].values():
            for value in row['bounds']['size_m'] + row['center_xz_m']:
                self.assertTrue(math.isfinite(value))


if __name__ == '__main__':
    unittest.main()
