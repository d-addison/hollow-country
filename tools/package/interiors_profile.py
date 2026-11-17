"""Interior data pack: derive, validate, install and byte-exact roll back.

The pack (mission/hollow-country/interiors) holds the server-profile data the interior
placement module (HCInteriorsModule.OnStart) and the infected room catalog
(HCInfectedRooms) load from "$profile:HollowCountry/". Everything in it is DERIVED from small,
reviewed evidence records; nothing is measured here and nothing is guessed:

  evidence/house-candidates.json  native pose observation (run 060 real-house acquisition)
  pack-profile.json               epoch/seed/slot choices (the only authored decisions)
  interiors.json                  HCInteriorConfig, derived from the two files above
  interiors-measured-profile.json + measured-interiors/*   only after a reviewed native survey
  evidence/room-survey.json, evidence/house-classes.json + Infected/production-rooms.json
                                  only after a native room survey and House-class census

A component without its native measurement is "pending-measurement" and absent. Validation
reports it with the exact measurement it still needs. Offline validation mirrors the Enforce
admission rules for review; it never establishes DayZ behaviour, fit, rooms or acceptance, and
the runtime acceptance of every component stays pending.

Install and rollback target a stopped server's <profiles>/HollowCountry directory. Install
records an intent receipt and backups of replaced files first, never writes through a symlink or
hard link, and refuses to touch a different file unless --replace is given. Rollback restores
the exact prior bytes, refuses drift, and never deletes files it does not own. It never touches
interiors_s1_e<epoch> journals.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import sys
from decimal import Decimal

try:
    from tools.package import interior_catalog as catalog
    from tools.package.economy import child, fresh_write, plain_file, read_plain
except ImportError:  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.package import interior_catalog as catalog
    from tools.package.economy import child, fresh_write, plain_file, read_plain

WORLD = 'chernarusplus'
BUILD = '1.30.164289'
BUILDING = 'Land_House_1W01'
PROFILE_DIRECTORY = 'HollowCountry'
MANAGED = 'hc-interiors-pack'
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACK = ROOT / 'mission/hollow-country/interiors'
ENFORCE_SOURCES = ROOT / 'mods/HollowCountry/scripts/4_World/Interiors'
FILE_LIMIT = 1048576
MEASURED_TEXT_LIMIT = 32767
PROFILE_TEXT_LIMIT = 262144
EVIDENCE_BUILDS = (BUILD, BUILD + '.70')
LAYOUTS = tuple((row[0], row[1]) for row in catalog.PILOT)
DISPOSITIONS = ('unmeasured', 'not_enterable', 'path_pending', 'door_pending', 'unsupported_geometry')
CONFIG_KEYS = ('SchemaVersion', 'MapName', 'Build', 'Epoch', 'Seed', 'InitializeNewEpoch', 'MigrateLegacyJournal',
               'DiagnosticPlacementTrial', 'DiagnosticSearchTrial', 'Candidates')
CANDIDATE_KEYS = ('SlotId', 'Type', 'Position', 'Orientation')
PROFILE_KEYS = ('SchemaVersion EnableTrustedExperiment TrustedExternalValidation WorldName Build TrustedAddonSha256 '
                'TrustedValidatorSha256 SourceSha256 ExpectedRecordText ExpectedCandidateText ExpectedPolicyText '
                'ExpectedReportText').split()
MEASURED_FILES = ('measured-interiors/measured-record.json', 'measured-interiors/interior-layouts.candidate.json',
                  'measured-interiors/context-policy.candidate.json', 'measured-interiors/interior-report.json')
MEASURED_PROFILE = 'interiors-measured-profile.json'
ROOMS_FILE = 'Infected/production-rooms.json'
ROOM_SOURCES = ('evidence/room-survey.json', 'evidence/house-classes.json')
CORE_FILES = ('pack.json', 'pack-profile.json', 'interiors.json', 'evidence/house-candidates.json')
ALLOWED = set(CORE_FILES) | set(ROOM_SOURCES) | {ROOMS_FILE, MEASURED_PROFILE, *MEASURED_FILES}
PENDING = 'pending-measurement'
PRESENT = 'present-pending-native-acceptance'
NEEDS_MEASURED = (
    'Native survey (DayZDiag or normal-server-survey) of the evidenced Land_House_1W01 pose that yields an '
    'interior_catalog schema-1 record: authored prop Position/Orientation/SearchPoint and measured bounds for '
    'the three pilot layouts, room labels, door-sweep and stair keepouts, clearance observations, and the five '
    'observation artifacts (native-build, asset-config, geometry, door-clearance, stairs-clearance).',
    'The record SourceSha256 must equal the current HCInteriorCatalog.c, HCInteriorRules.c and HCInteriorStore.c digests.',
    'Then: interiors_profile.py generate --measured-record R --sources DIR --artifacts DIR --trusted-addon-sha256 SHA.')
NEEDS_ROOMS = (
    'Native room survey with per-room local bounds for each admitted house; the pose-only acquisition has no room '
    'labels or bounds. The run id must start with native- and its SHA-256 pins the survey bytes.',
    'Native House-class census: every installed CfgVehicles House subclass, each classified (covered by a survey '
    'building, or unmeasured/not_enterable/path_pending/door_pending/unsupported_geometry).',
    'Then: interiors_profile.py generate --rooms-survey S --house-classes C.')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def scrub(text):
    return str(text).replace(str(Path.home()), '~')


# ---- Enforce scalar rules mirrored with float32 arithmetic (HCInteriorRules) -------------------

def f32(value):
    try:
        return struct.unpack('<f', struct.pack('<f', value))[0]
    except (OverflowError, struct.error) as exc:
        raise ValueError('number outside float32 range') from exc


def quantize(value):
    scaled = f32(f32(value) * 100.0)
    return math.floor(f32(scaled + 0.5))


def yaw(angle):
    angle = f32(angle)
    turns = math.floor(f32(angle / 360.0))
    return quantize(f32(angle - f32(turns * 360.0))) % 36000


def layout_index(x, y, z, yaw_value, seed):
    return ((abs(x) % 1009) * 31 + (abs(y) % 1009) * 17 + (abs(z) % 1009) * 13 + yaw_value + seed) % 3


def transform_key(position, orientation):
    return '_'.join(str(n) for n in (quantize(position[0]), quantize(position[1]), quantize(position[2]),
                                      yaw(orientation[0]), quantize(orientation[1]), quantize(orientation[2])))


def instance_id(candidate, epoch):
    return (f'chernarusplus_130164289_s1_e{epoch}_{candidate["Type"]}_'
            f'{transform_key(candidate["Position"], candidate["Orientation"])}_d{candidate["SlotId"]}')


def selected_layout(candidate, seed):
    p, o = candidate['Position'], candidate['Orientation']
    return LAYOUTS[layout_index(quantize(p[0]), quantize(p[1]), quantize(p[2]), yaw(o[0]), seed)]


# ---- JSON text -----------------------------------------------------------------------------

def number_text(value):
    """Plain decimal that parses back to the same float32 and fits the 32-character native grammar."""
    exact = f32(float(value))
    if exact == 0:
        return '0.0'
    text = repr(exact)
    if 'e' in text.lower() or len(text) > 32:
        for digits in range(1, 10):
            text = '%.*g' % (digits, exact)
            if f32(float(text)) == exact:
                break
        if 'e' in text.lower():
            text = format(Decimal(text), 'f')
    if '.' not in text:
        text += '.0'
    require(len(text) <= 32, 'number text exceeds the native 32-character grammar')
    return text


def _scalar(value):
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    if value is None:
        return 'null'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return number_text(value)
    return json.dumps(value)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def dumps(value, level=0):
    pad = '  ' * level
    if isinstance(value, dict):
        if not value:
            return '{}'
        rows = ',\n'.join(f'{pad}  {json.dumps(k)}: {dumps(v, level + 1)}' for k, v in value.items())
        return '{\n' + rows + '\n' + pad + '}'
    if isinstance(value, (list, tuple)):
        if not value:
            return '[]'
        if all(_is_number(v) for v in value):
            return '[' + ', '.join(_scalar(v) for v in value) + ']'
        rows = ',\n'.join(pad + '  ' + dumps(v, level + 1) for v in value)
        return '[\n' + rows + '\n' + pad + ']'
    return _scalar(value)


def encode(value):
    return (dumps(value) + '\n').encode('ascii')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('nonfinite JSON constant')


def parse(raw, name, limit=FILE_LIMIT):
    require(isinstance(raw, bytes) and 0 < len(raw) <= limit, f'{name}: size outside limits')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ValueError(f'{name}: invalid JSON') from exc


# ---- shared value checks ---------------------------------------------------------------------

def exact_keys(value, keys, name):
    require(isinstance(value, dict) and set(value) == set(keys), f'{name}: unsupported or missing fields')


def hash_ok(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None and value != '0' * 64


def token(value, limit=128):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]+', value) is not None and 1 <= len(value) <= limit


def vec(value, limit, name, exact=True):
    require(isinstance(value, list) and len(value) == 3 and all(_is_number(v) and math.isfinite(v) for v in value),
            f'{name}: expected three finite numbers')
    for v in value:
        require(-limit <= v <= limit, f'{name}: outside bounds')
        require(not exact or f32(v) == v, f'{name}: not float32-exact')
    return [f32(v) for v in value]


def native_run(value, name):
    require(token(value, 96) and len(value) >= 8, f'{name}: invalid run id')
    low = value.lower()
    require(not any(w in low for w in ('synthetic', 'fixture', 'selftest')), f'{name}: synthetic/fixture run id refused')


def native_room_run(value, name):
    native_run(value, name)
    require(value.lower().startswith('native-'), f'{name}: run id must start with native-')


def same_pose(a_position, a_orientation, b_position, b_orientation):
    return ([f32(v) for v in a_position] == [f32(v) for v in b_position]
            and [f32(v) for v in a_orientation] == [f32(v) for v in b_orientation])


# ---- pack-profile and evidence ---------------------------------------------------------------

def load_profile(raw):
    data = parse(raw, 'pack-profile.json', 65536)
    exact_keys(data, ('schema', 'world', 'build', 'epoch', 'seed', 'initialize_new_epoch', 'slots'), 'pack-profile.json')
    require(data['schema'] == 1 and type(data['schema']) is int, 'pack-profile.json: unsupported schema')
    require(data['world'] == WORLD and data['build'] == BUILD, 'pack-profile.json: world/build mismatch')
    for key, lo, hi in (('epoch', 1, 899999), ('seed', 1, 1000000)):
        require(type(data[key]) is int and lo <= data[key] <= hi, f'pack-profile.json: {key} outside supported bounds')
    require(type(data['initialize_new_epoch']) is bool, 'pack-profile.json: initialize_new_epoch must be boolean')
    slots = data['slots']
    require(isinstance(slots, list) and 1 <= len(slots) <= 12, 'pack-profile.json: 1..12 slots required')
    for slot in slots:
        exact_keys(slot, ('slot_id', 'house'), 'pack-profile.json slot')
        require(type(slot['slot_id']) is int and 0 <= slot['slot_id'] < 12 and token(slot['house']), 'pack-profile.json: invalid slot')
    require(len({s['slot_id'] for s in slots}) == len(slots) and len({s['house'] for s in slots}) == len(slots),
            'pack-profile.json: duplicate slot or house')
    return data


def load_evidence(raw):
    data = parse(raw, 'evidence/house-candidates.json', 65536)
    exact_keys(data, ('schema', 'kind', 'world', 'build', 'source', 'houses'), 'evidence')
    require(data['schema'] == 1 and type(data['schema']) is int and data['kind'] == 'native-house-pose-evidence',
            'evidence: unsupported schema/kind')
    require(data['world'] == WORLD and data['build'] == BUILD, 'evidence: world/build mismatch')
    source = data['source']
    exact_keys(source, ('kind', 'run_id', 'engine_version', 'result_sha256', 'request_sha256', 'survey_complete',
                        'gameplay_acceptance'), 'evidence source')
    require(source['kind'] == 'native-real-house-measurement-acquisition', 'evidence: unsupported source kind')
    native_run(source['run_id'], 'evidence run id')
    require(source['engine_version'] in EVIDENCE_BUILDS, 'evidence: engine build mismatch')
    require(hash_ok(source['result_sha256']) and hash_ok(source['request_sha256']), 'evidence: source pins must be SHA-256')
    require(source['survey_complete'] is False and source['gameplay_acceptance'] is False,
            'evidence: pose acquisition is not a completed survey or acceptance')
    houses = data['houses']
    require(isinstance(houses, list) and 1 <= len(houses) <= 12, 'evidence: 1..12 houses required')
    seen, keys = set(), set()
    for house in houses:
        exact_keys(house, ('id', 'building_class', 'position', 'orientation', 'matches'), 'evidence house')
        require(token(house['id']) and house['id'] not in seen, 'evidence: invalid or duplicate house id')
        seen.add(house['id'])
        require(house['building_class'] == BUILDING, 'evidence: only Land_House_1W01 is supported by the pilot')
        require(house['matches'] == 1 and type(house['matches']) is int, 'evidence: pose was not a unique native match')
        position = vec(house['position'], 20000, 'evidence position')
        orientation = vec(house['orientation'], 360, 'evidence orientation')
        require(orientation[1] == 0 and orientation[2] == 0, 'evidence: tilted building unsupported by the yaw-only pilot')
        key = transform_key(position, orientation)
        require(key not in keys, 'evidence: duplicate quantised pose')
        keys.add(key)
    return data


def evidence_house(evidence, building_class, position, orientation):
    for house in evidence['houses']:
        if house['building_class'] == building_class and same_pose(house['position'], house['orientation'], position, orientation):
            return house
    return None


# ---- interiors.json ----------------------------------------------------------------------------

def derive_config(profile, evidence):
    houses = {h['id']: h for h in evidence['houses']}
    candidates = []
    for slot in sorted(profile['slots'], key=lambda s: s['slot_id']):
        house = houses.get(slot['house'])
        require(house is not None, f'pack-profile.json: slot references a house without native pose evidence: {slot["house"]}')
        candidates.append({'SlotId': slot['slot_id'], 'Type': house['building_class'],
                           'Position': [f32(v) for v in house['position']],
                           'Orientation': [f32(v) + 0.0 for v in house['orientation']]})
    return {'SchemaVersion': 1, 'MapName': WORLD, 'Build': BUILD, 'Epoch': profile['epoch'], 'Seed': profile['seed'],
            'InitializeNewEpoch': profile['initialize_new_epoch'], 'MigrateLegacyJournal': False,
            'DiagnosticPlacementTrial': False, 'DiagnosticSearchTrial': False, 'Candidates': candidates}


def check_config(config, evidence):
    """Mirror HCInteriorsModule.ValidateConfig for review, and bind every candidate to native pose evidence."""
    exact_keys(config, CONFIG_KEYS, 'interiors.json')
    require(config['SchemaVersion'] == 1 and type(config['SchemaVersion']) is int, 'interiors.json: schema/map/build mismatch')
    require(config['MapName'] == WORLD and config['Build'] == BUILD, 'interiors.json: schema/map/build mismatch')
    require(type(config['Epoch']) is int and 1 <= config['Epoch'] <= 899999, 'interiors.json: epoch outside supported bounds')
    require(type(config['Seed']) is int and 1 <= config['Seed'] <= 1000000, 'interiors.json: seed outside supported bounds')
    require(type(config['InitializeNewEpoch']) is bool, 'interiors.json: InitializeNewEpoch must be boolean')
    for key in ('MigrateLegacyJournal', 'DiagnosticPlacementTrial', 'DiagnosticSearchTrial'):
        require(config[key] is False, f'interiors.json: {key} must be false in a shipped pack')
    candidates = config['Candidates']
    require(isinstance(candidates, list) and 1 <= len(candidates) <= 12, 'interiors.json: 1..12 candidates required')
    slots, keys = set(), set()
    for candidate in candidates:
        exact_keys(candidate, CANDIDATE_KEYS, 'interiors.json candidate')
        require(type(candidate['SlotId']) is int and 0 <= candidate['SlotId'] < 12, 'interiors.json: invalid stable slot')
        require(candidate['Type'] == BUILDING, 'interiors.json: unsupported building class')
        position = vec(candidate['Position'], 20000, 'interiors.json position')
        orientation = vec(candidate['Orientation'], 360, 'interiors.json orientation')
        require(orientation[1] == 0 and orientation[2] == 0, 'interiors.json: tilted building unsupported by yaw-only pilot')
        key = transform_key(position, orientation)
        require(candidate['SlotId'] not in slots and key not in keys, 'interiors.json: duplicate slot/quantised building identity')
        slots.add(candidate['SlotId'])
        keys.add(key)
        require(evidence_house(evidence, candidate['Type'], position, orientation) is not None,
                'interiors.json: candidate has no matching native pose evidence (exact float32 pose required)')
    require([c['SlotId'] for c in candidates] == sorted(slots), 'interiors.json: candidates must be listed in slot order')


# ---- infected production rooms -----------------------------------------------------------------

def _box(value, name):
    return vec(value, 512, name, exact=False)


def parse_survey(raw, evidence):
    data = parse(raw, 'room survey')
    exact_keys(data, ('schema', 'kind', 'world', 'build', 'source_run_id', 'source_sha256', 'buildings'), 'room survey')
    require(data['schema'] == 1 and data['kind'] == 'native-room-survey-input', 'room survey: unsupported schema/kind')
    require(data['world'] == WORLD and data['build'] == BUILD, 'room survey: world/build mismatch')
    native_room_run(data['source_run_id'], 'room survey run id')
    require(hash_ok(data['source_sha256']), 'room survey: source_sha256 must be a nonzero lowercase SHA-256')
    buildings = data['buildings']
    require(isinstance(buildings, list) and 1 <= len(buildings) <= 64, 'room survey: 1..64 buildings required')
    houses, total, result = set(), 0, []
    for building in buildings:
        exact_keys(building, ('house', 'building_class', 'position', 'orientation', 'box_min', 'box_max', 'rooms'), 'room survey building')
        require(token(building['house']) and building['house'] not in houses, 'room survey: invalid or duplicate house')
        houses.add(building['house'])
        position = vec(building['position'], 20000, 'room survey position', exact=False)
        orientation = vec(building['orientation'], 360, 'room survey orientation', exact=False)
        match = evidence_house(evidence, building['building_class'], position, orientation)
        require(match is not None and match['id'] == building['house'],
                'room survey: building has no matching native pose evidence (exact float32 pose and class required)')
        low, high = _box(building['box_min'], 'room box_min'), _box(building['box_max'], 'room box_max')
        require(all(a < b for a, b in zip(low, high)), 'room survey: empty or inverted house box')
        rooms = building['rooms']
        require(isinstance(rooms, list) and 1 <= len(rooms) <= 16, 'room survey: 1..16 rooms per house required')
        total += len(rooms)
        require(total <= 256, 'room survey: more than 256 rooms in total')
        ids, points, anchors = set(), [], []
        for room in rooms:
            exact_keys(room, ('id', 'local_position', 'local_min', 'local_max'), 'room survey room')
            require(type(room['id']) is int and 1 <= room['id'] <= 64 and room['id'] not in ids, 'room survey: invalid or duplicate room id')
            ids.add(room['id'])
            point = vec(room['local_position'], 512, 'room position', exact=False)
            rmin, rmax = vec(room['local_min'], 512, 'room local_min', exact=False), vec(room['local_max'], 512, 'room local_max', exact=False)
            for axis in range(3):
                require(low[axis] <= rmin[axis] < rmax[axis] <= high[axis], 'room survey: room box outside the house box')
                require(rmin[axis] <= point[axis] <= rmax[axis], 'room survey: room point outside its room box')
            for previous in points:
                require(sum((a - b) ** 2 for a, b in zip(previous, point)) >= 1.001, 'room survey: room points closer than 1 m')
            points.append(point)
            anchors.append({'Id': room['id'], 'LocalPosition': point, 'LocalMin': rmin, 'LocalMax': rmax,
                            'SourceRunId': data['source_run_id'], 'SourceSha256': data['source_sha256'],
                            'EvidenceKind': 'native-room-survey-v1'})
        result.append({'BuildingClass': building['building_class'], 'Position': position, 'Orientation': orientation,
                       'BoxMin': low, 'BoxMax': high, 'Anchors': anchors})
    return data, result


def parse_classes(raw, surveyed):
    data = parse(raw, 'house-class census')
    exact_keys(data, ('schema', 'kind', 'world', 'build', 'source_run_id', 'source_sha256', 'house_classes', 'dispositions'),
               'house-class census')
    require(data['schema'] == 1 and data['kind'] == 'native-house-class-census', 'house-class census: unsupported schema/kind')
    require(data['world'] == WORLD and data['build'] == BUILD, 'house-class census: world/build mismatch')
    native_room_run(data['source_run_id'], 'house-class census run id')
    require(hash_ok(data['source_sha256']), 'house-class census: source_sha256 must be a nonzero lowercase SHA-256')
    classes = data['house_classes']
    require(isinstance(classes, list) and 1 <= len(classes) <= 2048 and all(token(c, 128) for c in classes),
            'house-class census: 1..2048 valid class names required')
    require(len(set(classes)) == len(classes), 'house-class census: duplicate class')
    dispositions = data['dispositions']
    require(isinstance(dispositions, dict), 'house-class census: dispositions must be an object')
    for name, value in dispositions.items():
        require(name in classes and value in DISPOSITIONS, 'house-class census: unknown class or unsupported disposition')
        require(name not in surveyed, 'house-class census: a surveyed class cannot also carry a non-covered disposition')
    for name in surveyed:
        require(name in classes, 'house-class census: surveyed class missing from the denominator')
    for name in classes:
        require(name in surveyed or name in dispositions, 'house-class census: class lacks a disposition')
    rows = [{'BuildingClass': name, 'Disposition': 'covered' if name in surveyed else dispositions[name]} for name in sorted(classes)]
    return data, rows


def derive_rooms(survey_raw, classes_raw, evidence):
    survey, buildings = parse_survey(survey_raw, evidence)
    surveyed = {b['BuildingClass'] for b in buildings}
    classes, rows = parse_classes(classes_raw, surveyed)
    document = {'SchemaVersion': 1, 'Build': BUILD, 'WorldName': WORLD, 'Classes': rows, 'Buildings': buildings}
    production = encode(document)
    require(len(production) <= FILE_LIMIT, 'production rooms exceed the 1 MiB native read limit')
    return {ROOM_SOURCES[0]: encode(survey), ROOM_SOURCES[1]: encode(classes), ROOMS_FILE: production}


# ---- measured interiors ------------------------------------------------------------------------

def validator_sha():
    return sha(Path(catalog.__file__).read_bytes())


def derive_measured(spec, config, evidence):
    require(isinstance(spec, dict) and {'record', 'sources', 'artifacts', 'trusted_addon_sha256'} <= set(spec),
            'measured: record, sources, artifacts and trusted_addon_sha256 required')
    require(hash_ok(spec['trusted_addon_sha256']), 'measured: trusted addon SHA-256 must be nonzero lowercase hex')
    files, report = catalog.prepare(spec['record'], spec['sources'], spec['artifacts'])
    require(report['synthetic'] is False, 'measured: synthetic records cannot ship in the pack')
    record = json.loads(spec['record'].decode('utf-8'))
    context = record['Context']
    require(any(same_pose(c['Position'], c['Orientation'], context['BuildingPosition'], context['BuildingOrientation'])
                and c['Type'] == record['BuildingType'] for c in config['Candidates']),
            'measured: record house is not an interiors.json candidate (exact float32 pose required)')
    for name, data in files.items():
        require(len(data) <= MEASURED_TEXT_LIMIT, f'measured: {name} exceeds the native 32767 byte read limit')
    texts = {n: files[n].decode('utf-8') for n in ('measured-record.json', 'interior-layouts.candidate.json',
                                                   'context-policy.candidate.json', 'interior-report.json')}
    profile = {'SchemaVersion': 1, 'EnableTrustedExperiment': True, 'TrustedExternalValidation': True,
               'WorldName': WORLD, 'Build': BUILD, 'TrustedAddonSha256': spec['trusted_addon_sha256'],
               'TrustedValidatorSha256': validator_sha(), 'SourceSha256': record['SourceSha256'],
               'ExpectedRecordText': texts['measured-record.json'],
               'ExpectedCandidateText': texts['interior-layouts.candidate.json'],
               'ExpectedPolicyText': texts['context-policy.candidate.json'],
               'ExpectedReportText': texts['interior-report.json']}
    profile_bytes = encode(profile)
    require(len(profile_bytes) <= PROFILE_TEXT_LIMIT, 'measured: profile exceeds the native 262144 byte limit')
    result = {'measured-interiors/' + name: data for name, data in files.items()}
    result[MEASURED_PROFILE] = profile_bytes
    return result


def check_measured(raw, config, current_sources=True):
    """Structural re-check of measured files already in the pack (no record re-derivation is possible)."""
    require(all(n in raw for n in (MEASURED_PROFILE, *MEASURED_FILES)), 'measured: profile and all four measured files required together')
    for name in MEASURED_FILES:
        require(len(raw[name]) <= MEASURED_TEXT_LIMIT, f'measured: {name} exceeds the native read limit')
    profile = parse(raw[MEASURED_PROFILE], MEASURED_PROFILE, PROFILE_TEXT_LIMIT)
    exact_keys(profile, PROFILE_KEYS, MEASURED_PROFILE)
    require(profile['SchemaVersion'] == 1 and profile['EnableTrustedExperiment'] is True
            and profile['TrustedExternalValidation'] is True, 'measured profile: unsupported schema or trust flags')
    require(profile['WorldName'] == WORLD and profile['Build'] == BUILD, 'measured profile: world/build mismatch')
    require(hash_ok(profile['TrustedAddonSha256']) and hash_ok(profile['TrustedValidatorSha256']), 'measured profile: trust pins must be SHA-256')
    for key, name in (('ExpectedRecordText', MEASURED_FILES[0]), ('ExpectedCandidateText', MEASURED_FILES[1]),
                      ('ExpectedPolicyText', MEASURED_FILES[2]), ('ExpectedReportText', MEASURED_FILES[3])):
        require(isinstance(profile[key], str) and profile[key].encode('utf-8') == raw[name],
                f'measured profile: {key} differs from {name}')
    record = parse(raw[MEASURED_FILES[0]], MEASURED_FILES[0], MEASURED_TEXT_LIMIT)
    candidate = parse(raw[MEASURED_FILES[1]], MEASURED_FILES[1], MEASURED_TEXT_LIMIT)
    report = parse(raw[MEASURED_FILES[2 + 1]], MEASURED_FILES[3], MEASURED_TEXT_LIMIT)
    require(record.get('Synthetic') is False and candidate.get('Synthetic') is False and report.get('synthetic') is False,
            'measured: synthetic record refused')
    require(candidate.get('RecordSha256') == sha(raw[MEASURED_FILES[0]]) == report.get('record_sha256'),
            'measured: record digest binding mismatch')
    require(report.get('candidate_sha256') == {n.split('/')[-1]: sha(raw[n]) for n in MEASURED_FILES[:3]},
            'measured: report digests differ from the measured files')
    require(report.get('status') == 'candidate-native-validation-required' and report.get('production_accepted') is False
            and report.get('runtime_loader_wired') is False, 'measured: report must stay candidate-only')
    require(profile['SourceSha256'] == record.get('SourceSha256'), 'measured profile: SourceSha256 differs from the record')
    require(raw[MEASURED_FILES[2]] == catalog.encode(record['Policy']), 'measured: policy file differs from the record policy')
    context = record['Context']
    require(any(same_pose(c['Position'], c['Orientation'], context['BuildingPosition'], context['BuildingOrientation'])
                and c['Type'] == record['BuildingType'] for c in config['Candidates']),
            'measured: record house is not an interiors.json candidate (exact float32 pose required)')
    if current_sources and ENFORCE_SOURCES.is_dir():
        now = {n: sha((ENFORCE_SOURCES / n).read_bytes()) for n in catalog.SOURCE_NAMES}
        require(record['SourceSha256'] == now, 'measured: record was built against different Enforce sources; re-review and regenerate')
        require(profile['TrustedValidatorSha256'] == validator_sha(), 'measured: interior_catalog.py changed since the profile was generated; regenerate')


# ---- manifest ------------------------------------------------------------------------------------

def derive_manifest(raw, config, profile):
    houses = {s['slot_id']: s['house'] for s in profile['slots']}
    instances = []
    for candidate in config['Candidates']:
        iid = instance_id(candidate, config['Epoch'])
        layout_id, history = selected_layout(candidate, config['Seed'])
        instances.append({'slot_id': candidate['SlotId'], 'house': houses[candidate['SlotId']], 'instance_id': iid,
                          'storage_site_id': iid + '_storage_v1', 'layout_id': layout_id, 'history': history})
    order = ['interiors.json', MEASURED_PROFILE, *MEASURED_FILES, ROOMS_FILE]
    files = {n: sha(raw[n]) for n in order if n in raw}
    sources = {n: sha(raw[n]) for n in ('pack-profile.json', 'evidence/house-candidates.json', *ROOM_SOURCES) if n in raw}
    has_measured, has_rooms = MEASURED_PROFILE in raw, ROOMS_FILE in raw
    components = [
        {'id': 'house-candidates', 'state': 'native-evidenced-pending-acceptance', 'count': len(instances)},
        {'id': 'measured-interiors', 'state': PRESENT if has_measured else PENDING},
        {'id': 'infected-production-rooms', 'state': PRESENT if has_rooms else PENDING}]
    if not has_measured:
        components[1]['needs'] = list(NEEDS_MEASURED)
    if not has_rooms:
        components[2]['needs'] = list(NEEDS_ROOMS)
    return {'schema': 1, 'kind': 'hollow-country-interiors-pack', 'world': WORLD, 'build': BUILD,
            'runtime_acceptance': 'pending', 'files': files, 'sources': sources, 'instances': instances,
            'components': components}


# ---- generate -------------------------------------------------------------------------------------

def _pack_dir(pack):
    pack = Path(pack).absolute()
    require(pack.is_dir() and not pack.is_symlink(), 'pack must be an existing real directory')
    return pack


def _read_member(pack, name):
    path = child(pack, name)
    if not os.path.lexists(path):
        return None
    st = os.lstat(path)
    require(stat.S_ISREG(st.st_mode) and not stat.S_ISLNK(st.st_mode), f'pack member is a symlink or not a regular file: {name}')
    require(st.st_size <= FILE_LIMIT, f'pack member too large: {name}')
    return path.read_bytes()


def _write_member(pack, name, data):
    path = child(pack, name)
    if os.path.lexists(path):
        st = os.lstat(path)
        require(stat.S_ISREG(st.st_mode) and not stat.S_ISLNK(st.st_mode), f'pack member is a symlink or not a regular file: {name}')
        if path.read_bytes() == data:
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    child(pack, name)
    temp = path.with_name(path.name + '.next')
    require(not os.path.lexists(temp), 'stale temporary pack file; remove it')
    with open(temp, 'xb') as stream:
        stream.write(data)
    os.replace(temp, path)


def generate(pack, rooms_input=None, classes_input=None, measured=None):
    pack = _pack_dir(pack)
    profile_raw, evidence_raw = (_read_member(pack, n) for n in ('pack-profile.json', 'evidence/house-candidates.json'))
    require(profile_raw is not None and evidence_raw is not None, 'pack-profile.json and evidence/house-candidates.json are required')
    profile, evidence = load_profile(profile_raw), load_evidence(evidence_raw)
    config = derive_config(profile, evidence)
    check_config(config, evidence)
    raw = {'pack-profile.json': profile_raw, 'evidence/house-candidates.json': evidence_raw, 'interiors.json': encode(config)}
    require((rooms_input is None) == (classes_input is None), 'room survey and house-class census must be supplied together')
    if rooms_input is not None:
        raw.update(derive_rooms(rooms_input, classes_input, evidence))
    else:
        existing = [_read_member(pack, n) for n in (*ROOM_SOURCES, ROOMS_FILE)]
        if any(v is not None for v in existing):
            require(existing[0] is not None and existing[1] is not None, 'room sources are incomplete; supply survey and census')
            raw.update(derive_rooms(existing[0], existing[1], evidence))
    if measured is not None:
        raw.update(derive_measured(measured, config, evidence))
    else:
        existing = {n: _read_member(pack, n) for n in (MEASURED_PROFILE, *MEASURED_FILES)}
        if any(v is not None for v in existing.values()):
            require(all(v is not None for v in existing.values()), 'measured files are incomplete; supply a measured record')
            raw.update(existing)
            check_measured(raw, config)
    for name, data in raw.items():
        if name not in ('pack-profile.json', 'evidence/house-candidates.json'):
            _write_member(pack, name, data)
    _write_member(pack, 'pack.json', encode(derive_manifest(raw, config, profile)))
    return validate(pack)


# ---- validate ---------------------------------------------------------------------------------------

def _members(pack, errors):
    raw = {}
    for current, dirs, names in os.walk(pack, followlinks=False):
        base = Path(current)
        for name in list(dirs):
            if (base / name).is_symlink():
                errors.append(f'symlinked directory in pack: {(base / name).relative_to(pack).as_posix()}')
                dirs.remove(name)
        for name in names:
            path = base / name
            rel = path.relative_to(pack).as_posix()
            st = os.lstat(path)
            if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
                errors.append(f'pack member is a symlink or not a regular file: {rel}')
            elif rel not in ALLOWED:
                errors.append(f'unexpected pack file (not an allowed derived/evidence file): {rel}')
            elif st.st_size > FILE_LIMIT:
                errors.append(f'pack member too large: {rel}')
            else:
                raw[rel] = path.read_bytes()
    return raw


def validate(pack):
    errors, pending = [], []
    try:
        pack = _pack_dir(pack)
    except (ValueError, OSError) as exc:
        return {'errors': [scrub(exc)], 'pending': [], 'files': {}}
    raw = _members(pack, errors)

    def guard(function, *args):
        try:
            return function(*args)
        except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
            errors.append(scrub(exc))
            return None

    missing = [n for n in CORE_FILES if n not in raw]
    if missing:
        errors.extend(f'required pack file missing: {n}' for n in missing)
        return {'errors': errors, 'pending': [], 'files': {}}
    profile = guard(load_profile, raw['pack-profile.json'])
    evidence = guard(load_evidence, raw['evidence/house-candidates.json'])
    if profile is None or evidence is None:
        return {'errors': errors, 'pending': [], 'files': {}}
    derived = guard(derive_config, profile, evidence)
    actual = guard(parse, raw['interiors.json'], 'interiors.json', 65536)
    if actual is not None:
        guard(check_config, actual, evidence)
        if derived is not None and actual != derived:
            errors.append('interiors.json differs from the config derived from pack-profile.json and the evidence (regenerate)')
    config = derived if derived is not None else actual
    rooms = [n for n in (*ROOM_SOURCES, ROOMS_FILE) if n in raw]
    if rooms:
        if len(rooms) != 3:
            errors.append('room data is incomplete: survey, census and production rooms must be present together')
        else:
            built = guard(derive_rooms, raw[ROOM_SOURCES[0]], raw[ROOM_SOURCES[1]], evidence)
            if built is not None:
                for name, data in built.items():
                    if raw[name] != data:
                        errors.append(f'{name} differs from the canonical derivation (regenerate)')
    if any(n in raw for n in (MEASURED_PROFILE, *MEASURED_FILES)) and config is not None:
        guard(check_measured, raw, config)
    manifest = guard(parse, raw['pack.json'], 'pack.json', 65536)
    if derived is not None and config is not None and not any(n for n in rooms if n not in raw):
        expected = guard(derive_manifest, raw, config, profile)
        if manifest is not None and expected is not None:
            for section in ('files', 'sources'):
                stored = manifest.get(section) if isinstance(manifest, dict) else None
                for name, digest in (expected[section] or {}).items():
                    if not isinstance(stored, dict) or stored.get(name) != digest:
                        errors.append(f'pack.json {section} sha256 pin for {name} does not match the file (regenerate)')
                if isinstance(stored, dict) and set(stored) != set(expected[section]):
                    errors.append(f'pack.json {section} lists a different file set than the pack holds (regenerate)')
            if manifest != expected:
                errors.append('pack.json differs from the manifest derived from the pack contents (regenerate)')
        if expected is not None:
            pending = [{'id': c['id'], 'state': c['state'], 'needs': c.get('needs', [])}
                       for c in expected['components'] if c['state'] == PENDING]
    return {'errors': errors, 'pending': pending, 'files': {n: sha(d) for n, d in sorted(raw.items())}}


# ---- install / rollback ---------------------------------------------------------------------------

def _target(target, must_exist=True):
    target = Path(target).absolute()
    require(target.name == PROFILE_DIRECTORY, f'target must be the profile directory named {PROFILE_DIRECTORY}')
    require(not target.is_symlink(), 'target is a symlink; refusing')
    if must_exist:
        require(target.is_dir(), 'target profile directory does not exist')
    else:
        require(not target.exists() or target.is_dir(), 'target is not a directory')
        require(target.parent.is_dir() and not target.parent.is_symlink(), 'profiles directory must exist and not be a symlink')
    child(target.parent, target.name)
    return target


def _managed_expected(receipt):
    names = {'receipt.json', 'receipt.next', 'place.next', 'restore.next'}
    names.update(f'backup/{i}.bak' for i, row in enumerate(receipt['files']) if row['action'] == 'replace')
    return names


def _preflight_managed(managed, receipt):
    expected = _managed_expected(receipt)
    for path in managed.rglob('*'):
        name = path.relative_to(managed).as_posix()
        child(managed, name)
        if path.is_dir() and not path.is_symlink():
            require(name == 'backup', 'unexpected managed directory; rollback refuses deletion')
            continue
        require(name in expected, 'unexpected managed file; rollback refuses deletion')
        plain_file(managed, path)


def install(pack, target, replace=False):
    pack = _pack_dir(pack)
    report = validate(pack)
    require(not report['errors'], 'pack invalid: ' + (report['errors'][0] if report['errors'] else ''))
    target = _target(target, must_exist=False)
    manifest = parse((pack / 'pack.json').read_bytes(), 'pack.json', 65536)
    config = parse((pack / 'interiors.json').read_bytes(), 'interiors.json', 65536)
    managed = child(target, MANAGED)
    require(not os.path.lexists(managed), 'already installed or interrupted installation; inspect/rollback first')
    journal = child(target, f'interiors_s1_e{config["Epoch"]}')
    require(not os.path.lexists(journal), 'an interiors journal already exists for this epoch; a changed pack needs an explicit new epoch')
    rows, created_dirs, planned = [], [], set()
    if not target.exists():
        created_dirs.append('.')
    for index, (name, digest) in enumerate(manifest['files'].items()):
        data = (pack / name).read_bytes()
        require(sha(data) == digest, 'pack changed during install')
        dest = child(target, name)
        row = {'path': name, 'action': 'create', 'sha256': digest}
        for parent in reversed(Path(name).parents):
            rel = parent.as_posix()
            if rel == '.' or rel in planned:
                continue
            planned.add(rel)
            where = child(target, rel)
            if os.path.lexists(where):
                require(where.is_dir() and not where.is_symlink(), f'profile path is not a directory: {rel}')
            else:
                created_dirs.append(rel)
        if os.path.lexists(dest):
            current = plain_file(target, dest).read_bytes()
            if current == data:
                row['action'] = 'keep'
            else:
                require(replace, f'a different {name} already exists; review it or pass --replace')
                row.update(action='replace', original_sha256=sha(current))
                row['_original'] = current
        row['_data'] = data
        rows.append(row)
    if not target.exists():
        target.mkdir()
    managed.mkdir()
    receipt = {'schema': 1, 'status': 'intent', 'pack_sha256': sha((pack / 'pack.json').read_bytes()),
               'epoch': config['Epoch'], 'created_dirs': created_dirs,
               'files': [{k: v for k, v in row.items() if not k.startswith('_')} for row in rows]}
    # Backups and the intent receipt exist before any profile file changes. Stop the server first.
    if any(r['action'] == 'replace' for r in rows):
        (managed / 'backup').mkdir()
        for index, row in enumerate(rows):
            if row['action'] == 'replace':
                fresh_write(managed, f'backup/{index}.bak', row['_original'])
    fresh_write(managed, 'receipt.json', encode(receipt))
    for rel in created_dirs:
        if rel != '.':
            child(target, rel).mkdir(exist_ok=True)
    for row in rows:
        if row['action'] != 'keep':
            os.replace(fresh_write(managed, 'place.next', row['_data']), child(target, row['path']))
    receipt['status'] = 'installed'
    os.replace(fresh_write(managed, 'receipt.next', encode(receipt)), managed / 'receipt.json')
    return json.loads(json.dumps(receipt))


def rollback(target):
    target = _target(target)
    managed = child(target, MANAGED)
    try:
        receipt = parse(read_plain(managed, 'receipt.json'), 'receipt.json', 262144)
    except OSError as exc:
        raise ValueError('no installation receipt found; nothing to roll back') from exc
    require(isinstance(receipt, dict) and receipt.get('schema') == 1 and receipt.get('status') in ('intent', 'installed')
            and isinstance(receipt.get('files'), list) and isinstance(receipt.get('created_dirs'), list), 'unsupported receipt')
    _preflight_managed(managed, receipt)
    removable = {MANAGED}
    actions = []
    for index, row in enumerate(receipt['files']):
        require(isinstance(row, dict) and row.get('action') in ('create', 'keep', 'replace') and hash_ok(row.get('sha256')), 'unsupported receipt row')
        dest = child(target, row['path'])
        present = os.path.lexists(dest)
        current = plain_file(target, dest).read_bytes() if present else None
        if row['action'] == 'create':
            require(current is None or sha(current) == row['sha256'], f'{row["path"]} changed since install; inspect before rollback')
            if present:
                removable.add(row['path'])
            actions.append(('remove', dest, None))
        elif row['action'] == 'replace':
            backup = read_plain(managed, f'backup/{index}.bak')
            require(sha(backup) == row['original_sha256'], 'backup drift; inspect before rollback')
            require(current is not None and sha(current) in (row['sha256'], row['original_sha256']),
                    f'{row["path"]} changed since install; inspect before rollback')
            actions.append(('restore', dest, backup))
    dirs = [d for d in receipt['created_dirs'] if d != '.']
    for rel in dirs:
        removable.add(rel)
    for rel in [*dirs, *(['.'] if '.' in receipt['created_dirs'] else [])]:
        where = target if rel == '.' else child(target, rel)
        if not where.exists():
            continue
        for entry in where.iterdir():
            relative = entry.relative_to(target).as_posix()
            require(relative in removable, 'a created directory now holds other files; rollback refuses deletion')
    for kind, dest, backup in actions:
        if kind == 'remove':
            if os.path.lexists(dest):
                dest.unlink()
        else:
            os.replace(fresh_write(managed, 'restore.next', backup), dest)
    shutil.rmtree(managed)  # only our fixed directory, preflighted above
    for rel in sorted(dirs, key=lambda r: r.count('/'), reverse=True):
        where = child(target, rel)
        if where.is_dir():
            where.rmdir()
    if '.' in receipt['created_dirs']:
        target.rmdir()


# ---- command line -------------------------------------------------------------------------------------

def _read_input(path, limit=FILE_LIMIT):
    return catalog.read_file(path, limit)


def _artifacts(record_raw, directory):
    record = catalog.load_record(record_raw)
    result, total = {}, 0
    for entry in catalog.bounded_list(record['Observations'], 5, 16):
        catalog.fields(entry, 'Path Sha256 Kind')
        name = catalog.portable_name(entry['Path'])
        data = catalog.read_file(Path(directory) / name, catalog.ARTIFACT_LIMIT)
        total += len(data)
        require(total <= catalog.ARTIFACT_TOTAL, 'artifact total exceeds limit')
        result[name] = data
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('validate', help='check the pack and list components still pending measurement')
    p.add_argument('--pack', type=Path, default=DEFAULT_PACK)
    p.add_argument('--strict', action='store_true', help='also fail while any component is pending-measurement')
    p = sub.add_parser('generate', help='re-derive the pack; optional inputs add measured or room components')
    p.add_argument('--pack', type=Path, default=DEFAULT_PACK)
    p.add_argument('--rooms-survey', type=Path)
    p.add_argument('--house-classes', type=Path)
    p.add_argument('--measured-record', type=Path)
    p.add_argument('--sources', type=Path, default=ENFORCE_SOURCES)
    p.add_argument('--artifacts', type=Path)
    p.add_argument('--trusted-addon-sha256')
    p = sub.add_parser('install', help='install into <profiles>/HollowCountry with an intent receipt')
    p.add_argument('--pack', type=Path, default=DEFAULT_PACK)
    p.add_argument('--target', type=Path, required=True)
    p.add_argument('--replace', action='store_true', help='allow replacing a different existing file (backed up)')
    p = sub.add_parser('rollback', help='restore the exact prior profile bytes')
    p.add_argument('--target', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'validate':
            report = validate(args.pack)
            for error in report['errors']:
                print('ERROR: ' + scrub(error))
            for row in report['pending']:
                print(f'{PENDING}: {row["id"]}')
                for need in row['needs']:
                    print('  needs: ' + need)
            if report['errors'] or (args.strict and report['pending']):
                sys.exit(1)
            print('pack valid; runtime acceptance pending. Offline validation never proves DayZ behaviour.')
        elif args.command == 'generate':
            measured = None
            if args.measured_record:
                require(args.artifacts and args.trusted_addon_sha256, '--artifacts and --trusted-addon-sha256 are required with --measured-record')
                record = _read_input(args.measured_record, catalog.RECORD_LIMIT)
                sources = {n: catalog.read_file(args.sources / n, catalog.SOURCE_LIMIT) for n in catalog.SOURCE_NAMES}
                measured = {'record': record, 'sources': sources, 'artifacts': _artifacts(record, args.artifacts),
                            'trusted_addon_sha256': args.trusted_addon_sha256}
            require((args.rooms_survey is None) == (args.house_classes is None), '--rooms-survey and --house-classes go together')
            report = generate(args.pack, _read_input(args.rooms_survey) if args.rooms_survey else None,
                              _read_input(args.house_classes) if args.house_classes else None, measured)
            for error in report['errors']:
                print('ERROR: ' + scrub(error))
            for row in report['pending']:
                print(f'{PENDING}: {row["id"]}')
            if report['errors']:
                sys.exit(1)
            print('pack generated; runtime acceptance pending.')
        elif args.command == 'install':
            receipt = install(args.pack, args.target, args.replace)
            print(scrub(f'installed {len(receipt["files"])} file(s) into {args.target}; roll back with the rollback command. '
                        'Runtime acceptance pending.'))
        else:
            rollback(args.target)
            print('rolled back; prior profile bytes restored.')
    except (ValueError, OSError, KeyError, TypeError, RecursionError, OverflowError) as exc:
        parser.exit(1, scrub(exc) + '\n')


if __name__ == '__main__':
    main()
