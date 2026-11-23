"""Read-only inventory config inputs; never extracts scripts or assets."""
import os
from pathlib import Path
import struct
from tools.audit import pbo_config as reader

# Folder aliases keep restricted provider identifiers out of packaged config data.
WORKSHOP_FOLDERS = {
    '@CF': '1559212036', '@COT': '1564026768', '@DabsFramework': '2545327648',
    '@Expansion-Core': '2291785308', '@Expansion-Licensed': '2116157322',
    '@Expansion-Vehicles': '2291785437', '@Expansion-AI': '2792982069',
    '@Expansion-Navigation': '2792984722',
    '@AmbientAnimals': '3114410963',
    '@RaG_Core': '3556131153', '@RaG_Immersive_Vehicles': '3105330157',
    '@WeaponPackA': '2646817942', '@WeaponPackB': '2443122116',
}
BANNED = ('snafu', 'tacticalflava', '2646817942', '2291785308', '2792982069')


# One indexed read per PBO. reader.read_pbo_index walks the header one byte at a time (about 25 ms
# per addon, 3 s for the installed vanilla set); read_index decodes the same bounded header from
# buffered blocks with the same budgets and returns the same dictionary, and memoises it per file
# state. iter_members opens a PBO once for all its members; reader.read_member opens it per member.
HEADER_BLOCK = 256 * 1024
_INDEX_CACHE = {}
_DOCUMENT_CACHE = {}


def _file_state(path):
    stat = os.stat(path)
    return str(path), stat.st_size, stat.st_mtime_ns


def _parse_index(handle, max_entries, max_header_bytes):
    buffer = bytearray()

    def fill():
        block = handle.read(HEADER_BLOCK)
        if not block:
            raise ValueError('truncated PBO header')
        buffer.extend(block)

    def cstring(position):
        while True:
            end = buffer.find(b'\0', position)
            if end >= 0:
                if end - position > reader.MAX_NAME:
                    raise ValueError('PBO header name exceeds budget')
                return buffer[position:end].decode('latin-1'), end + 1
            if len(buffer) - position > reader.MAX_NAME:
                raise ValueError('PBO header name exceeds budget')
            fill()

    def budget(position):
        if position > max_header_bytes:
            raise ValueError('PBO header exceeds budget')

    entries, props, offset, position = [], {}, 0, 0
    while True:
        name, position = cstring(position)
        while len(buffer) < position + 20:
            fill()
        method, original, _reserved, _stamp, size = struct.unpack_from('<IIIII', buffer, position)
        position += 20
        budget(position)
        if name == '' and method == reader.PACK_VERS:
            while True:
                key, position = cstring(position)
                if key == '':
                    break
                props[key.lower()], position = cstring(position)
                budget(position)
            continue
        if name == '':
            break
        if len(entries) >= max_entries:
            raise ValueError('PBO entry count exceeds budget')
        entries.append({'name': name, 'method': method, 'original': original, 'size': size, 'offset': offset})
        offset += size
    return entries, props.get('prefix', ''), position, offset


def read_index(path, max_entries=reader.MAX_ENTRIES, max_header_bytes=reader.MAX_HEADER_BYTES):
    """Same result as reader.read_pbo_index(path), memoised per (path, size, mtime)."""
    key = _file_state(path) + (max_entries, max_header_bytes)
    index = _INDEX_CACHE.get(key)
    if index is None:
        with open(path, 'rb') as handle:
            entries, prefix, header_end, data_size = _parse_index(handle, max_entries, max_header_bytes)
            handle.seek(0, 2)
            file_size = handle.tell()
        if header_end + data_size > file_size:
            raise ValueError('PBO data extends past the end of file')
        index = {'prefix': prefix, 'entries': entries, 'header_end': header_end, 'size': file_size}
        _INDEX_CACHE[key] = index
    return index


def iter_members(path, index, names, max_bytes=reader.MAX_CONFIG_BYTES):
    """Yield (name, bytes or None) like reader.read_member for each name, opening the file once."""
    first = {}
    for entry in index['entries']:
        first.setdefault(entry['name'].lower().replace('/', '\\'), entry)
    with open(path, 'rb') as handle:
        for name in names:
            entry = first.get(name.lower().replace('/', '\\'))
            if entry is None:
                yield name, None
                continue
            if entry['method'] != 0:
                raise ValueError('compressed PBO member unsupported')
            if entry['size'] > max_bytes:
                raise ValueError('PBO member exceeds budget')
            handle.seek(index['header_end'] + entry['offset'])
            data = handle.read(entry['size'])
            if len(data) != entry['size']:
                raise ValueError('truncated PBO member')
            yield name, data


def safe_text(text):
    compact = ''.join(c for c in text.lower() if c.isalnum())
    return not any(word in compact for word in BANNED)


def text_rows(data, fields):
    """Use the audit reader's bounded lexer, retaining numeric inventory arrays."""
    if len(data) > reader.MAX_CONFIG_BYTES:
        raise ValueError('text inventory config exceeds budget')
    tokens = reader._Tokens(reader._strip_text(data.decode('latin-1')), reader.MAX_TEXT_TOKENS)

    def body(depth):
        if depth > reader.MAX_TEXT_DEPTH:
            raise ValueError('text inventory nesting exceeds budget')
        classes, values = {}, {}
        while True:
            kind, name = tokens.next()
            if kind == 'eof':
                if depth == 0:
                    return classes, values
                raise ValueError('truncated inventory config')
            if (kind, name) == ('op', '}'):
                return classes, values
            if (kind, name) == ('op', ';'):
                continue
            if (kind, name) == ('id', 'class'):
                _, cname = tokens.next()
                parent = ''
                nxt = tokens.next()
                if nxt == ('op', ':'):
                    _, parent = tokens.next()
                    nxt = tokens.next()
                if nxt == ('op', ';'):
                    continue
                if nxt != ('op', '{'):
                    raise ValueError('malformed inventory class')
                children, props = body(depth + 1)
                reader._expect(tokens, ';')
                for child_name, (_, _, child_props) in children.items():
                    if child_name.lower() == 'opticsinfo':
                        props.update({k: v for k, v in child_props.items()
                                      if k in {'opticsZoomMin', 'opticsZoomMax'}})
                classes[cname] = (parent, children, props)
            elif kind == 'id' and tokens.peek() == ('op', '['):
                tokens.next()
                reader._expect(tokens, ']')
                _, op = tokens.next()
                if op not in ('=', '+='):
                    raise ValueError('malformed inventory array')
                value = reader._text_array(tokens)
                reader._expect(tokens, ';')
                if name in fields | {'units', 'requiredAddons'}:
                    if op == '+=' and name in {'inventorySlot', 'attachments'}:
                        values['append:' + name] = values.get('append:' + name, []) + value
                    elif op == '+=' and name in {'units', 'requiredAddons'}:
                        values[name] = values.get(name, []) + value
                    elif op == '+=':
                        raise ValueError('unsupported inventory array append: ' + name)
                    else:
                        values[name] = value
                        values.pop('append:' + name, None)
            elif kind == 'id' and tokens.peek() == ('op', '='):
                tokens.next()
                value = reader._text_scalar(tokens)
                if name in fields:
                    if name == 'scope' and isinstance(value, str):
                        value = reader._KEYWORD_SCOPE.get(value.lower())
                    if value is not None:
                        values[name] = value
            else:
                reader._skip_statement_from(tokens, kind, name)
    roots, _ = body(0)
    patches, rows = {}, {}
    for name, (_, children, _) in roots.items():
        if name.lower() == 'cfgpatches':
            patches.update({n: props for n, (_, _, props) in children.items()})
        elif name.lower() in {'cfgvehicles', 'cfgmagazines', 'cfgweapons'}:
            root = {'cfgvehicles': 'CfgVehicles', 'cfgmagazines': 'CfgMagazines', 'cfgweapons': 'CfgWeapons'}[name.lower()]
            rows.update({(n if root == 'CfgVehicles' else root + '::' + n):
                         {'name': n, 'root': root, 'parent': parent, 'fields': props}
                         for n, (parent, _, props) in children.items()})
    return patches, rows


def documents(addons, source, fields, rap_rows, vanilla=False):
    """Config documents of one source directory, memoised per process and PBO file state.

    The vanilla source is read by both load_vanilla and load_stack; callers only read the
    returned documents (merge_documents copies what it keeps), so the memo is shared.
    """
    addons = Path(addons)
    if not addons.is_dir():
        raise ValueError('inventory source directory missing: ' + source)
    states = tuple(sorted(_file_state(p) for p in addons.iterdir() if p.suffix.lower() in {'.pbo', '.ebo'}))
    key = (str(addons), source, frozenset(fields), rap_rows, vanilla, states)
    cached = _DOCUMENT_CACHE.get(key)
    if cached is None:
        cached = _DOCUMENT_CACHE[key] = _read_documents(addons, source, fields, rap_rows, vanilla)
    return list(cached[0]), list(cached[1])


def _read_documents(addons, source, fields, rap_rows, vanilla):
    docs, skipped = [], []
    families = ('characters_', 'gear_', 'weapon_', 'weapons_', 'vehicles_')
    for path in sorted(addons.iterdir(), key=lambda p: p.name.lower()):
        if path.suffix.lower() == '.ebo':
            skipped.append({'pbo': path.name, 'reason': 'encrypted-ebo'})
            continue
        if path.suffix.lower() != '.pbo':
            continue
        if vanilla and not (path.name.startswith(families) or path.name in {'dz.pbo', 'plants.pbo'}):
            continue
        index = read_index(path)
        entries = sorted(index['entries'], key=lambda e: e['name'].lower())
        # A bin supersedes cpp only in the same config directory.
        bins = {e['name'].lower().replace('\\', '/')[:-3] for e in entries
                if e['name'].lower().endswith('config.bin')}
        wanted = []
        for entry in entries:
            member = entry['name'].lower().replace('\\', '/')
            if not member.endswith(('config.bin', 'config.cpp')):
                continue
            if member.endswith('.cpp') and member[:-3] in bins:
                continue
            wanted.append(entry['name'])
        for name, data in iter_members(path, index, wanted):
            patches, rows = rap_rows(data) if data[:4] == b'\0raP' else text_rows(data, fields)
            docs.append({'source': source, 'pbo': path.name, 'member': name,
                         'patches': patches, 'rows': rows})
    # Text fragments without CfgPatches belong to the nearest enclosing config
    # directory in the same PBO. Never infer ownership from a provider's name.
    for doc in docs:
        if doc['patches']:
            continue
        member = doc['member'].lower().replace('\\', '/')
        enclosing = [d for d in docs if d['pbo'] == doc['pbo'] and d['patches'] and
                     member.startswith(d['member'].lower().replace('\\', '/').rsplit('/', 1)[0] + '/')]
        roots = [d for d in docs if d['pbo'] == doc['pbo'] and d['patches'] and
                 '/' not in d['member'].replace('\\', '/')]
        candidates = sorted(enclosing or roots, key=lambda d: len(d['member']), reverse=True)
        if candidates:
            doc['enclosing_patches'] = candidates[0]['patches']
    return docs, skipped
