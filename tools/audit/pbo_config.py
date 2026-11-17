"""Bounded, read-only PBO header and rapified ``config.bin`` reader (standard library only).

Only what the firearm audit needs is decoded: top-level classes of chosen config roots
with their parent, ``scope``, ``model``, ``ammo``, ``count`` and ``magazines``. PBO members
are streamed with explicit size budgets; compressed members and unknown rap entry types are
refused rather than guessed. A parsed config is static file evidence, never proof of what
the running engine does.
"""
import re
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
ARRAY_FIELDS = ('magazines', 'chamberableFrom', 'handAnim', 'attachments', 'inventorySlot')
MAX_TEXT_TOKENS = 4_000_000
MAX_TEXT_DEPTH = 16
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
                out.append(('array+', name, value))  # ``+=``: the array extends the parent's, never replaces it
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
            appended = []
            for bkind, bname, value in body:
                if bkind == 'value' and bname in SCALAR_FIELDS:
                    row[bname] = _whole(value) if isinstance(value, (int, float)) else value
                elif bkind in ('array', 'array+') and bname in ARRAY_FIELDS:
                    row[bname] = [v for v in value if isinstance(v, str)]
                    if bkind == 'array+' and bname not in appended:
                        appended.append(bname)
            if appended:
                row['appended'] = appended
            row = {k: v for k, v in row.items() if v is not None or k in ('parent', 'scope')}
            result[root_name][cname] = row
    return result


_TEXT_TOKEN = re.compile(r'''
    (?P<str>"(?:[^"]|"")*")
  | (?P<id>[A-Za-z_][A-Za-z0-9_.\\]*)
  | (?P<num>[-+]?(?:0[xX][0-9A-Fa-f]+|[0-9]+\.?[0-9]*(?:[eE][-+]?[0-9]+)?|\.[0-9]+))
  | (?P<op>\+=|[{}\[\]=;:,])
  | (?P<other>\S)
''', re.VERBOSE)
_KEYWORD_SCOPE = {'public': 2, 'protected': 1, 'private': 0}


def _at_line_start(text, i):
    j = i - 1
    while j >= 0 and text[j] in ' \t':
        j -= 1
    return j < 0 or text[j] == '\n'


def _strip_text(text):
    """Remove comments and preprocessor lines while keeping string literals intact."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            j = i + 1
            while j < n:
                if text[j] == '"':
                    if j + 1 < n and text[j + 1] == '"':
                        j += 2
                        continue
                    break
                j += 1
            if j >= n:
                raise ValueError('unterminated string in text config')
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith('//', i):
            j = text.find('\n', i)
            i = n if j < 0 else j
        elif text.startswith('/*', i):
            j = text.find('*/', i + 2)
            if j < 0:
                raise ValueError('unterminated comment in text config')
            out.append(' ')
            i = j + 2
        elif c == '#' and _at_line_start(text, i):
            while True:  # preprocessor line, with backslash continuations
                j = text.find('\n', i)
                if j < 0:
                    i = n
                    break
                continued = text[i:j].rstrip().endswith('\\')
                i = j
                if not continued:
                    break
                i += 1
        else:
            out.append(c)
            i += 1
    return ''.join(out)


class _Tokens:
    def __init__(self, text, max_tokens):
        self.iter = (self._classify(m) for m in _TEXT_TOKEN.finditer(text))
        self.buffer, self.count, self.max_tokens = [], 0, max_tokens

    @staticmethod
    def _classify(match):
        kind = match.lastgroup
        value = match.group()
        if kind == 'str':
            value = value[1:-1].replace('""', '"')
        return kind, value

    def peek(self):
        if not self.buffer:
            self.count += 1
            if self.count > self.max_tokens:
                raise ValueError('text config exceeds token budget')
            self.buffer.append(next(self.iter, ('eof', '')))
        return self.buffer[0]

    def next(self):
        token = self.peek()
        self.buffer.pop(0)
        return token


def _expect(tokens, value):
    kind, got = tokens.next()
    if got != value or kind in ('str',):
        raise ValueError(f'malformed text config: expected {value!r}')


def _skip_braced(tokens, depth):
    """Consume tokens up to and including the matching ``}`` (the ``{`` is already consumed)."""
    while True:
        kind, value = tokens.next()
        if kind == 'eof':
            raise ValueError('truncated text config')
        if kind == 'op' and value == '{':
            depth += 1
            if depth > MAX_TEXT_DEPTH:
                raise ValueError('text config nesting exceeds budget')
        elif kind == 'op' and value == '}':
            depth -= 1
            if depth == 0:
                return


def _skip_statement(tokens):
    while True:
        kind, value = tokens.next()
        if kind == 'eof':
            raise ValueError('truncated text config')
        if kind == 'op' and value == ';':
            return
        if kind == 'op' and value == '{':
            _skip_braced(tokens, 1)


def _text_array(tokens, depth=0):
    if depth > MAX_ARRAY_DEPTH:
        raise ValueError('text array nesting exceeds budget')
    _expect(tokens, '{')
    items = []
    while True:
        kind, value = tokens.next()
        if kind == 'eof':
            raise ValueError('truncated text config')
        if kind == 'op' and value == '}':
            return items
        if kind == 'op' and value == ',':
            continue
        if len(items) >= MAX_ARRAY_ITEMS:
            raise ValueError('text array exceeds budget')
        if kind == 'op' and value == '{':
            tokens.buffer.insert(0, (kind, value))
            items.append(_text_array(tokens, depth + 1))
        elif kind == 'str':
            items.append(value)
        elif kind == 'num':
            items.append(_text_number(value))
        else:
            items.append(None)  # identifiers/expressions are never trusted as class names


def _text_number(value):
    try:
        return int(value, 0) if value.lower().lstrip('+-').startswith('0x') else (
            int(value) if re.fullmatch(r'[-+]?[0-9]+', value) else float(value))
    except ValueError:
        return None


def _text_scalar(tokens):
    parts = []
    while True:
        kind, value = tokens.next()
        if kind == 'eof':
            raise ValueError('truncated text config')
        if kind == 'op' and value == ';':
            break
        if kind == 'op' and value == '{':
            _skip_braced(tokens, 1)
            parts.append(('other', '{}'))
            continue
        parts.append((kind, value))
    if len(parts) != 1:
        return None
    kind, value = parts[0]
    if kind == 'str':
        return value
    if kind == 'num':
        return _text_number(value)
    return value if kind == 'id' else None


def _text_class_body(tokens, depth):
    """Parse one first-level class body (fields only); nested classes are skipped."""
    row = {'parent': None, 'scope': None, 'model': None, 'ammo': None, 'count': None, 'magazines': None,
           'chamberableFrom': None, 'handAnim': None, 'attachments': None, 'inventorySlot': None}
    appended = []
    while True:
        kind, value = tokens.next()
        if kind == 'eof':
            raise ValueError('truncated text config')
        if kind == 'op' and value == '}':
            break
        if kind == 'op' and value == ';':
            continue
        if kind == 'id' and value == 'class':
            kind2, _name = tokens.next()
            nxt = tokens.next()
            if nxt == ('op', ':'):
                tokens.next()
                nxt = tokens.next()
            if nxt == ('op', '{'):
                _skip_braced(tokens, 1)
                _expect(tokens, ';')
            elif nxt != ('op', ';'):
                raise ValueError('malformed nested class')
            continue
        if kind == 'id':
            nxt = tokens.peek()
            if nxt == ('op', '['):
                tokens.next()
                _expect(tokens, ']')
                op_kind, op = tokens.next()
                if op not in ('=', '+='):
                    raise ValueError('malformed array assignment')
                items = _text_array(tokens)
                _expect(tokens, ';')
                if value in ARRAY_FIELDS:
                    row[value] = [v for v in items if isinstance(v, str)]
                    if op == '+=' and value not in appended:
                        appended.append(value)
                continue
            if nxt == ('op', '='):
                tokens.next()
                scalar = _text_scalar(tokens)
                if value in SCALAR_FIELDS and scalar is not None:
                    if value == 'scope' and isinstance(scalar, str):
                        scalar = _KEYWORD_SCOPE.get(scalar.lower())
                        if scalar is None:
                            continue
                    row[value] = _whole(scalar) if isinstance(scalar, (int, float)) else scalar
                continue
        _skip_statement_from(tokens, kind, value)
    if appended:
        row['appended'] = appended
    return row


def _skip_statement_from(tokens, kind, value):
    if kind == 'op' and value == '{':
        _skip_braced(tokens, 1)
    _skip_statement(tokens)


def parse_text_config(text, roots, max_bytes=MAX_CONFIG_BYTES // 4, max_tokens=MAX_TEXT_TOKENS):
    """Return the same ``{root: {class: row}}`` shape as ``parse_rap`` from plain-text config source.

    Handles derapped ``config.cpp`` text: comments, preprocessor lines, forward declarations,
    ``name[] = {..}`` and ``+=`` arrays and doubled-quote strings. Only first-level classes of the
    named roots are decoded; nested classes are skipped. Budgets bound bytes, tokens and nesting.
    """
    if isinstance(text, bytes):
        text = text.decode('latin-1')
    if len(text) > max_bytes:
        raise ValueError('text config exceeds budget')
    tokens = _Tokens(_strip_text(text), max_tokens)
    result = {name: {} for name in roots}
    canonical = {name.lower(): name for name in roots}
    seen = 0
    while True:
        kind, value = tokens.next()
        if kind == 'eof':
            return result
        if not (kind == 'id' and value == 'class'):
            _skip_statement_from(tokens, kind, value)
            continue
        _kind, name = tokens.next()
        nxt = tokens.next()
        if nxt == ('op', ':'):
            tokens.next()
            nxt = tokens.next()
        if nxt == ('op', ';'):
            continue
        if nxt != ('op', '{'):
            raise ValueError('malformed class declaration')
        if name.lower() not in canonical:
            _skip_braced(tokens, 1)
            _expect(tokens, ';')
            continue
        classes = result[canonical[name.lower()]]
        while True:
            kind, value = tokens.next()
            if kind == 'eof':
                raise ValueError('truncated text config')
            if kind == 'op' and value == '}':
                break
            if kind == 'op' and value == ';':
                continue
            if not (kind == 'id' and value == 'class'):
                _skip_statement_from(tokens, kind, value)
                continue
            _k, cname = tokens.next()
            parent = None
            nxt = tokens.next()
            if nxt == ('op', ':'):
                _k, parent = tokens.next()
                nxt = tokens.next()
            if nxt == ('op', ';'):
                continue  # forward declaration, not a definition
            if nxt != ('op', '{'):
                raise ValueError('malformed class declaration')
            seen += 1
            if seen > MAX_CLASSES:
                raise ValueError('config class count exceeds budget')
            row = _text_class_body(tokens, 1)
            _expect(tokens, ';')
            row['parent'] = parent or None
            row = {k: v for k, v in row.items() if v is not None or k in ('parent', 'scope')}
            classes[cname] = row
        _expect(tokens, ';')


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


def read_config_members(path, roots, index=None):
    """``[(member_name, {root: classes})]`` for every ``config.bin`` and plain-text ``config.cpp`` member."""
    index = index or read_pbo_index(path)
    out = []
    for entry in index['entries']:
        base = entry['name'].replace('/', '\\').lower().split('\\')[-1]
        if base not in ('config.bin', 'config.cpp'):
            continue
        data = read_member(path, index, entry['name'])
        out.append((entry['name'], parse_rap(data, roots) if base == 'config.bin'
                    else parse_text_config(data, roots)))
    return out


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
