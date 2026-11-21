"""Deterministic manifest check of a staged or signed mod folder before it reaches players (#153 WP-1).

Run ``python3 -B -m tools.validate.package_manifest --mod <dir> --kind base|expansionai [--signed]
[--vdf <file>]``. Exit 0 when nothing is wrong, 1 otherwise; one line per finding then one summary line.

The expected PBO names and Workshop ids come from the packaging code (``workshop_publish.ITEMS`` and
``WORKSHOP_IDS``, mapped to ``pbo.PREFIXES``), not a list kept here. Each finding has a stable code:
missing_pbo, missing_signature, missing_key, missing_mod_cpp, missing_meta_cpp, wrong_publishedid,
missing_mod_tag. Details use folder-relative names only, never absolute paths.

This proves the folder layout and launcher metadata only. It does not verify PBO contents, signature
validity or any DayZ/launcher behaviour; those stay with the DayZ Tools signing step and client checks.
"""
import argparse
from collections import namedtuple
from pathlib import Path
import re

from tools.package import pbo, weapon_pack_guards, workshop_publish

KINDS = {'base': 'base', 'expansionai': 'addon'}  # CLI kind -> workshop_publish item
Finding = namedtuple('Finding', 'code detail')
MAX_TEXT = 64 * 1024
_VDF_PAIR = re.compile(r'"([^"]+)"\s+"([^"]*)"')


def expected_spec(kind):
    """Expected PBO names, their packaging prefixes and the Workshop id of one mod kind."""
    if kind not in KINDS:
        raise ValueError('unknown kind %r; choose from %s' % (kind, ', '.join(sorted(KINDS))))
    item = KINDS[kind]
    entry = workshop_publish.item_spec(item)
    names = (entry['pbo'],) + tuple(entry['extra_pbos'])
    # The guard PBO's file name is not its lowercased prefix; the guard packer owns it.
    by_name = {(weapon_pack_guards.PBO_NAME if prefix == pbo.GUARD_PREFIX else prefix.lower() + '.pbo'): prefix
               for prefix in pbo.PREFIXES}
    unknown = [n for n in names if n not in by_name]
    if unknown:
        raise ValueError('publish tool names a PBO without a packaging prefix: %s' % ', '.join(unknown))
    return {'kind': kind, 'pbos': names, 'prefixes': {n: by_name[n] for n in names},
            'published_id': workshop_publish.WORKSHOP_IDS[item]}


def published_id(text):
    """The publishedid in meta.cpp text, or None."""
    match = workshop_publish.PUBLISHED.search(text)
    return int(match.group(1)) if match else None


def _listing(folder):
    """casefolded name -> real name of the regular files directly inside folder (empty when absent)."""
    try:
        return {p.name.casefold(): p.name for p in Path(folder).iterdir() if p.is_file()}
    except OSError:
        return {}


def _nonempty(folder, name):
    try:
        return (Path(folder) / name).stat().st_size > 0
    except OSError:
        return False


def _read(path):
    try:
        with open(path, 'rb') as f:
            return f.read(MAX_TEXT).decode('utf-8-sig', 'replace')
    except OSError:
        return None


def check(mod, spec, signed=False, vdf=None):
    """Findings for the mod folder ``mod``; an empty list means the manifest is complete."""
    mod = Path(mod)
    expected_id = spec['published_id']
    found = []
    addons, keys = mod / 'addons', mod / 'keys'
    addon_files = _listing(addons)
    for name in spec['pbos']:
        real = addon_files.get(name.casefold())
        if real is None or not _nonempty(addons, real):
            found.append(Finding('missing_pbo', 'addons/' + name))
    if signed:
        key_names = set()
        for name in spec['pbos']:
            pattern = re.compile(re.escape(name) + r'\.(.+)\.bisign$', re.IGNORECASE)
            signs = [(m.group(1), real) for real in addon_files.values()
                     for m in [pattern.match(real)] if m and _nonempty(addons, real)]
            if not signs:
                found.append(Finding('missing_signature', 'addons/' + name + ' has no .bisign'))
            key_names.update(key for key, _ in signs)
        bikeys = {n[:-len('.bikey')].casefold() for n in _listing(keys).values()
                  if n.lower().endswith('.bikey') and _nonempty(keys, n)}
        if not bikeys:
            found.append(Finding('missing_key', 'keys/*.bikey'))
        else:
            for key in sorted(key_names):
                if key.casefold() not in bikeys:
                    found.append(Finding('missing_key', 'keys/%s.bikey' % key))
    top = _listing(mod)
    if 'mod.cpp' not in top or not _nonempty(mod, top['mod.cpp']):
        found.append(Finding('missing_mod_cpp', 'mod.cpp'))
    if 'meta.cpp' not in top or not _nonempty(mod, top['meta.cpp']):
        found.append(Finding('missing_meta_cpp', 'meta.cpp'))
    else:
        actual = published_id(_read(mod / top['meta.cpp']) or '')
        if actual != expected_id:
            found.append(Finding('wrong_publishedid', 'meta.cpp publishedid %s, expected %d'
                                 % ('absent' if actual is None else actual, expected_id)))
    if vdf is not None:
        found.extend(_check_vdf(vdf, expected_id))
    return found


def _check_vdf(vdf, expected_id):
    text = _read(vdf)
    if text is None:
        return [Finding('missing_mod_tag', 'workshop vdf unreadable')]
    pairs = dict((k.lower(), v) for k, v in _VDF_PAIR.findall(text))
    found = []
    tags = [t.strip().casefold() for t in pairs.get('tags', '').split(',')]
    if 'mod' not in tags:
        found.append(Finding('missing_mod_tag', 'workshop vdf tags %r lack "Mod"' % pairs.get('tags', '')))
    item = pairs.get('publishedfileid', '')
    # 0 is the first-upload placeholder; any other id must be this mod's own.
    if item.isdigit() and int(item) not in (0, expected_id):
        found.append(Finding('wrong_publishedid', 'workshop vdf publishedfileid %s, expected %d'
                             % (item, expected_id)))
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--mod', type=Path, required=True, help='staged or signed mod folder (@HollowCountry style)')
    parser.add_argument('--kind', choices=sorted(KINDS), required=True)
    parser.add_argument('--signed', action='store_true', help='also require one .bisign per PBO and the .bikey')
    parser.add_argument('--vdf', type=Path, help='workshop_item.vdf to check for the Mod tag and item id')
    args = parser.parse_args(argv)
    spec = expected_spec(args.kind)
    found = check(args.mod, spec, signed=args.signed, vdf=args.vdf)
    for f in found:
        print('%s: %s' % (f.code, f.detail))
    mode = 'signed' if args.signed else 'unsigned'
    if found:
        print('package_manifest: FAIL kind=%s mode=%s findings=%d codes=%s'
              % (args.kind, mode, len(found), ','.join(sorted({f.code for f in found}))))
        return 1
    print('package_manifest: OK kind=%s mode=%s pbos=%d' % (args.kind, mode, len(spec['pbos'])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
