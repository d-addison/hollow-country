"""Apartment (tenement) CE coverage delta: request, generate, install, rollback, validate (#11, #41).

Observed (EXP-CE-coverage): the Land_Tenement_Small and Land_Tenement_Big prototypes declare three containers,
lootmax 0 and ZERO raw points, so the CE census shows no loot there. Barracks have points and reach lootmax,
so barracks are NOT changed in v1; any barracks tuning is deferred until a baseline is measured.

Points are never invented. This tool only turns a NATIVE in-engine sampler result into authored <point>
entries inside the existing containers of those two groups, plus a conservative lootmax, and patches the
mission's mapgroupproto.xml in place with a receipt and a byte-exact rollback. Without a native result it
produces nothing, and `validate` reports the work as pending.

  request   write the sampler request (class list, stock pins, the native sampler command, the result contract)
  generate  --sampler-result R --mission M --out D     result -> delta (refuses anything not native/in bounds)
  install   --delta D --mission M                       patch mapgroupproto.xml (backup + receipt written first)
  rollback  --mission M                                 restore the backup byte-exactly (also recovers an
                                                        interrupted install); refuses drift, links, hard links
  validate  [--sampler-result R] [--mission M]          pending when no sampler result is shipped

The result (``ce-coverage-sampler-result``, schema 1) is produced from a native census run of
tools/setup/interior_sampler.py. It carries the 32-hex native run id, three SHA-256 pins (the stock
mapgroupproto.xml the points belong to, the census file, the hook), ``frame: stock`` (points already converted
back to the prototype frame), and per group a bounding box plus points per existing container. The managed
folder hollow-country-ce-coverage collides with no other installer. Install economy first; roll back this
delta before the economy delta, because the economy rollback pins mapgroupproto.xml as stock input.
Offline tests never establish DayZ behavior; engine acceptance stays pending.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

try:
    from tools.package import economy
except ImportError:  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.package import economy

REPO_ROOT = Path(__file__).resolve().parents[2]
MANAGED = 'hollow-country-ce-coverage'
TARGET_GROUPS = ('Land_Tenement_Small', 'Land_Tenement_Big')
SHIPPED_RESULT = Path('mission/hollow-country/ce-coverage/sampler-result.json')
PROTO = 'mapgroupproto.xml'
DELTA_FILES = {'coverage-delta.json', 'delta-manifest.json'}
MANAGED_FILES = {'receipt.json', 'mapgroupproto.backup', 'coverage-delta.json', 'mapgroupproto.next'}
RESULT_KIND = 'ce-coverage-sampler-result'
DELTA_KIND = 'ce-coverage-delta'
REQUEST_KIND = 'ce-coverage-request'
PIN_NAMES = ('mapgroupproto_sha256', 'census_sha256', 'hook_sha256')
# Reviewed caps. Provisional: chosen conservative, to be re-judged against a native baseline.
MAX_POINTS_PER_CONTAINER = 24
MAX_CONTAINER_LOOTMAX = 6
MAX_GROUP_LOOTMAX = 12
LOOT_RATIO = 0.25
POINT_RANGE = '0.400000'
POINT_HEIGHT = '1.000000'
MAX_COORDINATE = 1000.0
MAX_EXTENT = 200.0
MAX_RESULT_BYTES = 1024 * 1024
MAX_PROTO_BYTES = 16 * 1024 * 1024
SAMPLER_TOOL = 'tools/setup/interior_sampler.py'
SAMPLER_PER_CLASS = 16
NAME = re.compile(r'[A-Za-z0-9_]{1,64}')
HEX64 = re.compile(r'[0-9a-f]{64}')
RUN_ID = re.compile(r'[0-9a-f]{32}')
PENDING = ('no native sampler result is shipped; apartment coverage stays pending until a native sampler run '
           'produces one')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return economy.encode(value)


def _reject_constant(name):
    raise ValueError(f'non-finite JSON constant {name}')


def _json(data, what):
    if not isinstance(data, (bytes, bytearray)) or not data or len(data) > MAX_RESULT_BYTES:
        raise ValueError(f'{what} must be non-empty bytes within the size bound')
    try:
        value = json.loads(bytes(data).decode('utf-8'), parse_constant=_reject_constant)
    except RecursionError as error:
        raise ValueError(f'{what} nesting too deep') from error
    if not isinstance(value, dict):
        raise ValueError(f'{what} must be a JSON object')
    return value


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value) and abs(value) <= MAX_COORDINATE
    except OverflowError:
        return False


def _clean(value):
    return round(float(value), 6) + 0.0  # + 0.0 turns -0.0 into 0.0


def _triple(values, what):
    if not isinstance(values, list) or len(values) != 3 or not all(_number(v) for v in values):
        raise ValueError(f'{what} must be three finite numbers within +/-{MAX_COORDINATE:g}')
    return tuple(_clean(v) for v in values)


def _pos(point):
    return '%.6f %.6f %.6f' % point


# ------------------------------------------------------------------------------------------------ result


def _exact(doc, keys, what):
    if not isinstance(doc, dict) or set(doc) != set(keys):
        raise ValueError(f'{what} keys must be exactly: ' + ', '.join(sorted(keys)))


def parse_result(data):
    """Validate a native sampler result; return it normalized (sorted, rounded) or raise ValueError."""
    doc = _json(data, 'sampler result')
    _exact(doc, ('schema', 'kind', 'native_run_id', 'frame', 'pins', 'groups'), 'sampler result')
    if doc['schema'] != 1 or isinstance(doc['schema'], bool) or doc['kind'] != RESULT_KIND:
        raise ValueError(f'sampler result must be {RESULT_KIND} schema 1')
    run_id = doc['native_run_id']
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ValueError('a native run id (32 lowercase hex characters) is required; a result without one '
                         'is not a native observation')
    if doc['frame'] != 'stock':
        raise ValueError('frame must be "stock": points are in the prototype frame, not the sampler frame')
    pins = doc['pins']
    _exact(pins, PIN_NAMES, 'pins')
    if not all(isinstance(pins[n], str) and HEX64.fullmatch(pins[n]) for n in PIN_NAMES):
        raise ValueError('every pin must be a lowercase SHA-256 hex digest')
    groups = doc['groups']
    if not isinstance(groups, dict) or not groups:
        raise ValueError('groups must name at least one tenement group')
    if set(groups) - set(TARGET_GROUPS):
        raise ValueError('only the tenement groups may be covered: ' + ', '.join(TARGET_GROUPS))
    normalized = {}
    for name in TARGET_GROUPS:
        if name in groups:
            normalized[name] = _group(name, groups[name])
    return {'run_id': run_id, 'pins': dict(pins), 'groups': normalized}


def _group(name, doc):
    _exact(doc, ('bounds', 'containers'), f'group {name}')
    _exact(doc['bounds'], ('min', 'max'), f'{name} bounds')
    low, high = _triple(doc['bounds']['min'], f'{name} bounds min'), _triple(doc['bounds']['max'], f'{name} bounds max')
    if any(h <= l or h - l > MAX_EXTENT for l, h in zip(low, high)):
        raise ValueError(f'{name} bounds must have min < max and an extent of at most {MAX_EXTENT:g} m')
    containers = doc['containers']
    if not isinstance(containers, dict) or not containers:
        raise ValueError(f'{name} needs at least one container with points')
    seen, result = set(), {}
    for container in sorted(containers):
        if not isinstance(container, str) or not NAME.fullmatch(container):
            raise ValueError(f'{name} has an invalid container name')
        raw = containers[container]
        if not isinstance(raw, list) or not raw:
            raise ValueError(f'{name}/{container} needs at least one point')
        if len(raw) > MAX_POINTS_PER_CONTAINER:
            raise ValueError(f'{name}/{container} exceeds the reviewed cap of {MAX_POINTS_PER_CONTAINER} points')
        points = []
        for raw_point in raw:
            point = _triple(raw_point, f'{name}/{container} point')
            if any(not l <= v <= h for v, l, h in zip(point, low, high)):
                raise ValueError(f'{name}/{container} has a point outside the prototype bounds')
            if _pos(point) in seen:
                raise ValueError(f'{name} has a duplicate point (duplicate loot positions are refused)')
            seen.add(_pos(point))
            points.append(point)
        result[container] = sorted(points)
    return {'bounds': (low, high), 'containers': result}


def lootmax_for(count):
    return min(MAX_CONTAINER_LOOTMAX, max(1, math.ceil(count * LOOT_RATIO - 1e-9)))


def build_delta(result, source_sha):
    """The delta document (a plain, deterministic structure) for a normalized result."""
    groups = {}
    for name in TARGET_GROUPS:
        if name not in result['groups']:
            continue
        spec = result['groups'][name]
        containers = {c: {'lootmax': lootmax_for(len(p)), 'points': [list(x) for x in p]}
                      for c, p in sorted(spec['containers'].items())}
        groups[name] = {'bounds': {'min': list(spec['bounds'][0]), 'max': list(spec['bounds'][1])},
                        'lootmax': min(MAX_GROUP_LOOTMAX, sum(c['lootmax'] for c in containers.values())),
                        'containers': containers}
    return {'schema': 1, 'kind': DELTA_KIND, 'native_run_id': result['run_id'], 'frame': 'stock',
            'pins': dict(result['pins']), 'source': {'mapgroupproto_sha256': source_sha},
            'caps': {'points_per_container': MAX_POINTS_PER_CONTAINER, 'container_lootmax': MAX_CONTAINER_LOOTMAX,
                     'group_lootmax': MAX_GROUP_LOOTMAX, 'loot_ratio': LOOT_RATIO},
            'groups': groups, 'runtime_acceptance': 'pending'}


# ------------------------------------------------------------------------------------------------ stock proto


def _text(data):
    if not isinstance(data, (bytes, bytearray)) or len(data) > MAX_PROTO_BYTES:
        raise ValueError('mapgroupproto.xml is missing or too large')
    text = bytes(data).decode('utf-8')  # strict UTF-8; a BOM survives as the first character and is written back
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper() or '\x00' in text:
        raise ValueError('mapgroupproto.xml declares a DTD or contains NUL')
    return text


def _parse(data):
    _text(data)
    try:
        root = ET.fromstring(bytes(data))
    except ET.ParseError as error:
        raise ValueError('mapgroupproto.xml is not well-formed') from error
    return root


def _read_proto(mission):
    path = Path(mission).absolute() / PROTO
    if not path.is_file() or path.stat().st_size > MAX_PROTO_BYTES:
        raise ValueError('mission has no readable mapgroupproto.xml')
    return path.read_bytes()


def _shell(root, name, wanted=None):
    """The container names of an empty lootmax-0 tenement group, else ValueError."""
    found = [g for g in root.iter('group') if g.get('name') == name]
    if len(found) != 1:
        raise ValueError(f'stock must have exactly one group {name}, found {len(found)}')
    group = found[0]
    containers = group.findall('container')
    if (group.get('lootmax') != '0' or group.findall('.//point') or not containers
            or any(c.get('lootmax') != '0' for c in containers)):
        raise ValueError(f'group {name} is not an empty lootmax-0 shell (stock lootmax or authored points present)')
    names = [c.get('name') for c in containers]
    for wanted_name in (wanted or ()):
        if names.count(wanted_name) != 1:
            raise ValueError(f'group {name} has no single container named {wanted_name}')
    return names


def _group_block(text, name):
    matches = list(re.finditer(r'<group\b[^>]*\bname="%s"[^>]*>' % re.escape(name), text))
    if len(matches) != 1 or matches[0].group(0).endswith('/>'):
        raise ValueError(f'expected exactly one open group {name} written with double quotes')
    end = text.find('</group>', matches[0].end())
    if end < 0:
        raise ValueError(f'group {name} is not closed')
    return matches[0].start(), end + len('</group>')


def _set_lootmax(tag, value):
    changed, count = re.subn(r'\blootmax="0"', 'lootmax="%d"' % value, tag, count=1)
    if count != 1:
        raise ValueError('stock lootmax is not 0; refusing to overwrite authored data')
    return changed


def _edit_group(block, spec):
    eol = '\r\n' if '\r\n' in block else '\n'
    opening = re.match(r'<group\b[^>]*>', block)
    located = []
    for name in spec['containers']:
        found = list(re.finditer(r'<container\b[^>]*\bname="%s"[^>]*>' % re.escape(name), block))
        if len(found) != 1 or found[0].group(0).endswith('/>'):
            raise ValueError(f'expected exactly one open container {name}')
        located.append((found[0], name))
    for match, name in sorted(located, key=lambda item: item[0].start(), reverse=True):
        close = block.find('</container>', match.end())
        if close < 0:
            raise ValueError(f'container {name} is not closed')
        line_start = block.rfind('\n', 0, close) + 1
        if line_start <= match.end() - 1 or block[line_start:close].strip():
            raise ValueError(f'container {name} end tag is not on its own line')
        children = [line for line in block[match.end():line_start].splitlines() if line.strip()]
        indent = re.match(r'[ \t]*', children[-1]).group(0) if children else block[line_start:close] + '\t'
        lines = ''.join('%s<point pos="%s" range="%s" height="%s" />%s'
                        % (indent, _pos(tuple(p)), POINT_RANGE, POINT_HEIGHT, eol)
                        for p in spec['containers'][name]['points'])
        block = (block[:match.start()] + _set_lootmax(match.group(0), spec['containers'][name]['lootmax'])
                 + block[match.end():line_start] + lines + block[line_start:])
    return _set_lootmax(opening.group(0), spec['lootmax']) + block[opening.end():]


def _strip(text, names):
    for name in names:
        start, end = _group_block(text, name)
        text = text[:start] + '\x00' + text[end:]
    return text


def apply_delta(stock, delta):
    """Return the stock mapgroupproto bytes with the delta's points and lootmax added, nothing else changed."""
    text = _text(stock)
    root = _parse(stock)
    edits = []
    for name in TARGET_GROUPS:
        if name in delta['groups']:
            spec = delta['groups'][name]
            _shell(root, name, spec['containers'])
            start, end = _group_block(text, name)
            edits.append((start, end, spec))
    for start, end, spec in sorted(edits, key=lambda e: e[0], reverse=True):
        text = text[:start] + _edit_group(text[start:end], spec) + text[end:]
    output = text.encode('utf-8')
    _verify(stock, output, delta)
    return output


def _skeleton(group):
    return [(e.tag, e.get('name')) for e in group.iter() if e.tag in ('usage', 'container', 'category', 'tag')]


def _verify(stock, output, delta):
    before, after = _parse(stock), _parse(output)
    old = [(g.get('name'), g) for g in before.iter('group')]
    new = [(g.get('name'), g) for g in after.iter('group')]
    if [n for n, _ in old] != [n for n, _ in new]:
        raise ValueError('patch changed the set or order of groups')
    for (name, was), (_, now) in zip(old, new):
        spec = delta['groups'].get(name)
        if spec is None:
            if ET.tostring(was) != ET.tostring(now):
                raise ValueError(f'patch changed group {name}')
            continue
        if _skeleton(was) != _skeleton(now) or now.get('lootmax') != str(spec['lootmax']):
            raise ValueError(f'patch altered the structure of {name}')
        for container in now.findall('container'):
            written = container.findall('point')
            planned = spec['containers'].get(container.get('name'))
            if planned is None:
                if written or container.get('lootmax') != '0':
                    raise ValueError(f'patch touched container {container.get("name")} of {name}')
                continue
            if ([p.get('pos') for p in written] != [_pos(tuple(p)) for p in planned['points']]
                    or container.get('lootmax') != str(planned['lootmax'])
                    or any(set(p.attrib) != {'pos', 'range', 'height'} for p in written)):
                raise ValueError(f'patch points of {name} do not match the delta')
    names = [n for n in TARGET_GROUPS if n in delta['groups']]
    if _strip(_text(stock), names) != _strip(_text(output), names):
        raise ValueError('patch changed bytes outside the tenement groups')


# ------------------------------------------------------------------------------------------------ request / generate


def _shipped_guard(path):
    resolved = Path(os.path.realpath(path))
    shipped = Path(os.path.realpath(REPO_ROOT / 'mission'))
    if resolved == shipped or shipped in resolved.parents:
        raise ValueError('refusing to write generated coverage data into the shipped mission folder')


def request(mission):
    """Bytes of the sampler request: what to sample natively and what result the generator will accept."""
    stock = _read_proto(mission)
    root = _parse(stock)
    classes = [{'class': name, 'stock': {'lootmax': 0, 'points': 0, 'containers': _shell(root, name)}}
               for name in TARGET_GROUPS]
    sources = {PROTO: sha(stock)}
    pos = Path(mission).absolute() / 'mapgrouppos.xml'
    if pos.is_file() and pos.stat().st_size <= MAX_PROTO_BYTES:
        sources['mapgrouppos.xml'] = sha(pos.read_bytes())
    return encode({
        'schema': 1, 'kind': REQUEST_KIND, 'classes': classes, 'sources': sources,
        'sampler': {'tool': SAMPLER_TOOL, 'kind': 'interior-sampler',
                    'classes': list(TARGET_GROUPS),
                    'command': ['python3', SAMPLER_TOOL, '--destination', '<fresh runtime directory; must not exist>',
                                '--per-class', str(SAMPLER_PER_CLASS)],
                    'note': 'Run natively; convert the census to the result below. Points must be native floor '
                            'positions of the exact prototype, never hand-authored.'},
        'result_contract': {'kind': RESULT_KIND, 'schema': 1, 'frame': 'stock',
                            'native_run_id': '32 lowercase hex characters from the native run',
                            'pins': list(PIN_NAMES),
                            'groups': 'per group: bounds {min,max} and points [[x,y,z]] per existing container',
                            'caps': {'points_per_container': MAX_POINTS_PER_CONTAINER,
                                     'container_lootmax': MAX_CONTAINER_LOOTMAX,
                                     'group_lootmax': MAX_GROUP_LOOTMAX}},
        'barracks': 'unchanged in v1; barracks have native points and reach lootmax, tuning is deferred',
        'runtime_acceptance': 'pending'})


def write_request(out, data):
    out = Path(out)
    _shipped_guard(out)
    try:
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o666)
    except FileExistsError as error:
        raise ValueError('output must be a fresh file') from error
    with os.fdopen(fd, 'wb') as handle:
        handle.write(data)


def generate(result_bytes, mission):
    """The delta file set for a native sampler result against the mission's stock mapgroupproto.xml."""
    result = parse_result(result_bytes)
    stock = _read_proto(mission)
    if result['pins']['mapgroupproto_sha256'] != sha(stock):
        raise ValueError('result pin mapgroupproto_sha256 does not match the mission mapgroupproto.xml')
    root = _parse(stock)
    for name, spec in result['groups'].items():
        _shell(root, name, spec['containers'])
    document = build_delta(result, sha(stock))
    apply_delta(stock, document)  # dry run: a stock layout that cannot be patched exactly is refused now
    delta = encode(document)
    manifest = encode({'schema': 1, 'sources': {PROTO: sha(stock)}, 'files': {'coverage-delta.json': sha(delta)},
                       'runtime_acceptance': 'pending'})
    return {'coverage-delta.json': delta, 'delta-manifest.json': manifest}


def write_delta(stage, files):
    stage = Path(stage)
    _shipped_guard(stage)
    if set(files) != DELTA_FILES:
        raise ValueError('unexpected generated file set')
    if os.path.lexists(stage):
        raise ValueError('output must be a fresh directory')
    stage.mkdir(parents=True)
    for name, data in files.items():
        economy.fresh_write(stage, name, data)


# ------------------------------------------------------------------------------------------------ install / rollback


def _target(target):
    target = Path(target).absolute()
    economy.child(target, PROTO)
    if not target.is_dir() or 'steamapps' in (part.lower() for part in target.parts):
        raise ValueError('install requires an isolated existing mission copy outside Steam')
    return target


def _load_delta(stage):
    stage = Path(stage)
    found = set()
    for path in stage.rglob('*'):
        economy.child(stage, path.relative_to(stage).as_posix())
        if path.is_file():
            found.add(path.relative_to(stage).as_posix())
        elif not path.is_dir():
            raise ValueError('special stage file')
    if found != DELTA_FILES:
        raise ValueError('unexpected or missing stage files')
    files = {name: economy.child(stage, name).read_bytes() for name in found}
    manifest = _json(files['delta-manifest.json'], 'delta manifest')
    if (manifest.get('schema') != 1 or set(manifest) != {'schema', 'sources', 'files', 'runtime_acceptance'}
            or manifest['runtime_acceptance'] != 'pending' or not isinstance(manifest['sources'], dict)
            or set(manifest['sources']) != {PROTO} or not isinstance(manifest['files'], dict)
            or set(manifest['files']) != {'coverage-delta.json'}):
        raise ValueError('invalid delta manifest')
    if manifest['files']['coverage-delta.json'] != sha(files['coverage-delta.json']):
        raise ValueError('delta checksum mismatch')
    return files, manifest


def checked_delta(data, manifest):
    """Re-derive the delta from its own content; a delta that is not exactly what generate emits is refused."""
    delta = _json(data, 'delta')
    try:
        result = parse_result(json.dumps({
            'schema': 1, 'kind': RESULT_KIND, 'native_run_id': delta['native_run_id'], 'frame': delta['frame'],
            'pins': delta['pins'],
            'groups': {name: {'bounds': spec['bounds'],
                              'containers': {c: row['points'] for c, row in spec['containers'].items()}}
                       for name, spec in delta['groups'].items()}}).encode())
        source = delta['source']['mapgroupproto_sha256']
        rebuilt = encode(build_delta(result, source))
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('delta content is malformed') from error
    if rebuilt != bytes(data):
        raise ValueError('delta content is not what generate emits (caps, lootmax or layout differ)')
    if not isinstance(source, str) or not HEX64.fullmatch(source) or source != manifest['sources'][PROTO]:
        raise ValueError('delta source pin differs from the manifest')
    if result['pins']['mapgroupproto_sha256'] != source:
        raise ValueError('delta result pin differs from its source pin')
    return delta


def _stage_next(managed, data, like):
    staged = economy.fresh_write(managed, 'mapgroupproto.next', data)
    os.chmod(staged, os.lstat(like).st_mode & 0o777)
    return staged


def install(stage, target):
    target = _target(target)
    managed = economy.child(target, MANAGED)
    if os.path.lexists(managed):
        raise ValueError('already installed or interrupted installation; inspect/rollback first')
    files, manifest = _load_delta(stage)
    delta = checked_delta(files['coverage-delta.json'], manifest)
    proto = economy.plain_file(target, economy.child(target, PROTO))
    original = proto.read_bytes()
    if sha(original) != delta['source']['mapgroupproto_sha256']:
        raise ValueError('target mapgroupproto.xml differs from the delta source pin; regenerate')
    patched = apply_delta(original, delta)
    receipt = {'schema': 1, 'before': sha(original), 'after': sha(patched),
               'delta_sha256': sha(files['coverage-delta.json']), 'native_run_id': delta['native_run_id'],
               'runtime_acceptance': 'pending'}
    managed.mkdir()
    # Receipt first, then backup and delta; the atomic switch comes last. A run killed anywhere before the
    # switch leaves the mission untouched, and rollback recognises every one of those states.
    economy.fresh_write(managed, 'receipt.json', encode(receipt))
    economy.fresh_write(managed, 'mapgroupproto.backup', original)
    economy.fresh_write(managed, 'coverage-delta.json', files['coverage-delta.json'])
    os.replace(_stage_next(managed, patched, proto), proto)
    return receipt


def _preflight(managed):
    managed = Path(managed)
    if managed.is_symlink() or not managed.is_dir():
        raise ValueError('managed path is a symlink or not a directory')
    for path in managed.rglob('*'):
        name = path.relative_to(managed).as_posix()
        economy.child(managed, name)
        if path.is_dir() and not path.is_symlink():
            raise ValueError('unexpected managed directory; rollback refuses deletion')
        if name not in MANAGED_FILES:
            raise ValueError('unexpected managed file; rollback refuses deletion')
        economy.plain_file(managed, path)


def _receipt(managed):
    try:
        receipt = _json(economy.read_plain(managed, 'receipt.json'), 'receipt')
    except ValueError:
        return None
    keys = {'schema', 'before', 'after', 'delta_sha256', 'native_run_id', 'runtime_acceptance'}
    if (set(receipt) != keys or receipt['schema'] != 1 or receipt['runtime_acceptance'] != 'pending'
            or not all(isinstance(receipt[k], str) and HEX64.fullmatch(receipt[k])
                       for k in ('before', 'after', 'delta_sha256'))
            or not isinstance(receipt['native_run_id'], str) or not RUN_ID.fullmatch(receipt['native_run_id'])):
        return None
    return receipt


def rollback(target):
    target = _target(target)
    managed = economy.child(target, MANAGED)
    if not os.path.lexists(managed):
        raise ValueError('no coverage installation to roll back')
    _preflight(managed)
    proto = economy.plain_file(target, economy.child(target, PROTO))
    present = {p.name for p in managed.iterdir()}
    receipt = _receipt(managed) if 'receipt.json' in present else None
    switched = False
    if receipt is None:
        # No usable receipt. The receipt is written before the backup and the backup before the switch, so
        # with no backup the mission cannot have been touched. A backup beside a bad receipt is not safe.
        if 'receipt.json' in present and 'mapgroupproto.backup' in present:
            raise ValueError('invalid receipt next to a backup; manual reconciliation required')
    else:
        current = sha(proto.read_bytes())
        if current == receipt['after'] and receipt['after'] != receipt['before']:
            switched = True
        elif current != receipt['before']:
            raise ValueError('mapgroupproto drift; manual reconciliation required')
        if switched:
            if ('mapgroupproto.backup' not in present
                    or sha(economy.read_plain(managed, 'mapgroupproto.backup')) != receipt['before']):
                raise ValueError('backup is missing or does not match the receipt; manual reconciliation required')
            if ('coverage-delta.json' not in present
                    or sha(economy.read_plain(managed, 'coverage-delta.json')) != receipt['delta_sha256']):
                raise ValueError('installed delta drift; inspect before rollback')
    if switched:
        os.replace(_stage_next(managed, economy.read_plain(managed, 'mapgroupproto.backup'), proto), proto)
    shutil.rmtree(managed)  # only our fixed directory, preflighted above
    return {'restored': switched}


# ------------------------------------------------------------------------------------------------ validate


def validate(result_path=None, mission=None):
    path = Path(result_path) if result_path is not None else REPO_ROOT / SHIPPED_RESULT
    if not path.is_file():
        return {'status': 'pending', 'reason': PENDING, 'groups': list(TARGET_GROUPS),
                'runtime_acceptance': 'pending'}
    data = path.read_bytes()
    result = parse_result(data)
    if mission is not None:
        generate(data, mission)
    return {'status': 'result-valid', 'native_run_id': result['run_id'], 'mission_checked': mission is not None,
            'points': {name: sum(len(p) for p in spec['containers'].values())
                       for name, spec in result['groups'].items()},
            'runtime_acceptance': 'pending'}


# ------------------------------------------------------------------------------------------------ CLI


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('request')
    p.add_argument('--mission', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('generate')
    p.add_argument('--sampler-result', type=Path, required=True)
    p.add_argument('--mission', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('install')
    p.add_argument('--delta', type=Path, required=True)
    p.add_argument('--mission', type=Path, required=True)
    p = sub.add_parser('rollback')
    p.add_argument('--mission', type=Path, required=True)
    p = sub.add_parser('validate')
    p.add_argument('--sampler-result', type=Path, default=None)
    p.add_argument('--mission', type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        if args.command == 'request':
            doc = json.loads(request(args.mission))
            write_request(args.out, encode(doc))
            print('sampler request written. Run natively: ' + ' '.join(doc['sampler']['command']))
        elif args.command == 'generate':
            files = generate(args.sampler_result.read_bytes(), args.mission)
            write_delta(args.out, files)
            print('coverage delta written (native run %s). Offline operation complete; DayZ runtime acceptance pending.'
                  % json.loads(files['coverage-delta.json'])['native_run_id'])
        elif args.command == 'install':
            install(args.delta, args.mission)
            print('Offline operation complete; DayZ runtime acceptance pending.')
        elif args.command == 'rollback':
            rollback(args.mission)
            print('Rolled back; mapgroupproto.xml restored byte-exactly.')
        else:
            report = validate(args.sampler_result, args.mission)
            if report['status'] == 'pending':
                print('ce-coverage: PENDING (%s)' % report['reason'])
            else:
                print('ce-coverage: sampler result valid (native run %s, points %s); runtime acceptance pending.'
                      % (report['native_run_id'], json.dumps(report['points'], sort_keys=True)))
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('ce_coverage: %s' % (error.strerror or type(error).__name__ if isinstance(error, OSError) else error),
              file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
