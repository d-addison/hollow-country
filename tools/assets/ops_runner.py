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
    'primitive': ({'id', 'kind', 'size'}, {'segments'}),
    'boolean': ({'target', 'operand', 'mode'}, set()),
    'bevel': ({'target', 'width', 'segments'}, set()),
    'array': ({'target', 'count', 'offset'}, set()),
    'mirror': ({'target', 'axis'}, set()),
    'transform': ({'target', 'translate', 'rotate', 'scale'}, set()),
    'uv-unwrap': ({'target'}, set()),
    'material-slot': ({'target', 'texture', 'material'}, set()),
    'named-selection': ({'target', 'name'}, set()),
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
    objects, selections, points = {}, set(), set()
    for op in ops:
        if not isinstance(op, dict) or op.get('op') not in SCHEMAS:
            raise ValueError('recipe.unknown_op')
        required, optional = SCHEMAS[op['op']]
        if not required <= op.keys() or set(op) - required - optional != {'op'}:
            raise ValueError('recipe.op_fields')
        kind = op['op']
        if 'target' in op and op['target'] not in objects:
            raise ValueError('recipe.target_missing')
        if kind == 'primitive':
            ident = name(op['id'])
            if ident in objects or op['kind'] not in {'box', 'cylinder', 'sphere'}:
                raise ValueError('recipe.primitive')
            vector(op['size'], 0.00001, 1000)
            segments = integer(op.get('segments', 16), 3, 64)
            objects[ident] = 8 if op['kind'] == 'box' else segments * segments * 2
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
        elif kind in {'named-selection', 'memory-point'}:
            names = selections if kind == 'named-selection' else points
            ident = name(op['name'])
            if ident in names:
                raise ValueError('recipe.duplicate_name')
            names.add(ident)
            if kind == 'memory-point':
                vector(op['position'])
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
