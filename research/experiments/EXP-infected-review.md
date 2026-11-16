# Infected adversarial source review

Date: 2026-11-16. Scope: `mods/HollowCountry/scripts/4_World/Infected/**`.
Reviewer owns this report only; no implementation, tests, packaging or shared
documentation edited. AGENTS.md, runtime contract, specification, plan and tasks
were read. T018–T022 / AC-007–008 remain pending native acceptance.

Installed evidence root (abbreviated **N** below):
`/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`.
Native execution was unavailable. No Enforce compilation, DayZ behavior,
two-client result or runtime fix is claimed. The main thread's reported full
245-test snapshot pass is separate evidence; this reviewer did not run that suite.

## Findings and disposition

Main applied the fixes after closing Linnaeus's concurrent implementation work.
Final reread and scoped tests completed after main's final notification. All four
reported findings are resolved at the source-review level in the pinned snapshot;
no additional concrete compile/API defect was identified. Native acceptance is
still pending. Original locations below describe the defects before correction.

| ID | Priority | Source finding | Status |
|---|---|---|---|
| IR-01 | P2 | Release loses ownership when default-group allocation fails | Resolved in source; native cleanup untested |
| IR-02 | P2 | Accepted work cap eight cannot collect three adoption candidates | Resolved; adoption minimum nine enforced |
| IR-03 | P2 | Cached members and persisted route status can outlive native membership/route | Resolved for pack progress/active-route status |
| IR-04 | P2 | Low-budget adoption repeatedly scans the same assigned prefix | Resolved; persistent bounded rotating scan |

**IR-01 — Preserve failed-release ownership.** Original
`HCInfectedNavigation.c:181–192` continues when `CreateDefaultGroup()` fails,
then unconditionally clears the member list and group handle. Callers also
discard the pack after Tick returns false (`HCInfectedModule.c:449–452`).
Members still in that native group lose retry/expiry ownership. The local hold
waypoint reduces movement intent, but does not prove group release or CE cleanup.
Native basis: **N** `3_Game/AI/AIWorld.c:79–87` declares group creation and
documents that DeleteGroup destroys attached agents;
`3_Game/AI/AIGroup.c:6–14` requires removing old membership and warns empty
groups disappear next frame. Fix must retain failed-release ownership, account
for pending cleanup against caps, and bound retries without abandoning handles.
Native allocation failure and shutdown cleanup still require actual trials.

**IR-02 — Reject an impossible adoption budget.** Original
`HCInfectedModule.c:82–85` accepts eight work items, while `:315–333` examines
at most `m_WorkCap - 6` candidates and requires at least three. At cap eight,
even three adjacent eligible actors cannot be adopted. Earlier startup also
accepted caps four through seven without routes; the updated horde minimum eight
still leaves this boundary defect. Require at least nine for adoption or change
the candidate budget/scheduling. Native source has no bearing on this arithmetic;
the inconsistency is entirely in authored policy.

**IR-03 — Reconcile actual native membership and route metadata.** Original
`HCInfectedNavigation.c:131–150` treats any live cached member as leader/progress
without checking that its current agent still belongs to Group. A member
transferred elsewhere can keep this pack apparently progressing. Original
`HCInfectedModule.c:353–357` sets HasRoute/RouteEnd, while route failure at
`:449–452` discards the pack without clearing that status. The persisted record
can advertise a route after patrol has stopped. Native basis: **N**
`3_Game/AI/AIAgent.c:6–7` exposes current GetGroup; `AIGroup.c:6–14` documents
native group lifetime. Reconcile live membership and route state separately
from immutable reservations/tombstones. Do not refill losses or rebind by
classname/proximity. Original finite reservation retention is intentional;
retired/unresolved groups occupying the finite ledger is not itself a bug.

**IR-04 — Rotate adoption work.** After the minimum-budget correction, cap nine
with six eligible actors could adopt indices 0–2, then repeatedly inspect only
those assigned actors, permanently ignoring indices 3–5. The default cap 32 was
unaffected. Final `HCInfectedModule.c:35,323–329` retains m_AdoptionCursor and
scans at most min(actor count, work cap minus six), advancing through the actual
array with NextAdoptionCursor. Empty arrays execute zero iterations, avoiding
modulo zero. The synthetic two-interval regression visits 0–2 then 3–5.

Final fix evidence:

- **IR-01:** `HCInfectedNavigation.c:5,24–29,62,187–258` retains pending packs
  statically, places hold intent, checks actual ownership, and limits allocation
  attempts to three with five-second backoff. Exhaustion retains handles and
  blocks new packs; it does not silently destroy agents. Module line 438 retries
  before the health check, so quarantining does not orphan retained cleanup.
  Pending ownership is structurally bounded by two horde packs, two investigators
  and at most one partial transfer while new starts are blocked. Shutdown has
  no promised future ticks; retained/hold state is a fail-closed fallback,
  not proven eventual native cleanup.
- **IR-02:** `HCInfectedPolicy.c:143–146` admits adoption budgets 9–32;
  `HCInfectedModule.c:89–92,316–328` wires that rule at startup and adoption.
- **IR-03:** `HCInfectedNavigation.c:156–159` checks current native membership
  before counting leader/progress. `HCInfectedModule.c:475–478` clears HasRoute
  when the pack ends or releases; `:407–432,533–539` clears it before shutdown
  save; `HCInfectedState.c:242–247` clears it after restart. RouteEnd remains
  historical. Immutable reservations remain intact; a logical cohort ledger
  is not a live native membership roster.

## Compile/API and contact guard

No definite missing-symbol/signature error was identified by source comparison.
This is not a compiler pass. Relevant installed declarations match the authored
calls:

- **N** `4_World/Entities/Creatures/Infected/ZombieBase.c:92–100,583–601,613`:
  EOnInit, protected ProcessSoundVoiceEvent and FightLogic; stance is protected
  at line 10 and assigned in 0–3 at line 96.
- **N** `3_Game/Entities/DayZAnimal.c:191–193`: DayZCreatureAI.GetAIAgent;
  `3_Game/AI/AIWorld.c:59–67,79–122`: PGFilter, groups, FindPath and nav sampling;
  `3_Game/AI/AIGroupBehaviour.c:7–31`: waypoint DTO and SetWaypoints.
  Its line 25 specifies loop=false means patrol, not a single traversal.
- **N** `3_Game/Entities/DayZInfectedInputController.c:9–10`: mind/target;
  `3_Game/Global/DayZPhysics.c:128–144,199`: sorted geometry raycast;
  `3_Game/tools/JsonFileLoader.c:69–96`: JSON string load/make;
  `1_Core/proto/EnSystem.c:417–425`: OpenFile/ReadFile into a string.

The contact guard at `HCInfectedNative.c:24–39` **does skip this invocation's
script damage branch** when CanAttackToPosition rejects the target. **N**
`ZombieBase.c:628–676` checks WasHit and invokes damage at 658, 664 and 670;
`:265–267` shows true only returns from command handling. It does not cancel
the attack command, consume a hit event or demonstrate physical contact.
**N** `3_Game/Entities/DayZInfected.c:49–52,115` exposes native WasHit and
CanAttackToPosition without their consumption/geometry semantics. Do not call the
guard an accepted through-wall-hit correction. Its existing default-off caveat
is accurate. Required trial: attack starts, target moves behind wall/closed door,
then emerges during the same command; record authoritative health and command/hit
lifecycle, ordinary same-side/block controls, and two observers.

## Authority, bounded work and persistence

Voice provenance is source-authoritative at the local emission hook:
`HCInfectedNative.c:15–21` calls super once, then records the server callback.
**N** `ZombieBase.c:583–601` separates client sound rendering from server
AddNoise. **N** `3_Game/DayZAnimEvents.c:218–249` loads m_iID from config:
this is an event **type**, not a unique propagation/root ID. NoiseParams proves
neither client audibility nor delivery to any particular infected.
The queue applies a clue to its emitter only; it does not implement forwarding,
recipient hearing, root/hop lineage or attribution of a gunshot chain. Metadata
TTL/hop limits therefore do not bound the engine's native alert graph.

Visual memory uses a current native target as candidate, then distance/cone and
both sorted view/fire raycasts before caching a frozen point
(`HCInfectedNavigation.c:198–245` in the original snapshot). This avoids directly
routing to an occluded current target. Actual proxy intersections, lighting/native
perception parity and no hidden tracking remain native tests.

Source work has finite containers: <=24 actors, <=32 queued voices, <=2 group
records with 3–6 members, <=2 investigators; bounded lookups, callback admission,
one visual candidate/two rays and one investigation route attempt per core tick.
Path result rejection above 32 points occurs after FindPath; it does not cap
native path-search time. Logical work items are not measured CPU budgets.
The independent per-tick 3600-second retirement added in Module avoids retirement
depending on a completed actor sweep. Pending-release retention adds the structurally bounded owner list described
above; successful cleanup and group lifetime are still unobserved. Intended 3–6-player profiling remains outstanding.

`HCInfectedState.c:168–269` validates schema/build/world/clock, generation pairs,
finite coordinates and immutable/nonincreasing membership. Existing corrupt slots
quarantine rather than falling back. Restart converts active records to
unresolved and preserves reservations; no exact native entity identity is stored,
and no member recreation occurs. This supports conservative no-refill accounting,
not persistent horde recovery. Truncate/write/readback is not proven atomic or
fsync-durable; **N** JsonFileLoader and EnSystem expose ordinary I/O only.
Missing both slots initializes a new ledger, so operator deletion/reset is outside
the no-refill guarantee. Adoption observes ZombieBase hooks, not a verified CE
ownership/global-population query. Existing counts are not increased by this
source, but its ledger cannot establish the world's total CE occupancy.

## Exact documentation status

| Area | Authored source, native behavior untested | Missing gameplay/implementation |
|---|---|---|
| Competence/contact/injury | Retained native collision/AI/audio/crawl; optional attack-invocation filter | Proven competence improvement, reliable doorway correction, supported extra injury effects |
| Routing/search | Optional native group waypoints, reachable last-seen point and <=3 nearby navmesh anchors, expiry/interruption | Semantic building/room catalog, ordered methodical room search and complete door policy |
| Variants | Existing CE appearance/location preserved; civilian/military attention and anchor overlays | Custom recognizable behavior/location distributions, stalker behavior and door trade-offs |
| Chains | Existing native hearing; bounded native-emitter instrumentation | Supplementary audible rebroadcast, actual recipient/root/hop attribution and physically validated propagation |
| Hordes | Finite logical cohorts; optional native patrol source; conservative persisted reservations | Abstract movement/materialization, observer hysteresis, global CE reconciliation, durable exact membership/rebinding and resumable persistent migration |

Logical cohorts are **not full persistent hordes**. Routing APIs are present;
optional routing source is already authored. Their native behavior is untested,
rather than categorically unavailable. Nearby anchors are not semantic rooms.
Do not label missing gameplay as merely “awaiting playtest.”

Remaining native gates: actual Enforce compilation; DayZDiag policy/lifecycle and
normal PBO/server loading; CE group transfer/release and failure cleanup; patrol,
navmesh/doors, perception, crawl/combat interruption; queued-hit behavior;
native JSON corruption/crash/restart and CE reconciliation; two-client audio,
network and visibility; measured 3–6-player performance. No missing experiment
is accepted, and all production feature enablement remains pending.

## Scoped verification

Reviewer ran only the scoped infected suite (initially 15, then 19, finally 20
tests as the owners added regression coverage). Final run:

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_infected_contract.py -v
Ran 20 tests in 0.008s
OK
```

This executes translated scalar policy bodies and source assertions, not DayZ.
A separate in-memory stdlib unittest derived minimum startup cap, scan reservation
and cohort minimum from Module source; it failed as expected before the fix:

```
assertGreaterEqual(accepted_min - scan_reserve, required_members)
AssertionError: 2 not greater than or equal to 3
Ran 1 test in 0.000s
FAILED (failures=1)
```

No persistent test file or source edit was made by this reviewer. Main reported
three actual source-contract failures before wiring the first fixes, then 19
passing tests; the cursor regression subsequently failed for a missing policy
before the final 20-pass run. Those red histories belong to main; this review
independently observed the final pass and inspected wiring/control flow.
Source assertions and translated policies do not execute native release, file
I/O or navigation. No full-project suite was rerun. Scoped report whitespace
verification passed.

## Frozen source pins

SHA-256, paths relative to `mods/HollowCountry/scripts/4_World/Infected/`:

```text
HCInfectedModule.c      2b6f7ccc160eb712a718bd17b5db0ab4cd49036e2c8153498b237e9b48b31c6c
HCInfectedNative.c      656e80af5829a1734a09fafbcbbc98a3eda560521871681d7603ad1a89bf0da9
HCInfectedNavigation.c  8f486358ca3dbcbaad7e3084e5058673f17eb963f58bafcb64453096ec343739
HCInfectedPolicy.c      b40dcd3e1ab1446484e6956ef1dbbdc7ee07a2f3aeacdf88dc49dc483b348010
HCInfectedSelfTests.c   0ae8b6522fc6a4d930f0bb629e29e23372a8c4c4c831369bcad9749c93d56a49
HCInfectedState.c       e5c7d2007895eafd40b417f5e68b8211bc5e79baf054fd70d90d71f34701a0e4
```

`tests/unit/test_infected_contract.py`:
`31e666812a102f3fa7e4dc842ec2fa83f2b63ff57905b00c12b1f9c15e9b0e8c`.

Native evidence pins, relative to **N**:

```text
3_Game/AI/AIWorld.c             6ffd6f8b6e1d80d9f612ef59958bd0e5960432176fa6c1cd27458239b3b124a3
3_Game/AI/AIGroup.c             10a6977e87af518e2576ab7f9199da40013aec1d50b46f7b6b954c9aa013686f
3_Game/AI/AIGroupBehaviour.c    a4ad32738a782bd30f93c38f765957f90b9e1153596f41c4e6ca08dfb78738e1
4_World/Entities/Creatures/Infected/ZombieBase.c
                               c67ec8fdaa8db1fddab20fb8ed0bdeffa0e8785566ee869f465e97803223660c
```
