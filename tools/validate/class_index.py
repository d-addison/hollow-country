"""Build the class-name index of vanilla plus every declared Workshop dependency.

Only class names, parent names and the declared ``scope`` of the direct children of the
object/ammo config roots are read from each installed PBO's ``config.bin``/``config.cpp``
(``tools.audit.pbo_config``); no other config value, file or asset is read or stored. The
index is written under the approved cache and is never committed. It is static file
evidence of which classes the installed stack declares, never proof of engine behaviour.
Coverage is exact: an archive whose config cannot be decoded is recorded as unreadable and
makes the index incomplete, so a consumer never treats absence as proof without it.

Without the installed game, ``main`` falls back to the committed vanilla script names index
(``tools.validate.native_symbols``, names only): it lists script class names and parents, not
config classes, so it writes no cache and never counts as config coverage.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.audit import pbo_config
from tools.validate import native_symbols, texture_index

SCHEMA = 1
CONFIG_ROOTS = ('CfgVehicles', 'CfgWeapons', 'CfgMagazines', 'CfgAmmo')
DEFAULT_CACHE = Path.home() / '.cache/hollow-country/class-index.json'
DEFAULT_ADDONS = texture_index.DEFAULT_ADDONS
DEFAULT_WORKSHOP = texture_index.DEFAULT_WORKSHOP
DEFAULT_MANIFEST = texture_index.DEFAULT_MANIFEST
VANILLA = 'vanilla'


def manifest_dependencies(manifest=DEFAULT_MANIFEST):
    """Declared dependency rows in load order; our own published items are repository sources."""
    mods = json.loads(Path(manifest).read_text(encoding='utf-8'))['mods']
    return sorted((m for m in mods if m.get('id') and not m.get('publish')), key=lambda m: m['rank'])


def manifest_digest(manifest=DEFAULT_MANIFEST):
    return hashlib.sha256(Path(manifest).read_bytes()).hexdigest()


def addon_directory(item_root):
    """The single ``addons`` folder of an installed item (the casing differs between items)."""
    candidates = sorted(p for p in Path(item_root).iterdir()
                        if p.is_dir() and p.name.casefold() == 'addons') if Path(item_root).is_dir() else []
    return candidates[0] if len(candidates) == 1 else None


def read_archive(path, roots=CONFIG_ROOTS):
    """Merged ``{root: {class: {parent, scope}}}`` of every config member of one PBO."""
    merged = {root: {} for root in roots}
    for _member, classes in pbo_config.read_config_members(path, roots):
        for root, rows in classes.items():
            for name, row in rows.items():
                merge_row(merged[root], name, row)
    return merged


def merge_row(rows, name, row):
    """Later declarations refine earlier ones; an absent scope or parent never erases a known one."""
    key = name.lower()
    previous = rows.get(key)
    parent = (row.get('parent') or '').lower() or None
    scope = row.get('scope')
    if previous is None:
        rows[key] = {'name': name, 'parent': parent, 'scope': scope}
        return
    if parent:
        previous['parent'] = parent
    if scope is not None:
        previous['scope'] = scope


def build_index(sources, roots=CONFIG_ROOTS, manifest=None):
    """``sources`` is ``[(source_id, [pbo paths])]`` in load order (vanilla first)."""
    classes = {root: {} for root in roots}
    origin = {}
    report = []
    for source_id, archives in sources:
        unreadable, readable = [], 0
        for path in sorted(archives):
            try:
                parsed = read_archive(path, roots)
            except (ValueError, OSError) as error:
                unreadable.append({'archive': Path(path).name, 'reason': str(error)})
                continue
            readable += 1
            for root, rows in parsed.items():
                for key, row in rows.items():
                    merge_row(classes[root], row['name'], row)
                    origin.setdefault((root, key), source_id)
        report.append({'id': source_id, 'archives': readable, 'unreadable': unreadable})
    out = {'schema': SCHEMA, 'roots': list(roots), 'sources': report,
           'coverage': [s['id'] for s in report if s['archives'] and not s['unreadable']],
           'classes': {root: {row['name']: {'parent': row['parent'], 'scope': row['scope'],
                                            'source': origin[(root, key)]}
                              for key, row in sorted(rows.items())}
                       for root, rows in classes.items()}}
    if manifest is not None:
        out['manifest_sha256'] = manifest_digest(manifest)
    return out


def vanilla_sources(addons=DEFAULT_ADDONS):
    """The base ``Addons`` folder plus every DLC folder of the same install (``<install>/<dlc>/addons``).

    DLC content (e.g. the Nasdara and Sakhal packs) is part of the stock install and declares
    object classes that the base folder lacks, so it is its own source id (``vanilla:<dlc>``).
    Folders whose name starts with ``!`` are tool/Workshop containers, not content."""
    addons = Path(addons)
    base = sorted(p for p in addons.iterdir() if p.suffix.casefold() == '.pbo') if addons.is_dir() else []
    if not base:
        raise ValueError('no vanilla PBO archives found')
    sources = [(VANILLA, base)]
    for dlc in sorted(p for p in addons.parent.iterdir() if p.is_dir() and not p.name.startswith('!')):
        directory = addon_directory(dlc)
        pbos = sorted(p for p in directory.iterdir() if p.suffix.casefold() == '.pbo') if directory else []
        if pbos and dlc.resolve() != addons.resolve():
            sources.append((VANILLA + ':' + dlc.name.casefold(), pbos))
    return sources


def declared_sources(addons=DEFAULT_ADDONS, workshop=DEFAULT_WORKSHOP, manifest=DEFAULT_MANIFEST):
    """Vanilla (base and DLC) plus every declared dependency's Addons; an unavailable pack is an error."""
    sources = vanilla_sources(addons)
    for item in manifest_dependencies(manifest):
        directory = addon_directory(Path(workshop) / str(item['id']))
        pbos = sorted(p for p in directory.iterdir() if p.suffix.casefold() == '.pbo') if directory else []
        if not pbos:
            raise ValueError('declared dependency unavailable: ' + item['folder'])
        sources.append((str(item['id']), pbos))
    return sources


def script_class_names(names_path=native_symbols.NAMES_INDEX):
    """``{script class: parent}`` of the ordinary (not modded) vanilla script classes, names only."""
    doc = native_symbols.load_names_index(names_path)
    rows = {}
    for name, entries in sorted(doc['classes'].items()):
        for entry in entries:
            if not entry['modded']:
                rows.setdefault(name, entry['parent'] or None)
    return rows


def write_index(data, cache=DEFAULT_CACHE):
    cache = Path(cache).expanduser().resolve()
    if not cache.is_relative_to(DEFAULT_CACHE.parent.expanduser().resolve()):
        raise ValueError('cache output must stay under the default cache root')
    cache.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache.with_suffix(cache.suffix + '.tmp')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(json.dumps(data, sort_keys=True) + '\n')
        temporary.replace(cache)
    finally:
        temporary.unlink(missing_ok=True)


def load_rows(doc, roots):
    """Validate a stored index and return ``{root: {name: row}}`` for the requested roots."""
    if (not isinstance(doc, dict) or doc.get('schema') != SCHEMA or not isinstance(doc.get('classes'), dict)
            or not isinstance(doc.get('coverage'), list)):
        raise ValueError('unsupported or invalid class index; rebuild it')
    out = {}
    for root in roots:
        rows = doc['classes'].get(root)
        if rows is None:
            continue
        if not isinstance(rows, dict) or not all(isinstance(v, dict) for v in rows.values()):
            raise ValueError('invalid class index root: ' + root)
        out[root] = {name: {'parent': row.get('parent'), 'scope': row.get('scope')}
                     for name, row in rows.items()}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--addons', type=Path, default=DEFAULT_ADDONS)
    parser.add_argument('--workshop', type=Path, default=DEFAULT_WORKSHOP)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--cache', type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args(argv)
    if not args.addons.is_dir() or not any(p.suffix.casefold() == '.pbo' for p in args.addons.iterdir()):
        try:
            rows = script_class_names()
        except ValueError as error:
            print('class_index: ' + str(error), file=sys.stderr)
            return 1
        print(f'class_index: names-index script classes={len(rows)}; vanilla Addons unavailable, '
              'config class cache not written (script names only, not config coverage)')
        return 0
    try:
        data = build_index(declared_sources(args.addons, args.workshop, args.manifest), manifest=args.manifest)
        write_index(data, args.cache)
    except (ValueError, OSError) as error:
        print('class_index: ' + str(error), file=sys.stderr)
        return 1
    for source in data['sources']:
        print(f"{source['id']}: archives={source['archives']} unreadable={len(source['unreadable'])}")
    print('classes: ' + ', '.join(f'{root}={len(rows)}' for root, rows in data['classes'].items()))
    incomplete = [s['id'] for s in data['sources'] if s['unreadable']]
    if incomplete:
        print('class_index: incomplete coverage for ' + ', '.join(incomplete), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
