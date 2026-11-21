"""Authored composition invariants on synthetic XML; no DayZ behaviour claims."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools.package import HCWildlife_habitats as habitats, optional_overlays as overlays

ROOT = Path(__file__).resolve().parents[2]


class AnimalComposition(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads((ROOT / 'mission/hollow-country/ecology/composition-variety.json').read_bytes())
        self.events = ET.Element('events')
        for name, choices in self.policy['NativeEvents'].items():
            event = ET.SubElement(self.events, 'event', name=name)
            for tag, text in [('nominal', '8'), ('min', '0'), ('max', '8'), ('limit', 'child')]:
                ET.SubElement(event, tag).text = text
            children = ET.SubElement(event, 'children')
            # Synthetic input differs in required members but retains the authored ceiling.
            for classname, (_, maximum) in choices.items():
                ET.SubElement(children, 'child', type=classname, min='0', max=str(maximum), lootmin='0', lootmax='0')
        self.environment = ET.Element('env')
        territories = ET.SubElement(self.environment, 'territories')
        for name, choice in self.policy['NativeAmbient'].items():
            territories.append(self.territory(name, choice))

    @staticmethod
    def territory(name, choice):
        territory = ET.Element('territory', name=name, behavior='SyntheticNativeBrain')
        for index, (sex, chance) in enumerate(choice['Agents'].items()):
            agent = ET.SubElement(territory, 'agent', type=sex, chance=str(chance))
            # Authored hen first class is the male branch; the remaining are female.
            classes = list(choice['Spawns'].items())
            for classname, weight in (classes[:1] if index == 0 else classes[1:]):
                ET.SubElement(agent, 'spawn', configName=classname, chance=str(weight))
        ET.SubElement(territory, 'item', name='globalCountMax', val='8')
        return territory

    def test_native_budget_class_loot_and_receipt_rollback(self):
        originals = {'db/events.xml': ET.tostring(self.events),
                     'cfgenvironment.xml': ET.tostring(self.environment)}
        files = habitats.composition_build(self.policy, originals['cfgenvironment.xml'], originals['db/events.xml'])
        changed = ET.fromstring(files['db/events.xml'])
        for before, after in zip(self.events, changed):
            self.assertEqual({n.tag: n.text for n in before if n.tag != 'children'},
                             {n.tag: n.text for n in after if n.tag != 'children'})
            old, new = before.findall('children/child'), after.findall('children/child')
            self.assertEqual({n.get('type') for n in old}, {n.get('type') for n in new})
            self.assertEqual(sum(int(n.get('max')) for n in old), sum(int(n.get('max')) for n in new))
            self.assertEqual([(n.get('lootmin'), n.get('lootmax')) for n in old],
                             [(n.get('lootmin'), n.get('lootmax')) for n in new])
        with tempfile.TemporaryDirectory(prefix='hc-composition-') as directory:
            mission = Path(directory)
            for name, data in originals.items():
                path = mission / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            candidate = {'files': files, 'before': originals, 'sources': {}, 'mission': str(mission)}
            overlays.install(candidate, mission, overlays.BUNDLE_MANAGED)
            overlays.rollback(mission, managed_name=overlays.BUNDLE_MANAGED)
            self.assertEqual(originals, {p.relative_to(mission).as_posix(): p.read_bytes()
                                         for p in mission.rglob('*') if p.is_file()})

    def test_default_on_explicit_off_and_invalid_switch(self):
        self.assertTrue(habitats.composition_enabled({}))
        self.assertTrue(habitats.composition_enabled({'Ecology': {}}))
        self.assertFalse(habitats.composition_enabled({'Ecology': {'EnableCompositionVariety': False}}))
        with self.assertRaises(ValueError):
            habitats.composition_enabled({'Ecology': {'EnableCompositionVariety': 0}})

    def test_bundle_switch_is_independent_of_habitat_opt_out(self):
        with tempfile.TemporaryDirectory(prefix='hc-composition-bundle-') as directory:
            root = Path(directory)
            mission, bundle = root / 'mission', root / 'bundle'
            ecology = bundle / 'mission-overlay/hollow-country/ecology'
            optional = ecology.parent / 'optional'
            ecology.mkdir(parents=True)
            optional.mkdir()
            (mission / 'db').mkdir(parents=True)
            (bundle / 'mission-patches.json').write_text(json.dumps({'core': [], 'gameplay': []}))
            (ecology / 'habitat-overrides.json').write_text(json.dumps({'Enabled': False}))
            (ecology / 'composition-variety.json').write_text(json.dumps(self.policy))
            (mission / 'db/events.xml').write_bytes(ET.tostring(self.events))
            (mission / 'cfgenvironment.xml').write_bytes(ET.tostring(self.environment))
            (mission / 'cfgeconomycore.xml').write_bytes(b'<economycore/>')
            preference = optional / 'overlay-policy.json'
            preference.write_text('{}')
            default = overlays.bundle_candidate(bundle, mission)
            preference.write_text(json.dumps({'Ecology': {'EnableCompositionVariety': True}}))
            explicit = overlays.bundle_candidate(bundle, mission)
            for name in ('db/events.xml', 'cfgenvironment.xml'):
                self.assertEqual(default['files'][name], explicit['files'][name])
            preference.write_text(json.dumps({'Ecology': {'EnableCompositionVariety': False}}))
            disabled = overlays.bundle_candidate(bundle, mission)
            self.assertNotIn('db/events.xml', disabled['files'])
            self.assertNotIn('cfgenvironment.xml', disabled['files'])

    def test_changed_inventory_and_population_ceiling_refused(self):
        policy = copy.deepcopy(self.policy)
        selections = next(iter(policy['NativeEvents'].values()))
        next(iter(selections.values()))[1] += 1
        with self.assertRaisesRegex(ValueError, 'ceiling'):
            habitats.composition_build(policy, ET.tostring(self.environment), ET.tostring(self.events))
        next(iter(self.events)).find('children/child').set('type', 'SyntheticUnknownClass')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            habitats.composition_build(self.policy, ET.tostring(self.environment), ET.tostring(self.events))

    def test_dependency_palettes_keep_all_supplied_classes_and_chance_sums(self):
        for choice in self.policy['DependencyAmbient'].values():
            territory = self.territory(choice['Territory'], choice)
            before = copy.deepcopy(territory)
            habitats.composition_ambient(territory, choice)
            self.assertEqual({n.get('configName') for n in before.findall('agent/spawn')},
                             {n.get('configName') for n in territory.findall('agent/spawn')})
            self.assertEqual(sum(int(n.get('chance')) for n in before.findall('agent')),
                             sum(int(n.get('chance')) for n in territory.findall('agent')))
        caps = overlays.ambient_caps(json.loads(overlays.POLICY.read_bytes())['ambient'])
        self.assertLessEqual(sum(caps.values()), 48)
        self.assertLessEqual(caps['snake'], 2)
        self.assertTrue(all(value <= 8 for value in caps.values()))


if __name__ == '__main__':
    unittest.main()
