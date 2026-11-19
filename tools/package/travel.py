"""Ship the authored V2 travel CE overlay into a stopped private mission copy.

CE runs before HCSettings is loaded: EnableTravel is evaluated at install time.
No script controller, runtime gate override, stock file edit, or save wipe.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.package import economy

MANAGED = 'hollow-country-travel'
INPUTS = ('cfgeconomycore.xml',)
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
BICYCLE_WHEELS = {**dict.fromkeys(('Old_Bike', 'Old_Bike_White', 'Old_Bike_Red', 'Old_Bike_Green',
                                 'Old_Bike_Blue', 'Old_Bike_Pink'), 'bicycle_wheel'),
                  **dict.fromkeys(('Lady_Bicycle', 'Lady_Bicycle_Purple'), 'ladybicycle_wheel')}
VEHICLE_CLASSES = {n.casefold() for names in NATIVE_FAMILIES.values() for n in names} | {
    n.casefold() for n in BICYCLE_WHEELS}
CANONICAL_VEHICLES = {n.casefold(): n for names in NATIVE_FAMILIES.values() for n in names}
CANONICAL_VEHICLES.update({n.casefold(): n for n in BICYCLE_WHEELS})


def repair_parts(vehicle):
    """Reviewed attachment identities/multiplicities, not invented slot names.

    Ruined wheels inherit the matching native wheel slots. GlowPlug declares a
    scalar inventorySlot in vehicles_parts/config.bin (not an array). These
    checks preserve the authored probabilities; they add no repair supplies.
    """
    vehicle = CANONICAL_VEHICLES.get(vehicle.casefold(), '')
    if not vehicle:
        return None
    if vehicle in BICYCLE_WHEELS:
        return Counter({BICYCLE_WHEELS[vehicle]: 2})
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
    return _roster(events, templates)


def _roster(events, templates):
    owners = vehicle_owners(events)
    expected = {n.casefold() for key, names in NATIVE_FAMILIES.items()
                if key != 'VehicleTruck01' for n in names}
    if set(owners) != expected:
        raise ValueError('HC-32 incomplete native travel roster')
    for event in events:
        family = NATIVE_FAMILIES.get(event.get('name'))
        if family is None:
            raise ValueError('HC-32 native travel roster has an unreviewed event: ' + str(event.get('name')))
        if {n.get('type') for n in event.findall('children/child')} != set(family):
            raise ValueError('HC-32 native vehicle family mismatch')
    rows = {n.get('name', '').casefold(): n for n in templates.findall('type')}
    if set(rows) & {n.casefold() for n in NATIVE_FAMILIES['VehicleTruck01']}:
        raise ValueError('HC-32 truck repair must remain native-stock')
    for name in expected:
        if name not in rows:
            raise ValueError('HC-32 missing native repair template: ' + name)
        wanted = repair_parts(rows[name].get('name'))
        actual = Counter(n.get('name', '').casefold() for n in rows[name].findall('attachments/item'))
        if actual != Counter({n.casefold(): count for n, count in wanted.items()}):
            raise ValueError('HC-32 incomplete native repair parts: ' + name)
    return {'vehicle_families': len(NATIVE_FAMILIES), 'authored_variants': len(expected),
            'runtime': 'PENDING', 'families': {key: {
                'disposition': 'native-stock' if key == 'VehicleTruck01' else 'hc-override',
                'variants': list(names), 'repair': 'native-stock' if key == 'VehicleTruck01' else 'native-attachments'
            } for key, names in NATIVE_FAMILIES.items()}}


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
                'VehicleSedan02': 9, 'VehicleOffroad02': 3, 'VehicleMotorbike': 28, 'VehicleBoat': 6}
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
        _roster(events, roots[2])
    fragment = economy.xml(files[REGISTRATION], 'economycore')
    if (len(fragment) != 1 or fragment[0].tag != 'ce'
            or fragment[0].attrib != {'folder': MANAGED + '/ce'}
            or [f.attrib for f in fragment[0]] != [
                {'name': name.split('/')[-1], 'type': kind}
                for name, kind in zip(CE_FILES, ('types', 'events', 'spawnabletypes'))]):
        raise ValueError('unsupported travel CE registration')
    return files


def install(source, target, enabled=True):
    if type(enabled) is not bool:
        raise ValueError('EnableTravel must be boolean')
    if not enabled:
        return False
    target = economy._target(target)
    managed = economy.child(target, MANAGED)
    if os.path.lexists(managed):
        raise ValueError('travel already installed or interrupted; inspect/rollback first')
    files = validate(source)
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
    import xml.etree.ElementTree as ET
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
    receipt = {'schema': 1, 'before': economy.sha(original), 'after': economy.sha(patched),
               **{name: economy.sha(files[name]) for name in CE_FILES}}
    managed.mkdir()
    economy.fresh_write(managed, 'receipt.json', economy.encode(receipt))
    economy.fresh_write(managed, 'core.backup', original)
    (managed / 'ce').mkdir()
    for name in CE_FILES:
        economy.fresh_write(managed, name, files[name])
    economy.restore_core(managed, target / 'cfgeconomycore.xml', patched)
    return True


def rollback(target):
    target = economy._target(target)
    managed = economy.child(target, MANAGED)
    if not managed.is_dir():
        raise ValueError('nothing to roll back')
    economy.preflight_managed(managed, {*CE_FILES, 'receipt.json', 'core.backup', 'core.next'})
    receipt = json.loads(economy.read_plain(managed, 'receipt.json'))
    if (set(receipt) != {'schema', 'before', 'after', *CE_FILES} or receipt['schema'] != 1
            or any(not isinstance(receipt[k], str) or not economy.HEX64.fullmatch(receipt[k])
                   for k in ('before', 'after', *CE_FILES))):
        raise ValueError('invalid travel receipt')
    current = economy.read_plain(target, 'cfgeconomycore.xml')
    if economy.sha(current) not in (receipt['before'], receipt['after']):
        raise ValueError('core drift; roll back later CE installers first')
    restore = economy.needs_restore(managed, receipt, economy.sha(current),
                                    [(n, n, 'travel CE drift: ' + n) for n in CE_FILES])
    if restore:
        backup = economy.read_plain(managed, 'core.backup')
        if economy.sha(backup) != receipt['before']:
            raise ValueError('travel backup drift')
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
            print('Travel CE parses; cars=39 motorbikes=28 boats=6; EXP-T1/T2/T4 pending')
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
