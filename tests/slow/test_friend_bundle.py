"""Friend server bundle: synthetic mission, profile and mod trees only.

Issue #175 / Wave 7 bundle catalogue TDD RED (before implementation):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_friend_bundle.FriendBundleTests.test_profile_default_history_records_current_and_earlier_git_bytes -v
KeyError: 'profile_defaults'
Ran 1 test in 0.049s; FAILED (errors=1)
The paired installer/bundle GREEN command and result are in test_friend_install.py.

Additional TDD RED for optional invalid results, before the omission fix (verbatim failure line):
AssertionError: 2 != 0 : refused: sampler result keys must be exactly: frame, groups, kind, native_run_id, pins, schema
Ran 1 test in 0.132s
FAILED (failures=1)
GREEN command: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.slow.test_friend_bundle

Nothing here runs DayZ, steamcmd or a server. It checks which files the exporter copies, refuses and
writes; it establishes nothing about DayZ behaviour or a real friend's install.
"""
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
import unittest.mock
import xml.etree.ElementTree as ET

from tools.setup import friend_bundle as fb, workshop_sync as ws

CFG = '''hostname = "Local";
password = "S3CRET-PASS-71";
passwordAdmin = "S3CRET-ADMIN-71";
thirdPersonView = 1;
disable3rdPerson = 0;
serverTimeAcceleration = 4;
serverNightTimeAcceleration = 8;
enableCfgGameplayFile = 1;
class Missions { class DayZ { template = "dayzOffline.chernarusplus"; }; };
'''


def put(root, rel, data='x'):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    return path


class RepoInputGuardTests(unittest.TestCase):
    """Read-only synthetic Git responses exercise the real release refusal guard."""
    ROOTS = ['mission/hollow-country', 'config', 'tools/package',
             'mods/HollowCountryExpansionAI/data/defaults']

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for root in self.ROOTS:
            put(self.root, root + '/synthetic.json', '{}')
        patch = unittest.mock.patch.object(fb.lts, 'ROOT', self.root)
        patch.start()
        self.addCleanup(patch.stop)

    def test_committed_inputs_pass_and_all_release_roots_are_checked(self):
        with unittest.mock.patch.object(fb.subprocess, 'run', return_value=
                subprocess.CompletedProcess([], 0, stdout=b'', stderr=b'')) as run:
            fb.check_repo_inputs()
        self.assertEqual(run.call_args_list[0].args[0],
                         ['git', 'diff', '--quiet', 'HEAD', '--', *self.ROOTS])
        tracked = run.call_args_list[1].args[0]
        self.assertEqual(tracked[:4], ['git', 'ls-files', '--error-unmatch', '--'])
        self.assertEqual(set(tracked[4:]), {root + '/synthetic.json' for root in self.ROOTS})
        for call in run.call_args_list:
            self.assertEqual(call.kwargs['cwd'], self.root)
            self.assertEqual(call.kwargs['env']['GIT_OPTIONAL_LOCKS'], '0')

    def test_modified_staged_deleted_inputs_or_git_error_refuse(self):
        for returncode in (1, 128):
            with self.subTest(returncode=returncode), unittest.mock.patch.object(
                    fb.subprocess, 'run', return_value=subprocess.CompletedProcess(
                        [], returncode, stdout=b'', stderr=b'private diagnostic')) as run:
                with self.assertRaisesRegex(fb.Refused, 'differ from build commit') as error:
                    fb.check_repo_inputs()
                self.assertNotIn('private diagnostic', str(error.exception))
                self.assertEqual(run.call_count, 1)

    def test_untracked_release_inputs_refuse(self):
        with unittest.mock.patch.object(fb.subprocess, 'run', side_effect=[
                subprocess.CompletedProcess([], 0, stdout=b'', stderr=b''),
                subprocess.CompletedProcess([], 1, stdout=b'', stderr=b'')]):
            with self.assertRaisesRegex(fb.Refused, 'untracked repo data or generators'):
                fb.check_repo_inputs()


class FriendBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(self.tmp, ignore_errors=True))
        m = self.tmp / 'server/mpmissions/dayzOffline.chernarusplus'
        put(m, 'init.c', 'void main() {}')
        put(m, 'storage_1/data/players.db', 'HC_SYNTHETIC_PRIVATE_STORAGE_71')
        # Synthetic stock supports the real checkout-driven economy generator. No
        # installed overlay may use placeholder receipts: scratch rollback validates them.
        from tools.package import datamined_items, firearms
        from tests.slow.test_datamined_items import stock_mission
        profile = json.loads((fb.SOURCE / 'economy-profiles/contextual-pilot.json').read_bytes())
        roster = firearms.selected_roster(json.loads((fb.lts.ROOT / fb.lts.FIREARMS_ROSTER).read_bytes()))
        names = set(profile['add_usage']) | {e['class'] for e in roster['entries']}
        names.update(e['new_type_parent'] for e in roster['entries'] if 'new_type_parent' in e)
        stock_mission(m, datamined_items.load_rows(), profile_names=sorted(names))
        carriers = ET.Element('spawnabletypes')
        for entry in roster['entries']:
            host = ET.SubElement(carriers, 'type', name=entry['class'])
            attachments = ET.SubElement(host, 'attachments', chance='1.0')
            for part in entry.get('parts', []):
                if part['route'] == 'native-carrier':
                    ET.SubElement(attachments, 'item', name=part['class'], chance='1.0')
        put(m, 'cfgspawnabletypes.xml', ET.tostring(carriers))
        put(m, 'cfggameplay.json', json.dumps({
            'version': 123, 'PlayerData': {}, 'UIData': {},
            'WorldsData': {'environmentMinTemps': [0] * 12, 'environmentMaxTemps': [20] * 12,
                           'objectSpawnersArr': []}}))
        put(m, 'expansion/settings/AIPatrolSettings.json', '{"Patrols": []}')
        put(m, 'server.log', 'log')
        self.mission = m
        p = self.tmp / 'profiles'
        put(p, 'HollowCountry/settings.json', '{}')
        put(p, 'HollowCountry/stamina.json', '{}')
        put(p, 'HollowCountry/interiors.json', '{}')
        put(p, 'HollowCountry/expansion-ai.json', '{}')
        # Local acceptance markers never ship: features are on by default, so the bundle carries neither the
        # opt-in diagnostic nor an operator's .disable opt-outs.
        put(p, 'HollowCountry/acceptance/xai_diagnostic_spawn.enable', '')
        put(p, 'HollowCountry/acceptance/events.disable', '')
        put(p, 'HollowCountry/acceptance/interior_search.disable', '')
        put(p, 'HollowCountry/templates/index.json', '{}')
        put(p, 'HollowCountry/templates/t-0000.json', '{}')
        put(p, 'HollowCountry/Ecology/settings.json', '{}')
        put(p, 'HollowCountry/Ecology/state-chernarusplus.json', '{}')
        put(p, 'HollowCountry/Events/settings.json', '{}')
        put(p, 'HollowCountry/Events/state/commit-1.json', '{}')
        put(p, 'HollowCountry/Events/rewards/2-boot.txt', '')
        put(p, 'HollowCountry/Groups/settings.json', '{}')
        put(p, 'HollowCountry/Groups/state/state_1.json', '{}')
        put(p, 'HollowCountry/Infected/config.json', '{}')
        put(p, 'HollowCountry/Infected/hordes-a.json', '{}')
        put(p, 'HollowCountry/hc-interiors-pack/receipt.json', '{}')
        put(p, 'HollowCountry/expansion-ai-leases.json', '{}')
        put(p, 'HollowCountry/expansion-ai-sites.json', '{}')
        put(p, 'HollowCountry/expansion-ai-localities.json', '{"synthetic": true}')
        for suffix in ('json', 'pending.json', 'bak.json'):
            put(p, 'HollowCountry/expansion-ai-locality-rotation.' + suffix, '{}')
        put(p, 'HollowCountry/expansion-ai-routes.json', '{}')
        put(p, 'HollowCountry/expansion-ai-caches.json', '{}')
        put(p, 'HollowCountry/expansion-ai-owned.json', '{}')
        put(p, 'ExpansionMod/Loadouts/HollowCountry_Patrol.json', '{}')
        put(p, 'ExpansionMod/Loadouts/OtherMod_Loadout.json', '{}')
        put(p, 'HollowCountry/SearchEconomy/epoch_1.json', '{}')
        put(p, 'ExpansionMod/Settings/AISettings.json', '{"Enabled": 1}')
        put(p, 'ExpansionMod/Settings/MarketSettings.json', '{}')
        put(p, 'DayZServer_x64.RPT', 'rpt')
        self.profiles = p
        mod = self.tmp / 'session/@HollowCountry'
        put(mod, 'addons/hollowcountry.pbo', b'PBO')
        put(mod, 'addons/hollowcountry.pbo.hollowcountry.bisign', b'SIG')
        put(mod, 'keys/hollowcountry.bikey', b'KEY')
        put(mod, 'mod.cpp', 'name = "Hollow Country";')
        self.mod = mod
        addon = self.tmp / 'session/@HollowCountryExpansionAI'
        put(addon, 'addons/hollowcountryexpansionai.pbo', b'PBO2')
        put(addon, 'addons/hollowcountryexpansionai.pbo.hollowcountry.bisign', b'SIG2')
        self.addon = addon
        self.cfg = put(self.tmp / 'server', 'serverDZ.cfg', CFG)
        self.out = self.tmp / 'bundle'
        # Bundle tests use synthetic stock and real authored data, but do not claim
        # commit provenance. Exercise the unmocked guard separately below.
        guard = unittest.mock.patch.object(fb, 'check_repo_inputs')
        self.repo_guard = guard.start()
        self.addCleanup(guard.stop)
        # Most tests cover export contents, not repository history. Avoid hundreds
        # of history subprocesses for the real template catalogue per build.
        if self._testMethodName not in {
                'test_profile_default_history_records_current_and_earlier_git_bytes',
                'test_profile_history_refuses_shallow_clone_and_missing_git',
                'test_profile_bytes_vs_repo_source_normalize_line_endings',
                'test_profile_content_drift_labels_history_best_effort',
                'test_missing_git_build_refuses_without_traceback'}:
            history = unittest.mock.patch.object(fb, 'profile_history', return_value=set())
            history.start()
            self.addCleanup(history.stop)

    def install_synthetic_economy(self):
        from tools.package import economy
        profile = {'schema': 1, 'name': 'synthetic-installed',
                   'add_usage': {'BandageDressing': ['Town']}, 'diagnostics': []}
        stage = self.tmp / 'installed-delta'
        economy.write_delta(stage, economy.generate(self.mission, profile, include_datamined=False))
        economy.install(stage, self.mission)

    def run_cli(self, *extra, addon=True):
        argv = ['build', '--mission', str(self.mission), '--profiles', str(self.profiles),
                '--mod', str(self.mod), '--server-cfg', str(self.cfg), '--out', str(self.out)]
        if addon:
            argv += ['--addon', str(self.addon)]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = fb.main(argv + list(extra))
        return code, buf.getvalue()

    def files(self):
        return sorted(str(p.relative_to(self.out)).replace(os.sep, '/')
                      for p in self.out.rglob('*') if p.is_file())

    def test_overlay_removal_ships_and_imports_with_only_bundled_helpers(self):
        code, text = self.run_cli()
        self.assertEqual(0, code, text)
        self.assertIn('tools/package/overlay_remove.py', self.files())
        self.assertFalse((self.out / 'tools/package/inventory_sizes.py').exists())
        # Fresh isolated interpreter: repository modules cannot satisfy imports.
        script = """import sys
sys.path.insert(0, sys.argv[1])
from tools.package import overlay_remove
assert 'tools.package.inventory_sizes' not in sys.modules
try:
    overlay_remove.remove('unused', ('inventory',), dry_run=True)
except ValueError as error:
    assert str(error) == overlay_remove.INVENTORY_GAP
else:
    raise AssertionError('inventory rollback must refuse')
"""
        result = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(self.out)],
                                cwd=self.tmp, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        guide = (self.out / 'README.txt').read_text()
        self.assertIn('tools.package.overlay_remove', guide)
        self.assertIn('--server-stopped', guide)

    def test_overlay_bundle_preflight_and_receipted_install_smoke(self):
        # Explicit synthetic stock; no DayZ/Workshop execution or runtime claim.
        import shutil
        from tools.package import optional_overlays as overlays
        repo = self.tmp / 'repo'
        source = repo / 'mission/hollow-country'
        shutil.copytree(fb.SOURCE, source)
        for name in ('config', 'tools', 'mods', 'docs'):
            shutil.copytree(fb.lts.ROOT / name, repo / name, ignore=shutil.ignore_patterns('__pycache__'))
        # Synthetic stock mirrors only the selective delta's required sheep fields.
        events = ET.fromstring((source / 'ecology/events.append.xml').read_bytes())
        children = events.find('event/children')
        children.remove(children.find("child[@type='Animal_OvisGmelini']"))
        ET.SubElement(events, 'event', {'name': 'SyntheticUnrelated'})
        # Default-on animal composition (#316) needs its native events and
        # territories; derive them from the authored policy, not a literal list.
        from tests.slow.test_animal_composition import AnimalComposition
        composition = json.loads((source / 'ecology/composition-variety.json').read_bytes())
        for name, choices in composition['NativeEvents'].items():
            event = ET.SubElement(events, 'event', {'name': name})
            for tag, text in (('nominal', '8'), ('min', '0'), ('max', '8'), ('limit', 'child')):
                ET.SubElement(event, tag).text = text
            kids = ET.SubElement(event, 'children')
            for classname, (_, maximum) in choices.items():
                ET.SubElement(kids, 'child', type=classname, min='0', max=str(maximum), lootmin='0', lootmax='0')
        environment = ET.fromstring(b'<env><territories><file path="env/hare_territories.xml"/>'
                                    b'<file path="env/hare_territories.xml"/></territories></env>')
        for name, choice in composition['NativeAmbient'].items():
            environment.find('territories').append(AnimalComposition.territory(name, choice))
        stock = {
            'cfgenvironment.xml': ET.tostring(environment) + b'\n',
            'db/events.xml': ET.tostring(events) + b'\n',
        }
        manifest_path = source / 'ecology/habitat-overrides.json'
        manifest = json.loads(manifest_path.read_bytes())
        manifest['Sources'] = [{'Path': name, 'Sha256': hashlib.sha256(data).hexdigest()}
                               for name, data in stock.items()]
        manifest_path.write_text(json.dumps(manifest))
        missing = source / 'ce/events.xml'
        data = missing.read_bytes()
        missing.unlink()
        put(self.mission, 'db/globals.xml', '<variables/>')
        with unittest.mock.patch.object(fb, 'SOURCE', source), \
                unittest.mock.patch.object(fb.lts, 'ROOT', repo):
            code, text = self.run_cli()
            self.assertEqual(code, 2, 'missing travel CE must refuse the bundle: ' + text)
            self.assertIn('travel CE', text)
            self.assertFalse(self.out.exists())
            missing.write_bytes(data)
            policy = source / 'optional/overlay-policy.json'
            policy_data = policy.read_bytes()
            policy.unlink()
            code, text = self.run_cli()
            self.assertEqual(code, 2, text)
            self.assertIn('optional overlay source', text)
            policy.write_bytes(policy_data)
            code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        self.assertIn('tools/package/HCWildlife_habitats.py', self.files())
        self.assertFalse(any(name.startswith('mpmissions/') for name in self.files()))
        self.assertFalse(any(name.endswith('db/globals.xml') for name in self.files()))
        target = self.tmp / 'friend-mission'
        put(target, 'cfgeconomycore.xml', '<economycore/>')
        put(target, 'cfggameplay.json', (self.mission / 'cfggameplay.json').read_bytes())
        for name, data in stock.items():
            put(target, name, data)
        original = {p.relative_to(target).as_posix(): p.read_bytes()
                    for p in target.rglob('*') if p.is_file()}
        self.assertEqual((self.out / 'mission-overlay/hollow-country/ecology/events.append.xml').read_bytes(),
                         (source / 'ecology/events.append.xml').read_bytes())
        candidate = overlays.bundle_candidate(self.out, target)
        overlays.install(candidate, target, managed_name=overlays.BUNDLE_MANAGED)
        self.assertTrue((target / overlays.BUNDLE_MANAGED / 'receipt.json').is_file())
        self.assertIn(b'hollow-country/ce', (target / 'cfgeconomycore.xml').read_bytes())
        installed_events = ET.fromstring((target / 'db/events.xml').read_bytes())
        self.assertEqual(len(installed_events.findall("event[@name='AnimalSheep']")), 1)
        self.assertIsNotNone(installed_events.find("event/children/child[@type='Animal_OvisGmelini']"))
        self.assertEqual(len(ET.fromstring((target / 'cfgenvironment.xml').read_bytes()).findall(
            "territories/file[@path='env/hare_territories.xml']")), 1)
        for path in source.rglob('*.json'):
            relative = path.relative_to(source)
            if relative.parts[0] in ('events',):
                self.assertEqual((target / 'hollow-country' / relative).read_bytes(), path.read_bytes())
        overlays.rollback(target, managed_name=overlays.BUNDLE_MANAGED)
        self.assertEqual({p.relative_to(target).as_posix(): p.read_bytes()
                          for p in target.rglob('*') if p.is_file()}, original)
        self.assertFalse((target / 'hollow-country/events/scene-chains.json').exists())

    def test_missing_authored_habitat_event_refuses_without_export(self):
        import shutil
        source = self.tmp / 'authored'
        shutil.copytree(fb.SOURCE, source)
        (source / 'ecology/events.append.xml').unlink()
        with unittest.mock.patch.object(fb, 'SOURCE', source):
            with self.assertRaisesRegex((fb.Refused, OSError, ValueError), 'events.append.xml'):
                fb.build(__import__('argparse').Namespace(out=self.out, mission=self.mission,
                    profiles=self.profiles, mod=self.mod, addon=self.addon,
                    server_cfg=self.cfg, ce_coverage_result=None))
            code, text = self.run_cli()
        self.assertEqual(code, 2, text)
        self.assertIn('events.append.xml', text)
        self.assertFalse(self.out.exists())

    def test_unreceipted_stale_habitat_copy_refuses_without_export(self):
        put(self.mission, 'hollow-country/ecology/events.append.xml', '<events><!--synthetic stale--></events>')
        code, text = self.run_cli()
        self.assertEqual(code, 2, text)
        self.assertIn('rollback refuses', text)
        self.assertFalse(self.out.exists())

    def test_bundle_ships_shared_ce_guard_without_requiring_optional_weapon_tools(self):
        """SYNTHETIC exported tools must import without the private checkout on sys.path."""
        import subprocess
        import sys
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        self.assertIn('tools/package/ce_extensions.py', self.files())
        result = subprocess.run([sys.executable, '-B', '-I', '-c',
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "from tools.package import ce_extensions, HCWildlife_habitats; "
            "ce_extensions.checked_core(b'<economycore><ce folder=\"hollow-country/ce\">"
            "<file name=\"types.xml\" type=\"types\"/></ce></economycore>')", str(self.out)],
            cwd=self.out, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_exported_supply_ledger_ships_and_its_loss_refuses_before_writes(self):
        """SYNTHETIC HC-22 delta: exported tools must name the missing ledger before importing repo-only tools."""
        import subprocess
        import sys
        from tools.package import datamined_items, economy
        from tests.slow.test_datamined_items import stock_mission, profile
        source = self.tmp / 'synthetic-supply'
        stock_mission(source, datamined_items.load_rows())
        stage = self.tmp / 'synthetic-supply-delta'
        economy.write_delta(stage, economy.generate(source, profile() | {'name': 'contextual-pilot'}))
        before = economy.snapshot(source)
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        ledger = self.out / 'config/loot-dispositions.json'
        self.assertEqual(ledger.read_bytes(), (fb.lts.ROOT / 'config/loot-dispositions.json').read_bytes())
        ledger.unlink()  # Deliberate incomplete-bundle fault; real bundles must carry this input.
        result = subprocess.run([sys.executable, '-B', '-I', '-c',
            'import sys; sys.path.insert(0, sys.argv[1]); from tools.package import economy; '
            'economy.install_delta(sys.argv[2], sys.argv[3])', str(self.out), str(stage), str(source)],
            cwd=self.out, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ValueError: HC22_DISPOSITIONS_MISSING', result.stderr)
        self.assertNotIn('FileNotFoundError', result.stderr)
        self.assertEqual(before, economy.snapshot(source))
        self.assertFalse((source / economy.MANAGED).exists())

    def test_mission_copy_keeps_config_and_drops_storage_rollback_and_logs(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        got = [f for f in self.files() if f.startswith('mpmissions/')]
        self.assertEqual(got, [])
        self.assertIn('mission-patches.json', self.files())
        self.assertIn('mission-overlay/hollow-country/events/scene-chains.json', self.files())

    def test_unreceipted_weapon_pack_deltas_refuse_instead_of_shipping(self):
        from tools.package import snafu_optional, tactical_flava_optional
        for managed in (snafu_optional.MANAGED, tactical_flava_optional.MANAGED):
            put(self.mission, managed + '/types.xml', '<types/>')
        code, text = self.run_cli()
        self.assertEqual(code, 2, text)
        self.assertIn('rollback refuses', text)
        self.assertFalse(self.out.exists())

    def test_a_locally_boosted_mission_exports_pre_boost_overlay_bytes_and_ships_the_boost_installer(self):
        # SYNTHETIC rows: the friend's own install doubles the loot once; the export must never carry doubled bytes.
        from tools.package import loot_boost
        self.install_synthetic_economy()
        unboosted = (self.mission / 'hollow-country/ce/types.xml').read_bytes()
        put(self.mission, 'db/globals.xml', '<variables><var name="RespawnTypes" type="0" value="12"/></variables>')
        loot_boost.install(self.mission, 2.0, None)
        self.assertNotEqual(unboosted, (self.mission / 'hollow-country/ce/types.xml').read_bytes())
        installed = {p.relative_to(self.mission): p.read_bytes() for p in self.mission.rglob('*') if p.is_file()}
        regenerated, _core, _gameplay = fb.fresh_economy(self.mission, self.tmp)
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        files = self.files()
        self.assertEqual((self.out / 'mission-overlay/hollow-country/ce/types.xml').read_bytes(), regenerated['ce/types.xml'])
        self.assertEqual(installed, {p.relative_to(self.mission): p.read_bytes() for p in self.mission.rglob('*') if p.is_file()})
        self.assertFalse([f for f in files if f.startswith('mission-overlay/' + loot_boost.MANAGED)])
        for name in ('tools/package/loot_boost.py', 'tools/package/firearms_roster.json',
                     'mission/hollow-country/loot-points/additions.json',
                     'mission/hollow-country/loot-points/families.json',
                     'mission/hollow-country/loot-points/settings.json'):
            self.assertIn(name, files)
        self.assertIn('loot boost', (self.out / 'README.txt').read_text())

    def test_locality_config_is_allowed_but_rotation_state_is_not(self):
        self.assertTrue(fb._profile_allowed('HollowCountry/expansion-ai-localities.json'))
        for suffix in ('json', 'pending.json', 'bak.json'):
            self.assertFalse(fb._profile_allowed('HollowCountry/expansion-ai-locality-rotation.' + suffix))

    def test_profile_copy_is_an_allowlist_of_config_never_runtime_state(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        got = [f for f in self.files() if f.startswith('profiles/')]
        expected = fb.repo_profile_sources()
        self.assertEqual(got, sorted('profiles/' + rel for rel in expected))
        for rel, source in expected.items():
            self.assertEqual((self.out / 'profiles' / rel).read_bytes(), fb.profile_bytes(source), rel)
        self.assertNotIn('profiles/HollowCountry/acceptance/events.disable', got)
        self.assertNotIn('profiles/HollowCountry/Events/state/commit-1.json', got)

    def test_legacy_room_owners_stay_out_when_the_template_pack_ships(self):
        # The pilot interiors.json is retired (the server ignores a stale copy) and HCInteriorTemplates refuses the
        # whole pack (rooms_conflict) beside the legacy production-rooms.json, so a bundle must carry neither.
        put(self.profiles, 'HollowCountry/Infected/production-rooms.json', '{}')
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        got = self.files()
        self.assertNotIn('profiles/HollowCountry/interiors.json', got)
        self.assertNotIn('profiles/HollowCountry/Infected/production-rooms.json', got)
        self.assertEqual((self.out / 'profiles/HollowCountry/templates/index.json').read_bytes(),
                         (fb.SOURCE / 'interiors/templates/index.json').read_bytes())

    def test_missing_installed_template_pack_still_ships_repo_templates(self):
        for name in ('index.json', 't-0000.json'):
            (self.profiles / 'HollowCountry' / 'templates' / name).unlink()
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        self.assertNotIn('profiles/HollowCountry/interiors.json', self.files())
        self.assertIn('profiles/HollowCountry/templates/index.json', self.files())

    def test_mods_and_public_keys_are_copied(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        got = self.files()
        for rel in ['@HollowCountry/addons/hollowcountry.pbo', '@HollowCountry/addons/hollowcountry.pbo.hollowcountry.bisign',
                    '@HollowCountry/keys/hollowcountry.bikey', '@HollowCountry/mod.cpp',
                    '@HollowCountryExpansionAI/addons/hollowcountryexpansionai.pbo', 'keys/hollowcountry.bikey']:
            self.assertIn(rel, got)

    def test_a_second_signed_pbo_in_the_mod_is_copied_with_its_bisign(self):
        put(self.mod, 'addons/hollowcountryanims.pbo', b'PBO3')
        put(self.mod, 'addons/hollowcountryanims.pbo.hollowcountry.bisign', b'SIG3')
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        got = self.files()
        for rel in ['@HollowCountry/addons/hollowcountryanims.pbo',
                    '@HollowCountry/addons/hollowcountryanims.pbo.hollowcountry.bisign']:
            self.assertIn(rel, got)

    def test_a_second_unsigned_pbo_in_the_mod_refuses(self):
        put(self.mod, 'addons/hollowcountryanims.pbo', b'PBO3')
        code, text = self.run_cli()
        self.assertNotEqual(code, 0)
        self.assertIn('hollowcountryanims.pbo', text)
        self.assertIn('bisign', text)
        self.assertFalse(self.out.exists())

    def test_without_addon_the_launcher_has_no_server_mod(self):
        code, text = self.run_cli(addon=False)
        self.assertEqual(code, 0, text)
        bat = (self.out / 'start-server.bat').read_text()
        self.assertNotIn('-serverMod', bat)
        self.assertNotIn('@HollowCountryExpansionAI', bat)
        self.assertFalse(any(f.startswith('@HollowCountryExpansionAI') for f in self.files()))

    def test_launcher_uses_manifest_load_order_and_shared_mod_list(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        bat = (self.out / 'start-server.bat').read_text()
        expected = ws.launch_lines(ws.select(ws.load_manifest(), ws.GROUPS))[0]
        self.assertIn('"' + expected + '"', bat)
        self.assertNotIn('-serverMod', bat)
        self.assertIn('-config=serverDZ.cfg', bat)
        self.assertIn('-profiles=profiles', bat)
        self.assertIn('-port=2302', bat)
        self.assertIn(b'\r\n', (self.out / 'start-server.bat').read_bytes())

    def test_server_settings_carry_managed_values_and_never_passwords(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        snippet = (self.out / 'serverDZ-hollow-country.txt').read_text()
        for line in ['thirdPersonView = 1;', 'disable3rdPerson = 0;', 'serverTimeAcceleration = 4;',
                     'serverNightTimeAcceleration = 8;', 'enableCfgGameplayFile = 1;',
                     'template = "dayzOffline.chernarusplus";']:
            self.assertIn(line, snippet)
        for path in self.out.rglob('*'):
            if path.is_file():
                data = path.read_bytes()
                self.assertFalse(b'S3CRET' in data, path.relative_to(self.out).as_posix())
                self.assertFalse(b'HC_SYNTHETIC_PRIVATE_STORAGE_71' in data, path.relative_to(self.out).as_posix())

    def test_readme_names_every_workshop_item_and_the_ports(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        readme = (self.out / 'README.txt').read_text()
        for item in ['1559212036', '1564026768', '2792984722', '3556131153', '3105330157', '2545327648', '2291785308', '2116157322', '2291785437', '3114410963', '2792982069', '2443122116',
                     '2646817942']:
            self.assertIn('workshop_download_item 221100 ' + item, readme)
        self.assertIn('2302', readme)
        self.assertIn('27016', readme)
        self.assertIn('Players subscribe to @HollowCountryExpansionAI when this server uses it', readme)
        self.assertIn('Default dependencies are subscribed from the Workshop, never repacked or included as third-party files.', readme)
        for optional_name in ['Community Framework (CF)', 'COT', 'RaG_Core', 'RaG Immersive Vehicles', 'Expansion Navigation (GPS)', 'Dabs Framework', 'Expansion-Core',
                              'Expansion-AI',
                              'Ambient Animals Pack']:
            self.assertIn(optional_name, readme)
        mod_line = next(line for line in fb.ws.launch_lines(fb.ws.select(fb.ws.load_manifest(), fb.ws.GROUPS))
                        if line.startswith('-mod='))
        self.assertIn(mod_line, readme)
        self.assertIn('"' + mod_line + '"', (self.out / 'start-server.bat').read_text())
        self.assertEqual(readme.count(fb.overlays.friend_notes().replace('\r\n', '\n')), 1)

    def test_mission_cleanup_leaves_readme_notes_to_the_bundle_writer(self):
        # Synthetic bytes: this helper receives mission rows in build(), before README creation.
        original = b'SYNTHETIC README\r\n'
        rows = fb.overlays.friend_bundle_plan(self.mission, [('README.txt', original)])
        self.assertEqual(dict(rows)['README.txt'], original)

    def test_the_guided_installer_and_report_tool_ship_with_crlf_batch_files(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        got = self.files()
        for rel in ['install-hollow-country.bat', 'server-report.bat', 'tools/setup/friend_install.py',
                    'tools/setup/server_report.py', 'tools/setup/workshop_sync.py', 'tools/setup/workshop_mods.json']:
            self.assertIn(rel, got)
        for name, module in (('install-hollow-country.bat', 'tools.setup.friend_install'),
                             ('server-report.bat', 'tools.setup.server_report')):
            data = (self.out / name).read_bytes()
            self.assertIn(module.encode(), data)
            self.assertNotIn(b'\n', data.replace(b'\r\n', b''), name + ' must be CRLF only')

    def test_the_bundled_installer_modules_import_from_the_bundle_alone(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, '-I', '-c',
             'import sys; sys.path.insert(0, %r); import tools.setup.friend_install as f, tools.setup.server_report as r; '
             'print(f.__file__)' % str(self.out)],
            capture_output=True, text=True, cwd=str(self.tmp))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip().startswith(str(self.out)), result.stdout)

    def test_readme_first_steps_are_the_guided_installer_and_the_report(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        readme = (self.out / 'README.txt').read_text()
        self.assertIn('install-hollow-country.bat', readme.split('3. Copy', 1)[0])
        self.assertLess(readme.index('install-hollow-country.bat'), readme.index('1. Install DayZ Server'))
        self.assertIn('after a play session, run server-report.bat and upload the file', readme.lower())

    def test_the_map_overlay_tool_and_its_layer_config_ship_and_run_from_the_bundle_alone(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        got = self.files()
        source = fb.lts.ROOT / 'config/map-overlays'
        wanted = sorted(p.relative_to(fb.lts.ROOT).as_posix() for p in source.rglob('*.json'))
        self.assertIn('config/map-overlays/profile.json', wanted)
        self.assertTrue(any(w.startswith('config/map-overlays/layers/') for w in wanted))
        for rel in wanted + ['tools/package/map_overlay.py']:
            self.assertIn(rel, got)
            self.assertEqual((self.out / rel).read_bytes(), (fb.lts.ROOT / rel).read_bytes())
        self.assertEqual(self.repo_guard.call_count, 2, 'check release inputs before planning and after staging')
        manifest = json.loads((self.out / 'bundle-manifest.json').read_text())
        listed = {row['path'] for row in manifest['files']}
        self.assertIn('tools/package/map_overlay.py', listed)
        self.assertTrue(set(wanted) <= listed)
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, '-I', '-c',
             'import sys; sys.path.insert(0, %r); from tools.package import map_overlay as m; '
             'sys.exit(m.main(["validate"]))' % str(self.out)],
            capture_output=True, text=True, cwd=str(self.tmp))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Overlay layers valid', result.stdout)

    def test_a_locally_installed_map_overlay_never_reaches_the_export(self):
        # SYNTHETIC rows: the friend installs the map overlay layers themselves; the owner's local copy of it
        # (its spawner files and its entries in cfggameplay.json) must not be exported as authored overlay bytes.
        from tools.package import map_overlay
        from tests.slow.test_map_overlay import source, layer, obj, PROTO_XML
        managed = map_overlay.MANAGED
        put(self.mission, 'mapgroupproto.xml', PROTO_XML)
        map_overlay.install(source(layers=[layer(objects=[obj('synthetic', x=5000)])]), self.mission)
        installed = (self.mission / 'cfggameplay.json').read_bytes()
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        self.assertEqual([f for f in self.files() if managed in f], [])
        patches = (self.out / 'mission-patches.json').read_text()
        self.assertNotIn(managed, patches)
        self.assertEqual((self.mission / 'cfggameplay.json').read_bytes(), installed)

    def test_manifest_hashes_every_bundled_file(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        self.assertEqual(self.repo_guard.call_count, 2, 'check release inputs before planning and after staging')
        manifest = json.loads((self.out / 'bundle-manifest.json').read_text())
        listed = {row['path']: row['sha256'] for row in manifest['files']}
        on_disk = [f for f in self.files() if f != 'bundle-manifest.json']
        self.assertEqual(sorted(listed), on_disk)
        for rel, digest in listed.items():
            self.assertEqual(hashlib.sha256((self.out / rel).read_bytes()).hexdigest(), digest)
        self.assertGreater(manifest['excluded']['profiles'], 0)
        self.assertGreater(manifest['excluded']['mission'], 0)

    def test_profile_default_history_records_current_and_earlier_git_bytes(self):
        # Synthetic history, including a rename: read-only git calls, no test repository writes.
        import subprocess
        old, older = b'{"synthetic_release": 52}', b'{"synthetic_release": 50}'
        rel = 'profiles/HollowCountry/expansion-ai-sites.json'
        put(self.profiles, rel.removeprefix('profiles/'), b'{"synthetic_release": 54}')
        custom = 'ExpansionMod/Loadouts/HollowCountry_SyntheticCustom.json'
        put(self.profiles, custom, b'{"synthetic_operator_loadout": true}')
        source = 'mods/HollowCountryExpansionAI/data/defaults/expansion-ai-sites.json'
        previous = 'mission/hollow-country/ai/sites.json'

        def git_result(argv, **kwargs):
            if argv[1] == 'rev-parse':
                return subprocess.CompletedProcess(argv, 0, stdout=b'false\n', stderr=b'')
            if argv[1] == 'log':
                data = ('a' * 40 + '\n\n' + source + '\n' + 'b' * 40 + '\n\n' + previous + '\n').encode()
            else:
                self.assertEqual(argv[1], 'show')
                data = old if argv[-1].startswith('a' * 40 + ':') else older
            return subprocess.CompletedProcess(argv, 0, stdout=data, stderr=b'')

        with unittest.mock.patch('subprocess.run', side_effect=git_result) as calls:
            code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        manifest = json.loads((self.out / 'bundle-manifest.json').read_text())
        profiles = {row['path']: row['sha256'] for row in manifest['files']
                    if row['path'].startswith('profiles/')}
        self.assertEqual(set(manifest['profile_defaults']), set(profiles))
        self.assertNotIn('profiles/' + custom, manifest['profile_defaults'])
        self.assertFalse((self.out / 'profiles' / custom).exists())
        self.assertEqual(fb.profile_defaults([(custom, self.profiles / custom)])['profiles/' + custom]['history'],
                         'receipt-only')
        for name, digest in profiles.items():
            self.assertEqual(manifest['profile_defaults'][name]['sha256'], digest)
            self.assertIn(digest, manifest['profile_defaults'][name]['shipped_sha256'])
        self.assertTrue({hashlib.sha256(old).hexdigest(), hashlib.sha256(older).hexdigest()}
                        <= set(manifest['profile_defaults'][rel]['shipped_sha256']))
        self.assertTrue(any(c.args[0][1] == 'log' and '--follow' in c.args[0]
                            and source in c.args[0] for c in calls.call_args_list))
        with unittest.mock.patch('subprocess.run', return_value=subprocess.CompletedProcess(
                [], 128, stdout=b'', stderr=b'synthetic private path or identity')):
            with self.assertRaisesRegex(fb.Refused, '^profile_history_unavailable:') as error:
                fb.profile_history(source)
        self.assertNotIn('private path or identity', str(error.exception))

    def test_profile_history_refuses_shallow_clone_and_missing_git(self):
        # Synthetic git answers only; no repository is read.
        import subprocess
        source = 'mods/HollowCountryExpansionAI/data/defaults/expansion-ai-sites.json'

        def shallow(argv, **kwargs):
            self.assertEqual(argv[1:], ['rev-parse', '--is-shallow-repository'])
            return subprocess.CompletedProcess(argv, 0, stdout=b'true\n', stderr=b'')

        with unittest.mock.patch('subprocess.run', side_effect=shallow):
            with self.assertRaisesRegex(fb.Refused, '^profile_history_unavailable: shallow clone'):
                fb.profile_history(source)
        with unittest.mock.patch('subprocess.run', side_effect=FileNotFoundError('git')):
            with self.assertRaisesRegex(fb.Refused, '^profile_history_unavailable: git binary') as error:
                fb.profile_history(source)
        self.assertNotIn('FileNotFoundError', str(error.exception))

    def test_missing_git_build_refuses_without_traceback(self):
        put(self.profiles, 'HollowCountry/expansion-ai-sites.json', b'{"synthetic_release": 54}')
        with unittest.mock.patch('subprocess.run', side_effect=FileNotFoundError('git')):
            code, text = self.run_cli()
        self.assertNotEqual(code, 0)
        self.assertIn('profile_history_unavailable', text)
        self.assertNotIn('Traceback', text)
        self.assertFalse(self.out.exists())

    def test_profile_bytes_vs_repo_source_normalize_line_endings(self):
        import subprocess
        source = 'mods/HollowCountryExpansionAI/data/defaults/expansion-ai-sites.json'
        current = (fb.lts.ROOT / source).read_bytes()
        rel = 'HollowCountry/expansion-ai-sites.json'

        def git_result(argv, **kwargs):
            if argv[1] == 'rev-parse':
                return subprocess.CompletedProcess(argv, 0, stdout=b'false\n', stderr=b'')
            data = ('a' * 40 + '\n\n' + source + '\n').encode() if argv[1] == 'log' else current
            return subprocess.CompletedProcess(argv, 0, stdout=data, stderr=b'')

        crlf = current.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        put(self.profiles, rel, crlf)
        with unittest.mock.patch('subprocess.run', side_effect=git_result):
            defaults = fb.profile_defaults([(rel, self.profiles / rel)])
            self.assertEqual(defaults['profiles/' + rel]['sha256'],
                             hashlib.sha256(fb.normalize_profile(current)).hexdigest())
        put(self.profiles, rel, current)
        with unittest.mock.patch('subprocess.run', side_effect=git_result):
            defaults = fb.profile_defaults([(rel, self.profiles / rel)])
        self.assertEqual(defaults['profiles/' + rel]['history'], 'git-log')

    def test_profile_content_drift_labels_history_best_effort(self):
        import subprocess
        source = 'mods/HollowCountryExpansionAI/data/defaults/expansion-ai-sites.json'
        rel = 'HollowCountry/expansion-ai-sites.json'

        def git_result(argv, **kwargs):
            if argv[1] == 'rev-parse':
                return subprocess.CompletedProcess(argv, 0, stdout=b'false\n', stderr=b'')
            data = ('a' * 40 + '\n\n' + source + '\n').encode() if argv[1] == 'log' else b'{"x": 1}'
            return subprocess.CompletedProcess(argv, 0, stdout=data, stderr=b'')

        put(self.profiles, rel, b'{"synthetic_release": 54}')
        buf = io.StringIO()
        with unittest.mock.patch('subprocess.run', side_effect=git_result), contextlib.redirect_stdout(buf):
            defaults = fb.profile_defaults([(rel, self.profiles / rel)])
        row = defaults['profiles/' + rel]
        self.assertEqual(row['history'], 'git-log-best-effort')
        self.assertIn('best-effort', buf.getvalue())

    def test_private_key_anywhere_refuses_and_writes_nothing(self):
        put(self.mod, 'keys/hollowcountry.biprivatekey', b'PRIVATE')
        code, text = self.run_cli()
        self.assertNotEqual(code, 0)
        self.assertIn('biprivatekey', text)
        self.assertFalse(self.out.exists())

    def test_symlink_in_input_refuses(self):
        os.symlink(self.cfg, self.mission / 'linked.cfg')
        code, text = self.run_cli()
        self.assertNotEqual(code, 0)
        self.assertIn('symlink', text)
        self.assertFalse(self.out.exists())

    def test_existing_output_refuses(self):
        self.out.mkdir()
        code, text = self.run_cli()
        self.assertNotEqual(code, 0)
        self.assertIn('exists', text)

    def test_mod_without_signed_pbo_refuses(self):
        (self.mod / 'addons/hollowcountry.pbo.hollowcountry.bisign').unlink()
        code, text = self.run_cli()
        self.assertNotEqual(code, 0)
        self.assertIn('bisign', text)
        self.assertFalse(self.out.exists())


    def test_coverage_is_left_out_once_when_result_is_pending(self):
        from tests.slow import test_ce_coverage as fixtures
        from tools.package import ce_coverage
        stock = fixtures.stock_proto()
        put(self.mission, 'mapgroupproto.xml', stock)
        self.install_synthetic_economy()
        result = put(self.tmp, 'synthetic-result.json', fixtures.blob(fixtures.result_doc(stock)))
        delta = self.tmp / 'coverage-delta'
        ce_coverage.write_delta(delta, ce_coverage.generate(result.read_bytes(), self.mission))
        ce_coverage.install(delta, self.mission)
        installed = (self.mission / 'mapgroupproto.xml').read_bytes()
        code, text = self.run_cli('--ce-coverage-result', str(self.tmp / 'missing-result.json'))
        self.assertEqual(code, 0, text)
        self.assertEqual(text.count('left out CE building coverage'), 1)
        self.assertIn('PENDING', text)
        bundled = self.out / 'mpmissions' / self.mission.name
        self.assertFalse((bundled / 'mapgroupproto.xml').exists())
        self.assertFalse((bundled / ce_coverage.MANAGED).exists())
        self.assertEqual((self.mission / 'mapgroupproto.xml').read_bytes(), installed)

    def test_validated_coverage_stays_local_without_changing_source(self):
        from tests.slow import test_ce_coverage as fixtures
        stock = fixtures.stock_proto()
        put(self.mission, 'mapgroupproto.xml', stock)
        self.install_synthetic_economy()
        result = put(self.tmp, 'synthetic-result.json', fixtures.blob(fixtures.result_doc(stock)))
        code, text = self.run_cli('--ce-coverage-result', str(result))
        self.assertEqual(code, 0, text)
        bundled = self.out / 'mpmissions' / self.mission.name
        self.assertFalse((bundled / 'mapgroupproto.xml').exists())
        self.assertEqual((self.mission / 'mapgroupproto.xml').read_bytes(), stock)
        self.assertFalse(any(Path(name).name == result.name or 'coverage-delta' in Path(name).parts
                             for name in self.files()))
        self.assertIn('tools/setup/interior_sampler.py', self.files(),
                      'the public sampling tool ships; private native results do not')
        self.assertIn('left out CE building coverage', text)


    def test_invalid_coverage_result_is_left_out_once_and_no_points_are_bundled(self):
        from tests.slow import test_ce_coverage as fixtures
        stock = fixtures.stock_proto()
        put(self.mission, 'mapgroupproto.xml', stock)
        result = put(self.tmp, 'synthetic-invalid-result.json', '{}')
        code, text = self.run_cli('--ce-coverage-result', str(result))
        self.assertEqual(code, 0, text)
        self.assertEqual(text.count('left out CE building coverage'), 1)
        self.assertFalse((self.out / 'mpmissions' / self.mission.name / 'mapgroupproto.xml').exists())

    def test_installed_coverage_and_valid_result_ship_no_stock_proto_bytes(self):
        from tests.slow import test_ce_coverage as fixtures
        from tools.package import ce_coverage
        stock = fixtures.stock_proto()
        put(self.mission, 'mapgroupproto.xml', stock)
        self.install_synthetic_economy()
        result = put(self.tmp, 'synthetic-result.json', fixtures.blob(fixtures.result_doc(stock)))
        delta = self.tmp / 'coverage-delta'
        ce_coverage.write_delta(delta, ce_coverage.generate(result.read_bytes(), self.mission))
        ce_coverage.install(delta, self.mission)
        installed = (self.mission / 'mapgroupproto.xml').read_bytes()
        code, text = self.run_cli('--ce-coverage-result', str(result))
        self.assertEqual(code, 0, text)
        self.assertIn('left out CE building coverage', text)
        self.assertFalse((self.out / 'mpmissions' / self.mission.name / 'mapgroupproto.xml').exists())
        self.assertFalse(any(ce_coverage.MANAGED in name for name in self.files()))
        manifest = json.loads((self.out / 'bundle-manifest.json').read_bytes())
        for row in manifest['files']:
            self.assertEqual(hashlib.sha256((self.out / row['path']).read_bytes()).hexdigest(), row['sha256'])
        self.assertTrue((self.mission / ce_coverage.MANAGED / 'receipt.json').is_file())


if __name__ == '__main__':
    unittest.main()


class HomePathRedactionTests(unittest.TestCase):
    """Review P3 (#113): an OSError names the failing path; the printed refusal must not show the home folder."""

    def home_error(self):
        return OSError(2, 'No such file or directory', str(Path.home() / 'private' / 'mission.xml'))

    def test_bundle_refusal_prints_the_home_folder_as_tilde(self):
        err = io.StringIO()
        with unittest.mock.patch.object(fb, 'build', side_effect=self.home_error()), \
                contextlib.redirect_stderr(err):
            code = fb.main(['build', '--mission', 'm', '--profiles', 'p', '--mod', 'x', '--server-cfg', 's',
                            '--out', 'o'])
        self.assertEqual(code, 2)
        self.assertIn('~/private/mission.xml', err.getvalue())
        self.assertNotIn(str(Path.home()) + os.sep, err.getvalue())

    def test_invalid_coverage_reason_prints_the_home_folder_as_tilde(self):
        with unittest.mock.patch.object(fb.ce_coverage, 'validate', side_effect=self.home_error()):
            report = fb.coverage_report(Path('result.json'))
        self.assertEqual(report['status'], 'invalid')
        self.assertIn('~/private/mission.xml', report['reason'])
        self.assertNotIn(str(Path.home()) + os.sep, report['reason'])

    def test_launcher_refusal_prints_the_home_folder_as_tilde(self):
        from tools.setup import local_test_session as lts
        err = io.StringIO()
        with unittest.mock.patch.object(lts, 'rollback', side_effect=self.home_error()), \
                contextlib.redirect_stderr(err):
            code = lts.main(['rollback', '--server-root', 'srv', '--dry-run'], out=io.StringIO())
        self.assertNotEqual(code, 0)
        self.assertIn('~/private/mission.xml', err.getvalue())
        self.assertNotIn(str(Path.home()) + os.sep, err.getvalue())


MAP_CLASSES = {'kind': 'hollow-country-overlay-classes',
               'provenance': {'source': 'synthetic test allowlist', 'method': 'invented', 'verified': 'none'},
               'classes': {'Land_Mil_Tent_Big1_1': {'pbo': 'structures_military.pbo'}}}
MAP_PROFILE = {'kind': 'hollow-country-overlay-profile', 'enabled': ['alpha-v1'],
               'limits': {'map_size': 15360, 'max_objects_total': 20, 'max_objects_per_layer': 10,
                          'min_spacing_m': 6.0, 'vanilla_clearance_m': 8.0}}
MAP_LAYER = {'kind': 'hollow-country-map-overlay', 'id': 'alpha-v1', 'version': 1,
             'purpose': 'synthetic test layer', 'status': 'runtime-unverified',
             'objects': [{'id': 't01', 'class': 'Land_Mil_Tent_Big1_1', 'pos': [2000.0, 100.0, 3000.0],
                          'yaw': 0.0, 'loot': 'proto', 'area': 'synthetic'}]}


def synthetic_mission(root, rows):
    groups = ''.join('<group name="%s" pos="%s %s %s" rpy="0 0 0" a="80" />\n' % row for row in rows)
    put(root, 'mapgrouppos.xml', '<map>\n' + groups + '</map>\n')
    put(root, 'mapgroupproto.xml', '<prototype><group name="Land_Mil_Tent_Big1_1" lootmax="11">'
                                   '<usage name="Military" /></group></prototype>\n')
    return Path(root)


def synthetic_layers(root):
    put(root, 'profile.json', json.dumps(MAP_PROFILE))
    put(root, 'classes.json', json.dumps(MAP_CLASSES))
    put(root, 'layers/alpha-v1.json', json.dumps(MAP_LAYER))
    return Path(root)


class OverlayVanillaCheckTests(unittest.TestCase):
    """#336: the bundle's own layer validation against a mission's vanilla rows, with a synthetic mission."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.layers = synthetic_layers(self.root / 'layers-src')

    def mission(self, rows):
        return synthetic_mission(self.root / 'mission', rows)

    def test_layers_clear_of_every_vanilla_row_are_valid(self):
        mission = self.mission([('Land_House_1W12_Brown', '2500', '101', '3500')])
        self.assertEqual(fb.overlay_vanilla_errors(mission, self.layers), [])

    def test_a_vanilla_row_on_a_layer_object_refuses_and_is_listed(self):
        mission = self.mission([('Land_Mil_Barracks2', '2000', '100', '3000')])
        errors = fb.overlay_vanilla_errors(mission, self.layers)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn('vanilla group Land_Mil_Barracks2', errors[0])
        self.assertIn('alpha-v1/t01', errors[0])

    def test_the_mission_is_only_read(self):
        mission = self.mission([('Land_Mil_Barracks2', '2000', '100', '3000')])
        before = {p.name: p.read_bytes() for p in mission.iterdir()}
        fb.overlay_vanilla_errors(mission, self.layers)
        self.assertEqual({p.name: p.read_bytes() for p in mission.iterdir()}, before)

    def test_unreadable_vanilla_rows_are_an_error_not_a_pass(self):
        mission = self.mission([])
        (mission / 'mapgrouppos.xml').unlink()
        errors = fb.overlay_vanilla_errors(mission, self.layers)
        self.assertEqual(len(errors), 1)
        self.assertIn('could not be read', errors[0])

    def test_the_command_lists_every_error_and_fails(self):
        mission = self.mission([('Land_Mil_Barracks2', '2000', '100', '3000')])
        err, out = io.StringIO(), io.StringIO()
        with unittest.mock.patch.object(fb, 'MAP_OVERLAY_CONFIG', str(self.layers)), \
                contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            code = fb.main(['check-overlays', '--mission', str(mission)])
        self.assertEqual(code, 1)
        self.assertIn('refused: vanilla group Land_Mil_Barracks2', err.getvalue())

    def test_the_command_passes_a_clean_mission(self):
        mission = self.mission([('Land_House_1W12_Brown', '2500', '101', '3500')])
        err, out = io.StringIO(), io.StringIO()
        with unittest.mock.patch.object(fb, 'MAP_OVERLAY_CONFIG', str(self.layers)), \
                contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            code = fb.main(['check-overlays', '--mission', str(mission)])
        self.assertEqual(code, 0, err.getvalue())
        self.assertIn('valid', out.getvalue())


class FriendcycleOverlayGateTests(unittest.TestCase):
    """#336: friendcycle refuses before building when the overlay layers fail against the mission's vanilla rows."""

    def setUp(self):
        from tools.release import friendcycle
        self.fc = friendcycle
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.args = unittest.mock.Mock(out=self.root / 'signed', bundle_out=self.root / 'bundle', build='999',
                                       commit='HEAD', allow_unpushed=True, mission=self.root / 'mission')
        for name, value in (('resolve_commit', 'a' * 40), ('build', None)):
            patch = unittest.mock.patch.object(self.fc, name, return_value=value)
            setattr(self, name, patch.start())
            self.addCleanup(patch.stop)

    def test_no_mission_is_a_hard_failure_never_a_pass(self):
        self.args.mission = None
        with self.assertRaises(ValueError) as caught:
            self.fc.cycle(self.args)
        self.assertIn('overlay vanilla check not run', str(caught.exception))
        self.build.assert_not_called()

    def test_a_refused_check_stops_the_cycle_before_anything_is_built(self):
        with unittest.mock.patch.object(self.fc, 'overlay_vanilla_check',
                                        side_effect=ValueError('overlay layers refused')) as check:
            with self.assertRaises(ValueError):
                self.fc.cycle(self.args)
        check.assert_called_once_with('a' * 40, self.args.mission, '999')
        self.build.assert_not_called()

    def run_check(self, help_text, completed):
        import contextlib as ctx

        @ctx.contextmanager
        def tree(_sha, _number):
            yield self.root
        with unittest.mock.patch.object(self.fc, 'worktree', tree), \
                unittest.mock.patch.object(self.fc, 'run', return_value=help_text), \
                unittest.mock.patch.object(self.fc.subprocess, 'run', return_value=completed):
            return self.fc.overlay_vanilla_check('a' * 40, self.root / 'mission', '999')

    def completed(self, code, err=''):
        return subprocess.CompletedProcess([], code, stdout='', stderr=err)

    def test_a_pass_returns(self):
        self.assertIsNone(self.run_check('{build,check-overlays}', self.completed(0)))

    def test_every_error_is_listed_in_the_refusal(self):
        err = ''.join('refused: flat: military-zones-v2/s0%02d: height 257.0 differs from the median 255.9\n' % n
                      for n in range(60))
        with self.assertRaises(ValueError) as caught:
            self.run_check('{build,check-overlays}', self.completed(1, err))
        text = str(caught.exception)
        self.assertIn('the build is refused', text)
        self.assertIn('flat: military-zones-v2/s000', text)
        self.assertIn('flat: military-zones-v2/s039', text)
        self.assertIn('(+20 more)', text)

    def test_a_pinned_commit_without_the_command_did_not_run_the_check_and_fails(self):
        with self.assertRaises(ValueError) as caught:
            self.run_check('{build}', self.completed(0))
        self.assertIn('overlay vanilla check not run', str(caught.exception))

    def test_a_check_that_died_without_a_result_is_not_a_pass(self):
        with self.assertRaises(ValueError) as caught:
            self.run_check('{build,check-overlays}', self.completed(3, 'Traceback...'))
        self.assertIn('overlay vanilla check not run', str(caught.exception))
