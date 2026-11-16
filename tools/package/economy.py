"""Minimal native CE deltas, isolated installation and byte-exact rollback.

Generate reads installed stock. Install/rollback target an explicitly chosen
stopped, private mission copy, never the Steam installation. No placement edits.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

INPUTS = ('cfgeconomycore.xml', 'db/types.xml', 'cfglimitsdefinition.xml',
          'mapgroupproto.xml', 'mapgrouppos.xml')
LOG_NAMES = {'log_ce_lootspawn', 'log_ce_lootcleanup', 'log_ce_lootrespawn',
             'log_ce_statistics', 'log_missionfilewarning', 'log_hivewarning'}
DELTA_FILES = {'ce/types.xml', 'cfgeconomycore.append.xml', 'core-defaults.patch.json',
               'economy-report.json', 'delta-manifest.json'}
MANAGED = 'hollow-country'


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def child(root, name):
    root = Path(root).absolute()
    if name.startswith('/') or '\\' in name or ':' in name or any(p in {'', '.', '..'} for p in name.split('/')):
        raise ValueError('unsafe mission path')
    path = root / name
    for p in (path, *path.parents):
        if p.is_symlink():
            raise ValueError('symlinks forbidden')
    return path


def xml(data, tag):
    if len(data) > 16 * 1024 * 1024 or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('unsupported XML declarations or size')
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise ValueError('malformed XML') from e
    if root.tag != tag:
        raise ValueError(f'expected XML root {tag}')
    return root


def snapshot(source):
    return {name: child(source, name).read_bytes() for name in INPUTS}


def _unique(nodes, attribute='name'):
    result = {}
    for n in nodes:
        name = n.get(attribute)
        if not name or name in result:
            raise ValueError('missing/duplicate named XML element')
        result[name] = n
    return result


def _validate_profile(profile):
    if (not isinstance(profile, dict) or set(profile) != {'schema', 'name', 'add_usage', 'diagnostics'}
            or type(profile['schema']) is not int or profile['schema'] != 1
            or not isinstance(profile['name'], str)
            or not re.fullmatch(r'[a-z0-9-]{1,64}', profile['name'])
            or not isinstance(profile['add_usage'], dict)
            or not isinstance(profile['diagnostics'], list)):
        raise ValueError('unsupported profile schema/fields')
    if any(not isinstance(s, str) or s not in LOG_NAMES for s in profile['diagnostics']):
        raise ValueError('unsupported diagnostic default')
    if len(set(profile['diagnostics'])) != len(profile['diagnostics']):
        raise ValueError('duplicate diagnostic')


def _validate_budget(item):
    values = {}
    for field in ('nominal', 'min', 'lifetime', 'restock', 'cost'):
        elements = item.findall(field)
        if len(elements) != 1 or not re.fullmatch(r'[0-9]+', elements[0].text or ''):
            raise ValueError('targeted stock type has invalid/missing budget')
        values[field] = int(elements[0].text)
    for field in ('quantmin', 'quantmax'):
        nodes = item.findall(field)
        if len(nodes) != 1 or not re.fullmatch(r'-?[0-9]+', nodes[0].text or '') or not -1 <= int(nodes[0].text) <= 100:
            raise ValueError('invalid stock quantity bounds')
    if int(item.findtext('quantmin')) > int(item.findtext('quantmax')):
        raise ValueError('stock quantity minimum exceeds maximum')
    if values['min'] > values['nominal']:
        raise ValueError('targeted stock minimum exceeds nominal')
    flags = item.findall('flags')
    required = {'count_in_cargo', 'count_in_hoarder', 'count_in_map', 'count_in_player', 'crafted', 'deloot'}
    if len(flags) != 1 or set(flags[0].attrib) != required or any(v not in {'0', '1'} for v in flags[0].attrib.values()):
        raise ValueError('targeted stock flags must be complete and binary')


def generate(source, profile):
    _validate_profile(profile)
    data = snapshot(source)
    core = xml(data['cfgeconomycore.xml'], 'economycore')
    # Stock-only generator refuses to silently merge another operator's overrides.
    if core.findall('ce'):
        raise ValueError('existing CE extensions need explicit operator reconciliation')
    types = _unique(xml(data['db/types.xml'], 'types').findall('type'))
    vocabulary = _unique(xml(data['cfglimitsdefinition.xml'], 'lists').findall('./usageflags/usage'))
    defaults = _unique(core.findall('./defaults/default'))
    for name in profile['diagnostics']:
        if name not in defaults or defaults[name].get('value') not in {'true', 'false'}:
            raise ValueError(f'diagnostic default unavailable: {name}')
    out = ET.Element('types')
    routes = []
    for name, added in sorted(profile['add_usage'].items()):
        if (not isinstance(name, str) or name not in types or not isinstance(added, list)
                or not added or any(not isinstance(u, str) or u not in vocabulary for u in added)
                or len(set(added)) != len(added)):
            raise ValueError(f'invalid item/usage policy: {name}')
        item = types[name]
        _validate_budget(item)
        old = [n.get('name') for n in item.findall('usage')]
        if not old or any(u not in vocabulary for u in old) or len(set(old)) != len(old):
            raise ValueError('source usage requires explicit reconciliation')
        new = sorted(set(old) | set(added))
        if new != sorted(old):
            dest = copy.deepcopy(item)
            positions = [i for i, n in enumerate(dest) if n.tag == 'usage']
            first = positions[0]
            for n in list(dest):
                if n.tag == 'usage':
                    dest.remove(n)
            for index, u in enumerate(new):
                dest.insert(first + index, ET.Element('usage', {'name': u}))
            out.append(dest)
        routes.append({'item': name, 'stock_usage': old, 'candidate_usage': new,
                       'rates_flags_categories_tags_tiers': 'copied-exact-stock-runtime-semantics-pending',
                       'observed_acquisition_routes': None})
    fragment = ET.Element('economycore')
    if len(out):
        ce = ET.SubElement(fragment, 'ce', {'folder': MANAGED + '/ce'})
        ET.SubElement(ce, 'file', {'name': 'types.xml', 'type': 'types'})
    proto = _unique(xml(data['mapgroupproto.xml'], 'prototype').findall('group'))
    placed = xml(data['mapgrouppos.xml'], 'map')
    placements = {}
    for g in placed.findall('group'):
        placements[g.get('name')] = placements.get(g.get('name'), 0) + 1
    raw = [{'name': n, 'raw_points': len(g.findall('.//point')),
            'lootmax': g.get('lootmax'), 'placements': placements.get(n, 0),
            'eligibility': 'unobserved'} for n, g in proto.items()]
    report = {'schema': 1, 'profile': profile['name'], 'status': 'offline-only-runtime-pending',
              'engine_eligible_loot_points': None, 'loot_fix_claim': False,
              'engine_merge_semantics': 'unobserved',
              'geometry_changes': [], 'raw_geometry': raw, 'routes': routes,
              'unresolved_placement_names': sorted(n for n in placements if n not in proto),
              'diagnostics': profile['diagnostics'], 'supplementary_loot_budget': 0,
              'population_budget': 'selected entries copy stock counts/flags; effective merging and world totals unobserved',
              'pending': ['DayZDiag eligibility/geometry', 'normal PBO/server load',
                          'CE spawn/error trials', '3-6-player budget measurement',
                          'two-client multiplayer', 'destination rollback']}
    patches = {n: {'before': defaults[n].get('value'), 'after': 'true'} for n in profile['diagnostics']}
    files = {'ce/types.xml': ET.tostring(out, encoding='utf-8', xml_declaration=True) + b'\n',
             'cfgeconomycore.append.xml': ET.tostring(fragment, encoding='utf-8', xml_declaration=True) + b'\n',
             'core-defaults.patch.json': encode(patches), 'economy-report.json': encode(report)}
    files['delta-manifest.json'] = encode({'schema': 1, 'profile': profile['name'],
        'sources': {n: sha(d) for n, d in data.items()},
        'files': {n: sha(d) for n, d in files.items()}, 'runtime_acceptance': 'pending'})
    return files


def write_delta(stage, files):
    stage = Path(stage)
    if set(files) != DELTA_FILES:
        raise ValueError('unexpected generated file set')
    if stage.exists() or stage.is_symlink():
        raise ValueError('output must be a fresh directory')
    # Preflight before any writes.
    for name in files:
        child(stage, name)
    stage.mkdir(parents=True)
    for name, data in files.items():
        p = child(stage, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


def _target(target):
    target = Path(target).absolute()
    child(target, 'cfgeconomycore.xml')
    if not target.is_dir() or 'steamapps' in (s.lower() for s in target.parts):
        raise ValueError('install requires an isolated existing mission copy outside Steam')
    return target


def _load_delta(stage):
    stage = Path(stage)
    found = set()
    for p in stage.rglob('*'):
        child(stage, p.relative_to(stage).as_posix())
        if p.is_file():
            found.add(p.relative_to(stage).as_posix())
        elif not p.is_dir():
            raise ValueError('special stage file')
    if found != DELTA_FILES:
        raise ValueError('unexpected or missing stage files')
    files = {n: child(stage, n).read_bytes() for n in found}
    manifest = json.loads(files['delta-manifest.json'])
    if (manifest.get('schema') != 1 or set(manifest.get('sources', {})) != set(INPUTS)
            or set(manifest.get('files', {})) != DELTA_FILES - {'delta-manifest.json'}):
        raise ValueError('invalid delta manifest')
    if any(sha(files[n]) != h for n, h in manifest['files'].items()):
        raise ValueError('delta checksum mismatch')
    return files, manifest


def _patched_core(original, fragment, patches):
    core = xml(original, 'economycore')
    if core.findall('ce'):
        raise ValueError('existing CE extensions require reconciliation')
    frag = xml(fragment, 'economycore')
    if any(x.tag != 'ce' or x.attrib != {'folder': MANAGED + '/ce'}
           or len(x) != 1 or x[0].tag != 'file'
           or x[0].attrib != {'name': 'types.xml', 'type': 'types'} for x in frag) or len(frag) > 1:
        raise ValueError('unsupported CE registration')
    defaults = _unique(core.findall('./defaults/default'))
    result = original
    for name, patch in patches.items():
        if (name not in LOG_NAMES or set(patch) != {'before', 'after'}
                or patch['after'] != 'true' or patch['before'] not in {'true', 'false'}
                or name not in defaults or defaults[name].get('value') != patch['before']):
            raise ValueError('invalid/drifted diagnostic patch')
        matches = [m for m in re.finditer(rb'<default\b[^<>]*/>', result)
                   if ET.fromstring(m.group()).get('name') == name]
        if len(matches) != 1:
            raise ValueError('ambiguous core default formatting')
        m = matches[0]
        changed, count = re.subn(rb'\bvalue\s*=\s*([\'"])(?:true|false)\1', b'value="true"', m.group())
        if count != 1:
            raise ValueError('unsupported core default formatting')
        result = result[:m.start()] + changed + result[m.end():]
    closing = list(re.finditer(rb'</economycore\s*>', result))
    if len(closing) != 1:
        raise ValueError('ambiguous core closing tag')
    if len(frag):
        insertion = b'\n' + ET.tostring(frag[0], encoding='utf-8') + b'\n'
        offset = closing[0].start()
        result = result[:offset] + insertion + result[offset:]
    xml(result, 'economycore')
    return result


def install(stage, target):
    target = _target(target)
    files, manifest = _load_delta(stage)
    data = snapshot(target)
    if {n: sha(d) for n, d in data.items()} != manifest['sources']:
        raise ValueError('target source hashes differ; regenerate/reconcile')
    managed = child(target, MANAGED)
    if managed.exists():
        raise ValueError('already installed or interrupted installation; inspect/rollback first')
    original = data['cfgeconomycore.xml']
    patched = _patched_core(original, files['cfgeconomycore.append.xml'], json.loads(files['core-defaults.patch.json']))
    types = xml(files['ce/types.xml'], 'types')
    stock = _unique(xml(data['db/types.xml'], 'types').findall('type'))
    vocabulary = _unique(xml(data['cfglimitsdefinition.xml'], 'lists').findall('./usageflags/usage'))
    _unique(types.findall('type'))
    def retained_fields(element):
        return (element.tag, tuple(sorted(element.attrib.items())), (element.text or '').strip(),
                tuple(retained_fields(n) for n in element if n.tag != 'usage'))
    for item in types:
        name = item.get('name')
        if item.tag != 'type' or name not in stock or retained_fields(item) != retained_fields(stock[name]):
            raise ValueError('candidate must retain every stock field except usage')
        _validate_budget(item)
        usages = item.findall('usage')
        _unique(usages)
        if not usages or any(set(n.attrib) != {'name'} or n.get('name') not in vocabulary or len(n) for n in usages):
            raise ValueError('invalid complete-entry usage override')
        if not {n.get('name') for n in stock[name].findall('usage')} <= {n.get('name') for n in usages}:
            raise ValueError('usage removal forbidden')
    managed.mkdir()
    receipt = {'schema': 1, 'before': sha(original), 'after': sha(patched),
               'types_sha256': sha(files['ce/types.xml']), 'sources': manifest['sources']}
    # Receipt+backup exist before the atomic core switch. Rollback also handles
    # an interrupted install whose switch did not happen. Stop the server first.
    (managed / 'core.backup').write_bytes(original)
    (managed / 'receipt.json').write_bytes(encode(receipt))
    (managed / 'ce').mkdir()
    (managed / 'ce/types.xml').write_bytes(files['ce/types.xml'])
    (managed / 'core.next').write_bytes(patched)
    os.replace(managed / 'core.next', child(target, 'cfgeconomycore.xml'))
    return receipt


def rollback(target):
    target = _target(target)
    managed = child(target, MANAGED)
    receipt = json.loads(child(managed, 'receipt.json').read_bytes())
    expected = {'core.backup', 'receipt.json', 'ce/types.xml', 'core.next'}
    for p in managed.rglob('*'):
        name = p.relative_to(managed).as_posix()
        child(managed, name)
        if p.is_file() and name not in expected:
            raise ValueError('unexpected managed file; rollback refuses deletion')
    core = child(target, 'cfgeconomycore.xml')
    backup = child(managed, 'core.backup').read_bytes()
    if sha(backup) != receipt['before'] or sha(core.read_bytes()) not in {receipt['before'], receipt['after']}:
        raise ValueError('core drift; manual reconciliation required')
    if sha(child(managed, 'ce/types.xml').read_bytes()) != receipt['types_sha256']:
        raise ValueError('installed delta drift; inspect before rollback')
    if {n: sha(child(target, n).read_bytes()) for n in INPUTS if n != 'cfgeconomycore.xml'} != {
            n: h for n, h in receipt['sources'].items() if n != 'cfgeconomycore.xml'}:
        raise ValueError('stock drift; inspect before rollback')
    (managed / 'core.next').write_bytes(backup)
    os.replace(managed / 'core.next', core)
    shutil.rmtree(managed)  # only our fixed directory, preflighted above


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('generate')
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--profile', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('install')
    p.add_argument('--delta', type=Path, required=True)
    p.add_argument('--target', type=Path, required=True)
    p = sub.add_parser('rollback')
    p.add_argument('--target', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'generate':
            write_delta(args.out, generate(args.source, json.loads(args.profile.read_bytes())))
        elif args.command == 'install':
            install(args.delta, args.target)
        else:
            rollback(args.target)
        print('Offline operation complete; DayZ runtime acceptance pending.')
    except (ValueError, OSError, KeyError, TypeError) as e:
        parser.exit(1, f'{e}\n')


if __name__ == '__main__':
    main()
