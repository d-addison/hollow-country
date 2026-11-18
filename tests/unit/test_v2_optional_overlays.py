"""One packaging smoke; all dependency/mission bytes below are synthetic, not DayZ evidence."""
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET


class OptionalOverlaysSmoke(unittest.TestCase):
    def test_w5_stack_types_are_local_reversible_and_not_exported(self):
        from tools.package import optional_overlays as overlays
        from tools.setup import friend_bundle, workshop_sync

        with tempfile.TemporaryDirectory(prefix='hc-synthetic-w5-stack-') as directory:
            root = Path(directory)
            mission, workshop = root / 'mission', root / 'workshop'
            mission.mkdir()
            workshop.mkdir()
            for name, data in {'cfgeconomycore.xml': '<economycore/>',
                               'cfgeventspawns.xml': '<eventposdef/>',
                               'db/types.xml': '<types/>'}.items():
                path = mission / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(data)
            before = {p.relative_to(mission).as_posix(): p.read_bytes()
                      for p in mission.rglob('*') if p.is_file()}
            rag = workshop / '3105330157'
            (rag / 'types').mkdir(parents=True)
            (rag / 'types/rag_immersive_vehicles.xml').write_text(
                '<types><type name="SyntheticRaGTool"><nominal>7</nominal></type></types>')
            core, navigation = workshop / '3556131153', workshop / '2792984722'
            core.mkdir()
            navigation.mkdir()
            loaded = [rag, core, navigation]
            candidate = overlays.plan(workshop, mission, loaded)
            self.assertIn(overlays.MANAGED + '/types.xml', candidate['files'])
            overlays.install(candidate, mission)
            types = ET.fromstring((mission / overlays.MANAGED / 'types.xml').read_bytes())
            self.assertEqual(types.find("type[@name='SyntheticRaGTool']/nominal").text, '7')
            gps = types.find("type[@name='ExpansionGPS']")
            self.assertEqual(gps.findtext('nominal'), '4')
            self.assertEqual({n.get('name') for n in gps.findall('usage')}, {'Military', 'Police'})
            rows, _ = friend_bundle.mission_files(mission)
            export = overlays.friend_bundle_plan(mission, [('mpmissions/mission/' + n, p) for n, p in rows])
            self.assertFalse(any(b'SyntheticRaGTool' in (p if isinstance(p, bytes) else p.read_bytes())
                                 for _, p in export))
            overlays.rollback(mission)
            self.assertEqual({p.relative_to(mission).as_posix(): p.read_bytes()
                              for p in mission.rglob('*') if p.is_file()}, before)
            (mission / 'db/types.xml').write_text('<types><type name="ExpansionGPS"/></types>')
            with self.assertRaisesRegex(ValueError, 'reconciliation'):
                overlays.plan(workshop, mission, loaded)
            items = workshop_sync.load_manifest()['mods']
            folders = [m['folder'] for m in sorted(items, key=lambda m: m['rank'])]
            self.assertEqual(folders[:6], ['@CF', '@COT', '@DabsFramework', '@Expansion-Core',
                                          '@Expansion-AI', '@Expansion-Navigation'])
            self.assertLess(folders.index('@RaG_Core'), folders.index('@RaG_Immersive_Vehicles'))
            self.assertLess(folders.index('@RaG_Immersive_Vehicles'), folders.index('@AmbientAnimals'))

    def test_absent_loaded_install_export_and_rollback(self):
        from tools.package import optional_overlays as overlays
        from tools.setup import friend_bundle

        with tempfile.TemporaryDirectory(prefix='hc-synthetic-overlays-') as directory:
            root = Path(directory)
            mission, workshop = root / 'mission', root / 'workshop'
            mission.mkdir()
            workshop.mkdir()

            def put(base, name, content):
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)

            def snapshot(base):
                return {p.relative_to(base).as_posix(): p.read_bytes()
                        for p in base.rglob('*') if p.is_file()}

            put(mission, 'cfgeconomycore.xml', '<economycore><defaults/></economycore>')
            put(mission, 'cfgeventspawns.xml', '<eventposdef/>')
            put(mission, 'db/events.xml', '<events/>')
            put(mission, 'db/types.xml', '<types/>')
            put(mission, 'cfgspawnabletypes.xml', '<spawnabletypes/>')
            put(mission, 'cfgenvironment.xml', '<env><territories>'
                '<territory type="Ambient" name="AmbientHen" behavior="SyntheticNative">'
                '<file usable="hen_territories"/><item name="globalCountMax" val="12"/>'
                '</territory></territories></env>')
            put(mission, 'env/hen_territories.xml', '<territory-type><territory>'
                '<zone name="Zone_hen" x="10" z="10" r="20" smin="0" smax="0" dmin="0" dmax="2"/>'
                '</territory></territory-type>')
            put(mission, 'mapgrouppos.xml', '<map><group name="Land_Farm_Synthetic" pos="10 0 10"/></map>')
            before = snapshot(mission)
            absent = overlays.plan(workshop, mission, [])
            self.assertEqual(absent['files'], {})
            self.assertEqual(len(absent['diagnostics']), 4)
            overlays.install(absent, mission)
            self.assertEqual(snapshot(mission), before)

            bike = workshop / overlays.BICYCLE_ID
            put(bike, 'events.xml', '<events><event name="SyntheticBikeEvent"><nominal>20</nominal>'
                '<min>0</min><max>100</max><children><child type="SyntheticBike" min="0" max="20"/>'
                '</children></event></events>')
            put(bike, 'cfgeventspawns_Chernarus.xml', '<events><event name="SyntheticBikeEvent">'
                '<pos x="11" z="11" a="0"/></event></events>')
            put(bike, 'types.xml', '<types><type name="SyntheticBike"><nominal>0</nominal></type></types>')
            put(bike, 'spawnabletypes.xml', '<spawnabletypes><type name="SyntheticBike"/></spawnabletypes>')
            put(mission, 'mapgrouppos.xml', '<map><group name="Land_Shed_Synthetic" pos="11 0 11"/>'
                '<group name="Land_Farm_Synthetic" pos="10 0 10"/></map>')
            animals = workshop / overlays.ANIMALS_ID
            for species in overlays.AMBIENT_SPECIES:
                put(animals, species + '_territories/Ambient_' + species + '_ReadMe.txt',
                    '<file path="env/' + species + '_territories.xml"/>'
                    '<territory type="Ambient" name="Synthetic_' + species + '" behavior="SyntheticBeh">'
                    '<file usable="wrong_upstream_reference"/>'
                    '<item name="globalCountMax" val="50"/>'
                    '<agent><spawn configName="Synthetic_' + species + '"/></agent></territory>'
                    '<event name="Synthetic_' + species + '"><nominal>3</nominal><min>0</min><max>50</max></event>'
                    '<type name="Synthetic_' + species + '"><nominal>0</nominal></type>')
                put(animals, species + '_territories/chernarus/' + species + '_territories.xml',
                    '<territory-type><territory><zone name="Graze" x="20" z="20" r="20" '
                    'smin="0" smax="0" dmin="0" dmax="0"/></territory></territory-type>')
            # Snake has a separate upstream instruction layout.
            put(animals, 'snake_territories/Snake_TypesEvents.txt',
                '<event name="SyntheticSnake"><nominal>1</nominal><min>0</min><max>2</max></event>'
                '<type name="SyntheticSnake"><nominal>0</nominal></type>'
                '<file path="env/snake_territories.xml"/>'
                '<territory type="Herd" name="SyntheticSnake" behavior="SyntheticSnakeBeh">'
                '<file usable="snake_territories"/></territory><event name="SyntheticSnake"/>')
            put(animals, 'snake_territories/Chernarus/snake_territories.xml',
                '<territory-type><territory/></territory-type>')
            put(bike, 'Addons/Synthetic.pbo', 'SYNTHETIC-DO-NOT-BUNDLE')
            installed_source = snapshot(workshop)
            self.assertEqual(overlays.plan(workshop, mission, [])['files'], {})
            before = snapshot(mission)
            candidate = overlays.plan(workshop, mission, [bike, animals])
            self.assertEqual(snapshot(mission), before, 'plan must be read only')
            overlays.install(candidate, mission)
            events = ET.fromstring((mission / overlays.MANAGED / 'events.xml').read_bytes())
            self.assertEqual(events.find("event[@name='SyntheticBikeEvent']/nominal").text, '40')
            environment = ET.fromstring((mission / 'cfgenvironment.xml').read_bytes())
            self.assertTrue(all(int(i.get('val')) <= 8 for i in environment.findall(
                "./territories/territory[@name='Synthetic_otter']/item[@name='globalCountMax']")))
            rows, _ = friend_bundle.mission_files(mission)
            prefix = 'mpmissions/mission/'
            bundled = overlays.friend_bundle_plan(mission, [(prefix + rel, source) for rel, source in rows])
            export = {rel[len(prefix):]: source if isinstance(source, bytes) else source.read_bytes()
                      for rel, source in bundled if rel.startswith(prefix)}
            self.assertEqual(export, before, 'bundle must restore mission and omit every generated dependency byte')
            self.assertFalse(any(b'SYNTHETIC-DO-NOT-BUNDLE' in (source if isinstance(source, bytes) else source.read_bytes())
                                 for _, source in bundled))
            self.assertEqual(snapshot(workshop), installed_source)
            # A partial install and operator edits must remain recoverable without overwriting drift.
            core = mission / 'cfgeconomycore.xml'
            expected = core.read_bytes()
            core.write_bytes(expected + b'<!--operator edit-->')
            with self.assertRaisesRegex(ValueError, 'drift'):
                overlays.rollback(mission)
            core.write_bytes(expected)
            overlays.rollback(mission)
            self.assertEqual(snapshot(mission), before)


if __name__ == '__main__':
    unittest.main()
