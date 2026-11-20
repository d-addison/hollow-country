"""Check an install and observe a boot; starting requires explicit --start.

python3 -B -m tools.release.checkstart --bundle 'D:\\HollowCountryLocal\\friend-bundle-N'
Without --start, attach to the newest RPT (or --rpt); never launch a process.
With --start, require no server running, invoke start-server.bat, follow a NEW RPT.
Exit codes: 0 connect-enabled after settle; 2 install check failed; 3 compile;
4 crash/dump; 5 process gone; 6 stall; 7 ready=false; 8 interop unknown;
9 input/start/timeout error; 130 interrupted. No exit path stops the server.
"""
import argparse
import math
from pathlib import Path
import time

from tools.setup import winproc
from tools.release.rpt_summary import Summary, failure, filtered

CODES = {'compile_failed': 3, 'crashed': 4, 'process_gone': 5,
         'stalled': 6, 'not_ready': 7, 'interop_unknown': 8,
         'input_error': 9, 'timed_out': 9, 'connect_enabled': 0}


def psquote(value):
    return "'" + str(value).replace("'", "''") + "'"


def newest(profiles):
    return max(profiles.glob('*.RPT'), key=lambda p: p.stat().st_mtime_ns, default=None)


def dumps(profiles):
    # Metadata only; never open dumps or private profile files.
    result = {}
    for pattern in ('*.mdmp', '*.dmp', '*.crash', '*.MDMP', '*.DMP'):
        for path in profiles.glob(pattern):
            info = path.stat()
            result[path] = (info.st_mtime_ns, info.st_size)
    return result


def watch(args, before, old_dumps):
    began = last_growth = time.monotonic()
    connected_at = None
    rpt = args.rpt
    position = 0
    pending = b''
    discard = False
    identity = None
    observed_running = False
    while True:
        now = time.monotonic()
        if now - began >= args.timeout_seconds:
            return 'timed_out', rpt
        if any(old_dumps.get(p) != stamp for p, stamp in dumps(args.profiles).items()):
            return 'crashed', rpt
        if rpt is None:
            candidate = newest(args.profiles)
            if candidate and (not args.start or candidate not in before):
                rpt = candidate
        batch_outcome = None
        if rpt is not None:
            stat = rpt.stat()
            current_identity = (stat.st_dev, stat.st_ino)
            if identity is not None and (current_identity != identity or stat.st_size < position):
                return 'input_error', rpt
            identity = current_identity
            if stat.st_size > position:
                last_growth = now
                # Drain a bounded chunk per poll; skip oversized/partial lines.
                with rpt.open('rb') as stream:
                    stream.seek(position)
                    block = stream.read(1024 * 1024)
                    position = stream.tell()
                for part in block.splitlines(keepends=True):
                    pending += part
                    if len(pending) > 16384:
                        pending = b''
                        discard = True
                    if not part.endswith(b'\n'):
                        continue
                    if not discard:
                        line = pending.decode('utf-8', errors='replace')
                        verdict = failure(line)
                        if verdict and (batch_outcome is None or verdict == 'compile_failed'):
                            batch_outcome = verdict
                        if 'Player connect enabled' in line and connected_at is None:
                            connected_at = now
                    pending = b''
                    discard = False
            if batch_outcome:
                return batch_outcome, rpt
        state = winproc.process_state(args.image, **args.interop)
        if state == 'gone':
            if not args.start or observed_running or time.monotonic() - began >= 15:
                return 'process_gone', rpt
        elif state == 'running':
            observed_running = True
        if state == 'unknown':
            return 'interop_unknown', rpt
        now = time.monotonic()
        if now - last_growth >= args.stall_seconds:
            return 'stalled', rpt
        # Drain all bytes present before passing, including errors after connect.
        caught_up = rpt is not None and rpt.stat().st_size <= position
        if state == 'running' and connected_at is not None and caught_up and now - connected_at >= args.settle_minutes * 60:
            return 'connect_enabled', rpt
        time.sleep(args.poll_seconds if caught_up or rpt is None else 0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, help='Windows path to extracted friend bundle')
    parser.add_argument('--server-root', default=r'D:\HollowCountryLocal\friend-local-1', help='Windows path')
    parser.add_argument('--profiles', type=Path, default=Path('/mnt/d/HollowCountryLocal/friend-local-1/profiles'))
    parser.add_argument('--rpt', type=Path, help='attach to this existing RPT; incompatible with --start')
    parser.add_argument('--start', action='store_true', help='explicitly authorize start-server.bat')
    parser.add_argument('--image', default='DayZServer_x64.exe')
    parser.add_argument('--stall-seconds', type=float, default=180)
    parser.add_argument('--settle-minutes', type=float, default=0)
    parser.add_argument('--timeout-seconds', type=float, default=900, help='total watch deadline, including settle')
    parser.add_argument('--poll-seconds', type=float, default=5)
    parser.add_argument('--interop-attempts', type=int, default=3)
    parser.add_argument('--interop-timeout', type=float, default=30)
    parser.add_argument('--retry-seconds', type=float, default=2)
    parser.add_argument('--system32', type=Path, default=winproc.SYSTEM32)
    parser.add_argument('--interop-cwd', default='/mnt/c')
    args = parser.parse_args(argv)
    if args.start and args.rpt:
        parser.error('--rpt cannot be used with --start')
    for name in ('stall_seconds', 'timeout_seconds', 'poll_seconds', 'interop_timeout'):
        if not math.isfinite(getattr(args, name)) or getattr(args, name) <= 0:
            parser.error('time limits must be finite and positive')
    if not math.isfinite(args.settle_minutes) or args.settle_minutes < 0:
        parser.error('settle minutes must be finite and nonnegative')
    if not args.profiles.is_dir():
        parser.error('profiles directory unavailable')
    args.interop = dict(attempts=args.interop_attempts, timeout=args.interop_timeout,
                        retry_seconds=args.retry_seconds, system32=args.system32, cwd=args.interop_cwd)
    rpt = None
    try:
        # Use PowerShell argument quoting; no shell interpolation on Linux.
        check = ("$env:PYTHONDONTWRITEBYTECODE='1'; Set-Location -LiteralPath " + psquote(args.bundle)
                 + "; if (-not $?) { exit 2 }; & py -3 -m tools.setup.friend_install --bundle "
                 + psquote(args.bundle) + ' --server-root ' + psquote(args.server_root)
                 + ' --check; exit $LASTEXITCODE')
        result = winproc.run('powershell', [check], **args.interop)
        print(f'install_check_rc={result.returncode} attempts={result.attempts}', flush=True)
        for line in (result.stdout + '\n' + result.stderr).splitlines():
            safe = filtered(line)
            if safe:
                print(safe)
        if result.returncode:
            return 2
        old_dumps = dumps(args.profiles)
        before = set(args.profiles.glob('*.RPT'))
        if args.start:
            state = winproc.process_state(args.image, **args.interop)
            if state != 'gone':
                print('start refused: process state=' + state)
                return 8 if state == 'unknown' else 9
            # Emit an acknowledgement for a normally silent Start-Process.
            # Never retry this side effect: Windows may launch the server even
            # if its acknowledgement is lost. The operator can attach afterward.
            script = ("$ErrorActionPreference='Stop'; Start-Process -FilePath "
                      + psquote(args.server_root.rstrip('\\/') + '\\start-server.bat')
                      + ' -WorkingDirectory ' + psquote(args.server_root)
                      + " -WindowStyle Minimized; Write-Output 'HC launch acknowledged'")
            started = winproc.run('powershell', [script], **dict(args.interop, attempts=1))
            if started.returncode:
                print('start failed')
                return 9
        outcome, rpt = watch(args, before, old_dumps)
        if rpt is not None:
            summary = Summary(rpt)
            try:
                summary.scan().print()
                if summary.outcome in ('compile_failed', 'crashed', 'not_ready'):
                    # The full summary can see a failure beyond the tail chunk.
                    outcome = summary.outcome
            finally:
                summary.close()
        print('boot_verdict=' + outcome)
        return CODES.get(outcome, 9)
    except winproc.InteropError:
        print('boot_verdict=interop_unknown')
        return 8
    except (OSError, ValueError):
        print('boot_verdict=input_error')
        return 9
    except KeyboardInterrupt:
        print('observation interrupted; server state unchanged by observer')
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
