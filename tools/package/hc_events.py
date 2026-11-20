"""Install authored CE encounter scenes on a stopped, isolated Chernarus mission.

No runtime loot creation. Receipts retain exact original bytes; reverse later
mission overlays before rollback. The game installation is read-only evidence.
"""
import argparse
import base64
import json
import math
import os
from pathlib import Path
import xml.etree.ElementTree as ET

from tools.package import economy

SOURCE = Path(__file__).resolve().parents[2] / 'mission/hollow-country'
MANAGED = 'hollow-country-events'
DATA = ('hc-events.xml', 'hc-eventspawns.xml', 'hc-eventgroups.xml',
        'hc-event-proto.xml', 'hc-event-sites.json')
ROOTS = ('events', 'eventposdef', 'eventgroupdef', 'prototype')
PATCHED = ('cfgeconomycore.xml', 'cfgeventspawns.xml', 'cfgeventgroups.xml', 'mapgroupproto.xml')
GENERATED = MANAGED + '/events.xml'
TARGETS = {*PATCHED, GENERATED}
CRATE = 'StaticObj_Misc_SupplyBox2_DE'
SEEDS = ('StaticHeliCrash', 'StaticPoliceCar', 'StaticMilitaryConvoy',
         'StaticPoliceSituation', 'StaticBonfire')


def _serialized(root):
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'


def _key(pos):
    return tuple(sorted(pos.attrib.items()))


def validate(source=SOURCE):
    """Validate the bounded authored policy before touching target bytes."""
    data = {name: economy.read_plain(source, 'ce/' + name) for name in DATA}
    events, positions, groups, proto = [economy.xml(data[n], tag)
                                       for n, tag in zip(DATA, ROOTS)]
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
                or not 1 <= int(e.findtext('nominal')) <= 4
                or not 1800 <= int(e.findtext('lifetime')) <= 5400
                or not 60 <= int(e.findtext('restock')) <= 600
                or int(e.findtext('distanceradius')) < 300):
            raise ValueError('invalid encounter lifecycle')
    group_names = {g.get('name') for g in groups}
    used = set()
    coords = set()
    count = 0
    for e in positions:
        if len(e.findall('pos')) < int(events.find("event[@name='%s']/nominal" % e.get('name')).text):
            raise ValueError('insufficient encounter positions')
        for p in e.findall('pos'):
            if p.get('group') not in group_names:
                raise ValueError('missing encounter group')
            used.add(p.get('group'))
            x, z = float(p.get('x')), float(p.get('z'))
            if not (0 < x < 15360 and 0 < z < 15360) or (x, z) in coords:
                raise ValueError('duplicate or invalid encounter anchor')
            if any(math.hypot(x - a, z - b) < 340 for a, b in coords):
                raise ValueError('encounter anchors less than 340 m apart')
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
    return data, (events, positions, groups, proto), evidence, {
        'event_types': len(events), 'nominal': nominal, 'positions': count,
        'groups': len(groups), 'objects_in_groups': sum(len(g) for g in groups),
        'runtime': 'PENDING'}


def _digest(data):
    return economy.sha(b''.join(n.encode() + b'\0' + data[n] for n in DATA))


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
    files[GENERATED] = data['hc-events.xml']
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
    parser.add_argument('command', choices=('plan', 'install', 'rollback'))
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--mission', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'rollback':
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
