"""#161: explicit synthetic CE files and fake installed packs; no DayZ evidence."""
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools.package import economy, loot_boost, optional_overlays as overlays, travel
from tools.package import snafu_optional as snafu, tactical_flava_optional as tactical

try:
    from . import test_snafu_optional as sf, test_tactical_flava_optional as tf
except ImportError:
    import test_snafu_optional as sf
    import test_tactical_flava_optional as tf


def put(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)


def files_of(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def layer(mission, files, managed):
    """Use real receipted installer with entirely synthetic candidate bytes."""
    overlays.install({'mission': str(mission), 'files': files, 'sources': {},
                      'before': {n: (mission / n).read_bytes() if (mission / n).exists() else None
                                 for n in files}}, mission, managed_name=managed)


def bundle(mission, source, base=True):
    """Compose synthetic loot layers with authored travel data and the loot boost."""
    core = (mission / 'cfgeconomycore.xml').read_bytes()
    registration = b'<ce folder="hollow-country/ce"><file name="types.xml" type="types"/></ce>'
    base_files = {'cfgeconomycore.xml': core.replace(b'</economycore>', registration + b'</economycore>')}
    if base:
        base_files['hollow-country/ce/types.xml'] = b'<types><type name="SyntheticBase"/></types>'
    else:
        base_files['cfgeconomycore.xml'] = core
    layer(mission, base_files, overlays.BUNDLE_MANAGED)
    # Use the current authored travel overlay so composition follows its manifest,
    # registrations and position inputs. Keep the loot row synthetic and disjoint.
    for name, data in travel.validate().items():
        put(source, name, data)
    put(source, travel.EXPANSION_ROSTER,
        (travel.SOURCE / travel.EXPANSION_ROSTER).read_bytes())
    put(source, 'ce/types.xml', '<types>' + tf.stock_entry(
        'SyntheticTravel', 2, 1, 14400, 0, ['Town'], []) + '</types>')
    travel.install(source, mission)
    core = (mission / 'cfgeconomycore.xml').read_bytes()
    optional = b'''<ce folder="hollow-country-optional-packs"><file name="types.xml" type="types"/>
<file name="events.xml" type="events"/><file name="spawnabletypes.xml" type="spawnabletypes"/></ce>'''
    layer(mission, {
        'cfgeconomycore.xml': core.replace(b'</economycore>', optional + b'</economycore>'),
        overlays.MANAGED + '/types.xml': b'<types><type name="SyntheticLiving"/></types>',
        overlays.MANAGED + '/events.xml': b'<events/>',
        overlays.MANAGED + '/spawnabletypes.xml': b'<spawnabletypes/>'}, overlays.MANAGED)
    loot_boost.install(mission, multiplier=2.0)


try:
    from tests.unit import hash_cache_isolation
except ImportError:  # run as a script from tests/unit
    import hash_cache_isolation


def setUpModule():
    # #194: the whole-PBO hashing path reads/writes the hash cache; never the user's.
    hash_cache_isolation.enter()


def tearDownModule():
    hash_cache_isolation.leave()


class ManagedCEComposition(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        sf.patch_roster(self, self.tmp.name)
        sf.build_install(self.root / 'snafu-mod')
        tf.build_install(self.root / 'tactical-mod')
        self.snafu_allow = sf.allowlist(*sf.GOOD)
        self.tactical_allow = tf.allowlist(*tf.good())
        self.packs = (
            (snafu, self.snafu_allow, snafu.verify_install(self.root / 'snafu-mod', self.snafu_allow)),
            (tactical, self.tactical_allow, tactical.verify_install(
                self.root / 'tactical-mod', self.tactical_allow, vanilla=tf.VANILLA)))

    def mission(self, name='mission', base=True):
        mission = self.root / name
        mission.mkdir()
        tf.mission(mission)
        put(mission, 'db/globals.xml', '<variables><var name="RespawnTypes" type="0" value="5"/></variables>')
        put(mission, 'cfgeventspawns.xml', '<eventposdef/>')
        before = files_of(mission)
        bundle(mission, self.root / (name + '-travel'), base=base)
        return mission, before

    def test_each_pack_and_both_orders_restore_exact_bundle_then_original_bytes(self):
        for index, packs in enumerate(((self.packs[0],), (self.packs[1],), self.packs, self.packs[::-1])):
            with self.subTest(order=[p[0].MANAGED for p in packs]):
                mission, before = self.mission(str(index))
                bundled = files_of(mission)
                self.assertEqual(len(ET.fromstring(bundled['cfgeconomycore.xml']).findall('ce')), 3)
                checkpoints = []
                for number, (pack, allow, report) in enumerate(packs):
                    checkpoints.append(files_of(mission))
                    stage = self.root / f'delta-{index}-{number}'
                    pack.write_delta(stage, pack.generate(mission, allow, report))
                    pack.install(stage, mission)
                self.assertEqual(len(ET.parse(mission / 'cfgeconomycore.xml').findall('ce')), 3 + len(packs))
                with self.assertRaises(ValueError):
                    overlays.bundle_rollback(mission)
                for (pack, _, _), checkpoint in zip(reversed(packs), reversed(checkpoints)):
                    pack.rollback(mission)
                    self.assertEqual(files_of(mission), checkpoint)
                self.assertEqual(files_of(mission), bundled)
                overlays.bundle_rollback(mission)
                self.assertEqual(files_of(mission), before)

    def test_unknown_folders_are_named_at_generate_and_install_without_writes(self):
        for index, (pack, allow, report) in enumerate(self.packs):
            with self.subTest(pack=pack.MANAGED):
                mission, _ = self.mission(str(index))
                delta = pack.generate(mission, allow, report)
                core = (mission / 'cfgeconomycore.xml').read_bytes()
                put(mission, 'cfgeconomycore.xml', core.replace(b'</economycore>', b'''
<ce folder="third-party/ce"><file name="types.xml" type="types"/></ce>
<ce folder="hollow-country-unowned/ce"><file name="types.xml" type="types"/></ce></economycore>'''))
                before = files_of(mission)
                with self.assertRaisesRegex(ValueError, 'hollow-country-unowned/ce.*third-party/ce'):
                    pack.generate(mission, allow, report)
                # Keep a self-consistent staged source pin so install reaches its own guard.
                manifest = json.loads(delta['delta-manifest.json'])
                manifest['sources']['cfgeconomycore.xml'] = economy.sha(before['cfgeconomycore.xml'])
                delta['delta-manifest.json'] = economy.encode(manifest)
                stage = self.root / f'unknown-{index}'
                pack.write_delta(stage, delta)
                with self.assertRaisesRegex(ValueError, 'hollow-country-unowned/ce.*third-party/ce'):
                    pack.install(stage, mission)
                self.assertEqual(files_of(mission), before)

    def test_stock_and_every_registered_types_file_retain_class_ownership(self):
        paths = ('db/types.xml', 'hollow-country/ce/types.xml',
                 'hollow-country-travel/ce/types.xml', 'hollow-country-optional-packs/types.xml')
        for index, (pack, allow, report) in enumerate(self.packs):
            for number, relative in enumerate(paths):
                for alias in (False, True):
                    with self.subTest(pack=pack.MANAGED, path=relative, alias=alias):
                        mission, _ = self.mission(f'{index}-{number}-{alias}')
                        delta = pack.generate(mission, allow, report)
                        name = allow['entries'][0]['class']
                        collision = name.lower() if alias else name
                        path = mission / relative
                        put(mission, relative, path.read_bytes().replace(
                            b'</types>', f'<type name="{collision}"/></types>'.encode()))
                        before = files_of(mission)
                        with self.assertRaisesRegex(ValueError, 'already defined.*' + name):
                            pack.generate(mission, allow, report)
                        manifest = json.loads(delta['delta-manifest.json'])
                        manifest['sources'] = {n: economy.sha(d) for n, d in economy.snapshot(mission).items()}
                        delta['delta-manifest.json'] = economy.encode(manifest)
                        stage = self.root / f'collision-{index}-{number}-{alias}'
                        pack.write_delta(stage, delta)
                        with self.assertRaisesRegex(ValueError, 'already defined.*' + name):
                            pack.install(stage, mission)
                        self.assertEqual(files_of(mission), before)

    def test_economy_guard_allows_managed_layers_and_refuses_unknown_folders(self):
        mission, before = self.mission(base=False)
        profile = {'schema': 1, 'name': 'synthetic', 'add_usage': {'SynthWoodRifle': ['Village']}, 'diagnostics': []}
        bundled = files_of(mission)
        stage = self.root / 'economy-delta'
        economy.write_delta(stage, economy.generate(mission, profile, include_datamined=False))
        economy.install(stage, mission)
        economy.rollback(mission)
        self.assertEqual(files_of(mission), bundled)
        core = bundled['cfgeconomycore.xml']
        put(mission, 'cfgeconomycore.xml', core.replace(b'</economycore>', b'<ce folder="third-party/ce"/></economycore>'))
        with self.assertRaisesRegex(ValueError, 'third-party/ce'):
            economy.generate(mission, profile, include_datamined=False)
        put(mission, 'cfgeconomycore.xml', core)
        overlays.bundle_rollback(mission)
        self.assertEqual(files_of(mission), before)


class StaleRegistration(unittest.TestCase):
    """Review P2 on #161: a pack folder deleted by hand leaves its <ce> row; install must not add a second."""

    def core(self, folder, files):
        rows = ''.join(f'<file name="{n}" type="{t}"/>' for n, t in files)
        return f'<?xml version="1.0"?>\n<economycore>\n<ce folder="{folder}/ce">{rows}</ce>\n</economycore>\n'.encode()

    def test_each_optional_pack_refuses_a_core_that_already_registers_its_folder(self):
        cases = ((snafu, [('types.xml', 'types')]),
                 (tactical, [('types.xml', 'types'), ('cfgspawnabletypes.xml', 'spawnabletypes')]))
        for module, files in cases:
            with self.subTest(pack=module.MANAGED):
                core = self.core(module.MANAGED, files)
                with self.assertRaisesRegex(ValueError, 'CE folder already registered: ' + module.MANAGED + '/ce'):
                    module._patched_core(core, core, {})
