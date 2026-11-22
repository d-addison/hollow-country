"""Fire Geometry / View Geometry audit of our own P3D models (Neon P3.3).

Reads the .p3d files of our own sources (mods/ and assets_src/ inside this repository,
never vanilla or Workshop files) with the clean-room ODOL56 reader (binarised models) or
the MLOD reader of our own writer, and reports:

  FG001  no Fire Geometry LOD (7e15)               FG002  no View Geometry LOD (6e15)
  FG003  model or LOD unreadable                    FG010  LOD without vertices or faces
  FG011  non-finite vertex coordinate               FG012  every face has zero area
  FG013  some faces have zero area (warning)        FG014  LOD is flat (extent ~0 on an axis)
  FG020  Fire Geometry has no ComponentNN           FG022  empty ComponentNN selection
  FG023  ComponentNN is flat or has no geometry
  FG030  config DamageZones componentNames entry missing from the Fire Geometry
  FG031  Fire Geometry hit component absent from the model's DamageZones (warning)
  FG032  hit components but no config class references the model (warning)
  FG040  config text not parseable, name cross-check skipped (warning)

Hit components are Fire Geometry named selections that are not ComponentNN; DamageZones
come from the `componentNames[]` of `DamageSystem/DamageZones/<zone>` of the config class
whose `model` path is this model (config.cpp of the scanned sources, expanded text only).
A class without its own DamageZones inherits them from a parent that this offline audit
does not resolve; that is listed in `notes`, not as a finding.

Static file evidence only: engine_verified is always false, and a pass never says how the
engine treats the geometry. Exit code 0 = no errors, 1 = errors (or warnings with
--strict), 2 = refused input.
"""
import argparse
from dataclasses import dataclass, field
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
import sys

from tools.assets import mlod
from tools.audit import odol56
from tools.validate import asset_lint

ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = ('mods', 'assets_src')
SCHEMA = 'p3d-firegeom-audit.v1'
VIEW_GEOMETRY, FIRE_GEOMETRY = 6e15, 7e15
COMPONENT = re.compile(r'component\d+', re.IGNORECASE)
MAX_MODEL_BYTES = 128 * 1024 * 1024
MAX_MODELS = 4096
MAX_FILES = 100000
MAX_CONFIG_BYTES = 8 * 1024 * 1024
# Offline review thresholds in metres / square metres, not engine limits.
POLICY = {'min_extent_m': 1e-4, 'degenerate_area_m2': 1e-10}
SEVERITY = {'FG013': 'warning', 'FG031': 'warning', 'FG032': 'warning', 'FG040': 'warning'}


class AuditRefusal(ValueError):
    """Stable reason for refused input; never carries file contents or absolute paths."""


@dataclass
class LodView:
    resolution: float
    vertices: list
    faces: list
    selections: dict = field(default_factory=dict)   # lower name -> (name, face ids, vertex ids)


@dataclass
class ModelView:
    lods: list = field(default_factory=list)
    failed: list = field(default_factory=list)       # resolutions of LODs the reader refused


def _same(a, b):
    return abs(a - b) <= 1e-6 * max(abs(b), 1.0)


def load_model(data):
    """Decode a P3D (ODOL or our MLOD subset) into a ModelView; raises AuditRefusal."""
    if len(data) > MAX_MODEL_BYTES:
        raise AuditRefusal('model.size')
    view = ModelView()
    try:
        if data[:4] == b'ODOL':
            model = odol56.read_odol(data, strict=False)
            for index in sorted(model.failed_lods):
                view.failed.append(model.resolutions[index])
            for lod in model.lods:
                selections = {s.name.lower(): (s.name, tuple(s.faces), tuple(s.vertices))
                              for s in lod.named_selections}
                view.lods.append(LodView(lod.resolution, [tuple(v) for v in lod.vertices],
                                         [tuple(f) for f in lod.faces], selections))
        elif data[:4] == b'MLOD':
            asset = mlod.read_mlod(data, physical=False)
            for resolution, lod in sorted(asset.lods.items()):
                selections = {n.lower(): (n, tuple(s.faces), tuple(s.vertices))
                              for n, s in lod.selections.items()}
                view.lods.append(LodView(resolution, [tuple(v.position) for v in lod.vertices],
                                         [tuple(f.vertices) for f in lod.faces], selections))
        else:
            raise AuditRefusal('model.magic')
    except AuditRefusal:
        raise
    except (ValueError, IndexError, struct.error):
        raise AuditRefusal('model.unreadable') from None
    return view


def lod_at(model, resolution):
    for lod in model.lods:
        if _same(lod.resolution, resolution):
            return lod
    return None


def _extent(points):
    lows = [min(p[i] for p in points) for i in range(3)]
    highs = [max(p[i] for p in points) for i in range(3)]
    return [h - l for l, h in zip(lows, highs)]


def _area(vertices, face):
    total = 0.0
    a = vertices[face[0]]
    for i in range(1, len(face) - 1):
        b, c = vertices[face[i]], vertices[face[i + 1]]
        u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        total += 0.5 * math.sqrt(cross[0] ** 2 + cross[1] ** 2 + cross[2] ** 2)
    return total


def _geometry_findings(lod, label, add):
    """Findings shared by Fire and View Geometry: empty, non-finite, zero-area, flat."""
    if not lod.vertices or not lod.faces:
        add('FG010', label, 'LOD has no vertices or no faces')
        return False
    if any(not math.isfinite(c) for v in lod.vertices for c in v):
        add('FG011', label, 'non-finite vertex coordinate')
        return False
    areas = [_area(lod.vertices, f) for f in lod.faces]
    flat_faces = sum(1 for a in areas if a < POLICY['degenerate_area_m2'])
    if flat_faces == len(areas):
        add('FG012', label, 'every face has zero area')
        return False
    if flat_faces:
        add('FG013', label, '%d of %d faces have zero area' % (flat_faces, len(areas)))
    if min(_extent(lod.vertices)) < POLICY['min_extent_m']:
        add('FG014', label, 'LOD is flat: extent below %g m on an axis' % POLICY['min_extent_m'])
        return False
    return True


def _component_points(lod, faces, vertices):
    ids = set(vertices)
    for face in faces:
        if 0 <= face < len(lod.faces):
            ids.update(lod.faces[face])
    return [lod.vertices[i] for i in sorted(ids) if 0 <= i < len(lod.vertices)]


def hit_components(fire):
    return sorted(name for name, _f, _v in fire.selections.values() if not COMPONENT.fullmatch(name))


def audit_model(model, *, zones=None):
    """Findings for one decoded model. zones: None skips the name cross-check; [] means no
    config class references the model; otherwise one set of lower-case componentNames per
    referencing class that has its own DamageZones."""
    findings = []

    def add(rule, label, detail):
        findings.append({'id': rule, 'severity': SEVERITY.get(rule, 'error'), 'lod': label, 'detail': detail})
    for name, resolution in (('fire_geometry', FIRE_GEOMETRY), ('view_geometry', VIEW_GEOMETRY)):
        if any(_same(f, resolution) for f in model.failed):
            add('FG003', name, 'LOD present but unreadable by the reader')
            continue
        lod = lod_at(model, resolution)
        if lod is None:
            add('FG001' if resolution == FIRE_GEOMETRY else 'FG002', name, 'LOD missing')
            continue
        if _geometry_findings(lod, name, add) and resolution == FIRE_GEOMETRY:
            _component_findings(lod, add)
    fire = lod_at(model, FIRE_GEOMETRY)
    if fire is not None and zones is not None:
        _zone_findings(fire, zones, add)
    return findings


def _component_findings(fire, add):
    components = [s for s in fire.selections.values() if COMPONENT.fullmatch(s[0])]
    if not components:
        add('FG020', 'fire_geometry', 'no ComponentNN selection: nothing can be hit')
    for name, faces, vertices in sorted(components):
        points = _component_points(fire, faces, vertices)
        if not faces and not vertices:
            add('FG022', 'fire_geometry', '%s is empty' % name)
        elif not points or min(_extent(points)) < POLICY['min_extent_m']:
            add('FG023', 'fire_geometry', '%s is flat or has no geometry' % name)


def _zone_findings(fire, zones, add):
    hits = {n.lower() for n in hit_components(fire)}
    if not zones:
        if hits:
            add('FG032', 'fire_geometry', 'hit components %s but no config class references the model'
                % ', '.join(sorted(hits)))
        return
    for declared in zones:
        for name in sorted(declared - hits):
            add('FG030', 'fire_geometry', 'DamageZones componentNames entry %s has no Fire Geometry selection' % name)
        for name in sorted(hits - declared):
            add('FG031', 'fire_geometry', 'Fire Geometry hit component %s is in no DamageZones entry' % name)


def _norm_path(value):
    return str(PurePosixPath(value.replace('\\', '/').strip('/').casefold()))


def _prefix(directory):
    path = directory / '$PBOPREFIX$'
    if path.is_file() and not path.is_symlink():
        text = path.read_text(encoding='utf-8', errors='replace').strip().splitlines()
        if text:
            return text[0].strip().strip('\\/')
    return directory.name


def collect_model_classes(configs):
    """{normalised model path: [class path, ...]} plus {class path: [component name sets]}
    over expanded config texts; returns (models, zones, errors)."""
    models, zones, errors = {}, {}, 0
    for text in configs:
        try:
            rows = asset_lint._fields(text)
        except (ValueError, IndexError):
            errors += 1
            continue
        for ancestry, key, values in rows:
            folded = tuple(a.casefold() for a in ancestry)
            if key == 'model' and values:
                models.setdefault(_norm_path(values[0]), []).append(folded)
            if key == 'componentnames' and 'damagesystem' in folded and 'damagezones' in folded:
                zones.setdefault(folded[:folded.index('damagesystem')], set()).update(
                    v.casefold() for v in values if v)
    return models, zones, errors


def _files(root):
    found = []
    stack = [root]
    while stack:
        directory = stack.pop()
        for entry in sorted(directory.iterdir()):
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name not in ('.git', 'build'):
                    stack.append(entry)
            elif entry.is_file():
                found.append(entry)
                if len(found) > MAX_FILES:
                    raise AuditRefusal('audit.too_many_files')
    return found


def audit_paths(roots, *, base=ROOT):
    """Audit every .p3d under the given roots (directories inside base)."""
    base = Path(base).resolve()
    resolved = []
    for root in roots:
        path = Path(root)
        path = (base / path) if not path.is_absolute() else path
        if path.is_symlink() or not path.is_dir():
            raise AuditRefusal('audit.root_invalid')
        path = path.resolve()
        if base not in path.parents and path != base:
            raise AuditRefusal('audit.root_outside_repo')
        if path == base or path.name in ('.git', 'build'):
            raise AuditRefusal('audit.root_invalid')
        resolved.append(path)
    models, configs = [], []
    for path in resolved:
        for entry in _files(path):
            if entry.suffix.lower() == '.p3d':
                models.append(entry)
            elif entry.name.lower() == 'config.cpp' and entry.stat().st_size <= MAX_CONFIG_BYTES:
                configs.append(entry)
    if len(models) > MAX_MODELS:
        raise AuditRefusal('audit.too_many_models')
    report = {'schema': SCHEMA, 'engine_verified': False, 'models': len(models), 'findings': [], 'notes': []}
    if not models:
        report['notes'].append('no .p3d under %s: nothing to audit' % ', '.join(
            str(p.relative_to(base).as_posix()) for p in resolved))
        report['valid'] = True
        return report
    texts = [c.read_text(encoding='utf-8', errors='replace') for c in sorted(configs)]
    class_models, class_zones, parse_errors = collect_model_classes(texts)
    if parse_errors:
        report['findings'].append({'id': 'FG040', 'severity': 'warning', 'model': '*', 'lod': '',
                                   'detail': '%d config.cpp not parseable as expanded text; its models are '
                                             'not cross-checked' % parse_errors})
    for entry in sorted(models):
        rel = entry.relative_to(base).as_posix()
        mod_dir = next((p for p in [entry.parent, *entry.parents]
                        if (p / 'config.cpp').is_file() or (p / '$PBOPREFIX$').is_file()), None)
        try:
            data = entry.read_bytes() if entry.stat().st_size <= MAX_MODEL_BYTES else b''
            model = load_model(data)
        except AuditRefusal as exc:
            report['findings'].append({'id': 'FG003', 'severity': 'error', 'model': rel, 'lod': '',
                                       'detail': str(exc)})
            continue
        classes = []
        if mod_dir is not None and not parse_errors:
            virtual = _norm_path(_prefix(mod_dir) + '/' + entry.relative_to(mod_dir).as_posix())
            classes = class_models.get(virtual, [])
        declared = []
        for ancestry in classes:
            if ancestry in class_zones:
                declared.append(class_zones[ancestry])
            else:
                report['notes'].append('%s: class %s has no own DamageZones (inherited zones are not '
                                       'resolved offline)' % (rel, ancestry[-1]))
        zones = declared
        if parse_errors or (classes and not declared):
            zones = None
        for finding in audit_model(model, zones=zones):
            report['findings'].append(dict(finding, model=rel))
    report['valid'] = not any(f['severity'] == 'error' for f in report['findings'])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', action='append', type=Path,
                        help='source directory inside this repository (default: %s)' % ', '.join(SCAN_ROOTS))
    parser.add_argument('--strict', action='store_true', help='warnings also fail')
    args = parser.parse_args(argv)
    roots = args.root or [r for r in SCAN_ROOTS if (ROOT / r).is_dir()]
    try:
        report = audit_paths(roots)
    except AuditRefusal as exc:
        print(json.dumps({'valid': False, 'reason': str(exc)}))
        return 2
    except OSError:
        print(json.dumps({'valid': False, 'reason': 'audit.io'}))
        return 2
    ok = report['valid'] and not (args.strict and any(f['severity'] == 'warning' for f in report['findings']))
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
