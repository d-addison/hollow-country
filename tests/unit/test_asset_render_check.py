"""Offline render_check tests on synthetic images; no Blender or GPU is used."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import os
import tempfile
import unittest

from tools.assets import render_check, visual_diff
from tools.assets.pbr_pack import Image, decode_image, encode_tga
from tools.assets.provenance import Refusal

SIZE = 16


def render(box, *, shade=200, size=SIZE, alpha=False):
    """A flat-background image with a filled rectangle (x0, y0, x1, y1)."""
    background = (0, 0, 0, 0) if alpha else (13, 13, 13, 255)
    pixels = bytearray()
    for y in range(size):
        for x in range(size):
            inside = box[0] <= x < box[2] and box[1] <= y < box[3]
            pixels += bytes((shade, shade, shade, 255)) if inside else bytes(background)
    return Image(size, size, bytes(pixels))


def views(box, **kwargs):
    return {v: encode_tga(render(box, **kwargs)) for v in render_check.VIEWS}


class SilhouetteTests(unittest.TestCase):
    def test_mask_from_corner_colour_and_alpha(self):
        for alpha in (False, True):
            width, height, mask = render_check.silhouette(render((4, 4, 12, 12), alpha=alpha))
            self.assertEqual((width, height, sum(mask)), (SIZE, SIZE, 64))

    def test_iou_values(self):
        a = render_check.silhouette(render((4, 4, 12, 12)))
        b = render_check.silhouette(render((8, 4, 16, 12)))
        self.assertEqual(render_check.iou(a, a), 1)
        self.assertAlmostEqual(render_check.iou(a, b), 32 / 96)

    def test_empty_and_mismatched_refused(self):
        empty = render_check.silhouette(render((0, 0, 0, 0)))
        with self.assertRaises(ValueError):
            render_check.iou(empty, empty)
        with self.assertRaises(ValueError):
            render_check.iou(empty, render_check.silhouette(render((0, 0, 0, 0), size=8)))
        with self.assertRaises(ValueError):
            render_check.silhouette(b'raw')

    def test_compare_pass_and_fail(self):
        same = render_check.compare_silhouettes(views((4, 4, 12, 12)), views((4, 4, 12, 12), shade=90))
        self.assertTrue(same['pass'])
        self.assertFalse(same['engine_verified'])
        self.assertEqual(set(same['views']), set(render_check.VIEWS))
        moved = render_check.compare_silhouettes(views((4, 4, 12, 12)), views((6, 4, 14, 12)))
        self.assertFalse(moved['pass'])
        self.assertTrue(render_check.compare_silhouettes(views((4, 4, 12, 12)), views((6, 4, 14, 12)),
                                                         min_iou=0.5)['pass'])
        partial = views((4, 4, 12, 12))
        del partial['top']
        for bad in (partial, {}):
            with self.assertRaises(ValueError):
                render_check.compare_silhouettes(bad, views((4, 4, 12, 12)))
        for threshold in (0, 2, True, 'x'):
            with self.assertRaises(ValueError):
                render_check.compare_silhouettes(views((4, 4, 12, 12)), views((4, 4, 12, 12)), min_iou=threshold)


class SheetAndGoldenTests(unittest.TestCase):
    def test_contact_sheet_layout_and_determinism(self):
        raw = views((4, 4, 12, 12))
        sheet = render_check.contact_sheet(raw)
        self.assertEqual(sheet, render_check.contact_sheet(raw))
        image = decode_image(sheet)
        self.assertEqual((image.width, image.height), (SIZE * 3, SIZE * 2))
        # The first tile is the front view, pixel for pixel.
        front = decode_image(raw['front'])
        self.assertEqual(image.rgba[:SIZE*4], front.rgba[:SIZE*4])
        self.assertEqual(decode_image(render_check.contact_sheet(raw, columns=6)).width, SIZE * 6)
        for bad in (0, 7, True):
            with self.assertRaises(ValueError):
                render_check.contact_sheet(raw, columns=bad)
        mixed = dict(raw, top=encode_tga(render((0, 0, 4, 4), size=8)))
        with self.assertRaises(ValueError):
            render_check.contact_sheet(mixed)

    def test_goldens_are_pinned_by_digest(self):
        goldens = views((4, 4, 12, 12))
        manifest = render_check.pin_goldens(goldens)
        report = render_check.check_goldens(goldens, manifest, goldens)
        self.assertTrue(report['pass'])
        self.assertEqual(report['pixel_diff']['schema'], 'visual-diff.v1')
        tampered = dict(goldens, front=encode_tga(render((4, 4, 12, 12), shade=10)))
        with self.assertRaises(Refusal):
            render_check.check_goldens(goldens, manifest, tampered)
        with self.assertRaises(Refusal):
            render_check.check_goldens(goldens, manifest, {k: v for k, v in goldens.items() if k != 'top'})
        for bad in ({}, {'schema': 'x', 'views': {}}, {**manifest, 'views': {**manifest['views'], 'top': 'zz'}}):
            with self.assertRaises(Refusal):
                render_check.check_goldens(goldens, bad, goldens)

    def test_golden_pixel_difference_fails_even_with_same_silhouette(self):
        goldens = views((4, 4, 12, 12))
        report = render_check.check_goldens(views((4, 4, 12, 12), shade=100),
                                            render_check.pin_goldens(goldens), goldens)
        self.assertTrue(report['pass'] is False)
        self.assertTrue(all(v == 1 for v in report['views'].values()))


class DirectoryAndCliTests(unittest.TestCase):
    def write(self, directory, box, **kwargs):
        for view, raw in views(box, **kwargs).items():
            (Path(directory) / (view + '.tga')).write_bytes(raw)

    def test_read_views_refusals(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(Refusal):
                render_check.read_views(temp)
            self.write(temp, (4, 4, 12, 12))
            self.assertEqual(set(render_check.read_views(temp)), set(render_check.VIEWS))
            (Path(temp) / 'front.png').write_bytes(b'x')
            with self.assertRaises(Refusal):
                render_check.read_views(temp)
            (Path(temp) / 'front.png').unlink()
            (Path(temp) / 'front.tga').unlink()
            os.symlink(Path(temp) / 'back.tga', Path(temp) / 'front.tga')
            with self.assertRaises(Refusal):
                render_check.read_views(temp)
            with self.assertRaises(Refusal):
                render_check.read_views(Path(temp) / 'absent')

    def run_main(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = render_check.main(list(argv))
        return code, json.loads(out.getvalue())

    def test_cli_compare_and_failure_output_is_private(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self.write(a, (4, 4, 12, 12))
            self.write(b, (4, 4, 12, 12))
            code, result = self.run_main('--views', a, '--reference', b)
            self.assertEqual((code, result['valid']), (0, True))
            self.write(b, (7, 4, 15, 12))
            code, result = self.run_main('--views', a, '--reference', b)
            self.assertEqual((code, result['valid']), (1, False))
            code, result = self.run_main('--views', str(Path(a) / 'absent'))
            self.assertEqual(code, 1)
            self.assertNotIn(a, json.dumps(result))

    def test_sheet_output_must_stay_under_build(self):
        with tempfile.TemporaryDirectory() as a:
            self.write(a, (4, 4, 12, 12))
            code, result = self.run_main('--views', a, '--sheet', str(Path(a) / 'sheet.png'))
            self.assertEqual((code, result['valid']), (1, False))
            self.assertFalse((Path(a) / 'sheet.png').exists())

    def test_selftest_and_render_delegates_to_visual_diff(self):
        code, result = self.run_main('--selftest')
        self.assertEqual((code, result), (0, {'valid': True}))
        sentinel = object()
        calls = []
        original = visual_diff.render_request
        visual_diff.render_request = lambda recipe, **kw: calls.append((recipe, kw)) or sentinel
        try:
            self.assertIs(render_check.render({'x': 1}, timeout=5), sentinel)
        finally:
            visual_diff.render_request = original
        self.assertEqual(calls, [({'x': 1}, {'config': None, 'timeout': 5})])


if __name__ == '__main__':
    unittest.main()
