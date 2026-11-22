"""Install-time CE rows for the variety packs; stdlib only, no runtime module or engine API.

The authored rows come from mission/hollow-country/optional/variety-types.json, which
tools/package/variety_packs.py generates from the pack dispositions (dev and CI only). A pack
that is not loaded contributes nothing, so a server without a pack never carries rows for it.
optional_overlays owns source hashes, duplicate checks, category checks and rollback.
"""
import json
from pathlib import PurePosixPath
import re
import xml.etree.ElementTree as ET

RELATIVE = 'variety-types.json'
KIND = 'hollow-country-variety-ce'
MAX_ROWS = 4096
SETTINGS_ROOTS = ('mission', 'profile')
SETTINGS_TARGET = re.compile(r'[A-Za-z0-9_]+(/[A-Za-z0-9_]+)*/[A-Za-z0-9_.]+\.json')
ORDER = ('nominal', 'lifetime', 'restock', 'min', 'quantmin', 'quantmax', 'cost')


def parse(data):
    document = json.loads(data.decode('utf-8'))
    if document.get('kind') != KIND or document.get('schema') != 1 or not isinstance(document.get('packs'), dict):
        raise ValueError('unknown variety CE document')
    for ident, pack in document['packs'].items():
        for entry in pack.get('settings', ()):
            target = entry.get('target')
            if (entry.get('root') not in SETTINGS_ROOTS or not isinstance(target, str)
                    or not SETTINGS_TARGET.fullmatch(target) or '..' in PurePosixPath(target).parts
                    or not isinstance(entry.get('content'), dict) or not entry['content']):
                raise ValueError('unsafe variety settings entry in ' + str(ident))
    return document['packs']


def pack_ids(path):
    """Workshop ids of the variety packs the shipped document covers; empty when none ships."""
    if not path.is_file():
        return ()
    return tuple(sorted(parse(path.read_bytes())))


def overlay_packs(path):
    return tuple(('Variety_' + ident, ident) for ident in pack_ids(path))


def _element(row):
    node = ET.Element('type', {'name': row['name']})
    for key in ORDER:
        ET.SubElement(node, key).text = str(row[key])
    ET.SubElement(node, 'flags', {key: str(value) for key, value in sorted(row['flags'].items())})
    if row['category']:
        ET.SubElement(node, 'category', {'name': row['category']})
    for tag in row['tags']:
        ET.SubElement(node, 'tag', {'name': tag})
    for usage in row['usage']:
        ET.SubElement(node, 'usage', {'name': usage})
    for value in row['value']:
        ET.SubElement(node, 'value', {'name': value})
    return node


def append_types(packs, path, types, source, overlays):
    """packs maps loaded overlay names to folders; rows are appended only for those packs."""
    if not any(name.startswith('Variety_') for name in packs):
        return 0
    document = parse(source(path))
    added = 0
    for name, ident in overlay_packs(path):
        if name not in packs:
            continue
        rows = document[ident]['types']
        if not 0 < len(rows) <= MAX_ROWS:
            raise ValueError('variety rows missing or over budget: ' + ident)
        for row in rows:
            overlays.unique_append(types, _element(row))
            added += 1
    return added


def settings_bytes(entry):
    return (json.dumps(entry['content'], indent=4) + '\n').encode('utf-8')


def _settings(path, root, ident=None):
    if not path.is_file():
        return []
    return [(pid, entry) for pid, pack in sorted(parse(path.read_bytes()).items())
            for entry in pack.get('settings', ()) if entry['root'] == root and ident in (None, pid)]


def mission_targets(path):
    """Mission-relative settings files the shipped document may write; optional_overlays allows exactly these."""
    return {entry['target'] for _, entry in _settings(path, 'mission')}


def profile_files(path):
    """{profile-relative target: bytes} of every shipped profile default (the friend bundle catalogue)."""
    return {entry['target']: settings_bytes(entry) for _, entry in _settings(path, 'profile')}


def mission_settings(packs, path, source, mission):
    """[(target, bytes)] for loaded packs; a file the server already has is never replaced."""
    if not any(name.startswith('Variety_') for name in packs):
        return []
    document = parse(source(path))
    rows = []
    for name, ident in overlay_packs(path):
        if name in packs:
            for entry in document[ident].get('settings', ()):
                if entry['root'] == 'mission' and not (mission / entry['target']).exists():
                    rows.append((entry['target'], settings_bytes(entry)))
    return rows
