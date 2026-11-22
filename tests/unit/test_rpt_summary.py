"""RPT phase classification using native module markers; no native process."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from tools.release import rpt_summary as rpt


MISSION = 'SCRIPT : Module: Mission; loaded\n'
ERROR = 'SCRIPT (E): JSON ERROR\n'
READY = '12:00:01 [HC Ready] module=Events enabled=true ready=true\n'
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

    def test_summary_exposes_r4_evidence_separately_from_boot_verdict(self):
        from tools.release.acceptance_targets import load_targets
        limit = load_targets()['readiness_max_after_hive_seconds']
        # Minutes keep the fixture valid for configured allowances above a minute.
        seconds = int(limit) + 1
        hour, remainder = divmod(12 * 3600 + seconds, 3600)
        minute, second = divmod(remainder, 60)
        summary = self.scan('12:00:00 ' + rpt.HIVE_FINISHED + '\n' + CONNECT +
            f'{hour:02}:{minute:02}:{second:02} [HC Ready] module=Events enabled=true ready=true\n')
        evidence = summary.header()['readiness_timing']
        self.assertEqual(evidence['status'], 'failed')
        self.assertEqual(evidence['late'], ['Events'])
        self.assertEqual(evidence['limit_seconds'], limit)

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


class ReadinessTimingTests(unittest.TestCase):
    def timing(self, lines, limit=30):
        timing = rpt.ReadinessTiming()
        for line in lines:
            timing.observe(line)
        return timing.result(limit)

    def test_boundary_and_overrun_use_same_boot_hive(self):
        for elapsed, expected in ((30, 'passed'), (30.001, 'failed')):
            result = self.timing(['12:00:00 ' + rpt.HIVE_FINISHED,
                f'12:00:{elapsed:06.3f} [HC Ready] module=Events enabled=true ready=true'])
            self.assertEqual(result['status'], expected)
            self.assertEqual(bool(result['late']), expected == 'failed')

    def test_midnight_and_readiness_before_hive(self):
        result = self.timing(['23:59:55 [HC Ready] module=Core enabled=true ready=true',
            '23:59:59.500 ' + rpt.HIVE_FINISHED,
            '00:00:29.500 [HC Ready] module=Events enabled=true ready=true'])
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['max_after_hive_seconds'], 30)
        self.assertEqual(result['ready_before_hive'], ['Core'])

    def test_only_pre_hive_readiness_has_zero_elapsed(self):
        result = self.timing(['12:00:00 [HC Ready] module=Core enabled=true ready=true',
                              '12:00:05 ' + rpt.HIVE_FINISHED])
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['max_after_hive_seconds'], 0)
        self.assertEqual(result['ready_before_hive'], ['Core'])

    def test_missing_markers_timestamps_and_repeated_boot_fail_closed(self):
        hive = '12:00:00 ' + rpt.HIVE_FINISHED
        for lines in ([READY], [hive], [hive, READY[9:]],
                      [rpt.HIVE_FINISHED, READY], [hive, READY, hive]):
            with self.subTest(lines=lines):
                self.assertEqual(self.timing(lines)['status'], 'unavailable')

    def test_pending_and_disabled_modules(self):
        lines = ['12:00:00 ' + rpt.HIVE_FINISHED,
            '12:00:01 [HC Ready] module=Pending enabled=true ready=false',
            '12:00:01 [HC Ready] module=Off enabled=false ready=false']
        self.assertEqual(self.timing(lines)['pending'], ['Pending'])
        lines.append('12:00:02 [HC Ready] module=Pending enabled=true ready=true')
        self.assertEqual(self.timing(lines)['status'], 'passed')
