"""Audit explicitly supplied native mission territory metadata, never live AI.

Stdlib only. No gameplay edits or eligibility/route/population acceptance.
Example: python3 -B -m tools.audit.ecology_territories --mission <mission>
  --world chernarusplus --animal-territory env/red_deer_territories.xml
  --infected-territory env/zombie_territories.xml
"""
import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys
import xml.etree.ElementTree as ET

MAX_BYTES = 4 * 1024 * 1024
MAX_ZONES = 10000
MAX_FILES = 32


def document(root, relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or '\\' in relative:
        raise ValueError('unsafe mission path')
    target = root / path
    if any((root.joinpath(*path.parts[:n])).is_symlink() for n in range(1, len(path.parts)+1)):
        raise ValueError('symlink mission path')
    if not target.resolve().is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError('missing or external mission file')
    with target.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError('mission XML outside byte budget')
    # Decode first so UTF-16 cannot hide an entity/doctype declaration.
    if b'\x00' in raw or re.search(br'<!\s*(?:DOCTYPE|ENTITY)', raw, re.I):
        raise ValueError('XML declarations not supported')
    try:
        return ET.fromstring(raw), hashlib.sha256(raw).hexdigest()
    except ET.ParseError as exc:
        raise ValueError('malformed mission XML') from exc


def integer(text):
    if not re.fullmatch(r'[0-9]{1,9}', text or ''):
        raise ValueError('invalid nonnegative native count')
    return int(text)


def coordinate(text):
    try:
        value = float(text)
    except (ValueError, TypeError) as exc:
        raise ValueError('invalid territory coordinate') from exc
    if not math.isfinite(value) or abs(value) > 3.4028234663852886e38:
        raise ValueError('nonfinite territory coordinate')
    return value


def audit(mission, world, territories):
    root = Path(mission)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,96}', world):
        raise ValueError('invalid world key')
    if not territories or len(territories) > MAX_FILES:
        raise ValueError('territory file budget exceeded or empty')
    variables, digest = document(root, 'db/globals.xml')
    if variables.tag != 'variables':
        raise ValueError('invalid globals root')
    maxima = {'animal': None, 'infected': None}
    names = {'AnimalMaxCount': 'animal', 'ZombieMaxCount': 'infected'}
    seen = set()
    for var in variables:
        key = var.get('name')
        if key in names:
            if key in seen:
                raise ValueError('duplicate population global')
            seen.add(key)
            if var.get('type') != '0':
                raise ValueError('population global is not an integer')
            maxima[names[key]] = integer(var.get('value'))
    sources = [{'path': 'db/globals.xml', 'sha256': digest}]
    seen_files = set(); rows = []
    for population, path in territories:
        if population not in maxima or path in seen_files:
            raise ValueError('invalid population or duplicate territory input')
        seen_files.add(path)
        tree, digest = document(root, path)
        if tree.tag != 'territory-type':
            raise ValueError('invalid territory root')
        sources.append({'path': path, 'sha256': digest})
        if any(child.tag != 'territory' for child in tree):
            raise ValueError('unrecognized territory structure')
        for territory_index, territory in enumerate(tree):
            for zone_index, zone in enumerate(territory):
                if zone.tag != 'zone' or len(rows) >= MAX_ZONES:
                    raise ValueError('unknown zone or zone budget exceeded')
                name = zone.get('name', '')
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', name):
                    raise ValueError('invalid zone name')
                values = {key: integer(zone.get(key)) for key in ('smin', 'smax', 'dmin', 'dmax')}
                if values['smin'] > values['smax'] or values['dmin'] > values['dmax']:
                    raise ValueError('inverted territory density range')
                x, z, radius = (coordinate(zone.get(key)) for key in ('x', 'z', 'r'))
                if radius <= 0:
                    raise ValueError('invalid territory radius')
                # Zero animal dmax accompanies Graze/Water/Rest metadata in the
                # installed mission. It cannot establish zero biological capacity.
                maximum = maxima[population]
                ceiling = None
                if population == 'infected' and maximum is not None and values['dmax'] > 0:
                    ceiling = min(maximum, values['dmax'])
                identity = f'{world}:{path}:{territory_index}:{zone_index}'
                rows.append(dict(id=hashlib.sha256(identity.encode()).hexdigest(), population=population,
                                 name=name, x=x, z=z, radius=radius, **values,
                                 capacity_ceiling=ceiling))
    return dict(schema_version=1, world=world, sources=sources, globals=maxima, zones=rows,
                live_occupancy_known=False, runtime_acceptance='PENDING',
                exclusions=['territory metadata is not observed food or water',
                            'no native territory occupancy query exposed',
                            'zero animal density does not establish carrying capacity',
                            'no route survey, sensory eligibility, feeding or drinking proven'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mission', type=Path, required=True)
    parser.add_argument('--world', required=True)
    parser.add_argument('--animal-territory', action='append', default=[])
    parser.add_argument('--infected-territory', action='append', default=[])
    args = parser.parse_args(argv)
    entries = [('animal', path) for path in args.animal_territory]
    entries += [('infected', path) for path in args.infected_territory]
    try:
        result = audit(args.mission, args.world, entries)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
