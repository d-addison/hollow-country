"""Bounded, read-only PBO header and rapified ``config.bin`` reader (standard library only).

Only what the firearm audit needs is decoded: top-level classes of chosen config roots
with their parent, ``scope``, ``model``, ``ammo``, ``count`` and ``magazines``. PBO members
are streamed with explicit size budgets; compressed members and unknown rap entry types are
refused rather than guessed. A parsed config is static file evidence, never proof of what
the running engine does.
"""
import struct

MAX_HEADER_BYTES = 16 * 1024 * 1024
MAX_ENTRIES = 200_000
MAX_NAME = 1024
MAX_CONFIG_BYTES = 64 * 1024 * 1024
MAX_CLASSES = 200_000
MAX_BODY_ENTRIES = 100_000
MAX_ARRAY_ITEMS = 100_000
MAX_ARRAY_DEPTH = 8
PACK_VERS = 0x56657273
SCALAR_FIELDS = ('scope', 'model', 'ammo', 'count')
ARRAY_FIELDS = ('magazines', 'chamberableFrom', 'handAnim')
CHUNK = 65536


class _HeaderReader:
    """Incremental reader that bounds how many header bytes may be consumed."""

    def __init__(self, handle, limit):
        self.handle, self.limit, self.buffer, self.position, self.consumed = handle, limit, b'', 0, 0

    def take(self, n):
        while len(self.buffer) - self.position < n:
            block = self.handle.read(CHUNK)
            if not block:
                raise ValueError('truncated PBO header')
            self.buffer = self.buffer[self.position:] + block
            self.position = 0
        data = self.buffer[self.position:self.position + n]
        self.position += n
        self.consumed += n
        if self.consumed > self.limit:
            raise ValueError('PBO header exceeds budget')
        return data

    def cstring(self):
        out = bytearray()
        while True:
            byte = self.take(1)
            if byte == b'\0':
                return out.decode('latin-1')
            out += byte
            if len(out) > MAX_NAME:
                raise ValueError('PBO header name exceeds budget')


def read_pbo_index(path, max_entries=MAX_ENTRIES, max_header_bytes=MAX_HEADER_BYTES):
    """Return ``{'prefix', 'entries', 'header_end', 'size'}`` without reading member data."""
    entries, props, prefix = [], {}, ''
    with open(path, 'rb') as handle:
        reader = _HeaderReader(handle, max_header_bytes)
        offset = 0
        while True:
            name = reader.cstring()
            method, original, _reserved, _stamp, size = struct.unpack('<IIIII', reader.take(20))
            if name == '' and method == PACK_VERS:
                while True:
                    key = reader.cstring()
                    if key == '':
                        break
                    props[key.lower()] = reader.cstring()
                continue
            if name == '':
                break
            if len(entries) >= max_entries:
                raise ValueError('PBO entry count exceeds budget')
            entries.append({'name': name, 'method': method, 'original': original,
                            'size': size, 'offset': offset})
            offset += size
        header_end = reader.consumed
        handle.seek(0, 2)
        file_size = handle.tell()
    if header_end + offset > file_size:
        raise ValueError('PBO data extends past the end of file')
    prefix = props.get('prefix', '')
    return {'prefix': prefix, 'entries': entries, 'header_end': header_end, 'size': file_size}


def read_member(path, index, name, max_bytes=MAX_CONFIG_BYTES):
    """Read one uncompressed member (case-insensitive name); None when absent."""
    wanted = name.lower().replace('/', '\\')
    for entry in index['entries']:
        if entry['name'].lower().replace('/', '\\') == wanted:
            if entry['method'] != 0:
                raise ValueError('compressed PBO member unsupported')
            if entry['size'] > max_bytes:
                raise ValueError('PBO member exceeds budget')
            with open(path, 'rb') as handle:
                handle.seek(index['header_end'] + entry['offset'])
                data = handle.read(entry['size'])
            if len(data) != entry['size']:
                raise ValueError('truncated PBO member')
            return data
    return None


def normalize_path(text):
    return text.lower().replace('/', '\\').lstrip('\\')


def model_paths(index):
    """Lower-case normalized full paths of .p3d members, using the PBO prefix."""
    prefix = normalize_path(index['prefix'])
    paths = set()
    for entry in index['entries']:
        if entry['name'].lower().endswith('.p3d'):
            paths.add(normalize_path((prefix + '\\' if prefix else '') + entry['name']))
    return paths


class _Rap:
    def __init__(self, data):
        self.data = data
        self.size = len(data)

    def byte(self, pos):
        if pos >= self.size:
            raise ValueError('truncated rapified config')
        return self.data[pos], pos + 1

    def cint(self, pos):
        value, pos = self.byte(pos)
        if value & 0x80:
            extra, pos = self.byte(pos)
            value += (extra - 1) * 128
        return value, pos

    def cstring(self, pos):
        end = self.data.find(b'\0', pos)
        if end < 0 or end - pos > MAX_NAME:
            raise ValueError('bad rapified string')
        return self.data[pos:end].decode('latin-1'), end + 1

    def fixed(self, pos, fmt):
        n = struct.calcsize(fmt)
        if pos + n > self.size:
            raise ValueError('truncated rapified config')
        return struct.unpack_from(fmt, self.data, pos)[0], pos + n

    def array_item(self, pos, depth):
        kind, pos = self.byte(pos)
        if kind == 0:
            return self.cstring(pos)
        if kind == 1:
            return self.fixed(pos, '<f')
        if kind == 2:
            return self.fixed(pos, '<i')
        if kind == 3:
            return self.array(pos, depth + 1)
        raise ValueError('unsupported rapified array element')

    def array(self, pos, depth=0):
        if depth > MAX_ARRAY_DEPTH:
            raise ValueError('rapified array nesting exceeds budget')
        count, pos = self.cint(pos)
        if count > MAX_ARRAY_ITEMS:
            raise ValueError('rapified array exceeds budget')
        items = []
        for _ in range(count):
            item, pos = self.array_item(pos, depth)
            items.append(item)
        return items, pos

    def entries(self, pos):
        """Yield (kind, name, payload) for one class body; payload class = body offset."""
        parent, pos = self.cstring(pos)
        count, pos = self.cint(pos)
        if count > MAX_BODY_ENTRIES:
            raise ValueError('rapified class exceeds entry budget')
        out = []
        for _ in range(count):
            kind, pos = self.byte(pos)
            if kind == 0:
                name, pos = self.cstring(pos)
                offset, pos = self.fixed(pos, '<I')
                out.append(('class', name, offset))
            elif kind == 1:
                sub, pos = self.byte(pos)
                name, pos = self.cstring(pos)
                if sub == 0:
                    value, pos = self.cstring(pos)
                elif sub == 1:
                    value, pos = self.fixed(pos, '<f')
                elif sub == 2:
                    value, pos = self.fixed(pos, '<i')
                else:
                    raise ValueError('unsupported rapified value type')
                out.append(('value', name, value))
            elif kind == 2:
                name, pos = self.cstring(pos)
                value, pos = self.array(pos)
                out.append(('array', name, value))
            elif kind == 3 or kind == 4:
                name, pos = self.cstring(pos)
                out.append(('extern' if kind == 3 else 'delete', name, None))
            elif kind == 5:
                _flag, pos = self.fixed(pos, '<I')
                name, pos = self.cstring(pos)
                value, pos = self.array(pos)
                out.append(('array', name, value))
            else:
                raise ValueError('unsupported rapified entry type')
        return parent, out


def _whole(number):
    return int(number) if float(number) == int(number) else number


def parse_rap(data, roots, max_bytes=MAX_CONFIG_BYTES):
    """Return ``{root: {class: {parent, scope, model, ammo, count, magazines}}}``.

    Only direct child classes of the named roots are decoded, and only the selected
    fields. ``scope`` is the class's own declaration; inheritance is resolved separately.
    """
    if len(data) > max_bytes:
        raise ValueError('config exceeds budget')
    if len(data) < 16 or data[:4] != b'\0raP':
        raise ValueError('not a rapified config')
    rap = _Rap(data)
    _, root_entries = rap.entries(16)
    result = {name: {} for name in roots}
    canonical = {name.lower(): name for name in roots}  # engine config class names are case-insensitive
    seen = 0
    for kind, name, offset in root_entries:
        if kind != 'class' or name.lower() not in canonical:
            continue
        root_name = canonical[name.lower()]
        if offset >= len(data):
            raise ValueError('rapified class offset out of range')
        _parent, children = rap.entries(offset)
        for ckind, cname, cpos in children:
            if ckind != 'class':
                continue
            seen += 1
            if seen > MAX_CLASSES:
                raise ValueError('config class count exceeds budget')
            if cpos >= len(data):
                raise ValueError('rapified class offset out of range')
            parent, body = rap.entries(cpos)
            row = {'parent': parent or None, 'scope': None, 'model': None, 'ammo': None,
                   'count': None, 'magazines': None, 'chamberableFrom': None, 'handAnim': None}
            for bkind, bname, value in body:
                if bkind == 'value' and bname in SCALAR_FIELDS:
                    row[bname] = _whole(value) if isinstance(value, (int, float)) else value
                elif bkind == 'array' and bname in ARRAY_FIELDS:
                    row[bname] = [v for v in value if isinstance(v, str)]
            row = {k: v for k, v in row.items() if v is not None or k in ('parent', 'scope')}
            result[root_name][cname] = row
    return result


def ancestry(classes, name, limit=128):
    """Class then parents, stopping at unknown parents, cycles or the limit."""
    chain, seen = [], set()
    while name and name in classes and name not in seen and len(chain) < limit:
        seen.add(name)
        chain.append(name)
        name = classes[name].get('parent')
    return chain


def resolve_scope(classes, name):
    """First explicit ``scope`` up the parent chain, or None when it cannot be resolved."""
    seen = set()
    while name in classes and name not in seen and len(seen) < 128:
        seen.add(name)
        scope = classes[name].get('scope')
        if scope is not None:
            return scope
        name = classes[name].get('parent')
        if not name:
            return None
    return None


def config_member_names(index):
    """Names of every ``config.bin`` member, at the root or in any sub-folder."""
    return [e['name'] for e in index['entries']
            if e['name'].replace('/', '\\').lower().split('\\')[-1] == 'config.bin']


def read_configs(path, roots, index=None):
    """Merge the selected roots from every ``config.bin`` member of one PBO."""
    index = index or read_pbo_index(path)
    merged = {name: {} for name in roots}
    for member in config_member_names(index):
        data = read_member(path, index, member)
        for root, classes in parse_rap(data, roots).items():
            merged[root].update(classes)
    return merged


def resolve_field(classes, name, field):
    """First non-None value of ``field`` up the parent chain (None if unresolved)."""
    seen = set()
    while name in classes and name not in seen and len(seen) < 128:
        seen.add(name)
        value = classes[name].get(field)
        if value is not None:
            return value
        name = classes[name].get('parent')
        if not name:
            return None
    return None
