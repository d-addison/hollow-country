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
from functools import cached_property
import os
import re

from tools.validate import source_cache

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


def clean(text, directives=None):
    """Return text with comments and string-literal contents replaced by spaces.

    Length and newlines are preserved, so offsets and line numbers still match
    the original. String quotes are kept ("" stays a string token). If supplied,
    directives receives (offset, keyword) for real preprocessor directives."""
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
            if directives is not None:
                directive = re.match(r'#\s*(\w+)', text[i:])
                if directive:
                    directives.append((i, directive.group(1)))
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


def split_parameters(text):
    """Split a parameter list on top-level commas, also outside <> generics.

    Only for declarations, where '<' is always a template bracket (defaults are
    literals). split_top must not do this: expressions compare with '<'.
    """
    parts, depth, current = [], 0, []
    for ch in text:
        if ch in '([<':
            depth += 1
        elif ch in ')]>':
            depth = max(depth - 1, 0)
        if ch == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
            continue
        current.append(ch)
    parts.append(''.join(current))
    return parts


@dataclass
class Field:
    name: str
    type: str
    modifiers: frozenset
    initializer: str
    offset: int
    # Preserve the existing masked initializer for all structural consumers.
    # Only the JSON-default audit needs literal contents, including whitespace.
    string_initializer: str = field(default='', compare=False)

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
        for part in split_parameters(self.params):
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


@dataclass
class EnumDef:
    name: str
    offset: int
    body_start: int
    body_end: int


@dataclass
class MethodSignature:
    name: str
    params: str
    modifiers: frozenset
    offset: int
    end: int             # offset immediately after the closing ')'


@dataclass(frozen=True)
class ParseIssue:
    offset: int
    message: str


class Source:
    """One authored .c file: raw text, cleaned text and its top-level structure."""

    def __init__(self, path, text, root=None, mod=None):
        self.path = Path(path)
        self.rel = self.path.relative_to(root).as_posix() if root else self.path.as_posix()
        self.mod = mod
        self.text = text
        self.directives = []
        self.code = clean(text, self.directives)
        self._lines = [m.start() for m in re.finditer('\n', self.code)]
        self.layer = next((LAYERS.index(p) for p in self.path.parts if p in LAYERS), None)
        self.classes, self.functions, self.enums, self.typedefs = [], [], [], {}
        self.parse_issues = []
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

    def _method(self, header_start, brace, end, owner=None, prefix=False):
        # clean() has blanked comments and string contents, so literal brackets
        # (including escaped quotes) cannot affect this attribute nesting count.
        while header_start < brace:
            if self.code[header_start].isspace():
                header_start += 1
            elif self.code[header_start] == '[':
                attribute_start = header_start
                depth = 1
                header_start += 1
                while header_start < brace and depth:
                    ch = self.code[header_start]
                    if ch == '[':
                        depth += 1
                    elif ch == ']':
                        depth -= 1
                    header_start += 1
                if depth:
                    # A { } array argument such as [Attr({"a"})] puts the scan's
                    # brace inside the attribute call: that is not unbalanced.
                    attribute = self.code[attribute_start:brace]
                    if attribute.count('(') > attribute.count(')'):
                        return None
                    issue = ParseIssue(attribute_start, 'unbalanced method attribute: missing closing ]')
                    if issue not in self.parse_issues:
                        self.parse_issues.append(issue)
                    return None
            else:
                break
        header = self.code[header_start:brace]
        paren = header.find('(')
        if paren < 0:
            return None
        close = matching_paren(header, paren)
        if close == len(header):
            return None
        before = header[:paren]
        name = re.search(r'(~?[A-Za-z_]\w*)\s*$', before)
        if not name:
            return None
        words = before[:name.start()].split()
        modifiers = frozenset(w for w in words if w in MODIFIERS)
        return_type = ' '.join(w for w in words if w not in MODIFIERS)
        trailing_start = header_start + close + 1
        if not prefix and header[close + 1:].strip():
            # Native prototypes may end at a newline without a semicolon. They
            # are signatures, never the owner of a later declaration's body.
            if modifiers & {'proto', 'native'} and self._line_terminated(trailing_start, brace):
                return self._method(trailing_start, brace, end, owner)
            # The preprocessor has no selected branch in this source model.
            # Retain the first complete alternative and register its body once.
            alternative = next((offset for offset, directive in self.directives
                                if trailing_start <= offset < brace and directive in {'else', 'elif'}), None)
            if alternative is None or self.code[trailing_start:alternative].strip():
                return None
        if name.group(1) in {'if', 'while', 'for', 'foreach', 'switch', 'return', 'else'}:
            return None
        return Method(name.group(1), return_type, modifiers, header[paren + 1:close],
                      header_start + name.start(1), brace, end, owner)

    def _line_terminated(self, start, stop):
        """Whether a completed native header ends before the next code line."""
        whitespace = re.match(r'\s*', self.code[start:stop]).group()
        return '\n' in whitespace

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
                    if parsed.group(2) == 'string' and parsed.group(4) is not None:
                        start = statement_start + len(statement) - len(statement.lstrip()) + parsed.start(4)
                        # Quote spans come from cleaned code, so commented-out
                        # literals cannot become an initializer. Recover only
                        # those literal spans; keep structural parsing masked.
                        definition.fields[-1].string_initializer = re.sub(
                            r'"[^"\n]*"', lambda m: self.text[start + m.start():start + m.end()],
                            parsed.group(4)).strip()
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

    def class_signatures(self, definition):
        """All direct methods, including native/bodyless declarations, of a class."""
        return [signature for signature in self.signatures
                if definition.body_start < signature.offset < definition.body_end]

    def local_declarations(self, method):
        """(name, declared type, start, scope end) for explicit local bindings.

        Includes foreach and for headers. Unknown/auto types are retained to
        shadow fields; this deliberately does not infer expression types.
        Offsets are absolute. A for/foreach binding ends with its loop body.
        """
        body = self.body(method)
        scopes, stack = {}, []
        for index, ch in enumerate(body):
            if ch == '{':
                stack.append(index)
            elif ch == '}' and stack:
                scopes[stack.pop()] = index
        declarations = []
        pattern = re.compile(r'(?<![\w.])([A-Za-z_]\w*(?:\s*<[^;(){}=]*>)?)'
                             r'\s+([A-Za-z_]\w*)\s*(?=[=;\[,:)]|$)')
        for match in pattern.finditer(body):
            kind = re.sub(r'\s+', '', match[1])
            if kind in MODIFIERS or kind in {'return', 'new', 'delete', 'else', 'case', 'throw'}:
                continue
            end = min((close for start, close in scopes.items()
                       if start < match.start() < close), default=len(body))
            # Loop header variables have the loop's scope, not the containing
            # block's. Match only enclosing headers (not earlier loops).
            for loop in re.finditer(r'\b(?:for|foreach)\s*\(', body[:match.start()]):
                close = matching_paren(body, loop.end() - 1)
                if close > match.start():
                    after = close + 1
                    while after < len(body) and body[after].isspace():
                        after += 1
                    end = scopes.get(after, body.find(';', after))
                    if end < 0:
                        end = len(body)
            declarations.append((match[2], kind, method.body_start + match.start(),
                                 method.body_start + end))
            # Preserve the declared type in common grouped declarations such
            # as HCInfectedSnapshot a, b; (not separate typed foreach slots).
            position = match.end()
            while True:
                following = re.match(r',\s*([A-Za-z_]\w*)\s*(?=[,;=])', body[position:])
                if not following:
                    break
                declarations.append((following[1], kind,
                                     method.body_start + position + following.start(1),
                                     method.body_start + end))
                position += following.end()
        return declarations

    @property
    def methods(self):
        """Class methods and file functions in source order (definitions only)."""
        return sorted(self.functions + [m for c in self.classes for m in c.methods],
                      key=lambda m: m.offset)

    @cached_property
    def signatures(self):
        """Method headers, including bodyless declarations, in source order.

        Keep prototypes separate from methods: body-based lint rules must never
        treat a declaration's semicolon as an executable body.
        """
        methods = list(self.methods)
        regions = [(0, len(self.code))] + [(c.body_start + 1, c.body_end) for c in self.classes]
        for position, stop in regions:
            while position < stop:
                brace = self.code.find('{', position, stop)
                semi = self.code.find(';', position, stop)
                boundary = min(p for p in (brace, semi, stop) if p >= 0)
                candidate = self._method(position, boundary, boundary, prefix=True)
                if candidate and candidate.modifiers & {'proto', 'native'}:
                    close = self.code.find('(', candidate.offset) + len(candidate.params) + 2
                    has_body = boundary == brace and not self.code[close:brace].strip()
                    if not has_body and (self._line_terminated(close, boundary) or close == stop):
                        methods.append(candidate)
                        position = close
                        continue
                if brace >= 0 and (semi < 0 or brace < semi):
                    position = matching_brace(self.code, brace) + 1
                elif semi >= 0:
                    header = self.code[position:semi]
                    method = self._method(position, semi, semi)
                    if method and '=' not in header.split('(', 1)[0]:
                        methods.append(method)
                    position = semi + 1
                else:
                    break
        return [MethodSignature(m.name, m.params, m.modifiers, m.offset,
                                self.code.find('(', m.offset) + len(m.params) + 2)
                for m in sorted(methods, key=lambda m: m.offset)]

    def header_start(self, method):
        """Start of the declaration containing method, including its modifiers."""
        return max(self.code.rfind(ch, 0, method.offset) for ch in ';{}') + 1

    @property
    def enum_blocks(self):
        """Enum names and brace offsets, using the same cleaned source as classes."""
        return [EnumDef(m.group(1), m.start(), m.end() - 1,
                        matching_brace(self.code, m.end() - 1))
                for m in _ENUM.finditer(self.code)]


def parse(path, text, root=None, mod=None, stat=None, persist=False):
    """Source(path, text, root, mod) through the shared parsed-source cache (see source_cache).

    Equal inputs return the same parsed object within a process, so callers must treat it as read-only.
    ``stat`` is (size, mtime_ns) of a file the text came from; ``persist`` also uses the on-disk cache
    when $HC_SOURCE_CACHE_DIR is set."""
    return source_cache.shared().get(lambda: Source(path, text, root, mod), path, text, root, mod, stat, persist)


def _read_file(path, root, mod):
    path = Path(path)
    with path.open('rb') as handle:
        info = os.fstat(handle.fileno())
        data = handle.read()
    # Same text as Path.read_text: universal newlines, so offsets match the pre-cache behaviour.
    text = data.decode('utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n')
    return parse(path, text, root, mod, (info.st_size, info.st_mtime_ns), True)


def read_source(path, root=None):
    """Read a source once, or reuse an already parsed Source supplied by a check."""
    if isinstance(path, Source):
        return path
    return _read_file(path, root, None)


def mod_sources(root, mods=('HollowCountry', 'HollowCountryAnims', 'HollowCountryExpansionAI', 'HollowCountryTest')):
    """Authored script sources in deterministic mod load order, then path order."""
    root = Path(root)
    result = []
    for mod in mods:
        scripts = root / 'mods' / mod / 'scripts'
        if not scripts.is_dir():
            continue
        for path in sorted(scripts.rglob('*.c'), key=lambda p: p.relative_to(scripts).as_posix().lower()):
            result.append(_read_file(path, root, mod))
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
