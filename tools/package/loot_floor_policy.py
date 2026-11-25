"""Strict clothing/exact-garbage floor admission, applied to operator-owned CE files.

Equipment uses evidence-indexed native shelf and raised/platform points. Native
coordinates are relocated rather than duplicated. Displaced capacity transfers to
compatible receivers locally, then across native usage-compatible groups. Exact
Military group exceptions admit at most two weapon slots where no raised route is
evidenced. Nominal/min and coordinates are never invented; group maxima are clamped
to physical capacity. Bulky Motorbike lootdispatch wheels retain native routes. Unmatched
finite demand and exceptions remain explicit in the install receipt. Counts are offline CE estimates, runtime=PENDING.
The policy is enabled by default with floor-policy.json enabled=false opt-out.
"""
import json
import math
from pathlib import Path
import re
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.package import economy, loot_boost, xml_text  # noqa: E402

FLOOR_POLICY = Path('mission/hollow-country/loot-points/floor-policy.json')
KIND = 'hollow-country-loot-floor-policy'
MAX_POLICY_BYTES = 256 * 1024
NAME = re.compile(r'[A-Za-z0-9_]{1,80}')
KEYS = {'schema', 'kind', 'enabled', 'note', 'floor_categories', 'floor_classes', 'floor_class_patterns',
        'shelf_categories', 'floor_tag', 'shelf_tag', 'floor_container_names', 'floor_container_tags', 'height_checked_container_names', 'extra_floor_container_names',
        'floor_band_m', 'capacity', 'receivers', 'collision_support'}
CAPACITY_KEYS = {'enabled', 'max_container_lootmax', 'preserve_tolerance'}
SHELF_CATEGORY_CHOICES = frozenset({'tools', 'containers', 'food', 'books', 'weapons', 'explosives', 'lootdispatch'})
FLOOR_BAND_RANGE = (0.1, 3.0)
MAX_CONTAINER_LOOTMAX = 40
MAX_LIST = 256


def supported_nominal(record):
    """Conservative supply bound for an unfulfilled floor-to-shelf allocation.

    Compatible points are shared, not an entitlement for each class. Restrict
    nominal to the fulfilled fraction of requested slots as well as that point
    ceiling. This estimate is frozen before the final supply cap so a receipt
    retains the evidence that caused the cut.
    """
    requested = record['requested_slots']
    return min(record['compatible_shelf_points'],
               record['nominal'] * max(0, requested - record['unplaced_slots']) // max(1, requested))


def _names(value, what):
    if (not isinstance(value, list) or len(value) > MAX_LIST
            or any(not isinstance(v, str) or not NAME.fullmatch(v) for v in value)):
        raise ValueError(f'floor policy {what} must be a bounded list of plain names')
    return list(value)


def validate_collision_support(value):
    """Open-structure exemptions for the loot support audit (shipped with the bundle)."""
    if (not isinstance(value, dict) or set(value) != {'open_structure_prefixes', 'open_structure_classes', 'note'}
            or not isinstance(value['note'], str) or not value['note']):
        raise ValueError('collision_support policy shape')
    for key in ('open_structure_prefixes', 'open_structure_classes'):
        if (not isinstance(value[key], list) or len(value[key]) > 256
                or any(not isinstance(n, str) or not loot_boost.NAME.fullmatch(n) for n in value[key])):
            raise ValueError('collision_support policy names')
    return value


def parse_policy(data):
    """Validated exact-class policy; refuses unknown or unbounded values."""
    if len(data) > MAX_POLICY_BYTES:
        raise ValueError('floor policy exceeds its byte bound')
    doc = json.loads(data, object_pairs_hook=loot_boost._unique_object)
    if (not isinstance(doc, dict) or not set(doc) <= KEYS or doc.get('schema') != 1 or doc.get('kind') != KIND
            or type(doc.get('enabled')) is not bool):
        raise ValueError('not a loot floor policy')
    if not KEYS - {'note', 'receivers', 'collision_support'} <= set(doc):
        raise ValueError('floor policy is missing a named field')
    if 'collision_support' in doc:
        validate_collision_support(doc['collision_support'])
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
    receivers = doc.setdefault('receivers', {})
    if not isinstance(receivers, dict) or len(receivers) > 256:
        raise ValueError('floor policy receivers must be a bounded group map')
    for group, spec in receivers.items():
        if (not NAME.fullmatch(group) or not isinstance(spec, dict)
                or set(spec) != {'evidence', 'sources', 'widen', 'floor_exception'}
                or not isinstance(spec['evidence'], str) or not 1 <= len(spec['evidence']) <= 1200):
            raise ValueError('floor policy receiver evidence shape')
        _names(spec['widen'], 'receiver containers')
        if not isinstance(spec['sources'], dict) or len(spec['sources']) > 8:
            raise ValueError('floor policy receiver sources shape')
        for cname, points in spec['sources'].items():
            if not NAME.fullmatch(cname) or not isinstance(points, list) or len(points) > 256:
                raise ValueError('floor policy receiver points bound')
            if any(not isinstance(point, str) for point in points):
                raise ValueError('receiver source point must be native xyz text')
            if len(set(points)) != len(points):
                raise ValueError('duplicate receiver source point')
            for point in points:
                if not isinstance(point, str):
                    raise ValueError('receiver source point must be native xyz text')
                loot_boost._point([float(v) for v in point.split()])
        exception = spec['floor_exception']
        if exception is not None:
            if (not isinstance(exception, dict) or set(exception) != {'source', 'points', 'max_slots', 'reason'}
                    or not NAME.fullmatch(str(exception['source']))
                    or not isinstance(exception['points'], list)
                    or type(exception['max_slots']) is not int or not 1 <= exception['max_slots'] <= 2
                    or len(exception['points']) != exception['max_slots']
                    or not isinstance(exception['reason'], str) or not 1 <= len(exception['reason']) <= 500):
                raise ValueError('floor policy military weapon exception bounds')
            if any(not isinstance(point, str) for point in exception['points']):
                raise ValueError('exception point must be native xyz text')
            for point in exception['points']:
                loot_boost._point([float(v) for v in point.split()])
            if len(set(exception['points'])) != len(exception['points']):
                raise ValueError('duplicate exception point')
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


def _shelf_exempt(name, categories):
    # Vehicle wheels retain their native Industrial/garage routes and quantities.
    # A category-wide lootdispatch exemption would also bypass small equipment.
    return ('lootdispatch' in categories
            and re.fullmatch(r'Motorbike_[A-Za-z0-9_]+_Wheel_[A-Za-z0-9_]+', name, re.I) is not None)


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
        movable = (not _shelf_exempt(name, cats) and (bool(cats) or floor_tag in tags or value > 0)
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
                'group': gname, 'name': loot_boost._attr(tag_open, 'name') or '', 'open': (start, start + len(tag_open)),
                'body': (start + len(tag_open), end_body), 'tag_open': tag_open,
                'lootmax': int(lootmax) if lootmax is not None and lootmax.isdigit() else default_lootmax,
                'usages': {m.group(1) for m in re.finditer(r'<usage\s+name="([^"]*)"', body)} or group_usages,
                'cats': {m.group(1) for m in re.finditer(r'<category\s+name="([^"]*)"', body)},
                'tags': [m.group(1) for m in _TAG.finditer(body)], 'ys': ys})
        group_max = loot_boost._attr(group.group(0), 'lootmax')
        groups.append((gname, int(group_max if group_max is not None else default_group or 0), containers))
    return groups


def _is_floor(container, group_floor, policy):
    spec = policy.get('receivers', {}).get(container.get('group'), {})
    if container['name'] in spec.get('sources', {}):
        return True  # native source remainder; its evidenced raised points are relocated after allocation
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


SURFACE_RECEIVER = 'lootHCReceiver'
WEAPON_EXCEPTION = 'lootHCWeaponException'


def provision_receivers(data, policy):
    """Stage exact native points for transfer. Sources remain until allocation is verified.

    No invented heights or duplicate final positions: finish_receivers removes each
    staged point from its original container. Existing pure shelf containers only
    gain contextual categories. Missing source geometry refuses installation.
    """
    import copy
    import xml.etree.ElementTree as ET
    root = economy.xml(data, 'prototype')
    default_lootmax = _default(root)
    report = {'groups': {}, 'absent': [], 'surface_points': 0, 'exception_points': 0,
              'runtime_acceptance': 'pending'}
    groups = {g.get('name'): g for g in root.findall('group')}
    for name, spec in sorted(policy.get('receivers', {}).items()):
        group = groups.get(name)
        if group is None:
            report['absent'].append(name)
            continue
        existing = {c.get('name'): c for c in group.findall('container')}
        if SURFACE_RECEIVER in existing or WEAPON_EXCEPTION in existing:
            raise ValueError('receiver already present: ' + name)
        row = {'surface_points': 0, 'exception_points': 0, 'widened': [], 'relocations': [],
               'evidence': spec['evidence']}
        for cname in spec['widen']:
            c = existing.get(cname)
            if c is None or {t.get('name') for t in c.findall('tag')} - {policy['shelf_tag']}:
                raise ValueError('receiver shelf source changed: ' + name + '/' + cname)
            if not c.findall('tag'):
                ET.SubElement(c, 'tag', {'name': policy['shelf_tag']})
            cats = {c.get('name') for c in c.findall('category')}
            for cat in policy['shelf_categories']:
                if cat not in cats:
                    ET.SubElement(c, 'category', {'name': cat})
            row['widened'].append(cname)
        selections = [(SURFACE_RECEIVER, spec['sources'], policy['shelf_categories'])]
        exception = spec['floor_exception']
        if exception:
            if 'Military' not in {u.get('name') for u in group.findall('usage')}:
                raise ValueError('weapon floor exceptions require native Military usage: ' + name)
            selections.append((WEAPON_EXCEPTION, {exception['source']: exception['points']}, ['weapons']))
        used = set()
        for target, sources, categories in selections:
            receiver = ET.Element('container', {'name': target})
            source_capacity = 0
            for cat in categories:
                ET.SubElement(receiver, 'category', {'name': cat})
            ET.SubElement(receiver, 'tag', {'name': policy['shelf_tag']})
            for cname, points in sources.items():
                source = existing.get(cname)
                if source is None:
                    raise ValueError('receiver source missing: ' + name + '/' + cname)
                source_capacity += min(len(points), int(source.get('lootmax', str(default_lootmax))))
                for xyz in points:
                    found = [p for p in source.findall('point') if p.get('pos') == xyz]
                    if len(found) != 1 or xyz in used:
                        raise ValueError('receiver geometry changed or duplicated: ' + name + '/' + cname)
                    used.add(xyz)
                    receiver.append(copy.deepcopy(found[0]))
                    row['relocations'].append({'source': cname, 'pos': xyz, 'target': target})
            count = len(receiver.findall('point'))
            if count:
                # Native containers have an explicit limit or inherit the prototype
                # default. Relocating their points must not create an inert shell
                # whose admission depends on unrelated displaced demand/headroom.
                limit = min(count, policy['capacity']['max_container_lootmax'], max(1, source_capacity))
                if target == WEAPON_EXCEPTION:
                    limit = min(limit, exception['max_slots'])
                receiver.set('lootmax', str(limit))
                group.append(receiver)
                key = 'exception_points' if target == WEAPON_EXCEPTION else 'surface_points'
                row[key] += count
                report[key] += count
        report['groups'][name] = row
    return xml_text.document(root), report


def finish_receivers(data, report, policy, floor_report):
    """Remove staged source coordinates and verify the final finite geometry."""
    import xml.etree.ElementTree as ET
    root = economy.xml(data, 'prototype')
    groups = {g.get('name'): g for g in root.findall('group')}
    exception_slots = 0
    for name, row in report['groups'].items():
        group = groups[name]
        containers = {c.get('name'): c for c in group.findall('container')}
        for move in row['relocations']:
            source = containers[move['source']]
            found = [p for p in source.findall('point') if p.get('pos') == move['pos']]
            if len(found) != 1:
                raise ValueError('receiver relocation verification failed: ' + name)
            source.remove(found[0])
        for cname in (SURFACE_RECEIVER, WEAPON_EXCEPTION):
            if cname not in containers:
                continue
            c = containers[cname]
            if c.findall('point') and int(c.get('lootmax')) <= 0:
                raise ValueError('receiver has points but no capacity: ' + name + '/' + cname)
            if int(c.get('lootmax')) > len(c.findall('point')):
                raise ValueError('receiver capacity exceeds its physical points: ' + name)
            if cname == WEAPON_EXCEPTION:
                maximum = policy['receivers'][name]['floor_exception']['max_slots']
                if int(c.get('lootmax')) > maximum:
                    raise ValueError('military exception exceeds its bound: ' + name)
                exception_slots += int(c.get('lootmax'))
            # Every introduced position has exactly one final owner, including stock shelves.
            for point in c.findall('point'):
                xyz = tuple(float(v) for v in point.get('pos').split())
                count = sum(tuple(float(v) for v in p.get('pos').split()) == xyz
                            for p in group.iter('point'))
                if count != 1:
                    raise ValueError('receiver overlaps another native point: ' + name)
    introduced_names = {SURFACE_RECEIVER, WEAPON_EXCEPTION, *policy['extra_floor_container_names']}
    introduced = [c for g in root.findall('group') for c in g.findall('container')
                  if c.get('name') in introduced_names and c.findall('point')]
    zero_capacity = [c for c in introduced if int(c.get('lootmax', str(_default(root)))) <= 0]
    report['containers_after'] = len(introduced)
    report['points_after'] = sum(len(c.findall('point')) for c in introduced)
    report['zero_capacity_containers_after'] = len(zero_capacity)
    report['zero_capacity_points_after'] = sum(len(c.findall('point')) for c in zero_capacity)
    if zero_capacity:
        raise ValueError('floor policy introduced containers with points but no capacity')
    output = loot_boost._clamp_proto(xml_text.document(root))
    loot_boost._verify_proto_caps(economy.xml(output, 'prototype'))
    text = output.decode('utf-8')
    scanned = _scan(text, loot_boost._mask(text), _default(root))
    floor_report['slots_after'] = sum(min(limit, sum(min(c['lootmax'], len(c['ys'])) for c in cs))
                                    for _, limit, cs in scanned)
    floor_report['weapon_exception_slots_after'] = exception_slots
    floor_report['floor_nonclothing_slots_after'] = round(
        floor_report['floor_nonclothing_slots_after'] + exception_slots, 2)
    return output


def rebalance_proto(data, rows_by_file, policy):
    """Strict floor tags plus bounded shelf transfers; receipt includes per-class supply gaps.

    Slots are allocated to displaced classes by nominal-weighted largest remainder,
    then to compatible existing shelf points. This is a finite capacity estimate,
    not a promise of CE counts, distribution or native geometry qualification.
    """
    data = loot_boost._clamp_proto(data)
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
        if (row[3] > 0 and not _shelf_exempt(name, row[0])
                and not all(floor_eligible(name, category, policy) for category in (row[0] or {''}))):
            supply[name] = {'nominal': row[3], 'compatible_shelf_points': 0,
                            'displaced_slot_estimate': 0.0, 'requested_slots': 0,
                            'transferred_slots': 0, 'unplaced_slots': 0,
                            'groups_without_receiver': []}
    edits = []
    spare_receivers = []
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
        room = [max(0, min(len(c['ys']),
                           policy['receivers'][gname]['floor_exception']['max_slots']
                           if c['name'] == 'lootHCWeaponException' else cap['max_container_lootmax'])
                    - c['lootmax']) if cap['enabled'] else 0 for c in shelves]
        gained = [0] * len(shelves)
        compatible = {name: [i for i, receiver in enumerate(shelves) if _matches(table[name], receiver, 'after')]
                      for name in supply}
        for name, indexes in compatible.items():
            if group_max > 0:
                supply[name]['compatible_shelf_points'] += sum(
                    min(len(shelves[i]['ys']), shelves[i]['lootmax'] + room[i]) for i in indexes
                    if shelves[i]['name'] != 'lootHCWeaponException')
        removed_by_container = {}
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
            # Every added floor with points keeps a usable slot even when rounded
            # displaced demand would otherwise drain its entire small budget; #274
            # floors carry their building's own story, not only clothing, and an
            # inert receiver is refused by finish_receivers.
            reserve = int(c['name'] in policy['extra_floor_container_names'] and bool(c['ys']))
            need = min(max(0, c['lootmax'] - reserve), slots, int(math.floor(estimate + 0.5)))
            allocation = {name: estimates[name] * need / estimate if reserve and estimate else estimates[name]
                          for name in displaced}
            requests = {name: int(math.floor(allocation[name])) for name in displaced}
            order = sorted(displaced, key=lambda name: (-(allocation[name] - requests[name]), name))
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
            removed_by_container[c['name']] = need
            report['displaced'] += need
            report['transferred'] += placed
            report['unplaced'] += need - placed
        # Preserve remaining demand elsewhere within the same native CE usage.
        # Shared group headroom prevents counting receiver capacity beyond lootmax.
        spec = policy.get('receivers', {}).get(gname, {})
        moved_points = {n: len(ps) for n, ps in spec.get('sources', {}).items()}
        exception = spec.get('floor_exception')
        if exception:
            source = exception['source']
            moved_points[source] = moved_points.get(source, 0) + len(exception['points'])
        used = sum(min(c['lootmax'] - removed_by_container.get(c['name'], 0),
                       len(c['ys']) - moved_points.get(c['name'], 0)) for c in containers) + sum(gained)
        spare_receivers.append((shelves, room, gained, [max(0, group_max - used)]))
    report['transferred_between_groups'] = 0
    # Firearm routes take priority; the remaining nominal/min and category rules stay intact.
    for name in sorted(supply, key=lambda n: ('weapons' not in table[n][0], n)):
        record = supply[name]
        remaining = record['unplaced_slots']
        for shelves, room, gained, headroom in spare_receivers:
            if not remaining:
                break
            for i, c in enumerate(shelves):
                if c['name'] == WEAPON_EXCEPTION or not _matches(table[name], c, 'after'):
                    continue
                amount = min(remaining, room[i] - gained[i], headroom[0])
                gained[i] += amount
                headroom[0] -= amount
                remaining -= amount
                record['transferred_slots'] += amount
                record['unplaced_slots'] -= amount
                report['transferred'] += amount
                report['transferred_between_groups'] += amount
                report['unplaced'] -= amount
        # Local missing-receiver names remain visible even when another group receives the demand.
    for shelves, room, gained, headroom in spare_receivers:
        for c, gain in zip(shelves, gained):
            if gain:
                edits.append((c['open'][0], c['open'][1], loot_boost._with_lootmax(c['tag_open'], c['lootmax'] + gain)))
    for name, record in supply.items():
        record['displaced_slot_estimate'] = round(record['displaced_slot_estimate'], 4)
        if record['unplaced_slots'] or record['groups_without_receiver'] or not record['compatible_shelf_points']:
            report['supply_gaps'][name] = record
    for key in ('floor_nonclothing_slots_before', 'floor_nonclothing_slots_after'):
        report[key] = round(report[key], 2)
    output = loot_boost._clamp_proto(loot_boost._encode(loot_boost._apply(text, edits), data))
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
    loot_boost._verify_proto_caps(new)
    groups_old, groups_new = old.findall('group'), new.findall('group')
    if [g.get('name') for g in groups_old] != [g.get('name') for g in groups_new]:
        raise ValueError('floor policy verification failed: group order changed')
    gain = 0
    removed = 0
    for a, b in zip(groups_old, groups_new):
        attributes = dict(a.attrib)
        defaults = loot_boost._proto_defaults(new)
        capacity = sum(min(int(c.get('lootmax', str(defaults.get('container', 0)))),
                           len(c.findall('point'))) for c in b.findall('container'))
        original_limit = int(a.get('lootmax', str(defaults.get('group', 0))))
        if original_limit > capacity:
            attributes['lootmax'] = str(capacity)
        if attributes != b.attrib:
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
            'displaced_slots=%d transferred_to_receivers=%d unplaced=%d floor_nonclothing_slots %.1f->%.1f '
            '(CE honouring the rewritten tags is unobserved until a native server session)'
            % (report.get('retagged_types', 0), report['floor_containers'], report['converted'],
               report['kept_without_shelf_room'], report['displaced'], report['transferred'], report['unplaced'],
               report['floor_nonclothing_slots_before'], report['floor_nonclothing_slots_after'])
            + ' weapon_floor_exception_slots=%d supply_gap_classes=%d runtime=PENDING'
            % (report.get('weapon_exception_slots_after', 0), len(report.get('supply_gaps', {}))))
