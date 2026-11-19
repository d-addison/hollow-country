"""Validate pinned measured pilot interiors and export a fresh diagnostic candidate.

Hashes bind caller assertions, not their truth. No runtime loader, placement,
allocation, installation or native acceptance is supplied by this utility.
"""
import argparse
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat


RECORD_LIMIT = 32767
SOURCE_LIMIT = 65536
ARTIFACT_LIMIT = 1024 * 1024
ARTIFACT_TOTAL = 8 * ARTIFACT_LIMIT
SOURCE_NAMES = ('HCInteriorCatalog.c', 'HCInteriorRules.c', 'HCInteriorStore.c')
BUILD = '1.30.164289'
NATIVE_SHA = '09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a'
ASSET_PBOS = {
    'structures_residential': 'f47cbd5f46f3597cc83fef822ed405cbd69de0f160c414b6deb843cc3ff2106a',
    'structures_furniture': 'e5add5e387d17df70e680e966f1705f55940ba267dcb05e7b76b8013e9d4b448',
}
# Deliberately narrow reviewed pilot. Changed source/schema requires tool review.
PILOT = (
    ('family-pantry-v1', 'family', 'StaticObj_Furniture_case_a', 'StaticObj_Furniture_kitchen_chair_a'),
    ('family-storage-v1', 'family', 'StaticObj_Furniture_case_bedroom_b', 'StaticObj_Furniture_PaperBox_01_small_closed'),
    ('ransacked-storage-v1', 'ransacked', 'StaticObj_Furniture_case_a_open', 'StaticObj_Furniture_PaperBox_01_small_ransacked'),
)
# Template catalog, independent of the frozen schema-1 PILOT layouts above.
# Read-only verification: datamine-2026-11-17/cfg.pkl (vanilla CfgVehicles census),
# then tools.audit.pbo_config.read_configs against the installed PBOs below.
# No assets/config dumps are distributed here. Sizes are conservative guesses, NOT measurements.
_FURNITURE_CONFIG = 'installed:/mnt/d/SteamLibrary/steamapps/common/DayZServer/addons/structures_furniture.pbo!config.bin:CfgVehicles/'
_CRATE_CONFIG = 'installed:/mnt/d/SteamLibrary/steamapps/common/DayZServer/addons/structures_residential_bliss.pbo!config.bin:CfgVehicles/'
_PROP_ROWS = (
    ('StaticObj_Furniture_case_a', (0.9, 0.6, 1.8), ('family', 'ransacked'), 'container'),
    ('StaticObj_Furniture_case_a_open', (1.2, 0.9, 1.8), ('ransacked', 'abandoned'), 'container'),
    ('StaticObj_Furniture_case_bedroom_b', (0.9, 0.6, 1.4), ('family', 'ransacked'), 'container'),
    ('StaticObj_Furniture_PaperBox_01_small_closed', (0.6, 0.5, 0.5), ('family', 'abandoned'), 'clutter'),
    ('StaticObj_Furniture_PaperBox_01_small_ransacked', (0.8, 0.7, 0.5), ('ransacked', 'abandoned'), 'clutter'),
    ('StaticObj_Furniture_kitchen_chair_a', (0.7, 0.7, 1.1), ('family', 'ransacked'), 'seat'),
    ('StaticObj_Furniture_matress_white', (1.1, 2.2, 0.4), ('ransacked', 'abandoned'), 'bed'),
    ('StaticObj_Furniture_postel_panelak1', (1.2, 2.3, 1.2), ('family', 'ransacked'), 'bed'),
    ('StaticObj_Furniture_almara', (1.5, 0.8, 2.2), ('family', 'ransacked'), 'container'),
    ('StaticObj_Furniture_almara_open', (1.8, 1.2, 2.2), ('ransacked', 'abandoned'), 'container'),
    ('StaticObj_Furniture_library_a', (1.4, 0.6, 2.1), ('family', 'ransacked'), 'container'),
    ('StaticObj_Furniture_kitchen_table_a', (1.6, 1.0, 1.0), ('family', 'ransacked'), 'table'),
    ('StaticObj_Furniture_table_drawer', (1.4, 0.9, 1.0), ('family', 'ransacked'), 'container'),
    ('StaticObj_Furniture_Kitchen_desk_A', (1.3, 0.9, 1.1), ('family', 'ransacked'), 'kitchen'),
    ('StaticObj_Furniture_case_sink_a', (1.4, 0.9, 1.2), ('family', 'ransacked'), 'kitchen'),
    ('StaticObj_Furniture_Dkamna_bila', (1.0, 1.0, 1.5), ('family', 'ransacked'), 'stove'),
    ('StaticObj_Furniture_Kitchenstove_Elec', (0.9, 0.9, 1.2), ('family', 'ransacked'), 'stove'),
    ('StaticObj_Furniture_sofa_leather_old', (2.5, 1.2, 1.2), ('family', 'ransacked'), 'seat'),
    ('StaticObj_Furniture_kitchen_unit_a_DZ', (2.8, 0.9, 2.2), ('family', 'ransacked'), 'container'),
    ('StaticObj_Furniture_PaperBox_01_small_destroyed', (0.9, 0.8, 0.5), ('ransacked', 'abandoned'), 'clutter'),
    ('StaticObj_Furniture_debris_small_house', (1.5, 1.5, 0.5), ('ransacked', 'abandoned'), 'rubbish'),
    ('StaticObj_Furniture_dirtpile_small_house', (1.5, 1.5, 0.3), ('abandoned',), 'rubbish'),
    ('StaticObj_Furniture_metalcrate', (1.2, 0.9, 1.0), ('family', 'ransacked'), 'container'),
    ('StaticObj_Misc_WoodenCrate', (1.2, 0.9, 1.0), ('family', 'abandoned'), 'container'),
)
PROPS = {name: {'Size': size, 'History': histories, 'Role': role,
                'Evidence': (_CRATE_CONFIG if name == 'StaticObj_Misc_WoodenCrate' else _FURNITURE_CONFIG) + name}
         for name, size, histories, role in _PROP_ROWS}
SEARCH_TYPES = tuple(name for name, spec in PROPS.items() if spec['Role'] == 'container')
AUTHORED_LIMIT = 32767
AUTHORED_LAYOUT_CAP = 3
ROOMS = {'kitchen', 'pantry', 'bedroom', 'storage', 'living-room', 'workshop', 'bathroom', 'hallway'}
KINDS = {'native-build', 'asset-config', 'geometry', 'door-clearance', 'stairs-clearance'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, names):
    require(isinstance(value, dict) and set(value) == set(names.split()), 'unsupported or missing fields')


def bounded_list(value, lo, hi):
    require(isinstance(value, list) and lo <= len(value) <= hi, 'collection outside diagnostic limits')
    return value


def number(value, lo, hi):
    require(type(value) in (int, float) and lo <= value <= hi and math.isfinite(value), 'nonfinite or out-of-bounds number')
    return value


def integer(value, lo, hi):
    require(type(value) is int and lo <= value <= hi, 'invalid bounded integer')
    return value


def text_value(value, lo=1, hi=256):
    require(isinstance(value, str) and lo <= len(value.strip()) <= hi
            and all(ord(c) >= 32 for c in value), 'invalid measurement text')
    require(value.strip().lower() not in {'todo', 'unknown', 'placeholder', 'unmeasured', 'n/a'}, 'placeholder measurement')
    return value


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9-]{0,63}', value), 'invalid policy identifier')
    text_value(value)
    return value


def digest(data):
    return hashlib.sha256(data).hexdigest()


def byte_input(data, limit):
    require(isinstance(data, bytes) and 0 < len(data) <= limit, 'input bytes outside limits')
    return data


def json_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError('nonfinite JSON constant')


def load_record(raw):
    byte_input(raw, RECORD_LIMIT)
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=json_pairs, parse_constant=reject_constant)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('invalid UTF-8 or excessive JSON depth') from exc


def authored_layouts(inputs):
    """HC-56 intentions only: no authored coordinates or invented native boxes.

    The caller explicitly selects this mode; an empty mapping queues all furniture.
    Exact bytes are pinned by the template generator, never added to the runtime DTOs.
    """
    require(isinstance(inputs, dict) and len(inputs) <= 2, 'authored input cap')
    require(all(name in ('home-layouts.json', 'service-layouts.json') for name in inputs),
            'unknown authored theme file')
    layouts, identities = {}, set()
    for name, raw in sorted(inputs.items()):
        byte_input(raw, AUTHORED_LIMIT)
        document = load_record(raw)
        fields(document, 'SchemaVersion RuntimeAcceptance Pending Layouts')
        require(type(document['SchemaVersion']) is int and document['SchemaVersion'] == 1
                and document['RuntimeAcceptance'] == 'pending', 'unsupported authored schema/acceptance')
        for pending in bounded_list(document['Pending'], 1, 8):
            text_value(pending)
        for entry in bounded_list(document['Layouts'], 1, AUTHORED_LAYOUT_CAP):
            fields(entry, 'Id BuildingClass History PropClasses Intent')
            identity = identifier(entry['Id'])
            building = entry['BuildingClass']
            require(isinstance(building, str) and re.fullmatch(r'Land_[A-Za-z0-9_]{1,123}', building),
                    'invalid authored building class')
            require(identity not in identities and building not in layouts, 'duplicate authored identity/class')
            history = entry['History']
            require(isinstance(history, str) and history in ('family', 'ransacked', 'abandoned'),
                    'invalid authored history')
            props = bounded_list(entry['PropClasses'], 2, 5)
            require(all(isinstance(prop, str) and prop in PROPS and history in PROPS[prop]['History']
                        for prop in props), 'unsupported authored prop/history')
            require(len(set(props)) == len(props), 'duplicate authored prop')
            require(history != 'abandoned' or len(props) == 2, 'abandoned layout must stay sparse')
            text_value(entry['Intent'])
            identities.add(identity)
            layouts[building] = entry
            require(len(layouts) <= AUTHORED_LAYOUT_CAP, 'authored layout cap')
    return layouts


def portable_name(name):
    require(isinstance(name, str) and 1 <= len(name) <= 160
            and re.fullmatch(r'[A-Za-z0-9_./-]+', name), 'unsafe observation path')
    for part in name.split('/'):
        require(part not in {'', '.', '..'} and not part.endswith('.')
                and part.split('.')[0].upper() not in {'CON', 'PRN', 'AUX', 'NUL',
                     *(f'COM{i}' for i in range(10)), *(f'LPT{i}' for i in range(10))}, 'unsafe observation path')
    return name


def vector(value, limit):
    bounded_list(value, 3, 3)
    return [number(n, -limit, limit) for n in value]


def box(value):
    fields(value, 'Min Max')
    low, high = vector(value['Min'], 100), vector(value['Max'], 100)
    require(all(a < b for a, b in zip(low, high)), 'empty or inverted measured bounds')
    return low, high


def contains(outer, inner):
    return all(a <= c <= d <= b for a, b, c, d in zip(*outer, *inner))


def gap(left, right):
    return math.sqrt(sum(max(a - d, c - b, 0) ** 2 for a, b, c, d in zip(*left, *right)))


def source_catalog(sources):
    require(isinstance(sources, dict) and set(sources) == set(SOURCE_NAMES), 'exact pilot sources required')
    for value in sources.values():
        byte_input(value, SOURCE_LIMIT)
    try:
        catalog = sources['HCInteriorCatalog.c'].decode('utf-8')
    except UnicodeError as exc:
        raise ValueError('invalid catalog source') from exc
    # Inspect actual Get blocks; literals in comments must not admit new assets.
    catalog = re.sub(r'/\*.*?\*/|//[^\n]*', '', catalog, flags=re.S)
    require(re.search(r'BUILDING\s*=\s*"Land_House_1W01"\s*;', catalog)
            and re.search(r'VERSION\s*=\s*1\s*;', catalog), 'unsupported pilot catalog source')
    blocks = re.findall(r'layout.Id\s*=\s*"([^"]+)";\s*layout.History\s*=\s*"([^"]+)";(.*?)(?=\}\s*else)', catalog, re.S)
    actual = []
    for identity, history, body in blocks:
        props = re.findall(r'layout.Props.Insert\(new HCInteriorProp\("([^"]+)"[^;]+;', body)
        actual.append((identity, history, *props))
    require(tuple(actual) == PILOT, 'pilot asset/layout source changed; review adapter')
    for method, allowed in (('SearchType', set(SEARCH_TYPES)), ('ItemAllowed', {'', 'Rag', 'Battery9V'})):
        body = re.search(r'static bool ' + method + r'\(string type\)\s*\{([^}]+)\}', catalog)
        require(body is not None and set(re.findall(r'type == "([^"]*)"', body[1])) == allowed,
                'pilot native allowlist changed; review adapter')
    rules = sources['HCInteriorRules.c'].decode('utf-8')
    rules = re.sub(r'/\*.*?\*/|//[^\n]*', '', rules, flags=re.S)
    body = re.search(r'static bool PoolWithinBounds\([^)]*\)\s*\{([^}]+)\}', rules)
    require(body is not None and all(clause in body[1] for clause in
            ('entries <= 12', 'rags <= 4', 'batteries <= 2')), 'pilot allocation caps changed; review adapter')


def observations(record, artifacts):
    entries = bounded_list(record['Observations'], 5, 16)
    require(isinstance(artifacts, dict), 'artifact bytes required')
    result, folded, total = {}, set(), 0
    for entry in entries:
        fields(entry, 'Path Sha256 Kind')
        name = portable_name(entry['Path'])
        require(name.casefold() not in folded and name in artifacts and isinstance(entry['Kind'], str) and entry['Kind'] in KINDS, 'duplicate/missing/unsupported observation')
        folded.add(name.casefold())
        data = byte_input(artifacts[name], ARTIFACT_LIMIT)
        total += len(data)
        require(entry['Sha256'] == digest(data), 'observation hash mismatch')
        result[name] = entry['Kind']
    require(total <= ARTIFACT_TOTAL and set(artifacts) == set(result), 'unrelated or excessive artifact bytes')
    return result


def reference(refs, name, kind):
    require(isinstance(name, str) and refs.get(name) == kind, 'missing or wrong-kind observation reference')


def context(value, refs):
    fields(value, 'World Build NativeScriptsSha256 SurveyId BuildingPosition BuildingOrientation AssetPboSha256 Operator MeasuredAt Method CoordinateBasis BuildObservation AssetObservation')
    require(value['World'] == 'chernarusplus' and value['Build'] == BUILD
            and value['NativeScriptsSha256'] == NATIVE_SHA, 'world/build/native snapshot mismatch')
    identifier(value['SurveyId'])
    vector(value['BuildingPosition'], 30000)
    vector(value['BuildingOrientation'], 360)
    require(value['AssetPboSha256'] == ASSET_PBOS, 'installed asset snapshot mismatch')
    text_value(value['Operator'])
    try:
        measured = datetime.fromisoformat(value['MeasuredAt'])
        require(measured.tzinfo is not None, 'measurement time requires timezone')
    except (TypeError, ValueError) as exc:
        raise ValueError('invalid measurement timestamp') from exc
    require(value['Method'] in ('DayZDiag', 'Workbench', 'normal-server-survey')
            and value['CoordinateBasis'] == 'building-model-local-metres', 'explicit native survey method/basis required')
    reference(refs, value['BuildObservation'], 'native-build')
    reference(refs, value['AssetObservation'], 'asset-config')


def layout(value, expected, refs):
    fields(value, 'Id History Props Survey')
    identity, history, *assets = expected
    require(value['Id'] == identity and value['History'] == history, 'pilot identity/history changed')
    props = bounded_list(value['Props'], 2, 2)
    for i, prop in enumerate(props):
        fields(prop, 'Type Position Orientation Searchable SearchPoint')
        require(prop['Type'] == assets[i] and type(prop['Searchable']) is bool
                and prop['Searchable'] == (i == 0), 'unsupported prop/search classification')
        vector(prop['Position'], 100)
        vector(prop['Orientation'], 360)
        vector(prop['SearchPoint'], 3)
        require(prop['Searchable'] or prop['SearchPoint'] == [0, 0, 0], 'nonsearch prop has search offset')
    survey = value['Survey']
    fields(survey, 'Bounds Props Stairs DoorObservation StairObservation MinimumClearanceMetres Keepouts')
    outer = box(survey['Bounds'])
    clearance = number(survey['MinimumClearanceMetres'], .001, 5)
    require(survey['Stairs'] in ('present', 'absent'), 'explicit stairs observation required')
    reference(refs, survey['DoorObservation'], 'door-clearance')
    reference(refs, survey['StairObservation'], 'stairs-clearance')
    keepouts, ids, kinds = [], set(), set()
    for keepout in bounded_list(survey['Keepouts'], 1, 32):
        fields(keepout, 'Id Kind Bounds')
        key = identifier(keepout['Id'])
        require(key not in ids and keepout['Kind'] in ('door', 'stairs'), 'duplicate/unsupported keepout')
        ids.add(key)
        kinds.add(keepout['Kind'])
        bounds = box(keepout['Bounds'])
        require(contains(outer, bounds), 'keepout outside surveyed bounds')
        keepouts.append(bounds)
    require('door' in kinds and ('stairs' in kinds) == (survey['Stairs'] == 'present'), 'door/stair keepout missing or inconsistent')
    boxes, room = [], None
    for i, measured in enumerate(bounded_list(survey['Props'], 2, 2)):
        fields(measured, 'Index Room Bounds Observation')
        require(type(measured['Index']) is int and measured['Index'] == i and isinstance(measured['Room'], str) and measured['Room'] in ROOMS, 'invalid measured prop/room binding')
        reference(refs, measured['Observation'], 'geometry')
        bounds = box(measured['Bounds'])
        position = props[i]['Position']
        require(contains(outer, bounds) and contains(bounds, (position, position)), 'prop or anchor outside measured bounds')
        require(all(gap(bounds, k) >= clearance for k in keepouts), 'prop violates observed movement clearance')
        require(all(gap(bounds, b) > 0 for b in boxes), 'overlapping measured props')
        boxes.append(bounds)
        if props[i]['Searchable']:
            room = measured['Room']
    return room


def policy(value, rooms, refs):
    fields(value, 'ItemGroups Rules Limits')
    fields(value['Limits'], 'Slots Rag Battery9V')
    for name, cap in (('Slots', 12), ('Rag', 4), ('Battery9V', 2)):
        integer(value['Limits'][name], 1 if name == 'Slots' else 0, cap)
    groups = {}
    for group in bounded_list(value['ItemGroups'], 1, 8):
        fields(group, 'Id Items')
        key = identifier(group['Id'])
        items = bounded_list(group['Items'], 1, 2)
        require(key not in groups and all(isinstance(item, str) and item in ('Rag', 'Battery9V') for item in items)
                and len(set(items)) == len(items), 'duplicate or unsupported item group')
        require(all(value['Limits'][item] > 0 for item in items), 'policy item has no supplementary cap')
        groups[key] = items
    seen, used = set(), set()
    for rule in bounded_list(value['Rules'], 3, 3):
        fields(rule, 'LayoutId Room History Risk ItemGroups EmptyAllowed MaxItems Selection Condition Storage Observation Rationale')
        identity = rule['LayoutId']
        require(isinstance(identity, str) and identity in rooms and identity not in seen, 'missing/duplicate/unsupported layout rule')
        seen.add(identity)
        require((rule['Room'], rule['History']) == rooms[identity], 'policy room/history differs from measured site')
        identifier(rule['Risk'])
        text_value(rule['Rationale'], 16, 512)
        reference(refs, rule['Observation'], 'geometry')
        selected = bounded_list(rule['ItemGroups'], 1, 8)
        require(all(isinstance(g, str) and g in groups for g in selected) and len(set(selected)) == len(selected), 'unknown/duplicate item group reference')
        used.update(selected)
        require(rule['EmptyAllowed'] is True and type(rule['MaxItems']) is int and rule['MaxItems'] == 1
                and rule['Selection'] == 'unweighted-review-only' and rule['Condition'] == 'unmodified-native'
                and rule['Storage'] == 'added-searchable-prop', 'unsupported allocation/balance/storage policy')
    require(seen == set(rooms) and used == set(groups), 'missing context rules or unrelated groups')


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')


def prepare(raw, sources, artifacts):
    """Return review files and report; never modify a caller record or game state."""
    record = load_record(raw)
    fields(record, 'SchemaVersion Synthetic Context SourceSha256 BuildingType CatalogVersion Layouts Observations Policy')
    require(type(record['SchemaVersion']) is int and record['SchemaVersion'] == 1
            and type(record['Synthetic']) is bool and type(record['CatalogVersion']) is int
            and record['CatalogVersion'] == 1 and record['BuildingType'] == 'Land_House_1W01', 'unsupported record/catalog version or building')
    source_catalog(sources)
    require(record['SourceSha256'] == {n: digest(v) for n, v in sources.items()}, 'source binding mismatch')
    refs = observations(record, artifacts)
    context(record['Context'], refs)
    rooms = {}
    layouts = bounded_list(record['Layouts'], 3, 3)
    for value, expected in zip(layouts, PILOT):
        room = layout(value, expected, refs)
        rooms[value['Id']] = room, value['History']
    policy(record['Policy'], rooms, refs)
    candidate = {'SchemaVersion': 1, 'CatalogVersion': 1, 'BuildingType': record['BuildingType'],
                 'Synthetic': record['Synthetic'], 'RecordSha256': digest(raw),
                 'Layouts': [{k: v for k, v in value.items() if k != 'Survey'} for value in layouts]}
    files = {'measured-record.json': raw, 'interior-layouts.candidate.json': encode(candidate),
             'context-policy.candidate.json': encode(record['Policy'])}
    report = {'schema': 1, 'status': 'synthetic-candidate-only' if record['Synthetic'] else 'candidate-native-validation-required',
              'synthetic': record['Synthetic'], 'runtime_loader_wired': False, 'production_accepted': False,
              'record_sha256': digest(raw), 'source_sha256': record['SourceSha256'],
              'observations': record['Observations'], 'world': record['Context']['World'], 'build': record['Context']['Build'],
              'candidate_sha256': {n: digest(v) for n, v in files.items()},
              'pending': ['measured-evidence-review', 'runtime-loader-and-live-house-binding',
                          'DayZDiag-fit-collision-door-stair-targeting', 'normal-PBO-server-and-two-client-tests',
                          'CE-ownership-and-durable-inventory-commit', 'rarity-condition-balance-and-3-6-player-benchmarks']}
    files['interior-report.json'] = encode(report)
    return files, report


def checked_path(path):
    path = Path(path).absolute()
    require('..' not in path.parts and all(not part.is_symlink() for part in (path, *path.parents)), 'symlink or traversal path forbidden')
    return path


def read_file(path, limit):
    path = checked_path(path)
    require(stat.S_ISREG(path.stat().st_mode), 'input must be a regular file')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'input must be a regular file')
        return byte_input(stream.read(limit + 1), limit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--sources', type=Path, required=True, help='Directory containing the three current interior sources')
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='New review directory; never an installation destination')
    args = parser.parse_args()
    try:
        raw = read_file(args.record, RECORD_LIMIT)
        record = load_record(raw)
        fields(record, 'SchemaVersion Synthetic Context SourceSha256 BuildingType CatalogVersion Layouts Observations Policy')
        entries = bounded_list(record['Observations'], 5, 16)
        source_root, artifact_root, out = map(checked_path, (args.sources, args.artifacts, args.out))
        require(source_root.is_dir() and artifact_root.is_dir(), 'source/artifact directory required')
        require(not any(out == root or root in out.parents for root in (source_root, artifact_root, checked_path(args.record))), 'output overlaps an input tree')
        sources = {n: read_file(source_root / n, SOURCE_LIMIT) for n in SOURCE_NAMES}
        artifacts, total = {}, 0
        for entry in entries:
            fields(entry, 'Path Sha256 Kind')
            name = portable_name(entry['Path'])
            require(name.casefold() not in {n.casefold() for n in artifacts}, 'duplicate observation path')
            data = read_file(artifact_root / name, ARTIFACT_LIMIT)
            total += len(data)
            require(total <= ARTIFACT_TOTAL, 'artifact total exceeds limit')
            artifacts[name] = data
        files, report = prepare(raw, sources, artifacts)
        out.mkdir()
        for name, data in files.items():
            with (out / name).open('xb') as stream:
                stream.write(data)
        print(json.dumps({'status': report['status'], 'runtime_loader_wired': False}))
    except (ValueError, OSError, KeyError, TypeError, RecursionError, OverflowError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
