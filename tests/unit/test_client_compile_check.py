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
                           'SCRIPT (E): unknown function', 'Cannot compile Mission',
                           'Failed to load World script', 'Compile error',
                           'Unable to load script module'):
            for path in (self.rpt, self.script):
                with self.subTest(diagnostic=diagnostic, log=path.name):
                    self.rpt.write_text('[HC Driver] step=s01 kind=wait result=ok detail=ok\n')
                    self.script.write_text('SCRIPT (W): warning only\n')
                    with path.open('a') as stream:
                        stream.write(diagnostic + '\n')
                    result = check.scan(self.rpt)
                    self.assertFalse(result['passed'])
                    self.assertEqual(result['reason'], 'compile_errors')

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
