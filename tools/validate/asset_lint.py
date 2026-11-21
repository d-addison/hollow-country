"""Offline authored Asset IR/MLOD checks; never establishes native acceptance.

JSON IR uses mlod.Asset's dataclass fields, with numeric-string LOD keys.
Optional skin_weights maps LOD keys to one {bone: weight} record per vertex.
The codec cannot encode skin weights yet: supply them in IR for skinned checks.
--sources is a JSON list of virtual paths inventoried from installed DZ content
and authored source files; no filesystem guessing or runtime path construction.
Config inputs are standalone text (expand includes/macros before linting).
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
}


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


def lint(asset, *, model_cfg='', config='', sources=(), skin_weights=None):
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
    findings = sorted({(f['id'], f['detail']) for f in findings})
    return {'valid': not findings, 'findings': [{'id': i, 'detail': d} for i, d in findings]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset', type=Path)
    parser.add_argument('--model-cfg', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        weights = None
        if args.asset.suffix.lower() == '.p3d':
            asset = mlod.read_mlod(args.asset.read_bytes())
        else:
            document = json.loads(args.asset.read_text())
            asset = asset_from_ir(document)
            weights = document.get('skin_weights')
        result = lint(asset, model_cfg=args.model_cfg.read_text(), config=args.config.read_text(),
                      sources=json.loads(args.sources.read_text()), skin_weights=weights)
    except (OSError, ValueError, TypeError, KeyError):
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
