"""Fail-closed release evidence on one exact commit; native execution is lead-only."""
import argparse
import contextlib
import io
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time

from tools.audit import rpt_config_audit
from tools.release import activity_check, checkstart, friendcycle, rpt_summary
from tools.release.acceptance_targets import load_targets, TargetsError
from tools.release.host_lock import host_lock, LockRefused
from tools.setup import winproc
from tools.validate.tick_cost_report import perf_rules

CATEGORIES = ('map', 'inventory', 'groups', 'admin', 'ai', 'event')
CHECKLIST = ('One tester: join; open the M map with group controls, inventory and admin window; '
             'walk from outside into one reviewed AI site activation radius and one published mission zone. '
             'Keep this client connected through activity validation.')


class Refused(ValueError):
    pass


def emit(text):
    for line in text.splitlines():
        safe = rpt_summary.filtered(line)
        if safe:
            print(safe, flush=True)


def command(argv, timeout):
    result = subprocess.run([str(x) for x in argv], capture_output=True, text=True, timeout=timeout)
    emit(result.stdout)
    emit(result.stderr)
    if result.returncode:
        raise Refused('tool failed')
    return result.stdout


def capture(function, argv):
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = function(argv)
    except SystemExit:
        raise Refused('tool arguments unsupported') from None
    finally:
        emit(output.getvalue())
    if code:
        raise Refused('tool failed')


def audit(path, *, client=False, targets=None):
    """Reuse the common summary and perf parser; add only release-specific rules."""
    targets = load_targets() if targets is None else targets
    summary = rpt_summary.Summary(path)
    try:
        summary.scan()
        # Count SCRIPT (E) below; compile markers and other failures stay unconditional.
        if summary.failures - {'compile_failed'} or (not client and
                (not summary.connected or not summary.ready_last or not all(summary.ready_last.values()))):
            raise Refused('RPT boot/error/readiness check failed')
    finally:
        summary.close()
    script_errors = vmes = missing_textures = 0
    for line in rpt_summary.lines(path):
        if rpt_summary.COMPILE_MARKER.search(line):
            raise Refused('RPT compile failure')
        script_errors += bool(rpt_summary.SCRIPT_ERROR.search(line))
        if script_errors > targets['max_script_errors']:
            raise Refused('RPT script error limit exceeded')
        if re.search(r'\bVME\b|Virtual Machine Exception', line, re.I):
            vmes += 1
            if vmes > targets['client_max_vme' if client else 'max_vme_server']:
                raise Refused('RPT VME limit exceeded')
        if '[HC SelfTest]' in line and re.search(r'\bpass=false\b', line):
            raise Refused('self-test failed')
        if re.search(r'quarantin', line, re.I):
            raise Refused('store quarantine observed')
        if client and re.search(r"can.t load|missing texture|cannot load.*texture", line, re.I):
            missing_textures += 1
            if missing_textures > targets['client_max_missing_textures']:
                raise Refused('client texture error limit exceeded')
    if not client:
        # Use the audit's exact taxonomy and bounded reader, including lines that
        # do not contain generic warning/error words. Never serialize raw text.
        counts, oversized = rpt_config_audit.scan_rpt(path, rpt_config_audit.category_rules())
        totals = {category: 0 for category in rpt_config_audit.RULES}
        unclassified = 0
        for (category, _diagnostic), count in counts.items():
            if category == 0:
                unclassified += count
            else:
                totals[category] += count
        if oversized or unclassified:
            raise Refused(f'R3 incomplete RPT census unclassified={unclassified} oversized={oversized}')
        for category, count in totals.items():
            ceiling = targets['rpt_category_ceilings'][str(category)]
            if ceiling is None:
                raise Refused(f'R3 category={category} ceiling unavailable; measured count required')
            if count > ceiling:
                raise Refused(f'R3 category={category} count={count} ceiling={ceiling}')
        limit = min(targets['readiness_max_after_hive_seconds'],
                    targets['readiness_ratchet_max_after_hive_seconds'])
        timing = summary.readiness_timing.result(limit)
        if timing['status'] != 'passed' or timing['max_after_hive_seconds'] is None:
            raise Refused('R4 readiness timing unavailable or exceeds ratchet')
    if not client:
        for rule in perf_rules(path):
            if 'perf_rule=R2 ' in rule:
                value = re.search(r'\bms=([0-9.]+)', rule)
                if value is None or float(value[1]) > targets['perf_r2_max_ms']:
                    raise Refused(f"perf R2 over {targets['perf_r2_max_ms']:g} ms")
        evidence = dict(rpt_categories={str(key): dict(count=value,
                        ceiling=targets['rpt_category_ceilings'][str(key)])
                        for key, value in totals.items()}, readiness_timing=dict(
                            status=timing['status'],
                            max_after_hive_seconds=timing['max_after_hive_seconds'],
                            limit_seconds=timing['limit_seconds']))
        emit('R3/R4 ' + json.dumps(evidence, sort_keys=True))
        return evidence


def client_profiles():
    # Default retail profile location; resolve Windows environment read-only,
    # never echo the result. Explicit --client-profiles supports custom launchers.
    result = winproc.run('powershell', ["[Console]::Write((Join-Path $env:LOCALAPPDATA 'DayZ'))"])
    if result.returncode:
        raise Refused('client profiles unavailable')
    value = result.stdout.strip()
    match = re.fullmatch(r'([A-Za-z]):[\\/](.+)', value)
    if not match:
        raise Refused('client profiles unavailable')
    return Path('/mnt') / match[1].lower() / match[2].replace('\\', '/')


class NativeSteps:
    def __init__(self, args, targets=None):
        self.args = args
        self.targets = load_targets() if targets is None else targets
        self.rpt = None
        self.client_rpt = None
        self.started = False
        self.client_dir = None
        self.client_before = set()

    def compile(self):
        output = command([sys.executable, '-B', '-m', 'tools.release.compile_gate',
                          '--commit', self.args.commit], 1200)
        passed = re.search(r'^compile_gate: PASS status=(mission-loaded-runtime-json|initialized|timeout)$',
                           output, re.M)
        mission = re.search(r'^compile_gate: Mission loaded with zero compile errors; runtime acceptance pending$',
                            output, re.M)
        # The legacy status already certifies Mission; native initialized and
        # timeout statuses require the wrapper's explicit Mission observation.
        if not passed or (passed[1] != 'mission-loaded-runtime-json' and not mission):
            raise Refused('compile did not establish a clean Mission load')

    def manifest(self):
        manifest = json.loads((self.args.bundle / 'BUILD_MANIFEST.json').read_text())
        if manifest.get('commit') != self.args.commit:
            raise Refused('bundle manifest commit mismatch')
        digests = manifest.get('generated_digests')
        if not isinstance(digests, dict) or digests.get('strict') is not True or digests.get('waived_unavailable'):
            raise Refused('bundle was not built with strict generated-artefact digests (local test waivers)')

    def install(self, bundle):
        if winproc.process_state('DayZServer_x64.exe') != 'gone':
            raise Refused('installation requires stopped server')
        # Same installer flow as friendcycle, through bounded shared interop.
        windows = friendcycle.windows_path(bundle)
        script = ("$env:PYTHONDONTWRITEBYTECODE='1'; Set-Location -LiteralPath " + checkstart.psquote(windows)
                  + '; if (-not $?) { exit 2 }; & py -3 -B -m tools.setup.friend_install --bundle '
                  + checkstart.psquote(windows) + ' --server-root ' + checkstart.psquote(self.args.server_root)
                  + ' --apply --yes --workshop-content ' + checkstart.psquote(self.args.workshop_content)
                  + '; exit $LASTEXITCODE')
        result = winproc.run('powershell', [script], attempts=1, timeout=300)
        emit(result.stdout + '\n' + result.stderr)
        if result.returncode:
            raise Refused('install failed')

    def boot(self, bundle, minutes):
        before = set(self.args.profiles.glob('*.RPT'))
        if winproc.process_state('DayZServer_x64.exe') != 'gone':
            raise Refused('boot requires stopped server')
        # Record ownership before launch: an interop failure may hide a successful start.
        self.started = True
        capture(checkstart.main, ['--bundle', friendcycle.windows_path(bundle), '--start',
                '--server-root', self.args.server_root, '--profiles', str(self.args.profiles),
                '--settle-minutes', str(minutes), '--timeout-seconds', str(minutes * 60 + 900)])
        fresh = set(self.args.profiles.glob('*.RPT')) - before
        if len(fresh) != 1:
            raise Refused('fresh server RPT ambiguous or missing')
        path = fresh.pop()
        audit(path, targets=self.targets)
        return path

    def stop(self):
        if not self.started:
            return
        # Existing native smoke graceful path (CloseMainWindow), without escalation.
        script = ("$p=@(Get-Process -Name DayZServer_x64 -ErrorAction SilentlyContinue); "
                  "if ($p.Count -eq 0) { Write-Output 'HC stopped'; exit 0 }; "
                  "if ($p.Count -ne 1) { Write-Output 'HC stop ambiguous'; exit 2 }; "
                  "if (-not $p[0].CloseMainWindow()) { Write-Output 'HC close refused'; exit 2 }; "
                  "if (-not $p[0].WaitForExit(60000)) { Write-Output 'HC close timeout'; exit 2 }; "
                  "Write-Output 'HC stopped'")
        result = winproc.run('powershell', [script], attempts=1, timeout=75)
        if result.returncode or winproc.process_state('DayZServer_x64.exe') != 'gone':
            raise Refused('graceful server stop failed; operator intervention required')
        self.started = False

    def upgrade(self):
        if not self.args.previous_bundle:
            if self.targets['upgrade_from_previous_release_required']:
                raise Refused('previous release bundle required for the upgrade check (--previous-bundle)')
            return
        if self.args.previous_bundle:
            self.install(self.args.previous_bundle)
            self.boot(self.args.previous_bundle, 1)
            self.stop()
            self.install(self.args.bundle)
            self.boot(self.args.bundle, 1)
            self.stop()

    def soak(self):
        self.client_dir = self.args.client_profiles or client_profiles()
        self.client_before = set(self.client_dir.glob('*.RPT'))
        self.install(self.args.bundle)
        emit(CHECKLIST)
        self.rpt = self.boot(self.args.bundle, self.targets['soak_minutes'])
        fresh = set(self.client_dir.glob('*.RPT')) - self.client_before
        if len(fresh) == 1:
            self.client_rpt = fresh.pop()

    def activity(self):
        if self.client_rpt is None:
            raise Refused('fresh client RPT required during soak')
        capture(activity_check.main, [str(self.rpt), '--client-rpt', str(self.client_rpt), '--release'])

    def client(self):
        emit(CHECKLIST)
        required = set()
        categories = set()
        for item in self.args.smoke_use:
            match = re.fullmatch(r'(map|inventory|groups|admin|ai|event)=([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)', item)
            if not match or match[1] in categories:
                raise Refused('invalid smoke signal mapping')
            categories.add(match[1])
            required.add((match[2], match[3]))
        if categories != set(CATEGORIES) or len(required) != len(CATEGORIES):
            raise Refused('six distinct smoke signal mappings required; see RELEASE_GATE.md')
        deadline = time.monotonic() + self.args.client_timeout
        while True:
            audit(self.client_rpt, client=True, targets=self.targets)
            # Delegate shared [HC Use] parsing to the activity checker. Release
            # mode owns the signal format and reports per-feature active counts.
            result = activity_check.scan(self.rpt, client_rpt=self.client_rpt)
            active = {(row['module'], row['feature']) for row in result['features']
                      if row.get('scope') == 'client' and row.get('status') == 'ACTIVE'
                      and row.get('value', 0) is not None and row['value'] > 0}
            if required <= active:
                audit(self.rpt, targets=self.targets)
                audit(self.client_rpt, client=True, targets=self.targets)
                return
            if time.monotonic() >= deadline:
                raise Refused('client smoke timeout')
            time.sleep(min(5, max(0, deadline - time.monotonic())))


def run_gate(args, steps=None):
    verdict = dict(commit=args.commit, passed=False, steps=[])
    current = 'acceptance_targets'
    try:
        targets = load_targets()
        steps = steps or NativeSteps(args, targets)
        current = 'host_lock'
        with host_lock('release_gate'):
            try:
                for current in ('compile', 'manifest', 'upgrade', 'soak', 'activity', 'client'):
                    getattr(steps, current)()
                    verdict['steps'].append(dict(step=current, passed=True))
            finally:
                if sys.exc_info()[0] is None:
                    current = 'cleanup'
                steps.stop()
        verdict['passed'] = True
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError, winproc.InteropError, KeyboardInterrupt) as error:
        verdict['failed_step'] = current
        verdict['reason'] = str(error) if isinstance(error, (Refused, LockRefused, TargetsError)) else 'required evidence unavailable or failed'
    return verdict


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, 'release gate arguments invalid\n')


def main(argv=None):
    parser = Parser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--previous-bundle', type=Path)
    parser.add_argument('--profiles', type=Path, default=Path('/mnt/e/HollowCountryLocal/friend-local-1/profiles'))
    parser.add_argument('--server-root', default=r'E:\HollowCountryLocal\friend-local-1')
    parser.add_argument('--workshop-content', default=r'G:\SteamLibrary\steamapps\workshop\content\221100')
    parser.add_argument('--client-profiles', type=Path)
    parser.add_argument('--client-timeout', type=float, default=900)
    parser.add_argument('--smoke-use', action='append', default=[], metavar='CATEGORY=MODULE/FEATURE')
    parser.add_argument('--verdict', type=Path, default=Path('release-gate-verdict.json'))
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[0-9a-f]{40}', args.commit):
        parser.error('full commit required')
    if not math.isfinite(args.client_timeout) or not 0 < args.client_timeout <= 3600:
        parser.error('timeout out of bounds')
    verdict = run_gate(args)
    try:
        args.verdict.write_text(json.dumps(verdict, indent=2) + '\n')
    except OSError:
        verdict['passed'] = False
        verdict['reason'] = 'verdict write failed'
    print(json.dumps(verdict))
    print('release_gate=' + ('PASS' if verdict['passed'] else 'FAIL'))
    return 0 if verdict['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
