"""Curated vanilla firearms roster as a minimal Hollow Country CE delta.

Reuses the economy delta model: generate reads installed stock and never writes it; the delta is a
complete-entry ``types.xml`` override (stock fields copied, only the roster's budget/tier fields
changed) in the managed ``hollow-country/ce`` folder; install/rollback target an explicit stopped,
private mission copy (never Steam) and restore bytes exactly. No placement edits.

Offline generation establishes nothing about DayZ behaviour. Effective CE merging, world totals and
the 3-6 player feel are unobserved; runtime acceptance stays pending.
"""
import argparse
import copy
import json
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
REQUIRED = {'class', 'kind', 'role', 'tier', 'set', 'justification'}
OPTIONAL = {'add_usage', 'set_value', 'ammo', 'magazines'}
CLASS = re.compile(r'[A-Za-z0-9_]{1,80}')
MAX_ENTRIES = 400


def _int(value, low):
    return type(value) is int and value >= low


def validate_roster(roster):
    if not isinstance(roster, dict) or set(roster) != TOP or roster['schema'] != 1 \
            or type(roster['schema']) is not int:
        raise ValueError('unsupported roster schema/fields')
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
    for e in entries:
        if e['kind'] == 'weapon':
            if not set(e['ammo']) <= by_kind.get('ammo', set()) \
                    or not set(e['magazines']) <= by_kind.get('magazine', set()):
                raise ValueError(f'unreferenced ammo/magazine: {e["class"]}')
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
        raise ValueError(f'stock entry has no usage to extend: {entry["class"]}')
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


def generate(source, roster):
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
    rows, totals = [], {'weapon_nominal_stock': 0, 'weapon_nominal_candidate': 0}
    for entry in roster['entries']:
        name = entry['class']
        if name not in stock:
            raise ValueError(f'class absent from stock types.xml: {name}')
        economy._validate_budget(stock[name])
        item = copy.deepcopy(stock[name])
        _apply(item, entry, usage_vocab, value_vocab)
        economy._validate_budget(item)
        changed = ET.tostring(item) != ET.tostring(stock[name])
        if changed:
            out.append(item)
        rows.append({'class': name, 'kind': entry['kind'], 'role': entry['role'], 'tier': entry['tier'],
                     'stock': _row(stock[name]), 'candidate': _row(item), 'changed': changed,
                     'ammo': entry.get('ammo', []), 'magazines': entry.get('magazines', []),
                     'justification': entry['justification']})
        if entry['kind'] == 'weapon':
            totals['weapon_nominal_stock'] += rows[-1]['stock']['nominal']
            totals['weapon_nominal_candidate'] += rows[-1]['candidate']['nominal']
    fragment = ET.Element('economycore')
    if len(out):
        ce = ET.SubElement(fragment, 'ce', {'folder': economy.MANAGED + '/ce'})
        ET.SubElement(ce, 'file', {'name': 'types.xml', 'type': 'types'})
    report = {'schema': 1, 'kind': 'firearms-roster', 'profile': roster['name'], 'players': roster['players'],
              'status': 'offline-only-runtime-pending', 'loot_fix_claim': False,
              'engine_merge_semantics': 'unobserved', 'entries': rows, 'totals': totals,
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
        'files': {n: economy.sha(d) for n, d in files.items()}, 'runtime_acceptance': 'pending'})
    return files


write_delta = economy.write_delta
rollback = economy.rollback


def install(stage, target):
    return economy.install(stage, target, mutable=MUTABLE)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('generate')
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--roster', type=Path, default=ROSTER_PATH)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('install')
    p.add_argument('--delta', type=Path, required=True)
    p.add_argument('--target', type=Path, required=True)
    p = sub.add_parser('rollback')
    p.add_argument('--target', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'generate':
            write_delta(args.out, generate(args.source, json.loads(args.roster.read_bytes())))
        elif args.command == 'install':
            install(args.delta, args.target)
        else:
            rollback(args.target)
        print('Offline operation complete; DayZ runtime acceptance pending.')
    except (ValueError, OSError, KeyError, TypeError) as e:
        parser.exit(1, f'{e}\n')


if __name__ == '__main__':
    main()
