"""Synthetic native census admission and geometry audits; no DayZ behaviour claims."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.package import new_buildings as nb
from tools.audit import interior_points as pts


def census(name='Land_Test', hits=None, run='a' * 32):
    hits = [[.25, 0, .25, 3, 1, -1]] if hits is None else hits
    row = {'class': name, 'i': 0, 'found': True, 'box_source': 'clipping',
           'box_min': [0, -1, 0], 'box_max': [1, 4, 1], 'grid': {'step': 1},
           'hits': hits, 'player_codes': [-1] * len(hits), 'open_player_codes': [-1] * len(hits),
           'reach': {'player': {'state': 'no-door'}}, 'stats': {}}
    calibration = copy.deepcopy(row)
    calibration.update({'class': pts.CALIBRATION_CLASSES[0],
                        'frame': [[i, 0, -i, 0, 0, 1, 0] for i in range(8)]})
    return {'Synthetic': True, 'schema': 1, 'kind': pts.CENSUS_KIND,
            'door_phase_contract': pts.DOOR_PHASE_CONTRACT, 'native_run_id': run,
            'house_classes': [name, calibration['class']], 'placements': [row, calibration],
            'summary': {'complete': True}}


class NativeInputs(unittest.TestCase):
    def load(self, *docs):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for i, doc in enumerate(docs):
                path = Path(directory) / ('census-%d.json' % i)
                path.write_text(json.dumps(doc))
                paths.append(path)
            return nb.native_inputs(paths)

    def test_shared_parser_provenance_and_sorted_runs(self):
        docs, rows = self.load(census(run='b' * 32), census())
        self.assertEqual([d['run'] for d in docs], sorted(d['run'] for d in docs))
        sample = rows['Land_Test']
        self.assertEqual(len(sample['hits']), sum(r['hit_count'] for r in sample['runs']))
        self.assertEqual(sample['hits'][0], (.25, 0, .25, 3))
        self.assertTrue(all(len(d['sha']) == 64 for d in docs))

    def test_incomplete_or_duplicate_or_wrong_frame_refused(self):
        doc = census()
        doc['summary']['complete'] = False
        with self.assertRaises(ValueError):
            self.load(doc)
        with self.assertRaises(ValueError):
            self.load(census(), census())
        doc = census()
        doc['placements'][1]['frame'] = [[i, 0, -i, 1, 0, 0, 0] for i in range(8)]
        with self.assertRaises(ValueError):
            self.load(doc)

    def test_caps_and_failed_path_never_widen_admission(self):
        for mutation in ('cap', 'failed'):
            doc = census()
            row = doc['placements'][0]
            if mutation == 'cap':
                row['stats']['ray_capped'] = True
            else:
                row['reach']['player']['state'] = 'tested'
                row['open_player_codes'] = [0]
            _, rows = self.load(doc)
            self.assertEqual(rows['Land_Test']['hits'], [])
            self.assertTrue(rows['Land_Test']['refusals'])

    def test_missing_parallel_codes_refused_and_zero_hits_retained(self):
        doc = census()
        del doc['placements'][0]['open_player_codes']
        with self.assertRaises(ValueError):
            self.load(doc)
        _, rows = self.load(census(hits=[]))
        self.assertEqual(rows['Land_Test']['runs'][0]['observed_hit_count'], 0)


class GeometryAudits(unittest.TestCase):
    def setUp(self):
        self.stats = {k: 0 for k in ('supported', 'standing', 'roofed', 'enclosed', 'eligible')}
        self.footprint = SimpleNamespace(floors=lambda *args: [0])
        self.visual = SimpleNamespace(hits=lambda *args: [(3,)])
        self.scene = SimpleNamespace(clear=lambda *args: True)
        self.solid = SimpleNamespace(clear=lambda *args: False)

    def audit(self, native=True):
        return nb._floor_audit(.25, 0, .25, self.footprint, self.visual, self.scene,
                               self.solid, self.stats, native=native)

    def test_native_standing_only_replaces_body_check(self):
        with patch('tools.package.loot_reach_audit.body_clear', return_value=False):
            self.assertEqual(self.audit(native=False), (False, False))
            self.assertEqual(self.audit(), (True, True))

    def test_native_never_bypasses_support_roof_walls_or_loader(self):
        self.footprint.floors = lambda *args: []
        self.assertEqual(self.audit(), (False, False))
        self.footprint.floors = lambda *args: [0]
        self.visual.hits = lambda *args: []
        self.assertEqual(self.audit(), (True, False))
        self.visual.hits = lambda *args: [(1,)]
        self.assertEqual(self.audit(), (True, False))
        self.visual.hits = lambda *args: [(3,)]
        self.solid.clear = lambda *args: True
        self.assertEqual(self.audit(), (True, False))
        self.solid.clear = lambda *args: False
        self.scene.clear = lambda *args: False
        self.assertEqual(self.audit(), (True, False))

    def test_native_point_conversion_and_clearance(self):
        model = SimpleNamespace(lods=[])
        auditor = SimpleNamespace(scene=lambda *args: (None, model, self.visual, self.scene,
                                   {'Min': [0, -1, 0], 'Max': [.5, 4, .5]}, None, self.footprint))
        with patch.object(nb, '_walk_scene', return_value=self.scene), \
                patch('tools.package.loot_reach_audit.body_clear', return_value=False):
            # Use scene walls for enclosure, but keep vertical loader rays clear.
            self.scene.clear = lambda a, b: a[0] == b[0] and a[2] == b[2]
            hits = [[.25, 0, .25, 3]]
            points, stats = nb.floor_points(auditor, 'Land_Test', 'pin', {'hits': hits, 'runs': []})
            self.assertEqual(points, [[.25, .005, -.25]])
            self.assertEqual(stats['native']['audited_points'], len(hits))
            hits[0][3] = nb.CEILING[0] - .1
            points, _ = nb.floor_points(auditor, 'Land_Test', 'pin', {'hits': hits, 'runs': []})
            self.assertEqual(points, [])

    def test_stock_hash_apply_remains_all_or_nothing(self):
        doc = json.loads((nb.REPO_ROOT / nb.PATH).read_bytes())
        proto, pos = b'<prototype/>', b'<map/>'
        a, b, report = nb.apply(proto, pos, json.dumps(doc).encode())
        self.assertEqual((a, b), (proto, pos))
        self.assertFalse(report['applied'])


if __name__ == '__main__':
    unittest.main()
