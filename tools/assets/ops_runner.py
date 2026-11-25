"""Closed, bounded ops.v1 recipes. Coordinates are Blender metres (Z up).

The subprocess exports canonical DayZ axes (X right, Y up, Z forward) by
(x,y,z)->(x,z,-y), a rotation preserving winding. No arbitrary scripts/paths.
CLI validates only; use blender_runner.build for execution.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import re

from tools.assets.provenance import load_json
from tools.assets.mlod import virtual_path

MAX_OPS = 128
MAX_ELEMENTS = 60000
SCHEMAS = {
    'primitive': ({'id', 'kind', 'size'}, {'segments', 'top_radius'}),
    'boolean': ({'target', 'operand', 'mode'}, set()),
    'bevel': ({'target', 'width', 'segments'}, set()),
    'array': ({'target', 'count', 'offset'}, set()),
    'mirror': ({'target', 'axis'}, set()),
    'transform': ({'target', 'translate', 'rotate', 'scale'}, set()),
    'uv-unwrap': ({'target'}, set()),
    'material-slot': ({'target', 'texture', 'material'}, {'selection'}),
    'named-selection': ({'target', 'name'}, {'faces'}),
    'lathe': ({'id', 'profile', 'segments', 'closed'}, set()),
    'tube': ({'id', 'points', 'radius', 'segments'}, set()),
    'smooth-shading': ({'target', 'enabled', 'sharp_angle'}, set()),
    'memory-point': ({'name', 'position'}, set()),
    'proxy': ({'model', 'position', 'rotation', 'instance'}, set()),
}


def number(value, low=-10000, high=10000):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('recipe.number_out_of_range')
    return value


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('recipe.integer_out_of_range')
    return value


def vector(value, low=-10000, high=10000):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError('recipe.vector')
    return tuple(number(v, low, high) for v in value)


def name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,62}', value):
        raise ValueError('recipe.name')
    return value


def _validate(recipe):
    if (not isinstance(recipe, dict) or set(recipe) != {'schema', 'name', 'ops'}
            or recipe['schema'] != 'ops.v1'):
        raise ValueError('recipe.schema')
    name(recipe['name'])
    ops = recipe['ops']
    if not isinstance(ops, list) or not 1 <= len(ops) <= MAX_OPS:
        raise ValueError('recipe.op_limit')
    objects, selections, points = {}, {}, set()
    face_selected = set()
    for op in ops:
        if not isinstance(op, dict) or op.get('op') not in SCHEMAS:
            raise ValueError('recipe.unknown_op')
        required, optional = SCHEMAS[op['op']]
        if not required <= op.keys() or set(op) - required - optional != {'op'}:
            raise ValueError('recipe.op_fields')
        kind = op['op']
        if 'target' in op and op['target'] not in objects:
            raise ValueError('recipe.target_missing')
        if kind in {'boolean', 'bevel', 'array', 'mirror'} and op['target'] in face_selected:
            raise ValueError('recipe.topology_after_face_selection')
        if kind == 'boolean' and op['operand'] in face_selected:
            raise ValueError('recipe.topology_after_face_selection')
        if kind == 'primitive':
            ident = name(op['id'])
            if ident in objects or op['kind'] not in {'box', 'cylinder', 'sphere', 'cone'}:
                raise ValueError('recipe.primitive')
            vector(op['size'], 0.00001, 1000)
            segments = integer(op.get('segments', 16), 3, 64)
            if op['kind'] == 'cone':
                number(op.get('top_radius', 0), 0, 1)
            elif 'top_radius' in op:
                raise ValueError('recipe.top_radius_only_cone')
            objects[ident] = 8 if op['kind'] == 'box' else segments * segments * 2
        elif kind in {'lathe', 'tube'}:
            ident = name(op['id'])
            if ident in objects:
                raise ValueError('recipe.duplicate_object')
            segments = integer(op['segments'], 3, 64)
            rows = op['profile'] if kind == 'lathe' else op['points']
            if not isinstance(rows, list) or not 2 <= len(rows) <= 128:
                raise ValueError('recipe.profile_limit')
            if kind == 'lathe':
                if type(op['closed']) is not bool or (op['closed'] and len(rows) < 3):
                    raise ValueError('recipe.profile_closed')
                for row in rows:
                    if not isinstance(row, list) or len(row) != 2:
                        raise ValueError('recipe.profile_pair')
                    number(row[0], 0.00001, 1000)
                    number(row[1])
                pairs = list(zip(rows, rows[1:]))
                if op['closed']:
                    pairs.append((rows[-1], rows[0]))
            else:
                number(op['radius'], 0.00001, 100)
                for row in rows:
                    vector(row)
                pairs = list(zip(rows, rows[1:]))
                directions = [tuple(b[i]-a[i] for i in range(3)) for a, b in pairs]
                for a, b in zip(directions, directions[1:]):
                    if math.hypot(*a) and math.hypot(*b):
                        cosine = sum(x*y for x, y in zip(a, b))/math.hypot(*a)/math.hypot(*b)
                        if cosine < -0.999:
                            raise ValueError('recipe.tube_reversal')
            if any(math.dist(a, b) < 0.000001 for a, b in pairs):
                raise ValueError('recipe.zero_length_segment')
            objects[ident] = 4 * len(rows) * segments
        elif kind == 'smooth-shading':
            if type(op['enabled']) is not bool:
                raise ValueError('recipe.shading_bool')
            number(op['sharp_angle'], 0, 180)
        elif kind == 'boolean':
            if (op['operand'] not in objects or op['operand'] == op['target']
                    or op['mode'] not in {'UNION', 'DIFFERENCE', 'INTERSECT'}):
                raise ValueError('recipe.boolean')
            objects[op['target']] = (objects[op['target']] + objects.pop(op['operand'])) * 4
        elif kind == 'bevel':
            number(op['width'], 0.000001, 100)
            segments = integer(op['segments'], 1, 8)
            objects[op['target']] *= 6 * segments
        elif kind == 'array':
            objects[op['target']] *= integer(op['count'], 1, 32)
            vector(op['offset'])
        elif kind == 'mirror':
            if op['axis'] not in {'X', 'Y', 'Z'}:
                raise ValueError('recipe.axis')
            objects[op['target']] *= 2
        elif kind == 'transform':
            vector(op['translate'])
            vector(op['rotate'], -360, 360)
            vector(op['scale'], 0.00001, 1000)
        elif kind == 'material-slot':
            virtual_path(op['texture'])
            virtual_path(op['material'])
            if 'selection' in op and selections.get(op['selection']) != op['target']:
                raise ValueError('recipe.material_selection')
        elif kind in {'named-selection', 'memory-point'}:
            names = selections if kind == 'named-selection' else points
            ident = name(op['name'])
            if ident in names:
                raise ValueError('recipe.duplicate_name')
            if kind == 'memory-point':
                names.add(ident)
                vector(op['position'])
            else:
                names[ident] = op['target']
                if 'faces' in op:
                    faces = op['faces']
                    if not isinstance(faces, list) or not 1 <= len(faces) <= MAX_ELEMENTS:
                        raise ValueError('recipe.face_selection_limit')
                    for face in faces:
                        integer(face, 0, min(MAX_ELEMENTS, objects[op['target']]) - 1)
                    if len(set(faces)) != len(faces):
                        raise ValueError('recipe.duplicate_face')
                    face_selected.add(op['target'])
        elif kind == 'proxy':
            virtual_path(op['model'])
            if not op['model'].lower().endswith('.p3d'):
                raise ValueError('recipe.proxy_model')
            vector(op['position'])
            vector(op['rotation'], -360, 360)
            integer(op['instance'], 1, 999)
        if sum(objects.values()) > MAX_ELEMENTS:
            raise ValueError('recipe.expansion_limit')
    if not objects:
        raise ValueError('recipe.no_mesh')
    return copy.deepcopy(recipe)


def validate(recipe):
    """Refuse malformed JSON values with a stable ValueError, never a traceback."""
    try:
        return _validate(recipe)
    except (TypeError, KeyError, OverflowError, RecursionError):
        raise ValueError('recipe.invalid_value') from None


def script_arguments(recipe_path, output_path, *, render=False):
    """Only paths are passed as argv; recipe data is never interpolated as code."""
    return ['--recipe', str(recipe_path), '--output', str(output_path)] + (['--render'] if render else [])


def selftest():
    validate({'schema': 'ops.v1', 'name': 'test', 'ops': [
        {'op': 'primitive', 'id': 'cube', 'kind': 'box', 'size': [1, 1, 1]}]})
    try:
        validate({'schema': 'ops.v1', 'name': 'test', 'ops': [{'op': 'python'}]})
    except ValueError:
        return
    raise AssertionError('unknown op admitted')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe', nargs='?', type=Path)
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args()
    if args.selftest:
        selftest()
    elif args.recipe:
        try:
            validate(load_json(args.recipe.read_bytes()))
        except (OSError, ValueError):
            print(json.dumps({'valid': False, 'reason': 'recipe.invalid_or_unreadable'}))
            return 1
    else:
        parser.error('recipe or --selftest required')
    print(json.dumps({'valid': True}))


if __name__ == '__main__':
    raise SystemExit(main())
