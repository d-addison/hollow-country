"""Boot watcher phase and settle behavior with fake time/process observations."""
import contextlib
import io
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools.release import checkstart as boot
from tests.unit.test_rpt_summary import MISSION, ERROR, READY, CONNECT


class CheckstartTests(unittest.TestCase):
    def setup_watch(self, text):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        path = root / 'server.RPT'
        path.write_text(text)
        return SimpleNamespace(rpt=path, profiles=root, start=False, image='fake',
                               interop={}, timeout_seconds=30, stall_seconds=20,
                               settle_minutes=3 / 60, poll_seconds=1)

    def watch(self, args, on_sleep=None):
        now = [0]
        def sleep(seconds):
            now[0] += seconds
            if on_sleep:
                on_sleep()
        with patch.object(boot.time, 'monotonic', side_effect=lambda: now[0]), \
                patch.object(boot.time, 'sleep', side_effect=sleep), \
                patch.object(boot.winproc, 'process_state', return_value='running') as process:
            outcome, _ = boot.watch(args, set(), {})
        return outcome, now[0], process

    def test_runtime_error_keeps_settling_and_collects_late_readiness(self):
        args = self.setup_watch(MISSION + ERROR + CONNECT + READY.replace("ready=true", "ready=false"))
        def append_ready():
            with args.rpt.open('a') as stream:
                stream.write(READY)
        outcome, elapsed, process = self.watch(args, append_ready)
        self.assertEqual(outcome, 'script_error')
        self.assertGreaterEqual(elapsed, args.settle_minutes * 60)
        process.assert_called()
        summary = boot.Summary(args.rpt)
        try:
            summary.scan()
            self.assertTrue(summary.ready_last['Events'])
            self.assertEqual(summary.outcome, outcome)
        finally:
            summary.close()

    def test_script_error_before_mission_stops_early(self):
        args = self.setup_watch(ERROR + MISSION + CONNECT)
        outcome, elapsed, process = self.watch(args)
        self.assertEqual(outcome, 'compile_failed')
        self.assertEqual(elapsed, 0)
        process.assert_not_called()

    def test_mission_phase_survives_tail_chunks(self):
        args = self.setup_watch(MISSION + CONNECT)
        def append_error():
            with args.rpt.open('a') as stream:
                stream.write(ERROR)
        self.assertEqual(self.watch(args, append_error)[0], 'script_error')

    def test_clean_boot_passes_after_settle(self):
        args = self.setup_watch(MISSION + CONNECT + READY)
        outcome, elapsed, _ = self.watch(args)
        self.assertEqual(outcome, 'connect_enabled')
        self.assertGreaterEqual(elapsed, args.settle_minutes * 60)

    def test_main_runtime_failure_uses_distinct_code(self):
        args = self.setup_watch(MISSION + ERROR + CONNECT + READY)
        result = SimpleNamespace(returncode=0, attempts=1, stdout='', stderr='')
        with patch.object(boot.winproc, 'run', return_value=result), \
                patch.object(boot, 'watch', return_value=('connect_enabled', args.rpt)), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            code = boot.main(['--bundle', 'fake', '--profiles', str(args.profiles), '--rpt', str(args.rpt)])
        self.assertEqual(code, boot.CODES['script_error'])
        self.assertNotEqual(code, 0)
        self.assertNotIn(code, [value for key, value in boot.CODES.items() if key != 'script_error'])
        self.assertIn('boot_verdict=script_error', output.getvalue())
