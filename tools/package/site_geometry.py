# SPDX-License-Identifier: MIT
"""Per-class geometry table for composed sites: measured box, long axis, symmetry and front.

Writes ``config/sites/class-geometry.json``. The composer (W4) and the offline validator (W5)
read that file; they never open a model. Numbers only: no vertices, no model paths, no
selection names and no pack class names are written.

Inputs (read-only)
    config/map-overlays/classes.json   the class list; every class in it gets a row.
    installed PBOs                     read in place through tools.audit.world_mesh_audit
                                       (Geometry LOD bounds, the same numbers
                                       ``world_mesh_audit --bounds-out`` proposes) and
                                       tools.audit.odol56 (memory LOD door points).
    the ``calibrated`` map of the existing output file (lead calibration results).

Frames and conventions (also written into the output under "conventions")
    Model frame: x right, y up, z forward, origin = the placement origin. All values are in
    that frame, metres, rounded to 3 decimals; angles in degrees rounded to 1 decimal.
    Bearing / yaw: clockwise seen from above, 0 = model +z, 90 = model +x. A front vector
    (x, z) has ``front_yaw_deg = atan2(x, z)`` normalised to [0, 360).
    Final object yaw (composer rule, sites-design 2.3): ``yaw = target_bearing - front_yaw_deg``.
    The lead's calibration session confirms the sign with one class before the table is used.

Row schema (``classes[<name>]``)
    bounds.min_m / max_m / size_m   [x, y, z] box; bounds.footprint_m = [size_x, size_z]
    bounds.source                   "geometry" (Geometry LOD) | "visual_lod" (no Geometry LOD)
                                    | "reserve_unmeasured" (no decodable vertices: the
                                    authoring reserve from classes.json, listed in "unmeasured")
    center_xz_m                     [x, z] of the footprint centre relative to the origin
    long_axis                       "x" | "z" (the longer footprint side) | null when the
                                    footprint is nearly square (aspect < 1.1)
    aspect                          longer side / shorter side
    symmetric                       true: any yaw is equivalent, front_yaw_deg is absent.
                                    false: directional; front_yaw_deg and front_source present.
    symmetry                        only when symmetric: "small" (footprint <= 0.5 m),
                                    "two_fold" (point and both mirror tests within tolerance),
                                    "two_fold_doors" (memory door points at both ends),
                                    "front_agnostic" (FRONT_AGNOSTIC policy list),
                                    "reserve_square", or "calibrated" (lead said so)
    asymmetry                       measured fractions of the footprint diagonal for a 180 deg
                                    turn (r180) and mirrors across the x and z axes (mx, mz)
    front_yaw_deg                   directional only. null while front_source is
                                    calibration_pending: the composer refuses a null front
                                    (no guess is ever written)
    front_source                    "odol_memory" (derived from memory-LOD door points on one
                                    end of an enclosure) | "calibration_pending" |
                                    "calibrated" (lead entered it with --set-front)
    front_candidates_deg            pending only: the yaws a long-axis front can take
    memory_end_door_deg             pending only, informational: bearing of the end of the long
                                    axis that carries door selections, when exactly one end does.
                                    For vehicles this is the tailgate/rear-door end, not a front.

Top-level keys: kind, version, conventions, thresholds, calibrated (input map), calibration_pending
(sorted class names that still need a front), unmeasured (sorted), classes.

Policy (thresholds are reviewable constants below; geometry cannot see textures or doors):
    * enclosures and vehicles (kinds building, tent, wreck, container) and classes whose name
      says they have a head end (bed, radio) are directional whatever the collision box looks
      like. A container whose memory LOD has doors at both ends is symmetric; at one end only,
      the front is that end (odol_memory).
    * FRONT_AGNOSTIC props (piles, pallets, hedgehogs) are symmetric by policy ("front_agnostic").
    * everything else is symmetric when its footprint is <= 0.5 m or its Geometry vertices
      match their own 180 degree turn and both mirrors within 5 percent of the footprint
      diagonal; otherwise it is directional and needs calibration.
    * the lead's ``--set-front CLASS=DEG`` (or ``CLASS=symmetric``) always wins and survives rebuilds.

CLI (run from the repo root)
    python3 -B -m tools.package.site_geometry                  rebuild and write the file
    python3 -B -m tools.package.site_geometry --check          rebuild, compare bytes (exit 1 on diff)
    python3 -B -m tools.package.site_geometry --calibration-list [--json]
    python3 -B -m tools.package.site_geometry --set-front CLASS=DEG [CLASS=symmetric ...]
``--calibration-list`` and ``--set-front`` only read and write the committed file (no PBOs);
rebuild and --check need the installed PBOs (``--addons``). Offline results never establish
DayZ behaviour; the calibrated fronts are the lead's one-session measurements.
"""
import argparse
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
CATALOG = 'config/map-overlays/classes.json'
OUTPUT = 'config/sites/class-geometry.json'
VERSION = 1
MEMORY_LOD = 1e15
THRESHOLDS = {
    'door_end_fraction': 0.6,      # a door point is "at an end" beyond this share of the half length
    'near_square_aspect': 1.1,     # below this ratio there is no long axis
    'small_footprint_m': 0.5,      # longest footprint side at or below this: orientation unreadable
    'symmetry_tolerance': 0.05,    # of the footprint diagonal
}
DIRECTIONAL_KINDS = ('building', 'tent', 'wreck')
DIRECTIONAL_NAME_TOKENS = ('bed', 'radio')
# Props with no composable front: piles, stacks and omnidirectional obstacles. A composed site
# never aims them, so they need no calibration (the lead can still override with --set-front).
FRONT_AGNOSTIC = ('StaticObj_Decon_HazmatBag_01_F', 'StaticObj_Garbage_Pile1', 'StaticObj_Misc_Hedgehog_Concrete',
                  'StaticObj_Misc_Hedgehog_Iron', 'StaticObj_Misc_Pallets1', 'StaticObj_Misc_Pallets2',
                  'StaticObj_Misc_WoodPile1')
DOOR_NAME = re.compile(r'^(doors?\d+|doorstwin\d+)$')
CONVENTIONS = {
    'frame': 'model frame, metres: x right, y up, z forward, origin = placement origin',
    'front_yaw_deg': 'atan2(x, z) of the front vector in the model frame, clockwise from +z, [0, 360)',
    'yaw_rule': 'object yaw = target bearing - front_yaw_deg',
    'null_front': 'front_source calibration_pending means front_yaw_deg is null; refuse, never guess',
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def r3(value):
    return round(float(value) + 0.0, 3)


def r1(value):
    return round(float(value) + 0.0, 1)


def normalise_deg(value):
    return r1(float(value) % 360.0) % 360.0


def front_yaw_deg(x, z):
    """Bearing of a model-frame vector (x, z): clockwise from +z, [0, 360)."""
    return normalise_deg(math.degrees(math.atan2(x, z)))


# -- geometry measurement -------------------------------------------------------------

def hausdorff(a, b):
    """One-sided max over a of the distance to the nearest point of b (2D)."""
    worst = 0.0
    for px, pz in a:
        best = min((px - qx) * (px - qx) + (pz - qz) * (pz - qz) for qx, qz in b)
        worst = max(worst, best)
    return math.sqrt(worst)


def asymmetry(points_xz, center):
    """Fractions of the footprint diagonal: 180 deg turn, mirror x, mirror z about ``center``."""
    unique = sorted({(round(x - center[0], 3), round(z - center[1], 3)) for x, z in points_xz})
    xs = [p[0] for p in unique]
    zs = [p[1] for p in unique]
    diagonal = math.hypot(max(xs) - min(xs), max(zs) - min(zs))
    if not unique or diagonal <= 0.0:
        return {'mx': 0.0, 'mz': 0.0, 'r180': 0.0}
    turned = [(-x, -z) for x, z in unique]
    mirror_x = [(-x, z) for x, z in unique]
    mirror_z = [(x, -z) for x, z in unique]
    return {'mx': r3(hausdorff(unique, mirror_x) / diagonal),
            'mz': r3(hausdorff(unique, mirror_z) / diagonal),
            'r180': r3(hausdorff(unique, turned) / diagonal)}


def axis_info(footprint):
    """(long_axis, aspect) for [size_x, size_z]; the axis is None when nearly square."""
    low, high = sorted(footprint)
    aspect = high / low if low > 0 else 1.0
    if aspect < THRESHOLDS['near_square_aspect']:
        return None, r3(aspect)
    return ('x' if footprint[0] > footprint[1] else 'z'), r3(aspect)


def door_ends(door_points, center, footprint):
    """Which ends of the long axis carry door points: (axis, sorted signs) or None.

    ``door_points`` are model-frame (x, z); only points beyond the end fraction of the half
    length count (a side door sits near the middle of the long axis and is ignored).
    """
    axis, _ = axis_info(footprint)
    if axis is None:
        return None
    index = 0 if axis == 'x' else 1
    half = footprint[index] / 2.0
    signs = set()
    for point in door_points:
        along = point[index] - center[index]
        if abs(along) >= THRESHOLDS['door_end_fraction'] * half:
            signs.add(1 if along > 0 else -1)
    return (axis, sorted(signs)) if signs else None


def end_bearing(axis, sign):
    """Bearing of the +/- end of a model axis."""
    return front_yaw_deg(sign if axis == 'x' else 0.0, sign if axis == 'z' else 0.0)


def lod_points(model, lod):
    """Vertices of ``lod`` in the model frame (bounding centre restored), as (x, y, z)."""
    centre = model.bounding_center
    return [tuple(v[a] + centre[a] for a in range(3)) for v in lod.vertices]


def find_lod(model, resolution):
    for lod in model.lods:
        if math.isclose(lod.resolution, resolution, rel_tol=1e-6):
            return lod
    return None


def measure_model(model, box):
    """Measurements of one decoded model for a measured ``box`` ((min xyz), (max xyz)).

    Returns {'asymmetry': {...}, 'door_points': [[x, z], ...]}. The footprint points come from
    the Geometry LOD, else the nearest visual LOD; door points are the centroids of the
    memory-LOD selections named doors<N> / doorstwin<N>.
    """
    from tools.audit import world_mesh_audit as wma
    center = ((box[0][0] + box[1][0]) / 2.0, (box[0][2] + box[1][2]) / 2.0)
    lod = find_lod(model, wma.GEOMETRY)
    if lod is None or not lod.vertices:
        visual = [item for item in model.lods if 0 <= item.resolution < 1000 and item.vertices]
        lod = min(visual, key=lambda item: (item.resolution, item.index)) if visual else None
    points = [(p[0], p[2]) for p in lod_points(model, lod)] if lod is not None else []
    result = {'asymmetry': asymmetry(points, center) if points else None, 'door_points': []}
    memory = find_lod(model, MEMORY_LOD)
    if memory is not None:
        centre = model.bounding_center
        for selection in memory.named_selections:
            if not DOOR_NAME.match(selection.name.lower()):
                continue
            chosen = [memory.vertices[i] for i in selection.vertices if i < len(memory.vertices)]
            if chosen:
                result['door_points'].append([r3(sum(v[0] for v in chosen) / len(chosen) + centre[0]),
                                              r3(sum(v[2] for v in chosen) / len(chosen) + centre[2])])
    result['door_points'].sort()
    return result


# -- classification -------------------------------------------------------------------

def forced_directional(name, entry):
    lowered = name.lower()
    return entry.get('kind') in DIRECTIONAL_KINDS or any(t in lowered for t in DIRECTIONAL_NAME_TOKENS)


def classify(name, entry, footprint, asym, ends):
    """(symmetric?, fields) for one class; see the module docstring for the policy.

    ``ends`` is door_ends() output or None. Returns a dict with symmetric and either
    symmetry or front fields; no calibration is applied here.
    """
    axis, _ = axis_info(footprint)
    candidates = [0.0, 180.0] if axis == 'z' else [90.0, 270.0] if axis == 'x' else [0.0, 90.0, 180.0, 270.0]
    hint = None
    if ends is not None and len(ends[1]) == 1:
        hint = end_bearing(ends[0], ends[1][0])
    if entry.get('kind') == 'container' and ends is not None:
        if len(ends[1]) == 2:
            return {'symmetric': True, 'symmetry': 'two_fold_doors'}
        return {'symmetric': False, 'front_yaw_deg': hint, 'front_source': 'odol_memory'}
    pending = {'symmetric': False, 'front_yaw_deg': None, 'front_source': 'calibration_pending',
               'front_candidates_deg': candidates}
    if hint is not None:
        pending['memory_end_door_deg'] = hint
    if forced_directional(name, entry) or entry.get('kind') == 'container':
        return pending
    if name in FRONT_AGNOSTIC:
        return {'symmetric': True, 'symmetry': 'front_agnostic'}
    if max(footprint) <= THRESHOLDS['small_footprint_m']:
        return {'symmetric': True, 'symmetry': 'small'}
    if asym and max(asym.values()) <= THRESHOLDS['symmetry_tolerance']:
        return {'symmetric': True, 'symmetry': 'two_fold'}
    return pending


def overlay_calibration(row, value):
    """Apply one calibrated value (degrees or "symmetric") to a row; idempotent."""
    for key in ('front_candidates_deg', 'memory_end_door_deg', 'symmetry', 'front_yaw_deg', 'front_source'):
        row.pop(key, None)
    if value == 'symmetric':
        row['symmetric'] = True
        row['symmetry'] = 'calibrated'
    else:
        row['symmetric'] = False
        row['front_yaw_deg'] = normalise_deg(value)
        row['front_source'] = 'calibrated'
    return row


def pending_list(classes):
    return sorted(n for n, row in classes.items() if row.get('front_source') == 'calibration_pending')


def assemble(catalog, bounds, measures, calibrated=None):
    """Build the output document.

    catalog   classes.json["classes"]
    bounds    {name: {'min_m', 'max_m', 'size_m', 'footprint_m', 'source'}} (measured)
    measures  {name: measure_model() result} for measured classes
    calibrated {name: degrees | "symmetric"} lead results
    """
    calibrated = dict(calibrated or {})
    classes, unmeasured = {}, []
    for name in sorted(catalog):
        entry = catalog[name]
        info = bounds.get(name)
        if info is None:
            reserve = entry.get('footprint_reserve_m') or [0.0, 0.0]
            info = {'min_m': [r3(-reserve[0] / 2), 0.0, r3(-reserve[1] / 2)],
                    'max_m': [r3(reserve[0] / 2), 0.0, r3(reserve[1] / 2)],
                    'size_m': [r3(reserve[0]), 0.0, r3(reserve[1])],
                    'footprint_m': [r3(reserve[0]), r3(reserve[1])], 'source': 'reserve_unmeasured'}
            unmeasured.append(name)
        footprint = info['footprint_m']
        centre = [r3((info['min_m'][0] + info['max_m'][0]) / 2), r3((info['min_m'][2] + info['max_m'][2]) / 2)]
        measure = measures.get(name) or {'asymmetry': None, 'door_points': []}
        ends = door_ends(measure['door_points'], centre, footprint)
        axis, aspect = axis_info(footprint)
        row = {'bounds': {'footprint_m': [r3(v) for v in footprint], 'max_m': [r3(v) for v in info['max_m']],
                          'min_m': [r3(v) for v in info['min_m']], 'size_m': [r3(v) for v in info['size_m']],
                          'source': info['source']},
               'center_xz_m': centre, 'long_axis': axis, 'aspect': aspect}
        if measure['asymmetry'] is not None:
            row['asymmetry'] = dict(measure['asymmetry'])
        if info['source'] == 'reserve_unmeasured':
            if footprint[0] == footprint[1] and not forced_directional(name, entry):
                row.update(symmetric=True, symmetry='reserve_square')
            else:
                row.update(classify(name, entry, footprint, None, None))
        else:
            row.update(classify(name, entry, footprint, measure['asymmetry'], ends))
        if name in calibrated:
            overlay_calibration(row, calibrated[name])
        classes[name] = row
    return {'kind': 'hollow-country-class-geometry', 'version': VERSION, 'conventions': dict(CONVENTIONS),
            'thresholds': dict(THRESHOLDS),
            'calibrated': {n: calibrated[n] for n in sorted(calibrated) if n in catalog},
            'calibration_pending': pending_list(classes), 'unmeasured': sorted(unmeasured),
            'classes': classes}


def render(document):
    return json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + '\n'


# -- measurement from installed PBOs --------------------------------------------------

def measure_installed(catalog, addons):
    """(bounds, measures) for every catalogue class from the installed PBOs (read-only)."""
    from tools.audit import world_mesh_audit as wma
    installed = wma.Installed(Path(addons))
    result = wma.audit([], installed, catalog)
    proposal = wma.bounds_update(result, catalog)
    bounds = {n: {'min_m': row['geometry_min_m'], 'max_m': row['geometry_max_m'], 'size_m': row['size_m'],
                  'footprint_m': row['footprint_m'], 'source': 'geometry'}
              for n, row in proposal['classes'].items()}
    boxes = {n: (tuple(row['geometry_min_m']), tuple(row['geometry_max_m'])) for n, row in proposal['classes'].items()}
    for name in proposal['unmeasured']:
        model = installed.model(name)
        box = wma.contact_box(model)[0] if model is not None else None
        if box is not None:
            row = wma.class_bounds(box)
            bounds[name] = {'min_m': row['geometry_min_m'], 'max_m': row['geometry_max_m'],
                            'size_m': row['size_m'], 'footprint_m': row['footprint_m'], 'source': 'visual_lod'}
            boxes[name] = box
    measures = {}
    for name in sorted(boxes):
        measures[name] = measure_model(installed.model(name), boxes[name])
    return bounds, measures


def build(repo, addons, calibrated=None):
    catalog = read_json(Path(repo) / CATALOG)['classes']
    bounds, measures = measure_installed(catalog, addons)
    return assemble(catalog, bounds, measures, calibrated)


# -- calibration helpers --------------------------------------------------------------

def calibration_rows(document):
    rows = []
    for name in document['calibration_pending']:
        row = document['classes'][name]
        rows.append({'class': name, 'footprint_m': row['bounds']['footprint_m'], 'long_axis': row['long_axis'],
                     'candidates_deg': row.get('front_candidates_deg'),
                     'memory_end_door_deg': row.get('memory_end_door_deg')})
    return rows


def calibration_text(document):
    lines = ['%d classes need a front (front_yaw_deg is null until calibrated):' % len(document['calibration_pending'])]
    for row in calibration_rows(document):
        lines.append('%-40s footprint=%sx%s axis=%s candidates=%s end_door=%s' % (
            row['class'], row['footprint_m'][0], row['footprint_m'][1], row['long_axis'],
            row['candidates_deg'], row['memory_end_door_deg']))
    return '\n'.join(lines) + '\n'


def parse_set_front(items):
    result = {}
    for item in items:
        name, _, value = item.partition('=')
        if not name or not value:
            raise ValueError('expected CLASS=DEG or CLASS=symmetric: ' + item)
        result[name] = 'symmetric' if value == 'symmetric' else normalise_deg(float(value))
    return result


def set_front(document, updates):
    """Apply lead calibration to a loaded document; returns it (rows and lists recomputed)."""
    for name in updates:
        if name not in document['classes']:
            raise KeyError('unknown class: ' + name)
    document['calibrated'] = {n: v for n, v in sorted({**document['calibrated'], **updates}.items())}
    for name, value in updates.items():
        overlay_calibration(document['classes'][name], value)
    document['calibration_pending'] = pending_list(document['classes'])
    return document


def load_calibrated(path):
    path = Path(path)
    return read_json(path).get('calibrated', {}) if path.is_file() else {}


def main(argv=None):
    from tools.release.ship_inputs import ADDONS
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--addons', type=Path, default=ADDONS)
    parser.add_argument('--check', action='store_true', help='rebuild and compare bytes with the committed file')
    parser.add_argument('--calibration-list', action='store_true', help='print the classes that need a front')
    parser.add_argument('--json', action='store_true', help='with --calibration-list: JSON output')
    parser.add_argument('--set-front', nargs='+', metavar='CLASS=DEG|symmetric',
                        help='record lead calibration in the committed file (no PBOs needed)')
    args = parser.parse_args(argv)
    path = Path(args.repo) / OUTPUT
    if args.calibration_list:
        document = read_json(path)
        sys.stdout.write(json.dumps(calibration_rows(document), indent=2, sort_keys=True) + '\n' if args.json
                         else calibration_text(document))
        return 0
    if args.set_front:
        document = set_front(read_json(path), parse_set_front(args.set_front))
        path.write_text(render(document), encoding='utf-8')
        print('site_geometry: %d calibrated, %d pending' % (len(document['calibrated']),
                                                           len(document['calibration_pending'])))
        return 0
    if not Path(args.addons).is_dir() or not any(Path(args.addons).glob('*.pbo')):
        print('site_geometry: SKIP installed addons unavailable')
        return 2
    rendered = render(build(args.repo, args.addons, load_calibrated(path)))
    if args.check:
        current = path.read_text(encoding='utf-8') if path.is_file() else ''
        if current != rendered:
            print('site_geometry: STALE ' + OUTPUT + ' (rebuild without --check)')
            return 1
        print('site_geometry: ok')
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding='utf-8')
    print('site_geometry: wrote ' + OUTPUT)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
