"""Offline Enforce performance candidates; no engine or timing claims.

Run python3 -B -m tools.validate.enforce_perf [source.c ...]. Paths select
output, not the call-graph universe. --stdin PATH replaces one authored source
with stdin (e.g. git show REV:PATH | ... --stdin PATH PATH). check(sources)
is the integration entry point and accepts enforce_source.Source objects.

P001 checks lexically enclosing loops, string parameters/fields/locals and
simple assignments. Unknown strings are unbounded. Literal initializers,
small length refusal guards (including literal caller bounds) and explicit clamped, strided bulk Substring copies are
bounded; HCTextWindow receivers are typed objects, never strings. This is not
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
Single I/O operations are candidates too: the tool cannot infer their latency.
Baseline entries acknowledge candidates, not native acceptance. P002 is omitted
because source-only configured-float bounds have too much ambiguity.

P004 finds lexical nested collection loops with equality comparisons and array
Find/Contains/IndexOf/Get calls inside loops. Literal upper bounds <=16 are
skipped; Get is deliberately a broad candidate, including indexed access.
Only declared array/map/set receivers are recognized, not aliases, returned
collections or interprocedural nesting. Equality need not compare loop items.
P005 finds Print in lexical loops on the same bounded tick graph as P003;
it cannot prove logging frequency or recognize latches and summary logging.
P006 finds literal HC_WORK_* arguments to HCTakeFor/HCCharge shared across
owner class names (modded definitions share their class name). It cannot
resolve computed slots or prove that different classes compete at runtime.
P007 checks consumer declarations against profile registration, weight fields
and decoded assignments, settings registration and the report CONSUMERS list.
HC_WORK_CONSUMERS is a count; HC_WORK_UNBOUNDED is an arithmetic sentinel,
not a slot. This is structural completeness, not runtime settings validation.
P008 finds Save calls on declared types ending in Store on P003's tick graph;
it cannot resolve returned stores, infer synchronous implementation details or
distinguish required durability barriers. All rules report review candidates,
never measured complexity, timing or native acceptance.
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
_ARRAY_SCAN = re.compile(rf'\b({_CHAIN})\s*\.\s*(Find|Contains|IndexOf|Get)\s*\(')
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
        self.envs = [self.environment(s, m) for s, m in self.nodes]

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
        if re.search(r'\.Length\s*\(\s*\)\s*!=\s*[A-Za-z_]', s.body(m)):
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
                    values.setdefault((target, name), []).append(int(arg) if arg.isdecimal() else 0)
    return {key: max(items) for key, items in values.items() if all(0 < n <= 1024 for n in items)}


def bounded_string(s, m, receiver, offset, caps):
    """Recognize small literal values and early length guards, not file caps."""
    body = s.code[m.body_start:offset]
    name = re.escape(receiver)
    # A literal assignment is bounded only if it is the sole write to the name.
    writes = list(re.finditer(rf'(?<![\w.]){name}\s*(?:\+=|=(?!=))\s*([^;]*);', body))
    file_loaded = re.search(rf'\b(?:ReadFile|FGets)\s*\([^;]*\b{name}\b[^;]*\)', body)
    if (not file_loaded and len(writes) == 1 and len(writes[0].group(1)) <= 1026
            and re.fullmatch(r'\s*"[^"\n]*"\s*', writes[0].group(1))):
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
            bound = re.fullmatch(rf'\s*{name}\.Length\s*\(\s*\)\s*(>|!=)\s*({_IDENT}|\d+)\s*', term)
            if bound:
                limit = int(bound.group(2)) if bound.group(2).isdecimal() else caps.get(bound.group(2), 0)
                if 0 < limit <= 1024:
                    return True
    return False


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


def slot_registrations(sources, root):
    """Cross-file checks on authored sources; no execution of report Python."""
    by_name = {}
    for s in sources:
        if s.rel.startswith('mods/HollowCountry/scripts/'):
            by_name.setdefault(s.path.name, []).append(s)

    def named(filename):
        return by_name.get(filename, [])

    def has_call(filename, name, argument):
        for s in named(filename):
            for call in re.finditer(rf'\b{name}\s*\(\s*("[^"\n]*")', s.code):
                # Quotes survive masking; recover only the matching literal.
                if s.text[call.start(1):call.end(1)] == json.dumps(argument):
                    return True
        return False

    consumers = set()
    report = root / 'tools/validate/tick_cost_report.py'
    if report.is_file():
        tree = ast.parse(report.read_text(encoding='utf-8'))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CONSUMERS' for t in node.targets):
                value = node.value
                if (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                        and value.func.attr == 'split' and not value.args and not value.keywords):
                    literal = ast.literal_eval(value.func.value)
                    if isinstance(literal, str):
                        consumers.update(literal.split())
                elif isinstance(value, (ast.List, ast.Tuple, ast.Set)):
                    consumers.update(ast.literal_eval(value))
    for s in named('HCUnitBudget.c'):
        declarations = list(re.finditer(r'\bstatic\s+const\s+int\s+HC_WORK_(\w+)\s*=\s*(\d+)\s*;', s.code))
        slots = [d for d in declarations if d[1] not in {'CONSUMERS', 'UNBOUNDED'}]
        count = next((d for d in declarations if d[1] == 'CONSUMERS'), None)
        for slot in slots:
            name = slot[1]
            field = 'TickWeight_' + name
            pieces = {
                'profile': has_call('HCUnitProfile.c', 'HCRegister', name),
                'field': any(f.name == field for source in named('HCPerfSlices.c') for c in source.classes for f in c.fields),
                'load': any(re.search(rf'\b{field}\s*=\s*decoded\s*\.\s*{field}\s*;', source.code)
                            for source in named('HCPerfSlices.c')),
                'settings': has_call('HCPerfSettingsRegistry.c', 'HCAdd', 'Performance.' + field),
                'report': name in consumers,
            }
            for piece, present in pieces.items():
                if not present:
                    yield Finding('HC-P007', s.rel, s.line_of(slot.start()), 'HCUnitBudget',
                                  f'HC_WORK_{name}:{piece}', f'HC_WORK_{name} missing {piece} registration (see PERFORMANCE_PRACTICES)')
        if slots and (count is None or int(count[2]) <= max(int(d[2]) for d in slots)):
            yield Finding('HC-P007', s.rel, s.line_of(count.start() if count else slots[0].start()),
                          'HCUnitBudget', 'HC_WORK_CONSUMERS:capacity',
                          'HC_WORK_CONSUMERS must exceed the largest consumer slot value')


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
                              {name: cap for (target, name), cap in caps.items() if target == i}):
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
        outgoing, sites, candidates = set(), [], []
        for call in _CALL.finditer(s.code, m.body_start, m.body_end):
            expression = re.sub(r'\s+', '', call.group(1))
            name = expression.split('.')[-1]
            if expression == 'Print' and any(a <= call.start() < b for a, b in loop_spans[i]):
                candidates.append((call.start(), 'HC-P005', 'Print', 'per-item Print on a tick path; latch or summarize'))
            if name == 'Save' and '.' in expression and model.type_of(expression.rsplit('.', 1)[0], model.envs[i]).endswith('Store'):
                candidates.append((call.start(), 'HC-P008', expression,
                                   'synchronous store Save on a tick path; mark dirty and let the HCSaveScheduler job stage it unless this is a durability barrier'))
            if (name in _IO and '.' not in expression) or expression.split('.')[0] == 'JsonFileLoader':
                # LoadData/MakeData serialize memory, not files.
                if expression.startswith('JsonFileLoader'):
                    continue
                sites.append((call.start(), name))
            outgoing.update(model.targets(i, expression))
        # JsonFileLoader<T>.LoadFile/SaveFile/legacy JsonLoadFile/JsonSaveFile.
        for call in re.finditer(r'\bJsonFileLoader\s*<[^;{}()]+>\s*[.:]+\s*(LoadFile|SaveFile|JsonLoadFile|JsonSaveFile)\s*\(', s.body(m)):
            sites.append((m.body_start + call.start(), 'JsonFileLoader.' + call.group(1)))
        edges.append(sorted(outgoing))
        ios.append(sorted(set(sites)))
        tick_sites.append(candidates)

    def boundary(i):
        s, m = model.nodes[i]
        return (s.rel == _WRITER_PATH and m.owner and m.owner.name == 'HCStagedSaveImage'
                and m.name in _BOUNDARIES)

    roots = [i for i, (_, m) in enumerate(model.nodes) if _ROOT.fullmatch(m.name) and not boundary(i)
             and (not m.owner or m.name != m.owner.name)]
    queue = deque((i, (i,)) for i in roots)
    reached = set(roots)
    while queue:
        i, chain = queue.popleft()
        s, m = model.nodes[i]
        tick_counts = {}
        for offset, rule, operation, message in tick_sites[i]:
            key = (rule, operation)
            tick_counts[key] = tick_counts.get(key, 0) + 1
            findings.append(Finding(rule, s.rel, s.line_of(offset), symbol(m),
                                    f'{operation}#{tick_counts[key]}', message))
        counts = {}
        for offset, operation in ios[i]:
            counts[operation] = counts.get(operation, 0) + 1
            witness = ' -> '.join(symbol(model.nodes[n][1]) for n in chain)
            findings.append(Finding('HC-P003', s.rel, s.line_of(offset), symbol(m),
                                    f'{operation}#{counts[operation]}', f'{operation} reachable via {witness}'))
        if len(chain) - 1 >= MAX_DEPTH:
            continue
        for target in edges[i]:
            drains_writer = (m.owner and m.owner.name == 'HCStagedSaveImage' and m.name == 'Finish'
                             and s.rel == _WRITER_PATH)
            if target not in reached and (not boundary(target) or drains_writer):
                reached.add(target)
                queue.append((target, chain + (target,)))
    return sorted(findings, key=lambda f: (f.path, f.line, f.rule, f.key))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('paths', nargs='*', help='only report these repository-relative source paths')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--baseline', type=Path, default=BASELINE)
    parser.add_argument('--write-baseline', action='store_true', help='explicitly acknowledge current findings at --baseline')
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
        findings = [f for f in check(sources, root) if not selected or f.path in selected]
        if args.write_baseline:
            if selected or args.stdin:
                parser.error('--write-baseline requires the full current project')
            args.baseline.write_text(json.dumps({'version': 1, 'note': 'Offline review candidates; no native acceptance. See enforce_perf.py for approximation limits.',
                                                 'findings': [asdict(f) for f in findings]}, indent=2) + '\n', encoding='utf-8')
        baseline = json.loads(args.baseline.read_text(encoding='utf-8')) if args.baseline.exists() else {'findings': []}
        identities = {(f['rule'], f['path'], f['symbol'], f['key']) for f in baseline['findings']}
        new = [f for f in findings if f.identity() not in identities]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Do not echo local filesystem paths from exceptions.
        print(f'enforce_perf: error ({type(exc).__name__}); check source/baseline inputs', file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps([dict(asdict(f), new=f in new) for f in findings], indent=2))
    else:
        for f in findings:
            print(f.render() + (' [new]' if f in new else ' [baseline]'))
    print(f'enforce_perf: {"fail" if new else "pass"} findings={len(findings)} new={len(new)}')
    return int(bool(new))


if __name__ == '__main__':
    raise SystemExit(main())
