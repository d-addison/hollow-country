"""Conservative, offline shelf reach audit; never establishes native acceptance.

Uses the generator's hash-pinned external ODOL reader and installed vanilla PBOs.
No asset extraction is written. --fix only removes refused points and parallel
surface evidence, recalculating container capacity; it never invents support.
Run as ``python3 -B -m tools.package.loot_reach_audit --help``.
"""
import argparse
from collections import Counter
import copy
import io
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from tools.audit import pbo_config as pbo
from tools.package import interior_catalog, interior_templates, loot_boost as loot
from tools.package import interior_points_gen as gen

ROOT = Path(__file__).resolve().parents[2]
GEOMETRY = 1e13
MEMORY = 1e15
ROADWAY = 3e15
# Lower end of the owner's approximate vanilla reach band. These are audit
# margins, not measurements of the engine's interaction implementation.
MAX_RISE = 1.8
MAX_REACH = 1.0
HEIGHT = 1.8
RADIUS = .22
CELL = 1.0


def model_point(stock):
    return [-stock[2], stock[1], stock[0]]


def transform(point, matrix):
    if matrix is None:
        return tuple(point)
    return tuple(matrix[9 + a] + sum(point[i] * matrix[3 * i + a] for i in range(3))
                 for a in range(3))


def subtract(a, b):
    return tuple(x - y for x, y in zip(a, b))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def intersection(start, end, triangle):
    """Two-sided segment/triangle test; endpoints excluded by 0.1 mm."""
    edge1, edge2 = subtract(triangle[1], triangle[0]), subtract(triangle[2], triangle[0])
    direction = subtract(end, start)
    h = cross(direction, edge2)
    det = dot(edge1, h)
    if abs(det) < 1e-10:
        return False
    s = subtract(start, triangle[0])
    u = dot(s, h) / det
    if not -1e-7 <= u <= 1 + 1e-7:
        return False
    q = cross(s, edge1)
    v = dot(direction, q) / det
    if v < -1e-7 or u + v > 1 + 1e-7:
        return False
    t = dot(edge2, q) / det
    return .0001 < t < .9999


def lod_for(model, resolution):
    return next((lod for lod in model.lods
                 if math.isclose(lod.resolution, resolution, rel_tol=1e-6)), None)


def triangles(model, lod, matrix=None):
    vertices = [transform([v[a] + model.bounding_center[a] for a in range(3)], matrix)
                for v in lod.vertices]
    for face in lod.faces:
        for i in range(1, len(face) - 1):
            yield (vertices[face[0]], vertices[face[i]], vertices[face[i + 1]])


def collision_triangles(model, lod, matrix=None):
    # Named proxy faces encode transforms; the referenced model supplies the
    # physical geometry. Marker triangles are not walls or furniture blockers.
    markers = {index for selection in lod.named_selections
               if selection.name.lower().startswith('proxy:')
               for index in selection.faces}
    solid = copy.copy(lod)
    solid.faces = [face for index, face in enumerate(lod.faces) if index not in markers]
    return triangles(model, solid, matrix)


class Scene:
    """XZ indexed installed geometry triangles, including baked furniture proxies."""
    def __init__(self):
        self.triangles = []
        self.cells = {}
        self.floor_cells = {}
        self.height_bounds = []

    def add(self, values):
        for tri in values:
            index = len(self.triangles)
            self.triangles.append(tri)
            low, high = min(v[1] for v in tri), max(v[1] for v in tri)
            # Wider than intersection's barycentric tolerance, including long
            # triangles. This is only a broad-phase rejection, never a hit.
            margin = 1e-6 * (high-low+1)
            self.height_bounds.append((low-margin, high+margin))
            normal = cross(subtract(tri[1], tri[0]), subtract(tri[2], tri[0]))
            horizontal = abs(normal[1]) >= .9 * math.sqrt(dot(normal, normal))
            for x in range(math.floor(min(v[0] for v in tri) / CELL),
                           math.floor(max(v[0] for v in tri) / CELL) + 1):
                for z in range(math.floor(min(v[2] for v in tri) / CELL),
                               math.floor(max(v[2] for v in tri) / CELL) + 1):
                    self.cells.setdefault((x, z), []).append(index)
                    if horizontal:
                        self.floor_cells.setdefault((x, z), []).append(index)

    def candidate_indices(self, start, end):
        found = set()
        for x in range(math.floor(min(start[0], end[0]) / CELL),
                       math.floor(max(start[0], end[0]) / CELL) + 1):
            for z in range(math.floor(min(start[2], end[2]) / CELL),
                           math.floor(max(start[2], end[2]) / CELL) + 1):
                found.update(self.cells.get((x, z), ()))
        return sorted(found)

    def candidates(self, start, end):
        return (self.triangles[i] for i in self.candidate_indices(start, end))

    def clear(self, start, end):
        low, high = min(start[1], end[1]), max(start[1], end[1])
        return not any(intersection(start, end, self.triangles[i])
                       for i in self.candidate_indices(start, end)
                       if self.height_bounds[i][0] <= high and self.height_bounds[i][1] >= low)

    def floors(self, x, z, low, high):
        result = []
        # Winding differs between LODs; the precomputed index retains horizontal
        # planes either way, with exactly the same normal threshold as before.
        for i in self.floor_cells.get((math.floor(x / CELL), math.floor(z / CELL)), ()):
            tri = self.triangles[i]
            y = gen.triangle_height(tri, x, z)
            if y is not None and low <= y <= high:
                result.append(y)
        return sorted(set(round(y, 5) for y in result), reverse=True)


def body_clear(scene, position):
    x, y, z = position
    # Vertical cylinder samples and cross sections prevent standing inside a
    # solid, thin wall or furniture. This remains a finite static sample.
    offsets = [(0, 0), (RADIUS, 0), (-RADIUS, 0), (0, RADIUS), (0, -RADIUS)]
    if any(not scene.clear((x+dx, y+.06, z+dz), (x+dx, y+HEIGHT, z+dz))
           for dx, dz in offsets):
        return False
    return all(scene.clear((x-RADIUS, y+h, z), (x+RADIUS, y+h, z))
               and scene.clear((x, y+h, z-RADIUS), (x, y+h, z+RADIUS))
               for h in (.2, .9, 1.65))


def approach_clear(scene, seed, stance, slots=()):
    # Straight same-storey corridor to a native CE floor anchor. Refuses paths
    # through walls/closed doors; does not infer open-door or stair navigation.
    if abs(seed[1] - stance[1]) > .20:
        return False
    # Sweep the whole standing body's conservative box against optional props.
    # Three horizontal ray heights alone can miss a thin shelf between them.
    for slot in slots:
        box = slot['Bounds']
        expanded = {'Min': [box['Min'][0]-RADIUS, box['Min'][1]-HEIGHT, box['Min'][2]-RADIUS],
                    'Max': [box['Max'][0]+RADIUS, box['Max'][1]-.06, box['Max'][2]+RADIUS]}
        if segment_box_hit(seed, stance, expanded):
            return False
    for height in (.2, .9, 1.65):
        for dx, dz in ((0, 0), (RADIUS, 0), (-RADIUS, 0), (0, RADIUS), (0, -RADIUS)):
            a = (seed[0]+dx, seed[1]+height, seed[2]+dz)
            b = (stance[0]+dx, stance[1]+height, stance[2]+dz)
            if (not scene.clear(a, b)
                    or any(segment_box_hit(a, b, slot['Bounds']) for slot in slots)):
                return False
    # Continuous horizontal rays alone could bridge a floor hole. Sample the
    # supporting floor along the corridor every 25 cm.
    steps = max(1, math.ceil(math.hypot(seed[0]-stance[0], seed[2]-stance[2]) / .25))
    for i in range(steps + 1):
        t = i / steps
        x, z = (seed[a] + t * (stance[a]-seed[a]) for a in (0, 2))
        y = seed[1] + t * (stance[1]-seed[1])
        if not scene.floors(x, z, y-.12, y+.12):
            return False
    return True


def box_hit(point, box, margin=0):
    return all(box['Min'][a]-margin <= point[a] <= box['Max'][a]+margin for a in range(3))


def volume_hit(position, radius, low, high, box):
    return all(position[a] + radius >= box['Min'][a]
               and position[a] - radius <= box['Max'][a] for a in (0, 2)) and (
        position[1] + high >= box['Min'][1] and position[1] + low <= box['Max'][1])


def segment_box_hit(start, end, box):
    """Closed segment/AABB slab test, including endpoints inside optional props.

    Bounds already union authored and measured furniture extents. Testing the
    solid volume also catches segments wholly inside a box, which a triangle
    boundary test would miss. Parallel and zero-length segments are supported.
    """
    enter, leave = 0.0, 1.0
    for axis in range(3):
        delta = end[axis] - start[axis]
        if abs(delta) < 1e-12:
            if not box['Min'][axis] <= start[axis] <= box['Max'][axis]:
                return False
            continue
        first = (box['Min'][axis] - start[axis]) / delta
        last = (box['Max'][axis] - start[axis]) / delta
        enter = max(enter, min(first, last))
        leave = min(leave, max(first, last))
        if enter > leave:
            return False
    return True


class Audit:
    def __init__(self, addons, reader, stock, repo):
        self.repo = Path(repo)
        self.reader = gen.Reader(reader)
        self.assets = gen.Assets(addons)
        self.stock_bytes = Path(stock).read_bytes()
        self.stock = {g.get('name'): g for g in ET.fromstring(self.stock_bytes).findall('group')}
        self.props = {}
        self.meshes = {}
        self.templates = {}
        self.boxes_bytes = interior_templates.BOXES_PATH.read_bytes()
        self.boxes = interior_templates.load_boxes(self.boxes_bytes)['Props']
        for path in sorted((self.repo/'mission/hollow-country/interiors/templates').glob('t-*.json')):
            doc = json.loads(path.read_bytes())
            interior_catalog.box(doc['Box'])
            # Expand optional-slot obstacles to the union of authored bounds and
            # independently measured native prop boxes (including origin offset).
            for slot in doc.get('PropSlots', []):
                entry = self.boxes.get(slot['Type'])
                if entry is None:
                    continue
                yaw, pitch, roll = slot['Orientation']
                if abs(pitch) > .001 or abs(roll) > .001:
                    raise ValueError('optional prop tilt unsupported: ' + doc['BuildingClass'])
                yaw = math.radians(yaw)
                corners = []
                for x in (entry['Min'][0], entry['Max'][0]):
                    for y in (entry['Min'][1], entry['Max'][1]):
                        for z in (entry['Min'][2], entry['Max'][2]):
                            corners.append([slot['Position'][0]+x*math.cos(yaw)+z*math.sin(yaw),
                                            slot['Position'][1]+y,
                                            slot['Position'][2]-x*math.sin(yaw)+z*math.cos(yaw)])
                slot['Bounds'] = {
                    'Min': [min(slot['Bounds']['Min'][a], min(c[a] for c in corners)) for a in range(3)],
                    'Max': [max(slot['Bounds']['Max'][a], max(c[a] for c in corners)) for a in range(3)]}
            self.templates.setdefault(doc['BuildingClass'], []).append((path, doc))
        self.scene_stats = Counter()

    def read_model(self, name):
        return self.reader.module.ODOL_File.read(io.BytesIO(self.assets.read(name)))

    def prop(self, name):
        if name not in self.props:
            model = self.read_model(name)
            visual = min((l for l in model.lods if l.resolution < 1000),
                         key=lambda l: (l.resolution, l.index), default=None)
            geometry = lod_for(model, GEOMETRY)
            # Other visual, memory and shadow LODs are irrelevant for props in
            # this audit; retaining every decoded LOD needlessly grows memory.
            model.lods = [l for l in (visual, geometry) if l is not None]
            self.props[name] = model
        return self.props[name]

    def scene(self, name, spec):
        stock = self.stock.get(name)
        if stock is None or loot.group_pin(stock) != spec['stock_sha256']:
            raise ValueError('stock pin mismatch: ' + name)
        model_name = pbo.normalize_path(pbo.resolve_field(self.assets.classes, name, 'model') or '')
        data = self.assets.read(model_name)
        if spec.get('building_model_sha256', gen.sha(data)) != gen.sha(data):
            raise ValueError('building model pin mismatch: ' + name)
        model = self.read_model(model_name)
        # Building vertices are already in the centred CE/model frame. Native
        # floor points independently match these raw vertices (e.g. 1W01 floor
        # -2.84871 m). Proxy furniture uses its own local mesh origin instead.
        # Adding the building bounding centre moves both walls and floors away
        # from the stock points. Keep it zero for every building LOD here.
        model.bounding_center = (0.0, 0.0, 0.0)
        geometry = lod_for(model, GEOMETRY)
        if geometry is None:
            raise ValueError('missing building geometry: ' + name)
        scene = Scene()
        scene.add(collision_triangles(model, geometry))
        footprint = Scene()
        footprint.add(collision_triangles(model, geometry))
        roadway = lod_for(model, ROADWAY)
        if roadway is not None:
            scene.add(collision_triangles(model, roadway))
            footprint.add(collision_triangles(model, roadway))
            self.scene_stats['buildings_with_roadway'] += 1
        visual = gen.Mesh(model)
        # Some installed tents have only proxy markers in the root visual LOD.
        # Their structural collision mesh still supplies real building bounds;
        # marker triangles must not become either bounds or support evidence.
        envelope = [tri for tri, _, _ in visual.triangles] or footprint.triangles
        bounds = ({'Min': [min(v[a] for tri in envelope for v in tri) for a in range(3)],
                   'Max': [max(v[a] for tri in envelope for v in tri) for a in range(3)]}
                  if envelope else None)
        self.scene_stats['buildings'] += 1
        memory = lod_for(model, MEMORY)
        self.scene_stats['memory_selections'] += len(memory.named_selections) if memory else 0
        self.scene_stats['buildings_without_memory'] += memory is None
        seen = set()
        for proxy, matrix in gen.stock_proxies(data, model):
            # This parser intentionally matches the generator's upright proxy
            # admission; reject other transforms rather than treating text as one.
            if (max(abs(matrix[3+i]-(1 if i == 1 else 0)) for i in range(3)) > .001
                    or any(abs(sum(v*v for v in axis)-1) > .001
                           for axis in (matrix[:3], matrix[6:9]))
                    or abs(dot(matrix[:3], matrix[6:9])) > .001):
                continue
            key = (proxy, tuple(round(v, 4) for v in matrix))
            if key in seen:
                continue
            seen.add(key)
            if proxy not in self.assets.members:
                self.scene_stats['unresolved_proxy_members'] += 1
                continue
            prop = self.prop(proxy)
            geom = lod_for(prop, GEOMETRY)
            if geom is None:
                # Visual fallback is conservative for blockers, never a claim
                # about engine collision. Include chairs/clutter as well as tops.
                geom = min((l for l in prop.lods if l.resolution < 1000),
                           key=lambda l: l.resolution, default=None)
                self.scene_stats['proxy_visual_fallbacks'] += 1
            if geom is not None:
                scene.add(collision_triangles(prop, geom, matrix))
                self.scene_stats['proxy_instances'] += 1
        floors = [model_point([float(v) for v in p.get('pos').split()])
                  for c in stock.findall('container') if 'floor' in c.get('name', '').lower()
                  for p in c.findall('point')]
        self.assets.cache.pop(model_name, None)
        return model_name, model, visual, scene, bounds, floors, footprint

    def check(self, point, source, context, templates, stop_on_refusal=False):
        # Dense generation can stop at a refusal. Admission always traverses
        # every check; the independent emitted-file audit collects all reasons.
        model_name, model, visual, scene, bounds, floors, footprint = context
        point = model_point(point)
        failures = []
        if bounds is None or not box_hit(point, bounds, .02):
            failures.append('outside_building_bounds')
        if not source:
            return failures + ['missing_support_evidence'], None
        local = source['local_point']
        if source['surface'] == 'baked-interior-ledge':
            support, matrix = visual, None
            expected = local
            if any(abs(v) > .000001 for v in source['model_center']):
                failures.append('building_frame_mismatch')
        else:
            support_name = source.get('support_model', source['model'])
            if support_name not in self.meshes:
                self.meshes[support_name] = gen.Mesh(self.prop(support_name))
            support, matrix = self.meshes[support_name], source['transform']
            expected = transform(local, matrix)
        if max(abs(point[a]-expected[a]) for a in range(3)) > .00002:
            failures.append('support_transform_mismatch')
        # Re-read actual triangles, never merely trust the embedded triangle.
        for dx, dz in ((0, 0), (.12, 0), (-.12, 0), (0, .12), (0, -.12)):
            if not any(abs(y-(local[1]-.005)) <= .025 and normal > .85
                       for y, normal, _, _ in support.hits(local[0]+dx, local[2]+dz)):
                failures.append('floating_or_edge_support')
                break
        # Cheap room evidence precedes the collision rays during dense scans.
        # Full audits still collect the same overlapping reasons below.
        nearby = [f for f in floors if math.hypot(f[0]-point[0], f[2]-point[2]) <= 6
                  and .25 <= point[1]-f[1] <= MAX_RISE+.20]
        if not nearby:
            failures.append('above_reach_or_no_floor_anchor')
        elif not any(abs(y-f[1]) <= .20 for f in nearby
                     for y in footprint.floors(point[0], point[2], point[1]-MAX_RISE-.20, point[1]-.25)):
            failures.append('outside_supported_room_footprint')
        if stop_on_refusal and failures:
            return sorted(set(failures)), None
        # Fixed loader box needs 50 cm of empty space at the centre and edges.
        if any(not scene.clear((point[0]+dx, point[1]+.025, point[2]+dz),
                               (point[0]+dx, point[1]+.525, point[2]+dz))
               for dx, dz in ((0, 0), (.12, 0), (-.12, 0), (0, .12), (0, -.12))):
            failures.append('under_furniture_or_ceiling')
        if stop_on_refusal and failures:
            return sorted(set(failures)), None
        if any(not scene.clear((point[0]-.12, point[1]+h, point[2]),
                               (point[0]+.12, point[1]+h, point[2]))
               or not scene.clear((point[0], point[1]+h, point[2]-.12),
                                  (point[0], point[1]+h, point[2]+.12))
               for h in (.06, .30, .50)):
            failures.append('wall_or_furniture_box_overlap')
        if stop_on_refusal and failures:
            return sorted(set(failures)), None
        # Optional runtime props can obstruct; they never provide support. Union
        # of all histories is deliberately conservative. Bounds are model frame.
        slots = [slot for _, doc in templates for slot in doc.get('PropSlots', [])]
        if any(volume_hit(point, .12, -.12, .50, slot['Bounds']) for slot in slots):
            failures.append('optional_prop_overlap')
        if failures:
            return sorted(set(failures)), None
        saw_stance, saw_sight = False, False
        for distance in (.50, .75, MAX_REACH):
            for angle in range(16):
                x = point[0]+distance*math.cos(angle*math.tau/16)
                z = point[2]+distance*math.sin(angle*math.tau/16)
                for y in scene.floors(x, z, point[1]-MAX_RISE, point[1]-.25):
                    if not any(abs(y-f[1]) <= .20 for f in nearby):
                        continue
                    stance = (x, y, z)
                    if not body_clear(scene, stance):
                        continue
                    if any(volume_hit(stance, RADIUS, .06, HEIGHT, slot['Bounds']) for slot in slots):
                        continue
                    saw_stance = True
                    target = (point[0], point[1]+.06, point[2])
                    eye = (x, y+1.5, z)
                    if (not scene.clear(eye, target)
                            or any(segment_box_hit(eye, target, slot['Bounds']) for slot in slots)):
                        continue
                    saw_sight = True
                    for seed in sorted(nearby, key=lambda f: math.hypot(f[0]-x, f[2]-z)):
                        if math.hypot(seed[0]-x, seed[2]-z) > 6:
                            continue
                        if approach_clear(scene, seed, stance, slots):
                            return sorted(set(failures)), {
                                'stance_model': [round(v, 5) for v in stance],
                                'floor_anchor_model': seed, 'rise_m': round(point[1]-y, 5)}
        failures.append('no_clear_standing_space' if not saw_stance else
                        'wall_or_furniture_occluded' if not saw_sight else 'no_clear_floor_approach')
        return sorted(set(failures)), None

    def run(self, fix=False):
        report = {'schema': 1, 'native_acceptance': 'pending', 'files': {}, 'failures': [],
                  'failure_counts': {}, 'stock_proto_sha256': gen.sha(self.stock_bytes),
                  'prop_boxes_sha256': gen.sha(self.boxes_bytes),
                  'optional_prop_checks': {
                      'bounds': 'union of authored slots and yaw-transformed measured native boxes; all histories',
                      'corridor': 'continuous standing-body AABB sweep plus sampled rays against solid bounds',
                      'sight': 'closed eye-to-item segment against solid bounds',
                      'building_classes': 0, 'slots': 0},
                  'limits': {'max_rise_m': MAX_RISE, 'max_horizontal_reach_m': MAX_REACH,
                             'standing_height_m': HEIGHT, 'body_radius_m': RADIUS}}
        counts = Counter()
        optional_classes = set()
        for path in sorted((self.repo / loot.POINTS_DIR).glob('additions*.json')):
            raw = path.read_bytes()
            doc = loot.parse_overlay(raw)
            before = sum(len(c['points']) for s in doc['groups'].values() for c in s['containers'].values())
            rejected, checked = 0, 0
            for name, spec in list(doc['groups'].items()):
                container = spec['containers'].get('lootHCSurface')
                if container is None:
                    continue
                print('audit ' + name, file=sys.stderr, flush=True)
                context = self.scene(name, spec)
                if name not in optional_classes:
                    slots = [slot for _, template in self.templates.get(name, [])
                             for slot in template.get('PropSlots', [])]
                    if slots:
                        optional_classes.add(name)
                        report['optional_prop_checks']['slots'] += len(slots)
                # A bad source pin refuses the audit rather than deleting data
                # based on a different installed build.
                for source in spec.get('surface_sources', []):
                    member = source.get('support_model', source['model'])
                    pin = doc.get('sources', {}).get('model_surfaces', {}).get(member, {}).get('sha256')
                    if source['surface'] != 'baked-interior-ledge' and (
                            not pin or gen.sha(self.assets.read(member)) != pin):
                        raise ValueError('support model pin mismatch: ' + name)
                sources = spec.get('surface_sources', [])
                if sources and len(sources) != len(container['points']):
                    raise ValueError('surface evidence count mismatch: ' + name)
                collision = spec.get('collision_support', {}).get('lootHCSurface')
                if collision is not None and len(collision) != len(container['points']):
                    raise ValueError('collision evidence count mismatch: ' + name)
                keep, evidence, collision_evidence = [], [], []
                for index, point in enumerate(container['points']):
                    source = sources[index] if sources else None
                    failures, witness = self.check(point, source, context, self.templates.get(name, []))
                    checked += 1
                    if failures:
                        rejected += 1
                        counts.update(failures)
                        report['failures'].append({'file': path.name, 'group': name, 'index': index,
                                                   'point': point, 'reasons': failures})
                    else:
                        keep.append(point)
                        evidence.append(source)
                        if collision is not None:
                            collision_evidence.append(collision[index])
                if fix:
                    if keep:
                        container['points'] = keep
                        container['lootmax'] = loot.added_lootmax(len(keep))
                        spec['surface_sources'] = evidence
                        if collision is not None:
                            spec['collision_support']['lootHCSurface'] = collision_evidence
                    else:
                        del spec['containers']['lootHCSurface']
                        spec.pop('surface_sources', None)
                        spec.get('collision_support', {}).pop('lootHCSurface', None)
                    if not spec['containers']:
                        del doc['groups'][name]
            report['files'][path.name] = {'before_points': before, 'shelf_checked': checked,
                                         'refused_points': rejected, 'after_points': before-rejected,
                                         'input_sha256': gen.sha(raw)}
            if fix and rejected:
                doc['sources']['reach_audit'] = {
                    'method': 'loot_reach_audit static geometry, support and conservative floor approach; native pending',
                    'removed_points': rejected, 'prior_sha256': gen.sha(raw),
                    'max_rise_m': MAX_RISE, 'max_horizontal_reach_m': MAX_REACH,
                    'failure_counts': dict(sorted(Counter(reason
                        for row in report['failures'] if row['file'] == path.name
                        for reason in row['reasons']).items())),
                    'refused_groups': dict(sorted(Counter(row['group']
                        for row in report['failures'] if row['file'] == path.name).items()))}
                encoded = (json.dumps(doc, sort_keys=True, indent=2)+'\n').encode()
                loot.parse_overlay(encoded)
                path.write_bytes(encoded)
        report['failure_counts'] = dict(sorted(counts.items()))
        report['optional_prop_checks']['building_classes'] = len(optional_classes)
        report['scene_counts'] = dict(sorted(self.scene_stats.items()))
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--addons', type=Path, required=True)
    parser.add_argument('--reader', type=Path, required=True, help='generator hash-pinned external reader directory')
    parser.add_argument('--stock-proto', type=Path, required=True, help='unmodified pre-boost mapgroupproto.xml')
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--report', type=Path, help='optional local JSON diagnostic (never an asset dump)')
    parser.add_argument('--fix', action='store_true', help='drop refused shelf points; never moves unsupported points')
    args = parser.parse_args()
    result = Audit(args.addons, args.reader, args.stock_proto, args.repo).run(args.fix)
    if args.report:
        args.report.write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'failures'}, sort_keys=True, indent=2))
    # A fix reports its original failures; a fresh read-only audit must pass.
    return 1 if result['failures'] and not args.fix else 0


if __name__ == '__main__':
    raise SystemExit(main())
