"""Guided friend installer: synthetic bundle, server, Workshop content and mission trees only.

Issue #175 / Wave 7 profile upgrade TDD RED (actual failure before implementation):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_friend_install.ProfileUpgradeTests -v
AssertionError: b'{"synthetic_release": 52}' != b'{"EnableX": true}'
Ran 1 test in 0.953s; FAILED (failures=1)
GREEN: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_friend_install.ProfileUpgradeTests test_friend_bundle.FriendBundleTests.test_profile_default_history_records_current_and_earlier_git_bytes -v
Ran 2 tests in 1.986s; OK

Issue #174 TDD RED, before implementing the holdouts migration:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_friend_install.HoldoutProfileTests.test_plan_only_names_each_existing_legacy_file_and_changes_nothing
AssertionError: 'legacy' not found
Ran 1 test in 0.053s; FAILED (failures=1)
GREEN command: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_friend_install test_friend_bundle test_windows_bundle_apply
GREEN: Ran 175 tests in 344.353s; OK

Nothing here runs DayZ, steamcmd, a server or a network call; the Workshop download and the mission
overlay apply are replaced by explicit fakes, and the server-process check is patched. It checks which
files the installer plans, writes, backs up, refuses and leaves alone; it establishes nothing about DayZ
behaviour or a real friend's install.
"""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from tools.setup import friend_bundle as fb
from tools.setup import friend_install as fi
from tools.setup import workshop_sync as ws

REAL_OVERLAY_MAIN = fi.overlays.main
ROOT = Path(__file__).resolve().parents[2]
MISSION = 'dayzOffline.chernarusplus'
SERVER_CFG = '''hostname = "Local";
password = "S3CRET-PASS-71";
passwordAdmin = "S3CRET-ADMIN-71";
verifySignatures = 2;
BattlEye = 1;
thirdPersonView = 0;
serverTimeAcceleration = 1;
class Missions
{
    class DayZ
    {
        template = "dayz.synthetic";
    };
};
'''
SNIPPET = '''// Hollow Country settings for serverDZ.cfg.
thirdPersonView = 2;
disable3rdPerson = 0;
serverTimeAcceleration = 4;
serverNightTimeAcceleration = 8;
enableCfgGameplayFile = 1;

// and in class Missions { class DayZ { ... }; }:
template = "%s";
''' % MISSION


def put(root, rel, data=''):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    return path


def snapshot(root):
    rows = {}
    for path in sorted(Path(root).rglob('*')):
        rel = path.relative_to(root).as_posix()
        rows[rel] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else 'dir'
    return rows


def make_bundle(tmp, addon=True):
    bundle = Path(tmp) / 'bundle'
    manifest = ws.load_manifest()
    items = ws.select(manifest, list(ws.GROUPS))
    if not addon:
        items = [i for i in items if i['folder'] != '@HollowCountryExpansionAI']
    put(bundle, '@HollowCountry/addons/hollowcountry.pbo', b'PBO')
    put(bundle, '@HollowCountry/addons/hollowcountry.pbo.hollowcountry.bisign', b'SIG')
    put(bundle, '@HollowCountry/keys/hollowcountry.bikey', b'KEY')
    put(bundle, '@HollowCountry/mod.cpp', 'name = "Hollow Country";\n')
    put(bundle, '@HollowCountry/meta.cpp', 'publishedid = 3841628320;\nname = "Hollow Country";\n')
    if addon:
        put(bundle, '@HollowCountryExpansionAI/addons/hollowcountryexpansionai.pbo', b'PBO2')
        put(bundle, '@HollowCountryExpansionAI/addons/hollowcountryexpansionai.pbo.hollowcountry.bisign', b'SIG2')
        put(bundle, '@HollowCountryExpansionAI/mod.cpp', 'name = "HCX";\n')
        put(bundle, '@HollowCountryExpansionAI/meta.cpp', 'publishedid = 3841637854;\n')
    put(bundle, 'keys/hollowcountry.bikey', b'KEY')
    put(bundle, 'profiles/HollowCountry/settings.json', '{"EnableX": true}')
    put(bundle, 'profiles/HollowCountry/Events/settings.json', '{"a": 1}')
    put(bundle, 'profiles/ExpansionMod/Settings/AISettings.json', '{"Enabled": 1}')
    put(bundle, 'serverDZ-hollow-country.txt', SNIPPET)
    put(bundle, 'start-server.bat', fb.launcher(items))
    put(bundle, 'README.txt', 'bundle readme')
    put(bundle, 'tools/setup/workshop_mods.json', (ROOT / 'tools/setup/workshop_mods.json').read_bytes())
    put(bundle, 'mission-patches.json', json.dumps({'schema': 1, 'core': [], 'gameplay': []}))
    put(bundle, 'mission-overlay/hollow-country/events/scene-chains.json', '{}')
    # The real layer set and tool, as the exporter ships them (the layers are validated and composed for real).
    put(bundle, 'tools/package/map_overlay.py', (ROOT / 'tools/package/map_overlay.py').read_bytes())
    for path in sorted((ROOT / 'config/map-overlays').rglob('*.json')):
        put(bundle, path.relative_to(ROOT).as_posix(), path.read_bytes())
    write_manifest(bundle)
    return bundle


def write_manifest(bundle):
    bundle = Path(bundle)
    rows = [{'path': p.relative_to(bundle).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(bundle.rglob('*')) if p.is_file() and p.name != 'bundle-manifest.json']
    put(bundle, 'bundle-manifest.json', json.dumps({'schema': 1, 'mission': MISSION, 'files': rows,
                                                    'excluded': {'mission': 0, 'profiles': 0}}))


def make_content(root, items=None):
    """Synthetic downloaded Workshop items (numeric folders), explicit bytes."""
    for item in items or [i for i in ws.select(ws.load_manifest(), list(ws.GROUPS)) if not i['publish']]:
        put(root, '%s/addons/%s.pbo' % (item['id'], item['id']), b'PBO-' + item['id'].encode())
        put(root, '%s/keys/%s.bikey' % (item['id'], item['id']), b'KEY-' + item['id'].encode())
        put(root, '%s/meta.cpp' % item['id'], 'publishedid = %s;\n' % item['id'])
        put(root, '%s/mod.cpp' % item['id'], 'name = "%s";\n' % item['name'])


def fake_overlay(calls):
    def main(argv):
        calls.append(list(argv))
        mission = Path(argv[argv.index('--mission') + 1])
        if argv[0] == 'bundle-plan':
            print('bundle overlay: hollow-country/events/scene-chains.json')
        elif argv[0] == 'bundle-apply':
            put(mission, 'hollow-country-bundle/receipt.json', '{"synthetic": true}')
            print('HC bundle bundle-apply complete; runtime acceptance pending')
        elif argv[0] == 'bundle-rollback':
            (mission / 'hollow-country-bundle/receipt.json').unlink()
        return 0
    return main


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fake_map_overlay(calls):
    """Stands in for tools/package/map_overlay.py main(); layers are loaded and composed by the real functions."""
    def main(argv):
        calls.append(list(argv))

        def option(name):
            return Path(argv[argv.index(name) + 1])

        def refuse(text):
            print('refused: ' + text, file=sys.stderr)
            return 1
        if argv[0] == 'validate':
            if '--source' not in argv:
                return refuse('no --source')
            fi.map_overlay.load_source(option('--source'))
            print('Overlay layers valid: synthetic')
            return 0
        target = option('--target')
        managed = target / fi.map_overlay.MANAGED
        if argv[0] == 'install':
            for name in fi.map_overlay.INPUTS:
                if not (target / name).is_file():
                    return refuse('mission has no %s; the overlays need it (install the gameplay step first)' % name)
            if managed.exists():
                return refuse('overlays already installed or interrupted; inspect/rollback first')
            files = fi.map_overlay.compose(fi.map_overlay.load_source(option('--source')))
            gameplay, pos = (target / 'cfggameplay.json').read_bytes(), (target / 'mapgrouppos.xml').read_bytes()
            after_gameplay, after_pos = gameplay + b'\n', pos + b'\n<!-- overlay rows -->\n'
            receipt = {'schema': 1, 'gameplay': {'before': sha(gameplay), 'after': sha(after_gameplay)},
                       'mapgrouppos': {'before': sha(pos), 'after': sha(after_pos)},
                       'outputs': {name: sha(data) for name, data in sorted(files.items())}}
            put(managed, 'receipt.json', json.dumps(receipt))
            put(managed, 'gameplay.backup', gameplay)
            put(managed, 'mapgrouppos.backup', pos)
            for name, data in files.items():
                put(managed, name, data)
            (target / 'cfggameplay.json').write_bytes(after_gameplay)
            (target / 'mapgrouppos.xml').write_bytes(after_pos)
            print('Overlays installed; runtime acceptance pending')
        elif argv[0] == 'rollback':
            if not managed.is_dir():
                return refuse('nothing to roll back')
            (target / 'cfggameplay.json').write_bytes((managed / 'gameplay.backup').read_bytes())
            (target / 'mapgrouppos.xml').write_bytes((managed / 'mapgrouppos.backup').read_bytes())
            shutil.rmtree(managed)
            print('Overlays rolled back byte-exact')
        return 0
    return main


class InstallerCase(unittest.TestCase):
    def make_server(self, server):
        put(server, 'DayZServer_x64.exe', b'EXE')
        (server / 'keys').mkdir(exist_ok=True)
        mission = server / 'mpmissions' / MISSION
        put(mission, 'cfgeconomycore.xml', '<economycore/>')
        put(mission, 'cfggameplay.json', '{"WorldsData": {"objectSpawnersArr": []}}\n')
        put(mission, 'mapgrouppos.xml', '<map>\n<group name="SyntheticShed" pos="100 5 100"/>\n</map>\n')
        put(mission, 'mapgroupproto.xml', '<prototype><group name="SyntheticShed"/></prototype>\n')
        put(mission, 'init.c', 'void main() {}')
        put(mission, 'storage_1/data/players.db', 'SAVED PLAYERS')
        put(server, 'serverDZ.cfg', SERVER_CFG)
        return mission

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.bundle = make_bundle(self.tmp)
        self.server = self.tmp / 'server'
        self.mission = self.make_server(self.server)
        self.content = self.tmp / 'steamcmd/steamapps/workshop/content/221100'
        make_content(self.content)
        self.overlay_calls = []
        self.map_calls = []
        # Overlay services have their own fixtures; this synthetic mission lacks their CE inputs.
        for patcher in (mock.patch.object(fi, 'do_weapons', return_value='already-done'),
                        mock.patch.object(fi.hc_events, 'install', return_value={}),
                        mock.patch.object(fi.infected_variety, 'install',
                                          side_effect=lambda mission, **kw: put(
                                              mission, fi.infected_variety.MANAGED + '/receipt.json', '{}')),
                        mock.patch.object(fi.infected_variety, 'check', return_value={}),
                        mock.patch.object(fi.infected_variety, 'rollback',
                                          side_effect=lambda mission: shutil.rmtree(
                                              mission / fi.infected_variety.MANAGED, ignore_errors=True)),
                        mock.patch.object(fi.tactical_flava_optional, 'check_weapon_packs', return_value=[]),
                        mock.patch.object(fi.tactical_flava_optional, 'apply_weapon_packs', return_value=[]),
                        mock.patch.object(ws, 'server_running', return_value=False),
                        mock.patch.object(fi.overlays, 'main', side_effect=fake_overlay(self.overlay_calls)),
                        mock.patch.object(fi.map_overlay, 'main', side_effect=fake_map_overlay(self.map_calls))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_cli(self, *extra, answers=None, bundle=None, server=None, root=True, content=True):
        argv = ['--bundle', str(bundle or self.bundle)]
        if content:
            argv += ['--workshop-content', str(self.content)]
        if root:
            argv += ['--server-root', str(server or self.server)]
        out, err = io.StringIO(), io.StringIO()
        prompts = []
        input_fn = None
        if answers is not None:
            def input_fn(prompt):
                prompts.append(prompt)
                return answers(prompt) if callable(answers) else next(answers)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = fi.main(argv + list(extra), out=out, input_fn=input_fn)
        self.prompts = prompts
        return code, out.getvalue(), err.getvalue()

    def apply(self, *extra, **kw):
        return self.run_cli('--apply', '--yes', *extra, **kw)


def status_of(text, step):
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith('Step %d of 11' % step))
    for line in lines[start + 1:]:
        if line.strip().startswith('status:'):
            return line.split(':', 1)[1].strip().split()[0]
        if line.startswith('Step '):
            break
    raise AssertionError('no status for step %d in %s' % (step, text))


class DryRunTests(InstallerCase):
    def test_missing_habitat_stock_surfaces_as_overlay_refusal_without_writes(self):
        # Real bundle planner; only stock and dependency presence are synthetic.
        fi.overlays.main.side_effect = REAL_OVERLAY_MAIN
        put(self.bundle, 'mission-overlay/hollow-country/ecology/habitat-overrides.json', '{"Enabled": true}')
        put(self.bundle, 'mission-overlay/hollow-country/ecology/events.append.xml', '<events/>')
        write_manifest(self.bundle)
        stock = {'cfgenvironment.xml': b'<env><territories/></env>', 'db/events.xml': b'<events/>'}
        for missing in stock:
            with self.subTest(missing=missing):
                for name, data in stock.items():
                    put(self.mission, name, data)
                (self.mission / missing).unlink()
                before = live_snapshot(self.server)
                dry_before = snapshot(self.server)
                code, out, err = self.run_cli()
                self.assertEqual(code, 0, out + err)
                self.assertEqual(status_of(out, 5), 'blocked')
                self.assertIn('bundle-plan refused: refused: HC149_HABITAT_STOCK_MISSING: ' + missing, out)
                self.assertEqual(snapshot(self.server), dry_before)
                code, out, err = self.apply()
                self.assertEqual(code, 2, out + err)
                self.assertIn('HC149_HABITAT_STOCK_MISSING: ' + missing, out + err)
                # Apply retains its rollback audit, while restoring every live byte.
                self.assertEqual(live_snapshot(self.server), before)

    def test_default_is_a_dry_run_that_lists_ten_steps_in_order_and_changes_nothing(self):
        before = snapshot(self.tmp)
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(snapshot(self.tmp), before)
        positions = [out.index('Step %d of 11' % n) for n in range(1, 12)]
        self.assertEqual(positions, sorted(positions))
        for title in ('server folder', 'stopped', 'Workshop', 'mod folders and keys', 'overlay', 'Profiles',
                      'serverDZ.cfg', 'start-server.bat', 'checklist', 'Map overlays'):
            self.assertIn(title, out)
        self.assertIn('dry-run', out)
        self.assertIn('--apply', out)
        self.assertFalse((self.server / fi.RECEIPT).exists())
        self.assertFalse((self.server / fi.BACKUP_DIR).exists())

    def test_the_dry_run_shows_the_bundle_plan_for_the_mission_and_never_applies_it(self):
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, out + err)
        self.assertIn('bundle overlay: hollow-country/events/scene-chains.json', out)
        self.assertEqual([c[0] for c in self.overlay_calls], ['bundle-plan'])
        self.assertIn(str(self.mission), ' '.join(self.overlay_calls[0]))

    def test_dry_run_shows_what_each_step_would_do(self):
        code, out, _ = self.run_cli()
        self.assertEqual(status_of(out, 1), 'ok')
        self.assertEqual(status_of(out, 2), 'ok')
        for step in (3, 4, 5, 6, 7, 8, 9):
            self.assertEqual(status_of(out, step), 'planned', step)
        self.assertIn('@CF', out)
        self.assertIn('thirdPersonView', out)
        self.assertNotIn('S3CRET', out)

    def test_a_running_server_blocks_apply_and_is_reported_by_a_dry_run(self):
        ws.server_running.return_value = True
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, 'a dry run reports; it does not fail')
        self.assertEqual(status_of(out, 2), 'blocked')
        before = snapshot(self.server)
        code, out, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn('server_running', err)
        self.assertEqual(snapshot(self.server), before)

    def test_unknown_server_state_needs_the_flag_or_a_typed_confirmation(self):
        ws.server_running.return_value = None
        before = snapshot(self.server)
        code, out, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn('server_state_unknown', err)
        self.assertEqual(snapshot(self.server), before)
        code, out, err = self.apply('--assume-stopped', '--skip', 'workshop,overlay')
        self.assertEqual(code, 0, out + err)

    def test_the_tool_never_kills_or_controls_processes(self):
        source = (ROOT / 'tools/setup/friend_install.py').read_text(encoding='utf-8')
        for word in ('taskkill', 'terminate(', '.kill(', 'Stop-Process', 'os.kill', 'psutil'):
            self.assertNotIn(word, source)

    def test_dry_run_keeps_unrelated_files_and_empty_directories(self):
        put(self.server, 'unrelated/keep.txt', 'KEEP')
        (self.server / 'empty').mkdir()
        before = snapshot(self.server)
        self.run_cli()
        self.assertEqual(snapshot(self.server), before)

    def test_a_missing_server_folder_refuses_and_names_the_exe(self):
        code, out, err = self.run_cli(server=self.tmp / 'nope')
        self.assertEqual(code, 2)
        self.assertIn('server_root', err)
        empty = self.tmp / 'empty'
        empty.mkdir()
        code, out, err = self.run_cli(server=empty)
        self.assertEqual(code, 2)
        self.assertIn('DayZServer_x64.exe', err)

    def test_the_bundle_folder_itself_is_never_accepted_as_the_server(self):
        put(self.bundle, 'DayZServer_x64.exe', b'EXE')
        code, out, err = self.run_cli(server=self.bundle)
        self.assertEqual(code, 2)
        self.assertIn('server_root', err)

    def test_the_server_root_is_required_without_a_terminal(self):
        code, out, err = self.run_cli(root=False)
        self.assertEqual(code, 2)
        self.assertIn('server_root', err)

    def test_the_server_folder_is_asked_for_in_a_terminal(self):
        answers = iter([str(self.server), ])
        code, out, err = self.run_cli(root=False, answers=answers)
        self.assertEqual(code, 0, out + err)
        self.assertIn('server folder', self.prompts[0].lower())

    def test_a_tampered_bundle_file_refuses_before_anything_is_read(self):
        (self.bundle / '@HollowCountry/addons/hollowcountry.pbo').write_bytes(b'CHANGED')
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertIn('bundle_tampered', err)
        self.assertIn('hollowcountry.pbo', err)

    def test_a_missing_bundle_file_refuses(self):
        (self.bundle / 'profiles/HollowCountry/settings.json').unlink()
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertIn('bundle_tampered', err)

    def test_home_paths_print_as_a_tilde(self):
        home = self.tmp / 'home'
        (home / 'srv').mkdir(parents=True)
        with mock.patch.object(Path, 'home', return_value=home):
            code, out, err = self.run_cli(server=home / 'srv')
        self.assertEqual(code, 2)
        self.assertIn('~', err)
        self.assertNotIn(str(home), out + err)

    def test_credential_options_are_refused_without_echoing_a_value(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            fi.main(['--password', 'hunter2-synthetic'], out=io.StringIO())
        self.assertNotIn('hunter2', err.getvalue())
        self.assertIn('credential', err.getvalue())

    def test_the_source_never_reads_a_secret_from_the_terminal(self):
        source = (ROOT / 'tools/setup/friend_install.py').read_text(encoding='utf-8')
        self.assertNotIn('getpass', source)


class ApplyTests(InstallerCase):
    def test_apply_installs_every_piece_with_backups_and_a_receipt(self):
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        for rel in ('@CF/addons/%s.pbo' % '1559212036', '@HollowCountry/addons/hollowcountry.pbo',
                    '@HollowCountry/meta.cpp', '@HollowCountryExpansionAI/addons/hollowcountryexpansionai.pbo',
                    'keys/hollowcountry.bikey', 'keys/1559212036.bikey',
                    'profiles/HollowCountry/settings.json', 'profiles/ExpansionMod/Settings/AISettings.json',
                    'start-server.bat', fi.RECEIPT, ws.RECEIPT_NAME):
            self.assertTrue((self.server / rel).is_file(), rel)
        self.assertEqual((self.server / 'start-server.bat').read_bytes(), (self.bundle / 'start-server.bat').read_bytes())
        cfg = (self.server / 'serverDZ.cfg').read_text()
        for line in ('thirdPersonView = 2;', 'serverTimeAcceleration = 4;', 'enableCfgGameplayFile = 1;',
                     'template = "%s";' % MISSION, 'password = "S3CRET-PASS-71";'):
            self.assertIn(line, cfg)
        backups = list((self.server / fi.BACKUP_DIR).rglob('serverDZ.cfg'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), SERVER_CFG)
        self.assertEqual([c[0] for c in self.overlay_calls], ['bundle-plan', 'bundle-apply'])
        self.assertTrue((self.mission / 'hollow-country-bundle/receipt.json').is_file())
        receipt = json.loads((self.server / fi.RECEIPT).read_text())
        self.assertEqual(receipt['schema'], 1)
        self.assertIn('start-server.bat', receipt['files'])
        self.assertNotIn('S3CRET', json.dumps(receipt))
        self.assertNotIn('S3CRET', out + err)
        self.assertEqual((self.bundle / fi.REMEMBER_FILE).read_text().strip(), str(self.server))

    def test_saves_and_storage_are_never_touched(self):
        db = self.mission / 'storage_1/data/players.db'
        self.apply()
        self.assertEqual(db.read_text(), 'SAVED PLAYERS')
        self.assertTrue(all(p.exists() for p in [db, self.mission / 'init.c']))

    def test_a_second_apply_changes_nothing_and_says_everything_is_done(self):
        self.assertEqual(self.apply()[0], 0)
        before = snapshot(self.tmp)
        calls = len(self.overlay_calls)
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(snapshot(self.tmp), before)
        self.assertEqual(len(self.overlay_calls), calls)
        for step in (3, 4, 5, 6, 7, 8, 9):
            self.assertEqual(status_of(out, step), 'already-done', step)

    def test_a_modified_installed_file_is_drift_and_refuses_before_any_change(self):
        self.apply()
        launcher = self.server / 'start-server.bat'
        launcher.write_bytes(launcher.read_bytes().replace(b'"-mod=@CF;', b'"-mod='))
        before = snapshot(self.server)
        code, out, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn('drift', err)
        self.assertIn('start-server.bat', err)
        self.assertEqual(snapshot(self.server), before)

    def test_a_hand_edited_signed_pbo_is_drift_too(self):
        self.apply()
        (self.server / '@HollowCountry/addons/hollowcountry.pbo').write_bytes(b'EDITED')
        before = snapshot(self.server)
        code, out, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn('drift', err)
        self.assertIn('hollowcountry.pbo', err)
        self.assertEqual(snapshot(self.server), before)

    def test_a_server_rewritten_profile_file_is_kept_and_reported_not_overwritten(self):
        self.apply()
        edited = self.server / 'profiles/ExpansionMod/Settings/AISettings.json'
        edited.write_text('{"Enabled": 1, "Edited": true}')
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(edited.read_text(), '{"Enabled": 1, "Edited": true}')
        self.assertIn('kept', out)
        self.assertIn('AISettings.json', out)

    def test_an_older_installed_version_is_upgraded_with_a_backup(self):
        self.apply()
        newer = make_bundle(self.tmp / 'v2')
        put(newer, '@HollowCountry/addons/hollowcountry.pbo', b'PBO-NEW')
        rows = json.loads((newer / 'bundle-manifest.json').read_text())
        for row in rows['files']:
            row['sha256'] = hashlib.sha256((newer / row['path']).read_bytes()).hexdigest()
        (newer / 'bundle-manifest.json').write_text(json.dumps(rows))
        code, out, err = self.apply(bundle=newer)
        self.assertEqual(code, 0, out + err)
        self.assertEqual((self.server / '@HollowCountry/addons/hollowcountry.pbo').read_bytes(), b'PBO-NEW')
        backed_up = [p for p in (self.server / fi.BACKUP_DIR).rglob('hollowcountry.pbo')]
        self.assertEqual([p.read_bytes() for p in backed_up], [b'PBO'])

    def test_a_different_pre_existing_file_needs_confirmation_then_is_backed_up(self):
        own = b'start x -port=2999 "-mod=@Mine" -dologs\r\n'
        put(self.server, 'start-server.bat', own)
        code, out, err = self.run_cli('--apply', '--skip', 'workshop,overlay')
        self.assertEqual(code, 2)
        self.assertIn('confirmation_required', err)
        self.assertEqual((self.server / 'start-server.bat').read_bytes(), own)
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        backups = list((self.server / fi.BACKUP_DIR).rglob('start-server.bat'))
        self.assertEqual([p.read_bytes() for p in backups], [own])
        merged = (self.server / 'start-server.bat').read_bytes()
        self.assertIn(b'-port=2999', merged)  # merged into the operator's file, not replaced
        self.assertTrue(merged.decode().count('@Mine'), merged)

    def test_a_stale_pbo_in_our_mod_folder_is_moved_to_the_backup_not_deleted(self):
        put(self.server, '@HollowCountry/addons/oldname.pbo', b'STALE')
        put(self.server, '@HollowCountry/addons/oldname.pbo.hollowcountry.bisign', b'STALESIG')
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertFalse((self.server / '@HollowCountry/addons/oldname.pbo').exists())
        moved = list((self.server / fi.BACKUP_DIR).rglob('oldname.pbo'))
        self.assertEqual([p.read_bytes() for p in moved], [b'STALE'])

    def test_apply_refuses_when_the_two_inputs_would_overwrite_a_symlink(self):
        if not hasattr(os, 'symlink'):
            self.skipTest('no symlinks')
        target = self.tmp / 'elsewhere'
        target.mkdir()
        try:
            os.symlink(target, self.server / '@HollowCountry')
        except OSError:
            self.skipTest('symlinks not permitted')
        code, out, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn('symlink', err)

    def test_without_the_addon_nothing_about_it_is_installed_or_expected(self):
        bundle = make_bundle(self.tmp / 'noaddon', addon=False)
        code, out, err = self.apply(bundle=bundle)
        self.assertEqual(code, 0, out + err)
        self.assertFalse((self.server / '@HollowCountryExpansionAI').exists())
        code, out, err = self.run_cli('--check', bundle=bundle)
        self.assertEqual(code, 0, out + err)

    def test_skip_names_leave_those_steps_alone(self):
        code, out, err = self.apply('--skip', 'workshop,overlay,overlays-map,cfg')
        self.assertEqual(code, 0, out + err)
        for step in (3, 5, 6, 9):
            self.assertEqual(status_of(out, step), 'skipped', step)
        self.assertFalse((self.server / '@CF').exists())
        self.assertEqual((self.server / 'serverDZ.cfg').read_text(), SERVER_CFG)
        self.assertEqual(self.overlay_calls, [])
        self.assertEqual(self.map_calls, [])

    def test_an_unknown_skip_name_is_refused(self):
        code, out, err = self.run_cli('--skip', 'nonsense')
        self.assertEqual(code, 2)
        self.assertIn('nonsense', err)

    def test_terminal_prompts_can_skip_one_step_and_continue(self):
        def answer(prompt):
            return 's' if 'Mission overlay' in prompt else 'y'
        code, out, err = self.run_cli('--apply', answers=answer)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(status_of(out, 5), 'skipped')
        self.assertEqual(status_of(out, 4), 'done')
        self.assertFalse((self.mission / 'hollow-country-bundle/receipt.json').exists())

    def test_a_terminal_dry_run_offers_to_apply_and_does_so_on_yes(self):
        code, out, err = self.run_cli(answers=lambda prompt: 'y', root=True)
        self.assertEqual(code, 0, out + err)
        self.assertTrue((self.server / fi.RECEIPT).is_file())
        self.assertTrue(any('now' in p.lower() for p in self.prompts))

    def test_a_terminal_dry_run_does_nothing_on_no(self):
        before = snapshot(self.tmp)
        code, out, err = self.run_cli(answers=lambda prompt: 'n')
        self.assertEqual(code, 0)
        self.assertEqual(snapshot(self.tmp), before)

    def test_plan_only_never_offers_to_apply(self):
        code, out, err = self.run_cli('--plan-only', answers=lambda prompt: self.fail('prompted: ' + prompt))
        self.assertEqual(code, 0, out + err)

    def test_the_overlay_failure_rolls_back_earlier_work(self):
        before = live_snapshot(self.server)
        def failing(argv):
            if argv[0] == 'bundle-apply':
                print('refused: mission core merge conflict: x', file=__import__('sys').stderr)
                return 2
            return 0
        fi.overlays.main.side_effect = failing
        code, out, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn('overlay', err)
        self.assertIn('mission core merge conflict', err)
        self.assertEqual(live_snapshot(self.server), before)
        self.assertIn('rolled back: the server is as it was before this run', err)

    def test_a_changed_bundle_rolls_the_old_overlay_back_first_when_confirmed(self):
        self.apply()
        newer = make_bundle(self.tmp / 'v2')
        put(newer, 'mission-overlay/hollow-country/events/extra.json', '{}')
        rows = json.loads((newer / 'bundle-manifest.json').read_text())
        rows['files'].append({'path': 'mission-overlay/hollow-country/events/extra.json',
                              'sha256': hashlib.sha256(b'{}').hexdigest()})
        (newer / 'bundle-manifest.json').write_text(json.dumps(rows))
        self.overlay_calls.clear()
        code, out, err = self.apply(bundle=newer)
        self.assertEqual(code, 0, out + err)
        self.assertEqual([c[0] for c in self.overlay_calls], ['bundle-rollback', 'bundle-plan', 'bundle-apply'])

    def test_the_map_overlay_is_rolled_back_before_the_mission_overlay_it_sits_on_and_reinstalled(self):
        self.apply()
        newer = make_bundle(self.tmp / 'v2')
        put(newer, 'mission-overlay/hollow-country/events/extra.json', '{}')
        write_manifest(newer)
        self.overlay_calls.clear()
        self.map_calls.clear()
        code, out, err = self.apply(bundle=newer)
        self.assertEqual(code, 0, out + err)
        self.assertEqual([c[0] for c in self.overlay_calls], ['bundle-rollback', 'bundle-plan', 'bundle-apply'])
        self.assertEqual([c[0] for c in self.map_calls], ['rollback', 'validate', 'install'])
        self.assertTrue((self.mission / fi.map_overlay.MANAGED / 'receipt.json').is_file())


class WorkshopStepTests(InstallerCase):
    def setUp(self):
        super().setUp()
        self.fetches = []
        for patcher in (mock.patch.object(fi, 'fetch_workshop', side_effect=self.fake_fetch),
                        mock.patch.object(fi.shutil, 'which', return_value=None)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def fake_fetch(self, argv, say):
        self.fetches.append(list(argv))
        make_content(self.content)
        return 0

    def empty_content(self):
        shutil.rmtree(self.content)
        self.steamcmd = put(self.tmp, 'steamcmd/steamcmd.exe', b'EXE')

    def test_the_friend_types_their_own_login_name_and_no_secret_is_collected(self):
        self.empty_content()
        code, out, err = self.run_cli('--apply', '--yes', '--steamcmd', str(self.steamcmd),
                                      answers=lambda prompt: 'friendlogin')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len(self.fetches), 1)
        argv = self.fetches[0]
        self.assertEqual(argv[argv.index('--steam-user') + 1], 'friendlogin')
        for token in argv:
            self.assertNotIn('pass', token.lower())
        asked = [p for p in self.prompts if 'steam' in p.lower()]
        self.assertEqual(len(asked), 1)
        # The only mention of a password is the warning that steamcmd asks for it itself.
        for prompt in self.prompts:
            if 'password' in prompt.lower():
                self.assertIn('itself', prompt.lower())
                self.assertIn('login name only', prompt.lower())
        self.assertTrue((self.server / '@CF/addons/1559212036.pbo').is_file())

    def test_a_login_name_is_required_when_a_download_is_needed_and_there_is_no_terminal(self):
        self.empty_content()
        before = snapshot(self.server)
        code, out, err = self.apply('--steamcmd', str(self.steamcmd))
        self.assertEqual(code, 2)
        self.assertIn('steam_user_required', err)
        self.assertEqual(self.fetches, [])
        self.assertEqual(snapshot(self.server), before)

    def test_a_missing_steamcmd_is_explained_not_guessed(self):
        self.empty_content()
        code, out, err = self.apply('--steam-user', 'friendlogin')
        self.assertEqual(code, 2)
        self.assertIn('steamcmd_required', err)

    def test_our_own_workshop_items_are_never_fetched_here(self):
        self.empty_content()
        self.run_cli('--apply', '--yes', '--steamcmd', str(self.steamcmd), '--steam-user', 'friendlogin')
        argv = ' '.join(self.fetches[0])
        manifest_path = Path(self.fetches[0][self.fetches[0].index('--manifest') + 1]) if '--manifest' in argv else None
        self.assertIsNotNone(manifest_path)
        # the temporary manifest is gone after the run; the call carried only third-party ids
        self.assertNotIn('3841628320', argv)

    def test_present_content_means_no_download_and_the_step_is_done(self):
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.fetches, [])
        self.assertEqual(status_of(out, 3), 'done')

    def test_already_installed_third_party_folders_are_left_untouched(self):
        put(self.server, '@CF/addons/own-version.pbo', b'THEIRS')
        put(self.server, '@CF/keys/own.bikey', b'THEIRKEY')
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertEqual((self.server / '@CF/addons/own-version.pbo').read_bytes(), b'THEIRS')
        self.assertFalse((self.server / '@CF/addons/1559212036.pbo').exists())

    def test_missing_default_packs_block_the_overlay_step_with_a_clear_reason(self):
        shutil.rmtree(self.content / '3114410963')
        code, out, err = self.apply('--skip', 'workshop')
        self.assertEqual(code, 2)
        self.assertIn('3114410963', err)
        self.assertEqual(self.overlay_calls, [])

    def test_the_prompt_says_to_type_the_login_name_only_and_never_the_password(self):
        self.empty_content()
        self.run_cli('--apply', '--yes', '--steamcmd', str(self.steamcmd), answers=lambda prompt: 'friendlogin')
        prompt = next(p for p in self.prompts if 'steam' in p.lower())
        self.assertIn('login name only', prompt.lower())
        self.assertIn('password', prompt.lower())
        self.assertIn('itself', prompt.lower())

    def test_a_typed_value_with_spaces_is_refused_and_never_echoed(self):
        self.empty_content()
        typed = 'my secret pass phrase'
        before = snapshot(self.server)
        code, out, err = self.run_cli('--apply', '--yes', '--steamcmd', str(self.steamcmd), answers=lambda prompt: typed)
        self.assertEqual(code, 2)
        self.assertIn('steam_user_invalid', err)
        self.assertIn('login name', err)
        self.assertNotIn('secret', out + err)
        self.assertEqual(self.fetches, [])
        self.assertEqual(snapshot(self.server), before)

    def test_a_login_option_with_spaces_is_refused_the_same_way(self):
        self.empty_content()
        code, out, err = self.apply('--steamcmd', str(self.steamcmd), '--steam-user', 'two words')
        self.assertEqual(code, 2)
        self.assertIn('steam_user_invalid', err)
        self.assertNotIn('two words', out + err)
        self.assertEqual(self.fetches, [])


class RetiredDependencyTests(InstallerCase):
    """An older release installed items the manifest has since retired; the upgrade must still work."""

    def setUp(self):
        super().setUp()
        self.retired = ws.load_manifest()['retired']
        self.assertTrue(self.retired)

    def seed_old_install(self):
        """Apply the current bundle, then add what an older install recorded for the retired items."""
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        path = self.server / ws.RECEIPT_NAME
        receipt = json.loads(path.read_text())
        files = {e['path']: e for e in receipt['files']}
        dirs = set(receipt['dirs'])
        self.old_paths = []
        for item in self.retired:
            top, name = item['folder'], 'old-' + item['id']
            dirs |= {top, top + '/addons', top + '/keys'}
            for rel, data in ((top + '/addons/%s.pbo' % name, b'OLDPBO-' + item['id'].encode()),
                              (top + '/keys/%s.bikey' % name, b'OLDKEY-' + item['id'].encode()),
                              (top + '/meta.cpp', b'publishedid = %s;\n' % item['id'].encode()),
                              ('keys/%s.bikey' % name, b'OLDKEY-' + item['id'].encode())):
                put(self.server, rel, data)
                files[rel] = {'path': rel, 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data),
                              'item': item['id']}
                self.old_paths.append(rel)
        path.write_bytes(ws.json_bytes(ws.receipt_data(files, dirs)))
        return receipt

    def test_an_older_receipt_naming_retired_folders_does_not_block_the_upgrade(self):
        before = self.seed_old_install()
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, out + err)
        self.assertNotIn('workshop_receipt', err)
        self.assertEqual(status_of(out, 3), 'planned')
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        for rel in self.old_paths:
            self.assertFalse((self.server / rel).exists(), rel)
        for item in self.retired:
            self.assertFalse((self.server / item['folder']).exists(), item['folder'])
        after = json.loads((self.server / ws.RECEIPT_NAME).read_text())
        self.assertEqual(after, before)
        self.assertTrue((self.server / '@CF/addons/1559212036.pbo').is_file())

    def test_a_second_apply_changes_nothing(self):
        self.seed_old_install()
        self.assertEqual(self.apply()[0], 0)
        before = snapshot(self.server)
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(status_of(out, 3), 'already-done')
        self.assertEqual(snapshot(self.server), before)

    def test_a_retired_file_changed_since_install_is_left_and_reported(self):
        self.seed_old_install()
        kept = '%s/addons/old-%s.pbo' % (self.retired[0]['folder'], self.retired[0]['id'])
        (self.server / kept).write_bytes(b'EDITED BY HAND')
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertEqual((self.server / kept).read_bytes(), b'EDITED BY HAND')
        self.assertIn(kept, out)
        receipt = json.loads((self.server / ws.RECEIPT_NAME).read_text())
        self.assertNotIn(kept, {e['path'] for e in receipt['files']})
        before = snapshot(self.server)
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual(snapshot(self.server), before)

    def test_rollback_with_an_older_receipt_removes_retired_files_and_keys(self):
        self.seed_old_install()
        code = ws.main(['rollback', '--server-root', str(self.server), '--assume-stopped'], out=io.StringIO())
        self.assertEqual(code, 0)
        for rel in self.old_paths:
            self.assertFalse((self.server / rel).exists(), rel)
        self.assertFalse((self.server / ws.RECEIPT_NAME).exists())


class SteamcmdResolutionTests(InstallerCase):
    """A fresh machine has no download folder yet: steamcmd must be resolved, remembered and passed on."""

    def setUp(self):
        super().setUp()
        shutil.rmtree(self.content)
        self.steamcmd_dir = self.tmp / 'steamcmd'
        self.steamcmd = put(self.steamcmd_dir, 'steamcmd.exe', b'EXE')
        self.commands = []
        for patcher in (mock.patch.object(fi.shutil, 'which', return_value=None),
                        mock.patch.object(ws.subprocess, 'run', side_effect=self.fake_run)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def fake_run(self, command, check=False):
        """Stands in for steamcmd: puts the items where steamcmd would (force_install_dir, else its own folder)."""
        self.commands.append(list(command))
        home = Path(command[command.index('+force_install_dir') + 1]) if '+force_install_dir' in command \
            else Path(command[0]).parent
        make_content(home / 'steamapps/workshop/content/221100')
        return mock.Mock(returncode=0)

    def test_steamcmd_from_the_option_is_passed_on_with_its_own_folder_as_the_install_dir(self):
        code, out, err = self.run_cli('--apply', '--yes', '--steamcmd', str(self.steamcmd), '--steam-user', 'friendlogin',
                                      content=False)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len(self.commands), 1)
        command = self.commands[0]
        self.assertEqual(command[0], str(self.steamcmd))
        self.assertEqual(command[command.index('+force_install_dir') + 1], str(self.steamcmd_dir))
        self.assertEqual(command[command.index('+login') + 1], 'friendlogin')
        self.assertTrue((self.server / '@CF/addons/1559212036.pbo').is_file())

    def test_steamcmd_found_on_the_path_is_used_without_the_option(self):
        fi.shutil.which.return_value = str(self.steamcmd)
        code, out, err = self.run_cli('--apply', '--yes', '--steam-user', 'friendlogin', content=False)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.commands[0][0], str(self.steamcmd))
        self.assertIn('+force_install_dir', self.commands[0])
        self.assertTrue((self.server / '@CF/addons/1559212036.pbo').is_file())

    def test_an_unknown_steamcmd_is_asked_for_then_remembered_for_the_next_run(self):
        def answer(prompt):
            return str(self.steamcmd_dir) if 'steamcmd' in prompt.lower() and 'path' in prompt.lower() else 'friendlogin'
        code, out, err = self.run_cli('--apply', '--yes', answers=answer, content=False)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.commands[0][0], str(self.steamcmd))
        self.assertEqual((self.bundle / fi.REMEMBER_STEAMCMD).read_text().strip(), str(self.steamcmd))
        # a second, empty server on the same machine: no path question, the remembered one is used
        shutil.rmtree(self.steamcmd_dir / 'steamapps')
        second = self.tmp / 'server2'
        self.make_server(second)

        def only_login(prompt):
            self.assertNotIn('path', prompt.lower(), 'steamcmd was asked for again: ' + prompt)
            return 'friendlogin'
        code, out, err = self.run_cli('--apply', '--yes', answers=only_login, server=second, content=False)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.commands[1][0], str(self.steamcmd))

    def test_a_typed_path_that_is_not_steamcmd_refuses_before_anything_is_written(self):
        before = snapshot(self.server)
        code, out, err = self.run_cli('--apply', '--yes', answers=lambda prompt: str(self.tmp / 'nowhere'), content=False)
        self.assertEqual(code, 2)
        self.assertIn('steamcmd_required', err)
        self.assertEqual(self.commands, [])
        self.assertEqual(snapshot(self.server), before)
        self.assertFalse((self.bundle / fi.REMEMBER_STEAMCMD).exists())

    def test_without_a_terminal_the_missing_steamcmd_is_named_with_the_option_to_pass(self):
        code, out, err = self.run_cli('--apply', '--yes', '--steam-user', 'friendlogin', content=False)
        self.assertEqual(code, 2)
        self.assertIn('steamcmd_required', err)
        self.assertIn('--steamcmd', err)
        self.assertEqual(self.commands, [])

    def test_a_plan_never_asks_and_says_where_the_download_would_come_from(self):
        code, out, err = self.run_cli('--plan-only', answers=lambda prompt: self.fail('prompted: ' + prompt), content=False)
        self.assertEqual(code, 0, out + err)
        self.assertIn('steamcmd', out)
        self.assertFalse((self.bundle / fi.REMEMBER_STEAMCMD).exists())


class MapOverlayStepTests(InstallerCase):
    def managed(self):
        return self.mission / fi.map_overlay.MANAGED

    def layer_ids(self):
        return [layer['id'] for layer in fi.map_overlay.load_source(self.bundle / 'config/map-overlays').layers]

    def newer_bundle(self, drop_last_layer=True):
        newer = make_bundle(self.tmp / 'v2')
        path = newer / 'config/map-overlays/profile.json'
        profile = json.loads(path.read_text())
        if drop_last_layer:
            profile['enabled'] = profile['enabled'][:-1]
        path.write_text(json.dumps(profile, indent=2))
        write_manifest(newer)
        return newer

    def test_a_dry_run_validates_and_lists_the_layers_but_installs_nothing(self):
        before = snapshot(self.tmp)
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(snapshot(self.tmp), before)
        self.assertEqual(status_of(out, 6), 'planned')
        self.assertEqual([c[0] for c in self.map_calls], ['validate'])
        for ident in self.layer_ids():
            self.assertIn(ident, out)
        self.assertIn('server must be stopped', out)

    def test_apply_validates_then_installs_after_the_mission_overlay_and_marks_acceptance_pending(self):
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(status_of(out, 6), 'done')
        self.assertLess(out.index('Step 5 of 11'), out.index('Step 6 of 11'))
        self.assertEqual([c[0] for c in self.map_calls], ['validate', 'install'])
        validate, install = self.map_calls
        source = str(self.bundle / 'config/map-overlays')
        self.assertEqual(validate[validate.index('--source') + 1], source)
        self.assertEqual(validate[validate.index('--mission') + 1], str(self.mission))
        self.assertEqual(validate[validate.index('--server-root') + 1], str(self.server))
        self.assertEqual(install[install.index('--source') + 1], source)
        self.assertEqual(install[install.index('--target') + 1], str(self.mission))
        self.assertTrue((self.managed() / 'receipt.json').is_file())
        self.assertIn('runtime acceptance pending', out.lower())
        self.assertIn('map_overlay.py rollback --target', out)

    def test_a_second_apply_finds_an_intact_matching_receipt_and_changes_nothing(self):
        self.apply()
        before = snapshot(self.tmp)
        self.map_calls.clear()
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(status_of(out, 6), 'already-done')
        self.assertEqual(self.map_calls, [])
        self.assertEqual(snapshot(self.tmp), before)

    def test_an_overlay_installed_by_hand_for_the_same_layers_counts_as_installed(self):
        source = str(self.bundle / 'config/map-overlays')
        self.assertEqual(fi.map_overlay.main(['install', '--source', source, '--target', str(self.mission)]), 0)
        self.map_calls.clear()
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(status_of(out, 6), 'already-done')
        self.assertEqual(self.map_calls, [])

    def test_a_different_layer_set_is_rolled_back_first_and_only_after_confirmation(self):
        self.apply()
        newer = self.newer_bundle()
        self.map_calls.clear()
        before = snapshot(self.server)
        code, out, err = self.run_cli('--apply', bundle=newer)
        self.assertEqual(code, 2)
        self.assertIn('confirmation_required', err)
        self.assertIn('map overlay', err)
        self.assertEqual(snapshot(self.server), before)
        self.assertEqual(self.map_calls, [])
        code, out, err = self.apply(bundle=newer)
        self.assertEqual(code, 0, out + err)
        self.assertEqual([c[0] for c in self.map_calls], ['validate', 'rollback', 'validate', 'install'])
        receipt = json.loads((self.managed() / 'receipt.json').read_text())
        wanted = fi.map_overlay.compose(fi.map_overlay.load_source(newer / 'config/map-overlays'))
        self.assertEqual(receipt['outputs'], {n: sha(d) for n, d in sorted(wanted.items())})

    def test_a_damaged_receipt_blocks_with_the_rollback_command_and_installs_nothing(self):
        self.apply()
        (self.managed() / 'receipt.json').write_text('{ not json')
        self.map_calls.clear()
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, 'a dry run reports; it does not fail')
        self.assertEqual(status_of(out, 6), 'blocked')
        code, out, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn('overlays-map', err)
        self.assertIn('damaged', err)
        self.assertIn('map_overlay.py rollback --target', err)
        self.assertEqual([c[0] for c in self.map_calls if c[0] in ('install', 'rollback')], [])

    def test_a_hand_edited_gameplay_file_is_damage_not_a_quiet_reinstall(self):
        self.apply()
        (self.mission / 'cfggameplay.json').write_text('{"edited": true}')
        self.map_calls.clear()
        code, out, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn('cfggameplay.json', err)
        self.assertEqual([c[0] for c in self.map_calls if c[0] in ('install', 'rollback')], [])
        self.assertEqual((self.mission / 'cfggameplay.json').read_text(), '{"edited": true}')

    def test_a_tampered_overlay_output_is_damage(self):
        self.apply()
        victim = next(p for p in (self.managed() / 'objects').iterdir())
        victim.write_bytes(b'{}')
        code, out, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn('damaged', err)

    def test_skipping_leaves_the_mission_alone(self):
        code, out, err = self.apply('--skip', 'overlays-map')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(status_of(out, 6), 'skipped')
        self.assertEqual(self.map_calls, [])
        self.assertFalse(self.managed().exists())
        self.assertEqual((self.mission / 'cfggameplay.json').read_text(), '{"WorldsData": {"objectSpawnersArr": []}}\n')

    def test_a_running_server_stops_the_install_before_the_map_overlay(self):
        ws.server_running.return_value = True
        code, out, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn('server_running', err)
        self.assertEqual(self.map_calls, [])

    def test_a_dry_run_before_the_mission_overlay_exists_waits_for_it_instead_of_failing(self):
        (self.mission / 'cfggameplay.json').unlink()
        (self.mission / 'mapgrouppos.xml').unlink()
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(status_of(out, 6), 'planned')
        self.assertIn('after the mission overlay', out)
        self.assertEqual([c[0] for c in self.map_calls], ['validate'])
        self.assertNotIn('--mission', self.map_calls[0])

    def test_missing_mission_inputs_after_the_mission_overlay_refuse_with_the_tool_reason(self):
        (self.mission / 'mapgrouppos.xml').unlink()
        code, out, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn('mapgrouppos.xml', err)
        self.assertFalse(self.managed().exists())

    def test_a_validation_refusal_is_shown_and_blocks_the_install(self):
        def refusing(argv):
            if argv[0] == 'validate':
                print('refused: layer x is closer than 8 m to vanilla group y', file=sys.stderr)
                return 1
            return 0
        fi.map_overlay.main.side_effect = refusing
        code, out, err = self.run_cli()
        self.assertEqual(code, 0)
        self.assertEqual(status_of(out, 6), 'blocked')
        self.assertIn('closer than 8 m', out)
        code, out, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn('closer than 8 m', err)
        self.assertFalse(self.managed().exists())

    def test_map_failure_keeps_storage_and_unrelated_files(self):
        before = live_snapshot(self.server)
        fi.map_overlay.main.side_effect = lambda argv: 1
        self.assertEqual(self.apply()[0], 2)
        self.assertEqual(live_snapshot(self.server), before)


class EarlierMapOverlayKeptTests(InstallerCase):
    """#336: replacing the mission overlay rolls back the map overlay sitting on it (they patch the same
    cfggameplay.json, so the mission rollback refuses while it is in place). A run never leaves the server with
    fewer installed overlay layers than it started with unless that run installs the replacement."""

    def setUp(self):
        super().setUp()
        self.assertEqual(self.apply()[0], 0)
        self.newer = make_bundle(self.tmp / 'v2')
        put(self.newer, 'mission-overlay/hollow-country/events/extra.json', '{}')
        write_manifest(self.newer)
        self.managed = self.mission / fi.map_overlay.MANAGED
        self.installed = snapshot(self.mission)
        self.overlay_calls.clear()
        self.map_calls.clear()

    def test_skipping_the_map_step_over_an_earlier_map_overlay_refuses_before_any_change(self):
        before = snapshot(self.server)
        code, out, err = self.apply('--skip', 'mods,overlays-map', bundle=self.newer)
        self.assertEqual(code, 2, out + err)
        self.assertIn('overlay_layers', err)
        self.assertIn('map overlay', err)
        self.assertIn('step 6 (map overlays) is skipped', err)
        self.assertIn('before anything is changed', err)
        self.assertEqual(snapshot(self.server), before)
        self.assertEqual(snapshot(self.mission), self.installed)
        self.assertEqual(self.overlay_calls, [])
        self.assertEqual([c[0] for c in self.map_calls if c[0] in ('install', 'rollback')], [])
        self.assertTrue((self.managed / 'receipt.json').is_file())

    def test_the_dry_run_blocks_that_skip_and_says_why(self):
        before = snapshot(self.server)
        code, out, err = self.run_cli('--skip', 'mods,overlays-map', bundle=self.newer)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(status_of(out, 5), 'blocked')
        self.assertIn('map overlay (%s): cannot be kept: step 6 (map overlays) is skipped' % fi.map_overlay.MANAGED, out)
        self.assertIn('the installed map overlay (%s) stays as it is, byte for byte' % fi.map_overlay.MANAGED, out)
        self.assertEqual(snapshot(self.server), before)

    def test_the_dry_run_names_which_layers_go_and_which_are_replaced(self):
        before = snapshot(self.server)
        code, out, err = self.run_cli(bundle=self.newer)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(snapshot(self.server), before)
        self.assertEqual(status_of(out, 5), 'planned')
        self.assertIn('map overlay (%s): rolled back here, installed again by the overlays-map step' % fi.map_overlay.MANAGED, out)
        # The installed layer set equals the bundle's, but step 5 removes it: step 6 is not "already done".
        self.assertEqual(status_of(out, 6), 'planned')
        self.assertIn('step 5 rolls the installed map overlay back first', out)

    def test_an_unchanged_mission_overlay_leaves_the_map_overlay_alone_even_when_the_map_step_is_skipped(self):
        code, out, err = self.run_cli('--skip', 'overlays-map')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(status_of(out, 5), 'already-done')
        self.assertIn('layers on top of it stay installed, byte for byte: %s' % fi.map_overlay.MANAGED, out)
        code, out, err = self.apply('--skip', 'overlays-map')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(snapshot(self.mission), self.installed)
        self.assertEqual(self.map_calls, [])

    def test_a_refused_map_step_undoes_the_whole_run_and_the_earlier_overlay_is_intact(self):
        def refusing_after_rollback(argv):
            if argv[0] == 'validate' and '--mission' in argv and not self.managed.exists():
                print('refused: flat: military-zones-v2/s016-p03: height 257.0 differs from the median 255.9',
                      file=sys.stderr)
                return 1
            return REAL_FAKE_MAP(argv)
        REAL_FAKE_MAP = fake_map_overlay(self.map_calls)
        fi.map_overlay.main.side_effect = refusing_after_rollback
        before = snapshot(self.server)
        code, out, err = self.apply(bundle=self.newer)
        self.assertEqual(code, 2, out + err)
        self.assertIn('flat: military-zones-v2/s016-p03', err)
        self.assertIn('rolled back: the server is as it was before this run', err)
        self.assertEqual([c[0] for c in self.map_calls].count('rollback'), 1)
        # Receipted files, the objectSpawnersArr patch and the overlays folder are byte for byte as they were.
        self.assertEqual(snapshot(self.mission), self.installed)
        self.assertTrue((self.managed / 'receipt.json').is_file())
        self.assertEqual(live_snapshot(self.server), {k: v for k, v in before.items()
                                                      if k != fi.BACKUP_DIR and not k.startswith(fi.BACKUP_DIR + '/')})

    def test_skipping_the_map_step_at_the_prompt_after_step_5_replaced_the_overlay_undoes_the_run(self):
        def answers(prompt):
            if 'Map overlays' in prompt:
                return 's'
            return 'y'
        code, out, err = self.run_cli('--apply', bundle=self.newer, answers=answers)
        self.assertEqual(code, 2, out + err)
        self.assertIn('overlay_layers', err)
        self.assertIn('rolled back: the server is as it was before this run', err)
        self.assertEqual(snapshot(self.mission), self.installed)
        self.assertEqual(self.prompts[-1].split(':')[0], 'Map overlays (layers)')


class ManifestAndConfigDriftTests(InstallerCase):
    def test_files_not_listed_in_the_manifest_are_never_installed(self):
        put(self.bundle, '@HollowCountry/addons/planted.pbo', b'PLANTED')
        put(self.bundle, '@HollowCountry/addons/planted.pbo.hollowcountry.bisign', b'PLANTEDSIG')
        put(self.bundle, 'profiles/HollowCountry/planted.json', '{}')
        put(self.bundle, 'keys/planted.bikey', b'PLANTEDKEY')
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        for rel in ('@HollowCountry/addons/planted.pbo', '@HollowCountry/addons/planted.pbo.hollowcountry.bisign',
                    'profiles/HollowCountry/planted.json', 'keys/planted.bikey'):
            self.assertFalse((self.server / rel).exists(), rel)
        self.assertNotIn('planted', json.dumps(json.loads((self.server / fi.RECEIPT).read_text())))
        self.assertTrue((self.server / '@HollowCountry/addons/hollowcountry.pbo').is_file())

    def test_a_server_cfg_edited_while_the_prompt_waits_is_drift_and_is_not_overwritten(self):
        edited = SERVER_CFG.replace('hostname = "Local";', 'hostname = "Edited while waiting";')
        seen = []
        before = live_snapshot(self.server)

        def answer(prompt):
            if prompt.startswith('serverDZ.cfg settings'):
                seen.append(prompt)
                (self.server / 'serverDZ.cfg').write_text(edited)
            return 'y'
        code, out, err = self.run_cli('--apply', answers=answer)
        self.assertEqual(code, 2)
        self.assertTrue(seen)
        self.assertIn('drift', err)
        self.assertIn('serverDZ.cfg', err)
        self.assertEqual((self.server / 'serverDZ.cfg').read_text(), edited)
        self.assertEqual(list((self.server / fi.BACKUP_DIR).rglob('serverDZ.cfg')), [])
        self.assertFalse((self.server / '.serverDZ.cfg.hc-new').exists())
        before['serverDZ.cfg'] = sha(edited.encode())
        self.assertEqual(live_snapshot(self.server), before)
        self.assertIn('rolled back: the server is as it was before this run', err)


class HoldoutProfileTests(InstallerCase):
    """#174: authored JSON fixtures; no engine load or funded-state acceptance is implied."""

    HOLDOUT = 'profiles/HollowCountry/holdouts.json'
    # HCHoldoutState fields before HC-16: Version, TemplatePin, Rows. An explicit
    # empty catalog is sufficient to reproduce the legacy refusal without game data.
    LEGACY = b'{"Version":1,"TemplatePin":"synthetic-legacy-pin","Rows":[]}\r\n'
    # HCHoldoutState / HCAICampPolicy / HCAICampResources, authored by hand from
    # 4_World/World/HCHoldouts.c and HCAICampLifecycle.c. Not a native save image.
    # Schema 2: the finite founding pool before HC-16 reserves (refused by schema 3).
    PRE_RESERVE = b'''{"Version":2,"CampPolicy":{"FoundingStock":48,"FoundingPopulation":12,
"CampAllocation":24,"BivouacCost":1,"HouseholdCost":2,"StableCost":4,"HubCost":8,
"GrowthSeconds":3600,"UpkeepSeconds":86400,"RaidLockoutSeconds":604800,
"RoleSeconds":120,"RoutineRangeMeters":30,"ArrivalToleranceMeters":1},
"Resources":{"Stock":48,"Population":12},"TemplatePin":"synthetic-funded-pin","Rows":[]}\n'''
    FUNDED = b'''{"Version":3,"CampPolicy":{"FoundingStock":48,"FoundingPopulation":12,
"CampAllocation":24,"BivouacCost":1,"HouseholdCost":2,"StableCost":4,"HubCost":8,
"GrowthSeconds":3600,"UpkeepSeconds":86400,"RaidLockoutSeconds":604800,
"RoleSeconds":120,"RoutineRangeMeters":30,"ArrivalToleranceMeters":1,"ReserveCap":144,
"ReserveRegenPerDay":12,"ReserveDaySeconds":86400,"ReservePopulationCap":36,
"ReservePopulationRegenPerDay":3},"Resources":{"Stock":48,"Population":12,"ReserveAt":0,
"Refunded":0},"TemplatePin":"synthetic-funded-pin","Rows":[]}\n'''

    def put_holdouts(self, image, companions=True):
        rows = {self.HOLDOUT: image}
        if companions:
            rows.update({self.HOLDOUT + '.bak': b'SYNTHETIC prior backup\x00\r\n',
                         self.HOLDOUT + '.tmp': b'{"Version":1,"Rows":['})
        for rel, data in rows.items():
            put(self.server, rel, data)
        return rows

    def test_plan_only_names_each_existing_legacy_file_and_changes_nothing(self):
        rows = self.put_holdouts(self.LEGACY)
        before = snapshot(self.tmp)
        code, out, err = self.run_cli('--plan-only')
        self.assertEqual(code, 0, out + err)
        self.assertIn('legacy', out.lower())
        for rel in rows:
            self.assertIn('move to the backup folder: ' + rel, out)
        self.assertEqual(snapshot(self.tmp), before)

    def test_legacy_moves_use_the_same_run_journal_and_relative_receipt_names(self):
        rows = self.put_holdouts(self.LEGACY)
        put(self.server, 'profiles/HollowCountry/pickers.json', b'UNRELATED STATE')
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        journals = list((self.server / fi.BACKUP_DIR).glob('*/' + fi.JOURNAL))
        self.assertEqual(len(journals), 1, 'reuse the existing run, including its other steps')
        journal = json.loads(journals[0].read_text())
        entries = {row['path']: row for row in journal['entries']}
        for rel, data in rows.items():
            self.assertFalse((self.server / rel).exists(), rel)
            self.assertEqual((journals[0].parent / rel).read_bytes(), data)
            self.assertEqual(entries[rel]['kind'], 'file')
            self.assertEqual(entries[rel]['written'][''], [None])
        receipt = json.loads((self.server / fi.RECEIPT).read_text())
        self.assertEqual(receipt['holdouts_moved'], list(rows))
        self.assertNotIn(str(self.tmp), json.dumps(receipt))
        self.assertEqual((self.server / 'profiles/HollowCountry/pickers.json').read_bytes(), b'UNRELATED STATE')
        before = snapshot(self.tmp)
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual(snapshot(self.tmp), before, 'second apply must not rewrite or lose the move receipt')

    def test_schema_2_founding_pool_image_is_moved_because_schema_3_refuses_it(self):
        # Lead RED (2026-11-18): with HC-16 reserves (schema 3) the installer kept a Version 2 image
        # as "funded", so the mod refused it with STATE_INVALID on every boot.
        rows = self.put_holdouts(self.PRE_RESERVE)
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertIn('legacy schema 2', out)
        for rel in rows:
            self.assertFalse((self.server / rel).exists(), rel)
        receipt = json.loads((self.server / fi.RECEIPT).read_text())
        self.assertEqual(receipt['holdouts_moved'], list(rows))

    def test_only_existing_files_are_moved_even_when_profiles_are_otherwise_done(self):
        self.assertEqual(self.apply()[0], 0)
        self.put_holdouts(self.LEGACY, companions=False)
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(status_of(out, 8), 'done')
        receipt = json.loads((self.server / fi.RECEIPT).read_text())
        self.assertEqual(receipt['holdouts_moved'], [self.HOLDOUT])
        self.assertFalse((self.server / self.HOLDOUT).exists())

    def test_invalid_json_and_invalid_utf8_are_moved_with_their_companions(self):
        for image in (b'{"Version":1,"Rows":[', b'\xff\xfeNOT JSON'):
            with self.subTest(image=image):
                rows = self.put_holdouts(image)
                code, out, err = self.apply()
                self.assertEqual(code, 0, out + err)
                self.assertIn('invalid JSON', out)
                for rel, data in rows.items():
                    self.assertFalse((self.server / rel).exists(), rel)
                    self.assertIn(data, [p.read_bytes() for p in
                                        (self.server / fi.BACKUP_DIR).glob('*/' + rel)])

    def test_funded_schema_and_companions_stay_byte_identical_without_new_backups(self):
        self.assertEqual(self.apply()[0], 0)
        self.put_holdouts(self.FUNDED)
        before = snapshot(self.tmp)
        code, out, err = self.run_cli('--plan-only')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(status_of(out, 8), 'already-done')
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual(snapshot(self.tmp), before)

    def test_absent_primary_does_not_move_orphan_companions(self):
        self.assertEqual(self.apply()[0], 0)
        put(self.server, self.HOLDOUT + '.bak', self.LEGACY)
        before = snapshot(self.tmp)
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual(snapshot(self.tmp), before)

    def test_check_reports_absent_funded_legacy_invalid_and_unknown_images_read_only(self):
        self.assertEqual(self.apply()[0], 0)
        for image, expected in ((None, 'PASS'), (self.FUNDED, 'PASS'), (self.LEGACY, 'FAIL'), (self.PRE_RESERVE, 'FAIL'),
                                (b'{broken', 'FAIL'), (b'{"Version":99}', 'FAIL'),
                                (b'{"Version":true}', 'FAIL'), (b'[]', 'FAIL')):
            with self.subTest(image=image):
                if image is not None:
                    self.put_holdouts(image)
                before = snapshot(self.tmp)
                code, out, err = self.run_cli('--check')
                self.assertEqual(code, 0 if expected == 'PASS' else 1, out + err)
                self.assertRegex(out, expected + r'\s+holdouts\s+')
                self.assertEqual(snapshot(self.tmp), before)

    def test_unknown_schema_is_reported_but_never_moved(self):
        self.assertEqual(self.apply()[0], 0)
        self.put_holdouts(b'{"Version":99,"Rows":[]}')
        before = snapshot(self.tmp)
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertIn('unsupported holdouts schema', out)
        self.assertEqual(snapshot(self.tmp), before)

    def test_running_server_refuses_before_moving_legacy_state(self):
        self.put_holdouts(self.LEGACY)
        before = snapshot(self.tmp)
        ws.server_running.return_value = True
        code, out, err = self.apply()
        self.assertEqual(code, 2, out + err)
        self.assertIn('server_running', err)
        self.assertEqual(snapshot(self.tmp), before)

    def test_skipping_profiles_leaves_legacy_state_and_companions_untouched(self):
        rows = self.put_holdouts(self.LEGACY)
        code, out, err = self.apply('--skip', 'profiles')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(status_of(out, 8), 'skipped')
        for rel, data in rows.items():
            self.assertEqual((self.server / rel).read_bytes(), data)
        # A skipped write step cannot hide incompatible state from --check.
        code, out, err = self.run_cli('--check', '--skip', 'profiles')
        self.assertEqual(code, 1, out + err)
        self.assertRegex(out, r'FAIL\s+holdouts\s+')

    def test_late_refusal_restores_all_moved_bytes_and_the_original_receipt(self):
        self.assertEqual(self.apply()[0], 0)
        rows = self.put_holdouts(self.LEGACY)
        before = live_snapshot(self.server)
        with mock.patch.dict(fi.PLANNERS, {'cfg': lambda ctx, a: (
                'blocked', ['synthetic failure after profiles'], None)}):
            code, out, err = self.apply()
        self.assertEqual(code, 2, out + err)
        self.assertIn(fi.ROLLBACK_OK, err)
        self.assertEqual(live_snapshot(self.server), before)
        for rel, data in rows.items():
            self.assertEqual((self.server / rel).read_bytes(), data)

    def test_interruption_after_each_move_recovers_original_bytes(self):
        real_unlink = Path.unlink
        for suffix in ('', '.bak', '.tmp'):
            with self.subTest(suffix=suffix):
                self.server = self.tmp / ('interrupted-' + (suffix or 'primary'))
                self.make_server(self.server)
                rows = self.put_holdouts(self.LEGACY)
                before = live_snapshot(self.server)
                target = self.server / (self.HOLDOUT + suffix)

                def crash_after_unlink(path, *args, **kw):
                    real_unlink(path, *args, **kw)
                    if path == target:
                        raise SystemExit('synthetic hard exit after holdouts move')

                with mock.patch.object(Path, 'unlink', crash_after_unlink):
                    with self.assertRaises(SystemExit):
                        self.apply()
                self.assertFalse(target.exists(), 'fixture must reach the move before crashing')
                ctx = fi.Ctx(fi.build_parser().parse_args([]), io.StringIO(), None)
                ctx.server = self.server
                runs = fi.pending_runs(ctx)
                self.assertEqual(len(runs), 1)
                fi.recover_runs(ctx, runs)
                self.assertEqual(live_snapshot(self.server), before)
                for rel, data in rows.items():
                    self.assertEqual((self.server / rel).read_bytes(), data)

    def test_linked_companion_is_refused_without_moving_any_state(self):
        self.put_holdouts(self.LEGACY, companions=False)
        outside = put(self.tmp, 'outside.json', b'OUTSIDE')
        try:
            (self.server / (self.HOLDOUT + '.bak')).symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest('symlinks not permitted')
        before = snapshot(self.tmp)
        code, out, err = self.apply()
        self.assertEqual(code, 2, out + err)
        self.assertIn('symlink', err)
        self.assertEqual(snapshot(self.tmp), before)


class ProfileUpgradeTests(InstallerCase):
    def test_shipped_history_upgrade_preserves_edits_warns_and_rolls_back(self):
        # Explicit synthetic shipped versions, not native config/runtime evidence.
        rel = 'profiles/HollowCountry/settings.json'
        old = b'{"synthetic_release": 52}'
        current = (self.bundle / rel).read_bytes()
        self.assertEqual(self.apply()[0], 0)
        put(self.server, rel, old)
        unshipped = put(self.server, 'profiles/HollowCountry/unshipped.json', old)
        doc = json.loads((self.bundle / fi.BUNDLE_MANIFEST).read_text())
        doc['profile_defaults'] = {
            row['path']: {'sha256': row['sha256'], 'shipped_sha256': [row['sha256']]}
            for row in doc['files'] if row['path'].startswith('profiles/')}
        doc['profile_defaults'][rel]['shipped_sha256'].append(sha(old))
        put(self.bundle, fi.BUNDLE_MANIFEST, json.dumps(doc))
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertEqual((self.server / rel).read_bytes(), current)
        journals = [p for p in (self.server / fi.BACKUP_DIR).rglob(fi.JOURNAL)
                    if any(r['path'] == rel and r.get('sha256') == sha(old)
                           for r in json.loads(p.read_text())['entries'])]
        self.assertEqual(len(journals), 1)
        journal = journals[0]
        self.assertEqual((journal.parent / rel).read_bytes(), old)
        receipt = json.loads((self.server / fi.RECEIPT).read_text())
        self.assertEqual(receipt['files'][rel], sha(current))
        # Reuse the real journal rollback, including restoration of the old receipt.
        ctx = fi.Ctx(fi.build_parser().parse_args([]), io.StringIO(), None)
        ctx.server = self.server
        fi.rollback_run(ctx, journal.parent, json.loads(journal.read_text()))
        self.assertEqual((self.server / rel).read_bytes(), old)
        self.assertEqual(unshipped.read_bytes(), old)
        # A legacy receipt alone also recognizes a previous installer-owned default.
        doc.pop('profile_defaults')
        put(self.bundle, fi.BUNDLE_MANIFEST, json.dumps(doc))
        receipt = json.loads((self.server / fi.RECEIPT).read_text())
        receipt['files'][rel] = sha(old)
        put(self.server, fi.RECEIPT, json.dumps(receipt))
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual((self.server / rel).read_bytes(), current)
        history = json.loads((self.server / fi.RECEIPT).read_text())['profile_defaults'][rel]
        self.assertEqual(set(history), {sha(old), sha(current)})
        # An operator restoring an older installer-owned image still gets the upgrade.
        put(self.server, rel, old)
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual((self.server / rel).read_bytes(), current)
        edited = b'{"synthetic_operator_choice": false}'
        put(self.server, rel, edited)
        # AISettings intentionally merges HC-owned fields; use an ordinary profile for preservation.
        other = 'profiles/HollowCountry/Events/settings.json'
        put(self.server, other, edited)
        # Even without a receipt, --yes must preserve an unknown profile image.
        (self.server / fi.RECEIPT).unlink()
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual((self.server / rel).read_bytes(), edited)
        before = snapshot(self.tmp)
        code, out, err = self.run_cli('--check')
        self.assertEqual(code, 0, out + err)
        self.assertRegex(out, r'WARN\s+profile_defaults.*' + rel)
        self.assertRegex(out, r'WARN\s+profile_defaults.*' + other)
        self.assertNotRegex(out, r'FAIL\s+profile_defaults')
        adopt = '--adopt-profile "%s"' % rel
        self.assertIn('install-hollow-country.bat --apply ' + adopt, out)
        self.assertEqual(snapshot(self.tmp), before)
        self.assertEqual(self.apply('--adopt-profile', rel)[0], 0)
        self.assertEqual((self.server / rel).read_bytes(), current)
        self.assertEqual((self.server / other).read_bytes(), edited)
        self.assertEqual(unshipped.read_bytes(), old)
        code, out, err = self.apply('--adopt-profile', 'profiles/HollowCountry/unshipped.json')
        self.assertEqual(code, 2, out + err)
        self.assertEqual(unshipped.read_bytes(), old)
        doc['profile_defaults'] = {'profiles/HollowCountry/unshipped.json': {
            'sha256': sha(old), 'shipped_sha256': [sha(old)]}}
        put(self.bundle, fi.BUNDLE_MANIFEST, json.dumps(doc))
        before = snapshot(self.server)
        code, out, err = self.apply()
        self.assertEqual(code, 2, out + err)
        self.assertIn('bundle_tampered', err)
        self.assertEqual(snapshot(self.server), before)


    def test_a_retired_interiors_json_from_an_older_install_is_left_alone_and_never_fails_the_upgrade(self):
        # The pilot config is no longer shipped; the server ignores a copy left by an older release.
        retired = put(self.server, 'profiles/HollowCountry/interiors.json', b'{"synthetic_release": 52}')
        before = retired.read_bytes()
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(retired.read_bytes(), before)
        self.assertNotIn('profiles/HollowCountry/interiors.json',
                         json.loads((self.server / fi.RECEIPT).read_text())['files'])


class CheckTests(InstallerCase):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.apply()[0], 0)

    def check(self):
        before = snapshot(self.tmp)
        code, out, err = self.run_cli('--check')
        self.assertEqual(snapshot(self.tmp), before, '--check is read only')
        return code, out + err

    def test_a_complete_install_passes_and_lists_each_check(self):
        code, text = self.check()
        self.assertEqual(code, 0, text)
        for name in ('mod_folders', 'bikeys', 'meta_ids', 'mod_order'):
            self.assertRegex(text, r'PASS\s+%s' % name)
        self.assertIn('check result: pass', text)

    def test_a_missing_mod_folder_fails(self):
        shutil.move(str(self.server / '@COT'), str(self.tmp / 'moved'))
        code, text = self.check()
        self.assertEqual(code, 1)
        self.assertRegex(text, r'FAIL\s+mod_folders.*@COT')
        self.assertIn('missing_mod_folder', text)

    def test_a_missing_bikey_fails(self):
        (self.server / 'keys/hollowcountry.bikey').rename(self.tmp / 'moved.bikey')
        code, text = self.check()
        self.assertEqual(code, 1)
        self.assertIn('missing_bikey', text)
        self.assertIn('hollowcountry.bikey', text)

    def test_a_wrong_publishedid_fails(self):
        put(self.server, '@CF/meta.cpp', 'publishedid = 999999999;\n')
        code, text = self.check()
        self.assertEqual(code, 1)
        self.assertIn('wrong_publishedid', text)
        self.assertIn('@CF', text)

    def test_a_missing_meta_cpp_fails(self):
        (self.server / '@HollowCountry/meta.cpp').rename(self.tmp / 'moved.cpp')
        code, text = self.check()
        self.assertEqual(code, 1)
        self.assertIn('missing_meta_cpp', text)

    def test_a_different_mod_order_fails_and_names_the_first_difference(self):
        bat = (self.server / 'start-server.bat').read_text()
        swapped = bat.replace('@CF;@COT', '@COT;@CF')
        self.assertNotEqual(bat, swapped)
        (self.server / 'start-server.bat').write_text(swapped)
        code, text = self.check()
        self.assertEqual(code, 1)
        self.assertIn('wrong_mod_order', text)

    def test_a_missing_start_server_bat_fails(self):
        (self.server / 'start-server.bat').rename(self.tmp / 'moved.bat')
        code, text = self.check()
        self.assertEqual(code, 1)
        self.assertIn('missing_start_server', text)

    def test_signature_checking_turned_off_fails(self):
        cfg = (self.server / 'serverDZ.cfg').read_text().replace('verifySignatures = 2;', 'verifySignatures = 0;')
        (self.server / 'serverDZ.cfg').write_text(cfg)
        code, text = self.check()
        self.assertEqual(code, 1)
        self.assertIn('verify_signatures_off', text)
        self.assertNotIn('S3CRET', text)

    def test_the_map_overlay_receipt_is_reported_present_and_intact(self):
        code, text = self.check()
        self.assertEqual(code, 0, text)
        self.assertRegex(text, r'PASS\s+map_overlays')

    def test_a_missing_map_overlay_fails_the_check(self):
        shutil.rmtree(self.mission / fi.map_overlay.MANAGED)
        code, text = self.check()
        self.assertEqual(code, 1)
        self.assertRegex(text, r'FAIL\s+map_overlays.*missing_map_overlay')

    def test_a_damaged_map_overlay_receipt_fails_the_check(self):
        (self.mission / fi.map_overlay.MANAGED / 'receipt.json').write_text('{}')
        code, text = self.check()
        self.assertEqual(code, 1)
        self.assertRegex(text, r'FAIL\s+map_overlays.*damaged_map_overlay')

    def test_a_hand_edited_gameplay_file_fails_the_map_overlay_check(self):
        (self.mission / 'cfggameplay.json').write_text('{}')
        code, text = self.check()
        self.assertEqual(code, 1)
        self.assertIn('damaged_map_overlay', text)
        self.assertIn('cfggameplay.json', text)

    def test_a_skipped_map_overlay_is_not_checked(self):
        shutil.rmtree(self.mission / fi.map_overlay.MANAGED)
        code, out, err = self.run_cli('--check', '--skip', 'overlays-map')
        self.assertEqual(code, 0, out + err)
        self.assertNotIn('map_overlays', out)

    def test_check_needs_no_prompt_and_no_stopped_server(self):
        ws.server_running.return_value = True
        code, out, err = self.run_cli('--check', answers=lambda prompt: self.fail('prompted'))
        self.assertEqual(code, 0, out + err)


class ConfigMergeTests(unittest.TestCase):
    WANT = {'thirdPersonView': '2', 'serverTimeAcceleration': '4'}

    def merge(self, text, want=None, template=MISSION):
        return fi.merge_cfg(text, want or self.WANT, template)

    def test_values_are_replaced_in_place_and_nothing_else_changes(self):
        new, changes = self.merge(SERVER_CFG)
        self.assertIn('thirdPersonView = 2;', new)
        self.assertIn('serverTimeAcceleration = 4;', new)
        self.assertIn('template = "%s";' % MISSION, new)
        old_lines, new_lines = SERVER_CFG.splitlines(), new.splitlines()
        self.assertEqual(len(old_lines), len(new_lines))
        changed = [o for o, n in zip(old_lines, new_lines) if o != n]
        self.assertEqual(len(changed), 3)
        for line in ('password = "S3CRET-PASS-71";', 'passwordAdmin = "S3CRET-ADMIN-71";', 'verifySignatures = 2;'):
            self.assertIn(line, new_lines)
        self.assertEqual({c['key'] for c in changes}, {'thirdPersonView', 'serverTimeAcceleration', 'template'})

    def test_missing_keys_are_inserted_before_the_first_class(self):
        text = 'hostname = "x";\nclass Missions\n{\n    class DayZ\n    {\n        template = "a";\n    };\n};\n'
        new, _ = self.merge(text)
        self.assertLess(new.index('thirdPersonView = 2;'), new.index('class Missions'))
        self.assertLess(new.index('serverTimeAcceleration = 4;'), new.index('class Missions'))

    def test_bom_and_crlf_are_preserved(self):
        text = '﻿' + SERVER_CFG.replace('\n', '\r\n')
        new, _ = self.merge(text)
        self.assertTrue(new.startswith('﻿'))
        self.assertNotIn('\n', new.replace('\r\n', ''))
        self.assertIn('thirdPersonView = 2;\r\n', new)

    def test_an_already_merged_file_comes_back_identical_with_no_changes(self):
        merged, _ = self.merge(SERVER_CFG)
        again, changes = self.merge(merged)
        self.assertEqual(again, merged)
        self.assertEqual([c for c in changes if c['action'] != 'unchanged'], [])

    def test_numeric_equivalents_are_not_changes(self):
        new, changes = self.merge('serverTimeAcceleration = 4.0;\nclass Missions { class DayZ { template = "%s"; }; };\n'
                                  % MISSION, {'serverTimeAcceleration': '4'})
        self.assertEqual([c['action'] for c in changes], ['unchanged', 'unchanged'])

    def test_comments_and_nested_keys_are_not_matched(self):
        text = ('// thirdPersonView = 5;\nclass Other { thirdPersonView = 9; };\n'
                'class Missions { class DayZ { template = "a"; }; };\n')
        new, _ = self.merge(text, {'thirdPersonView': '2'})
        self.assertIn('// thirdPersonView = 5;', new)
        self.assertIn('class Other { thirdPersonView = 9; };', new)
        self.assertEqual(new.count('thirdPersonView = 2;'), 1)

    def test_keys_match_case_insensitively(self):
        new, _ = self.merge('thirdpersonview = 0;\nclass Missions { class DayZ { template = "a"; }; };\n',
                            {'thirdPersonView': '2'})
        self.assertIn('thirdpersonview = 2;', new)

    def test_a_line_holding_several_statements_refuses(self):
        with self.assertRaises(fi.Refused) as caught:
            self.merge('thirdPersonView = 0; disable3rdPerson = 1;\nclass Missions { class DayZ { template = "a"; }; };\n')
        self.assertEqual(caught.exception.code, 'cfg_multiple')

    def test_a_key_set_twice_refuses(self):
        with self.assertRaises(fi.Refused) as caught:
            self.merge('thirdPersonView = 0;\nthirdPersonView = 1;\nclass Missions { class DayZ { template = "a"; }; };\n')
        self.assertEqual(caught.exception.code, 'cfg_duplicate')

    def test_a_missing_template_block_refuses(self):
        with self.assertRaises(fi.Refused) as caught:
            self.merge('hostname = "x";\n')
        self.assertEqual(caught.exception.code, 'cfg_template_missing')

    def test_the_snippet_parser_reads_keys_and_template_and_ignores_comments(self):
        keys, template = fi.parse_snippet(SNIPPET)
        self.assertEqual(keys['thirdPersonView'], '2')
        self.assertEqual(keys['serverNightTimeAcceleration'], '8')
        self.assertEqual(template, MISSION)
        self.assertNotIn('template', keys)

    def test_the_snippet_parser_refuses_a_snippet_without_a_template(self):
        with self.assertRaises(fi.Refused):
            fi.parse_snippet('thirdPersonView = 2;\n')

    def test_only_listed_keys_can_ever_change(self):
        with self.assertRaises(fi.Refused) as caught:
            fi.parse_snippet('password = "x";\ntemplate = "a";\n')
        self.assertEqual(caught.exception.code, 'cfg_key_not_allowed')


class LauncherFilesTests(unittest.TestCase):
    def test_the_installer_launcher_calls_the_module_and_passes_arguments_through(self):
        bat = (ROOT / 'tools/setup/install-hollow-country.bat').read_text(encoding='utf-8')
        self.assertIn('-m tools.setup.friend_install', bat)
        self.assertIn('%*', bat)
        self.assertIn('%~dp0', bat)
        self.assertNotIn('--apply', bat, 'the launcher is a dry run until the friend says yes')

    def test_the_installer_ships_the_same_module_as_the_repo_checks(self):
        self.assertEqual(fi.REMEMBER_FILE, 'hollow-country-server-root.txt')
        self.assertEqual(fi.STEPS[0], 'server')
        self.assertEqual(len(fi.STEPS), 11)


def live_snapshot(root):
    """Compare every live file and directory; retained installer audit backups are separate."""
    return {rel: value for rel, value in snapshot(root).items()
            if rel != fi.BACKUP_DIR and not rel.startswith(fi.BACKUP_DIR + '/')}


class RunRollbackTests(InstallerCase):
    JOURNAL = 'run-journal.json'
    WRITING = ('workshop', 'mods', 'overlay', 'overlays-map', 'profiles', 'cfg', 'launcher')

    def inject_after(self, step, error):
        planner = fi.PLANNERS[step]

        def wrapped(ctx, analysis):
            status, lines, action = planner(ctx, analysis)
            def fail_after():
                action()
                raise error
            return status, lines, fail_after if action else None
        return mock.patch.dict(fi.PLANNERS, {step: wrapped})

    def test_refusal_after_every_writing_step_restores_the_pre_run_tree(self):
        for step in self.WRITING:
            with self.subTest(step=step):
                self.server = self.tmp / ('server-' + step)
                self.mission = self.make_server(self.server)
                put(self.server, 'start-server.bat', 'start x "-mod=@Old"\r\n')
                put(self.server, 'profiles/HollowCountry/settings.json', 'OLD SETTINGS')
                put(self.server, '@HollowCountry/mod.cpp', 'OLD MOD')
                put(self.server, '@HollowCountry/addons/retired.pbo', 'OLD SIGNED NAME')
                put(self.server, 'unrelated/keep.txt', 'KEEP')
                (self.server / 'empty').mkdir()
                before = live_snapshot(self.server)
                with self.inject_after(step, fi.Refused('injected', 'after ' + step)):
                    code, out, err = self.apply()
                self.assertEqual(code, 2, out + err)
                self.assertEqual(live_snapshot(self.server), before)
                self.assertIn('rolled back: the server is as it was before this run', err)
                self.assertEqual(self.apply()[0], 0)
                self.assertEqual(self.run_cli('--check')[0], 0)

    def test_late_refusal_restores_the_previous_install_including_both_overlays(self):
        self.assertEqual(self.apply()[0], 0)
        before = live_snapshot(self.server)
        newer = make_bundle(self.tmp / 'newer')
        put(newer, '@HollowCountry/mod.cpp', 'NEW MOD')
        put(newer, 'profiles/HollowCountry/settings.json', 'NEW SETTINGS')
        put(newer, 'start-server.bat', (newer / 'start-server.bat').read_text() + '\nrem new\n')
        put(newer, 'mission-overlay/hollow-country/events/scene-chains.json', '{"new": true}')
        profile_path = newer / 'config/map-overlays/profile.json'
        profile = json.loads(profile_path.read_text())
        profile['enabled'] = profile['enabled'][:-1]
        profile_path.write_text(json.dumps(profile))
        write_manifest(newer)
        with self.inject_after('launcher', fi.Refused('injected', 'late upgrade refusal')):
            code, out, err = self.apply(bundle=newer)
        self.assertEqual(code, 2, out + err)
        self.assertEqual(live_snapshot(self.server), before)
        self.assertIn('rolled back: the server is as it was before this run', err)
        self.assertEqual(self.run_cli('--check')[0], 0)

    def test_a_crash_is_named_read_only_and_a_rerun_recovers_then_installs(self):
        class Crash(BaseException):
            pass
        with self.inject_after('overlays-map', Crash()):
            with self.assertRaises(Crash):
                self.apply()
        journals = list((self.server / fi.BACKUP_DIR).rglob(self.JOURNAL))
        self.assertEqual(len(journals), 1)
        self.assertEqual(json.loads(journals[0].read_text())['state'], 'active')
        before_check = snapshot(self.tmp)
        code, out, err = self.run_cli('--check')
        self.assertEqual(code, 1, out + err)
        self.assertIn('install_interrupted', out + err)
        self.assertIn('pending:', out + err)
        self.assertEqual(snapshot(self.tmp), before_check)
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertIn('Recovered interrupted install', out)
        self.assertEqual(self.run_cli('--check')[0], 0)

    def test_a_failed_rollback_stops_lists_remaining_changes_and_a_rerun_finishes(self):
        original = Path.unlink
        def refuse_launcher(path, *args, **kwargs):
            if path == self.server / 'start-server.bat':
                raise PermissionError('synthetic locked launcher')
            return original(path, *args, **kwargs)
        with self.inject_after('launcher', fi.Refused('injected', 'late refusal')), \
                mock.patch.object(Path, 'unlink', refuse_launcher):
            code, out, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn('rollback_pending', err)
        self.assertIn('pending: remove start-server.bat', err)
        self.assertNotIn('rolled back: the server is as it was before this run', err)
        # The first reverse-order undo failed: no earlier undo may have run.
        self.assertTrue((self.server / '@HollowCountry/mod.cpp').is_file())
        self.assertTrue((self.mission / fi.map_overlay.MANAGED).is_dir())
        code, checked, check_err = self.run_cli('--check')
        self.assertEqual(code, 1, checked + check_err)
        self.assertIn('rollback_pending', checked)
        self.assertEqual([line.strip() for line in err.splitlines() if 'pending:' in line],
                         [line.strip() for line in checked.splitlines() if 'pending:' in line])
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual(self.run_cli('--check')[0], 0)

    def test_journal_is_replaced_atomically_before_a_live_write_even_if_the_write_crashes(self):
        original_replace, original_copy = os.replace, ws.copy_atomic
        replacements = []
        def observe_replace(source, target):
            if Path(target).name == self.JOURNAL:
                self.assertNotEqual(Path(source), Path(target))
                self.assertEqual(Path(source).parent, Path(target).parent)
                replacements.append(json.loads(Path(source).read_text()))
            return original_replace(source, target)
        class Crash(BaseException):
            pass
        def crash_after_copy(source, target):
            target = Path(target)
            if target.is_relative_to(self.server) and fi.BACKUP_DIR not in target.relative_to(self.server).parts:
                rel = target.relative_to(self.server).as_posix()
                self.assertTrue(replacements, 'journal must precede the live copy')
                self.assertTrue(any(row['path'] == rel for row in replacements[-1]['entries']), rel)
            original_copy(source, target)
            if target == self.server / '@HollowCountry/mod.cpp':
                raise Crash()
        with mock.patch.object(os, 'replace', observe_replace), \
                mock.patch.object(ws, 'copy_atomic', crash_after_copy):
            with self.assertRaises(Crash):
                self.apply()
        self.assertTrue(replacements, 'an atomic journal must precede live writes')
        self.assertIn('install_interrupted', ''.join(self.run_cli('--check')[1:]))
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual(self.run_cli('--check')[0], 0)

    def test_crashes_inside_atomic_writers_remove_only_new_scratch_files_on_recovery(self):
        class Crash(BaseException):
            pass
        for writer in ('mod', 'key', 'receipt'):
            with self.subTest(writer=writer):
                self.server = self.tmp / ('scratch-' + writer)
                self.mission = self.make_server(self.server)
                put(self.server, '@HollowCountry/mod.cpp', 'OLD MOD')
                put(self.server, 'keys/.sync-preexisting.tmp', 'KEEP THIS OLD TEMP')
                before = live_snapshot(self.server)
                original_copy, original_json = ws.copy_atomic, ws.write_json_atomic
                def crash_copy(source, target):
                    target = Path(target)
                    if ((writer == 'mod' and target == self.server / '@HollowCountry/mod.cpp')
                            or (writer == 'key' and target.parent == self.server / 'keys')):
                        put(target.parent, '.sync-synthetic.tmp', 'PARTIAL COPY')
                        raise Crash()
                    return original_copy(source, target)
                def crash_json(target, data):
                    if writer == 'receipt' and target == self.server / ws.RECEIPT_NAME:
                        put(target.parent, '.receipt-synthetic.tmp', '{"partial":')
                        raise Crash()
                    return original_json(target, data)
                with mock.patch.object(ws, 'copy_atomic', crash_copy), \
                        mock.patch.object(ws, 'write_json_atomic', crash_json):
                    with self.assertRaises(Crash):
                        self.apply()
                self.assertIn('install_interrupted', ''.join(self.run_cli('--check')[1:]))
                # Recover, then refuse this fresh run too: the live tree must equal the original.
                with self.inject_after('workshop', fi.Refused('injected', 'refuse fresh run')):
                    code, out, err = self.apply()
                self.assertEqual(code, 2, out + err)
                self.assertIn('Recovered interrupted install', out)
                self.assertEqual(live_snapshot(self.server), before)

    def test_a_partial_mission_apply_is_restored_without_copying_storage(self):
        before = live_snapshot(self.server)
        regular = fi.overlays.main.side_effect
        def partial(argv):
            if argv[0] == 'bundle-apply':
                put(self.mission, 'cfgeconomycore.xml', '<partial/>')
                put(self.mission, 'hollow-country/new/deep/file.json', '{}')
                put(self.mission, 'hollow-country-bundle/receipt.json', '{"partial":true}')
                print('refused: synthetic partial apply', file=sys.stderr)
                return 2
            return regular(argv)
        with mock.patch.object(fi.overlays, 'main', side_effect=partial):
            code, out, err = self.apply()
        self.assertEqual(code, 2, out + err)
        self.assertIn('rolled back: the server is as it was before this run', err)
        self.assertEqual(live_snapshot(self.server), before)
        self.assertFalse(list((self.server / fi.BACKUP_DIR).rglob('players.db')))
        self.assertEqual(self.apply()[0], 0)

    def test_a_crash_during_rollback_resumes_the_remaining_work(self):
        class Crash(BaseException):
            pass
        original = fi.restore_change
        calls = []
        def crash_after_undo(ctx, change):
            original(ctx, change)
            calls.append(change)
            if len(calls) == 2:
                raise Crash()
        with self.inject_after('launcher', fi.Refused('injected', 'late refusal')), \
                mock.patch.object(fi, 'restore_change', crash_after_undo):
            with self.assertRaises(Crash):
                self.apply()
        code, out, err = self.run_cli('--check')
        self.assertEqual(code, 1, out + err)
        self.assertIn('rollback_pending', out)
        self.assertNotIn('pending: remove start-server.bat', out)
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual(self.run_cli('--check')[0], 0)


class ReviewRoundTwoTests(InstallerCase):
    """Synthetic crash/recovery fixtures; no DayZ or Windows behavior is established."""
    inject_after = RunRollbackTests.inject_after

    def crash_after(self, step):
        class Crash(BaseException):
            pass
        with self.inject_after(step, Crash()):
            with self.assertRaises(Crash):
                self.apply()
        return next((self.server / fi.BACKUP_DIR).rglob(fi.JOURNAL))

    def test_recovery_preserves_cfg_edited_after_crash_and_names_backup(self):
        journal = self.crash_after('cfg')
        edited = put(self.server, 'serverDZ.cfg', 'OPERATOR EDIT AFTER CRASH')
        code, out, err = self.apply()
        self.assertEqual(edited.read_text(), 'OPERATOR EDIT AFTER CRASH')
        self.assertEqual(code, 2, out + err)
        self.assertIn('rollback_pending', out + err)
        self.assertIn('serverDZ.cfg', err)
        self.assertIn(str(journal.parent / 'serverDZ.cfg'), err)
        self.assertEqual(json.loads(journal.read_text())['state'], 'rollback_pending')

    def test_recovery_preserves_file_created_at_absent_target_after_crash(self):
        original = ws.copy_atomic
        class Crash(BaseException):
            pass
        target = self.server / '@HollowCountry/mod.cpp'
        def crash_before_copy(source, destination):
            if destination == target:
                raise Crash()
            original(source, destination)
        with mock.patch.object(ws, 'copy_atomic', crash_before_copy):
            with self.assertRaises(Crash):
                self.apply()
        put(self.server, target.relative_to(self.server), 'OPERATOR CREATED THIS')
        code, out, err = self.apply()
        self.assertEqual(target.read_text(), 'OPERATOR CREATED THIS')
        self.assertEqual(code, 2, out + err)
        self.assertIn('rollback_pending', err)
        self.assertIn('@HollowCountry/mod.cpp', err)
        self.assertIn(fi.BACKUP_DIR, err)

    def test_recovery_preserves_edited_and_unrecognized_tree_files(self):
        journal = self.crash_after('overlays-map')
        put(self.mission, 'cfggameplay.json', 'SERVER EDIT')
        put(self.mission, 'operator.txt', 'OPERATOR CREATED')
        code, out, err = self.apply()
        self.assertEqual((self.mission / 'cfggameplay.json').read_text(), 'SERVER EDIT')
        self.assertEqual((self.mission / 'operator.txt').read_text(), 'OPERATOR CREATED')
        self.assertEqual(code, 2, out + err)
        self.assertIn(str(journal.parent / 'mpmissions' / MISSION), err)
        self.assertIn('cfggameplay.json', err)
        self.assertIn('operator.txt', err)

    def test_journal_records_written_file_and_tree_hashes(self):
        journal = self.crash_after('cfg')
        rows = {row['path']: row for row in json.loads(journal.read_text())['entries']}
        for rel in ('serverDZ.cfg', '@HollowCountry/mod.cpp'):
            self.assertIn(sha((self.server / rel).read_bytes()), rows[rel]['written'][''])
        tree_rel = 'mpmissions/' + MISSION
        tree = rows[tree_rel]['written']
        for name in ('cfggameplay.json', fi.map_overlay.MANAGED + '/receipt.json'):
            self.assertIn(sha((self.mission / name).read_bytes()), tree[name])

    def test_reserved_components_are_case_insensitive(self):
        for rel in ('Storage_1/player.db', 'nested/Storage_1/file',
                    'hollow-country-install-backups/file', 'HOLLOW-COUNTRY-INSTALL-BACKUPS/file'):
            with self.subTest(rel=rel), self.assertRaises(ValueError):
                fi.safe_relative(rel)

    def test_tree_inventory_and_backup_skip_mixed_case_storage(self):
        put(self.mission, 'Storage_1/player.db', 'PERSISTENCE')
        inventory = fi.tree_inventory(self.mission)
        self.assertNotIn('Storage_1/player.db', inventory)
        self.crash_after('overlay')
        self.assertFalse(list((self.server / fi.BACKUP_DIR).rglob('player.db')))

    def test_load_bundle_refuses_backslash_manifest_paths(self):
        # POSIX permits a literal backslash filename; Windows would treat it as a separator.
        path = put(self.bundle, 'keys\\injected.bikey', 'KEY')
        manifest = json.loads((self.bundle / fi.BUNDLE_MANIFEST).read_text())
        manifest['files'].append({'path': path.name, 'sha256': sha(b'KEY')})
        put(self.bundle, fi.BUNDLE_MANIFEST, json.dumps(manifest))
        with self.assertRaises(fi.Refused):
            fi.load_bundle(self.bundle)

    def test_cfg_uses_atomic_fsync_writer_without_clobbering_fixed_temp_name(self):
        sentinel = put(self.server, '.serverDZ.cfg.hc-new', 'OPERATOR TEMP')
        syncs = []
        real_fsync = os.fsync
        real_replace = os.replace
        def sync(fd):
            syncs.append(fd)
            return real_fsync(fd)
        def replace(source, target):
            if Path(target) == self.server / 'serverDZ.cfg':
                self.assertTrue(syncs, 'cfg replacement must follow fsync')
                self.assertNotEqual(Path(source), sentinel)
            return real_replace(source, target)
        with mock.patch.object(os, 'fsync', sync), mock.patch.object(os, 'replace', replace):
            code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(sentinel.read_text(), 'OPERATOR TEMP')

    def test_atomic_copy_fsyncs_parent_after_replace(self):
        events = []
        source = put(self.tmp, 'source', 'BYTES')
        target = self.tmp / 'target'
        real_sync, real_replace = os.fsync, os.replace
        def sync(fd):
            events.append('sync')
            return real_sync(fd)
        def replace(source, target):
            events.append('replace')
            return real_replace(source, target)
        with mock.patch.object(os, 'fsync', sync), mock.patch.object(os, 'replace', replace):
            ws.copy_atomic(source, target)
        self.assertEqual(events, ['sync', 'replace', 'sync'])

    def test_parent_fsync_failure_is_best_effort_on_windows(self):
        target = self.tmp / 'target'
        with mock.patch.object(ws.os, 'name', 'nt'), \
                mock.patch.object(ws.os, 'open', side_effect=PermissionError('synthetic Windows directory handle')):
            ws.fsync_parent(target)

    def test_parent_fsync_io_failure_is_reported_when_supported(self):
        target = self.tmp / 'target'
        with mock.patch.object(ws.os, 'name', 'posix'), \
                mock.patch.object(ws.os, 'open', return_value=123), \
                mock.patch.object(ws.os, 'fsync', side_effect=OSError('synthetic disk failure')), \
                mock.patch.object(ws.os, 'close') as close:
            with self.assertRaises(OSError):
                ws.fsync_parent(target)
            close.assert_called_once_with(123)

    def test_unfingerprinted_mission_bytes_require_manual_reconciliation(self):
        journal = self.crash_after('overlay')
        # Explicitly model a hard exit before a tree writer publishes its after snapshot.
        data = json.loads(journal.read_text())
        tree = next(row for row in data['entries'] if row['kind'] == 'tree')
        tree['written'] = {}
        journal.write_text(json.dumps(data))
        before = live_snapshot(self.server)
        code, out, err = self.apply()
        self.assertEqual(code, 2, out + err)
        self.assertEqual(live_snapshot(self.server), before)
        self.assertIn('rollback_pending', err)
        self.assertIn('hollow-country-bundle/receipt.json', err)
        self.assertEqual(err.count('changed after interrupted install; left untouched:'), 1)

    def test_identical_dependency_key_is_unchanged_without_a_backup(self):
        key = next(self.content.rglob('*.bikey'))
        rel = 'keys/' + key.name
        put(self.server, rel, key.read_bytes())
        journal = self.crash_after('workshop')
        data = json.loads(journal.read_text())
        self.assertFalse((journal.parent / rel).exists(), 'unchanged dependency must not be backed up')
        self.assertIn(rel, data['unchanged'])
        self.assertNotIn(rel, [row['path'] for row in data['entries']])


if __name__ == '__main__':
    unittest.main()


class CaseFoldTests(InstallerCase):
    """Synthetic NTFS case-insensitivity fixtures (review P2-1/P2-2); no Windows behavior is established."""

    def test_a_case_only_variant_of_an_expected_pbo_is_not_treated_as_stale(self):
        put(self.server, '@HollowCountry/addons/HollowCountry.pbo', b'OLD CASE')
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertTrue((self.server / '@HollowCountry/addons/HollowCountry.pbo').exists())
        self.assertEqual(list((self.server / fi.BACKUP_DIR).rglob('HollowCountry.pbo')), [])

    def test_a_bundle_listing_two_paths_that_differ_only_by_case_refuses(self):
        put(self.bundle, 'profiles/HollowCountry/Settings.json', '{"EnableX": false}')
        write_manifest(self.bundle)
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertIn('bundle_tampered', err)
        self.assertIn('differ only by case', err)

    def test_track_target_treats_a_case_variant_as_already_captured(self):
        ctx = mock.Mock()
        ctx.server = self.server
        ctx.backup_root = self.tmp / 'backup-root'
        ctx.journal = {'entries': [{'path': '@HollowCountry/addons/hollowcountry.pbo', 'kind': 'file'}]}
        with mock.patch.object(fi, 'ensure_journal'), mock.patch.object(fi, 'record_written') as recorded:
            fi.track_target(ctx, '@HollowCountry/addons/HollowCountry.PBO')
        recorded.assert_not_called()
        self.assertEqual(len(ctx.journal['entries']), 1)


GLOBALS_STOCK = (b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\r\n<variables>\r\n'
                 b'\t<var name="IdleModeCountdown" type="0" value="60"/>\r\n'
                 b'\t<var name="IdleModeStartup" type="0" value="1"/>\r\n'
                 b'\t<var name="RespawnLimit" type="0" value="20"/>\r\n'
                 b'\t<var name="RespawnTypes" type="0" value="12"/>\r\n'
                 b'\t<!-- <var name="RespawnTypes" type="0" value="999"/> -->\r\n'
                 b'</variables>\r\n')


def install_loot(mission, stock, multiplier):
    """Synthetic loot boost state for db/globals.xml only, in the real receipt layout and with the real scaler."""
    managed = mission / fi.loot_boost.MANAGED
    after, report = fi.loot_boost.scale_globals(stock, multiplier)
    row = {'name': 'db/globals.xml', 'before': sha(stock), 'after': sha(after), 'backup': '00.backup'}
    receipt = {'schema': 1, 'kind': 'hollow-country-loot-boost', 'multiplier': multiplier, 'files': [row],
               'counts': {'globals': report}, 'runtime_acceptance': 'pending'}
    put(managed, 'receipt.json', json.dumps(receipt))
    put(managed, '00.backup', stock)
    put(mission, 'db/globals.xml', after)
    return after


def loot_overlay(calls, multiplier):
    """The synthetic bundle overlay plus a globals-only loot boost that uses the real rollback."""
    base = fake_overlay(calls)

    def main(argv):
        mission = Path(argv[argv.index('--mission') + 1])
        if argv[0] == 'bundle-rollback' and (mission / fi.loot_boost.MANAGED).exists():
            try:
                fi.loot_boost.rollback(mission)
            except ValueError as error:
                print('refused: %s' % error, file=sys.stderr)
                return 1
        code = base(argv)
        if argv[0] == 'bundle-apply':
            install_loot(mission, (mission / 'db/globals.xml').read_bytes(), multiplier)
        return code
    return main


def values_of(data):
    text = re.sub(r'<!--.*?-->', '', data.decode('utf-8-sig'), flags=re.S)
    return dict(re.findall(r'<var name="([^"]+)" type="\d+" value="([^"]*)"/>', text))


def var_values(path):
    return values_of(Path(path).read_bytes())


def boosted_values(multiplier):
    """The variable values the real scaler writes for the stock file at that multiplier."""
    return values_of(fi.loot_boost.scale_globals(GLOBALS_STOCK, multiplier)[0])


def var_tag(name, value):
    """The stock file's tag for one variable with another value (the edit tuple a test applies)."""
    tag = re.search(rb'<var name="%s" type="\d+" value="[^"]*"/>' % name.encode(), re.sub(rb'<!--.*?-->', b'', GLOBALS_STOCK, flags=re.S)).group(0)
    return re.sub(rb'value="[^"]*"', b'value="%s"' % str(value).encode(), tag)


class SelfHealingTests(InstallerCase):
    """Drift repair, globals carry-forward and run rollback on synthetic trees; nothing here runs DayZ."""

    def upgraded_bundle(self):
        newer = make_bundle(self.tmp / 'newer')
        put(newer, 'mission-overlay/hollow-country/events/scene-chains.json', '{"new": true}')
        write_manifest(newer)
        return newer

    def tuned_server(self, edits):
        """First install, then a loot boost on a stock globals.xml with the operator's edits on top."""
        self.assertEqual(self.apply()[0], 0)
        install_loot(self.mission, GLOBALS_STOCK, 2.0)
        path = self.mission / 'db/globals.xml'
        data = path.read_bytes()
        for old, new in edits:
            self.assertIn(old, data)
            data = data.replace(old, new)
        path.write_bytes(data)
        patcher = mock.patch.object(fi.overlays, 'main', side_effect=loot_overlay(self.overlay_calls, 3.0))
        patcher.start()
        self.addCleanup(patcher.stop)
        return path

    def latest_run(self):
        return sorted(p.name for p in (self.server / fi.BACKUP_DIR).iterdir())[-1]

    def receipt(self):
        return json.loads((self.server / fi.RECEIPT).read_text())

    def test_operator_globals_values_survive_an_upgrade_and_the_dry_run_names_them(self):
        edited = (b'<var name="IdleModeStartup" type="0" value="1"/>', b'<var name="IdleModeStartup" type="0" value="0"/>')
        path = self.tuned_server([edited, (b'value="60"', b'value="90"'),
                                  (b'<var name="RespawnLimit" type="0" value="20"/>',
                                   b'<var name="RespawnLimit" type="0" value="20"/>\r\n'
                                   b'\t<var name="RespawnAttempt" type="0" value="5"/>')])
        operator_bytes = path.read_bytes()
        newer = self.upgraded_bundle()
        before = snapshot(self.tmp)
        code, out, err = self.run_cli(bundle=newer)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(snapshot(self.tmp), before)
        self.assertIn('Repair preview', out)
        self.assertIn('IdleModeStartup 1 -> 0', out)
        preview = out
        self.assertEqual(self.run_cli('--check', bundle=newer)[1].count('would repair  globals'), 1)
        code, out, err = self.apply(bundle=newer)
        self.assertEqual(code, 0, out + err)
        values = var_values(path)
        self.assertEqual((values['IdleModeStartup'], values['IdleModeCountdown'], values['RespawnAttempt']),
                         ('0', '90', '5'))
        self.assertEqual(values['RespawnTypes'], boosted_values(3.0)['RespawnTypes'])  # untouched by the operator: rescaled by the new boost
        self.assertEqual(values['RespawnLimit'], '20')
        data = path.read_bytes()
        self.assertTrue(data.startswith(b'\xef\xbb\xbf'))
        self.assertIn(b'\r\n', data)
        self.assertIn(b'<!-- <var name="RespawnTypes" type="0" value="999"/> -->', data)
        # The operator's exact bytes are backed up, and the preview rows equal the receipt rows.
        backups = list((self.server / fi.BACKUP_DIR / self.latest_run()).rglob('globals.xml'))
        self.assertEqual([b.read_bytes() for b in backups], [operator_bytes])
        rows = self.receipt()['repairs'][-1]['rows']
        self.assertEqual([r['kind'] for r in rows], ['globals'])
        row = rows[0]
        self.assertIn('  would repair  %s  %s: %s' % (row['kind'], row['path'], row['detail']), preview)
        self.assertIn('  repaired  %s  %s: %s' % (row['kind'], row['path'], row['detail']), out)
        # A second run changes nothing and reports nothing to repair.
        before = snapshot(self.tmp)
        code, out, err = self.apply(bundle=newer)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(snapshot(self.tmp), before)
        self.assertIn('nothing to repair', out)

    def test_an_operator_respawn_types_value_wins_over_the_new_scale(self):
        path = self.tuned_server([(b'<var name="RespawnTypes" type="0" value="24"/>',
                                   b'<var name="RespawnTypes" type="0" value="40"/>')])
        self.assertEqual(self.apply(bundle=self.upgraded_bundle())[0], 0)
        self.assertEqual(var_values(path)['RespawnTypes'], '40')

    def test_run_rollback_restores_the_pre_upgrade_tree_and_refuses_after_later_edits(self):
        path = self.tuned_server([(b'value="60"', b'value="90"')])
        before = live_snapshot(self.server)
        self.assertEqual(self.apply(bundle=self.upgraded_bundle())[0], 0)
        run = self.latest_run()
        code, out, err = self.run_cli('--rollback', run)
        self.assertEqual(code, 0, out + err)
        self.assertIn('dry run', out)
        self.assertNotEqual(live_snapshot(self.server), before)
        # A file changed after the run is a conflict: nothing is rolled back.
        edited = path
        kept = edited.read_bytes()
        edited.write_bytes(kept + b'<!-- later edit -->\r\n')
        mid = live_snapshot(self.server)
        code, out, err = self.run_cli('--rollback', run, '--apply')
        self.assertEqual(code, 2, out + err)
        self.assertIn('rollback_conflict', err)
        self.assertEqual(live_snapshot(self.server), mid)
        edited.write_bytes(kept)
        code, out, err = self.run_cli('--rollback', run, '--apply')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(live_snapshot(self.server), before)
        self.assertIn(b'value="90"', path.read_bytes())
        self.assertIn('already rolled back', self.run_cli('--rollback', run, '--apply')[1])

    def test_unreproducible_globals_evidence_still_blocks_and_changes_nothing(self):
        self.tuned_server([(b'value="60"', b'value="90"')])
        receipt_path = self.mission / fi.loot_boost.MANAGED / 'receipt.json'
        receipt = json.loads(receipt_path.read_text())
        receipt['files'][0]['after'] = '0' * 64
        receipt_path.write_text(json.dumps(receipt))
        newer = self.upgraded_bundle()
        before = snapshot(self.server)
        code, out, err = self.run_cli(bundle=newer)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(status_of(out, 5), 'blocked')
        self.assertIn('cannot be reproduced', out)
        code, out, err = self.apply(bundle=newer)
        self.assertEqual(code, 2)
        self.assertIn('globals_drift', err)
        self.assertEqual(live_snapshot(self.server), live_snapshot_of(before))

    def test_a_missing_globals_file_is_restored_from_the_loot_receipt(self):
        path = self.tuned_server([])
        stock_scaled = path.read_bytes()
        path.unlink()
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, out + err)
        self.assertIn('would repair  globals', out)
        self.assertFalse(path.exists())
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(path.read_bytes(), stock_scaled)
        self.assertEqual(self.receipt()['repairs'][-1]['rows'][0]['kind'], 'globals')

    def test_repair_restores_edited_missing_and_retired_files_and_keeps_operator_files(self):
        self.assertEqual(self.apply()[0], 0)
        pbo = self.server / '@HollowCountry/addons/hollowcountry.pbo'
        bikey = self.server / 'keys/hollowcountry.bikey'
        launcher = self.server / 'start-server.bat'
        profile = self.server / 'profiles/ExpansionMod/Settings/AISettings.json'
        retired = self.server / '@HollowCountry/addons/retired.pbo'
        bundle_launcher = (self.bundle / 'start-server.bat').read_bytes()
        operator_launcher = bundle_launcher.replace(b'-port=2302', b'-port=2999 -cpuCount=4').replace(
            b'"-mod=@CF;', b'"-mod=@Mine;@CF;')
        self.assertNotEqual(operator_launcher, bundle_launcher)
        for target, data in ((pbo, b'EDITED'), (launcher, operator_launcher), (retired, b'OLD'),
                             (profile, b'{"Enabled": 1, "Edited": true}')):
            target.write_bytes(data)
        bikey.unlink()
        # Without --repair an edit is still a refusal that names the flag and changes nothing.
        before = snapshot(self.server)
        code, out, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn('--repair', err)
        self.assertEqual(snapshot(self.server), before)
        # The dry run with --repair names every repair and changes nothing.
        code, out, err = self.run_cli('--repair')
        self.assertEqual(code, 0, out + err)
        kinds = sorted(line.split()[2] for line in out.splitlines() if line.startswith('  would repair'))
        self.assertEqual(kinds, ['edited', 'edited', 'missing', 'retired'])
        self.assertEqual(snapshot(self.server), before)
        checked = self.run_cli('--check', '--repair')[1]
        self.assertEqual(sorted(l for l in checked.splitlines() if l.startswith('  would repair')),
                         sorted(l for l in out.splitlines() if l.startswith('  would repair')))
        code, applied, err = self.apply('--repair')
        self.assertEqual(code, 0, applied + err)
        self.assertEqual(pbo.read_bytes(), b'PBO')
        self.assertEqual(bikey.read_bytes(), b'KEY')
        # The edited launcher is never replaced wholesale: only the -mod= value comes from the bundle.
        self.assertEqual(launcher.read_bytes(), with_mods(bundle_launcher.replace(b'-port=2302', b'-port=2999 -cpuCount=4'), '@Mine'))
        self.assertFalse(retired.exists())
        self.assertEqual(profile.read_bytes(), b'{"Enabled": 1, "Edited": true}')
        self.assertEqual((self.mission / 'storage_1/data/players.db').read_text(), 'SAVED PLAYERS')
        saved = sorted(b.read_bytes() for b in (self.server / fi.BACKUP_DIR / self.latest_run()).rglob('*')
                       if b.is_file() and b.name != fi.JOURNAL)
        for original in (b'EDITED', operator_launcher, b'OLD'):
            self.assertIn(original, saved)
        rows = self.receipt()['repairs'][-1]['rows']
        for row in rows:
            self.assertIn('  repaired  %s  %s: %s' % (row['kind'], row['path'], row['detail']), applied)
            self.assertIn('  would repair  %s  %s: %s' % (row['kind'], row['path'], row['detail']), out)
        self.assertEqual(len(rows), 4)
        self.assertEqual(self.run_cli('--check')[0], 0)
        before = snapshot(self.tmp)
        code, again, err = self.apply('--repair')
        self.assertEqual(code, 0, again + err)
        self.assertEqual(snapshot(self.tmp), before)

    def test_an_unreadable_receipt_is_replaced_only_under_repair_with_the_old_bytes_kept(self):
        self.assertEqual(self.apply()[0], 0)
        (self.server / fi.RECEIPT).write_bytes(b'not json')
        before = snapshot(self.server)
        code, out, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn('receipt_invalid', err)
        self.assertIn('--repair', err)
        self.assertEqual(snapshot(self.server), before)
        code, out, err = self.apply('--repair')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.receipt()['schema'], 1)
        self.assertEqual(self.receipt()['repairs'][-1]['rows'][0]['kind'], 'receipt')
        kept = [b.read_bytes() for b in (self.server / fi.BACKUP_DIR / self.latest_run()).rglob(fi.RECEIPT)]
        self.assertEqual(kept, [b'not json'])
        # The repair entry names the run whose backup folder holds the old bytes (the journal exists by then).
        self.assertEqual(self.receipt()['repairs'][-1]['run'], self.latest_run())
        self.assertEqual(self.run_cli('--check')[0], 0)

    def test_an_interrupted_run_is_recovered_and_recorded_in_the_repair_receipt(self):
        class Crash(BaseException):
            pass
        planner = fi.PLANNERS['launcher']

        def wrapped(ctx, analysis):
            status, lines, action = planner(ctx, analysis)

            def crash():
                action()
                raise Crash()
            return status, lines, crash if action else None
        with mock.patch.dict(fi.PLANNERS, {'launcher': wrapped}):
            with self.assertRaises(Crash):
                self.apply()
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertEqual([r['kind'] for r in self.receipt()['repairs'][-1]['rows']], ['interrupted'])
        self.assertEqual(self.run_cli('--check')[0], 0)


class WaveCRoundTwoTests(InstallerCase):
    """Opus review fixes for the friend installer on synthetic trees; nothing here runs DayZ or a real server."""
    inject_after = RunRollbackTests.inject_after
    tuned_server = SelfHealingTests.tuned_server
    upgraded_bundle = SelfHealingTests.upgraded_bundle
    latest_run = SelfHealingTests.latest_run
    receipt = SelfHealingTests.receipt

    def bundle_launcher(self):
        return (self.bundle / 'start-server.bat').read_bytes()

    def operator_launcher(self):
        return self.bundle_launcher().replace(b'-port=2302', b'-port=2999 -cpuCount=4')

    # P1: a run-created folder the server wrote into

    def test_a_server_written_file_in_a_run_created_folder_keeps_the_folder_and_the_rollback_completes(self):
        before = live_snapshot(self.server)
        self.assertEqual(self.apply()[0], 0)
        run = self.latest_run()
        folder = self.server / 'profiles/HollowCountry/Events'
        self.assertTrue(folder.is_dir())
        runtime = put(folder, 'runtime-state.json', '{"written": "by the server"}')
        code, out, err = self.run_cli('--rollback', run)
        self.assertEqual(code, 0, out + err)
        self.assertIn('kept non-empty folder profiles/HollowCountry/Events', out)
        mid = live_snapshot(self.server)
        code, out, err = self.run_cli('--rollback', run, '--apply')
        self.assertEqual(code, 0, out + err)
        self.assertIn('kept non-empty folder profiles/HollowCountry/Events', out)
        self.assertIn(fi.ROLLBACK_OK, out)
        self.assertEqual(runtime.read_text(), '{"written": "by the server"}')
        self.assertFalse((self.server / 'profiles/HollowCountry/Events/settings.json').exists())
        journal = json.loads((self.server / fi.BACKUP_DIR / run / fi.JOURNAL).read_text())
        self.assertEqual(journal['state'], 'rolled-back')
        self.assertNotEqual(live_snapshot(self.server), mid)
        # Nothing is wedged: a later install and check work, and the server's file is still there.
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual(self.run_cli('--check')[0], 0)
        self.assertTrue(runtime.is_file())
        self.assertNotEqual(live_snapshot(self.server), before)

    def test_a_kept_folder_does_not_hide_a_real_conflict_and_nothing_changes_then(self):
        self.assertEqual(self.apply()[0], 0)
        run = self.latest_run()
        put(self.server, 'profiles/HollowCountry/Events/runtime-state.json', '{}')
        (self.server / '@HollowCountry/mod.cpp').write_bytes(b'EDITED LATER')
        before = live_snapshot(self.server)
        code, out, err = self.run_cli('--rollback', run, '--apply')
        self.assertEqual(code, 2, out + err)
        self.assertIn('rollback_conflict', err)
        self.assertEqual(live_snapshot(self.server), before)
        journal = json.loads((self.server / fi.BACKUP_DIR / run / fi.JOURNAL).read_text())
        self.assertEqual(journal['state'], 'complete')

    # P2: an interrupted --rollback is finished by --rollback on that run only

    def test_an_interrupted_rollback_resumes_with_rollback_and_installs_nothing(self):
        before = live_snapshot(self.server)
        self.assertEqual(self.apply()[0], 0)
        run = self.latest_run()
        original, calls = fi.restore_change, []

        def fail_on_second(ctx, change):
            calls.append(change)
            if len(calls) == 2:
                raise PermissionError('synthetic locked file')
            return original(ctx, change)
        with mock.patch.object(fi, 'restore_change', fail_on_second):
            code, out, err = self.run_cli('--rollback', run, '--apply')
        self.assertEqual(code, 2, out + err)
        self.assertIn('rollback_pending', err)
        self.assertIn('--rollback %s --apply' % run, err)
        journal_path = self.server / fi.BACKUP_DIR / run / fi.JOURNAL
        self.assertEqual(json.loads(journal_path.read_text())['state'], 'rollback_pending')
        runs = sorted(p.name for p in (self.server / fi.BACKUP_DIR).iterdir())
        code, out, err = self.run_cli('--check')
        self.assertEqual(code, 1, out + err)
        self.assertIn('--rollback %s --apply' % run, out)
        # The dry run of the resume changes nothing and says it is a resume.
        mid = snapshot(self.server)
        code, out, err = self.run_cli('--rollback', run)
        self.assertEqual(code, 0, out + err)
        self.assertIn('Resuming the rollback', out)
        self.assertEqual(snapshot(self.server), mid)
        code, out, err = self.run_cli('--rollback', run, '--apply')
        self.assertEqual(code, 0, out + err)
        self.assertIn(fi.ROLLBACK_OK, out)
        self.assertNotIn('Install finished', out)
        self.assertEqual(live_snapshot(self.server), before)
        self.assertEqual(sorted(p.name for p in (self.server / fi.BACKUP_DIR).iterdir()), runs)
        self.assertEqual(json.loads(journal_path.read_text())['state'], 'rolled-back')
        self.assertEqual(self.apply()[0], 0)

    def test_rollback_of_another_run_is_refused_while_a_different_run_is_pending(self):
        class Crash(BaseException):
            pass
        self.assertEqual(self.apply()[0], 0)
        done = self.latest_run()
        journal = self.server / fi.BACKUP_DIR / done / fi.JOURNAL
        self.assertEqual(json.loads(journal.read_text())['state'], 'complete')
        with self.inject_after('overlay', Crash()):
            with self.assertRaises(Crash):
                self.apply(bundle=self.upgraded_bundle())
        pending = self.latest_run()
        self.assertNotEqual(pending, done)
        before = snapshot(self.server)
        code, out, err = self.run_cli('--rollback', done, '--apply')
        self.assertEqual(code, 2, out + err)
        self.assertIn('install_interrupted', err)
        self.assertEqual(snapshot(self.server), before)
        self.assertEqual(json.loads(journal.read_text())['state'], 'complete')

    # P2: --repair merges an edited launcher instead of replacing it

    def test_merge_launcher_keeps_every_other_byte_and_takes_only_the_mod_values(self):
        bundle = (b'@echo off\r\nstart "" DayZServer_x64.exe -config=serverDZ.cfg -port=2302 '
                  b'"-mod=@A;@B" "-serverMod=@S" -dologs\r\n')
        current = (b'@echo off\r\nrem -mod=@Ignored\r\nstart "" DayZServer_x64.exe -config=my.cfg -port=2999 '
                   b'-cpuCount=4 "-mod=@A" -profiles=data\r\n')
        merged, changes = fi.merge_launcher(current, bundle)
        self.assertEqual(merged, (b'@echo off\r\nrem -mod=@Ignored\r\nstart "" DayZServer_x64.exe -config=my.cfg '
                                  b'-port=2999 -cpuCount=4 "-mod=@A;@B" "-serverMod=@S" -profiles=data\r\n'))
        self.assertEqual(len(changes), 2)
        self.assertEqual(fi.merge_launcher(merged, bundle), (merged, []))
        self.assertIsNone(fi.merge_launcher(b'echo no mods here\r\n', bundle))
        self.assertIsNone(fi.merge_launcher(b'\xff\xfe', bundle))

    def test_an_edited_launcher_is_merged_under_repair_with_a_preview_backup_and_no_wholesale_replace(self):
        self.assertEqual(self.apply()[0], 0)
        launcher = self.server / 'start-server.bat'
        stale = self.operator_launcher().replace(b'"-mod=@CF;', b'"-mod=@Mine;@CF;')
        launcher.write_bytes(stale)
        before = snapshot(self.server)
        code, out, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn('--repair', err)
        self.assertEqual(snapshot(self.server), before)
        code, preview, err = self.run_cli('--repair')
        self.assertEqual(code, 0, preview + err)
        self.assertEqual(snapshot(self.server), before)
        self.assertIn('would repair  edited  start-server.bat', preview)
        self.assertIn('      kept    -mod @Mine (not managed by this installer)', preview)
        self.assertNotIn('      - ', preview)
        code, applied, err = self.apply('--repair')
        self.assertEqual(code, 0, applied + err)
        self.assertEqual(launcher.read_bytes(), with_mods(self.operator_launcher(), '@Mine'))
        saved = [b.read_bytes() for b in (self.server / fi.BACKUP_DIR / self.latest_run()).rglob('start-server.bat')]
        self.assertEqual(saved, [stale])
        rows = [r for r in self.receipt()['repairs'][-1]['rows'] if r['path'] == 'start-server.bat']
        self.assertEqual([r['kind'] for r in rows], ['edited'])
        self.assertIn('  repaired  edited  start-server.bat: %s' % rows[0]['detail'], applied)
        code, checked, err = self.run_cli('--check')
        self.assertEqual(code, 0, checked + err)
        self.assertIn(', then 1 of your own)', checked)  # the operator's @Mine follows the bundle folders
        # Idempotent: the merged launcher is the operator's, kept on later runs, with or without --repair.
        before = snapshot(self.tmp)
        for extra in ((), ('--repair',)):
            code, again, err = self.apply(*extra)
            self.assertEqual(code, 0, again + err)
            self.assertEqual(snapshot(self.tmp), before)
        self.assertEqual(launcher.read_bytes(), with_mods(self.operator_launcher(), '@Mine'))

    def test_a_launcher_with_the_right_mod_values_and_other_edits_is_kept_without_repair(self):
        self.assertEqual(self.apply()[0], 0)
        launcher = self.server / 'start-server.bat'
        launcher.write_bytes(self.operator_launcher())
        before = snapshot(self.server)
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(snapshot(self.server), before)
        self.assertEqual(self.run_cli('--check')[0], 0)

    def test_a_merged_launcher_is_merged_again_by_a_later_bundle_not_replaced(self):
        self.assertEqual(self.apply()[0], 0)
        launcher = self.server / 'start-server.bat'
        launcher.write_bytes(self.operator_launcher().replace(b'"-mod=@CF;', b'"-mod=@Mine;@CF;'))
        self.assertEqual(self.apply('--repair')[0], 0)
        newer = self.upgraded_bundle()
        put(newer, 'start-server.bat', (newer / 'start-server.bat').read_bytes().replace(b'-dologs', b'-dologs -newflag'))
        write_manifest(newer)
        code, out, err = self.apply(bundle=newer)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(launcher.read_bytes(), with_mods(self.operator_launcher(), '@Mine'))

    def test_an_unmergeable_edited_launcher_stays_a_refusal_even_with_repair(self):
        self.assertEqual(self.apply()[0], 0)
        launcher = self.server / 'start-server.bat'
        launcher.write_bytes(b'echo mine\r\n')
        before = snapshot(self.server)
        code, preview, err = self.run_cli('--repair')
        self.assertEqual(code, 0, preview + err)
        self.assertIn('blocked  launcher  start-server.bat', preview)
        code, out, err = self.apply('--repair')
        self.assertEqual(code, 2)
        self.assertIn('refused: launcher', err)
        self.assertIn('no -mod= argument', err)
        self.assertEqual(snapshot(self.server), before)

    def test_the_installer_bat_does_not_pass_repair(self):
        bat = (ROOT / 'tools/setup/install-hollow-country.bat').read_text(encoding='utf-8')
        self.assertNotIn('--repair', bat)

    def test_blocked_repair_rows_in_an_interactive_run_ask_and_proceed_as_repair_only_on_yes(self):
        self.assertEqual(self.apply()[0], 0)
        pbo = self.server / '@HollowCountry/addons/hollowcountry.pbo'
        pbo.write_bytes(b'EDITED')
        before = snapshot(self.server)
        code, out, err = self.run_cli(answers=lambda prompt: 'n')
        self.assertEqual(code, 0, out + err)
        self.assertIn('repair these (each backed up)? [y/N]: ', self.prompts)
        self.assertNotIn('Apply these changes now? [y/N]: ', self.prompts)
        self.assertEqual(snapshot(self.server), before)
        code, out, err = self.run_cli(answers=lambda prompt: 'y')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(pbo.read_bytes(), b'PBO')
        saved = [b.read_bytes() for b in (self.server / fi.BACKUP_DIR / self.latest_run()).rglob('hollowcountry.pbo')]
        self.assertEqual(saved, [b'EDITED'])
        self.assertEqual(self.receipt()['repairs'][-1]['rows'][0]['kind'], 'edited')
        # With nothing blocked the usual question is asked and --repair is not implied.
        self.run_cli(answers=lambda prompt: 'n')
        self.assertIn('Apply these changes now? [y/N]: ', self.prompts)
        self.assertNotIn('repair these (each backed up)? [y/N]: ', self.prompts)

    # P2: a hard exit inside a mission writer

    def crash_inside_the_mission_writer(self, bundle=None):
        class Crash(BaseException):
            pass
        regular = fi.overlays.main.side_effect
        armed = []
        original = ws.write_json_atomic

        def partial(argv):
            if argv[0] == 'bundle-apply':
                put(self.mission, 'cfgeconomycore.xml', '<partial/>')
                put(self.mission, 'hollow-country/new/deep/file.json', '{}')
                put(self.mission, 'hollow-country-bundle/receipt.json', '{"partial":true}')
                armed.append(True)
                raise Crash()
            return regular(argv)

        def lost_write(target, data):
            # The process is gone: nothing after the helper's last instruction reaches the journal.
            if armed and Path(target).name == fi.JOURNAL:
                raise Crash()
            return original(target, data)
        with mock.patch.object(fi.overlays, 'main', side_effect=partial), \
                mock.patch.object(ws, 'write_json_atomic', lost_write):
            with self.assertRaises(Crash):
                self.apply(bundle=bundle)
        journals = [j for j in (self.server / fi.BACKUP_DIR).rglob(fi.JOURNAL)
                    if json.loads(j.read_text())['state'] != 'complete']
        self.assertEqual(len(journals), 1)
        rows = [r for r in json.loads(journals[0].read_text())['entries'] if r['kind'] == 'tree']
        self.assertTrue(rows and rows[0].get('writing'), 'the tree writer marker must be journaled before the helper')

    def test_a_hard_exit_inside_the_mission_writer_needs_repair_and_then_restores_the_whole_tree(self):
        before = live_snapshot(self.server)
        self.crash_inside_the_mission_writer()
        crashed = self.latest_run()
        code, out, err = self.run_cli('--check')
        self.assertEqual(code, 1, out + err)
        self.assertIn('hard exit', out)
        # Without --repair recovery refuses, says why and names the flag; nothing is changed.
        mid = live_snapshot(self.server)
        code, out, err = self.apply()
        self.assertEqual(code, 2, out + err)
        self.assertIn('rollback_pending', err)
        self.assertIn('hard exit', err)
        self.assertIn('--repair', err)
        self.assertEqual(live_snapshot(self.server), mid)
        code, out, err = self.apply('--repair')
        self.assertEqual(code, 0, out + err)
        self.assertIn('Recovered interrupted install', out)
        self.assertEqual((self.mission / 'cfgeconomycore.xml').read_text(), '<economycore/>')
        self.assertFalse((self.mission / 'hollow-country/new').exists())
        self.assertEqual((self.mission / 'storage_1/data/players.db').read_text(), 'SAVED PLAYERS')
        stash = list((self.server / fi.BACKUP_DIR).rglob(fi.STASH_PREFIX + '*'))
        self.assertEqual([s.name for s in stash], [fi.STASH_PREFIX + crashed])
        self.assertIn('Kept a copy of the cut-off mission folder before restoring it: ', out)
        self.assertIn(stash[0].name, out)
        self.assertEqual(list((self.server / fi.BACKUP_DIR).rglob(fi.STASH_TEMP + '*')), [])
        self.assertEqual((stash[0] / 'mpmissions' / MISSION / 'cfgeconomycore.xml').read_text(), '<partial/>')
        self.assertEqual(self.run_cli('--check')[0], 0)
        self.assertNotEqual(live_snapshot(self.server), before)

    def test_a_hard_exit_in_an_interactive_run_asks_before_restoring_the_tree(self):
        self.crash_inside_the_mission_writer()
        code, out, err = self.run_cli('--apply', answers=lambda prompt: 'n')
        self.assertEqual(code, 2, out + err)
        self.assertIn('repair these (each backed up)? [y/N]: ', self.prompts)
        self.assertEqual((self.mission / 'cfgeconomycore.xml').read_text(), '<partial/>')
        code, out, err = self.run_cli('--apply', answers=lambda prompt: 'y')
        self.assertEqual(code, 0, out + err)
        self.assertIn('Recovered interrupted install', out)
        self.assertEqual(self.run_cli('--check')[0], 0)

    def test_the_marker_is_cleared_when_the_writer_returns_so_a_normal_failure_needs_no_repair(self):
        with self.inject_after('overlay', fi.Refused('injected', 'late refusal')):
            code, out, err = self.apply()
        self.assertEqual(code, 2, out + err)
        self.assertIn(fi.ROLLBACK_OK, err)
        for journal in (self.server / fi.BACKUP_DIR).rglob(fi.JOURNAL):
            rows = json.loads(journal.read_text())['entries']
            self.assertFalse([r for r in rows if r.get('writing')])

    # P3

    def reset_edits(self):
        """The operator puts RespawnTypes back at its stock value (and tunes IdleModeCountdown); every expectation is
        derived from the real scaler and the stock file."""
        stock = values_of(GLOBALS_STOCK)['RespawnTypes']
        first = boosted_values(2.0)['RespawnTypes']
        self.assertNotEqual(first, stock)
        return [(var_tag('RespawnTypes', first), var_tag('RespawnTypes', stock)), (b'value="60"', b'value="90"')], stock

    def test_a_loot_boosted_variable_back_at_its_stock_value_is_a_reset_and_the_boost_returns(self):
        edits, _stock = self.reset_edits()
        path = self.tuned_server(edits)
        newer = self.upgraded_bundle()
        code, out, err = self.run_cli(bundle=newer)
        self.assertEqual(code, 0, out + err)
        self.assertIn('WARN  globals  RespawnTypes is back at its stock value', out)
        self.assertIn('IdleModeCountdown 60 -> 90', out)
        self.assertEqual(self.apply(bundle=newer)[0], 0)
        values = var_values(path)
        self.assertEqual(values['RespawnTypes'], boosted_values(3.0)['RespawnTypes'])  # the new boost, not stock kept as tuning
        self.assertEqual(values['IdleModeCountdown'], '90')

    def test_a_reset_without_a_new_bundle_gets_the_boost_value_back_with_a_repair_row(self):
        edits, _stock = self.reset_edits()
        path = self.tuned_server(edits)
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        values = var_values(path)
        self.assertEqual((values['RespawnTypes'], values['IdleModeCountdown']),
                         (boosted_values(2.0)['RespawnTypes'], '90'))
        self.assertEqual(self.receipt()['repairs'][-1]['rows'][0]['kind'], 'globals')
        before = snapshot(self.tmp)
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual(snapshot(self.tmp), before)

    def test_the_whole_file_put_back_to_stock_is_read_like_one_stock_variable(self):
        # The same reset line and the same outcome as a single variable put back (see the test above): the boost
        # value returns, every other stock value stays.
        whole = self.tuned_server([])
        whole.write_bytes(GLOBALS_STOCK)
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, out + err)
        self.assertIn('WARN  globals  RespawnTypes is back at its stock value', out)
        self.assertNotIn('blocked', out.lower())
        self.assertEqual(self.apply()[0], 0)
        expected = dict(values_of(GLOBALS_STOCK), RespawnTypes=boosted_values(2.0)['RespawnTypes'])
        self.assertEqual(var_values(whole), expected)
        self.assertEqual(self.receipt()['repairs'][-1]['rows'][0]['kind'], 'globals')

    def test_keep_stock_globals_records_an_opt_out_and_the_boost_never_returns_for_that_variable(self):
        edits, stock = self.reset_edits()
        path = self.tuned_server(edits)
        code, out, err = self.apply('--keep-stock-globals')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.receipt()['globals_optout'], ['RespawnTypes'])
        values = var_values(path)
        self.assertEqual((values['RespawnTypes'], values['IdleModeCountdown']), (stock, '90'))
        # Later runs, with and without a new overlay bundle and without the flag, keep the stock value.
        newer = self.upgraded_bundle()
        code, preview, err = self.run_cli(bundle=newer)
        self.assertEqual(code, 0, preview + err)
        self.assertIn('RespawnTypes stays at its stock value: you opted out', preview)
        self.assertNotIn('is back at its stock value', preview)
        for bundle in (self.bundle, newer):
            code, out, err = self.apply(bundle=bundle)
            self.assertEqual(code, 0, out + err)
            self.assertEqual(var_values(path)['RespawnTypes'], stock)
            self.assertEqual(self.receipt()['globals_optout'], ['RespawnTypes'])
        self.assertEqual(self.run_cli('--check')[0], 0)

    def test_a_receipt_with_another_schema_is_never_rebuilt_by_repair(self):
        self.assertEqual(self.apply()[0], 0)
        (self.server / fi.RECEIPT).write_text(json.dumps({'schema': 99, 'files': {}}))
        before = snapshot(self.server)
        code, out, err = self.apply('--repair')
        self.assertEqual(code, 2)
        self.assertIn('receipt_invalid', err)
        self.assertIn('unknown layout', err)
        self.assertEqual(snapshot(self.server), before)

    def test_an_unrecorded_file_replaced_by_yes_has_a_preview_row_and_a_receipt_row(self):
        put(self.server, '@HollowCountry/mod.cpp', 'name = "Mine";\n')
        code, preview, err = self.run_cli()
        self.assertEqual(code, 0, preview + err)
        self.assertIn('would repair  unrecorded  @HollowCountry/mod.cpp', preview)
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        rows = self.receipt()['repairs'][-1]['rows']
        self.assertEqual([r['kind'] for r in rows if r['path'] == '@HollowCountry/mod.cpp'], ['unrecorded'])
        for row in rows:
            self.assertIn('  repaired  %s  %s: %s' % (row['kind'], row['path'], row['detail']), out)
        saved = [b.read_bytes() for b in (self.server / fi.BACKUP_DIR / self.latest_run()).rglob('mod.cpp')]
        self.assertEqual(saved, [b'name = "Mine";\n'])


    # Round 3: the launcher lists are merged, never replaced or rebuilt

    BUNDLE_LAUNCHER = (b'@echo off\r\nstart "" DayZServer_x64.exe -port=2302 "-mod=@CF;@HollowCountry;@New" '
                       b'"-serverMod=@S" -dologs\r\n')

    def merged_lists(self, merged):
        text = merged.decode('utf-8')
        return {name: fi.launcher_entries(text[start:end]) for name, start, end, _q in fi.launcher_args(text)}

    def test_a_quoted_mod_value_with_spaces_is_one_token_and_is_never_split(self):
        current = (b'start "" DayZServer_x64.exe "-mod=@CF;@Base Building Plus;@HollowCountry" -profiles=data\r\n')
        merged, changes = fi.merge_launcher(current, self.BUNDLE_LAUNCHER)
        bundle_list = fi.parse_mod_list(self.BUNDLE_LAUNCHER.decode())
        lists = self.merged_lists(merged)
        self.assertEqual(lists['mod'], bundle_list + ['@Base Building Plus'])
        self.assertEqual(lists['servermod'], ['@S'])
        self.assertTrue(merged.startswith(b'start "" DayZServer_x64.exe "-mod='))
        self.assertTrue(merged.endswith(b' -profiles=data\r\n'))
        self.assertEqual(fi.merge_launcher(merged, self.BUNDLE_LAUNCHER), (merged, []))
        # The quote may also follow the equals sign.
        other = b'start x -mod="@CF;@Base Building Plus;@HollowCountry" -profiles=data\r\n'
        merged, _changes = fi.merge_launcher(other, self.BUNDLE_LAUNCHER)
        self.assertEqual(self.merged_lists(merged)['mod'], bundle_list + ['@Base Building Plus'])
        self.assertIn(b'-mod="@CF;', merged)

    def test_operator_mods_and_the_operator_server_mod_list_are_kept_after_the_bundle_folders(self):
        operators = ['@Operator%d' % number for number in range(13)]
        current = ('start "" DayZServer_x64.exe -port=2999 "-mod=@CF;%s;@HollowCountry" "-serverMod=@OperatorServerSide" '
                   '-cpuCount=4\r\n' % ';'.join(operators)).encode()
        merged, changes = fi.merge_launcher(current, self.BUNDLE_LAUNCHER)
        lists = self.merged_lists(merged)
        bundle_mods = fi.parse_mod_list(self.BUNDLE_LAUNCHER.decode())
        self.assertEqual(lists['mod'], bundle_mods + operators)
        self.assertEqual(lists['servermod'], ['@S', '@OperatorServerSide'])
        self.assertIn(b'-port=2999', merged)
        self.assertIn(b'-cpuCount=4', merged)
        shown_lines = fi.launcher_change_lines(changes)
        for name in operators + ['@OperatorServerSide']:
            self.assertIn('kept    ' + ('-serverMod ' if name == '@OperatorServerSide' else '-mod ') + name
                          + ' (not managed by this installer)', shown_lines)
        self.assertIn('added   -mod @New', shown_lines)
        self.assertIn('added   -serverMod @S', shown_lines)
        self.assertEqual(fi.merge_launcher(merged, self.BUNDLE_LAUNCHER), (merged, []))

    def test_retired_folders_are_removed_and_names_match_ignoring_case(self):
        retired = fi.retired_folders()
        self.assertTrue(retired)
        current = ('start x "-mod=@cf;%s;@Mine;@hollowcountry" -dologs\r\n' % ';'.join(retired)).encode()
        merged, changes = fi.merge_launcher(current, self.BUNDLE_LAUNCHER, retired)
        bundle_mods = fi.parse_mod_list(self.BUNDLE_LAUNCHER.decode())
        self.assertEqual(self.merged_lists(merged)['mod'], bundle_mods + ['@Mine'])
        lines = fi.launcher_change_lines(changes)
        for name in retired:
            self.assertIn('removed -mod %s (retired by this bundle)' % name, lines)
        self.assertNotIn('kept    -mod @cf (not managed by this installer)', lines)
        # A retired folder the bundle itself lists again is the bundle's, not removed.
        again, _changes = fi.merge_launcher(current, self.BUNDLE_LAUNCHER.replace(b'@New', retired[0].encode()), retired)
        self.assertIn(retired[0], self.merged_lists(again)['mod'])

    def test_a_launcher_that_cannot_be_merged_names_the_reason(self):
        for label, data in (('no mods', b'echo mine\r\n'), ('not utf-8', b'\xff\xfe start -mod=@A'),
                            ('batch variable', b'start x -mod=%MODS% -dologs\r\n'),
                            ('unclosed quote', b'start x "-mod=@A -dologs\r\n')):
            with self.subTest(label):
                self.assertIsNone(fi.merge_launcher(data, self.BUNDLE_LAUNCHER))
                self.assertTrue(fi.launcher_problem(data, self.BUNDLE_LAUNCHER))

    def test_repair_and_yes_never_replace_a_launcher_that_cannot_be_merged_recorded_or_not(self):
        cases = (('no-mods', b'echo mine\r\n'), ('not-utf8', b'\xff\xfe start -mod=@A\r\n'),
                 ('variable', b'start x -mod=%MODS% -dologs\r\n'), ('unclosed', b'start x "-mod=@A -dologs\r\n'))
        for recorded in (True, False):
            for label, data in cases:
                with self.subTest(recorded=recorded, case=label):
                    self.server = self.tmp / ('server-%s-%s' % (recorded, label))
                    self.mission = self.make_server(self.server)
                    if recorded:
                        self.assertEqual(self.apply()[0], 0)
                    (self.server / 'start-server.bat').write_bytes(data)
                    before = live_snapshot(self.server)
                    for extra in ((), ('--repair',)):
                        code, out, err = self.apply(*extra)
                        self.assertEqual(code, 2, out + err)
                        self.assertIn('refused: launcher', err)
                        self.assertIn('never replace a launcher wholesale', err)
                        self.assertEqual((self.server / 'start-server.bat').read_bytes(), data)
                        self.assertEqual(live_snapshot(self.server), before)

    # Round 3: a rollback after a retire step restores the retired folders

    def test_a_refusal_after_the_retired_folders_were_removed_restores_them_and_a_later_apply_works(self):
        retired = ws.load_manifest()['retired']
        self.assertEqual(self.apply()[0], 0)
        path = self.server / ws.RECEIPT_NAME
        receipt = json.loads(path.read_text())
        files = {e['path']: e for e in receipt['files']}
        dirs = set(receipt['dirs'])
        for item in retired:
            top = item['folder']
            dirs |= {top, top + '/addons', top + '/keys'}
            for rel, data in ((top + '/addons/old.pbo', b'OLDPBO-' + item['id'].encode()),
                              (top + '/keys/old.bikey', b'OLDKEY-' + item['id'].encode()),
                              (top + '/meta.cpp', b'publishedid = %s;\n' % item['id'].encode())):
                put(self.server, rel, data)
                files[rel] = {'path': rel, 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data), 'item': item['id']}
        path.write_bytes(ws.json_bytes(ws.receipt_data(files, dirs)))
        before = live_snapshot(self.server)
        self.assertTrue([k for k in before if k.startswith(retired[0]['folder'])])
        with self.inject_after('weapons', fi.Refused('injected', 'after the retire step')):
            code, out, err = self.apply()
        self.assertEqual(code, 2, out + err)
        self.assertIn('rolled back: the server is as it was before this run', err)
        self.assertEqual(live_snapshot(self.server), before)
        for item in retired:
            self.assertTrue((self.server / item['folder'] / 'addons/old.pbo').is_file())
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        for item in retired:
            self.assertFalse((self.server / item['folder']).exists())

    # Round 3: a typed y at the hard-exit prompt restores the tree and nothing else

    def test_y_at_the_hard_exit_prompt_does_not_turn_on_repair(self):
        self.assertEqual(self.apply()[0], 0)
        newer = self.upgraded_bundle()
        self.crash_inside_the_mission_writer(bundle=newer)
        pbo = self.server / '@HollowCountry/addons/hollowcountry.pbo'
        bikey = self.server / 'keys/hollowcountry.bikey'
        launcher = self.server / 'start-server.bat'
        pbo.write_bytes(b'EDITED')
        bikey.write_bytes(b'MY KEY')
        stale = self.operator_launcher().replace(b'"-mod=@CF;', b'"-mod=@Mine;@CF;')
        launcher.write_bytes(stale)
        asked = []

        def answers(prompt):
            asked.append(prompt)
            return 'y' if len(asked) == 1 and 'repair these' in prompt else 'n'
        code, out, err = self.run_cli('--apply', answers=answers, bundle=newer)
        self.assertIn('Recovered interrupted install', out)
        self.assertEqual((self.mission / 'cfgeconomycore.xml').read_text(), '<economycore/>')
        self.assertFalse((self.mission / 'hollow-country/new').exists())
        # Edited files and the launcher are exactly as the operator left them: the y was not --repair.
        self.assertEqual(pbo.read_bytes(), b'EDITED')
        self.assertEqual(bikey.read_bytes(), b'MY KEY')
        self.assertEqual(launcher.read_bytes(), stale)
        self.assertNotIn('repaired  ', out)
        self.assertNotIn('repairs', self.receipt())

    # Round 3: the stash is one per attempt, complete before it is named, and a retry loses nothing

    def test_a_stash_copy_that_fails_halfway_leaves_no_stash_and_a_retry_keeps_the_operator_edits(self):
        self.crash_inside_the_mission_writer()
        crashed = self.latest_run()
        root = self.server / fi.BACKUP_DIR / crashed
        real = shutil.copytree

        def half(src, dst, *args, **kwargs):
            if fi.STASH_TEMP in str(dst):
                Path(dst).mkdir(parents=True)
                (Path(dst) / 'half-copied.txt').write_text('partial')
                raise OSError('disk full')
            return real(src, dst, *args, **kwargs)
        with mock.patch.object(fi.shutil, 'copytree', side_effect=half):
            code, out, err = self.apply('--repair')
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual((self.mission / 'cfgeconomycore.xml').read_text(), '<partial/>')
        self.assertEqual([p for p in root.glob(fi.STASH_PREFIX + '*')], [])
        code, out, err = self.apply('--repair')
        self.assertEqual(code, 0, out + err)
        stash = root / (fi.STASH_PREFIX + crashed)
        self.assertEqual((stash / 'mpmissions' / MISSION / 'cfgeconomycore.xml').read_text(), '<partial/>')
        self.assertFalse((stash / 'half-copied.txt').exists())
        self.assertEqual(list(root.glob(fi.STASH_TEMP + '*')), [])
        self.assertIn('Kept a copy of the cut-off mission folder before restoring it: ', out)
        self.assertEqual((self.mission / 'cfgeconomycore.xml').read_text(), '<economycore/>')

    def test_each_recovery_attempt_makes_its_own_stash_and_never_replaces_an_earlier_one(self):
        self.crash_inside_the_mission_writer()
        crashed = self.latest_run()
        root = self.server / fi.BACKUP_DIR / crashed
        with mock.patch.object(fi, 'restore_change', side_effect=OSError('locked')):
            code, out, err = self.apply('--repair')
        self.assertNotEqual(code, 0, out + err)
        first = root / (fi.STASH_PREFIX + crashed)
        self.assertTrue(first.is_dir())
        (self.mission / 'cfgeconomycore.xml').write_text('<edited again/>')
        with mock.patch.object(fi, 'restore_change', side_effect=OSError('locked')):
            code, out, err = self.apply('--repair')
        self.assertNotEqual(code, 0, out + err)
        second = root / (fi.STASH_PREFIX + crashed + '-2')
        self.assertTrue(second.is_dir())
        self.assertEqual((first / 'mpmissions' / MISSION / 'cfgeconomycore.xml').read_text(), '<partial/>')
        self.assertEqual((second / 'mpmissions' / MISSION / 'cfgeconomycore.xml').read_text(), '<edited again/>')
        self.assertEqual(self.apply('--repair')[0], 0)

    # Round 3: receipts, paths and the journal

    def test_a_receipt_that_cannot_be_opened_is_never_rebuilt_but_a_damaged_one_is(self):
        self.assertEqual(self.apply()[0], 0)
        path = self.server / fi.RECEIPT
        path.unlink()
        path.mkdir()  # reading it raises an OSError (not a damaged file)
        before = snapshot(self.server)
        for extra in ((), ('--repair',)):
            code, out, err = self.apply(*extra)
            self.assertEqual(code, 2, out + err)
            self.assertIn('receipt_unreadable', err)
            self.assertEqual(snapshot(self.server), before)
        path.rmdir()
        path.write_bytes(b'\xff\xfe not text')
        code, out, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn('receipt_invalid', err)
        self.assertEqual(self.apply('--repair')[0], 0)
        self.assertEqual(json.loads(path.read_text())['schema'], fi.SCHEMA)
        self.assertNotEqual(path.read_bytes(), b'\xff\xfe not text')

    def test_journal_rows_are_found_ignoring_case_and_a_missing_row_is_a_refusal_not_a_stop_iteration(self):
        row = {'path': 'mpmissions/' + MISSION, 'kind': 'tree', 'written': {}}
        ctx = mock.Mock(journal={'entries': [row]}, backup_root=self.tmp)
        self.assertIs(fi.journal_row(ctx, 'MPMissions/' + MISSION.upper()), row)
        with self.assertRaises(fi.Refused) as caught:
            fi.journal_row(ctx, 'somewhere/else')
        self.assertEqual(caught.exception.code, 'journal_invalid')
        with mock.patch.object(fi, 'track_target'), mock.patch.object(ws, 'write_json_atomic'):
            fi.record_written(ctx, 'MPMISSIONS/' + MISSION + '/Db/Globals.xml', 'a' * 64)
        self.assertEqual(row['written'], {'Db/Globals.xml': ['a' * 64]})


def with_mods(launcher, *extras):
    """The launcher bytes with the operator's extra mods appended to the -mod= list the bundle wrote."""
    listed = ';'.join(fi.parse_mod_list(launcher.decode('utf-8')))
    assert ('-mod=' + listed).encode() in launcher
    return launcher.replace(('-mod=' + listed).encode(), ('-mod=' + ';'.join([listed, *extras])).encode(), 1)


def live_snapshot_of(rows):
    return {rel: value for rel, value in rows.items()
            if rel != fi.BACKUP_DIR and not rel.startswith(fi.BACKUP_DIR + '/')}


class RoundFourTests(InstallerCase):
    """Opus round-3 review fixes (launcher merge ownership, path-form entries, comments, receipts) on synthetic trees."""
    inject_after = RunRollbackTests.inject_after
    tuned_server = SelfHealingTests.tuned_server
    upgraded_bundle = SelfHealingTests.upgraded_bundle
    latest_run = SelfHealingTests.latest_run
    receipt = SelfHealingTests.receipt
    reset_edits = WaveCRoundTwoTests.reset_edits
    crash_inside_the_mission_writer = WaveCRoundTwoTests.crash_inside_the_mission_writer
    seed_old_install = RetiredDependencyTests.seed_old_install
    BUNDLE = (b'start "" DayZServer_x64.exe -port=2302 "-mod=@CF;@COT;@HollowCountry" "-serverMod=@S" -dologs\r\n')
    BUNDLE_AB = (b'@echo off\r\nstart "" DayZServer_x64.exe -port=2302 "-mod=@CF;@HollowCountry;@New" '
                 b'"-serverMod=@S" -dologs\r\n')

    def setUp(self):
        super().setUp()
        self.retired = ws.load_manifest()['retired']

    def lists(self, data):
        text = data.decode('utf-8')
        return {name: fi.launcher_entries(text[start:end]) for name, start, end, _q in fi.launcher_args(text)}

    def live_launcher(self):
        return (self.server / 'start-server.bat').read_bytes()

    # Retired folders are removed only when this installer put them there

    def test_a_retired_folder_the_operator_brought_stays_in_the_mod_list_with_a_warning(self):
        self.assertEqual(self.apply()[0], 0)
        folder = self.retired[-1]['folder']
        put(self.server, folder + '/addons/own.pbo', b'the operator\'s own copy')
        bundle_mods = fi.parse_mod_list(self.live_launcher().decode())
        (self.server / 'start-server.bat').write_bytes(with_mods(self.live_launcher(), folder))
        code, out, err = self.apply('--repair')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lists(self.live_launcher())['mod'], bundle_mods + [folder])
        self.assertRegex(out, r'WARN\s+-mod %s is a retired' % re.escape(folder))
        self.assertTrue((self.server / folder / 'addons/own.pbo').is_file())
        before = snapshot(self.server)
        self.assertEqual(self.apply('--repair')[0], 0)
        self.assertEqual(snapshot(self.server), before)

    def test_retired_folders_this_installer_removed_leave_the_launcher_even_in_a_later_attempt(self):
        self.seed_old_install()
        bundle_mods = fi.parse_mod_list(self.live_launcher().decode())
        names = [item['folder'] for item in self.retired]
        (self.server / 'start-server.bat').write_bytes(with_mods(self.live_launcher(), *names, '@Mine'))
        # The launcher step does not run in the first attempt: the Workshop receipt no longer lists the folders, the
        # install receipt remembers, so the next run still removes them from the launcher.
        code, out, err = self.apply('--repair', '--skip', 'launcher')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.receipt()['retired_removed'], sorted(names))
        for name in names:
            self.assertFalse((self.server / name).exists())
        self.assertEqual(self.lists(self.live_launcher())['mod'], bundle_mods + names + ['@Mine'])
        code, out, err = self.apply('--repair')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lists(self.live_launcher())['mod'], bundle_mods + ['@Mine'])

    def test_retired_removed_is_forgotten_once_the_launcher_is_written_without_the_names(self):
        self.seed_old_install()
        names = [item['folder'] for item in self.retired]
        (self.server / 'start-server.bat').write_bytes(with_mods(self.live_launcher(), *names))
        self.assertEqual(self.apply('--repair')[0], 0)
        self.assertNotIn('retired_removed', self.receipt())

    def test_retired_removed_is_forgotten_when_the_launcher_is_already_done(self):
        self.seed_old_install()
        self.assertEqual(self.apply('--repair', '--skip', 'launcher')[0], 0)
        receipt = self.receipt()
        self.assertTrue(receipt['retired_removed'])
        self.assertEqual(self.apply('--repair')[0], 0)
        self.assertNotIn('retired_removed', self.receipt())

    def test_a_retired_folder_put_back_after_the_installer_removed_it_stays_with_a_warning(self):
        self.seed_old_install()
        bundle_mods = fi.parse_mod_list(self.live_launcher().decode())
        folder = self.retired[-1]['folder']
        self.assertEqual(self.apply('--repair', '--skip', 'launcher')[0], 0)
        self.assertIn(folder, self.receipt()['retired_removed'])
        put(self.server, folder + '/addons/own.pbo', b'the operator put this back')
        (self.server / 'start-server.bat').write_bytes(with_mods(self.live_launcher(), folder))
        code, out, err = self.apply('--repair')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lists(self.live_launcher())['mod'], bundle_mods + [folder])
        self.assertRegex(out, r'WARN\s+-mod %s is a retired .*folder is back' % re.escape(folder))
        self.assertTrue((self.server / folder / 'addons/own.pbo').is_file())
        self.assertNotIn(folder, self.receipt().get('retired_removed', []))
        before = snapshot(self.server)
        self.assertEqual(self.apply('--repair')[0], 0)
        self.assertEqual(snapshot(self.server), before)

    def test_a_skipped_workshop_step_keeps_a_retired_folder_and_says_why(self):
        self.seed_old_install()
        folder = self.retired[-1]['folder']
        bundle_mods = fi.parse_mod_list(self.live_launcher().decode())
        (self.server / 'start-server.bat').write_bytes(with_mods(self.live_launcher(), folder))
        code, out, err = self.apply('--repair', '--skip', 'workshop')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lists(self.live_launcher())['mod'], bundle_mods + [folder])
        self.assertRegex(out, r'WARN\s+-mod %s is a retired .*workshop step was skipped' % re.escape(folder))
        self.assertNotIn('did not install', out)
        self.assertTrue((self.server / folder).is_dir())

    def test_merge_keeps_an_unowned_retired_folder_and_removes_an_owned_one(self):
        owned, unowned = [item['folder'] for item in self.retired]
        current = ('start x "-mod=@CF;%s;%s" -dologs\r\n' % (owned, unowned)).encode()
        merged, changes = fi.merge_launcher(current, self.BUNDLE, [owned], [unowned])
        self.assertEqual(self.lists(merged)['mod'], ['@CF', '@COT', '@HollowCountry', unowned])
        lines = fi.launcher_change_lines(changes)
        self.assertIn('removed -mod %s (retired by this bundle)' % owned, lines)
        self.assertTrue([line for line in lines if line.startswith('WARN') and unowned in line])
        self.assertFalse([line for line in lines if line.startswith('kept') and unowned in line])

    # Entries are compared by their last path component

    def test_path_form_entries_of_bundle_folders_are_replaced_by_the_bundle_form(self):
        for operator in (r'C:\mods\@CF;@COT;@HollowCountry;@Mine', r'.\@CF;@COT;@HollowCountry;@Mine',
                         r'C:/mods/@CF/;@cot;.\@HollowCountry\;@Mine'):
            with self.subTest(operator):
                current = ('start x "-mod=%s" -dologs\r\n' % operator).encode()
                merged, changes = fi.merge_launcher(current, self.BUNDLE)
                self.assertEqual(self.lists(merged)['mod'], ['@CF', '@COT', '@HollowCountry', '@Mine'])
                self.assertTrue([line for line in fi.launcher_change_lines(changes) if line.startswith('replaced')])
                self.assertEqual(fi.merge_launcher(merged, self.BUNDLE), (merged, []))

    def test_a_path_form_entry_keeps_its_form_when_the_folder_is_not_there_and_not_installed(self):
        operator = r'C:\mods\@CF;@COT;@HollowCountry;@Mine'
        current = ('start x "-mod=%s" -dologs\r\n' % operator).encode()
        merged, changes = fi.merge_launcher(current, self.BUNDLE, present={'@cot', '@hollowcountry'})
        self.assertEqual(self.lists(merged)['mod'], ['C:\\mods\\@CF', '@COT', '@HollowCountry', '@Mine'])
        self.assertFalse([line for line in fi.launcher_change_lines(changes) if line.startswith('replaced')])
        self.assertEqual(fi.merge_launcher(merged, self.BUNDLE, present={'@cot', '@hollowcountry'}), (merged, []))
        merged, changes = fi.merge_launcher(current, self.BUNDLE, present={'@cf', '@cot', '@hollowcountry'})
        self.assertEqual(self.lists(merged)['mod'], ['@CF', '@COT', '@HollowCountry', '@Mine'])
        self.assertTrue([line for line in fi.launcher_change_lines(changes) if line.startswith('replaced')])

    def test_a_skipped_workshop_step_keeps_the_operators_path_form_of_a_dependency(self):
        self.assertEqual(self.apply('--skip', 'workshop')[0], 0)
        folder = fi.mod_leaf(fi.parse_mod_list(self.live_launcher().decode())[0])
        self.assertFalse((self.server / folder).exists())
        path_form = 'C:\\mods\\' + folder
        current = self.live_launcher().replace(('-mod=' + folder).encode(), ('-mod=' + path_form).encode(), 1)
        (self.server / 'start-server.bat').write_bytes(current)
        code, out, err = self.apply('--repair', '--skip', 'workshop')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lists(self.live_launcher())['mod'][0], path_form)
        self.assertNotIn('replaced', out)

    def test_a_path_form_retired_entry_is_removed_and_an_unowned_one_kept(self):
        owned, unowned = [item['folder'] for item in self.retired]
        current = ('start x "-mod=@CF;C:\\mods\\%s;.\\%s" -dologs\r\n' % (owned, unowned)).encode()
        merged, _changes = fi.merge_launcher(current, self.BUNDLE, [owned], [unowned])
        self.assertEqual(self.lists(merged)['mod'], ['@CF', '@COT', '@HollowCountry', '.\\' + unowned])

    # -mod= and -serverMod= are one managed set

    def test_a_bundle_folder_in_the_other_list_moves_to_its_own_list(self):
        current = (b'start x "-mod=@CF;@S;@Mine" "-serverMod=@New;@OperatorServerSide" -dologs\r\n')
        merged, changes = fi.merge_launcher(current, self.BUNDLE_AB)
        lists = self.lists(merged)
        self.assertEqual(lists['mod'], ['@CF', '@HollowCountry', '@New', '@Mine'])
        self.assertEqual(lists['servermod'], ['@S', '@OperatorServerSide'])
        lines = fi.launcher_change_lines(changes)
        self.assertIn('moved   -mod @S (the bundle lists it in the other argument)', lines)
        self.assertIn('moved   -serverMod @New (the bundle lists it in the other argument)', lines)
        self.assertEqual(fi.merge_launcher(merged, self.BUNDLE_AB), (merged, []))

    def test_a_retired_folder_in_the_server_mod_list_is_removed_too(self):
        owned = self.retired[0]['folder']
        current = ('start x "-mod=@CF" "-serverMod=@S;%s;@OperatorServerSide" -dologs\r\n' % owned).encode()
        merged, _changes = fi.merge_launcher(current, self.BUNDLE_AB, [owned])
        self.assertEqual(self.lists(merged)['servermod'], ['@S', '@OperatorServerSide'])

    # Comments, delayed expansion and escapes

    def test_at_rem_lines_are_comments_like_rem_and_double_colon(self):
        for word in ('@rem', '@REM', '@@Rem', 'rem', 'REM', '::', '@::'):
            with self.subTest(word):
                self.assertTrue(fi._launcher_comment('%s start x -mod=@Old\r\n' % word))
        self.assertFalse(fi._launcher_comment('@echo off'))
        self.assertFalse(fi._launcher_comment('remote x'))
        current = (b'@rem start x -mod=@Old\r\n@REM "-mod=@Older"\r\n'
                   b'start x "-mod=@CF;@Mine" -dologs\r\n')
        self.assertEqual(fi.live_mod_list(current.decode()), ['@CF', '@Mine'])
        merged, _changes = fi.merge_launcher(current, self.BUNDLE)
        self.assertTrue(merged.startswith(b'@rem start x -mod=@Old\r\n@REM "-mod=@Older"\r\n'))
        self.assertEqual(self.lists(merged.split(b'\r\n', 2)[2])['mod'], ['@CF', '@COT', '@HollowCountry', '@Mine'])

    def test_a_bang_is_literal_unless_the_launcher_enables_delayed_expansion(self):
        plain = b'start x "-mod=@A;@Mine!" -dologs\r\n'
        merged = fi.merge_launcher(plain, self.BUNDLE)
        self.assertIsNotNone(merged)
        self.assertEqual(self.lists(merged[0])['mod'], ['@CF', '@COT', '@HollowCountry', '@A', '@Mine!'])
        self.assertIsNone(fi.launcher_problem(plain, self.BUNDLE))
        self.assertIsNone(fi.live_launcher_problem(plain.decode()))
        self.assertEqual(fi.live_mod_list(plain.decode()), ['@A', '@Mine!'])
        for setlocal in (b'setlocal EnableDelayedExpansion', b'@SETLOCAL ENABLEDELAYEDEXPANSION',
                         b'setlocal enableextensions enabledelayedexpansion'):
            with self.subTest(setlocal):
                data = setlocal + b'\r\n' + plain
                self.assertIsNone(fi.merge_launcher(data, self.BUNDLE))
                self.assertIn('delayed expansion', fi.live_launcher_problem(data.decode()))
        commented = b'rem setlocal EnableDelayedExpansion\r\n' + plain
        self.assertIsNotNone(fi.merge_launcher(commented, self.BUNDLE))

    def test_delayed_expansion_and_escape_characters_in_a_value_are_refused_with_a_reason(self):
        for data, reason in ((b'setlocal EnableDelayedExpansion\r\nstart x "-mod=@A;!MODS!" -dologs\r\n',
                              'delayed expansion'),
                             (b'start x -mod=@A^;@B -dologs\r\n', 'escape character ^'),
                             (b'start x -mod=@A;%MODS% -dologs\r\n', 'batch variable')):
            with self.subTest(reason):
                self.assertIsNone(fi.merge_launcher(data, self.BUNDLE))
                self.assertIn(reason, fi.launcher_problem(data, self.BUNDLE))
                self.assertIn(reason, fi.live_launcher_problem(data.decode()))

    def test_check_with_an_unreadable_launcher_reports_the_launcher_problem_not_a_wrong_order(self):
        self.assertEqual(self.apply()[0], 0)
        (self.server / 'start-server.bat').write_bytes(b'start x -mod=%MODS% -dologs\r\n')
        code, out, err = self.run_cli('--check')
        self.assertEqual(code, 1, out + err)
        self.assertRegex(out + err, r'FAIL\s+mod_order')
        self.assertIn('launcher_problem', out + err)
        self.assertNotIn('wrong_mod_order', out + err)

    # Stash cleanup and the journal

    def test_an_unfinished_stash_copy_that_cannot_be_removed_is_a_refusal_not_a_silent_reuse(self):
        self.crash_inside_the_mission_writer()
        root = self.server / fi.BACKUP_DIR / self.latest_run()
        leftover = root / (fi.STASH_TEMP + '-earlier')
        put(root, leftover.name + '/mpmissions/old.txt', 'older partial copy')
        with mock.patch.object(fi.shutil, 'rmtree'):
            code, out, err = self.apply('--repair')
        self.assertEqual(code, 2, out + err)
        self.assertIn('stash_cleanup', err)
        self.assertIn(fi.STASH_TEMP, err)
        self.assertIn(fi.shown(leftover), err)
        self.assertEqual((self.mission / 'cfgeconomycore.xml').read_text(), '<partial/>')
        code, out, err = self.apply('--repair')
        self.assertEqual(code, 0, out + err)
        self.assertFalse(leftover.exists())

    def test_journal_rows_are_sliced_by_path_parts_when_case_folding_changes_the_length(self):
        row = {'path': 'mpmissions/stra\u00dfe', 'kind': 'tree', 'written': {}}
        ctx = mock.Mock(journal={'entries': [row]}, backup_root=self.tmp)
        rel = 'MPMISSIONS/STRASSE/Db/Globals.xml'
        self.assertEqual(rel.casefold().split('/')[1], row['path'].casefold().split('/')[1])
        with mock.patch.object(fi, 'track_target'), mock.patch.object(ws, 'write_json_atomic'):
            fi.record_written(ctx, rel, 'b' * 64)
        self.assertEqual(row['written'], {'Db/Globals.xml': ['b' * 64]})

    # globals_optout

    def test_a_globals_optout_that_is_not_a_list_of_names_is_refused_and_repaired_under_repair(self):
        edits, stock = self.reset_edits()
        path = self.tuned_server(edits)
        self.assertEqual(self.apply('--keep-stock-globals')[0], 0)
        self.assertEqual(self.receipt()['globals_optout'], ['RespawnTypes'])
        for bad in ('RespawnTypes', [1, 2], [''], {'RespawnTypes': True}):
            with self.subTest(bad=bad):
                data = self.receipt()
                data['globals_optout'] = bad
                (self.server / fi.RECEIPT).write_text(json.dumps(data))
                code, out, err = self.apply()
                self.assertEqual(code, 2, out + err)
                self.assertIn('receipt_optout_invalid', err)
                code, out, err = self.apply('--repair')
                self.assertEqual(code, 0, out + err)
                self.assertEqual(self.receipt()['globals_optout'], ['RespawnTypes'])
                self.assertEqual(var_values(path)['RespawnTypes'], stock)

    def test_an_orphaned_workshop_receipt_key_row_is_repaired_once_and_persisted_with_the_journal(self):
        self.assertEqual(self.apply()[0], 0)
        path = self.server / ws.RECEIPT_NAME
        key = sorted((self.bundle / 'keys').glob('*.bikey'))[0]
        data = json.loads(path.read_text())
        row = 'keys/' + key.name
        data['files'] = [e for e in data['files'] if e['path'] != row] + [
            {'path': row, 'sha256': hashlib.sha256(key.read_bytes()).hexdigest(), 'size': 1, 'item': 'old'}]
        self.assertFalse([e for e in data['files'] if e['path'].endswith('/keys/' + key.name)
                          and e['path'].startswith('@') and e['sha256'] == data['files'][-1]['sha256']])
        path.write_bytes(ws.json_bytes(data))
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertIn('WARN: receipt key ' + row, out)
        self.assertNotIn(row, [e['path'] for e in json.loads(path.read_text())['files']])
        journal = json.loads((self.server / fi.BACKUP_DIR / self.latest_run() / fi.JOURNAL).read_text())
        self.assertIn(ws.RECEIPT_NAME, [entry['path'] for entry in journal['entries']])
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        self.assertNotIn('WARN: receipt key', out)

    def test_the_retire_cache_does_not_outlive_a_run(self):
        ctx = mock.Mock(retire_cache=(['@Old'], []), retire_reasons={'@old': 'unowned'})
        with mock.patch.object(fi, 'analyze', side_effect=RuntimeError('stop')):
            with self.assertRaises(RuntimeError):
                fi.run_steps(ctx, True)
        self.assertIsNone(ctx.retire_cache)
        self.assertEqual(ctx.retire_reasons, {})

    def test_the_rest_of_a_receipt_is_validated_when_globals_optout_is_repaired(self):
        self.assertEqual(self.apply()[0], 0)
        receipt_path = self.server / fi.RECEIPT
        for bad in ('0' * 64, ['not a hash'], {'default': 'a' * 64}):
            with self.subTest(bad=bad):
                data = self.receipt()
                data['globals_optout'] = 'RespawnTypes'
                data['profile_defaults'] = bad
                receipt_path.write_text(json.dumps(data))
                before = receipt_path.read_bytes()
                for extra in ((), ('--repair',)):
                    code, out, err = self.apply(*extra)
                    self.assertEqual(code, 2, out + err)
                    self.assertIn('receipt_invalid', err)
                    self.assertNotIn('receipt_optout_invalid', err)
                    self.assertEqual(receipt_path.read_bytes(), before)

    def test_a_rebuilt_receipt_keeps_the_globals_optout_from_the_old_text_or_the_overlay_state(self):
        edits, stock = self.reset_edits()
        path = self.tuned_server(edits)
        self.assertEqual(self.apply('--keep-stock-globals')[0], 0)
        receipt_path = self.server / fi.RECEIPT
        good = receipt_path.read_text()
        # Damaged JSON that still holds the array.
        receipt_path.write_text(good.rstrip()[:-1] + ' garbage')
        code, out, err = self.apply('--repair')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.receipt()['globals_optout'], ['RespawnTypes'])
        self.assertEqual(var_values(path)['RespawnTypes'], stock)
        # Bytes that are not text at all: the opt-out is read back from the loot-boost state on disk.
        receipt_path.write_bytes(b'\xff\xfe not text')
        code, out, err = self.apply('--repair')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.receipt()['globals_optout'], ['RespawnTypes'])
        self.assertEqual(var_values(path)['RespawnTypes'], stock)
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual(var_values(path)['RespawnTypes'], stock)
