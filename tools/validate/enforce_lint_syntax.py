"""Syntax and signature rules that the native compile gate refused on 2026-11-22 (HC-E042..HC-E047).

Registered from tools.validate.enforce_lint (``rules_for``); no command line of its own. Each rule
closes a gap that let a native compile error through an enforce_lint pass:

  HC-E042  a method redefines or overrides a parent declaration with a different signature
           (91a364d1: modded static spawner methods without ``override``; also the HCFoodCompat
           InitTemperature shape, see the note on HC-E042 below)
  HC-E043  a method named like an engine name the compiler resolves itself (``Wait``)
  HC-E044  an Enforce keyword used as a variable, parameter, field, method or enum member name
           (``foreach (Object owned : list)``), found by tokenising, not by one regex
  HC-E045  a bitwise operator inside a float expression (HCMissionBeacon.ZoneCentre)
  HC-E046  a field read on a typed receiver that has no such field (grudge.Group after the field
           was removed); HC-E012 only looked at method calls
  HC-E047  a non-static const, or a static field, read from a non-literal initializer (HC-E028 only
           covered ``static const`` of int/float/bool/string)

The pure helpers take cleaned source text only. The rules need the HC-E012 machinery of
tools.validate.enforce_lint (Project, local declarations), which imports this module, so
``rules_for(enforce_lint_module)`` binds them after enforce_lint is loaded. Standard library only.
Nothing here proves DayZ behaviour; only a native compile does.

HC-E042 and installed packs: a Workshop pack ships packed scripts, so a pack-side declaration of
Inventory_Base.InitTemperature is invisible here. The Inventory_Base override itself had the
signature of EntityAI.InitTemperature (installed 1.30: ``protected void InitTemperature()``), so no
script-only check can call it wrong; classes whose ancestors are not all visible are skipped rather
than guessed. Vanilla also overrides with a different visibility (1182 cases) and with covariant
class parameters, so neither is flagged.
"""
from collections import namedtuple
from pathlib import Path
import re

from tools.validate import enforce_source as es

RULES = {
    'HC-E042': 'method redefines or overrides a parent declaration with a different signature '
               '(missing override, parameter/return/static mismatch, or no parent method)',
    'HC-E043': 'method named like an engine name the compiler resolves itself (native compile: statement-form Wait( failed); rename it',
    'HC-E044': 'Enforce keyword used as a name (native compile: Expected name, not a keyword); tokenised, includes foreach slots and enum members',
    'HC-E045': 'bitwise or % operator inside a float expression (native compile: Unknown operator); compute it in int-only statements first',
    'HC-E046': 'field read on a typed receiver that has no such field (including parents and modded bodies)',
    'HC-E047': 'initializer must be a literal: non-static const, vector const or a static primitive that reads another class or constant (read as 0 natively, build 169)',
}

# Set by enforce_lint.main from the engine script cache it already reads; None means authored-only.
NATIVE_ROOT = None

# Names the native compiler resolves before a class method. Wait: the native gate on 2026-11-22
# refused HCEventCacheFill.Wait( ("statement-form Wait( failed"); the extracted 1.30 scripts do not
# declare it, which is why HC-E025 (names found in the scripts) could not see it.
ENGINE_RESERVED_METHODS = {'Wait': 'native compile 2026-11-22: statement-form Wait( failed (HCEventCacheFill, renamed HCWaitSite)'}

# Native boots 075 and 098, compile-xai4-01 and the 2026-11-22 gate (owned) refused these as names.
NAME_KEYWORDS = frozenset({
    'owned', 'out', 'inout', 'local', 'auto', 'ref', 'autoptr', 'proto', 'native', 'volatile', 'notnull',
    'private', 'protected', 'static', 'const', 'typename', 'thread', 'event', 'reference', 'external',
    'sealed', 'override', 'modded', 'class', 'enum', 'extends', 'typedef', 'new', 'delete', 'return',
    'null', 'this', 'super', 'if', 'else', 'while', 'for', 'foreach', 'switch', 'case', 'default',
    'break', 'continue'})
# Words that can stand between a declaration's type and its name without being a type.
NOT_A_TYPE = NAME_KEYWORDS | {'in'}

_TOKEN = re.compile(r'[A-Za-z_]\w*|\d[\w.]*|"|[<>]=?|&&|\|\||[^\s\w]')
_NAME_FOLLOWERS = frozenset({'=', ';', ',', ')', ':', '[', '('})
_PRIMITIVES = frozenset({'int', 'float', 'bool', 'string', 'vector', 'typename', 'void'})
_MODIFIER_WORDS = frozenset({'ref', 'autoptr', 'notnull', 'const', 'reference', 'owned', 'volatile', 'local'})


def _el(project):
    return project._syntax_bound


# ---------------------------------------------------------------- HC-E043

def reserved_method_names(source):
    """[(name, offset)] of declared methods, prototypes included, that use a reserved engine name."""
    found, seen = [], set()
    for method in list(source.methods) + list(source.signatures):
        if method.name in ENGINE_RESERVED_METHODS and method.offset not in seen:
            seen.add(method.offset)
            found.append((method.name, method.offset))
    return found


def rule_reserved_method_names(project, source):
    el = _el(project)
    for name, offset in reserved_method_names(source):
        owner = next((c.name for c in source.classes if c.body_start < offset < c.body_end), '<file>')
        yield el._finding('HC-E043', source, offset, f'{owner}.{name}',
                          f'{name}: {RULES["HC-E043"]} ({ENGINE_RESERVED_METHODS[name]})')


# ---------------------------------------------------------------- HC-E044

def keyword_names(code):
    """[(keyword, offset)] where an Enforce keyword stands in a declared-name position.

    Tokenises cleaned code. A name position is a keyword that follows a type-like token (an
    identifier that is not itself a keyword/modifier, or the closing > of a generic) and is followed
    by one of = ; , ) : [ ( -- covering locals, fields, parameters, foreach slots, method names and
    enum members after a comma. Leading modifiers (static const int X, protected override event
    typename F) never count, because their previous token is itself a keyword.
    """
    tokens = [(m.group(), m.start()) for m in _TOKEN.finditer(code)]
    found = []
    for index in range(1, len(tokens) - 1):
        word, offset = tokens[index]
        if word not in NAME_KEYWORDS:
            continue
        before, after = tokens[index - 1][0], tokens[index + 1][0]
        if after not in _NAME_FOLLOWERS:
            continue
        if before == '>' or (re.fullmatch(r'[A-Za-z_]\w*', before) and before not in NOT_A_TYPE):
            found.append((word, offset))
    return found


def _enum_member_keywords(source):
    found = []
    for block in source.enum_blocks:
        body = source.code[block.body_start + 1:block.body_end]
        for match in re.finditer(r'(?:^|[,{])\s*([A-Za-z_]\w*)\s*(?==|,|$)', body):
            if match[1] in NAME_KEYWORDS:
                found.append((match[1], block.body_start + 1 + match.start(1)))
    return found


def rule_keyword_identifiers(project, source):
    el = _el(project)
    for word, offset in sorted(set(keyword_names(source.code) + _enum_member_keywords(source))):
        yield el._finding('HC-E044', source, offset, word, f'{word}: {RULES["HC-E044"]}')


# ---------------------------------------------------------------- HC-E045

# % joins them: the 2026-11-23 test boot refused `(maxRadius - minRadius) * (attempt % 4) / 3` (Unknown operator '%').
_BITWISE = re.compile(r'<<|>>|(?<![&=!<>])&(?![&=])|(?<![|])\|(?![|=])|\^|%(?!=)')
_FLOAT_LITERAL = re.compile(r'(?<![\w.])(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?f?(?![\w.])|\bMath\.(?:PI|PI2|PI_HALF|DEG2RAD|RAD2DEG)\b')
_CONTROL_PREFIX = re.compile(r'^(?:else\b\s*|(?:if|while|for|foreach|switch)\s*\()')
_ASSIGNMENT = re.compile(r'^(?:(?:const|static|ref|autoptr)\s+)*(?:([A-Za-z_]\w*(?:\s*<.*?>)?)\s+)?'
                         r'([A-Za-z_][\w.\[\]]*)\s*(?:[-+*/]=|=)(?!=)\s*(.+)$', re.S)


def statements(body, start=0):
    """[(text, offset)] simple statements of a method body: split at ; { } outside parentheses."""
    result, depth, begin = [], 0, 0
    for index, ch in enumerate(body):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth = max(0, depth - 1)
        elif depth == 0 and ch in ';{}':
            text = body[begin:index]
            if text.strip():
                result.append((text, start + begin + len(text) - len(text.lstrip())))
            begin = index + 1
    return result


def _strip_control(text):
    """Drop leading else / if (...) / while (...) so an unbraced body statement is judged alone."""
    text = text.strip()
    while True:
        match = _CONTROL_PREFIX.match(text)
        if not match:
            return text
        if match.group().endswith('('):
            close = es.matching_paren(text, match.end() - 1)
            if close >= len(text):
                return ''
            if match.group().startswith(('for', 'foreach')):
                return ''  # loop headers hold ; and are not assignments
            text = text[close + 1:].strip()
        else:
            text = text[match.end():].strip()


def _call_free(expression, scan):
    """Replace every call's parenthesised arguments with a placeholder, scanning each argument alone."""
    out, index = [], 0
    while index < len(expression):
        ch = expression[index]
        if ch == '(' and out and re.search(r'[\w\]]\s*$', ''.join(out)):
            close = es.matching_paren(expression, index)
            inner = expression[index + 1:close]
            for argument in es.split_top(inner, ','):
                scan(argument)
            out.append('()')
            index = close + 1
            continue
        out.append(ch)
        index += 1
    return ''.join(out)


def float_bitwise(expression, float_context=False):
    """Offsets (relative to expression) of bitwise operators inside a float expression.

    A float expression holds a float literal or Math constant, or is assigned to a float. Call
    arguments are separate expressions: ``Math.Max(a & 3, 1)`` is judged per argument. Pure.
    """
    hits = []

    def scan(part, context=False):
        base = expression.find(part) if part in expression else 0
        flat = _call_free(part, lambda argument: scan(argument, False))
        if context or _FLOAT_LITERAL.search(flat):
            for match in _BITWISE.finditer(flat):
                hits.append(base + match.start())

    scan(expression, float_context)
    return sorted(set(hits))


def _float_names(source, method, project):
    names = {name for kind, name, _ in method.parameters() if kind == 'float'}
    names.update(name for name, kind, start, end in source.local_declarations(method) if kind == 'float')
    if method.owner:
        names.update(name for name, kind in project.receiver_members(method.owner.name, source.layer)[1].items()
                     if kind == 'float')
    return names


def rule_float_bitwise(project, source):
    el = _el(project)
    for method in el._all_methods(source):
        floats = None
        body = source.code[method.body_start + 1:method.body_end]
        for text, offset in statements(body, method.body_start + 1):
            statement = _strip_control(text)
            if not statement:
                continue
            context, expression = False, statement
            returned = re.match(r'return\b\s*(.*)$', statement, re.S)
            if returned:
                context, expression = method.return_type == 'float', returned[1]
            else:
                assignment = _ASSIGNMENT.match(statement)
                if assignment:
                    if re.match(r'new\b', assignment[3].strip()):
                        continue
                    if floats is None:
                        floats = _float_names(source, method, project)
                    context = assignment[1] == 'float' or (assignment[1] is None and assignment[2] in floats)
                    expression = assignment[3]
            if not _BITWISE.search(expression):
                continue
            hits = float_bitwise(expression, context)
            if hits:
                shown = re.sub(r'\s+', ' ', statement)[:90]
                yield el._finding('HC-E045', source, offset, el._symbol(method), RULES['HC-E045'], key=shown)


# ---------------------------------------------------------------- HC-E046

_FIELD_READ = re.compile(r'(?<![\w.)\]])\b([A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*)*)\s*\.\s*([A-Za-z_]\w*)\b(?!\s*\()')


def _declared_anywhere(project, kind, member):
    """Whether any authored body in the lineage still declares `member` as a field.

    The shared field parser skips attributed fields (`[NonSerialized()] int X;`) and fields
    with brace initialisers (`ref array<string> X = {...};`). A token scan of the class
    text is deliberately lenient: it can only hide a finding, never invent one.
    """
    pattern = re.compile(r'[\w>\]]\s+' + re.escape(member) + r'\s*(?:=|;|,|\[)')
    for name in project.lineage(kind):
        for definition in project.links.get(name, ()):
            text = definition.source.code[definition.body_start:definition.body_end]
            if pattern.search(text):
                return True
    return False


def rule_receiver_fields(project, source):
    """Field reads on typed receivers, resolved like HC-E012 does for calls (explicit types only)."""
    el = _el(project)
    for method in el._all_methods(source):
        fields = (project.receiver_members(method.owner.name, source.layer)[1] if method.owner else {})
        parameters = {name: kind for kind, name, _ in method.parameters()}
        declarations = source.local_declarations(method)
        for read in _FIELD_READ.finditer(source.body(method)):
            offset = method.body_start + read.start()
            chain = re.split(r'\s*\.\s*', read[1]) + [read[2]]
            first = chain.pop(0)
            if first == 'this' and method.owner:
                kind = method.owner.name
            else:
                bindings = [kind for name, kind, start, end in declarations
                            if name == first and start <= offset < end]
                if bindings:
                    kind = bindings[-1]
                elif first in parameters:
                    kind = parameters[first]
                elif first in fields:
                    kind = fields[first]
                elif first in project.links:
                    kind = first
                else:
                    continue
            for member in chain:
                kind = project.resolve_typedef(kind)
                if kind not in project.types or kind not in project.links or '<' in kind:
                    break
                layers = project.types.get(kind, set()) - {None}
                if layers and source.layer is not None and min(layers) > source.layer:
                    break
                methods, kind_fields, complete = project.receiver_members(kind, source.layer)
                if member in kind_fields:
                    kind = kind_fields[member]
                    continue
                if complete and member not in methods and not _declared_anywhere(project, kind, member):
                    yield el._finding('HC-E046', source, offset, el._symbol(method),
                                      f'{read[0].strip()}: {kind} has no visible field {member} '
                                      '(including parents and modded bodies)',
                                      native=any(n in project.native_names for n in project.lineage(kind)))
                break


# ---------------------------------------------------------------- HC-E047

_LITERAL = re.compile(r'[+-]?\s*(?:0[xX][0-9a-fA-F]+|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)|true|false|"[^"\n]*"')
_CONST_TYPES = frozenset({'int', 'float', 'bool', 'string', 'vector'})
_FILE_CONST = re.compile(r'(?m)^[ \t]*const\s+(int|float|bool|string|vector)\s+(\w+)\s*=\s*([^;{}]*);')


def non_literal(initializer):
    return not _LITERAL.fullmatch(initializer.strip())


def rule_literal_initializers(project, source):
    """HC-E028 owns ``static const`` int/float/bool/string; this rule owns the rest of the shapes.

    Build 169: HC_MAX_STAGES, a cross-class constant expression, read 0 natively and silently
    disabled a guard. The same initialiser order applies to a plain ``const``, a ``vector`` const
    and a static primitive field that reads another class or constant.
    """
    el = _el(project)
    for match in _FILE_CONST.finditer(source.code):
        if non_literal(match[3]):
            yield el._finding('HC-E047', source, match.start(2), '<file>', f'{match[2]}: {RULES["HC-E047"]}',
                              key=f'const {match[1]} {match[2]} = {re.sub(chr(10), " ", match[3]).strip()}')
    for definition in source.classes:
        for item in definition.fields:
            static, const = 'static' in item.modifiers, 'const' in item.modifiers
            if item.type not in _CONST_TYPES or not item.initializer.strip():
                continue
            if static and const and item.type != 'vector':
                continue  # HC-E028
            if not (const or static):
                continue
            if item.type == 'vector' and item.string_initializer and not non_literal(item.string_initializer):
                continue
            initial = item.string_initializer if item.type in {'string', 'vector'} and item.string_initializer else item.initializer
            if non_literal(initial):
                yield el._finding('HC-E047', source, item.offset, f'{definition.name}.{item.name}',
                                  f'{item.name}: {RULES["HC-E047"]}',
                                  key=f'{"static " if static else ""}{"const " if const else ""}{item.type} {item.name} = '
                                      f'{re.sub(r"\s+", " ", initial).strip()}')


# ---------------------------------------------------------------- HC-E042

Decl = namedtuple('Decl', 'name returns modifiers params offset source cls')


def split_parameters(text):
    parts, depth, current = [], 0, []
    for ch in text:
        depth += (ch == '<') - (ch == '>')
        if ch == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(ch)
    parts.append(''.join(current))
    return [part.strip() for part in parts if part.strip()]


def normal_parameters(text):
    """[(type text, is out/inout)]; names, defaults, ref/notnull/const markers dropped."""
    result = []
    for part in split_parameters(text):
        part = part.split('=')[0].strip()
        words = re.findall(r'[A-Za-z_]\w*(?:\s*<[^()]*>)?', part)
        flagged = any(word in {'out', 'inout'} for word in words)
        words = [re.sub(r'\s+', '', w) for w in words if w not in _MODIFIER_WORDS | {'out', 'inout'}]
        if len(words) >= 2:
            words = words[:-1]
        if words:
            result.append((words[0], flagged))
    return tuple(result)


def declarations(source, definition):
    """Every direct method declaration of a class body, prototypes included."""
    result = []
    for signature in source.class_signatures(definition):
        start = source.header_start(signature)
        head = re.sub(r'\[[^\]]*\]', ' ', source.code[start:signature.offset]).split()
        returns = re.sub(r'\s+', '', ' '.join(w for w in head if w not in es.MODIFIERS))
        result.append(Decl(signature.name, returns, signature.modifiers, normal_parameters(signature.params),
                           signature.offset, source, definition.name))
    return result


_NATIVE = {}


def _native_index(root):
    """({class name: [paths]}, {typedef alias: class}, enum names) from raw native text; cheap prescan."""
    key = str(root)
    if key not in _NATIVE:
        classes, aliases, enums = {}, {}, set()
        for layer in es.LAYERS:
            for path in sorted((Path(root) / layer).rglob('*.c')):
                text = path.read_text(encoding='utf-8', errors='replace')
                for match in re.finditer(r'^\s*(?:modded\s+|sealed\s+)*class\s+(\w+)', text, re.M):
                    classes.setdefault(match[1], []).append(path)
                for match in re.finditer(r'^\s*typedef\s+(\w+)\s+(\w+)\s*;', text, re.M):
                    aliases[match[2]] = match[1]
                enums.update(re.findall(r'^\s*enum\s+(\w+)', text, re.M))
        _NATIVE[key] = (classes, aliases, enums, {})
    return _NATIVE[key]


def _native_source(root, path):
    sources = _native_index(root)[3]
    if path not in sources:
        sources[path] = es.Source(path, path.read_text(encoding='utf-8', errors='replace'))
    return sources[path]


class Model:
    """Class bodies in apply order: per script layer originals, then modded bodies; engine before authored."""

    def __init__(self, project, native_root=None):
        self.project = project
        self.root = Path(native_root).expanduser() if native_root and (Path(native_root).expanduser() / '3_Game').is_dir() else None
        self.classes, self.aliases, self.enums = {}, dict(project.typedefs), set(project.enums)
        order = {id(source): index for index, source in enumerate(project.sources)}
        for source in project.sources:
            for definition in source.classes:
                key = (source.layer if source.layer is not None else 9, int(definition.modded), 1, order[id(source)])
                self.classes.setdefault(definition.name, []).append((key, definition, source))
        self.authored = {name for name in self.classes}
        self._load_native()

    def alias(self, name):
        seen = set()
        while name in self.aliases and name not in seen:
            seen.add(name)
            name = self.aliases[name]
        return name

    def _load_native(self):
        if self.root is None:
            return
        index, aliases, enums, _ = _native_index(self.root)
        for alias, target in aliases.items():
            self.aliases.setdefault(alias, target)
        self.enums.update(enums)
        pending, done = [self.alias(n) for n in self.classes], set()
        while pending:
            name = self.alias(pending.pop())
            if name in done:
                continue
            done.add(name)
            for path in index.get(name, ()):
                source = _native_source(self.root, path)
                if any(s.path.resolve() == source.path.resolve() for _, _, s in self.classes.get(name, ())
                       if s in self.project.sources):
                    continue  # the same file is also an authored source (sanity runs over the engine tree)
                for definition in source.classes:
                    if definition.name == name:
                        key = (source.layer if source.layer is not None else 9, int(definition.modded), 0, 0)
                        self.classes.setdefault(name, []).append((key, definition, source))
                        if definition.base:
                            pending.append(definition.base)
            for _, definition, _ in list(self.classes.get(name, ())):
                if definition.base:
                    pending.append(definition.base)

    def complete(self, name):
        """True when every ancestor has a visible body (a Workshop base would make this False)."""
        seen, pending = set(), [self.alias(name)]
        while pending:
            current = self.alias(pending.pop())
            if current in seen:
                continue
            seen.add(current)
            bodies = self.classes.get(current, ())
            if not bodies or all(definition.modded for _, definition, _ in bodies):
                return False
            pending.extend(definition.base for _, definition, _ in bodies if definition.base)
        return True

    def authored_only(self, name):
        """The whole lineage is authored, rooted in no engine class (override of nothing is then certain)."""
        seen, pending = set(), [self.alias(name)]
        while pending:
            current = self.alias(pending.pop())
            if current in seen:
                continue
            seen.add(current)
            bodies = self.classes.get(current, ())
            if (not bodies or any(key[2] == 0 for key, _, _ in bodies)
                    or all(definition.modded for _, definition, _ in bodies)):
                return False
            for _, definition, _ in bodies:
                if definition.base and definition.base not in {'Managed', 'Class'}:
                    pending.append(definition.base)
        return True

    def parent_declarations(self, definition, source):
        """Declarations an override or redefinition in this body can see (earlier same-class bodies, ancestors)."""
        layer = source.layer if source.layer is not None else 9
        own = next((key for key, d, s in self.classes.get(definition.name, ()) if d is definition), None)
        pool, seen, pending = [], set(), []
        for key, other, other_source in self.classes.get(definition.name, ()):
            if other is definition or own is None or key >= own:
                continue
            if other_source is source and other.modded == definition.modded:  # #ifdef alternatives
                continue
            pool.extend(declarations(other_source, other))
            if other.base:
                pending.append(other.base)
        if definition.base:
            pending.append(definition.base)
        while pending:
            name = self.alias(pending.pop())
            if name in seen:
                continue
            seen.add(name)
            for key, other, other_source in self.classes.get(name, ()):
                if key[0] > layer:
                    continue
                pool.extend(declarations(other_source, other))
                if other.base:
                    pending.append(other.base)
        return pool

    def kind(self, text):
        text = self.alias(re.sub(r'\s+', '', text))
        return 'int' if text in self.enums else text

    def same_parameters(self, left, right):
        return (len(left) == len(right)
                and all(a[1] == b[1] and self.kind(a[0]) == self.kind(b[0]) for a, b in zip(left, right)))

    def compatible_parameters(self, left, right):
        """Equal, or both class types: vanilla overrides with a derived class parameter (WeaponFSM)."""
        if len(left) != len(right):
            return False
        for a, b in zip(left, right):
            x, y = self.kind(a[0]), self.kind(b[0])
            if a[1] != b[1]:
                return False
            if x != y and (x in _PRIMITIVES or y in _PRIMITIVES):
                return False
        return True

    def return_conflict(self, ours, parent):
        x, y = self.kind(ours), self.kind(parent)
        if x == y or {x, y} == {'int', 'bool'}:
            return False
        return x in _PRIMITIVES or y in _PRIMITIVES


def model(project):
    if getattr(project, '_syntax_model', None) is None:
        project._syntax_model = Model(project, NATIVE_ROOT)
    return project._syntax_model


def _show(declaration):
    parameters = ', '.join(('out ' if flag else '') + kind for kind, flag in declaration.params)
    return f'{declaration.returns} {declaration.name}({parameters})'


def rule_parent_signatures(project, source):
    el = _el(project)
    shared = model(project)
    for definition in source.classes:
        mine = declarations(source, definition)
        if not mine:
            continue
        pool = shared.parent_declarations(definition, source)
        names = {d.name for d in pool}
        for declaration in mine:
            name = declaration.name
            if name == definition.name or name.startswith('~'):
                continue
            symbol = f'{definition.name}.{name}'
            overriding = 'override' in declaration.modifiers
            candidates = [d for d in pool if d.name == name] if name in names else []
            exact = [d for d in candidates if shared.same_parameters(declaration.params, d.params)]
            if not overriding:
                if exact:
                    yield el._finding('HC-E042', source, declaration.offset, symbol,
                                      f'{_show(declaration)} redefines {exact[0].cls}.{name} without override '
                                      '(native compile: redefinition needs the override keyword)',
                                      key=f'no override: {_show(declaration)}')
                continue
            if candidates:
                compatible = [d for d in candidates if shared.compatible_parameters(declaration.params, d.params)]
                if not compatible:
                    yield el._finding('HC-E042', source, declaration.offset, symbol,
                                      f'override {_show(declaration)} matches none of the parent signatures: '
                                      + '; '.join(sorted({_show(d) for d in candidates})),
                                      key=f'signature: {_show(declaration)}')
                    continue
                parent = next((d for d in compatible if shared.same_parameters(declaration.params, d.params)), compatible[0])
                if ('static' in declaration.modifiers) != ('static' in parent.modifiers):
                    yield el._finding('HC-E042', source, declaration.offset, symbol,
                                      f'override {_show(declaration)} differs from {parent.cls}.{name} in static',
                                      key=f'static: {_show(declaration)}')
                elif shared.return_conflict(declaration.returns, parent.returns):
                    yield el._finding('HC-E042', source, declaration.offset, symbol,
                                      f'override {_show(declaration)} returns a different type than '
                                      f'{parent.cls}.{_show(parent)}',
                                      key=f'return: {_show(declaration)}')
            elif shared.authored_only(definition.name):
                yield el._finding('HC-E042', source, declaration.offset, symbol,
                                  f'override {_show(declaration)} has no parent method in any authored ancestor',
                                  key=f'no parent: {_show(declaration)}')


def rules_for(lint):
    """The rule callables bound to the enforce_lint module that imports this one."""
    def bind(rule):
        def bound(project, source):
            project._syntax_bound = lint
            return rule(project, source)
        bound.__name__ = rule.__name__
        bound.__doc__ = rule.__doc__
        return bound
    return tuple(bind(rule) for rule in (
        rule_parent_signatures, rule_reserved_method_names, rule_keyword_identifiers,
        rule_float_bitwise, rule_receiver_fields, rule_literal_initializers))
