"""Native cfggameplay.json delta, spawn-gear preset, isolated install and byte-exact rollback.

Generate reads a mission copy's cfggameplay.json and the committed Hollow Country
profile. Only the keys HC owns are changed; the native `version` field, unknown
keys and every unowned value (notably all StaminaData, MovementData and
DrowningData values) stay exactly as found. Install/rollback target an explicitly
chosen stopped, private mission copy, never the Steam installation, and never
edit the server configuration. The server must be started with
`enableCfgGameplayFile = 1` for the native loader to read the file.

Infected leg-zone health is not a cfggameplay key. It is the minimal CfgVehicles
override in mods/HollowCountry/config.cpp (LEG_HITPOINTS below mirrors it).
Offline generation never establishes DayZ behavior; runtime acceptance is pending.
"""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat

INPUTS = ('cfggameplay.json',)
MANAGED = 'hollow-country-gameplay'
GEAR_REL = 'gear/hardscrabble.json'
GEAR_PATH = MANAGED + '/' + GEAR_REL
DELTA_FILES = {'cfggameplay.delta.json', 'cfggameplay.merged.json', GEAR_REL,
               'gameplay-report.json', 'delta-manifest.json'}
RECEIPT_FILES = {'cfggameplay.backup', 'receipt.json', GEAR_REL, 'cfggameplay.next'}
MAX_BYTES = 4 * 1024 * 1024
OPERATOR_REQUIREMENT = ('serverDZ.cfg must contain enableCfgGameplayFile = 1 (operator edit; '
                        'this tool never edits server configuration)')

# Native evidence (DayZ 1.30, scripts-1.30.164289, 3_Game/constants.c lines 961-965).
NATIVE_WETNESS_WEIGHTS = [1.0, 1.0, 1.33, 1.66, 2.0]
# CfgVehicles ZombieBase LeftLeg Health hitpoints (characters_zombies.pbo): vanilla 100.
# RightLeg inherits LeftLeg. Provisional HC value, tuned only after local acceptance.
VANILLA_LEG_HITPOINTS = 100
LEG_HITPOINTS = 50

TEMP_MIN_DELTA = (-3.0, 0.0)  # cold but not harsh: -2..-3 C on minimum
TEMP_MAX_DELTA = (-2.0, 0.0)  # -1..-2 C on maximum
HIT_KEYS = ('hitDirectionOverrideEnabled', 'hitDirectionBehaviour', 'hitDirectionStyle',
            'hitDirectionIndicatorColorStr', 'hitDirectionMaxDuration',
            'hitDirectionBreakPointRelative', 'hitDirectionScatter',
            'hitIndicationPostProcessEnabled')
# Allowlisted leaf paths a delta may set. StaminaData, MovementData and DrowningData
# are deliberately absent: HC's stamina module (HCStaminaConfiguration) is the single
# owner of the 50% drain and 25% faster recovery; the other values stay vanilla.
PROFILE_PATHS = {
    ('PlayerData', 'spawnGearPresetFiles'),
    ('PlayerData', 'WeaponObstructionData', 'staticMode'),
    ('PlayerData', 'WeaponObstructionData', 'dynamicMode'),
    ('WorldsData', 'wetnessWeightModifiers'),
    *(('UIData', 'HitIndicationData', k) for k in HIT_KEYS),
}
TEMP_PATHS = {('WorldsData', 'environmentMinTemps'), ('WorldsData', 'environmentMaxTemps')}
DELTA_PATHS = PROFILE_PATHS | TEMP_PATHS
# Reviewed civilian clothing per slot (all scope 2, retained in the item-review workbook) and the
# only permitted small items. Anything else, including any weapon or ammunition, is refused.
CLOTHING = {
    'Body': ('TShirt_Beige', 'TShirt_Blue', 'TShirt_Green', 'TShirt_Grey', 'TShirt_Black',
             'Hoodie_Black', 'Hoodie_Brown', 'Hoodie_Grey'),
    'Legs': ('Jeans_Black', 'Jeans_Blue', 'Jeans_BlueDark', 'Jeans_Brown', 'Jeans_Grey', 'CargoPants_Black'),
    'Feet': ('AthleticShoes_Black', 'AthleticShoes_Brown', 'AthleticShoes_Grey', 'JoggingShoes_Black',
             'HikingBootsLow_Black'),
}
# Every player spawns with exactly one knife and one bandage: the native loader picks one cargo set and
# spawns every simpleChildrenTypes entry of it, so each set is [knife, bandage, one small item].
# KitchenKnife is the one melee tool allowed; weapons and ammunition stay refused.
KNIFE = 'KitchenKnife'
BANDAGE = 'BandageDressing'
SMALL_ITEMS = ('Rag', 'Chemlight_White', 'Chemlight_Yellow', 'Chemlight_Green',
               'BakedBeansCan', 'SpaghettiCan', 'TunaCan')
# Native DAMAGE_WORN_VALUE is 0.7 (health >= 0.7 reads as pristine), so worn means strictly below it.
WORN_HEALTH = (0.6, 0.69)
CLASS_NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_]{1,63}$')


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def encode_source(value):
    return (json.dumps(value, indent='\t', ensure_ascii=False) + '\n').encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def child(root, name):
    root = Path(root).absolute()
    if name.startswith('/') or '\\' in name or ':' in name or any(p in {'', '.', '..'} for p in name.split('/')):
        raise ValueError('unsafe mission path')
    path = root / name
    for p in (path, *path.parents):
        if p.is_symlink():
            raise ValueError('symlinks forbidden')
    return path


def regular(path):
    """Refuse anything that is not a plain single-link file (hard links can alias files outside the mission)."""
    st = Path(path).lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
        raise ValueError('managed/target file must be a regular file without hard links: ' + Path(path).name)
    return path


def write_fresh(path, data):
    """Create a new file exclusively; an existing staging file is unlinked, never opened for writing."""
    path = Path(path)
    if path.is_symlink() or path.exists():
        if path.is_dir():
            raise ValueError('refusing to replace a directory')
        path.unlink()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o644)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(data)


def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('duplicate JSON key')
        out[key] = value
    return out


def _reject_constant(name):
    raise ValueError('non-finite JSON number')


def parse(data):
    if len(data) > MAX_BYTES:
        raise ValueError('JSON file too large')
    try:
        text = data.decode('utf-8-sig')
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as e:
        raise ValueError('malformed JSON') from e
    if not isinstance(value, dict):
        raise ValueError('JSON root must be an object')
    return value


def snapshot(source):
    return {n: child(source, n).read_bytes() for n in INPUTS}


def _num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _int_in(value, low, high):
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _leaves(value, prefix=()):
    if isinstance(value, dict):
        if not value:
            raise ValueError('empty object in delta: ' + '.'.join(prefix))
        for k, v in value.items():
            yield from _leaves(v, prefix + (k,))
    else:
        yield prefix, value


def _get(value, path):
    for part in path:
        if not isinstance(value, dict) or part not in value:
            raise ValueError('missing ' + '.'.join(path))
        value = value[part]
    return value


def _source_checked(source):
    if not isinstance(source.get('version'), int) or isinstance(source.get('version'), bool):
        raise ValueError('source cfggameplay.json must keep its native integer version')
    for section in ('PlayerData', 'WorldsData', 'UIData'):
        if not isinstance(source.get(section), dict):
            raise ValueError('source cfggameplay.json lacks ' + section)
    for path in TEMP_PATHS:
        values = _get(source, path)
        if not isinstance(values, list) or len(values) != 12 or not all(_num(v) for v in values):
            raise ValueError('source temperatures must be 12 numbers (native loader ignores other sizes)')
    return source


def _validate_values(delta, source):
    paths = {p for p, _ in _leaves(delta)}
    if not paths <= DELTA_PATHS:
        raise ValueError('delta sets keys HC does not own: ' + ', '.join(sorted('.'.join(p) for p in paths - DELTA_PATHS)))
    if paths != DELTA_PATHS:
        # HitIndicationData members absent from the JSON are treated as 0 by the loader.
        raise ValueError('delta must set every owned key; missing: ' + ', '.join(sorted('.'.join(p) for p in DELTA_PATHS - paths)))
    if _get(delta, ('PlayerData', 'spawnGearPresetFiles')) != [GEAR_PATH]:
        raise ValueError('spawnGearPresetFiles must list exactly ' + GEAR_PATH)
    for key in ('staticMode', 'dynamicMode'):  # EWeaponObstructionMode: DISABLED 0, ENABLED 1, ALWAYS 2
        if not _int_in(_get(delta, ('PlayerData', 'WeaponObstructionData', key)), 0, 2):
            raise ValueError('WeaponObstructionData modes are integers 0..2')
    wet = _get(delta, ('WorldsData', 'wetnessWeightModifiers'))
    if (not isinstance(wet, list) or len(wet) != len(NATIVE_WETNESS_WEIGHTS) or not all(_num(v) for v in wet)
            or wet[0] != 1.0 or wet != sorted(wet) or max(wet) > 2.5
            or any(v < n - 1e-9 or v > n * 1.2 + 1e-9 for v, n in zip(wet, NATIVE_WETNESS_WEIGHTS))):
        raise ValueError('wetnessWeightModifiers must be 5 values, dry 1.0, non-decreasing, '
                         'within +0..20% of native, at most 2.5')
    hit = _get(delta, ('UIData', 'HitIndicationData'))
    if not isinstance(hit['hitDirectionOverrideEnabled'], bool) or not isinstance(hit['hitIndicationPostProcessEnabled'], bool):
        raise ValueError('hit indication flags must be booleans')
    if not _int_in(hit['hitDirectionBehaviour'], 0, 2) or not _int_in(hit['hitDirectionStyle'], 0, 2):
        raise ValueError('hit indication behaviour/style must be 0..2')
    colour = hit['hitDirectionIndicatorColorStr']
    if not isinstance(colour, str) or not re.fullmatch(r'0x[0-9a-f]{8}', colour):
        raise ValueError('hit indication colour must be 0xaarrggbb lower-case hex')
    for key, low, high in (('hitDirectionMaxDuration', 0.5, 10), ('hitDirectionBreakPointRelative', 0, 1),
                           ('hitDirectionScatter', 0, 180)):
        if not _num(hit[key]) or not low <= hit[key] <= high:
            raise ValueError(f'{key} must be within {low}..{high}')
    for path, bounds in ((('WorldsData', 'environmentMinTemps'), TEMP_MIN_DELTA),
                         (('WorldsData', 'environmentMaxTemps'), TEMP_MAX_DELTA)):
        new, old = _get(delta, path), _get(source, path)
        if not isinstance(new, list) or len(new) != 12 or not all(_num(v) for v in new):
            raise ValueError('temperatures must be 12 numbers')
        if any(not bounds[0] - 1e-9 <= n - o <= bounds[1] + 1e-9 for n, o in zip(new, old)):
            raise ValueError(f'{path[1]} must stay within {bounds[0]}..{bounds[1]} C of the source')
    if any(lo >= hi for lo, hi in zip(_get(delta, ('WorldsData', 'environmentMinTemps')),
                                      _get(delta, ('WorldsData', 'environmentMaxTemps')))):
        raise ValueError('every month needs minimum < maximum')


def _validate_profile(profile):
    if (not isinstance(profile, dict) or set(profile) != {'schema', 'name', 'temperature', 'cfggameplay'}
            or profile['schema'] != 1 or not isinstance(profile['name'], str)
            or not isinstance(profile['temperature'], dict)
            or set(profile['temperature']) != {'min_delta', 'max_delta'}
            or not isinstance(profile['cfggameplay'], dict)):
        raise ValueError('unsupported gameplay profile')
    for key, bounds in (('min_delta', TEMP_MIN_DELTA), ('max_delta', TEMP_MAX_DELTA)):
        values = profile['temperature'][key]
        if (not isinstance(values, list) or len(values) != 12 or not all(_num(v) for v in values)
                or any(not bounds[0] <= v <= bounds[1] for v in values)):
            raise ValueError(f'{key} must be 12 numbers within {bounds[0]}..{bounds[1]}')
    paths = {p for p, _ in _leaves(profile['cfggameplay'])}
    if not paths <= PROFILE_PATHS:
        raise ValueError('profile sets keys HC does not own: ' + ', '.join(sorted('.'.join(p) for p in paths - PROFILE_PATHS)))


def validate_preset(preset):
    """Schema of PlayerSpawnPreset (CfgPlayerSpawnDataJson.c), plus the Hardscrabble rules."""
    if (not isinstance(preset, dict) or set(preset) != {'spawnWeight', 'name', 'characterTypes',
                                                         'attachmentSlotItemSets', 'discreteUnsortedItemSets'}
            or not _int_in(preset['spawnWeight'], 1, 1000) or not isinstance(preset['name'], str)
            or preset['characterTypes'] != []):
        raise ValueError('unsupported spawn preset')
    slots = preset['attachmentSlotItemSets']
    if not isinstance(slots, list) or [s.get('slotName') if isinstance(s, dict) else None for s in slots] != ['Body', 'Legs', 'Feet']:
        raise ValueError('preset must define exactly Body, Legs and Feet')
    for slot in slots:
        if set(slot) != {'slotName', 'discreteItemSets'} or not isinstance(slot['discreteItemSets'], list) \
                or len(slot['discreteItemSets']) < 4:
            raise ValueError('each clothing slot needs several randomised options')
        names = []
        for item in slot['discreteItemSets']:
            if (not isinstance(item, dict)
                    or set(item) != {'itemType', 'spawnWeight', 'attributes', 'quickBarSlot',
                                     'complexChildrenTypes', 'simpleChildrenTypes',
                                     'simpleChildrenUseDefaultAttributes'}
                    or not isinstance(item['itemType'], str) or not CLASS_NAME.match(item['itemType'])
                    or not _int_in(item['spawnWeight'], 1, 1000) or item['quickBarSlot'] != -1
                    or item['complexChildrenTypes'] != [] or item['simpleChildrenTypes'] != []
                    or not isinstance(item['simpleChildrenUseDefaultAttributes'], bool)):
                raise ValueError('invalid clothing entry')
            a = item['attributes']
            if (not isinstance(a, dict) or set(a) != {'healthMin', 'healthMax', 'quantityMin', 'quantityMax'}
                    or not all(_num(v) for v in a.values())
                    or not WORN_HEALTH[0] <= a['healthMin'] < a['healthMax'] <= WORN_HEALTH[1]
                    or a['quantityMin'] != 0 or a['quantityMax'] != 0):
                raise ValueError('clothing must be worn (health 0.6..0.69, below native 0.7) with no quantity')
            if item['itemType'] not in CLOTHING[slot['slotName']]:
                raise ValueError('clothing class is not on the reviewed list for ' + slot['slotName'])
            names.append(item['itemType'])
        if len(names) != len(set(names)):
            raise ValueError('duplicate clothing class in a slot')
    cargo = preset['discreteUnsortedItemSets']
    if not isinstance(cargo, list) or not cargo:
        raise ValueError('preset needs the small item sets')
    for item in cargo:
        if (not isinstance(item, dict)
                or set(item) != {'name', 'spawnWeight', 'simpleChildrenTypes',
                                 'simpleChildrenUseDefaultAttributes'}
                or not _int_in(item['spawnWeight'], 1, 1000)
                or item['simpleChildrenUseDefaultAttributes'] is not True):
            raise ValueError('each kit set must use default attributes and a plain weight')
        children = item['simpleChildrenTypes']
        if (not isinstance(children, list) or len(children) != 3 or children[:2] != [KNIFE, BANDAGE]
                or not isinstance(children[2], str) or children[2] not in SMALL_ITEMS):
            raise ValueError(f'each kit set must hold exactly {KNIFE}, {BANDAGE} and one small item')


def _merge(base, delta):
    out = {}
    for key, value in base.items():
        if key in delta:
            out[key] = _merge(value, delta[key]) if isinstance(value, dict) and isinstance(delta[key], dict) else copy.deepcopy(delta[key])
        else:
            out[key] = copy.deepcopy(value)
    for key, value in delta.items():
        if key not in base:
            out[key] = copy.deepcopy(value)
    return out


def _nest(path, value, into):
    for part in path[:-1]:
        into = into.setdefault(part, {})
    into[path[-1]] = value


def _build_delta(source, profile):
    delta = copy.deepcopy(profile['cfggameplay'])
    for key, path in (('min_delta', ('WorldsData', 'environmentMinTemps')),
                      ('max_delta', ('WorldsData', 'environmentMaxTemps'))):
        base = _get(source, path)
        _nest(path, [round(b + d, 6) for b, d in zip(base, profile['temperature'][key])], delta)
    return delta


def _merged(source, delta):
    _validate_values(delta, source)
    return _merge(source, delta)


def generate(source, profile, preset):
    _validate_profile(profile)
    validate_preset(preset)
    data = snapshot(source)
    original = _source_checked(parse(data['cfggameplay.json']))
    delta = _build_delta(original, profile)
    merged = _merged(original, delta)
    files = {
        'cfggameplay.delta.json': encode(delta),
        'cfggameplay.merged.json': encode_source(merged),
        GEAR_REL: encode(preset),
        'gameplay-report.json': encode({
            'schema': 1, 'profile': profile['name'], 'owned_paths': sorted('.'.join(p) for p in DELTA_PATHS),
            'untouched': ['StaminaData', 'MovementData', 'DrowningData', 'version', 'unknown keys',
                          'CE globals (zombie/animal caps)'],
            'infected_leg_hitpoints': {'vanilla': VANILLA_LEG_HITPOINTS, 'hollow_country': LEG_HITPOINTS,
                                       'location': 'mods/HollowCountry/config.cpp CfgVehicles ZombieBase LeftLeg'},
            'operator_requirement': OPERATOR_REQUIREMENT, 'runtime_acceptance': 'pending'}),
    }
    files['delta-manifest.json'] = encode({
        'schema': 1, 'profile': profile['name'], 'runtime_acceptance': 'pending',
        'sources': {n: sha(d) for n, d in data.items()},
        'files': {n: sha(d) for n, d in files.items()}})
    return files


def write_delta(stage, files):
    stage = Path(stage)
    if set(files) != DELTA_FILES:
        raise ValueError('unexpected generated file set')
    if stage.exists() or stage.is_symlink():
        raise ValueError('output must be a fresh directory')
    for name in files:  # preflight before any writes
        child(stage, name)
    stage.mkdir(parents=True)
    for name, data in files.items():
        p = child(stage, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        write_fresh(p, data)


def _target(target):
    target = Path(target).absolute()
    child(target, 'cfggameplay.json')
    if not target.is_dir() or 'steamapps' in (s.lower() for s in target.parts):
        raise ValueError('install requires an isolated existing mission copy outside Steam')
    return target


def _load_delta(stage):
    stage = Path(stage)
    found = set()
    if not stage.is_dir():
        raise ValueError('delta stage is not a directory')
    for p in stage.rglob('*'):
        child(stage, p.relative_to(stage).as_posix())
        if p.is_file():
            found.add(p.relative_to(stage).as_posix())
        elif not p.is_dir():
            raise ValueError('special stage file')
    if found != DELTA_FILES:
        raise ValueError('unexpected or missing stage files')
    files = {n: child(stage, n).read_bytes() for n in found}
    manifest = parse(files['delta-manifest.json'])
    if (manifest.get('schema') != 1 or not isinstance(manifest.get('sources'), dict)
            or set(manifest['sources']) != set(INPUTS) or not isinstance(manifest.get('files'), dict)
            or set(manifest['files']) != DELTA_FILES - {'delta-manifest.json'}):
        raise ValueError('invalid delta manifest')
    if any(sha(files[n]) != h for n, h in manifest['files'].items()):
        raise ValueError('delta checksum mismatch')
    return files, manifest


def install(stage, target, dry_run=False):
    target = _target(target)
    files, manifest = _load_delta(stage)
    data = snapshot(target)
    if {n: sha(d) for n, d in data.items()} != manifest['sources']:
        raise ValueError('target source hashes differ; regenerate/reconcile')
    managed = child(target, MANAGED)
    if managed.exists() or managed.is_symlink():
        raise ValueError('already installed or interrupted installation; inspect/rollback first')
    gear_target = child(target, GEAR_PATH)
    regular(child(target, 'cfggameplay.json'))
    original = data['cfggameplay.json']
    source = _source_checked(parse(original))
    # Re-validate the stage content itself: checksums only prove it was not edited
    # after generation, not that it respects HC's ownership and bounds.
    delta = parse(files['cfggameplay.delta.json'])
    merged = encode_source(_merged(source, delta))
    if merged != files['cfggameplay.merged.json']:
        raise ValueError('merged file does not equal the delta applied to the target source')
    validate_preset(parse(files[GEAR_REL]))
    plan = {'dry_run': dry_run, 'would_replace': ['cfggameplay.json'], 'would_create': [GEAR_PATH,
            MANAGED + '/receipt.json', MANAGED + '/cfggameplay.backup'],
            'operator_requirement': OPERATOR_REQUIREMENT, 'runtime_acceptance': 'pending'}
    if dry_run:
        return plan
    receipt = {'schema': 1, 'before': sha(original), 'after': sha(merged), 'gear_sha256': sha(files[GEAR_REL]),
               'sources': manifest['sources'], 'runtime_acceptance': 'pending'}
    managed.mkdir()
    # Backup and receipt exist before the atomic switch. Rollback also handles an
    # interrupted install whose switch did not happen. Stop the server first.
    write_fresh(managed / 'cfggameplay.backup', original)
    write_fresh(managed / 'receipt.json', encode(receipt))
    gear_target.parent.mkdir()
    write_fresh(gear_target, files[GEAR_REL])
    write_fresh(managed / 'cfggameplay.next', merged)
    os.replace(managed / 'cfggameplay.next', child(target, 'cfggameplay.json'))
    return receipt


def rollback(target, dry_run=False):
    target = _target(target)
    managed = child(target, MANAGED)
    if not managed.is_dir() or not (managed / 'receipt.json').is_file():
        raise ValueError('no gameplay installation receipt; nothing to roll back')
    receipt = parse(child(managed, 'receipt.json').read_bytes())
    if set(receipt) != {'schema', 'before', 'after', 'gear_sha256', 'sources', 'runtime_acceptance'} or receipt['schema'] != 1:
        raise ValueError('invalid receipt')
    for p in managed.rglob('*'):
        name = p.relative_to(managed).as_posix()
        child(managed, name)
        if p.is_file() and name not in RECEIPT_FILES:
            raise ValueError('unexpected managed file; rollback refuses deletion')
        if not p.is_dir():
            regular(p)
    config = regular(child(target, 'cfggameplay.json'))
    backup = child(managed, 'cfggameplay.backup').read_bytes()
    if sha(backup) != receipt['before'] or sha(config.read_bytes()) not in {receipt['before'], receipt['after']}:
        raise ValueError('cfggameplay.json drift; manual reconciliation required')
    gear = child(managed, GEAR_REL)
    if not gear.is_file() or sha(gear.read_bytes()) != receipt['gear_sha256']:
        raise ValueError('installed spawn preset drift; inspect before rollback')
    if dry_run:
        return {'dry_run': True, 'would_restore': ['cfggameplay.json'], 'would_remove': [MANAGED + '/'],
                'runtime_acceptance': 'pending'}
    write_fresh(managed / 'cfggameplay.next', backup)
    os.replace(managed / 'cfggameplay.next', config)
    shutil.rmtree(managed)  # only our fixed directory, preflighted above
    return {'dry_run': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('generate')
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--profile', type=Path, required=True)
    p.add_argument('--preset', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('install')
    p.add_argument('--delta', type=Path, required=True)
    p.add_argument('--target', type=Path, required=True)
    p.add_argument('--dry-run', action='store_true')
    p = sub.add_parser('rollback')
    p.add_argument('--target', type=Path, required=True)
    p.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'generate':
            write_delta(args.out, generate(args.source, parse(args.profile.read_bytes()),
                                           parse(args.preset.read_bytes())))
        elif args.command == 'install':
            result = install(args.delta, args.target, args.dry_run)
            if args.dry_run:
                print(json.dumps(result, indent=2))
        else:
            result = rollback(args.target, args.dry_run)
            if args.dry_run:
                print(json.dumps(result, indent=2))
        print('Offline operation complete; DayZ runtime acceptance pending. ' + OPERATOR_REQUIREMENT + '.')
    except (ValueError, OSError, KeyError, TypeError) as e:
        parser.exit(1, f'{e}\n')


if __name__ == '__main__':
    main()
