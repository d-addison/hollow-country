"""Offline authored Asset IR/MLOD checks; never establishes native acceptance.

JSON IR uses mlod.Asset's dataclass fields, with numeric-string LOD keys.
Optional skin_weights maps LOD keys to one {bone: weight} record per vertex.
The codec cannot encode skin weights yet: supply them in IR for skinned checks.
--sources is a JSON list of virtual paths inventoried from installed DZ content
and authored source files; no filesystem guessing or runtime path construction.
Config inputs are standalone text (expand includes/macros before linting).

Extensions (all offline, none establish native acceptance):
  mesh  HC-A011/A012: degenerate triangles, materials per visual LOD (< 4),
        monotonic LOD reduction (<= 0.65x per step). Optional policy keys:
        triangles_only, closed_visual, expected_bbox ([min, max]) with
        bbox_tolerance (default 5 mm), uv_overlap (no UV-overlapping faces).
        LOD deviation (Hausdorff) is gated where LODs are made: finisher.finish.
  tex   HC-A013/A014: textures maps virtual path -> .paa bytes (header magic,
        power-of-two size, _nohq is DXT5, own paths shipped, none unreferenced);
        rvmats maps virtual path -> rvmat text whose stage texture paths must
        resolve (engine procedural #(...) expressions are not paths).
  rig   HC-A015: rig = {bones, skeleton, poses}: weight groups must be in the
        bones allowlist; synthetic poses over skeleton ({bone: {parent, pivot}},
        poses {name: {bone: [axis, degrees]}}) bound edge stretch to 2.5x.
Texel density needs recipe data and is not checked here.
"""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re

from tools.assets import mlod

RULES = {
    'HC-A001': 'Geometry LOD present',
    'HC-A002': 'Geometry components closed and consistently wound',
    'HC-A003': 'Geometry components convex and named',
    'HC-A004': 'Geometry has positive per-vertex #Mass#',
    'HC-A005': 'Referenced named selections exist',
    'HC-A006': 'DamageZones/hit selections match Fire Geometry',
    'HC-A007': 'Referenced memory points exist in Memory LOD',
    'HC-A008': 'Texture/material virtual paths allowed and inventoried',
    'HC-A009': 'Skin weights have at most four bones and sum to one',
    'HC-A010': 'Supported IR and standalone text config',
    'HC-A011': 'Visual meshes: finite non-degenerate triangles, policy topology and bounds',
    'HC-A012': 'Visual LODs: fewer than four materials and monotonic reduction',
    'HC-A013': 'Textures: .paa header, power-of-two size, suffix format, referenced and shipped',
    'HC-A014': 'Material stage textures resolve to allowed inventoried paths',
    'HC-A015': 'Rig: allowlisted bones and bounded synthetic-pose edge stretch',
}

MIN_AREA = 1e-12
LOD_RATIO = 0.65
MAX_MATERIALS = 3
BBOX_TOLERANCE = 0.005
MAX_EDGE_STRETCH = 2.5
MAX_PAA_TAGGS = 64
MAX_UV_FACES = 2000
PAA_FORMATS = {b'\x01\xff': 'DXT1', b'\x05\xff': 'DXT5'}
PROCEDURAL = re.compile(r'#\((?:argb|ai|rgb),\d{1,4},\d{1,4},\d\)(?:color|fresnel)\([A-Za-z0-9.,+\- ]*\)')
POLICY_KEYS = {'triangles_only', 'closed_visual', 'expected_bbox', 'bbox_tolerance', 'uv_overlap'}
RIG_KEYS = {'bones', 'skeleton', 'poses'}


def asset_from_ir(document):
    lods = {}
    for resolution, row in document['lods'].items():
        lods[float(resolution)] = mlod.LOD(
            vertices=tuple(mlod.Vertex(tuple(v['position']), v.get('flags', 0)) for v in row.get('vertices', [])),
            faces=tuple(mlod.Face(tuple(f['vertices']), tuple(tuple(uv) for uv in f['uv']),
                                  f.get('texture', ''), f.get('material', ''),
                                  tuple(tuple(n) for n in f.get('normals', [])), f.get('flags', 0))
                        for f in row.get('faces', [])),
            selections={n: mlod.Selection(tuple(s.get('vertices', [])), tuple(s.get('faces', [])))
                        for n, s in row.get('selections', {}).items()},
            properties=row.get('properties', {}), masses=tuple(row.get('masses', [])))
    return mlod.Asset(lods, document.get('physical', True))


def _fields(text):
    """Parse nested config fields, retaining class ancestry and refusing macros.

    Intentionally small text subset: classes, forward declarations, scalar and
    array assignments. Unknown syntax fails closed rather than hiding references.
    """
    tokens = re.findall(r'"(?:""|[^"\n])*"|//[^\n]*|/\*.*?\*/|[A-Za-z_]\w*|[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|\S', text, re.S)
    tokens = [t for t in tokens if not t.startswith(('//', '/*'))]
    at = 0
    rows = []

    def body(path, closing=False):
        nonlocal at
        while at < len(tokens):
            token = tokens[at]
            at += 1
            if token == '}' and closing:
                return
            if token == ';':
                continue
            if token == 'class':
                name = tokens[at]
                at += 1
                if tokens[at] == ':':
                    at += 2
                if tokens[at] == ';':
                    at += 1
                    continue
                if tokens[at] != '{':
                    raise ValueError('class body expected')
                at += 1
                body(path + (name,), True)
                continue
            if not re.fullmatch(r'[A-Za-z_]\w*', token):
                raise ValueError('unsupported config syntax')
            if tokens[at:at+2] == ['[', ']']:
                at += 2
            if tokens[at] != '=':
                raise ValueError('assignment expected')
            at += 1
            values = []
            depth = 0
            while at < len(tokens):
                value = tokens[at]
                at += 1
                if value == ';' and depth == 0:
                    break
                if value == '{':
                    depth += 1
                elif value == '}':
                    depth -= 1
                elif value.startswith('"'):
                    values.append(value[1:-1].replace('""', '"'))
                elif value != ',' and not re.fullmatch(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?', value):
                    raise ValueError('unresolved config expression')
                if depth < 0:
                    raise ValueError('unbalanced array')
            else:
                raise ValueError('unterminated assignment')
            rows.append((path, token.casefold(), values))
        if closing:
            raise ValueError('unclosed class')
    body(())
    return rows


def _components(lod):
    remaining = set(range(len(lod.faces)))
    by_vertex = defaultdict(set)
    for index, face in enumerate(lod.faces):
        for vertex in face.vertices:
            by_vertex[vertex].add(index)
    while remaining:
        pending = [min(remaining)]
        component = set()
        while pending:
            index = pending.pop()
            if index in component:
                continue
            component.add(index)
            remaining.discard(index)
            for vertex in lod.faces[index].vertices:
                pending.extend(by_vertex[vertex] - component)
        yield component


def paa_info(data):
    """Return (format, width, height) of a .paa's first mip; ValueError if malformed."""
    if not isinstance(data, (bytes, bytearray)) or len(data) < 4 or bytes(data[:2]) not in PAA_FORMATS:
        raise ValueError('paa magic')
    offset = 2
    for _ in range(MAX_PAA_TAGGS + 1):
        if bytes(data[offset:offset + 4]) != b'GGAT':
            break
        if offset + 12 > len(data):
            raise ValueError('paa tagg')
        offset += 12 + int.from_bytes(data[offset + 8:offset + 12], 'little')
    else:
        raise ValueError('paa tagg limit')
    if offset + 2 > len(data):
        raise ValueError('paa palette')
    offset += 2 + 3 * int.from_bytes(data[offset:offset + 2], 'little')
    if offset + 7 > len(data):
        raise ValueError('paa mip')
    width = int.from_bytes(data[offset:offset + 2], 'little') & 0x7fff
    height = int.from_bytes(data[offset + 2:offset + 4], 'little') & 0x7fff
    return PAA_FORMATS[bytes(data[:2])], width, height


def _triangles(face):
    return [(face.vertices[0], face.vertices[i], face.vertices[i + 1]) for i in range(1, len(face.vertices) - 1)]


def _area2(lod, tri):
    a, b, c = [lod.vertices[i].position for i in tri]
    u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
    return math.hypot(u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])


def _tri_count(lod):
    return sum(len(f.vertices) - 2 for f in lod.faces)


def _uv_overlap(lod):
    """True if two triangles' UV interiors intersect (touching is allowed)."""
    tris = [[face.uv[0], face.uv[i], face.uv[i + 1]] for face in lod.faces for i in range(1, len(face.uv) - 1)]
    if len(tris) > MAX_UV_FACES:
        raise ValueError('uv work limit')

    def separated(a, b):
        for poly in (a, b):
            for i in range(3):
                p, q = poly[i], poly[(i + 1) % 3]
                axis = (q[1] - p[1], p[0] - q[0])
                pa = [axis[0]*v[0] + axis[1]*v[1] for v in a]
                pb = [axis[0]*v[0] + axis[1]*v[1] for v in b]
                if max(pa) <= min(pb) + 1e-9 or max(pb) <= min(pa) + 1e-9:
                    return True
        return False
    boxes = [(min(v[0] for v in t), max(v[0] for v in t), min(v[1] for v in t), max(v[1] for v in t)) for t in tris]
    for i in range(len(tris)):
        for j in range(i + 1, len(tris)):
            x, y = boxes[i], boxes[j]
            if x[1] <= y[0] or y[1] <= x[0] or x[3] <= y[2] or y[3] <= x[2]:
                continue
            area = sum(abs((t[1][0]-t[0][0])*(t[2][1]-t[0][1])-(t[1][1]-t[0][1])*(t[2][0]-t[0][0])) for t in (tris[i], tris[j]))
            if area > 0 and not separated(tris[i], tris[j]):
                return True
    return False


def _mesh_checks(asset, policy, fail):
    unknown = set(policy) - POLICY_KEYS
    if unknown:
        fail('HC-A010', 'unsupported mesh policy key')
        return
    visual = sorted((r, lod) for r, lod in asset.lods.items() if r < 1000 and lod.faces)
    positions = []
    for resolution, lod in visual:
        if policy.get('triangles_only') and any(len(f.vertices) != 3 for f in lod.faces):
            fail('HC-A011', 'visual LOD has non-triangle faces')
        if any(_area2(lod, t) / 2 < MIN_AREA for f in lod.faces for t in _triangles(f)):
            fail('HC-A011', 'degenerate visual triangle')
        if asset.physical and policy.get('closed_visual'):
            edges = Counter(e for f in lod.faces for e in zip(f.vertices, f.vertices[1:] + f.vertices[:1]))
            if any(count != 1 or edges[(b, a)] != 1 for (a, b), count in edges.items()):
                fail('HC-A011', 'open/nonmanifold or inconsistently wound visual shell')
        materials = {(f.texture.casefold(), f.material.casefold()) for f in lod.faces}
        if len(materials) > MAX_MATERIALS:
            fail('HC-A012', 'visual LOD uses too many materials')
        if policy.get('uv_overlap'):
            try:
                if _uv_overlap(lod):
                    fail('HC-A011', 'overlapping UV faces')
            except ValueError:
                fail('HC-A011', 'UV overlap check exceeds work limit')
        positions.extend(v.position for v in lod.vertices)
    for (_, high), (_, low) in zip(visual, visual[1:]):
        if _tri_count(low) > LOD_RATIO * _tri_count(high):
            fail('HC-A012', 'LOD triangle reduction is not monotonic')
    box = policy.get('expected_bbox')
    if box is not None:
        tolerance = policy.get('bbox_tolerance', BBOX_TOLERANCE)
        try:
            lo, hi = box
            lo, hi = [tuple(float(x) for x in v) for v in (lo, hi)]
            if len(lo) != 3 or len(hi) != 3 or not all(math.isfinite(x) for x in lo + hi) or not 0 <= tolerance <= 1:
                raise ValueError
        except (TypeError, ValueError):
            fail('HC-A010', 'invalid expected_bbox')
        else:
            first = visual[0][1] if visual else None
            if first is None:
                fail('HC-A011', 'no visual LOD for bounds check')
            else:
                points = [v.position for v in first.vertices]
                found = (tuple(min(p[i] for p in points) for i in range(3)),
                         tuple(max(p[i] for p in points) for i in range(3)))
                if any(abs(found[0][i] - lo[i]) > tolerance or abs(found[1][i] - hi[i]) > tolerance for i in range(3)):
                    fail('HC-A011', 'bounding box or pivot differs from recipe')


def _texture_checks(textures, rvmats, asset, inventory, check_path, fail):
    referenced = {f.texture.casefold() for lod in asset.lods.values() for f in lod.faces if f.texture}
    referenced |= {f.material.casefold() for lod in asset.lods.values() for f in lod.faces if f.material}
    if not isinstance(rvmats, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in rvmats.items()):
        fail('HC-A014', 'invalid rvmat inventory')
        rvmats = {}
    for path, text in rvmats.items():
        check_path(path)
        try:
            stages = [v for _, key, values in _fields(text) if key == 'texture' for v in values]
        except ValueError:
            fail('HC-A010', 'unsupported rvmat; supply standalone text')
            continue
        for value in stages:
            if not value or PROCEDURAL.fullmatch(value):
                continue
            try:
                mlod.virtual_path(value)
                if value.casefold() not in inventory:
                    raise ValueError
            except (ValueError, TypeError):
                fail('HC-A014', 'rvmat stage texture absent from allowed source inventory')
            referenced.add(value.casefold())
    if textures is None:
        return
    if not isinstance(textures, dict):
        fail('HC-A013', 'invalid texture inventory')
        return
    shipped = {p.casefold() for p in textures if isinstance(p, str)}
    for path, data in textures.items():
        try:
            mlod.virtual_path(path)
            kind, width, height = paa_info(data)
        except (ValueError, TypeError):
            fail('HC-A013', 'invalid .paa or texture path')
            continue
        if not width or not height or width & (width - 1) or height & (height - 1):
            fail('HC-A013', 'texture size is not power-of-two')
        if path.casefold().endswith('_nohq.paa') and kind != 'DXT5':
            fail('HC-A013', 'normal map is not DXT5')
        if path.casefold() not in referenced:
            fail('HC-A013', 'unreferenced texture')
        check_path(path)
    own = mlod.OWN_PREFIX.casefold() + '\\'
    for path in referenced:
        if path.endswith('.paa') and path.startswith(own) and path not in shipped:
            fail('HC-A013', 'referenced own texture not shipped')


def _rotate(point, pivot, axis, degrees):
    length = math.sqrt(sum(a * a for a in axis))
    k = tuple(a / length for a in axis)
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    v = tuple(point[i] - pivot[i] for i in range(3))
    kv = k[0]*v[0] + k[1]*v[1] + k[2]*v[2]
    cross = (k[1]*v[2]-k[2]*v[1], k[2]*v[0]-k[0]*v[2], k[0]*v[1]-k[1]*v[0])
    return tuple(pivot[i] + v[i]*c + cross[i]*s + k[i]*kv*(1-c) for i in range(3))


def _rig_checks(asset, rig, weights, fail):
    if not isinstance(rig, dict) or set(rig) - RIG_KEYS:
        fail('HC-A015', 'unsupported rig input')
        return
    used = set()
    for rows in (weights or {}).values():
        for row in rows:
            if isinstance(row, dict):
                used.update(k for k in row if isinstance(k, str))
    bones = rig.get('bones')
    if bones is not None and not used <= {b for b in bones}:
        fail('HC-A015', 'vertex group is not an allowed skeleton bone')
    skeleton, poses = rig.get('skeleton'), rig.get('poses')
    if skeleton is None and poses is None:
        return
    try:
        if not weights:
            raise ValueError
        for bone, row in skeleton.items():
            parent = row.get('parent')
            if (parent is not None and parent not in skeleton) or len(row['pivot']) != 3:
                raise ValueError
            [float(x) for x in row['pivot']]

        def depth(bone):
            n = 0
            while skeleton[bone].get('parent') is not None:
                bone, n = skeleton[bone]['parent'], n + 1
                if n > len(skeleton):
                    raise ValueError
            return n
        for bone in skeleton:
            depth(bone)
        if not used <= set(skeleton) or not poses:
            raise ValueError
        for pose in poses.values():
            if not set(pose) <= set(skeleton):
                raise ValueError
            for axis, degrees in pose.values():
                if len(axis) != 3 or not math.isfinite(degrees) or not any(axis):
                    raise ValueError
    except (AttributeError, KeyError, TypeError, ValueError):
        fail('HC-A015', 'skeleton or poses unusable for stretch test')
        return

    def posed(bone, point, pose):
        while bone is not None:
            if bone in pose:
                axis, degrees = pose[bone]
                point = _rotate(point, skeleton[bone]['pivot'], axis, degrees)
            bone = skeleton[bone].get('parent')
        return point
    for key, rows in weights.items():
        lod = asset.lods.get(float(key))
        if lod is None or len(rows) != len(lod.vertices):
            continue
        edges = {tuple(sorted(e)) for f in lod.faces for e in zip(f.vertices, f.vertices[1:] + f.vertices[:1])}
        for pose in poses.values():
            out = []
            for vertex, row in zip(lod.vertices, rows):
                parts = [(w, posed(b, vertex.position, pose)) for b, w in row.items()]
                out.append(tuple(sum(w * p[i] for w, p in parts) for i in range(3)))
            for a, b in edges:
                rest = math.dist(lod.vertices[a].position, lod.vertices[b].position)
                now = math.dist(out[a], out[b])
                if rest > 1e-9 and not now <= MAX_EDGE_STRETCH * rest:
                    fail('HC-A015', 'synthetic pose stretches edges beyond 2.5x')
                    return


def lint(asset, *, model_cfg='', config='', sources=(), skin_weights=None,
         policy=None, textures=None, rvmats=None, rig=None):
    findings = []

    def fail(rule, detail):
        findings.append({'id': rule, 'detail': detail})

    geometry = asset.lods.get(mlod.GEOMETRY)
    if not geometry or not geometry.faces or not geometry.vertices:
        fail('HC-A001', 'missing or empty Geometry')
    elif (len(geometry.masses) != len(geometry.vertices)
          or any(not math.isfinite(m) or m < 0 for m in geometry.masses)
          or sum(geometry.masses) <= 0):
        fail('HC-A004', 'missing or invalid #Mass#')
    if not isinstance(sources, (list, tuple, set, frozenset)) or any(not isinstance(p, str) for p in sources):
        return {'valid': False, 'findings': [{'id': 'HC-A008', 'detail': 'invalid source inventory'}]}
    inventory = {p.casefold() for p in sources}

    def check_path(path):
        try:
            mlod.virtual_path(path)
            if path and path.casefold() not in inventory:
                raise ValueError('unresolved')
        except (ValueError, TypeError):
            fail('HC-A008', 'texture/material absent from allowed source inventory')
    for lod in asset.lods.values():
        for face in lod.faces:
            for path in (face.texture, face.material):
                check_path(path)
    # Structural validation precedes indexed topology operations. It also catches
    # unsupported metadata, nonfinite coordinates, invalid faces and indices.
    try:
        mlod.validate(asset)
    except (ValueError, TypeError, IndexError):
        fail('HC-A010', 'invalid or unsupported MLOD IR')
        return {'valid': False, 'findings': findings}
    if geometry:
        for component in _components(geometry):
            edges = Counter()
            vertices = set()
            for index in component:
                face = geometry.faces[index]
                vertices.update(face.vertices)
                edges.update(zip(face.vertices, face.vertices[1:] + face.vertices[:1]))
            if any(count != 1 or edges[(b, a)] != 1 for (a, b), count in edges.items()):
                fail('HC-A002', 'open/nonmanifold or inconsistently wound component')
            # All vertices must be on the inward side of every face plane. This
            # checks outward winding too; inward shells cannot masquerade as convex.
            convex = True
            scale = max((math.dist(geometry.vertices[a].position, geometry.vertices[b].position)
                         for a, b in edges), default=1)
            tolerance = max(scale, 1e-9) * 1e-6
            volume = 0.0
            for index in component:
                face = geometry.faces[index]
                a, b, c = [geometry.vertices[i].position for i in face.vertices[:3]]
                u, v = [b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)]
                normal = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
                length = math.hypot(*normal)
                if length == 0:
                    convex = False
                    continue
                for vertex in vertices:
                    distance = sum(normal[i]*(geometry.vertices[vertex].position[i]-a[i]) for i in range(3)) / length
                    if distance > tolerance or (vertex in face.vertices and abs(distance) > tolerance):
                        convex = False
                # Triangulate quads for signed enclosed volume.
                for corner in range(1, len(face.vertices)-1):
                    b, c = [geometry.vertices[i].position for i in face.vertices[corner:corner+2]]
                    volume += sum(a[i] * (b[(i+1)%3]*c[(i+2)%3]-b[(i+2)%3]*c[(i+1)%3]) for i in range(3)) / 6
            named = any(re.fullmatch(r'component\d+', name, re.I)
                        and set(selection.vertices) == vertices
                        and (not selection.faces or set(selection.faces) == component)
                        for name, selection in geometry.selections.items())
            if not convex or volume <= tolerance**3 or not named:
                fail('HC-A003', 'nonconvex/zero-volume or unnamed component')
    if policy is not None and not isinstance(policy, dict):
        fail('HC-A010', 'unsupported mesh policy')
    else:
        _mesh_checks(asset, policy or {}, fail)
    if textures is not None or rvmats is not None:
        _texture_checks(textures, {} if rvmats is None else rvmats, asset, inventory, check_path, fail)
    try:
        fields = _fields(model_cfg) + _fields(config)
        visual = {n.casefold() for r, lod in asset.lods.items() if r < 1000 for n, s in lod.selections.items() if s.vertices or s.faces}
        all_names = {n.casefold() for lod in asset.lods.values() for n, s in lod.selections.items() if s.vertices or s.faces}
        memory = {n.casefold() for n, s in asset.lods.get(mlod.MEMORY, mlod.LOD()).selections.items() if s.vertices}
        fire = {n.casefold() for n, s in asset.lods.get(mlod.FIRE_GEOMETRY, mlod.LOD()).selections.items()
                if (s.vertices or s.faces) and not re.fullmatch(r'component\d+', n, re.I)}
        damage = set()
        has_damage = False
        skinned = False
        for ancestry, key, values in fields:
            names = {v.casefold() for v in values if v}
            for value in values:
                if re.search(r'\.(?:paa|rvmat|tga|png)$', value, re.I):
                    check_path(value)
            if key == 'skeletonname' and names:
                skinned = True
            if key == 'sections' and not names <= visual:
                fail('HC-A005', 'model.cfg sections missing from visual LODs')
            if ((key.startswith('selection') or key in {'hiddenselections', 'simplehiddenselections'})
                    and not names <= all_names):
                fail('HC-A005', 'config selection missing')
            if 'memorypoint' in key or key in {'axis', 'begin', 'end'}:
                if not names <= memory:
                    fail('HC-A007', 'config memory point missing')
            if ((key == 'componentnames' and any(a.casefold() == 'damagezones' for a in ancestry))
                    or (key in {'name', 'selection'} and any(a.casefold() == 'hitpoints' for a in ancestry))):
                has_damage = True
                damage.update(names)
        if has_damage and damage != fire:
            fail('HC-A006', 'damage/hit selection set differs from Fire Geometry')
        if skinned and not skin_weights:
            fail('HC-A009', 'skinned model requires explicit IR weights')
    except (ValueError, IndexError):
        fail('HC-A010', 'unsupported config; supply standalone expanded text')
    if skin_weights:
        try:
            weighted_lods = {float(r): rows for r, rows in skin_weights.items()}
            if any(r not in asset.lods for r in weighted_lods):
                raise ValueError
            for resolution, lod in asset.lods.items():
                if resolution >= 1000:
                    continue
                rows = weighted_lods[resolution]
                if len(rows) != len(lod.vertices):
                    raise ValueError
                for row in rows:
                    if (not 1 <= len(row) <= 4 or any(not isinstance(bone, str) or not bone for bone in row)
                            or any(not math.isfinite(w) or w <= 0 for w in row.values())
                            or not math.isclose(sum(row.values()), 1, abs_tol=1e-5)):
                        raise ValueError
        except (ValueError, KeyError, TypeError, AttributeError):
            fail('HC-A009', 'invalid skin weights')
    if rig is not None:
        _rig_checks(asset, rig, skin_weights, fail)
    findings = sorted({(f['id'], f['detail']) for f in findings})
    return {'valid': not findings, 'findings': [{'id': i, 'detail': d} for i, d in findings]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset', type=Path)
    parser.add_argument('--model-cfg', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--policy', type=Path, help='JSON mesh policy (see module docstring)')
    parser.add_argument('--rig', type=Path, help='JSON {bones, skeleton, poses}')
    parser.add_argument('--textures', type=Path, help='JSON {virtual path: local .paa file}')
    parser.add_argument('--rvmats', type=Path, help='JSON {virtual path: local .rvmat file}')
    args = parser.parse_args(argv)
    try:
        weights = None
        if args.asset.suffix.lower() == '.p3d':
            asset = mlod.read_mlod(args.asset.read_bytes())
        else:
            document = json.loads(args.asset.read_text())
            asset = asset_from_ir(document)
            weights = document.get('skin_weights')
        def table(path, binary):
            if path is None:
                return None
            mapping = json.loads(path.read_text())
            if not isinstance(mapping, dict):
                raise ValueError
            return {k: Path(v).read_bytes() if binary else Path(v).read_text() for k, v in mapping.items()}
        result = lint(asset, model_cfg=args.model_cfg.read_text(), config=args.config.read_text(),
                      sources=json.loads(args.sources.read_text()), skin_weights=weights,
                      policy=json.loads(args.policy.read_text()) if args.policy else None,
                      rig=json.loads(args.rig.read_text()) if args.rig else None,
                      textures=table(args.textures, True), rvmats=table(args.rvmats, False))
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        result = {'valid': False, 'findings': [{'id': 'HC-A010', 'detail': 'unreadable or unsupported input'}]}
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print('asset_lint: ' + ('pass' if result['valid'] else 'fail'))
        for finding in result['findings']:
            print(finding['id'] + ': ' + finding['detail'])
    return 0 if result['valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
