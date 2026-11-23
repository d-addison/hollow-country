import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.package import loot_slack

DOC = {'schema': 1, 'limit': 1.0, 'deficit': 0, 'buckets': {'0': {'slack': 4, 'nominal': 2, 'unassigned': 0, 'route': 'a'}},
       'classes': {'x': '0'}}


class LootSlackCheck(unittest.TestCase):
    def run_main(self, committed, fresh, *args):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'tools/package').mkdir(parents=True)
            if committed is not None:
                (root / loot_slack.TABLE).write_bytes(committed)
            calls = []
            def generate(source):
                calls.append(source)
                return fresh[min(len(calls), len(fresh)) - 1]
            out = io.StringIO()
            with mock.patch.object(loot_slack, 'ROOT', root), mock.patch.object(loot_slack, 'generate', generate), \
                    redirect_stdout(out):
                code = loot_slack.main(['--source', str(root), *args])
            return code, out.getvalue(), (root / loot_slack.TABLE).read_bytes() if (root / loot_slack.TABLE).exists() else None, calls

    def test_check_passes_on_a_fixpoint(self):
        data = loot_slack.encode(DOC)
        code, out, _, _ = self.run_main(data, [data], '--check')
        self.assertEqual(0, code)
        self.assertIn('PASS', out)

    def test_check_fails_on_a_stale_or_missing_table(self):
        data = loot_slack.encode(DOC)
        stale = loot_slack.encode(dict(DOC, deficit=100))
        for committed in (stale, None):
            code, out, written, _ = self.run_main(committed, [data], '--check')
            self.assertEqual(1, code)
            self.assertIn('FAIL', out)
            self.assertEqual(committed, written)

    def test_write_runs_until_the_table_settles(self):
        first, second = loot_slack.encode(dict(DOC, deficit=100)), loot_slack.encode(DOC)
        code, _, written, calls = self.run_main(None, [first, second, second], '--write')
        self.assertEqual(0, code)
        self.assertEqual(second, written)
        self.assertEqual(3, len(calls))

    def test_write_refuses_a_table_that_never_settles(self):
        runs = [loot_slack.encode(dict(DOC, deficit=n * 100)) for n in range(loot_slack.MAX_ROUNDS + 2)]
        code, out, _, _ = self.run_main(None, runs, '--write')
        self.assertEqual(1, code)
        self.assertIn('did not settle', out)

    def test_rounding_jitter_inside_the_tolerance_settles_and_a_real_move_does_not(self):
        base = loot_slack.encode(DOC)
        jitter = json.loads(base)
        jitter['buckets']['0']['slack'] += loot_slack.TOLERANCE
        moved = json.loads(base)
        moved['buckets']['0']['slack'] += loot_slack.TOLERANCE + 1
        rerouted = json.loads(base)
        rerouted['buckets']['0']['route'] = 'b'
        self.assertTrue(loot_slack.settled(base, loot_slack.encode(jitter)))
        self.assertFalse(loot_slack.settled(base, loot_slack.encode(moved)))
        self.assertFalse(loot_slack.settled(base, loot_slack.encode(rerouted)))
        self.assertFalse(loot_slack.settled(None, base))
        code, out, written, _ = self.run_main(base, [loot_slack.encode(jitter)], '--check')
        self.assertEqual(0, code)
        self.assertEqual(base, written)

    def test_reproduce_keeps_the_committed_bytes_inside_the_tolerance(self):
        base = loot_slack.encode(DOC)
        jitter = json.loads(base)
        jitter['buckets']['0']['slack'] += 1
        stale = loot_slack.encode(dict(DOC, deficit=100))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'tools/package').mkdir(parents=True)
            (root / loot_slack.TABLE).write_bytes(base)
            with mock.patch.object(loot_slack, 'ROOT', root):
                with mock.patch.object(loot_slack, 'generate', lambda source: loot_slack.encode(jitter)):
                    self.assertEqual(base, loot_slack.reproduce(root))
                with mock.patch.object(loot_slack, 'generate', lambda source: stale):
                    self.assertEqual(stale, loot_slack.reproduce(root))

    def test_exactly_one_input_is_required(self):
        with self.assertRaises(SystemExit):
            loot_slack.main([])


class LootSlackShipped(unittest.TestCase):
    def test_committed_table_loads_and_is_well_formed(self):
        table = loot_slack.load()
        doc = json.loads((loot_slack.ROOT / loot_slack.TABLE).read_bytes())
        self.assertEqual(loot_slack.encode(doc), (loot_slack.ROOT / loot_slack.TABLE).read_bytes())
        self.assertEqual(set(doc['buckets']), set(table['bucket']))
        self.assertTrue(set(table['class'].values()) <= set(table['bucket']))


if __name__ == '__main__':
    unittest.main()
