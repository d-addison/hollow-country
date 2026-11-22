"""Offline DamageZones census of installed configs; counts and a fixed vocabulary only.

Reads rapified ``config.bin`` members of installed PBO folders (vanilla Addons plus any
folder of built or Workshop PBOs the caller names) with the bounded ``pbo_config`` reader,
merges ``CfgVehicles`` classes the way later-loaded patches do, and resolves each actor's
DamageZones through the class parent chain. The report holds only counts per fixed family
and fixed zone vocabulary: no class names, paths or vanilla values beyond hit-point numbers
are written, so nothing in it is a dump. Static file evidence; it never establishes what the
running engine does.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from tools.audit import pbo_config as pbo
from tools.release.ship_inputs import ADDONS

# Fixed vocabularies. Zone names outside ZONES are only counted, never listed.
ZONES = ('Head', 'Neck', 'Brain', 'Torso', 'Pelvis', 'LeftArm', 'RightArm', 'LeftHand', 'RightHand',
         'LeftLeg', 'RightLeg', 'LeftFoot', 'RightFoot')
FAMILIES = ('infected_vanilla', 'infected_hc', 'eai_actor', 'survivor_vanilla')
SKIP_REASONS = {'infected_vanilla': 'INFECTED_BASE_NOT_INSTALLED', 'infected_hc': 'HC_INFECTED_NOT_INSTALLED',
                'eai_actor': 'EAI_ACTORS_NOT_INSTALLED', 'survivor_vanilla': 'SURVIVOR_BASE_NOT_INSTALLED'}
MAX_ZONE_DECLARATIONS = 500_000
_LOWER_ZONES = {name.lower(): name for name in ZONES}


def _number(value):
    if isinstance(value, float):
        value = round(value, 3)
        return int(value) if value == int(value) else value
    return value


def read_vehicles(data):
    """``{class: {parent, scope, zones: {zone: {parent, hp}}, own_zones}}`` for one config.bin.

    Names are lower-cased because engine config class names are case-insensitive.
    """
    rap = pbo._Rap(data)
    _, root = rap.entries(16)
    result = {}
    for kind, name, offset in root:
        if kind != 'class' or name.lower() != 'cfgvehicles':
            continue
        _parent, children = rap.entries(offset)
        for ckind, cname, cpos in children:
            if ckind != 'class':
                continue
            parent, body = rap.entries(cpos)
            row = {'parent': parent.lower() or None, 'scope': None, 'zones': {}, 'own_zones': False}
            for bkind, bname, value in body:
                if bkind == 'value' and bname.lower() == 'scope' and isinstance(value, (int, float)):
                    row['scope'] = _number(value)
                elif bkind == 'class' and bname.lower() == 'damagesystem':
                    _p, system = rap.entries(value)
                    for skind, sname, spos in system:
                        if skind == 'class' and sname.lower() == 'damagezones':
                            row['own_zones'] = True
                            row['zones'] = read_zones(rap, spos)
            result[cname.lower()] = row
    return result


def read_zones(rap, offset):
    _parent, zones = rap.entries(offset)
    result = {}
    for kind, name, pos in zones:
        if kind != 'class':
            continue
        parent, body = rap.entries(pos)
        hp = None
        for bkind, bname, value in body:
            if bkind == 'class' and bname.lower() == 'health':
                for hkind, hname, hvalue in rap.entries(value)[1]:
                    if hkind == 'value' and hname.lower() == 'hitpoints' and isinstance(hvalue, (int, float)):
                        hp = _number(hvalue)
        result[name.lower()] = {'parent': parent.lower() or None, 'hp': hp}
    return result


def merge(classes, loaded):
    """Fold one config's classes over the earlier ones (later patches win, nested like config merge)."""
    for name, row in loaded.items():
        old = classes.setdefault(name, {'parent': None, 'scope': None, 'zones': {}, 'own_zones': False})
        old['parent'] = row['parent'] or old['parent']
        old['scope'] = row['scope'] if row['scope'] is not None else old['scope']
        old['own_zones'] = old['own_zones'] or row['own_zones']
        for zone, detail in row['zones'].items():
            current = old['zones'].setdefault(zone, {'parent': None, 'hp': None})
            current['parent'] = detail['parent'] or current['parent']
            current['hp'] = detail['hp'] if detail['hp'] is not None else current['hp']


def scan(addon_dirs):
    """Merge CfgVehicles from every PBO under the folders, in folder then name order."""
    classes, stats = {}, Counter()
    declared = 0
    for folder in addon_dirs:
        stats['addon_dirs'] += 1
        for path in sorted(Path(folder).glob('*.pbo')):
            stats['pbos'] += 1
            try:
                index = pbo.read_pbo_index(path)
                members = pbo.config_member_names(index)
                for member in members:
                    loaded = read_vehicles(pbo.read_member(path, index, member))
                    declared += sum(len(row['zones']) for row in loaded.values())
                    if declared > MAX_ZONE_DECLARATIONS:
                        raise ValueError('zone declarations exceed budget')
                    merge(classes, loaded)
                    stats['config_members'] += 1
            except (ValueError, OSError, EOFError, IndexError, KeyError):
                stats['config_unreadable'] += 1
    stats['cfgvehicles_classes'] = len(classes)
    return classes, stats


def family_of(classes, name):
    chain = pbo.ancestry(classes, name)
    if 'zombiebase' in chain:
        return 'infected_hc' if name.startswith('hc_') else 'infected_vanilla'
    if name.startswith('eai') or 'eaibase' in chain:
        return 'eai_actor'
    if 'survivorbase' in chain:
        return 'survivor_vanilla'
    return None


def zone_names(classes, name):
    names = set()
    for ancestor in pbo.ancestry(classes, name):
        names.update(classes[ancestor]['zones'])
    return names


def zone_link(classes, name, zone):
    """Nearest declared parent zone along the class chain, or None.

    ``class Zone: Zone`` is an override of the parent class's zone, not a link to another zone.
    """
    for ancestor in pbo.ancestry(classes, name):
        detail = classes[ancestor]['zones'].get(zone)
        if detail and detail['parent'] and detail['parent'] != zone:
            return detail['parent']
    return None


def zone_hp(classes, name, zone, depth=0):
    """Hit points the zone resolves to; a zone parent is read in the class that declared the link."""
    for ancestor in pbo.ancestry(classes, name):
        detail = classes[ancestor]['zones'].get(zone)
        if detail is None:
            continue
        if detail['hp'] is not None:
            return detail['hp']
        if detail['parent'] and detail['parent'] != zone and depth < 8:
            return zone_hp(classes, ancestor, detail['parent'], depth + 1)
    return None


def census(classes):
    """Counts per family and zone vocabulary for every spawnable (scope 2) actor class."""
    families = {}
    for family in FAMILIES:
        families[family] = {'classes': 0, 'public': 0, 'with_zones': 0, 'own_zone_overrides': 0,
                            'zone_names_outside_vocabulary': 0, 'zones': {},
                            'right_leg': {'present': 0, 'inherits_left_leg': 0, 'hitpoints_equal_left': 0,
                                          'hitpoints_differ_from_left': 0, 'hitpoints_unresolved': 0}}
    stats = {family: {'hp': defaultdict(Counter), 'link': defaultdict(Counter), 'present': Counter()}
             for family in FAMILIES}
    outside = {family: set() for family in FAMILIES}
    for name in sorted(classes):
        family = family_of(classes, name)
        if family is None:
            continue
        row = families[family]
        row['classes'] += 1
        if pbo.resolve_scope(classes, name) != 2:
            continue
        row['public'] += 1
        names = zone_names(classes, name)
        row['with_zones'] += bool(names)
        row['own_zone_overrides'] += bool(classes[name]['own_zones'])
        for zone in sorted(names):
            if zone not in _LOWER_ZONES:
                outside[family].add(zone)
                continue
            label = _LOWER_ZONES[zone]
            hp = zone_hp(classes, name, zone)
            link = zone_link(classes, name, zone)
            stats[family]['present'][label] += 1
            stats[family]['hp'][label]['unresolved' if hp is None else str(hp)] += 1
            stats[family]['link'][label]['none' if link is None else _LOWER_ZONES.get(link, 'other')] += 1
        if 'rightleg' in names:
            leg = row['right_leg']
            leg['present'] += 1
            leg['inherits_left_leg'] += zone_link(classes, name, 'rightleg') == 'leftleg'
            right, left = zone_hp(classes, name, 'rightleg'), zone_hp(classes, name, 'leftleg')
            if right is None or left is None:
                leg['hitpoints_unresolved'] += 1
            elif right == left:
                leg['hitpoints_equal_left'] += 1
            else:
                leg['hitpoints_differ_from_left'] += 1
    for family in FAMILIES:
        row = families[family]
        row['zone_names_outside_vocabulary'] = len(outside[family])
        for label in ZONES:
            if stats[family]['present'][label]:
                row['zones'][label] = {'present': stats[family]['present'][label],
                                       'hitpoints': dict(sorted(stats[family]['hp'][label].items())),
                                       'parent_link': dict(sorted(stats[family]['link'][label].items()))}
    return families


def report(families=None, stats=None, skips=()):
    families = families or {}
    stats = dict(stats or {})
    return {'schema': 1, 'status': 'pass', 'sources': dict(sorted(stats.items())), 'families': families,
            'skipped': sorted(skips, key=lambda s: s['reason']),
            'vocabulary': {'families': list(FAMILIES), 'zones': list(ZONES)},
            'limitations': ['Static config evidence from installed PBOs; engine inheritance is not exercised.',
                            'Zone parents resolve in the class that declared the link, as config lookup does.',
                            'Only spawnable (scope 2) classes are counted in zone statistics.',
                            'Output has counts only: no class names, paths or vanilla dumps.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--addons', type=Path, action='append',
                        help='PBO folder; repeat for built/Workshop folders (default: the shared Addons)')
    parser.add_argument('--report', type=Path, help='JSON destination; defaults to stdout')
    parser.add_argument('--require-installed', action='store_true',
                        help='fail on any skip (missing folder, unreadable config or empty family)')
    args = parser.parse_args(argv)
    folders = args.addons or [ADDONS]
    present = [f for f in folders if f.is_dir() and any(f.glob('*.pbo'))]
    skips = [{'reason': 'ADDONS_UNAVAILABLE'} for f in folders if f not in present]
    families, stats = {}, {}
    if present:
        try:
            classes, stats = scan(present)
            families = census(classes)
            skips += [{'reason': SKIP_REASONS[name]} for name in FAMILIES if not families[name]['public']]
            if stats['config_unreadable']:
                skips.append({'reason': 'CONFIG_UNREADABLE'})
        except Exception:
            # Reader diagnostics can carry private paths; keep the failure machine readable.
            print('damagezones_census: fail reason=INVALID_INPUT_OR_READER')
            return 1
    result = report(families, stats, skips)
    rendered = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n'
    if args.report:
        args.report.write_text(rendered, encoding='utf-8')
    else:
        print(rendered, end='')
    for reason in sorted({s['reason'] for s in skips}):
        print('SKIP ' + reason)
    print(f"damagezones_census: {result['status']} families={sum(1 for f in families.values() if f['public'])} "
          f"classes={sum(f['classes'] for f in families.values())} skipped={len(skips)}")
    return int(args.require_installed and bool(skips))


if __name__ == '__main__':
    raise SystemExit(main())
