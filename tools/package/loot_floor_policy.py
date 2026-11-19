"""Strict clothing/exact-garbage floor admission, applied to operator-owned CE files.

Equipment (including firearms) loses floor eligibility regardless of spare shelf
capacity. Existing raised shelf containers receive displaced capacity only when
category, tag and usage agree, within their point count and the configured cap.
Nominal/min, group maxima and physical coordinates are never invented. Unmatched
finite demand is recorded in the install receipt rather than restored to floors
or duplicated into Search. Counts are offline CE estimates, runtime=PENDING.
The policy is enabled by default with floor-policy.json enabled=false opt-out.
"""
import json
import math
from pathlib import Path
import re
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.package import economy, loot_boost  # noqa: E402

FLOOR_POLICY = Path('mission/hollow-country/loot-points/floor-policy.json')
KIND = 'hollow-country-loot-floor-policy'
MAX_POLICY_BYTES = 64 * 1024
NAME = re.compile(r'[A-Za-z0-9_]{1,80}')
KEYS = {'schema', 'kind', 'enabled', 'note', 'floor_categories', 'floor_classes', 'floor_class_patterns',
        'shelf_categories', 'floor_tag', 'shelf_tag', 'floor_container_names', 'floor_container_tags', 'height_checked_container_names', 'extra_floor_container_names',
        'floor_band_m', 'capacity'}
CAPACITY_KEYS = {'enabled', 'max_container_lootmax', 'preserve_tolerance'}
SHELF_CATEGORY_CHOICES = frozenset({'tools', 'containers', 'food', 'books', 'weapons', 'explosives', 'lootdispatch'})
FLOOR_BAND_RANGE = (0.1, 3.0)
MAX_CONTAINER_LOOTMAX = 40
MAX_LIST = 256


def _names(value, what):
    if (not isinstance(value, list) or len(value) > MAX_LIST
            or any(not isinstance(v, str) or not NAME.fullmatch(v) for v in value)):
        raise ValueError(f'floor policy {what} must be a bounded list of plain names')
    return list(value)


def parse_policy(data):
    """Validated exact-class policy; refuses unknown or unbounded values."""
    if len(data) > MAX_POLICY_BYTES:
        raise ValueError('floor policy exceeds its byte bound')
    doc = json.loads(data)
    if (not isinstance(doc, dict) or not set(doc) <= KEYS or doc.get('schema') != 1 or doc.get('kind') != KIND
            or type(doc.get('enabled')) is not bool):
        raise ValueError('not a loot floor policy')
    if not KEYS - {'note'} <= set(doc):
        raise ValueError('floor policy is missing a named field')
    floor_categories = _names(doc['floor_categories'], 'floor_categories')
    shelf_categories = _names(doc['shelf_categories'], 'shelf_categories')
    if not set(floor_categories) <= {'clothes'} or not set(shelf_categories) <= SHELF_CATEGORY_CHOICES:
        raise ValueError('floor categories must be clothing; equipment belongs on shelves')
    if set(floor_categories) & set(shelf_categories):
        raise ValueError('a category cannot be both floor and shelf')
    patterns = doc['floor_class_patterns']
    if not isinstance(patterns, list) or len(patterns) > MAX_LIST or any(
            not isinstance(p, str) or not 1 <= len(p) <= 80 for p in patterns):
        raise ValueError('floor policy patterns must be a bounded list of short strings')
    if patterns:
        raise ValueError('garbage eligibility requires exact class names, not patterns')
    for key in ('floor_tag', 'shelf_tag'):
        if not isinstance(doc[key], str) or not NAME.fullmatch(doc[key]):
            raise ValueError(f'floor policy {key} must be a plain name')
    _names(doc['floor_classes'], 'floor_classes')
    _names(doc['floor_container_names'], 'floor_container_names')
    _names(doc['floor_container_tags'], 'floor_container_tags')
    if doc['floor_tag'] == doc['shelf_tag']:
        raise ValueError('floor and shelf tags must differ')
    _names(doc['height_checked_container_names'], 'height_checked_container_names')
    if not set(_names(doc['extra_floor_container_names'], 'extra_floor_container_names')) <= set(
            doc['floor_container_names']):
        raise ValueError('extra floor containers must also be floor containers')
    band = doc['floor_band_m']
    if (isinstance(band, bool) or not isinstance(band, (int, float)) or not math.isfinite(band)
            or not FLOOR_BAND_RANGE[0] <= band <= FLOOR_BAND_RANGE[1]):
        raise ValueError('floor_band_m outside its range')
    cap = doc['capacity']
    if not isinstance(cap, dict) or set(cap) != CAPACITY_KEYS or type(cap['enabled']) is not bool:
        raise ValueError('floor policy capacity block shape')
    top, tol = cap['max_container_lootmax'], cap['preserve_tolerance']
    if (type(top) is not int or not 1 <= top <= MAX_CONTAINER_LOOTMAX or isinstance(tol, bool)
            or not isinstance(tol, (int, float)) or not math.isfinite(tol) or not 0.0 <= tol <= 0.5):
        raise ValueError('floor policy capacity bounds')
    doc['_classes'] = {c.lower() for c in doc['floor_classes']}
    return doc


def shipped_policy(repo=None):
    """Committed policy bytes, or None when this tree does not carry the file (the plain boost then applies)."""
    path = Path(repo or loot_boost.REPO_ROOT) / FLOOR_POLICY
    return path.read_bytes() if path.is_file() else None


def floor_eligible(name, category, policy):
    """Only clothing and explicitly named garbage may retain floor eligibility."""
    return category in policy['floor_categories'] or name.lower() in policy['_classes']


# ------------------------------------------------------------------------------------------------ types

_TAG = re.compile(r'<tag\s+name="([^"]*)"\s*/>')


def retag_types(data, policy, roster=frozenset()):
    """Return (bytes, rows). rows: (name, categories, tags_before, tags_after, nominal, usage)."""
    economy.xml(data, 'types')
    text = data.decode('utf-8-sig')
    masked = loot_boost._mask(text)
    edits, rows, expected = [], [], {}
    floor_tag, shelf_tag = policy['floor_tag'], policy['shelf_tag']
    for opening in re.finditer(r'<type\b[^>]*>', masked):
        if opening.group(0).endswith('/>'):
            continue
        close = masked.find('</type>', opening.end())
        if close < 0:
            raise ValueError('unclosed type row')
        name = loot_boost._attr(opening.group(0), 'name') or ''
        body = masked[opening.end():close]
        cats = re.findall(r'<category\s+name="([^"]*)"', body)
        tags = [m.group(1) for m in _TAG.finditer(body)]
        nominal = re.search(r'<nominal>\s*(\d+)\s*</nominal>', body)
        value = int(nominal.group(1)) if nominal else 0
        after = list(tags)
        # Roster membership protects supply quantities, never equipment floor placement.
        movable = ((bool(cats) or floor_tag in tags or value > 0)
                   and not all(floor_eligible(name, category, policy) for category in (cats or [''])))
        if movable:
            after = [t for t in tags if t != floor_tag]
            if (floor_tag in tags or not tags) and shelf_tag not in after:
                after.append(shelf_tag)
            if sorted(after) != sorted(tags):
                edits.extend(_retag_edits(masked, opening.end(), body, tags, floor_tag, shelf_tag))
                expected[name] = set(after)
        usages = tuple(re.findall(r'<usage\s+name="([^"]*)"', body))
        rows.append((name, tuple(cats), tuple(tags), tuple(after), value, usages))
    output = loot_boost._encode(loot_boost._apply(text, edits), data)
    _verify_retag(data, output, expected)
    return output, rows


def _retag_edits(masked, base, body, tags, floor_tag, shelf_tag):
    found = list(_TAG.finditer(body))
    floor = next((m for m in found if m.group(1) == floor_tag), None)
    has_shelf = shelf_tag in tags
    if floor is not None and not has_shelf:
        start, end = base + floor.start(), base + floor.end()
        return [(start, end, floor.group(0).replace('name="%s"' % floor_tag, 'name="%s"' % shelf_tag))]
    if floor is not None:
        start = base + floor.start()
        while start > base and masked[start - 1] in ' \t':
            start -= 1
        if start > base and masked[start - 1] == '\n':
            start -= 1
            if start > base and masked[start - 1] == '\r':
                start -= 1
        return [(start, base + floor.end(), '')]
    last = list(re.finditer(r'<category\s+name="[^"]*"\s*/>', body))
    if not last:
        # Uncategorized stock rows still must not gain unrestricted floor eligibility.
        return [(base, base, '<tag name="%s"/>' % shelf_tag)]
    anchor = last[-1]
    line = body.rfind('\n', 0, anchor.start())
    lead = body[line + 1:anchor.start()] if line >= 0 else ''
    eol = '\r\n' if '\r\n' in body else '\n'
    spaced = ' />' if anchor.group(0).endswith(' />') else '/>'
    element = '<tag name="%s"%s' % (shelf_tag, spaced)
    insert = (eol + lead + element) if (line >= 0 and not lead.strip()) else element
    return [(base + anchor.end(), base + anchor.end(), insert)]


def _verify_retag(before, after, expected):
    old, new = economy.xml(before, 'types'), economy.xml(after, 'types')
    rows_old, rows_new = old.findall('type'), new.findall('type')
    if [t.get('name') for t in rows_old] != [t.get('name') for t in rows_new]:
        raise ValueError('floor policy verification failed: row order changed')
    for a, b in zip(rows_old, rows_new):
        name = a.get('name')
        strip = ('tag',) if name in expected else ()
        shape = lambda t: [(c.tag, sorted(c.attrib.items()), (c.text or '').strip())
                           for c in t if c.tag not in strip]
        if shape(a) != shape(b) or a.attrib != b.attrib:
            raise ValueError(f'floor policy verification failed: {name} changed beyond its tags')
        if name in expected and {t.get('name') for t in b.findall('tag')} != expected[name]:
            raise ValueError(f'floor policy verification failed: {name} tags')


def type_table(rows_by_file):
    """{name: (categories, tags_before, tags_after, nominal, usage)}; later files win like a loaded override."""
    table = {}
    for rows in rows_by_file:
        for name, cats, before, after, nominal, usages in rows:
            table[name] = (frozenset(cats), frozenset(before), frozenset(after), nominal, frozenset(usages))
    return table


# ------------------------------------------------------------------------------------------------ prototype


def _matches(row, container, which):
    categories, before, after, nominal, usages = row
    tags = before if which == 'before' else after
    return (nominal > 0 and bool(categories & container['cats'])
            and (not tags or bool(tags & set(container['tags'])))
            and (not usages or not container['usages'] or bool(usages & container['usages'])))


def _scan(text, masked, default_lootmax):
    """Per group: list of container dicts with offsets, from the (comment-masked) prototype text."""
    groups = []
    default_group = next((d.get('lootmax') for d in economy.xml(text.encode(), 'prototype').iter('default')
                          if d.get('name') == 'group'), '0')
    for group in re.finditer(r'<group\b[^>]*>', masked):
        if group.group(0).endswith('/>'):
            continue  # a self-closing group has no containers
        close = masked.find('</group>', group.end())
        if close < 0:
            raise ValueError('unclosed prototype group')
        gname = loot_boost._attr(group.group(0), 'name') or ''
        group_body = masked[group.end():close]
        group_prefix = group_body.split('<container', 1)[0]
        group_usages = set(re.findall(r'<usage\s+name="([^"]*)"', group_prefix))
        containers = []
        for opening in re.finditer(r'<container\b[^>]*>', masked[group.end():close]):
            tag_open = opening.group(0)
            if tag_open.endswith('/>'):
                continue
            start = group.end() + opening.start()
            end_body = masked.find('</container>', start)
            if end_body < 0 or end_body > close:
                raise ValueError('unclosed prototype container')
            body = masked[start + len(tag_open):end_body]
            lootmax = loot_boost._attr(tag_open, 'lootmax')
            ys = []
            for p in re.finditer(r'<point\b[^>]*>', body):
                pos = loot_boost._attr(p.group(0), 'pos')
                try:
                    ys.append(float(pos.split()[1]))
                except (AttributeError, IndexError, ValueError):
                    continue
            containers.append({
                'name': loot_boost._attr(tag_open, 'name') or '', 'open': (start, start + len(tag_open)),
                'body': (start + len(tag_open), end_body), 'tag_open': tag_open,
                'lootmax': int(lootmax) if lootmax is not None and lootmax.isdigit() else default_lootmax,
                'usages': {m.group(1) for m in re.finditer(r'<usage\s+name="([^"]*)"', body)} or group_usages,
                'cats': {m.group(1) for m in re.finditer(r'<category\s+name="([^"]*)"', body)},
                'tags': [m.group(1) for m in _TAG.finditer(body)], 'ys': ys})
        group_max = loot_boost._attr(group.group(0), 'lootmax')
        groups.append((gname, int(group_max if group_max is not None else default_group or 0), containers))
    return groups


def _is_floor(container, group_floor, policy):
    # Mixed floor/shelf tags are not evidence that all points are raised surfaces.
    if (container['name'] in policy['floor_container_names']
            or set(container['tags']) & set(policy['floor_container_tags'])):
        return True
    if container['name'] in policy['height_checked_container_names'] and container['ys']:
        return min(container['ys']) <= group_floor + policy['floor_band_m']
    return False


def _floor_tag_edits(masked, container, floor_tag, shelf_tag):
    start, end = container['body']
    body = masked[start:end]
    edits = []
    found = list(_TAG.finditer(body))
    for m in found:
        if m.group(1) != floor_tag:
            cut = start + m.start()
            while cut > start and masked[cut - 1] in ' \t':
                cut -= 1
            if cut > start and masked[cut - 1] == '\n':
                cut -= 1
                if cut > start and masked[cut - 1] == '\r':
                    cut -= 1
            edits.append((cut, start + m.end(), ''))
    if floor_tag not in container['tags']:
        cats = list(re.finditer(r'<category\s+name="[^"]*"\s*/>', body))
        if cats:
            anchor = cats[-1]
            line = body.rfind('\n', 0, anchor.start())
            lead = body[line + 1:anchor.start()] if line >= 0 else ''
            eol = '\r\n' if '\r\n' in body else '\n'
            spaced = ' />' if anchor.group(0).endswith(' />') else '/>'
            element = '<tag name="%s"%s' % (floor_tag, spaced)
            insert = (eol + lead + element) if (line >= 0 and not lead.strip()) else element
            edits.append((start + anchor.end(), start + anchor.end(), insert))
    return edits


def rebalance_proto(data, rows_by_file, policy):
    """Strict floor tags plus bounded shelf transfers; receipt includes per-class supply gaps.

    Slots are allocated to displaced classes by nominal-weighted largest remainder,
    then to compatible existing shelf points. This is a finite capacity estimate,
    not a promise of CE counts, distribution or native geometry qualification.
    """
    economy.xml(data, 'prototype')
    text = data.decode('utf-8-sig')
    masked = loot_boost._mask(text)
    block = re.search(r'<default\b[^>]*\bname="container"[^>]*>', masked)
    default_lootmax = int(loot_boost._attr(block.group(0), 'lootmax') or 0) if block else 0
    table = type_table(rows_by_file)
    floor_tag, shelf_tag = policy['floor_tag'], policy['shelf_tag']
    cap = policy['capacity']
    report = {'enabled': True, 'floor_containers': 0, 'converted': 0, 'kept_without_shelf_room': 0,
              'tags_rewritten': 0, 'displaced': 0, 'transferred': 0, 'unplaced': 0,
              'floor_nonclothing_slots_before': 0.0, 'floor_nonclothing_slots_after': 0.0,
              'slots_before': 0, 'slots_after': 0, 'supply': {}, 'supply_gaps': {}}
    supply = report['supply']
    for name, row in sorted(table.items()):
        if row[3] > 0 and not all(floor_eligible(name, category, policy) for category in (row[0] or {''})):
            supply[name] = {'nominal': row[3], 'compatible_shelf_points': 0,
                            'displaced_slot_estimate': 0.0, 'requested_slots': 0,
                            'transferred_slots': 0, 'unplaced_slots': 0,
                            'groups_without_receiver': []}
    edits = []
    for gname, group_max, containers in _scan(text, masked, default_lootmax):
        report['slots_before'] += min(group_max, sum(min(c['lootmax'], len(c['ys'])) for c in containers))
        ys = [y for c in containers for y in c['ys']]
        group_floor = min(ys) if ys else 0.0
        floors, shelves = [], []
        for c in containers:
            if _is_floor(c, group_floor, policy):
                floors.append(c)
            elif shelf_tag in c['tags']:
                shelves.append(c)
        room = [max(0, min(len(c['ys']), cap['max_container_lootmax']) - c['lootmax']) if cap['enabled'] else 0
                for c in shelves]
        gained = [0] * len(shelves)
        compatible = {name: [i for i, receiver in enumerate(shelves) if _matches(table[name], receiver, 'after')]
                      for name in supply}
        for name, indexes in compatible.items():
            if group_max > 0:
                supply[name]['compatible_shelf_points'] += sum(
                    min(len(shelves[i]['ys']), shelves[i]['lootmax'] + room[i]) for i in indexes)
        for c in floors:
            report['floor_containers'] += 1
            report['converted'] += 1
            if set(c['tags']) != {floor_tag}:
                report['tags_rewritten'] += 1
                edits.extend(_floor_tag_edits(masked, c, floor_tag, shelf_tag))
            accepted = {name: row for name, row in table.items() if _matches(row, c, 'before')}
            before = sum(row[3] for row in accepted.values())
            displaced = sorted(name for name in accepted if name in supply)
            if not before or not displaced:
                continue
            slots = min(c['lootmax'], len(c['ys']), group_max)
            estimates = {name: slots * table[name][3] / before for name in displaced}
            estimate = sum(estimates.values())
            need = min(slots, int(math.floor(estimate + 0.5)))
            requests = {name: int(math.floor(estimates[name])) for name in displaced}
            order = sorted(displaced, key=lambda name: (-(estimates[name] - requests[name]), name))
            for name in order[:need - sum(requests.values())]:
                requests[name] += 1
            report['floor_nonclothing_slots_before'] += estimate
            placed = 0
            # Most constrained demand first; no slot can be transferred twice.
            for name in sorted(displaced, key=lambda name: (len(compatible[name]), name)):
                record = supply[name]
                record['displaced_slot_estimate'] += estimates[name]
                record['requested_slots'] += requests[name]
                indexes = compatible[name]
                if not any(shelves[i]['lootmax'] + room[i] > 0 and shelves[i]['ys'] for i in indexes):
                    if gname not in record['groups_without_receiver']:
                        record['groups_without_receiver'].append(gname)
                remaining = requests[name]
                for index in indexes:
                    transfer = min(remaining, room[index] - gained[index])
                    gained[index] += transfer
                    remaining -= transfer
                    placed += transfer
                    record['transferred_slots'] += transfer
                    if not remaining:
                        break
                record['unplaced_slots'] += remaining
            if need:
                edits.append((c['open'][0], c['open'][1],
                              loot_boost._with_lootmax(c['tag_open'], c['lootmax'] - need)))
            report['displaced'] += need
            report['transferred'] += placed
            report['unplaced'] += need - placed
        for c, gain in zip(shelves, gained):
            if gain:
                edits.append((c['open'][0], c['open'][1], loot_boost._with_lootmax(c['tag_open'], c['lootmax'] + gain)))
    for name, record in supply.items():
        record['displaced_slot_estimate'] = round(record['displaced_slot_estimate'], 4)
        if record['unplaced_slots'] or record['groups_without_receiver'] or not record['compatible_shelf_points']:
            report['supply_gaps'][name] = record
    for key in ('floor_nonclothing_slots_before', 'floor_nonclothing_slots_after'):
        report[key] = round(report[key], 2)
    output = loot_boost._encode(loot_boost._apply(text, edits), data)
    output_text = output.decode('utf-8-sig')
    after_groups = _scan(output_text, loot_boost._mask(output_text), default_lootmax)
    report['slots_after'] = sum(min(limit, sum(min(c['lootmax'], len(c['ys'])) for c in containers))
                                for _, limit, containers in after_groups)
    for _, limit, containers in after_groups:
        floor_y = min((y for c in containers for y in c['ys']), default=0.0)
        for c in containers:
            if not _is_floor(c, floor_y, policy):
                continue
            accepted_after = {name: row for name, row in table.items() if _matches(row, c, 'after')}
            total = sum(row[3] for row in accepted_after.values())
            prohibited = sum(row[3] for name, row in accepted_after.items() if name in supply)
            if total:
                report['floor_nonclothing_slots_after'] += min(limit, c['lootmax'], len(c['ys'])) * prohibited / total
    if report['floor_nonclothing_slots_after']:
        raise ValueError('floor policy verification failed: equipment can still use a floor container')
    _verify_proto(data, output, report, policy)
    return output, report


def _verify_proto(before, after, report, policy):
    old, new = economy.xml(before, 'prototype'), economy.xml(after, 'prototype')
    groups_old, groups_new = old.findall('group'), new.findall('group')
    if [g.get('name') for g in groups_old] != [g.get('name') for g in groups_new]:
        raise ValueError('floor policy verification failed: group order changed')
    gain = 0
    removed = 0
    for a, b in zip(groups_old, groups_new):
        if a.attrib != b.attrib:
            raise ValueError('floor policy verification failed: group attributes changed')
        cs_old, cs_new = a.findall('container'), b.findall('container')
        if len(cs_old) != len(cs_new):
            raise ValueError('floor policy verification failed: container count changed')
        for x, y in zip(cs_old, cs_new):
            same = (x.get('name') == y.get('name')
                    and [(c.tag, sorted(c.attrib.items())) for c in x if c.tag in ('category', 'point', 'usage')]
                    == [(c.tag, sorted(c.attrib.items())) for c in y if c.tag in ('category', 'point', 'usage')])
            if not same:
                raise ValueError('floor policy verification failed: container content changed')
            tags_new = {t.get('name') for t in y.findall('tag')}
            tags_old = {t.get('name') for t in x.findall('tag')}
            if not tags_new <= tags_old | {policy['floor_tag']}:
                raise ValueError('floor policy verification failed: unexpected tag')
            lm_old = x.get('lootmax')
            lm_new = y.get('lootmax')
            if lm_old != lm_new:
                delta = int(lm_new) - (int(lm_old) if lm_old is not None else _default(old))
                gain += max(0, delta)
                removed += max(0, -delta)
    if report['displaced'] != report['transferred'] + report['unplaced']:
        raise ValueError('floor policy verification failed: displaced supply accounting')
    if gain != report['transferred'] or removed != report['displaced']:
        raise ValueError('floor policy verification failed: transferred lootmax does not match the edits')


def _default(root):
    for d in root.iter('default'):
        if d.get('name') == 'container' and (d.get('lootmax') or '').isdigit():
            return int(d.get('lootmax'))
    return 0


def describe(report):
    """One admission/status line; honest that nothing was observed in DayZ."""
    if not report.get('enabled'):
        return 'floor policy disabled (floor-policy.json enabled=false or file absent): plain loot boost'
    return ('floor policy retagged_types=%d floor_containers=%d converted=%d kept_without_shelf_room=%d '
            'displaced_slots=%d moved_to_shelves=%d unplaced=%d floor_nonclothing_slots %.1f->%.1f '
            '(CE honouring the rewritten tags is unobserved until a native server session)'
            % (report.get('retagged_types', 0), report['floor_containers'], report['converted'],
               report['kept_without_shelf_room'], report['displaced'], report['transferred'], report['unplaced'],
               report['floor_nonclothing_slots_before'], report['floor_nonclothing_slots_after'])
            + ' supply_gap_classes=%d runtime=PENDING' % len(report.get('supply_gaps', {})))
