"""Derive map-wide habitat and shelter metadata from operator-owned stock inputs.

No engine calls, population edits, native flora control or runtime acceptance.
Run as a module with --mission <stock mission>; --write updates only the three
owned mission manifests. External vanilla XML is read, never redistributed.
AdditionalScenes are authored data awaiting the shared catalog integration;
Scenes retains its exact five-row runtime contract until that edit is applied.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import sys

from tools.audit.ecology_territories import audit, document

ROOT = Path(__file__).resolve().parents[2]
ECOLOGY = 'mission/hollow-country/ecology/habitat-overrides.json'
FORAGE = 'mission/hollow-country/forage/habitats.json'
SHELTERS = 'mission/hollow-country/travel/auditshelter_scenes.json'
SITES = 'mission/hollow-country/ai/sites.json'
LOCALITIES = 'mission/hollow-country/ai/localities.json'
CATALOG = 'mods/HollowCountry/scripts/4_World/Travel/HCShelterCatalog.c'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def distance(a, b):
    return math.hypot(a[0] - b[0], a[2] - b[2])


def position(text):
    result = [float(value) for value in text.split()]
    if len(result) != 3 or not all(math.isfinite(value) for value in result):
        raise ValueError('invalid stock position')
    return result


def derive(mission, repo=ROOT, censuses=()):
    hc43 = read_json(repo / SITES)['HC43']
    localities = hc43['Localities']
    ids = [row['Id'] for row in localities]
    expected = [row['Id'] for row in read_json(repo / LOCALITIES)['Localities']]
    if len(ids) != len(set(ids)):
        raise ValueError('locality identity join is incomplete')
    missing = sorted(set(ids) - set(expected))
    if missing:
        raise ValueError('locality identity join is incomplete: missing=' + missing[0])
    # gapcov_regions adds component rows without named-locality anchors. They
    # belong to the regional queue, not this nearest-named-locality partition.
    unexpected = sorted(key for key in set(expected) - set(ids)
                        if not key.startswith('gapcov-'))
    if unexpected:
        raise ValueError('locality identity join is incomplete: unexpected=' + unexpected[0])
    anchors = {row['Id']: row['Anchor'] for row in localities}
    for anchor in anchors.values():
        position(' '.join(str(value) for value in anchor))
    # Existing audit radius is only a reporting proxy, never a new spawn range.
    proxy = hc43['AuditRanges']['NamedContentProxyMeters']
    if not math.isfinite(proxy) or proxy <= 0:
        raise ValueError('invalid existing locality reporting radius')
    environment, environment_hash = document(mission, 'cfgenvironment.xml')
    bindings = environment.findall('./territories/territory')
    active = {node.get('usable') for row in bindings for node in row.findall('file')}
    files = sorted({row.get('path') for row in environment.findall('./territories/file')
                    if row.get('path') and 'zombie' not in row.get('path')
                    and Path(row.get('path')).stem in active})
    # The outputs describe stock data; an installed HC mission merges our own
    # territories and economy, which would shift every derived membership.
    installed = [path for path in files if not path.startswith('env/')]
    if installed or (mission / 'hollow-country').exists():
        raise ValueError('mission is not stock: installed_hc_mission='
                         + (installed[0] if installed else 'hollow-country'))
    wildlife = audit(mission, 'chernarusplus', [('animal', path) for path in files])
    sources = [{'path': 'cfgenvironment.xml', 'sha256': environment_hash}]
    sources += wildlife['sources']
    groups, group_hash = document(mission, 'mapgrouppos.xml')
    prototypes, proto_hash = document(mission, 'mapgroupproto.xml')
    sources += [{'path': 'mapgrouppos.xml', 'sha256': group_hash},
                {'path': 'mapgroupproto.xml', 'sha256': proto_hash}]
    zones = wildlife['zones']

    def membership(point):
        return [zone['id'] for zone in zones
                if math.hypot(point[0] - zone['x'], point[2] - zone['z']) <= zone['radius']]

    def nearest(point):
        return min(localities, key=lambda row: (distance(point, row['Anchor']), row['Id']))

    proto_usage = {row.get('name'): sorted({usage.get('name') for usage in row.findall('usage')})
                   for row in prototypes.findall('group')}
    stock = []
    hosts = {key: {} for key in ids}
    for index, group in enumerate(groups.findall('group')):
        point = position(group.get('pos', ''))
        owner = nearest(point)
        gap = distance(point, owner['Anchor'])
        record = dict(index=index, row=dict(group.attrib), point=point,
                      locality=owner['Id'], distance=round(gap, 3))
        stock.append(record)
        if gap <= proxy:
            for usage in proto_usage.get(group.get('name'), []):
                counts = hosts[owner['Id']]
                counts[usage] = counts.get(usage, 0) + 1
    scenes_doc = read_json(repo / SHELTERS)
    scenes = scenes_doc['Scenes']
    templates = {row['BuildingClass']: row for row in scenes}
    census_sources = []
    # Additional stock roof families use supplied native class measurements,
    # never a guessed clipping box or an unmeasured interior placement.
    for census_path in censuses:
        census = read_json(census_path)
        if census.get('door_phase_contract') != 2 or census.get('world', '').lower() != 'chernarusplus':
            raise ValueError('census world or measurement contract mismatch')
        census_sources.append(dict(path=census_path.parent.parent.parent.name + '/profiles/HCInteriorSampler/census.json',
                                   sha256=digest(census_path)))
        for measurement in census['placements']:
            kind = measurement['class']
            if kind not in ('Land_BusStop_Village2', 'Land_Barn_Wood2'):
                continue
            if not measurement.get('found') or measurement.get('box_source') != 'clipping':
                raise ValueError('roof class lacks measured clipping envelope')
            template = deepcopy(scenes[0])
            low, high = measurement['box_min'], measurement['box_max']
            if len(low) != 3 or len(high) != 3 or not all(math.isfinite(v) for v in low + high):
                raise ValueError('invalid measured roof bounds')
            if not all(a < b for a, b in zip(low, high)):
                raise ValueError('inverted measured roof bounds')
            # Retain the authored reference clearance, yard and slot policy.
            shift = low[0] - template['ClipMin'][0]
            for key in ('YardMin', 'YardMax'):
                template[key][0] += shift
            for slot in template['Slots']:
                slot[0] += shift
            for axis in (0, 2):
                template['AccessMin'][axis] += low[axis] - template['ClipMin'][axis]
                template['AccessMax'][axis] += high[axis] - template['ClipMax'][axis]
            template.update(BuildingClass=kind, ClipMin=low, ClipMax=high)
            template['Evidence'] = dict(class_source=census_sources[-1]['path'],
                                        class_sha256=census_sources[-1]['sha256'],
                                        sample_position=measurement['actual'], sample_is_candidate=False,
                                        path_tests=0, design=scenes[0]['Evidence']['design'])
            if kind in templates and templates[kind]['ClipMin'] != low:
                raise ValueError('conflicting roof class measurements')
            templates[kind] = template
    linked = {key: [] for key in ids}
    # Preserve catalog-declared membership separately from nearest-label proxies.
    catalog = (repo / CATALOG).read_text(encoding='utf-8')
    declared = dict(re.findall(r'HCCandidate\("([^"]+)", "[^"]+", "[^"]+", "[^"]+", "([^"]+)"', catalog))
    for scene in scenes:
        if declared.get(scene['Id']) not in linked:
            raise ValueError('existing shelter has no known catalog locality')
        scene['LocalityId'] = declared[scene['Id']]
        scene['MembershipBasis'] = 'existing_catalog_declaration_not_native_access'
        linked[scene['LocalityId']].append(scene['Id'])
    barns = []
    for name, pose in re.findall(r'Add\("([^"]+)", "([^"]+)"', catalog):
        point = position(pose)
        exact = [row for row in stock if row['row']['name'] == 'Land_Barn_Wood2' and row['point'] == point]
        if len(exact) != 1:
            raise ValueError('legacy shelter stock identity missing or ambiguous')
        row = exact[0]
        barns.append(dict(Name=name, Position=point, LocalityId=row['locality'],
                          DistanceToLabelM=row['distance'], StockRowIndex=row['index'],
                          MembershipBasis='nearest_label_proxy_not_boundary_or_access', RuntimeAcceptance='PENDING'))
    proposals = []
    existing_poses = {tuple(row['Position']) for row in scenes}
    for locality in sorted(localities, key=lambda row: row['Id']):
        # An island label cannot establish land connectivity for a nearby roof.
        # Keep islands explicit in the gap queue rather than assign mainland roofs.
        if locality.get('Island') or linked[locality['Id']]:
            continue
        options = [row for row in stock if row['locality'] == locality['Id']
                   and row['row']['name'] in templates
                   and tuple(row['point']) not in existing_poses]
        if not options:
            continue
        chosen = min(options, key=lambda row: (row['distance'], row['index']))
        proposal = deepcopy(templates[chosen['row']['name']])
        proposal.update(Id='gapcov-' + locality['Id'] + '-roof',
                        Name=locality['Id'] + ' exterior rest', Position=chosen['point'],
                        LocalityId=locality['Id'], MembershipBasis='nearest_label_proxy_not_boundary_or_access',
                        RuntimeAcceptance='PENDING')
        proposal['Evidence'].update(stock_row=chosen['row'], stock_row_index=chosen['index'],
                                    within_named_content_proxy=chosen['distance'] <= proxy,
                                    stock_sha256=group_hash, distance_to_label_m=chosen['distance'])
        proposals.append(proposal)
    proposal_links = {row['LocalityId']: row['Id'] for row in proposals}
    rows = []
    for locality in sorted(localities, key=lambda row: row['Id']):
        key = locality['Id']
        members = membership(locality['Anchor'])
        barn_links = [row['Name'] for row in barns if row['LocalityId'] == key]
        rows.append(dict(Id=key, Anchor=locality['Anchor'], Island=locality.get('Island', False),
                         WildlifeZoneIds=members,
                         WildlifeDisposition='retain_native' if members else 'label_gap_investigate_no_population_addition',
                         NativeCEHostUsageCounts=hosts[key], NativeFloraSurface='unknown_no_surface_census',
                         CatalogShelterIds=linked[key], LegacyBarnNames=barn_links,
                         AdditionalSceneId=proposal_links.get(key, ''),
                         ShelterGap=('island_local_geometry_and_access_pending' if locality.get('Island') else
                                     'measured_stock_roof_missing_in_nearest_label_partition') if not linked[key] and key not in proposal_links and not barn_links else '',
                         RuntimeAcceptance='PENDING'))
    clusters = []
    for cluster in hc43['ResidentialClusters']:
        owner = nearest(cluster['Anchor'])
        clusters.append(dict(Id=cluster['Id'], Anchor=cluster['Anchor'], LocalityId=owner['Id'],
                             DistanceToLabelM=round(distance(cluster['Anchor'], owner['Anchor']), 3),
                             WildlifeZoneIds=membership(cluster['Anchor']),
                             MembershipBasis='nearest_label_proxy_not_boundary_or_access', RuntimeAcceptance='PENDING'))
    if len({row['Id'] for row in clusters}) != len(clusters):
        raise ValueError('duplicate residential cluster')
    # A compact index preserves exact zone identity without copying vanilla XML.
    zone_index = {row['id']: index for index, row in enumerate(zones)}
    for row in rows + clusters:
        row['WildlifeZoneIndices'] = [zone_index[key] for key in row.pop('WildlifeZoneIds')]
    summary = dict(Localities=len(rows), ResidentialClusters=len(clusters), NativeHabitatFiles=len(files),
                   NativeZoneRows=len(zones), LabelPointsOutsideWildlife=sum(not row['WildlifeZoneIndices'] for row in rows),
                   ExistingRegionalScenes=len(scenes), LegacyBarns=len(barns), AdditionalExteriorScenes=len(proposals),
                   ShelterGapLocalities=sum(bool(row['ShelterGap']) for row in rows), ObservedShelters=0)
    coverage = dict(SchemaVersion=1, Trace='audit-cov worker E; #199; HC-48/HC-33/HC-59',
                    RuntimeAcceptance='PENDING', Summary=summary, Sources=sources, CensusSources=census_sources,
                    RepositorySources=[dict(path=path, sha256=digest(repo / path)) for path in (SITES, LOCALITIES, CATALOG)],
                    Policy='Native population and flora lifecycle unchanged. Circle membership tests label points only; nearest-label CE hosts, barns and clusters are spatial proxies. No locality boundaries, terrain access, food availability or occupancy inferred.',
                    NativeZoneIndexBasis='Zero-based ecology_territories.audit zones, files in NativeHabitatFiles order; includes every zone, never a second CE registration.',
                    NativeHabitatFiles=files, Localities=rows, ResidentialClusters=clusters)
    ecology = read_json(repo / ECOLOGY)
    ecology['GapcovMembership'] = dict(SchemaVersion=1, RuntimeAcceptance='PENDING', Summary=summary,
                                      Detail='forage/habitats.json#gapcov_membership',
                                      NativePopulationPolicy='retain_all_effective_native_zones_and_quotas_no_addition_from_label_gaps',
                                      NativeHabitatFiles=files,
                                      LocalityZoneCounts=[[row['Id'], len(row['WildlifeZoneIndices'])] for row in rows])
    forage = read_json(repo / FORAGE)
    forage['gapcov_membership'] = coverage
    # HCJsonFields.Every(Enabled, depth=3) scans every object at that
    # depth. Wrap non-scene row metadata so it cannot invalidate live scenes.
    scenes_doc['LegacyBarnMembership'] = dict(Rows=barns)
    scenes_doc['AdditionalScenes'] = proposals
    scenes_doc['GapcovIntegration'] = dict(
        RuntimeAcceptance='PENDING',
        State='authored_additional_scenes_waiting_shared_catalog_registration',
        ExistingGlobalOptOut='Enabled=false applies to both Scenes and AdditionalScenes after integration',
        OperatorOptOut='Enabled=false for regional scenes; each scene Enabled=false for individual opt-out; EnableTravel=false for all shelters',
        Policy='Scenes stays compatible with the five-row catalog. AdditionalScenes reuses those measured class envelopes, three empty exterior props, zero stock grants and full roof/access keepouts. Site collision, terrain, rain and all-player visibility remain runtime vetoes.',
        RequiredSharedEdit='Register these HCCandidate calls after the existing five in HCShelterCatalog.HCEnsureCandidates; merge AdditionalScenes after Scenes in HCLoadRegional BEFORE HCRegionalValid and HCJsonFields guards; add owned AdditionalScenes array to HCShelterRegionalConfig. Keep existing shape, identity, bounds, slot, sight and budget checks. Derive status through existing HCGetOperationalStatus.',
        CandidateCalls=[f'HCCandidate("{row["Id"]}", "{row["Name"]}", "{row["BuildingClass"]}", "' +
                        ' '.join(str(value) for value in row['Position']) + f'", "{row["LocalityId"]}", "map-wide", "exterior-rest", "runtime_access_clearance_pending");'
                        for row in proposals])
    return {ECOLOGY: ecology, FORAGE: forage, SHELTERS: scenes_doc}, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mission', type=Path, required=True)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--census', type=Path, action='append', default=[])
    args = parser.parse_args(argv)
    try:
        outputs, summary = derive(args.mission, censuses=args.census)
        encoded = {path: json.dumps(data, indent=2, allow_nan=False) + '\n' for path, data in outputs.items()}
        if len(encoded[ECOLOGY].encode('utf-8')) > outputs[ECOLOGY]['ManifestMaxBytes']:
            raise ValueError('ecology manifest byte budget exceeded')
        if args.write:
            for path, content in encoded.items():
                (ROOT / path).write_text(content, encoding='utf-8')
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('gapcov habitats refused: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(dict(summary, runtime='PENDING'), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
