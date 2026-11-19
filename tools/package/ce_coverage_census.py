"""Convert a native interior-sampler census into a ce-coverage-sampler-result (#11, CE apartment coverage).

    python3 tools/package/ce_coverage_census.py convert --census census.json --request ce-coverage-request.json \\
        --mission <stock mission dir> --out result.json --plan interior-sampler-plan.json \\
        [--min-calibration 0.6] [--reach-source strict|player] [--allow-empty-classes]

HC-57 optionally accepts --input apartments.json after the ordinary native conversion. It selects through
ce_coverage.select_input, including exact full-result byte/run/pin and stock category checks. Keep the full
external result when composing with ce_coverage.py --input; a subset is not the original source document.
Municipal-office survey input refuses explicitly; this converter does not qualify office geometry.

Input is the census.json that tools/setup/interior_sampler.py writes after a NATIVE run (kind
interior-sampler-census, door_phase_contract 2: floor-cell hit rows in the sampler frame per placement, plus
calibration placements and frame-check records). Points are never invented: the selection, the native frame
verdict, the door-semantics and calibration gates are tools/audit/interior_points.py (reused, not copied), and
every written point is one actual observed census hit of a selected floor cell (never a cross-placement
average), converted back to the stock prototype frame (``frame: stock``) and placed in the existing lootFloor
container. Calibration classes (barracks and the block
house) are evidence only and never become result groups.

Fields the result needs and where they come from:
  native_run_id   chosen by interior_sampler.py when the plan is staged (secrets.token_hex, never inside
                  Enforce), recorded as probe.native_run_id in interior-sampler-plan.json and echoed by the hook
                  into the census header. The census value must equal the plan's; a mismatch or a census
                  without one is refused
  prototype pin   the plan's mission_files entry for mapgroupproto.xml (sha256 and source_sha256) must equal the
                  request pin and the --mission file, checked before any calibration; a mismatch is refused
  hook_sha256     the plan's probe.hook_sha256 (the hook embeds the run id, so it cannot hash itself; a census
                  hook_sha256, if ever present, must equal the plan's)
  census_sha256   SHA-256 of the census file bytes
  mapgroupproto   the request's stock pin, which must equal the --mission mapgroupproto.xml (calibration needs
                  the stock points, so the stock mission is required)
The group bounds are the union of the usable placements' sampler boxes, converted to the stock frame. The
result is validated with ce_coverage.parse_result before it is written; the output must be a fresh file under
real (non-symlink) directories and may not be inside the repo's mission/ folder. It is written to a temporary
file in the same directory through a directory descriptor, fsynced and published without overwrite (hard link,
then the temporary is removed), so a failed write leaves no partial final file. Offline conversion never establishes DayZ behavior.
"""
import argparse
import errno
import json
import os
from pathlib import Path
import sys

try:
    from tools.audit import interior_points as pts
    from tools.package import ce_coverage as ce
except ImportError:  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.audit import interior_points as pts
    from tools.package import ce_coverage as ce

MAX_JSON_BYTES = pts.MAX_CENSUS_BYTES


def _object(data, what):
    if not isinstance(data, (bytes, bytearray)) or not data or len(data) > MAX_JSON_BYTES:
        raise ValueError(f'{what} must be non-empty bytes within the size bound')
    try:
        value = json.loads(bytes(data).decode('utf-8'), parse_constant=ce._reject_constant)
    except (ValueError, RecursionError) as error:
        raise ValueError(f'{what} is not readable JSON: {error}') from error
    if not isinstance(value, dict):
        raise ValueError(f'{what} must be a JSON object')
    return value


def _hex(value, pattern):
    return isinstance(value, str) and bool(pattern.fullmatch(value))


def _check_request(request):
    if request.get('kind') != ce.REQUEST_KIND or request.get('schema') != 1 or isinstance(request.get('schema'), bool):
        raise ValueError(f'request must be a {ce.REQUEST_KIND} schema 1 document')
    sources = request.get('sources')
    pin = sources.get(ce.PROTO) if isinstance(sources, dict) else None
    if not _hex(pin, ce.HEX64):
        raise ValueError(f'request has no {ce.PROTO} SHA-256 pin')
    classes = request.get('classes')
    names = [c.get('class') for c in classes if isinstance(c, dict)] if isinstance(classes, list) else []
    if names != list(ce.TARGET_GROUPS):
        raise ValueError('request classes must be exactly ' + ', '.join(ce.TARGET_GROUPS))
    for entry in classes:
        stock = entry.get('stock')
        containers = stock.get('containers') if isinstance(stock, dict) else None
        if not isinstance(containers, list) or pts.FLOOR_CONTAINER not in containers:
            raise ValueError(f'request class {entry["class"]} has no {pts.FLOOR_CONTAINER} container to receive points')
    return pin


def _plan_proto_pin(plan, stock_sha):
    """The plan's mission_files must pin exactly the stock prototype the request and mission carry."""
    files = plan.get('mission_files')
    entries = [e for e in files if isinstance(e, dict) and e.get('path') == ce.PROTO] if isinstance(files, list) else []
    if len(entries) != 1:
        raise ValueError(f'plan mission_files must list {ce.PROTO} exactly once (found {len(entries)}); the stock '
                         'prototype pin cannot be checked')
    entry = entries[0]
    for key in ('sha256', 'source_sha256'):
        if entry.get(key) != stock_sha:
            raise ValueError(f'plan {ce.PROTO} {key} does not match the request/mission {ce.PROTO}; the census '
                             'was sampled against a different stock prototype')


def _plan_pins(document, plan_bytes, stock_sha):
    """(hook pin) from the staged plan; the census run id and the stock prototype pin must be the plan's."""
    if plan_bytes is None:
        raise ValueError('the staged interior-sampler plan is required (it carries the hook pin and the run id '
                         'the census must echo)')
    plan = _object(plan_bytes, 'plan')
    probe = plan.get('probe')
    probe = probe if isinstance(probe, dict) else {}
    hook, planned = probe.get('hook_sha256'), probe.get('native_run_id')
    if plan.get('kind') != 'interior-sampler' or not _hex(hook, ce.HEX64) or not _hex(planned, ce.RUN_ID):
        raise ValueError('plan must be an interior-sampler plan with probe.hook_sha256 and probe.native_run_id')
    _plan_proto_pin(plan, stock_sha)
    if document.get('native_run_id') != planned:
        raise ValueError('census native_run_id does not match the plan native_run_id; the census is not from '
                         'the run this plan staged')
    echoed = document.get('hook_sha256')
    if echoed is not None and echoed != hook:
        raise ValueError('census hook_sha256 and the plan hook pin differ')
    return hook


def _check_census(document):
    run_id = document.get('native_run_id')
    if not _hex(run_id, ce.RUN_ID):
        raise ValueError('census has no valid native run id (native_run_id, 32 lowercase hex characters); '
                         'without one it is not attributable to a native run')
    allowed = set(pts.TENEMENT_CLASSES) | set(pts.CALIBRATION_CLASSES)
    for index, row in enumerate(document['placements']):
        if row['class'] not in allowed:
            raise ValueError(f'placement {index} has class {row["class"]}, which is not a tenement or a '
                             'calibration class')
    return run_id


def _bounds(document, name, frame):
    """Union of the usable placements' boxes of one class, in the stock frame."""
    low = high = None
    for row in document['placements']:
        if row['class'] != name or not pts._usable(row):
            continue
        for key in ('box_min', 'box_max'):
            box = row.get(key)
            if not isinstance(box, list) or len(box) != 3 or not all(pts._coordinate(v) for v in box):
                raise ValueError(f'a {name} placement has no finite {key}; group bounds cannot be derived')
        corners = [pts.sampler_to_stock(row[key], frame) for key in ('box_min', 'box_max')]
        row_low = [min(c[i] for c in corners) for i in range(3)]
        row_high = [max(c[i] for c in corners) for i in range(3)]
        low = row_low if low is None else [min(a, b) for a, b in zip(low, row_low)]
        high = row_high if high is None else [max(a, b) for a, b in zip(high, row_high)]
    if low is None:
        raise ValueError(f'no usable {name} placement carries a box')
    return {'min': [round(v, 6) + 0.0 for v in low], 'max': [round(v, 6) + 0.0 for v in high]}


def _observed_point(document, name, point, frame, reach_source):
    """The actual census hit that represents one selected cell, in the stock frame.

    The selection works on per-cell averages, so a candidate height can match no single hit. The written
    point is instead the qualifying observed hit of the same grid cell and storey (usable placement, selected
    filter's control passed, opened-door code 1, roofed clearance) nearest the candidate height; ties go to
    higher clearance, then lower height, then the earlier placement, so the choice is deterministic.
    """
    usable = [row for row in document['placements'] if row['class'] == name and pts._usable(row)]
    step = float(usable[0]['grid']['step'])
    origin_x, origin_z = float(usable[0]['box_min'][0]) + step / 2.0, float(usable[0]['box_min'][2]) + step / 2.0
    cell = (round((point['x'] - origin_x) / step), round((point['z'] - origin_z) / step))
    best = None
    for index, row in enumerate(usable):
        if not pts._gate_passed(row, reach_source):
            continue
        row_step = float(row['grid']['step'])
        bx, bz = float(row['box_min'][0]) + row_step / 2.0, float(row['box_min'][2]) + row_step / 2.0
        codes = pts._row_codes(row, reach_source, name)
        for hit, code in zip(row['hits'], codes):
            x, y, z, clearance = hit[0], hit[1], hit[2], hit[3]
            ix, iz = round((x - bx) / row_step), round((z - bz) / row_step)
            if (abs(x - (bx + ix * row_step)) > pts.OFF_GRID_TOLERANCE
                    or abs(z - (bz + iz * row_step)) > pts.OFF_GRID_TOLERANCE or (ix, iz) != cell):
                continue
            if (int(code) != 1 or clearance < pts.MIN_CLEARANCE - pts.EPSILON
                    or abs(y - point['y']) > pts.HEIGHT_SPREAD_BOUND + pts.EPSILON):
                continue
            key = (round(abs(y - point['y']), 9), -clearance, y, index)
            if best is None or key < best[0]:
                best = (key, (x, y, z))
    if best is None:
        raise ValueError(f'{name} selected cell ({point["x"]}, {point["z"]}) has no qualifying observed hit; '
                         'refusing to invent a point')
    return [round(v, 6) for v in pts.sampler_to_stock(best[1], frame)]


def convert(census_bytes, request_bytes, mission, plan_bytes=None, min_calibration=pts.DEFAULT_MIN_CALIBRATION,
            reach_source='strict', allow_empty_classes=False, input_bytes=None):
    """Return (result bytes, summary). Raise ValueError with the reason on anything not exactly native."""
    request_pin = _check_request(_object(request_bytes, 'request'))
    stock = ce._read_proto(mission)
    if ce.sha(stock) != request_pin:
        raise ValueError('request mapgroupproto.xml pin does not match the --mission mapgroupproto.xml')
    document = pts.parse_census(census_bytes)  # finite numbers, bounded rows, actual door phase, complete run
    run_id = _check_census(document)
    hook = _plan_pins(document, plan_bytes, request_pin)
    _treatment, report = pts.build_treatment(
        census_bytes, stock, min_calibration, max_total=ce.MAX_POINTS_PER_CONTAINER, reach_source=reach_source,
        allow_empty_classes=allow_empty_classes)
    frame = report['frame']['verdict']
    groups, counts, omitted = {}, {}, []
    for name in ce.TARGET_GROUPS:
        chosen = report['classes'][name]['points']
        counts[name] = len(chosen)
        if not chosen:
            omitted.append(name)
            continue
        groups[name] = {'bounds': _bounds(document, name, frame),
                        'containers': {pts.FLOOR_CONTAINER: [_observed_point(document, name, p, frame, reach_source)
                                                              for p in chosen]}}
    result = {'schema': 1, 'kind': ce.RESULT_KIND, 'native_run_id': run_id, 'frame': 'stock',
              'pins': {'mapgroupproto_sha256': request_pin, 'census_sha256': ce.sha(bytes(census_bytes)),
                       'hook_sha256': hook},
              'groups': groups}
    data = ce.encode(result)
    try:
        ce.parse_result(data)
    except ValueError as error:
        raise ValueError(f'converted result rejected by the coverage validator: {error}') from error
    summary = {'points': counts, 'omitted': omitted, 'frame': frame,
               'calibration': report['calibration'].get('min_coverage')}
    if input_bytes is not None:
        data = ce.select_input(data, input_bytes, stock)
        selected = ce.parse_result(data)
        summary['source_points'] = counts
        summary['points'] = {name: sum(len(p) for p in spec['containers'].values())
                             for name, spec in selected['groups'].items()}
    return data, summary


def _read(path, what):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError(f'{what} must be a regular file within the size bound: {path}')
    return path.read_bytes()


_DIR_FLAGS = (os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0)
              | getattr(os, 'O_CLOEXEC', 0))


def _checked_output(path):
    """The output as one absolute path with no ``..`` component, so the guard and the write name the same place."""
    if '..' in Path(path).parts:
        raise ValueError("output path must not contain '..' components")
    return Path(os.path.abspath(path))


def _open_parent(path):
    """Descriptor of the output's parent directory, opened component by component without following links."""
    if not (hasattr(os, 'O_DIRECTORY') and hasattr(os, 'O_NOFOLLOW') and os.open in os.supports_dir_fd
            and os.link in os.supports_dir_fd and os.unlink in os.supports_dir_fd):
        raise ValueError('output creation needs directory-descriptor operations (POSIX/WSL)')
    parts = _checked_output(path).parts
    if len(parts) < 2:
        raise ValueError('output must name a file')
    descriptor = os.open(parts[0], _DIR_FLAGS)
    try:
        for part in parts[1:-1]:
            try:
                child = os.open(part, _DIR_FLAGS, dir_fd=descriptor)
            except OSError as error:
                if error.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise ValueError(f'output directory component {part!r} is a symlink or not a directory') from error
                raise
            os.close(descriptor)
            descriptor = child
        return descriptor, parts[-1]
    except BaseException:
        os.close(descriptor)
        raise


def _write_all(descriptor, data):
    view = memoryview(data)
    while view:
        view = view[os.write(descriptor, view):]


def _publish(out, data):
    """Write ``data`` to the fresh file ``out``: temp file in the same directory, fsync, then link without overwrite."""
    out = _checked_output(out)
    ce._shipped_guard(out)
    parent, name = _open_parent(out)
    temp = f'.{name}.{os.getpid()}.{os.urandom(6).hex()}.tmp'
    try:
        descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
                             | getattr(os, 'O_CLOEXEC', 0), 0o666, dir_fd=parent)
        try:
            try:
                _write_all(descriptor, data)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            try:
                os.link(temp, name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
            except FileExistsError as error:
                raise ValueError('output must be a fresh file') from error
        finally:
            try:
                os.unlink(temp, dir_fd=parent)
            except FileNotFoundError:
                pass
        os.fsync(parent)
    finally:
        os.close(parent)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    cmd = sub.add_parser('convert', help='native census -> ce-coverage-sampler-result')
    cmd.add_argument('--census', required=True, help='census.json from a native interior-sampler run (one file)')
    cmd.add_argument('--request', required=True, help='ce-coverage-request.json from ce_coverage.py request')
    cmd.add_argument('--mission', required=True, help='stock mission directory (calibration needs its stock points)')
    cmd.add_argument('--out', required=True, help='fresh result file; never inside the repo mission/ folder')
    cmd.add_argument('--plan', required=True, help='interior-sampler-plan.json of the run that wrote the census')
    cmd.add_argument('--input', help='optional HC-57 named subset of this exact converted native result')
    cmd.add_argument('--min-calibration', type=float, default=pts.DEFAULT_MIN_CALIBRATION)
    cmd.add_argument('--reach-source', choices=pts.REACH_SOURCES, default='strict')
    cmd.add_argument('--allow-empty-classes', action='store_true',
                     help='omit (and report) a tenement class with no eligible point instead of refusing')
    args = parser.parse_args(argv)
    try:
        out = _checked_output(args.out)
        ce._shipped_guard(out)
        if os.path.lexists(out):
            raise ValueError('output must be a fresh file')
        data, summary = convert(_read(args.census, 'census'), _read(args.request, 'request'), args.mission,
                                plan_bytes=_read(args.plan, 'plan'),
                                min_calibration=args.min_calibration, reach_source=args.reach_source,
                                allow_empty_classes=args.allow_empty_classes,
                                input_bytes=_read(args.input, 'coverage input') if args.input else None)
        _publish(out, data)  # fresh, no-overwrite publish behind the same shipped-folder guard
    except (OSError, ValueError, OverflowError) as error:
        print(f'refused: {error}', file=sys.stderr)
        return 1
    print(f'wrote {out}: points {summary["points"]}, omitted {summary["omitted"]}, frame {summary["frame"]}; '
          'runtime acceptance stays pending')
    return 0


if __name__ == '__main__':
    sys.exit(main())
