# B04 WP2 — D2/D3 source fixes

2026-11-17. Scope: #19/#20/#22, audit WP2. Source implementation and offline
regressions only. Runtime acceptance and production qualification remain pending.

## Files changed

- `mods/HollowCountry/scripts/4_World/Infected/HCInfectedNavigation.c`
- `tests/unit/test_infected_routes.py`
- `tests/unit/test_infected_perception.py` (new)
- `tests/unit/test_infected_pack_ownership.py` (new)
- `scratchpad-review/wp2/REPORT.md` (this report)
- `.banso-writer/commit-message` (uncommitted writer control file)

No shared Module, State, Policy, Profiles, BDD binding, or other product files
were changed. No git commands, DayZ, Wine, or PowerShell processes were run; no
writes were made under `/mnt/d`. Tests with native-launcher names use their
existing synthetic/mocked collaborators; they do not establish engine behavior.

## Design inputs and traceability

Read `AGENTS.md`, `docs/RUNTIME_IMPLEMENTATION_CONTRACT.md`, the audit's D2/D3
findings and WP2 contract, and its `test_audit_findings.py`, all read only.
The audit lives at
`/code/hc-worktrees/b04-audit/scratchpad-review/b04/`.

Both required local specification paths are absent. Read the available external
design copies at `/code/dayzsa_mods/docs/SPECIFICATION.md` and
`/code/dayzsa_mods/docs/specs/001-survival-overhaul/spec.md`, plus the relevant
`plan.md`, `tasks.md`, and `completion-plan.md` material there. Those copies are
design input, with no assertion of historical identity to this worktree or of
runtime acceptance. Active session rules prevail: 3–6 players, private source,
source authoring before client join, and no public/Workshop publication.

D2 maps to FR-008, NFR-002, AC-007, T019/T020, AI-04/PHY-01 and the no-hidden-live-
position rule in specification §6.1. D3 maps to FR-009, NFR-003/004, AC-008,
T022 and bounded native ownership/fallback. This report does not complete those
larger requirements or waive their experiments.

## Implementation

### D2 — unknown visual provenance

`HCInfectedObservation.VisualProvenanceEstablished(controller)` returns false:
the inspected installed controller has no fresh, lighting-aware sight receipt.
`SampleVisual` checks that gate before `GetTargetEntity` or any target-coordinate
read. Unknown observations cannot replace frozen visual memory, update timestamps,
or reset search attempts. The scalar geometry predicate now receives the actual
gate result rather than a hard-coded true.

Native pursuit is untouched. Existing frozen clues and their consumers are
unchanged. The range/FOV/two-ray/valid-position checks and visual stamping code
remain behind the closed provenance gate; geometry remains a prerequisite, never
a sight receipt. No evidence-backed positive native visual producer was found in
this path, so no new positive producer or Boolean configuration bypass was added.
Fresh authored visual acquisition remains unavailable until a genuine observed
source is implemented and qualified.

The auditory counterexample was ported to execution of the actual authored
`SampleVisual` body. Its fixture explicitly supplies a retained auditory target,
clear geometry, in-range/in-FOV values, and no visual provenance. A second test
checks both chase and fight and asserts that no target or coordinates were read.

### D3 — verified per-member fallback ownership

`m_ReleaseFallbacks` records each member's expected native fallback before
detachment. Release clears a member only on confirmed non-null expected ownership
or disappearance of the entity itself. A missing AIAgent, ungrouped survivor,
missing old Group, or unexpected third owner does not count as successful rehome.
Unexpected owners are not detached. A void RemoveAgent is checked before AddAgent.

Ungrouped members retry the recorded fallback. If AIWorld has deleted an empty
fallback, a replacement is recorded before another attempt. The existing shared
`MayRetryRelease` policy still permits at most three attempts with five-second
cooldowns. After exhaustion, the next release poll latches quarantine and emits
one diagnostic; members and pending-release tracking stay retained, and the
existing pending-release Start gate blocks replacement packs. No further native
transfer mutations occur. A later observation of the expected owner can complete
release even after exhaustion; absence of the old owner cannot.

`IsReleaseQuarantined()` exposes the exhaustion marker for optional WP1 status
reporting. The marker records that quarantine occurred; successful later cleanup
removes the pack from pending tracking. No persistence/restart guarantee is added.

Synthetic tests cover failed AddAgent, cooldown, successful retry into the same
fallback, allocation failure, failed RemoveAgent, missing AIAgent, unexpected
third ownership, an ungrouped partial Start, partial member confirmation, finite
exhaustion, and delayed confirmation. Existing route/scheduler checks are intact.

## Actual RED and GREEN

Tests were written and run against the unchanged navigation source first.
The exact command for both runs was:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_routes tests.unit.test_infected_perception tests.unit.test_infected_pack_ownership -v
```

RED output excerpts (exit 1):

```text
test_retained_auditory_candidate_is_not_a_confirmed_visual_observation (tests.unit.test_infected_perception.InfectedPerceptionTests.test_retained_auditory_candidate_is_not_a_confirmed_visual_observation) ... FAIL
AssertionError: True is not false : Clear geometry and retained sound target do not prove native sight
test_release_does_not_forget_member_after_failed_fallback_add (tests.unit.test_infected_pack_ownership.InfectedPackOwnershipTests.test_release_does_not_forget_member_after_failed_fallback_add) ... FAIL
AssertionError: True is not false : No old owner is not proof of fallback ownership
Ran 21 tests in 0.122s
FAILED (failures=12)
```

The twelve failures include the chase/fight subtest assertions; there were no
translation/import errors. The route test import was made compatible with both
package invocation and the existing discovery invocation before this run.

GREEN after the navigation fix (exit 0):

```text
test_retained_auditory_candidate_is_not_a_confirmed_visual_observation (tests.unit.test_infected_perception.InfectedPerceptionTests.test_retained_auditory_candidate_is_not_a_confirmed_visual_observation) ... ok
test_release_does_not_forget_member_after_failed_fallback_add (tests.unit.test_infected_pack_ownership.InfectedPackOwnershipTests.test_release_does_not_forget_member_after_failed_fallback_add) ... ok
Ran 21 tests in 0.190s
OK
```

Required full checks, both exit 0:

```text
$ PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit
Ran 2374 tests in 76.932s
OK (skipped=1)

$ python3 -B -m tools.validate.bdd
Ran 1276 tests in 32.131s
OK (skipped=1)
Bound offline scenarios: 61; runtime acceptance: NOT EXECUTED
```

The full unit run includes `test_script_syntax.py` and
`test_script_identifiers.py`; both remain green. The native-cache-dependent
checks ran with the installed cache present. No Enforce compilation was executed.
New regressions execute a restricted translation of shipped method bodies with
explicit synthetic collaborators; they are not a replacement gameplay model or
proof of native transfer, perception, collision, audio, or replication.

## Installed native API citations

All paths in this section are relative to the inspected local snapshot:
`/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`.
These are declarations/source observations, not runtime receipts.

| Surface | Native source citation and implication |
|---|---|
| Membership confirmation | `3_Game/AI/AIAgent.c:7` — GetGroup is the ownership observation used to confirm the expected fallback. |
| Native transfer | `3_Game/AI/AIGroup.c:11` AddAgent, `:12` RemoveAgent; both return void. `:9` documents next-frame deletion of empty groups. `:14` GetBehaviour. |
| Fallback allocation | `3_Game/AI/AIWorld.c:83` CreateDefaultGroup; `:77` documents managed empty-group lifetime. `:79` CreateGroup is the existing route group allocator. `:87` DeleteGroup destroys agents and is never called. |
| Waypoint intent | `3_Game/AI/AIGroupBehaviour.c:12` waypoint constructor; `:27` SetWaypoints. Existing stop/route intent remains native. |
| Entity agent/controller | `3_Game/Entities/DayZAnimal.c:193` GetAIAgent; `3_Game/Entities/DayZInfected.c:107` GetInputController. |
| Insufficient perception surface | `3_Game/Entities/DayZInfectedInputController.c:9` GetMindState; `:10` GetTargetEntity. Neither declares fresh visual provenance. `3_Game/Entities/DayZInfected.c:16`/`:17` chase/fight constants. |
| Actor observations | `3_Game/Entities/Object.c:517` IsAlive, `:994` GetHealth; `4_World/Entities/Creatures/Infected/ZombieBase.c:182` GetMindStateSynced. |
| Position/direction and dormant visual geometry | `3_Game/Entities/Object.c:287` GetPosition, `:314` GetDirection, `:873` ModelToWorld; `3_Game/Entities/EntityAI.c:3843` GetDefaultHitPosition, overridden at `4_World/Entities/Creatures/Infected/ZombieBase.c:166`. Unknown sight returns before target sampling. |
| Existing raycast guards | `3_Game/Global/DayZPhysics.c:199` RaycastRV; geometry kinds documented at `:140`. Geometry cannot prove lighting-aware sight. |
| Existing nav filter/path sampling | `3_Game/AI/AIWorld.c:65` SetFlags, `:67` SetCost, `:98` FindPath, `:122` SampleNavmeshPosition. These APIs and the bounded route logic are unchanged. |
| Game/world access | `3_Game/gameplay.c:636` GetGame; `3_Game/Global/Game.c:931` GetWorld, `:1120` IsServer, `:612` ConfigIsExisting; `3_Game/Global/World.c:116` GetAIWorld. |
| Expected-owner map | `1_Core/proto/EnScript.c:866` map.Get (null if absent), `:902` map.Set, `:906` map.Remove, `:857` map.Clear. The map is bounded by the pack's existing six-member limit. |
| Existing collections | `1_Core/proto/EnScript.c:380` array.Count, `:394` Find, `:407` Insert, `:463` Remove, `:502` RemoveItem, `:399` Get/index access; `:743` set.Count, `:744` set.Clear, `:750` set.Get. |
| Existing math | `1_Core/proto/EnConvert.c:153` vector.Normalize, `:196` Distance, `:210` DistanceSq, `:284` Dot; `1_Core/proto/EnMath.c:225` AbsFloat, `:553` Min. |
| Cast/logging | `1_Core/proto/EnScript.c:94` Class.Cast; `1_Core/proto/EnDebug.c:96` Print. No new gameplay native API was introduced. |

## Remaining gaps and WP1 interfaces

No Module/State change is required for the D2/D3 source corrections. Existing
`HCNativeInfectedPack.RetryPendingReleases()` remains called before the module's
health early return, so quarantine does not discard pending objects.

WP1-owned follow-up requests:

1. Keep visual sampling admission unavailable while
   `HCInfectedObservation.VisualProvenanceEstablished(DayZInfectedInputController controller)`
   is false, and report that reason independently of operator preferences.
   Do not replace it with requested=true, target presence, or clear geometry.
   A future observed-source adapter needs separate reviewed frozen-cue provenance
   and native qualification; this patch supplies no positive evidence.
2. If shared status reporting needs the distinction, use the new
   `bool HCNativeInfectedPack.IsReleaseQuarantined()` marker together with
   `IsReleasing()` and the Release return value. Preserve unresolved reservations
   and pending tracking; do not interpret lack of the old Group as success or
   reset the retry budget. Source ownership state is in memory only; restart and
   persistent cohort reconciliation remain WP1/WP7 work.
3. Add explicit BDD scenarios/bindings for `test_infected_perception.py` and
   `test_infected_pack_ownership.py` in the WP1-owned feature/binding files.
   Suggested behaviors: retained auditory targets cannot refresh visual clues;
   failed fallback adds retain unresolved members through bounded retry and
   quarantine. The current BDD run executes existing bound scenarios, including
   routes, but does not bind these two new test modules. Full unit discovery
   does execute both.

Pending runtime work: pinned DayZDiag and normal PBO/server compilation and
ownership tests; injected/observed add/remove/allocation failures where feasible;
AIWorld group invalidation and delayed ownership observations; native pursuit
controls under daylight/darkness/fog/occlusion and auditory-only retention; two
clients for visibility/audio/network assertions; CE/death/corpse/restart cleanup
and measured budgets at the intended 3–6-player load. No engine experiment is
marked accepted and no production capability is enabled by this report.
