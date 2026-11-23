"""Point-density lootmax rule of the interior point generator (offline arithmetic only)."""
import json
import unittest

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


if __name__ == '__main__':
    unittest.main()
