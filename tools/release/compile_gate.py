"""Run the actual DayZ compiler under Wine against a checkout or commit.

This launches and stops an isolated DayZServer_x64.exe. Do not execute against
an active server or in a session that forbids game executable launches.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from tools.package import inventory_sizes, pbo, weapon_pack_guards
from tools.audit.pbo_config import parse_text_config, read_config_members
from tools.setup import wine_compile_probe as probe
from tools.release import ship_inputs

SCRIPT_ERROR = re.compile(r'SCRIPT\s*\(E\)', re.I)
COMPILE_FAILURE = re.compile(
    r"Can't compile|Cannot compile|Failed to load .*script|script.*module.*(?:failed|failure)|"
    r'(?:failed|unable|cannot) to load.*(?:script|module)', re.I)
# JsonFileLoader reports unreadable data as SCRIPT (E) "JSON ERROR" at runtime. The
# gate runs the vanilla mission without HC mission data, so after every module
# (Mission included) loaded these are missing-data reports, not compile failures.
RUNTIME_JSON_ERROR = re.compile(r'SCRIPT\s*\(E\):\s*JSON ERROR\b', re.I)
MODULE_LOADED = re.compile(r'\bModule:\s*([A-Za-z0-9_]+);\s*loaded\s+\d+x?\s+files', re.I)


def prerequisites(server_root=None, prefix=None):
    """Discover only isolated cached installs; never select a live Windows server.

    Explicit CLI/environment inputs take precedence. Missing prerequisites are a
    documented release skip; a discovered gate that fails is never a skip.
    """
    cache = Path.home() / '.cache/hollow-country'
    server_root = server_root or os.environ.get('HC_SERVER_ROOT')
    prefix = prefix or os.environ.get('HC_WINE_PREFIX')
    if server_root is None:
        server_root = next((p for p in sorted(cache.glob('wine-server-*'), reverse=True)
                            if (p / 'DayZServer_x64.exe').is_file()), None)
    if prefix is None:
        prefix = next((p for p in sorted(cache.glob('wine-server-prefix-*'), reverse=True)
                       if (p / 'system.reg').is_file() and (p / 'drive_c').is_dir()), None)
    if server_root is None:
        return None, None, 'isolated server root absent (HC_SERVER_ROOT or cached wine-server-*)'
    if prefix is None:
        return None, None, 'isolated Wine prefix absent (HC_WINE_PREFIX or cached wine-server-prefix-*)'
    server_root, prefix = [Path(p).expanduser().absolute() for p in (server_root, prefix)]
    try:
        for path in (server_root, prefix):
            probe.safe(path)
    except ValueError:
        return None, None, 'isolated server root or Wine prefix has an unsafe location'
    if str(server_root).startswith('/mnt/'):
        return None, None, 'isolated server root must be on the Linux filesystem'
    if not all((server_root / name).is_file() for name in (
            'DayZServer_x64.exe', 'mpmissions/dayzOffline.chernarusplus/init.c',
            'battleye/BEServer_x64.dll')):
        return None, None, 'complete isolated server root absent'
    if not (prefix / 'system.reg').is_file() or not (prefix / 'drive_c').is_dir():
        return None, None, 'initialized isolated Wine prefix absent'
    if not Path('/usr/lib/wine/wine64').is_file() or not shutil.which('xvfb-run'):
        return None, None, 'Wine64 or xvfb-run absent'
    return server_root, prefix, None


def script_summary(experiment):
    # collect_logs applies the probe's byte/count limits and refuses symlinks.
    _, hashes, skipped = probe.collect_logs(experiment / 'profiles')
    # Only profiles/script_*.log establishes script-module loading. RPT and
    # launcher logs can repeat errors and must not inflate the script count.
    texts = []
    for name in sorted(hashes):
        path = Path(name)
        if len(path.parts) == 1 and path.match('script_*.log'):
            source = experiment / 'profiles' / path
            if source.is_symlink() or not source.is_file():
                skipped[name] = 'script log is no longer a regular file'
                continue
            with source.open('rb') as stream:
                data = stream.read(probe.MAX_LOG_FILE + 1)
            if hashlib.sha256(data).hexdigest() != hashes[name]:
                skipped[name] = 'script log changed after bounded snapshot'
                continue
            texts.append(data.decode(errors='replace'))
    script = '\n'.join(texts)
    modules = list(dict.fromkeys(MODULE_LOADED.findall(script)))
    errors = [line for line in script.splitlines() if SCRIPT_ERROR.search(line)]
    runtime = []
    if 'Mission' in modules:
        runtime = [line for line in errors if RUNTIME_JSON_ERROR.search(line)]
        errors = [line for line in errors if not RUNTIME_JSON_ERROR.search(line)]
    print('compile_gate: modules_loaded=' + (','.join(modules) or 'none')
          + ' SCRIPT (E)=' + str(len(errors))
          + ' runtime_json_errors=' + str(len(runtime)))
    for line in runtime[:3]:
        print('compile_gate: runtime_json_error (gate mission lacks HC data): ' + private(line)[:400])
    for line in errors[:5]:
        print('compile_gate: script_error: ' + private(line)[:1200])
    return modules, errors, skipped


def private(text):
    """Only filtered diagnostics go to the terminal; raw logs stay in cache."""
    text = str(text).replace(str(Path.home()), '~')
    text = re.sub(r'(?i)(?:[a-z]:[\\/]|/mnt/[a-z]/)users[\\/][^\\/\s"\']+', '~', text)
    text = re.sub(r'(?i)(?:[a-z]:)?[\\/](?:home|Users)[\\/][^\\/\s"\']+', '~', text)
    text = re.sub(r'\b\d{17}\b', '<identity>', text)
    text = re.sub(r'(?i)\b(password|admin_?id|player_?(?:id|name)|steam_?id)\s*[:=]\s*[^\s,;]+',
                  r'\1=<redacted>', text)
    return text


def git(tree, *args):
    result = subprocess.run(['git', '-C', str(tree), *args],
                            capture_output=True, check=False, timeout=120)
    if result.returncode:
        raise ValueError('git read failed: ' + result.stderr.decode(errors='replace'))
    return result.stdout


@contextlib.contextmanager
def source_tree(tree, commit, cache):
    if not commit:
        yield tree
        return
    sha = git(tree, 'rev-parse', '--verify', '--end-of-options', commit + '^{commit}').decode().strip()
    # Equivalent detached tracked tree without touching read-only .git metadata.
    # No checkout/reset/worktree registration; the unique snapshot always goes away.
    with tempfile.TemporaryDirectory(prefix='tree-' + sha[:12] + '-', dir=cache) as directory:
        root = Path(directory)
        archive = git(tree, 'archive', '--format=tar', sha)
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            for entry in stream:
                relative = Path(entry.name)
                if relative.is_absolute() or '..' in relative.parts:
                    raise ValueError('unsafe archive member')
                target = root / relative
                if entry.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif entry.isfile():
                    if target.suffix.lower() == '.biprivatekey' or target.name == 'hits_privkey.txt':
                        raise ValueError('private signing input forbidden')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with stream.extractfile(entry) as source, target.open('wb') as dest:
                        dest.write(source.read())
                elif entry.issym() or entry.islnk():
                    raise ValueError('links forbidden in compile snapshot')
        yield root


def validate_adapter_dependencies(tree, extra_mods):
    """Reject an incomplete installed stack before starting the native compiler.

    Only config metadata is inspected; no installed scripts/assets are staged.
    The adapter has one authored CfgPatches requiredAddons array. Refuse a changed
    declaration shape rather than silently skipping dependency validation.
    """
    config = (tree / 'mods/HollowCountryExpansionAI/config.cpp').read_text()
    # The release-time attachment scale patch (see ship_config) carries its own
    # requiredAddons; check it against the stack too, apart from the authored array.
    injected = re.findall(re.escape(inventory_sizes.PACK_BEGIN + ' CfgPatches') + r'\n(.*?)'
                          + re.escape(inventory_sizes.PACK_END + ' CfgPatches'), config, flags=re.S)
    config = re.sub(re.escape(inventory_sizes.PACK_BEGIN + ' CfgPatches') + r'\n.*?'
                    + re.escape(inventory_sizes.PACK_END + ' CfgPatches'), '', config, flags=re.S)
    config = re.sub(r'/\*.*?\*/|//[^\n]*', '', config, flags=re.S)
    arrays = re.findall(r'\brequiredAddons\s*\[\s*\]\s*=\s*\{([^{}]*)\}\s*;', config)
    if len(arrays) != 1:
        raise ValueError('HCX requiredAddons declaration changed; review required')
    required = set(re.findall(r'"([^"\n]+)"', arrays[0]))
    if not required or re.sub(r'"[^"\n]+"|[\s,]', '', arrays[0]):
        raise ValueError('HCX requiredAddons must be a nonempty literal string array')
    for block in injected:
        for array in re.findall(r'\brequiredAddons\s*\[\s*\]\s*=\s*\{([^{}]*)\}\s*;', block):
            required.update(re.findall(r'"([^"\n]+)"', array))
    base = (tree / 'mods/HollowCountry/config.cpp').read_bytes()
    providers = set(parse_text_config(base, ('CfgPatches',))['CfgPatches'])
    for mod in extra_mods:
        for addon in sorted((mod / 'addons').iterdir()):
            if addon.is_file() and addon.suffix.lower() == '.pbo':
                try:
                    for _, roots in read_config_members(addon, ('CfgPatches',)):
                        providers.update(roots['CfgPatches'])
                except (OSError, ValueError) as error:
                    raise ValueError('cannot inspect staged dependency config: '
                                     + mod.name + '/' + addon.name) from error
    missing = sorted(required - providers)
    if missing:
        raise ValueError('HCX requiredAddons missing from staged stack: ' + ', '.join(missing))
    print('compile_gate: HCX requiredAddons verified=' + str(len(required))
          + ' dependency_mods=' + str(len(extra_mods)))


@contextlib.contextmanager
def compatibility_inputs(tree, workshop, cache):
    """Stage our original addons only; load installed dependency mods read-only."""
    manifest_path = tree / 'tools/setup/workshop_mods.json'
    if not weapon_pack_guards.declared(manifest_path):
        print('compile_gate: weapon_pack_guards=absent (pack not declared)')
        yield {}
        return
    if not (workshop / weapon_pack_guards.ITEM).exists():
        raise ValueError('declared weapon pack missing; complete compile stack required')
    manifest = json.loads(manifest_path.read_bytes())
    # Match the friend server's entire declared dependency stack, including the
    # living-pack providers required by the full adapter. No Wine exclusions.
    dependencies = [row for row in manifest['mods'] if not row['publish']]
    extra_mods = [workshop / row['id'] for row in sorted(dependencies, key=lambda row: row['rank'])]
    # Validate before launching: partial dependency stacks must fail, never silently
    # compile only the base mod and label that as guard acceptance.
    probe.referenced_mods(extra_mods)
    validate_adapter_dependencies(tree, extra_mods)
    with tempfile.TemporaryDirectory(prefix='guard-inputs-', dir=cache) as directory:
        root = Path(directory)
        guard_mod = root / '@HCWeaponPackGuards'
        result = subprocess.run(
            [sys.executable, '-B', '-m', 'tools.package.weapon_pack_guards', '--declared-stack',
             '--workshop', str(workshop), '--out', str(guard_mod / 'addons')],
            cwd=tree, capture_output=True, text=True,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=300)
        if result.returncode:
            raise ValueError('weapon-pack guard generation failed; installed API review required')
        receipt = json.loads((guard_mod / 'addons/weapon-pack-guards.json').read_bytes())
        if receipt.get('status') != 'generated':
            raise ValueError('installed pack did not produce the required guard')
        adapter = root / 'hollowcountryexpansionai.pbo'
        adapter.write_bytes(pbo.pack(pbo.collect_addon(tree / 'mods/HollowCountryExpansionAI',
                                                      prefix='HollowCountryExpansionAI'),
                                     prefix='HollowCountryExpansionAI'))
        # Ship layout: the guard sits beside the HCX PBO in @HollowCountryExpansionAI/addons,
        # exactly as the friend installer places it (a separate test-only mod hid a prefix clash).
        print('compile_gate: weapon_pack_guards=staged sha256=' + receipt['sha256'] + ' layout=hcx_addons')
        yield {'extra_mods': extra_mods, 'server_mod': adapter,
               'server_extra_pbos': [guard_mod / 'addons' / weapon_pack_guards.PBO_NAME]}


def ship_config(tree, disposable):
    """Compile the HCX config the release ships, not the bare commit.

    Build 123 crashed at load on a duplicate member that only the release-time attachment
    scale injection created; the gate compiled the uninjected config and passed."""
    config = tree / 'mods/HollowCountryExpansionAI/config.cpp'
    if not config.is_file() or inventory_sizes.PACK_BEGIN in config.read_text():
        return
    if not disposable:
        print('compile_gate: attachment_scale=not_injected (in-place tree; pass --commit to compile the shipped config)')
        return
    # Same pinned generator invocation as tools/release/release.py build().
    result = subprocess.run([sys.executable, '-B', '-m', 'tools.package.inventory_sizes', '--inject', str(tree)],
                            cwd=tree, capture_output=True, text=True,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=300)
    if result.returncode:
        raise ValueError('attachment scale injection failed: ' + private(result.stderr.strip()[-400:]))
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    print('compile_gate: attachment_scale=injected overrides=' + str(receipt['overrides'])
          + ' sha256=' + receipt['sha256'])


def build_command(command, cwd):
    result = subprocess.run([str(arg) for arg in command], cwd=cwd, capture_output=True,
                            text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                            timeout=1800)
    if result.returncode:
        raise ValueError('animation build/verify failed: ' + Path(str(command[0])).name
                         + ' ' + private(result.stderr.strip()[-400:]))
    return result.stdout


def validate_staged_pbos(staged, guard_name=None):
    """Compare actual staged paths with the catalogue used by release signing."""
    expected = {f'@{mod}/addons/{name}.pbo'.casefold()
                for name, mod, _ in ship_inputs.signing_inputs(guard_name)}
    actual = {name.casefold() for name, path in staged.items() if path.is_file()}
    missing = sorted(expected - actual)
    if missing:
        raise ValueError('release PBOs not staged: ' + ', '.join(missing))
    if actual - expected:
        raise ValueError('unexpected staged PBOs: ' + ', '.join(sorted(actual - expected)))
    print('compile_gate: staged_pbos=' + str(len(actual)) + ' names=' + ','.join(sorted(actual)))


def stage_release_pbos(tree, package, inputs, addons, scratch):
    """Stage release layout once, then give the probe these exact package files."""
    base = scratch / '@HollowCountry/addons'
    base.mkdir(parents=True)
    shutil.copyfile(package, base / 'hollowcountry.pbo')
    anims = ship_inputs.build_anims(tree, addons, scratch, build_command)
    shutil.copyfile(anims, base / 'hollowcountryanims.pbo')
    server = scratch / '@HollowCountryExpansionAI/addons'
    server.mkdir(parents=True)
    adapter = server / 'hollowcountryexpansionai.pbo'
    if inputs.get('server_mod'):
        shutil.copyfile(inputs['server_mod'], adapter)
    else:
        adapter.write_bytes(pbo.pack(pbo.collect_addon(tree / 'mods/HollowCountryExpansionAI',
                                                      prefix='HollowCountryExpansionAI'),
                                     prefix='HollowCountryExpansionAI'))
    extras = []
    for source in inputs.get('server_extra_pbos', ()):
        target = server / source.name
        shutil.copyfile(source, target)
        extras.append(target)
    staged = {path.relative_to(scratch).as_posix(): path
              for path in scratch.glob('@*/addons/*.pbo')}
    guard_name = weapon_pack_guards.PBO_NAME if weapon_pack_guards.declared(
        tree / 'tools/setup/workshop_mods.json') else None
    validate_staged_pbos(staged, guard_name)
    return dict(inputs, server_mod=adapter, server_extra_pbos=extras,
                base_extra_pbos=[base / 'hollowcountryanims.pbo'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', type=Path, default=Path.cwd(), help='source checkout (default: current directory)')
    parser.add_argument('--commit', help='compile the exact tracked commit, discarding its temporary tree afterwards')
    parser.add_argument('--server-root', type=Path, help='complete isolated Linux-filesystem server copy')
    parser.add_argument('--prefix', type=Path, help='existing reusable isolated Wine prefix')
    parser.add_argument('--cache', type=Path, default=Path.home() / '.cache/hollow-country/compile-gate')
    parser.add_argument('--seconds', type=int, default=900,
                        help='Wine probe budget, 15..900 seconds (default 900; PASS requires Mission loaded)')
    parser.add_argument('--workshop', type=Path, default=weapon_pack_guards.WORKSHOP,
                        help='installed Workshop content root; compile guard and HCX when pack is installed')
    parser.add_argument('--addons', type=Path, default=ship_inputs.ADDONS,
                        help='installed DayZ/DayZServer Addons folder (read only; same as release)')
    parser.add_argument('--prepare-only', action='store_true', help='package inputs only; NEVER establishes compiler acceptance')
    args = parser.parse_args()
    if not args.prepare_only:
        args.server_root, args.prefix, reason = prerequisites(args.server_root, args.prefix)
        if reason:
            parser.error(reason)
    if not 15 <= args.seconds <= 900:
        parser.error('--seconds must be 15..900')
    started = time.monotonic()
    try:
        cache = args.cache.expanduser().resolve()
        probe.safe(cache)
        cache.mkdir(parents=True, exist_ok=True)
        with contextlib.ExitStack() as stack:
            tree = stack.enter_context(source_tree(args.tree.resolve(), args.commit, cache))
            ship_config(tree, bool(args.commit))
            inputs = stack.enter_context(compatibility_inputs(tree, args.workshop.expanduser().resolve(), cache))
            blob = pbo.pack(pbo.collect_addon(tree / 'mods/HollowCountry'))
            digest = hashlib.sha256(blob).hexdigest()
            package = cache / (digest + '.pbo')
            reused = package.is_file() and package.read_bytes() == blob
            if not reused:
                # Atomic cache publication also tolerates independent packers.
                with tempfile.NamedTemporaryFile(dir=cache, delete=False) as output:
                    temporary = Path(output.name)
                    try:
                        output.write(blob)
                        output.close()
                        os.replace(temporary, package)
                    finally:
                        temporary.unlink(missing_ok=True)
            print('compile_gate: pbo_sha256=' + digest + ' package_cache=' + ('hit' if reused else 'miss'))
            staging = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='ship-inputs-', dir=cache)))
            inputs = stage_release_pbos(tree, package, inputs, args.addons.expanduser().absolute(), staging)
            if args.prepare_only:
                print('compile_gate: PREPARED ONLY; native compile NOT RUN')
                return 0
            # Unique experiment: profiles, storage, mission inputs and logs are
            # never reused. Only the server install, Wine prefix and PBO persist.
            experiment = cache / ('run-' + str(time.time_ns()))
            report = probe.run(args.server_root.expanduser().resolve(), package, experiment,
                               args.prefix.expanduser().resolve(), seconds=args.seconds, **inputs)
            text, _, skipped = probe.collect_logs(experiment)
            modules, script_errors, script_skipped = script_summary(experiment)
            errors = [line for line in text.splitlines()
                      if COMPILE_FAILURE.search(line) or SCRIPT_ERROR.search(line)]
            if 'Mission' in modules:
                errors = [line for line in errors if not RUNTIME_JSON_ERROR.search(line)]
            for line in [line for line in errors if not SCRIPT_ERROR.search(line)][:5]:
                print('compile_gate: ' + private(line)[:1200])
            # An engine ErrorMessage (e.g. a config.cpp "Member already defined") writes a
            # dump and blocks on a dialog under Wine; the RPT never gets the line.
            dumps = sorted((experiment / 'profiles').glob('ErrorMessage_*.mdmp'))
            for dump in dumps[:2]:
                data = dump.read_bytes()[:probe.MAX_LOG_FILE]
                found = dict.fromkeys(m.decode(errors='replace') for m in re.findall(
                    rb'File [^\x00\r\n]{1,200}, line \d+:[^\x00\r\n]{1,200}', data))
                print('compile_gate: engine_error_message dump=' + dump.name + ' '
                      + (private(next(iter(found)))[:400] if found else 'text=unavailable'))
            # Conservatively reject cascade errors too, rather than risk hiding
            # a primary error with an overly broad cascade exemption.
            # Cached run-1795243948522642708, script_2026-11-21_01-52-29.log:76
            # records "Module: Mission; loaded 680x files". Later timeout runs
            # end at World (line 73), which cannot establish Mission compilation.
            # Require the observed Mission marker; this is still not boot acceptance.
            status_ok = report['status'] in {'initialized', 'timeout'}
            status = report['status']
            # The probe's shared classifier stops at any SCRIPT (E). Once Mission
            # loaded, a stop caused only by missing-data JSON reports is not a
            # compile failure; a crash or failed self-test still is.
            if (report['status'] == 'compiler-error' and 'Mission' in modules
                    and not re.search(r'\bENGINE\s*\(F\)\s*:\s*Crashed\b|Core native self-test FAILED'
                                      r'|\bFile [^\n]*\.(?:cpp|hpp|bin), line \d+:|Member already defined', text)):
                status_ok = True
                status = 'mission-loaded-runtime-json'
                print('compile_gate: probe stopped on runtime JSON report after Mission loaded')
            passed = ('World' in modules and 'Mission' in modules
                      and not script_errors and not errors and not dumps
                      and not skipped and not script_skipped and status_ok)
            if passed:
                print('compile_gate: Mission loaded with zero compile errors; runtime acceptance pending')
            elif 'Mission' not in modules:
                print('compile_gate: Mission load not observed; compile completion unproven')
            print('compile_gate: ' + ('PASS' if passed else 'FAIL') + ' status=' + status)
            print('compile_gate: logs=' + private(experiment))
            return 0 if passed else 1
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as error:
        print('compile_gate: FAIL ' + private(error), file=sys.stderr)
        return 1
    finally:
        print('compile_gate: wall_seconds=%.3f' % (time.monotonic() - started))


if __name__ == '__main__':
    raise SystemExit(main())
