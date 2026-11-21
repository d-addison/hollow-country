"""Disposable stock-shaped inputs derived from the variety installer policy."""
from collections import Counter
from decimal import Decimal
import hashlib
import xml.etree.ElementTree as ET

from tools.package import infected_variety as tool


def transfers(policy):
    rows = list(policy['substitutions'])
    if tool.enabled(policy, 'EnableComposition'):
        rows.extend(policy.get('palette_rebalance', {}).get('transfers', []))
    return rows


def weight_deltas(policy):
    deltas = Counter()
    for row in transfers(policy):
        deltas[row['event'], row['from']] -= row['share']
        deltas[row['event'], row['to']] += row['share']
    return deltas


def synthetic_events(policy):
    rows = transfers(policy)
    outgoing = Counter()
    present = set()
    for row in rows:
        outgoing[row['event'], row['from']] += row['share']
        present.add((row['event'], row['from']))
    # Exercise existing stock destinations as well as newly inserted children.
    new_substitutions = {(r['event'], r['to']) for r in policy['substitutions']
                         if not r.get('existing_destination', False)}
    present.update((r['event'], r['to']) for r in rows
                   if (r['event'], r['to']) not in new_substitutions)
    events = ET.Element('events')
    for name in sorted({r['event'] for r in rows}):
        event = ET.SubElement(events, 'event', name=name)
        ET.SubElement(event, 'nominal').text = '42'
        ET.SubElement(event, 'active').text = '1'
        children = ET.SubElement(event, 'children')
        for event_name, child in sorted(present):
            if event_name == name:
                # Synthetic positive reserve after every authored outgoing share.
                ET.SubElement(children, 'child', type=child,
                              min=str(8 + outgoing[name, child]), max='0',
                              lootmin='0', lootmax='5')
    unrelated = ET.SubElement(events, 'event', name='Unrelated')
    ET.SubElement(unrelated, 'active').text = '0'
    ET.SubElement(ET.SubElement(unrelated, 'children'), 'child',
                  type='SyntheticUntouched', min='3', max='7', lootmin='0', lootmax='2')
    ET.indent(events)
    return (b'<?xml version="1.0" encoding="UTF-8"?>\r\n'
            b'<!-- synthetic comment retained -->\r\n'
            + ET.tostring(events).replace(b'\n', b'\r\n') + b'\r\n')


def probabilities(names, rows):
    outgoing = Counter()
    for row in rows:
        outgoing[row['from']] += Decimal(row['chance'])
    reserve = (Decimal(1) - sum(outgoing.values())) / len(names)
    if reserve <= 0:
        raise ValueError('synthetic probability fixture needs positive headroom')
    return {name: outgoing[name] + reserve for name in sorted(names)}


def write_mission(mission, policy, events):
    """Create every enabled installer input; re-pin synthetic bytes in the copy."""
    inputs = {tool.TARGET: events}
    policy['evidence']['stock_events_sha256'] = hashlib.sha256(events).hexdigest()
    if tool.enabled(policy, 'EnableAccessories'):
        overlay = policy['accessories']
        rows = overlay['probability_transfers']
        names = set(overlay['item_transfers']) | {r[k] for r in rows for k in ('from', 'to')}
        presets = ET.Element('randompresets')
        for name, chance in probabilities(names, rows).items():
            preset = ET.SubElement(presets, 'attachments', name=name, chance=str(chance))
            item_rows = overlay['item_transfers'].get(name, [])
            items = {r[k] for r in item_rows for k in ('from', 'to')} or {'SyntheticAccessory'}
            for item, weight in probabilities(items, item_rows).items():
                ET.SubElement(preset, 'item', name=item, chance=str(weight))
        spawnable = ET.Element('spawnabletypes')
        for name in sorted(set(overlay['explicit_classes'].values()) | {'ZmbM_Synthetic'}):
            node = ET.SubElement(spawnable, 'type', name=name)
            ET.SubElement(node, 'cargo', preset='SyntheticCargo')
            for preset in sorted(names):
                ET.SubElement(node, 'attachments', preset=preset)
        inputs[tool.SPAWNABLE] = ET.tostring(spawnable)
        inputs[tool.PRESETS] = ET.tostring(presets)
        for key, name in (('stock_spawnable_sha256', tool.SPAWNABLE),
                          ('stock_presets_sha256', tool.PRESETS)):
            overlay[key] = hashlib.sha256(inputs[name]).hexdigest()
    for name, data in inputs.items():
        path = mission / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return inputs
