"""Shared deterministic military CE budgets and read-only installed mission census.

Nominals are map-wide pools, not hard population caps or observed local counts.
The area map reader uses the native 4096-grid usage uint32 plane followed by
its uint8 value plane. Point shares are a planning estimate, never CE simulation.
"""
import argparse
from collections import Counter, defaultdict
import copy
import hashlib
from functools import lru_cache
import json
import math
import re
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / 'config/military-loot.json'
SOURCES = ('firearms_roster.json', 'snafu_allowlist.json', 'tactical_flava_allowlist.json')


def catalog():
    result = {}
    for source in SOURCES:
        data = json.loads((ROOT / 'tools/package' / source).read_bytes())
        families = {m['class']: m['family'] for m in data.get('hc61', {}).get('members', [])}
        for entry in data['entries']:
            row = copy.deepcopy(entry)
            if row['class'] in families:
                # Optional legacy families are whole-provider ceilings, not firearm models.
                row['family'] = re.sub(r'(?i)(_|^)(black|green|tan|snow|wood|woodland|dkmc|od|fde|camo)(_|$)', '_', row['class']).lower()
            row['usage'] = row.get('usage', row.get('set_usage', []))
            row['value'] = row.get('value', row.get('set_value', []))
            result[row['class']] = row
    return result


def item_kind(entry):
    kind = entry['kind']
    if kind == 'weapon':
        ammo = entry.get('ammo', []) + entry.get('vanilla_ammo', []) + entry.get('snafu_ammo', [])
        if any('bolt' in name.lower() for name in ammo):
            return 'archery'
        if any('40mm' in name.lower() for name in ammo):
            return 'launcher'
        return 'firearm'
    return kind


def effective_types(mission):
    """Case-insensitive last-definition wins in CE registration order."""
    paths = [Path('db/types.xml')]
    for ce in ET.parse(mission / 'cfgeconomycore.xml').getroot().findall('ce'):
        paths.extend(Path(ce.get('folder')) / f.get('name') for f in ce if f.get('type') == 'types')
    result = {}
    for path in paths:
        for row in ET.parse(mission / path).getroot():
            result[row.get('name').lower()] = (str(path.parent), row)
    return result


def census(mission):
    known = {k.lower(): v for k, v in catalog().items()}
    totals = defaultdict(lambda: [0, 0])
    distinct = defaultdict(lambda: [0, 0])
    for name, (source, row) in effective_types(mission).items():
        entry = known.get(name)
        kind = item_kind(entry) if entry else ('magazine' if name.startswith('mag_') else
               'ammo' if name.startswith(('ammo_', 'ammobox_')) else None)
        if kind is None:
            continue  # category=weapons also includes melee; never call those firearms
        cell = distinct[source, kind]
        cell[0] += 1
        cell[1] += int(row.findtext('nominal', '0'))
        for usage in [u.get('name') for u in row.findall('usage')] or ['*']:
            for tier in [v.get('name') for v in row.findall('value')] or ['*']:
                cell = totals[source, tier, usage, kind]
                cell[0] += 1
                cell[1] += int(row.findtext('nominal', '0'))
    print('source,tier,usage,kind,classes,nominal (multi-route rows occur in each route)')
    for key, counts in sorted(totals.items()):
        print(','.join(map(str, (*key, *counts))))
    print('distinct_source,kind,classes,nominal')
    for key, counts in sorted(distinct.items()):
        print(','.join(map(str, (*key, *counts))))
    return totals


def point_share(mission, bounds=(1000, 2500, 13200, 15000)):
    data = (mission / 'areaflags.map').read_bytes()
    width, height, world_x, world_z, bits = struct.unpack_from('<5I', data)
    cells = width * height
    if bits != 32 or struct.unpack_from('<I', data, 20 + cells * 4)[0] != 8 or len(data) != 24 + cells * 5:
        raise ValueError('unsupported area map layout')
    protos = {g.get('name'): g for g in ET.parse(mission / 'mapgroupproto.xml').getroot().findall('group')}
    totals = Counter()
    for group in ET.parse(mission / 'mapgrouppos.xml').getroot():
        proto = protos.get(group.get('name'))
        if proto is None:
            continue
        x, _, z = map(float, group.get('pos').split())
        index = min(height-1, max(0, int(z * height / world_z))) * width + min(width-1, max(0, int(x * width / world_x)))
        usage = struct.unpack_from('<I', data, 20 + index * 4)[0]
        value = data[24 + cells * 4 + index]
        military = usage & 1 or any(u.get('name') == 'Military' for u in proto.findall('usage'))
        if not military or not value & 8:
            continue
        count = sum(len(c.findall('point')) for c in proto.findall('container')
                    if any(n.get('name') == 'weapons' for n in c.findall('category')))
        totals['all_tier4_military_weapon_points'] += count
        if bounds[0] <= x <= bounds[1] and bounds[2] <= z <= bounds[3]:
            totals['tisy_tier4_military_weapon_points'] += count
    all_points = totals['all_tier4_military_weapon_points']
    totals['tisy_share'] = totals['tisy_tier4_military_weapon_points'] / all_points if all_points else 0
    print(json.dumps({'tisy_bounds_xmin_xmax_zmin_zmax': bounds, **totals,
                      'includes': 'installed map positions and prototypes, including installed HC additions',
                      'estimate': 'equal eligible-point occupancy; CE selection/lootmax/tag effects unobserved'}, sort_keys=True))
    return totals


def load_rules():
    rules = json.loads(RULES.read_bytes())
    if rules['schema'] != 1 or rules['usage'] != 'Military' or set(rules['firearms']) != {'Tier1', 'Tier2', 'Tier3', 'Tier4'}:
        raise ValueError('invalid military loot rules')
    for tier, roles in rules['firearms'].items():
        if tier not in {'Tier1', 'Tier2', 'Tier3', 'Tier4'} or set(roles) != {'primary', 'secondary'}:
            raise ValueError('invalid military tier/roles')
        if any(type(n) is not int or n < 0 for n in roles.values()):
            raise ValueError('invalid military firearm budget')
    if set(rules['support_per_firearm']) != {'attachment', 'magazine', 'ammo'}:
        raise ValueError('invalid support kinds')
    for kind, ratio in rules['support_per_firearm'].items():
        if kind not in {'attachment', 'magazine', 'ammo'} or type(ratio) is not int or ratio < 0:
            raise ValueError('invalid support ratio')
    receivers = rules['weapon_receivers']
    if (set(receivers) != {'usages', 'comparable_categories'}
            or set(receivers['usages']) != {'Military', 'Police', 'Prison'}
            or set(receivers['comparable_categories']) != {'clothes', 'containers'}):
        raise ValueError('invalid military weapon receivers')
    share = rules.get('route_weapons')
    if (not isinstance(share, dict) or set(share) != {'per_family', 'floor', 'shared'}
            or type(share['shared']) is not bool
            or any(type(share[k]) is not int or share[k] < 1 for k in ('per_family', 'floor'))
            or share['per_family'] < share['floor']):
        raise ValueError('invalid route weapon share')
    quantity = rules['magazine_quantity_percent']
    if not 0 <= quantity['min'] < quantity['max'] <= 100:
        raise ValueError('invalid magazine quantity')
    if not 0 <= rules['min_fraction'] <= 1 or rules['lifetime_seconds'] <= 0 or rules['restock_seconds'] < 0:
        raise ValueError('invalid military replenishment')
    if set(rules['rarity_weights']) != {'common', 'uncommon', 'rare'} or any(
            type(n) is not int or n <= 0 for n in rules['rarity_weights'].values()):
        raise ValueError('invalid rarity weights')
    return rules


EVENT_USAGES = frozenset({'ContaminatedArea', 'Lunapark', 'Historical', 'SeasonalEvent'})
ROUTE_USAGES = {'Military', 'Police', 'Prison'}


def budgeted(row):
    """CE has one pool per class: keep every non-military route intact.

    Archery and launchers retain their authored policy, including dependencies.
    """
    return (set(row['usage']) == {'Military'} and
            item_kind(row) in {'firearm', 'attachment', 'magazine', 'ammo'})


def _fingerprint():
    paths = [RULES, ROOT / 'tools/package/military_loot_allowlist.json', ROOT / 'tools/package/loot_families.json']
    paths.extend(ROOT / 'tools/package' / source for source in SOURCES)
    return tuple(hashlib.sha256(path.read_bytes()).digest() for path in paths)


def allocation():
    return _allocation(_fingerprint())


def route_shares():
    """{class: nominal} of every route-only firearm (usage within Military, Police, Prison, with Military or Police):
    an equal share per gun family. Guns that also spawn in Town or Village keep their authored pools unless
    route_weapons.shared is true (then they take the share too, which cuts the civilian pools of those pistols).

    No vanilla priority (owner 2026-11-22): every family gets route_weapons.per_family (at least floor, the R2b
    minimum), whatever its source. A family of several colours spends its share as one base variant plus the
    others, so that it totals at most ceil(1.5 x its largest variant) (R3) with every variant at least 1; a family
    with too many variants for that rises to the smallest total that keeps both rules."""
    return dict(_route_shares(_fingerprint()))


@lru_cache(maxsize=4)
def _route_shares(fingerprint):
    from tools.package import loot_balance
    rules_all = load_rules()
    rules = rules_all['route_weapons']
    share = max(rules['per_family'], rules['floor'])
    entries = role_routes(list(catalog().values()))
    members = {}
    for entry in entries:
        usage = set(entry.get('set_usage', entry.get('usage', [])))
        # A gun that also spawns in Town or Village keeps its authored civilian pool (CE has one pool per class)
        # unless route_weapons.shared opts those in.
        if (entry['kind'] == 'weapon' and item_kind(entry) == 'firearm' and usage & {'Military', 'Police'}
                and (usage <= ROUTE_USAGES or rules_all['route_weapons']['shared'])):
            members.setdefault(loot_balance.family(entry['class']), []).append(entry['class'])
    result = {}
    for names in members.values():
        names = sorted(names, key=lambda name: (len(name), name))
        count = len(names)
        total = share if count == 1 else max(share, 3 * (count - 1))
        if count == 1:
            result[names[0]] = total
            continue
        largest = int(math.ceil(round(total / 1.5, 6)))
        result[names[0]] = largest
        rest = loot_balance.split([(name, 1) for name in names[1:]], total - largest)
        result.update(rest)
    return tuple(sorted(result.items()))


@lru_cache(maxsize=4)
def _allocation(fingerprint):
    """Reserve every class floor, then apportion spare units round-robin.

    Fail closed when configured ceilings cannot retain the authored catalog.
    Stable hash ordering avoids provider/alphabetical priority.
    """
    rules = load_rules()
    rows = catalog()
    secondary = set(json.loads((ROOT / 'tools/package/military_loot_allowlist.json').read_bytes())['secondary_firearms'])
    military = {name: row for name, row in rows.items() if budgeted(row)}
    counts = Counter()
    remaining = {(tier, role): n for tier, roles in rules['firearms'].items() for role, n in roles.items()}
    for tier, roles in rules['firearms'].items():
        for kind, ratio in rules['support_per_firearm'].items():
            remaining[tier, kind] = sum(roles.values()) * ratio
    families = Counter(row.get('family', name) for name, row in military.items())

    def role(name):
        kind = rows[name]['kind']
        return ('secondary' if name in secondary else 'primary') if kind == 'weapon' else kind

    # Reserve distinct native Tier4 choices first, then constrained classes, then
    # round-robin flexible classes over tiers with remaining floor capacity.
    native = {entry['class'] for entry in json.loads(
        (ROOT / 'tools/package' / SOURCES[0]).read_bytes())['entries'] if not entry.get('datamined')}
    floor_remaining = dict(remaining)
    tier_cursor = Counter()
    guns = [name for name, row in military.items() if row['kind'] == 'weapon']
    stable = lambda name: hashlib.sha256(name.encode()).hexdigest()
    fallback = sorted((name for name in guns if name in native and role(name) == 'primary'
                       and 'Tier4' in military[name]['value']), key=stable)[:3]
    for name in fallback:
        military[name]['value'] = ['Tier4']
    for name in sorted(guns, key=lambda name: (name not in fallback, len(military[name]['value']), stable(name))):
        row = military[name]
        tiers = sorted(t for t in row['value'] if t in rules['firearms'])
        choices = [t for t in tiers if floor_remaining[t, role(name)] > 0]
        if not choices:
            raise ValueError('military ceiling cannot retain class floor: ' + name)
        index = tier_cursor[role(name)]
        tier = next((tiers[(index + i) % len(tiers)] for i in range(len(tiers))
                     if tiers[(index + i) % len(tiers)] in choices))
        tier_cursor[role(name)] = tiers.index(tier) + 1
        row['value'] = [tier]
        floor_remaining[tier, role(name)] -= 1

    def routes(name):
        return [(tier, role(name)) for tier in military[name]['value'] if tier in rules['firearms']]

    def available(name):
        keys = routes(name)
        authored = rows[name]['set']['nominal']
        within_cartridge_ceiling = rows[name]['kind'] == 'weapon' or counts[name] < authored
        return authored > 0 and within_cartridge_ceiling and bool(keys) and all(remaining[key] > 0 for key in keys)

    def debit(name):
        counts[name] += 1
        for key in routes(name):
            remaining[key] -= 1

    def priority(name):
        row = rows[name]
        weight = rules['rarity_weights'][row['tier']] / families[row.get('family', name)]
        digest = hashlib.sha256(name.encode()).hexdigest()
        uniform = (int(digest[:13], 16) + 1) / (16**13 + 1)
        return (counts[name] * 1000 - math.log(uniform) / weight, digest)

    def distribute(names):
        while True:
            eligible = [name for name in names if available(name)]
            if not eligible:
                break
            debit(min(eligible, key=priority))

    # All support is retained, including parts used only by a colour variant.
    # A ceiling too small for these floors is an explicit policy error.
    for name in sorted(military, key=stable):
        keys = routes(name)
        if not keys or any(remaining[key] < 1 for key in keys):
            raise ValueError('military ceiling cannot retain class floor: ' + name)
        debit(name)
    distribute([name for name in military if rows[name]['kind'] == 'weapon'])
    distribute([name for name in military if rows[name]['kind'] != 'weapon'])
    return rows, counts, remaining


def check_retained(inputs, outputs):
    """Reject disappearing/zeroed weapon and support rows, case-insensitively.

    Inputs are policy entries; outputs may be policy entries or effective XML
    rows. An unchanged stock row is present in the effective output even when
    it needs no delta. Deliberate omissions such as --no-datamined are filtered
    by the caller before this check.
    """
    zeroed = json.loads((ROOT / 'tools/package/military_loot_allowlist.json').read_bytes())['zeroed']
    if not isinstance(zeroed, dict) or any(not isinstance(reason, str) or not reason.strip()
                                            for reason in zeroed.values()):
        raise ValueError('zeroed allowlist requires a nonempty reason per class')
    allowed = {name.lower() for name in zeroed}
    actual = {}
    for row in outputs:
        if isinstance(row, dict):
            actual[row['class'].lower()] = dict(row['set'])
            if 'usage' in row or 'set_usage' in row:
                actual[row['class'].lower()]['usage'] = row.get('set_usage', row.get('usage'))
        else:
            actual[row.get('name').lower()] = {'nominal': int(row.findtext('nominal', '0')),
                                              'min': int(row.findtext('min', '0')),
                                              'usage': [u.get('name') for u in row.findall('usage')]}
    errors = []
    for row in inputs:
        name = row['class']
        if row['kind'] not in {'weapon', 'magazine', 'attachment', 'ammo'} or name.lower() in allowed:
            continue
        candidate = actual.get(name.lower())
        if candidate is None or candidate['nominal'] < 1:
            errors.append(name + (':missing' if candidate is None else ':nominal=0'))
        elif ('usage' in candidate or 'usage' in row or 'set_usage' in row) and not candidate.get('usage'):
            errors.append(name + ':no usage')
        elif budgeted(dict(row, usage=row.get('usage', row.get('set_usage', [])))) and candidate['min'] < 1:
            errors.append(name + ':min=0')
    if errors:
        raise ValueError('HC_MILITARY_LOOT_RETENTION: ' + ', '.join(sorted(errors)))


def apply(entries):
    """Project only shipped classes; synthetic/custom policies keep their semantics."""
    shipped = catalog()
    if not any(entry['class'] in shipped for entry in entries):
        check_retained(entries, entries)
        return entries
    rules = load_rules()
    known, counts, _ = allocation()
    result = copy.deepcopy(entries)
    for entry in result:
        original = known.get(entry['class'])
        if original is None or not budgeted(original):
            continue
        nominal = counts[entry['class']]
        if item_kind(original) == 'firearm':
            if 'value' in entry:
                entry['value'] = original['value']
            if 'set_value' in entry:
                entry['set_value'] = original['value']
        entry['set'].update(nominal=nominal, min=min(nominal, math.ceil(nominal * rules['min_fraction'])),
                            lifetime=rules['lifetime_seconds'], restock=rules['restock_seconds'])
    result = role_routes(result)
    result = _equal_share(result, rules)
    result = _balance_packs(result, rules)
    check_retained(entries, result)
    return result


def pack_estimates():
    """{class: scaled entry} of both optional packs as the installer will write them (allowlist test_abundance_multiplier)
    -- the guns loot_boost cannot see when it balances the support rows they share with the roster."""
    return dict(_pack_estimates(_fingerprint()))


@lru_cache(maxsize=4)
def _pack_estimates(fingerprint):
    from tools.package import snafu_optional
    result = {}
    for source in SOURCES[1:]:
        data = json.loads((ROOT / 'tools/package' / source).read_bytes())
        entries, _, _ = snafu_optional._scaled_entries(data['entries'], data.get('test_abundance_multiplier', 1), None)
        result.update({entry['class']: entry for entry in entries})
    return tuple(sorted(result.items()))


def check_pack_family_caps():
    """The pack installers refuse a layer over its HC-61 family caps (HC61_FAMILY_BUDGET). The rows they write come
    from apply() (R4 floors included), so check them here, where no Workshop report is needed."""
    from tools.package import firearms, snafu_optional
    parts = []
    for source in SOURCES[1:]:
        data = json.loads((ROOT / 'tools/package' / source).read_bytes())
        roster = snafu_optional._family_policy(data)
        if roster is None:
            continue
        entries, _, _ = snafu_optional._scaled_entries(data['entries'], data.get('test_abundance_multiplier', 1), None)
        rows = [{'class': entry['class'], 'candidate': {field: entry['set'][field] for field in ('nominal', 'min')}}
                for entry in entries]
        try:
            firearms.family_totals(roster, rows)
        except ValueError as error:
            raise SystemExit(f'{source}: {error} (the pack installer would refuse this layer: raise the cap in '
                             f'hc61.family_budgets with a reason, or lower the rows)') from None
        parts.append(source.removesuffix('_allowlist.json') + '=' + str(len(rows)))
    return ' '.join(parts)


def _roster_classes():
    return {entry['class'] for entry in json.loads((ROOT / 'tools/package' / SOURCES[0]).read_bytes())['entries']}


def _set_nominal(entry, nominal, rules):
    old_min, old_nominal = entry['set'].get('min', 0), entry['set'].get('nominal', 0)
    if old_nominal and old_min:
        minimum = max(1, min(nominal, math.ceil(old_min * nominal / old_nominal)))
    else:
        minimum = old_min and min(nominal, old_min)
    entry['set'].update(nominal=nominal, min=minimum)


def _equal_share(result, rules):
    """Every firearm on the Military/Police route gets its family's equal share (route_shares)."""
    shares = route_shares()
    for entry in result:
        nominal = shares.get(entry['class'])
        if nominal is not None and entry['kind'] == 'weapon':
            entry['set'].update(nominal=nominal, min=min(nominal, math.ceil(nominal * rules['min_fraction'])))
    return result


def _balance_packs(result, rules):
    """R3/R1/re-investment/R2b among the optional-pack attachments and unrouted guns, then R4 for pack magazines.

    The roster rows are balanced later by loot_boost, which also sees stock rows and every scale; pack rows are
    installed after it, so they are balanced here against each other (their own category totals, no stock share)."""
    from tools.package import loot_balance
    roster = _roster_classes()
    known = catalog()
    shares = route_shares()
    rows = {}
    for entry in result:
        name = entry['class']
        if name in roster or name not in known or entry['set'].get('nominal', 0) <= 0:
            continue
        if entry['kind'] == 'attachment':
            rows[name] = {'category': 'attachments', 'nominal': entry['set']['nominal'], 'stock': 0}
        elif entry['kind'] == 'weapon':
            rows[name] = {'category': 'weapons', 'nominal': entry['set']['nominal'], 'stock': 0,
                          'locked': name in shares}
    if rows:
        changed, _ = loot_balance.balance(rows)
        by_class = {entry['class']: entry for entry in result}
        for name, nominal in changed.items():
            _set_nominal(by_class[name], nominal, rules)
    support = {}
    for entry in result:
        name = entry['class']
        if entry['kind'] in {'magazine', 'ammo'} and name not in roster and entry['set'].get('nominal', 0) > 0:
            support[name] = {'category': entry['kind'] + 's', 'nominal': entry['set']['nominal'], 'stock': 0}
    if support:  # R2b only: the shares of a pack-private pool are not capped by a category total
        changed, _ = loot_balance.balance(support, r3=frozenset(), share=1.0)
        by_class = {entry['class']: entry for entry in result}
        for name, nominal in changed.items():
            _set_nominal(by_class[name], nominal, rules)
    ammo = {entry['class']: entry['set']['nominal'] for entry in result
            if entry['kind'] == 'ammo' and entry['class'] not in roster and entry['set'].get('nominal', 0) > 0}
    mags = {entry['class']: entry['set']['nominal'] for entry in result
            if entry['kind'] == 'magazine' and entry['class'] not in roster and entry['set'].get('nominal', 0) > 0}
    guns = {}
    for entry in result:
        if entry['kind'] == 'weapon' and entry['class'] not in roster and entry['set'].get('nominal', 0) > 0:
            source = known[entry['class']]
            listed = source.get('ammo', []) + source.get('vanilla_ammo', []) + source.get('snafu_ammo', [])
            guns[entry['class']] = {'nominal': entry['set']['nominal'], 'ammo': [a for a in listed if a in ammo],
                                    'magazines': [m for m in source.get('magazines', []) if m in mags]}
    if guns and (ammo or mags):
        added, _ = loot_balance.support_floors(guns, ammo, mags)
        by_class = {entry['class']: entry for entry in result}
        for name, add in added.items():
            _set_nominal(by_class[name], by_class[name]['set']['nominal'] + add, rules)
    return result


def role_routes(entries):
    """Expand shipped routes from roles/families and weapon dependency edges.

    Apply AFTER shared budget allocation: Police access must not exempt a
    military class from its ceiling. Custom/synthetic policies are untouched.
    No tags are added: native firearms use category=weapons without a tag
    restriction, which also admits floor/shelf containers of that category.
    """
    known = catalog()
    weapons = {name: row for name, row in known.items() if row['kind'] == 'weapon'}
    routes, tiers = {}, {}
    for name, row in weapons.items():
        usage = set(row['usage'])
        if item_kind(row) == 'firearm' and 'Military' in usage:
            usage.add('Police')
        if row['role'] == 'police' or usage == {'Police'}:
            usage.add('Prison')
        if 'Hunting' in usage or item_kind(row) == 'archery':
            usage.update(('Hunting', 'Farm', 'Town', 'Village'))
        routes[name] = usage
        tiers[name] = (set(('Tier1', 'Tier2', 'Tier3', 'Tier4'))
                       if usage & {'Hunting', 'Town', 'Village', 'Farm'} else set(row['value']))
    family_routes = defaultdict(set)
    for name, row in weapons.items():
        family_routes[row.get('family', name)].update(routes[name])
    for name, row in weapons.items():
        routes[name].update(family_routes[row.get('family', name)])
    parents = defaultdict(set)
    for name, weapon in weapons.items():
        for field in ('magazines', 'ammo', 'vanilla_ammo', 'snafu_ammo', 'optic_requires'):
            for child in weapon.get(field, []):
                parents[child.lower()].add(name)
    result = copy.deepcopy(entries)
    for entry in result:
        name = entry['class']
        if name not in known:
            continue
        usage_key = 'set_usage' if 'set_usage' in entry else 'usage'
        value_key = 'set_value' if 'set_value' in entry else 'value'
        if entry['kind'] == 'weapon':
            usage = routes[name]
            # Keep the allocated military tier; civilian/hunting choices must
            # reach vanilla deer stands throughout the map's value plane.
            values = tiers[name] if usage & {'Hunting', 'Town', 'Village', 'Farm'} else set(entry[value_key])
        else:
            carriers = parents[name.lower()] | set(known[name].get('fits', []))
            usage = set(entry[usage_key])
            values = set(entry[value_key])
            for parent in carriers:
                if parent in routes:
                    usage.update(routes[parent])
                    values.update(tiers[parent])
        entry[usage_key] = sorted(usage)
        entry[value_key] = sorted(values)
        if 'usage' in entry and 'set_usage' in entry:
            entry['usage'] = entry['set_usage']
        if 'value' in entry and 'set_value' in entry:
            entry['value'] = entry['set_value']
    return result



def spread_proto(data):
    """Admit weapons on existing contextual floor proxies; never raise caps.

    These points already carry bulky clothing/containers. Keep their tags and
    geometry: the matching type-side exception is applied after floor retagging.
    """
    from tools.package import xml_text
    root = ET.fromstring(data)
    rules = load_rules()['weapon_receivers']
    defaults = {d.get('name'): int(d.get('lootmax')) for d in root.findall('./defaults/default') if d.get('lootmax') is not None}
    changed = []
    for group in root.findall('group'):
        if (not {u.get('name') for u in group.findall('usage')} & set(rules['usages'])
                or int(group.get('lootmax', defaults.get('group', 12))) <= 0):
            continue
        for container in group.findall('container'):
            cats = {c.get('name') for c in container.findall('category')}
            tags = {t.get('name') for t in container.findall('tag')}
            if (container.get('name', '').startswith('lootHC')
                    or 'weapons' in cats or not cats & set(rules['comparable_categories'])
                    or not tags or not tags <= {'floor', 'shelves'}
                    or not container.findall('point')
                    or int(container.get('lootmax', defaults.get('container', 8))) <= 0):
                continue
            ET.SubElement(container, 'category', {'name': 'weapons'})
            changed.append(group.get('name') + '/' + container.get('name'))
    return (xml_text.document(root) if changed else data), {'containers': sorted(changed),
            'caps_changed': 0, 'points_added': 0, 'runtime_acceptance': 'pending'}


def spread_types(data):
    """Apply narrow post-floor-policy exceptions, including reviewed kit routes.

    Native weapon tags and matching modded tags receive the same floor access.
    All budgets, tiers, usages, flags and non-selected rows are preserved.
    """
    from tools.package import economy, xml_text
    root = ET.fromstring(data)
    usages = set(load_rules()['weapon_receivers']['usages'])
    kits = {name.lower() for name in economy.CONSTRUCTION_KITS}
    changed = []
    for row in root:
        if int(row.findtext('nominal', '0')) <= 0:
            continue
        cats = {c.get('name') for c in row.findall('category')}
        military_weapon = ('weapons' in cats and
            bool({u.get('name') for u in row.findall('usage')} & usages))
        if row.get('name').lower() not in kits and not military_weapon:
            continue
        tags = {t.get('name') for t in row.findall('tag')}
        # No tags already means unrestricted. Leave unrelated authored tags alone.
        if tags and tags <= {'floor', 'shelves'} and 'floor' not in tags:
            ET.SubElement(row, 'tag', {'name': 'floor'})
            changed.append(row.get('name'))
    return (xml_text.document(root) if changed else data), changed


def magazine_quantity():
    quantity = load_rules()['magazine_quantity_percent']
    return quantity['min'], quantity['max']


def other_sources():
    guns = {name for name, row in catalog().items() if row['kind'] == 'weapon'}
    bounds = load_rules()['tisy_bounds']
    sites = json.loads((ROOT / 'mission/hollow-country/ai/sites.json').read_bytes())
    tisy = []
    for row in sites['Sites']:
        position = row.get('HousePosition') or next(iter(row.get('Waypoints', [])), None)
        if position and bounds[0] <= position[0] <= bounds[1] and bounds[2] <= position[2] <= bounds[3]:
            tisy.append(row)
    cache_guns = sum(item.get('Quantity', 1) for row in tisy for item in row.get('CacheLoot', [])
                     if item.get('ClassName') in guns)
    zones = json.loads((ROOT / 'mission/hollow-country/ai/zones.json').read_bytes())['zones']
    held = [z for z in zones if z['area'] == 'Tisy' and z['default_state'] == 'held']
    rewards = [ROOT / 'mods/HollowCountry/scripts/4_World/Events' / name
               for name in ('HCEventRewards.c', 'HCEventRewardCache.c')]
    reward_guns = sum(int(count) for path in rewards
                      for name, count in re.findall(r'Entry\("([^"]+)", (\d+)\)', path.read_text()) if name in guns)
    print(json.dumps({'other_tisy_sources': {
        'event_reward_cache_firearm_pool_units': reward_guns,
        'event_reward_evidence': 'HCEventRewardPools.V1 and police pool contain consumables/tools only',
        'military_overlay_direct_firearms': 0,
        'overlay_evidence': 'inert compositions and CE loot points; no direct gun spawn list',
        'authored_AI_sites_in_bounds': len(tisy),
        'AI_site_authored_members_min_sum': sum(row['NumberOfAI'] for row in tisy),
        'AI_site_authored_members_max_sum': sum(row['NumberOfAIMax'] for row in tisy),
        'AI_site_cache_firearms': cache_guns,
        'held_zone_guard_members': sum(min(2 + z['tier'], 6, len(z['guard_slots'])) for z in held),
        'guard_death_guns': 'one primary per armed guard; loadout chances and shared AI limits apply; outside CE nominal',
        'runtime': 'authored/source census only; active sites and death drops unobserved'
    }}, sort_keys=True))


def regenerate(output=None):
    """Refresh only the committed native/travel types; optional packs stay install-time."""
    path = ROOT / 'mission/hollow-country/ce/types.xml'
    tree = ET.parse(path)
    entries = {entry['class']: entry for entry in apply(list(catalog().values()))}
    changed = 0
    for node in tree.getroot():
        entry = entries.get(node.get('name'))
        if entry is None:
            continue
        if entry['kind'] == 'weapon':
            for old_usage in node.findall('usage'):
                node.remove(old_usage)
            for usage in entry['usage']:
                ET.SubElement(node, 'usage', {'name': usage})
            for old_value in node.findall('value'):
                node.remove(old_value)
            for tier in entry['value']:
                ET.SubElement(node, 'value', {'name': tier})
        elif entry['kind'] in ('ammo', 'magazine'):
            # a carrier spawns wherever its guns do (role_routes), minus the event-only usages (wh-econ round 7)
            have = [u.get('name') for u in node.findall('usage')]
            want = sorted(set(have) | (set(entry.get('usage', entry.get('set_usage', []))) - EVENT_USAGES))
            if want != sorted(have):
                for old_usage in node.findall('usage'):
                    node.remove(old_usage)
                last = max([i for i, child in enumerate(node) if child.tag in ('category', 'tag')] or [-1])
                for offset, usage in enumerate(want):
                    node.insert(last + 1 + offset, ET.Element('usage', {'name': usage}))
                changed += 1
        for field, value in entry['set'].items():
            old = node.find(field)
            if old is not None and old.text != str(value):
                old.text = str(value)
                changed += 1
    check_retained([entries[node.get('name')] for node in tree.getroot() if node.get('name') in entries],
                   tree.getroot())
    from tools.package import xml_text
    ET.indent(tree, space='  ')
    data = xml_text.document(tree.getroot())
    (output if output is not None else path).write_bytes(b'\n'.join(line.rstrip() for line in data.splitlines()) + b'\n')
    print('native/travel fields refreshed=' + str(changed))


def plan(mission):
    """Print installed versus generated Military nominals; never write a census dump."""
    from tools.package import snafu_optional
    projected = {}
    for source in SOURCES:
        data = json.loads((ROOT / 'tools/package' / source).read_bytes())
        if source == 'firearms_roster.json':
            entries = apply(data['entries'])
        else:
            entries, _, _ = snafu_optional._scaled_entries(
                data['entries'], data.get('test_abundance_multiplier', 1))
        projected.update({entry['class'].lower(): entry for entry in entries})
    known = {name.lower(): entry for name, entry in catalog().items()}
    before, after = Counter(), Counter()
    for name, (source, node) in effective_types(mission).items():
        if name not in known:
            continue
        kind = item_kind(known[name])
        if any(u.get('name') == 'Military' for u in node.findall('usage')):
            for tier in node.findall('value'):
                before[source, tier.get('name'), kind] += int(node.findtext('nominal', '0'))
        entry = projected[name]
        if 'Military' in entry.get('usage', entry.get('set_usage', [])):
            for tier in entry.get('value', entry.get('set_value', [])):
                after[source, tier, kind] += entry['set']['nominal']
    print('source,tier,kind,installed_nominal,generated_nominal')
    for key in sorted(set(before) | set(after)):
        print(','.join(map(str, (*key, before[key], after[key]))))
    _, _, remaining = allocation()
    print('unused ceiling units=' + str(remaining))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mission', type=Path)
    parser.add_argument('--regenerate', action='store_true')
    parser.add_argument('--check', action='store_true', help='validate catalog retention and committed native rows')
    parser.add_argument('--plan', action='store_true', help='with --mission: compare installed and generated Military pools')
    parser.add_argument('--out', type=Path, help='regenerated types destination')
    args = parser.parse_args()
    if args.plan and not args.mission:
        parser.error('--plan requires --mission')
    if args.mission:
        if args.plan:
            plan(args.mission)
        else:
            census(args.mission)
        point_share(args.mission, load_rules()['tisy_bounds'])
        other_sources()
    if args.regenerate:
        regenerate(args.out)
    if args.check:
        entries = apply(list(catalog().values()))
        path = ROOT / 'mission/hollow-country/ce/types.xml'
        tree = ET.parse(path)
        native = json.loads((ROOT / 'tools/package' / SOURCES[0]).read_bytes())['entries']
        check_retained(native, tree.getroot())
        print('military loot retention: catalog=' + str(len(entries)) + ' native=' + str(len(native)) + ' pass')
        print('pack family caps: ' + check_pack_family_caps() + ' pass')
    if not args.mission and not args.regenerate and not args.check:
        parser.error('select --mission, --regenerate or --check')


if __name__ == '__main__':
    main()
