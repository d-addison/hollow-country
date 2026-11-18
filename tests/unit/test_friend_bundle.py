"""Friend server bundle: synthetic mission, profile and mod trees only.

Additional TDD RED for optional invalid results, before the omission fix (verbatim failure line):
AssertionError: 2 != 0 : refused: sampler result keys must be exactly: frame, groups, kind, native_run_id, pins, schema
Ran 1 test in 0.132s
FAILED (failures=1)
GREEN command: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_friend_bundle

Nothing here runs DayZ, steamcmd or a server. It checks which files the exporter copies, refuses and
writes; it establishes nothing about DayZ behaviour or a real friend's install.
"""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import unittest.mock

from tools.setup import friend_bundle as fb

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


class FriendBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(self.tmp, ignore_errors=True))
        m = self.tmp / 'server/mpmissions/dayzOffline.chernarusplus'
        put(m, 'init.c', 'void main() {}')
        put(m, 'cfgeconomycore.xml', '<economycore/>')
        put(m, 'db/types.xml', '<types/>')
        put(m, 'storage_1/data/players.db', 'PLAYERS')
        put(m, 'hollow-country/ce/types.xml', '<types/>')
        put(m, 'hollow-country/core.backup', 'old')
        put(m, 'hollow-country/receipt.json', '{}')
        put(m, 'hollow-country-gameplay/gear/hardscrabble.json', '{}')
        put(m, 'hollow-country-gameplay/cfggameplay.backup', 'old')
        put(m, 'hollow-country-extra/verification.json', '{}')
        put(m, 'hollow-country-extra/ce/types.xml', '<types/>')
        put(m, 'hollow-country-extra/core.next', 'n')
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

    def test_mission_copy_keeps_config_and_drops_storage_rollback_and_logs(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        got = [f for f in self.files() if f.startswith('mpmissions/')]
        base = 'mpmissions/dayzOffline.chernarusplus/'
        self.assertEqual(got, sorted(base + r for r in [
            'cfgeconomycore.xml', 'db/types.xml', 'expansion/settings/AIPatrolSettings.json',
            'hollow-country-extra/ce/types.xml', 'hollow-country-gameplay/gear/hardscrabble.json',
            'hollow-country/ce/types.xml', 'init.c']))

    def test_profile_copy_is_an_allowlist_of_config_never_runtime_state(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        got = [f for f in self.files() if f.startswith('profiles/')]
        self.assertEqual(got, sorted('profiles/' + r for r in [
            'ExpansionMod/Loadouts/HollowCountry_Patrol.json', 'ExpansionMod/Settings/AISettings.json',
            'HollowCountry/Ecology/settings.json', 'HollowCountry/Events/settings.json',
            'HollowCountry/Groups/settings.json', 'HollowCountry/Infected/config.json',
            'HollowCountry/expansion-ai-sites.json', 'HollowCountry/expansion-ai.json',
            'HollowCountry/settings.json', 'HollowCountry/stamina.json',
            'HollowCountry/templates/index.json', 'HollowCountry/templates/t-0000.json']))

    def test_legacy_room_owners_stay_out_when_the_template_pack_ships(self):
        # HCInteriorTemplates refuses the whole pack (rooms_conflict) when the pilot interiors.json or the
        # legacy production-rooms.json sits beside it, so a bundle with templates must not carry them.
        put(self.profiles, 'HollowCountry/Infected/production-rooms.json', '{}')
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        got = self.files()
        self.assertNotIn('profiles/HollowCountry/interiors.json', got)
        self.assertNotIn('profiles/HollowCountry/Infected/production-rooms.json', got)
        self.assertIn('rooms_conflict', text)

    def test_pilot_interiors_config_ships_when_there_is_no_template_pack(self):
        for name in ('index.json', 't-0000.json'):
            (self.profiles / 'HollowCountry' / 'templates' / name).unlink()
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        self.assertIn('profiles/HollowCountry/interiors.json', self.files())

    def test_mods_and_public_keys_are_copied(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        got = self.files()
        for rel in ['@HollowCountry/addons/hollowcountry.pbo', '@HollowCountry/addons/hollowcountry.pbo.hollowcountry.bisign',
                    '@HollowCountry/keys/hollowcountry.bikey', '@HollowCountry/mod.cpp',
                    '@HollowCountryExpansionAI/addons/hollowcountryexpansionai.pbo', 'keys/hollowcountry.bikey']:
            self.assertIn(rel, got)

    def test_without_addon_the_launcher_has_no_server_mod(self):
        code, text = self.run_cli(addon=False)
        self.assertEqual(code, 0, text)
        bat = (self.out / 'start-server.bat').read_text()
        self.assertNotIn('-serverMod', bat)
        self.assertFalse(any(f.startswith('@HollowCountryExpansionAI') for f in self.files()))

    def test_launcher_uses_manifest_load_order_and_server_mod(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        bat = (self.out / 'start-server.bat').read_text()
        self.assertIn('"-mod=@CF;@DabsFramework;@Expansion-Core;@Expansion-Animations;@Expansion-AI;'
                      '@SnafuWeapons;@TacticalFlava;@HollowCountry"', bat)
        self.assertIn('"-serverMod=@HollowCountryExpansionAI"', bat)
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
        everything = b''.join(p.read_bytes() for p in self.out.rglob('*') if p.is_file())
        self.assertNotIn(b'S3CRET', everything)
        self.assertNotIn(b'PLAYERS', everything)

    def test_readme_names_every_workshop_item_and_the_ports(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        readme = (self.out / 'README.txt').read_text()
        for item in ['1559212036', '2545327648', '2291785308', '2793893086', '2792982069', '2443122116',
                     '2646817942']:
            self.assertIn('workshop_download_item 221100 ' + item, readme)
        self.assertIn('2302', readme)
        self.assertIn('27016', readme)

    def test_manifest_hashes_every_bundled_file(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        manifest = json.loads((self.out / 'bundle-manifest.json').read_text())
        listed = {row['path']: row['sha256'] for row in manifest['files']}
        on_disk = [f for f in self.files() if f != 'bundle-manifest.json']
        self.assertEqual(sorted(listed), on_disk)
        for rel, digest in listed.items():
            self.assertEqual(hashlib.sha256((self.out / rel).read_bytes()).hexdigest(), digest)
        self.assertGreater(manifest['excluded']['profiles'], 0)
        self.assertGreater(manifest['excluded']['mission'], 0)

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
        from tests.unit import test_ce_coverage as fixtures
        from tools.package import ce_coverage
        stock = fixtures.stock_proto()
        put(self.mission, 'mapgroupproto.xml', stock)
        put(self.mission, 'hollow-country/receipt.json', json.dumps({'sources': {
            'mapgroupproto.xml': hashlib.sha256(stock).hexdigest()}}))
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
        self.assertEqual((bundled / 'mapgroupproto.xml').read_bytes(), stock)
        self.assertFalse((bundled / ce_coverage.MANAGED).exists())
        self.assertEqual((self.mission / 'mapgroupproto.xml').read_bytes(), installed)

    def test_validated_coverage_is_applied_to_bundle_without_changing_source(self):
        from tests.unit import test_ce_coverage as fixtures
        stock = fixtures.stock_proto()
        put(self.mission, 'mapgroupproto.xml', stock)
        put(self.mission, 'hollow-country/receipt.json', json.dumps({'sources': {
            'mapgroupproto.xml': hashlib.sha256(stock).hexdigest()}}))
        result = put(self.tmp, 'synthetic-result.json', fixtures.blob(fixtures.result_doc(stock)))
        code, text = self.run_cli('--ce-coverage-result', str(result))
        self.assertEqual(code, 0, text)
        bundled = self.out / 'mpmissions' / self.mission.name
        self.assertNotEqual((bundled / 'mapgroupproto.xml').read_bytes(), stock)
        self.assertEqual((self.mission / 'mapgroupproto.xml').read_bytes(), stock)
        self.assertFalse(any('sampler' in name or 'coverage-delta' in name for name in self.files()))
        self.assertNotIn('left out CE building coverage', text)


    def test_invalid_coverage_result_is_left_out_once_and_no_points_are_bundled(self):
        from tests.unit import test_ce_coverage as fixtures
        stock = fixtures.stock_proto()
        put(self.mission, 'mapgroupproto.xml', stock)
        result = put(self.tmp, 'synthetic-invalid-result.json', '{}')
        code, text = self.run_cli('--ce-coverage-result', str(result))
        self.assertEqual(code, 0, text)
        self.assertEqual(text.count('left out CE building coverage'), 1)
        self.assertEqual((self.out / 'mpmissions' / self.mission.name / 'mapgroupproto.xml').read_bytes(), stock)

    def test_installed_coverage_and_valid_result_ship_only_patched_proto_bytes(self):
        from tests.unit import test_ce_coverage as fixtures
        from tools.package import ce_coverage
        stock = fixtures.stock_proto()
        put(self.mission, 'mapgroupproto.xml', stock)
        put(self.mission, 'hollow-country/receipt.json', json.dumps({'sources': {
            'mapgroupproto.xml': hashlib.sha256(stock).hexdigest()}}))
        result = put(self.tmp, 'synthetic-result.json', fixtures.blob(fixtures.result_doc(stock)))
        delta = self.tmp / 'coverage-delta'
        ce_coverage.write_delta(delta, ce_coverage.generate(result.read_bytes(), self.mission))
        ce_coverage.install(delta, self.mission)
        installed = (self.mission / 'mapgroupproto.xml').read_bytes()
        code, text = self.run_cli('--ce-coverage-result', str(result))
        self.assertEqual(code, 0, text)
        self.assertNotIn('left out CE building coverage', text)
        self.assertEqual((self.out / 'mpmissions' / self.mission.name / 'mapgroupproto.xml').read_bytes(), installed)
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
