"""Closed op contracts only; no Blender process or Enforce translation."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.assets import blender_ops_script, ops_runner


def recipe(*ops):
    return {'schema': 'ops.v1', 'name': 'test', 'ops': list(ops)}


def lathe(**changes):
    return dict({'op': 'lathe', 'id': 'rim', 'profile': [[.04, 0], [.05, .01], [.04, .02]],
                 'segments': 16, 'closed': True}, **changes)


def tube(**changes):
    return dict({'op': 'tube', 'id': 'wire', 'points': [[0, 0, 0], [0, 0, .1]],
                 'radius': .002, 'segments': 8}, **changes)


class LanternOpsTests(unittest.TestCase):
    def test_recipes_and_new_ops_are_valid_without_blender(self):
        for path in Path('assets_src/lantern').glob('*.ops.json'):
            with self.subTest(recipe=path.name):
                ops_runner.validate(json.loads(path.read_text()))
        ops_runner.validate(recipe(lathe(), tube(),
            {'op': 'primitive', 'id': 'flame', 'kind': 'cone', 'size': [.01, .01, .02], 'top_radius': 0}))

    def test_profiles_refuse_bad_shapes_and_caps(self):
        bad = [lathe(profile=[]), lathe(profile=[[1, 2, 3]]*3), lathe(profile=[[0, 0], [1, 1]]),
               lathe(profile=[[1, 0]]*3), lathe(profile=[[1, 0], [1, 1]], closed=True),
               lathe(profile=[[1, 0], [1, 1]], closed='yes'), lathe(segments=65),
               lathe(profile=[[1, float('nan')], [1, 1]]), lathe(segments=True),
               lathe(profile=[[1, i] for i in range(129)]), tube(radius=0), tube(radius=True),
               tube(points=[[0, 0, 0]]*2), tube(points=[[0, 0, 0], [1, 0, 0], [0, 0, 0]]),
               tube(points=[[0, 0, 0], [1, 0, float('inf')]]), tube(segments=2),
               tube(points=[[0, 0, 0]]*129)]
        for operation in bad:
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                ops_runner.validate(recipe(operation))

    def test_new_ops_share_global_expansion_and_op_caps(self):
        data = recipe(lathe(profile=[[1, i] for i in range(128)], segments=64, closed=False))
        ops_runner.validate(data)
        data['ops'].append(tube(points=[[i, 0, 0] for i in range(128)], segments=64))
        with self.assertRaisesRegex(ValueError, 'expansion_limit'):
            ops_runner.validate(data)
        with self.assertRaisesRegex(ValueError, 'op_limit'):
            ops_runner.validate(recipe(*([tube()] * 129)))

    def test_face_selection_and_shading_contract(self):
        data = recipe(lathe(), {'op': 'named-selection', 'target': 'rim', 'name': 'upper', 'faces': [0, 1]},
                      {'op': 'material-slot', 'target': 'rim', 'selection': 'upper',
                       'texture': '', 'material': 'DZ\\data\\data\\default.rvmat'},
                      {'op': 'smooth-shading', 'target': 'rim', 'enabled': True, 'sharp_angle': 40})
        ops_runner.validate(data)
        for index, field, value in [(1, 'faces', []), (1, 'faces', [True]), (1, 'faces', [-1]),
                                    (1, 'faces', [0, 0]), (1, 'faces', [60000]),
                                    (2, 'selection', 'missing'), (3, 'enabled', 1),
                                    (3, 'sharp_angle', 181)]:
            bad = copy.deepcopy(data);bad['ops'][index][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                ops_runner.validate(bad)
        for op in [{'op': 'mirror', 'target': 'rim', 'axis': 'X'},
                   {'op': 'bevel', 'target': 'rim', 'width': .01, 'segments': 1}]:
            with self.assertRaisesRegex(ValueError, 'topology_after_face_selection'):
                ops_runner.validate({**data, 'ops': data['ops']+[op]})

    def test_cone_ratio_and_closed_fields(self):
        base = {'op': 'primitive', 'id': 'cone', 'kind': 'cone', 'size': [1, 1, 1]}
        for change in [{'top_radius': -1}, {'top_radius': 2}, {'top_radius': True}, {'code': 'exec'}]:
            with self.assertRaises(ValueError): ops_runner.validate(recipe(dict(base, **change)))
        with self.assertRaises(ValueError):
            ops_runner.validate(recipe(dict(base, kind='box', top_radius=.5)))
        with self.assertRaises(ValueError): ops_runner.validate(recipe(lathe(), lathe()))

    def test_blender_exact_patch_version_refused_before_scene_access(self):
        for version in [(5, 2, 3), (5, 2, 5), (5, 3, 0)]:
            with patch.dict(sys.modules, {'bpy': SimpleNamespace(app=SimpleNamespace(version=version)),
                                         'mathutils': SimpleNamespace(Vector=object)}):
                with self.assertRaisesRegex(ValueError, 'requires_5_2_4'):
                    blender_ops_script.execute(recipe(lathe()), Path('unused.json'))
