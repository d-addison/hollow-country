"""Deterministic loot-family detection and the loot balance rules (owner 2026-11-22).

A family is a name stem plus an explicit override table (tools/package/loot_families.json): colour words are
removed from a class name, so every colour of a model is one family. The rules work on plain {class: nominal}
data, never on files, so loot_boost, military_loot and the tests share one engine:

  R1   a class or family holds at most max(3% of its category, 2 x its stock share);
  R2b  every family totals at least 3;
  R3   a colour family totals at most ceil(1.5 x its largest variant) (every variant keeps at least 1);
  R4   at least 1.5 ammo and 1.0 magazines per gun, per calibre / magazine pool.

Nominal that R1 and R3 free is re-invested in the same category: pass 1 in the families below the category median,
pass 2 (a share of what is still unspent, not for PASS2_SKIP categories) in every family, proportionally to its total.
Offline numbers only: nothing here establishes spawning behaviour in DayZ.
"""
from functools import lru_cache
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
TABLE = 'tools/package/loot_families.json'
R3_CATEGORIES = frozenset({'weapons', 'clothes', 'containers', 'tools', 'attachments'})
PASS2_SKIP = frozenset({'weapons'})  # hard to place: the nominal R1/R3 free there is not handed back in pass 2
_WORD = re.compile(r'[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+')


def load_table(root=None):
    path = Path(root or ROOT) / TABLE
    doc = json.loads(path.read_bytes())
    if doc.get('schema') != 1 or not isinstance(doc.get('colours'), list) or not isinstance(doc.get('overrides'), dict):
        raise ValueError('invalid loot family table')
    return doc


@lru_cache(maxsize=8)
def _vocabulary(root):
    doc = load_table(root)
    colours = {c.lower() for c in doc['colours']}
    modifiers = {m.lower() for m in doc.get('modifiers', [])}
    overrides = {k.lower(): v for k, v in doc['overrides'].items()}
    return frozenset(colours), frozenset(modifiers), overrides


def _decomposes(token, words, base):
    """True when the lowercase token is a concatenation of words with at least one base colour word."""
    token = token.lower()
    reach = {0: False}  # position -> whether the words so far use a base colour; absent = unreachable
    for i in range(len(token)):
        if i not in reach:
            continue
        for word in words:
            if token.startswith(word, i):
                flag = reach[i] or word in base
                reach[i + len(word)] = reach.get(i + len(word), False) or flag
    return reach.get(len(token), False)


def _is_colour(token, colours, modifiers):
    if token.lower() in colours or token.lower() in modifiers:
        return True
    return _decomposes(token, colours | modifiers, colours)


def family(name, root=None):
    """The family stem of a class name: explicit override, else the name without its colour tokens."""
    root = str(Path(root or ROOT))
    colours, modifiers, overrides = _vocabulary(root)
    if name.lower() in overrides:
        return overrides[name.lower()]
    tokens = name.split('_')
    keep = [t for t in tokens if not _is_colour(t, colours, modifiers)]
    if keep and keep[-1] == tokens[-1] and len(tokens[-1]) > 3:
        last = keep[-1]
        for match in _WORD.finditer(last):
            i = match.start()
            if i >= 3 and _is_colour(last[i:], colours, modifiers):
                keep[-1] = last[:i]
                break
    return '_'.join(keep) or name


def split(weights, total):
    """Integer shares of total, proportional to weights (a list of (name, weight)); each share is at least 1.

    Largest remainder, ties by name, so the result is deterministic. total below the member count is raised to it."""
    names = sorted(weights, key=lambda item: item[0])
    total = max(total, len(names))
    weight_sum = sum(max(w, 0) for _, w in names) or len(names)
    shares, order = {}, []
    spare = total - len(names)
    for name, weight in names:
        exact = spare * (max(weight, 0) if sum(max(w, 0) for _, w in names) else 1) / weight_sum
        shares[name] = 1 + int(exact)
        order.append((-(exact - int(exact)), name))
    left = total - sum(shares.values())
    for _, name in sorted(order)[:left]:
        shares[name] += 1
    return shares


def _families(rows, names):
    groups = {}
    for name in names:
        groups.setdefault(family(rows[name].get('name', name)), []).append(name)
    return {key: sorted(members) for key, members in groups.items()}


def _total(rows, members, current):
    return sum(current[m] for m in members)


def balance(rows, r3=R3_CATEGORIES, k=1.5, floor=3, share=0.03, stock_factor=2.0, pass2_share=1.0,
            pass2_skip=PASS2_SKIP, slack=None, slack_share=0.5):
    """Apply R3, R1, the re-investment and R2b to {class: {category, nominal, stock, locked}}.

    Locked rows keep their nominal (they count in totals only). Rows with nominal 0 are never touched. Returns
    ({class: new nominal} for every changed class, report {category: {...}}). Only nominal changes; callers rescale
    min. Deterministic: ordering is by name."""
    current = {n: r['nominal'] for n, r in rows.items()}
    # capacity table: {'bucket': {id: spare nominal}, 'class': {lowercase class: bucket id}}; slack_share of each
    # bucket's spare capacity may be handed out (buckets share containers, so the full figure overstates it)
    left = None if slack is None else {b: int(v * slack_share) for b, v in slack['bucket'].items()}
    bucket_of = {} if slack is None else {n: slack['class'].get(n.lower()) for n in rows}
    report = {}
    by_cat = {}
    for name, row in rows.items():
        if row['nominal'] > 0 and row['category']:
            by_cat.setdefault(row['category'], []).append(name)
    for category in sorted(by_cat):
        names = by_cat[category]
        free = [n for n in names if not rows[n].get('locked')]
        groups = _families(rows, names)
        stock_total = sum(rows[n].get('stock', 0) for n in names) or 1
        info = {'r3_freed': 0, 'r1_freed': 0, 'reinvested': 0, 'reinvested2': 0, 'floored': 0, 'unspent': 0}
        freed = 0

        def shrink(members, target, group):
            """Shrink the unlocked members of a group to a total of at most target; returns the nominal freed."""
            nonlocal current
            unlocked = [m for m in members if not rows[m].get('locked')]
            fixed = sum(current[m] for m in members if rows[m].get('locked'))
            allowed = max(target - fixed, len(unlocked))
            if not unlocked or sum(current[m] for m in unlocked) <= allowed:
                return 0
            before = sum(current[m] for m in unlocked)
            shares = split([(m, current[m]) for m in unlocked], allowed)
            for m in unlocked:
                current[m] = min(current[m], shares[m])
            return before - sum(current[m] for m in unlocked)

        if category in r3:
            for key, members in groups.items():
                if len(members) > 1:
                    largest = max(current[m] for m in members)
                    freed += shrink(members, int(math.ceil(round(k * largest, 6))), key)
            info['r3_freed'] = freed
        for _ in range(4):
            total = sum(current[n] for n in names)
            r1 = 0
            for key, members in groups.items():
                cap = lambda m: int(math.floor(max(share, stock_factor * rows[m].get('stock', 0) / stock_total) * total))
                for m in members:
                    if not rows[m].get('locked') and current[m] > max(cap(m), 1):
                        r1 += current[m] - max(cap(m), 1)
                        current[m] = max(cap(m), 1)
                if len(members) > 1:
                    family_cap = max(1, int(math.floor(max(share, stock_factor * sum(rows[m].get('stock', 0)
                                                                                     for m in members) / stock_total) * total)))
                    r1 += shrink(members, family_cap, key)
            freed += r1
            info['r1_freed'] += r1
            if not r1:
                break
        # re-invest into the families below the category median, up to the median
        totals = {key: sum(current[m] for m in members) for key, members in groups.items()}
        ordered = sorted(totals.values())
        median = ordered[len(ordered) // 2] if ordered else 0
        total = sum(current[n] for n in names)

        def room_of(key):
            """Nominal the family can still take where the feasibility graph has spare capacity (None: no table)."""
            if left is None:
                return None
            members = [m for m in groups[key] if not rows[m].get('locked')]
            return sum(left.get(b, 0) for b in {bucket_of.get(m) for m in members if bucket_of.get(m) is not None})

        def give(key, add):
            """Add nominal to the unlocked variants of a family, proportionally to their size (and, with a capacity
            table, never past what their bucket still holds); returns the nominal given."""
            unlocked = [m for m in groups[key] if not rows[m].get('locked')]
            if left is None:
                shares = split([(m, current[m]) for m in unlocked], sum(current[m] for m in unlocked) + add)
                for m in unlocked:
                    current[m] = shares[m]
                return add
            given = 0
            for _ in range(4):
                want = add - given
                eligible = [m for m in unlocked if left.get(bucket_of.get(m), 0) > 0]
                weight = sum(current[m] for m in eligible)
                if want <= 0 or not eligible or weight <= 0:
                    break
                parts = sorted(eligible, key=lambda m: (-(want * current[m] % weight), m))
                base = {m: want * current[m] // weight for m in eligible}
                for m in parts[:want - sum(base.values())]:
                    base[m] += 1
                for m in sorted(eligible):
                    amount = min(base[m], left[bucket_of[m]])
                    if amount > 0:
                        current[m] += amount
                        left[bucket_of[m]] -= amount
                        given += amount
            return given

        room = {}
        for key, members in groups.items():
            unlocked = [m for m in members if not rows[m].get('locked')]
            if not unlocked or totals[key] >= median:
                continue
            limit = median
            if len(members) > 1 and category in r3:
                limit = min(limit, int(math.ceil(round(k * max(current[m] for m in members), 6))))
            share_cap = max(share, stock_factor * sum(rows[m].get('stock', 0) for m in members) / stock_total)
            limit = min(limit, int(math.floor(share_cap * total)))
            if left is not None:
                limit = min(limit, totals[key] + room_of(key))
            if limit > totals[key]:
                room[key] = (totals[key], limit)
        spend = 0
        if freed and room:
            lo, hi = 0, max(limit for _, limit in room.values())
            need = lambda level: sum(max(0, min(level, limit) - base) for base, limit in room.values())
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if need(mid) <= freed:
                    lo = mid
                else:
                    hi = mid - 1
            gain = {key: max(0, min(lo, limit) - base) for key, (base, limit) in room.items()}
            left_over = freed - sum(gain.values())
            for key in sorted(room, key=lambda x: (room[x][0] + gain[x], x)):
                if left_over <= 0:
                    break
                if room[key][0] + gain[key] < room[key][1]:
                    gain[key] += 1
                    left_over -= 1
            for key, add in sorted(gain.items()):
                if add:
                    spend += give(key, add)
        info['reinvested'] = spend
        # pass 2: the still-unspent nominal goes to every family of the category, within the R1 cap and the R3
        # colour budget (measured on the largest variant as it stands now). Without a capacity table it is
        # proportional to the family total; with one it goes only where the feasibility graph
        # has spare capacity, weighted by that slack and recomputed each round. Only pass2_share of the unspent nominal
        # is handed back (the owner's total band); categories in pass2_skip (hard to
        # place) get nothing back and report the nominal as unspent.
        leftover = freed - spend
        if category in pass2_skip:
            leftover = 0
        leftover = min(leftover, int(math.floor(leftover * pass2_share + 1e-9)))
        spend2 = 0
        if leftover > 0:
            total = sum(current[n] for n in names) + leftover
            limits = {}
            for key, members in groups.items():
                unlocked = [m for m in members if not rows[m].get('locked')]
                if not unlocked:
                    continue
                limit = int(math.floor(max(share, stock_factor * sum(rows[m].get('stock', 0) for m in members)
                                           / stock_total) * total))
                if len(members) > 1 and category in r3:
                    limit = min(limit, int(math.ceil(round(k * max(current[m] for m in members), 6))))
                have = sum(current[m] for m in members)
                if limit > have:
                    limits[key] = limit - have
            gain = dict.fromkeys(limits, 0)
            for _ in range(12):
                pool = leftover - spend2
                if pool <= 0:
                    break
                open_keys = [key for key in sorted(limits) if gain[key] < limits[key]]
                if left is not None:
                    open_keys = [key for key in open_keys if room_of(key) > 0]
                if not open_keys:
                    break
                if left is None:
                    weight = {key: sum(current[m] for m in groups[key]) for key in open_keys}
                    cap = {key: limits[key] - gain[key] for key in open_keys}
                else:
                    weight = {key: room_of(key) for key in open_keys}
                    cap = {key: min(limits[key] - gain[key], weight[key]) for key in open_keys}
                weight_sum = sum(weight.values())
                grant = {key: min(cap[key], int(pool * weight[key] / weight_sum)) for key in open_keys}
                if not any(grant.values()):
                    # fewer units than families: hand them out one at a time, largest weight first
                    for key in sorted(open_keys, key=lambda x: (-weight[x], x))[:pool]:
                        grant[key] = 1
                moved = 0
                for key in open_keys:
                    if grant[key]:
                        added = give(key, grant[key])
                        gain[key] += added
                        moved += added
                spend2 += moved
                if not moved:
                    break
        info['reinvested2'] = spend2
        info['unspent'] = freed - spend - spend2
        # R2b: every family totals at least `floor`
        for key, members in groups.items():
            unlocked = [m for m in members if not rows[m].get('locked')]
            have = sum(current[m] for m in members)
            if unlocked and have < floor:
                current[unlocked[0]] += floor - have
                info['floored'] += floor - have
        report[category] = info
    changed = {n: v for n, v in current.items() if v != rows[n]['nominal']}
    return changed, report


def base_ammo(name):
    """Ammo pool class of a row: a box or a tracer counts toward its plain cartridge class."""
    match = re.match(r'AmmoBox_(.*?)_?\d+[Rr]nd$', name)
    if match:
        name = 'Ammo_' + {'00buck': '12gaPellets'}.get(match.group(1), match.group(1))
    return re.sub(r'Tracer$', '', name)


def pools(edges):
    """Connected pools of {gun: [resource]}: [(guns, resources)]; guns sharing a resource share a pool."""
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for gun, resources in sorted(edges.items()):
        for resource in resources:
            parent[find(('g', gun))] = find(('r', resource))
    comps = {}
    for gun, resources in sorted(edges.items()):
        if resources:
            guns, found = comps.setdefault(find(('g', gun)), ([], set()))
            guns.append(gun)
            found.update(resources)
    return [(guns, sorted(found)) for _, (guns, found) in sorted(comps.items(), key=lambda kv: min(kv[1][0]))]


def _raise_pool(demand, supply, required, rows_of):
    """Water-fill the least supplied classes of one pool; returns {row: added}."""
    classes = sorted(c for c in demand if demand[c] > 0 and rows_of.get(c))
    added = {}
    current = {c: supply.get(c, 0) for c in classes}
    deficit = required - sum(supply.get(c, 0) for c in demand)
    guard = 0
    while deficit > 0 and classes and guard < 100000:
        guard += 1
        order = sorted(classes, key=lambda c: (current[c] / demand[c], c))
        low = order[0]
        nxt = current[order[1]] / demand[order[1]] if len(order) > 1 else float('inf')
        want = deficit if nxt == float('inf') else max(1, int(math.ceil(demand[low] * nxt - current[low] + 1e-9)))
        step = min(deficit, want)
        current[low] += step
        deficit -= step
        row = rows_of[low]
        added[row] = added.get(row, 0) + step
    return added


def support_floors(guns, ammo, magazines, ammo_ratio=1.5, magazine_ratio=1.0, raisable=None):
    """R4: raises ({row: added nominal}, report) so every ammo pool holds at least ammo_ratio units per gun and
    every magazine pool at least magazine_ratio.

    guns {class: {'nominal': n, 'ammo': [...], 'magazines': [...]}}; ammo and magazines are {row: nominal} of the rows
    that exist (the caller decides what is an ammo or a magazine row). A pool is a set of guns sharing a cartridge
    (boxes and tracers fold into the plain cartridge) or a magazine class; a gun's nominal is split evenly over the
    classes it accepts. Pools without any existing row are reported, never invented. raisable (a set of rows,
    default all) limits which rows may be raised; the others still count as supply."""
    added, report = {}, {'ammo_pools': 0, 'magazine_pools': 0, 'raised_ammo': 0, 'raised_magazines': 0, 'no_row': []}
    live = {g: d for g, d in guns.items() if d['nominal'] > 0}
    for kind, ratio, supply in (('ammo', ammo_ratio, ammo), ('magazines', magazine_ratio, magazines)):
        edges = {g: sorted({base_ammo(a) if kind == 'ammo' else a for a in d.get(kind, [])}) for g, d in live.items()}
        have = {}
        rows_of = {}
        for row, nominal in supply.items():
            cls = base_ammo(row) if kind == 'ammo' else row
            have[cls] = have.get(cls, 0) + nominal
            if raisable is not None and row not in raisable:
                continue
            best = rows_of.get(cls)
            if best is None or (row == cls) or (best != cls and nominal > supply[best]):
                rows_of[cls] = row
        for members, classes in pools(edges):
            guns_total = sum(live[g]['nominal'] for g in members)
            demand = {}
            for g in members:
                if edges[g]:
                    for c in edges[g]:
                        demand[c] = demand.get(c, 0) + live[g]['nominal'] / len(edges[g])
            report[kind + '_pools' if kind == 'ammo' else 'magazine_pools'] += 1
            required = int(math.ceil(round(ratio * guns_total, 6)))
            raise_by = _raise_pool(demand, have, required, rows_of)
            if not any(rows_of.get(c) for c in demand):
                report['no_row'].append(sorted(classes)[0])
            for row, add in raise_by.items():
                added[row] = added.get(row, 0) + add
                report['raised_' + kind] += add
    return added, report
