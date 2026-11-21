"""Generate admin-only map anchors from repository data and official stock CE.

Run from the repository root before packaging. No profile/installed server inputs.
Generation fetches the pinned upstream input in memory; only derived anchors ship.
The --check mode reuses its recorded SHA-256 and reads local repository inputs only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
# Official Bohemia source; explicit revision is recorded beside the derived data.
UPSTREAM = 'https://raw.githubusercontent.com/BohemiaInteractive/DayZ-Central-Economy/7bfc95cb9f6fb676311cef76be80050314b2cc16/dayzOffline.chernarusplus/cfgeventspawns.xml'

CATALOG = Path('mods/HollowCountry/scripts/4_World/Admin/HCAdminWorldCatalog.c')
JSON_INPUTS = (
    'mission/hollow-country/ai/sites.json',
    'mission/hollow-country/events/story-sites.json',
    'mission/hollow-country/leads/localities.json',
    'mission/hollow-country/travel/auditshelter_scenes.json',
)
# Bound every generated function's dispatch/literal body, including first entry.
PAGE_ROWS = 8
DISPATCH_PAGES = 8

CE_INPUTS = (
    'mission/hollow-country/ce/hc-eventspawns.xml',
    'mission/hollow-country/events/cache-eventspawns.xml',
    'mission/hollow-country/vehicles/vehexp-eventspawns.xml',
)


def local_inputs(root):
    """The same ordered inputs feed generation and the offline package check."""
    names = list(JSON_INPUTS)
    names += [path.relative_to(root).as_posix()
              for path in sorted((root / 'config/map-overlays/layers').glob('*.json'))]
    names += [name for name in CE_INPUTS if (root / name).exists()]
    return {name: (root / name).read_bytes() for name in names}


def inputs_digest(inputs, stock_sha256):
    digest = hashlib.sha256()
    # Names and lengths frame each contribution, including optional input presence.
    for name, data in inputs.items():
        digest.update(name.encode() + b'\0' + str(len(data)).encode() + b'\0' + data)
    digest.update(UPSTREAM.encode() + b'\0' + stock_sha256.encode())
    return digest.hexdigest()


def check(root=ROOT):
    """Refuse stale/missing provenance without fetching or reading stock CE."""
    refusal = 'stale admin world catalog; regenerate with python3 -B -m tools.package.admin_world_catalog'
    try:
        header = (root / CATALOG).read_text(encoding='utf-8').splitlines()[:4]
        source = [line.removeprefix('// Official CE source: ') for line in header
                  if line.startswith('// Official CE source: ')]
        stock = [line.removeprefix('// Stock CE sha256: ') for line in header
                 if line.startswith('// Stock CE sha256: ')]
        recorded = [line.removeprefix('// Inputs digest: ') for line in header
                    if line.startswith('// Inputs digest: ')]
        if (source != [UPSTREAM] or len(stock) != 1 or len(recorded) != 1
                or not re.fullmatch('[0-9a-f]{64}', stock[0])
                or not re.fullmatch('[0-9a-f]{64}', recorded[0])
                or inputs_digest(local_inputs(root), stock[0]) != recorded[0]):
            raise ValueError(refusal)
    except OSError as exc:
        raise ValueError(refusal) from exc


def generate(output=None):
    rows = []
    inputs = local_inputs(ROOT)

    def load(name):
        return json.loads(inputs[name])

    def add(layer, pos, label, detail):
        if len(pos) != 3 or not (0 <= pos[0] <= 15360 and 0 <= pos[2] <= 15360):
            raise ValueError('invalid catalog coordinate')
        rows.append((layer, pos, label, detail))

    for row in load('mission/hollow-country/ai/sites.json')['Sites']:
        add('ai-sites', (row.get('Waypoints') or [row['HousePosition']])[0], row['Id'], 'Authored AI site; faction=' + row['Faction'] + '; role=' + row['Kind'] + '; not live occupancy')
    for row in load('mission/hollow-country/events/story-sites.json')['Sites']:
        add('story-sites', row['Anchor'], row['Id'], 'Authored story candidate; not an active event')
    for row in load('mission/hollow-country/leads/localities.json')['Localities']:
        add('localities', row['Position'], row['Name'], 'Authored locality')
    shelters = load('mission/hollow-country/travel/auditshelter_scenes.json')
    for row in shelters['Scenes'] + shelters['AdditionalScenes']:
        add('shelter-sites', row['Position'], row['Name'], 'Authored shelter; native access/rain verification pending')
    for name in inputs:
        if not name.startswith('config/map-overlays/layers/'):
            continue
        data = load(name)
        layer = data['id'].rsplit('-v', 1)[0]
        for row in data.get('sites', []):
            add(layer, row['pos'], row['id'], 'Authored overlay: ' + row['composition'] + '; installation/placement not inferred')
        for index, row in enumerate(data.get('objects', [])):
            pos = row.get('pos')
            if pos:
                add(layer, pos, str(index), 'Authored object: ' + row.get('type', row.get('class', 'object')))
    # A pinned official-source derivation is reproducible without shipping a vanilla dump.
    with urllib.request.urlopen(UPSTREAM, timeout=45) as response:
        stock = response.read(4_000_000)
    stock_sha256 = hashlib.sha256(stock).hexdigest()
    digest = inputs_digest(inputs, stock_sha256)
    for event in ET.fromstring(stock).findall('event'):
        for pos in event.findall('pos'):
            add('vanilla-ce-spawns', [float(pos.attrib['x']), 0, float(pos.attrib['z'])], event.attrib['name'], 'Stock CE candidate; not a live event or vehicle')
    for name in CE_INPUTS:
        if name not in inputs:
            continue
        data = inputs[name]
        for event in ET.fromstring(data).findall('event'):
            for pos in event.findall('pos'):
                add('hc-ce-spawns', [float(pos.attrib['x']), 0, float(pos.attrib['z'])], event.attrib['name'], 'Packaged HC CE candidate; not live occupancy')
    if len(rows) > 8192:
        raise ValueError('catalog exceeds stream cap')
    version = int(digest[:7], 16)
    (output if output is not None else ROOT / CATALOG).write_text(render(rows, version, stock_sha256, digest))
    print(f'Generated {len(rows)} anchors; version={version}; stock_sha256={stock_sha256}')


def render(rows, version, stock_sha256, digest):
    """Small bounded dispatch bodies; no whole-catalog or 64-row function entry."""
    out = ['// Generated by tools.package.admin_world_catalog; derived anchors only, no raw stock dump.',
           '// Official CE source: ' + UPSTREAM,
           '// Stock CE sha256: ' + stock_sha256,
           '// Inputs digest: ' + digest,
           'class HCAdminWorldCatalog', '{', f'    static const int VERSION = {version};', f'    static const int COUNT = {len(rows)};',
           '    // One atomic row per call; caller owns the shared slice and retained cursor.',
           '    static void Emit(HCAdminWorldCapture capture, int index)', '    {',
           '        if (index < 0 || index >= COUNT) { return; }']
    pages = (len(rows) + PAGE_ROWS - 1) // PAGE_ROWS
    if pages:
        out.append(f'        Dispatch0_{pages}(capture, index, index / {PAGE_ROWS});')
    out += ['    }']

    def dispatch(first, end):
        out.extend([f'    static void Dispatch{first}_{end}(HCAdminWorldCapture capture, int index, int page)', '    {'])
        if end - first > DISPATCH_PAGES:
            middle = (first + end) // 2
            out.extend([f'        if (page < {middle}) {{ Dispatch{first}_{middle}(capture, index, page); }}',
                        f'        else {{ Dispatch{middle}_{end}(capture, index, page); }}', '    }'])
            dispatch(first, middle)
            dispatch(middle, end)
        else:
            out.extend(['        switch (page)', '        {'])
            for page in range(first, end):
                out.append(f'            case {page}: Page{page}(capture, index); break;')
            out.extend(['        }', '    }'])

    if pages:
        dispatch(0, pages)
    for page in range(pages):
        out += [f'    static void Page{page}(HCAdminWorldCapture capture, int index)', '    {', '        switch (index)', '        {']
        for index in range(page * PAGE_ROWS, min(len(rows), (page + 1) * PAGE_ROWS)):
            layer, pos, label, detail = rows[index]
            vals = ', '.join(json.dumps(s, ensure_ascii=True) for s in (label, detail))
            out.append(f'            case {index}: capture.Put({json.dumps(layer)}, Vector({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f}), {vals}); break;')
        out += ['        }', '    }']
    out += ['}', '']
    return '\n'.join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--check', action='store_true', help='check local inputs offline; do not regenerate')
    parser.add_argument('--out', type=Path, help='generated catalogue destination')
    args = parser.parse_args(argv)
    try:
        if args.check:
            check()
            print('Admin world catalog inputs are current (offline check)')
        else:
            generate(args.out)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
