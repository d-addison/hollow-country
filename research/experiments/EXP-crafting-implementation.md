# EXP-crafting-implementation — native salvage pilots

Date: 2026-11-16. Target: installed DayZ **1.30.164289**.
Status: authored native implementation plus T0/T1 regressions; **runtime acceptance
PENDING**. No compilation, DayZDiag, normal PBO/client, two-client transaction,
crash-recovery or performance success is claimed by this report. Main's Wine
engine probe is independent and must supply its own evidence.

## Scope and spec/plan linkage

Read AGENTS, full product handoff, active spec/plan/tasks and
`docs/RUNTIME_IMPLEMENTATION_CONTRACT.md`. User explicitly authorized source
implementation before client tests. T016 (audit/pilots), T017 (native salvage),
FR-007, AC-006, CRFT-01 and CRF-001–007 retain their runtime gates. NET-001/002/003/
007 and P8 integration remain pending. Only the assigned Crafting directory,
crafting tests/fixtures and this experiment were changed by this worker.
Shared Core/settings/config/mission, spec/plan and other workers are untouched.

## Audit before pilot selection

Private installed source root:
`/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289`.
Pinned scripts.pbo SHA-256:
`09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a`.
`tests/fixtures/runtime/crafting-native-audit.json` records exact inspected-file
hashes and the audit method. No extracted source/assets are included.

Inspected 235 recipe files; stripped line/block comments before counting **143
active registrations**, all unique. The apparent 204 registration lines include
commented code and are not the active recipe count. Scanned ingredient/result
literals across the corpus, then read native base/manager/action, deletion,
energy and relevant recipes. Generic repair/dynamic results and optional mods
mean this audit is not a proof of every possible engine economy transition.

| Existing recipe/surface | Decision |
| --- | --- |
| CraftRag, CraftBurlapStrips | Existing cloth/rag and burlap conversion; do not duplicate |
| CraftMetalWire | BarbedWire + Pliers -> MetalWire already exists; select CableReel instead |
| CraftGhillieAttachment / DeCraftGhillieAttachment | Existing Netting + BurlapStrip -> GhillieAtt_Tan and lossy reversal; reuse wrap |
| Other ghillie, courier/improvised/leather bag dismantling | Existing salvage; do not add competing copies |
| CraftCamoNetShelter | Source exists, registration commented; existence alone does not make a usable recipe |
| DeCraftCamoNetShelter | Registered, returns stick and CamoNet; does not convert netting into a camo net |
| CraftLeatherBelt | Current build consumes LizardPelt + kit quantity, outputs LeatherBelt_Lizard; it does not use TannedLeather |
| CamoNet / CableReel / LeatherBelt_ColorBase | No matching selected input/tool/output salvage transformation registered |

Camo-net feasibility: reuse **Netting**, then native **GhillieAtt_Tan** with native
burlap strips. This avoids new models/attachments or claims of green camo visual
inheritance. Rifle attachment compatibility/visibility is still CRF-001/007 in
game. The source path is feasible to author; actual appearance is not observed.

## Authored pilots and eligibility

All yields are conservative pilot choices, not measured mass/balance promises.
Each consumes **one whole source object** (not one unit of a hypothetical source
stack) and produces **one result stack**. Fixed quantity, no soft skills/random
bonus, no source replacement/color/property transfer or hidden extra outputs.

| Recipe | Tool | Native output | Tool health cost | Time |
| --- | --- | --- | --- | --- |
| HCSalvageCamoNet: CamoNet | KitchenKnife | Netting x2 | 5 absolute HP | 2 units = 8 seconds |
| HCSalvageCableReel: CableReel | Pliers | MetalWire x1 | 5 absolute HP | 8 seconds |
| HCSalvageLeatherBelt: LeatherBelt_ColorBase | KitchenKnife | TannedLeather x1 | 3 absolute HP | 8 seconds |

Base initialization sets native quantity/health/destroy fields explicitly. Result
health inherits source normalized health then loses another 25%. Tool health must
be **strictly greater** than its cost. Ruined/deletion-pending inputs or tools,
null/same item, wrong material/tool, dead/unconscious actor, worn/attached items,
items with attachments/cargo and connected/feeding cable reels are rejected.
Belt colors inherit through the native class base; tool classname must match
exactly. Detach the belt and put it in hands/cargo; empty it before salvage.
No ruined-gear salvage is offered without a separately justified recipe.

Both items must have the acting player as hierarchy root, one in hands via
native CheckRecipe. Ground/shared/corpse materials are conservatively excluded;
this tightens vanilla's close-enough/not-owned-by-another-live-player checks.
Types are checked again in CanDo because RecipeBase.CheckRecipe alone does not
check ingredient class membership. Preserve super.CanDo attachment checks.

## Integration, authority and safety

`HCRecipeRegistration.c` extends native PluginRecipesManager.RegisterRecipies
(spelling verified), calls super, then registers all three in fixed order on
**clients and server**, before native cache creation. It never registers from
module OnStart and never conditionally removes recipes based on profile state.

`HCCraftingModule` registers through HCModuleRegistry. On enabled server start,
read-only native checks validate definitions, registrations, config existence,
output scope/stack limits and the synchronous completion guard. If any fails,
Crafting remains disabled. These checks are authored but **not yet executed in
the engine**. They create no gameplay entities. Idle work is empty; no timers,
world/inventory scans, RPC, JSON state or custom persistence. A saturating recipe
counter logs only on stop. Native animation/action sound is reused; no new noise
broadcast or claim of audibility to two clients.

Server checks read `HCServer.Get().GetSettings().EnableCrafting` in 4_World and
also require the module to be started/validated. The shipped shared setting is
default false. Missing settings/start/validation fail closed. Clients preview
without checking their default-false profile settings. Consequently an off server
may still show the client recipe option; server continuation/completion rejects
it. This is intentional until an authorized settings replication design exists.
Client code cannot commit: our PerformRecipe returns before native mutation.

Native ActionWorldCraft continuation and finish -> PluginRecipesManager server
sanity -> RecipeBase.CheckRecipe/CanDo run again at completion. No changes occur
in our preview, selection, cancellation or tick paths. Death/unconsciousness,
item transfer/drop, disablement, exhausted tool or pending deletion therefore
reject subsequent completion checks. Normal engine action cancellation and
network juncture semantics are inherited, not reimplemented.

Per native recipe instance, a synchronous guard rejects reentrant completion
before spawning and releases after native completion. Native self-check exercises
first entry, nested rejection, release and next entry. Following completion,
IsSetForDeletion rejects the consumed source while native deletion is queued.
The same ownership/deletion checks cover both source and tool. This is **not**
a thread lock, global transaction ledger, persistent replay ID or recovery claim.

## Exact native transaction limits

RecipeBase order is **SpawnItems -> ApplyModificationsResults ->
ApplyModificationsIngredients -> Do -> DeleleIngredientsPass**. Destroy flags
queue deletion in the recipe's array; actual item.Delete is called only by the
last pass, and EntityAI.Delete marks pending then queues engine deletion for the
next frame. Source is therefore still available when our Do reads its condition.
The native material/tool changes are delegated to these exact native methods.

For m_ResultToInventory=-1 the native code tries CreateInInventory, then
SpawnEntityOnGroundRaycastDispersed on failure. Full inventory can deliver the
single stack on the ground: there is no new teleport, forced slot swap, retry or
client inventory mutation. If both native spawns fail/null, our result-ready flag
prevents **all** ingredient consumption/tool wear and Do. The native result pass
already skips null outputs. Using one result stack avoids partial multi-output
salvage. This is an authored failure guard, not an observed spawn-failure test.

**No offline atomicity claim:** outputs exist before source consumption, tool wear
and deferred deletion. The installed script offers no all-or-nothing rollback,
write-ahead journal or crash-safe inventory transaction. A server/script fault
between spawn/consume/delete may leave inconsistent persisted outcomes. Our guard
cannot repair an interrupted engine call or a process crash. Do does not undo or
retry a partial native commit. Death/disconnect during or after a synchronous
native call, inventory reservation release around completion, actual ground
placement and races require two-client failure injection. Do not enable in
production until CRF/NET tests below establish acceptable behavior; if native
crash semantics fail, retain default-off rather than promise atomic recovery.

## Exact installed API references (paths relative to snapshot root)

| File and lines | Inspected contract/use |
| --- | --- |
| 4_World/Classes/Recipes/Recipes/PluginRecipesManagerBase.c:10,14 | RegisterRecipe prototype; RegisterRecipies hook |
| 4_World/Plugins/PluginBase/PluginRecipesManager.c:52–56,180,296–347,407–456,660–663 | Registration/cache order; server continuation/completion; sanity distance/ownership; registration IDs |
| 4_World/Classes/Recipes/RecipeBase.c:67–98,159–172,198–202 | Constructor Init, time conversion, typed ingredients, result declaration |
| same RecipeBase.c:215–265,268–358 | Native inventory/ground spawn fallback; quantity and condition application |
| same RecipeBase.c:362–426,429–502,521–561 | Delete pass, ingredient mutations/conditions, CheckRecipe/PerformRecipe ordering, CanDo attachments |
| 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWorldCraft.c:12–17,48–52,77–110,173–194 | Native CAContinuousCraft; target/item continuation; server finish only |
| 4_World/Classes/UserActionsComponent/ActionBase.c:1053–1107,1167–1229 | Inventory reservations and network junctures inherited; not proof of atomicity |
| 3_Game/Entities/EntityAI.c:779–783,812–815,882,3409 | Deferred delete flag, IsSetForDeletion, root owner, GetCompEM |
| 3_Game/Entities/Object.c:511,517,994–1015,1219 | IsKindOf/IsAlive, health APIs, IsRuined |
| 3_Game/Systems/Inventory/Inventory.c:138,205,410; Cargo.c:28 | Cargo, attachments, location; cargo item count |
| 3_Game/tools/Component/ComponentEnergyManager.c:905,1188 | IsPlugged, GetPluggedDevicesCount |
| 4_World/Entities/ItemBase/CableReel.c:25–35,57–70,113–123 | Reel connection/inventory behavior and unplug semantics |
| 4_World/Entities/ItemBase/CamoNet.c:1–11 | Existing net class/base/tent attach actions |
| 4_World/Entities/ItemBase/Clothing/LeatherBelt_ColorBase.c:1–26 | Belt base and color subclasses, attachment/cargo behavior |
| 4_World/Entities/ManBase/PlayerBase.c:3925 | IsUnconscious override |
| 4_World/Entities/ItemBase.c:3319–3330,3439–3488 | Quantity setter no-op for singleton; stack/quantity fallback |
| 3_Game/Global/Game.c:524,539,612; 3_Game/constants.c:675 | Native config queries, 4-second crafting time unit |
| 4_World/Classes/Recipes/Recipes/CraftGhillieAttachment.c:15–51; DeCraftGhillieAttachment.c:27–96 | Existing wrap inputs and lossy return quantities |
| 4_World/Classes/Recipes/Recipes/CraftMetalWire.c:27–52; CraftRag.c:68–104 | Existing wire recovery; generic rag eligibility/yield |
| 4_World/Classes/Recipes/Recipes/CraftLeatherBelt.c:26–49 | LizardPelt source, 25 kit quantity, source-condition inheritance |

## TDD/SDD/BDD evidence and material accounting

`tests/unit/test_crafting_contract.py` uses standard-library unittest. Definitions
are read from the actual authored Configure calls; the test does not contain a
second executable gameplay implementation. Source checks enforce delegation,
server/client boundaries, deletion guard and single-output failure guard.
Synthetic token vectors separately track mesh/cloth/wire/hide. They are explicit
review assumptions, **not measured DayZ mass**. Tests reject extra yields, free
products and cross-material conversion, and enumerate reachable combinations of
salvage plus native ghillie forward/reverse and lizard-belt boundaries. Inherited
lizard belt is normalized to the allowed belt base. Every transition has a
nonincreasing typed potential, so every sequence in that scoped graph does too.
Native wrap reversal loses one burlap strip. No selected output has an inspected
native route regenerating CamoNet/CableReel/belt from those salvage outputs.

Condition tests require the actual authored factor to be between zero and one
and exercise repeated degradation/tool costs. They do not execute native health,
repair actions, stack splitting or inherited condition replication. Full native
and compatibility graph/balance acceptance remains CRF-006, not an offline PASS.
Main owns the crafting BDD binding and active task/spec updates.

Actual commands/evidence:

- Initial red: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_crafting_contract.py -v` -> 9 tests, **8 failures**, exit 1; `crafting-tdd-red.txt`.
- Deferred-deletion regression red: same command -> 10 tests, **1 failure** (missing IsSetForDeletion), exit 1; `crafting-tdd-deletion-red.txt`.
- Completion reentry red: same command -> 11 tests, **1 failure** (missing TryEnter), exit 1; `crafting-tdd-reentry-red.txt`.
- Final green: same scoped command -> **11 tests passed**, exit 0; `crafting-tdd-green.txt`.
- Full suite: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v` -> **244 tests, 1 failure**, exit 1; `crafting-regression.txt`. The sole failure was `test_package.PackageBehavior.test_windows_python_preflight_is_explicit` (packaging PowerShell missing `Get-Command -Name $Python` during the snapshot). That file is outside this worker scope and was not changed. All Crafting tests passed.
- `git diff --check` passed at the validation snapshot. The original-source native self-tests remain authored/unexecuted, and no compile or runtime acceptance is inferred.

## Pending engine protocol / rollback

Every entry is PENDING; no fixture is runtime evidence. Exact steps are retained
in `crafting-contract.json` under pending_scenarios, mapping CRF-001–007 and NET.
Run Diag then normal PBO server with identical client/server source, all flags off
first, then experimental EnableCrafting on a disposable save. Capture class/recipe
IDs, config checks and native self-test logs, source/PBO/build hashes, item IDs,
quantities/condition before/after and ground result location. Test both ingredient
orders, belt colors/attachments, inputs at quality/wear boundaries, connected reel,
max/split stacks, cancel 0/50/99%, death/unconsciousness, toggle mid-action, full
inventory and force null spawn. Repeat completion before delete and after pending
mark. Two clients: attempt same-source completion, owner transfer/drop/steal,
disconnect/reconnect, latency/replay/forged action. Kill server at spawn/consume/
delete boundaries; verify actual persisted source/result/tool count after restart.
Verify native wrap on compatible rifle and native audio with both clients.

Profile idle and crafting bursts at 3–6 players; existing budgets are provisional.
Do not promote T2–T5/AC-006 based on these source/algebra tests. Rollback: disable
EnableCrafting and restart; registration stays identical on both peers and vanilla
recipes remain registered. No custom crafting save/schema migration is introduced.
Use Core/package backup policy for any disposable save changed by native crafts.
