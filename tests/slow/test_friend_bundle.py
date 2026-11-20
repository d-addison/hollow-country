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
        put(m, 'cfggameplay.json', '{}')
        put(m, 'storage_1/data/players.db', 'PLAYERS')
        put(m, 'hollow-country/ce/types.xml', '<types/>')
        put(m, 'hollow-country/core.backup', '<economycore/>')
        put(m, 'hollow-country/receipt.json', '{}')
        put(m, 'hollow-country-gameplay/gear/hardscrabble.json', '{}')
        put(m, 'hollow-country-gameplay/cfggameplay.backup', '{}')
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
        source = self.tmp / 'authored'
        shutil.copytree(fb.lts.ROOT / 'mission/hollow-country', source)
        # Synthetic stock mirrors only the selective delta's required sheep fields.
        events = ET.fromstring((source / 'ecology/events.append.xml').read_bytes())
        children = events.find('event/children')
        children.remove(children.find("child[@type='Animal_OvisGmelini']"))
        ET.SubElement(events, 'event', {'name': 'SyntheticUnrelated'})
        stock = {
            'cfgenvironment.xml': b'<env><territories><file path="env/hare_territories.xml"/>'
                b'<file path="env/hare_territories.xml"/></territories></env>\n',
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
        put(self.mission, 'cfgeconomycore.xml', '<economycore><ce folder="hollow-country/ce"><file name="types.xml" type="types"/></ce></economycore>')
        with unittest.mock.patch.object(fb, 'SOURCE', source, create=True):
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

    def test_missing_authored_habitat_event_refuses_even_if_local_mission_has_it(self):
        import shutil
        source = self.tmp / 'authored'
        shutil.copytree(fb.SOURCE, source)
        (source / 'ecology/events.append.xml').unlink()
        put(self.mission, 'hollow-country/ecology/events.append.xml', '<events/>')
        with unittest.mock.patch.object(fb, 'SOURCE', source):
            with self.assertRaisesRegex(fb.Refused, 'HC149_HABITAT_SOURCE_MISSING.*ecology/events.append.xml'):
                fb.build(__import__('argparse').Namespace(out=self.out, mission=self.mission,
                    profiles=self.profiles, mod=self.mod, addon=self.addon,
                    server_cfg=self.cfg, ce_coverage_result=None))
            code, text = self.run_cli()
        self.assertEqual(code, 2, text)
        self.assertIn('HC149_HABITAT_SOURCE_MISSING', text)
        self.assertFalse(self.out.exists())

    def test_authored_habitat_event_replaces_stale_local_copy_in_bundle(self):
        put(self.mission, 'hollow-country/ecology/events.append.xml', '<events><!--synthetic stale--></events>')
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        self.assertEqual((self.out / 'mission-overlay/hollow-country/ecology/events.append.xml').read_bytes(),
                         (fb.SOURCE / 'ecology/events.append.xml').read_bytes())

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

    def test_exported_economy_install_refuses_missing_repo_only_supply_ledger(self):
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
        self.assertFalse((self.out / 'config/loot-dispositions.json').exists())
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

    def test_weapon_pack_deltas_from_third_party_workshop_items_never_ship(self):
        from tools.package import snafu_optional, tactical_flava_optional
        for managed in (snafu_optional.MANAGED, tactical_flava_optional.MANAGED):
            put(self.mission, managed + '/types.xml', '<types/>')
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        leaked = [f for f in self.files()
                  if f.startswith(('mission-overlay/' + snafu_optional.MANAGED, 'mission-overlay/' + tactical_flava_optional.MANAGED))]
        self.assertEqual(leaked, [])

    def test_a_locally_boosted_mission_exports_pre_boost_overlay_bytes_and_ships_the_boost_installer(self):
        # SYNTHETIC rows: the friend's own install doubles the loot once; the export must never carry doubled bytes.
        from tools.package import loot_boost
        put(self.mission, 'cfgeconomycore.xml', '<economycore><ce folder="hollow-country/ce">'
            '<file name="types.xml" type="types"/></ce></economycore>')
        put(self.mission, 'db/types.xml', '<types><type name="SyntheticApple"><nominal>4</nominal><min>2</min>'
            '<category name="food"/></type></types>')
        authored = ('<types>\n<type name="SyntheticSaw"><nominal>3</nominal><min>1</min>'
                    '<category name="tools"/></type>\n</types>\n')
        put(self.mission, 'hollow-country/ce/types.xml', authored)
        put(self.mission, 'db/globals.xml', '<variables><var name="RespawnTypes" type="0" value="12"/></variables>')
        put(self.mission, 'mapgroupproto.xml', '<prototype><group name="SyntheticShed" lootmax="2">'
            '<container name="lootFloor"><point pos="0 0 0"/></container></group></prototype>')
        put(self.mission, 'cfglimitsdefinition.xml', '<lists><categories/><tags/></lists>')
        loot_boost.install(self.mission, 2.0, None)
        self.assertIn(b'<nominal>6</nominal>', (self.mission / 'hollow-country/ce/types.xml').read_bytes())
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        files = self.files()
        self.assertEqual((self.out / 'mission-overlay/hollow-country/ce/types.xml').read_text(), authored)
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
        self.assertEqual(got, sorted('profiles/' + r for r in [
            'ExpansionMod/Loadouts/HollowCountry_Patrol.json', 'ExpansionMod/Settings/AISettings.json',
            'HollowCountry/Ecology/settings.json', 'HollowCountry/Events/settings.json',
            'HollowCountry/Groups/settings.json', 'HollowCountry/Infected/config.json',
            'HollowCountry/expansion-ai-sites.json', 'HollowCountry/expansion-ai-localities.json',
            'HollowCountry/expansion-ai.json',
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
        self.assertIn('"-mod=@CF;@COT;@DabsFramework;@Expansion-Core;@Expansion-Licensed;@Expansion-Vehicles;@Expansion-AI;@Expansion-Navigation;'
                      '@SnafuWeapons;@TacticalFlava;@RaG_Core;@RaG_Immersive_Vehicles;@AmbientAnimals;@SurvivorAnimations;@DayZ-Bicycle;@HollowCountry;@HollowCountryExpansionAI"', bat)
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
        everything = b''.join(p.read_bytes() for p in self.out.rglob('*') if p.is_file())
        self.assertNotIn(b'S3CRET', everything)
        self.assertNotIn(b'PLAYERS', everything)

    def test_readme_names_every_workshop_item_and_the_ports(self):
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        readme = (self.out / 'README.txt').read_text()
        for item in ['1559212036', '1564026768', '2792984722', '3556131153', '3105330157', '2545327648', '2291785308', '2116157322', '2291785437', '3114410963', '2918418331', '2971190303', '2792982069', '2443122116',
                     '2646817942']:
            self.assertIn('workshop_download_item 221100 ' + item, readme)
        self.assertIn('2302', readme)
        self.assertIn('27016', readme)
        self.assertIn('Players subscribe to @HollowCountryExpansionAI when this server uses it', readme)
        self.assertIn('Default dependencies are subscribed from the Workshop, never repacked or included as third-party files.', readme)
        for optional_name in ['Community Framework (CF)', 'COT', 'RaG_Core', 'RaG Immersive Vehicles', 'Expansion Navigation (GPS)', 'Dabs Framework', 'Expansion-Core',
                              'Expansion-AI', 'DayZ-Bicycle',
                              'Ambient Animals Pack', 'Survivor Animations']:
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
        managed = 'hollow-country-overlays'
        put(self.mission, managed + '/receipt.json', '{}')
        put(self.mission, managed + '/gameplay.backup', '{}')
        put(self.mission, managed + '/mapgrouppos.backup', '<map/>')
        put(self.mission, managed + '/objects/military-tents-v1.json', '{"Objects": []}')
        put(self.mission, managed + '/mapgrouppos.additions.xml', '<group/>')
        spawners = ['hollow-country-gear/own.json', managed + '/objects/military-tents-v1.json']
        put(self.mission, 'cfggameplay.json', json.dumps({'WorldsData': {'objectSpawnersArr': spawners}}))
        put(self.mission, 'hollow-country-gameplay/cfggameplay.backup',
            json.dumps({'WorldsData': {'objectSpawnersArr': spawners[:1]}}))
        code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        self.assertEqual([f for f in self.files() if managed in f], [])
        patches = (self.out / 'mission-patches.json').read_text()
        self.assertNotIn(managed, patches)

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
        self.assertEqual(manifest['profile_defaults']['profiles/' + custom]['history'], 'receipt-only')
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

    def test_profile_bytes_vs_repo_source_refuse_line_endings_label_other_drift(self):
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
            code, text = self.run_cli()
        self.assertNotEqual(code, 0)
        self.assertIn('profile_line_endings_differ', text)
        self.assertIn(rel, text)
        self.assertFalse(self.out.exists())

        put(self.profiles, rel, current)
        with unittest.mock.patch('subprocess.run', side_effect=git_result):
            code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        manifest = json.loads((self.out / 'bundle-manifest.json').read_text())
        self.assertEqual(manifest['profile_defaults']['profiles/' + rel]['history'], 'git-log')

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
        with unittest.mock.patch('subprocess.run', side_effect=git_result):
            code, text = self.run_cli()
        self.assertEqual(code, 0, text)
        manifest = json.loads((self.out / 'bundle-manifest.json').read_text())
        row = manifest['profile_defaults']['profiles/' + rel]
        self.assertEqual(row['history'], 'git-log-best-effort')
        self.assertIn('best-effort', text)

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
        self.assertFalse((bundled / 'mapgroupproto.xml').exists())
        self.assertFalse((bundled / ce_coverage.MANAGED).exists())
        self.assertEqual((self.mission / 'mapgroupproto.xml').read_bytes(), installed)

    def test_validated_coverage_stays_local_without_changing_source(self):
        from tests.slow import test_ce_coverage as fixtures
        stock = fixtures.stock_proto()
        put(self.mission, 'mapgroupproto.xml', stock)
        put(self.mission, 'hollow-country/receipt.json', json.dumps({'sources': {
            'mapgroupproto.xml': hashlib.sha256(stock).hexdigest()}}))
        result = put(self.tmp, 'synthetic-result.json', fixtures.blob(fixtures.result_doc(stock)))
        code, text = self.run_cli('--ce-coverage-result', str(result))
        self.assertEqual(code, 0, text)
        bundled = self.out / 'mpmissions' / self.mission.name
        self.assertFalse((bundled / 'mapgroupproto.xml').exists())
        self.assertEqual((self.mission / 'mapgroupproto.xml').read_bytes(), stock)
        self.assertFalse(any('sampler' in name or 'coverage-delta' in name for name in self.files()))
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
        put(self.mission, 'hollow-country/receipt.json', json.dumps({'sources': {
            'mapgroupproto.xml': hashlib.sha256(stock).hexdigest()}}))
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
