"""Probe tooling checks only; native timing and binding remain unverified."""
from pathlib import Path
import tempfile
import unittest
from xml.etree.ElementTree import Element, SubElement, tostring

from tools.setup import interiors_query_probe as probe
from tools.setup import probe_runtime


def positions():
    root = Element('map')
    for index, name in enumerate(probe.CLASSES):
        SubElement(root, 'group', name=name, pos=f'{100 + index} 25.125 200')
    return tostring(root)


class QueryProbeTests(unittest.TestCase):
    def test_selects_all_classes_and_refuses_missing_or_invalid_origins(self):
        rows = probe.select_targets(positions())
        self.assertEqual([row['building_class'] for row in rows], list(probe.CLASSES))
        for data in (b'<map/>', positions().replace(b'25.125', b'nan'),
                     b'<!DOCTYPE map><map/>'):
            with self.subTest(data=data[:20]), self.assertRaises(ValueError):
                probe.select_targets(data)
        with self.assertRaises(ValueError):
            probe.select_targets(positions(), instances=2)

    def test_generated_hook_passes_shared_syntax_checks_and_binds_inputs(self):
        targets = probe.select_targets(positions())
        hook = probe.render_hook(targets)
        self.assertEqual(probe_runtime.lint_hook(hook, explicit_numbers=True), [])
        self.assertNotEqual(hook, probe.render_hook(targets, samples=2))
        self.assertNotEqual(hook, probe.render_hook(targets, legacy_first=True))
        for invalid in (0, True, 999):
            with self.assertRaises(ValueError):
                probe.render_hook(targets, samples=invalid)

    def test_generation_replaces_unique_factory_and_requires_installed_apis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            game = root / '3_Game/Global/Game.c'
            game.parent.mkdir(parents=True)
            game.write_text('GetObjectsAtPosition( GetObjectsAtPosition3D(')
            init = b'Mission CreateCustomMission(string path) { return new CustomMission(); }'
            result = probe.generate(init, positions(), root)
            self.assertIn(b'return new HCInteriorQueryProbeMission();', result)
            with self.assertRaises(ValueError):
                probe.generate(init + init, positions(), root)
            game.write_text('')
            with self.assertRaises(ValueError):
                probe.generate(init, positions(), root)
