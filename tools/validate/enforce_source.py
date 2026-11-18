"""A small, deterministic structural model of authored Enforce Script (.c) files.

Standard library only. It is not a compiler: it blanks comments and string
contents (keeping every offset and line number), then finds top-level classes,
enums and typedefs, class fields and method bodies by brace matching. Checks in
tools/validate build on this model instead of each test re-deriving regexes.
Nothing here establishes DayZ behaviour; only a native compile/boot does.
"""
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
import re

LAYERS = ('1_Core', '2_GameLib', '3_Game', '4_World', '5_Mission')
PRIMITIVES = frozenset({'int', 'float', 'bool', 'string', 'vector', 'void', 'typename', 'auto', 'func', 'Class'})
MODIFIERS = frozenset({'ref', 'autoptr', 'static', 'protected', 'private', 'const', 'owned', 'notnull',
                       'reference', 'override', 'proto', 'native', 'external', 'volatile', 'event', 'sealed'})
_CLASS = re.compile(r'\b(modded\s+)?(?:sealed\s+)?class\s+([A-Za-z_]\w*)\s*(?:<[^>{;]*>)?\s*'
                    r'(?:(?::|extends)\s*([A-Za-z_]\w*)\s*(?:<[^{;]*>)?)?\s*\{')
_ENUM = re.compile(r'\benum\s+([A-Za-z_]\w*)\s*(?::\s*\w+\s*)?\{')
_TYPEDEF = re.compile(r'\btypedef\s+([^;]+?)\s+([A-Za-z_]\w*)\s*;')
_FIELD = re.compile(r'^((?:(?:ref|autoptr|static|protected|private|const|owned|notnull|reference)\s+)*)'
                    r'([A-Za-z_]\w*(?:\s*<.*>)?)\s+([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*(?:=\s*(.*))?$', re.S)


def clean(text):
    """Return text with comments and string-literal contents replaced by spaces.

    Length and newlines are preserved, so offsets and line numbers still match
    the original. String quotes are kept ("" stays a string token)."""
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == '/' and i + 1 < n and text[i + 1] == '/':
            while i < n and text[i] != '\n':
                out[i] = ' '
                i += 1
        elif ch == '/' and i + 1 < n and text[i + 1] == '*':
            end = text.find('*/', i + 2)
            end = n if end < 0 else end + 2
            for j in range(i, end):
                if out[j] != '\n':
                    out[j] = ' '
            i = end
        elif ch == '#' and not text[text.rfind('\n', 0, i) + 1:i].strip():
            while i < n and text[i] != '\n':   # preprocessor line (#ifdef/#endif/#define)
                out[i] = ' '
                i += 1
        elif ch == '"':
            i += 1
            while i < n and text[i] != '"' and text[i] != '\n':
                if text[i] == '\\' and i + 1 < n:
                    out[i] = ' '
                    i += 1
                out[i] = ' '
                i += 1
            i += 1
        else:
            i += 1
    return ''.join(out)


def matching_brace(text, start):
    """Offset of the '}' that closes the '{' at start (len(text) if unbalanced)."""
    depth = 0
    for position in range(start, len(text)):
        ch = text[position]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return position
    return len(text)


def matching_paren(text, start):
    depth = 0
    for position in range(start, len(text)):
        ch = text[position]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return position
    return len(text)


def split_top(text, separator):
    """Split on a separator string that is outside (), [] and <> nesting."""
    parts, depth, current, i = [], 0, [], 0
    while i < len(text):
        ch = text[i]
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth -= 1
        if depth == 0 and text.startswith(separator, i):
            parts.append(''.join(current))
            current = []
            i += len(separator)
            continue
        current.append(ch)
        i += 1
    parts.append(''.join(current))
    return parts


@dataclass
class Field:
    name: str
    type: str
    modifiers: frozenset
    initializer: str
    offset: int

    @property
    def strong(self):
        return bool(self.modifiers & {'ref', 'autoptr'})


@dataclass
class Method:
    name: str
    return_type: str
    modifiers: frozenset
    params: str
    offset: int          # offset of the method name
    body_start: int      # offset of '{'
    body_end: int        # offset of matching '}'
    owner: object = None

    def parameters(self):
        """[(type, name, is_out)] for a parameter list; defaults are dropped."""
        result = []
        for part in split_top(self.params, ','):
            part = part.split('=')[0].strip()
            words = re.findall(r'[A-Za-z_]\w*(?:\s*<[^()]*>)?', part)
            if len(words) < 2:
                continue
            result.append((words[-2], words[-1], 'out' in words[:-1] or 'inout' in words[:-1]))
        return result


@dataclass
class ClassDef:
    name: str
    base: str
    modded: bool
    offset: int
    body_start: int
    body_end: int
    source: object = None
    fields: list = field(default_factory=list)
    methods: list = field(default_factory=list)


class Source:
    """One authored .c file: raw text, cleaned text and its top-level structure."""

    def __init__(self, path, text, root=None, mod=None):
        self.path = Path(path)
        self.rel = self.path.relative_to(root).as_posix() if root else self.path.as_posix()
        self.mod = mod
        self.text = text
        self.code = clean(text)
        self._lines = [m.start() for m in re.finditer('\n', self.code)]
        self.layer = next((LAYERS.index(p) for p in self.path.parts if p in LAYERS), None)
        self.classes, self.functions, self.enums, self.typedefs = [], [], [], {}
        self._parse()

    def line_of(self, offset):
        return bisect_right(self._lines, offset - 1) + 1 if offset > 0 else 1

    def line_text(self, offset):
        start = self.text.rfind('\n', 0, offset) + 1
        end = self.text.find('\n', offset)
        return self.text[start:end if end >= 0 else len(self.text)].strip()

    def _parse(self):
        code, position = self.code, 0
        for match in _TYPEDEF.finditer(code):
            self.typedefs[match.group(2)] = match.group(1).strip()
        while position < len(code):
            nxt = code.find('{', position)
            if nxt < 0:
                break
            header_start = max(code.rfind(';', position, nxt), code.rfind('}', position, nxt)) + 1
            header_start = max(header_start, position)
            header = code[header_start:nxt + 1]
            end = matching_brace(code, nxt)
            cls = _CLASS.search(header)
            enum = _ENUM.search(header)
            if cls:
                definition = ClassDef(cls.group(2), cls.group(3) or '', bool(cls.group(1)),
                                      header_start + cls.start(2), nxt, end, self)
                self._members(definition)
                self.classes.append(definition)
            elif enum:
                self.enums.append(enum.group(1))
            else:
                method = self._method(header_start, nxt, end)
                if method:
                    self.functions.append(method)
            position = end + 1

    def _method(self, header_start, brace, end, owner=None):
        header = self.code[header_start:brace]
        paren = header.find('(')
        if paren < 0:
            return None
        close = matching_paren(header, paren)
        if header[close + 1:].strip():
            return None
        before = header[:paren]
        name = re.search(r'(~?[A-Za-z_]\w*)\s*$', before)
        if not name:
            return None
        words = before[:name.start()].split()
        modifiers = frozenset(w for w in words if w in MODIFIERS)
        return_type = ' '.join(w for w in words if w not in MODIFIERS)
        if name.group(1) in {'if', 'while', 'for', 'foreach', 'switch', 'return', 'else'}:
            return None
        return Method(name.group(1), return_type, modifiers, header[paren + 1:close],
                      header_start + name.start(1), brace, end, owner)

    def _members(self, definition):
        code, position, stop = self.code, definition.body_start + 1, definition.body_end
        statement_start = position
        while position < stop:
            ch = code[position]
            if ch == ';':
                statement = code[statement_start:position]
                parsed = _FIELD.match(statement.strip())
                if parsed and '(' not in parsed.group(2) and parsed.group(2) not in {'return', 'typedef'}:
                    words = parsed.group(1).split()
                    offset = statement_start + len(statement) - len(statement.lstrip()) + parsed.start(3)
                    definition.fields.append(Field(parsed.group(3), re.sub(r'\s+', '', parsed.group(2)),
                                                   frozenset(words), (parsed.group(4) or '').strip(), offset))
                statement_start = position + 1
            elif ch == '{':
                end = matching_brace(code, position)
                method = self._method(statement_start, position, end, definition)
                if method:
                    definition.methods.append(method)
                position = end
                statement_start = end + 1
            position += 1

    def body(self, method):
        return self.code[method.body_start:method.body_end + 1]


def mod_sources(root, mods=('HollowCountry', 'HollowCountryAnims', 'HollowCountryExpansionAI')):
    """Authored script sources in deterministic mod load order, then path order."""
    root = Path(root)
    result = []
    for mod in mods:
        scripts = root / 'mods' / mod / 'scripts'
        if not scripts.is_dir():
            continue
        for path in sorted(scripts.rglob('*.c'), key=lambda p: p.relative_to(scripts).as_posix().lower()):
            result.append(Source(path, path.read_text(encoding='utf-8', errors='replace'), root, mod))
    return result


def native_types_by_layer(cache):
    """{layer index: class/enum/typedef names} from an extracted engine script cache (local only)."""
    visible = {}
    for index, layer in enumerate(LAYERS):
        names = set()
        for source in sorted((Path(cache) / layer).rglob('*.c')):
            text = clean(source.read_text(encoding='utf-8', errors='replace'))
            names.update(re.findall(r'^\s*(?:modded\s+|sealed\s+)*(?:class|enum)\s+(\w+)', text, re.M))
            names.update(m.group(2) for m in _TYPEDEF.finditer(text))
        visible[index] = names
    return visible
