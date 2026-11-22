"""Run only the unit-test modules that a set of changed Python files can affect (unittest only).

A changed ``tools/x/y.py`` selects, deterministically and without importing anything:
  * the changed test modules themselves (``tests/unit/test_*.py`` and ``tests/test_*.py``);
  * ``tests/unit/test_y.py`` (name convention) when it exists;
  * every test module that imports the changed module, directly (depth 1) or through other repository
    modules (depth 2 by default), found by scanning import lines.
Transitive levels are added whole while the selection stays within ``--max-modules``; a level that would
exceed it is dropped and named in the output. The direct level can never be dropped: if it alone exceeds the
cap the run is refused (exit 2) instead of widening toward the full suite. This never runs pytest, never the
full unit suite and never the slow suite. It proves nothing about DayZ behaviour; it only runs Python tooling tests.
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
TEST_DIRS = ('tests/unit', 'tests')
SKIP_PARTS = frozenset({'__pycache__', '.git', 'build', 'out', 'third_party', 'node_modules'})
DEFAULT_DEPTH = 2
DEFAULT_MAX_MODULES = 80


def module_name(relative):
    parts = list(Path(relative).with_suffix('').parts)
    if parts and parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts)


def is_test(relative):
    path = Path(relative)
    return (path.suffix == '.py' and path.name.startswith('test_')
            and path.parent.as_posix() in TEST_DIRS)


def repo_modules(root):
    """{dotted module: relative path} for Python files under tools/ and tests/ (never tests/slow)."""
    root = Path(root)
    found = {}
    for top in ('tools', 'tests'):
        base = root / top
        if not base.is_dir():
            continue
        for path in sorted(base.rglob('*.py')):
            relative = path.relative_to(root)
            if SKIP_PARTS.intersection(relative.parts) or relative.parts[:2] == ('tests', 'slow'):
                continue
            found[module_name(relative.as_posix())] = relative.as_posix()
    return found


_FROM = re.compile(r'^[ \t]*from[ \t]+(\.*[\w.]*)[ \t]+import[ \t]*(\([^)]*\)|[^\n]*)', re.M)
_IMPORT = re.compile(r'^[ \t]*import[ \t]+([^\n#;]*)', re.M)


def import_names(text):
    """(level, module, imported names) per import statement, found by a line scan.

    A scan, not a parse: an import-looking line inside a string only over-selects a test, and the whole
    repository is read in milliseconds instead of building ~300 syntax trees."""
    for match in _FROM.finditer(text):
        module = match.group(1)
        level = len(module) - len(module.lstrip('.'))
        listed = re.sub(r'#[^\n]*', '', match.group(2)).replace('(', ' ').replace(')', ' ')
        names = [n.split(' as ')[0].strip() for n in listed.split(',')]
        yield level, module.lstrip('.'), [n for n in names if n.isidentifier()]
    for match in _IMPORT.finditer(text):
        for part in match.group(1).split(','):
            name = part.split(' as ')[0].strip()
            if name:
                yield 0, name, []


def imports_of(root, relative, modules):
    """Repository modules that the file imports (any nesting, including lazy imports)."""
    try:
        text = (Path(root) / relative).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return set()
    here = Path(relative).parent
    package = module_name(here.as_posix()) if here.parts else ''
    names = set()
    for level, module, imported in import_names(text):
        base = module
        if level:
            anchor = package.split('.') if package else []
            anchor = anchor[:len(anchor) - (level - 1)] if level > 1 else anchor
            base = '.'.join(anchor + ([module] if module else []))
        names.add(base)
        names.update(base + '.' + name if base else name for name in imported)
    found = set()
    for name in names:
        # `import a.b.c` also executes a and a.b when they are modules of this repository.
        parts = name.split('.')
        for end in range(1, len(parts) + 1):
            candidate = '.'.join(parts[:end])
            if candidate in modules:
                found.add(candidate)
        # A script-style bare import (`import probe_runtime`) resolves beside the importing file.
        sibling = module_name((here / (parts[0] + '.py')).as_posix()) if here.parts else ''
        if sibling in modules:
            found.add(sibling)
    found.discard(module_name(relative))
    return found


def importer_graph(root, modules):
    """{module: set of repository modules that import it}."""
    reverse = {}
    for name, relative in modules.items():
        for imported in imports_of(root, relative, modules):
            reverse.setdefault(imported, set()).add(name)
    return reverse


def select(changed, root=ROOT, depth=DEFAULT_DEPTH, max_modules=DEFAULT_MAX_MODULES):
    """Return (test modules in run order, notes, changed Python files that no test maps to)."""
    root = Path(root)
    modules = repo_modules(root)
    relatives = {relative: name for name, relative in modules.items()}
    reverse = importer_graph(root, modules)
    levels = [set() for _ in range(depth + 1)]       # levels[k]: test modules first reached at depth k
    unmapped = []
    for relative in sorted({Path(p).as_posix() for p in changed if str(p).endswith('.py')}):
        if not (root / relative).is_file():
            continue            # a deletion has nothing left to test
        found = [set() for _ in range(depth + 1)]
        if is_test(relative):
            found[1].add(module_name(relative))
        name = relatives.get(relative)
        if name is not None:
            conventional = 'tests/unit/test_%s.py' % Path(relative).stem
            if conventional in relatives:
                found[1].add(module_name(conventional))
            seen, frontier = {name}, {name}
            for level in range(1, depth + 1):
                frontier = {i for n in frontier for i in reverse.get(n, ())} - seen
                seen |= frontier
                found[level].update(i for i in frontier if is_test(modules[i]))
        if not any(found):
            unmapped.append(relative)
        for level in range(1, depth + 1):
            levels[level] |= found[level]
    chosen, notes = set(levels[1]), []
    if len(chosen) > max_modules:
        return sorted(chosen), ['direct level selects %d test modules, over --max-modules %d'
                                % (len(chosen), max_modules)], unmapped
    for level in range(2, depth + 1):
        extra = levels[level] - chosen
        if len(chosen) + len(extra) > max_modules:
            notes.append('depth-%d importers dropped (%d more test modules would pass --max-modules %d)'
                         % (level, len(extra), max_modules))
            break
        chosen |= extra
    return sorted(chosen), notes, unmapped


def git_changed(base, root=ROOT):
    """Committed, staged, unstaged and untracked paths relative to base (read-only git queries)."""
    names = set()
    for command in (['git', 'diff', '--name-only', '-z', base, '--'],
                    ['git', 'ls-files', '--others', '--exclude-standard', '-z']):
        result = subprocess.run(command, cwd=root, capture_output=True, check=True, timeout=30)
        names.update(result.stdout.decode('utf-8', errors='replace').split('\0'))
    return sorted(name for name in names if name)


def run(modules, root=ROOT, timeout=900):
    command = [sys.executable, '-B', '-m', 'unittest', *modules]
    return subprocess.run(command, cwd=root, timeout=timeout).returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--base', metavar='REF', help='changed files from git relative to REF')
    source.add_argument('--files', nargs='+', metavar='PATH', help='explicit repository-relative changed files')
    parser.add_argument('--depth', type=int, default=DEFAULT_DEPTH, help='importer depth (1 = direct importers only)')
    parser.add_argument('--max-modules', type=int, default=DEFAULT_MAX_MODULES)
    parser.add_argument('--list', action='store_true', help='print the selected test modules and exit')
    parser.add_argument('--timeout', type=int, default=900)
    args = parser.parse_args(argv)
    if args.depth < 1 or args.max_modules < 1:
        parser.error('--depth and --max-modules must be at least 1')
    try:
        changed = git_changed(args.base) if args.base else args.files
    except (OSError, subprocess.SubprocessError):
        print('test_changed: cannot read changed files; check the base revision')
        return 1
    modules, notes, unmapped = select(changed, ROOT, args.depth, args.max_modules)
    for note in notes:
        print('test_changed: ' + note)
    for path in unmapped:
        print('test_changed: no unit test imports or is named for ' + path)
    if any(note.startswith('direct level') for note in notes):
        print('test_changed: refusing to widen toward the full suite; change fewer shared modules per run')
        return 2
    if not modules:
        print('test_changed: no unit tests map to the changed Python files')
        return 0
    print('test_changed: running %d test module(s)' % len(modules))
    if args.list:
        print('\n'.join(modules))
        return 0
    try:
        return run(modules, ROOT, args.timeout)
    except subprocess.TimeoutExpired:
        print('test_changed: timed out after %d s' % args.timeout)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
