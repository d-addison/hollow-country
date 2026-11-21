# DayZDiag source development loop

This WSL helper plans an isolated DayZDiag server and **one** DayZDiag client. It
uses the current checkout, not a release bundle. Native boot, file resolution,
script reload and debugger attachment remain **pending lead observation** on
DayZ 1.30.164289. Python tests do not establish DayZ behaviour.

## Run

From the checkout root, print the complete Windows launch script without writing
files, running Windows commands or starting a game:

```sh
python3 -B -m tools.setup.diag_session --plan --tag edit-001
# --plan is also the default
python3 -B -m tools.setup.diag_session --tag edit-001
```

The lead can explicitly stage and launch that plan:

```sh
python3 -B -m tools.setup.diag_session --launch --tag edit-001
```

DayZDiag compiles more strictly than retail. As of 2026-11-21 the Tactical Flava
Workshop script `TF_ActionFlipOptic.c` fails Diag with "Missing function scope"
because it uses a body-less `override typename GetInputType() return ...;`.
We never patch third-party code, so leave that optional pack out of a Diag session:

```sh
python3 -B -m tools.setup.diag_session --launch --tag edit-002 --without @TacticalFlava
```

Only the optional weapon packs (`@TacticalFlava`, `@SnafuWeapons`) can be left out.

A required dependency fails Diag too. Ambient Animals `Seagull_Base.c(110)` has
unmatched brackets ("Unmatched brackets detected!"), and the Expansion AI addon
requires that pack. So the full stack cannot boot under Diag without patching
third-party code. `--core-only` loads only `@HollowCountry` (its requiredAddons are
vanilla), so Diag still strict-compiles every base script:

```sh
python3 -B -m tools.setup.diag_session --launch --tag edit-003 --core-only
```

Observed 2026-11-21 (session full-005, core-only): the Diag server compiled the GameLib,
Game (491 files) and World (2613 files) modules with HollowCountry included, with no
script errors. Then it logged `Player dpid=2 added`, counted down
`[Server] :: termination in: 10..1` and exited cleanly before loading the mission, so
5_Mission was not Diag-compiled and no `[HC Ready]` line was printed. The countdown
is not in vanilla or HollowCountry scripts. The cause and the Diag server boot remain
UNVERIFIED.
The session receipt records them under `without`. Retail boots (checkstart) still
load every dependency.

The fixed destination is `D:\HollowCountryLocal\diag-edit-001`. Choose a new tag
for each launch; an existing destination, including a failed partial stage, is
never reused. Tags cannot contain paths. There is no runtime-directory override.
The helper never writes `E:\HollowCountryLocal\friend-local-1`, bundle directories,
installed engine files or Workshop files. It never stops any process. On failure,
close the processes you started normally and preserve the isolated profiles for
inspection; do not retry an ambiguous launch with another tag while DayZ remains
running.

Prerequisites are the installed paths supplied for this tooling round:

| Input | Location |
| --- | --- |
| Diagnostic executable and client assets | `G:\SteamLibrary\steamapps\common\DayZ` |
| Stock Chernarus mission | `D:\SteamLibrary\steamapps\common\DayZServer\mpmissions\dayzOffline.chernarusplus` |
| Dependency content | `G:\SteamLibrary\steamapps\workshop\content\221100` |
| Workbench | `D:\SteamLibrary\steamapps\common\DayZ Tools\Bin\Workbench\WorkbenchApp.exe` |

Keep Steam available if required by the installed diagnostic build. This is a
local loopback session, not an Internet server: the server command uses
`-ip=127.0.0.1`, the client uses `-connect=127.0.0.1`, and the default game port
is 2402 (query port 2405). `--port 2502` changes both commands and the query port
(to 2505). Actual socket binding remains a native check; this helper installs no
firewall rule and does not forward ports.

Before staging, a bounded Windows process observation must succeed with no
retail/Diag client or DayZ server present. Unknown/failed observation refuses.
Before starting the pair, the Windows script repeats that check under a named
launch mutex. Do not independently launch DayZ during staging. The launcher
starts the server first and waits up to 180 seconds for its isolated RPT to say
`Player connect enabled`. Only then does it request one client. Timeout/server
exit leaves the client unstarted and preserves the server/profile for inspection.
There are no launch retries, even if Windows interop loses the response.
`maxPlayers=1`, `BattlEye=0`, `verifySignatures=0` and `allowFilePatching=1` are
written only to this disposable server configuration. The executable is started
directly, without the BattlEye launcher. This is not suitable for public hosting.

## What is staged

The helper copies the diagnostic executable, its root DLLs and `steam_appid.txt`
into the new runtime. Engine asset directories (`Addons`, `dta`, and installed
terrain/main-menu directories) are Windows junctions back to the installation;
the helper performs no writes through those links. Stock mission configuration
is copied, excluding persistence and logs. The server profile starts with the
repository defaults selected by `friend_bundle.repo_profile_sources()`; the
client profile starts empty. No existing server profile is read.

The shared `tools/setup/workshop_mods.json` selects **all** manifest entries in
rank order. Third-party dependencies are loaded directly from their installed
Workshop folders, read-only to this helper. No dependency is copied or downloaded.
`side=server` entries, if added to the manifest, go only in the server's
`-serverMod`. Published own entries resolve to `mods/<folder without @>` in this
checkout, currently HollowCountry and HollowCountryExpansionAI. Both peers load
the same ordered client-mod list.

The layout is:

```text
D:\HollowCountryLocal\diag-edit-001\
  DayZDiag_x64.exe                 copied; both processes use this executable
  Addons\, dta\, ...               junctions to installed engine assets
  @HollowCountry\addons\hollowcountry.pbo
  @HollowCountryExpansionAI\addons\hollowcountryexpansionai.pbo
  HollowCountry\                  loose repo runtime sources
  HollowCountryExpansionAI\       loose repo runtime sources
  mpmissions\dayzOffline.chernarusplus\
  profiles\server\, profiles\client\
  serverDZ.cfg
  diag-session.json               config hashes and owned loose-file inventory
```

The bootstrap PBOs contain **only `config.cpp`**, using the existing stored-PBO
writer and exact addon prefixes. Scripts, layouts, XML, JSON and lighting text inputs stay
unpacked. Source directories are mirrors, not links into the Linux checkout;
refresh them after editing:

```sh
python3 -B -m tools.setup.diag_session --refresh --tag edit-001
```

Refresh never launches, repacks, changes mission/profile defaults or touches
Workshop. It copies added/changed runtime inputs and removes formerly staged
source files deleted in the checkout. Any addon/config.cpp change requires a
fresh launch tag. Source refresh is permitted while the pair runs, but does not
make the engine re-read a file: use the Script Editor's supported reload action
or reopen the resource/mission; restart with a fresh tag if reload is unavailable
or state/line numbers are inconsistent. Keep the same `--port` when reviewing an
existing session. Quiesce editing while copying; staging/refresh is not an atomic
snapshot against concurrent source edits or hostile directory replacement.

This is a source scripting loop, not release parity. It uses stock CE mission
configuration, without applying the friend installer's generated CE/map overlays.
It does not generate or load the additional HollowCountryAnims addon (its runtime
graph/clips are generated outside Git), or the generated weapon-pack compatibility
PBO. Animation/sway/overlay acceptance requires the normal build pipeline. Source
asset types requiring compilation still need their respective authoring tools.

## File patching: documented versus observed

Bohemia's [Modding Basics](https://community.bistudio.com/wiki/DayZ:Modding_Basics)
describes loading a mod PBO and exposing loose files at its addon prefix beneath
the executable directory, commonly using a junction to `P:\FirstMod`. `P:` is an
authoring drive, not a requirement for this helper: loose mirrors live beside the
copied executable at `HollowCountry\...` and `HollowCountryExpansionAI\...`.
`@HollowCountry` is the mod container; it is not the resource prefix. Both commands
include `-filePatching`. Config changes still require a new bootstrap configuration.

The [server configuration reference](https://community.bohemia.net/wiki/DayZ:Server_Configuration)
documents `allowFilePatching=1` for patching clients. Its launch-parameter table
currently describes `-filePatching` backwards relative to the Modding Basics
example; this tooling follows the tutorial, with native resolution explicitly
unverified. The isolated copied executable, loose-only script-directory discovery,
`-server`/loopback behaviour and config-only bootstrap must all be proved by the
lead. No DayZ `-help` probe was run because **any game process was forbidden**.

Observed in this worker session: installed paths and required dependency folders
exist; default plan resolves them without writes; Windows PowerShell's parser
accepted the generated launch script with `parse_errors=0`. That parser check
**did not execute the launch script**. No game or Workbench process was started.
The installed `dayz.gproj` and existing `HC_TxaBuild.c` pattern were inspected;
they establish neither debugger attachment nor a headless compiler verdict.

## Workbench Script Editor attachment (lead procedure; unverified here)

Prepare the DayZ Tools project drive/native scripts according to Bohemia's
[Workbench Script Debugging](https://community.bistudio.com/wiki/DayZ:Workbench_Script_Debugging)
guide. Use the installed version's sources; keep the pinned native cache at
`~/.cache/hollow-country/native-scripts/scripts-1.30.164289` local. Do not copy it
into Git. The guide describes automatic attachment when Script Editor and
DayZDiag run, then breakpoints and stepping. Verify the connection notification.

After the lead launches the pair, open Workbench from Windows PowerShell:

```powershell
& 'D:\SteamLibrary\steamapps\common\DayZ Tools\Bin\Workbench\WorkbenchApp.exe' `
  '-gproj=D:\SteamLibrary\steamapps\common\DayZ Tools\Bin\Workbench\dayz.gproj' `
  '-filePatching' `
  '-mod=D:\HollowCountryLocal\diag-edit-001\HollowCountry;D:\HollowCountryLocal\diag-edit-001\HollowCountryExpansionAI'
```

Open Script Editor and the staged `.c` file, not a stale copy in another worktree.
Confirm the target is the server for server-owned code or the client for client
presentation. With two Diag instances, inspect the installed UI's target selector;
automatic selection is not a guarantee of the intended peer. Set a breakpoint in
an executable method, trigger it, inspect locals/call stack, add a simple variable
to Watch, step and continue. Watch expressions should not mutate gameplay state.
Exact target-selector/watch labels and shortcuts are **UI checks still pending**;
no speculative debug-port flag is added. If the source is absent from Resource
Browser, fix project source visibility before trusting breakpoints. Keep source
and loaded script versions aligned after refresh/reload. Never leave the server
paused while assessing stalls or performance.

## Diag menu (documented; installed UI unverified)

The [official Diag Menu reference](https://community.bohemia.net/wiki/DayZ:Diag_Menu)
lists `Win+Alt` in a 3D viewport, arrows to select/change values and Backspace to
leave a submenu; `Ctrl+Num9` toggles the pointer.

| Inspection | Menu/action |
| --- | --- |
| Loot volumes | Game → Central Economy → Loot Spawn Edit → Spawn Volume Vis / Setup Vis |
| Navigation | AI → Debug NavMesh; Num0 start, Num4 end, Num5 nearest position, Num6 raycast |
| AI pathing/behaviour | AI → Debug Path Agent / Debug AI Agent; target an AI |
| Camera | Game → Free Camera; WASD, Q/Z, mouse; End returns to player camera |

**Most Central Economy diagnostics require a single-player mission with CE**;
the reference says only Building Stats works in multiplayer/without CE. This
server/client pair cannot prove loot-volume visualization. For CE visualization,
close the pair first and use a separate disposable offline CE mission with one
Diag process. Navmesh visualization is client-side context, not proof of server
AI decisions. Avoid regeneration/export/edit actions during inspection. Keep
FrCam Player Move off; do not use player teleport bindings.

## Logs and lead acceptance

Print a bounded, privacy-filtered snapshot (choose the actual file name locally):

```sh
python3 -B -m tools.setup.diag_session --log /mnt/d/HollowCountryLocal/diag-edit-001/profiles/server/DayZDiag_example.RPT
python3 -B -m tools.setup.diag_session --log /mnt/d/HollowCountryLocal/diag-edit-001/profiles/server/script_example.log
python3 -B -m tools.release.rpt_summary /mnt/d/HollowCountryLocal/diag-edit-001/profiles/server/DayZDiag_example.RPT
```

The helper prints only `[HC ...]` messages and script/compiler errors through the
existing release privacy filter. Oversized lines are discarded. It does not
follow logs or award acceptance; privacy filtering may drop error text. Use
`rpt_summary` separately for the full boot verdict and raw failure detection.
Never share unfiltered RPTs, debugger output, profile data or screenshots with
player/account information in this public repository.

Lead checks still required, with the commands above:

1. Launch one fresh session. Record installed build, exact source revision/dirty
   state and config/PBO hashes. Prove the server and single client actually load
   the staged HC/HCX scripts with clean module readiness and no crash/stall.
2. Change a harmless existing diagnostic string locally, refresh loose sources,
   use the supported reload or a new session, and observe the changed HC output.
   Revert the probe afterwards. Prove layout/data reopening independently; file
   patching is not universal hot reload.
3. Attach Script Editor to each intended peer, hit a breakpoint and inspect a
   watch value. Record target selection and reload behaviour without private data.
4. Inspect camera/navmesh menus; test CE overlays in a separate offline mission.
   Record unavailable menus as deferred, not accepted.
5. Run the existing signed PBO friendcycle build/boot separately. See
   `python3 -B -m tools.release.friendcycle --help` and
   [MOD_DEVELOPMENT.md](../MOD_DEVELOPMENT.md). This helper neither builds a release
   from a clean commit nor writes `BUILD_MANIFEST.json`; its local receipt is not
   a release manifest. Diag iteration complements signature, generated-asset,
   installer and normal-server boot checks. Neither path proves multiplayer.

Focused tooling validation:

```sh
python3 -B -m unittest tests.unit.test_diag_session -v
```

No Enforce files are changed by this implementation. Offline tests cover fake
installs/interop only. Target-load performance remains provisional.

Integration note: the existing `/docs/*` Git ignore rule hides this new document.
The lead must allowlist `docs/tools/` before the writer stages it; this worker
does not own `.gitignore` and cannot write Git metadata.
