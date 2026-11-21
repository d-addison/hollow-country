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
        report = travel.roster(source)
        self.assertEqual({e.get('name') for e in events}, set(report['families']))
        for event in events:
            self.assertEqual({c.get('type') for c in event.findall('children/child')},
                             set(report['families'][event.get('name')]['variants']))
            low, nominal, high = (int(event.findtext(n)) for n in ('min', 'nominal', 'max'))
            self.assertLessEqual(low, nominal)
            self.assertLessEqual(nominal, high)
        with tempfile.TemporaryDirectory(prefix='hc-synthetic-travel-') as tmp:
            mission = Path(tmp) / 'mission'
            mission.mkdir()
            (mission / 'cfgeventspawns.xml').write_bytes(b'<eventposdef/>')
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
            installed = {p.relative_to(mission): p.read_bytes()
                         for p in mission.rglob('*') if p.is_file()}
            self.assertTrue(travel.install(source, mission))
            self.assertEqual({p.relative_to(mission): p.read_bytes()
                              for p in mission.rglob('*') if p.is_file()}, installed)
            changed = mission / travel.MANAGED / 'ce/events.xml'
            original = changed.read_bytes()
            changed.write_bytes(b'<events/>')
            with self.assertRaisesRegex(ValueError, 'drift'):
                travel.rollback(mission)
            changed.write_bytes(original)
            travel.rollback(mission)
            self.assertEqual((mission / 'cfgeconomycore.xml').read_bytes(), core)
            self.assertEqual((mission / 'cfgeventspawns.xml').read_bytes(), b'<eventposdef/>')
            self.assertFalse((mission / travel.MANAGED).exists())
