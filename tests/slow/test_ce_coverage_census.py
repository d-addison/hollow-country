"""Offline census -> ce-coverage-sampler-result converter (#11); SYNTHETIC fixtures only.

Every census, stock mission and request below is hand-built (the census rows come from the synthetic
builders of test_interior_points). They check the conversion and refusal rules; they never show where a real
building has floors, which run id a native run carries, or what spawns. Temp directories only.
"""
import contextlib
import errno
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.slow import test_interior_points as fx
from tools.package import ce_coverage as ce
from tools.package import ce_coverage_census as census_tool

RUN_ID = '0123456789abcdef0123456789abcdef'  # SYNTHETIC; a real id comes from a native run
HOOK = 'ab' * 32  # SYNTHETIC hook pin


def native_plan(run_id=RUN_ID, hook=HOOK, kind='interior-sampler', proto=None, files=None):
    """SYNTHETIC staged plan with the fields the converter reads (mission_files pins the stock prototype)."""
    proto = ce.sha(fx.STOCK) if proto is None else proto
    if files is None:
        files = [{'path': 'init.c', 'sha256': 'cd' * 32, 'source_sha256': 'ef' * 32, 'origin': 'instrumented'},
                 {'path': 'mapgroupproto.xml', 'sha256': proto, 'source_sha256': proto, 'origin': 'stock-copy'}]
    return encode({'kind': kind, 'probe': {'hook_sha256': hook, 'native_run_id': run_id}, 'mission_files': files})


def native_census(frame='as-is', run_id=RUN_ID, hook=None, document=None):
    """SYNTHETIC census document carrying the fields the converter requires on top of the sampler header."""
    document = json.loads(json.dumps(document if document is not None else fx.full_census_frame(frame)))
    if run_id is not None:
        document['native_run_id'] = run_id
    if hook is not None:
        document['hook_sha256'] = hook
    return document


def encode(document):
    return json.dumps(document).encode()


class Fixture(unittest.TestCase):
    stock = fx.STOCK

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.mission = root / 'stock-mission'  # SYNTHETIC stock mission
        self.mission.mkdir()
        (self.mission / 'mapgroupproto.xml').write_bytes(self.stock)
        self.request = ce.request(self.mission)
        self.out = root / 'result.json'

    def convert(self, document=None, raw=None, **kwargs):
        kwargs.setdefault('plan_bytes', native_plan(proto=ce.sha(self.stock)))
        data = raw if raw is not None else encode(document if document is not None else native_census())
        return census_tool.convert(data, self.request, self.mission, **kwargs)

    def refusal(self, **kwargs):
        with self.assertRaises(ValueError) as caught:
            self.convert(**kwargs)
        return str(caught.exception)


class RoundTripTests(Fixture):
    def test_synthetic_census_converts_and_generate_accepts_it(self):
        result_bytes, summary = self.convert(min_calibration=0.4)
        files = ce.generate(result_bytes, self.mission)
        self.assertEqual({'coverage-delta.json', 'delta-manifest.json'}, set(files))
        result = json.loads(result_bytes)
        self.assertEqual('ce-coverage-sampler-result', result['kind'])
        self.assertEqual(1, result['schema'])
        self.assertEqual('stock', result['frame'])
        self.assertEqual(RUN_ID, result['native_run_id'])
        self.assertEqual(ce.sha(self.stock), result['pins']['mapgroupproto_sha256'])
        self.assertEqual(ce.sha(encode(native_census())), result['pins']['census_sha256'])
        self.assertEqual(HOOK, result['pins']['hook_sha256'])
        self.assertEqual(set(ce.TARGET_GROUPS), set(result['groups']))
        self.assertEqual({'Land_Tenement_Small': 8, 'Land_Tenement_Big': 4}, summary['points'])

    def test_every_point_is_a_native_census_hit_of_the_tenement_rows(self):
        result = json.loads(self.convert(min_calibration=0.4)[0])
        for name, group in result['groups'].items():
            native = {tuple(round(v, 6) for v in fx.pts.sampler_to_stock(hit[:3], 'as-is'))
                      for row in fx.full_census()['placements'] if row['class'] == name for hit in row['hits']}
            self.assertEqual({'lootFloor'}, set(group['containers']))
            points = group['containers']['lootFloor']
            self.assertTrue(points)
            for point in points:
                self.assertIn(tuple(point), native)

    def test_points_from_placements_with_different_heights_are_actual_observed_hits(self):
        document = native_census()
        small = [row for row in document['placements'] if row['class'] == 'Land_Tenement_Small']
        for offset, row in zip((0.0, 0.02, 0.04, 0.06), small):
            for hit in row['hits']:
                hit[1] = round(hit[1] + offset, 6)
        result_bytes = self.convert(document, min_calibration=0.4)[0]
        result = json.loads(result_bytes)
        for name, group in result['groups'].items():
            native = {tuple(round(v, 6) for v in fx.pts.sampler_to_stock(hit[:3], 'as-is'))
                      for row in document['placements'] if row['class'] == name for hit in row['hits']}
            points = group['containers']['lootFloor']
            self.assertTrue(points)
            for point in points:
                self.assertIn(tuple(point), native, f'{name} point {point} is not in any input hit')
        self.assertEqual(result_bytes, self.convert(document, min_calibration=0.4)[0])
        ce.generate(result_bytes, self.mission)

    def test_rot90_census_points_are_converted_back_to_the_stock_frame(self):
        class Rot(Fixture):
            stock = fx.rotated_stock()
        case = Rot('setUp')
        case.setUp()
        try:
            result = json.loads(case.convert(document=native_census('rot90'), min_calibration=0.4)[0])
            ce.generate(json.dumps(result).encode(), case.mission)
            native = {tuple(round(v, 6) for v in fx.pts.sampler_to_stock(hit[:3], 'rot90'))
                      for row in fx.full_census()['placements'] if row['class'] == 'Land_Tenement_Small'
                      for hit in row['hits']}
            for point in result['groups']['Land_Tenement_Small']['containers']['lootFloor']:
                self.assertIn(tuple(point), native)
        finally:
            case.tmp.cleanup()

    def test_two_conversions_are_byte_identical(self):
        self.assertEqual(self.convert(min_calibration=0.4)[0], self.convert(min_calibration=0.4)[0])

    def test_points_per_container_never_exceed_the_cap(self):
        document = native_census()
        hits = [[x, y, z, 2.8, 1.0, 1] for y in (0.0, 3.0, 6.0, 9.0, 12.0, 15.0, 18.0)
                for x in fx.XS0 for z in fx.ZS]
        for row in document['placements']:
            if row['class'] == 'Land_Tenement_Small':
                row['hits'] = [list(h[:5]) + [0] for h in hits]
                row['open_codes'] = [1] * len(hits)
                row['box_max'] = [7.0, 20.0, 3.0]
        result = json.loads(self.convert(document, min_calibration=0.4)[0])
        self.assertEqual(ce.MAX_POINTS_PER_CONTAINER,
                         len(result['groups']['Land_Tenement_Small']['containers']['lootFloor']))
        ce.generate(json.dumps(result).encode(), self.mission)


class RefusalTests(Fixture):
    def test_missing_run_id_is_refused(self):
        self.assertIn('run id', self.refusal(document=native_census(run_id=None), min_calibration=0.4))

    def test_malformed_run_ids_are_refused(self):
        for bad in ('ABCDEF0123456789ABCDEF0123456789', 'abc', 123, None, '0123456789abcdef0123456789abcdeg'):
            document = native_census()
            document['native_run_id'] = bad
            with self.subTest(run_id=bad):
                self.assertIn('run id', self.refusal(document=document, min_calibration=0.4))

    def test_a_non_tenement_class_is_refused(self):
        document = native_census()
        document['placements'] += fx.four_placements('Land_Other')
        self.assertIn('Land_Other', self.refusal(document=document, min_calibration=0.4))

    def test_calibration_rows_never_become_result_groups(self):
        self.assertEqual(set(ce.TARGET_GROUPS), set(json.loads(self.convert(min_calibration=0.4)[0])['groups']))

    def test_non_finite_positions_are_refused(self):
        for token in (b'NaN', b'Infinity', b'-Infinity', b'1e999'):
            raw = encode(native_census()).replace(b'-4.5, 0.0, -3.5,', token + b', 0.0, -3.5,', 1)
            self.assertIn(token, raw)
            with self.subTest(token=token):
                self.refusal(raw=raw, min_calibration=0.4)

    def test_a_malformed_record_is_refused_not_dropped(self):
        document = native_census()
        document['placements'][0]['hits'][0] = [0.0, 0.0, 0.0]
        self.assertIn('hit', self.refusal(document=document, min_calibration=0.4))

    def test_the_plan_supplies_the_hook_pin_and_must_carry_one(self):
        result = json.loads(self.convert(plan_bytes=native_plan(hook='cd' * 32), min_calibration=0.4)[0])
        self.assertEqual('cd' * 32, result['pins']['hook_sha256'])
        self.assertIn('plan', self.refusal(plan_bytes=native_plan(hook=None), min_calibration=0.4))
        self.assertIn('plan', self.refusal(plan_bytes=native_plan(kind='other'), min_calibration=0.4))

    def test_a_missing_plan_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            census_tool.convert(encode(native_census()), self.request, self.mission, min_calibration=0.4)
        self.assertIn('plan', str(caught.exception))

    def test_a_census_run_id_that_differs_from_the_plan_is_refused(self):
        other = 'f' * 32
        self.assertIn('does not match', self.refusal(plan_bytes=native_plan(run_id=other), min_calibration=0.4))
        self.assertIn('plan', self.refusal(plan_bytes=native_plan(run_id=None), min_calibration=0.4))

    def test_an_echoed_hook_pin_must_equal_the_plans(self):
        self.assertIn('hook', self.refusal(document=native_census(hook='cd' * 32), min_calibration=0.4))
        self.convert(document=native_census(hook=HOOK), min_calibration=0.4)

    def test_a_request_pin_that_does_not_match_the_mission_is_refused(self):
        request = json.loads(self.request)
        request['sources']['mapgroupproto.xml'] = '0' * 64
        self.request = json.dumps(request).encode()
        self.assertIn('mapgroupproto', self.refusal(min_calibration=0.4))

    def test_the_plan_prototype_pin_must_match_the_request_and_mission(self):
        other = 'f' * 64
        for label, files in (
                ('other hash', None),
                ('no mission_files', 'absent'),
                ('no prototype entry', [{'path': 'init.c', 'sha256': 'cd' * 32, 'source_sha256': 'ef' * 32}]),
                ('source differs', [{'path': 'mapgroupproto.xml', 'sha256': ce.sha(self.stock), 'source_sha256': other}]),
                ('duplicate', [{'path': 'mapgroupproto.xml', 'sha256': ce.sha(self.stock),
                                'source_sha256': ce.sha(self.stock)}] * 2),
                ('not a list', {'path': 'mapgroupproto.xml'})):
            if label == 'other hash':
                plan = native_plan(proto=other)
            elif files == 'absent':
                plan = encode({'kind': 'interior-sampler',
                               'probe': {'hook_sha256': HOOK, 'native_run_id': RUN_ID}})
            else:
                plan = native_plan(files=files)
            with self.subTest(label=label):
                self.assertIn('mapgroupproto', self.refusal(plan_bytes=plan, min_calibration=0.4))

    def test_a_request_and_mission_regenerated_without_the_stock_calibration_points_are_refused(self):
        edited = self.stock
        for line in (b'\t\t\t<point pos="-1.0 0.0 -2.0" range="0.4" height="1.0" />\n',
                     b'\t\t\t<point pos="-4.5 0.0 3.5" range="0.4" height="1.0" />\n'):
            self.assertIn(line, edited)
            edited = edited.replace(line, b'', 1)
        (self.mission / 'mapgroupproto.xml').write_bytes(edited)
        self.request = ce.request(self.mission)  # request and mission agree with each other, not with the plan
        self.assertIn('mapgroupproto', self.refusal(plan_bytes=native_plan(), min_calibration=0.4))

    def test_a_request_that_is_not_the_coverage_request_is_refused(self):
        self.request = json.dumps({'kind': 'something-else', 'schema': 1}).encode()
        self.assertIn('request', self.refusal(min_calibration=0.4))

    def test_calibration_below_the_threshold_is_refused(self):
        self.assertIn('calibration', self.refusal(min_calibration=0.9).lower())

    def test_a_class_without_eligible_points_is_refused_unless_explicitly_allowed(self):
        document = native_census()
        document['placements'] = [row for row in document['placements'] if row['class'] != 'Land_Tenement_Small'] \
            + fx.four_placements('Land_Tenement_Small', hits=[])
        self.assertIn('Land_Tenement_Small', self.refusal(document=document, min_calibration=0.4))
        data, summary = self.convert(document, min_calibration=0.4, allow_empty_classes=True)
        self.assertEqual(['Land_Tenement_Big'], sorted(json.loads(data)['groups']))
        self.assertEqual(['Land_Tenement_Small'], summary['omitted'])

    def test_an_incomplete_census_is_refused(self):
        document = native_census()
        document['summary']['complete'] = False
        self.assertIn('incomplete', self.refusal(document=document, min_calibration=0.4))


class CliTests(Fixture):
    def run_cli(self, *extra, census=None, out=None):
        census_path = Path(self.tmp.name) / 'census.json'
        census_path.write_bytes(encode(census if census is not None else native_census()))
        request_path = Path(self.tmp.name) / 'request.json'
        request_path.write_bytes(self.request)
        plan_path = Path(self.tmp.name) / 'plan.json'
        plan_path.write_bytes(native_plan())
        argv = ['convert', '--census', str(census_path), '--request', str(request_path),
                '--plan', str(plan_path), '--mission', str(self.mission), '--out', str(out or self.out), '--min-calibration', '0.4', *extra]
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = census_tool.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_convert_writes_a_result_generate_accepts(self):
        code, _out, err = self.run_cli()
        self.assertEqual((0, ''), (code, err))
        ce.generate(self.out.read_bytes(), self.mission)

    def test_refusal_exits_nonzero_and_writes_nothing(self):
        code, _out, err = self.run_cli(census=native_census(run_id=None))
        self.assertEqual(1, code)
        self.assertIn('run id', err)
        self.assertFalse(self.out.exists())

    def test_an_existing_output_is_refused_and_left_alone(self):
        self.out.write_bytes(b'keep')
        code, _out, err = self.run_cli()
        self.assertEqual(1, code)
        self.assertEqual(b'keep', self.out.read_bytes())

    def test_a_symlinked_output_directory_is_refused_and_nothing_is_written(self):
        real = Path(self.tmp.name) / 'real'
        real.mkdir()
        (Path(self.tmp.name) / 'link').symlink_to(real, target_is_directory=True)
        code, _out, err = self.run_cli(out=Path(self.tmp.name) / 'link' / 'result.json')
        self.assertEqual(1, code)
        self.assertIn('symlink', err)
        self.assertEqual([], list(real.iterdir()))

    def test_a_symlinked_ancestor_further_up_is_refused(self):
        real = Path(self.tmp.name) / 'real'
        (real / 'inner').mkdir(parents=True)
        (Path(self.tmp.name) / 'link').symlink_to(real, target_is_directory=True)
        code, _out, err = self.run_cli(out=Path(self.tmp.name) / 'link' / 'inner' / 'result.json')
        self.assertEqual(1, code)
        self.assertIn('symlink', err)
        self.assertEqual([], list((real / 'inner').iterdir()))

    def test_a_dangling_symlink_at_the_output_is_refused_and_not_followed(self):
        victim = Path(self.tmp.name) / 'victim.json'
        self.out.symlink_to(victim)
        code, _out, _err = self.run_cli()
        self.assertEqual(1, code)
        self.assertFalse(victim.exists())

    def test_a_failed_write_leaves_no_final_or_temporary_file_and_a_retry_works(self):
        real_write = os.write
        calls = []

        def failing(fd, data):
            calls.append(len(data))
            if len(calls) == 1:
                return real_write(fd, bytes(data)[:10])  # a short write, then the disk fills
            raise OSError(errno.ENOSPC, 'No space left on device')
        with mock.patch.object(census_tool.os, 'write', failing):
            code, _out, err = self.run_cli()
        self.assertEqual(1, code)
        self.assertIn('refused', err)
        self.assertGreaterEqual(len(calls), 2)
        self.assertFalse(self.out.exists())
        self.assertEqual([], [p.name for p in Path(self.tmp.name).iterdir() if p.name.startswith('.') or p.name.endswith('.tmp')])
        code, _out, err = self.run_cli()
        self.assertEqual((0, ''), (code, err))
        ce.generate(self.out.read_bytes(), self.mission)
        self.assertEqual([], [p.name for p in Path(self.tmp.name).iterdir() if p.name.startswith('.') or p.name.endswith('.tmp')])

    def test_the_published_file_is_complete_and_never_overwrites_a_late_arrival(self):
        real_write_all = census_tool._write_all

        def racing(descriptor, data):
            Path(self.out).write_bytes(b'late')  # someone else creates the output after the early check
            real_write_all(descriptor, data)
        with mock.patch.object(census_tool, '_write_all', racing):
            code, _out, err = self.run_cli()
        self.assertEqual(1, code)
        self.assertEqual(b'late', self.out.read_bytes())
        self.assertEqual(['result.json'], sorted(p.name for p in Path(self.tmp.name).iterdir()
                                                 if p.name.startswith('result') or p.name.startswith('.')))

    def test_output_inside_the_shipped_mission_folder_is_refused(self):
        target = ce.REPO_ROOT / 'mission' / 'hollow-country' / 'ce-coverage' / 'census-test-result.json'
        before = target.exists()
        code, _out, err = self.run_cli(out=target)
        self.assertEqual(1, code)
        self.assertIn('mission', err)
        self.assertEqual(before, target.exists())

    def test_a_dotdot_output_cannot_alias_the_guard_and_the_write_to_different_places(self):
        root = Path(self.tmp.name) / 'fixture'
        (root / 'mission').mkdir(parents=True)
        (root / 'outside' / 'nested').mkdir(parents=True)
        (root / 'mission' / 'alias').symlink_to(root / 'outside' / 'nested', target_is_directory=True)
        with mock.patch.object(ce, 'REPO_ROOT', root):
            code, _out, err = self.run_cli(out=root / 'mission' / 'alias' / '..' / 'result.json')
        self.assertEqual(1, code)
        self.assertIn('..', err)
        self.assertEqual([], list((root / 'mission').glob('result*')))
        self.assertEqual([], list((root / 'outside').glob('result*')))
        self.assertEqual(['alias'], sorted(p.name for p in (root / 'mission').iterdir()))


if __name__ == '__main__':
    unittest.main()
