"""Variety packs: per-class dispositions and CE rows generated from installed configs and authored rules.

Reads every pack's config members (read-only; nothing from a pack is copied) plus vanilla, applies the
ordered rules in config/variety-packs.json and writes two committed artefacts:

  * mission/hollow-country/optional/variety-types.json: CE rows per pack, applied only when that pack is loaded
    (tools/package/variety_optional.py), at 2x scarcity relative to the closest vanilla peer;
  * config/variety-dispositions.json: one explicit disposition per scope-2 class (spawn / crafted / excluded with a
    reason). A class no rule matches fails generation; nothing is silently zeroed.

Offline estimates only: no DayZ behaviour is established here (runtime=PENDING).
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys
import xml.etree.ElementTree as ET

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.audit import pbo_config as reader
from tools.package import inventory_sources, variety_optional

ROOT = Path(__file__).resolve().parents[2]
RULES = 'config/variety-packs.json'
CE_OUT = 'mission/hollow-country/optional/variety-types.json'
DISPOSITIONS_OUT = 'config/variety-dispositions.json'
FLOOR_POLICY = 'mission/hollow-country/loot-points/floor-policy.json'
OUTPUTS = (CE_OUT, DISPOSITIONS_OUT)
ROOTS = ('CfgVehicles', 'CfgWeapons', 'CfgMagazines')
FIELDS = {'scope', 'itemSize', 'inventorySlot', 'itemInfo', 'weight', 'displayName', 'varQuantityInit'}
ARRAYS = {'itemSize', 'inventorySlot', 'itemInfo'}
MATCH_KEYS = {'name', 'ancestor', 'slot', 'root', 'parent'}
RULE_KEYS = MATCH_KEYS | {'id', 'disposition', 'reason', 'peers', 'peer_slot', 'usage', 'category', 'value', 'size_check', 'extra_divisor', 'evidence', 'decision'}
DISPOSITIONS = ('spawn', 'crafted', 'excluded')
SETTINGS_KEYS = {'id', 'root', 'target', 'tokens', 'reason', 'json'}
SETTINGS_ROOTS = variety_optional.SETTINGS_ROOTS
SETTINGS_TARGET = variety_optional.SETTINGS_TARGET
EVIDENCE = ('script', 'derived')
FLAG_ORDER = ('count_in_cargo', 'count_in_hoarder', 'count_in_map', 'count_in_player', 'crafted', 'deloot')


# ------------------------------------------------------------------------------------------------ reading

def addons_dir(root):
    root = Path(root)
    for child in sorted(root.iterdir()) if root.is_dir() else ():
        if child.name.lower() == 'addons' and child.is_dir():
            return child
    return root if root.name.lower() == 'addons' else None


def _members(path, index):
    entries = sorted(index['entries'], key=lambda e: e['name'].lower())
    bins = {e['name'].lower().replace('\\', '/')[:-3] for e in entries if e['name'].lower().endswith('config.bin')}
    for entry in entries:
        member = entry['name'].lower().replace('\\', '/')
        if member.endswith('config.bin') or (member.endswith('config.cpp') and member[:-3] not in bins):
            yield entry['name']


def _rap_rows(data):
    rap = reader._Rap(data)
    _, top = rap.entries(16)
    canon = {r.lower(): r for r in ROOTS}
    out = []
    for kind, name, offset in top:
        if kind != 'class' or name.lower() not in canon:
            continue
        _, children = rap.entries(offset)
        for ck, cname, cp in children:
            if ck != 'class':
                continue
            parent, body = rap.entries(cp)
            fields, nutrition = {}, None
            for bk, bn, bv in body:
                if bk == 'value' and bn in FIELDS:
                    fields[bn] = bv
                elif bk in ('array', 'array+') and bn in ARRAYS:
                    fields[bn] = list(bv)
                elif bk == 'class' and bn == 'Nutrition':
                    _, nbody = rap.entries(bv)
                    nutrition = {a: v for nk, a, v in nbody if nk == 'value'}
            out.append((canon[name.lower()], cname, parent, fields, nutrition))
    return out


def _text_rows(data):
    _, rows = inventory_sources.text_rows(data, FIELDS)
    out = []
    for key, row in rows.items():
        root, _, name = key.rpartition('::')
        out.append((root or 'CfgVehicles', name, row['parent'], dict(row['fields']), None))
    return out


def read_configs(directory):
    """(rows, digests): {(root, name): row} merged field-wise in sorted PBO order; digests pin the config bytes."""
    rows, digests = {}, {}
    for path in sorted(Path(directory).glob('*.pbo'), key=lambda p: p.name.lower()):
        index = inventory_sources.read_index(path)
        members = {}
        for member, data in inventory_sources.iter_members(path, index, list(_members(path, index))):
            members[member] = hashlib.sha256(data).hexdigest()
            if data[:4] == b'\0raP':
                found = _rap_rows(data)
            else:
                found = _text_rows(data)
            for root, name, parent, fields, nutrition in found:
                row = rows.setdefault((root, name), {'root': root, 'name': name, 'parent': '', 'fields': {},
                                                     'nutrition': None, 'pbo': path.name})
                if parent:
                    row['parent'] = parent
                row['fields'].update(fields)
                if nutrition:
                    row['nutrition'] = nutrition
        if members:
            digests[path.name] = members
    return rows, digests


def script_tokens(directory):
    """Identifiers that appear in a pack's script members (read only, used to prove a crafted class is producible)."""
    tokens = set()
    for path in sorted(Path(directory).glob('*.pbo'), key=lambda p: p.name.lower()):
        index = inventory_sources.read_index(path)
        scripts = [e['name'] for e in index['entries'] if e['name'].lower().endswith('.c')]
        for _, data in inventory_sources.iter_members(path, index, scripts):
            tokens.update(re.findall(rb'[A-Za-z_][A-Za-z0-9_]*', data))
    return {t.decode('ascii') for t in tokens}


def provider_digest(directory):
    _, digests = read_configs(directory)
    return hashlib.sha256(json.dumps(digests, sort_keys=True).encode()).hexdigest()


def pack_directories(workshop, repo=ROOT):
    """{pack id: installed Addons directory or None} for every pack the rules name."""
    rules = Rules(json.loads((Path(repo) / RULES).read_bytes()))
    return {pack['id']: addons_dir(Path(workshop) / pack['id']) for pack in rules.packs}


def identities(addons, workshop, source, repo=ROOT):
    """Stable identities of every installed input (never paths or content), for the generated-digest receipt."""
    out = {'stock/db/types.xml': hashlib.sha256((Path(source) / 'db/types.xml').read_bytes()).hexdigest(),
           'provider/vanilla': provider_digest(addons)}
    for ident, directory in pack_directories(workshop, repo).items():
        if directory is None:
            raise FileNotFoundError('installed pack unavailable: ' + ident)
        out['provider/' + ident] = provider_digest(directory)
        out['scripts/' + ident] = hashlib.sha256('\n'.join(sorted(script_tokens(directory))).encode()).hexdigest()
    return out


def stock_types(path):
    """Stock CE rows as plain dicts keyed by class name."""
    out = {}
    for node in ET.parse(path).getroot().findall('type'):
        row = {'name': node.get('name'), 'tags': [], 'usage': [], 'value': [], 'category': None, 'flags': {}}
        for child in node:
            if child.tag in ('nominal', 'lifetime', 'restock', 'min', 'quantmin', 'quantmax', 'cost'):
                row[child.tag] = int(child.text)
            elif child.tag == 'flags':
                row['flags'] = {k: child.get(k) for k in FLAG_ORDER if child.get(k) is not None}
            elif child.tag == 'category':
                row['category'] = child.get('name')
            elif child.tag in ('tag', 'usage', 'value'):
                row[{'tag': 'tags'}.get(child.tag, child.tag)].append(child.get('name'))
        out[row['name']] = row
    return out


# ------------------------------------------------------------------------------------------------ rules

class Rules:
    def __init__(self, data):
        if data.get('schema') != 1 or data.get('kind') != 'hollow-country-variety-packs':
            raise ValueError('unknown variety rules document')
        self.data = data
        self.divisor = int(data['scarcity_divisor'])
        self.generic = set(data['generic_anchors'])
        self.nutrition = data['nutrition']
        self.size = data['size_check']
        self.crafted_lifetime = int(data['crafted_lifetime'])
        self.packs = data['packs']
        seen = set()
        for pack in self.packs:
            if pack['id'] in seen or not pack.get('licence') or not pack.get('scope'):
                raise ValueError('pack entries need a unique id, licence and scope: ' + pack.get('id', '?'))
            seen.add(pack['id'])
            ids = set()
            self._settings(pack)
            for rule in pack['rules']:
                unknown = set(rule) - RULE_KEYS
                if unknown or rule.get('disposition') not in DISPOSITIONS or rule['id'] in ids:
                    raise ValueError('invalid rule ' + str(rule.get('id')) + ' in ' + pack['id'])
                ids.add(rule['id'])
                if rule['disposition'] != 'spawn' and not rule.get('reason'):
                    raise ValueError('non-spawn rule needs a reason: ' + rule['id'])
                if rule['disposition'] == 'spawn' and rule.get('reason'):
                    raise ValueError('spawn rule must not carry an exclusion reason: ' + rule['id'])
                if (rule['disposition'] == 'crafted') != (rule.get('evidence') in EVIDENCE):
                    raise ValueError('crafted rules (and only those) need evidence script or derived: ' + rule['id'])
                if 'decision' in rule and (not isinstance(rule['decision'], str)
                                           or not re.fullmatch(r'owner_[0-9]{4}_[0-9]{2}_[0-9]{2}_[a-z0-9_]{1,80}', rule['decision'])):
                    raise ValueError('decision must record an owner decision as owner_YYYY_MM_DD_topic: ' + rule['id'])
                if rule.get('extra_divisor', 1) < 1:
                    raise ValueError('extra_divisor must be at least 1: ' + rule['id'])
                if not set(rule) & MATCH_KEYS:
                    raise ValueError('rule matches nothing: ' + rule['id'])

    @staticmethod
    def _settings(pack):
        seen = set()
        for entry in pack.get('settings_files', ()):
            if (set(entry) != SETTINGS_KEYS or entry['root'] not in SETTINGS_ROOTS or not entry['reason']
                    or not SETTINGS_TARGET.fullmatch(entry['target']) or '..' in entry['target'].split('/')
                    or not isinstance(entry['json'], dict) or not entry['json'] or entry['id'] in seen):
                raise ValueError('invalid settings file entry in ' + pack['id'] + ': ' + str(entry.get('id')))
            seen.add(entry['id'])


def json_keys(value):
    """Every object key of a JSON value, nested, as the identifiers a pack script must declare."""
    keys = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(key)
            keys |= json_keys(child)
    elif isinstance(value, list):
        for child in value:
            keys |= json_keys(child)
    return keys


def settings_rows(pack, tokens):
    """Shipped third-party settings files of one pack; each key and the file name must appear in the pack scripts."""
    rows = []
    for entry in pack.get('settings_files', ()):
        missing = sorted((json_keys(entry['json']) | set(entry['tokens'])) - tokens)
        if missing:
            raise ValueError('settings file %s has no script evidence for: %s' % (entry['id'], ', '.join(missing)))
        rows.append({'id': entry['id'], 'root': entry['root'], 'target': entry['target'],
                     'reason': entry['reason'], 'content': entry['json']})
    return rows


class Index:
    """Merged vanilla + pack rows with inheritance helpers."""

    def __init__(self, vanilla, packs):
        self.rows = dict(vanilla)
        for pack in packs:
            for key, row in pack.items():
                if key in self.rows and key not in vanilla:
                    continue
                self.rows[key] = row
        self.vanilla = set(vanilla)
        self._chains = {}

    def chain(self, key):
        found = self._chains.get(key)
        if found is None:
            out, seen, name = [], set(), key[1]
            while name and name not in seen:
                seen.add(name)
                out.append(name)
                row = self.rows.get((key[0], name))
                name = row['parent'] if row else ''
            found = self._chains[key] = out
        return found

    def eff(self, key, field):
        for name in self.chain(key):
            row = self.rows.get((key[0], name))
            if row and field in row['fields']:
                return row['fields'][field]
        return None

    def slots(self, key):
        """Effective inventory slots: inventorySlot, else the slot names after the category in itemInfo."""
        own = [s for s in _slots(self.eff(key, 'inventorySlot')) if s]
        if own:
            return own
        info = self.eff(key, 'itemInfo')
        return [str(s) for s in info[1:] if s] if isinstance(info, list) else []

    def nutrition(self, key):
        for name in self.chain(key):
            row = self.rows.get((key[0], name))
            if row and row['nutrition']:
                return row['nutrition']
        return None

    def anchor(self, key):
        for name in self.chain(key)[1:]:
            if (key[0], name) in self.vanilla:
                return name
        return None


def _slots(value):
    if value is None:
        return []
    return [value] if isinstance(value, str) else [str(v) for v in value]


def _area(value):
    if isinstance(value, list) and len(value) == 2 and all(isinstance(v, (int, float)) for v in value):
        return int(value[0]) * int(value[1])
    return None


def _matches(rule, key, index, row):
    chain = index.chain(key)
    if 'name' in rule and not re.fullmatch(rule['name'], key[1]):
        return False
    if 'root' in rule and rule['root'] != key[0]:
        return False
    if 'parent' in rule and row['parent'] != rule['parent']:
        return False
    if 'ancestor' in rule and not set(rule['ancestor']) & set(chain[1:]):
        return False
    if 'slot' in rule and not set(rule['slot']) & set(index.slots(key)):
        return False
    return True


def scope_two_classes(pack_rows, vanilla, index):
    """Classes the pack adds (not reopened vanilla names) with effective scope 2."""
    return sorted(key for key in pack_rows
                  if key not in vanilla and index.eff(key, 'scope') == 2)


def _family(stock, index, anchor, peers, slot, category):
    """(names, mode) of stock rows forming the closest vanilla peer set."""
    if peers:
        missing = [n for n in peers if n not in stock]
        if missing:
            raise ValueError('rule names peers without stock types rows: ' + ', '.join(missing))
        return sorted(peers), 'family'
    if slot:
        names = sorted(n for n, r in stock.items()
                       if ('CfgVehicles', n) in index.vanilla and r.get('category') == category
                       and slot in index.slots(('CfgVehicles', n)))
        if not names:
            raise ValueError('no stock peers for slot ' + slot)
        return names, 'mean'
    names = sorted(n for n in stock if ('CfgVehicles', n) in index.vanilla
                   and anchor in index.chain(('CfgVehicles', n)))
    if not names:
        raise ValueError('no stock types rows under anchor ' + str(anchor))
    return names, 'family'


def _template(stock, names):
    return max((stock[n] for n in names), key=lambda r: (r.get('nominal', 0), r['name']))


def classify_pack(pack, rules, index, pack_rows, stock, floor, tokens):
    """Rows for one pack: dispositions plus pending spawn groups resolved to nominals."""
    vanilla = index.vanilla
    classes = scope_two_classes(pack_rows, vanilla, index)
    shelf, floor_categories = floor['shelf_tag'], set(floor['floor_categories'])
    out, groups, unclassified, unproducible = [], {}, [], []
    for key in classes:
        row = pack_rows[key]
        rule = next((r for r in pack['rules'] if _matches(r, key, index, row)), None)
        if rule is None:
            unclassified.append(key[1])
            continue
        entry = {'name': key[1], 'root': key[0], 'disposition': rule['disposition'], 'rule': rule['id']}
        if rule.get('decision'):
            entry['decision'] = rule['decision']
        if rule.get('evidence') == 'script' and key[1] not in tokens:
            unproducible.append(key[1])
        if rule['disposition'] != 'spawn':
            entry['reason'] = rule['reason']
            out.append(entry)
            continue
        if key[0] != 'CfgVehicles':
            raise ValueError('only CfgVehicles classes can spawn: ' + key[1])
        anchor = index.anchor(key)
        if not rule.get('peers') and not rule.get('peer_slot') and (anchor is None or anchor in rules.generic):
            raise ValueError('generic anchor %s for %s needs explicit peers or peer_slot (rule %s)' % (
                anchor, key[1], rule['id']))
        names, mode = _family(stock, index, anchor, rule.get('peers'), rule.get('peer_slot'), rule.get('category'))
        template = _template(stock, names)
        group = (rule['id'], tuple(names) if rule.get('peers') or rule.get('peer_slot') else anchor)
        entry.update(peer=template['name'], _group=group, _names=names, _mode=mode, _rule=rule)
        groups.setdefault(group, []).append(entry)
        out.append(entry)
    if unclassified:
        raise ValueError('%d unclassified class(es) in pack %s; add rules: %s' % (
            len(unclassified), pack['id'], ', '.join(unclassified[:400])))
    if unproducible:
        raise ValueError('%d crafted class(es) in pack %s never appear in its scripts: %s' % (
            len(unproducible), pack['id'], ', '.join(unproducible[:40])))
    stats = []
    for members in groups.values():
        first = members[0]
        values = [stock[n].get('nominal', 0) for n in first['_names']]
        divisor = rules.divisor * first['_rule'].get('extra_divisor', 1)
        if first['_mode'] == 'family':
            budget = math.ceil(sum(values) / divisor)
            share, extra = divmod(budget, len(members))
            for position, member in enumerate(sorted(members, key=lambda m: m['name'])):
                member['nominal'] = max(1, share + (1 if position < extra else 0))
        else:
            budget = None
            each = max(1, round(statistics.mean(values) / divisor))
            for member in members:
                member['nominal'] = each
        for member in members:
            _guard(member, rules, index, stock)
        stats.append({'rule': first['_rule']['id'], 'peers': first['_names'], 'peer_nominal': sum(values),
                      'budget': budget, 'classes': len(members),
                      'assigned': sum(m.get('nominal', 0) for m in members)})
    return out, sorted(stats, key=lambda s: (s['rule'], s['peers']))


def _guard(entry, rules, index, stock):
    """Nutrition and clothing size guards; a failing spawn becomes an explicit exclusion."""
    key = ('CfgVehicles', entry['name'])
    names = entry['_names']
    notes = []
    own = index.nutrition(key) or index.nutrition((key[0], entry['name'] + '_Opened'))
    peer_rows = [index.nutrition(('CfgVehicles', n)) or index.nutrition(('CfgVehicles', n + '_Opened'))
                 for n in names]
    peer_rows = [p for p in peer_rows if p]
    if own and peer_rows:
        peer_energy = statistics.median(p.get('energy', 0) for p in peer_rows)
        peer_water = max(statistics.median(p.get('water', 0) for p in peer_rows), rules.nutrition['water_floor'])
        ratio = max(own.get('energy', 0) / max(peer_energy, 1), own.get('water', 0) / peer_water)
        entry['nutrition_ratio'] = round(ratio, 2)
        if ratio > rules.nutrition['exclude_ratio']:
            notes.append(('nutrition_outlier', 'nutrition %.1fx the vanilla peer median' % ratio))
        elif ratio > rules.nutrition['report_ratio']:
            entry['note'] = 'nutrition %.1fx the vanilla peer median (reported)' % ratio
    if entry['_rule'].get('size_check'):
        area = _area(index.eff(key, 'itemSize'))
        peer_areas = [a for a in (_area(index.eff(('CfgVehicles', n), 'itemSize')) for n in names) if a]
        if area and peer_areas:
            ratio = area / statistics.median(peer_areas)
            entry['size_ratio'] = round(ratio, 2)
            if ratio > rules.size['exclude_area_ratio']:
                notes.append(('inventory_size_outlier', 'inventory area %.1fx the vanilla peer median' % ratio))
            elif ratio > rules.size['report_area_ratio']:
                entry['note'] = (entry.get('note', '') + '; ' if entry.get('note') else '') + \
                    'inventory area %.1fx the vanilla peer median (reported)' % ratio
    if notes:
        entry['disposition'] = 'excluded'
        entry['reason'] = notes[0][0]
        entry['note'] = notes[0][1]
        entry.pop('nominal', None)


def _common(stock, names, field, template):
    """The template's list when set, else the most common non-empty list among the peers (ties: alphabetical)."""
    if template[field]:
        return template[field]
    counts = Counter(tuple(stock[n][field]) for n in names if stock[n][field])
    if not counts:
        return []
    return list(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0])


def _type_row(entry, rules, stock, shelf, floor_categories):
    template = stock[entry['peer']] if entry['disposition'] == 'spawn' else None
    row = {'name': entry['name']}
    if entry['disposition'] == 'spawn':
        rule = entry['_rule']
        nominal = entry['nominal']
        peer_nominal = max(template.get('nominal', 0), 1)
        row.update(nominal=nominal, min=int(nominal * template.get('min', 0) / peer_nominal),
                   lifetime=template['lifetime'], restock=template.get('restock', 0),
                   quantmin=template.get('quantmin', -1), quantmax=template.get('quantmax', -1),
                   cost=template.get('cost', 100), flags=dict(template['flags']))
        category = rule.get('category') or template['category']
        if category is None:
            raise ValueError('spawn row needs a category: ' + entry['name'])
        row['category'] = category
        tags = list(template['tags'])
        if category not in floor_categories:
            tags = [shelf]
        row['tags'] = tags
        row['usage'] = list(rule.get('usage') or _common(stock, entry['_names'], 'usage', template))
        row['value'] = list(rule['value'] if 'value' in rule else _common(stock, entry['_names'], 'value', template))
        if not row['usage']:
            raise ValueError('spawn row has no usage (set usage in the rule): ' + entry['name'])
    else:
        row.update(nominal=0, min=0, lifetime=rules.crafted_lifetime, restock=0, quantmin=-1, quantmax=-1, cost=100,
                   flags={'count_in_cargo': '0', 'count_in_hoarder': '0', 'count_in_map': '1',
                          'count_in_player': '0', 'crafted': '1', 'deloot': '0'},
                   category=None, tags=[], usage=[], value=[])
    return row


# ------------------------------------------------------------------------------------------------ generation

def load_inputs(addons, workshop, source, rules):
    vanilla, _ = read_configs(addons)
    packs, digests, tokens = {}, {}, {}
    for pack in rules.packs:
        directory = addons_dir(Path(workshop) / pack['id'])
        if directory is None:
            raise FileNotFoundError('installed pack unavailable: ' + pack['id'])
        packs[pack['id']], digests[pack['id']] = read_configs(directory)
        tokens[pack['id']] = script_tokens(directory)
    stock = stock_types(Path(source) / 'db/types.xml')
    return vanilla, packs, stock, tokens


def generate(addons, workshop, source, repo=ROOT):
    repo = Path(repo)
    rules = Rules(json.loads((repo / RULES).read_bytes()))
    floor = json.loads((repo / FLOOR_POLICY).read_bytes())
    vanilla, packs, stock, tokens = load_inputs(addons, workshop, source, rules)
    index = Index(vanilla, list(packs.values()))
    ce, report = {'schema': 1, 'kind': 'hollow-country-variety-ce', 'scarcity_divisor': rules.divisor,
                  'note': 'Generated by tools/package/variety_packs.py; applied only for loaded packs; runtime=PENDING.',
                  'packs': {}}, []
    for pack in rules.packs:
        entries, stats = classify_pack(pack, rules, index, packs[pack['id']], stock, floor, tokens[pack['id']])
        types = []
        classes = []
        for entry in sorted(entries, key=lambda e: e['name']):
            if entry['disposition'] in ('spawn', 'crafted'):
                row = _type_row(entry, rules, stock, floor['shelf_tag'], set(floor['floor_categories']))
                types.append(row)
            clean = {k: v for k, v in entry.items() if not k.startswith('_')}
            classes.append(clean)
        counts = Counter(c['disposition'] for c in classes)
        reasons = Counter((c['disposition'], c.get('reason') or c['rule']) for c in classes
                          if c['disposition'] != 'spawn')
        ce['packs'][pack['id']] = {'folder': pack['folder'], 'types': types,
                                   'settings': settings_rows(pack, tokens[pack['id']])}
        report.append({'id': pack['id'], 'name': pack['name'], 'folder': pack['folder'], 'scope': pack['scope'],
                       'licence': pack['licence'], 'total': len(classes),
                       'counts': {d: counts.get(d, 0) for d in DISPOSITIONS},
                       'spawn_nominal': sum(c.get('nominal', 0) for c in classes),
                       'reasons': [{'disposition': d, 'reason': r, 'count': n}
                                   for (d, r), n in sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))],
                       'settings': [{k: row[k] for k in ('id', 'root', 'target', 'reason')}
                                    for row in ce['packs'][pack['id']]['settings']],
                       'groups': stats, 'classes': classes})
    dispositions = {'schema': 1, 'kind': 'hollow-country-variety-dispositions',
                    'note': 'Generated by tools/package/variety_packs.py from config/variety-packs.json; '
                            'every scope-2 class a pack adds has one explicit disposition.',
                    'packs': report}
    return {CE_OUT: _dump(ce), DISPOSITIONS_OUT: _dump(dispositions)}


def _dump(data):
    return (json.dumps(data, indent=1, ensure_ascii=False) + '\n').encode('utf-8')


def summary(files):
    data = json.loads(files[DISPOSITIONS_OUT])
    lines = []
    for pack in data['packs']:
        c = pack['counts']
        lines.append('%s %s: total=%d spawn=%d crafted=%d excluded=%d spawn_nominal=%d' % (
            pack['id'], pack['name'], pack['total'], c['spawn'], c['crafted'], c['excluded'], pack['spawn_nominal']))
        for row in pack['reasons'][:6]:
            lines.append('    %s %s x%d' % (row['disposition'], row['reason'], row['count']))
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--addons', type=Path, required=True)
    parser.add_argument('--workshop', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True, help='stock mission directory (db/types.xml)')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--write', action='store_true')
    mode.add_argument('--report', action='store_true')
    args = parser.parse_args(argv)
    files = generate(args.addons, args.workshop, args.source)
    if args.report:
        print(summary(files))
        return 0
    if args.write:
        for rel, data in files.items():
            (ROOT / rel).write_bytes(data)
        print(summary(files))
        return 0
    stale = [rel for rel, data in files.items() if not (ROOT / rel).is_file() or (ROOT / rel).read_bytes() != data]
    if stale:
        print('variety packs: stale ' + ', '.join(stale), file=sys.stderr)
        return 1
    print('variety packs: committed bytes match fresh generation')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
