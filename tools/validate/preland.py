"""Ordered developer gates; skips are visible and never native acceptance."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import re
import tempfile
from typing import NamedTuple
import sys

from tools.validate.cfgconvert_check import SKIPPED
from tools.release.rpt_summary import filtered
from tools.validate.wiring_audit import OFFLINE_EXCLUSIONS
from tools.validate import layout_lint

ROOT = Path(__file__).resolve().parents[2]
NATIVE = Path.home() / '.cache/hollow-country/native-scripts/scripts-1.30.164289'
CHECKS = ('enforce_lint', 'enforce_perf', 'layout_lint', 'cfgconvert_check',
          'settings_consistency', 'wiring_audit', 'regenerate_all', 'generated_digests')


# This list is the CI contract, not a blanket permission to skip a whole gate.
CI_EXCLUSIONS = {
    'cfgconvert_check': 'requires the installed Windows DayZ Tools cfgconvert executable',
    'wb_compile': 'requires installed Windows Workbench; engine compilation is a separate lead gate',
    'enforce_lint.native': 'installed native and Workshop APIs are absent; use pinned names with --no-native',
    'layout_lint.textures': 'installed vanilla/Workshop texture index is absent; owned UI checks still run',
    'layout_lint.native_review': 'only existing reasoned texture-baseline references may defer native review',
    'regenerate_all.inventory_sizes': 'requires installed vanilla and Workshop provider Addons',
    'regenerate_all.firearms': 'requires a pristine installed stock mission',
    'regenerate_all.snafu_optional': 'requires a pristine stock mission and external verification report',
    'regenerate_all.tactical_flava_optional': 'requires a pristine stock mission and external verification report',
    'regenerate_all.new_buildings': 'requires a pristine installed stock mission',
    'regenerate_all.loot_point_preserve': 'requires a pristine installed stock mission',
    'regenerate_all.gui_icons': 'requires the Windows DayZ Tools ImageToPAA converter',
    'regenerate_all.anims_config': 'requires the installed stock zombie addon',
    **{'regenerate_all.' + name: 'requires a pristine installed stock mission'
       for name in ('economy', 'ai_patrols')},
    'generated_digests.inventory_sizes': 'requires installed vanilla and Workshop provider Addons',
    **{'generated_digests.' + name: 'requires a pristine installed stock mission'
       for name in ('firearms', 'loot_point_preserve', 'snafu_optional',
                    'tactical_flava_optional', 'new_buildings', 'economy', 'ai_patrols')},
    'generated_digests.anims_config': 'requires the installed stock zombie addon',
    'generated_digests.gui_icons': 'requires the Windows DayZ Tools ImageToPAA converter',
    **{'wiring_audit.' + name: reason for name, reason in OFFLINE_EXCLUSIONS.items()},
    'wiring_audit.external_classes': 'installed vanilla/Workshop class caches are absent; repository wiring still runs',
}
# Match only the documented coverage notices, never arbitrary output from a named gate.
CI_NOTICES = {
    'layout_lint': (r'^layout_lint: NOTICE installed texture index unavailable; skipping unresolved vanilla file checks ',
                    r'^layout_lint: SKIP explicit offline run$'),
    'enforce_lint': (r'^enforce_lint: .* native=no$',),
    'regenerate_all': (
        r'^SKIP inventory_sizes (?:required addons directory unavailable|installed inventory provider Addons directory unavailable)$',
        r'^SKIP (?:firearms|snafu_optional|tactical_flava_optional|new_buildings|economy|ai_patrols) required source directory unavailable$',
        r'^SKIP loot_point_preserve existing validation passed; byte regeneration: stock mission mapgrouppos\.xml unavailable$',
        r'^SKIP gui_icons existing validation passed; byte regeneration: ImageToPAA (?:converter|Windows interop) unavailable$',
        r'^SKIP anims_config required addons directory unavailable$',
        r'^regenerate_all: pass checked=\d+ failed=0 skipped=\d+$',
    ),
    'generated_digests': (
        r'^SKIP inventory_sizes inventory provider Addons unavailable$',
        r'^SKIP (?:firearms|snafu_optional|tactical_flava_optional|economy) stock mission cfgeconomycore\.xml unavailable$',
        r'^SKIP (?:loot_point_preserve|new_buildings|ai_patrols) stock mission mapgrouppos\.xml unavailable$',
        r'^SKIP anims_config stock zombie addon unavailable$',
        r'^SKIP gui_icons ImageToPAA (?:converter|Windows interop) unavailable$',
    ),
    'wiring_audit': (
        *(r'^EXCLUDED ' + re.escape(name + ': ' + reason) + r'$'
          for name, reason in OFFLINE_EXCLUSIONS.items()),
        r'^NOTE Optional class source unavailable: ',
        r'^NOTE External class-index roots missing: ',
        r'^NOTE Workshop class-index coverage incomplete: ',
    ),
}
INCOMPLETE = re.compile(r'\b(?:skip(?:ped|ping)?|unavailable|not available|missing input|native=no)\b'
                        r'|External class-index roots missing|Workshop class-index coverage incomplete', re.I)


class CheckResult(NamedTuple):
    code: int
    output: str = ''


def incomplete_lines(name, output, ci=False):
    lines = output.splitlines()
    notices = CI_NOTICES.get(name, ())
    if ci and name == 'layout_lint':
        # R7 emits exit 2 for its explicit offline subset and lists native-review
        # references. Permit only exact, reasoned entries from its owned baseline.
        baseline = json.loads(layout_lint.BASELINE.read_text(encoding='utf-8'))
        notices += tuple(r'^SKIPPED ' + re.escape(row['reference']) + r'$'
                         for row in baseline['skipped'] if row.get('reason', '').strip())
    gaps = [line for line in lines
            if INCOMPLETE.search(re.sub(r'\bskipped=0\b', '', line)) and not (
                ci and any(re.search(pattern, line) for pattern in notices))]
    if ci and name == 'regenerate_all':
        # A summary alone must not conceal an unnamed skipped generator.
        skips = sum(line.startswith('SKIP ') for line in lines)
        for line in lines:
            summary = re.fullmatch(r'regenerate_all: pass checked=\d+ failed=0 skipped=(\d+)', line)
            if summary and int(summary[1]) != skips:
                gaps.append('regenerate_all: skipped count lacks matching generator results')
    return gaps


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
    return CheckResult(result.returncode, result.stdout + "\n" + result.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-scripts', type=Path, default=NATIVE)
    parser.add_argument('--changed', metavar='BASE', help='limit supported gates; others retain full-tree scope')
    parser.add_argument('--wb', action='store_true', help='also run tools.release.wb_compile when installed')
    parser.add_argument('--strict', action='store_true', help='fail on any unavailable/skipped coverage or missing input')
    parser.add_argument('--profile', choices=('local', 'ci'), default='local',
                        help='ci: deterministic Windows-free checks with listed installed-input exclusions')
    args = parser.parse_args(argv)
    if args.profile == 'ci' and (args.wb or args.changed):
        parser.error('--profile ci always runs the full offline tree; --wb/--changed are local only')
    try:
        paths = changed_files(args.changed) if args.changed else None
    except (OSError, subprocess.SubprocessError):
        print('preland: cannot read changed files; check base revision')
        return 1
    # Explicitly absent directories make generator coverage independent of host installs.
    with tempfile.TemporaryDirectory(prefix='hc-preland-') as scratch:
        return execute(args, paths, Path(scratch))


def execute(args, paths, scratch):
    ci = args.profile == 'ci'
    if ci:
        print('preland: CI exclusions (installed checks remain local/lead obligations):')
        for name, reason in CI_EXCLUSIONS.items():
            print(f'  {name}: {reason}')
    rows = []
    failed = False
    incomplete = False
    checks = [('tools.package.' + name if name in {'regenerate_all', 'generated_digests'} else 'tools.validate.' + name, name)
              for name in CHECKS]
    if args.wb:
        checks.append(('tools.release.wb_compile', 'wb_compile'))
    for module, name in checks:
        if ci and name in {'cfgconvert_check', 'wb_compile'}:
            rows.append((name, 'excluded: ' + CI_EXCLUSIONS[name], 'CI profile'))
            continue
        if importlib.util.find_spec(module) is None:
            rows.append((name, 'not available', 'full tree'))
            # These two gates are added by sibling workers; their absence is optional.
            if args.strict or ci or name not in {'layout_lint', 'wb_compile'}:
                failed = True
            else:
                incomplete = True
            continue
        arguments = []
        scope = 'full tree'
        if name == 'enforce_lint':
            arguments = ['--no-native'] if ci else ['--native-scripts', str(args.native_scripts.expanduser())]
        elif name in {'regenerate_all', 'generated_digests'}:
            arguments = ['--check']
            if ci:
                arguments += ['--addons', str(scratch / 'addons'), '--workshop', str(scratch / 'workshop'),
                              '--source', str(scratch / 'stock'),
                              '--image-to-paa', str(scratch / 'ImageToPAA.exe')]
            if args.strict:
                arguments += ['--require-installed']
        elif name == 'wiring_audit' and ci:
            arguments = ['--offline']
        elif name == 'layout_lint' and ci:
            arguments = ['--no-texture-index']
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
            result = run_check(module, arguments)
            code = result.code
            gaps = incomplete_lines(name, result.output, ci=ci and not args.strict)
            if name == 'generated_digests' and re.search(r'^FAIL\b', result.output, re.M):
                status = 'FAIL (digest receipt verification)'
                failed = True
            elif (args.strict or ci) and (gaps or code == SKIPPED):
                status = 'FAIL (skipped/unavailable coverage)'
                failed = True
            elif name == 'cfgconvert_check' and code == SKIPPED:
                status = 'skipped: unavailable'
                incomplete = True
            elif (ci and not args.strict and name == 'layout_lint'
                  and code == layout_lint.SKIPPED and not gaps
                  and 'layout_lint: SKIP explicit offline run' in result.output.splitlines()):
                status = 'repository checks pass; textures/native review excluded'
            elif ci and name == 'wiring_audit' and code == 0:
                status = 'repository checks pass; stock mission excluded'
            else:
                status = 'pass' if code == 0 else f'FAIL ({code})'
                failed |= code != 0
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
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
