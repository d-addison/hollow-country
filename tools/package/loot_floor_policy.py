"""Floor loot policy: prefer clothing and trash on floors; move other classes to compatible shelves where capacity permits.

Owner direction 2026-11-19: apart from some clothes and garbage, items should not spawn on floors. The CE places a
type only where a container lists its category and, when the type carries tags, where a container carries one of them
(stock rows already use the ``floor`` and ``shelves`` tags that way). This module is the data-driven version of that
rule, applied at install time by ``loot_boost.plan`` on the operator's own installed mission bytes; nothing from the
vanilla files is shipped:

* ``retag_types``: every building-loot type (nominal > 0, category in ``shelf_categories``, not a firearm-roster class)
  that is not floor eligible (clothing category, a listed class or a listed class pattern) loses its ``floor`` tag and
  gains ``shelves``. Eligible classes and every other row keep their exact bytes.
* ``rebalance_proto``: containers on the floor (named in ``floor_container_names``, or named in
  ``height_checked_container_names`` with every point within ``floor_band_m`` of the group's lowest point) lose the
  ``shelves`` tag, so shelf-only classes cannot use them. The floor slots those classes used (container lootmax times
  the displaced share of the nominal they could draw) move to the same building's shelf containers, never above the
  container's point count or ``max_container_lootmax``; the remainder is reported as unplaced, never invented.
  A floor container that no shelf of its building can take keeps its stock tags (loot stays about equal), except
  the boost's own extra floor containers (``extra_floor_container_names``), which are extras on top of stock and
  convert even without replacement room: their shelf-only share is reported unplaced. Floors needed by a global
  stock fallback retain eligibility, including extra floors, and are reported as retained.

Placement is resolved before type restrictions: any class needed by a retained stock floor keeps its original tags
globally. Receiver allocation conservatively requires compatibility with every displaced class, including usage.
Transfers subtract the displaced slots from floor maxima, leave group maxima intact, and report group-bounded
usable capacity.

Every limit is a named field of ``mission/hollow-country/loot-points/floor-policy.json`` (``enabled`` is the operator
opt-out). Offline only: whether the CE honours the rewritten tags and the resulting shelf density stay pending a native
server session (runtime=PENDING).
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
        'shelf_categories', 'floor_tag', 'shelf_tag', 'floor_container_names', 'height_checked_container_names', 'extra_floor_container_names',
        'floor_band_m', 'capacity'}
CAPACITY_KEYS = {'enabled', 'max_container_lootmax', 'preserve_tolerance'}
KEPT = frozenset({'weapons', 'explosives', 'lootdispatch'})
SHELF_CATEGORY_CHOICES = frozenset({'tools', 'containers', 'food', 'books'})
FLOOR_BAND_RANGE = (0.1, 3.0)
MAX_CONTAINER_LOOTMAX = 40
MAX_LIST = 256


def _names(value, what):
    if (not isinstance(value, list) or len(value) > MAX_LIST
            or any(not isinstance(v, str) or not NAME.fullmatch(v) for v in value)):
        raise ValueError(f'floor policy {what} must be a bounded list of plain names')
    return list(value)


def parse_policy(data):
    """Validated policy dict (patterns compiled under ``_patterns``); refuses unknown or unbounded values."""
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
    if set(floor_categories) & KEPT or not set(shelf_categories) <= SHELF_CATEGORY_CHOICES:
        raise ValueError('floor policy may not move weapons, explosives or dispatch rows')
    if set(floor_categories) & set(shelf_categories):
        raise ValueError('a category cannot be both floor and shelf')
    patterns = doc['floor_class_patterns']
    if not isinstance(patterns, list) or len(patterns) > MAX_LIST or any(
            not isinstance(p, str) or not 1 <= len(p) <= 80 for p in patterns):
        raise ValueError('floor policy patterns must be a bounded list of short strings')
    try:
        compiled = [re.compile(p) for p in patterns]
    except re.error as error:
        raise ValueError(f'floor policy pattern does not compile: {error}') from None
    for key in ('floor_tag', 'shelf_tag'):
        if not isinstance(doc[key], str) or not NAME.fullmatch(doc[key]):
            raise ValueError(f'floor policy {key} must be a plain name')
    _names(doc['floor_classes'], 'floor_classes')
    _names(doc['floor_container_names'], 'floor_container_names')
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
    doc['_patterns'] = compiled
    doc['_classes'] = {c.lower() for c in doc['floor_classes']}
    return doc


def shipped_policy(repo=None):
    """Committed policy bytes, or None when this tree does not carry the file (the plain boost then applies)."""
    path = Path(repo or loot_boost.REPO_ROOT) / FLOOR_POLICY
    return path.read_bytes() if path.is_file() else None


def floor_eligible(name, category, policy):
    """True for clothing, listed trash classes and listed class patterns; the data decides, never script."""
    if category in policy['floor_categories'] or name.lower() in policy['_classes']:
        return True
    return any(p.search(name) for p in policy['_patterns'])


# ------------------------------------------------------------------------------------------------ types

_TAG = re.compile(r'<tag\s+name="([^"]*)"\s*/>')


def retag_types(data, policy, roster=frozenset(), preserve=frozenset()):
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
        movable = (cats and set(cats) <= set(policy['shelf_categories']) and not set(cats) & KEPT
                   and name.lower() not in roster and value > 0
                   and not floor_eligible(name, cats[0], policy))
        if movable and name not in preserve:
            after = [t for t in tags if t != floor_tag]
            if shelf_tag not in after:
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
    """{name: (category, tags_before, tags_after, nominal, usage)}; later files win like a loaded override."""
    table = {}
    for rows in rows_by_file:
        for name, cats, before, after, nominal, usages in rows:
            if cats:
                table[name] = (cats[0], frozenset(before), frozenset(after), nominal, frozenset(usages))
    return table


# ------------------------------------------------------------------------------------------------ prototype


def _accepted(table, cats, tags, which):
    """Nominal a container can draw: category listed, and a tagged row needs a shared tag (CE matching model)."""
    total = 0
    for category, before, after, nominal, usages in table.values():
        if category not in cats or category in KEPT:
            continue
        row_tags = before if which == 'before' else after
        if not row_tags or row_tags & tags:
            total += nominal
    return total


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
    if container['name'] in policy['floor_container_names']:
        return True
    if container['name'] in policy['height_checked_container_names'] and container['ys']:
        return max(container['ys']) <= group_floor + policy['floor_band_m']
    return False


def _floor_tag_edits(masked, container, floor_tag, shelf_tag):
    start, end = container['body']
    body = masked[start:end]
    edits = []
    found = list(_TAG.finditer(body))
    for m in found:
        if m.group(1) == shelf_tag:
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


def rebalance_proto(data, rows_by_file, policy, preserve=None):
    """Return (bytes, report): floor containers become floor only and their displaced slots move to shelves."""
    preserve = set() if preserve is None else preserve
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
              'slots_before': 0, 'slots_after': 0}
    edits = []
    for gname, group_max, containers in _scan(text, masked, default_lootmax):
        report['slots_before'] += min(group_max, sum(min(c['lootmax'], len(c['ys'])) for c in containers))
        ys = [y for c in containers for y in c['ys']]
        group_floor = min(ys) if ys else 0.0
        floors, shelves = [], []
        for c in containers:
            if c['cats'] <= KEPT:
                continue
            if _is_floor(c, group_floor, policy):
                floors.append(c)
            elif shelf_tag in c['tags'] and c['cats'] & set(policy['shelf_categories']):
                shelves.append(c)
        room = [max(0, min(len(c['ys']), cap['max_container_lootmax']) - c['lootmax']) if cap['enabled'] else 0
                for c in shelves]
        gained = [0] * len(shelves)
        for c in floors:
            tags_after = {t for t in c['tags'] if t != shelf_tag} | {floor_tag}
            before = _accepted(table, c['cats'], frozenset(c['tags']), 'before')
            after = _accepted(table, c['cats'], frozenset(tags_after), 'after')
            if before <= 0:
                continue  # draws nothing from the types: no slots to displace, nothing to rewrite
            report['floor_containers'] += 1
            share = (before - after) / before
            slots = min(c['lootmax'], len(c['ys']), group_max)  # the CE never spawns more than the container has points
            need = int(math.floor(slots * share + 0.5))
            report['floor_nonclothing_slots_before'] += slots * share
            displaced_names = {name for name, (cat, old, new, nominal, usages) in table.items()
                               if nominal > 0 and cat in c['cats'] and (not old or old & set(c['tags']))
                               and new and not new & tags_after}
            # A replacement must admit every displaced row; otherwise retain the stock floor.
            # This deliberately conservative allocation cannot count a books-only slot for a tool.
            compatible = [all(table[name][0] in receiver['cats']
                              and (not table[name][2] or table[name][2] & set(receiver['tags']))
                              and (not table[name][4] or not receiver['usages']
                                   or table[name][4] & receiver['usages'])
                              for name in displaced_names) for receiver in shelves]
            free = sum(r - g for r, g, ok in zip(room, gained, compatible) if ok)
            extra = c['name'] in policy['extra_floor_container_names']  # added by the boost: never above stock
            unavailable = displaced_names and not any(
                ok and receiver['lootmax'] + available > 0
                for receiver, available, ok in zip(shelves, room, compatible))
            if displaced_names & preserve or (not extra and (unavailable or
                    (need and free < need - int(need * cap['preserve_tolerance'])))):
                preserve.update(displaced_names)
                report['kept_without_shelf_room'] += 1  # no shelf to take them: this floor keeps its stock tags
                report['floor_nonclothing_slots_after'] += slots * share
                continue
            report['converted'] += 1
            if sorted(tags_after) != sorted(c['tags']):
                report['tags_rewritten'] += 1
                edits.extend(_floor_tag_edits(masked, c, floor_tag, shelf_tag))
            placed = 0
            while placed < need and any(ok and r > g for r, g, ok in zip(room, gained, compatible)):
                for index in range(len(shelves)):
                    if compatible[index] and placed < need and gained[index] < room[index]:
                        gained[index] += 1
                        placed += 1
            if need:
                edits.append((c['open'][0], c['open'][1],
                              loot_boost._with_lootmax(c['tag_open'], c['lootmax'] - need)))
            report['displaced'] += need
            report['transferred'] += placed
            report['unplaced'] += need - placed
        for c, gain in zip(shelves, gained):
            if gain:
                edits.append((c['open'][0], c['open'][1], loot_boost._with_lootmax(c['tag_open'], c['lootmax'] + gain)))
    for key in ('floor_nonclothing_slots_before', 'floor_nonclothing_slots_after'):
        report[key] = round(report[key], 2)
    output = loot_boost._encode(loot_boost._apply(text, edits), data)
    output_text = output.decode('utf-8-sig')
    report['slots_after'] = sum(min(limit, sum(min(c['lootmax'], len(c['ys'])) for c in containers))
                                for _, limit, containers in _scan(output_text, loot_boost._mask(output_text),
                                                                  default_lootmax))
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
            'displaced_slots=%d moved_to_shelves=%d unplaced=%d floor_nonclothing_slots %.1f->%.1f runtime=PENDING '
            '(CE honouring the rewritten tags is unobserved until a native server session)'
            % (report.get('retagged_types', 0), report['floor_containers'], report['converted'],
               report['kept_without_shelf_room'], report['displaced'], report['transferred'], report['unplaced'],
               report['floor_nonclothing_slots_before'], report['floor_nonclothing_slots_after']))
