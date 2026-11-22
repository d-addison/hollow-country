"""Write or check the route source pin file consumed by tools.package.ai_route_precompute.

Source of truth: the road source path and whole-file SHA-256 authored by
tools.audit.gapcov_routes into ai/caravans.json (gapcov_graph_source), which the
catalog index must repeat. Only the dependency road bytes carry a byte/page pin here;
a mission source row is a path declaration, because ai_route_precompute computes fresh
identities for authored mission files on every run. That keeps this file stable under
ordinary mission edits.

--check verifies the road bytes against the authored pin and that the committed pin
file equals the generated one. Standard library plus ai_route_precompute.road_bytes;
no network or engine invocation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

CARAVANS = 'ai/caravans.json'
CATALOG_INDEX = 'travel/gapcov-roads/index.json'
PINS = 'travel/gapcode_routes_source-pages.json'
MISSION_SOURCES = ('ai/sites.json', 'ai/localities.json', 'travel/route-surveys.json')
CHUNK_BYTES = 4096
MAX_SOURCE_BYTES = 4194304
PROVENANCE = ('SHA-256 pages only; no dependency geometry. Read-only installed Expansion v4 road source. '
              'Mission source rows declare paths only; their identities are computed fresh by '
              'ai_route_precompute. The road pin is the authored gapcov_graph_source in ai/caravans.json.')


def road_pin(mission: Path) -> dict:
    """The authored road pin, required to agree between caravans.json and the catalog index."""
    pin = json.loads((mission / CARAVANS).read_text())['gapcov_graph_source']
    catalog = json.loads((mission / CATALOG_INDEX).read_text())['sources']
    for key in ('road_virtual_path', 'road_sha256'):
        if pin[key] != catalog[key]:
            raise ValueError(f'{key} differs between {CARAVANS} and {CATALOG_INDEX}')
    return {'road_virtual_path': pin['road_virtual_path'], 'road_sha256': pin['road_sha256']}


def build_pins(root: Path, roads: Path) -> dict:
    mission = root / 'mission/hollow-country'
    pin = road_pin(mission)
    road_bytes = roads.read_bytes()
    if hashlib.sha256(road_bytes).hexdigest() != pin['road_sha256']:
        raise ValueError('installed road source differs from authored route source pin')
    if not 0 < len(road_bytes) <= MAX_SOURCE_BYTES:
        raise ValueError('road source outside runtime byte cap')
    files = [{
        'Path': pin['road_virtual_path'],
        'Bytes': len(road_bytes),
        'Sha256': pin['road_sha256'],
        'Pages': [hashlib.sha256(road_bytes[n:n + CHUNK_BYTES]).hexdigest()
                  for n in range(0, len(road_bytes), CHUNK_BYTES)],
    }]
    for name in MISSION_SOURCES:
        if not (mission / name).is_file():
            raise ValueError(f'mission route source missing: {name}')
        files.append({'Path': '$mission:hollow-country/' + name})
    return {'SchemaVersion': 1, 'ChunkBytes': CHUNK_BYTES, 'MaxSourceBytes': MAX_SOURCE_BYTES,
            'Files': files, 'Provenance': PROVENANCE, 'Runtime': 'PENDING'}


def encode(document: dict) -> str:
    return json.dumps(document, indent=2) + '\n'


def write_pins(root: Path, roads: Path) -> Path:
    target = root / 'mission/hollow-country' / PINS
    target.write_text(encode(build_pins(root, roads)))
    return target


def check_pins(root: Path, roads: Path) -> bool:
    target = root / 'mission/hollow-country' / PINS
    return target.is_file() and target.read_text() == encode(build_pins(root, roads))


def main(argv=None) -> int:
    from tools.package import ai_route_precompute
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--roads', type=Path, help='read-only installed Expansion v4 roads '
                        '(default: the installed Workshop member)')
    parser.add_argument('--check', action='store_true', help='verify the committed pin file, write nothing')
    args = parser.parse_args(argv)
    try:
        roads = args.roads
        if roads is None:
            import tempfile
            scratch = tempfile.TemporaryDirectory(prefix='hc-route-pins-')
            roads = Path(scratch.name) / 'installed.roads'
            roads.write_bytes(ai_route_precompute.road_bytes(args.root.resolve(), ai_route_precompute.WORKSHOP))
        if args.check:
            if not check_pins(args.root, roads):
                print('FAIL route source pins: committed pin file differs from the authored pins')
                return 1
            print('route source pins: committed pin file matches')
            return 0
        target = write_pins(args.root, roads)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f'route source pins: {error}\n')
    print(f'{target}: page pins authored; runtime=PENDING')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
