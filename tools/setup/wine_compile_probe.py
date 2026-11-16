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
import shutil
import signal
import subprocess
import time

from tools.package import pbo
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


def run(server_root, source_pbo, experiment, prefix, seconds=90, settings=None, settings_case=None, state_seed=None, hold_seconds=0, diagnostic=False, diagnostic_selftests=False, native_autotest_scripts=None, autotest_x=6500, autotest_z=6500, native_actor_direct=False):
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
    if native_autotest_scripts is not None:
        from tools.testing.native_autotest import prepare_autotest
        mission = experiment / 'native.chernarusplus'
        diagnostic_mission = prepare_autotest(root / 'mpmissions/dayzOffline.chernarusplus', mission,
                                               native_autotest_scripts, x=autotest_x, z=autotest_z,
                                               mode='direct-actor' if native_actor_direct else 'harness')
        command.append('-mission=' + win(mission))
        if not native_actor_direct:
            command.append('-autotest=' + win(mission / 'hc-autotest.json'))
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
    report['native_autotest_observation'] = 'not-run'
    report['settings_sha256'] = hashlib.sha256(settings_blob).hexdigest() if settings_blob is not None else None
    report['negative_settings_experiment'] = settings_case
    report['state_seed_sha256'] = {name: hashlib.sha256(data).hexdigest() for name, data in seeds.items()}
    report['hold_seconds_requested'] = hold_seconds
    report['hold_seconds_observed'] = 0
    process = None
    try:
        with (experiment / 'wine-output.log').open('wb') as output:
            process = subprocess.Popen(command, cwd=root, env=env, stdout=output,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            report['launcher_pid'] = process.pid
            deadline = time.monotonic() + seconds
            initialized_at = None
            saw_engine_error = False
            while time.monotonic() < deadline:
                text, _, _ = collect_logs(profiles)
                result = classify(text)
                if native_autotest_scripts is not None:
                    saw_engine_error = saw_engine_error or result == 'compiler-error'
                    if time.monotonic() >= deadline:
                        break
                    if ('[HC Native Actor] FAIL' if native_actor_direct else '[HC Native Autotest] FAIL') in text:
                        report['native_autotest_observation'] = 'FAIL-marker'
                        report['status'] = 'compiler-error' if saw_engine_error else 'native-autotest-failed'
                        break
                    if ('[HC Native Actor] PASS authored assertions; not native harness acceptance' if native_actor_direct else '[HC Native Autotest] PASS; XML and logs still require verification') in text:
                        report['native_autotest_observation'] = 'PASS-marker; receipt verification required' if native_actor_direct else 'PASS-marker; XML verification required'
                        report['status'] = 'compiler-error' if saw_engine_error else 'native-autotest-completed'
                        break
                    if process.poll() is not None:
                        report['status'] = 'compiler-error' if saw_engine_error else 'exited-before-native-autotest-completion'
                        break
                    time.sleep(1)
                    continue
                if result == 'initialized':
                    # Reading bounded logs can still cross the wall-clock limit;
                    # a historical marker cannot prove the launcher remains live.
                    if time.monotonic() >= deadline:
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
    finally:
        if process is not None:
            report['forced_stop'] = stop_group(process)
        report['launcher_exit_code'] = process.returncode if process else None
        _, report['logs'], report['skipped_logs'] = collect_logs(experiment)
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
    parser.add_argument('--native-autotest-scripts', type=Path, help='installed extracted script interfaces for a fresh native TestHarness mission')
    parser.add_argument('--autotest-x', type=float, default=6500)
    parser.add_argument('--autotest-z', type=float, default=6500)
    parser.add_argument('--native-actor-direct', action='store_true', help='use authored direct actor assertions rather than native TestHarness')
    setting_options = parser.add_mutually_exclusive_group()
    setting_options.add_argument('--settings', type=Path)
    setting_options.add_argument('--settings-case', choices=['malformed-json', 'oversized', 'unsupported-schema'])
    args = parser.parse_args()
    try:
        report = run(args.server_root, args.pbo, args.experiment, args.prefix, args.seconds, args.settings, args.settings_case, args.state_seed, args.hold_seconds, args.diagnostic, args.diagnostic_selftests, args.native_autotest_scripts, args.autotest_x, args.autotest_z, args.native_actor_direct)
        print(json.dumps(report, indent=2))
        expected = 'settings-rejected' if args.settings_case else 'initialized'
        return 0 if report['status'] == expected and report.get('settings_original_preserved', True) else 1
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
