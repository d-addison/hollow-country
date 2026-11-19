"""Synthetic JsonFileLoader scalar semantics, based on native boot 057.

Constructors still supply object/array shapes for these restricted ports. JSON
loading zeroes primitive fields first, recursively; supplied keys then win.
This models neither serializer type checking nor native object allocation.
"""
import copy
from functools import lru_cache
import json
from pathlib import Path
import re
from types import SimpleNamespace


def zero_scalars(value):
    value = copy.deepcopy(value)
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return 0
    if isinstance(value, float):
        return 0.0
    if isinstance(value, str):
        return ''
    if isinstance(value, list):
        return type(value)(zero_scalars(item) for item in value)
    if hasattr(value, '__dict__'):
        for key, item in vars(value).items():
            setattr(value, key, zero_scalars(item))
    return value


def overlay(values, template=None, array_type=list, children=None):
    """Decode already parsed JSON using explicit DTO shapes, never initializers."""
    children = children or {}
    if isinstance(values, list):
        return array_type(overlay(item, template, array_type, children) for item in values)
    if isinstance(values, dict):
        result = zero_scalars(template) if template is not None else SimpleNamespace()
        for key, item in values.items():
            child = children[key]() if key in children else getattr(result, key, None)
            # Array constructors describe the container, not its element type.
            if isinstance(child, list):
                child = None
            setattr(result, key, overlay(item, child, array_type, children))
        return result
    return values


@lru_cache(maxsize=1)
def schemas():
    from tools.validate.enforce_source import mod_sources
    fields = {}
    bases = {}
    for source in mod_sources(Path(__file__).resolve().parents[2]):
        for definition in source.classes:
            fields.setdefault(definition.name, {}).update({field.name: field for field in definition.fields
                if not field.modifiers & {'static', 'const'}})
            if definition.base:
                bases[definition.name] = definition.base
    def inherited(name, seen=()):
        if name in seen:
            return {}
        result = inherited(bases[name], seen + (name,)) if name in bases else {}
        result.update(fields.get(name, {}))
        return result
    return {name: inherited(name) for name in fields}


def hydrate(values, kind, array_type=list, string_type=str, depth=0):
    """Typed native-zero DTO shape read from authored declarations, no policy."""
    if depth > 20:
        raise ValueError('synthetic DTO depth exceeded')
    schema = schemas()
    if kind.startswith(('array<', 'set<')):
        element = re.sub(r'^(?:array|set)<(?:ref)?', '', kind)[:-1]
        return array_type(hydrate(item, element, array_type, string_type, depth + 1)
                          for item in (values or []))
    if kind in {'int', 'float', 'bool', 'string', 'vector'}:
        if values is not None:
            return string_type(values) if kind == 'string' else values
        return {'int': 0, 'float': 0.0, 'bool': False, 'string': string_type(''),
                'vector': [0., 0., 0.]}[kind]
    if kind not in schema:
        return values
    if values is not None and not isinstance(values, dict):
        raise ValueError('synthetic object expected for ' + kind)
    result = SimpleNamespace()
    supplied = values or {}
    for name, field in schema[kind].items():
        field_kind = field.type
        if name in supplied or field_kind in {'int', 'float', 'bool', 'string', 'vector'} or field.initializer.startswith('new'):
            setattr(result, name, hydrate(supplied.get(name), field_kind, array_type, string_type, depth + 1))
        else:
            setattr(result, name, None)
    return result


def decode_json(text, kind, array_type=list, string_type=str):
    try:
        values = json.loads(text)
        if not isinstance(values, dict):
            return None
        return hydrate(values, kind, array_type, string_type)
    except (ValueError, TypeError):
        return None


@lru_cache(maxsize=1)
def json_fields_port():
    """Execute authored HCJsonFields; only native string operations are ports."""
    from tests.unit.test_event_runtime import translate
    from tests.unit.test_map_layers import EStr
    class Text(EStr):
        def Get(self, index): return Text(self[index])
        def __getitem__(self, index): return Text(super().__getitem__(index))
        def Substring(self, start, length): return Text(self[start:start + length])
        def ToAscii(self): return ord(self)
        def HexToInt(self): return int(self, 16)
    source = (Path(__file__).resolve().parents[2] /
              'mods/HollowCountry/scripts/3_Game/HCSettings.c').read_text()
    api = SimpleNamespace()
    env = dict(HCJsonFields=api)
    for name in ('KeyMatches', 'Check', 'Has', 'Every'):
        fn = translate(source, name, env, 'HCJsonFields')
        if name in ('Check', 'Every'):
            fn.__defaults__ = ('',)  # Syntax-only Enforce optional argument.
        setattr(api, name, lambda *args, fn=fn: fn(*(Text(arg) if isinstance(arg, str) else arg for arg in args)))
    return api
