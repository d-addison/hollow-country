"""Generate a local engine symbol index; no engine source is copied to the repo.

Run python3 -B -m tools.validate.native_symbols. The source-content hash also
includes the parser so parser changes invalidate an otherwise current index.

``--emit-names-index`` writes the committed vanilla names index
(tools/validate/data/vanilla_names_<build>.json): a symbol table of class,
parent, method, field and enum names only. It holds no code body, comment or
string literal, and ``validate_names_index`` refuses to write or load one that
does. Workers without the native cache use it through ``resolve``.
"""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from tools.validate import dayz_build
from tools.validate import enforce_source as es

DEFAULT_SCRIPTS = dayz_build.native_scripts_dir()
DEFAULT_OUTPUT = dayz_build.symbols_cache_path()
SCHEMA = 1
BUILD = dayz_build.pinned()
NAMES_INDEX = dayz_build.names_index_path()
NAMES_SCHEMA = 1
NAMES_KIND = 'vanilla-script-names'


def load(scripts=DEFAULT_SCRIPTS, output=DEFAULT_OUTPUT, allow_uncached=False):
    """Load or atomically regenerate the index when any source content changes.

    Keep separate class bodies: merging modded bodies across script layers
    would let lower-layer callers incorrectly see higher-layer methods.
    """
    scripts, output = Path(scripts).expanduser(), Path(output).expanduser()
    if not (scripts / '3_Game').is_dir():
        raise ValueError('native scripts cache is missing 3_Game')
    digest = hashlib.sha256()
    digest.update(Path(es.__file__).read_bytes())
    digest.update(Path(__file__).read_bytes())
    inputs = []
    for layer in es.LAYERS:
        for path in sorted((scripts / layer).rglob('*.c')):
            data = path.read_bytes()
            digest.update(path.relative_to(scripts).as_posix().encode())
            digest.update(b'\0')
            digest.update(data)
            digest.update(b'\0')
            inputs.append((path, data))
    source_hash = digest.hexdigest()
    try:
        cached = json.loads(output.read_text(encoding='utf-8'))
        if (isinstance(cached, dict) and cached.get('schema') == SCHEMA
                and cached.get('source_hash') == source_hash
                and isinstance(cached.get('classes'), dict)
                and isinstance(cached.get('types'), dict)):
            return cached
    except (OSError, ValueError):
        pass
    classes, types = {}, {str(i): set() for i in range(len(es.LAYERS))}
    for path, data in inputs:
        source = es.Source(path, data.decode('utf-8', errors='replace'))
        # Preserve the existing native-name census, including enums/typedefs
        # that the structural model intentionally does not fully interpret.
        types[str(source.layer)].update(re.findall(
            r'^\s*(?:modded\s+|sealed\s+)*(?:class|enum)\s+(\w+)', source.code, re.M))
        types[str(source.layer)].update(source.typedefs)
        types[str(source.layer)].update(
            re.findall(r'\benum\s+(\w+)', source.code))
        signatures = source.signatures
        for definition in source.classes:
            methods = sorted({s.name for s in signatures
                              if definition.body_start < s.offset < definition.body_end})
            classes.setdefault(definition.name, []).append({
                'parent': definition.base, 'modded': definition.modded,
                'layer': source.layer, 'methods': methods,
                'fields': {f.name: f.type for f in definition.fields},
            })
    result = {'schema': SCHEMA, 'source_hash': source_hash, 'classes': classes,
              'types': {layer: sorted(names) for layer, names in types.items()}}
    temporary = None
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent,
                                         prefix=output.name + '.', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(result, stream, sort_keys=True, separators=(',', ':'))
            stream.write('\n')
        os.replace(temporary, output)
    except OSError as exc:
        if not allow_uncached or exc.errno not in {errno.EROFS, errno.EACCES, errno.EPERM}:
            raise
        print('native_symbols: cache is read-only; using the generated in-memory index', file=sys.stderr)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return result


# ------------------------------------------------------------ names-only index

_IDENT = re.compile(r'~?[A-Za-z_]\w*\Z')
# A type is identifiers joined by template punctuation, never a number, quote or operator.
_TYPE = re.compile(r'(?:(?:out|inout) )?[A-Za-z_][\w ,<>~]*\Z')
_NUMBER_TOKEN = re.compile(r'(?<!\w)\d')
_QUALIFIERS = frozenset({'out', 'inout', 'notnull', 'const', 'ref', 'autoptr', 'owned', 'reference', 'local'})
_ENTRY_KEYS = frozenset({'parent', 'modded', 'layer', 'methods', 'fields'})
_TOP_KEYS = frozenset({'schema', 'kind', 'game_build', 'source_hash', 'layers', 'classes', 'enums', 'types',
                       'globals'})
_MAX_NAME = 200


class NamesIndexError(ValueError):
    """The names index would hold a body, comment, literal or anything but names."""


def _script_files(scripts):
    scripts = Path(scripts).expanduser()
    if not (scripts / '3_Game').is_dir():
        raise ValueError('native scripts cache is missing 3_Game')
    return [(layer, path) for layer in es.LAYERS for path in sorted((scripts / layer).rglob('*.c'))]


def _parameter_types(params):
    """Parameter types only (an ``out ``/``inout `` prefix kept); names and defaults are dropped."""
    result = []
    for part in es.split_parameters(params):
        part = part.split('=')[0].strip()
        words = re.findall(r'[A-Za-z_]\w*(?:\s*<[^()]*>)?', part)
        flags = []
        while len(words) > 1 and words[0] in _QUALIFIERS:
            word = words.pop(0)
            if word in {'out', 'inout'}:
                flags.append(word)
        if words and words[0] != 'void':
            result.append(' '.join(flags + [re.sub(r'\s+', ' ', re.sub(r'\s*([<>,])\s*', r'\1', words[0]))]))
    return result


def build_names_index(scripts):
    """The deterministic names-only index of every ``.c`` under the five script layers."""
    digest = hashlib.sha256()
    classes, enums, types, globals_ = {}, {}, {str(i): set() for i in range(len(es.LAYERS))}, {}
    for layer, path in _script_files(scripts):
        data = path.read_bytes()
        digest.update(path.relative_to(Path(scripts).expanduser()).as_posix().encode() + b'\0' + data + b'\0')
        source = es.Source(path, data.decode('utf-8', errors='replace'))
        key = str(source.layer)
        types[key].update(re.findall(r'^\s*(?:modded\s+|sealed\s+)*(?:class|enum)\s+(\w+)', source.code, re.M))
        types[key].update(source.typedefs)
        types[key].update(re.findall(r'\benum\s+(\w+)', source.code))
        enums.setdefault(key, set()).update(re.findall(r'\benum\s+(\w+)', source.code))
        signatures = source.signatures
        for definition in source.classes:
            methods = {(s.name, ' '.join(sorted(s.modifiers)), tuple(_parameter_types(s.params)))
                       for s in signatures if definition.body_start < s.offset < definition.body_end}
            classes.setdefault(definition.name, []).append({
                'parent': definition.base, 'modded': definition.modded, 'layer': source.layer,
                'methods': [[n, m, list(p)] for n, m, p in sorted(methods)],
                'fields': {f.name: f.type for f in definition.fields},
            })
        for signature in signatures:
            if not any(c.body_start < signature.offset < c.body_end for c in source.classes):
                globals_.setdefault(signature.name, set()).add((' '.join(sorted(signature.modifiers)),
                                                               source.layer))
    doc = {'schema': NAMES_SCHEMA, 'kind': NAMES_KIND, 'game_build': BUILD, 'source_hash': digest.hexdigest(),
           'layers': list(es.LAYERS), 'classes': classes,
           'enums': {k: sorted(v) for k, v in sorted(enums.items())},
           'types': {k: sorted(v) for k, v in types.items()},
           'globals': {name: [[m, layer] for m, layer in sorted(rows)] for name, rows in sorted(globals_.items())}}
    validate_names_index(doc)
    return doc


def _name(value, what, pattern=_IDENT):
    if (not isinstance(value, str) or len(value) > _MAX_NAME or not pattern.match(value)
            or _NUMBER_TOKEN.search(value)):
        raise NamesIndexError('names index %s is not a plain name or type' % what)
    return value


def validate_names_index(doc):
    """Refuse anything that is not a name: a body, comment, literal or unknown field fails."""
    if not isinstance(doc, dict) or set(doc) != _TOP_KEYS:
        raise NamesIndexError('names index has unexpected top-level fields')
    if doc['schema'] != NAMES_SCHEMA or doc['kind'] != NAMES_KIND or doc['game_build'] != BUILD:
        raise NamesIndexError('names index schema, kind or build is not the supported one')
    if not (isinstance(doc['source_hash'], str) and re.fullmatch(r'[0-9a-f]{64}', doc['source_hash'])):
        raise NamesIndexError('names index source hash is not a sha256')
    if doc['layers'] != list(es.LAYERS):
        raise NamesIndexError('names index layers differ from the script layers')
    layers = range(len(es.LAYERS))
    for name, entries in doc['classes'].items():
        _name(name, 'class name')
        if not isinstance(entries, list):
            raise NamesIndexError('names index class entries must be a list')
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS:
                raise NamesIndexError('names index class entry has unexpected fields: ' + name)
            if entry['parent']:
                _name(entry['parent'], 'parent name')
            if type(entry['modded']) is not bool or entry['layer'] not in layers:
                raise NamesIndexError('names index class flags are invalid: ' + name)
            for row in entry['methods']:
                if not (isinstance(row, list) and len(row) == 3 and isinstance(row[2], list)):
                    raise NamesIndexError('names index method row is not [name, modifiers, parameter types]')
                _name(row[0], 'method name')
                if not set(row[1].split()) <= es.MODIFIERS or not isinstance(row[1], str):
                    raise NamesIndexError('names index method modifiers are not engine modifiers')
                for kind in row[2]:
                    _name(kind, 'parameter type', _TYPE)
            for field_name, field_type in entry['fields'].items():
                _name(field_name, 'field name')
                _name(field_type, 'field type', _TYPE)
    for group in ('enums', 'types'):
        for layer, names in doc[group].items():
            if layer not in {str(i) for i in layers} or not isinstance(names, list):
                raise NamesIndexError('names index %s layer is invalid' % group)
            for name in names:
                _name(name, group + ' name')
    for name, rows in doc['globals'].items():
        _name(name, 'global function name')
        for row in rows:
            if not (isinstance(row, list) and len(row) == 2 and row[1] in layers
                    and isinstance(row[0], str) and set(row[0].split()) <= es.MODIFIERS):
                raise NamesIndexError('names index global row is invalid: ' + name)
    return doc


def dump_names_index(doc):
    """Sorted, compact and newline-terminated: the same input is always the same bytes."""
    return json.dumps(doc, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n'


def load_names_index(path=NAMES_INDEX):
    try:
        doc = json.loads(Path(path).read_text(encoding='utf-8'))
    except OSError as exc:
        raise NamesIndexError('committed names index is unreadable: ' + type(exc).__name__)
    except ValueError:
        raise NamesIndexError('committed names index is not valid JSON')
    return validate_names_index(doc)


def symbols_from_names_index(doc):
    """The same shape as ``load`` (classes, types) plus ``global_functions`` (proto/native only)."""
    classes = {}
    for name, entries in doc['classes'].items():
        classes[name] = [{'parent': e['parent'], 'modded': e['modded'], 'layer': e['layer'],
                          'methods': sorted({row[0] for row in e['methods']}), 'fields': dict(e['fields'])}
                         for e in entries]
    natives = {}
    for name, rows in doc['globals'].items():
        for modifiers, layer in rows:
            if set(modifiers.split()) & {'proto', 'native'}:
                natives.setdefault(name, set()).add(layer)
    return {'schema': SCHEMA, 'source_hash': doc['source_hash'], 'classes': classes,
            'types': {layer: list(names) for layer, names in doc['types'].items()},
            'global_functions': natives, 'origin': 'names-index'}


def resolve(scripts, allow_uncached=True, names_path=NAMES_INDEX):
    """(symbols, origin): the local native cache when present, else the committed names index.

    Origin is ``cache`` or ``names-index``, so a run that used the fallback says so."""
    if (Path(scripts).expanduser() / '3_Game').is_dir():
        return load(scripts, allow_uncached=allow_uncached), 'cache'
    return symbols_from_names_index(load_names_index(names_path)), 'names-index'


def check_names_index(scripts, names_path=NAMES_INDEX):
    """(status, reason) for the committed index against a fresh generation from the cache."""
    if not (Path(scripts).expanduser() / '3_Game').is_dir():
        return 'SKIP', 'needs-host-check: native scripts cache unavailable; committed names index not compared'
    try:
        committed = Path(names_path).read_text(encoding='utf-8')
    except OSError:
        return 'FAIL', 'committed names index missing; run python3 -B -m tools.validate.native_symbols --emit-names-index'
    try:
        fresh = dump_names_index(build_names_index(scripts))
    except ValueError as exc:
        return 'FAIL', 'fresh names index refused: ' + str(exc)
    if fresh != committed:
        return 'FAIL', 'committed names index differs from the cache; run python3 -B -m tools.validate.native_symbols --emit-names-index'
    return 'PASS', 'committed names index matches the native scripts cache'


def emit_names_index(scripts, output=NAMES_INDEX):
    """Validate, then atomically write the index; a refused index never touches the file."""
    text = dump_names_index(build_names_index(scripts))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent,
                                         prefix=output.name + '.', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.chmod(temporary, 0o644)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return len(text.encode('utf-8'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--native-scripts', type=Path, default=DEFAULT_SCRIPTS)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--emit-names-index', action='store_true',
                        help='write the committed names-only vanilla index and exit')
    parser.add_argument('--names-output', type=Path, default=NAMES_INDEX)
    parser.add_argument('--check-names-index', action='store_true',
                        help='compare the committed names index with a fresh generation')
    args = parser.parse_args(argv)
    if args.emit_names_index or args.check_names_index:
        if args.check_names_index:
            status, reason = check_names_index(args.native_scripts, args.names_output)
            print('native_symbols: names-index %s %s' % (status, reason))
            return 0 if status == 'PASS' else 1
        try:
            size = emit_names_index(args.native_scripts, args.names_output)
        except ValueError as exc:
            parser.exit(1, 'native_symbols: ' + str(exc) + '\n')
        print('native_symbols: names-index written bytes=%d' % size)
        return 0
    try:
        symbols = load(args.native_scripts, args.output)
    except (OSError, ValueError):
        parser.exit(1, 'native_symbols: cannot read scripts or write the local symbol cache\n')
    print(f"native_symbols: classes={len(symbols['classes'])} source_hash={symbols['source_hash']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
