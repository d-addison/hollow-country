"""Curated vanilla firearms roster as a minimal Hollow Country CE delta.

Reuses the economy delta model: generate reads installed stock and never writes it; the delta is a
complete-entry ``types.xml`` delta in the managed ``hollow-country/ce`` folder. Ordinary entries
copy their stock row and change only roster budget/tier fields. Reviewed #48/#30 variants copy
their stock parent's row with explicit family-budget shares; stock case aliases are reused.
Vanilla CE-listed optics and parts are ordinary support rows in the abundance profile. Install/rollback target an explicit
stopped, private mission copy (never Steam) and restore bytes exactly. No geometry edits.

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
    from tools.package import xml_text
except ImportError:  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.package import economy
    from tools.package import xml_text

ROSTER_PATH = Path(__file__).with_name('firearms_roster.json')
MUTABLE = frozenset({'usage', 'value', 'nominal', 'min', 'lifetime', 'restock'})
SET_FIELDS = ('nominal', 'min', 'lifetime', 'restock')
KINDS = {'weapon': {'wood', 'modern'}, 'magazine': {'support'}, 'ammo': {'support'}, 'attachment': {'support'}}
TIERS = {'common', 'uncommon', 'rare'}
TOP = {'schema', 'name', 'players', 'entries', 'deferred_datamined'}
TOP_OPTIONAL = {'optics', 'family_budgets', 'refusals', 'economy_profile', 'scarcity_policy'}
# Historical metadata for the old optional-pack decision; abundance uses attachment entries.
OPTICS_SUPERSEDED = {'status': 'superseded', 'entries': []}
REQUIRED = {'class', 'kind', 'role', 'tier', 'set', 'justification'}
OPTIONAL = {'set_usage', 'add_usage', 'set_value', 'ammo', 'magazines', 'datamined', 'acceptance',
            'new_type_parent', 'runtime_acceptance', 'status', 'family', 'disposition',
            'unit_rounds', 'parts'}
PENDING_LOCAL = 'pending-local'
CLASS = re.compile(r'[A-Za-z0-9_]{1,80}')
MAX_ENTRIES = 400


def _int(value, low):
    return type(value) is int and value >= low


def selected_roster(roster):
    """One release-wide knob; the historical scarcity entries/caps remain byte-for-byte data."""
    if not isinstance(roster, dict):
        raise ValueError('unsupported roster schema/fields')
    profile = roster.get('economy_profile')
    if profile is None:
        return roster  # Legacy/custom rosters retain their existing schema.
    if profile not in {'test-abundance', 'scarcity'}:
        raise ValueError('invalid economy_profile: expected test-abundance or scarcity')
    policy = roster.get('scarcity_policy')
    if not isinstance(policy, dict) or set(policy) != {'entries', 'family_budgets'}:
        raise ValueError('economy_profile requires the historical scarcity_policy')
    if profile == 'scarcity':
        return dict(roster, **policy)
    return roster


def validate_roster(roster):
    if isinstance(roster, dict):
        roster = selected_roster(roster)
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
        if 'new_type_parent' in e:
            if (e.get('new_type_parent') != economy.datamined_items.NEW_TYPE_PARENTS.get(name)
                    or name not in economy.datamined_items.NEW_TYPE_PARENTS
                    or e.get('runtime_acceptance') != 'pending'
                    or e.get('status') != 'requires-local-acceptance' or not e.get('datamined')
                    or (roster.get('economy_profile') != 'test-abundance' and
                        (set(e['set']) != {'nominal', 'min'} or
                         any(f in e for f in ('add_usage', 'set_usage', 'set_value'))))):
                raise ValueError(f'new type needs reviewed parent, unchanged placement and pending acceptance: {name}')
        elif ('status' in e or ('runtime_acceptance' in e and
                (e.get('disposition') != 'review-native-budget' or e['runtime_acceptance'] != 'pending'))):
            raise ValueError(f'unsupported runtime acceptance: {name}')
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
        for field in ('add_usage', 'set_usage', 'set_value'):
            if field in e and (not isinstance(e[field], list) or not e[field] or len(set(e[field])) != len(e[field])
                               or any(not isinstance(v, str) or not CLASS.fullmatch(v) for v in e[field])):
                raise ValueError(f'invalid {field}: {name}')
        if kind == 'weapon':
            for field in ('ammo', 'magazines'):
                if not isinstance(e.get(field), list) or any(not isinstance(v, str) for v in e[field]):
                    raise ValueError(f'weapon needs {field} list: {name}')
        elif 'ammo' in e or 'magazines' in e:
            raise ValueError(f'only weapons carry ammo/magazines: {name}')
    referenced_magazines = {m for e in entries if e['kind'] == 'weapon' for m in e['magazines']}
    if by_kind.get('magazine', set()) - referenced_magazines:
        raise ValueError('unreferenced magazine support row')
    datamined = {e['class'] for e in entries if e.get('datamined')}
    for e in entries:
        if roster.get('economy_profile') == 'test-abundance' and (
                not e.get('set_usage') or not e.get('set_value')):
            raise ValueError(f'abundance entry needs explicit usage and tiers: {e["class"]}')
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
    family_totals(roster)


def family_totals(roster, rows=None):
    """Validate authored shares, or effective rows, in item / maximum-cartridge units.

    These are CE nominal envelopes, never a promise of hard native world caps. Legacy synthetic
    callers without the HC-21 policy keep their previous schema and behaviour.
    """
    if 'family_budgets' not in roster:
        if any({'family', 'unit_rounds', 'disposition', 'parts'} & e.keys() for e in roster['entries']):
            raise ValueError('family budget policy missing')
        return {}
    budgets = roster['family_budgets']
    if not isinstance(budgets, list) or not 0 < len(budgets) <= MAX_ENTRIES:
        raise ValueError('invalid family budget list')
    caps = {}
    for budget in budgets:
        if (not isinstance(budget, dict) or set(budget) != {'family', 'kind', 'nominal', 'min'}
                or not isinstance(budget['family'], str) or not CLASS.fullmatch(budget['family'].replace('-', '_'))
                or budget['kind'] not in KINDS or not _int(budget['nominal'], 0)
                or not _int(budget['min'], 0) or budget['min'] > budget['nominal']
                or budget['family'] in caps):
            raise ValueError('invalid or duplicate family budget')
        caps[budget['family']] = budget
    sums = {family: {'nominal': 0, 'min': 0} for family in caps}
    effective = {r['class']: r['candidate'] for r in rows} if rows is not None else None
    members = set()
    for entry in roster['entries']:
        family = entry.get('family')
        if family not in caps or caps[family]['kind'] != entry['kind']:
            raise ValueError(f'family budget membership missing: {entry["class"]}')
        members.add(family)
        if entry.get('disposition') not in {'curated-family-split', 'keep-native-budget', 'review-native-budget'}:
            raise ValueError(f'family disposition missing: {entry["class"]}')
        weight = entry.get('unit_rounds', 1)
        if not _int(weight, 1) or (entry['kind'] == 'ammo' and 'unit_rounds' not in entry) \
                or (entry['kind'] != 'ammo' and weight != 1):
            raise ValueError('family budget needs native ammo unit_rounds, or one item per weapon/magazine')
        parts = entry.get('parts', [])
        if not isinstance(parts, list) or len(parts) > 16 or (parts and entry['kind'] != 'weapon'):
            raise ValueError('invalid family part routes')
        for part in parts:
            if (not isinstance(part, dict) or set(part) != {'class', 'route'}
                    or not isinstance(part['class'], str) or not CLASS.fullmatch(part['class'])
                    or part['route'] not in {'native-integral', 'native-carrier'}):
                raise ValueError('unsupported family part route')
        candidate = entry['set'] if effective is None else effective.get(entry['class'])
        if candidate is not None:
            for field in sums[family]:
                sums[family][field] += candidate[field] * weight
    if members != set(caps):
        raise ValueError('family budget without members')
    for family, counts in sums.items():
        if any(counts[field] > caps[family][field] for field in counts):
            raise ValueError(f'family budget exceeded: {family}')
    refusals = roster.get('refusals', [])
    if (not isinstance(refusals, list) or len(refusals) > 16
            or any(not isinstance(code, str) or not re.fullmatch(r'HC21_[A-Z0-9_]{1,70}', code) for code in refusals)):
        raise ValueError('invalid HC-21 refusal list')
    return {'family_count': sum(c['kind'] == 'weapon' for c in caps.values()),
            'family_budget': sum(c['nominal'] for c in caps.values() if c['kind'] == 'weapon'),
            'families': [{'family': family, 'kind': cap['kind'], 'cap': {k: cap[k] for k in ('nominal', 'min')},
                          'candidate': sums[family], 'unit': 'max-cartridges' if cap['kind'] == 'ammo' else 'items'}
                         for family, cap in caps.items()],
            'boost': 'excluded', 'refusals': refusals, 'runtime_acceptance': 'pending',
            'policy_sha256': economy.sha(economy.encode(roster)),
            'operational_state': 'authored-runtime-pending',
            'admitted_families': None, 'observed_families': None}


def render_family_summary(roster):
    """Bounded generated documentation from the same validated policy used by both CE paths."""
    roster = selected_roster(roster)
    validate_roster(roster)
    totals = family_totals(roster)
    if not totals:
        raise ValueError('HC-21 summary requires family budgets')
    entries = roster['entries']
    weapons = [e for e in entries if e['kind'] == 'weapon']
    counts = {kind: sum(e['kind'] == kind for e in entries) for kind in KINDS}
    lines = ['<!-- HC21-GENERATED-BEGIN -->', '## Current authored family policy', '',
             f"Generated from `tools/package/firearms_roster.json`: {counts['weapon']} weapon classes, "
             f"{totals['family_count']} weapon families, {counts['magazine']} magazine classes and "
             f"{counts['ammo']} ammo sources (loose, boxed, tracer and specialist).", '',
             f"Weapon nominal ceiling: **{totals['family_budget']}**; with datamined rows omitted: "
             f"**{sum(e['set']['nominal'] for e in weapons if not e.get('datamined'))}**. "
             'These are provisional CE proposals for 3–6 players; runtime acceptance remains pending.', '',
             '| Family | Nominal / min cap | Explicit member shares (nominal / min) |',
             '| --- | --- | --- |']
    for budget in roster['family_budgets']:
        if budget['kind'] == 'weapon':
            members = [f"`{e['class']}` {e['set']['nominal']}/{e['set']['min']}" for e in weapons
                       if e['family'] == budget['family']]
            lines.append(f"| {budget['family']} | {budget['nominal']} / {budget['min']} | " + '; '.join(members) + ' |')
    lines += ['', '### Cartridge ceilings', '',
              'Each nominal/min is multiplied by `unit_rounds`: native pile maximum or box resource count. '
              'Detachable magazines have separate item budgets; loaded rounds and carrier throughput remain unmeasured.', '',
              '| Ammo family | Nominal / min maximum cartridges | Sources |', '| --- | --- | --- |']
    for budget in roster['family_budgets']:
        if budget['kind'] == 'ammo':
            names = [f"`{e['class']}` {e['set']['nominal']}/{e['set']['min']} × {e['unit_rounds']}"
                     for e in entries if e['family'] == budget['family']]
            lines.append(f"| {budget['family']} | {budget['nominal']} / {budget['min']} | " + '; '.join(names) + ' |')
    native_count = sum(e['disposition'] in {'keep-native-budget', 'review-native-budget'} for e in weapons)
    lines += ['', '### Formerly off-roster positives', '',
              f'All {native_count} are retained explicitly. Counts follow the selected economy profile; '
              'skin members share the family ceiling. `review-native-budget` preserves SV98 while refusing functional acceptance.', '',
              '| Class | Disposition | Family |', '| --- | --- | --- |']
    lines += [f"| `{e['class']}` | {e['disposition']} | {e['family']} |" for e in weapons
              if e['disposition'] in {'keep-native-budget', 'review-native-budget'}]
    lines += ['', 'Named pending refusals:', ''] + [f'- `{code}`' for code in totals['refusals']]
    lines += ['', '<!-- HC21-GENERATED-END -->']
    return '\n'.join(lines) + '\n'


def reviewed_type(name, stock, roster=None):
    """Narrow installer seam: full reviewed parent row with only authored nominal/min shares.

    economy.install uses this helper. All other fields, the independent NEW_TYPE_PARENTS
    allowlist and new-entry permissions stay exact.
    """
    roster = selected_roster(roster if roster is not None else json.loads(ROSTER_PATH.read_bytes()))
    validate_roster(roster)
    item = economy.datamined_items.reviewed_new_type(name, stock)
    if 'family_budgets' in roster:
        entry = next((e for e in roster['entries'] if e['class'] == name), None)
        if entry is None:
            raise ValueError(f'reviewed class missing from roster: {name}')
        if roster.get('economy_profile') == 'test-abundance':
            _apply(item, entry, set(entry['set_usage']), set(entry['set_value']))
        else:
            for field in ('nominal', 'min'):
                item.find(field).text = str(entry['set'][field])
    return item


def check_family_routes(source, roster, rows):
    """Verify declared native carrier references without creating parts or claiming assembly.

    Parent-cloned CE rows do not inherit their parent's cfgspawnabletypes definitions.
    Integral/default assemblies are deliberately never demanded as loose loot.
    """
    if 'family_budgets' not in roster:
        return
    needed = [(e, part) for e in roster['entries'] for part in e.get('parts', [])
              if part['route'] == 'native-carrier' and any(
                  r['class'] == e['class'] and r['candidate']['nominal'] > 0 for r in rows)]
    if not needed:
        return
    path = 'cfgspawnabletypes.xml'
    if not os.path.lexists(economy.child(source, path)):
        raise ValueError('HC21_PART_ROUTE_MISSING: cfgspawnabletypes.xml')
    root = economy.xml(economy.read_plain(source, path), 'spawnabletypes')
    wanted = {entry['class'] for entry, _ in needed}
    hosts = economy._unique([host for host in root.findall('type') if host.get('name') in wanted])
    for entry, part in needed:
        host = hosts.get(entry['class'])
        groups = [] if host is None else host.findall('attachments')
        if not any(float(group.get('chance', '0')) > 0 and any(
                item.get('name') == part['class'] and float(item.get('chance', '0')) > 0
                for item in group.findall('item')) for group in groups):
            raise ValueError(f'HC21_PART_ROUTE_MISSING: {entry["class"]}/{part["class"]}')


def _row(item):
    return {'nominal': int(item.findtext('nominal')), 'min': int(item.findtext('min')),
            'lifetime': int(item.findtext('lifetime')), 'restock': int(item.findtext('restock')),
            'usage': [n.get('name') for n in item.findall('usage')],
            'value': [n.get('name') for n in item.findall('value')]}


def _apply(item, entry, usage_vocab, value_vocab):
    # Only the two reviewed native SKS rows lack a category. Installer permissions
    # independently allow this exact addition and retain every other native field.
    if entry['class'] in {'SKS_Black', 'SKS_Green'} and item.find('category') is None:
        item.append(ET.Element('category', {'name': 'weapons'}))
    for field, value in entry['set'].items():
        node = item.find(field)
        if node is None:
            raise ValueError(f'stock lacks {field}: {entry["class"]}')
        node.text = str(value)
    positions = [i for i, n in enumerate(item) if n.tag == 'usage']
    if not positions:
        if not any(f in entry for f in ('add_usage', 'set_usage')):
            raise ValueError(f'stock entry has no usage to extend: {entry["class"]}')
        # Unused stock rows may carry no usage at all: the declared usage goes before any value tag.
        first_value = next((i for i, n in enumerate(item) if n.tag == 'value'), len(item))
        positions = [first_value]
    old = [n.get('name') for n in item.findall('usage')]
    if 'add_usage' in entry or 'set_usage' in entry:
        requested = entry.get('set_usage', entry.get('add_usage', []))
        if any(u not in usage_vocab for u in requested + (old if 'set_usage' not in entry else [])):
            raise ValueError(f'unknown usage: {entry["class"]}')
        merged = sorted(set(requested) if 'set_usage' in entry else set(old) | set(requested))
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
    if any('family' in entry for entry in entries):
        # The supplied entries are the policy, including for a custom --roster. Their
        # authored weighted shares bound effective rows; never substitute the shipped file.
        caps = {}
        for entry in entries:
            family = entry.get('family')
            cap = caps.setdefault(family, {'family': family, 'kind': entry['kind'], 'nominal': 0, 'min': 0})
            for field in ('nominal', 'min'):
                cap[field] += entry['set'][field] * entry.get('unit_rounds', 1)
        roster = {'entries': entries, 'family_budgets': list(caps.values())}
        effective_rows = _effective_family_rows(roster, effective_lower)
        family_totals(roster, effective_rows)
        check_family_routes(source, roster, effective_rows)


def _effective_family_rows(roster, effective_lower):
    return [{'class': entry['class'], 'candidate': {
        field: int(effective_lower[entry['class'].lower()].findtext(field) or 0)
        if entry['class'].lower() in effective_lower else 0 for field in ('nominal', 'min')}}
        for entry in roster['entries']]


def roster_items(stock, usage_vocab, value_vocab, roster, include_datamined=True):
    """Pure roster pass shared by the firearms-only delta and the combined economy delta.

    Returns ``(changed_elements, report_rows, totals)``; ``stock`` is economy's name -> <type> map.
    """
    roster = selected_roster(roster)
    validate_roster(roster)
    changed_elements = []
    rows, totals = [], {'weapon_nominal_stock': 0, 'weapon_nominal_candidate': 0}
    for kind in KINDS:
        for phase in ('stock', 'candidate'):
            totals[kind + '_nominal_' + phase] = 0
    stock_lower = {class_name.lower(): type_item for class_name, type_item in stock.items()}
    if len(stock_lower) != len(stock):
        raise ValueError('case-insensitive duplicate stock class')
    if 'family_budgets' in roster:
        named = {e['class'].lower() for e in roster['entries']}
        unaccounted = sorted(item.get('name') for low, item in stock_lower.items()
                             if low.startswith(('ammo_', 'ammobox_', 'mag_')) and low not in named
                             and int(item.findtext('nominal') or 0) > 0)
        if unaccounted:
            raise ValueError('HC21_UNACCOUNTED_SUPPORT: ' + ','.join(unaccounted[:16]))
    for entry in roster['entries']:
        name = entry['class']
        if entry.get('datamined') and not include_datamined:
            continue
        stock_row = None
        if 'new_type_parent' in entry:
            original = stock_lower.get(name.lower())
            item = reviewed_type(name, stock, roster)
            if original is not None:
                stock_row = _row(original)
            if any(node.get('name') not in usage_vocab for node in item.findall('usage')):
                raise ValueError(f'unknown parent usage: {name}')
            if any(node.get('name') not in value_vocab for node in item.findall('value')):
                raise ValueError(f'unknown parent value tier: {name}')
            changed = True
        elif name.lower() in stock_lower:
            original = stock_lower[name.lower()]
            economy._validate_budget(original)
            item = copy.deepcopy(original)
            _apply(item, entry, usage_vocab, value_vocab)
            stock_row = _row(original)
            changed = ET.tostring(item) != ET.tostring(original)
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
        if 'family' in entry:
            rows[-1].update(family=entry['family'], disposition=entry['disposition'],
                            unit_rounds=entry.get('unit_rounds'), parts=entry.get('parts', []),
                            runtime_acceptance='pending')
        if stock_row is not None:
            totals[entry['kind'] + '_nominal_stock'] += stock_row['nominal']
        totals[entry['kind'] + '_nominal_candidate'] += rows[-1]['candidate']['nominal']
    effective = dict(stock)
    effective.update({item.get('name'): item for item in changed_elements})
    effective_lower = {class_name.lower(): type_item for class_name, type_item in effective.items()}
    check_support([e for e in roster['entries'] if include_datamined or not e.get('datamined')],
                  lambda name: _nominal(effective_lower, name))
    totals.update(family_totals(roster, _effective_family_rows(roster, effective_lower)))
    return changed_elements, rows, totals


def generate(source, roster, include_datamined=True):
    roster = selected_roster(roster)
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
    check_family_routes(source, roster, rows)
    out.extend(changed)
    fragment = ET.Element('economycore')
    if len(out):
        ce = ET.SubElement(fragment, 'ce', {'folder': economy.MANAGED + '/ce'})
        ET.SubElement(ce, 'file', {'name': 'types.xml', 'type': 'types'})
    report = {'schema': 1, 'kind': 'firearms-roster', 'profile': roster['name'], 'economy_profile': roster.get('economy_profile', 'legacy'), 'players': roster['players'],
              'status': 'offline-only-runtime-pending', 'loot_fix_claim': False,
              'engine_merge_semantics': 'unobserved', 'entries': rows, 'totals': totals,
              'datamined': {'enabled': bool(include_datamined), 'classes': datamined},
              'deferred_datamined': roster['deferred_datamined'], 'runtime_acceptance': 'pending',
              'population_budget': 'roster counts are proposals for 3-6 players; effective world totals unobserved',
              'pending': ['normal PBO/server load', 'CE spawn/error trials', '3-6-player budget measurement',
                          'local acceptance of every datamined candidate', 'destination rollback']}
    files = {'ce/types.xml': xml_text.document(out) + b'\n',
             'cfgeconomycore.append.xml': xml_text.document(fragment) + b'\n',
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
    roster = selected_roster(roster)
    validate_roster(roster)
    profile = profile or {'schema': 1, 'name': roster['name'], 'add_usage': {}, 'diagnostics': []}
    files = economy.generate(source, profile, include_datamined=include_items, roster=roster,
                             include_roster_datamined=include_datamined)
    report = json.loads(files['economy-report.json'])
    check_family_routes(source, roster, report['firearms']['entries'])
    return files


write_delta = economy.write_delta
rollback = economy.rollback


def install(stage, target):
    """The single installer: per-class permissions come from the delta manifest."""
    return economy.install_delta(stage, target)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('summary', help='print current authored HC-21 documentation; no native claims')
    p.add_argument('--roster', type=Path, default=ROSTER_PATH)
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
        if args.command == 'summary':
            print(render_family_summary(json.loads(args.roster.read_bytes())), end='')
            return
        elif args.command == 'generate':
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
