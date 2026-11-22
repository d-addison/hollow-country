"""Plan-first, disposable Windows DayZDiag server + exactly one client.

Run from WSL with python3 -B -m tools.setup.diag_session --tag NAME.
Only --launch starts processes. --refresh copies loose source only; no restart.
"""
import argparse
from contextlib import ExitStack
from tools.release.host_lock import host_lock, LockRefused
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil

from tools.package import pbo
from tools.release.rpt_summary import (CASCADE, COMPILE_MARKER, HC, SCRIPT_ERROR,
                                       filtered, lines)
from tools.setup import workshop_sync, winproc

REPO = Path(__file__).resolve().parents[2]
CLIENT = Path('/mnt/g/SteamLibrary/steamapps/common/DayZ')
SERVER = Path('/mnt/d/SteamLibrary/steamapps/common/DayZServer')
WORKSHOP = Path('/mnt/g/SteamLibrary/steamapps/workshop/content/221100')
RUNTIME_PARENT = Path('/mnt/d/HollowCountryLocal')
IMAGES = ('DayZ_x64.exe', 'DayZDiag_x64.exe', 'DayZServer_x64.exe',
          'DayZ_BE.exe', 'DayZServer.exe')
MISSION = 'dayzOffline.chernarusplus'
MARKER = 'diag-session.json'
ASSET_DIRS = ('Addons', 'dta', 'bliss', 'enoch', 'sakhal', 'nasdara',
              'MainMenu.ChernarusPlus', 'MainMenu.Enoch')
# Optional weapon packs that the retail compiler accepts but DayZDiag refuses
# (observed 2026-11-21: a body-less `override typename GetInputType() return X;` in a
# third-party optic action fails with "Missing function scope"). We never patch
# third-party code, so a Diag session may drop these optional packs; HollowCountry
# keeps them out of requiredAddons and its optional overlays are guarded.
DIAG_OPTIONAL = frozenset({'@TacticalFlava', '@SnafuWeapons'})
# A required dependency can fail Diag too (2026-11-21: Ambient Animals Seagull_Base.c(110)
# "Unmatched brackets", needed by the Expansion AI addon). --core-only then loads only the
# base addon, whose requiredAddons are vanilla, so Diag still checks every base script.
CORE_FOLDER = '@HollowCountry'
SOURCE_SUFFIXES = {'.c', '.cpp', '.xml', '.json', '.layout', '.edds', '.paa',
                   '.rvmat', '.p3d', '.ogg', '.wav', '.imageset', '.html', '.csv', '.txt'}


class Refused(ValueError):
    """Invalid or unsafe session input (messages contain no private paths)."""


def plain(path):
    """Refuse links/reparse points in a managed path and its ancestors."""
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or (part.exists() and
                getattr(part.lstat(), 'st_file_attributes', 0) & 0x400):
            raise Refused('linked/reparse path refused')
    return path


def windows(path):
    match = re.fullmatch(r'/mnt/([a-zA-Z])/(.+)', str(Path(path)))
    if not match or any(c in match[2] for c in '\r\n";'):
        raise Refused('expected a WSL drive path without command separators')
    return match[1].upper() + ':\\' + match[2].replace('/', '\\')


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def source_files(source):
    """Only runtime inputs; never traverse links or read key/private files."""
    result = {}
    pending = [plain(source)]
    while pending:
        directory = pending.pop()
        for path in sorted(directory.iterdir()):
            plain(path)
            if path.is_dir():
                if path.name not in {'.git', '__pycache__', 'keys'}:
                    pending.append(path)
            elif path.suffix.lower() in SOURCE_SUFFIXES:
                if not path.is_file() or path.stat().st_size > pbo.MAX_BYTES:
                    raise Refused('source file is not regular or exceeds size limit')
                result[path.relative_to(source).as_posix()] = path
    if 'config.cpp' not in result:
        raise Refused('own source addon config.cpp missing')
    return result


@dataclass
class Plan:
    runtime: Path
    repo: Path
    client: Path
    stock_mission: Path
    items: list
    sources: dict
    assets: list
    dlls: list
    port: int
    without: tuple = ()

    def mods(self, side):
        return [windows(self.runtime / item['folder']) if item['publish'] else
                windows(item['source']) for item in self.items if item['side'] == side]

    def arguments(self, server):
        shared = ['-filePatching', '-doLogs', '-noPause', '-mod=' + ';'.join(self.mods('client'))]
        profile = self.runtime / 'profiles' / ('server' if server else 'client')
        args = shared + ['-profiles=' + windows(profile), '-port=' + str(self.port)]
        if server:
            args += ['-server', '-ip=127.0.0.1', '-config=' + windows(self.runtime / 'serverDZ.cfg')]
            if self.mods('server'):
                args += ['-serverMod=' + ';'.join(self.mods('server'))]
        else:
            args += ['-connect=127.0.0.1', '-window']
        return args

    def launch_script(self):
        """One shot: never retry a process launch after an ambiguous interop result."""
        exe = windows(self.runtime / 'DayZDiag_x64.exe')
        script = ["$ErrorActionPreference='Stop'",
                  "$mutex=New-Object System.Threading.Mutex($false,'Local\\HC_DayZDiag_Launch'); "
                  "if (!$mutex.WaitOne(0)) { throw 'another diag launch is in progress' }; try {",
                  process_guard(),
                  "$root=" + quote(windows(self.runtime)),
                  # DrvFs does not reliably expose junction attributes to Python.
                  "$p=$root; while ($p) { if ((Get-Item -LiteralPath $p).Attributes -band "
                  "[IO.FileAttributes]::ReparsePoint) { throw 'runtime reparse point refused' }; "
                  "$p=Split-Path -Parent $p }"]
        for name in self.assets:
            script += ["New-Item -ItemType Junction -Path " + quote(windows(self.runtime / name)) +
                       ' -Target ' + quote(windows(self.client / name)) + ' | Out-Null']
        for server in (True, False):
            if not server:
                script += [
                    '$deadline=(Get-Date).AddSeconds(180)',
                    "do { if ($server.HasExited) { throw 'diag server exited before connect enabled' }; "
                    "$ready=@(Get-ChildItem -LiteralPath ($root+'\\profiles\\server') -Filter '*.RPT' | "
                    "Select-String -SimpleMatch 'Player connect enabled' -Quiet); "
                    "if ($ready -contains $true) { break }; Start-Sleep -Milliseconds 500 "
                    "} while ((Get-Date) -lt $deadline)",
                    "if (!($ready -contains $true)) { throw 'server readiness timeout; client not started' }"]
            args = ','.join(quote('"' + arg + '"') for arg in self.arguments(server))
            label = 'server' if server else 'client'
            script += [f"${label}=Start-Process -FilePath {quote(exe)} -WorkingDirectory $root "
                       f'-ArgumentList @({args}) -PassThru',
                       f"Write-Output 'HC diag {label} launch requested'"]
        script += ['} finally { $mutex.ReleaseMutex(); $mutex.Dispose() }']
        return ';\n'.join(script)


def process_guard():
    names = ','.join(quote(name) for name in IMAGES)
    return (f'$busy=@(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object '
            f'{{ $_.Name -in @({names}) }}); '
            "if ($busy.Count) { throw 'DayZ process already running' }")


def make_plan(tag, *, repo=REPO, client=CLIENT, server=SERVER, workshop=WORKSHOP,
              parent=RUNTIME_PARENT, port=2402, without=(), core_only=False):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,39}', tag) or re.search(r'\d{17}', tag):
        raise Refused('tag must be 1..40 letters/digits/underscore/hyphen; no identifiers')
    if not 1024 <= port <= 65531:
        raise Refused('port must be 1024..65531')
    runtime = plain(parent / ('diag-' + tag))
    client, server, workshop, repo = map(Path, (client, server, workshop, repo))
    # Validate printed command paths even in plan mode.
    for path in (runtime, client, server, workshop):
        windows(path)
    if not plain(client / 'DayZDiag_x64.exe').is_file():
        raise Refused('installed DayZDiag executable missing')
    stock = plain(server / 'mpmissions' / MISSION)
    if not (stock / 'init.c').is_file():
        raise Refused('installed stock Chernarus mission missing')
    without = tuple(sorted(set(without)))
    for folder in without:
        if folder not in DIAG_OPTIONAL:
            raise Refused('only optional weapon packs may be left out: ' + ', '.join(sorted(DIAG_OPTIONAL)))
    manifest = workshop_sync.load_manifest()
    items, sources = [], {}
    for row in manifest['mods']:
        item = dict(row)
        if item['folder'] in without or (core_only and item['folder'] != CORE_FOLDER):
            continue
        if item['publish']:
            prefix = item['folder'][1:]
            addon = repo / 'mods' / prefix
            sources[prefix] = source_files(addon)
        else:
            source = plain(workshop / item['id'])
            if not (source / 'addons').is_dir() and not (source / 'Addons').is_dir():
                raise Refused('Workshop dependency missing: ' + item['folder'])
            item['source'] = source
        items.append(item)
    assets = [name for name in ASSET_DIRS if (client / name).is_dir()]
    if 'Addons' not in assets or 'dta' not in assets:
        raise Refused('installed engine Addons/dta missing')
    dlls = [plain(path) for path in sorted(client.glob('*.dll'))]
    if core_only:
        if [item['folder'] for item in items] != [CORE_FOLDER]:
            raise Refused('core-only session needs the published base addon in the manifest')
        without = tuple(sorted(row['folder'] for row in manifest['mods'] if row['folder'] != CORE_FOLDER))
    return Plan(runtime, repo, client, stock, items, sources, assets, dlls, port, without)


def guard_idle(runtime):
    result = winproc.run('powershell', ["$ErrorActionPreference='Stop'; " + process_guard() +
                                      '; ' + path_guard(runtime) +
                                      "; Write-Output 'HC_DIAG_IDLE'"], attempts=1)
    if result.returncode or result.stdout.strip() != 'HC_DIAG_IDLE':
        raise Refused('DayZ already running or process observation unavailable')


def path_guard(runtime):
    return ('$p=' + quote(windows(runtime)) +
            '; while ($p) { if ((Test-Path -LiteralPath $p) -and '
            '((Get-Item -LiteralPath $p).Attributes -band [IO.FileAttributes]::ReparsePoint)) '
            "{ throw 'runtime reparse point refused' }; $p=Split-Path -Parent $p }")


def write_new(path, data):
    plain(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)


def stage(plan):
    """Fresh output only. Partial failures remain for inspection, never overwritten."""
    guard_idle(plan.runtime)
    plain(plan.runtime)
    plan.runtime.mkdir(parents=True, exist_ok=False)
    # dayz.gproj is the engine project file; without it Enfusion refuses to start (observed 2026-11-21).
    for name in ('DayZDiag_x64.exe', 'steam_appid.txt', 'dayz.gproj'):
        path = plain(plan.client / name)
        if not path.is_file():
            raise Refused('required installed engine file missing')
        shutil.copyfile(path, plan.runtime / name)
    for path in plan.dlls:
        shutil.copyfile(path, plan.runtime / path.name)
    # Never copy stock persistence, profiles, logs, keys or existing install snapshots.
    for path in sorted(plan.stock_mission.rglob('*')):
        rel = path.relative_to(plan.stock_mission)
        if any(part.lower().startswith('storage_') for part in rel.parts):
            continue
        plain(path)
        if path.is_file() and path.suffix.lower() in {'.c', '.xml', '.json', '.map'}:
            write_new(plan.runtime / 'mpmissions' / MISSION / rel, path.read_bytes())
    # DayZDiag's cfg validator requires instanceId (missing = silent 10 s
    # termination before Steam init); shardId is format-checked. maxPlayers=6
    # matches every cfg that reached Mission.
    config = ('hostname="HC isolated diag";\nmaxPlayers=6;\nBattlEye=0;\n'
              'instanceId=1;\nshardId="hcdia1";\nguaranteedUpdates=1;\ndisableVoN=1;\n'
              'verifySignatures=0;\nallowFilePatching=1;\nforceSameBuild=1;\n'
              'steamQueryPort=' + str(plan.port + 3) + ';\n'
              'class Missions { class HC { template="' + MISSION + '"; }; };\n')
    write_new(plan.runtime / 'serverDZ.cfg', config.encode())
    for side in ('server', 'client'):
        (plan.runtime / 'profiles' / side).mkdir(parents=True)
    from tools.setup.friend_bundle import repo_profile_sources
    for rel, source in repo_profile_sources().items():
        data = source if isinstance(source, bytes) else plain(source).read_bytes()
        write_new(plan.runtime / 'profiles/server' / rel, data)
    receipt = {'schema': 1, 'tag': plan.runtime.name, 'configs': {}, 'files': {},
               'without': list(plan.without)}
    for prefix, files in plan.sources.items():
        for rel, path in files.items():
            write_new(plan.runtime / prefix / rel, path.read_bytes())
        data = files['config.cpp'].read_bytes()
        receipt['configs'][prefix] = hashlib.sha256(data).hexdigest()
        receipt['files'][prefix] = sorted(files)
        write_new(plan.runtime / ('@' + prefix) / 'addons' / (prefix.lower() + '.pbo'),
                  pbo.pack({'config.cpp': data}, prefix=prefix))
    write_new(plan.runtime / MARKER, (json.dumps(receipt, indent=2) + '\n').encode())


def refresh(plan):
    """Synchronize loose runtime files; config changes require a fresh session tag."""
    root = plain(plan.runtime)
    marker = plain(root / MARKER)
    if marker.stat().st_nlink != 1:
        raise Refused('hard-linked session receipt refused')
    receipt = json.loads(marker.read_text())
    if receipt.get('schema') != 1 or receipt.get('tag') != root.name:
        raise Refused('not an owned diagnostic session')
    if set(receipt['configs']) != set(plan.sources):
        raise Refused('addon set changed; use a fresh tag')
    for prefix, files in plan.sources.items():
        digest = hashlib.sha256(files['config.cpp'].read_bytes()).hexdigest()
        if digest != receipt['configs'][prefix]:
            raise Refused('config.cpp changed; use a fresh tag')
        for rel in receipt['files'][prefix]:
            if Path(rel).is_absolute() or '..' in Path(rel).parts or '\\' in rel:
                raise Refused('invalid session receipt')
    check = winproc.run('powershell', ["$ErrorActionPreference='Stop'; " +
                        '; '.join(path_guard(root / prefix) +
                                  '; if (Get-ChildItem -LiteralPath ' + quote(windows(root / prefix)) +
                                  ' -Recurse -Force | Where-Object { $_.Attributes -band '
                                  '[IO.FileAttributes]::ReparsePoint }) '
                                  "{ throw 'linked source mirror refused' }"
                                  for prefix in plan.sources) +
                        "; Write-Output 'HC_DIAG_PATHS_OK'"], attempts=1)
    if check.returncode or check.stdout.strip() != 'HC_DIAG_PATHS_OK':
        raise Refused('runtime path observation unavailable')
    # Config validation completes before any source writes. No mission/profile synchronization.
    for prefix, files in plan.sources.items():
        for rel in set(receipt['files'][prefix]) - set(files):
            plain(root / prefix / rel).unlink(missing_ok=True)
        for rel, path in files.items():
            target = plain(root / prefix / rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.stat().st_nlink != 1:
                raise Refused('hard-linked runtime file refused')
            target.write_bytes(path.read_bytes())
        receipt['files'][prefix] = sorted(files)
    plain(root / MARKER).write_text(json.dumps(receipt, indent=2) + '\n')


def log_lines(path):
    for raw in lines(path):
        if HC.search(raw) or SCRIPT_ERROR.search(raw) or COMPILE_MARKER.search(raw) or CASCADE.search(raw):
            safe = filtered(raw)
            if safe:
                yield safe


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', default='dev')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--plan', action='store_true', help='default: print only, write nothing')
    mode.add_argument('--launch', action='store_true', help='stage fresh runtime and launch one server + one client')
    mode.add_argument('--refresh', action='store_true', help='refresh loose sources in an existing session')
    mode.add_argument('--log', type=Path, help='print only privacy-filtered HC/script error lines; no staging')
    parser.add_argument('--port', type=int, default=2402)
    parser.add_argument('--without', action='append', default=[], metavar='FOLDER',
                        help='leave out an optional weapon pack that DayZDiag cannot compile '
                             '(' + ', '.join(sorted(DIAG_OPTIONAL)) + ')')
    parser.add_argument('--core-only', action='store_true',
                        help='load only the base addon (no Workshop dependencies, no AI addon)')
    args = parser.parse_args(argv)
    lease = ExitStack()
    try:
        if args.launch or args.refresh:
            lease.enter_context(host_lock('diag_session'))
        if args.log:
            for line in log_lines(args.log):
                print(line)
            return 0
        plan = make_plan(args.tag, port=args.port, without=args.without, core_only=args.core_only)
        if plan.without:
            print('Diag session leaves out optional packs: ' + ', '.join(plan.without))
        if args.refresh:
            refresh(plan)
            print('Loose sources refreshed; reload scripts/reopen resources as appropriate.')
        elif args.launch:
            stage(plan)
            # Never retry: a lost response can follow a successful launch.
            result = winproc.run('powershell', [plan.launch_script()], attempts=1, timeout=240)
            if result.returncode:
                raise Refused('Windows launch failed; inspect isolated profiles; no automatic retry/cleanup')
            print('Launch requested for one server and one client; runtime acceptance pending.')
        else:
            if plan.runtime.exists():
                raise Refused('session tag already exists; choose a fresh tag (or --refresh)')
            print('PLAN ONLY: fresh runtime ' + windows(plan.runtime))
            print('Copy installed Diag executable/DLLs; junction engine assets; Workshop dependencies read-only.')
            print('Stage stock mission + repo profile defaults; mirror repo addon sources at PBO prefixes.')
            print('Create config-only bootstrap PBOs; source scripts/layout/data remain unpacked.')
            print('Native source resolution, boot and debugger attachment remain UNVERIFIED.')
            print(plan.launch_script())
        return 0
    except LockRefused as error:
        print(str(error))
        return 2
    except Refused as error:
        print('Diag session refused: ' + str(error))
        return 2
    except (OSError, ValueError, KeyError, TypeError, workshop_sync.SyncError, winproc.InteropError):
        # Never echo exception contents: OS/interop errors may contain account paths or command lines.
        print('Diag session refused: missing/unsafe input, existing runtime, active DayZ, or unavailable Windows interop. '
              'Check prerequisites in docs/tools/DAYZDIAG.md; partial runtimes are preserved.')
        return 2

    finally:
        lease.close()


if __name__ == '__main__':
    raise SystemExit(main())
