"""Generate a local engine symbol index; no engine source is copied to the repo.

Run python3 -B -m tools.validate.native_symbols. The source-content hash also
includes the parser so parser changes invalidate an otherwise current index.
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

from tools.validate import enforce_source as es

DEFAULT_SCRIPTS = Path('~/.cache/hollow-country/native-scripts/scripts-1.30.164289')
DEFAULT_OUTPUT = Path('~/.cache/hollow-country/native-symbols-1.30.json')
SCHEMA = 1


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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--native-scripts', type=Path, default=DEFAULT_SCRIPTS)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        symbols = load(args.native_scripts, args.output)
    except (OSError, ValueError):
        parser.exit(1, 'native_symbols: cannot read scripts or write the local symbol cache\n')
    print(f"native_symbols: classes={len(symbols['classes'])} source_hash={symbols['source_hash']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
