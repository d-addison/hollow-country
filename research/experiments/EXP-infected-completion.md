# Infected source completion — 2026-11-16

Scope: T020 / T021 / T022, FR-008 / FR-009, AC-007 / AC-008. This is
source engineering under the existing Banso specification and task graph, not
engine acceptance. Production flags remain false. Client playtesting is deferred.

## Execution plan

1. Inspect installed 1.30.164289 voice, entity persistence and navmesh interfaces.
2. Record actual failing behavioral tests for root TTL/hops/recipient deduplication,
   deterministic room ordering and exact persistent-member recovery eligibility.
3. Implement a bounded supplementary clue graph driven exclusively by actual
   native voice callbacks. Each relay needs another real native voice; do not
   manufacture a hearing target, force an unsynchronized sound or track players.
4. Add an explicit, bounded room-anchor registration/catalog interface. Require
   measured catalog admission and exact house binding; ship no invented room
   coordinates. Order eligible anchors deterministically and revalidate native
   reachability for every route segment before transferring agents.
5. Persist exact nonzero four-part native member IDs and classnames when available.
   Reconcile only entities actually observed loading from storage. Zero, missing,
   duplicate, conflicting or unproven identities remain unresolved; never respawn,
   infer membership from proximity, or release spent population reservations.
6. Run focused regressions and the existing infected suite; inspect the final
   source for lifecycle/work-budget gaps. Report remaining engine gates explicitly.

## Native inspection

Private installed snapshot:
`/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289`.
No purchased source is copied into this repository.

- `4_World/Entities/Creatures/Infected/ZombieBase.c:556–605`: native
  `OnSoundVoiceEvent` resolves an `AnimSoundVoiceEvent`; `ProcessSoundVoiceEvent`
  renders sound on non-headless peers and calls native `NoiseSystem.AddNoise`
  on the server. Our supplementary graph observes this path after `super`.
- `3_Game/DayZAnimEvents.c:218–265`: event IDs and native noise params exist;
  a dedicated server does not construct a playable client sound builder. A
  server callback alone cannot establish two-client audibility or transmission.
- `3_Game/Entities/EntityAI.c:3374`: `GetPersistentID(out int, out int, out int,
  out int)` exists. `AfterStoreLoad()` at 1419 is a storage-load lifecycle hook.
  This does not prove CE infected are saved or receive durable nonzero IDs.
- `3_Game/Entities/EntityAI.c:1381` warns the native persistent-ID lookup is
  available only in the after-load event. No arbitrary-tick lookup is used.
- Existing inspected `AIWorld.SampleNavmeshPosition` / `FindPath`, native pack
  `SetWaypoints`, `Object.ModelToWorld` / `WorldToModel`, and physics raycasts
  remain the movement/geometry interfaces. No new steering or spawn API.

## TDD evidence

Actual command used throughout:
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p 'test_infected*.py' -v`.

- Initial focused RED: 10 errors, missing authored files/policies. Recorded in
  `tests/fixtures/runtime/infected-completion-tdd-red.txt`.
- Integration RED: missing audible investigation wiring and dedicated recovery
  cursor; 2 failures. Fixed frozen clue routing and one-per-tick rotating recovery.
- Seed RED: missing self/external distinction; 1 failure. Fixed self-investigation
  exclusion and refused calm ambient voices as alarm roots.
- Recipient scheduling RED: missing rotating start; 1 failure. Fixed permanent
  registration-order bias under the short voice processing window.
- Native compile-001 RED observed in the actual official server under Wine/Xvfb:
  `HCInfectedState` fields `World` and `Entity` clash with type names. Renamed to
  `WorldName` / `InfectedEntity`; proactively renamed the navigation helper to
  `GetAIWorld`. Error log at local
  `/home/david/.cache/hollow-country/wine-server-20261116/experiments/compile-001/profiles/error_2026-11-16_15-49-17.log`,
  SHA-256 `cb137c59bb31537cd7c048ec033ace0c0c0811ea2652a2d5278be45308e37a4c`.
- Native compile-002 RED reported `HCInfectedRooms.c:67,119` broken expressions:
  `owned` / `local` are keywords. Renamed `ownedSurvey` / `localPoint`. The rename
  audit also found two accidental `GetGame().GetGetAIWorld()` calls introduced by
  the earlier identifier replacement (rooms and module); restored both to exact
  installed `GetGame().GetWorldName()`. New focused test failed in three subchecks
  before repair, then passed. A full infected search now finds no such calls.
- Native compile-003 RED: room survey `HouseType` clashes with a native enum and
  binding `Building` clashes with a native class. Renamed exact identifiers to
  `BuildingClass` and `HouseObject`. A proactive intersection with all **7,455**
  installed class/enum/typedef names also found method `Step`; renamed it to
  `ProcessPending` and updated the module call/test. The audit regression failed
  on `Step` before repair. No substring replacement was used in this pass.
- Final local GREEN before compile-003: **38 tests**, 0 failures, 0 errors;
  `Ran 38 tests in 0.038s; OK`. Scoped `git diff --check` also passed. The additional
  native-name audit regression brings the subsequent focused suite to 39 tests.
- Native compile-004 RED: actual server error log
  `experiments/compile-004/profiles/error_2026-11-16_15-57-06.log`, SHA-256
  `cc06e8787bf28c988cdf587d593bacae41bd0dca41c7d3848fe2d05f8a979e3e`,
  reports `HCInfectedPolicy.c:11: Formula too complex` three times, then errors
  involving vanilla generic types. These later messages are recorded as possible
  cascades, not independently diagnosed native defects. A focused complexity
  regression was actually RED with 12 failing subchecks. Long conjunctions in
  policy admission, state config validation and audible-clue selection were split
  into small guards while preserving comparison/NaN rejection and short-circuit
  authority checks. The policy translator executes the revised guard bodies.
  **Final focused GREEN: 40 tests in 0.044s, OK**; scoped whitespace check passes.
  No infected expression now exceeds six boolean operators. Compiler success
  still requires the next actual server pass; this source is frozen for it.
- Native compile-005 RED: actual error log
  `experiments/compile-005/profiles/error_2026-11-16_16-00-52.log`, SHA-256
  `e56f794884d23d66037d15b7ce4ff5936377ef3c48875e1e25c6f66c20c6fa76`,
  first fails `HCInfectedModule.c:308: Incompatible parameter 'living'` on vector
  division by scalar. Installed `3_Game/Entities/CachedInfosInstanced.c:93` uses
  reciprocal scalar multiplication for a centroid (`tmpPos * (1 / count)`).
  Replaced the vector division with that supported pattern and an explicit
  floating reciprocal from bounded `CentroidWeight` (valid live count 1–6).
  The new scalar/wiring regression actually failed on missing `CentroidWeight`
  before implementation. Later generic-loader errors remain possible cascades
  until the next native pass; no unrelated native class was patched.

Synthetic scalar tests execute authored policy bodies; source contracts inspect
wiring. The two Given/When/Then fixture scenarios are explicitly synthetic and
exercise chain admission/deduplication and deterministic room ordering. They do
not emulate the engine. The actual compiler REDs above are a distinct evidence
layer; a new native compiler pass is still required for the repaired snapshot.

## Implemented source and limits

- `HCAlertChain.c`: actual native voice-backed root IDs, inherited expiry (at
  most 30 seconds), two hops, halved strength each hop, root-wide recipient and
  emitter dedupe, maximum 8 roots / 16 queued emissions / 12 recipients including
  seed, 10-second recipient cooldown. At most two tracked candidate evaluations
  per tick, at most two geometry rays each; the module charges three work slots
  each and reserves actor progress. Stale work drops after two seconds, retaining
  native hearing/audio. Rotating emission start avoids permanent tail starvation.
  Radius is a conservative **unmeasured pilot** `15 * strength`, not an acoustic
  claim. Relays wait for real native vocalizations; no extra sound is forced.
- `HCInfectedRooms.c`: explicit diagnostic-only registration for at most four
  measured exact house instances with at most six copied anchors each. Build,
  map, revision, classname, stable IDs, bounds and ambiguity are validated.
  Deterministic order favors the clue room, then distance and ID. Up to two
  catalog anchors extend the frozen-clue route only after native navmesh/path
  checks. No fabricated room offsets or shipped coordinates remain.
- `HCHordeRecovery.c`: complete nonzero four-part native ID/class roster or none;
  immutable cross-generation rosters, duplicate rejection across groups, durable
  conflict latch, exact matches only from entities observed in `AfterStoreLoad`.
  One rotating tracked actor per tick may be reconciled. New adoption is blocked
  while a reservation is unresolved; retirement never refunds reservations.
  Recovered members are accounted for but native pack reactivation remains shut.
- `EnableSupplementaryChains` and `EnableMemberRecovery` default false. Existing
  shared/production settings were not enabled. State identity now uses
  `WorldName`; old incompatible files quarantine rather than silently resetting.

## Remaining gates and missing gameplay

The compile-006 World module load below is actual native compilation evidence.
It does not establish mission initialization or infected gameplay acceptance. Native warnings about missing animation skeletons are not accepted as
harmless without controls. Normal Windows and DayZDiag behavior, two-client voice
rendering/attenuation/replication, native perception/fairness and measured budgets
remain pending. Geometry plus short radius is conservative source policy, not
proof a recipient or human heard a cue. Gunshot acquisition continues through
native hearing; there is no new custom gunshot hook.

The room catalog intentionally ships empty. A measured survey and diagnostic
binding harness must supply actual house instances before semantic room routing
can operate; normal-build catalog registration is hard-gated. Persistent CE
infected storage and durable nonzero IDs are unproven. Missing/zero identities
remain unresolved, and there is no respawn/replacement or location fallback.
Observer-safe abstraction/materialization, restored native pack activation,
complete variant roster, stalker trade-offs, door forcing and additional injury
corrections remain missing/gated. All native movement, contact, sound and restart
acceptance stays open under T018–T022 / AC-007–AC-008.


## Compile-006 inspection and frozen source status

Inspected the completed local `experiments/compile-006/compiler-report.json` and
its script/RPT/error logs, rather than relying only on the progress message:

- Official server under Wine/Xvfb loaded **World: 2,341 files / 6,179 classes** at
  16:02:27.327. No `SCRIPT (E)` was found in those inspected logs. This is real
  compiler progress beyond the infected errors in builds 001–005.
- The completed report is `exited-before-initialization`, launcher exit **255**,
  `runtime_acceptance: pending`, client count **0**. It does not show an accepted
  mission/module initialization. PBO SHA-256:
  `c71579a4d2f498771bcb81cbe7450a34ccc0522618d965432bfb7a39f0f273b4`.
- The report's `signature_verified: false` describes this probe. It does not
  negate the coordinator's separate signature-check experiment.
- The error log includes a missing addon `Anims/cfg/skeletons.anim.xml` warning;
  its cause/control comparison belongs to the coordinator, not an invented
  infected fix. Wine compiler evidence remains distinct from native Windows,
  DayZDiag, two-client behavior and target-load acceptance.

The compile-005 repair finished with **41 focused tests passing in 0.051s**.
This follow-up changes this experiment document only. Gameplay source remains
frozen for coordinator builds; no new roster/controller/transition is implemented
by the proposals below. Task IDs `IC-*` are proposed subtasks of the existing
Banso T018–T022 plan, not completed work or changes to its acceptance checkboxes.

## Complete variant roster audit against specification section 6.2

Current `HCInfectedActor.RefreshProfile` has three overlays: civilian searcher,
military reactive and native injured. They alter remembered-clue lifetime and
investigation admission/anchor budget. Native stance variation supplies four
bounded attention variations. These overlays do not add a seven-archetype
probability distribution or change native senses, health, damage or locomotion.

| Required archetype | Source present | Actual missing capability / feasible next source | Engine dependency before acceptance |
|---|---|---|---|
| Ordinary wanderer | Native CE infected and ordinary native movement remain; civilian attention overlay exists. | Explicit short-attention/distractibility policy and ordinary-profile descriptor; appearance/location assignment data. Current civilian overlay is a searcher, not a distinct ordinary policy. | Native control comparisons for distraction, open doors, pursuit termination and recognizable ordinary behavior. |
| Reactive infected | Military overlay retains clues 12–15 seconds and requests at most one search anchor; native alarm/chase remains. | Separate reactive descriptor, reaction scheduling policy and auditable appearance/location mapping. A shorter memory is not proof of faster hearing or reaction. | Actual cue-to-reaction delay, loudness and reachable-route response; no unsupported native sensory override. |
| Persistent searcher | Civilian overlay retains clues 24–27 seconds; frozen-clue native route and bounded semantic-anchor interfaces exist. | Populate measured room catalog, bind surveyed houses, record actual route progress and expose bounded search/pause policy. | Open-door entry, floor/room reachability, actual waypoint traversal, LOS escape and two-client locomotion sounds. Catalog currently ships empty. |
| Careful stalker | No custom stalker locomotion, listening pauses or quieter-path selection. | Descriptor and pure pause/listen scheduling can be authored. Movement/sound modification remains a separately gated probe; it must produce measurable slower/less explosive trade-offs. | Native speed-control units, release/reset behavior, combat interruption, surface footsteps and two-client audibility. No physically silent movement or vocal suppression. |
| Forceful/heavy | No door-forcing controller, hit animation/audio or heavy locomotion. Closed doors have high path cost only. | Explicit capability-disabled descriptor; bounded door-intent/eligibility state machine is feasible after class/index and lock-policy inputs are defined. It must not call OpenDoor as a substitute for force. | Reliable entry through already-open doors first; authentic door contact/strike animation and audible effort, permitted door materials, locks/base protection, two-client state parity. No supported force transaction has been identified in this audit. |
| Group responder | Native-voice-backed bounded supplementary chains, local recipient dedupe and finite CE cohorts exist, default off. | Route already-owned cohorts toward a fresh member-observed clue, with provenance, expiry and bounded rate limits. Current horde route does not retarget to a heard clue. | Actual native emitter/recipient and human audibility controls, credible delay/attenuation, physical pack response and coexistence with native hearing. No forced extra relay call exists. |
| Injured/crawler | Exact LeftLeg/RightLeg health checks avoid taking injured units into custom investigations; native hit/crawl logic and synchronization remain. | Keep injury as an overlay on stable base personality; diagnostic measurements of the native transition and actual crawl-accessible routes. Additional correction only after a demonstrated defect. | Native leg-hit/crawl/movement/attack-reach results and two-client parity. No additional arm/head injury effect or crawler route controller is implemented. |

Recognizability and distribution remain cross-cutting gaps: no measured class or
zone catalog, configured archetype probability weights, full spawn-stable base
profile assignment, or recognition experiment exists. Native military classes
and native stance are observed inputs, not proof of the desired distribution.
A profile label alone must never be recorded as completed gameplay. Do not invent
class/zone probabilities or claim civilian/military placement was newly authored.

## Additional inspected native interfaces and their limits

All paths below are relative to the private installed 1.30.164289 snapshot cited
above. These are inspected declarations/implementations, not measured behavior.

| Native source / interface | What is supported in source | Boundary relevant to the outstanding work |
|---|---|---|
| `3_Game/AI/AIWorld.c:74–122`, `AIGroup.c` | Create native groups; move agents between groups; sample navmesh and find paths with filters. Empty groups are managed by AIWorld. | `DeleteGroup` explicitly destroys attached agents. Group membership transfer is not a documented CE ownership, save or population-reservation transaction. Never use group deletion for abstraction. |
| `3_Game/AI/AIGroupBehaviour.c` | `BehaviourGroupInfectedPack.SetWaypoints`, traverse direction, loop and current waypoint setters. | `loop=false` is documented as patrol, not one-shot completion. No arrival callback/current-waypoint getter is exposed in this file. Completion must use bounded observed member positions plus expiry/stall release; current deadline release is essential. |
| `3_Game/Entities/DayZCreatureAIInputController.c:3–26` | Movement-speed, heading, alert and behavior-slot overrides are declared. | Declaration alone does not establish units, clamp, reset, conflict with native combat/crawl or replicated footstep behavior. Existing source does not use these overrides; a diagnostic experiment must precede a gameplay controller. |
| `4_World/Entities/Creatures/Infected/ZombieBase.c:54–57,96,811–854,978–1010,1090` | Native mind/speed/crawl synchronization, stance variation and leg-damage crawl transition are implemented. `IsCrawling()` exists. | Preserve super/native hit handling. Health thresholds, route accessibility and client perception still need observation; do not infer a working partial-leg speed curve or arbitrary bone/arm effects. |
| `3_Game/CE/CentralEconomy.c:335–382,442–503` | Group/event/entity spawn helpers are declared. | These inspected helpers are documented DEVELOPER/DIAG ONLY. `SpawnDE` explicitly force-spawns, bypasses limits/avoidance and overrides herd limits. They are not an acceptable production activation or global-cap transaction. |
| `3_Game/CE/CentralEconomy.c:535–599,754–755` | Radius lifetime adjustments; global config reads; nominal/minimum profile parameters. | Radius changes affect surrounding objects, not exclusively owned members. Config/nominal values are not a live occupancy counter or reservation/rollback API. They cannot establish duplication-safe replenishment. |
| `3_Game/CE/CentralEconomy.c:610–640` | `AvoidPlayer(position, distance)` returns false when a player is inside; `CountPlayersWithinRange` exists. | Useful proximity vetoes only. They do not prove nobody can see a distant group through optics or a spectator camera. A true AvoidPlayer result is not visibility acceptance. |
| `3_Game/Global/Game.c:691–709,731–732` | Native object create/delete and remote registration helpers; current-camera getters. | Object creation is not CE-budget admission. Remote unregister is not safe physical simulation LOD. Current-camera getters do not provide every remote client's observer camera to the dedicated server. |
| `3_Game/Entities/EntityAI.c:1381,1419,3374`, `3_Game/Hive/Hive.c` | Storage load hooks and four-int persistent IDs; Hive character save operations. | CE infected persistence/nonzero IDs and event ordering remain unobserved. CharacterSave is for Man, not an infected save API. Persistent-ID lookup has a restricted after-load context; no arbitrary-tick recovery lookup or inferred identity is justified. |
| `3_Game/Noise.c`, native ZombieBase voice handler | Native sound/hearing paths and environment noise-reduction query exist. | Hearing strength, environment reduction units and rendered client sound are separate evidence. Do not subtract an uncalibrated environment value from normalized script strength or inject a synthetic target to obtain movement. |

## Abstract/materialized lifecycle capability audit

`HCInfectedPolicy.CanAbstract()` and `CanMaterialize()` both return false.
Current records are materialized-cohort bookkeeping: actual member centroid,
finite session reservation, historical route and logical interest. Logical states
0–6 are not the complete section 6.4 abstract lifecycle. No entity is spawned,
despawned or repositioned to make those states appear implemented.

| Required capability | Current source and gap | Safe authoring now / dependency |
|---|---|---|
| Logical identity, size budget and purpose | Group ID/epoch, spent reservations, living count, anchor history and route end persist. No explicit validated purpose/destination/transition-intent schema. | Add bounded versioned intent metadata and validate transitions, preserving existing records through explicit migration or quarantine. No invented distant movement. |
| Genuine stimulus motivation | Native member vocalization can update logical interest; supplementary heard/visual clues are not comprehensively consumed by horde routing. | A provenance-aware bounded selector plus in-place pack retarget can use frozen observed clues. Never read the player's current hidden position. |
| Credible migration and roam | Existing CE cohort may receive one navmesh-validated destination 40 metres east. Actual centroid is sampled. | Replace arbitrary pilot offset with bounded authored/surveyed route candidates and progress/timeout handling. A fixed offset is not credible persistent migration or an abstract route simulation. |
| Coarse distant simulation | No valid abstract-only population exists; native entities continue physical simulation. | Diagnostic logical intent/timing can be modeled, but never advance an abstract anchor while still claiming the same physical cohort is there. Lower decision cadence for native cohorts is feasible and does not fulfill abstraction. |
| Observer-safe activation/deactivation | No observer protocol, visibility proof, activation hysteresis/grace or safe transition commits. | Author veto-only policy and diagnostics. Unknown/stale observer data must keep transitions blocked. Two-client and long-range/optics/spectator testing is a prerequisite, not a future assumption. |
| Global population ownership | At most two adopted groups of 3–6 existing entities; module cap bounds its own tracked/reserved set. | Preserve adoption-only operation. Establish an evidence-backed CE ownership/replenishment design before materialization; module counters do not bound all vanilla infected or establish HOR-010. |
| Crash-safe reservation transfer | Reservation/state is dirtied after adoption/optional native transfer, then saved periodically. No durable pre-transfer intent. | Write/read back a spent reservation intent before native ownership changes; retain it on ambiguous failure/restart. This strengthens module accounting but cannot make native CE operations atomic. |
| Exact restart identity | Full nonzero ID/class roster or none; exact loaded-entity matching; durable conflict latch. Restored records remain unresolved even after matches. | Prove storage and registration event order; add bounded reconciliation diagnostics and death evidence. No classname/proximity replacement, same-session ID assumption, silent reservation refund or active-group reactivation. |
| Membership loss, death and loot | Sampled living count can decrease when a tracked entity/reference disappears; null is not proof of death. No abstract inventory/health preservation. | Distinguish observed death from missing/unloaded/foreign-owned member and preserve ambiguous reservations. Prove corpse/inventory/CE cleanup behavior before any removal or recreation. |
| Return, replenishment and overload | Routes expire/release, spent reservations are never refunded; unresolved groups block new adoption. | Add bounded scheduling/defer diagnostics. Finite non-replenishing adoption is a safe limitation, not a finished recurrent horde system. All transition/CE gates remain closed. |

## Exact next implementation tasks for coordinator scheduling

The following source tasks can be taken through actual failing tests, smallest
implementation, focused GREEN and an official compiler pass without pretending
the engine acceptance gates have passed. They are proposals, **not executed** in
this frozen follow-up. Retain default-false flags and existing per-tick caps.
Do not dispatch overlapping infected files concurrently; one source owner can
work while a separate read-only reviewer inspects native experiments.

1. **IC-01 — Explicit seven-profile policy catalog (T020; AI-007).** Own new
   `HCInfectedProfiles.c`, existing State/Policy and focused infected tests. Define
   bounded capability descriptors for all seven archetypes, separate stable base
   personality from injury, and expose unsupported capabilities as unavailable.
   RED: ordinary/reactive/searcher policies are indistinguishable; changing leg
   health overwrites base identity; stalker/heavy can claim unsupported behavior;
   unknown class/zone data silently creates a distribution. GREEN: deterministic
   policy differences, stable base identity, explicit native fallback, rejection
   of invalid weights and no health/damage/speed/audio/door mutation. Native
   CfgVehicles/mission zone audit must supply appearance mapping and weights
   before production selection. Descriptor completeness alone does not pass AI-007.

2. **IC-02 — Retarget an existing owned pack to a genuine clue (T021/T022;
   HOR-002/HOR-005).** Own Module/Navigation and new `HCHordeStimulus.c` if useful.
   RED: an already-grouped recipient hears a valid clue but its route stays on the
   pilot offset; seed self-voice, expired/exhausted, hidden, duplicate or weaker
   stale clues can retarget; native combat is interrupted. GREEN: select only
   provenance-bearing member observations, copy the origin once, check lifetime,
   ownership and reachable route, then update the existing group's SetWaypoints.
   No transfer/new entity is needed. Charge existing route work, at most one
   group retarget per tick and a bounded cooldown/attempt budget; refuse when a
   live native threat takes priority. No root-lifetime extension or recursive
   hearing injection. Native path traversal, sound provenance/attenuation and
   response timing remain engine acceptance gates.

3. **IC-03 — Actual waypoint progress and purpose (T020/T022; AI-005/AI-010,
   HOR-004).** Own Navigation/State plus new `HCHordeRoute.c` if useful. RED:
   `loop=false` is mistaken for stop-on-arrival; reachable route completion is
   never recognized; stalled/memberless routes persist; arbitrary eastward
   offsets masquerade as migration. GREEN: bounded route plans reference
   surveyed/authored candidates; measure actual owned member positions for
   arrival/progress, enforce timeout and release, and record purpose/last reached
   anchor without calling SetPosition. Do not change the anchor to the intended
   destination before members arrive. Native travel/door/collision and waypoint
   patrol behavior must be tested against controls. Empty route catalogs defer
   routing; they do not invent safe paths.

4. **IC-04 — Durable adoption intent before native transfer (T022;
   HOR-008/HOR-009).** Own Module/State/Recovery. RED: crash/save failure between
   transfer and periodic save loses the spent reservation; ambiguous native
   transfer releases a reservation or retries as a fresh cohort. GREEN: persist
   a validated bounded intent with epoch/member evidence before Start, then
   commit observed result; failed save performs no transfer; any uncertain
   outcome remains reserved/unresolved after restart. Keep existing generation
   monotonicity, roster immutability and 64 KiB bound. Version the schema or
   quarantine explicitly. File write/readback proves neither OS power-loss
   durability nor CE atomicity; native crash/restart controls remain required.

5. **IC-05 — Separate member death from missing identity (T022; AI-009,
   HOR-009/HOR-010).** Own Native/Recovery/State. First inspect the exact native
   killed/deletion/store hook signatures before adding a hook. RED: missing/null
   entity is counted as confirmed death; duplicate IDs are cleared; a restored
   member gets readopted; missing initialization events silently imply absence.
   GREEN: bounded observation records distinguish confirmed death, missing,
   foreign ownership and conflicting identities; ambiguity keeps the reservation
   spent and reactivation blocked. Log bounded initialization/load ordering to
   diagnose entities created before module Instance; a bounded startup handoff
   may follow that evidence, never a global rescan. Do not add spawning or
   release the recovery latch. Actual CE cleanup, native ID stability, storage
   survival, corpse loot and restart ordering must be measured before recovery
   can restore a native pack.

6. **IC-06 — Measured room catalog binding harness (T020; AI-001/AI-005).**
   Own Rooms/Navigation and `infected-*` fixtures; coordinate with interior owner
   through the existing contract, without editing their files. RED: mismatched
   world/build/house/revision, ambiguous clue room, duplicate anchor IDs or
   unreachable floor are accepted. GREEN: diagnostic-only registration loads
   explicit measured records, binds exact live house instances and validates
   each route segment before use. Synthetic ordering fixtures remain labeled
   synthetic. A real house survey, open-door approach matrix, stair/blocked-door
   checks and normal PBO parity are indispensable; empty production catalog and
   default-off behavior remain until those gates pass.

7. **IC-07 — Veto-only observer/transition policy (T022; HOR-006/HOR-007).** Own
   new `HCHordeTransitionPolicy.c` and focused tests; coordinate future observer
   inputs with core rather than invent a shared API. RED: absent/stale observer
   snapshot, observer-count overflow, positive visibility, recent proximity,
   combat, unresolved membership, missing CE authority or missing durable intent
   permits a transition. GREEN: every uncertainty vetoes; hysteresis/grace uses
   explicit input evidence and bounded timestamps. This task must not call
   CreateObject, ObjectDelete, RemoteObjectDelete, DeleteGroup or toggle
   CanAbstract/CanMaterialize. AvoidPlayer is one necessary radius veto only.
   Any later executable transition still needs an authoritative population
   protocol and measured multi-observer visibility coverage.

8. **IC-08 — Stalker/heavy/injury diagnostic probes (T019/T020; AI-001–003,
   AI-007/AI-008/AI-012 and audio matrix).** Own Native plus new
   `HCInfected*` diagnostic helpers/tests. RED: a probe can run in production,
   omit super, leave native override active after interruption, manufacture
   unheard noise or operate on unknown/protected doors. GREEN: diagnostic-only,
   explicit opt-in, bounded capture with native control and no default gameplay
   mutation. Capture native crawl state/movement first. A speed-override probe
   or door strike probe is a separate later change, after exact command/animation
   and cleanup API inspection. Source inspection has not established a safe
   forceful-door implementation. Observations must justify the correction;
   a mock cannot establish locomotion or audio acceptance.

9. **IC-09 — CE ownership/materialization feasibility experiment (T022;
   HOR-008–010).** No gameplay transition implementation yet. Specify and collect
   before/after native group ownership, live CE counts/replenishment, stable IDs,
   stored member/corpse/inventory state and crash/restart outcome in an isolated
   diagnostic mission. Developer force-spawn helpers may generate a controlled
   experiment only, never satisfy production limits. Determine whether an
   actual native event-owned population design can supply reservation/cleanup
   guarantees. If it cannot, record an explicit architecture/spec decision;
   continuing adoption-only cohorts is not equivalent to fulfilling the abstract
   lifecycle. Only after this evidence and IC-07 observer acceptance may an
   executable, rollback-aware transition be designed and reviewed.

For each executable source task: first save the actual behavioral RED output in
`tests/fixtures/runtime/infected-*`, implement the minimum change, run
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p 'test_infected*.py' -v`,
then hand a frozen coherent snapshot to the coordinator's real compiler harness.
Use source-policy execution/native diagnostic assertions where possible rather
than a test that simply mirrors a newly written Python model. Add explicit
Given/When/Then cases for stale clues, group combat interruption, crash boundaries,
missing members and observer uncertainty. Compilation/init, offline policy tests,
DayZDiag observations, normal Windows PBO tests, two-client perception and
measured 3–6-player performance remain separate results. No acceptance status or
performance budget is upgraded by this plan.


## Executed bounded integration wave: IC-01 + IC-02 + IC-05 accounting subset

This section supersedes the relevant source-gap entries above. The user narrowed
this integration wave to these tasks; IC-03/04/06/07/08/09 are still tracked,
not silently completed. Gameplay source is now frozen for a new coordinator
compiler/PBO snapshot. No source change after this freeze is authorized by this
report; a concrete compiler finding may require a separate repair.

### Implemented behavior

- **IC-01:** New `HCInfectedProfiles.c` provides seven descriptors and explicit
  unavailable-capability fallback. Ordinary/reactive/searcher/group-responder
  policies now differ in bounded clue lifetime and room-anchor budget. Stalker
  and heavy requests resolve to ordinary behavior, preserving their requested
  ID for diagnosis; neither falsely obtains quiet locomotion or forced doors.
  Injured/crawler is a native injury overlay. Base personality is assigned once
  at registration and is not overwritten by leg injury.
- `EnableVariantPolicies` defaults false. Civilian/military stance-indexed maps
  default **empty**, require exactly four valid explicit entries when enabled,
  and reject invalid/null maps. No class/zone weights or automatic archetype
  distribution is invented. Existing appearance (`IsZombieMilitary`) and native
  stance (0–3) are the only assignment inputs. New lifetimes/anchor limits are
  experimental policy bounds, not measured behavior or calibrated probabilities.
- **IC-02:** New `HCHordeStimulus.c` selects live provenanced visual memory or
  externally received native-voice-backed clues, freezes origin and original
  expiry, excludes self-vocalization and compares candidate age/strength with
  visual-provenance priority. Selection does not read a target entity.
- Already-owned native cohorts can retarget through `HCNativeInfectedPack.Retarget`
  using the inspected SetWaypoints API. Every surviving member must still belong
  to that pack; native chase/fight or leg injury refuses the retarget. There is
  no new group/member transfer. One bounded path to the frozen origin must pass
  before the waypoint update. Every path attempt spends a cooldown/attempt;
  repeated evidence cannot trigger unbounded pathfinding. Pack expiry is capped
  by the original clue expiry, never extended by processing time.
- `EnableHordeStimulusRoutes` defaults false and requires native pack routes,
  enabled hordes and a work cap of at least 16. At most one group retarget is
  scheduled per tick, at most two attempts per pack, 10 seconds between attempts,
  with eight work slots reserved for at most six members and a bounded path.
  These are source limits, not a native performance benchmark.
- **IC-05 accounting subset:** Sweeps distinguish live members, explicitly
  observed dead members, missing entities and ownership/position ambiguity.
  An incomplete/ambiguous cohort enters unresolved state 6 with a durable
  RecoveryConflicted latch, preserving its last known living count and all spent
  reservations. Its optional pack is released safely through existing ownership
  retry handling. Missing/null is not treated as confirmed death.
- Assigned dead/missing actor slots remain protected until terminal retirement,
  so incoming CE registrations cannot erase the accounting evidence. A confirmed
  death remains a bounded actor tombstone even after its entity reference goes
  null; unexpected revival is ambiguity. Terminal records retain the last
  observed living count rather than silently overwriting it with an empty sweep.
  There is no new killed/deletion hook and no claim of native storage durability.
- `CanAbstract` and `CanMaterialize` remain hard false. All production flags remain
  false. No spawning, despawning, remote unregister, teleport, population refund,
  hidden live target tracking, speed override, synthetic sound or door forcing
  was introduced. Persistent adoption intent/CE atomicity remains IC-04/IC-09.

### Actual RED/GREEN and source evidence

- Added `tests/unit/test_infected_wave.py` before implementation. The first actual
  run was **2 failures / 8 errors**, recorded in
  `tests/fixtures/runtime/infected-wave-red.txt` (missing policies, selectors,
  retargeting and ambiguity accounting).
- Implemented source then ran all infected tests: **51 passed**. A final review
  added two actually failing regressions for an accidentally reused `owned`
  parameter keyword and terminal-count preservation. Their actual RED is
  `tests/fixtures/runtime/infected-wave-edge-red.txt` (**2 failures**).
- Renamed the parameter to `ownsCohort` and preserved terminal counts. Final
  command:
  `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p 'test_infected*.py' -v`.
  **53 tests passed in 0.062s**, recorded in
  `tests/fixtures/runtime/infected-wave-green.txt`. This executes authored scalar
  policy bodies plus source wiring contracts; it does not execute native AI.
- A fresh intersection against all **7,455** installed native class/enum/typedef
  names found no infected declaration collisions. Formula complexity and known
  reserved identifier regressions pass. Scoped `git diff --check` passes.
- `tests/fixtures/runtime/infected-wave-source-freeze.json` records SHA-256 values
  of the frozen infected source and focused tests. A subsequent compiler/PBO
  result must bind the newly built PBO, not the older successful build008 hash.

### Actual compiler boundary and still-open work

Inspected compile-008's completed `compiler-report.json`: actual server under
Wine status **initialized**, client count 0, runtime acceptance pending, PBO
`c71579a4d2f498771bcb81cbe7450a34ccc0522618d965432bfb7a39f0f273b4`.
The coordinator additionally reports Mission/core VM selftest INIT passed.
**This preceded the current wave** and does not compile or exercise the new
profile/selector/retargeting snapshot. Coordinator owns the next default and
crafting-only compiler/init probes; their results will be reviewed separately.

Remaining: actual stalker/heavy locomotion/doors and recognizable appearance/zone
selection; IC-03 migration/arrival; IC-04 durable pre-transfer adoption intent;
IC-05 native storage/order/death/cleanup proof and safe pack reactivation;
IC-06 real surveyed room data/binding; IC-07 measured observer/transition protocol;
IC-08 diagnostic native movement/audio/door probes; IC-09 CE population authority
and duplication-safe materialization. Native Windows/DayZDiag, two-client hearing,
physical route fairness, restart and target-load measurement acceptance remain
open even after the new source passes compilation. This is source completion of
the agreed feasible subset, not acceptance of the complete infected overhaul.


## Frozen wave actual compiler result — build009

Reviewed the completed actual server-under-Wine report and script/RPT logs for
`experiments/compile-009`. **Status: initialized.** World loaded 2,348 files /
6,298 classes; Mission loaded 220 files / 470 classes. Core settings selftest
printed PASS in the native script VM, followed by the server initialized marker.
No SCRIPT(E) was found in the inspected logs. The probe was stopped by its
harness after initialization; zero clients and runtime acceptance still pending.

PBO SHA-256:
`8339c144c658862e293bd5eadba65cc6d81b1ea0f61959334230799ff4f87159`.
Parsed the actual probe PBO with the existing bounded stored-PBO parser and
compared **all 11 infected source entries** against the frozen manifest: every
entry matched, with none missing or changed. The current workspace infected
files also still match. This binds the actual compiler/init result to this
wave, independently of earlier builds. Exact report, its SHA-256, matched entry
list and observed script markers are recorded in
`tests/fixtures/runtime/infected-wave-compiler-009.json`.

Coordinator reports the integrated Banso checks GREEN (371 tests / 16 BDD cases).
The independently run infected suite remains **53 GREEN**, with actual initial
and edge RED evidence above. No gameplay source edits followed the freeze.
Default-off compilation/init does not execute the optional infected controllers
or prove profiles, cues, native route behavior, persistence, audibility or
performance. A subsequent crafting-enabled build after the separate crafting
fix belongs to the coordinator; its PBO must be identified separately and it
must not be attributed to build009. No commits were made by this worker.


## Executed source wave IC-04, IC-03 and CR-06 — frozen for build014

User explicitly requested the next feasible source work after the build009 freeze,
then added independent finding CR-06. This section supersedes the corresponding
source gaps in the earlier plan. It does not upgrade native acceptance. Only
infected source/tests/this report were edited; no commits, production flags,
coordinate surveys, observer transitions or probe hooks were added. The later
room-loader assignment to Hubble owns `HCInfectedRooms.c`; this worker leaves
that file unchanged and reviews build014 independently of its next integration.

### IC-04: prepared reservation and outcome journal implemented

- `HCInfectedModule.TryAdopt` first constructs a finite reservation, exact native
  identity roster when available, group ID/epoch context, observed anchor and UTC
  timestamps. `AdoptionStage=1` / unresolved state 6 is saved and read back through
  `SaveAdoptionBoundary("prepare")` **before** optional native pack Start. Failure
  quarantines the module and performs no new transfer.
- Only after successful preparation are candidate actors marked assigned. Native
  transfer result is classified as committed (stage 2/state 0) or aborted (stage
  3/state 6/conflicted). A pending native release is ambiguity, not success.
  `SaveAdoptionBoundary("outcome")` saves/readbacks that result immediately.
  A failed result write quarantines and preserves the prepared reservation;
  native failure/ambiguity is saved as aborted and quarantines. There is no refund,
  replenishment, replacement entity or retry of the same incomplete intent.
- Snapshot **schema 2** explicitly rejects schema 1 data without overwriting or
  resetting it. Config schema remains 1. Existing two alternating snapshot slots,
  the 64 KiB bound, strict present-slot validation and monotonic reservation/
  generation checks remain. A corrupt present slot quarantines rather than
  rolling back to the other slot.
- Cross-generation validation permits exactly the new prepared-to-committed
  transition with identical ID/count/living/creation identity. Stage rollback,
  replay, count growth and aborted reactivation are rejected. Interrupted stage 1
  becomes stage 3/conflicted after load. Every nonterminal loaded group remains
  unresolved; the loader never repeats a native membership transfer.
- Inspected native `1_Core/proto/EnSystem.c:397–481`: OpenFile, FPrint and CloseFile
  exist, with readback through the existing bounded reader. These declarations
  offer no explicit fsync/atomic CE transaction guarantee. The implementation
  establishes write-before-transfer ordering and conservative process-restart
  semantics in source. OS power-loss durability, actual native group transfer,
  crash/restart and CE ownership correctness remain **unaccepted** until observed.

### IC-03: actual route progress and purpose implemented, migration still open

- Removed the generated 40-metre-east destination and automatic return waypoint.
  When native routing is requested but no live genuine clue exists, adoption
  defers and native CE groups continue unchanged. Candidates already in native
  chase/fight are excluded before preparation. Following preparation, cue expiry
  is rechecked against UTC before optional Start; stale work cannot extend it.
- All routes originate in a frozen sensed clue; only registered surveyed room
  anchors may extend an investigation. No map route, distant simulation or
  migration coordinate was invented. The shipped room catalog remains empty.
- Native `BehaviourGroupInfectedPack.SetWaypoints` receives **one point at a
  time**, because the installed declaration documents `loop=false` as patrol.
  A bounded route plan holds at most three validated points. Native group agents
  perform all physical movement.
- Every pack tick samples at most six members. Advancing a waypoint requires
  all surviving owned members to be within its existing waypoint radius, using
  actual 3D positions; a centroid alone cannot satisfy arrival. Missing/foreign
  ownership or invalid positions fail closed. Only a decrease in worst-member
  squared destination distance counts as progress; unrelated wandering does not
  refresh the stall timer. Radius/progress thresholds remain experimental bounds.
- Explicit outcomes distinguish active, completed, stalled, expired, interrupted
  and ambiguous. Combat or leg injury yields to native control. Expiry/stall/
  completion releases through existing bounded ownership handling, never deletes
  the group/agents. Route purpose, intended final point, planned/completed counts
  and outcome are copied into bounded group persistence. Last actual centroid
  remains separate from intended route destination.
- Destination/plan changes mark the journal dirty even when outcome/purpose stay
  the same. Restart interrupts historical active routes; it does not replay them.
  This completes the feasible observed-route progress/purpose source subset.
  Authored/surveyed long migration routes, distant abstract movement, physical
  route acceptance and resumable native pack recovery remain open.

### CR-06: fair cohort scheduling and charged work implemented

- `RetargetCohorts` rotates its starting cohort. `Retarget` now returns an explicit
  outcome: 0 for rejection before native path work, 1 for a spent path attempt
  that fails, 2 for an accepted path. A shared route slot is consumed only for
  outcomes 1/2. Failed geometry remains charged; cooldown and attempt limits
  remain spent. No rejected first-cohort clue can repeatedly consume the only
  path slot and starve the second cohort.
- At most two cohort eligibility checks and one charged native path are allowed
  per sweep/tick. Six members per cohort and the existing bounded native path
  remain the maxima. Sixteen work slots are reserved, and opt-in horde stimulus
  routing requires a core work cap of at least 24. These are source bounds, not
  target hardware measurements.
- The regression translates and executes the **authored scheduler method**, with
  explicitly synthetic pack callbacks delegating eligibility to the actual
  scalar policy bodies. The independent review's first-consumed/second-short-TTL
  scenario now produces callback counts **[8,8]**, charged path attempts **[0,1]**
  for times 12–19: the second cohort gets its attempt before expiry. Repeating with
  failed geometry still spends exactly one path attempt. These are synthetic
  scheduler counters, not actual native engine path/audibility observations.
  Results: `tests/fixtures/runtime/infected-cr06-scheduler.json`.

### Actual tests and coherent freeze

1. IC-04 tests were written first: actual RED **2 failures / 6 errors** in
   `tests/fixtures/runtime/infected-persistence-red.txt`. Implemented the policies,
   stage validation, schema and ordering; focused infected suite became **61
   GREEN**, recorded in `infected-persistence-green.txt`.
2. IC-03/CR-06 actual RED **1 failure / 6 errors** is recorded in
   `infected-route-red.txt`. Implemented observed progression, metadata and fair
   scheduling; focused suite became **68 GREEN**, recorded in
   `infected-route-green-attempt.txt`.
3. Final review added an actually failing regression for route destination/plan
   changes failing to mark persistence dirty: **1 failure**, recorded in
   `infected-route-journal-red.txt`. Fixed that source edge and ran:
   `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p 'test_infected*.py' -v`.
   **69 tests passed in 0.156s**, recorded in `infected-ic0304-green.txt`.
4. Scalar tests execute authored policy bodies; scheduler tests execute the
   restricted authored scheduler with synthetic collaborators; other checks
   inspect wiring. They do not prove native file durability, engine movement,
   crash atomicity or client behavior. Source-name intersection against all
   **7,455** installed class/enum/typedef names found zero collisions. Known
   keyword/formula regressions and scoped `git diff --check` pass.
5. Source is frozen. Exact source/test hashes are in
   `tests/fixtures/runtime/infected-ic0304-source-freeze.json`; canonical entries
   SHA-256 is `1b698f4c2610661999181d6d4633840cc4450ceda1a5ce83ca68c7c59a1156a6`.
   Older freeze/build009 evidence is retained unchanged and is not reused for the
   new snapshot. Build014's PBO already matches all 11 frozen infected entries;
   its World compilation is observed. Mission/init/hold and native journal results
   require the completed report and actual files before a stronger claim.

### Native periodic-save observation is still pending

Inspected the completed coordinator probe013 report: old PBO
`1ba4caa424f5ebf84362196aee6a73d242c8b2d3e4e30d9a0a919207b9dae502`,
status initialized, zero clients, hold requested 90 seconds / observed 90.769.
The script log shows infected module admission and the profile contains its config,
but no horde snapshot was observed. This does **not** prove periodic saving.

Installed `3_Game/DayZGame.c:3000–3028` updates the SYSTEM queue outside the
`doSim && mission` guard. `HCServer` schedules its callback on that SYSTEM queue.
No script-visible zero-client suppression was found in this inspected path;
engine callback delivery/timeslice/host lifecycle behavior remains unresolved.
Do not diagnose no-clients suspension as proven or add invasive test hooks.
The coordinator's seed/hold probe is unchanged. A native schema-2 seed-load result,
if obtained, will establish only the loader path actually exercised; periodic
writes require observed file/generation changes. Prepared native transfers and
real crash recovery still require a controlled native experiment with actual
members and CE accounting evidence.

IC-03/IC-04 source work above is implemented; their native acceptance is pending.
IC-06 belongs to Hubble's separate room-loader wave. IC-07 transitions remain
unimplemented/blocked by observer evidence, and IC-09 CE population authority,
abstraction/materialization, complete physical variants, room surveys, two-client
perception and target-load performance remain open. CanAbstract/CanMaterialize
are hard false; all production enablement remains false. No unsupported despawn,
teleport, native speed/audio override or test-only gameplay bypass was added.


## Final build014 review: frozen source compiles and admits, journal unobserved

Reviewed the completed `compile-014-infected/compiler-report.json` and script log.
Actual official server under Wine initialized, World/Mission loaded, core native
VM selftest passed, and the infected module was admitted. The harness held
**90.792 seconds** after init with zero clients, then stopped it. No SCRIPT(E)
was found. PBO SHA-256:
`e0868ee3a53639795e21e33c0f03412c3b1d8b30c4157caf9abc3fa5021642ce`.
All **11** infected PBO entries match the IC-03/IC-04/CR-06 frozen manifest.
Report/hash, matched entries and observed HC profile file list are recorded in
`tests/fixtures/runtime/infected-ic0304-compiler-014.json`.

Observed HC files are settings and Infected/config.json only; no empty horde
journal appeared. Therefore neither periodic saving nor native schema-2 journal
round-trip is accepted. No native member transfer/crash recovery, path traversal,
client audio or performance acceptance is inferred from this run. The focused
source suite remains **69 GREEN**. Coordinator separately reports the integrated
gate at 409 PASS; that is not an independent run by this worker.

IC-03/IC-04/CR-06 source is coherent and frozen. No gameplay edits followed the
freeze and no further features were started. Hubble owns HCInfectedRooms.c and
Curie owns HCObserverTransitionGate.c in their separate waves; this worker edits
neither. Subsequent integration/PBO evidence must identify those additions
separately. No commits; unsafe transitions and production enablement remain off.


## Native016 extended hold: journal remains unobserved

Independently reviewed the completed coordinator `compile-016-journal-long`
report, script log, Wine output and RPT tail. This run used the same build014 PBO
`e0868ee3a53639795e21e33c0f03412c3b1d8b30c4157caf9abc3fa5021642ce`.
Core VM selftest, infected admission and initialization were observed; no
SCRIPT(E) was observed. The requested 210-second post-init hold measured
**210.363 seconds**, then the harness forced termination. Only
`HollowCountry/settings.json` and `HollowCountry/Infected/config.json` were
present: **no journal was observed**. Exact report/hash and file observations
are preserved in `tests/fixtures/runtime/infected-ic0304-compiler-016.json`.

The script log ends at module admission/initialization and supplies no actual
tick witness. The RPT continues with asset/geometry warnings and native radio
entity type errors; the Wine output includes a device-volume access warning and
X disconnection at shutdown. These observations do not identify the callback or
journal root cause. No causal conclusion about CE initialization or zero-client
suppression is justified. Installed SYSTEM-queue inspection above still does
not establish delivery in this run.

This is an extended **negative/unobserved persistence observation**, not proof of
periodic saving, successful native journal round-trip or a diagnosed save defect.
Runtime persistence acceptance remains pending. No gameplay source, probe hooks,
feature flags or worker-owned files were changed; the source freeze remains.
