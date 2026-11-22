"""Ship the authored V2 travel CE overlay into a stopped private mission copy.

CE runs before HCSettings is loaded: EnableTravel is evaluated at install time.
Air positions merge by event name with byte-preserving rollback.
No script controller, runtime gate override, or save wipe.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.package import economy

MANAGED = 'hollow-country-travel'
INPUTS = ('cfgeconomycore.xml', 'cfgeventspawns.xml')
EXPANSION_ROSTER = 'vehicles/vehexp-roster.json'
EXPANSION_POSITIONS = 'vehicles/vehexp-eventspawns.xml'
AIR_EVENT = 'VehicleHCExpansionAir'
CE_FILES = ('ce/types.xml', 'ce/events.xml', 'ce/travel-spawnabletypes.xml')
REGISTRATION = 'cfgeconomycore.append.xml'
SOURCE = Path(__file__).resolve().parents[2] / 'mission/hollow-country'

# HC-32: curated identities verified against installed 1.30.164289 vehicle
# config.bin and Chernarus db/events.xml/cfgspawnabletypes.xml. This is a source
# disposition, never a live CE census. Trucks deliberately retain stock policy.
NATIVE_FAMILIES = {
    'VehicleCivilianSedan': ('CivilianSedan', 'CivilianSedan_Black', 'CivilianSedan_Wine'),
    'VehicleHatchback02': ('Hatchback_02', 'Hatchback_02_Black', 'Hatchback_02_Blue'),
    'VehicleOffroadHatchback': ('OffroadHatchback', 'OffroadHatchback_Blue', 'OffroadHatchback_White'),
    'VehicleSedan02': ('Sedan_02', 'Sedan_02_Grey', 'Sedan_02_Red'),
    'VehicleOffroad02': ('Offroad_02', 'Offroad_02_Beige'),
    'VehicleMotorbike': ('Motorbike_01_Blue', 'Motorbike_01_Red', 'Motorbike_01_Yellow',
                         'Motorbike_02_Blue', 'Motorbike_02_Red', 'Motorbike_02_Green', 'Motorbike_02_Yellow'),
    'VehicleBoat': ('Boat_01_Black', 'Boat_01_Blue', 'Boat_01_Camo', 'Boat_01_Orange'),
    'VehicleTruck01': ('Truck_01_Covered', 'Truck_01_Covered_Blue', 'Truck_01_Covered_Orange'),
}
VEHICLE_CLASSES = {n.casefold() for names in NATIVE_FAMILIES.values() for n in names}
CANONICAL_VEHICLES = {n.casefold(): n for names in NATIVE_FAMILIES.values() for n in names}


def repair_parts(vehicle):
    """Reviewed attachment identities/multiplicities, not invented slot names.

    Ruined wheels inherit the matching native wheel slots. GlowPlug declares a
    scalar inventorySlot in vehicles_parts/config.bin (not an array). These
    checks preserve the authored probabilities; they add no repair supplies.
    """
    vehicle = CANONICAL_VEHICLES.get(vehicle.casefold(), '')
    if not vehicle:
        return None
    for base, wheel, panels in (
            ('CivilianSedan', 'CivSedanWheel', ('CivSedanDoors_Driver', 'CivSedanDoors_CoDriver',
              'CivSedanDoors_BackLeft', 'CivSedanDoors_BackRight', 'CivSedanHood', 'CivSedanTrunk')),
            ('Hatchback_02', 'Hatchback_02_Wheel', ('Hatchback_02_Door_1_1', 'Hatchback_02_Door_1_2',
              'Hatchback_02_Door_2_1', 'Hatchback_02_Door_2_2', 'Hatchback_02_Hood', 'Hatchback_02_Trunk')),
            ('OffroadHatchback', 'HatchbackWheel', ('HatchbackDoors_Driver', 'HatchbackDoors_CoDriver',
              'HatchbackHood', 'HatchbackTrunk')),
            ('Sedan_02', 'Sedan_02_Wheel', ('Sedan_02_Door_1_1', 'Sedan_02_Door_1_2',
              'Sedan_02_Door_2_1', 'Sedan_02_Door_2_2', 'Sedan_02_Hood', 'Sedan_02_Trunk')),
            ('Offroad_02', 'Offroad_02_Wheel', ('Offroad_02_Trunk', 'Offroad_02_Hood',
              'Offroad_02_Door_1_1', 'Offroad_02_Door_1_2', 'Offroad_02_Door_2_1', 'Offroad_02_Door_2_2'))):
        if vehicle == base or vehicle.startswith(base + '_'):
            suffix = vehicle[len(base):]
            result = Counter({wheel: 5, wheel + '_Ruined': 5, 'CarBattery': 1, 'HeadlightH7': 2})
            result.update({p + suffix: 1 for p in panels})
            result.update({'GlowPlug': 1} if base == 'Offroad_02' else {'CarRadiator': 1, 'SparkPlug': 1})
            return result
    if vehicle.startswith('Motorbike_'):
        base, colour = vehicle.rsplit('_', 1)
        result = Counter({'SparkPlug': 1, base + '_Wheel_1': 1, base + '_Wheel_2': 1})
        if base == 'Motorbike_02':
            result.update({base + '_Shield' + panel + '_' + colour: 1 for panel in ('Front', 'Left', 'Right')})
        return result
    if vehicle.startswith('Boat_01_'):
        return Counter({'SparkPlug': 1})
    return None


def validate_repairs(spawnable):
    for template in spawnable.findall('type'):
        expected = repair_parts(template.get('name', ''))
        if expected is None:
            continue
        actual = Counter(n.get('name', '').casefold() for n in template.findall('attachments/item'))
        allowed = {n.casefold(): count for n, count in expected.items()}
        for name, count in actual.items():
            if name not in allowed or count > allowed[name]:
                kind = 'wheel' if 'wheel' in name else 'part'
                raise ValueError('HC-32 incompatible ' + kind + ' for ' + template.get('name'))


def vehicle_owners(events):
    """Class ownership must be unique even when event names differ in spelling."""
    owners = {}
    for event in events:
        for child in event.findall('children/child'):
            name = child.get('type', '').casefold()
            if not name or name in owners:
                raise ValueError('HC-32 vehicle has duplicate or missing event owner: ' + name)
            owners[name] = event.get('name')
    return owners


def validate_vehicle_budgets(types, vehicles):
    for row in types:
        if row.get('name', '').casefold() in vehicles | VEHICLE_CLASSES:
            if any(int(row.findtext(tag, '0')) != 0 for tag in ('nominal', 'min')):
                raise ValueError('HC-32 vehicle has a loose-loot budget: ' + row.get('name'))


def roster(source=SOURCE):
    """Exact authored roster receipt; native spawn/repair/persistence stay pending."""
    files = validate(source)
    events = economy.xml(files['ce/events.xml'], 'events')
    templates = economy.xml(files['ce/travel-spawnabletypes.xml'], 'spawnabletypes')
    return _roster(events, templates, source)


def expansion_repairs(vehicle):
    """Authored repair subset of installed Expansion CfgVehicles attachment slots.

    config.bin has no source lines. Evidence: 2291785437 vehicles_ground_landrover,
    vehicles_ground_uaz, vehicles_air_gyro, vehicles_air_hatchbird,
    vehicles_water_zodiac; 2116157322 vehicles_ground_bus, vehicles_ground_tractor,
    vehicles_air_mh6, vehicles_air_uh1h, vehicles_air_merlin, vehicles_water_utility.
    Four road/rotor wheels are authored, without spare/dummy Niva wheel slots.
    These are source policy multiplicities, never a claim about live attachments.
    """
    road = Counter({'CarBattery': 1, 'CarRadiator': 1, 'SparkPlug': 1})
    air = Counter({'ExpansionHelicopterBattery': 1, 'ExpansionIgniterPlug': 1,
                   'ExpansionHydraulicHoses': 1})
    if vehicle.startswith('Expansion_Landrover'):
        road.update({'Expansion_Landrover_Wheel': 4})
        road.update({'Expansion_Landrover_' + panel: 1 for panel in
                     ('Driverdoor', 'Codriverdoor', 'Left', 'Right', 'Trunk', 'Hood')})
        return road
    if vehicle.startswith('ExpansionUAZ'):
        road.update({'ExpansionUAZWheel': 4})
        panels = ['Driver', 'CoDriver', 'Hood']
        if vehicle != 'ExpansionUAZCargo':
            panels += ['Cargo1', 'Cargo2']
        road.update({'ExpansionUAZDoor' + panel: 1 for panel in panels})
        return road
    if vehicle.startswith('ExpansionBus'):
        return Counter({'ExpansionBusWheel': 2, 'ExpansionBusWheelDouble': 2,
                        'TruckBattery': 1, 'CarRadiator': 1, 'GlowPlug': 1})
    if vehicle.startswith('ExpansionTractor'):
        return Counter({'ExpansionTractorFrontWheel': 2, 'ExpansionTractorBackWheel': 2,
                        'CarBattery': 1, 'SparkPlug': 1, 'ExpansionTractorDoorsDriver': 1,
                        'ExpansionTractorDoorsCodriver': 1})
    if vehicle == 'ExpansionZodiacBoat' or vehicle.startswith('ExpansionUtilityBoat'):
        return Counter({'TruckBattery': 1, 'GlowPlug': 1})
    if vehicle in ('ExpansionGyrocopter', 'ExpansionBigGyrocopter'):
        return Counter({'ExpansionHelicopterBattery': 1, 'SparkPlug': 1})
    if vehicle == 'ExpansionHatchBird':
        air.update({'HatchbackWheel': 4})
        air.update({'ExpansionHatchBird' + panel: 1 for panel in
                    ('Doors_Driver', 'Doors_CoDriver', 'Hood', 'Trunk')})
        return air
    if vehicle in ('ExpansionMh6', 'ExpansionUh1h'):
        prefix = 'Expansion_Mh6_Door_' if vehicle == 'ExpansionMh6' else 'ExpansionUh1hDoor_'
        air.update({prefix + panel: 1 for panel in ('1_1', '1_2', '2_1', '2_2')})
        return air
    if vehicle == 'ExpansionMerlin':
        air.update({'ExpansionMerlinFrontWheel': 2, 'ExpansionMerlinBackWheel': 2})
        return air
    raise ValueError('HC-32 unreviewed Expansion repair template: ' + vehicle)


def _families(source):
    manifest = json.loads(economy.read_plain(source, EXPANSION_ROSTER))
    if not isinstance(manifest, dict):
        raise ValueError('HC-32 invalid Expansion manifest')
    additions = manifest.get('families')
    if not isinstance(additions, dict) or set(additions) != {
            'VehicleOffroadHatchback', 'VehicleTruck01', 'VehicleBoat', AIR_EVENT}:
        raise ValueError('HC-32 unreviewed Expansion families')
    families = {key: set(names) for key, names in NATIVE_FAMILIES.items()}
    for key, names in additions.items():
        if (not isinstance(names, list) or not names
                or any(not isinstance(name, str) or not name for name in names)
                or len({name.casefold() for name in names}) != len(names)):
            raise ValueError('HC-32 invalid Expansion family: ' + key)
        families.setdefault(key, set()).update(names)
    identities = [name.casefold() for names in families.values() for name in names]
    if len(identities) != len(set(identities)):
        raise ValueError('HC-32 vehicle has duplicate manifest owners')
    return families


def _roster(events, templates, source=SOURCE):
    families = _families(source)
    owners = vehicle_owners(events)
    expected = {n.casefold() for names in families.values() for n in names}
    if set(owners) != expected:
        raise ValueError('HC-32 incomplete travel roster')
    if {event.get('name') for event in events} != set(families):
        raise ValueError('HC-32 travel roster has an unreviewed or missing event')
    for event in events:
        family = families[event.get('name')]
        if {n.get('type') for n in event.findall('children/child')} != family:
            raise ValueError('HC-32 vehicle family mismatch')
    rows = {n.get('name', '').casefold(): n for n in templates.findall('type')}
    if len(rows) != len(templates):
        raise ValueError('HC-32 duplicate repair template')
    stock = {n.casefold() for n in NATIVE_FAMILIES['VehicleTruck01']}
    if set(rows) & stock:
        raise ValueError('HC-32 truck repair must remain native-stock')
    for name in expected - stock:
        if name not in rows:
            raise ValueError('HC-32 missing repair template: ' + name)
        canonical = rows[name].get('name')
        wanted = repair_parts(canonical)
        if wanted is None:
            wanted = expansion_repairs(canonical)
        actual = Counter(n.get('name', '').casefold() for n in rows[name].findall('attachments/item'))
        if actual != Counter({n.casefold(): count for n, count in wanted.items()}):
            raise ValueError('HC-32 incomplete repair parts: ' + name)
    return {'vehicle_families': len(families), 'authored_variants': len(expected - stock),
            'runtime': 'PENDING', 'families': {key: {
                'disposition': 'hc-override', 'variants': sorted(names),
                'repair': 'native-stock-trucks-and-authored-attachments' if key == 'VehicleTruck01'
                          else 'authored-attachments'
            } for key, names in families.items()}}


def preference(profiles):
    path = Path(profiles) / 'HollowCountry/settings.json'
    if not os.path.lexists(path):
        return True
    settings = json.loads(economy.read_plain(path.parent, path.name))
    if not isinstance(settings, dict) or settings.get('SchemaVersion') != 1:
        raise ValueError('invalid HCSettings; travel install refuses')
    enabled = settings.get('EnableTravel', True)
    if type(enabled) is not bool:
        raise ValueError('EnableTravel must be boolean')
    return enabled


def validate(source=SOURCE):
    files = {name: economy.read_plain(source, name) for name in (*CE_FILES, REGISTRATION)}
    roots = [economy.xml(files[name], tag) for name, tag in zip(
        CE_FILES, ('types', 'events', 'spawnabletypes'))]
    for root in roots:
        economy._unique(root)
        if len({n.get('name', '').casefold() for n in root}) != len(root):
            raise ValueError('HC-32 duplicate CE row (case alias)')
    events = roots[1]
    expected = {'VehicleCivilianSedan': 9, 'VehicleHatchback02': 9, 'VehicleOffroadHatchback': 9,
                'VehicleSedan02': 9, 'VehicleOffroad02': 3, 'VehicleMotorbike': 28, 'VehicleBoat': 6,
                'VehicleTruck01': 7, AIR_EVENT: 4}
    if {e.get('name'): int(e.findtext('nominal')) for e in events} != expected:
        raise ValueError('travel event counts differ from reviewed SA-07 policy')
    for event in events:
        low, nominal, high = (int(event.findtext(n)) for n in ('min', 'nominal', 'max'))
        if not 0 <= low <= nominal <= high:
            raise ValueError('invalid travel event bounds')
    for item in roots[0]:
        economy._validate_budget(item)
    validate_repairs(roots[2])
    validate_vehicle_budgets(roots[0], set(vehicle_owners(events)))
    # Childless documents cannot spawn vehicles (legacy synthetic composition
    # ports use these). Every populated vehicle overlay must be complete before
    # any installer writes it, not merely when the report command is requested.
    if events.findall('event/children/child'):
        _roster(events, roots[2], source)
    files[EXPANSION_POSITIONS] = economy.read_plain(source, EXPANSION_POSITIONS)
    positions = economy.xml(files[EXPANSION_POSITIONS], 'eventposdef')
    if len(positions) != 1 or positions[0].tag != 'event' or positions[0].get('name') != AIR_EVENT:
        raise ValueError('HC-32 unsupported Expansion event positions')
    fragment = economy.xml(files[REGISTRATION], 'economycore')
    if (len(fragment) != 1 or fragment[0].tag != 'ce'
            or fragment[0].attrib != {'folder': MANAGED + '/ce'}
            or [f.attrib for f in fragment[0]] != [
                {'name': name.split('/')[-1], 'type': kind}
                for name, kind in zip(CE_FILES, ('types', 'events', 'spawnabletypes'))]):
        raise ValueError('unsupported travel CE registration')
    return files


def _definition(node):
    return (node.tag, sorted(node.attrib.items()), (node.text or '').strip(),
            tuple(_definition(child) for child in node))


def _merge_positions(original, authored):
    root = economy.xml(original, 'eventposdef')
    addition = economy.xml(authored, 'eventposdef')[0]
    existing = [event for event in root if event.get('name', '').casefold() == AIR_EVENT.casefold()]
    if existing:
        if len(existing) != 1 or _definition(existing[0]) != _definition(addition):
            raise ValueError('conflicting ' + AIR_EVENT + ' event positions')
        return original
    opened = re.sub(rb'<eventposdef\s*/>', b'<eventposdef></eventposdef>', original)
    endings = list(re.finditer(rb'</eventposdef\s*>', opened))
    if len(endings) != 1:
        raise ValueError('ambiguous eventposdef closing tag')
    offset = endings[0].start()
    patched = opened[:offset] + b'\n' + ET.tostring(addition) + b'\n' + opened[offset:]
    economy.xml(patched, 'eventposdef')
    return patched


def _receipt(managed):
    receipt = json.loads(economy.read_plain(managed, 'receipt.json'))
    keys = {'before', 'after', *CE_FILES}
    if isinstance(receipt, dict) and receipt.get('schema') == 2:
        keys.update(('positions_before', 'positions_after'))
    if (not isinstance(receipt, dict) or type(receipt.get('schema')) is not int
            or receipt['schema'] not in (1, 2) or set(receipt) != {'schema', *keys}
            or any(not isinstance(receipt[k], str) or not economy.HEX64.fullmatch(receipt[k])
                   for k in keys)):
        raise ValueError('invalid travel receipt')
    economy.preflight_managed(managed, {*CE_FILES, 'receipt.json', 'core.backup', 'core.next',
                                        'positions.backup'})
    return receipt


def _already_installed(managed, target, files):
    receipt = _receipt(managed)
    if receipt['schema'] != 2:
        raise ValueError('legacy travel install; rollback before installing expanded roster')
    for name in CE_FILES:
        if economy.sha(files[name]) != receipt[name] or economy.sha(economy.read_plain(managed, name)) != receipt[name]:
            raise ValueError('travel source or installed CE drift: ' + name)
    for name, key in (('cfgeconomycore.xml', 'after'), ('cfgeventspawns.xml', 'positions_after')):
        if economy.sha(economy.read_plain(target, name)) != receipt[key]:
            raise ValueError('travel already installed or interrupted; inspect/rollback first')
    for name, key in (('core.backup', 'before'), ('positions.backup', 'positions_before')):
        if economy.sha(economy.read_plain(managed, name)) != receipt[key]:
            raise ValueError('travel backup drift: ' + name)
    current = economy.read_plain(target, 'cfgeventspawns.xml')
    if _merge_positions(current, files[EXPANSION_POSITIONS]) != current:
        raise ValueError('travel source positions drift')
    return True


def install(source, target, enabled=True):
    if type(enabled) is not bool:
        raise ValueError('EnableTravel must be boolean')
    if not enabled:
        return False
    target = economy._target(target)
    managed = economy.child(target, MANAGED)
    files = validate(source)
    if os.path.lexists(managed):
        return _already_installed(managed, target, files)
    positions_before = economy.read_plain(target, 'cfgeventspawns.xml')
    positions_after = _merge_positions(positions_before, files[EXPANSION_POSITIONS])
    original = economy.read_plain(target, 'cfgeconomycore.xml')
    core = economy.xml(original, 'economycore')
    if any(ce.get('folder', '').lower().rstrip('/') == MANAGED + '/ce' for ce in core.findall('ce')):
        raise ValueError('travel CE already registered')
    # Preserve every existing byte, including unrelated CE declarations and comments.
    endings = list(re.finditer(rb'</economycore\s*>', original))
    if not endings:
        # Handle the valid empty synthetic/operator core form too.
        original_open = re.sub(rb'<economycore\s*/>', b'<economycore></economycore>', original)
    else:
        original_open = original
    endings = list(re.finditer(rb'</economycore\s*>', original_open))
    if len(endings) != 1:
        raise ValueError('ambiguous economycore closing tag')
    registration = economy.xml(files[REGISTRATION], 'economycore')[0]
    offset = endings[0].start()
    patched = original_open[:offset] + b'\n' + ET.tostring(registration) + b'\n' + original_open[offset:]
    economy.xml(patched, 'economycore')
    # Refuse two custom owners of the same event or class. Stock rows are the overrides' baseline.
    kinds = {'types': ('ce/types.xml', 'types'), 'events': ('ce/events.xml', 'events'),
             'spawnabletypes': ('ce/travel-spawnabletypes.xml', 'spawnabletypes')}
    new_events = economy.xml(files['ce/events.xml'], 'events')
    new_vehicles = set(vehicle_owners(new_events))
    stock_events = target / 'db/events.xml'
    if stock_events.exists():
        overridden = {e.get('name', '').casefold() for e in new_events}
        for event in economy.xml(economy.read_plain(target, 'db/events.xml'), 'events'):
            if (event.get('name', '').casefold() not in overridden
                    and new_vehicles & {n.get('type', '').casefold() for n in event.findall('children/child')}):
                raise ValueError('HC-32 vehicle has another stock event owner')
    for ce in core.findall('ce'):
        for file in ce.findall('file'):
            if file.get('type') in kinds:
                filename, tag = kinds[file.get('type')]
                names = {n.get('name').lower() for n in economy.xml(files[filename], tag)}
                path = ce.get('folder', '') + '/' + file.get('name', '')
                existing = economy.xml(economy.read_plain(target, path), tag)
                if names & {n.get('name', '').lower() for n in existing}:
                    raise ValueError('travel class/event has another CE owner; reconcile first')
                if tag == 'events' and new_vehicles & {
                        n.get('type', '').casefold() for n in existing.findall('event/children/child')}:
                    raise ValueError('HC-32 vehicle has another event owner')
                if tag == 'types':
                    validate_vehicle_budgets(existing, new_vehicles)
    receipt = {'schema': 2, 'before': economy.sha(original), 'after': economy.sha(patched),
               'positions_before': economy.sha(positions_before),
               'positions_after': economy.sha(positions_after),
               **{name: economy.sha(files[name]) for name in CE_FILES}}
    managed.mkdir()
    economy.fresh_write(managed, 'core.backup', original)
    economy.fresh_write(managed, 'positions.backup', positions_before)
    economy.fresh_write(managed, 'receipt.json', economy.encode(receipt))
    (managed / 'ce').mkdir()
    for name in CE_FILES:
        economy.fresh_write(managed, name, files[name])
    economy.restore_core(managed, target / 'cfgeventspawns.xml', positions_after)
    economy.restore_core(managed, target / 'cfgeconomycore.xml', patched)
    return True


def rollback(target):
    target = economy._target(target)
    managed = economy.child(target, MANAGED)
    if not managed.is_dir():
        raise ValueError('nothing to roll back')
    receipt = _receipt(managed)
    current = economy.read_plain(target, 'cfgeconomycore.xml')
    if economy.sha(current) not in (receipt['before'], receipt['after']):
        raise ValueError('core drift; roll back later CE installers first')
    restore = economy.needs_restore(managed, receipt, economy.sha(current),
                                    [(n, n, 'travel CE drift: ' + n) for n in CE_FILES])
    backup = economy.read_plain(managed, 'core.backup')
    if economy.sha(backup) != receipt['before']:
        raise ValueError('travel backup drift')
    positions_backup = None
    if receipt['schema'] == 2:
        positions_backup = economy.read_plain(managed, 'positions.backup')
        if economy.sha(positions_backup) != receipt['positions_before']:
            raise ValueError('travel positions backup drift')
        positions_current = economy.read_plain(target, 'cfgeventspawns.xml')
        if economy.sha(positions_current) not in (receipt['positions_before'], receipt['positions_after']):
            raise ValueError('travel event positions drift; reconcile before rollback')
    # Validate all evidence before either target file is restored. Positions may
    # have switched even when interruption prevented the final core switch.
    if positions_backup is not None:
        economy.restore_core(managed, target / 'cfgeventspawns.xml', positions_backup)
    if restore:
        economy.restore_core(managed, target / 'cfgeconomycore.xml', backup)
    shutil.rmtree(managed)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('validate', 'install', 'rollback'))
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--target', type=Path)
    parser.add_argument('--profiles', type=Path, help='read EnableTravel (missing preference defaults true)')
    args = parser.parse_args(argv)
    try:
        if args.command == 'validate':
            report = roster(args.source)
            print('[HC Plan] HC-32 vehicle_families=%d optional=0 refused=runtime_pending state=authored runtime=PENDING'
                  % report['vehicle_families'])
            print('Travel CE parses; cars=39 trucks=7 motorbikes=28 boats=6 aircraft=4; EXP-T1/T2/T4 pending')
        elif args.target is None:
            parser.error('--target is required')
        elif args.command == 'rollback':
            rollback(args.target)
            print('Travel CE rolled back; persisted vehicles are unchanged')
        else:
            enabled = preference(args.profiles) if args.profiles else True
            applied = install(args.source, args.target, enabled)
            print('Travel CE installed; EXP-T1/T2/T4 pending' if applied else 'Travel CE skipped: EnableTravel=false')
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('refused: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
