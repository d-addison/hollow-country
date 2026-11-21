"""Static test triage. Never import tests or execute their fixtures.

Counts are AST test definitions (not generated unittest cases or subTest runs).
A/B/C/E are exclusive recommendations; D is an overlapping diagnostic, not a
claim that unexecuted tests pass. Conservative dependency closure deliberately
flags mixed methods for review. JSON includes the evidence behind every choice.
"""
import argparse
import ast
import builtins
from collections import Counter, defaultdict
import io
import json
from pathlib import Path
import re
import symtable
import tokenize

CATEGORIES = ('A', 'B', 'C', 'D', 'E')


def call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return call_name(node.value) + '.' + node.attr
    return ''


def literal(node):
    try:
        ast.literal_eval(node)
        return True
    except (ValueError, TypeError):
        return False


def analyze(path, root):
    """Return serializable evidence, using only AST and local import existence."""
    relative = path.relative_to(root).as_posix()
    try:
        source = path.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=relative)
        # Compile only for Python syntax checks such as return outside a function.
        # The resulting code object is never executed.
        compile(tree, relative, 'exec')
        symbols = symtable.symtable(source, relative, 'exec')
    except (SyntaxError, UnicodeError):
        return dict(path=relative, tests=[], categories={'D': 0}, diagnostics=['parse error'])
    definitions = defaultdict(list)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            definitions[node.name].append(node)
    module_nodes = [n for n in tree.body if not isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
    literal_globals = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    literal_globals[target.id] = node.value.value
    contract_lines = {token.start[0] for token in tokenize.generate_tokens(io.StringIO(source).readline)
                      if token.type == tokenize.COMMENT and 'external contract' in token.string.lower()}
    imports = []
    missing = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
            if node.module.startswith(('tests.', 'tools.')):
                target = root.joinpath(*node.module.split('.'))
                if not target.with_suffix('.py').exists() and not target.is_dir():
                    missing.append(node.module)
        elif isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.Call) and call_name(node.func).endswith('import_module'):
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                imports.append(node.args[0].value)
    # Unbound Python globals are candidates only: dynamic globals/exec can supply
    # names. Keep these diagnostics distinct from observed runtime failures.
    bound = {x.get_name() for x in symbols.get_symbols() if x.is_assigned() or x.is_imported() or x.is_namespace()}
    def global_assignments(scope):
        assigned = {symbol.get_name() for symbol in scope.get_symbols()
                    if symbol.is_global() and symbol.is_assigned()}
        for child in scope.get_children():
            assigned.update(global_assignments(child))
        return assigned
    bound.update(global_assignments(symbols))
    unbound = set()
    def inspect_scope(scope):
        for symbol in scope.get_symbols():
            if symbol.is_referenced() and symbol.is_global() and symbol.get_name() not in bound and not hasattr(builtins, symbol.get_name()):
                if symbol.get_name() not in {'__file__', '__name__', '__package__', '__path__'}:
                    unbound.add(symbol.get_name())
        for child in scope.get_children():
            inspect_scope(child)
    if not any(isinstance(n, ast.ImportFrom) and any(a.name == '*' for a in n.names) for n in ast.walk(tree)):
        inspect_scope(symbols)
    imported_ports = {a.asname or a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                      and (n.module or '').startswith('tests.') for a in n.names
                      if a.name in ('translate', 'bind', 'policy_functions')}
    walk_cache = {}
    def walk(node):
        key = id(node)
        if key not in walk_cache:
            walk_cache[key] = list(ast.walk(node))
        return walk_cache[key]
    results = []
    for cls in tree.body:
        methods = cls.body if isinstance(cls, ast.ClassDef) else [cls]
        setup = [n for n in methods if isinstance(n, ast.FunctionDef) and n.name in ('setUp', 'setUpClass')]
        for method in methods:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) or not method.name.startswith('test'):
                continue
            nodes = [method, *setup, *module_nodes]
            seen = set()
            # Follow local helper calls and their reads without executing them.
            for node in nodes:
                for ref in walk(node):
                    name = ref.id if isinstance(ref, ast.Name) else ref.attr if isinstance(ref, ast.Attribute) else ''
                    if name not in seen:
                        seen.add(name)
                        nodes.extend(definitions.get(name, []))
            walked = [n for node in nodes for n in walk(node)]
            strings = [n.value for n in walked if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            calls = [n for n in walked if isinstance(n, ast.Call)]
            assertions = [n for n in ast.walk(method) if isinstance(n, ast.Call) and call_name(n.func).split('.')[-1].startswith('assert')]
            kinds = Counter(call_name(n.func).split('.')[-1] for n in assertions)
            kinds['assert'] += sum(isinstance(n, ast.Assert) for n in ast.walk(method))
            kinds += Counter()  # drop zero entries
            literal_operands = sum(literal(a) for n in assertions for a in n.args[:2])
            readers = sorted({call_name(n.func).split('.')[-1] for n in calls if call_name(n.func).split('.')[-1] in
                              ('read_text', 'read_bytes', 'open', 'parse', 'load', 'loads', 'translate', 'bind', 'exec')})
            enforce = any(re.search(r'\.(?:c|cpp)(?:$|["\s/])', s) for s in strings)
            authored = any(re.search(r'\.(?:json|xml|csv)(?:$|["\s/])', s) and not s.lstrip().startswith(('{', '<', '[')) for s in strings)
            translates = bool(imported_ports & seen)
            tools = sorted({x for x in imports if x.startswith('tools.')})
            # E requires an actual literal pin operand, not merely use of hashing.
            pin_operands = [literal_globals.get(a.id) if isinstance(a, ast.Name) else a.value
                            if isinstance(a, ast.Constant) else None
                            for n in assertions for a in n.args[:2]]
            pins = [value for value in pin_operands if isinstance(value, str) and re.fullmatch(r'[a-fA-F0-9]{64}', value)]
            snapshots = sum(call_name(n.func).split('.')[-1] in ('assertEqual', 'assertListEqual', 'assertDictEqual', 'assertSetEqual', 'assertIn', 'assertNotIn')
                            and any(literal(a) for a in n.args[:2]) for n in assertions)
            contract_comment = any(method.lineno - 2 <= line <= method.end_lineno for line in contract_lines)
            synthetic = any(call_name(n.func).split('.')[-1] in ('TemporaryDirectory', 'mkdtemp', 'MemoryTree') for n in calls)
            version_pins = sum(call_name(n.func).split('.')[-1] == 'assertEqual'
                               and any(literal(a) for a in n.args[:2])
                               and any(isinstance(a, ast.Constant) and isinstance(a.value, str)
                                       and a.value in ('schema', 'schema_version', 'wire_version', 'protocol_version')
                                       for a in ast.walk(n)) for n in assertions)
            if (enforce and readers and not tools and not synthetic) or translates:
                category = 'A'
            elif pins or version_pins or (contract_comment and literal_operands):
                category = 'E'
            elif authored and snapshots and not synthetic:
                category = 'B'
            else:
                category = 'C'
            results.append(dict(name=(cls.name + '.' if isinstance(cls, ast.ClassDef) else '') + method.name,
                                category=category, assertions=dict(sorted(kinds.items())), literal_operands=literal_operands,
                                reads=readers, enforce_input=enforce, data_input=authored, synthetic_fixture=synthetic,
                                tools=tools, snapshot_assertions=snapshots, external_hash_pins=len(pins), external_version_pins=version_pins))
    counts = Counter(r['category'] for r in results)
    assertion_counts = Counter()
    for row in results:
        assertion_counts.update(row['assertions'])
    if missing or unbound:
        counts['D'] = len(results)
    return dict(path=relative, tests=results, categories=dict(sorted(counts.items())),
                assertions=dict(sorted(assertion_counts.items())),
                literal_operands=sum(r['literal_operands'] for r in results),
                diagnostics=(['missing local import: ' + x for x in sorted(set(missing))]
                             + ['unbound Python global candidate: ' + x for x in sorted(unbound)]))


def audit(root):
    files = [analyze(p, root) for p in sorted((root / 'tests').rglob('*.py')) if p.name != '__init__.py']
    suites = {}
    for file in files:
        suite = file['path'].split('/')[1] if len(file['path'].split('/')) > 2 else '(root)'
        summary = suites.setdefault(suite, {c: dict(files=0, tests=0) for c in CATEGORIES})
        for category, count in file['categories'].items():
            summary[category]['files'] += 1
            summary[category]['tests'] += count
    return dict(method='AST definitions; A/B/C/E exclusive per test; D overlaps; heuristic review required',
                files=files, suites=suites)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--json', action='store_true', help='include per-method evidence')
    args = parser.parse_args()
    report = audit(args.root.resolve())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print(report['method'])
    print('file\t' + '\t'.join(CATEGORIES))
    for row in report['files']:
        print(row['path'] + '\t' + '\t'.join(str(row['categories'].get(c, 0)) for c in CATEGORIES))
        for diagnostic in row['diagnostics']:
            print('  D: ' + diagnostic)
    print('suite\t' + '\t'.join(c + ' files/tests' for c in CATEGORIES))
    for suite, counts in sorted(report['suites'].items()):
        print(suite + '\t' + '\t'.join(f"{counts[c]['files']}/{counts[c]['tests']}" for c in CATEGORIES))


if __name__ == '__main__':
    main()
