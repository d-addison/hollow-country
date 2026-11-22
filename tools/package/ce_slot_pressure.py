"""Offline CE slot pressure: map-wide nominal demand against matching proxy slots.

The engine's hard-to-place warning has several possible causes. This estimate
cannot identify one from nominal/point counts alone. ``feasibility`` checks all
positive building-routed types together against shared group/container caps,
category/tag filters and actual placed tier sets, without splitting shared
capacity evenly between usages. It is an optimistic upper bound: dimensions,
point range/height, collisions and native selection remain unobserved.
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


def feasibility(mission):
    """Optimistic joint capacity bound, with integral max flow over shared caps.

    A failure proves a static demand/capacity conflict under these constraints;
    a pass cannot explain or exclude native hard-to-place warnings. Unassigned
    routes are one allocation witness, not causal row attribution or a cut policy.
    """
    from collections import deque
    mission = Path(mission)
    limits = ET.parse(mission / 'cfglimitsdefinition.xml').getroot()
    values = [v.get('name') for v in limits.find('valueflags')]
    data = (mission / 'areaflags.map').read_bytes()
    width, height, world_x, world_z, bits = struct.unpack_from('<5I', data)
    cells = width * height
    if bits != 32 or len(data) != 24 + cells * 5:
        raise ValueError('unsupported area map layout')
    placed = Counter()
    for group in ET.parse(mission / 'mapgrouppos.xml').getroot():
        x, _, z = map(float, group.get('pos').split())
        index = min(height - 1, max(0, int(z * height / world_z))) * width + min(width - 1, max(0, int(x * width / world_x)))
        flags = data[24 + cells * 4 + index]
        tiers = frozenset(v for b, v in enumerate(values) if flags >> b & 1) or frozenset(values)
        placed[group.get('name'), tiers] += 1
    demands, categories = Counter(), Counter()
    for _, row in _types(mission).values():
        nominal = int(row.findtext('nominal', '0'))
        flags = row.find('flags')
        usages = frozenset(n.get('name') for n in row.findall('usage'))
        cats = frozenset(n.get('name') for n in row.findall('category'))
        if (nominal <= 0 or not usages or usages <= EVENT_USAGES or not cats
                or (flags is not None and flags.get('count_in_map') == '0')):
            continue
        tiers = frozenset(n.get('name') for n in row.findall('value')) or frozenset(values)
        tags = frozenset(n.get('name') for n in row.findall('tag'))
        demands[usages, tiers, cats, tags] += nominal
        for category in cats:
            categories[category] += nominal
    # Residual edges [destination, remaining, reverse-index]. Group caps couple
    # containers; container caps couple every category and route using them.
    graph = [[], []]
    def node():
        graph.append([])
        return len(graph) - 1
    def edge(a, b, amount):
        graph[a].append([b, amount, len(graph[b])])
        graph[b].append([a, 0, len(graph[a]) - 1])
    containers = []
    protos = {g.get('name'): g for g in ET.parse(mission / 'mapgroupproto.xml').getroot().findall('group')}
    for (name, tiers), count in sorted(placed.items(), key=lambda pair: (pair[0][0], sorted(pair[0][1]))):
        proto = protos.get(name)
        if proto is None:
            continue
        usages = {u.get('name') for u in proto.findall('usage')}
        if not usages:
            continue
        group_node = node()
        edge(group_node, 1, max(0, int(proto.get('lootmax', 12))) * count)
        for container in proto.findall('container'):
            cap = min(len(container.findall('point')), max(0, int(container.get('lootmax', 8)))) * count
            if not cap:
                continue
            ident = node()
            edge(ident, group_node, cap)
            containers.append((ident, usages, tiers,
                {c.get('name') for c in container.findall('category')},
                {t.get('name') for t in container.findall('tag')}))
    unreachable = 0
    demand_nodes = {}
    for (usages, tiers, cats, tags), demand in demands.items():
        ident = node()
        edge(0, ident, demand)
        demand_nodes[ident] = dict(usages=sorted(usages), tiers=sorted(tiers),
                                   categories=sorted(cats), tags=sorted(tags), nominal=demand)
        matches = [c[0] for c in containers if usages & c[1] and tiers & c[2] and cats & c[3]
                   and (not tags or tags & c[4])]
        if not matches:
            unreachable += demand
        for target in matches:
            edge(ident, target, demand)
    flow = 0
    while True:
        levels = [-1] * len(graph)
        levels[0] = 0
        queue = deque([0])
        while queue:
            a = queue.popleft()
            for b, cap, _ in graph[a]:
                if cap > 0 and levels[b] < 0:
                    levels[b] = levels[a] + 1
                    queue.append(b)
        if levels[1] < 0:
            break
        cursor = [0] * len(graph)
        def send(a, amount):
            if a == 1:
                return amount
            while cursor[a] < len(graph[a]):
                item = graph[a][cursor[a]]
                b, cap, reverse = item
                if cap > 0 and levels[b] == levels[a] + 1:
                    sent = send(b, min(amount, cap))
                    if sent:
                        item[1] -= sent
                        graph[b][reverse][1] += sent
                        return sent
                cursor[a] += 1
            return 0
        while True:
            sent = send(0, sum(demands.values()))
            if not sent:
                break
            flow += sent
    total = sum(demands.values())
    unassigned = [dict(demand_nodes[target], unassigned=remaining)
                  for target, remaining, _ in graph[0] if remaining]
    return dict(status='fail' if flow < total else 'pass', demand=total,
                placeable_upper_bound=flow, deficit=total-flow, unreachable_nominal=unreachable,
                categories=dict(sorted(categories.items())), unassigned_routes=unassigned,
                limitation='Optimistic static bound; point dimensions, collisions and native selection unobserved.')


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
    parser.add_argument('--all-categories', action='store_true', help='joint shared-capacity bound across all building-routed categories')
    parser.add_argument('--coverage', action='store_true', help='report modded usage/container eligibility')
    parser.add_argument('--top', type=int, default=10)
    args = parser.parse_args(argv)
    if args.all_categories:
        result = feasibility(args.mission)
        print(json.dumps(result, sort_keys=True))
        return 1 if result['status'] == 'fail' else 0
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
