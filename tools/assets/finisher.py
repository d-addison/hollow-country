"""Deterministic neutral.v1 -> canonical mlod.Asset, without native tools.

Welds preserve UV seams (UVs are per corner), remap named selections, discard
collapsed/zero-area triangles, orient connected surfaces and emit flat normals by default.
Optional face smooth booleans and mesh sharp_edges preserve authored shading.
Physical visual meshes must be closed, orientable 2-manifolds. Each component's
volume/area thickness proxy must pass: this is a conservative authoring guard,
not a proof of local wall thickness or engine collision validity.

Geometry is a bounded set of explicit axis-aligned box primitives, each a convex
hull and component selection. If omitted, one enclosing box is generated. This
is deliberately conservative collision; no decomposition or CoACD. Proxies
remain refused by mlod until native P0-6. UV/culling convention remains unverified.
"""
from collections import defaultdict, deque
from dataclasses import replace
import itertools
import math

from tools.assets import mlod
from tools.assets.ops_runner import integer, name, number, vector

MAX_WORK = 2_000_000
MAX_MESH = 60000


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def triangle_normal(a, b, c):
    return cross(sub(b, a), sub(c, a))


def _indices(values, length):
    if (not isinstance(values, (tuple, list)) or len(values) > MAX_MESH
            or any(type(i) is not int or not 0 <= i < length for i in values)
            or len(set(values)) != len(values)):
        raise ValueError('neutral.indices')
    return values


def _weld(vertices, distance):
    cells, output, remap = defaultdict(list), [], []
    work = 0
    for position in vertices:
        cell = tuple(math.floor(v / distance) for v in position)
        candidates = []
        for offset in itertools.product((-1, 0, 1), repeat=3):
            candidates.extend(cells[tuple(a + b for a, b in zip(cell, offset))])
        chosen = None
        for index in sorted(candidates):
            work += 1
            if work > MAX_WORK:
                raise ValueError('finish.weld_work_limit')
            if math.dist(output[index], position) <= distance:
                chosen = index
                break
        if chosen is None:
            chosen = len(output)
            output.append(position)
            cells[cell].append(chosen)
        remap.append(chosen)
    return output, remap


def clean(mesh, *, merge_distance=1e-6, min_thickness=0.001, closed=True):
    number(merge_distance, 1e-9, 0.1)
    number(min_thickness, 1e-9, 100)
    if (not isinstance(mesh, dict) or not
            {'schema', 'vertices', 'faces', 'selections', 'points', 'proxies'} <= set(mesh)
            or set(mesh) - {'schema', 'vertices', 'faces', 'selections', 'points', 'proxies', 'sharp_edges'}
            or mesh['schema'] != 'neutral.v1'):
        raise ValueError('neutral.schema')
    if mesh['proxies']:
        raise ValueError('finish.proxy_unverified_until_P0_6')
    if (not isinstance(mesh['vertices'], list) or not 1 <= len(mesh['vertices']) <= MAX_MESH
            or not isinstance(mesh['faces'], list) or not 1 <= len(mesh['faces']) <= MAX_MESH):
        raise ValueError('neutral.mesh_limit')
    raw = [vector(v) for v in mesh['vertices']]
    positions, remap = _weld(raw, merge_distance)
    sharp_raw = mesh.get('sharp_edges', [])
    if not isinstance(sharp_raw, (list, tuple)) or len(sharp_raw) > MAX_MESH:
        raise ValueError('neutral.sharp_edges')
    sharp = set()
    for edge in sharp_raw:
        if not isinstance(edge, (list, tuple)) or len(edge) != 2:
            raise ValueError('neutral.sharp_edges')
        _indices(edge, len(raw))
        a, b = (remap[i] for i in edge)
        if a != b:
            sharp.add(tuple(sorted((a, b))))
    faces, face_map, smooth = [], {}, []
    for index, face in enumerate(mesh['faces']):
        if (not isinstance(face, dict) or not {'vertices', 'uv', 'texture', 'material'} <= set(face)
                or set(face) - {'vertices', 'uv', 'texture', 'material', 'smooth'}
                or type(face.get('smooth', False)) is not bool
                or not 3 <= len(face['vertices']) <= 4):
            raise ValueError('neutral.face')
        corners = face['vertices']
        if any(type(i) is not int or not 0 <= i < len(raw) for i in corners):
            raise ValueError('neutral.indices')
        if not isinstance(face['uv'], list) or len(face['uv']) != len(corners):
            raise ValueError('neutral.uv')
        uv = []
        for pair in face['uv']:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError('neutral.uv')
            uv.append(tuple(number(v) for v in pair))
        mlod.virtual_path(face['texture'])
        mlod.virtual_path(face['material'])
        face_map[index] = []
        # Always triangulate: makes area, normals and distance checks unambiguous.
        for tri in ((0, 1, 2), (0, 2, 3)) if len(corners) == 4 else ((0, 1, 2),):
            ids = tuple(remap[corners[i]] for i in tri)
            if len(set(ids)) < 3:
                continue
            normal = triangle_normal(*(positions[i] for i in ids))
            if math.hypot(*normal) <= merge_distance**2:
                continue
            face_map[index].append(len(faces))
            smooth.append(face.get('smooth', False))
            faces.append(mlod.Face(ids, tuple(uv[i] for i in tri),
                                   face['texture'], face['material']))
    if not faces:
        raise ValueError('finish.empty_mesh')
    # Orphan removal also removes vertices left by discarded faces.
    used = sorted({i for face in faces for i in face.vertices})
    compact = {old: new for new, old in enumerate(used)}
    positions = [positions[i] for i in used]
    faces = [replace(f, vertices=tuple(compact[i] for i in f.vertices)) for f in faces]
    sharp = {tuple(sorted((compact[a], compact[b]))) for a, b in sharp
             if a in compact and b in compact}
    edges = defaultdict(list)
    for fi, face in enumerate(faces):
        for a, b in zip(face.vertices, face.vertices[1:] + face.vertices[:1]):
            edges[tuple(sorted((a, b)))].append((fi, a < b))
    if any(len(v) > 2 or (closed and len(v) != 2) for v in edges.values()):
        raise ValueError('finish.nonmanifold_or_open')
    adjacency = defaultdict(list)
    for members in edges.values():
        if len(members) == 2:
            (a, da), (b, db) = members
            adjacency[a].append((b, da == db))
            adjacency[b].append((a, da == db))
    if closed:
        # Edge incidence alone admits a pinched vertex joining two closed shells.
        # A manifold vertex has one connected fan of incident faces.
        incident = defaultdict(set)
        links = defaultdict(list)
        for fi, face in enumerate(faces):
            for vertex in face.vertices:
                incident[vertex].add(fi)
        for edge, members in edges.items():
            a, b = (m[0] for m in members)
            for vertex in edge:
                links[(vertex, a)].append(b)
                links[(vertex, b)].append(a)
        for vertex, members in incident.items():
            seed = next(iter(members))
            seen, queue = {seed}, [seed]
            while queue:
                for neighbour in links[(vertex, queue.pop())]:
                    if neighbour not in seen:
                        seen.add(neighbour)
                        queue.append(neighbour)
            if seen != members:
                raise ValueError('finish.nonmanifold_vertex')
    flips, components = {}, []
    for seed in range(len(faces)):
        if seed in flips:
            continue
        flips[seed], component, queue = False, [], deque([seed])
        while queue:
            index = queue.popleft()
            component.append(index)
            for neighbour, invert in adjacency[index]:
                value = flips[index] ^ invert
                if neighbour in flips and flips[neighbour] != value:
                    raise ValueError('finish.nonorientable')
                if neighbour not in flips:
                    flips[neighbour] = value
                    queue.append(neighbour)
        components.append(component)
    def flip(index):
        faces[index] = replace(faces[index], vertices=faces[index].vertices[::-1],
                               uv=faces[index].uv[::-1])
    for index, value in flips.items():
        if value:
            flip(index)
    for component in components:
        volume, area = 0.0, 0.0
        # Use a local origin to avoid catastrophic cancellation far from origin.
        origin = positions[faces[component[0]].vertices[0]]
        for index in component:
            a, b, c = [sub(positions[i], origin) for i in faces[index].vertices]
            volume += dot(a, cross(b, c)) / 6
            area += math.hypot(*triangle_normal(a, b, c)) / 2
        if closed and 2 * abs(volume) / area < min_thickness:
            raise ValueError('finish.thin_shell')
        if closed and volume < 0:
            for index in component:
                flip(index)
    # Smooth only across shared, non-sharp edges between smooth faces. Per-corner
    # angle weighting avoids bias from triangulating a quad's diagonal.
    face_normals = []
    for face in faces:
        normal = triangle_normal(*(positions[i] for i in face.vertices))
        length = math.hypot(*normal)
        face_normals.append(tuple(v / length for v in normal))
    fans = defaultdict(list)
    for edge, members in edges.items():
        if edge not in sharp and len(members) == 2:
            a, b = (m[0] for m in members)
            if smooth[a] and smooth[b]:
                for vertex in edge:
                    fans[(vertex, a)].append(b)
                    fans[(vertex, b)].append(a)
    corner_normals, visited = {}, set()
    work = 0
    for fi, face in enumerate(faces):
        if not smooth[fi]:
            continue
        for vertex in face.vertices:
            if (vertex, fi) in visited:
                continue
            queue, group, total = [fi], [], [0.0]*3
            visited.add((vertex, fi))
            while queue:
                current = queue.pop()
                group.append(current)
                work += 1
                if work > MAX_WORK:
                    raise ValueError('finish.smoothing_work_limit')
                ids = faces[current].vertices
                at = ids.index(vertex)
                u = sub(positions[ids[(at-1) % 3]], positions[vertex])
                v = sub(positions[ids[(at+1) % 3]], positions[vertex])
                angle = math.acos(max(-1, min(1, dot(u, v)/(math.hypot(*u)*math.hypot(*v)))))
                for axis in range(3):
                    total[axis] += face_normals[current][axis] * angle
                for neighbour in fans[(vertex, current)]:
                    if (vertex, neighbour) not in visited:
                        visited.add((vertex, neighbour))
                        queue.append(neighbour)
            length = math.hypot(*total)
            if length <= 1e-12:
                raise ValueError('finish.smoothing_zero_normal')
            normal = tuple(v/length for v in total)
            for member in group:
                corner_normals[(vertex, member)] = normal
    for fi, face in enumerate(faces):
        faces[fi] = replace(face, normals=tuple(corner_normals.get((v, fi), face_normals[fi])
                                              for v in face.vertices))
    selections = {}
    if not isinstance(mesh['selections'], dict) or len(mesh['selections']) > 512:
        raise ValueError('neutral.selection_limit')
    for label, selection in sorted(mesh['selections'].items()):
        name(label)
        if not isinstance(selection, dict) or set(selection) != {'vertices', 'faces'}:
            raise ValueError('neutral.selection')
        vi = _indices(selection['vertices'], len(raw))
        fi = _indices(selection['faces'], len(mesh['faces']))
        selections[label] = mlod.Selection(
            tuple(sorted({compact[remap[i]] for i in vi if remap[i] in compact})),
            tuple(sorted({j for i in fi for j in face_map[i]})))
    return mlod.LOD(tuple(mlod.Vertex(p) for p in positions), tuple(faces), selections,
                    sharp_edges=tuple(sorted(sharp & edges.keys())))


def _point_triangle(p, a, b, c):
    """Euclidean distance to a triangle, including edges and vertices."""
    ab, ac, ap = sub(b, a), sub(c, a), sub(p, a)
    normal = cross(ab, ac)
    n2 = dot(normal, normal)
    d00, d01, d11 = dot(ab, ab), dot(ab, ac), dot(ac, ac)
    denom = d00*d11 - d01*d01
    # A zero-area (collapsed) triangle has no plane: fall through to its edges
    # rather than dividing by zero. clean() never emits one; hausdorff() is public.
    if n2 > 0 and denom > 0:
        projected = tuple(p[i] - normal[i] * dot(ap, normal) / n2 for i in range(3))
        v = sub(projected, a)
        u = (d11*dot(v, ab) - d01*dot(v, ac)) / denom
        w = (d00*dot(v, ac) - d01*dot(v, ab)) / denom
        if u >= 0 and w >= 0 and u + w <= 1:
            return math.dist(p, projected)
    def edge(x, y):
        direction = sub(y, x)
        length = dot(direction, direction)
        if length == 0:
            return math.dist(p, x)
        fraction = max(0, min(1, dot(sub(p, x), direction) / length))
        return math.dist(p, tuple(x[i] + fraction*direction[i] for i in range(3)))
    return min(edge(a, b), edge(b, c), edge(c, a))


def hausdorff(a, b, *, subdivisions=2):
    """Bounded, symmetric surface distance interval in metres.

    Sample vertices/centroids of subdivided triangles. Distance to a surface is
    1-Lipschitz, so max sample distance + largest covering radius bounds the true
    Hausdorff distance. A tolerance gate uses upper, never the optimistic lower.
    Refuse oversized work rather than silently dropping samples.
    """
    integer(subdivisions, 0, 4)
    def triangles(lod):
        return [tuple(lod.vertices[i].position for i in face.vertices) for face in lod.faces]
    ta, tb = triangles(a), triangles(b)
    if not ta or not tb:
        raise ValueError('finish.distance_empty')
    if any(len(t) != 3 for t in ta + tb):
        raise ValueError('finish.distance_requires_triangles')
    if 2 * len(ta) * len(tb) * (4**subdivisions) * 4 > MAX_WORK:
        raise ValueError('finish.distance_work_limit')
    # Identical surfaces have exactly zero distance, regardless of sampling radius.
    if sorted(tuple(sorted(t)) for t in ta) == sorted(tuple(sorted(t)) for t in tb):
        return {'lower': 0.0, 'upper': 0.0, 'method': 'surface_interval'}
    def directed(source, target):
        sampled = source
        for _ in range(subdivisions):
            refined = []
            for x, y, z in sampled:
                xy, yz, zx = [tuple((v[i]+w[i])/2 for i in range(3))
                              for v, w in ((x, y), (y, z), (z, x))]
                refined.extend(((x, xy, zx), (xy, y, yz), (zx, yz, z), (xy, yz, zx)))
            sampled = refined
        lower, upper = 0.0, 0.0
        for triangle in sampled:
            center = tuple(sum(v[i] for v in triangle)/3 for i in range(3))
            distance = min(_point_triangle(center, *t) for t in target)
            radius = max(math.dist(center, v) for v in triangle)
            lower = max(lower, distance, *(min(_point_triangle(v, *t) for t in target)
                                          for v in triangle))
            upper = max(upper, distance + radius)
        return lower, upper
    ab, ba = directed(ta, tb), directed(tb, ta)
    return {'lower': max(ab[0], ba[0]), 'upper': max(ab[1], ba[1]),
            'method': 'surface_interval'}


def box_hulls(primitives, *, mass):
    number(mass, 0.000001, 1e9)
    if not isinstance(primitives, list) or not 1 <= len(primitives) <= 32:
        raise ValueError('finish.geometry_primitive_limit')
    positions, faces, selections, volumes = [], [], {}, []
    for index, primitive in enumerate(primitives):
        if not isinstance(primitive, dict) or set(primitive) != {'kind', 'center', 'size'} or primitive['kind'] != 'box':
            raise ValueError('finish.geometry_box_required')
        center, size = vector(primitive['center']), vector(primitive['size'], 0.000001, 1000)
        start, first_face = len(positions), len(faces)
        positions.extend(tuple(center[i] + sign[i]*size[i]/2 for i in range(3))
                         for sign in itertools.product((-1, 1), repeat=3))
        volumes.append(math.prod(size))
        # Each face is outward CCW; clean triangulates and verifies winding.
        for quad in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
                     (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            faces.append({'vertices': [start+i for i in quad], 'uv': [[0, 0]] * 4,
                          'texture': '', 'material': ''})
        selections[f'component{index+1:02d}'] = {
            'vertices': list(range(start, len(positions))),
            'faces': list(range(first_face, len(faces)))}
    # Separate touching primitive hull vertices must not weld across components.
    # Build each hull separately then combine, preserving convex components.
    lods = []
    for index in range(len(primitives)):
        selected = selections[f'component{index+1:02d}']
        start = selected['vertices'][0]
        local_faces = [{**faces[i], 'vertices': [v-start for v in faces[i]['vertices']]}
                       for i in selected['faces']]
        lods.append(clean({'schema': 'neutral.v1', 'vertices': positions[start:start+8],
                           'faces': local_faces, 'selections': {}, 'points': {}, 'proxies': []},
                          merge_distance=1e-9, min_thickness=1e-9))
    vertices, result_faces, result_selections, masses = [], [], {}, []
    for index, lod in enumerate(lods):
        vi, fi = len(vertices), len(result_faces)
        vertices.extend(lod.vertices)
        result_faces.extend(replace(f, vertices=tuple(i+vi for i in f.vertices)) for f in lod.faces)
        result_selections[f'component{index+1:02d}'] = mlod.Selection(
            tuple(range(vi, len(vertices))), tuple(range(fi, len(result_faces))))
        masses.extend([mass * volumes[index] / sum(volumes) / len(lod.vertices)] * len(lod.vertices))
    return mlod.LOD(tuple(vertices), tuple(result_faces), result_selections,
                    {'autocenter': '0'}, tuple(masses))


def finish(meshes, *, budgets, geometry_primitives=None, mass=10, physical=True,
           merge_distance=1e-6, min_thickness=0.001, lod_distance=0.05,
           view_geometry_primitives=None, fire_geometry_primitives=None, shadow_mesh=None):
    """meshes/budgets map visual resolutions to neutral meshes/triangle limits.

    View/Fire use the same bounded convex-box schema as Geometry and reuse it
    when omitted. Shadow defaults to the lowest-detail visual mesh, always
    checked closed and triangulated, including nonphysical assets.
    No automatic simplification: supply authored lower-detail recipes. Lower
    LODs must satisfy both their triangle budget and a conservative surface
    Hausdorff upper bound against the highest detail mesh.
    """
    if not isinstance(meshes, dict) or not 1 <= len(meshes) <= 16 or set(meshes) != set(budgets):
        raise ValueError('finish.lods_or_budgets')
    if type(physical) is not bool:
        raise ValueError('finish.physical_boolean')
    number(lod_distance, 0, 10000)
    lods = {}
    for resolution, mesh in sorted(meshes.items()):
        number(resolution, 0, 999)
        budget = integer(budgets[resolution], 1, mlod.MAX_FACES)
        lod = clean(mesh, merge_distance=merge_distance, min_thickness=min_thickness, closed=physical)
        if len(lod.faces) > budget:
            raise ValueError('finish.triangle_budget')
        lods[resolution] = lod
    first = lods[min(lods)]
    for resolution, lod in lods.items():
        if resolution != min(lods) and hausdorff(first, lod)['upper'] > lod_distance:
            raise ValueError('finish.lod_distance')
    try:
        shadow = clean(meshes[max(meshes)] if shadow_mesh is None else shadow_mesh,
                       merge_distance=merge_distance, min_thickness=min_thickness, closed=True)
    except ValueError as exc:
        raise ValueError('finish.shadow.' + str(exc)) from None
    lods[mlod.SHADOW] = replace(shadow, faces=tuple(replace(f, texture='', material='')
                                                 for f in shadow.faces), selections={})
    points = meshes[min(meshes)]['points']
    if not isinstance(points, dict) or len(points) > 512:
        raise ValueError('neutral.points')
    if any(mesh['points'] != points for mesh in meshes.values()):
        raise ValueError('finish.inconsistent_memory_points')
    if points:
        memory_vertices, selections = [], {}
        for label, position in sorted(points.items()):
            name(label)
            selections[label] = mlod.Selection((len(memory_vertices),))
            memory_vertices.append(mlod.Vertex(vector(position)))
        lods[mlod.MEMORY] = mlod.LOD(tuple(memory_vertices), selections=selections)
    if physical:
        if geometry_primitives is None:
            low = tuple(min(v.position[i] for v in first.vertices) for i in range(3))
            high = tuple(max(v.position[i] for v in first.vertices) for i in range(3))
            geometry_primitives = [{'kind': 'box', 'center': [(a+b)/2 for a, b in zip(low, high)],
                                    'size': [b-a for a, b in zip(low, high)]}]
        lods[mlod.GEOMETRY] = box_hulls(geometry_primitives, mass=mass)
        for resolution, primitives in ((mlod.VIEW_GEOMETRY, view_geometry_primitives),
                                       (mlod.FIRE_GEOMETRY, fire_geometry_primitives)):
            lods[resolution] = (lods[mlod.GEOMETRY] if primitives is None
                                else box_hulls(primitives, mass=mass))
    asset = mlod.Asset(lods, physical)
    mlod.validate(asset)
    return asset


def selftest():
    lod = box_hulls([{'kind': 'box', 'center': [0, 0, 0], 'size': [1, 1, 1]}], mass=10)
    asset = mlod.Asset({0: replace(lod, masses=()), mlod.GEOMETRY: lod})
    mlod.read_mlod(mlod.write_mlod(asset))
    assert hausdorff(lod, lod)['upper'] == 0


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selftest', action='store_true', required=True)
    parser.parse_args()
    selftest()
    print('{"valid": true}')
