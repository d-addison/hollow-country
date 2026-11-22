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
                               settle_minutes=3 / 60, ready_deadline_minutes=10 / 60, poll_seconds=1)

    def watch(self, args, on_sleep=None, through_main=False):
        now = [0]
        def sleep(seconds):
            now[0] += seconds
            if on_sleep:
                on_sleep()
        with patch.object(boot.time, 'monotonic', side_effect=lambda: now[0]), \
                patch.object(boot.time, 'sleep', side_effect=sleep), \
                patch.object(boot.winproc, 'process_state', return_value='running') as process:
            if through_main:
                result = SimpleNamespace(returncode=0, attempts=1, stdout='', stderr='')
                with patch.object(boot.winproc, 'run', return_value=result):
                    outcome = boot.main([
                        '--bundle', 'fake', '--profiles', str(args.profiles), '--rpt', str(args.rpt),
                        '--settle-minutes', str(args.settle_minutes),
                        '--ready-deadline-minutes', str(args.ready_deadline_minutes),
                        '--timeout-seconds', str(args.timeout_seconds),
                        '--stall-seconds', str(args.stall_seconds), '--poll-seconds', str(args.poll_seconds)])
            else:
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

    def test_main_dump_with_runtime_error_keeps_crash_verdict(self):
        args = self.setup_watch(MISSION + ERROR + CONNECT + READY)
        result = SimpleNamespace(returncode=0, attempts=1, stdout='', stderr='')
        # The first snapshot precedes observation; the next sees a new dump.
        dump = args.profiles / 'server.mdmp'
        with patch.object(boot.winproc, 'run', return_value=result), \
                patch.object(boot, 'dumps', side_effect=[{}, {dump: (1, 1)}]), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            code = boot.main(['--bundle', 'fake', '--profiles', str(args.profiles), '--rpt', str(args.rpt)])
        self.assertEqual(code, boot.CODES['crashed'])
        self.assertIn('boot_verdict=crashed', output.getvalue())

    def test_main_runtime_error_preserves_observer_failures(self):
        args = self.setup_watch(MISSION + ERROR + CONNECT + READY)
        result = SimpleNamespace(returncode=0, attempts=1, stdout='', stderr='')
        for outcome in ('stalled', 'process_gone', 'interop_unknown', 'timed_out'):
            with self.subTest(outcome=outcome), \
                    patch.object(boot.winproc, 'run', return_value=result), \
                    patch.object(boot, 'watch', return_value=(outcome, args.rpt)), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                code = boot.main(['--bundle', 'fake', '--profiles', str(args.profiles), '--rpt', str(args.rpt)])
            self.assertEqual(code, boot.CODES[outcome])
            self.assertIn('boot_verdict=' + outcome, output.getvalue())

    def readiness_boot(self, updates):
        """Stream authored readiness fixtures at selected fake poll times."""
        modules = ('AIRoles', 'optional-expansion-human-ai')
        def line(module, ready, reason):
            return f'[HC Ready] module={module} enabled=true ready={str(ready).lower()} reason={reason} runtime=PENDING\n'
        args = self.setup_watch(MISSION + CONNECT + ''.join(
            line(module, False, 'source_pages') for module in modules))
        ticks = [0]
        def append():
            ticks[0] += 1
            with args.rpt.open('a') as stream:
                stream.write('[HC Progress] source pages advancing\n')
                for module, ready, reason in updates.get(ticks[0], ()):
                    stream.write(line(module, ready, reason))
        return args, modules, append

    def test_late_readiness_converges_to_exit_zero(self):
        args, modules, append = self.readiness_boot({
            5: [('AIRoles', True, 'ok')],
            7: [('optional-expansion-human-ai', True, 'ok')]})
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code, elapsed, _ = self.watch(args, append, through_main=True)
        self.assertEqual(code, 0)
        self.assertEqual(elapsed, 7)
        lines = output.getvalue().splitlines()
        pending = [line for line in lines if line.startswith('checkstart settle window passed;')]
        self.assertEqual(len(pending), 1)
        for module in modules:
            self.assertIn(module, pending[0])
        self.assertIn('checkstart readiness converged after 7s (pending at settle: '
                      + ', '.join(modules) + ')', lines)

    def test_readiness_deadline_returns_seven_and_last_reasons(self):
        args, modules, append = self.readiness_boot({
            5: [('AIRoles', False, 'last_source_page')]})
        # Equal overall and readiness deadlines must still return not_ready.
        args.timeout_seconds = args.ready_deadline_minutes * 60
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code, elapsed, _ = self.watch(args, append, through_main=True)
        self.assertEqual(code, 7)
        self.assertEqual(elapsed, args.ready_deadline_minutes * 60)
        deadline = [line for line in output.getvalue().splitlines()
                    if line.startswith('checkstart readiness deadline exceeded:')]
        self.assertEqual(len(deadline), 1)
        self.assertIn(modules[0] + ' reason=last_source_page', deadline[0])
        self.assertIn(modules[1] + ' reason=source_pages', deadline[0])
        self.assertNotIn('runtime=', deadline[0])
        self.assertNotIn('readiness converged', output.getvalue())

    def test_ready_flips_back_to_false_and_keeps_waiting(self):
        args, _, append = self.readiness_boot({
            1: [('AIRoles', True, 'ok')],
            2: [('AIRoles', False, 'rechecking')],
            4: [('optional-expansion-human-ai', True, 'ok')],
            8: [('AIRoles', True, 'ok')]})
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code, elapsed, _ = self.watch(args, append, through_main=True)
        self.assertEqual(code, 0)
        self.assertEqual(elapsed, 8)
        self.assertIn('checkstart readiness converged after 8s', output.getvalue())

    def test_disabled_readiness_does_not_block_settle(self):
        args = self.setup_watch(MISSION + CONNECT
                               + '[HC Ready] module=Disabled enabled=false ready=false reason=off\n')
        outcome, elapsed, _ = self.watch(args)
        self.assertEqual(outcome, 'connect_enabled')
        self.assertEqual(elapsed, args.settle_minutes * 60)

    def test_ready_deadline_validation_precedes_install_check(self):
        args = self.setup_watch('')
        invalid = [('--ready-deadline-minutes', value) for value in ('nan', 'inf', '-1')]
        invalid += [('--ready-deadline-minutes', '1', '--settle-minutes', '2'),
                    ('--ready-deadline-minutes', '2', '--timeout-seconds', '119')]
        for options in invalid:
            with self.subTest(options=options), \
                    patch.object(boot.winproc, 'run') as install, \
                    contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit) as error:
                boot.main(['--bundle', 'fake', '--profiles', str(args.profiles), *options])
            self.assertEqual(error.exception.code, 2)
            install.assert_not_called()

    def test_pending_readiness_deadline_precedes_total_timeout(self):
        args, _, append = self.readiness_boot({})
        with contextlib.redirect_stdout(io.StringIO()):
            outcome, elapsed, _ = self.watch(args, append)
        self.assertEqual(outcome, 'not_ready')
        self.assertEqual(elapsed, args.ready_deadline_minutes * 60)
        self.assertLess(elapsed, args.timeout_seconds)

    def test_pending_readiness_does_not_extend_stall_limit(self):
        args, _, _ = self.readiness_boot({})
        args.stall_seconds = args.ready_deadline_minutes * 60 / 2
        with contextlib.redirect_stdout(io.StringIO()):
            outcome, elapsed, _ = self.watch(args)
        self.assertEqual(outcome, 'stalled')
        self.assertEqual(elapsed, args.stall_seconds)
