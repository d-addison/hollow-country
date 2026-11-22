"""Headless Blender check: exported hit components against the visual mesh bounds (Neon P3.3).

For each of our own .p3d models (mods/ and assets_src/ inside this repository) the
Python side decodes the highest-detail Visual LOD and the Fire Geometry ComponentNN
selections (tools.validate.p3d_firegeom_audit loader, ODOL56 or our MLOD subset) and
hands them to one isolated Blender run (the pinned portable Blender 5.2.4 through
tools.assets.blender_runner: HC_BLENDER, factory startup, autoexec disabled). Blender
builds the meshes and measures bounding boxes, volumes, non-manifold edges and the
distance from each component centroid to the visual surface; the policy below is
applied in Python to those numbers:

  BH001  component bounding box leaves the visual bounds by more than the tolerance
  BH002  the components together cover less of the visual extent than min_axis_cover
  BH003  component bounding box is flat (extent ~0 on an axis)
  BH004  component centroid lies farther from the visual surface than max_detached
  BH005  model has no ComponentNN selection, or its Visual LOD is degenerate

Without a usable Blender 5.2 the tool never skips: it prints a `needs-host-check:` line
and exits 3. Exit codes: 0 = pass, 1 = findings or Blender build failure, 2 = refused
input, 3 = needs-host-check. Offline mesh evidence only (engine_verified is false); the
thresholds are provisional review values, not measured engine limits.
"""
import argparse
import json
import math
from pathlib import Path
import sys

SCHEMA = 'hitbox-check.v1'
REQUEST = 'hitbox-request.v1'
MEASURE = 'hitbox-measure.v1'
PINNED = '5.2.4'
SCAN_ROOTS = ('mods', 'assets_src')
MAX_VERTICES = 400_000
# Provisional review policy, metres unless a ratio: tolerance is the larger of the
# absolute value and the relative share of the visual bounding-box diagonal.
POLICY = {'tolerance_m': 0.05, 'tolerance_rel': 0.05, 'min_axis_cover': 0.5,
          'max_detached_rel': 0.5, 'min_extent_m': 1e-4}
# Refusal reasons that mean this host cannot run the check (as opposed to a bad model).
HOST_REASONS = ('blender.not_found', 'blender.configuration_invalid', 'blender.launch_failed',
                'blender.windows_path_unavailable', 'blender.timeout', 'blender.version_requires_5_2')


# --------------------------------------------------------------------------
# Python side: request building and policy (no bpy)
# --------------------------------------------------------------------------

def build_request(data):
    """JSON-ready {visual, components} from one P3D's bytes, or raises ValueError."""
    from tools.validate import p3d_firegeom_audit as audit
    model = audit.load_model(data)
    visual = [lod for lod in model.lods if 0 <= lod.resolution < 1000]
    fire = audit.lod_at(model, audit.FIRE_GEOMETRY)
    if not visual or fire is None:
        raise ValueError('hitbox.lods_missing')
    visual = min(visual, key=lambda lod: lod.resolution)
    if not visual.faces or not visual.vertices:
        raise ValueError('hitbox.visual_empty')
    components = {}
    for name, faces, vertices in sorted(s for s in fire.selections.values() if audit.COMPONENT.fullmatch(s[0])):
        ids = set(vertices)
        picked = []
        for face in faces:
            if 0 <= face < len(fire.faces):
                picked.append(face)
                ids.update(fire.faces[face])
        order = sorted(i for i in ids if 0 <= i < len(fire.vertices))
        local = {old: new for new, old in enumerate(order)}
        components[name] = {'vertices': [list(fire.vertices[i]) for i in order],
                            'faces': [[local[i] for i in fire.faces[f]] for f in picked
                                      if all(i in local for i in fire.faces[f])]}
    total = len(visual.vertices) + sum(len(c['vertices']) for c in components.values())
    if total > MAX_VERTICES:
        raise ValueError('hitbox.too_large')
    return {'schema': REQUEST, 'visual': {'vertices': [list(v) for v in visual.vertices],
                                          'faces': [list(f) for f in visual.faces]},
            'components': components}


def _extent(box):
    return [h - l for l, h in zip(box[0], box[1])]


def evaluate(measure, policy=None):
    """Findings from a hitbox-measure.v1 document (numbers measured inside Blender)."""
    policy = dict(POLICY, **(policy or {}))
    findings = []

    def add(rule, detail):
        findings.append({'id': rule, 'detail': detail})
    visual = measure['visual']
    low, high = visual['bbox']
    extent = _extent((low, high))
    diagonal = math.sqrt(sum(e * e for e in extent))
    components = measure['components']
    if not components:
        add('BH005', 'no ComponentNN selection in Fire Geometry')
        return findings
    if min(extent) < policy['min_extent_m'] or not math.isfinite(diagonal):
        add('BH005', 'visual mesh bounds are degenerate')
        return findings
    tolerance = max(policy['tolerance_m'], policy['tolerance_rel'] * diagonal)
    union_low, union_high = [math.inf] * 3, [-math.inf] * 3
    for name in sorted(components):
        item = components[name]
        c_low, c_high = item['bbox']
        if min(_extent((c_low, c_high))) < policy['min_extent_m']:
            add('BH003', '%s bounding box is flat' % name)
        if any(c_low[i] < low[i] - tolerance or c_high[i] > high[i] + tolerance for i in range(3)):
            add('BH001', '%s leaves the visual bounds by more than %.3f m' % (name, tolerance))
        if item['distance_to_visual'] > policy['max_detached_rel'] * diagonal:
            add('BH004', '%s centroid is %.3f m from the visual surface' % (name, item['distance_to_visual']))
        for i in range(3):
            union_low[i], union_high[i] = min(union_low[i], c_low[i]), max(union_high[i], c_high[i])
    for axis, label in enumerate('xyz'):
        if extent[axis] <= 2 * tolerance:
            continue          # a thin axis is covered by tolerance alone
        covered = max(0.0, min(union_high[axis], high[axis]) - max(union_low[axis], low[axis]))
        if covered < policy['min_axis_cover'] * extent[axis]:
            add('BH002', 'components cover %.0f%% of the visual %s extent'
                % (100.0 * covered / extent[axis], label))
    return findings


def check_measure(measure, *, models=1):
    findings = evaluate(measure)
    return {'schema': SCHEMA, 'valid': not findings, 'findings': findings, 'engine_verified': False,
            'blender': measure.get('blender'), 'pinned': PINNED, 'models': models}


# --------------------------------------------------------------------------
# Blender side (the only code that imports bpy; runs inside the child process)
# --------------------------------------------------------------------------

def blender_measure(request):
    import bmesh
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    if bpy.app.version[:2] != (5, 2):
        raise ValueError('blender.version_requires_5_2')
    if request.get('schema') != REQUEST:
        raise ValueError('hitbox.request_schema')
    bpy.ops.wm.read_factory_settings(use_empty=True)

    def mesh_of(name, spec):
        points = [Vector(v) for v in spec['vertices']]
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([tuple(p) for p in points], [], [tuple(f) for f in spec['faces']])
        mesh.update()
        return mesh, points

    def bounds(points):
        if not points:
            return [[0.0] * 3, [0.0] * 3]
        return [[min(p[i] for p in points) for i in range(3)], [max(p[i] for p in points) for i in range(3)]]

    def stats(mesh):
        bm = bmesh.new()
        bm.from_mesh(mesh)
        try:
            return {'volume': abs(bm.calc_volume(signed=True)) if bm.faces else 0.0,
                    'area': sum(f.calc_area() for f in bm.faces),
                    'non_manifold_edges': sum(1 for e in bm.edges if not e.is_manifold)}
        finally:
            bm.free()
    visual_mesh, visual_points = mesh_of('hc_visual', request['visual'])
    tree = BVHTree.FromPolygons(visual_points, [tuple(f) for f in request['visual']['faces']])
    visual = dict(stats(visual_mesh), bbox=bounds(visual_points), vertices=len(visual_points))
    components = {}
    for name, spec in sorted(request['components'].items()):
        mesh, points = mesh_of('hc_' + name, spec)
        centroid = sum(points, Vector((0.0, 0.0, 0.0))) / len(points) if points else Vector((0.0, 0.0, 0.0))
        hit = tree.find_nearest(centroid)
        distance = hit[3] if hit is not None and hit[3] is not None else math.inf
        components[name] = dict(stats(mesh), bbox=bounds(points), vertices=len(points),
                                centroid=[centroid.x, centroid.y, centroid.z], distance_to_visual=distance)
    return {'schema': MEASURE, 'blender': list(bpy.app.version), 'visual': visual, 'components': components}


def blender_main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--recipe', required=True, type=Path)    # request JSON (name shared with the runner)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    request = json.loads(args.recipe.read_text(encoding='utf-8'))
    args.output.write_text(json.dumps(blender_measure(request), sort_keys=True, allow_nan=False),
                           encoding='utf-8')


# --------------------------------------------------------------------------
# Host side
# --------------------------------------------------------------------------

def run_blender(request, *, config=None, timeout=120):
    """One isolated Blender run for one request; returns the measurement document."""
    import shutil
    import tempfile
    from tools.assets import blender_runner
    executable = blender_runner.locate(config)
    scratch = blender_runner.build_directory(blender_runner.BUILD_ROOT / 'asset-tmp')
    with tempfile.TemporaryDirectory(prefix='hitbox-', dir=scratch) as temp:
        directory = Path(temp)
        request_path, output_path = directory / 'request.json', directory / 'measure.json'
        request_path.write_text(json.dumps(request, sort_keys=True, allow_nan=False), encoding='utf-8')
        script = directory / 'hitbox_script.py'
        shutil.copyfile(Path(__file__), script)
        blender_runner._execute(executable, script, ['--recipe', str(request_path), '--output', str(output_path)],
                                directory, timeout)
        if output_path.is_symlink() or not output_path.is_file() or output_path.stat().st_size > 64 * 1024 * 1024:
            raise blender_runner.BlenderRefusal('blender.output_invalid')
        try:
            measure = json.loads(output_path.read_text(encoding='utf-8'))
        except ValueError:
            raise blender_runner.BlenderRefusal('blender.output_invalid') from None
    if not isinstance(measure, dict) or measure.get('schema') != MEASURE:
        raise blender_runner.BlenderRefusal('blender.output_invalid')
    return measure


def needs_host_check(reason):
    line = 'needs-host-check: %s' % reason
    print(line, file=sys.stderr)
    print(json.dumps({'valid': False, 'status': 'needs-host-check', 'reason': reason, 'line': line}))
    return 3


def _models(paths, base):
    from tools.validate import p3d_firegeom_audit as audit
    found = []
    base = Path(base).resolve()
    for root in paths:
        path = Path(root)
        path = path if path.is_absolute() else base / path
        if path.is_symlink() or not path.exists():
            raise audit.AuditRefusal('audit.root_invalid')
        path = path.resolve()
        if base not in path.parents:
            raise audit.AuditRefusal('audit.root_outside_repo')
        found.extend([path] if path.is_file() else audit._files(path))
    return sorted(p for p in found if p.suffix.lower() == '.p3d' and not p.is_symlink())


def check_paths(paths, *, base=None, config=None, timeout=120, runner=None):
    """Check every .p3d under paths. runner(request) -> measure (defaults to Blender)."""
    from tools.validate import p3d_firegeom_audit as audit
    base = audit.ROOT if base is None else Path(base)
    models = _models(paths, base)
    report = {'schema': SCHEMA, 'engine_verified': False, 'pinned': PINNED, 'models': len(models),
              'results': [], 'valid': True}
    if not models:
        report['note'] = 'no .p3d under the given roots: nothing to check'
    for model in models:
        rel = model.relative_to(base.resolve()).as_posix()
        try:
            request = build_request(model.read_bytes())
        except (ValueError, OSError) as exc:
            report['results'].append({'model': rel, 'valid': False,
                                      'findings': [{'id': 'BH005', 'detail': str(exc) if isinstance(exc, ValueError) else 'io'}]})
            continue
        measure = runner(request) if runner else run_blender(request, config=config, timeout=timeout)
        result = check_measure(measure)
        report['results'].append({'model': rel, 'valid': result['valid'], 'findings': result['findings'],
                                  'blender': result['blender']})
    report['valid'] = all(r['valid'] for r in report['results'])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', action='append', type=Path,
                        help='.p3d file or directory inside this repository (default: %s)' % ', '.join(SCAN_ROOTS))
    parser.add_argument('--timeout', type=int, default=120)
    args = parser.parse_args(argv)
    from tools.assets import blender_runner
    from tools.validate import p3d_firegeom_audit as audit
    try:
        blender_runner.locate()
    except blender_runner.BlenderRefusal as exc:
        return needs_host_check(str(exc))
    roots = args.root or [r for r in SCAN_ROOTS if (audit.ROOT / r).is_dir()]
    try:
        report = check_paths(roots, timeout=args.timeout)
    except audit.AuditRefusal as exc:
        print(json.dumps({'valid': False, 'reason': str(exc)}))
        return 2
    except blender_runner.BlenderRefusal as exc:
        reason = str(exc)
        if reason.split(':')[0] in HOST_REASONS:
            return needs_host_check(reason)
        print(json.dumps({'valid': False, 'status': 'blender-error', 'reason': reason}))
        return 1
    except OSError:
        print(json.dumps({'valid': False, 'reason': 'audit.io'}))
        return 2
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report['valid'] else 1


if __name__ == '__main__':
    try:
        import bpy  # noqa: F401  (only importable inside Blender)
    except ImportError:
        sys.exit(main())
    else:
        blender_main()
