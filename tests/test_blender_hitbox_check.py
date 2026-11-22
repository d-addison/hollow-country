"""Synthetic fixtures only. Blender itself is not available to unit tests: the bpy side is
exercised on the host; here the request builder, the policy and the runner plumbing are
tested with generated boxes and a patched executor."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.assets import blender_runner, mlod
from tools.validate import blender_hitbox_check as check
from tests.test_p3d_firegeom_audit import box_lod, component, FIRE, VIEW


def model_bytes(visual=None, fire=None):
    visual = box_lod() if visual is None else visual
    fire = box_lod(selections=component()) if fire is None else fire
    return mlod.write_mlod(mlod.Asset({1.: visual, FIRE: fire, VIEW: box_lod()}, physical=False))


def measure_for(request, shift=(0., 0., 0.)):
    """What Blender would measure, computed here from the request's own points."""
    def bounds(points):
        return [[min(p[i] for p in points) for i in range(3)],
                [max(p[i] for p in points) for i in range(3)]]
    visual = bounds(request['visual']['vertices'])
    components = {}
    for name, spec in request['components'].items():
        box = bounds(spec['vertices'])
        box = [[box[0][i] + shift[i] for i in range(3)], [box[1][i] + shift[i] for i in range(3)]]
        components[name] = {'bbox': box, 'distance_to_visual': 0.0}
    return {'schema': check.MEASURE, 'blender': [5, 2, 4], 'visual': {'bbox': visual}, 'components': components}


class RequestTests(unittest.TestCase):
    def test_request_has_visual_and_components(self):
        request = check.build_request(model_bytes())
        self.assertEqual(request['schema'], check.REQUEST)
        self.assertEqual(len(request['visual']['vertices']), 8)
        self.assertEqual(sorted(request['components']), ['Component01'])
        self.assertEqual(len(request['components']['Component01']['faces']), 6)
        json.dumps(request, allow_nan=False)

    def test_missing_lods_and_empty_visual(self):
        no_fire = mlod.write_mlod(mlod.Asset({1.: box_lod(), VIEW: box_lod()}, physical=False))
        with self.assertRaises(ValueError):
            check.build_request(no_fire)
        no_visual = mlod.write_mlod(mlod.Asset({FIRE: box_lod(selections=component()), VIEW: box_lod()}, physical=False))
        with self.assertRaises(ValueError):
            check.build_request(no_visual)

    def test_garbage_is_refused(self):
        with self.assertRaises(ValueError):
            check.build_request(b'not a model')


class PolicyTests(unittest.TestCase):
    def evaluate(self, **kwargs):
        request = check.build_request(model_bytes(**kwargs))
        return check.evaluate(measure_for(request))

    def test_matching_component_passes(self):
        self.assertEqual(self.evaluate(), [])

    def test_component_outside_visual_bounds(self):
        request = check.build_request(model_bytes())
        findings = check.evaluate(measure_for(request, shift=(3., 0., 0.)))
        self.assertIn('BH001', [f['id'] for f in findings])

    def test_small_overhang_within_tolerance_passes(self):
        request = check.build_request(model_bytes())
        self.assertEqual(check.evaluate(measure_for(request, shift=(0.02, 0., 0.))), [])

    def test_small_component_misses_coverage(self):
        findings = self.evaluate(fire=box_lod(low=(0., 0., 0.), high=(0.1, 0.1, 0.1), selections=component()))
        self.assertIn('BH002', [f['id'] for f in findings])

    def test_flat_and_detached_components(self):
        request = check.build_request(model_bytes())
        measure = measure_for(request)
        measure['components']['Component01'].update(bbox=[[0., 0., 0.], [1., 1., 0.]], distance_to_visual=9.0)
        ids = [f['id'] for f in check.evaluate(measure)]
        self.assertIn('BH003', ids)
        self.assertIn('BH004', ids)

    def test_no_components_and_degenerate_visual(self):
        measure = {'visual': {'bbox': [[0, 0, 0], [1, 1, 1]]}, 'components': {}}
        self.assertEqual([f['id'] for f in check.evaluate(measure)], ['BH005'])
        measure = {'visual': {'bbox': [[0, 0, 0], [1, 1, 0]]},
                   'components': {'C': {'bbox': [[0, 0, 0], [1, 1, 1]], 'distance_to_visual': 0.0}}}
        self.assertEqual([f['id'] for f in check.evaluate(measure)], ['BH005'])

    def test_report_never_claims_engine_verification(self):
        request = check.build_request(model_bytes())
        report = check.check_measure(measure_for(request))
        self.assertTrue(report['valid'])
        self.assertFalse(report['engine_verified'])


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        (self.base / 'mods').mkdir()

    def write(self, name, data):
        (self.base / 'mods' / name).write_bytes(data)

    def test_runner_results_are_reported_per_model(self):
        self.write('good.p3d', model_bytes())
        self.write('bad.p3d', model_bytes(fire=box_lod(low=(0., 0., 0.), high=(.1, .1, .1), selections=component())))
        self.write('broken.p3d', b'junk')
        report = check.check_paths(['mods'], base=self.base, runner=lambda r: measure_for(r))
        by_name = {r['model']: r for r in report['results']}
        self.assertEqual(sorted(by_name), ['mods/bad.p3d', 'mods/broken.p3d', 'mods/good.p3d'])
        self.assertTrue(by_name['mods/good.p3d']['valid'])
        self.assertFalse(by_name['mods/bad.p3d']['valid'])
        self.assertEqual(by_name['mods/broken.p3d']['findings'][0]['id'], 'BH005')
        self.assertFalse(report['valid'])

    def test_no_models_is_a_visible_note(self):
        report = check.check_paths(['mods'], base=self.base, runner=lambda r: {})
        self.assertTrue(report['valid'])
        self.assertIn('nothing to check', report['note'])

    def test_outside_repo_and_symlink_refused(self):
        from tools.validate import p3d_firegeom_audit as audit
        with tempfile.TemporaryDirectory() as other:
            with self.assertRaises(audit.AuditRefusal):
                check.check_paths([other], base=self.base, runner=lambda r: {})
        (self.base / 'link').symlink_to(self.base / 'mods')
        with self.assertRaises(audit.AuditRefusal):
            check.check_paths(['link'], base=self.base, runner=lambda r: {})


class HostTests(unittest.TestCase):
    def run_main(self, *argv, env=None):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env or {}), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = check.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_missing_blender_exits_needs_host_check(self):
        with mock.patch.dict(os.environ, {'HC_BLENDER': ''}), \
                mock.patch.object(blender_runner.shutil, 'which', return_value=None):
            code, out, err = self.run_main()
        self.assertEqual(code, 3)
        self.assertTrue(err.startswith('needs-host-check: blender.not_found'))
        self.assertEqual(json.loads(out)['status'], 'needs-host-check')

    def test_host_failures_are_needs_host_check_but_model_failures_are_not(self):
        with mock.patch.object(blender_runner, 'locate', return_value=Path('/x/blender')), \
                mock.patch.object(check, 'check_paths', side_effect=blender_runner.BlenderRefusal('blender.timeout')):
            self.assertEqual(self.run_main()[0], 3)
        with mock.patch.object(blender_runner, 'locate', return_value=Path('/x/blender')), \
                mock.patch.object(check, 'check_paths', side_effect=blender_runner.BlenderRefusal('blender.failed')):
            self.assertEqual(self.run_main()[0], 1)

    def test_run_blender_plumbing_with_patched_executor(self):
        request = check.build_request(model_bytes())
        seen = {}

        def fake_execute(executable, script, arguments, directory, timeout):
            seen['args'] = list(arguments)
            seen['script'] = Path(script).read_text(encoding='utf-8')
            Path(arguments[arguments.index('--output') + 1]).write_text(
                json.dumps(measure_for(request)), encoding='utf-8')
        with mock.patch.object(blender_runner, 'locate', return_value=Path('/x/blender')), \
                mock.patch.object(blender_runner, '_execute', side_effect=fake_execute):
            measure = check.run_blender(request)
        self.assertEqual(measure['schema'], check.MEASURE)
        self.assertEqual(seen['args'][0], '--recipe')
        self.assertIn('def blender_measure', seen['script'])

    def test_bad_child_output_is_refused(self):
        request = check.build_request(model_bytes())

        def fake_execute(executable, script, arguments, directory, timeout):
            Path(arguments[arguments.index('--output') + 1]).write_text('{"schema": "x"}', encoding='utf-8')
        with mock.patch.object(blender_runner, 'locate', return_value=Path('/x/blender')), \
                mock.patch.object(blender_runner, '_execute', side_effect=fake_execute):
            with self.assertRaises(blender_runner.BlenderRefusal):
                check.run_blender(request)

    def test_module_import_does_not_need_bpy(self):
        self.assertFalse(hasattr(check, 'bpy'))


if __name__ == '__main__':
    unittest.main()
