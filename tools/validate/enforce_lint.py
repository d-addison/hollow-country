"""Project-wide static lint for Enforce Script traps and silent server refusals.

Run ``python3 -B -m tools.validate.enforce_lint`` from the repository root.
Standard library only, offline, deterministic (sorted inputs, no clocks in
results). It reads authored sources under mods/*/scripts and, when present,
the local extracted engine script cache (``--native-scripts`` or the
HC_NATIVE_SCRIPTS environment variable; never committed). ``--no-native``
forces the pinned-only mode the unit tests use.

Every rule maps to a trap a native compile/boot or a real client actually hit
(see audit/CHECKS.md). Findings already present when the lint landed are listed
in tools/validate/enforce_lint_baseline.json (and HC-S005 module legacy entries)
with a review note; the check fails
on any finding not in the baseline and on baseline entries that no longer
occur (fixed code must shrink the baseline). A pass is not DayZ evidence.
"""
import argparse
from collections import Counter
from dataclasses import dataclass, asdict
import json
import os
from pathlib import Path
import re
import sys

from tools.setup.probe_runtime import ENGINE_TYPE_NAMES, RESERVED_WORDS
from tools.validate import enforce_source as es
from tools.validate import enforce_json
from tools.validate import enforce_rules_readiness as _readiness
from tools.validate import native_symbols

ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).with_name('enforce_lint_baseline.json')
STORAGE_ALLOWLIST = Path(__file__).with_name('enforce_lint_storage_allowlist.json')
WORKSHOP_ROOT = Path('/mnt/e/HollowCountryLocal/friend-local-1')
DEFAULT_CACHE = Path('~/.cache/hollow-country/native-scripts/scripts-1.30.164289')
# Vanilla 1.30.164289 4_World/Entities/GardenBase/Slot.c declares class Slot(float); an authored
# method named Slot made an unqualified call resolve to that class (native boot 026, commit acab865).
PINNED_TYPES = frozenset(ENGINE_TYPE_NAMES) | {'Slot', 'PlayerBase', 'DayZPlayer', 'ActionBase', 'House'}
# Where a pinned name lives, so the layer rule can work without the native cache.
PINNED_LAYERS = {'Slot': 3, 'PlayerBase': 3, 'ActionBase': 3, 'ItemBase': 3, 'EntityAI': 2, 'DayZPlayer': 2}

RULES = {
    'HC-E001': 'ternary operator (the native compiler rejects ?:)',
    'HC-E002': 'type used in a lower script layer than the one that defines it (3_Game cannot see 4_World)',
    'HC-E003': 'new assigned to a member that is not a strong ref (object is released at once)',
    'HC-E004': 'new inserted into a collection whose element type is not ref',
    'HC-E005': 'modded link calls a method that only another modded link of the class declares',
    'HC-E006': 'Substring on a receiver whose Length() the method never consults (Wrong parameter value)',
    'HC-E007': 'method named like a visible type (unqualified calls resolve to the type)',
    'HC-E008': 'unbalanced method attribute (the source model cannot inspect the declaration)',
    'HC-E010': 'integer assigned to a FileHandle (native compile: Incompatible parameter); track open state in a bool',
    'HC-E011': 'Enforce keyword used as a variable, member or parameter name (native compile: Expected name, not a keyword)',
    'HC-E012': 'method absent from the declared receiver type and its visible ancestors/modded bodies',
    'HC-E013': 'type only defined in a higher script layer than its use',
    'HC-E014': 'modded class declared outside the script module of its original class',
    'HC-E015': 'unsupported map key or set element type (use int/string/typename/class types)',
    'HC-E016': 'FileHandle/FindFileHandle compared with null (use truthiness)',
    'HC-E017': 'vanilla storage override without an explicit migration-plan allowlist entry',
    'HC-L001': 'Print of a bare variable (the engine logs "string name = \'...\'" instead of the text)',
    'HC-S001': 'server commit point returns early without logging or telling the player why',
    'HC-S002': 'server gate returns false without a reason code, log line or player message',
    'HC-S003': 'client-predicted action whose server path never sends the player a refusal message',
    'HC-S004': 'literal engine/build version comparison without a Print or log in the same method',
    enforce_json.RULE: enforce_json.DESCRIPTION,
}
RULES.update(_readiness.RULES)  # HC-S006 module names, HC-E009 engine-type variable names

_KEYWORDS = frozenset({'if', 'while', 'for', 'foreach', 'switch', 'return', 'new', 'delete', 'case',
                       'else', 'sizeof', 'typename', 'super', 'this', 'thread', 'string', 'int', 'float',
                       'bool', 'vector', 'array', 'map', 'set', 'Cast', 'CastTo'}) | RESERVED_WORDS
_CALL = re.compile(r'(?<![\w.])((?:super|this)\s*\.\s*)?([A-Za-z_]\w*)\s*\(')
_ANY_CALL = re.compile(r'(?<![\w])([A-Za-z_]\w*)\s*\(')
_LOCAL = re.compile(r'(?<![\w.])([A-Za-z_]\w*(?:<[^;(){}=]*>)?)\s+([A-Za-z_]\w*)\s*(?=[=;\[,)])')
_EMITTER = re.compile(
    r'\b(?:Print|PrintFormat|PrintToRPT|Error|ErrorEx|DPrint|MessageStatus|MessageImportant|MessageAction'
    r'|SendMessage\w*|\w*Log|Log\w*|\w*Refus\w*|\w*Report\w*|\w*Notify\w*|\w*Warn\w*|\w*Diagnos\w*'
    r'|\w*Reject\w*|\w*Explain\w*)\s*\(|\b\w*[Rr]eason\w*\s*=(?!=)')
_PLAYER_MESSAGE = re.compile(r'\b(?:MessageStatus|MessageImportant|MessageAction|\w*RefusalMessage\w*|HCRefusal\w*)\s*\(')
# Guard terms that are not refusals: machine role, re-entry/single-instance, operator preference
# (core HCServer only starts modules whose IsEnabled is true) and a reason already computed in scope.
_ROLE_GUARD = re.compile(r'^!?\s*(?:GetGame\s*\(\s*\)|g_Game|(?:[\w.]+\.)?(?:HC)?Is(?:Server|Client|DedicatedServer|Multiplayer)'
                         r'\s*\(\s*\))(?:\s*\.\s*(?:IsServer|IsClient|IsDedicatedServer|IsMultiplayer)\s*\(\s*\))?$')
_REENTRY_GUARD = re.compile(r'^!?\s*(?:m_|s_)?\w*(?:Started|Running|Listening|Instance|Starting)$'
                            r'|^(\w*Instance)\s*&&\s*\1\s*!=\s*this$|^!\s*IsEnabled\s*\(\s*\w+\s*\)$'
                            # Positive-only bare member: "already printed / already finished" (never the inverse).
                            r'|^(?:m_|s_)\w*(?:Printed|Finished)$')
_REASON_IN_SCOPE = re.compile(r'\b\w*(?:[Rr]eason|Problem)\w*\b')
# Native experiment / audit / probe harnesses report through their own receipts; the S rules
# target gameplay and admission paths.
_HARNESS = re.compile(r'(?:NativeChecks|SelfTest|Diagnostic|Probe|Audit|Experiment|Census|Sampler)')
COMMIT_VOID = re.compile(r'^(?:Begin|Start|Commit|Execute|Apply|Grant|Claim|Spawn|Perform|Accept)\w*$'
                         r'|^On(?:Start|Execute|FinishProgress|Complete)\w*Server$|^OnStart$')
GATE_BOOL = re.compile(r'^(?:Gate\w*|\w+Gate|CanStart|CanBegin|CanContinue|CanExecute|CanCommit|Admit\w*'
                       r'|Ensure\w*|Begin\w*|Start\w*|Commit\w*|Grant\w*|Claim\w*)$')
_ACTION_BASE = re.compile(r'^Action\w*Base$')
_PREDICTION = re.compile(r'\b(?:IsServer|IsClient|IsDedicatedServer|IsMultiplayer)\s*\(')


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int
    symbol: str
    key: str
    message: str
    native: bool = False

    def identity(self):
        return (self.rule, self.path, self.symbol, self.key)

    def render(self):
        return f'{self.path}:{self.line}: {self.rule} {self.symbol}: {self.message}'


class Project:
    """Cross-file indexes over authored sources (and optional native type names)."""

    def __init__(self, sources, native=None, symbols=None, provider_layers=None):
        self.sources = sources
        self.native = native or {}
        self.symbols = (symbols or {}).get('classes', {})
        self._receiver_cache = {}
        self.provider_layers = provider_layers or {}
        self.storage_allowlist = load_storage_allowlist()
        self.links, self.types, self.enums, self.typedefs = {}, {}, set(), {}
        for source in sources:
            for definition in source.classes:
                self.links.setdefault(definition.name, []).append(definition)
                if not definition.modded:
                    self.types.setdefault(definition.name, set()).add(source.layer)
            for name in source.enums:
                self.enums.add(name)
                self.types.setdefault(name, set()).add(source.layer)
            for name, target in source.typedefs.items():
                self.typedefs[name] = target
                self.types.setdefault(name, set()).add(source.layer)
        self.native_names = set().union(*self.native.values()) if self.native else set()
        self.methods = {}
        for definitions in self.links.values():
            for definition in definitions:
                for method in definition.methods:
                    self.methods.setdefault(method.name, []).append(method)

    def declaring_layers(self, name, source):
        """Original bodies only; a modded link never declares a new type.

        Prefer this addon's own declarations, then dependencies. Layers are
        zero-based es.LAYERS indexes, never inferred from the caller's module.
        """
        bodies = [d for d in self.links.get(name, ()) if not d.modded]
        own = [d for d in bodies if _mod_name(d.source) == _mod_name(source)]
        if own:
            return {d.source.layer for d in own} - {None}
        if bodies:
            return {d.source.layer for d in bodies} - {None}
        engine = {d['layer'] for d in self.symbols.get(name, ()) if not d['modded']}
        if engine:
            return engine
        # Name-only indexes and the small pinned census support offline callers.
        engine = {layer for layer, names in self.native.items() if name in names}
        if engine:
            return engine
        if name in PINNED_LAYERS:
            return {PINNED_LAYERS[name]}
        return self.provider_layers.get(name, set())

    def base_of(self, name):
        for definition in self.links.get(name, ()):
            if not definition.modded and definition.base:
                return definition.base
        return ''

    def lineage(self, name):
        """The class and its authored ancestors (cycle-safe)."""
        chain, seen = [], set()
        while name and name not in seen:
            seen.add(name)
            chain.append(name)
            name = self.base_of(name)
        return chain

    def is_enum(self, name):
        return name in self.enums

    def class_type(self, type_text):
        base = re.sub(r'<.*$', '', type_text.strip())
        return bool(base) and base not in es.PRIMITIVES and not self.is_enum(base)

    def resolve_typedef(self, type_text):
        seen = set()
        while type_text in self.typedefs and type_text not in seen:
            seen.add(type_text)
            type_text = re.sub(r'\s+', '', self.typedefs[type_text])
        return type_text

    def receiver_members(self, name, layer):
        """(method names, field types, complete) at the caller's script layer.

        Unknown engine parents leave resolution incomplete, so offline mode
        never guesses that their methods are absent. Both authored and native
        classes include their visible authored modded bodies.
        """
        key = (name, layer)
        if key in self._receiver_cache:
            return self._receiver_cache[key]
        methods, fields, seen, complete = set(), {}, set(), True

        def visit(kind):
            nonlocal complete
            if kind in seen:
                return
            seen.add(kind)
            bodies = [d for d in self.links.get(kind, ())
                      if layer is None or d.source.layer is None or d.source.layer <= layer]
            engine = [d for d in self.symbols.get(kind, ())
                      if layer is None or d['layer'] <= layer]
            ordinary = [d for d in bodies if not d.modded]
            native_ordinary = [d for d in engine if not d['modded']]
            if not ordinary and not native_ordinary:
                complete = False
            parents = [d.base for d in bodies if d.base]
            parents += [d['parent'] for d in engine if d['parent']]
            for parent in parents:
                visit(parent)
            for body in engine:
                methods.update(body['methods'])
                fields.update(body['fields'])
            for body in bodies:
                methods.update(s.name for s in body.source.class_signatures(body))
                fields.update({f.name: f.type for f in body.fields})

        visit(name)
        # Every Enforce class implicitly inherits Class; these intrinsic
        # methods are also legal in --no-native mode (pinned EnScript.c).
        methods.update({'Cast', 'CastTo', 'IsInherited', 'ClassName', 'Type', 'StaticType', 'ToString'})
        if name != 'Class' and self.symbols:
            visit('Class')
        result = methods, fields, complete
        self._receiver_cache[key] = result
        return result


def _finding(rule, source, offset, symbol, message, native=False, key=None):
    text = key if key is not None else re.sub(r'\s+', ' ', source.line_text(offset))
    return Finding(rule, source.rel, source.line_of(offset), symbol, text, message, native)


def _symbol(method):
    owner = method.owner.name if method.owner is not None else '<file>'
    return f'{owner}.{method.name}'


def _all_methods(source):
    for definition in source.classes:
        for method in definition.methods:
            yield method
    yield from source.functions


def _locals(body):
    names = {}
    for match in _LOCAL.finditer(body):
        kind = match.group(1)
        if kind.split('<')[0] in _KEYWORDS - es.PRIMITIVES - {'array', 'map', 'set'}:
            continue
        names[match.group(2)] = re.sub(r'\s+', '', kind)
    return names


# ---------------------------------------------------------------- compile traps

def rule_parse_issues(project, source):
    # Also inspect bodyless declarations; signature reads keep diagnostics unique.
    _ = source.signatures
    for issue in source.parse_issues:
        yield _finding('HC-E008', source, issue.offset, '<parse>', issue.message)


def rule_ternary(project, source):
    for match in re.finditer(r'\?', source.code):
        yield _finding('HC-E001', source, match.start(), '<file>', RULES['HC-E001'])


def rule_file_handle_int(project, source):
    # Native boot 074: FileHandle is typedef int[]; comparing with 0 compiles, assigning 0 does not.
    names = set(re.findall(r'\bFileHandle\s+(\w+)', source.code))
    for name in sorted(names):
        for match in re.finditer(r'(?<![\w.])' + name + r'\s*=\s*\d+\s*;', source.code):
            yield _finding('HC-E010', source, match.start(), name, RULES['HC-E010'])


# Native boot 075: hcxaibaseraid.c,270 "Expected name, not a keyword 'local'"; compile-xai4-01 refused `owned`.
# Native boot 098: hcinteriortemplatesstrict.c,464 `string native = ""` -> "Broken expression".
_NAME_KEYWORDS = ('owned', 'out', 'inout', 'notnull', 'autoptr', 'reference', 'volatile', 'external', 'event',
                  'thread', 'sealed', 'local', 'native', 'proto', 'private', 'protected', 'static', 'const',
                  'override', 'modded')
_NAME_KEYWORD_DECL = re.compile(r'\b([A-Za-z_][A-Za-z0-9_<>]*)\s+(%s)\s*(?==|;|,|\))' % '|'.join(_NAME_KEYWORDS))


def _mod_name(source):
    if source.mod:
        return source.mod
    parts = source.path.parts
    if 'mods' in parts and parts.index('mods') + 1 < len(parts):
        return parts[parts.index('mods') + 1]
    return ''


def load_storage_allowlist(path=STORAGE_ALLOWLIST):
    """An exception must name the exact file, vanilla class, hook and migration.

    Invalid entries fail closed, rather than accidentally granting a broad waiver.
    """
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema') != 1 or not isinstance(data.get('entries'), list):
        raise ValueError('invalid storage migration allowlist')
    entries = set()
    for entry in data['entries']:
        if (not all(isinstance(entry.get(k), str) and entry[k].strip()
                    for k in ('path', 'class', 'method', 'migration_plan'))
                or entry['method'] not in {'OnStoreSave', 'OnStoreLoad'}):
            raise ValueError('storage exception requires path, class, method and migration_plan')
        entries.add((entry['path'], entry['class'], entry['method']))
    return entries


def workshop_class_layers(names, root=WORKSHOP_ROOT):
    """Read available provider .c declarations only, never unpack or copy mods.

    Packed-only/unreadable installs leave unknown bases unresolved. Do not read
    installed HC copies: authored HC declarations are authoritative for this run.
    """
    result = {}
    if not names:
        return result
    layers = {name.lower(): i for i, name in enumerate(es.LAYERS)}
    for addon in sorted(Path(root).glob('@*')):
        if addon.name.lower() in {'@hollowcountry', '@hollowcountryexpansionai'}:
            continue
        for path in sorted(addon.rglob('*.c')):
            layer = next((layers[p.lower()] for p in path.parts if p.lower() in layers), None)
            if layer is None:
                continue
            try:
                code = es.clean(path.read_text(encoding='utf-8', errors='replace'))
            except OSError:
                continue
            for match in re.finditer(r'\b(modded\s+)?(?:sealed\s+)?class\s+([A-Za-z_]\w*)', code):
                if not match[1] and match[2] in names:
                    result.setdefault(match[2], set()).add(layer)
    return result


def rule_modded_module(project, source):
    if source.layer is None:
        return
    for definition in source.classes:
        if not definition.modded:
            continue
        layers = project.declaring_layers(definition.name, source)
        if layers and source.layer not in layers:
            declared = ', '.join(es.LAYERS[i] for i in sorted(layers))
            yield _finding('HC-E014', source, definition.offset, definition.name,
                           f'modded class is in {es.LAYERS[source.layer]}; original class is in {declared}')


def rule_collection_keys(project, source):
    # Match every instantiation, including nested generics and return types.
    for match in re.finditer(r'\b(map|set)\s*<\s*((?:(?:ref|autoptr)\s+)?[A-Za-z_]\w*)', source.code):
        kind = re.sub(r'^(?:ref|autoptr)\s+', '', match[2])
        kind = project.resolve_typedef(kind)
        if kind in {'int', 'string', 'typename', 'Class', 'class'}:
            continue
        # Enums are integer keys. Unknown identifiers may be template type
        # parameters/provider classes; do not guess they are primitive keys.
        if project.is_enum(kind):
            continue
        if kind in es.PRIMITIVES or kind.startswith(('array<', 'map<', 'set<')) or kind.endswith('[]'):
            yield _finding('HC-E015', source, match.start(), '<file>',
                           f'{match[1]}<{match[2]}>: {RULES["HC-E015"]}')


_NULL_HANDLE = re.compile(
    r'(?<![\w.])(?:(?P<left>[A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*)*)\s*(?:==|!=)\s*null\b'
    r'|null\s*(?:==|!=)\s*(?P<right>[A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*)*))')


def rule_handle_null(project, source):
    methods = list(_all_methods(source))
    # File-scope variables remain visible in functions and member initializers.
    globals_ = {m[2]: m[1] for m in _LOCAL.finditer(source.code)
                if not any(d.body_start < m.start() < d.body_end for d in source.classes)
                and not any(f.offset <= m.start() < f.body_end for f in source.functions)}
    for match in _NULL_HANDLE.finditer(source.code):
        offset = match.start()
        method = next((m for m in methods if m.body_start < offset < m.body_end), None)
        owner = (method.owner if method else
                 next((d for d in source.classes if d.body_start < offset < d.body_end), None))
        fields = project.receiver_members(owner.name, source.layer)[1] if owner else {}
        parameters = {name: kind for kind, name, _ in method.parameters()} if method else {}
        declarations = source.local_declarations(method) if method else []
        parts = re.split(r'\s*\.\s*', match['left'] or match['right'])
        first = parts.pop(0)
        bindings = [kind for name, kind, start, end in declarations
                    if name == first and start <= offset < end]
        if first == 'this' and owner:
            kind = owner.name
        elif bindings:
            kind = bindings[-1]
        else:
            kind = parameters.get(first, fields.get(first, globals_.get(first, '')))
        for member in parts:
            kind = project.receiver_members(project.resolve_typedef(kind), source.layer)[1].get(member, '')
        # Preserve handle names before typedef expansion to int[]. Follow
        # authored aliases without treating all int arrays as file handles.
        seen = set()
        while kind in project.typedefs and kind not in seen and kind not in {'FileHandle', 'FindFileHandle'}:
            seen.add(kind)
            kind = project.typedefs[kind].strip()
        if kind in {'FileHandle', 'FindFileHandle'}:
            symbol = _symbol(method) if method else (owner.name if owner else '<file>')
            yield _finding('HC-E016', source, offset, symbol,
                           f'{match[0].strip()}: {RULES["HC-E016"]}')


def rule_vanilla_storage(project, source):
    for definition in source.classes:
        if not definition.modded:
            continue
        # Authored original classes own their storage layout. Modding a vanilla
        # subclass is covered because its original is in the native census.
        if any(not d.modded for d in project.links.get(definition.name, ())):
            continue
        if definition.name not in project.native_names | PINNED_TYPES | set(PINNED_LAYERS) | set(project.symbols):
            continue
        for method in definition.methods:
            if method.name not in {'OnStoreSave', 'OnStoreLoad'}:
                continue
            if (source.rel, definition.name, method.name) in project.storage_allowlist:
                continue
            yield _finding('HC-E017', source, method.offset, _symbol(method), RULES['HC-E017'])


def rule_keyword_names(project, source):
    for match in _NAME_KEYWORD_DECL.finditer(source.code):
        if match.group(1) in ('ref', 'out', 'inout', 'notnull', 'autoptr', 'return', 'new', 'delete', 'typename'):
            continue
        yield _finding('HC-E011', source, match.start(2), match.group(2), RULES['HC-E011'])


def rule_layers(project, source):
    if source.layer is None:
        return
    reported = set()
    own_members = {m.name for m in _all_methods(source)} | {f.name for d in source.classes for f in d.fields}
    for match in re.finditer(r'(?<![\w.])([A-Z]\w*)\b', source.code):
        name = match.group(1)
        if name in reported or name in own_members:
            continue
        authored = project.types.get(name, set())
        native_layers = {layer for layer, names in project.native.items() if name in names}
        if not project.native and name in PINNED_LAYERS:
            native_layers = {PINNED_LAYERS[name]}
        layers = authored | native_layers
        if layers and min(layers) > source.layer:
            reported.add(name)
            defined = es.LAYERS[min(layers)]
            yield _finding('HC-E002', source, match.start(), name,
                           f'{name} is defined in {defined}; {es.LAYERS[source.layer]} cannot see it',
                           native=not authored, key=f'{name} used in {es.LAYERS[source.layer]}')


def rule_receiver_layers(project, source):
    """Extend the legacy layer check to all authored class names, including lowercase.

    E002 remains stable for existing consumers/baselines; E013 explicitly
    identifies the receiver-resolution layer contract for authored types.
    Member names (including method declarations) are not type uses.
    """
    if source.layer is None:
        return
    members = {s.offset for s in source.signatures}
    members.update(f.offset for d in source.classes for f in d.fields)
    own_methods = {s.name for s in source.signatures}
    reported = set()
    for match in re.finditer(r'(?<![\w.])\b[A-Za-z_]\w*\b', source.code):
        name = match[0]
        if name in reported or match.start() in members:
            continue
        if (name in own_methods and re.match(r'\s*\(', source.code[match.end():])
                and not re.search(r'\bnew\s+$', source.code[:match.start()])):
            continue  # unqualified method calls are not type references
        layers = project.types.get(name, set()) - {None}
        layers |= {layer for layer, names in project.native.items() if name in names}
        if not project.native and name in PINNED_LAYERS:
            layers.add(PINNED_LAYERS[name])
        if layers and min(layers) > source.layer:
            reported.add(name)
            yield _finding('HC-E013', source, match.start(), name,
                           f'{name} is defined in {es.LAYERS[min(layers)]}; '
                           f'{es.LAYERS[source.layer]} cannot see it',
                           native=name not in project.types,
                           key=f'{name} used in {es.LAYERS[source.layer]}')


_RECEIVER_CALL = re.compile(r'(?<![\w.)\]])\b([A-Za-z_]\w*'
                            r'(?:\s*\.\s*[A-Za-z_]\w*)*)\s*\.\s*([A-Za-z_]\w*)\s*\(')


def rule_receiver_methods(project, source):
    """Resolve explicit typed receivers; no cast, return-type or auto inference.

    Start only with types originally declared in our mods, not engine/provider
    types that we merely mod. Provider method tables are unavailable here.
    Ancestors may be engine classes. Field chains retain declared types,
    never the runtime subtype. Incomplete ancestor chains are skipped.
    """
    for method in _all_methods(source):
        fields = (project.receiver_members(method.owner.name, source.layer)[1]
                  if method.owner else {})
        parameters = {name: kind for kind, name, _ in method.parameters()}
        declarations = source.local_declarations(method)
        for call in _RECEIVER_CALL.finditer(source.body(method)):
            offset = method.body_start + call.start()
            receiver = re.split(r'\s*\.\s*', call[1])
            first = receiver.pop(0)
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
                elif first in project.links:  # explicit Type.Method static call
                    kind = first
                else:
                    continue
            for member in receiver:
                kind = project.resolve_typedef(kind)
                kind = project.receiver_members(kind, source.layer)[1].get(member, '')
            kind = project.resolve_typedef(kind)
            # Generic specializations and template parameters need substitution;
            # skip them instead of resolving against an unrelated concrete type.
            if kind not in project.types or kind not in project.links or '<' in kind:
                continue
            layers = project.types.get(kind, set()) - {None}
            if layers and source.layer is not None and min(layers) > source.layer:
                continue  # E013 owns invisible receiver types
            methods, _, complete = project.receiver_members(kind, source.layer)
            if complete and call[2] not in methods:
                yield _finding('HC-E012', source, offset, _symbol(method),
                               f'{call[1]}.{call[2]}: {kind} has no visible method {call[2]} '
                               '(including parents and modded bodies)',
                               native=any(name in project.native_names for name in project.lineage(kind)))


def _fields_visible(project, class_name):
    fields = {}
    for name in reversed(project.lineage(class_name)):
        for definition in project.links.get(name, ()):
            for item in definition.fields:
                fields[item.name] = item
    return fields


def _weak_element(project, type_text):
    type_text = project.resolve_typedef(type_text)
    match = re.match(r'^(?:array|set)<(.+)>$', type_text) or re.match(r'^map<[^,<>]+,(.+)>$', type_text)
    if not match:
        return None
    element = match.group(1)
    if element.startswith('ref') or not project.class_type(element):
        return None
    return element


def rule_weak_new(project, source):
    for definition in source.classes:
        for item in definition.fields:
            if not item.strong and project.class_type(item.type) and re.match(r'new\b', item.initializer):
                yield _finding('HC-E003', source, item.offset, f'{definition.name}.{item.name}',
                               f'{item.type} {item.name} is initialised with new but is not declared ref')
        visible = _fields_visible(project, definition.name)
        for method in definition.methods:
            body = source.body(method)
            shadow = set(_locals(body)) | {name for _, name, _ in method.parameters()}
            for name, item in visible.items():
                if name in shadow or item.strong:
                    continue
                if project.class_type(item.type):
                    for match in re.finditer(r'(?<![\w.])(?:this\s*\.\s*)?%s\s*=\s*new\b' % re.escape(name), body):
                        yield _finding('HC-E003', source, method.body_start + match.start(), _symbol(method),
                                       f'member {item.type} {name} is not ref; the new object is released at once')


def rule_weak_collection(project, source):
    for method in _all_methods(source):
        body = source.body(method)
        types = {}
        if method.owner is not None:
            types.update({n: f.type for n, f in _fields_visible(project, method.owner.name).items()})
        types.update({name: kind for kind, name, _ in method.parameters()})
        types.update(_locals(body))
        for name, kind in types.items():
            element = _weak_element(project, kind)
            if not element:
                continue
            pattern = r'(?<![\w.])(?:this\s*\.\s*)?%s\s*\.\s*(?:Insert|InsertAt|Set)\s*\(\s*(?:[^,();]*,\s*)?new\b'
            for match in re.finditer(pattern % re.escape(name), body):
                yield _finding('HC-E004', source, method.body_start + match.start(), _symbol(method),
                               f'{name} is {kind}; its elements are weak, so the new {element} is released at once')


def rule_modded_links(project, source):
    """Links compile in mod load order, then case-insensitive path order (mod_sources). Native boot 021:
    HCHordeMigration.c called HCVarietyWalkerHerd, added only by the later Infected/Variety link
    (Undefined function); HCWeatherDaysModule.c calling methods of the earlier HCChernarusAtmosphere.c
    link compiles (boot 024). So only calls to methods that a later link adds are flagged."""
    for definition in source.classes:
        links = project.links.get(definition.name, [])
        if not any(d.modded for d in links):
            continue
        order = [d for d in links if not d.modded] + [d for d in links if d.modded]
        index = next(i for i, d in enumerate(order) if d is definition)
        known = set()
        for name in project.lineage(definition.name)[1:]:
            for link in project.links.get(name, ()):
                known |= {m.name for m in link.methods} | {f.name for f in link.fields}
        for link in order[:index + 1]:
            known |= {m.name for m in link.methods} | {f.name for f in link.fields}
        later = {}
        for link in order[index + 1:]:
            for method in link.methods:
                if 'override' not in method.modifiers:
                    later.setdefault(method.name, link.source.rel)
        for method in definition.methods:
            body = source.body(method)
            shadow = set(_locals(body)) | {n for _, n, _ in method.parameters()}
            for match in _CALL.finditer(body):
                name = match.group(2)
                if name in _KEYWORDS or name in known or name in shadow or name not in later:
                    continue
                yield _finding('HC-E005', source, method.body_start + match.start(2), _symbol(method),
                               f'{name}() is added only by a later modded {definition.name} link ({later[name]}); '
                               'declare it (empty) on the base class and override it there')


def _bounded(body, receiver):
    """True when the method consults receiver.Length(), or an alias's Length(), or guards an
    IndexOf/LastIndexOf result of the receiver against a negative value before slicing."""
    dotted = r'\s*\.\s*'.join(map(re.escape, receiver.split('.')))
    if re.search(r'(?<![\w.])%s\s*\.\s*Length(?:Utf8)?\s*\(' % dotted, body):
        return True
    alias = re.search(r'(?<![\w.])%s\s*=\s*([A-Za-z_][\w.]*)\s*;' % dotted, body)
    if alias and re.search(r'(?<![\w.])%s\s*\.\s*Length\s*\(' % re.escape(alias.group(1)), body):
        return True
    for index in re.finditer(r'(?<![\w.])(\w+)\s*=\s*%s\s*\.\s*(?:Last)?IndexOf\s*\(' % dotted, body):
        name = re.escape(index.group(1))
        if re.search(r'\b%s\s*(?:<\s*0|==\s*-\s*1|>=\s*0|<\s*1|>\s*-\s*1)' % name, body):
            return True
    return False


def rule_substring(project, source):
    for method in _all_methods(source):
        body = source.body(method)
        for match in re.finditer(r'\.\s*Substring\s*\(', body):
            receiver = re.search(r'([A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*)*)\s*$', body[:match.start()])
            if receiver:
                text = re.sub(r'\s+', '', receiver.group(1))
                if _bounded(body, text):
                    continue
                message = f'{text}.Substring(...) without consulting {text}.Length() in this method'
            else:
                message = 'Substring on an expression result; bound it by that string\'s Length() first'
            yield _finding('HC-E006', source, method.body_start + match.start(), _symbol(method), message)


def _visible_type_layer(project, name, layer):
    """Lowest layer defining a type named name that a source at layer can see, else None."""
    layers = set(project.types.get(name, set()))
    layers |= {index for index, names in project.native.items() if name in names}
    if name in PINNED_TYPES:
        layers.add(PINNED_LAYERS.get(name, 0))
    visible = [index for index in layers if index is not None and (layer is None or index <= layer)]
    return min(visible) if visible else None


def rule_type_named_methods(project, source):
    """Native boot 026 (acab865): HCXGrudge declared Slot(...) and an unqualified Slot(x) call bound to
    vanilla class Slot(float). Flag a method named like a visible type when it is called unqualified."""
    for definition in source.classes:
        bodies = [d.source.body(m) for name in project.lineage(definition.name)
                  for d in project.links.get(name, ()) for m in d.methods]
        for method in definition.methods:
            name = method.name
            if name.startswith('~') or 'override' in method.modifiers or name == definition.name:
                continue
            if _visible_type_layer(project, name, source.layer) is None:
                continue
            call = re.compile(r'(?<![\w.])(?<!new )%s\s*\(' % re.escape(name))
            if not any(call.search(body) for body in bodies):
                continue
            authored = name in project.types
            yield _finding('HC-E007', source, method.offset, _symbol(method),
                           f'method {name} shares its name with a visible {"" if authored else "native "}type and '
                           'is called unqualified, so the call can bind to the type; rename it',
                           native=not authored and name not in PINNED_TYPES)



# ---------------------------------------------------------------- log lines

_BARE_PRINT = re.compile(r'(?<![\w.])Print\s*\(\s*(?!(?:true|false|null)\s*\))([A-Za-z_]\w*)\s*\)')


def rule_bare_print(project, source):
    """Boot 032 RPT: Print(line) logged "string line = '[HC XAI] live ...'" (EnDebug.c proto Print(void var)
    describes a variable argument), so tagged RPT lines lost their prefix. Print an expression: "" + line."""
    for method in _all_methods(source):
        body = source.body(method)
        for match in _BARE_PRINT.finditer(body):
            yield _finding('HC-L001', source, method.body_start + match.start(), _symbol(method),
                           f'Print({match.group(1)}) logs the declaration, not the text; use Print("" + {match.group(1)})')

# ---------------------------------------------------------------- silent refusals

_IDENTITY_LOG = re.compile(r'\b(?:Print|PrintFormat|PrintToRPT|DPrint|Error|ErrorEx|Log\w*|log\w*|\w+Log\w*)\s*(?:\(|\.)')
_VERSION_LITERAL = re.compile(r'(?<!\d)\d+\.\d+\b')
_VALUE = r'[A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*)*'
_BUILD_TOKEN = (r'"[^"\n]*"|[A-Za-z_]\w*(?:\s*\(\s*\))?'
                r'(?:\s*\.\s*[A-Za-z_]\w*(?:\s*\(\s*\))?)*')
_BUILD_COMPARE = re.compile(r'\(*\s*(?P<left>' + _BUILD_TOKEN + r')\s*\)*\s*(?:==|!=)\s*'
                            r'\(*\s*(?P<right>' + _BUILD_TOKEN + r')\s*\)*')


def _build_value(value, raw=False):
    name = value.rsplit('.', 1)[-1].lower()
    if raw:
        # Value/value comparisons need stronger evidence than literals: generic
        # Version is commonly an RPC/schema and Building is geometry. Untyped
        # Build fields still need owner review; explicit profile stamps, native
        # getters and GetVersion out-argument aliases are the supported heuristic.
        return (name == 'buildversion'
                or (value.endswith('()') and ('build' in name or name == 'getversion()'))
                or re.fullmatch(r'(?:m_|s_)?(?:engine|game|runtime|native|current|actual)(?:build|version)', name))
    return (('build' in name and 'building' not in name)
            or re.fullmatch(r'(?:(?:m_|s_)?(?:engine|game|runtime|native|current|actual)?)version', name)
            or value.endswith('GetVersion()'))


def rule_build_identity(project, source):
    """Inspect build operands without treating comments/log text as code.

    Track GetVersion out-arguments and simple aliases within each method. Also
    recognise build-named values and conventional engine-version names (not a
    dependency's ProviderVersion). This is deliberately not intermethod dataflow.
    Include value/value, zero-argument getters and parenthesised operands.
    A log anywhere in this method satisfies the rule; runtime path coverage is
    still a native acceptance check. The shared matcher owns raw comparisons.
    """
    for method in _all_methods(source):
        if method.owner and method.owner.name == 'HCBuildIdentity':
            continue
        body = source.body(method)
        if _IDENTITY_LOG.search(body):
            continue
        observed = {re.sub(r'\s+', '', m[1]) for m in
                    re.finditer(r'\bGetVersion\s*\(\s*(' + _VALUE + r')\s*\)', body)}
        aliases = list(re.finditer(r'(' + _VALUE + r')\s*=(?!=)\s*(' + _VALUE + r')\s*;', body))
        while True:
            before = set(observed)
            for alias in aliases:
                target, value = (re.sub(r'\s+', '', alias[i]) for i in (1, 2))
                if value in observed or _build_value(value):
                    observed.add(target)
            if observed == before:
                break
        for match in _BUILD_COMPARE.finditer(body):
            operands = [re.sub(r'\s+', '', match[key]) for key in ('left', 'right')]
            # A normalizer call with arguments is outside the operand grammar;
            # never mistake its argument's closing paren for a raw comparison.
            if 'HCBuildIdentity.Normalize' in operands:
                continue
            literal_index = next((i for i, value in enumerate(operands) if value.startswith('"')), None)
            raw = literal_index is None
            if not any(value in observed or _build_value(value, raw=raw) for value in operands if not value.startswith('"')):
                continue
            group = ('left', 'right')[literal_index] if literal_index is not None else 'left'
            offset = method.body_start + match.start(group)
            if literal_index is not None:
                literal = source.text[offset:method.body_start + match.end(group)]
                if not _VERSION_LITERAL.search(literal):
                    continue
            yield _finding('HC-S004', source, offset, _symbol(method), RULES['HC-S004'])

def _branch(body, position):
    """(condition or None, branch text, is_branch, is_block) for a return at body offset position."""
    start = max(body.rfind(';', 0, position), body.rfind('{', 0, position), body.rfind('}', 0, position))
    prefix = body[start + 1:position].strip()
    if prefix:
        match = re.match(r'^(?:else\s+)?if\s*\(', prefix)
        if match:
            close = es.matching_paren(prefix, match.end() - 1)
            return prefix[match.end():close], prefix, True, False
        return None, prefix, True, False     # else / case X: / loop one-liner
    depth, block = 0, -1
    for index in range(position - 1, -1, -1):
        ch = body[index]
        if ch == '}':
            depth += 1
        elif ch == '{':
            if depth == 0:
                block = index
                break
            depth -= 1
    if block <= 0:
        return None, body[:position], False, True  # unconditional return in the method body itself
    text = body[block:position]
    head_start = max(body.rfind(';', 0, block), body.rfind('{', 0, block), body.rfind('}', 0, block))
    header = body[head_start + 1:block].strip()
    match = re.match(r'^(?:else\s+)?if\s*\(', header)
    if match:
        close = es.matching_paren(header, match.end() - 1)
        return header[match.end():close], text, True, True
    return None, text, True, True


def _exempt(condition, parameters, reentry):
    if condition is None:
        return False
    names = '|'.join(re.escape(n) for n in parameters) or r'(?!)'
    param_guard = re.compile(r'^(?:!\s*(?:%s)(?:\s*\.\s*\w+)*|(?:%s)(?:\s*\.\s*\w+)*\s*==\s*null)$' % (names, names))
    for term in es.split_top(condition, '||'):
        term = term.strip()
        while term.startswith('(') and term.endswith(')') and es.matching_paren(term, 0) == len(term) - 1:
            term = term[1:-1].strip()
        if not (param_guard.match(term) or _ROLE_GUARD.match(term) or (reentry and _REENTRY_GUARD.match(term))
                or _REASON_IN_SCOPE.search(term)):
            return False
    return True


# A reason-code member (m_Refusal, m_LastReason, ...) whose latest assignment before the
# refusal is a non-empty value: the caller reports it (HCSearchHouses.ReportRefusal).
_MEMBER_REASON = re.compile(r'\bm_\w*(?:Refusal|Reason)\w*\s*=(?!=)\s*([^;]*);')


def _member_reason_set(body, offset):
    last = None
    for assigned in _MEMBER_REASON.finditer(body, 0, offset):
        last = assigned.group(1).strip()
    return last is not None and last not in ('""', "''")


def _silent_returns(source, method, pattern, rule, what, reentry):
    body = source.body(method)
    parameters = [name for _, name, _ in method.parameters()]
    reason_params = [name for _, name, out in method.parameters() if out]
    emitter = _EMITTER if not reason_params else re.compile(
        _EMITTER.pattern + '|' + '|'.join(r'\b%s\s*=(?!=)' % re.escape(n) for n in reason_params))
    for match in re.finditer(pattern, body):
        condition, text, is_branch, is_block = _branch(body, match.start())
        if not is_branch or emitter.search(text) or _exempt(condition, parameters, reentry):
            continue
        if _member_reason_set(body, match.start()):
            continue
        # A block that does work before returning is a handled path (delegation, cleanup), not a refusal.
        if is_block and any(c.group(1) not in _KEYWORDS for c in _ANY_CALL.finditer(text[1:])):
            continue
        offset = method.body_start + match.start()
        yield _finding(rule, source, offset, _symbol(method),
                       f'{what} with no reason: {re.sub(chr(92) + "s+", " ", source.line_text(offset))[:140]}')


def _harness(method):
    return bool(_HARNESS.search(method.owner.name if method.owner is not None else '')
                or _HARNESS.search(method.owner.source.rel if method.owner is not None else ''))


def rule_silent_commit(project, source):
    for method in _all_methods(source):
        if _harness(method):
            continue
        if method.return_type == 'void' and COMMIT_VOID.match(method.name):
            yield from _silent_returns(source, method, r'\breturn\s*;', 'HC-S001', 'returns', True)


def rule_silent_gate(project, source):
    for method in _all_methods(source):
        # static bool helpers are pure policies; their caller owns the reason.
        if _harness(method) or 'static' in method.modifiers:
            continue
        if method.return_type == 'bool' and GATE_BOOL.match(method.name):
            yield from _silent_returns(source, method, r'\breturn\s+false\s*;', 'HC-S002', 'refuses', False)


def _reachable(project, roots, limit=6):
    """Bodies reachable from root methods by name; names declared by more than 3 classes are not followed."""
    seen, frontier = set(), list(roots)
    for _ in range(limit):
        following = []
        for method in frontier:
            if id(method) in seen:
                continue
            seen.add(id(method))
            yield method
            body = method.owner.source.body(method) if method.owner is not None else ''
            for match in _ANY_CALL.finditer(body):
                targets = project.methods.get(match.group(1), [])
                if 0 < len({t.owner.name for t in targets}) <= 3:
                    following.extend(targets)
        frontier = following


def rule_predicted_actions(project, source):
    for definition in source.classes:
        lineage = project.lineage(definition.name)
        # An authored action: some class in its authored chain derives from a vanilla Action*Base.
        if definition.modded or not any(_ACTION_BASE.match(project.base_of(name)) for name in lineage):
            continue
        methods = [m for name in lineage for d in project.links.get(name, ()) for m in d.methods]
        conditions = [m for m in methods if m.name in ('ActionCondition', 'ActionConditionContinue')]
        if not any(_PREDICTION.search(m.owner.source.body(m)) for m in conditions):
            continue
        hooks = [m for m in methods if re.match(r'^On\w*Server$', m.name)]
        if any(_PLAYER_MESSAGE.search(m.owner.source.body(m)) for m in _reachable(project, hooks)):
            continue
        yield _finding('HC-S003', source, definition.offset, definition.name,
                       'ActionCondition predicts on the client but no server hook path calls MessageStatus '
                       'or a refusal helper, so a server refusal looks like a progress bar that stops',
                       key=f'{definition.name} predicted without server refusal message')


ALL_RULES = (rule_parse_issues, rule_ternary, rule_file_handle_int, rule_keyword_names, rule_layers, rule_weak_new, rule_weak_collection, rule_modded_links,
             rule_receiver_layers, rule_receiver_methods, rule_modded_module,
             rule_collection_keys, rule_handle_null, rule_vanilla_storage,
             rule_substring, rule_type_named_methods, rule_bare_print, rule_build_identity, rule_silent_commit, rule_silent_gate,
             rule_predicted_actions, enforce_json.rule_json_defaults,
             _readiness.rule_module_names, _readiness.rule_engine_type_names)


def lint(sources, native=None, rules=ALL_RULES, symbols=None, provider_layers=None):
    project = Project(sources, native, symbols, provider_layers)
    findings = []
    for source in sources:
        for rule in rules:
            findings.extend(rule(project, source))
    return sorted(set(findings), key=lambda f: (f.path, f.line, f.rule, f.symbol, f.key))


def lint_texts(files, native=None, rules=ALL_RULES):
    """Lint {relative path: text}; for behavioural tests with explicit synthetic fixtures."""
    sources = [es.Source(Path(path), text) for path, text in sorted(files.items())]
    return lint(sources, native, rules)


# ---------------------------------------------------------------- baseline

def load_baseline(path=BASELINE):
    """The reviewed baseline; a missing file means no reviewed exceptions."""
    path = Path(path)
    baseline = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'entries': []}
    if path.exists() and path.resolve() == BASELINE.resolve():
        identities = {(entry['rule'], entry['path'], entry['symbol'], entry['key'])
                      for entry in baseline.get('entries', [])}
        for entry in enforce_json.LEGACY_BASELINE:
            identity = (entry['rule'], entry['path'], entry['symbol'], entry['key'])
            if identity not in identities:
                baseline.setdefault('entries', []).append(dict(entry))
    return baseline


def compare(findings, baseline, native_available):
    """(new findings, stale baseline entries) by identity multiset; line numbers are not identity."""
    allowed = Counter()
    entries = {}
    for entry in baseline.get('entries', []):
        if entry.get('native') and not native_available:
            continue
        identity = (entry['rule'], entry['path'], entry['symbol'], entry['key'])
        allowed[identity] += int(entry.get('count', 1))
        entries[identity] = entry
    seen = Counter(f.identity() for f in findings)
    new, budget = [], Counter(allowed)
    for finding in findings:
        if budget[finding.identity()] > 0:
            budget[finding.identity()] -= 1
        else:
            new.append(finding)
    stale = [dict(entries[i], unused=allowed[i] - seen[i]) for i in sorted(allowed) if seen[i] < allowed[i]]
    return new, stale


def baseline_from(findings, review):
    counts = Counter(f.identity() for f in findings)
    native = {f.identity(): f.native for f in findings}
    lines = {}
    for f in findings:
        lines.setdefault(f.identity(), f.line)
    entries = []
    for identity in sorted(counts):
        rule, path, symbol, key = identity
        entry = {'rule': rule, 'path': path, 'symbol': symbol, 'key': key, 'count': counts[identity],
                 'line_at_review': lines[identity], 'review': review}
        if native[identity]:
            entry['native'] = True
        entries.append(entry)
    return {'schema': 1, 'scope': 'authored mods/*/scripts; reviewed pre-existing findings only',
            'entries': entries}


def native_cache(argument=None, disabled=False):
    if disabled:
        return None
    path = Path(argument or os.environ.get('HC_NATIVE_SCRIPTS') or DEFAULT_CACHE).expanduser()
    if not (path / '3_Game').is_dir():
        return None
    symbols = native_symbols.load(path, allow_uncached=True)
    return {int(layer): set(names) for layer, names in symbols['types'].items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--native-scripts', help='extracted engine scripts (local only)')
    parser.add_argument('--no-native', action='store_true', help='pinned engine names only (deterministic CI mode)')
    parser.add_argument('--baseline', type=Path, default=BASELINE)
    parser.add_argument('--all', action='store_true', help='also print baselined findings')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--write-baseline', metavar='REVIEW_NOTE',
                        help='rewrite the baseline from the current findings with this review note')
    args = parser.parse_args(argv)
    path = Path(args.native_scripts or os.environ.get('HC_NATIVE_SCRIPTS') or DEFAULT_CACHE).expanduser()
    symbols = None
    if not args.no_native and (path / '3_Game').is_dir():
        try:
            symbols = native_symbols.load(path, allow_uncached=True)
        except (OSError, ValueError):
            parser.exit(1, 'enforce_lint: cannot read scripts or write the local symbol cache\n')
    native = ({int(layer): set(names) for layer, names in symbols['types'].items()}
              if symbols is not None else None)
    mods = tuple(sorted(p.parent.name for p in (args.root / 'mods').glob('*/scripts') if p.is_dir()))
    sources = es.mod_sources(args.root, mods=mods)
    provider_layers = {}
    if not args.no_native:
        project = Project(sources, native, symbols)
        unknown = {d.name for source in sources for d in source.classes
                   if d.modded and not project.declaring_layers(d.name, source)}
        provider_layers = workshop_class_layers(unknown)
    findings = lint(sources, native, symbols=symbols, provider_layers=provider_layers)
    if args.write_baseline:
        args.baseline.write_text(json.dumps(baseline_from(findings, args.write_baseline), indent=1) + '\n',
                                 encoding='utf-8')
        print(f'wrote {len(findings)} findings to {args.baseline.name}')
        return 0
    baseline = load_baseline(args.baseline)
    new, stale = compare(findings, baseline, native is not None)
    per_rule = Counter(f.rule for f in findings)
    new_rule = Counter(f.rule for f in new)
    if args.json:
        print(json.dumps({'status': 'fail' if new or stale else 'pass', 'native': native is not None,
                          'counts': {r: {'total': per_rule[r], 'new': new_rule[r]} for r in RULES},
                          'new': [asdict(f) for f in new], 'stale': stale}, indent=1))
    else:
        for finding in (findings if args.all else new):
            print(('NEW  ' if finding in new else 'base ') + finding.render())
        for entry in stale:
            print(f"STALE {entry['path']}: {entry['rule']} {entry['symbol']}: {entry['key']} "
                  '(fixed? remove it from the baseline)')
        for rule in RULES:
            print(f'{rule} total={per_rule[rule]} new={new_rule[rule]}  {RULES[rule]}')
        print(f"enforce_lint: {'FAIL' if new or stale else 'pass'} findings={len(findings)} new={len(new)} "
              f"stale={len(stale)} native={'yes' if native is not None else 'no'}")
        # The tick-path cost check is part of the same gate; baselined lines stay quiet.
        perf_failed = run_perf(args.root)
        return 1 if new or stale or perf_failed else 0
    return 1 if new or stale else 0


def run_perf(root):
    import contextlib
    import io
    from tools.validate import enforce_perf
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        code = enforce_perf.main(['--root', str(root)])
    for line in captured.getvalue().splitlines():
        if not line.endswith('[baseline]'):
            print(line)
    return code != 0


if __name__ == '__main__':
    sys.exit(main())
