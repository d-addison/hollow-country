"""Child command diagnostics, without executing build or native commands."""
import contextlib
import io
import subprocess
import unittest
from unittest.mock import patch

from tools.release import release


class ReleaseRunTests(unittest.TestCase):
    def run_child(self, stdout='', stderr='', code=1):
        output = io.StringIO()
        result = subprocess.CompletedProcess(['python3'], code, stdout, stderr)
        with patch.object(release.subprocess, 'run', return_value=result), contextlib.redirect_stdout(output):
            if code:
                with self.assertRaisesRegex(ValueError, 'Build command failed: python3'):
                    release.run(['python3', 'build'])
            else:
                self.assertEqual(stdout, release.run(['python3', 'build']))
        return output.getvalue().splitlines()

    def test_authored_refusals_from_both_streams(self):
        lines = ['refused: unreviewed mission source: ce/hc-site-measurements.json',
                 'Refused unsafe input', 'FAIL validation', 'error: missing receipt']
        self.assertEqual(lines, self.run_child('noise\n' + '\n'.join(lines[:2]), '\n'.join(lines[2:])))

    def test_privacy_filter_runs_before_output_truncation(self):
        # Synthetic identities only; none are printed by this test.
        unix_home = '/' + 'home' + '/example/build'
        windows_home = 'C:' + chr(92) + 'Users' + chr(92) + 'example' + chr(92) + 'build'
        identity = '1' * 17
        private = f'{unix_home} {windows_home} {identity}'
        lines = self.run_child('refused: ' + private, 'error: player_name=example')
        self.assertTrue(lines)
        self.assertNotIn('example', '\n'.join(lines))
        self.assertNotIn(identity, '\n'.join(lines))
        self.assertNotIn('Users', '\n'.join(lines))

    def test_bounded_lines_and_success_remains_quiet(self):
        refusals = ['FAIL ' + 'x' * 500] * 25
        lines = self.run_child('\n'.join(refusals))
        self.assertEqual(20, len(lines))
        self.assertTrue(all(len(line) <= 300 for line in lines))
        self.assertEqual([], self.run_child('refused: example', code=0))
        self.assertEqual([], self.run_child('ordinary failure without authored prefix'))
