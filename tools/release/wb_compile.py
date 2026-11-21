"""Guarded experimental Workbench script validation (WSL -> Windows).

A plugin receipt or zero exit alone NEVER passes. Native validation completion
must also be captured. This route has not yet been qualified against DayZ 1.30.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from tools.release import ship_inputs
from tools.release.compile_gate import source_tree
from tools.release.rpt_summary import filtered
from tools.setup import winproc

REPO = Path(__file__).resolve().parents[2]
WORKBENCH = Path('/mnt/d/SteamLibrary/steamapps/common/DayZ Tools/Bin/Workbench')
NATIVE = Path.home() / '.cache/hollow-country/native-scripts/scripts-1.30.164289'
MODULES = ('1_Core', '2_GameLib', '3_Game', '4_World', '5_Mission')
ERROR = re.compile(r"Can't compile|Cannot compile|SCRIPT\s*\(E\)|Compile error|"
                   r'Script validation failed|Failed to load .*script', re.I)
LOCATION = re.compile(r'(?P<file>[^\s"\'<>]*?\.c)(?:\((?P<paren>\d+)\)|:(?P<colon>\d+))', re.I)
SUCCESS = 'Script validation successful.'
RECEIPT = '[HC CompileCheck] action_returned'
MAX_LOG = 16 * 1024 * 1024
REQUIRED_SCRIPT_INPUTS = (('hollowcountry', 'HollowCountry'),
                         ('hollowcountryexpansionai', 'HollowCountryExpansionAI'))


def private(value):
    """Drop identity-bearing messages; preserve an error verdict independently."""
    value = str(value).replace(str(Path.home()), '~')
    value = re.sub(r'(?i)(?:[a-z]:[\\/]|/mnt/[a-z]/)users[\\/][^\\/\r\n]+', '~', value)
    value = re.sub(r'(?i)/(?:home|Users)/[^/\r\n]+', '~', value)
    return filtered(value) or '<private diagnostic>'


def diagnostics(text):
    """Inspect raw errors first. Engine locations may follow the error header."""
    lines = text.splitlines()
    found = []
    for index, line in enumerate(lines):
        if not ERROR.search(line):
            continue
        context = '\n'.join(private(item) for item in lines[index:index + 4])
        location = LOCATION.search(context)
        found.append({'file': private(location['file']) if location else None,
                      'line': int(location['paren'] or location['colon']) if location else None,
                      'message': private(line)[:2000]})
    return found


def verdict(text, returncode, timed_out=False, truncated=False):
    errors = diagnostics(text)
    if errors:
        status = 'compile_failed'
    elif timed_out:
        status = 'timeout'
    elif truncated:
        status = 'incomplete_logs'
    elif returncode != 0:
        status = 'tool_failed'
    elif SUCCESS not in text or RECEIPT not in text:
        status = 'unverified'
    else:
        status = 'passed'
    return {'status': status, 'errors': errors, 'tool_exit': returncode,
            'native_validation_completed': SUCCESS in text,
            'plugin_returned': RECEIPT in text, 'route_qualified': False}


def windows_path(path):
    result = subprocess.run(['wslpath', '-w', str(Path(path).absolute())],
                            capture_output=True, text=True, timeout=10, check=True)
    return result.stdout.strip()


def linux_path(path):
    result = subprocess.run(['wslpath', '-u', path], capture_output=True,
                            text=True, timeout=10, check=True)
    return Path(result.stdout.strip())


def quote_ps(value):
    return "'" + str(value).replace("'", "''") + "'"


def copy_scripts(source, destination):
    """Stage script sources only; refuse links, never copy keys/assets/profiles."""
    count = 0
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError('symlink in script input')
        if path.is_file() and path.suffix.lower() == '.c':
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            count += 1
    return count


def stage(tree, native, workbench, scratch):
    """Select authored mods through the same ship catalogue as compile_gate."""
    catalogue = {(stem, mod) for stem, mod, _ in ship_inputs.signing_inputs()}
    selected = []
    for entry in REQUIRED_SCRIPT_INPUTS:
        stem, mod = entry
        if entry not in catalogue:
            raise ValueError('required script addon absent from ship catalogue: ' + stem)
        if not (tree / 'mods' / mod / 'scripts').is_dir():
            raise ValueError('required script directory absent: ' + mod)
        selected.append(mod)
    counts = {}
    for module in MODULES:
        root = native / module
        if not root.is_dir():
            raise ValueError('native module absent: ' + module)
        counts['native/' + module] = copy_scripts(root, scratch / 'scripts' / module)
        if not counts['native/' + module]:
            raise ValueError('empty native module: ' + module)
    editor = native / 'editor/Workbench'
    if not editor.is_dir():
        raise ValueError('native Workbench scripts absent')
    copy_scripts(editor, scratch / 'scripts/editor/Workbench')
    plugin = tree / 'tools/workbench/HC_CompileCheck.c'
    target = scratch / 'scripts/editor/plugins/HC_CompileCheck.c'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(plugin, target)
    for mod in selected:
        counts[mod] = copy_scripts(tree / 'mods' / mod / 'scripts', scratch / mod / 'scripts')
        if not counts[mod]:
            raise ValueError('empty required script input: ' + mod)
    template = (workbench / 'dayz.gproj').read_text()
    # Modify only the observed installed Paths blocks and root mount, preserving
    # native module names, order and entry points verbatim.
    for module in MODULES:
        original = '"scripts/' + module + '"'
        if template.count(original) != 1:
            raise ValueError('installed gproj module shape changed: ' + module)
        paths = [original] + ['"' + mod + '/scripts/' + module + '"'
                              for mod in selected if (scratch / mod / 'scripts' / module).is_dir()]
        template = template.replace(original, '\n      '.join(paths))
    if template.count('Directory "./"') != 1:
        raise ValueError('installed gproj root shape changed')
    template = template.replace('Directory "./"',
                                'Directory "' + windows_path(scratch).replace('\\', '/') + '"')
    (scratch / 'hc_compile.gproj').write_text(template)
    return counts


def controller(executable, scratch, seconds, action):
    """PowerShell owns the process handle through timeout and cleanup.

    No retries: a lost interop response must never launch a second process.
    A named mutex serializes cooperating drivers; a second process query inside
    the lock covers the interval between the Python preflight and Start-Process.
    """
    args = ['-gproj=' + windows_path(scratch / 'hc_compile.gproj'),
            '-wbmodule=ScriptEditor', '-plugin=HC_CompileCheck',
            '-hcCompileAction=' + action]
    # Start-Process joins ArgumentList without quoting; explicitly quote each arg.
    if any('"' in arg or '\n' in arg or '\r' in arg for arg in args):
        raise ValueError('unsafe Windows argument')
    argument_list = ','.join(quote_ps('"' + arg + '"') for arg in args)
    return f"""
$ErrorActionPreference = 'Stop'
$mutex = New-Object System.Threading.Mutex($false, 'Local\\HollowCountryWorkbenchCompile')
$locked = $false
$owned = $null
$expired = $false
$cleanupConfirmed = $false
$exitCode = $null
try {{
    $locked = $mutex.WaitOne(0)
    if (!$locked) {{ throw 'Workbench compile controller busy' }}
    if (Get-Process -Name WorkbenchApp -ErrorAction SilentlyContinue) {{
        throw 'Workbench already running'
    }}
    $owned = Start-Process -FilePath {quote_ps(windows_path(executable))} -WorkingDirectory {quote_ps(windows_path(executable.parent))} -ArgumentList @({argument_list}) -RedirectStandardOutput {quote_ps(windows_path(scratch / 'stdout.log'))} -RedirectStandardError {quote_ps(windows_path(scratch / 'stderr.log'))} -PassThru
    $expired = !$owned.WaitForExit({int(seconds * 1000)})
}} finally {{
    if ($null -ne $owned) {{
        if (!$owned.HasExited) {{
            try {{
                [void]$owned.CloseMainWindow()
                [void]$owned.WaitForExit(30000)
            }} catch {{
                # A refused shutdown is not permission to terminate the process.
            }}
        }}
        $owned.Refresh()
        $cleanupConfirmed = $owned.HasExited
        if ($cleanupConfirmed) {{ $exitCode = $owned.ExitCode }}
        $owned.Dispose()
    }}
    if ($locked) {{ $mutex.ReleaseMutex() }}
    $mutex.Dispose()
}}
@{{exit_code=$exitCode; timed_out=$expired; cleanup_confirmed=$cleanupConfirmed}} | ConvertTo-Json -Compress
"""


def collect_logs(scratch):
    texts, total, truncated = [], 0, False
    for path in sorted(scratch.rglob('*')):
        if path.suffix.lower() not in ('.log', '.rpt') or path.is_symlink() or not path.is_file():
            continue
        with path.open('rb') as stream:
            data = stream.read(MAX_LOG - total + 1)
        if len(data) > MAX_LOG - total:
            truncated = True
            break
        total += len(data)
        texts.append(data.decode('utf-8', errors='replace'))
    return '\n'.join(texts), truncated


def run(args):
    state = winproc.process_state('WorkbenchApp.exe', attempts=1, timeout=10)
    if state != 'gone':
        return {'status': 'blocked', 'reason': 'Workbench process state: ' + state}, 2
    if not (args.workbench / 'WorkbenchApp.exe').is_file():
        raise ValueError('Workbench executable absent')
    # TEMP is queried privately; raw Windows output is never printed.
    result = winproc.run('powershell', ['[Console]::Write($env:TEMP)'], attempts=1, timeout=10)
    if result.returncode or not re.fullmatch(r'[A-Za-z]:\\[^\r\n]+', result.stdout.strip()):
        raise ValueError('Windows TEMP unavailable')
    temp_root = linux_path(result.stdout.strip())
    scratch = Path(tempfile.mkdtemp(prefix='hc-wbcompile-', dir=temp_root))
    cleanup = True
    try:
        with source_tree(args.tree.resolve(), args.commit, scratch) as tree:
            counts = stage(tree, args.native_scripts, args.workbench, scratch)
        script = controller(args.workbench / 'WorkbenchApp.exe', scratch, args.seconds, args.action_path)
        # Run directly, once. winproc's retry helper is unsuitable for launching.
        try:
            process = subprocess.Popen(
                [str(winproc.SYSTEM32 / 'WindowsPowerShell/v1.0/powershell.exe'),
                 '-NoProfile', '-NonInteractive', '-Command', script],
                cwd='/mnt/c', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            cleanup = False  # Preserve sources until owned-process exit is confirmed.
            stdout, _ = process.communicate(timeout=args.seconds + 45)
        except subprocess.TimeoutExpired:
            # The Windows controller requests graceful shutdown only. Sources
            # must remain available while the owned process may still be alive.
            return {'status': 'cleanup_unconfirmed', 'reason': 'controller timed out; owned-process exit unconfirmed'}, 2
        raw = stdout.decode(errors='replace')
        if process.returncode:
            return {'status': 'controller_failed', 'reason': 'Windows controller failed; no compile verdict'}, 2
        try:
            receipt = json.loads(raw.strip())
            code, expired = receipt['exit_code'], receipt['timed_out']
            confirmed = receipt['cleanup_confirmed']
            if (type(expired) is not bool or type(confirmed) is not bool
                    or (confirmed and type(code) is not int)
                    or (not confirmed and code is not None)):
                raise ValueError('invalid controller receipt')
        except (ValueError, KeyError, TypeError):
            return {'status': 'controller_failed', 'reason': 'missing owned-process receipt'}, 2
        if not confirmed:
            return {'status': 'cleanup_unconfirmed',
                    'reason': 'owned Workbench still running; scratch preserved'}, 2
        cleanup = True
        logs, truncated = collect_logs(scratch)
        report = verdict(logs, code, expired, truncated)
        report['inputs'] = counts
        report['scope'] = 'script validation only; dependency stack/config and boot are not qualified'
        return report, 0 if report['status'] == 'passed' else 1
    finally:
        if cleanup:
            shutil.rmtree(scratch)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', type=Path, default=REPO)
    parser.add_argument('--commit', help='read-only git archive snapshot; default: current tree')
    parser.add_argument('--native-scripts', type=Path, default=NATIVE)
    parser.add_argument('--workbench', type=Path, default=WORKBENCH)
    parser.add_argument('--seconds', type=int, default=120)
    parser.add_argument('--action-path', default='Validate Scripts',
                        help='unverified ExecuteAction menu path, slash separated')
    args = parser.parse_args(argv)
    if not 1 <= args.seconds <= 900 or not re.fullmatch(r'[A-Za-z &/]+', args.action_path):
        parser.error('invalid timeout or action path')
    try:
        report, code = run(args)
    except (OSError, ValueError, subprocess.SubprocessError, winproc.InteropError) as error:
        report, code = {'status': 'unavailable', 'reason': private(error)}, 2
    print(json.dumps(report, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
