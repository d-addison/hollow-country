"""External Blender 5.2 runner; never imports bpy or launches during selftest.

Set HC_BLENDER or pass config={'blender': executable}. WSL-mounted .exe files
use winproc (one attempt: builds are not replayed). Raw logs are returned to the
caller privately, never printed by CLI. Recipe script verifies Blender 5.2.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from tools.assets import ops_runner
from tools.assets.provenance import ROOT, load_json, reject_worker_authority

BUILD_ROOT = ROOT / 'build'
SCRIPT = Path(__file__).with_name('blender_ops_script.py')
MAX_OUTPUT = 32 * 1024 * 1024


class BlenderRefusal(RuntimeError):
    """Stable public reason; logs are private attributes, excluded from str()."""

    def __init__(self, reason, *, stdout='', stderr=''):
        super().__init__(reason)
        self.stdout = (stdout.decode('utf-8', errors='replace') if isinstance(stdout, bytes) else stdout)[-65536:]
        self.stderr = (stderr.decode('utf-8', errors='replace') if isinstance(stderr, bytes) else stderr)[-65536:]


@dataclass(frozen=True)
class Result:
    mesh: dict
    renders: dict[str, bytes]
    stdout: str
    stderr: str


def build_directory(path):
    """Resolve before writing; outputs must stay inside the ignored build root."""
    path = Path(path).resolve()
    root = BUILD_ROOT.resolve()
    # Refuse a redirected build root too.
    if root != ROOT / 'build' or path == root or root not in path.parents:
        raise BlenderRefusal('output.outside_build')
    path.mkdir(parents=True, exist_ok=True)
    return path


def locate(config=None, *, environ=None):
    env = os.environ if environ is None else environ
    candidate = env.get('HC_BLENDER') or (config or {}).get('blender') or 'blender'
    if not isinstance(candidate, str) or not candidate or '\x00' in candidate:
        raise BlenderRefusal('blender.configuration_invalid')
    found = shutil.which(candidate)
    if not found and Path(candidate).is_file():
        found = candidate
    if not found:
        raise BlenderRefusal('blender.not_found: set HC_BLENDER or config.blender')
    return Path(found).resolve()


def _windows_path(path):
    try:
        result = subprocess.run(['wslpath', '-w', str(path)], capture_output=True,
                                text=True, timeout=5, check=True)
        value = result.stdout.strip()
        if not value or '\n' in value or '\r' in value:
            raise ValueError
        return value
    except (OSError, ValueError, subprocess.SubprocessError):
        raise BlenderRefusal('blender.windows_path_unavailable') from None


def _ps(value):
    return "'" + value.replace("'", "''") + "'"


def _execute(executable, script, arguments, directory, timeout):
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    for key in ('BLENDER_USER_CONFIG', 'BLENDER_USER_SCRIPTS', 'BLENDER_USER_EXTENSIONS'):
        env[key] = str(directory / key.lower())
    flags = ['-b', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1', '-P']
    try:
        if executable.suffix.lower() == '.exe' and os.name != 'nt':
            from tools.setup import winproc
            # Windows cannot consume POSIX paths. Convert all file arguments.
            converted = list(arguments)
            for option in ('--recipe', '--output'):
                index = converted.index(option) + 1
                converted[index] = _windows_path(converted[index])
            commandline = subprocess.list2cmdline(flags + [_windows_path(script), '--'] + converted)
            setup = ';'.join('$env:' + k + '=' + _ps(_windows_path(directory / k.lower()))
                             for k in ('BLENDER_USER_CONFIG', 'BLENDER_USER_SCRIPTS',
                                       'BLENDER_USER_EXTENSIONS'))
            command = (
                "$ErrorActionPreference='Stop';" + setup + ';'
                "$env:PYTHONPATH=$null;$env:PYTHONHOME=$null;"
                '$s=New-Object System.Diagnostics.ProcessStartInfo;'
                '$s.FileName=' + _ps(_windows_path(executable)) + ';'
                '$s.Arguments=' + _ps(commandline) + ';'
                '$s.WorkingDirectory=' + _ps(_windows_path(directory)) + ';'
                '$s.UseShellExecute=$false;$s.RedirectStandardOutput=$true;'
                '$s.RedirectStandardError=$true;$p=New-Object System.Diagnostics.Process;'
                '$p.StartInfo=$s;[void]$p.Start();'
                '$o=$p.StandardOutput.ReadToEndAsync();$e=$p.StandardError.ReadToEndAsync();'
                f'if(-not $p.WaitForExit({int(timeout * 1000)}))'
                '{$p.Kill();$p.WaitForExit();exit 124};'
                '$p.WaitForExit();[Console]::Out.Write($o.Result);'
                '[Console]::Error.Write($e.Result);exit $p.ExitCode')
            result = winproc.run('powershell', [command], attempts=1, timeout=timeout + 10)
        else:
            result = subprocess.run([str(executable), *flags, str(script), '--', *arguments],
                                    cwd=directory, env=env, capture_output=True,
                                    text=True, errors='replace', timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise BlenderRefusal('blender.timeout', stdout=exc.stdout or '', stderr=exc.stderr or '') from None
    except (OSError, RuntimeError):
        raise BlenderRefusal('blender.launch_failed') from None
    if result.returncode == 124:
        raise BlenderRefusal('blender.timeout')
    if result.returncode:
        reason = ('blender.version_requires_5_2' if 'blender.version_requires_5_2' in result.stderr
                  else 'blender.failed')
        raise BlenderRefusal(reason, stdout=result.stdout, stderr=result.stderr)
    return result


def build(recipe, *, config=None, timeout=120, render=False):
    """Return validated neutral JSON and optional six TGA views, in memory.

    No output from the child is licence authority. Parent must retain provenance.v2
    separately and check it at admission. Temp files are removed on all paths.
    """
    recipe = ops_runner.validate(recipe)
    if type(timeout) not in (int, float) or not 1 <= timeout <= 280:
        raise BlenderRefusal('blender.timeout_invalid')
    executable = locate(config)
    scratch_root = build_directory(BUILD_ROOT / 'asset-tmp')
    with tempfile.TemporaryDirectory(prefix='blender-', dir=scratch_root) as temp:
        directory = Path(temp)
        recipe_path, output_path = directory / 'recipe.json', directory / 'mesh.json'
        recipe_path.write_text(json.dumps(recipe, sort_keys=True), encoding='utf-8')
        # Copy only our script and validator dependencies; repo is never on child sys.path.
        # Validation happens in the parent; the script also validates with this package.
        package = directory / 'tools' / 'assets'
        package.mkdir(parents=True)
        (directory / 'tools' / '__init__.py').touch()
        (package / '__init__.py').touch()
        for filename in ('ops_runner.py', 'provenance.py', 'mlod.py'):
            shutil.copyfile(SCRIPT.with_name(filename), package / filename)
        script = directory / SCRIPT.name
        shutil.copyfile(SCRIPT, script)
        result = _execute(executable, script, ops_runner.script_arguments(
            recipe_path, output_path, render=render), directory, timeout)
        def read(path):
            if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_OUTPUT:
                raise BlenderRefusal('blender.output_invalid')
            return path.read_bytes()
        try:
            mesh = load_json(read(output_path))
            reject_worker_authority(mesh)
            if (not isinstance(mesh, dict) or mesh.get('schema') != 'neutral.v1'
                    or set(mesh) != {'schema', 'vertices', 'faces', 'selections', 'points', 'proxies'}):
                raise BlenderRefusal('blender.mesh_invalid')
            renders = {v: read(directory / (v + '.tga')) for v in
                       ('front', 'back', 'left', 'right', 'top', 'bottom')} if render else {}
        except (OSError, ValueError):
            raise BlenderRefusal('blender.output_invalid') from None
        return Result(mesh, renders, result.stdout, result.stderr)


def selftest():
    try:
        locate({'blender': 'hc-deliberately-absent-blender'}, environ={})
    except BlenderRefusal:
        return
    raise AssertionError('missing executable admitted')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selftest', action='store_true', required=True)
    parser.parse_args()
    selftest()
    print('{"valid": true}')
