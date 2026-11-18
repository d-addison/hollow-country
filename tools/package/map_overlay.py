"""Map overlay layers: small authored object layers added to a stock Chernarus+ mission, with CE loot rows.

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
import xml.etree.ElementTree as ET

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
LAYER_KIND = 'hollow-country-map-overlay'
MANIFEST_KIND = 'hollow-country-overlay-manifest'
STATUSES = ('runtime-unverified', 'runtime-verified')
LOOT = ('proto', 'none')
LAYER_ID = re.compile(r'[a-z][a-z0-9-]{0,47}')
OBJECT_ID = re.compile(r'[a-z0-9][a-z0-9_-]{0,31}')
CLASS_NAME = re.compile(r'[A-Za-z0-9_]{1,80}')
HEX64 = re.compile(r'[0-9a-f]{64}')
MAX_XML = 64 * 1024 * 1024
Y_RANGE = (-50.0, 800.0)
DEFAULT_LIMITS = {'map_size': 15360, 'max_objects_total': 200, 'max_objects_per_layer': 48,
                  'min_spacing_m': 6.0, 'vanilla_clearance_m': 8.0}
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
    """The three authored inputs: profile (enabled layers and limits), class allowlist, layers."""

    def __init__(self, profile, classes, layers):
        self.profile, self.classes, self.layers = profile, classes, list(layers)


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
    return Source(read(directory / 'profile.json'), read(directory / 'classes.json'), layers)


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


def validate(source, vanilla=None, proto_names=None):
    """Every problem as a list of strings (empty means valid). vanilla = [(class, x, y, z)], proto_names = set."""
    errors = []
    if not _validate_profile(source, errors):
        return errors
    limits = limits_of(source.profile)
    seen_layers, placed, total = set(), [], 0
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
        objects = layer.get('objects')
        if not isinstance(objects, list):
            errors.append('%s: objects must be a list' % name)
            continue
        cap = limits['max_objects_per_layer']
        own = (layer.get('limits') or {}).get('max_objects')
        if own is not None:
            cap = min(cap, own)
        if len(objects) > cap:
            errors.append('%s: %d objects exceed the per-layer cap of %d' % (name, len(objects), cap))
        total += len(objects)
        ids = set()
        for item in objects:
            pos = _validate_object(name, item, source, limits, errors)
            if isinstance(item, dict) and isinstance(item.get('id'), str):
                if item['id'] in ids:
                    errors.append('%s: object id %s is used twice' % (name, item['id']))
                ids.add(item['id'])
            if pos is not None:
                placed.append((name, item['id'] if isinstance(item.get('id'), str) else '?', pos,
                               (layer.get('limits') or {})))
            if proto_names is not None and isinstance(item, dict) and item.get('loot') == 'proto' \
                    and item.get('class') not in proto_names and isinstance(item.get('class'), str):
                errors.append('%s/%s: loot proto but %s has no mapgroupproto prototype group' % (
                    name, item.get('id'), item['class']))
    if total > limits['max_objects_total']:
        errors.append('total of %d objects exceeds the total cap of %d' % (total, limits['max_objects_total']))
    errors.extend(_spacing_errors(placed, limits))
    if vanilla is not None:
        errors.extend(_vanilla_errors(placed, vanilla, limits))
    return errors


def _spacing_errors(placed, limits):
    errors = []
    for i, (layer_a, id_a, pa, lim_a) in enumerate(placed):
        for layer_b, id_b, pb, lim_b in placed[i + 1:]:
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

    def near(self, x, z, radius):
        reach = int(radius // self.cell) + 1
        cx, cz = int(x // self.cell), int(z // self.cell)
        for i in range(cx - reach, cx + reach + 1):
            for j in range(cz - reach, cz + reach + 1):
                for row in self.cells.get((i, j), ()):
                    if math.hypot(row[1] - x, row[3] - z) <= radius:
                        yield row


def _vanilla_errors(placed, vanilla, limits):
    grid, errors = Grid(vanilla), []
    for layer_id, object_id, pos, own in placed:
        need = max(limits['vanilla_clearance_m'], own.get('vanilla_clearance_m', 0))
        hits = sorted(grid.near(pos[0], pos[2], need), key=lambda r: (math.hypot(r[1] - pos[0], r[3] - pos[2]), r))
        if hits:
            row = hits[0]
            errors.append('vanilla group %s is %.1f m from %s/%s (clearance %.1f m)' % (
                row[0], math.hypot(row[1] - pos[0], row[3] - pos[2]), layer_id, object_id, need))
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


def _spawner(layer):
    rows = []
    for item in sorted(layer['objects'], key=lambda o: o['id']):
        x, y, z = (round(float(v), 6) for v in item['pos'])
        rows.append({'name': item['class'], 'pos': [x, y, z], 'ypr': [wrap(float(item['yaw'])), 0.0, 0.0],
                     'scale': 1.0, 'enableCEPersistency': False, 'customString': ''})
    return json.dumps({'Objects': rows}, indent=2).encode() + b'\n'


def _group_rows(layer):
    # Vanilla rows satisfy a = wrap(90 - rpy_z) (observed on the installed 1.30 mapgrouppos.xml). That `a`
    # equals the spawner yaw is an assumption: verify in game, or cross-check with the engine's own export
    # (GetCEApi().ExportProxyData) of the spawned objects.
    lines = ['    <!-- hollow-country-overlays %s v%d (runtime-unverified) -->' % (layer['id'], layer['version'])]
    for item in sorted(layer['objects'], key=lambda o: o['id']):
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
        files['objects/%s.json' % layer['id']] = _spawner(layer)
        rows.extend(_group_rows(layer))
    files['mapgrouppos.additions.xml'] = ('\n'.join(rows) + '\n').encode()
    verified = all(layer['status'] == 'runtime-verified' for layer in layers) and bool(layers)
    manifest = {
        'kind': MANIFEST_KIND, 'schema': 1,
        'status': 'runtime-verified' if verified else 'runtime-unverified',
        'layers': [{'id': l['id'], 'version': l['version'], 'objects': len(l['objects']),
                    'status': l['status'], 'sha256': sha(canonical(dict(l, objects=sorted(
                        l['objects'], key=lambda o: o['id']))))} for l in layers],
        'sources': {'profile_sha256': sha(canonical(source.profile)),
                    'classes_sha256': sha(canonical(source.classes))},
        'outputs': {name: sha(data) for name, data in sorted(files.items())},
    }
    files['manifest.json'] = canonical(manifest)
    return files


# ---- site selection rule ------------------------------------------------------------------------------------

def _is_military(name):
    return name.startswith(MILITARY_PREFIXES)


def _clusters(rows):
    points = sorted(row for row in rows if _is_military(row[0]))
    grid = Grid(points, CLUSTER_LINK_M)
    seen, clusters = set(), []
    for start in points:
        if start in seen:
            continue
        seen.add(start)
        stack, members = [start], []
        while stack:
            row = stack.pop()
            members.append(row)
            for other in grid.near(row[1], row[3], CLUSTER_LINK_M):
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
    parser.add_argument('command', choices=('validate', 'compose', 'install', 'rollback', 'suggest'))
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--mission', type=Path, help='mission copy to read mapgrouppos.xml / mapgroupproto.xml from')
    parser.add_argument('--target', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--server-root', type=Path, help='DayZ server folder; checks class names against its addons')
    parser.add_argument('--per-cluster', type=int, default=2)
    parser.add_argument('--max-total', type=int, default=12)
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
            sites = suggest_sites(rows, args.per_cluster, args.max_total)
            digest = sha((Path(args.mission) / POS).read_bytes())
            print(json.dumps(_layer_from_sites(sites, ' '.join(suggest_sites.__doc__.split('\n\n')[1].split()),
                                               digest, len(rows)), indent=2))
            return 0
        source = load_source(args.source)
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
            ', '.join('%s (%d objects)' % (l['id'], len(l['objects'])) for l in source.layers),
            '' if vanilla is not None else '; vanilla clearance not checked (no --mission)'))
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError) as error:
        print('refused: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
