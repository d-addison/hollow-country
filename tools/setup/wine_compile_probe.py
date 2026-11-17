"""Bounded actual DayZ compiler probe under Wine; not native Windows acceptance.

Requires an already isolated complete server copy on a Linux filesystem, Wine64
and xvfb-run. Never stages purchased assets into source or modifies Steam files.
Every invocation creates fresh profiles/storage/mod staging and preserves logs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import time

from tools.package import pbo
from tools.setup import infected_death_probe as death_probe
from tools.validate.runtime import validate_settings

MAX_LOG_FILE = 16 * 1024 * 1024
MAX_LOG_TOTAL = 32 * 1024 * 1024
MAX_LOG_FILES = 64


def group_alive(pid):
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False


def stop_group(process, grace=5):
    # The leader may have exited while its server/display descendants survived.
    forced = group_alive(process.pid)
    if forced:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline and group_alive(process.pid):
            time.sleep(0.1)
        if group_alive(process.pid):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        raise RuntimeError('owned launcher did not exit after bounded cleanup')
    return forced


def collect_logs(root):
    texts, hashes, skipped = [], {}, {}
    remaining = MAX_LOG_TOTAL
    count = 0
    for index, path in enumerate(root.rglob('*')):
        if index >= 512:
            skipped['*'] = 'discovery budget exceeded'
            break
        if path.suffix.lower() not in {'.log', '.rpt', '.adm'}:
            continue
        name = path.relative_to(root).as_posix()
        count += 1
        if path.is_symlink() or not path.is_file():
            skipped[name] = 'not a regular log'
            continue
        size = path.stat().st_size
        if count > MAX_LOG_FILES or size > min(MAX_LOG_FILE, remaining):
            skipped[name] = 'log count or byte budget exceeded'
            continue
        digest, chunks, length = hashlib.sha256(), [], 0
        with path.open('rb') as stream:
            while length < size:
                chunk = stream.read(min(65536, size - length))
                if not chunk:
                    break
                length += len(chunk)
                digest.update(chunk)
                chunks.append(chunk)
        remaining -= length
        hashes[name] = digest.hexdigest()
        texts.append(b''.join(chunks).decode(errors='replace'))
        if path.stat().st_size != length:
            skipped[name] = 'log changed during bounded snapshot'
    return '\n'.join(texts), hashes, skipped


def classify(text):
    if re.search(r"SCRIPT\s*\(E\)|Can't compile|Cannot compile|Core native self-test FAILED", text):
        return 'compiler-error'
    if '[HollowCountry] Invalid settings; original file preserved;' in text or '[HollowCountry] Settings rejected; original file preserved:' in text:
        return 'settings-rejected'
    if '[HollowCountry] Server initialized;' in text:
        return 'initialized'
    return None


def native_observation(text, direct):
    prefix = '[HC Native Actor]' if direct else '[HC Native Autotest]'
    if prefix + ' FAIL' in text:
        return 'FAIL-marker'
    completion = (' PASS authored assertions; not native harness acceptance' if direct
                  else ' PASS; XML and logs still require verification')
    if prefix + completion in text:
        return 'PASS-marker; receipt verification required' if direct else 'PASS-marker; XML verification required'
    if prefix + ' BEGIN' in text:
        return 'begun-but-incomplete'
    return None


def negative_settings(name):
    fixtures = {'malformed-json': b'{', 'oversized': b' ' * 16385,
                'unsupported-schema': b'{"SchemaVersion":2}'}
    if name not in fixtures:
        raise ValueError('unknown negative settings experiment')
    return fixtures[name]


def win(path):
    return 'Z:' + str(Path(path).absolute()).replace('/', '\\')


def configuration():
    # Required server identity/protocol fields follow the installed stock cfg.
    return ('hostname="Hollow Country disposable compiler";\n'
            'password="local-compiler-probe"; maxPlayers=6;\n'
            'instanceId=1; guaranteedUpdates=1; shardId="hcdev1";\n'
            'verifySignatures=0; forceSameBuild=1; BattlEye=0; disableVoN=1; steamQueryPort=2405;\n'
            'class Missions { class DayZ { template="dayzOffline.chernarusplus"; }; };\n')


def safe(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlink ancestors forbidden')
    if any(n.lower() in {'steamapps', '.git'} for n in path.parts):
        raise ValueError('use isolated paths outside Steam/source')
    checkout = Path(__file__).absolute().parents[2]
    if path == checkout or checkout in path.parents:
        raise ValueError('experiment cannot be inside source checkout')
    return path


def read_state_seed(root):
    root = safe(root)
    allowed = {'config.json', 'hordes-a.json', 'hordes-b.json'}
    result = {}
    for index, path in enumerate(root.iterdir()):
        if index >= 3 or path.name not in allowed or path.is_symlink() or not path.is_file():
            raise ValueError('only regular infected config/journal seed files allowed')
        with path.open('rb') as stream:
            blob = stream.read(65537)
        if len(blob) > 65536:
            raise ValueError('infected seed file exceeds 64 KiB')
        result[path.name] = blob
    return result


def run(server_root, source_pbo, experiment, prefix, seconds=90, settings=None, settings_case=None, state_seed=None, hold_seconds=0, diagnostic=False, diagnostic_selftests=False, native_autotest_scripts=None, autotest_x=6500, autotest_z=6500, native_actor_direct=False, item_compatibility_audit=False, group_checks=False, infected_death_scripts=None):
    death_mode = infected_death_scripts is not None
    if death_mode:
        if diagnostic:
            raise ValueError('infected death mode requires the normal server executable')
        if group_checks or item_compatibility_audit or diagnostic_selftests or native_autotest_scripts is not None:
            raise ValueError('infected death requires one mission hook')
        if native_actor_direct or hold_seconds or state_seed is not None:
            raise ValueError('infected death is a fixed purpose without actor/hold/seed options')
        if settings is not None or settings_case is not None:
            raise ValueError('infected death requires fresh default settings')
        if type(seconds) is not int or not 15 <= seconds <= death_probe.MAX_OUTER_SECONDS:
            raise ValueError('infected death outer budget must be integer 15..180 seconds')
    if group_checks and (item_compatibility_audit or diagnostic_selftests or native_autotest_scripts is not None):
        raise ValueError('group checks require one mission hook')
    if item_compatibility_audit and (diagnostic_selftests or native_autotest_scripts is not None):
        raise ValueError('item audit requires one mission hook')
    if native_actor_direct and native_autotest_scripts is None:
        raise ValueError('direct actor requires native script interfaces')
    if diagnostic_selftests and not diagnostic:
        raise ValueError('selftests require explicit diagnostic server mode')
    if native_autotest_scripts is not None and (not diagnostic or diagnostic_selftests):
        raise ValueError('native autotest requires diagnostic mode and one mission hook')
    if not 15 <= seconds <= 300:
        raise ValueError('probe duration must be 15..300 seconds')
    if not 0 <= hold_seconds <= 240 or hold_seconds >= seconds:
        raise ValueError('hold must be 0..240 seconds and shorter than probe duration')
    seeds = read_state_seed(state_seed) if state_seed is not None else {}
    root, experiment, prefix = [safe(p) for p in (server_root, experiment, prefix)]
    executable = root / ('DayZDiag_x64.exe' if diagnostic else 'DayZServer_x64.exe')
    if not executable.is_file() or not (root / 'mpmissions/dayzOffline.chernarusplus/init.c').is_file():
        raise ValueError('complete isolated server required')
    if str(root).startswith('/mnt/'):
        raise ValueError('Wine PE loading must use the Linux filesystem')
    blob = Path(source_pbo).read_bytes()
    pbo.parse(blob)
    settings_blob = None
    if settings is not None and settings_case is not None:
        raise ValueError('explicit and negative settings are mutually exclusive')
    if settings is not None:
        with Path(settings).open('rb') as stream:
            settings_blob = stream.read(16385)
        if len(settings_blob) > 16384 or validate_settings(json.loads(settings_blob)):
            raise ValueError('invalid or oversized explicit settings')
    if settings_case is not None:
        settings_blob = negative_settings(settings_case)
    if experiment.exists() or experiment.is_symlink():
        raise ValueError('experiment must be fresh')
    if subprocess.run(['pgrep', '-f', r'(^|/)DayZ(Server|Diag)_x64\.exe( |$)'], capture_output=True).returncode == 0:
        raise ValueError('another DayZ server is running')
    wine = Path('/usr/lib/wine/wine64')
    if not wine.is_file() or not shutil.which('xvfb-run'):
        raise ValueError('Wine64 and xvfb-run required')
    experiment.mkdir(parents=True)
    profiles, storage = experiment / 'profiles', experiment / 'storage'
    profiles.mkdir()
    storage.mkdir()
    if settings_blob is not None:
        (profiles / 'HollowCountry').mkdir()
        (profiles / 'HollowCountry/settings.json').write_bytes(settings_blob)
    if seeds:
        seed_root = profiles / 'HollowCountry/Infected'
        seed_root.mkdir(parents=True, exist_ok=True)
        for name, data in seeds.items():
            (seed_root / name).write_bytes(data)
    battleye = experiment / 'battleye'
    battleye.mkdir()
    native_be = root / 'battleye/BEServer_x64.dll'
    if not native_be.is_file():
        raise ValueError('installed BattlEye server DLL required even for disposable config')
    shutil.copyfile(native_be, battleye / native_be.name)
    addon = experiment / '@HollowCountry/addons'
    addon.mkdir(parents=True)
    (addon / 'hollowcountry.pbo').write_bytes(blob)
    config = experiment / 'serverDZ.cfg'
    config.write_text(configuration())
    command = ['xvfb-run', '-a', str(wine), str(executable), '-ip=127.0.0.1', '-port=2402',
               '-config=' + win(config), '-profiles=' + win(profiles), '-storage=' + win(storage),
               '-mod=' + win(addon.parent), '-BEpath=' + win(battleye), '-doLogs', '-adminLog', '-noPause']
    if diagnostic:
        command.append('-server')
    diagnostic_mission = None
    if diagnostic_selftests:
        from tools.setup.diagnostic_mission import prepare_diagnostic_mission
        mission = experiment / 'diagnostic.chernarusplus'
        diagnostic_mission = prepare_diagnostic_mission(root / 'mpmissions/dayzOffline.chernarusplus', mission)
        command.append('-mission=' + win(mission))
    if item_compatibility_audit:
        from tools.setup.diagnostic_mission import prepare_diagnostic_mission
        mission = experiment / 'item-audit.chernarusplus'
        diagnostic_mission = prepare_diagnostic_mission(root / 'mpmissions/dayzOffline.chernarusplus', mission,
                                                       purpose='item-audit')
        command.append('-mission=' + win(mission))
    if group_checks:
        from tools.setup.diagnostic_mission import prepare_diagnostic_mission
        mission = experiment / 'group-checks.chernarusplus'
        diagnostic_mission = prepare_diagnostic_mission(root / 'mpmissions/dayzOffline.chernarusplus', mission,
                                                       purpose='group-checks')
        command.append('-mission=' + win(mission))
    if native_autotest_scripts is not None:
        from tools.testing.native_autotest import prepare_autotest
        mission = experiment / 'native.chernarusplus'
        diagnostic_mission = prepare_autotest(root / 'mpmissions/dayzOffline.chernarusplus', mission,
                                               native_autotest_scripts, x=autotest_x, z=autotest_z,
                                               mode='direct-actor' if native_actor_direct else 'harness')
        command.append('-mission=' + win(mission))
        if not native_actor_direct:
            command.append('-autotest=' + win(mission / 'hc-autotest.json'))
    death_manifest = None
    death_mission = None
    if death_mode:
        death_mission = experiment / 'infected-death.chernarusplus'
        death_manifest = death_probe.prepare_probe(
            root / 'mpmissions/dayzOffline.chernarusplus', death_mission,
            infected_death_scripts, x=autotest_x, z=autotest_z,
            run_id=secrets.token_hex(16), diagnostic_only=False)
        diagnostic_mission = death_manifest
        command.append('-mission=' + win(death_mission))
    env = dict(os.environ, WINEPREFIX=str(prefix), WINEARCH='win64', WINEDEBUG='-all')
    report = {'schema': 1, 'environment': 'actual-DayZ-server-under-Wine',
              'runtime_acceptance': 'pending', 'signature_verified': False,
              'client_count': 0, 'status': 'timeout', 'forced_stop': False,
              'requested_gameplay_bind': '127.0.0.1:2402',
              'steam_query_may_bind_wildcard': True, 'command': command,
              'pbo_sha256': hashlib.sha256(blob).hexdigest(),
              'server_sha256': hashlib.sha256(executable.read_bytes()).hexdigest()}
    report['config_sha256'] = hashlib.sha256(config.read_bytes()).hexdigest()
    report['executable_kind'] = 'diagnostic-server' if diagnostic else 'dedicated-server'
    report['diagnostic_mission'] = diagnostic_mission
    report['item_compatibility_audit_requested'] = bool(item_compatibility_audit)
    report['group_checks_requested'] = bool(group_checks)
    report['infected_death_requested'] = death_mode
    report['infected_death_run_id'] = death_manifest['run_id'] if death_manifest else None
    report['infected_death_timed_out'] = False
    report['infected_death_receipt'] = None
    report['infected_death_observation'] = 'not-run'
    report['infected_death_receipt_error'] = None
    report['infected_death_outer_outcome'] = 'not-run'
    if death_mode:
        report['infected_death_outer_budget_seconds'] = seconds
        report['infected_death_cleanup_reserve_seconds'] = 10
        report['infected_death_process_budget_seconds'] = seconds - 10
    report['native_autotest_observation'] = 'not-run'
    report['native_autotest_timed_out'] = False
    report['engine_error_observed'] = False
    report['settings_rejection_observed'] = False
    report['settings_sha256'] = hashlib.sha256(settings_blob).hexdigest() if settings_blob is not None else None
    report['negative_settings_experiment'] = settings_case
    report['state_seed_sha256'] = {name: hashlib.sha256(data).hexdigest() for name, data in seeds.items()}
    report['hold_seconds_requested'] = hold_seconds
    report['hold_seconds_observed'] = 0
    process = None
    deadline_expired = False
    outer_started = time.monotonic() if death_mode else None
    outer_deadline = outer_started + seconds if death_mode else None

    def checked_death_receipt(timed_out):
        receipt = death_probe.validate_result(
            profiles / death_probe.RESULT, death_mission, outer_timed_out=timed_out)
        if receipt['run_id'] != report['infected_death_run_id']:
            raise ValueError('receipt differs from generated harness nonce')
        if receipt.get('execution_mode') != 'normal-server':
            raise ValueError('receipt not from prepared normal-server mission')
        return receipt

    try:
        with (experiment / 'wine-output.log').open('wb') as output:
            process = subprocess.Popen(command, cwd=root, env=env, stdout=output,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            report['launcher_pid'] = process.pid
            deadline = time.monotonic() + seconds
            if death_mode:
                # Includes cold startup. Keep ten seconds for the existing
                # bounded TERM/KILL/wait cleanup; never extend a slow run.
                deadline = outer_deadline - 10
            initialized_at = None
            while time.monotonic() < deadline:
                text, _, _ = collect_logs(profiles)
                result = classify(text)
                report['engine_error_observed'] = report['engine_error_observed'] or result == 'compiler-error'
                report['settings_rejection_observed'] |= result == 'settings-rejected'
                if report['settings_rejection_observed']:
                    report['status'] = 'settings-rejected'
                    break
                if death_mode:
                    if '[HC Infected Death] BEGIN' in text:
                        report['infected_death_observation'] = 'begun-but-incomplete'
                    if time.monotonic() >= deadline:
                        deadline_expired = True
                        break
                    if report['engine_error_observed']:
                        report['status'] = 'compiler-error'
                        break
                    if '[HC Infected Death] FAIL' in text:
                        report['status'] = 'infected-death-failed'
                        report['infected_death_observation'] = 'FAIL-marker'
                        break
                    if process.poll() is not None:
                        report['status'] = 'exited-before-infected-death-completion'
                        break
                    marker = '[HC Infected Death] COMPLETE run=' + report['infected_death_run_id']
                    if re.search(re.escape(marker) + r'(?=\s|$)', text):
                        try:
                            receipt = checked_death_receipt(False)
                        except (OSError, ValueError) as exc:
                            report['infected_death_receipt_error'] = str(exc)[:512]
                            report['infected_death_observation'] = 'invalid-receipt'
                            report['status'] = 'infected-death-failed'
                            break
                        # Evidence reads can cross the deadline or outlive
                        # the launcher; neither condition permits completion.
                        if time.monotonic() >= deadline:
                            deadline_expired = True
                            break
                        if process.poll() is not None:
                            report['status'] = 'exited-before-infected-death-completion'
                            break
                        report['infected_death_receipt'] = receipt
                        report['infected_death_observation'] = 'verified-five-case-receipt'
                        report['status'] = 'infected-death-completed'
                        break
                    # Initialization alone cannot finish this purpose.
                    time.sleep(1)
                    continue
                if native_autotest_scripts is not None:
                    observation = native_observation(text, native_actor_direct)
                    if observation == 'begun-but-incomplete':
                        report['native_autotest_observation'] = 'begun-but-incomplete'
                    if time.monotonic() >= deadline:
                        deadline_expired = True
                        break
                    if observation == 'FAIL-marker':
                        report['native_autotest_observation'] = observation
                        report['status'] = 'compiler-error' if report['engine_error_observed'] else 'native-autotest-failed'
                        break
                    if observation and observation.startswith('PASS-marker;'):
                        report['native_autotest_observation'] = observation
                        report['status'] = 'compiler-error' if report['engine_error_observed'] else 'native-autotest-completed'
                        break
                    if process.poll() is not None:
                        report['status'] = 'compiler-error' if report['engine_error_observed'] else 'exited-before-native-autotest-completion'
                        break
                    time.sleep(1)
                    continue
                if result == 'initialized':
                    # Reading bounded logs can still cross the wall-clock limit;
                    # a historical marker cannot prove the launcher remains live.
                    if time.monotonic() >= deadline:
                        deadline_expired = True
                        break
                    if process.poll() is not None:
                        report['status'] = 'exited-during-initialization-hold'
                        break
                    if initialized_at is None:
                        initialized_at = time.monotonic()
                    report['hold_seconds_observed'] = round(time.monotonic() - initialized_at, 3)
                    if report['hold_seconds_observed'] >= hold_seconds:
                        report['status'] = result
                        break
                elif result:
                    report['status'] = result
                    break
                if process.poll() is not None:
                    report['status'] = 'exited-before-initialization'
                    break
                time.sleep(1)
            else:
                deadline_expired = True
    except Exception:
        # Re-raise the original failure after preserving a truthful report.
        # A launch/I/O exception is not evidence that the deadline expired.
        report['status'] = 'probe-error'
        raise
    finally:
        if process is not None:
            report['forced_stop'] = stop_group(process)
        report['launcher_exit_code'] = process.returncode if process else None
        final_text, report['logs'], report['skipped_logs'] = collect_logs(experiment)
        final_result = classify(final_text)
        report['engine_error_observed'] = report['engine_error_observed'] or final_result == 'compiler-error'
        report['settings_rejection_observed'] |= final_result == 'settings-rejected'
        if report['settings_rejection_observed']:
            report['status'] = 'settings-rejected'
        if death_mode:
            if time.monotonic() >= outer_deadline:
                deadline_expired = True
            if '[HC Infected Death] FAIL' in final_text:
                report['infected_death_observation'] = 'FAIL-marker'
                if report['status'] == 'infected-death-completed':
                    report['status'] = 'infected-death-failed'
            # Always supply the bounded run's real timeout outcome.
            # Final evidence may revoke completion but never promote a late run.
            try:
                final_receipt = checked_death_receipt(deadline_expired)
            except (OSError, ValueError) as exc:
                report['infected_death_receipt_error'] = str(exc)[:512]
                report['infected_death_receipt'] = None
                if report['status'] == 'infected-death-completed':
                    report['status'] = 'infected-death-failed'
            else:
                if report['status'] == 'infected-death-completed' and not report['engine_error_observed']:
                    report['infected_death_receipt'] = final_receipt
                else:
                    report['infected_death_receipt'] = None
            # Account for process cleanup and final evidence reads too.
            if time.monotonic() >= outer_deadline:
                deadline_expired = True
            report['infected_death_timed_out'] = deadline_expired
            report['infected_death_outer_elapsed_seconds'] = round(time.monotonic() - outer_started, 3)
            if deadline_expired:
                report['infected_death_receipt'] = None
                if report['status'] in {'infected-death-completed', 'infected-death-failed'}:
                    report['status'] = 'timeout'
            if report['engine_error_observed']:
                report['infected_death_receipt'] = None
                report['status'] = 'compiler-error'
            if deadline_expired:
                report['infected_death_outer_outcome'] = 'timed-out'
            elif report['status'] == 'infected-death-completed':
                report['infected_death_outer_outcome'] = 'completed-before-deadline'
            elif report['status'].startswith('exited-'):
                report['infected_death_outer_outcome'] = 'exited-before-completion'
            else:
                report['infected_death_outer_outcome'] = 'failed'
        if native_autotest_scripts is not None:
            report['native_autotest_timed_out'] = deadline_expired
            final_observation = native_observation(final_text, native_actor_direct)
            previous = report['native_autotest_observation']
            if final_observation == 'FAIL-marker':
                report['native_autotest_observation'] = final_observation
                if report['status'] == 'native-autotest-completed':
                    report['status'] = 'native-autotest-failed'
            elif previous in {'not-run', 'begun-but-incomplete'} and final_observation:
                # Retain late evidence, without converting timeout/exit/error
                # into success after the deadline or process cleanup.
                report['native_autotest_observation'] = final_observation.replace(
                    'PASS-marker; ', 'PASS-marker; observed during final collection; ')
        if report['engine_error_observed']:
            report['status'] = 'compiler-error'
        if settings_blob is not None:
            with (profiles / 'HollowCountry/settings.json').open('rb') as stream:
                report['settings_original_preserved'] = stream.read(16386) == settings_blob
        (experiment / 'compiler-report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('server-root', 'pbo', 'experiment', 'prefix'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--seconds', type=int, default=90)
    parser.add_argument('--hold-seconds', type=int, default=0)
    parser.add_argument('--state-seed', type=Path)
    parser.add_argument('--diagnostic', action='store_true', help='use explicitly staged DayZDiag_x64.exe in server mode')
    parser.add_argument('--diagnostic-selftests', action='store_true', help='instrument a fresh disposable mission for native scalar/storage probes')
    parser.add_argument('--item-compatibility-audit', action='store_true', help='request fixed metadata export in a fresh mission; inspect export completeness separately from startup')
    parser.add_argument('--group-checks', action='store_true', help='request fixed native policy fixtures; inspect fixture result separately from startup')
    parser.add_argument('--infected-death-scripts', type=Path,
                        help='fixed five-case normal-server mission; installed interfaces required; <=180s including map startup and cleanup, fixture watchdog stays 60s')
    parser.add_argument('--native-autotest-scripts', type=Path, help='installed extracted script interfaces for a fresh native TestHarness mission')
    parser.add_argument('--autotest-x', type=float, default=6500)
    parser.add_argument('--autotest-z', type=float, default=6500)
    parser.add_argument('--native-actor-direct', action='store_true', help='use authored direct actor assertions rather than native TestHarness')
    setting_options = parser.add_mutually_exclusive_group()
    setting_options.add_argument('--settings', type=Path)
    setting_options.add_argument('--settings-case', choices=['malformed-json', 'oversized', 'unsupported-schema'])
    args = parser.parse_args()
    try:
        report = run(args.server_root, args.pbo, args.experiment, args.prefix, args.seconds, args.settings, args.settings_case, args.state_seed, args.hold_seconds, args.diagnostic, args.diagnostic_selftests, args.native_autotest_scripts, args.autotest_x, args.autotest_z, args.native_actor_direct, args.item_compatibility_audit, args.group_checks,
                     infected_death_scripts=args.infected_death_scripts)
        print(json.dumps(report, indent=2))
        expected = 'settings-rejected' if args.settings_case else 'initialized'
        if args.infected_death_scripts is not None:
            expected = 'infected-death-completed'
        return 0 if report['status'] == expected and report.get('settings_original_preserved', True) else 1
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
