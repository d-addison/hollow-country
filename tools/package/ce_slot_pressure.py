"""Offline CE slot pressure: map-wide nominal demand against matching proxy slots.

The engine's hard-to-place warning has several possible causes. This estimate
cannot identify one from nominal/point counts alone. ``feasibility`` checks all
positive building-routed types together against shared group/container caps,
category/tag filters and actual placed tier sets, without splitting shared
capacity evenly between usages. It is an optimistic upper bound: dimensions,
point range/height, collisions and native selection remain unobserved.

CLI: ``MISSION --calibrate-rpt RUN.RPT`` compares per-class retry rates with
static bounds (repeat the flag for multiple runs; output omits input paths).
``--initial-fill-seconds`` separates initial fill from later activity (default 120).

``MISSION --feasibility`` (alias ``--all-categories``) emits one JSON
report and exits 0 for a static pass, 1 for a capacity deficit, or 2 for invalid
inputs/options. A static pass is never native placement acceptance.
"""
import argparse
from collections import Counter
import json
import math
import re
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


def village_items(mission):
    """Offline items per Village-usage building, the model of the owner's "5-6 per house" target.

    Fill model of economy.placement_budget: a row's nominal splits evenly over its usages, a group's slots
    (min(group lootmax, sum(min(container lootmax, points)))) split evenly over its usages, a usage fills
    min(1, nominal / slots), and a group holds slots x fill per usage. Weighted by placed buildings. Returns
    {'fill', 'nominal', 'slots', 'kinds': {kind: {'groups', 'buildings', 'median', 'p90'}}} for the kinds house
    (Land_House_*), wreck, outhouse (Toilet), shed (Shed/Garage) and other; offline, never DayZ behaviour.
    """
    mission = Path(mission)
    nominal, slots = Counter(), Counter()
    for _, row in _types(mission).values():
        usages = [u.get('name') for u in row.findall('usage')] or ['*']
        for usage in usages:
            nominal[usage] += int(row.findtext('nominal', '0')) / len(usages)
    placed = Counter(g.get('name') for g in ET.parse(mission / 'mapgrouppos.xml').getroot().findall('group'))
    proto = ET.parse(mission / 'mapgroupproto.xml').getroot()
    defaults = {d.get('name'): int(d.get('lootmax')) for d in proto.iter('default') if d.get('lootmax')}
    groups = {}
    for group in proto.findall('group'):
        usages = [u.get('name') for u in group.findall('usage')]
        capacity = sum(min(int(c.get('lootmax', str(defaults.get('container', 8)))), len(c.findall('point')))
                       for c in group.findall('container'))
        size = min(int(group.get('lootmax', str(defaults.get('group', 12)))), capacity)
        groups[group.get('name')] = (usages, size)
        for usage in usages:
            slots[usage] += size * placed[group.get('name')] / len(usages)
    fill = {usage: min(1.0, nominal[usage] / slots[usage]) for usage in slots if slots[usage]}
    kinds = {}
    for name, (usages, size) in groups.items():
        if 'Village' not in usages or not placed[name]:
            continue
        lower = name.lower()
        kind = ('wreck' if 'wreck' in lower else 'outhouse' if 'toilet' in lower else 'house' if lower.startswith('land_house_')
                else 'shed' if 'shed' in lower or 'garage' in lower else 'other')
        kinds.setdefault(kind, []).append((sum(size / len(usages) * fill[u] for u in usages), placed[name]))

    def weighted(values, share):
        total, running = sum(w for _, w in values), 0
        for value, weight in sorted(values):
            running += weight
            if running >= share * total:
                return round(value, 2)
    return {'fill': round(fill.get('Village', 0.0), 3), 'nominal': round(nominal['Village']), 'slots': round(slots['Village']),
            'kinds': {k: {'groups': len(v), 'buildings': sum(w for _, w in v), 'median': weighted(v, 0.5), 'p90': weighted(v, 0.9)}
                      for k, v in sorted(kinds.items())}}


def feasibility(mission, military_weapons=False, limit=LIMIT, slack=False):
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
    route_names, excluded = {}, []
    if not 0 < limit <= 1:
        raise ValueError("limit must be greater than zero and at most one")
    for _, row in _types(mission).values():
        nominal = int(row.findtext('nominal', '0'))
        flags = row.find('flags')
        usages = frozenset(n.get('name') for n in row.findall('usage'))
        cats = frozenset(n.get('name') for n in row.findall('category'))
        if military_weapons and ('weapons' not in cats or not usages & {'Military', 'Police', 'Prison'}):
            continue
        if nominal > 0 and (not usages or usages <= EVENT_USAGES or not cats):
            excluded.append({'name': row.get('name'), 'nominal': nominal,
                             'reason': 'no building usage/category or event-only routing; other supply requires native verification'})
        if (nominal <= 0 or not usages or usages <= EVENT_USAGES or not cats
                or (flags is not None and flags.get('count_in_map') == '0')):
            continue
        tiers = frozenset(n.get('name') for n in row.findall('value')) or frozenset(values)
        tags = frozenset(n.get('name') for n in row.findall('tag'))
        demands[usages, tiers, cats, tags] += nominal
        route_names.setdefault((usages, tiers, cats, tags), []).append((row.get('name'), nominal))
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
    container_caps, group_limits = {}, {}
    root = ET.parse(mission / 'mapgroupproto.xml').getroot()
    defaults = {d.get('name'): int(d.get('lootmax')) for d in root.findall('./defaults/default') if d.get('lootmax') is not None}
    protos = {g.get('name'): g for g in root.findall('group')}
    for (name, tiers), count in sorted(placed.items(), key=lambda pair: (pair[0][0], sorted(pair[0][1]))):
        proto = protos.get(name)
        if proto is None:
            continue
        usages = {u.get('name') for u in proto.findall('usage')}
        if not usages:
            continue
        if int(proto.get('lootmax', defaults.get('group', 12))) <= 0:
            continue
        group_node = node()
        group_limits[group_node] = max(0, int(proto.get('lootmax', defaults.get('group', 12)))) * count
        edge(group_node, 1, group_limits[group_node])
        for container in proto.findall('container'):
            cap = min(len(container.findall('point')), max(0, int(container.get('lootmax', defaults.get('container', 8))))) * count
            if not cap:
                continue
            ident = node()
            edge(ident, group_node, cap)
            container_caps[ident] = (group_node, cap)
            containers.append((ident, usages, tiers,
                {c.get('name') for c in container.findall('category')},
                {t.get('name') for t in container.findall('tag')}))
    unreachable = 0
    unreachable_types = []
    matched_containers = set()
    required = 0
    demand_nodes, demand_matches, demand_keys = {}, {}, {}
    for (usages, tiers, cats, tags), demand in demands.items():
        ident = node()
        reserved = math.ceil(demand / limit) if military_weapons else demand
        required += reserved
        edge(0, ident, reserved)
        demand_keys[ident] = (usages, tiers, cats, tags)
        demand_nodes[ident] = dict(usages=sorted(usages), tiers=sorted(tiers),
                                   categories=sorted(cats), tags=sorted(tags), nominal=demand)
        matches = [c[0] for c in containers if usages & c[1] and tiers & c[2] and cats & c[3]
                   and (not tags or tags & c[4])]
        if not matches:
            unreachable += demand
            unreachable_types.extend({'name': name, 'nominal': nominal,
                'reason': 'no placed positive-capacity container matches usage, tier, category and tag'}
                for name, nominal in route_names[usages, tiers, cats, tags])
        matched_containers.update(matches)
        demand_matches[ident] = matches
        for target in matches:
            edge(ident, target, reserved)
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
            sent = send(0, required)
            if not sent:
                break
            flow += sent
    total = sum(demands.values())
    unassigned = [dict(demand_nodes[target], unassigned=remaining)
                  for target, remaining, _ in graph[0] if remaining]
    # Union capacity counts each matching container and shared group only once.
    group_caps = Counter()
    for ident in matched_containers:
        group, cap = container_caps[ident]
        group_caps[group] += cap
    matching_capacity = sum(min(cap, group_limits[group]) for group, cap in group_caps.items())
    result = dict(status='fail' if flow < required else 'pass', demand=total,
                limit=limit if military_weapons else 1, required_with_headroom=required,
                matching_capacity=matching_capacity, headroom_deficit=required-flow,
                unreachable_types=sorted(unreachable_types, key=lambda row: row['name'].lower()),
                excluded_types=excluded,
                reserved_placeable=flow, unreachable_nominal=unreachable,
                categories=dict(sorted(categories.items())), unassigned_routes=unassigned,
                limitation='Optimistic static bound; point dimensions, collisions and native selection unobserved.')
    if not military_weapons:
        result.update(placeable_upper_bound=flow, deficit=total-flow)
    if slack:
        # Spare capacity per demand bucket after the max flow: per shared group, the residual of the matching
        # containers capped by the group's residual. A bucket with unassigned demand has none. Buckets share
        # containers, so the sum over buckets overstates what all of them could take at once.
        result['bucket_slack'] = []
        for ident, matches in demand_matches.items():
            per_group = Counter()
            for target in matches:
                per_group[container_caps[target][0]] += graph[target][0][1]
            spare = sum(min(have, graph[group][0][1]) for group, have in per_group.items())
            compatible = Counter()
            for target in matches:
                group, cap = container_caps[target]
                compatible[group] += cap
            # A row can use this union, but cannot claim it independently of its competitors.
            compatible_capacity = sum(min(have, group_limits[group]) for group, have in compatible.items())
            usages, tiers, cats, tags = demand_keys[ident]
            unassigned_here = next((r for t, r, _ in graph[0] if t == ident), 0)
            result['bucket_slack'].append(dict(
                usages=sorted(usages), tiers=sorted(tiers), categories=sorted(cats), tags=sorted(tags),
                nominal=demands[usages, tiers, cats, tags], compatible_capacity=compatible_capacity,
                slack=0 if unassigned_here else spare,
                unassigned=unassigned_here, classes=sorted(name for name, _ in route_names[usages, tiers, cats, tags])))
    return result


def rpt_placement_counts(path, initial_fill_seconds=120):
    """Stream one RPT, separating initial fill from later warnings; never return paths or raw lines.

    Rates use the complete timestamp window, including quiet time. Clock wrap is
    handled; a backwards clock change other than midnight refuses calibration.
    The initial window is an explicit reporting convention, not engine readiness.
    """
    counts, later = Counter(), Counter()
    first = previous = None
    offset = 0
    with Path(path).open(encoding='utf-8', errors='replace') as stream:
        for line in stream:
            timestamp = re.match(r'\s*(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d+))?\s', line)
            if not timestamp:
                continue
            h, m, sec = map(int, timestamp.groups()[:3])
            if h > 23 or m > 59 or sec > 59:
                continue
            # DayZ prints unpadded millisecond integers: .40 means 40 ms, not 400 ms.
            clock = h * 3600 + m * 60 + sec + int(timestamp[4] or '0') / 1000
            stamp = clock + offset
            if previous is not None and stamp < previous:
                if previous - stamp > 12 * 3600:
                    offset += 86400
                    stamp += 86400
                else:
                    raise ValueError('RPT clock moved backwards; elapsed rate unavailable')
            first = stamp if first is None else first
            previous = stamp
            warning = re.search(r'\[LootRespawner\].*hard to place, performance drops: "([A-Za-z0-9_]+)"', line)
            if warning:
                counts[warning[1]] += 1
                if stamp - first >= initial_fill_seconds:
                    later[warning[1]] += 1
    if first is None:
        raise ValueError('RPT has no clock window')
    duration = previous - first
    later_duration = max(0, duration - initial_fill_seconds)
    return dict(duration_seconds=round(duration, 3), initial_fill_seconds=initial_fill_seconds,
                later_seconds=round(later_duration, 3), counts=dict(counts), later_counts=dict(later))


def calibration(mission, rpts, initial_fill_seconds=120):
    """Join observed retry rates to static bounds. This never certifies an engine capacity or chooses cuts.

    RPTs need the corresponding mission snapshot to attribute a failure. A current
    snapshot can be compared, but cannot reconstruct historical item/point state.
    """
    mission = Path(mission)
    runs = [rpt_placement_counts(path, initial_fill_seconds) for path in rpts]
    static = feasibility(mission, slack=True)
    buckets = {name.lower(): b for b in static['bucket_slack'] for name in b['classes']}
    rows = _types(mission)
    # Reproduce the floor allocator's prototype-only point count. It omits
    # placed multiplicity, actual tiers and the shared group limit.
    from tools.package import loot_floor_policy, loot_boost
    proto = (mission / 'mapgroupproto.xml').read_bytes()
    text = proto.decode('utf-8-sig')
    root = ET.fromstring(proto)
    default = loot_floor_policy._default(root)
    containers = [c for _, limit, cs in loot_floor_policy._scan(text, loot_boost._mask(text), default)
                  if limit > 0 for c in cs if 'shelves' in c['tags']]
    # Include zero-warning controls, not just the classes that retried.
    names = sorted({n for run in runs for n in run['counts']}
                   | {n for b in static['bucket_slack'] for n in b['classes']})
    result = []
    for name in names:
        entry = rows.get(name.lower())
        row = entry[1] if entry else None
        bucket = buckets.get(name.lower())
        prototype_points = None
        if row is not None:
            cats = frozenset(n.get('name') for n in row.findall('category'))
            tags = frozenset(n.get('name') for n in row.findall('tag'))
            usages = frozenset(n.get('name') for n in row.findall('usage'))
            nominal = int(row.findtext('nominal', '0'))
            match_row = (cats, tags, tags, nominal, usages)
            prototype_points = sum(min(c['lootmax'], len(c['ys'])) for c in containers
                                   if loot_floor_policy._matches(match_row, c, 'after'))
        observations = []
        for run in runs:
            count = run['counts'].get(name, 0)
            later = run['later_counts'].get(name, 0)
            observations.append(dict(count=count, per_hour=round(count * 3600 / run['duration_seconds'], 3)
                                     if run['duration_seconds'] else None,
                                     later_count=later, later_per_hour=round(later * 3600 / run['later_seconds'], 3)
                                     if run['later_seconds'] else None))
        result.append(dict(name=name, nominal=int(row.findtext('nominal', '0')) if row is not None else None,
                           minimum=int(row.findtext('min', '0')) if row is not None else None,
                           prototype_shelf_points=prototype_points,
                           placed_compatible_upper_bound=bucket['compatible_capacity'] if bucket else None,
                           shared_route_nominal=bucket['nominal'] if bucket else None,
                           shared_route_unassigned=bucket['unassigned'] if bucket else None,
                           shared_route_slack=bucket['slack'] if bucket else None, observations=observations))
    return dict(status='unverified', runs=[{k: v for k, v in run.items() if k not in {'counts', 'later_counts'}}
                                          for run in runs], classes=result,
                limitation='Static bounds omit physical fit and occupancy. RPT order is input order; '
                           'mission snapshot identity at each run is unverified. Retry counts are not missing item counts. '
                           'No calibrated engine capacity or expected post-fix rate is established.')


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
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--military-weapons', action='store_true', help='joint Military/Police/Prison weapon bound with LIMIT headroom and named unrouted types')
    modes.add_argument('--all-categories', '--feasibility', action='store_true', help='joint shared-capacity bound across all building-routed categories; exit 1 on deficit')
    modes.add_argument('--coverage', action='store_true', help='report modded usage/container eligibility')
    modes.add_argument('--calibrate-rpt', type=Path, action='append', help='read-only RPT comparison; repeat in run order')
    parser.add_argument('--initial-fill-seconds', type=int, default=120)
    parser.add_argument('--top', type=int, default=10)
    args = parser.parse_args(argv)
    if not math.isfinite(args.limit) or not 0 < args.limit <= 1:
        parser.error('--limit must be greater than zero and at most one')
    if args.initial_fill_seconds < 0:
        parser.error('--initial-fill-seconds must be nonnegative')
    if args.calibrate_rpt:
        try:
            report = calibration(args.mission, args.calibrate_rpt, args.initial_fill_seconds)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, struct.error, ET.ParseError):
            print(json.dumps({'status': 'error', 'reason': 'calibration inputs unreadable or invalid'}))
            return 2
        print(json.dumps(report, sort_keys=True))
        return 0  # A completed comparison, explicitly unverified; never a capacity gate pass.
    if args.top < 0:
        parser.error('--top must be nonnegative')
    if args.all_categories or args.military_weapons:
        try:
            result = feasibility(args.mission, args.military_weapons, args.limit)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, struct.error, ET.ParseError):
            # Stable machine-readable failure without leaking local input paths.
            print(json.dumps({'status': 'error', 'reason': 'CE inputs unreadable or invalid'}, sort_keys=True))
            return 2
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
