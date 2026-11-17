Verdict: **MERGE-WITH-FIXES**.

Review identity **hc-interior-review-004**, reviewing `88054db30c5526cc4d7c2a961073dc804d9800b9`, parent `73241f6`, with the requested four-file comparison against `9816612`. The three ranked r3 defects are fixed in source. Two smaller implementation gaps remain in the treatment builder. This verdict concerns source/tooling; it grants no native compilation, gameplay, player access or CE acceptance.

Only `scratchpad-review/r4/` was written. No tracked repository file, git metadata, `/mnt/d` content, runtime or `.banso-writer/` was edited. No DayZ, Wine, PowerShell, deployment, publishing, lifecycle operation or delegation was invoked. AGENTS.md, the runtime contract, the prior review and its scripts were read. `docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md` are absent; `docs/README.md` says internal specifications are excluded from Git. No spec/plan/tasks artifacts were available. Banso CLI dispatched-worker guidance was applied to this confined review. Synthetic fixtures remain synthetic.

**Ranked findings**

1. **P2 — The builder does not require the selected filter's control to pass.** `tools/audit/interior_points.py:170`, `:173`, `:189`. `_control_state()` is used only for report counts; `_row_codes()` supplies codes regardless of that state. With otherwise valid synthetic census/calibration data, set every tenement control to `control-failed`, `unavailable`, or remove its state. Keeping its hit codes at 1 produces a successful 2,967-byte treatment with **8 small / 4 big** points in every case, for both strict and player sources. The report itself says all four class controls failed/are absent. This violates the explicit control-under-filter requirement. Scope: the current hook prevents this inconsistent combination by returning -1 for a failed control; the reproduction establishes missing builder validation, not a demonstrated native hook path. **Minimal fix:** before counting a reached observation, require `_control_state(row, reach_source) == "tested"`; reject contradictory input or count it as unknown while retaining the full usable-placement denominator. Merely dropping failed rows would inflate agreement. Add strict/player failed, missing and other-filter-passed builder regressions.

2. **P2 — A normal reach-source refusal omits the promised report.** `tools/audit/interior_points.py:158`, `:575`, `:583`, `:670`. Requesting `--reach-source player` with a valid legacy census having hits but no `player_codes` raises during `class_candidates`, before the report base exists. `main` returns 1, and `_write_refusal` silently returns because `error.report` is absent. The report and treatment are both absent. Both supplied native archives are this legacy shape, so this is an ordinary migration path, not malformed JSON. **Minimal fix:** establish the report identity/source/error envelope before analysis, attach it to aggregation refusals, and represent uncomputable class funnels explicitly with their refusal reason. Keep refusing treatment and never substitute strict codes. Add a CLI regression asserting the report for a valid legacy census requested as player.

The new review expectations intentionally remain red: **2 tests / 7 subtest failures** (six control-state cases plus missing refusal report). No fix was authored in this read-only review. `new-regressions.log` contains the tracebacks; `reproductions.log` contains end-to-end accepted/refused outputs. The existing player-source tests construct player codes without a player control, explaining why they miss finding 1.

**Disposition of every r3 ranked and carried finding**

FIXED means the original acceptance/measurement reproduction is corrected in source. PARTIAL retains the original review's broader qualification limits. None of these labels accepts an engine experiment.

| Prior finding | Status | Reproduction on 88054db |
| --- | --- | --- |
| r3 P1-1: waist-slot ray authorizes a nontrivial snap/gap | FIXED | Slot point (-0.5,0,0.5) is code 3 under both filters. End-to-end selection has x=0.5,4.5,5.5; none in the enclosed x=-1..-0.2 room. Clear lateral final gaps are also code 3. Authorizing either new branch is killed by tests. |
| r3 P1-2: foreign solid ignored in usable clearance | FIXED | 0.1..2.4 m solid over the floor gives code 3; treatment refuses `Land_Tenement_Small: no eligible candidates`. Owner-ceiling height remains the separate original field. |
| r3 P2-3: start-inside owner contacts create floors/exhaust owner budget | FIXED | Thick owner model has emitted heights `[0.0]`, 24 re-hits, with no phantom 1.15/1.95/2.75 m floors. Near-zero hits consume descent steps/rays, not floors. Step/floor-capped columns give code 3 for eligible-height hits under both filters. |
| Original unknown reachability authorizes loot | FIXED | Unknown tenements with valid calibration refuse `no eligible candidates`; one yes plus three unknown gives 0 eligible. Unknown selected-control states are a separate builder validation gap, finding 1. |
| Original reached point across a wall | PARTIAL | Owner wall and masked owner wall give code 2; no-wall 0.4 m snap now gives 3. r3 slot/endpoint occupancy counterexamples are fixed. 1 cm horizontal and 0.25 m vertical allowances remain explicitly provisional; actor-volume/native connectivity is unaccepted. |
| Original exterior control inside isolated interior | PARTIAL | Internal island and seed projected back inside both give `control-failed`. Low foreign roof gives `control-failed`. High roof above finite sky ray still gives `tested`, stage 12; mocked west-edge mesh accepts seed world (-5.9,20,4999.5). No independent map-boundary, water or neighboring-interior classification was added. Those synthetic responses are not claims of native off-map/water mesh. |
| Original stairs merge floors into phantom averages | FIXED | Stair bridge yields eligible physical heights `[0.0,3.0]`. |
| Original calibration ignores vertical coverage | FIXED | +100 m calibration shift refuses 3D coverage 0.000 despite xz-only 0.571. |
| Original barracks calibration optional | FIXED | Missing barracks refuses and names `Land_Mil_Barracks2`. |
| Original setup ignores path budget | FIXED | Budget 0: 0 mesh samples, 0 FindPath calls, strict/player counters both 0. |
| Review 002: nearer object hides wall | FIXED | Owner wall alone code 2; same wall masked by closer foreign wall code 2. |
| Review 002: <=5 cm snap skips wall | FIXED | Four-centimetre wall snap gives code 2. The new 1 cm trivial allowance remains provisional, not an assertion that every nonzero displacement is checked. |
| Review 002: final 40 cm gap skips obstruction | FIXED | Original final-gap wall fixture gives code 0; clear nontrivial gap remains unqualified, code 3. |
| Review 002: other object's roof ignored by sky check | FIXED for original reproduction | Original low foreign roof gives `control-failed`; finite-height limitation remains PARTIAL as recorded in the exterior-control row. |

The r3 diagnostic-compatibility fixture concern remains **OPEN**: `tests/unit/test_interior_points.py:405` still uses a vector as the first attempt field, where the sampler emits an integer door index. It tests tolerance of extra keys, not native diagnostic schema validity. It is a test-fixture correction, not an additional gameplay blocker.

**Hook generation, compile shape and main-base staging**

Fixture targets regenerate **54,595 bytes**, SHA-256 **1fb0c5ecb5cb84be1eb650cc0dd1d0d143dedf9107321d2db6e1cc9ff0eb2f34** on this base: exactly the worker's claimed hash. Run 002's literal targets and archived limits regenerate **54,590 bytes**, SHA-256 **16a04d1dbfd620e3029a0bea2fb6dcdfb25021cdb9694efa521eaf688a3ef103**. A hash without its target/limit set is ambiguous.

Both generated hooks pass current `probe_runtime.lint_hook` and `lint_sampler_hook` with the installed native type names. Independent lexical scanning of the archive-target hook, stripping strings/comments and splitting syntax statements regardless of formatting, finds **959 statement fragments**, maximum **8 binary '+'**, at generated lines 1228,1231,1235,1251. No over-limit statement, leading boolean operator, ternary, duplicate local/parameter or native-type identifier collision was found across **54 methods**. The fixture and archive-target versions have the same code shape. All numbers entering strings pass through HCProbeInt/HCProbeNum using `.ToString()`; the strict-string behavioral tests pass. All out arguments are declared before calls. The only override is parameterless `OnInit()`, matching `MissionServer.OnInit()`; no override parameter-name mismatch exists.

Synthetic staging through the unchanged main-base `probe_runtime`/`diagnostic_mission` stack produces `staged-only-not-launched`; appended hook bytes equal the rendered bytes exactly, its plan hash agrees, and launcher validation returns `[]`. `stage-audit.log` records both hashes and byte counts. Installed APIs plus lint are source checks; neither archive compiled this new hook.

Every external call was reconciled with the exact installed snapshot `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`. `api-audit.log` preserves declarations; `api-constants.log` preserves flags/constants. Paths below are relative to that cache.

| API / constant | Installed file:line |
| --- | --- |
| GetGame | `3_Game/gameplay.c:636` |
| GetObjectsAtPosition3D, GetWorld, GetWorldName, GetVersion | `3_Game/Global/Game.c:930`, `:931`, `:932`, `:942` |
| IsServer, SurfaceY, GetTime, GetCallQueue | `3_Game/Global/Game.c:1120`, `:1176`, `:1535`, `:1550` |
| GetAIWorld | `3_Game/Global/World.c:116` |
| RaycastRV, ObjIntersectGeom/View/Fire/IFire | `3_Game/Global/DayZPhysics.c:199`, documented engine values `:67`–`:70`; ray default radius is 0.0 |
| PGFilter / GetIncludeFlags / GetExcludeFlags / GetExlusiveFlags / SetFlags / SetCost | `3_Game/AI/AIWorld.c:59`, `:62`, `:63`, `:64`, `:65`, `:67` |
| FindPath, SampleNavmeshPosition | `3_Game/AI/AIWorld.c:98`, `:122` |
| PGPolyFlags NONE/WALK/DISABLED/DOOR/INSIDE/SWIM/SWIM_SEA | `3_Game/AI/AIWorld.c:3`, `:5`, `:6`, `:7`, `:8`, `:10`, `:11` |
| LADDER/JUMP_OVER/JUMP_DOWN/CLIMB/CRAWL/CROUCH/UNREACHABLE/ALL/JUMP/SPECIAL | `3_Game/AI/AIWorld.c:13`, `:14`, `:15`, `:16`, `:17`, `:18`, `:20`, `:22`, `:24`, `:25` |
| PGAreaType.DOOR_CLOSED | `3_Game/AI/AIWorld.c:47` |
| GetDoorCount, GetDoorSoundPos | `3_Game/Entities/Building.c:31`, `:73` |
| GetPosition, GetOrientation, ClippingInfo, GetType | `3_Game/Entities/Object.c:287`, `:305`, `:358`, `:467` |
| CoordToParent, CoordToLocal, GetParent | `1_Core/proto/EnEntity.c:473`, `:499`, `:571` |
| Cast; array Count/Clear/Set/Get/Insert; set Count/Find/Get; TVectorArray | `1_Core/proto/EnScript.c:94`, `:380`, `:385`, `:389`, `:399`, `:407`, `:743`, `:749`, `:750`, `:738` |
| int.ToString, AsciiToString, float.ToString, vector.Distance | `1_Core/proto/EnConvert.c:30`, `:44`, `:115`, `:196` |
| Substring, Replace, Length | `1_Core/proto/EnString.c:113`, `:156`, `:199` |
| AbsFloat, Sqrt, Vector | `1_Core/proto/EnMath.c:225`, `:305`; `1_Core/proto/EnMath3D.c:18` |
| FileExist, OpenFile, CloseFile, FPrintln, MakeDirectory | `1_Core/proto/EnSystem.c:397`, `:417`, `:443`, `:481`, `:525` |
| FileMode.WRITE/APPEND, FileHandle | `1_Core/proto/EnSystem.c:385`, `:386`, `:390` |
| Print, CallLater, super.OnInit | `1_Core/proto/EnDebug.c:96`; `2_GameLib/tools.c:61`; `5_Mission/mission/missionServer.c:85` |
| CALL_CATEGORY_SYSTEM, FLT_MAX, CollisionFlags.NEARESTCONTACT | `3_Game/tools/tools.c:8`; `1_Core/proto/EnScript.c:4` (engine predefined, also used at `EnConvert.c:112`); `1_Core/proto/EnDebug.c:144` |

No missing or mismatched API was found. The player filter includes WALK|DOOR|INSIDE|JUMP|CLIMB|CROUCH|LADDER and excludes DISABLED|UNREACHABLE|SWIM|SWIM_SEA. Strict flags remain unchanged. Both set DOOR_CLOSED cost 1000 and exclusive NONE. Installed declarations expose those symbols and bitmask APIs; they do not establish actor traversal or runtime flag values. The hook records actual flag values/getters in its census header.

**Sampling, unknowns and bounded work**

The roof test still requires an owner collision above the sampled owner surface. Ordinary unroofed tops and a foreign roof alone cannot supply that owner ceiling. The new first-hit free-clearance check rejects owner/foreign obstruction below 1.9 m independently of owner ceiling. Nontrivial horizontal projection or path-end gaps cannot become code 1 through a zero-radius ray. Synthetic wall/slot/solid regressions now pass. These checks do not classify enclosed rooms vs covered exterior galleries/ledges, validate a player's whole swept volume, or prove access through native doors, ladders and stance links. No new native experiment exists to establish those remaining geometry/filter assumptions. Bounds/water/finite sky issues remain qualified as above.

Hit codes -1 and 3 never independently authorize an eligible point. Code 3 is counted in reach_unqualified and the tested denominator, not yes; successful reach agreement still uses the full usable cohort. Unknown control states, however, can authorize known codes in the builder (finding 1). Each filter has separate control state, entrance, attempts and a separate path budget; rays and run output remain shared. Path budget includes setup samples. Re-hits now spend step/ray work but no owner-floor budget. All search/descent/clearance/diagnostic loops remain bounded: targets<=64, doors<=4, standoff attempts<=30, column steps<=512, nominal floors<=64, clearance attempts<=16, foreign type names<=16, diagnostic columns<=3 with <=32 trace entries.

reach_diag has **2 variants x 13 reasons x at most 8 samples = 208 retained samples per placement**. Counts may exceed eight but samples do not grow. Type strings are truncated to 96 characters; samples have fixed fields. The default synthetic row has 2,963 diagnostic bytes and exactly 59 classified high-clearance candidates per variant. Path=3 stops both counters at 3; step=3 and floor=2 produce only code 3 / unknown rows. A zero ray budget sets ray_capped and produces no hits. The declared output_limit is a hit-emission threshold, not an exact whole-file byte cap: headers/tails/bounded diagnostics are appended separately. It remains bounded overhead, not an unbounded diagnostic accumulator. Benchmark/performance promises remain pending target-load measurement.

The `unknown-ray-clear` mutant survives: **211 interior tests pass both before and after that mutation**, excluding only the worker mutation meta-test. Its current production effect is contained: HCProbeBlocked is called by the nontrivial-gap branch, whose clear result is still stage 6 / code 3; an unknown ray also latches ray_capped, excluding the whole row in the builder. Direct execution confirms baseline Blocked=True on unknown, mutant hit code=3 with ray_capped=True. Thus the worker's no-eligibility-effect claim is supported for current call sites. Add a direct fail-closed helper test before reusing this helper where a clear result can authorize anything.

**Mutation strength**

The independent runner mutates source in memory, stores mutated sources/logs beneath r4, and executes 91 existing behavioral tests per case. The baseline passes. It does not invoke the worker mutation runner. **24 mutants: 23 killed / 1 survived**. The final two anchors were corrected in a separate runner; initial anchor mismatches are retained in the first log and are not counted as mutants.

| Mutation | Result |
| --- | --- |
| snap-authorized | KILLED |
| gap-authorized | KILLED |
| free-clearance-disabled | KILLED |
| owner-rehits-counted | KILLED |
| column-cap-eligible | KILLED |
| samples-unbounded | KILLED |
| samples-one-short | KILLED |
| player-budget-shared | KILLED |
| player-budget-disabled | KILLED |
| strict-budget-disabled | KILLED |
| player-state-uses-strict | KILLED |
| player-path-uses-strict | KILLED |
| snap-vertical-disabled | KILLED |
| gap-vertical-disabled | KILLED |
| unknown-ray-clear | SURVIVED |
| far-control-altitude | KILLED |
| sloped-gap-ray | KILLED |
| clearance-no-doubling | KILLED |
| rehit-max-raised | KILLED |
| unqualified-as-yes | KILLED |
| unqualified-denominator-removed | KILLED |
| player-source-uses-strict | KILLED |
| unknown-eligible | KILLED |
| refusal-report-removed | KILLED |

The prior far-control-altitude, sloped-gap-ray, upward-clearance-doubling and re-hit-ceiling survivors are now killed. The sloped-gap mutation is rejected by the reference scene's vertical-or-level ray contract; that is offline checking, not native qualification. The previous redundant nonowner-blocks mutation was not repeated because it implements existing behavior. The previous sub-millimetre exemption concern is superseded by the explicitly provisional 1 cm allowance; no physical qualification is inferred from that policy.

**Product rules and supplied native evidence**

Using actual stock XML read from the sole permitted `/mnt/d` file, with explicitly synthetic selections, the writer changes only the two tenement group byte ranges. Bytes outside are identical. Output parses; 10 seeded placement/hit permutations produce identical treatment. Small tenement has 8 unique coordinates and lootmax 2; big has 4 unique coordinates and lootmax 1. Only lootFloor has points; shelf/weapon containers remain zero. Existing points/limits are still refused. No new loot spawner, inventory authority, teleport, door blocking or gameplay controller was added. These are XML/source checks, not CE ingestion or player-reach acceptance.

Archives 001 and 002 remain `observed-not-accepted`, with sentinel-seen, no crash logs and exit code -1. Their hooks have hashes 035823a9... and b56f2abb..., respectively, and neither is the current hook. Archive 002 has 14 tested / 2 failed controls, 215,502 rays, 124,297 re-hits, 32 step-capped and 1,458 floor-capped columns. Those old measurements do not validate the newly changed descent logic. Current builder still refuses both native censuses at calibration 0.6 with HouseBlock 3D coverage 0.000. No native treatment was produced. Both lack player_codes. No missing experiment was marked accepted.

**Commands and actual output**

Read-only inspection used `cat AGENTS.md`, the two missing specification paths, `cat docs/README.md docs/RUNTIME_IMPLEMENTATION_CONTRACT.md`, `git show 88054db`, the requested `git diff 9816612 88054db -- tools/setup/interior_sampler.py tools/audit/interior_points.py tests/unit/test_interior_sampler.py tests/unit/test_interior_points.py`, `git show --format=fuller --no-patch 88054db`, `rg`, `sed`, `nl -ba`, and standard-library reads of the prior review, installed source and permitted archives/XML. The complete reviewed patch and four-file diff are retained in `reviewed-commit.patch` and `round3-diff.patch`. Missing specs reported `No such file or directory`.

The first exact full-discovery run on the worktree, with TMPDIR confined under r4, produced:

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/scratchpad-review/r4" python3 -m unittest discover -s tests/unit -v
```
```text
Ran 2573 tests in 95.533s
FAILED (failures=43, errors=287, skipped=1)
```

Those failures include expected refusal of output/temp paths under the source checkout. To exercise the interior stager and CLI without modifying source, I copied the 304 tracked source files under `r4/source-copy`, keeping temp files in sibling `r4/tmp`. `prepare_sources.py` recreates that copy; no git metadata is copied. An unmodified full-discovery run there produced:

```sh
cd scratchpad-review/r4/source-copy
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/code/hc-worktrees/interior-r3/scratchpad-review/r4/tmp python3 -m unittest discover -s tests/unit -v
```
```text
Ran 2573 tests in 98.200s
FAILED (failures=1, errors=155, skipped=1)
```

Every remaining failure/error is in unrelated deployment/fuel/native-startup tooling that checks *all ancestor Git checkouts* and refuses the confined temp paths. I did not weaken those guards or use external writable directories. Full suite output is retained in `full-unit-tests.log` and `full-unit-tests-source-copy.log`; there is no claim of a green repository-wide run.

The focused unmodified source-copy run exercises all four interior/shared modules, including the worker's mutation meta-test:

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/code/hc-worktrees/interior-r3/scratchpad-review/r4/tmp python3 -m unittest tests.unit.test_interior_sampler tests.unit.test_interior_points tests.unit.test_probe_runtime tests.unit.test_diagnostic_mission -v
```
```text
Ran 306 tests in 46.787s
OK
```

From the worktree root, reviewer scripts were invoked with `PYTHONDONTWRITEBYTECODE=1` and, for scripts using temporary files, `TMPDIR="$PWD/scratchpad-review/r4/tmp"`. Each writes only beneath r4. The generated source copy may be removed after use; run `python3 scratchpad-review/r4/prepare_sources.py` to recreate it.

```sh
python3 scratchpad-review/r4/audit.py
```
```text
fixture sha256 1fb0c5ecb5cb84be1eb650cc0dd1d0d143dedf9107321d2db6e1cc9ff0eb2f34 bytes 54595
shared lint: []
sampler lint: []
archive-targets sha256 16a04d1dbfd620e3029a0bea2fb6dcdfb25021cdb9694efa521eaf688a3ef103 bytes 54590
shared lint: []
sampler lint: []
```

```sh
python3 scratchpad-review/r4/compile_shape.py scratchpad-review/r4/archive-targets-hook.c
```
```text
Targets: 16 statements: 959 maximum binary plus: 8
Statements with 8 plus (generated lines): [1228, 1231, 1235, 1251]
Statements over 8: []
Leading boolean operators: []
Ternary tokens: []
Methods checked: 54 duplicate local/parameter names: [] native type name collisions: []
Out call: HCProbeRay RaycastRV line 288 [('contactPos', True), ('contactDir', True), ('contactComponent', True)]
Out call: HCProbeSampleMesh SampleNavmeshPosition line 507 [('sampled', True)]
Out call: HCProbePath FindPath line 519 [('waypoints', True)]
Out call: HCProbeBeginBuilding GetObjectsAtPosition3D line 1121 [('candidates', True), ('candidateCargos', True)]
Out call: HCProbeBeginBuilding ClippingInfo line 1207 [('clip', True)]
Out call: HCProbeStart GetWorldName line 1330 [('world', True)]
Out call: HCProbeStart GetVersion line 1331 [('version', True)]
Numeric JSON: HCProbeInt/HCProbeNum each return value.ToString(); strict-string behavioral suite is also run.
External calls: ['AbsFloat', 'AsciiToString', 'CallLater', 'Cast', 'Clear', 'ClippingInfo', 'CloseFile', 'CoordToLocal', 'CoordToParent', 'Count', 'Distance', 'FPrintln', 'FileExist', 'Find', 'FindPath', 'Get', 'GetAIWorld', 'GetCallQueue', 'GetDoorCount', 'GetDoorSoundPos', 'GetExcludeFlags', 'GetExlusiveFlags', 'GetGame', 'GetIncludeFlags', 'GetObjectsAtPosition3D', 'GetOrientation', 'GetParent', 'GetPosition', 'GetTime', 'GetType', 'GetVersion', 'GetWorld', 'GetWorldName', 'Insert', 'IsServer', 'Length', 'MakeDirectory', 'OnInit', 'OpenFile', 'Print', 'RaycastRV', 'Replace', 'SampleNavmeshPosition', 'Set', 'SetCost', 'SetFlags', 'Sqrt', 'Substring', 'SurfaceY', 'ToString', 'Vector']
```

```sh
python3 scratchpad-review/r4/stage_audit.py
```
```text
Synthetic stage, current shared runtime; status: staged-only-not-launched
Rendered hook: 54595 1fb0c5ecb5cb84be1eb650cc0dd1d0d143dedf9107321d2db6e1cc9ff0eb2f34
Staged hook: 54595 1fb0c5ecb5cb84be1eb650cc0dd1d0d143dedf9107321d2db6e1cc9ff0eb2f34
Byte-identical: True plan hash matches: True
Launcher problems: []
```

```sh
python3 scratchpad-review/r4/reproductions.py
```
```text
owner-wall 2
masked-owner-wall 2
four-centimetre-wall-snap 2
40cm-final-gap-wall 0
foreign-roof-low control-failed
r3-waist-slot 3
r3-waist-slot selected [(0.5, 0.0, -2.5), (0.5, 0.0, 1.5), (4.5, 0.0, 1.5), (5.5, 0.0, -2.5)]
r3-solid-block 3
r3-solid-block REFUSED Land_Tenement_Small: no eligible candidates (usable placements 4, reachability known, source strict; unknown reachability never enters treatment)
r3-owner-rehits heights [0.0] rehits 24
prior snap-wall codes [2, 3, 2]
prior snap-distance codes [2, 3]
prior internal-island control control-failed
prior projected-inside control control-failed
prior zero-budget samples 0 paths 0 variant counters 0 0
unknown-tenements REFUSED Land_Tenement_Small: no eligible candidates (usable placements 4, reachability unknown, source strict; unknown reachability never enters treatment); Land_Tenement_Big: no eligible candidates (usable placements 4, reachability unknown, source strict; unknown reachability never enters treatment)
one-yes-three-unknown 0
vertical-calibration+100 REFUSED calibration vertical (3D) coverage 0.000 (Land_HouseBlock_2F1, radius 0.5, xz-only 0.571) is below the threshold 0.400
missing-barracks REFUSED calibration data missing for Land_Mil_Barracks2 (no usable placement); every calibration class is required
stair-bridge [0.0, 3.0]
strict:control-failed ACCEPTED 2967 bytes; selected {'Land_Tenement_Small': 8, 'Land_Tenement_Big': 4} control_states {'Land_Tenement_Small': {'control-failed': 4}, 'Land_Tenement_Big': {'control-failed': 4}}
strict:unavailable ACCEPTED 2967 bytes; selected {'Land_Tenement_Small': 8, 'Land_Tenement_Big': 4} control_states {'Land_Tenement_Small': {'unavailable': 4}, 'Land_Tenement_Big': {'unavailable': 4}}
strict:None ACCEPTED 2967 bytes; selected {'Land_Tenement_Small': 8, 'Land_Tenement_Big': 4} control_states {'Land_Tenement_Small': {'absent': 4}, 'Land_Tenement_Big': {'absent': 4}}
player:control-failed ACCEPTED 2967 bytes; selected {'Land_Tenement_Small': 8, 'Land_Tenement_Big': 4} control_states {'Land_Tenement_Small': {'control-failed': 4}, 'Land_Tenement_Big': {'control-failed': 4}}
player:unavailable ACCEPTED 2967 bytes; selected {'Land_Tenement_Small': 8, 'Land_Tenement_Big': 4} control_states {'Land_Tenement_Small': {'unavailable': 4}, 'Land_Tenement_Big': {'unavailable': 4}}
player:None ACCEPTED 2967 bytes; selected {'Land_Tenement_Small': 8, 'Land_Tenement_Big': 4} control_states {'Land_Tenement_Small': {'absent': 4}, 'Land_Tenement_Big': {'absent': 4}}
foreign-roof-above-finite-sky tested [12]
map-edge-mocked-mesh tested (-5.9, 20.0, 4999.5)
```

```sh
python3 scratchpad-review/r4/semantic_audit.py
```
```text
default control tested tested codes {0: 22, 1: 35, 3: 1, -1: 2, 2: 1} player {0: 22, 1: 35, 3: 1, -1: 2, 2: 1} paths 59 59 mesh_calls 236 ray_capped False
diagnostics bytes 2963 max samples 8
diagnostic counts equal candidates: {'strict': 59, 'player': 59} candidates 59
path0 control path-budget path-budget codes {-1: 61} player {-1: 61} paths 0 0 mesh_calls 0 ray_capped False
path3 control tested tested codes {0: 1, 1: 1, -1: 58, 3: 1} player {0: 1, 1: 1, -1: 58, 3: 1} paths 3 3 mesh_calls 14 ray_capped False
step3 control tested tested codes {3: 38, -1: 1} player {3: 38, -1: 1} paths 1 1 mesh_calls 6 ray_capped False
floor2 control tested tested codes {3: 39, -1: 1} player {3: 39, -1: 1} paths 1 1 mesh_calls 6 ray_capped False
ray0 control control-failed control-failed codes {} player {} paths 1 1 mesh_calls 2 ray_capped True
unknown direct baseline Blocked: True row-capped: True
unknown-ray-clear mutant hit code: 3 row-capped: True
```

```sh
python3 scratchpad-review/r4/product_checks.py
```
```text
real stock writer + explicit synthetic selections: bytes 1230695 hash 5ae3afe8efe089ee282bc810259c9ccff9998e197f4e844236d5717ef5ae223b changed ['Land_Tenement_Big', 'Land_Tenement_Small']
outside bytes identical True
10 seeded permutations of placements/hits produce identical treatment: True [True, True, True, True, True, True, True, True, True, True]
Land_Tenement_Small points 8 unique coordinates 8 group lootmax 2 containers [('lootFloor', '2', 8), ('lootshelves', '0', 0), ('lootweapons', '0', 0)]
Land_Tenement_Big points 4 unique coordinates 4 group lootmax 1 containers [('lootFloor', '1', 4), ('lootshelves', '0', 0), ('lootweapons', '0', 0)]
```

```sh
python3 scratchpad-review/r4/survivor_check.py
```
```text
all-interior-baseline tests 211 failures 0 errors 0
all-interior-unknown-ray-clear tests 211 failures 0 errors 0
```

Additional commands and full outputs:

- `python3 scratchpad-review/r4/api_audit.py` → `api-audit.log` (installed declarations shown in the API table).
- `python3 scratchpad-review/r4/native_audit.py` → `native-audit.log` (archive summaries, refusals and sentinels).
- `python3 scratchpad-review/r4/mutations.py` → `mutations.log`, `mutation-results.json`, per-mutant sources and test tracebacks.
- `python3 scratchpad-review/r4/mutations_extra.py` → `mutations-extra.log`, `mutation-results-extra.json` (two corrected anchors; both killed).
- `python3 scratchpad-review/r4/new_regressions.py` → `new-regressions.log`: `Ran 2 tests in 0.028s`, `FAILED (failures=7)`; the two intentionally red review expectations above.
- `GIT_OPTIONAL_LOCKS=0 git diff --exit-code --no-ext-diff` and `GIT_OPTIONAL_LOCKS=0 git diff --cached --exit-code --no-ext-diff` → empty output, exit 0.

Source/native acceptance remains pending DayZDiag and normal PBO/server testing. The verdict does not require connecting a client before the two source/tooling fixes can be authored.
