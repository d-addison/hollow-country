"""#149 bounded habitat delta, composed by the shared mission installer.

Only our authored child selection ships; native XML stays operator-owned.
This module constructs bytes and never installs or runs a game/server. Native
brains, territory coordinates and all population/timing/range fields survive.
A successful candidate is source evidence, with runtime acceptance PENDING.
"""
from copy import deepcopy
import hashlib
import xml.etree.ElementTree as ET

MAX_XML_BYTES = 16 * 1024 * 1024
MAX_EVENTS = 4096
REQUIRED_CLASSES = frozenset({'Animal_OvisAries', 'Animal_OvisAriesF', 'Animal_OvisGmelini'})


def _xml(data, root):
    if not isinstance(data, bytes) or len(data) > MAX_XML_BYTES:
        raise ValueError('habitat XML missing or over byte bound')
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('habitat XML declarations refused')
    parsed = ET.fromstring(data)
    if parsed.tag != root:
        raise ValueError('habitat XML root mismatch')
    return parsed


def _shape(node):
    return node.tag, sorted(node.attrib.items()), (node.text or '').strip(), tuple(_shape(child) for child in node)


def _events(root):
    rows = root.findall('event')
    if len(rows) > MAX_EVENTS:
        raise ValueError('habitat event count bound')
    result = {}
    for row in rows:
        name = row.get('name', '')
        if not name or name.casefold() in result:
            raise ValueError('duplicate or unnamed habitat event')
        result[name.casefold()] = row
    return result


def build(manifest, delta, environment_data, events_data, available_classes):
    """Return replacements for stock files, never a duplicate CE registration.

    available_classes is the caller's inspected installed class inventory; it
    is NOT evidence those classes loaded or that the mixed herd behaves.
    Source hashes pin the original stock/owner input before other overlay steps.
    The caller owns atomic install/backup/rollback through the shared installer.
    """
    if manifest.get('Enabled') is False:
        return {}
    if manifest.get('Enabled') is not True:
        raise ValueError('habitat Enabled preference missing')
    expected = {row['Path']: row['Sha256'] for row in manifest['Sources']}
    for path, data in (('cfgenvironment.xml', environment_data), ('db/events.xml', events_data)):
        if hashlib.sha256(data).hexdigest() != expected.get(path):
            raise ValueError('habitat source hash changed: ' + path)
    if not REQUIRED_CLASSES <= set(available_classes):
        raise ValueError('habitat class unavailable: ' + ','.join(sorted(REQUIRED_CLASSES - set(available_classes))))
    events = _xml(events_data, 'events')
    additions = _xml(delta, 'events')
    existing, selected = _events(events), _events(additions)
    if set(selected) != {'animalsheep'} or 'animalsheep' not in existing:
        raise ValueError('habitat requires exactly one existing AnimalSheep event')
    before, after = existing['animalsheep'], selected['animalsheep']
    old_fields, new_fields = deepcopy(before), deepcopy(after)
    old_children, new_children = old_fields.find('children'), new_fields.find('children')
    if old_children is None or new_children is None:
        raise ValueError('habitat children missing')
    old_fields.remove(old_children)
    new_fields.remove(new_children)
    if _shape(old_fields) != _shape(new_fields):
        raise ValueError('habitat population/timing/range change refused')
    rows = new_children.findall('child')
    if len(rows) != 3 or {row.get('type') for row in rows} != REQUIRED_CLASSES:
        raise ValueError('habitat child selection differs from inspected classes')
    counts = {row.get('type'): (row.get('min'), row.get('max'), row.get('lootmin'), row.get('lootmax')) for row in rows}
    if counts != {'Animal_OvisAries': ('1', '1', '0', '0'),
                  'Animal_OvisAriesF': ('3', '5', '0', '0'),
                  'Animal_OvisGmelini': ('0', '1', '0', '0')}:
        raise ValueError('habitat population or loot budget change refused')
    # Edit the existing event in place; keep its ordering and unrelated rows.
    before.remove(before.find('children'))
    before.append(deepcopy(after.find('children')))
    environment = _xml(environment_data, 'env')
    territories = environment.find('territories')
    if territories is None:
        raise ValueError('habitat territories missing')
    hare = territories.findall("file[@path='env/hare_territories.xml']")
    if not 1 <= len(hare) <= 2:
        raise ValueError('habitat hare declarations differ from inspected baseline')
    for duplicate in hare[1:]:
        territories.remove(duplicate)
    return {path: ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'
            for path, root in (('db/events.xml', events), ('cfgenvironment.xml', environment))}
