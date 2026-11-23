"""CE loot groups for placed Chernarus buildings that stock leaves without any.

Stock mapgroupproto.xml has no group for many classed world buildings, so the CE never spawns there.
This layer adds a group for each selected class plus one mapgrouppos row per placed instance.
The loot boost applies it in the same receipted install (see loot_boost.plan).

There are two kinds of group in ``mission/hollow-country/loot-points/new-buildings.json``:

* ``copy``: the class uses the same installed p3d as a stock group authored for another map (the
  Livonia ``*_DE`` wrecks). Install copies that group's rows verbatim from the mission's own
  mapgroupproto.xml, renamed. It refuses the copy if the source group no longer matches its pin.
* ``generated``: points are made offline from installed ODOL LODs. A floor point must have floor
  support, a roof above it, clear standing space, and a walk connection to a door or ladder memory
  point or an audited native standing seed. These checks reuse the loot_reach_audit scene and body checks. Surface points come from
  interior_points_gen.generate with its collision, room and reach audits, run on a synthetic proto
  seeded with those floor points. Usage, categories and tags are taken from a named stock analog
  group.

Positions are the installed world's classed objects, read from ChernarusPlus.wrp (read-only, pinned
by hash). Rotation comes from each object's own transform. The same derivation reproduces every
stock mapgrouppos row except the small boats (see sources.world.validation). Rows are written only
when the mission's mapgrouppos.xml is the pinned stock file, so any other map or game build
changes nothing.

Optional native censuses supply standing evidence through the shared admission parser. CE spawning,
ExportProxyData agreement, reachability and loot density stay pending a native treatment run.

Generate (offline, heavy): ``python3 -B -m tools.package.new_buildings generate --addons <full-client>/addons
--mission <stock chernarus mission> --scratch <fresh directory> [--native-census <file>] --out <file>``.
"""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import re
import struct
import sys
import xml.etree.ElementTree as ET

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.package import economy  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
PATH = Path('mission/hollow-country/loot-points/new-buildings.json')
FLOOR_POLICY = Path('mission/hollow-country/loot-points/floor-policy.json')
# Copied groups that floor-policy.json lists as receivers carry this note in their basis.
RECEIVER_NOTE = ('; #326/#327: floor-policy.json relocates exact raised donor points to lootHCReceiver for '
                 'shelf-tagged Farm equipment; ground points stay separate; native acceptance pending')
KIND = 'hollow-country-loot-new-buildings'
PENDING = 'pending'
MARKER = 'hollow-country-new-buildings'
NAME = re.compile(r'[A-Za-z0-9_]{1,80}')
HEX = re.compile(r'[0-9a-f]{64}')
MAX_GROUP_LOOTMAX = 40
MAX_CONTAINER_POINTS = 48
MAX_INSTANCES = 1000
MAX_COORDINATE = 200.0
POINT_SHAPE = {'floor': ('0.500000', '1.200000'), 'surface': ('0.300000', '0.500000')}  # range, height

# Pinned installed world (DayZ 1.30.164289): ChernarusPlus.wrp member of worlds_chernarusplus.pbo.
WORLD_PBO = 'worlds_chernarusplus.pbo'
WORLD_MEMBER = 'ChernarusPlus.wrp'
WORLD_SHA256 = 'a0abe0c1dcadcad1aca90611b3edb505100e023a57d7e52d8caa3cd2cf14cc7a'
STOCK_POS_SHA256 = '3eeaad9786a73c339f61f6e6ad203f0732e36b88f27333978cc8b4beece9cec4'
MODELS_AT, CLASSED_AT, CLASSED_END = 18089648, 18203226, 19896284
OBJECTS_AT, OBJECT_SIZE, OBJECT_COUNT = 27151045, 64, 2971251
WORLD_MAX_BYTES = 256 * 1024 * 1024

# Selected classes -> how their group is made. ``copy`` names the stock group on the same p3d;
# ``analog`` names the stock group whose usage/categories/tags the generated containers inherit.
SELECTION = {
    'Land_Wreck_Uaz': {'kind': 'copy', 'copy_of': 'StaticObj_Wreck_Uaz_DE'},
    'Land_Wreck_Tractor': {'kind': 'copy', 'copy_of': 'Land_Wreck_Tractor_DE'},
    'Land_Wreck_Trailer_Closed': {'kind': 'copy', 'copy_of': 'Land_Wreck_Trailer_Closed_DE'},
    'Land_Mil_Tower_Small': {'kind': 'generated', 'analog': 'Land_Mil_GuardTower'},
    'Land_Farm_WaterTower_Small': {'kind': 'generated', 'analog': 'Land_Tower_TC1'},
    'Land_Misc_Toilet_Mobile': {'kind': 'generated', 'analog': 'Land_Misc_Toilet_Dry'},
    'Land_Church2_1': {'kind': 'generated', 'analog': 'Land_Church2_2'},
    'Land_Office_Municipal1': {'kind': 'generated', 'analog': 'Land_Office2'},
    'Land_Cementworks_Conveyorhall': {'kind': 'generated', 'analog': 'Land_CementWorks_Hall1'},
    'Land_CementWorks_SiloBig1B': {'kind': 'generated', 'analog': 'Land_CementWorks_SiloBig1A'},
    'Land_CementWorks_MillA': {'kind': 'generated', 'analog': 'Land_CementWorks_MillB'},
    'Land_Castle_Donjon': {'kind': 'generated', 'analog': 'Land_Castle_Bergfrit2'},
    'Land_HouseBlock_2F1': {'kind': 'generated', 'analog': 'Land_HouseBlock_2F1'},
    'Land_Mil_Barracks2': {'kind': 'generated', 'analog': 'Land_Mil_Barracks2'},
    'Land_Wreck_Harverster': {'kind': 'generated', 'analog': 'Land_Wreck_Tractor_DE'},
    'Land_Wreck_Harvester_head_trailer': {'kind': 'generated', 'analog': 'Land_Wreck_Trailer_Closed_DE'},
    'Land_Wreck_C130J_2': {'kind': 'generated', 'analog': 'Land_Wreck_C130J_Cargo'},
}

# Floor generation (model frame, metres). Reuses loot_reach_audit body/approach geometry checks.
GRID = 0.5
CEILING = (1.9, 8.0)        # a roof within this band above the floor point ("inside")
ENCLOSURE = (5.0, 3)         # at least 3 of 8 horizontal rays at 1 m hit structure within 5 m
SUPPORT_TOLERANCE = 0.03     # the 12 cm footprint must stay on the same floor plane
WALK_STEP = 0.3
ENTRY_REACH = (2.0, -0.6, 1.6)  # horizontal reach; entry point height above the seed floor (min, max)
DOOR_CLEAR = 1.0
FLOOR_SPACING = 1.5
FLOOR_AREA_PER_POINT = 8.0
ENTRY = re.compile(r'(doors?\d*(_action)?|aidoor\d+|point\w*door|ladder\d+_(top|bottom)_front)$')
DOOR = re.compile(r'(doors?\d*(_action)?|aidoor\d+|point\w*door)$')
# Rows must not change other install-time gates: hc_events refuses a structural Land_ row within 80 m of an
# encounter site, and map_overlay reads mapgrouppos rows as height/clearance evidence for its objects.
EVENT_SITES = Path('mission/hollow-country/ce/hc-event-sites.json')
EVENT_CLEARANCE = 80.0
OVERLAY_CLEARANCE = 150.0
DOOR_LEAF = re.compile(r'(dvere|doors?)\d*$')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fmt(value):
    text = '%.6f' % value
    return '0.000000' if text == '-0.000000' else text


# ------------------------------------------------------------------------------------------------ schema


def _names(values, what):
    if (not isinstance(values, list) or not values or len(values) != len(set(values))
            or not all(isinstance(v, str) and NAME.fullmatch(v) for v in values)):
        raise ValueError('new building %s names must be unique safe names' % what)
    return values


def _finite(values, count, bound):
    return (isinstance(values, list) and len(values) == count
            and all(not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v)
                    and abs(v) <= bound for v in values))


def _lootmax(value):
    return value is None or (type(value) is int and 1 <= value <= MAX_GROUP_LOOTMAX)


def parse(data):
    if len(data) > 8 * 1024 * 1024:
        raise ValueError('new buildings input exceeds byte bound')
    doc = json.loads(data)
    if (not isinstance(doc, dict) or doc.get('schema') != 1 or doc.get('kind') != KIND
            or doc.get('runtime_acceptance') != PENDING or doc.get('frame') != 'stock-mapgroupproto'
            or not isinstance(doc.get('groups'), dict) or not isinstance(doc.get('world'), dict)):
        raise ValueError('not a new buildings layer')
    if not HEX.fullmatch(str(doc['world'].get('mapgrouppos_sha256'))):
        raise ValueError('new buildings need a stock mapgrouppos pin')
    seen = set()
    for name, spec in doc['groups'].items():
        if not NAME.fullmatch(name) or not isinstance(spec, dict) or name.casefold() in seen:
            raise ValueError('unsafe new building group')
        seen.add(name.casefold())
        if spec.get('kind') == 'copy':
            if not NAME.fullmatch(str(spec.get('copy_of'))) or not HEX.fullmatch(str(spec.get('stock_sha256'))):
                raise ValueError('copied group needs a source name and pin: ' + name)
        elif spec.get('kind') == 'generated':
            if not _lootmax(spec.get('lootmax')):
                raise ValueError('generated group lootmax bound: ' + name)
            _names(spec.get('usages'), 'usage')
            containers = spec.get('containers')
            if not isinstance(containers, list) or not containers:
                raise ValueError('generated group needs containers: ' + name)
            cnames = set()
            for c in containers:
                if (not isinstance(c, dict) or set(c) != {'name', 'shape', 'lootmax', 'categories', 'tags', 'points'}
                        or not _lootmax(c['lootmax'])
                        or not NAME.fullmatch(str(c['name'])) or c['name'] in cnames
                        or c['shape'] not in POINT_SHAPE or not isinstance(c['points'], list)
                        or not 1 <= len(c['points']) <= MAX_CONTAINER_POINTS):
                    raise ValueError('generated container shape or bounds: ' + name)
                cnames.add(c['name'])
                _names(c['categories'], 'category')
                if c['tags']:
                    _names(c['tags'], 'tag')
                if not all(_finite(p, 3, MAX_COORDINATE) for p in c['points']):
                    raise ValueError('generated point must be three finite model-frame coordinates: ' + name)
        else:
            raise ValueError('unknown new building group kind: ' + name)
        rows = spec.get('positions')
        if (not isinstance(rows, list) or not 1 <= len(rows) <= MAX_INSTANCES
                or not all(_finite(r, 7, 20000.0) for r in rows)):
            raise ValueError('new building positions: ' + name)
    return doc


def shipped(repo=REPO_ROOT):
    path = Path(repo) / PATH
    if not path.is_file():
        return None
    if path.is_symlink():
        raise ValueError('new buildings input must be a regular file')
    data = path.read_bytes()
    parse(data)
    return data


# ------------------------------------------------------------------------------------------------ apply


def _mask(text):
    return re.sub(r'<!--.*?-->', lambda m: re.sub(r'[^\n]', ' ', m.group(0)), text, flags=re.S)


def _group_span(text, masked, name):
    spans = []
    for m in re.finditer(r'<group\b[^>]*\bname="%s"[^>]*>' % re.escape(name), masked):
        close = masked.find('</group>', m.end())
        if close < 0 or m.group(0).endswith('/>'):
            raise ValueError('copied source group is not a closed element: ' + name)
        start = text.rfind('\n', 0, m.start()) + 1
        spans.append((start, m.start(), close + len('</group>')))
    if len(spans) != 1:
        raise ValueError('copied source group missing or repeated: ' + name)
    return spans[0]


def _render(name, spec, indent, unit, eol):
    def cap(value):
        return '' if value is None else ' lootmax="%d"' % value
    lines = ['%s<group name="%s"%s>' % (indent, name, cap(spec['lootmax']))]
    lines += ['%s<usage name="%s" />' % (indent + unit, u) for u in spec['usages']]
    for c in spec['containers']:
        shape = POINT_SHAPE[c['shape']]
        lines.append('%s<container name="%s"%s>' % (indent + unit, c['name'], cap(c['lootmax'])))
        inner = indent + unit * 2
        lines += ['%s<category name="%s" />' % (inner, n) for n in c['categories']]
        lines += ['%s<tag name="%s" />' % (inner, n) for n in c['tags']]
        lines += ['%s<point pos="%s" range="%s" height="%s" />' % (inner, ' '.join(fmt(v) for v in p), *shape)
                  for p in c['points']]
        lines.append('%s</container>' % (indent + unit))
    lines.append('%s</group>' % indent)
    return ''.join(line + eol for line in lines)


def apply(proto, positions, data, limits=None):
    """(proto bytes, mapgrouppos bytes, report). Unchanged inputs unless mapgrouppos is the pinned stock file."""
    from tools.package import loot_boost as loot
    doc = parse(data)
    report = {'applied': False, 'groups_added': 0, 'rows_added': 0, 'points_added': 0,
              'skipped': {}, 'layer_sha256': sha(data), 'runtime_acceptance': PENDING}
    if positions is None or sha(positions) != doc['world']['mapgrouppos_sha256']:
        report['reason'] = 'mapgrouppos is not the pinned stock Chernarus file; nothing added'
        return proto, positions, report
    text = proto.decode('utf-8-sig')
    masked = _mask(text)
    eol = '\r\n' if '\r\n' in text else '\n'
    root = economy.xml(proto, 'prototype')
    existing = {g.get('name', '').casefold() for g in root.iter('group')}
    placed = {g.get('name', '').casefold() for g in economy.xml(positions, 'map').iter('group')}
    stock = {}
    for g in root.iter('group'):
        stock.setdefault(g.get('name'), []).append(g)
    if limits is not None:
        categories, tags = limits
    blocks, added = [], {}
    first = re.search(r'<group\b', masked)
    indent = text[text.rfind('\n', 0, first.start()) + 1:first.start()] if first else '\t\t'
    unit = indent or '\t'  # stock nests by the group's own indent (two tabs per level)
    for name, spec in doc['groups'].items():
        if name.casefold() in existing or name.casefold() in placed:
            report['skipped'][name] = 'mission already has this group or placement'
            continue
        if spec['kind'] == 'copy':
            source = stock.get(spec['copy_of'], [])
            if len(source) != 1 or loot.group_pin(source[0]) != spec['stock_sha256']:
                report['skipped'][name] = 'copied source group differs from its pin'
                continue
            line, start, end = _group_span(text, masked, spec['copy_of'])
            body = text[start:end]
            body = re.sub(r'(<group\b[^>]*\bname=")%s(")' % re.escape(spec['copy_of']),
                          lambda m: m.group(1) + name + m.group(2), body, count=1)
            blocks.append(text[line:start] + body + eol)
            report['points_added'] += len(source[0].findall('.//point'))
        else:
            if limits is not None:
                missing = ({n for c in spec['containers'] for n in c['categories']} - categories) | (
                    {n for c in spec['containers'] for n in c['tags']} - tags)
                if missing:
                    raise ValueError('new building names absent from cfglimitsdefinition: %s' % sorted(missing))
            blocks.append(_render(name, spec, indent, unit, eol))
            report['points_added'] += sum(len(c['points']) for c in spec['containers'])
        added[name] = spec
    if not added:
        report['reason'] = 'no selected group applies to this mission'
        return proto, positions, report
    ends = [m for m in re.finditer(r'</prototype\s*>', masked)]
    if len(ends) != 1:
        raise ValueError('mapgroupproto.xml needs exactly one closing prototype tag')
    at = text.rfind('\n', 0, ends[0].start()) + 1
    if text[at:ends[0].start()].strip():
        at = ends[0].start()
    comment = '%s<!-- %s: %d group(s), offline only, runtime acceptance pending -->%s' % (
        indent, MARKER, len(added), eol)
    proto_after = economy_encode(text[:at] + comment + ''.join(blocks) + text[at:], proto)
    pos_text = positions.decode('utf-8-sig')
    pos_eol = '\r\n' if '\r\n' in pos_text else '\n'
    pos_masked = _mask(pos_text)
    pend = [m for m in re.finditer(r'</map\s*>', pos_masked)]
    if len(pend) != 1:
        raise ValueError('mapgrouppos.xml needs exactly one closing map tag')
    rows = ['    <!-- %s (runtime-unverified) -->' % MARKER]
    for name, spec in added.items():
        for x, y, z, r, p, w, a in spec['positions']:
            rows.append('    <group name="%s" pos="%s %s %s" rpy="%s %s %s" a="%s" />' % (
                name, fmt(x), fmt(y), fmt(z), fmt(r), fmt(p), fmt(w), fmt(a)))
    at = pos_text.rfind('\n', 0, pend[0].start()) + 1
    if pos_text[at:pend[0].start()].strip():
        at = pend[0].start()
    pos_after = economy_encode(pos_text[:at] + ''.join(r + pos_eol for r in rows) + pos_text[at:], positions)
    _verify(proto, proto_after, positions, pos_after, added)
    report.update({'applied': True, 'groups_added': len(added),
                   'rows_added': sum(len(s['positions']) for s in added.values()),
                   'groups': {n: {'kind': s['kind'], 'instances': len(s['positions'])} for n, s in added.items()}})
    report.pop('reason', None)
    return proto_after, pos_after, report


def economy_encode(text, original):
    data = text.encode('utf-8')
    return (b'\xef\xbb\xbf' + data) if original.startswith(b'\xef\xbb\xbf') else data


def _verify(proto, proto_after, positions, pos_after, added):
    from tools.package import loot_boost as loot
    old, new = economy.xml(proto, 'prototype'), economy.xml(proto_after, 'prototype')
    old_groups, new_groups = list(old.iter('group')), list(new.iter('group'))
    if [g.get('name') for g in new_groups] != [g.get('name') for g in old_groups] + list(added):
        raise ValueError('new buildings verification failed: proto groups')
    if [loot.group_pin(g) for g in old_groups] != [loot.group_pin(g) for g in new_groups[:len(old_groups)]]:
        raise ValueError('new buildings verification failed: stock groups changed')
    for g in new_groups[len(old_groups):]:
        spec = added[g.get('name')]
        if spec['kind'] == 'copy':
            source = [s for s in old_groups if s.get('name') == spec['copy_of']][0]
            twin = ET.fromstring(ET.tostring(g))
            twin.set('name', spec['copy_of'])
            if loot.group_pin(twin) != spec['stock_sha256'] or loot.group_pin(source) != spec['stock_sha256']:
                raise ValueError('new buildings verification failed: copied group ' + g.get('name'))
        else:
            got = [[[float(v) for v in p.get('pos').split()] for p in c.findall('point')] for c in g.findall('container')]
            want = [[[round(v, 6) for v in p] for p in c['points']] for c in spec['containers']]
            caps = [None if c.get('lootmax') is None else int(c.get('lootmax')) for c in g.findall('container')]
            if (got != want or (None if g.get('lootmax') is None else int(g.get('lootmax'))) != spec['lootmax']
                    or caps != [c['lootmax'] for c in spec['containers']]):
                raise ValueError('new buildings verification failed: generated group ' + g.get('name'))
    a, b = economy.xml(positions, 'map'), economy.xml(pos_after, 'map')
    old_rows, new_rows = list(a.iter('group')), list(b.iter('group'))
    if [r.attrib for r in new_rows[:len(old_rows)]] != [r.attrib for r in old_rows]:
        raise ValueError('new buildings verification failed: stock rows changed')
    if [r.get('name') for r in new_rows[len(old_rows):]] != [n for n, s in added.items() for _ in s['positions']]:
        raise ValueError('new buildings verification failed: added rows')


# ------------------------------------------------------------------------------------------------ world


def read_world(addons):
    """[(class, model, x, y, z, matrix12)] for every classed WRP object; refuses any other world build."""
    from tools.audit import pbo_config as pbo
    path = Path(addons) / WORLD_PBO
    index = pbo.read_pbo_index(path)
    names = [e['name'] for e in index['entries'] if e['name'].lower() == WORLD_MEMBER.lower()]
    if len(names) != 1:
        raise ValueError('world member missing: ' + WORLD_MEMBER)
    data = pbo.read_member(path, index, names[0], max_bytes=WORLD_MAX_BYTES)
    if sha(data) != WORLD_SHA256:
        raise ValueError('installed world differs from the pinned build; re-derive offsets first')
    count = struct.unpack_from('<I', data, MODELS_AT)[0]
    models, at = [], MODELS_AT + 4
    for _ in range(count):
        stop = data.index(b'\0', at)
        models.append(pbo.normalize_path(data[at:stop].decode('ascii')))
        at = stop + 1
    if not all(m.endswith('.p3d') for m in models):
        raise ValueError('world model table did not parse')
    count, at = struct.unpack_from('<I', data, CLASSED_AT)[0], CLASSED_AT + 4
    classed = []
    for _ in range(count):
        stop = data.index(b'\0', at)
        cls = data[at:stop].decode('ascii')
        at = stop + 1
        stop = data.index(b'\0', at)
        model = pbo.normalize_path(data[at:stop].decode('ascii'))
        at = stop + 1
        x, y, z = struct.unpack_from('<3f', data, at)
        at += 20
        classed.append((cls, model, x, y, z))
    if at != CLASSED_END:
        raise ValueError('world classed list did not parse')
    by_model = {}
    for i, m in enumerate(models):
        by_model.setdefault(m, []).append(i)
    wanted = {i for c in classed for i in by_model[c[1]]}
    records = {}
    for k in range(OBJECT_COUNT):
        o = OBJECTS_AT + k * OBJECT_SIZE
        mi = struct.unpack_from('<I', data, o + 12)[0]
        if mi >= len(models):
            raise ValueError('world object table did not parse')
        if mi in wanted:
            records.setdefault(mi, []).append(struct.unpack_from('<12f', data, o + 16))
    grid = {}
    for mi, rows in records.items():
        for m in rows:
            grid.setdefault((mi, round(m[9]), round(m[11])), []).append(m)
    out = []
    for cls, model, x, y, z in classed:
        hits = [m for mi in by_model[model] for dx in (-1, 0, 1) for dz in (-1, 0, 1)
                for m in grid.get((mi, round(x) + dx, round(z) + dz), ())
                if math.hypot(m[9] - x, m[11] - z) < 0.05]
        if len(hits) != 1:
            raise ValueError('classed object without exactly one transform: %s at %.2f %.2f' % (cls, x, z))
        out.append((cls, model, x, y, z, hits[0]))
    return out, sha(data)


def orientation(m):
    """(roll, pitch, yaw, a) in mapgrouppos convention from the WRP basis rows (aside, up, dir)."""
    ax, ay, az, ux, uy, uz, dx, dy, dz = m[:9]
    return (-math.degrees(math.atan2(ay, uy)), math.degrees(math.atan2(dy, math.hypot(dx, dz))),
            math.degrees(math.atan2(dx, dz)), math.degrees(math.atan2(dz, dx)))


def validate_world(world, stock_pos):
    """Reproduce every stock mapgrouppos row from the world rows; returns counts and worst errors."""
    index = {}
    for cls, model, x, y, z, m in world:
        index.setdefault((cls.casefold(), round(x), round(z)), []).append((x, y, z, m))
    result = {'rows': 0, 'matched': 0, 'max_pos_m': 0.0, 'max_yaw_deg': 0.0, 'max_roll_deg': 0.0,
              'max_a_deg': 0.0, 'max_pitch_deg': 0.0, 'pitch_mismatch_classes': {}}
    def diff(a, b):
        return abs((a - b + 180.0) % 360.0 - 180.0)
    for g in economy.xml(stock_pos, 'map').iter('group'):
        result['rows'] += 1
        p = [float(v) for v in g.get('pos').split()]
        rpy = [float(v) for v in g.get('rpy').split()]
        hits = [h for dx in (-1, 0, 1) for dz in (-1, 0, 1)
                for h in index.get((g.get('name').casefold(), round(p[0]) + dx, round(p[2]) + dz), ())
                if math.hypot(h[0] - p[0], h[2] - p[2]) < 0.05]
        if len(hits) != 1:
            continue
        result['matched'] += 1
        x, y, z, m = hits[0]
        r, pt, w, a = orientation(m)
        result['max_pos_m'] = max(result['max_pos_m'], abs(x - p[0]), abs(y - p[1]), abs(z - p[2]))
        result['max_yaw_deg'] = max(result['max_yaw_deg'], diff(w, rpy[2]))
        result['max_roll_deg'] = max(result['max_roll_deg'], diff(r, rpy[0]))
        result['max_a_deg'] = max(result['max_a_deg'], diff(a, float(g.get('a'))))
        if diff(pt, rpy[1]) > 0.01:
            name = g.get('name')
            result['pitch_mismatch_classes'][name] = result['pitch_mismatch_classes'].get(name, 0) + 1
        else:
            result['max_pitch_deg'] = max(result['max_pitch_deg'], diff(pt, rpy[1]))
    for k in ('max_pos_m', 'max_yaw_deg', 'max_roll_deg', 'max_a_deg', 'max_pitch_deg'):
        result[k] = round(result[k], 6)
    return result


# ------------------------------------------------------------------------------------------------ points


def _lod(model, resolution):
    return next((l for l in model.lods if math.isclose(l.resolution, resolution, rel_tol=1e-6)), None)


def _walk_scene(model, scene):
    """The audit scene with door leaves removed from the collision LOD: players open doors to walk in.

    Audit.scene adds geometry, then roadway, then proxy furniture; the proxy tail is kept unchanged.
    """
    import copy
    from tools.package import loot_reach_audit as reach
    geometry, roadway = _lod(model, reach.GEOMETRY), _lod(model, reach.ROADWAY)
    head = len(list(reach.collision_triangles(model, geometry))) + (
        len(list(reach.collision_triangles(model, roadway))) if roadway is not None else 0)
    leaves = {i for sel in geometry.named_selections if DOOR_LEAF.fullmatch(sel.name.lower()) for i in sel.faces}
    if not leaves:
        return scene
    open_lod = copy.copy(geometry)
    open_lod.faces = [f for i, f in enumerate(geometry.faces) if i not in leaves]
    walk = reach.Scene()
    walk.add(reach.collision_triangles(model, open_lod))
    if roadway is not None:
        walk.add(reach.collision_triangles(model, roadway))
    walk.add(scene.triangles[head:])
    return walk


def native_inputs(paths):
    """Reuse the template/profile admission parser; retain raw hashes, never raw censuses."""
    from tools.package import interior_templates as templates
    from tools.audit import interior_points as pts
    docs = sorted((templates.load_census(Path(p).read_bytes()) for p in paths), key=lambda d: d['run'])
    if len({d['run'] for d in docs}) != len(docs):
        raise ValueError('two censuses share one native_run_id')
    seen = {}
    for doc in docs:
        templates._check_house_conflicts(doc['houses'], seen)
        verdicts = {r['verdict'] for r in pts.frame_verdict(doc['doc'])['classes'].values()
                    if r['verdict'] is not None}
        if verdicts != {'rot90'}:
            raise ValueError('native census needs unambiguous rot90 frame calibration')
    by_class = {}
    for doc in docs:
        for row in doc['doc']['placements']:
            name = row['class']
            item = by_class.setdefault(name, {'hits': [], 'runs': [], 'refusals': []})
            provenance = {'native_run_id': doc['run'], 'observed_hit_count': len(row['hits']), 'hit_count': 0}
            item['runs'].append(provenance)
            if not pts._usable(row):
                item['refusals'].append('missing object or capped native observation')
                continue
            codes = pts._row_codes(row, 'player', name)
            no_door = pts._control_state(row, 'player') == 'no-door'
            door_ok = pts._gate_passed(row, 'player') and pts._door_run_problem(row.get('door_run')) is None
            for hit, code in zip(row['hits'], codes):
                # Unknown no-door paths provide standing evidence only. A tested failed path never admits.
                if (code == 1 and door_ok) or (code == -1 and no_door):
                    item['hits'].append(tuple(hit[:4]))
                    provenance['hit_count'] += 1
            if row['hits'] and not (no_door or door_ok):
                item['refusals'].append('native player entry/door control not admitted')
    return docs, by_class


def _floor_audit(x, y, z, footprint, visual, scene, solid, stats, native=False):
    """Shared support/roof/enclosure/loader audits; native standing replaces only body_clear."""
    from tools.package import loot_reach_audit as reach
    if not all(any(abs(h - y) <= SUPPORT_TOLERANCE for h in footprint.floors(x + dx, z + dz, y - .1, y + .1))
               for dx, dz in ((0, 0), (.12, 0), (-.12, 0), (0, .12), (0, -.12))):
        return False, False
    stats['supported'] += 1
    if not native and not reach.body_clear(scene, (x, y, z)):
        return False, False
    stats['standing'] += 1
    ceilings = [h[0] for h in visual.hits(x, z) if h[0] > y + .10]
    if ceilings and min(ceilings) - y < CEILING[0]:
        return True, False
    if not (ceilings and min(ceilings) - y <= CEILING[1]) and scene.clear(
            (x, y + CEILING[0], z), (x, y + CEILING[1], z)):
        return True, False
    stats['roofed'] += 1
    walls = sum(not solid.clear((x, y + 1.0, z),
                               (x + ENCLOSURE[0] * math.cos(t * math.tau / 8), y + 1.0,
                                z + ENCLOSURE[0] * math.sin(t * math.tau / 8))) for t in range(8))
    if walls < ENCLOSURE[1]:
        return True, False
    stats['enclosed'] += 1
    if any(not scene.clear((x + dx, y + .025, z + dz), (x + dx, y + .525, z + dz))
           for dx, dz in ((0, 0), (.12, 0), (-.12, 0), (0, .12), (0, -.12))):
        return True, False
    stats['eligible'] += 1
    return True, True


def floor_points(auditor, name, pin, native=None):
    """(CE-frame floor points, evidence) for one class from its installed ODOL LODs; raises on no model."""
    from tools.package import interior_points_gen as ipg
    from tools.package import loot_reach_audit as reach
    from tools.package import loot_boost as loot
    _, model, visual, scene, bounds, _, footprint = auditor.scene(name, {'stock_sha256': pin})
    scene, solid = _walk_scene(model, scene), scene
    memory = _lod(model, reach.MEMORY)
    entries, doors = [], []
    for s in (memory.named_selections if memory else ()):
        label = s.name.lower()
        if ENTRY.fullmatch(label):
            verts = [memory.vertices[i] for i in s.vertices]
            if verts:
                centre = [sum(v[a] for v in verts) / len(verts) for a in range(3)]
                centre[1] = min(v[1] for v in verts)  # door/ladder selections span upward from their sill
                entries.append(centre)
                if DOOR.fullmatch(label):
                    doors.append(centre)
    stats = {'entry_points': len(entries), 'cells': 0, 'supported': 0, 'standing': 0, 'roofed': 0, 'enclosed': 0, 'eligible': 0,
             'connected': 0, 'door_clear': 0}
    if bounds is None:
        return [], dict(stats, refusal='no-bounds')
    cells, eligible = {}, set()
    native = native or {'hits': [], 'runs': []}
    native_stats = {key: 0 for key in ('supported', 'standing', 'roofed', 'enclosed', 'eligible', 'clearance_rejected')}
    native_points = []
    for x, y, z, clearance in sorted(set(tuple(h) for h in native['hits'])):
        if clearance < CEILING[0]:
            native_stats['clearance_rejected'] += 1
            continue
        standing, admitted = _floor_audit(x, y, z, footprint, visual, scene, solid, native_stats, native=True)
        if admitted:
            native_points.append((x, y, z))
    stats['native'] = dict(native_stats, runs=native['runs'], hit_count=len(native['hits']),
                           audited_points=len(native_points), path='standing seeds; entry reach pending for no-door')
    lo, hi = bounds['Min'], bounds['Max']
    for i in range(math.floor(lo[0] / GRID), math.floor(hi[0] / GRID) + 1):
        for k in range(math.floor(lo[2] / GRID), math.floor(hi[2] / GRID) + 1):
            x, z = (i + .5) * GRID, (k + .5) * GRID
            for y in footprint.floors(x, z, lo[1] - 1, hi[1] + 1):
                stats['cells'] += 1
                standing, admitted = _floor_audit(x, y, z, footprint, visual, scene, solid, stats)
                if standing:
                    cells.setdefault((i, k), []).append(y)
                if admitted:
                    eligible.add((i, k, y))
    # Walk from entry memory points over standing cells; neighbours need a clear body corridor.
    seeds = [(i, k, y) for (i, k), ys in cells.items() for y in ys
             if any(math.hypot((i + .5) * GRID - e[0], (k + .5) * GRID - e[2]) <= ENTRY_REACH[0]
                    and ENTRY_REACH[1] <= e[1] - y <= ENTRY_REACH[2] for e in entries)]
    # Native points are independently audited standing seeds. Nearby grid cells still need a clear corridor.
    seeds += [(i, k, y) for (i, k), ys in cells.items() for y in ys
              if any(math.hypot((i + .5) * GRID - x, (k + .5) * GRID - z) <= GRID
                     and abs(y - ny) <= SUPPORT_TOLERANCE
                     and reach.approach_clear(scene, (x, ny, z), ((i + .5) * GRID, y, (k + .5) * GRID))
                     for x, ny, z in native_points)]
    seen, queue = set(seeds), list(seeds)
    while queue:
        i, k, y = queue.pop()
        for di, dk in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for y2 in cells.get((i + di, k + dk), ()):
                other = (i + di, k + dk, y2)
                if other in seen or abs(y2 - y) > WALK_STEP:
                    continue
                if reach.approach_clear(scene, ((i + .5) * GRID, y, (k + .5) * GRID),
                                        ((i + di + .5) * GRID, y2, (k + dk + .5) * GRID)) or abs(y2 - y) > .2 and all(
                        scene.clear(((i + .5) * GRID, y + h, (k + .5) * GRID),
                                    ((i + di + .5) * GRID, y2 + h, (k + dk + .5) * GRID)) for h in (.5, .9, 1.65)):
                    seen.add(other)
                    queue.append(other)
    stats['connected'] = len(seen)
    stats['connected_eligible'] = len(seen & eligible)
    candidates = []
    raw_candidates = list(native_points) + [((i + .5) * GRID, y, (k + .5) * GRID) for i, k, y in seen & eligible]
    for x, y, z in raw_candidates:
        if any(abs(x - d[0]) <= DOOR_CLEAR and abs(z - d[2]) <= DOOR_CLEAR and -0.6 <= d[1] - y <= 1.6 for d in doors):
            continue
        candidates.append((round(z, 6), round(y + .005, 6), round(-x, 6)))  # CE frame = (z, y, -x)
    stats['door_clear'] = len(candidates)
    # Native samples count only where the finer offline grid did not already cover their area.
    extra = sum(not any(math.hypot(x - (i + .5) * GRID, z - (k + .5) * GRID) <= GRID
                        and abs(y - gy) <= SUPPORT_TOLERANCE for i, k, gy in seen & eligible)
                for x, y, z in native_points)
    area = len(seen & eligible) * GRID * GRID + extra * GRID * GRID
    limit = min(MAX_CONTAINER_POINTS, max(1, int(area / FLOOR_AREA_PER_POINT)))
    chosen = loot._spread(candidates, [], FLOOR_SPACING, limit)
    stats['chosen'] = len(chosen)
    return [list(p) for p in chosen], stats


def _analog(stock, name):
    groups = [g for g in stock.findall('group') if g.get('name') == name]
    if len(groups) != 1:
        raise ValueError('stock analog group missing: ' + name)
    g = groups[0]
    containers = []
    for c in g.findall('container'):
        containers.append({'name': c.get('name'), 'lootmax': c.get('lootmax'),
                           'categories': [x.get('name') for x in c.findall('category')],
                           'tags': [x.get('name') for x in c.findall('tag')],
                           'points': len(c.findall('point'))})
    return g, [u.get('name') for u in g.findall('usage')], containers


def _scaled(analog_max, analog_points, points):
    """The analog's lootmax per point applied to ``points``, never above the analog's own value; None if it has none."""
    if analog_max is None:
        return None
    analog_max = int(analog_max)
    return max(1, min(analog_max, round(points * analog_max / analog_points) if analog_points else 1))


def _containers(analog, floor, surface):
    """Map generated floor/surface points onto the analog's own container names, categories, tags and density."""
    weapons = [c for c in analog if {'weapons', 'explosives'} & set(c['categories']) and 'shelves' not in c['tags']
               and 'floor' not in c['tags']]
    floors = [c for c in analog if 'floor' in c['tags'] or c['name'].lower() == 'lootfloor'] or [analog[0]]
    shelves = [c for c in analog if 'shelves' in c['tags'] and c not in floors]
    floor_pts, weapon_pts = list(floor), []
    # The analog keeps weapons in their own floor-level container: hand it every third floor point.
    if weapons and len(floor_pts) >= 3:
        weapon_pts, floor_pts = floor_pts[::3], [p for i, p in enumerate(floor_pts) if i % 3]
    rows = [(floors[0], 'floor', floor_pts), (weapons[0] if weapons else None, 'floor', weapon_pts)]
    if surface:
        rows.append((shelves[0] if shelves else floors[0], 'surface', surface))
    out = []
    for c, shape, points in rows:
        if not points:
            continue
        own = shape == 'floor' or c in shelves
        out.append({'name': c['name'] if own else 'lootshelves', 'shape': shape,
                    'lootmax': _scaled(c['lootmax'], c['points'], len(points)),
                    'categories': c['categories'], 'tags': c['tags'] if own else ['shelves'], 'points': points})
    return out


def _structural(name):
    """hc_events' building rule: Land_ rows other than wrecks, misc props and ruins."""
    return name.startswith('Land_') and not any(v in name for v in ('Wreck', 'Misc', 'Ruins'))


def exclusions(instances, stock_pos):
    """(kept instances, dropped counts): drop rows that would alter the hc_events or map_overlay gates."""
    from tools.package import map_overlay as mo
    source = mo.load_source()
    anchors = []
    for layer in source.layers:
        anchors += [site['pos'] for site in layer.get('sites', [])]
        anchors += [item['pos'] for item in mo.expand_layer(source, layer) if isinstance(item.get('pos'), list)]
    sites = [(float(r['authored_position']['x']), float(r['authored_position']['z']))
             for r in json.loads((REPO_ROOT / EVENT_SITES).read_bytes())['sites']]
    kept, dropped = {}, {}
    for name, rows in instances.items():
        for row in rows:
            event = _structural(name) and any(math.hypot(row[0] - x, row[2] - z) < EVENT_CLEARANCE for x, z in sites)
            overlay = any(math.hypot(row[0] - a[0], row[2] - a[2]) < OVERLAY_CLEARANCE for a in anchors)
            if event or overlay:
                key = 'event_site_%dm' % EVENT_CLEARANCE if event else 'map_overlay_%dm' % OVERLAY_CLEARANCE
                dropped.setdefault(name, {}).setdefault(key, 0)
                dropped[name][key] += 1
            else:
                kept.setdefault(name, []).append(row)
    stock = [(g.get('name'), *(float(v) for v in g.get('pos').split()))
             for g in economy.xml(stock_pos, 'map').iter('group')]
    added = [(name, row[0], row[1], row[2]) for name, rows in kept.items() for row in rows]
    before, after = set(mo.validate(source, stock, None)), set(mo.validate(source, stock + added, None))
    if after - before:
        raise ValueError('new building rows still change map_overlay validation: %s' % sorted(after - before)[:3])
    return kept, dropped


def generate(addons, mission, scratch, native_censuses=()):
    """The new-buildings layer as bytes; heavy (reads the world and ODOL models)."""
    from tools.audit import pbo_config as pbo
    from tools.package import interior_points_gen as ipg
    from tools.package import loot_reach_audit as reach
    from tools.package import loot_boost as loot
    docs, native = native_inputs(native_censuses)
    mission, scratch = Path(mission), Path(scratch)
    stock_proto_bytes = (mission / 'mapgroupproto.xml').read_bytes()
    stock_pos = (mission / 'mapgrouppos.xml').read_bytes()
    if sha(stock_pos) != STOCK_POS_SHA256:
        raise ValueError('mission mapgrouppos.xml is not the pinned stock Chernarus file')
    stock = economy.xml(stock_proto_bytes, 'prototype')
    world, world_sha = read_world(addons)
    validation = validate_world(world, stock_pos)
    print('world validation', json.dumps(validation), file=sys.stderr, flush=True)
    assets = ipg.Assets(addons, require_visual=True)
    config = {k.casefold(): k for k in assets.classes}
    instances = {}
    for cls, model, x, y, z, m in world:
        name = config.get(cls.casefold())
        if name in SELECTION:
            r, p, w, a = orientation(m)
            instances.setdefault(name, []).append([round(x, 6), round(y, 6), round(z, 6),
                                                   round(r, 6), round(p, 6), round(w, 6), round(a, 6)])
    instances, dropped = exclusions(instances, stock_pos)
    stock_names = {g.get('name').casefold() for g in stock.findall('group')}
    groups, refused, evidence = {}, {}, {}
    receivers = json.loads((REPO_ROOT / FLOOR_POLICY).read_bytes())['receivers']
    synthetic, pins = ET.Element('prototype'), {}
    for name, rule in SELECTION.items():
        sample = native.get(name)
        if sample and not any(r['observed_hit_count'] for r in sample['runs']):
            refused[name] = 'native census: no standable hits (run %s)' % ','.join(sorted({r['native_run_id'] for r in sample['runs']}))
            continue
        if name.casefold() in stock_names:
            refused[name] = 'stock already has this group'
            continue
        if not instances.get(name):
            refused[name] = 'no classed instance in the world'
            continue
        model = pbo.normalize_path(pbo.resolve_field(assets.classes, name, 'model') or '')
        if model not in assets.members:
            refused[name] = 'model not installed'
            continue
        model_sha = sha(assets.read(model))
        assets.cache.clear()
        if rule['kind'] == 'copy':
            source = [g for g in stock.findall('group') if g.get('name') == rule['copy_of']]
            src_model = pbo.normalize_path(pbo.resolve_field(assets.classes, rule['copy_of'], 'model') or '')
            if len(source) != 1 or src_model != model:
                refused[name] = 'copy source missing or on a different model'
                continue
            basis = 'stock group authored for the same installed p3d (copied at install)'
            if name in receivers:
                basis += RECEIVER_NOTE
            groups[name] = {'kind': 'copy', 'copy_of': rule['copy_of'], 'stock_sha256': loot.group_pin(source[0]),
                            'model': model, 'model_sha256': model_sha,
                            'basis': basis,
                            'positions': sorted(instances[name])}
            continue
        g = ET.SubElement(synthetic, 'group', {'name': name, 'lootmax': '1'})
        ET.SubElement(g, 'container', {'name': 'lootFloor'})
        pins[name] = (g, model, model_sha)
    scratch.mkdir(parents=True, exist_ok=False)
    seed_path = scratch / 'seed-proto.xml'
    seed_path.write_bytes(ET.tostring(synthetic))
    auditor = reach.Audit(addons, None, seed_path, REPO_ROOT)
    floors = {}
    for name, (g, model, model_sha) in pins.items():
        print('floor ' + name, file=sys.stderr, flush=True)
        points, stats = floor_points(auditor, name, loot.group_pin(g), native.get(name))
        evidence[name] = {'floor': stats}
        if native.get(name):
            evidence[name]['native_provenance'] = native[name]['runs']
            evidence[name]['native_refusals'] = native[name]['refusals']
        if name == 'Land_Office_Municipal1':
            heights = [h[1] for h in native.get(name, {}).get('hits', [])]
            ground = min(heights) if heights else min((p[1] for p in points), default=0)
            upper = [p for p in points if p[1] > ground + CEILING[0]]
            evidence[name]['upper_floors'] = {'points': len(upper),
                'native_upper_hits': sum(y > ground + CEILING[0] for y in heights),
                'ground_height': ground, 'reason': (
                'native-seeded points above ground storey' if upper else
                'no upper-floor point passed support/roof/standing/entry-connection checks')}
        auditor.props.clear()
        auditor.meshes.clear()
        auditor.assets.cache.clear()
        if not points:
            reason = 'no floor point passed support/roof/standing/entry-connection checks'
            ns = stats.get('native', {})
            if native.get(name):
                reason += '; native audits: ' + ', '.join('%s=%s' % (key, ns.get(key, 0)) for key in
                    ('hit_count', 'clearance_rejected', 'supported', 'roofed', 'enclosed', 'eligible'))
            refused[name] = reason
            continue
        floors[name] = points
    # Surface points: interior_points_gen on a proto whose new groups carry the floor points above.
    seeded = ET.Element('prototype')
    for name, points in floors.items():
        g = ET.SubElement(seeded, 'group', {'name': name, 'lootmax': '1'})
        c = ET.SubElement(g, 'container', {'name': 'lootFloor'})
        for p in points:
            ET.SubElement(c, 'point', {'pos': ' '.join(fmt(v) for v in p), 'range': POINT_SHAPE['floor'][0],
                                       'height': POINT_SHAPE['floor'][1]})
    floor_path = scratch / 'floor-proto.xml'
    floor_path.write_bytes(ET.tostring(seeded))
    surfaces = json.loads(ipg.generate(addons, floor_path, None)) if floors else {'groups': {}, 'sources': {}}
    for name, points in floors.items():
        g, model, model_sha = pins[name]
        analog, usages, containers = _analog(stock, SELECTION[name]['analog'])
        surface = []
        spec = surfaces['groups'].get(name)
        if spec:
            surface = spec['containers']['lootHCSurface']['points']
            evidence[name]['surface_sources'] = len(spec.get('surface_sources', []))
        built = _containers(containers, points, surface)
        total = sum(len(c['points']) for c in built)
        analog_points = sum(c['points'] for c in containers)
        groups[name] = {'kind': 'generated', 'analog': SELECTION[name]['analog'],
                        'analog_sha256': loot.group_pin(analog), 'model': model, 'model_sha256': model_sha,
                        # Density follows the analog (its lootmax per point), never above the analog's own lootmax.
                        'lootmax': _scaled(analog.get('lootmax'), analog_points, total),
                        'usages': usages, 'containers': built, 'evidence': evidence[name],
                        'positions': sorted(instances[name])}
    for name in evidence:
        if name in refused:
            refused[name] = {'reason': refused[name], **evidence[name]}
    doc = {'schema': 1, 'kind': KIND, 'runtime_acceptance': PENDING, 'frame': 'stock-mapgroupproto',
           'world': {'mapgrouppos_sha256': STOCK_POS_SHA256, 'wrp_member': WORLD_PBO + '/' + WORLD_MEMBER,
                     'wrp_sha256': world_sha, 'validation': validation,
                     'orientation': 'roll=-atan2(aside.y, up.y), pitch=atan2(dir.y, |dir.xz|), yaw=atan2(dir.x, dir.z), '
                                    'a=atan2(dir.z, dir.x); position = classed-object xyz'},
           'sources': {'stock_proto_sha256': sha(stock_proto_bytes),
                       'native_censuses': [{'native_run_id': d['run'], 'sha256': d['sha']} for d in docs],
                       'native_method': 'native model-frame standing hits (rot90 calibration); shared support/roof/enclosure/loader audits; audited standing seeds widen entry evidence only; no-door reach remains pending',
                       'reader_revision': ipg.READER_REVISION, 'reader_sha256': ipg.READER_HASHES,
                       'surface_method': surfaces['sources'].get('method'),
                       'floor_method': ('ODOL geometry+roadway floors on a %.1f m grid; 12 cm footprint support; '
                                        'door leaves opened (removed from the walk scene); visual or collision/proxy roof %.1f-%.1f m above; 3 of 8 rays at 1 m hit structure within 5 m; loot_reach_audit body_clear and 50 cm loader '
                                        'box; 4-neighbour walk (|dy|<=%.1f m, approach_clear corridor) from door/ladder '
                                        'memory sills within 2 m; %.1f m door clearance; farthest-point spread %.1f m, one per '
                                        '%.0f m2 of connected floor' % (GRID, CEILING[0], CEILING[1], WALK_STEP,
                                                                       DOOR_CLEAR, FLOOR_SPACING, FLOOR_AREA_PER_POINT))},
           'gates': {'event_sites': EVENT_SITES.as_posix(), 'event_clearance_m': EVENT_CLEARANCE,
                     'map_overlay_clearance_m': OVERLAY_CLEARANCE, 'dropped_instances': dropped,
                     'map_overlay_validation': 'unchanged with the added rows'},
           'refused': refused, 'groups': groups}
    data = (json.dumps(doc, indent=1, sort_keys=False) + '\n').encode()
    parse(data)
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    g = sub.add_parser('generate', help='rebuild the layer offline from installed assets (heavy)')
    g.add_argument('--addons', required=True, type=Path)
    g.add_argument('--mission', required=True, type=Path, help='stock dayzOffline.chernarusplus folder (read-only)')
    g.add_argument('--reader', type=Path, default=None, help=argparse.SUPPRESS)  # legacy, ignored
    g.add_argument('--scratch', required=True, type=Path, help='fresh scratch folder for synthetic protos')
    g.add_argument('--native-census', type=Path, action='append', default=[], help='native interior census (repeatable, read-only)')
    g.add_argument('--out', required=True, type=Path)
    c = sub.add_parser('check', help='parse the shipped layer and dry-run it against a mission copy')
    c.add_argument('--mission', required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == 'generate':
        data = generate(args.addons, args.mission, args.scratch, args.native_census)
        args.out.write_bytes(data)
        print('wrote %s (%s)' % (args.out, sha(data)))
        return 0
    data = shipped()
    if data is None:
        print('no new buildings layer')
        return 1
    proto = (args.mission / 'mapgroupproto.xml').read_bytes()
    pos = (args.mission / 'mapgrouppos.xml').read_bytes()
    _, _, report = apply(proto, pos, data)
    print(json.dumps(report, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
