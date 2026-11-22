"""Synthetic parser/generator checks; these do not establish engine behavior."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools.package import hc_events as hc
from tools.setup import ce_site_probe as probe


def measurement(rows):
    return dict(schema=1, blocker_radius_m=hc.BLOCKER_RADIUS_M,
                provenance=dict(server_exe_sha256='a' * 64, stock_mission_sha256='b' * 64,
                                probe_plan_sha256='c' * 64, rpt_sha256='d' * 64,
                                treatment='current', date='2026-11-21'),
                targets=[dict(r, y=100.25, slope_deg=0, water=0, blockers=0) for r in rows])


class SiteProbeTests(unittest.TestCase):
    def setUp(self):
        self.rows = probe.targets()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = dict(run_id='synthetic-run', kind='ce-site-probe', variant='current', targets=self.rows,
                         stock_mission_sha256='b' * 64, server_exe_sha256=probe.rt.SERVER_EXE_SHA256,
                         staged_utc='2026-11-21T00:00:00Z')
        self.plan['binding'] = probe.binding(self.rows, 'current', self.plan['stock_mission_sha256'], self.plan['run_id'])
        self.plan_path = self.root / probe.PLAN_NAME
        self.plan_path.write_text(json.dumps(self.plan))

    def log(self):
        lines = ['[HC SiteProbe] begin binding=' + self.plan['binding']]
        for r in self.rows:
            lines.append('[HC SiteProbe] id={id} x={x} z={z} y=100.25 slope_deg=0 water=0 blockers=0 nearest=none@-1'.format(**r))
        lines.append('[HC SiteProbe] done targets=' + str(len(self.rows)))
        return lines

    def ingest(self, lines):
        rpt = self.root / 'probe.RPT'
        rpt.write_text('\n'.join(lines))
        return probe.ingest(rpt, self.root / 'measured.json', self.plan_path)

    def test_targets_cover_authored_positions_and_bounded_cache_rings(self):
        anchors = {}
        for relative in ('ce/hc-eventspawns.xml', 'events/cache-eventspawns.xml'):
            for event in ET.fromstring((hc.SOURCE / relative).read_bytes()):
                for index, pos in enumerate(event.findall('pos'), 1):
                    anchors['%s:site%03d' % (event.get('name'), index)] = pos
        self.assertEqual({r['id'] for r in self.rows if ':site' in r['id']}, set(anchors))
        for r in self.rows:
            if ':ring' in r['id']:
                anchor = anchors[r['id'].split(':')[0] + ':site001']
                self.assertLessEqual(((r['x'] - float(anchor.get('x'))) ** 2 +
                                      (r['z'] - float(anchor.get('z'))) ** 2) ** .5, hc.CACHE_RADIUS_M)
        self.assertLessEqual(len(self.rows), probe.HARD_CAP)

    def test_complete_ingest_counts_both_phases_and_keeps_provenance(self):
        lines = self.log()
        for phase in ('Init', 'Respawning'):
            lines.append('!!! [CE][VehicleRespawner] (PRIHC) :: %s: "StaticHCTest" - Failed to spawn the requested amount (0 < 3) within 9 attempts.' % phase)
        result = self.ingest(lines)
        self.assertEqual(result['targets'], [dict(r, y=100.25, slope_deg=0, water=0, blockers=0,
                                                 nearest='none', nearest_m=-1) for r in self.rows])
        self.assertEqual([r['phase'] for r in result['ce_failures']], ['Init', 'Respawning'])
        self.assertEqual(result['ce_failure_counts'], {p: sum(f['phase'] == p for f in result['ce_failures'])
                                                      for p in ('Init', 'Respawning')})
        self.assertEqual(result['provenance']['probe_plan_sha256'], probe.rt.sha256(self.plan_path.read_bytes()))

    def test_incomplete_duplicate_malformed_and_wrong_run_refused(self):
        original = self.log()
        cases = [original[:-1], original[:1] + original[2:], original + [original[1]],
                 [original[0].replace(self.plan['binding'], 'f' * 64)] + original[1:],
                 [original[0], original[1].replace('y=100.25', 'y=nan')] + original[2:]]
        for lines in cases:
            with self.subTest(lines=len(lines)), self.assertRaises(ValueError):
                self.ingest(lines)

    def source_copy(self):
        for name in hc.DATA:
            path = self.root / 'ce' / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes((hc.SOURCE / 'ce' / name).read_bytes())
        for name in hc.CACHE_DATA:
            path = self.root / 'events' / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes((hc.SOURCE / 'events' / name).read_bytes())

    def test_measured_generator_heights_candidates_and_digest(self):
        self.source_copy()
        old_data, old_roots, _, _ = hc.validate(self.root)
        data = measurement(self.rows)
        (self.root / hc.MEASUREMENTS).write_text(json.dumps(data))
        new_data, roots, _, _ = hc.validate(self.root)
        self.assertNotEqual(hc._digest(old_data), hc._digest(new_data))
        for event in roots[1]:
            self.assertTrue(all(float(pos.get('y')) == 100.25 for pos in event.findall('pos')))
            if event.get('name').startswith('ItemHCSceneCache'):
                self.assertGreaterEqual(len(event), hc.MIN_CACHE_POSITIONS)
        self.assertEqual(len(old_roots[2]), len(roots[2]))

    def test_generator_refuses_missing_drift_and_short_cache_pool(self):
        self.source_copy()
        original = measurement(self.rows)
        cases = []
        missing = copy.deepcopy(original)
        missing['targets'].pop(0)
        cases.append(missing)
        bad = copy.deepcopy(original)
        bad['targets'][0]['x'] = 1
        cases.append(bad)
        bad = copy.deepcopy(original)
        for row in bad['targets']:
            if row['id'].startswith('ItemHCSceneCache'):
                row['water'] = 1
        cases.append(bad)
        for bad in cases:
            (self.root / hc.MEASUREMENTS).write_text(json.dumps(bad))
            with self.subTest(case=len(bad['targets'])), self.assertRaises(ValueError):
                hc.validate(self.root)

    def test_screened_out_group_anchor_is_kept_and_reported(self):
        self.source_copy()
        for key, value in (('water', 1), ('slope_deg', hc.MAX_SLOPE_DEG + 1), ('blockers', 1)):
            bad = measurement(self.rows)
            bad['targets'][0][key] = value
            (self.root / hc.MEASUREMENTS).write_text(json.dumps(bad))
            with self.subTest(key=key):
                report = hc.validate(self.root)[3]
                self.assertEqual(report['measured_unusable_anchors'], [bad['targets'][0]['id']])

    def test_generated_hook_passes_shared_compile_shape_checks(self):
        hook = probe.render_hook(self.rows, self.plan['binding'])
        self.assertEqual(probe.rt.lint_hook(hook.decode('ascii')), [])

    def test_treatment_and_timing_refusals(self):
        for args in (dict(treatment='measured'), dict(hold_seconds=239), dict(hold_seconds=600, wait_minutes=5)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                probe.stage('unused', self.root / 'fresh', dry_run=True, **args)
        self.assertFalse((self.root / 'fresh').exists())


if __name__ == '__main__':
    unittest.main()
