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
it cannot resolve returned stores, infer synchronous implementation details or
distinguish required durability barriers. All rules report review candidates,
never measured complexity, timing or native acceptance.

P009 follows the same bounded typed call graph from OnStart, carrying lexical
loop context across calls. Repeated file opens, probes, copies, deletes and JSON
file loads/saves are synchronous multi-file candidates; reads from an already
open handle are not. It cannot distinguish repeated access to one path from
different paths, prove loop trip counts, or follow queued callbacks.
P010 finds raw HCTake calls on declared HCUnitBudget receivers (including
derived types) and HCServer.HCTickWork() chains. The shared budget's own
implementation is excluded. Private budgets remain review candidates; unknown
receiver/return types are not inferred by method name alone.
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

    def targets(self, i, expression):
        s, m = self.nodes[i]
        parts = re.sub(r'\s+', '', expression).split('.')
        name = parts[-1]
        if len(parts) == 1:
            typ = m.owner.name if m.owner else ''
        else:
            typ = self.type_of('.'.join(parts[:-1]), self.envs[i])
        result = []
        if typ:
            for ancestor in self.lineage(typ):
                result.extend(self.index.get((ancestor, name), []))
            # Typed virtual calls can reach authored derived implementations.
            # Static class-qualified and super calls do not dispatch downward.
            if len(parts) == 1 or (parts[0] not in self.classes and parts[0] != 'super'):
                for child in self.descendants.get(typ, []):
                    result.extend(self.index.get((child, name), []))
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
        if '&&' in condition or not re.match(r'\s*{?\s*return\b[^;]*;', body[closing + 1:]):
            continue
        if any(w.start() > closing for w in writes):
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
_EXIT = re.compile(r'\b(?:return|continue|break)\b')


def _latch_field(model, i, expression):
    """(defining class, field name, type) of a bool/ref latch field, else None.

    Locals, parameters, ints, floats, strings and vectors are not latches."""
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
    if not field or field.type in {'int', 'float', 'string', 'vector', 'typename'}:
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
        count += 1
        yield Finding('HC-P010', s.rel, s.line_of(call.start()), symbol(m),
                      f'HCTake#{count}',
                      'raw HCTake bypasses consumer fairness/attribution; use HCTakeFor with an owned HC_WORK slot')


def startup_file_loops(model, edges, ios, loop_spans):
    """Visit each (method, repeated) state once, retaining a shortest witness."""
    roots = [i for i, (_, m) in enumerate(model.nodes) if m.name == 'OnStart']
    queue = deque((i, False, (i,)) for i in roots)
    reached = {(i, False) for i in roots}
    reported = set()
    while queue:
        i, repeated, chain = queue.popleft()
        s, m = model.nodes[i]

        def in_loop(offset):
            return repeated or any(a <= offset < b for a, b in loop_spans[i])

        counts = {}
        for offset, operation in ios[i]:
            if operation not in {'OpenFile', 'FileExist', 'CopyFile', 'DeleteFile'} and not operation.startswith('JsonFileLoader.'):
                continue
            counts[operation] = counts.get(operation, 0) + 1
            if not in_loop(offset) or (i, offset, operation) in reported:
                continue
            reported.add((i, offset, operation))
            witness = ' -> '.join(symbol(model.nodes[n][1]) for n in chain)
            yield Finding('HC-P009', s.rel, s.line_of(offset), symbol(m),
                          f'{operation}#{counts[operation]}',
                          f'{operation} in a synchronous startup loop via {witness}; enqueue bounded startup work')
        if len(chain) - 1 >= MAX_DEPTH:
            continue
        for offset, target in edges[i]:
            state = (target, in_loop(offset))
            if state not in reached:
                reached.add(state)
                queue.append((*state, chain + (target,)))


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

    findings.extend(startup_file_loops(model, edges, ios, loop_spans))

    def boundary(i):
        s, m = model.nodes[i]
        return (s.rel == _WRITER_PATH and m.owner and m.owner.name == 'HCStagedSaveImage'
                and m.name in _BOUNDARIES)

    roots = [i for i, (_, m) in enumerate(model.nodes) if _ROOT.fullmatch(m.name) and not boundary(i)
             and (not m.owner or m.name != m.owner.name)]

    def walk(skipped):
        """Breadth-first tick reachability; skipped[i] holds spans whose code is once-only."""
        queue = deque((i, (i,)) for i in roots)
        reached = {i: (i,) for i in roots}
        while queue:
            i, chain = queue.popleft()
            s, m = model.nodes[i]
            if len(chain) - 1 >= MAX_DEPTH:
                continue
            for offset, target in edges[i]:
                if any(a <= offset < b for a, b in skipped.get(i, ())):
                    continue
                drains_writer = (m.owner and m.owner.name == 'HCStagedSaveImage' and m.name == 'Finish'
                                 and s.rel == _WRITER_PATH)
                if target not in reached and (not boundary(target) or drains_writer):
                    reached[target] = chain + (target,)
                    queue.append((target, chain + (target,)))
        return reached

    # Latch spans count only when nothing on a tick path can reset the latch; the
    # unpruned reachable set is a superset of the pruned one, so this stays conservative.
    latched = {i: once_spans(model, i) for i in range(len(model.nodes))}
    resettable = set()
    for i in walk({}):
        s, m = model.nodes[i]
        for reset in _RESET.finditer(s.code, m.body_start, m.body_end):
            latch = _latch_field(model, i, reset.group(1))
            if latch:
                resettable.add(latch[:2])
    skipped = {i: [(a, b) for a, b, latch in spans if latch[:2] not in resettable]
               for i, spans in latched.items() if spans}

    for i, chain in walk(skipped).items():
        s, m = model.nodes[i]
        # Once-only code (a load-once latch, or a Print/Save inside a set-once guard)
        # is not per-tick or per-item work.
        live = lambda offset: not any(a <= offset < b for a, b in skipped.get(i, ()))
        tick_counts = {}
        for offset, rule, operation, message in tick_sites[i]:
            if not live(offset):
                continue
            key = (rule, operation)
            tick_counts[key] = tick_counts.get(key, 0) + 1
            findings.append(Finding(rule, s.rel, s.line_of(offset), symbol(m),
                                    f'{operation}#{tick_counts[key]}', message))
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
