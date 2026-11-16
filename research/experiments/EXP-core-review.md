# EXP-core-review: independent shared-core static/native API review

Date: 2026-11-16.
Disposition: CORE-001 (P2) resolved in source on re-inspection; native timing validation remains pending. No confirmed compile blocker or client-authority vulnerability in the reviewed core. This is source inspection, not native execution or runtime acceptance.

## Scope and evidence

Read AGENTS.md, docs/SPECIFICATION.md, docs/specs/001-survival-overhaul/spec.md, plan.md/tasks.md, and docs/RUNTIME_IMPLEMENTATION_CONTRACT.md. Reviewed only these implementation files:

- mods/HollowCountry/config.cpp
- mods/HollowCountry/scripts/3_Game/HCSettings.c
- mods/HollowCountry/scripts/4_World/Core/HCModule.c
- mods/HollowCountry/scripts/4_World/Core/HCServer.c
- mods/HollowCountry/scripts/4_World/Core/HCNativeSelfTests.c
- mods/HollowCountry/scripts/5_Mission/HCMissionServer.c

Installed native-source root, abbreviated N below:
`/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289`.
The implementation contract records scripts.pbo SHA-256
`09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a`.
No native source copied into the repository. Gameplay module directories and package tooling are outside this audit.

Reviewed source SHA-256 (HCServer refreshed at fix re-inspection; other files retain their original review hashes):

| File relative to mods/HollowCountry | SHA-256 |
| --- | --- |
| config.cpp | 3b40ac0dfed257ae16c56bc9cd74be461d24b3e808e673b97abc01f9c79994db |
| scripts/3_Game/HCSettings.c | efec8d1ab67bc0005eb5b15b985143dfec4bb9cfae2fba187d640611e17b9809 |
| scripts/4_World/Core/HCModule.c | 269b77b174e6395647c07846f2a693c44a7c669b175b4fcd0729accdf3debf56 |
| scripts/4_World/Core/HCNativeSelfTests.c | ec883e558c623407eb00b53a65dfdb767e9b26f8dbd039058cfd70c75fdfa697 |
| scripts/4_World/Core/HCServer.c | bb6a87356d10ca180777f747bb4877913966c8cbb8035b4d4cc3910dfd0e5272 |
| scripts/5_Mission/HCMissionServer.c | 21d367b470e2273c91c2c3abde9a4ea226c778019367c5ea26c888f87c5da485 |

Concurrent integration can supersede these hashes and line references.

## Finding CORE-001 — P2, resolved in source; native timing pending

Original location: `mods/HollowCountry/scripts/4_World/Core/HCServer.c:46-47`
in original source SHA-256
`f75eaf72196c97fb1446cb1a1a92cb9d4b146171aaa99107fbbe933720418530`.

The original Tick calculated module delta exclusively from the configured period.
The installed call queue is processed by the game's frame update:
N/3_Game/DayZGame.c:3025-3028 calls the system queue's Tick(timeslice).
N/2_GameLib/tools.c:54-61 describes execution when a scheduled time has elapsed
and declares CallLater(func, int delay, bool repeat, ...). It provides no
guarantee of execution at the exact requested deadline. A delayed callback could
therefore undercount time for consumers accumulating the advertised deltaTime.

### Source resolution inspected 2026-11-16

Re-inspected HCServer.c SHA-256
`bb6a87356d10ca180777f747bb4877913966c8cbb8035b4d4cc3910dfd0e5272`.

- Line 8 stores m_LastTick.
- Lines 39-41 initialize the timestamp with GetGame().GetTickTime() on each
  successful Start, before scheduling the first callback. Stop/Start therefore
  takes a fresh sample.
- Lines 48-50 sample the clock once, calculate now minus m_LastTick, and update
  m_LastTick for the next callback.
- Lines 53-57 reject any delta that does not satisfy elapsed > 0, or exceeds
  300 seconds: log, Stop, return without dispatching module ticks. Exactly
  300 seconds remains allowed. The five-minute threshold is a conservative
  source policy, not a calibrated runtime limit.
- Line 59 dispatches the measured elapsed value once per active module.
  No catch-up loop was introduced.
- Stop at lines 64-68 marks the core stopped, removes the repeating callback,
  stops modules in reverse order and clears the active array.

The clock call matches N/3_Game/Global/Game.c:910-914:
GetTickTime() returns a float in seconds since game start. An installed precedent
is N/4_World/Classes/AreaDamage/AreaDamageNew/AreaDamageLooped.c:28 and 50-52,
which initializes a timestamp and accumulates the measured difference.

This fixes the reported configured-period-versus-elapsed-time mismatch in source.
No new compile/API issue was identified in the inspected change. The dispatch
count remains bounded by the active-module registry; module internal work remains
the responsibility of each module and is outside this re-review.

### Pending validation

Native compilation, clock behavior, delayed-frame timing, removal of a repeating
callback from inside that callback, and shutdown/flush effects remain pending
DayZDiag and normal PBO/server testing. No native red/green execution is claimed.

A future native test with an injected clock would be useful if a small clock seam
is introduced by the implementation owner: feed samples producing 1.0, 1.6 and
0.9 second deltas; assert one dispatch per module per accepted callback, with
the measured delta. Cover zero, negative, exactly 300 and greater-than-300
seconds, no dispatch after Stop, and a fresh timestamp after restart. Use an
explicitly synthetic clock and module spy; it would verify authored branching
and dispatch only. Actual call-queue scheduling still requires real engine
timing observations. No clock abstraction, self-test or implementation was
written by this reviewer.

## Native declarations and lifecycle checks without additional findings

- HCMissionServer.c:3 and :9 match the inherited OnInit() and OnMissionFinish()
  declarations at N/3_Game/gameplay.c:700-703. MissionServer derives from
  MissionBase at N/5_Mission/mission/missionServer.c:5; its OnInit override at
  :85-97 performs native initialization. The authored hook calls super.OnInit()
  first. The finish override removes core callbacks/stops modules before its
  super call. A missing MissionServer-local finish override is not a compile
  defect: the method is inherited.
- HCServer.c:41 and :66 (fixed source) use matching CallLater/Remove method references.
  Signatures are at N/2_GameLib/tools.c:61 and :65; the installed MissionServer
  pairs its own repeating registration/removal at :68 and :80-82.
- HCSettings.c:47 and :53 match bool-returning LoadFile(string, out T,
  out string) and SaveFile(string, T, out string) at
  N/3_Game/tools/JsonFileLoader.c:7 and :42. They are not the deprecated
  void-returning JsonLoadFile/JsonSaveFile functions.
- HCSettings.c:37 matches FileExist(string) and MakeDirectory(string) at
  N/1_Core/proto/EnSystem.c:397 and :525. Directory creation is explicit.
  Existing settings are not overwritten on rejected load/validation.
- Core startup/ticking checks GetGame().IsServer(). All shipped gameplay
  booleans are false. Reviewed core introduces no custom RPC, client-provided
  path, inventory commit, teleport or gameplay spawn.
- Registration has an eight-module bound and rejects duplicate names.
  Stop cancels the repeating callback before stopping modules in reverse order.
  These source properties do not establish module internals or crash durability.
- CfgMods points Game/World/Mission at the corresponding authored directories.
  Static inspection did not identify a concrete config defect. Addon dependency
  resolution, config parsing and compilation are still native smoke-test gates.

## Validation and explicit limitations

Ran:
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_runtime_settings.py -v`

Result: 5 tests passed. These tests execute the offline Python admission validator,
not HCSettings.c, Enforce compilation, filesystem behavior or mission lifecycle.
These prior offline results do not validate the timing fix. CORE-001 is resolved
by source re-inspection only; native timing validation remains pending. No tests
were rerun for this report-only amendment.

WSL interop/native execution is unavailable per the task context. No DayZDiag,
normal PBO/server load, actual shutdown/restart, client join or two-client check
was executed. Do not promote any runtime requirement based on this report.

The native JsonSerializer implementation is opaque in this snapshot; matching
JsonFileLoader signatures does not establish strict rejection of missing/unknown
keys, duplicate keys, or wrong JSON types. Python schema tests do not establish
those semantics. Probe them natively before claiming parity.

OnMissionFinish is a valid inherited hook, but the timing/order of its invocation
on dedicated-server shutdown versus mission destruction is not demonstrated by
its declaration. Confirm graceful Stop/flush and absence of post-finish ticks
with native lifecycle logs. Abrupt process termination cannot be proven safe by
a finish hook alone. These are pending validation questions, not additional
confirmed bugs.

Only this report is owned/changed by the reviewer. Implementation, planning,
integration and other workers' modules remain with their respective owners.

## Crafting sidecar — bounded native lifecycle review (2026-11-16)

Scope extension authorized after the core review: read-only inspection of
`mods/HollowCountry/scripts/4_World/Crafting/**`; agentChandrasekhar retains
implementation ownership. Only this report was edited. N continues to mean the
pinned installed 1.30.164289 scripts root above.

Disposition: no remaining concrete compile/API, authority or mutation-order
defect identified in the final inspected snapshot. A pending-deletion admission
gap seen in the initial snapshot was closed by concurrent implementation work
and independently re-inspected below. No native dupe/loss/replay/crash acceptance
is implied.

CORE-001 remains resolved in source: latest HCServer.c SHA-256
`18bfc36172d1cf0ff1373c5fed37d72b0b9d44719d85835357f800e14e9bcbaf`
retains the measured clock delta, Start reset and bounded discontinuity Stop.
The earlier core section pins its prior reviewed snapshot; this later hash also
includes a revised module admission log message.

### Final inspected crafting source

| File in scripts/4_World/Crafting | SHA-256 |
| --- | --- |
| HCCraftingModule.c | 3d41141c6af214647e90171c616ab855a74c24f46d5ad4b45894bc849d302bab |
| HCCraftingNativeChecks.c | 82094c8063b1028c7ef86fad16580bda9519c593acdfbff1e55111a42f3892ee |
| HCRecipeRegistration.c | a0ca89c2b6e5355953c612094399e85d7a3b3c6aa59cca130593f60d12409230 |
| HCSalvageRecipe.c | 6b5d805bdf7930d085c1828261c8ca41915cb09b6d62f4def879531d7c29fc69 |

These are concurrent-work snapshots, not frozen integration artifacts.

### Installed mutation order and its implications

N/4_World/Classes/Recipes/RecipeBase.c:521-539 performs the following sequence,
after CheckRecipe succeeds:

1. SpawnItems at :532.
2. ApplyModificationsResults at :534.
3. ApplyModificationsIngredients at :535.
4. Do at :537.
5. DeleleIngredientsPass at :539 (installed spelling).

The authored overrides at HCSalvageRecipe.c:85-123 follow this lifecycle.

- **Do does not read an already deleted source.** Ingredient modification at
  N/RecipeBase.c:380-382 queues destroy=true inputs into m_IngredientsToBeDeleted;
  it does not delete them immediately. The tool receives AddHealth at :386-389.
  Actual Delete is requested later at :362-369. Therefore the source health
  read at HCSalvageRecipe.c:121 occurs before its deletion request. Result
  inheritance already ran at N/RecipeBase.c:323-334, and the authored Do applies
  the additional 0.75 health multiplier once.
- **Failed allocation does not consume the inputs on this path.**
  N/RecipeBase.c:242 tries inventory creation; :254-262 uses the ground fallback
  and inserts the cast result even if null. The authored SpawnItems at :97-104
  requires exactly one non-null ItemBase. Without that result, the authored
  ingredient-modification override at :107-111 and Do at :114-117 return.
  Native result modification skips null results at :282-285. No source is
  enqueued for deletion and no tool wear is applied in that failed-allocation
  branch.
- **Native creation is not an automatic stack merge in the inspected script.**
  N/3_Game/Systems/Inventory/Inventory.c:876-893 finds an attachment/cargo
  location and creates a new entity there. HumanInventory.c:65-70 can also try
  hands. RecipeBase then uses ground fallback. No second authored spawn or
  unbounded retry is introduced.
- **Singleton quantity is not necessarily an error.** Installed
  N/4_World/Entities/ItemBase.c:3319-3325 returns without changing quantity for
  items without quantity. Its :3453-3471 chooses stack maximum for splitable
  items before the quantity maximum. The concurrent HCCraftingNativeChecks.c
  revision at :28-34 handles quantity=1 outputs without requiring a positive
  stack capacity. Specific output config values and successful creation still
  require native validation; they were not observed by running those checks.

Paths abbreviated N/RecipeBase.c in this subsection refer to
N/4_World/Classes/Recipes/RecipeBase.c.

### CRAFT-S001 — P2 admission gap, resolved in source during review

Initial HCSalvageRecipe.c SHA-256
`d93d53117b5e38099a3cff8e526c0e5b2d23e2c3b9d5512b473ad4a7a0eca842`
did not reject items already scheduled for deletion in IsOwnedEmptyLooseItem.

Installed evidence: N/3_Game/Entities/EntityAI.c:779-783 sets m_PendingDelete
before delegating Delete, and N/3_Game/Entities/Object.c:82-84 queues ObjectDelete
for the next frame. EntityAI.c:812-815 exposes IsSetForDeletion, including that
pending flag. RecipeBase.CheckRecipe (:479-501), CheckConditions (:429-475),
and CanDo (:551-560) do not themselves reject that flag.

Thus a second server recipe invocation against a still-present pending-deletion
source lacked a rejection at the authored recipe boundary. This was a concrete
admission gap in source, not an observed network exploit or duplicate item.

Final HCSalvageRecipe.c:49 now rejects IsSetForDeletion for both source and tool
through CanDo at :71. Successful consumption marks the source pending before
PerformRecipe returns through the native delete pass. A subsequent invocation is
therefore rejected before another SpawnItems call on the inspected path.
The same concurrent revision adds null player/item guards at :90-91, before
entering native CheckRecipe, which dereferences player at :487.
Disposition: resolved in source; native same-frame replay test remains pending.

### Authority, registration and compile/API inspection

- Native completion is ActionWorldCraft.OnFinishProgressServer at
  N/4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWorldCraft.c:
  170-192. It clears reservations/junctures, calls PerformRecipeServer, then
  reacquires them. The recipe manager at
  N/4_World/Plugins/PluginBase/PluginRecipesManager.c:317-344 sorts ingredients,
  checks recipe validity and sanity, then calls the recipe.
- HCSalvageRecipe.c:88 rejects client PerformRecipe execution. Its CanDo
  rechecks exact tool type, source inheritance, separate ingredient identities,
  live/conscious player, ownership, empty cargo/attachments, unworn/unattached
  items, adequate tool health and disconnected reel state. It then delegates to
  native CanDo. Client preview permission at HCCraftingModule.c:11-12 does not
  authorize a server commit; server checks require started/validated/enabled
  state at :13-14. No generic client RPC was added.
- HCRecipeRegistration.c:5-10 registers after super on all peers, before the
  native cache build. Installed PluginRecipesManager constructor :52-56 calls
  CreateAllRecipes and GenerateRecipeCache; :660-663 calls RegisterRecipies.
  The native base declares that spelling at
  N/4_World/Classes/Recipes/Recipes/PluginRecipesManagerBase.c:14. RecipeBase
  constructor :67-85 initializes arrays before invoking the subclass Init.
- The reviewed PerformRecipe, SpawnItems, ApplyModificationsIngredients and Do
  signatures match the installed methods at RecipeBase.c:521, :215, :373 and
  :563. Referenced recipe fields are public at :23-63.
  RecipeIDFromClassname is available at PluginRecipesManager.c:470-475;
  GetHierarchyRootPlayer at N/3_Game/Entities/EntityAI.c:882;
  inventory IsAttachment at N/3_Game/Systems/Inventory/Inventory.c:410-419;
  energy IsPlugged/GetPluggedDevicesCount at
  N/3_Game/tools/Component/ComponentEnergyManager.c:905/:1188.
  No unsupported native API identified in these calls.

### Pending safety tests; no atomicity claim

The native path spawns output before wearing the tool and requesting source
deletion. Deletion itself is deferred. A crash or interruption in these mutation
windows is not an atomic inventory transaction, and this implementation explicitly
says so at HCSalvageRecipe.c:1-2. Neither the output-ready guard nor the new
pending-deletion check establishes durable exactly-once recovery. The
consequences for persisted input/output after process termination remain
unmeasured; this review does not assert either observed duplication or loss.

Keep the existing runtime acceptance gates: Diag and normal PBO compilation/load,
both ingredient orders, interrupted actions and gate changes, full inventory and
failed inventory/ground creation, repeated same-frame completion after deletion
is queued, two-client ownership/races/replay, and disconnect/crash/restart around
spawn, modifications and deletion. Inspect output quantities/condition, tool
wear and source disappearance on both clients. Output class/config admission
checks have not been run in the actual VM.

Offline command run on the final inspected revision:
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_crafting_contract.py -v`

Result: 10 tests passed. These are source contracts and explicitly synthetic
material/condition graph checks. They do not execute RecipeBase, prove actual
mutation/replication, or constitute native red/green evidence. No implementation
or tests were written by this reviewer.

The lifecycle conclusion and resolved pending-deletion concern were coordinated
to main task `01a1e5a3-8cd0-7161-b339-a1731ba3d474` during the review.

## Interiors sidecar — bounded native and package integration review (2026-11-16)

Scope: read-only `mods/HollowCountry/scripts/4_World/Interiors/**`, shared
registration/config seams and an in-memory package inclusion check.
AgentLaplace retains implementation ownership. Only this report was edited.

Disposition: no concrete native compile/API, ownership/duplication, persistence
protection or existing-object adoption/deletion defect identified in this
snapshot. This is a source review, not successful Enforce compilation or native
placement/search acceptance. Documented hard-false production gates are intended
behavior and are not findings.

### Reviewed snapshot

| File in scripts/4_World/Interiors | SHA-256 |
| --- | --- |
| HCInteriorAction.c | bd02306961dd2ee4622837278e72351eed99014e513a44b0b2c36fb969f8ccd0 |
| HCInteriorCatalog.c | 0f04ce3d3027d62496a87fbed6cec7ea9bb22dfa2d5ffada13f0ef604eeefeda |
| HCInteriorModule.c | b67b0d93ed42ad5e827e913a45ecb0c4f64ee27c4a690d3c5ad7eba5ced851d0 |
| HCInteriorRules.c | 4e272e9e20097be48af1a5728c86a5ad57da39bbf9336f5dcbe1a376c820242f |
| HCInteriorSelfTests.c | 6bc77e0620ea0845e666315874b6efed06ad1e8b4090186f4f3eb600cbe55c10 |
| HCInteriorStore.c | c7b9a69feecec70eb38ac3e5f2b65ba4b46e8934d8b43eff9422c9d75db723ef |

N denotes the pinned installed scripts root recorded above. Implementation line
references below are to these hashes.

### Compile/API and action integration evidence

- HCInteriorModule.c:40 uses a real zero-argument GetWorldName overload at
  N/3_Game/Global/Game.c:934-938. It is not restricted to the out-string form.
  GetObjectsAtPosition3D at module :186/:203 matches Game.c:930.
  CreateObjectEx and ObjectDelete at module :237/:240/:397 match Game.c:703-705.
- Module :301 uses the installed RaycastRV parameter order: hit set, with=null,
  ignore=player, sorted=true, ground_only=false, view geometry. Its declaration
  at N/3_Game/Global/DayZPhysics.c:199 defaults to nearest contact. Actual cabinet
  component/geometry compatibility remains an experiment, not an API mismatch.
  ModelToWorld, GetOrientation and SetOrientation are declared at
  N/3_Game/Entities/Object.c:873, :305 and :311.
- HCInteriorAction.c:84 and :93 match RegisterActions(TTypenameArray) at
  N/4_World/Classes/UserActionsComponent/ActionConstructor.c:27 and
  SetActions(out TInputActionMap) at N/4_World/Entities/ManBase/PlayerBase.c:1695.
  Native AddAction with that map exists at PlayerBase.c:1817.
  Both authored overrides call super and registration is unconditional across
  peers. Native ActionConstructor.c:6-20 sorts names before assigning IDs.
- ActionConditionContinue/OnStartServer/OnEndServer exist at
  N/4_World/Classes/UserActionsComponent/ActionBase.c:436/:1391/:1409.
  CCTCursor(float) exists at TargetConditionsComponents/CCTCursor.c:11 under
  that same component directory. GetHumanInventory exists at
  N/3_Game/Entities/Man.c:81 and the native head-position helper at
  N/4_World/Static/MiscGameplayFunctions.c:778.
- HCInteriorStore.c:9 passes a string to ReadFile; this is supported by
  N/1_Core/proto/EnSystem.c:419-425, whose return is the read byte count.
  The 32769-byte read and 32768 rejection limit precede deserialization.
  JsonFileLoader LoadData/MakeData/SaveFile signatures match the installed
  N/3_Game/tools/JsonFileLoader.c:69/:85/:42.

### Ownership, duplication and existing objects

HCInteriorModule.c:182-196 resolves a candidate by exact type and quantized
transform, rejecting multiple matches instead of selecting by query order.
Config validation at :51-60 rejects duplicate stable slots and quantized keys;
sorted slots also stabilize assignment order.

Vacant at :199-209 checks a same-type prop origin within 0.25 m, with a bounded
returned-count admission check. PlaceCandidate :224-230 rejects the entire
candidate on a possible orphan/native duplicate. It never adopts an existing
object as an owned decoration or searchable site.

Only successful CreateObjectEx results enter the local created list at
:237-247. Failure rolls back that list at :240; success transfers it to m_Objects
at :259. OnStop deletes only m_Objects at :395-399. The building, queried existing
props and generated/player loot are not added to that deletion list.

The ECE_DYNAMIC_PERSISTENCY flag at :236 is not an unconditional persistent-spawn
flag: N/3_Game/CE/CentralEconomy.c:33 explicitly describes initial nonpersistence,
with persistence enabled if a player takes the object. :17/:28/:30 document
physics creation, retained height and no initial lifetime. Those declarations
do not prove replication or restart behavior of these particular static props.

Vacant is an exact-duplicate guard, not collision-volume clearance against
different object types or model-baked furnishings. No unobserved safe-fit claim
is made here. The existing diagnostic-only placement trials and production gate
correctly leave collision, doors, navmesh and visibility acceptance pending.

### Authority and persistence protection

- Search resolves a server-owned site pointer and endpoint. Module :288-303
  checks live/conscious identity, empty hands, registered target, range,
  nearest contact and component. It does not trust a client cursor position for
  committing a grant.
- CanContinue at :320-324 requires the exact ActionData lock owner and a valid
  time window. CommitSearch at :340-355 checks that again, enforces six elapsed
  seconds and checks capacity before reserving. Only one inventory creation
  occurs at :367 after the reservation; :376 reduces quantity-bearing output
  to one unit. No ground fallback or output retry appears on this path.
- Store.Open at :50-70 requires explicit new-epoch initialization, compares a
  freshly computed immutable manifest with the saved manifest and never restores
  a stale backup. A partial/mismatched manifest is preserved, not overwritten.
  Paths use a fixed profile root and bounded validated epoch/slot integers;
  player identity and client data do not form filesystem paths.
- Reserve at store :100-121 sets in-memory phase before I/O, refuses an existing
  claim, and disables further claims on write/readback failure. RecoverSite at
  :78-97 quarantines corrupt, mismatched or incomplete claims, including a
  completion without a reservation. Only an exact valid spent result returns
  spent; reserved/ambiguous states never return available.
- Finish at store :124-139 retains the reservation and disables further claims
  if completion cannot be written. The design deliberately avoids automatic
  reissue; an unavailable reward after a failed allocation is not silently
  retried. Readback is explicitly not fsync and proves no crash durability.
- PlacementAccepted/SearchAccepted remain false in HCInteriorRules.c:50-57.
  The diagnostic overrides at module :145-149 are compiled only under
  DIAG_DEVELOPER. This documented boundary is not a bug.

### Cross-module package inclusion and validation

Inspected the three modded HCModuleRegistry overrides in Interiors, Crafting and
Infected: each calls super.RegisterModules() and registers its own module.
The shared CfgMods World path includes all three directories. No duplicate plain
HC class declarations were found by a narrow declaration-name scan; this is not
an Enforce name-resolution or compilation test.

Read-only in-memory check used the actual tools.package.pbo functions
collect_addon(Path("mods/HollowCountry")), pack(files) and parse(blob), asserting
the exact HollowCountry prefix, byte-for-byte entry roundtrip and inclusion of
every authored scripts/**/*.c file. No archive was written to disk.

Observed snapshot: 22 PBO entries, including config.cpp and 21 scripts:
Core 3, Interiors 6, Crafting 4, Infected 6, plus Game 1 and Mission 1.
PBO length: 105653 bytes. In-memory SHA-256:
`d6dc9195eeb80c687192b451b7f778b5288d8722aaa9e7fa386f07e6732bbf8c`.
This is a changing source/package snapshot, not a signed or engine-accepted build.

Ran:
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_interiors_contract.py -v`

Result: 21 tests passed. These execute restricted scalar algorithms and source
contracts in Python, not Enforce, world geometry, native persistence or networking.
No native red/green evidence is claimed. Native compile/load, storage probe,
crash handling, actual placements and two-client search/visibility remain pending.

Preliminary no-defect conclusions and the exact-duplicate-versus-clearance
distinction were communicated to main during review. No implementation or tests
were edited; no other worker's scope was changed.
