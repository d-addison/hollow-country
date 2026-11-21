"""Guarded Workbench script compile check (WSL -> Windows).

Workbench is started with the installed game data (-loadAddons) and the same mod
stack as the compile gate (-mod=): the declared Workshop dependencies, read in
place, then our packed HollowCountry and HollowCountryExpansionAI addons and a
scratch-only tool mod. Workbench's game runtime compiles every script module at
start. Generated probe files in the tool mod reference one authored class per
module and raise a compile warning marker, so a pass proves our files were in
the compiled module. A plugin receipt or zero exit alone NEVER passes.
"""
import argparse
import base64
import contextlib
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time

from tools.package import pbo, weapon_pack_guards
from tools.release import compile_gate, ship_inputs
from tools.release.compile_gate import source_tree
from tools.release.rpt_summary import filtered
from tools.setup import winproc

REPO = Path(__file__).resolve().parents[2]
WORKBENCH = Path('/mnt/d/SteamLibrary/steamapps/common/DayZ Tools/Bin/Workbench')
MODULES = ('3_Game', '4_World', '5_Mission')
TOOL = 'HCWorkbenchTool'
PROBE = 'hc_wb_probe'
ERROR = re.compile(r"Can't compile|Cannot compile|SCRIPT\s*\(E\)|Compile error|"
                   r'Script validation failed|Failed to load .*script|Assertion failed', re.I)
WARNING = re.compile(r'SCRIPT\s*\(W\)', re.I)
DIAGNOSTIC = re.compile(r'SCRIPT\s*\([EWI]\)', re.I)
COMPILE_FAILURE = re.compile(r"Can't compile|Cannot compile|Compile error|Script validation failed"
                             r'|Failed to load .*script', re.I)
LOCATION = re.compile(r'(?P<file>[^\s"\'<>@]*?\.c)(?:\((?P<paren>\d+)\)|:(?P<colon>\d+)|,(?P<comma>\d+))', re.I)
MODULE_LINE = re.compile(r'Module: (?P<name>\w+); loaded (?P<files>\d+)x files')
PROBE_MARK = re.compile(r"is obsolete: " + PROBE + r" (?P<module>\d_\w+)")
ASSERT_HEADER = re.compile(r'\s*Assertion failed\s*$')
ASSERT_REASON = re.compile(r'Reason: [^\r\n]*')
SUCCESS = 'Script validation successful.'
RECEIPT = '[HC CompileCheck] action_returned'
MAX_LOG = 16 * 1024 * 1024
DIALOG_TITLE = 'Script Authorization Required'
DIALOG_LIMIT = 8
PLUGIN_ERROR = r'^Error: Plugin[A-Za-z]+$'
PLUGIN_ERROR_LIMIT = 24
ASSERT_TITLE = 'Enfusion engine'
ASSERT_LIMIT = 16
# WorkbenchApp.exe builds on which this route was qualified natively: the clean
# tree passed (all three probe markers, Mission loaded, owned exit confirmed) and
# a scratch-only broken control failed at HCCompileBrokenControl.c:5. A new
# DayZ Tools build stays unqualified until both runs are repeated.
QUALIFIED_WORKBENCH = {
    '16085382d1c2609b4fe879080809d9d6cfc5e2ea5e80cb006e686a349933c7db':
        '2026-11-21 DayZ Tools 1.30: clean pass + broken control at HCCompileBrokenControl.c:5',
}
MAIN_TITLE ='Workbench - *'
CLOSE_SECONDS = 150
CLOSE_REQUESTS = 3
RECEIPT_FILE ='controller-receipt.json'
STARTED_FILE = 'controller-started.txt'
CONTROLLER_START = 60
SETTLED = r"Module: Mission;|Can't compile|Failed to load \w+ script"
REQUIRED_SCRIPT_INPUTS = (('hollowcountry', 'HollowCountry'),
                          ('hollowcountryexpansionai', 'HollowCountryExpansionAI'))
# Workbench compiles "FIX-ME" diagnostics as errors; the game runtime (and so the
# native server gate) logs the same lines as warnings and compiles on. Observed
# 2026-11-21 with DayZ Tools 1.30: these dependency sources stop Workbench's World
# module, so they are left out of the Workbench mount and reported as uncovered.
# Nothing in HollowCountry or HollowCountryExpansionAI requires them; the weapon
# pack guard PBO requires script_a and is therefore not mounted either.
WORKBENCH_EXCLUDED = {
    '2646817942': (None, 'script_a: brace-less method bodies, FIX-ME: Missing function scope (12)'),
    '3114410963': (('dayz_seagull.pbo',), 'Dayz_Seagull: FIX-ME: Unmatched brackets detected (1)'),
}
OURS = re.compile(r'(?:^|[/~])(?:HollowCountry|HollowCountryExpansionAI|' + TOOL + r')/', re.I)
# Observed with game data and the full dependency stack mounted (2026-11-21,
# DayZ Tools 1.30). These come from the stock Workbench runtime, vanilla scripts
# or the absence of a game world, never from a compiled-script verdict.
KNOWN_VANILLA = tuple(re.compile(pattern) for pattern in (
    r'Missing script declaration for method',
    r'Method not linked',
    r'Leaked .* script instance',
    r'==== Total Leaks',
    r'Script is leaking',
    r'Assertion failed, Script is leaking',
    r'enf_scriptmodule\.cpp',
    r'Unknown object type',
    r'No entry .*(?:CfgWorlds|CfgVehicles|heatHazeNoise)',
    r'skeletons\.anim\.xml',
    r'\.emat',
    r'STR_DN_',
    r'UAGestureSlot|UAEmote',
    r'InputAccess',
    r'Cannot write offline shader cache',
    r'Enfusion setting file load failed',
    r'Config file deleted',
    r"is obsolete: 1\.\d+",
    r'scripts/[1-5]_\w+/',
))


def mask(value):
    """Home folders and 17-digit ids masked; used in-process for classification."""
    value = str(value).replace(str(Path.home()), '~')
    value = re.sub(r'(?i)(?:[a-z]:[\\/]|/mnt/[a-z]/)users[\\/][^\\/\r\n]+', '~', value)
    value = re.sub(r'(?i)/(?:home|Users)/[^/\r\n]+', '~', value)
    return re.sub(r'\b\d{17}\b', '<id>', value)


def private(value):
    """Drop identity-bearing messages; preserve an error verdict independently."""
    return filtered(mask(value)) or '<private diagnostic>'


def classify(entry, text=None):
    """ours: our sources; dependency: a mounted mod; known_vanilla: stock noise."""
    location = (entry.get('file') or '').replace('\\', '/')
    if OURS.search(location):
        return 'ours'
    text = entry['message'] if text is None else text
    if any(pattern.search(text) for pattern in KNOWN_VANILLA[:-1]):
        return 'known_vanilla'
    if location.startswith('scripts/') or KNOWN_VANILLA[-1].search(location):
        return 'known_vanilla'
    if location:
        return 'dependency'
    return 'unclassified'


def diagnostics(text, pattern=ERROR):
    """Match raw lines; locations (maybe on the next lines) are read after masking."""
    lines = text.splitlines()
    found, seen = [], set()
    for index, line in enumerate(lines):
        if not pattern.search(line):
            continue
        masked = mask(line)
        context = []
        # VM exceptions print Reason/Class/Function before the stack-trace location.
        for following in lines[index + 1:index + 10]:
            if DIAGNOSTIC.search(following):
                break  # The next diagnostic carries its own location.
            context.append(mask(following))
        reason = ASSERT_REASON.search('\n'.join(context)) if ASSERT_HEADER.match(line) else None
        if reason:
            masked += ' | ' + reason[0]  # A bare engine assertion header names its reason below.
        location = LOCATION.search(masked) or LOCATION.search('\n'.join(context))
        entry = {'file': location['file'] if location else None,
                 'line': int(location['paren'] or location['colon'] or location['comma']) if location else None,
                 'message': private(masked)[:2000]}
        # script_*.log and error_*.log repeat the same timestamped lines.
        key = (masked, entry['file'], entry['line'])
        if key in seen:
            continue
        seen.add(key)
        entry['class'] = 'probe' if PROBE_MARK.search(masked) else classify(entry, masked)
        if COMPILE_FAILURE.search(line):
            entry['class'] = 'ours' if entry['class'] == 'ours' else 'compile_failure'
        found.append(entry)
    return found


def summary(entries):
    counts = {}
    for entry in entries:
        counts[entry['class']] = counts.get(entry['class'], 0) + 1
    return counts


def verdict(text, returncode, timed_out=False, truncated=False, probes=MODULES):
    """Blocking: our errors, any compile failure, unclassified errors, missing markers."""
    every = diagnostics(text)
    warnings = diagnostics(text, WARNING)
    modules = {match['name']: int(match['files']) for match in MODULE_LINE.finditer(text)}
    marked = sorted(set(PROBE_MARK.findall(text)))
    blocking = [entry for entry in every if entry['class'] in ('ours', 'compile_failure', 'unclassified')]
    if blocking:
        status = 'compile_failed'
    elif truncated:
        status = 'incomplete_logs'
    elif 'Mission' not in modules or sorted(probes) != marked:
        status = 'timeout' if timed_out else 'unverified'
    elif returncode not in (0, None):
        status = 'tool_failed'
    else:
        status = 'passed'
    ours_warnings = [entry for entry in warnings if entry['class'] == 'ours']
    return {'status': status, 'errors': blocking, 'warnings_ours': ours_warnings[:200],
            'triage': {'errors': summary(every), 'warnings': summary(warnings)},
            'modules': modules, 'probe_modules': marked, 'tool_exit': returncode,
            'timed_out': timed_out,
            'native_validation_completed': 'Mission' in modules and sorted(probes) == marked,
            'plugin_returned': RECEIPT in text, 'script_editor_validation': SUCCESS in text,
            'route_qualified': False}


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


def tool_pbo(files, prefix):
    """Uncompressed scratch-only PBO for the generated tool mod (never shipped)."""
    words = struct.Struct('<5I')
    header = bytearray(b'\0' + words.pack(0x56657273, 0, 0, 0, 0))
    header += b'prefix\0' + prefix.encode('ascii') + b'\0\0'
    payload = bytearray()
    for name in sorted(files):
        pbo.safe_name(name)
        header += name.replace('/', '\\').encode('ascii') + b'\0' + words.pack(0, 0, 0, 0, len(files[name]))
        payload += files[name]
    body = bytes(header + bytes(21) + payload)
    return body + b'\0' + hashlib.sha1(body).digest()


def probe_class(scripts, module):
    """First plain top-level class in a file without preprocessor branches."""
    for path in sorted((scripts / module).rglob('*.c')):
        text = path.read_text(encoding='utf-8-sig', errors='replace')
        if re.search(r'^\s*#\s*(?:ifdef|ifndef|if)\b', text, re.M):
            continue
        match = re.search(r'^class\s+([A-Za-z_]\w*)', text, re.M)
        if match:
            return match[1]
    return None


def tool_mod(tree, mods):
    """Plugin plus per-module probes that only compile if our classes loaded."""
    files = {'plugins/HC_CompileCheck.c': (tree / 'tools/workbench/HC_CompileCheck.c').read_bytes()}
    defs, probes = ['class workbenchScriptModule { value = ""; files[] = {"%s/plugins"}; };' % TOOL], []
    names = {'3_Game': 'gameScriptModule', '4_World': 'worldScriptModule', '5_Mission': 'missionScriptModule'}
    for module in MODULES:
        refs = []
        for mod in mods:
            name = probe_class(tree / 'mods' / mod / 'scripts', module)
            if name:
                refs.append('\t\ttypename ref%d = %s;' % (len(refs), name))
        if not refs:
            continue
        probes.append(module)
        files['probe/%s/hc_wb_probe.c' % module] = (
            '// Generated by tools/release/wb_compile.py for scratch Workbench runs only.\n'
            'class HCWorkbenchProbe_%s\n{\n\t[Obsolete("%s %s")]\n\tstatic void Mark() {}\n'
            '\tstatic void Use()\n\t{\n%s\n\t\tMark();\n\t}\n}\n'
            % (module, PROBE, module, '\n'.join(refs))).encode()
        defs.append('class %s { value = ""; files[] = {"%s/probe/%s"}; };' % (names[module], TOOL, module))
    files['config.cpp'] = (
        'class CfgPatches { class %s { units[] = {}; weapons[] = {}; requiredVersion = 0.1; '
        'requiredAddons[] = {"DZ_Data", "DZ_Scripts"}; }; };\n'
        'class CfgMods { class %s { dir = "%s"; name = "HC Workbench compile tool"; type = "mod"; '
        'dependencies[] = {"Game", "World", "Mission"}; class defs { %s }; }; };\n'
        % (TOOL, TOOL, TOOL, ' '.join(defs))).encode()
    return files, probes


def stage(tree, workshop, scratch):
    """Pack our addons like compile_gate; dependencies stay in the Workshop folder."""
    catalogue = {(stem, mod) for stem, mod, _ in ship_inputs.signing_inputs()}
    mods = []
    for entry in REQUIRED_SCRIPT_INPUTS:
        stem, mod = entry
        if entry not in catalogue:
            raise ValueError('required script addon absent from ship catalogue: ' + stem)
        scripts = tree / 'mods' / mod / 'scripts'
        if not scripts.is_dir():
            raise ValueError('required script directory absent: ' + mod)
        if not any(path.suffix.lower() == '.c' for path in scripts.rglob('*')):
            raise ValueError('empty required script input: ' + mod)
        mods.append(mod)
    with contextlib.redirect_stdout(sys.stderr), contextlib.ExitStack() as stack:
        inputs = stack.enter_context(compile_gate.compatibility_inputs(tree, workshop, scratch))
        base = scratch / '@HollowCountry/addons'
        base.mkdir(parents=True)
        (base / 'hollowcountry.pbo').write_bytes(pbo.pack(pbo.collect_addon(tree / 'mods/HollowCountry')))
        adapter = scratch / '@HollowCountryExpansionAI/addons'
        adapter.mkdir(parents=True)
        (adapter / 'hollowcountryexpansionai.pbo').write_bytes(pbo.pack(
            pbo.collect_addon(tree / 'mods/HollowCountryExpansionAI', prefix='HollowCountryExpansionAI'),
            prefix='HollowCountryExpansionAI'))
        dependencies, excluded = workbench_dependencies(list(inputs.get('extra_mods', ())), scratch)
        uncovered = []
        for extra in inputs.get('server_extra_pbos', ()):
            if weapon_pack_guards.ITEM in excluded:
                uncovered.append(extra.name + ' (requires ' + weapon_pack_guards.PATCH + ')')
                continue
            shutil.copyfile(extra, adapter / extra.name)
    files, probes = tool_mod(tree, mods)
    (scratch / ('@' + TOOL) / 'addons').mkdir(parents=True)
    (scratch / ('@' + TOOL) / 'addons/hcworkbenchtool.pbo').write_bytes(tool_pbo(files, TOOL))
    (scratch / 'profile').mkdir()
    staged = [scratch / '@HollowCountry', scratch / '@HollowCountryExpansionAI', scratch / ('@' + TOOL)]
    counts = {mod: sum(1 for path in (tree / 'mods' / mod / 'scripts').rglob('*.c')) for mod in mods}
    counts['dependency_mods'] = len(dependencies)
    counts['excluded_dependencies'] = excluded
    counts['uncovered'] = uncovered
    return dependencies + staged, probes, counts


def workbench_dependencies(mods, scratch):
    """Mount dependencies in place, minus sources Workbench cannot compile.

    A wholly excluded item is not mounted. A partly excluded item is mirrored
    into the scratch folder without the listed PBOs (local, deleted with the
    scratch, never in git); every other item is read from the Workshop folder.
    """
    mounted, excluded = [], {}
    for mod in mods:
        rule = WORKBENCH_EXCLUDED.get(mod.name)
        if rule is None:
            mounted.append(mod)
            continue
        names, reason = rule
        excluded[mod.name] = {'pbos': sorted(names) if names else 'all', 'reason': reason}
        if names is None:
            continue
        addons = [path for path in mod.iterdir() if path.is_dir() and path.name.lower() == 'addons']
        if len(addons) != 1:
            raise ValueError('dependency has no unique addons directory: ' + mod.name)
        present = {path.name.lower() for path in addons[0].iterdir()}
        if not set(names) <= present:
            raise ValueError('Workbench exclusion no longer matches the installed item: ' + mod.name)
        mirror = scratch / ('@wb-' + mod.name) / 'addons'
        mirror.mkdir(parents=True)
        for path in sorted(addons[0].iterdir()):
            if path.is_file() and path.suffix.lower() == '.pbo' and path.name.lower() not in names:
                shutil.copyfile(path, mirror / path.name)
        mounted.append(mirror.parent)
    return mounted, excluded


def controller(executable, scratch, seconds, action, mods):
    """PowerShell owns the process handle through timeout and cleanup.

    No retries: a lost interop response must never launch a second process.
    A named mutex serializes cooperating drivers; a second process query inside
    the lock covers the interval between the Python preflight and Start-Process.
    The vanilla game runtime asks once per launch whether scripts may call
    OpenFile; only that exact dialog, owned by our process, is answered "No to
    All" (keyboard mnemonic O posted to the dialog, no focus change or click).
    """
    args = ['-loadAddons', '-mod=' + ';'.join(windows_path(mod) for mod in mods),
            '-profiles=' + windows_path(scratch / 'profile'),
            '-wbmodule=ScriptEditor', '-plugin=HC_CompileCheck', '-hcCompileAction=' + action]
    # Start-Process joins ArgumentList without quoting; explicitly quote each arg.
    if any('"' in arg or '\n' in arg or '\r' in arg for arg in args):
        raise ValueError('unsafe Windows argument')
    argument_list = ','.join(quote_ps('"' + arg + '"') for arg in args)
    return f"""
$ErrorActionPreference = 'Stop'
$receiptPath = {quote_ps(windows_path(scratch / RECEIPT_FILE))}
[IO.File]::WriteAllText({quote_ps(windows_path(scratch / STARTED_FILE))}, [string]$PID)
$failure = $null
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class HcWbDialogs {{
    delegate bool EnumProc(IntPtr hwnd, IntPtr data);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc proc, IntPtr data);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int size);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr hwnd, StringBuilder text, int size);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr hwnd, uint msg, IntPtr w, IntPtr l);
    public class Win {{ public IntPtr Handle; public string Title; public string Class; }}
    public static List<Win> Windows(uint owner) {{
        var found = new List<Win>();
        EnumWindows((hwnd, data) => {{
            uint pid;
            GetWindowThreadProcessId(hwnd, out pid);
            if (pid != owner || !IsWindowVisible(hwnd)) return true;
            var text = new StringBuilder(256);
            GetWindowText(hwnd, text, text.Capacity);
            var kind = new StringBuilder(256);
            GetClassName(hwnd, kind, kind.Capacity);
            found.Add(new Win {{ Handle = hwnd, Title = text.ToString(), Class = kind.ToString() }});
            return true;
        }}, IntPtr.Zero);
        return found;
    }}
    public static bool Close(IntPtr hwnd) {{
        // WM_CLOSE to the owned main window: the same request as CloseMainWindow.
        return PostMessage(hwnd, 0x0010, IntPtr.Zero, IntPtr.Zero);
    }}
    public static bool Command(IntPtr hwnd, int id) {{
        // WM_COMMAND with a standard MessageBox button id, posted to this dialog only.
        return PostMessage(hwnd, 0x0111, (IntPtr)id, IntPtr.Zero);
    }}
    public static bool Key(IntPtr hwnd, int vk, int scan) {{
        // Posted to this one window: no focus change, no global input injection.
        return PostMessage(hwnd, 0x0100, (IntPtr)vk, (IntPtr)((scan << 16) | 1))
            && PostMessage(hwnd, 0x0101, (IntPtr)vk, (IntPtr)unchecked((int)(0xC0000001u | (uint)(scan << 16))));
    }}
}}
'@
$mutex = New-Object System.Threading.Mutex($false, 'Local\\HollowCountryWorkbenchCompile')
$locked = $false
$owned = $null
$expired = $false
$cleanupConfirmed = $false
$exitCode = $null
$denied = 0
$dismissed = 0
$ignored = 0
$settled = $false
$answered = @{{}}
function Answer-Dialogs($process) {{
    $open = $false
    foreach ($window in [HcWbDialogs]::Windows([uint32]$process.Id)) {{
        $title = $window.Title
        $key = [string]$window.Handle
        if ($answered.ContainsKey($key) -and ([DateTime]::UtcNow - $answered[$key]).TotalSeconds -lt 3) {{ $open = $true; continue }}
        if ($title -ceq {quote_ps(DIALOG_TITLE)} -and $script:denied -lt {DIALOG_LIMIT}) {{
            # Vanilla/dependency script asks for OpenFile: answer N&o to All (mnemonic O).
            if ([HcWbDialogs]::Key($window.Handle, 0x4F, 0x18)) {{ $script:denied++ }}
        }} elseif ($title -cmatch {quote_ps(PLUGIN_ERROR)} -and $script:dismissed -lt {PLUGIN_ERROR_LIMIT}) {{
            # Dependency Workbench plugin Workbench.Dialog("Error: <plugin>") with one OK button.
            if ([HcWbDialogs]::Key($window.Handle, 0x0D, 0x1C)) {{ $script:dismissed++ }}
        }} elseif ($title -ceq {quote_ps(ASSERT_TITLE)} -and $window.Class -ceq '#32770' -and $script:ignored -lt {ASSERT_LIMIT}) {{
            # Engine assertion MessageBox (Abort/Retry/Ignore); the text is also in crash_*.log.
            # Ignore (IDIGNORE=5) continues; Abort would end the process abruptly.
            if ([HcWbDialogs]::Command($window.Handle, 5)) {{ $script:ignored++ }}
        }} else {{
            continue
        }}
        $answered[$key] = [DateTime]::UtcNow
        $open = $true
    }}
    return $open
}}
try {{
    $locked = $mutex.WaitOne(0)
    if (!$locked) {{ throw 'Workbench compile controller busy' }}
    if (Get-Process -Name WorkbenchApp -ErrorAction SilentlyContinue) {{
        throw 'Workbench already running'
    }}
    $owned = Start-Process -FilePath {quote_ps(windows_path(executable))} -WorkingDirectory {quote_ps(windows_path(executable.parent))} -ArgumentList @({argument_list}) -RedirectStandardOutput {quote_ps(windows_path(scratch / 'stdout.log'))} -RedirectStandardError {quote_ps(windows_path(scratch / 'stderr.txt'))} -PassThru
    # Cache the handle now; without it Start-Process objects report a null ExitCode after exit.
    $null = $owned.Handle
    $deadline = [DateTime]::UtcNow.AddMilliseconds({int(seconds * 1000)})
    $logs = {quote_ps(windows_path(scratch / 'profile'))}
    $settleAt = $null
    $tick = 0
    while (!$owned.HasExited -and [DateTime]::UtcNow -lt $deadline) {{
        [void](Answer-Dialogs $owned)
        [void]$owned.WaitForExit(250)
        $tick++
        if ($null -eq $settleAt -and $tick % 8 -eq 0) {{
            # The game runtime compiles at start; once Mission loaded or a module
            # failed, the verdict is in the log and the session can be closed.
            $done = Get-ChildItem -LiteralPath $logs -Filter 'script_*.log' -ErrorAction SilentlyContinue |
                Select-String -Pattern {quote_ps(SETTLED)} -Quiet
            if ($done) {{ $settleAt = [DateTime]::UtcNow.AddSeconds(5) }}
        }}
        if ($null -ne $settleAt -and [DateTime]::UtcNow -gt $settleAt) {{ $settled = $true; break }}
    }}
    $expired = !$owned.HasExited -and !$settled
}} catch {{
    $failure = 'controller error'
}} finally {{
    if ($null -ne $owned) {{
        if (!$owned.HasExited) {{
            try {{
                # Graceful only: clear our known dialogs, then ask the owned main
                # window to close (WM_CLOSE, what CloseMainWindow sends). A close
                # posted while Workbench is still opening plugin dialogs is
                # dropped, so it is repeated a bounded number of times.
                $closeBy = [DateTime]::UtcNow.AddSeconds({CLOSE_SECONDS})
                $nextClose = [DateTime]::UtcNow
                $requests = 0
                while (!$owned.HasExited -and [DateTime]::UtcNow -lt $closeBy) {{
                    if (!(Answer-Dialogs $owned) -and $requests -lt {CLOSE_REQUESTS} -and [DateTime]::UtcNow -ge $nextClose) {{
                        $main = [HcWbDialogs]::Windows([uint32]$owned.Id) | Where-Object {{ $_.Title -clike {quote_ps(MAIN_TITLE)} }} | Select-Object -First 1
                        if ($null -ne $main -and [HcWbDialogs]::Close($main.Handle)) {{
                            $requests++
                            $nextClose = [DateTime]::UtcNow.AddSeconds(20)
                        }}
                    }}
                    [void]$owned.WaitForExit(1000)
                }}
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
$receipt = @{{exit_code=$exitCode; timed_out=$expired; cleanup_confirmed=$cleanupConfirmed; launched=($null -ne $owned); failure=$failure; authorization_denied=$denied; plugin_dialogs_dismissed=$dismissed; assertions_ignored=$ignored; settled=$settled}} | ConvertTo-Json -Compress
# Write then rename, so the WSL side never reads a partial receipt.
[IO.File]::WriteAllText($receiptPath + '.tmp', $receipt)
Move-Item -LiteralPath ($receiptPath + '.tmp') -Destination $receiptPath -Force
"""


def collect_logs(root):
    """Engine logs from the scratch profile only (stderr carries a client identity)."""
    texts, total, truncated = [], 0, False
    for path in sorted(root.rglob('*')):
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


def workbench_build(executable):
    digest = hashlib.sha256()
    with executable.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def launch_controller(script, scratch, seconds, clock=time.monotonic, pause=time.sleep):
    """Start the controller as a detached Windows process and wait for its receipt file.

    WSL interop pipes can drop mid-run ("UtilAcceptVsock ... accept4 failed"),
    which killed a -Command controller while Workbench stayed open. The
    controller therefore runs from a scratch .ps1 via shell-execute (no inherited
    WSL handles) and reports through files. The launcher call is never retried:
    an ambiguous launch is resolved by the started marker, not by a second start.
    Returns the receipt text, or None when the owned-process outcome is unknown.
    """
    path = scratch / 'controller.ps1'
    path.write_text(script, encoding='utf-8-sig')
    started, receipt = scratch / STARTED_FILE, scratch / RECEIPT_FILE
    target = windows_path(path)
    if '"' in target:
        raise ValueError('unsafe controller path')
    # Load the file as a scriptblock (as the client launcher does) rather than -File, so no
    # execution-policy override is needed; -EncodedCommand avoids nested argument quoting.
    body = '& ([scriptblock]::Create((Get-Content -Raw -LiteralPath %s)))' % quote_ps(target)
    encoded = base64.b64encode(body.encode('utf-16-le')).decode('ascii')
    launcher = ("Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -ArgumentList "
                + "'-NoProfile','-NonInteractive','-EncodedCommand'," + quote_ps(encoded))
    try:
        subprocess.run([str(winproc.SYSTEM32 / 'WindowsPowerShell/v1.0/powershell.exe'),
                        '-NoProfile', '-NonInteractive', '-Command', launcher],
                       cwd='/mnt/c', stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=30)
    except subprocess.TimeoutExpired:
        pass  # Ambiguous: the started marker decides.
    begin = clock()
    while clock() - begin < CONTROLLER_START:
        if started.exists() or receipt.exists():
            break
        pause(1)
    else:
        raise ValueError('Windows controller did not start')
    while clock() - begin < seconds:
        if receipt.exists():
            return receipt.read_text(encoding='utf-8-sig', errors='replace')
        pause(2)
    return None


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
            with contextlib.redirect_stdout(sys.stderr):
                compile_gate.ship_config(tree, bool(args.commit))
            mods, probes, counts = stage(tree, args.workshop, scratch)
        script = controller(args.workbench / 'WorkbenchApp.exe', scratch, args.seconds, args.action_path, mods)
        cleanup = False  # Preserve sources until owned-process exit is confirmed.
        raw = launch_controller(script, scratch, args.seconds + CLOSE_SECONDS + 120)
        if raw is None:
            return {'status': 'cleanup_unconfirmed', 'reason': 'no controller receipt; owned-process exit unconfirmed'}, 2
        try:
            receipt = json.loads(raw.strip())
            code, expired = receipt['exit_code'], receipt['timed_out']
            confirmed, denied = receipt['cleanup_confirmed'], receipt.get('authorization_denied', 0)
            dismissed = receipt.get('plugin_dialogs_dismissed', 0)
            ignored = receipt.get('assertions_ignored', 0)
            if (type(expired) is not bool or type(confirmed) is not bool or type(denied) is not int
                    or type(dismissed) is not int or type(ignored) is not int
                    or (confirmed and type(code) is not int)
                    or (not confirmed and code is not None)):
                raise ValueError('invalid controller receipt')
        except (ValueError, KeyError, TypeError):
            return {'status': 'controller_failed', 'reason': 'missing owned-process receipt'}, 2
        if receipt.get('failure') is not None and not receipt.get('launched'):
            cleanup = True
            return {'status': 'controller_failed', 'reason': 'Windows controller refused or failed before launch'}, 2
        if not confirmed:
            return {'status': 'cleanup_unconfirmed',
                    'reason': 'owned Workbench still running; scratch preserved'}, 2
        if receipt.get('failure') is not None:
            return {'status': 'controller_failed', 'reason': 'Windows controller error during the run'}, 2
        cleanup = not args.keep_scratch
        logs, truncated = collect_logs(scratch / 'profile')
        settled = receipt.get('settled') is True
        # Our own close request (deadline or settled) makes the exit code meaningless.
        report = verdict(logs, None if expired or settled else code, expired, truncated, probes)
        report['settled'] = settled
        report['inputs'] = counts
        report['authorization_dialogs_denied'] = denied
        report['plugin_error_dialogs_dismissed'] = dismissed
        report['assertion_dialogs_ignored'] = ignored
        build = workbench_build(args.workbench / 'WorkbenchApp.exe')
        report['workbench_build'] = build[:16]
        # Qualified only on a Workbench build with recorded pass + broken-control evidence.
        report['route_qualified'] = report['status'] == 'passed' and build in QUALIFIED_WORKBENCH
        report['scope'] =('Workbench game-runtime compile of the mounted stack (game data, Workshop '
                           'dependencies, our packed addons); not boot, config runtime or gameplay')
        return report, 0 if report['status'] == 'passed' else 1
    finally:
        if cleanup:
            shutil.rmtree(scratch)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', type=Path, default=REPO)
    parser.add_argument('--commit', help='read-only git archive snapshot; default: current tree')
    parser.add_argument('--workbench', type=Path, default=WORKBENCH)
    parser.add_argument('--workshop', type=Path, default=weapon_pack_guards.WORKSHOP,
                        help='installed Workshop content root, mounted read-only via -mod')
    parser.add_argument('--seconds', type=int, default=240)
    parser.add_argument('--keep-scratch', action='store_true', help='keep the Windows TEMP scratch and logs')
    parser.add_argument('--action-path', default='Validate Scripts',
                        help='Script Editor ExecuteAction menu path, slash separated')
    args = parser.parse_args(argv)
    if not 1 <= args.seconds <= 900 or not re.fullmatch(r'[A-Za-z &/]+', args.action_path):
        parser.error('invalid timeout or action path')
    try:
        from tools.release.host_lock import host_lock
        with host_lock('wb_compile'):
            report, code = run(args)
    except (OSError, ValueError, subprocess.SubprocessError, winproc.InteropError) as error:
        report, code = {'status': 'unavailable', 'reason': private(error)}, 2
    print(json.dumps(report, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
