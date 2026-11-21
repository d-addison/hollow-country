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

# Vanilla peaks near 0.21 for weapons; the 3x firearm test abundance sits near 0.7.
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
    parser.add_argument('--top', type=int, default=10)
    args = parser.parse_args(argv)
    for row in pressure(args.mission, args.category)[:args.top]:
        print(json.dumps(row, sort_keys=True))
    found = problems(args.mission, args.category, args.limit)
    for line in found:
        print('HC_CE_SLOT_PRESSURE: ' + line)
    print('slot pressure: %s (limit %.2f, offline estimate)' % ('fail' if found else 'pass', args.limit))
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
