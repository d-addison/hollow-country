"""W6 #60: measured cellar candidates, never runtime acceptance (stdlib only).

Native scripts-1.30.164289/3_Game/UndergroundAreaLoader.c:69-99 defines the
JSON fields; :105-132 loads the mission-root file; :156-169 spawns carriers.
4_World/Entities/ScriptedEntities/Triggers/UndergroundTrigger.c:10 limits indices
0..4095; :90-118 consumes FULL Size and classifies breadcrumb transitions.
4_World/Classes/UndergroundHandlerClient.c:203-277 uses WORLD breadcrumb points.

python3 -m tools.audit.cellar_triggers --measured <profile>/cellars-measured.json --out <external-dir>
Stop server, then: --install <external-dir> --mission <isolated-mission>
If mission file is absent, add --native-baseline <installed-world-cfgundergroundtriggers.json>.
Undo while stopped: --rollback --mission <isolated-mission>

No guessed stairs: annotate the sampler's class list with local StairTop and
StairBottom after inspecting the actual stairs, set StairsMeasured=true, rerun.
Confidence is a probe coverage score, not a calibrated probability or approval.
Generated instance coordinates and receipts stay outside every repository.
"""
import argparse
import json
import math
from pathlib import Path
import sys

# Allow the documented direct-file invocation as well as python -m.
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.package import optional_overlays as overlays

TRIGGER_FILE = 'cfgundergroundtriggers.json'
MAX_TRIGGERS = 4096
MAX_BYTES = 4 * 1024 * 1024
MIN_CONFIDENCE = 0.85


def number(value, bound=100000):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('finite bounded number required')
    if not math.isfinite(value) or abs(value) > bound:
        raise ValueError('finite bounded number required')
    return float(value)


def vec(value, bound=100000):
    # Enforce JSON serializers may emit vector as a space-separated string.
    if isinstance(value, str):
        value = [float(part) for part in value.split()]
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError('three-component vector required')
    return [number(part, bound) for part in value]


def world(local, origin, yaw):
    angle = math.radians(yaw)
    x, y, z = local
    return [round(origin[0] + x * math.cos(angle) + z * math.sin(angle), 5),
            round(origin[1] + y, 5),
            round(origin[2] - x * math.sin(angle) + z * math.cos(angle), 5)]


def box(low, high):
    if any(high[i] - low[i] < 0.5 for i in range(3)):
        raise ValueError('empty or too small cellar box')
    return [(low[i] + high[i]) / 2 for i in range(3)], [high[i] - low[i] for i in range(3)]


def trigger(comment, center, size, yaw, accommodation, crumbs):
    return {'Comment': comment, 'CustomSpawn': False, 'Position': center,
            'Orientation': [yaw, 0, 0], 'Size': size,
            'EyeAccommodation': accommodation, 'InterpolationSpeed': 0.5,
            'UseLinePointFade': bool(crumbs), 'AmbientSoundType': '',
            'AmbientSoundSet': '', 'Breadcrumbs': crumbs}


def generate(measured, threshold=MIN_CONFIDENCE):
    threshold = number(threshold, 1)
    if not MIN_CONFIDENCE <= threshold < 1:
        raise ValueError('confidence threshold must be >= 0.85 and < 1')
    if not isinstance(measured, dict):
        raise ValueError('measurement must be a JSON object')
    if measured.get('SchemaVersion') != 1 or measured.get('Complete') is not True:
        raise ValueError('complete schema-1 measurement required')
    if measured.get('WorldName', '').lower() != 'chernarusplus':
        raise ValueError('ChernarusPlus measurement required')
    classes = measured.get('Classes')
    if not isinstance(classes, list) or not 1 <= len(classes) <= 64:
        raise ValueError('1..64 measured classes required')
    report = {'runtime': 'PENDING', 'threshold': threshold, 'generated': 0, 'skipped': []}
    entries, seen_classes, seen_instances = [], set(), set()
    for row in classes:
        if not isinstance(row, dict):
            raise ValueError('class measurement must be an object')
        name = row.get('BuildingClass')
        if not isinstance(name, str) or not name.startswith('Land_') or name in seen_classes:
            raise ValueError('unique Land_ class required')
        seen_classes.add(name)
        reason = ''
        if number(row.get('Confidence', 0), 1) <= threshold:
            reason = 'confidence below or equal to threshold'
        elif row.get('SampleCount', 0) < 9:
            reason = 'fewer than nine geometric samples'
        elif row.get('StairsMeasured') is not True:
            reason = 'stair anchors unmeasured; no guessed transition'
        if reason:
            report['skipped'].append({'class': name, 'reason': reason})
            continue
        low, high = vec(row['BoxMin'], 64), vec(row['BoxMax'], 64)
        center, size = box(low, high)
        top, bottom = vec(row['StairTop'], 64), vec(row['StairBottom'], 64)
        if top[1] - bottom[1] < 0.75:
            raise ValueError(name + ': stairs must descend at least 0.75m')
        if not all(low[i] <= bottom[i] <= high[i] for i in range(3)):
            raise ValueError(name + ': stair bottom must meet the measured inner box')
        # Thin envelope around the actual stair endpoints, overlapping the inner
        # at the bottom. No enlargement of the dark room into upper floors.
        outer_low = [min(top[i], bottom[i]) - 0.75 for i in range(3)]
        outer_high = [max(top[i], bottom[i]) + 0.75 for i in range(3)]
        outer_center, outer_size = box(outer_low, outer_high)
        instances = row.get('Instances')
        if not isinstance(instances, list) or len(instances) > 8192:
            raise ValueError('bounded instance list required')
        for instance in instances:
            if instance.get('Eligible', True) is not True:
                report['skipped'].append({'class': name, 'reason': 'instance probe rejected',
                                          'position': instance.get('Position')})
                continue
            origin, yaw = vec(instance['Position']), number(instance['Yaw'], 360)
            identity = (name, *origin)
            if identity in seen_instances:
                raise ValueError('duplicate measured instance')
            seen_instances.add(identity)
            crumbs = [{'Position': world(point, origin, yaw), 'EyeAccommodation': eye,
                       'UseRaycast': False, 'Radius': 3, 'LightLerp': light,
                       'Comment': 'HC measured stair ' + label}
                      for point, eye, light, label in ((top, 1, False, 'top'), (bottom, 0, True, 'bottom'))]
            entries.append(trigger('HC cellar transition ' + name, world(outer_center, origin, yaw),
                                   outer_size, yaw, 1, crumbs))
            entries.append(trigger('HC cellar inner ' + name, world(center, origin, yaw), size, yaw, 0, []))
            if len(entries) > MAX_TRIGGERS:
                raise ValueError('native carrier index cap 4096 exceeded; no partial output')
    report['generated'] = len(entries)
    return {'Triggers': entries}, report


def load(path):
    return json.loads(overlays.read(path, MAX_BYTES), parse_constant=lambda text: reject(text))


def reject(text):
    raise ValueError('non-finite JSON value: ' + text)


def generate_files(measured_path, out, threshold):
    out = overlays.safe(out)
    # Check without creating a directory under a repository on rejected calls.
    if any((p / '.git').exists() for p in (out, *out.parents)):
        raise ValueError('generated cellar files must never enter a repository')
    if overlays.safe(str(measured_path) + '.tmp').exists():
        raise ValueError('interrupted measurement store: preserve .tmp and recover before generation')
    payload, report = generate(load(measured_path), threshold)
    if out.exists():
        raise ValueError('output directory exists; choose a new external directory')
    out.mkdir(parents=True)
    for name, data in ((TRIGGER_FILE, payload), ('cellar-trigger-report.json', report)):
        with (out / name).open('x', encoding='utf-8') as stream:
            json.dump(data, stream, indent=2, allow_nan=False)
            stream.write('\n')
    for skipped in report['skipped']:
        print('[HC Cellars] skipped class=' + skipped['class'] + ' reason=' + skipped['reason'])
    print('[HC Cellars] generated triggers=' + str(report['generated']) + ' runtime=PENDING')


def install_plan(generated, mission, baseline=None):
    mission = overlays.mission_target(mission)
    generated = overlays.safe(Path(generated) / TRIGGER_FILE)
    additions = load(generated).get('Triggers')
    if not isinstance(additions, list) or not additions:
        raise ValueError('no generated triggers to install')
    # Only our exact generated format is admitted; preserve native stock rows.
    required = set(trigger('', [0, 0, 0], [1, 1, 1], 0, 0, []))
    for row in additions:
        if set(row) != required or not row['Comment'].startswith('HC cellar '):
            raise ValueError('unexpected generated trigger format')
        vec(row['Position'])
        vec(row['Orientation'], 360)
        if any(v <= 0 for v in vec(row['Size'], 128)):
            raise ValueError('positive trigger size required')
    path = overlays.safe(mission / TRIGGER_FILE)
    before = overlays.read(path) if path.exists() else None
    if before is None and baseline is None:
        raise ValueError('mission has no trigger file: supply --native-baseline to preserve the native fallback')
    source = path if before is not None else overlays.safe(baseline)
    stock = load(source)
    if not isinstance(stock, dict) or not isinstance(stock.get('Triggers'), list):
        raise ValueError('native baseline needs a Triggers array')
    if len(stock['Triggers']) + len(additions) > MAX_TRIGGERS:
        raise ValueError('merged triggers exceed native carrier index cap 4096')
    stock['Triggers'].extend(additions)  # preserve every existing index and root field
    encoded = (json.dumps(stock, indent=2, allow_nan=False) + '\n').encode()
    if len(encoded) > overlays.MAX_BYTES:
        raise ValueError('merged trigger file exceeds receipt byte budget')
    return {'mission': str(mission), 'files': {TRIGGER_FILE: encoded},
            'before': {TRIGGER_FILE: before}, 'sources': {
                str(source): overlays.sha(overlays.read(source)),
                str(generated): overlays.sha(overlays.read(generated))}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--measured', type=Path)
    mode.add_argument('--install', type=Path, metavar='GENERATED_DIR')
    mode.add_argument('--rollback', action='store_true')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--mission', type=Path)
    parser.add_argument('--native-baseline', type=Path)
    parser.add_argument('--min-confidence', type=float, default=MIN_CONFIDENCE)
    args = parser.parse_args(argv)
    try:
        if args.measured:
            if args.out is None:
                raise ValueError('--out is required with --measured')
            generate_files(args.measured, args.out, args.min_confidence)
        else:
            if args.mission is None:
                raise ValueError('--mission is required')
            if args.rollback:
                overlays.rollback(args.mission, managed_name=overlays.CELLARS_MANAGED)
                print('[HC Cellars] overlay rolled back')
            else:
                candidate = install_plan(args.install, args.mission, args.native_baseline)
                overlays.install(candidate, args.mission, managed_name=overlays.CELLARS_MANAGED)
                print('[HC Cellars] overlay installed; restart required runtime=PENDING')
        return 0
    except (ValueError, KeyError, TypeError, OSError, OverflowError) as error:
        print('cellar triggers: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
