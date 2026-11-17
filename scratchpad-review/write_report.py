from pathlib import Path
here=Path(__file__).resolve().parent
report='''Verdict: **BLOCK**.

Review identity: **hc-interior-review-003**, reviewing `98166121a7d2081ade1d47e06897fc46f0ea63e7`, parent `68dd22fcbf78013a94a7b06e6b0616a42e6983e8`. The three changed files and the unchanged treatment builder were inspected. The prior review's reproductions and mutations were rerun against current-source scratch copies. All geometry in reviewer-authored reproductions is explicitly synthetic. Native observations below came from the supplied runs; I launched no engine process and grant no acceptance.

Only `scratchpad-review/` was written. No source, git state, runtime, `/mnt/d` content, or `.banso-writer/` content was changed. No DayZ, Wine, PowerShell, lifecycle command, delegation, commit, staging or publishing was run. AGENTS.md and the runtime contract were read. Both required specification paths are absent; `docs/README.md` explains that internal specs are excluded from Git. No local spec/plan/tasks files were found. I applied Banso CLI dispatched-worker guidance and the user's confined review contract; the generic panel workflow was not invoked.

**Ranked findings**

1. **P1 — A zero-radius waist ray still authorizes a point behind an impassable wall.** `tools/setup/interior_sampler.py:687`, `:689`, and the corresponding final-gap check at `:542`, `:545`; the shared ray is zero-radius at `:313` through the native default. The fix now detects all owners along the ray, but it only tests a line 1 m above the floor. In an explicitly synthetic enclosed room, the separating wall has a 20 cm slot from y=0.9 to 1.1, with full walls closing its other sides. Floor x=-0.5 snaps 0.4 m to connected mesh east of the wall. The waist ray passes through the slot, the hook emits reach code **1**, and the end-to-end treatment builder selects **(-0.5, 0, 1.5)** in that room. A player cannot pass through the slot. The same weakness applies to the final path gap. This is a source acceptance counterexample, not a claim that a native navmesh was observed in this scene. **Minimal safe fix:** keep nontrivial snaps/final gaps ineligible until their physical connection has a native-qualified player-clearance check; a clear zero-radius line alone cannot authorize them. Add a closed-room/waist-slot regression. If using the existing RaycastRV radius argument, qualify its volume semantics natively before relying on it.

2. **P1 — Foreign solid geometry is skipped when deciding whether the loot position has player clearance.** `tools/setup/interior_sampler.py:343` and `:352`, consumed at `:701`. `HCProbeClearance` searches for the building's ceiling through every non-owner collision and returns that ceiling distance as clearance. With an owner floor at y=0, ceiling at 2.8 and a foreign solid volume occupying y=0.1..2.4, it reports clearance **2.8**, emits reach code **1**, and the builder selects points under that solid object. Exact mesh samples trigger no level obstruction ray. The fixture's navmesh is explicitly static; it does not know about the extra object, which is the condition this independent physical check must handle. **Minimal fix:** retain owner-ceiling distance separately from usable physical clearance, and refuse obstructed player/item space. Conservatively failing eligibility on a collision within the required clearance is safer than stepping through it. Add an obstructed-endpoint case; the current hanging-object tests deliberately measure only the owner ceiling and do not establish free player volume.

3. **P2 — Start-inside owner re-hits are counted and recorded as new floors, exhausting the new owner budget.** `tools/setup/interior_sampler.py:767` and `:779`–`:793`. The code identifies near-zero drop, then independently counts the same contact as a floor once the previous restart was at least 0.25 m higher. At the 0.8 m offset, repeated start-position hits therefore become artificial floor measurements. A synthetic 3 m thick owner volume emits interior heights **1.15, 1.95 and 2.75** although its only traversable floor is y=0. Native run 002 confirms the counting failure: placement 4, column (-10.5026,-8.09233), reports **30 steps / 24 floors / floor cap**. Steps 5–17 have approximately zero drop and action 4 while heights descend by 0.8 m. Across the native run, **1,458 columns hit the floor cap**. This prevents the floor budget from representing distinct surfaces and truncates lower-floor measurement. I do not claim the phantom native contacts became selected loot; the native treatment refuses calibration. **Minimal fix:** near-zero/negative-drop re-hits must only advance the bounded descent and diagnostics; they must not update the accepted-surface history, consume a floor, or emit a floor. Add owner-volume fixtures, not just foreign thick clutter. Keep capped/incomplete geometry unqualified for treatment.

The three new behavioral safety tests fail on the unchanged commit. The first two also have complete synthetic census-to-treatment reproductions. These are remaining reachability/measurement failures, even though every exact reproduction from the last BLOCK is now rejected.

**Prior finding disposition**

“FIXED” here means the original reproduced acceptance was corrected in source; it does not mean native gameplay acceptance or closure of every broader geometric case.

| Original seven findings carried by review 002 | Status on 9816612 | Actual result |
| --- | --- | --- |
| Unknown reachability authorizes loot | FIXED | Unknown tenements with both valid calibration classes refuse `no eligible candidates`; one yes plus three unknown gives 0 eligible. |
| Reached point can be across a wall | PARTIAL | Original 1 m snap and the last review's ordinary walls are rejected; the enclosed waist-slot room still reaches treatment (finding 1), and endpoint occupancy is unchecked (finding 2). |
| Exterior control can run inside isolated interior | PARTIAL | The original internal-door island is rejected; horizontal-box margins and overhead collisions within the tested column fail closed. The new seed ladder still has no independent map/water/foreign-interior classification; finite-height sky limitation remains. |
| Stairs merge floors into phantom heights | FIXED | Original bridge case has eligible physical levels `[0.0, 3.0]`. New native descent re-hits are a separate problem (finding 3). |
| Calibration ignores vertical coverage | FIXED | +100 m calibration shift refuses with 3D coverage 0.000. |
| Barracks calibration can be omitted | FIXED | Missing barracks refuses and names the class; unusable and empty-stock cases remain covered. |
| Setup ignores path budget | FIXED | Zero budget performs zero mesh samples and zero FindPath calls; setup/hits share the counter. |

| Four ranked findings raised by review 002 | Status of original reproduction | Actual output |
| --- | --- | --- |
| Nearer object hides building wall | FIXED | Building wall alone: code 2; same wall masked by a nearer object: code 2. |
| <=5 cm snaps bypass wall validation | FIXED | Four-centimetre snap across a wall: code 2. Horizontal shifts <=1 mm and purely vertical shifts still omit this ray; “every nonzero snap” overstates the implementation. |
| Final 40 cm gap bypasses obstruction check | FIXED | Same truncated-path fixture and full wall: code 0; clear short gap remains code 1. General player-volume safety remains partial (finding 1). |
| Other objects' roofs skipped by sky check | FIXED | Same foreign roof gives `control-failed`, stage 6; no longer skipped. The sky ray remains finite. |

All seven original regression tests and all four last-review safety regressions pass. The separate extra probes ensure that missing calibration cannot mask the unknown-tenement or vertical-coverage refusals.

**Native evidence, without acceptance**

Run 001 is read from `/home/david/.cache/hollow-country/experiments/interior-sampler-001/`; run 002 is read from `/mnt/d/HollowCountryLocal/interior-sampler-002/`. Re-rendering this commit with run 002's literal targets/limits exactly reproduces the plan hook SHA-256 **b56f2abb9563ac4b729a5f85a2d3d2b567146ee8ec6731e90167ceaf70ffbb8f** and those bytes occur verbatim in its init.c. Thus the supplied native success corresponds to the reviewed generator. The script log contains LOADED, BEGIN, rows=16 found=16, COMPLETE. The observation says `observed-not-accepted`, `sentinel-seen`, no crash logs; it also records server exit -1, which I do not reinterpret as a clean shutdown.

The census hash is **dc066bcf090b5a42c399017bcd9e5146203b845d94eddb22edd330ad153c06ae**, 3,063,649 bytes. It found 16/16 placements and made 215,502 rays. Fourteen placements are `tested`; big tenement placement 5 fails all four attempts at stage 4 (seed mesh sample), and house-block placement 11 fails all four at stage 10 (final path gap). The stage histogram is **12:14, 6:6, 4:4, 10:6**. Native stage-10 attempts have returned paths with 2–16 waypoints but gaps approximately 2.16–4.30 m; the endpoint gate correctly refuses them. This is now native evidence that a true FindPath result can leave a substantial final gap, rather than merely a synthetic test assumption.

The relation totals are **none=15,109; building=97,663; proxy=0; other=29,116**. Same-class type names sometimes have relation 3, which does not prove they are the sampled object or its children. Do not relabel them as owner hits without identity evidence. No proxy-child detection was exercised by this native run. The diagnostics show restart offsets 0.05, 0.1, 0.2, 0.4, 0.8 and near-zero or slightly negative drops, consistent with bounded start-inside re-hits. There are **124,297 re-hits, 32 step-capped columns, 1,458 floor-capped columns, 0 clearance-attempt caps**, and 61,610 emitted interior observations. These counts are not proof that those observations are real walkable floors.

The builder finds 135 eligible small-tenement cells and 17 big-tenement cells at the default agreement gate, but 0 eligible HouseBlock_2F1 calibration cells and 2 barracks calibration cells. Building against the actual stock XML refuses **calibration vertical (3D) coverage 0.000 (Land_HouseBlock_2F1), below 0.600**. No native treatment was written. Do not lower calibration to convert this run into acceptance.

**Compile shape and installed APIs**

An independent lexical scanner removed string/comment contents, split syntax-delimited statements regardless of formatting, and counted the actual `+` tokens. Both the synthetic 16-target hook and the exact native-plan hook have **683 statement fragments**, maximum **8 binary '+'**, reached at generated lines **865, 868, 882**. No statement exceeds eight. The scan of **42 methods** finds no duplicate local/parameter names, native-type identifier collisions, leading `||`/`&&`, or ternary. Numeric JSON formatting uses HCProbeInt/HCProbeNum with explicit `.ToString()`; strict-string execution passes. Each relevant engine out parameter is declared before the call. The only override is `OnInit()` with no parameters, matching `MissionServer.OnInit()`; there are no override parameter names to mismatch. The supplied native compilation is corroborating evidence, separate from the static audit.

All external call names were reconciled against `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`. Paths in the following table are relative to that cache; exact declarations are in `api-audit.log`.

| Calls | Installed file:line |
| --- | --- |
| GetGame | `3_Game/gameplay.c:636` |
| GetObjectsAtPosition3D, GetWorld, GetWorldName, GetVersion | `3_Game/Global/Game.c:930`, `:931`, `:932`, `:942` |
| IsServer, SurfaceY, GetTime, GetCallQueue | `3_Game/Global/Game.c:1120`, `:1176`, `:1535`, `:1550` |
| GetAIWorld | `3_Game/Global/World.c:116` |
| RaycastRV (including default radius=0 and NEARESTCONTACT) | `3_Game/Global/DayZPhysics.c:199`; ObjIntersectGeom at `:69` |
| SetFlags, SetCost, FindPath, SampleNavmeshPosition | `3_Game/AI/AIWorld.c:65`, `:67`, `:98`, `:122`; requested flags and DOOR_CLOSED in enums at `:1`–`:53` |
| GetDoorCount, GetDoorSoundPos (world-space position) | `3_Game/Entities/Building.c:31`, `:73` |
| GetPosition, GetOrientation, ClippingInfo, GetType | `3_Game/Entities/Object.c:287`, `:305`, `:358`, `:467` |
| CoordToParent, CoordToLocal, GetParent | `1_Core/proto/EnEntity.c:473`, `:499`, `:571` |
| Cast; array Count/Clear/Set/Get/Insert; set Count/Find/Get; TVectorArray | `1_Core/proto/EnScript.c:94`, `:380`, `:385`, `:389`, `:399`, `:407`, `:743`, `:749`, `:750`, `:738` |
| int.ToString, AsciiToString, float.ToString, vector.Distance | `1_Core/proto/EnConvert.c:30`, `:44`, `:115`, `:196` |
| string Substring, Replace, Length | `1_Core/proto/EnString.c:113`, `:156`, `:199` |
| Sqrt, Vector | `1_Core/proto/EnMath.c:305`, `1_Core/proto/EnMath3D.c:18` |
| FileExist, OpenFile, CloseFile, FPrintln, MakeDirectory | `1_Core/proto/EnSystem.c:397`, `:417`, `:443`, `:481`, `:525` |
| Print, CallLater, super.OnInit | `1_Core/proto/EnDebug.c:96`, `2_GameLib/tools.c:61`, `5_Mission/mission/missionServer.c:85` |

No undeclared/mismatched API use was found. Installed declarations do not establish clipping basis, object ownership of every contact, player connectivity, collision-volume semantics or performance. contactDir is recorded raw; the cache calls it “direction of first contact”, and native values are not unit normals. It must not be treated as a qualified floor normal.

**Budgets, seed ladder and eligibility**

The owner budget defaults to **24** and the descent step budget to **64**; these are defaults, not hard API maxima (accepted parameter bounds are 64 and 512 respectively). Every descent contact consumes a step; only owner contacts separated by >=0.25 m consume the nominal floor counter, including the erroneous re-hits in finding 3. Ray, path, per-column and clearance-attempt loops terminate under explicit bounds. Diagnostics retain at most three columns with 32 sequence entries, at most 16 foreign type names, and at most four door attempts. Actual target-load performance remains unqualified.

The ladder tests standoffs **2..31 m**, stops at the *first* position outside the own-box margin, and uses SurfaceY. It does not retry farther positions after mesh/sky/control failure; that avoids an unbounded search but does not classify the chosen location. Its far control adds another 10 m and independently uses SurfaceY. There is no map-boundary or water query. A synthetic edge placement at world x=1 chooses seed x=-5.9 and becomes `tested` if the mock mesh returns a path. This demonstrates missing source checks, not observed native off-map navigation. SWIM and SWIM_SEA polygons are excluded; that is the only water protection, and does not independently establish that a point is dry. A neighboring roof within the sky column blocks; a foreign roof above its finite top is unqueried (synthetic roof y=20 over a short building still gives stage 12). SurfaceY can be under another building. Filtered sampling plus this finite ray is not a general exterior/dry-land classifier. Roofed outdoor ledges also remain distinguishable only through native qualification, not through an enclosure predicate in this hook.

Unknown path/reach results do not enter eligibility. The full-cohort success denominator and per-cell `reachable is True` gate remain enforced. A ray-budget failure is treated as blocked by HCProbeBlocked, not clear. The 1 mm horizontal ray exemption and all purely vertical displacements qualify the worker's “every nonzero snap” claim. The new gap ray is level at goal-floor waist height, as claimed, but is still zero-radius and not a player sweep.

**Treatment builder, changed point tests and product rules**

`tools/audit/interior_points.py` is unchanged by this commit; only its tests changed. Both calibration classes and minimum 3D coverage remain mandatory. The new even-split/low-agreement test behaviorally kills the previously surviving removal of `reachable is True`. Its separate hand-made contradictory candidate tests only the predicate; the integration case supplies the stronger evidence. The new diagnostic-compatibility fixture has a vector as the first attempt field at `tests/unit/test_interior_points.py:405`, whereas the native field is an integer door index. It establishes tolerance of opaque extra keys, not validation of the diagnostic schema. Correcting that fixture would make it representative.

Using the actual stock XML and explicit synthetic selections, output parses, bytes outside the two tenement groups are unchanged, and 10 seeded permutations of the synthetic census placements/hits produce identical selections and treatment bytes. There are eight unique small-tenement points and four unique big-tenement points; group/lootFloor lootmax values are 2 and 1; shelf and weapon containers remain zero with no points. Existing points/nonzero limits are refused. The default lootmax boundary results for 1,4,5,48,49,100 points remain 1,1,2,12,12,12. No second loot writer, gameplay spawning, inventory authority change or duplicate-loot controller was added. This is source/XML evidence only; CE ingestion, actual item clearance and spawning remain unaccepted. Findings 1 and 2 violate the reachable-point rule despite the contained two-group XML edit.

**Independent mutation results**

The baseline is **153 tests, 0 failures/errors**, excluding only the bundled mutation meta-test. I executed all 24 mutations from the last review, adapting replaced anchors to their current semantic equivalents, plus 20 new mutations. No worker mutation runner was imported or credited. The actual result is **37 killed / 7 survived**. Each source and failing-test log is retained in `mutation-logs/`; full results with failed test names are in `mutations.log`.

The survivors are:

- `small-snap-no-exemption`: removing the remaining 1 mm exemption adds checking; no discriminating sub-millimetre fixture. This does not restore the old unsafe 5 cm exemption, whose mutation is killed.
- `nonowner-blocks`: a now-redundant explicit branch returning blocked for result 2. This prior change is already implemented, so survival is expected, not a gap.
- `rehit-max-raised`: raising the restart ceiling from 0.8 to 8.0 is not detected. The fixture only needs smaller offsets and never exercises the cap.
- `clearance-no-doubling`: disabling upward re-hit widening is not detected. The thick reference model handles start-inside only for downward rays, so upward widening is untested behaviorally.
- `far-door-altitude`: using the seed's old height instead of far SurfaceY is not detected; flat terrain hides the difference. Add terrain sloping between seed and far control.
- `unknown-ray-clear`: treating ray result -1 as clear in HCProbeBlocked survives. Whole-row ray-capping still prevents treatment, but the segment-level fail-closed policy lacks a direct regression.
- `final-gap-sloped-height`: using final-waypoint height at the ray start survives; all final-gap fixtures have equal endpoint heights. Add a nonzero-height final gap and assert a level ray.

The original unknown/failed-reach eligibility mutation now dies in two new tests. The prior four safety regressions are stronger than before, but their full-height planar walls, foreign-object-only thick volumes, flat control terrain and equal-height gaps explain the remaining blind spots.

**Commands and actual output**

Read-only inspection used `cat AGENTS.md`, attempts to read the two absent specification files, `cat docs/README.md`, `cat docs/RUNTIME_IMPLEMENTATION_CONTRACT.md`, `git show 9816612`, `git show 9816612 -- tests/unit/test_interior_points.py`, `git diff 9816612^ 9816612 -- tools/audit/interior_points.py`, `rg`, `sed`, `nl -ba`, and Python standard-library reads of the supplied caches/stock/runtime records. The full commit is retained in `reviewed-commit.patch`. The builder diff is empty. The absent specification reads return `No such file or directory`.

Tracked files were copied using `git ls-files -z` and pathlib/shutil into `scratchpad-review/source-copy`, without git metadata. Every test process uses `PYTHONDONTWRITEBYTECODE=1`; TMPDIR is `scratchpad-review/tmp`. Test stagers run from the source copy so their own-source exclusion remains active. Git-ancestor confinement was not bypassed. Commands below are from the review worktree unless marked otherwise.
'''

def block(cmd,output):
 return '\n```sh\n'+cmd+'\n```\n\n```text\n'+output.rstrip()+'\n```\n'
report+=block('TMPDIR="$PWD/scratchpad-review/tmp" PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/review_regressions.py', (here/'prior-regressions.log').read_text())
report+=block('TMPDIR="$PWD/scratchpad-review/tmp" PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/new_safety_regressions.py',(here/'new-safety-regressions.log').read_text())
report+=block('PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/round2_probes.py',(here/'round2-probes.log').read_text())
report+=block('PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/round2_safety_regressions.py',(here/'round2-safety-regressions.log').read_text())
report+=block('PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/compile_shape.py scratchpad-review/native-generated-hook.c',(here/'native-compile-shape.log').read_text())
report+='\n`python3 scratchpad-review/api_audit.py` produced all matching installed declarations; its complete output is in `api-audit.log`. `native_audit.py` and `native_summary.py` produced the read-only native comparison in `native-audit.log` and `native-summary.log`. The latter includes exact regeneration/hash checks. Native summary output, omitting only the long single-line column sequence already preserved in those logs:\n'
report+=block('PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/native_summary.py','\n'.join(l for l in (here/'native-summary.log').read_text().splitlines() if not l.startswith('sample owner capped column:')))
report+=block('PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/product_checks.py',(here/'product-checks.log').read_text())
report+='\nAn initial product-check harness attempt combined the synthetic calibration census with real stock points and correctly refused coverage 0.000 against threshold 0.100. That output is preserved in `product-checks-initial.log`. I corrected the harness to calibrate against its matching explicit synthetic stock fixture, then separately exercise the actual-stock writer. No threshold was lowered to claim real-stock calibration.\n'
report+=block('# From scratchpad-review/source-copy:\nTMPDIR=/code/hc-worktrees/interior-review-3/scratchpad-review/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_interior_sampler tests.unit.test_interior_points tests.unit.test_probe_runtime -v > ../targeted-tests.log 2>&1','\n'.join((here/'targeted-tests.log').read_text().splitlines()[-4:]))
full=(here/'full-unit-tests.log').read_text().splitlines()
report+=block('# From scratchpad-review/source-copy:\nTMPDIR=/code/hc-worktrees/interior-review-3/scratchpad-review/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v > ../full-unit-tests.log 2>&1','\n'.join(l for l in full if l.startswith(('Ran ','FAILED ('))))
report+='\nThe full-suite 155 errors comprise 114 probe Git-ancestor refusals, 40 destination Git-ancestor refusals, and one unbound `result` following refused startup-runner subtests. The single failure is `test_standalone_cli_readonly_json_plan`, which encounters the same checkout restriction. These are confined-run failures, not a full-suite pass and not regressions attributed to this commit.\n'
ml=(here/'mutations.log').read_text().splitlines()
report+=block('TMPDIR="$PWD/scratchpad-review/tmp" PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/mutations.py > scratchpad-review/mutations.log 2>&1','\n'.join(';'.join(l.split(';')[:3]) for l in ml))
report+=block('GIT_OPTIONAL_LOCKS=0 git diff --exit-code --no-ext-diff\nGIT_OPTIONAL_LOCKS=0 git diff --cached --exit-code --no-ext-diff\nGIT_OPTIONAL_LOCKS=0 git status --short','Both diff commands: empty output, exit 0.\n?? .banso-brief.md\n?? scratchpad-review/')
report+='\nThe untracked brief was present before this review. No implementation fix was authored in this read-only review; the three newly failing safety expectations remain red. Native player access, geometry qualification, CE spawning and normal PBO/server acceptance remain pending.\n'
(here/'REVIEW.md').write_text(report)
print('Wrote',here/'REVIEW.md','bytes',len(report.encode()))
