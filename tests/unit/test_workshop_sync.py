"""Workshop sync tool: synthetic Workshop content and server roots only.

steamcmd is never run: subprocess.run is patched (to fail the test, or to a recorded fake in the fetch
tests). Nothing here establishes DayZ behaviour, the real Workshop layout beyond addons/ and keys/, or
a real server install.
"""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from tools.setup import workshop_sync as ws

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / 'tools/setup/workshop_mods.json'
IDS = {'cf': '1559212036', 'dabs': '2545327648', 'core': '2291785308', 'anim': '2793893086',
       'ai': '2792982069', 'snafu': '2443122116', 'tf': '2646817942'}
HC_ID = '3600000001'
FULL_MOD = ('-mod=@CF;@DabsFramework;@Expansion-Core;@Expansion-Animations;@Expansion-AI;'
            '@SnafuWeapons;@TacticalFlava;@HollowCountry')
RECEIPT = 'hollow-country-workshop-receipt.json'
MARKER = 'S3CRET-MARKER-9f2'


def make_item(content, item_id, key=None, extra=True, name=None):
    base = Path(content) / item_id
    key = key or 'key_' + item_id
    (base / 'addons').mkdir(parents=True)
    (base / 'keys').mkdir()
    (base / 'addons' / ('%s.pbo' % (name or 'm' + item_id))).write_bytes(b'pbo-' + item_id.encode())
    (base / 'addons' / ('%s.pbo.%s.bisign' % (name or 'm' + item_id, key))).write_bytes(b'sig-' + item_id.encode())
    (base / 'keys' / (key + '.bikey')).write_bytes(b'public-' + item_id.encode())
    (base / 'mod.cpp').write_text('name = "%s";\n' % item_id)
    (base / 'meta.cpp').write_text('protocol = 1;\npublishedid = %s;\n' % item_id)
    if extra:
        (base / 'Licenses').mkdir()
        (base / 'Licenses' / 'LICENSE.txt').write_text('third party licence')
        (base / 'ReadMe.txt').write_text('read me')
    return base


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree(root):
    root = Path(root)
    return sorted(p.relative_to(root).as_posix() for p in root.rglob('*'))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.content = self.tmp / 'content'
        self.content.mkdir()
        self.root = self.tmp / 'server'
        (self.root / 'keys').mkdir(parents=True)
        self.running = mock.patch.object(ws, 'server_running', return_value=False)
        self.running_mock = self.running.start()
        self.addCleanup(self.running.stop)
        self.run_patch = mock.patch('subprocess.run', side_effect=AssertionError('process started'))
        self.run_mock = self.run_patch.start()
        self.addCleanup(self.run_patch.stop)

    def main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err):
            code = ws.main(list(argv), out=out)
        return code, out.getvalue(), err.getvalue()

    def common(self, groups, *extra):
        return ['--server-root', str(self.root), '--groups', groups, '--workshop-content', str(self.content), *extra]

    def run_cmd(self, command, groups, *extra):
        return self.main(command, *self.common(groups, *extra))

    def rollback(self, *extra):
        return self.main('rollback', '--server-root', str(self.root), *extra)


class Manifest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(MANIFEST.read_text())
        self.mods = {m['folder']: m for m in self.data['mods']}

    def test_third_party_items_are_referenced_by_id_only(self):
        by_id = {m['id']: m for m in self.data['mods'] if m['id']}
        self.assertEqual(sorted(by_id), sorted(IDS.values()))
        for item_id in IDS.values():
            self.assertTrue(by_id[item_id]['name'] and by_id[item_id]['folder'].startswith('@'))

    def test_groups_and_sides(self):
        self.assertEqual({m['group'] for m in self.data['mods']}, {'base', 'snafu', 'tactical_flava', 'pve_patrols'})
        self.assertEqual({m['folder'] for m in self.data['mods'] if m['side'] == 'server'},
                         {'@HollowCountryExpansionAI'})
        self.assertEqual(self.mods['@HollowCountry']['group'], 'base')
        self.assertEqual({m['folder'] for m in self.data['mods'] if m['group'] == 'pve_patrols'},
                         {'@CF', '@DabsFramework', '@Expansion-Core', '@Expansion-Animations', '@Expansion-AI',
                          '@HollowCountryExpansionAI'})

    def test_load_order_is_the_documented_one(self):
        order = [m['folder'] for m in sorted(self.data['mods'], key=lambda m: m['rank'])]
        self.assertEqual(order, ['@CF', '@DabsFramework', '@Expansion-Core', '@Expansion-Animations',
                                 '@Expansion-AI', '@SnafuWeapons', '@TacticalFlava', '@HollowCountry',
                                 '@HollowCountryExpansionAI'])
        self.assertEqual(len({m['rank'] for m in self.data['mods']}), len(self.data['mods']))

    def test_own_mods_have_no_workshop_id_until_published_and_the_ai_mod_is_never_published(self):
        self.assertIsNone(self.mods['@HollowCountry']['id'])
        self.assertTrue(self.mods['@HollowCountry']['publish'])
        self.assertIsNone(self.mods['@HollowCountryExpansionAI']['id'])
        self.assertFalse(self.mods['@HollowCountryExpansionAI']['publish'])

    def test_manifest_stays_outside_the_base_mission_folders(self):
        self.assertEqual(MANIFEST.parent, REPO / 'tools/setup')
        for folder in ('config', 'mission', 'mods'):
            for path in (REPO / folder).rglob('*'):
                if path.is_file() and path.suffix.lower() in {'.json', '.md', '.xml', '.cpp', '.c'}:
                    data = path.read_bytes().lower()
                    self.assertNotIn(IDS['tf'].encode(), data, path)
                    self.assertNotIn(b'snafu', data, path)

    def test_loader_rejects_a_malformed_manifest(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        cases = {
            'dup-rank': lambda d: d['mods'][1].update(rank=d['mods'][0]['rank']),
            'dup-folder': lambda d: d['mods'][1].update(folder=d['mods'][0]['folder']),
            'bad-id': lambda d: d['mods'][0].update(id='12ab'),
            'bad-group': lambda d: d['mods'][0].update(group='nope'),
            'bad-side': lambda d: d['mods'][0].update(side='both'),
            'bad-folder': lambda d: d['mods'][0].update(folder='../evil'),
            'no-at': lambda d: d['mods'][0].update(folder='CF'),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                data = json.loads(MANIFEST.read_text())
                mutate(data)
                path = tmp / (name + '.json')
                path.write_text(json.dumps(data))
                with self.assertRaises(ws.SyncError):
                    ws.load_manifest(path)
        self.assertTrue(ws.load_manifest(MANIFEST))


class Plan(Base):
    def test_base_only_prints_the_mod_line_and_marks_the_unpublished_mod(self):
        code, text, _ = self.run_cmd('plan', 'base')
        self.assertEqual(code, 0, text)
        self.assertIn('-mod=@HollowCountry', text)
        self.assertNotIn('-serverMod', text)
        self.assertIn('unpublished', text)

    def test_full_set_prints_the_documented_load_order(self):
        code, text, _ = self.run_cmd('plan', 'base,snafu,tactical_flava,pve_patrols')
        self.assertEqual(code, 0, text)
        self.assertIn(FULL_MOD, text.splitlines())
        self.assertIn('-serverMod=@HollowCountryExpansionAI', text.splitlines())

    def test_group_order_on_the_command_line_does_not_change_load_order(self):
        _, a, _ = self.run_cmd('plan', 'pve_patrols,base')
        _, b, _ = self.run_cmd('plan', 'base,pve_patrols')
        self.assertEqual([l for l in a.splitlines() if l.startswith('-')],
                         [l for l in b.splitlines() if l.startswith('-')])

    def test_present_and_missing_items_are_reported_with_copy_actions(self):
        make_item(self.content, IDS['cf'])
        code, text, _ = self.run_cmd('plan', 'pve_patrols')
        self.assertEqual(code, 0, text)
        self.assertIn('%s present' % IDS['cf'], text)
        self.assertIn(str(self.content / IDS['cf']), text)
        self.assertIn('copy %s -> %s' % (self.content / IDS['cf'], self.root / '@CF'), text)
        self.assertIn('%s missing' % IDS['dabs'], text)
        self.assertEqual(tree(self.root), ['keys'])  # plan writes nothing

    def test_steamcmd_content_dir_is_derived_from_the_steamcmd_path(self):
        steam = self.tmp / 'steamcmd'
        deep = steam / 'steamapps/workshop/content/221100'
        make_item(deep, IDS['cf'])
        code, text, _ = self.main('plan', '--server-root', str(self.root), '--groups', 'pve_patrols',
                                  '--steamcmd', str(steam / 'steamcmd.sh'))
        self.assertEqual(code, 0, text)
        self.assertIn('%s present' % IDS['cf'], text)

    def test_item_without_addons_or_keys_is_reported_incomplete_not_present(self):
        broken = self.content / IDS['cf']
        (broken / 'addons').mkdir(parents=True)
        code, text, _ = self.run_cmd('plan', 'pve_patrols')
        self.assertIn('%s incomplete' % IDS['cf'], text)

    def test_unknown_group_and_empty_groups_refused(self):
        self.assertEqual(self.run_cmd('plan', 'base,nonsense')[0], 1)
        self.assertEqual(self.run_cmd('plan', '')[0], 1)

    def test_pve_patrols_without_base_warns(self):
        _, text, _ = self.run_cmd('plan', 'pve_patrols')
        self.assertIn('base', text.lower())
        self.assertIn('warning', text.lower())

    def test_hollowcountry_id_option_makes_the_own_mod_downloadable(self):
        make_item(self.content, HC_ID)
        _, text, _ = self.run_cmd('plan', 'base', '--hollowcountry-id', HC_ID)
        self.assertIn('%s present' % HC_ID, text)
        self.assertNotIn('unpublished', text)

    def test_bad_hollowcountry_id_refused(self):
        with self.assertRaises(SystemExit):
            self.run_cmd('plan', 'base', '--hollowcountry-id', 'abc')

    def test_server_only_mod_is_reported_as_a_local_build(self):
        _, text, _ = self.run_cmd('plan', 'pve_patrols')
        self.assertIn('@HollowCountryExpansionAI', text)
        self.assertIn('never published', text)


class Fetch(Base):
    def fake_steamcmd(self, content, ids):
        def run(cmd, **kwargs):
            for item_id in ids:
                make_item(content, item_id, extra=False)
            return subprocess.CompletedProcess(cmd, 0)
        return run

    def test_runs_steamcmd_with_the_exact_arguments_and_verifies_items(self):
        steam = self.tmp / 'steamcmd'
        deep = steam / 'steamapps/workshop/content/221100'
        calls = []
        base_fake = self.fake_steamcmd(deep, [IDS['cf'], IDS['dabs'], IDS['core'], IDS['anim'], IDS['ai']])
        self.run_mock.side_effect = lambda cmd, **kw: (calls.append((cmd, kw)), base_fake(cmd, **kw))[1]
        code, text, _ = self.main('fetch', '--server-root', str(self.root), '--groups', 'pve_patrols',
                                  '--steamcmd', str(steam / 'steamcmd.sh'), '--steam-user', 'owner_login')
        self.assertEqual(code, 0, text)
        self.assertEqual(len(calls), 1)
        cmd, kwargs = calls[0]
        self.assertEqual(cmd, [str(steam / 'steamcmd.sh'), '+login', 'owner_login',
                               '+workshop_download_item', '221100', IDS['cf'], 'validate',
                               '+workshop_download_item', '221100', IDS['dabs'], 'validate',
                               '+workshop_download_item', '221100', IDS['core'], 'validate',
                               '+workshop_download_item', '221100', IDS['anim'], 'validate',
                               '+workshop_download_item', '221100', IDS['ai'], 'validate',
                               '+quit'])
        # Interactive: the operator types the password into steamcmd; we never touch stdin, stdout or env.
        for forbidden in ('input', 'stdin', 'stdout', 'stderr', 'capture_output', 'env', 'shell'):
            self.assertNotIn(forbidden, kwargs)
        self.assertNotIn('password', ' '.join(cmd).lower())
        self.assertIn('verified', text)

    def test_install_dir_goes_before_login_and_sets_the_verified_location(self):
        install = self.tmp / 'dl'
        deep = install / 'steamapps/workshop/content/221100'
        self.run_mock.side_effect = self.fake_steamcmd(deep, [IDS['snafu']])
        code, _, _ = self.main('fetch', '--server-root', str(self.root), '--groups', 'snafu',
                               '--install-dir', str(install), '--steam-user', 'owner')
        self.assertEqual(code, 0)
        cmd = self.run_mock.call_args[0][0]
        self.assertEqual(cmd[:5], ['steamcmd', '+force_install_dir', str(install), '+login', 'owner'])

    def test_missing_downloads_fail_verification(self):
        self.run_mock.side_effect = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0)
        code, _, err = self.main('fetch', *self.common('snafu'), '--steam-user', 'owner')
        self.assertEqual(code, 1)
        self.assertIn(IDS['snafu'], err)

    def test_item_without_keys_dir_fails_verification(self):
        def run(cmd, **kw):
            (self.content / IDS['snafu'] / 'addons').mkdir(parents=True)
            return subprocess.CompletedProcess(cmd, 0)
        self.run_mock.side_effect = run
        code, _, err = self.main('fetch', *self.common('snafu'), '--steam-user', 'owner')
        self.assertEqual(code, 1)
        self.assertIn('keys', err)

    def test_nonzero_steamcmd_exit_fails(self):
        self.run_mock.side_effect = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 5)
        code, _, err = self.main('fetch', *self.common('snafu'), '--steam-user', 'owner')
        self.assertEqual(code, 1)
        self.assertIn('5', err)

    def test_missing_steamcmd_binary_is_a_clean_error(self):
        self.run_mock.side_effect = FileNotFoundError('steamcmd')
        code, _, err = self.main('fetch', *self.common('snafu'), '--steam-user', 'owner')
        self.assertEqual(code, 1)
        self.assertIn('steamcmd', err)

    def test_username_is_required_and_validated(self):
        with self.assertRaises(SystemExit):
            self.main('fetch', *self.common('snafu'))
        for bad in ('', '+quit', '-x', 'a b', 'x;y', 'me@example.com', 'a' * 70):
            with self.subTest(bad=bad):
                code, _, _ = self.main('fetch', *self.common('snafu'), '--steam-user=' + bad)
                self.assertEqual(code, 1)
                self.run_mock.assert_not_called()

    def test_secret_values_are_never_echoed_on_rejection(self):
        for argv in (['--password', MARKER], ['--password=' + MARKER], ['--steam-pass', MARKER], ['-p', MARKER],
                     ['--token', MARKER], ['--secret=' + MARKER], ['--bogus', MARKER], ['--guard-code=' + MARKER]):
            with self.subTest(argv=argv):
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    with self.assertRaises(SystemExit) as caught:
                        ws.main(['fetch', *self.common('snafu'), '--steam-user', 'owner', *argv], out=out)
                self.assertEqual(caught.exception.code, 2)
                self.assertNotIn(MARKER, out.getvalue() + err.getvalue())
                self.assertTrue(err.getvalue())
                self.run_mock.assert_not_called()

    def test_no_password_option_exists(self):
        for flag in ('--password', '--steam-password', '--steam-pass'):
            with self.subTest(flag=flag):
                with self.assertRaises(SystemExit):
                    with contextlib.redirect_stderr(io.StringIO()):
                        ws.main(['fetch', *self.common('snafu'), '--steam-user', 'owner', flag, 'x'],
                                out=io.StringIO())

    def test_nothing_to_fetch_does_not_start_steamcmd(self):
        code, text, _ = self.main('fetch', *self.common('base'), '--steam-user', 'owner')
        self.assertEqual(code, 0)
        self.assertIn('nothing to fetch', text)
        self.run_mock.assert_not_called()

    def test_no_known_download_location_is_refused_before_running(self):
        code, _, err = self.main('fetch', '--server-root', str(self.root), '--groups', 'snafu',
                                 '--steam-user', 'owner')
        self.assertEqual(code, 1)
        self.assertIn('--install-dir', err)
        self.run_mock.assert_not_called()

    def test_fetch_does_not_touch_the_server_root(self):
        self.run_mock.side_effect = self.fake_steamcmd(self.content, [IDS['snafu']])
        self.main('fetch', *self.common('snafu'), '--steam-user', 'owner')
        self.assertEqual(tree(self.root), ['keys'])


class Install(Base):
    def populate(self, *keys, **kw):
        for key in keys:
            make_item(self.content, IDS[key], **kw)

    def test_copies_mod_folders_and_public_keys_not_symlinks(self):
        self.populate('snafu')
        code, text, _ = self.run_cmd('install', 'snafu')
        self.assertEqual(code, 0, text)
        folder = self.root / '@SnafuWeapons'
        self.assertEqual(sha(folder / 'addons' / ('m%s.pbo' % IDS['snafu'])),
                         sha(self.content / IDS['snafu'] / 'addons' / ('m%s.pbo' % IDS['snafu'])))
        self.assertTrue((folder / 'mod.cpp').is_file())
        self.assertTrue((self.root / 'keys' / ('key_%s.bikey' % IDS['snafu'])).is_file())
        self.assertTrue((folder / 'keys' / ('key_%s.bikey' % IDS['snafu'])).is_file())
        for path in self.root.rglob('*'):
            self.assertFalse(path.is_symlink(), path)
            if path.is_file():
                self.assertEqual(os.lstat(path).st_nlink, 1, path)

    def test_never_copies_anything_else(self):
        self.populate('snafu')
        code, text, _ = self.run_cmd('install', 'snafu')
        self.assertEqual(code, 0)
        self.assertNotIn('Licenses', tree(self.root))
        self.assertEqual(sorted(p for p in tree(self.root) if p.startswith('@SnafuWeapons')), [
            '@SnafuWeapons', '@SnafuWeapons/addons',
            '@SnafuWeapons/addons/m%s.pbo' % IDS['snafu'],
            '@SnafuWeapons/addons/m%s.pbo.key_%s.bisign' % (IDS['snafu'], IDS['snafu']),
            '@SnafuWeapons/keys', '@SnafuWeapons/keys/key_%s.bikey' % IDS['snafu'],
            '@SnafuWeapons/meta.cpp', '@SnafuWeapons/mod.cpp'])
        self.assertEqual(sorted(p for p in tree(self.root) if p.startswith('keys/')),
                         ['keys/key_%s.bikey' % IDS['snafu']])
        self.assertIn('skipped', text)
        self.assertIn('Licenses', text)

    def test_prints_the_launch_lines_for_the_installed_set(self):
        for key in IDS:
            self.populate(key)
        make_item(self.content, HC_ID)
        code, text, _ = self.run_cmd('install', 'base,snafu,tactical_flava,pve_patrols',
                                     '--hollowcountry-id', HC_ID)
        self.assertEqual(code, 0, text)
        self.assertIn(FULL_MOD, text.splitlines())
        self.assertIn('-serverMod=@HollowCountryExpansionAI', text.splitlines())
        self.assertTrue((self.root / '@HollowCountry' / 'addons').is_dir())
        # The locally built server-only mod is never created or copied by this tool.
        self.assertFalse((self.root / '@HollowCountryExpansionAI').exists())
        self.assertIn('@HollowCountryExpansionAI', text)

    def test_refuses_all_or_nothing_when_an_item_is_missing(self):
        self.populate('cf')
        code, _, err = self.run_cmd('install', 'pve_patrols')
        self.assertEqual(code, 1)
        self.assertIn(IDS['dabs'], err)
        self.assertEqual(tree(self.root), ['keys'])

    def test_refuses_private_keys_and_unexpected_files_in_a_workshop_item(self):
        for rel in ('keys/evil.biprivatekey', 'keys/notes.txt', 'addons/notes.txt', 'addons/sub/x.pbo'):
            with self.subTest(rel=rel):
                shutil.rmtree(self.content, True)
                self.content.mkdir()
                base = make_item(self.content, IDS['snafu'])
                (base / rel).parent.mkdir(parents=True, exist_ok=True)
                (base / rel).write_bytes(b'x')
                code, _, err = self.run_cmd('install', 'snafu')
                self.assertEqual(code, 1)
                self.assertTrue(err)
                self.assertEqual(tree(self.root), ['keys'])

    def test_refuses_symlinks_inside_a_workshop_item(self):
        base = make_item(self.content, IDS['snafu'])
        outside = self.tmp / 'outside.pbo'
        outside.write_bytes(b'x')
        os.symlink(outside, base / 'addons' / 'linked.pbo')
        code, _, err = self.run_cmd('install', 'snafu')
        self.assertEqual(code, 1)
        self.assertIn('symlink', err)
        self.assertEqual(tree(self.root), ['keys'])

    def test_refuses_to_overwrite_a_different_file_and_writes_nothing(self):
        self.populate('snafu', 'tf')
        (self.root / 'keys' / ('key_%s.bikey' % IDS['tf'])).write_bytes(b'someone else key')
        code, _, err = self.run_cmd('install', 'snafu,tactical_flava')
        self.assertEqual(code, 1)
        self.assertIn('key_%s.bikey' % IDS['tf'], err)
        self.assertEqual(tree(self.root), ['keys', 'keys/key_%s.bikey' % IDS['tf']])
        self.assertEqual((self.root / 'keys' / ('key_%s.bikey' % IDS['tf'])).read_bytes(), b'someone else key')

    def test_refuses_to_overwrite_a_different_mod_file(self):
        self.populate('snafu')
        folder = self.root / '@SnafuWeapons'
        folder.mkdir()
        (folder / 'mod.cpp').write_text('different')
        code, _, err = self.run_cmd('install', 'snafu')
        self.assertEqual(code, 1)
        self.assertIn('mod.cpp', err)
        self.assertEqual((folder / 'mod.cpp').read_text(), 'different')

    def test_refuses_symlinked_destinations(self):
        self.populate('snafu')
        elsewhere = self.tmp / 'elsewhere'
        elsewhere.mkdir()
        os.symlink(elsewhere, self.root / '@SnafuWeapons')
        code, _, err = self.run_cmd('install', 'snafu')
        self.assertEqual(code, 1)
        self.assertIn('symlink', err)
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_refuses_a_server_root_that_is_not_a_directory(self):
        self.populate('snafu')
        code, _, _ = self.main('install', '--server-root', str(self.tmp / 'nope'), '--groups', 'snafu',
                               '--workshop-content', str(self.content))
        self.assertEqual(code, 1)

    def test_second_install_is_a_no_op(self):
        self.populate('snafu')
        self.run_cmd('install', 'snafu')
        before = {p: (p.read_bytes() if p.is_file() else None) for p in self.root.rglob('*')}
        receipt = (self.root / RECEIPT).read_bytes()
        code, text, _ = self.run_cmd('install', 'snafu')
        self.assertEqual(code, 0)
        self.assertIn('already installed', text)
        self.assertEqual({p: (p.read_bytes() if p.is_file() else None) for p in self.root.rglob('*')}, before)
        self.assertEqual((self.root / RECEIPT).read_bytes(), receipt)

    def test_receipt_lists_exactly_what_was_added(self):
        self.populate('snafu')
        (self.root / 'keys' / 'preexisting.bikey').write_bytes(b'mine')
        self.run_cmd('install', 'snafu')
        receipt = json.loads((self.root / RECEIPT).read_text())
        paths = sorted(f['path'] for f in receipt['files'])
        self.assertEqual(paths, sorted(p for p in tree(self.root)
                                       if (self.root / p).is_file() and p not in (RECEIPT, 'keys/preexisting.bikey')))
        for entry in receipt['files']:
            self.assertEqual(entry['sha256'], sha(self.root / entry['path']))
        self.assertEqual(receipt['schema'], 1)
        self.assertNotIn('password', json.dumps(receipt).lower())

    def test_rollback_removes_exactly_what_was_added(self):
        self.populate('snafu')
        (self.root / 'keys' / 'preexisting.bikey').write_bytes(b'mine')
        # A key that already matched before install is not ours to remove.
        shared = self.root / 'keys' / ('key_%s.bikey' % IDS['snafu'])
        shared.write_bytes(b'public-' + IDS['snafu'].encode())
        self.run_cmd('install', 'snafu')
        code, text, _ = self.rollback()
        self.assertEqual(code, 0, text)
        self.assertEqual(tree(self.root), ['keys', 'keys/key_%s.bikey' % IDS['snafu'], 'keys/preexisting.bikey'])
        self.assertEqual(shared.read_bytes(), b'public-' + IDS['snafu'].encode())

    def test_rollback_leaves_foreign_and_modified_files(self):
        self.populate('snafu')
        self.run_cmd('install', 'snafu')
        folder = self.root / '@SnafuWeapons'
        (folder / 'my-notes.txt').write_text('keep me')
        pbo = folder / 'addons' / ('m%s.pbo' % IDS['snafu'])
        pbo.write_bytes(b'locally edited')
        code, text, _ = self.rollback()
        self.assertEqual(code, 0)
        self.assertEqual((folder / 'my-notes.txt').read_text(), 'keep me')
        self.assertEqual(pbo.read_bytes(), b'locally edited')
        self.assertIn('left in place', text)
        self.assertFalse((folder / 'mod.cpp').exists())

    def test_rollback_refuses_a_tampered_receipt(self):
        self.populate('snafu')
        self.run_cmd('install', 'snafu')
        victim = self.tmp / 'victim.txt'
        victim.write_text('precious')
        path = self.root / RECEIPT
        data = json.loads(path.read_text())
        for bad in ('../victim.txt', '/etc/passwd', 'serverDZ.cfg', '@X/../../victim.txt', 'keys/../../victim.txt'):
            with self.subTest(bad=bad):
                data['files'].append({'path': bad, 'sha256': sha(victim), 'size': 8, 'item': 'x'})
                path.write_text(json.dumps(data))
                code, _, err = self.rollback()
                self.assertEqual(code, 1)
                self.assertEqual(victim.read_text(), 'precious')
                self.assertTrue((self.root / '@SnafuWeapons' / 'mod.cpp').exists())
                data['files'].pop()

    def test_rollback_without_a_receipt_refuses(self):
        code, _, err = self.rollback()
        self.assertEqual(code, 1)
        self.assertIn('receipt', err)

    def test_install_after_rollback_reinstalls(self):
        self.populate('snafu')
        self.run_cmd('install', 'snafu')
        self.rollback()
        self.assertFalse((self.root / RECEIPT).exists())
        self.assertEqual(self.run_cmd('install', 'snafu')[0], 0)
        self.assertTrue((self.root / '@SnafuWeapons' / 'mod.cpp').exists())

    def test_install_extends_a_previous_receipt_without_dropping_it(self):
        self.populate('snafu', 'tf')
        self.run_cmd('install', 'snafu')
        self.run_cmd('install', 'snafu,tactical_flava')
        self.assertEqual(self.rollback()[0], 0)
        self.assertEqual(tree(self.root), ['keys'])

    def test_server_running_refuses_install_and_rollback(self):
        self.populate('snafu')
        self.running_mock.return_value = True
        code, _, err = self.run_cmd('install', 'snafu')
        self.assertEqual(code, 1)
        self.assertIn('running', err)
        self.assertEqual(tree(self.root), ['keys'])
        self.running_mock.return_value = False
        self.run_cmd('install', 'snafu')
        self.running_mock.return_value = True
        code, _, err = self.rollback()
        self.assertEqual(code, 1)
        self.assertTrue((self.root / '@SnafuWeapons' / 'mod.cpp').exists())

    def test_unknown_detection_refuses_unless_assume_stopped(self):
        self.populate('snafu')
        self.running_mock.return_value = None
        code, _, err = self.run_cmd('install', 'snafu')
        self.assertEqual(code, 1)
        self.assertIn('--assume-stopped', err)
        code, _, _ = self.run_cmd('install', 'snafu', '--assume-stopped')
        self.assertEqual(code, 0)

    def test_assume_stopped_skips_detection_entirely(self):
        self.populate('snafu')
        self.running_mock.side_effect = AssertionError('detection must not run')
        self.assertEqual(self.run_cmd('install', 'snafu', '--assume-stopped')[0], 0)

    def test_plan_and_fetch_do_not_require_a_stopped_server(self):
        self.running_mock.return_value = True
        self.assertEqual(self.run_cmd('plan', 'base')[0], 0)


class ReceiptScope(Base):
    """Review P1: a receipt may only name what install itself created."""

    def setUp(self):
        super().setUp()
        make_item(self.content, IDS['snafu'])
        self.existing = self.root / '@ExistingMod' / 'addons' / 'existing.pbo'
        self.existing.parent.mkdir(parents=True)
        self.existing.write_bytes(b'someone elses mod')
        self.run_cmd('install', 'snafu')
        self.receipt = self.root / RECEIPT
        self.data = json.loads(self.receipt.read_text())

    def tamper(self, path):
        self.data['files'].append({'path': path, 'sha256': sha(self.root / path), 'size': 1, 'item': 'x'})
        self.receipt.write_text(json.dumps(self.data))

    def test_rollback_refuses_an_entry_in_a_folder_install_did_not_create(self):
        self.tamper('@ExistingMod/addons/existing.pbo')
        code, _, err = self.rollback()
        self.assertEqual(code, 1)
        self.assertIn('@ExistingMod', err)
        self.assertEqual(self.existing.read_bytes(), b'someone elses mod')
        self.assertTrue((self.root / '@SnafuWeapons' / 'mod.cpp').exists())

    def test_rollback_refuses_a_key_entry_with_no_matching_created_copy(self):
        victim = self.root / 'keys' / 'preexisting.bikey'
        victim.write_bytes(b'someone elses key')
        self.tamper('keys/preexisting.bikey')
        code, _, err = self.rollback()
        self.assertEqual(code, 1)
        self.assertEqual(victim.read_bytes(), b'someone elses key')
        self.assertTrue((self.root / '@SnafuWeapons' / 'mod.cpp').exists())

    def test_rollback_refuses_a_folder_entry_naming_a_folder_not_created(self):
        self.data['dirs'].append('@ExistingMod')
        self.data['dirs'].append('@ExistingMod/addons')
        self.tamper('@ExistingMod/addons/existing.pbo')
        # Folders must also be mod folders from the manifest, so a forged list cannot name a stranger's mod.
        code, _, _ = self.rollback()
        self.assertEqual(code, 1)
        self.assertEqual(self.existing.read_bytes(), b'someone elses mod')

    def test_install_refuses_a_pre_existing_mod_folder_it_did_not_create(self):
        self.rollback()
        folder = self.root / '@SnafuWeapons'
        (folder / 'addons').mkdir(parents=True)
        (folder / 'addons' / 'user.pbo').write_bytes(b'user')
        code, _, err = self.run_cmd('install', 'snafu')
        self.assertEqual(code, 1)
        self.assertIn('not created', err)
        self.assertFalse((self.root / RECEIPT).exists())

    def test_normal_install_then_rollback_still_works(self):
        self.assertEqual(self.rollback()[0], 0)
        self.assertEqual(tree(self.root), ['@ExistingMod', '@ExistingMod/addons', '@ExistingMod/addons/existing.pbo',
                                           'keys'])


class ServerDetection(unittest.TestCase):
    def test_posix_uses_pgrep(self):
        with mock.patch('subprocess.run') as run, mock.patch('os.name', 'posix'), \
                mock.patch('shutil.which', return_value=None):
            run.return_value = subprocess.CompletedProcess([], 0)
            self.assertTrue(ws.server_running())
            self.assertEqual(run.call_args[0][0][0], 'pgrep')
            run.return_value = subprocess.CompletedProcess([], 1)
            self.assertFalse(ws.server_running())

    def test_missing_tool_means_unknown(self):
        with mock.patch('subprocess.run', side_effect=FileNotFoundError('pgrep')), mock.patch('os.name', 'posix'), \
                mock.patch('shutil.which', return_value=None):
            self.assertIsNone(ws.server_running())

    def test_any_failed_probe_means_unknown_not_stopped(self):
        # Review P1: pgrep says "not running" but the Windows probe errors; that must not read as stopped.
        def run(command, **kwargs):
            if command[0] == 'pgrep':
                return subprocess.CompletedProcess(command, 1)
            return subprocess.CompletedProcess(command, 1, stdout='')
        with mock.patch('subprocess.run', side_effect=run), mock.patch('os.name', 'posix'), \
                mock.patch('shutil.which', return_value='/mnt/c/Windows/System32/tasklist.exe'):
            self.assertIsNone(ws.server_running())
        with mock.patch('subprocess.run', side_effect=lambda c, **k: (_ for _ in ()).throw(OSError('x'))
                        if c[0] != 'pgrep' else subprocess.CompletedProcess(c, 1)), \
                mock.patch('os.name', 'posix'), mock.patch('shutil.which', return_value='tasklist.exe'):
            self.assertIsNone(ws.server_running())

    def test_all_probes_clean_is_stopped_and_one_hit_is_running(self):
        def run(hit):
            def inner(command, **kwargs):
                if command[0] == 'pgrep':
                    return subprocess.CompletedProcess(command, 1)
                return subprocess.CompletedProcess(command, 0, stdout='DayZServer_x64.exe 1\n' if hit else
                                                   'INFO: No tasks are running which match.\n')
            return inner
        with mock.patch('os.name', 'posix'), mock.patch('shutil.which', return_value='tasklist.exe'):
            with mock.patch('subprocess.run', side_effect=run(False)):
                self.assertFalse(ws.server_running())
            with mock.patch('subprocess.run', side_effect=run(True)):
                self.assertTrue(ws.server_running())

    def test_windows_uses_tasklist(self):
        out = 'Image Name   PID\nDayZServer_x64.exe   1234\n'
        with mock.patch('subprocess.run') as run, mock.patch('os.name', 'nt'):
            run.return_value = subprocess.CompletedProcess([], 0, stdout=out)
            self.assertTrue(ws.server_running())
            self.assertEqual(run.call_args[0][0][0], 'tasklist')
            run.return_value = subprocess.CompletedProcess(
                [], 0, stdout='INFO: No tasks are running which match the specified criteria.\n')
            self.assertFalse(ws.server_running())


class Documentation(unittest.TestCase):
    def test_docs_cover_the_workshop_flow(self):
        text = (REPO / 'docs/FRIEND_SERVER.md').read_text()
        for needle in ('workshop_sync.py', 'workshop_publish.py', '-serverMod', 'Unlisted', 'Publisher'):
            self.assertIn(needle, text)
        self.assertNotIn('@HollowCountryExpansionAI` in `-mod`', text)


if __name__ == '__main__':
    unittest.main()
