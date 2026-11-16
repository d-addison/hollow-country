# Local Windows vanilla P0 setup

Ready for native Windows review and dry run. Validation here is **static only**:
PowerShell parsing, native -WhatIf, staging, launch, binding, client join and
persistence have **not executed** in this agent environment. WSL Windows launches
previously failed with UtilAcceptVsock/timeout. Do the next step in an ordinary
Windows PowerShell 5.1+ terminal, not WSL. No administrator shell is required.

The first actual Windows dry run reached the installed server executable but
failed because the hash helper returned no `Hash` property under `-WhatIf`.
The revised script uses read-only .NET SHA-256 streams and disposes them without
provider helper operations. Seven local static checks pass after the fix; the
user's installed-file dry run still requires a successful rerun. A separate
Windows CI synthetic integration test checks hashing, dry-run non-creation,
staging and overwrite refusal without game assets or a server process.

## Next concrete command

Paste this in Windows PowerShell (it reads/verifies the installed baseline and
prints the proposed staging operation; it must not create the runtime):

~~~powershell
powershell.exe -NoProfile -File "$env:USERPROFILE\Downloads\HollowCountry-Setup-20261116\New-LocalVanillaRuntime.ps1" -RuntimeRoot "D:\HollowCountryLocal\vanilla-p0-001" -WhatIf
~~~

The original `\\wsl.localhost\Ubuntu-24.04\code\dayzsa_mods` command failed on the
user's Windows terminal: the file was not found. A wslpath conversion did not
prove Windows share access. The .ps1 and baseline JSON were copied to the above
Windows Downloads folder and both SHA-256 hashes matched repository source.
If execution
policy blocks the script, stop and use your approved local script execution
policy; this setup does not change machine policy or bypass it. You may review
and copy the three authored setup files (.ps1, baseline .json, and this guide)
to a Windows folder, preserving the .ps1/.json adjacency, then invoke that .ps1.

## Observed installations and prerequisites

| Purpose | Exact Windows path / observed version |
| --- | --- |
| Official DayZ Tools | D:\SteamLibrary\steamapps\common\DayZ Tools |
| Workbench | D:\SteamLibrary\steamapps\common\DayZ Tools\Bin\Workbench\WorkbenchApp.exe |
| Addon Builder | D:\SteamLibrary\steamapps\common\DayZ Tools\Bin\AddonBuilder\AddonBuilder.exe |
| CE Editor | D:\SteamLibrary\steamapps\common\DayZ Tools\Bin\CeEditor\CeEditor.exe |
| Official server | D:\SteamLibrary\steamapps\common\DayZServer |
| Server executable | D:\SteamLibrary\steamapps\common\DayZServer\DayZServer_x64.exe |
| Stock config | D:\SteamLibrary\steamapps\common\DayZServer\serverDZ.cfg |
| Stock mission | D:\SteamLibrary\steamapps\common\DayZServer\mpmissions\dayzOffline.chernarusplus |
| Normal game client (earlier inventory; recheck before joining) | G:\SteamLibrary\steamapps\common\DayZ\DayZ_x64.exe |
| Proposed test runtime (must not exist) | D:\HollowCountryLocal\vanilla-p0-001 |

Read-only installation inventory, 2026-11-16: server Steam app 223350, build
26220720; Tools app 830640, build 26405911; StateFlags 4 for both. Server and
Workbench PE resources report FileVersion 1.30.164.289, ProductVersion
1.30.164289.70. These are file observations, not successful launches.

Prerequisites: complete official Steam installations and applicable terms/
BattlEye setup, matching normal client/server build, no running DayZ server,
an approved Windows PowerShell session, access to the UNC source and writable
D: drive. Allow at least 300 MB for the approximately 218 MB mission plus backup,
then additional space for saves/logs/dumps. The server's existing approximately
5.8 GB asset installation is used in place. Tools binaries are checked for
presence, but Workbench, project drive creation and extraction are not run here.

The hash-only [installed baseline](../tools/setup/installed-vanilla-baseline.json)
pins 43 stock mission files (108,740,480 bytes total), the server executable,
config and BattlEye DLL. No storage directory was found in that mission during
inventory. Source copies are not committed to Git. A hash mismatch means stop and
review changed installation files; do not regenerate a trusted baseline merely to
make the check pass. This is a local installed-file pin, not an independent
verification of Steam authenticity.

## What staging does

[New-LocalVanillaRuntime.ps1](../tools/setup/New-LocalVanillaRuntime.ps1) stages
only after its ShouldProcess gate. -WhatIf performs read-only validation first.
It accepts one new named direct child of D:\HollowCountryLocal, rejects reparse
points/junctions in source/destination ancestors and copied mission paths, and
refuses any existing runtime (including empty, partial, authored or saved ones).
There is no force/reuse/reset option. Stock storage/profile/log/backup folders
are excluded without traversing their contents. Unexpected mission files or
changed source hashes abort staging.

~~~text
D:\HollowCountryLocal\vanilla-p0-001\
  serverDZ.cfg
  mpmissions\dayzOffline.chernarusplus\...
  profiles\
  storage\
  battleye\BEServer_x64.dll
  stock-backup\serverDZ.cfg
  stock-backup\mpmissions\dayzOffline.chernarusplus\...
  start-command.txt
  launch-plan.json
~~~

Stock config and all 43 mission files are backed up byte-for-byte under
stock-backup. New files use create-new/no-overwrite operations. A copy error leaves
a partial runtime for inspection, not automatic deletion; use a new name such as
vanilla-p0-002 for a new attempt. launch-plan.json is written last and is the
staging completion marker, not runtime acceptance.

The installed serverDZ.cfg is the authority for config names. This script keeps
its mission template and other stock fields, changing hostname and enforcing:

~~~cpp
maxPlayers = 6;
verifySignatures = 2;
forceSameBuild = 1;
~~~

Signature verification and same-build enforcement are already 2 and 1 in stock.
The supplied config has blank login/admin passwords; these are retained for this
local-only test. No secrets, RCon config, UPnP directive, router mapping, firewall
rule, WinRM service or public-server configuration is added.

The only staged mission change is db\messages.xml: a documented graceful shutdown
countdown, 30 minutes by default (-SessionMinutes accepts 10–180). The original
messages XML is retained in stock-backup. The installed vanilla init.c is copied
unchanged (SHA-256 73658fca45ade1c54d7ee729b31f78f3c27b46282ffd3d503d10b524b8a20afb).
No authored Enforce scripts, mod, unsigned gameplay code or file-patching flags
are deployed. The executable/assets remain in the official server directory;
absolute mission/storage/profiles/BattlEye arguments point into the fresh runtime.

## Native syntax check, dry run, then stage

The -WhatIf command at the top naturally requires native PowerShell parsing.
For a parser-only check before running script code, use this in Windows PowerShell:

~~~powershell
$script = "$env:USERPROFILE\Downloads\HollowCountry-Setup-20261116\New-LocalVanillaRuntime.ps1"
$tokens = $null
$parseErrors = $null
$null = [System.Management.Automation.Language.Parser]::ParseFile($script, [ref]$tokens, [ref]$parseErrors)
$parseErrors | Format-List Message, Extent
if ($parseErrors.Count -ne 0) { throw 'Native parse failed; do not stage.' }
~~~

After a successful -WhatIf, confirm the runtime still does not exist:

~~~powershell
Test-Path -LiteralPath 'D:\HollowCountryLocal\vanilla-p0-001'
# Expected False before staging; this has not been observed here.
~~~

Run this separately to stage (still launches nothing):

~~~powershell
powershell.exe -NoProfile -File "$env:USERPROFILE\Downloads\HollowCountry-Setup-20261116\New-LocalVanillaRuntime.ps1" -RuntimeRoot "D:\HollowCountryLocal\vanilla-p0-001"
~~~

Review the local config, backup hashes, staged messages, launch-plan.json and
start-command.txt before launch. No installed source file should have changed.
Do not launch a partial runtime lacking launch-plan.json.

## User-controlled launch and local-bind observation

The script generates start-command.txt containing a complete Start-Process
command with quoted argument values. It never evaluates that text. Inspect it:

~~~powershell
Get-Content -LiteralPath 'D:\HollowCountryLocal\vanilla-p0-001\start-command.txt'
Get-Content -LiteralPath 'D:\HollowCountryLocal\vanilla-p0-001\launch-plan.json'
~~~

For the default paths, this is the equivalent command you can execute directly
in your existing Windows PowerShell session. It starts only the dedicated server,
keeps its process object in $server, and does not launch the client:

~~~powershell
if (Get-Process -Name DayZServer_x64 -ErrorAction SilentlyContinue) { throw 'A DayZ server is already running.' }
if (-not (Test-Path -LiteralPath 'D:\HollowCountryLocal\vanilla-p0-001\launch-plan.json')) { throw 'Staging incomplete.' }
$server = Start-Process -FilePath 'D:\SteamLibrary\steamapps\common\DayZServer\DayZServer_x64.exe' -WorkingDirectory 'D:\SteamLibrary\steamapps\common\DayZServer' -ArgumentList @(
    '-ip=127.0.0.1',
    '-port=2302',
    '"-config=D:\HollowCountryLocal\vanilla-p0-001\serverDZ.cfg"',
    '"-mission=D:\HollowCountryLocal\vanilla-p0-001\mpmissions\dayzOffline.chernarusplus"',
    '"-storage=D:\HollowCountryLocal\vanilla-p0-001\storage"',
    '"-profiles=D:\HollowCountryLocal\vanilla-p0-001\profiles"',
    '"-BEpath=D:\HollowCountryLocal\vanilla-p0-001\battleye"',
    '-doLogs',
    '-adminLog'
) -PassThru
$server.Id
~~~

If you selected another runtime name, use the corresponding generated command
after review, not the default command above. Do not use Invoke-Expression.

-ip=127.0.0.1 requests loopback. Its effectiveness for this build and every
Steam/query socket has not been observed, and the indexed official launch list
does not explicitly establish this parameter. Do not treat a successful process
start as proof of isolation. Before connecting, inspect all endpoints owned by
the actual server PID (repeat until startup completes; a blank result is not a
pass):

~~~powershell
Get-NetUDPEndpoint -OwningProcess $server.Id -ErrorAction SilentlyContinue |
    Format-Table LocalAddress, LocalPort, OwningProcess
Get-NetTCPConnection -OwningProcess $server.Id -ErrorAction SilentlyContinue |
    Format-Table LocalAddress, LocalPort, RemoteAddress, RemotePort, State
~~~

Require game UDP port 2302 on 127.0.0.1. Confirm listeners/query endpoints are
loopback too; a wildcard or non-loopback local bind is not acceptable for this
task. Steam/BattlEye outbound connections are not the same thing as listeners,
but inspect rather than assume the difference. If a wildcard/non-loopback listener
appears, do not connect or widen access: abort that test process immediately
(Stop-Process -Id $server.Id is an emergency containment option, not a graceful
save operation), preserve its isolated logs and report the bind mismatch. No
firewall, UPnP or public-IP workaround belongs to this runbook. Loopback access
does not provide the eventual friend's/LAN server setup.

## Logs, manual connection and safe stop

Inspect D:\HollowCountryLocal\vanilla-p0-001\profiles for the newly created RPT,
script/crash logs and DayZServer_x64.ADM. Actual filenames and readiness messages
must be observed, not inferred. Example log observation in a second Windows
PowerShell window:

~~~powershell
Get-ChildItem -LiteralPath 'D:\HollowCountryLocal\vanilla-p0-001\profiles' -File |
    Sort-Object LastWriteTime -Descending |
    Format-Table Name, Length, LastWriteTime
$rpt = Get-ChildItem -LiteralPath 'D:\HollowCountryLocal\vanilla-p0-001\profiles' -Filter '*.RPT' |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($null -ne $rpt) { Get-Content -LiteralPath $rpt.FullName -Tail 60 -Wait }
~~~

Ctrl+C in that log-tail window stops the tail, not the server. Check logs for
the matching build, Chernarus mission initialization, CE/script errors and
shutdown countdown. Verify new persistence appears under the isolated storage
root (its exact nested filenames are pending observation); verify stock mission
storage remains unchanged.

Only after acceptable bind/log evidence, manually open the normal DayZ client
with all mods and file patching disabled and the same game build. In the normal
launcher, use Direct Connect to address 127.0.0.1, game port 2302. If the launcher
requires a query port, inspect the actual server endpoints/logs rather than
inventing one. This agent does not launch the client.

For normal stop, log out through the client, wait for the staged messages.xml
shutdown countdown, and observe the save/kick/lock/exit sequence in logs.
The documented sequence can include a further minute before process exit.
Do not close the server window, use Task Manager termination, or kill it as your
normal persistence test. The script does not install an auto-restarter. To finish
a shorter session, choose a shorter SessionMinutes value when staging a fresh
runtime; editing messages after startup is not assumed to reload it.

After the process exits naturally, back up the entire isolated runtime while
stopped to a new destination outside Git before a persistence restart test.
Keep source/backup hashes and logs. Reuse the reviewed Start-Process command for
the same runtime to test restart persistence; do not rerun the creation script
over it. Never delete stock or test storage to manufacture a successful restart.
Stock files were not changed, so rollback is simply stop using this runtime.
Existing authored files/saves are preserved; no automatic cleanup is supplied.

## Evidence, traceability and remaining gates

This is support for Banso plan T002/T003, FR-002/FR-012 and AC-002. It does not
complete T003, NET-004, NET-005, diagnostic/PBO/signature smoke tests, two-client
acceptance or target-load performance. The 3–6-player preference is a capacity
setting here, not a measured benchmark or proof of six-client operation.

Red recorded 2026-11-16T19:19:15Z:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools/setup -p 'test_*.py' -v
exited 1 with six FileNotFoundError errors for the not-yet-written .ps1. Static
tests inspect guardrails, pinned metadata and runbook coverage; they do not parse
or execute PowerShell and cannot establish native -WhatIf/no-write behavior.
Green observed 2026-11-16T19:25:30Z: the same setup command exited 0,
6 tests passed in 0.003s. The required existing regression command
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v
also exited 0: 168 tests passed in 5.960s. A read-only hash recheck confirmed
all 43 pinned mission files, the stock config, server executable and BattlEye DLL
were unchanged. None of these results establishes native PowerShell behavior.

Main owns CI/README/Banso verification integration. Read-only inspection confirms
CI includes python3 -B -m unittest discover -s tools/setup -v; this task does not
edit those integration files.

Evidence to capture from Windows: native parser result, exact -WhatIf output and
absent runtime, staging transcript/hash checks, actual launch command/PID,
loopback socket bindings, mission/log initialization, manual connect/disconnect,
inventory/respawn/reconnect observations, natural shutdown and saved-state restart.
Redact player IDs and keep saves/profiles outside Git. No CAP/acceptance status
is promoted by these files.

Installed authority: serverDZ.cfg (SHA-256
2a6d24d89f61939fe0310342a83bfd55cefdbf1dfaa191ee3bffc6aa07e7f295);
the original db\messages.xml includes the same deadline/shutdown XML example;
the shipped server_manager\Server_manager.ps1 uses config/profiles/BattlEye/log
launch arguments. The manager is read only, not invoked (it also contains update
and mod-management operations outside this scope).

Supplementary official references, available as search-indexed text after earlier
wiki 403 responses: [Server Configuration](https://community.bistudio.com/wiki/DayZ:Server_Configuration)
documents mission/storage/profiles arguments, and
[Server Messages](https://community.bistudio.com/wiki/DayZ:Server_Messages)
documents scheduled graceful shutdown. These references support preparation,
not this machine's runtime behavior.
