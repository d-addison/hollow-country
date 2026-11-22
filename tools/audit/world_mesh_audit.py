"""Deterministic, read-only world placement audit; no native acceptance implied."""
import argparse
from collections import defaultdict
from dataclasses import dataclass
import itertools
import json
import math
from pathlib import Path
import re

from tools.audit import odol56, pbo_config as pbo
from tools.package import interior_points_gen as gen, map_overlay
from tools.package.loot_reach_audit import collision_triangles, cross, dot, lod_for, subtract
from tools.release.ship_inputs import ADDONS

ROOT = Path(__file__).resolve().parents[2]
# Reviewable audit policy, in metres unless otherwise stated. These are offline
# review thresholds, not measured engine performance or interaction limits.
POLICY = {
    'pivot_offset_m': 0.5, 'origin_y_tolerance_m': 0.10,
    'lowest_visual_triangles': 2000, 'lowest_visual_sections': 20,
    'door_radius_m': 0.30, 'door_height_m': 1.8, 'door_sweep_each_way_m': 1.5,
    'contact_epsilon_m': 0.005,
    # Paths LOD walk check: agent column of door_radius_m x door_height_m moved along
    # authored path segments; boxes lower than the step-over height are walked over.
    'path_step_over_m': 0.20, 'path_sample_step_m': 0.10, 'stair_min_slope': 0.30,
}
GEOMETRY, VIEW_GEOMETRY, PATHS = 1e13, 6e15, 4e15
CLASS_CATALOG = 'config/map-overlays/classes.json'
SHELTER_PROPS = ('StaticObj_Furniture_fireplace_grill', 'StaticObj_Misc_Chair_Camp1',
                 'StaticObj_Furniture_PaperBox_01_small_closed')
WIRING = ('Not wired into preland. A future preland adapter must invoke this module, '
          'supply full-client --addons (models decode with tools.audit.odol56), '
          'retain the JSON report, and use --require-installed to refuse SKIPs. '
          'Native placement, terrain contact and action checks remain separate.')


@dataclass(frozen=True)
class Placement:
    group: str
    key: str
    classname: str
    position: tuple = (0., 0., 0.)
    orientation: tuple = (0., 0., 0.)
    scale: float = 1.
    host: str = ''
    terrain: bool = False


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def discover(repo):
    """Inventory authored placements, including disabled layers/templates.

    Reuse the production composition expansion. Native spawner JSON is also
    supported wherever shipped beneath mission/ (currently generated at install).
    Do not scan evidence JSON as though it were a second placement source.
    """
    repo = Path(repo)
    rows = []
    overlays = repo / 'config/map-overlays'
    if overlays.is_dir():
        source = map_overlay.load_source(overlays)
        errors = []
        # Expansion skips malformed pieces; refuse these instead of losing classes.
        map_overlay._validate_compositions(source, map_overlay.limits_of(source.profile), errors)
        if errors:
            raise ValueError('invalid overlay compositions')
        for layer in source.layers:
            for item in map_overlay.expand_layer(source, layer):
                rows.append(Placement('overlay:' + layer['id'], item['id'], item['class'],
                                      tuple(item['pos']), (item['yaw'], 0., 0.)))
    template_dir = repo / 'mission/hollow-country/interiors/templates'
    for path in sorted(template_dir.glob('t-*.json')):
        doc = read_json(path)
        group = path.relative_to(repo).as_posix()
        for slot in doc['PropSlots']:
            rows.append(Placement(group, str(slot['Id']), slot['Type'], tuple(slot['Position']),
                                  tuple(slot['Orientation']), host=doc['BuildingClass']))
    shelter = repo / 'mission/hollow-country/travel/auditshelter_scenes.json'
    if shelter.is_file():
        doc = read_json(shelter)
        for scene in doc['Scenes'] + doc.get('AdditionalScenes', []):
            if len(scene['Slots']) != len(SHELTER_PROPS):
                raise ValueError('unsupported shelter slot count')
            for index, (name, position) in enumerate(zip(SHELTER_PROPS, scene['Slots'])):
                rows.append(Placement('shelter:' + scene['Id'], str(index), name,
                                      tuple(position), host=scene['BuildingClass'], terrain=True))
    for path in sorted((repo / 'mission').rglob('*.json')):
        doc = read_json(path)
        if not isinstance(doc, dict) or not isinstance(doc.get('Objects'), list):
            continue
        for index, item in enumerate(doc['Objects']):
            rows.append(Placement(path.relative_to(repo).as_posix(), str(index), item['name'],
                                  tuple(item['pos']), tuple(item['ypr']), item.get('scale', 1.) or 1.))
    identities = [(r.group, r.key) for r in rows]
    if len(set(identities)) != len(identities):
        raise ValueError('duplicate placement identity')
    for row in rows:
        if (len(row.position) != 3 or len(row.orientation) != 3 or row.scale <= 0
                or not all(math.isfinite(x) for x in (*row.position, *row.orientation, row.scale))):
            raise ValueError('invalid placement transform')
    return sorted(rows, key=lambda r: (r.group, r.key, r.classname))


def bounds(points):
    points = list(points)
    if not points:
        return None
    return tuple(tuple(f(points, key=lambda p: p[a])[a] for a in range(3)) for f in (min, max))


def corners(box):
    return itertools.product(*zip(*box))


def rotate(point, orientation):
    """Yaw (+z towards +x), pitch about x, roll about z; degrees, Y-up."""
    y, p, r = map(math.radians, orientation)
    x, h, z = point
    x, h = x * math.cos(r) - h * math.sin(r), x * math.sin(r) + h * math.cos(r)
    h, z = h * math.cos(p) - z * math.sin(p), h * math.sin(p) + z * math.cos(p)
    return (x * math.cos(y) + z * math.sin(y), h, -x * math.sin(y) + z * math.cos(y))


def placed_box(box, row):
    return bounds(tuple(row.position[a] + rotate(tuple(v * row.scale for v in point),
                                                row.orientation)[a] for a in range(3))
                  for point in corners(box))


def overlaps(a, b):
    return all(min(a[1][i], b[1][i]) - max(a[0][i], b[0][i]) > POLICY['contact_epsilon_m']
               for i in range(3))


def triangle_box(triangle, box):
    """Triangle/AABB separating-axis test; mere floor contact is permitted."""
    epsilon = POLICY['contact_epsilon_m']
    center = tuple((box[0][i] + box[1][i]) / 2 for i in range(3))
    half = tuple(max(0., (box[1][i] - box[0][i]) / 2 - epsilon) for i in range(3))
    vertices = [subtract(p, center) for p in triangle]
    edges = [subtract(vertices[(i + 1) % 3], vertices[i]) for i in range(3)]
    axes = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
    axes += [cross(edges[0], edges[1])]
    axes += [cross(edge, axis) for edge in edges for axis in axes[:3]]
    for axis in axes:
        if dot(axis, axis) < 1e-16:
            continue
        projection = [dot(v, axis) for v in vertices]
        radius = sum(half[i] * abs(axis[i]) for i in range(3))
        if min(projection) > radius or max(projection) < -radius:
            return False
    return True


def segment_distance(point, a, b):
    delta = tuple(b[i] - a[i] for i in range(2))
    length = sum(x*x for x in delta)
    t = max(0., min(1., sum((point[i]-a[i])*delta[i] for i in range(2))/length)) if length else 0.
    return math.dist(point, tuple(a[i] + t * delta[i] for i in range(2)))


def segment_rectangle(a, b, low, high):
    start, end = 0., 1.
    for i in range(2):
        delta = b[i] - a[i]
        if abs(delta) < 1e-12:
            if not low[i] <= a[i] <= high[i]:
                return False
        else:
            t0, t1 = sorted(((low[i]-a[i])/delta, (high[i]-a[i])/delta))
            start, end = max(start, t0), min(end, t1)
            if start > end:
                return False
    return True


def door_intersects(box, door):
    """Exact capsule/rectangle distance in XZ, extruded 1.8m vertically.

    door = (threshold centre, horizontal normal); 0.6m is diameter.
    """
    center, normal = door
    if box[1][1] <= center[1] or box[0][1] >= center[1] + POLICY['door_height_m']:
        return False
    sweep = POLICY['door_sweep_each_way_m']
    a = tuple(center[i] - sweep * normal[i] for i in (0, 2))
    b = tuple(center[i] + sweep * normal[i] for i in (0, 2))
    low, high = tuple(box[0][i] for i in (0, 2)), tuple(box[1][i] for i in (0, 2))
    if segment_rectangle(a, b, low, high):
        return True
    distances = [math.dist(p, tuple(max(low[i], min(high[i], p[i])) for i in range(2))) for p in (a, b)]
    distances += [segment_distance(p, a, b) for p in itertools.product(*zip(low, high))]
    return min(distances) < POLICY['door_radius_m']


def path_segments(model):
    """Paths LOD (4e15) polylines as (start, end, is_stair); None when the model has no Paths LOD.

    Each LOD face is read as a polyline of consecutive vertices (a two-vertex face is one
    segment). A segment is a stair flight when it rises more than stair_min_slope per metre
    of horizontal run, including vertical (ladder-like) segments.
    """
    lod = lod_for(model, PATHS)
    if lod is None:
        return None
    points = [tuple(v[a] + model.bounding_center[a] for a in range(3)) for v in lod.vertices]
    result = []
    for face in lod.faces:
        for a, b in zip(face, face[1:]):
            start, end = points[a], points[b]
            run = math.hypot(end[0] - start[0], end[2] - start[2])
            rise = abs(end[1] - start[1])
            if run == 0 and rise == 0:
                continue
            result.append((start, end, rise > POLICY['stair_min_slope'] * run))
    return result


def path_blocked(box, segment):
    """True when the agent column swept along one path segment meets the box.

    Sampled every path_sample_step_m (conservative to well within one step); the column is
    door_radius_m wide on each side of the sample and door_height_m tall above the path
    point, ignoring boxes whose top is below path_step_over_m.
    """
    start, end, _ = segment
    radius, height = POLICY['door_radius_m'], POLICY['door_height_m']
    low, high = (box[0][0], box[0][2]), (box[1][0], box[1][2])
    count = max(1, math.ceil(math.dist(start, end) / POLICY['path_sample_step_m']))
    for i in range(count + 1):
        point = tuple(start[a] + (end[a] - start[a]) * i / count for a in range(3))
        if box[1][1] <= point[1] + POLICY['path_step_over_m'] or box[0][1] >= point[1] + height:
            continue
        nearest = tuple(max(low[a], min(high[a], point[2 * a])) for a in range(2))
        if math.dist((point[0], point[2]), nearest) < radius:
            return True
    return False


def class_bounds(box):
    """Measured Geometry bounds for one class, millimetre-rounded and ordered by axis."""
    size = tuple(box[1][a] - box[0][a] for a in range(3))
    return {'geometry_min_m': [round(v, 3) for v in box[0]], 'geometry_max_m': [round(v, 3) for v in box[1]],
            'size_m': [round(v, 3) for v in size], 'footprint_m': [round(size[0], 3), round(size[2], 3)]}


def reserve_status(reserve, footprint):
    """Compare an authored reserve with the measured footprint; axis order is unspecified."""
    if not reserve or len(reserve) != 2:
        return 'NO_RESERVE'
    covered = all(r + 1e-9 >= f for r, f in zip(sorted(reserve, reverse=True), sorted(footprint, reverse=True)))
    return 'RESERVE_COVERS_MEASURED' if covered else 'RESERVE_BELOW_MEASURED'


def bounds_update(result, catalog):
    """Proposed measured-bounds update for the class catalogue; never applied automatically.

    Covers every catalogue class the audit measured, placed or not. Classes that could not
    be measured are listed, never guessed.
    """
    measured = dict(result.get('catalog_bounds', {}))
    for metric in result['classes']:
        if 'geometry_bounds' in metric:
            measured[metric['classname']] = metric['geometry_bounds']
    classes = {}
    for name in sorted(set(measured) & set(catalog)):
        row = class_bounds(measured[name])
        reserve = catalog[name].get('footprint_reserve_m')
        row['footprint_reserve_m'] = reserve
        row['reserve_status'] = reserve_status(reserve, row['footprint_m'])
        classes[name] = row
    unmeasured = sorted({s['classname'] for s in result['skipped']
                         if s.get('reason') in ('MODEL_UNRESOLVED', 'GEOMETRY_LOD_EMPTY_OR_MISSING',
                                                'CLASS_BOUNDS_UNMEASURED', 'MODEL_DECODE_FAILED')
                         and s.get('classname') in catalog and s['classname'] not in classes})
    return {'schema': 1, 'kind': 'measured_bounds_proposal', 'target': CLASS_CATALOG,
            'applied': False, 'reader_revision': gen.READER_REVISION, 'classes': classes,
            'unmeasured': unmeasured,
            'note': 'Geometry LOD vertex bounds in the model frame; review before copying into the catalogue.'}


class Installed:
    """All installed PBOs, indexed and read in place; no extracted assets."""
    def __init__(self, addons):
        self.classes, self.members = {}, {}
        self.visual_available = not ((addons.parent / 'DayZServer_x64.exe').is_file()
                                     and not (addons.parent / 'DayZ_x64.exe').is_file())
        for path in sorted(addons.glob('*.pbo')):
            index = pbo.read_pbo_index(path)
            self.classes.update(pbo.read_configs(path, ['CfgVehicles'], index)['CfgVehicles'])
            for entry in index['entries']:
                if entry['name'].lower().endswith('.p3d'):
                    key = pbo.normalize_path(index['prefix'] + '/' + entry['name'])
                    if key in self.members:
                        raise ValueError('ambiguous installed model')
                    self.members[key] = (path, index, entry['name'])

    def model(self, classname, host=False):
        path = pbo.normalize_path(classname if classname.lower().endswith('.p3d')
                                  else pbo.resolve_field(self.classes, classname, 'model') or '')
        if path and not path.endswith('.p3d'):
            path += '.p3d'
        if path not in self.members:
            return None
        archive, index, member = self.members[path]
        try:
            model = odol56.read_odol(pbo.read_member(archive, index, member))
        except odol56.OdolError:
            raise ValueError('ODOL model decode failed') from None
        # Match existing reach/support tools: building raw vertices are already
        # in the CE/model frame; standalone prop vertices restore bounding_center.
        if host or classname.startswith('Land_'):
            model.bounding_center = (0., 0., 0.)
        return model


def geometry(model):
    lod = lod_for(model, GEOMETRY)
    if lod is None:
        return None, []
    triangles = list(collision_triangles(model, lod))
    # Bounds and bottom use all Geometry vertices, not visual bounds or only
    # vertices referenced by faces. Proxy marker triangles remain excluded
    # from host-solid intersection tests.
    points = [tuple(v[a] + model.bounding_center[a] for a in range(3)) for v in lod.vertices]
    return bounds(points), triangles


def doors(model):
    """Use authored door leaf selections, never infer doors from host extents.

    Selection vertices/faces give a leaf plane; its horizontal normal supplies
    the in/out direction. Axis-only memory points cannot establish a threshold.
    """
    lod = lod_for(model, GEOMETRY)
    result, skipped = [], []
    for selection in sorted(lod.named_selections if lod else (), key=lambda s: s.name):
        if not re.fullmatch(r'door\d+', selection.name, re.IGNORECASE):
            continue
        indices = set(selection.vertices)
        indices.update(i for f in selection.faces for i in lod.faces[f])
        points = [tuple(lod.vertices[i][a] + model.bounding_center[a] for a in range(3))
                  for i in sorted(indices)]
        box = bounds(points)
        normal = None
        if len(points) >= 3:
            base = points[0]
            for i in range(1, len(points)-1):
                candidate = cross(subtract(points[i], base), subtract(points[i+1], base))
                length = math.hypot(candidate[0], candidate[2])
                if length > 1e-6 and abs(candidate[1]) < length * .2:
                    normal = (candidate[0]/length, 0., candidate[2]/length)
                    break
        if box is None or normal is None:
            skipped.append(selection.name)
        else:
            result.append((selection.name, ((sum(p[0] for p in points)/len(points), box[0][1],
                                            sum(p[2] for p in points)/len(points)), normal)))
    return result, skipped


def audit(rows, installed, catalog=()):
    """Audit placements; catalogue classes without placements only get measured bounds."""
    findings, skips, metrics, hosts = [], [], [], []
    catalog_bounds = {}
    class_rows = defaultdict(list)
    for row in rows:
        class_rows[row.classname].append(row)
    boxes = {}

    def record(target, name, code, **detail):
        target.append(dict(classname=name, reason=code, **detail))

    unplaced = sorted(set(catalog) - set(class_rows))
    for name in sorted(set(class_rows) | set(unplaced)):
        if name not in class_rows:
            try:
                model = installed.model(name)
                box = geometry(model)[0] if model is not None else None
            except (ValueError, OSError, EOFError, IndexError, KeyError, AttributeError, TypeError):
                record(skips, name, 'CLASS_BOUNDS_UNMEASURED', detail='decode')
                continue
            if box is None:
                record(skips, name, 'CLASS_BOUNDS_UNMEASURED', detail='model' if model is None else 'geometry')
            else:
                catalog_bounds[name] = box
            continue
        try:
            model = installed.model(name)
            if model is None:
                record(skips, name, 'MODEL_UNRESOLVED')
                continue
            if getattr(model, 'failed_lods', ()):
                record(skips, name, 'READER_PARTIAL_LODS')
            box, _ = geometry(model)
            metric = {'classname': name, 'placements': len(class_rows[name])}
            if box is None:
                record(skips, name, 'GEOMETRY_LOD_EMPTY_OR_MISSING')
            else:
                boxes[name] = box
                center = tuple((box[0][i]+box[1][i])/2 for i in range(3))
                metric.update(geometry_bounds=box, geometry_center=center, lowest_y_m=box[0][1])
                if math.dist(center, (0, 0, 0)) > POLICY['pivot_offset_m']:
                    record(findings, name, 'PIVOT_OFFSET', center_m=center)
                if abs(box[0][1]) > POLICY['origin_y_tolerance_m']:
                    record(findings, name, 'FLOATING_ORIGIN' if box[0][1] > 0 else 'SINKING_ORIGIN',
                           lowest_y_m=box[0][1])
            # Conservative superset: every placed prop is checked, including
            # classes whose action availability is decided by runtime scripts.
            view = lod_for(model, VIEW_GEOMETRY)
            if view is None or not view.vertices or not view.faces:
                record(findings, name, 'VIEW_GEOMETRY_EMPTY_OR_MISSING')
            visual = [lod for lod in model.lods if 0 <= lod.resolution < 1000]
            if not installed.visual_available:
                record(skips, name, 'FULL_CLIENT_VISUALS_REQUIRED')
            elif not visual:
                record(skips, name, 'VISUAL_LOD_MISSING')
            else:
                # Lowest numeric visual resolution (LOD0 when present), as in
                # the existing generator; never substitute a cheaper distant LOD.
                lod = min(visual, key=lambda l: (l.resolution, l.index))
                count = sum(max(0, len(face)-2) for face in lod.faces)
                metric.update(lowest_visual_resolution=lod.resolution, lowest_visual_triangles=count)
                if count > POLICY['lowest_visual_triangles']:
                    record(findings, name, 'VISUAL_TRIANGLE_COST', triangles=count)
                sections = getattr(lod, 'sections', None)
                if sections is None:
                    record(skips, name, 'SECTION_COUNT_UNAVAILABLE')
                else:
                    count = len(sections)
                    metric['lowest_visual_sections'] = count
                    if count > POLICY['lowest_visual_sections']:
                        record(findings, name, 'VISUAL_SECTION_COST', sections=count)
            metrics.append(metric)
        except (ValueError, OSError, EOFError, IndexError, KeyError, AttributeError, TypeError):
            record(skips, name, 'MODEL_DECODE_FAILED')

    grouped = defaultdict(list)
    for row in rows:
        if row.classname in boxes and not row.terrain:
            grouped[row.group].append((row, placed_box(boxes[row.classname], row)))
        if row.terrain:
            record(skips, row.classname, 'LIVE_TERRAIN_AND_SHELTER_RETRIES_REQUIRED', group=row.group, key=row.key)
    for group, pieces in sorted(grouped.items()):
        # Sweep along X: avoid comparing distant pieces of large authored layers.
        active = []
        for row, box in sorted(pieces, key=lambda p: (p[1][0][0], p[0].key)):
            active = [(other, bb) for other, bb in active if bb[1][0] > box[0][0]]
            for other, bb in active:
                if overlaps(box, bb):
                    record(findings, row.classname, 'PIECE_AABB_OVERLAP', group=group, key=row.key,
                           other_class=other.classname, other_key=other.key)
            active.append((row, box))
    host_rows = defaultdict(list)
    for row in rows:
        if row.host:
            host_rows[row.host].append(row)
    for host, placements in sorted(host_rows.items()):
        try:
            model = installed.model(host, host=True)
            if model and getattr(model, 'failed_lods', ()):
                for row in placements:
                    record(skips, row.classname, 'HOST_READER_PARTIAL_LODS', host=host,
                           group=row.group, key=row.key)
            host_box, triangles = geometry(model) if model else (None, [])
            door_rows, incomplete = doors(model) if model else ([], [])
            segments = path_segments(model) if model else None
        except (ValueError, OSError, EOFError, IndexError, KeyError, AttributeError, TypeError):
            host_box, triangles, door_rows, incomplete, segments = None, [], [], [], None
        # A host without a Paths LOD has no authored AI/stair paths: recorded, not a skip.
        hosts.append({'classname': host, 'placements': len(placements),
                      'paths_lod': segments is not None, 'path_segments': len(segments or ()),
                      'stair_segments': sum(1 for seg in segments or () if seg[2])})
        for row in placements:
            detail = dict(group=row.group, key=row.key, host=host)
            if not door_rows or incomplete:
                record(skips, row.classname, 'DOOR_SELECTION_UNAVAILABLE_OR_INCOMPLETE', **detail,
                       selections=incomplete)
            if not host_box:
                record(skips, row.classname, 'HOST_GEOMETRY_UNAVAILABLE', **detail)
            if row.classname not in boxes:
                continue
            if row.terrain:
                # Local slot Y is discarded by SurfaceY at runtime. Do not turn
                # an assumed host-relative height into a clearance verdict.
                continue
            box = placed_box(boxes[row.classname], row)
            if any(triangle_box(tri, box) for tri in triangles):
                record(findings, row.classname, 'HOST_GEOMETRY_ENCROACHMENT', **detail)
            for selection, door in door_rows:
                if door_intersects(box, door):
                    record(findings, row.classname, 'DOOR_APRON_INTERSECTION', selection=selection, **detail)
            hit = {False: 0, True: 0}
            for segment in segments or ():
                if path_blocked(box, segment):
                    hit[segment[2]] += 1
            if hit[True]:
                record(findings, row.classname, 'STAIR_PATH_INTERSECTION', segments=hit[True], **detail)
            if hit[False]:
                record(findings, row.classname, 'PATH_LOD_INTERSECTION', segments=hit[False], **detail)
    result = report(rows, metrics, findings, skips)
    result['hosts'] = sorted(hosts, key=lambda h: h['classname'])
    result['catalog_bounds'] = {n: catalog_bounds[n] for n in sorted(catalog_bounds)}
    return result


def report(rows, metrics=(), findings=(), skips=()):
    ordered = lambda values: sorted(values, key=lambda v: json.dumps(v, sort_keys=True))
    return {'schema': 1, 'status': 'fail' if findings else 'pass', 'checked': len(metrics),
            'placements': len(rows), 'findings': ordered(findings), 'skipped': ordered(skips),
            'classes': ordered(metrics), 'policy': POLICY, 'reader_revision': gen.READER_REVISION,
            'reader_sha256': gen.READER_HASHES, 'wiring_needed': WIRING,
            'runtime_acceptance': 'pending', 'hosts': [], 'catalog_bounds': {},
            'limitations': ['AABB overlap is a conservative review finding, not proven mesh clipping.',
                            'Origin Y is model-relative; no terrain support or runtime grounding verdict.',
                            'Door leaf selection planes approximate the closed-door threshold.',
                            'All placed props receive the View Geometry check as an interaction superset.',
                            'Shelter slots inventory the base layout; live terrain and retry variants are skipped.',
                            'Paths LOD faces are read as polylines; the sampled agent column is an offline walk approximation, not the engine navmesh.',
                            'Host checks use baked Geometry, excluding proxy marker faces; stock proxy solids are not expanded.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--addons', type=Path, default=ADDONS)
    parser.add_argument('--reader', type=Path, default=None, help=argparse.SUPPRESS)  # legacy, ignored
    parser.add_argument('--report', type=Path, help='JSON destination; defaults to stdout')
    parser.add_argument('--bounds-out', type=Path,
                        help='write the proposed measured-bounds update for the class catalogue')
    parser.add_argument('--require-installed', action='store_true')
    args = parser.parse_args(argv)
    try:
        rows = discover(args.repo)
        catalog = {}
        catalog_path = Path(args.repo) / CLASS_CATALOG
        if catalog_path.is_file():
            catalog = read_json(catalog_path)['classes']
        proposal = None
        missing = []
        if not args.addons.is_dir() or not any(args.addons.glob('*.pbo')):
            missing.append('INSTALLED_ADDONS_UNAVAILABLE')
        if missing:
            result = report(rows, skips=[{'reason': reason} for reason in missing])
        else:
            result = audit(rows, Installed(args.addons), catalog)
            proposal = bounds_update(result, catalog)
    except Exception:
        # External reader/PBO diagnostics can contain private filesystem paths.
        # Keep errors machine-readable without echoing paths or raw exceptions.
        result = report([], findings=[{'reason': 'INVALID_INPUT_OR_READER'}])
    rendered = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n'
    if args.bounds_out and proposal is not None:
        args.bounds_out.write_text(json.dumps(proposal, sort_keys=True, indent=2, allow_nan=False) + '\n',
                                   encoding='utf-8')
    if args.report:
        args.report.write_text(rendered, encoding='utf-8')
    else:
        print(rendered, end='')
    for reason in sorted({s['reason'] for s in result['skipped']}):
        print('SKIP ' + reason)
    print(f"world_mesh_audit: {result['status']} checked={result['checked']} "
          f"findings={len(result['findings'])} skipped={len(result['skipped'])}")
    return int(bool(result['findings']) or (args.require_installed and bool(result['skipped'])))


if __name__ == '__main__':
    raise SystemExit(main())
