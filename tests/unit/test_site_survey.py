"""Site survey tool: candidate determinism, input shape, bitmap decoding and result import (synthetic data only)."""
import json
import tempfile
import unittest
from pathlib import Path

from tools.package import site_survey as ss

REPO = ss.ROOT
PROBE = REPO / 'mods/HollowCountry/scripts/4_World/Debug/HCSiteSurveyProbe.c'


def synthetic_input(calibrate=()):
    gn, cn = ss.grid_n(), ss.cell_n()
    body = dict(ss.PARAMS)
    body.update({'schema': 1, 'kind': ss.INPUT_KIND, 'hold_seconds': 300.0, 'slice_ms': 4.0, 'units_per_tick': 64,
                 'calibrate_x': 0.0, 'calibrate_z': 0.0, 'calibrate_spacing_m': 0.0,
                 'roads': [100.0, 200.0, 45.0], 'centres': [100.0, 200.0],
                 'pieces': [100.0, 200.0, 0.0, 2.0, 3.0, 2.5], 'piece_ids': ['p1'], 'calibrate': list(calibrate),
                 'input_id': 'abcd'})
    return body, gn, cn


def synthetic_result(gn, cn, legend):
    n = gn * gn
    width = (cn + 3) // 4 * cn
    return {'schema': 1, 'kind': ss.RESULT_KIND, 'input_id': 'abcd', 'world': 'chernarusplus', 'done': True,
            'params': {'grid_n': gn, 'cell_n': cn}, 'surface_legend': legend,
            'roads': [[0, '001', 2000, 1990]],
            'centres': [{'i': 0, 'h': ','.join(['2000'] * n), 's': ','.join(['5'] * n), 'w': '0' * n,
                         't': '0' * n, 'b': '0' * width, 'tr': 'f' * width}],
            'pieces': [{'i': 0, 'id': 'p1', 'y': [1, 2, 3, 4, 5], 'w': 0, 'spread': 4, 'hit': 1, 'n': [1, 0, 0]}],
            'calibration': []}


class SiteSurveyTests(unittest.TestCase):
    def test_candidates_are_committed_and_deterministic(self):
        first = ss.build_candidates(REPO, 50, ss.DEFAULTS['min_spacing_m'], ss.DEFAULTS['straight_spacing_m'])
        second = ss.build_candidates(REPO, 50, ss.DEFAULTS['min_spacing_m'], ss.DEFAULTS['straight_spacing_m'])
        self.assertEqual(first, second)
        self.assertEqual(ss.cmd_check(REPO, None), 0)

    def test_input_matches_probe_dto_and_is_stable(self):
        a = ss.build_input(REPO)
        b = ss.build_input(REPO)
        self.assertEqual(a, b)
        text = PROBE.read_text()
        dto = text.split('class HCSiteSurveyInput', 1)[1].split('}', 1)[0]
        for key in a:
            self.assertIn(' %s;' % key, dto, key)
        self.assertEqual(len(a['roads']) % 3, 0)
        self.assertEqual(len(a['centres']) % 2, 0)

    def test_hex_rows_decode_high_bit_first(self):
        rows = ss.hex_rows('84', 2)
        self.assertEqual(rows, [[True, False], [False, True]])
        self.assertEqual(len(ss.hex_rows('f' * 100, 20)), 20)
        with self.assertRaises(ss.SurveyError):
            ss.hex_rows('ff', 20)

    def test_surface_classification(self):
        self.assertEqual(ss.classify_surface('Some_Asphalt_Dry'), 'a')
        self.assertEqual(ss.classify_surface('xyz_unknown'), 'o')

    def test_import_roundtrip_and_rejections(self):
        inp, gn, cn = synthetic_input(calibrate=['TestClassA'])
        res = synthetic_result(gn, cn, ['grass_mud', 'asphalt_road'])
        res['calibration'] = [{'i': 0, 'x': 0, 'y': 0, 'z': 0, 'spawned': 1}]
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            (repo / ss.SURVEY_DIR).mkdir(parents=True)
            (repo / ss.SURVEY_DIR / 'candidates.json').write_text('{}')
            (repo / 'in.json').write_text(json.dumps(inp))
            (repo / 'out.json').write_text(json.dumps(res))
            self.assertEqual(ss.import_result(repo, repo / 'in.json', repo / 'out.json'), 0)
            first = {p.name: p.read_bytes() for p in (repo / ss.SURVEY_DIR).glob('*.json')}
            self.assertEqual(ss.import_result(repo, repo / 'in.json', repo / 'out.json'), 0)
            second = {p.name: p.read_bytes() for p in (repo / ss.SURVEY_DIR).glob('*.json')}
            self.assertEqual(first, second)
            self.assertNotIn(b'TestClassA', b''.join(first.values()))
            data = ss.load_survey(repo)
            self.assertEqual(data['roads'], {'kind': ss.SURVEY_KIND, 'version': 1, 'road_samples': [[100.0, 200.0, 'dirt']]})
            samples = data['cells']['cells']['samples']
            self.assertEqual(len(samples), gn * gn)
            self.assertEqual(samples[0], [60.0, 160.0, 5, 0])
            self.assertEqual(data['cells']['cells']['size_m'], 8.0)
            entry = data['pieces']['pieces']['p1']
            self.assertEqual(entry['corners_y'], [0.01, 0.02, 0.03, 0.04])
            self.assertEqual(sorted(entry), ['center_y', 'collides', 'corners_y', 'slope_pct', 'water'])
            self.assertIs(entry['collides'], True)
            self.assertIs(entry['water'], False)
            self.assertEqual(data['manifest']['parts']['calibration']['spawned'], 1)
            self.assertEqual(ss.cmd_check(repo, None), 1)  # candidates.json and format.json are absent in this temp repo
            for bad in ({'done': False}, {'input_id': 'other'}, {'params': {'grid_n': 3, 'cell_n': cn}}):
                broken = dict(res)
                broken.update(bad)
                (repo / 'bad.json').write_text(json.dumps(broken))
                with self.subTest(bad=bad), self.assertRaises(ss.SurveyError):
                    ss.import_result(repo, repo / 'in.json', repo / 'bad.json')

    def test_probe_is_inert_by_default(self):
        text = PROBE.read_text()
        self.assertIn('HCSiteSurveyGate.HCArmed()', text)
        self.assertIn('hcSiteSurvey', text)
        self.assertNotIn('HCModuleReadiness.HCPrint', text)
        self.assertNotIn('HCUse', text)


if __name__ == '__main__':
    unittest.main()
