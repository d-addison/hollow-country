"""Offline tooling checks only; synthetic logs do not establish DayZ behaviour."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.setup import ce_overlay_probe as probe


class OverlayProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = [dict(id='sample:tent-p01', **{'class': 'Land_Medical_Tent_Big'},
                          x=12345.6789, z=4567.8912, authored_y=80, yaw=-90, loot='proto')]
        self.plan = dict(kind='ce-probe', probe_kind='ce-overlay-probe', targets=self.rows, run_id='offline-test',
                         stock_mission_sha256='b' * 64, server_exe_sha256=probe.rt.SERVER_EXE_SHA256,
                         staged_utc='2026-11-22T00:00:00Z')
        self.plan['binding'] = probe.binding(self.rows, self.plan['stock_mission_sha256'], self.plan['run_id'])
        self.plan_path = self.root / probe.PLAN_NAME
        self.plan_path.write_text(json.dumps(self.plan))

    def log(self):
        row = self.rows[0]
        return ['[HC OverlayProbe] begin binding=' + self.plan['binding'],
                '[HC OverlayProbe] id=%s x=%.6g z=%.6g y=81.25 nx=0 ny=1 nz=0 slope_deg=0 '
                'collision=1 blockers=2 spawned=1 yaw=-90 pitch=0 roll=0' %
                (row['id'], row['x'], row['z']),
                '[HC OverlayProbe] done targets=' + str(len(self.rows))]

    def ingest(self, lines, name='measured-heights.json'):
        rpt = self.root / 'probe.RPT'
        rpt.write_text('\n'.join(lines))
        return probe.ingest(rpt, self.root / name, self.plan_path)

    def test_authored_coverage_and_transform(self):
        source = probe.overlay.load_source()
        expected = {layer['id'] + ':' + obj['id']: obj
                    for layer in probe.overlay.enabled_layers(source)
                    for obj in probe.overlay.expand_layer(source, layer)}
        actual = probe.targets()
        self.assertEqual({r['id'] for r in actual}, set(expected))
        for row in actual:
            obj = expected[row['id']]
            self.assertEqual([row['x'], row['authored_y'], row['z']], obj['pos'])
            self.assertEqual(row['yaw'], obj['yaw'])
            self.assertEqual(row['class'], obj['class'])

    def test_complete_log_provenance_and_coordinate_precision(self):
        result = self.ingest(self.log())
        row = result['targets'][0]
        self.assertEqual([row['x'], row['z']], [self.rows[0]['x'], self.rows[0]['z']])
        self.assertEqual(row['y'], 81.25)
        self.assertEqual(row['normal'], [0, 1, 0])
        self.assertEqual(row['ypr'], [-90, 0, 0])
        self.assertEqual(row['rpy'], [0, 0, 180])
        self.assertEqual(row['a'], -90)
        self.assertTrue(row['collision'])
        self.assertEqual(result['orientation_mapping'], 'candidate-unverified')
        self.assertEqual(result['provenance']['probe_plan_sha256'],
                         probe.rt.sha256(self.plan_path.read_bytes()))
        with self.assertRaises(FileExistsError):
            self.ingest(self.log())

    def test_failed_creation_retained_without_fake_orientation(self):
        lines = self.log()
        lines[1] = lines[1].replace('spawned=1', 'spawned=0')
        row = self.ingest(lines)['targets'][0]
        self.assertFalse(row['spawned'])
        self.assertIsNone(row['rpy'])
        self.assertIsNone(row['a'])
        self.assertIsNone(row['ypr'])

    def test_bad_runs_refused_without_output(self):
        original = self.log()
        cases = [original[:-1], original[:1] + original[2:], original + [original[1]],
                 [original[0], original[1], original[1], original[2]],
                 [original[2], original[1], original[0]],
                 [original[0].replace(self.plan['binding'], 'f' * 64)] + original[1:]]
        for old, new in [('y=81.25', 'y=nan'), ('y=81.25', 'y=1e999'),
                         ('x=12345.7', 'x=12000'), ('ny=1', 'ny=0'),
                         ('slope_deg=0', 'slope_deg=30'), ('collision=1', 'collision=0'),
                         ('blockers=2', 'blockers=2.5'), ('spawned=1', 'spawned=2'),
                         ('sample:tent-p01', 'sample:unknown')]:
            cases.append([original[0], original[1].replace(old, new), original[2]])
        for lines in cases:
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                self.ingest(lines)
            self.assertFalse((self.root / 'measured-heights.json').exists())

    def test_plan_tamper_and_injection_refused(self):
        plan = copy.deepcopy(self.plan)
        plan['targets'][0]['yaw'] += 1
        self.plan_path.write_text(json.dumps(plan))
        with self.assertRaises(ValueError):
            self.ingest(self.log())
        for field, value in [('id', 'bad"injection'), ('class', 'bad"injection'), ('x', True), ('z', -1)]:
            rows = copy.deepcopy(self.rows)
            rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                probe.render_hook(rows, 'a' * 64)

    def test_dry_run_lints_without_touching_runtime(self):
        with mock.patch.object(probe.rt, 'begin', side_effect=AssertionError('must not stage')):
            result = probe.stage('unused', self.root / 'runtime', dry_run=True)
        self.assertEqual(result['targets'], len(probe.targets()))
        self.assertEqual(result['status'], 'inputs-validated-not-staged')
        self.assertFalse((self.root / 'runtime').exists())

    def test_stage_uses_safe_runtime_builder_and_exclusive_plan(self):
        context = dict(source=dict(records={'init.c': dict(source_sha256='a' * 64)}))
        built = dict(mission_files=[], staged=[])
        destination = self.root / 'runtime'
        destination.mkdir()
        with mock.patch.object(probe.rt, 'begin', return_value=context) as begin, \
                mock.patch.object(probe.rt, 'build_runtime', return_value=built) as build, \
                mock.patch.object(probe.rt, 'plan_runtime_fields', return_value={
                    'server_exe_sha256': probe.rt.SERVER_EXE_SHA256}), \
                mock.patch.object(probe.rt, 'launcher_problems', return_value=[]):
            plan = probe.stage('unused', destination)
        self.assertEqual(plan['variant'], 'overlay-survey')
        self.assertEqual(plan['probe_kind'], 'ce-overlay-probe')
        begin.assert_called_once()
        build.assert_called_once()
        self.assertEqual(plan['binding'], probe.binding(plan['targets'],
                         plan['stock_mission_sha256'], plan['run_id']))
        self.assertEqual(json.loads((destination / probe.PLAN_NAME).read_text()), plan)


if __name__ == '__main__':
    unittest.main()
