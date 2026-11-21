"""Focused tooling checks; no Enforce emulation or engine acceptance claims."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.release import wb_compile as wb


def evidence(probes=wb.MODULES):
    """Module load lines plus probe markers, as the Workbench runtime logs them."""
    return '\n'.join(['Module: Game; loaded 9x files', 'Module: Mission; loaded 9x files']
                     + ['SCRIPT (W): @"%s/probe/%s/hc_wb_probe.c,9": \'Mark\' is obsolete: %s %s'
                        % (wb.TOOL, module, wb.PROBE, module) for module in probes])


class DiagnosticsTests(unittest.TestCase):
    def test_location_formats_and_error_header_context(self):
        cases = [('scripts/4_World/bad.c(17)', 17),
                 ('HollowCountry/scripts/3_Game/bad.c:23', 23),
                 ('@"HollowCountry/scripts/3_Game/bad.c,8"', 8)]
        for location, number in cases:
            with self.subTest(location=location):
                result = wb.diagnostics("SCRIPT (E): Can't compile World\n" + location + ': unknown type')
                self.assertEqual(result[0]['line'], number)
                self.assertTrue(result[0]['file'].endswith('bad.c'))

    def test_private_error_still_fails(self):
        text = ('SCRIPT (E): playerName=private SteamID=12345678901234567\n'
                'C:/Users/Secret Folder/HollowCountry/scripts/bad.c(4)\n' + evidence())
        report = wb.verdict(text, 0)
        serialized = json.dumps(report)
        for forbidden in ('Secret', 'Folder', '12345678901234567', 'playerName=private'):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(report['errors'][0]['line'], 4)
        self.assertEqual(report['status'], 'compile_failed')

    def test_no_false_pass_from_exit_plugin_or_success_alone(self):
        for text in ('', wb.RECEIPT, wb.SUCCESS, wb.RECEIPT + '\n' + wb.SUCCESS,
                     evidence(wb.MODULES[:-1])):
            self.assertEqual(wb.verdict(text, 0)['status'], 'unverified')
        text = evidence()
        report = wb.verdict(text, 0)
        self.assertEqual(report['status'], 'passed')
        self.assertTrue(report['native_validation_completed'])
        self.assertEqual(report['probe_modules'], sorted(wb.MODULES))
        self.assertEqual(report['warnings_ours'], [])
        self.assertFalse(report['route_qualified'])
        self.assertEqual(wb.verdict(text, 9)['status'], 'tool_failed')
        self.assertEqual(wb.verdict(evidence(()), None, True)['status'], 'timeout')
        self.assertEqual(wb.verdict(text, 0, truncated=True)['status'], 'incomplete_logs')
        self.assertEqual(wb.verdict(text + '\nScript validation failed.', 0)['status'], 'compile_failed')
        failed = wb.verdict(text + '\nSCRIPT (E): Can\'t compile "Game" script module!', 0)
        self.assertEqual(failed['errors'][0]['class'], 'compile_failure')

    def test_known_vanilla_noise_is_counted_not_blocking(self):
        noise = ['SCRIPT (E): Missing script declaration for method \'Fixture\'',
                 'SCRIPT (E): scripts/1_Core/fixture.c(3): Method not linked',
                 'SCRIPT (E): Cannot write offline shader cache']
        report = wb.verdict('\n'.join(noise) + '\n' + evidence(), 0)
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(report['triage']['errors'], {'known_vanilla': len(noise)})
        ours = wb.verdict('SCRIPT (E): Missing script declaration @"HollowCountry/scripts/3_Game/a.c,2"\n'
                          + evidence(), 0)
        self.assertEqual(ours['status'], 'compile_failed')
        unknown = wb.verdict('SCRIPT (E): unexplained\n' + evidence(), 0)
        self.assertEqual(unknown['errors'][0]['class'], 'unclassified')

    def test_log_collection_is_bounded_and_ignores_nonlogs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'a.log').write_text('SCRIPT (E): bad.c(5): bad')
            (root / 'secret.txt').write_text('private')
            text, truncated = wb.collect_logs(root)
            self.assertIn('bad.c', text)
            self.assertNotIn('private', text)
            self.assertFalse(truncated)
            with patch.object(wb, 'MAX_LOG', 3):
                self.assertTrue(wb.collect_logs(root)[1])


class DriverTests(unittest.TestCase):
    def test_running_and_unknown_refuse_before_temp_or_launch(self):
        for state in ('running', 'unknown'):
            with self.subTest(state=state), patch.object(wb.winproc, 'process_state', return_value=state), \
                    patch.object(wb.winproc, 'run') as interop, patch.object(wb.subprocess, 'Popen') as launch:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(wb.main([]), 2)
                self.assertEqual(json.loads(output.getvalue())['status'], 'blocked')
                interop.assert_not_called()
                launch.assert_not_called()

    def test_stage_uses_ship_catalogue_probes_authored_classes_and_no_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tree, workshop, scratch = root / 'tree', root / 'workshop', root / 'scratch'
            plugin = tree / 'tools/workbench/HC_CompileCheck.c'
            plugin.parent.mkdir(parents=True)
            plugin.write_text('// fixture')
            dependency = workshop / '@Fixture'
            for mod in ('HollowCountry', 'HollowCountryExpansionAI', 'Ignored'):
                for module in wb.MODULES:
                    path = tree / 'mods' / mod / 'scripts' / module / 'authored.c'
                    path.parent.mkdir(parents=True)
                    path.write_text('#ifdef X\nclass Hidden%s {}\n#endif\n' % mod)
                    path.with_name('plain.c').write_text('class Plain%s%s\n{\n}\n' % (mod, module[0]))
                    path.with_suffix('.paa').write_bytes(b'asset')

            @contextlib.contextmanager
            def compatibility(*_):
                yield {'extra_mods': [dependency]}

            def collect(path, prefix=None):
                return {item.relative_to(path).as_posix(): item.read_bytes() for item in path.rglob('*.c')}

            def fresh():
                if scratch.exists():
                    wb.shutil.rmtree(scratch)
                scratch.mkdir()
                return wb.stage(tree, workshop, scratch)

            with patch.object(wb.ship_inputs, 'signing_inputs', wraps=wb.ship_inputs.signing_inputs) as catalogue, \
                    patch.object(wb.compile_gate, 'compatibility_inputs', side_effect=compatibility), \
                    patch.object(wb.pbo, 'collect_addon', side_effect=collect), \
                    patch.object(wb.pbo, 'pack', side_effect=lambda files, prefix=None: b''.join(files.values())):
                mods, probes, counts = fresh()
                catalogue.assert_called_once_with()
                self.assertEqual(mods[0], dependency)
                self.assertEqual([mod.name for mod in mods[1:]],
                                 ['@HollowCountry', '@HollowCountryExpansionAI', '@' + wb.TOOL])
                self.assertEqual(probes, list(wb.MODULES))
                self.assertEqual(counts['HollowCountry'], len(wb.MODULES) * 2)
                self.assertEqual(counts['dependency_mods'], 1)
                self.assertFalse((scratch / '@Ignored').exists())
                self.assertFalse(list(scratch.rglob('*.paa')))
                self.assertTrue((scratch / 'profile').is_dir())
                files, _ = wb.tool_mod(tree, ['HollowCountry', 'HollowCountryExpansionAI'])
                for module in wb.MODULES:
                    probe = files['probe/%s/hc_wb_probe.c' % module].decode()
                    self.assertIn('%s %s' % (wb.PROBE, module), probe)
                    self.assertIn('PlainHollowCountry' + module[0], probe)
                    self.assertNotIn('Hidden', probe)
                self.assertIn(b'workbenchScriptModule', files['config.cpp'])
                for _, mod in wb.REQUIRED_SCRIPT_INPUTS:
                    scripts = tree / 'mods' / mod / 'scripts'
                    hidden = scripts.with_name('hidden')
                    scripts.rename(hidden)
                    with self.subTest(mod=mod, state='missing'), self.assertRaisesRegex(ValueError, 'directory absent'):
                        fresh()
                    (scripts / 'empty').mkdir(parents=True)
                    with self.subTest(mod=mod, state='empty'), self.assertRaisesRegex(ValueError, 'empty required'):
                        fresh()
                    wb.shutil.rmtree(scripts)
                    hidden.rename(scripts)
            with patch.object(wb.ship_inputs, 'signing_inputs', return_value=[]), \
                    self.assertRaisesRegex(ValueError, 'absent from ship catalogue'):
                fresh()

    def test_driver_collects_engine_failure_after_owned_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            executable = root / 'WorkbenchApp.exe'
            executable.touch()
            args = SimpleNamespace(workbench=root, tree=root, workshop=root, keep_scratch=False,
                                   commit=None, seconds=10, action_path='Validate Scripts')

            def staged(tree, workshop, scratch):
                (scratch / 'profile').mkdir()
                (scratch / 'profile/script.log').write_text(
                    'SCRIPT (E): @"HollowCountry/scripts/3_Game/bad.c,8": invalid')
                (scratch / 'stderr.txt').write_text('client identity 12345678901234567')
                return [scratch / '@HollowCountry'], list(wb.MODULES), {'fixture': 1}

            receipts = ['{"exit_code":0,"timed_out":false,"cleanup_confirmed":true,"launched":true,'
                        '"failure":null,"authorization_denied":1,"plugin_dialogs_dismissed":2}',
                        '{"exit_code":null,"timed_out":true,"cleanup_confirmed":false,"launched":true}',
                        None]
            with patch.object(wb.winproc, 'process_state', return_value='gone'), \
                    patch.object(wb.winproc, 'run', return_value=SimpleNamespace(returncode=0, stdout='C:\\Temp')), \
                    patch.object(wb, 'linux_path', return_value=root), \
                    patch.object(wb.compile_gate, 'ship_config'), \
                    patch.object(wb, 'stage', side_effect=staged), \
                    patch.object(wb, 'controller', return_value='fake controller'), \
                    patch.object(wb, 'launch_controller', side_effect=receipts) as launch:
                report, code = wb.run(args)
                self.assertFalse(list(root.glob('hc-wbcompile-*')))
                pending, pending_code = wb.run(args)
                lost, lost_code = wb.run(args)
            self.assertEqual((pending_code, lost_code), (2, 2))
            self.assertEqual(pending['status'], 'cleanup_unconfirmed')
            self.assertEqual(lost['status'], 'cleanup_unconfirmed')
            self.assertEqual(code, 1)
            self.assertEqual(report['status'], 'compile_failed')
            self.assertEqual(report['errors'][0]['line'], 8)
            self.assertFalse(report['route_qualified'])
            self.assertEqual(report['authorization_dialogs_denied'], 1)
            self.assertEqual(report['plugin_error_dialogs_dismissed'], 2)
            self.assertNotIn('12345678901234567', json.dumps(report))
            self.assertEqual(len(list(root.glob('hc-wbcompile-*'))), 2)
            self.assertEqual(launch.call_count, 3)
            self.assertGreater(launch.call_args.args[2], args.seconds)

    def test_launch_controller_starts_once_and_reads_receipt_file(self):
        with tempfile.TemporaryDirectory() as temp:
            scratch = Path(temp)
            now = [0.0]

            def pause(seconds):
                now[0] += seconds
                if now[0] >= 4:
                    (scratch / wb.STARTED_FILE).write_text('1')
                if now[0] >= 10:
                    (scratch / wb.RECEIPT_FILE).write_text('{"settled": true}')

            def tick(seconds):
                now[0] += seconds

            with patch.object(wb, 'windows_path', return_value='C:\\scratch\\controller.ps1'), \
                    patch.object(wb.subprocess, 'run') as start:
                raw = wb.launch_controller('script', scratch, 100, clock=lambda: now[0], pause=pause)
                self.assertEqual(raw, '{"settled": true}')
                self.assertEqual(start.call_count, 1)
                launcher = start.call_args.args[0][-1]
                self.assertNotIn('Bypass', launcher)
                encoded = launcher.rsplit("'", 2)[-2]
                body = wb.base64.b64decode(encoded).decode('utf-16-le')
                self.assertIn(wb.quote_ps('C:\\scratch\\controller.ps1'), body)
                (scratch / wb.RECEIPT_FILE).unlink()
                self.assertIsNone(wb.launch_controller('script', scratch, 30, clock=lambda: now[0], pause=tick))
                (scratch / wb.STARTED_FILE).unlink()
                with self.assertRaises(ValueError):
                    wb.launch_controller('script', scratch, 30, clock=lambda: now[0], pause=tick)
                self.assertEqual(start.call_count, 3)

    def test_controller_has_second_guard_owns_handle_and_bounded_wait(self):
        with patch.object(wb, 'windows_path', side_effect=lambda path: 'C:\\scratch\\' + path.name):
            script = wb.controller(Path('WorkbenchApp.exe'), Path('scratch'), 17, 'Validate Scripts',
                                   [Path('@HollowCountry'), Path('@Dependency')])
        self.assertLess(script.index('Get-Process'), script.index('Start-Process'))
        self.assertIn('AddMilliseconds(17000)', script)
        self.assertIn('-mod=C:\\scratch\\@HollowCountry;C:\\scratch\\@Dependency', script)
        self.assertIn('[HcWbDialogs]::Close($main.Handle)', script)
        self.assertIn('cleanup_confirmed=$cleanupConfirmed', script)
        self.assertIn(wb.RECEIPT_FILE, script)
        self.assertIn('IDIGNORE', script)
        self.assertNotIn('Command($window.Handle, 3)', script)  # never IDABORT
        self.assertIn("-ceq '%s'" % wb.DIALOG_TITLE, script)
        self.assertIn('GetWindowThreadProcessId', script)
        self.assertNotIn('.Kill(', script)
        self.assertNotIn('.WaitForExit()', script)
        self.assertNotIn('SendKeys', script)
        self.assertNotIn('SetForegroundWindow', script)
        self.assertIn('$mutex.WaitOne(0)', script)
        self.assertNotIn('Stop-Process', script)
        self.assertNotIn('taskkill', script)


if __name__ == '__main__':
    unittest.main()
