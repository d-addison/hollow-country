"""Point-density lootmax rule of the interior point generator (offline arithmetic only)."""
import json
import unittest
import xml.etree.ElementTree as ET

from tools.package import interior_points_gen as gen
from tools.package import loot_boost as boost


def overlay(surface_points, floor_points, area=40.0):
    containers = {}
    if surface_points:
        containers['lootHCSurface'] = {'lootmax': 1, 'categories': ['tools'], 'tags': ['shelves'],
                                       'points': [[i, 0.0, 0.0] for i in range(surface_points)]}
    if floor_points:
        containers['lootHCFloor'] = {'lootmax': 1, 'categories': ['clothes'], 'tags': ['floor'],
                                     'points': [[i, 0.0, 5.0] for i in range(floor_points)]}
    return {'schema': 1, 'kind': boost.OVERLAY_KIND, 'frame': 'stock-mapgroupproto',
            'runtime_acceptance': boost.PENDING, 'sources': {},
            'groups': {'Land_Test': {'family': 'civic', 'stock_sha256': 'a' * 64,
                                     'containers': containers, 'interior_area_m2': area}}}


class DensityLootmax(unittest.TestCase):
    def test_never_below_the_size_realistic_value(self):
        for count in range(1, 40):
            for area in (None, 6.0, 45.0, 300.0):
                self.assertGreaterEqual(gen.density_lootmax(count, area), boost.added_lootmax(count, area))

    def test_bounded_by_points_and_the_container_cap(self):
        for count in range(1, 60):
            for density in (gen.SURFACE_DENSITY, gen.FLOOR_DENSITY):
                value = gen.density_lootmax(count, 500.0, density)
                self.assertLessEqual(value, min(count, boost.MAX_ADDED_LOOTMAX))
                self.assertGreaterEqual(value, 1)

    def test_density_values(self):
        self.assertEqual(gen.density_lootmax(8, 600.0), 6)
        self.assertEqual(gen.density_lootmax(8, 600.0, gen.FLOOR_DENSITY), 4)
        self.assertEqual(gen.density_lootmax(30, 600.0), boost.MAX_ADDED_LOOTMAX)
        self.assertEqual(gen.density_lootmax(1, 3.0), 1)


class OccupiedPoints(unittest.TestCase):
    def test_reserves_both_surface_and_floor_additions(self):
        group = ET.fromstring('<group name="Land_Test"/>')
        spec = overlay(2, 1)['groups']['Land_Test']
        spec['stock_sha256'] = boost.group_pin(group)
        self.assertEqual([[0, 0., 0.], [1, 0., 0.], [0, 0., 5.]],
                         gen.occupied_points(group, {'Land_Test': spec}))
        self.assertEqual([], list(group.iter('point')))  # no synthetic native anchors

    def test_refuses_coordinates_for_a_different_native_group(self):
        group = ET.fromstring('<group name="Land_Test"/>')
        with self.assertRaisesRegex(ValueError, 'stock pin mismatch'):
            gen.occupied_points(group, overlay(2, 0)['groups'])

    def test_uncovered_group_has_no_reservations(self):
        self.assertEqual([], gen.occupied_points(ET.fromstring('<group name="Land_Other"/>'),
                                               overlay(2, 0)['groups']))


class ResizeOverlay(unittest.TestCase):
    def test_resize_is_idempotent_and_keeps_points(self):
        raw = (json.dumps(overlay(8, 6), sort_keys=True, indent=2) + '\n').encode()
        once = gen.resize_lootmax(raw)
        self.assertEqual(gen.resize_lootmax(once), once)
        before, after = json.loads(raw), json.loads(once)
        for kind in ('lootHCSurface', 'lootHCFloor'):
            self.assertEqual(before['groups']['Land_Test']['containers'][kind]['points'],
                             after['groups']['Land_Test']['containers'][kind]['points'])
        containers = after['groups']['Land_Test']['containers']
        self.assertEqual(containers['lootHCSurface']['lootmax'], 6)
        self.assertEqual(containers['lootHCFloor']['lootmax'], 3)


class ReplaceFloorGroups(unittest.TestCase):
    def additions(self, floor_points):
        doc = overlay(0, floor_points)
        doc['sources'] = {'hc_floor_generation': {'method': 'test', 'stock_proto_sha256': 'b' * 64,
                                                  'refusal_counts': {}, 'rejected_groups': {}}}
        return doc

    def test_replace_swaps_only_with_the_flag(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'base.json'
            base.write_bytes((json.dumps(overlay(0, 3), sort_keys=True, indent=2) + '\n').encode())
            with self.assertRaises(ValueError):
                gen.add_floor_groups(base, self.additions(5))
            raw = gen.add_floor_groups(base, self.additions(5), replace=True, label='hc_floor_test')
        group = json.loads(raw)['groups']['Land_Test']['containers']['lootHCFloor']
        self.assertEqual(len(group['points']), 5)
        self.assertIn('hc_floor_test', json.loads(raw)['sources'])


if __name__ == '__main__':
    unittest.main()
