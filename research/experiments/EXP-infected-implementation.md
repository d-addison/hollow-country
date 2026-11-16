# Infected implementation — source evidence and remaining gameplay

Date: 2026-11-16. Build inspected: 1.30.164289. Status: experimental Enforce
source authored; native compilation, DayZDiag, normal PBO/server and client
acceptance have **not** occurred. AC-007 and AC-008 remain unaccepted.

This report owns the T018–T022 implementation delta under the user's instruction
to implement before client join. The canonical spec, plan and task ledger are
inputs; no other worker's files or acceptance status were changed. The full
handoff and `docs/RUNTIME_IMPLEMENTATION_CONTRACT.md` were read. The installed
native source/config stays outside Git. Synthetic tests are not runtime evidence.

## Concrete source delivered

All files are in `mods/HollowCountry/scripts/4_World/Infected/`:

| File | Implemented source behavior |
|---|---|
| `HCInfectedModule.c` | Shared HCModule registration, server-only startup, validated private DTO, bounded tracking/queue/sampling, CE cohort reservation, finite group state transitions and snapshot scheduling |
| `HCInfectedNative.c` | Native init/voice hooks preserving super; access to native spawn stance; optional experimental attack invocation filter |
| `HCInfectedPolicy.c` | Executable scalar rules for clue provenance/expiry, overload/dedupe/cooldown, population reservation, finite lifecycle, restart, snapshot progression, observations and search interruption |
| `HCInfectedState.c` | Config, clue/profile/group DTOs, UTC time, bounded JSON input, alternating snapshot generations with readback and fail-closed validation |
| `HCInfectedNavigation.c` | Native pack creation/membership/waypoints, bounded navmesh path checks, last-seen anchor investigation and native-default-group release |
| `HCInfectedSelfTests.c` | Optional DIAG_DEVELOPER policy/default checks; written, **not executed** |

Native AI retains navigation, collision, commands, attacks, ordinary pursuit,
injury/crawling, footstep/voice rendering and hearing. No script position changes,
entity spawning/deletion, health/damage multipliers, opening doors, silent movement,
fake noise targets, manual heading/speed steering, custom RPC or inventory state.

## Exact installed surfaces inspected

Paths below are relative to the private snapshot
`/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`.
Presence/signature is source evidence, not proof of behavior in this scenario.

| Surface | Inspection and consequence |
|---|---|
| `3_Game/Entities/DayZCreatureAIInputController.c:3,9` | `OverrideMovementSpeed(bool,float)` and `OverrideHeading(bool,float)` exist. They override input, not a destination/path request. No getter for underlying unoverridden movement input is exposed. A persistent speed override could mask native stopping/crawl transitions; these are deliberately not used. |
| `3_Game/Entities/DayZInfected.c:47` | `DayZInfectedCommandMove` exposes stance/idle/turn state; no destination setter. Script command translation hooks are physical overrides, not a navigation fix, and are not used. |
| `3_Game/Entities/DayZInfectedInputController.c:9–10` | `GetMindState` and `GetTargetEntity` exist. A target can be retained after LOS loss. It is used only as a visual-sensor candidate, with current native chase/fight state, <=20m, forward cone, and view **and** fire geometry hits on that candidate. The destination cache changes only after both checks pass. No hidden candidate coordinate is copied into a route. |
| `3_Game/AIBehaviour.c:60` | `OnNoise` is commented out, not an available hearing callback. No verified general target-visible or heard-by-infected delivery callback was found in these interfaces. |
| `3_Game/Global/DayZPhysics.c:199` | `RaycastRV` exposes geometry and result objects. The sensor requires an actual first hit on the native candidate for both geometry tests; empty results fail closed. Lighting/perception parity still needs a native trial. |
| `3_Game/Entities/DayZAnimal.c:191–208` | `DayZCreatureAI.GetAIAgent`, `InitAIAgent`, and `DestroyAIAgent` exist. Only `GetAIAgent` is needed; existing CE agents are retained. |
| `3_Game/AI/AIAgent.c:6–7` | `GetGroup` and `SetKeepInIdle` exist. The latter is not used to suppress native AI. |
| `3_Game/AI/AIWorld.c:77–122` | `CreateGroup`, `CreateDefaultGroup`, `SampleNavmeshPosition`, `FindPath`, and `RaycastNavMesh` exist. `DeleteGroup` destroys attached agents, so it is never used. |
| `3_Game/AI/AIGroup.c:6–14` | `RemoveAgent`, `AddAgent`, `GetBehaviour`; the source explicitly requires removing old membership and warns empty groups disappear next frame. Transfer occurs in one script call. Release creates a default native group; it cannot promise restoration of an original empty CE group. |
| `3_Game/AI/AIGroupBehaviour.c:7–32` | `BehaviourGroupInfectedPackWaypointParams` and `BehaviourGroupInfectedPack.SetWaypoints` are real. `loop=false` means native patrol, not one traversal; script expiry/stall handling limits our pack lifecycle. This discovery supersedes the initial overly broad assumption that infected routing was unavailable. |
| `4_World/Entities/Creatures/Infected/ZombieBase.c:583–608` | `ProcessSoundVoiceEvent` plays native client voice and adds native server noise when `m_NoiseParams` exists. Our override calls super exactly once, then records a bounded source event. No second AddNoise or invented sound. |
| `ZombieBase.c:612–680,698,746` | FightLogic's attack branch checks `WasHit` then invokes native damage helpers. Selection uses `CanAttackToPosition`; delivery has a distance test. See the contact-guard limitation below. |
| `ZombieBase.c:811–849,981–1010` and `3_Game/Entities/DayZInfected.c` | Real `LeftLeg`/`RightLeg` health, crawl transition and synced crawling are already present. They remain unchanged; no speculative extra injury effect is implemented. |
| `3_Game/Noise.c` | AddNoise/AddNoisePos/AddNoiseTarget are hearing signals, not proof of player-audible sound. AddNoiseTarget explicitly creates an AI-visible position for a lifetime; we do not use it as a movement command. |
| `3_Game/tools/JsonFileLoader.c` and `1_Core/proto/EnSystem.c` | JSON string serialization, ReadFile/OpenFile/FPrint/CloseFile/MakeDirectory exist. Bounded custom reads replace the stock 100MB loader limit. No atomic rename/fsync contract was found; crash durability is not claimed. |

Source SHA-256 pins:

```
3_Game/AI/AIWorld.c                  6ffd6f8b6e1d80d9f612ef59958bd0e5960432176fa6c1cd27458239b3b124a3
3_Game/AI/AIGroup.c                  10a6977e87af518e2576ab7f9199da40013aec1d50b46f7b6b954c9aa013686f
3_Game/AI/AIGroupBehaviour.c         a4ad32738a782bd30f93c38f765957f90b9e1153596f41c4e6ca08dfb78738e1
3_Game/AI/AIAgent.c                 a361355bf706783ce0c40399001fe758380ca8e471ee3cc442d4179f6d24a2e1
DayZInfectedInputController.c        152ccfb5f48bddad8df6780354b6419813ffc991b693fe54e6a102369236fbf4
ZombieBase.c                        c67ec8fdaa8db1fddab20fb8ed0bdeffa0e8785566ee869f465e97803223660c
```

The installed server `addons/dz.pbo` was inspected in memory using bounded stored
PBO entry headers; no extracted config was written into the repository.
`aiconfigs/config.bin` contains `GroupBehaviourTemplates/DZInfectedPackBeh`, with
`type=InfectedPack`. The source checks this template in the runtime database and
casts its actual native behavior before transferring any agents. The installed
template includes native alert distribution and prediction parameters: that is
not proof of fairness/audio acceptance, and no values are overridden here.

```
addons/dz.pbo SHA-256                96397454ae3723c5007d0e429572c481e259ac833b957ee18944ff1e611d31aa
aiconfigs/config.bin SHA-256         898aa4e52a7542374e01b235b3fe94c179701960dc9fefad393bfcf9bf8785be
```

CE feasibility was inspected in the installed Chernarus `db/events.xml`,
`db/globals.xml`, `cfgeventspawns.xml`, and `env/zombie_territories.xml`.
Existing infected events use native player-relative spawning and location pools;
territories already have variable density ranges; `ZombieMaxCount` is 1000 in this
installed baseline, not a recommended target. These controls can tune native
population/location tendencies but do not establish persistent moving group IDs.
`3_Game/CE/CentralEconomy.c:350–383` explicitly describes SpawnDE/SpawnDEEx as
DIAG-only forced spawns bypassing limits/avoidance (and overriding herd limits).
They are not safe production materialization APIs and are not used. Mission CE
files are outside this worker's write scope and were not changed.

## Actual gameplay coverage versus gaps

| Requirement/tasks | Source implemented | Still unimplemented gameplay |
|---|---|---|
| AI-01, PHY-01; T018–T019 | Native navigation/combat retained; path-failure/stall fallback; optional delivery-invocation filter | Proven competence correction, door-approach improvement and a verified queued wall-hit fix |
| AI-03/04; T020 | Native candidate + physical visibility checks; frozen last-seen memory; native pack visits <=3 reachable nearby anchors; expiry, two attempts, reacquisition/injury interrupt | Semantic room inventory, room ordering and building-class door/room anchor catalog. Nearby navmesh anchors are **not** evidence of methodical room search. |
| AI-05/06/07; FR-013; T020 | No health/damage/population inflation; existing CE class/location cues retained. Civilian search overlays retain 24–27s and request up to three anchors; military overlays retain 12–15s and request one. Native stance supplies bounded individual variation. | New class/location probability distribution, new visual cues, custom stalker locomotion, heavy-door behavior and demonstrated player recognition. Two search overlays are not a complete custom variant roster. |
| AI-08; T019–T020 | Native door collision/path decisions retained; closed doors get high path cost | Contact/animation/audio-authorized unlocked opening or forcing, class/index policy and lock compatibility |
| AI-09/10, AUD-01; T019–T020 | Native audible locomotion, actual damage and native leg/crawl handling retained; search does not commandeer injured units | Slow careful-stalker behavior, extra arm/head injury consequences; two-client surface/occlusion parity |
| AI-02 local chains; T021 | Existing native hearing and native pack response preserved. Native voice event instrumentation is bounded/deduped/cooled down and records actual emitter origin only. | Supplementary audible rebroadcast and reliable heard-by recipient/hop attribution. Our metadata hop limit does **not** bound vanilla's internal alert graph. No fabricated root/hop history or remote exact-coordinate injection. |
| AI-02 hordes; T022 | Finite existing CE cohorts can be transferred to native infected packs and receive actual native movement waypoints. Group ID/epoch, reserved/living counts, anchor history, route end, state and UTC lifetime persist. | Exact native member recovery across restart, abstract movement/materialization, verified CE occupancy reconciliation, observer-safe activation/deactivation and resumable persistent migration. This is **not yet the complete persistent horde feature**. |

Already-materialized CE adoption changes no entity positions/counts. Thus it avoids
introducing spawn pop-in, but it does **not** implement dormant-to-materialized
activation or prove native CE's observer behavior. A pack walks/patrols only if the
native engine accepts its template and validated route. No guarantee of actual
movement, open-door reliability or native LOD behavior is made without a run.

After restart, active records become `UNRESOLVED`. They keep their reservations,
cannot recruit replacements, and expire at their original lifetime. No classname,
proximity or runtime pointer is treated as persistent identity. Retired records are
kept; there is no automatic replenishment or fresh epoch. This is a conservative
fallback, **not** implemented persistent member survival/rebinding.

## Bounds, lifecycle and failure behavior

- Shared flags `EnableInfected`, `EnableHordes`, `EnableAlertChains` remain default
  false. Local `EnableCEAdoption`, `EnableNativePackRoutes`, `EnableInvestigation`,
  `EnableContactGuard`, `RunPolicySelfTests` also default false.
- At most 24 tracked entities, 2 horde records, 3–6 existing members per cohort;
  reservations never exceed the smaller of core's member cap and 24. With two
  six-member cohorts this implementation can reserve at most 12 horde members.
  Existing global native CE counts are not measurable from these script records.
- Registry admission, actor/voice jobs and group maintenance have finite bounds.
  Core work is clamped to 32 logical items, with pack/transition maintenance
  reserved before a resumable actor sweep. Each lookup inspects <=24 entries.
  Hordes/native route/investigation require a core budget >=8. At most one investigation
  route and one visual candidate (two geometry tests) are attempted per tick.
- <=2 individual investigation packs; <=3 anchors, <=2 attempts per clue,
  >=10s retry delay, <=15s route lifetime/stall allowance, <=20m visual samples.
  Native combat reacquisition or injury interrupts an investigation on the next
  core tick. Tick scheduling resolution is an explicit timing limit.
- Native route segments <=120m (investigation <=24m); 1.5m nav sample radius,
  <=1.5m vertical sample difference, <=32 returned path points, bounded path-length
  ratio. Conservative walking/interior filter rejects special movement classes.
  Native path-query internal cost has no exposed time budget; must be profiled.
- Hordes expire after 3600 real UTC seconds even while engaged. No clue means
  native attention plus a <=60s logical cooling period, then roaming metadata.
  Native packs use native patrol until expiry/stall/release. A stopped pack's
  waypoint intent is replaced by a local hold before survivors are rehomed in a
  native default group. No DeleteGroup/agent destruction is used. Original CE
  group restoration and cleanup compatibility remain a specific experiment.
  Absolute retirement is checked every tick independently of actor-sweep progress,
  so repeated CE registrations cannot prolong a record indefinitely.
- Queue <=16 by default (validated ceiling 32), <=8 voice attempts per tick,
  emitter cooldown >=10s; accepted memories <=30s, strength decays, metadata hops
  <=2 with **no scripted forwarding**. Native audio/hearing is not rate-limited
  or silenced by these metadata limits.
- Each native group/member scan is bounded; there is no full-world scan.
  Entities initialized before module startup can remain untracked until a later
  eligible native voice event; they continue ordinary native AI.
- JSON reads/writes <=64KiB, snapshots normally no faster than 60s (validated
  30–300s), plus dirty shutdown flush. Fields use invalid sentinels when absent.
  Schema/build/world/clock/generation/IDs/counts/finite coordinates and immutable
  reservations are validated; count refill and retired/unresolved reactivation
  are rejected across generations.
- Alternating snapshots retain a previous generation. Any present corrupt slot
  quarantines; no silent fallback to a spent population budget, reset or wipe.
  Exact readback is checked. This is recoverable quarantine, not a claim of
  atomic/fsync crash durability. UTC rollback and unsupported clock years disable
  module work. Supported signed-seconds clock years: 2026–2037.

## Contact guard: exact claim and required experiment

`EnableContactGuard=false` is intentional. `ZombieBase.FightLogic` contains the
scripted `DamageSystem.CloseCombatDamageName` calls inside its attack/`WasHit`
branch. Early `return true` in our override skips that branch for the current
invocation when `CanAttackToPosition` rejects the current target position.
It does **not** call an attack cancellation API, does **not** end the native
animation/command and does **not** prove `WasHit` cannot remain queued and apply
on a later frame. No verified cancellation/consumption semantics were found in
`DayZInfectedCommandAttack`, whose exposed query is `WasHit`.

Next trial: record command ID, WasHit lifecycle and authoritative health in
baseline/guard runs while a target moves behind a solid wall/closed door between
attack selection and impact, then emerges again during the same command. Include
same-side and ordinary attack controls, block stance and two clients. Confirm no
delayed damage or stuck attack. Until then this is an **experimental invocation
filter**, not an accepted wall-hit correction.

## Specific next experiments, not broad API-unavailable claims

1. Compile this addon in Workbench/DayZDiag and normal server; run the optional
   native policy selftest. Check `GroupBehaviourTemplates DZInfectedPackBeh`, cast,
   PGFilter flags and actual SetWaypoints traversal. Test transferring CE agents,
   original-group cleanup, native combat/crawl interruption, retirement, fallback
   allocation failure and shutdown. APIs exist; their integration is untested.
2. For one actual building, survey observed-floor reachable room/door anchors,
   open/closed-door variants, heights and visibility. Native SampleNavmeshPosition
   and FindPath are available; semantic room order/data and an accepted doorway
   route are missing. Then supply a real class-specific anchor catalog rather
   than calling the current offset anchors rooms.
3. Compare civilian/military search overlays against unchanged CE class/location
   pools and native controls. For a slow stalker, test speed override enable/
   release across stopping, command changes and leg damage before implementing
   throttling. The override API exists; safe underlying-input semantics and audio
   are unproven, not asserted impossible.
4. Determine whether CE serializes these infected at restart and provides a
   durable member ID/owner hook usable by this addon. Crash/restart exact-member
   reconciliation must precede persisted pack rebinding. No recreation fallback.
5. For abstraction/materialization, find a production CE ownership/reservation
   and avoidance mechanism plus two-observer visibility/hysteresis proof. The
   inspected forced SpawnDE functions explicitly bypass these protections; they
   cannot be substituted. Native LOD and script materialization are different.
6. Log native gunshot/voice response and pack attraction with two clients across
   walls, floors, weather and surfaces. Determine an authoritative hearing
   delivery/provenance hook and synchronized player-audible rebroadcast mechanism
   before supplementing native chains. NoiseParams alone proves neither.
7. Run intended 3–6-player paired performance/native-fairness trials. All numbers
   above are provisional pilot bounds, not calibrated acceptance budgets.

Traceability retained: T018–T020 / AI-001–AI-012 and AUD-001–AUD-007 remain pending
native controls/results; T021–T022 / HOR-001–HOR-011 remain pending chains,
activation, exact identity, restart, global occupancy, visibility and performance.
NET-001–NET-008 combined-module/normal-package acceptance remains pending as well.
No missing experiment is marked accepted or removed from the roadmap.

## Actual TDD and verification record

The test file was written before the implementation. Command throughout:

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_infected_contract.py -v
```

Initial run: missing `HCInfectedPolicy.c` (setUpClass FileNotFoundError, exit 5).
Then scalar seams were added with failing default bodies before implementation.
The meaningful red run executed **9 tests, 8 failures**, exit 1; examples:

```
test_chain_overload_dedupe_cooldown_ttl_hops_and_attenuation ... FAIL
  AssertionError: False is not true
test_horde_finite_lifecycle_and_escape_without_new_clues ... FAIL
  AssertionError: 1 != 0
test_restart_does_not_rebind_or_replenish_unresolved_entities ... FAIL
  AssertionError: 6 != 0
Ran 9 tests in 0.002s
FAILED (failures=8)
```

After minimum policy/integration implementation: **9 tests passed**. Further
tests preceded snapshot membership/progression, native route/search interruption,
visibility provenance and per-profile anchor budgets. Recorded subsequent reds
included missing new policy seams, and accepting visual provenance initially
failed `AssertionError: False is not true`. These were corrected in Enforce source.
Final targeted run: **15 tests passed**, exit 0.

Full discovery was also executed:

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v
Ran 245 tests in 6.902s
OK
```

This final integrated run passed after the other module owners completed their
changes. An earlier run during their work had two unrelated crafting/package WIP
failures; no out-of-scope edits were made to address them. `git diff --check`
also passed. A final horde-lifetime scheduling fix is covered by the same scalar
3600-second boundary checks; it does not establish native timing behavior.

The standard-library-only Python harness translates only the intentionally small
scalar Enforce policy subset and executes its actual bodies with explicit
synthetic fixtures (`tests/fixtures/runtime/infected-policy.json`). It also checks
source wiring and absence of prohibited shortcuts. It does **not** compile
Enforce, execute native methods, test actual JSON file I/O in DayZ, establish room
navigation, hear audio, prove authoritative damage/replication or establish crash
durability. Optional native selftests have not run. No native compile claimed.

## Integration review corrections

Main took ownership after the worker stopped. Independent review identified
IR-01 release ownership loss, IR-02 an accepted budget unable to collect three
members, and IR-03 stale native membership/active-route metadata. Three added
source/policy regressions first failed, then all 19 infected tests passed.
The partially authored worker release/membership policy was preserved and wired.

Release now retains failed/expired packs in a static pending-owner list even
when their caller discards them. Module ticks retry cleanup before the health
guard. Native allocation is limited to three attempts with five-second backoff;
an exhausted pack remains held/owned and blocks new pack creation, with an
operator log. It is not silently detached or destroyed. Structural limits allow
two horde packs, two investigators and at most one partial transfer; no new pack
can start while any release is pending. After core stop there is no further
retry tick; retained handles remain until native world teardown. Actual fallback
allocation/transfer failure, teardown and CE ownership require native trials.

Adoption now requires the tested 9..32 work budget at admission and execution.
Tick progress counts actual native group membership. Releasing, expired/stopped
and restarted routes clear HasRoute; RouteEnd remains historical. Stop updates
this metadata before saving. Finite reservations/tombstones are preserved.
Native self-test source includes budget/membership/retry assertions, unexecuted.

Final review also found low-budget adoption starvation: each interval restarted
at already-assigned first members. A persistent rotating scan cursor now visits
the bounded registry fairly without increasing per-tick scan limits. The new
regression first failed on the absent cursor seam; after implementation all 20
infected tests pass. The restricted translator requires brace-delimited branches;
that test harness limitation is not a native compiler result.
