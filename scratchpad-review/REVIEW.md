Verdict: **BLOCK**.

Reviewed `68dd22fcbf78013a94a7b06e6b0616a42e6983e8` on `hc/interior-review-2`, plus the launcher kind rows and compile-refusal exit in parent `82d3042`. The four changed files were inspected, and the prior review's reproductions and mutations were rerun against scratch copies of the new sources. This is source review and synthetic testing, not native compilation or DayZ acceptance.

Only `scratchpad-review/` was written. No repository source, git metadata, runtime, or `/mnt/d` file was changed. No DayZ, Wine, PowerShell, staging, deployment, network lookup, or lifecycle command was run. AGENTS.md and the runtime contract were read. Both required specification paths remain absent; `docs/README.md` explains that internal specifications are excluded from Git. The Banso CLI skill's dispatched-worker constraints were applied; no lifecycle state was changed. The supplied worker mutation runner path does not exist in this environment. My runner does not import or rely on it.

**Ranked findings**

1. **P1 — A nearer object can hide the building wall from the snap check.** `tools/setup/interior_sampler.py:317`, called at `:500`; the current test explicitly requires accepting a non-building obstruction at `tests/unit/test_interior_sampler.py:1075`. `HCProbeBlocked` treats ray result `2` as clear. With nearest-contact raycasts, that does not establish that the rest of the segment is clear. Synthetic floor x=-0.5 snaps to connected mesh near x=-0.1 across a building wall at x=-0.2. With that wall alone, the emitted reach code is `2`. Put another object's collision plane at x=-0.3 in front of it: the code becomes `1`. An end-to-end builder run with four explicit synthetic observations selects `(-0.5, 0, 1.5)` across this same wall. **Minimal fix:** conservatively treat every collision on the floor-to-mesh segment as blocked, including non-owner contacts; update the crate expectation and add a nearer-object-plus-building-wall case. Do not skip past solid obstructions to establish player clearance.

2. **P1 — Snaps of 5 cm or less bypass wall validation altogether.** `tools/setup/interior_sampler.py:498`. The squared-distance exemption `> 0.0025` allows a 4 cm snap from x=-0.5 to mesh x=-0.46 through a collision plane at x=-0.48. The hook emits code `1`. Neither the 0.5 m displacement bound nor the endpoint tolerance catches it. **Minimal fix:** check every nonzero physical displacement, or use only a numerical epsilon justified by measurement and refuse uncertain cases. Add a short-snap wall case. Removing this exemption survives the existing suite, so the worker's mutation battery does not establish coverage of this boundary.

3. **P2 — A short final path gap is accepted without checking the physical connection.** `tools/setup/interior_sampler.py:392`, `:394`, and `:503`. The floor-to-sampled-mesh ray checks `candidate`, while `HCProbePath` independently permits its last waypoint to be 0.5 m from the measured floor. In the same synthetic short/partial-path model used by the worker's tests, an exact floor mesh sample and a last waypoint 40 cm away across a wall still produce code `1`: no snap displacement means no wall ray runs. **Minimal fix:** also validate the actual last-waypoint-to-floor connection with conservative collision/height checks, or reject the remaining gap until a smaller native-qualified tolerance exists. Add a wall in that final gap. This reproduces the source acceptance condition; it does **not** assert that native `FindPath` has been observed returning such a partial path. The installed declaration documents waypoints including the ending position, and its native behavior still needs observation. The existing code/tests nevertheless explicitly tolerate shortened endpoints, so their safety policy needs to cover this case.

4. **P2 — The open-sky test skips other objects' roofs.** `tools/setup/interior_sampler.py:303`, `:305`, used at `:470`. A solid overhead plane owned by another object over the exterior seed yields result `2`; `HCProbeOpenSky` advances through it and reports clear sky. The setup becomes `tested`. Thus being outside the sampled building's box does not establish an open-sky exterior seed when the seed lies under another structure. **Minimal fix:** conservatively reject any overhead collision in the tested sky column, or use an independently validated exterior classification. Add a foreign-roof case. Keep failures/unknowns ineligible. The current open-sky ray is also finite (own-building height + 2 m); do not describe this unmeasured predicate as a general sky-visibility proof.

All four new safety expectations fail on the unmodified fix round. The first two do not depend on partial native path behavior. Finding 1 alone is sufficient to keep the treatment unsafe for the stated player-reachability rule.

**Prior BLOCK disposition**

The seven original regression scripts now pass. They retain their original data by importing a scratch copy of the old point-test fixtures; they execute the new sampler through the current transpiler. Additional isolated probes use both current calibration classes so a missing-class refusal cannot accidentally mask the vertical or unknown-tenement checks.

| Prior finding | Status | Current result |
| --- | --- | --- |
| 1. Unknown reachability authorizes loot | **FIXED** | Unknown tenements with valid calibration refuse `no eligible candidates`; one yes plus three unknown produces 0 eligible candidates. Success coverage uses the entire usable cohort. |
| 2. Reached point can be across a wall | **PARTIAL** | Original 1 m snap reproduction is rejected; 3D snap distance is bounded at 0.5 m and the endpoint is compared with the measured floor. Findings 1–3 above still accept wall-separated points. |
| 3. Exterior control can run inside isolated interior | **PARTIAL** | Original 40 m internal-door island cannot validate setup; raw and snapped seeds must exceed horizontal box margins, and own-building overhang/capped sky casts fail closed. Foreign overhead geometry is skipped (finding 4). |
| 4. Stairs merge floors into phantom heights | **FIXED** | Support-centred, non-chaining bands preserve physical levels. Per-cell raw height spread is bounded at 0.1 m. The old bridge case now has eligible heights `[0.0, 3.0]`, rather than 1.5 m. |
| 5. Calibration ignores vertical coverage | **FIXED** | Minimum per-class `v3_coverage` is enforced. A +100 m shift refuses with 3D coverage 0.000. |
| 6. Barracks calibration can be omitted | **FIXED** | Missing/unusable placements or empty stock points name the missing class and refuse. Both classes are required. |
| 7. Setup ignores path budget | **FIXED** | Setup and hit paths share `HCProbeTakePath`; zero budget makes zero control queries. Exhaustion leaves unknown observations, which cannot authorize treatment. |

**Compile shape and installed API audit**

I tokenized the actual generated hook independently of both lints, stripping string/comment contents and separating statements by syntax rather than indentation or line layout. The 16-target hook has 501 statement fragments; the maximum binary `+` count is **8**, attained on generated lines 618 and 621. No statement exceeds 8. The 34-method scan finds no duplicate locals/parameters and no identifiers colliding with the 7,190 native type names. There are no leading `||`/`&&` lines or ternary tokens. All numeric JSON fields pass through `HCProbeInt`/`HCProbeNum`, whose bodies explicitly call `ToString`; the strict string execution test also passes. Out variables for every relevant engine call are declared before the call. The separate shared-lint formatting bypass does not affect this count.

Every external callable used by the hook was checked against `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`. Native file paths below are relative to that root; full signature output is retained in `api-audit.log`.

| Calls/types | Installed evidence |
| --- | --- |
| GetGame | `3_Game/gameplay.c:636` |
| IsServer, GetTime, GetCallQueue | `3_Game/Global/Game.c:1120`, `:1535`, `:1550` |
| GetWorld, GetObjectsAtPosition3D, GetWorldName, GetVersion | `3_Game/Global/Game.c:931`, `:930`, `:932`, `:942` |
| GetAIWorld | `3_Game/Global/World.c:116` |
| RaycastRV and default nearest contact | `3_Game/Global/DayZPhysics.c:199`; ObjIntersectGeom at `:69` |
| PGFilter.SetFlags, SetCost | `3_Game/AI/AIWorld.c:65`, `:67`; flag and area enum members in that same file |
| FindPath, SampleNavmeshPosition | `3_Game/AI/AIWorld.c:98`, `:122` (closest filtered point within radius) |
| GetDoorCount, GetDoorSoundPos | `3_Game/Entities/Building.c:31`, `:73`; preceding comment specifies world space |
| GetPosition, GetOrientation, ClippingInfo, GetType | `3_Game/Entities/Object.c:287`, `:305`, `:358`, `:467` |
| CoordToParent, CoordToLocal | `1_Core/proto/EnEntity.c:473`, `:499` |
| Cast; array Count/Get/Insert; set Find; TVectorArray | `1_Core/proto/EnScript.c:94`, `:380`, `:399`, `:407`, `:749`, `:738` |
| int.ToString, AsciiToString, float.ToString, vector.Distance | `1_Core/proto/EnConvert.c:30`, `:44`, `:115`, `:196` |
| string Substring/Replace/Length | `1_Core/proto/EnString.c:113`, `:156`, `:199` |
| Math.Sqrt, Vector | `1_Core/proto/EnMath.c:305`, `1_Core/proto/EnMath3D.c:18` |
| FileExist/OpenFile/CloseFile/FPrintln/MakeDirectory | `1_Core/proto/EnSystem.c:397`, `:417`, `:443`, `:481`, `:525` |
| Print, CallLater, super.OnInit | `1_Core/proto/EnDebug.c:96`, `2_GameLib/tools.c:61`, `5_Mission/mission/missionServer.c:85` |

Argument order, out arguments, and one-shot CallLater scheduling match these declarations. No mismatched native API call was found. This is not an Enforce compile result, nor proof of contact ownership, clipping coordinate basis, navmesh connectivity, collision volume, or performance.

Parent launcher review: `probe_runtime.LAUNCHER_PROBES` and the PS1 ValidateSet/table agree on `interior-sampler-plan.json`, `HCInteriorSampler`, and `census.json`. The compile-refusal check reads a shared, bounded script-log tail for `Can't compile`, breaks the wait loop, and leaves cleanup in `finally`; a crash log alone does not trigger it. Fresh profiles prevent stale-log matching, the sentinel check takes precedence, and the report records crash logs separately. No source finding was identified in these rows/exit changes. Their Python/static-text tests pass; PowerShell execution was prohibited and remains untested.

**Treatment and product checks**

The builder now requires usable placements and stock points for both calibration classes and compares their minimum 3D volume coverage with the threshold. Horizontal coverage remains reported. Height bands cannot chain through staircase heights; excessive within-cell spread is rejected before eligibility. Selection is sorted, bounded, and deterministic in the existing shuffled-input tests.

The default lootmax formula is `max(1, min(12, ceil(count * 0.25 - EPSILON)))`; actual results for point counts 1, 4, 5, 48, 49, 100 are 1, 1, 2, 12, 12, 12. Group and lootFloor limits agree. Existing points and nonzero container/group limits are refused. No duplicate spawning mechanism or second loot writer was introduced; the deterministic selected cells are distinct and enter only lootFloor.

I read the actual stock XML and exercised the writer in memory with explicitly synthetic selections. The result parses as `prototype`, repeats byte-for-byte, and bytes outside the two tenement group blocks are identical. Both tenements retain shelf/weapon containers at zero with no points. Stock contains 10,646 points with exactly `height/pos/range` attributes and 428 with additional `flags`; generated points use the supported former syntax. This establishes XML parsing and stock-shaped point serialization, not CE ingestion or spawning. Native CE/PBO/server acceptance remains pending, as required. Roofed ray hits alone also do not establish an enclosed interior, a clear item radius/player volume, or absence of covered outdoor ledges. Findings 1–3 show concrete current reachability failures; the implementation should not be enabled based on this review.

The parent launcher has consistent fixed `interior-sampler` rows in Python and PS1, including its distinct plan, directory, census and sentinel paths. Its compile-refusal check reads the newest script log tail with shared access, recognizes `Can't compile`, leaves the loop through `compile-failed`, and reaches the existing finally cleanup/report path. Sentinel and process-exit checks precede that check; crash logs alone do not trigger it. Shared runtime/launcher tests pass. PowerShell execution was expressly prohibited and was not performed.

**Independent mutation results**

All mutations are confined scratch source copies. Each is executed against the existing two feature test modules with only the bundled `test_every_mutated_condition_is_detected` meta-test excluded. This removes source-anchor/meta-test credit: the baseline is **117 tests, zero failures/errors**. All eight formerly surviving mutations listed in the prior report are now behaviorally killed. The original mesh-altitude check mutation is replayed against its replacement 3D snap-displacement guard. Results for all 24 mutations are copied verbatim below. Individual failing-test output is in `mutation-logs/`.

Two survivors need interpretation. Removing `reachable is True` is redundant under the default 0.75 whole-cohort success gate; its survival alone does not show unknown observations becoming eligible. Removing the 5 cm exemption adds checks, and survives because there is no discriminating short-snap case. Conversely, making non-owner geometry block is killed because current tests deliberately demand acceptance of that obstruction. That expectation needs correction along with finding 1.

**Commands and actual output**

Read-only inspection used `cat`, `sed`, `nl -ba`, `rg`, `git show 68dd22f`, `git show 82d3042 -- tools/setup/probe_runtime.py tools/setup/Start-CEProbeServer.ps1`, and `git diff --stat 93a3042 68dd22f --` the four review files. Full patch snapshots are retained in `reviewed-commit.patch` and `launcher-parent.patch`. Reading the two specification paths reports `No such file or directory`. Reading the supplied worker runner likewise reports `No such file or directory`.

Tracked sources were copied, without `.git`, to `scratchpad-review/source-copy` using Python standard-library pathlib/shutil and read-only `git ls-files -z`. TMPDIR is a sibling of that source copy; this satisfies the feature tools' outside-own-source rule while keeping every write inside the permitted scratch directory.

From `scratchpad-review/source-copy`:

```sh
TMPDIR=/code/hc-worktrees/interior-review-2/scratchpad-review/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_interior_sampler tests.unit.test_interior_points tests.unit.test_probe_runtime -v > ../targeted-tests.log 2>&1
```

```text
Ran 175 tests in 5.880s
OK
```

```sh
TMPDIR=/code/hc-worktrees/interior-review-2/scratchpad-review/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v > ../full-unit-tests.log 2>&1
```

```text
Ran 2169 tests in 54.663s
FAILED (failures=1, errors=155, skipped=1)
```

These are confinement results, not a green full-suite claim: 114 errors are `probe files must be outside every Git checkout`, 40 are `destination must be outside Steam and source checkouts`, and the remaining error is an unbound `result` after failed startup-runner subtests. The single failure is the deployment CLI reporting that same confinement refusal. The permitted scratch directory is necessarily inside this Git ancestor. No restrictions were bypassed to obtain a green run.

From the real worktree:

```sh
TMPDIR="$PWD/scratchpad-review/tmp" PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/review_regressions.py > scratchpad-review/prior-regressions.log 2>&1
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/extra_probes.py > scratchpad-review/extra-probes.log 2>&1
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/new_safety_regressions.py > scratchpad-review/new-safety-regressions.log 2>&1
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/compile_shape.py > scratchpad-review/compile-shape.log 2>&1
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/api_audit.py > scratchpad-review/api-audit.log
TMPDIR="$PWD/scratchpad-review/tmp" PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/mutations.py > scratchpad-review/mutations.log 2>&1
```

```text
Prior regression scripts: Ran 7 tests in 0.067s; OK
New safety regressions: Ran 4 tests in 0.046s; FAILED (failures=4)
```

Extra probes:

```text
building-wall state tested floor (-.5,0,.5) reach 2
same-wall-masked-by-other-object state tested floor (-.5,0,.5) reach 1
four-centimetre-snap-across-wall: 1
endpoint-stops-40cm-away-across-wall: tested 1
seed-under-other-object-roof: tested
one-yes-three-unknown-eligible: 0
stock syntax attribute counts: {('flags', 'height', 'pos', 'range'): 428, ('height', 'pos', 'range'): 10646}
real-stock parses: prototype outside bytes identical: True deterministic: True
stock treatment Land_Tenement_Small group lootmax 2 containers [('lootFloor', '2', 5), ('lootshelves', '0', 0), ('lootweapons', '0', 0)]
stock treatment Land_Tenement_Big group lootmax 2 containers [('lootFloor', '2', 5), ('lootshelves', '0', 0), ('lootweapons', '0', 0)]
lootmax boundaries: [(1, 1), (4, 1), (5, 2), (48, 12), (49, 12), (100, 12)]
native type lint: []
masked-wall selected point coordinates: [(-0.5, 0.0, 1.5), (0.5, 0.0, -2.5), (4.5, 0.0, 1.5), (5.5, 0.0, -2.5)]
unknown-tenements-only refusal: ValueError Land_Tenement_Small: no eligible candidates (usable placements 4, reachability unknown; unknown reachability never enters treatment)
vertical-only refusal: CoverageError calibration vertical (3D) coverage 0.000 (Land_HouseBlock_2F1, radius 0.5, xz-only 0.571) is below the threshold 0.600
missing-barracks refusal: CoverageError calibration data missing for Land_Mil_Barracks2 (no usable placement); every calibration class is required
stair-bridge eligible physical heights: [0.0, 3.0]
```

Independent compile shape:

```text
Targets: 16 statements: 501 maximum binary plus: 8
Statements with 8 plus (generated lines): [618, 621]
Statements over 8: []
Leading boolean operators: []
Ternary tokens: []
Methods checked: 34 duplicate local/parameter names: [] native type name collisions: []
Out call: HCProbeRay RaycastRV line 195 [('contactPos', True), ('contactDir', True), ('contactComponent', True)]
Out call: HCProbeSampleMesh SampleNavmeshPosition line 314 [('sampled', True)]
Out call: HCProbePath FindPath line 324 [('waypoints', True)]
Out call: HCProbeBeginBuilding GetObjectsAtPosition3D line 544 [('candidates', True), ('candidateCargos', True)]
Out call: HCProbeBeginBuilding ClippingInfo line 597 [('clip', True)]
Out call: HCProbeStart GetWorldName line 704 [('world', True)]
Out call: HCProbeStart GetVersion line 705 [('version', True)]
Numeric JSON: HCProbeInt/HCProbeNum each return value.ToString(); strict-string behavioral suite is also run.
External calls: ['+', '=', 'AsciiToString', 'CallLater', 'Cast', 'ClippingInfo', 'CloseFile', 'CoordToLocal', 'CoordToParent', 'Count', 'Distance', 'FPrintln', 'FileExist', 'Find', 'FindPath', 'Get', 'GetAIWorld', 'GetCallQueue', 'GetDoorCount', 'GetDoorSoundPos', 'GetGame', 'GetObjectsAtPosition3D', 'GetOrientation', 'GetPosition', 'GetTime', 'GetType', 'GetVersion', 'GetWorld', 'GetWorldName', 'Insert', 'IsServer', 'Length', 'MakeDirectory', 'OnInit', 'OpenFile', 'Print', 'RaycastRV', 'Replace', 'SampleNavmeshPosition', 'SetCost', 'SetFlags', 'Sqrt', 'Substring', 'ToString', 'Vector']
```

Mutation results:

```text
baseline: SURVIVED; tests=117; failures/errors=0; 
control-self-loop: KILLED; tests=117; failures/errors=2; test_a_control_path_to_an_unlinked_far_point_fails_the_control, test_generated_logic_matches_the_independent_reference_scenarios
endpoint-five-cm: KILLED; tests=117; failures/errors=5; test_generated_logic_matches_the_independent_reference_scenarios, test_mesh_snapping_across_a_wall_is_not_reachability, test_the_final_waypoint_must_end_at_the_measured_floor_not_within_two_metres, test_the_path_end_tolerance_is_tight_enough_to_fail_a_truncated_control_path, test_the_snap_displacement_from_the_measured_floor_is_bounded
endpoint-disabled: KILLED; tests=117; failures/errors=4; test_a_failing_control_path_or_missing_door_or_missing_navmesh_leaves_reachability_unknown [control-failed], test_generated_logic_matches_the_independent_reference_scenarios, test_the_final_waypoint_must_end_at_the_measured_floor_not_within_two_metres, test_the_path_end_tolerance_is_tight_enough_to_fail_a_truncated_control_path
snap-distance-disabled: KILLED; tests=117; failures/errors=2; test_generated_logic_matches_the_independent_reference_scenarios, test_the_snap_displacement_from_the_measured_floor_is_bounded
wall-ray-disabled: KILLED; tests=117; failures/errors=2; test_generated_logic_matches_the_independent_reference_scenarios, test_mesh_snapping_across_a_wall_is_not_reachability
small-snap-no-exemption: SURVIVED; tests=117; failures/errors=0; 
nonowner-blocks: KILLED; tests=117; failures/errors=2; test_generated_logic_matches_the_independent_reference_scenarios, test_mesh_snapping_across_a_wall_is_not_reachability
open-sky-disabled: KILLED; tests=117; failures/errors=3; test_an_exterior_seed_under_a_building_overhang_is_not_open_sky, test_an_unanswerable_open_sky_test_does_not_validate_the_seed, test_generated_logic_matches_the_independent_reference_scenarios
projected-seed-validation-disabled: KILLED; tests=117; failures/errors=2; test_an_exterior_seed_that_snaps_back_inside_the_building_is_refused, test_generated_logic_matches_the_independent_reference_scenarios
raw-seed-validation-disabled: KILLED; tests=117; failures/errors=2; test_a_door_near_the_box_edge_gets_a_seed_with_a_real_standoff, test_generated_logic_matches_the_independent_reference_scenarios
path-budget-disabled: KILLED; tests=117; failures/errors=3; test_a_zero_path_budget_runs_no_setup_or_control_queries, test_generated_logic_matches_the_independent_reference_scenarios, test_path_budget_marks_the_remaining_candidates_untested
nonowner-clearance-skip-50cm: KILLED; tests=117; failures/errors=3; test_a_hanging_object_above_the_floor_does_not_end_the_clearance_search, test_generated_logic_matches_the_independent_reference_scenarios, test_only_interior_floor_surfaces_of_the_building_itself_are_recorded
floor-owner-disabled: KILLED; tests=117; failures/errors=4; test_a_hanging_object_above_the_floor_does_not_end_the_clearance_search, test_generated_logic_matches_the_independent_reference_scenarios, test_mesh_snapping_across_a_wall_is_not_reachability, test_only_interior_floor_surfaces_of_the_building_itself_are_recorded
barracks-calibration-omitted: KILLED; tests=117; failures/errors=4; test_a_calibration_class_whose_placements_are_all_unusable_is_refused, test_a_calibration_class_without_stock_points_is_named_and_refused, test_calibration_names_every_missing_class_in_the_refusal, test_build_reports_calibration_selection_and_hashes
calibration-threshold-disabled: KILLED; tests=117; failures/errors=4; test_calibration_enforces_vertical_agreement_so_floors_moved_100_m_fail, test_coverage_below_the_threshold_is_refused_with_the_numbers, test_missing_calibration_data_is_refused_not_assumed, test_cli_refuses_low_coverage_without_writing_anything
calibration-xz-instead-3d: KILLED; tests=117; failures/errors=3; test_build_reports_calibration_selection_and_hashes, test_calibration_enforces_vertical_agreement_so_floors_moved_100_m_fail, test_coverage_below_the_threshold_is_refused_with_the_numbers
clearance-pick-highest-first: KILLED; tests=117; failures/errors=1; test_the_floor_with_the_most_clearance_is_chosen_not_the_highest_surface_in_a_cell
height-first-not-mean: KILLED; tests=117; failures/errors=1; test_the_cell_height_is_the_mean_of_the_placements_not_the_first_observation
height-spread-disabled: KILLED; tests=117; failures/errors=1; test_height_spread_above_the_bound_is_rejected_before_averaging
reach-agreement-disabled: KILLED; tests=117; failures/errors=2; test_one_success_and_three_unknown_does_not_pass_the_agreement_gate, test_reach_agreement_counts_successes_over_the_whole_usable_cohort
reach-known-disabled: SURVIVED; tests=117; failures/errors=0; 
lootmax-floor: KILLED; tests=117; failures/errors=1; test_lootmax_rounds_up_so_a_fractional_share_still_gets_the_next_slot
outside-bytes-guard-disabled: KILLED; tests=117; failures/errors=1; test_bytes_outside_the_edited_groups_that_change_are_refused
preexisting-point-refusal-disabled: KILLED; tests=117; failures/errors=2; test_stock_points_already_in_a_tenement_group_are_refused_as_authored_data (container=b'lootFloor'), test_stock_points_already_in_a_tenement_group_are_refused_as_authored_data (container=b'lootshelves')
```

Final repository integrity check:

```sh
git diff --exit-code
git diff --cached --exit-code
git status --short
```

Both diff commands: empty output, exit code 0. Status:

```text
?? .banso-brief.md
?? scratchpad-review/
```

The brief was pre-existing. No implementation changes were made.
