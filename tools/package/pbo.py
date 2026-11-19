"""Deterministic stored PBO and private development handoff. No game assets.

This intentionally accepts a small, strict subset of PBO (Vers prefix + method 0).
SHA-1 is the PBO trailer checksum, NOT an addon signature or authenticity proof.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import zipfile

PREFIX = 'HollowCountry'
# The optional server-side Expansion AI adapter is built under its own prefix, only on request.
PREFIXES = (PREFIX, 'HollowCountryExpansionAI', 'HollowCountryAnims')
WORDS = struct.Struct('<5I')
VERS = 0x56657273
MAX_BYTES = 64 * 1024 * 1024
MAX_ENTRIES = 8192
RESERVED = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{p}{i}' for p in ('COM', 'LPT') for i in range(1, 10)}
MISSION_FILES = {'auditleaves_settings.json', 'README.md', 'INSTALL_AND_ROLLBACK.md', 'operator/settings.json', 'ce/types.xml', 'cfgeconomycore.append.xml',
                 'ce/events.xml', 'ce/travel-spawnabletypes.xml',
                 # HC-23 helmet light review manifest (fail-closed; qualification stays false).
                 'lights/helmet-mounts.json',
                 # HC-30 authored recovery dispositions; native qualification remains pending.
                 'crafting/recovery-dispositions.json',
                 # HC-15 wildlife observation budgets (read by HCWildlifeObservation.HCStart).
                 'ecology/species.json', 'ecology/HCWildlife-providers.json',
                 # V2 optional-pack overlay policy (the packs themselves are never shipped or copied).
                 'optional/overlay-policy.json',
                 # W6 #60 authored survey inputs only; generated trigger instances never ship.
                 'cellars/classes.json', 'cellars/README.md',
                 # V2 scene chains catalog, its native/class provenance and the operator handoff.
                 'events/README.md', 'events/scene-chains.json', 'events/scene-provenance.json',
                 'economy-profiles/baseline.json', 'economy-profiles/contextual-pilot.json',
                 'economy-profiles/diagnostic.json', 'gameplay-profiles/hollow-country-v1.json',
                 'gear/hardscrabble.json',
                 # Interiors data pack (W1.1): one evidenced house; measured layouts and rooms stay pending.
                 'interiors/pack.json', 'interiors/pack-profile.json', 'interiors/interiors.json',
                 'interiors/evidence/house-candidates.json',
                 # Optional Expansion AI patrol contract and examples; inert without the addon and its marker.
                 'ai/README.md', 'ai/AISettings.merge.json', 'ai/event-sites.contract.json', 'ai/patrols.example.json',
                 'ai/AIPatrolSettings.override.json',
                 'ai/localities.json', 'ai/sites.json', 'ai/picker-routes.json', 'ai/loadouts/HollowCountry_Patrol.json', 'ai/loadouts/HollowCountry_Scavenger.json',
                 'ai/loadouts/HollowCountry_Holdout.json',
                 # HC-43 finite Raider/Traveller loadouts (not yet mapped by HCXAISites).
                 'ai/loadouts/HollowCountry_Raider.json', 'ai/loadouts/HollowCountry_Traveller.json',
                 # HC-35 one reciprocal AI-to-AI trade recipe (inert until the provider is qualified).
                 'ai/trade-recipes.json',
                 # HC-42 regional story-kit site candidates (authored; indexed-site consumer pending).
                 'events/story-sites.json',
                 # HC-57 tenement CE input subset (offline-selected) and the office survey (pending, refused).
                 'ce-coverage/apartments.json', 'ce-coverage/municipal-office.json',
                 # HC-36 caravan corridor (unsurveyed, refused), HC-49 carcass sites (authored refused),
                 # HC-39 raid and foot-column profiles (admission refused until provider evidence).
                 'ai/caravans.json', 'ai/car-repair.json', 'ecology/carcass-sites.json', 'events/raids.json',
                 # HC-40 transit profiles (admission refused until route/clearance evidence).
                 'events/transit-situations.json',
                 # Loot boost: multiplier setting, building-family policy and the model-derived points overlay
                 # (stock-frame offsets only, generated offline; never a vanilla dump).
                 'loot-points/settings.json', 'loot-points/families.json', 'loot-points/additions.json', 'loot-points/floor-policy.json',
                 # HC-14 infected variety policy read by tools/package/infected_variety.py install/rollback.
                 'infected/variants.json',
                 # HC-33 authored forage route dispositions (native generator stays in charge).
                 'forage/habitats.json',
                 # HC-45 posture site research record (not read at runtime yet).
                 'infected/variety-sites.json',
                 # HC-56 fresh dormant crawler groups and CE context anchors (HCInfectedVariety reads $mission:).
                 'infected/variety-runtime.json',
                 # HC-46 surveyed herd routes (HCHordeMigration reads $mission:; unsurveyed routes stay inert).
                 'infected/route-surveys.json',
                 # HC-48 habitat dispositions; events.append.xml is inert (no cfgeconomycore registration).
                 'ecology/habitat-overrides.json', 'ecology/events.append.xml',
                 # HC-52 backpack light pairs (fail-closed; qualification stays false).
                 'lights/backpack-mounts.json',
                 'lights/pair-receipts.json',
                 # HC-59 shelter survey backlog and finite wreck part dispositions.
                 'travel/route-surveys.json', 'travel/auditshelter_scenes.json', 'travel/wreck-dispositions.json'}


# cov-buildings: strict schema-2 mission template pack, native acceptance pending.
MISSION_FILES.update({
    'interiors/templates/classes-000.json',
    'interiors/templates/classes-001.json',
    'interiors/templates/furnish-000.json',
    'interiors/templates/furnish-001.json',
    'interiors/templates/furnish-002.json',
    'interiors/templates/furnish-003.json',
    'interiors/templates/furnish-004.json',
    'interiors/templates/furnish-005.json',
    'interiors/templates/furnish-006.json',
    'interiors/templates/index-000.json',
    'interiors/templates/index-001.json',
    'interiors/templates/index.json',
    'interiors/templates/search-groups-000.json',
    'interiors/templates/search-groups-001.json',
    'interiors/templates/search-groups-002.json',
    'interiors/templates/search-groups-003.json',
    'interiors/templates/search-groups-004.json',
    'interiors/templates/search-groups-005.json',
    'interiors/templates/search-groups-006.json',
    'interiors/templates/search-groups-007.json',
    'interiors/templates/search-groups-008.json',
    'interiors/templates/search-groups-009.json',
    'interiors/templates/search-groups-010.json',
    'interiors/templates/search-groups-011.json',
    'interiors/templates/search-groups-012.json',
    'interiors/templates/search-groups-013.json',
    'interiors/templates/search-groups-014.json',
    'interiors/templates/search-groups-015.json',
    'interiors/templates/search-groups-016.json',
    'interiors/templates/search-groups-017.json',
    'interiors/templates/search-groups-018.json',
    'interiors/templates/search-groups-019.json',
    'interiors/templates/t-0000.json',
    'interiors/templates/t-0001.json',
    'interiors/templates/t-0002.json',
    'interiors/templates/t-0003.json',
    'interiors/templates/t-0004.json',
    'interiors/templates/t-0005.json',
    'interiors/templates/t-0006.json',
    'interiors/templates/t-0007.json',
    'interiors/templates/t-0008.json',
    'interiors/templates/t-0009.json',
    'interiors/templates/t-0010.json',
    'interiors/templates/t-0011.json',
    'interiors/templates/t-0012.json',
    'interiors/templates/t-0013.json',
    'interiors/templates/t-0014.json',
    'interiors/templates/t-0015.json',
    'interiors/templates/t-0016.json',
    'interiors/templates/t-0017.json',
    'interiors/templates/t-0018.json',
    'interiors/templates/t-0019.json',
    'interiors/templates/t-0020.json',
    'interiors/templates/t-0021.json',
    'interiors/templates/t-0022.json',
    'interiors/templates/t-0023.json',
    'interiors/templates/t-0024.json',
    'interiors/templates/t-0025.json',
    'interiors/templates/t-0026.json',
    'interiors/templates/t-0027.json',
    'interiors/templates/t-0028.json',
    'interiors/templates/t-0029.json',
    'interiors/templates/t-0030.json',
    'interiors/templates/t-0031.json',
    'interiors/templates/t-0032.json',
    'interiors/templates/t-0033.json',
    'interiors/templates/t-0034.json',
    'interiors/templates/t-0035.json',
    'interiors/templates/t-0036.json',
    'interiors/templates/t-0037.json',
    'interiors/templates/t-0038.json',
    'interiors/templates/t-0039.json',
    'interiors/templates/t-0040.json',
    'interiors/templates/t-0041.json',
    'interiors/templates/t-0042.json',
    'interiors/templates/t-0043.json',
    'interiors/templates/t-0044.json',
    'interiors/templates/t-0045.json',
    'interiors/templates/t-0046.json',
    'interiors/templates/t-0047.json',
    'interiors/templates/t-0048.json',
    'interiors/templates/t-0049.json',
    'interiors/templates/t-0050.json',
    'interiors/templates/t-0051.json',
    'interiors/templates/t-0052.json',
    'interiors/templates/t-0053.json',
    'interiors/templates/t-0054.json',
    'interiors/templates/t-0055.json',
    'interiors/templates/t-0056.json',
    'interiors/templates/t-0057.json',
    'interiors/templates/t-0058.json',
    'interiors/templates/t-0059.json',
    'interiors/templates/t-0060.json',
    'interiors/templates/t-0061.json',
    'interiors/templates/t-0062.json',
    'interiors/templates/t-0063.json',
    'interiors/templates/t-0064.json',
    'interiors/templates/t-0065.json',
    'interiors/templates/t-0066.json',
    'interiors/templates/t-0067.json',
    'interiors/templates/t-0068.json',
    'interiors/templates/t-0069.json',
    'interiors/templates/t-0070.json',
    'interiors/templates/t-0071.json',
    'interiors/templates/t-0072.json',
    'interiors/templates/t-0073.json',
    'interiors/templates/t-0074.json',
    'interiors/templates/t-0075.json',
    'interiors/templates/t-0076.json',
    'interiors/templates/t-0077.json',
    'interiors/templates/t-0078.json',
    'interiors/templates/t-0079.json',
    'interiors/templates/t-0080.json',
    'interiors/templates/t-0081.json',
    'interiors/templates/t-0082.json',
    'interiors/templates/t-0083.json',
    'interiors/templates/t-0084.json',
    'interiors/templates/t-0085.json',
    'interiors/templates/t-0086.json',
    'interiors/templates/t-0087.json',
    'interiors/templates/t-0088.json',
    'interiors/templates/t-0089.json',
    'interiors/templates/t-0090.json',
    'interiors/templates/t-0091.json',
    'interiors/templates/t-0092.json',
    'interiors/templates/t-0093.json',
    'interiors/templates/t-0094.json',
    'interiors/templates/t-0095.json',
    'interiors/templates/t-0096.json',
    'interiors/templates/t-0097.json',
    'interiors/templates/t-0098.json',
    'interiors/templates/t-0099.json',
    'interiors/templates/t-0100.json',
    'interiors/templates/t-0101.json',
    'interiors/templates/t-0102.json',
    'interiors/templates/t-0103.json',
    'interiors/templates/t-0104.json',
    'interiors/templates/t-0105.json',
    'interiors/templates/t-0106.json',
    'interiors/templates/t-0107.json',
    'interiors/templates/t-0108.json',
    'interiors/templates/t-0109.json',
    'interiors/templates/t-0110.json',
    'interiors/templates/t-0111.json',
    'interiors/templates/t-0112.json',
    'interiors/templates/t-0113.json',
    'interiors/templates/t-0114.json',
    'interiors/templates/t-0115.json',
    'interiors/templates/t-0116.json',
    'interiors/templates/t-0117.json',
    'interiors/templates/t-0118.json',
    'interiors/templates/t-0119.json',
    'interiors/templates/t-0120.json',
    'interiors/templates/t-0121.json',
    'interiors/templates/t-0122.json',
    'interiors/templates/t-0123.json',
    'interiors/templates/t-0124.json',
    'interiors/templates/t-0125.json',
    'interiors/templates/t-0126.json',
    'interiors/templates/t-0127.json',
    'interiors/templates/t-0128.json',
    'interiors/templates/t-0129.json',
    'interiors/templates/t-0130.json',
    'interiors/templates/t-0131.json',
    'interiors/templates/t-0132.json',
    'interiors/templates/t-0133.json',
    'interiors/templates/t-0134.json',
    'interiors/templates/t-0135.json',
    'interiors/templates/t-0136.json',
    'interiors/templates/t-0137.json',
    'interiors/templates/t-0138.json',
    'interiors/templates/t-0139.json',
    'interiors/templates/t-0140.json',
    'interiors/templates/t-0141.json',
    'interiors/templates/t-0142.json',
    'interiors/templates/t-0143.json',
    'interiors/templates/t-0144.json',
    'interiors/templates/t-0145.json',
    'interiors/templates/t-0146.json',
    'interiors/templates/t-0147.json',
    'interiors/templates/t-0148.json',
    'interiors/templates/t-0149.json',
    'interiors/templates/t-0150.json',
    'interiors/templates/t-0151.json',
    'interiors/templates/t-0152.json',
    'interiors/templates/t-0153.json',
    'interiors/templates/t-0154.json',
    'interiors/templates/t-0155.json',
    'interiors/templates/t-0156.json',
    'interiors/templates/t-0157.json',
    'interiors/templates/t-0158.json',
    'interiors/templates/t-0159.json',
    'interiors/templates/t-0160.json',
    'interiors/templates/t-0161.json',
    'interiors/templates/t-0162.json',
    'interiors/templates/t-0163.json',
    'interiors/templates/t-0164.json',
    'interiors/templates/t-0165.json',
    'interiors/templates/t-0166.json',
    'interiors/templates/t-0167.json',
    'interiors/templates/t-0168.json',
    'interiors/templates/t-0169.json',
    'interiors/templates/t-0170.json',
    'interiors/templates/t-0171.json',
    'interiors/templates/t-0172.json',
    'interiors/templates/t-0173.json',
    'interiors/templates/t-0174.json',
    'interiors/templates/t-0175.json',
    'interiors/templates/t-0176.json',
    'interiors/templates/t-0177.json',
    'interiors/templates/t-0178.json',
    'interiors/templates/t-0179.json',
    'interiors/templates/t-0180.json',
    'interiors/templates/t-0181.json',
    'interiors/templates/t-0182.json',
    'interiors/templates/t-0183.json',
    'interiors/templates/t-0184.json',
    'interiors/templates/t-0185.json',
    'interiors/templates/t-0186.json',
    'interiors/templates/t-0187.json',
    'interiors/templates/t-0188.json',
    'interiors/templates/t-0189.json',
    'interiors/templates/t-0190.json',
    'interiors/templates/t-0191.json',
    'interiors/templates/t-0192.json',
    'interiors/templates/t-0193.json',
    'interiors/templates/t-0194.json',
    'interiors/templates/t-0195.json',
    'interiors/templates/t-0196.json',
    'interiors/templates/t-0197.json',
    'interiors/templates/t-0198.json',
    'interiors/templates/t-0199.json',
    'interiors/templates/t-0200.json',
    'interiors/templates/t-0201.json',
    'interiors/templates/t-0202.json',
    'interiors/templates/t-0203.json',
    'interiors/templates/t-0204.json',
    'interiors/templates/t-0205.json',
    'interiors/templates/t-0206.json',
    'interiors/templates/t-0207.json',
    'interiors/templates/t-0208.json',
    'interiors/templates/t-0209.json',
    'interiors/templates/t-0210.json',
    'interiors/templates/t-0211.json',
    'interiors/templates/t-0212.json',
    'interiors/templates/t-0213.json',
    'interiors/templates/t-0214.json',
    'interiors/templates/t-0215.json',
    'interiors/templates/t-0216.json',
    'interiors/templates/t-0217.json',
    'interiors/templates/t-0218.json',
    'interiors/templates/t-0219.json',
    'interiors/templates/t-0220.json',
    'interiors/templates/t-0221.json',
    'interiors/templates/t-0222.json',
    'interiors/templates/t-0223.json',
    'interiors/templates/t-0224.json',
    'interiors/templates/t-0225.json',
    'interiors/templates/t-0226.json',
    'interiors/templates/t-0227.json',
    'interiors/templates/t-0228.json',
    'interiors/templates/t-0229.json',
    'interiors/templates/t-0230.json',
    'interiors/templates/t-0231.json',
    'interiors/templates/t-0232.json',
    'interiors/templates/t-0233.json',
    'interiors/templates/t-0234.json',
    'interiors/templates/t-0235.json',
    'interiors/templates/t-0236.json',
    'interiors/templates/t-0237.json',
    'interiors/templates/t-0238.json',
    'interiors/templates/t-0239.json',
    'interiors/templates/t-0240.json',
    'interiors/templates/t-0241.json',
    'interiors/templates/t-0242.json',
    'interiors/templates/t-0243.json',
    'interiors/templates/t-0244.json',
    'interiors/templates/t-0245.json',
    'interiors/templates/t-0246.json',
    'interiors/templates/t-0247.json',
    'interiors/templates/t-0248.json',
    'interiors/templates/t-0249.json',
    'interiors/templates/t-0250.json',
    'interiors/templates/t-0251.json',
    'interiors/templates/t-0252.json',
    'interiors/templates/t-0253.json',
    'interiors/templates/t-0254.json',
    'interiors/templates/t-0255.json',
    'interiors/templates/t-0256.json',
    'interiors/templates/t-0257.json',
    'interiors/templates/t-0258.json',
    'interiors/templates/t-0259.json',
    'interiors/templates/t-0260.json',
    'interiors/templates/t-0261.json',
})


def safe_name(name):
    if not isinstance(name, str) or len(name) > 240 or not name:
        raise ValueError('invalid path length/type')
    if not re.fullmatch(r'[A-Za-z0-9_@.$/ -]+', name):
        raise ValueError(f'unsafe path: {name!r}')
    for part in name.split('/'):
        if (not part or part in {'.', '..'} or part[-1:] in {'.', ' '}
                or part.split('.')[0].upper() in RESERVED):
            raise ValueError(f'unsafe Windows path: {name!r}')
    return name


def _names(files):
    seen = set()
    if len(files) > MAX_ENTRIES:
        raise ValueError('too many entries')
    for name in files:
        safe_name(name)
        if name.casefold() in seen:
            raise ValueError('case-colliding paths')
        seen.add(name.casefold())
    return sorted(files, key=lambda x: (x.casefold(), x))


def pack(files, prefix=PREFIX):
    if prefix not in PREFIXES:
        raise ValueError('unknown addon prefix')
    names = _names(files)
    header = bytearray(b'\0' + WORDS.pack(VERS, 0, 0, 0, 0))
    header += b'prefix\0' + prefix.encode('ascii') + b'\0\0'
    payload = bytearray()
    for name in names:
        data = files[name]
        if not isinstance(data, bytes) or len(data) > MAX_BYTES:
            raise ValueError('entry must be bounded bytes')
        header += name.replace('/', '\\').encode('ascii') + b'\0'
        header += WORDS.pack(0, 0, 0, 0, len(data))
        payload += data
    body = bytes(header + bytes(21) + payload)
    if len(body) > MAX_BYTES:
        raise ValueError('PBO size exceeds authored-addon limit')
    return body + b'\0' + hashlib.sha1(body).digest()


def parse(blob, prefixes=(PREFIX,)):
    if not isinstance(blob, bytes) or not 63 <= len(blob) <= MAX_BYTES + 21:
        raise ValueError('invalid PBO length')
    body, trailer = blob[:-21], blob[-21:]
    if trailer != b'\0' + hashlib.sha1(body).digest():
        raise ValueError('PBO checksum mismatch')
    offset = 0

    def string():
        nonlocal offset
        end = body.find(b'\0', offset, min(offset + 1025, len(body)))
        if end < 0:
            raise ValueError('unterminated string')
        try:
            value = body[offset:end].decode('ascii')
        except UnicodeDecodeError as e:
            raise ValueError('non-ASCII PBO string') from e
        offset = end + 1
        return value

    def words():
        nonlocal offset
        if offset + WORDS.size > len(body):
            raise ValueError('truncated header')
        value = WORDS.unpack_from(body, offset)
        offset += WORDS.size
        return value

    if string() != '' or words() != (VERS, 0, 0, 0, 0):
        raise ValueError('expected Vers header')
    props = {}
    while True:
        key = string()
        if not key:
            break
        if key in props:
            raise ValueError('duplicate property')
        props[key] = string()
    if set(props) != {'prefix'} or props['prefix'] not in prefixes:
        raise ValueError('exact HollowCountry prefix required' if prefixes == (PREFIX,) else 'unknown addon prefix')
    entries = {}
    while True:
        wire_name, meta = string(), words()
        if not wire_name:
            if meta != (0, 0, 0, 0, 0):
                raise ValueError('nonzero end header')
            break
        name = wire_name.replace('\\', '/')
        safe_name(name)
        if '/' in wire_name or name in entries or len(entries) >= MAX_ENTRIES:
            raise ValueError('duplicate/noncanonical header or too many entries')
        method, original, reserved, stamp, size = meta
        if method or original or reserved or stamp:
            raise ValueError('only canonical stored entries with zero timestamps supported')
        entries[name] = size
    _names(entries)
    if offset + sum(entries.values()) != len(body):
        raise ValueError('data sizes do not match archive')
    result = {}
    for name, size in entries.items():
        result[name] = body[offset:offset + size]
        offset += size
    return props['prefix'], result


def _regular_files(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('expected a real source directory')
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'symlink forbidden: {path}')
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError('special file forbidden')
        yield path.relative_to(root).as_posix(), path


def _text(data):
    if len(data) > MAX_BYTES:
        raise ValueError('oversize source')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError as e:
        raise ValueError('UTF-8 text required') from e
    if '\0' in text:
        raise ValueError('binary source forbidden')


def original_addon_name(name):
    if name in {'config.cpp', 'inputs.xml'}:
        return True
    if '..' in name:
        return False
    # data/defaults/** holds shipped profile defaults (JSON only) that the runtime self-provisions
    # into $profile:HollowCountry when the operator has no file of its own.
    return bool(re.fullmatch(
        r'(scripts/(3_Game|4_World|5_Mission)/[A-Za-z0-9_/.-]+\.c|gui/layouts/[A-Za-z0-9_-]+\.layout'
        r'|data/lighting/[A-Za-z0-9_-]+\.txt|data/defaults/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_.-]+\.json)', name))


def addon_prefix(root):
    """The contract prefix named by the addon's $PBOPREFIX$ (the main addon when absent)."""
    marker = Path(root) / '$PBOPREFIX$'
    if not marker.exists():
        return PREFIX
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_size > 256:
        raise ValueError('prefix file must be a small regular file')
    prefix = marker.read_text().strip()
    if prefix not in PREFIXES:
        raise ValueError('prefix file differs from contract')
    return prefix


def collect_addon(root, prefix=PREFIX):
    files = {}
    for name, path in _regular_files(root):
        safe_name(name)
        if name == '$PBOPREFIX$':
            if path.read_text().strip() != prefix:
                raise ValueError('prefix file differs from contract')
            continue  # property header is canonical; marker is build metadata
        if name in ('mod.cpp', 'meta.cpp'):
            _text(path.read_bytes())
            continue  # launcher metadata belongs at @HollowCountry/mod.cpp and meta.cpp
        if not original_addon_name(name):
            raise ValueError(f'addon file outside allowlist: {name}')
        data = path.read_bytes()
        if len(data) > MAX_BYTES:
            raise ValueError('oversize source file')
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError as e:
            raise ValueError('only original UTF-8 config/input/script/layout text allowed') from e
        if '\0' in text:
            raise ValueError('binary source forbidden')
        files[name] = data
    if 'config.cpp' not in files:
        raise ValueError('config.cpp required')
    _names(files)
    return files


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def handoff(addon, mission, release=False):
    if release:
        raise ValueError('release gated: official signatures and native/multiplayer acceptance pending')
    sources = collect_addon(addon)
    files = {'@HollowCountry/addons/hollowcountry.pbo': pack(sources)}
    metadata = Path(addon) / 'mod.cpp'
    if metadata.exists():
        files['@HollowCountry/mod.cpp'] = metadata.read_bytes()
    for name in ('docs/INSTALL_ROLLBACK.md', 'LICENSE.md', 'docs/PROVENANCE_AND_LICENSES.md'):
        guide = Path(__file__).resolve().parents[2] / name
        if guide.is_symlink():
            raise ValueError('symlinked portable documentation forbidden')
        files[name] = guide.read_bytes()
    for name, path in _regular_files(mission):
        if name not in MISSION_FILES:
            raise ValueError(f'mission handoff file outside allowlist: {name}')
        files['mission/hollow-country/' + name] = path.read_bytes()
    # Only these authored helpers, never arbitrary repository or build outputs.
    for name in ('travel.py', 'datamined_items.py', 'economy.py', 'gameplay.py', 'coverage.py', 'ce_coverage.py', 'interior_catalog.py', 'atmosphere.py', 'deploy.py', 'pbo.py', 'sign.py', 'Build-Sign-Verify.ps1', 'Invoke-NativeSmoke.ps1', 'Test-NativePackage.ps1', 'interiors_profile.py', 'ai_patrols.py', 'overlay_remove.py', 'ce_extensions.py', 'xml_text.py', 'optional_overlays.py', 'rag_optional.py', 'loot_boost.py', 'loot_floor_policy.py', 'firearms_roster.json', 'README.md'):
        path = Path(__file__).with_name(name)
        if path.is_file():
            files['tools/package/' + name] = path.read_bytes()
    manifest = {
        'schema': 1, 'distribution': 'private-only', 'status': 'unsigned-development',
        'prefix': PREFIX, 'release_allowed': False, 'runtime_acceptance': 'pending',
        'signature': None,
        'sources': {n: hashlib.sha256(d).hexdigest() for n, d in sorted(sources.items())},
        'files': {n: {'sha256': hashlib.sha256(d).hexdigest(), 'bytes': len(d)} for n, d in sorted(files.items())},
    }
    files['manifest.json'] = json_bytes(manifest)
    _names(files)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            z.writestr(info, files[name])
    return stream.getvalue()


def verify_handoff(blob):
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            names = z.namelist()
            _names(names)
            if len(names) != len(set(names)) or sum(x.file_size for x in z.infolist()) > MAX_BYTES:
                raise ValueError('duplicate entries or oversized handoff')
            for info in z.infolist():
                if info.is_dir() or ((info.external_attr >> 16) & 0o170000) == 0o120000:
                    raise ValueError('directories/symlinks forbidden')
            manifest = json.loads(z.read('manifest.json'))
            if (manifest.get('schema') != 1 or manifest.get('prefix') != PREFIX
                    or manifest.get('status') != 'unsigned-development'
                    or manifest.get('distribution') != 'private-only'
                    or manifest.get('runtime_acceptance') != 'pending'
                    or manifest.get('release_allowed') is not False
                    or manifest.get('signature') is not None):
                raise ValueError('unsupported handoff manifest')
            if set(names) != set(manifest['files']) | {'manifest.json'}:
                raise ValueError('manifest file set mismatch')
            helper_names = {'travel.py', 'optional_overlays.py', 'datamined_items.py', 'economy.py', 'gameplay.py', 'coverage.py', 'ce_coverage.py', 'interior_catalog.py', 'atmosphere.py', 'deploy.py', 'pbo.py', 'sign.py', 'Build-Sign-Verify.ps1',
                            'Invoke-NativeSmoke.ps1', 'Test-NativePackage.ps1', 'interiors_profile.py', 'ai_patrols.py', 'overlay_remove.py', 'ce_extensions.py', 'xml_text.py', 'rag_optional.py', 'loot_boost.py', 'loot_floor_policy.py',
                            'firearms_roster.json', 'README.md'}
            for name, expected in manifest['files'].items():
                if not (name in {'@HollowCountry/addons/hollowcountry.pbo', '@HollowCountry/mod.cpp', 'docs/INSTALL_ROLLBACK.md', 'LICENSE.md', 'docs/PROVENANCE_AND_LICENSES.md'}
                        or name in {'mission/hollow-country/' + n for n in MISSION_FILES}
                        or name in {'tools/package/' + n for n in helper_names}):
                    raise ValueError('handoff file outside allowlist')
                data = z.read(name)
                if expected != {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}:
                    raise ValueError('handoff checksum mismatch')
            _, entries = parse(z.read('@HollowCountry/addons/hollowcountry.pbo'))
            if {n: hashlib.sha256(d).hexdigest() for n, d in entries.items()} != manifest['sources']:
                raise ValueError('PBO source manifest mismatch')
            return manifest
    except (KeyError, TypeError, zipfile.BadZipFile, RuntimeError) as e:
        raise ValueError('invalid handoff archive') from e


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('pbo', 'handoff'):
        p = sub.add_parser(name)
        p.add_argument('--addon', type=Path, required=True)
        p.add_argument('--out', type=Path, required=True)
        if name == 'pbo':
            # The caller names the contract; the addon's own marker must then match it.
            p.add_argument('--prefix', choices=PREFIXES, default=PREFIX)
        if name == 'handoff':
            p.add_argument('--mission', type=Path, required=True)
            p.add_argument('--release', action='store_true')
    p = sub.add_parser('verify')
    p.add_argument('--prefix', choices=PREFIXES, default=PREFIX)
    p.add_argument('file', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'verify':
            if args.file.suffix.lower() == '.zip':
                manifest = verify_handoff(args.file.read_bytes())
                print(json.dumps({'status': manifest['status'], 'files': len(manifest['files'])}))
                return
            prefix, entries = parse(args.file.read_bytes(), prefixes=(args.prefix,))
            print(json.dumps({'prefix': prefix, 'entries': len(entries), 'signature': None,
                              'sha256': hashlib.sha256(args.file.read_bytes()).hexdigest()}))
            return
        blob = (pack(collect_addon(args.addon, args.prefix), args.prefix)
                if args.command == 'pbo'
                else handoff(args.addon, args.mission, args.release))
        # No overwriting stale or symlinked artifacts; choose a fresh output.
        with args.out.open('xb') as f:
            f.write(blob)
        print(json.dumps({'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest(),
                          'status': 'unsigned-development'}))
    except (ValueError, OSError) as e:
        parser.exit(1, f'{e}\n')


if __name__ == '__main__':
    main()
