"""Synthetic tooling checks only; no Enforce emulation or native acceptance."""
import json
from pathlib import Path
from contextlib import nullcontext
import tempfile
import unittest
from unittest import mock

from tools.setup import interior_resolve_probe as probe


class InteriorResolveProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rows, self.pins = probe.targets(per_class=1)
        self.plan = dict(schema=1, kind='interior-resolve-probe', run='a' * 32,
                         targets=self.rows, apis=['query3d_zero', 'ray_geom'])
        self.plan_path = self.root / 'plan.json'
        self.plan_path.write_text(json.dumps(self.plan))

    def lines(self, *, found=True, ticks=5000):
        lines = ['[HC ResolveProbe] begin run=' + self.plan['run']]
        for target in self.rows:
            for order in range(len(self.plan['apis'])):
                api = self.plan['apis'][(order + target['index']) % len(self.plan['apis'])]
                for pair in (0, 1):
                    lines.append('[HC ResolveProbe] run=%s target=%d class=%s api=%s order=%d pair=%d ticks=%d found=%s capped=false'
                                 % (self.plan['run'], target['index'], target['class'], api,
                                    order, pair, ticks, str(found).lower()))
        lines.append('[HC ResolveProbe] summary run=%s measurements=%d' % (self.plan['run'], len(lines) - 1))
        return lines

    def ingest(self, lines, **kwargs):
        rpt = self.root / 'probe.RPT'
        rpt.write_text('\n'.join(lines))
        return probe.ingest(rpt, self.plan_path, self.root / 'result.json', **kwargs)

    def test_catalog_sampling_is_distinct_and_from_furnishing_data(self):
        rows, pins = probe.targets()
        source = {}
        for name in pins:
            if name.startswith('furnish-'):
                for row in json.loads((probe.CATALOG / name).read_text())['Rows']:
                    source[row['BuildingClass'], tuple(row['Position'])] = row
        for name in probe.CLASSES:
            selected = [r for r in rows if r['class'] == name]
            self.assertEqual(len(selected), len({tuple(r['pos']) for r in selected}))
            self.assertTrue(selected)
            for row in selected:
                self.assertIn((name, tuple(row['pos'])), source)
                self.assertEqual(len(row['ray_pos']), len(row['pos']))
        with self.assertRaises(ValueError):
            probe.targets(per_class=0)

    def test_ingest_preserves_units_pairs_and_first_touch(self):
        result = self.ingest(self.lines(), ticks_per_ms=5000)
        self.assertEqual(len(result['table']), len(self.rows) * len(self.plan['apis']))
        for row in result['table']:
            self.assertEqual(row['first_ms'], [1])
            self.assertEqual(row['repeat_ms'], [1])
            self.assertTrue(row['found'])
        self.assertEqual(sum(len(r['first_touch_ms']) for r in result['table']), len(self.rows))
        self.assertIn('Candidate', result['recommendation'])
        self.assertEqual(result['evidence'], 'diag-only-unverified')

    def test_misses_and_over_budget_never_recommend_candidate(self):
        result = self.ingest(self.lines(found=False, ticks=250001))
        self.assertTrue(all(not r['found'] for r in result['table']))
        self.assertIn('No API', result['recommendation'])

    def test_incomplete_duplicate_mixed_and_wrong_order_are_refused(self):
        baseline = self.lines()
        variants = [baseline[:-1], baseline[:2] + baseline[1:],
                    [line.replace('run=' + self.plan['run'], 'run=' + 'b' * 32) for line in baseline],
                    baseline[:1] + [baseline[2], baseline[1]] + baseline[3:],
                    baseline[:2] + baseline[3:]]
        for lines in variants:
            with self.subTest(lines=lines[:2]), self.assertRaises(ValueError):
                self.ingest(lines)
        self.assertFalse((self.root / 'result.json').exists())

    def test_cap_or_failed_repeat_disqualifies_api(self):
        lines = self.lines()
        lines = [line.replace('capped=false', 'capped=true') if ' pair=1 ' in line else line
                 for line in lines]
        result = self.ingest(lines)
        self.assertTrue(all(row['capped'] for row in result['table']))
        self.assertIn('No API', result['recommendation'])

    def test_ingest_refuses_overwrite(self):
        self.ingest(self.lines())
        with self.assertRaises(FileExistsError):
            self.ingest(self.lines())

    def test_dry_run_never_stages_or_launches(self):
        from tools.setup import diag_session
        with mock.patch.object(diag_session, 'stage') as stage:
            result = probe.stage('test', per_class=1, dry_run=True)
        stage.assert_not_called()
        self.assertEqual(result['status'], 'validated-not-staged')
        self.assertEqual(set(result['apis']), set(probe.CALLS))

    def test_stage_instruments_fresh_mission_and_prelaunch_detects_tampering(self):
        from tools.setup import diag_session as ds
        from types import SimpleNamespace
        runtime = self.root / 'runtime'
        init = runtime / 'mpmissions' / ds.MISSION / 'init.c'
        original = (b'class CustomMission : MissionServer {}\n'
                    b'Mission CreateCustomMission(string path) { return new CustomMission(); }\n')

        def fake_stage(plan):
            init.parent.mkdir(parents=True)
            init.write_bytes(original)

        fake_plan = SimpleNamespace(runtime=runtime)
        with mock.patch.object(probe, 'diag_plan', return_value=fake_plan), \
                mock.patch.object(ds, 'stage', side_effect=fake_stage), \
                mock.patch('tools.release.host_lock.host_lock', return_value=nullcontext()), \
                mock.patch.object(ds, 'guard_idle'):
            result = probe.stage('test', per_class=1)
            self.assertEqual(result['stock_init_sha256'], probe.rt.sha256(original))
            self.assertEqual(result['staged_init_sha256'], probe.rt.sha256(init.read_bytes()))
            self.assertIs(probe.staged_plan('test'), fake_plan)
            init.write_bytes(original)
            with self.assertRaises(ValueError):
                probe.staged_plan('test')

    def test_payload_passes_existing_generated_hook_lint(self):
        hook = probe.render_hook(self.rows, probe.APIS, self.plan['run']).decode()
        self.assertEqual(probe.rt.lint_hook(hook), [])


if __name__ == '__main__':
    unittest.main()
