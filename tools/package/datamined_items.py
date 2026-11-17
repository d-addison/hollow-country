"""Chernarus CE rows for datamined, unused-but-finished vanilla NON-weapon items.

The census (static config parsing, never CE behaviour) found finished vanilla items that
Chernarus's stock types.xml sets to nominal 0 or omits. This module holds the owner-approved
rows (``datamined_items.json``), validates them against the installed vanilla config, the
Chernarus stock types and the other maps' types, and emits ``<type>`` elements in exactly the
shape ``economy.py`` already consumes (stock ``type`` elements: the same child tags, order and
retained fields). Every row stays ``acceptance: pending-local``: nothing here is runtime proof.

Standard library only. This module never imports ``economy`` so economy can import it.
"""
import copy
import json
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

SCHEMA = 1
DATA = Path(__file__).with_name('datamined_items.json')
ACCEPTANCE = 'pending-local'
FLAG_ORDER = ('count_in_cargo', 'count_in_hoarder', 'count_in_map', 'count_in_player', 'crafted', 'deloot')
ROW_KEYS = ('class', 'nominal', 'min', 'lifetime', 'restock', 'quantmin', 'quantmax', 'cost', 'flags',
            'category', 'usage', 'value', 'stock', 'winter_only', 'equivalent', 'source_maps',
            'source_map_note', 'placement', 'acceptance')
TOP_KEYS = ('schema', 'status', 'flags_order', 'census', 'craft_output_candidates', 'rows')
CATEGORIES = frozenset({'tools', 'containers', 'clothes', 'lootdispatch', 'food', 'weapons', 'books',
                        'explosives'})
TIERS = frozenset({'Tier1', 'Tier2', 'Tier3', 'Tier4', 'Unique'})
# Native Chernarus winter gear (HuntingJacket_Winter, HunterPants_Winter) is nominal 4; Sakhal-only
# or seasonal winter gear must stay below it.
WINTER_CEILING = 3
HINT_MAPS = ('enoch', 'sakhal')  # vanilla maps whose types.xml are nominal hints; Nasdara is DLC
# Child order of a stock type element.
ORDER = ('nominal', 'lifetime', 'restock', 'min', 'quantmin', 'quantmax', 'cost', 'flags', 'category',
         'tag', 'usage', 'value')
EXCLUDED_NAMES = frozenset({'enginoil', 'engineoil', 'brakefluid', 'chelatingtablets'})
EXCLUDED_PATTERN = re.compile(r'(^|_)(test|dev|debug)|keys?(_|$)', re.I)
CRAFT_PATTERN = re.compile(r'^(LeatherPants|LeatherStorageVest)_', re.I)
MAX_XML_BYTES = 16 * 1024 * 1024
MAX_JSON_BYTES = 1024 * 1024
MAX_CONFIG_BYTES = 64 * 1024 * 1024
MAX_HEADER_BYTES = 16 * 1024 * 1024
MAX_PBO_ENTRIES = 200_000
MAX_BODY_ENTRIES = 100_000
MAX_CLASSES = 400_000
MAX_ARRAY_ITEMS = 100_000
CONFIG_ROOTS = ('cfgvehicles', 'cfgweapons', 'cfgmagazines')


def _int(value):
    return type(value) is int


def _fail(message):
    raise ValueError(message)


def _lower(mapping):
    return {str(k).lower(): v for k, v in mapping.items()}


def _check_shape(row):
    if not isinstance(row, dict) or set(row) != set(ROW_KEYS):
        _fail('row does not use the exact schema keys')
    name = row['class']
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_]{1,80}', name):
        _fail('row class name is invalid')
    for key in ('nominal', 'min', 'lifetime', 'restock', 'quantmin', 'quantmax', 'cost'):
        if not _int(row[key]):
            _fail(f'{name}: {key} must be an integer')
    if row['nominal'] < 0 or row['min'] < 0 or row['min'] > row['nominal']:
        _fail(f'{name}: nominal/min must satisfy 0 <= min <= nominal')
    if row['lifetime'] <= 0 or row['restock'] < 0 or row['cost'] < 0:
        _fail(f'{name}: lifetime must be positive and restock/cost non-negative')
    if not (-1 <= row['quantmin'] <= 100 and -1 <= row['quantmax'] <= 100) or row['quantmin'] > row['quantmax']:
        _fail(f'{name}: invalid quantity bounds')
    if not isinstance(row['flags'], str) or not re.fullmatch(r'[01]{6}', row['flags']):
        _fail(f'{name}: flags must be six binary digits in flags_order')
    if row['category'] is not None and row['category'] not in CATEGORIES:
        _fail(f'{name}: unknown category')
    for key in ('usage', 'value'):
        items = row[key]
        if (not isinstance(items, list) or any(not isinstance(v, str) or not v for v in items)
                or len(set(items)) != len(items)):
            _fail(f'{name}: {key} must be a list of unique names')
    if not row['usage']:
        _fail(f'{name}: at least one usage is required to spawn')
    if any(v not in TIERS for v in row['value']):
        _fail(f'{name}: unknown value tier')
    if row['stock'] not in {'present', 'absent'}:
        _fail(f'{name}: stock must be present or absent')
    if not isinstance(row['winter_only'], bool):
        _fail(f'{name}: winter_only must be a boolean')
    eq = row['equivalent']
    if (not isinstance(eq, dict) or set(eq) != {'class', 'nominal'} or not isinstance(eq['class'], str)
            or not _int(eq['nominal']) or eq['nominal'] <= 0):
        _fail(f'{name}: equivalent needs a class and a positive nominal')
    maps = row['source_maps']
    if (not isinstance(maps, dict) or any(m not in HINT_MAPS or not _int(n) or n <= 0
                                         for m, n in maps.items())):
        _fail(f'{name}: source_maps must map a vanilla hint map to a positive nominal')
    for key in ('source_map_note', 'placement'):
        if not isinstance(row[key], str) or not row[key].strip():
            _fail(f'{name}: {key} must be a non-empty note')
    if row['acceptance'] != ACCEPTANCE:
        _fail(f'{name}: acceptance must stay {ACCEPTANCE}')


def _check_name(name):
    if name.lower() in EXCLUDED_NAMES or EXCLUDED_PATTERN.search(name):
        _fail(f'{name}: class is excluded (dev/test, key, engine fluid or chelating tablets)')
    if CRAFT_PATTERN.match(name):
        _fail(f'{name}: craft-output candidate, not a spawn')


def _check_config(name, entry):
    if entry is None:
        _fail(f'{name}: class is not in the installed config')
    if not _int(entry.get('scope')) or entry['scope'] != 2:
        _fail(f'{name}: config scope must be 2, found {entry.get("scope")!r}')
    if str(entry.get('lootCategory') or '').lower() == 'crafted':
        _fail(f'{name}: lootCategory is Crafted (craft output, not a spawn)')
    if '$UNT$' in str(entry.get('displayName') or ''):
        _fail(f'{name}: display name carries the unfinished $UNT$ marker')
    if 'nasdara' in str(entry.get('source') or '').lower():
        _fail(f'{name}: Nasdara DLC class')


def _check_budget_rules(row):
    name = row['class']
    if row['winter_only'] and row['nominal'] > WINTER_CEILING:
        _fail(f'{name}: winter-only gear must stay at or below nominal {WINTER_CEILING}')
    if row['nominal'] > row['equivalent']['nominal']:
        _fail(f'{name}: nominal exceeds its vanilla equivalent {row["equivalent"]["class"]}')
    if row['source_maps'] and row['nominal'] > max(row['source_maps'].values()):
        _fail(f'{name}: nominal exceeds the other-map hint')


def _check_other_maps(row, other_maps):
    name = row['class']
    for m, declared in row['source_maps'].items():
        if _lower(other_maps.get(m, {})).get(name.lower()) != declared:
            _fail(f'{name}: source map {m} nominal does not match that map\'s types')
    for m in HINT_MAPS:
        actual = _lower(other_maps.get(m, {})).get(name.lower(), 0)
        if actual > 0 and m not in row['source_maps']:
            _fail(f'{name}: spawns on {m} (nominal {actual}) but the row has no source map note')


def _stock_usage(element):
    return {u.get('name') for u in element.findall('usage')}


def _check_stock(row, stock_lower):
    name = row['class']
    element = stock_lower.get(name.lower())
    if row['stock'] == 'absent':
        if element is not None:
            _fail(f'{name}: already in stock types.xml as {element.get("name")} (case-insensitive duplicate)')
        return None
    if element is None:
        _fail(f'{name}: row says present but the class is not in stock types.xml')
    for tag in ('quantmin', 'quantmax', 'cost'):
        if (element.findtext(tag) or '').strip() != str(row[tag]):
            _fail(f'{name}: {tag} differs from stock')
    flags = element.find('flags')
    if flags is None or ''.join(flags.get(k, '') for k in FLAG_ORDER) != row['flags']:
        _fail(f'{name}: flags differ from stock')
    category = element.find('category')
    if category is not None and category.get('name') != row['category']:
        _fail(f'{name}: category differs from stock')
    if not _stock_usage(element) <= set(row['usage']):
        _fail(f'{name}: row usage drops a stock usage')
    return element


def validate_rows(rows, catalog, stock=None, vocabulary=None, other_maps=None, equivalents=None):
    """Raise ValueError unless every row is a finished, spawnable, modest vanilla item.

    catalog: ``load_catalog`` output (resolved scope/lootCategory/displayName/source per class).
    stock: optional Chernarus ``{name: <type>}``; other_maps: optional ``{map: {name: nominal}}``;
    equivalents: optional ``{name: nominal}`` of the Chernarus vanilla equivalents.
    """
    if not isinstance(rows, list) or not rows:
        _fail('rows must be a non-empty list')
    seen = set()
    catalog = _lower(catalog)
    stock_lower = None if stock is None else _lower(stock)
    for row in rows:
        _check_shape(row)
        name = row['class']
        if name.lower() in seen:
            _fail(f'{name}: duplicate class')
        seen.add(name.lower())
        _check_name(name)
        _check_config(name, catalog.get(name.lower()))
        if vocabulary is not None and any(u not in vocabulary for u in row['usage']):
            _fail(f'{name}: usage is not in the cfglimitsdefinition vocabulary')
        _check_budget_rules(row)
        if equivalents is not None:
            actual = _lower(equivalents).get(row['equivalent']['class'].lower())
            if actual != row['equivalent']['nominal']:
                _fail(f'{name}: equivalent {row["equivalent"]["class"]} nominal does not match stock')
        if other_maps is not None:
            _check_other_maps(row, other_maps)
        if stock_lower is not None:
            _check_stock(row, stock_lower)
    return rows


def load_rows(path=None):
    """Load and shape-check the rows (no config needed). Returns a deep copy per call."""
    path = Path(path or DATA)
    raw = path.read_bytes()
    if len(raw) > MAX_JSON_BYTES:
        _fail('datamined items file exceeds budget')
    doc = json.loads(raw)
    if (not isinstance(doc, dict) or set(doc) != set(TOP_KEYS) or doc['schema'] != SCHEMA
            or doc['flags_order'] != list(FLAG_ORDER) or not isinstance(doc['rows'], list)):
        _fail('unsupported datamined items schema')
    candidates = doc['craft_output_candidates']
    if (not isinstance(candidates, list) or not candidates
            or any(not isinstance(c, str) or not CRAFT_PATTERN.match(c) for c in candidates)):
        _fail('craft_output_candidates must name craft-output classes')
    for row in doc['rows']:
        _check_shape(row)
    return doc['rows']


def craft_output_candidates(path=None):
    """Crafted-lootCategory classes the census listed: craft outputs, never CE spawns."""
    doc = json.loads(Path(path or DATA).read_bytes())
    return list(doc['craft_output_candidates'])


def total_nominal(rows):
    return sum(r['nominal'] for r in rows)


def read_types(path):
    """Bounded read of a types.xml into ``{name: <type>}``; DOCTYPE/ENTITY and duplicates refused."""
    data = Path(path).read_bytes()
    if len(data) > MAX_XML_BYTES:
        _fail('types.xml exceeds budget')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeError as e:
        raise ValueError('types.xml must be UTF-8') from e
    if '\x00' in text or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        _fail('unsupported XML declarations')
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise ValueError('malformed types.xml') from e
    if root.tag != 'types':
        _fail('expected a types root')
    out = {}
    for node in root.findall('type'):
        name = node.get('name')
        if not name or name in out:
            _fail('missing or duplicate type name')
        out[name] = node
    return out


def _children(element, tag):
    return [ET.tostring(n) for n in element.findall(tag)]


def retention_changes(rows_out, stock):
    """Child tags that differ from stock across the emitted elements (the mutable set it needs)."""
    stock_lower = _lower(stock)
    changed = set()
    for element in rows_out:
        original = stock_lower.get(element.get('name', '').lower())
        if original is None:
            continue
        for tag in ORDER:
            if _children(element, tag) != _children(original, tag):
                changed.add(tag)
    return changed


def _text_child(element, tag, text):
    node = element.find(tag)
    if node is None:
        node = ET.SubElement(element, tag)
    node.text = str(text)


def _build(row, original):
    element = copy.deepcopy(original) if original is not None else ET.Element('type', {'name': row['class']})
    if original is not None:
        element.set('name', original.get('name'))
    for tag in ('nominal', 'lifetime', 'restock', 'min', 'quantmin', 'quantmax', 'cost'):
        _text_child(element, tag, row[tag])
    flags = element.find('flags')
    if flags is None:
        flags = ET.SubElement(element, 'flags')
    flags.attrib.clear()
    flags.attrib.update(zip(FLAG_ORDER, row['flags']))
    if row['category'] is not None:
        category = element.find('category')
        if category is None:
            category = ET.SubElement(element, 'category')
        category.set('name', row['category'])
    for tag, names in (('usage', row['usage']), ('value', row['value'])):
        for node in element.findall(tag):
            element.remove(node)
        for name in sorted(names):
            ET.SubElement(element, tag, {'name': name})
    kids = sorted(element, key=lambda n: ORDER.index(n.tag) if n.tag in ORDER else len(ORDER))
    for node in list(element):
        element.remove(node)
    element.extend(kids)
    return element


def type_rows(stock, vocabulary=None, include_new=False, rows=None):
    """Return ``<type>`` elements for economy.py: stock entries with the row's budget/usage/tiers.

    stock: ``{name: <type>}`` (economy's ``types`` mapping). Stock-present rows keep every stock
    field except nominal/min/lifetime/restock/usage/value (and category only where stock has none).
    Stock-absent rows are new types; they are returned only with ``include_new`` because
    ``economy.install`` currently refuses types that stock lacks. Pure: never mutates ``stock``.
    """
    rows = load_rows() if rows is None else rows
    stock_lower = _lower(stock)
    seen = set()
    out = []
    for row in rows:
        _check_shape(row)
        name = row['class']
        if name.lower() in seen:
            _fail(f'{name}: duplicate class')
        seen.add(name.lower())
        _check_name(name)
        if vocabulary is not None and any(u not in vocabulary for u in row['usage']):
            _fail(f'{name}: usage is not in the cfglimitsdefinition vocabulary')
        _check_budget_rules(row)
        original = _check_stock(row, stock_lower)
        if original is None and not include_new:
            continue
        out.append(_build(row, original))
    return sorted(out, key=lambda e: e.get('name'))


# ---- installed vanilla config (read-only, bounded, rapified config.bin only) -------------------

class _Reader:
    def __init__(self, data):
        self.data = data

    def byte(self, pos):
        if pos >= len(self.data):
            _fail('truncated rapified config')
        return self.data[pos], pos + 1

    def cint(self, pos):
        value = shift = 0
        while True:
            b, pos = self.byte(pos)
            value |= (b & 0x7F) << shift
            shift += 7
            if not b & 0x80:
                return value, pos
            if shift > 35:
                _fail('bad rapified integer')

    def cstring(self, pos):
        end = self.data.find(b'\0', pos)
        if end < 0:
            _fail('unterminated rapified string')
        return self.data[pos:end].decode('latin-1'), end + 1

    def fixed(self, pos, fmt):
        n = struct.calcsize(fmt)
        if pos + n > len(self.data):
            _fail('truncated rapified config')
        return struct.unpack_from(fmt, self.data, pos)[0], pos + n

    def array(self, pos, depth=0):
        if depth > 8:
            _fail('rapified array nesting exceeds budget')
        count, pos = self.cint(pos)
        if count > MAX_ARRAY_ITEMS:
            _fail('rapified array exceeds budget')
        for _ in range(count):
            kind, pos = self.byte(pos)
            if kind == 0:
                _, pos = self.cstring(pos)
            elif kind in (1, 2):
                _, pos = self.fixed(pos, '<f' if kind == 1 else '<i')
            elif kind == 3:
                pos = self.array(pos, depth + 1)
            else:
                _fail('unsupported rapified array element')
        return pos

    def body(self, pos, keep):
        """Return (parent, {scalar: value} for names in keep, [(class, offset)])."""
        parent, pos = self.cstring(pos)
        count, pos = self.cint(pos)
        if count > MAX_BODY_ENTRIES:
            _fail('rapified class exceeds entry budget')
        scalars, classes = {}, []
        for _ in range(count):
            kind, pos = self.byte(pos)
            if kind == 0:
                name, pos = self.cstring(pos)
                offset, pos = self.fixed(pos, '<I')
                classes.append((name, offset))
            elif kind == 1:
                sub, pos = self.byte(pos)
                name, pos = self.cstring(pos)
                if sub == 0:
                    value, pos = self.cstring(pos)
                elif sub in (1, 2):
                    value, pos = self.fixed(pos, '<f' if sub == 1 else '<i')
                else:
                    _fail('unsupported rapified value type')
                if name.lower() in keep:
                    scalars[name.lower()] = value
            elif kind == 2:
                _, pos = self.cstring(pos)
                pos = self.array(pos)
            elif kind in (3, 4):
                _, pos = self.cstring(pos)
            elif kind == 5:
                _, pos = self.cstring(pos + 4)
                pos = self.array(pos)
            else:
                _fail('unsupported rapified entry type')
        return parent, scalars, classes


def _pbo_member(path, wanted):
    """Read one uncompressed member of a PBO with bounded header/member sizes; None when absent."""
    wanted = wanted.lower()
    with open(path, 'rb') as handle:
        head = handle.read(MAX_HEADER_BYTES + 1)
        pos, entries = 0, []

        def cstr():
            nonlocal pos
            end = head.find(b'\0', pos)
            if end < 0:
                _fail('truncated PBO header')
            text = head[pos:end].decode('latin-1')
            pos = end + 1
            return text
        while True:
            name = cstr()
            if pos + 20 > len(head):
                _fail('truncated PBO header')
            method, _original, _reserved, _stamp, size = struct.unpack_from('<5I', head, pos)
            pos += 20
            if name == '' and method == 0x56657273:
                while cstr():
                    cstr()
                continue
            if name == '':
                break
            if len(entries) >= MAX_PBO_ENTRIES:
                _fail('PBO entry count exceeds budget')
            entries.append((name, method, size))
        offset = 0
        for name, method, size in entries:
            if name.lower() == wanted:
                if method != 0:
                    _fail('compressed PBO member unsupported')
                if size > MAX_CONFIG_BYTES:
                    _fail('PBO member exceeds budget')
                handle.seek(pos + offset)
                data = handle.read(size)
                if len(data) != size:
                    _fail('truncated PBO member')
                return data
            offset += size
    return None


def _scan_config(data):
    """Top-level classes of the Cfg roots: ``{lower: {parent, scope, lootcategory, displayname}}``."""
    if data[:4] != b'\0raP':
        _fail('config.bin is not rapified')
    reader = _Reader(data)
    keep = {'scope', 'lootcategory', 'displayname'}
    try:
        _, _, roots = reader.body(16, set())
        found, budget = {}, MAX_CLASSES
        for root_name, offset in roots:
            if root_name.lower() not in CONFIG_ROOTS:
                continue
            _, _, classes = reader.body(offset, set())
            for class_name, class_offset in classes:
                budget -= 1
                if budget < 0:
                    _fail('config class count exceeds budget')
                parent, scalars, _children_unused = reader.body(class_offset, keep)
                found[class_name] = dict(scalars, parent=parent)
    except (IndexError, struct.error, UnicodeError) as e:
        raise ValueError('malformed rapified config') from e
    return found


def load_catalog(addons_dir):
    """Resolve scope/lootCategory/displayName (with inheritance) and source PBO of every class.

    Returns ``{lower class: {'scope', 'lootCategory', 'displayName', 'source'}}`` from the
    ``config.bin`` of each ``*.pbo`` in addons_dir. Static file evidence only.
    """
    addons = Path(addons_dir)
    if not addons.is_dir() or addons.is_symlink():
        _fail('addons directory is missing or a symlink')
    own = {}
    for path in sorted(addons.glob('*.pbo')):
        if path.is_symlink() or not path.is_file():
            continue
        data = _pbo_member(path, 'config.bin')
        if data is None:
            continue
        for name, values in _scan_config(data).items():
            slot = own.setdefault(name.lower(), {'name': name, 'source': path.name, 'parent': ''})
            if values['parent']:
                slot['parent'] = values['parent']
            for key in ('scope', 'lootcategory', 'displayname'):
                if key in values:
                    slot[key] = values[key]

    def resolve(slot, key):
        seen = set()
        while slot is not None and id(slot) not in seen:
            if key in slot:
                return slot[key]
            seen.add(id(slot))
            slot = own.get(slot['parent'].lower())
        return None
    return {key: {'scope': resolve(slot, 'scope'), 'lootCategory': resolve(slot, 'lootcategory'),
                  'displayName': resolve(slot, 'displayname'), 'source': slot['source']}
            for key, slot in own.items()}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Validate the datamined item rows against an install')
    parser.add_argument('--addons', required=True, help='installed server addons directory')
    parser.add_argument('--missions', required=True, help='directory holding dayzOffline.<map> missions')
    args = parser.parse_args(argv)
    missions = Path(args.missions)
    stock = read_types(missions / 'dayzOffline.chernarusplus/db/types.xml')
    other = {m: {n: int(e.findtext('nominal') or 0)
                 for n, e in read_types(missions / f'dayzOffline.{m}/db/types.xml').items()} for m in HINT_MAPS}
    limits = ET.parse(missions / 'dayzOffline.chernarusplus/cfglimitsdefinition.xml').getroot()
    vocabulary = {u.get('name') for u in limits.findall('./usageflags/usage')}
    rows = load_rows()
    validate_rows(rows, load_catalog(args.addons), stock=stock, vocabulary=vocabulary, other_maps=other,
                  equivalents={n: int(e.findtext('nominal') or 0) for n, e in stock.items()})
    print(json.dumps({'rows': len(rows), 'total_nominal': total_nominal(rows), 'acceptance': ACCEPTANCE}))


if __name__ == '__main__':
    main()
