"""FLIP gate tests on synthetic images only; no renders, no game assets."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.assets import blender_runner, render_check
from tools.assets.pbr_pack import Image, decode_image, encode_tga
from tools.assets.provenance import Refusal
from tools.validate import flip_diff

try:
    import numpy  # noqa: F401
except ImportError:      # the gate itself refuses loudly without numpy
    numpy = None

SIZE = 32


def render(box, shade=200, size=SIZE, background=13):
    pixels = bytearray()
    for y in range(size):
        for x in range(size):
            inside = box[0] <= x < box[2] and box[1] <= y < box[3]
            value = shade if inside else background
            pixels += bytes((value, value, value, 255))
    return Image(size, size, bytes(pixels))


def views(box, **kwargs):
    return {v: encode_tga(render(box, **kwargs)) for v in flip_diff.VIEWS}


@unittest.skipIf(numpy is None, 'numpy missing')
class MetricTests(unittest.TestCase):
    def test_identical_images_have_zero_error(self):
        image = render((8, 8, 24, 24))
        errors = flip_diff.error_map(image, image)
        self.assertEqual(float(errors.max()), 0.0)
        self.assertEqual(flip_diff.metric(image, image)['mean_flip'], 0.0)

    def test_error_is_bounded_and_grows_with_difference(self):
        base = render((8, 8, 24, 24))
        shifted = flip_diff.metric(base, render((12, 8, 28, 24)))['mean_flip']
        dimmer = flip_diff.metric(base, render((8, 8, 24, 24), shade=120))['mean_flip']
        black_white = flip_diff.metric(render((0, 0, 0, 0), background=0),
                                       render((0, 0, 0, 0), background=255))['mean_flip']
        self.assertGreater(shifted, 0.0)
        self.assertGreater(dimmer, 0.0)
        self.assertGreater(black_white, max(shifted, dimmer))
        self.assertLessEqual(black_white, 1.0)

    def test_error_is_symmetric_and_deterministic(self):
        a, b = render((8, 8, 24, 24)), render((10, 6, 26, 22), shade=150)
        forward = flip_diff.metric(a, b)
        self.assertEqual(forward, flip_diff.metric(a, b))
        self.assertAlmostEqual(forward['mean_flip'], flip_diff.metric(b, a)['mean_flip'], places=2)

    def test_heatmap_dimensions_and_colours(self):
        a, b = render((8, 8, 24, 24)), render((12, 8, 28, 24))
        image = flip_diff.heatmap(flip_diff.error_map(a, b))
        self.assertEqual((image.width, image.height, len(image.rgba)), (SIZE, SIZE, SIZE * SIZE * 4))
        self.assertEqual(image.rgba[3::4], bytes([255]) * (SIZE * SIZE))
        flat = flip_diff.heatmap(flip_diff.error_map(a, a))
        self.assertEqual(tuple(flat.rgba[0:3]), flip_diff.MAGMA[0])

    def test_input_validation(self):
        image = render((8, 8, 24, 24))
        with self.assertRaises(ValueError):
            flip_diff.error_map(image, render((8, 8, 24, 24), size=16))
        with self.assertRaises(ValueError):
            flip_diff.error_map(image, b'raw')
        for bad in (0, -1, float('nan'), 1e9, True):
            with self.assertRaises(ValueError):
                flip_diff.error_map(image, image, ppd=bad)

    def test_compare_pass_and_fail(self):
        same = flip_diff.compare(views((8, 8, 24, 24)), views((8, 8, 24, 24)))
        self.assertTrue(same['pass'])
        self.assertFalse(same['engine_verified'])
        self.assertEqual(set(same['views']), set(flip_diff.VIEWS))
        other = flip_diff.compare(views((8, 8, 24, 24)), views((8, 8, 24, 24), shade=40))
        self.assertFalse(other['pass'])
        loose = flip_diff.compare(views((8, 8, 24, 24)), views((8, 8, 24, 24), shade=40), max_mean=1.0)
        self.assertTrue(loose['pass'])

    def test_compare_refuses_bad_threshold_and_missing_views(self):
        good = views((8, 8, 24, 24))
        for bad in (-0.1, 1.5, float('nan'), True, '0.1'):
            with self.assertRaises(ValueError):
                flip_diff.compare(good, good, max_mean=bad)
        with self.assertRaises(ValueError):
            flip_diff.compare({k: v for k, v in good.items() if k != 'top'}, good)

    def test_selftest(self):
        flip_diff.selftest()


class NumpyMissingTests(unittest.TestCase):
    def test_refusal_is_loud_not_a_skip(self):
        with mock.patch.dict('sys.modules', {'numpy': None}):
            with self.assertRaises(Refusal) as caught:
                flip_diff.metric(render((8, 8, 24, 24)), render((8, 8, 24, 24)))
        self.assertIn('flip.numpy_required', str(caught.exception))


@unittest.skipIf(numpy is None, 'numpy missing')
class RenderCheckWiringTests(unittest.TestCase):
    def test_goldens_report_includes_flip_and_it_gates(self):
        goldens = views((8, 8, 24, 24))
        manifest = render_check.pin_goldens(goldens)
        report = render_check.check_goldens(goldens, manifest, goldens)
        self.assertTrue(report['pass'])
        self.assertEqual(report['flip']['schema'], flip_diff.SCHEMA)
        # same silhouette, pixel difference: the flip gate must also fail on its own
        dim = views((8, 8, 24, 24), shade=40)
        report = render_check.check_goldens(dim, manifest, goldens)
        self.assertFalse(report['flip']['pass'])
        self.assertFalse(report['pass'])
        disabled = render_check.check_goldens(dim, manifest, goldens, max_flip=None)
        self.assertNotIn('flip', disabled)

    def write(self, directory, box, **kwargs):
        for view, raw in views(box, **kwargs).items():
            (Path(directory) / (view + '.tga')).write_bytes(raw)

    def run_main(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = render_check.main(list(argv))
        return code, json.loads(out.getvalue())

    def test_cli_flip_gate_fails_when_silhouette_matches(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self.write(a, (8, 8, 24, 24))
            self.write(b, (8, 8, 24, 24), shade=40)
            code, result = self.run_main('--views', a, '--reference', b)
            self.assertEqual((code, result['valid']), (1, False))
            self.assertTrue(result['report']['views'] and not result['report']['flip']['pass'])
            code, result = self.run_main('--views', a, '--reference', b, '--max-flip', '1.0')
            self.assertEqual((code, result['valid']), (0, True))

    def test_heatmaps_must_stay_under_build(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b, \
                tempfile.TemporaryDirectory() as out:
            self.write(a, (8, 8, 24, 24))
            self.write(b, (12, 8, 28, 24))
            code, result = self.run_main('--views', a, '--reference', b, '--flip-heatmaps', out)
            self.assertEqual(code, 1)
            self.assertFalse(result['valid'])
            self.assertEqual(list(Path(out).iterdir()), [])

    def test_heatmaps_written_under_build(self):
        directory = blender_runner.BUILD_ROOT / 'flip-test-heatmaps'
        reference, candidate = views((8, 8, 24, 24)), views((12, 8, 28, 24))
        try:
            render_check.write_heatmaps(reference, candidate, directory)
            written = sorted(p.name for p in directory.iterdir())
            self.assertEqual(written, sorted('flip-%s.png' % v for v in flip_diff.VIEWS))
            image = decode_image((directory / written[0]).read_bytes())
            self.assertEqual((image.width, image.height), (SIZE, SIZE))
        finally:
            if directory.is_dir():
                for path in directory.iterdir():
                    path.unlink()
                directory.rmdir()


if __name__ == '__main__':
    unittest.main()
