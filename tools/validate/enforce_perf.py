"""Offline Enforce performance candidates; no engine or timing claims.

Run python3 -B -m tools.validate.enforce_perf [source.c ...]. Paths select
output, not the call-graph universe. --stdin PATH replaces one authored source
with stdin (e.g. git show REV:PATH | ... --stdin PATH PATH). check(sources)
is the integration entry point and accepts enforce_source.Source objects.

P001 checks lexically enclosing loops, string parameters/fields/locals and
simple assignments. Unknown strings are unbounded. Literal initializers,
small length refusal guards (including literal caller bounds) and explicit clamped, strided bulk Substring copies are
bounded, as are constant-length (<=1024) Substring copies, locals only ever set
from such pieces or one-character Get/At, and >, >= or != length guards against
a literal, a static const int or an all-literal-callers int parameter.
HCTextWindow receivers are typed objects, never strings. This is not
interprocedural string taint analysis: aliases, returned strings and caller
bounds can cause misses or candidates needing review.

P003 follows typed authored calls, inherited methods and virtual overrides.
A deterministic breadth-first search visits at most the finite parsed method
set, with a 24-edge depth limit. No name-only cross-class fallback, engine
callbacks, reflection, function pointers or flow/path feasibility analysis.
Each reachable I/O site is reported once with its shortest witness. Tick roots
are OnTick, OnUpdate, HCStep* and *SaveStage* / *StageSave*. Calls into the
shared HCStagedSaveImage Begin/HCStepImage/HCRefreshIntent are stage boundaries;
Finish is deliberately traversed because it drains stages synchronously.
A load-once latch (a bool/ref field tested first and set unconditionally before any
return/continue/break, with no reset on a tick path) makes the code it guards once-only:
neither its I/O, calls, Print nor Save sites are reported (see once_spans).
Retry window (once_spans): `if (!latch) { float now = ..; if (now >= window) { if (attempt()) { latch = true; }
else { window = now + K; } } }` (bool latch, float window field, K a positive literal or static const number)
bounds a retry-until-success probe to one attempt per window, and the guarded block counts as once-only.
Consume latch (once_spans): `if (!latch) { return; }` at method level, then a method-level
`latch = null/false;` later, makes the code after the last exit before that reset, to the
end of the method, run once per arming; it counts unless a tick path assigns the latch a
non-null value. Latch resets that are reachable only through an OnStop override do not
defeat a load-once latch (shutdown is not tick work).
Staged steps: a *Step*/*SaveStage*/*StageSave* method is exempt as a tick root, and as a
callee of a call that is not inside a loop, when StepCost bounds one call at STAGE_OPS file
operations and the method advances a field of its own class. StepCost follows statement
structure: sequential statements add, if/else takes the larger arm, an arm that always
returns excludes the code after it, any loop that can reach file I/O is unbounded, a
ReadFile counts only with a constant length <= STAGE_READ_BYTES, and a recursive call into
I/O-reaching code is unbounded. The stage boundaries above cost one operation.
Exact-field dispatch (Model.concrete_type): a field whose initializer and every write
(anywhere in its class lineage, never through a qualifier elsewhere) is `new T` or null
with a single T dispatches only to T's lineage instead of every override of its declared
type. It only filters targets and never adds an edge.
Capped retry (capped_retry): a CallLater scheduled in the then-branch of
`if (counter < N)` (int field of the scheduling class, N a literal or static const int
<= TRIP_LOOP_CAP, counter incremented before the call, no callback assigning it other than
by increment) is a finite retry sequence and does not make the callback a tick root.
Single I/O operations are candidates too: the tool cannot infer their latency.
Baseline entries acknowledge candidates, not native acceptance. P002 is omitted
because source-only configured-float bounds have too much ambiguity.

P004 finds lexical nested collection loops with equality comparisons and array
Find/Contains/IndexOf/Get calls inside loops. Literal upper bounds <=16 are
skipped; array.Get/Count/Set are O(1) natives and are not candidates, array.Find is.
Only declared array/map/set receivers are recognized, not aliases, returned
collections or interprocedural nesting. Equality need not compare loop items.
P005 finds Print in lexical loops on the same bounded tick graph as P003;
it cannot prove logging frequency or summary logging. A Print under a set-once latch,
or directly followed by return/break (once per call), is not per-item.
P006 finds literal HC_WORK_* arguments to HCTakeFor/HCCharge shared across
owner class names (modded definitions share their class name). It cannot
resolve computed slots or prove that different classes compete at runtime.
P007 checks contiguous, unique consumer slots against HCRegisterConsumer table
rows and shared_settings.json weight defaults/ranges. No profile DTO ceremony.
HC_WORK_CONSUMERS is a count; HC_WORK_UNBOUNDED is an arithmetic sentinel,
not a slot. This is structural completeness, not runtime settings validation.
P008 finds Save calls on declared types ending in Store on P003's tick graph;
it cannot resolve returned stores or infer synchronous implementation details. A
Save reachable only through a module OnStop (shutdown, run once) is the durability
barrier and is not reported; any other tick-reachable Save still is. All rules report review candidates,
never measured complexity, timing or native acceptance.

CallLater roots (B-14): a method scheduled through CallLater/CallLaterByName is a
tick root for P003/P005/P008 when the call repeats (any repeat argument other than
a literal false/0) or when the callback re-arms itself (it reaches, through typed
authored calls, a method that schedules it again). One-shot, non-rearming
callbacks stay out of the roots. Update-queue Insert callbacks are not modelled.

P009 follows the same bounded typed call graph from OnStart, carrying lexical
loop context across calls. Repeated file opens, probes, copies, deletes and JSON
file loads/saves are synchronous multi-file candidates; reads from an already
open handle are not. A counting for-loop with a literal start, a literal or static const int
limit, a unit stride and a body that never writes the counter has a constant trip count
(trip_count); loops up to TRIP_LOOP_CAP iterations, nested to a product of at most
TRIP_PRODUCT_CAP, are bounded and do not make a pass multi-file (multiplier). Latch spans
and calls into OnStop overrides are not followed. It cannot distinguish repeated access to
one path from different paths, prove other loop trip counts (while, foreach, configured
bounds), or follow queued callbacks.
P010 finds raw HCTake calls on declared HCUnitBudget receivers (including
derived types) and HCServer.HCTickWork() chains. The shared budget's own
implementation is excluded. A module-owned budget (a local or one-identifier field
whose every initializer and assignment is `new` of a budget type or null, never given
an HCSetProfile) has no other consumer and no attribution table and is not flagged;
parameters, aliases of the shared accessor and unknown receiver/return types are not
inferred by method name alone.
"""
import argparse
import ast
from collections import deque
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys

# Support both the module CLI and direct script execution.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.validate import enforce_source as es

ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).with_name('enforce_perf_baseline.json')
RULES = {
    'HC-P001': 'unbounded string scan inside a loop without HCTextWindow',
    'HC-P003': 'file I/O reachable in one tick/save step outside the staged writer',
    'HC-P004': 'nested linear collection scan',
    'HC-P005': 'per-item Print reachable on a tick path',
    'HC-P006': 'work slot shared by different owner classes',
    'HC-P007': 'incomplete work slot registration',
    'HC-P008': 'synchronous store Save reachable on a tick path',
    'HC-P009': 'synchronous multi-file loop reachable from OnStart',
    'HC-P010': 'raw HCTake bypasses consumer fairness and attribution',
}
MAX_DEPTH = 24
_IDENT = r'[A-Za-z_]\w*'
_CHAIN = rf'{_IDENT}(?:\s*\.\s*{_IDENT})*'
_SCAN = re.compile(rf'\b({_CHAIN})\s*\.\s*(Get|Substring|IndexOfFrom|IndexOf|Contains)\s*\(')
_CALL = re.compile(rf'(?<![\w.])({_CHAIN})(?:\s*<[^;{{}}()]*>)?\s*\(')
_LOCAL = re.compile(rf'\b({_IDENT}(?:\s*<[^;{{}}()=]*>)?)\s+({_IDENT})\s*(?=[=;,)])')
_IO = frozenset('FileExist OpenFile FPrint FGets ReadFile CopyFile DeleteFile'.split())
_ROOT = re.compile(r'^(?:OnTick|OnUpdate|HCStep\w*|\w*SaveStage\w*|\w*StageSave\w*)$')
# Exact shared implementation, rather than a blanket class/name suppression.
_WRITER_PATH = 'mods/HollowCountry/scripts/4_World/World/HCWorkBudget.c'
_BOUNDARIES = frozenset({'Begin', 'HCStepImage', 'HCRefreshIntent'})
# array.Get(n)/Count()/Set() are O(1) native index operations (EnScript.c protos), so
# Get is not a scan candidate; array.Find is a linear first-occurrence search.
_ARRAY_SCAN = re.compile(rf'\b({_CHAIN})\s*\.\s*(Find|Contains|IndexOf)\s*\(')
_SLOT_CALL = re.compile(r'\b(HCTakeFor|HCCharge)\s*\(')
_CALL_LATER = re.compile(r'\b(CallLater|CallLaterByName)\s*\(')
# Names of staged steps (the HCStep* part of _ROOT, plus the save-stage spellings).
_STEP = re.compile(r'^(?:HCStep\w*|\w*SaveStage\w*|\w*StageSave\w*)$')


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


class Model:
    def __init__(self, sources):
        self.nodes = [(s, m) for s in sources for m in s.methods]
        self.classes = {}
        self._lineages = {}
        self.index = {}
        self.globals = {}
        for i, (s, m) in enumerate(self.nodes):
            if m.owner:
                self.index.setdefault((m.owner.name, m.name), []).append(i)
            else:
                self.globals.setdefault(m.name, []).append(i)
        for s in sources:
            for c in s.classes:
                self.classes.setdefault(c.name, []).append(c)
        self.descendants = {name: [child for child in self.classes if child != name and name in self.lineage(child)]
                            for name in self.classes}
        # Named integer constants (static const int NAME = N;); the largest value wins
        # for a name defined more than once, so a bound is never understated.
        self.consts = {}
        for s in sources:
            for c in re.finditer(r'\bconst\s+int\s+(\w+)\s*=\s*(\d+)\s*;', s.code):
                self.consts[c.group(1)] = max(self.consts.get(c.group(1), 0), int(c.group(2)))
        self._writes = None
        self._concrete = {}
        self.envs = [self.environment(s, m) for s, m in self.nodes]

    def const_int(self, text):
        """Literal or named constant integer value of an expression, else None."""
        text = re.sub(r'\s+', '', text)
        if text.isdecimal():
            return int(text)
        return self.consts.get(text.split('.')[-1]) if re.fullmatch(_CHAIN, text) else None

    def lineage(self, name):
        if name in self._lineages:
            return self._lineages[name]
        result, pending = [], [name]
        while pending:
            current = pending.pop(0)
            if current in result:
                continue
            result.append(current)
            pending.extend(c.base for c in self.classes.get(current, []) if c.base)
        self._lineages[name] = result
        return result

    def environment(self, s, m):
        env = {}
        if m.owner:
            for name in reversed(self.lineage(m.owner.name)):
                for c in self.classes.get(name, []):
                    env.update((f.name, f.type) for f in c.fields)
            env['this'] = m.owner.name
            env['super'] = m.owner.base
        env.update((name, typ) for typ, name, _ in m.parameters())
        env.update((a.group(2), re.sub(r'\s+', '', a.group(1)))
                   for a in _LOCAL.finditer(s.body(m)))
        return env

    def field_of(self, owner, name):
        """Field definition by name through the class lineage, else None."""
        return next((f for ancestor in self.lineage(owner) for c in self.classes.get(ancestor, [])
                     for f in c.fields if f.name == name), None)

    def type_of(self, expression, env):
        parts = re.sub(r'\s+', '', expression).split('.')
        typ = env.get(parts[0], parts[0] if parts[0] in self.classes else '')
        for part in parts[1:]:
            typ = next((f.type for ancestor in self.lineage(typ)
                        for c in self.classes.get(ancestor, []) for f in c.fields
                        if f.name == part), '')
        return typ

    def writes(self):
        """Every `name = value;` statement in authored method bodies: name -> [(node, qualifier, value)]."""
        if self._writes is None:
            self._writes = {}
            pattern = re.compile(rf'(?<![\w.])((?:{_IDENT}\s*\.\s*)*)({_IDENT})\s*=(?!=)\s*([^;]*);')
            for i, (s, m) in enumerate(self.nodes):
                for write in pattern.finditer(s.code, m.body_start, m.body_end):
                    self._writes.setdefault(write.group(2), []).append(
                        (i, re.sub(r'\s+', '', write.group(1)), write.group(3).strip()))
        return self._writes

    def concrete_type(self, i, expression):
        """Exact class that a field named by expression always holds, else ''.

        Holds when every write to the field, in its class or a derived class, and its
        initializer, is `new T(...)` or null, with one T; and no code outside those
        classes writes the field through a qualifier. Parameters, locals and fields
        assigned from other expressions keep their declared type."""
        s, m = self.nodes[i]
        parts = re.sub(r'\s+', '', expression).split('.')
        if parts[0] == 'this':
            parts = parts[1:]
        if len(parts) != 1 or not m.owner or parts[0] in {n for _, n, _ in m.parameters()}:
            return ''
        name = parts[0]
        body = s.body(m)
        if re.search(rf'\b(?!return\b|else\b|new\b)[A-Za-z_]\w*(?:\s*<[^;(){{}}]*>)?\s+{re.escape(name)}\s*[=;,)]', body):
            return ''
        field = self.field_of(m.owner.name, name)
        if not field:
            return ''
        defining = next(c.name for ancestor in self.lineage(m.owner.name) for c in self.classes.get(ancestor, [])
                        if any(f is field for f in c.fields))
        key = (defining, name)
        if key not in self._concrete:
            kinds, exact = set(), True
            if field.initializer.strip():
                made = re.match(r'\s*new\s+(\w+)', field.initializer)
                if made:
                    kinds.add(made.group(1))
                elif field.initializer.strip() not in {'null', 'NULL'}:
                    exact = False
            for node, qualifier, value in self.writes().get(name, []):
                owner = self.nodes[node][1].owner
                related = owner and defining in self.lineage(owner.name)
                if qualifier not in {'', 'this'}:
                    exact = False
                elif related:
                    made = re.match(r'new\s+(\w+)', value)
                    if made:
                        kinds.add(made.group(1))
                    elif value not in {'null', 'NULL'}:
                        exact = False
            self._concrete[key] = next(iter(kinds)) if exact and len(kinds) == 1 else ''
        return self._concrete[key] if self._concrete[key] in self.classes else ''

    def targets(self, i, expression):
        s, m = self.nodes[i]
        parts = re.sub(r'\s+', '', expression).split('.')
        name = parts[-1]
        exact = ''
        if len(parts) == 1:
            typ = m.owner.name if m.owner else ''
        else:
            typ = self.type_of('.'.join(parts[:-1]), self.envs[i])
            exact = self.concrete_type(i, '.'.join(parts[:-1]))
        result = []
        if typ:
            for ancestor in self.lineage(typ):
                result.extend(self.index.get((ancestor, name), []))
            # Typed virtual calls can reach authored derived implementations.
            # Static class-qualified and super calls do not dispatch downward.
            if len(parts) == 1 or (parts[0] not in self.classes and parts[0] != 'super'):
                for child in self.descendants.get(typ, []):
                    result.extend(self.index.get((child, name), []))
        # A receiver field that is only ever constructed as one exact class cannot
        # dispatch to the declared type's other derived implementations.
        if exact and typ:
            held = set(self.lineage(exact))
            result = [r for r in result if self.nodes[r][1].owner and self.nodes[r][1].owner.name in held]
        if len(parts) == 1 and not result:
            result.extend(self.globals.get(name, []))
        return sorted(set(result))


def symbol(m):
    return (m.owner.name + '.' if m.owner else '') + m.name


def loops(s, m):
    """Header plus body spans, including brace-less and do/while loops."""
    code = s.code
    for match in re.finditer(r'\b(for|foreach|while|do)\b', code[m.body_start:m.body_end]):
        start = m.body_start + match.start()
        pos = m.body_start + match.end()
        while pos < m.body_end and code[pos].isspace():
            pos += 1
        if match.group() != 'do':
            if code[pos:pos + 1] != '(':
                continue
            pos = es.matching_paren(code, pos) + 1
            while pos < m.body_end and code[pos].isspace():
                pos += 1
        end = es.matching_brace(code, pos) + 1 if code[pos:pos + 1] == '{' else code.find(';', pos) + 1
        if end > pos:
            yield start, end


def parameter_caps(model):
    """Small integer parameters only when every resolved authored call is literal.

    Native/external callers remain outside this closed authored approximation.
    No matching calls means no inferred bound.
    """
    candidates = {}
    for i, (s, m) in enumerate(model.nodes):
        # >/>= refusal guards bound the length exactly like != does (see bounded_string).
        if re.search(r'\.Length\s*\(\s*\)\s*(?:!=|>=|>)\s*[A-Za-z_]', s.body(m)):
            candidates[i] = [(pos, name) for pos, (typ, name, _) in enumerate(m.parameters()) if typ == 'int']
    values = {}
    names = {model.nodes[i][1].name for i in candidates}
    for i, (s, m) in enumerate(model.nodes):
        for call in _CALL.finditer(s.code, m.body_start, m.body_end):
            if call.group(1).split('.')[-1].strip() not in names:
                continue
            opening = s.code.find('(', call.start(), call.end())
            args = es.split_top(s.code[opening + 1:es.matching_paren(s.code, opening)], ',')
            for target in model.targets(i, call.group(1)):
                for pos, name in candidates.get(target, []):
                    arg = args[pos].strip() if pos < len(args) else ''
                    # A named constant argument is as fixed as a literal one.
                    values.setdefault((target, name), []).append((model.const_int(arg) if arg else 0) or 0)
    return {key: max(items) for key, items in values.items() if all(0 < n <= 1024 for n in items)}


def refusal_exit(text, start):
    """End offset of a branch that always returns, else -1.

    Either `return ...;` directly, or a brace-free block whose last statement is
    `return ...;`. Nested blocks are not followed, so a conditional return inside
    the branch cannot be mistaken for an unconditional one.
    """
    direct = re.match(r'\s*return\b[^;]*;', text[start:])
    if direct:
        return start + direct.end()
    block = re.match(r'\s*\{([^{}]*)\}', text[start:])
    if block and re.search(r'(?:^|;)\s*return\b[^;]*;\s*$', block.group(1)):
        return start + block.end()
    return -1


_FIELD_CAP = 65536   # two 32 KiB read chunks: one native pass over the field stays cheap
_FIELD_GET_CAP = 4096


def field_bound(model, owner, name):
    """Longest value a string field can hold, proven from every write, else None.

    Each write in the authored lineage must be a literal (<=1024), a ReadFile or
    FGets into the field with a constant byte cap, `field = field.Substring(a, n)`
    where n is refused above a constant before the copy, or `field = field + piece`
    where piece is a local filled only by a constant-cap ReadFile in the same
    method. Appends add that read cap to the largest non-append value. Anything
    else (parameters, other expressions, unknown receivers) is unbounded.
    """
    declared = model.field_of(owner, name) if owner else None
    if not declared or re.sub(r'\s+', '', declared.type) != 'string':
        return None
    ident = re.escape(name)
    assign = re.compile(rf'(?<![\w.])(?:this\s*\.\s*)?{ident}\s*(\+=|=(?!=))\s*([^;]*);')
    load = re.compile(rf'\b(?:ReadFile|FGets)\s*\(\s*[^,;()]+,\s*(?:this\s*\.\s*)?{ident}\s*,\s*([^;)]+)\)')
    base, grow, seen = 0, 0, False
    values = [f.initializer for ancestor in model.lineage(owner) for c in model.classes.get(ancestor, [])
              for f in c.fields if f.name == name and f.initializer]
    for value in values:
        if not re.fullmatch(r'\s*"[^"\n]*"\s*', value) or len(value) > 1026:
            return None
    for ancestor in model.lineage(owner):
        for c in model.classes.get(ancestor, []):
            for method in c.methods:
                text = c.source.body(method)
                for call in load.finditer(text):
                    cap = model.const_int(call.group(1).strip())
                    if not cap or cap > 32768:
                        return None
                    base, seen = max(base, cap), True
                for write in assign.finditer(text):
                    rhs = write.group(2).strip()
                    if re.fullmatch(r'"[^"\n]*"', rhs) and write.group(1) == '=' and len(rhs) <= 1026:
                        seen = True
                        continue
                    shape = (re.fullmatch(rf'(?:this\s*\.\s*)?{ident}\s*\.\s*Substring\s*\(\s*[^,]+,\s*({_IDENT}|\d+)\s*\)', rhs)
                             if write.group(1) == '=' else None)
                    if shape:
                        limit = guarded_limit(model, text[:write.start()], shape.group(1))
                        if not limit:
                            return None
                        base, seen = max(base, limit), True
                        continue
                    appended = (re.fullmatch(rf'(?:(?:this\s*\.\s*)?{ident}\s*\+\s*)?({_IDENT})', rhs)
                                if write.group(1) == '+=' else
                                re.fullmatch(rf'(?:this\s*\.\s*)?{ident}\s*\+\s*({_IDENT})', rhs))
                    if not appended:
                        return None
                    piece = appended.group(1)
                    reads = [model.const_int(r.group(1).strip()) for r in re.finditer(
                        rf'\b(?:ReadFile|FGets)\s*\(\s*[^,;()]+,\s*{re.escape(piece)}\s*,\s*([^;)]+)\)', text)]
                    if (len(reads) != 1 or not reads[0] or reads[0] > 32768
                            or re.search(rf'(?<![\w.]){re.escape(piece)}\s*(?:\+=|=(?!=))', text)):
                        return None
                    grow, seen = max(grow, reads[0]), True
    return base + grow if seen else None


def guarded_limit(model, before, variable):
    """Constant ceiling for an int local refused above it before this point."""
    if variable.isdecimal():
        return int(variable)
    # The declaration is the only write: a later reassignment could escape the guard.
    if len(re.findall(rf'(?<![\w.]){variable}\s*(?:\+=|-=|\*=|=(?!=))', before)) > 1:
        return 0
    for guard in re.finditer(r'\bif\s*\(', before):
        opening = before.find('(', guard.start(), guard.end())
        closing = es.matching_paren(before, opening)
        if closing < 0 or '&&' in before[opening + 1:closing] or refusal_exit(before, closing + 1) < 0:
            continue
        for term in before[opening + 1:closing].split('||'):
            bound = re.fullmatch(rf'\s*{variable}\s*>\s*(\w+)\s*', term)
            if bound and model.const_int(bound.group(1)):
                return model.const_int(bound.group(1))
    return 0


def bounded_string(s, m, receiver, offset, caps, model=None, index=None):
    """Recognize small literal values and early length guards, not file caps."""
    body = s.code[m.body_start:offset]
    name = re.escape(receiver)
    # A literal assignment is bounded only if it is the sole write to the name.
    writes = list(re.finditer(rf'(?<![\w.]){name}\s*(\+=|=(?!=))\s*([^;]*);', body))
    file_loaded = re.search(rf'\b(?:ReadFile|FGets)\s*\([^;]*\b{name}\b[^;]*\)', body)
    if (not file_loaded and len(writes) == 1 and len(writes[0].group(2)) <= 1026
            and re.fullmatch(r'\s*"[^"\n]*"\s*', writes[0].group(2))):
        return True
    # A local whose every write is a short value is bounded: a constant-length
    # Substring copy (<=1024), a one-character string Get, or an HCTextWindow
    # At/Range piece. Parameters and fields are excluded because the writes seen
    # here may be conditional, leaving the incoming unbounded value reachable.
    if (model is not None and not file_loaded and writes and receiver.isidentifier()
            and receiver not in {n for _, n, _ in m.parameters()}
            and not (m.owner and model.field_of(m.owner.name, receiver))
            and all(w.group(1) == '=' and small_value(model, index, w.group(2)) for w in writes)):
        return True
    # A direct disjunct of a refusal guard suffices; a conjunct does not.
    # Reassignment after a guard invalidates the bound.
    for guard in re.finditer(r'\bif\s*\(', body):
        opening = body.find('(', guard.start(), guard.end())
        closing = es.matching_paren(body, opening)
        condition = body[opening + 1:closing]
        exit_end = refusal_exit(body, closing + 1)
        if '&&' in condition or exit_end < 0:
            continue
        # Writes inside the refusing branch never reach the guarded scan.
        if any(w.start() > closing and w.start() >= exit_end for w in writes):
            continue
        for term in condition.split('||'):
            # >= N refuses every length from N up, so it bounds just as > N does.
            bound = re.fullmatch(rf'\s*{name}\.Length\s*\(\s*\)\s*(>=|>|!=)\s*({_IDENT}|\d+)\s*', term)
            if bound:
                if bound.group(2).isdecimal():
                    limit = int(bound.group(2))
                else:
                    # Parameter caps first, then a named constant (static const int).
                    limit = caps.get(bound.group(2)) or (model.consts.get(bound.group(2), 0) if model else 0)
                if 0 < limit <= 1024:
                    return True
    return False


def small_value(model, i, rhs):
    """True when an assigned expression is a short string by construction."""
    call = re.fullmatch(rf'({_CHAIN})\s*\.\s*(Substring|Get|At|Range)\s*\((.*)\)', rhs.strip(), re.S)
    if not call:
        return False
    typ = re.sub(r'\s+', '', model.type_of(re.sub(r'\s+', '', call.group(1)), model.envs[i]))
    args = es.split_top(call.group(3), ',')
    if call.group(2) == 'Substring':
        # Copies exactly the requested constant number of bytes, whatever the receiver.
        return typ == 'string' and len(args) == 2 and 0 < (model.const_int(args[1]) or 0) <= 1024
    if call.group(2) == 'Get':
        return typ == 'string' and len(args) == 1   # one character
    if typ != 'HCTextWindow':
        return False
    # HCTextWindow pieces: At is one character, Range a constant-sized copy.
    return call.group(2) == 'At' or (len(args) == 2 and 0 < (model.const_int(args[1]) or 0) <= 1024)


def bulk_copy(s, start, end, call):
    """Chunked Substring with an explicit <=4096 clamp and matching stride."""
    if call.group(2) != 'Substring':
        return False
    opening = s.code.find('(', call.start(), call.end())
    args = es.split_top(s.code[opening + 1:es.matching_paren(s.code, opening)], ',')
    if len(args) != 2 or not re.fullmatch(r'\s*' + _IDENT + r'\s*', args[1]):
        return False
    piece = args[1].strip()
    code = s.code[start:end]
    clamp = rf'if\s*\(\s*{piece}\s*>\s*(\d+)\s*\)\s*{{\s*{piece}\s*=\s*\1\s*;\s*}}'
    clamps = list(re.finditer(clamp, s.code[start:call.start()]))
    if clamps and re.search(rf'\b{piece}\s*(?:\+=|=(?!=))', s.code[start + clamps[-1].end():call.start()]):
        return False
    stride = re.search(rf'\b({_IDENT})\s*=\s*\1\s*\+\s*{piece}\s*;', code)
    return bool(clamps and int(clamps[-1].group(1)) <= 4096 and stride
                and re.search(rf'\b{stride.group(1)}\b', args[0]))


def small_loop(s, start):
    """Recognize direct literal upper conditions, not configured/caller bounds."""
    match = re.match(r'(for|while)\s*\(', s.code[start:])
    if not match:
        return False
    opening = start + match.end() - 1
    header = s.code[opening + 1:es.matching_paren(s.code, opening)]
    if match.group(1) == 'for':
        parts = header.split(';')
        if len(parts) != 3:
            return False
        header = parts[1]
    return bool('||' not in header and re.search(
        rf'\b{_IDENT}\s*<=?\s*(?:[0-9]|1[0-6])\b(?!\s*[\w.+*/-])', header))


def nested_scans(model, i, spans):
    s, m = model.nodes[i]
    active = [(a, b) for a, b in spans if not small_loop(s, a)]
    sites = []
    for start, end in active:
        if not any(a < start < b for a, b in active):
            continue
        opening = s.code.find('(', start, end)
        closing = es.matching_paren(s.code, opening)
        header = s.code[opening + 1:closing]
        # foreach's receiver or a for/while collection Count/Get header.
        receivers = re.findall(rf':\s*({_CHAIN})\s*$', header)
        receivers.extend(re.findall(rf'\b({_CHAIN})\s*\.\s*(?:Count|Get|GetKey|GetElement)\s*\(', header))
        for receiver in dict.fromkeys(re.sub(r'\s+', '', r) for r in receivers):
            typ = re.sub(r'\s+', '', model.type_of(receiver, model.envs[i]))
            if (typ.startswith(('array<', 'map<', 'set<')) or typ == 'set') and '==' in s.code[closing + 1:end]:
                sites.append((start, receiver + '.loop'))
    for call in _ARRAY_SCAN.finditer(s.code, m.body_start, m.body_end):
        receiver = re.sub(r'\s+', '', call.group(1))
        typ = re.sub(r'\s+', '', model.type_of(receiver, model.envs[i]))
        if typ.startswith('array<') and any(a <= call.start() < b for a, b in active):
            sites.append((call.start(), receiver + '.' + call.group(2)))
    counts = {}
    for offset, key in sorted(sites):
        counts[key] = counts.get(key, 0) + 1
        yield Finding('HC-P004', s.rel, s.line_of(offset), symbol(m),
                      f'{key}#{counts[key]}', 'O(n*m) scan; build a map/set index outside the loop')


_RESET = re.compile(rf'(?<![\w.])({_CHAIN})\s*=(?!=)\s*(?:false|null|NULL|0)\s*;')
_ASSIGN = re.compile(rf'(?<![\w.])({_CHAIN})\s*=(?!=)\s*([^;]*);')
_EXIT = re.compile(r'\b(?:return|continue|break)\b')
# Any write to a field: plain or compound assignment, increment or decrement.
_WRITE = re.compile(rf'(?<![\w.])({_CHAIN})\s*(?:[-+*/%|&^]|<<|>>)?=(?!=)|(?<![\w.])({_CHAIN})\s*(?:\+\+|--)|(?:\+\+|--)\s*({_CHAIN})')
_TICK_TIME = r'GetGame\s*\(\s*\)\s*\.\s*GetTickTime\s*\(\s*\)'


def _latch_field(model, i, expression, scalars=False):
    """(defining class, field name, type) of a bool/ref latch field, else None.

    Locals, parameters, ints, floats, strings and vectors are not latches unless
    scalars is set (the retry-window check resolves its float window field)."""
    s, m = model.nodes[i]
    parts = re.sub(r'\s+', '', expression).split('.')
    if parts[0] == 'this':
        parts = parts[1:]
    if len(parts) == 2 and parts[0] in model.classes:
        owner = parts[0]
    elif len(parts) == 1 and m.owner:
        owner = m.owner.name
        if parts[0] in {n for _, n, _ in m.parameters()} or re.search(
                rf'\b(?!return\b|else\b|new\b)[A-Za-z_]\w*(?:\s*<[^;(){{}}]*>)?\s+{re.escape(parts[0])}\s*[=;]', s.body(m)):
            return None
    else:
        return None
    field = model.field_of(owner, parts[-1])
    if not field or (not scalars and field.type in {'int', 'float', 'string', 'vector', 'typename'}):
        return None
    defining = next(c.name for ancestor in model.lineage(owner) for c in model.classes.get(ancestor, [])
                    if any(f is field for f in c.fields))
    return defining, field.name, field.type


def once_spans(model, i):
    """Code spans of method i that run at most once per latch, as (start, end, latch).

    A load-once latch is a bool/ref field that is tested first and then set by an
    unconditional statement with no return/continue/break before it, so the guarded
    code cannot repeat unless something resets the field (the caller checks resets):
      if (!latch) { ...; latch = true/new/call(); ... }          wrapped block, any depth
      if (latch [|| more]) { return ...; }  latch = true; ...    early return, method level
    Anything else, including a conditional set, stays a per-call path."""
    s, m = model.nodes[i]
    code = s.code
    spans = []

    def statement(pos):
        """Span (start, end) of the block or single statement starting near pos."""
        while pos < m.body_end and code[pos].isspace():
            pos += 1
        if code[pos:pos + 1] == '{':
            return pos + 1, es.matching_brace(code, pos)
        return pos, code.find(';', pos) + 1

    def sets_latch(start, end, key):
        spelled = rf'(?<![\w.])(?:this\s*\.\s*|{re.escape(key[0])}\s*\.\s*)?{re.escape(key[1])}\s*=(?!=)\s*([^;]*);'
        for assign in re.finditer(spelled, code[start:end]):
            before = code[start:start + assign.start()]
            if before.count('{') != before.count('}') or _EXIT.search(before):
                continue
            value = assign.group(1).strip()
            if (value == 'true') if key[2] == 'bool' else (value not in {'null', 'NULL', 'false', '0', ''}):
                return True
        return False

    def retry_window(start, end, key):
        """Retry-until-success latch with a time window (the attempt repeats at most once per window):
          if (!latch) { float now = GetGame().GetTickTime(); if (now >= window) { if (attempt()) { latch = true; }
          else { window = now + K; } } }
        now must come from the engine tick clock, window is a float field and K a positive literal or
        static const number. Returns the window field (defining class, name), else None. The caller
        rejects the window when another tick-path write reaches the window or the latch field."""
        block = code[start:end]
        spelled = (rf'\s*float\s+(\w+)\s*=\s*{_TICK_TIME}\s*;\s*if\s*\(\s*\1\s*>=\s*({_CHAIN})\s*\)\s*\{{\s*'
                   rf'if\s*\([^{{}}]*\)\s*\{{\s*(?:this\s*\.\s*)?{re.escape(key[1])}\s*=\s*true\s*;\s*\}}\s*'
                   rf'else\s*\{{\s*(?:this\s*\.\s*)?\2\s*=\s*\1\s*\+\s*([\w.]+)\s*;\s*\}}\s*\}}\s*')
        found = re.fullmatch(spelled, block)
        if not found or key[2] != 'bool' or not m.owner:
            return None
        window = _latch_field(model, i, found.group(2), True)
        if not window or window[2] != 'float':
            return None
        step = found.group(3)
        if re.fullmatch(r'\d+(?:\.\d+)?', step):
            return window[:2] if float(step) > 0 else None
        constant = model.field_of(m.owner.name, step)
        if (constant and {'static', 'const'} <= set(constant.modifiers)
                and re.fullmatch(r'\d+(?:\.\d+)?', constant.initializer.strip() or 'x')
                and float(constant.initializer.strip()) > 0):
            return window[:2]
        return None

    for guard in re.finditer(r'\bif\s*\(', code[m.body_start + 1:m.body_end]):
        start = m.body_start + 1 + guard.start()
        opening = code.find('(', start)
        closing = es.matching_paren(code, opening)
        condition = code[opening + 1:closing]
        a, b = statement(closing + 1)
        wrapped = re.fullmatch(rf'\s*(?:!\s*({_CHAIN})|({_CHAIN})\s*==\s*(?:false|null|NULL))\s*', condition)
        if wrapped:
            latch = _latch_field(model, i, wrapped.group(1) or wrapped.group(2))
            if latch and sets_latch(a, b, latch):
                spans.append((a, b, latch))
            elif latch:
                window = retry_window(a, b, latch)
                if window:
                    spans.append((a, b, latch + ('window',) + window))
            continue
        # Early-return form, only as a top-level statement of the method.
        before = code[m.body_start + 1:start]
        if before.count('{') != before.count('}'):
            continue
        if not re.fullmatch(r'\s*return\b[^;]*;\s*', code[a:b]):
            continue
        after = b + 1 if code[b:b + 1] == '}' else b
        for term in condition.split('||'):
            held = re.fullmatch(rf'\s*(?:({_CHAIN})|({_CHAIN})\s*!=\s*(?:null|NULL|false)|({_CHAIN})\s*==\s*true)\s*', term)
            if not held:
                continue
            latch = _latch_field(model, i, next(g for g in held.groups() if g))
            if latch and sets_latch(after, m.body_end, latch):
                spans.append((after, m.body_end, latch))
                break
    # Consume form: `if (!latch) { return ...; }` at method level, later a method-level
    # `latch = null/false;`. Code after the last exit before that reset runs only on the
    # pass that consumes the latch, including the rest of the method; a later pass leaves at the guard (unless the latch is
    # armed again on a tick path, which the caller checks).
    for guard in re.finditer(r'\bif\s*\(', code[m.body_start + 1:m.body_end]):
        start = m.body_start + 1 + guard.start()
        before = code[m.body_start + 1:start]
        if before.count('{') != before.count('}'):
            continue
        opening = code.find('(', start)
        closing = es.matching_paren(code, opening)
        entry = re.fullmatch(rf'\s*(?:!\s*({_CHAIN})|({_CHAIN})\s*==\s*(?:false|null|NULL))\s*', code[opening + 1:closing])
        a, b = statement(closing + 1)
        if not entry or not re.fullmatch(r'\s*return\b[^;]*;\s*', code[a:b]):
            continue
        latch = _latch_field(model, i, entry.group(1) or entry.group(2))
        if not latch:
            continue
        spelled = rf'(?<![\w.])(?:this\s*\.\s*|{re.escape(latch[0])}\s*\.\s*)?{re.escape(latch[1])}\s*=(?!=)\s*(?:null|NULL|false|0)\s*;'
        after = b + 1 if code[b:b + 1] == '}' else b
        for consume in re.finditer(spelled, code[after:m.body_end]):
            middle = code[after:after + consume.start()]
            if middle.count('{') != middle.count('}'):
                continue
            exits = list(_EXIT.finditer(middle))
            floor = after
            if exits:
                tail = middle.find(';', exits[-1].end())
                if tail < 0:
                    continue
                floor = after + tail + 1
                if code[floor:].lstrip().startswith('}'):
                    floor = code.find('}', floor) + 1
                if re.match(r'\s*else\b', code[floor:]):
                    continue
            spans.append((floor, m.body_end, latch + ('consume',)))
            break
    return spans


def terminal_print(s, call):
    """Print statement directly followed by return/break leaves the loop at once.

    It can run at most once per call, so it is not a per-item log line."""
    opening = s.code.find('(', call.start(), call.end())
    closing = es.matching_paren(s.code, opening)
    return re.match(r'\s*;\s*(?:return|break)\b', s.code[closing + 1:]) is not None


def slot_registrations(sources, root):
    """Cross-file checks on authored sources; no execution of report Python."""
    by_name = {}
    for s in sources:
        if s.rel.startswith('mods/HollowCountry/scripts/'):
            by_name.setdefault(s.path.name, []).append(s)

    def named(filename):
        return by_name.get(filename, [])

    registry = root / 'tools/validate/shared_settings.json'
    weights = {}
    if registry.is_file():
        for row in json.loads(registry.read_text(encoding='utf-8')):
            key = row.get('key', '')
            if key.startswith('Performance.TickWeight_'):
                weights[key.removeprefix('Performance.TickWeight_')] = row
    for s in named('HCUnitBudget.c'):
        declarations = list(re.finditer(r'\bstatic\s+const\s+int\s+HC_WORK_(\w+)\s*=\s*(\d+)\s*;', s.code))
        slots = [d for d in declarations if d[1] not in {'CONSUMERS', 'UNBOUNDED'}]
        count = next((d for d in declarations if d[1] == 'CONSUMERS'), None)
        registrations = {}
        for call in re.finditer(r'\bHCRegisterConsumer\s*\(\s*HC_WORK_(\w+)\s*,\s*("[^"\n]*")\s*,\s*(\d+)\s*\)', s.code):
            label = json.loads(s.text[call.start(2):call.end(2)])
            registrations.setdefault(call[1], []).append((label, int(call[3])))
        declared = {slot[1] for slot in slots}
        seen_values = set()
        for slot in slots:
            name = slot[1]
            entries = registrations.get(name, [])
            row = weights.get(name, {})
            pieces = {
                'table': len(entries) == 1 and entries[0][0] == name and 1 <= entries[0][1] <= 64,
                'settings': row.get('type') == 'int' and row.get('owner') == 'HCPerfConfig'
                            and len(entries) == 1 and row.get('default') == entries[0][1]
                            and row.get('min') == 1 and row.get('max') == 64,
                'unique': int(slot[2]) not in seen_values,
            }
            seen_values.add(int(slot[2]))
            for piece, present in pieces.items():
                if not present:
                    yield Finding('HC-P007', s.rel, s.line_of(slot.start()), 'HCUnitBudget',
                                  f'HC_WORK_{name}:{piece}', f'HC_WORK_{name} missing {piece} registration (see PERFORMANCE_PRACTICES)')
        for name in sorted((registrations.keys() | weights.keys()) - declared):
            yield Finding('HC-P007', s.rel, 1, 'HCUnitBudget', f'HC_WORK_{name}:undeclared',
                          f'consumer {name} registered without an HC_WORK slot')
        if slots and (count is None or int(count[2]) != len(slots) or seen_values != set(range(int(count[2])))):
            yield Finding('HC-P007', s.rel, s.line_of(count.start() if count else slots[0].start()),
                          'HCUnitBudget', 'HC_WORK_CONSUMERS:capacity',
                          'HC_WORK_CONSUMERS must match contiguous unique consumer slots')


def private_budget(model, i, receiver):
    """True when a budget receiver is a module-owned instance, never the shared pool.

    The receiver is one identifier (optionally this.): a local or a field of declared
    type HCUnitBudget whose every initializer and assignment in the authored sources
    is `new` of a budget type or null, with no HCSetProfile call on it. Such an
    instance has no other consumer to be fair to and no attribution table (only the
    shared core budget gets a profile), so its HCTake is that module's own pacing
    limit. Parameters, aliases of HCServer.HCTickWork() and anything unprovable stay
    flagged.
    """
    s, m = model.nodes[i]
    parts = re.sub(r'\s+', '', receiver).split('.')
    if parts[0] == 'this':
        parts = parts[1:]
    if len(parts) != 1:
        return False
    name = parts[0]
    assign = re.compile(rf'(?<![\w.])(?:this\s*\.\s*)?{name}\s*=(?!=)\s*([^;]*);')
    profile = re.compile(rf'\b{name}\s*\.\s*HCSetProfile\b')

    def owned(value):
        value = value.strip()
        made = re.match(r'new\s+(\w+)', value)
        return value == 'null' or bool(made and 'HCUnitBudget' in model.lineage(made.group(1)))

    body = s.body(m)
    if re.search(rf'\bHCUnitBudget\s+{name}\b', body):
        values = [a.group(1) for a in assign.finditer(body)]
        return bool(values) and all(owned(v) for v in values) and not profile.search(body)
    if not m.owner or name in {p[1] for p in m.parameters()}:
        return False
    declared = model.field_of(m.owner.name, name)
    if not declared or 'HCUnitBudget' not in model.lineage(declared.type):
        return False
    values = []
    for ancestor in model.lineage(m.owner.name):
        for c in model.classes.get(ancestor, []):
            values.extend(f.initializer for f in c.fields if f.name == name and f.initializer)
            for method in c.methods:
                text = c.source.body(method)
                if profile.search(text):
                    return False
                values.extend(a.group(1) for a in assign.finditer(text))
    return bool(values) and all(owned(v) for v in values)


def raw_budget_calls(model, i):
    """Typed budget calls plus the known shared accessor's call-result chain."""
    s, m = model.nodes[i]
    if (s.rel == 'mods/HollowCountry/scripts/4_World/Core/HCUnitBudget.c'
            and m.owner and m.owner.name == 'HCUnitBudget'):
        return
    count = 0
    for call in re.compile(r'\bHCTake\s*\(').finditer(s.code, m.body_start, m.body_end):
        prefix = s.code[m.body_start:call.start()]
        receiver = re.search(rf'({_CHAIN})\s*\.\s*$', prefix)
        typ = model.type_of(receiver.group(1), model.envs[i]) if receiver else ''
        if not receiver and not prefix.rstrip().endswith('.') and m.owner:
            typ = m.owner.name
        shared = re.search(r'\bHCServer\s*\.\s*(?:Get\s*\(\s*\)\s*\.\s*)?'
                           r'HCTickWork\s*\(\s*\)\s*\.\s*$', prefix)
        if 'HCUnitBudget' not in model.lineage(typ) and not shared:
            continue
        if not shared and receiver and private_budget(model, i, receiver.group(1)):
            continue
        count += 1
        yield Finding('HC-P010', s.rel, s.line_of(call.start()), symbol(m),
                      f'HCTake#{count}',
                      'raw HCTake bypasses consumer fairness/attribution; use HCTakeFor with an owned HC_WORK slot')


# Per-visit file operation budget of a staged step, and the byte ceiling of one read.
STAGE_OPS = 1
STAGE_READ_BYTES = 65536
# Constant-trip loops that cannot make a startup pass "multi-file": per loop and per nest.
TRIP_LOOP_CAP = 16
TRIP_PRODUCT_CAP = 64
UNBOUNDED = 1 << 20


def trip_count(model, s, start, end):
    """Iteration bound of a counting for-loop with a constant limit, else None.

    Recognized only for: for (int i = A; i < N | i <= N; i++ | ++i | i += 1) with literal A
    and a literal or static const int N, where the body never writes i. Anything else
    (while, foreach, configured or computed bounds, other strides) has no constant bound."""
    match = re.match(r'for\s*\(', s.code[start:end])
    if not match:
        return None
    opening = start + match.end() - 1
    closing = es.matching_paren(s.code, opening)
    parts = es.split_top(s.code[opening + 1:closing], ';')
    if len(parts) != 3:
        return None
    init = re.fullmatch(rf'\s*(?:int\s+)?({_IDENT})\s*=\s*(\d+)\s*', parts[0])
    if not init:
        return None
    var = init.group(1)
    # Conjuncts all have to hold, so one constant bound on the counter bounds the loop.
    bounds = [re.fullmatch(rf'\s*{var}\s*(<|<=)\s*({_CHAIN}|\d+)\s*', term) for term in parts[1].split('&&')]
    bounds = [b for b in bounds if b and model.const_int(b.group(2)) is not None]
    cond = min(bounds, key=lambda b: model.const_int(b.group(2)) + (b.group(1) == '<='), default=None) if '||' not in parts[1] else None
    step = re.fullmatch(rf'\s*(?:{var}\s*\+\+|\+\+\s*{var}|{var}\s*\+=\s*1|{var}\s*=\s*{var}\s*\+\s*1)\s*', parts[2])
    if not cond or not step:
        return None
    limit = model.const_int(cond.group(2))
    if re.search(rf'(?<![\w.]){var}\s*(?:=(?!=)|[-+*/]=|\+\+|--)|(?:\+\+|--)\s*{var}\b', s.code[closing + 1:end]):
        return None
    return max(0, limit - int(init.group(2)) + (1 if cond.group(1) == '<=' else 0))


def multiplier(model, s, spans, offset, base):
    """Iterations of the loops around offset, multiplied onto base; UNBOUNDED when any
    enclosing loop lacks a constant trip count within TRIP_LOOP_CAP or the nest exceeds
    TRIP_PRODUCT_CAP."""
    result = base
    for a, b in spans:
        if not a <= offset < b:
            continue
        trips = trip_count(model, s, a, b)
        if trips is None or trips > TRIP_LOOP_CAP:
            return UNBOUNDED
        result *= max(trips, 1)
    return UNBOUNDED if result > TRIP_PRODUCT_CAP else result


def _statements(s, pos, end):
    """Parse code[pos:end] into statement nodes: block, if, loop or simple (a span)."""
    code = s.code
    nodes = []
    while True:
        while pos < end and code[pos].isspace():
            pos += 1
        if pos >= end:
            return nodes
        node, after = _statement(s, pos, end)
        nodes.append(node)
        pos = max(after, pos + 1)


def _statement(s, pos, end):
    code = s.code
    if code[pos] == '{':
        close = es.matching_brace(code, pos)
        return ('block', _statements(s, pos + 1, close)), close + 1
    keyword = re.match(r'(if|for|foreach|while|switch)\b\s*\(', code[pos:end])
    if keyword:
        opening = pos + keyword.end() - 1
        closing = es.matching_paren(code, opening)
        head = (opening, closing)
        body, after = _statement_at(s, closing + 1, end)
        if keyword.group(1) == 'if':
            other = after
            while other < end and code[other].isspace():
                other += 1
            if re.match(r'else\b', code[other:end]):
                alternative, after = _statement_at(s, other + 4, end)
                return ('if', head, body, alternative), after
            return ('if', head, body, None), after
        if keyword.group(1) == 'switch':
            return ('block', [('simple', pos, closing + 1)] + ([body] if body else [])), after
        return ('loop', head, body), after
    if re.match(r'do\b', code[pos:end]):
        body, after = _statement_at(s, pos + 2, end)
        tail = re.compile(r'\s*while\s*\(').match(code, after)
        if tail:
            closing = es.matching_paren(code, tail.end() - 1)
            return ('loop', (tail.end() - 1, closing), body), code.find(';', closing) + 1
        return ('loop', (pos, pos), body), after
    depth = 0
    cursor = pos
    while cursor < end:
        if code[cursor] in '({[':
            depth += 1
        elif code[cursor] in ')}]':
            depth -= 1
        elif code[cursor] == ';' and depth <= 0:
            break
        cursor += 1
    return ('simple', pos, cursor + 1), cursor + 1


def _statement_at(s, pos, end):
    while pos < end and s.code[pos].isspace():
        pos += 1
    if pos >= end:
        return None, pos
    return _statement(s, pos, end)


def _leaves(s, node):
    """True when every path through the node ends in a return."""
    kind = node[0]
    if kind == 'simple':
        return re.match(r'return\b', s.code[node[1]:node[2]].lstrip()) is not None
    if kind == 'block':
        return any(_leaves(s, n) for n in node[1])
    if kind == 'if':
        return node[3] is not None and node[2] is not None and _leaves(s, node[2]) and _leaves(s, node[3])
    return False


class StepCost:
    """Maximum file operations one call of a method can perform, UNBOUNDED when no
    constant bound exists.

    Statement structure decides the sum: sequential statements add, if/else branches
    take the larger arm, a branch that always returns excludes the code after it, and any
    loop whose header or body can reach a file operation is UNBOUNDED. A ReadFile counts
    one operation only when its length argument is a constant <= STAGE_READ_BYTES.
    A call costs the largest cost among its resolved targets, a stage boundary
    (HCStagedSaveImage Begin/HCStepImage/HCRefreshIntent) costs one operation, and
    calls or sites inside once-only (load-once latch) spans cost nothing. A recursive
    call into a method that can reach file I/O is UNBOUNDED."""

    def __init__(self, model, edges, ios, boundary, skipped, io_reaching):
        self.model, self.edges, self.ios = model, edges, ios
        self.boundary, self.skipped, self.io_reaching = boundary, skipped, io_reaching
        self.memo, self.parsed, self.seqmemo = {}, {}, {}
        self.at = [{} for _ in model.nodes]
        for i, pairs in enumerate(edges):
            for offset, target in pairs:
                self.at[i].setdefault(offset, []).append(target)

    def live(self, i, offset):
        return not any(a <= offset < b for a, b in self.skipped.get(i, ()))

    def method(self, i, stack=()):
        if self.boundary(i):
            return STAGE_OPS
        if i not in self.io_reaching:
            return 0
        if i in self.memo:
            return self.memo[i]
        if i in stack:
            return UNBOUNDED
        s, m = self.model.nodes[i]
        if i not in self.parsed:
            self.parsed[i] = _statements(s, m.body_start + 1, m.body_end)
        cost = self.sequence(s, i, self.parsed[i], 0, stack + (i,))
        # A result computed through a recursion cut is not final for callers up the stack.
        if not any(t in stack for t in {t for _, t in self.edges[i]}):
            self.memo[i] = cost
        return cost

    def span(self, s, i, start, end, stack):
        cost = 0
        for offset, name in self.ios[i]:
            if start <= offset < end and self.live(i, offset):
                weight = 1
                if name == 'ReadFile':
                    opening = s.code.find('(', offset)
                    args = es.split_top(s.code[opening + 1:es.matching_paren(s.code, opening)], ',')
                    limit = self.model.const_int(args[2]) if len(args) >= 3 else None
                    if limit is None or limit > STAGE_READ_BYTES:
                        weight = UNBOUNDED
                cost += weight
        for offset, targets in self.at[i].items():
            if start <= offset < end and self.live(i, offset):
                cost += max(self.method(t, stack) for t in targets)
        return min(cost, UNBOUNDED)

    def node(self, s, i, n, stack):
        kind = n[0]
        if kind == 'simple':
            return self.span(s, i, n[1], n[2], stack)
        if kind == 'block':
            return self.sequence(s, i, n[1], 0, stack)
        head = self.span(s, i, n[1][0], n[1][1] + 1, stack)
        if kind == 'loop':
            inner = self.node(s, i, n[2], stack) if n[2] else 0
            return UNBOUNDED if head + inner else 0
        first = self.node(s, i, n[2], stack) if n[2] else 0
        second = self.node(s, i, n[3], stack) if n[3] else 0
        return min(UNBOUNDED, head + max(first, second))

    def sequence(self, s, i, nodes, k, stack):
        key = (id(nodes), k)
        if key not in self.seqmemo:
            self.seqmemo[key] = self._sequence(s, i, nodes, k, stack)
        return self.seqmemo[key]

    def _sequence(self, s, i, nodes, k, stack):
        if k >= len(nodes):
            return 0
        n = nodes[k]
        rest = lambda: self.sequence(s, i, nodes, k + 1, stack)
        if n[0] == 'if':
            head = self.span(s, i, n[1][0], n[1][1] + 1, stack)

            def arm(x):
                if x is None:
                    return rest()
                return self.node(s, i, x, stack) + (0 if _leaves(s, x) else rest())
            return min(UNBOUNDED, head + max(arm(n[2]), arm(n[3])))
        cost = self.node(s, i, n, stack)
        return cost if _leaves(s, n) else min(UNBOUNDED, cost + rest())


def advances_state(model, i):
    """True when the method assigns a field of its own class (a cursor or phase)."""
    s, m = model.nodes[i]
    if not m.owner:
        return False
    local = {n for _, n, _ in m.parameters()}
    for write in re.finditer(rf'(?<![\w.])(?:this\s*\.\s*)?({_IDENT})\s*(?:=(?!=)|\+=|-=|\+\+)', s.body(m)):
        name = write.group(1)
        if name not in local and model.field_of(m.owner.name, name) and not re.search(
                rf'\b(?!return\b|else\b|new\b)[A-Za-z_]\w*(?:\s*<[^;(){{}}]*>)?\s+{name}\s*[=;]', s.body(m)):
            return True
    return False


def reaching(model, edges, ios, boundary):
    """Nodes that can reach a file operation or a stage boundary, over the call edges."""
    reverse = [[] for _ in model.nodes]
    for i, pairs in enumerate(edges):
        for _, target in pairs:
            reverse[target].append(i)
    seen = {i for i in range(len(model.nodes)) if ios[i] or boundary(i)}
    queue = deque(seen)
    while queue:
        for caller in reverse[queue.popleft()]:
            if caller not in seen:
                seen.add(caller)
                queue.append(caller)
    return seen



def startup_file_loops(model, edges, ios, loop_spans, skipped=None):
    """Visit each (method, iteration multiplier) state once, retaining a shortest witness.

    Loops with a constant trip count within TRIP_LOOP_CAP (nest product within
    TRIP_PRODUCT_CAP) are bounded and do not make a pass multi-file. Once-only code (a
    load-once latch in `skipped`) and calls into a lifecycle OnStop override, which runs
    at shutdown and never on the OnStart path, are not followed."""
    skipped = skipped or {}
    roots = [i for i, (_, m) in enumerate(model.nodes) if m.name == 'OnStart']
    queue = deque((i, 1, (i,)) for i in roots)
    reached = {(i, 1) for i in roots}
    reported = set()
    while queue:
        i, mult, chain = queue.popleft()
        s, m = model.nodes[i]

        def live(offset):
            return not any(a <= offset < b for a, b in skipped.get(i, ()))

        counts = {}
        for offset, operation in ios[i]:
            if operation not in {'OpenFile', 'FileExist', 'CopyFile', 'DeleteFile'} and not operation.startswith('JsonFileLoader.'):
                continue
            counts[operation] = counts.get(operation, 0) + 1
            if (not live(offset) or multiplier(model, s, loop_spans[i], offset, mult) < UNBOUNDED
                    or (i, offset, operation) in reported):
                continue
            reported.add((i, offset, operation))
            witness = ' -> '.join(symbol(model.nodes[n][1]) for n in chain)
            yield Finding('HC-P009', s.rel, s.line_of(offset), symbol(m),
                          f'{operation}#{counts[operation]}',
                          f'{operation} in a synchronous startup loop via {witness}; enqueue bounded startup work')
        if len(chain) - 1 >= MAX_DEPTH:
            continue
        for offset, target in edges[i]:
            if not live(offset) or model.nodes[target][1].name == 'OnStop':
                continue
            state = (target, multiplier(model, s, loop_spans[i], offset, mult))
            if state not in reached:
                reached.add(state)
                queue.append((*state, chain + (target,)))


def capped_retry(model, i, offset, callbacks):
    """True when the scheduling call at offset only runs under a constant retry cap.

    The call sits in the then-branch of `if (counter < N)` (conjuncts allowed, no ||),
    where counter is an int field of the scheduling class, N is a literal or static const
    int <= TRIP_LOOP_CAP, the branch increments the counter before the call, and no
    callback target assigns the counter other than by increment. Such a re-arm is a
    finite retry sequence of one-shot callbacks, not a repeating tick."""
    s, m = model.nodes[i]
    if not m.owner:
        return False
    code = s.code
    for guard in re.finditer(r'\bif\s*\(', code[m.body_start:offset]):
        opening = m.body_start + guard.end() - 1
        closing = es.matching_paren(code, opening)
        if closing > offset:
            continue
        pos = closing + 1
        while code[pos].isspace():
            pos += 1
        if code[pos] != '{':
            continue
        end = es.matching_brace(code, pos)
        if not pos < offset < end or '||' in code[opening:closing]:
            continue
        for term in code[opening + 1:closing].split('&&'):
            bound = re.fullmatch(rf'\s*({_IDENT})\s*(<|<=)\s*({_CHAIN}|\d+)\s*', term)
            if not bound:
                continue
            counter, limit = bound.group(1), model.const_int(bound.group(3))
            field = model.field_of(m.owner.name, counter)
            if not field or field.type != 'int' or limit is None or not 0 < limit <= TRIP_LOOP_CAP:
                continue
            bump = rf'(?<![\w.])(?:this\s*\.\s*)?{counter}\s*(?:\+\+|\+=\s*1\b|=\s*{counter}\s*\+\s*1\b)|\+\+\s*{counter}\b'
            assign = rf'(?<![\w.])(?:this\s*\.\s*)?{counter}\s*(?:=(?!=)|[-*/]=)(?!\s*{counter}\s*\+\s*1\b)'
            if re.search(bump, code[pos:offset]) and not any(
                    re.search(assign, model.nodes[c][0].body(model.nodes[c][1])) for c in callbacks):
                return True
    return False


def callback_roots(model, edges):
    """Methods scheduled by a repeating or self-rearming CallLater/CallLaterByName.

    Returns {target node: (scheduler node, 'repeat' | 'rearm')}. A bounded breadth-first
    walk over the authored call edges decides re-arming; unresolved callbacks are ignored.
    """
    scheduled = []
    for i, (s, m) in enumerate(model.nodes):
        for call in _CALL_LATER.finditer(s.code, m.body_start, m.body_end):
            opening = s.code.find('(', call.start(), call.end())
            closing = es.matching_paren(s.code, opening)
            arguments = es.split_top(s.code[opening + 1:closing], ',')
            if call.group(1) == 'CallLater':
                if not arguments or not arguments[0].strip():
                    continue
                expression, repeat_at = arguments[0], 2
                targets = model.targets(i, expression)
            else:
                if len(arguments) < 2:
                    continue
                # The lexer blanks string contents; read the callback name from the raw text.
                raw = es.split_top(s.text[opening + 1:closing], ',')[1].strip().strip('"')
                if not re.fullmatch(_IDENT, raw):
                    continue
                owner = re.sub(r'\s+', '', arguments[0])
                typ = (m.owner.name if m.owner else '') if owner == 'this' else model.type_of(owner, model.envs[i])
                targets = sorted({t for ancestor in model.lineage(typ) if typ
                                  for t in model.index.get((ancestor, raw), [])})
                repeat_at = 3
            repeat = re.sub(r'\s+', '', arguments[repeat_at]) if len(arguments) > repeat_at else 'false'
            repeating = repeat not in ('false', '0', '')
            if not repeating and capped_retry(model, i, call.start(), targets):
                continue
            scheduled.append((i, targets, repeating))
    schedulers = {}
    for i, targets, _ in scheduled:
        for target in targets:
            schedulers.setdefault(target, set()).add(i)
    roots = {}
    for i, targets, repeating in scheduled:
        for target in targets:
            if repeating and target not in roots:
                roots[target] = (i, 'repeat')
    for target, owners in sorted(schedulers.items()):
        if target in roots:
            continue
        seen, queue = {target}, deque([target])
        while queue:
            current = queue.popleft()
            if current in owners:
                roots[target] = (current, 'rearm')
                break
            for _, nxt in edges[current]:
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
    return roots


def check(sources, root=ROOT):
    """Return deterministic Finding objects; does not load/write a baseline."""
    model = Model(sources)
    findings = []
    loop_spans = []
    slot_uses = []
    caps = parameter_caps(model)
    for i, (s, m) in enumerate(model.nodes):
        spans = list(loops(s, m))
        loop_spans.append(spans)
        findings.extend(nested_scans(model, i, spans))
        findings.extend(raw_budget_calls(model, i))
        slot_counts = {}
        for call in _SLOT_CALL.finditer(s.code, m.body_start, m.body_end):
            opening = s.code.find('(', call.start(), call.end())
            arguments = s.code[opening + 1:es.matching_paren(s.code, opening)]
            for slot in dict.fromkeys(re.findall(r'\bHC_WORK_[A-Z0-9_]+\b', arguments)):
                slot_counts[slot] = slot_counts.get(slot, 0) + 1
                slot_uses.append((s.rel, call.start(), i, slot, slot_counts[slot]))
        counts = {}
        for call in _SCAN.finditer(s.code, m.body_start, m.body_end):
            receiver = re.sub(r'\s+', '', call.group(1))
            enclosing = [(a, b) for a, b in spans if a <= call.start() < b]
            if not enclosing or model.type_of(receiver, model.envs[i]) != 'string':
                continue
            if m.owner and receiver.removeprefix('this.').isidentifier():
                held = field_bound(model, m.owner.name, receiver.removeprefix('this.'))
                if held is not None and held <= (_FIELD_GET_CAP if call.group(2) == 'Get' else _FIELD_CAP):
                    continue
            if bounded_string(s, m, receiver, call.start(),
                              {name: cap for (target, name), cap in caps.items() if target == i}, model, i):
                continue
            # Substring copies only its constant length (<=1024), however long the receiver.
            if call.group(2) == 'Substring':
                opening = s.code.find('(', call.start(), call.end())
                args = es.split_top(s.code[opening + 1:es.matching_paren(s.code, opening)], ',')
                if len(args) == 2 and 0 < (model.const_int(args[1]) or 0) <= 1024:
                    continue
            if any(bulk_copy(s, a, b, call) for a, b in enclosing):
                continue
            key = receiver + '.' + call.group(2)
            counts[key] = counts.get(key, 0) + 1
            findings.append(Finding('HC-P001', s.rel, s.line_of(call.start()), symbol(m),
                                    f'{key}#{counts[key]}', f'{key} scans a string with no recognized small bound inside a loop'))

    first_owners = {}
    for _, offset, i, slot, occurrence in sorted(slot_uses):
        s, m = model.nodes[i]
        owner = m.owner.name if m.owner else '<global>'
        first = first_owners.setdefault(slot, owner)
        if owner != first:
            findings.append(Finding('HC-P006', s.rel, s.line_of(offset), symbol(m),
                                    f'{slot}#{occurrence}', f'slot {slot} shared by {first} and {owner}; give each consumer its own slot (see PERFORMANCE_PRACTICES)'))
    findings.extend(slot_registrations(sources, root))

    edges, ios, tick_sites = [], [], []
    for i, (s, m) in enumerate(model.nodes):
        outgoing, sites, candidates = [], [], []
        for call in _CALL.finditer(s.code, m.body_start, m.body_end):
            expression = re.sub(r'\s+', '', call.group(1))
            name = expression.split('.')[-1]
            if (expression == 'Print' and any(a <= call.start() < b for a, b in loop_spans[i])
                    and not terminal_print(s, call)):
                candidates.append((call.start(), 'HC-P005', 'Print', 'per-item Print on a tick path; latch or summarize'))
            if name == 'Save' and '.' in expression and model.type_of(expression.rsplit('.', 1)[0], model.envs[i]).endswith('Store'):
                candidates.append((call.start(), 'HC-P008', expression,
                                   'synchronous store Save on a tick path; mark dirty and let the HCSaveScheduler job stage it unless this is a durability barrier'))
            if (name in _IO and '.' not in expression) or expression.split('.')[0] == 'JsonFileLoader':
                # LoadData/MakeData serialize memory, not files.
                if expression.startswith('JsonFileLoader'):
                    continue
                sites.append((call.start(), name))
            outgoing.extend((call.start(), target) for target in model.targets(i, expression))
        # JsonFileLoader<T>.LoadFile/SaveFile/legacy JsonLoadFile/JsonSaveFile.
        for call in re.finditer(r'\bJsonFileLoader\s*<[^;{}()]+>\s*[.:]+\s*(LoadFile|SaveFile|JsonLoadFile|JsonSaveFile)\s*\(', s.body(m)):
            sites.append((m.body_start + call.start(), 'JsonFileLoader.' + call.group(1)))
        edges.append(sorted(set(outgoing)))
        ios.append(sorted(set(sites)))
        tick_sites.append(candidates)

    def boundary(i):
        s, m = model.nodes[i]
        return (s.rel == _WRITER_PATH and m.owner and m.owner.name == 'HCStagedSaveImage'
                and m.name in _BOUNDARIES)

    roots = [i for i, (_, m) in enumerate(model.nodes) if _ROOT.fullmatch(m.name) and not boundary(i)
             and (not m.owner or m.name != m.owner.name)]
    roots.extend(i for i in sorted(callback_roots(model, edges)) if i not in roots and not boundary(i))
    staged = set()

    def walk(skipped, prune_staged=False, cut_stop=False, avoid=lambda i: False):
        """Breadth-first tick reachability; skipped[i] holds spans whose code is once-only.

        With prune_staged, a staged step is neither a root nor entered by a call that runs
        at most once per visit (a call inside a loop still enters it). With cut_stop, calls
        into a lifecycle OnStop override are not followed (shutdown, not tick work). A
        method for which avoid(i) holds is neither a root nor traversed."""
        queue = deque((i, (i,)) for i in roots
                      if not (prune_staged and i in staged) and not avoid(i))
        reached = {i: chain for i, chain in queue}
        while queue:
            i, chain = queue.popleft()
            s, m = model.nodes[i]
            if len(chain) - 1 >= MAX_DEPTH:
                continue
            for offset, target in edges[i]:
                if any(a <= offset < b for a, b in skipped.get(i, ())):
                    continue
                if prune_staged and target in staged and not any(a <= offset < b for a, b in loop_spans[i]):
                    continue
                if cut_stop and model.nodes[target][1].name == 'OnStop':
                    continue
                drains_writer = (m.owner and m.owner.name == 'HCStagedSaveImage' and m.name == 'Finish'
                                 and s.rel == _WRITER_PATH)
                if target not in reached and not avoid(target) and (not boundary(target) or drains_writer):
                    reached[target] = chain + (target,)
                    queue.append((target, chain + (target,)))
        return reached

    # Latch spans count only when nothing on a tick path can reset the latch; the
    # unpruned reachable set is a superset of the pruned one, so this stays conservative.
    latched = {i: once_spans(model, i) for i in range(len(model.nodes))}
    resettable = set()
    for i in walk({}, False, True):
        s, m = model.nodes[i]
        for reset in _RESET.finditer(s.code, m.body_start, m.body_end):
            latch = _latch_field(model, i, reset.group(1))
            if latch:
                resettable.add(latch[:2])
    armed = set()
    for i in walk({}, False, True):
        s, m = model.nodes[i]
        for write in _ASSIGN.finditer(s.code, m.body_start, m.body_end):
            if write.group(2).strip() not in {'null', 'NULL', 'false', '0', ''}:
                latch = _latch_field(model, i, write.group(1))
                if latch:
                    armed.add(latch[:2])
    # A consume latch is cleared by design, so only arming it again defeats it.
    # A retry-window span counts only when no tick path writes its window or latch field
    # outside the accepted window blocks: any other write could reopen the window early.
    window_blocks = {}
    watched = set()
    for i, spans in latched.items():
        for a, b, latch in spans:
            if len(latch) == 6:
                window_blocks.setdefault(i, []).append((a, b))
                watched.update((latch[:2], latch[4:6]))
    tampered = set()
    if watched:
        for i in walk({}, False, True):
            s, m = model.nodes[i]
            for write in _WRITE.finditer(s.code, m.body_start, m.body_end):
                field = _latch_field(model, i, next(g for g in write.groups() if g), True)
                if field and field[:2] in watched and not any(a <= write.start() < b for a, b in window_blocks.get(i, ())):
                    tampered.add(field[:2])

    def counts(latch):
        if len(latch) == 4:
            return latch[:2] not in armed
        if len(latch) == 6:
            return latch[:2] not in resettable and not ({latch[:2], latch[4:6]} & tampered)
        return latch[:2] not in resettable

    skipped = {i: [(a, b) for a, b, latch in spans if counts(latch)]
               for i, spans in latched.items() if spans}

    findings.extend(startup_file_loops(model, edges, ios, loop_spans, skipped))

    cost = StepCost(model, edges, ios, boundary, skipped, reaching(model, edges, ios, boundary))
    for i, (s, m) in enumerate(model.nodes):
        if (_STEP.fullmatch(m.name) and not boundary(i) and cost.method(i) <= STAGE_OPS
                and advances_state(model, i)):
            staged.add(i)

    # A module OnStop runs once, at shutdown or when the module is retired; a
    # synchronous Save there is the durability barrier, not per-tick persistence. A
    # Save also reachable without passing through an OnStop is still reported.
    outside_stop = walk(skipped, avoid=lambda n: model.nodes[n][1].name == 'OnStop')
    for i, chain in walk(skipped).items():
        s, m = model.nodes[i]
        # Once-only code (a load-once latch, or a Print/Save inside a set-once guard)
        # is not per-tick or per-item work.
        live = lambda offset: not any(a <= offset < b for a, b in skipped.get(i, ()))
        tick_counts = {}
        for offset, rule, operation, message in tick_sites[i]:
            if not live(offset) or (rule == 'HC-P008' and i not in outside_stop):
                continue
            key = (rule, operation)
            tick_counts[key] = tick_counts.get(key, 0) + 1
            findings.append(Finding(rule, s.rel, s.line_of(offset), symbol(m),
                                    f'{operation}#{tick_counts[key]}', message))
    for i, chain in walk(skipped, True, True).items():
        s, m = model.nodes[i]
        live = lambda offset: not any(a <= offset < b for a, b in skipped.get(i, ()))
        counts = {}
        for offset, operation in ios[i]:
            if not live(offset):
                continue
            counts[operation] = counts.get(operation, 0) + 1
            witness = ' -> '.join(symbol(model.nodes[n][1]) for n in chain)
            findings.append(Finding('HC-P003', s.rel, s.line_of(offset), symbol(m),
                                    f'{operation}#{counts[operation]}', f'{operation} reachable via {witness}'))
    return sorted(findings, key=lambda f: (f.path, f.line, f.rule, f.key))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('paths', nargs='*', help='only report these repository-relative source paths')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--baseline', type=Path, default=BASELINE)
    parser.add_argument('--write-baseline', action='store_true', help='explicitly acknowledge current findings at --baseline')
    parser.add_argument('--ratchet', '--prune-baseline', dest='ratchet', action='store_true',
                        help='drop baseline entries that no longer match a finding; never adds entries')
    parser.add_argument('--strict-baseline', action='store_true', help='fail when baseline entries no longer match live findings')
    parser.add_argument('--stdin', metavar='PATH', help='replace this repository source with stdin, for historical checks')
    parser.add_argument('--json', action='store_true', help='print findings as JSON before the summary')
    args = parser.parse_args(argv)
    root = args.root.resolve()

    def relative(path):
        p = Path(path)
        p = p.resolve() if p.is_absolute() else (root / p).resolve()
        return p.relative_to(root).as_posix()

    try:
        selected = {relative(p) for p in args.paths}
        sources = es.mod_sources(root)
        # Include mission scripts; never inspect installed profiles/native dumps.
        mission = root / 'mission'
        if mission.is_dir():
            sources.extend(es.read_source(p, root) for p in sorted(mission.rglob('*.c')))
        if args.stdin:
            rel = relative(args.stdin)
            sources = [s for s in sources if s.rel != rel]
            sources.append(es.Source(root / rel, sys.stdin.read(), root))
        known = {s.rel for s in sources}
        if selected - known:
            parser.error('selected paths must be authored sources under mods/*/scripts or mission/')
        live_findings = check(sources, root)
        findings = [f for f in live_findings if not selected or f.path in selected]
        if args.write_baseline and args.ratchet:
            parser.error('--ratchet cannot be combined with --write-baseline')
        if args.strict_baseline and args.stdin:
            parser.error('--strict-baseline requires the current project, without --stdin')
        if args.write_baseline:
            if selected or args.stdin:
                parser.error('--write-baseline requires the full current project')
            args.baseline.write_text(json.dumps({'version': 1, 'note': 'Offline review candidates; no native acceptance. See enforce_perf.py for approximation limits.',
                                                 'findings': [asdict(f) for f in findings]}, indent=2) + '\n', encoding='utf-8')
        if args.ratchet and (selected or args.stdin):
            parser.error('--ratchet requires the full current project')
        baseline = json.loads(args.baseline.read_text(encoding='utf-8')) if args.baseline.exists() else {'findings': []}
        identities = {(f['rule'], f['path'], f['symbol'], f['key']) for f in baseline['findings']}
        new = [f for f in findings if f.identity() not in identities]
        # Compare against the full graph even when paths filter the displayed findings.
        # Ratcheting only removes entries; it never acknowledges a new candidate.
        stale = []
        if not args.stdin:
            current = {f.identity() for f in live_findings}
            stale = [e for e in baseline['findings'] if (e['rule'], e['path'], e['symbol'], e['key']) not in current]
            if args.ratchet and stale:
                baseline['findings'] = [e for e in baseline['findings'] if e not in stale]
                args.baseline.write_text(json.dumps(baseline, indent=2) + '\n', encoding='utf-8')
                print(f'enforce_perf: pruned {len(stale)} stale baseline entries')
                stale = []
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Do not echo local filesystem paths from exceptions.
        print(f'enforce_perf: error ({type(exc).__name__}); check source/baseline inputs', file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps([dict(asdict(f), new=f in new) for f in findings], indent=2))
    else:
        for f in findings:
            print(f.render() + (' [new]' if f in new else ' [baseline]'))
    for e in stale:
        print(f"{e['path']}: {e['rule']} {e['symbol']} {e['key']} [stale baseline entry; run --ratchet]")
    failed = bool(new or (args.strict_baseline and stale))
    print(f'enforce_perf: {"fail" if failed else "pass"} findings={len(findings)} new={len(new)} stale={len(stale)}')
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
