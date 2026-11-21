"""Baseline ratcheting tests; synthetic audit results establish no engine behavior."""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.validate import wiring_audit as wiring


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'config').mkdir()
        (self.root / 'config/wiring-audit.json').write_text(json.dumps({'schema': 1, 'baseline': 'baseline.json'}))
        self.path = self.root / 'baseline.json'
        self.live = {'id': 'W004', 'subject': 'Local', 'file': 'mods/Local.c', 'line': 1, 'why': 'local class'}
        self.kept = dict(self.live, reason='reviewed fixture')
        self.stale = dict(self.kept, subject='Removed')
        self.baseline = {'schema': 1, 'note': 'retain metadata', 'findings': [self.kept, self.stale]}
        self.path.write_text(json.dumps(self.baseline))

    def run_cli(self, *args, findings=None):
        output = io.StringIO()
        with patch.object(wiring, 'ROOT', self.root), patch.object(wiring.Audit, 'run', return_value=copy.deepcopy([self.live] if findings is None else findings)), redirect_stdout(output):
            result = wiring.main(['--json', *args])
        return result, json.loads(output.getvalue())

    def test_report_and_strict_do_not_mutate_baseline(self):
        before = self.path.read_bytes()
        result, report = self.run_cli()
        self.assertEqual(result, 0)
        self.assertEqual(report['stale_baseline'], [self.stale])
        self.assertEqual(report['stale_baseline_entries'], len(report['stale_baseline']))
        self.assertEqual(self.run_cli('--strict-baseline')[0], 1)
        self.assertEqual(self.path.read_bytes(), before)

    def test_ratchet_only_removes_stale_and_preserves_new_failure(self):
        new = dict(self.live, subject='New')
        result, report = self.run_cli('--ratchet', '--strict-baseline', findings=[self.live, new])
        self.assertEqual(result, 1)
        expected = dict(self.baseline, findings=[self.kept])
        self.assertEqual(json.loads(self.path.read_text()), expected)
        self.assertEqual(report['stale_baseline'], [])
        self.assertEqual([f['subject'] for f in report['findings'] if f['new']], [new['subject']])
        before = self.path.read_bytes()
        self.assertEqual(self.run_cli('--ratchet', '--strict-baseline')[0], 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_legacy_prune_alias_and_empty_live_set(self):
        self.assertEqual(self.run_cli('--update-baseline', '--strict-baseline', findings=[])[0], 0)
        self.assertEqual(json.loads(self.path.read_text())['findings'], [])


if __name__ == '__main__':
    unittest.main()
