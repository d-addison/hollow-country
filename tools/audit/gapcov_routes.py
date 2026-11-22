"""Source-pinned route proposals, never native traversal receipts.

Read installed Expansion v4 roads without copying dependency geometry. Format:
.banso-writer/xref/ai/4_World/DayZExpansion_AI/Classes/Roads/
eAIRoadNetwork.c:684-730 and eAIRoadNode.c:281-319. No engine API calls.
Existing HCXAICaravanRoads remains the runtime graph owner; this tool is offline.
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
import math
from pathlib import Path


MISSION = Path('mission/hollow-country')
# HCXAISiteRules.c:10; fail before authoring a catalog the runtime cannot load.
MAX_CATALOG_ROWS = 1024
CATALOG_PAGE_BYTES = 4096
# Reserve the exact envelope (including identity and newline), then pack whole
# rows against the audited row bound. Refuse growth rather than oversize a read.
CATALOG_ROW_BYTES = 675
CATALOG_PAGE_OVERHEAD = len((json.dumps(
    {'schema': 1, 'kind': 'gapcov-road-page', 'routes': [],
     'identity_sha256': '0' * 64}, separators=(',', ':')) + '\n').encode())
CATALOG_PAGE_ROWS = (CATALOG_PAGE_BYTES - CATALOG_PAGE_OVERHEAD) // (CATALOG_ROW_BYTES + 1)
CATALOG_INDEX_BYTES = 32768
CATALOG_INDEX = 'travel/gapcov-roads/index.json'


def page_paths(root):
    localities = root / MISSION / 'ai/localities.json'
    count = len(json.loads(localities.read_bytes())['Localities']) if localities.is_file() else 0
    return tuple('travel/gapcov-roads/page-%03d.json' % index
                 for index in range((count + CATALOG_PAGE_ROWS - 1) // CATALOG_PAGE_ROWS))

OUTPUTS = tuple(str(MISSION / name) for name in (
    'travel/route-surveys.json', 'ai/picker-routes.json', 'ai/caravans.json',
    'infected/route-surveys.json', CATALOG_INDEX,
    *page_paths(Path(__file__).resolve().parents[2])))
ROAD_VIRTUAL_PATH = 'DayZExpansion/AI/Scripts/Data/Roads/ChernarusPlus.roads'


def pin(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def load_roads(path, limits):
    """Strict bounded reader matching the existing runtime provider's v4 header."""
    with path.open(encoding='utf-8') as stream:
        def line():
            value = stream.readline(98)
            if not value or len(value.rstrip('\r\n')) > 96 or not value.endswith('\n'):
                raise ValueError('road line missing, oversized or unterminated')
            return value.strip()

        version, width, height, count = (int(line()) for _ in range(4))
        if (version, width, height) != (4, limits['RoadMapWidth'], limits['RoadMapHeight']):
            raise ValueError('road header does not match caravan configuration')
        if not 1 <= count <= limits['MaxRoadNodes']:
            raise ValueError('road node count exceeds configured cap')
        positions, links = [], []
        for index in range(count):
            if int(line()) != index:
                raise ValueError('road indices must be contiguous')
            position = tuple(float(part) for part in line().split())
            if len(position) != 3 or not all(math.isfinite(part) for part in position):
                raise ValueError('road position invalid')
            int(line())  # provider flags, not a native passability verdict
            degree = int(line())
            if not 0 <= degree <= limits['MaxRoadDegree']:
                raise ValueError('road degree exceeds configured cap')
            neighbours = [int(line()) for _ in range(degree)]
            if any(target < 0 or target >= count for target in neighbours):
                raise ValueError('road link outside graph')
            positions.append(position)
            links.append(neighbours)
        if stream.read().strip():
            raise ValueError('unexpected trailing road data')
    return positions, links


def components(links):
    """Weak components for inventory; proposals separately require reciprocal edges."""
    neighbours = [set(row) for row in links]
    for origin, targets in enumerate(links):
        for target in targets:
            neighbours[target].add(origin)
    membership = [-1] * len(links)
    rows = []
    for seed in range(len(links)):
        if membership[seed] != -1:
            continue
        component_id = len(rows)
        membership[seed] = component_id
        frontier = deque([seed])
        count = 0
        while frontier:
            node = frontier.popleft()
            count += 1
            for target in sorted(neighbours[node]):
                if membership[target] == -1:
                    membership[target] = component_id
                    frontier.append(target)
        rows.append({'id': component_id, 'first_node': seed, 'nodes': count})
    return membership, rows


def candidate_path(start, positions, links, limits):
    """Bounded retained BFS over real reciprocal edges, never straight-line shortcuts."""
    paths = {start: ([start], 0.0)}
    frontier = deque([start])
    while frontier and len(paths) < limits['search_nodes']:
        node = frontier.popleft()
        path, length = paths[node]
        if len(path) >= limits['waypoints']:
            continue
        for target in sorted(links[node]):
            if target in paths or node not in links[target]:
                continue
            segment = math.dist(positions[node], positions[target])
            if segment <= 0 or segment > limits['segment_metres'] or length + segment > limits['journey_metres']:
                continue
            paths[target] = (path + [target], length + segment)
            frontier.append(target)
            if len(paths) >= limits['search_nodes']:
                break
    path, length = max(paths.values(), key=lambda row: (row[1], len(row[0]), -row[0][-1]))
    return path, length


def locality_anchor(locality, sites):
    """Mirror HCXAISiteDirector's committed site binding, without ground sampling.

    HCXAISites.c:750-766 removes unknown SiteIds; :1080-1098 selects in
    SiteIds order (initial rotation cursor zero); :832-836 HCSiteAnchor uses
    HousePosition for holdouts and Waypoints[0] otherwise. gapcode_routes_sites.c:
    99-102 likewise uses the source site's first waypoint for road approach.
    No source-name heuristic or nearby-house proxy can replace this binding.
    """
    for site_id in locality['SiteIds']:
        site = sites.get(site_id)
        if site is None:
            continue
        anchor = (site.get('HousePosition') if site['Kind'] == 'holdout'
                  else next(iter(site.get('Waypoints', [])), None))
        # An unresolved first bound site must remain pending, not silently move
        # the locality to a different site's anchor.
        if anchor is None:
            return None
        if len(anchor) != 3 or not all(math.isfinite(part) for part in anchor):
            raise ValueError('invalid committed site anchor')
        return anchor
    return None


def build(root, roads):
    mission = root / MISSION
    caravan_path = mission / 'ai/caravans.json'
    picker_path = mission / 'ai/picker-routes.json'
    infected_path = mission / 'infected/route-surveys.json'
    locality_path = mission / 'ai/localities.json'
    sites_path = mission / 'ai/sites.json'
    caravan = json.loads(caravan_path.read_text())
    picker = json.loads(picker_path.read_text())
    infected = json.loads(infected_path.read_text())
    localities = json.loads(locality_path.read_text())['Localities']
    sites = {row['Id']: row for row in json.loads(sites_path.read_text())['Sites']}
    ids = [row['Id'] for row in localities]
    if not 1 <= len(ids) <= MAX_CATALOG_ROWS or len(set(ids)) != len(ids):
        raise ValueError('duplicate locality ID or catalog row cap exceeded')
    limits = {
        'waypoints': picker['MaxWaypoints'],
        'segment_metres': min(picker['MaxLegMeters'], infected['Defaults']['NativeSegmentMetres']),
        'journey_metres': caravan['MaxJourneyMeters'],
        'approach_metres': caravan['MaxApproachMeters'],
        'search_nodes': caravan['MaxRouteNodes'],
        'page_size': picker['MaxRoutes'],
    }
    positions, links = load_roads(roads, caravan)
    membership, inventory = components(links)
    proposals = []
    for locality in localities:
        key = locality['Id']
        anchor = locality_anchor(locality, sites)
        if anchor is None:
            row = {
                'id': 'gapcov-road-' + key, 'locality_id': key,
                'anchor_source': locality['Source'], 'island': locality['Island'],
                'component': -1, 'road_node_ids': [], 'length_metres': 0,
                'anchor_gap_metres': 0, 'connected_both_directions': False,
                'anchor_approach': 'pending-native',
                'island_access': 'pending-island-locality-and-landing-survey' if locality['Island'] else 'not-applicable',
                'status': 'anchor-runtime-resolved',
            }
            row['route_sha256'] = digest(row)
            proposals.append(row)
            continue
        start = min(range(len(positions)), key=lambda node: (
            (positions[node][0] - anchor[0]) ** 2 + (positions[node][2] - anchor[2]) ** 2, node))
        path, length = candidate_path(start, positions, links, limits)
        gap = math.hypot(positions[start][0] - anchor[0], positions[start][2] - anchor[2])
        row = {
            'id': 'gapcov-road-' + key, 'locality_id': key,
            'anchor_source': locality['Source'], 'island': locality['Island'],
            'component': membership[start], 'road_node_ids': path,
            'length_metres': round(length, 3), 'anchor_gap_metres': round(gap, 3),
            'connected_both_directions': len(path) >= 2,
            'anchor_approach': 'pending-native' if gap <= limits['approach_metres'] else 'missing-local-approach',
            'island_access': 'pending-island-locality-and-landing-survey' if locality['Island'] else 'not-applicable',
            'status': 'authored-candidate-native-pending' if len(path) >= 2 else 'missing-connected-road-segment',
        }
        row['route_sha256'] = digest(row)
        proposals.append(row)
    return {
        'schema': 1, 'kind': 'gapcov-road-proposals', 'runtime_acceptance': 'PENDING',
        'enabled_by_default': True, 'operator_opt_out': 'EnableEncounters=false (pickers/caravans), EnableTravel=false (travel), Enabled=false (infected route document), EnableMigration=false (variety)',
        'sources': {'road_virtual_path': ROAD_VIRTUAL_PATH, 'road_sha256': pin(roads),
                    'localities_sha256': pin(locality_path), 'sites_sha256': pin(sites_path)},
        'limits': limits,
        'limit_sources': {'waypoints': 'picker.MaxWaypoints (same existing 2..8 node contract as infected)',
                         'segment_metres': 'min(picker.MaxLegMeters, infected.Defaults.NativeSegmentMetres)',
                         'journey_metres': 'caravans.MaxJourneyMeters', 'approach_metres': 'caravans.MaxApproachMeters',
                         'search_nodes': 'caravans.MaxRouteNodes', 'page_size': 'picker.MaxRoutes'},
        'graph': {'nodes': len(links), 'directed_edges': sum(map(len, links)),
                  'max_degree': max(map(len, links)), 'component_kind': 'weak',
                  'nonreciprocal_edges': sum(origin not in links[target] for origin, row in enumerate(links) for target in row),
                  'components': inventory},
        'policy': 'Node IDs reference installed dependency data; no dependency geometry is redistributed. Consecutive IDs have reciprocal adjacency; no loop closing edge is implied. Reverse the chain for return. Nearest road is a candidate only, never evidence of an anchor approach, island-local road, navmesh, driving or water access. Never bridge disconnected components, interpolate a shortcut, teleport, alter native movement or infer native qualification.',
        'runtime_integration': 'Catalog is authoring data, not consumed by current DTOs. Page into existing bounded owners only after source-pin resolution, actual site/party binding and native path qualification. Keep current Routes lists intact. Derive operational status from HCGetOperationalStatus/HCPublish; loaded catalog alone cannot establish readiness.',
        'routes': proposals,
    }


def receipt_schema():
    """Portable JSON Schema for private, mode-specific native receipts."""
    sha = {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}
    text = {'type': 'string', 'minLength': 1}
    verdict = {'enum': ['passed', 'refused', 'pending', 'not-applicable']}
    checks = ['navmesh', 'doors', 'obstacles', 'terrain', 'visibility', 'custody',
              'cleanup', 'restart', 'island-access', 'boat-depth', 'grounding', 'landing-access', 'shelter-access']
    properties = {key: sha for key in ['route_sha256', 'road_sha256', 'localities_sha256',
                  'sites_sha256', 'pbo_sha256', 'mission_sha256', 'settings_sha256',
                  'dependency_sha256', 'server_log_sha256']}
    properties.update({key: text for key in ['route_id', 'build', 'run_id']})
    properties.update({
        'schema': {'const': 1}, 'kind': {'const': 'gapcov-native-route-receipt'},
        'observed_at_utc': {'type': 'string', 'format': 'date-time', 'pattern': 'Z$'},
        'mode': {'enum': ['walking', 'driving', 'boat', 'shelter-access']},
        'direction': {'enum': ['outbound', 'return']},
        'verdict': {'enum': ['passed', 'refused', 'pending']},
        'observer_ids': {'type': 'array', 'uniqueItems': True, 'items': text},
        'checks': {'type': 'object', 'required': checks, 'additionalProperties': False,
                   'properties': {key: verdict for key in checks}},
        'refusals': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['road_node_id', 'world_position', 'reason', 'log_line'],
            'properties': {'road_node_id': {'type': 'integer', 'minimum': 0},
                           'world_position': {'type': 'array', 'minItems': 3, 'maxItems': 3,
                                              'items': {'type': 'number'}},
                           'reason': text, 'log_line': text}}},
    })
    return {
        '$schema': 'https://json-schema.org/draft/2020-12/schema',
        'type': 'object', 'additionalProperties': False,
        'required': list(properties), 'properties': properties,
        'allOf': [
            {'if': {'properties': {'verdict': {'const': 'passed'}}},
             'then': {'properties': {'checks': {'properties': {
                 key: {'const': 'passed'} for key in ['visibility', 'custody', 'cleanup', 'restart']}}}}},
            *[{'if': {'properties': {'verdict': {'const': 'passed'}, 'mode': {'const': mode}}},
               'then': {'properties': {'checks': {'properties': {
                   key: {'const': 'passed'} for key in required_checks}}}}}
              for mode, required_checks in [
                  ('walking', ['navmesh', 'doors', 'obstacles', 'terrain']),
                  ('driving', ['obstacles', 'terrain']),
                  ('boat', ['boat-depth', 'grounding', 'landing-access']),
                  ('shelter-access', ['shelter-access', 'doors', 'obstacles'])]],
            {'if': {'properties': {'verdict': {'const': 'passed'}}},
             'then': {'properties': {'refusals': {'maxItems': 0},
                       'checks': {'properties': {key: {'enum': ['passed', 'not-applicable']}
                                                for key in checks}}}}},
            {'if': {'properties': {'verdict': {'const': 'refused'}}},
             'then': {'properties': {'refusals': {'minItems': 1}}}},
            {'if': {'properties': {'checks': {'anyOf': [
                {'properties': {'visibility': {'const': 'passed'}}},
                {'properties': {'custody': {'const': 'passed'}}}]}}},
             'then': {'properties': {'observer_ids': {'minItems': 2}}}},
        ],
    }


def receipt_contract():
    """Recording contract; accepting a receipt does not change runtime admission."""
    return {
        'schema': 1, 'kind': 'gapcov-native-route-receipt',
        'json_schema': receipt_schema(),
        'required': ['schema', 'kind', 'route_id', 'route_sha256', 'road_sha256', 'localities_sha256',
                     'sites_sha256', 'build', 'pbo_sha256', 'mission_sha256', 'settings_sha256',
                     'dependency_sha256', 'run_id', 'observed_at_utc', 'server_log_sha256',
                     'mode', 'direction', 'verdict', 'observer_ids', 'checks', 'refusals'],
        'modes': ['walking', 'driving', 'boat', 'shelter-access'],
        'directions': ['outbound', 'return'], 'verdicts': ['passed', 'refused', 'pending'],
        'checks': ['navmesh', 'doors', 'obstacles', 'terrain', 'visibility', 'custody', 'cleanup', 'restart', 'island-access', 'boat-depth', 'grounding', 'landing-access', 'shelter-access'],
        'check_verdicts': ['passed', 'refused', 'pending', 'not-applicable'],
        'refusal_fields': ['road_node_id', 'world_position', 'reason', 'log_line'],
        'evidence_policy': 'Private receipt, exact-source hashes and server log. UTC ISO timestamp, unique run identity, both directions recorded separately. Two distinct client identities required for visibility/custody checks. Boat mode requires actual depth/grounding/landing observations; walking never accepts driving/boat/shelter access. Any pending/refused check prevents passed verdict. Native survey does not bypass live per-segment geometry, perception, observer veto, physical custody or bounded owners. No receipt is shipped or fabricated by the offline generator.',
    }


def catalog_outputs(root, catalog):
    """Return complete derived documents without mutating authored inputs."""
    outputs = {}
    mission = root / MISSION
    path = mission / 'travel/route-surveys.json'
    travel = json.loads(path.read_text())
    header = {key: value for key, value in catalog.items() if key != 'routes'}
    header['row_count'] = len(catalog['routes'])
    header['pages'] = []
    if any(len(json.dumps(row, separators=(',', ':'), allow_nan=False).encode()) > CATALOG_ROW_BYTES
           for row in catalog['routes']):
        raise ValueError('catalog row exceeds packing bound; revise row paging')
    for index, relative in enumerate(page_paths(root)):
        rows = catalog['routes'][index * CATALOG_PAGE_ROWS:(index + 1) * CATALOG_PAGE_ROWS]
        page = {'schema': 1, 'kind': 'gapcov-road-page', 'routes': rows}
        page['identity_sha256'] = digest(page)
        data = (json.dumps(page, separators=(',', ':'), allow_nan=False) + '\n').encode()
        if not rows or len(data) > CATALOG_PAGE_BYTES:
            raise ValueError('catalog page outside row/byte bounds')
        outputs[str(MISSION / relative)] = data
        header['pages'].append({'Path': '$mission:hollow-country/' + relative,
                                'Bytes': len(data), 'Sha256': hashlib.sha256(data).hexdigest(),
                                'IdentitySha256': page['identity_sha256'],
                                'Rows': len(rows)})
    header['identity_sha256'] = digest(header)
    header_data = (json.dumps(header, separators=(',', ':'), allow_nan=False) + '\n').encode()
    if len(header_data) > CATALOG_INDEX_BYTES:
        raise ValueError('catalog header outside byte bounds')
    outputs[str(MISSION / CATALOG_INDEX)] = header_data
    travel['gapcov_routes'] = {'catalog': CATALOG_INDEX, 'locality_candidates': header['row_count']}
    travel['gapcov_survey_receipt_contract'] = receipt_contract()
    outputs[str(path.relative_to(root))] = (json.dumps(travel, indent=2) + '\n').encode()
    reference = {
        'catalog': CATALOG_INDEX,
        'receipt_contract': 'travel/route-surveys.json#gapcov_survey_receipt_contract',
        'locality_candidates': len(catalog['routes']), 'runtime_acceptance': 'PENDING',
        'admission': 'Existing features remain default-on with their existing opt-outs. Candidate catalog needs bounded runtime paging; current active Routes are unchanged. No native survey accepted.',
    }
    for relative in ['ai/picker-routes.json', 'ai/caravans.json', 'infected/route-surveys.json']:
        target = mission / relative
        document = json.loads(target.read_text())
        document['gapcov_routes'] = reference
        if relative == 'ai/caravans.json':
            document['gapcov_graph_source'] = catalog['sources']
            document['gapcov_graph_counts'] = {key: value for key, value in catalog['graph'].items() if key != 'components'}
        if relative == 'infected/route-surveys.json':
            document['survey_contract']['evidence'] = 'Surveyed=true is the legacy authored-source binding flag, not a native verdict. Native evidence is a separate exact-source gapcov receipt; all runtime segment checks remain mandatory.'
        outputs[str(target.relative_to(root))] = (json.dumps(document, indent=2) + '\n').encode()
    return outputs


def write_catalog(root, catalog):
    for name, data in catalog_outputs(root, catalog).items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--roads', type=Path, required=True, help='read-only installed Expansion v4 road source')
    parser.add_argument('--write', action='store_true', help='write derived metadata to the four owned mission manifests')
    args = parser.parse_args()
    try:
        catalog = build(args.root, args.roads)
        if args.write:
            write_catalog(args.root, catalog)
            print('gapcov routes authored=%d connected=%d components=%d runtime=PENDING' % (
                len(catalog['routes']), sum(row['connected_both_directions'] for row in catalog['routes']),
                len(catalog['graph']['components'])))
        else:
            print(json.dumps(catalog, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, 'gapcov routes: %s\n' % error)


if __name__ == '__main__':
    main()
