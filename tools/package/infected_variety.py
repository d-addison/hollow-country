"""HC-14 restart-bound child substitution; offline installation, runtime PENDING.

Stop the server. Supply installed stock db/events.xml, pinned in variants.json.
Authored palette rows and selected infected attachment rows change; other bytes are
retained, except a missing/nonstandard XML declaration is normalized through
xml_text to the double-quoted UTF-8 form. No CE extension is registered.
Seasonal rows (seasonal_rebalance in variants.json) apply only when the install names
a season (--season, or --season-profile reading the persisted HCVisualSeasons clock);
the season is restart-bound and recorded in the receipt, so a season change means
rollback and install again.
Off and rollback restore the original bytes, including the original declaration.
Infected kits (#339): an HC child row copies its parent row (cargo and attachments); stock
Zmb rows gain role cargo presets (hc_kit_*, written to cfgrandompresets.xml) and a little
worn-gear variety inside slots the row already has. Spawnable and preset files join the
receipt, so rollback restores stock bytes and a changed policy or generator reapplies.
"""
import argparse
import base64
import copy
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET
from xml.parsers import expat

from tools.package import economy, xml_text
from tools.package.optional_overlays import atomic, mission_target, read, safe

POLICY = Path(__file__).resolve().parents[2] / 'mission/hollow-country/infected/variants.json'
MANAGED = 'hollow-country-infected'
TARGET = 'db/events.xml'
SPAWNABLE = 'cfgspawnabletypes.xml'
PRESETS = 'cfgrandompresets.xml'
SEASONS = ('spring', 'summer', 'autumn', 'winter')
SEASON_STATE = 'HollowCountry/visual-seasons.json'
SEASON_CONFIG = 'HollowCountry/seasons.json'
DEFAULT_PHASE_SECONDS = 604800
ACCESSORY_MARKER = b'<!-- HC #316 accessories; receipt rollback required -->'
KIT_MARKER = b'<!-- HC #339 infected kits; receipt rollback required -->'
KIT_PREFIX = 'hc_kit_'
# Bump with any change to how spawnable or preset bytes are produced: the receipt records it,
# and friend_install folds the policy file (and so a bump in the same commit) into overlay_fingerprint.
GENERATOR_VERSION = 'HC-339-kits-1'
MAX_KIT_PRESETS = 2


def _signature(node):
    return (node.tag, sorted(node.attrib.items()), (node.text or '').strip(),
            tuple(_signature(c) for c in node))


def _events(data):
    root = economy.xml(data, 'events')
    return economy._unique(root.findall('event'))


def _spans(data):
    """Locate direct event child rows with Expat byte offsets, not XML regexes."""
    parser = expat.ParserCreate()
    stack = []
    rows = {}
    event = None
    pending = None

    def start(name, attrs):
        nonlocal event, pending
        if stack == ['events'] and name == 'event':
            event = attrs.get('name')
        if stack == ['events', 'event', 'children'] and name == 'child':
            pending = (event, attrs.get('type'), parser.CurrentByteIndex)
        stack.append(name)

    def end(name):
        nonlocal pending
        if stack == ['events', 'event', 'children', 'child']:
            event_name, type_name, begin = pending
            finish = parser.CurrentByteIndex
            # For <child/> Expat reports the following byte. For paired tags
            # it reports the beginning of </child>; that end tag has no attrs.
            if not data[begin:finish].rstrip().endswith(b'/>'):
                finish = data.index(b'>', finish) + 1
            rows[(event_name, type_name)] = (begin, finish)
            pending = None
        stack.pop()

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.Parse(data, True)
    return rows


def season_transfers(policy, season):
    """Authored restart-bound transfers for one season; None selects none."""
    if season is None:
        return []
    if season not in SEASONS:
        raise ValueError('unknown season: ' + str(season))
    block = policy.get('seasonal_rebalance', {}).get('seasons', {}).get(season, {})
    return block.get('transfers', [])


def season_from_profile(profile):
    """Season of the persisted HCVisualSeasons clock, or None when it is unavailable.

    Offline mirror of HCVisualSeasons.HCPhase: elapsed seconds modulo four phases of
    PhaseSeconds. Missing or invalid state selects no season, like the runtime's -1.
    """
    profile = Path(profile)
    try:
        state = json.loads(read(profile / SEASON_STATE, 4096))
    except (OSError, ValueError):
        return None
    elapsed = state.get('ElapsedSeconds') if isinstance(state, dict) else None
    if type(elapsed) is not int or elapsed < 0:
        return None
    phase_seconds = DEFAULT_PHASE_SECONDS
    try:
        config = json.loads(read(profile / SEASON_CONFIG, 4096))
        value = config.get('PhaseSeconds', DEFAULT_PHASE_SECONDS) if isinstance(config, dict) else None
        if type(value) is int and value > 0:
            phase_seconds = value
    except (OSError, ValueError):
        pass
    return SEASONS[elapsed % (phase_seconds * 4) // phase_seconds]


def substitute(original, stock, policy, season=None):
    """Require stock-identical targeted events; preserve other mission content."""
    if economy.sha(stock) != policy['evidence']['stock_events_sha256']:
        raise ValueError('installed stock hash does not match pinned stock events')
    expected, current = _events(stock), _events(original)
    substitutions = policy['substitutions']
    targets = {s['event'] for s in substitutions}
    if enabled(policy, 'EnableComposition'):
        targets |= {r['event'] for r in policy.get('palette_rebalance', {}).get('transfers', [])}
        targets |= {r['event'] for r in season_transfers(policy, season)}
    for name in targets:
        if name not in expected or name not in current:
            raise ValueError('missing stock target event: ' + name)
        if _signature(current[name]) != _signature(expected[name]):
            raise ValueError('target event differs from expected stock: ' + name)
        if len(current[name].findall('children')) != 1:
            raise ValueError('stock target needs one children element: ' + name)
        economy._unique(current[name].findall('./children/child'), 'type')
    spans = _spans(original)
    replacements = {}
    destinations = set()
    donors = {(r['event'], r['from']) for r in substitutions}
    changed = {}
    additions = {}
    for row in substitutions:
        name, donor, variant, share = row['event'], row['from'], row['to'], row['share']
        key, destination = (name, donor), (name, variant)
        if destination in destinations or destination in donors:
            raise ValueError('duplicate destination or donor/destination overlap')
        destinations.add(destination)
        children = economy._unique(current[name].findall('./children/child'), 'type')
        if donor not in children or key not in spans:
            raise ValueError('stock donor missing: ' + name)
        child = changed.setdefault(key, copy.deepcopy(children[donor]))
        if (set(child.attrib) != {'type', 'min', 'max', 'lootmin', 'lootmax'} or len(child)
                or (child.text or '').strip() or type(share) is not int or share <= 0
                or any(not re.fullmatch(r'[0-9]+', child.get(f, '')) for f in ('min', 'max', 'lootmin', 'lootmax'))
                or int(child.get('min')) <= share):
            # A donor always keeps a positive weight: no stock class leaves an event.
            raise ValueError('unsupported stock donor values: ' + donor)
        child.set('min', str(int(child.get('min')) - share))
        if variant in children:
            # Reweight an existing stock police outfit without duplicating its row
            # or changing its stock cap/loot policy.
            added = changed.setdefault(destination, copy.deepcopy(children[variant]))
            weight = int(added.get('min')) + share
            if int(added.get('max')) > 0 and weight > int(added.get('max')):
                raise ValueError('destination share exceeds stock cap: ' + variant)
            added.set('min', str(weight))
        else:
            added = copy.deepcopy(children[donor])
            added.set('min', str(share))
            added.set('max', '0')
            added.set('type', variant)
            additions.setdefault(key, []).append(added)
    for key, child in changed.items():
        begin, finish = spans[key]
        prefix = original[:begin].rsplit(b'\n', 1)[-1]
        indent = prefix if not prefix.strip() else b'      '
        newline = b'\r\n' if b'\r\n' in original else b'\n'
        nodes = [child] + additions.get(key, [])
        for node in nodes:
            node.tail = None
        replacements[key] = (begin, finish, (newline + indent).join(
            ET.tostring(node, encoding='utf-8') for node in nodes))
    result = original
    for begin, finish, replacement in sorted(replacements.values(), reverse=True):
        result = result[:begin] + replacement + result[finish:]
    declaration = re.match(br'(?:\xef\xbb\xbf)?<\?xml\s.*?\?>', result, re.S)
    if declaration:
        result = xml_text.DECLARATION.rstrip(b'\n') + result[declaration.end():]
    else:
        result = xml_text.DECLARATION + result
    # Validate emitted XML and each budget as an independent postcondition.
    after = _events(result)
    for name in targets:
        for field in ('min', 'max'):
            if sum(int(c.get(field)) for c in current[name].findall('./children/child')) != sum(
                    int(c.get(field)) for c in after[name].findall('./children/child')):
                raise ValueError('authored child budget changed: ' + name)
    if enabled(policy, 'EnableComposition'):
        result = rebalance(result, policy.get('palette_rebalance', {}).get('transfers', []))
        seasonal = season_transfers(policy, season)
        if seasonal:
            result = rebalance(result, seasonal)
    return result


def enabled(policy, switch):
    value = policy.get('mix_policy', {}).get(switch, True)
    if type(value) is not bool:
        raise ValueError('mix_policy flag must be boolean: ' + switch)
    return value


def rebalance(original, transfers):
    """Apply authored stock-model family transfers after the legacy substitutions."""
    events = _events(original)
    changed, additions = {}, {}
    spans = _spans(original)
    for row in transfers:
        name, donor, receiver, share = (row[k] for k in ('event', 'from', 'to', 'share'))
        if type(share) is not int or share <= 0 or donor == receiver:
            raise ValueError('invalid palette share')
        if name not in events:
            raise ValueError('palette event missing: ' + name)
        children = economy._unique(events[name].findall('./children/child'), 'type')
        if donor not in children:
            raise ValueError('palette donor missing: ' + donor)
        source = changed.setdefault((name, donor), copy.deepcopy(children[donor]))
        if int(source.get('min')) <= share:
            raise ValueError('palette donor must remain positive: ' + donor)
        source.set('min', str(int(source.get('min')) - share))
        key = (name, receiver)
        if receiver in children:
            dest = changed.setdefault(key, copy.deepcopy(children[receiver]))
        else:
            dest = additions.get(key)
            if dest is None:
                dest = copy.deepcopy(children[donor])
                dest.set('type', receiver)
                dest.set('min', '0')
                dest.set('max', '0')
                additions[key] = dest
        dest.set('min', str(int(dest.get('min')) + share))
        if int(dest.get('max')) > 0 and int(dest.get('min')) > int(dest.get('max')):
            raise ValueError('palette destination exceeds cap: ' + receiver)
    # Reuse byte spans: all non-child event settings and untouched bytes survive.
    patches = []
    for key, child in changed.items():
        begin, end = spans[key]
        child.tail = None
        patches.append((begin, end, ET.tostring(child, encoding='utf-8')))
    for (name, _), child in additions.items():
        key = next(k for k in spans if k[0] == name)
        begin, _ = spans[key]
        child.tail = None
        patches.append((begin, begin, ET.tostring(child, encoding='utf-8') + b'\n      '))
    result = original
    # At equal offsets replace the old row before inserting new rows.
    for begin, end, data in sorted(patches, key=lambda r: (r[0], r[1]), reverse=True):
        result = result[:begin] + data + result[end:]
    after = _events(result)
    for name in {r['event'] for r in transfers}:
        before_rows = economy._unique(events[name].findall('./children/child'), 'type')
        after_rows = economy._unique(after[name].findall('./children/child'), 'type')
        for field in ('min', 'max'):
            if sum(int(c.get(field)) for c in before_rows.values()) != sum(int(c.get(field)) for c in after_rows.values()):
                raise ValueError('palette budget changed: ' + name)
        for field in ('lootmin', 'lootmax'):
            if sum(int(c.get('min')) * int(c.get(field)) for c in after_rows.values()) > sum(
                    int(c.get('min')) * int(c.get(field)) for c in before_rows.values()):
                raise ValueError('palette increased weighted loot budget: ' + name)
        for n, child in before_rows.items():
            if {k: v for k, v in child.attrib.items() if k != 'min'} != {k: v for k, v in after_rows[n].attrib.items() if k != 'min'}:
                raise ValueError('palette changed non-weight field: ' + n)
            if int(child.get('min')) > 0 and int(after_rows[n].get('min')) <= 0:
                raise ValueError('palette zeroed a stock class: ' + n)
    return result


def _chance(value):
    try:
        chance = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('invalid accessory chance') from None
    if not chance.is_finite() or not 0 <= chance <= 1:
        raise ValueError('invalid accessory chance')
    return chance


def _type_spans(data):
    parser = expat.ParserCreate()
    stack, spans = [], {}
    pending = None
    def start(name, attrs):
        nonlocal pending
        if stack == ['spawnabletypes'] and name == 'type':
            pending = (attrs.get('name'), parser.CurrentByteIndex)
        stack.append(name)
    def end(name):
        if stack == ['spawnabletypes', 'type']:
            key, begin = pending
            finish = parser.CurrentByteIndex
            if not data[begin:data.index(b'>', begin) + 1].rstrip().endswith(b'/>'):
                finish = data.index(b'>', finish) + 1
            spans[key] = (begin, finish)
        stack.pop()
    parser.StartElementHandler, parser.EndElementHandler = start, end
    parser.Parse(data, True)
    return spans


def kits_enabled(policy):
    """Kits ride on the accessories files, so they need that lever too."""
    return enabled(policy, 'EnableAccessories') and enabled(policy, 'EnableKits')


def _kits(policy):
    """Validated #339 kit policy: roles, hc_kit_* cargo presets, worn-gear variety."""
    kits = policy.get('infected_kits')
    if not isinstance(kits, dict) or kits.get('schema_version') != 1:
        raise ValueError('missing or invalid authored infected kit policy')
    presets = kits.get('presets')
    roles = kits.get('roles')
    worn = kits.get('worn_gear')
    if not isinstance(presets, dict) or not isinstance(roles, dict) or not isinstance(worn, dict) or not presets or not roles:
        raise ValueError('invalid infected kit policy shape')
    for name, row in presets.items():
        if not re.fullmatch(KIT_PREFIX + r'[a-z0-9_]+', name) or not isinstance(row, dict):
            raise ValueError('invalid kit preset name: ' + str(name))
        if not Decimal('0.10') <= _chance(row.get('chance')) <= Decimal('0.25'):
            raise ValueError('kit preset chance outside 0.10-0.25: ' + name)
        items = row.get('items')
        if not isinstance(items, list) or not items:
            raise ValueError('kit preset has no items: ' + name)
        seen = set()
        for item in items:
            if (not isinstance(item, dict) or set(item) != {'name', 'chance'}
                    or not isinstance(item['name'], str) or not re.fullmatch(r'[A-Za-z0-9_]+', item['name'])
                    or item['name'] in seen or not 0 < _chance(item['chance']) <= 1):
                raise ValueError('invalid kit preset item: ' + name)
            seen.add(item['name'])
    for role, row in roles.items():
        prefixes = row.get('segment_prefixes') if isinstance(row, dict) else None
        used = row.get('presets') if isinstance(row, dict) else None
        if (not isinstance(prefixes, list) or not prefixes or any(not isinstance(x, str) or not x for x in prefixes)
                or not isinstance(used, list) or not 0 < len(used) <= MAX_KIT_PRESETS
                or len(set(used)) != len(used) or any(x not in presets for x in used)):
            raise ValueError('invalid kit role: ' + str(role))
    if not isinstance(worn.get('slot_transfers'), list) or not isinstance(worn.get('item_transfers'), dict):
        raise ValueError('invalid worn gear policy')
    return kits


def _role(name, kits):
    """Role of a stock Zmb class from its name segments (ZmbM_<family>_<colour>); None for civilians."""
    segments = name.split('_')[1:]
    for role, row in kits['roles'].items():
        if any(segment.startswith(prefix) for segment in segments for prefix in row['segment_prefixes']):
            return role
    return None


def _add_kits(node, name, kits):
    """Append the role's cargo presets after the row's cargo; returns the preset names added."""
    role = _role(name, kits)
    if role is None or any((c.get('preset') or '').startswith(KIT_PREFIX) for c in node.findall('cargo')):
        return []
    added = kits['roles'][role]['presets']
    at = max([i + 1 for i, child in enumerate(node) if child.tag == 'cargo'], default=0)
    # Keep the row's own line layout: new elements take the whitespace that followed their neighbour.
    space = node[at - 1].tail if at else node.text
    for offset, preset in enumerate(added):
        row = ET.Element('cargo', {'preset': preset})
        row.tail = space
        node.insert(at + offset, row)
    if sum(1 for c in node.findall('cargo') if (c.get('preset') or '').startswith(KIT_PREFIX)) > MAX_KIT_PRESETS:
        raise ValueError('more than two kit presets on one row: ' + name)
    return list(added)


def _kit_preset_bytes(presets_data, kits, used):
    """Stock presets plus the hc_kit_* cargo presets some row names; stock bytes before them are untouched."""
    names = {n.get('name') for n in economy.xml(presets_data, 'randompresets')}
    emitted = [n for n in kits['presets'] if n in used]
    if any(n in names for n in emitted):
        raise ValueError('kit preset already present in cfgrandompresets.xml')
    newline = b'\r\n' if b'\r\n' in presets_data else b'\n'
    lines = ['\t\t' + KIT_MARKER.decode()]
    for name in emitted:
        row = kits['presets'][name]
        lines.append('\t\t<cargo chance="%s" name="%s">' % (row['chance'], name))
        lines.extend('\t\t\t\t<item name="%s" chance="%s" />' % (i['name'], i['chance']) for i in row['items'])
        lines.append('\t\t</cargo>')
    end = presets_data.rfind(b'</randompresets>')
    if end < 0:
        raise ValueError('randompresets closing tag missing')
    block = (newline.join(l.encode() for l in lines) + newline)
    result = presets_data[:end] + block + presets_data[end:]
    economy._unique(economy.xml(result, 'randompresets').findall('cargo'))
    return result, emitted


def accessories(original, presets_data, overlay, kits=None):
    """Spawnabletypes bytes only (see build); kept for callers that need nothing else."""
    return build(original, presets_data, overlay, kits)['spawn']


def build(original, presets_data, overlay, kits=None):
    """Spawn rows for stock and HC infected: accessories, worn-gear variety, role kits, HC parity.

    Returns {'spawn': bytes, 'presets': bytes or None, 'report': dict}. Presets change only when
    kits are given. An HC child copies its final parent row (cargo and attachments); a parent
    without a stock row uses the authored family sibling; no child is ever left without a row.
    """
    if economy.sha(presets_data) != overlay['stock_presets_sha256']:
        raise ValueError('accessory random presets differ from pinned stock')
    root = economy.xml(original, 'spawnabletypes')
    # Stock has duplicate non-infected HuntingVest rows; leave them untouched.
    types = economy._unique([n for n in root.findall('type')
                             if n.get('name', '').startswith(('ZmbM_', 'ZmbF_', 'HC_Zmb'))])
    presets = economy._unique(economy.xml(presets_data, 'randompresets').findall('attachments'))
    spans, changed = _type_spans(original), {}
    transfers = list(overlay['probability_transfers'])
    item_transfers = {k: list(v) for k, v in overlay['item_transfers'].items()}
    if kits is not None:
        # Worn gear moves probability only between slots a row already has (existing_slot_only).
        transfers += [dict(r, existing_slot_only=True) for r in kits['worn_gear']['slot_transfers']]
        for preset, rows in kits['worn_gear']['item_transfers'].items():
            item_transfers.setdefault(preset, []).extend(rows)
    chosen = set(item_transfers) | {r[k] for r in transfers for k in ('from', 'to')}
    def expand(node):
        node = copy.deepcopy(node)
        refs = {}
        for a in node.findall('attachments'):
            preset = a.get('preset')
            if preset not in chosen:
                continue
            if preset in refs or set(a.attrib) != {'preset'} or len(a):
                raise ValueError('unsupported accessory preset reference')
            expanded = copy.deepcopy(presets[preset])
            expanded.attrib.pop('name')
            node.insert(list(node).index(a), expanded)
            node.remove(a)
            refs[preset] = expanded
        for row in transfers:
            if row['from'] not in refs:
                continue
            source = refs[row['from']]
            dest = refs.get(row['to'])
            if dest is None:
                if row.get('existing_slot_only'):
                    continue
                dest = copy.deepcopy(presets[row['to']])
                # A new slot is funded solely by the source probability.
                dest.attrib.pop('name')
                dest.set('chance', '0')
                refs[row['to']] = dest
                node.append(dest)
            delta = _chance(row['chance'])
            old = _chance(source.get('chance'))
            if delta <= 0 or old <= delta:
                raise ValueError('accessory source must remain positive')
            source.set('chance', str(old - delta))
            dest.set('chance', str(_chance(dest.get('chance')) + delta))
        for preset, rows in item_transfers.items():
            if preset not in refs:
                continue
            items = economy._unique(refs[preset].findall('item'))
            before = sum(_chance(i.get('chance')) for i in items.values())
            for row in rows:
                if row['from'] not in items or row['to'] not in items:
                    raise ValueError('accessory item missing from preset: ' + preset)
                source, dest = items[row['from']], items[row['to']]
                delta = _chance(row['chance'])
                old = _chance(source.get('chance'))
                if delta <= 0 or old <= delta:
                    raise ValueError('accessory item must remain positive')
                source.set('chance', str(old - delta))
                dest.set('chance', str(_chance(dest.get('chance')) + delta))
            if before != sum(_chance(i.get('chance')) for i in items.values()):
                raise ValueError('accessory item probability changed')
        # Validate every emitted probability, including destinations.
        for a in refs.values():
            _chance(a.get('chance'))
            for item in a.findall('item'):
                _chance(item.get('chance'))
        return node, bool(refs)
    final, kit_names = {}, {}
    for name, node in types.items():
        if not name.startswith(('ZmbM_', 'ZmbF_')):
            continue
        updated, touched = expand(node)
        given = _add_kits(updated, name, kits) if kits is not None else []
        if touched or given:
            changed[name] = updated
        final[name] = updated
        if given:
            kit_names[name] = given
    fallbacks = overlay.get('parent_fallbacks', {})
    sources, additions = {}, []
    for name, parent in overlay['explicit_classes'].items():
        if name in types:
            raise ValueError('explicit accessory class already present: ' + name)
        # An HC child is its parent for loot: same cargo and attachments. A stock parent without a
        # spawnabletypes row borrows the authored family sibling's row; none is left without one.
        source = parent if parent in final else fallbacks.get(parent)
        if source not in final:
            raise ValueError('HC child has no parent row and no family fallback: ' + name)
        node = copy.deepcopy(final[source])
        node.set('name', name)
        additions.append(node)
        sources[name] = source
        if source in kit_names:
            kit_names[name] = kit_names[source]
    patches = []
    for name, node in changed.items():
        node.tail = None
        patches.append((*spans[name], ET.tostring(node, encoding='utf-8')))
    result = original
    for begin, end, data in sorted(patches, reverse=True):
        result = result[:begin] + data + result[end:]
    end = result.rfind(b'</spawnabletypes>')
    if end < 0:
        raise ValueError('spawnabletypes closing tag missing')
    newline = b'\r\n' if b'\r\n' in original else b'\n'
    data = ACCESSORY_MARKER + newline + newline.join(ET.tostring(n, encoding='utf-8') for n in additions) + newline
    result = result[:end] + data + result[end:]
    economy._unique([n for n in economy.xml(result, 'spawnabletypes').findall('type')
                     if n.get('name', '').startswith(('ZmbM_', 'ZmbF_', 'HC_Zmb'))])
    presets_out, emitted = None, []
    if kits is not None:
        presets_out, emitted = _kit_preset_bytes(presets_data, kits, {p for given in kit_names.values() for p in given})
    return {'spawn': result, 'presets': presets_out,
            'report': _report(result, overlay, sources, kit_names, emitted, kits)}


def _report(spawn, overlay, sources, kit_names, emitted, kits):
    """Postcondition over the emitted bytes: HC rows equal their source row; kit limits hold."""
    rows = {n.get('name'): n for n in economy.xml(spawn, 'spawnabletypes').findall('type')
            if n.get('name', '').startswith(('ZmbM_', 'ZmbF_', 'HC_Zmb'))}
    def body(node):
        return tuple(_signature(c) for c in node)
    parity = missing = 0
    for name in overlay['explicit_classes']:
        row = rows.get(name)
        if row is None:
            missing += 1
        elif body(row) == body(rows[sources[name]]) and (len(row) or not len(rows[sources[name]])):
            parity += 1
    if missing or parity != len(overlay['explicit_classes']):
        raise ValueError('HC child rows are not equal to their parent rows')
    chance = {}
    for name, given in kit_names.items():
        if len(given) > MAX_KIT_PRESETS:
            raise ValueError('more than two kit presets on one row: ' + name)
        chance[name] = sum(_chance(kits['presets'][p]['chance']) for p in given)
    return {'hc_total': len(overlay['explicit_classes']), 'hc_parity': parity, 'hc_missing': missing,
            'kit_rows': len(chance), 'kit_presets': len(emitted), 'kit_chance': chance}


def plan_lines(report, events, kits=None):
    """The two describe/plan lines. expected_extra_items assumes each active infected event holds its
    nominal count of infected spread by child weight (the stock budget); it is an expectation, not a cap."""
    lines = []
    if kits is not None:
        expected = Decimal(0)
        for event in events.values():
            if not event.get('name', '').startswith('Infected') or (event.findtext('active') or '').strip() != '1':
                continue
            children = event.findall('./children/child')
            total = sum(int(c.get('min')) for c in children)
            if total <= 0:
                continue
            nominal = int(event.findtext('nominal') or 0)
            expected += sum(Decimal(nominal * int(c.get('min'))) * report['kit_chance'].get(c.get('type'), 0)
                            for c in children) / total
        lines.append('infected kits rows=%d presets=%d expected_extra_items~%d'
                     % (report['kit_rows'], report['kit_presets'], int(expected.to_integral_value())))
    lines.append('hc_children parity=%d/%d missing=%d' % (report['hc_parity'], report['hc_total'], report['hc_missing']))
    return lines


def _overlay(policy):
    # Keep authored install data in the already-packaged/fingerprinted policy.
    overlay = policy.get('accessories')
    if not isinstance(overlay, dict) or overlay.get('schema_version') != 1:
        raise ValueError('missing or invalid authored accessory policy')
    return economy.encode(overlay)


def install(mission, stock_events=None, off=False, season=None):
    """Write the optional-overlays style backup receipt before the atomic switch."""
    if off:
        return rollback(mission)
    mission = mission_target(mission)
    managed = safe(mission / MANAGED)
    if managed.exists():
        receipt = check(mission)
        if season is not None and receipt.get('season') != season:
            raise ValueError('infected variety is installed for season ' + str(receipt.get('season'))
                             + '; rollback first to install for ' + season)
        return receipt
    policy_bytes = read(POLICY)
    policy = json.loads(policy_bytes)
    original = read(mission / TARGET)
    if not policy['production_enabled']:
        raise ValueError('infected variety policy is disabled')
    if stock_events is None:
        # Habitat owns other events; validate only its events backup here.
        # Other layers may legitimately own gameplay/core files by this point.
        from tools.package.optional_overlays import BUNDLE_MANAGED
        bundle_receipt = safe(mission / BUNDLE_MANAGED / 'receipt.json')
        stock = original
        if bundle_receipt.exists():
            baseline = json.loads(read(bundle_receipt, 128 * 1024 * 1024))
            if baseline.get('schema') != 1 or not isinstance(baseline.get('files'), dict):
                raise ValueError('invalid bundle receipt for infected stock')
            row = baseline['files'].get(TARGET)
            if row is not None:
                stock = base64.b64decode(row['before'], validate=True)
                if (economy.sha(stock) != row['before_sha256']
                        or economy.sha(original) not in {row['before_sha256'], row['after']}):
                    raise ValueError('bundle events backup/mission drift')
    else:
        stock = read(Path(stock_events))
    result = substitute(original, stock, policy, season)
    originals, results = {TARGET: original}, {TARGET: result}
    overlay_bytes, kits_bytes, presets_bytes, lines = None, None, None, []
    if enabled(policy, 'EnableAccessories'):
        overlay_bytes = _overlay(policy)
        originals[SPAWNABLE] = read(mission / SPAWNABLE)
        presets_bytes = read(mission / PRESETS)
        kits = _kits(policy) if kits_enabled(policy) else None
        built = build(originals[SPAWNABLE], presets_bytes, json.loads(overlay_bytes), kits)
        results[SPAWNABLE] = built['spawn']
        if kits is not None:
            kits_bytes = economy.encode(kits)
            originals[PRESETS], results[PRESETS] = presets_bytes, built['presets']
        lines = plan_lines(built['report'], _events(result), kits)
    receipt = {'schema': 1, 'kind': 'HC-14-infected-variety', 'runtime_acceptance': 'PENDING',
               'season': season, 'stock_events_sha256': economy.sha(stock), 'policy_sha256': economy.sha(policy_bytes),
               'accessory_policy_sha256': economy.sha(overlay_bytes) if overlay_bytes is not None else None,
               'kits_policy_sha256': economy.sha(kits_bytes) if kits_bytes is not None else None,
               'generator': GENERATOR_VERSION,
               'files': {name: {'before': base64.b64encode(data).decode('ascii'),
                                 'before_sha256': economy.sha(data), 'after': economy.sha(results[name])}
                         for name, data in originals.items()}}
    # Plan both files before writing anything; persist all backups before either switch.
    for name, data in originals.items():
        if read(mission / name) != data:
            raise ValueError('mission drift during planning: ' + name)
    if presets_bytes is not None and read(mission / PRESETS) != presets_bytes:
        raise ValueError('random presets drift during planning')
    managed.mkdir()
    atomic(managed / 'receipt.json', economy.encode(receipt), managed)
    for name, data in results.items():
        atomic(mission / name, data, managed)
    _summary(policy, lines)
    return receipt


def _backups(receipt):
    if (not isinstance(receipt, dict) or type(receipt.get('schema')) is not int
            or receipt['schema'] != 1 or receipt.get('kind') != 'HC-14-infected-variety'
            or not isinstance(receipt.get('files'), dict)
            or set(receipt['files']) not in ({TARGET}, {TARGET, SPAWNABLE}, {TARGET, SPAWNABLE, PRESETS})):
        raise ValueError('invalid infected variety receipt')
    backups = {}
    for name, row in receipt['files'].items():
        if (not isinstance(row, dict) or set(row) != {'before', 'before_sha256', 'after'}
                or not isinstance(row.get('before'), str)
                or any(not isinstance(row.get(k), str) or not economy.HEX64.fullmatch(row[k])
                       for k in ('before_sha256', 'after'))):
            raise ValueError('invalid infected variety backup receipt')
        before = base64.b64decode(row['before'], validate=True)
        if economy.sha(before) != row['before_sha256']:
            raise ValueError('infected variety backup drift')
        backups[name] = before
    return backups


def _summary(policy, lines=()):
    # Install-time levers have no runtime script hook; retain these lines in install logs.
    for line in lines:
        print(line)
    for event, coverage in sorted(policy.get('ce_pose_coverage', {}).items()):
        print('[HC Variety] ce_variants phase=install event=' + event
              + ' rows=' + str(coverage['rows']) + ' weight=' + str(coverage['weight'])
              + '/' + str(coverage['stock_weight']) + ' population_delta=0 runtime=PENDING')
    for lever, switch in (('composition_ce', 'EnableComposition'), ('accessories', 'EnableAccessories'), ('kits', 'EnableKits')):
        print('[HC Variety] ' + lever + ' enabled=' + str(int(enabled(policy, switch)))
              + ' phase=install restart_required=1 runtime=PENDING')


def check(mission):
    """Read-only integrity/policy check; an interrupted switch refuses reinstall."""
    mission = mission_target(mission)
    managed = safe(mission / MANAGED)
    economy.preflight_managed(managed, {'receipt.json', '.next'})
    receipt = json.loads(read(managed / 'receipt.json', 64 * 1024 * 1024))
    _backups(receipt)
    policy = json.loads(read(POLICY))
    expected = {TARGET, SPAWNABLE} if enabled(policy, 'EnableAccessories') else {TARGET}
    if kits_enabled(policy):
        expected.add(PRESETS)
    kits_sha = economy.sha(economy.encode(_kits(policy))) if PRESETS in expected else None
    if (receipt.get('policy_sha256') != economy.sha(read(POLICY))
            or set(receipt['files']) != expected
            or (SPAWNABLE in expected and receipt.get('accessory_policy_sha256') != economy.sha(_overlay(policy)))
            or receipt.get('kits_policy_sha256') != kits_sha
            or receipt.get('generator') != GENERATOR_VERSION):
        raise ValueError('infected variety receipt/policy mismatch; rollback first')
    if SPAWNABLE in expected and PRESETS not in expected and economy.sha(read(mission / PRESETS)) != json.loads(_overlay(policy))['stock_presets_sha256']:
        raise ValueError('infected variety random presets drift; rollback first')
    for name, row in receipt['files'].items():
        if economy.sha(read(mission / name)) != row['after']:
            raise ValueError('infected variety receipt/mission drift; rollback first')
    _summary(policy)
    return receipt


def rollback(mission):
    """Preflight every file before restoration; interrupted multi-file switches recover."""
    mission = mission_target(mission)
    managed = safe(mission / MANAGED)
    if not managed.exists():
        return []
    if not managed.is_dir():
        raise ValueError('managed receipt directory required')
    economy.preflight_managed(managed, {'receipt.json', '.next'})
    receipt_path = managed / 'receipt.json'
    if not receipt_path.exists():
        policy = json.loads(read(POLICY))
        current = _events(read(mission / TARGET))
        if (mission / SPAWNABLE).exists() and ACCESSORY_MARKER in read(mission / SPAWNABLE):
            raise ValueError('infected variety receipt missing; accessories modified; reconcile before rollback')
        if (mission / PRESETS).exists() and KIT_MARKER in read(mission / PRESETS):
            raise ValueError('infected variety receipt missing; kit presets modified; reconcile before rollback')
        for row in policy['substitutions']:
            if row.get('existing_destination', False):
                continue
            event = current.get(row['event'])
            if event is not None and any(c.get('type') == row['to'] for c in event.findall('./children/child')):
                raise ValueError('infected variety receipt missing; target modified; reconcile '
                                 + TARGET + ' against stock before rollback')
        shutil.rmtree(managed)
        return []
    with economy.refuse_missing(managed):
        receipt = json.loads(read(receipt_path, 64 * 1024 * 1024))
        backups = _backups(receipt)
        # Never restore the first file before discovering drift in the second.
        for name, row in receipt['files'].items():
            if economy.sha(read(mission / name)) not in {row['before_sha256'], row['after']}:
                raise ValueError('infected variety mission drift; reconcile before rollback: ' + name)
        for name, before in backups.items():
            atomic(mission / name, before, managed)
    shutil.rmtree(managed)
    return list(backups)


def _requested_season(args):
    if args.season_profile is not None:
        season = season_from_profile(args.season_profile)
        print('[HC Variety] season=' + str(season) + ' source=profile phase=install restart_required=1 runtime=PENDING')
        return season
    return args.season


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    apply = sub.add_parser('install', help='stopped isolated mission only; runtime acceptance pending')
    apply.add_argument('--mission', type=Path, required=True)
    apply.add_argument('--stock-events', type=Path, help='pristine events matching policy pin; default: validated bundle backup or current file')
    apply.add_argument('--off', action='store_true', help='restore receipt backup byte for byte')
    choose = apply.add_mutually_exclusive_group()
    choose.add_argument('--season', choices=SEASONS, help='restart-bound seasonal placement for this season')
    choose.add_argument('--season-profile', type=Path, help='server profile directory; the season comes from its persisted visual-seasons clock')
    undo = sub.add_parser('rollback')
    undo.add_argument('--mission', type=Path, required=True)
    preview = sub.add_parser('dry-run', help='report child counts without writing the mission')
    preview.add_argument('--mission', type=Path, required=True)
    preview.add_argument('--stock-events', type=Path, required=True)
    pick = preview.add_mutually_exclusive_group()
    pick.add_argument('--season', choices=SEASONS)
    pick.add_argument('--season-profile', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'dry-run':
            policy = json.loads(read(POLICY))
            original = read(args.mission / TARGET)
            season = _requested_season(args)
            result = substitute(original, read(args.stock_events), policy, season)
            before, after = _events(original), _events(result)
            palette = [r['event'] for r in policy.get('palette_rebalance', {}).get('transfers', []) + season_transfers(policy, season)]
            for name in sorted({r['event'] for r in policy['substitutions']} | (set(palette) if enabled(policy, 'EnableComposition') else set())):
                old, new = before[name].findall('./children/child'), after[name].findall('./children/child')
                print(name + ': children=' + str(len(old)) + '->' + str(len(new))
                      + ' shares=' + str(sum(int(c.get('min')) for c in old)) + '->'
                      + str(sum(int(c.get('min')) for c in new)))
            lines = []
            if enabled(policy, 'EnableAccessories'):
                kits = _kits(policy) if kits_enabled(policy) else None
                built = build(read(args.mission / SPAWNABLE), read(args.mission / PRESETS), json.loads(_overlay(policy)), kits)
                lines = plan_lines(built['report'], after, kits)
            _summary(policy, lines)
            print('HC-14 dry-run; population_delta=0; runtime=PENDING')
            return
        if args.command == 'install':
            install(args.mission, args.stock_events, args.off, _requested_season(args))
        else:
            rollback(args.mission)
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + '\n')
    print('HC-14 ' + ('restored/off' if args.command == 'rollback' or args.off else 'installed') + '; runtime=PENDING')


if __name__ == '__main__':
    main()
