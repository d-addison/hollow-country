"""Bounded stdlib patrol/site contract validator. Never qualifies or installs AI.

Only Id + Position crosses the events boundary; Reviewed is an admission input.
Missions mirror HCXAIMission and may be merged into a separately verified profile.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

MAX_BYTES = 65536
TOKEN = re.compile(r'[A-Za-z0-9_-]{1,48}\Z')
CLASS = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,63}\Z')
HEX = re.compile(r'[0-9a-f]{64}\Z')


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def read_json(path):
    with Path(path).open('rb') as handle:
        payload = handle.read(MAX_BYTES + 1)
    need(len(payload) <= MAX_BYTES, 'input-budget')

    def pairs(entries):
        result = {}
        for key, value in entries:
            need(key not in result, 'duplicate-key')
            result[key] = value
        return result

    def constant(_):
        raise ValueError('nonfinite-number')

    try:
        result = json.loads(payload.decode('utf-8'), object_pairs_hook=pairs,
                            parse_constant=constant)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('invalid-json') from exc
    need(type(result) is dict, 'object-required')
    return result


def loadout_hash(equipment):
    encoded = json.dumps(equipment, sort_keys=True, separators=(',', ':'),
                         allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def position(value):
    return (type(value) is list and len(value) == 3
            and all(type(v) in (int, float) and math.isfinite(v) and abs(v) <= 20000
                    for v in value))


def validate(data, sites):
    need(type(data) is dict and type(sites) is dict, 'object-required')
    need(type(data.get('SchemaVersion')) is int and data['SchemaVersion'] == 1,
         'schema-version')
    source = sites.get('Sites')
    need(type(source) is list and 1 <= len(source) <= 8, 'site-count')
    anchors = {}
    for site in source:
        need(type(site) is dict, 'site-object')
        key = site.get('Id')
        need(type(key) is str and TOKEN.fullmatch(key), 'site-id')
        need(key not in anchors, 'duplicate-site')
        need(site.get('Reviewed') is True and position(site.get('Position')), 'site-unreviewed')
        anchors[key] = site['Position']
    missions = data.get('Missions')
    need(type(missions) is list and 1 <= len(missions) <= 8, 'patrol-count')
    seen = set()
    for route in missions:
        need(type(route) is dict, 'patrol-object')
        need(set(route) == {'SiteId', 'MissionId', 'Anchor', 'GroupSize', 'Spawns',
                           'Waypoints', 'ActorClass', 'FactionName', 'Equipment',
                           'SurveySha256', 'LoadoutSha256'}, 'patrol-fields')
        site_id = route['SiteId']
        need(type(site_id) is str and site_id in anchors, 'unknown-site')
        need(site_id not in seen, 'duplicate-patrol')
        seen.add(site_id)
        need(route['MissionId'] == site_id + '-5', 'mission-id')
        need(position(route['Anchor']) and route['Anchor'] == anchors[site_id], 'anchor-drift')
        count = route['GroupSize']
        need(type(count) is int and 1 <= count <= 8, 'group-size')
        for field, low, high in (('Spawns', count, count), ('Waypoints', 1, 16)):
            points = route[field]
            need(type(points) is list and low <= len(points) <= high, 'route-count')
            need(all(position(p) for p in points), 'route-position')
            need(len({tuple(p) for p in points}) == len(points), 'duplicate-position')
            # Local examples only, never a map-wide omniscient route.
            need(all(sum((p[i] - route['Anchor'][i]) ** 2 for i in range(3)) <= 250 ** 2
                     for p in points), 'route-bound')
        actor, faction = route['ActorClass'], route['FactionName']
        need(type(actor) is str and CLASS.fullmatch(actor) and actor.startswith('eAI_Survivor'),
             'actor-class')
        need(faction == 'Raiders', 'faction-policy')
        equipment = route['Equipment']
        need(type(equipment) is list and 1 <= len(equipment) <= 8, 'loadout-count')
        need(len(equipment) * count <= 128, 'item-budget')
        for item in equipment:
            need(type(item) is dict and set(item) == {'ClassName', 'InHands', 'IsMagazine', 'AmmoCount'},
                 'item-fields')
            need(type(item['ClassName']) is str and CLASS.fullmatch(item['ClassName']), 'item-class')
            need(type(item['InHands']) is bool and type(item['IsMagazine']) is bool, 'item-flags')
            ammo = item['AmmoCount']
            need(type(ammo) is int and 0 <= ammo <= 128, 'finite-ammunition')
            need(item['IsMagazine'] or ammo == 0, 'nonmagazine-ammunition')
        need(sum(i['InHands'] for i in equipment) == 1, 'hands-count')
        need(route['LoadoutSha256'] == loadout_hash(equipment), 'loadout-hash')
        survey = route['SurveySha256']
        need(type(survey) is str and (survey == '' or HEX.fullmatch(survey)), 'survey-hash')
    need(seen == set(anchors), 'site-coverage')
    return {'valid': True, 'qualified': False, 'site_ids': sorted(seen),
            'surveyed': all(bool(r['SurveySha256']) for r in missions)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patrols', required=True, type=Path)
    parser.add_argument('--sites', required=True, type=Path,
                        help='event JSON object with Sites [{Id, Position, Reviewed, ...}]')
    args = parser.parse_args(argv)
    try:
        result = validate(read_json(args.patrols), read_json(args.sites))
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        print(json.dumps({'valid': False, 'qualified': False, 'reason': str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
