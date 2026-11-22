"""Pure helpers of the Blender preview script (frame selection, sheet layout, argument parsing).

The render itself needs a real Blender run and is not covered here.
"""
import importlib.util
from pathlib import Path
import sys
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'tools/anim/blender/hc_preview.py'


def load():
    spec = importlib.util.spec_from_file_location('hc_preview_under_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PreviewHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pv = load()

    def test_imports_without_blender(self):
        self.assertNotIn('bpy', sys.modules)
        self.assertIsNone(self.pv.bpy)

    def test_strip_frames_properties(self):
        for frame_count in (1, 2, 3, 7, 30, 121, 300):
            for count in (1, 2, 3, 8, 12, 500):
                frames = self.pv.strip_frames(frame_count, count)
                self.assertEqual(frames, sorted(set(frames)))
                self.assertLessEqual(len(frames), min(count, frame_count))
                self.assertGreaterEqual(len(frames), 1)
                self.assertEqual(frames[0], 1)
                if count > 1:
                    self.assertEqual(frames[-1], frame_count)
                self.assertTrue(all(1 <= f <= frame_count for f in frames))

    def test_strip_frames_deterministic_and_even(self):
        self.assertEqual(self.pv.strip_frames(121, 8), self.pv.strip_frames(121, 8))
        frames = self.pv.strip_frames(121, 8)
        gaps = [b - a for a, b in zip(frames, frames[1:])]
        self.assertLessEqual(max(gaps) - min(gaps), 1)

    def test_strip_frames_short_clip_returns_every_frame(self):
        self.assertEqual(self.pv.strip_frames(3, 8), [1, 2, 3])
        self.assertEqual(self.pv.strip_frames(0, 8), [])

    def test_sheet_layout_holds_every_tile(self):
        for count in range(1, 30):
            columns, rows = self.pv.sheet_layout(count)
            self.assertGreaterEqual(columns * rows, count)
            self.assertLess((rows - 1) * columns, count)
            self.assertLessEqual(columns, self.pv.STRIP_COLUMNS)

    def test_tile_origins_are_unique_and_top_row_is_highest(self):
        count = 7
        columns, rows = self.pv.sheet_layout(count)
        origins = [self.pv.tile_origin(i, columns, rows, 640, 480) for i in range(count)]
        self.assertEqual(len(set(origins)), count)
        self.assertEqual(origins[0], (0, (rows - 1) * 480))
        self.assertTrue(all(0 <= x < columns * 640 and 0 <= y < rows * 480 for x, y in origins))
        self.assertEqual(origins[columns][1], origins[0][1] - 480)

    def test_parse_args_video_and_strip(self):
        self.assertEqual(self.pv.parse_args(['a.json', 'out', 'n']), ('a.json', 'out', 'n', 0))
        self.assertEqual(self.pv.parse_args(['a.json', 'out', 'n', '--strip']),
                         ('a.json', 'out', 'n', self.pv.STRIP_DEFAULT_FRAMES))
        self.assertEqual(self.pv.parse_args(['a.json', 'out', 'n', '--strip', '5']), ('a.json', 'out', 'n', 5))
        self.assertEqual(self.pv.parse_args(['--strip', '5', 'a.json', 'out', 'n']), ('a.json', 'out', 'n', 5))

    def test_parse_args_rejects_bad_input(self):
        for bad in (['a.json', 'out'], ['a.json', 'out', 'n', 'extra'], ['a.json', 'out', 'n', '--strip', '0']):
            with self.assertRaises(ValueError):
                self.pv.parse_args(bad)


if __name__ == '__main__':
    unittest.main()
