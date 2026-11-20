"""Minimal native CE deltas, isolated installation and byte-exact rollback.

Generate reads installed stock. Install/rollback target an explicitly chosen
stopped, private mission copy, never the Steam installation. No placement edits.
"""
import argparse
from collections import Counter
import contextlib
import copy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import xml.etree.ElementTree as ET

try:
    from tools.package import ce_extensions, datamined_items
    from tools.package import xml_text
    from tools.package import xml_text
except ImportError:  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.package import ce_extensions, datamined_items
    from tools.package import xml_text
    from tools.package import xml_text

INPUTS = ('cfgeconomycore.xml', 'db/types.xml', 'cfglimitsdefinition.xml',
          'mapgroupproto.xml', 'mapgrouppos.xml')
LOG_NAMES = {'log_ce_lootspawn', 'log_ce_lootcleanup', 'log_ce_lootrespawn',
             'log_ce_statistics', 'log_missionfilewarning', 'log_hivewarning'}
DELTA_FILES = {'ce/types.xml', 'cfgeconomycore.append.xml', 'core-defaults.patch.json',
               'economy-report.json', 'delta-manifest.json'}
MANAGED = 'hollow-country'
# Child tags an installed candidate may change relative to stock. Default is usage only; a
# caller (the firearms roster) may widen it to budget/tier tags, never flags, cost or quantities.
MUTABLE_DEFAULT = frozenset({'usage'})
MUTABLE_ALLOWED = frozenset({'usage', 'value', 'nominal', 'min', 'lifetime', 'restock'})
# The datamined non-weapon rows (datamined_items.py) may change MUTABLE_ALLOWED on their own classes only.
# A category may be ADDED, never changed, only on a named class whose stock row has none, and only as
# the declared category (class -> category).
CATEGORY_ADDED = {'FilteringBottle': 'tools', 'SKS_Black': 'weapons', 'SKS_Green': 'weapons'}



# Reviewed CE acquisition rows; built entities (Fence, Watchtower, TerritoryFlag,
# Shelter*) remain native persistence rows and are never rewritten here.
CONSTRUCTION_KITS = {
    'FenceKit': (20, 12, ('Farm', 'Industrial')),
    'WatchtowerKit': (8, 4, ('Farm', 'Industrial')),
    'TerritoryFlagKit': (4, 2, ('Industrial',)),
    'ShelterKit': (16, 8, ('Farm', 'Hunting')),
}


def construction_kit(stock, name):
    """Clone native quantity/count/persistence fields; author only reviewed acquisition."""
    row = copy.deepcopy(stock[name])
    nominal, minimum, usages = CONSTRUCTION_KITS[name]
    for field, value in (('nominal', nominal), ('min', minimum), ('lifetime', 14400)):
        row.find(field).text = str(value)
    row.find('flags').set('crafted', '0')
    for field in ('category', 'tag', 'usage'):
        for node in list(row.findall(field)):
            row.remove(node)
    ET.SubElement(row, 'category', {'name': 'tools'})
    ET.SubElement(row, 'tag', {'name': 'shelves'})
    for usage in usages:
        ET.SubElement(row, 'usage', {'name': usage})
    _validate_budget(row)
    return row


def placement_budget(layers, proto_bytes, pos_bytes):
    """Offline usage/tag pressure estimate, never engine-qualified placement capacity.

    Later type layers replace earlier rows. Nominals with several usages/tags
    are divided evenly (they are alternatives, not independent populations).
    Container slots are bounded by physical points and group lootmax; shared
    group headroom is divided proportionally, then divided across usage/tag
    alternatives. Category, tier, item size and live occupancy can reduce actual
    capacity further. Wildcard buckets describe unrestricted rows/groups, not
    a separate exclusive route. These are pressure estimates, not placeable-point
    certification or independent route capacities.
    """
    rows = {}
    for data in layers:
        rows.update(_unique(xml(data, 'types').findall('type')))
    placed = Counter(g.get('name') for g in xml(pos_bytes, 'map').findall('group'))
    proto = xml(proto_bytes, 'prototype')
    defaults = {d.get('name'): int(d.get('lootmax', '0')) for d in proto.iter('default')}
    buckets = {}
    def bucket(usage, tag):
        return buckets.setdefault(usage + '/' + tag, {'nominal': 0.0, 'point_slots': 0.0})
    for row in rows.values():
        nominal = int(row.findtext('nominal') or 0)
        usages = [n.get('name') for n in row.findall('usage')] or ['*']
        tags = [n.get('name') for n in row.findall('tag')] or ['*']
        for usage in usages:
            for tag in tags:
                bucket(usage, tag)['nominal'] += nominal / (len(usages) * len(tags))
    for group in proto.findall('group'):
        usages = [u.get('name') for u in group.findall('usage')] or ['*']
        containers = [(c, min(int(c.get('lootmax', str(defaults.get('container', 0)))),
                              len(c.findall('point')))) for c in group.findall('container')]
        total = sum(n for c, n in containers)
        slots = min(int(group.get('lootmax', str(defaults.get('group', 0)))), total)
        for container, count in containers:
            tags = [t.get('name') for t in container.findall('tag')] or ['*']
            for usage in usages:
                for tag in tags:
                    bucket(usage, tag)['point_slots'] += (count * slots / max(1, total)
                        * placed[group.get('name')] / (len(usages) * len(tags)))
    return {'runtime_acceptance': 'pending', 'method': 'usage/tag alternatives split evenly; shared group slots proportional; geometry eligibility unobserved',
            'nominal': sum(int(r.findtext('nominal') or 0) for r in rows.values()),
            'by_usage_tag': {k: {f: round(v, 3) for f, v in values.items()}
                             for k, values in sorted(buckets.items())}}


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
    if len(data) > 16 * 1024 * 1024:
        raise ValueError('unsupported XML declarations or size')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeError as e:
        raise ValueError('XML must use UTF-8') from e
    if '\x00' in text or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('unsupported XML declarations or encoding')
    try:
        root = ET.fromstring(text)
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


def _refuse_collisions(profile_names, roster_names, item_names):
    """One class may be changed by only one source: a second <type> for it would be ambiguous."""
    def lower(names):
        return {n.lower() for n in names if isinstance(n, str)}
    prof, ros, items = lower(profile_names), lower(roster_names), lower(item_names)
    for label, a, b in (('roster class also named by the profile add_usage', ros, prof),
                        ('datamined class also named by the profile add_usage', items, prof),
                        ('roster class also a datamined item class', ros, items)):
        clash = sorted(a & b)
        if clash:
            raise ValueError(f'{label} (case-insensitive): ' + ', '.join(clash))


def generate(source, profile, include_datamined=True, roster=None, include_roster_datamined=True,
             authored_types=None):
    """One delta from the profile, the optional firearms roster and the datamined non-weapon items.

    ``authored_types`` (bytes of the shipped mission/hollow-country/ce/types.xml) names classes that
    the authored CE file already carries as complete rows; their roster rows are left out of the
    delta so one class never has two CE owners (travel refuses a second owner at install).
    """
    _validate_profile(profile)
    if roster is not None:
        try:
            from tools.package import firearms
        except ImportError:  # pragma: no cover - script mode
            import firearms
        roster = firearms.selected_roster(roster)
        firearms.validate_roster(roster)
        roster_names = [e['class'] for e in roster['entries']
                        if include_roster_datamined or not e.get('datamined')]
    else:
        roster_names = []
    item_rows = datamined_items.load_rows() if include_datamined else []
    _refuse_collisions(profile['add_usage'], roster_names, [r['class'] for r in item_rows])
    # The existing named pilot opts into HC-22; keep the public profile schema and
    # legacy/synthetic profiles intact. This is a content policy, not a module flag.
    supply = profile['name'] == 'contextual-pilot'
    supply_refused = []
    if supply and include_datamined:
        item_rows, supply_refused = datamined_items.supply_rows(
            item_rows, datamined_items.load_supply_dispositions())
    data = snapshot(source)
    core = ce_extensions.checked_core(data['cfgeconomycore.xml'])
    registered = ce_extensions.registered_types(source, core)
    types = _unique(xml(data['db/types.xml'], 'types').findall('type'))
    limits = xml(data['cfglimitsdefinition.xml'], 'lists')
    vocabulary = _unique(limits.findall('./usageflags/usage'))
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
    firearms_report = firearms_classes = None
    if roster is not None:
        value_vocab = _unique(limits.findall('./valueflags/value'))
        changed, rows, totals = firearms.roster_items(types, vocabulary, value_vocab, roster,
                                                      include_roster_datamined)
        firearms.check_family_routes(source, roster, rows)
        if authored_types is not None:
            owned = {n.get('name', '').casefold() for n in xml(authored_types, 'types').findall('type')}
            changed = [n for n in changed if n.get('name', '').casefold() not in owned]
        out.extend(changed)
        firearms_classes = sorted(n.get('name') for n in changed)
        firearms_report = {
            'enabled': True, 'profile': roster['name'],
            'economy_profile': roster.get('economy_profile', 'legacy'), 'players': roster['players'], 'entries': rows,
            'totals': totals,
            'datamined': {'enabled': bool(include_roster_datamined),
                          'classes': sorted(e['class'] for e in roster['entries'] if e.get('datamined'))},
            'deferred_datamined': roster['deferred_datamined']}
    datamined_report = None
    if include_datamined:
        datamined = datamined_items.type_rows(types, vocabulary, rows=item_rows, include_new=supply, floor=supply)
        emitted = {n.get('name') for n in datamined}
        absent = sorted(r['class'] for r in item_rows if r['class'] not in emitted)
        out.extend(datamined)
        by_class = {r['class']: r for r in item_rows}
        datamined_report = {'enabled': True, 'classes': sorted(emitted),
                            'acceptance': datamined_items.ACCEPTANCE, 'stock_absent_not_emitted': absent,
                            'rows': [{'class': n, 'acceptance': by_class[n]['acceptance'],
                                      'nominal': by_class[n]['nominal'], 'min': by_class[n]['min'],
                                      'lifetime': by_class[n]['lifetime'], 'restock': by_class[n]['restock'],
                                      'usage': sorted(by_class[n]['usage']), 'value': sorted(by_class[n]['value']),
                                      'stock_nominal': int(types[n].findtext('nominal')) if n in types else None}
                                     for n in sorted(emitted)],
                            'note': 'budgets are proposals; CE spawn of unused vanilla rows is unobserved'}
    if supply:
        authored = {n.get('name') for n in xml(authored_types, 'types')} if authored_types else set()
        for name in CONSTRUCTION_KITS:
            if name in types and name not in authored:
                out.append(construction_kit(types, name))
    ce_extensions.refuse_collisions((n.get('name') for n in out), registered)
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
              'population_budget': 'selected roster budgets override stock; native flags retained; effective merging and world totals unobserved',
              'datamined': datamined_report or {'enabled': False, 'classes': []},
              'firearms': firearms_report or {'enabled': False},
              'pending': ['DayZDiag eligibility/geometry', 'normal PBO/server load',
                          'CE spawn/error trials', '3-6-player budget measurement',
                          'two-client multiplayer', 'destination rollback']}
    if supply:
        report['supply'] = {
            'wp': 'HC-22', 'state': 'authored' if include_datamined else 'off',
            'authored': len(datamined_items.load_rows()),
            'admitted': len(datamined_report['classes']) if datamined_report else 0,
            'floor_refused': len(supply_refused), 'refusals': supply_refused,
            'refused_by_route': dict(Counter(r['route'] for r in supply_refused)),
            'refused_by_reason': dict(Counter(r['reason'] for r in supply_refused)),
            'observed': 0, 'extra_cold': 0, 'runtime_acceptance': 'pending',
            'dispositions_sha256': sha(datamined_items.supply_disposition_bytes()),
            'note': 'admitted counts candidate XML rows, never native spawns; off leaves native stock intact'}
    patches = {n: {'before': defaults[n].get('value'), 'after': 'true'} for n in profile['diagnostics']}
    files = {'ce/types.xml': xml_text.document(out) + b'\n',
             'cfgeconomycore.append.xml': xml_text.document(fragment) + b'\n',
             'core-defaults.patch.json': encode(patches), 'economy-report.json': encode(report)}
    files['delta-manifest.json'] = encode({'schema': 1, 'profile': profile['name'],
        'sources': {n: sha(d) for n, d in data.items()},
        'files': {n: sha(d) for n, d in files.items()}, 'runtime_acceptance': 'pending',
        'datamined_classes': datamined_report['classes'] if datamined_report else [],
        'firearms_classes': firearms_classes or [],
        'new_type_classes': sorted(n.get('name') for n in out if n.get('name') not in types
                                  and n.get('name') in datamined_items.NEW_TYPE_PARENTS),
        'supply_new_type_classes': sorted(n.get('name') for n in out if n.get('name') not in types
                                         and n.get('name') in datamined_items.SUPPLY_NEW_TYPES)})
    return files


# ------------------------------------------------------------------------------------------------ essential routes
# AC-004 / CE-006 (T012): every essential has at least two distinct credible routes. A route is one civilian usage
# flag whose buildings (placed in mapgrouppos) hold a container that accepts the item. This is an OFFLINE count of
# eligible opportunities: it is not an observed spawn, and the CE tag/usage semantics assumed below are unobserved.
# Cargo presets (cfgspawnabletypes holders) are listed as `carried` evidence only and never count as a route.

ROUTE_POLICY = Path(__file__).with_name('essential_routes.json')
ROUTE_POLICY_KIND = 'hollow-country-essential-routes'
ROUTE_COLUMNS = ('role', 'item', 'required', 'verdict', 'route_count', 'routes', 'weak_routes', 'row_source',
                 'carried', 'categories', 'usage', 'usage_semantics', 'tags', 'tag_rule', 'nominal_stock', 'nominal_effective',
                 'min_buildings', 'types_sha256', 'proto_sha256', 'layers', 'runtime_acceptance')
TAG_RULE = 'tags-must-match-when-both-sides-declare(assumed)'
ANY_USAGE = 'empty-usage-any-assumed'


def parse_route_policy(data):
    try:
        doc = json.loads(data)
    except ValueError as error:
        raise ValueError('essential route policy is not JSON') from error
    if (not isinstance(doc, dict) or doc.get('schema') != 1 or doc.get('kind') != ROUTE_POLICY_KIND
            or type(doc.get('min_buildings')) is not int or doc['min_buildings'] < 1
            or not isinstance(doc.get('excluded_usages'), list)
            or not all(isinstance(u, str) for u in doc['excluded_usages'])
            or not isinstance(doc.get('roles'), list) or not doc['roles']):
        raise ValueError('unsupported essential route policy')
    seen = set()
    for role in doc['roles']:
        if (not isinstance(role, dict) or not re.fullmatch(r'[a-z_]{1,32}', str(role.get('role', '')))
                or not isinstance(role.get('items'), list) or not role['items']):
            raise ValueError('essential role needs a label and items')
        for item in role['items']:
            name = item.get('class') if isinstance(item, dict) else None
            if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_]{1,80}', name)
                    or not isinstance(item.get('required'), bool) or name in seen):
                raise ValueError('essential item needs a unique class and a required flag')
            seen.add(name)
    return doc


def _row_fields(row):
    return {'categories': sorted(c.get('name') for c in row.findall('category')),
            'usage': sorted(u.get('name') for u in row.findall('usage')),
            'tags': sorted(t.get('name') for t in row.findall('tag')),
            'nominal': int(row.findtext('nominal') or 0)}


def _route_groups(proto_bytes, pos_bytes, overlay):
    """[(group name, usages, placed buildings, [(categories, tags, points)])] for every lootable stock group."""
    from tools.package import loot_boost
    placed = {}
    for group in xml(pos_bytes, 'map').findall('group'):
        placed[group.get('name')] = placed.get(group.get('name'), 0) + 1
    out = []
    wanted = (overlay or {}).get('groups', {})
    for group in xml(proto_bytes, 'prototype').iter('group'):
        name = group.get('name')
        if group.get('lootmax') == '0':
            continue
        containers = [(frozenset(c.get('name') for c in cont.findall('category')),
                       frozenset(t.get('name') for t in cont.findall('tag')), len(cont.findall('point')))
                      for cont in group.findall('container')]
        spec = wanted.get(name)
        if spec is not None and spec['stock_sha256'] == loot_boost.group_pin(group):
            containers += [(frozenset(c['categories']), frozenset(c['tags']), len(c['points']))
                           for c in spec['containers'].values()]
        out.append((name, frozenset(u.get('name') for u in group.findall('usage')), placed.get(name, 0), containers))
    return out


def _carried_routes(spawnable_bytes, presets_bytes):
    """{item: (sorted preset names, holder class count)}: cargo/attachment presets and inline items on spawnable holders."""
    if spawnable_bytes is None:
        return {}
    presets = {}
    if presets_bytes is not None:
        for preset in xml(presets_bytes, 'randompresets'):
            presets[preset.get('name')] = [i.get('name') for i in preset.iter('item')]
    holders, names = {}, {}
    for holder in xml(spawnable_bytes, 'spawnabletypes').findall('type'):
        for part in holder:
            ref = part.get('preset')
            items = presets.get(ref, []) if ref else [i.get('name') for i in part.iter('item')]
            for item in items:
                holders.setdefault(item, set()).add(holder.get('name'))
                if ref:
                    names.setdefault(item, set()).add(ref)
    return {item: (sorted(names.get(item, ())), len(found)) for item, found in holders.items()}


def _count_routes(row, groups, vocabulary, excluded):
    fields = _row_fields(row)
    wanted_usage = fields['usage'] or sorted(vocabulary)
    cats, tags = set(fields['categories']), set(fields['tags'])
    counts = {}
    for usage in wanted_usage:
        if usage in excluded:
            continue
        total = 0
        for _name, usages, placed, containers in groups:
            if usage not in usages:
                continue
            if any(cats & c_cats and (not tags or not c_tags or tags & c_tags) for c_cats, c_tags, _p in containers):
                total += placed
        counts[usage] = total
    return fields, counts


def route_report(layers, proto_bytes, pos_bytes, limits_bytes, policy_bytes, overlay=None, multiplier=None,
                 spawnable_bytes=None, presets_bytes=None):
    """Route rows for the essential list. `layers` is [(label, types bytes)]; a later layer replaces a row by name."""
    policy = parse_route_policy(policy_bytes)
    vocabulary = {u.get('name') for u in xml(limits_bytes, 'lists').iter('usage')}
    rows_by_name = {}
    for label, data in layers:
        for row in xml(data, 'types').findall('type'):
            rows_by_name[row.get('name')] = (label, row)
    stock_rows = {row.get('name'): row for row in xml(layers[0][1], 'types').findall('type')}
    groups = _route_groups(proto_bytes, pos_bytes, overlay)
    carried = _carried_routes(spawnable_bytes, presets_bytes)
    excluded, minimum = set(policy['excluded_usages']), policy['min_buildings']
    boost = None
    if multiplier is not None:
        from tools.package import loot_boost
        boost = (loot_boost, loot_boost._roster_names())
    out, failing, unresolved = [], [], []
    for role in policy['roles']:
        for item in role['items']:
            name = item['class']
            row = {'role': role['role'], 'item': name, 'required': item['required'], 'min_buildings': minimum,
                   'types_sha256': sha(layers[0][1])[:12], 'proto_sha256': sha(proto_bytes)[:12],
                   'layers': '+'.join(label for label, _ in layers), 'tag_rule': TAG_RULE,
                   'runtime_acceptance': 'pending', 'routes': '', 'weak_routes': '', 'route_count': 0,
                   'row_source': '', 'carried': '', 'categories': '', 'usage': '', 'usage_semantics': '', 'tags': '',
                   'nominal_stock': '', 'nominal_effective': ''}
            if name not in rows_by_name:
                row['verdict'] = 'absent'
            else:
                label, element = rows_by_name[name]
                fields, counts = _count_routes(element, groups, vocabulary, excluded)
                credible = sorted((u, n) for u, n in counts.items() if n >= minimum)
                presets, holders = carried.get(name, ([], 0))
                weak = sorted((u, n) for u, n in counts.items() if 0 < n < minimum)
                row.update({'row_source': label, 'categories': ';'.join(fields['categories']),
                            'usage': ';'.join(fields['usage']), 'tags': ';'.join(fields['tags']),
                            'usage_semantics': 'explicit' if fields['usage'] else ANY_USAGE,
                            'routes': ';'.join('%s:%d' % r for r in credible),
                            'weak_routes': ';'.join('%s:%d' % r for r in weak),
                            'route_count': len(credible),
                            'carried': ('%s:%d' % ('+'.join(presets) or 'inline', holders)) if holders else '',
                            'nominal_effective': fields['nominal']})
                if name in stock_rows:
                    row['nominal_stock'] = _row_fields(stock_rows[name])['nominal']
                if boost and boost[0]._scales(fields['categories'], name, boost[1]):
                    row['nominal_effective'] = boost[0].scaled(fields['nominal'], multiplier)
                if not fields['categories']:
                    row['verdict'] = 'no-building-route'
                elif row['route_count'] >= 2:
                    row['verdict'] = 'pass'
                else:
                    row['verdict'] = 'fail-routes'
            if row['verdict'] != 'pass' and item['required']:
                failing.append(name)
            if row['verdict'] == 'no-building-route' and item['required']:
                unresolved.append(name)
            out.append(row)
    return {'rows': out, 'failing': sorted(failing), 'unresolved': sorted(unresolved), 'policy': policy}


def route_csv(report):
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=ROUTE_COLUMNS, lineterminator='\n')
    writer.writeheader()
    for row in report['rows']:
        writer.writerow({k: ('true' if row[k] is True else 'false' if row[k] is False else row[k])
                         for k in ROUTE_COLUMNS})
    return buffer.getvalue().encode()


def routes_for_mission(mission, repo, profile_name='contextual-pilot'):
    """Route report for a stock mission (read only) with the committed economy delta, authored CE rows and boost."""
    from tools.package import loot_boost
    repo = Path(repo)
    data = snapshot(mission)
    profile = json.loads((repo / 'mission/hollow-country/economy-profiles' / (profile_name + '.json')).read_bytes())
    roster = json.loads((repo / 'tools/package/firearms_roster.json').read_bytes())
    delta = generate(mission, profile, roster=roster)['ce/types.xml']
    carried = {n: _read_optional(Path(mission), n) for n in ('cfgspawnabletypes.xml', 'cfgrandompresets.xml')}
    authored = (repo / 'mission/hollow-country/ce/types.xml').read_bytes()
    overlay = loot_boost.parse_overlay((repo / loot_boost.ADDITIONS).read_bytes())
    return route_report(
        [('stock', data['db/types.xml']), (profile_name, delta), ('authored-ce', authored)],
        data['mapgroupproto.xml'], data['mapgrouppos.xml'], data['cfglimitsdefinition.xml'],
        (repo / 'tools/package/essential_routes.json').read_bytes(), overlay=overlay,
        multiplier=loot_boost.default_multiplier(repo), spawnable_bytes=carried['cfgspawnabletypes.xml'],
        presets_bytes=carried['cfgrandompresets.xml'])


def _read_optional(mission, name):
    path = child(mission, name)
    return path.read_bytes() if path.is_file() else None


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
    core = ce_extensions.checked_core(original)
    frag = xml(fragment, 'economycore')
    if any(x.tag != 'ce' or x.attrib != {'folder': MANAGED + '/ce'}
           or len(x) != 1 or x[0].tag != 'file'
           or x[0].attrib != {'name': 'types.xml', 'type': 'types'} for x in frag) or len(frag) > 1:
        raise ValueError('unsupported CE registration')
    if len(frag) and any(ce.get('folder') == MANAGED + '/ce' for ce in core.findall('ce')):
        raise ValueError('CE folder already registered: ' + MANAGED + '/ce')
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


def plain_file(root, path):
    """Refuse anything but a single-link regular file that resolves inside root.

    Hard links are refused because writing through one would modify a file outside the mission.
    """
    root, path = Path(root).absolute(), Path(path).absolute()
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise ValueError(f'managed path is a symlink, hard link or not a regular file: {path.name}')
    resolved = path.resolve(strict=True)
    if resolved != root.resolve(strict=True) / path.relative_to(root):
        raise ValueError('managed path resolves outside its directory')
    return path


def read_plain(root, name):
    return plain_file(root, child(root, name)).read_bytes()


def fresh_write(root, name, data):
    """Create name fresh (O_EXCL). A stale regular file is unlinked, never written through."""
    path = child(root, name)
    if os.path.lexists(path):
        plain_file(root, path)
        path.unlink()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o666)
    with os.fdopen(fd, 'wb') as f:
        f.write(data)
    return path


def preflight_managed(managed, expected):
    """Every managed entry must be expected, plain and single-link before anything is modified."""
    managed = Path(managed)
    for p in managed.rglob('*'):
        name = p.relative_to(managed).as_posix()
        child(managed, name)
        if p.is_dir() and not p.is_symlink():
            if name != 'ce':
                raise ValueError('unexpected managed directory; rollback refuses deletion')
            continue
        if name not in expected:
            raise ValueError('unexpected managed file; rollback refuses deletion')
        plain_file(managed, p)


ROLLED_BACK = 'rolled_back'
RECOVERED_BOOTSTRAP = 'recovered_bootstrap'
RECEIPT = 'receipt'
HEX64 = re.compile(r'[0-9a-f]{64}')


class MissingEvidence(ValueError):
    """Required managed evidence is absent. A refusal: rollback changed nothing and must not be read as a noop."""


@contextlib.contextmanager
def refuse_missing(managed):
    """Inside a rollback, a vanished file is MissingEvidence once the managed directory exists.

    With no managed directory a FileNotFoundError is the honest answer: nothing was installed.
    """
    try:
        yield
    except FileNotFoundError:
        if not os.path.lexists(managed):
            raise
        raise MissingEvidence('required managed evidence is missing; rollback refuses and changed nothing') from None


def validate_receipt(receipt, digests=('types_sha256',), optional=()):
    """Refuse a receipt that is not complete before any branch can delete anything because of it."""
    if not isinstance(receipt, dict):
        raise ValueError('unsupported receipt; rollback refuses')
    if type(receipt.get('schema')) is not int or receipt['schema'] != 1:
        raise ValueError('unsupported receipt schema; rollback refuses')
    keys = ('before', 'after') + tuple(digests) + tuple(k for k in optional if k in receipt)
    for key in keys:
        if not isinstance(receipt.get(key), str) or not HEX64.fullmatch(receipt[key]):
            raise ValueError(f'incomplete receipt ({key}); rollback refuses')
    sources = receipt.get('sources')
    if (not isinstance(sources, dict) or set(sources) != set(INPUTS)
            or any(not isinstance(v, str) or not HEX64.fullmatch(v) for v in sources.values())
            or sources['cfgeconomycore.xml'] != receipt['before']):
        raise ValueError('incomplete receipt (sources); rollback refuses')
    return receipt


def read_receipt_or_recover(target, managed, core_name='cfgeconomycore.xml', backup_name='core.backup',
                            digests=('types_sha256',), optional=()):
    """Return (RECEIPT, receipt) or, after clearing an install that died before a complete receipt, (RECOVERED_BOOTSTRAP, None).

    The outcome is a tag, never something parsed from receipt.json: a file holding ``null`` or any other
    non-object is refused, not mistaken for recovery. Install writes a complete core.backup (staged as
    core.backup.next, then renamed) and only then receipt.json, so a managed directory with no complete
    receipt can hold nothing but those backups, a possibly half-written receipt.json and staging files, and
    the core is still the original. That is re-proved before anything is removed: no other managed entry,
    every entry a plain file, and the core byte-identical to EVERY backup present (core.backup and
    core.backup.next). Anything else, including a half-written staged backup, refuses and changes nothing.
    """
    managed = Path(managed)
    path = managed / 'receipt.json'
    if os.path.lexists(path):
        try:
            receipt = json.loads(read_plain(managed, 'receipt.json'))
        except json.JSONDecodeError:
            pass  # half-written receipt: only the bootstrap evidence rules can clear it
        else:
            return RECEIPT, validate_receipt(receipt, digests, optional)
    elif not os.path.lexists(managed):
        read_plain(managed, 'receipt.json')  # raises the usual FileNotFoundError: nothing installed
    if not managed.is_dir() or managed.is_symlink():
        raise ValueError('managed path is not a plain directory; rollback refuses')
    staged = backup_name + '.next'
    entries = {}
    for entry in managed.rglob('*'):
        name = entry.relative_to(managed).as_posix()
        child(managed, name)
        if entry.is_dir() or name not in {backup_name, staged, 'receipt.json', 'receipt.next'}:
            raise ValueError('no valid receipt and unexpected managed content; rollback refuses deletion')
        entries[name] = plain_file(managed, entry).read_bytes()
    core = plain_file(target, child(target, core_name)).read_bytes()
    for name in (backup_name, staged):
        if name in entries and core != entries[name]:
            raise ValueError(f'no valid receipt and the core differs from {name}; manual reconciliation required')
    if 'receipt.json' in entries and backup_name not in entries:
        raise ValueError('no valid receipt and no backup to prove the core is unchanged; manual reconciliation required')
    shutil.rmtree(managed)  # only our fixed directory, preflighted above
    return RECOVERED_BOOTSTRAP, None


COMPLETE = 'complete.json'
COMPLETE_STAGED = 'complete.next'


def completion_evidence(receipt_bytes):
    """The marker an install writes last, after the core switch: it binds completion to this exact receipt."""
    return encode({'schema': 1, 'receipt_sha256': sha(receipt_bytes)})


def read_completion(managed):
    """True when a valid completion marker is present, False when absent; a present but wrong marker refuses.

    Without the marker a no-op install (before == after) cannot tell drift after success from an interrupted
    write, so the marker is what keeps the drift refusal once an install has finished.
    """
    if not os.path.lexists(child(managed, COMPLETE)):
        return False
    if read_plain(managed, COMPLETE) != completion_evidence(read_plain(managed, 'receipt.json')):
        raise ValueError('completion marker does not match the receipt; manual reconciliation required')
    return True


def needs_restore(managed, receipt, core_sha, delta, completed=False):
    """Whether the install reached its core switch, proving the delta files whole when it did.

    delta lists (file, receipt key, drift message) in install write order. The core hash shows the switch
    only when the patch changed the core. When before == after it cannot, so the delta files decide: each file
    is whole, or it is the last one written (the frontier) with nothing written after it. Absent or partial
    delta with an unchanged core means the switch never happened; and an unchanged core never needs restoring.
    ``completed`` is True when the install's completion marker was proven: every delta file must then be whole,
    so a changed or missing one is drift or missing evidence, never a frontier.
    """
    if receipt['before'] != receipt['after']:
        if core_sha != receipt['after']:
            return False  # install died before the switch: delta files may be absent or partial
        for name, key, message in delta:
            if sha(read_plain(managed, name)) != receipt[key]:
                raise ValueError(message)
        return True
    if completed:
        for name, key, message in delta:
            if not os.path.lexists(child(managed, name)):
                raise MissingEvidence(f'required managed evidence is missing: {name}; rollback refuses')
            if sha(read_plain(managed, name)) != receipt[key]:
                raise ValueError(message)
        return False
    for i, (name, key, message) in enumerate(delta):
        present = os.path.lexists(child(managed, name))
        if present and sha(read_plain(managed, name)) == receipt[key]:
            continue
        if any(os.path.lexists(child(managed, n)) for n in [d[0] for d in delta[i + 1:]] + ['core.next']):
            if not present:
                raise MissingEvidence(f'required managed evidence is missing: {name}; rollback refuses')
            raise ValueError(message)
        break  # the frontier: absent or partial, nothing written after it
    return False


def restore_core(managed, core, backup):
    """Stage the backup as a fresh file in the managed directory and atomically swap it in."""
    staged = fresh_write(managed, 'core.next', backup)
    os.replace(staged, core)


def _full(element):
    """Complete subtree identity: tag, attributes, text and every descendant."""
    return (element.tag, tuple(sorted(element.attrib.items())), (element.text or '').strip(),
            tuple(_full(n) for n in element))


def _retained(item, allowed, skip_category=False):
    """The type's identity with only its DIRECT children of the allowed tags set aside.

    Everything else, including any descendant of a retained child, is compared completely.
    """
    return (item.tag, tuple(sorted(item.attrib.items())), (item.text or '').strip(),
            tuple(_full(n) for n in item if n.tag not in allowed and not (skip_category and n.tag == 'category')))


def _check_supply_ledger(files, manifest, supply_new_types):
    """Bind HC-22 install admission to the same authored ledger used by generation."""
    report = json.loads(files['economy-report.json'])
    if ('supply' in report or manifest.get('profile') == 'contextual-pilot' or supply_new_types):
        digest = sha(datamined_items.supply_disposition_bytes())
        supply = report.get('supply')
        if not isinstance(supply, dict) or supply.get('dispositions_sha256') != digest:
            raise ValueError('HC22_DISPOSITIONS_HASH_MISMATCH')


def install(stage, target, mutable=MUTABLE_DEFAULT, widened=frozenset(), datamined=frozenset(),
            new_types=frozenset(), supply_new_types=frozenset()):
    """Install a staged delta.

    ``mutable`` is the field set every row may change (default usage only). ``widened`` names the classes
    that may change MUTABLE_ALLOWED (firearms and datamined rows); ``datamined`` names the classes that may
    additionally ADD the one category CATEGORY_ADDED declares for them. Profile rows stay at ``mutable``.
    ``new_types`` explicitly admits only NEW_TYPE_PARENTS additions. Their full row must equal the
    reviewed stock-parent clone with authored family shares, including all flags, tags and placement fields.
    Reviewed variants already in stock (including case aliases) use that same strict parent comparison
    when widened by the roster; unrelated stock classes retain the original per-field rules.
    ``supply_new_types`` separately admits only the exact HC-22 bandana rows.
    An authored HC-22 supply report permits only the 17 fixed floor rows to clear
    crafted, with deloot additionally cleared only for TortillaBag_Desert.
    """
    mutable = frozenset(mutable)
    widened = frozenset(widened) | frozenset(datamined)
    datamined = frozenset(datamined)
    new_types = frozenset(new_types)
    supply_new_types = frozenset(supply_new_types)
    if not new_types <= set(datamined_items.NEW_TYPE_PARENTS):
        raise ValueError('new class is not on the reviewed allowlist')
    if (not supply_new_types <= datamined_items.SUPPLY_NEW_TYPES
            or not supply_new_types <= datamined):
        raise ValueError('HC22_NEW_TYPE_NOT_REVIEWED')
    if 'usage' not in mutable or not mutable <= MUTABLE_ALLOWED:
        raise ValueError('unsupported mutable field set')
    target = _target(target)
    files, manifest = _load_delta(stage)
    _check_supply_ledger(files, manifest, supply_new_types)
    floor_supply = json.loads(files['economy-report.json']).get('supply', {}).get('state') == 'authored'
    data = snapshot(target)
    if {n: sha(d) for n, d in data.items()} != manifest['sources']:
        raise ValueError('target source hashes differ; regenerate/reconcile')
    managed = child(target, MANAGED)
    if managed.exists():
        raise ValueError('already installed or interrupted installation; inspect/rollback first')
    original = data['cfgeconomycore.xml']
    patched = _patched_core(original, files['cfgeconomycore.append.xml'], json.loads(files['core-defaults.patch.json']))
    types = xml(files['ce/types.xml'], 'types')
    ce_extensions.refuse_collisions(
        _unique(types.findall('type')),
        ce_extensions.registered_types(target, ce_extensions.checked_core(original)))
    stock = _unique(xml(data['db/types.xml'], 'types').findall('type'))
    vocabulary = _unique(xml(data['cfglimitsdefinition.xml'], 'lists').findall('./usageflags/usage'))
    _unique(types.findall('type'))
    if len({name.lower() for name in stock}) != len(stock):
        raise ValueError('case-insensitive duplicate stock class')
    for item in types:
        name = item.get('name')
        if item.tag != 'type':
            raise ValueError('candidate must retain every stock field except the mutable set')
        if name in supply_new_types:
            if any(n.lower() == name.lower() for n in stock):
                raise ValueError('HC22_NEW_TYPE_ALREADY_IN_STOCK: ' + name)
            expected_supply = datamined_items.reviewed_supply_type(name)
            if _full(item) != _full(expected_supply):
                raise ValueError('HC22_NEW_TYPE_DRIFT: ' + name)
            if any(n.get('name') not in vocabulary for n in item.findall('usage')):
                raise ValueError('HC22_NEW_TYPE_USAGE: ' + name)
            _validate_budget(item)
            continue
        reviewed_name = next((policy_name for policy_name in datamined_items.NEW_TYPE_PARENTS
                              if policy_name.lower() == name.lower()), None)
        if reviewed_name is not None and (name in new_types or name in widened):
            if name not in stock and name not in new_types:
                raise ValueError('new class needs explicit reviewed new-type permission')
            from tools.package import firearms
            expected_new = firearms.reviewed_type(reviewed_name, stock)
            _validate_budget(expected_new)
            if _full(item) != _full(expected_new):
                raise ValueError(f'new class must exactly clone its reviewed parent with the authored family share: {name}')
            new_usages = item.findall('usage')
            _unique(new_usages)
            if not new_usages or any(node.get('name') not in vocabulary for node in new_usages):
                raise ValueError('invalid new-type usage')
            continue
        if name not in stock:
            raise ValueError('new class needs explicit reviewed new-type permission')
        if name in CONSTRUCTION_KITS:
            if _full(item) != _full(construction_kit(stock, name)):
                raise ValueError('construction kit differs from reviewed native clone: ' + name)
            if any(n.get('name') not in vocabulary for n in item.findall('usage')):
                raise ValueError('construction kit usage unavailable: ' + name)
            continue
        allowed = mutable | MUTABLE_ALLOWED if name in widened else mutable
        # A category may only be added, once, as the declared category, where stock has none.
        add_category = (name in datamined or name in widened) and name in CATEGORY_ADDED and stock[name].find('category') is None
        if add_category:
            cats = item.findall('category')
            if len(cats) > 1 or any(dict(c.attrib) != {'name': CATEGORY_ADDED[name]} or len(c) or (c.text or '').strip()
                                    for c in cats):
                raise ValueError(f'invalid category addition (only {CATEGORY_ADDED[name]!r} is declared): {name}')
        retained_item = item
        if floor_supply and name in datamined and name in datamined_items.SUPPLY_UNVERIFIED_FLOOR:
            # Only these reviewed rows may clear crafted (and Tortilla's deloot).
            # Compare the complete flags node, including structure and every count flag.
            expected_flags = copy.deepcopy(stock[name].find('flags'))
            expected_flags.set('crafted', '0')
            if name == 'TortillaBag_Desert':
                expected_flags.set('deloot', '0')
            candidate_flags = item.findall('flags')
            if len(candidate_flags) != 1 or _full(candidate_flags[0]) != _full(expected_flags):
                raise ValueError('HC22_FLOOR_FLAGS_DRIFT: ' + name)
            retained_item = copy.deepcopy(item)
            retained_item.find('flags').attrib.clear()
            retained_item.find('flags').attrib.update(stock[name].find('flags').attrib)
        if _retained(retained_item, allowed, add_category) != _retained(stock[name], allowed, add_category):
            raise ValueError('candidate must retain every stock field except the mutable set')
        for n in item:  # a changed tag is a plain value: no attributes beyond the name, no descendants
            if n.tag in allowed and (len(n) or set(n.attrib) != ({'name'} if n.tag in {'usage', 'value'} else set())):
                raise ValueError(f'mutable field must be a plain value: {name}')
        _validate_budget(item)
        usages = item.findall('usage')
        _unique(usages)
        if not usages or any(set(n.attrib) != {'name'} or n.get('name') not in vocabulary or len(n) for n in usages):
            raise ValueError('invalid complete-entry usage override')
        if not {n.get('name') for n in stock[name].findall('usage')} <= {n.get('name') for n in usages}:
            # Replacement is narrower than generic widening: only the selected shipped
            # roster's explicit, exact usage list can remove a native usage (e.g. gas-only M4).
            from tools.package import firearms
            policy = firearms.selected_roster(json.loads(firearms.ROSTER_PATH.read_bytes()))
            firearms.validate_roster(policy)
            entry = next((e for e in policy['entries'] if e['class'].lower() == name.lower()), None)
            if (name not in widened or entry is None or not entry.get('set_usage')
                    or {n.get('name') for n in usages} != set(entry['set_usage'])):
                raise ValueError('usage removal forbidden')
    managed.mkdir()
    receipt = {'schema': 1, 'before': sha(original), 'after': sha(patched),
               'types_sha256': sha(files['ce/types.xml']), 'sources': manifest['sources']}
    receipt_bytes = encode(receipt)
    # Receipt+backup exist before the atomic core switch. Rollback also handles
    # an interrupted install whose switch did not happen. Stop the server first.
    try:
        os.replace(fresh_write(managed, 'core.backup.next', original), managed / 'core.backup')  # never half-written
        fresh_write(managed, 'receipt.json', receipt_bytes)
        (managed / 'ce').mkdir()
        fresh_write(managed, 'ce/types.xml', files['ce/types.xml'])
        os.replace(fresh_write(managed, 'core.next', patched), child(target, 'cfgeconomycore.xml'))
        # last, published by rename so a kill never leaves a half-written marker
        os.replace(fresh_write(managed, COMPLETE_STAGED, completion_evidence(receipt_bytes)), managed / COMPLETE)
    except OSError:
        # Receipt/backup precede the core switch. A failed write before that
        # switch has changed no mission input; remove only preflighted intent.
        if read_plain(target, 'cfgeconomycore.xml') == original:
            preflight_managed(managed, {'core.backup', 'core.backup.next', 'receipt.json', 'ce/types.xml', 'core.next',
                                         COMPLETE, COMPLETE_STAGED})
            shutil.rmtree(managed)
        raise
    return receipt


def install_delta(stage, target):
    """Install a generated delta once, with per-class permissions taken from its manifest.

    datamined_classes must be shipped datamined rows (they may also add the declared category);
    firearms_classes are roster rows (budget fields only); every other row is usage-only.
    new_type_classes must be both rostered and in the separate reviewed parent allowlist.
    supply_new_type_classes must be fixed HC-22 bandanas also named by datamined_classes.
    """
    _files, manifest = _load_delta(stage)
    lists = {}
    for key in ('datamined_classes', 'firearms_classes', 'new_type_classes', 'supply_new_type_classes'):
        listed = manifest.get(key, [])
        if (not isinstance(listed, list) or any(not isinstance(n, str) or not re.fullmatch(r'[A-Za-z0-9_]{1,80}', n)
                                                for n in listed) or len(set(listed)) != len(listed)):
            raise ValueError(f'delta manifest has an invalid {key}')
        lists[key] = frozenset(listed)
    # Fail with the missing-ledger diagnostic even from a portable export that
    # omits the repo-only roster tooling. No target writes precede this check.
    _check_supply_ledger(_files, manifest, lists['supply_new_type_classes'])
    from tools.package import firearms
    roster = firearms.selected_roster(json.loads(firearms.ROSTER_PATH.read_bytes()))
    firearms.validate_roster(roster)
    if not {name.lower() for name in lists['firearms_classes']} <= {r['class'].lower() for r in roster['entries']}:
        raise ValueError('delta manifest names a class that is not in the shipped firearms roster')
    reviewed = {r['class'] for r in roster['entries'] if 'new_type_parent' in r}
    if (not lists['new_type_classes'] <= reviewed
            or not lists['new_type_classes'] <= set(datamined_items.NEW_TYPE_PARENTS)
            or not lists['new_type_classes'] <= lists['firearms_classes']):
        raise ValueError('delta new classes must be reviewed roster additions')
    shipped = {r['class'] for r in datamined_items.load_rows()}
    if not lists['datamined_classes'] <= shipped:
        raise ValueError('delta manifest names a class that is not a shipped datamined row')
    if (not lists['supply_new_type_classes'] <= datamined_items.SUPPLY_NEW_TYPES
            or not lists['supply_new_type_classes'] <= lists['datamined_classes']):
        raise ValueError('HC22_NEW_TYPE_NOT_REVIEWED')
    if {n.lower() for n in lists['firearms_classes']} & {n.lower() for n in lists['datamined_classes']}:
        raise ValueError('delta manifest lists a firearms class that is also a datamined class')
    if lists['firearms_classes']:
        stock = _unique(xml(read_plain(_target(target), 'db/types.xml'), 'types').findall('type'))
        candidates = xml(_files['ce/types.xml'], 'types')
        firearms.check_effective_support(target, stock, roster['entries'], candidates)
    return install(stage, target, widened=lists['firearms_classes'], datamined=lists['datamined_classes'],
                   new_types=lists['new_type_classes'], supply_new_types=lists['supply_new_type_classes'])


def rollback(target):
    """Undo an install: returns ROLLED_BACK, or RECOVERED_BOOTSTRAP for an install killed before its receipt.

    A core still equal to the backup means the switch never happened (the delta files may then be absent or
    partial and are not compared); a core equal to the receipt's installed digest must carry every delta file
    whole. Equal before/after digests are decided by the delta files (needs_restore). Missing evidence is a
    MissingEvidence refusal, never a FileNotFoundError, once the managed directory exists.
    """
    target = _target(target)
    managed = child(target, MANAGED)
    with refuse_missing(managed):
        outcome, receipt = read_receipt_or_recover(target, managed)
        if outcome == RECOVERED_BOOTSTRAP:
            return outcome
        preflight_managed(managed, {'core.backup', 'receipt.json', 'ce/types.xml', 'core.next', COMPLETE,
                                    COMPLETE_STAGED})  # a staged marker never proves completion
        completed = read_completion(managed)
        core = plain_file(target, child(target, 'cfgeconomycore.xml'))
        backup = read_plain(managed, 'core.backup')
        core_sha = sha(core.read_bytes())
        if sha(backup) != receipt['before'] or core_sha not in {receipt['before'], receipt['after']}:
            raise ValueError('core drift; manual reconciliation required')
        switched = needs_restore(managed, receipt, core_sha,
                                 [('ce/types.xml', 'types_sha256', 'installed delta drift; inspect before rollback')],
                                 completed)
        if {n: sha(child(target, n).read_bytes()) for n in INPUTS if n != 'cfgeconomycore.xml'} != {
                n: h for n, h in receipt['sources'].items() if n != 'cfgeconomycore.xml'}:
            raise ValueError('stock drift; inspect before rollback')
        if switched:
            restore_core(managed, core, backup)
        shutil.rmtree(managed)  # only our fixed directory, preflighted above
        return ROLLED_BACK


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('generate')
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--profile', type=Path, required=True)
    p.add_argument('--roster', type=Path, default=None,
                   help='compose this firearms roster (e.g. tools/package/firearms_roster.json) into the one delta')
    p.add_argument('--no-datamined', action='store_true',
                   help='leave every datamined non-weapon item row (acceptance: pending-local) out of the delta')
    p.add_argument('--no-roster-datamined', action='store_true',
                   help='leave the roster\'s datamined weapon/magazine rows (pending-local) out of the delta')
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('routes', help='essential two-route check (AC-004); reads the mission, never writes it')
    p.add_argument('--source', type=Path, required=True, help='stock mission directory (read only)')
    p.add_argument('--profile', default='contextual-pilot', help='economy profile name under economy-profiles/')
    p.add_argument('--out', type=Path, default=None, help='write the CSV here (default: print the summary only)')
    p = sub.add_parser('install')
    p.add_argument('--delta', type=Path, required=True)
    p.add_argument('--target', type=Path, required=True)
    p = sub.add_parser('rollback')
    p.add_argument('--target', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'generate':
            write_delta(args.out, generate(
                args.source, json.loads(args.profile.read_bytes()), include_datamined=not args.no_datamined,
                roster=json.loads(args.roster.read_bytes()) if args.roster else None,
                include_roster_datamined=not args.no_roster_datamined))
        elif args.command == 'routes':
            report = routes_for_mission(args.source, Path(__file__).resolve().parents[2], args.profile)
            if args.out:
                args.out.write_bytes(route_csv(report))
            for row in report['rows']:
                print('%-8s %-24s %-17s routes=%s' % (row['role'], row['item'], row['verdict'], row['routes']))
            print('essentials failing=%s unresolved=%s; offline eligibility only, runtime acceptance pending'
                  % (report['failing'], report['unresolved']))
            return
        elif args.command == 'install':
            install_delta(args.delta, args.target)
        else:
            if rollback(args.target) == RECOVERED_BOOTSTRAP:
                print('Recovered an interrupted install: it never changed the core; managed directory removed.')
        print('Offline operation complete; DayZ runtime acceptance pending.')
    except (ValueError, OSError, KeyError, TypeError) as e:
        parser.exit(1, f'{e}\n')


if __name__ == '__main__':
    main()
