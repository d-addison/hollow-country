"""Ordered developer gates; skips are visible and never native acceptance."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import re
import tempfile
from typing import NamedTuple
import sys

from tools.package.regenerate_all import GEOMETRY_COMPARE_TIMEOUTS
from tools.validate.cfgconvert_check import SKIPPED
from tools.release.rpt_summary import filtered
from tools.release.test_queue import submit_line
from tools.release.ship_inputs import ADDONS
from tools.validate.wiring_audit import OFFLINE_EXCLUSIONS
from tools.validate import layout_lint, source_cache

ROOT = Path(__file__).resolve().parents[2]
NATIVE = Path.home() / '.cache/hollow-country/native-scripts/scripts-1.30.164289'
CHECKS = ('enforce_lint', 'enforce_perf', 'layout_lint', 'cfgconvert_check',
          'settings_consistency', 'wiring_audit', 'regenerate_all', 'generated_digests',
          'mission_sources', 'hygiene', 'hc_events', 'ce_slot_pressure', 'world_mesh_audit',
          'asset_lint')
# Checks whose entry point is not tools.validate.<name>. hygiene runs the whole repository
# scan (secrets, local paths, banned provider text in mods/mission/config); hc_events and
# ce_slot_pressure use quiet mission_sources summaries instead of 10-20 KB JSON lines.
COMMANDS = {
    'hygiene': ('tools.validate.hygiene', ['--summary']),
    'hc_events': ('tools.validate.mission_sources', ['--events']),
    'ce_slot_pressure': ('tools.validate.mission_sources', ['--ce-slots']),
    'world_mesh_audit': ('tools.audit.world_mesh_audit', []),
}
# Gates that need installed or staged inputs; the CI profile lists them as exclusions.
CI_ONLY_EXCLUDED = ('cfgconvert_check', 'wb_compile', 'ce_slot_pressure', 'world_mesh_audit')
# Built assets for asset_lint: <stem>.p3d (or <stem>.ir.json) beside <stem>.model.cfg and
# <stem>.sources.json; the config is the owned assets addon's config.cpp. assets_src holds
# only ops recipes today, so the gate reports no applicable inputs until a built asset lands.
ASSET_SOURCES = ROOT / 'assets_src'
ASSET_CONFIG = ROOT / 'mods/HollowCountryAssets/config.cpp'


# This list is the CI contract, not a blanket permission to skip a whole gate.
CI_EXCLUSIONS = {
    'cfgconvert_check': 'requires the installed Windows DayZ Tools cfgconvert executable',
    'wb_compile': 'requires installed Windows Workbench; engine compilation is a separate lead gate',
    'ce_slot_pressure': 'requires a staged mission (stock files plus installed overlays); pass --ce-mission locally',
    'world_mesh_audit': 'requires installed vanilla Addons (the in-repo ODOL reader is used)',
    'enforce_lint.native': 'installed native and Workshop APIs are absent; use pinned names with --no-native',
    'layout_lint.textures': 'installed vanilla/Workshop texture index is absent; owned UI checks still run',
    'layout_lint.native_review': 'only reasoned texture-baseline references and vanilla set:dayz_gui members may defer native review',
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
        r'^EXCLUDED external_classes: installed vanilla/Workshop class caches are absent; repository wiring still runs; count=\d+$',
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
    if name == 'layout_lint':
        # The successful texture inventory reports zero counts in JSON.
        complete = 'layout_lint: texture counts {"skipped": 0, "unresolved": 0}'
        lines = [line for line in lines if line != complete]
    notices = CI_NOTICES.get(name, ())
    if ci and name == 'layout_lint':
        # R7 emits exit 2 for its explicit offline subset and lists native-review
        # references. Permit only exact, reasoned entries from its owned baseline.
        baseline = json.loads(layout_lint.BASELINE.read_text(encoding='utf-8'))
        notices += tuple(r'^SKIPPED ' + re.escape(row['reference']) + r'$'
                         for row in baseline['skipped'] if row.get('reason', '').strip())
        # The vanilla dayz_gui imageset is only readable from the installed index; the
        # indexed local run resolves each member. Owned and unknown sets stay gaps.
        notices += (r'^SKIPPED [^\s:]+:\d+: imageset symbolic reference needs native review: '
                    r'set:dayz_gui image:[A-Za-z0-9_]+$',)
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


def asset_lint_runs(sources=None, config=None):
    """One asset_lint argument list per built asset, or a refusal string for a missing sidecar."""
    sources = ASSET_SOURCES if sources is None else Path(sources)
    config = ASSET_CONFIG if config is None else Path(config)
    runs = []
    for asset in sorted(p for pattern in ('*.p3d', '*.ir.json') for p in sources.rglob(pattern)):
        stem = asset.name[:-len('.ir.json')] if asset.name.endswith('.ir.json') else asset.stem
        model_cfg, listing = asset.with_name(stem + '.model.cfg'), asset.with_name(stem + '.sources.json')
        if not (model_cfg.is_file() and listing.is_file() and config.is_file()):
            return 'asset %s lacks its model.cfg, sources.json or the assets addon config' % asset.name
        runs.append([str(asset), '--model-cfg', str(model_cfg), '--config', str(config),
                     '--sources', str(listing)])
    return runs


def world_mesh_gap(addons):
    """Why the offline mesh audit cannot read installed data, or '' when it can."""
    if not addons.is_dir() or not any(addons.glob('*.pbo')):
        return 'installed vanilla Addons unavailable'
    return ''


# Checks run as separate processes; this git-ignored directory lets them share parsed Enforce sources
# (tools/validate/source_cache.py), so each authored file is parsed once per run.
SOURCE_CACHE_DIR = ROOT / 'build' / 'source-cache'


def run_check(module, arguments):
    environment = {**os.environ}
    environment.setdefault(source_cache.ENV, str(SOURCE_CACHE_DIR))
    timeout = 600
    if ('--require-installed' in arguments and '--geometry-addons' not in arguments
            and environment.get('HC_GENERATED_GEOMETRY_ADDONS')):
        if module == 'tools.package.regenerate_all':
            timeout += sum(GEOMETRY_COMPARE_TIMEOUTS.values())
        elif module == 'tools.package.generated_digests':
            timeout = 1800  # Same budget as the release checker.
    result = subprocess.run([sys.executable, '-B', '-m', module, *arguments], cwd=ROOT, env=environment,
                            capture_output=True, text=True, errors='replace', timeout=timeout)
    for line in (result.stdout + '\n' + result.stderr).splitlines():
        safe = filtered(line)
        if safe:
            print(safe)
    return CheckResult(result.returncode, result.stdout + "\n" + result.stderr)


def anim_lint_step(args, paths):
    """anim_lint gate for changed animation files: ((name, status, scope), failed, incomplete) or None.

    Deliberately outside CHECKS: it runs only when --changed lists an animation file (tools/anim,
    mods/HollowCountryAnims, .bvh/.anm) and lints the addon config plus each changed source.
    """
    if paths is None:
        return None
    from tools.validate import anim_lint
    files = anim_lint.changed_inputs(paths)
    if files is None:
        return None
    arguments = list(files)
    addons = Path(args.addons).expanduser()
    if addons.is_dir() and any(addons.glob('*.pbo')):
        arguments += ['--addons', str(addons)]
    if args.strict:
        arguments.append('--require-installed')
    print('preland: running anim_lint (changed animation files)', flush=True)
    try:
        result = run_check('tools.validate.anim_lint', arguments)
    except (OSError, subprocess.SubprocessError):
        return ('anim_lint', 'FAIL (launch/timeout)', 'changed files'), True, False
    if result.code != 0:
        return ('anim_lint', 'FAIL (%d)' % result.code, 'changed files'), True, False
    if 'not run (no installed Addons)' in result.output:
        return ('anim_lint', 'pass (stock comparison not run)', 'changed files'), False, True
    return ('anim_lint', 'pass', 'changed files'), False, False


def site_rules_step(args, paths):
    """site_rules for composed sites: ((name, status, scope) or None, failed).

    Gating (full tree, or --changed touching config/sites/ or a composed-*.json layer): any failing rule fails.
    Otherwise it prints the report-current summary, which never gates (today's layers fail by design).
    It runs in-process and adds a table row only when changed paths gate it or it fails, so the
    per-check list and row count of the other steps stay as they are.
    """
    import contextlib
    import io
    from tools.validate import site_rules
    on_paths = paths is not None and any(
        path.startswith('config/sites/') or re.match(r'config/map-overlays/layers/composed-[^/]*\.json$', path)
        for path in paths)
    gated = paths is None or on_paths
    print('preland: running site_rules (%s)' % ('gate' if gated else 'report only, never gates'), flush=True)
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):
            code = site_rules.main([] if gated else ['--report-current', '--summary'])
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        code = 1
        captured.write('site_rules: could not run\n')
    for line in captured.getvalue().splitlines():
        safe = filtered(line)
        if safe:
            print(safe)
    failed = gated and code != 0
    if failed:
        return ('site_rules', 'FAIL (%d)' % code, 'composed sites'), True
    if on_paths:
        return ('site_rules', 'pass', 'composed sites'), False
    return None, False


def changed_unit_tests(paths):
    """(row name, status, failed) for the unit-test modules mapped to the changed Python files."""
    python = [path for path in paths if path.endswith('.py')]
    if not python:
        return ('unit_tests_changed', 'no applicable changes', False)
    print('preland: running unit_tests_changed (tests mapped to changed Python files)', flush=True)
    try:
        result = run_check('tools.validate.test_changed', ['--files', *python])
    except (OSError, ValueError, subprocess.SubprocessError):
        return ('unit_tests_changed', 'FAIL (launch/timeout)', True)
    if result.code:
        return ('unit_tests_changed', f'FAIL ({result.code})', True)
    return ('unit_tests_changed', 'pass', False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-scripts', type=Path, default=NATIVE)
    parser.add_argument('--changed', metavar='BASE', help='limit supported gates; others retain full-tree scope')
    parser.add_argument('--ce-mission', type=Path, default=os.environ.get('HC_CE_MISSION') or None,
                        help='staged mission (stock plus installed overlays) for ce_slot_pressure; default HC_CE_MISSION')
    parser.add_argument('--addons', type=Path, default=ADDONS,
                        help='installed vanilla Addons; HC_GENERATED_GEOMETRY_ADDONS overrides mesh audit input')
    parser.add_argument('--wb', action='store_true', help='also run tools.release.wb_compile when installed')
    parser.add_argument('--strict', action='store_true', help='fail on any unavailable/skipped coverage or missing input')
    parser.add_argument('--native-census', type=Path, action='append', default=[],
                        help='original native interior census for regeneration/digests (repeatable, read-only)')
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
    checks = [(COMMANDS[name][0] if name in COMMANDS
               else 'tools.package.' + name if name in {'regenerate_all', 'generated_digests'}
               else 'tools.validate.' + name, name) for name in CHECKS]
    if args.wb:
        checks.append(('tools.release.wb_compile', 'wb_compile'))
    for module, name in checks:
        if ci and name in CI_ONLY_EXCLUDED:
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
        arguments = list(COMMANDS[name][1]) if name in COMMANDS else []
        runs = None
        scope = 'full tree'
        gap = ''
        if name == 'ce_slot_pressure':
            if args.ce_mission:
                arguments.append(str(Path(args.ce_mission).expanduser()))
            else:
                gap = 'staged CE mission not provided (--ce-mission or HC_CE_MISSION)'
        elif name == 'world_mesh_audit':
            addons = Path(os.environ.get('HC_GENERATED_GEOMETRY_ADDONS') or args.addons).expanduser().resolve()
            gap = world_mesh_gap(addons)
            arguments += ['--report', str(scratch / 'world-mesh-audit.json'), '--addons', str(addons)]
        elif name == 'asset_lint':
            runs = asset_lint_runs()
            if isinstance(runs, str):
                rows.append((name, 'FAIL (' + runs + ')', scope))
                failed = True
                continue
            if not runs:
                rows.append((name, 'no applicable inputs (assets_src holds no built MLOD/IR)', scope))
                continue
        if gap:
            # A named gap is never a pass: strict fails it, the local run is incomplete.
            rows.append((name, ('FAIL (skipped: ' if args.strict else 'skipped: ') + gap + (')' if args.strict else ''), scope))
            if args.strict:
                failed = True
            else:
                incomplete = True
            continue
        if name == 'enforce_lint':
            arguments = ['--no-native'] if ci else ['--native-scripts', str(args.native_scripts.expanduser())]
        elif name in {'regenerate_all', 'generated_digests'}:
            arguments = ['--check']
            for census in getattr(args, 'native_census', []):
                arguments += ['--native-census', str(census.expanduser().resolve())]
            if ci:
                arguments += ['--addons', str(scratch / 'addons'), '--geometry-addons', str(scratch / 'addons'),
                              '--workshop', str(scratch / 'workshop'), '--source', str(scratch / 'stock'),
                              '--snafu-report', str(scratch / 'snafu.json'),
                              '--tactical-flava-report', str(scratch / 'tf.json'),
                              '--image-to-paa', str(scratch / 'ImageToPAA.exe')]
            if args.strict:
                arguments += ['--require-installed']
                if not ci and args.addons != ADDONS:
                    arguments += ['--addons', str(args.addons.expanduser().resolve())]
                if not ci and name == 'regenerate_all' and args.native_scripts != NATIVE:
                    arguments += ['--native-scripts', str(args.native_scripts.expanduser().resolve())]
            elif ci and name == 'generated_digests':
                arguments += ['--waive-unavailable']
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
            if runs:
                results = [run_check(module, run) for run in runs]
                result = CheckResult(max(r.code for r in results), '\n'.join(r.output for r in results))
            else:
                result = run_check(module, arguments)
            code = result.code
            gaps = incomplete_lines(name, result.output, ci=ci and not args.strict)
            if name == 'world_mesh_audit':
                gaps = []  # Its summary always names skipped=N; the branch below judges it exactly.
            mesh = re.search(r'^world_mesh_audit: \w+ checked=\d+ findings=(\d+) skipped=(\d+)$', result.output, re.M)
            if name == 'world_mesh_audit' and code == 0 and mesh and int(mesh[2]):
                reasons = sorted(set(re.findall(r'^SKIP (\S+)$', result.output, re.M)))
                status = ('FAIL (skipped: ' if args.strict else 'skipped: ') + ', '.join(reasons or ['partial coverage']) \
                    + (')' if args.strict else '')
                if args.strict:
                    failed = True
                else:
                    incomplete = True
            elif name == 'world_mesh_audit' and code == 0 and not mesh:
                status = 'FAIL (no audit summary)'
                failed = True
            elif name == 'generated_digests' and re.search(r'^FAIL\b', result.output, re.M):
                status = 'FAIL (digest receipt verification)'
                failed = True
            elif (args.strict or ci) and (gaps or code == SKIPPED):
                status = 'FAIL (skipped/unavailable coverage)'
                failed = True
            elif name == 'cfgconvert_check' and code == SKIPPED:
                status = 'needs-host-check: unavailable'
                incomplete = True
            elif not ci and (code == SKIPPED or (code == 0 and gaps)):
                # Host-only inputs (native cache, Windows tools) are missing: never a pass.
                status = 'needs-host-check: ' + ('; '.join(gaps[:1]) or 'inputs unavailable')[:120]
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
    animation = anim_lint_step(args, paths)
    if animation is not None:
        rows.append(animation[0])
        failed |= animation[1]
        incomplete |= animation[2]
    site_row = site_rules_step(args, paths)
    if site_row[0] is not None:
        rows.append(site_row[0])
    failed |= site_row[1]
    if paths is not None:
        changed_tests = changed_unit_tests(paths)
        rows.append(changed_tests[:2] + ('changed files',))
        failed |= changed_tests[2]
    print('\nCheck | Result | Scope')
    print('--- | --- | ---')
    for row in rows:
        print(' | '.join(row))
    print('preland: ' + ('FAILED' if failed else 'INCOMPLETE (native/optional checks pending)' if incomplete else 'PASS')
          + '; engine compile/boot acceptance remains separate')
    if incomplete and not failed:
        print('preland: status=needs-host-check; host-only inputs are missing here, so this is not a pass.'
              ' Commit, then run on the lead host queue:')
        print(submit_line(ROOT))
    return 1 if failed else SKIPPED if incomplete else 0


if __name__ == '__main__':
    raise SystemExit(main())
