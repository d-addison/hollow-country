"""Curated vanilla firearms roster as a minimal Hollow Country CE delta.

Reuses the economy delta model: generate reads installed stock and never writes it; the delta is a
complete-entry ``types.xml`` delta in the managed ``hollow-country/ce`` folder. Ordinary entries
copy their stock row and change only roster budget/tier fields. Reviewed #48/#30 variants copy
their stock parent's entire row with nominal/min halved (floor); stock case aliases are reused.
Optics are superseded by the optional pack's mod-side config. Install/rollback target an explicit
stopped, private mission copy (never Steam) and restore bytes exactly. No placement edits.

Offline generation establishes nothing about DayZ behaviour. Effective CE merging, world totals and
the 3-6 player feel are unobserved; runtime acceptance stays pending.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

try:
    from tools.package import economy
except ImportError:  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.package import economy

ROSTER_PATH = Path(__file__).with_name('firearms_roster.json')
MUTABLE = frozenset({'usage', 'value', 'nominal', 'min', 'lifetime', 'restock'})
SET_FIELDS = ('nominal', 'min', 'lifetime', 'restock')
KINDS = {'weapon': {'wood', 'modern'}, 'magazine': {'support'}, 'ammo': {'support'}}
TIERS = {'common', 'uncommon', 'rare'}
TOP = {'schema', 'name', 'players', 'entries', 'deferred_datamined'}
TOP_OPTIONAL = {'optics'}
# Optics are supplied by the separately accepted optional pack's mod-side config (#30).
OPTICS_SUPERSEDED = {'status': 'superseded', 'entries': []}
REQUIRED = {'class', 'kind', 'role', 'tier', 'set', 'justification'}
OPTIONAL = {'add_usage', 'set_value', 'ammo', 'magazines', 'datamined', 'acceptance',
            'new_type_parent', 'runtime_acceptance', 'status'}
PENDING_LOCAL = 'pending-local'
CLASS = re.compile(r'[A-Za-z0-9_]{1,80}')
MAX_ENTRIES = 400


def _int(value, low):
    return type(value) is int and value >= low


def validate_roster(roster):
    if not isinstance(roster, dict) or not TOP <= set(roster) <= TOP | TOP_OPTIONAL or roster['schema'] != 1 \
            or type(roster['schema']) is not int:
        raise ValueError('unsupported roster schema/fields')
    if 'optics' in roster and roster['optics'] != OPTICS_SUPERSEDED:
        raise ValueError('rostered optics are superseded by the optional pack; entries must stay empty')
    if not isinstance(roster['name'], str) or not re.fullmatch(r'[a-z0-9-]{1,64}', roster['name']):
        raise ValueError('invalid roster name')
    if roster['players'] != '3-6':
        raise ValueError('roster must target 3-6 players')
    entries = roster['entries']
    if not isinstance(entries, list) or not 0 < len(entries) <= MAX_ENTRIES:
        raise ValueError('roster entries missing or over budget')
    by_kind = {}
    for e in entries:
        if not isinstance(e, dict) or not REQUIRED <= set(e) <= REQUIRED | OPTIONAL:
            raise ValueError('unsupported roster entry fields')
        name, kind = e['class'], e['kind']
        if not isinstance(name, str) or not CLASS.fullmatch(name):
            raise ValueError('invalid class name')
        # Datamined rows (stock nominal 0 or absent) spawn in the test candidate only under an explicit
        # pending-local marker, so the owner can accept or switch them all off in the local session.
        if ('datamined' in e) != ('acceptance' in e) or ('datamined' in e and (
                e['datamined'] is not True or e['acceptance'] != PENDING_LOCAL)):
            raise ValueError(f'datamined rows need datamined: true with acceptance: {PENDING_LOCAL}: {name}')
        if {'new_type_parent', 'runtime_acceptance', 'status'} & set(e):
            if (e.get('new_type_parent') != economy.datamined_items.NEW_TYPE_PARENTS.get(name)
                    or name not in economy.datamined_items.NEW_TYPE_PARENTS
                    or e.get('runtime_acceptance') != 'pending'
                    or e.get('status') != 'requires-local-acceptance' or not e.get('datamined')
                    or set(e['set']) != {'nominal', 'min'} or 'add_usage' in e or 'set_value' in e):
                raise ValueError(f'new type needs reviewed parent, unchanged placement and pending acceptance: {name}')
        if kind not in KINDS or e['role'] not in KINDS[kind] or e['tier'] not in TIERS:
            raise ValueError(f'invalid kind/role/tier: {name}')
        if any(name in names for names in by_kind.values()):
            raise ValueError(f'duplicate roster class: {name}')
        by_kind.setdefault(kind, set()).add(name)
        if not isinstance(e['justification'], str) or not e['justification'].strip():
            raise ValueError(f'justification required: {name}')
        s = e['set']
        if (not isinstance(s, dict) or not {'nominal', 'min'} <= set(s) or not set(s) <= set(SET_FIELDS)
                or not _int(s['nominal'], 0) or not _int(s['min'], 0) or s['min'] > s['nominal']
                or ('lifetime' in s and not _int(s['lifetime'], 1))
                or ('restock' in s and not _int(s['restock'], 0))):
            raise ValueError(f'invalid budget fields: {name}')
        for field in ('add_usage', 'set_value'):
            if field in e and (not isinstance(e[field], list) or not e[field] or len(set(e[field])) != len(e[field])
                               or any(not isinstance(v, str) or not CLASS.fullmatch(v) for v in e[field])):
                raise ValueError(f'invalid {field}: {name}')
        if kind == 'weapon':
            for field in ('ammo', 'magazines'):
                if not isinstance(e.get(field), list) or any(not isinstance(v, str) for v in e[field]):
                    raise ValueError(f'weapon needs {field} list: {name}')
        elif 'ammo' in e or 'magazines' in e:
            raise ValueError(f'only weapons carry ammo/magazines: {name}')
    datamined = {e['class'] for e in entries if e.get('datamined')}
    for e in entries:
        if e['kind'] == 'weapon':
            if not set(e['ammo']) <= by_kind.get('ammo', set()) \
                    or not set(e['magazines']) <= by_kind.get('magazine', set()):
                raise ValueError(f'unreferenced ammo/magazine: {e["class"]}')
            if not e.get('datamined') and (set(e['ammo']) | set(e['magazines'])) & datamined:
                raise ValueError(f'a non-datamined weapon cannot depend on a datamined row: {e["class"]}')
    deferred = roster['deferred_datamined']
    if not isinstance(deferred, list) or len(deferred) > MAX_ENTRIES:
        raise ValueError('invalid deferred list')
    taken = set().union(*by_kind.values())
    for d in deferred:
        if (not isinstance(d, dict) or set(d) != {'class', 'status', 'note'}
                or not isinstance(d['class'], str) or not CLASS.fullmatch(d['class'])
                or d['status'] != 'requires-local-acceptance' or not isinstance(d['note'], str)):
            raise ValueError('deferred datamined entries must stay pending local acceptance')
        if d['class'] in taken:
            raise ValueError('deferred class overlaps an enabled entry')


def _row(item):
    return {'nominal': int(item.findtext('nominal')), 'min': int(item.findtext('min')),
            'lifetime': int(item.findtext('lifetime')), 'restock': int(item.findtext('restock')),
            'usage': [n.get('name') for n in item.findall('usage')],
            'value': [n.get('name') for n in item.findall('value')]}


def _apply(item, entry, usage_vocab, value_vocab):
    for field, value in entry['set'].items():
        node = item.find(field)
        if node is None:
            raise ValueError(f'stock lacks {field}: {entry["class"]}')
        node.text = str(value)
    positions = [i for i, n in enumerate(item) if n.tag == 'usage']
    if not positions:
        if 'add_usage' not in entry:
            raise ValueError(f'stock entry has no usage to extend: {entry["class"]}')
        # Unused stock rows may carry no usage at all: the declared usage goes before any value tag.
        first_value = next((i for i, n in enumerate(item) if n.tag == 'value'), len(item))
        positions = [first_value]
    old = [n.get('name') for n in item.findall('usage')]
    if 'add_usage' in entry:
        if any(u not in usage_vocab for u in entry['add_usage'] + old):
            raise ValueError(f'unknown usage: {entry["class"]}')
        merged = sorted(set(old) | set(entry['add_usage']))
        for n in item.findall('usage'):
            item.remove(n)
        for offset, u in enumerate(merged):
            item.insert(positions[0] + offset, ET.Element('usage', {'name': u}))
    if 'set_value' in entry:
        if any(v not in value_vocab for v in entry['set_value']):
            raise ValueError(f'unknown value tier: {entry["class"]}')
        for n in item.findall('value'):
            item.remove(n)
        after = max(i for i, n in enumerate(item) if n.tag == 'usage')
        for offset, v in enumerate(entry['set_value']):
            item.insert(after + 1 + offset, ET.Element('value', {'name': v}))


def effective_types(source, stock, managed_folders):
    """Layer the known managed overrides over stock for offline dependency checks."""
    result = dict(stock)
    for folder in managed_folders:
        path = economy.child(source, folder + '/ce/types.xml')
        if os.path.lexists(path):
            result.update(economy._unique(economy.xml(
                economy.read_plain(source, folder + '/ce/types.xml'), 'types').findall('type')))
    return result


def check_support(entries, nominal, ammo_fields=('ammo',)):
    """A spawning weapon needs at least one spawning compatible source of each required kind."""
    for entry in entries:
        name = entry['class']
        if entry['kind'] != 'weapon' or nominal(name) <= 0:
            continue
        ammo = [a for field in ammo_fields for a in entry[field]]
        if not any(nominal(a) > 0 for a in ammo):
            raise ValueError(f'spawning weapon has no spawning compatible ammo: {name}')
        if entry['magazines'] and not any(nominal(m) > 0 for m in entry['magazines']):
            raise ValueError(f'spawning weapon has no spawning compatible magazine: {name}')


def _nominal(types, name):
    item = types.get(name.lower())
    if item is None:
        return 0
    return int(item.findtext('nominal') or 0)


def check_effective_support(source, stock, entries, generated, managed_folders=(),
                            ammo_fields=('ammo',), verification=None):
    """Recheck source plus managed/generated rows at generation and immediately before install."""
    effective = effective_types(source, stock, managed_folders)
    effective.update({item.get('name'): item for item in generated})
    effective_lower = {class_name.lower(): type_item for class_name, type_item in effective.items()}
    support_entries = []
    for entry in entries:
        if entry['kind'] == 'weapon':
            if any(not isinstance(entry.get(field), list) for field in (*ammo_fields, 'magazines')):
                raise ValueError('delta lacks compatible support policy; regenerate')
            if verification is not None:
                compatible = verification.get(entry['class'], {}).get('compatible_magazines')
                if not isinstance(compatible, list):
                    raise ValueError('verification lacks compatible magazine evidence; reverify')
                entry = dict(entry, magazines=entry['magazines'] or compatible)
        support_entries.append(entry)
    check_support(support_entries,
                  lambda name: _nominal(effective_lower, name),
                  ammo_fields=ammo_fields)


def roster_items(stock, usage_vocab, value_vocab, roster, include_datamined=True):
    """Pure roster pass shared by the firearms-only delta and the combined economy delta.

    Returns ``(changed_elements, report_rows, totals)``; ``stock`` is economy's name -> <type> map.
    """
    validate_roster(roster)
    changed_elements = []
    rows, totals = [], {'weapon_nominal_stock': 0, 'weapon_nominal_candidate': 0}
    stock_lower = {class_name.lower(): type_item for class_name, type_item in stock.items()}
    if len(stock_lower) != len(stock):
        raise ValueError('case-insensitive duplicate stock class')
    for entry in roster['entries']:
        name = entry['class']
        if entry.get('datamined') and not include_datamined:
            continue
        stock_row = None
        if 'new_type_parent' in entry:
            original = stock_lower.get(name.lower())
            item = economy.datamined_items.reviewed_new_type(name, stock)
            if original is not None:
                stock_row = _row(original)
            if any(node.get('name') not in usage_vocab for node in item.findall('usage')):
                raise ValueError(f'unknown parent usage: {name}')
            if any(node.get('name') not in value_vocab for node in item.findall('value')):
                raise ValueError(f'unknown parent value tier: {name}')
            changed = True
        elif name in stock:
            economy._validate_budget(stock[name])
            item = copy.deepcopy(stock[name])
            _apply(item, entry, usage_vocab, value_vocab)
            stock_row = _row(stock[name])
            changed = ET.tostring(item) != ET.tostring(stock[name])
        else:
            raise ValueError(f'class absent from stock types.xml: {name}')
        economy._validate_budget(item)
        if changed:
            changed_elements.append(item)
        rows.append({'class': name, 'kind': entry['kind'], 'role': entry['role'], 'tier': entry['tier'],
                     'stock': stock_row, 'candidate': _row(item), 'changed': changed,
                     'ammo': entry.get('ammo', []), 'magazines': entry.get('magazines', []),
                     'justification': entry['justification']})
        if 'acceptance' in entry:
            rows[-1]['acceptance'] = entry['acceptance']
        if 'new_type_parent' in entry:
            rows[-1].update(new_type_parent=entry['new_type_parent'], runtime_acceptance='pending',
                            status='requires-local-acceptance', new_type=stock_row is None,
                            emitted_class=item.get('name'))
        if entry['kind'] == 'weapon':
            if stock_row is not None:
                totals['weapon_nominal_stock'] += stock_row['nominal']
            totals['weapon_nominal_candidate'] += rows[-1]['candidate']['nominal']
    effective = dict(stock)
    effective.update({item.get('name'): item for item in changed_elements})
    effective_lower = {class_name.lower(): type_item for class_name, type_item in effective.items()}
    check_support([e for e in roster['entries'] if include_datamined or not e.get('datamined')],
                  lambda name: _nominal(effective_lower, name))
    return changed_elements, rows, totals


def generate(source, roster, include_datamined=True):
    validate_roster(roster)
    data = economy.snapshot(source)
    core = economy.xml(data['cfgeconomycore.xml'], 'economycore')
    if core.findall('ce'):
        raise ValueError('existing CE extensions need explicit operator reconciliation')
    stock = economy._unique(economy.xml(data['db/types.xml'], 'types').findall('type'))
    limits = economy.xml(data['cfglimitsdefinition.xml'], 'lists')
    usage_vocab = set(economy._unique(limits.findall('./usageflags/usage')))
    value_vocab = set(economy._unique(limits.findall('./valueflags/value')))
    out = ET.Element('types')
    datamined = sorted(e['class'] for e in roster['entries'] if e.get('datamined'))
    changed, rows, totals = roster_items(stock, usage_vocab, value_vocab, roster, include_datamined)
    out.extend(changed)
    fragment = ET.Element('economycore')
    if len(out):
        ce = ET.SubElement(fragment, 'ce', {'folder': economy.MANAGED + '/ce'})
        ET.SubElement(ce, 'file', {'name': 'types.xml', 'type': 'types'})
    report = {'schema': 1, 'kind': 'firearms-roster', 'profile': roster['name'], 'players': roster['players'],
              'status': 'offline-only-runtime-pending', 'loot_fix_claim': False,
              'engine_merge_semantics': 'unobserved', 'entries': rows, 'totals': totals,
              'datamined': {'enabled': bool(include_datamined), 'classes': datamined},
              'deferred_datamined': roster['deferred_datamined'], 'runtime_acceptance': 'pending',
              'population_budget': 'roster counts are proposals for 3-6 players; effective world totals unobserved',
              'pending': ['normal PBO/server load', 'CE spawn/error trials', '3-6-player budget measurement',
                          'local acceptance of every datamined candidate', 'destination rollback']}
    files = {'ce/types.xml': ET.tostring(out, encoding='utf-8', xml_declaration=True) + b'\n',
             'cfgeconomycore.append.xml': ET.tostring(fragment, encoding='utf-8', xml_declaration=True) + b'\n',
             'core-defaults.patch.json': economy.encode({}), 'economy-report.json': economy.encode(report)}
    files['delta-manifest.json'] = economy.encode({
        'schema': 1, 'kind': 'firearms-roster', 'profile': roster['name'],
        'sources': {n: economy.sha(d) for n, d in data.items()},
        'files': {n: economy.sha(d) for n, d in files.items()}, 'runtime_acceptance': 'pending',
        'firearms_classes': sorted(n.get('name') for n in out), 'datamined_classes': [],
        'new_type_classes': sorted(r['class'] for r in rows if r.get('new_type'))})
    return files


def generate_combined(source, roster, include_datamined=True, include_items=True, profile=None):
    """Profile + roster + datamined items as one delta (delegates to economy.generate)."""
    validate_roster(roster)
    profile = profile or {'schema': 1, 'name': roster['name'], 'add_usage': {}, 'diagnostics': []}
    return economy.generate(source, profile, include_datamined=include_items, roster=roster,
                            include_roster_datamined=include_datamined)


write_delta = economy.write_delta
rollback = economy.rollback


def install(stage, target):
    """The single installer: per-class permissions come from the delta manifest."""
    return economy.install_delta(stage, target)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('generate')
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--roster', type=Path, default=ROSTER_PATH)
    p.add_argument('--no-datamined', action='store_true',
                   help='single switch: leave every datamined (acceptance: pending-local) row out of the delta')
    p.add_argument('--with-items', action='store_true',
                   help='compose the datamined non-weapon items (and --profile) into the same single delta')
    p.add_argument('--profile', type=Path, default=None,
                   help='economy profile to compose (implies --with-items)')
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('install')
    p.add_argument('--delta', type=Path, required=True)
    p.add_argument('--target', type=Path, required=True)
    p = sub.add_parser('rollback')
    p.add_argument('--target', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'generate':
            roster = json.loads(args.roster.read_bytes())
            if args.with_items or args.profile:
                profile = json.loads(args.profile.read_bytes()) if args.profile else None
                files = generate_combined(args.source, roster, include_datamined=not args.no_datamined,
                                          profile=profile)
            else:
                files = generate(args.source, roster, include_datamined=not args.no_datamined)
            write_delta(args.out, files)
        elif args.command == 'install':
            install(args.delta, args.target)
        else:
            rollback(args.target)
        print('Offline operation complete; DayZ runtime acceptance pending.')
    except (ValueError, OSError, KeyError, TypeError) as e:
        parser.exit(1, f'{e}\n')


if __name__ == '__main__':
    main()
