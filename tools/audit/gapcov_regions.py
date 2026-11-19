"""Derive finite regional inputs from installed stock mission metadata (stdlib only).

Run with --stock-mission, optionally --livonia-mission and --livonia-world-pbo.
--write updates only the three owned regional JSON catalogues. No engine calls,
Expansion data, survey receipts, inventory grants or native acceptance are made.
Placement IDs are zero-based group ordinals, pinned to the exact XML SHA-256.
Nearest-label assignment is an offline partition, never an official boundary.
"""
import argparse
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from tools.audit import pbo_config

MAX_XML_BYTES = 32 * 1024 * 1024
MAX_PLACEMENTS = 100000
MAX_CATALOG_BYTES = 1048576  # HCWorldStore.MAX_BYTES


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(path.read_text())


def encoded(value):
    # Keep placement-ID arrays and individual records compact, while splitting
    # large catalogs into reviewable rows within the native one-megabyte budget.
    def render(item, depth=0):
        compact = json.dumps(item, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
        if len(compact) <= 2000 or not isinstance(item, (dict, list)):
            return compact
        padding = '  ' * (depth + 1)
        closing = '  ' * depth
        if isinstance(item, dict):
            body = [padding + json.dumps(key) + ': ' + render(val, depth + 1) for key, val in item.items()]
            return '{\n' + ',\n'.join(body) + '\n' + closing + '}'
        if all(not isinstance(val, (dict, list)) for val in item):
            return compact
        return '[\n' + ',\n'.join(padding + render(val, depth + 1) for val in item) + '\n' + closing + ']'
    return (render(value) + '\n').encode()


def stock(mission):
    roots, pins = {}, {}
    for name, tag in [('mapgrouppos.xml', 'map'), ('mapgroupproto.xml', 'prototype')]:
        with (mission / name).open('rb') as stream:
            raw = stream.read(MAX_XML_BYTES + 1)
        if len(raw) > MAX_XML_BYTES or b'\x00' in raw or re.search(br'<!\s*(DOCTYPE|ENTITY)', raw, re.I):
            raise ValueError('unsupported stock XML')
        roots[name] = ET.fromstring(raw)
        if roots[name].tag != tag:
            raise ValueError('unexpected stock XML root')
        pins[name] = digest(raw)
    usages = {g.attrib['name']: sorted({u.attrib['name'] for u in g.findall('usage')})
              for g in roots['mapgroupproto.xml'].findall('group')}
    rows = []
    for ordinal, group in enumerate(roots['mapgrouppos.xml'].findall('group')):
        position = [float(v) for v in group.attrib['pos'].split()]
        if len(position) != 3 or not all(math.isfinite(v) for v in position):
            raise ValueError('invalid stock transform')
        rows.append(dict(Id=ordinal, ClassName=group.attrib['name'], Position=position,
                         Usage=usages.get(group.attrib['name'], []), HasPrototype=group.attrib['name'] in usages))
    if not rows or len(rows) > MAX_PLACEMENTS:
        raise ValueError('stock placement budget')
    return rows, pins


def distance(a, b):
    return (a[0] - b[0]) ** 2 + (a[2] - b[2]) ** 2


def components(rows, link):
    """Exact planar connected components; grid buckets avoid all-pairs scans."""
    buckets = defaultdict(list)
    for row in rows:
        point = row['Position']
        buckets[int(point[0] // link), int(point[2] // link)].append(row)
    seen, result = set(), []
    for row in rows:
        if row['Id'] in seen:
            continue
        seen.add(row['Id'])
        todo, members = [row], []
        while todo:
            current = todo.pop()
            members.append(current)
            point = current['Position']
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for other in buckets[int(point[0] // link) + dx, int(point[2] // link) + dz]:
                        if other['Id'] not in seen and distance(point, other['Position']) <= link * link:
                            seen.add(other['Id'])
                            todo.append(other)
        result.append(sorted(members, key=lambda m: m['Id']))
    return result


def center(rows):
    return [sum(row['Position'][axis] for row in rows) / len(rows) for axis in range(3)]


def nearest(point, rows, field='Anchor'):
    return min(rows, key=lambda row: (distance(point, row[field]), str(row['Id'])))


def membership(rows):
    # Derived identity inventory only: no full vanilla transforms/content copied.
    return dict(PlacementIds=[row['Id'] for row in rows])


def route(rows, anchor, policy):
    """Use distinct stock XZ anchors; native ground/navmesh owner must qualify."""
    ordered = sorted(rows, key=lambda row: (distance(row['Position'], anchor), str(row['Id'])))
    if not ordered:
        return []
    first = ordered[0]
    for second in ordered[1:]:
        leg = math.sqrt(distance(first['Position'], second['Position']))
        if 5 <= leg <= policy['MaxLegLength']:
            return [first, second]
    return []


def ai_site(site_id, pair, template):
    result = {key: deepcopy(template[key]) for key in (
        'Kind', 'Faction', 'Loadout', 'NumberOfAI', 'NumberOfAIMax', 'Behaviour',
        'Speed', 'ActivationRadius', 'DespawnSeconds', 'RespawnSeconds')}
    result.update(Id=site_id, Behaviour='ALTERNATE', Waypoints=[[row['Position'][0], 0, row['Position'][2]] for row in pair],
                  Provenance=dict(AnchorRefs=[row['Id'] for row in pair],
                                  Basis='stock XZ, y=0 placeholder; native SurfaceY/route qualification required', Runtime='PENDING'))
    return result


def add_story(stories, key, locality_id, island, anchor_row, kit):
    site_id = 'gapcov-' + key
    if key == locality_id and any(site['LocalityId'] == locality_id for site in stories['Sites']):
        return
    stories['Sites'].append(dict(Id=site_id, LocalityId=locality_id, Island=island,
        AnchorSource='stock mapgrouppos.xml', SourceRef=str(anchor_row['Id']),
        Anchor=anchor_row['Position'], SourceReviewed=True, Surveyed=False,
        Refusal='HC42_KIT_SITE_SURVEY_PENDING', Runtime='PENDING',
        AnchorBasis='Building/object origin, never a surveyed ground or kit layout transform'))
    stories['Candidates'].append(dict(Id=site_id, Kit=kit, SiteId=site_id, Variant='primary',
        Setting='Finite regional scenery candidate; no invented casualties or world facts.',
        Qualified=False, NativeReceipt='', Refusal='HC42_KIT_SITE_SURVEY_PENDING', Runtime='PENDING'))


def derive(rows, pins, localities, clusters, policy, queue, stories=None, extra_anchors=()):
    link = policy['HC43']['AuditRanges']['ResidentialLinkMeters']
    template = next(s for s in policy['Sites'] if s['Kind'] == 'patrol' and not s.get('Checkpoint'))
    for locality in localities:
        locality['LabelAnchor'] = locality.get('LabelAnchor', locality['Anchor'])
    assigned = defaultdict(list)
    for row in rows:
        assigned[nearest(row['Position'], localities, 'LabelAnchor')['Id']].append(row)
    gaps = []

    def candidate(key, members, anchor, locality_id, island, site_ids):
        pair = route(members, anchor, policy)
        if not pair and not island:
            pair = route(list(members) + list(extra_anchors), anchor, policy)
        if stories is not None and members:
            add_story(stories, key, locality_id, island, nearest(anchor, members, 'Position'), 'survivor-distress-camp')
        if not pair:
            gaps.append(dict(Id=key, Reason='no distinct stock pair within MaxLegLength', Runtime='PENDING'))
            return
        site_id = 'gapcov-' + key
        policy['Sites'].append(ai_site(site_id, pair, template))
        site_ids.append(site_id)

    for locality in localities:
        members = assigned[locality['Id']]
        if not members:
            raise ValueError('locality has no source-derived members: ' + locality['Id'])
        label = locality.get('LabelAnchor', locality['Anchor'])
        locality['LabelAnchor'] = label
        anchor = nearest(label, members, 'Position')
        locality.update(Anchor=anchor['Position'], AnchorPlacementId=anchor['Id'],
                        Membership=membership(members), Disposition='source_resolved_runtime_pending')
        queue_row = next(q for q in queue['Localities'] if q['Id'] == locality['Id'])
        if not queue_row['SiteIds']:
            candidate(locality['Id'], members, anchor['Position'], locality['Id'], locality['Island'], queue_row['SiteIds'])
        locality['SiteIds'] = list(queue_row['SiteIds'])
        if stories is not None:
            if not any(s['LocalityId'] == locality['Id'] for s in stories['Sites']):
                add_story(stories, locality['Id'], locality['Id'], locality['Island'], anchor, 'survivor-distress-camp')
            for site in stories['Sites']:
                if site['LocalityId'] == locality['Id'] and site['AnchorSource'] == 'HC43ContentManifest.Localities':
                    site.update(Anchor=anchor['Position'], AnchorSource='stock mapgrouppos.xml',
                                SourceRef=str(anchor['Id']), SourceReviewed=True,
                                Refusal='HC42_KIT_SITE_SURVEY_PENDING', Runtime='PENDING',
                                AnchorBasis='Stock object origin; native ground/layout/access pending')

    houses = [row for row in rows if row['ClassName'].startswith('Land_House')]
    house_components = components(houses, link)
    used = set()
    for cluster in clusters:
        label = cluster.get('LabelAnchor', cluster['Anchor'])
        members = min(house_components, key=lambda group: distance(center(group), label))
        centroid = center(members)
        if len(members) != cluster['Houses'] or distance(centroid, label) > 0.01 or members[0]['Id'] in used:
            raise ValueError('residential source membership mismatch: ' + cluster['Id'])
        used.add(members[0]['Id'])
        locality = nearest(centroid, localities, 'LabelAnchor')
        anchor = nearest(centroid, members, 'Position')
        cluster.update(LabelAnchor=label, Anchor=anchor['Position'], LocalityId=locality['Id'],
                       Membership=membership(members), Disposition='source_resolved_runtime_pending', SiteIds=[])
        key = cluster['Id'].lower()
        candidate(key, members, anchor['Position'], locality['Id'], locality['Island'], cluster['SiteIds'])
        queue['Localities'].append(dict(Id='gapcov-' + key, Island=locality['Island'],
            Source='HC43.ResidentialClusters/' + cluster['Id'], SiteIds=cluster['SiteIds']))

    atlas = []
    for usage, prefix in [('Industrial', 'i'), ('Military', 'm')]:
        selected = [row for row in rows if usage in row['Usage']]
        for index, members in enumerate(components(selected, link), 1):
            key = prefix + str(index).zfill(3)
            centroid = center(members)
            anchor = nearest(centroid, members, 'Position')
            locality = nearest(anchor['Position'], localities, 'LabelAnchor')
            entry = dict(Id=key, Usage=usage, LocalityId=locality['Id'],
                         Anchor=anchor['Position'], Membership=membership(members), SiteIds=[])
            # Singleton clusters cannot create a valid route. Preserve their
            # identity and use nearby stock members of the same locality instead.
            candidates = members
            if not route(candidates, anchor['Position'], policy):
                candidates = rows
                if locality['Island']:
                    candidates = assigned[locality['Id']]
            candidate(key, candidates, anchor['Position'], locality['Id'], locality['Island'], entry['SiteIds'])
            atlas.append(entry)
            queue['Localities'].append(dict(Id='gapcov-' + key, Island=locality['Island'],
                Source='HC43.ZoneAtlas/' + key, SiteIds=entry['SiteIds']))
    return dict(Sources=pins, MembershipPolicy='Nearest stock label planar partition; tie by ID. Not official borders or island-access proof.',
        ClusterPolicy='Land_House* connected components at existing HC43 ResidentialLinkMeters; exact count/centroid reconciliation.',
        AtlasPolicy='All placements with exact stock prototype Industrial/Military usage; connected components at ResidentialLinkMeters. Includes mixed-use sheds; no invented zone boundaries.',
        PlacementCount=len(rows), ZoneAtlas=atlas, Gaps=gaps,
        UnmatchedPrototypeClasses=sorted({r['ClassName'] for r in rows if not r['HasPrototype']}), Runtime='PENDING')


def supplemental_anchors(mission):
    """Native CE/territory centres as finite XZ proposals, never live habitats."""
    anchors, pins = [], {}
    paths = [mission / 'cfgeventspawns.xml'] + sorted((mission / 'env').glob('*territories.xml'))
    for path in paths:
        if not path.is_file():
            continue
        with path.open('rb') as stream:
            raw = stream.read(MAX_XML_BYTES + 1)
        if len(raw) > MAX_XML_BYTES or b'\x00' in raw or re.search(br'<!\s*(DOCTYPE|ENTITY)', raw, re.I):
            raise ValueError('unsupported supplemental stock XML')
        relative = path.relative_to(mission).as_posix()
        pins[relative] = digest(raw)
        for ordinal, node in enumerate(ET.fromstring(raw).iter()):
            if node.tag not in ('pos', 'zone') or 'x' not in node.attrib or 'z' not in node.attrib:
                continue
            x, z = float(node.attrib['x']), float(node.attrib['z'])
            if not math.isfinite(x) or not math.isfinite(z):
                raise ValueError('invalid supplemental coordinate')
            anchors.append(dict(Id=relative + '#' + str(ordinal), Position=[x, 0, z]))
    return anchors, pins


def map_existing(root, localities):
    links = {l['Id']: dict(SceneChains=[], ShelterScenes=[], PoliceEventSources=[]) for l in localities}
    sources = {}
    for relative, kind, collection, position in [
        ('events/scene-chains.json', 'SceneChains', 'Chains', None),
        ('travel/auditshelter_scenes.json', 'ShelterScenes', 'Scenes', 'Position'),
        ('ai/event-sites.contract.json', 'PoliceEventSources', 'Sites', 'Position')]:
        path = root / relative
        sources[relative] = digest(path.read_bytes())
        for row in load(path)[collection]:
            point = row[position] if position else row['Stages'][0]['Objective']['Source']
            locality = nearest(point, localities, 'LabelAnchor')
            links[locality['Id']][kind].append(row['Id'])
    return dict(Sources=sources, Policy='Nearest-label source assignment only; original scene identities and transforms unchanged.', Localities=links)


def livonia_labels(pbo):
    raw = pbo_config.read_member(pbo, pbo_config.read_pbo_index(pbo), 'config.bin')
    rap = pbo_config._Rap(raw)
    _, entries = rap.entries(16)
    for name in ('CfgWorlds', 'Enoch', 'Names'):
        entry = next(e for e in entries if e[0] == 'class' and e[1].lower() == name.lower())
        _, entries = rap.entries(entry[2])
    labels = []
    for kind, name, offset in entries:
        if kind != 'class':
            continue
        _, body = rap.entries(offset)
        values = {key: value for entry_kind, key, value in body if entry_kind in ('array', 'value')}
        if values.get('type') not in ('Village', 'City', 'Capital') or 'position' not in values:
            continue
        x, z = values['position']
        labels.append(dict(Id=name.lower().replace('_', '-'), Source='CfgWorlds/Enoch/Names/' + name,
                           Anchor=[x, 0, z], Island=False, SiteIds=[]))
    if not labels:
        raise ValueError('no Livonia settlement labels')
    return labels, digest(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-mission', type=Path, required=True)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--livonia-mission', type=Path)
    parser.add_argument('--livonia-world-pbo', type=Path)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args(argv)
    try:
        root = args.repo / 'mission/hollow-country'
        paths = [root / p for p in ('ai/localities.json', 'ai/sites.json', 'events/story-sites.json')]
        queue, policy, stories = [load(path) for path in paths]
        # Rebuild owned derivations deterministically; preserve authored legacy rows.
        queue['Localities'] = [r for r in queue['Localities'] if not r['Id'].startswith('gapcov-')]
        policy['Sites'] = [r for r in policy['Sites'] if not r['Id'].startswith('gapcov-')]
        stories['Sites'] = [r for r in stories['Sites'] if not r['Id'].startswith('gapcov-')]
        stories['Candidates'] = [r for r in stories['Candidates'] if not r['Id'].startswith('gapcov-')]
        for row in queue['Localities']:
            row['SiteIds'] = [s for s in row['SiteIds'] if not s.startswith('gapcov-')]
        rows, pins = stock(args.stock_mission)
        manifest = policy['HC43']
        if len(manifest['Localities']) != 88 or len(manifest['ResidentialClusters']) != 64:
            raise ValueError('expected all 88 locality identities and 64 residential proxies')
        extras, extra_pins = supplemental_anchors(args.stock_mission)
        pins.update(extra_pins)
        regions = derive(rows, pins, manifest['Localities'], manifest['ResidentialClusters'], policy, queue, stories, extras)
        regions['ExistingContent'] = map_existing(root, manifest['Localities'])
        manifest['Regions'] = regions
        manifest['State'] = 'source_resolved_runtime_pending'
        manifest['SelectionPolicy'] = 'HC-18 retained cursor and existing work/actor caps; all named, residential and atlas rows remain eligible over time. Native route, access and sight qualification remains authoritative.'
        manifest['RangeBasis'] = 'Existing ResidentialLinkMeters defines offline stock components only; label partition and source origins never prove access, terrain or coverage observations.'
        manifest['Identity'] = '88 named locality identities and 64 exact stock residential components; supplemental atlas/cluster queue IDs are finite scheduling identities, not accepted settlements.'
        manifest['Sources']['MapGroupPosSha256'] = pins['mapgrouppos.xml']
        manifest['Sources']['MapGroupProtoSha256'] = pins['mapgroupproto.xml']
        if bool(args.livonia_mission) != bool(args.livonia_world_pbo):
            raise ValueError('supply both Livonia inputs')
        if args.livonia_mission:
            labels, world_pin = livonia_labels(args.livonia_world_pbo)
            extra_rows, extra_pins = stock(args.livonia_mission)
            extra_policy = deepcopy(policy)
            extra_policy['WorldName'] = 'enoch'
            extra_policy['Sites'] = []
            # Patrol template remains the existing Chernarus tuning, not new limits.
            extra_policy['Sites'].append(deepcopy(policy['Sites'][0]))
            extra_queue = dict(WorldName='enoch', Localities=[dict(Id=l['Id'], Island=False, Source=l['Source'], SiteIds=[]) for l in labels])
            extra_story = dict(Sites=[], Candidates=[])
            extra_anchors, anchor_pins = supplemental_anchors(args.livonia_mission)
            extra_pins.update(anchor_pins)
            extra = derive(extra_rows, extra_pins, labels, [], extra_policy, extra_queue, extra_story, extra_anchors)
            extra_policy['Sites'] = extra_policy['Sites'][1:]
            extra.update(WorldName='enoch', WorldConfigSha256=world_pin, Localities=labels,
                Queue=extra_queue, Sites=extra_policy['Sites'], StorySites=extra_story,
                Activation='Alternate-world source catalog only; never load into a chernarusplus mission')
            manifest['AdditionalWorlds'] = [extra]
        for catalog in (queue['Localities'], policy['Sites'], stories['Sites'], stories['Candidates']):
            ids = [row['Id'] for row in catalog]
            if len(ids) != len(set(ids)):
                raise ValueError('duplicate derived catalog identity')
        policy_ids = {site['Id'] for site in policy['Sites']}
        for queued in queue['Localities']:
            if not queued['SiteIds'] or len(queued['SiteIds']) > 8 or not set(queued['SiteIds']) <= policy_ids:
                raise ValueError('unresolved or excessive locality site references: ' + queued['Id'])
        covered = sorted({s['LocalityId'] for s in stories['Sites']})
        if set(covered) != {row['Id'] for row in manifest['Localities']}:
            raise ValueError('unresolved named story locality')
        stories['Coverage'].update(CandidateLocalityIds=covered, PendingLocalityIds=[],
            PendingResidentialReason='All 64 memberships source-resolved; native layout and access acceptance pending.',
            Refusal='HC42_KIT_SITE_SURVEY_PENDING')
        stories['Sources']['LocalityQueueSha256'] = digest(encoded(queue))
        stories['Sources']['LocalityContentSha256'] = digest(encoded(policy))
        result = dict(Localities=len(manifest['Localities']), ResidentialClusters=len(manifest['ResidentialClusters']),
                      AtlasZones=len(regions['ZoneAtlas']), AISites=len(policy['Sites']),
                      QueueRows=len(queue['Localities']), StorySites=len(stories['Sites']), Gaps=regions['Gaps'], Runtime='PENDING')
        outputs = [encoded(value) for value in (queue, policy, stories)]
        if any(len(raw) > MAX_CATALOG_BYTES for raw in outputs) or len(queue['Localities']) > 1024 or len(policy['Sites']) > 1024:
            raise ValueError('catalog exceeds existing native read/cardinality budgets: bytes=' + str([len(raw) for raw in outputs]) + ' rows=' + str(result))
        result['Bytes'] = [len(raw) for raw in outputs]
        if args.write:
            for path, raw in zip(paths, outputs):
                path.write_bytes(raw)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, KeyError, StopIteration, ET.ParseError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
