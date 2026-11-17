# V1 ecology and migration — #34 writer report

Source/package implementation is authored for the supported native subset.
Runtime acceptance and production enablement remain **PENDING**. No DayZ, Wine,
network, Git index, commit or push operation was run. Animal destination control,
food/water sensory attraction, biological carrying capacity and offscreen
population simulation have evidence-backed exclusions below; they are not
silently counted as completed gameplay.

## Inputs and scope

Read AGENTS.md, README ecology/migration, MODULE_STATUS, the runtime contract,
the ecology sources/tests and the installed native interfaces. The two required
spec paths (`docs/SPECIFICATION.md`, `docs/specs/001-survival-overhaul/spec.md`)
do not exist in this checkout. No cached issue body was found. `gh issue view 34`
was not run because this writer explicitly forbids network. The active user
contract and `.banso-brief.md` supply the task; no issue details were invented.
Scoped Banso specification, plan and task ledger are alongside this report.
No lifecycle/dispatch operation was taken over from the orchestrator.

## Files

- `mods/HollowCountry/scripts/3_Game/Ecology/HCEcologyRuntimeData.c`: bounded
  durable schedule/journal DTOs and frozen diagnostic resource samples. Required
  counter fields use invalid sentinels to reject incomplete deserialization.
- New `4_World/Ecology/HCEcologyMigrationRules.c`: UTC due/attempt policies,
  eight-schedule bound, strict state/world/sequence admission, CE-limited shared
  cohort reservations, no catch-up burst.
- New `4_World/Ecology/HCEcologyMigrationNative.c`: once-per-process experimental
  marker, static `Qualified() == false`, explicit unsupported animal destination
  capability, live CE ceilings, shared consistent UTC reader, owned Infected
  public API and frozen, owner-admitted sensory evidence only.
- New `4_World/Ecology/HCEcologyMigration.c`: enrollment, write before native
  retarget, exact attempt completion, terminal-write fault latch and preservation
  of the owner's path-work charge. No group/entity ownership acquisition.
- New `4_World/Ecology/HCEcologyMigrationStore.c`: bounded 16 KiB journal,
  per-world paths, pending/image/readback/delete protocol and fail-closed restart.
- New `4_World/Ecology/HCEcologyResourceSurvey.c`: native object observations
  and explicit-point pond/sea classification behind the experimental gate. A
  resource location is never promoted to a sensory ticket or a usable shore.
- `4_World/Ecology/HCEcologyRuntimeModule.c`: start/stop the cadence service
  through the existing module, after successful observation-service admission.
  The existing registration block is unchanged; no HCModule was added.
- `tests/unit/test_ecology_module.py`, `test_ecology_rules.py`: behavioral
  lifecycle checks and a standard unittest `load_tests` hook. The existing BDD
  binding stays unchanged and also executes the new v1 ecology cases.
- New `tests/unit/test_v1_ecology_{migration,resources,territories}.py`: execute
  authored Enforce bodies through the existing syntax translator with explicit
  synthetic engine/storage collaborators; exercise the stdlib territory audit.
- New `tools/audit/ecology_territories.py`: bounded, read-only mission XML audit.
  Records every supplied zone and source digest; missing capacity stays unknown.
- `scratchpad-review/v1-ecology/`: spec/plan/tasks, actual RED/GREEN transcripts
  and this report. `.banso-writer/commit-message` contains the suggested message.

`HCEcologyNative`, the original live cohort/path probe, and the resource scheduler
remain conservative. Its `ProviderAvailable == false` is intentional: a separate
infected clue provider does not qualify food/water sensory attraction. Existing
fresh ground-food, well and finite-water observations remain in that service.
No shared Core, Infected, settings, config, inputs or asset files were edited.
The pre-existing untracked `.banso-brief.md` was not changed.

## RED and GREEN evidence

All unit/translator/native ports are synthetic unless explicitly described as a
read-only source inspection. Offline success establishes neither DayZ behavior
nor durability, perception, collision, navigation or client presentation.

Actual RED transcripts:

- `RED-migration.txt`: 12 authored behavior cases fail before the new methods
  exist. `RED-store.txt`: five store cases fail before the new store exists.
- `RED-resources-territories.txt`: resource survey and audit cases fail before
  their implementations exist (the initial discovery also imported four existing
  resource tests; that redundant import was removed).
- `RED-shared-capacity.txt`: actual assertion `0 != 2`; independent schedules
  incorrectly passed a shared CE ceiling before shared reservations were added.
- `RED-lifecycle.txt`: expected migration start callback absent before wiring.
- `RED-animal-enrollment.txt`: unsupported animal enrollment returned true before
  the native capability veto was added.
- `RED-required-fields.txt`: missing schedule counter was accepted as zero before
  required counter sentinels were introduced.
- `RED-terminal-budget.txt`: terminal journal failure returned zero after native
  work; fixed to return work-spent/uncertain (1) and latch the service fault.
- `RED-clock.txt`, `RED-perception-admission.txt`: missing shared clock method and
  explicit owner-admission arguments before their interfaces were implemented.
- `RED-integration-suite.txt`: first whole-suite run, 2,582 tests / one failure /
  one skip. The changed ecology BDD filename violated the existing binding
  contract; the filename was restored and owned `load_tests` integration added.
- `RED-migration-behavior.txt` retains an intermediate translator harness error
  (missing synthetic population constants); it is not engine or policy evidence.

Passing commands/transcripts:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_v1_ecology_migration -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_v1_ecology_resources tests.unit.test_v1_ecology_territories -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_ecology_module -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p 'test_ecology_rules.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_bdd_bindings tests.unit.test_v1_ecology_migration tests.unit.test_v1_ecology_resources tests.unit.test_v1_ecology_territories tests.unit.test_ecology_module tests.unit.test_script_syntax -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit
python3 -B -m tools.validate.bdd
```

`GREEN-required-fields.txt`: 22 migration cases. `GREEN-lifecycle.txt`: nine
module cases. `GREEN-bdd-ecology.txt`: 64 bound ecology cases.
`GREEN-final-focused.txt`: 57 cases including syntax and BDD binding admission.
Final full-suite and BDD totals are recorded at the end of this report.

`GREEN-package.txt` records a successful deterministic authored-source PBO build
and verification in a fresh private temporary directory. No game assets were
included. This unsigned container is not native compilation or signed loading.

A read-only smoke of the new audit against the locally staged Chernarus mission
retained 1,023 supplied zones (255 red-deer, 768 infected) and raw globals
AnimalMaxCount=200 / ZombieMaxCount=1000. It retained `runtime_acceptance=PENDING`.
Those are inspected content values, not live CE counts or measured population
budgets. The native mission files/output were not copied into the repository.

## Native API citations

Every native path below is relative to
`~/.cache/hollow-country/native-scripts/scripts-1.30.164289/`.
These declarations were inspected locally; declarations are not observations of
runtime behavior. Shared HC helpers are cited separately because they are authored
public interfaces rather than engine APIs.

| Surface | Native file:line |
| --- | --- |
| GetGame / server authority / world / world name | `3_Game/gameplay.c:636`; `3_Game/Global/Game.c:1120`, `:931`, `:932-939` |
| Existing tick clock | `3_Game/Global/Game.c:1535` |
| Pond and sea terrain classification | `3_Game/Global/Game.c:1196-1197` |
| Object deletion, position, type, alive, ruin, food classification | `3_Game/Entities/Object.c:215`, `:287`, `:467-471`, `:517-521`, `:1219-1223`, `:723` |
| Water source classification | `3_Game/Entities/Object.c:647-660`; `3_Game/Enums/EWaterSourceObjectType.c:1-6` (WELL=0) |
| Hierarchy custody, quantity, liquid type | `3_Game/Entities/EntityAI.c:885`, `:2222-2232`, `:2714`; native ItemBase overrides at `4_World/Entities/ItemBase.c:3485-3493`, `:3887` |
| Liquid-container classification | `4_World/Entities/ItemBase.c:825-830` |
| Water/clean-water constants; edible class ancestry | `3_Game/constants.c:578`, `:591`; `4_World/Entities/ItemBase/Edible_Base.c:1` |
| Animal/creature AI ancestry and agent access | `4_World/Entities/Creatures/Animals/AnimalBase.c:1`; `3_Game/Entities/DayZAnimal.c:191-211`, `:655-675` |
| Native navmesh world/filter/path API retained by existing ProbePath | `3_Game/Global/World.c:116`; `3_Game/AI/AIWorld.c:1-29`, `:65`, `:98`, `:122` |
| Agent/group ownership and infected-only waypoints (used inside existing pack provider) | `3_Game/AI/AIAgent.c:6-7`; `3_Game/AI/AIGroup.c:6-14`; `3_Game/AI/AIGroupBehaviour.c:19-32` |
| CE handle and integer globals, including missing/wrong-type sentinel | `3_Game/CE/CentralEconomy.c:574-585`, `:746` |
| Date/time primitives used by shared UTC helper | `1_Core/proto/EnSystem.c:76`, `:100` |
| File existence, open/read/close/print, mkdir, delete | `1_Core/proto/EnSystem.c:397`, `:417`, `:425`, `:443`, `:462`, `:525`, `:528`; READ/WRITE enum at `:382-386` |
| Bounded native JSON string codec | `3_Game/tools/JsonFileLoader.c:69-94` (`LoadData`, `MakeData`; error/out arguments declared before calls) |
| Diagnostic Print | `1_Core/proto/EnDebug.c:96` |
| Math.Min / Max | `1_Core/proto/EnMath.c:553`, `:566` |
| Array Count / Get / Insert | `1_Core/proto/EnScript.c:380`, `:399`, `:407` |
| Finite bound and vector distances used by retained path checks | `1_Core/proto/EnScript.c:4`; `1_Core/proto/EnConvert.c:112-113`, `:196`, `:210` |
| Token checks, explicit integer string conversion | `1_Core/proto/EnString.c:113`, `:199`, `:240`; `1_Core/proto/EnConvert.c:30`, `:59` |

Authored public API consumed, unchanged:

- `Groups/HCGroupService.c:1-88`, `HCGroupClock.Utc()`: consistent bracketed UTC
  snapshots, bounded retries, calendar validation and monotonic process watermark.
  It does not require the Groups service to be enabled.
- `Infected/HCInfectedNavigation.c:219-287`: `OwnsMember`, `Retarget`; the latter
  rejects changed ownership, combat, injury, expiry, cooldown/attempt exhaustion
  and invalid geometry, then uses native infected waypoints.
- Same file `:361-369`: release/quarantine queries; `:481-500`: visual evidence
  availability stays false. No inference from retained native targets was added.
- `Infected/HCHordeStimulus.c:45-68`, `:102-115`: clue precedence and frozen copy.
- `Infected/HCInfectedState.c:47-87`, `:170-188`: independent qualification gates
  and clue liveness. Ecology never promotes those gates or refreshes their TTL.

## Exclusions and pending experiments

1. **Animal-directed migration/resource goals excluded for this native snapshot.**
   `AIAgent.c:1-8` exposes idle/group access; base `AIGroupBehaviour.c:1-5` has no
   destination API. The waypoint subclass at `:19-32` is explicitly infected.
   `DayZAnimal.c:664-675` exposes controller and animation/script commands, not an
   animal path destination. `Entities/DayZCreatureAIInputController.c:3-34` and
   `Entities/DayZAnimalInputController.c:54-75` expose motion/behavior overrides;
   implementing a new locomotion controller around those would invent unobserved
   navigation. `AnimalDestinationSupported()` remains false even with a marker.
   Existing native animal grazing/travel/threat behavior is preserved.
2. **Forced feeding/drinking, food attraction and thirst/diet simulation excluded.**
   Animal behavior enums include eating/drinking (`DayZAnimalInputController.c:2-53`),
   but an animation/behavior slot does not establish target selection, sensory
   eligibility, food depletion, water access or conservation. Resource observations
   retain `SensoryEligibility=false`. No stock is consumed or created.
3. **Live territory capacity / biological carrying capacity excluded.**
   CentralEconomy.c exposes scalar globals but no territory enumeration or live
   occupancy getter. The read-only audit retains XML geometry/density as static
   metadata, not admission evidence. In the local staged mission,
   `env/red_deer_territories.xml:4-8` has Graze/Water/Rest zones with all density
   fields zero; `env/zombie_territories.xml:4-8` has nonzero density ranges.
   `db/globals.xml:3`, `:31` supplies raw maxima. These are mission content, not
   native script APIs or proof that the running server uses those exact values.
   Runtime reads the actual CE globals, rejects missing/zero data, and caps its
   conservative total route reservations separately for each population. It never
   spawns, despawns, replenishes or equates a partial cohort registry to a census.
4. **Unobserved global seasonal/offline migration excluded.** No clock-driven
   teleport, remote position update, hidden player destination, offscreen spawning
   or entity identity recreation. Across restart only cadence, sequence, reserved
   count and outcome survive. Accepted command != observed arrival. Existing
   Infected owns route progress, release, stable membership and recovery.
5. **Native path surveys / restart / performance pending.** Existing AIWorld
   probes are geometry candidates, not route traversal receipts. Terrain pond
   presence does not establish a shore. No surveyed route, trustworthy perception
   source, durable crash guarantee or combined performance budget was accepted.
   Eight schedules, six members/route, 16 KiB journal and the existing bounded
   observation/path budgets are implementation ceilings only.
6. **Incomplete/ambiguous journal handling is deliberately conservative.** A pending
   schedule survives restart and blocks that slot; a pending storage write blocks
   the world journal. Reservations are never automatically reclaimed because an
   old route may still exist. This can reduce availability after ambiguity. Do not
   delete pending files or reset counts to make the feature appear operational;
   owner recovery requires correlated native ownership evidence and operator review.

## Owner wiring patch (not applied)

No Core, config.cpp, inputs.xml or HCSettings patch is required. The pre-existing
Ecology module already registers, and its owned start/stop wiring is implemented.
The remaining hook belongs in `Infected/HCInfectedModule.c`, inside
`RetargetCohorts`, replacing only:

```c
int result = pack.Retarget(sweep.Stimulus, m_Now);
```

with the following. Keep the existing `RetargetSpent`/work-budget/cursor/route
snapshot code immediately after it. Cohort IDs must keep their existing durable
identity; never recycle an ID to evade a pending schedule or reservation.

```c
int result = 0;
if (HCEcologyMigrationQualification.Admitted())
{
    array<HCInfectedActor> ecologyMembers = new array<HCInfectedActor>;
    int ecologyMemberIndex = 0;
    while (ecologyMemberIndex < m_Actors.Count() && ecologyMemberIndex < 32)
    {
        HCInfectedActor ecologyMember = m_Actors.Get(ecologyMemberIndex);
        if (ecologyMember && ecologyMember.GroupId == record.Id)
        {
            ecologyMembers.Insert(ecologyMember);
        }
        ecologyMemberIndex++;
    }
    // Partial member lists cannot lower the CE reservation charge. Unknown,
    // dead/missing or overflowed membership stays with the existing owner.
    bool ecologyComplete = !sweep.Ambiguous;
    ecologyComplete = ecologyComplete && sweep.Accounted == record.Reserved;
    ecologyComplete = ecologyComplete && ecologyMembers.Count() == record.Reserved;
    string ecologyScheduleId = "infected-cohort-" + record.Id.ToString();
    if (ecologyComplete && HCEcologyMigration.Enroll(ecologyScheduleId, HCEcologyPopulation.INFECTED, 300))
    {
        result = HCEcologyMigration.Submit(ecologyScheduleId, pack, ecologyMembers, m_Now, m_Admission.Investigation, HeardAdmitted());
    }
}
else
{
    result = pack.Retarget(sweep.Stimulus, m_Now);
}
```

This preserves native ownership and the Infected owner's admission flags. A
faulted ecology service must not fall back to retargeting around its durable
schedule. Return 1 means native work was spent or its terminal persistence is
uncertain; return 2 means accepted retarget with journal readback, never arrival.
The caller still owns ticking/releasing packs and observing route completion.

**Additional prerequisites:** current Infected native-route/stimulus/visual/heard
qualifications are false. The ecology marker cannot override them. The Infected
owner must provide its own reviewed experimental admission and trustworthy clue
source before a movement acceptance run can exercise this adapter. Adding a
retained target or fake clue to force that run is not an acceptable hook. A public
bounded exact-membership snapshot could later replace the owner's loop; no new
Infected API is referenced by the authored ecology files.

## Exact later local-server acceptance procedure

All steps remain unexecuted. Use a fresh isolated local profile/storage and one
connected client per the active user decision. Any future audio/network/visibility
change needs a separate two-client run; this patch emits no gameplay audio or RPC.

1. Owner applies/reviews the hook above and supplies the prerequisite Infected
   experimental route/perception admission. Keep all production Qualified methods
   false. If no trustworthy clue path is available, record the blocked prerequisite
   and do not manufacture an infected movement PASS.
2. Freeze source and rebuild a fresh authored-source PBO using
   `python3 -B tools/package/pbo.py pbo --addon mods/HollowCountry --out <fresh-pbo>`;
   verify with `python3 -B tools/package/pbo.py verify <fresh-pbo>`. Record hashes.
   Compile the exact source in DayZDiag, then load the same candidate in the normal
   dedicated server/PBO flow described in tools/package/README.md. Record compiler,
   initialization and script errors; a source PBO checksum alone cannot pass.
3. Baseline run without `$profile:HollowCountry/acceptance/ecology_migration.enable`:
   verify the not-admitted diagnostic, no migration journal creation/retargeting,
   and unchanged native animal/infected behavior. The existing observation service
   may still maintain its separate diagnostic counters.
4. Stop gracefully. Create the empty marker in the isolated acceptance directory,
   restart, and retain the EXPERIMENTAL/runtime-PENDING log and migration-journal
   readiness line. Add/remove the marker while this process is alive and confirm
   admission does not change; the marker is read once per process.
5. Join the local dedicated server with the normal client and the same addon,
   using the observed loopback game/query ports (documented baseline is
   `-connect=127.0.0.1:2302:27016 -port=2302`). Confirm movement, inventory and reconnect.
6. In a temporary diagnostic mission harness, call
   `HCEcologyResourceSurvey.ObjectSample(liveResource, "survey-food-a", GetGame().GetTime())`
   for ground food, empty/full water container and a well. Repeat after quantity
   depletion, inventory pickup, ruin and deletion. Observe the actual native calls,
   expected presence/rejection, and unchanged inventory quantities. Call
   `HCEcologyResourceSurvey.Pond(surveyedPoint, "survey-pond-a", GetGame().GetTime())`
   at measured pond/land/sea points. No pond point may be counted as an accessible
   drinking location without a separate shore survey.
7. Observe `HCEcologyRuntime.IntentSnapshot(GetGame().GetTime())` on a local bounded
   animal/resource cohort. Record actual AIWorld path points/length/endpoint,
   failure/closed-door/water cases and query budgets. Verify no actor transforms,
   headings or movement overrides are changed. Animal migration enrollment must
   fail; observing native grazing/drinking does not qualify directed migration.
8. With an actually owned, complete, healthy infected cohort and an independently
   qualified frozen clue, enroll the durable cohort schedule once (300 seconds in
   the owner patch). Before due: no retarget/write. At due: verify the pending
   journal with incremented sequence/reserved count/next UTC precedes the native
   `Retarget` invocation; accepted return is recorded separately from traversal.
   Observe movement and actual arrival through the existing pack's RouteResult /
   RouteCompleted and the connected client. Never refresh a clue from hidden live
   player coordinates. Expired/self-heard/disabled/unowned/engaged/injured cohorts
   must veto. Blocked geometry must spend the attempt and the owner's work budget.
9. Test missing/zero CE maxima in a disposable mission and two cohorts under a
   reduced live ZombieMaxCount. Missing data must reject, and combined persisted
   reservations must not exceed the maximum. Run the read-only territory audit
   with explicitly supplied mission XML; verify its digests and retain raw zones,
   unknown animal capacity and PENDING status outside the source checkout.
10. Stop gracefully before due, restart using the same profile/storage, reconnect
    and confirm unchanged next-due UTC/sequence/reservations and no catch-up burst
    or restored entity handles. Repeat across an elapsed due time: only a fresh
    owner-supplied pack and live qualified clue may retarget; offline time cannot
    move/recreate a cohort. Inspect actual CE/native membership separately.
11. In disposable copied profiles, interrupt after each intent/image/readback/
    terminal-write boundary and test corrupt, oversized, foreign-world, omitted
    fields, pending and rollback-clock states. Preserve ambiguous artifacts.
    Confirm no movement replay, no reservation reset, process fault latch and no
    extra owner path budget after terminal failure. Readback is not fsync proof.
12. Repeat normal-build PBO/server traversal/restart with this candidate. Record
    one-client route/collision/fairness evidence. Then measure identical baseline
    and combined feature scenarios at the intended 3–6-player load: server frame
    time, path-query counts, journal time, memory and entity counts, including
    blocked routes and restart. Establish budgets from those measurements before
    production enablement; current ceilings are not a qualified benchmark.

## Final verification

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit`:
**2,582 tests, OK (one skip), 100.034 seconds**, exit 0; see
`GREEN-full-suite.txt`. The first integration failure was corrected before this
final run.

`python3 -B -m tools.validate.bdd`: **1,332 tests, OK (one skip),
61 bound offline scenarios, 39.407 seconds**, exit 0; see `GREEN-bdd.txt`.
Runtime acceptance: NOT EXECUTED. This required BDD command was run once.

Source PBO: 100 authored entries, prefix HollowCountry, 890,360 bytes;
SHA-256 `8562952d1cbcd4c68c3b37fa2bf0b7e61958ec2efff2abf70d025d8a94a4b0cc`.
Unsigned development only; see `GREEN-package.txt`.

`git diff --check` passed. A read-only native type/declaration scan found no
new identifiers equal to engine types. The syntax suite passed; no ternaries,
leading logical operators, redeclared sibling locals, unqualified enum members,
implicit numeric concatenation or undeclared out arguments were introduced.
