"""Read-only audit command recorder; all temporary writes stay beside this file."""
import os
from pathlib import Path
import shlex
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
tmp = HERE / 'tmp'
tmp.mkdir(exist_ok=True)
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(tmp))
command = sys.argv[1:]
result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
with (HERE / 'COMMANDS.log').open('a') as log:
    log.write('$ PYTHONDONTWRITEBYTECODE=1 TMPDIR=' + str(tmp) + ' ' + shlex.join(command) + '\n')
    log.write(result.stdout)
    log.write('\n[exit=' + str(result.returncode) + ']\n\n')
print(result.stdout, end='')
print('[exit=' + str(result.returncode) + ']')
raise SystemExit(result.returncode)
