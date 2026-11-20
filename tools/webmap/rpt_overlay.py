"""Stream privacy-filtered HC diagnostics into a local map layer using repo catalogues."""
import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import re
import tempfile

# Only content-id keys are exempt from the old blanket id= rejection.
CONTENT_KEYS = r'(?:id|site_?id|locality_?id|camp_?id|region_?id|mission_?id)'
PRIVACY = re.compile(
    r'steam ?id|uid|name=|[0-9]{17}|Player "|'
    rf'\b(?!{CONTENT_KEYS}\s*=)[A-Za-z_-]*id\s*=', re.I)
CONTENT_ID = re.compile(r'[A-Za-z][A-Za-z0-9_.-]{0,95}\Z')
ID_TOKEN = re.compile(r'(?<![\w.-])[A-Za-z][A-Za-z0-9_.-]{0,95}(?![\w.-])')
ID_FIELD = re.compile(
    rf'\b(?:{CONTENT_KEYS}|site|locality|camp|region|mission|nearest|from|to)\s*=\s*["\']?([A-Za-z][A-Za-z0-9_.-]{{0,95}})(?![\w.-])', re.I)
MAX_UNPLACED = 256
CATALOG_ROOT = Path(__file__).resolve().parents[2]
# Read only these authored catalogues; never scan profiles or installed mods.
JSON_CATALOGS = (
    'mission/hollow-country/ai/sites.json',
    'mission/hollow-country/ai/localities.json',
    'mission/hollow-country/events/story-sites.json',
    'mission/hollow-country/travel/auditshelter_scenes.json',
    'mission/hollow-country/travel/route-surveys.json',
)

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


def catalog_position(value):
    if isinstance(value, str):
        value = value.split()
    if not isinstance(value, list) or len(value) not in (2, 3):
        return None
    try:
        values = [float(v) for v in value if not isinstance(v, bool)]
    except (TypeError, ValueError):
        return None
    if len(values) != len(value) or not all(math.isfinite(v) for v in values):
        return None
    x, z = values[0], values[-1]
    return (x, z) if 0 <= x <= 15360 and 0 <= z <= 15360 else None


def load_catalogs(root=CATALOG_ROOT):
    """Index authored anchors once; conflicting definitions stay unresolved.

    This reads data literals, not Enforce execution. Runtime-created camp IDs
    without a shipped anchor intentionally cannot be resolved from this index.
    """
    root = Path(root)
    candidates, event_ids = {}, set()
    loaded = 0
    protected_ids = set()

    def add(identifier, value):
        if isinstance(identifier, str) and identifier in protected_ids:
            return
        position = catalog_position(value)
        if isinstance(identifier, str) and CONTENT_ID.fullmatch(identifier) and not PRIVACY.search(identifier) and position:
            candidates.setdefault(identifier, set()).add(position)

    def walk(value, event=False):
        if isinstance(value, list):
            for row in value:
                walk(row, event)
        elif isinstance(value, dict):
            fields = {k.lower(): v for k, v in value.items()}
            identifier = fields.get('id')
            point = next((fields[k] for k in ('position', 'anchor', 'center', 'centre', 'houseposition', 'housepos') if k in fields), None)
            if point is None and isinstance(fields.get('waypoints'), list) and fields['waypoints']:
                point = fields['waypoints'][0]  # Site origin, not an observed AI position.
            add(identifier, point)
            # Regional shelter entries explicitly name their authored region.
            if 'region' in fields and ('locality_id' in fields or 'localityid' in fields):
                add(fields['region'], point)
            if event and isinstance(identifier, str) and catalog_position(point):
                event_ids.add(identifier)
            for row in value.values():
                if isinstance(row, (dict, list)):
                    walk(row, event)

    paths = [root / name for name in JSON_CATALOGS]
    paths += sorted(root.glob('mods/*/data/defaults/expansion-ai-sites.json'))
    paths += sorted(root.glob('mods/*/data/defaults/expansion-ai-localities.json'))
    for path in paths:
        if not path.is_file():
            continue
        if path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError('catalogue byte cap')
        # Checkout mission content wins over older packaged defaults.
        protected_ids = set(candidates) if 'defaults' in path.parts else set()
        walk(json.loads(path.read_text(encoding='utf-8-sig')), path.name == 'story-sites.json')
        loaded += 1

    protected_ids = set()
    if not loaded:
        raise ValueError('no repository catalogues found')

    # The two base event sources are code-authored, with no JSON counterpart.
    path = root / 'mods/HollowCountry/scripts/4_World/Events/HCEventSites.c'
    if path.is_file():
        if path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError('catalogue byte cap')
        source = re.sub(r'//[^\n]*|/\*.*?\*/', '', path.read_text(), flags=re.S)
        for match in re.finditer(r'\b(\w+)\.Id\s*=\s*"([^"\n]+)"\s*;', source):
            vector = re.search(rf'\b{re.escape(match[1])}\.Position\s*=\s*Vector\(([^)]+)\)', source)
            if vector:
                add(match[2], vector[1].replace(',', ' '))
                event_ids.add(match[2])
        loaded += 1
    # HCEventRoster constructs exactly site.Id + '-' + family (1..7).
    for identifier in sorted(event_ids):
        for family in range(1, 8):
            for point in candidates.get(identifier, ()):
                add(f'{identifier}-{family}', list(point))
    catalog = {key: next(iter(points)) for key, points in candidates.items() if len(points) == 1}
    return catalog, {'filesLoaded': loaded, 'idsResolved': len(catalog),
                     'ambiguousIds': sum(len(points) > 1 for points in candidates.values())}


def line_ids(text, catalog):
    identifiers = {m[0] for m in ID_TOKEN.finditer(text) if m[0] in catalog}
    identifiers.update(m[1] for m in ID_FIELD.finditer(text))
    for pattern in (r'\bbind failed;\s*([A-Za-z][A-Za-z0-9_.-]{0,95})\s*;',
                    r'\b(?:site|locality|camp|region)\s+([A-Za-z][A-Za-z0-9_.-]{0,95})\s+(?:route|spawn|member|actor|refused|failed|held|skipped)\b'):
        identifiers.update(m[1] for m in re.finditer(pattern, text, re.I))
    return sorted(identifier for identifier in identifiers if identifier.lower() not in ('none', 'unknown', 'null'))


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


def build_layer(paths, catalog_root=CATALOG_ROOT):
    catalog, catalog_summary = load_catalogs(catalog_root)
    rows = Counter()
    counts, unplaced, placed = Counter(), Counter(), Counter()
    unresolved = Counter()
    unresolved_omitted = 0
    coordinate_lines = catalog_lines = 0
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
                from_catalog = not coordinates
                if coordinates:
                    coordinate_lines += 1
                else:
                    identifiers = line_ids(text, catalog)
                    coordinates = sorted({catalog[key] for key in identifiers if key in catalog})
                    missing = [key for key in identifiers if key not in catalog]
                    if not identifiers:
                        missing = ['<no-id>']
                    for identifier in missing:
                        key = kind, identifier
                        if key in unresolved or len(unresolved) < MAX_UNPLACED:
                            unresolved[key] += 1
                        else:
                            unresolved_omitted += 1
                    if coordinates:
                        catalog_lines += 1
                if not coordinates:
                    unplaced[kind] += 1
                    continue
                placed[kind] += 1
                module = tag[1]
                reason = reason_text(text[tag.end()-tag.start():], kind)
                if from_catalog:
                    reason = ('catalogue anchor; ' + reason)[:256]
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
                'placedByKind': {kind: placed[kind] for kind in KINDS},
                'unplacedByKind': {kind: unplaced[kind] for kind in KINDS},
                'coordinateLines': coordinate_lines, 'catalogLines': catalog_lines,
                'catalog': catalog_summary, 'features': len(features),
                'unplaced': [{'kind': kind, 'id': identifier,
                              'reason': 'no_content_id' if identifier == '<no-id>' else 'unknown_or_ambiguous_id',
                              'count': count}
                             for (kind, identifier), count in unresolved.most_common()],
                'unplacedIdsOmitted': unresolved_omitted,
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
    parser.add_argument('--catalog-root', type=Path, default=CATALOG_ROOT,
                        help='repository checkout containing mission/ and mods/ catalogues')
    parser.add_argument('--out', type=Path, default=Path(tempfile.gettempdir()) / 'hollow-country-rpt-overlay.json')
    args = parser.parse_args(argv)
    temporary = None
    try:
        data = build_layer(args.rpt, args.catalog_root)
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
