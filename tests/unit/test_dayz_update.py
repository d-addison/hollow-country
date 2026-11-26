"""Synthetic update evidence only: no network, installed files or native process launches."""
import contextlib
import io
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.release import dayz_update as update
from tools.validate import dayz_build


def pbo(path, entries):
    header, body = b'', b''
    for name, method, content in entries:
        header += name.encode() + b'\0' + struct.pack('<IIIII', method, len(content), 0, 0, len(content))
        body += content
    path.write_bytes(header + b'\0' + bytes(20) + body)


class UpdateTests(unittest.TestCase):
    def test_acf_nested_comments_and_escapes(self):
        doc = update.parse_acf('// comment\n"AppWorkshop" { "WorkshopItemsInstalled" { "12" { "timeupdated" "100" } } }')
        self.assertEqual('100', doc['appworkshop']['workshopitemsinstalled']['12']['timeupdated'])
        for text in ('"a" { "b"', '}', '"a" {'):
            with self.assertRaises(ValueError):
                update.parse_acf(text)

    def test_manifest_roots_and_tools_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / 'appmanifest_830640.acf'
            app.write_text('"AppState" { "appid" "830640" "buildid" "123" "installdir" "DayZ Tools" }')
            self.assertEqual('123', update.manifest('830640', root / 'absent', root)['buildid'])
            app.write_text('"AppState" { "appid" "830640" "buildid" "123" "installdir" "../escape" }')
            with self.assertRaises(ValueError):
                update.manifest('830640', root, root)

    def test_exe_version_synthetic_utf16(self):
        data = bytes(37) + 'FileVersion\0\x001.30.164.289\0'.encode('utf-16le')
        data += 'ProductVersion\0\x001.30.164289.70\0'.encode('utf-16le')
        self.assertEqual('1.30.164289', update.parse_exe_version(data))
        self.assertEqual('2.1.123456', update.parse_exe_version('ProductVersion\0 2, 1, 123456, 0\0'.encode('utf-16le')))
        with self.assertRaises(ValueError):
            update.parse_exe_version(b'not an exe version')
        with self.assertRaises(ValueError):
            update.parse_exe_version(data + 'ProductVersion\0 2.1.123456.0\0'.encode('utf-16le'))

    def test_app_state_table(self):
        cases = [((None, '100', '100', None), 'unknown(network)'),
                 (('100', '100', '100', None), 'current'),
                 (('100', '100', '101', '102'), 'update-available'),
                 (('101', '100', '101', None), 'installed-not-pinned'),
                 (('100', '100', '100', '101'), 'experimental-only'),
                 (('100', '100', None, None), 'unknown(network)'),
                 (('101', '100', None, None), 'installed-not-pinned')]
        for args, state in cases:
            with self.subTest(args=args):
                self.assertEqual(state, update.app_state(*args))
        self.assertEqual('unknown(network)', update.app_state('100', '100', network=False))

    def test_workshop_states_and_old_receipt(self):
        self.assertEqual('current', update.workshop_state(100, 100, 100))
        self.assertEqual('update-available', update.workshop_state(99, None, 100))
        self.assertEqual('current', update.workshop_state(100, None, 100))
        self.assertEqual({}, update.receipt_times({'schema': 1, 'files': [{'path': '@CF/addons/cf.pbo'}]}))
        self.assertEqual({'12': 100}, update.receipt_times({'mods': [{'id': '12', 'time_updated': 100}]}))

    def test_extraction_refuses_paths_compression_and_budgets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'scripts.pbo'
            for name, method in [('../escape.c', 0), ('/absolute.c', 0), ('C:\\escape.c', 0), ('..\\escape.c', 0), ('3_Game/a.c', 1)]:
                with self.subTest(name=name, method=method):
                    pbo(archive, [(name, method, b'content')])
                    with self.assertRaises(ValueError):
                        update.extract_scripts(archive, root / 'cache')
                    self.assertFalse((root / 'cache').exists())
            pbo(archive, [('3_Game/a.c', 0, b'content')])
            with patch.object(update, 'MAX_MEMBER', 2), self.assertRaises(ValueError):
                update.extract_scripts(archive, root / 'cache')
            with patch.object(update, 'MAX_TOTAL', 2), self.assertRaises(ValueError):
                update.extract_scripts(archive, root / 'cache')
            destination = root / 'link'
            destination.symlink_to(root / 'elsewhere')
            with self.assertRaisesRegex(ValueError, 'symlink'):
                update.extract_scripts(archive, destination)

    def test_extraction_atomic_reuse_and_different_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive, cache = root / 'scripts.pbo', root / 'cache'
            pbo(archive, [('3_Game/test.c', 0, b'class Test {}')])
            result = update.extract_scripts(archive, cache)
            self.assertEqual(1, result['entry_count'])
            self.assertEqual(b'class Test {}', (cache / '3_Game/test.c').read_bytes())
            self.assertEqual(result, update.extract_scripts(archive, cache))
            (cache / '3_Game/test.c').write_bytes(b'different')
            with self.assertRaisesRegex(ValueError, 'different'):
                update.extract_scripts(archive, cache)
            (cache / '3_Game/test.c').unlink()
            (cache / '3_Game/test.c').symlink_to(archive)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                update.extract_scripts(archive, cache)

    def test_symbol_diff_conservative_filter(self):
        old = {'class:Foo': [('0', 'Parent')], 'method:Foo.Bar': [('int',)],
               'field:Other.Value': [('int',)], 'method:Unused.Hidden': [('void',)]}
        new = {'class:Foo': [('0', 'NewParent')], 'method:Foo.Bar': [('string',)]}
        result = update.symbol_diff(old, new, {'Bar', 'Value'})
        self.assertEqual(4, result['full_count'])
        self.assertEqual(2, result['referenced_count'])
        self.assertEqual(['field:Other.Value', 'method:Foo.Bar'], [row['symbol'] for row in result['referenced']])
        self.assertEqual(2, update.symbol_diff(old, new, {'Foo'})['referenced_count'])

    def test_shared_build_check(self):
        pin = {'steam': {'221100': '100', '223350': '100'}}
        with patch.object(dayz_build, 'manifest', return_value={'buildid': '100'}):
            self.assertEqual('pass', update.build_check(pin=pin)[0])
        with patch.object(dayz_build, 'manifest', side_effect=ValueError('missing')):
            self.assertEqual('needs-host-check', update.build_check(pin=pin)[0])
        with patch.object(dayz_build, 'manifest', return_value={'buildid': '101'}):
            state, message = update.build_check(pin=pin)
            self.assertEqual('FAIL', state)
            self.assertIn('prepare+bump first: native cache is stale', message)

    def test_offline_check_never_calls_network(self):
        with patch.object(update, 'request_json', side_effect=AssertionError('network forbidden')), \
             patch.object(update, 'manifest', side_effect=ValueError('synthetic absent')), \
             patch.object(update, 'read_acf', side_effect=ValueError('synthetic absent')), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(2, update.main(['check', '--offline', '--json']))
        self.assertTrue(json.loads(output.getvalue())['offline'])

    def test_signature_diff_includes_native_return_types_and_overloads(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            layer = root / '3_Game'
            layer.mkdir()
            source = layer / 'api.c'
            source.write_text('class API { proto native int Read(float value); int Count; }')
            old = update.signature_index(root)
            source.write_text('class API { proto native string Read(float value); string Count; }')
            new = update.signature_index(root)
            result = update.symbol_diff(old, new, {'Read', 'Count'})
            self.assertEqual(2, result['referenced_count'])
            self.assertEqual('int', old['method:API.Read'][0][1])
            self.assertEqual('string', new['method:API.Read'][0][1])

    def test_empty_acf_value_and_nesting_budget(self):
        self.assertEqual({'a': ''}, update.parse_acf('"a" ""'))
        with self.assertRaises(ValueError):
            update.parse_acf('"a" {' * 34 + '}' * 34)

    def test_prepare_refuses_exe_mismatch_before_extraction(self):
        with patch.object(update, 'installed_server', return_value=Path('/synthetic')), \
             patch.object(update, 'exe_version', return_value='1.31.999999'), \
             patch.object(update, 'extract_scripts') as extract, \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, update.main(['prepare', '--build', dayz_build.pinned()]))
        extract.assert_not_called()

    def test_bump_requires_lint_or_recorded_force_and_checks_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pin = root / 'pin.json'
            pin.write_text(json.dumps({'schema': 1, 'build': '1.30.164289', 'steam': {},
                                       'server_scripts_pbo_sha256': 'b' * 64}))
            build = '1.31.999999'
            report = {'schema': 1, 'build': build, 'prepared': True,
                      'enforce_lint': {'passed': False}, 'extraction': {'sha256': 'a' * 64}}
            update.write_report(root / build, report)
            with patch.object(dayz_build, 'PIN', pin), \
                 patch.object(update, 'installed_server', return_value=Path('/synthetic')), \
                 patch.object(update, 'exe_version', return_value=build), \
                 patch.object(update, 'sha256', return_value='a' * 64), \
                 patch.object(update, 'manifest', return_value={'buildid': '123'}), \
                 patch.object(update, 'refresh_dependency_pins'), \
                 patch.object(update, 'run_tool', return_value={'passed': True, 'output': 'PASS'}) as run, \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                args = ['bump', '--build', build, '--report-root', str(root)]
                self.assertEqual(2, update.main(args))
                self.assertEqual('1.30.164289', json.loads(pin.read_text())['build'])
                run.assert_not_called()
                self.assertEqual(0, update.main(args + ['--force', 'reviewed API incompatibility']))
                self.assertEqual(build, json.loads(pin.read_text())['build'])
                self.assertEqual('reviewed API incompatibility', json.loads((root / build / 'report.json').read_text())['force_reason'])
                self.assertEqual('tools.package.regenerate_all', run.call_args.args[0])
                self.assertEqual(['--check'], run.call_args.args[1])

    def test_check_old_receipt_exit_codes_and_json_out(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'tools/setup').mkdir(parents=True)
            (root / 'tools/setup/workshop_mods.json').write_text('{"mods": [{"id": "12"}]}')
            server = root / 'server'
            server.mkdir()
            (server / 'hollow-country-workshop-receipt.json').write_text('{"schema": 1, "files": []}')
            pin = {'build': '1.30.164289', 'steam': {ident: '100' for ident in update.APPS}}
            with patch.object(update, 'ROOT', root), \
                 patch.object(dayz_build, 'pin_record', return_value=pin), \
                 patch.object(update, 'manifest', return_value={'buildid': '100', 'root': server}), \
                 patch.object(update, 'exe_version', return_value=pin['build']), \
                 patch.object(update, 'read_acf', return_value={'appworkshop': {
                     'workshopitemsinstalled': {'12': {'timeupdated': '100'}}}}), \
                 patch.object(update, 'latest_app', return_value={'public': '100', 'experimental': None}), \
                 patch.object(update, 'latest_workshop', return_value={'12': {'time_updated': 100}}) as remote, \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(0, update.main(['check', '--json']))
                self.assertIn('server receipt predates timestamps', output.getvalue())
                remote.return_value = {'12': {'time_updated': 101}}
                self.assertEqual(10, update.main(['check']))
                path = root / 'check.json'
                self.assertEqual(0, update.main(['check', '--json-out', str(path)]))
                self.assertTrue(json.loads(path.read_text())['action_needed'])
                remote.side_effect = ValueError('synthetic failure')
                self.assertEqual(2, update.main(['check', '--json-out', str(path)]))

    def test_workshop_copy_timestamp_receipt(self):
        from tools.setup import workshop_sync as sync
        with tempfile.TemporaryDirectory() as temp:
            workshop = Path(temp) / 'workshop'
            content = workshop / 'content/221100'
            content.mkdir(parents=True)
            (workshop / 'appworkshop_221100.acf').write_text(
                '\"AppWorkshop\" { \"WorkshopItemsInstalled\" { \"12\" { \"timeupdated\" \"100\" } } }')
            self.assertEqual(100, sync.workshop_timestamps([content])[(str(content), '12')])
            doc = sync.receipt_data({}, set(), [{'id': '12', 'timeupdated': 100}])
            self.assertEqual({'12': 100}, update.receipt_times(doc))

    def test_install_records_source_acf_timestamp(self):
        from tools.setup import workshop_sync as sync
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            content = root / 'workshop/content/221100'
            item = sync.select(sync.load_manifest(sync.DEFAULT_MANIFEST), ['snafu'])[0]
            source = content / item['id']
            (source / 'addons').mkdir(parents=True)
            (source / 'keys').mkdir()
            (source / 'addons/example.pbo').write_bytes(b'synthetic pbo')
            (source / 'keys/example.bikey').write_bytes(b'synthetic public key')
            (root / 'workshop/appworkshop_221100.acf').write_text(
                '\"AppWorkshop\" { \"WorkshopItemsInstalled\" { \"' + item['id'] + '\" { \"timeupdated\" \"100\" } } }')
            server = root / 'server'
            server.mkdir()
            args = ['install', '--server-root', str(server), '--workshop-content', str(content),
                    '--groups', 'snafu', '--assume-stopped']
            with patch.object(sync.subprocess, 'run', side_effect=AssertionError('no process')):
                self.assertEqual(0, sync.main(args, out=io.StringIO()))
                self.assertEqual(0, sync.main(args, out=io.StringIO()))
            receipt = json.loads((server / sync.RECEIPT_NAME).read_text())
            self.assertEqual({item['id']: 100}, update.receipt_times(receipt))

    def test_experimental_public_branch_and_allowlist(self):
        with patch.object(update, 'request_json', return_value={
                'data': {'223350': {'depots': {'branches': {
                    'public': {'buildid': '100'}, 'experimental_public': {'buildid': '101'}}}}}}):
            self.assertEqual({'public': '100', 'experimental': '101'}, update.latest_app('223350'))
        for url in ('http://api.steamcmd.net/a', 'https://evil.test/',
                    'https://user@api.steamcmd.net/', 'https://api.steamcmd.net:444/'):
            with self.assertRaises(ValueError):
                update.allowed_url(url)

    def test_dependency_pin_refresh(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'config').mkdir()
            for name in ('hollow-country-variant-dependencies.json', 'hollow-country-winter-terrain.json'):
                (root / 'config' / name).write_text(json.dumps({
                    'evidence': {'native_scripts': 'old'}, 'versions': [{'game_build': 'old'}],
                    'citation': 'observed 164289:14'}))
            with patch.object(update, 'ROOT', root):
                update.refresh_dependency_pins('1.31.999999')
            doc = json.loads((root / 'config' / name).read_text())
            self.assertTrue(doc['evidence']['native_scripts'].endswith('scripts-1.31.999999'))
            self.assertEqual('1.31.999999', doc['versions'][0]['game_build'])
            self.assertEqual('observed 164289:14', doc['citation'])

    def test_notify_local_only_and_timer_dry_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            event = root / 'event.json'
            event.write_text(json.dumps({'kind': 'dayz_update', 'source': 'dayz-update',
                'payload': {'build': '1.31.999999', 'rows': [{'name': 'Server', 'state': 'update-available'}]}}))
            with patch.object(update, 'REPORT_ROOT', root), \
                 patch.object(update.subprocess, 'run', side_effect=AssertionError('no subprocess')), \
                 patch.object(update, 'request_json', side_effect=AssertionError('no network')), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, update.main(['notify', '--event', str(event)]))
            self.assertIn('native gate and soak remain pending', (root / 'pending.md').read_text())
            for action in ('install', 'remove', 'status'):
                with patch.object(update.subprocess, 'run', return_value=subprocess.CompletedProcess(
                        [], 0, str(root / '.git'), '')) as run, contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(0, update.main(['timer', action, '--dry-run']))
                    self.assertIn('systemctl --user', output.getvalue())
                    self.assertEqual(1, run.call_count)  # read-only git lookup only
            self.assertFalse((root / '.config').exists())

    def test_queue_refuses_dirty_unpushed_or_non_bump_commit(self):
        build = '1.31.999999'
        cases = [([' M file'], 'clean tree'), (['', 'a' * 40, ''], 'unpushed'),
                 (['', 'a' * 40, 'origin/dev', json.dumps({'build': '1.30.164289'}), 'config/dayz-build.json'], 'bump commit')]
        for outputs, message in cases:
            results = [subprocess.CompletedProcess([], 0, value, '') for value in outputs]
            with patch.object(update.subprocess, 'run', side_effect=results) as run:
                with self.assertRaisesRegex(ValueError, message):
                    update.queue_compile(build, {'bumped': True})
                self.assertTrue(all(call.args[0][0] == 'git' for call in run.call_args_list))

    def test_force_requires_reason_and_prepare_report(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, update.main(['bump', '--build', dayz_build.pinned(), '--report-root', temp, '--force', 'reason']))


if __name__ == '__main__':
    unittest.main()
