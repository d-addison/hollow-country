"""Synthetic Python log evidence only; no native launches."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.release import client_compile_check as check, release_gate as gate
from tools.testing import soak_campaign as camp


class ClientCompileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rpt = self.root / 'client.RPT'
        self.rpt.write_text('[HC Driver] step=s01 kind=wait result=ok detail=ok\n')
        self.script = self.root / 'script_1.log'

    def test_clean_and_missing_completion(self):
        self.assertTrue(check.scan(self.rpt)['passed'])
        self.rpt.write_text('[HC Driver] connect session start\n')
        self.assertEqual(check.scan(self.rpt)['reason'], 'completion_missing')
        self.script.write_text('SCRIPT       : Module: Mission; loaded 42x files\n')
        self.assertTrue(check.scan(self.rpt)['passed'])

    def test_compile_errors_in_either_log_override_completion(self):
        for diagnostic in ("Can't compile \"Game\" script module!",
                           "Multiple declaration of function 'Connect'",
                           "SCRIPT (E): Can't compile World script module!", 'Cannot compile Mission',
                           'Failed to load World script', 'Compile error',
                           'Unable to load script module', 'Script validation failed',
                           'Script module load failed'):
            for path in (self.rpt, self.script):
                with self.subTest(diagnostic=diagnostic, log=path.name):
                    self.rpt.write_text('[HC Driver] step=s01 kind=wait result=ok detail=ok\n')
                    self.script.write_text('SCRIPT (W): warning only\n')
                    with path.open('a') as stream:
                        stream.write(diagnostic + '\n')
                    result = check.scan(self.rpt)
                    self.assertFalse(result['passed'])
                    self.assertEqual(result['reason'], 'compile_errors')
                    self.assertEqual(result['compile_errors'], 1)
                    self.assertEqual(result['errors'], 1)
                    self.assertEqual(result['runtime_errors'], 0)

    def test_runtime_only_is_reported_and_cli_passes_with_completion(self):
        self.script.write_text('SCRIPT    (E): NULL pointer to instance\n'
                               'SCRIPT (E): unknown function\n')
        result = check.scan(self.rpt)
        self.assertTrue(result['passed'])
        self.assertEqual(result['reason'], 'clean')
        self.assertEqual(result['compile_errors'], 0)
        self.assertEqual(result['runtime_errors'], 2)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(check.main(['--rpt', str(self.rpt)]), 0)
        self.assertIn('errors=0 runtime_errors=2 complete=true', out.getvalue())
        self.rpt.write_text('boot\n')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check.main(['--rpt', str(self.rpt)]), 1)
        self.assertEqual(check.scan(self.rpt)['reason'], 'completion_missing')

    def test_verdict_accepts_existing_compile_only_results(self):
        # Existing release-gate callers/tests may supply the original result schema.
        result = dict(passed=True, reason='clean', logs=1, errors=0, complete=True)
        self.assertIn('errors=0 runtime_errors=0 complete=true', check.verdict_line(result))

    def test_compile_marker_precedence_over_runtime_and_completion(self):
        self.script.write_text('SCRIPT (E): NULL pointer\n'
                               'SCRIPT (E): Cannot compile Mission\n')
        result = check.scan(self.rpt)
        self.assertEqual((result['compile_errors'], result['runtime_errors']), (1, 1))
        self.assertEqual(result['reason'], 'compile_errors')
        self.assertFalse(result['passed'])

    def test_poll_cache_reads_only_appends_and_rechecks_partial_lines(self):
        scanner = check.Scanner()
        self.script.write_text('SCRIPT (E): NULL pointer\nSCRIPT (E): Can')
        self.assertEqual(scanner.scan(self.rpt)['runtime_errors'], 2)
        with patch.object(Path, 'open', side_effect=AssertionError('unchanged file reread')):
            self.assertEqual(scanner.scan(self.rpt)['runtime_errors'], 2)
        with self.script.open('a') as stream:
            stream.write("'t compile World\n")
        with patch.object(check, '_counts', wraps=check._counts) as counts:
            result = scanner.scan(self.rpt)
        self.assertEqual(counts.call_count, 1)
        self.assertEqual(result, check.scan(self.rpt))
        self.assertEqual((result['compile_errors'], result['runtime_errors']), (1, 1))

    def test_poll_cache_resets_edited_truncated_and_replaced_logs_and_discovers_new(self):
        scanner = check.Scanner()
        self.script.write_text('SCRIPT (E): NULL pointer\n')
        self.assertEqual(scanner.scan(self.rpt)['runtime_errors'], 1)
        # Same-size edit must not reuse a stale count, even with a coarse mtime.
        self.script.write_text('x' * (self.script.stat().st_size - 1) + '\n')
        import os
        stamp = self.script.stat().st_mtime_ns
        os.utime(self.script, ns=(stamp, stamp + 1_000_000_000))
        self.assertEqual(scanner.scan(self.rpt)['runtime_errors'], 0)
        self.script.write_text('boot\n')
        self.assertEqual(scanner.scan(self.rpt), check.scan(self.rpt))
        replacement = self.root / 'replacement'
        replacement.write_text('SCRIPT (E): Cannot compile Mission\n')
        replacement.replace(self.script)
        self.assertEqual(scanner.scan(self.rpt)['compile_errors'], 1)
        self.script.unlink()
        new = self.root / 'script_2.log'
        new.write_text('SCRIPT (E): NULL pointer\n')
        self.assertEqual(scanner.scan(self.rpt)['runtime_errors'], 1)
        self.assertNotIn(self.script, scanner.files)

    def test_poll_cache_keeps_byte_line_and_file_bounds(self):
        scanner = check.Scanner()
        self.assertTrue(scanner.scan(self.rpt)['passed'])
        with patch.object(check, 'MAX_BYTES', self.rpt.stat().st_size - 1):
            self.assertFalse(scanner.scan(self.rpt)['passed'])
        self.script.write_text('x' * check.MAX_LINE)
        scanner.scan(self.rpt)
        with self.script.open('a') as stream:
            stream.write('x')
        self.assertEqual(scanner.scan(self.rpt)['reason'], 'logs_oversized')
        self.script.unlink()
        for i in range(32):
            (self.root / f'script_{i}.log').touch()
        self.assertEqual(scanner.scan(self.rpt)['reason'], 'too_many_logs')
        self.assertEqual(scanner.files, {})

    def test_missing_unreadable_and_bounded_logs_fail_closed(self):
        self.assertFalse(check.scan(None)['passed'])
        self.assertFalse(check.scan(self.root / 'missing.RPT')['passed'])
        self.assertFalse(check.scan(self.rpt, [self.root / 'missing.log'])['passed'])
        with patch.object(Path, 'open', side_effect=PermissionError):
            self.assertFalse(check.scan(self.rpt)['passed'])
        self.script.write_bytes(b'x' * (check.MAX_LINE + 1))
        self.assertFalse(check.scan(self.rpt)['passed'])
        self.script.unlink()
        with patch.object(check, 'MAX_BYTES', 2):
            self.assertFalse(check.scan(self.rpt)['passed'])

    def test_explicit_logs_and_safe_cli_verdict(self):
        self.script.write_text("Multiple declaration of function 'Connect' private detail\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = check.main(['--rpt', str(self.rpt), '--script-log', str(self.script)])
        self.assertEqual(code, 1)
        self.assertIn('client_compile_check: FAIL reason=compile_errors', out.getvalue())
        self.assertNotIn('private detail', out.getvalue())
        self.assertNotIn(str(self.root), out.getvalue())
        self.assertTrue(check.scan(self.rpt, [])['passed'])
        self.script.unlink()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check.main(['--rpt', str(self.rpt)]), 0)

    def test_r3_refuses_before_activity_even_when_counters_would_pass(self):
        from types import SimpleNamespace
        args = SimpleNamespace(smoke_use=[f'{c}=Core/{c}' for c in gate.CATEGORIES], client_timeout=1)
        steps = gate.NativeSteps(args)
        steps.client_rpt = self.rpt
        self.script.write_text("Multiple declaration of function 'Connect'\n")
        with patch.object(gate, 'emit'), patch.object(gate.activity_check, 'scan') as activity:
            with self.assertRaisesRegex(gate.Refused, 'client compile check failed: compile_errors'):
                steps.client()
        activity.assert_not_called()

    def test_campaign_report_and_exit_code_include_compile_failure(self):
        keep = self.root / 'last-run'
        (keep / 'client').mkdir(parents=True)
        (keep / 'server').mkdir()
        (keep / 'client/client.RPT').write_text("Multiple declaration of function 'Connect'\n")
        (keep / 'server/server.RPT').write_text('server\n')
        for failed, code in ((True, 8), (False, 0)):
            if not failed:
                (keep / 'client/client.RPT').write_text('[HC Driver] step=s01 kind=wait result=ok detail=ok\n')
            with patch.object(camp, 'activity_results', return_value=(None, None, [])):
                out = io.StringIO()
                self.assertEqual(camp.command_report({}, self.root, out), code)
                self.assertIn('client_compile_check: ' + ('FAIL' if failed else 'PASS'), out.getvalue())


if __name__ == '__main__':
    unittest.main()
