"""Install authored CE encounter scenes on a stopped, isolated Chernarus mission.

No runtime loot creation. Receipts retain exact original bytes; reverse later
mission overlays before rollback. The game installation is read-only evidence.
"""
import argparse
import base64
import copy
import json
import math
import os
from pathlib import Path
import xml.etree.ElementTree as ET

from tools.package import economy, xml_text

SOURCE = Path(__file__).resolve().parents[2] / 'mission/hollow-country'
MANAGED = 'hollow-country-events'
DATA = ('hc-events.xml', 'hc-eventspawns.xml', 'hc-eventgroups.xml',
        'hc-event-proto.xml', 'hc-event-sites.json')
CACHE_DATA = ('cache-events.xml', 'cache-eventspawns.xml')
ROOTS = ('events', 'eventposdef', 'eventgroupdef', 'prototype')
PATCHED = ('cfgeconomycore.xml', 'cfgeventspawns.xml', 'cfgeventgroups.xml', 'mapgroupproto.xml')
GENERATED = MANAGED + '/events.xml'
TARGETS = {*PATCHED, GENERATED}
CRATE = 'StaticObj_Misc_SupplyBox2_DE'
SEEDS = ('StaticHeliCrash', 'StaticPoliceCar', 'StaticMilitaryConvoy',
         'StaticPoliceSituation', 'StaticBonfire')
MAX_OBSERVERS = 6
MEASUREMENTS = 'ce/hc-site-measurements.json'
MAX_SLOPE_DEG = 12.0
BLOCKER_RADIUS_M = 2.0
RELOCATE_RADIUS_M = 12.0
CACHE_RADIUS_M = 15.0
MIN_CACHE_POSITIONS = 3
# Native factorial (2026-11-21, ce-site factorial-003): every fixed event with
# restock > 0 failed its VehicleRespawner Init and never spawned during the 25 min
# hold; every one with restock 0 (the vanilla static-event value) spawned.
NATIVE_RESTOCK = '0'

GROUP_POLICY = b'per-anchor-groups-v1\0'


def _serialized(root):
    ET.indent(root, space='  ')
    return xml_text.document(root) + b'\n'


def _key(pos):
    return tuple(sorted(pos.attrib.items()))


def _anchor_groups(positions, templates):
    """Give each fixed site its own CE group identity, as stock convoys do.

    Authored groups are composition templates. Reusing one identity across all
    anchors of a type matches build 117's repeated one-of-three spawn failures.
    Keep coordinates and finite loot unchanged; native population remains pending.
    """
    by_name = {g.get('name'): g for g in templates}
    groups = ET.Element('eventgroupdef')
    names = set()
    for event in positions:
        for index, pos in enumerate(event.findall('pos'), 1):
            group = copy.deepcopy(by_name[pos.get('group')])
            name = '%s_Site%03d' % (event.get('name'), index)
            if name in names:
                raise ValueError('duplicate encounter site group')
            names.add(name)
            group.set('name', name)
            pos.set('group', name)
            groups.append(group)
    return groups


def measurement_usable(row):
    """Named conservative screening policy; native CE success is still required."""
    for key in ('x', 'z', 'y', 'slope_deg'):
        value = row.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('invalid measurement: ' + key)
    if not 0 <= row['slope_deg'] <= 90:
        raise ValueError('invalid measurement slope')
    if (type(row.get('water')) is not int or row['water'] not in (0, 1)
            or type(row.get('blockers')) is not int or row['blockers'] < 0):
        raise ValueError('invalid measurement water/blockers')
    return (row['water'] == 0 and row['slope_deg'] <= MAX_SLOPE_DEG
            and row['blockers'] == 0)


def measurement_rows(measured):
    """Validate common ingested/merged evidence, including screened-out rows."""
    if not isinstance(measured, dict) or not isinstance(measured.get('provenance'), dict):
        raise ValueError('invalid measurement document')
    provenance = measured['provenance']
    for key in ('server_exe_sha256', 'stock_mission_sha256', 'probe_plan_sha256', 'rpt_sha256'):
        if not economy.HEX64.fullmatch(str(provenance.get(key, ''))):
            raise ValueError('missing measured provenance: ' + key)
    if (measured.get('schema') != 1 or provenance.get('treatment') not in ('current', 'measured')
            or not provenance.get('date') or measured.get('blocker_radius_m') != BLOCKER_RADIUS_M):
        raise ValueError('invalid measurement provenance or collision radius')
    rows = measured.get('targets', [])
    if (not isinstance(rows, list) or not rows
            or any(not isinstance(r, dict) or not isinstance(r.get('id'), str) for r in rows)):
        raise ValueError('invalid measurement targets')
    by_id = {r['id']: r for r in rows}
    if len(by_id) != len(rows):
        raise ValueError('duplicate measurement id')

    for row in rows:
        measurement_usable(row)
        if not all(0 < row[a] < 15360 for a in ('x', 'z')):
            raise ValueError('invalid measurement coordinates')
    return by_id


def check_anchor_separation(events, positions):
    """Apply the authored spacing policy also to the final generated anchors."""
    coords = []
    for event in positions:
        policy = events.find("event[@name='%s']" % event.get('name'))
        separation = max(int(policy.findtext('distanceradius')),
                         2 * int(policy.findtext('saferadius')))
        same_type = []
        for pos in event.findall('pos'):
            x, z = (float(pos.get(a)) for a in ('x', 'z'))
            if any(math.hypot(x - a, z - b) < 340 for a, b in coords):
                raise ValueError('encounter anchors less than 340 m apart')
            if any(math.hypot(x - a, z - b) <= separation for a, b in same_type):
                raise ValueError('encounter anchors overlap same-type exclusion radius')
            coords.append((x, z))
            same_type.append((x, z))


def check_anchor_invariants(positions):
    """Refuse missing/nonfinite heights and degenerate explicit CE zones.

    Fixed anchors may omit zones, as stock fixed events do. A numeric height
    alone is not native spawn proof; measurement screening remains separate.
    """
    for event in positions:
        name = event.get('name', '')
        for index, pos in enumerate(event.findall('pos'), 1):
            try:
                height = float(pos.get('y', ''))
            except ValueError:
                height = math.nan
            if not math.isfinite(height):
                raise ValueError('missing or invalid anchor y: %s:site%03d' % (name, index))
        for zone in event.findall('zone'):
            try:
                values = [float(zone.get(a, '')) for a in ('smin', 'smax', 'dmin', 'dmax', 'r')]
            except ValueError:
                raise ValueError('invalid anchor zone: ' + name) from None
            if any(not math.isfinite(v) or v < 0 for v in values):
                raise ValueError('invalid anchor zone: ' + name)
            if not any(values):
                raise ValueError('zero anchor zone: ' + name)


def apply_measurements(positions, cache_positions, measured, *, relocated=None,
                       retired=None, events=None):
    """Apply native observations using authored indices, never renumbering survivors.

    Without lifecycle policies, retain/report unusable anchors for ring surveys.
    Retirement requires both policies (headroom admission) and a report sink.
    """
    if events is not None and retired is None:
        raise ValueError('anchor retirement requires a report')
    by_id = measurement_rows(measured)
    rows = list(by_id.values())

    def checked(ident, pos):
        row = by_id.get(ident)
        if row is None:
            raise ValueError('missing measurement: ' + ident)
        usable = measurement_usable(row)
        if any(abs(row[a] - float(pos.get(a))) > 0.01 for a in ('x', 'z')):
            raise ValueError('measurement coordinate drift: ' + ident)
        return row, usable
    unusable = []
    for event in positions:
        for index, pos in enumerate(event.findall('pos'), 1):
            ident = '%s:site%03d' % (event.get('name'), index)
            row, usable = checked(ident, pos)
            if not usable:
                origin = {a: float(pos.get(a)) for a in ('x', 'z')}
                origin['y'] = row['y']
                candidates = []
                for candidate in rows:
                    if not candidate['id'].startswith(ident + ':ring'):
                        continue
                    distance = math.hypot(candidate['x'] - origin['x'], candidate['z'] - origin['z'])
                    if measurement_usable(candidate) and 0 < distance <= RELOCATE_RADIUS_M:
                        candidates.append((distance, candidate['id'], candidate))
                if candidates:
                    distance, _, selected = min(candidates)
                    for axis in ('x', 'z'):
                        pos.set(axis, format(selected[axis], '.6f'))
                    if relocated is not None:
                        relocated[ident] = {
                            'from': origin, 'to': {a: selected[a] for a in ('x', 'z', 'y')},
                            'distance': distance}
                    row = selected
                else:
                    if events is None:
                        unusable.append(ident)
                    else:
                        reasons = {key: row[key] for key, failing in (
                            ('water', row['water'] != 0),
                            ('slope_deg', row['slope_deg'] > MAX_SLOPE_DEG),
                            ('blockers', row['blockers'] != 0)) if failing}
                        retired[ident] = dict(x=origin['x'], z=origin['z'], reasons=reasons)
                        event.remove(pos)
                        continue
            pos.set('y', format(row['y'], '.6f'))
    if events is not None:
        for event in positions:
            policy = events.find("event[@name='%s']" % event.get('name'))
            if len(event.findall('pos')) < int(policy.findtext('nominal')) + MAX_OBSERVERS:
                raise ValueError('insufficient encounter positions after retirement: ' + event.get('name'))
    for event in cache_positions:
        anchor = event.find('pos')
        x, z = (float(anchor.get(a)) for a in ('x', 'z'))
        selected = []
        seen = set()
        prefix = event.get('name') + ':'
        for row in rows:
            if not row['id'].startswith(prefix):
                continue
            if not measurement_usable(row):
                continue
            distance = math.hypot(row['x'] - x, row['z'] - z)
            if distance > CACHE_RADIUS_M + 0.001:
                raise ValueError('cache candidate outside observer radius')
            coord = (row['x'], row['z'])
            if coord in seen:
                raise ValueError('duplicate cache candidate')
            seen.add(coord)
            selected.append(ET.Element('pos', x=format(row['x'], '.6f'),
                                       z=format(row['z'], '.6f'), y=format(row['y'], '.6f'), a='0'))
        if len(selected) < MIN_CACHE_POSITIONS:
            raise ValueError('insufficient usable measured cache candidates: ' + event.get('name'))
        event[:] = selected
    return unusable


def validate(source=SOURCE):
    """Validate the bounded authored policy before touching target bytes."""
    data = {name: economy.read_plain(source, 'ce/' + name) for name in DATA}
    events, positions, groups, proto = [economy.xml(data[n], tag)
                                       for n, tag in zip(DATA, ROOTS)]
    # Check authored bytes before measurement application can conceal regressions.
    check_anchor_invariants(positions)
    for root in (events, positions, groups, proto):
        economy._unique(root)
        names = [n.get('name', '').casefold() for n in root]
        if len(set(names)) != len(names):
            raise ValueError('case-aliased encounter definitions')
    names = {e.get('name') for e in events}
    if len(names) < 16 or any(not n.startswith('StaticHC') for n in names):
        raise ValueError('missing encounter events')
    if {e.get('name') for e in positions} != names:
        raise ValueError('encounter position ownership mismatch')
    nominal = sum(int(e.findtext('nominal')) for e in events)
    if not 45 <= nominal <= 55:
        raise ValueError('encounter nominal outside policy')
    for e in events:
        if (e.findtext('active') != '1' or e.findtext('position') != 'fixed'
                or e.findtext('limit') != 'child' or len(e.find('children'))
                or e.findtext('min') != '0' or e.findtext('max') != '0'
                or not 1 <= int(e.findtext('nominal')) <= 4
                or not 1800 <= int(e.findtext('lifetime')) <= 5400
                or e.findtext('restock') != NATIVE_RESTOCK
                or int(e.findtext('distanceradius')) < 300):
            raise ValueError('invalid encounter lifecycle')
    group_names = {g.get('name') for g in groups}
    used = set()
    coords = set()
    count = 0
    budgets = []
    for e in positions:
        policy = events.find("event[@name='%s']" % e.get('name'))
        wanted = int(policy.findtext('nominal'))
        anchors = e.findall('pos')
        # With same-type anchors > twice the safe radius apart, each observer
        # excludes at most one candidate. Reserve six in addition to nominal.
        if len(anchors) < wanted + MAX_OBSERVERS:
            raise ValueError('insufficient encounter positions for six observers')
        separation = max(int(policy.findtext('distanceradius')),
                         2 * int(policy.findtext('saferadius')))
        same_type = []
        budgets.append({'event': e.get('name'), 'nominal': wanted,
                        'min': 0, 'max': 0, 'positions': len(anchors),
                        'positions_after_six_observers': len(anchors) - MAX_OBSERVERS})
        for p in e.findall('pos'):
            if p.get('group') not in group_names:
                raise ValueError('missing encounter group')
            used.add(p.get('group'))
            x, z = float(p.get('x')), float(p.get('z'))
            if not (0 < x < 15360 and 0 < z < 15360) or (x, z) in coords:
                raise ValueError('duplicate or invalid encounter anchor')
            if any(math.hypot(x - a, z - b) < 340 for a, b in coords):
                raise ValueError('encounter anchors less than 340 m apart')
            if any(math.hypot(x - a, z - b) <= separation for a, b in same_type):
                raise ValueError('encounter anchors overlap same-type exclusion radius')
            same_type.append((x, z))
            coords.add((x, z))
            count += 1
    # 208 authored; anchors within building clearance of the shipped map overlays are retired.
    if count < 200 or used != group_names:
        raise ValueError('incomplete encounter coverage')
    for g in groups:
        if not 6 <= len(g) <= 12 or not any(c.get('type') == CRATE for c in g):
            raise ValueError('encounter lacks scene or weapons crate')
        for c in g:
            if c.tag != 'child' or c.get('spawnsecondary') != 'false':
                raise ValueError('unbounded encounter secondary population')
            if 'lootmin' in c.attrib and not 0 <= int(c.get('lootmin')) <= int(c.get('lootmax')) <= 3:
                raise ValueError('invalid encounter loot bound')
    if len(proto) != 1 or proto[0].get('name') != CRATE:
        raise ValueError('unexpected encounter prototype patch')
    crate = proto[0]
    if ({v.get('name') for v in crate.findall('value')} != {'Tier3', 'Tier4'}
            or crate.get('lootmax') != '3'
            or len(crate.findall('container/point')) != 3
            or any(float(p.get('pos').split()[1]) <= 0 for p in crate.findall('container/point'))):
        raise ValueError('invalid elevated weapons crate policy')
    evidence = json.loads(data[DATA[-1]])
    if evidence.get('schema') != 2 or len(evidence['sites']) != count:
        raise ValueError('missing anchor provenance')
    source_keys = set()
    seeds = set()
    authored_keys = {(e.get('name'), float(p.get('x')), float(p.get('z')))
                     for e in positions for p in e.findall('pos')}
    for row in evidence['sites']:
        if row['source_event'] not in SEEDS:
            raise ValueError('unsupported anchor evidence')
        key = (row['event'], float(row['authored_position']['x']), float(row['authored_position']['z']))
        distance = math.hypot(float(row['authored_position']['x']) - float(row['source_position']['x']),
                              float(row['authored_position']['z']) - float(row['source_position']['z']))
        roadside = row['source_event'] in ('StaticPoliceCar', 'StaticMilitaryConvoy', 'StaticPoliceSituation')
        if (roadside and not 89 <= distance <= 131) or (not roadside and distance > 0.01):
            raise ValueError('invalid encounter seed offset')
        if key not in authored_keys or key in source_keys:
            raise ValueError('anchor provenance differs from authored positions')
        seed = (row['source_event'], tuple(sorted(row['source_position'].items())))
        if seed in seeds:
            raise ValueError('encounter seed owned twice')
        seeds.add(seed)
        source_keys.add(key)
    template_count = len(groups)
    groups = _anchor_groups(positions, groups)
    # Cache stock uses the same CE registration, collision checks, merged spawn
    # positions and rollback receipt as encounters. CE alone creates the cases.
    data.update({name: economy.read_plain(source, 'events/' + name) for name in CACHE_DATA})
    caches, cache_positions = [economy.xml(data[n], tag)
                              for n, tag in zip(CACHE_DATA, ('events', 'eventposdef'))]
    cache_names = {'ItemHCSceneCache' + site for site in ('Kamenka', 'Staroye', 'Kumyrna')}
    for root in (caches, cache_positions):
        economy._unique(root)
        if len(root) != 3 or {e.get('name') for e in root} != cache_names:
            raise ValueError('cache event/position ownership mismatch')
    for event in caches:
        children = event.findall('children/child')
        if (event.findtext('active') != '1' or event.findtext('position') != 'fixed'
                or event.findtext('limit') != 'mixed'
                or any(event.findtext(n) != '1' for n in ('nominal', 'min', 'max'))
                or not 1800 <= int(event.findtext('lifetime')) <= 5400
                or event.findtext('restock') != NATIVE_RESTOCK
                or len(children) != 1 or children[0].attrib != {
                    'lootmax': '0', 'lootmin': '0', 'max': '1', 'min': '1',
                    'type': 'SmallProtectorCase'}):
            raise ValueError('invalid cache stock lifecycle')
    for event in cache_positions:
        anchors = event.findall('pos')
        if len(anchors) != 1:
            raise ValueError('cache requires one fixed anchor')
        x, z = (float(anchors[0].get(axis)) for axis in ('x', 'z'))
        if not (0 < x < 15360 and 0 < z < 15360):
            raise ValueError('invalid cache anchor')
    measured_path = economy.child(source, MEASUREMENTS)
    unusable = None
    relocated = {}
    retired = {}
    if os.path.lexists(measured_path):
        data[MEASUREMENTS] = economy.read_plain(source, MEASUREMENTS)
        unusable = apply_measurements(positions, cache_positions, json.loads(data[MEASUREMENTS]),
                                      relocated=relocated, retired=retired, events=events)
        check_anchor_invariants(positions)
        check_anchor_invariants(cache_positions)
        check_anchor_separation(events, positions)
        active_groups = {p.get('group') for e in positions for p in e.findall('pos')}
        groups[:] = [g for g in groups if g.get('name') in active_groups]
        count = sum(len(e.findall('pos')) for e in positions)
        for budget, event in zip(budgets, positions):
            budget['positions'] = len(event.findall('pos'))
            budget['positions_after_six_observers'] = budget['positions'] - MAX_OBSERVERS
    encounter_count = len(events)
    events.extend(caches)
    positions.extend(cache_positions)
    return data, (events, positions, groups, proto), evidence, {
        'event_types': encounter_count, 'nominal': nominal, 'positions': count,
        'group_templates': template_count,
        'cache_event_types': len(caches), 'cache_nominal': len(caches),
        'groups': len(groups), 'objects_in_groups': sum(len(g) for g in groups),
        'observer_headroom': MAX_OBSERVERS, 'event_budgets': budgets,
        'measured_unusable_anchors': unusable,
        'measured_relocated_anchors': relocated,
        'measured_retired_anchors': retired,
        'runtime': 'PENDING'}


def _digest(data):
    # A prior receipt with shared template identities must require reinstall,
    # even when the authored XML itself has not changed. Measured retirement
    # likewise changes generated output without changing its source evidence.
    names = (*DATA, *CACHE_DATA) + ((MEASUREMENTS,) if MEASUREMENTS in data else ())
    policy = GROUP_POLICY + (b'measured-retirement-v1\0' if MEASUREMENTS in data else b'')
    return economy.sha(policy + b''.join(n.encode() + b'\0' + data[n] for n in names))


def plan(target, source=SOURCE):
    target = economy._target(target)
    data, (events, positions, groups, proto), evidence, report = validate(source)
    if os.path.lexists(economy.child(target, MANAGED)):
        raise ValueError('encounters already installed; rollback before replanning')
    before = {n: economy.read_plain(target, n) for n in PATCHED}
    if os.path.lexists(economy.child(target, GENERATED)):
        raise ValueError('unowned encounter definitions')
    before[GENERATED] = None
    core, spawns, target_groups, target_proto = [economy.xml(before[n], tag) for n, tag in
                                               zip(PATCHED, ('economycore', 'eventposdef', 'eventgroupdef', 'prototype'))]
    # Reject another CE owner even if its registration uses a different folder.
    owners = {e.get('name', '').casefold() for e in events}
    for relative in ['db/events.xml'] + [ce.get('folder', '') + '/' + f.get('name', '')
                                          for ce in core.findall('ce') for f in ce
                                          if f.get('type') == 'events']:
        registered = economy.xml(economy.read_plain(target, relative), 'events')
        if any(e.get('name', '').casefold() in owners for e in registered):
            raise ValueError('encounter event already owned by another CE file')
    if any(c.get('folder', '').casefold().rstrip('/') == MANAGED for c in core.findall('ce')):
        raise ValueError('encounter CE folder already registered')
    economy._unique(spawns)
    economy._unique(target_groups)
    economy._unique(target_proto.findall('group'))
    if owners & {e.get('name', '').casefold() for e in spawns}:
        raise ValueError('encounter position collision')
    if {g.get('name', '').casefold() for g in groups} & {g.get('name', '').casefold() for g in target_groups}:
        raise ValueError('encounter group collision')
    # Fail closed if the friend's static building evidence differs from our clearance policy.
    buildings = []
    for g in economy.xml(economy.read_plain(target, 'mapgrouppos.xml'), 'map'):
        name = g.get('name', '')
        if name.startswith('Land_') and not any(v in name for v in ('Wreck', 'Misc', 'Ruins')):
            x, _, z = map(float, g.get('pos').split())
            buildings.append((x, z))
    for row in evidence['sites']:
        x, z = (float(row['authored_position'][v]) for v in ('x', 'z'))
        if any(math.hypot(x - a, z - b) < 80 for a, b in buildings):
            raise ValueError('encounter too close to mapped building origin')
    areas = json.loads(economy.read_plain(target, 'cfgeffectarea.json'))['Areas']
    for row in evidence['sites']:
        x, z = (float(row['authored_position'][v]) for v in ('x', 'z'))
        for area in areas:
            area_data = area['Data']
            a, _, b = area_data['Pos']
            if math.hypot(x - a, z - b) < float(area_data['Radius']) + 120:
                raise ValueError('encounter inside contamination exclusion')
    # Transfer seeds out of their stock pools, including laterally shifted seeds.

    for row in evidence['sites']:
        old = spawns.find("event[@name='%s']" % row['source_event'])
        matching = [] if old is None else [p for p in old.findall('pos')
                                          if p.attrib == row['source_position']]
        if len(matching) != 1:
            raise ValueError('stock anchor missing or ambiguous: ' + row['source_event'])
        old.remove(matching[0])
    # Preserve stock event viability (stock PoliceCar is currently inactive).
    for name in {row['source_event'] for row in evidence['sites']}:
        if len(spawns.find("event[@name='%s']" % name).findall('pos')) < 10:
            raise ValueError('stock event pool would become too small')
    spawns.extend(positions)
    target_groups.extend(groups)
    existing = target_proto.find("group[@name='%s']" % CRATE)
    if existing is None:
        raise ValueError('installed supply crate prototype missing')
    # Require each point to be grounded in the installed model's native evidence.
    native_points = {_key(p) for p in existing.findall('container/point')}
    if not {_key(p) for p in proto[0].findall('container/point')} <= native_points:
        raise ValueError('installed supply crate top points differ')
    target_proto[list(target_proto).index(existing)] = proto[0]
    registration = ET.SubElement(core, 'ce', folder=MANAGED)
    ET.SubElement(registration, 'file', name='events.xml', type='events')
    files = dict(zip(PATCHED, map(_serialized, (core, spawns, target_groups, target_proto))))
    files[GENERATED] = _serialized(events)
    return {'before': before, 'files': files, 'source': _digest(data), 'report': report}


def _atomic(target, name, content):
    managed = economy.child(target, MANAGED)
    path = economy.child(target, name)
    temporary = economy.child(managed, '.next')
    if temporary.exists():
        economy.read_plain(managed, '.next')
        temporary.unlink()
    with temporary.open('xb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _receipt(target):
    managed = economy.child(target, MANAGED)
    economy.preflight_managed(managed, {'receipt.json', 'events.xml', '.next'})
    receipt = json.loads(economy.read_plain(managed, 'receipt.json'))
    if (set(receipt) != {'schema', 'source', 'files'} or receipt['schema'] != 1
            or not isinstance(receipt['source'], str) or not economy.HEX64.fullmatch(receipt['source'])
            or not isinstance(receipt['files'], dict) or set(receipt['files']) != TARGETS):
        raise ValueError('invalid encounter receipt')
    originals = {}
    for name, row in receipt['files'].items():
        if set(row) != {'before', 'before_sha256', 'after'}:
            raise ValueError('invalid encounter receipt row')
        old = None if row['before'] is None else base64.b64decode(row['before'], validate=True)
        if row['before_sha256'] != (None if old is None else economy.sha(old)):
            raise ValueError('encounter backup digest mismatch')
        if not isinstance(row['after'], str) or not economy.HEX64.fullmatch(row['after']):
            raise ValueError('invalid encounter installed digest')
        if (name == GENERATED) != (old is None):
            raise ValueError('invalid encounter backup ownership')
        path = economy.child(target, name)
        current = economy.read_plain(target, name) if os.path.lexists(path) else None
        if current != old and (current is None or economy.sha(current) != row['after']):
            raise ValueError('encounter target drift: ' + name)
        originals[name] = old
    return receipt, originals


def install(source, target):
    """Single bundle hook. Default-on, idempotent, with recoverable exact rollback."""
    target = economy._target(target)
    data, _, _, report = validate(source)
    managed = economy.child(target, MANAGED)
    if os.path.lexists(managed):
        receipt, _ = _receipt(target)
        if receipt['source'] != _digest(data):
            raise ValueError('encounter source changed; rollback first')
        for name, row in receipt['files'].items():
            if economy.sha(economy.read_plain(target, name)) != row['after']:
                raise ValueError('interrupted encounter install; rollback first')
        return report
    candidate = plan(target, source)
    for name, old in candidate['before'].items():
        current = economy.read_plain(target, name) if os.path.lexists(economy.child(target, name)) else None
        if current != old:
            raise ValueError('mission drift since encounter preflight')
    receipt = {'schema': 1, 'source': candidate['source'], 'files': {name: {
        'before': None if candidate['before'][name] is None else base64.b64encode(candidate['before'][name]).decode(),
        'before_sha256': None if candidate['before'][name] is None else economy.sha(candidate['before'][name]),
        'after': economy.sha(content)} for name, content in candidate['files'].items()}}
    managed.mkdir()
    # No target can change until the complete self-contained receipt is durable.
    _atomic(target, MANAGED + '/receipt.json', economy.encode(receipt))
    for name, content in candidate['files'].items():
        _atomic(target, name, content)
    return report


def rollback(target):
    target = economy._target(target)
    managed = economy.child(target, MANAGED)
    if not os.path.lexists(managed):
        return False
    # A pre-receipt interruption cannot have modified any target.
    if not os.path.lexists(managed / 'receipt.json'):
        economy.preflight_managed(managed, {'.next'})
        if (managed / '.next').exists():
            (managed / '.next').unlink()
        managed.rmdir()
        return True
    _, originals = _receipt(target)  # validate every target before any mutation
    for name, old in originals.items():
        if old is not None:
            _atomic(target, name, old)
        elif os.path.lexists(economy.child(target, name)):
            economy.child(target, name).unlink()
    for name in ('.next', 'receipt.json'):
        if os.path.lexists(managed / name):
            economy.child(managed, name).unlink()
    managed.rmdir()
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'plan', 'install', 'rollback'))
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--mission', type=Path)
    args = parser.parse_args(argv)
    if args.command != 'check' and args.mission is None:
        parser.error('--mission is required for ' + args.command)
    try:
        if args.command == 'check':
            report = validate(args.source)[3]
            print(json.dumps(dict(report, valid=True), sort_keys=True))
        elif args.command == 'rollback':
            print(json.dumps({'rolled_back': rollback(args.mission), 'runtime': 'PENDING'}))
        else:
            report = install(args.source, args.mission) if args.command == 'install' else plan(args.mission, args.source)['report']
            print(json.dumps(report, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError) as error:
        # OSError paths can expose operator details; keep CLI errors bounded.
        print('refused: ' + (str(error) if isinstance(error, ValueError) else type(error).__name__))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
