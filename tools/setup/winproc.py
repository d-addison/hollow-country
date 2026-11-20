"""Bounded WSL Windows interop. Empty tasklist output is UNKNOWN, never gone.

API: run('powershell', [script]); process_state('DayZServer_x64.exe').
CLI: python3 -B -m tools.setup.winproc query DayZServer_x64.exe
Only query is read-only; powershell/cmd execute the supplied command.
"""
import argparse
import csv
from dataclasses import dataclass
import io
import json
from pathlib import Path
import re
import subprocess
import time

SYSTEM32 = Path('/mnt/c/Windows/System32')
INTEROP = re.compile(r'UtilAcceptVsock|accept4 failed', re.I)


class InteropError(RuntimeError):
    """Windows result unavailable after bounded retries (no raw command/output)."""


@dataclass(frozen=True)
class Result:
    returncode: int
    stdout: str
    stderr: str
    attempts: int


def run(kind, args, *, attempts=3, timeout=30, retry_seconds=2,
        system32=SYSTEM32, cwd='/mnt/c'):
    """Retry only vsock/empty/timeout failures; retain real Windows exit codes.

    Commands with side effects must be idempotent: an empty response can mean
    that Windows executed the command but its response was lost.
    """
    if not 1 <= attempts <= 60 or not 0 < timeout <= 300 or not 0 <= retry_seconds <= 60:
        raise ValueError('invalid retry bounds')
    root = Path(system32)
    commands = {
        'powershell': [str(root / 'WindowsPowerShell/v1.0/powershell.exe'),
                       '-NoProfile', '-NonInteractive', '-Command'],
        'cmd': [str(root / 'cmd.exe'), '/d', '/s', '/c'],
        'tasklist': [str(root / 'tasklist.exe')],
    }
    if kind not in commands:
        raise ValueError('expected powershell, cmd or tasklist')
    for attempt in range(1, attempts + 1):
        try:
            completed = subprocess.run(commands[kind] + list(args), cwd=cwd,
                                       capture_output=True, timeout=timeout)
            out = completed.stdout.decode('utf-8', errors='replace').replace('\r', '')
            err = completed.stderr.decode('utf-8', errors='replace').replace('\r', '')
            if not INTEROP.search(out + err) and (out + err).strip():
                return Result(completed.returncode, out, err, attempt)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if attempt < attempts:
            time.sleep(retry_seconds)
    raise InteropError('Windows interop unavailable after bounded retries')


def process_state(image, **kwargs):
    """Return running/gone/unknown for an exact image name; never infer from empty."""
    if not re.fullmatch(r'[A-Za-z0-9_.-]+\.exe', image, re.I):
        raise ValueError('expected executable image name')
    try:
        result = run('tasklist', ['/FI', 'IMAGENAME eq ' + image, '/FO', 'CSV', '/NH'], **kwargs)
    except InteropError:
        return 'unknown'
    if result.returncode:
        return 'unknown'
    rows = list(csv.reader(io.StringIO(result.stdout)))
    if any(row and row[0].casefold() == image.casefold() for row in rows):
        return 'running'
    if result.stdout.strip().startswith('INFO: No tasks are running'):
        return 'gone'
    return 'unknown'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempts', type=int, default=3)
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--retry-seconds', type=float, default=2)
    parser.add_argument('--system32', type=Path, default=SYSTEM32)
    parser.add_argument('--cwd', default='/mnt/c')
    parser.add_argument('kind', choices=['query', 'powershell', 'cmd', 'tasklist'])
    parser.add_argument('args', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    options = dict(attempts=args.attempts, timeout=args.timeout,
                   retry_seconds=args.retry_seconds, system32=args.system32, cwd=args.cwd)
    try:
        if args.kind == 'query':
            if len(args.args) != 1:
                parser.error('query requires one image name')
            state = process_state(args.args[0], **options)
            print(json.dumps({'state': state}))
            return {'running': 0, 'gone': 1, 'unknown': 2}[state]
        result = run(args.kind, args.args, **options)
        # Reuse the strict release privacy filter; never echo raw Windows output.
        from tools.release.rpt_summary import filtered
        for line in (result.stdout + '\n' + result.stderr).splitlines():
            safe = filtered(line)
            if safe:
                print(safe)
        return result.returncode
    except (InteropError, ValueError):
        print('Windows interop unavailable or invalid arguments')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
