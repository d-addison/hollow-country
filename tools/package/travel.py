"""Ship the authored V2 travel CE overlay into a stopped private mission copy.

CE runs before HCSettings is loaded: EnableTravel is evaluated at install time.
No script controller, runtime gate override, stock file edit, or save wipe.
"""
import argparse
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
    for ce in core.findall('ce'):
        for file in ce.findall('file'):
            if file.get('type') in kinds:
                filename, tag = kinds[file.get('type')]
                names = {n.get('name').lower() for n in economy.xml(files[filename], tag)}
                path = ce.get('folder', '') + '/' + file.get('name', '')
                existing = economy.xml(economy.read_plain(target, path), tag)
                if names & {n.get('name', '').lower() for n in existing}:
                    raise ValueError('travel class/event has another CE owner; reconcile first')
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
            validate(args.source)
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
