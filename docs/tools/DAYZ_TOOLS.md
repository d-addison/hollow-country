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
| ImageToPAA / `ImageToPAA` | Texture conversion | Original icons and CC0 asset maps | **To verify natively**: `ImageToPAA.exe <source.tga> <destination.paa>`; exact commands/logs below |
| CeEditor / `CeEditor` | Central Economy map editing | Inspect staged loot/event geography | GUI recipe below unverified; no assumed headless mode |
| ObjectBuilder / `ObjectBuilder` | Model/LOD editing and inspection | Building selections, memory points and proxies | GUI recipe below unverified; no assumed headless mode |
| NavMeshGenerator / `NavMeshGenerator` | Build navigation meshes | Investigate terrain pathing inputs; no stock replacement shipped | Tool-assisted generation; GUI/CLI launch and flags unverified locally |
| BinMake / `BinMake` | Asset build orchestration | No current pipeline adoption; preserve deterministic Python packer | CLI unverified |
| AddonBuilder / `AddonBuilder` | Build addon PBOs with asset processing | Native comparison; deterministic Python packer ships sealed ODOL | **To verify natively**: source/destination, `-project`, `-temp`, `-binarize`; exact commands/logs below |
| DsUtils / `DsUtils` | Signatures and key utilities | Existing release signing process only | CLI/GUI unverified; never open private keys during inspection |
| PboUtils / `PboUtils` | PBO archive utilities | Read-only listing/inspection, local outputs only | CLI unverified; project also has stored-PBO reader |
| Publisher / `Publisher` | Workshop publication | Owner-approved release only | GUI/automation unverified; never part of preland |
| TerrainBuilder / `TerrainBuilder` | Terrain authoring | No custom terrain maintained; optional inspection | GUI unverified |
| WorkDrive / `WorkDrive` | Prepare/mount development data drive | Optional local P: setup for asset tools | CLI/GUI unverified; do not change drive mappings automatically |
| Binarize / `Binarize` | Asset binarization | Required ODOL proof for the tin-can lantern | **To verify natively**: source/destination/mask, `-textures`, candidate `-binPath`; exact commands/logs below |
| TerrainProcessor / `TerrainProcessor` | Procedural terrain processing | Not needed for our existing Chernarus mission overlays | GUI/CLI unverified |
| Launcher / `Launcher` | Tool launch/setup entry point | Manual development environment setup | GUI unverified |

## Asset tool commands: to verify natively

**Every command in this section is to verify natively.** No native receipt was
produced by this worker. The lead must take the shared native host lock, confirm
that the owner is idle, and run these serially. Use a fresh Windows-local cache;
never run Binarize against the checkout or an entire shared project drive.
Prepare `src\HollowCountryAssets` with the authored MLOD, `model.cfg`, config,
rvmats and original/CC0 TGA maps. Preserve the own-prefix directory structure.
The filenames below define the staging convention; map the lantern worker's
outputs to those names before running. Dependencies must resolve in this staging
project. Nothing here permits copying installed/Workshop assets into Git.

The [BI Binarize reference](https://community.bistudio.com/wiki/Binarize)
documents positional source/destination/mask and `-textures` (plural), plus the
importance of the working directory. `-binPath` below is a **DayZ candidate flag**,
not established by that wiki: first capture local help and verify its spelling
and support. If refused, record that result and revise the invocation from the
installed tool's usage. Do not call an unknown flag verified.

```powershell
$tools = 'D:\SteamLibrary\steamapps\common\DayZ Tools'
$assetCache = 'C:\hc-asset-cache\lantern-proof-01'
$src = Join-Path $assetCache 'src\HollowCountryAssets'
$dst = Join-Path $assetCache 'binarized\HollowCountryAssets'
$logs = Join-Path $assetCache 'logs'
$null = New-Item -ItemType Directory -Force -Path $logs,$dst
& "$tools\Bin\Binarize\binarize.exe" -help *> "$logs\binarize-help.log"
& "$tools\Bin\ImageToPAA\ImageToPAA.exe" -help *> "$logs\imagetopaa-help.log"
& "$tools\Bin\AddonBuilder\AddonBuilder.exe" -help *> "$logs\addonbuilder-help.log"
```

[ImageToPAA format documentation](https://community.bistudio.com/wiki/ImageToPAA)
and [BI developer CLI usage](https://forums.bohemia.net/forums/topic/166353-how-to-use-imagetopaa/)
provide the source/destination form. Use power-of-two, 8-bit source maps.
Verify all four nonempty PAA files and the asset lint's PAA header/size checks;
normal-map channel convention still needs a native visual check.

```powershell
foreach ($map in @('co','nohq','smdi','as')) {
    & "$tools\Bin\ImageToPAA\ImageToPAA.exe" "$src\data\lantern_$map.tga" "$src\data\lantern_$map.paa" *> "$logs\imagetopaa-$map.log"
    if ($LASTEXITCODE -ne 0) { throw 'ImageToPAA refused' }
}
Push-Location (Join-Path $assetCache 'src')
try {
    & "$tools\Bin\Binarize\binarize.exe" "-textures=$assetCache\binarized" "-binPath=$tools\Bin\Binarize" "-addon=$assetCache\src" $src $dst '*.p3d' *> "$logs\binarize.log"
    if ($LASTEXITCODE -ne 0) { throw 'Binarize refused' }
} finally { Pop-Location }
```

Expected model: `$dst\models\lantern.p3d`, beginning with `ODOL`.
The offline builder parses the whole model using the clean-room ODOL56 reader;
other ODOL versions fail closed and require a separately scoped reader update.
A `.p3d` suffix or exit zero is insufficient. Copy/admit the resulting ODOL and
PAA bytes into a **new** sealed provenance candidate; do not mutate the original
sealed MLOD candidate. Admit unchanged source config/notice/prefix/model.cfg
alongside them. Binarize's model output does not replace source-coverage checks.

The [BI Addon Builder reference](https://community.bistudio.com/wiki/Addon_Builder)
documents this comparison invocation. AddonBuilder binarizes by default;
`-binarize` selects the executable, while `-packonly` would bypass binarization.
It does not establish an AddonBuilder `-binPath` option. Keep this native output
separate from the Python release packer output; compare members and load results,
not PBO bytes.

```powershell
& "$tools\Bin\AddonBuilder\AddonBuilder.exe" $src "$assetCache\addonbuilder" -clear "-prefix=HollowCountryAssets" "-project=$assetCache\src" "-temp=$assetCache\addonbuilder-temp" "-binarize=$tools\Bin\Binarize\binarize.exe" *> "$logs\addonbuilder.log"
if ($LASTEXITCODE -ne 0) { throw 'AddonBuilder refused' }
```

Expected comparison output: `addonbuilder\HollowCountryAssets.pbo`. All console
logs above are explicitly redirected into `$logs`. Also retain any per-model
`.log`/`.rpt` under `$dst`, the AddonBuilder temp tree and the installed
`Bin\Logs` directory (in particular `AddonBuilder.rpt`) if generated; their exact
native locations remain to verify. Help output, exit codes, output hashes and
read-back/load evidence must be recorded before changing these rows' status.

### Offline scores and opt-in package proof

The shared switch is **`HC_ASSETS_PLAN`**, unset by default. Set it to an absolute
sealed-plan path only for the lead's proof. Python release and compile staging,
and `tools/package/Build-Sign-Verify.ps1`, then add `hollowcountryassets.pbo`
beside animations inside `@HollowCountry/addons`. The compile staging list is
`tools/release/compile_gate.py:stage_release_pbos`. With the switch absent the
legacy catalogue, animation commands and PBO bytes are unchanged. The release
helper builds optional companion assets during `ship_inputs.build_anims`, before
the existing release caller iterates the shared signing catalogue.

The score loop consumes PNG directories with `views.json` (schema and examples
in `tools/assets/score_loop.py`). Front, side, top and three-quarter must have
matching fixed metres/pixel, orthographic cameras and an opaque black frame.
It never aligns/resizes inputs or starts Blender. The existing six-view renderer
uses automatic framing and cannot supply this contract: the lead must prepare
fixed cameras/PNGs separately. Silhouette/edge/palette scores are deterministic;
palette uses foreground-weighted, nearest reference-colour CIE76 Delta E with a
16-colour histogram palette. LOD triangle counts come from the exporter and must
be supplied for every budgeted LOD; PNGs cannot establish mesh complexity.
Edge/palette thresholds require explicit calibration in the reference manifest.

```sh
python3 -B -m tools.assets.score_loop --reference build/lantern/reference --candidates build/lantern/round-1 build/lantern/round-2 --max-iterations 6 --max-renders 24 --max-seconds 120 --out build/lantern/score.json
python3 -B -m tools.package.build_assets_addon --plan build/lantern/plan.json --out build/lantern/packed
python3 -B -m tools.package.pbo verify --prefix HollowCountryAssets build/lantern/packed/addons/HollowCountryAssets.pbo
```

The loop stops on pass, six iterations, two rounds without any normalized metric
improving by more than .01, or its render/wall budget. Four submitted views charge
four renders, even for repeated candidates. Wall time covers scoring in a
cancellable Python worker; earlier rendering time is outside this invocation.
The lead's external rendering driver must separately cap Blender invocations by
remaining time/count. Reports select the best iteration and its worst metric/view
(or LOD for polycount). `engine_verified` is always false, including on pass.
`--allow-mlod` on the standalone packer is offline development only; release
wiring never passes it. Native acceptance remains pending.

Lead-only native sequence from the repository root (substitute absolute native
paths for the environment variables; keep keys external):

```powershell
$null = New-Item -ItemType Directory -Force -Path build/lantern
# HC_BLENDER must point to the lead's pinned Blender 5.2.4 executable.
foreach ($folder in @('config','scripts','extensions','temp')) {
    $null = New-Item -ItemType Directory -Force -Path "$assetCache\blender-$folder"
}
$env:BLENDER_USER_CONFIG = "$assetCache\blender-config"
$env:BLENDER_USER_SCRIPTS = "$assetCache\blender-scripts"
$env:BLENDER_USER_EXTENSIONS = "$assetCache\blender-extensions"
$env:TEMP = "$assetCache\blender-temp"
$env:TMP = $env:TEMP
& $env:HC_BLENDER -b --factory-startup --disable-autoexec --python-exit-code 1 -P tools/assets/blender_ops_script.py -- --recipe assets_src/test/hc_testcube.ops.json --output build/lantern/mesh.json --render *> build/lantern/blender.log
# This exercises the existing cube exporter: mesh.json plus six auto-framed TGA
# views, not the fixed-camera lantern scoring set. Use the lantern recipe once
# authored and prepare its four fixed-camera PNGs before running score_loop.
$env:HC_ASSETS_PLAN = 'C:\hc-asset-cache\lantern-proof-01\plan.json'
python -B -m tools.package.build_assets_addon --plan $env:HC_ASSETS_PLAN --out build/lantern/native-pack
python -B tools/package/sign.py --pbo build/lantern/native-pack/addons/HollowCountryAssets.pbo --tools $tools --private-key $env:HC_PRIVATE_KEY --public-key $env:HC_PUBLIC_KEY --out build/lantern/signed-assets
```

Run these environment changes in a disposable PowerShell session. Use the runner's
isolated setup when integrating the lantern recipe. Expected
pack/sign outputs are `addons/HollowCountryAssets.pbo`, its `.bisign`, a public
`.bikey`, `signing-report.json` and `verification.log` with a positive exact
signature result. No private key contents are read or printed by this recipe.
Run the native compile gate serially from WSL after preparing the same sealed
plan with WSL-readable absolute paths:

```sh
HC_ASSETS_PLAN=/mnt/c/hc-asset-cache/lantern-proof-01/plan.json agent-run --memory 12G -- python3 -B -m tools.release.compile_gate --tree .
```

Expected gate result is Mission loaded and assets listed among staged PBOs.
For a normal load, install the signed assets PBO/signature beside the existing
animations in an isolated signed proof bundle, then use the existing boot helper
(the bundle's server launcher loads `@HollowCountry`):

```sh
python3 -B -m tools.release.checkstart --bundle 'C:\hc-asset-cache\lantern-proof-01\bundle' --server-root 'C:\hc-asset-cache\lantern-proof-01\server' --profiles /mnt/c/hc-asset-cache/lantern-proof-01/server/profiles --start
```

The bundle must already contain its mission/dependencies and valid launcher
configuration. Join with at most one client loading the identical signed addon;
spawn the lantern, hold it and toggle its light using the authored actions.
Require zero script/VM errors, missing textures and missing models, correct
materials/light, and the feature's `[HC Use]` evidence. Record the actual item
class/actions when the lantern worker supplies them. This worker neither starts
that load nor claims it passed; multiplayer remains unproven.

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
interop or tool files print `skipped:` with the reason, never a pass. The converter
wrapper logs and retries one explicit WSL vsock connection failure, where
PowerShell did not start. The shared `winproc.run` previously collapsed that
failure, empty replies and timeouts into a generic skip with retries disabled.
An empty reply now identifies the unknown execution state and is not replayed;
real compiler refusals and missing/invalid RAP receipts are never retried.
Each native process has a 30-second limit. A native timeout fails the check;
the process is left running and its scratch tree retained, without force-killing.
The outer interop call has a 60-second limit; its timeout also fails without retry.
A prior config failure takes precedence over a later skip.

Preland runs Enforce lint with the pinned native cache argument, performance lint,
layout lint, config gate, settings consistency and wiring audit, in that order.
`--wb` appends `tools.release.wb_compile` with its default arguments if present.
Missing layout/Workbench modules report `not available`; missing required Python
gates fail. Other launch failures, timeouts and nonzero exits fail, while config
unavailability remains incomplete. The summary states each result and scope.
Changed mode includes committed differences from BASE, staged/unstaged edits and
untracked files. Config checks select affected addons even for deleted includes.
Performance, Enforce, layout, settings and wiring checks retain full-tree scope.
Changed Python files also select mapped tooling unit-test modules. Preland does
not run the full unit suite, start game processes, or replace the native
compile/boot gate.

Preland's installed-input checks are host-only. Without their inputs a local
run is incomplete (exit 3); `--strict` fails the missing coverage. The CI profile
lists these rows as explicit exclusions.

| Check | Host input |
| --- | --- |
| `cfgconvert_check` | Installed Windows CfgConvert and working WSL interop |
| `ce_slot_pressure` | Staged mission via `--ce-mission` or `HC_CE_MISSION` |
| `overlay_vanilla` | Vanilla source mission (the friendcycle `--mission`) via `--overlay-mission` or `HC_OVERLAY_MISSION`; never the installed mission, which already carries our overlays |
| `world_mesh_audit` | Installed vanilla Addons via `--addons` |
| `wb_compile` (opt-in `--wb`) | Installed Workbench; separate lead compile gate |

`overlay_vanilla` reuses `friendcycle.overlay_vanilla_check` against the current
working tree, including uncommitted overlay edits. It runs the same
`friend_bundle check-overlays` path as release builds, rolling back installed HC
overlays on a scratch mission copy before validating against vanilla rows. The
host mission is read only. The check retains full-tree scope with `--changed`.
For example:

```sh
HC_CE_MISSION=/path/to/staged/mission python3 -B -m tools.validate.preland --changed origin/dev
```

Friendcycle requires the running checkout's HEAD to equal the resolved `--commit`
and its `tools/release` and `tools/package` directories to have no tracked or
untracked changes. It refuses before taking the host lock or setting up a build
with “run friendcycle from a clean worktree at the candidate commit”. This small
guard keeps the existing clean build worktrees and avoids changing which Python
driver performs release verification.

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
gate's documented options for the lead's isolated server (the gate is the Python module
`tools.release.compile_gate`; there is no `compile_gate.sh`). Record compile and boot/readiness evidence
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
