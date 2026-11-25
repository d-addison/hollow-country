"""Validate authored configs with CfgConvert; never replace packaged source.

Exit 0: converted (or no inputs), 1: failed, 3: unavailable/skipped.
"""
import argparse
from pathlib import Path
import re
import subprocess
import time

from tools.release.rpt_summary import filtered
from tools.setup import winproc

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TOOL = Path('/mnt/d/SteamLibrary/steamapps/common/DayZ Tools/Bin/CfgConvert/CfgConvert.exe')
SKIPPED = 3
MARKER = 'HC_CFG_RESULT='
STARTED = 'HC_CFG_STARTED'
ERROR = re.compile(r'\b(?:error|cannot|failed|fatal)\b', re.I)


def discover(root, paths=None):
    """Headers are compiled via their owning addon, never as standalone configs.

    Metadata mod.cpp/meta.cpp are outside addon payloads. Any changed file in an
    addon rechecks its configs, including shared headers and include dependencies.
    """
    configs = sorted(p for p in (root / 'mods').glob('**/*')
                     if p.is_file() and p.name in {'config.cpp', 'model.cfg'})
    if paths is None or any(not p.startswith('mods/') for p in paths):
        return configs
    addons = {Path(p).parts[1] for p in paths if len(Path(p).parts) > 2}
    return [p for p in configs if p.relative_to(root).parts[1] in addons]


def windows_path(path):
    try:
        result = subprocess.run(['wslpath', '-w', str(path.resolve())], capture_output=True,
                                text=True, timeout=10, check=True)
    except subprocess.TimeoutExpired as error:
        raise winproc.InteropError('wslpath timed out before CfgConvert could start') from error
    except subprocess.CalledProcessError as error:
        raise winproc.InteropError('wslpath failed with exit %d before CfgConvert could start'
                                   % error.returncode) from error
    if not result.stdout.strip():
        raise winproc.InteropError('wslpath returned no Windows path before CfgConvert could start')
    return result.stdout.strip()


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def run_converter_interop(script):
    """Retry only an explicit connection refusal before PowerShell starts.

    winproc.run folds empty replies, timeouts and vsock refusals into one error.
    Here those cases must stay distinct: lost replies/timeouts may have launched
    CfgConvert, so replaying them could hide a real refusal or leave two processes.
    """
    command = [str(winproc.SYSTEM32 / 'WindowsPowerShell/v1.0/powershell.exe'),
               '-NoProfile', '-NonInteractive', '-Command', script]
    for attempt in range(2):
        try:
            result = subprocess.run(command, cwd='/mnt/c', capture_output=True, timeout=60)
        except subprocess.TimeoutExpired as error:
            raise ValueError('Windows interop timed out; converter execution state unknown (no retry)') from error
        out = result.stdout.decode('utf-8', errors='replace').replace('\r', '')
        err = result.stderr.decode('utf-8', errors='replace').replace('\r', '')
        lines = [line for line in (out + '\n' + err).splitlines() if line.strip()]
        if (lines and STARTED not in out + err and MARKER not in out + err
                and all(winproc.INTEROP.search(line) for line in lines)):
            if attempt == 0:
                print('cfgconvert_check: retrying Windows interop after explicit vsock connection failure (1/1)')
                time.sleep(2)
                continue
            raise winproc.InteropError('explicit vsock connection failure after one retry; PowerShell did not start')
        if not lines:
            raise winproc.InteropError('empty Windows interop reply; execution state unknown (no retry)')
        return winproc.Result(result.returncode, out, err, attempt + 1)


def convert(source, tool):
    """Windows TEMP owns the disposable output; source includes stay in place.

    Stage the addon locally: CfgConvert silently ignores WSL UNC inputs.
    RAP header plus exit code guard against silent failures. PowerShell emits an
    explicit receipt even when the native tool writes no console output.
    """
    addon = source.parent
    while addon.parent.name != 'mods' and addon.parent != addon:
        addon = addon.parent
    if addon.parent.name != 'mods':
        raise ValueError('config must belong to mods/<addon>')
    src, exe = windows_path(addon), windows_path(tool)
    relative = (Path(addon.name) / source.relative_to(addon)).as_posix().replace('/', '\\')
    script = (
        f"$ErrorActionPreference='Stop'; Write-Output '{STARTED}'; $scratch=Join-Path $env:TEMP "
        "('hc-cfg-'+[Guid]::NewGuid()); $p=$null; try { "
        "New-Item -ItemType Directory -Path $scratch | Out-Null; "
        f"Copy-Item -LiteralPath {quote(src)} -Destination $scratch -Recurse; "
        f"$local=Join-Path $scratch {quote(relative)}; "
        "$out=Join-Path $scratch 'checked.bin'; "
        "$stdout=Join-Path $scratch 'stdout.txt'; $stderr=Join-Path $scratch 'stderr.txt'; "
        # Start-Process receives a Windows command line; quote each filename.
        "$cli='-bin -dst \"'+$out+'\" \"'+$local+'\"'; "
        f"$p=Start-Process -FilePath {quote(exe)} -ArgumentList $cli "
        "-PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr; "
        "$handle=$p.Handle; $rc=124; if ($p.WaitForExit(30000)) { $p.WaitForExit(); $rc=$p.ExitCode } "
        "else { Write-Output 'CfgConvert failed: timeout (process left running, not killed)' }; "
        "Get-Content -LiteralPath $stdout,$stderr -ErrorAction SilentlyContinue; "
        "$valid=$false; if (Test-Path -LiteralPath $out) { "
        "$b=[IO.File]::ReadAllBytes($out); $valid=($b.Length -gt 4 -and "
        "$b[0] -eq 0 -and $b[1] -eq 114 -and $b[2] -eq 97 -and $b[3] -eq 80) }; "
        f"Write-Output ('{MARKER}'+$rc+':'+$valid) "
        # Never force-kill: a stalled converter is reported as a failure and its scratch is kept.
        "} finally { if (!$p -or $p.HasExited) { "
        "Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction SilentlyContinue } }"
    )
    result = run_converter_interop(script)
    raw = result.stdout + '\n' + result.stderr
    receipts = re.findall(re.escape(MARKER) + r'(-?\d+):(True|False)', raw)
    ok = (result.returncode == 0 and receipts == [('0', 'True')]
          and not ERROR.search(raw))
    return ok, raw.replace(src, addon.as_posix())


def diagnostics(raw, source, root):
    label = source.relative_to(root).as_posix()
    result = []
    for line in raw.splitlines():
        if MARKER in line or line.strip() == STARTED or not line.strip():
            continue
        safe = filtered(line.replace(str(root) + '/', ''))
        if safe is None:
            safe = '[diagnostic removed by privacy filter]'
        if safe:
            match = re.search(r'\bline\s+(\d+)|\((\d+)\)|:(\d+)(?::|\s)', line, re.I)
            number = next((g for g in match.groups() if g), '1') if match else '1'
            result.append(f'{label}:{number}: {safe}')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='*', help='changed repository-relative paths (owning addons checked)')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--tool', type=Path, default=DEFAULT_TOOL)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    configs = discover(root, args.paths or None)
    if not configs:
        print('cfgconvert_check: no configs selected')
        return 0
    if not args.tool.is_file():
        print('skipped: CfgConvert executable not found (--tool or default installation)')
        return SKIPPED
    failed = 0
    for source in configs:
        try:
            ok, raw = convert(source, args.tool)
        except winproc.InteropError as error:
            print('skipped: CfgConvert unavailable: ' + str(error))
            return 1 if failed else SKIPPED
        except (OSError, subprocess.SubprocessError) as error:
            # wslpath runs before PowerShell; report the actual failure category.
            print('skipped: CfgConvert path/interop launch failed (' + type(error).__name__
                  + ', errno=' + str(getattr(error, 'errno', None)) + ')')
            return 1 if failed else SKIPPED
        except ValueError as error:
            print('cfgconvert_check: failed: ' + str(error))
            return 1
        for line in diagnostics(raw, source, root):
            print(line)
        if not ok:
            failed += 1
            print(f'{source.relative_to(root).as_posix()}:1: CfgConvert failed or RAP output missing')
    print(f'cfgconvert_check: configs={len(configs)} failed={failed}; packaged sources unchanged')
    return int(bool(failed))


if __name__ == '__main__':
    raise SystemExit(main())
