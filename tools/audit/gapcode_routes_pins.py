"""Build bounded runtime SHA-256 page pins, never dependency geometry/receipts.

Run after integrating changes to the mission sources. The road input must
match the authored catalog's existing whole-file SHA-256 before producing pins.
Standard library only; no network or engine invocation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def write_pins(root: Path, roads: Path) -> Path:
    mission = root / 'mission/hollow-country'
    travel = mission / 'travel/route-surveys.json'
    sources = json.loads(travel.read_text())['gapcov_routes']['sources']
    road_bytes = roads.read_bytes()
    if hashlib.sha256(road_bytes).hexdigest() != sources['road_sha256']:
        raise ValueError('installed road source differs from authored route source pin')
    chunk_bytes = 4096
    max_source_bytes = 4194304
    inputs = [
        (sources['road_virtual_path'], road_bytes),
        ('$mission:hollow-country/ai/sites.json', (mission / 'ai/sites.json').read_bytes()),
        ('$mission:hollow-country/ai/localities.json', (mission / 'ai/localities.json').read_bytes()),
        ('$mission:hollow-country/travel/route-surveys.json', travel.read_bytes()),
    ]
    files = []
    for virtual_path, content in inputs:
        if not 0 < len(content) <= max_source_bytes:
            raise ValueError(f'source outside runtime byte cap: {virtual_path}')
        files.append({
            'Path': virtual_path,
            'Bytes': len(content),
            'Sha256': hashlib.sha256(content).hexdigest(),
            'Pages': [hashlib.sha256(content[n:n + chunk_bytes]).hexdigest()
                      for n in range(0, len(content), chunk_bytes)],
        })
    document = {
        'SchemaVersion': 1, 'ChunkBytes': chunk_bytes,
        'MaxSourceBytes': max_source_bytes, 'Files': files,
        'Provenance': 'SHA-256 pages only; no dependency geometry. Read-only installed Expansion v4 road source. '
                      'Site/locality pins rebased to the expanded authored mission; original route authoring '
                      'hashes remain provenance, not a native receipt.',
        'Runtime': 'PENDING',
    }
    target = mission / 'travel/gapcode_routes_source-pages.json'
    target.write_text(json.dumps(document, indent=2) + '\n')
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--roads', type=Path, required=True, help='read-only installed Expansion v4 roads')
    args = parser.parse_args()
    try:
        target = write_pins(args.root, args.roads)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f'route source pins: {error}\n')
    print(f'{target}: page pins authored; runtime=PENDING')


if __name__ == '__main__':
    main()
