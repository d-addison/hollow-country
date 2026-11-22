"""Deterministic offline route integrity manifest and Expansion v4 CSR road graph.

Node i has XYZ at Positions[3*i:3*i+3], Flags[i], and directed neighbours
Edges[Offsets[i]:Offsets[i+1]]. IDs, flags, edge order and duplicates are preserved.
Neither output establishes native traversal or changes runtime admission (Wave 2).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import tempfile
from pathlib import Path, PurePosixPath

from tools.audit import gapcov_routes

ROOT = Path(__file__).resolve().parents[2]
WORKSHOP = Path('/mnt/g/SteamLibrary/steamapps/workshop/content/221100')
PINS = 'mission/hollow-country/travel/gapcode_routes_source-pages.json'
ROAD_PATH = 'DayZExpansion/AI/Scripts/Data/Roads/ChernarusPlus.roads'
OUTPUTS = ('mission/hollow-country/travel/routes-manifest.json',
           'mission/hollow-country/ai/road-graph.compact.json', *gapcov_routes.OUTPUTS)
MAX_SOURCE_BYTES = 4 * 1024 * 1024
MANIFEST_ROOT_BYTES = 6144
MANIFEST_PAGE_BYTES = 4096
MANIFEST_HASHES_PER_PAGE = 59
MANIFEST_CATALOG_PINS_PER_PAGE = 15


def manifest_page_paths(root=ROOT):
    pins = json.loads((root / PINS).read_bytes())
    count = 0
    for row in pins['Files']:
        if row['Path'] == ROAD_PATH:
            count += len(row['Pages'])
        else:
            name = row['Path'].replace('$mission:', 'mission/', 1)
            size = (root / name).stat().st_size
            count += (size + pins['ChunkBytes'] - 1) // pins['ChunkBytes']
    return tuple('mission/hollow-country/travel/routes-manifest-%03d.json' % i
                 for i in range(max(1, (len(gapcov_routes.page_paths(root)) + MANIFEST_CATALOG_PINS_PER_PAGE - 1)
                                    // MANIFEST_CATALOG_PINS_PER_PAGE)
                                + (count + MANIFEST_HASHES_PER_PAGE - 1) // MANIFEST_HASHES_PER_PAGE))


OUTPUTS = (*OUTPUTS, *manifest_page_paths())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encode(document):
    return (json.dumps(document, separators=(',', ':'), allow_nan=False) + '\n').encode()


def road_bytes(root=ROOT, workshop=WORKSHOP, roads=None):
    """Read only the installed member; never extract or copy dependency code."""
    if roads is not None:
        with Path(roads).open('rb') as stream:
            data = stream.read(MAX_SOURCE_BYTES + 1)
    else:
        from tools.audit import pbo_config
        mods = json.loads((root / 'tools/setup/workshop_mods.json').read_bytes())
        rows = mods if isinstance(mods, list) else mods['mods']
        provider = next(row for row in rows if row['name'] == 'Expansion-AI')
        candidates = [workshop / str(provider[key]) / 'addons/ai_scripts.pbo' for key in ('id', 'folder')]
        source = next((path for path in candidates if path.is_file()), None)
        if source is None:
            raise FileNotFoundError('installed Expansion AI road source unavailable')
        index = pbo_config.read_pbo_index(source)
        prefix = index['prefix'].replace('\\', '/').strip('/')
        member = ROAD_PATH[len(prefix) + 1:] if ROAD_PATH.lower().startswith(prefix.lower() + '/') else ''
        data = pbo_config.read_member(source, index, member, max_bytes=MAX_SOURCE_BYTES)
        if data is None:
            raise ValueError('installed Expansion AI road member missing')
    if not 0 < len(data) <= MAX_SOURCE_BYTES:
        raise ValueError('road source exceeds byte cap or is empty')
    return data


def compact_graph(data, limits):
    stream = io.StringIO(data.decode('utf-8'))

    def line():
        value = stream.readline(98)
        if not value.endswith('\n') or len(value.rstrip('\r\n')) > 96:
            raise ValueError('road line missing, oversized or unterminated')
        return value.strip()

    version, width, height, count = (int(line()) for _ in range(4))
    if (version, width, height) != (4, limits['RoadMapWidth'], limits['RoadMapHeight']):
        raise ValueError('road header does not match caravan configuration')
    if not 1 <= count <= limits['MaxRoadNodes']:
        raise ValueError('road node count exceeds configured cap')
    positions, flags, offsets, edges = [], [], [0], []
    for node in range(count):
        if int(line()) != node:
            raise ValueError('road indices must be contiguous')
        position = [float(part) for part in line().split()]
        if len(position) != 3 or not all(math.isfinite(part) for part in position):
            raise ValueError('road position invalid')
        positions.extend(position)
        flags.append(int(line()))
        degree = int(line())
        if not 0 <= degree <= limits['MaxRoadDegree']:
            raise ValueError('road degree exceeds configured cap')
        for _ in range(degree):
            target = int(line())
            if not 0 <= target < count:
                raise ValueError('road link outside graph')
            edges.append(target)
        offsets.append(len(edges))
    if stream.read().strip():
        raise ValueError('unexpected trailing road data')
    return {'SchemaVersion': 1, 'SourcePath': ROAD_PATH, 'SourceSha256': sha(data),
            'RoadVersion': version, 'Width': width, 'Height': height,
            'NodeCount': count, 'EdgeCount': len(edges), 'Positions': positions,
            'Flags': flags, 'Offsets': offsets, 'Edges': edges, 'Runtime': 'PENDING'}


def plan(root=ROOT, *, workshop=WORKSHOP, roads=None):
    """Verify pinned dependency bytes; compute fresh mission-source page identities."""
    pins_data = (root / PINS).read_bytes()
    pins = json.loads(pins_data)
    if pins['SchemaVersion'] != 1:
        raise ValueError('unsupported source-page schema')
    chunk, cap = pins['ChunkBytes'], pins['MaxSourceBytes']
    if type(chunk) is not int or type(cap) is not int or not 0 < chunk <= cap <= MAX_SOURCE_BYTES:
        raise ValueError('invalid source-page byte limits')
    road = road_bytes(root, workshop, roads)
    # Regenerate candidates before pinning their complete document bytes. Minimal
    # graph-only callers need no locality catalog; shipped missions always have it.
    derived = {}
    if (root / gapcov_routes.OUTPUTS[0]).is_file():
        with tempfile.TemporaryDirectory(prefix='hc-gapcov-roads-') as temporary:
            road_file = Path(temporary) / 'installed.roads'
            road_file.write_bytes(road)
            derived = gapcov_routes.catalog_outputs(root, gapcov_routes.build(root, road_file))
    files, seen, page_start = [], set(), 0
    for row in pins['Files']:
        path = row['Path']
        if path in seen:
            raise ValueError('duplicate route source')
        seen.add(path)
        if path == ROAD_PATH:
            data = road
        else:
            prefix = '$mission:hollow-country/'
            rel = path.removeprefix(prefix)
            parts = PurePosixPath(rel)
            if not path.startswith(prefix) or parts.is_absolute() or '..' in parts.parts or '\\' in rel:
                raise ValueError('unsupported route source path')
            target = root / 'mission/hollow-country' / parts
            if not target.resolve().is_relative_to((root / 'mission/hollow-country').resolve()):
                raise ValueError('route source escapes mission')
            if target.relative_to(root).as_posix() in derived:
                data = derived[target.relative_to(root).as_posix()]
            else:
                with target.open('rb') as stream:
                    data = stream.read(cap + 1)
        if not 0 < len(data) <= cap:
            raise ValueError('route source outside byte cap')
        pages = [sha(data[i:i + chunk]) for i in range(0, len(data), chunk)]
        if path == ROAD_PATH and (row['Bytes'] != len(data) or row['Sha256'] != sha(data) or row['Pages'] != pages):
            raise ValueError('route source byte/page digest differs: ' + path)
        files.append({'Path': path, 'Bytes': len(data), 'Sha256': sha(data),
                      'PageStart': page_start, 'PageCount': len(pages), 'Pages': pages})
        page_start += len(pages)
    if ROAD_PATH not in seen:
        raise ValueError('road source pin missing')
    limits = json.loads((root / 'mission/hollow-country/ai/caravans.json').read_bytes())
    graph = encode(compact_graph(road, limits))
    manifest = {'SchemaVersion': 1, 'SourcePagesSha256': sha(pins_data),
                'ChunkBytes': chunk, 'SourceCount': len(files), 'PageCount': page_start,
                'Files': files, 'RoadGraphPath': '$mission:hollow-country/ai/road-graph.compact.json',
                'RoadGraphSha256': sha(graph), 'Runtime': 'PENDING'}
    if derived:
        index_path = str(gapcov_routes.MISSION / gapcov_routes.CATALOG_INDEX)
        header = json.loads(derived[index_path])
        manifest['CatalogPath'] = '$mission:hollow-country/' + gapcov_routes.CATALOG_INDEX
        manifest['CatalogIdentitySha256'] = header['identity_sha256']
        manifest['CatalogSha256'] = sha(derived[index_path])
        manifest['CatalogPages'] = header['pages']
    # Keep graph fields/schema compatible with the shared compact-road reader.
    # The catalog pin list and source hash arrays each get bounded atomic parses.
    hashes = [value for row in files for value in row.pop('Pages')]
    catalog_pages = manifest.pop('CatalogPages', [])
    documents = []
    for start in range(0, max(1, len(catalog_pages)), MANIFEST_CATALOG_PINS_PER_PAGE):
        documents.append({'SchemaVersion': 1, 'PageStart': 0, 'Hashes': [],
                          'CatalogPageStart': start,
                          'CatalogPages': catalog_pages[start:start + MANIFEST_CATALOG_PINS_PER_PAGE]})
    for start in range(0, len(hashes), MANIFEST_HASHES_PER_PAGE):
        documents.append({'SchemaVersion': 1, 'PageStart': start,
                          'Hashes': hashes[start:start + MANIFEST_HASHES_PER_PAGE],
                          'CatalogPageStart': len(catalog_pages), 'CatalogPages': []})
    manifest['HashPageVersion'] = 1
    manifest['HashPages'] = []
    paged = {}
    for index, document in enumerate(documents):
        name = 'mission/hollow-country/travel/routes-manifest-%03d.json' % index
        data = encode(document)
        if len(data) > MANIFEST_PAGE_BYTES:
            raise ValueError('manifest hash page exceeds byte cap')
        paged[name] = data
        manifest['HashPages'].append({'Path': name.replace('mission/', '$mission:', 1),
                                      'Bytes': len(data), 'Sha256': sha(data)})
    header_data = encode(manifest)
    if len(header_data) > MANIFEST_ROOT_BYTES:
        raise ValueError('manifest header exceeds byte cap')
    return {OUTPUTS[0]: header_data, OUTPUTS[1]: graph, **derived, **paged}


def check(root=ROOT, **kwargs):
    return all((root / path).is_file() and (root / path).read_bytes() == data
               for path, data in plan(root, **kwargs).items())


def write(root=ROOT, **kwargs):
    outputs = plan(root, **kwargs)
    for name, data in outputs.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--write', action='store_true')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--workshop', type=Path, default=WORKSHOP)
    parser.add_argument('--roads', type=Path, help='installed uncompressed v4 road file override')
    args = parser.parse_args(argv)
    try:
        options = dict(workshop=args.workshop, roads=args.roads)
        if args.write:
            outputs = write(args.root, **options)
        elif args.check:
            if not check(args.root, **options):
                print('FAIL ai_route_precompute committed outputs differ')
                return 1
            outputs = plan(args.root, **options)
        else:
            outputs = plan(args.root, **options)
        for name, data in outputs.items():
            print(f'{name} bytes={len(data)} sha256={sha(data)}')
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        print('FAIL ai_route_precompute source validation or generation refused')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
