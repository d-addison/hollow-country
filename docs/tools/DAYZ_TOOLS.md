# DayZ Tools in Hollow Country

Developer tooling for DayZ 1.30. These checks do not establish gameplay behaviour,
multiplayer correctness, or target-load performance. Native acceptance remains one
server plus at most one client; only the lead starts game/server executables.

## Evidence and installation

On 2026-11-21 this worker observed the installed `Bin` directories listed below
and read `CfgConvert/CPPToBIN.bat`. That batch file invokes
`CfgConvert.exe -bin -dst <output.bin> <source.cpp>`.
An attempted `CfgConvert.exe -help` returned WSL `UtilAcceptVsock / accept4 failed`
instead of usage. A later PowerShell no-argument invocation successfully printed usage, confirming
`-bin`, `-txt`, `-pcpp`, `-xml`, `-test`, `-q`, `-dst` and `-rvmat`.
All three repository addon configs then converted successfully after staging their
addon trees into Windows TEMP. A valid scratch config returned 0 and an
unterminated scratch config returned 1; the latter supplied no usable native line
diagnostic, so the wrapper reported file:1. Direct UNC
conversion was rejected as a validation strategy: inaccessible scratch inputs
silently yielded RAP output and exit 0. PowerShell staging now explicitly fails
when the source cannot be copied. All GUI recipes and untested CLI capabilities
below are **unverified locally**.
Do not infer flags from directory names.

The installation root is `D:\SteamLibrary\steamapps\common\DayZ Tools`;
WSL sees `/mnt/d/SteamLibrary/steamapps/common/DayZ Tools`.
The client is on `G:\SteamLibrary\steamapps\common\DayZ`, the server on
`D:\SteamLibrary\steamapps\common\DayZServer`. Keep local extracts, indexes,
project work drives and outputs outside this public checkout. Never inspect keys.

[Bohemia's tool announcement](https://forums.dayz.com/topic/240636-modding-support-and-tools-initial-release/)
confirms the official tool family. It is historical documentation, not evidence
that a current local invocation works.

## Tool index

“CLI unverified” means no local flags or successful automation were observed here.
GUI tools must be opened deliberately by the lead, outside automated worker gates.

| Binary / Bin directory | Purpose | Hollow Country use | Execution and evidence |
| --- | --- | --- | --- |
| Workbench / `Workbench/WorkbenchApp.exe` | Script, resource and UI development | Compile/resource diagnostics; existing animation plugin | GUI; project-specific headless plugin prior art in `tools/anim/workbench/HC_TxaBuild.c`; no run this round |
| CfgConvert / `CfgConvert/CfgConvert.exe` | Text config ↔ RAP conversion | Config syntax gate; scratch output only | CLI command observed in installed batch file; three native conversions observed through PowerShell with local staging |
| ImageToPAA / `ImageToPAA` | Texture conversion | Original GUI icon textures | CLI/GUI workflow unverified; see icon guide |
| CeEditor / `CeEditor` | Central Economy map editing | Inspect staged loot/event geography | GUI recipe below unverified; no assumed headless mode |
| ObjectBuilder / `ObjectBuilder` | Model/LOD editing and inspection | Building selections, memory points and proxies | GUI recipe below unverified; no assumed headless mode |
| NavMeshGenerator / `NavMeshGenerator` | Build navigation meshes | Investigate terrain pathing inputs; no stock replacement shipped | Tool-assisted generation; GUI/CLI launch and flags unverified locally |
| BinMake / `BinMake` | Asset build orchestration | No current pipeline adoption; preserve deterministic Python packer | CLI unverified |
| AddonBuilder / `AddonBuilder` | Build addon PBOs with asset processing | Manual comparison if needed; current shipping packer remains authoritative | GUI; CLI unverified |
| DsUtils / `DsUtils` | Signatures and key utilities | Existing release signing process only | CLI/GUI unverified; never open private keys during inspection |
| PboUtils / `PboUtils` | PBO archive utilities | Read-only listing/inspection, local outputs only | CLI unverified; project also has stored-PBO reader |
| Publisher / `Publisher` | Workshop publication | Owner-approved release only | GUI/automation unverified; never part of preland |
| TerrainBuilder / `TerrainBuilder` | Terrain authoring | No custom terrain maintained; optional inspection | GUI unverified |
| WorkDrive / `WorkDrive` | Prepare/mount development data drive | Optional local P: setup for asset tools | CLI/GUI unverified; do not change drive mappings automatically |
| Binarize / `Binarize` | Asset binarization | No new asset pipeline introduced here | CLI unverified |
| TerrainProcessor / `TerrainProcessor` | Procedural terrain processing | Not needed for our existing Chernarus mission overlays | GUI/CLI unverified |
| Launcher / `Launcher` | Tool launch/setup entry point | Manual development environment setup | GUI unverified |

## Worker and lead gates

From the checkout root:

```sh
python3 -B -m tools.validate.cfgconvert_check
python3 -B -m tools.validate.preland
python3 -B -m tools.validate.preland --changed origin/main
python3 -B -m tools.validate.preland --wb
python3 -B -m unittest tests.unit.test_cfgconvert_check tests.unit.test_preland
```

`cfgconvert_check` selects every addon `config.cpp` and `model.cfg` under `mods/`.
Include headers are parsed through their owning config; launcher `mod.cpp` and
`meta.cpp` are excluded. Currently no model.cfg is authored; extend the selector
explicitly if another standalone rapifiable format is added. The packer's
`original_addon_name` currently permits `config.cpp`, not model.cfg; the gate's
model support anticipates that future packaging decision rather than changing it.
`tools/package/pbo.py:collect_addon` reads UTF-8 source bytes directly and
`pack` stores them without CfgConvert. Thus the scratch `.bin` is a syntax check,
never substituted into a release PBO. Generated package-time addon configs are
outside this source-tree check and still require lead native validation.

The gate converts WSL paths with `wslpath -w`, calls the absolute Windows
PowerShell executable through `tools.setup.winproc`, writes a unique `.bin` in
Windows TEMP and removes it in `finally`. Source files remain in place so local
includes retain their paths. PowerShell copies the owning addon (including its relative include tree) into a
unique Windows TEMP directory before running CfgConvert against a Windows-local
path. Cross-addon includes are not staged and remain unsupported. Scratch roots
must be accessible from Windows; the container's `/tmp` was not. Successful validation requires a zero tool exit, no detected error
text and a nonempty RAP header. Diagnostics use `file:line`; messages without line
information use line 1. Output passes the existing strict privacy filter.
`--tool /mnt/<drive>/.../CfgConvert.exe` overrides the installation location.
Optional positional repository-relative paths select affected addons; a non-mod
path conservatively selects all configs.

Both commands return 0 on success, 1 on failed checks, and 3 for unavailable
native/optional checks (incomplete). Argparse usage errors return 2. Missing
interop or tool files print `skipped: CfgConvert unavailable`, never a pass.
Each native process has a 30-second limit; the wrapper terminates only the
process it starts and cleans its temporary tree. A native timeout fails the check.
The outer interop call has a 60-second limit. A prior config failure takes precedence over a later skip.

Preland runs Enforce lint with the pinned native cache argument, performance lint,
layout lint, config gate, settings consistency and wiring audit, in that order.
`--wb` appends `tools.release.wb_compile` with its default arguments if present.
Missing layout/Workbench modules report `not available`; missing required Python
gates fail. Other launch failures, timeouts and nonzero exits fail, while config
unavailability remains incomplete. The summary states each result and scope.
Changed mode includes committed differences from BASE, staged/unstaged edits and
untracked files. Performance lint selects existing changed authored `.c` paths;
config checks select affected addons even for deleted includes. Enforce lint,
layout, settings and wiring currently retain full-tree scope because their
observed CLIs do not expose file selection. Preland does not run unit suites,
start game processes, or replace the native compile/boot gate.

Lead follow-up after Windows interop is restored:

```sh
python3 -B -m tools.validate.cfgconvert_check
python3 -B -m tools.validate.preland --wb
python3 -B -m tools.release.compile_gate --help
```

Reproduce conversions, including a deliberately malformed scratch config
outside the repo (use a Windows-visible scratch location and `--root` pointing to a tree containing
`mods/Probe/config.cpp`), to prove diagnostic/exit behaviour. A valid scratch
fixture and a syntax error must produce 0 and 1 respectively. Standalone valid input and all shipped config conversions were observed locally.
Additional include resolution and diagnostic variants remain pending; a RAP file
alone never authorizes a pass without the process receipt and Windows-local input. Use the compile
gate's documented options for the lead's isolated server; `compile_gate.sh` was
absent during this worker's inspection. Record compile and boot/readiness evidence
separately; a green preland does not accept missing engine experiments.

## CeEditor: inspect the staged mission

**Unverified GUI recipe; exact menus/import support must be recorded by the lead.**
Use a disposable copy of the release-staged Chernarus mission, never the live
server profile. The files must be the installed/merged outputs, not just the
append fragments in `mission/hollow-country/ce/`.

1. Copy the staged mission to a local scratch directory. Retain `db/types.xml`,
   `db/events.xml`, `cfgeconomycore.xml`, `cfgeventspawns.xml`,
   `cfgeventgroups.xml`, `mapgroupproto.xml` and `mapgrouppos.xml`, plus every
   custom XML referenced by `cfgeconomycore.xml`. Our custom sources include
   `ce/types.xml`, `ce/events.xml`, `ce/hc-events.xml`, `ce/hc-eventgroups.xml`,
   `ce/hc-eventspawns.xml` and `ce/hc-event-proto.xml` under the HC mission subtree.
2. Launch CeEditor from DayZ Tools. Select the matching Chernarus terrain/project
   using the installed editor's supported open/import controls. Record any
   required project/map assets and rejected file types; do not assume opening a
   mission folder automatically imports these XML files.
3. Load supported loot/event layers from that scratch copy. Join group prototypes
   to world positions by group name; compare a known HC addition and one event
   coordinate against the staged XML. Types describe supply, group proto/pos
   describe candidate points, and event spawn files supply event coordinates.
4. If the editor cannot import types or group XML directly, inspect those files
   beside the map and use supported editor layers for coordinates. Record this
   limitation; do not claim an in-editor loot-point view until it is observed.
5. Save only in scratch. Review any export diff before transferring an authored
   change. A map preview does not prove native spawning, tag matching or access.

## ObjectBuilder: inspect building details

**Unverified GUI recipe.** Resolve a candidate building's model path from the
installed config using the project's existing local inspection workflow. Keep
extracted files under the external cache; stock model redistribution is forbidden.

Open that local model in ObjectBuilder if its format is supported. Inspect the
Memory LOD, named selections, door-related points and any loot/attachment proxy
references. Compare coordinates and transforms with `mission/hollow-country/loot-points/`
inputs and `docs/LOOT_POINTS.md`. Record the model/class, LOD and point names,
without checking in the model. Binarized ODOL models may refuse editing or expose
insufficient detail; do not assume they are editable MLOD or invent missing points.
Fall back to existing native model/loot-point inspection and lead diagnostics.
Visibility in a model viewer does not prove world collision, enclosure or reach.

## NavMeshGenerator: inspect AI pathing inputs

**Unverified local workflow.** Bohemia's
[navigation mesh guide](https://community.bohemia.net/wiki/DayZ%3AGenerating_navigation_mesh)
describes terrain configuration and generation prerequisites. Its generation
workflow needs a working terrain and game involvement, so this worker did not run
it or add guessed CLI flags.

For a recorded stuck-AI location, first identify the stock terrain, building model,
nearby door/jump links and our authored route coordinates. Inspect the installed
NavMeshGenerator UI/help with the lead; record supported inputs and whether it can
load an existing stock mesh before claiming inspection support. Use an isolated
terrain/project copy for any generation experiment, preserve the original mesh,
and leave game launches to the lead. Do not regenerate or ship a replacement
Chernarus navmesh to hide a controller defect. The lead must then check the same
route/door location natively with one server and at most one client; generator
output alone is not pathing acceptance.

## Related recipes

- [Workbench compilation](WORKBENCH_COMPILE.md)
- [DayZDiag](DAYZDIAG.md)
- [GUI icons](GUI_ICONS.md)
- [Layout checks](LAYOUT_CHECK.md)
- [Animation pipeline](../ANIMATION_PIPELINE.md)
- [Mod development](../MOD_DEVELOPMENT.md)

Sibling guides may land independently; follow their recorded evidence and flag
contracts when available.
