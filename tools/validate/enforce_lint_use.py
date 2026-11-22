"""HC-E040: an unguarded [HC Use] counter must not be reachable from an init path.

A use counter says "a player or the server did this feature at runtime". A counter
that every run of an init path hits (OnInit, OnStart, a constructor, Load/Migrate/
Restore code, entity init) counts work no gameplay caused, so [HC Use] reports
activity that never happened and tools/release/activity_check believes it.

The rule builds a conservative call graph over the authored sources. From every init
root it follows only calls that run on every pass through the caller (no enclosing
if/else/loop/switch, no short-circuit operand) and reports each HCUse/HCUseFixture
reached that way. A counter behind a branch depends on an outcome and is safe; a
call to HCUseGuarded is safe by construction (the API refuses init-path counts at
runtime). Only calls it can resolve with certainty are followed: unqualified,
this/super, ``Type.Method`` for an authored class, and receivers whose type is a
declared field, parameter or local. Nothing is guessed from a method name alone.

Pure and offline over the shared source model. A pass is not DayZ evidence; the
native boot [HC Use] and [HC UseRefused] lines are. ``python3 -B -m
tools.validate.enforce_lint_use`` prints the safe/flagged classification.
"""
from collections import deque
import re

RULE = 'HC-E040'
RULES = {RULE: 'use counter reached unconditionally from an init path (OnInit, OnStart, constructor, '
               'Load/Migrate/Restore, entity init); count from the gameplay path with HCUseGuarded'}

# Counters that count unconditionally. HCUseGuarded is absent on purpose.
COUNTERS = frozenset({'HCUse', 'HCUseFixture'})
_READINESS = 'HCModuleReadiness'

_ROOT_NAMES = frozenset({'OnInit', 'OnStart', 'OnAllModulesStarted', 'EEInit', 'EOnInit', 'AfterStoreLoad',
                         'OnStoreLoad', 'OnGameplayDataHandlerLoad'})
_ROOT_PREFIXES = ('Init', 'Load', 'Migrate', 'Restore', 'Recover')

_KEYWORDS = frozenset({'if', 'while', 'for', 'foreach', 'switch', 'return', 'new', 'delete', 'case', 'else',
                       'sizeof', 'typename', 'super', 'this', 'thread', 'Cast', 'CastTo'})
_CALL = re.compile(r'(?<![\w.])(?:(super|this)\s*\.\s*)?([A-Za-z_]\w*)\s*\(')
_QUALIFIED = re.compile(r'(?<![\w.])([A-Za-z_]\w*)\s*\.\s*([A-Za-z_]\w*)\s*\(')
_BRANCH_START = re.compile(r'^\s*(?:if|else|for|foreach|while|switch|case)\b')
_QUALIFIERS = re.compile(r'\b(?:ref|autoptr|notnull|const|static|out|inout|protected|private)\b')


def is_init_name(owner, name):
    """True for constructors and the start-up, entity-init, load and migration method names."""
    return name == owner or name in _ROOT_NAMES or name.startswith(_ROOT_PREFIXES)


def _base_type(text):
    match = re.match(r'[A-Za-z_]\w*', _QUALIFIERS.sub('', text).strip())
    return match.group(0) if match else ''


def _plain(code, method, offset):
    """True when a call at offset runs on every pass through the method body.

    Not enclosed in a nested block (if/else/loop/switch bodies), not the single statement
    of a braceless if/else/loop, and not behind && or ||. An early return elsewhere does not
    make a call conditional: a guard clause about the caller's own inputs is not evidence
    that the feature was used."""
    before = code[method.body_start:offset]
    if before.count('{') - before.count('}') > 1:
        return False
    statement = before[max(before.rfind(';'), before.rfind('{'), before.rfind('}')) + 1:]
    return not (_BRANCH_START.match(statement) or '&&' in statement or '||' in statement)


class _Graph:
    """Authored methods keyed (class, name) with their resolved calls and counter calls."""

    def __init__(self, project):
        self.links = project.links
        self.methods = {}
        for source in project.sources:
            for definition in source.classes:
                for method in definition.methods:
                    self.methods.setdefault((definition.name, method.name), []).append((source, method))
        self._calls = {}

    def ancestors(self, cls):
        seen, order, queue = set(), [], deque([cls])
        while queue:
            current = queue.popleft()
            if current in seen or current not in self.links:
                continue
            seen.add(current)
            order.append(current)
            queue.extend(d.base for d in self.links[current] if d.base)
        return order

    def field_type(self, cls, name):
        for owner in self.ancestors(cls):
            for definition in self.links.get(owner, ()):
                for member in definition.fields:
                    if member.name == name:
                        return _base_type(member.type)
        return ''

    def declaring(self, cls, name):
        """The nearest class from cls upward that declares name, as a method key list."""
        for owner in self.ancestors(cls):
            if (owner, name) in self.methods:
                return [(owner, name)]
        return []

    def typed_names(self, source, method):
        types = {}
        for kind, name, _out in method.parameters():
            types[name] = _base_type(kind)
        for name, kind, _start, _end in source.local_declarations(method):
            types.setdefault(name, _base_type(kind))
        return types

    def calls(self, source, method):
        """([(callee key, plain)], [(offset, counter name, plain)]) for one method body."""
        cache_key = (source.rel, method.offset)
        if cache_key in self._calls:
            return self._calls[cache_key]
        code = source.code
        owner = method.owner.name if method.owner is not None else ''
        edges, counters, taken = [], [], set()
        if owner == _READINESS and method.name in COUNTERS | {'HCUseGuarded'}:
            self._calls[cache_key] = (edges, counters)  # the counter API itself, not a call site
            return self._calls[cache_key]
        types = self.typed_names(source, method)
        for match in _QUALIFIED.finditer(code, method.body_start, method.body_end):
            receiver, name = match.group(1), match.group(2)
            if receiver in ('super', 'this'):
                continue
            taken.add(match.start(2))
            plain = _plain(code, method, match.start(1))
            if receiver == _READINESS and name in COUNTERS:
                counters.append((match.start(2), name, plain))
                continue
            cls = ''
            if receiver in types:
                cls = types[receiver]
            elif receiver in self.links:
                cls = receiver
            elif owner:
                cls = self.field_type(owner, receiver)
            for key in self.declaring(cls, name) if cls in self.links else ():
                edges.append((key, plain))
        for match in _CALL.finditer(code, method.body_start, method.body_end):
            name = match.group(2)
            if name in _KEYWORDS or match.start(2) in taken or not owner:
                continue
            plain = _plain(code, method, match.start())
            if match.group(1) == 'super':
                for ancestor in self.ancestors(owner)[1:]:
                    if (ancestor, name) in self.methods:
                        edges.append(((ancestor, name), plain))
                        break
                continue
            if owner == _READINESS and name in COUNTERS and name != method.name:
                counters.append((match.start(2), name, plain))
                continue
            for key in self.declaring(owner, name):
                edges.append((key, plain))
        edges = [edge for edge in edges if edge[0][0] != _READINESS]
        self._calls[cache_key] = (edges, counters)
        return self._calls[cache_key]


def counter_sites(project, graph=None):
    """Every counter call: [(source, method, offset, name, plain)] in source order."""
    graph = graph or _Graph(project)
    sites = []
    for entries in graph.methods.values():
        for source, method in entries:
            sites.extend((source, method, offset, name, plain)
                         for offset, name, plain in graph.calls(source, method)[1])
    return sorted(sites, key=lambda site: (site[0].rel, site[2]))


def analyse(project):
    """({(path, offset): (source, method, counter name, method keys from the init root)}, all sites)."""
    graph = _Graph(project)
    flagged = {}
    for root in sorted(key for key in graph.methods if is_init_name(*key)):
        paths, queue = {root: (root,)}, deque([root])
        while queue:
            current = queue.popleft()
            for source, method in graph.methods[current]:
                edges, counters = graph.calls(source, method)
                for offset, name, plain in counters:
                    if plain:
                        flagged.setdefault((source.rel, offset), (source, method, name, paths[current]))
                for target, plain in edges:
                    if plain and target not in paths:
                        paths[target] = paths[current] + (target,)
                        queue.append(target)
    return flagged, counter_sites(project, graph)


_CACHE = {}


def rule_use_init_path(project, source):
    """enforce_lint adapter; the project-wide analysis runs once per project."""
    from tools.validate.enforce_lint import _finding, _symbol
    if _CACHE.get('project') is not project:
        _CACHE.clear()
        _CACHE['project'] = project
        _CACHE['flagged'] = analyse(project)[0]
    for (path, offset), (src, method, name, chain) in sorted(_CACHE['flagged'].items()):
        if path == source.rel:
            via = ' -> '.join(f'{owner}.{member}' for owner, member in chain)
            yield _finding(RULE, source, offset, _symbol(method), f'{name} reached from init via {via}: {RULES[RULE]}')


def main():
    from pathlib import Path
    from tools.validate import enforce_lint, enforce_source
    root = Path(__file__).resolve().parents[2]
    project = enforce_lint.Project(enforce_source.mod_sources(root))
    flagged, sites = analyse(project)
    print(f'counter call sites: {len(sites)}; safe: {len(sites) - len(flagged)}; flagged: {len(flagged)}')
    for (path, offset), (src, method, name, chain) in sorted(flagged.items()):
        print(f'  {path}:{src.line_of(offset)} {name} via ' + ' -> '.join(f'{o}.{m}' for o, m in chain))
    return 1 if flagged else 0


if __name__ == '__main__':
    raise SystemExit(main())
