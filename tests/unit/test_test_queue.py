"""Queue orchestration tests: every subprocess, git call and the host lock are faked."""
from contextlib import contextmanager
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.release import test_queue as queue
from tools.release.host_lock import LockRefused

SHA = 'a' * 40
BASE = 'b' * 40


def done(code=0, out=''):
    return subprocess.CompletedProcess([], code, out, '')


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='hc-queue-test-'))
        self.addCleanup(lambda: __import__('shutil').rmtree(self.tmp, ignore_errors=True))
        self.git_calls = []
        self.commands = []
        self.locks = []
        self.state = 'gone'
        self.codes = {}
        self.dirty = ''
        self.lock_refused = None
        self.removal_code = 0
        self.worktree_head = SHA
        self.worktree_dirty = ''
        self.worktree_exists = False

        @contextmanager
        def fake_lock(holder, path=None):
            if self.lock_refused:
                raise LockRefused('native host busy: holder=' + self.lock_refused)
            self.locks.append(holder)
            yield

        def fake_git(*arguments, cwd=None):
            self.git_calls.append((arguments, cwd))
            if arguments[0] == 'rev-parse' and arguments[-1].endswith('^{commit}'):
                name = arguments[-1][:-len('^{commit}')]
                return done(0, (SHA if name == SHA else BASE if name == 'origin/dev' else '') + '\n')
            if arguments[0] == 'rev-parse' and arguments[1] == 'HEAD':
                return done(0, self.worktree_head + '\n')
            if arguments[0] == 'status':
                in_worktree = cwd is not None
                return done(0, self.worktree_dirty if in_worktree else self.dirty)
            if arguments[:2] == ('worktree', 'remove'):
                return done(self.removal_code)
            return done(0)

        def fake_run(argv, cwd, log_path, timeout):
            self.commands.append((argv, cwd))
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text('fake log\n')
            return self.codes.get(argv[7], 0)

        for name, replacement in (('host_lock', fake_lock), ('git', fake_git), ('run_command', fake_run),
                                  ('client_state', lambda: self.state), ('wb_calibrated', lambda: False),
                                  ('worktree_root', lambda: self.tmp / 'worktrees')):
            patcher = patch.object(queue, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.store = queue.Store(self.tmp / 'queue')

    def cli(self, *argv):
        out = io.StringIO()
        with patch.object(queue, 'queue_dir', return_value=self.tmp / 'queue'), contextlib.redirect_stdout(out):
            code = queue.main(list(argv))
        return code, out.getvalue()

    def submit(self, checks='preland,wb,gate'):
        code, out = self.cli('submit', '--commit', SHA, '--checks', checks)
        self.assertEqual(0, code, out)
        return self.store.all()[-1]

    def test_submit_pins_a_full_sha_and_resolves_the_base(self):
        self.assertEqual(2, self.cli('submit', '--commit', SHA[:8])[0])
        job = self.submit()
        self.assertEqual(SHA, job['sha'])
        self.assertEqual(BASE, job['base_sha'])
        self.assertEqual(['preland', 'wb', 'gate'], job['checks'])
        self.assertEqual('queued', job['status'])

    def test_run_uses_a_detached_worktree_at_the_pinned_sha_and_removes_it_without_force(self):
        self.submit()
        code, out = self.cli('run-next')
        self.assertEqual(0, code, out)
        add = [a for a, _ in self.git_calls if a[:2] == ('worktree', 'add')]
        self.assertEqual([('worktree', 'add', '--detach', str(self.tmp / 'worktrees' / ('queue-' + SHA[:8])), SHA)], add)
        remove = [a for a, _ in self.git_calls if a[:2] == ('worktree', 'remove')]
        self.assertEqual(1, len(remove))
        self.assertNotIn('--force', remove[0])
        self.assertNotIn('-f', remove[0])
        wb = [argv for argv, _ in self.commands if 'tools.release.wb_compile' in argv][0]
        self.assertEqual(SHA, wb[wb.index('--commit') + 1])
        preland = [argv for argv, _ in self.commands if 'tools.validate.preland' in argv][0]
        self.assertEqual(BASE, preland[preland.index('--changed') + 1])
        self.assertEqual('passed', self.store.all()[0]['status'])

    def test_every_native_check_runs_under_the_shared_host_lock_with_its_memory_cap(self):
        self.submit()
        self.cli('run-next')
        self.assertEqual(['test_queue'], self.locks)
        caps = {argv[7]: argv[2] for argv, _ in self.commands}
        self.assertEqual({'tools.validate.preland': '3G', 'tools.release.wb_compile': '3G',
                          'tools.release.compile_gate': '12G'}, caps)
        self.assertTrue(all(argv[0] == 'agent-run' for argv, _ in self.commands))

    def test_lock_module_is_the_shared_host_lock_not_a_second_lock(self):
        source = Path(queue.__file__).read_text()
        self.assertIn('from tools.release.host_lock import', source)
        self.assertNotIn('flock', source)

    def test_running_dayz_client_holds_the_job_and_runs_nothing(self):
        self.submit()
        self.state = 'running'
        code, out = self.cli('run-next')
        self.assertEqual(0, code)
        job = self.store.all()[0]
        self.assertEqual('held', job['status'])
        self.assertIn('owner client', job['held_reason'])
        self.assertEqual([], self.commands)
        self.assertEqual([], [a for a, _ in self.git_calls if a[:2] == ('worktree', 'add')])
        self.state = 'gone'
        self.assertEqual(0, self.cli('run-next')[0])
        self.assertEqual('passed', self.store.all()[0]['status'])

    def test_unknown_client_state_also_holds(self):
        self.submit()
        self.state = 'unknown'
        self.cli('run-next')
        self.assertEqual('held', self.store.all()[0]['status'])

    def test_client_started_between_checks_holds_and_resumes_only_the_rest(self):
        self.submit()
        states = iter(['gone', 'running', 'gone', 'gone'])
        with patch.object(queue, 'client_state', lambda: next(states)):
            self.cli('run-next')
            self.assertEqual('held', self.store.all()[0]['status'])
            self.cli('run-next')
        job = self.store.all()[0]
        self.assertEqual('passed', job['status'])
        self.assertEqual(['tools.validate.preland', 'tools.release.wb_compile', 'tools.release.compile_gate'],
                         [argv[7] for argv, _ in self.commands])

    def test_friendcycle_holding_the_host_lock_holds_the_job(self):
        self.submit()
        self.lock_refused = 'friendcycle'
        self.assertEqual(0, self.cli('run-next')[0])
        job = self.store.all()[0]
        self.assertEqual('held', job['status'])
        self.assertIn('friendcycle', job['held_reason'])
        self.assertEqual([], self.commands)

    def test_exit_137_is_recorded_as_oom_and_never_retried(self):
        self.submit('gate')
        self.codes['tools.release.compile_gate'] = 137
        code, _ = self.cli('run-next')
        self.assertEqual(1, code)
        job = self.store.all()[0]
        self.assertEqual('oom', job['status'])
        result = job['results'][-1]
        self.assertEqual(('gate', 137, 'oom'), (result['check'], result['rc'], result['status']))
        self.assertEqual(1, len(self.commands))
        self.cli('run-next')
        self.assertEqual(1, len(self.commands))

    def test_failed_check_stops_the_job_and_advisory_wb_failure_does_not(self):
        self.submit()
        self.codes['tools.release.wb_compile'] = 1
        self.assertEqual(0, self.cli('run-next')[0])
        job = self.store.all()[0]
        self.assertEqual('passed', job['status'])
        wb = [r for r in job['results'] if r['check'] == 'wb'][0]
        self.assertEqual(('fail', True), (wb['status'], wb['advisory']))
        self.assertIn('not calibrated', wb['note'])
        self.assertEqual({'sha', 'check', 'rc', 'status', 'log', 'started', 'finished', 'advisory', 'note'}, set(wb))

    def test_preland_failure_skips_later_checks(self):
        self.submit()
        self.codes['tools.validate.preland'] = 1
        self.assertEqual(1, self.cli('run-next')[0])
        self.assertEqual('failed', self.store.all()[0]['status'])
        self.assertEqual(1, len(self.commands))

    def test_dirty_existing_worktree_is_refused_not_reused_or_forced(self):
        self.submit()
        path = self.tmp / 'worktrees' / ('queue-' + SHA[:8])
        path.mkdir(parents=True)
        self.worktree_dirty = ' M tools/x.py\n'
        self.assertEqual(1, self.cli('run-next')[0])
        job = self.store.all()[0]
        self.assertEqual('failed', job['status'])
        self.assertIn('dirty', job['results'][-1]['note'])
        self.assertEqual([], self.commands)
        self.assertEqual([], [a for a, _ in self.git_calls if a[:2] == ('worktree', 'remove')])

    def test_dirty_submitting_checkout_is_refused(self):
        self.dirty = ' M tools/x.py\n'
        code, out = self.cli('submit', '--commit', SHA)
        self.assertEqual(2, code)
        self.assertIn('uncommitted', out)
        self.assertEqual([], self.store.all())

    def test_worktree_that_will_not_remove_is_kept_and_recorded(self):
        self.submit('preland')
        self.removal_code = 1
        self.cli('run-next')
        self.assertIn('kept', self.store.all()[0]['worktree_kept'])

    def test_calibrated_wb_makes_the_gate_a_wave_or_release_check(self):
        with patch.object(queue, 'wb_calibrated', lambda: True):
            code, out = self.cli('submit', '--commit', SHA, '--checks', 'preland,gate')
            self.assertEqual(['preland'], self.store.all()[0]['checks'])
            self.assertIn('Wine gate dropped', out)
            self.cli('submit', '--commit', SHA, '--checks', 'preland,gate', '--wave')
            self.assertEqual(['preland', 'gate'], self.store.all()[-1]['checks'])

    def test_status_and_list_report_jobs_and_results(self):
        self.submit('preland')
        self.cli('run-next')
        self.assertIn('passed=1', self.cli('status')[1])
        self.assertIn('advisory', self.cli('status')[1])
        listing = self.cli('list')[1]
        self.assertIn('preland rc=0 pass', listing)
        self.assertEqual(1, len(json.loads(self.cli('list', '--json')[1])))

    def test_submit_line_names_the_exact_command(self):
        self.assertEqual('python3 -B -m tools.release.test_queue submit --commit %s --checks preland,wb,gate' % SHA,
                         queue.submit_line(sha=SHA))
        self.assertIn('<full commit sha>', queue.submit_line(sha='short'))


if __name__ == '__main__':
    unittest.main()
