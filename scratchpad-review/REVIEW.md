Verdict: **BLOCK**.

Reviewed commit `93a30422325d9d7d550b3cefc085a86442d2c417`, parent `76678fe`, on `hc/interior-review`. This is a source review with synthetic counterexamples, not a native acceptance run. No tracked file was edited, no git metadata was written, and no DayZ, Wine or PowerShell process was run. All review artifacts and test temporary files are under `scratchpad-review/`.

The required `docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md` are absent. There are no tracked spec/plan/task artifacts in this checkout; `docs/README.md` says internal specifications are excluded from Git. I read AGENTS.md, the runtime integration contract, module status and the supplied review brief. I used the Banso CLI skill's dispatched-worker constraints; no lifecycle commands were run.

Findings, ordered by priority:

1. **P1 — Unknown reachability authorizes loot.** `tools/audit/interior_points.py:183–187`, also `:161–168`. When the AI world is unavailable, doors are missing, the control fails, or no path calls are allowed, the hook emits `-1`. If the entire class is unknown, `eligible()` explicitly bypasses the reachability requirement. The supplied synthetic full census therefore builds eight Small and four Big points with `reachability_mode="unknown"`. With mixed observations, one successful placement and three unknowns also makes all 32 candidates eligible at `min_agreement=0.75`: geometry agreement is 100%, but tested reachability is only 25%. **Minimal fix:** refuse treatment for unknown reachability and require successful/tested reachability coverage against the configured placement agreement denominator; do not discard unknown placements from the safety denominator. Observation reports may still retain unknown hits.

2. **P1 — The reached point can be across a wall from the authored point.** `tools/setup/interior_sampler.py:378–383`, with `:303–306`. `SampleNavmeshPosition` returns the closest filtered position within 1.5 m. Only its altitude is checked. The path then ends at that snapped point, and its last waypoint may still be another 2 m away. In the synthetic walled-room fixture with no filtered mesh inside, the measured floor changes from code `2` to code `1` when sampling returns the nearest connected mesh boundary 1 m across the wall at identical altitude. The exterior control continues to succeed. **Minimal fix:** validate displacement and the physical connection from the measured floor to the mesh sample; reject displaced samples without that evidence. Check the final waypoint against the original measured floor with tight, measured tolerances, rather than permitting a 2 m gap to an already displaced destination. Add horizontal-snap and short-partial-path cases; the current mock only moves samples vertically.

3. **P1 — The exterior control can run entirely inside an isolated interior.** `tools/setup/interior_sampler.py:347–365`. `GetDoorCount` includes doors without an exterior classification. Moving 2 m and 12 m along a centre-to-door direction does not establish that either seed is outside the building. A valid synthetic 40 m wide bounding box with an internal door at local x=5 yields seeds at x=7 and x=17, both inside. With only an isolated interior navmesh and no exterior navmesh, setup reports `tested` and interior hits report reached. **Minimal fix:** use a validated exterior seed; conservatively reject a setup whose sampled seed/control points have not been established outside the building. Validate after mesh snapping as well as before it. A positive path on the same island is insufficient exterior evidence.

4. **P1 — Staircase heights can create loot points between floors.** `tools/audit/interior_points.py:99–109`, `:137–150`. Storeys use single-link clustering over all raw hit heights, including stairs and slab undersides. Heights 0, 0.5, 1, 1.5, 2, 2.5, 3 merge the y=0 and y=3 floors. The per-cell reducer selects the surface with most clearance separately in each placement, then averages those surfaces. With two placements choosing y=0 and two choosing y=3, the result is a flat, agreed, reached candidate at y=1.5, where none of those cells had a surface. The end-to-end builder selects those phantom y=1.5 points. **Minimal fix:** prevent unbounded height chaining, match per-cell physical height bands across placements, and reject excessive height spread before aggregation. Never average observations from different slabs into an unmeasured surface.

5. **P2 — Calibration ignores the vertical coverage it computes.** `tools/audit/interior_points.py:449–453`. The refusal uses only `xz_coverage`. Shifting every calibration hit upward by 100 m preserves that coverage and still passes while `v3_coverage=0`. A synthetic supported-point fixture passes at the default 0.6 threshold with xz coverage 0.7142857142857143 and zero vertical coverage. **Minimal fix:** require the appropriate 3D/vertical coverage threshold as well as horizontal agreement. Include a vertically shifted census refusal test.

6. **P2 — Missing one calibration building silently removes its gate.** `tools/audit/interior_points.py:440–448`. An absent, not-found or capped Barracks2 observation is skipped; successful HouseBlock data alone suffices. The native stock contains 52 Barracks2 points, but none need be checked. Deleting Barracks calibration from the implementation survives the entire applicable existing suite because its main build fixture contains only HouseBlock calibration. **Minimal fix:** require usable data and stock points for both specified calibration classes, and refuse with the missing class named.

7. **P3 — Setup ignores the configured path budget.** `tools/setup/interior_sampler.py:361–362`. The guard exists only in `HCProbeReachHit`. With accepted `path_limit=0`, setup still makes one control path query; multiple failed doors can make up to four. **Minimal fix:** apply the same budget guard before every setup path query and leave reachability unknown when exhausted. The fail-closed treatment change in finding 1 must also apply.

Checks without findings:

- Native signatures and argument order match the installed cache: `RaycastRV` in `3_Game/Global/DayZPhysics.c:199`; `PGFilter.SetFlags/SetCost`, `FindPath` and `SampleNavmeshPosition` in `3_Game/AI/AIWorld.c`; coordinate transforms in `1_Core/proto/EnEntity.c:473,499`; `ClippingInfo` in `3_Game/Entities/Object.c:358`; doors in `3_Game/Entities/Building.c:31,73`. The latter explicitly documents `GetDoorSoundPos` as **world space**, so the hook's `CoordToLocal` is correct. All referenced PG flags, area types and intersection constants exist. CallLater is declared in `2_GameLib/tools.c:61`; its one-shot scheduling and argument order match.
- The generated hook passes compile-shape lint against 7,190 native type names. Required out parameters are declared first; `FLT_MAX` is used. This is not an Enforce compilation result.
- Nearest-contact ray ownership, the descending restart, same-slab skip and capped upward search have working synthetic regressions. Roofless surfaces are excluded. A roofed hit is not by itself proof of enclosure or clearance around a player/item; findings 1–4 expose the consequences of treating the remaining filters as sufficient. No native contact/backface or clipping-basis behavior was established here.
- Ray limits are checked before casts. Work is split by rows through one-shot callbacks. Hit-cap and output-cap state are emitted. Row-sized work is bounded but has not been benchmarked. The path budget exception is finding 7.
- JSON fragments are flushed at complete fragment boundaries. The final JSON flush and write-failure check precede sentinel creation. Native `FPrintln` returns void, so handle checks and ordering do not independently establish durable writes.
- Real stock has 10,646 points with exactly `pos/range/height`, and 428 with optional `flags` added. The treatment uses the former supported shape. Both real tenement groups have the expected `lootFloor`, `lootshelves`, `lootweapons` shells; generated points enter only `lootFloor`.
- An in-memory treatment of the actual stock parses, and bytes outside the two edited groups are identical. Existing points/nonzero lootmax are refused. The default lootmax formula is `max(1, min(12, ceil(point_count * 0.25)))`; both group and floor container receive it. Other containers, tags, categories and usage remain unchanged. Selection is sorted and the existing repeatability tests pass. There is no observed loot increase outside the two groups and no duplicate-spawn mechanism in this change. CE ingestion/spawning remains untested.

Mutation results:

All mutations were written to scratch copies and executed against the two existing test modules, excluding only the expressly known launcher test. Baseline: **81 tests, zero failures/errors**. The existing meta-test also passes its bundled mutation battery, but relies in part on exact source anchors.

| Independent scratch mutation | Existing 81-test suite |
| --- | --- |
| Omit Barracks calibration | SURVIVED |
| Prefer height before clearance in per-cell reduction | SURVIVED |
| Replace height mean with first observation | SURVIVED |
| Replace lootmax ceil with floor | SURVIVED |
| Remove outside-group verification | SURVIVED |
| Remove explicit pre-existing-point refusal | SURVIVED |
| Replace exterior control path with destination self-loop | Killed only by source-anchor meta-test; SURVIVED other 80 tests |
| Tighten endpoint gap from 2 m to 5 cm | Killed only by source-anchor meta-test; SURVIVED other 80 tests |
| Disable endpoint-gap test | KILLED behaviorally |
| Disable mesh-altitude test | KILLED behaviorally |
| Increase upward non-owner skip to 50 cm | KILLED behaviorally |
| Disable floor owner test | KILLED behaviorally |
| Disable path budget | KILLED behaviorally |
| Disable calibration threshold refusal | KILLED behaviorally |
| Disable known-reachability filter | KILLED behaviorally |

A surviving mutation indicates missing regression discrimination; redundant checks mean it does not automatically establish a new source defect. The seven explicit review safety regressions all fail on the unmodified commit, with their actual failure output retained.

Commands and actual output (full output in the adjacent logs):

```text
git show --stat 93a3042
 tests/unit/test_interior_points.py  | 602 ++++++++++++++++++++++++
 tests/unit/test_interior_sampler.py | 907 ++++++++++++++++++++++++++++++++++++
 tools/audit/interior_points.py      | 557 ++++++++++++++++++++++
 tools/setup/interior_sampler.py    | 864 ++++++++++++++++++++++++++++++++++
 4 files changed, 2930 insertions(+)

cat docs/SPECIFICATION.md docs/specs/001-survival-overhaul/spec.md docs/RUNTIME_IMPLEMENTATION_CONTRACT.md
cat: docs/SPECIFICATION.md: No such file or directory
cat: docs/specs/001-survival-overhaul/spec.md: No such file or directory
[runtime contract printed]
```

I also viewed the full `git show 93a3042` implementation and used `nl -ba`, `sed`, and `rg` to inspect its four changed files and the API declarations above. No web lookup was needed: the requested exact installed source cache and stock XML were available locally.

Initial confined runs from the real checkout:

```sh
TMPDIR="$PWD/scratchpad-review/tmp" PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_interior_sampler tests.unit.test_interior_points -v > scratchpad-review/targeted-tests.log 2>&1
TMPDIR="$PWD/scratchpad-review/tmp" PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v > scratchpad-review/unit-tests.log 2>&1
```

```text
Ran 82 tests in 5.355s
FAILED (failures=3, errors=5)

Ran 1932 tests in 55.605s
FAILED (failures=8, errors=260, skipped=1)
```

These initial runs put temp fixtures inside the checkout, causing the tools' legitimate outside-checkout refusals. I copied 294 tracked files, without git metadata, to `scratchpad-review/source-copy` and reran with the temp directory beside that copy. These copies contain repository source only, not the stock XML/native cache.

From `scratchpad-review/source-copy`:

```sh
TMPDIR="/code/hc-worktrees/interior-review/scratchpad-review/tmp" PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_interior_sampler tests.unit.test_interior_points -v > ../targeted-copy-tests.log 2>&1
TMPDIR="/code/hc-worktrees/interior-review/scratchpad-review/tmp" PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v > ../full-copy-tests.log 2>&1
```

```text
Ran 82 tests in 4.330s
FAILED (failures=1)

Ran 1932 tests in 60.405s
FAILED (failures=2, errors=155, skipped=1)
```

The targeted failure is exactly the excluded launcher-text test. The full suite still has tools that reject **any ancestor Git checkout**, so this required scratch location cannot satisfy their destination policies. It also reports the known launcher failure and the corresponding deployment CLI failure. These unrelated/confinement failures are not findings against this commit. No all-suite green claim is made.

From the real checkout:

```sh
TMPDIR="$PWD/scratchpad-review/tmp" PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/mutations.py > scratchpad-review/mutations.log 2>&1
TMPDIR="$PWD/scratchpad-review/tmp" PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/mutations.py control-self-loop path-gap-tightened-to-5cm > scratchpad-review/mutation-boundaries.log 2>&1
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/probes.py > scratchpad-review/probes.log 2>&1
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/review_regressions.py > scratchpad-review/review-regressions.log 2>&1
```

```text
BASELINE: 81 tests; 0 failures/errors
[mutation outcomes listed in the table above and verbatim in mutations.log]

Native type names: 7190
Generated hook lint: []
Actual stock treatment parses: prototype
Actual stock bytes outside tenements equal: True
Untested reachability treatment: [('Land_Tenement_Small', 'unknown', 8), ('Land_Tenement_Big', 'unknown', 4)]
Same vertical failure at default threshold 0.6: True [('Land_HouseBlock_2F1', 0.7142857142857143, 0.0)]
One reachable + three unknown placements: 32 eligible; first reach counts: {'yes': 1, 'no': 0, 'nonav': 0, 'unknown': 3}
Disconnected room without snap reach code: 2
Same disconnected room snapped 1m across wall reach code: 1
Interior-door control with NO exterior mesh: {'state': 'tested', 'doors': [[5.0, 0.0, 0.0]], 'entrances': [[7.0, 0.0, 0.0]]} reach code 1
Storeys before/after staircase heights: [0, 1] [0]
path_limit=0 actual path calls: 1
Merged-storey eligible heights where only y=0 and y=3 floors exist: [1.5]
End-to-end tenement treatment selects phantom heights: [1.5]

Ran 7 tests in 0.077s
FAILED (failures=7)
```

Final tracked/staged difference checks:

```sh
git diff --exit-code && git diff --cached --exit-code
```

Actual output: empty; exit code 0. `git status --short` retains the pre-existing untracked `.banso-brief.md` and the new untracked `scratchpad-review/` directory.
