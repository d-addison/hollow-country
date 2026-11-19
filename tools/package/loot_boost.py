"""Receipted loot boost: scale non-firearm CE loot and add contextual building loot points.

Everything is generated at install time from the operator's own installed mission bytes; no vanilla
file or dump is shipped. One install edits, in place and with byte-exact backups:

* ``db/types.xml`` and every types file registered in ``cfgeconomycore.xml`` (except the generated
  optional-pack folder, which holds hunting/vehicle types, not building loot): ``nominal`` and ``min``
  are multiplied for the building-loot categories in SCALED_CATEGORIES only. Weapons, explosives,
  lootdispatch, uncategorised rows (vehicle parts) and every firearms-roster class keep their exact
  current values, so firearms, ammunition, magazines and attachments stay at the scarcity the owner chose.
* ``db/globals.xml``: ``RespawnTypes`` (types refilled per CE respawn cycle) is multiplied so a persistent
  storage reaches the larger nominals; every other knob is left alone and reported.
* ``mapgroupproto.xml``: group/container ``lootmax`` (defaults included) are multiplied, weapons-only
  containers keep their effective lootmax (written explicitly when they inherited a default), and the
  committed contextual points overlay (``mission/hollow-country/loot-points/additions.json``) adds
  ``lootHCFloor``/``lootHCSurface`` containers to buildings whose stock group still matches its pin.

The overlay is produced offline by ``points`` from native interior sampler censuses (model-frame floor
hits; furniture surfaces need a ``--intersect view`` census). Nothing here observes DayZ: whether the CE
spawns on the added containers, and the resulting loot density, stay pending native/server testing.

Install writes the receipt first, then fsynced backups, then switches each file through a staged
``.next`` and ``os.replace``. Each switch rehashes the live file after staging and verifies readback.
Rollback checks every file is in its recorded before/after state (and each needed backup matches)
before restoring anything, then rechecks each backup and live file at its switch; drift refuses and
keeps all recovery data. Interrupted restores can be retried after explicit operator reconciliation.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.package import economy  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
MANAGED = 'hollow-country-loot-boost'
POINTS_DIR = Path('mission/hollow-country/loot-points')
SETTINGS = POINTS_DIR / 'settings.json'
FAMILIES = POINTS_DIR / 'families.json'
ADDITIONS = POINTS_DIR / 'additions.json'
OVERLAY_KIND = 'hollow-country-loot-points'
POLICY_KIND = 'hollow-country-loot-families'
SETTINGS_KIND = 'hollow-country-loot-boost-settings'
PROTO = 'mapgroupproto.xml'
GLOBALS = 'db/globals.xml'
STOCK_TYPES = 'db/types.xml'
CORE = 'cfgeconomycore.xml'
LIMITS = 'cfglimitsdefinition.xml'
INPUTS = (GLOBALS,)  # read beyond economy.INPUTS + mapgroupproto (rehearsal scratch copies)
OPTIONAL_FOLDER = 'hollow-country-optional-packs'  # generated hunting/vehicle types; not building loot
SCALED_CATEGORIES = frozenset({'tools', 'containers', 'clothes', 'food', 'books'})
KEPT_CATEGORIES = frozenset({'weapons', 'explosives'})
MIN_MULTIPLIER, MAX_MULTIPLIER = 1.0, 4.0
RESPAWN_TYPES_CAP = 64
MAX_GROUP_LOOTMAX = 40
MAX_ADDED_LOOTMAX = 4
CONTAINERS = {'floor': 'lootHCFloor', 'surface': 'lootHCSurface'}
POINT_SHAPE = {'floor': ('0.500000', '1.200000'), 'surface': ('0.300000', '0.500000')}  # range, height
MAX_FLOOR_POINTS = 12
MAX_SURFACE_POINTS = 8
MAX_TOTAL_POINTS = 3000
MAX_COORDINATE = 200.0
# A point may sit below its building's lowest stock loot point only by a basement's depth. The committed overlay
# had one Land_Tower_TC2_Base point 20 m under the stock floor (a shaft or terrain hit, not a floor).
MAX_BELOW_STOCK_FLOOR = 8.0
# Floor selection tolerances on the sampler's 1 m lattice (provisional, offline).
MIN_CLEARANCE = 1.9
WALK_STEP = 0.3
STAIR_RISE = 1.2
STOCK_CLEAR = 1.0
STOCK_BAND = 0.4
DOOR_CLEAR = 1.0
CELLS_PER_POINT = 8  # one added floor spot per ~8 m2 of reachable floor, within [2, MAX_FLOOR_POINTS]
FLOOR_SPACING = 1.5
SURFACE_RISE = (0.4, 1.8)
SURFACE_CLEARANCE = 0.3
SURFACE_SPACING = 1.0
NAME = re.compile(r'[A-Za-z0-9_]{1,80}')
LABEL = re.compile(r'[a-z][a-z0-9_]{0,31}')
MANAGED_FILE = re.compile(r'(receipt\.json|[0-9]{2}\.backup|[0-9]{2}\.next)')
PENDING = 'pending'
ADVISORY = ('offline generation only: CE spawning on the added containers, the doubled density and respawn '
            'throughput are unobserved until a native server session')


def _sha(data):
    return economy.sha(data)


# ------------------------------------------------------------------------------------------------ settings


def _multiplier(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('loot multiplier must be a number')
    value = float(value)
    if not MIN_MULTIPLIER <= value <= MAX_MULTIPLIER:
        raise ValueError(f'loot multiplier must be within {MIN_MULTIPLIER}..{MAX_MULTIPLIER}')
    return value


def default_multiplier(repo=REPO_ROOT):
    doc = json.loads((Path(repo) / SETTINGS).read_bytes())
    if (not isinstance(doc, dict) or set(doc) != {'schema', 'kind', 'Multiplier'} or doc['schema'] != 1
            or doc['kind'] != SETTINGS_KIND):
        raise ValueError('loot-points/settings.json must be {schema 1, kind, Multiplier}')
    return _multiplier(doc['Multiplier'])


def shipped_points(repo=REPO_ROOT):
    path = Path(repo) / ADDITIONS
    return path.read_bytes() if path.is_file() else None


def scaled(value, multiplier):
    return int(math.floor(value * multiplier + 0.5))


# ------------------------------------------------------------------------------------------------ text helpers


def _mask(text):
    """Blank XML comments so regexes never edit commented-out rows; offsets stay identical."""
    return re.sub(r'<!--.*?-->', lambda m: re.sub(r'[^\n]', ' ', m.group(0)), text, flags=re.S)


def _attr(tag, name):
    found = re.search(r'\b%s="([^"]*)"' % name, tag)
    return found.group(1) if found else None


def _with_lootmax(tag, value):
    if re.search(r'\blootmax="[^"]*"', tag):
        return re.sub(r'\blootmax="[^"]*"', 'lootmax="%d"' % value, tag, count=1)
    changed, count = re.subn(r'(\bname="[^"]*")', r'\1 lootmax="%d"' % value, tag, count=1)
    if count != 1:
        raise ValueError('cannot place lootmax on a tag without name')
    return changed


def _apply(text, edits):
    edits = sorted(edits, key=lambda e: (e[0], e[1]))
    for (a, b, _), (c, _d, _r) in zip(edits, edits[1:]):
        if c < b:
            raise ValueError('overlapping edits')
    for start, end, replacement in reversed(edits):
        text = text[:start] + replacement + text[end:]
    return text


def _encode(text, original):
    data = text.encode('utf-8')
    return (b'\xef\xbb\xbf' + data) if original.startswith(b'\xef\xbb\xbf') else data


# ------------------------------------------------------------------------------------------------ types


def _roster_names():
    try:
        roster = json.loads((REPO_ROOT / 'tools/package/firearms_roster.json').read_bytes())
        return {e['class'].lower() for e in roster['entries']}
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError('firearms roster unreadable; refusing to guess which classes are firearms')


def _scales(categories, name, roster):
    cats = {c.lower() for c in categories}
    return bool(cats) and cats <= SCALED_CATEGORIES and not cats & KEPT_CATEGORIES and name.lower() not in roster


def scale_types(data, multiplier, roster=frozenset()):
    """Return (bytes, scaled_count) with nominal/min multiplied for building-loot categories only."""
    economy.xml(data, 'types')
    text = data.decode('utf-8-sig')
    masked = _mask(text)
    edits, expected = [], {}
    for opening in re.finditer(r'<type\b[^>]*>', masked):
        if opening.group(0).endswith('/>'):
            continue
        close = masked.find('</type>', opening.end())
        if close < 0:
            raise ValueError('unclosed type row')
        name = _attr(opening.group(0), 'name') or ''
        body = masked[opening.end():close]
        if not _scales(re.findall(r'<category\s+name="([^"]*)"', body), name, roster):
            continue
        values = {}
        for field in ('nominal', 'min'):
            found = list(re.finditer(r'(<%s>\s*)(\d+)(\s*</%s>)' % (field, field), body))
            if len(found) != 1:
                break
            values[field] = (found[0], int(found[0].group(2)))
        if len(values) != 2:
            continue
        nominal, minimum = values['nominal'][1], values['min'][1]
        new_nominal, new_min = scaled(nominal, multiplier), scaled(minimum, multiplier)
        if minimum <= nominal:
            new_min = min(new_min, new_nominal)
        for field, value in (('nominal', new_nominal), ('min', new_min)):
            match = values[field][0]
            start = opening.end() + match.start(2)
            edits.append((start, start + len(match.group(2)), str(value)))
        expected[name] = (new_nominal, new_min)
    output = _encode(_apply(text, edits), data)
    _verify_types(data, output, expected)
    return output, len(expected)


def _verify_types(before, after, expected):
    old, new = economy.xml(before, 'types'), economy.xml(after, 'types')
    rows_old, rows_new = old.findall('type'), new.findall('type')
    if [t.get('name') for t in rows_old] != [t.get('name') for t in rows_new]:
        raise ValueError('types verification failed: row order changed')
    for a, b in zip(rows_old, rows_new):
        name = a.get('name')
        if name in expected:
            if (int(b.findtext('nominal')), int(b.findtext('min'))) != expected[name]:
                raise ValueError(f'types verification failed: {name}')
            strip = ('nominal', 'min')
        else:
            strip = ()
        shape = lambda t: [(c.tag, sorted(c.attrib.items()), None if c.tag in strip else (c.text or '').strip())
                           for c in t]
        if shape(a) != shape(b) or a.attrib != b.attrib:
            raise ValueError(f'types verification failed: {name} changed beyond nominal/min')


def types_files(mission):
    """db/types.xml plus every registered ce types file (optional-pack folder excluded), in load order."""
    root = economy.xml(economy.read_plain(mission, CORE), 'economycore')
    names = [STOCK_TYPES]
    for ce in root.findall('ce'):
        folder = ce.get('folder') or ''
        if folder.strip('/') == OPTIONAL_FOLDER:
            continue
        for row in ce.findall('file'):
            if row.get('type') == 'types':
                name = folder.strip('/') + '/' + (row.get('name') or '')
                economy.child(mission, name)
                if name not in names:
                    names.append(name)
    return names


# ------------------------------------------------------------------------------------------------ globals


def scale_globals(data, multiplier):
    economy.xml(data, 'variables')
    text = data.decode('utf-8-sig')
    masked = _mask(text)
    report = {}
    edits = []
    for var in re.finditer(r'<var\b[^>]*>', masked):
        name, value = _attr(var.group(0), 'name'), _attr(var.group(0), 'value')
        if name is None or value is None:
            continue
        report[name] = value
        if name == 'RespawnTypes' and re.fullmatch(r'\d+', value):
            new = int(value) if int(value) >= RESPAWN_TYPES_CAP else min(RESPAWN_TYPES_CAP, math.ceil(int(value) * multiplier))
            found = re.search(r'\bvalue="\d+"', var.group(0))
            edits.append((var.start() + found.start(), var.start() + found.end(), 'value="%d"' % new))
            report['RespawnTypes'] = '%s->%d' % (value, new)
    return _encode(_apply(text, edits), data), report


# ------------------------------------------------------------------------------------------------ overlay


def _names(values, what):
    if not isinstance(values, list) or not values or len(values) > 8 or len(set(values)) != len(values):
        raise ValueError(f'{what} must be a short unique list')
    for value in values:
        if not isinstance(value, str) or not LABEL.fullmatch(value):
            raise ValueError(f'unsafe {what} name')
    return list(values)


def _added_categories(values):
    names = _names(values, 'category')
    if {str(v).lower() for v in names} & KEPT_CATEGORIES:
        raise ValueError('added loot spots never carry firearm or explosive categories')
    return names


def parse_policy(data):
    doc = json.loads(data)
    if not isinstance(doc, dict) or doc.get('schema') != 1 or doc.get('kind') != POLICY_KIND:
        raise ValueError('not a loot families policy')
    families = doc.get('families')
    if not isinstance(families, list) or not families:
        raise ValueError('policy needs families')
    rows = []
    for row in families:
        if not isinstance(row, dict) or not LABEL.fullmatch(str(row.get('family', ''))):
            raise ValueError('family needs a label')
        patterns = row.get('match')
        if not isinstance(patterns, list) or not patterns:
            raise ValueError('family needs match patterns')
        compiled = [re.compile(p) for p in patterns]
        kinds = {}
        for kind in CONTAINERS:
            if kind in row:
                spec = row[kind]
                kinds[kind] = {'categories': _added_categories(spec.get('categories')),
                               'tags': _names(spec.get('tags'), 'tag')}
        if 'floor' not in kinds:
            raise ValueError('family needs floor rules')
        rows.append({'family': row['family'], 'match': compiled, **kinds})
    return rows


def family_of(name, policy):
    for row in policy:
        if any(p.search(name) for p in row['match']):
            return row
    return None


def stock_floor(group):
    """Lowest y over a stock group's own loot points (its floor plane), or None when it has none."""
    ys = []
    for point in group.iter('point'):
        try:
            ys.append(float(point.get('pos').split()[1]))
        except (AttributeError, IndexError, ValueError):
            continue
    return min(ys) if ys else None


def group_pin(group):
    """Canonical digest of a stock group: every element, attribute and point, whitespace-insensitive."""
    shape = [(e.tag, sorted(e.attrib.items())) for e in group.iter()]
    return _sha(economy.encode(shape))


def _point(value):
    if (not isinstance(value, list) or len(value) != 3
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                   or abs(v) > MAX_COORDINATE for v in value)):
        raise ValueError('point must be three finite model-frame coordinates')
    return [round(float(v), 6) for v in value]


def added_lootmax(count):
    return max(1, min(MAX_ADDED_LOOTMAX, math.ceil(count / 3)))


def build_overlay(selection, stock_proto, policy_bytes, sources, skip=()):
    """Overlay bytes from per-class stock-frame points: {class: {'floor': [[x,y,z]..], 'surface': [..]}}."""
    policy = parse_policy(policy_bytes)
    root = economy.xml(stock_proto, 'prototype')
    stock = {}
    for group in root.iter('group'):
        stock.setdefault(group.get('name'), []).append(group)
    groups, total = {}, 0
    for name in sorted(selection):
        found = stock.get(name, [])
        family = family_of(name, policy)
        if len(found) != 1 or family is None or name in skip or found[0].get('lootmax') == '0':
            continue
        containers = {}
        floor = stock_floor(found[0])
        for kind, limit in (('floor', MAX_FLOOR_POINTS), ('surface', MAX_SURFACE_POINTS)):
            points = [_point(list(p)) for p in selection[name].get(kind, [])]
            points = [p for p in points if floor is None or p[1] >= floor - MAX_BELOW_STOCK_FLOOR][:limit]
            if points and kind in family:
                if total + len(points) > MAX_TOTAL_POINTS:
                    points = points[:MAX_TOTAL_POINTS - total]
                if not points:
                    continue
                total += len(points)
                containers[CONTAINERS[kind]] = {'lootmax': added_lootmax(len(points)),
                                                'categories': family[kind]['categories'],
                                                'tags': family[kind]['tags'], 'points': points}
        if containers:
            groups[name] = {'family': family['family'], 'stock_sha256': group_pin(found[0]),
                            'containers': containers}
    doc = {'schema': 1, 'kind': OVERLAY_KIND, 'frame': 'stock-mapgroupproto',
           'sources': dict(sources, stock_mapgroupproto_sha256=_sha(stock_proto)),
           'caps': {'floor_per_group': MAX_FLOOR_POINTS, 'surface_per_group': MAX_SURFACE_POINTS,
                    'total_points': MAX_TOTAL_POINTS, 'added_container_lootmax': MAX_ADDED_LOOTMAX,
                    'group_lootmax': MAX_GROUP_LOOTMAX},
           'groups': groups, 'runtime_acceptance': PENDING}
    return economy.encode(doc)


def parse_overlay(data):
    doc = json.loads(data)
    if (not isinstance(doc, dict) or doc.get('schema') != 1 or doc.get('kind') != OVERLAY_KIND
            or doc.get('runtime_acceptance') != PENDING or not isinstance(doc.get('groups'), dict)):
        raise ValueError('not a loot points overlay')
    total = 0
    for name, spec in doc['groups'].items():
        if not NAME.fullmatch(name) or not isinstance(spec, dict):
            raise ValueError('unsafe overlay group')
        if not re.fullmatch(r'[0-9a-f]{64}', str(spec.get('stock_sha256'))):
            raise ValueError('overlay group needs a stock pin')
        containers = spec.get('containers')
        if not isinstance(containers, dict) or not containers or not set(containers) <= set(CONTAINERS.values()):
            raise ValueError('overlay containers must be lootHCFloor/lootHCSurface')
        for cname, c in containers.items():
            limit = MAX_FLOOR_POINTS if cname == CONTAINERS['floor'] else MAX_SURFACE_POINTS
            if (not isinstance(c, dict) or set(c) != {'lootmax', 'categories', 'tags', 'points'}
                    or type(c['lootmax']) is not int or not 1 <= c['lootmax'] <= MAX_ADDED_LOOTMAX
                    or not isinstance(c['points'], list) or not 1 <= len(c['points']) <= limit):
                raise ValueError('overlay container shape or bounds')
            _added_categories(c['categories'])
            _names(c['tags'], 'tag')
            c['points'] = [_point(p) for p in c['points']]
            total += len(c['points'])
    if total > MAX_TOTAL_POINTS:
        raise ValueError('overlay exceeds the total point bound')
    return doc


# ------------------------------------------------------------------------------------------------ mapgroupproto


def _fmt(value):
    text = '%.6f' % value
    return '0.000000' if text == '-0.000000' else text


def _limits(mission):
    root = economy.xml(economy.read_plain(mission, LIMITS), 'lists')
    return ({c.get('name') for c in root.iter('category')}, {t.get('name') for t in root.iter('tag')})


def scale_proto(data, multiplier, overlay=None, limits=None):
    """Return (bytes, report) for mapgroupproto with lootmax scaled and overlay containers appended."""
    root = economy.xml(data, 'prototype')
    text = data.decode('utf-8-sig')
    masked = _mask(text)
    eol = '\r\n' if '\r\n' in text else '\n'
    edits, defaults = [], {}
    block = re.search(r'<defaults\b[^>]*>(.*?)</defaults>', masked, re.S)
    if block:
        for d in re.finditer(r'<default\b[^>]*>', masked[block.start():block.end()]):
            tag = d.group(0)
            name, value = _attr(tag, 'name'), _attr(tag, 'lootmax')
            if name in ('group', 'container') and value is not None and value.isdigit():
                defaults[name] = int(value)
                start = block.start() + d.start()
                edits.append((start, start + len(tag), _with_lootmax(tag, scaled(int(value), multiplier))))
    pins, floors = {}, {}
    for group in root.iter('group'):
        pins.setdefault(group.get('name'), []).append(group_pin(group))
        floors.setdefault(group.get('name'), []).append(stock_floor(group))
    wanted = (overlay or {}).get('groups', {})
    report = {'groups_scaled': 0, 'containers_kept': 0, 'groups_added': 0, 'points_added': 0,
              'stale': [], 'families': {}}
    applied = {}
    if wanted and limits is not None:
        categories, tags = limits
        for name, spec in wanted.items():
            if name not in pins:
                continue  # building absent from this mission: its names need not be declared
            for c in spec['containers'].values():
                missing = (set(c['categories']) - categories) | (set(c['tags']) - tags)
                if missing:
                    raise ValueError(f'overlay names absent from cfglimitsdefinition: {sorted(missing)}')
    for opening in re.finditer(r'<group\b[^>]*>', masked):
        tag = opening.group(0)
        if tag.endswith('/>'):
            continue
        close = masked.find('</group>', opening.end())
        if close < 0:
            raise ValueError('unclosed group')
        name = _attr(tag, 'name') or ''
        lootmax = _attr(tag, 'lootmax')
        if lootmax is not None and not lootmax.isdigit():
            raise ValueError(f'group {name} lootmax is not an integer')
        if lootmax == '0':
            continue
        body = masked[opening.end():close]
        first_container = None
        for cm in re.finditer(r'<container\b[^>]*>', body):
            ctag = cm.group(0)
            first_container = first_container or cm
            if ctag.endswith('/>'):
                continue
            cclose = body.find('</container>', cm.end())
            cats = {c.lower() for c in re.findall(r'<category\s+name="([^"]*)"', body[cm.end():cclose])}
            value = _attr(ctag, 'lootmax')
            start = opening.end() + cm.start()
            if cats & KEPT_CATEGORIES:  # any firearm/explosive container keeps its stock lootmax
                report['containers_kept'] += 1
                if value is None and 'container' in defaults:
                    edits.append((start, start + len(ctag), _with_lootmax(ctag, defaults['container'])))
            elif value is not None and value.isdigit():
                edits.append((start, start + len(ctag), _with_lootmax(ctag, scaled(int(value), multiplier))))
        group_scaled = scaled(int(lootmax), multiplier) if lootmax is not None else None
        added = 0
        spec = wanted.get(name)
        if spec is not None:
            if pins.get(name) != [spec['stock_sha256']]:
                report['stale'].append(name)
            else:
                floor = floors[name][0]
                for c in spec['containers'].values():
                    for p in c['points']:
                        if floor is not None and p[1] < floor - MAX_BELOW_STOCK_FLOOR:
                            raise ValueError(f'overlay point {p} of {name} is more than {MAX_BELOW_STOCK_FLOOR} m '
                                             f'below the stock floor plane {floor:.2f}')
                line_start = text.rfind('\n', 0, close) + 1
                if text[line_start:close].strip():
                    raise ValueError(f'group {name} end tag is not on its own line')
                closing_indent = text[line_start:close]
                unit = '\t' if '\t' in closing_indent or not closing_indent else ' ' * 4
                if first_container is not None:
                    cstart = opening.end() + first_container.start()
                    cindent = text[text.rfind('\n', 0, cstart) + 1:cstart]
                else:
                    cindent = closing_indent + unit
                kindent = cindent + unit
                lines = []
                for cname in (CONTAINERS['floor'], CONTAINERS['surface']):
                    if cname not in spec['containers']:
                        continue
                    c = spec['containers'][cname]
                    shape = POINT_SHAPE['floor' if cname == CONTAINERS['floor'] else 'surface']
                    lines.append('%s<container name="%s" lootmax="%d">' % (cindent, cname, c['lootmax']))
                    lines += ['%s<category name="%s" />' % (kindent, n) for n in c['categories']]
                    lines += ['%s<tag name="%s" />' % (kindent, n) for n in c['tags']]
                    lines += ['%s<point pos="%s" range="%s" height="%s" />'
                              % (kindent, ' '.join(_fmt(v) for v in p), shape[0], shape[1]) for p in c['points']]
                    lines.append('%s</container>' % cindent)
                    added += c['lootmax']
                    report['points_added'] += len(c['points'])
                    fam = report['families'].setdefault(spec['family'], {'groups': 0, 'points': 0})
                    fam['points'] += len(c['points'])
                report['families'][spec['family']]['groups'] += 1
                report['groups_added'] += 1
                edits.append((line_start, line_start, ''.join(line + eol for line in lines)))
                applied[name] = spec
        if added:
            base = group_scaled if group_scaled is not None else scaled(defaults.get('group', 0), multiplier)
            new = base + added
            if new > MAX_GROUP_LOOTMAX:
                new = max(base, MAX_GROUP_LOOTMAX)
            edits.append((opening.start(), opening.end(), _with_lootmax(tag, new)))
            report['groups_scaled'] += 1
        elif group_scaled is not None:
            edits.append((opening.start(), opening.end(), _with_lootmax(tag, group_scaled)))
            report['groups_scaled'] += 1
    output = _encode(_apply(text, edits), data)
    _verify_proto(data, output, applied)
    report['stale'].sort()
    return output, report


def _verify_proto(before, after, applied):
    old, new = economy.xml(before, 'prototype'), economy.xml(after, 'prototype')
    old_groups, new_groups = list(old.iter('group')), list(new.iter('group'))
    if [g.get('name') for g in old_groups] != [g.get('name') for g in new_groups]:
        raise ValueError('mapgroupproto verification failed: groups changed')
    drop = lambda e: sorted((k, v) for k, v in e.attrib.items() if k != 'lootmax')
    for a, b in zip(old_groups, new_groups):
        added = [c for c in b.findall('container') if c.get('name') in CONTAINERS.values()]
        kept = [c for c in b.findall('container') if c.get('name') not in CONTAINERS.values()]
        inside = {id(e) for x in added for e in x.iter()}
        if [(c.tag, drop(c)) for c in a.iter() if c is not a] != [
                (c.tag, drop(c)) for c in b.iter() if c is not b and id(c) not in inside]:
            raise ValueError(f'mapgroupproto verification failed: {a.get("name")} stock rows changed')
        spec = applied.get(a.get('name'))
        want = list(spec['containers']) if spec else []
        if [c.get('name') for c in added] != [n for n in CONTAINERS.values() if n in want]:
            raise ValueError(f'mapgroupproto verification failed: {a.get("name")} added containers')
        for c in added:
            points = [[float(v) for v in p.get('pos').split()] for p in c.findall('point')]
            if points != spec['containers'][c.get('name')]['points']:
                raise ValueError(f'mapgroupproto verification failed: {a.get("name")} points')
        if len(kept) != len(a.findall('container')):
            raise ValueError('mapgroupproto verification failed: container count')


# ------------------------------------------------------------------------------------------------ install


def _target(mission):
    mission = Path(mission).absolute()
    if mission.is_symlink() or not mission.is_dir():
        raise ValueError('mission must be an existing real directory')
    return mission


SHIPPED = object()  # floor_policy default: the committed floor-policy.json of this tree (None disables the policy)


def _floor_policy(floor_policy):
    """(parsed policy or None, digest or None). Enabled by default; ``enabled=false`` is the operator opt-out."""
    from tools.package import loot_floor_policy
    raw = loot_floor_policy.shipped_policy() if floor_policy is SHIPPED else floor_policy
    if raw is None:
        return None, None
    parsed = loot_floor_policy.parse_policy(raw)
    return (parsed if parsed['enabled'] else None), _sha(raw)


def plan(mission, multiplier=None, points=None, floor_policy=SHIPPED):
    """All edits computed in memory from the mission's current bytes; nothing written."""
    from tools.package import loot_floor_policy
    mission = _target(mission)
    multiplier = default_multiplier() if multiplier is None else _multiplier(multiplier)
    overlay = parse_overlay(points) if points is not None else None
    roster = _roster_names()
    policy, policy_sha = _floor_policy(floor_policy)
    outputs, counts, tag_rows = [], {'types': {}}, []
    for name in types_files(mission):
        before = economy.read_plain(mission, name)
        after, count = scale_types(before, multiplier, roster)
        counts['types'][name] = count
        if policy is not None:
            after, rows = loot_floor_policy.retag_types(after, policy, roster)
            tag_rows.append(rows)
        outputs.append((name, before, after))
    before = economy.read_plain(mission, GLOBALS)
    after, knobs = scale_globals(before, multiplier)
    counts['globals'] = knobs
    outputs.append((GLOBALS, before, after))
    proto_before = economy.read_plain(mission, PROTO)
    proto_after, report = scale_proto(proto_before, multiplier, overlay, _limits(mission) if overlay else None)
    counts['mapgroupproto'] = report
    if policy is not None:
        proto_after, floor = loot_floor_policy.rebalance_proto(proto_after, tag_rows, policy)
        floor['retagged_types'] = sum(1 for rows in tag_rows for r in rows if sorted(r[2]) != sorted(r[3]))
        floor['policy_sha256'] = policy_sha
    else:
        floor = {'enabled': False}
    counts['floor_policy'] = floor
    outputs.append((PROTO, proto_before, proto_after))
    files = [(n, b, a) for n, b, a in outputs if a != b]
    return {'multiplier': multiplier, 'points_sha256': _sha(points) if points is not None else None,
            'floor_policy_sha256': policy_sha, 'files': files, 'counts': counts, 'proto_before': _sha(proto_before)}


def _check_coverage_above(mission, proto_after_sha, proto_before_sha):
    """Refuse when ce_coverage was installed on top of our patched mapgroupproto (its rollback would break)."""
    folder = economy.child(mission, 'hollow-country-ce-coverage')
    if not os.path.lexists(folder) or proto_after_sha == proto_before_sha:
        return
    try:
        pinned = json.loads(economy.read_plain(folder, 'receipt.json'))['before']
    except (ValueError, OSError, KeyError, TypeError) as error:
        raise ValueError('CE coverage has no readable receipt; manual recovery needed, nothing was changed') from error
    if pinned == proto_after_sha:
        raise ValueError('CE coverage was installed on top of the loot boost; roll coverage back first')


def install(mission, multiplier=None, points=None, floor_policy=SHIPPED):
    mission = _target(mission)
    managed = economy.child(mission, MANAGED)
    if os.path.lexists(managed):
        raise ValueError('loot boost already installed or interrupted; rollback first (never applied twice)')
    result = plan(mission, multiplier, points, floor_policy)
    rows = []
    for index, (name, before, after) in enumerate(result['files']):
        rows.append({'name': name, 'before': _sha(before), 'after': _sha(after), 'backup': '%02d.backup' % index})
    receipt = {'schema': 1, 'kind': 'hollow-country-loot-boost', 'multiplier': result['multiplier'],
               'points_sha256': result['points_sha256'],
               'floor_policy_sha256': result['floor_policy_sha256'], 'files': rows, 'counts': result['counts'],
               'sources': {PROTO: result['proto_before']}, 'runtime_acceptance': PENDING}
    managed.mkdir()
    started = set()  # rows whose swap began; only these can hold this run's bytes
    try:
        economy.fresh_write(managed, 'receipt.json', economy.encode(receipt))
        for row, (_, before, _) in zip(rows, result['files']):
            economy.fresh_write(managed, row['backup'], before)
        for path in managed.iterdir():
            _sync_file(path)  # barrier: recovery data is durable before any switch
        _sync_dir(managed)
        _sync_dir(mission)
        _check_unchanged(mission, rows)  # barrier: nothing moved between planning and the first swap
        for row, (name, _, after) in zip(rows, result['files']):
            _check_unchanged(mission, [row])  # re-hash right before this file's swap
            started.add(row['name'])
            _switch(mission, managed, name, after, row['backup'].replace('.backup', '.next'), row['before'])
    except BaseException as error:
        _undo_install(mission, managed, rows, error, started)
        raise
    return receipt


def _check_unchanged(mission, rows):
    for row in rows:
        if _sha(economy.read_plain(mission, row['name'])) != row['before']:
            raise ValueError(f'{row["name"]} changed since planning; refusing to overwrite it')


def _undo_install(mission, managed, rows, error, started=None):
    """Put back the files this install switched (verified against their pre-boost hashes), then drop the managed dir.

    Files that are not in the state this install left them (an operator edit) are never overwritten; in that case
    the recovery data stays in place and the failure names it.
    """
    try:
        drifted = []
        for row in rows:  # a swap that raised after os.replace must be undone too
            current = _sha(economy.read_plain(mission, row['name']))
            if row['after'] == row['before'] or current == row['before']:
                continue  # never switched by this run
            if started is not None and row['name'] not in started:
                continue  # edited before this run reached it: not ours, never overwritten
            if current != row['after']:
                drifted.append(row['name'])  # an edit that is not ours: never overwritten
                continue
            backup = economy.read_plain(managed, row['backup'])
            if _sha(backup) != row['before']:
                raise ValueError(f'backup of {row["name"]} drifted')
            _switch(mission, managed, row['name'], backup, row['backup'].replace('.backup', '.next'), row['after'])
            if _sha(economy.read_plain(mission, row['name'])) != row['before']:
                raise ValueError(f'{row["name"]} did not verify after restore')
        if drifted:
            raise ValueError('changed since this install switched them: ' + ', '.join(drifted))
        _check_unchanged(mission, [r for r in rows if started is None or r['name'] in started])
        shutil.rmtree(managed)
    except (OSError, ValueError) as undo_error:
        error.add_note('loot boost automatic undo failed (%s); recovery data kept in %s, run rollback after '
                       'reconciling' % (undo_error, MANAGED))


def _sync_file(path):
    """fsync a file. Windows maps fsync to _commit, which needs a writable handle (#142)."""
    mode = os.O_RDWR if os.name == 'nt' else os.O_RDONLY
    fd = os.open(path, mode | getattr(os, 'O_NOFOLLOW', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _sync_dir(path):
    """fsync a directory entry table. Windows cannot open a directory this way; skip it there."""
    if os.name == 'nt':
        return
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _switch(mission, managed, name, data, staged_name, expected_sha):
    """Stage, rehash just before replacement, and verify readback; not a multi-file atomic swap.

    The server must be stopped. These checks detect drift at the barriers; they cannot lock out
    another writer in the interval between the final hash and os.replace.
    """
    live = economy.plain_file(mission, economy.child(mission, name))
    staged = economy.fresh_write(managed, staged_name, data)
    os.chmod(staged, os.lstat(live).st_mode & 0o777)
    _sync_file(staged)
    if _sha(economy.read_plain(managed, staged_name)) != _sha(data):
        raise ValueError(f'staged replacement of {name} drifted; recovery data kept')
    if _sha(economy.read_plain(mission, name)) != expected_sha:
        raise ValueError(f'{name} changed before staged swap; refusing to overwrite it')
    os.replace(staged, live)
    _sync_dir(live.parent)
    if _sha(economy.read_plain(mission, name)) != _sha(data):
        raise ValueError(f'{name} did not verify after swap; recovery data kept')


def _receipt(managed):
    try:
        receipt = json.loads(economy.read_plain(managed, 'receipt.json'))
    except (ValueError, OSError):
        return None
    if (not isinstance(receipt, dict) or receipt.get('schema') != 1 or receipt.get('kind') != 'hollow-country-loot-boost'
            or receipt.get('runtime_acceptance') != PENDING or not isinstance(receipt.get('files'), list)):
        return None
    for row in receipt['files']:
        if (not isinstance(row, dict) or set(row) != {'name', 'before', 'after', 'backup'}
                or not all(isinstance(row[k], str) for k in row)
                or not re.fullmatch(r'[0-9]{2}\.backup', row['backup'])):
            return None
        economy.child(managed.parent, row['name'])
    return receipt


def _preflight(managed):
    if managed.is_symlink() or not managed.is_dir():
        raise ValueError('managed path is a symlink or not a directory')
    for path in managed.iterdir():
        if path.is_dir() or not MANAGED_FILE.fullmatch(path.name):
            raise ValueError('unexpected managed entry; rollback refuses deletion')
        economy.plain_file(managed, path)


def rollback(mission):
    mission = _target(mission)
    managed = economy.child(mission, MANAGED)
    if not os.path.lexists(managed):
        raise ValueError('nothing to roll back: no loot boost installation')
    _preflight(managed)
    present = {p.name for p in managed.iterdir()}
    receipt = _receipt(managed) if 'receipt.json' in present else None
    if receipt is None:
        if any(n.endswith('.backup') for n in present):
            raise ValueError('loot boost backups exist without a valid receipt; manual recovery needed')
        shutil.rmtree(managed)  # receipt is written first: nothing in the mission was touched
        return {'restored': 0}
    restore = []
    for row in receipt['files']:
        current = _sha(economy.read_plain(mission, row['name']))
        if current == row['after'] and row['after'] != row['before']:
            if row['backup'] not in present or _sha(economy.read_plain(managed, row['backup'])) != row['before']:
                raise ValueError(f'loot boost backup missing or drifted for {row["name"]}; manual recovery needed')
            restore.append(row)
        elif current != row['before']:
            raise ValueError(f'{row["name"]} drifted since the loot boost; manual reconciliation required')
    proto = [r for r in receipt['files'] if r['name'] == PROTO]
    if proto:
        _check_coverage_above(mission, proto[0]['after'], proto[0]['before'])
    for row in restore:
        backup = economy.read_plain(managed, row['backup'])
        if _sha(backup) != row['before']:
            raise ValueError(f'loot boost backup drifted for {row["name"]}; recovery data kept')
        _switch(mission, managed, row['name'], backup, row['backup'].replace('.backup', '.next'), row['after'])
    _check_unchanged(mission, receipt['files'])  # keep recovery data if an earlier restore drifted
    shutil.rmtree(managed)
    return {'restored': len(restore)}


def installed_before(mission):
    """{relative name: pre-boost bytes} for files the boost currently holds; {} when not installed."""
    managed = economy.child(Path(mission).absolute(), MANAGED)
    if not os.path.lexists(managed):
        return {}
    _preflight(managed)
    receipt = _receipt(managed)
    if receipt is None:
        raise ValueError('loot boost receipt unreadable; roll back before exporting')
    out = {}
    for row in receipt['files']:
        current = _sha(economy.read_plain(mission, row['name']))
        if current == row['after']:
            data = economy.read_plain(managed, row['backup'])
            if _sha(data) != row['before']:
                raise ValueError('loot boost backup drifted; roll back before exporting')
            out[row['name']] = data
        elif current != row['before']:
            raise ValueError(f'{row["name"]} drifted since the loot boost; roll back before exporting')
    return out


def rollback_inputs(mission):
    """Mission files a trial rollback must copy (those named in the receipt)."""
    managed = economy.child(Path(mission).absolute(), MANAGED)
    if not os.path.lexists(managed):
        return []
    receipt = _receipt(managed)
    return [row['name'] for row in receipt['files']] if receipt else []


def describe(result):
    counts = result['counts']
    lines = ['loot boost multiplier=%s (firearms/ammo/explosives/vehicle parts unchanged)' % result['multiplier']]
    for name, count in counts['types'].items():
        lines.append('  types %s scaled_rows=%d' % (name, count))
    knobs = counts['globals']
    lines.append('  globals RespawnTypes=%s InitialSpawn=%s RespawnLimit=%s RespawnAttempt=%s'
                 % tuple(knobs.get(k, '?') for k in ('RespawnTypes', 'InitialSpawn', 'RespawnLimit', 'RespawnAttempt')))
    proto = counts['mapgroupproto']
    lines.append('  mapgroupproto groups_scaled=%d weapons_containers_kept=%d contextual_groups=%d points=%d stale=%d'
                 % (proto['groups_scaled'], proto['containers_kept'], proto['groups_added'], proto['points_added'],
                    len(proto['stale'])))
    for family, row in sorted(proto['families'].items()):
        lines.append('    family %s groups=%d points=%d' % (family, row['groups'], row['points']))
    from tools.package import loot_floor_policy
    lines.append('  ' + loot_floor_policy.describe(counts.get('floor_policy', {'enabled': False})))
    lines.append('  runtime acceptance pending: ' + ADVISORY)
    return lines


# ------------------------------------------------------------------------------------------------ point selection


def _key(x, z, step):
    return (int(round(x / step)), int(round(z / step)))


def _walkable(hits, codes):
    cells = []
    for index, hit in enumerate(hits):
        if len(hit) < 4 or hit[3] < MIN_CLEARANCE:
            continue
        cells.append((float(hit[0]), float(hit[1]), float(hit[2]), codes[index] if index < len(codes) else -1))
    return cells


def _component(cells, stock, step):
    """Cells connected (4-neighbour, |dy| <= WALK_STEP) to a native-reached cell or a stock loot point."""
    columns = {}
    for cell in cells:
        columns.setdefault(_key(cell[0], cell[2], step), []).append(cell)
    seeds = [c for c in cells if c[3] == 1 or any(
        abs(c[0] - s[0]) <= STOCK_CLEAR and abs(c[2] - s[2]) <= STOCK_CLEAR and abs(c[1] - s[1]) <= STOCK_BAND
        for s in stock)]
    seen, queue = set(seeds), list(seeds)
    while queue:
        cell = queue.pop()
        kx, kz = _key(cell[0], cell[2], step)
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for other in columns.get((kx + dx, kz + dz), ()):
                if other not in seen and abs(other[1] - cell[1]) <= WALK_STEP:
                    seen.add(other)
                    queue.append(other)
    return seen, columns


def _spread(candidates, avoid, spacing, limit):
    """Deterministic farthest-point selection: spread new spots away from stock ones and each other."""
    chosen = []
    dist = lambda a, b: math.sqrt((a[0] - b[0]) ** 2 + (a[2] - b[2]) ** 2 + (2.0 * (a[1] - b[1])) ** 2)
    pool = sorted(candidates)
    while pool and len(chosen) < limit:
        anchors = chosen + list(avoid)
        scored = [(min((dist(p, a) for a in anchors), default=1e9), p) for p in pool]
        best = max(scored, key=lambda s: (s[0], tuple(-v for v in s[1])))
        if best[0] < spacing:
            break
        chosen.append(best[1])
        pool = [p for p in pool if dist(p, best[1]) >= spacing]
    return chosen


def floor_points(hits, codes, stock, doors, step=1.0, limit=MAX_FLOOR_POINTS):
    """Wall-side, reachable, roofed floor cells away from stock points, doors and stair edges (sampler frame)."""
    cells = _walkable(hits, codes)
    component, columns = _component(cells, stock, step)
    candidates, interior = [], []
    for cell in component:
        kx, kz = _key(cell[0], cell[2], step)
        wall = stair = False
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            near = columns.get((kx + dx, kz + dz), ())
            if not any(abs(o[1] - cell[1]) <= WALK_STEP for o in near):
                wall = True
            if any(WALK_STEP < abs(o[1] - cell[1]) <= STAIR_RISE for o in near):
                stair = True
        if stair:
            continue
        if any(math.hypot(cell[0] - s[0], cell[2] - s[2]) <= STOCK_CLEAR + 1e-9 and abs(cell[1] - s[1]) <= STOCK_BAND
               for s in stock):
            continue
        if any(abs(cell[0] - d[0]) <= DOOR_CLEAR and abs(cell[2] - d[2]) <= DOOR_CLEAR and abs(cell[1] - d[1]) <= 2.5
               for d in doors):
            continue
        (candidates if wall else interior).append(cell[:3])
    limit = min(limit, max(2, len(component) // CELLS_PER_POINT))
    chosen = _spread(candidates, [tuple(s) for s in stock], FLOOR_SPACING, limit)
    if len(chosen) < 2:  # tiny rooms: fall back to open floor rather than leave the building unchanged
        chosen += _spread(interior, [tuple(s) for s in stock] + chosen, FLOOR_SPACING, 2 - len(chosen))
    return chosen


def surface_points(view_hits, hits, codes, stock, step=1.0, limit=MAX_SURFACE_POINTS):
    """Raised surfaces (tables, counters, shelves) from a view-geometry census over reachable floor columns."""
    component, _ = _component(_walkable(hits, codes), stock, step)
    floors = {}
    for cell in component:
        floors.setdefault(_key(cell[0], cell[2], step), []).append(cell[1])
    candidates = []
    for hit in view_hits:
        if len(hit) < 4 or hit[3] < SURFACE_CLEARANCE:
            continue
        x, y, z = float(hit[0]), float(hit[1]), float(hit[2])
        below = floors.get(_key(x, z, step), ())
        if not any(SURFACE_RISE[0] <= y - f <= SURFACE_RISE[1] for f in below):
            continue
        if any(math.hypot(x - s[0], z - s[2]) <= SURFACE_SPACING and abs(y - s[1]) <= STOCK_BAND for s in stock):
            continue
        candidates.append((x, y, z))
    return _spread(candidates, [tuple(s) for s in stock], SURFACE_SPACING, limit)


def select_from_censuses(geom_docs, view_docs, stock_proto, skip=()):
    """{class: {'floor': [...], 'surface': [...]}} in the stock frame, best usable placement per class."""
    from tools.audit import interior_points as pts
    from tools.package import interior_templates as it
    proto = it.parse_proto(stock_proto)
    best, views = {}, {}
    for doc in geom_docs:
        for row in doc['placements']:
            if pts._usable(row) and (row['class'] not in best or len(row['hits']) > len(best[row['class']]['hits'])):
                best[row['class']] = row
    for doc in view_docs:
        for row in doc['placements']:
            if pts._usable(row) and (row['class'] not in views or len(row['hits']) > len(views[row['class']]['hits'])):
                views[row['class']] = row
    selection = {}
    for name, row in sorted(best.items()):
        group = proto.get(name)
        if group is None or name in skip:
            continue
        stock = [pts.stock_to_sampler(p[:3], 'rot90') for c in group['containers'] for p in c['points']]
        codes = row.get('open_codes') or [-1] * len(row['hits'])
        doors = [tuple(d[:3]) for d in (row.get('door_run') or {}).get('doors', []) if isinstance(d, list)]
        step = float(row.get('grid', {}).get('step', 1.0))
        floor = floor_points(row['hits'], codes, stock, doors, step)
        surface = []
        if name in views:
            surface = surface_points(views[name]['hits'], row['hits'], codes, stock, step)
        to_stock = lambda ps: [list(pts.sampler_to_stock(p, 'rot90')) for p in ps]
        if floor or surface:
            selection[name] = {'floor': to_stock(floor), 'surface': to_stock(surface)}
    return selection


def _load_censuses(paths, log):
    from tools.audit import interior_points as pts
    docs, sources = [], []
    for path in paths:
        data = Path(path).read_bytes()
        try:
            docs.append(pts.parse_census(data))
        except ValueError as error:
            log('skip census sha256=%s: %s' % (_sha(data)[:12], str(error)[:80]))
            continue
        sources.append(_sha(data))
    return docs, sources


# ------------------------------------------------------------------------------------------------ CLI


def main(argv=None):
    parser = argparse.ArgumentParser(prog='loot_boost.py', description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('points', help='generate the contextual points overlay from native censuses')
    p.add_argument('--census', nargs='+', required=True, help='geom census.json files')
    p.add_argument('--view-census', nargs='*', default=[], help='--intersect view census.json files (surfaces)')
    p.add_argument('--stock-proto', required=True, help="the operator's stock mapgroupproto.xml (read only)")
    p.add_argument('--out', default=str(REPO_ROOT / ADDITIONS))
    for name in ('plan', 'install'):
        q = sub.add_parser(name)
        q.add_argument('--mission', required=True)
        q.add_argument('--multiplier', type=float)
        q.add_argument('--points', default='shipped', help='overlay JSON path, "shipped" (default) or "none"')
    r = sub.add_parser('rollback')
    r.add_argument('--mission', required=True)
    sub.add_parser('validate')
    args = parser.parse_args(argv)
    try:
        if args.command == 'points':
            from tools.package import ce_coverage
            geom, geom_sources = _load_censuses(args.census, print)
            view, view_sources = _load_censuses(args.view_census, print)
            stock = Path(args.stock_proto).read_bytes()
            selection = select_from_censuses(geom, view, stock, skip=ce_coverage.TARGET_GROUPS)
            data = build_overlay(selection, stock, (REPO_ROOT / FAMILIES).read_bytes(),
                                 {'geom_census_sha256': sorted(geom_sources),
                                  'view_census_sha256': sorted(view_sources), 'sampler_frame': 'rot90'},
                                 skip=ce_coverage.TARGET_GROUPS)
            overlay = parse_overlay(data)
            Path(args.out).write_bytes(data)
            families = {}
            for spec in overlay['groups'].values():
                row = families.setdefault(spec['family'], [0, 0, 0])
                row[0] += 1
                row[1] += len(spec['containers'].get(CONTAINERS['floor'], {}).get('points', []))
                row[2] += len(spec['containers'].get(CONTAINERS['surface'], {}).get('points', []))
            print('loot points groups=%d sha256=%s' % (len(overlay['groups']), _sha(data)))
            for family, (g, f, s) in sorted(families.items()):
                print('  family %s groups=%d floor_points=%d surface_points=%d' % (family, g, f, s))
            return 0
        if args.command == 'validate':
            multiplier = default_multiplier()
            data = shipped_points()
            overlay = parse_overlay(data) if data is not None else None
            parse_policy((REPO_ROOT / FAMILIES).read_bytes())
            print('loot boost multiplier=%s overlay_groups=%s runtime_acceptance=pending'
                  % (multiplier, len(overlay['groups']) if overlay else 'absent'))
            return 0
        if args.command == 'rollback':
            print('loot boost rolled back restored=%d' % rollback(args.mission)['restored'])
            return 0
        points = (shipped_points() if args.points == 'shipped' else None if args.points == 'none'
                  else Path(args.points).read_bytes())
        if args.command == 'plan':
            for line in describe(plan(args.mission, args.multiplier, points)):
                print(line)
            return 0
        receipt = install(args.mission, args.multiplier, points)
        for line in describe({'multiplier': receipt['multiplier'], 'counts': receipt['counts']}):
            print(line)
        print('loot boost installed files=%d receipt=%s/receipt.json' % (len(receipt['files']), MANAGED))
        return 0
    except (OSError, ValueError) as error:
        print('loot_boost: %s' % error, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
