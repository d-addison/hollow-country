"""Calibration orchestration with fake drivers only; never launches native tools."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.release import wb_calibrate as calib


def receipt(status, first=None):
    return {'status': status, 'first_error': first}


class CorpusTests(unittest.TestCase):
    def test_every_parent_is_checked_before_returning_resolved_data(self):
        calls = []

        def fake_git(*args):
            calls.append(args)
            return 'resolved-' + args[-1]

        with patch.object(calib, 'git', side_effect=fake_git):
            rows = calib.validate_corpus()
        self.assertEqual([row['fix'] for row in rows], [sha for sha, _ in calib.CORPUS])
        for row, (sha, reason) in zip(rows, calib.CORPUS):
            self.assertEqual(row['reason'], reason)
            self.assertTrue(reason)
            self.assertIn(('rev-parse', '--verify', sha + '^{commit}'), calls)
            self.assertIn(('merge-base', '--is-ancestor', row['parent_commit'], 'main'), calls)

    def test_missing_revision_or_nonancestor_refuses(self):
        failed = SimpleNamespace(returncode=1, stdout='', stderr='private')
        with patch.object(calib.subprocess, 'run', return_value=failed):
            with self.assertRaises(calib.Refusal):
                calib.validate_corpus()


class VerdictTests(unittest.TestCase):
    def invoke(self, tool, stdout, code, stderr=''):
        with patch.object(calib.subprocess, 'run', return_value=SimpleNamespace(
                stdout=stdout, stderr=stderr, returncode=code)) as run:
            result = calib.invoke(tool, calib.CORPUS[0][0] + '^')
        command = run.call_args.args[0]
        self.assertIn('tools.release.' + tool, command)
        self.assertEqual(command[-2:], ['--commit', calib.CORPUS[0][0] + '^'])
        self.assertTrue(run.call_args.kwargs['capture_output'])
        return result

    def test_workbench_verdict_and_location_without_private_text(self):
        data = {'status': 'compile_failed', 'workbench_build': 'a' * 16,
                'errors': [{'file': None, 'line': None},
                           {'file': '/'.join(('C:', 'Users', 'PrivateUser', 'HollowCountry/scripts/3_Game/bad.c')),
                            'line': 7, 'message': 'playerName=secret 12345678901234567'}]}
        result = self.invoke('wb_compile', json.dumps(data), 1)
        self.assertEqual(result['first_error'], {'file': 'HollowCountry/scripts/3_Game/bad.c', 'line': 7})
        self.assertEqual(result['workbench_build'], data['workbench_build'])
        self.assertNotIn('PrivateUser', json.dumps(result))
        self.assertNotIn('secret', json.dumps(result))
        self.assertNotIn('12345678901234567', json.dumps(result))

    def test_output_tail_redacts_json_escaped_windows_folder_and_identity_fields(self):
        folder = 'C:' + chr(92) + 'Users' + chr(92) + 'PrivateAccount' + chr(92) + 'source.c'
        tail = calib.output_tail(json.dumps({'file': folder, 'message': 'playerName=privateidentity'}))
        self.assertNotIn('PrivateAccount', tail)
        self.assertNotIn('privateidentity', tail)
        self.assertNotIn('12345678901234567', calib.output_tail('account id=12345678901234567'))

    def test_invalid_or_inconsistent_workbench_report_is_not_a_verdict(self):
        for stdout, code in [('not json', 1), ('[]', 0),
                             ('{"status":"passed"}', 1), ('{"status":"unknown"}', 0)]:
            with self.subTest(stdout=stdout):
                self.assertEqual(self.invoke('wb_compile', stdout, code)['status'], 'invalid_report')

    def test_native_compile_error_is_distinct_from_generic_failure(self):
        error = ('compile_gate: script_error: SCRIPT (E): @"HollowCountry/scripts/4_World/bad.c,8": unknown type\n'
                 'compile_gate: Can\'t compile World script module!\n'
                 'compile_gate: FAIL status=compiler-error')
        result = self.invoke('compile_gate', error, 1)
        self.assertEqual(result['status'], 'compile_failed')
        self.assertEqual(result['first_error'], {'file': 'HollowCountry/scripts/4_World/bad.c', 'line': 8})
        for text in ('compile_gate: FAIL status=timeout', 'compile_gate: FAIL prerequisite missing',
                     'compile_gate: PREPARED ONLY; native compile NOT RUN', 'compile_gate: PASS status=timeout',
                     'compile_gate: script_error: SCRIPT (E): NULL pointer to instance\n'
                     'compile_gate: FAIL status=compiler-error'):
            self.assertEqual(self.invoke('compile_gate', text, 1)['status'], 'unverified')
        passed = ('compile_gate: Mission loaded with zero compile errors; runtime acceptance pending\n'
                  'compile_gate: PASS status=timeout')
        self.assertEqual(self.invoke('compile_gate', passed, 0)['status'], 'passed')

    def test_native_gate_source_error_without_compile_banner(self):
        text = ('compile_gate: script_error: SCRIPT (E): @"HollowCountry/scripts/3_Game/bad.c,9": Unknown type\n'
                'compile_gate: Mission load not observed; compile completion unproven\n'
                'compile_gate: FAIL status=compiler-error')
        self.assertEqual(self.invoke('compile_gate', text, 1)['status'], 'compile_failed')
        for status in ('timeout', 'engine-crash', 'exited-1', 'log-collection-incomplete', 'input-drift'):
            result = self.invoke('compile_gate', 'compile_gate: FAIL status=' + status, 1)
            self.assertEqual(result['status'], 'unverified')
            self.assertEqual(result['reason'], 'gate_fail_' + status)

    def test_unknown_prelaunch_state_retries_but_running_does_not(self):
        def completed(status, reason=None):
            return SimpleNamespace(stdout=json.dumps({'status': status, 'reason': reason}), stderr='',
                                   returncode=0 if status == 'passed' else 2)
        unknown = completed('blocked', 'Workbench process state: unknown')
        with patch.object(calib.subprocess, 'run', side_effect=[unknown, unknown, completed('passed')]) as run, \
                patch.object(calib.time, 'sleep'):
            result = calib.invoke('wb_compile', 'fixture')
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['state_query_retries'], run.call_count - 1)
        with patch.object(calib.subprocess, 'run', return_value=unknown) as run, patch.object(calib.time, 'sleep'):
            result = calib.invoke('wb_compile', 'fixture')
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['state_query_retries'], run.call_count - 1)
        self.assertLessEqual(run.call_count, 3)
        with patch.object(calib.subprocess, 'run', return_value=completed('blocked', 'Workbench process state: running')) as run:
            calib.invoke('wb_compile', 'fixture')
        run.assert_called_once()

    def test_agreement_requires_real_native_evidence(self):
        row = {'wb_parent': receipt('compile_failed'), 'wb_fix': receipt('passed')}
        self.assertEqual(calib.agreement(row, False), 'expected_only')
        self.assertEqual(calib.agreement(row, True), 'incomplete')
        for status, expected in [('passed', 'disagree'), ('compile_failed', 'agree'),
                                 ('unverified', 'inconclusive')]:
            row['native_parent'] = receipt(status)
            self.assertEqual(calib.agreement(row, True), expected)
        row['native_parent'] = receipt('compile_failed')
        row['wb_fix'] = receipt('compile_failed')
        self.assertEqual(calib.agreement(row, True), 'inconclusive')

    def test_chained_fix_agrees_when_parent_error_is_gone(self):
        first = {'file': 'HollowCountry/scripts/3_Game/a.c', 'line': 47}
        later = {'file': 'HollowCountry/scripts/3_Game/b.c', 'line': 8}
        row = {'wb_parent': receipt('compile_failed', first), 'wb_fix': receipt('compile_failed', later),
               'native_parent': receipt('compile_failed', dict(first, file=first['file'].upper()))}
        self.assertEqual(calib.agreement(row, True), 'agree')
        row['wb_fix'] = receipt('compile_failed', dict(first))
        self.assertEqual(calib.agreement(row, True), 'disagree')
        row['wb_fix'] = receipt('passed')
        row['native_parent'] = receipt('compile_failed', later)
        self.assertEqual(calib.agreement(row, True), 'disagree')


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'WorkbenchApp.exe').touch()
        self.rows = [{'fix': sha, 'reason': reason, 'fix_commit': sha + '-resolved',
                      'parent_commit': sha + '-parent'} for sha, reason in calib.CORPUS]
        self.enterContext(patch.object(calib.wb, 'WORKBENCH', self.root))
        self.validate = self.enterContext(patch.object(calib, 'validate_corpus', return_value=self.rows))
        self.stdout, self.stderr = io.StringIO(), io.StringIO()
        self.enterContext(contextlib.redirect_stdout(self.stdout))
        self.enterContext(contextlib.redirect_stderr(self.stderr))
        self.out = self.root / 'results'

    def read_report(self):
        return json.loads((self.out / 'agreement.json').read_text())

    def test_only_sequential_jobs_and_both_output_formats(self):
        sha = self.rows[-1]['fix']
        jobs = []

        def fake(tool, commit):
            jobs.append((tool, commit))
            # Each call sees the preceding invocation's persisted evidence.
            checkpoint = self.read_report()['entries'][0]
            self.assertEqual(len([key for key in checkpoint if key.startswith('wb_') or key == 'native_parent']),
                             len(jobs) - 1)
            return receipt('passed' if commit == sha else 'compile_failed')

        with patch.object(calib, 'invoke', side_effect=fake):
            code = calib.main(['--only', sha, '--gate', '--out', str(self.out)])
        self.assertEqual(code, 0)
        self.assertEqual(jobs, [('wb_compile', sha + '^'), ('wb_compile', sha), ('compile_gate', sha + '^')])
        report = self.read_report()
        self.assertEqual(report['status'], 'agree')
        self.assertEqual([entry['fix'] for entry in report['entries']], [sha])
        self.assertIn('| agree |', (self.out / 'agreement.md').read_text())
        self.validate.assert_called_once_with()

    def test_whole_corpus_no_gate_is_expected_only(self):
        with patch.object(calib, 'invoke', side_effect=lambda tool, commit:
                          receipt('compile_failed' if commit.endswith('^') else 'passed')) as invoke:
            self.assertEqual(calib.main(['--out', str(self.out)]), 0)
        self.assertEqual(invoke.call_count, len(calib.CORPUS) * 2)
        self.assertEqual(self.read_report()['status'], 'expected_only')
        self.assertNotIn('native_parent', self.read_report()['entries'][0])

    def test_disagreement_nonzero_and_continues(self):
        with patch.object(calib, 'invoke', return_value=receipt('passed')) as invoke:
            self.assertEqual(calib.main(['--out', str(self.out)]), 1)
        self.assertEqual(invoke.call_count, len(calib.CORPUS) * 2)
        self.assertEqual(self.read_report()['status'], 'disagree')

    def test_explicit_stop_on_inconclusive(self):
        for status in calib.WB_STATUSES - {'passed', 'compile_failed'}:
            with self.subTest(status=status), patch.object(calib, 'invoke', return_value=receipt(status)) as invoke:
                self.assertEqual(calib.main(['--gate', '--stop-on-inconclusive', '--out', str(self.out)]), 2)
                invoke.assert_called_once()
                self.assertEqual(self.read_report()['status'], 'incomplete')

    def test_inconclusive_continues_all_sides_and_rows(self):
        with patch.object(calib, 'invoke', return_value=receipt('unverified')) as invoke:
            self.assertEqual(calib.main(['--gate', '--out', str(self.out)]), 2)
        report = self.read_report()
        self.assertEqual(invoke.call_count, sum(3 for _ in report['entries']))
        self.assertEqual(report['summary']['inconclusive'], len(report['entries']))
        self.assertEqual(report['summary']['incomplete'], 0)
        for row in report['entries']:
            for side in ('wb_parent', 'wb_fix', 'native_parent'):
                self.assertTrue((self.out / row[side]['output_log']).is_file())

    def test_persists_redacted_bounded_tail_and_reference(self):
        secret = '/home/' + 'privateaccount'
        output = '\n'.join(['old'] * 250 + [secret + ' 12345678901234567'])
        with patch.object(calib.subprocess, 'run', return_value=SimpleNamespace(
                stdout=output, stderr='', returncode=1)):
            result = calib.invoke('compile_gate', 'fixture')
        self.assertLessEqual(len(result['output_tail'].splitlines()), 200)
        self.assertNotIn(secret, result['output_tail'])
        self.assertNotIn('12345678901234567', result['output_tail'])
        with patch.object(calib, 'invoke', return_value=result):
            calib.main(['--only', self.rows[0]['fix'], '--out', str(self.out)])
        row = self.read_report()['entries'][0]
        self.assertNotIn('output_tail', row['wb_parent'])
        saved = (self.out / row['wb_parent']['output_log']).read_text()
        self.assertNotIn(secret, saved)
        self.assertNotIn('12345678901234567', saved)
        self.assertTrue(saved.strip())

    def test_missing_install_unknown_selection_and_repo_output_refuse(self):
        with patch.object(calib, 'invoke') as invoke:
            self.assertEqual(calib.main(['--only', 'not-a-corpus-sha']), 2)
            self.assertEqual(calib.main(['--out', str(calib.REPO / 'forbidden-results')]), 2)
            (self.root / 'WorkbenchApp.exe').unlink()
            self.assertEqual(calib.main(['--out', str(self.out)]), 2)
            invoke.assert_not_called()
        self.assertIn('Workbench install missing', self.stderr.getvalue())
        self.assertFalse(self.out.exists())

    def test_invalid_corpus_refuses_even_a_selected_subset(self):
        sha = self.rows[0]['fix']
        self.validate.side_effect = calib.Refusal('corpus revision missing')
        with patch.object(calib, 'invoke') as invoke:
            self.assertEqual(calib.main(['--only', sha, '--out', str(self.out)]), 2)
            invoke.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_report_symlink_refuses_before_launch(self):
        self.out.mkdir()
        target = self.root / 'untouched'
        target.write_text('original')
        (self.out / 'agreement.json').symlink_to(target)
        with patch.object(calib, 'invoke') as invoke:
            self.assertEqual(calib.main(['--out', str(self.out)]), 2)
            invoke.assert_not_called()
        self.assertEqual(target.read_text(), 'original')

    def test_default_output_uses_job_temp(self):
        sha = self.rows[0]['fix']
        with patch.dict(calib.os.environ, {'TEMP': str(self.root)}), \
                patch.object(calib, 'invoke', side_effect=[receipt('compile_failed'), receipt('passed')]):
            self.assertEqual(calib.main(['--only', sha]), 0)
        outputs = list(self.root.glob('hc-wb-calibrate-*/agreement.json'))
        self.assertEqual(len(outputs), 1)
        self.assertEqual(json.loads(outputs[0].read_text())['status'], 'expected_only')

    def test_private_launch_exception_is_not_printed(self):
        with patch.object(calib, 'invoke', side_effect=OSError('/'.join(('C:', 'Users', 'PrivateUser')) + ' playerName=secret')):
            self.assertEqual(calib.main(['--out', str(self.out)]), 2)
        self.assertNotIn('PrivateUser', self.stderr.getvalue())
        self.assertNotIn('secret', self.stderr.getvalue())
        self.assertEqual(self.read_report()['status'], 'incomplete')
        self.assertEqual(self.read_report()['entries'][0]['wb_parent']['status'], 'tool_failed')


if __name__ == '__main__':
    unittest.main()
