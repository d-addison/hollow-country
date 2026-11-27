"""Fail-closed release evidence on one exact commit; native execution is lead-only."""
import argparse
import contextlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import tempfile
import zipfile

from tools.audit import rpt_config_audit
from tools.release import activity_check, checkstart, client_compile_check, friendcycle, rpt_summary
from tools.release.acceptance_targets import load_targets, parse_targets, TargetsError
from tools.release.host_lock import host_lock, LockRefused
from tools.setup import winproc
from tools.validate.tick_cost_report import perf_rules

CATEGORIES = ('map', 'inventory', 'groups', 'admin', 'ai', 'event')
ROOT = Path(__file__).resolve().parents[2]
CHECKLIST = ('One tester: join; open the M map with group controls, inventory and admin window; '
             'walk from outside into one reviewed AI site activation radius and one published mission zone. '
             'Keep this client connected through activity validation.')
# Default client mode (owner, 2026-11-24): the dev-only test addon drives one real client through the R3
# route, so no person has to play. --client-mode human keeps the one-tester checklist above.
CLIENT_MODES = ('scripted', 'human')
SCRIPTED_CHECKLIST = ('Scripted client: the dev-only test addon drives one real client through the R3 route '
                      '(M map with group controls, inventory, admin window, then on foot from outside into one AI '
                      'site activation radius and one published mission zone). Nobody has to play; the scripted '
                      'client stays connected through activity validation.')
SERVER_IMAGE = 'DayZServer_x64.exe'
STOP_WAIT_SECONDS = 240
STOP_POLL_SECONDS = 5
# Everything the scripted client needs lives in one new folder next to the server root; restore removes
# only a folder that carries the marker.
SCRIPTED_FOLDER = 'release-gate-client'
SCRIPTED_MARKER = '.hc-release-gate-client'
SCRIPTED_READY_SECONDS = 20 * 60
SCRIPTED_JOIN_SECONDS = 600


class Refused(ValueError):
    pass


GATE_ERRORS = (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError,
               winproc.InteropError, KeyboardInterrupt)


def failure_reason(error):
    if isinstance(error, (Refused, LockRefused, TargetsError)):
        return str(error)
    return 'required evidence unavailable or failed'


def candidate_policy(commit, root=ROOT):
    """Read policy from the same immutable Git commit required by the bundle."""
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise Refused('full commit required')

    def git(*arguments, refusal):
        try:
            result = subprocess.run(['git', '--no-replace-objects', *arguments], cwd=root,
                                    capture_output=True, check=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            raise Refused(refusal) from None
        return result.stdout

    if git('cat-file', '-t', commit, refusal='candidate commit unavailable').strip() != b'commit':
        raise Refused('candidate object is not a commit')
    targets = parse_targets(git('cat-file', 'blob', f'{commit}:config/acceptance-targets.json',
                                refusal='candidate acceptance targets unavailable'))
    expectations = git('cat-file', 'blob', f'{commit}:config/activity-expectations.json',
                       refusal='candidate activity expectations unavailable')
    try:
        entries = activity_check.parse_expectations(expectations)
    except (ValueError, TypeError, OverflowError, RecursionError, re.error):
        raise Refused('candidate activity expectations invalid') from None
    return targets, entries


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


def capture(function, argv, **kwargs):
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = function(argv, **kwargs)
    except SystemExit:
        raise Refused('tool arguments unsupported') from None
    finally:
        emit(output.getvalue())
    if code:
        raise Refused('tool failed')


# Persisted-store/record announcements only. Source inventory (2026-11-25):
# HCGroupIO.c:173, HCEcologyRuntimeStore.c:272, HCEcologyMigrationStore.c:61/71,
# HCEventModule.c:832, HCInteriorStore.c:62, HCInfectedModule.c:1132,
# HCXEmoteObservation.c:247; HCStagedStore.c:HCEvidence emits action=quarantine.
STORE_QUARANTINE_MARKERS = {
    'hc28-store-recovery': r'\[HC Plan\] HC-28 store=\S+ recovery=quarantined\b',
    'ecology-recovery': r'\[HC Ecology\] recovery=quarantined\b',
    'ecology-migration': r'\[HC Ecology\] migration quarantine in place\b',
    'event-cleanup': r'\[HC Events\] cleanup quarantined\b',
    'interior-slot': r'\[HC Interiors\] slot [0-9]+ quarantined:',
    'infected-cohort': r'\[HollowCountry\] infected cohort quarantined\b',
    'betrayal-store': r'\[HC Plan\] HC-5 signals=\S+ betrayal_store=quarantined\b',
    # HCSiteGuard.c:432 emits a persisted-state recovery summary through Log.
    'sites-state': r'\[HC Sites\] state recovered=\S+ quarantined=(?:1|true)\b',
    'staged-store': r'\[HC Store\].*\baction=quarantine\b',
}
TEXTURE = re.compile(r"Cannot load texture '([^'\r\n]+)'", re.I)


def texture_prefixes(root=ROOT, workshop=None):
    """Derive virtual roots from authored prefixes/config and declared dependency PBO headers."""
    from tools.setup import workshop_sync
    from tools.audit.pbo_config import read_pbo_index
    own, dependency = set(), set()
    for config in (Path(root) / 'mods').glob('*/config.cpp'):
        prefix = config.with_name('$PBOPREFIX$')
        if prefix.is_file():
            own.add(prefix.read_text().strip().lower().replace('/', '\\').strip('\\'))
        else:
            # The base addon uses its CfgMods dir as its virtual root.
            own.update(x.lower() for x in re.findall(r'\bdir\s*=\s*"([^"\r\n]+)"', config.read_text()))
    workshop = Path(workshop) if workshop else Path('/mnt/g/SteamLibrary/steamapps/workshop/content/221100')
    manifest = workshop_sync.load_manifest(Path(root) / 'tools/setup/workshop_mods.json')
    for item in manifest['mods']:
        if item['publish'] or not item['id']:
            continue
        for pbo in (workshop / item['id']).glob('**/*.pbo'):
            prefix = read_pbo_index(pbo)['prefix'].lower().replace('/', '\\').strip('\\')
            if prefix:
                dependency.add(prefix)
    return own, dependency


def texture_counts(path, prefixes=None):
    own, dependency = texture_prefixes() if prefixes is None else prefixes
    result = dict(missing_textures=0, vanilla_texture_noise=0, other_texture_noise=0)
    roots = tuple(x.lower().replace('/', '\\').strip('\\') + '\\' for x in own | dependency)
    for raw in rpt_summary.lines(path):
        match = TEXTURE.search(raw)
        if not match:
            continue
        resource = match[1].lower().replace('/', '\\').lstrip('\\')
        if resource.startswith(('dz\\', 'a3\\', 'd:\\p4\\')) or '\\' not in resource:
            result['vanilla_texture_noise'] += 1
        elif resource.startswith(roots):
            result['missing_textures'] += 1
        else:
            result['other_texture_noise'] += 1
    return result


def post_stop_check(path, *, soak_minutes=None):
    for category, raw in rpt_config_audit.diagnostic_lines(path, rpt_config_audit.category_rules()):
        if category is None:
            raise Refused('post-stop RPT oversized line; crash evidence incomplete')
        if rpt_summary.failure(raw, True) == 'crashed':
            raise Refused('post-stop crash observed')
    if soak_minutes is not None:
        span = rpt_summary.soak_span(path)
        emit('soak_duration_seconds=' + ('unavailable' if span is None else f'{span:.3f}'))
        if span is None or span < soak_minutes * 60:
            measured = 'unavailable' if span is None else f'{span:.3f}'
            raise Refused(f'soak duration insufficient measured_seconds={measured} required_minutes={soak_minutes:g}')


def campaign_evidence(directory, commit):
    """Only explicit full, release-class, commit-bound receipts may contribute counters."""
    directory = Path(directory)
    try:
        selection_file = directory / 'selection.json'
        selection = json.loads(selection_file.read_text()) if selection_file.is_file() else {}
        manifests = [directory / name for name in ('manifest.json', 'BUILD_MANIFEST.json')
                     if (directory / name).is_file()]
        metadata = [selection] + [json.loads(p.read_text()) for p in manifests]
        if not all(isinstance(m, dict) for m in metadata):
            raise Refused('activity evidence receipt invalid')
        if selection.get('targeted') is True:
            raise Refused('activity evidence targeted run is not release-class')
        commits = [m['commit'] for m in metadata if 'commit' in m]
        if not commits or any(value != commit for value in commits):
            raise Refused('activity evidence candidate commit mismatch or unavailable')
        # The campaign removes selection.json for a full run (record_selection).
        # A retained report plus the exact manifest binds that established format.
        report = directory / 'report.md'
        full_report = (not selection_file.exists() and report.is_file()
                       and report.read_text().startswith('# Soak campaign report\n')
                       and 'Targeted run:' not in report.read_text())
        explicit_full = selection.get('targeted') is False
        if (any(m.get('release_class') is False for m in metadata)
                or not (full_report or explicit_full)):
            raise Refused('activity evidence full release-class receipt required')
        server = list((directory / 'server').glob('*.RPT'))
        client = list((directory / 'client').glob('*.RPT'))
        if len(server) != 1 or len(client) > 1:
            raise Refused('activity evidence RPT selection ambiguous or missing')
        for category, raw in rpt_config_audit.diagnostic_lines(server[0], rpt_config_audit.category_rules()):
            if category is None:
                raise Refused('activity evidence oversized line; crash/script/VME evidence incomplete')
            if (rpt_summary.failure(raw, True) in ('crashed', 'compile_failed', 'script_error')
                    or re.search(r'\bVME\b|Virtual Machine Exception', raw, re.I)):
                raise Refused('activity evidence server crash/script/VME observed')
        return server[0], client[0] if client else None
    except (OSError, ValueError, TypeError) as error:
        if isinstance(error, Refused):
            raise
        raise Refused('activity evidence receipt unavailable or invalid') from None


def previous_release(tag, cache=None):
    """Download an immutable release bundle, safely extract, verify its entire installer manifest."""
    from tools.setup import friend_install
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}', tag) or '..' in tag:
        raise Refused('previous release tag invalid')
    cache = (Path(cache) if cache else Path.home() / '.cache/hollow-country/releases') / tag
    cache.mkdir(parents=True, exist_ok=True)
    extracted = cache / 'verified'

    def verify(folder):
        manifests = list(folder.rglob('bundle-manifest.json'))
        if len(manifests) != 1:
            raise Refused('previous release installer manifest missing or ambiguous')
        bundle = manifests[0].parent
        try:
            manifest = friend_install.load_bundle(bundle)
            if not manifest.get('files'):
                raise Refused('previous release manifest empty')
        except friend_install.Refused:
            raise Refused('previous release manifest verification failed') from None
        return bundle

    if extracted.exists():
        return verify(extracted)
    try:
        result = subprocess.run(['gh', 'release', 'view', tag, '--json', 'assets'], cwd=ROOT,
                                capture_output=True, text=True, check=True, timeout=60)
        assets = json.loads(result.stdout)['assets']
        names = [a['name'] for a in assets if 'bundle' in a['name'].lower() and a['name'].endswith('.zip')]
        if len(names) != 1 or Path(names[0]).name != names[0]:
            raise Refused('previous release bundle asset missing or ambiguous')
        with tempfile.TemporaryDirectory(dir=cache, prefix='download-') as tmp:
            tmp = Path(tmp)
            subprocess.run(['gh', 'release', 'download', tag, '--pattern', names[0], '--dir', str(tmp)],
                           cwd=ROOT, capture_output=True, check=True, timeout=600)
            unpack = tmp / 'unpack'
            unpack.mkdir()
            with zipfile.ZipFile(tmp / names[0]) as archive:
                members = archive.infolist()
                if len(members) > 100000 or sum(m.file_size for m in members) > 8 * 1024**3:
                    raise Refused('previous release archive exceeds budget')
                for member in members:
                    name = member.filename
                    if (name.startswith('/') or '\\' in name or ':' in name or '..' in name.split('/')
                            or (member.external_attr >> 16) & 0o170000 == 0o120000):
                        raise Refused('previous release archive unsafe')
                archive.extractall(unpack)
            verify(unpack)
            unpack.rename(extracted)
        return verify(extracted)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        if isinstance(error, Refused):
            raise
        raise Refused('previous release download or verification failed') from None


def audit(path, *, client=False, startup_only=False, targets=None, entries=None, texture_roots=None):
    """Reuse the common summary and perf parser; add only release-specific rules."""
    targets = load_targets() if targets is None else targets
    warnings = rpt_summary.r2b_warnings(path, targets['perf_r2_max_ms']) if not client else []
    for warning in warnings:
        emit(warning)
    summary = rpt_summary.Summary(path, targets=targets, entries=entries)
    try:
        summary.scan()
        # Count SCRIPT (E) below; compile markers and other failures stay unconditional.
        if summary.failures - {'compile_failed'} or (not client and
                (not summary.connected or not summary.ready_last or not all(summary.ready_last.values()))):
            raise Refused('RPT boot/error/readiness check failed')
    finally:
        summary.close()
    script_errors = vmes = 0
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
        for marker, pattern in STORE_QUARANTINE_MARKERS.items():
            if re.search(pattern, line):
                raise Refused('store quarantine observed marker=' + marker)
    if client:
        textures = texture_counts(path, texture_roots)
        emit('client_textures ' + ' '.join(f'{key}={value}' for key, value in textures.items()))
        if textures['missing_textures'] > targets['client_max_missing_textures']:
            raise Refused('client texture error limit exceeded')
    if client or startup_only:
        return

    # Use the audit's exact taxonomy and bounded reader, including lines that
    # do not contain generic warning/error words. Never serialize raw text.
    counts, oversized = rpt_config_audit.scan_rpt_totals(path, rpt_config_audit.category_rules())
    totals = {category: counts[category] for category in rpt_config_audit.RULES}
    unclassified = counts[0]
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
    for rule in perf_rules(path):
        if 'perf_rule=R2 ' in rule:
            value = re.search(r'\bms=([0-9.]+)', rule)
            if value is None or float(value[1]) > targets['perf_r2_max_ms']:
                raise Refused(f"perf R2 over {targets['perf_r2_max_ms']:g} ms")
    evidence = dict(warnings=warnings, engine_noise_count=counts[rpt_config_audit.ENGINE_NOISE],
                    hc_diagnostic_count=counts[rpt_config_audit.HC_TELEMETRY],
                    rpt_categories={str(key): dict(count=value,
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


def client_mode(args):
    return getattr(args, 'client_mode', 'human')


class ScriptedClient:
    """The no-human R3 client: one real DayZ client, the dev-only test addon and the R3 step file.

    Reuses tools.testing.soak_campaign (client_mods, the dependency parity check, client_arguments,
    WindowsHost.launch_client and its graceful stop) and tools.testing.test_addon (pack and sign). The
    addon loads on the client only; the server runs the installed candidate unchanged. The addon, the
    step file and the client profile live in one marked folder next to the server root, which restore
    removes once both client images are confirmed gone.
    """

    def __init__(self, server_root, client_root, *, host=None, campaign=None, addon=None, driver=None,
                 win=None, clock=time.monotonic, poll=5):
        from tools.testing import driver_script, soak_campaign, test_addon
        self.campaign = campaign or soak_campaign
        self.addon = addon or test_addon
        self.driver = driver or driver_script
        self.host = host or self.campaign.WindowsHost()
        self.win = win or self.campaign.default_win
        self.server = Path(server_root)
        self.client_root = Path(client_root)
        self.folder = self.server.parent / SCRIPTED_FOLDER
        self.profile = self.folder / 'profile'
        self.clock = clock
        self.poll = poll
        self.halt = threading.Event()
        self.thread = None
        self.arguments = None
        self.launched = False
        self.error = None
        self.run_id = None

    def ours(self):
        return (self.folder / SCRIPTED_MARKER).is_file()

    def stage(self):
        if self.folder.exists():
            if not self.ours():
                raise Refused('scripted client folder exists and is not ours; move it away first')
            self.require_gone()
            self.restore()
        script, _ = self.driver.build_r3()
        self.run_id = script['run_id']
        mods = self.campaign.server_mods((self.server / 'start-server.bat').read_bytes())
        paths = self.campaign.client_mods(mods, self.server, self.client_root / '!Workshop', Path)
        self.campaign.require_dependency_parity(mods, self.server, paths, log=emit)
        built = self.addon.build()
        self.folder.mkdir()
        (self.folder / SCRIPTED_MARKER).write_text('release_gate scripted client\n', encoding='utf-8')
        addon = self.folder / self.campaign.TEST_MOD
        shutil.copytree(built['path'], addon)
        step = self.profile / self.campaign.STEP_REL
        step.parent.mkdir(parents=True)
        step.write_text(json.dumps(script, indent=1) + '\n', encoding='utf-8')
        self.arguments = self.campaign.client_arguments([self.win(path) for path in paths] + [self.win(addon)],
                                                        self.win(self.profile))
        emit('scripted client: staged run=%s steps=%d mods=%d' % (self.run_id, len(script['steps']), len(paths) + 1))

    def start(self, profiles, before):
        """Launch the client from a watcher once the fresh server RPT says connect enabled."""
        self.thread = threading.Thread(target=self.watch, args=(Path(profiles), set(before)),
                                       name='hc-scripted-client', daemon=True)
        self.thread.start()

    def watch(self, profiles, before):
        deadline = self.clock() + SCRIPTED_READY_SECONDS
        follow = {'path': None, 'offset': 0}
        try:
            while not self.halt.is_set():
                fresh = sorted(set(profiles.glob('*.RPT')) - before)
                if fresh:
                    if follow['path'] != fresh[-1]:
                        follow.update(path=fresh[-1], offset=0)
                    lines, follow['offset'] = self.campaign.tail_lines(follow['path'], follow['offset'])
                    if any(self.campaign.CONNECT_ENABLED in line for line in lines):
                        # Record ownership first: a lost interop reply may hide a launch that happened.
                        self.launched = True
                        self.host.launch_client(self.win(self.client_root), self.arguments)
                        emit('scripted client: launched after server connect enabled')
                        return
                if self.clock() >= deadline:
                    self.error = 'server connect enabled not seen'
                    return
                self.halt.wait(self.poll)
        except Exception as error:  # the thread reports through self.error; never echo raw text
            self.error = str(error) if isinstance(error, (Refused, self.campaign.Refused)) else failure_reason(error)

    def require_launched(self):
        if self.thread is not None:
            self.thread.join(timeout=SCRIPTED_JOIN_SECONDS)
        if self.error:
            raise Refused('scripted client launch failed: ' + self.error)
        if not self.launched:
            raise Refused('scripted client was never launched')

    def states(self):
        return {image: self.host.state(image)
                for image in (self.campaign.LAUNCHER_IMAGE, self.campaign.CLIENT_IMAGE)}

    def require_gone(self):
        deadline = self.clock() + STOP_WAIT_SECONDS
        while True:
            states = self.states()
            if all(state == 'gone' for state in states.values()):
                return
            if self.clock() >= deadline:
                raise Refused('scripted client stop could not be verified (%s); stop DayZ by hand' %
                              ','.join('%s=%s' % row for row in sorted(states.items())))
            time.sleep(STOP_POLL_SECONDS)

    def stop(self):
        """Graceful client close (the soak campaign's CloseMainWindow path), then restore."""
        self.halt.set()
        if self.thread is not None:
            self.thread.join(timeout=SCRIPTED_JOIN_SECONDS)
            if self.thread.is_alive():
                raise Refused('scripted client launch still in progress; stop DayZ by hand')
        if self.launched or self.states()[self.campaign.CLIENT_IMAGE] != 'gone':
            self.host.stop(self.campaign.CLIENT_IMAGE)
        self.require_gone()
        self.restore()

    def restore(self):
        if self.folder.exists() and self.ours():
            shutil.rmtree(self.folder)


class NativeSteps:
    def __init__(self, args, targets=None, entries=None):
        self.args = args
        self.targets = load_targets() if targets is None else targets
        self.entries = entries
        self.rpt = None
        self.client_rpt = None
        self.started = False
        self.client_dir = None
        self.client_before = set()
        self.scripted = None
        self.boot_rpt = None
        self.boot_soak = None
        self.warnings = []
        self.texture_roots = None

    def scripted_client(self):
        from tools.testing import soak_campaign
        root = getattr(self.args, 'client_root', None) or soak_campaign.discover_client_root()
        if root is None:
            raise Refused('scripted client: no DayZ client install found; pass --client-root')
        return ScriptedClient(Path(soak_campaign.default_linux(self.args.server_root)), Path(root))

    def checklist(self):
        return SCRIPTED_CHECKLIST if client_mode(self.args) == 'scripted' else CHECKLIST

    def compile(self):
        from tools.release.dayz_update import build_check
        status, reason = build_check()
        if status != 'pass':
            raise Refused('dayz_build: ' + status + ': ' + reason)
        output = command([sys.executable, '-B', '-m', 'tools.release.compile_gate',
                          '--tree', ROOT, '--commit', self.args.commit], 1200)
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
        if winproc.process_state(SERVER_IMAGE) != 'gone':
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
            codes = re.findall(r'(?:refused:|Refused)\s*([A-Za-z0-9_-]{1,64})', result.stdout + '\n' + result.stderr)
            raise Refused('install failed' + (' code=' + codes[-1] if codes else ''))

    def boot(self, bundle, minutes, *, startup_only=False):
        before = set(self.args.profiles.glob('*.RPT'))
        if winproc.process_state(SERVER_IMAGE) != 'gone':
            raise Refused('boot requires stopped server')
        # Record ownership before launch: an interop failure may hide a successful start.
        self.started = True
        capture(checkstart.main, ['--bundle', friendcycle.windows_path(bundle), '--start',
                '--server-root', self.args.server_root, '--profiles', str(self.args.profiles),
                '--settle-minutes', str(minutes), '--timeout-seconds', str(minutes * 60 + 900)],
                targets=self.targets, entries=self.entries)
        fresh = set(self.args.profiles.glob('*.RPT')) - before
        if len(fresh) != 1:
            raise Refused('fresh server RPT ambiguous or missing')
        path = fresh.pop()
        self.boot_rpt = path
        self.boot_soak = None if startup_only else minutes
        self.warnings.extend(rpt_summary.r2b_warnings(path, self.targets['perf_r2_max_ms']))
        audit(path, startup_only=startup_only, targets=self.targets, entries=self.entries)
        return path

    def stop(self):
        # Client first (it would only log a lost connection), then the server; restore follows the client.
        failure = None
        if self.scripted is not None:
            try:
                self.scripted.stop()
                self.scripted = None
            except GATE_ERRORS as error:
                failure = error
        self.stop_server()
        if self.boot_rpt is not None:
            post_stop_check(self.boot_rpt, soak_minutes=self.boot_soak)
            self.boot_rpt = None
        if failure is not None:
            raise failure

    def stop_server(self):
        if not self.started:
            return
        # Existing native smoke graceful path (CloseMainWindow), without escalation.
        script = ("$p=@(Get-Process -Name DayZServer_x64 -ErrorAction SilentlyContinue); "
                  "if ($p.Count -eq 0) { Write-Output 'HC stopped'; exit 0 }; "
                  "if ($p.Count -ne 1) { Write-Output 'HC stop ambiguous'; exit 2 }; "
                  "if (-not $p[0].CloseMainWindow()) { Write-Output 'HC close refused'; exit 2 }; "
                  f"if (-not $p[0].WaitForExit({STOP_WAIT_SECONDS * 1000})) {{ Write-Output 'HC close timeout'; exit 2 }}; "
                  "Write-Output 'HC stopped'")
        deadline = time.monotonic() + STOP_WAIT_SECONDS
        try:
            result = winproc.run('powershell', [script], attempts=1, timeout=STOP_WAIT_SECONDS + 60)
        except winproc.InteropError:
            # The close request may already be saving the world in Windows.
            result = None
        if result is None or result.returncode == 0:
            while True:
                if winproc.process_state(SERVER_IMAGE, attempts=3, timeout=5) == 'gone':
                    self.started = False
                    return
                remaining = deadline - time.monotonic()
                if result is not None or remaining <= 0:
                    break
                time.sleep(min(STOP_POLL_SECONDS, remaining))
        raise Refused('graceful server stop could not be verified; operator intervention required')

    def upgrade(self):
        if getattr(self.args, 'previous_release', None):
            self.args.previous_bundle = previous_release(self.args.previous_release)
        if not self.args.previous_bundle:
            if self.targets['upgrade_from_previous_release_required']:
                raise Refused('previous release bundle required for the upgrade check (--previous-bundle)')
            return
        # checkstart still enforces startup readiness for both versions. The
        # candidate census, ratchet and performance checks use the soak RPT.
        try:
            self.install(self.args.previous_bundle)
        except Refused as error:
            raise Refused('upgrade previous-install-refused reason=' + str(error)) from None
        self.boot(self.args.previous_bundle, 1, startup_only=True)
        self.stop()
        self.install(self.args.bundle)
        self.boot(self.args.bundle, 1, startup_only=True)
        self.stop()

    def soak(self):
        if client_mode(self.args) == 'scripted':
            self.scripted = self.scripted_client()
            self.scripted.stage()  # before install: a refused build or dependency mismatch fails early
            self.client_dir = self.scripted.profile
        else:
            self.client_dir = self.args.client_profiles or client_profiles()
        self.client_before = set(self.client_dir.glob('*.RPT'))
        self.install(self.args.bundle)
        emit(self.checklist())
        if self.scripted is not None:
            self.scripted.start(self.args.profiles, set(self.args.profiles.glob('*.RPT')))
        self.rpt = self.boot(self.args.bundle, self.targets['soak_minutes'])
        if self.scripted is not None:
            self.scripted.require_launched()
        fresh = set(self.client_dir.glob('*.RPT')) - self.client_before
        if len(fresh) == 1:
            self.client_rpt = fresh.pop()

    def activity(self):
        if self.client_rpt is None:
            raise Refused('fresh client RPT required during soak')
        evidence_dir = getattr(self.args, 'activity_evidence', None)
        evidence = campaign_evidence(evidence_dir, self.args.commit) if evidence_dir else None
        result = activity_check.scan_release(self.rpt, client_rpt=self.client_rpt,
                    targets=self.targets, entries=self.entries, evidence=evidence)
        activity_check.print_result(result)
        if result['count']:
            raise Refused(activity_check.summary_line(result))

    def audit_client(self):
        if self.texture_roots is None:
            from tools.testing.soak_campaign import default_linux
            workshop = getattr(self.args, 'workshop_content', None)
            self.texture_roots = texture_prefixes(workshop=default_linux(workshop) if workshop else None)
        return audit(self.client_rpt, client=True, targets=self.targets, entries=self.entries,
                     texture_roots=self.texture_roots)

    def client_script_errors(self, result):
        # The compile check no longer fails on runtime SCRIPT (E); the release bar
        # still counts them across the client RPT and every script_*.log.
        if result.get('runtime_errors', 0) > self.targets['max_script_errors']:
            raise Refused('client script error limit exceeded')

    def client(self):
        emit(self.checklist())
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
            result = client_compile_check.scan(self.client_rpt)
            emit(client_compile_check.verdict_line(result))
            if not result['passed']:
                raise Refused('client compile check failed: ' + result['reason'])
            self.client_script_errors(result)
            self.audit_client()
            # Delegate shared [HC Use] parsing to the activity checker. Release
            # mode owns the signal format and reports per-feature active counts.
            result = activity_check.scan(self.rpt, client_rpt=self.client_rpt, entries=self.entries)
            active = {(row['module'], row['feature']) for row in result['features']
                      if row.get('scope') == 'client' and row.get('status') == 'ACTIVE'
                      and row.get('value', 0) is not None and row['value'] > 0}
            if required <= active:
                audit(self.rpt, targets=self.targets, entries=self.entries)
                self.audit_client()
                result = client_compile_check.scan(self.client_rpt)
                emit(client_compile_check.verdict_line(result))
                if not result['passed']:
                    raise Refused('client compile check failed: ' + result['reason'])
                self.client_script_errors(result)
                return
            if time.monotonic() >= deadline:
                raise Refused('client smoke timeout')
            time.sleep(min(5, max(0, deadline - time.monotonic())))


def run_gate(args, steps=None):
    mode = client_mode(args)
    verdict = dict(commit=args.commit, passed=False, steps=[], client_mode=mode,
                   client='scripted client' if mode == 'scripted' else 'one tester')
    current = 'acceptance_targets'
    try:
        targets, entries = candidate_policy(args.commit)
        steps = steps or NativeSteps(args, targets, entries)
        current = 'host_lock'
        with host_lock('release_gate'):
            completed = False
            try:
                for current in ('compile', 'manifest', 'upgrade', 'soak', 'activity', 'client'):
                    getattr(steps, current)()
                    verdict['steps'].append(dict(step=current, passed=True))
                completed = True
            finally:
                if completed:
                    current = 'cleanup'
                try:
                    steps.stop()
                except GATE_ERRORS as error:
                    if completed:
                        raise
                    verdict['cleanup_reason'] = failure_reason(error)
        verdict['passed'] = True
    except GATE_ERRORS as error:
        verdict['failed_step'] = current
        verdict['reason'] = failure_reason(error)
    warnings = getattr(steps, 'warnings', None)
    if isinstance(warnings, list):
        verdict['warnings'] = sorted(set(warnings))
    return verdict


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, 'release gate arguments invalid\n')


def main(argv=None):
    parser = Parser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    previous = parser.add_mutually_exclusive_group()
    previous.add_argument('--previous-bundle', type=Path)
    previous.add_argument('--previous-release')
    parser.add_argument('--activity-evidence', type=Path)
    parser.add_argument('--profiles', type=Path, default=Path('/mnt/e/HollowCountryLocal/friend-local-1/profiles'))
    parser.add_argument('--server-root', default=r'E:\HollowCountryLocal\friend-local-1')
    parser.add_argument('--workshop-content', default=r'G:\SteamLibrary\steamapps\workshop\content\221100')
    parser.add_argument('--client-mode', choices=CLIENT_MODES, default='scripted')
    parser.add_argument('--client-root', type=Path)
    parser.add_argument('--client-profiles', type=Path)
    parser.add_argument('--client-timeout', type=float, default=900)
    parser.add_argument('--smoke-use', action='append', default=[], metavar='CATEGORY=MODULE/FEATURE')
    parser.add_argument('--verdict', type=Path, default=Path('release-gate-verdict.json'))
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[0-9a-f]{40}', args.commit):
        parser.error('full commit required')
    if not math.isfinite(args.client_timeout) or not 0 < args.client_timeout <= 3600:
        parser.error('timeout out of bounds')
    if args.client_mode == 'scripted' and args.client_profiles:
        parser.error('--client-profiles belongs to --client-mode human')
    if args.client_mode == 'human' and args.client_root:
        parser.error('--client-root belongs to --client-mode scripted')
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
