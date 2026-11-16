# Native interiors and search implementation experiment

Status: authored source and scoped offline regressions ready for integration;
**native compilation, DayZ behavior and production acceptance remain pending**.
Date: 2026-11-16. Build inspected: 1.30.164289. No client connection required
for this source work; no runtime success is inferred from source inspection.

## Scope and traceability

This worker changed only six Enforce sources under
`mods/HollowCountry/scripts/4_World/Interiors/`,
`tests/unit/test_interiors_contract.py`, `tests/fixtures/runtime/interiors*`,
and this report. Core, settings, config.cpp, packaging, BDD, specification, plan
and task files are owned elsewhere and were not edited by this worker.
Banso's existing T013/T014/T015 implement INT-01–INT-04, FR-005/006 and AC-005.
This report preserves the uncompleted native gates rather than closing those tasks.

| Source | Implemented responsibility |
|---|---|
| HCInteriorRules.c | Centimeter quantization, normalized yaw, bounded seeded layout choice, finite allocation policy, irreversible claim transitions and recovery, explicit false acceptance gates |
| HCInteriorCatalog.c | Native class allowlists; three authored trial layouts, family/ransacked histories; typed configuration, manifest, site and claim records |
| HCInteriorStore.c | Bounded JSON I/O, immutable allocation manifest and backup, reservation before grant, completion record, conservative recovery and operator reasons |
| HCInteriorAction.c | Native ActionConstructor/PlayerBase registration; six-second continuous action; profile-free client preview and authoritative server lifecycle |
| HCInteriorModule.c | Shared HCModule registration, validated bounded building manifest, startup-only placement, server target/component/LOS/range validation, allocation and action ownership |
| HCInteriorSelfTests.c | Native scalar tests and an explicit diagnostic-only real storage probe, without inventory/world spawning |

## Authored behavior and bounds

The addon uses the shared `HCModule` / `HCModuleRegistry` interface and reads
server settings through `HCServer.Get().GetSettings()`. It never loads settings
on a client. Native action registration runs on both peers independently of
feature flags. Client preview checks the known native furniture classes and
cursor feasibility; it is deliberately not authorization. Because no custom
client marker or state replication protocol is introduced, a preview can also
appear on matching vanilla furniture or an already depleted site; the server
rejects unregistered/disabled/claimed targets. Two-client UI feedback remains a
required experiment; preview is not proof of synchronized depletion display.

A profile manifest supplies 1–12 exact building transforms and distinct stable
slots 0–11. Candidates are sorted by stable slot, independently of input/query
order. Duplicate slots and quantized transforms fail closed. No world/player
scan or proximity streaming occurs. Each candidate uses a 0.75 m native query;
queries returning over 256 objects are refused. Native spatial query internal
cost is not measured by this output cap. Each of three layouts has two props
and one search site: at most 24 props/12 sites, further constrained by core
MaxActiveInteriors, MaxPropsPerInterior and MaxTickWorkItems. Furnishings are
created synchronously during mission startup, never on live ticks. At most 36
small spatial queries occur during this bounded startup; tick work only checks
up to 12 expiring locks. Native mission/client ordering still needs observation.

Instance identity includes world/build/schema/epoch, native class, quantized
position and orientation, and explicit slot discriminator. Engine query
ambiguity is rejected rather than resolved by pointer/iteration order. The
pilot allows yaw-only buildings and rejects tilted transforms. Layout/history
and allocations are compared against an immutable persisted manifest at every
start; changes never silently reroll. Unknown schema/changed manifest requires
manual migration of a saved copy. No automatic migration, reset or wipe is
implemented, and migration acceptance remains pending.

Supplementary allocations are precommitted at initialization: up to four
single Rag outputs and two Battery9V outputs per epoch; all other sites have
an explicit empty result, including the ransacked history. Allocation is sorted
and deterministic using a server-only configured seed. Each allocation is
consumed at most once in the authored state machine. These pilot quotas are
not calibrated balance, CE world-count integration, or a replacement for the
Loot owner. The shared runtime contract exposes no Loot allocation API, so
cross-module economy reconciliation remains an explicit integration gate.
Visible ordinary loot remains owned by vanilla CE; this module never spawns
extra visible loot or moves/removes baked furniture.

Server start/continue/finish validation binds the exact registered Object,
component index, no parent/proxy substitution, alive/conscious identified
player and empty hands. It uses a stance-derived native head approximation,
1.8 m head range, 2.5 m root range and a nearest view-geometry raycast to a
server-authored anchor. The ray must hit only that prop/component within
0.5 m of the anchor. Client cursor coordinates never authorize a grant.
Action ownership is the exact server ActionData, with a 15-second timeout;
commit also rechecks at least six seconds of native GetTickTime elapsed.
Native cancellation/death/disconnect end or expire the lock without a grant.
These are authored safeguards, not observed native scheduling/race behavior.
Core's real elapsed-time rollback/>300-second guard and OnStop cleanup are
respected; this worker did not modify that guard.

Full inventory detected before reservation leaves the site unconsumed and
uses native MessageStatus feedback. Reservation failure disables further
claims. A null inventory-creation result after reservation quarantines the
site without a retry or ground fallback. Empty, success and post-reservation
failure outcomes have native messages. No generic client command RPC, teleport,
physics/collision disablement or invented gameplay API is used.

## Durable state and honest failure boundary

State lives at `$profile:HollowCountry/interiors_s1_e<Epoch>`. Configuration
is `$profile:HollowCountry/interiors.json`. SchemaVersion=1,
World=`chernarusplus`, Build=`1.30.164289`, Epoch=1–899999 and Seed=1–1000000
are required. Native Candidate Position/Orientation vectors should be authored
from the inspected live object and serialized with native JsonFileLoader;
no unverified JSON vector format or real map coordinates are supplied here.
InitializeNewEpoch defaults false and is the only permission to create a fresh
root. Existing incomplete/corrupt roots are never automatically reinitialized.
Explicitly changing epoch is an operator reset, not routine restart behavior.
Reserved storage-test epochs 900001–900999 are excluded from production config.

Reads reject empty, malformed or >=32768-byte records. Writes serialize and
bound output, refuse existing files and verify canonical readback. The initial
manifest has a backup; recovery never rewinds allocation/depletion from an older
snapshot. Claims use short stable slot filenames and complete SiteId matching.
A reservation marker is written before inventory creation. Partial/unknown
reservation, bad schema/identity, missing completion, or completion without a
reservation quarantines the site. A matching completion restores spent state.
There is no transition from spent/quarantined to available, no drawer refill,
no automatic reissue, and no deletion of player loot. Persistence failures and
quarantines log an operator-visible reason and preserve evidence files.

**Exactly-once durability is NOT established.** Native SaveFile calls FPrint
and CloseFile but exposes no inspected durable-flush contract. FileExist plus
WriteNew is not an exclusive cross-process create. A single running server
is assumed; shared-profile/multiple-writer use is unsupported. A power loss can
lose a reservation after inventory has persisted; deletion/rewind of claim
files or an entire profile cannot be detected without an external trusted
ledger. The native inventory grant and ledger are not one transaction. A crash
between native default-stack creation and SetQuantity(1) also needs injection.
Ambiguous surviving markers sacrifice possible loot to avoid a retry, but that
alone does not prove exactly-once behavior. SearchAccepted therefore returns
false in all normal builds. This is a hard missing capability experiment, not
an accepted transaction design. Do not restore only a manifest backup or
manually remove claim files. Back up/restore the entire epoch and associated
native player/economy state together; validate on a copy before recovery.

Props use inspected native object-spawner flags with native physics and
dynamic persistency (initially nonpersistent). Exact-class nearby objects
cause a slot refusal to avoid recreating potential orphan/native props.
OnStop deletes only this process's owned decorative objects and clears locks;
it never deletes player/generated inventory items. Post-crash native orphan
reconciliation and restart duplication remain runtime gates.

## Source and asset confidence

Private snapshot (never copied to the repository):
`/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289`.
Shared pinned scripts.pbo SHA-256:
`09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a`.
`tests/fixtures/runtime/interiors-inspection.json` records exact inspected
relative file/line and individual script hashes, with runtime_accepted=false.
No purchased source excerpts, models, textures, vanilla dumps or PBOs were added.

Class entries were read in memory from the local installed PBO config.bin RAP
CfgVehicles table, not inferred from class-looking strings. Parent for every
listed entry is HouseNoDestruct. This establishes config/script availability,
not map-instance identity, placement fit, action geometry or runtime creation.

| Installed PBO / class | config.bin class body byte offset |
|---|---:|
| structures_residential / Land_House_1W01 | 118306 |
| structures_furniture / StaticObj_Furniture_case_a | 9081 |
| structures_furniture / StaticObj_Furniture_case_a_open | 9170 |
| structures_furniture / StaticObj_Furniture_case_bedroom_b | 9264 |
| structures_furniture / StaticObj_Furniture_kitchen_chair_a | 12273 |
| structures_furniture / StaticObj_Furniture_PaperBox_01_small_closed | 16185 |
| structures_furniture / StaticObj_Furniture_PaperBox_01_small_ransacked | 16513 |

Installed PBO SHA-256: structures_residential
`f47cbd5f46f3597cc83fef822ed405cbd69de0f160c414b6deb843cc3ff2106a`;
structures_furniture
`e5add5e387d17df70e680e966f1705f55940ba267dcb05e7b76b8013e9d4b448`.
All local references were under
`/mnt/d/SteamLibrary/steamapps/common/DayZServer/addons/`.
The three authored relative layouts and cupboard search points are explicitly
**unmeasured trial coordinates**. No house is claimed verified in-engine.
Production PlacementAccepted remains false. Existing props avoid new assets;
they are not assumed to be collision-safe solely because they are native.

## Exact inspected API locations

Paths below are relative to the private snapshot, not copied source. The
inspection JSON includes per-file hashes and all the following call evidence.

| File:line | Inspected use/limitation |
| `1_Core/proto/EnSystem.c:417` | OpenFile |
| `1_Core/proto/EnSystem.c:425` | ReadFile bounded byte count |
| `1_Core/proto/EnSystem.c:443` | CloseFile |
| `1_Core/proto/EnSystem.c:462` | FPrint |
| `1_Core/proto/EnSystem.c:525` | MakeDirectory |
| `1_Core/proto/EnMath.c:237` | AbsInt |
| `1_Core/proto/EnMath.c:427` | Floor |
| `1_Core/proto/EnMath.c:553` | Min |
| `3_Game/tools/JsonFileLoader.c:42` | SaveFile; FPrint/CloseFile at 63/64, no demonstrated durable flush |
| `3_Game/tools/JsonFileLoader.c:69` | LoadData |
| `3_Game/tools/JsonFileLoader.c:85` | MakeData |
| `3_Game/Global/Game.c:612` | ConfigIsExisting |
| `3_Game/Global/Game.c:703` | CreateObjectEx |
| `3_Game/Global/Game.c:705` | ObjectDelete |
| `3_Game/Global/Game.c:914` | GetTickTime |
| `3_Game/Global/Game.c:930` | GetObjectsAtPosition3D |
| `3_Game/Global/Game.c:934` | GetWorldName string wrapper |
| `3_Game/Entities/Object.c:287` | GetPosition |
| `3_Game/Entities/Object.c:305` | GetOrientation |
| `3_Game/Entities/Object.c:311` | SetOrientation |
| `3_Game/Entities/Object.c:873` | ModelToWorld |
| `3_Game/CE/CentralEconomy.c:28` | ECE_KEEPHEIGHT |
| `3_Game/CE/CentralEconomy.c:30` | ECE_NOLIFETIME |
| `3_Game/CE/CentralEconomy.c:33` | ECE_DYNAMIC_PERSISTENCY explicitly starts without persistence |
| `3_Game/CE/CentralEconomy.c:57` | RF_IGNORE |
| `3_Game/ObjectSpawner.c:48` | native spawner flags |
| `3_Game/ObjectSpawner.c:56` | native spawn/orientation usage |
| `3_Game/Global/DayZPhysics.c:199` | RaycastRV nearest-contact signature |
| `3_Game/Systems/Inventory/Inventory.c:291` | FindFirstFreeLocationForNewEntity |
| `3_Game/Systems/Inventory/Inventory.c:876` | CreateInInventory; null on full, no automatic ground fallback |
| `3_Game/Systems/Inventory/HumanInventory.c:16` | GetEntityInHands |
| `3_Game/Entities/Man.c:81` | GetHumanInventory |
| `3_Game/gameplay.c:368` | PlayerIdentityBase.GetId |
| `4_World/Classes/UserActionsComponent/ActionConstructor.c:27` | RegisterActions |
| `4_World/Entities/ManBase/PlayerBase.c:1695` | SetActions(out TInputActionMap) |
| `4_World/Entities/ManBase/PlayerBase.c:6911` | Message dispatch using native ChatMP |
| `4_World/Entities/ManBase/PlayerBase.c:6924` | MessageStatus |
| `4_World/Classes/UserActionsComponent/ActionTargets.c:115` | ActionTarget; GetObject 142, GetComponentIndex 159, GetCursorHitPos 169 |
| `4_World/Classes/UserActionsComponent/TargetConditionsComponents/CCTCursor.c:32` | server distance differs from client cursor check; custom server anchor validation required |
| `4_World/Classes/UserActionsComponent/ActionBase.c:240` | CreateActionData |
| `4_World/Classes/UserActionsComponent/ActionBase.c:436` | ActionConditionContinue |
| `4_World/Classes/UserActionsComponent/ActionBase.c:1391` | OnStartServer |
| `4_World/Classes/UserActionsComponent/ActionBase.c:1409` | OnEndServer |
| `4_World/Classes/UserActionsComponent/Actions/ActionContinuousBase.c:257` | dispatches OnFinishProgressServer only on server |
| `4_World/Classes/UserActionsComponent/Actions/ActionContinuousBase.c:289` | OnFinishProgressServer |
| `4_World/Classes/UserActionsComponent/ActionComponents/CAContinuousTime.c:9` | continuous action duration constructor |
| `4_World/Classes/UserActionsComponent/Actions/Continuous/ActionMineBushByHand.c:6` | native empty-hand CMD_ACTIONFB_INTERACT use |
| `4_World/Classes/UserActionsComponent/Actions/Continuous/ActionMineBushByHand.c:15` | CCINone |
| `4_World/Static/MiscGameplayFunctions.c:778` | GetPlayerHeadPosition is stance-based approximation, not camera proof |
| `4_World/Entities/ItemBase.c:3319` | SetQuantity, NOT jointly atomic with creation/ledger |
| `4_World/Entities/ItemBase.c:3485` | HasQuantity |
| `4_World/Entities/Building/Residential/Houses/Land_House_1W01.c:1` | native residential script class |

## Red/green execution and native self-tests

Actual command for each scoped run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_interiors_contract.py -v
```

- `interiors-tdd-red.txt`: initial actual red, 12 missing-source errors.
- `interiors-tdd-red-cursor.txt`: 15 tests, one real source-contract failure;
  server action mistakenly required client preview cursor data. Fixed by
  separating client preview before authoritative server feasibility.
- `interiors-tdd-red-startup.txt`: 17 tests, two actual source-contract failures
  for live-tick furnishing and missing native full-inventory/empty feedback.
- `interiors-tdd-red-quota.txt`: 19 tests, one missing authored allocation
  algorithm failure before extracting/implementing the tested quota policy.
- `interiors-tdd-red-hard-gates.txt`: 21 tests, two actual source-contract
  failures for missing server duration/empty-hands check and acceptance reasons.
- `interiors-tdd-green.txt`: final 21 tests passed, exit 0.

Tests execute the actual restricted scalar Enforce function bodies with a small
standard-library Python adapter: quantization, yaw, layout choice, finite quota,
irreversible transitions, quarantine recovery and all seven authority gates.
They also check native hookup, ownership, independent reason logs, bounded I/O,
claim-before-grant and startup ordering. They do not emulate the DayZ engine,
compile Enforce, prove float32 boundary behavior, disk durability, collision,
networking, action timing or inventory atomicity. The synthetic fixture says so.

HCInteriorSelfTests.Run() executes native scalar/identity checks automatically
when this module starts under DIAG_DEVELOPER, even before placement promotion.
In a server Workbench console, explicitly call
`HCInteriorSelfTests.RunStorageProbe(900001)` on a fresh disposable test epoch
to exercise native JSON/file/claim/restart/torn-file behavior. It preserves its
files, refuses a reused probe epoch and creates no inventory or world items.
No native self-test was executed in this worker session; native compilation
is itself still pending. Neither helper constitutes multiplayer acceptance.

The earlier mandatory full discovery command was executed: 218 tests, five
errors in the concurrently authored packaging scope (mod.cpp allowlist,
Invoke-NativeSmoke.ps1, Build-Sign-Verify.ps1, package.sign and verify_handoff).
Those were not changed here. Main owns the final post-stabilization full
regression and package validation; no final full-suite pass is claimed here.

## Remaining hard gates; none completed by offline tests

| Gate / tracked tests | Required observation before acceptance |
|---|---|
| Native compilation / NET-006/008 | Compile all registered 4_World classes and action overrides, including when flags are false; Workbench/Diag logs and normal PBO/signature load. User says main's Wine64 probe is underway; no result received here. |
| Native building/layout fit / T013, INT-001/004/005/010/011 | Identify actual Land_House_1W01 map instance; measure each of the three layouts, floor heights/anchor/component and props; doors/stairs/windows/player/infected navigation against vanilla, no blocked doors. Unsupported/ambiguous instances must refuse cleanly. |
| Persistence/identity / T014, INT-002/003/009, CE-010, NET-005 | Repeat startup/init, graceful stop and injected crashes; no orphan objects/duplicates/reroll, stable IDs, no visible pop-in, unchanged CE loot and full-epoch backup/restore. Unknown schema remains blocked pending a tested controlled migration. |
| Search target, UI and races / T015, INT-006/007/008, NET-001/002/003/007 | Two clients: same site concurrently, retry, malformed/wrong target/component/proxy, wall/floor occlusion, range, full inventory, inventory changing mid-action, held item, death/unconscious/disconnect/cancel, late join and depleted preview. Observe actual native action duration and feedback. |
| Search crash safety / FR-006, NFR-004, INT-003/007, CE-010 | Inject termination/power-loss around every file/quantity/inventory step, corrupt/oversize/partial files and missing records; prove durable reservation across native inventory persistence or introduce an inspected trusted durable mechanism. At-most-once surviving-marker policy is insufficient for exactly-once acceptance. |
| Economy / T012/T015, CE-009/010 | Loot owner supplies a narrow validated allocator or measured CE reconciliation; compare all supplementary/native world/player/storage counts and intended 3–6-player balance. Quotas here are provisional finite escrow, not CE inflation proof. |
| Audio/replication / INT-006, NET-006/007, AUD/PHY requirements | Two simultaneous clients observe furnishings, search outcome, action/rummage audibility and interest/occlusion behavior. Native interact animation does not establish audible rummaging; no invented sound is emitted. |
| Performance/integration / T023/T024, INT-010, NET-004/008 | Measure startup spatial queries, 0/5/10/20-prop sweep where appropriate, frame-time p95/p99, net and save costs at 3–6 players; calibrated budgets, combinations and normal signed server restart. |

Operator logs distinguish configuration/build/map/identity/budget/asset failures,
placement proof pending (collision/nav/replication), search proof pending
(durable commit/CE/two-client), persistence failure and per-slot quarantine.
Settings and both acceptance functions default false. Only explicit
DIAG_DEVELOPER profile trial switches can bypass proof for isolated experiments;
normal builds ignore those trial fields. Diagnostic trials remain experiments,
not permission to promote these pending tests or publish anything.
