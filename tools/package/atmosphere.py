"""Bounded operator profiles -> fresh native cfgweather.xml candidates (#35).

Includes an explicit ChernarusPlus v1 script-delegation candidate. No installation
or runtime acceptance. Inspected baseline:
DayZ 1.30.164289 scripts/3_Game/{Weather,WorldData}.c,
4_World/Classes/Worlds/ChernarusPlus.c and the four installed official missions.
Official reference: https://community.bistudio.com/wiki/DayZ:Weather_Configuration

Profile schema 1 requires schema/name/world/build/source_sha256/enable/reset/
overrides. World and build are OPERATOR ASSERTIONS, not inferred from XML.
Supported worlds: chernarusplus, enoch, sakhal, nasdara (inspected templates).
overrides = {phenomenon: {section: {attribute: number}}, storm: {attribute: number}}.
Sections: current(actual,time,duration), limits(min,max), timelimits(min,max),
changelimits(min,max), rain/snowfall thresholds(min,max,end).
Storm: density,threshold,timeout. Unspecified values retain source lexemes;
no-op retains exact bytes (except the canonical v1-script delegation root).
enable/reset are mandatory booleans; reset=False
preserves native storage precedence, so initial values are not guaranteed.

Safety envelope, NOT measured balance/native maximum claims: normalized 0..1;
wind 0..20 m/s; direction/change -pi..pi rad; times 0..86400 seconds with
positive forecast windows, precipitation end and storm timeout. Source-disabled
phenomena cannot be enabled by this adapter. No daily/seasonal scheduling,
date/time, lighting, shaders, volumetric fog or sandstorm XML is invented.
Chernarus world scripts also modify weather: effective XML behavior requires
native probing. Two-client visibility and performance acceptance remain pending.
The reserved hc-v1-script profile requires enable=False/reset=False, no overrides,
and ChernarusPlus. It emits a canonical disabled root checked by the gated script.
XML owns no phenomenon in this mode; after admission the script owns all weather,
otherwise vanilla does. Existing operator XML profiles remain explicit XML work.

API: generate(source_xml, profile)->three byte files; write_candidate(fresh_dir,
files); validate_candidate(dir, source=None)->report + source_verified flag.
Validation WITH the trusted pinned source reconstructs all outputs byte-for-byte;
hashes alone are integrity checks, not authenticated provenance. The parent of
fresh_dir must exist, be operator-controlled and outside Steam. Links/reparse
points are refused. Hostile concurrent directory replacement is not supported.
Manifest written last is the completion marker. Interrupted partial candidates
are refused, never resumed/overwritten. Existing deployment owns install/rollback.
"""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import xml.etree.ElementTree as ET
try:
    from tools.package import xml_text
except ImportError:  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.package import xml_text

MAX_XML_BYTES = 65536
MAX_JSON_BYTES = 65536
PHENOMENA = ('overcast', 'fog', 'rain', 'windMagnitude', 'windDirection', 'snowfall')
WORLDS = ('chernarusplus', 'enoch', 'sakhal', 'nasdara')
BUILD = '1.30.164289'
BUILDS = (BUILD, '1.30.164289.70')
FILES = {'cfgweather.xml', 'atmosphere-report.json', 'atmosphere-manifest.json'}
SECTIONS = {'current': {'actual', 'time', 'duration'}, 'limits': {'min', 'max'},
            'timelimits': {'min', 'max'}, 'changelimits': {'min', 'max'}}
PENDING = ['native XML load/storage precedence and world-script interaction',
           'normal server restart/rollback', 'two-client visibility and accessibility',
           'representative client/server performance and map compatibility']
SCRIPT_PROFILE = 'hc-v1-script'
SCRIPT_XML_PREFIX = xml_text.DECLARATION + b'<weather enable="0" reset="0">'


def v1_script_profile(source):
    """Pin a ChernarusPlus delegation candidate; never install or opt in."""
    data = _read(source, MAX_XML_BYTES)
    _xml(data)
    return dict(schema=1, name=SCRIPT_PROFILE, world='chernarusplus', build=BUILD,
                source_sha256=sha(data), enable=False, reset=False, overrides={})


def driver_ownership(profile):
    if profile['name'] == SCRIPT_PROFILE:
        owner = 'script-after-admission; otherwise vanilla'
        return {name: owner for name in (*PHENOMENA, 'storm', 'volumetricFog')}
    owner = 'XML candidate; native precedence PENDING' if profile['enable'] else 'vanilla'
    return dict({name: owner for name in (*PHENOMENA, 'storm')},
                volumetricFog='native world script; not represented in XML')


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _safe_path(path):
    path = Path(path).absolute()
    for part in path.parts[1:]:
        if part in {'.', '..'} or ':' in part or part.rstrip(' .') != part:
            raise ValueError('ambiguous filesystem path')
    for node in (*reversed(path.parents), path):
        try:
            info = os.lstat(node)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 1024:
            raise ValueError('links/reparse points forbidden')
    return path


def _read(path, limit):
    path = _safe_path(path)
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise ValueError('input must be a bounded regular file')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError('input changed during open')
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('input size exceeded')
    return data


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _json(data):
    if type(data) is not bytes or len(data) > MAX_JSON_BYTES:
        raise ValueError('JSON size/type unsupported')
    def constant(_):
        raise ValueError('nonfinite JSON number')
    try:
        return json.loads(data.decode('utf-8-sig'), object_pairs_hook=_pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('malformed or excessively nested UTF-8 JSON') from exc


def load_profile(path):
    profile = _json(_read(path, MAX_JSON_BYTES))
    _profile(profile)
    return profile


def _fields(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError('unsupported/missing fields')


def _number(value, low, high):
    if type(value) not in (int, float) or not low <= value <= high:
        raise ValueError('number outside finite safety envelope')
    return value


def _section_fields(name):
    fields = dict(SECTIONS)
    if name in ('rain', 'snowfall'):
        fields['thresholds'] = {'min', 'max', 'end'}
    return fields


def _profile(profile):
    _fields(profile, {'schema', 'name', 'world', 'build', 'source_sha256', 'enable', 'reset', 'overrides'})
    if type(profile['schema']) is not int or profile['schema'] != 1:
        raise ValueError('unsupported profile version')
    if type(profile['name']) is not str or not re.fullmatch('[a-z0-9-]{1,64}', profile['name']):
        raise ValueError('invalid profile name')
    if profile['world'] not in WORLDS or profile['build'] not in BUILDS:
        raise ValueError('world/build outside inspected baseline')
    if type(profile['source_sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', profile['source_sha256']):
        raise ValueError('source SHA256 pin required')
    if type(profile['enable']) is not bool or type(profile['reset']) is not bool:
        raise ValueError('enable/reset must be explicit booleans')
    if profile['name'] == SCRIPT_PROFILE and (profile['enable'] or profile['reset'] or
            profile['world'] != 'chernarusplus' or profile['overrides'] != {}):
        raise ValueError('v1-script requires disabled non-reset ChernarusPlus XML without overrides')
    overrides = profile['overrides']
    if type(overrides) is not dict or not set(overrides) <= set(PHENOMENA) | {'storm'}:
        raise ValueError('unsupported phenomenon')
    for name, sections in overrides.items():
        allowed = {'density', 'threshold', 'timeout'} if name == 'storm' else set(_section_fields(name))
        if type(sections) is not dict or not sections or not set(sections) <= allowed:
            raise ValueError('unsupported/empty override')
        if name == 'storm':
            for value in sections.values(): _number(value, -86400, 86400)
        else:
            for section, attributes in sections.items():
                if type(attributes) is not dict or not attributes or not set(attributes) <= _section_fields(name)[section]:
                    raise ValueError('unsupported/empty attribute override')
                for value in attributes.values(): _number(value, -86400, 86400)
    # Bound dictionaries supplied directly via API as well as JSON input.
    if len(encode(profile)) > MAX_JSON_BYTES:
        raise ValueError('profile too large')


def _boolean(value):
    if value not in ('0', '1', 'true', 'false', 'yes', 'no'):
        raise ValueError('invalid native boolean')
    return value in ('1', 'true', 'yes')


def _attributes(node, fields):
    _fields(node.attrib, fields)
    values = {}
    for key, text in node.attrib.items():
        if len(text) > 32 or not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?', text):
            raise ValueError('invalid finite XML number')
        value = float(text)
        _number(value, -86400, 86400)
        values[key] = value
    return values


def _range(values, low, high):
    _number(values['min'], low, high)
    _number(values['max'], low, high)
    if values['min'] > values['max']:
        raise ValueError('reversed range')


def _xml(data):
    if type(data) is not bytes or len(data) > MAX_XML_BYTES:
        raise ValueError('XML size/type unsupported')
    try:
        text = data.decode('utf-8-sig')
        plain = re.sub(r'<!--.*?-->', '', text, flags=re.S)
        declaration = re.match(r'<\?xml\s+[^?]*\?>', plain)
        if declaration:
            encoding = re.search(r'encoding\s*=\s*[\'"]([^\'"]+)[\'"]', declaration[0])
            if encoding and encoding[1].casefold() != 'utf-8':
                raise ValueError('native XML must declare UTF-8')
        if ('\x00' in text or '<!' in plain or
                '<?' in plain[declaration.end() if declaration else 0:]):
            raise ValueError('unsupported XML declarations')
        root = ET.fromstring(text, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
    except (UnicodeError, ET.ParseError, RecursionError) as exc:
        raise ValueError('malformed UTF-8 XML') from exc
    if root.tag != 'weather':
        raise ValueError('expected native weather root')
    _fields(root.attrib, {'enable', 'reset'})
    _boolean(root.get('enable')); _boolean(root.get('reset'))
    # Validate shape before iterating descendants: bounded expected depth/nodes.
    children = [n for n in root if isinstance(n.tag, str)]
    if len(children) != 7 or {n.tag for n in children} != set(PHENOMENA) | {'storm'}:
        raise ValueError('missing/duplicate/unknown weather nodes')
    parsed = {}
    for node in children:
        if node.tag == 'storm':
            if len(node): raise ValueError('storm must be a leaf')
            values = _attributes(node, {'density', 'threshold', 'timeout'})
            _number(values['density'], 0, 1); _number(values['threshold'], 0, 1)
            _number(values['timeout'], 1, 86400)
            parsed['storm'] = values
            continue
        allowed = _section_fields(node.tag)
        _fields(node.attrib, set())
        leaves = [n for n in node if isinstance(n.tag, str)]
        if len(leaves) != len(allowed) or {n.tag for n in leaves} != set(allowed):
            raise ValueError('missing/duplicate/unknown phenomenon sections')
        values = {}
        for leaf in leaves:
            if len(leaf): raise ValueError('weather section must be a leaf')
            values[leaf.tag] = _attributes(leaf, allowed[leaf.tag])
        low, high = (-math.pi, math.pi) if node.tag == 'windDirection' else (0, 20 if node.tag == 'windMagnitude' else 1)
        _range(values['limits'], low, high)
        _range(values['changelimits'], low, high)
        _range(values['timelimits'], 0.001, 86400)
        current = values['current']
        _number(current['actual'], values['limits']['min'], values['limits']['max'])
        _number(current['time'], 0, 86400); _number(current['duration'], 0, 86400)
        if 'thresholds' in values:
            _range(values['thresholds'], 0, 1)
            _number(values['thresholds']['end'], .001, 86400)
        parsed[node.tag] = values
    for node in root.iter():
        if (node.tail or '').strip() or (isinstance(node.tag, str) and (node.text or '').strip()):
            raise ValueError('unexpected XML text')
    cloud = parsed['overcast']['limits']
    for name in ('rain', 'snowfall'):
        values = parsed[name]
        if values['limits']['max'] > 0:
            thresholds = values['thresholds']
            if max(thresholds['min'], cloud['min']) > min(thresholds['max'], cloud['max']):
                raise ValueError('unreachable precipitation threshold window')
    if parsed['storm']['density'] > 0 and parsed['storm']['threshold'] > cloud['max']:
        raise ValueError('unreachable storm threshold')
    return root, parsed


def generate(source, profile):
    _profile(profile)
    profile = copy.deepcopy(profile)
    data = _read(source, MAX_XML_BYTES)
    if sha(data) != profile['source_sha256']:
        raise ValueError('source SHA256 mismatch')
    root, before = _xml(data)
    changes = []
    def change(node, attribute, value, path):
        previous = node.get(attribute)
        if previous != value:
            changes.append({'path': path + '/' + attribute, 'before': previous, 'after': value})
            node.set(attribute, value)
    for attribute in ('enable', 'reset'):
        if _boolean(root.get(attribute)) != profile[attribute]:
            change(root, attribute, str(int(profile[attribute])), 'weather')
    for name, sections in sorted(profile['overrides'].items()):
        if name == 'storm':
            for attribute, value in sorted(sections.items()):
                change(root.find(name), attribute, str(value), name)
        else:
            for section, attributes in sorted(sections.items()):
                for attribute, value in sorted(attributes.items()):
                    change(root.find(name + '/' + section), attribute, str(value), name + '/' + section)
    if profile['name'] == SCRIPT_PROFILE:
        # The script admits only this exact root prefix, never flags found in a
        # comment or a second root. Phenomenon nodes remain source-derived.
        root.attrib.clear()
        root.set('enable', '0')
        root.set('reset', '0')
        candidate = xml_text.document(root)
    else:
        candidate = xml_text.document(root) if changes else data
    _, after = _xml(candidate)
    for name in PHENOMENA:
        if before[name]['limits']['max'] == 0 and after[name]['limits']['max'] != 0:
            raise ValueError('source-disabled phenomenon requires separate native qualification')
    report = {'schema': 1, 'profile': profile, 'source_sha256': sha(data),
              'candidate_sha256': sha(candidate), 'changes': changes,
              'driver_ownership': driver_ownership(profile),
              'world_binding': 'operator-asserted; not encoded in native weather XML',
              'runtime_acceptance': 'pending', 'feature_complete': False, 'pending': PENDING}
    files = {'cfgweather.xml': candidate, 'atmosphere-report.json': encode(report)}
    files['atmosphere-manifest.json'] = encode({'schema': 1, 'source_sha256': sha(data),
        'files': {name: sha(value) for name, value in files.items()}, 'runtime_acceptance': 'pending'})
    _validate_files(files)
    return files


def _write_file(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    info = os.fstat(fd)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
    except BaseException:
        if path.exists() and os.path.samestat(info, os.lstat(path)):
            path.unlink()
        raise
    return info


def _validate_files(files):
    _fields(files, FILES)
    root, _ = _xml(files['cfgweather.xml'])
    report = _json(files['atmosphere-report.json'])
    manifest = _json(files['atmosphere-manifest.json'])
    _fields(report, {'schema', 'profile', 'source_sha256', 'candidate_sha256', 'changes',
                     'driver_ownership', 'world_binding', 'runtime_acceptance', 'feature_complete', 'pending'})
    _profile(report['profile'])
    _fields(manifest, {'schema', 'source_sha256', 'files', 'runtime_acceptance'})
    _fields(manifest['files'], {'cfgweather.xml', 'atmosphere-report.json'})
    if (type(report['schema']) is not int or report['schema'] != 1 or
            type(manifest['schema']) is not int or manifest['schema'] != 1 or
            report['feature_complete'] is not False or report['pending'] != PENDING or
            report['world_binding'] != 'operator-asserted; not encoded in native weather XML' or
            manifest['runtime_acceptance'] != 'pending' or report['runtime_acceptance'] != 'pending' or
            report['source_sha256'] != report['profile']['source_sha256'] or
            manifest['source_sha256'] != report['source_sha256'] or
            report['candidate_sha256'] != sha(files['cfgweather.xml'])):
        raise ValueError('inconsistent/unqualified atmosphere metadata')
    for name, digest in manifest['files'].items():
        if digest != sha(files[name]): raise ValueError('candidate digest mismatch')
    profile = report['profile']
    if report['driver_ownership'] != driver_ownership(profile):
        raise ValueError('inconsistent phenomenon ownership')
    if profile['name'] == SCRIPT_PROFILE and not files['cfgweather.xml'].startswith(SCRIPT_XML_PREFIX):
        raise ValueError('v1-script requires canonical disabled XML root')
    if _boolean(root.get('enable')) != profile['enable'] or _boolean(root.get('reset')) != profile['reset']:
        raise ValueError('native flags disagree with explicit profile')
    for name, sections in profile['overrides'].items():
        sections = {'': sections} if name == 'storm' else sections
        for section, attributes in sections.items():
            node = root.find(name + ('/' + section if section else ''))
            for attribute, value in attributes.items():
                if float(node.get(attribute)) != value:
                    raise ValueError('candidate disagrees with explicit override')
    if type(report['changes']) is not list or len(report['changes']) > 100:
        raise ValueError('invalid delta inventory')
    seen = set()
    for change in report['changes']:
        _fields(change, {'path', 'before', 'after'})
        path = change['path']
        if type(path) is not str or path in seen or type(change['before']) is not str or type(change['after']) is not str:
            raise ValueError('invalid/duplicate delta')
        seen.add(path)
        pieces = path.split('/')
        node = root if pieces[:-1] == ['weather'] else root.find('/'.join(pieces[:-1]))
        if node is None or node.get(pieces[-1]) != change['after']:
            raise ValueError('delta disagrees with candidate')
    return report


def write_candidate(destination, files):
    _validate_files(files)
    destination = _safe_path(destination)
    if 'steamapps' in [part.casefold() for part in destination.parts]:
        raise ValueError('candidate output must be outside Steam')
    if destination.exists() or not destination.parent.is_dir():
        raise ValueError('output must be a fresh directory under an existing parent')
    destination.mkdir(mode=0o700)
    directory = os.lstat(destination)
    written = []
    try:
        # Completion manifest is always last.
        for name in ('cfgweather.xml', 'atmosphere-report.json', 'atmosphere-manifest.json'):
            if not os.path.samestat(directory, os.lstat(_safe_path(destination))):
                raise ValueError('staging directory changed')
            path = destination / name
            written.append((path, _write_file(path, files[name])))
        validate_candidate(destination)
    except BaseException:
        if destination.exists() and os.path.samestat(directory, os.lstat(_safe_path(destination))):
            for path, info in reversed(written):
                if path.exists() and os.path.samestat(info, os.lstat(_safe_path(path))):
                    path.unlink()
            # Refuse to remove unexpected files from a concurrently changed dir.
            if not any(destination.iterdir()): destination.rmdir()
        raise


def validate_candidate(candidate, source=None):
    candidate = _safe_path(candidate)
    if not candidate.is_dir():
        raise ValueError('incomplete/unexpected candidate contents')
    names = set()
    for path in candidate.iterdir():
        if path.name not in FILES or path.name in names or len(names) >= len(FILES):
            raise ValueError('incomplete/unexpected candidate contents')
        names.add(path.name)
    if names != FILES:
        raise ValueError('incomplete/unexpected candidate contents')
    files = {name: _read(candidate/name, MAX_XML_BYTES if name == 'cfgweather.xml' else MAX_JSON_BYTES) for name in FILES}
    report = _validate_files(files)
    if source is not None and files != generate(source, report['profile']):
        raise ValueError('candidate differs from reconstruction with pinned source')
    return dict(report, source_verified=source is not None)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('generate')
    create.add_argument('--source', required=True, type=Path)
    create.add_argument('--profile', required=True, type=Path)
    create.add_argument('--output', required=True, type=Path)
    script = commands.add_parser('v1-script', help='ChernarusPlus: delegate XML to the gated v1 world script')
    script.add_argument('--source', required=True, type=Path)
    script.add_argument('--output', required=True, type=Path)
    check = commands.add_parser('validate')
    check.add_argument('--candidate', required=True, type=Path)
    check.add_argument('--source', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command in ('generate', 'v1-script'):
            profile = v1_script_profile(args.source) if args.command == 'v1-script' else load_profile(args.profile)
            write_candidate(args.output, generate(args.source, profile))
            result = validate_candidate(args.output, args.source)
        else:
            result = validate_candidate(args.candidate, args.source)
        print(json.dumps({'runtime_acceptance': 'pending', 'feature_complete': False,
                          'source_verified': result['source_verified']}))
        return 0
    except (ValueError, OSError, OverflowError) as exc:
        print('Atmosphere candidate refused: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
