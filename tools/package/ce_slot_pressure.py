"""Offline CE slot pressure: map-wide nominal demand against matching proxy slots.

CE logs "Item [N] is hard to place, performance drops" when a class's usage/value
points are already full. This reads the installed mission (registration-order
types, mapgroupproto containers, mapgrouppos instances and the areaflags value
plane) and, for every distinct usage x tier route set of a category, compares
the nominal of all rows confined to that set with the slots inside it
(Hall-style). Slots are min(points, container lootmax) per container, capped by
group lootmax, split evenly over the group's usages and its position's tiers.
It is a planning estimate, never CE simulation.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

# Provisional bound; neither passing pressure nor route coverage simulates CE fill.
# Build 133 spammed ~200k lines with a 1.04 route set.
LIMIT = 0.8
INPUTS = ('cfgeconomycore.xml', 'cfglimitsdefinition.xml', 'areaflags.map', 'mapgroupproto.xml', 'mapgrouppos.xml')
EVENT_USAGES = {'ContaminatedArea', 'Lunapark', 'Historical', 'SeasonalEvent'}


def _types(mission):
    paths = [Path('db/types.xml')]
    for ce in ET.parse(mission / 'cfgeconomycore.xml').getroot().findall('ce'):
        paths.extend(Path(ce.get('folder')) / f.get('name') for f in ce if f.get('type') == 'types')
    rows = {}
    for path in paths:
        for row in ET.parse(mission / path).getroot():
            rows[row.get('name').lower()] = (str(path.parent).split('/')[0], row)
    return rows


def capacity(mission, category):
    data = (mission / 'areaflags.map').read_bytes()
    width, height, world_x, world_z, bits = struct.unpack_from('<5I', data)
    cells = width * height
    if bits != 32 or len(data) != 24 + cells * 5:
        raise ValueError('unsupported area map layout')
    limits = ET.parse(mission / 'cfglimitsdefinition.xml').getroot()
    values = [v.get('name') for v in limits.find('valueflags')]
    protos = {g.get('name'): g for g in ET.parse(mission / 'mapgroupproto.xml').getroot().findall('group')}
    slots = Counter()
    for group in ET.parse(mission / 'mapgrouppos.xml').getroot():
        proto = protos.get(group.get('name'))
        if proto is None:
            continue
        total = 0
        for container in proto.findall('container'):
            if category in [c.get('name') for c in container.findall('category')]:
                total += min(len(container.findall('point')), int(container.get('lootmax', 8)))
        usages = [u.get('name') for u in proto.findall('usage')]
        total = min(total, int(proto.get('lootmax', 12)))
        if not total or not usages:
            continue
        x, _, z = map(float, group.get('pos').split())
        index = (min(height - 1, max(0, int(z * height / world_z))) * width
                 + min(width - 1, max(0, int(x * width / world_x))))
        flags = data[24 + cells * 4 + index]
        tiers = [values[b] for b in range(len(values)) if flags >> b & 1] or values
        for usage in usages:
            for tier in tiers:
                slots[usage, tier] += total / len(usages) / len(tiers)
    return slots, values


def pressure(mission, category='weapons'):
    """Rows sorted worst first: ratio, demand, slots, route set, demand by layer."""
    mission = Path(mission)
    slots, values = capacity(mission, category)
    routes, layers = Counter(), {}
    for source, row in _types(mission).values():
        if category not in [c.get('name') for c in row.findall('category')]:
            continue
        flags = row.find('flags')
        nominal = int(row.findtext('nominal') or 0)
        usages = [u.get('name') for u in row.findall('usage')]
        if nominal < 1 or not usages or (flags is not None and flags.get('count_in_map') == '0'):
            continue
        if set(usages) <= EVENT_USAGES:
            continue  # placed by events/areas, not building proxies
        route = frozenset((u, t) for u in usages for t in ([v.get('name') for v in row.findall('value')] or values))
        routes[route] += nominal
        layers.setdefault(route, Counter())[source] += nominal
    result = []
    for route in routes:
        demand = sum(n for other, n in routes.items() if other <= route)
        room = sum(slots[key] for key in route)
        result.append({'ratio': round(demand / room, 3) if room else float('inf'), 'demand': demand,
                       'slots': round(room), 'route': sorted('%s/%s' % key for key in route),
                       'layers': dict(layers[route])})
    result.sort(key=lambda r: -r['ratio'])
    return result


def modded_coverage(mission):
    """Offline usage/container census for shipped pack and datamined classes.

    No type tags means unrestricted tags (as in native firearms); explicit
    tags require an intersection. Count only positive capacity containers in
    placed groups and tiers actually present at those groups' positions.
    Geometry, item dimensions and the engine's random picks remain unobserved.
    """
    from tools.package import military_loot
    mission = Path(mission)
    catalog = military_loot.catalog()
    selected = {name.lower() for name, row in catalog.items()
                if row.get('datamined')}
    # Every pack entry, including ammo/magazines without fit metadata.
    for source in military_loot.SOURCES[1:]:
        selected.update(e['class'].lower() for e in json.loads(
            (military_loot.ROOT / 'tools/package' / source).read_bytes())['entries'])
    rows = {name: row for name, (_, row) in _types(mission).items()
            if name in selected and int(row.findtext('nominal', '0')) > 0
            and (row.find('flags') is None or row.find('flags').get('count_in_map') != '0')}
    limits = ET.parse(mission / 'cfglimitsdefinition.xml').getroot()
    values = [v.get('name') for v in limits.find('valueflags')]
    usages = [u.get('name') for u in limits.find('usageflags')]
    data = (mission / 'areaflags.map').read_bytes()
    width, height, world_x, world_z, bits = struct.unpack_from('<5I', data)
    cells = width * height
    if bits != 32 or len(data) != 24 + cells * 5:
        raise ValueError('unsupported area map layout')
    placed = {}
    for group in ET.parse(mission / 'mapgrouppos.xml').getroot():
        x, _, z = map(float, group.get('pos').split())
        index = min(height - 1, max(0, int(z * height / world_z))) * width + min(width - 1, max(0, int(x * width / world_x)))
        flags = data[24 + cells * 4 + index]
        tiers = {v for b, v in enumerate(values) if flags >> b & 1} or set(values)
        placed.setdefault(group.get('name'), set()).update(tiers)
    eligible = {usage: set() for usage in usages}
    uncovered = []
    constraints = {name: {key: {n.get('name') for n in row.findall(key)}
                          for key in ('usage', 'value', 'category', 'tag')}
                   for name, row in rows.items()}
    for group in ET.parse(mission / 'mapgroupproto.xml').getroot().findall('group'):
        if group.get('name') not in placed or int(group.get('lootmax', 12)) < 1:
            continue
        for container in group.findall('container'):
            if not container.findall('point') or int(container.get('lootmax', 8)) < 1:
                continue
            categories = {n.get('name') for n in container.findall('category')}
            tags = {n.get('name') for n in container.findall('tag')}
            for usage in [n.get('name') for n in group.findall('usage')]:
                matches = {name for name, row in constraints.items()
                           if usage in row['usage'] and row['category'] & categories
                           and (not row['tag'] or bool(row['tag'] & tags))
                           and (not row['value'] or bool(row['value'] & placed[group.get('name')]))}
                eligible.setdefault(usage, set()).update(matches)
                if not matches:
                    uncovered.append({'usage': usage, 'group': group.get('name'),
                                      'container': container.get('name'),
                                      'categories': sorted(categories), 'tags': sorted(tags)})
    return {'classes_by_usage': {u: len(names) for u, names in sorted(eligible.items())},
            'positive_modded_classes': len(rows),
            'unreachable_classes': sorted(set(rows) - set().union(*eligible.values())),
            'uncovered_containers': uncovered}


def problems(mission, category='weapons', limit=LIMIT):
    return ['%s demand %d over %d slots (%.2f > %.2f) layers=%s'
            % (','.join(r['route']) if len(r['route']) <= 8 else '%d routes' % len(r['route']),
               r['demand'], r['slots'], r['ratio'], limit, ','.join(sorted(r['layers'])))
            for r in pressure(mission, category)
            # Stock rows on routes without proxies (e.g. Military/Unique) are vanilla's own.
            if r['ratio'] > limit and (r['slots'] or set(r['layers']) != {'db'})]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('mission', type=Path)
    parser.add_argument('--category', default='weapons')
    parser.add_argument('--limit', type=float, default=LIMIT)
    parser.add_argument('--coverage', action='store_true', help='report modded usage/container eligibility')
    parser.add_argument('--top', type=int, default=10)
    args = parser.parse_args(argv)
    if args.coverage:
        print(json.dumps(modded_coverage(args.mission), sort_keys=True))
    for row in pressure(args.mission, args.category)[:args.top]:
        print(json.dumps(row, sort_keys=True))
    found = problems(args.mission, args.category, args.limit)
    for line in found:
        print('HC_CE_SLOT_PRESSURE: ' + line)
    print('slot pressure: %s (limit %.2f, offline estimate)' % ('fail' if found else 'pass', args.limit))
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
