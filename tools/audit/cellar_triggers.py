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
HC-31: explicitly select at most two measured instances with SliceSelected=true
in an external review copy. This permits native rehearsal only; admitted stays 0.
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
MAX_SLICE_SPACES = 2
DEFAULTS_FILE = overlays.ROOT / 'mission/hollow-country/cellars/classes.json'


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


def instance_refusal(instance):
    reason = instance.get('Reason') or 'instance_probe_unmeasured_or_refused'
    if not isinstance(reason, str) or len(reason) > 128:
        return 'instance_probe_unmeasured_or_refused'
    return reason


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
    defaults = measured.get('TriggerDefaults')
    if not isinstance(defaults, dict):
        raise ValueError('authored TriggerDefaults required; no guessed distances')
    padding = number(defaults.get('StairEnvelopePaddingMeters'), 64)
    radius = number(defaults.get('BreadcrumbRadiusMeters'), 64)
    # Do not let a local override expand this first slice beyond its authored
    # defaults. These existing distances live only in the feature configuration.
    limits = load(DEFAULTS_FILE)['TriggerDefaults']
    if not 0 < padding <= limits['StairEnvelopePaddingMeters']:
        raise ValueError('stair envelope padding exceeds authored first-slice limit')
    if not 0 < radius <= limits['BreadcrumbRadiusMeters']:
        raise ValueError('breadcrumb radius exceeds authored first-slice limit')
    report = {'package': 'HC-31', 'runtime': 'PENDING', 'state': 'off',
              'threshold': threshold, 'generated': 0, 'admitted': 0,
              'cellar_measured': 0, 'pending': len(classes), 'selected': 0,
              'classes': [], 'skipped': [], 'refused': 'native_stair_route_unobserved'}
    entries, seen_classes, seen_instances = [], set(), set()
    instance_count = 0
    for row in classes:
        if not isinstance(row, dict):
            raise ValueError('class measurement must be an object')
        name = row.get('BuildingClass')
        if not isinstance(name, str) or not name.startswith('Land_') or len(name) > 128 or name in seen_classes:
            raise ValueError('unique Land_ class required')
        seen_classes.add(name)
        instances = row.get('Instances', [])
        if not isinstance(instances, list):
            raise ValueError('bounded instance list required')
        instance_count += len(instances)
        if instance_count > 8192 or any(not isinstance(i, dict) for i in instances):
            raise ValueError('bounded instance list required')
        task = row.get('SurveyTask', '')
        if not isinstance(task, str) or len(task) > 64:
            raise ValueError('bounded survey task ID required')
        disposition = {'class': name, 'task': task,
                       'state': 'pending', 'reason': 'native_survey_pending'}
        report['classes'].append(disposition)
        if any(i.get('GeometryMeasured') is True for i in instances):
            report['cellar_measured'] += 1
            disposition['reason'] = 'native_stair_route_unobserved'
        reason = ''
        if measured.get('SkippedTiles', 0) != 0:
            reason = 'incomplete_survey_skipped_tiles'
        elif row.get('Inconsistent') is True:
            reason = 'inconsistent_measured_boxes'
            disposition['state'] = 'refused'
        elif not instances:
            reason = 'native_survey_pending'
        elif number(row.get('Confidence', 0), 1) <= threshold:
            reason = 'confidence below or equal to threshold'
        elif row.get('SampleCount', 0) < 9:
            reason = 'fewer than nine geometric samples'
        elif row.get('StairsMeasured') is not True:
            reason = 'stair anchors unmeasured; no guessed transition'
        if reason:
            disposition['reason'] = reason
            report['skipped'].append({'class': name, 'reason': reason})
            # A class gate must not hide the actual failed stair samples that
            # lowered its confidence in the first place.
            for instance in instances:
                if instance.get('Eligible') is not True:
                    report['skipped'].append({'class': name, 'reason': instance_refusal(instance),
                                              'position': instance.get('Position')})
            continue
        # No missing-field acceptance, nor class-level promotion of every map
        # instance. Eligible here means probe candidate, NEVER runtime admission.
        selected = []
        for instance in instances:
            reason = ''
            if instance.get('Eligible') is not True:
                reason = instance_refusal(instance)
            elif instance.get('GeometryMeasured') is not True:
                reason = 'instance_geometry_unmeasured'
            elif instance.get('StairAnchorsValid') is not True:
                reason = 'stair_anchor_probe_failed_or_unmeasured'
            elif instance.get('SliceSelected') is not True:
                reason = 'native_slice_selection_pending'
            if reason:
                report['skipped'].append({'class': name, 'reason': reason,
                                          'position': instance.get('Position')})
                continue
            selected.append(instance)
        if not selected:
            continue
        report['selected'] += len(selected)
        if report['selected'] > MAX_SLICE_SPACES:
            raise ValueError('HC-31 permits at most two selected spaces; no partial output')
        low, high = vec(row['BoxMin'], 64), vec(row['BoxMax'], 64)
        center, size = box(low, high)
        top, bottom = vec(row['StairTop'], 64), vec(row['StairBottom'], 64)
        if top[1] - bottom[1] < 0.75:
            raise ValueError(name + ': stairs must descend at least 0.75m')
        if not all(low[i] <= bottom[i] <= high[i] for i in range(3)):
            raise ValueError(name + ': stair bottom must meet the measured inner box')
        # Bounded endpoint envelope overlaps the inner at the bottom. Exterior,
        # connected-room and upper-floor spill still need native qualification.
        outer_low = [min(top[i], bottom[i]) - padding for i in range(3)]
        outer_high = [max(top[i], bottom[i]) + padding for i in range(3)]
        outer_center, outer_size = box(outer_low, outer_high)
        for instance in selected:
            origin, yaw = vec(instance['Position']), number(instance['Yaw'], 360)
            identity = (name, *origin)
            if identity in seen_instances:
                raise ValueError('duplicate measured instance')
            seen_instances.add(identity)
            crumbs = [{'Position': world(point, origin, yaw), 'EyeAccommodation': eye,
                       'UseRaycast': False, 'Radius': radius, 'LightLerp': light,
                       'Comment': 'HC measured stair ' + label}
                      for point, eye, light, label in ((top, 1, False, 'top'), (bottom, 0, True, 'bottom'))]
            entries.append(trigger('HC cellar transition ' + name, world(outer_center, origin, yaw),
                                   outer_size, yaw, 1, crumbs))
            entries.append(trigger('HC cellar inner ' + name, world(center, origin, yaw), size, yaw, 0, []))
            if len(entries) > MAX_TRIGGERS:
                raise ValueError('native carrier index cap 4096 exceeded; no partial output')
    report['generated'] = len(entries)
    if entries:
        report['state'] = 'rehearsal_only'
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
    measured_bytes = overlays.read(measured_path, MAX_BYTES)
    payload, report = generate(json.loads(measured_bytes, parse_constant=reject), threshold)
    if out.exists():
        raise ValueError('output directory exists; choose a new external directory')
    encoded = (json.dumps(payload, indent=2, allow_nan=False) + '\n').encode()
    report['payload_sha256'] = overlays.sha(encoded)
    report['measurement_sha256'] = overlays.sha(measured_bytes)
    report_encoded = (json.dumps(report, indent=2, allow_nan=False) + '\n').encode()
    if max(len(encoded), len(report_encoded)) > MAX_BYTES:
        raise ValueError('generated cellar payload/report exceeds byte budget')
    out.mkdir(parents=True)
    with (out / TRIGGER_FILE).open('xb') as stream:
        stream.write(encoded)
    with (out / 'cellar-trigger-report.json').open('xb') as stream:
        stream.write(report_encoded)
    for skipped in report['skipped']:
        print('[HC Cellars] skipped class=' + skipped['class'] + ' reason=' + skipped['reason'])
    print('[HC Cellars] generated triggers=' + str(report['generated']) + ' runtime=PENDING')
    print('[HC Plan] HC-31 cellar_measured=' + str(report['cellar_measured'])
          + ' admitted=0 pending=' + str(report['pending'])
          + ' state=' + report['state'] + ' refused=native_stair_route_unobserved runtime=PENDING')


def install_plan(generated, mission, baseline=None):
    mission = overlays.mission_target(mission)
    generated = overlays.safe(Path(generated) / TRIGGER_FILE)
    generated_bytes = overlays.read(generated, MAX_BYTES)
    receipt_path = generated.parent / 'cellar-trigger-report.json'
    receipt_bytes = overlays.read(receipt_path, MAX_BYTES)
    receipt = json.loads(receipt_bytes, parse_constant=reject)
    if not isinstance(receipt, dict) or receipt.get('package') != 'HC-31':
        raise ValueError('HC-31 rehearsal report required')
    if receipt.get('payload_sha256') != overlays.sha(generated_bytes):
        raise ValueError('generated trigger hash drift')
    if receipt.get('runtime') != 'PENDING' or receipt.get('admitted') != 0 or receipt.get('state') != 'rehearsal_only':
        raise ValueError('rehearsal report cannot claim runtime admission')
    payload = json.loads(generated_bytes, parse_constant=reject)
    if not isinstance(payload, dict):
        raise ValueError('generated trigger object required')
    additions = payload.get('Triggers')
    if not isinstance(additions, list) or len(additions) not in (2, 4):
        raise ValueError('no generated triggers to install')
    if receipt.get('generated') != len(additions) or receipt.get('selected') != len(additions) // 2:
        raise ValueError('first-slice report counts disagree')
    # Only our exact generated format is admitted; preserve native stock rows.
    required = set(trigger('', [0, 0, 0], [1, 1, 1], 0, 0, []))
    for row in additions:
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError('unexpected generated trigger format')
        if not isinstance(row['Comment'], str) or not row['Comment'].startswith('HC cellar '):
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
    source_bytes = before if before is not None else overlays.read(source)
    stock = json.loads(source_bytes, parse_constant=reject)
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
                str(source): overlays.sha(source_bytes),
                str(generated): overlays.sha(generated_bytes),
                str(receipt_path): overlays.sha(receipt_bytes)}}


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
