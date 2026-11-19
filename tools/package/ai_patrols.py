"""Bounded stdlib patrol/site contract validator and HC site generator. Never qualifies or installs AI.

Only Id + Position crosses the events boundary; Reviewed is an admission input.
Missions mirror HCXAIMission and may be merged into a separately verified profile.

`sites` generates mission/hollow-country/ai/sites.json (HCXAISitePolicy) from the installed stock
mapgrouppos.xml/mapgroupproto.xml, read-only; only the chosen coordinates are written, never a dump:

    python3 tools/package/ai_patrols.py sites --mapgrouppos <mission>/mapgrouppos.xml \
        --mapgroupproto <mission>/mapgroupproto.xml --out mission/hollow-country/ai/sites.json

Routes are qualified natively at runtime (navmesh sampling and FindPath); nothing here establishes DayZ
behavior.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

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
    validate_policy(result)
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
    need(type(source) is list and 1 <= len(source) <= 24, 'site-count')
    anchors = {}
    for site in source:
        need(type(site) is dict, 'site-object')
        key = site.get('Id')
        need(type(key) is str and TOKEN.fullmatch(key), 'site-id')
        need(key not in anchors, 'duplicate-site')
        need(site.get('Reviewed') is True and position(site.get('Position')), 'site-unreviewed')
        anchors[key] = site['Position']
    missions = data.get('Missions')
    need(type(missions) is list and 1 <= len(missions) <= 24, 'patrol-count')
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
        need(type(count) is int and 1 <= count <= 12, 'group-size')
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


MAX_XML = 4 * 1024 * 1024
# Chosen sites (Chernarus). Anchors and clusters are resolved from the stock files at generation time.
SITE_SPEC = {
    'patrols': [
        dict(Id='police-chernogorsk', Faction='Guards', Anchor=['Land_City_PoliceStation'], Near=[6633, 2587],
             Around=['Land_'], Radius=120),
        dict(Id='police-elektrozavodsk', Faction='Guards', Anchor=['Land_City_PoliceStation'], Near=[10456, 2273],
             Around=['Land_'], Radius=120),
        dict(Id='police-berezino', Faction='Guards', Anchor=['Land_City_PoliceStation'], Near=[12065, 9064],
             Around=['Land_'], Radius=120),
        dict(Id='police-zelenogorsk', Faction='Guards', Anchor=['Land_City_PoliceStation'], Near=[2730, 5374],
             Around=['Land_'], Radius=120),
        # Village stations that anchor the two reviewed event sites (HCEventSites.c). The shipped
        # routes were re-authored from stock road points so the first point is beyond MinPlayerDistance.
        dict(Id='police-komarovo', Faction='Guards', Anchor=['Land_Village_PoliceStation'], Near=[3570, 2431],
             Around=['Land_'], Radius=120),
        dict(Id='police-novaya-petrovka', Faction='Guards', Anchor=['Land_Village_PoliceStation'], Near=[3421, 13020],
             Around=['Land_'], Radius=120),
        dict(Id='mil-nwaf', Faction='East', Anchor=['Land_Mil_Barracks1'], Near=[4759, 10624],
             Around=['Land_Mil_'], Radius=250),
        dict(Id='mil-tisy', Faction='East', Anchor=['Land_Mil_Barracks1'], Near=[1665, 14313],
             Around=['Land_Mil_'], Radius=250),
        dict(Id='mil-vybor', Faction='East', Anchor=['Land_Mil_Barracks1'], Near=[4524, 8315],
             Around=['Land_Mil_'], Radius=250),
    ],
    'scavengers': [
        dict(Id='scav-chernogorsk', Near=[6750, 2600], Radius=600),
        dict(Id='scav-elektrozavodsk', Near=[10300, 2250], Radius=600),
        dict(Id='scav-berezino', Near=[12100, 9300], Radius=600),
        dict(Id='scav-vybor', Near=[3820, 8900], Radius=600),
        dict(Id='scav-novodmitrovsk', Near=[11500, 14400], Radius=600),
    ],
    'holdouts': [
        dict(Id='holdout-gorka', Near=[9550, 8850], Radius=500, CacheClass='WoodenCrate',
             Loot=[['TunaCan', 2], ['Rag', 2], ['WaterBottle', 1], ['Mag_IJ70_8Rnd', 1]]),
        dict(Id='holdout-mogilevka', Near=[7550, 5150], Radius=500, CacheClass='SeaChest',
             Loot=[['BakedBeansCan', 2], ['BandageDressing', 1], ['Matchbox', 1], ['Ammo_12gaPellets', 1]]),
        dict(Id='holdout-nadezhdino', Near=[5850, 4750], Radius=500, CacheClass='WoodenCrate',
             Loot=[['PeachesCan', 2], ['Rag', 2], ['Canteen', 1], ['Ammo_380', 1]]),
        dict(Id='holdout-pogorevka', Near=[4450, 6400], Radius=500, CacheClass='SeaChest',
             Loot=[['SardinesCan', 2], ['BandageDressing', 1], ['Battery9V', 1], ['Ammo_22', 1]]),
        dict(Id='holdout-polana', Near=[10700, 8050], Radius=500, CacheClass='WoodenCrate',
             Loot=[['SpaghettiCan', 2], ['Rag', 2], ['WaterBottle', 1], ['Ammo_9x19', 1]]),
    ],
}
HOUSE_PREFIXES = ('Land_House_', 'Land_Village_')
# Scavengers also roam city blocks (loot clusters), holdouts only claim houses.
LOOT_PREFIXES = HOUSE_PREFIXES + ('Land_HouseBlock_', 'Land_Tenement_')
POLICY_DEFAULTS = dict(SchemaVersion=1, WorldName='chernarusplus', BuildVersion='1.30.164289',
                       ObserverPolicy='native-eai', MaxActiveAI=72, MaxActiveSites=15, MinPlayerDistance=200.0,
                       LineOfSightRange=1000.0, MaxLegLength=400.0, CacheClearRadius=300.0,
                       RaidCooldownFloorSeconds=0, ActivationRadiusScale=0.0,
                       MaxSignalWorkPerSecond=8, MaxBetrayalRows=128, BetrayalRetentionSeconds=172800)


def validate_policy(policy):
    """Validate operator overrides; zero/missing preserves legacy runtime defaults."""
    need(type(policy) is dict, 'object-required')
    floor = policy.get('RaidCooldownFloorSeconds', 0)
    need(type(floor) is int and (floor == 0 or 1800 <= floor <= 604800),
         'RaidCooldownFloorSeconds must be 0 or 1800..604800')
    scale = policy.get('ActivationRadiusScale', 0)
    need(type(scale) in (int, float) and math.isfinite(scale)
         and (scale == 0 or .5 <= scale <= 2.),
         'ActivationRadiusScale must be 0 or 0.5..2.0')

KIND_DEFAULTS = {
    'patrol': dict(Loadout='HollowCountry_Patrol', NumberOfAI=2, NumberOfAIMax=5, Behaviour='LOOP', Speed='WALK',
                   ActivationRadius=650.0, DespawnSeconds=600, RespawnSeconds=2700),
    'scavenger': dict(Faction='Raiders', Loadout='HollowCountry_Scavenger', NumberOfAI=2, NumberOfAIMax=6,
                      Behaviour='LOOP', Speed='WALK', ActivationRadius=600.0, DespawnSeconds=600,
                      RespawnSeconds=1800),
    'holdout': dict(Faction='Guards', Loadout='HollowCountry_Holdout', NumberOfAI=3, NumberOfAIMax=8,
                    Behaviour='ALTERNATE', Speed='WALK', ActivationRadius=500.0, DespawnSeconds=900,
                    RespawnSeconds=5400, CacheCooldownSeconds=14400),
}


def parse_stock(text, what):
    """Stock XML from text with bounded size; DTDs and entity declarations are refused."""
    need(type(text) is str and len(text) <= MAX_XML, what + ': input-budget')
    need('<!DOCTYPE' not in text and '<!ENTITY' not in text, what + ': dtd-refused')
    try:
        return ET.fromstring(text.encode('utf-8'))
    except ET.ParseError as exc:
        raise ValueError(what + ': invalid-xml') from exc


def numbers(text, count=3):
    values = [float(v) for v in str(text).split()]
    need(len(values) == count and all(math.isfinite(v) for v in values), 'bad-position')
    return values


def stock_positions(pos_text):
    rows = []
    for node in parse_stock(pos_text, 'mapgrouppos').iter('group'):
        name, pos = node.get('name'), node.get('pos')
        if name and pos and CLASS.fullmatch(name):
            rows.append((name, numbers(pos)))
    need(rows, 'mapgrouppos: no groups')
    return rows


def stock_floors(proto_text):
    floors = {}
    for node in parse_stock(proto_text, 'mapgroupproto').iter('group'):
        name = node.get('name')
        if not name or not CLASS.fullmatch(name):
            continue
        points = [numbers(p.get('pos')) for c in node.iter('container') if c.get('name') == 'lootFloor'
                  for p in c.iter('point') if p.get('pos')]
        if points:
            floors[name] = points
    return floors


def flat(a, b):
    return math.hypot(a[0] - b[0], a[2] - b[2])


def nearest(rows, classes, near, radius, exact=True):
    target = [near[0], 0.0, near[1]]
    hits = [(flat(p, target), name, p) for name, p in rows
            if (name in classes if exact else name.startswith(tuple(classes))) and flat(p, target) <= radius]
    need(hits, 'no stock %s within %d m of %s' % ('/'.join(classes), radius, near))
    return min(hits)


def ring(center, points, count, spacing=25.0):
    """Up to count spread points ordered by bearing around center."""
    chosen = []
    for p in sorted(points, key=lambda p: -flat(p, center)):
        if all(flat(p, q) >= spacing for q in chosen):
            chosen.append(p)
        if len(chosen) == count:
            break
    return sorted(chosen, key=lambda p: math.atan2(p[2] - center[2], p[0] - center[0]))


def rounded(p):
    return [round(float(v), 2) for v in p]


def legs_ok(points, limit):
    loop = points + points[:1]
    return all(5 <= flat(a, b) <= limit for a, b in zip(loop, loop[1:]))


def patrol_site(spec, rows):
    _, _, anchor = nearest(rows, spec['Anchor'], spec['Near'], 200)
    around = [p for name, p in rows if name.startswith(tuple(spec['Around'])) and 10 < flat(p, anchor) <= spec['Radius']]
    # Pulled toward the anchor so each waypoint lies between buildings; navmesh snapping happens at runtime.
    points = [[anchor[i] + (p[i] - anchor[i]) * 0.7 for i in range(3)] for p in ring(anchor, around, 5)]
    need(len(points) >= 3, spec['Id'] + ': fewer than three patrol points')
    site = dict(Id=spec['Id'], Kind='patrol', Faction=spec['Faction'], **KIND_DEFAULTS['patrol'])
    site['Waypoints'] = [rounded(p) for p in points]
    return site


def scavenger_site(spec, rows, limit):
    center = [spec['Near'][0], 0.0, spec['Near'][1]]
    houses = [p for name, p in rows if name.startswith(LOOT_PREFIXES) and flat(p, center) <= spec['Radius']]
    cells = {}
    for p in houses:
        cells.setdefault((int(p[0] // 120), int(p[2] // 120)), []).append(p)
    def chain(start, centroids):
        # Dense loot clusters, each 120..300 m from the previous, so every leg is a short walk.
        found = [start]
        while len(found) < 4:
            options = [c for c in centroids if c not in found and 120 <= flat(c, found[-1]) <= 300
                       and all(flat(c, q) >= 120 for q in found)]
            if not options:
                break
            found.append(min(options, key=lambda c: (flat(c, found[-1]), -c[3])))
        return found

    points = []
    for least in (3, 2):
        centroids = [[sum(p[i] for p in c) / len(c) for i in range(3)] + [len(c)]
                     for c in cells.values() if len(c) >= least]
        for start in sorted(centroids, key=lambda c: -c[3]):
            points = chain(start, centroids)
            if len(points) >= 3:
                break
        if len(points) >= 3:
            break
    points = [c[:3] for c in points]
    need(len(points) >= 3, spec['Id'] + ': no loot-cluster chain within leg limit')
    behaviour = 'LOOP' if flat(points[0], points[-1]) <= limit - 20 else 'ALTERNATE'
    site = dict(Id=spec['Id'], Kind='scavenger', **KIND_DEFAULTS['scavenger'])
    site.update(Behaviour=behaviour, Waypoints=[rounded(p) for p in points])
    return site


def holdout_site(spec, rows, floors):
    usable = {name for name, points in floors.items() if name.startswith(HOUSE_PREFIXES) and len(points) >= 4
              and max(p[1] for p in points) - min(p[1] for p in points) < 0.5}
    _, house, position = nearest(rows, usable, spec['Near'], spec['Radius'])
    points = floors[house]
    center = [sum(p[i] for p in points) / len(points) for i in range(3)]
    local = ring(center, points, 3, spacing=1.5)
    need(len(local) >= 2, spec['Id'] + ': fewer than two separated floor points')
    rest = [p for p in points if p not in local]
    need(rest, spec['Id'] + ': no floor point left for the cache')
    cache = min(rest, key=lambda p: flat(p, center))
    site = dict(Id=spec['Id'], Kind='holdout', **KIND_DEFAULTS['holdout'])
    site.update(Waypoints=[], HouseClass=house, HousePosition=rounded(position),
                LocalPoints=[rounded(p) for p in local], CacheClass=spec['CacheClass'], CacheLocal=rounded(cache),
                CacheLoot=[{'ClassName': c, 'Quantity': q} for c, q in spec['Loot']])
    return site


def generate_sites(pos_text, proto_text, spec=None):
    spec = SITE_SPEC if spec is None else spec
    rows, floors = stock_positions(pos_text), stock_floors(proto_text)
    policy = dict(POLICY_DEFAULTS)
    validate_policy(policy)
    sites = [patrol_site(s, rows) for s in spec.get('patrols', [])]
    sites += [scavenger_site(s, rows, policy['MaxLegLength']) for s in spec.get('scavengers', [])]
    sites += [holdout_site(s, rows, floors) for s in spec.get('holdouts', [])]
    need(len({s['Id'] for s in sites}) == len(sites), 'duplicate-site')
    policy['Sites'] = sites
    return policy


def read_text(path):
    with Path(path).open('rb') as handle:
        payload = handle.read(MAX_XML + 1)
    need(len(payload) <= MAX_XML, 'input-budget')
    return payload.decode('utf-8')


def main_sites(argv):
    parser = argparse.ArgumentParser(description='generate HC sites from stock map data (read-only)')
    parser.add_argument('--mapgrouppos', required=True, type=Path)
    parser.add_argument('--mapgroupproto', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        policy = generate_sites(read_text(args.mapgrouppos), read_text(args.mapgroupproto))
    except (OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({'generated': False, 'reason': str(exc)}))
        return 2
    args.out.write_text(json.dumps(policy, indent=2) + '\n')
    print(json.dumps({'generated': True, 'sites': [s['Id'] for s in policy['Sites']]}))
    return 0


def main(argv=None):
    import sys
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['sites']:
        return main_sites(argv[1:])
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
