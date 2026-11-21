"""RPT phase classification using native module markers; no native process."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from tools.release import rpt_summary as rpt


MISSION = 'SCRIPT : Module: Mission; loaded\n'
ERROR = 'SCRIPT (E): JSON ERROR\n'
READY = '[HC Ready] module=Events enabled=true ready=true\n'
CONNECT = 'Player connect enabled\n'


class RptSummaryTests(unittest.TestCase):
    def scan(self, text):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / 'server.RPT'
        path.write_text(text)
        summary = rpt.Summary(path)
        self.addCleanup(summary.close)
        return summary.scan()

    def test_script_error_phase_uses_mission_marker(self):
        self.assertRegex(MISSION, rpt.MISSION_LOADED)
        for prefix, expected in [('', 'compile_failed'),
                                 ('Module: World; loaded\n', 'compile_failed'),
                                 (MISSION, 'script_error')]:
            with self.subTest(prefix=prefix):
                summary = self.scan(prefix + ERROR + CONNECT + READY)
                self.assertEqual(summary.outcome, expected)
                field = 'script_errors' if expected == 'script_error' else 'compile_errors'
                self.assertEqual(summary.header()[field], [ERROR.strip()])
                self.assertTrue(summary.ready_last['Events'])

    def test_earlier_compile_error_is_not_reclassified(self):
        summary = self.scan(ERROR + MISSION + ERROR + READY)
        self.assertEqual(summary.outcome, 'compile_failed')
        self.assertEqual(summary.failures, {'compile_failed', 'script_error'})

    def test_explicit_compile_marker_still_fails_after_mission(self):
        line = "Can't compile Mission script module"
        self.assertRegex(line, rpt.COMPILE_MARKER)
        self.assertEqual(self.scan(MISSION + line + '\n').outcome, 'compile_failed')

    def test_runtime_error_fails_even_when_privacy_filter_drops_it(self):
        summary = self.scan(MISSION + 'SCRIPT (E): name=private\n' + CONNECT)
        self.assertEqual(summary.outcome, 'script_error')
        self.assertEqual(summary.script_errors, [])
        self.assertEqual(summary.header()['compile_result'], 'no_compile_error_observed')

    def test_crash_takes_precedence_over_runtime_error(self):
        self.assertEqual(self.scan(MISSION + ERROR + 'Unhandled exception\n').outcome, 'crashed')

    def test_runtime_error_cli_has_distinct_failure_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'server.RPT'
            path.write_text(MISSION + ERROR + CONNECT)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                runtime_code = rpt.main([str(path), '--json'])
            self.assertNotEqual(runtime_code, 0)
            self.assertIn('"outcome": "script_error"', output.getvalue())
            path.write_text(ERROR)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertNotEqual(runtime_code, rpt.main([str(path)]))
