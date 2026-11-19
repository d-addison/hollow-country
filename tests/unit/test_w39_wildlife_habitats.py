"""#149 installer behavior on explicit synthetic native CE XML, never engine proof."""
import hashlib
import importlib.util
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'tools/package/HCWildlife_habitats.py'

class WildlifeHabitats(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.exists(), 'habitat event installer missing')
        spec = importlib.util.spec_from_file_location('wildlife_habitats', SOURCE)
        self.tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tool)
        # Synthetic baseline retains the real sheep event fields; unrelated rows explicit.
        self.delta = (ROOT / 'mission/hollow-country/ecology/events.append.xml').read_bytes()
        delta = ET.fromstring(self.delta)
        sheep = delta.find('event')
        sheep.find('children').remove(sheep.find("children/child[@type='Animal_OvisGmelini']"))
        ET.SubElement(delta, 'event', {'name': 'SyntheticUnrelated'})
        self.events = ET.tostring(delta)
        self.env = b'<env><territories><file path="env/hare_territories.xml"/><file path="env/hare_territories.xml"/><file path="env/synthetic.xml"/></territories></env>'
        self.manifest = dict(Enabled=True, Sources=[dict(Path=p, Sha256=hashlib.sha256(data).hexdigest()) for p, data in [('cfgenvironment.xml', self.env), ('db/events.xml', self.events)]])
        self.classes = {'Animal_OvisAries', 'Animal_OvisAriesF', 'Animal_OvisGmelini'}

    def build(self):
        return self.tool.build(self.manifest, self.delta, self.env, self.events, self.classes)

    def test_enabled_default_replaces_one_existing_event_and_deduplicates_hare(self):
        result = self.build()
        events = ET.fromstring(result['db/events.xml'])
        self.assertEqual(1, len(events.findall("event[@name='AnimalSheep']")))
        self.assertEqual(1, len(events.findall("event[@name='SyntheticUnrelated']")))
        self.assertEqual(1, len(events.findall("event/children/child[@type='Animal_OvisGmelini']")))
        self.assertEqual('5', events.findtext("event[@name='AnimalSheep']/nominal"))
        env = ET.fromstring(result['cfgenvironment.xml'])
        self.assertEqual(1, len(env.findall("territories/file[@path='env/hare_territories.xml']")))
        self.assertEqual(1, len(env.findall("territories/file[@path='env/synthetic.xml']")))

    def test_operator_off_is_a_noop_and_changed_or_missing_native_data_refuses(self):
        self.manifest['Enabled'] = False
        self.assertEqual({}, self.build())
        self.manifest['Enabled'] = True
        self.events += b' '
        with self.assertRaisesRegex(ValueError, 'source hash'):
            self.build()
        self.events = self.events[:-1]
        self.classes.remove('Animal_OvisGmelini')
        with self.assertRaisesRegex(ValueError, 'class unavailable'):
            self.build()

    def test_duplicate_events_and_population_budget_changes_are_refused(self):
        self.delta = self.delta.replace(b'<nominal>5</nominal>', b'<nominal>6</nominal>')
        with self.assertRaisesRegex(ValueError, 'population'):
            self.build()

if __name__ == '__main__':
    unittest.main()
