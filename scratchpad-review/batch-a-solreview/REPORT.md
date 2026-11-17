# Batch A adversarial review

**Verdict: MERGE-WITH-FIXES.** Add discriminating behavioral coverage for the
placement integration before merging. No runtime source defect was reproduced
in the submitted implementation; the finding below concerns its regression
protection. No P0 or P1 finding.

Base: `99ff436` (Fuel siphon review fixes, #53). Reviewed the one-line
`HCInteriorModule.c` modification, new `HCInteriorPathgraph.c`, and new
`test_native_wiring_batch_a.py`. All reviewer writes are confined to this
scratch directory. No DayZ, Wine, network, staging, or commit commands were used.

## Findings, most severe first

### P2 — Placement integration test accepts broken control flow and reused props

**Location:** `tests/unit/test_native_wiring_batch_a.py:157`, particularly
the source-position assertions at lines 163–167.

The test checks the text order of the scheduling call, an orientation statement,
ownership bookkeeping, and a rollback log message. It does not execute
`PlaceCandidate`, establish that the call is reachable, check the rollback
return, or establish the contents of `created`. Four deliberately broken scratch
copies each pass all 12 Batch A tests and all 37 existing interior contract
tests:

- Wrap the scheduling call in `if (false)`: no pathgraph updates are scheduled.
- Return immediately after ownership insertion: successful placement never
  reaches scheduling (or site registration).
- Remove the rollback return at `HCInteriorModule.c:359`: a failed creation
  continues into `object.SetOrientation` on a null object.
- Move `created.Insert(object)` outside the creation-only branch: reused props
  get scheduled again and inserted into ownership again; a later partial failure
  can also delete previously owned props as if they were new.

These are counterexamples to what the new test purports to protect, **not
defects present in the submitted source**. The helper's translated unit tests
do not cover its caller's control flow.

**Minimal fix:** add authored-method behavioral tests with explicit synthetic
engine/store collaborators. Check successful placement schedules precisely the
new handles after all orientation and ownership operations; creation failure
deletes only new handles and returns without scheduling; and mixed new/reused
placement neither requeues nor duplicates ownership of reused handles. Keep
native navigation acceptance separate. The scratch prototype
`test_review_behavior.py` demonstrates this approach: four tests pass against
the submitted source and kill all four placement survivors. Its fixtures are
deliberately narrow: two non-searchable props, zero yaw, and synthetic native
calls. It is a review aid, not a complete engine or search-site test suite.

## API, lifetime, cost, and regression assessment

Native evidence was read only from
`~/.cache/hollow-country/native-scripts/scripts-1.30.164289`; no native source
tree was copied into the review artifacts.

- **Signature and call form:** `3_Game/Global/Game.c:1293` defines
  `void UpdatePathgraphRegionByObject(Object object)`. At lines 1295–1302 it
  guards the handle and computes a clipping-radius region from its current
  position before calling `UpdatePathgraphRegion`. `2_GameLib/tools.c:61`
  accepts `CallLater(func, int delay, bool repeat, void param1, ...)` and
  documents milliseconds and retained arguments. The submitted callback,
  100 ms delay, non-repeat flag, and single object argument match that API.
- **Queue category:** `3_Game/tools/tools.c:8` defines SYSTEM as **0**;
  `Game.c:1538` documents that this queue runs without gameplay/pause
  restrictions. `DayZGame.c:1233` returns the indexed queue and line 3026 ticks
  SYSTEM. The submitted code uses the correct symbolic constant. The new
  Python fixture uses an arbitrary synthetic value of 1 consistently; it does
  not establish the engine's numeric category value.
- **Vanilla precedent:** `TentBase.c:795–797` and
  `BaseBuildingBase.c:811–814` restore config-based pathgraph affect and then
  use the same deferred helper. `FireplaceBase.c:1779–1783` changes affect
  explicitly before the call. These support the scheduling idiom, not an
  inference that every furniture config affects navigation correctly.
  `CentralEconomy.c:13` also describes `ECE_UPDATEPATHGRAPH` as updating navmesh
  on placement; its actual interaction with the extra rebuild is unmeasured.
- **Deleted before dispatch / Stop:** the callback belongs to the game, not
  the short-lived module or a local wrapper. The vanilla helper checks the
  argument at dispatch. `HCInteriorModule.c:541` deletes owned props and clears
  ownership; it does not cancel these one-shot callbacks. If a deleted handle
  is invalidated as expected, the native helper skips it. The review-only test
  executes that null-guard *model* after synthetic deletion; it does not prove
  native handle invalidation, deletion timing, or stale-navmesh cleanup.
  A generic `Remove(GetGame().UpdatePathgraphRegionByObject)` would also target
  vanilla callers and is not an appropriate cleanup fix.
- **Rollback:** in the submitted source, failure deletes only `created` and
  returns at lines 357–359. No call is scheduled for that partial layout.
  Successful placement sets orientation, records all new handles, and only
  then schedules at line 376. Site registration follows unchanged. The scratch
  successful/partial-failure cases pass.
- **Reuse:** only the successful `CreateObjectEx` branch inserts into
  `created` (line 352); reusable handles remain excluded. Their transforms have
  already been checked by `InspectProp`. The scratch mixed new/reused case
  passes and schedules only its new handle.
- **Boundedness:** `Schedule` inspects at most eight array slots, skips nulls,
  and makes only non-repeating calls. This is a per-call cap, not a global
  queue cap or a time budget. Startup has at most 12 candidates; current
  layouts/import admission have two props each, giving at most **24** updates.
  The module's five-prop ceiling would allow **60** if layouts expand within
  that ceiling. They share a 100 ms deadline and can land in one SYSTEM tick.
  No recurring scan or queue growth path was introduced. Rebuild time and
  regional overlap costs remain unmeasured for the intended 3–6 players.
- **Enforce syntax:** all seven `test_script_syntax.py` tests pass, including
  installed-prototype override-name checks. The helper introduces no override,
  leading logical-operator continuation, exponent literal, or bare enum member.
  These checks are not an Enforce compilation of the final source.

## A17 and C4

The whole-mod noise-target ban kills an injected native `AddNoiseTarget` call.
The provenance pin rejects enabling `VisualSamplingAvailable`. Inverting the
actual `if (!visualObserved)` guard nevertheless survives the **new** lexical
pin: its name/order checks alone do not establish the guard's behavior.
Crucially, the **existing** `test_infected_perception.py` suite kills that
mutant on hidden-coordinate access for both chase and fight states, so this
is not an unprotected suite-wide regression or an additional blocking finding.
The original existing perception suite passes all three tests.

The C4 pin kills deletion, conditional execution, and late execution of
`super.ProcessSoundVoiceEvent(sound_event, aw)`. The original override's names
match `ZombieBase.c:583`, calls super first unconditionally, and adds no second
noise operation. Vanilla server noise emission remains visible at
`ZombieBase.c:597–600`. Runtime audio/hearing and two-client behavior remain
unqualified.

## Executed checks and mutation evidence

The requested full suite was run **once**, from this worktree:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit > scratchpad-review/batch-a-solreview/full.log 2>&1
```

Result: **2,561 tests, 215.385 seconds, OK (skipped=1), exit 0**. The log's
negative CLI-test diagnostics are expected; there is no test failure.

Focused syntax command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover
-s tests/unit -p test_script_syntax.py -v` → **7 passed** (`syntax.log`).

On every validated scratch copy, the focused mutation command was
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p
test_native_wiring_batch_a.py -v`. Baseline: **12 passed**, including all native
cache checks. Of **16 mutants**, **11 were killed and 5 survived** this command.

| Mutant | Batch A focused result | Follow-up evidence |
| --- | --- | --- |
| Remove scheduling call | KILLED | Integration source pin |
| Raise cap 8 → 800 | KILLED | Synthetic boundedness assertion |
| Delay 100 → 1000 ms | KILLED | Exact scheduled-call assertion |
| Repeat false → true | KILLED | Behavior assertion and source pin |
| Remove server guard | KILLED | Client fixture |
| Remove null-prop guard | KILLED | Null-entry fixture |
| Put scheduling in dead branch | SURVIVED | Existing interiors: PASS; review behavior: KILLED |
| Return before scheduling | SURVIVED | Existing interiors: PASS; review behavior: KILLED |
| Remove rollback return | SURVIVED | Existing interiors: PASS; review behavior: KILLED |
| Queue/own reused props again | SURVIVED | Existing interiors: PASS; review behavior: KILLED |
| Enable visual sampling | KILLED | Availability source pin |
| Invert actual visual guard | SURVIVED | Existing perception: KILLED |
| Inject native noise target | KILLED | Whole-mod ban and voice noise pin |
| Remove voice super call | KILLED | First-statement pin |
| Make voice super conditional | KILLED | First-statement pin |
| Invoke voice adapter before super | KILLED | First-statement and ordering pins |

Machine-readable details are in `mutation-results.json`; each
`mutants-validated/<id>/` retains its changed source, patch, and focused logs.
`mutation_review.py` creates the isolated copies; `verify_survivors.py` runs the
follow-up suites. The first harness attempt lacked a transitive test import;
its results were discarded. All counts above use the corrected, passing
baseline. No import/translation failure is counted as an independent mutation
kill. The rollback mutant's null dereference is its intended behavioral
failure, not a harness setup error.

After artifact compaction, the harness scripts can regenerate complete scratch
trees by removing only their `mutants-validated` output directory and rerunning
the mutation script followed by the survivor script. Do not run tests directly
inside compacted mutant directories: only changed source and logs are retained.

## Acceptance and available context

`docs/RUNTIME_IMPLEMENTATION_CONTRACT.md`, `docs/MODULE_STATUS.md`, `AGENTS.md`,
and the Banso task brief were available. The prescribed
`docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md`, and
feature spec/plan/tasks artifacts, are absent from this checkout; no claims of
alignment with their unavailable contents are made. The Banso skill's
task-contract guidance was applied without lifecycle commands or state writes.

`HCInteriorRules.PlacementAccepted()` and `SearchAccepted()` remain false;
diagnostic placement is still explicitly gated. This review accepts no missing
engine experiment. Final-source DayZDiag compilation, normal PBO/server loading,
observed navigation around new and deleted props, rollback/Stop timing, actual
furniture pathgraph affect, and load measurements remain pending; multiplayer
audio/visibility/replication acceptance requires the prescribed client trials.
