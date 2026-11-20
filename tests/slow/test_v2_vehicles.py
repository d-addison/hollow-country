"""One packaging smoke, with an explicit synthetic mission; no DayZ behaviour evidence."""
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from tools.package import travel


class TravelSmoke(unittest.TestCase):
    def test_travel_ce_ships_once_and_rolls_back_without_touching_stock(self):
        source = Path(__file__).resolve().parents[2] / 'mission/hollow-country'
        events = ET.parse(source / 'ce/events.xml').getroot()
        cars = [e for e in events if e.get('name') not in ('VehicleBoat', 'VehicleMotorbike')]
        self.assertEqual(sum(int(e.findtext('nominal')) for e in cars), 39)
        for car in cars:
            self.assertLessEqual(int(car.findtext('nominal')), 9)
        self.assertEqual(events.find("event[@name='VehicleBoat']/nominal").text, '6')
        self.assertEqual(len(events.find("event[@name='VehicleMotorbike']/children")), 7)
        with tempfile.TemporaryDirectory(prefix='hc-synthetic-travel-') as tmp:
            mission = Path(tmp) / 'mission'
            mission.mkdir()
            # SYNTHETIC: an existing, unrelated CE declaration must survive.
            core = b'<economycore><ce folder="synthetic/ce"><file name="types.xml" type="types"/></ce></economycore>'
            (mission / 'cfgeconomycore.xml').write_bytes(core)
            (mission / 'synthetic/ce').mkdir(parents=True)
            (mission / 'synthetic/ce/types.xml').write_bytes(b'<types/>')
            self.assertFalse(travel.install(source, mission, enabled=False))
            self.assertEqual((mission / 'cfgeconomycore.xml').read_bytes(), core)
            travel.install(source, mission)
            for name in travel.CE_FILES:
                self.assertEqual((mission / travel.MANAGED / name).read_bytes(), (source / name).read_bytes())
            with self.assertRaisesRegex(ValueError, 'already installed'):
                travel.install(source, mission)
            changed = mission / travel.MANAGED / 'ce/events.xml'
            original = changed.read_bytes()
            changed.write_bytes(b'<events/>')
            with self.assertRaisesRegex(ValueError, 'drift'):
                travel.rollback(mission)
            changed.write_bytes(original)
            travel.rollback(mission)
            self.assertEqual((mission / 'cfgeconomycore.xml').read_bytes(), core)
            self.assertFalse((mission / travel.MANAGED).exists())
