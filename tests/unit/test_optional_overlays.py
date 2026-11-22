"""Synthetic install coverage; these checks do not establish DayZ behavior."""
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools.package import optional_overlays as overlays


class OptionalOverlaysTests(unittest.TestCase):
    def test_ambient_install_excludes_snake_and_preserves_healthy_species(self):
        with tempfile.TemporaryDirectory(prefix='hc-synthetic-ambient-') as temporary:
            root = Path(temporary)
            mission, workshop = root / 'mission', root / 'workshop'
            animals = workshop / overlays.ANIMALS_ID

            def put(base, relative, data):
                path = base / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(data, encoding='utf-8')

            def snapshot(base):
                return {p.relative_to(base).as_posix(): p.read_bytes()
                        for p in base.rglob('*') if p.is_file()}

            for relative, data in {
                'cfgeconomycore.xml': '<economycore/>',
                'cfgeventspawns.xml': '<eventposdef/>',
                'cfgenvironment.xml': '<env><territories/></env>',
                'cfglimitsdefinition.xml': '<lists><categories><category name="lootdispatch"/></categories></lists>',
                'db/events.xml': '<events/>',
                'db/types.xml': '<types/>',
            }.items():
                put(mission, relative, data)
            for species in overlays.AMBIENT_SPECIES:
                folder = species + '_territories'
                name = 'Synthetic_' + species
                put(animals, folder + '/' + species + '_README.txt',
                    f'<territory name="{name}"><file usable="upstream"/>'
                    '<item name="globalCountMax" val="8"/></territory>\n'
                    f'<event name="{name}"><nominal>8</nominal><min>0</min><max>8</max>'
                    f'<children><child type="{name}" min="0" max="8"/></children></event>\n'
                    f'<event name="{name}"><pos x="10" z="10" a="0"/></event>\n'
                    f'<type name="{name}"><nominal>0</nominal></type>')
                put(animals, folder + '/chernarus/' + folder + '.xml', '<territory-type/>')
            # If Snake is consulted at all, malformed instructions must fail parsing.
            put(animals, 'snake_territories/Snake_TypesEvents.txt', '<!DOCTYPE forbidden>')
            policy = json.loads(overlays.POLICY.read_text())
            policy['Ecology']['EnableCompositionVariety'] = False
            policy_path = root / 'policy.json'
            policy_path.write_text(json.dumps(policy), encoding='utf-8')
            original_mission, original_pack = snapshot(mission), snapshot(animals)
            candidate = overlays.plan(workshop, mission, [animals], policy_path)
            self.assertEqual(snapshot(mission), original_mission)
            self.assertEqual(snapshot(animals), original_pack)
            self.assertFalse(any('snake' in Path(path).name.casefold() for path in candidate['sources']))
            self.assertFalse(any('snake' in name.casefold() or b'snake' in data.lower()
                                 for name, data in candidate['files'].items()))
            expected = {'Synthetic_' + species for species in overlays.AMBIENT_SPECIES}
            for filename, tag in (('types.xml', 'type'), ('events.xml', 'event')):
                generated = ET.fromstring(candidate['files'][overlays.MANAGED + '/' + filename])
                self.assertEqual({node.get('name') for node in generated.findall(tag)}, expected)
            environment = ET.fromstring(candidate['files']['cfgenvironment.xml'])
            self.assertEqual({node.get('name') for node in environment.findall('territories/territory')}, expected)
            spawns = ET.fromstring(candidate['files']['cfgeventspawns.xml'])
            self.assertEqual({node.get('name') for node in spawns.findall('event')}, expected)
            for species in overlays.AMBIENT_SPECIES:
                self.assertIn(overlays.MANAGED + '/' + species + '_territories.xml', candidate['files'])
            caps = overlays.ambient_caps(policy['ambient'])
            self.assertEqual(caps['snake'], 0)
            self.assertLessEqual(sum(caps.values()), policy['ambient']['total_cap'])
            overlays.install(candidate, mission)
            self.assertEqual(snapshot(animals), original_pack)
            overlays.rollback(mission)
            self.assertEqual(snapshot(mission), original_mission)

    def test_legacy_snake_receipt_can_still_roll_back(self):
        with tempfile.TemporaryDirectory(prefix='hc-synthetic-snake-rollback-') as temporary:
            mission = Path(temporary)
            relative = overlays.MANAGED + '/snake_territories.xml'
            candidate = {'files': {relative: b'<territory-type/>'},
                         'before': {relative: None}, 'sources': {}, 'mission': str(mission)}
            overlays.install(candidate, mission)
            self.assertTrue((mission / relative).exists())
            overlays.rollback(mission)
            self.assertFalse((mission / relative).exists())

    def test_comms_post_uses_antenna_in_former_radar_slot(self):
        compositions = json.loads((overlays.ROOT / 'config/map-overlays/compositions.json').read_text())
        for name, composition in compositions['compositions'].items():
            with self.subTest(composition=name):
                self.assertNotIn('Land_Mil_Radar_Mobile1', {piece['class'] for piece in composition['pieces']})
        pieces = compositions['compositions']['comms-post']['pieces']
        self.assertNotIn('Land_Mil_Radar_Mobile1', {piece['class'] for piece in pieces})
        replacement = next(piece for piece in pieces if (piece['dx'], piece['dz']) == (-6, -3))
        self.assertEqual(replacement['class'], 'StaticObj_Misc_Antenna')
        self.assertEqual(replacement['loot'], 'none')


if __name__ == '__main__':
    unittest.main()
