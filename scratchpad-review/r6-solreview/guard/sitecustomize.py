"""Read-only review constraints inherited by unittest child Python processes."""
import os
import sys
import unittest
from pathlib import Path

_ALLOWED = Path(__file__).resolve().parents[1]
_READ_GIT = {'ls-files', 'diff', 'show', 'rev-parse', 'status', 'log', 'check-ignore'}

def audit(event, args):
    if event == 'subprocess.Popen':
        executable, command, _cwd, _env = args
        name = Path(os.fsdecode(executable)).name.lower()
        if name in {'wine', 'wine64', 'dayzserver', 'dayzserver_x64.exe', 'dayzdiag_x64.exe'}:
            raise unittest.SkipTest('read-only review forbids DayZ/Wine')
        if name == 'git':
            parts = list(command) if not isinstance(command, str) else command.split()
            i = 1
            while i < len(parts) and parts[i] in ('-C', '-c'):
                i += 2
            if i >= len(parts) or parts[i] not in _READ_GIT:
                raise unittest.SkipTest('read-only review forbids mutating git, including synthetic fixture repositories')
    if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
        raise unittest.SkipTest('read-only review forbids network')
    if event == 'open':
        path, mode, flags = args
        if not isinstance(path, (str, bytes, os.PathLike)):
            return
        writes = (mode is not None and any(x in mode for x in 'wax+')) or (flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writes:
            resolved = Path(os.fsdecode(path)).resolve()
            if resolved != _ALLOWED and _ALLOWED not in resolved.parents:
                if str(resolved) != '/dev/null':
                    raise RuntimeError('review confinement rejected file write outside scratch directory')
sys.addaudithook(audit)
