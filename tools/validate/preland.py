"""Ordered developer gates; skips are visible and never native acceptance."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys

from tools.validate.cfgconvert_check import SKIPPED
from tools.release.rpt_summary import filtered

ROOT = Path(__file__).resolve().parents[2]
NATIVE = Path.home() / '.cache/hollow-country/native-scripts/scripts-1.30.164289'
CHECKS = ('enforce_lint', 'enforce_perf', 'layout_lint', 'cfgconvert_check',
          'settings_consistency', 'wiring_audit')


def changed_files(base):
    """Read-only git queries: committed, staged, unstaged and untracked inputs."""
    names = set()
    for command in (['git', 'diff', '--name-only', '-z', base, '--'],
                    ['git', 'ls-files', '--others', '--exclude-standard', '-z']):
        result = subprocess.run(command, cwd=ROOT, capture_output=True, check=True, timeout=30)
        names.update(result.stdout.decode('utf-8', errors='replace').split('\0'))
    return sorted(p for p in names if p)


def run_check(module, arguments):
    result = subprocess.run([sys.executable, '-B', '-m', module, *arguments], cwd=ROOT,
                            capture_output=True, text=True, errors='replace', timeout=600)
    for line in (result.stdout + '\n' + result.stderr).splitlines():
        safe = filtered(line)
        if safe:
            print(safe)
    return result.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-scripts', type=Path, default=NATIVE)
    parser.add_argument('--changed', metavar='BASE', help='limit supported gates; others retain full-tree scope')
    parser.add_argument('--wb', action='store_true', help='also run tools.release.wb_compile when installed')
    args = parser.parse_args(argv)
    try:
        paths = changed_files(args.changed) if args.changed else None
    except (OSError, subprocess.SubprocessError):
        print('preland: cannot read changed files; check base revision')
        return 1
    rows = []
    failed = False
    incomplete = False
    checks = [('tools.validate.' + name, name) for name in CHECKS]
    if args.wb:
        checks.append(('tools.release.wb_compile', 'wb_compile'))
    for module, name in checks:
        if importlib.util.find_spec(module) is None:
            rows.append((name, 'not available', 'full tree'))
            # These two gates are added by sibling workers; their absence is optional.
            if name not in {'layout_lint', 'wb_compile'}:
                failed = True
            else:
                incomplete = True
            continue
        arguments = []
        scope = 'full tree'
        if name == 'enforce_lint':
            arguments = ['--native-scripts', str(args.native_scripts.expanduser())]
        elif paths is not None and name == 'cfgconvert_check':
            # enforce_perf always runs on the full tree: its baseline ratchet (stale entries) and rule
            # changes are only checked by a full-project run.
            if not paths:
                rows.append((name, 'no applicable changes', 'changed files'))
                continue
            arguments = paths
            scope = 'changed addons (non-mod change: full tree)'
        print(f'preland: running {name} ({scope})', flush=True)
        try:
            code = run_check(module, arguments)
            if name == 'cfgconvert_check' and code == SKIPPED:
                status = 'skipped: unavailable'
                incomplete = True
            else:
                status = 'pass' if code == 0 else f'FAIL ({code})'
                failed |= code != 0
        except (OSError, subprocess.SubprocessError):
            status = 'FAIL (launch/timeout)'
            failed = True
        rows.append((name, status, scope))
    print('\nCheck | Result | Scope')
    print('--- | --- | ---')
    for row in rows:
        print(' | '.join(row))
    print('preland: ' + ('FAILED' if failed else 'INCOMPLETE (native/optional checks pending)' if incomplete else 'PASS')
          + '; engine compile/boot acceptance remains separate')
    return 1 if failed else SKIPPED if incomplete else 0


if __name__ == '__main__':
    raise SystemExit(main())
