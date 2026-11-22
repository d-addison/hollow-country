"""Synthetic parser/generator checks; these do not establish engine behavior."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock
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

    def test_screened_out_group_anchor_is_retired_and_reported(self):
        self.source_copy()
        for key, value in (('water', 1), ('slope_deg', hc.MAX_SLOPE_DEG + 1), ('blockers', 1)):
            bad = measurement(self.rows)
            bad['targets'][0][key] = value
            (self.root / hc.MEASUREMENTS).write_text(json.dumps(bad))
            with self.subTest(key=key):
                report = hc.validate(self.root)[3]
                anchor = bad['targets'][0]
                self.assertEqual(report['measured_unusable_anchors'], [])
                self.assertEqual(report['measured_retired_anchors'], {
                    anchor['id']: dict(x=anchor['x'], z=anchor['z'], reasons={key: value})})

    def original_survey_bytes(self):
        doc = json.loads((hc.SOURCE / hc.MEASUREMENTS).read_bytes())
        authored_ids = {r['id'] for r in self.rows}
        doc['targets'] = [r for r in doc['targets'] if r['id'] in authored_ids]
        doc['provenance'].pop('runs', None)
        return json.dumps(doc).encode()

    def relocation_source(self):
        doc = measurement(self.rows)
        doc['targets'][0]['water'] = 1
        path = self.root / 'base.json'
        path.write_text(json.dumps(doc))
        return path, doc

    def test_relocation_chunks_cover_only_screened_out_group_rings_under_cap(self):
        raw = self.original_survey_bytes()
        measured = json.loads(raw)
        groups = {r['id']: r for r in self.rows if ':site' in r['id']
                  and not r['id'].startswith('ItemHCSceneCache')}
        bad = {r['id'] for r in measured['targets']
               if r['id'] in groups and not hc.measurement_usable(r)}
        ring_size = len(probe.RING_RADII) * probe.RING_BEARINGS
        count = math.ceil(len(bad) / (probe.HARD_CAP // ring_size))
        observed = []
        for index in range(1, count + 1):
            selector = '%d/%d' % (index, count)
            rows, metadata = probe.relocation_targets(raw, selector)
            self.assertLessEqual(len(rows), probe.HARD_CAP)
            self.assertEqual(metadata['source_measurement_sha256'], probe.rt.sha256(raw))
            self.assertEqual(metadata['chunk'], selector)
            for row in rows:
                anchor = groups[row['id'].rsplit(':', 1)[0]]
                self.assertLessEqual(math.hypot(row['x'] - anchor['x'], row['z'] - anchor['z']),
                                     hc.RELOCATE_RADIUS_M + 0.000001)
            observed.extend(rows)
        self.assertEqual({r['id'].rsplit(':', 1)[0] for r in observed}, bad)
        self.assertEqual(len(observed), len(bad) * ring_size)
        self.assertEqual(len({r['id'] for r in observed}), len(observed))
        for selector in (None, '0/%d' % count, '1/%d' % (count + 1), '%d/%d' % (count + 1, count)):
            with self.subTest(selector=selector), self.assertRaises(ValueError):
                probe.relocation_targets(raw, selector)

    def chunk_document(self, base):
        rows, metadata = probe.relocation_targets(base.read_bytes(), '1/1')
        doc = measurement(rows)
        doc['relocation'] = metadata
        path = self.root / 'chunk.json'
        path.write_text(json.dumps(doc))
        return path, doc

    def test_merge_retains_every_run_and_applies_schema_one_output(self):
        self.source_copy()
        base, original = self.relocation_source()
        chunk, doc = self.chunk_document(base)
        out = self.root / hc.MEASUREMENTS
        merged = probe.merge(base, [chunk], out)
        self.assertEqual(merged['targets'], original['targets'] + doc['targets'])
        runs = merged['provenance']['runs']
        self.assertEqual([r['measurement_sha256'] for r in runs],
                         [probe.rt.sha256(p.read_bytes()) for p in (base, chunk)])
        self.assertEqual(runs[1]['relocation'], doc['relocation'])
        report = hc.validate(self.root)[3]
        self.assertIn(original['targets'][0]['id'], report['measured_relocated_anchors'])
        self.assertEqual(report['measured_unusable_anchors'], [])
        with self.assertRaises((ValueError, FileExistsError)):
            probe.merge(base, [chunk], out)

    def test_merge_refuses_hash_mismatch_duplicate_ids_and_incomplete_chunks(self):
        base, _ = self.relocation_source()
        chunk, original = self.chunk_document(base)
        cases = []
        for key in ('server_exe_sha256', 'stock_mission_sha256'):
            doc = copy.deepcopy(original)
            doc['provenance'][key] = 'f' * 64
            cases.append(doc)
        doc = copy.deepcopy(original)
        doc['targets'].append(doc['targets'][0])
        cases.append(doc)
        doc = copy.deepcopy(original)
        doc['relocation']['source_measurement_sha256'] = 'f' * 64
        cases.append(doc)
        doc = copy.deepcopy(original)
        doc['targets'][0]['x'] += 1
        cases.append(doc)
        for doc in cases:
            chunk.write_text(json.dumps(doc))
            with self.subTest(case=doc), self.assertRaises(ValueError):
                probe.merge(base, [chunk], self.root / 'merged.json')
            self.assertFalse((self.root / 'merged.json').exists())
        chunk.write_text(json.dumps(original))
        for chunks in ([], [chunk, chunk]):
            with self.subTest(chunks=len(chunks)), self.assertRaises(ValueError):
                probe.merge(base, chunks, self.root / 'merged.json')

    def test_merge_requires_every_chunk_and_keeps_unusable_evidence(self):
        original = measurement(self.rows)
        # Enough screened-out anchors across types to exercise multiple chunks,
        # while each type retains its nominal + observer headroom.
        per_chunk = probe.HARD_CAP // (len(probe.RING_RADII) * probe.RING_BEARINGS)
        bad_ids = set()
        by_event = {}
        for row in original['targets']:
            if row['id'].startswith('StaticHC'):
                by_event.setdefault(row['id'].split(':')[0], []).append(row)
        for event_rows in by_event.values():
            for row in event_rows[:2]:
                row['water'] = 1
                bad_ids.add(row['id'])
        raw = json.dumps(original).encode()
        base = self.root / 'base.json'
        base.write_bytes(raw)
        count = math.ceil(len(bad_ids) / per_chunk)
        chunks = []
        for index in range(1, count + 1):
            rows, metadata = probe.relocation_targets(raw, '%d/%d' % (index, count))
            doc = measurement(rows)
            doc['provenance'] = original['provenance']
            doc['relocation'] = metadata
            for row in doc['targets']:
                row['water'] = 1
            path = self.root / ('chunk%d.json' % index)
            path.write_text(json.dumps(doc))
            chunks.append(path)
        out = self.root / 'merged.json'
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            probe.merge(base, chunks[:-1], out)
        self.assertFalse(out.exists())
        merged = probe.merge(base, chunks, out)
        self.assertEqual(len(merged['provenance']['runs']), len(chunks) + 1)
        self.source_copy()
        (self.root / hc.MEASUREMENTS).write_bytes(out.read_bytes())
        report = hc.validate(self.root)[3]
        self.assertEqual(report['measured_unusable_anchors'], [])
        self.assertEqual(set(report['measured_retired_anchors']), bad_ids)
        self.assertEqual(report['measured_relocated_anchors'], {})

    def test_relocation_selects_nearest_usable_and_preserves_angle_and_group(self):
        self.source_copy()
        base, doc = self.relocation_source()
        anchor = doc['targets'][0]
        for distance in (hc.RELOCATE_RADIUS_M + 1, 8, 4, 2):
            doc['targets'].append(dict(anchor, id=anchor['id'] + ':ring%d_0' % distance,
                                       x=anchor['x'] + distance, water=int(distance == 2), y=distance))
        (self.root / hc.MEASUREMENTS).write_text(json.dumps(doc))
        baseline = hc.validate()[1][1][0].find('pos')
        _, roots, _, report = hc.validate(self.root)
        actual = roots[1][0].find('pos')
        selected = min((r for r in doc['targets'] if r['id'].startswith(anchor['id'] + ':ring')
                        and hc.measurement_usable(r)), key=lambda r: abs(r['x'] - anchor['x']))
        self.assertEqual(float(actual.get('x')), selected['x'])
        self.assertEqual(float(actual.get('z')), selected['z'])
        self.assertEqual(float(actual.get('y')), selected['y'])
        self.assertEqual(actual.get('a'), baseline.get('a'))
        self.assertEqual(actual.get('group'), baseline.get('group'))
        relocation = report['measured_relocated_anchors'][anchor['id']]
        self.assertEqual(relocation['from'], {a: anchor[a] for a in ('x', 'z', 'y')})
        self.assertEqual(relocation['to'], {a: selected[a] for a in ('x', 'z', 'y')})
        self.assertAlmostEqual(relocation['distance'], abs(selected['x'] - anchor['x']))
        # A usable authored anchor wins even when usable ring observations exist.
        anchor['water'] = 0
        (self.root / hc.MEASUREMENTS).write_text(json.dumps(doc))
        _, roots, _, report = hc.validate(self.root)
        self.assertEqual(float(roots[1][0].find('pos').get('x')), anchor['x'])
        self.assertEqual(report['measured_relocated_anchors'], {})

    def test_no_usable_candidate_within_radius_retires_and_reports_anchor(self):
        self.source_copy()
        _, doc = self.relocation_source()
        anchor = doc['targets'][0]
        doc['targets'].extend([
            dict(anchor, id=anchor['id'] + ':ring04_0', x=anchor['x'] + 4),
            dict(anchor, id=anchor['id'] + ':ring99_0',
                 x=anchor['x'] + hc.RELOCATE_RADIUS_M + 1, water=0)])
        (self.root / hc.MEASUREMENTS).write_text(json.dumps(doc))
        _, roots, _, report = hc.validate(self.root)
        self.assertEqual(report['measured_unusable_anchors'], [])
        self.assertIn(anchor['id'], report['measured_retired_anchors'])
        self.assertEqual(report['measured_relocated_anchors'], {})
        event = roots[1][0]
        self.assertNotIn(anchor['x'], [float(p.get('x')) for p in event.findall('pos')])
        name, site = anchor['id'].split(':')
        self.assertNotIn(name + '_Site' + site.removeprefix('site'),
                         {g.get('name') for g in roots[2]})
        budget = next(b for b in report['event_budgets'] if b['event'] == name)
        self.assertEqual(budget['positions'], len(event.findall('pos')))
        self.assertGreaterEqual(budget['positions_after_six_observers'], budget['nominal'])

    def test_retirement_refuses_headroom_breach_with_event_name(self):
        self.source_copy()
        doc = measurement(self.rows)
        events = ET.fromstring((self.root / 'ce/hc-events.xml').read_bytes())
        name = doc['targets'][0]['id'].split(':')[0]
        policy = events.find("event[@name='%s']" % name)
        anchors = [r for r in doc['targets'] if r['id'].startswith(name + ':site')]
        keep = int(policy.findtext('nominal')) + hc.MAX_OBSERVERS
        for row in anchors[:len(anchors) - keep + 1]:
            row['water'] = 1
        (self.root / hc.MEASUREMENTS).write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, name):
            hc.validate(self.root)

    def test_later_authored_ids_survive_retirement_and_measured_staging(self):
        self.source_copy()
        _, doc = self.relocation_source()
        first, later = doc['targets'][:2]
        later['y'] = 123.5
        later['water'] = 1
        moved = dict(later, id=later['id'] + ':ring04_0', x=later['x'] + 4, water=0)
        doc['targets'].append(moved)
        path = self.root / hc.MEASUREMENTS
        path.write_text(json.dumps(doc))
        _, roots, _, report = hc.validate(self.root)
        name, site = later['id'].split(':')
        survivor = roots[1].find("event[@name='%s']/pos" % name)
        self.assertEqual(survivor.get('group'), name + '_Site' + site.removeprefix('site'))
        self.assertEqual(float(survivor.get('y')), later['y'])
        self.assertEqual(probe.targets(self.root), self.rows)
        with mock.patch.object(probe, 'render_hook', wraps=probe.render_hook) as render:
            result = probe.stage('unused', self.root / 'fresh', source=self.root,
                                 treatment='measured', measured=path, dry_run=True)
        staged = {r['id']: r for r in render.call_args.args[0]}
        self.assertNotIn(first['id'], staged)
        self.assertEqual(staged[later['id']], dict(id=later['id'], x=moved['x'], z=moved['z']))
        self.assertEqual(result['targets'], len(self.rows) - len(report['measured_retired_anchors']))
        self.assertEqual(result['measured_retired_anchors'], report['measured_retired_anchors'])
        # A survey without policies cannot admit retirement; it keeps the unusable id.
        positions = ET.fromstring((self.root / 'ce/hc-eventspawns.xml').read_bytes())
        caches = ET.fromstring((self.root / 'events/cache-eventspawns.xml').read_bytes())
        self.assertEqual(hc.apply_measurements(positions, caches, doc), [first['id']])
        # Ingest keeps the surviving authored ids, including relocated coordinates.
        self.rows = list(staged.values())
        self.plan.update(variant='measured', targets=self.rows)
        self.plan['binding'] = probe.binding(self.rows, 'measured', self.plan['stock_mission_sha256'],
                                            self.plan['run_id'])
        self.plan_path.write_text(json.dumps(self.plan))
        ingested = self.ingest(self.log())
        self.assertEqual({r['id'] for r in ingested['targets']}, set(staged))
        self.assertNotIn(first['id'], {r['id'] for r in ingested['targets']})

    def test_current_staging_ignores_committed_measurements(self):
        self.source_copy()
        def current():
            with mock.patch.object(probe, 'render_hook', wraps=probe.render_hook) as render:
                result = probe.stage('unused', self.root / 'fresh', source=self.root, dry_run=True)
            return result, render.call_args
        before, before_args = current()
        (self.root / hc.MEASUREMENTS).write_bytes((hc.SOURCE / hc.MEASUREMENTS).read_bytes())
        after, after_args = current()
        self.assertEqual(before, after)
        self.assertEqual(before_args, after_args)
        self.assertEqual(after['targets'], len(self.rows))
        self.assertEqual(after['measured_retired_anchors'], {})

    def test_relocated_output_refuses_both_separation_violations(self):
        for same_type in (False, True):
            with self.subTest(same_type=same_type):
                positions = ET.Element('eventposdef')
                events = ET.Element('events')
                rows = []
                for index, x in enumerate((1000, 1341)):
                    name = 'TestA' if same_type else 'Test' + str(index)
                    event = positions.find("event[@name='%s']" % name)
                    if event is None:
                        event = ET.SubElement(positions, 'event', name=name)
                        policy = ET.SubElement(events, 'event', name=name)
                        ET.SubElement(policy, 'distanceradius').text = '340'
                        ET.SubElement(policy, 'saferadius').text = '170'
                    number = len(event.findall('pos')) + 1
                    ET.SubElement(event, 'pos', x=str(x), z='1000', a='7', group='test')
                    rows.append(dict(id='%s:site%03d' % (name, number), x=x, z=1000))
                hc.check_anchor_separation(events, positions)
                doc = measurement(rows)
                anchor = doc['targets'][0]
                anchor['water'] = 1
                # 340 m is allowed globally, but refused by this same-type policy.
                distance = 1 if same_type else 4
                doc['targets'].append(dict(anchor, id=anchor['id'] + ':ring04_0',
                                           x=anchor['x'] + distance, water=0))
                hc.apply_measurements(positions, ET.Element('eventposdef'), doc)
                with self.assertRaisesRegex(ValueError, 'same-type' if same_type else '340 m'):
                    hc.check_anchor_separation(events, positions)

    def test_relocation_binding_and_ingest_preserve_source_and_chunk(self):
        base, _ = self.relocation_source()
        self.rows, metadata = probe.relocation_targets(base.read_bytes(), '1/1')
        self.plan.update(targets=self.rows, relocation=metadata)
        self.plan['binding'] = probe.binding(self.rows, self.plan['variant'],
                                            self.plan['stock_mission_sha256'], self.plan['run_id'], metadata)
        self.plan_path.write_text(json.dumps(self.plan))
        result = self.ingest(self.log())
        self.assertEqual(result['relocation'], metadata)
        self.plan['relocation']['source_measurement_sha256'] = 'f' * 64
        self.plan_path.write_text(json.dumps(self.plan))
        with self.assertRaises(ValueError):
            self.ingest(self.log())

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
