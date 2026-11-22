"""Owner R4 policy validation; synthetic configuration only."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.release.acceptance_targets import load_targets, TargetsError


class AcceptanceTargetsTests(unittest.TestCase):
    def test_readiness_allowance_requires_finite_positive_number(self):
        targets = load_targets()
        key = 'readiness_max_after_hive_seconds'
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'targets.json'
            for value in (0, -1, True, '30', float('nan'), float('inf'), None):
                path.write_text(json.dumps(dict(targets, **{key: value})))
                with self.subTest(value=value), self.assertRaises(TargetsError):
                    load_targets(path)
            for value in (1, 2.5):
                path.write_text(json.dumps(dict(targets, **{key: value})))
                self.assertEqual(load_targets(path)[key], value)
            del targets[key]
            path.write_text(json.dumps(targets))
            with self.assertRaises(TargetsError):
                load_targets(path)
