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


class DiagnosticsTests(unittest.TestCase):
    def test_both_location_formats_and_error_header_context(self):
        cases = [('scripts/4_World/bad.c(17)', 17),
                 ('HollowCountry/scripts/3_Game/bad.c:23', 23)]
        for location, number in cases:
            with self.subTest(location=location):
                result = wb.diagnostics("SCRIPT (E): Can't compile World\n" + location + ': unknown type')
                self.assertEqual(result[0]['line'], number)
                self.assertTrue(result[0]['file'].endswith('bad.c'))

    def test_private_error_still_fails(self):
        text = 'SCRIPT (E): playerName=private SteamID=12345678901234567\nC:/Users/Secret Folder/scripts/bad.c(4)'
        report = wb.verdict(text, 0)
        serialized = json.dumps(report)
        for forbidden in ('Secret', 'Folder', '12345678901234567', 'playerName=private'):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(report['errors'][0]['line'], 4)
        self.assertEqual(report['status'], 'compile_failed')

    def test_no_false_pass_from_exit_plugin_or_success_alone(self):
        for text in ('', wb.RECEIPT, wb.SUCCESS):
            self.assertEqual(wb.verdict(text, 0)['status'], 'unverified')
        text = wb.RECEIPT + '\n' + wb.SUCCESS
        self.assertEqual(wb.verdict(text, 0)['status'], 'passed')
        self.assertEqual(wb.verdict(text, 9)['status'], 'tool_failed')
        self.assertEqual(wb.verdict(text, 0, True)['status'], 'timeout')
        self.assertEqual(wb.verdict(text, 0, truncated=True)['status'], 'incomplete_logs')
        self.assertEqual(wb.verdict(text + '\nScript validation failed.', 0)['status'], 'compile_failed')

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

    def test_stage_uses_ship_catalogue_preserves_native_module_order_and_no_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tree, native, tool, scratch = [root / name for name in ('tree', 'native', 'tool', 'scratch')]
            scratch.mkdir()
            tool.mkdir()
            plugin = tree / 'tools/workbench/HC_CompileCheck.c'
            plugin.parent.mkdir(parents=True)
            plugin.write_text('// fixture')
            for module in wb.MODULES + ('editor/Workbench',):
                path = native / module / 'native.c'
                path.parent.mkdir(parents=True)
                path.write_text('// native fixture')
            for mod in ('Selected', 'Ignored'):
                path = tree / 'mods' / mod / 'scripts/4_World/authored.c'
                path.parent.mkdir(parents=True)
                path.write_text('// authored fixture')
                path.with_suffix('.paa').write_bytes(b'asset')
            template = 'Directory "./"\n' + '\n'.join('Paths { "scripts/' + m + '" }' for m in wb.MODULES)
            (tool / 'dayz.gproj').write_text(template)
            with patch.object(wb.ship_inputs, 'signing_inputs', return_value=[('s', 'Selected', 'base')]) as catalogue, \
                    patch.object(wb, 'windows_path', return_value='C:\\scratch'):
                counts = wb.stage(tree, native, tool, scratch)
            catalogue.assert_called_once_with()
            self.assertIn('Selected', counts)
            self.assertFalse((scratch / 'Ignored').exists())
            self.assertFalse(list(scratch.rglob('*.paa')))
            project = (scratch / 'hc_compile.gproj').read_text()
            self.assertIn('Selected/scripts/4_World', project)
            self.assertEqual(sorted(wb.MODULES, key=project.index), list(wb.MODULES))
            self.assertTrue((scratch / 'scripts/editor/plugins/HC_CompileCheck.c').is_file())

    def test_driver_collects_engine_failure_after_owned_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            executable = root / 'WorkbenchApp.exe'
            executable.touch()
            args = SimpleNamespace(workbench=root, tree=root, native_scripts=root,
                                   commit=None, seconds=10, action_path='Validate Scripts')

            def staged(tree, native, workbench, scratch):
                (scratch / 'stdout.log').write_text("SCRIPT (E): bad.c(8): invalid")
                return {'fixture': 1}

            process = unittest.mock.Mock(returncode=0)
            process.communicate.return_value = (b'{"exit_code":0,"timed_out":false}', b'')
            with patch.object(wb.winproc, 'process_state', return_value='gone'), \
                    patch.object(wb.winproc, 'run', return_value=SimpleNamespace(returncode=0, stdout='C:\\Temp')), \
                    patch.object(wb, 'linux_path', return_value=root), \
                    patch.object(wb, 'stage', side_effect=staged), \
                    patch.object(wb, 'controller', return_value='fake controller'), \
                    patch.object(wb.subprocess, 'Popen', return_value=process):
                report, code = wb.run(args)
            self.assertEqual(code, 1)
            self.assertEqual(report['status'], 'compile_failed')
            self.assertEqual(report['errors'][0]['line'], 8)
            self.assertFalse(list(root.glob('hc-wbcompile-*')))
            process.communicate.assert_called_once_with(timeout=55)
            process.kill.assert_not_called()

    def test_script_links_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'bad.c').symlink_to(root / 'missing')
            with self.assertRaisesRegex(ValueError, 'symlink'):
                wb.copy_scripts(root, root / 'out')

    def test_controller_has_second_guard_owns_handle_and_bounded_wait(self):
        with patch.object(wb, 'windows_path', side_effect=lambda path: 'C:\\scratch\\' + path.name):
            script = wb.controller(Path('WorkbenchApp.exe'), Path('scratch'), 17, 'Validate Scripts')
        self.assertLess(script.index('Get-Process'), script.index('Start-Process'))
        self.assertIn('$owned.WaitForExit(17000)', script)
        self.assertIn('$owned.Kill()', script)
        self.assertIn('$mutex.WaitOne(0)', script)
        self.assertNotIn('Stop-Process', script)
        self.assertNotIn('taskkill', script)


if __name__ == '__main__':
    unittest.main()
