"""Index PBO header names only; never extract or cache installed asset contents."""
import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.package.pbo import VERS, WORDS, addon_prefix, original_addon_name

DEFAULT_CACHE = Path.home() / '.cache/hollow-country/texture-index.json'
DEFAULT_ADDONS = Path('/mnt/g/SteamLibrary/steamapps/common/DayZ/Addons')
SCHEMA = 1
MAX_HEADER = 64 * 1024 * 1024
MAX_ENTRIES = 500000


def canonical(name):
    return '/'.join(part for part in name.replace('\\', '/').split('/') if part).casefold()


def pbo_names(path):
    """Read the name/property table only, including compressed-entry names.

    File data and trailer are never read. Bound strings/count/total header bytes;
    reject truncated tables and unsafe names rather than publishing a partial index.
    """
    with Path(path).open('rb') as stream:
        def cstring():
            data = bytearray()
            while len(data) < 4096 and stream.tell() < MAX_HEADER:
                char = stream.read(1)
                if not char:
                    raise ValueError('truncated PBO header string')
                if char == b'\0':
                    return data.decode('utf-8', errors='strict')
                data.extend(char)
            raise ValueError('oversize PBO header string')

        names, prefix, payload_size = [], None, 0
        for index in range(MAX_ENTRIES):
            name = cstring()
            raw = stream.read(WORDS.size)
            if len(raw) != WORDS.size:
                raise ValueError('truncated PBO header entry')
            method, _, _, _, size = WORDS.unpack(raw)
            if not name and method == VERS and index == 0:
                while True:
                    key = cstring()
                    if not key:
                        break
                    value = cstring()
                    if key.casefold() == 'prefix':
                        prefix = value
                continue
            if not name:
                if any(WORDS.unpack(raw)):
                    raise ValueError('invalid PBO header terminator')
                break
            names.append(name)
            payload_size += size
        else:
            raise ValueError('too many PBO entries')
        if stream.tell() + payload_size > Path(path).stat().st_size:
            raise ValueError('PBO payload shorter than declared sizes')
    # Old archives without a prefix conventionally mount under the archive stem.
    # Keep that fallback explicit in the cache metadata; it needs native resolution.
    mount = prefix if prefix is not None else Path(path).stem
    result = set()
    for name in names:
        joined = canonical(mount + '/' + name)
        if any(part in ('.', '..', '') for part in joined.split('/')) or ':' in joined:
            raise ValueError('unsafe PBO virtual name')
        result.add(joined)
    return result, prefix is None


def local_files(root):
    """Map authored virtual names to packer eligibility using its actual prefix policy."""
    result = {}
    for addon in sorted((Path(root) / 'mods').iterdir()) if (Path(root) / 'mods').is_dir() else ():
        if not addon.is_dir():
            continue
        prefix = addon_prefix(addon)
        for path in sorted(addon.rglob('*')):
            if path.is_file() and not path.is_symlink() and path.name != '$PBOPREFIX$':
                relative = path.relative_to(addon).as_posix()
                result[canonical(prefix + '/' + relative)] = original_addon_name(relative)
    return result


def build_index(directories, cache=DEFAULT_CACHE):
    archives = []
    for directory in directories:
        directory = Path(directory)
        if not directory.is_dir():
            raise ValueError('PBO directory unavailable (check --addons/--extra)')
        archives.extend(p for p in directory.iterdir() if p.is_file() and p.suffix.casefold() == '.pbo')
    if not archives:
        raise ValueError('no PBO archives found')
    names, sources = set(), []
    for path in sorted(set(archives)):
        before = path.stat()
        try:
            entries, fallback = pbo_names(path)
        except ValueError as error:
            raise ValueError(f'{path.name}: {error}') from error
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError(f'{path.name}: archive changed during indexing; retry')
        names.update(entries)
        # Basenames and fingerprints only: no user/profile or install paths in cache.
        sources.append({'archive': path.name, 'size': after.st_size,
                        'mtime_ns': after.st_mtime_ns, 'stem_prefix_assumed': fallback})
    data = {'schema': SCHEMA, 'sources': sources, 'names': sorted(names)}
    cache = Path(cache).expanduser()
    cache.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache.with_suffix(cache.suffix + '.tmp')
    temporary.write_text(json.dumps(data, sort_keys=True) + '\n', encoding='utf-8')
    temporary.replace(cache)
    return data


def load_index(cache=DEFAULT_CACHE):
    data = json.loads(Path(cache).expanduser().read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or data.get('schema') != SCHEMA or not isinstance(data.get('sources'), list)
            or not data['sources'] or not isinstance(data.get('names'), list)
            or not all(isinstance(name, str) and name == canonical(name) for name in data['names'])):
        raise ValueError('unsupported or invalid texture index; rebuild it')
    return set(data['names'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--addons', type=Path, default=DEFAULT_ADDONS)
    parser.add_argument('--extra', type=Path, action='append', default=[], help='optional additional PBO directory, e.g. DayZ Tools dta')
    parser.add_argument('--cache', type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args(argv)
    try:
        data = build_index([args.addons, *args.extra], args.cache)
    except (OSError, ValueError) as error:
        # Do not echo OS errors containing private filesystem paths.
        reason = f'I/O errno={error.errno}; check directory/cache permissions' if isinstance(error, OSError) else str(error)
        print(f'texture_index: failed: {reason}', file=sys.stderr)
        return 1
    print(f'texture_index: archives={len(data["sources"])} names={len(data["names"])} '
          f'assumed_prefixes={sum(s["stem_prefix_assumed"] for s in data["sources"])}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
