"""Map overlay layers: authored object layers added to a stock Chernarus+ mission, with CE loot rows.

A layer is a reviewable JSON file under config/map-overlays/layers/. This tool validates the
enabled layers and composes them into the two things the engine and the Central Economy read, with no
terrain change and no client mod:

  * objectSpawnersArr spawner files (native 1.30 ObjectSpawner, schema read from the installed scripts,
    3_Game/ObjectSpawner.c: {"Objects": [{name, pos[3], ypr[3], scale, enableCEPersistency, customString}]});
  * mapgrouppos.xml rows (<group name pos rpy a/>) for every object whose loot intent is "proto", because the
    CE places loot from mapgrouppos rows joined to mapgroupproto groups, not from the objects themselves.

Install patches exactly two files of a stopped, private mission copy in place (cfggameplay.json's
objectSpawnersArr and mapgrouppos.xml), keeps byte-exact backups plus a hash receipt in
hollow-country-overlays/, and rolls back byte-for-byte. It never edits serverDZ.cfg; the server still needs
enableCfgGameplayFile = 1. Offline validation never establishes DayZ behavior: spawning, floating or clipping
and CE loot on the added objects stay pending native testing (every layer carries status runtime-unverified).
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import struct
import xml.etree.ElementTree as ET
import zlib

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.package import economy

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'config/map-overlays'
MANAGED = 'hollow-country-overlays'
INPUTS = ('cfggameplay.json', 'mapgrouppos.xml')
GAMEPLAY = 'cfggameplay.json'
POS = 'mapgrouppos.xml'
PROFILE_KIND = 'hollow-country-overlay-profile'
CLASSES_KIND = 'hollow-country-overlay-classes'
COMPOSITIONS_KIND = 'hollow-country-overlay-compositions'
LAYER_KIND = 'hollow-country-map-overlay'
MANIFEST_KIND = 'hollow-country-overlay-manifest'
STATUSES = ('runtime-unverified', 'runtime-verified')
LOOT = ('proto', 'none')
LAYER_ID = re.compile(r'[a-z][a-z0-9-]{0,47}')
OBJECT_ID = re.compile(r'[a-z0-9][a-z0-9_-]{0,31}')
SITE_ID = re.compile(r'[a-z0-9][a-z0-9_]{0,23}')
COMPOSITION_ID = re.compile(r'[a-z][a-z0-9-]{0,47}')
CLASS_NAME = re.compile(r'[A-Za-z0-9_]{1,80}')
HEX64 = re.compile(r'[0-9a-f]{64}')
MAX_XML = 64 * 1024 * 1024
Y_RANGE = (-50.0, 800.0)
DEFAULT_LIMITS = {'map_size': 15360, 'max_objects_total': 200, 'max_objects_per_layer': 48,
                  'min_spacing_m': 6.0, 'vanilla_clearance_m': 8.0,
                  # composition sites: pieces of one site may stand close (sandbags, barriers); every piece keeps
                  # its own clearance from vanilla groups and needs flat vanilla height support around it.
                  'piece_spacing_m': 1.0, 'piece_vanilla_clearance_m': 10.0, 'flat_radius_m': 60.0,
                  'flat_spread_m': 1.2, 'flat_min_rows': 3, 'flat_site_tolerance_m': 0.8,
                  'max_loot_total': 200, 'max_loot_per_layer': 48}
# Site selection rule constants (see suggest_sites and the layer's basis.rule).
CLUSTER_LINK_M = 250.0
MIN_CLUSTER_GROUPS = 6
MAX_TENT_SHARE = 0.25
SITE_CLEARANCE_M = 12.0
SITE_PAIR_M = 15.0
SITE_MAX_FROM_CENTRE_M = 100.0
SITE_FLAT_RADIUS_M = 60.0
SITE_FLAT_SPREAD_M = 1.2
SITE_MIN_NEIGHBOURS = 3
SITE_RADII = (20.0, 28.0)
SITE_BEARINGS = tuple(range(0, 360, 45))
SITE_CLASSES = tuple('Land_Mil_Tent_Big1_%d' % n for n in range(1, 6))
MILITARY_PREFIXES = ('Land_Mil_', 'Land_Tisy_', 'Land_Medical_Tent')


class Source:
    """The authored inputs: profile (enabled layers and limits), class allowlist, layers, compositions."""

    def __init__(self, profile, classes, layers, compositions=None):
        self.profile, self.classes, self.layers = profile, classes, list(layers)
        self.compositions = compositions if compositions is not None else {
            'kind': COMPOSITIONS_KIND, 'compositions': {}}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def finite(value):
    return number(value) and math.isfinite(value)


def wrap(angle):
    """Degrees into (-180, 180]."""
    angle = math.fmod(angle, 360.0)
    if angle <= -180.0:
        angle += 360.0
    elif angle > 180.0:
        angle -= 360.0
    return angle + 0.0


def fmt(value):
    return '%.6f' % (value + 0.0)


def limits_of(profile):
    merged = dict(DEFAULT_LIMITS)
    merged.update(profile.get('limits') or {})
    return merged


def load_source(directory=SOURCE):
    directory = Path(directory)

    def read(path):
        return json.loads(path.read_bytes())
    layers = [read(path) for path in sorted((directory / 'layers').glob('*.json'))]
    compositions = read(directory / 'compositions.json') if (directory / 'compositions.json').is_file() else None
    return Source(read(directory / 'profile.json'), read(directory / 'classes.json'), layers, compositions)


# ---- validation ---------------------------------------------------------------------------------------------

def _validate_profile(source, errors):
    profile, classes = source.profile, source.classes
    if not isinstance(profile, dict) or profile.get('kind') != PROFILE_KIND:
        errors.append('profile: kind must be %s' % PROFILE_KIND)
        return False
    if not isinstance(profile.get('enabled'), list) or not all(isinstance(i, str) for i in profile['enabled']):
        errors.append('profile: enabled must be a list of layer ids')
    elif len(set(profile['enabled'])) != len(profile['enabled']):
        errors.append('profile: enabled lists a layer id twice')
    for key, value in (profile.get('limits') or {}).items():
        if key not in DEFAULT_LIMITS or not finite(value) or value <= 0:
            errors.append('profile: limit %s is unknown or not a positive number' % key)
    if not isinstance(classes, dict) or classes.get('kind') != CLASSES_KIND or not isinstance(
            classes.get('classes'), dict) or not isinstance(classes.get('provenance'), dict):
        errors.append('classes: kind %s with a classes map and provenance is required' % CLASSES_KIND)
        return False
    return not errors


def _validate_object(layer_id, item, source, limits, errors):
    where = '%s/%s' % (layer_id, item.get('id') if isinstance(item, dict) else '?')
    if not isinstance(item, dict):
        errors.append('%s: object must be a mapping' % where)
        return None
    if not isinstance(item.get('id'), str) or not OBJECT_ID.fullmatch(item['id']):
        errors.append('%s: object id must match %s' % (where, OBJECT_ID.pattern))
    cls = item.get('class')
    if not isinstance(cls, str) or not CLASS_NAME.fullmatch(cls) or cls not in source.classes['classes']:
        errors.append('%s: class %r is not in the class allowlist' % (where, cls))
    pos = item.get('pos')
    good = isinstance(pos, list) and len(pos) == 3 and all(finite(v) for v in pos)
    if not good:
        errors.append('%s: pos must be [x, y, z] of finite numbers' % where)
    else:
        size = limits['map_size']
        if not (0.0 <= pos[0] <= size and 0.0 <= pos[2] <= size) or not (Y_RANGE[0] <= pos[1] <= Y_RANGE[1]):
            errors.append('%s: pos %s is outside the map bounds (0..%s, y %s..%s)' % (
                where, pos, size, Y_RANGE[0], Y_RANGE[1]))
    if not finite(item.get('yaw')):
        errors.append('%s: yaw must be a finite number of degrees' % where)
    if item.get('loot') not in LOOT:
        errors.append('%s: loot must be one of %s' % (where, ', '.join(LOOT)))
    return pos if good else None


def _finite_list(value, count):
    return isinstance(value, list) and len(value) == count and all(finite(v) for v in value)


def piece_world(piece, cx, cz, heading):
    """World x, z of a composition piece. heading is a compass angle in degrees (0 = north = +z, 90 = east =
    +x); the piece offset dx runs to the right of the heading and dz forward along it."""
    angle = math.radians(heading)
    s, c = math.sin(angle), math.cos(angle)
    dx, dz = float(piece['dx']), float(piece['dz'])
    return round(cx + dx * c + dz * s, 6), round(cz - dx * s + dz * c, 6)


def _piece_ok(piece):
    return isinstance(piece, dict) and isinstance(piece.get('class'), str) and isinstance(piece.get('loot'), str) \
        and all(finite(piece.get(k)) for k in ('dx', 'dz', 'yaw')) and (
            'dy' not in piece or finite(piece['dy']))


def expand_layer(source, layer):
    """The layer's explicit objects plus every composition site expanded to one object per piece.

    Piece ids are '<site>-pNN' in composition order; each piece carries its site id. The composition frame is
    rotated by the site heading (compass degrees). The piece yaw is the composition yaw plus the heading, with the
    same compass sense; that the engine yaw uses it too is an assumption pending native testing."""
    objects = [dict(item) if isinstance(item, dict) else item for item in layer.get('objects') or []]
    comps = (source.compositions or {}).get('compositions')
    comps = comps if isinstance(comps, dict) else {}
    for site in layer.get('sites') or []:
        if not isinstance(site, dict) or not isinstance(site.get('id'), str):
            continue
        comp = comps.get(site.get('composition'))
        pos, heading = site.get('pos'), site.get('heading')
        if not isinstance(comp, dict) or not isinstance(comp.get('pieces'), list) or not _finite_list(pos, 3) \
                or not finite(heading):
            continue
        for n, piece in enumerate(comp['pieces'], 1):
            if not _piece_ok(piece):
                continue
            x, z = piece_world(piece, pos[0], pos[2], heading)
            objects.append({'id': '%s-p%02d' % (site['id'], n), 'class': piece['class'],
                            'pos': [x, round(float(pos[1]) + float(piece.get('dy', 0.0)), 6), z],
                            'yaw': wrap(float(piece['yaw']) + float(heading)), 'loot': piece['loot'],
                            'area': site.get('area', ''), 'site': site['id']})
    return objects


def _validate_compositions(source, limits, errors):
    block = source.compositions
    if not isinstance(block, dict) or block.get('kind') != COMPOSITIONS_KIND or not isinstance(
            block.get('compositions'), dict):
        errors.append('compositions: kind %s with a compositions map is required' % COMPOSITIONS_KIND)
        return
    classes = source.classes['classes']
    for name, comp in sorted(block['compositions'].items()):
        where = 'composition %s' % name
        if not COMPOSITION_ID.fullmatch(name) or not isinstance(comp, dict):
            errors.append('%s: the name must match %s and hold a mapping' % (where, COMPOSITION_ID.pattern))
            continue
        for key in ('theme', 'purpose'):
            if not isinstance(comp.get(key), str) or not comp[key].strip():
                errors.append('%s: %s must be a non-empty string' % (where, key))
        pieces = comp.get('pieces')
        if not isinstance(pieces, list) or not pieces or len(pieces) > 32:
            errors.append('%s: pieces must be a list of 1 to 32 pieces' % where)
            continue
        boxes = comp.get('clear', [])
        good_boxes = []
        for box in boxes if isinstance(boxes, list) else [None]:
            if isinstance(box, dict) and _finite_list(box.get('x'), 2) and _finite_list(box.get('z'), 2) \
                    and box['x'][0] <= box['x'][1] and box['z'][0] <= box['z'][1]:
                good_boxes.append(box)
            else:
                errors.append('%s: clear must be a list of {x: [min, max], z: [min, max]} boxes' % where)
        good = []
        for n, piece in enumerate(pieces, 1):
            if not _piece_ok(piece):
                errors.append('%s piece %d: class, dx, dz, yaw (finite), loot are required' % (where, n))
                continue
            info = classes.get(piece['class'])
            if not CLASS_NAME.fullmatch(piece['class']) or not isinstance(info, dict):
                errors.append('%s piece %d: class %r is not in the class allowlist' % (where, n, piece['class']))
            elif piece['loot'] == 'proto' and info.get('loot_group') is False:
                errors.append('%s piece %d: loot proto but %s has no loot group (mapgroupproto) in the allowlist' % (
                    where, n, piece['class']))
            if piece['loot'] not in LOOT:
                errors.append('%s piece %d: loot must be one of %s' % (where, n, ', '.join(LOOT)))
            for box in good_boxes:
                if box['x'][0] <= piece['dx'] <= box['x'][1] and box['z'][0] <= piece['dz'] <= box['z'][1]:
                    errors.append('%s piece %d: %s stands in the clear lane (the entrance must stay open)' % (
                        where, n, piece['class']))
            good.append((n, piece))
        for i, (na, a) in enumerate(good):
            for nb, b in good[i + 1:]:
                gap = math.hypot(a['dx'] - b['dx'], a['dz'] - b['dz'])
                if gap == 0.0:
                    errors.append('%s: duplicate position of pieces %d and %d' % (where, na, nb))
                elif gap < limits['piece_spacing_m']:
                    errors.append('%s: spacing of pieces %d and %d is %.1f m (minimum %.1f m)' % (
                        where, na, nb, gap, limits['piece_spacing_m']))


def _validate_site(layer_id, site, source, limits, seen, errors):
    where = '%s/%s' % (layer_id, site.get('id') if isinstance(site, dict) else '?')
    if not isinstance(site, dict):
        errors.append('%s: site must be a mapping' % where)
        return
    if not isinstance(site.get('id'), str) or not SITE_ID.fullmatch(site['id']):
        errors.append('%s: site id must match %s' % (where, SITE_ID.pattern))
    elif site['id'] in seen:
        errors.append('%s: site id %s is used twice' % (layer_id, site['id']))
    else:
        seen.add(site['id'])
    comps = (source.compositions or {}).get('compositions')
    if not isinstance(comps, dict) or site.get('composition') not in comps:
        errors.append('%s: composition %r is not defined' % (where, site.get('composition')))
    if not _finite_list(site.get('pos'), 3):
        errors.append('%s: pos must be [x, y, z] of finite numbers' % where)
    if not finite(site.get('heading')):
        errors.append('%s: heading must be a finite compass angle in degrees' % where)


def validate(source, vanilla=None, proto_names=None):
    """Every problem as a list of strings (empty means valid). vanilla = [(class, x, y, z)], proto_names = set."""
    errors = []
    if not _validate_profile(source, errors):
        return errors
    limits = limits_of(source.profile)
    _validate_compositions(source, limits, errors)
    vanilla_grid = Grid(vanilla) if vanilla is not None else None
    seen_layers, placed, total, loot_total = set(), [], 0, 0
    for layer in source.layers:
        if not isinstance(layer, dict):
            errors.append('layer: must be a mapping')
            continue
        layer_id = layer.get('id')
        name = layer_id if isinstance(layer_id, str) else '?'
        if layer.get('kind') != LAYER_KIND:
            errors.append('%s: kind must be %s' % (name, LAYER_KIND))
        if not isinstance(layer_id, str) or not LAYER_ID.fullmatch(layer_id):
            errors.append('layer id %r must match %s' % (layer_id, LAYER_ID.pattern))
        elif layer_id in seen_layers:
            errors.append('layer id %s is used twice' % layer_id)
        seen_layers.add(layer_id)
        if not isinstance(layer.get('version'), int) or isinstance(layer.get('version'), bool) or layer['version'] < 1:
            errors.append('%s: version must be an integer >= 1' % name)
        if not isinstance(layer.get('purpose'), str) or not layer['purpose'].strip():
            errors.append('%s: purpose must be a non-empty string' % name)
        if layer.get('status') not in STATUSES:
            errors.append('%s: status must be one of %s' % (name, ', '.join(STATUSES)))
        objects, sites = layer.get('objects'), layer.get('sites', [])
        if not isinstance(objects, list):
            errors.append('%s: objects must be a list' % name)
            continue
        if not isinstance(sites, list):
            errors.append('%s: sites must be a list' % name)
            continue
        seen_sites = set()
        for site in sites:
            _validate_site(name, site, source, limits, seen_sites, errors)
            slope_cap = (layer.get('limits') or {}).get('max_support_slope_pct')
            if vanilla is not None and slope_cap is not None and isinstance(site, dict) and _finite_list(site.get('pos'), 3):
                evidence = height_evidence(vanilla_grid, site['pos'][0], site['pos'][2], limits['flat_radius_m'])
                slope = evidence.get('support_slope_pct')
                if slope is None or slope > slope_cap:
                    errors.append('%s/%s: unsupported or excessive vanilla-row support slope' % (name, site.get('id')))
        objects = expand_layer(source, layer)
        cap = limits['max_objects_per_layer']
        own = (layer.get('limits') or {}).get('max_objects')
        if own is not None:
            cap = min(cap, own)
        if len(objects) > cap:
            errors.append('%s: %d objects exceed the per-layer cap of %d' % (name, len(objects), cap))
        total += len(objects)
        loot = sum(1 for item in objects if isinstance(item, dict) and item.get('loot') == 'proto')
        loot_total += loot
        loot_cap = min(limits['max_loot_per_layer'], (layer.get('limits') or {}).get('max_loot', limits['max_loot_per_layer']))
        if loot > loot_cap:
            errors.append('%s: %d loot objects exceed the per-layer loot cap of %d' % (
                name, loot, loot_cap))
        ids = set()
        for item in objects:
            pos = _validate_object(name, item, source, limits, errors)
            if isinstance(item, dict) and isinstance(item.get('id'), str):
                if item['id'] in ids:
                    errors.append('%s: object id %s is used twice' % (name, item['id']))
                ids.add(item['id'])
            if pos is not None:
                site_key = (name, item['site']) if isinstance(item.get('site'), str) else None
                placed.append((name, item['id'] if isinstance(item.get('id'), str) else '?', pos,
                               (layer.get('limits') or {}), site_key))
            info = source.classes['classes'].get(item.get('class')) if isinstance(item, dict) else None
            if isinstance(item, dict) and item.get('loot') == 'proto' and 'site' not in item \
                    and isinstance(info, dict) and info.get('loot_group') is False:
                errors.append('%s/%s: loot proto but class %s has no loot group in the allowlist' % (
                    name, item.get('id'), item['class']))
            if proto_names is not None and isinstance(item, dict) and item.get('loot') == 'proto' \
                    and item.get('class') not in proto_names and isinstance(item.get('class'), str):
                errors.append('%s/%s: loot proto but %s has no mapgroupproto prototype group' % (
                    name, item.get('id'), item['class']))
    if total > limits['max_objects_total']:
        errors.append('total of %d objects exceeds the total cap of %d' % (total, limits['max_objects_total']))
    if loot_total > limits['max_loot_total']:
        errors.append('total of %d loot objects exceeds the total loot cap of %d' % (
            loot_total, limits['max_loot_total']))
    errors.extend(_spacing_errors(placed, limits))
    if vanilla is not None:
        errors.extend(_vanilla_errors(placed, vanilla, limits))
    return errors


def _spacing_errors(placed, limits):
    errors = []
    for i, (layer_a, id_a, pa, lim_a, site_a) in enumerate(placed):
        for layer_b, id_b, pb, lim_b, site_b in placed[i + 1:]:
            if site_a is not None and site_a == site_b:
                continue  # pieces of one site are checked once, on the composition itself
            need = max(limits['min_spacing_m'], lim_a.get('min_spacing_m', 0), lim_b.get('min_spacing_m', 0))
            gap = math.hypot(pa[0] - pb[0], pa[2] - pb[2])
            if gap == 0.0:
                errors.append('duplicate position: %s/%s and %s/%s' % (layer_a, id_a, layer_b, id_b))
            elif gap < need:
                errors.append('spacing: %s/%s and %s/%s are %.1f m apart (minimum %.1f m)' % (
                    layer_a, id_a, layer_b, id_b, gap, need))
    return errors


class Grid:
    """Fixed-cell spatial index over (class, x, y, z) rows."""

    def __init__(self, rows, cell=50.0):
        self.cell, self.cells = cell, {}
        for row in rows:
            self.cells.setdefault((int(row[1] // cell), int(row[3] // cell)), []).append(row)

    def add(self, row):
        self.cells.setdefault((int(row[1] // self.cell), int(row[3] // self.cell)), []).append(row)

    def near(self, x, z, radius):
        reach = int(radius // self.cell) + 1
        cx, cz = int(x // self.cell), int(z // self.cell)
        for i in range(cx - reach, cx + reach + 1):
            for j in range(cz - reach, cz + reach + 1):
                for row in self.cells.get((i, j), ()):
                    if math.hypot(row[1] - x, row[3] - z) <= radius:
                        yield row


def _flat_errors(where, pos, grid, limits):
    """Height support of one piece: enough vanilla rows nearby, nearly level, near the piece's own height.
    Vanilla group rows are the only height evidence offline; real ground is unverified until native testing."""
    radius = limits['flat_radius_m']
    heights = sorted(row[2] for row in grid.near(pos[0], pos[2], radius))
    if len(heights) < limits['flat_min_rows']:
        return ['flat: %s has only %d vanilla rows within %d m to support its height (need %d)' % (
            where, len(heights), radius, limits['flat_min_rows'])]
    errors = []
    if heights[-1] - heights[0] > limits['flat_spread_m']:
        errors.append('flat: %s: %d vanilla rows within %d m span %.1f m of height (maximum %.1f m)' % (
            where, len(heights), radius, heights[-1] - heights[0], limits['flat_spread_m']))
    median = heights[len(heights) // 2]
    if abs(pos[1] - median) > limits['flat_site_tolerance_m']:
        errors.append('flat: %s: height %.1f differs from the median %.1f of %d vanilla rows within %d m '
                      '(tolerance %.1f m)' % (where, pos[1], median, len(heights), radius,
                                              limits['flat_site_tolerance_m']))
    return errors


def _vanilla_errors(placed, vanilla, limits):
    grid, errors = Grid(vanilla), []
    for layer_id, object_id, pos, own, site in placed:
        base = limits['piece_vanilla_clearance_m'] if site is not None else limits['vanilla_clearance_m']
        need = max(base, own.get('vanilla_clearance_m', 0))
        hits = sorted(grid.near(pos[0], pos[2], need), key=lambda r: (math.hypot(r[1] - pos[0], r[3] - pos[2]), r))
        if hits:
            row = hits[0]
            errors.append('vanilla group %s is %.1f m from %s/%s (clearance %.1f m)' % (
                row[0], math.hypot(row[1] - pos[0], row[3] - pos[2]), layer_id, object_id, need))
        if site is not None:
            errors.extend(_flat_errors('%s/%s' % (layer_id, object_id), pos, grid, limits))
    return errors


def check(source, vanilla=None, proto_names=None):
    errors = validate(source, vanilla, proto_names)
    if errors:
        raise ValueError('overlay layers refused: ' + '; '.join(errors[:8]) + (
            ' (+%d more)' % (len(errors) - 8) if len(errors) > 8 else ''))


# ---- inventory readers (stream; the vanilla files are large and never committed) ------------------------------

def _stream(path, tag):
    path = Path(path)
    if path.stat().st_size > MAX_XML:
        raise ValueError('%s is larger than the %d byte limit' % (path.name, MAX_XML))
    with open(path, 'rb') as handle:
        for _event, element in ET.iterparse(handle):
            if element.tag == tag:
                yield element
                element.clear()


def read_vanilla(mission):
    """[(class, x, y, z)] from the mission's mapgrouppos.xml, in file order. pos is 'x y z' (y is height)."""
    path = economy.plain_file(mission, economy.child(mission, POS))
    rows = []
    for group in _stream(path, 'group'):
        x, y, z = (float(v) for v in group.get('pos').split())
        rows.append((group.get('name'), x, y, z))
    return rows


def read_proto_names(mission):
    path = economy.plain_file(mission, economy.child(mission, 'mapgroupproto.xml'))
    return {group.get('name') for group in _stream(path, 'group') if group.get('name')}


def missing_classes_in_server(server_root, classes):
    """Classes whose name does not appear in the addon PBO the allowlist cites. Name presence only: this does
    not prove scope or that CreateObjectEx can spawn the class."""
    missing, cache = [], {}
    for name, info in sorted(classes['classes'].items()):
        pbo = Path(server_root) / 'addons' / info['pbo']
        if pbo not in cache:
            cache[pbo] = pbo.read_bytes() if pbo.is_file() else b''
        if name.encode() not in cache[pbo]:
            missing.append(name)
    return missing


# ---- compose ------------------------------------------------------------------------------------------------

def enabled_layers(source):
    by_id = {layer['id']: layer for layer in source.layers}
    unknown = [i for i in source.profile['enabled'] if i not in by_id]
    if unknown:
        raise ValueError('profile enables unknown layer(s): ' + ', '.join(unknown))
    return [by_id[i] for i in source.profile['enabled']]


def spawner_path(layer_id):
    return '%s/objects/%s.json' % (MANAGED, layer_id)


def _spawner(objects):
    rows = []
    for item in sorted(objects, key=lambda o: o['id']):
        x, y, z = (round(float(v), 6) for v in item['pos'])
        rows.append({'name': item['class'], 'pos': [x, y, z], 'ypr': [wrap(float(item['yaw'])), 0.0, 0.0],
                     'scale': 1.0, 'enableCEPersistency': False, 'customString': ''})
    return json.dumps({'Objects': rows}, indent=2).encode() + b'\n'


def _group_rows(layer, objects):
    # Vanilla rows satisfy a = wrap(90 - rpy_z) (observed on the installed 1.30 mapgrouppos.xml). That `a`
    # equals the spawner yaw is an assumption: verify in game, or cross-check with the engine's own export
    # (GetCEApi().ExportProxyData) of the spawned objects.
    lines = ['    <!-- hollow-country-overlays %s v%d (runtime-unverified) -->' % (layer['id'], layer['version'])]
    for item in sorted(objects, key=lambda o: o['id']):
        if item['loot'] != 'proto':
            continue
        x, y, z = (round(float(v), 6) for v in item['pos'])
        yaw = wrap(float(item['yaw']))
        lines.append('    <group name="%s" pos="%s %s %s" rpy="%s %s %s" a="%s" />' % (
            item['class'], fmt(x), fmt(y), fmt(z), fmt(0.0), fmt(0.0), fmt(wrap(90.0 - yaw)), fmt(yaw)))
    return lines


def compose(source):
    """{relative name: bytes}: one spawner file per enabled layer, the mapgrouppos rows, a manifest with hashes."""
    check(source)
    layers = enabled_layers(source)
    files = {}
    rows = []
    for layer in layers:
        objects = expand_layer(source, layer)
        files['objects/%s.json' % layer['id']] = _spawner(objects)
        rows.extend(_group_rows(layer, objects))
    files['mapgrouppos.additions.xml'] = ('\n'.join(rows) + '\n').encode()
    verified = all(layer['status'] == 'runtime-verified' for layer in layers) and bool(layers)
    manifest = {
        'kind': MANIFEST_KIND, 'schema': 1,
        'status': 'runtime-verified' if verified else 'runtime-unverified',
        'layers': [{'id': l['id'], 'version': l['version'], 'objects': len(expand_layer(source, l)),
                    'sites': len(l.get('sites') or []), 'status': l['status'],
                    'sha256': sha(canonical(dict(l, objects=sorted(l['objects'], key=lambda o: o['id']),
                                                 **({'sites': sorted(l['sites'], key=lambda t: t['id'])}
                                                    if l.get('sites') else {}))))} for l in layers],
        'sources': {'profile_sha256': sha(canonical(source.profile)),
                    'classes_sha256': sha(canonical(source.classes)),
                    'compositions_sha256': sha(canonical(source.compositions))},
        'outputs': {name: sha(data) for name, data in sorted(files.items())},
    }
    files['manifest.json'] = canonical(manifest)
    return files


# ---- site selection rule ------------------------------------------------------------------------------------

def _is_military(name):
    return name.startswith(MILITARY_PREFIXES)


def _clusters(rows, link=CLUSTER_LINK_M):
    points = sorted(row for row in rows if _is_military(row[0]))
    grid = Grid(points, link)
    seen, clusters = set(), []
    for start in points:
        if start in seen:
            continue
        seen.add(start)
        stack, members = [start], []
        while stack:
            row = stack.pop()
            members.append(row)
            for other in grid.near(row[1], row[3], link):
                if other not in seen:
                    seen.add(other)
                    stack.append(other)
        clusters.append(sorted(members))
    return clusters


def suggest_sites(rows, per_cluster=2, max_total=12):
    """Deterministic tent sites from (class, x, y, z) vanilla rows.

    Rule: group the military-style rows (Land_Mil_*, Land_Tisy_*, Land_Medical_Tent*) into clusters by single
    linkage at 250 m; keep clusters with at least 6 rows and fewer than 25 percent tents; around each
    non-tent row try 8 compass bearings at 20 m and 28 m; a site must be within 100 m of the cluster centre,
    at least 12 m from every vanilla row, have at least 3 vanilla rows within 60 m whose heights span at most
    1.2 m (flat ground assumption; y is their median); choose the sites nearest the centre, pairs at least
    15 m apart. Class cycles through the Big1 tent family, yaw alternates 0 and 180 (the only yaws that do
    not depend on the unverified sign convention)."""
    rows = sorted(rows)
    grid = Grid(rows)
    chosen = []
    clusters = [c for c in _clusters(rows) if len(c) >= MIN_CLUSTER_GROUPS
                and sum('_Tent' in r[0] for r in c) / len(c) < MAX_TENT_SHARE]
    clusters.sort(key=lambda c: (-len(c), c[0][1], c[0][3]))
    for cluster in clusters:
        if len(chosen) >= max_total:
            break
        cx = sum(r[1] for r in cluster) / len(cluster)
        cz = sum(r[3] for r in cluster) / len(cluster)
        candidates = {}
        for anchor in (r for r in cluster if '_Tent' not in r[0]):
            for radius in SITE_RADII:
                for bearing in SITE_BEARINGS:
                    angle = math.radians(bearing)
                    x, z = round(anchor[1] + radius * math.sin(angle), 6), round(anchor[3] + radius * math.cos(angle), 6)
                    if (x, z) in candidates or math.hypot(x - cx, z - cz) > SITE_MAX_FROM_CENTRE_M:
                        continue
                    if any(True for _ in grid.near(x, z, SITE_CLEARANCE_M)):
                        continue
                    heights = sorted(r[2] for r in grid.near(x, z, SITE_FLAT_RADIUS_M))
                    if len(heights) < SITE_MIN_NEIGHBOURS or heights[-1] - heights[0] > SITE_FLAT_SPREAD_M:
                        continue
                    candidates[(x, z)] = (round(heights[len(heights) // 2], 6), len(heights),
                                          round(heights[-1] - heights[0], 3), anchor[0])
        taken = []
        for (x, z), (y, count, spread, anchor_class) in sorted(
                candidates.items(), key=lambda kv: (math.hypot(kv[0][0] - cx, kv[0][1] - cz), kv[0])):
            if len(taken) >= per_cluster or len(chosen) + len(taken) >= max_total:
                break
            if any(math.hypot(x - t['pos'][0], z - t['pos'][2]) < SITE_PAIR_M for t in taken):
                continue
            index = len(chosen) + len(taken)
            taken.append({'pos': [x, y, z], 'yaw': 0.0 if index % 2 == 0 else 180.0,
                          'class': SITE_CLASSES[index % len(SITE_CLASSES)],
                          'cluster': [round(cx), round(cz)], 'anchor': anchor_class,
                          'y_basis': 'median of %d vanilla rows within %d m, spread %.1f m' % (
                              count, SITE_FLAT_RADIUS_M, spread)})
        chosen.extend(taken)
    return chosen


# ---- composition planning -----------------------------------------------------------------------------------

BASE_LINK_M = 120.0
BASE_MIN_ROWS = 4
GUARD_CLASSES = ('Land_Guardhouse', 'Land_Mil_Guardhouse1', 'Land_Mil_Guardhouse2')
APPROACH_MIN_M = 60.0
APPROACH_REACH_M = 350.0
ROADSIDE_BASE_GAP_M = 300.0
ROADSIDE_PAIR_M = 150.0
SETTLEMENT_ROWS = 8
SEARCH_START_M = 20.0
SEARCH_STEP_M = 10.0
SEARCH_STEPS = 16
SEARCH_OFFSETS = (0.0, 12.0, -12.0, 24.0, -24.0)
ROADSIDE_RADII = (20.0, 28.0, 36.0, 44.0)
# Turns tried from the preferred flank bearing when nothing fits there (dumps only; outposts keep the approach).
FLANK_TURNS = (0.0, 45.0, -45.0, 90.0, -90.0, 135.0, -135.0, 180.0)
# (composition, bearing offset from the approach, heading offset from the search bearing)
OUTPOST_PLAN = (('forward-outpost', 0.0, 0.0), ('mg-nest', -35.0, 0.0), ('comms-post', 180.0, 180.0),
                ('mg-nest', 35.0, 0.0))
DUMP_PLAN = (('supply-dump', 90.0, 180.0), ('field-hospital', -90.0, 180.0), ('tent-camp', 150.0, 180.0))
LAYER_CAPS = {'military-tents-v1': 30, 'military-outposts-v1': 140, 'supply-dumps-v1': 135,
              'roadside-checkpoints-v1': 130}
LAYER_THEMES = {
    'military-tents-v1': ('tents', 'Extra military tents in tent-poor vanilla military clusters.'),
    'military-outposts-v1': ('outposts', 'Forward outposts, MG nests and comms posts at the approaches to the '
                                         'vanilla military bases and barracks clusters.'),
    'supply-dumps-v1': ('supply dumps', 'Supply dumps, field hospitals and tent camps on the flanks of the '
                                        'vanilla military bases, with vanilla loot groups only.'),
    'roadside-checkpoints-v1': ('road checkpoints', 'Sandbag and barrier checkpoints beside the vanilla guard '
                                                    'booths that stand away from the military bases.')}


def piece_stats(comp):
    """(pieces, loot pieces) of a composition."""
    pieces = comp['pieces']
    return len(pieces), sum(1 for p in pieces if p['loot'] == 'proto')


def place_site(source, composition, x, z, heading, rows, taken=None):
    """A site dict {composition, pos, heading, y_basis} when the whole composition fits at (x, z), else None.

    Every piece must keep the piece clearance from vanilla groups, have flat vanilla height support (see
    _flat_errors, the same rule validate applies), stay in the map and stay clear of the positions in taken
    (x, z of earlier pieces). The site height is the median height of the vanilla rows within the flat radius of
    the site centre."""
    limits = limits_of(source.profile)
    comp = ((source.compositions or {}).get('compositions') or {}).get(composition)
    if not isinstance(comp, dict):
        return None
    grid = rows if isinstance(rows, Grid) else Grid(rows)
    heights = sorted(row[2] for row in grid.near(x, z, limits['flat_radius_m']))
    if len(heights) < limits['flat_min_rows']:
        return None
    y = round(heights[len(heights) // 2], 6)
    clearance = limits['piece_vanilla_clearance_m']
    apart = max(limits['min_spacing_m'], clearance)
    for piece in comp['pieces']:
        px, pz = piece_world(piece, x, z, heading)
        pos = [px, round(y + float(piece.get('dy', 0.0)), 6), pz]
        if not (0.0 <= px <= limits['map_size'] and 0.0 <= pz <= limits['map_size']):
            return None
        if any(True for _ in grid.near(px, pz, clearance)) or _flat_errors('', pos, grid, limits):
            return None
        if isinstance(taken, Grid):
            if any(True for _ in taken.near(px, pz, apart)):
                return None
        elif any(math.hypot(px - tx, pz - tz) < apart for tx, tz in taken or ()):
            return None
    return {'composition': composition, 'pos': [round(x, 6), y, round(z, 6)],
            'heading': round(heading % 360.0, 6),
            'y_basis': 'median of %d vanilla rows within %d m, spread %.1f m' % (
                len(heights), limits['flat_radius_m'], heights[-1] - heights[0])}


def _bearing(dx, dz):
    return math.degrees(math.atan2(dx, dz)) % 360.0


def _settlement_bearing(x, z, civil):
    """Compass bearing from (x, z) to the centroid of the nearest vanilla non-military rows (None if none)."""
    near = sorted(((math.hypot(r[1] - x, r[3] - z), r) for r in civil if math.hypot(r[1] - x, r[3] - z) > 25.0),
                  key=lambda pair: (pair[0], pair[1]))[:SETTLEMENT_ROWS]
    if not near:
        return None
    mx = sum(r[1] for _d, r in near) / len(near)
    mz = sum(r[3] for _d, r in near) / len(near)
    return _bearing(mx - x, mz - z)


def _bases(rows):
    """Military base clusters: Land_Mil_ rows (no tents or guard booths) linked at 120 m, at least 4 rows."""
    points = [r for r in rows if _is_military(r[0]) and '_Tent' not in r[0] and not r[0].startswith(
        'Land_Mil_Guardhouse')]
    clusters = [c for c in _clusters(points, BASE_LINK_M) if len(c) >= BASE_MIN_ROWS]
    clusters.sort(key=lambda c: (-len(c), c[0][1], c[0][3]))
    out = []
    for members in clusters:
        cx = sum(r[1] for r in members) / len(members)
        cz = sum(r[3] for r in members) / len(members)
        out.append({'rows': members, 'cx': cx, 'cz': cz,
                    'extent': max(math.hypot(r[1] - cx, r[3] - cz) for r in members)})
    return out


def _approach(base, guards, civil):
    """Bearing of the approach to a base: toward the nearest vanilla guard booth that stands outside the base
    (booths stand on the approach roads), else toward the nearest settlement. No road data exists offline."""
    cx, cz = base['cx'], base['cz']
    reach = [(math.hypot(g[1] - cx, g[3] - cz), g) for g in guards]
    reach = sorted((d, g) for d, g in reach if APPROACH_MIN_M <= d <= base['extent'] + APPROACH_REACH_M)
    if reach:
        g = reach[0][1]
        return _bearing(g[1] - cx, g[3] - cz), 'guard booth %s' % g[0]
    away = [r for r in civil if math.hypot(r[1] - cx, r[3] - cz) > base['extent'] + 60.0]
    bearing = _settlement_bearing(cx, cz, away)
    return (bearing, 'nearest settlement') if bearing is not None else (None, None)


def _search_base(source, comp, base, bearing, heading, grid, taken):
    """First fit walking out from the base edge along a bearing (steps of 10 m, a few bearing offsets)."""
    s, c = math.sin(math.radians(bearing)), math.cos(math.radians(bearing))
    edge = max((r[1] - base['cx']) * s + (r[3] - base['cz']) * c for r in base['rows'])
    for step in range(SEARCH_STEPS + 1):
        d = max(SEARCH_START_M, edge + SEARCH_START_M) + step * SEARCH_STEP_M
        for offset in SEARCH_OFFSETS:
            angle = math.radians(bearing + offset)
            found = place_site(source, comp, base['cx'] + d * math.sin(angle), base['cz'] + d * math.cos(angle),
                               heading, grid, taken)
            if found is not None:
                return found
    return None


class _Budget:
    """Objects and loot a planned layer may still add, under the profile caps shared with every other layer."""

    def __init__(self, limits, layer_cap, shared):
        self.limits, self.layer_cap, self.shared = limits, layer_cap, shared
        self.objects = self.loot = 0

    def fits(self, comp):
        n, loot = piece_stats(comp)
        return (self.objects + n <= self.layer_cap
                and self.shared['objects'] + n <= self.limits['max_objects_total']
                and self.loot + loot <= self.limits['max_loot_per_layer']
                and self.shared['loot'] + loot <= self.limits['max_loot_total'])

    def take(self, comp):
        n, loot = piece_stats(comp)
        self.objects += n
        self.loot += loot
        self.shared['objects'] += n
        self.shared['loot'] += loot


def _record(source, layer, budget, site, taken, area, prefix):
    comp = source.compositions['compositions'][site['composition']]
    entry = dict(site, id='%s%02d' % (prefix, len(layer['sites']) + 1), area=area)
    layer['sites'].append(entry)
    budget.take(comp)
    taken.extend(piece_world(p, site['pos'][0], site['pos'][2], site['heading']) for p in comp['pieces'])


def _new_layer(ident, rule, inventory):
    theme, purpose = LAYER_THEMES[ident]
    basis = {'rule': rule}
    if inventory:
        basis['inventory'] = inventory
    return {'kind': LAYER_KIND, 'id': ident, 'version': 1, 'status': 'runtime-unverified', 'theme': theme,
            'purpose': purpose, 'basis': basis, 'objects': [], 'sites': []}


OUTPOST_RULE = (
    'Bases are Land_Mil_ rows (no tents or guard booths) linked at 120 m with at least 4 rows. The approach is the '
    'bearing from the base centre to the nearest vanilla guard booth 60 m or more away (within the base extent + '
    '350 m), else to the nearest settlement (no road data offline). Per base, in rounds: a forward outpost on the '
    'approach, an MG nest 35 degrees to the left, a comms post behind the base, then an MG nest 35 degrees to the right. Each site is found by '
    'walking out from the base edge along its bearing in 10 m steps with bearing offsets of 0, 12 and 24 degrees, '
    'and is kept only if every piece clears vanilla groups by 10 m and has flat vanilla height support.')
DUMP_RULE = (
    'On the flanks of the same bases (90 degrees either side of the approach, then 150 degrees): a supply dump, a '
    'field hospital and a tent camp, entrance facing the base, found with the same walk-out search and the same '
    'per-piece clearance and flat-support rules. When nothing fits on the preferred flank the search turns the '
    'bearing by 45, -45, 90, -90, 135, -135 and 180 degrees in that order and keeps the first fit.')
ROADSIDE_RULE = (
    'Anchors are vanilla guard booths (Land_Guardhouse, Land_Mil_Guardhouse1/2) more than 300 m outside every '
    'base extent, one per 150 m. The checkpoint stands 20, 28, 36 or 44 m from the booth on the first of 8 '
    'compass bearings that passes the per-piece rules; its lane runs toward the nearest settlement. The real road '
    'direction is not available offline, so lane alignment with the road is unverified.')


def plan_layers(source, rows, per_cluster=4, max_outposts=24, dumps_per_cluster=2, max_dumps=12, max_roadside=14,
                tents_per_cluster=3, max_tents=30, inventory=None):
    """The four themed layers, deterministic from vanilla (class, x, y, z) rows and the compositions.

    Layers: military-tents-v1 (suggest_sites singles), military-outposts-v1, supply-dumps-v1 and
    roadside-checkpoints-v1 (composition sites). Every layer stays within the profile's object and loot caps
    (planning stops adding sites that would exceed them) and keeps pieces apart from earlier sites."""
    limits = limits_of(source.profile)
    rows = sorted(rows)
    grid = Grid(rows)
    shared = {'objects': 0, 'loot': 0}
    caps = {i: min(c, limits['max_objects_per_layer']) for i, c in LAYER_CAPS.items()}
    taken = []
    tents = _new_layer('military-tents-v1', ' '.join(suggest_sites.__doc__.split('\n\n')[1].split()), inventory)
    del tents['sites']
    tent_cap = min(max_tents, caps['military-tents-v1'], limits['max_loot_per_layer'])
    for n, site in enumerate(suggest_sites(rows, tents_per_cluster, tent_cap), 1):
        tents['objects'].append({'id': 't%02d' % n, 'class': site['class'], 'pos': site['pos'], 'yaw': site['yaw'],
                                 'loot': 'proto', 'area': 'cluster@%d,%d' % tuple(site['cluster']),
                                 'y_basis': site['y_basis']})
        taken.append((site['pos'][0], site['pos'][2]))
    shared['objects'] += len(tents['objects'])
    shared['loot'] += len(tents['objects'])
    tents['limits'] = {'max_objects': caps['military-tents-v1']}
    outposts = _new_layer('military-outposts-v1', OUTPOST_RULE, inventory)
    dumps = _new_layer('supply-dumps-v1', DUMP_RULE, inventory)
    roadside = _new_layer('roadside-checkpoints-v1', ROADSIDE_RULE, inventory)
    budgets = {l['id']: _Budget(limits, caps[l['id']], shared) for l in (outposts, dumps, roadside)}
    comps = source.compositions['compositions']
    guards = [r for r in rows if r[0] in GUARD_CLASSES]
    civil = [r for r in rows if not _is_military(r[0]) and r[0] not in GUARD_CLASSES]
    all_bases = _bases(rows)
    for base in all_bases:
        base['approach'], base['via'] = _approach(base, guards, civil)
    bases = [b for b in all_bases if b['approach'] is not None]
    for layer, plan, rounds, cap in ((outposts, OUTPOST_PLAN, per_cluster, max_outposts),
                                     (dumps, DUMP_PLAN, dumps_per_cluster + 1, max_dumps)):
        budget = budgets[layer['id']]
        for index in range(min(rounds, len(plan))):
            composition, bearing_offset, heading_offset = plan[index]
            for base in bases:
                if len(layer['sites']) >= cap or not budget.fits(comps[composition]):
                    continue
                found = None
                for turn in (FLANK_TURNS if layer is dumps else (0.0,)):
                    bearing = (base['approach'] + bearing_offset + turn) % 360.0
                    found = _search_base(source, composition, base, bearing, bearing + heading_offset, grid, taken)
                    if found is not None:
                        break
                if found is not None:
                    _record(source, layer, budget, found, taken, 'base@%d,%d via %s' % (
                        round(base['cx']), round(base['cz']), base['via']), 'o' if layer is outposts else 'd')
    anchors = []
    for guard in guards:
        if any(math.hypot(guard[1] - cx, guard[3] - cz) <= extent + ROADSIDE_BASE_GAP_M for cx, cz, extent in ((b['cx'], b['cz'], b['extent']) for b in all_bases)):
            continue
        if any(math.hypot(guard[1] - a[1], guard[3] - a[3]) < ROADSIDE_PAIR_M for a in anchors):
            continue
        anchors.append(guard)
    budget = budgets[roadside['id']]
    for guard in anchors:
        if len(roadside['sites']) >= max_roadside or not budget.fits(comps['checkpoint']):
            continue
        heading = _settlement_bearing(guard[1], guard[3], civil)
        heading = 0.0 if heading is None else heading
        found = None
        for radius in ROADSIDE_RADII:
            for bearing in SITE_BEARINGS:
                angle = math.radians(bearing)
                found = place_site(source, 'checkpoint', guard[1] + radius * math.sin(angle),
                                   guard[3] + radius * math.cos(angle), heading, grid, taken)
                if found is not None:
                    break
            if found is not None:
                break
        if found is not None:
            _record(source, roadside, budget, found, taken, 'booth %s@%d,%d' % (
                guard[0], round(guard[1]), round(guard[3])), 'r')
    for layer in (outposts, dumps, roadside):
        layer['limits'] = {'max_objects': caps[layer['id']]}
    return {l['id']: l for l in (tents, outposts, dumps, roadside)}


# Expansion targets are geographic search centres, not asserted CE tier boundaries.
# Candidate order, composition rotation and acceptance are independent of XML row order.
EXPANSION_AREAS = (
    ('NWAF', 4600, 10200), ('NEAF', 12100, 12600), ('Balota', 4900, 2500),
    ('Tisy', 1700, 14200), ('Kamensk', 7900, 14600), ('VMC', 4500, 8300),
    ('Zelenogorsk', 2500, 5100), ('Myshkino', 1500, 7500), ('Pavlovo', 2100, 3400),
    ('Troitskoe', 7900, 13600), ('Severograd', 8400, 12800), ('Krasnostav', 11000, 12300),
    ('Vybor', 3800, 8900), ('Stary Sobor', 6200, 7700), ('Green Mountain', 3700, 6000),
    ('Altar', 8200, 9200), ('Prison Island approach', 2600, 1400),
)
# Keep existing authored layouts operational while the scene worker lands the rich kits.
# Re-running expand-plan after merging scenes selects their real pieces and rechecks fit.
EXPANSION_KITS = (
    ('field-hq', 'forward-outpost'), ('sniper-overwatch', 'mg-nest'),
    ('abandoned-checkpoint', 'checkpoint'), ('overrun-camp', 'tent-camp'),
    ('medevac-station', 'field-hospital'), ('radio-relay', 'comms-post'),
    ('ammo-dump', 'supply-dump'), ('mortar-pit', 'mg-nest'),
    ('fuel-depot', 'supply-dump'), ('motor-pool', 'forward-outpost'),
    ('fob-compound', 'forward-outpost'), ('crashed-convoy', 'checkpoint'),
    ('quarantine-post', 'checkpoint'), ('refugee-camp', 'tent-camp'),
    ('hunter-camp', 'tent-camp'), ('bandit-roadblock', 'checkpoint'),
    ('police-blockade', 'checkpoint'), ('helicopter-lz', 'forward-outpost'),
    ('supply-drop-site', 'supply-dump'), ('mass-grave-cleanup', 'field-hospital'),
)
EXPANSION_IDS = ('military-zones-v2', 'inland-discoveries-v2', 'civilian-stories-v2')


def height_evidence(grid, x, z, radius=60.0):
    """Vanilla-row support plane; a slope proxy, never a terrain measurement.

    Building group origins may differ from terrain. Nearly collinear rows cannot
    constrain a plane and are reported as such rather than implying level ground.
    """
    rows = sorted(grid.near(x, z, radius))
    if not rows:
        return {'rows': 0}
    n = len(rows)
    mx, my, mz = (sum(r[i] for r in rows) / n for i in (1, 2, 3))
    xx = sum((r[1] - mx) ** 2 for r in rows)
    zz = sum((r[3] - mz) ** 2 for r in rows)
    xz = sum((r[1] - mx) * (r[3] - mz) for r in rows)
    xy = sum((r[1] - mx) * (r[2] - my) for r in rows)
    zy = sum((r[3] - mz) * (r[2] - my) for r in rows)
    det = xx * zz - xz * xz
    slope = None
    if det > max(1.0, xx * zz * 0.01):
        sx, sz = (xy * zz - zy * xz) / det, (zy * xx - xy * xz) / det
        slope = round(100 * math.hypot(sx, sz), 4)
    heights = sorted(r[2] for r in rows)
    return {'rows': n, 'radius_m': radius, 'height_median_m': heights[n // 2],
            'height_spread_m': round(heights[-1] - heights[0], 4),
            'support_slope_pct': slope,
            'nearest_group_m': round(min(math.hypot(r[1] - x, r[3] - z) for r in rows), 4),
            'terrain_measured': False, 'roads_surveyed': False}


def plan_expansion(source, rows, inventory=None):
    """Add up to 301 bounded sites in deterministic geographic rounds, retaining v1 layers.

    Every piece passes the existing flat-height and spacing checks. New layers
    additionally reserve 16 m from vanilla group origins and reject unsupported
    or >3 percent support planes. No decoded WRP terrain/road data is available;
    these are conservative vanilla-row proxies. Remote candidates remain near
    isolated mapped structures: deep woods without height evidence are excluded.
    """
    rows = sorted(rows)
    grid = Grid(rows)
    limits = limits_of(source.profile)
    # New layers are regenerated from stock, never used as their own obstacles.
    retained = [l for l in source.layers if l['id'] not in EXPANSION_IDS]
    taken = [(o['pos'][0], o['pos'][2]) for l in retained for o in expand_layer(source, l)]
    centres = [(o['pos'][0], o['pos'][2]) for l in retained for o in l.get('sites', [])]
    taken_grid = Grid([('', x, 0, z) for x, z in taken])
    centre_grid = Grid([('', x, 0, z) for x, z in centres])
    planning_profile = json.loads(json.dumps(source.profile))
    planning_profile['limits']['piece_vanilla_clearance_m'] = 16.0
    planning = Source(planning_profile, source.classes, [], source.compositions)
    candidates = set()
    for row in rows:
        for dx in range(-60, 61, 20):
            for dz in range(-60, 61, 20):
                if dx * dx + dz * dz >= 400:
                    candidates.add((round((row[1] + dx) / 10) * 10.0,
                                    round((row[3] + dz) / 10) * 10.0))
    supported = []
    for x, z in sorted(candidates):
        evidence = height_evidence(grid, x, z)
        slope = evidence.get('support_slope_pct')
        if evidence['rows'] < limits['flat_min_rows'] or slope is None or slope > 3.0:
            continue
        if evidence['height_spread_m'] > limits['flat_spread_m'] or evidence['nearest_group_m'] < 22.0:
            continue
        supported.append((x, z, evidence))
    layers = []
    for ident, purpose in zip(EXPANSION_IDS, (
            'Military reinforcements at all named vanilla military areas.',
            'Inland field positions and isolated finds, biased toward northern and western military country.',
            'Town-edge quarantine, evacuation, policing and woodland survival stories.')):
        layers.append({'kind': LAYER_KIND, 'id': ident, 'version': 2, 'status': 'runtime-unverified',
                       'theme': purpose, 'purpose': purpose, 'objects': [], 'sites': [],
                       'limits': {'max_objects': 3500, 'max_loot': 600, 'vanilla_clearance_m': 16.0,
                                  'max_support_slope_pct': 3.0},
                       'basis': {'inventory': inventory or {}, 'rule': plan_expansion.__doc__,
                                 'candidate_count': len(supported), 'site_spacing_m': 55.0,
                                 'terrain': 'Vanilla group origins only; binary OPRW terrain is not decoded.',
                                 'tier': 'Geographic inland bias only; CE area flags retain authority.'}})
    used = set()
    def select(layer, pool, requested, area):
        desired, fallback = EXPANSION_KITS[requested % len(EXPANSION_KITS)]
        composition = desired if desired in source.compositions['compositions'] else fallback
        for x, z, evidence in pool:
            if (x, z) in used or any(True for _ in centre_grid.near(x, z, 55.0)):
                continue
            # Use a stable cardinal heading: avoids relying on road direction guesses.
            heading = (requested % 4) * 90.0
            found = place_site(planning, composition, x, z, heading, grid, taken_grid)
            if found is None:
                continue
            expanded = expand_layer(planning, {'sites': [dict(found, id='candidate')]})
            if len(expanded) + len(taken) > limits['max_objects_total']:
                raise ValueError('expansion exceeds total object budget')
            found.update(id='s%03d' % (len(layer['sites']) + 1), area=area,
                         requested_composition=desired, placement_evidence=evidence)
            layer['sites'].append(found)
            used.add((x, z)); centres.append((x, z))
            taken.extend((o['pos'][0], o['pos'][2]) for o in expanded)
            centre_grid.add(('', x, 0, z))
            for o in expanded:
                taken_grid.add((o['class'], *o['pos']))
            return True
        return False
    # Fair rounds: each named area gets a chance before any gets its second site.
    pools = {name: sorted((p for p in supported if math.hypot(p[0] - x, p[1] - z) <= 1800),
                         key=lambda p: (math.hypot(p[0] - x, p[1] - z), p[0], p[1]))
             for name, x, z in EXPANSION_AREAS}
    for turn in range(8):
        for index, (name, _x, _z) in enumerate(EXPANSION_AREAS):
            select(layers[0], pools[name], (turn * len(EXPANSION_AREAS) + index) % 12, name)
    # Inland military finds favour west/north, avoiding a fabricated CE tier override.
    inland = [p for p in supported if p[1] >= 7000 and (p[0] < 6500 or p[1] >= 12000)]
    inland.sort(key=lambda p: (sha(('%d,%d' % p[:2]).encode()), p[:2]))
    for turn in range(95):
        select(layers[1], inland, turn % 12, 'inland field position; tier subject to stock CE area flags')
    rural = sorted(supported, key=lambda p: (sha(('rural:%d,%d' % p[:2]).encode()), p[:2]))
    for turn in range(70):
        select(layers[2], rural, 12 + turn % 8, 'town-edge / isolated mapped structure; road and forest fit unverified')
    return {l['id']: l for l in layers}


# ---- report and map image -------------------------------------------------------------------------------------

def report(source, as_text=False):
    """Per layer and site: centre, theme, piece count and loot count. Explicit objects count as one-piece sites."""
    layers = []
    totals = {'objects': 0, 'loot': 0, 'sites': 0}
    comps = (source.compositions or {}).get('compositions') or {}
    for layer in source.layers:
        entry = {'id': layer['id'], 'theme': layer.get('theme', ''), 'status': layer.get('status'),
                 'enabled': layer['id'] in source.profile.get('enabled', []), 'sites': [], 'objects': 0, 'loot': 0}
        for item in layer.get('objects') or []:
            loot = 1 if item.get('loot') == 'proto' else 0
            entry['sites'].append({'id': item['id'], 'composition': item['class'], 'theme': layer.get('theme', ''),
                                   'centre': [round(v, 1) for v in item['pos']], 'heading': item.get('yaw'),
                                   'pieces': 1, 'loot': loot})
        for site in layer.get('sites') or []:
            comp = comps.get(site['composition'], {})
            pieces, loot = piece_stats(comp) if comp.get('pieces') else (0, 0)
            entry['sites'].append({'id': site['id'], 'composition': site['composition'],
                                   'theme': comp.get('theme', layer.get('theme', '')),
                                   'centre': [round(v, 1) for v in site['pos']], 'heading': site['heading'],
                                   'pieces': pieces, 'loot': loot})
        entry['objects'] = sum(s['pieces'] for s in entry['sites'])
        entry['loot'] = sum(s['loot'] for s in entry['sites'])
        for key, value in (('objects', entry['objects']), ('loot', entry['loot']), ('sites', len(entry['sites']))):
            totals[key] += value
        layers.append(entry)
    data = {'layers': layers, 'totals': totals}
    if not as_text:
        return data
    lines = []
    for entry in layers:
        lines.append('%s  theme=%s  sites=%d objects=%d loot=%d  status=%s%s' % (
            entry['id'], entry['theme'], len(entry['sites']), entry['objects'], entry['loot'], entry['status'],
            '' if entry['enabled'] else '  (not enabled)'))
        for site in entry['sites']:
            lines.append('  %-6s %-18s centre=(%.0f, %.0f, %.0f) heading=%s pieces=%d loot=%d' % (
                site['id'], site['composition'], site['centre'][0], site['centre'][1], site['centre'][2],
                '-' if site['heading'] is None else '%.0f' % site['heading'], site['pieces'], site['loot']))
    lines.append('totals: %d sites, %d objects, %d loot' % (totals['sites'], totals['objects'], totals['loot']))
    return '\n'.join(lines) + '\n'


PALETTE = ((255, 196, 40), (255, 96, 64), (70, 220, 120), (240, 90, 230), (250, 250, 250), (120, 200, 255))
BACKGROUND, CIVIL_DOT, MIL_DOT = (22, 24, 28), (64, 68, 76), (80, 150, 255)


def _png(width, height, pixels):
    raw = b''.join(b'\x00' + bytes(pixels[y * width * 3:(y + 1) * width * 3]) for y in range(height))

    def chunk(kind, body):
        crc = zlib.crc32(kind + body) & 0xffffffff
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', crc)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) + chunk(
        b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')


def render_png(source, rows, size=1024, window=None):
    """PNG bytes: vanilla group rows (dark dots, military in blue) with every layer's additions on top, one
    colour per layer in enabled-or-file order. window = (centre x, centre z, half size m) zooms; None is the
    whole map. A strip of colour swatches along the top edge keys the layers (see report for the names).
    Deterministic and stdlib only."""
    limits = limits_of(source.profile)
    cx, cz, half = window if window is not None else (limits['map_size'] / 2, limits['map_size'] / 2,
                                                       limits['map_size'] / 2)
    scale = size / (2.0 * half)
    pixels = bytearray(BACKGROUND * (size * size))

    def plot(x, z, radius, colour):
        px, py = (x - (cx - half)) * scale, ((cz + half) - z) * scale
        for j in range(int(py) - radius, int(py) + radius + 1):
            if 0 <= j < size:
                for i in range(int(px) - radius, int(px) + radius + 1):
                    if 0 <= i < size:
                        at = (j * size + i) * 3
                        pixels[at:at + 3] = bytes(colour)
    for row in sorted(rows):
        if _is_military(row[0]):
            continue
        plot(row[1], row[3], 0, CIVIL_DOT)
    for row in sorted(rows):
        if _is_military(row[0]):
            plot(row[1], row[3], 1, MIL_DOT)
    for index, layer in enumerate(source.layers):
        colour = PALETTE[index % len(PALETTE)]
        for item in expand_layer(source, layer):
            plot(item['pos'][0], item['pos'][2], 0 if window is None else 1, colour)
        for site in layer.get('sites') or []:
            plot(site['pos'][0], site['pos'][2], 3 if window is None else 4, colour)
        for item in layer.get('objects') or []:
            plot(item['pos'][0], item['pos'][2], 3 if window is None else 2, colour)
        for j in range(2, 8):
            for i in range(2 + index * 10, 10 + index * 10):
                if j < size and i < size:
                    pixels[(j * size + i) * 3:(j * size + i) * 3 + 3] = bytes(colour)
    return _png(size, size, pixels)


# ---- install / rollback -------------------------------------------------------------------------------------

def _patch_gameplay(original, paths):
    text = original.decode('utf-8')
    matches = list(re.finditer(r'("objectSpawnersArr"\s*:\s*)\[(.*?)\]', text, re.DOTALL))
    if len(matches) != 1:
        raise ValueError('cfggameplay.json needs exactly one objectSpawnersArr array')
    match = matches[0]
    existing = json.loads('[' + match.group(2) + ']')
    if not all(isinstance(p, str) for p in existing):
        raise ValueError('objectSpawnersArr must hold file path strings')
    duplicate = [p for p in paths if p in existing]
    if duplicate:
        raise ValueError('objectSpawnersArr already lists ' + ', '.join(duplicate))
    line_start = text.rfind('\n', 0, match.start()) + 1
    indent = re.match(r'[ \t]*', text[line_start:]).group(0)
    unit = '\t' if '\t' in indent or not indent else '    '
    body = ',\n'.join(indent + unit + json.dumps(p) for p in existing + paths)
    patched = text[:match.start(2) - 1] + '[\n' + body + '\n' + indent + ']' + text[match.end():]
    before, after = json.loads(text), json.loads(patched)
    before_arr = _find_arr(before)
    before_arr[:] = existing + paths
    if before != after:
        raise ValueError('cfggameplay.json patch would change more than objectSpawnersArr')
    return patched.encode('utf-8')


def _find_arr(document):
    arr = document.get('WorldsData', {}).get('objectSpawnersArr') if isinstance(document, dict) else None
    if not isinstance(arr, list):
        raise ValueError('cfggameplay.json has no WorldsData.objectSpawnersArr array')
    return arr


def _patch_pos(original, additions, expected_groups):
    ends = list(re.finditer(rb'</map\s*>', original))
    if len(ends) != 1:
        raise ValueError('mapgrouppos.xml needs exactly one closing map tag')
    if b'hollow-country-overlays' in original:
        raise ValueError('mapgrouppos.xml already carries overlay rows')
    fragment = additions.replace(b'\n', b'\r\n') if b'\r\n' in original else additions
    patched = original[:ends[0].start()] + fragment + original[ends[0].start():]
    root = economy.xml(patched, 'map')
    if len(root.findall('group')) != expected_groups:
        raise ValueError('mapgrouppos.xml patch would not add the expected rows')
    return patched


def _swap(managed, name, target, data):
    staged = economy.fresh_write(managed, name, data)
    try:
        os.chmod(staged, stat.S_IMODE(os.lstat(target).st_mode))
    except OSError:
        pass
    os.replace(staged, target)


def install(source, target):
    target = economy._target(target)
    managed = economy.child(target, MANAGED)
    if os.path.lexists(managed):
        raise ValueError('overlays already installed or interrupted; inspect/rollback first')
    for name in INPUTS:
        if not os.path.lexists(target / name):
            raise ValueError('mission has no %s; the overlays need it (install the gameplay step first)' % name)
    vanilla = read_vanilla(target)
    check(source, vanilla=vanilla, proto_names=read_proto_names(target))
    files = compose(source)
    layers = enabled_layers(source)
    paths = [spawner_path(layer['id']) for layer in layers]
    gameplay_before = economy.read_plain(target, GAMEPLAY)
    pos_before = economy.read_plain(target, POS)
    added = sum(1 for line in files['mapgrouppos.additions.xml'].splitlines() if line.lstrip().startswith(b'<group'))
    gameplay_after = _patch_gameplay(gameplay_before, paths)
    pos_after = _patch_pos(pos_before, files['mapgrouppos.additions.xml'], len(vanilla) + added)
    receipt = {'schema': 1, 'gameplay': {'before': sha(gameplay_before), 'after': sha(gameplay_after)},
               'mapgrouppos': {'before': sha(pos_before), 'after': sha(pos_after)},
               'outputs': {name: sha(data) for name, data in sorted(files.items())}}
    managed.mkdir()
    (managed / 'objects').mkdir()
    economy.fresh_write(managed, 'receipt.json', economy.encode(receipt))
    economy.fresh_write(managed, 'gameplay.backup', gameplay_before)
    economy.fresh_write(managed, 'mapgrouppos.backup', pos_before)
    for name, data in sorted(files.items()):
        economy.fresh_write(managed, name, data)
    _swap(managed, 'mapgrouppos.next', target / POS, pos_after)
    _swap(managed, 'gameplay.next', target / GAMEPLAY, gameplay_after)
    return files


def _preflight(managed, receipt):
    expected = {'receipt.json', 'gameplay.backup', 'mapgrouppos.backup', *receipt.get('outputs', {}),
                'gameplay.next', 'mapgrouppos.next'}
    for path in sorted(Path(managed).rglob('*')):
        name = path.relative_to(managed).as_posix()
        economy.child(managed, name)
        if path.is_dir() and not path.is_symlink():
            if name != 'objects':
                raise ValueError('unexpected managed directory; rollback refuses deletion')
            continue
        if name not in expected:
            raise ValueError('unexpected managed file; rollback refuses deletion')
        economy.plain_file(managed, path)


def rollback(target):
    target = economy._target(target)
    managed = economy.child(target, MANAGED)
    if not managed.is_dir():
        raise ValueError('nothing to roll back')
    receipt = json.loads(economy.read_plain(managed, 'receipt.json'))
    shape = isinstance(receipt, dict) and receipt.get('schema') == 1 and all(
        isinstance(receipt.get(k), dict) and set(receipt[k]) == {'before', 'after'}
        and all(isinstance(v, str) and HEX64.fullmatch(v) for v in receipt[k].values())
        for k in ('gameplay', 'mapgrouppos')) and isinstance(receipt.get('outputs'), dict)
    if not shape:
        raise ValueError('invalid overlay receipt')
    _preflight(managed, receipt)
    plan = []
    for key, name, backup in (('gameplay', GAMEPLAY, 'gameplay.backup'), ('mapgrouppos', POS, 'mapgrouppos.backup')):
        current = sha(economy.read_plain(target, name))
        if current == receipt[key]['after']:
            saved = economy.read_plain(managed, backup)
            if sha(saved) != receipt[key]['before']:
                raise ValueError('overlay backup drift: ' + name)
            plan.append((name, saved))
        elif current != receipt[key]['before']:
            raise ValueError('%s drift: roll back later installers first' % name)
    for name, data in receipt['outputs'].items():
        if sha(economy.read_plain(managed, name)) != data:
            raise ValueError('overlay output drift: ' + name)
    for name, saved in plan:
        _swap(managed, 'restore.next', target / name, saved)
    shutil.rmtree(managed)


def rollback_inputs(_mission=None):
    """Files outside the managed folder that the rollback reads (the rollback trial copies them)."""
    return list(INPUTS)


# ---- command line --------------------------------------------------------------------------------------------

def _layer_from_sites(sites, rule_text, inventory_sha, count):
    objects = []
    for n, site in enumerate(sites, 1):
        objects.append({'id': 't%02d' % n, 'class': site['class'], 'pos': site['pos'], 'yaw': site['yaw'],
                        'loot': 'proto', 'area': 'cluster@%d,%d' % tuple(site['cluster']),
                        'y_basis': site['y_basis']})
    return {'kind': LAYER_KIND, 'id': 'military-tents-v1', 'version': 1, 'status': 'runtime-unverified',
            'purpose': 'Extra military tents in tent-poor vanilla military clusters.',
            'basis': {'rule': rule_text, 'inventory': {'mapgrouppos_sha256': inventory_sha, 'groups': count}},
            'objects': objects}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('validate', 'compose', 'install', 'rollback', 'suggest', 'plan', 'report',
                                            'map', 'expand-plan'))
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--mission', type=Path, help='mission copy to read mapgrouppos.xml / mapgroupproto.xml from')
    parser.add_argument('--target', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--server-root', type=Path, help='DayZ server folder; checks class names against its addons')
    parser.add_argument('--per-cluster', type=int, default=None,
                        help='suggest: tents per cluster (2); plan: sites per base in the outposts layer (4)')
    parser.add_argument('--max-total', type=int, default=12)
    parser.add_argument('--tents-per-cluster', type=int, default=3)
    parser.add_argument('--max-tents', type=int, default=30)
    parser.add_argument('--max-outposts', type=int, default=24)
    parser.add_argument('--max-dumps', type=int, default=12)
    parser.add_argument('--max-roadside', type=int, default=14)
    parser.add_argument('--size', type=int, default=1024, help='map: image size in pixels')
    parser.add_argument('--window', help='map: x,z,half-size in metres to zoom (default the whole map)')
    args = parser.parse_args(argv)
    try:
        if args.command == 'rollback':
            if args.target is None:
                parser.error('--target is required')
            rollback(args.target)
            print('Overlays rolled back byte-exact')
            return 0
        if args.command == 'suggest':
            if args.mission is None:
                parser.error('--mission is required')
            rows = read_vanilla(args.mission)
            sites = suggest_sites(rows, args.per_cluster or 2, args.max_total)
            digest = sha((Path(args.mission) / POS).read_bytes())
            print(json.dumps(_layer_from_sites(sites, ' '.join(suggest_sites.__doc__.split('\n\n')[1].split()),
                                               digest, len(rows)), indent=2))
            return 0
        source = load_source(args.source)
        if args.command == 'report':
            sys.stdout.write(report(source, as_text=True))
            return 0
        if args.command in ('plan', 'map', 'expand-plan'):
            if args.mission is None or args.out is None:
                parser.error('--mission and --out are required')
            rows = read_vanilla(args.mission)
            if args.command == 'map':
                window = None if not args.window else tuple(float(v) for v in args.window.split(','))
                if window is not None and len(window) != 3:
                    parser.error('--window needs x,z,half')
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_bytes(render_png(source, rows, args.size, window))
                print('Map image written to %s' % args.out)
                return 0
            inventory = {'mapgrouppos_sha256': sha((Path(args.mission) / POS).read_bytes()), 'groups': len(rows)}
            if args.command == 'expand-plan':
                layers = plan_expansion(source, rows, inventory)
                proposed = Source(source.profile, source.classes,
                                  [l for l in source.layers if l['id'] not in layers] + list(layers.values()),
                                  source.compositions)
                check(proposed, rows, read_proto_names(args.mission))
            else:
                layers = plan_layers(source, rows, per_cluster=args.per_cluster or 4, max_outposts=args.max_outposts,
                                     max_dumps=args.max_dumps, max_roadside=args.max_roadside,
                                     tents_per_cluster=args.tents_per_cluster, max_tents=args.max_tents,
                                     inventory=inventory)
            args.out.mkdir(parents=True, exist_ok=True)
            for ident, layer in layers.items():
                (args.out / (ident + '.json')).write_bytes(canonical(layer))
            print('Planned layers written to %s: %s' % (args.out, ', '.join(
                '%s (%d sites/objects)' % (i, len(l.get('sites') or []) + len(l['objects'])) for i, l in layers.items())))
            return 0
        if args.command == 'install':
            if args.target is None:
                parser.error('--target is required')
            files = install(source, args.target)
            print('Overlays installed: %d spawner file(s), %d mapgrouppos row(s); runtime acceptance pending' % (
                sum(n.startswith('objects/') for n in files),
                sum(1 for l in files['mapgrouppos.additions.xml'].splitlines() if l.lstrip().startswith(b'<group'))))
            return 0
        vanilla = proto = None
        if args.mission is not None:
            vanilla, proto = read_vanilla(args.mission), read_proto_names(args.mission)
        check(source, vanilla, proto)
        if args.server_root is not None:
            missing = missing_classes_in_server(args.server_root, source.classes)
            if missing:
                raise ValueError('classes not found in the server addons: ' + ', '.join(missing))
        if args.command == 'compose':
            if args.out is None:
                parser.error('--out is required')
            args.out.mkdir(parents=True, exist_ok=True)
            for name, data in compose(source).items():
                (args.out / name).parent.mkdir(parents=True, exist_ok=True)
                (args.out / name).write_bytes(data)
            print('Composed overlays into %s' % args.out.name)
            return 0
        print('Overlay layers valid: %s; runtime-unverified%s' % (
            ', '.join('%s (%d objects)' % (l['id'], len(expand_layer(source, l))) for l in source.layers),
            '' if vanilla is not None else '; vanilla clearance not checked (no --mission)'))
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError) as error:
        print('refused: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
