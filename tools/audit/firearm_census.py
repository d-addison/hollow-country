"""Bounded, read-only census of vanilla firearm classes versus the CE economy files.

Reads weapon/magazine configs from addon PBOs (header + ``config.bin`` members only, never
whole PBOs) and cross-references ``types.xml``, ``cfgspawnabletypes.xml``,
``cfgrandompresets.xml``, ``cfgeventgroups.xml``, ``db/events.xml`` and ``cfgeventspawns.xml``.

The classification is static file evidence. It is not proof of in-game behaviour: the CE merge,
placement eligibility and DLC ownership gates are unobserved here. The full census is written
only outside any Git checkout; never commit it (it would be a vanilla dump).

    python3 -B -m tools.audit.firearm_census --addons server=ADDONS_DIR \\
        --mission MISSION_DIR --out ~/.cache/hollow-country/firearm-census-DATE
"""
import argparse
import json
from pathlib import Path
import sys

try:
    from tools.audit import pbo_config
    from tools.package import economy
except ImportError:  # run as a script from tools/audit
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.audit import pbo_config
    from tools.package import economy

ROOTS = ('CfgWeapons', 'CfgMagazines', 'CfgAmmo')
FAMILIES = (('Rifle_Base', 'rifle'), ('Pistol_Base', 'pistol'), ('Shotgun_Base', 'shotgun'),
            ('Launcher_Base', 'launcher'), ('Archery_Base', 'archery'),
            ('NonlethalCore', 'nonlethal'), ('Crossbow_Base', 'archery'))
LIMITATIONS = [
    'Static file evidence only: classes, scope and CE entries read from files, never from a running '
    'server; the classification is not proof of in-game spawning or usability.',
    'CE placement eligibility, loot-point geometry and event activity are unobserved.',
    'Scope is the first explicit value up the parent chain inside the scanned addons; classes whose '
    'chain leaves the scanned addons are reported unknown.',
    'A non-spawning class can be unfinished: the completeness flags check only model, hand '
    'animation and magazine presence, not that the weapon is actually usable.',
]
MISSION_FILES = {'types': 'db/types.xml', 'spawnable': 'cfgspawnabletypes.xml',
                 'presets': 'cfgrandompresets.xml', 'eventgroups': 'cfgeventgroups.xml',
                 'events': 'db/events.xml', 'eventspawns': 'cfgeventspawns.xml'}


def family(ancestors):
    """Weapon family from the ancestor chain, 'other' for unrecognised weapon lineages."""
    for base, name in FAMILIES:
        if base in ancestors:
            return name
    return 'other'


def check_output_dir(path):
    """Refuse an output directory inside any Git checkout (the census must stay out of Git)."""
    path = Path(path).absolute()
    for parent in (path, *path.parents):
        if (parent / '.git').exists():
            raise ValueError('census output must be outside any Git checkout')


def _integer(text):
    try:
        return int((text or '').strip())
    except ValueError:
        return None


def _parse_types(data):
    types = {}
    for node in economy.xml(data, 'types').findall('type'):
        name = node.get('name')
        if not name:
            raise ValueError('type without a name')
        types[name] = {'nominal': _integer(node.findtext('nominal')),
                       'min': _integer(node.findtext('min')),
                       'lifetime': _integer(node.findtext('lifetime')),
                       'restock': _integer(node.findtext('restock')),
                       'usage': [n.get('name') for n in node.findall('usage')],
                       'value': [n.get('name') for n in node.findall('value')]}
    return types


def _parse_spawnable(data):
    """carrier -> (direct item names, preset names)."""
    carriers = {}
    for node in economy.xml(data, 'spawnabletypes').findall('type'):
        items, presets = set(), set()
        for sub in node.iter():
            if sub.tag == 'item' and sub.get('name'):
                items.add(sub.get('name'))
            if sub.get('preset'):
                presets.add(sub.get('preset'))
        carriers[node.get('name')] = (items, presets)
    return carriers


def _parse_presets(data):
    presets = {}
    for node in economy.xml(data, 'randompresets'):
        name = node.get('name')
        if name:
            presets.setdefault(name, set()).update(i.get('name') for i in node.findall('item'))
    return presets


def _parse_event_children(groups, events):
    """Return (event carrier type names, direct event child names, active event names, event names)."""
    carriers, active, names = set(), set(), set()
    if groups is not None:
        for child in economy.xml(groups, 'eventgroupdef').iter('child'):
            if child.get('type'):
                carriers.add(child.get('type'))
    if events is not None:
        for event in economy.xml(events, 'events').findall('event'):
            names.add(event.get('name'))
            if (event.findtext('active') or '').strip() == '1':
                active.add(event.get('name'))
            for child in event.iter('child'):
                if child.get('type'):
                    carriers.add(child.get('type'))
    return carriers, active, names


def _magazine_rows(weapon, weapons, magazines, ammo, types):
    names = [m for m in (pbo_config.resolve_field(weapons, weapon, 'magazines') or []) if m]
    rows = []
    for name in names:
        row = {'class': name, 'scope': pbo_config.resolve_scope(magazines, name) if name in magazines else None,
               'in_types': name in types, 'ammo': None, 'ammo_present': False}
        bullet = pbo_config.resolve_field(magazines, name, 'ammo') if name in magazines else None
        row['ammo'] = bullet
        row['ammo_present'] = bool(bullet) and bullet in ammo
        rows.append(row)
    return rows


def _completeness(weapon, weapons, mags, models, anims):
    model = pbo_config.resolve_field(weapons, weapon, 'model')
    model_present = None if model is None else pbo_config.normalize_path(model) in models
    hand = pbo_config.resolve_field(weapons, weapon, 'handAnim') or []
    anim_missing = sorted(a for a in hand if a.lower().endswith('.rtm')
                          and pbo_config.normalize_path(a) not in anims)
    missing = sorted(m['class'] for m in mags if m['scope'] is None)
    hidden = sorted(m['class'] for m in mags if m['scope'] is not None and m['scope'] != 2)
    suspect = model_present is False or bool(anim_missing or missing or hidden)
    return {'model_present': model_present, 'anim_missing': anim_missing,
            'magazines_missing': missing, 'magazines_not_public': hidden,
            'suspect_unfinished': suspect}


def _classify(scope, types_row, world, event):
    if scope is None:
        return 'unknown', ['scope-unresolved-in-scanned-addons']
    if scope != 2:
        return 'scope-not-public', [f'resolved-scope-{scope}']
    if types_row is None:
        return 'missing-from-types', ['absent-from-db-types-xml']
    nominal = types_row['nominal']
    if nominal is None:
        return 'unknown', ['nominal-unparsable']
    if nominal > 0:
        if types_row['usage'] or world or event:
            return 'spawning', [f'nominal-{nominal}']
        return 'unknown', [f'nominal-{nominal}-without-usage-or-carrier']
    if world:
        return 'spawning', ['nominal-0-but-reached-through-world-carrier-or-preset']
    if event:
        return 'event-only', ['nominal-0-reached-only-through-event-carriers']
    return 'nominal-zero', ['nominal-0-no-carrier-or-preset']


def build_census(weapons, magazines, ammo, models, anims, mission):
    """Pure cross-reference. ``mission`` maps relative file names to raw XML bytes."""
    if MISSION_FILES['types'] not in mission:
        raise ValueError('db/types.xml is required')
    types = _parse_types(mission[MISSION_FILES['types']])
    spawnable = _parse_spawnable(mission.get(MISSION_FILES['spawnable'], b'<spawnabletypes/>'))
    presets = _parse_presets(mission.get(MISSION_FILES['presets'], b'<randompresets/>'))
    event_types, active_events, event_names = _parse_event_children(
        mission.get(MISSION_FILES['eventgroups']), mission.get(MISSION_FILES['events']))
    if MISSION_FILES['eventspawns'] in mission:
        spawn_events = {e.get('name') for e in
                        economy.xml(mission[MISSION_FILES['eventspawns']], 'eventposdef').findall('event')}
    else:
        spawn_events = set()
    children = {}
    for name, row in weapons.items():
        if row.get('parent'):
            children.setdefault(row['parent'], []).append(name)
    result, abstract = {}, []
    for name in sorted(weapons):
        scope = pbo_config.resolve_scope(weapons, name)
        if scope == 0 and name in children:
            abstract.append(name)
            continue
        ancestors = pbo_config.ancestry(weapons, name)
        refs = {'direct_carriers': sorted(c for c, (items, _) in spawnable.items() if name in items),
                'presets': sorted(p for p, items in presets.items() if name in items)}
        via_preset = sorted(c for c, (_, used) in spawnable.items() if used & set(refs['presets']))
        carriers = sorted(set(refs['direct_carriers']) | set(via_preset))
        refs['event_carriers'] = [c for c in carriers if c in event_types]
        refs['world_carriers'] = [c for c in carriers if c not in event_types]
        refs['event_direct'] = name in event_types
        refs['event_names_with_positions'] = sorted(spawn_events & event_names) if refs['event_carriers'] else []
        refs['events_active'] = sorted(active_events) if refs['event_carriers'] else []
        refs['direct_carriers'] = sorted(refs['direct_carriers'])
        row = types.get(name)
        classification, evidence = _classify(scope, row, refs['world_carriers'],
                                             refs['event_carriers'] or refs['event_direct'])
        if row is None and (refs['world_carriers'] or refs['event_carriers']):
            evidence.append('referenced-by-spawnabletypes-without-a-types-entry')
        mags = _magazine_rows(name, weapons, magazines, ammo, types)
        result[name] = {'class': name, 'parent': weapons[name].get('parent'), 'family': family(ancestors),
                        'scope': scope, 'classification': classification, 'evidence': evidence,
                        'types': row, 'references': refs, 'magazines': mags,
                        'chamber_ammo': pbo_config.resolve_field(weapons, name, 'chamberableFrom') or [],
                        'completeness': _completeness(name, weapons, mags, models, anims)}
    counts = {}
    for row in result.values():
        counts[row['classification']] = counts.get(row['classification'], 0) + 1
    for label in ('spawning', 'nominal-zero', 'missing-from-types', 'event-only',
                  'scope-not-public', 'unknown'):
        counts.setdefault(label, 0)
    summary = {'weapon_classes': len(result), 'abstract_bases': len(abstract),
               'by_classification': dict(sorted(counts.items())),
               'scope2_suspect_unfinished': sorted(n for n, r in result.items()
                                                    if r['scope'] == 2 and r['completeness']['suspect_unfinished'])}
    return {'schema': 1, 'limitations': LIMITATIONS, 'summary': summary,
            'abstract_base_names': abstract, 'weapons': result}


def cross_check_workbook(census, workbook):
    """Compare native item-review rows (hidden scope evidence) with the file-based census."""
    rows = [r for r in workbook.get('classes', []) if r.get('root') == 'CfgWeapons']
    weapons, abstract = census['weapons'], set(census['abstract_base_names'])
    hidden = sorted(r['name'] for r in rows if r.get('review_status') == 'excluded-definition'
                    and r['name'] not in weapons and r['name'] not in abstract)
    native_only = sorted(r['name'] for r in rows if r.get('review_status') != 'excluded-definition'
                         and r['name'] not in weapons and r['name'] not in abstract)
    disagree = sorted(r['name'] for r in rows if r.get('review_status') == 'retain'
                      and r['name'] in weapons and weapons[r['name']]['scope'] == 0)
    not_public = sorted(r['name'] for r in rows if r.get('review_status') == 'retain'
                        and r['name'] in weapons and weapons[r['name']]['scope'] == 1)
    return {'status': 'file-read-authoritative-native-is-cross-check', 'native_weapon_rows': len(rows),
            'native_only': native_only, 'native_hidden_not_in_census': hidden,
            'native_retained_but_file_scope_zero': disagree,
            'native_retained_but_file_scope_not_public': not_public}


def _merge(old, new):
    for key, value in new.items():
        if old.get(key) is None and value is not None:
            old[key] = value


def load_addons(sources, max_pbos=1024):
    """Read configs and asset paths from ``[(label, directory), ...]`` of addon folders.

    Only ``*.pbo`` files are opened (encrypted ``.ebo`` and others are skipped and named).
    Duplicate classes merge first-seen: later PBOs only fill fields the earlier ones left unset.
    """
    data = {'weapons': {}, 'magazines': {}, 'ammo': {}, 'models': set(), 'anims': set(), 'sources': []}
    targets = {'CfgWeapons': 'weapons', 'CfgMagazines': 'magazines', 'CfgAmmo': 'ammo'}
    for label, directory in sources:
        directory = Path(directory)
        pbos = sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == '.pbo')
        skipped = sorted(p.name for p in directory.iterdir()
                         if p.is_file() and p.suffix.lower() in {'.ebo'})
        if len(pbos) > max_pbos:
            raise ValueError('too many PBOs in one addon directory')
        for path in pbos:
            index = pbo_config.read_pbo_index(path)
            prefix = pbo_config.normalize_path(index['prefix'])
            for entry in index['entries']:
                low = entry['name'].lower()
                if low.endswith('.p3d') or low.endswith('.rtm'):
                    full = pbo_config.normalize_path((prefix + '\\' if prefix else '') + entry['name'])
                    (data['models'] if low.endswith('.p3d') else data['anims']).add(full)
            for root, classes in pbo_config.read_configs(path, ROOTS, index).items():
                bucket = data[targets[root]]
                for name, row in classes.items():
                    if name in bucket:
                        _merge(bucket[name], row)
                    else:
                        bucket[name] = dict(row)
        data['sources'].append({'label': label, 'pbo_count': len(pbos), 'skipped': skipped})
    return data


def load_mission(mission_dir):
    mission = {}
    root = Path(mission_dir)
    for name in MISSION_FILES.values():
        path = root / name
        if path.is_file():
            if path.stat().st_size > 16 * 1024 * 1024:
                raise ValueError(f'{name} exceeds the size budget')
            mission[name] = path.read_bytes()
    return mission


def render_summary(result):
    lines = ['Firearm census (static file evidence; not proof of in-game behaviour)', '']
    s = result['summary']
    lines.append(f"weapon classes: {s['weapon_classes']}   abstract scope-0 bases: {s['abstract_bases']}")
    for label, count in s['by_classification'].items():
        lines.append(f'  {label}: {count}')
    lines += ['', 'scope-2 classes with incomplete-asset suspicion:']
    lines += [f'  {n}' for n in s['scope2_suspect_unfinished']] or ['  none']
    lines += [''] + [f'- {text}' for text in result['limitations']]
    return '\n'.join(lines) + '\n'


def write_census(out, result):
    out = Path(out)
    check_output_dir(out)
    if out.exists() or out.is_symlink():
        raise ValueError('output must be a fresh directory')
    out.mkdir(parents=True)
    (out / 'census.json').write_text(json.dumps(result, indent=1, sort_keys=True) + '\n')
    (out / 'summary.txt').write_text(render_summary(result))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--addons', action='append', required=True, metavar='LABEL=DIR')
    parser.add_argument('--mission', type=Path, required=True)
    parser.add_argument('--workbook', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        check_output_dir(args.out)
        sources = []
        for item in args.addons:
            label, _, path = item.partition('=')
            if not path:
                raise ValueError('--addons needs LABEL=DIR')
            sources.append((label, Path(path).expanduser()))
        data = load_addons(sources)
        result = build_census(data['weapons'], data['magazines'], data['ammo'], data['models'],
                              data['anims'], load_mission(args.mission.expanduser()))
        result['sources'] = data['sources']
        if args.workbook:
            if args.workbook.stat().st_size > 64 * 1024 * 1024:
                raise ValueError('workbook exceeds the size budget')
            result['workbook_cross_check'] = cross_check_workbook(result, json.loads(args.workbook.read_bytes()))
        write_census(args.out.expanduser(), result)
    except (ValueError, OSError, KeyError) as e:
        parser.exit(1, f'{e}\n')
    print(render_summary(result))


if __name__ == '__main__':
    main()
