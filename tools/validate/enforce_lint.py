"""Project-wide static lint for Enforce Script traps and silent server refusals.

Run ``python3 -B -m tools.validate.enforce_lint`` from the repository root.
Standard library only, offline, deterministic (sorted inputs, no clocks in
results). It reads authored sources under mods/*/scripts and, when present,
the local extracted engine script cache (``--native-scripts`` or the
HC_NATIVE_SCRIPTS environment variable; never committed). ``--no-native``
forces the pinned-only mode the unit tests use.

Preland also prints every SERVER/CLIENT conditional arm under mods/*/scripts
and explicitly checks those files with HC-E012 and HC-E053, preserving the
whole-project receiver/signature context. Both arms are inspected; this is
static coverage, not evidence of a client compile. The server compile gate
cannot compile code excluded by SERVER, and neither compile driver currently
exposes a qualified client-defines mode.

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
from tools.validate import enforce_lint_handles as _handles
from tools.validate import enforce_rules_readiness as _readiness
from tools.validate import enforce_lint_use as _use
from tools.validate import enforce_lint_syntax as _syntax
from tools.validate import enforce_lint_names as _names
from tools.validate import native_symbols

ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).with_name('enforce_lint_baseline.json')
STORAGE_ALLOWLIST = Path(__file__).with_name('enforce_lint_storage_allowlist.json')
PROVIDER_METHODS = Path(__file__).with_name('enforce_lint_provider_methods.json')
WORKSHOP_ROOT = Path('/mnt/e/HollowCountryLocal/friend-local-1')
DEFAULT_CACHE = Path('~/.cache/hollow-country/native-scripts/scripts-1.30.164289')
# Vanilla 1.30.164289 4_World/Entities/GardenBase/Slot.c declares class Slot(float); an authored
# method named Slot made an unqualified call resolve to that class (native boot 026, commit acab865).
PINNED_TYPES = frozenset(ENGINE_TYPE_NAMES) | {'Slot', 'PlayerBase', 'DayZPlayer', 'ActionBase', 'House'}
# Where a pinned name lives, so the layer rule can work without the native cache.
# Native compile 2026-11-21 (15d39e76): Queue(region) bound to an engine
# Queue symbol absent from the extracted 1.30 scripts. Retain that observed
# collision as a pin, just as Slot above, alongside the installed symbol index.
PINNED_GLOBALS = {'Queue': {0}}
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
    'HC-E018': 'variable name shadows a type visible in this script module',
    'HC-E019': 'member declared only by a later file in the same modded-class chain',
    'HC-E020': 'string concatenation with too many + operands into a typed string (assignment, string parameter or return; Print is exempt) (native compile: Formula too complex); build it in steps with +=',
    'HC-E022': 'Expansion AI call outside HCXExpansionBridge.c (dependency invariant boundary)',
    'HC-E021': 'line starts with a binary operator continuing the previous line (native compile: Unknown type / Syntax error)',
    'HC-E023': 'else is not adjacent to an if body; move the intervening statement outside the if/else chain',
    'HC-E024': 'typename cannot return null; declare an empty typename and return it',
    'HC-E028': 'initializer must be a literal; a non-literal static const read as 0 natively (build 169)',
    'HC-E029': 'duplicate local declaration or local shadows a parameter (Enforce function scope is flat)',
    'HC-E030': 'boolean expression combines too many terms with inline string concatenation (native compile: Formula too complex); hold the string in a local first',
    'HC-E027': 'COT/CF/ExpansionStatic call outside its owned dependency bridge',
    'HC-E026': 'fresh unowned call result passed as an argument; hold it in a local first (build 161 crash)',
    'HC-O026': 'unresolved call-result ownership; inspect the factory and hold fresh results in a local',
    'HC-E025': 'method collides with a native global function or class and is called unqualified; rename it',
    'HC-E031': 'unguarded ConfigGet* read: check ConfigIsExisting first or go through HCConfigHelper (logs No entry / error value on a missing path)',
    'HC-E032': 'FindPath output array is null or never allocated (native FindPath dereferences it)',
    'HC-E033': 'navmesh query with a PGFilter that never had SetFlags (an empty filter matches no polygon)',
    'HC-E034': 'AIWorld.DeleteGroup without a living-member check (it destroys every agent still attached)',
    'HC-E035': 'StartCommand_ScriptInst on a DayZInfected (engine builds the command with null constructor arguments); use StartCommand_Script(new Command(this))',
    'HC-E036': 'new X passed directly as an argument to a call that does not store it (the temporary has no owner)',
    'HC-E037': 'UpdatePathgraphRegionByObject refreshes a flat-Y region; use HCPathgraphRefresh bounds with explicit Y margins',
    'HC-E049': 'modded class of an engine class the compiler refuses to mod (native compile: Engine class cannot be modded); hook the scripted subclass instead',
    'HC-E051': 'assignment into an indexed slot whose index calls a function (native compile: Function definition inside block); hold the index in a local first',
    'HC-E048': 'foreach iterates a call result directly (native VME NULL pointer to instance, #337); hold the collection in a typed local first',
    'HC-E038': 'array.Remove(0) moves the LAST element into slot 0 (native EnScript.c Remove, unordered); use RemoveOrdered(0) or annotate "// HC-ORDER: unordered ok"',
    'HC-L001': 'Print of a bare variable (the engine logs "string name = \'...\'" instead of the text)',
    'HC-S001': 'server commit point returns early without logging or telling the player why',
    'HC-S002': 'server gate returns false without a reason code, log line or player message',
    'HC-S003': 'client-predicted action whose server path never sends the player a refusal message',
    'HC-E055': 'test addon HCOwns fx_ command is absent from HCAdminCatalog; HCReceive rejects it before the provider',
    'HC-E054': 'two HC script RPC ids share a value; each RPC needs its own id',
    'HC-E053': 'method overrides or redeclares an inherited proto method, or adds an overload of its native name (build 185: Multiple declaration of function); hook a script method instead',
    'HC-E052': 'GunPile and reach fixtures must use config compatibility, never weapon magazine/muzzle/chamber natives',
    'HC-S004': 'literal engine/build version comparison without a Print or log in the same method',
    enforce_json.RULE: enforce_json.DESCRIPTION,
    _handles.RULE: _handles.DESCRIPTION,
}
RULES.update(_readiness.RULES)  # HC-S006 module names, HC-E009 engine-type variable names
RULES.update(_use.RULES)  # HC-E040 use counter reached from an init path
RULES.update(_syntax.RULES)  # HC-E042..HC-E047, bound in ALL_RULES below
RULES.update(_names.RULES)  # HC-E050 bare name resolves to nothing, bound in ALL_RULES below

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
    severity: str = 'error'

    def identity(self):
        return (self.rule, self.path, self.symbol, self.key)

    def render(self):
        return f'{self.path}:{self.line}: {self.rule} [{self.severity}] {self.symbol}: {self.message}'


class Project:
    """Cross-file indexes over authored sources (and optional native type names)."""

    def __init__(self, sources, native=None, symbols=None, provider_layers=None):
        self.sources = sources
        self.native = native or {}
        self.symbols = (symbols or {}).get('classes', {})
        self.native_globals = dict(PINNED_GLOBALS)
        self.native_globals.update((symbols or {}).get('globals', {}))
        self._receiver_cache = {}
        self.provider_layers = provider_layers or {}
        self.storage_allowlist = load_storage_allowlist()
        self.provider_methods = load_provider_methods()
        # The committed names index is not the engine method table; only a real
        # extracted-scripts cache may judge calls on engine-declared receivers.
        self.engine_receivers = bool(self.symbols) and (symbols or {}).get('origin') != 'names-index'
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
        self._visible_types = {}
        self._field_names = {}
        self.methods = {}
        for definitions in self.links.values():
            for definition in definitions:
                for method in definition.methods:
                    self.methods.setdefault(method.name, []).append(method)

    def visible_types(self, layer):
        if layer not in self._visible_types:
            names = {name for name, layers in self.types.items()
                     if any(index is not None and (layer is None or index <= layer) for index in layers)}
            for index, native in self.native.items():
                if layer is None or index <= layer:
                    names.update(native)
            names.update(name for name in PINNED_TYPES
                         if layer is None or PINNED_LAYERS.get(name, 0) <= layer)
            self._visible_types[layer] = names
        return self._visible_types[layer]

    def field_names(self, definition):
        key = id(definition)
        if key not in self._field_names:
            self._field_names[key] = set(_handle_nonlocals(definition.source, definition))
        return self._field_names[key]

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


def rule_static_const_literals(project, source):
    """Static primitive constants must survive native initialization (build 169).

    Use masked code so comments, string contents and preprocessor lines cannot
    introduce declarations or operators. Quotes remain, preserving string tokens.
    """
    declaration = re.compile(r'\b(?:static\s+const|const\s+static)\s+'
                             r'(?:int|float|bool|string)\s+([^;{}]+);')
    literal = re.compile(r'(?:[+-]?\s*(?:0[xX][0-9a-fA-F]+|'
                         r'(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)'
                         r'|true|false|"[^"\n]*")')
    for match in declaration.finditer(source.code):
        offset = match.start(1)
        for binding in es.split_top(match.group(1), ','):
            name, separator, initializer = binding.partition('=')
            if not separator or not literal.fullmatch(initializer.strip()):
                yield _finding('HC-E028', source, offset, name.strip(), RULES['HC-E028'])
            offset += len(binding) + 1


def rule_duplicate_locals(project, source):
    """Reject redeclarations across the entire function, including sibling blocks.

    Installed 1.30.164289 scripts never repeat a typed for-loop name in one
    parsed method. EntityAI.SetInvisibleRecursive declares i at line 4070 and
    reuses it without a type at 4096, even across blocks (see audit/CHECKS.md).
    Use masked source bindings, including grouped declarations and foreach
    slots, without changing the lexical scopes used by receiver resolution.
    """
    declaration = re.compile(r'[A-Za-z_]\w*(?:\s*<[^;(){}=]*>)?'
                             r'\s+([A-Za-z_]\w*)\s*(?=[=;\[,:)])')
    for method in _all_methods(source):
        seen = {name: 'parameter' for _, name, _ in method.parameters()}
        declarations = {}
        for name, kind, start, end in source.local_declarations(method):
            # The shared receiver model deliberately accepts broad generic
            # text. Comparisons such as `a < b || c > value` are not types,
            # and `Call(out value)` passes a binding rather than declaring it.
            if kind in {'out', 'inout', 'in'} or not re.fullmatch(r'[\w<>,]+', kind):
                continue
            declarations[start] = name
            match = declaration.match(source.code, start)
            if match and match[1] == name:
                for grouped, offset in _grouped_declarators(source.code, match.end(), end):
                    declarations[offset] = grouped
        for start, name in sorted(declarations.items()):
            if name in seen:
                yield _finding('HC-E029', source, start, _symbol(method),
                               f'{name}: {RULES["HC-E029"]}; first declared as {seen[name]}')
            else:
                seen[name] = f'local at line {source.line_of(start)}'


def rule_ternary(project, source):
    for match in re.finditer(r'\?', source.code):
        yield _finding('HC-E001', source, match.start(), '<file>', RULES['HC-E001'])


def rule_file_handle_int(project, source):
    # Native boot 074: FileHandle is typedef int[]; comparing with 0 compiles, assigning 0 does not.
    names = set(re.findall(r'\bFileHandle\s+(\w+)', source.code))
    for name in sorted(names):
        for match in re.finditer(r'(?<![\w.])' + name + r'\s*=\s*\d+\s*;', source.code):
            yield _finding('HC-E010', source, match.start(), name, RULES['HC-E010'])


# Native compile gate, build 132 (#313): an assignment of a string concatenation with 21 '+'
# operands failed with "Formula too complex" (hcxaifortification.c,90); the longest that compiles
# on main has 13. The limit sits between the two observations. Wave H gate (13ac85b8): the same error
# on a 20-operand concatenation passed to a method with a typed string parameter (HCRow(string),
# hcsitesurveyprobe.c,565; a 14-operand HCRow call compiled). Print takes `void var` (native
# 1_Core/proto/EnDebug.c) and compiles with 48 operands on main, so a statement that is a direct
# Print( call is exempt; every other statement counts. source.code has literal contents blanked, so
# a '+', ';' or brace inside a string never counts or splits.
MAX_STRING_PLUS = 16
_VOID_PARAMETER_CALL = re.compile(r'Print\s*\(')
# Lookbehind, not a consumed separator: consuming the ';' skipped every second statement.
_STRING_STATEMENT = re.compile(r'(?:^|(?<=[;{}]))\s*([^;{}]*);')


def rule_string_formula(project, source):
    for match in _STRING_STATEMENT.finditer(source.code):
        statement = match.group(1)
        if '"' not in statement or _VOID_PARAMETER_CALL.match(statement):
            continue
        operands = re.sub(r'\+\+|\+=', '', statement).count('+')
        if operands > MAX_STRING_PLUS:
            yield _finding('HC-E020', source, match.start(1), '<file>',
                           f'{operands} + operands (limit {MAX_STRING_PLUS}): {RULES["HC-E020"]}')


# Build 167 (a6433570): a 14-term condition with literal string concatenation
# failed natively; passing concat conditions on 40b7fa49 reach 8 terms, so the
# threshold sits between them (lead, 11-22). Calibrated offline; this is a
# structural warning threshold, not a model of the compiler's expression budget.
MIN_STRING_BOOLEAN_TERMS = 10
_INLINE_STRING_PLUS = re.compile(r'"[^"]*"\s*\)*\s*\+(?![+=])|(?<!\+)\+(?![+=])\s*\(*\s*"')


def _boolean_expressions(source):
    """Yield (keyword offset, expression) for if/while guards and returns.

    The shared lexer has already blanked comments and literal contents, keeping
    quotes and offsets. Parentheses may nest and expressions may span lines.
    """
    for match in re.finditer(r'\b(if|while|return)\b', source.code):
        start = match.end()
        if match[1] == 'return':
            end = source.code.find(';', start)
            if end < 0:
                continue
        else:
            while start < len(source.code) and source.code[start].isspace():
                start += 1
            if start == len(source.code) or source.code[start] != '(':
                continue
            end = es.matching_paren(source.code, start)
            start += 1
        yield match.start(), source.code[start:end]


def rule_boolean_string_formula(project, source):
    for offset, expression in _boolean_expressions(source):
        # Count both && and ||, including nested groups: parentheses do not
        # split the native formula into separate statements.
        terms = len(re.findall(r'&&|\|\|', expression)) + 1
        if terms >= MIN_STRING_BOOLEAN_TERMS and _INLINE_STRING_PLUS.search(expression):
            yield _finding('HC-E030', source, offset, '<file>',
                           f'{terms} boolean terms (threshold {MIN_STRING_BOOLEAN_TERMS}): {RULES["HC-E030"]}')


# Native compile gate, build 132 (#313): a return expression continued on the next line with a
# leading "||" failed with "Unknown type '||'" (hcinteriorplacementcursor.c,213).
_LEADING_OPERATOR = re.compile(r'^[ \t]*(\|\||&&|\+(?![+=])|\*(?!=)|/(?![=/*])|%|==|!=)', re.M)


def rule_leading_operator(project, source):
    for match in _LEADING_OPERATOR.finditer(source.code):
        yield _finding('HC-E021', source, match.start(1), '<file>', f'{match.group(1)}: {RULES["HC-E021"]}')



# Tokens use the same comment/string-masked Source as the structural parser.
_TOKENS = re.compile(r'[A-Za-z_]\w*|[^\s]')


def rule_broken_else(project, source):
    """Consume complete statements so dangling else binds to the nearest if.

    A block and a braceless statement both consume exactly one if body. Any
    following statement ends that if's opportunity to consume an else.
    """
    for method in _all_methods(source):
        body = source.body(method)
        if not re.search(r'\belse\b', body):
            continue
        tokens = list(_TOKENS.finditer(body))
        values = [t[0] for t in tokens]
        pairs, stack = {}, []
        for i, value in enumerate(values):
            if value in {'(', '[', '{'}:
                stack.append(i)
            elif value in {')', ']', '}'} and stack:
                pairs[stack.pop()] = i + 1
        size = len(tokens)

        def statement(i):
            if i >= size:
                return size
            value = values[i]
            if value == '{':
                i += 1
                while i < size and values[i] != '}':
                    i = statement(i)
                return min(i + 1, size)
            if value in {'if', 'while', 'for', 'foreach', 'switch', 'catch'}:
                head = i + 1
                if head < size and values[head] == '(':
                    end = statement(pairs.get(head, head + 1))
                    if value == 'if' and end < size and values[end] == 'else':
                        return statement(end + 1)
                    return end
            if value == 'do':
                end = statement(i + 1)
                if end + 1 < size and values[end:end + 2] == ['while', '(']:
                    end = pairs.get(end + 1, end + 2)
                    return end + (end < size and values[end] == ';')
                return end
            if value == 'else':
                broken.append(method.body_start + tokens[i].start())
                return statement(i + 1)
            # Labels must not hide the first statement in a switch arm.
            label = value in {'case', 'default'} or (i + 1 < size and values[i + 1] == ':')
            while i < size:
                value = values[i]
                if value in {'(', '[', '{'}:
                    i = pairs.get(i, i + 1)
                elif value == ';' or (label and value == ':'):
                    return i + 1
                elif value in {'}', 'else'}:
                    return i if value == '}' else statement(i)
                else:
                    i += 1
            return size

        broken = []
        statement(0)
        for offset in broken:
            yield _finding('HC-E023', source, offset, _symbol(method), RULES['HC-E023'])


def rule_typename_null(project, source):
    for method in _all_methods(source):
        if method.return_type != 'typename':
            continue
        for match in re.finditer(r'\breturn\s+(?:null|NULL)\s*;', source.body(method)):
            yield _finding('HC-E024', source, method.body_start + match.start(),
                           _symbol(method), RULES['HC-E024'])


def rule_native_named_methods(project, source):
    for definition in source.classes:
        candidates = [m for m in definition.methods
                      if m.name != definition.name and not m.name.startswith('~')
                      and 'override' not in m.modifiers
                      and (m.name in project.symbols or m.name in project.native_globals)]
        if not candidates:
            continue
        called = set()
        for link in project.links.get(definition.name, ()):
            for method in link.methods:
                tokens = [t[0] for t in _TOKENS.finditer(link.source.body(method))]
                for i in range(len(tokens) - 1):
                    if tokens[i + 1] == '(' and (i == 0 or tokens[i - 1] not in {'.', 'new'}):
                        called.add(tokens[i])
        for method in candidates:
            entries = project.symbols.get(method.name, ())
            layers = [e['layer'] for e in entries]
            layers += list(project.native_globals.get(method.name, ()))
            if method.name in called and any(source.layer is None or layer <= source.layer for layer in layers):
                yield _finding('HC-E025', source, method.offset, _symbol(method),
                               f'{method.name}: {RULES["HC-E025"]}', native=True)


def native_global_functions(path, names):
    """Supplement the HC-E012 index with candidate global proto/native names.

    The shared index has no globals field. Prefilter headers before parsing so
    only native files potentially colliding with authored methods need a model.
    Never include class members, ordinary script functions or commented code.
    """
    result = {}
    if not names:
        return result
    header = re.compile(r'\b(?:proto|native)\b[^;{}]*\b('
                        + '|'.join(re.escape(n) for n in sorted(names)) + r')\s*\(')
    for layer in es.LAYERS:
        for file in sorted((Path(path) / layer).rglob('*.c')):
            text = file.read_text(encoding='utf-8', errors='replace')
            if not header.search(text):
                continue
            source = es.Source(file, text)
            for signature in source.signatures:
                if (signature.name in names and signature.modifiers & {'proto', 'native'}
                        and not any(c.body_start < signature.offset < c.body_end for c in source.classes)):
                    result.setdefault(signature.name, set()).add(source.layer)
    return result

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


def load_provider_methods(path=PROVIDER_METHODS):
    """Engine receivers that call a Workshop-provider method outside a bridge.

    Packed providers (Expansion, CF, COT) add methods to engine classes through
    modded bodies we cannot index. Each entry names the exact file, calling
    method, engine receiver type and called method, with a reason; anything
    broader fails closed. These are possible dependency-boundary violations that
    are parked here until a bridge owns the call, not approvals of the pattern.
    """
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema') != 1 or not isinstance(data.get('entries'), list):
        raise ValueError('invalid provider method allowlist')
    entries = set()
    for entry in data['entries']:
        keys = ('path', 'symbol', 'receiver_type', 'method', 'reason')
        if not all(isinstance(entry.get(k), str) and entry[k].strip() for k in keys):
            raise ValueError('provider method exception requires ' + ', '.join(keys))
        entries.add(tuple(entry[k] for k in keys[:4]))
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


def _null_handle_comparisons(code):
    """Read simple member operands, allowing balanced parentheses on either side.

    Calls and compound expressions are not handle variables. An operand may end
    in one balanced [index] (reported as indexed). Keep token offsets so scope
    lookup and diagnostic lines still refer to the original source.
    """
    tokens = list(re.finditer(r'[A-Za-z_]\w*|==|!=|[^\s]', code))

    def skip_index(index, step):
        """Step over one balanced [..] starting at index; None if unbalanced."""
        opening, closing = ('[', ']') if step == 1 else (']', '[')
        depth = 0
        while 0 <= index < len(tokens):
            depth += (tokens[index][0] == opening) - (tokens[index][0] == closing)
            index += step
            if not depth:
                return index
        return None

    def operand(index, step):
        if not 0 <= index < len(tokens):
            return None
        token = tokens[index][0]
        opening, closing = ('(', ')') if step == 1 else (')', '(')
        indexed = False
        if token == opening:
            inner = operand(index + step, step)
            if inner is None:
                return None
            parts, index, indexed = inner
            if not 0 <= index < len(tokens) or tokens[index][0] != closing:
                return None
            index += step
            if indexed:
                return parts, index, indexed
        else:
            if step == -1 and token == ']':
                index = skip_index(index, step)
                if index is None or not 0 <= index < len(tokens):
                    return None
                token, indexed = tokens[index][0], True
            if not re.fullmatch(r'[A-Za-z_]\w*', token):
                return None
            parts, index = [token], index + step
        while 0 <= index < len(tokens) and tokens[index][0] == '.':
            index += step
            if not 0 <= index < len(tokens) or not re.fullmatch(r'[A-Za-z_]\w*', tokens[index][0]):
                return None
            parts.append(tokens[index][0])
            index += step
        if step == 1 and 0 <= index < len(tokens) and tokens[index][0] == '[' and not indexed:
            index = skip_index(index, step)
            if index is None:
                return None
            indexed = True
        return parts, index, indexed

    for index, token in enumerate(tokens):
        if token[0] not in {'==', '!='}:
            continue
        left, right = operand(index - 1, -1), operand(index + 1, 1)
        if left is None or right is None:
            continue
        left_parts, before, left_indexed = left
        right_parts, after, right_indexed = right
        # A closing call/index expression must not become a parenthesised
        # variable; likewise do not accept a prefix of a right-hand call.
        if (before >= 0 and (re.fullmatch(r'[A-Za-z_]\w*', tokens[before][0])
                             and tokens[before][0] not in {'return', 'case'}
                             or tokens[before][0] in {']', ')'})):
            continue
        if after < len(tokens) and tokens[after][0] in {'(', '[', '.'}:
            continue
        if left_parts == ['null'] and not left_indexed:
            parts, indexed = right_parts, right_indexed
        elif right_parts == ['null'] and not right_indexed:
            parts, indexed = list(reversed(left_parts)), left_indexed
        else:
            continue
        start, end = tokens[before + 1].start(), tokens[after - 1].end()
        yield start, code[start:end], parts, indexed


def _grouped_declarators(code, position, end):
    """Yield later names/offsets, skipping balanced, already string-masked initializers."""
    closing = {'(': ')', '[': ']', '{': '}'}
    while position < end:
        while position < end and code[position].isspace():
            position += 1
        # Fixed-size arrays can also participate in grouped declarations.
        while position < end and code[position] == '[':
            depth = 1
            position += 1
            while position < end and depth:
                depth += (code[position] == '[') - (code[position] == ']')
                position += 1
            while position < end and code[position].isspace():
                position += 1
        if position < end and code[position] == '=':
            position += 1
            stack = []
            while position < end:
                ch = code[position]
                if ch in closing:
                    stack.append(closing[ch])
                elif stack and ch == stack[-1]:
                    stack.pop()
                elif not stack and ch in ',;)]}':
                    break
                position += 1
        following = re.match(r',\s*([A-Za-z_]\w*)\s*(?=[,;=\[])', code[position:end])
        if not following:
            return
        yield following[1], position + following.start(1)
        position += following.end()


def _handle_locals(source, method):
    """Extend existing local scopes without changing the shared source model."""
    declarations = source.local_declarations(method)
    bindings = {start: (name, kind, start, end) for name, kind, start, end in declarations}
    for name, kind, start, end in declarations:
        match = _LOCAL.match(source.code, start)
        if match is None or match[2] != name:
            continue
        for grouped, offset in _grouped_declarators(source.code, match.end(), end):
            bindings[offset] = (grouped, kind, offset, end)
    return [bindings[start] for start in sorted(bindings)]


def _is_array_declarator(code, name, offset):
    """True when the declarator `name` at offset is a fixed-size array (name[N])."""
    return code[offset + len(name):].lstrip().startswith('[')


def _handle_nonlocals(source, owner=None, arrays=False):
    """Supplement HC-E016's field/global bindings with grouped declarations.

    With arrays=True a fixed-size array declarator binds `Kind[]` so indexed
    elements can be told from the array itself."""
    start, end = (owner.body_start + 1, owner.body_end) if owner else (0, len(source.code))
    excluded = [(m.offset, m.body_end) for m in source.methods]
    excluded += [(s.offset, s.end) for s in source.signatures]
    if owner is None:
        excluded += [(d.body_start, d.body_end) for d in source.classes]
    bindings = {}
    for match in _LOCAL.finditer(source.code, start, end):
        if any(begin <= match.start() < stop for begin, stop in excluded):
            continue
        kind = match[1]
        if kind in es.MODIFIERS or kind in {'return', 'new', 'delete', 'else', 'case', 'throw'}:
            continue
        suffix = '[]' if arrays and _is_array_declarator(source.code, match[2], match.start(2)) else ''
        bindings[match[2]] = kind + suffix
        for name, offset in _grouped_declarators(source.code, match.end(), end):
            suffix = '[]' if arrays and _is_array_declarator(source.code, name, offset) else ''
            bindings[name] = kind + suffix
    return bindings


def rule_handle_null(project, source):
    methods = list(_all_methods(source))
    # File-scope variables remain visible in functions and member initializers.
    globals_ = _handle_nonlocals(source, arrays=True)
    field_cache = {}

    def fields_for(kind):
        if kind not in field_cache:
            fields = {}
            field_cache[kind] = fields  # Break malformed inheritance cycles.
            bodies = [d for d in project.links.get(kind, ())
                      if source.layer is None or d.source.layer is None or d.source.layer <= source.layer]
            engine = [d for d in project.symbols.get(kind, ())
                      if source.layer is None or d['layer'] <= source.layer]
            # Match receiver_members' inheritance/modded-body order, adding
            # grouped fields at the declaring class so shadowing is preserved.
            parents = [d.base for d in bodies if d.base]
            parents += [d['parent'] for d in engine if d['parent']]
            for parent in parents:
                fields.update(fields_for(parent))
            for definition in engine:
                fields.update(definition['fields'])
            for definition in bodies:
                fields.update({f.name: f.type for f in definition.fields})
                fields.update(_handle_nonlocals(definition.source, definition, arrays=True))
        return field_cache[kind]

    def element_kind(kind):
        """Element type of an array/typedef'd collection kind, else ''."""
        kind = re.sub(r'\s+', '', project.resolve_typedef(re.sub(r'\s+', '', kind)))
        if kind.endswith('[]'):
            return kind[:-2]
        generic = re.fullmatch(r'array<(?:ref|autoptr)?([A-Za-z_]\w*)>', kind)
        return generic[1] if generic else ''

    for offset, comparison, parts, indexed in _null_handle_comparisons(source.code):
        method = next((m for m in methods if m.body_start < offset < m.body_end), None)
        owner = (method.owner if method else
                 next((d for d in source.classes if d.body_start < offset < d.body_end), None))
        fields = fields_for(owner.name) if owner else {}
        parameters = {name: kind for kind, name, _ in method.parameters()} if method else {}
        declarations = _handle_locals(source, method) if method else []
        first = parts.pop(0)
        bindings = [(kind, start, name) for name, kind, start, end in declarations
                    if name == first and start <= offset < end]
        if first == 'this' and owner:
            kind = owner.name
        elif bindings:
            kind, start, name = bindings[-1]
            declared = _LOCAL.match(source.code, start)
            at = declared.start(2) if declared and declared[2] == name else start
            if _is_array_declarator(source.code, name, at):
                kind = re.sub(r'\s+', '', kind) + '[]'
        else:
            kind = parameters.get(first, fields.get(first, globals_.get(first, '')))
            # A bare class name is the receiver of a static member.
            if not kind and parts and first in project.links:
                kind = first
        for member in parts:
            kind = fields_for(project.resolve_typedef(kind)).get(member, '')
        if indexed:
            kind = element_kind(kind)
        elif kind.endswith('[]'):
            # Comparing the array itself is not a handle comparison.
            continue
        # Preserve handle names before typedef expansion to int[]. Follow
        # authored aliases without treating all int arrays as file handles.
        seen = set()
        while kind in project.typedefs and kind not in seen and kind not in {'FileHandle', 'FindFileHandle'}:
            seen.add(kind)
            kind = project.typedefs[kind].strip()
        if kind in {'FileHandle', 'FindFileHandle'}:
            symbol = _symbol(method) if method else (owner.name if owner else '<file>')
            yield _finding('HC-E016', source, offset, symbol,
                           f'{comparison.strip()}: {RULES["HC-E016"]}')


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


# HC-E022 is a dependency boundary, not a naming ban. Declarations, inheritance,
# attributes, enum/field reads and Cast/CastTo remain legal. Calls on an eAI*
# receiver (including HC subclasses, static/generic calls, indexed collections,
# casts and method-result/field chains) must live in the one owned bridge file.
# Authored extensions and super calls to guarded HC overrides are HC APIs.
# PlayerBase group/target ports and ExpansionAI settings/spawn APIs are included.
# Engine observation calls on an explicitly eAI-typed receiver also cross the
# bridge; its lifecycle probes may read corpses without treating them as actors.
_EXPANSION_BRIDGE = 'mods/HollowCountryExpansionAI/scripts/4_World/HCXExpansionBridge.c'
_EXPANSION_RETURNS = {
    'GetGroup': 'eAIGroup', 'GetFaction': 'eAIFaction', 'GetFormation': 'eAIFormation',
    'GetTarget': 'eAITarget', 'GetTargetInformation': 'eAITargetInformation',
    'GetTargetForAI': 'eAITarget', 'AddAI': 'eAITarget',
    'GetMember': 'DayZPlayerImplement', 'GetFormationLeader': 'DayZPlayerImplement',
    'GetLeader': 'DayZPlayerImplement', 'eAI_GetAll': 'array<eAIBase>',
    'GetTargets': 'array<ref eAITarget>',
    'GetExpansionSettings': 'ExpansionSettings',
    'GetAI': 'ExpansionAISettings', 'GetAIPatrol': 'ExpansionAIPatrolSettings',
}
_EXPANSION_PLAYER_PORTS = {'GetGroup', 'SetGroup', 'GetTargetInformation'}


_COT_BRIDGE = 'mods/HollowCountryExpansionAI/scripts/4_World/HCXCotPermissions.c'
_CF_BRIDGE = 'mods/HollowCountryExpansionAI/scripts/4_World/HCXCFBridge.c'
_PROVIDER_BRIDGES = frozenset({_EXPANSION_BRIDGE, _COT_BRIDGE, _CF_BRIDGE})
_DEPENDENCY_GLOBALS = {
    'GetPermissionsManager': ('JMPermissionManager', _COT_BRIDGE),
    'GetRPCManager': ('RPCManager', _CF_BRIDGE),
}
# Public global API name census read from installed COT/CF scripts.pbo.
# Names only: provider sources remain external. Receiver calls use type resolution.
_COT_GLOBALS = frozenset("""ALT ArrayContains COTCreateLocalAdminNotification COTCreateNotification
    COT_CameraRaycast COT_PerformRayCast COT_SurfaceIsWater CTRL CheckStringType
    CreateCustomDefaultCharacter CreateWeapon DeleteFiles FileAttributeToString
    FindFilesInLocation ForceTargetCollisionUpdate FormatFloat GetCOT GetCOTBase
    GetCOTGame GetCOTWebhookSettings GetCOTWindowManager GetChildrenFromBaseClass
    GetCommunityOnlineTools GetCommunityOnlineToolsBase GetCurrentPosition
    GetCursorObject GetCursorPos GetObjectsAt GetPermissionsManager GetPlayer
    GetPlayerObjectByIdentity GetPointerObject GetPointerPos GetRandomChildFromBaseClass
    GetSpawnPoints GetWeaponInHands IsModLoaded JM_GetSelected LoadMag Message SHIFT
    SnapToGround SnapToGroundNew SpawnInfected ToFloat ToSingleDigit ToggleCursor
    VectorToString WINKEY WorkingZombieClasses""".split())
_CF_GLOBALS = frozenset("""Assert_Empty Assert_False Assert_Log Assert_Null Assert_True
    CreateModuleManager DestroyModuleManager GetModuleManager GetRPCManager GetXMLApi
    IsMissionClient IsMissionHost IsMissionOffline ModuleManagerExists""".split())
_CF_LEGACY_TYPES = frozenset("""JMAnimRegister JMModuleBase JMModuleBinding
    JMModuleConstructor JMModuleConstructorBase JMModuleManager JMModuleManagerBase
    JM_CommunityFramework JMDate""".split())
_DEPENDENCY_GLOBALS.update({name: (kind, _COT_BRIDGE) for name, kind in (
    ('GetCOT', 'CommunityOnlineTools'), ('GetCommunityOnlineTools', 'CommunityOnlineTools'),
    ('GetCOTBase', 'CommunityOnlineToolsBase'), ('GetCommunityOnlineToolsBase', 'CommunityOnlineToolsBase'),
    ('GetCOTGame', 'CommunityOnlineToolsGame'), ('GetCOTWindowManager', 'JMWindowManager'),
    ('GetCOTWebhookSettings', 'JMWebhookSerialize'))})
_DEPENDENCY_GLOBALS.update({
    'GetXMLApi': ('CF_XML', _CF_BRIDGE), 'GetModuleManager': ('JMModuleManager', _CF_BRIDGE)})
_DEPENDENCY_RETURNS = {
    ('JMPermissionManager', 'GetPlayer'): 'JMPlayerInstance',
    **{('CF_Date', name): 'CF_Date' for name in
       ('Now', 'Epoch', 'CreateDate', 'CreateTime', 'CreateDateTime')},
    ('CF_ModuleCoreManager', 'Get'): 'CF_ModuleCore',
    ('CF_ModuleCoreManager', 'GetModule'): 'CF_ModuleCore',
}


def _dependency_bridge(project, kind):
    for ancestor in project.lineage(project.resolve_typedef(kind)):
        if ancestor == 'ExpansionStatic':
            return _EXPANSION_BRIDGE
        if ancestor in _CF_LEGACY_TYPES:
            return _CF_BRIDGE
        if ancestor.startswith(('JM', 'COT', 'CommunityOnlineTools')):
            return _COT_BRIDGE
        if ancestor.startswith('CF_') or ancestor in {'RPCManager', 'ScriptRPCManager'}:
            return _CF_BRIDGE
    return ''


def expansion_calls(project, source, dependencies=False):
    """Yield (method, receiver start, dot offset, call name, receiver type).

    Resolve explicit declarations and authored return types, never runtime
    subtypes. A small API-only return census covers provider result chains when
    Workshop sources are unavailable. No provider implementation is inspected.
    """
    def lineage(kind):
        return project.lineage(project.resolve_typedef(kind))

    def fields_for(kind):
        fields = dict(project.receiver_members(kind, source.layer)[1])
        if dependencies:
            if not hasattr(project, '_dependency_field_bindings'):
                project._dependency_field_bindings = {}
            key = kind, source.layer
            if key not in project._dependency_field_bindings:
                grouped = {}
                for ancestor in reversed(lineage(kind)):
                    for definition in project.links.get(ancestor, ()):
                        grouped.update(_handle_nonlocals(definition.source, definition))
                project._dependency_field_bindings[key] = grouped
            fields.update(project._dependency_field_bindings[key])
        return fields

    def field_type(kind, name):
        fields = fields_for(kind)
        if name in fields:
            return fields[name]
        # Public provider field signatures used by the owned patrol subclass.
        # Keep these resolvable without installing or copying Workshop sources.
        if 'eAIDynamicPatrol' in lineage(kind):
            return {'m_Group': 'eAIGroup', 'm_Faction': 'eAIFaction',
                    'm_Formation': 'eAIFormation',
                    'm_Config': 'ExpansionAIDynamicSpawnBase'}.get(name, '')
        return ''

    def authored_port(kind, name, receiver):
        for ancestor in lineage(kind):
            for definition in project.links.get(ancestor, ()):
                for candidate in definition.methods:
                    if candidate.name != name:
                        continue
                    if 'override' not in candidate.modifiers:
                        return True
                    if (receiver == 'super' and not definition.name.startswith('eAI')
                            and not (dependencies and _dependency_bridge(project, definition.name))):
                        return True
        return False

    def dependency_element(kind):
        collection = re.fullmatch(r'(array|set|map)<(.+)>', kind)
        if not collection:
            return ''
        element = collection[2]
        if collection[1] == 'map':
            _, separator, element = element.partition(',')
            if not separator:
                return ''
        return re.sub(r'^ref', '', element)

    def result_type(kind, name):
        if dependencies and name in {'Get', 'GetElement', 'GetIteratorElement'}:
            element = dependency_element(kind)
            if element:
                return element
        if name == 'Get':
            element = re.fullmatch(r'(?:array|set)<(?:ref)?(.+)>', kind)
            if element:
                return element[1]
        if name in {'Cast', 'CastTo'}:
            return kind
        for ancestor in lineage(kind):
            for definition in project.links.get(ancestor, ()):
                for candidate in definition.methods:
                    if candidate.name == name:
                        return candidate.return_type
        if dependencies:
            for ancestor in lineage(kind):
                if (ancestor, name) in _DEPENDENCY_RETURNS:
                    return _DEPENDENCY_RETURNS[ancestor, name]
            if name in _DEPENDENCY_GLOBALS:
                return _DEPENDENCY_GLOBALS[name][0]
        return _EXPANSION_RETURNS.get(name, '')

    methods = list(_all_methods(source))
    global_bindings = {}
    if dependencies:
        if not hasattr(project, '_dependency_global_bindings'):
            project._dependency_global_bindings = [
                (item.layer, _handle_nonlocals(item)) for item in project.sources]
        for layer, values in project._dependency_global_bindings:
            if layer is None or source.layer is None or layer <= source.layer:
                global_bindings.update(values)
        excluded = [(d.offset, d.body_end) for d in source.classes]
        excluded += [(m.offset, m.body_end) for m in methods]
        for match in re.finditer(r'=([^;{}]+);', source.code):
            if not any(begin <= match.start() <= end for begin, end in excluded):
                methods.append(es.Method('<initializer>', '', frozenset(), '',
                                         match.start(), match.start(1), match.end(1), None))
    for definition in source.classes:
        for field in definition.fields:
            if not field.initializer:
                continue
            end = source.code.find(';', field.offset, definition.body_end)
            begin = source.code.find('=', field.offset, end)
            if begin >= 0:
                methods.append(es.Method('<initializer>', field.type, frozenset(), '',
                                         field.offset, begin, end, definition))
    for method in methods:
        owner = method.owner
        bindings = dict(global_bindings)
        if owner:
            bindings.update(fields_for(owner.name))
        if owner:
            bindings.update(this=owner.name, super=owner.base or owner.name)
        if dependencies:
            bindings.update(_Ownership.parameters(method))
        else:
            bindings.update({name: kind for kind, name, _ in method.parameters()})
        declarations = source.local_declarations(method)

        def head_token(end, generic=False):
            while end > method.body_start and source.code[end - 1].isspace():
                end -= 1
            start = end
            if generic and source.code[start - 1:start] == '>':
                depth = 1
                start -= 2
                while start >= method.body_start and depth:
                    if source.code[start] == '>':
                        depth += 1
                    elif source.code[start] == '<':
                        depth -= 1
                    start -= 1
                start += 1
            while start > method.body_start and (source.code[start - 1].isalnum() or source.code[start - 1] == '_'):
                start -= 1
            return source.code[start:end], start

        def expression(end):
            while end > method.body_start and source.code[end - 1].isspace():
                end -= 1
            final = source.code[end - 1:end]
            if final in {')', ']'}:
                closing, opening = final, {')': '(', ']': '['}[final]
                depth, cursor = 1, end - 2
                while cursor >= method.body_start and depth:
                    char = source.code[cursor]
                    if char == closing:
                        depth += 1
                    elif char == opening:
                        depth -= 1
                    cursor -= 1
                if depth:
                    return '', end
                if final == ']':
                    kind, start = expression(cursor + 1)
                    if dependencies:
                        return dependency_element(kind), start
                    element = re.fullmatch(r'(?:array|set)<(?:ref)?(.+)>', kind)
                    return (element[1] if element else ''), start
                name, head_start = head_token(cursor + 1)
                if not name:  # parenthesized receiver: (actor).Call()
                    kind, _ = expression(end - 1)
                    return kind, cursor + 1
                before = head_start
                while before and source.code[before - 1].isspace():
                    before -= 1
                if source.code[before - 1:before] == '.':
                    kind, start = expression(before - 1)
                    return result_type(kind, name), start
                return result_type(owner.name if owner else '', name), head_start
            name, start = head_token(end, generic=True)
            if not name:
                return '', end
            before = start
            while before and source.code[before - 1].isspace():
                before -= 1
            if source.code[before - 1:before] == '.':
                kind, start = expression(before - 1)
                return field_type(kind, name), start
            locals_ = [(kind, begin) for local, kind, begin, finish in declarations
                       if local == name and begin <= start < finish]
            kind = locals_[-1][0] if locals_ else bindings.get(name, name)
            if kind == 'auto':
                begin = locals_[-1][1]
                semi = source.code.find(';', begin, start)
                if semi >= 0 and '=' in source.code[begin:semi]:
                    kind, _ = expression(semi)
            return project.resolve_typedef(re.sub(r'\s+', '', kind)), start

        for call in re.finditer(r'\.\s*(\w+)\s*\(', source.body(method)):
            name = call[1]
            if name in {'Cast', 'CastTo'}:
                continue
            dot = method.body_start + call.start()
            kind, start = expression(dot)
            if authored_port(kind, name, source.code[start:dot].strip()):
                continue
            is_expansion = any(t.startswith(('eAI', 'ExpansionAI')) for t in lineage(kind))
            player_port = (name in _EXPANSION_PLAYER_PORTS or name.startswith('Expansion_')) and any(
                t in {'PlayerBase', 'DayZPlayer', 'DayZPlayerImplement'} for t in lineage(kind))
            settings_port = kind == 'ExpansionSettings' and name in {'GetAI', 'GetAIPatrol'}
            guarded = bool(_dependency_bridge(project, kind)) if dependencies else (
                is_expansion or player_port or settings_port or name.startswith('eAI_'))
            if guarded:
                yield method, start, dot, name, kind
        # An unqualified call inside a provider subclass is a receiver call too.
        # Global builtins and authored functions are not dependency methods.
        provider_owner = owner and (bool(_dependency_bridge(project, owner.name)) if dependencies
                                    else any(t.startswith('eAI') for t in lineage(owner.name)))
        if provider_owner:
            globals_ = {'GetGame', 'Print', 'PrintFormat', 'Error', 'ErrorEx', 'Vector'}
            globals_.update(function.name for item in project.sources for function in item.functions)
            for call in _CALL.finditer(source.body(method)):
                name = call[2]
                if call[1] or name in _KEYWORDS or name in globals_:
                    continue
                if authored_port(owner.name, name, 'this'):
                    continue
                if name in project.links or name in project.native_names:
                    continue  # constructor, not a method invocation
                offset = method.body_start + call.start(2)
                yield method, offset, offset, name, owner.name


def rule_expansion_bridge(project, source):
    if source.rel == _EXPANSION_BRIDGE:
        return
    covered = set()
    for method, start, dot, name, kind in expansion_calls(project, source):
        covered.add(dot)
        receiver = source.text[start:dot].strip() or 'this'
        yield _finding('HC-E022', source, dot, _symbol(method),
                       f'{receiver}.{name} ({kind}): call HCXExpansionBridge; '
                       'direct Expansion AI calls bypass invariant validation',
                       key=f'{_symbol(method)}:{receiver}.{name}')

    # Static calls can also occur in field/global initializers, outside methods.
    static_call = re.compile(r'\b((?:eAI|ExpansionAI)\w*(?:<[^;{}()]+>)?)\s*(\.)\s*(\w+)\s*\(')
    for call in static_call.finditer(source.code):
        if call.start(2) in covered or call[3] in {'Cast', 'CastTo'}:
            continue
        if any(method.body_start <= call.start() <= method.body_end
               for method in _all_methods(source)):
            continue
        yield _finding('HC-E022', source, call.start(2), '<initializer>',
                       f'{call[1]}.{call[3]}: call HCXExpansionBridge; '
                       'direct Expansion AI calls bypass invariant validation',
                       key=f'{call[1]}.{call[3]}')


def rule_dependency_bridges(project, source):
    covered = set()
    for method, start, dot, name, kind in expansion_calls(project, source, dependencies=True):
        covered.add(dot)
        bridge = _dependency_bridge(project, kind)
        if source.rel == bridge:
            continue
        receiver = source.code[start:dot].strip() or 'this'
        yield _finding('HC-E027', source, dot, _symbol(method),
                       f'{receiver}.{name} ({kind}): call {Path(bridge).stem}; '
                       'direct dependency calls bypass invariant validation',
                       key=f'{_symbol(method)}:{receiver}.{name}')

    # Global APIs and static/global initializers have no declared receiver.
    # clean code excludes comments and strings; bare-call matching excludes
    # declarations by inspecting only method bodies or initializer expressions.
    spans = [(m.body_start, m.body_end, _symbol(m), m.owner) for m in _all_methods(source)]
    for match in re.finditer(r'=([^;{}]+);', source.code):
        if not any(begin <= match.start() <= end for begin, end, _, _ in spans):
            owner = next((d for d in source.classes if d.body_start < match.start() < d.body_end), None)
            spans.append((match.start(1), match.end(1), '<initializer>', owner))
    for begin, end, symbol, owner in spans:
        code = source.code[begin:end]
        for call in _CALL.finditer(code):
            if call[1] or code[:call.start(2)].rstrip().endswith('.'):
                continue
            if begin + call.start(2) in covered:
                continue
            # Bare calls resolve against visible authored/native members first.
            if owner and call[2] in project.receiver_members(owner.name, source.layer)[0]:
                continue
            if any(function.name == call[2]
                   for item in project.sources
                   if item.layer is None or source.layer is None or item.layer <= source.layer
                   for function in item.functions):
                continue
            if any(source.layer is None or layer <= source.layer
                   for layer in project.native_globals.get(call[2], ())):
                continue
            # Resolve typedefs and legacy CF names before vendor prefix/global rules.
            bridge = _dependency_bridge(project, call[2])
            if not bridge and call[2] in _COT_GLOBALS:
                bridge = _COT_BRIDGE
            elif not bridge and call[2] in _CF_GLOBALS:
                bridge = _CF_BRIDGE
            kind, bridge = _DEPENDENCY_GLOBALS.get(call[2], (call[2], bridge))
            if not bridge:
                continue
            if source.rel != bridge:
                yield _finding('HC-E027', source, begin + call.start(2), symbol,
                               f'{call[2]} ({kind}): call {Path(bridge).stem}',
                               key=f'{symbol}:{call[2]}')



class _Ownership:
    """Declared receiver resolution and conservative, cycle-safe factory summaries.

    No method-name-only factory inference: ambiguous overloads/modded bodies must
    agree. Native calls and borrowed member returns never establish freshness.
    """

    def __init__(self, project):
        self.project = project
        self.cache = {}
        self.sources = {id(m): item for item in project.sources for m in _all_methods(item)}
        self.declarations = {}
        self.initializers = []

    def locals(self, method):
        key = id(method)
        if key not in self.declarations:
            self.declarations[key] = self.sources[key].local_declarations(method)
        return self.declarations[key]

    @staticmethod
    def parameters(method):
        # Parameter commas inside generic types do not separate parameters.
        parts, start, depth = [], 0, 0
        for index, char in enumerate(method.params):
            depth += (char == '<') - (char == '>')
            if char == ',' and depth == 0:
                parts.append(method.params[start:index])
                start = index + 1
        parts.append(method.params[start:])
        bindings = {}
        for part in parts:
            match = re.fullmatch(r'(?:(?:out|inout|ref|notnull|const)\s+)*(.+?)\s+(\w+)',
                                 part.split('=')[0].strip())
            if match:
                bindings[match[2]] = match[1]
        return bindings

    def kind(self, text):
        return self.project.resolve_typedef(re.sub(r'\s+', '', text))

    def reference(self, kind):
        return bool(re.match(r'^(array|map|set)<', kind) or kind in self.project.links)

    def receiver(self, expression, method, offset):
        expression = expression.strip()
        if expression.startswith('(') and es.matching_paren(expression, 0) == len(expression) - 1:
            return self.receiver(expression[1:-1], method, offset)
        call = self.call(expression, method, offset)
        if call:
            candidates, _, _ = call
            kinds = {self.kind(m.return_type) for m in candidates}
            return kinds.pop() if len(kinds) == 1 else ''
        parts = es.split_top(expression, '.')
        first = parts.pop(0).strip()
        source = self.sources[id(method)]
        fields = self.project.receiver_members(method.owner.name, source.layer)[1] if method.owner else {}
        bindings = dict(fields)
        if method.owner:
            bindings.update(this=method.owner.name, super=method.owner.base)
        bindings.update(self.parameters(method))
        bindings.update({name: kind for name, kind, start, end in self.locals(method)
                         if start <= offset < end})
        kind = bindings.get(first, first if first in self.project.links else '')
        for member in parts:
            kind = self.project.receiver_members(self.kind(kind), source.layer)[1].get(member.strip(), '')
        return self.kind(kind)

    def call(self, expression, method, offset):
        expression = expression.strip()
        if expression.startswith('(') and es.matching_paren(expression, 0) == len(expression) - 1:
            return self.call(expression[1:-1], method, offset)
        # Find the opening paren paired with the final close, allowing receivers
        # such as Holder.Get().Factory(). Operators are not complete calls.
        if not expression.endswith(')'):
            return None
        depth, opening = 0, None
        for index in range(len(expression) - 1, -1, -1):
            if expression[index] == ')':
                depth += 1
            elif expression[index] == '(':
                depth -= 1
                if depth == 0:
                    opening = index
                    break
        if opening is None:
            return None
        head = es.split_top(expression[:opening], '.')
        name = head.pop().strip()
        if not re.fullmatch(r'[A-Za-z_]\w*', name) or name in _KEYWORDS:
            return None
        if head and any(re.search(r'[+*/!<>=&|?:]', part) for part in head):
            return None
        kind = (self.receiver('.'.join(head), method, offset) if head
                else method.owner.name if method.owner else '')
        source = self.sources[id(method)]
        candidates = []
        for ancestor in self.project.lineage(kind):
            candidates = [m for d in self.project.links.get(ancestor, ())
                          if source.layer is None or d.source.layer is None or d.source.layer <= source.layer
                          for m in d.methods if m.name == name]
            if candidates:
                break
        if not head and not candidates:
            candidates = [m for item in self.project.sources for m in item.functions if m.name == name]
        return candidates, kind, name

    def passed_as_output(self, name, body):
        # Unknown calls may bind an out argument. Do not infer ownership through
        # them merely because an earlier assignment borrowed retained storage.
        for match in _ANY_CALL.finditer(body):
            if match[1] in _KEYWORDS:
                continue
            opening = body.find('(', match.start())
            closing = es.matching_paren(body, opening)
            for index, argument in enumerate(es.split_top(body[opening + 1:closing], ',')):
                if argument.strip() != name:
                    continue
                candidates = self.project.methods.get(match[1], ())
                if not candidates or any(len(m.parameters()) <= index or m.parameters()[index][2]
                                         for m in candidates):
                    return True
        return False

    def borrowed_expression(self, value, method, offset, seen=frozenset()):
        """Prove an alias to retained storage; temporaries and unknown calls stay unknown."""
        value = value.strip()
        source = self.sources[id(method)]
        body = source.body(method)
        # A cast preserves ownership; collection Get aliases an existing slot.
        cast = re.fullmatch(r'\w+\.Cast\((.*)\)', value, re.S)
        if cast:
            return self.borrowed_expression(cast[1], method, offset, seen)
        call = self.call(value, method, offset)
        if call:
            # Installed 1.30: PlayerBase.c GetItemInHands delegates to
            # GetEntityInHands; EntityAI.c FindAttachmentBySlotName delegates to
            # inventory.FindAttachment. Both return inventory-owned entities.
            # An authored override must still be summarized, never allowlisted.
            inventory_getters = {'PlayerBase': {'GetItemInHands', 'FindAttachmentBySlotName'},
                                 'EntityAI': {'FindAttachmentBySlotName'}}
            if not call[0] and call[2] in inventory_getters.get(call[1], set()):
                return True
            opening = value.rfind('(')
            head = es.split_top(value[:opening], '.')
            if call[2] == 'Get' and len(head) > 1 and re.match(r'^(array|map|set)<', call[1]):
                return self.borrowed_expression('.'.join(head[:-1]), method, offset, seen)
            return False
        # Indexing/member access cannot allocate. Its root must itself be retained.
        chain = re.fullmatch(r'(\w+)((?:\.\w+|\[[^\[\]]+\])*)', value)
        if not chain:
            return False
        root = chain[1]
        if root in seen:
            return False
        locals_ = [d for d in self.locals(method) if d[0] == root and d[2] <= offset < d[3]]
        if locals_:
            if self.passed_as_output(root, body):
                return False
            declaration = locals_[-1]
            writes = list(re.finditer(r'(?<![\w.])' + re.escape(root) + r'\s*=(?!=)\s*([^;]+);', body))
            if writes:
                return all(self.borrowed_expression(w[1], method, method.body_start + w.start(),
                                                    seen | {root}) for w in writes)
            # A foreach variable aliases its iterable, never a newly allocated value.
            prefix = source.code[method.body_start:declaration[2]]
            if re.search(r'foreach\s*\(\s*$', prefix):
                header = source.code[declaration[2]:]
                match = re.match(r'[^:;{}]+:\s*([^;{}]+?)\)', header)
                if match:
                    return self.borrowed_expression(match[1], method, declaration[2], seen | {root})
            return False  # out-parameter initialization is not a borrowed value
        parameters = self.parameters(method)
        if root in parameters:
            if self.passed_as_output(root, body):
                return False
            writes = list(re.finditer(r'(?<![\w.])' + re.escape(root) + r'\s*=(?!=)\s*([^;]+);', body))
            return all(self.borrowed_expression(w[1], method, method.body_start + w.start(),
                                                seen | {root}) for w in writes)
        fields = self.project.receiver_members(method.owner.name, source.layer)[1] if method.owner else {}
        if root in fields or root == 'this':
            return True
        # Installed 1.30 PluginRecipesManager.c:42 owns ref array<ref RecipeBase>.
        # Preserve this exact native-field fact when CI has no extracted scripts.
        if method.owner and method.owner.name == 'PluginRecipesManager' and root == 'm_RecipeList':
            return True
        # A qualified static member is retained by its class.
        parts = es.split_top(value, '.')
        return (len(parts) > 1 and root in self.project.links
                and parts[1].split('[')[0] in self.project.receiver_members(root, source.layer)[1])

    def summary(self, method, visiting=frozenset()):
        key = id(method)
        if key in self.cache:
            return self.cache[key]
        if key in visiting:
            return 'unresolved'
        kind = self.kind(method.return_type)
        if not self.reference(kind):
            return 'borrowed'
        source = self.sources[id(method)]
        body = source.body(method)
        states = []
        for returned in re.finditer(r'\breturn\s+([^;]+);', body):
            value = returned[1].strip()
            offset = method.body_start + returned.start()
            if value == 'null':
                continue
            if re.match(r'^new\s+', value):
                states.append('fresh')
                continue
            if self.borrowed_expression(value, method, offset):
                states.append('borrowed')
                continue
            if re.fullmatch(r'\w+', value):
                locals_ = [d for d in self.locals(method)
                           if d[0] == value and d[2] <= offset < d[3]]
                if not locals_:
                    states.append('borrowed')
                    continue
                # Every write must be an allocation; mixed aliases stay unknown.
                writes = list(re.finditer(r'\b' + re.escape(value) + r'\s*=(?!=)\s*([^;]+);', body))
                states.append('fresh' if writes and all(re.match(r'new\s+', w[1]) for w in writes)
                              else 'unresolved')
                continue
            call = self.call(value, method, offset)
            states.append(self.calls_state(call, visiting | {key}) if call else 'unresolved')
        result = ('fresh' if states and all(s == 'fresh' for s in states)
                  else 'borrowed' if not states or all(s == 'borrowed' for s in states)
                  else 'unresolved')
        self.cache[key] = result
        return result

    def calls_state(self, call, visiting=frozenset()):
        if not call or not call[0]:
            return 'unresolved'
        states = {self.summary(m, visiting) for m in call[0]}
        return states.pop() if len(states) == 1 else 'unresolved'


def rule_fresh_arguments(project, source):
    ownership = getattr(project, '_ownership', None)
    if ownership is None:
        ownership = project._ownership = _Ownership(project)
    methods = list(_all_methods(source))
    for definition in source.classes:
        for field in definition.fields:
            if not field.initializer:
                continue
            end = source.code.find(';', field.offset, definition.body_end)
            begin = source.code.find('=', field.offset, end)
            if begin >= 0:
                method = es.Method('<initializer:' + field.name + '>', field.type, frozenset(), '',
                                   field.offset, begin + 1, end - 1, definition)
                ownership.sources[id(method)] = source
                ownership.initializers.append(method)
                methods.append(method)
    for method in methods:
        body = source.body(method)

        def receiver_start(end):
            cursor = end - 1
            while cursor >= 0 and body[cursor].isspace():
                cursor -= 1
            if cursor >= 0 and body[cursor] in ')]':
                closing = body[cursor]
                opening_char = '(' if closing == ')' else '['
                depth = 1
                cursor -= 1
                while cursor >= 0 and depth:
                    if body[cursor] == closing:
                        depth += 1
                    elif body[cursor] == opening_char:
                        depth -= 1
                    cursor -= 1
            while cursor >= 0 and body[cursor].isspace():
                cursor -= 1
            while cursor >= 0 and (body[cursor].isalnum() or body[cursor] == '_'):
                cursor -= 1
            before = cursor
            while before >= 0 and body[before].isspace():
                before -= 1
            return receiver_start(before) if before >= 0 and body[before] == '.' else cursor + 1

        for match in _ANY_CALL.finditer(body):
            start = receiver_start(match.start(1) + len(match[1]))
            opening = match.end() - 1
            closing = es.matching_paren(body, opening)
            offset = method.body_start + start
            outer = ownership.call(body[start:closing + 1], method, offset)
            if not outer:
                continue
            candidates, receiver, name = outer
            # Native collection adoption only; a user-defined Insert is a call.
            adopted = set()
            collection = re.fullmatch(r'(array|map|set)<(.+)>', receiver)
            if collection and not candidates and name in {'Insert', 'InsertAt'}:
                # Map Insert owns both declared slots; array/set InsertAt owns
                # slot zero only (the second parameter is an integer index).
                slots, depth, begin = [], 0, 0
                for position, char in enumerate(collection[2]):
                    depth += (char == '<') - (char == '>')
                    if char == ',' and depth == 0:
                        slots.append(collection[2][begin:position])
                        begin = position + 1
                slots.append(collection[2][begin:])
                if collection[1] != 'map' or name == 'Insert':
                    adopted = {i for i, slot in enumerate(slots) if slot.startswith('ref')}
            fresh, unknown = [], []
            for index, argument in enumerate(es.split_top(body[opening + 1:closing], ',')):
                call = ownership.call(argument, method, offset)
                if not call:
                    continue
                if not call[0]:
                    # Only authored HC candidates belong to this ownership check;
                    # native/provider return ownership is outside this model.
                    if not call[1] and any(m.owner and m.owner.name.startswith('HC')
                                          and ownership.reference(ownership.kind(m.return_type))
                                          for m in project.methods.get(call[2], ())):
                        unknown.append(index)
                    continue
                if not any(ownership.reference(ownership.kind(m.return_type)) for m in call[0]):
                    continue
                state = ownership.calls_state(call)
                if state == 'fresh' and index not in adopted:
                    kinds = {ownership.kind(m.return_type) for m in call[0]}
                    fresh.append((index, all(re.match(r'^(array|map|set)<', k) for k in kinds)))
                elif state == 'unresolved':
                    unknown.append(index)
            call_key = re.sub(r'\s+', ' ', source.text[offset:method.body_start + closing + 1]).strip()
            severity = 'error' if sum(collection for _, collection in fresh) >= 2 else 'warning'
            for index, _ in fresh:
                finding = _finding('HC-E026', source, offset, _symbol(method), RULES['HC-E026'],
                                   key=f'{call_key} [argument {index + 1}]')
                yield Finding(**dict(asdict(finding), severity=severity))
            for index in unknown:
                finding = _finding('HC-O026', source, offset, _symbol(method), RULES['HC-O026'],
                                   key=f'{call_key} [argument {index + 1}]')
                yield Finding(**dict(asdict(finding), severity='warning'))


def rule_receiver_methods(project, source):
    """Resolve explicit typed receivers; no cast, return-type or auto inference.

    Receivers typed with our own classes, and (with a real native-scripts cache)
    engine classes, are checked. Ancestors may be engine classes. Field chains
    retain declared types, never the runtime subtype. Incomplete ancestor
    chains and generic specializations are skipped.

    Packed providers add methods to engine classes through modded bodies that
    cannot be indexed. Engine receivers are therefore not judged inside the
    dependency bridges (the only files allowed to call provider APIs); a call
    elsewhere needs an exact, reasoned entry in enforce_lint_provider_methods.json.
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
            engine_kind = kind in project.symbols and kind not in project.types
            if engine_kind:
                if not project.engine_receivers or source.rel in _PROVIDER_BRIDGES:
                    continue
            elif kind not in project.types or kind not in project.links:
                continue
            if '<' in kind:
                continue
            layers = project.types.get(kind, set()) - {None}
            if layers and source.layer is not None and min(layers) > source.layer:
                continue  # E013 owns invisible receiver types
            methods, _, complete = project.receiver_members(kind, source.layer)
            if (complete and call[2] not in methods
                    and (source.rel, _symbol(method), kind, call[2]) not in project.provider_methods):
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


_VARIABLE_DECLARATION = re.compile(
    r'(?:^|[;{}(,:])\s*(?:(?:ref|autoptr|static|protected|private|const|out|inout|owned|notnull)\s+)*'
    r'(?P<type>[A-Za-z_]\w*(?:\s*<[^;(){}=]+>)?)\s+'
    r'(?P<name>[A-Za-z_]\w*)\s*(?=[=;\[,:)])', re.M)


def rule_type_named_variables(project, source):
    """#306: Slot (World) and World (Game) are legal types, illegal binding names.

    Scan declaration boundaries, including prototypes and loop headers. Do not
    treat return expressions, member accesses, comments or strings as bindings.
    The native census includes typedefs/enums as well as class names.
    """
    visible = project.visible_types(source.layer)
    seen = set()
    for match in _VARIABLE_DECLARATION.finditer(source.code):
        if match['type'] in _KEYWORDS - es.PRIMITIVES - {'array', 'map', 'set'}:
            continue
        declarations = [(match['name'], match.start('name'))]
        declarations.extend(_grouped_declarators(source.code, match.end('name'), len(source.code)))
        for name, offset in declarations:
            if name not in visible or offset in seen:
                continue
            seen.add(offset)
            owner = next((c.name for c in source.classes if c.body_start < offset < c.body_end), '<file>')
            authored = name in project.types and any(
                layer is not None and (source.layer is None or layer <= source.layer)
                for layer in project.types[name])
            yield _finding('HC-E018', source, offset, f'{owner}.{name}',
                           f'{name}: {RULES["HC-E018"]}; rename the binding',
                           native=not authored and name not in PINNED_TYPES)


def _script_file_order(source):
    # mod_sources and the native d4a956d2 rename use the full script-relative
    # path, case-insensitively, rather than basename or caller input order.
    parts = source.path.parts
    path = '/'.join(parts[parts.index('scripts') + 1:]) if 'scripts' in parts else source.rel
    return path.lower(), path


def rule_modded_field_order(project, source):
    """#306/d4a956d2: earlier same-addon/module layers cannot see later fields.

    An ordinary base, ancestor, native declaration or earlier layer with the
    same field prevents this diagnostic. Other addons are outside this rule's
    ordering contract. Explicit this/super accesses must not bind to locals.
    """
    for definition in source.classes:
        if not definition.modded:
            continue
        links = project.links[definition.name]
        chain = sorted((d for d in links if d.modded
                        and d.source.layer == source.layer
                        and _mod_name(d.source) == _mod_name(source)),
                       key=lambda d: (_script_file_order(d.source), d.offset))
        index = next(i for i, d in enumerate(chain) if d is definition)
        later = {name: d.source.rel for d in reversed(chain[index + 1:])
                 for name in project.field_names(d)}
        if not later:
            continue
        earlier = {id(d) for d in chain[:index + 1]}
        known = {name for d in links if not d.modded or id(d) in earlier
                 or (d.source.layer is not None and source.layer is not None and d.source.layer < source.layer)
                 or _mod_name(d.source) != _mod_name(source) for name in project.field_names(d)}
        # Native parents may have no authored body. Follow both native and
        # authored ancestry, with a cycle guard, without merging higher layers.
        pending, visited = [definition.name], set()
        while pending:
            name = pending.pop()
            if name in visited:
                continue
            visited.add(name)
            if name != definition.name:
                known.update(project.receiver_members(name, source.layer)[1])
                for parent in project.links.get(name, ()):
                    if source.layer is None or parent.source.layer is None or parent.source.layer <= source.layer:
                        known.update(project.field_names(parent))
            for body in project.symbols.get(name, ()):
                if source.layer is None or body['layer'] <= source.layer:
                    known.update(body['fields'])
                    if body['parent']:
                        pending.append(body['parent'])
            pending.extend(d.base for d in project.links.get(name, ()) if d.base)
        later = {name: path for name, path in later.items() if name not in known}
        if not later:
            continue
        pattern = re.compile(r'\b(?:' + '|'.join(map(re.escape, sorted(later))) + r')\b')
        # Inspect all field initializers, including grouped declarations that
        # do not have individual Field records in the structural model.
        regions, position = [], definition.body_start + 1
        bodies = {m.offset: m.body_end + 1 for m in definition.methods}
        for signature in source.class_signatures(definition):
            stop = source.header_start(signature)
            regions.append((position, source.code[position:stop], None))
            position = bodies.get(signature.offset, signature.end)
        regions.append((position, source.code[position:definition.body_end], None))
        regions.extend((m.body_start, source.body(m), m) for m in definition.methods)
        for start, body, method in regions:
            matches = list(pattern.finditer(body))
            if not matches:
                continue
            locals_ = _handle_locals(source, method) if method else []
            parameters = {n for _, n, _ in method.parameters()} if method else set()
            for match in matches:
                name, offset = match[0], start + match.start()
                prefix = body[:match.start()]
                dotted = re.search(r'\.\s*$', prefix)
                if dotted:
                    receiver = re.search(r'(?<![\w.])(?:this|super|' + re.escape(definition.name)
                                         + r')\s*\.\s*$', prefix)
                    if not receiver or re.search(r'\.\s*$', prefix[:receiver.start()]):
                        continue
                elif name in parameters or any(n == name and begin <= offset < end
                                                for n, _, begin, end in locals_):
                    continue
                yield _finding('HC-E019', source, offset,
                               _symbol(method) if method else f'{definition.name}.{name}',
                               f'{name} is declared only by later modded {definition.name} file '
                               f'{later[name]}; load its declaring layer first')



# ---------------------------------------------------------------- log lines

_BARE_PRINT = re.compile(r'(?<![\w.])Print\s*\(\s*(?!(?:true|false|null)\s*\))([A-Za-z_]\w*)\s*\)')


def rule_stored_handles(project, source):
    for row in _handles.stored_handles(source):
        yield _finding(row.rule, source, row.offset, row.symbol, row.message, key=row.key)


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


# ---------------------------------------------------------------- native API shape rules (wave C, C10)

def _ownership(project):
    ownership = getattr(project, '_ownership', None)
    if ownership is None:
        ownership = project._ownership = _Ownership(project)
    return ownership


def _named_calls(source, method, names):
    """Yield (absolute offset of the name, name, receiver text, [arguments], absolute '(' offset).

    The receiver is the dotted chain before the name (one level of call parentheses
    per link). Arguments are split at top level on the masked code.
    """
    body = source.body(method)
    pattern = re.compile(r'(?<![\w.])((?:[A-Za-z_]\w*(?:\s*\((?:[^()]|\([^()]*\))*\))?\s*\.\s*)*)(' + names + r')\s*\(')
    for match in pattern.finditer(body):
        opening = match.end() - 1
        closing = es.matching_paren(body, opening)
        arguments = [argument.strip() for argument in es.split_top(body[opening + 1:closing], ',')]
        receiver = re.sub(r'\s*\.\s*$', '', match[1]).strip()
        yield (method.body_start + match.start(2), match[2], receiver, arguments, method.body_start + opening)


def _bare_name(expression):
    expression = re.sub(r'\s+', '', expression)
    if expression.startswith('this.'):
        expression = expression[5:]
    return expression if re.fullmatch(r'[A-Za-z_]\w*', expression) else ''


def _binding(project, source, method, name, offset):
    """('local', start) | ('param',) | ('field',) | None for a bare identifier at offset."""
    for declared, _, start, end in reversed(source.local_declarations(method)):
        if declared == name and start <= offset < end:
            return ('local', start)
    if any(parameter == name for _, parameter, _ in method.parameters()):
        return ('param',)
    if method.owner and name in project.receiver_members(method.owner.name, source.layer)[1]:
        return ('field',)
    return None


def _lineage_bodies(project, class_name, layer):
    for ancestor in project.lineage(class_name):
        for definition in project.links.get(ancestor, ()):
            if layer is None or definition.source.layer is None or definition.source.layer <= layer:
                yield definition


def _statement_end(code, start):
    end = code.find(';', start)
    return len(code) if end < 0 else end


_NULL_VALUE = re.compile(r'^\s*(?:null|NULL)\s*$')


def _assigned_value(code, name, start, stop, allow_null=False):
    """True when `name = <value>` appears in code[start:stop] (a null value only counts if allow_null)."""
    for match in re.finditer(r'(?<![\w.>])(?:this\s*\.\s*)?' + re.escape(name) + r'\s*=(?!=)\s*', code[start:stop]):
        value = code[start + match.end():_statement_end(code, start + match.end())]
        if allow_null or not _NULL_VALUE.match(value):
            return True
    return False


_FIND_PATH = re.compile(r'^FindPath$')


def rule_findpath_output(project, source):
    """FindPath(from, to, filter, out array) needs an allocated output array (WD-L1).

    The engine writes through the array it is handed; null or an array that was
    declared but never allocated is a null dereference in native code.
    """
    for method in _all_methods(source):
        for offset, _, receiver, arguments, _ in _named_calls(source, method, 'FindPath'):
            if len(arguments) != 4:
                continue
            argument = arguments[3]
            reason = ''
            if _NULL_VALUE.match(argument):
                reason = 'null output array'
            else:
                name = _bare_name(argument)
                bound = _binding(project, source, method, name, offset) if name else None
                if bound and bound[0] == 'local':
                    statement = source.code[bound[1]:_statement_end(source.code, bound[1])]
                    if '=' in statement:
                        initial = statement.split('=', 1)[1]
                        if _NULL_VALUE.match(initial) and not _assigned_value(source.code, name, bound[1] + len(statement), offset):
                            reason = f'{name} initialised to null'
                    elif not _assigned_value(source.code, name, bound[1] + len(statement), offset):
                        reason = f'{name} declared without new before the call'
                elif bound and bound[0] == 'field' and method.owner:
                    allocated = False
                    for definition in _lineage_bodies(project, method.owner.name, source.layer):
                        if any(f.name == name and f.initializer and not _NULL_VALUE.match(f.initializer)
                               for f in definition.fields):
                            allocated = True
                        elif _assigned_value(definition.source.code, name, definition.body_start, definition.body_end):
                            allocated = True
                    if not allocated:
                        reason = f'field {name} is never allocated'
            if reason:
                yield _finding('HC-E032', source, offset, _symbol(method), f'{reason}: {RULES["HC-E032"]}')


_NAVMESH_CALLS = 'SampleNavmeshPosition|FindPath|RaycastNavMesh'


def rule_navmesh_filter_flags(project, source):
    """Navmesh queries need a PGFilter whose SetFlags ran (WD-L2).

    A default PGFilter carries no include flags, so every query misses. Locals
    must call SetFlags before the query (or come from a call/parameter, which
    this rule cannot follow); fields need SetFlags somewhere in the class chain.
    """
    for method in _all_methods(source):
        for offset, name, receiver, arguments, _ in _named_calls(source, method, _NAVMESH_CALLS):
            if len(arguments) < 4 or (name == 'RaycastNavMesh' and len(arguments) != 5):
                continue
            argument = arguments[2]
            reason = ''
            if re.match(r'^new\s+PGFilter\b', argument):
                reason = 'inline new PGFilter'
            else:
                variable = _bare_name(argument)
                bound = _binding(project, source, method, variable, offset) if variable else None
                if bound and bound[0] == 'local':
                    statement = source.code[bound[1]:_statement_end(source.code, bound[1])]
                    initial = statement.split('=', 1)[1] if '=' in statement else ''
                    fresh = not initial or re.match(r'^\s*new\s+PGFilter\b', initial)
                    configured = re.search(r'(?<![\w.])' + re.escape(variable) + r'\s*\.\s*SetFlags\s*\(',
                                           source.code[bound[1]:offset])
                    if fresh and not configured:
                        reason = f'{variable} has no SetFlags before the query'
                elif bound and bound[0] == 'field' and method.owner:
                    configured = False
                    for definition in _lineage_bodies(project, method.owner.name, source.layer):
                        text = definition.source.code[definition.body_start:definition.body_end]
                        if re.search(r'(?<![\w>])(?:this\s*\.\s*)?' + re.escape(variable) + r'\s*\.\s*SetFlags\s*\(', text):
                            configured = True
                        # A field filled from a call (not new) is configured elsewhere.
                        for match in re.finditer(r'(?<![\w.>])(?:this\s*\.\s*)?' + re.escape(variable) + r'\s*=(?!=)\s*([^;]*)', text):
                            if not re.match(r'^\s*new\s+PGFilter\b', match[1]):
                                configured = True
                    if not configured:
                        reason = f'field {variable} never calls SetFlags'
            if reason:
                yield _finding('HC-E033', source, offset, _symbol(method), f'{name}: {reason}: {RULES["HC-E033"]}')


_LIVING_CHECK = re.compile(r'\b(?:Count|GetCount|MemberCount|GetMemberCount|AliveCount|LivingCount|DeceasedCount'
                           r'|GetAgentCount|IsAlive|IsDead|GetAgents|GetMember|GetAllAgents)\s*\(')


def rule_delete_group(project, source):
    """AIWorld.DeleteGroup destroys every attached agent (WD-L3).

    The method must have looked at the group's living members before the call.
    The check is textual and conservative: any member-count or liveness query
    earlier in the same method satisfies it.
    """
    authored = project.methods.get('DeleteGroup', ())
    for method in _all_methods(source):
        if method.name == 'DeleteGroup':
            continue
        for offset, name, receiver, arguments, _ in _named_calls(source, method, 'DeleteGroup'):
            if not receiver and authored:
                continue
            before = source.code[method.body_start:offset]
            if not _LIVING_CHECK.search(before):
                yield _finding('HC-E034', source, offset, _symbol(method), RULES['HC-E034'])


_INFECTED_ROOTS = frozenset({'DayZInfected', 'ZombieBase', 'ZombieMaleBase', 'ZombieFemaleBase'})


def _derives_from(project, kind, targets):
    seen, pending = set(), [project.resolve_typedef(kind)]
    while pending:
        name = pending.pop()
        if not name or name in seen:
            continue
        seen.add(name)
        if name in targets or name.startswith('Zmb'):
            return True
        pending.extend(d.base for d in project.links.get(name, ()) if d.base)
        pending.extend(d['parent'] for d in project.symbols.get(name, ()) if d['parent'])
    return False


def rule_infected_script_inst(project, source):
    """StartCommand_ScriptInst on a DayZInfected crashes natively (WD-L4, build 135)."""
    ownership = _ownership(project)
    for method in _all_methods(source):
        for offset, name, receiver, arguments, _ in _named_calls(source, method, 'StartCommand_ScriptInst'):
            if receiver in ('', 'this', 'super'):
                kind = method.owner.name if method.owner else ''
            else:
                kind = ownership.receiver(receiver, method, offset)
            if kind and _derives_from(project, kind, _INFECTED_ROOTS):
                yield _finding('HC-E035', source, offset, _symbol(method), f'{kind}: {RULES["HC-E035"]}')


# Collection and command APIs that adopt their argument.
# RegisterRecipe is the vanilla PluginRecipesManagerBase hook; the manager keeps the recipe.
_ADOPTING_CALLS = frozenset({'Insert', 'InsertAt', 'InsertAll', 'Set', 'StartCommand_Script', 'StartCommand_ScriptInst',
                             'RegisterRecipe'})
_NEW_ARGUMENT = re.compile(r'^new\s+[A-Za-z_]\w*')


def _parameter_retained(project, ownership, candidate, index, depth=0, visiting=frozenset()):
    """True when a parameter is stored in a field/collection or forwarded to a retaining callee."""
    parameters = candidate.parameters()
    if index >= len(parameters) or id(candidate) not in ownership.sources:
        return False
    name = parameters[index][1]
    source = ownership.sources[id(candidate)]
    body = source.body(candidate)
    escaped = re.escape(name)
    if re.search(r'(?:^|[;{}])\s*[A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*)*\s*=(?!=)\s*' + escaped + r'\s*;', body):
        return True
    if re.search(r'\.\s*(?:Insert|InsertAt|InsertAll|Set)\s*\([^;]*\b' + escaped + r'\b', body):
        return True
    # Returning the argument hands it to the caller's variable, which becomes its owner.
    if re.search(r'\breturn\s+' + escaped + r'\s*;', body):
        return True
    if depth >= 3 or id(candidate) in visiting:
        return False
    for call in _ANY_CALL.finditer(body):
        if call[1] in _KEYWORDS or call[1] == candidate.name:
            continue
        opening = body.find('(', call.start())
        arguments = [a.strip() for a in es.split_top(body[opening + 1:es.matching_paren(body, opening)], ',')]
        for position, argument in enumerate(arguments):
            if argument != name:
                continue
            callees = [m for m in project.methods.get(call[1], ()) if len(m.parameters()) > position]
            if callees and all(_parameter_retained(project, ownership, m, position, depth + 1,
                                                   visiting | {id(candidate)}) for m in callees):
                return True
    return False


def rule_new_argument(project, source):
    """new X passed straight into a call that does not keep it (WD-L5).

    HC-E026 covers fresh call results; this covers the same temporary-owner trap
    for a direct `new`. Adopting natives (collection Insert/Set, StartCommand_Script)
    and authored callees that store or forward the parameter are accepted.
    """
    ownership = _ownership(project)
    for method in _all_methods(source):
        for offset, name, receiver, arguments, opening in _named_calls(source, method, r'[A-Za-z_]\w*'):
            if name in _KEYWORDS or name in _ADOPTING_CALLS:
                continue
            before = source.code[max(method.body_start, offset - 8):offset]
            if re.search(r'\bnew\s*$', before) or (not receiver and re.search(r'\bnew\s+$', before)):
                continue  # constructor call, not a method call
            for index, argument in enumerate(arguments):
                if not _NEW_ARGUMENT.match(argument):
                    continue
                call = ownership.call((receiver + '.' if receiver else '') + name + '()', method, offset)
                pool = list(call[0]) if call else []
                if not pool and receiver:
                    # Generic receivers (Store<T>) resolve by their raw class name.
                    kind = re.sub(r'<.*$', '', ownership.receiver(receiver, method, offset) or '')
                    for ancestor in project.lineage(kind):
                        pool = [m for d in project.links.get(ancestor, ()) for m in d.methods if m.name == name]
                        if pool:
                            break
                candidates = [m for m in pool if len(m.parameters()) > index]
                if pool and not candidates:
                    continue  # arity mismatch: not resolvable here
                if candidates and all(_parameter_retained(project, ownership, m, index) for m in candidates):
                    continue
                key = re.sub(r'\s+', ' ', f'{(receiver + ".") if receiver else ""}{name}(... {argument} ...)')
                yield _finding('HC-E036', source, offset, _symbol(method), RULES['HC-E036'],
                               key=f'{key} [argument {index + 1}]')


def rule_flat_pathgraph(project, source):
    """UpdatePathgraphRegionByObject builds a flat-Y region from the object (WD-L9)."""
    for method in _all_methods(source):
        body = source.body(method)
        for match in re.finditer(r'\bUpdatePathgraphRegionByObject\b', body):
            yield _finding('HC-E037', source, method.body_start + match.start(), _symbol(method), RULES['HC-E037'])


def _foreach_iterable(body, start):
    """Return (iterable_text, offset) for the foreach whose '(' is at body[start], or None."""
    depth, colon = 0, -1
    for index in range(start, len(body)):
        char = body[index]
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                return (body[colon + 1:index], colon + 1) if colon >= 0 else None
        elif char == ':' and depth == 1 and colon < 0:
            colon = index
    return None


def rule_foreach_call_iterable(project, source):
    """foreach (x : Call()) faults natively even when the callee returns an owned array (#337).

    v1-test-15 threw `NULL pointer to instance` once a second at
    `foreach (Man observer : HCPerfPlayers.HCGet())` although HCGet returns a static ref
    array. Every call in the iterable (including `a.B().Field`) must be held in a typed local
    first; plain fields and locals are fine. HC-E026 covers call results passed as arguments.
    """
    for method in _all_methods(source):
        body = source.body(method)
        for match in re.finditer(r'\bforeach\s*\(', body):
            found = _foreach_iterable(body, match.end() - 1)
            if found and '(' in found[0]:
                yield _finding('HC-E048', source, method.body_start + match.start(), _symbol(method),
                               f'{found[0].strip()}: {RULES["HC-E048"]}')


_INDEXED_TARGET = re.compile(r'(?<![\w.])([A-Za-z_][\w.]*)\s*\[')


def rule_call_in_assigned_index(project, source):
    """a[F(x)] = v fails the native compile (Function definition inside block. (missing '}' ?)).

    The 2026-11-23 gate refused `s_Stamp[HCBucket(cellX, cellZ)] = s_Counter;` in HCNavRegionEpoch.c.
    Reading `a[F(x)]` is not flagged; only a slot that is assigned (=, +=, -=, *=, /=).
    """
    for method in _all_methods(source):
        body = source.body(method)
        for match in _INDEXED_TARGET.finditer(body):
            line_start = body.rfind('\n', 0, match.start()) + 1
            before = body[line_start:match.start()].strip()
            if before and not re.search(r'(?:^|[;{}]|\belse|\))$', before):
                continue
            depth, index = 0, match.end() - 1
            while index < len(body):
                if body[index] == '[':
                    depth += 1
                elif body[index] == ']':
                    depth -= 1
                    if depth == 0:
                        break
                elif body[index] in ';{}':
                    break
                index += 1
            if depth != 0 or index >= len(body):
                continue
            inner = body[match.end():index]
            if not re.search(r'[A-Za-z_]\w*\s*\(', inner):
                continue
            if re.match(r'\s*(?:[-+*/]=|=(?!=))', body[index + 1:]):
                yield _finding('HC-E051', source, method.body_start + match.start(), _symbol(method),
                               f'{match[1]}[{inner.strip()}]: {RULES["HC-E051"]}')


# Vanilla array typedefs (1_Core/proto/EnScript.c); resolved through the native scripts when present.
_ARRAY_TYPEDEFS = frozenset({'TStringArray', 'TIntArray', 'TFloatArray', 'TBoolArray', 'TVectorArray',
                             'TClassNameArray', 'TManagedArray'})
_ORDER_WAIVER = re.compile(r'//\s*HC-ORDER:\s*unordered ok\b')


def rule_unordered_head_remove(project, source):
    """array.Remove(0) breaks FIFO order: the engine fills the gap with the last element.

    Native 1_Core/proto/EnScript.c: Remove(index) replaces the slot with the last
    element; RemoveOrdered(index) keeps order. Only receivers that resolve to an
    array<...> (typedefs such as TStringArray included) are flagged, so map keys are
    not. The comment `// HC-ORDER: unordered ok` on the same or the previous line
    waives a drain where order does not matter.
    """
    ownership = _ownership(project)
    for method in _all_methods(source):
        for offset, name, receiver, arguments, _ in _named_calls(source, method, 'Remove'):
            if not receiver or arguments != ['0']:
                continue
            kind = ownership.receiver(receiver, method, offset)
            if not (kind.startswith('array<') or kind in _ARRAY_TYPEDEFS):
                continue
            line = source.line_of(offset)
            raw = source.text.split('\n')
            if any(_ORDER_WAIVER.search(raw[number - 1]) for number in (line, line - 1) if 0 < number <= len(raw)):
                continue
            yield _finding('HC-E038', source, offset, _symbol(method), RULES['HC-E038'])


# Value reads only. ConfigGetChildrenCount (0 is the true count of a missing class) and the
# bool-returning enumerators ConfigGetChildName/ConfigGetBaseName already report absence.
_CONFIG_READS = ('ConfigGetInt|ConfigGetFloat|ConfigGetText|ConfigGetTextRaw|ConfigGetTextOut|ConfigGetVector'
                 '|ConfigGetType|ConfigGetTextArray|ConfigGetTextArrayRaw|ConfigGetFloatArray|ConfigGetIntArray')
_CONFIG_GUARD = re.compile(r'\bConfigIsExisting\s*\(|\bHCConfigHelper\s*\.')
_CONFIG_HELPER = 'HCConfigHelper'


def rule_config_get(project, source):
    """ConfigGet* needs a presence guard or the HCConfigHelper path (new id; HC-E028 is taken).

    HCConfigHelper (3_Game/Core/HCConfigHelper.c) is the sanctioned reader: it
    checks ConfigIsExisting and ConfigGetType, then returns the caller's fallback.
    Elsewhere a ConfigIsExisting or HCConfigHelper call earlier in the same method
    counts as the guard; the rule does not prove both use the same path.
    """
    for method in _all_methods(source):
        if method.owner and method.owner.name == _CONFIG_HELPER:
            continue
        for offset, name, receiver, arguments, _ in _named_calls(source, method, _CONFIG_READS):
            if not _CONFIG_GUARD.search(source.code[method.body_start:offset]):
                yield _finding('HC-E031', source, offset, _symbol(method), f'{name}: {RULES["HC-E031"]}')



# HC-E049: engine classes the compiler refuses to mod. The native scripts cache gives no reliable signal:
# Building (3_Game/Entities/Building.c) is declared like EntityAI, a plain `class X : Y` with `proto native`
# members, and EntityAI/Man/ItemBase mod fine, so the list is cited evidence only. Add a class here only with the
# compile-gate line that refused it.
ENGINE_UNMODDABLE = {
    'Building': ('BuildingBase', 'compile gate 2026-11-22: Engine class \'Building\' cannot be modded; '
                                 'HCNavEpochDoors.c hooks the scripted base BuildingBase (4_World/Entities/Game/Super/Building.c)'),
}


def rule_engine_class_modded(project, source):
    for definition in source.classes:
        refused = ENGINE_UNMODDABLE.get(definition.name) if definition.modded else None
        if refused:
            yield _finding('HC-E049', source, definition.offset, definition.name,
                           f'modded class {definition.name}: {RULES["HC-E049"]}; use {refused[0]} ({refused[1]})')


# Extend the path scopes here when another CE consumer adopts the config-only contract.
_CONFIG_COMPAT_SCOPES = (
    re.compile(r'(?:^|/)mods/.*/Loot/HCGunPile[^/]*\.c$'),
    re.compile(r'(?:^|/)mods/.*/HCTestReachFixtures\.c$'),
)
_WEAPON_COMPAT_CALL = re.compile(
    r'\b(?:Get\w*(?:Magazine|Muzzle|Chamber)\w*|HasInternalMagazine|SpawnAmmo'
    r'|SpawnAttachedMagazine|FillChamber|GetAmmoMax)\s*\(')


def rule_fixture_catalog(project, source):
    """#368 build 187: fixture ownership alone cannot pass HCReceive's catalog gate.

    Use parsed HCOwns bodies and masked code offsets, so comments and strings
    mentioning commands cannot satisfy registration or invent fixture ownership.
    This extends the existing enforce_lint preland row; no generated data is involved.
    """
    if 'HollowCountryTest' not in source.path.parts:
        return
    if not hasattr(project, '_fixture_catalog_ids'):
        project._fixture_catalog_ids = set()
        for catalog in project.sources:
            if catalog.path.name != 'HCAdminCatalog.c':
                continue
            for match in re.finditer(r'\bHCAdd\s*\(\s*"[^"\n]*"', catalog.code):
                literal = re.search(r'"([^"\n]+)"', catalog.text[match.start():match.end()])
                if literal:
                    project._fixture_catalog_ids.add(literal[1])
    for method in _all_methods(source):
        if method.name != 'HCOwns':
            continue
        body = source.code[method.body_start:method.body_end]
        for match in re.finditer(r'\b\w+\s*==\s*"[^"\n]*"', body):
            offset = method.body_start + match.start()
            literal = re.search(r'"(fx_\w+)"', source.text[offset:method.body_start + match.end()])
            if literal and literal[1] not in project._fixture_catalog_ids:
                yield _finding('HC-E055', source, offset, _symbol(method),
                               literal[1] + ': ' + RULES['HC-E055'], key=literal[1])


def rule_config_only_weapon_compat(project, source):
    """#338 native null dereference: prohibit the whole query family in CE/fixture scopes.

    Scope by path, independent of receiver spelling/type/alias. The fixture's
    PushCartridgeToChamber, CanFire, IsChamberEmpty and Fire remain allowed.
    Comments and literals are masked by enforce_source.
    """
    if not any(scope.search(source.path.as_posix()) for scope in _CONFIG_COMPAT_SCOPES):
        return
    for method in _all_methods(source):
        for match in _WEAPON_COMPAT_CALL.finditer(source.code[method.body_start:method.body_end]):
            yield _finding('HC-E052', source, method.body_start + match.start(), _symbol(method),
                           RULES['HC-E052'])


def rule_proto_native_methods(project, source):
    """Reject native redeclarations, retaining existing scripted overload hooks.

    Use the same layer-aware ancestry/declaration model as HC-E042. Unknown
    parents do not hide a known proto ancestor. Proto external and static proto
    declarations are native boundaries too; the native modifier is not required.
    """
    shared = _syntax.model(project)
    for definition in source.classes:
        if not (definition.modded or definition.base):
            continue
        pool = shared.parent_declarations(definition, source)
        for declaration in _syntax.declarations(source, definition):
            if declaration.name == definition.name or declaration.name.startswith('~'):
                continue
            candidates = [d for d in pool if d.name == declaration.name]
            protos = [d for d in candidates if 'proto' in d.modifiers
                      and d.source not in project.sources]
            if not protos:
                continue
            arity = len(declaration.params)
            matches = [d for d in protos if len(d.params) == arity]
            script_hook = any('proto' not in d.modifiers
                              and shared.same_parameters(declaration.params, d.params)
                              for d in candidates)
            if not matches and script_hook:
                continue
            parent = (matches or protos)[0]
            action = 'redeclares' if matches else 'adds an overload of'
            yield _finding('HC-E053', source, declaration.offset,
                           f'{definition.name}.{declaration.name}',
                           f'{_syntax._show(declaration)} {action} proto {parent.cls}.{parent.name}; '
                           + RULES['HC-E053'], native=True,
                           key=f'proto: {_syntax._show(declaration)}')


def client_only_blocks(source):
    """Inventory role-conditional arms, including else/elif and nested blocks.

    Both sides of SERVER/CLIENT conditions are retained deliberately: lint has
    no selected preprocessor branch. Offsets come from the source lexer so
    comments and quoted directive examples cannot create inventory entries.
    """
    directives = []
    es.clean(source.text, directives)
    stack, blocks = [], []
    for offset, keyword in directives:
        line = source.line_text(offset).strip()
        # Prefix prevents clean() from treating the directive itself as a line
        # to erase, while still masking comments and quoted examples.
        condition = es.clean('_' + line)[1:]
        role = bool(re.search(r'\b(?:SERVER|CLIENT)\b', condition))
        if keyword in {'if', 'ifdef', 'ifndef'}:
            stack.append([offset, line, role])
        elif keyword in {'else', 'elif', 'endif'} and stack:
            start, label, relevant = stack[-1]
            if relevant or role:
                blocks.append((start, offset, label))
            if keyword == 'endif':
                stack.pop()
            else:
                stack[-1] = [offset, line, relevant or role]
    for start, label, relevant in stack:
        if relevant:
            blocks.append((start, len(source.text), label))
    return sorted(blocks)


def client_branch_coverage(sources, native=None, symbols=None, provider_layers=None):
    """Explicitly run client-relevant rules on files with role branches.

    Keep whole files and the whole project index: slicing a block would discard
    its owning class and declarations outside the block. Return branch-local
    findings plus a deterministic inventory for the preland transcript.
    """
    project = Project(sources, native, symbols, provider_layers)
    inventory, findings = [], []
    for source in sources:
        blocks = client_only_blocks(source)
        for start, end, label in blocks:
            inventory.append({'path': source.rel, 'line': source.line_of(start),
                              'end_line': source.line_of(end), 'condition': label})
        if not blocks:
            continue
        for rule in (rule_receiver_methods, rule_proto_native_methods):
            for finding in rule(project, source):
                if any(source.line_of(start) <= finding.line <= source.line_of(end)
                       for start, end, _ in blocks):
                    findings.append(finding)
    return inventory, findings


# RPC ids are a global wire namespace, even when declared in different classes.
_RPC_LITERAL = r'[+-]?\s*(?:0[xX][0-9a-fA-F]+|[0-9]+)'
_RPC_CONST = re.compile(r'\b(?:static\s+)?const\s+int\s+(\w+)\s*=\s*('
                        + _RPC_LITERAL + r')\s*;')
_RPC_MEMBER = re.compile(r'(?:^|,)\s*(\w+)\s*=\s*(' + _RPC_LITERAL + r')\s*(?=,|$)')
_RPC_SEND = re.compile(r'\b(\w+)\s*\.\s*Send\s*\(')
_RPC_SINGLE = re.compile(r'\bGetGame\s*\(\s*\)\s*\.\s*RPCSingleParam\s*\(')


@dataclass(frozen=True)
class RPCId:
    path: str
    line: int
    name: str
    value: int


def rpc_id_inventory(sources):
    """Literal wire allocations only; named uses do not allocate another id."""
    inventory = []

    def record(source, offset, name, literal):
        literal = re.sub(r'\s+', '', literal)
        value = int(literal, 16 if 'x' in literal.lower() else 10)
        inventory.append(RPCId(source.rel, source.line_of(offset), name, value))

    for source in sources:
        for match in _RPC_CONST.finditer(source.code):
            if 'rpc' in match[1].lower():
                record(source, match.start(1), match[1], match[2])
        for enum in source.enum_blocks:
            start = enum.body_start + 1
            for match in _RPC_MEMBER.finditer(source.code[start:enum.body_end]):
                if 'rpc' in match[1].lower():
                    record(source, start + match.start(1), enum.name + '.' + match[1], match[2])
        methods = list(source.functions) + [m for c in source.classes for m in c.methods]
        for pattern in (_RPC_SEND, _RPC_SINGLE):
            for match in pattern.finditer(source.code):
                if pattern is _RPC_SEND and match[1] != 'ScriptRPC':
                    # Send also belongs to unrelated HC clients. Inspect the enclosing
                    # method's locals/parameters and its class fields, not other methods.
                    method = next((m for m in methods
                                   if m.body_start < match.start() < m.body_end), None)
                    if method is None:
                        continue
                    receivers = set(re.findall(r'\bScriptRPC\s+(\w+)',
                                               method.params + ';' + source.code[
                                                   method.body_start:match.start()]))
                    if method.owner is not None:
                        receivers.update(f.name for f in method.owner.fields if f.type == 'ScriptRPC')
                    if match[1] not in receivers:
                        continue
                opening = match.end() - 1
                closing = es.matching_paren(source.code, opening)
                args = es.split_top(source.code[opening + 1:closing], ',')
                # Both native signatures take target first, then rpc_type.
                if len(args) > 1 and re.fullmatch(_RPC_LITERAL, args[1].strip()):
                    offset = opening + 1 + len(args[0]) + 1
                    offset += len(args[1]) - len(args[1].lstrip())
                    record(source, offset, 'Send' if pattern is _RPC_SEND else 'RPCSingleParam',
                           args[1].strip())
    return sorted(inventory, key=lambda entry: (entry.path, entry.line, entry.name, entry.value))


def rule_duplicate_rpc_ids(project, source):
    if not hasattr(project, '_rpc_collisions'):
        grouped = {}
        for entry in rpc_id_inventory(project.sources):
            grouped.setdefault(entry.value, []).append(entry)
        project._rpc_collisions = {}
        for value, entries in grouped.items():
            if len(entries) < 2:
                continue
            locations = ', '.join(f'{e.path}:{e.line} ({e.name})' for e in entries)
            for entry in entries:
                project._rpc_collisions.setdefault(entry.path, []).append(Finding(
                    'HC-E054', entry.path, entry.line, entry.name, str(value),
                    f'RPC id {value} is shared by {locations}; each RPC needs its own id'))
    return project._rpc_collisions.get(source.rel, ())


ALL_RULES = (rule_fixture_catalog, rule_duplicate_rpc_ids, rule_proto_native_methods, rule_config_only_weapon_compat, rule_engine_class_modded, rule_duplicate_locals, rule_static_const_literals, rule_fresh_arguments, rule_broken_else, rule_typename_null, rule_native_named_methods, rule_parse_issues, rule_ternary, rule_string_formula, rule_boolean_string_formula, rule_leading_operator, rule_file_handle_int, rule_keyword_names, rule_layers, rule_weak_new, rule_weak_collection, rule_modded_links,
             rule_receiver_layers, rule_receiver_methods, rule_expansion_bridge, rule_dependency_bridges, rule_modded_module,
             rule_collection_keys, rule_handle_null, rule_vanilla_storage,
             rule_type_named_variables, rule_modded_field_order,
             rule_substring, rule_type_named_methods, rule_bare_print, rule_build_identity, rule_silent_commit, rule_silent_gate,
             rule_predicted_actions, rule_config_get, rule_findpath_output, rule_navmesh_filter_flags,
             rule_delete_group, rule_infected_script_inst, rule_new_argument, rule_flat_pathgraph, rule_unordered_head_remove, rule_foreach_call_iterable, rule_call_in_assigned_index, enforce_json.rule_json_defaults,
             _readiness.rule_module_names, _readiness.rule_engine_type_names, _use.rule_use_init_path,
             rule_stored_handles, *_syntax.rules_for(sys.modules[__name__]),
             _names.make_rule(sys.modules[__name__], _syntax))


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
        if finding.rule == 'HC-E026' and finding.severity == 'error':
            new.append(finding)  # Crash-shape errors cannot be waived by warning baselines.
        elif budget[finding.identity()] > 0:
            budget[finding.identity()] -= 1
        else:
            new.append(finding)
    stale = [dict(entries[i], unused=allowed[i] - seen[i]) for i in sorted(allowed) if seen[i] < allowed[i]]
    return new, stale


def baseline_from(findings, review):
    counts = Counter(f.identity() for f in findings)
    native = {f.identity(): f.native for f in findings}
    severity = {f.identity(): f.severity for f in findings}
    lines = {}
    for f in findings:
        lines.setdefault(f.identity(), f.line)
    entries = []
    for identity in sorted(counts):
        rule, path, symbol, key = identity
        entry = {'rule': rule, 'path': path, 'symbol': symbol, 'key': key, 'count': counts[identity],
                 'line_at_review': lines[identity], 'review': review}
        if rule in {'HC-E026', 'HC-O026'}:
            entry['severity'] = severity[identity]
        if native[identity]:
            entry['native'] = True
        entries.append(entry)
    return {'schema': 1, 'scope': 'authored mods/*/scripts; reviewed pre-existing findings only',
            'entries': entries}


def native_cache(argument=None, disabled=False):
    if disabled:
        return None
    path = Path(argument or os.environ.get('HC_NATIVE_SCRIPTS') or DEFAULT_CACHE).expanduser()
    symbols, _origin = native_symbols.resolve(path, allow_uncached=True)
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
    symbols, native_origin = None, 'none'
    if not args.no_native:
        # No local cache: the committed vanilla names index stands in (summary says names-index).
        try:
            symbols, native_origin = native_symbols.resolve(path, allow_uncached=True)
        except (OSError, ValueError):
            parser.exit(1, 'enforce_lint: cannot read scripts or write the local symbol cache\n')
    if symbols is not None:
        print('enforce_lint: HC-E054 vanilla ERPCs comparison omitted: native index stores '
              'enum names, not values', file=sys.stderr)
    native = ({int(layer): set(names) for layer, names in symbols['types'].items()}
              if symbols is not None else None)
    _syntax.NATIVE_ROOT = path if symbols is not None else None
    mods = tuple(sorted(p.parent.name for p in (args.root / 'mods').glob('*/scripts') if p.is_dir()))
    sources = es.mod_sources(args.root, mods=mods)
    if symbols is not None:
        names = {m.name for source in sources for c in source.classes for m in c.methods
                 if m.name != c.name and 'override' not in m.modifiers}
        names.update(_COT_GLOBALS | _CF_GLOBALS | _DEPENDENCY_GLOBALS.keys())
        if native_origin == 'names-index':
            found = {n: set(layers) for n, layers in symbols['global_functions'].items() if n in names}
        else:
            found = native_global_functions(path, names)
        symbols = dict(symbols, globals=found)
    provider_layers = {}
    if not args.no_native:
        project = Project(sources, native, symbols)
        unknown = {d.name for source in sources for d in source.classes
                   if d.modded and not project.declaring_layers(d.name, source)}
        provider_layers = workshop_class_layers(unknown)
    findings = lint(sources, native, symbols=symbols, provider_layers=provider_layers)
    client_blocks, client_findings = client_branch_coverage(
        sources, native, symbols, provider_layers)
    findings = sorted(set(findings + client_findings),
                      key=lambda f: (f.path, f.line, f.rule, f.symbol, f.key))
    if args.write_baseline:
        args.baseline.write_text(json.dumps(baseline_from(findings, args.write_baseline), indent=1) + '\n',
                                 encoding='utf-8')
        print(f'wrote {len(findings)} findings to {args.baseline.name}')
        return 0
    baseline = load_baseline(args.baseline)
    new, stale = compare(findings, baseline, native is not None)
    per_rule = Counter(f.rule for f in findings)
    new_rule = Counter(f.rule for f in new)
    rpc_count = len(rpc_id_inventory(sources))
    if args.json:
        print(json.dumps({'rpc_ids': rpc_count, 'status': 'fail' if new or stale else 'pass', 'native': native is not None,
                          'client_blocks': client_blocks, 'client_findings': len(client_findings),
                          'counts': {r: {'total': per_rule[r], 'new': new_rule[r]} for r in RULES},
                          'new': [asdict(f) for f in new], 'stale': stale}, indent=1))
    else:
        print(f'enforce_lint: RPC id inventory={rpc_count}')
        for block in client_blocks:
            print('client-branch: {path}:{line}-{end_line} {condition} '
                  'checked=HC-E012,HC-E053'.format(**block))
        print(f'enforce_lint: client branches={len(client_blocks)} findings={len(client_findings)} '
              'coverage=static-all-arms (not a client compile)')
        for finding in (findings if args.all else new):
            print(('NEW  ' if finding in new else 'base ') + finding.render())
        for entry in stale:
            print(f"STALE {entry['path']}: {entry['rule']} {entry['symbol']}: {entry['key']} "
                  '(fixed? remove it from the baseline)')
        for rule in RULES:
            print(f'{rule} total={per_rule[rule]} new={new_rule[rule]}  {RULES[rule]}')
        print(f"enforce_lint: {'FAIL' if new or stale else 'pass'} findings={len(findings)} new={len(new)} "
              f"stale={len(stale)} native={'yes' if native_origin == 'cache' else native_origin if native is not None else 'no'}")
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
