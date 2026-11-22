"""Route source pin generator: reads the authored pin, refuses drift, stays mission-edit stable."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.audit import gapcode_routes_pins as pins


class RoutePinTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.mission = self.root / 'mission/hollow-country'
        self.roads = self.root / 'installed.roads'
        self.roads.write_bytes(b'road-data\n' * 1000)
        self.source = {'road_virtual_path': 'Vendor/Roads/Map.roads',
                       'road_sha256': hashlib.sha256(self.roads.read_bytes()).hexdigest()}
        self.save(pins.CARAVANS, {'gapcov_graph_source': dict(self.source, sites_sha256='x')})
        self.save(pins.CATALOG_INDEX, {'sources': dict(self.source)})
        for name in pins.MISSION_SOURCES:
            self.save(name, {'rows': []})

    def save(self, name, document):
        target = self.mission / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document))

    def test_pins_follow_the_authored_source_and_page_the_road_bytes(self):
        document = pins.build_pins(self.root, self.roads)
        road = document['Files'][0]
        self.assertEqual(self.source['road_virtual_path'], road['Path'])
        self.assertEqual(self.source['road_sha256'], road['Sha256'])
        data = self.roads.read_bytes()
        self.assertEqual(len(data), road['Bytes'])
        self.assertEqual(-(-len(data) // pins.CHUNK_BYTES), len(road['Pages']))
        self.assertEqual(['$mission:hollow-country/' + n for n in pins.MISSION_SOURCES],
                         [row['Path'] for row in document['Files'][1:]])

    def test_written_file_checks_and_survives_mission_source_edits(self):
        pins.write_pins(self.root, self.roads)
        self.assertTrue(pins.check_pins(self.root, self.roads))
        self.save(pins.MISSION_SOURCES[0], {'rows': ['edited']})
        self.assertTrue(pins.check_pins(self.root, self.roads))

    def test_changed_road_bytes_are_refused(self):
        self.roads.write_bytes(self.roads.read_bytes() + b'x')
        with self.assertRaises(ValueError):
            pins.build_pins(self.root, self.roads)

    def test_disagreeing_catalog_index_is_refused(self):
        self.save(pins.CATALOG_INDEX, {'sources': dict(self.source, road_sha256='0' * 64)})
        with self.assertRaises(ValueError):
            pins.build_pins(self.root, self.roads)

    def test_stale_pin_file_fails_check(self):
        target = pins.write_pins(self.root, self.roads)
        document = json.loads(target.read_text())
        document['Files'][0]['Pages'][0] = '0' * 64
        target.write_text(pins.encode(document))
        self.assertFalse(pins.check_pins(self.root, self.roads))

    def test_missing_mission_source_is_refused(self):
        (self.mission / pins.MISSION_SOURCES[1]).unlink()
        with self.assertRaises(ValueError):
            pins.build_pins(self.root, self.roads)


if __name__ == '__main__':
    unittest.main()
