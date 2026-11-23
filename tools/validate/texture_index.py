"""Index PBO header names, plus imageset member names; never cache installed asset contents.

Texture paths come from the PBO name tables only. Imagesets are plain text and the
engine resolves `set:<set> image:<member>` against them, so the index also records,
per imageset, the member name list read in memory from stored (method 0) imageset
entries. Nothing else in a payload is read, and only the names are cached.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.package.pbo import TEST_PREFIX, VERS, WORDS, addon_prefix, original_addon_name

DEFAULT_CACHE = Path.home() / '.cache/hollow-country/texture-index.json'
DEFAULT_ADDONS = Path('/mnt/g/SteamLibrary/steamapps/common/DayZ/Addons')
DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / 'setup/workshop_mods.json'
DEFAULT_WORKSHOP = DEFAULT_ADDONS.parents[2] / 'workshop/content/221100'
SCHEMA = 2
MAX_HEADER = 64 * 1024 * 1024
MAX_ENTRIES = 500000


def canonical(name):
    return '/'.join(part for part in name.replace('\\', '/').split('/') if part).casefold()


def _read_table(path):
    """Return ([(name, method, size)], prefix, payload_start) of one PBO header.

    File data and trailer are never read. Bound strings/count/total header bytes;
    reject truncated tables rather than publishing a partial index.
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

        entries, prefix, payload_size = [], None, 0
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
            entries.append((name, method, size))
            payload_size += size
        else:
            raise ValueError('too many PBO entries')
        start = stream.tell()
        if start + payload_size > Path(path).stat().st_size:
            raise ValueError('PBO payload shorter than declared sizes')
    return entries, prefix, start


def pbo_names(path):
    """Read the name/property table only, including compressed-entry names."""
    entries, prefix, _ = _read_table(path)
    # Old archives without a prefix conventionally mount under the archive stem.
    # Keep that fallback explicit in the cache metadata; it needs native resolution.
    mount = prefix if prefix is not None else Path(path).stem
    result = set()
    for name, _, _ in entries:
        joined = canonical(mount + '/' + name)
        if any(part in ('.', '..', '') for part in joined.split('/')) or ':' in joined:
            raise ValueError('unsafe PBO virtual name')
        result.add(joined)
    return result, prefix is None


# `set:<name>` resolves against an imageset's own top-level Name; members are the
# Name of each image definition. Anchored to the definition blocks so the texture
# list and any other Name-like text are never mistaken for members.
_SET_NAME = re.compile(r'\A\s*ImageSetClass\s*\{\s*Name\s+"([^"\r\n]+)"')
_MEMBER_NAME = re.compile(r'ImageSetDefClass\s+\S+\s*\{\s*Name\s+"([^"\r\n]+)"')
MAX_IMAGESET = 4 * 1024 * 1024


def parse_imageset(text):
    """Return (set name, member names) of one imageset text, or None when it is not one."""
    head = _SET_NAME.match(text.lstrip('\ufeff'))
    if not head:
        return None
    return head[1], set(_MEMBER_NAME.findall(text))


def pbo_imagesets(path):
    """Return {set name: {member names}} from the stored imageset entries of one PBO.

    Only entries named *.imageset with a stored (method 0) payload are read, bounded in
    size; compressed or oversize imagesets are skipped, so their sets stay unresolved
    (an error for any reference) rather than being guessed.
    """
    entries, _, start = _read_table(path)
    result, position = {}, start
    with Path(path).open('rb') as stream:
        for name, method, size in entries:
            if name.casefold().endswith('.imageset') and method == 0 and 0 < size <= MAX_IMAGESET:
                stream.seek(position)
                data = stream.read(size)
                if len(data) == size:
                    parsed = parse_imageset(data.decode('utf-8', errors='replace'))
                    if parsed:
                        result.setdefault(parsed[0], set()).update(parsed[1])
            position += size
    return result


def lint_prefix(addon):
    """addon_prefix, plus the dev-only test addon under its own prefix.

    The test addon is never shipped, so its prefix stays out of pbo.PREFIXES (every pack and sign refuses
    it); its layouts and scripts are still linted, and their texture names resolve under that prefix."""
    marker = Path(addon) / '$PBOPREFIX$'
    if (Path(addon).name == TEST_PREFIX and marker.is_file() and not marker.is_symlink()
            and marker.stat().st_size <= 256 and marker.read_text().strip() == TEST_PREFIX):
        return TEST_PREFIX
    return addon_prefix(addon)


def local_files(root):
    """Map authored virtual names to packer eligibility using its actual prefix policy."""
    result = {}
    for addon in sorted((Path(root) / 'mods').iterdir()) if (Path(root) / 'mods').is_dir() else ():
        if not addon.is_dir():
            continue
        prefix = lint_prefix(addon)
        for path in sorted(addon.rglob('*')):
            if path.is_file() and not path.is_symlink() and path.name != '$PBOPREFIX$':
                relative = path.relative_to(addon).as_posix()
                result[canonical(prefix + '/' + relative)] = original_addon_name(relative)
    return result


def build_index(directories, cache=DEFAULT_CACHE, coverage=None, manifest=DEFAULT_MANIFEST):
    # cache=None permits an in-memory audit on read-only worker hosts.
    persist = cache is not None
    if not persist:
        cache = DEFAULT_CACHE
    # Validate before creating directories or touching either output file. Keep
    # the permitted root lexical so a symlink at that root cannot widen it.
    cache_root = DEFAULT_CACHE.parent.expanduser().absolute()
    try:
        cache = Path(cache).expanduser().resolve()
        temporary = cache.with_suffix(cache.suffix + '.tmp')
        if (not cache.is_relative_to(cache_root)
                or not temporary.resolve().is_relative_to(cache_root)):
            raise ValueError('cache output must stay under the default cache root')
    except RuntimeError:
        raise ValueError('cache output contains a symlink loop') from None
    archives = []
    for directory in directories:
        directory = Path(directory)
        if not directory.is_dir():
            raise ValueError('PBO directory unavailable (check --addons/--extra)')
        archives.extend(p for p in directory.iterdir() if p.is_file() and p.suffix.casefold() == '.pbo')
    if not archives:
        raise ValueError('no PBO archives found')
    names, sources, imagesets = set(), [], {}
    for path in sorted(set(archives)):
        before = path.stat()
        try:
            entries, fallback = pbo_names(path)
            sets = pbo_imagesets(path)
        except ValueError as error:
            raise ValueError(f'{path.name}: {error}') from error
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError(f'{path.name}: archive changed during indexing; retry')
        names.update(entries)
        for set_name, members in sets.items():
            imagesets.setdefault(set_name, set()).update(members)
        # Basenames and fingerprints only: no user/profile or install paths in cache.
        sources.append({'archive': path.name, 'size': after.st_size,
                        'mtime_ns': after.st_mtime_ns, 'stem_prefix_assumed': fallback})
    data = {'schema': SCHEMA, 'sources': sources, 'names': sorted(names),
            'imagesets': {key: sorted(value) for key, value in sorted(imagesets.items())}}
    if coverage is not None:
        mods = json.loads(Path(manifest).read_text(encoding='utf-8'))['mods']
        for item in mods:
            if item.get('publish'):
                prefix = canonical(item['folder'].lstrip('@')) + '/'
                if not any(name.startswith(prefix) for name in names):
                    raise ValueError('built PBO prefix missing for ' + item['folder'])
        data.update(coverage=coverage, manifest_sha256=manifest_digest(manifest))
    if not persist:
        return data
    cache.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation refuses existing temporary files, including symlinks,
    # without ever opening their targets for writing.
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(json.dumps(data, sort_keys=True) + '\n')
        temporary.replace(cache)
    finally:
        temporary.unlink(missing_ok=True)
    return data


def declared_directories(addons=DEFAULT_ADDONS, workshop=DEFAULT_WORKSHOP,
                         manifest=DEFAULT_MANIFEST, our_pbos=()):
    """Require every declared pack; inspect directory/header names, never payloads.

    Published HC items are our built PBOs too. Explicit build directories replace
    those installed HC items when checking a newer local bundle.
    """
    mods = json.loads(Path(manifest).read_text(encoding='utf-8'))['mods']
    directories, coverage = [Path(addons)], ['vanilla']
    # Vanilla GUI imagesets live in the sibling dta folder (gui.pbo), not in Addons.
    core = Path(addons).parent / 'dta'
    if core.is_dir() and any(p.suffix.casefold() == '.pbo' for p in core.iterdir()):
        directories.append(core)
    for item in mods:
        if item.get('publish') and our_pbos:
            continue
        item_root = Path(workshop) / item['id']
        candidates = sorted(p for p in item_root.iterdir()
                            if p.is_dir() and p.name.casefold() == 'addons') if item_root.is_dir() else []
        if len(candidates) != 1 or not any(p.suffix.casefold() == '.pbo' for p in candidates[0].iterdir()):
            raise ValueError('declared dependency unavailable: ' + item['folder'])
        directories.extend(candidates)
        coverage.append(item['folder'])
    if our_pbos:
        directories.extend(Path(p) for p in our_pbos)
        coverage.extend(item['folder'] for item in mods if item.get('publish'))
    for directory in directories:
        if not directory.is_dir() or not any(p.suffix.casefold() == '.pbo' for p in directory.iterdir()):
            raise ValueError('required PBO directory unavailable or empty')
    return directories, sorted(coverage)


def manifest_digest(manifest=DEFAULT_MANIFEST):
    return hashlib.sha256(Path(manifest).read_bytes()).hexdigest()


def load_index(cache=DEFAULT_CACHE, require_complete=False, manifest=DEFAULT_MANIFEST):
    data = json.loads(Path(cache).expanduser().read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or data.get('schema') != SCHEMA or not isinstance(data.get('sources'), list)
            or not data['sources'] or not isinstance(data.get('names'), list)
            or not all(isinstance(name, str) and name == canonical(name) for name in data['names'])):
        raise ValueError('unsupported or invalid texture index; rebuild it')
    if require_complete:
        mods = json.loads(Path(manifest).read_text(encoding='utf-8'))['mods']
        expected = sorted(['vanilla', *(item['folder'] for item in mods)])
        if data.get('coverage') != expected or data.get('manifest_sha256') != manifest_digest(manifest):
            raise ValueError('index does not cover the current dependency manifest; rebuild it')
    return set(data['names'])


def load_imagesets(cache=DEFAULT_CACHE):
    """Return {set name: set of member names}; an index without imagesets must be rebuilt."""
    data = json.loads(Path(cache).expanduser().read_text(encoding='utf-8'))
    sets = data.get('imagesets') if isinstance(data, dict) else None
    if (not isinstance(sets, dict) or not sets
            or not all(isinstance(key, str) and isinstance(value, list)
                       and all(isinstance(item, str) for item in value)
                       for key, value in sets.items())):
        raise ValueError('texture index has no imageset members; rebuild it')
    return {key: set(value) for key, value in sets.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--addons', type=Path, default=DEFAULT_ADDONS)
    parser.add_argument('--workshop', type=Path, default=DEFAULT_WORKSHOP)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--our-pbos', type=Path, action='append', default=[], help='built HC addon directories replacing published HC items')
    parser.add_argument('--extra', type=Path, action='append', default=[], help='optional additional PBO directory, e.g. DayZ Tools dta')
    parser.add_argument('--no-cache', action='store_true', help='read-only audit; do not persist the index')
    parser.add_argument('--cache', type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args(argv)
    try:
        directories, coverage = declared_directories(args.addons, args.workshop, args.manifest, args.our_pbos)
        data = build_index([*directories, *args.extra], None if args.no_cache else args.cache, coverage, args.manifest)
    except (OSError, ValueError) as error:
        # Do not echo OS errors containing private filesystem paths.
        reason = f'I/O errno={error.errno}; check directory/cache permissions' if isinstance(error, OSError) else str(error)
        print(f'texture_index: failed: {reason}', file=sys.stderr)
        return 1
    print(f'texture_index: archives={len(data["sources"])} names={len(data["names"])} '
          f'dependency_groups={len(data["coverage"])} assumed_prefixes={sum(s["stem_prefix_assumed"] for s in data["sources"])}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
