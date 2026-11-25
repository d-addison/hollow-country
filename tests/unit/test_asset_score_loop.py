"""Synthetic offline scoring only: never Blender or DayZ."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from tools.assets import score_loop as loop, render_check, visual_diff
from tools.assets.pbr_pack import Image


def image(*, color=(180, 120, 70), shift=0, stripe=False):
    rgba = bytearray(b'\0\0\0\xff' * 32 * 32)
    for y in range(8, 24):
        for x in range(8 + shift, 24 + shift):
            rgb = (255, 255, 255) if stripe and x == 16 else color
            i = (y*32+x)*4
            rgba[i:i+4] = bytes((*rgb, 255))
    return Image(32, 32, bytes(rgba))


def slow_score(connection, reference, candidate):
    time.sleep(10)


class ScoreTests(unittest.TestCase):
    def fixture(self, root, *, shift=0, color=(180, 120, 70)):
        ref, cur = root / 'ref', root / 'cur'
        for directory, shape in ((ref, image()), (cur, image(shift=shift, color=color))):
            directory.mkdir()
            for view in loop.VIEWS:
                (directory / (view+'.png')).write_bytes(render_check._png(32, 32, shape.rgba))
            doc = {'schema': 'asset-views.v1', 'projection': 'orthographic', 'background': 'black',
                   'metres_per_pixel': .001, 'views': {v: v+'.png' for v in loop.VIEWS}}
            if directory == ref:
                doc.update(lod_budgets={'0': 1000, '1': 500}, palette=['front.png'],
                           thresholds={'silhouette_iou': .92, 'edge_f1': .8, 'palette_delta_e': 12})
            else:
                doc['polycounts'] = {'0': 1000, '1': 500}
            (directory / 'views.json').write_text(json.dumps(doc))
        return ref, cur

    def test_metrics_identical_shift_colour_internal_edge(self):
        a = image()
        self.assertEqual(render_check.edge_f1(a, a), 1)
        self.assertLess(render_check.edge_f1(a, image(stripe=True)), 1)
        self.assertEqual(visual_diff.palette_distance([a], [a]), 0)
        self.assertGreater(visual_diff.palette_distance([image(color=(30, 80, 240))], [a]), 20)
        with tempfile.TemporaryDirectory() as temp:
            ref, cur = self.fixture(Path(temp))
            report = loop.score(ref, cur)
            self.assertTrue(report['pass'])
            self.assertFalse(report['engine_verified'])
            self.assertEqual(report, loop.score(ref, cur))
        with tempfile.TemporaryDirectory() as temp:
            ref, cur = self.fixture(Path(temp), shift=4)
            report = loop.score(ref, cur)
            self.assertFalse(report['pass'])
            self.assertIn(report['worst']['view'], loop.VIEWS)

    def test_worst_view_is_actionable_and_cli_report_is_private(self):
        from contextlib import redirect_stdout
        from io import StringIO
        with tempfile.TemporaryDirectory() as temp:
            ref, cur = self.fixture(Path(temp))
            shape = image(color=(30, 80, 240))
            (cur / 'side.png').write_bytes(render_check._png(32, 32, shape.rgba))
            report = loop.score(ref, cur)
            self.assertEqual(report['worst']['view'], 'side')
            self.assertEqual(report['worst']['metric'], 'palette_delta_e')
            output = StringIO()
            (Path.cwd() / 'build').mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(dir=Path.cwd() / 'build') as directory:
                target = Path(directory) / 'report.json'
                with redirect_stdout(output):
                    result = loop.main(['--reference', str(ref), '--candidates', str(cur), '--out', str(target)])
                self.assertEqual(result, 1)
                saved = json.loads(target.read_text())
                self.assertFalse(saved['engine_verified'])
                self.assertEqual(saved['worst']['view'], 'side')
                self.assertNotIn(temp, output.getvalue())
            with redirect_stdout(StringIO()):
                self.assertEqual(loop.main(['--reference', str(ref), '--candidates', str(cur),
                                            '--out', str(Path(temp) / 'forbidden.json')]), 1)
            self.assertFalse((Path(temp) / 'forbidden.json').exists())

    def test_polycounts_and_manifest_refusals(self):
        with tempfile.TemporaryDirectory() as temp:
            ref, cur = self.fixture(Path(temp))
            path = cur / 'views.json'
            original = json.loads(path.read_text())
            for updates, error in (({'metres_per_pixel': .002}, 'scale'),
                                   ({'projection': 'perspective'}, 'manifest'),
                                   ({'polycounts': {'0': 1}}, 'lods'),
                                   ({'polycounts': {'0': -1}}, 'lod_counts'),
                                   ({'views': {**original['views'], 'front': '../escape.png'}}, 'path.invalid')):
                path.write_text(json.dumps({**original, **updates}))
                with self.assertRaisesRegex(ValueError, error):
                    loop.score(ref, cur)
            path.write_text(json.dumps({**original, 'polycounts': {'0': 2000, '1': 500}}))
            report = loop.score(ref, cur)
            self.assertFalse(report['pass'])
            self.assertEqual(report['worst']['metric'], 'polycount')
            self.assertEqual(report['worst']['lod'], '0')
            self.assertIsNone(report['worst']['view'])

    def test_empty_and_wrong_background_refused(self):
        for rgba in (b'\0\0\0\xff'*1024, b'\xff\xff\xff\xff'*1024):
            shape = Image(32, 32, rgba)
            if rgba[0]:
                with self.assertRaisesRegex(ValueError, 'black_frame'):
                    render_check.black_silhouette(shape)
            else:
                with self.assertRaisesRegex(ValueError, 'empty_silhouette'):
                    mask = render_check.black_silhouette(shape)
                    render_check.iou(mask, mask)

    def test_stop_rules_and_best_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            ref, cur = self.fixture(Path(temp), shift=4)
            options = dict(scorer=loop.score)
            report = loop.run_loop(ref, [cur]*6, **options)
            self.assertEqual(report['stop_reason'], 'no_improvement')
            self.assertEqual(report['iterations'], 3)
            self.assertEqual(report['best_iteration'], 1)
            for kwargs, reason, rounds in (({'max_iterations': 2}, 'iteration_budget', 2),
                                           ({'max_renders': 4}, 'render_budget', 1),
                                           ({'max_renders': 0}, 'render_budget', 0)):
                report = loop.run_loop(ref, [cur]*6, **options, **kwargs)
                self.assertEqual((report['stop_reason'], report['iterations']), (reason, rounds))
            ticks = iter([0, 0, 2])
            self.assertEqual(loop.run_loop(ref, [cur], max_seconds=1, clock=lambda: next(ticks),
                                          scorer=lambda *a, **k: {})['stop_reason'], 'wall_budget')
            # Improvement resets stale rounds; a later regression keeps best earlier candidate.
            base = loop.score(ref, cur)
            def staged(*args, **kwargs):
                deficit = next(values)
                return {**base, 'metrics': [{'deficit': deficit}], 'pass': False}
            values = iter([.5, .5, .4, .5, .5])
            report = loop.run_loop(ref, [cur]*5, scorer=staged)
            self.assertEqual(report['best_iteration'], 3)
            self.assertEqual(report['iterations'], 5)

    def test_python_worker_pass_and_hard_deadline(self):
        with tempfile.TemporaryDirectory() as temp:
            ref, cur = self.fixture(Path(temp))
            report = loop.run_loop(ref, [cur], max_seconds=20)
            self.assertTrue(report['pass'])
            # Parent deadline also works when the scoring worker never checks its clock.
            with patch.object(loop, '_score_worker', slow_score):
                start = time.monotonic()
                report = loop.run_loop(ref, [cur], max_seconds=.5)
                self.assertEqual(report['stop_reason'], 'wall_budget')
                self.assertFalse(report['pass'])
                self.assertLess(time.monotonic() - start, 2)


if __name__ == '__main__':
    unittest.main()
