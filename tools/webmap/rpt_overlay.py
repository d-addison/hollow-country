"""Stream privacy-filtered HC coordinates from server RPTs into a local map layer."""
import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import re
import tempfile

PRIVACY = re.compile(r'steam ?id|uid|name=|[0-9]{17}|Player "|id=', re.I)
KINDS = ('route-refusal', 'ai-refusal', 'event-bind', 'shelter-refusal',
         'interior-warning', 'incident')
MAX_FEATURES = 2048
MAX_BYTES = 1048576
NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'
# Native PointText: from=|x,y,z; also accept labelled engine vectors and x=/z=.
VECTOR = re.compile(
    rf'(?i)(?:\b(?:pos(?:ition)?|at|from|to|start|end|anchor|point|center|centre|waypoint)\s*[=:]?\s*)'
    rf'[|<\[("\s]*({NUMBER})[\s,]+({NUMBER})(?:[\s,]+({NUMBER}))?(?![\d.eE])')
BARE_VECTOR = re.compile(rf'[<\[(|]\s*({NUMBER})[\s,]+({NUMBER})[\s,]+({NUMBER})\s*[>\])|]')
XZ = re.compile(rf'\bx\s*=\s*({NUMBER})\s*[,; ]+\s*z\s*=\s*({NUMBER})(?![\d.eE])', re.I)
HC = re.compile(r'\[(HC(?: [A-Za-z0-9_-]+)*|HollowCountry)\]')


def classify(text):
    low = text.lower()
    failure = re.search(r'refus|fail|unbindable|unresolved|not bound|skipped|held|warn|missing', low)
    if failure:
        if re.search(r'\broute|\bleg\b', low):
            return 'route-refusal'
        if 'event' in low and re.search(r'bind|anchor', low):
            return 'event-bind'
        if 'shelter' in low:
            return 'shelter-refusal'
        if 'interior' in low and re.search(r'pack|template', low):
            return 'interior-warning'
        if re.search(r'\bai\b|\bspawn\b', low):
            return 'ai-refusal'
    if re.search(r'\bincidents?\b', low):
        return 'incident'
    return None


def positions(text):
    found = set()
    for pattern in (VECTOR, BARE_VECTOR, XZ):
        for match in pattern.finditer(text):
            values = [float(v) for v in match.groups() if v is not None]
            x, z = values[0], values[-1]
            if all(math.isfinite(v) for v in values) and 0 <= x <= 15360 and 0 <= z <= 15360:
                found.add((x, z))
    return sorted(found)


def reason_text(text, kind):
    # Never retain the whole line, site/party identifiers, quoted values or paths.
    match = re.search(r'\b(?:reason|refusal|refused)\s*=\s*([A-Za-z][A-Za-z0-9_.-]{0,95})', text, re.I)
    if match:
        return match[1]
    match = re.search(r'(?:refused(?:\s*\([^)]*\))?|failed|warning|warn|skipped|held|unbindable|unresolved)\s*[:;]\s*(.*)', text, re.I)
    if not match:
        return kind
    detail = match[1]
    detail = re.sub(r'\b(?:from|to|pos(?:ition)?|at|anchor)\s*=.*', '', detail, flags=re.I)
    detail = re.sub(r'"[^"]*"|\'[^\']*\'|\S*[/\\]\S*|\S*[:=]\S*', '', detail)
    detail = re.sub(r'[^A-Za-z0-9 _.,;-]', ' ', detail)
    return ' '.join(detail.split())[:256] or kind


def build_layer(paths):
    rows = Counter()
    counts, unplaced = Counter(), Counter()
    dropped = oversized = omitted = 0
    for path in paths:
        with Path(path).open('rb') as raw:
            prefix = raw.read(4)
        encoding = 'utf-16' if prefix.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
        with Path(path).open(encoding=encoding, errors='replace') as source:
            while True:
                line = source.readline(65537)
                if not line:
                    break
                if len(line) > 65536:
                    while line and not line.endswith('\n'):
                        line = source.readline(65537)
                    oversized += 1
                    continue
                if PRIVACY.search(line):
                    dropped += 1
                    continue
                tag = HC.search(line)
                if not tag:
                    continue
                text = line[tag.start():]
                kind = classify(text)
                if not kind:
                    continue
                counts[kind] += 1
                coordinates = positions(text)
                if not coordinates:
                    unplaced[kind] += 1
                    continue
                module = tag[1]
                reason = reason_text(text[tag.end()-tag.start():], kind)
                for position in coordinates:
                    key = kind, module, reason, position
                    if key not in rows and len(rows) >= MAX_FEATURES:
                        omitted += 1
                        continue
                    rows[key] += 1
    features = []
    for (kind, module, reason, position), count in sorted(rows.items()):
        features.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': list(position)},
                         'properties': {'kind': kind, 'module': module, 'reason': reason,
                                        'position': list(position), 'count': count}})
    return {'type': 'FeatureCollection', 'version': 1, 'map': 'chernarusplus',
            'coordinateSystem': 'DayZ metres x,z (not longitude/latitude)',
            'features': features, 'summary': {
                'linesByKind': {kind: counts[kind] for kind in KINDS},
                'unplacedByKind': {kind: unplaced[kind] for kind in KINDS},
                'privacyDropped': dropped, 'oversizedLines': oversized, 'omittedPositions': omitted}}


def validate_layer(data):
    if not isinstance(data, dict) or data.get('type') != 'FeatureCollection' or type(data.get('version')) is not int or data.get('version') != 1 or data.get('map') != 'chernarusplus':
        raise ValueError('unsupported overlay')
    features = data.get('features')
    if not isinstance(features, list) or len(features) > MAX_FEATURES:
        raise ValueError('overlay feature cap')
    for row in features:
        if not isinstance(row, dict) or row.get('type') != 'Feature':
            raise ValueError('invalid overlay feature')
        prop, geom = row.get('properties'), row.get('geometry')
        if not isinstance(prop, dict) or not isinstance(geom, dict) or geom.get('type') != 'Point':
            raise ValueError('invalid overlay point')
        pair = geom.get('coordinates')
        if not isinstance(pair, list) or len(pair) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 15360 for v in pair):
            raise ValueError('invalid overlay coordinates')
        if prop.get('position') != pair or prop.get('kind') not in KINDS:
            raise ValueError('invalid overlay properties')
        if type(prop.get('count')) is not int or not 1 <= prop['count'] <= 2147483647:
            raise ValueError('invalid overlay count')
        for key, limit in (('module', 96), ('reason', 256)):
            if not isinstance(prop.get(key), str) or not prop[key] or len(prop[key]) > limit or PRIVACY.search(prop[key]):
                raise ValueError('invalid overlay text')
    # Reject identity markers even in unexpected metadata; serve only our projection.
    if PRIVACY.search(json.dumps(data, ensure_ascii=False)):
        raise ValueError('overlay privacy filter')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rpt', nargs='+', type=Path, help='server RPT(s), read only')
    parser.add_argument('--out', type=Path, default=Path(tempfile.gettempdir()) / 'hollow-country-rpt-overlay.json')
    args = parser.parse_args(argv)
    temporary = None
    try:
        data = build_layer(args.rpt)
        validate_layer(data)
        body = json.dumps(data, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode() + b'\n'
        if len(body) > MAX_BYTES:
            raise ValueError('overlay byte cap')
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=args.out.parent, prefix='.hc-overlay-', delete=False) as target:
            temporary = Path(target.name)
            target.write(body)
        os.replace(temporary, args.out)
    except (OSError, ValueError):
        parser.exit(1, 'Overlay unavailable: check input/output access, schema and bounds.\n')
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(json.dumps(data['summary'], sort_keys=True))


if __name__ == '__main__':
    main()
