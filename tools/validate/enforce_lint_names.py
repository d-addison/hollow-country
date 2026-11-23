"""Unqualified names that resolve to nothing (HC-E050).

Registered from tools.validate.enforce_lint (``rules_for``); no command line of its own. The native
compile gate of 2026-11-22 failed with "Can't find variable 'Actor'" in two subclasses of
HCXTradeInventoryScan after commit 917bb075 renamed the field Actor to ActorHold: HC-E012 resolves
receivers of method calls and HC-E046 resolves ``a.b`` field reads, but neither looks at a bare name.

  HC-E050  an identifier read inside a method body that is not a local or parameter, not a member
           (field, constant, method) of the class or any ancestor (modded bodies merge into their
           base), not a class, enum, typedef, global function or global constant (authored or
           native), and not an Enforce keyword or builtin

Precision over recall. The rule is silent for
  * a class with any ancestor whose body is not visible (a packed Workshop parent, an engine class
    missing from the names index), exactly as HC-E042 and HC-E046 skip those;
  * a name followed by ``(`` (a call is HC-E012's business) or by ``.`` (it may be a packed Workshop
    class; an authored receiver is HC-E046's business);
  * a name in a type position (after ``new``, inside ``<...>``, before another name);
  * any name a local scan can find declared anywhere in the method (flat function scope).
Nothing here proves DayZ behaviour; only a native compile does.
"""
from pathlib import Path
import re

from tools.validate import enforce_source as es

RULES = {
    'HC-E050': 'bare name resolves to no local, parameter, member of the class or its ancestors, global, class, enum '
               'or constant (native compile: Can\'t find variable; a renamed or removed field read by a subclass)',
}

# Enforce keywords and builtins that may stand alone in an expression. Primitive type names are listed
# because ``int.MAX`` style reads and template arguments carry them.
BUILTINS = frozenset({
    'this', 'super', 'null', 'NULL', 'true', 'false', 'int', 'float', 'bool', 'string', 'vector', 'void',
    'typename', 'func', 'auto', 'Class', 'Managed', 'array', 'map', 'set', 'ref', 'autoptr', 'notnull',
    'const', 'static', 'private', 'protected', 'owned', 'out', 'inout', 'local', 'proto', 'native',
    'volatile', 'reference', 'external', 'override', 'sealed', 'modded', 'class', 'extends', 'enum',
    'typedef', 'new', 'delete', 'return', 'if', 'else', 'while', 'for', 'foreach', 'switch', 'case',
    'default', 'break', 'continue', 'thread', 'event', 'in', 'param', 'throw', 'goto'})

# Words that can precede a name without declaring it.
_NOT_A_TYPE = frozenset({'return', 'case', 'new', 'delete', 'else', 'throw', 'in', 'goto', 'default'})

# Engine builtins no script declares (EnConvert.c reads FLT_MAX, CrossHairSelector.c reads ObjIntersectFire,
# MapMenu.c reads UAMapToggle, Game.c documents CT_INT): input actions and the raycast layers.
_ENGINE_FAMILY = re.compile(r'^(?:ObjIntersect[A-Z]\w*|UA[A-Z]\w*)$')
# UPPER_SNAKE constants: engine (CT_INT, DT_CUSTOM, FLT_MAX) or a Workshop pack (EXPANSION_LOADOUT_FOLDER).
# One is judged only when an authored constant shares its prefix (a removed HC_ constant is still found).
_CONSTANT = re.compile(r'^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$')

_IDENT = re.compile(r'(?<![\w.$])([A-Za-z_]\w*)')
_DECLARED = re.compile(r'(?<![\w.])([A-Za-z_]\w*)(?:\s*<[^;(){}=]*>)?(?:\s*\[\s*\])?\s+([A-Za-z_]\w*)'
                       r'\s*(?==(?!=)|;|,|\[|:|\))')
_CHAINED = re.compile(r',\s*([A-Za-z_]\w*)\s*(?==(?!=)|;)')
_ENUM_BODY = re.compile(r'\benum\s+[A-Za-z_]\w*\s*(?::\s*\w+\s*)?\{([^}]*)\}')
# Declared names at column 0 of a file: functions, variables and constants of the global scope.
_GLOBAL_FUNCTION = re.compile(r'^[A-Za-z_][^()=;{}\n]*?\b([A-Za-z_]\w*)\s*\(', re.M)
_GLOBAL_VARIABLE = re.compile(r'^(?!(?:class|enum|typedef|modded|sealed)\b)[A-Za-z_][^()=;{}\n]*?\b([A-Za-z_]\w*)\s*(?:=|;|\[)', re.M)
_NATIVE = {}


def _blank_comments(text):
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    return re.sub(r'//[^\n]*', ' ', text)


def enum_members(code):
    """Member names of every enum body in cleaned code (comments already blanked)."""
    names = set()
    for body in _ENUM_BODY.findall(code):
        for part in body.split(','):
            member = re.match(r'\s*([A-Za-z_]\w*)', part)
            if member:
                names.add(member[1])
    return names


def global_names(code):
    """Names declared at column 0 (functions, variables, constants) and enum members of one file."""
    names = enum_members(code)
    names.update(_GLOBAL_FUNCTION.findall(code))
    names.update(_GLOBAL_VARIABLE.findall(code))
    return names


def _native_globals(root):
    key = str(root)
    if key not in _NATIVE:
        names = set()
        for layer in es.LAYERS:
            for path in sorted((Path(root) / layer).rglob('*.c')):
                code = _blank_comments(path.read_text(encoding='utf-8', errors='replace'))
                names.update(global_names(code))
        _NATIVE[key] = frozenset(names)
    return _NATIVE[key]


def _class_level_names(code, start, stop):
    """Names declared directly in a class body: fields, constants, methods, attributed and brace-initialised
    fields included (the shared field parser skips those two shapes)."""
    names, seg, pos = set(), start + 1, start + 1
    while pos < stop:
        ch = code[pos]
        if ch == ';':
            names.update(_statement_names(code[seg:pos]))
            seg = pos + 1
        elif ch == '{':
            end = es.matching_brace(code, pos)
            header = code[seg:pos]
            if header.rstrip().endswith(('=', ',')):
                pos = end   # brace initialiser: the statement goes on to its ';'
            else:
                names.update(_statement_names(header))
                pos = end
                seg = end + 1
        pos += 1
    return names


def _statement_names(text):
    text = text.strip()
    while text.startswith('['):   # attributes: [NonSerialized()] ...
        depth, index = 0, 0
        for index, ch in enumerate(text):
            depth += (ch == '[') - (ch == ']')
            if depth == 0:
                break
        text = text[index + 1:].strip()
    equals = re.search(r'(?<![=!<>])=(?!=)', text)
    paren = text.find('(')
    if paren >= 0 and (not equals or paren < equals.start()):
        name = re.search(r'([A-Za-z_]\w*)\s*$', text[:paren])
        return {name[1]} if name else set()
    names, depth, current = set(), 0, []
    parts = []
    for ch in text:
        if ch in '<([{':
            depth += 1
        elif ch in '>)]}':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(ch)
    parts.append(''.join(current))
    for index, part in enumerate(parts):
        part = re.split(r'(?<![=!<>])=(?!=)', part)[0]
        part = re.sub(r'\[[^\]]*\]\s*$', '', part).strip()
        found = re.findall(r'[A-Za-z_]\w*', part)
        if found and (index > 0 or len(found) > 1):
            names.add(found[-1] if index == 0 else found[0])
    return names


def _previous(body, index):
    index -= 1
    while index >= 0 and body[index].isspace():
        index -= 1
    return body[index] if index >= 0 else ''


def _following(body, index):
    while index < len(body) and body[index].isspace():
        index += 1
    return body[index] if index < len(body) else ''


def _word_before(body, index):
    return re.search(r'([A-Za-z_]\w*)\s*$', body[max(0, index - 40):index])


def _in_angle(body, index):
    """Whether the name sits inside an unclosed ``<`` of its own statement (a template argument)."""
    depth = 0
    for position in range(index - 1, -1, -1):
        ch = body[position]
        if ch in ';{}':
            return False
        if ch == '>':
            depth += 1
        elif ch == '<':
            depth -= 1
            if depth < 0:
                return True
    return False


class Names:
    """Per-project caches: global names, and the member names of a class lineage."""

    def __init__(self, project, native_root):
        self.project = project
        self.universe = set(BUILTINS) | set(project.native_globals)
        self.universe.update(project.visible_types(None))
        self.universe.update(project.typedefs)
        authored = set()
        for source in project.sources:
            authored.update(c.name for c in source.classes)
            authored.update(m.name for m in source.functions)
            authored.update(source.enums)
            authored.update(global_names(source.code))
        self.universe.update(authored)
        if native_root is not None:
            self.universe.update(_native_globals(native_root))
        self.constant_prefixes = {f.name.split('_')[0] for source in project.sources for c in source.classes
                                  for f in c.fields if _CONSTANT.match(f.name)}
        self.constant_prefixes.update(n.split('_')[0] for n in authored if _CONSTANT.match(n))
        self._members = {}

    def engine_or_pack(self, name):
        """A builtin or a Workshop constant that no visible script declares."""
        if _ENGINE_FAMILY.match(name):
            return True
        return bool(_CONSTANT.match(name)) and name.split('_')[0] not in self.constant_prefixes

    def members(self, kind):
        """(member names, complete) of a class and every ancestor; modded bodies merge into their base."""
        if kind not in self._members:
            methods, fields, complete = self.project.receiver_members(kind, None)
            names = set(methods) | set(fields)
            for name in self.project.lineage(kind):
                for definition in self.project.links.get(name, ()):
                    names.update(_class_level_names(definition.source.code, definition.body_start,
                                                    definition.body_end))
            self._members[kind] = (names, complete)
        return self._members[kind]


def _names(project, native_root):
    if not hasattr(project, '_names_cache'):
        project._names_cache = Names(project, native_root)
    return project._names_cache


def make_rule(lint, syntax):
    """The rule callable bound to the enforce_lint module that imports this one."""
    def rule_unresolved_names(project, source):
        names = _names(project, syntax.NATIVE_ROOT)
        for method in lint._all_methods(source):
            if method.owner is not None:
                members, complete = names.members(method.owner.name)
                if not complete:
                    continue
            else:
                members = set()
            body = source.body(method)
            known = {name for _, name, _ in method.parameters()}
            known.update(name for name, _, _, _ in source.local_declarations(method))
            known.update(m[2] for m in _DECLARED.finditer(body) if m[1] not in _NOT_A_TYPE)
            known.update(_CHAINED.findall(body))
            reported = set()
            for read in _IDENT.finditer(body):
                name = read[1]
                if name in known or name in members or name in names.universe or name.startswith('__') or names.engine_or_pack(name):
                    continue
                before, after = _previous(body, read.start()), _following(body, read.end())
                if before == '.' or after in '(.<>':
                    continue
                word = _word_before(body, read.start())
                if (word and word[1] == 'new') or _in_angle(body, read.start()):
                    continue
                if re.match(r'\s*[A-Za-z_]', body[read.end():read.end() + 40]):
                    continue   # a type position: ``Name other``
                offset = method.body_start + read.start()
                line = source.line_of(offset)
                if (line, name) in reported:
                    continue
                reported.add((line, name))
                owner = method.owner.name if method.owner is not None else 'a file function'
                yield lint._finding('HC-E050', source, offset, lint._symbol(method),
                                    f'{name}: resolves to no local, parameter, member of {owner} or its ancestors, '
                                    'global or constant (a field renamed or removed in a parent?)',
                                    native=False)
    return rule_unresolved_names
