# EXP-full-item-scope-decisions

Date: 2026-11-16. Decision review of installed DayZ 1.30.164289 source
and the actual native035 config export. Follow-up implements the bounded
EXT-CUT-TOOLS source patch below. No native processes, balance changes, new
assets or acceptance promotions were performed by this worker.
This report is ignored local research, not a release document.

## Decision and meaning of coverage

CRFT-01 and SPECIFICATION section 5 require broad plausible utility across the
item population. The three authored salvage chains are a starting implementation,
not the audit denominator or completion boundary. FR-007, T016/T017 and
CRF-001–007 remain applicable. The earlier three-pilot wording in AC-006 does not
replace the user's later full-audit instruction.

The full available census is sufficient to choose a native-first implementation
sequence. It is not sufficient to declare every config object an inventory item,
every source-registered recipe usable, every possible repair pair valid, or all
234 recipes accepted. Retain existing native functionality; extend only a
demonstrated missing use. “Implementation-ready” below means exact source API,
type identities and mutation strategy are available to author a scoped change.
It does not mean a yield, duration, wear schedule or multiplayer behavior is
accepted. No new numerical balance settings are selected by this report.

The generated annex retains all 7,389 config classes, all 234 recipe declarations
and all 460 observed ActionBase-path classes, including hidden definitions,
disabled/unregistered recipes and unresolved observations. UNKNOWN is a decision
classification, not an omission or a successful gameplay result.

## Evidence inputs and boundaries

Native035 is the strict admitted 15-chunk, four-root export: 7,392 advertised
children, 7,389 class rows and three non-class children. The full workbook keeps
CfgVehicles (6,789), CfgWeapons (215), CfgMagazines (131) and CfgAmmo (254).
CfgVehicles is a config root, not proof that its buildings, actors or base
definitions are usable inventory objects. A scope=0 base definition can still
explain inheritance and literal recipe targets; retain it for that purpose.

Source manifest `b7ed9fa47f1285f8aa436c18fc9c8681a7e017b2441a7923c8eae0f2a019af33`
covers 3,056 .c/.C files, 13,952,124 bytes, with 3,055 UTF-8 and one explicit
cp1252 decode. The crafting and action inventories share that exact manifest.
Source paths below are relative to the private installed-source root:
`/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289`.
The generated annex includes input artifact hashes and per-file anchor hashes.

The recipe census has 143 active source registrations, 74 comment-disabled
registrations and 17 declarations with no observed registration. Its 2,344
literal references resolve to 2,289 config references and 55 unresolved references;
no ambiguous literal-config matches were reported. A reference is not a
class-specific eligibility proof. In particular, Inventory_Base targets require
additional config and CanDo evaluation. All 234 have unresolved method semantics.

The action census retains 2,118 calls: 1,272 AddAction, 38 RemoveAction,
465 SetActions and 343 constructor Insert candidates; 22 observations are
comment-disabled. R2 records 32,603 parsed method/function declarations,
including 365 global functions, and
301 named callbacks (165 attachment, 120 cooking, 10 consume, six repair).
There are 399 unresolved call observations and 473 unresolved ancestries.
Constructor receivers, global/player actions and commented calls must not be
turned into per-item registrations. Runtime controls are inventoried by method;
their execution, branch attachment, overload resolution and inherited dispatch
are not established by this census.

R2 output is 30,523,514 bytes; charged analysis work is 2,205,483. The unchanged
earlier checkpoint remains preserved. Accepted artifacts are under
`/home/david/.cache/hollow-country/action-audit-full-r2-20261116`:

| Artifact | SHA-256 |
| --- | --- |
| action-census.json | ad114537a1b83d837fb04089e3d441664ac67294f004a68eacfdedb1c30f643e |
| provenance.json | 5cc3f09f2a62129c7fdbc64d8d8095f5d53836fdb9e156992722004f0eb201a4 |
| verification.json | d28cf944bcca2a7e6af13d227dee0e6409c938b78187bbb2dfc1765a451cc59d |

Global function observations include weapon_utils.c's four weapon helpers and
ItemBase.c:4976 SetupSpawnedItem. They are retained as global declarations,
not falsely assigned to an item or promoted to effective action registration.

Concrete adapter limitation found in this review: PlayerBase.c:1697 onward uses
the native two-argument AddAction(ActionOpenDoors, InputActionMap) form. The
frozen single-argument adapter retains such calls as argument_arity /
dynamic_expression. They are unresolved by this adapter, not necessarily dynamic
in the native source. FishingRod_Base.c:378 also retains ActionToggleFishing as
a missing-or-dynamic identifier; do not synthesize its implementation. These
limitations are reported to the coordinator; frozen source is unchanged here.

## Native integration contract: preserve identity and condition

| Surface | Installed source anchor | Implication for implementation |
| --- | --- | --- |
| Registered native recipe lifecycle | 4_World/Classes/Recipes/RecipeBase.c:479,521 | CheckRecipe/CanDo and condition checks run before mutation; these are not a durable transaction protocol. |
| Mutation order | RecipeBase.c:532–539 | SpawnItems -> ApplyModificationsResults -> ApplyModificationsIngredients -> Do -> DeleleIngredientsPass. A Do override can replace apparent Init field semantics. |
| Native delivery | RecipeBase.c:215 | Native inventory/ground placement exists; allocation/placement failure and full inventory still require real tests. |
| Result condition and property transfer | RecipeBase.c:323,344 | InheritsHealth chooses a source/average; ReplacesIngredient can transfer variables and attachments. Never infer conservation from AddResult alone. |
| Server commit route | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWorldCraft.c:170 and 4_World/Plugins/PluginBase/PluginRecipesManager.c:317 | Reuse OnFinishProgressServer -> PerformRecipeServer and native sanity checks, rather than a client-owned inventory mutation or separate crafting UI. |
| In-place repair | 4_World/Plugins/PluginBase/PluginRepairing.c:3,29,92 | Repair mutates the actual target, consumes the actual kit quantity/config cost and checks allowed repair-kit types. Preserve those objects; do not replace repaired items with new pristine copies. |
| Property-copy utility | 4_World/Static/MiscGameplayFunctions.c:271 | TransferItemProperties includes agents, variables and health by default. Copying health alone does not preserve contamination/state; copying quantity across unlike items can also be wrong. |
| Item action maps | 4_World/Entities/ItemBase.c:222,246,255,295 | Initialization caches type action maps. AddAction/RemoveAction source observations alone do not establish effective ordered inherited maps. |
| Existing mod salvage contract | mods/HollowCountry/scripts/4_World/Crafting/HCSalvageRecipe.c | Current authored wrappers preserve the actual tool object, reject attached/nonempty/ruined/deleting material, consume the material, inherit/degrade source health and guard synchronous reentry. This is not crash-safe atomicity. |

Tool identity means the same tool entity remains after wear; do not spawn a
replacement, refill its quantity, clear its agents or discard attachments.
Material identity means preserve relevant state for in-place repair, or explicitly
justify the state transfer/loss when a destructive conversion makes a new type.
No new implementation should blindly clone the entire source state into a
different output type. Require CanDo and completion-time authority checks, empty
container/attachment checks, placement failure behavior and cycle invariants.

## Supported native paths ready to reuse, not duplicate

In this table a concrete KitchenKnife or HandSaw instance is one exact accepted
native tool example, not a proposal to replace a recipe's complete native tool
set. All named outputs and concrete examples are checked against the admitted
config inventory. Recipe paths abbreviate
`4_World/Classes/Recipes/Recipes/`; the complete declarations, alternate inputs,
source status and line anchors are retained for every recipe in the annex.

| Domain / native recipe | Exact existing type path | Condition / identity behavior inspected | Decision |
| --- | --- | --- | --- |
| Cloth: CraftBurlapStrips | BurlapSack + KitchenKnife -> BurlapStrip | Init:23,36,65,73,78 consumes sack, retains/wears tool, inherits sack health. | Reuse registered native conversion; no parallel duplicate. |
| Cloth: CraftRag | Inventory_Base with positive ragQuantity + KitchenKnife -> Rag | Init:67 uses InsertIngredientEx with Rags_craft; CanDo:90 checks config and attachment context; Do:97 drops contents and splits output stacks. Result inherits source health. | Reuse config-driven eligibility; do not call every clothing item a rag source. Preserve contamination/material checks; no automatic extra recipe for every subclass. |
| Cordage: CraftRagRope | Rag + Rag -> Rope | Init:27,36,46; both are material stacks, not a tool. Result health averages inputs. | Reuse; preserve native quantity checks and cycle accounting. |
| Cordage: CraftGutsRope | Guts + KitchenKnife -> Rope | Init:27,39,65,73,78 consumes guts, retains/wears tool; native result inheritance is an input average. | Reuse native rule; do not claim output condition depends only on guts. |
| Wrap: CraftGhillieAttachment | Netting + BurlapStrip -> GhillieAtt_Tan | Init:27,36,46,51; two consumed material quantities, averaged health. | Existing-model camouflage route; exact rifle attachment compatibility/visible result remains a client test. |
| Wrap recovery: DeCraftGhillieAttachment | GhillieAtt_Tan (GhillieAtt_ColorBase target) + KitchenKnife -> Netting + BurlapStrip | Init:27,41,69,78 onward; source destroyed, knife retained/worn, result health inherits source. | Reuse native loss/condition rules; no green/black/moss appearance promise. |
| Wire: CraftMetalWire | BarbedWire + Pliers -> MetalWire | Init:27,36,46,51; CanDo:71 denies attached wire; material health inherited, pliers retained. | Existing native recovery; adding the same pair would duplicate it. |
| Storage: CraftCourierBag / DeCraftCourierBag | BurlapSack + Rope -> CourierBag; CourierBag + KitchenKnife -> BurlapSack + Rope | Forward Init:27,36,47,52 averages materials; reverse Init:27,41,78,90 inherits bag health for recovered materials; knife is retained/worn. | Reuse; empty-cargo and current native CanDo behavior need full observation rather than treating AddResult as a transaction proof. |
| Fishing: DeCraftFishingRod | ImprovisedFishingRod + KitchenKnife -> LongWoodenStick + Rope | Init:27,40,77,89; both outputs inherit source health, knife retained/worn. | Existing native reclamation, not a missing new recipe. |
| Wood: CraftWoodenPlank | WoodenLog + HandSaw -> WoodenPlank | Init literals retained in complete recipe annex; native tool/source wear and quantity fields remain authoritative. | Reuse; do not invent alternate plank yield or new geometry. |
| Wood: SawWoodenLog / SplitFirewood | WoodenLog + HandSaw -> Firewood; Firewood + HandSaw -> WoodenStick | Three AddResult(Firewood) calls in SawWoodenLog are separate declarations, not deduplicated into one result stack. | Reuse native paths; graph review must retain multiplicity. |
| Leather: CraftLeatherBelt | LizardPelt + LeatherSewingKit -> LeatherBelt_Lizard | Init:26,34,44,49 consumes pelt, retains kit, inherits pelt health. | Reuse exact current build; do not substitute TannedLeather based on older recipes. |
| Storage recovery: DeCraftWoodenCrate | WoodenCrate + Crowbar -> WoodenPlank + Nail | CanDo:74 rejects nonempty inventory; Do:86 branches on crate health and overrides initial result health/quantities. | Existing native salvage. Do not infer final condition from Init's tool-index inheritance fields; do not copy its random tables as newly approved HC balance. |
| In-place repair: RepairPlanks | WoodenPlank + WoodenCrate or SeaChest -> same existing container | Do:64 delegates PluginRepairing.Repair; no AddResult. | Reuse; never replace the container and lose cargo/state. Per-target config/health eligibility remains native. |
| In-place repair: RepairWithSewingKit / RepairWithLeatherSewingKit | SewingKit or LeatherSewingKit + compatible Inventory_Base -> same existing target | CanDo:61/66 requires PluginRepairing.CanRepair and CanBeRepairedByCrafting; Do:77 calls Repair. | Config-driven existing system, not blanket permission to sew every object. Actual concrete kit/target compatibility needs verified config arrays. |
| In-place repair: RepairElectric / RepairEpoxy | ElectronicRepairKit + compatible Inventory_Base, or EpoxyPutty + compatible Inventory_Base/DefaultWeapon -> same target | CanDo and Do delegate PluginRepairing; both ingredient identities retained. | Native extension seam exists; no invented electronic component decomposition/refill. |
| In-place repair: CleanWeapon | WeaponCleaningKit + compatible DefaultWeapon/DefaultMagazine/ItemSuppressor -> same target | CanDo:47 uses CanRepair; Do:56 uses Repair. | Reuse; no pristine replacement weapon, ammo, attachments or suppressor. |
| Specialized repair: RepairWithPliers | Pliers + Chainmail / Chainmail_Coif / Chainmail_Leggings / WitchHoodCoif_ColorBase -> same target | CanDo:64 returns true; Do directly transfers normalized health cost/benefit through the actual pliers/target, rather than generic repair-kit policy. | Separate reviewed native special case; do not claim every repair uses PluginRepairing or infer its tool policy from recipe name alone. |

Three already-authored HC transformations are also source-ready: CamoNet +
KitchenKnife -> Netting; CableReel + Pliers -> MetalWire; an empty loose
LeatherBelt_Beige (LeatherBelt_ColorBase input) + KitchenKnife -> TannedLeather.
They are not additional vanilla recipes and they do not qualify the whole CRFT
scope. Their existing source-selected quantities/wear remain provisional, not
reapproved by this report. Wire salvage must reject an active/connected reel.

## Relevant utility that the recipe list alone misses

Rope's SetActions in `4_World/Entities/ItemBase/Gear/Crafting/crafting.c:58–69`
adds ActionCraftRopeBelt; `Clothing/RopeBelt.c:3–7` adds
ActionDeCraftRopeBelt. Both continuous action classes have their server completion
method in `4_World/Classes/UserActionsComponent/Actions/Continuous/` at :37/:42.
They spawn RopeBelt/Rope and call MiscGameplayFunctions.TransferItemProperties.
Deconstruction requires no attachments and CCINonRuined. Preserve that actual
native route instead of adding a second RecipeBase conversion. Deletion/placement
and state-transfer ordering are source facts, not accepted crash safety.

The item displayed as a tarp uses the observed native type **Fabric**, not a
guessed Tarp classname. Its SetActions in crafting.c:109–117 adds
ActionRepairTentPart, ActionAttachToConstruction and ActionRepairCarChassis.
ActionRepairTentPart.c:55,107 requires a TentBase target and a non-body damaged
component; completion uses the source Fabric's health level for repaired-zone
health and consumes its quantity. TentBase.c:88 expressly returns false from
CanBeRepairedByCrafting, so a generic packed-tent sewing recipe is not a substitute.
ActionRepairCarChassis.c:30,88 specializes Fabric/WoodenPlank repairs for native
BackWood/BackTarp selections. Reuse observed selections only; do not invent a
damage zone or geometry. Full targeting/server validation still needs a native
and two-client exercise; source existence is not acceptance of arbitrary RPC data.

Consumption/cooking/attachment hooks are existing behavior to preserve, not new
manufacturing recipes: Edible_Base.c:95,103,129,134,630,697; Cooking/Cooking.c:44,
117,184; EntityAI EEItemAttached/Detached and ItemBase attachment checks. Do not
reset food stage, agents, temperature, energy, ammo, contents or ownership through
a convenience replacement object. The action/callback census keeps all declaring
owners, including service classes and non-item actors; these are not all items.

## Supported extension shortlist and remaining decisions

| ID | Proposed scope / exact types | Readiness and reason |
| --- | --- | --- |
| EXT-CUT-TOOLS | All 36 exact admitted native cloth/net cutting alternatives listed below for HC CamoNet -> Netting and LeatherBelt_ColorBase -> TannedLeather. | Scoped source patch authored and offline-tested below; native compilation/crafting remain pending. Preserve each actual tool entity and recheck its health/identity at completion. Existing result/condition policy, wear, duration and yield are unchanged. Tool health must strictly exceed wear. No wildcard Inventory_Base admission or guessed knife inheritance. |
| EXT-NATIVE-CHAIN-COVERAGE | Qualify the complete existing cloth/cordage/wrap, bag/fishing recovery, wire, wood and repair paths above; derive additional cases from the exhaustive register rather than limiting work to three chains. | Ready to implement bounded tests/diagnostics using these exact native types. This is reuse and broad qualification, not new duplicate registrations or an assertion that all recipes are safe. Preserve native tool/entity state and direction-specific result health. |
| EXT-REPAIR-POLICY | Any intended change for SewingKit, LeatherSewingKit, DuctTape, ElectronicRepairKit, EpoxyPutty or WeaponCleaningKit acting on a specific admitted target. | Native in-place API is ready. Per-target extension is NOT yet ready: requires verified repairableWithKits/repairCosts arrays, repairKitType, target/zone health, pristine rules and CanBeRepairedByCrafting. Retain current native behavior while those pairs remain UNKNOWN. No universal kit compatibility or pristine-repair upgrade. |
| EXT-LEATHER-RECOVERY | Possible LeatherGloves_Beige, LeatherHat_Beige, LeatherJacket_Beige or LeatherPants_Beige + KitchenKnife -> TannedLeather, following the existing belt mechanism. | Exact config and script types exist; plausible material mapping is a design inference. HOLD a new recipe until material/yield/quantity conservation and retained-container checks are specified and the full recipe/action census has ruled out a competing effective route. Names alone do not approve material conversion. No arbitrary per-garment yields are invented. |
| EXT-MECHANICAL-ELECTRICAL | Additional containers/devices -> recovered fasteners, wire or components. | HOLD unspecific recipes. CableReel -> MetalWire is already authored; BarbedWire -> MetalWire already exists natively. Battery9V exists, but that does not prove a viable MetalWire output, neutralized energy, safe contents or physical salvage yield. Never derive components from mass/name alone. |
| EXT-CAMO-VISUALS | CamoNet -> existing Netting -> native GhillieAtt_Tan chain. | Existing-asset route is authorable; visible attachment support per rifle and state retention still need actual clients. Custom green wraps, color inheritance, new models/materials or new slots are not implementation-ready from this evidence. |
| EXT-RUINED-SALVAGE | Deliberate recovery from ruined equipment, rather than normal repair. | HOLD broad enablement. Native recipes often deny damage level 4 before Do; a ruined branch inside Do alone does not prove reachability. Specify eligibility and an irreversible justified salvage loss; do not repair a ruined source by manufacturing a pristine replacement. |
| EXT-LEGACY-RECIPES | The 74 disabled and 17 unregistered native recipe declarations. | HOLD automatic registration. Inspect each exact declaration, config output, superseding native action, CanDo/Do and possible cycle before enabling. Their complete individual rows remain in the annex. Existing output geometry/implementation is not guaranteed by a class-name literal. |

Full item coverage does not require assigning a novel recipe to all 7,389 config
classes. It requires keeping every class in the decision register, distinguishing
non-item definitions and unknown eligibility, preserving existing native uses,
and recording a justified decision for each proposed extension. No source-name
join between script owners and config class names is promoted to runtime identity.

## Qualification work retained across the full scope

1. Resolve the native config arrays and eligibility needed by actual shortlisted
   repair/material targets. Native035 intentionally labels array elements
   unverified; its 29,606 unknown/variant field observations cannot become approved
   repair pairs, attachment compatibility or crafting quantities.
2. For every conversion selected from the full register, inspect Init, inherited
   behavior, CanDo and Do together. Preserve result multiplicity and distinguish
   a new output from mutation of an existing ingredient. DeCraftWoodenCrate is a
   concrete example where Do supersedes the initial field values.
3. Verify a recipe/material graph with native quantities, conditions, kit
   depletion and reverse edges; do not claim that the literal-link graph proves
   net conservation. Include variable/config yields and inherited recipes.
4. Execute CRF-001–007: wrong/ruined/exhausted tool, ownership/attachment/cargo,
   interrupted/dead actor, two-client competing requests, full inventory,
   disconnect, deletion pending and duplicate completion. Test the actual same
   tool and target handles before/after; do not check type names alone.
5. Preserve the distinction between a Wine server compilation/startup check,
   actual diagnostic inventory mutation and normal signed PBO/client acceptance.
   Earlier crafting startup admission is evidence for those definitions only;
   no actual craft, all-234 completion, two-client transaction or crash recovery
   follows from it. Runtime performance budgets remain unmeasured here.

The user authorized the EXT-CUT-TOOLS source follow-up below. Other source
changes or new balance choices do not follow automatically from this report.
The native reuse table guides scoped implementation; the explicit
HOLD/UNKNOWN register prevents an unsupported blanket “full crafting complete”.

## EXT-CUT-TOOLS scoped implementation and TDD

The complete union of literal tools in CraftRag (36 unique), CraftBurlapStrips
(33), DeCraftGhillieAttachment (32) and DeCraftCourierBag (32) contains these
36 exact classes, all present in the admitted CfgVehicles inventory:

```
AK_Bayonet Akinaka BoneKnife BrickTrowel Cleaver CombatKnife Crowbar
CrudeMachete DonerKnife FangeKnife FarmingHoe FieldShovel FirefighterAxe
Hacksaw HandSaw Hatchet HayHook HuntingKnife Iceaxe Jambiya KitchenKnife
KukriKnife M9A1_Bayonet Machete Mosin_Bayonet OrientalMachete Pickaxe
SKS_Bayonet Scimitar Screwdriver Shovel Sickle SteakKnife StoneKnife Sword WoodAxe
```

These are observed cutting alternatives, including saws, axes and digging tools;
the set is not narrowed arbitrarily to knives. The duplicated native BrickTrowel
literal is deduplicated. The malformed `Jambiya;` from another recipe is excluded;
valid Jambiya is independently present in the inspected cutting recipes.
Source anchors under `4_World/Classes/Recipes/Recipes/` are CraftRag.c:23–59,
CraftBurlapStrips.c:31–63, DeCraftGhillieAttachment.c:36–67 and
DeCraftCourierBag.c:36–67. RecipeBase.c:159,164 supports repeated alternatives
in the same ingredient slot. RecipeBase.c:373–426 applies health deltas to
the original ingredient, with destruction and quantity behavior separately set.

HCSalvageTools defines one bounded exact-name policy used by registration,
CanDo and cached startup admission. Registration checks every alternative's
native config existence and exact cached array, rejecting missing, extra,
duplicate or reordered entries. Pliers remains exclusive to CableReel salvage.
The existing KitchenKnife recipe argument selects the cutting family; no
settings, recipe count/order or shared module interface is changed.

The existing completion wrapper passes the original ingredient array, player
and tool handle to native mutation only after output readiness. Destroy=false,
negative health wear and zero quantity delta retain the tool entity; no new
tool is spawned or refilled. Output health inheritance, quantities and source
consumption remain unchanged. Synthetic adapters observe authored delegation
and configured mutation fields; they do not emulate or prove native mutation.

Actual initial RED: `python3 -B -m unittest tests.unit.test_salvage_tools -v`
ran six tests with five failures and one pass against the original single-tool
source. Actual Configure omitted 35 tools and CanDo rejected AK_Bayonet;
three other failures identified the missing policy methods. Follow-up adapter
binding and fixture errors were test harness issues, not engine observations.

GREEN: `python3 -B -m unittest tests.unit.test_salvage_tools
tests.unit.test_crafting_completion tests.unit.test_crafting_contract -v`
passes 33 tests: eight new behavioral tests plus 25 existing tests. New tests
execute the actual authored Configure, CanDo, ownership guard, tool policy,
startup admission and completion delegation bodies using explicit synthetic
native boundaries. The obsolete single-tool source-text assertion was removed;
no new source-text assertion establishes acceptance.

Pending: compile this expanded set, then observe actual tool identity/health,
outputs/material consumption, failure/reentry and two-client contention with
the normal server/PBO. No production enablement or broad crafting completion
is established by these offline results.

## Next batch decision: native maintenance across the whole admitted population

This follow-up is READ-ONLY planning for gameplay/source. Only this ignored
report and its local annex are updated. No test, production source, shared doc,
Git index or native process is changed. The batch below is proposed, not executed.

### Decision and complete boundary

The companion ignored local annex is
`research/experiments/EXP-full-item-maintenance-decisions-r2.json`:
3,622,213 bytes, SHA-256
`27630676a1c6bba09c310acc92d9aad8531866a601014c70cb81bd8089f19664`.
Its readback matched the generated decision object. It retains individual rows
for all 7,389 classes, 234 recipes, 460 actions, 469 unresolved possible action
classes, 2,302 positive config references and all 55 unresolved recipe literals.
All 3,056 source files were rehashed against both source census lists. This is
an exhaustive proposed maintenance disposition, not a completed usefulness
assessment of all those objects or a claim to have executed every method body.

Implement a complete native maintenance qualification path before introducing a
new generic repair system or more guessed decomposition recipes. Native repair,
sharpening, deployed-tent repair and vehicle-part repair already supply much of
the requested reuse. Their actual target eligibility and resource cost are the
missing evidence. A second generic recipe would duplicate native behavior and
could bypass target-zone, fuel or repair-kit checks. This batch implements the
diagnostic/reporting and regression path needed to use that supported scope;
it does not promise a new gameplay buff or claim all item utility is finished.

Keep all 7,389 classes in the decision register. Preserve all 143 lexically
registered recipes without blanket overrides; select the complete ten-recipe
maintenance family below for this batch. The other 133 remain native-preserved,
with separate semantic/behavior qualification outstanding. Retain all 74 disabled
recipes: 62 painting declarations and 12 other declarations. Do not auto-enable
either group. Preserve all 17 unregistered declarations as explicit holds.

Keep all 460 ActionBase-path classes and 469 unresolved possible action classes.
The inspected maintenance closure contains 21 ActionRepair declarations: 15
have item-source AddAction observations and six do not. Twenty are production
path/base candidates; one is expressly marked a test action by native source.
Neither absence of an item call nor presence of a constructor Insert establishes
effective runtime registration. The other 439 action classes remain untouched;
the complete population is retained, not adjudicated useless.

### Native evidence and proposed coverage

The pinned native035 manifest and every chunk were strictly admitted and
rehashed again for these figures. They share the previously recorded native
manifest pin and the same r2 source census; no new engine observation is claimed.

| Repair config observation | Classes | Decision |
| --- | ---: | --- |
| At least one positive repairableWithKits value | 1,510 | Keep native maintenance; resolve every candidate kit/target route before proposing extensions. |
| Nonempty list with nonpositive values only | 1,293 | Do not infer a valid regular kit; retain special action/recipe paths and unresolved behavior. |
| Present empty list | 53 | Do not invent a compatible regular kit; retain explicit exclusions and other native uses. |
| Field absent | 4,533 | No regular-kit evidence from this export; not proof of uselessness or non-inventory status. |
| Total | 7,389 | No rows dropped. |

The 1,510 positive-list classes comprise 1,266 scope=2, 15 scope=1 and 229
scope=0 definitions. These are config observations, not 1,266 approved inventory
targets. Across all roots there are 2,302 positive list entries: type 1=280,
2=739, 3=211, 4=35, 5=786, 6=65, 7=60, 8=106 and 10=20.
All have a corresponding observed positive kit type. Array element kinds remain
unverified; the references cannot be promoted to working repair pairs.

Exactly nine exported classes advertise a positive repairKitType: WeaponCleaningKit
(1), SewingKit (2), LeatherSewingKit (3), Whetstone (4), DuctTape (5),
TireRepairKit (6), ElectronicRepairKit (7), EpoxyPutty (8), Blowtorch (10).
WoodenPlank, Pliers and Fabric are separate native material/tool paths; do not
manufacture repair-kit IDs for them. Keep ammunition in CfgMagazines distinct
from projectile definitions in CfgAmmo and magazine ItemBase eligibility.

There are 49 mismatched repair-list/cost lengths. In every case the cost list
is LONGER, not shorter: five have nonempty allowed-kit lists (four PaddedGloves
definitions and Defibrillator); 44 have empty lists, including StoneKnife and
BoneKnife. This is not evidence of a missing-index crash. Native
PluginRepairing.GetKitRepairCost iterates allowed-kit IDs and selects that index.
Retain surplus-cost metadata as unresolved evidence; do not auto-repair it by
adding IDs, truncating native config or changing gameplay.

Of the 36 cutting tools, 31 advertise repair ID 4; BrickTrowel, FieldShovel and
Shovel advertise [0]; BoneKnife and StoneKnife advertise []. Their captured
cost entries alone cannot grant sharpening. Keep those five outside the
proposed regular-whetstone acceptance set unless native results establish a
different supported route. Cutting-tool admission itself remains unchanged.

### Exact native interfaces and complete maintenance family

All following paths are relative to the pinned installed-source root. Recipe
names below identify existing classes; this proposal adds no duplicate recipe.

| Existing recipe | Exact tool/material and declared target scope | Batch disposition |
| --- | --- | --- |
| CleanWeapon | WeaponCleaningKit + DefaultWeapon / DefaultMagazine / ItemSuppressor | Native in-place repair; preserve actual target, ammo and attachments. |
| RepairElectric | ElectronicRepairKit + Inventory_Base | Native kit/target eligibility, no general electronics component yield. |
| RepairEpoxy | EpoxyPutty + Inventory_Base / DefaultWeapon | Preserve native kit cost and target health thresholds. |
| RepairWithSewingKit | SewingKit + Inventory_Base | Resolve config arrays plus CanBeRepairedByCrafting; no universal cloth repair. |
| RepairWithLeatherSewingKit | LeatherSewingKit + Inventory_Base | Same native route, distinct native kit ID/cost. |
| RepairWithTape | DuctTape + Inventory_Base / DefaultWeapon / DefaultMagazine | Preserve native permissions/cost; never refill consumed tape. |
| RepairWithTireKit | TireRepairKit + Inventory_Base | Native eligibility; do not infer every wheel or detached vehicle part works. |
| SharpenMelee | Whetstone + Inventory_Base | Native CanRepair; classify all 36 cutting tools, including the five non-ID4 observations. |
| RepairPlanks | WoodenPlank + WoodenCrate / SeaChest | In-place container repair; native consumes two planks. Preserve same container/cargo. |
| RepairWithPliers | Pliers + Chainmail / Chainmail_Coif / Chainmail_Leggings / WitchHoodCoif_ColorBase | Separate native normalized-health transfer; not PluginRepairing kit logic. |

Native anchors: `4_World/Plugins/PluginBase/PluginRepairing.c:3,29,92,121,143`
define Repair, CalculateHealth, CanRepair, IsRepairValid and GetKitRepairCost.
The public signatures are `bool CanRepair(ItemBase repair_kit, Object item,
string damage_zone = "")` and `bool Repair(PlayerBase player, ItemBase repair_kit,
Object item, float specialty_weight, string damage_zone = "", bool use_kit_qty = true)`.
Do not call Repair directly as an eligibility oracle: it returns true and can
reach a ruined-state branch. Native recipe conditions/CanRepair must gate commit.
Preserve the exact parenthesized CanRepair behavior in observations; a simplified
Python predicate is not engine proof or a reason to broaden ruined repair.

`4_World/Entities/ItemBase.c:870` supplies CanBeRepairedByCrafting, overridden
false in TentBase.c:88. `3_Game/Entities/Object.c:1356` supplies
CanBeRepairedToPristine; per-class overrides require actual observation.
Native recipe Init/CanDo/Do must be read together. RepairPlanks.c:15–37,62–66
and RepairWithPliers.c:64–80 demonstrate why generic kit-ID inference is insufficient.

`4_World/Plugins/PluginBase/PluginRecipesManager.c:93,317,470` exposes
GetValidRecipes, PerformRecipeServer and RecipeIDFromClassname. Use the actual
manager discovery and server commit routes, not a freshly constructed recipe
as a substitute for registered recipes. `RecipeBase.c:521–539` establishes the
native mutation order; recipe ID/name presence alone proves neither completion
nor material conservation.

<!-- NEXT_MAINTENANCE_PLAN -->

### Action closure: deployed repairs are not interchangeable with recipes

Under `4_World/Classes/UserActionsComponent/Actions/Continuous/`, include all
the following production-path declarations and their inherited methods:

```
ActionRepairBoatChassis ActionRepairBoatEngine
ActionRepairCarChassis ActionRepairCarChassisWithBlowtorch
ActionRepairCarEngine ActionRepairCarEngineWithBlowtorch
ActionRepairCarPart ActionRepairCarPartWithBlowtorch
ActionRepairItemWithBlowtorch
ActionRepairMotorbikeChassis ActionRepairMotorbikeChassisWithBlowtorch
ActionRepairMotorbikeEngine ActionRepairMotorbikeEngineWithBlowtorch
ActionRepairMotorbikePart ActionRepairMotorbikePartWithBlowTorch
ActionRepairPart ActionRepairShelter ActionRepairTent ActionRepairTentPart
ActionRepairVehiclePartBase
```

`SingleUse/ActionRepairWithToolFromHands.c:1` explicitly says it is a test
action. Exclude it from production enablement, keep its declaration/evidence.
The list above includes intermediate/base declarations, not twenty independently
registered player actions. Preserve exact file-name capitalization from the
census; some WithBlowTorch paths differ from class-name capitalization.

ActionRepairTent.c:53–105 resolves a real proxy selection to a damage zone and
uses PluginRepairing with zone transfer. ActionRepairShelter.c:24–52 targets a
non-proxy ShelterBase. ActionRepairTentPart.c:55–123 uses Fabric/source condition
and quantity instead of the same generic kit rule. ActionRepairCarChassis.c:57–64
restricts Fabric/WoodenPlank to native BackWood/BackTarp selections; lines 75–99
have distinct consumption. ActionRepairPart.c:119–127 repairs a real construction
zone and wears the actual tool. Vehicle/base methods have their own health-level,
tool-consumption and zone handling; no universal PluginRepairing substitution.

Blowtorch.c:103–115 registers item/vehicle repair actions and :128 implements
HasEnoughEnergyForRepair(float). ActionRepairItemWithBlowtorch.c:29–62 checks
repair eligibility and energy and switches the actual tool on/off around server
completion. Preserve fuel use, interruption and end cleanup; a config kit ID
does not establish an executable blowtorch repair or vehicle-zone permission.

Native item action acquisition is available through
`ItemBase.c:223–243 InitializeActions/GetActions(typename action_input_type,
out array<ActionBase_Basic> actions)` and
`ActionBase.c:230 typename GetInputType()`;
`ActionConstructor.c:3 bool ConstructActions(out array<ref ActionBase> actionsArray,
out map<typename, ActionBase> actionNameActionMap)` describes construction.
Use the actual initialized engine/player action registry when inspecting items.
Do not fabricate a second constructor registry and call that proof of effective
item membership. ItemBase.RemoveAction reads the real local player; a headless
or no-client failure must remain an explicit limitation, not be bypassed.

### Proposed implementation tasks and ownership, dependency order

No shared file ownership is assigned by this report. Coordinator can delegate
these disjoint new files, keeping native process/probe integration centralized.

| Task | Proposed file(s) / deliverable | Dependency and acceptance |
| --- | --- | --- |
| N1: executable complete decision table | NEW tools/audit/item_utility.py and tests/unit/test_item_utility.py | Consume strict admitted/rehash-pinned native rows, r2 actions and source recipes. Keep all 7,389/234/460 plus unresolved classes/calls. Explicitly distinguish native-use preservation, scoped qualification, disabled/test hold and unsupported material conversion. Missing evidence stays UNKNOWN. No item-to-script identity by name heuristic. |
| N2: native read-only eligibility acquisition | NEW mods/HollowCountry/scripts/4_World/Crafting/HCItemUtilityDiagnostic.c | After N1 schema: bounded typed field/ancestry and actual object-method observations. Include all nine kit types, ten recipes and twenty production/base action declarations; keep special Pliers/Plank/Fabric routes separate. No startup/module registration or behavior override. Fresh isolated profile and explicit diagnostic invocation only. |
| N3: actual object/manager execution | Same N2 diagnostic, authored in separable bounded methods | After N2: for all admitted candidate definitions, record scope/creation/cast/route outcome. Scope 0/1 definitions stay metadata-only unless separately proved safe concrete targets. Process every scope=2 candidate without a pilot/sample cap; failed casts/unsupported targets remain counted, not dropped. Use owned real handles, actual manager GetValidRecipes/PerformRecipeServer and real CanRepair checks. Never mutate a user's existing item or world object. |
| N4: disposable bounded runner | NEW tools/setup/item_utility_probe.py and tests/unit/test_item_utility_probe.py | After N1 schema, parallel with N2: validate/pin inputs, stage one fresh mission, generate opt-in diagnostic config and verify run receipts. One diagnostic actor and bounded target/tool cohort; no arbitrary classnames from untrusted paths. Outer wall-clock timeout, exact invocation identity, progress and observed cleanup mandatory. Empty registry, missing action manager, partial work and no assertions cannot pass. |
| N5: whole maintenance decision readback | N1 reader plus ignored local artifacts | After N2–N4 observed runs: each of 2,302 positive config references receives a native route verdict or explicit pending reason, with per-class negatives/special routes conserved. Do not require all pairs to work; reject unsupported pairs while retaining their row. Compare nine regular-kit ID joins against actual CanRepair/recipe discovery. Preserve all 49 surplus-cost anomalies without inventing kit IDs. |
| N6: failure/conservation qualification | Authored behavioral tests in N1/N4 suites; diagnostic cases in N2 | Real RED/GREEN on authored selection, budgets, receipts and mutation adapters. For native observations: same target/tool handles, kit quantity/energy, target zones/health, cargo/attachments/ammo/agents, interrupted/exhausted/deleted/wrong-owner paths. No replacement pristine target and no resource refill. Native Pliers/Plank/Fabric semantics have separate assertions, not a copied universal kit model. |
| N7: actual acceptance matrix | Coordinator-owned native evidence and normal PBO/two-client work, not performed here | Compile and run diagnostic acquisition; native mutation is separate from action animation/transport. Normal signed client/server tests cover real action discovery, selections, interruption, full inventory, reconnect, duplicate/competing completion and two-client contention. Any unresolved cell keeps the slice partial. No broad CRFT promotion from this batch. |

N1 and N4 tests should exercise authored Python behavior and authored diagnostic
method bodies with explicit synthetic engine adapters, following the existing
translator convention. No source-substring assertion counts as behavior.
Native installed sources are read-only primary references, never copied into
Git or bundled as CI fixtures. RED/GREEN is required when implementation starts;
this planning follow-up ran no new tests and claims no new test success.

N2 must check time/work/bytes and explicit object accounting. Queue the full
candidate population in bounded chunks; do not replace a limit with silent
sampling. An overall time limit produces a PARTIAL receipt with a conserved
remaining queue. No SYSTEM tick or simulation progress is assumed on an empty
server. Synchronous bounded kickoff and a wall-clock external deadline are
required; stalled callbacks do not count as cleanup or successful completion.
Class creation failures are observations. Casting an already created object to
ItemBase does not retrospectively authorize spawning unsafe base/world classes;
construct a concrete-class plan first and refuse uncertain actors/explosives.
All excluded/unsafe-to-spawn definitions remain explicit pending rows.

Production acceptance for this slice means the complete supported maintenance
matrix has evidence-backed decisions, costs/state are conserved and unsupported
cases are expressly excluded. It does not mean every admitted class must become
repairable. Diagnostics/reporting are implementation work; they do not by
themselves add new player utility or satisfy the whole-item feature request.

### Decisions across the remaining item-use domains

| Domain | Actual next decision | Evidence still needed |
| --- | --- | --- |
| Cloth / nets / cordage / improvised storage | Keep native CraftRag, CraftBurlapStrips, CraftRagRope, CraftGutsRope, both courier/improvised bag directions, DrysackBag/action reverse, five Ghillie craft/reverse pairs and fish-net trap craft/reverse. Do not add a duplicate generic cloth, rope or net recipe. | Export ragQuantity and sorting/recipe eligibility, retain dynamic colors, inspect native Do and actual forward/reverse quantities, contamination, cargo and state transfer. Existing rope belt and rag-cover actions remain part of this family. |
| Leather | Keep native LeatherSack/Waterskin recovery and WildboarPelt courier/improvised-bag recovery; do not replace all of them with TannedLeather. Do not blanket-expand the existing HC belt recipe to every leather-named item. | CraftLeatherBelt/Sheath/Hippack.c:26 use LizardPelt. Native CraftTannedLeather.c:31,58–90 uses Pelt_Base/GardenLime and config leatherYield, with separate custom spawning. Garment material mapping/yield and reverse graph need an explicit design plus actual config/behavior checks. |
| Wood / stone / bone / tools | Keep native log/plank/firewood/stick, knife, hook and spear paths; no generic part counts inferred from item weight or a class-name word. | Actual recipe graph, multiplicity, source Do, tool depletion and environment actions. Log/rock/tree actions and finite resource behavior need their own full family qualification. |
| Mechanical / electrical salvage | Keep native wire/trap recovery and HC disconnected CableReel recovery. Do not turn a battery/radio/device into an arbitrary repair kit or assume a depleted powered device is empty. | Exact component output/material semantics, stored energy, attachments, quantity and reverse-cycle policy; no currently demonstrated all-device decomposition rule. |
| Repair / reuse | Execute N1–N7 as the next bounded complete family, preserving existing native permissions/costs. | All native route evidence described above; no blanket pristine/ruined upgrade. |
| Cooking / consuming / hygiene / medical | Preserve the native cooking stage, contamination, agents, quantities and actions. Keep their observed callbacks; no replacement item that launders state. | Full native eligibility/Do/action effects and actual behavior; recipe literal joins cannot establish nutritional, treatment or contamination outcomes. |
| Attachments / camouflage / lighting | Keep native GhillieAtt_Tan reuse; taped-light work remains separately owned. No generic proxy/slot/colors from a config-name match. | Exact host/slot/mount geometry, power, beam/switching, wear/removal, save state and two-client presentation. |
| Disabled / legacy declarations | Keep all 91 disabled/unregistered recipe declarations without automatic registration. Modern native actions can supersede a recipe. | Each proposed enablement needs a specific missing use, real output/config and mutation/registration proof. Publication/pilot/source availability never substitutes for that evidence. |

The 55 unresolved literal references are not 55 absent features: 30 occur in
registered source recipes, 17 in unregistered declarations and eight in disabled
ones. Dynamic result prefixes (Armband_, DrysackBag_, WitchHoodCoif_, BarrelHoles_)
must be evaluated with native result-color inheritance; legacy carrier/ammo
names and malformed `Jambiya;` require different treatment. A future complete
literal-resolution batch must keep all 55 and distinguish these reasons, not
create guessed replacement classes. Case-only output spelling, such as source
LeatherHippack_Lizard versus admitted LeatherHipPack_Lizard, is not evidence
of a missing class. No correction of these native files is authorized here.

### Truly user-dependent design, not blockers for N1–N7

No interview is required to preserve and qualify native maintenance. Keep native
kit permissions, costs, quality ceilings and current HC balance unchanged.
Routine cohort sizes, diagnostic chunk/rate limits and retention are bounded
operator options, not a new product decision or prerequisite server dependency.

Before NEW broad decomposition is approved, the product must select meaningful
material outputs and recovery rules for leather garments, devices and ruined
gear. In particular: whether lizard/fur/finished leather remain distinct; which
recoverable component types actually exist; and whether ruined equipment yields
any material rather than being repaired. Native APIs cannot decide that gameplay
intent. Propose a configurable, conservation-checked per-material table for
review; do not require the user to invent Enforce APIs or every numerical value.
No permission to improve every repair to pristine or reverse tanning follows
from the request for item usefulness. Visual/model feasibility is an engineering
investigation, not a question that should be pushed to the user.

<!-- END_NEXT_MAINTENANCE_PLAN -->

<!-- GENERATED_FULL_SCOPE_ANNEX -->

## Generated full-coverage decision annex

The following rows exhaust the admitted inventories. No sample or pilot cap is applied.
Recipe status is lexical registration status. Every runtime/eligibility result remains UNKNOWN.
No config-to-script identity or inherited recipe membership is inferred from matching names.

### Rehashed artifact provenance

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| /home/david/.cache/hollow-country/item-review-035-full-20261116/workbook.json | 7856281 | 2fe8154743c671182fcf5ef3be448109ce4e2b4fcd340f98a86b68ede62b6983 |
| /home/david/.cache/hollow-country/item-review-035-full-20261116/crafting-census.json | 2438538 | 1300f1e31f755cbaa477e64c5cd5dbdfbe6612edce8cc09446c6e4ebb152de60 |
| /home/david/.cache/hollow-country/action-audit-full-r2-20261116/action-census.json | 30523514 | ad114537a1b83d837fb04089e3d441664ac67294f004a68eacfdedb1c30f643e |

All 3,056 source files were independently rehashed for this report and match both census source lists.
Shared source manifest: `b7ed9fa47f1285f8aa436c18fc9c8681a7e017b2441a7923c8eae0f2a019af33`.

### Current action-census checkpoint

This generated checkpoint supersedes the earlier 30,382,043-byte action artifact.
The older checkpoint is preserved as history, not silently overwritten.

```json
{
  "action_candidates": 460,
  "aliases": 253,
  "analysis_work": 2205483,
  "bindings_by_call": {
    "AddAction": 1272,
    "Insert": 343,
    "RemoveAction": 38,
    "SetActions": 465
  },
  "callbacks": 301,
  "callbacks_by_category": {
    "attachment": 165,
    "consume": 10,
    "cooking": 120,
    "repair": 6
  },
  "class_declarations": 6801,
  "classes": 6796,
  "disabled_bindings": 22,
  "emitted_bindings": 2118,
  "excluded_non_action_classes": 5867,
  "method_declarations": 32603,
  "source_bytes": 13952124,
  "source_census_complete": true,
  "source_files": 3056,
  "tokens": 1915528,
  "unknown_action_ancestry_classes": 469,
  "unregistered_item_action_candidates": 167,
  "unresolved_ancestry_classes": 473,
  "unresolved_bindings": 399
}
```

### Exhaustive item/config decision classification

Direct literal links are observed native recipe references; no direct link means UNKNOWN utility, not useless.
Hidden definitions remain for config inheritance/base references; they are not approved direct spawn targets.

| Definition classification | Literal-reference classification | Count |
| --- | --- | --- |
| hidden-definition | direct-recipe-reference | 34 |
| hidden-definition | no-direct-recipe-reference | 633 |
| retain-definition | direct-recipe-reference | 287 |
| retain-definition | no-direct-recipe-reference | 6435 |

| Config class | Definition review | Literal refs | Inventory eligibility / script bridge |
| --- | --- | --- | --- |
| CfgAmmo:BarbedWireHit | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:BearTrapHit | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:BearTrapHit_CarWheel | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bolt_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_12GaugeBeanbag | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_12GaugePellets | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_12GaugeRubberSlug | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_12GaugeSlug | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_22 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_308Win | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_308WinTracer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_357 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_380 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_40mm_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_40mm_ChemGas | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_40mm_Explosive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_40mm_Smoke_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_40mm_Smoke_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_40mm_Smoke_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_40mm_Smoke_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_45ACP | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_545x39 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_545x39Tracer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_556x45 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_556x45Tracer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_762x39 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_762x39Tracer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_762x54 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_762x54Tracer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_9x19 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_9x39 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_9x39AP | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_CupidsBolt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_Flare | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_FlareBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_FlareGreen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_FlareRed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_HuntingBolt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_ImprovisedBolt_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Bullet_ImprovisedBolt_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:BulletCore | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:ClaymoreMine_Ammo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:ClaymoreMine_Secondary_Ammo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Dart_Syringe | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:DefaultAmmo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Dummy_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Dummy_Light | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:EnviroDmg | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Explosion_40mm_Ammo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Explosion_NonLethal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:FallDamageHealth | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:FallDamageHealthAttachment | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:FallDamageHealthOtherAttachments | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:FallDamageShock | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:FinisherHit | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:FinisherHitNeck | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:FirearmHit_Pistol | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:FirearmHit_Rifle | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:FirearmHit_Rifle_Bayonet | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:FirearmHit_Rifle_Bayonet_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:FirearmHit_Rifle_Buttstock | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:FireDamage | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Fireworks_Ammo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:FlashGrenade_Ammo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:GasCanister_Ammo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:GrenadeM4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:HeatDamage | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:LandFuelFeed_Ammo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:LandMineExplosion_Ammo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:LandMineExplosion_CarWheel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:M67Grenade_Ammo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeAxe | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeAxe_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBat | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBat_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBatNails | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBatNails_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBear | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBear_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBearShock | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBearShock_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBlunt | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBlunt_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBluntHeavy_1 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBluntHeavy_2 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBluntHeavy_3 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBluntHeavy_4 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBluntHeavy_5 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBluntLight_1 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBluntLight_2 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBluntLight_3 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBluntLight_4 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBluntLight_5 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBluntStick | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBluntStick_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBrassKnuckles | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeBrassKnuckles_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeChainsaw | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeChainsaw_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeCraftedHeavy_1 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeCraftedHeavy_2 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeCraftedHeavy_3 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeCraftedHeavy_4 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeCraftedHeavy_5 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeCraftedLight_1 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeCraftedLight_2 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeCraftedLight_3 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeCraftedLight_4 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeCraftedLight_5 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeCrowbar | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeCrowbar_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeDamage | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeFarmingHoe | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeFarmingHoe_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeFFAxelHeavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeFFAxeLight | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeFieldShovel | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeFieldShovel_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeFireAxe | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeFireAxe_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeFireExtinguisher | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeFireExtinguisher_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeFist | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeFist_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeFistHeavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeFistLight | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeHacksaw | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeHacksaw_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeHammer | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeHammer_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeHatchet | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeHatchet_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeHeavybat | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeHeavybat_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeInfected | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeInfected_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeInfectedLong | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeInfectedLong_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeKnife | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeKnife_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeLightBlunt | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeLightBlunt2 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeLightBlunt2_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeLightBlunt_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeLightBluntShock | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeLightBluntShock_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeMace | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeMace_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeMachete | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeMachete_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeMeatTenderizer | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeMeatTenderizer_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeMummyInfected | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeMummyInfected_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeMummyInfectedLong | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeMummyInfectedLong_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleePickaxe | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleePickaxe_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleePipeWrench | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleePipeWrench_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleePitchfork | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleePitchfork_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleePliers | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleePliers_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleePoliceInfected | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleePoliceInfected_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleePoliceInfectedLong | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleePoliceInfectedLong_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeProd | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeProd_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeScrewdriver | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeScrewdriver_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSharpHeavy_1 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSharpHeavy_2 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSharpHeavy_3 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSharpHeavy_4 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSharpHeavy_5 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSharpLight_1 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSharpLight_2 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSharpLight_3 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSharpLight_4 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSharpLight_5 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSharpWoodenStick | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSharpWoodenStick_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeShovel | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeShovel_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSickle | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSickle_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSlash | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSlash2 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSlash2_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSlash_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSledgeHammer | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSledgeHammer_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSoft | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSoft_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSoldierInfected | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSoldierInfected_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSoldierInfectedLong | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSoldierInfectedLong_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSpear | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSpear_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeStab | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeStab_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeStoneKnife | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeStoneKnife_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSword | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeSword_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeWAxelHeavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeWAxeLight | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeWolf | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeWolf_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeWoodBlunt | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeWoodBlunt_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeWrench | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeWrench_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombie | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombie_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieFemale | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieFemale_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieFemaleLong | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieFemaleLong_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieFirefighter | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieFirefighter_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieFirefighterLong | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieFirefighterLong_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieMale | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieMale_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieMaleLong | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieMaleLong_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieMummy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieMummy_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieMummyLong | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieMummyLong_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombiePolice | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombiePolice_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombiePoliceLong | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombiePoliceLong_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieSoldier | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieSoldier_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieSoldierLong | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:MeleeZombieSoldierLong_Heavy | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Plastic_Explosive_Ammo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:RGD5Grenade_Ammo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Rocket_LAW_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Rocket_LAW_HE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Rocket_RPG7_AP | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Rocket_RPG7_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Rocket_RPG7_HE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:Shotgun_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:ShotgunCore | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:TransportHit | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgAmmo:TripWireHit | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_12gaBeanbag | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_12gaPellets | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_12gaRubberSlug | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_12gaSlug | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_22 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_308Win | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_308WinTracer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_357 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_380 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_40mm_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_40mm_ChemGas | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_40mm_Explosive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_40mm_Smoke_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_40mm_Smoke_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_40mm_Smoke_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_40mm_Smoke_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_40mm_Smoke_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_45ACP | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_545x39 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_545x39Tracer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_556x45 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_556x45Tracer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_762x39 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_762x39Tracer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_762x54 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_762x54Tracer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_9x19 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_9x39 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_9x39AP | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_CupidsBolt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_Flare | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_FlareBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_FlareGreen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_FlareRed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_GrenadeM4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_HuntingBolt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_ImprovisedBolt_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_ImprovisedBolt_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_LAW_HE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_RPG7_AP | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammo_RPG7_HE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Ammunition_Base | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:DefaultMagazine | excluded-definition | 2 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_12gaSnaploader_2Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_1911_7Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_308WinSnaploader_2Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_357Speedloader_6Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_762x54Snaploader_2Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_AK101_30Rnd | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_AK101_30Rnd_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_AK101_30Rnd_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_AK74_30Rnd | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_AK74_30Rnd_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_AK74_30Rnd_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_AK74_45Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_AKM_30Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_AKM_30Rnd_Gold | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_AKM_Drum75Rnd | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_AKM_Drum75Rnd_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_AKM_Drum75Rnd_Gold | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_AKM_Drum75Rnd_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_AKM_Drum_TEST | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_AKM_Palm30Rnd | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_AKM_Palm30Rnd_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_AKM_Palm30Rnd_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_Arrows_Quiver | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_Aug_30Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_Bolts_Quiver | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CLIP762x39_10Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CLIP762x54_5Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CLIP9x19_10Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CMAG_10Rnd | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CMAG_10Rnd_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CMAG_10Rnd_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CMAG_20Rnd | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CMAG_20Rnd_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CMAG_20Rnd_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CMAG_30Rnd | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CMAG_30Rnd_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CMAG_30Rnd_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CMAG_40Rnd | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CMAG_40Rnd_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CMAG_40Rnd_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CZ527_5rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CZ550_10rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CZ550_4rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CZ61_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_CZ75_15Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_Dartgun_CO2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_Deagle_9rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_FAL_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_FAMAS_25Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_FNX45_15Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_Glock_15Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_Groza_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_IJ70_8Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_LeeEnfield_10Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_Luger_8Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_M14_10Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_M14_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_M249_Box200Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_MakarovPB_8Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_MKII_10Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_MP18_Drum32Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_MP5_15Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_MP5_30Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_P1_8Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_PM73_15Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_PM73_25Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_PP19_64Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_Ruger1022_10Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_Ruger1022_15Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_Ruger1022_30Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_Saiga_5Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_Saiga_8Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_Saiga_Drum20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_SCARH_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_SCARH_20Rnd_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_Scout_5Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_ShockCartridge | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_SSG82_5rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_STANAG_30Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_STANAG_60Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_STANAGCoupled_30Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_SV98_10Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_SVD_10Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_UMP_25Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_VAL_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_Vikhr_30Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Mag_VSS_10Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgMagazines:Magazine_Base | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Achar | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ACOGOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ACOGOptic_6x | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AgaricusMushroom | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Air | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AirborneMask | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK74_Hndgrd | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK74_Hndgrd_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK74_Hndgrd_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK74_WoodBttstck | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK74_WoodBttstck_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK74_WoodBttstck_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_Bayonet | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_FoldingBttstck | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_FoldingBttstck_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_FoldingBttstck_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_PlasticBttstck | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_PlasticBttstck_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_PlasticBttstck_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_PlasticHndgrd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_RailHndgrd | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_RailHndgrd_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_RailHndgrd_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_Suppressor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_WoodBttstck | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_WoodBttstck_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_WoodBttstck_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_WoodBttstck_Gold | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_WoodHndgrd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_WoodHndgrd_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_WoodHndgrd_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AK_WoodHndgrd_Gold | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Akinaka | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AKS74U_Bttstck | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AKS74U_Bttstck_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AKS74U_Bttstck_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AlarmClock_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AlarmClock_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AlarmClock_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AlarmClock_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AliceBag_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AliceBag_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AliceBag_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AliceBag_FarBubble | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AliceBag_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AliceBag_NearBubble | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:All | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AllDrive | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AllVehicles | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmanitaMushroom | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_00buck_10rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_12gaBeanbag_10Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_12gaRubberSlug_10Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_12gaSlug_10Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_22_50Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_308Win_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_308WinTracer_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_357_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_380_35rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_45ACP_25rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_545x39_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_545x39Tracer_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_556x45_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_556x45Tracer_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_762x39_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_762x39Tracer_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_762x54_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_762x54Tracer_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_9x19_25rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_9x39_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AmmoBox_9x39AP_20Rnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_BosTaurus | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_BosTaurus_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_BosTaurus_Spotted | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_BosTaurus_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_BosTaurusF | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_BosTaurusF_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_BosTaurusF_Spotted | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_BosTaurusF_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CanisFamiliaris_Dobermann_Bald | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CanisFamiliaris_Dobermann_Bloody | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CanisFamiliaris_Dobermann_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CanisFamiliaris_Dobermann_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CanisFamiliaris_Dobermann_Skinny | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CanisFamiliaris_Dobermann_Vest | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CanisFamiliaris_GermanShepherd_Balding | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CanisFamiliaris_GermanShepherd_Bloody | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CanisFamiliaris_GermanShepherd_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CanisFamiliaris_GermanShepherd_Harness | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CanisFamiliaris_GermanShepherd_Skinny | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CanisLupus | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CanisLupus_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CanisLupus_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CapraHircus | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CapraHircus_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CapraHircus_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CapraHircus_Spooky | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CapraHircus_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CapraHircusF | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CapreolusCapreolus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CapreolusCapreolusF | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CervusElaphus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_CervusElaphusF | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_GallusGallusDomesticus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_GallusGallusDomesticusF | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_GallusGallusDomesticusF_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_GallusGallusDomesticusF_Spotted | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_GallusGallusDomesticusF_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_LepusEuropaeus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_OvisAries | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_OvisAriesF | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_OvisGmelini | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_RangiferTarandus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_RangiferTarandus_Xmas | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_RangiferTarandusF | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_SusDomesticus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_SusScrofa | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_UrsusArctos | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_VaranusGriseus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Animal_VulpesVulpes | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AnimalBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AnimalsHoofsMedium | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Anniversary_FireworksLauncher | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AnniversaryBox | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AnniversaryMusicSource | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AnniversarySpotLight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AntiChemInjector | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AntiPestsSpray | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Apple | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Altis | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_APA | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_BabyDeer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Bear | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Bohemia | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_BrainZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Cannibals | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_CDF | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Chedaki | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_CHEL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Chernarus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_CMC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Crook | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_DayZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_HunterZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Livonia | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_LivoniaArmy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_LivoniaPolice | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_NAPA | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_NSahrani | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Pink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Pirates | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Refuge | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Rex | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Rooster | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_RSTA | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Sakhal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Snake | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_SSahrani | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_TEC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_UEC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_White | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Wolf | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Zagorky | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Armband_Zenit | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ArmyPouch_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ArmyPouch_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ArmyPouch_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ArmyPouch_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ArmyPouch_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AssaultBag_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AssaultBag_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AssaultBag_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AssaultBag_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AssaultBag_Ttsko | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AssaultBag_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AthleticShoes_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AthleticShoes_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AthleticShoes_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AthleticShoes_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AthleticShoes_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AthleticShoes_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AtlasBipod | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Attack2Bag_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Attack2Bag_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Attack2Bag_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Attack2Bag_Ttsko | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Attack2Bag_Yeger | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Aug_Barrel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AugOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AuriculariaMushroom | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AviatorGlasses | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Ayran | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:AyranBottle | retain | 10 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bait | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BakedBeansCan | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BakedBeansCan_Opened | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Balaclava3Holes_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Balaclava3Holes_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Balaclava3Holes_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Balaclava3Holes_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Balaclava3Holes_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Balaclava3Holes_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BalaclavaMask_BDU | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BalaclavaMask_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BalaclavaMask_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BalaclavaMask_Blackskull | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BalaclavaMask_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BalaclavaMask_Chain | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BalaclavaMask_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BalaclavaMask_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BalaclavaMask_Pig | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BalaclavaMask_Pink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BalaclavaMask_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Ballerinas_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Ballerinas_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Ballerinas_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Ballerinas_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Ballerinas_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BallisticHelmet_BDU | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BallisticHelmet_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BallisticHelmet_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BallisticHelmet_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BallisticHelmet_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BallisticHelmet_Navy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BallisticHelmet_UN | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BallisticHelmet_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BallisticHelmet_Woodland | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Banana | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BandageDressing | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bandana_BlackPattern | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bandana_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bandana_CamoPattern | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bandana_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bandana_Greenpattern | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bandana_Pink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bandana_PolkaPattern | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bandana_RedPattern | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bandana_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BarbedBaseballBat | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BarbedWire | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BarbedWireLocked | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bark_Birch | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bark_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bark_Oak | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bark_Palm | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Barrel_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Barrel_ColorBase | excluded-definition | 12 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Barrel_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Barrel_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Barrel_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BarrelHoles_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BarrelHoles_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BarrelHoles_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BarrelHoles_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BarrelHoles_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BaseballBat | retain | 4 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BaseballCap_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BaseballCap_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BaseballCap_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BaseballCap_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BaseballCap_CMMG_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BaseballCap_CMMG_Pink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BaseballCap_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BaseballCap_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BaseballCap_Pink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BaseballCap_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BaseBuildingBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BaseRadio | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Battery9V | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BatteryCharger | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BDUJacket | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BDUPants | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BeanieHat_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BeanieHat_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BeanieHat_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BeanieHat_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BeanieHat_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BeanieHat_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BeanieHat_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BeanieHat_Pink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BeanieHat_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bear_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bear_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bear_Dark | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bear_Pink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bear_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BearPelt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BearSteakMeat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BearTrap | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Binoculars | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bitterlings | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BloodBagEmpty | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BloodBagFull | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BloodBagIV | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BloodSyringe | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BloodTestKit | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Blouse_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Blouse_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Blouse_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Blouse_Violet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Blouse_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Blowtorch | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoarSteakMeat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Boat | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Boat_01_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Boat_01_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Boat_01_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Boat_01_ColorBase | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Boat_01_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoatScript | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoletusMushroom | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BomberJacket_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BomberJacket_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BomberJacket_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BomberJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BomberJacket_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BomberJacket_Maroon | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BomberJacket_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BomberJacket_SkyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bone | retain | 7 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoneBait | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoneHook | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoneKnife | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bonfire | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Book20000LieuesSousLesMers | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Book_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookADollsHouse | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookAfterLondon | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookAliceInWonderland | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookAndersen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookAndersensFairyTales | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookAnnaKarenina | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookAPrincessOfMars | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookAroundTheWorldIn80Days | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookATexasMatchmaker | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookATravelerInTime | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookAVoyageToArcturus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookBettyZane | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookBible | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookBilaNemoc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookBlackBeauty | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookBlackJack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookBuddenbrooks | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookCandide | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookCassidysRustlerRoundUp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookCinqSemainesEnBallon | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookCrimeAndPunishment | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookDasNibelungenlied | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookDeadSouls | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookDeLaTerreLaLune | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookDeLorigineDesEspces | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookDesertGold | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookDonQuichotte | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookDonQuixote | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookDracula | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookErewhon | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookFatherGoriot | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookFaust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookFaustErsterTeil | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookFlyingURanch | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookFrankenstein | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookGilgameshEpic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookGreatExpectations | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookGulliversTravels | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookGunmansReckoning | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookHeartOfDarkness | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookHerland | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookHinduLiterature | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookHunger | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookIvanhoe | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookJapaneseLiterature | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookKidnapped | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookKingLear | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookKingSolomonsMines | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookLaChartreuseDeParme | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookLaComdieHumaine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookLaDbcle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookLenfer1Of2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookLeRougeEtLeNoir | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookLesCorneilles | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookLesTroisMousquetaires | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookLleMystrieuse | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookLonesomeLand | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookLordJim | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookMadameBovary | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookMiddlemarch | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookMobyDick | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookMrchenFrKinder | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookNaturalSelection | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookNjalsSaga | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookNostromo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookPhilosophiaeNaturalis | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookPrideAndPrejudice | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookRasselas | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookRobinsonCrusoe | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookRobinsonCrusoeAdventures | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookRomeoUndJulia | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookRonickyDoone | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookRussian | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookRussianCheatSheet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookScaramouche | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookSelectedStories | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookShe | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookSkyrider | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookSonsAndLovers | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookSpinifexAndSand | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookSunsetPass | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheAeneid | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheArtOfWar | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheBarrier | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheBrothersKaramazov | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheCallOfCthulhu | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheCallOfTheWild | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheCanterburyTales | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheCaveOfGold | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheComingRace | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheCosmicComputer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheCountryOfTheBlind | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheDayOfTheBeast | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheDecameron | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheDesertOfWheat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheGiacomoLeopardi | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheHeritageOfTheSioux | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheHiddenChildren | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheHoundOfTheBaskervilles | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheHouseOfTheSevenGables | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheIslandOfDoctorMoreau | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheJungleBook | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheJustifiedSinner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheLastMan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheLastOfThePlainsmen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheLastTrail | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheMahabharataOfKrishna | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheManWhoWasThursday | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheMetamorphosesOfOvid | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheMetamorphosis | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheMonkARomance | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheOutlet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookThePictureOfDorianGray | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookThePitAndThePendulum | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookThePossessed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookThePrisonerOfZenda | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheQuirt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheRaven | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheRedBadgeOfCourage | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheRightsOfWoman | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheScarletPimpernel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheShunnedHouse | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheThreeMusketeers | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheThunderBird | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheTimeMachine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheTrial | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheTurnOfTheScrew | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheVariableMan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTheWarOfTheWorlds | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookThreeMenInABoat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTonyAndTheBeetles | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookToTheInteriorOfTheEarth | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTrailin | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTranslationsOfShakuntala | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookTreasureIsland | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookUlysses | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookUncleSilas | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookVerwandlung | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookVoyageAuCentreDeLaTerre | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookWarAndPeace | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookWealthOfNations | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookWielandOrTheTransformation | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookWutheringHeights | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BookYouth | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoonieHat_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoonieHat_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoonieHat_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoonieHat_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoonieHat_DPM | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoonieHat_Dubok | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoonieHat_Flecktran | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoonieHat_NavyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoonieHat_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoonieHat_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoonieHat_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoonieHat_Tan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoonieHat_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Bottle_Base | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Box_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BoxCerealCrunchin | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BrakeFluid | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BrassKnuckles_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BrassKnuckles_Dull | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BrassKnuckles_MenAtArms | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BrassKnuckles_Shiny | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Breeches_Beetcheck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Breeches_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Breeches_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Breeches_Blackcheck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Breeches_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Breeches_Browncheck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Breeches_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Breeches_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Breeches_Pink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Breeches_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Breeches_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BrickTrowel | retain | 48 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BrisketSpread | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BrisketSpread_Opened | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Broom | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Broom_Birch | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BudenovkaHat_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BudenovkaHat_Gray | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Building | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BUISOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BunkerBroadcastProxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BurlapSack | retain | 4 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BurlapSackCover | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BurlapStrip | retain | 11 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BushlatPoliceJacket_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:BushlatPoliceJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ButaneCanister | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CableReel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CamoNet | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CamoNetShelter | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Candle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Candycane_Colorbase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Candycane_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Candycane_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Candycane_RedGreen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Candycane_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CaninaBerry | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CanisterGasoline | retain | 10 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Cannabis | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CannabisSeeds | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CannabisSeedsPack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CanOpener | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Canteen | retain | 10 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CanvasBag_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CanvasBag_Medical | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CanvasBag_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CanvasPants_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CanvasPants_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CanvasPants_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CanvasPants_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CanvasPants_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CanvasPants_Violet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CanvasPantsMidi_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CanvasPantsMidi_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CanvasPantsMidi_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CanvasPantsMidi_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CanvasPantsMidi_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CanvasPantsMidi_Violet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Car | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CarBattery | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CarDoor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CargoPants_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CargoPants_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CargoPants_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CargoPants_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CargoPants_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CargoPants_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Carp | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CarpFilletMeat | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CarRadiator | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CarScript | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CarTent | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CarTentPlacing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CarWheel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Cassette | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Catfish | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CatfishFilletMeat | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CatFoodCan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CatFoodCan_Opened | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CattleProd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Cauldron | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Chainmail | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Chainmail_Coif | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Chainmail_Leggings | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Chainsaw | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CharcoalTablets | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChelatingTablets | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Chemlight_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Chemlight_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Chemlight_FarBubble | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Chemlight_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Chemlight_NearBubble | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Chemlight_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Chemlight_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Chemlight_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChernarusMap | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChernarusMap_Open | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChernarusMap_Open_Test | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChernarusSportShirt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChestHolster | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Chestplate | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChestRigVest_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChestRigVest_Khaki | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChestRigVest_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChestRigVest_Tan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChickenBreastMeat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChickenFeather | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChildBag_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChildBag_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChildBag_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChildBag_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Chips | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChristmasHeadband_Antlers | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChristmasHeadband_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChristmasHeadband_Gingerbread | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChristmasHeadband_Lights_Antlers | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChristmasHeadband_Lights_Gingerbread | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChristmasHeadband_Lights_Trees | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChristmasHeadband_Trees | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChristmasTree | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ChristmasTree_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Church | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CigarettePack_Chernamorka | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CigarettePack_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CigarettePack_Merkur | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CigarettePack_Partyzanka | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivilianBelt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivilianSedan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivilianSedan_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivilianSedan_Wine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_BackLeft | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_BackLeft_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_BackLeft_BlackRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_BackLeft_WhiteRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_BackLeft_Wine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_BackLeft_WineRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_BackRight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_BackRight_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_BackRight_BlackRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_BackRight_WhiteRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_BackRight_Wine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_BackRight_WineRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_CoDriver | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_CoDriver_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_CoDriver_BlackRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_CoDriver_WhiteRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_CoDriver_Wine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_CoDriver_WineRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_Driver | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_Driver_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_Driver_BlackRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_Driver_WhiteRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_Driver_Wine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanDoors_Driver_WineRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanHood | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanHood_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanHood_BlackRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanHood_WhiteRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanHood_Wine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanHood_WineRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanTrunk | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanTrunk_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanTrunk_BlackRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanTrunk_WhiteRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanTrunk_Wine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanTrunk_WineRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanWheel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CivSedanWheel_Ruined | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ClaymoreMine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ClaymoreMinePlacing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ClearSyringe | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Cleaver | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Clothing | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Clothing_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ClutterCutter2x2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ClutterCutter6x6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ClutterCutterFireplace | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ColdOperationBoots_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ColdOperationBoots_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ColdOperationBoots_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ColdOperationBoots_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CombatBoots_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CombatBoots_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CombatBoots_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CombatBoots_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CombatBoots_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CombatBoots_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CombatKnife | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CombinationLock | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CombinationLock4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CommonBrick | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Compass | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ConstructionHelmet_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ConstructionHelmet_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ConstructionHelmet_Lime | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ConstructionHelmet_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ConstructionHelmet_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ConstructionHelmet_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ConstructionHelmet_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Container_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ContainerLockedBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ContaminatedArea_Dynamic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ContaminatedArea_Local | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ContaminatedArea_Static | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CookingStand | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CourierBag | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CowboyHat_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CowboyHat_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CowboyHat_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CowboyHat_darkBrown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CowboyHat_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CowPelt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CowSteakMeat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CoyoteBag_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CoyoteBag_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CoyoteBag_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CoyoteBag_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CoyoteBag_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CrabCan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CrabCan_Opened | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Crackers | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CraterellusMushroom | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CraterLong | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CrookedNose | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Crowbar | retain | 46 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:CrudeMachete | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Dam_Concrete_20_Floodgate | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DarkMotoHelmet_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DarkMotoHelmet_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DarkMotoHelmet_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DarkMotoHelmet_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DarkMotoHelmet_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DarkMotoHelmet_Lime | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DarkMotoHelmet_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DarkMotoHelmet_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DarkMotoHelmet_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DarkMotoHelmet_YellowScarred | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DarkMotoHelmet_YellowScarred_Test | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DayZInfected | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DeadChicken_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DeadChicken_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DeadChicken_Spotted | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DeadChicken_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DeadFox | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DeadLizard | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DeadRabbit | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DeadRooster | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DeerPelt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DeerSteakMeat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Defibrillator | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DenimJacket | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DesignerGlasses | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DigitalCodeLock | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DigitalCodeLock_Bunker | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DirtBikeHelmet_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DirtBikeHelmet_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DirtBikeHelmet_Chernarus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DirtBikeHelmet_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DirtBikeHelmet_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DirtBikeHelmet_Khaki | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DirtBikeHelmet_Mouthguard | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DirtBikeHelmet_Police | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DirtBikeHelmet_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DirtBikeHelmet_Visor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DisinfectantAlcohol | retain | 5 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DisinfectantSpray | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DobermannPelt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DogFoodCan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DogFoodCan_Opened | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DogPelt_ColorBase | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DogSteakMeat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DonerKnife | retain | 48 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DoorTestCamera | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DownJacket_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DownJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DownJacket_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DownJacket_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DownJacket_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DressShoes_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DressShoes_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DressShoes_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DressShoes_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DressShoes_Sunburst | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DressShoes_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DryBag_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DryBag_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DryBag_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DryBag_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DryBag_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DryBag_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DryBag_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DrysackBag_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DrysackBag_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DrysackBag_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DrysackBag_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DuctTape | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DuctTapeLocked | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DuffelBagSmall_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DuffelBagSmall_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DuffelBagSmall_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DuffelBagSmall_Medical | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DustGoggles_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DustGoggles_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DustGoggles_Transparent | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DZ_LightAI | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:DZ_LightAI_old | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:EasterEgg | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Edible_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:EffectArea | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ElectronicRepairKit | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:EngineOil | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Epinephrine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:EpoxyPutty | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ExplosionTest | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ExplosivesBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:EyeMask_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:EyeMask_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:EyeMask_Christmas | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:EyeMask_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:EyeMask_Dead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:EyeMask_NewYears | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:EyeMask_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:EyeMask_Valentines | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:EyeMask_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:EyePatch_Improvised | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Fabric | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FaceCover_Improvised | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Fal_FoldingBttstck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Fal_OeBttstck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FangeKnife | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FarmingHoe | retain | 4 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FeetCover_Improvised | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleBatyFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleBatyFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleBatyHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleBatyHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleBatyHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleBatyLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleBatyLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleBatyTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleBatyTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleEvaFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleEvaFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleEvaHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleEvaHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleEvaHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleEvaLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleEvaLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleEvaTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleEvaTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleFeet_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleFridaFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleFridaFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleFridaHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleFridaHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleFridaHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleFridaLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleFridaLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleFridaTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleFridaTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleGabiFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleGabiFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleGabiHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleGabiHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleGabiHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleGabiLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleGabiLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleGabiTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleGabiTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleHands_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleHelgaFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleHelgaFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleHelgaHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleHelgaHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleHelgaHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleHelgaLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleHelgaLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleHelgaTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleHelgaTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleIrenaFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleIrenaFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleIrenaHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleIrenaHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleIrenaHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleIrenaLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleIrenaLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleIrenaTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleIrenaTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleJudyFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleJudyFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleJudyHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleJudyHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleJudyHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleJudyLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleJudyLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleJudyTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleJudyTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleKeikoFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleKeikoFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleKeikoHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleKeikoHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleKeikoHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleKeikoLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleKeikoLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleKeikoTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleKeikoTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleLegs_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleLegsAbove | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleLindaFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleLindaFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleLindaHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleLindaHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleLindaHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleLindaLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleLindaLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleLindaTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleLindaTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleMariaFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleMariaFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleMariaHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleMariaHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleMariaHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleMariaLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleMariaLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleMariaTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleMariaTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleNaomiFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleNaomiFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleNaomiHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleNaomiHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleNaomiHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleNaomiLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleNaomiLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleNaomiTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleNaomiTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FemaleTorso_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Fence | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FenceKit | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FenceKitPlacing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FieldShovel | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Figs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FilteringBottle | retain | 10 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FireExtinguisher | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FirefighterAxe | retain | 52 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FirefighterAxe_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FirefighterAxe_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FirefighterJacket_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FirefighterJacket_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FirefighterJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FirefightersHelmet_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FirefightersHelmet_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FirefightersHelmet_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FirefightersHelmet_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FirefightersPants_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FirefightersPants_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FirefightersPants_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Fireplace | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FireplaceBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FireplaceFireBarrel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FireplaceIndoor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FireplaceTandoor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Firewood | retain | 6 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FireworksLauncher | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FirstAidKit | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FishingRod | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FishingRod_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FishingRod_Base_New | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FishNetTrap | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Altis | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_APA | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_BabyDeer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Base | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Bear | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Bohemia | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_BrainZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Cannibals | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_CDF | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Chedaki | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_CHEL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Chernarus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_CMC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Crook | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_DayZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_HunterZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Livonia | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_LivoniaArmy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_LivoniaPolice | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_NAPA | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_NSahrani | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Pirates | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Refuge | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Rex | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Rooster | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_RSTA | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Sakhal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Snake | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_SSahrani | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_TEC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_UEC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Wolf | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Zagorky | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flag_Zenit | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FlagCarrierCore | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FlashGrenade | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Flashlight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FlatCap_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FlatCap_BlackCheck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FlatCap_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FlatCap_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FlatCap_BrownCheck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FlatCap_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FlatCap_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FlatCap_GreyCheck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FlatCap_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FNOJacket | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FNOPants | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FNP45_MRDSOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FoodCan_100g_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FoodCan_100g_Opened_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FoodCan_250g_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FoodCan_250g_Opened_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Fortress | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FoxPelt | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FoxSteakMeat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FrontDrive | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FryingPan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FurCourierBag | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FurImprovisedBag | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxCartridge | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxCartridge_12Beanbag | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxCartridge_12Pellet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxCartridge_12RubberSlug | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxCartridge_12Slug | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxCartridge_22 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxCartridge_357 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxCartridge_40mm | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxCartridge_556 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxCartridge_762 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxCartridge_762x39 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxCartridge_9mm | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxCartridge_Flare | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxCartridge_Flare_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxCartridge_Flare_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxCartridge_Flare_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxCartridge_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FXCrWindLeaf1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FXCrWindLeaf2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FXCrWindLeaf3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxExploArmor1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxExploArmor2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxExploArmor3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxExploArmor4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_12Beanbag | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_12Pellet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_12RubberSlug | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_12Slug | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_22 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_308Win | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_357 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_40mm | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_40mmBlack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_40mmChemGas | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_40mmGreen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_40mmRed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_40mmWhite | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_45acp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_556 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_762 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_762x39 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_9mm | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_CupidsBolt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_Flare | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_Flare_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_Flare_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_Flare_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_HuntingBolt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_ImprovisedBolt_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxRound_ImprovisedBolt_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FXUSWindLeaf1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FXUSWindLeaf2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FXUSWindLeaf3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxWindGrass1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxWindGrass2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxWindLeaf1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxWindLeaf2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxWindLeaf3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxWindPollen1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:FxWindRock1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GardenLime | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GardenPlot | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GardenPlotGreenhouse | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GardenPlotPlacing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GardenPlotPolytunnel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GasMask | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GasMask_Filter | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GasMask_Filter_Improvised | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GermanShepherdPelt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieAtt_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieAtt_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieAtt_Mossy | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieAtt_Tan | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieAtt_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieAtt_Woodland | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieBushrag_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieBushrag_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieBushrag_Mossy | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieBushrag_Tan | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieBushrag_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieBushrag_Woodland | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieHood_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieHood_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieHood_Mossy | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieHood_Tan | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieHood_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieHood_Woodland | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieSuit_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieSuit_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieSuit_Mossy | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieSuit_Tan | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieSuit_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieSuit_Woodland | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieTop_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieTop_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieTop_Mossy | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieTop_Tan | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieTop_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GhillieTop_Woodland | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GiftBox_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GiftBox_Large | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GiftBox_Large_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GiftBox_Large_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GiftBox_Large_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GiftBox_Large_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GiftBox_Medium | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GiftBox_Medium_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GiftBox_Medium_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GiftBox_Medium_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GiftBox_Medium_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GiftBox_Small | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GiftBox_Small_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GiftBox_Small_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GiftBox_Small_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GiftBox_Small_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GiftWrapPaper | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GlassBottle | retain | 10 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GlowPlug | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GoatPelt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GoatSteakMeat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GorkaEJacket_Autumn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GorkaEJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GorkaEJacket_Flat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GorkaEJacket_PautRev | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GorkaEJacket_Summer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GorkaEJacket_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GorkaHelmet | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GorkaHelmet_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GorkaHelmet_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GorkaHelmetVisor | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GorkaPants_Autumn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GorkaPants_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GorkaPants_Flat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GorkaPants_PautRev | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GorkaPants_Summer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GorkaPants_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GP5GasMask | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GP5GasMask_Filter | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GPSReceiver | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GreatHelm | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GreenBellPepper | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Grenade_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Grenade_ChemGas | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Groza_Barrel_Grip | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Groza_Barrel_Short | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Groza_Barrel_Suppressor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Groza_LowerReceiver | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GrozaGL_LowerReceiver | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GrozaOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GulagJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GulagJacket_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GunCase_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GunCase_ColorBase | excluded-definition | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GunCase_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GunCase_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GunCaseKeys_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GunCaseKeys_Colorbase | excluded-definition | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GunCaseKeys_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:GunCaseKeys_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Guts | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hacksaw | retain | 59 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HalvaCan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HalvaCan_Opened | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hammer | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HandcuffKeys | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Handcuffs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HandcuffsLocked | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HandDrillKit | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HandDrillKitBirch | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HandDrillKitPalm | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HandSaw | retain | 43 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HandsCover_Improvised | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_1_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_1_1_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_1_1_BlackRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_1_1_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_1_1_BlueRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_1_1_RedRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_1_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_1_2_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_1_2_BlackRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_1_2_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_1_2_BlueRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_1_2_RedRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_2_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_2_1_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_2_1_BlackRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_2_1_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_2_1_BlueRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_2_1_RedRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_2_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_2_2_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_2_2_BlackRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_2_2_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_2_2_BlueRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Door_2_2_RedRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Hood | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Hood_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Hood_BlackRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Hood_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Hood_BlueRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Hood_RedRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Trunk | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Trunk_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Trunk_BlackRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Trunk_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Trunk_BlueRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Trunk_RedRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Wheel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchback_02_Wheel_Ruined | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackDoors_CoDriver | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackDoors_CoDriver_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackDoors_CoDriver_BlueRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackDoors_CoDriver_GreenRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackDoors_CoDriver_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackDoors_CoDriver_WhiteRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackDoors_Driver | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackDoors_Driver_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackDoors_Driver_BlueRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackDoors_Driver_GreenRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackDoors_Driver_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackDoors_Driver_WhiteRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackHood | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackHood_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackHood_BlueRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackHood_GreenRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackHood_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackHood_WhiteRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackTrunk | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackTrunk_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackTrunk_BlueRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackTrunk_GreenRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackTrunk_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackTrunk_WhiteRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackWheel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HatchbackWheel_Ruined | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hatchet | retain | 52 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HayHook | retain | 43 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Head | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Head_Default | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HeadCover_Improvised | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Headdress_Bear | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Headdress_Colorbase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Headdress_Fox | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Headdress_Wolf | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HeadlightH7 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HeadlightH7_Box | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Headtorch_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Headtorch_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Headtorch_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Heatpack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Helicopter | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HescoBox | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HighCapacityVest_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HighCapacityVest_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HighCapacityVest_ION | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HighCapacityVest_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HikingBoots_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HikingBoots_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HikingBoots_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HikingBootsLow_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HikingBootsLow_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HikingBootsLow_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HikingBootsLow_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HikingBootsLow_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HikingJacket_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HikingJacket_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HikingJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HikingJacket_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HikingJacket_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HipPack_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HipPack_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HipPack_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HipPack_Medical | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HipPack_Party | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HockeyHelmet_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HockeyHelmet_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HockeyHelmet_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HockeyHelmet_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HockeyHelmet_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HockeyMask | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HockeyStick | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HoloOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HoloOptic_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Honey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hoodie_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hoodie_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hoodie_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hoodie_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hoodie_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hoodie_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hoodie_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Hook | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:House | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HouseDestructible | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HouseHighCost | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HouseNoDestruct | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HumanSteakMeat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HunterPants_Autumn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HunterPants_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HunterPants_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HunterPants_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HunterPants_Spring | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HunterPants_Summer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HunterPants_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HuntingBag | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HuntingBag_Hannah | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HuntingJacket_Autumn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HuntingJacket_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HuntingJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HuntingJacket_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HuntingJacket_Spring | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HuntingJacket_Summer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HuntingJacket_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HuntingKnife | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HuntingOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HuntingVest | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HuntingVest_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:HuntingVest_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Iceaxe | retain | 9 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ImpactTestObjectTakistan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ImprovisedBag | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ImprovisedExplosive | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ImprovisedExplosivePlacing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ImprovisedFishingRod | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ImprovisedSuppressor | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:InjectionVial | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Inventory_Base | excluded-definition | 11 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:IodineTincture | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ItemBarrel | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ItemBook | excluded-definition | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ItemCompass | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ItemGPS | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ItemMap | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ItemOptics | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ItemOptics_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ItemSuppressor | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Jambiya | retain | 48 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Jeans_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Jeans_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Jeans_BlueDark | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Jeans_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Jeans_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Jeans_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Jeans_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Jig | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JoggingShoes_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JoggingShoes_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JoggingShoes_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JoggingShoes_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JoggingShoes_Violet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JoggingShoes_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JumpsuitJacket_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JumpsuitJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JumpsuitJacket_Gray | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JumpsuitJacket_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JumpsuitJacket_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JumpsuitPants_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JumpsuitPants_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JumpsuitPants_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JumpsuitPants_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JumpsuitPants_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JungleBoots_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JungleBoots_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JungleBoots_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JungleBoots_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JungleBoots_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:JungleBoots_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KameezShirt_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KameezShirt_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KameezShirt_BlueFlowers | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KameezShirt_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KameezShirt_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KameezShirt_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KameezShirt_NavyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KameezShirt_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KameezShirt_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KameezShirt_Pink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KameezShirt_Purple | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KameezShirt_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KameezShirt_SkyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KameezShirt_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KameezShirt_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KashtanOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KazuarOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Keffiyeh_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Keffiyeh_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Keffiyeh_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Keffiyeh_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Keffiyeh_Gray | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Keffiyeh_LightBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Keffiyeh_LightBrown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Keffiyeh_LightRed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Keffiyeh_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KitchenKnife | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KitchenTimer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Kiwi | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KobraOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:KukriKnife | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LabCoat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LactariusMushroom | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Airfield_Hangar_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Airfield_Hangar_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Airfield_Radar_Tall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Airfield_ServiceHangar_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Airfield_ServiceHangar_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Airfield_Small_Control | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Airfield_Small_Hangar | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Airport_Small_Hangar | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Airport_Small_Hangar2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Airport_Small_Main | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Barn_Brick1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Barn_Brick2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Barn_Metal_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Barn_Metal_Big_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Barn_Wood1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Barn_Wood2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bazaar_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bazaar_Flat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bazaar_Flat_Entrance | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bazaar_Flat_Half | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bazaar_Left | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bazaar_Right | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_alkohol | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_Beach | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_Bienvenudo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_cibulka | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_cigara_chernomorky | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_Escape | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_Everon | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_hey_buddy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_hlinik | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_likery_bardak | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_Livonia_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_Livonia_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_Nogova | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_notacola | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_pizza_presto | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_Riviera | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_seci_stroje | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_Skiresort | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_smadny_maskrnik | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_strana_noveho_radu | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_toaletak_armasan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_vodka | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_volte_cernaruske_hnuti | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_vstup_do_CDF | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bilboard_zlute_zgrynda | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Boat_Small1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Boat_Small10_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Boat_Small10_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Boat_Small2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Boat_Small3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Boat_Small4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Boat_Small5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Boat_Small6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Boat_Small7 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Boat_Small8_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Boat_Small8_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Boat_Small9 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Boat_Small9_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Boathouse | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Border_01_Guardhouse | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Border_02_Guardhouse | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Border_03_Guardhouse_AD | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Border_03_Guardhouse_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bunker1_Double | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bunker1_Left | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bunker1_Right | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bunker2_Double | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bunker2_Left | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bunker2_Right | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bunker3_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bunker3_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bunker_Basement_Civilian | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bunker_Basement_Medical | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bunker_Basement_Storage | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bunker_Shelter_Medical | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bunker_Shelter_Office | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Bunker_Shelter_Storage | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Buoy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_BusStation_building | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_BusStation_wall_bench | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_BusStop_City | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_BusStop_Village2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Cableway_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Cableway_Cart | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Cableway_Cart2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Cableway_Cart3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Cableway_Tower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Cableway_Tower_Slope | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Camp_House_brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Camp_House_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Camp_House_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Caravanserai_Back | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Caravanserai_Front | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Bastion | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Bastion2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Bastion2_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Bastion3_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Bastion_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Bergfrit | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Bergfrit2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Donjon | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Gate | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Stairs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Stairs_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall1_20 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall1_20_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall1_20_Turn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall1_20_Turn_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall1_Corner1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall1_Corner1_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall1_Corner2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall1_Corner2_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall1_End1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall1_End1_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall1_End2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall1_End2_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall2_30 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall2_30_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall2_Corner1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall2_Corner1_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall2_Corner2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall2_Corner2_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall2_End1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall2_End1_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall2_End2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_Wall2_End2_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_WallS_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_WallS_10_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_WallS_5_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_WallS_5_D_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_WallS_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Castle_WallS_End_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Cementworks_Conveyorhall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_CementWorks_ExpeditionA | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_CementWorks_ExpeditionB | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_CementWorks_ExpeditionC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_CementWorks_Hall1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_CementWorks_Hall2_Brick | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_CementWorks_Hall2_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_CementWorks_MillA | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_CementWorks_MillB | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_CementWorks_MillC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_CementWorks_RotFurnace | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_CementWorks_SiloBig1A | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_CementWorks_SiloBig1B | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Chapel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Chapel2_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Chapel2_White_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Chapel2_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Chapel2_Yellow_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Church1_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Church2_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Church2_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Church3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Church4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Church4_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Church4_Lightblue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Church4_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Church4_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Church4_Yellow_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_City_FireStation | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_City_FireStation_Takistan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_City_Hospital | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_City_Hospital_East | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_City_Hospital_Ghost1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_City_Hospital_Ghost2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_City_PoliceStation | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_City_PoliceStation_Enoch | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_City_School | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_City_School_East | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_City_School_Takistan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_City_Stand_FastFood | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_City_Stand_Grocery | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_City_Stand_News1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_City_Stand_News2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_City_Store | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_City_Store_WithStairs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_CoalPlant_Main | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Construction_Building | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Construction_Crane | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Construction_Crane_Tall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Construction_Crane_Tall_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Construction_House1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Construction_House2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Container_1Aoh | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Container_1Aoh_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Container_1Bo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Container_1Bo_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Container_1Mo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Container_1Mo_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Container_1Mo_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Container_1Mo_ION | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Container_1Mo_IONd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Container_1Moh | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Container_1Moh_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Container_1Moh_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Container_1Moh_ION | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Container_1Moh_ION_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Container_1Moh_IONd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_ContainerLocked_Blue_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_ContainerLocked_Orange_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_ContainerLocked_Red_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_ContainerLocked_Yellow_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Conveyor_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Dead_MassGrave | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Desert_Construction_Hopper | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Desert_DieselPowerPlant_Tank_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Desert_DieselPowerPlant_Tank_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Desert_Pipe_Big_18m_Ladder | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Desert_Pipe_Big_BuildL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Desert_Pipe_Big_BuildR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Desert_Pipe_Big_CornerL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Desert_Pipe_Big_CornerR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Desert_Pipe_Big_Ground1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Desert_Pipe_Big_Ground2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Desert_Smokestack_Metal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_DieselPowerPlant_Building | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_DieselPowerPlant_Tank_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_DieselPowerPlant_Tank_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_DistillationTower_Thick_High | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_DistillationTower_Thick_Low | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_DistillationTower_Thin_High | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_DistillationTower_Thin_Low | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_DryDock_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_DryDock_Middle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_ErodedEmbankment_01_dirt_straight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_ErodedEmbankment_01_dirt_turn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_ErodedEmbankment_01_dirt_wave | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_ErodedEmbankment_01_grass_straight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_ErodedEmbankment_01_grass_turn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_ErodedEmbankment_01_grass_wave | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Factory_Lathes | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Factory_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Farm_CowshedA | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Farm_CowshedB | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Farm_CowshedC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Farm_Hopper | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Farm_Hopper2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Farm_Watertower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Farm_WaterTower_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_FuelStation_Build | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_FuelStation_Build_Enoch | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_FuelStation_Build_Takistan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_FuelStation_Feed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_FuelStation_Feed_Enoch | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_FuelStation_Feed_Takistan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Garage_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Garage_Medium | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Garage_Office | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Garage_Row_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Garage_Row_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Garage_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Garage_Tall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Gate_M1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Gate_Small_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Gate_Small_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Gate_Small_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Gate_Small_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Gate_Stone | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Gate_Tall_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Gate_Tall_Blue2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Gate_Tall_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Gate_Tall_Green2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Gate_Tall_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Gate_Tall_Red2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Gate_Tall_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Gate_Tall_Yellow2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Geoplant_CoolingStack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Geoplant_Corridor_Main | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Geoplant_DrillTower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Geoplant_MainHall_Left | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Geoplant_MainHall_Middle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Geoplant_MainHall_Right | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Geoplant_MaintenanceHall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Geoplant_MaintenanceHall_Corridor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Geoplant_OpenTank | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Geoplant_PipeHall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Geoplant_PowerHall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Geoplant_PowerHall_Corridor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Geoplant_PowerHall_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Geoplant_Well_Edgy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Geoplant_Well_Round | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Guardhouse | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HBarrierTower_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HealthCare_Takistan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Hospital_Takistan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Hotel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Hotel_Damaged | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1B01_Pub | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1C1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1C1_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1C1_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1M1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1M2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1M2_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1M2_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1M3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1M3_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1M3_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1M4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1M4_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1M4_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1M4_Dam3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1M5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1S1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1S2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1S2_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W01_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W02_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W03_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W04 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W04_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W05 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W05_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W06 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W06_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W07 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W07_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W08 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W08_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W08_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W09 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W09_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W10_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W11 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W11_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W12_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W13_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W13_Dam_NoIvy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W13_Dam_Snow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W14_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W14_Dam_Snow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W15_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_1W15_Dam_Snow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2B01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2B02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2B03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2B04 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2C1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2C1_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2C1_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2C1_Dam3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2C2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2C2_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2C2_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2C2_Dam3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2C3_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2C3_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2C3_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2C4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2C4_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2C4_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2C4_Dam3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2M1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2M1_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2M1_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2M1_Dam2_NAVMESHTEST | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2M2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2M2_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2M2_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2M2_Dam3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2S1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2S1_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2S1_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2S1_Dam3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2S1_Dam4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2S2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2S2_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2W01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2W01_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2W02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2W03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2W03_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2W04 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2W04_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_2W04_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_3C1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_3C1_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_3C1_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_3C1_Dam3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_3C1_Dam4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_3S1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_3S1_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_3S1_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_3S1_Dam3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_3S2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_3S2_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_3S2_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_House_3S2_Dam3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_1F1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_1F2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_1F3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_1F4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_1F_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2C1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2C1_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2C1_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2C1_Dam3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2C1_Dam4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2C2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2C_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2C_Corner2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2C_Corner3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2C_Corner_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2F1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2F2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2F3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2F4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2F5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2F6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2F7 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2F8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2F9 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_2F_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_3C1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_3C2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_3C3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_3C4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_3C_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_3C_Corner2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_3C_Corner3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_3F1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_3F2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_3F_Corner1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_3F_Corner2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_4C1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_HouseBlock_5F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_12m_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_12m_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_12m_03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_12m_Left_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_12m_Left_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_12m_Left_03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_12m_Right_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_12m_Right_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_12m_Right_03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_36m_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_36m_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_36m_03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_36m_Down_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_36m_Down_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_36m_Down_03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_Collapsed_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_End_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_Entrance_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_Merge_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_Split_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_IrrigationTunnel_Start_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_KirovDam_House_A | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_KirovDam_House_B | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_KirovDam_Outlet_A | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_KirovDam_Outlet_B | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_KirovDam_Overflow_Top | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_KirovDam_Penstock_Connector | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_KirovDam_PowerPlant | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_KirovDam_PowerPlant_Base_A | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_KirovDam_Statue_A | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_KirovDam_Statue_Staircase | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_KirovDam_Statue_Walkway_A | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_KirovDam_Statue_Walkway_B | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ladder | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ladder_Half | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Lamp_City1_amp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Lighthouse | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Lunapark_Autodrome | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Lunapark_Bumper_Car | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Lunapark_Carousel_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Lunapark_Carousel_Swan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Lunapark_Ferris_wheel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Lunapark_Shooting_Gallery | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Market1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Market2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mausoleum_Small1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mausoleum_Small1_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mausoleum_Small1_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mausoleum_Small1_Dam3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mausoleum_Small2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mausoleum_Small2_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Medical_Tent_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Medical_Tent_Shower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_AircraftShelter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Airfield_HQ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Antena_K7 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_ATC_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_ATC_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_ATC_Small_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Barracks1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Barracks2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Barracks3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Barracks4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Barracks5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Barracks5_Basement | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Barracks5_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Barracks6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Barracks6_Ghost1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Barracks6_Ghost2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Barracks6_Old | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Barracks_Round | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Barracks_Round_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_CamoNet_Roof_east | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_ContainerHabitat_Armory | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_ContainerHabitat_Armory_Locked_Green_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_ContainerHabitat_Medical | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_ContainerHabitat_Office | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_ContainerWatchTower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_ControlTower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_ControlTower_East | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_FireStation | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Fortified_Nest_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Fortified_Nest_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Fortified_Nest_Watchtower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Fortified_Nest_Watchtower_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_GuardBox_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_GuardBox_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_GuardBox_Smooth | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Guardhouse1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Guardhouse2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_GuardHouse3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_GuardShed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_GuardTower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Radar_Mobile1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Radar_Mobile2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Radar_Mobile3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Radome_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Radome_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_ReinforcedTank1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_ReinforcedTank1_Sakhal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_ReinforcedTank2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_ReinforcedTank2_Sakhal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big1_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big1_1_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big1_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big1_2_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big1_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big1_3_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big1_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big1_4_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big1_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big1_5_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big2_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big2_1_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big2_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big2_2_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big2_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big2_3_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big2_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big2_4_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big2_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big2_5_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big2_Desert_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big3_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big4_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big5_1_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big5_2_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big5_3_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big5_4_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tent_Big5_5_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mil_Tower_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Minaret1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Minaret2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mine_Building | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mine_Building_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_Calvary1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_misc_chickenCoop | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_DeerStand1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_DeerStand2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_DogHouse | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_FeedShack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_FireBarrel_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_FireBarrel_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_FireBarrel_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_FireBarrel_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_Greenhouse | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_Pallet_Spawn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_Pallet_Spawn_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_Polytunnel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_Scaffolding | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_Table_Large_Spawn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_Table_Market_Spawn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_Through_Static | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_Through_Static_Frozen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_Through_Trailer_Frozen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_Toilet_Dry | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_Toilet_Mobile | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_TrailRoof_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_TrailRoof_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_Well_Pump_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_Well_Pump_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_WoodenCrate_Spawn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Misc_WoodenCrate_Spawn_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_MobileLaboratory | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_MobileLaboratory_Ruin | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Model_plane_mig21 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Monument_mig21 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Monument_T34 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_MooringBuoy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_MooringBuoyNasdara | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mosque_Big_Gate | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mosque_Big_Main | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mosque_Big_Minaret1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mosque_Big_Minaret2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mosque_Big_Side | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mosque_Big_Wall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Mosque_Big_Wall_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Office1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Office2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Office2_Ghost1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Office2_Ghost2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Office_Municipal1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Office_Municipal2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Oil_DrillTower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Oil_Pump | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_OilRefinery_Makeshift_Boiler | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_OutsideThermometer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_OutsideThermometer_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_OutsideThermometer_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_OutsideThermometer_2_wall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Pier_Concrete4_Ladders | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Pier_Concrete5_Ladder | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Pier_Crane2_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Pier_Crane2_Top | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Pier_Crane_A | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Pier_Crane_B | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Pier_Crane_Submarine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Pier_Floating_50m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Pier_Floating_Bridge | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Pier_Wooden3_Ladder | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Pipe_Big_BuildL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Pipe_Big_BuildR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Pipe_Big_CornerL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Pipe_Big_CornerR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Pipe_Big_Ground1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Pipe_Big_Ground2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_PoliceStation_Large_Takistan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_PoliceStation_Small_Takistan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Power_Pole_Conc1_Amp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Power_Pole_Conc4_Lamp_Amp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Power_Pole_Wood1_Amp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Power_Pole_Wood1_Lamp_Amp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Power_Station | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Power_Transformer_Build | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Power_VHV_Tower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Power_VHV_Tower_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Prison_Main | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Prison_Side | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Prison_Wall_Large | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Quarry_Main | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Radio_building | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Radio_building_East | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Radio_PanelBig | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Radio_PanelPAS | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Rail_Station_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Rail_Station_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Rail_Warehouse_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_ContainerHabitat_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_ContainerHabitat_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_ContainerHabitat_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_ContainerHabitat_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_Tent_Big1_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_Tent_Big1_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_Tent_Big1_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_Tent_Big1_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_Tent_Big1_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_Tent_Big1_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_Tent_Big1_7 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_Tent_Big1_Desert_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_Tent_Big2_Desert_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_Tent_Big5_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_Tent_Big5_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_Tent_Big5_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_Tent_Big5_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_Tent_Big5_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Refugee_Tent_Big5_Desert_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Repair_Center | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_ResearchInstitute_Mirnyy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Roadblock_Table | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Roadblock_Table_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Roadblock_WoodenCrate | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Roadblock_WoodenCrate_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_RocketBase_Barracks | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_RocketBase_FuelingStation | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_RocketBase_FuelTank | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_RocketBase_FuelTank_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_RocketBase_Garages | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_RocketBase_LaunchControl | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_RocketBase_MissileStorage | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_RocketBase_MissileStorage2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_BusStop_Village2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Camp_House | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Chapel2_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Chapel2_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Chimney | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Church2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Church2_NoIvy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Highway_Pillar1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Highway_Pillar1_Garage | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_1B01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_1W01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_1W02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_1W03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_1W04 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_1W05 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_1W06 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_1W07 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_1W08 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_1W09 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_1W10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_1W11 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_1W12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_1W13 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_2B01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_2B02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_2B03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_2B04 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_2W01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_2W02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_2W03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_2W04 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_House_2W05 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseBig1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseBig1_Half | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseBig1_NoIvy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseBig1_NoIvy_Half | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseBig2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseBig2_Half | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseBig2_NoIvy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseBig2_NoIvy_Half | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseBig3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseBig3_Half | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseBig3_NoIvy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseBig3_NoIvy_Half | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseSmall1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseSmall1_Half | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseSmall1_NoIvy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseSmall1_NoIvy_Half | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseSmall2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_HouseSmall2_NoIvy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Mil_ControlTower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Mil_GuardBox_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Mil_GuardBox_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Mil_GuardBox_Smooth | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Shed_Closed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Shed_Closed2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Slum_House2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Slum_House3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Slum_House4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ruin_Smokestack_Metal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Sawmill_Building | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Sawmill_Illuminanttower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Shed_Closed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Shed_Closed2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Shed_Closed_Small1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Shed_Closed_Small2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Shed_M1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Shed_M3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Shed_M4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Shed_W1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Shed_W2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Shed_W3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Shed_W4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Shed_W5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Shed_W6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ship_Big_BackA | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ship_Big_BackB | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ship_Big_Castle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ship_Big_FrontA | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ship_Big_FrontA2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ship_Big_FrontB | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Ship_Medium2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Slum_House1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Slum_House2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Slum_House3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Slum_House4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Slum_House5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Slum_House6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Slum_House7 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Smokestack_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Smokestack_Brick | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Smokestack_Medium | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Smokestack_Metal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_SolarPowerPlant_Tower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_SolarPowerPlant_Tower_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_SolarPowerPlant_Tower_Old | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Static_An2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Static_An2_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Static_Mi8_Civilian | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Stockyard_Crusher | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Stockyard_Reclaimer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Stockyard_Shiploader | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Stockyard_Shiploader_Arm | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Store_CarService | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Store_CarService_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Store_CarService_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Store_Street1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Store_Street1_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Store_Street1_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Store_Street1_Dam3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Store_Street2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Store_Street2_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Store_Street2_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Store_Street2_Dam3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_leaf_long_curve_left | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_leaf_long_curve_left_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_leaf_long_curve_right | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_leaf_long_curve_right_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_leaf_long_snake | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_leaf_long_straight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_leaf_long_straight_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_leaf_short_arrow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_leaf_short_slanted | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_leaf_short_slanted_inv | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_leaf_short_straight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_moss_long_curve_left | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_moss_long_curve_left_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_moss_long_curve_right | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_moss_long_curve_right_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_moss_long_snake | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_moss_long_straight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_moss_long_straight_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_moss_short_arrow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_moss_short_slanted | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_moss_short_slanted_inv | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_moss_short_straight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_sand_long_curve_left | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_sand_long_curve_right | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_sand_long_snake | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_sand_long_straight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_sand_short_arrow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_sand_short_slanted | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_sand_short_slanted_inv | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_streambed_sand_short_straight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Submarine_Back | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Submarine_Front | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Submarine_Middle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TajbegPalace_BasementCell | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TajbegPalace_Left | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TajbegPalace_Left_Ghost | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TajbegPalace_Middle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TajbegPalace_Middle_Ghost | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TajbegPalace_Platform_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TajbegPalace_Platform_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TajbegPalace_Platform_03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TajbegPalace_Platform_04 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TajbegPalace_Platform_05 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TajbegPalace_Platform_06 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TajbegPalace_Platform_07 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TajbegPalace_Platform_08 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TajbegPalace_Platform_Basement_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TajbegPalace_Platform_Basement_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TajbegPalace_Right | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TajbegPalace_Right_Ghost | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tank_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tank_Big2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tank_Big3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tank_Medium_Stairs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tenement_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tenement_High_Apartments1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tenement_High_Apartments2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tenement_High_Construction | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tenement_Medium | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tenement_Medium_Ghost1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tenement_Medium_Ghost2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tenement_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tenement_Small_Brick | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tenement_Small_Brick_Ghost1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tenement_Small_Brick_Ghost2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tenement_Small_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tenement_Small_Brown_Ghost1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tenement_Small_Brown_Ghost2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tenement_Small_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tenement_Small_Yellow_Ghost1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tenement_Small_Yellow_Ghost2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tisy_Barracks | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tisy_Base_cooler | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tisy_BigHangar_A | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tisy_BigHangar_B | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tisy_Garages | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tisy_Garages2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tisy_Garages2_Sakhal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tisy_Garages3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tisy_HQ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tisy_KitchenRoom | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tisy_LaunchControl | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tisy_RadarB_Antenna | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tisy_RadarB_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tisy_RadarPlatform_Top | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tower_TC1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tower_TC2_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tower_TC2_Mid | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tower_TC2_Top | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tower_TC3_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tower_TC3_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tower_TC4_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tower_TC4_Mid | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tower_TC4_Top | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tower_TC5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tower_TC6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TradTent_Large | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TradTent_Medium1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TradTent_Medium2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TradTent_Medium3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_TradTent_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Train_742_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Train_742_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Train_Wagon_Box | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Train_Wagon_Box_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Train_Wagon_Box_Mil_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Bend_Left | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Biathlon_Left | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Biathlon_Right | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Collapsed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Collapsed_Bus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Collapsed_Obstacle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Connected | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Connected_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Connected_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Connected_03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Emergency_Stop | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Emergency_Stop_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Emergency_Stop_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Emergency_Stop_03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Entrance | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Entrance_Collapsed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Entrance_HeadWall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Entrance_WingWall_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Entrance_WingWall_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Maintenance_Room | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Medical_Room | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Single_2_Collapsed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Single_Bunker | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Single_Collapsed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Single_Emergency_Stop | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Single_Straight_15m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Straight_10m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Straight_15m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Tunnel_Straight_50m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Corridor_Connector | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Corridor_Connector_Inv | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Corridor_Main_Both | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Corridor_Main_Left | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Corridor_Main_Right | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Entrance | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Floor_Comms | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Floor_Crew | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Panel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Panel_Lever | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Stairs_Block | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Stairs_Block_Corridor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Stairs_Block_Corridor_NoDoor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Stairs_Block_Terminator | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Stairs_Collapsed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Stairs_Exit | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Stairs_Start | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Storage_Ammo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Storage_Ammo2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Storage_Barracks | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Storage_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Storage_Big_Vent | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Storage_Hospital | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Storage_Laboratory | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Storage_POX | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Storage_POX2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Storage_Prison | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Storage_Workshop | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Tunnel_Single | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Tunnel_Single_Left | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_Tunnel_Single_Right | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_WaterMaintenance | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_WaterReservoir | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Underground_WaterReservoir_Water | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_VASICore | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Victory_Arch | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Villa | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Villa_Dam1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Villa_Dam2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Villa_Dam3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Village_HealthCare | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Village_HealthCare_East | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Village_HealthCare_Enoch | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Village_HealthCare_Ghost1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Village_HealthCare_Ghost2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Village_PoliceStation | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Village_PoliceStation_East | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Village_PoliceStation_Enoch | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Village_Pub | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Village_store | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Village_Store_East | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Village_Store_Enoch | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_BackAlley_01_l_gate_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_FenForest_Gate | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Camp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Fen2_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Fen2_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Fen3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Fen4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_FenG | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_FenG_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_FenG_Big_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_FenG_Big_Open | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_FenG_Big_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_FenG_Open | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_FenR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_FenR_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_FenR_Big_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_FenR_Big_Open | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_FenR_Big_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_FenR_Open | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Ind1_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Ind1_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Ind2A_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Ind2A_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Ind2B_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Ind2B_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Ind2Rail_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Ind2Rail_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Ind3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_IndCnc4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_IndCnc4_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_IndCnc4_Desert_Low | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_IndCnc4_Low | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Tin6_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Tin6_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Village | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Village_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Village_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Wood1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Wood2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Wood3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wall_Gate_Wood4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WarheadStorage_Bunker_Facility | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WarheadStorage_Entrance | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WarheadStorage_Entrance_Roof | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WarheadStorage_Main | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WarheadStorage_PowerStation | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WarheadStorage_Room1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WarheadStorage_Room2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WarheadStorage_Room3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WarheadStorage_Room4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WarheadStorage_Top | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Water_Station | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Water_Well1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Water_Well2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WaterSpring_Water | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WaterTower_Large_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WaterTower_Large_01_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WaterTower_Large_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WaterTower_Large_02_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WaterTower_Medium_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WaterTower_Medium_01_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WaterTower_Medium_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WaterTower_Medium_02_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WaterTower_Medium_03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WaterTower_Medium_03_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WaterTower_Small_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WaterTower_Small_01_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WaterTower_Small_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WaterTower_Small_02_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WaterWell_Brick | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_WindPowerPlant_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Workshop1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Workshop2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Workshop3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Workshop4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Workshop5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Workshop_FuelStation | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_ArmedURAL_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_ArmedURAL_TK_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Bradley | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Bradley_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_BTR70_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_BTR70_TK_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_C130J | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_C130J_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_C130J_Body | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_C130J_Cargo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Car_ThreeDoors | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Car_TwoDoors | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Caravan_MGreen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Caravan_MRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Caravan_WBrown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Caravan_WGreen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Harverster | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Harvester_head_trailer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb01_aban1_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb01_aban1_blue_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb01_aban1_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb01_aban1_green_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb01_aban1_police | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb01_aban1_police_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb01_aban1_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb01_aban1_white_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb01_aban2_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb01_aban2_blue_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb01_aban2_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb01_aban2_green_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb01_aban2_police | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb01_aban2_police_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb01_aban2_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb01_aban2_white_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb02_aban1_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb02_aban1_black_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb02_aban1_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb02_aban1_blue_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb02_aban1_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb02_aban1_red_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb02_aban2_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb02_aban2_black_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb02_aban2_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb02_aban2_blue_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb02_aban2_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_hb02_aban2_red_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Ikarus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Ikarus_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Lada_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Lada_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_LR_Armed_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_LR_Armed_TK_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_LR_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_LR_TK_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Mi8_Civilian | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Mining_Excavator | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Mining_HaulTruck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_offroad02_aban1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_offroad02_aban1_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Offroad02_Aban1_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Offroad02_Aban1_TK_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_offroad02_aban2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_offroad02_aban2_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Offroad02_Aban2_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Offroad02_Aban2_TK_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Offroad02_Medic_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Offroad02_Medic_TK_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Pickup01_Aban_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Pickup01_Aban_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Pickup01_Aban_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Pickup01_Aban_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_pickup01_aban_yellow_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Pickup01_Armed_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_S1023_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_S1023_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_S1023_Medic_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_S1023_Medic_Beige_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_S1023_Medic_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_SCUDLauncher_Loaded | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_SCUDLauncher_Loaded_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed01_aban1_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed01_aban1_black_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed01_aban1_police | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed01_aban1_police_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed01_aban1_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed01_aban1_white_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed01_aban1_wine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed01_aban1_wine_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed01_aban2_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed01_aban2_black_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed01_aban2_police | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed01_aban2_police_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed01_aban2_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed01_aban2_white_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed01_aban2_wine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed01_aban2_wine_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed02_aban1_grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed02_aban1_grey_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_sed02_aban1_police | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_sed02_aban1_police_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed02_aban1_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed02_aban1_red_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed02_aban1_yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed02_aban1_yellow_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed02_aban2_grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed02_aban2_grey_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_sed02_aban2_police | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_sed02_aban2_police_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed02_aban2_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed02_aban2_red_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed02_aban2_yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_sed02_aban2_yellow_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Sed02_Aban3_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Sed02_Aban3_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Sed02_Aban3_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Tractor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Tractor_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Trailer_Closed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Trailer_Closed_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Trailer_Double_Tanker_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Trailer_Double_Tanker_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Trailer_Double_Tanker_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Trailer_Double_Tarp_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Trailer_Double_Tarp_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Trailer_Double_Tarp_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Trailer_Double_Tarp_Yellow_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Trailer_Double_TarpC_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Trailer_Double_TarpC_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Trailer_Double_TarpC_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Trailer_Double_TarpD_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Trailer_Double_TarpD_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Trailer_Double_TarpD_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_truck01_aban1_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_truck01_aban1_blue_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Truck01_Aban1_Cistern | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Truck01_Aban1_Cistern_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_truck01_aban1_firetruck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_truck01_aban1_firetruck_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_truck01_aban1_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_truck01_aban1_green_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_truck01_aban1_orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_truck01_aban1_orange_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_truck01_aban2_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_truck01_aban2_blue_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Truck01_Aban2_Cistern | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Truck01_Aban2_Cistern_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_truck01_aban2_firetruck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_truck01_aban2_firetruck_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_truck01_aban2_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_truck01_aban2_green_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_truck01_aban2_orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_wreck_truck01_aban2_orange_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Truck02_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Truck02_Blue_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Truck02_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Truck02_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Truck02_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Uaz | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_UAZ_Aban1_Police | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_UAZ_Aban2_Police | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Uaz_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_UAZ_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_UAZ_TK_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_URAL_Chassis_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_URAL_Chassis_TK_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_V3S | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_V3S_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Volha_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Volha_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Land_Wreck_Volha_Police | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LandMineTrap | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Lard | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LargeGasCanister | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LargeTent | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LargeTentBackPack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LargeTentClutterCutter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LargeTentPlacing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Lassi_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Lassi_Mango | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Lassi_Masala | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Lassi_Mint | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeafCrown_Autumn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeafCrown_Colorbase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeafCrown_Spring | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeafCrown_Summer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeafCrown_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherBelt_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherBelt_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherBelt_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherBelt_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherBelt_Lizard | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherBelt_Natural | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherGloves_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherGloves_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherGloves_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherGloves_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherGloves_Natural | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherHat_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherHat_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherHat_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherHat_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherHat_Natural | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherHipPack_Colorbase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherHipPack_Lizard | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherJacket_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherJacket_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherJacket_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherJacket_Natural | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherKnifeSheath | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherPants_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherPants_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherPants_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherPants_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherPants_Natural | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherSack_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherSack_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherSack_Brown | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherSack_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherSack_Natural | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherSewingKit | retain | 8 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherShirt_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherShirt_Natural | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherShoes_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherShoes_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherShoes_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherShoes_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherShoes_Natural | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherStorageVest_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherStorageVest_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherStorageVest_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherStorageVest_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LeatherStorageVest_Natural | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LegsCover_Improvised | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LinenVest_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LinenVest_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LinenVest_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LinenVest_DarkGrey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LinenVest_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LinenVest_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LinenVest_NavyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LizardKnifeSheath | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LizardMeat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LizardPelt | retain | 4 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Lockpick | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LongrangeOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LongTorch | retain | 4 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LongWoodenStick | retain | 14 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LowTierFemaleZombieBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LowTierMaleZombieBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LowTierZombieFemaleBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LowTierZombieMaleBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:LugWrench | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Lunchmeat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Lunchmeat_Opened | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M18SmokeGrenade_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M18SmokeGrenade_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M18SmokeGrenade_Purple | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M18SmokeGrenade_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M18SmokeGrenade_Red_Contaminated | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M18SmokeGrenade_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M18SmokeGrenade_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M249_Bipod | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M249_Hndgrd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M249_RisHndgrd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_CarryHandleOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_CQBBttstck | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_CQBBttstck_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_CQBBttstck_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_MPBttstck | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_MPBttstck_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_MPBttstck_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_MPHndgrd | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_MPHndgrd_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_MPHndgrd_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_OEBttstck | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_OEBttstck_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_OEBttstck_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_PlasticHndgrd | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_PlasticHndgrd_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_PlasticHndgrd_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_RISHndgrd | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_RISHndgrd_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_RISHndgrd_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_Suppressor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M4_T3NRDSOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M65Jacket_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M65Jacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M65Jacket_Khaki | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M65Jacket_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M65Jacket_Tan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M67Grenade | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M68Optic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M79DummyOptics | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:M9A1_Bayonet | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Mace | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Machete | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Mackerel | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MackerelFilletMeat | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MacrolepiotaMushroom | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Magnum_Cylinder | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Magnum_Cylinder_Gold | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Magnum_Ejector | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Magnum_Ejector_Gold | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MakarovPBSuppressor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamDecayedDarkFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamDecayedDarkHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamDecayedDarkLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamDecayedDarkTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamDecayedFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamDecayedHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamDecayedLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamDecayedLighterDarkFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamDecayedLighterDarkHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamDecayedLighterDarkLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamDecayedLighterDarkTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamDecayedTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamHead_BeardEnd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamHead_BeardStart | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleAdamTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleBorisFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleBorisFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleBorisHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleBorisHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleBorisHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleBorisLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleBorisLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleBorisTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleBorisTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleCyrilFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleCyrilFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleCyrilHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleCyrilHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleCyrilHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleCyrilLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleCyrilLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleCyrilTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleCyrilTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleDenisFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleDenisFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleDenisHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleDenisHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleDenisHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleDenisLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleDenisLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleDenisTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleDenisTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleEliasFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleEliasFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleEliasHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleEliasHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleEliasHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleEliasLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleEliasLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleEliasTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleEliasTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleFeet_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleFrancisFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleFrancisFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleFrancisHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleFrancisHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleFrancisHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleFrancisLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleFrancisLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleFrancisTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleFrancisTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleGuoFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleGuoFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleGuoHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleGuoHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleGuoHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleGuoLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleGuoLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleGuoTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleGuoTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleHands_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleHassanFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleHassanFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleHassanHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleHassanHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleHassanHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleHassanLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleHassanLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleHassanTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleHassanTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleIndarFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleIndarFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleIndarHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleIndarHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleIndarHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleIndarLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleIndarLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleIndarTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleIndarTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleJoseFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleJoseFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleJoseHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleJoseHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleJoseHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleJoseLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleJoseLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleJoseTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleJoseTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleKaitoFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleKaitoFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleKaitoHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleKaitoHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleKaitoHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleKaitoLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleKaitoLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleKaitoTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleKaitoTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleLegs_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleLegsAbove | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleLewisFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleLewisFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleLewisHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleLewisHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleLewisHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleLewisLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleLewisLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleLewisTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleLewisTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleManuaFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleManuaFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleManuaHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleManuaHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleManuaHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleManuaLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleManuaLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleManuaTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleManuaTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleNikiFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleNikiFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleNikiHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleNikiHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleNikiHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleNikiLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleNikiLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleNikiTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleNikiTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleOliverFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleOliverFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleOliverHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleOliverHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleOliverHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleOliverLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleOliverLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleOliverTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleOliverTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MalePeterFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MalePeterFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MalePeterHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MalePeterHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MalePeterHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MalePeterLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MalePeterLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MalePeterTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MalePeterTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleQuinnFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleQuinnFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleQuinnHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleQuinnHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleQuinnHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleQuinnLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleQuinnLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleQuinnTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleQuinnTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleRolfFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleRolfFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleRolfHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleRolfHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleRolfHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleRolfLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleRolfLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleRolfTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleRolfTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleSethFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleSethFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleSethHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleSethHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleSethHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleSethLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleSethLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleSethTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleSethTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleTaikiFeet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleTaikiFeetDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleTaikiHands | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleTaikiHandsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleTaikiHead | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleTaikiLegs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleTaikiLegsDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleTaikiTorso | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleTaikiTorsoDecayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MaleTorso_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Man | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Man_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ManSuit_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ManSuit_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ManSuit_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ManSuit_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ManSuit_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ManSuit_DarkGrey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ManSuit_Khaki | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ManSuit_LightGrey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ManSuit_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Marmalade | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Matchbox | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MeatTenderizer | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MedicalScrubsHat_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MedicalScrubsHat_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MedicalScrubsHat_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MedicalScrubsHat_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MedicalScrubsPants_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MedicalScrubsPants_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MedicalScrubsPants_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MedicalScrubsPants_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MedicalScrubsShirt_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MedicalScrubsShirt_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MedicalScrubsShirt_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MedicalScrubsShirt_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MedievalBoots | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MediumGasCanister | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MediumTent | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MediumTent_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MediumTent_GreenPlacing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MediumTent_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MediumTent_OrangePlacing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MediumTentClutterCutter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MediumTentPlacing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Megaphone | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MeleeItemBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MensShalwarPants_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MensShalwarPants_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MensShalwarPants_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MensShalwarPants_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MensShalwarPants_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MensShalwarPants_NavyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MensShalwarPants_SkyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MensShalwarPants_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MessTin | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MetalPlate | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MetalWire | retain | 7 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MetalWireLocked | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Mich2001Helmet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryBelt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryBeret_CDF | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryBeret_ChDKZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryBeret_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryBeret_NZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryBeret_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryBeret_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryBeret_UN | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryBoots_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryBoots_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryBoots_Bluerock | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryBoots_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryBoots_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryBoots_Redpunk | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryCap_BDU | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryCap_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryCap_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitaryCap_Woodland | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitarySweater_Chernarus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitarySweater_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitarySweater_Livonia | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MilitarySweater_NoPatch | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MimeMask_Female | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MimeMask_Male | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MiniDress_BlueChecker | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MiniDress_BlueWithDots | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MiniDress_BrownChecker | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MiniDress_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MiniDress_GreenChecker | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MiniDress_Pink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MiniDress_PinkChecker | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MiniDress_RedChecker | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MiniDress_WhiteChecker | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Misc_Spotlight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Misc_TirePile_Burning_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MK4Optic_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MK4Optic_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MK4Optic_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MK4Optic_Tan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MorozkoHat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Morphine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MorsecodeLeaflet_blood | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MorsecodeLeaflet_coffee | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MorsecodeLeaflet_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MorsecodeLeaflet_fire | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MortarMix | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MortarMix_Opened | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Mosin_Bayonet | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Mosin_Compensator | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MotoHelmet_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MotoHelmet_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MotoHelmet_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MotoHelmet_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MotoHelmet_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MotoHelmet_Lime | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MotoHelmet_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MotoHelmet_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MotoHelmet_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_01_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_01_ColorBase | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_01_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_01_Wheel_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_01_Wheel_1_Ruined | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_01_Wheel_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_01_Wheel_2_Ruined | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_01_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_ColorBase | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_ShieldFront_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_ShieldFront_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_ShieldFront_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_ShieldFront_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_ShieldFront_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_ShieldLeft_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_ShieldLeft_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_ShieldLeft_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_ShieldLeft_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_ShieldLeft_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_ShieldRight_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_ShieldRight_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_ShieldRight_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_ShieldRight_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_ShieldRight_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_Wheel_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_Wheel_1_Ruined | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_Wheel_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_Wheel_2_Ruined | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Motorbike_02_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MotorbikeScript | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MotorbikeWheel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MouflonPelt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MouflonSteakMeat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MountainBag_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MountainBag_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MountainBag_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MountainBag_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MountainBag_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MouthRag | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MP5_Compensator | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MP5_PlasticHndgrd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MP5_RailHndgrd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MP5k_StockBttstck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:MushroomBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Nail | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NailBox | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NailedBaseballBat | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NavyUniformJacket | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NavyUniformPants | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCBootsBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCBootsGray | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCBootsWhite | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCBootsYellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCGloves_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCGlovesGray | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCGlovesYellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCHoodBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCHoodGray | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCHoodWhite | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCHoodYellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCJacketBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCJacketGray | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCJacketWhite | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCJacketYellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCPack_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCPack_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCPack_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCPack_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCPantsBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCPantsGray | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCPantsWhite | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NBCPantsYellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Netting | retain | 12 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NewHockeyStick | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NioshFaceMask | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NonStrategic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NonStrategic_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NorseHelm | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NurseDress_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NurseDress_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NurseDress_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NVGHeadstrap | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NVGoggles | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:NylonKnifeSheath | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OBRCap_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OBRCap_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OBRCap_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OBRJacket_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OBRJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OBRJacket_Officer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OBRJacket_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OBRPants_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OBRPants_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OBRPants_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ObsoleteFishingRod | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OfficerHat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Door_1_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Door_1_1_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Door_1_1_BeigeRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Door_1_1_Rust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Door_1_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Door_1_2_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Door_1_2_BeigeRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Door_1_2_Rust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Door_2_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Door_2_1_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Door_2_1_BeigeRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Door_2_1_Rust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Door_2_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Door_2_2_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Door_2_2_BeigeRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Door_2_2_Rust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Hood | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Hood_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Hood_BeigeRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Trunk | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Trunk_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Trunk_BeigeRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Trunk_Rust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Wheel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Offroad_02_Wheel_Ruined | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OffroadHatchback | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OffroadHatchback_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OffroadHatchback_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OKZKCap_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OKZKCap_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OKZKCap_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OMKJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OMKJacket_Navy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OMKPants_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OMKPants_Navy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OMNOGloves_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OMNOGloves_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OMNOGloves_Gray | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OrientalMachete | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OrienteeringCompass | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:OvenIndoor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:P1907_Bayonet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PaddedGloves_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PaddedGloves_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PaddedGloves_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PaddedGloves_Threat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Paddle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PainkillerTablets | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Pajka | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Pajka_Opened | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PakolHat_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PakolHat_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PakolHat_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PakolHat_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PakolHat_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PakolHat_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Paper | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ParamedicJacket_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ParamedicJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ParamedicJacket_Crimson | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ParamedicJacket_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ParamedicPants_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ParamedicPants_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ParamedicPants_Crimson | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ParamedicPants_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PartyTent | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PartyTent_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PartyTent_BluePlacing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PartyTent_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PartyTent_BrownPlacing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PartyTent_Lunapark | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PartyTent_LunaparkPlacing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PartyTentPlacing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Pate | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Pate_Opened | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PaydayMask_Chains | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PaydayMask_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PaydayMask_Dallas | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PaydayMask_Hoxton | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PaydayMask_Wolf | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PeachesCan | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PeachesCan_Opened | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Pear | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Pelt_Base | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Pen_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Pen_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Pen_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Pen_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Pen_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PepperSeeds | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PepperSeedsPack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PersonalRadio | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PetrolLighter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PetushokHat_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PetushokHat_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PetushokHat_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PetushokHat_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Pickaxe | retain | 47 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PigPelt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PigSteakMeat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PileOfBricks | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PileOfWoodenPlanks | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PilotJacket_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PilotJacket_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PilotJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PilotJacket_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PilotkaCap | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Pipe | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PipeWrench | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PissGround | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PistolOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PistolSuppressor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Pitchfork | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Plant_Cannabis | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Plant_Pepper | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Plant_Potato | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Plant_Pumpkin | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Plant_Tomato | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Plant_Zucchini | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlantBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlantMaterial | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Plastic_Explosive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Plastic_Explosive_Placing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierHolster | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierHolster_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierHolster_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierHolster_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierHolster_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierHolster_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierPouches | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierPouches_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierPouches_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierPouches_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierPouches_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierPouches_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierVest | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierVest_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierVest_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierVest_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierVest_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PlateCarrierVest_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PleurotusMushroom | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Pliers | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Plum | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PoliceBaton | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PoliceCap | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PoliceJacket | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PoliceJacketOrel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PolicePants | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PolicePantsOrel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PoliceShortSleeveShirt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PoliceShortSleeveShirt_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PoliceVest | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PorkCan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PorkCan_Opened | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PortableGasLamp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PortableGasStove | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Pot | retain | 10 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Potato | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PotatoSeed | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PowderedMilk | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Powered_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PowerGenerator | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PowerGeneratorStatic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PP19_Bttstck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Preload2DOptic_1PN51 | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Preload2DOptic_Longrange | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Preload2DOptic_Pistol | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Preload2DOptic_Pso1_VSS | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PressVest_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PressVest_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PressVest_LightBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PrisonerCap | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PrisonUniformJacket | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PrisonUniformPants | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PsilocybeMushroom | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PSO11Optic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PSO1Optic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PSO6Optic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Pumpkin | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PumpkinHelmet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PumpkinSeeds | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PumpkinSeedsPack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PunchedCard | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PurificationTablets | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:PUScopeOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:QuiltedJacket_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:QuiltedJacket_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:QuiltedJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:QuiltedJacket_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:QuiltedJacket_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:QuiltedJacket_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:QuiltedJacket_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:QuiltedJacket_Violet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:QuiltedJacket_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RabbitLegMeat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RabbitPelt | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RabbitSnareTrap | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RadarCap_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RadarCap_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RadarCap_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RadarCap_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RadarCap_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RadarCap_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Radio | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Rag | retain | 14 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Raincoat_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Raincoat_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Raincoat_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Raincoat_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Raincoat_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Raincoat_Pink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Raincoat_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Raincoat_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Rangefinder | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Raycaster | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RDG2SmokeGrenade_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RDG2SmokeGrenade_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RDG2SmokeGrenade_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RearDrive | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Red9Bttstck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RedCaviar | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ReflexOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ReflexVest | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Refridgerator | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Refrigerator | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RefrigeratorMinsk | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ReindeerPelt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ReindeerSteakMeat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RemoteDetonator | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RemoteDetonatorReceiver | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RemoteDetonatorTrigger | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RGD5Grenade | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Rice | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RidersJacket_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RidersJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Roadflare | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RobeVest_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RobeVest_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RobeVest_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RobeVest_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RobeVest_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RobeVest_Navy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Rope | retain | 14 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RopeBelt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RopeLocked | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:RoundGoby | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Ruins | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Saiga_Bttstck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SalineBag | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SalineBagIV | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SaltyMix | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SaltySticks | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SambucusBerry | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SandalsShoes_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SandalsShoes_BlueNavy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SandalsShoes_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SandalsShoes_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SandalsShoes_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SantasBeard | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SantasHat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sardines | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SardinesCan | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SardinesCan_Opened | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SarmaCan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SarmaCan_Opened | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SCAR_PrecisionBttstck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SCAR_PrecisionBttstck_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SCAR_StockBttstck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SCAR_StockBttstck_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Scarh_Front_Sight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ScientificBriefcase | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ScientificBriefcaseKeys | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Scimitar | retain | 48 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Screwdriver | retain | 45 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SeaChest | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_1_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_1_1_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_1_1_GreyRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_1_1_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_1_1_RedRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_1_1_YellowRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_1_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_1_2_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_1_2_GreyRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_1_2_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_1_2_RedRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_1_2_YellowRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_2_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_2_1_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_2_1_GreyRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_2_1_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_2_1_RedRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_2_1_YellowRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_2_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_2_2_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_2_2_GreyRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_2_2_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_2_2_RedRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Door_2_2_YellowRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Hood | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Hood_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Hood_GreyRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Hood_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Hood_RedRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Hood_YellowRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Trunk | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Trunk_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Trunk_GreyRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Trunk_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Trunk_RedRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Trunk_YellowRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Wheel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sedan_02_Wheel_Ruined | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SeedBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SewingKit | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SharpWoodenStick | retain | 8 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SheepPelt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SheepSteakMeat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShelterBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShelterFabric | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShelterKit | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShelterKitPlacing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShelterLeather | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShelterSite | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShelterStick | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Shemag_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Shemag_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Shemag_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Shemag_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Shemag_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SherpaHat_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SherpaHat_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SherpaHat_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SherpaHat_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShippingContainerKeys_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShippingContainerKeys_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShippingContainerKeys_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShippingContainerKeys_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShippingContainerKeys_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShippingContainerKeys_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Shirt_BlueCheck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Shirt_BlueCheckBright | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Shirt_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Shirt_GreenCheck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Shirt_PlaneBlack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Shirt_RedCheck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Shirt_WhiteCheck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShitGround | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShortJeans_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShortJeans_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShortJeans_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShortJeans_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShortJeans_Darkblue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShortJeans_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShortJeans_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShortSleeveShirt_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShortSleeveShirt_BlueRectangles | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShortSleeveShirt_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShortSleeveShirt_CreamSquares | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShortSleeveShirt_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShortSleeveShirt_Hawaiian_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShortSleeveShirt_Hawaiian_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShortSleeveShirt_Hawaiian_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShortSleeveShirt_Waves | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ShortSleeveShirt_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Shovel | retain | 4 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Shrimp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sickle | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SkateHelmet_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SkateHelmet_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SkateHelmet_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SkateHelmet_Gray | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SkateHelmet_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SkateHelmet_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SkiGloves_90s | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SkiGloves_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SkiGloves_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SkiGloves_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SkiGoggles_BlackYellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SkiGoggles_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SkiGoggles_WhiteClear | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SkiGoggles_WhiteDark | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Skirt_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Skirt_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Skirt_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Skirt_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Skirt_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SKS_Bayonet | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SlacksPants_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SlacksPants_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SlacksPants_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SlacksPants_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SlacksPants_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SlacksPants_DarkGrey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SlacksPants_Khaki | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SlacksPants_LightGrey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SlacksPants_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SledgeHammer | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SlicedPumpkin | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SlingBag_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SlingBag_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SlingBag_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SlingBag_Gray | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SmallFishTrap | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SmallGasCanister | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SmallGlassBottle_Afza | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SmallGlassBottle_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SmallGlassBottle_Jallab | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SmallGuts | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SmallProtectorCase | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SmallStone | retain | 6 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SmershBag | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SmershVest | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Snack_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sneakers_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sneakers_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sneakers_Gray | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sneakers_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sneakers_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sneakers_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SnowstormUshanka_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SnowstormUshanka_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SnowstormUshanka_Navy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SnowstormUshanka_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SnowstormUshanka_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SodaCan_Cola | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SodaCan_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SodaCan_Empty | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SodaCan_Fronta | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SodaCan_Kvass | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SodaCan_Pipsi | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SodaCan_Spite | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SodaCan_Takola | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SodaCan_ZumZam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SpaghettiCan | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SpaghettiCan_Opened | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SparkPlug | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Spear | excluded-definition | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SpearBone | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SpearStone | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SpicyCrackers | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Splint | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Splint_Applied | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SpookyArea | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SportGlasses_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SportGlasses_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SportGlasses_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SportGlasses_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SportGlasses_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SportingOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Spotlight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Spraycan_Black | retain | 11 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Spraycan_ColorBase | excluded-definition | 35 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Spraycan_Green | retain | 16 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SSG82Optic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Ssh68Helmet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StarlightOptic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StartKitIV | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Static | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticFlagPole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_10thAnniversaryBanner_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_10thAnniversaryBanner_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Airfield_Lamp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Airfield_LandMark | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Airfield_Light_Edge | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Airfield_Light_Navig | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Airfield_Light_PAPI1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Airfield_Light_PAPI2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Airfield_Light_PAPI3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Airfield_Light_PAPI4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Airfield_Light_Reflector | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Airfield_Small_Control | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Airfield_Small_Hangar | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ammoboxes_big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ammoboxes_single | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ammoboxes_stacked | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_dashedline_0_2000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_dashedline_10_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_dashedline_10_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_dashedline_10_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_dashedline_10_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_dashedline_12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_dashedline_1_1000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_dashedline_30_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_dashedline_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_dashedline_60_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_dashedline_6konec | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_dashedline_7_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_fullline_0_2000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_fullline_10_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_fullline_10_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_fullline_10_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_fullline_10_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_fullline_12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_fullline_1_1000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_fullline_30_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_fullline_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_fullline_60_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_fullline_6konec | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf1sakhal_fullline_7_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf2sakhal_0_2000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf2sakhal_10_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf2sakhal_10_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf2sakhal_10_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf2sakhal_10_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf2sakhal_12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf2sakhal_1_1000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf2sakhal_30_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf2sakhal_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf2sakhal_60_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf2sakhal_6konec1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf2sakhal_6konec2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf2sakhal_7_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf3sakhal_0_2000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf3sakhal_10_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf3sakhal_10_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf3sakhal_10_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf3sakhal_10_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf3sakhal_12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf3sakhal_1_1000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf3sakhal_30_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf3sakhal_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf3sakhal_60_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf3sakhal_6konec1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_asf3sakhal_7_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bag_Closed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bags_Open | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bags_Small_Stack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Barn_CowshedA | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Barn_CowshedB | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Barn_CowshedC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Barn_Hopper | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Barn_StrawStack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Barn_WaterTower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Barn_WaterTower_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Basket_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Basket_Wicker | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_bed_large_metal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_bed_large_metal_broken | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_bed_large_metal_crushed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bench_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Billboard_CrabCan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Billboard_FilterBottle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Billboard_Generalism | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Billboard_Highway_Blank | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Billboard_Oil | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Billboard_Service | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Billboard_TKArmy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Billboard_TKWomen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Boathouse_PierL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Boathouse_PierR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Boathouse_PierT | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bollard_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Border_01_Arch | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Border_01_Arch_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Border_02_Arch | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Border_02_Arch_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Border_03_AD | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Border_03_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bowl_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_asf3_Middle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Concrete1_25_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Concrete1_Left_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Concrete1_Right_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Concrete3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Concrete3_Snow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Highway1_Left1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Highway1_Left2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Highway1_Middle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Highway1_Right1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Highway1_Right2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Highway2_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Highway2_Left | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Highway2_Right | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Highway_Pillar_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Highway_Pillar_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Highway_Pillar_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Metal_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Metal_25_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Metal_25_1_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Metal_25_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Stone_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Wood2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Wood2_Pillar | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Wood2_Snow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Wood_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Wood_25_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Wood_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Wood_50_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bridge_Wood_50_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bucket_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Bucket_Red_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_BunkBed_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_BusStation_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_BusStation_roof_big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_BusStation_roof_long | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_BusStation_wall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_BusStop_Village | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cabinet_Fancy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cable_Street | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cable_Street_Clothes | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cable_Street_V | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cableway_Base_Rope1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cableway_Base_Rope2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cableway_Rope | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cages | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Carpet1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Carpet2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Carpet3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_carpet_big_dirty | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_carpet_big_dirty2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Carpet_Wall1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Carpet_Wall2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Carpets_Stack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_case_bedroom_a | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_case_bedroom_b | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Castle_Wall3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Castle_Wall3_D_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Castle_Wall3_D_L_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Castle_Wall3_D_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Castle_Wall3_D_R_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Castle_Wall3_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_CementWorks_Conveyor_Up1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_CementWorks_Conveyor_Up2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_CementWorks_Conveyor_Up3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_CementWorks_ConveyorFurnace | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_CementWorks_ConveyorMillA | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_CementWorks_ConveyorMillB | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_CementWorks_ConveyorTowerA | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_CementWorks_ConveyorTowerB | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_CementWorks_ConveyorTowerC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_CementWorks_SiloBig1Bridge | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_CementWorks_SiloBig2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Fence1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Fence2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Fence3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Fence4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Fence_straight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Grave1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Grave2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Grave3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Grave4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_SmallCross | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_SmallCross2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Tombstone1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Tombstone10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Tombstone11 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Tombstone12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Tombstone13 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Tombstone14 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Tombstone2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Tombstone3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Tombstone4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Tombstone5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Tombstone5_damaged | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Tombstone6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Tombstone7 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Tombstone8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Tombstone8_damaged | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cemetery_Tombstone9 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_chair | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_chair_broken | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_chair_crushed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_chair_leisure | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_chair_leisure_broken | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_chair_leisure_crushed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Chest_Fancy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_classroom_case_a | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_classroom_case_a_broken | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_classroom_case_a_crushed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_classroom_case_b | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_classroom_case_b_broken | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_classroom_case_b_crushed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cloth_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cloth_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Cloth_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_CoalPlant_Conveyor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_CoalPlant_LoadingHouse | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Construction_Hopper | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_1C | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_1D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_1N | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_1Nr | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_1Nr2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_2A | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_2B | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_2C | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_2D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_2E | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Long_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Long_BrickRed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Long_Cyan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Long_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Long_LightBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Long_LightGreen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Long_MilitaryGreen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Long_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Long_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Long_Sand | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Long_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Long_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Medium_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Medium_BrickRed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Medium_Cyan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Medium_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Medium_LightBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Medium_LightGreen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Medium_MilitaryGreen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Medium_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Medium_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Medium_Sand | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Medium_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Container_Medium_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ContainerMetal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ContainerMetal_low | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Control_Valve | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Conveyor_Chute | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Conveyor_Junction | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Conveyor_Long | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Conveyor_Pillar | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Conveyor_Short | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Conveyor_Short2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Conveyor_Slope | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Conveyor_Slope_NoSup | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Conveyor_Tripper | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Counter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Crates_Large | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Crates_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Crates_Small_Stack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_CURCylinder_01_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Curtain_Divider | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Curtain_Fancy1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Curtain_Fancy1M | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_d_FagusSylvatica_fallen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_d_FagusSylvatica_fallen_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_d_FagusSylvatica_fallenb | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_d_FagusSylvatica_fallenb_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_d_FagusSylvatica_fallenc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_d_FagusSylvatica_fallenc_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_d_FagusSylvatica_stump | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_d_FagusSylvatica_stump_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Dam_Concrete_20 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Dam_Concrete_20_Floodgate | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Dam_Concrete_40 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Dead_MassGrave_15m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Dead_MassGrave_8m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Dead_pile1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Dead_pile2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Dead_pile3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Dead_pile4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_fix1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_fix2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_fix3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_fix4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_fix5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_fix6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_patch01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_patch02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_patch03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_patch04 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_patch05 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_patch06 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_patch07 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_patch08 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_patch09 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_patch10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_patch11 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_asphalt_patch12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_bulletholes_big_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_bulletholes_big_01_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_BulletHoles_Big_01_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_BulletHoles_Big_01_nolc_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_BulletHoles_Big_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_BulletHoles_Big_02_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_BulletHoles_Small_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_BulletHoles_Small_01_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_BulletHoles_Small_01_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_BulletHoles_Small_01_nolc_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_BulletHoles_Small_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_BulletHoles_Small_02_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_CaveInterior_Square | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Concrete_Panels | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Concrete_Panels_End1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Concrete_Panels_End2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Crosswalk | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Crosswalk_East | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_long1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_long1_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_long2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_long2_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_long3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_long3_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_long4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_long4_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_long5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_long5_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_long6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_long7 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_long8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_long9 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_medium1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_medium10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_medium1_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_medium2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_medium2_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_medium4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_medium5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_medium6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_medium7 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_medium8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_medium9 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_small1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_small1_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_small2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_damage_small2_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_dirt_damage_long1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_dirt_damage_long1_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_dirt_damage_long1_TK_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_dirt_damage_long2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_dirt_damage_long3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_dirt_damage_long3_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_dirt_damage_long3_TK_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_dirt_rocks1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_dirt_rocks2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Heli_Army | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Manhole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Manhole2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Manhole3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_oilstain1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_oilstain2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_oilstain3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_oilstain4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_HoldShort | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Line_1x30 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Line_2x30 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Line_6x30 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Num0 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Num1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Num2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Num3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Num4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Num5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Num6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Num7 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Num8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Num9 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Skidmarks | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Skidmarks_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Skidmarks_End2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Skidmarks_End2_Light | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Skidmarks_End_Light | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Runway_Skidmarks_Light | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_RunwayPanel_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_RunwayPanel_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_RunwayPanel_Damage_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_RunwayPanel_Damage_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_RunwayPanel_Damage_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_RunwayPanel_Line_15m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_RunwayPanel_Line_2m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_RunwayPanel_Line_8m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Sakhal_Snow_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Sakhal_Snow_01_noLC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Sakhal_Snow_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Sakhal_Snow_02_noLC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Sakhal_Snow_03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Sakhal_Snow_03_noLC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Sakhal_Snow_05 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Sakhal_Snow_05_noLC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Sakhal_Snow_06 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Sakhal_Snow_06_noLC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Sakhal_snow_long1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_Sakhal_snow_long1_noLC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_ScorchMark_01_large_f | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_ScorchMark_01_large_f_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_ScorchMark_01_large_f_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_ScorchMark_01_large_f_nolc_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_ScorchMark_01_small_f | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_ScorchMark_01_small_f_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_ScorchMark_01_small_f_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decal_ScorchMark_01_small_f_nolc_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_CBRNCase_01_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_HazmatBag_01_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_HazmatBag_01_roll_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_LayFlatHose_01_Corner_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_LayFlatHose_01_CurveLong_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_LayFlatHose_01_CurveShort_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_LayFlatHose_01_Roll_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_LayFlatHose_01_SBend_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_LayFlatHose_01_Step_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_LayFlatHose_01_StraightLong_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_LayFlatHose_01_StraightShort_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_PowerCable_01_Corner_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_PowerCable_01_CurveLong_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_PowerCable_01_CurveShort_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_PowerCable_01_Roll_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_PowerCable_01_SBend_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_PowerCable_01_Step_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_PowerCable_01_StraightLong_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_PowerCable_01_StraightShort_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_PressureHose_01_Corner_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_PressureHose_01_CurveLong_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_PressureHose_01_CurveShort_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_PressureHose_01_Roll_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_PressureHose_01_SBend_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_PressureHose_01_Step_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_PressureHose_01_StraightLong_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Decon_PressureHose_01_StraightShort_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Desert_Construction_ConcreteTank | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Desert_Pipe_Big_18m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Desert_Pipe_Big_9m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Desert_Pipe_Big_SmallConL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Desert_Pipe_Big_SmallConR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Desert_Pipe_Big_Support | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Desert_Pipe_Med_9m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Desert_Pipe_Med_Ground1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Desert_Pipe_Med_Ground2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Desert_Pipe_MedL_BuildR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Desert_Pipe_MedL_CornerL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Desert_Pipe_MedL_CornerR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Desert_Pipe_MedR_BuildL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Desert_Pipe_MedR_BuildR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_drapes_long_torn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_drapes_torn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Emergency_Tunnel_Cabinet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_EmergencyBlanket_discarded | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_EngineCrane_01_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fireplace_spot_snow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Flag_AD_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Flag_AD_Wall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Flag_TK_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Flag_TK_Wall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_flowerpot | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Forest_Anthill | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Forest_BeetleTrap1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Forest_BeetleTrap2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Forest_BeetleTrap3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Forest_DeerSkeleton_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Forest_DeerSkeleton_Full | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Forest_DeerSkeleton_Pile | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Forest_DeerSkeleton_Skull | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Forest_HumanSkeleton | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Fridge_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_01_beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_01_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_01_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_01_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_01_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_01_stainless | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_01_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_02_beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_02_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_02_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_02_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_02_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_02_stainless | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_02_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_03_beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_03_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_03_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_03_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_03_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_03_stainless | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_03_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_04_beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_04_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_04_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_04_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_04_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_04_stainless | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_04_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_05_beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_05_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_05_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_05_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_05_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_05_stainless | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_05_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_06_beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_06_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_06_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_06_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_06_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_06_stainless | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_fridge_a_06_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_FrozenScientist_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_FueldStation_Feed_NoFuel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_FueldStation_Shed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_FueldStation_Sign | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_FuelStation_Shed_Takistan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_FuelStation_Sign_Takistan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_almara | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_almara_open | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_anatomy_poster_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_anatomy_poster_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Anvil | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_bag_DZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_bar_shelves_DZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_bar_tap_DZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_basketball_korb | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_blackboard | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_boots_DZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_box_c | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_box_c_multi | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_bucket | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_canister_DZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_carpet_2_DZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_carpet_big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_case_a | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_case_a_open | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_case_bedroom_b | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_case_cans_b | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_case_d | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_case_sink_a | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_cashier | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_ch_mod_c | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_ch_mod_h | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_ch_office_B | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_chest_DZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_class_case_a_closed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_class_case_a_open | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_class_case_b_closed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_class_case_b_open | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_conference_table_a | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Couch_Beige84x213x75_DZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_couch_DZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_debris_small_house | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Desk_Globe | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Dhangar_brownskrin | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Dhangar_brownskrin_old | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_dirtpile_small_house | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Dkamna_bila | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Dkamna_uhli | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_drapes | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_drapes_long | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Drill | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_fireplace_grill | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_flag_chernarus_pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_flag_chernarus_wall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_FlagHolder | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_flowers_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_flowers_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_fluor_lamp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_foldingbed_matress | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_foldingbed_open | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_fridge | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_FuseBox | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_grinder | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_gym_ladder | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_hangar_lamp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_hospital_bench | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_hospital_transport_bed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_icebox | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_intercom_speaker | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_kitchen_chair_a | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Kitchen_desk_A | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Kitchen_desk_B | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_kitchen_table_a | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_kitchen_unit_a_DZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Kitchenstove_Elec | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lab_beaker | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lab_bench | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lab_bunsen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lab_cylinder_beaker | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lab_dropper | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lab_erlenmeyer_flask | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lab_microscope | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lab_petri_dish | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lab_sink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lab_teacher_bench | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lab_triplebeam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lab_vial | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lab_volume_beaker | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_ladder_A_wood | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lekarnicka | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_library_a | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_library_a_open | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Light_BathRoom | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_light_kitchen_03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lobby_case | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lobby_chair | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lobby_counter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_lobby_table | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_locker_closed_blue_v1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_locker_closed_blue_v2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_locker_closed_blue_v3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_locker_closed_v1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_locker_closed_v2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_locker_closed_v3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_locker_open_blue_v1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_locker_open_blue_v2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_locker_open_blue_v3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_locker_open_v1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_locker_open_v2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_locker_open_v3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_long_bench | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_luxury_lamp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Luxury_light | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_matress_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_matress_white_bent | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_medical_table | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_MedicalGarbage_Bandage | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Metal_cutting_saw | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_metalcase_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_metalcase_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_metalcrate | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_metalcrate_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_office_chair | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_office_desk | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_office_table_a | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_PaperBox_01_small_closed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_PaperBox_01_small_destroyed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_PaperBox_01_small_open | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_PaperBox_01_small_ransacked | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_patient_monitor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_pc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_periodic_table | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_phonebox | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_piano | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_picture_a | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_picture_a_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_picture_a_03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_picture_a_04 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_picture_a_05 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_picture_b | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_picture_b_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_picture_c | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_picture_c_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_picture_d | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_picture_d_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_picture_e | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_picture_e_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_picture_f | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_picture_f_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_picture_g | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_picture_g_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_PlasticBucket | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_PlasticBucket_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_pokladna | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_postel_manz_kov | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_postel_panelak1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_prison_sink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_prison_toilet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_pult | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_pultskasou | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_rack_DZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_radar_electronics | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_radar_panel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_radar_panel_flat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_radar_rack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_radar_rack_quad | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_radiator | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_radio_b | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_sarcophagus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_sawhorse_DZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_scale | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_school_cage | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_school_clock | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_school_map | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_school_ringbell | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_shelf | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_shelf_1side | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_shelf_DZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_shelfs_small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_shelfs_small_broken | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_shelfs_small_crushed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_skrin_bar | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_sofa_leather_new | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_sofa_leather_old | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_SofaCorner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_soustruh_proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_student_chair | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_student_desk | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_stul_kuch_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_table | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_table_broken | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_table_crushed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_table_drawer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_table_DZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_table_umakart | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_tac_board | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_tac_board_posters_level1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_tac_board_posters_level2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Tandoor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_teacher_desk | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_toilet_b_02_V2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_tools_racking | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_tools_racking_DZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_tv_a | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_vaulting_box_large | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_vaulting_box_small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_vaulting_goat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_vending_machine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Vise | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Vojenska_palanda | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_wall_board | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_wall_board_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_wall_board_03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_wall_hanger | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_wardrobe_a | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_wardrobe_b | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_washing_machine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_wheel_cart_DZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_Workbench | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_workbench_DZ | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Furniture_yellow_star | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Bin | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Bin2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Container | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Container2_Closed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Container2_Open | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Container_Glass | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Container_Paper | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Container_Plastic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Ground_6m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Ground_6m_NoLC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_GroundSq_3m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_GroundSq_3m_NoLC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_GroundSq_5m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_GroundSq_5m_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_GroundSq_5m_NoLC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Pile1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Pile2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Pile3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Pile4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Pile5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Pile6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Pile7 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Garbage_Pile8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_01_beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_01_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_01_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_01_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_01_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_01_stainless | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_01_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_02_beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_02_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_02_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_02_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_02_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_02_stainless | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_02_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_03_beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_03_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_03_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_03_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_03_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_03_stainless | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_03_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_04_beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_04_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_04_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_04_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_04_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_04_stainless | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gas_stove_a_04_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Gate_City | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Gate_M5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Geoplant_PowerHall_Wire | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Graffiti_Arabic_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Graffiti_Arabic_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Graffiti_Arabic_03 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Graffiti_Arabic_Ion_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Graffiti_Arabic_Ion_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Graffiti_Baderca | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Graffiti_BIBIX_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Graffiti_BIBIX_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Graffiti_Cat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Graffiti_Frog | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Graffiti_Gasmask | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Graffiti_Hooded_Woman | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Graffiti_IWasHere | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Graffiti_Muffin | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Graffiti_NoFriendlies | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Graffiti_Umbrella | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Graffiti_UrMom | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gravsakhal_0_2000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gravsakhal_10_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gravsakhal_10_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gravsakhal_10_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gravsakhal_10_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gravsakhal_12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gravsakhal_1_1000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gravsakhal_30_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gravsakhal_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gravsakhal_60_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gravsakhal_6konec1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_gravsakhal_7_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Hanged_civil | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Hanged_doctor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_HBarrier_1_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_HBarrier_3_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_HBarrier_5_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_HBarrier_Big_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_HBarrierWall_4_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_HBarrierWall_6_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_HBarrierWall_Corner_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_HBarrierWall_Corridor_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Hotel_Damaged_Airplane_Back | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Hotel_Damaged_Airplane_Wing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Hotel_Damaged_Decal1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Hotel_Damaged_Decal2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Hotel_Damaged_Rubble | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ice_Sea_Piece_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ice_Sea_Piece_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ice_Sea_Piece_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ice_Sea_Piece_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ice_Sea_Piece_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ice_Sea_Piece_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ice_Sea_Piece_7 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ice_Sea_Piece_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ice_Sea_Square_50m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ice_Sea_Square_Box_50m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ice_Sea_Triangle_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ice_Sea_Triangle_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_IronPipes | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_KirovDam_Back_Bottom | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_KirovDam_Back_Bottom_Special | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_KirovDam_Back_Top | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_KirovDam_Back_Top_Special | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_KirovDam_Front_Bottom | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_KirovDam_Front_Top | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_KirovDam_Front_Top_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_KirovDam_Overflow_Bottom | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_KirovDam_Penstock_Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_KirovDam_Penstock_Curved | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_KirovDam_Penstock_Manifold | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_KirovDam_Penstock_Straight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_KirovDam_PowerPlant_Base_B | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_KirovDam_PowerPlant_Base_C | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_KirovDam_Road | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_KirovDam_Road_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_KirovDam_Statue_B | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Lamp_City1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Lamp_City2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Lamp_City3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Lamp_Decorative | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Lamp_Halogen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Lamp_Harbour | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Lamp_Ind | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Lamp_Rail | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Lamp_Stadium | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_lobby_table | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Market1_Empty | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Market2_Empty | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Medical_Tarp_Large_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_MetalBed_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_01_beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_01_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_01_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_01_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_01_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_01_stainless | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_01_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_02_beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_02_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_02_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_02_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_02_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_02_stainless | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_02_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_03_beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_03_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_03_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_03_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_03_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_03_stainless | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_03_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_04_beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_04_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_04_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_04_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_04_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_04_stainless | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_microwave_a_04_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_AircraftShelter_Door_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_AircraftShelter_Door_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_AircraftShelter_Grass_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_AircraftShelter_Grass_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_Artilery_Nest | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_Artilery_Rampart | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_Artilery_Rampart_Sakhal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_Artillery_Nest_Sakhal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_Artillery_Nest_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_BlastCover1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_BlastCover1_Grass | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_BlastCover1_Sakhal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_BlastCover2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_BlastCover2_Grass | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_BlastCover2_Sakhal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_BlastCover3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_BlastCover3_Grass | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_BlastCover3_Sakhal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_BlastCover4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_BlastCover4_Grass_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_BlastCover4_Grass_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_BlastCover4_Sakhal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_CamoNet_Big_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_CamoNet_Big_east | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_CamoNet_Big_nato | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_CamoNet_Roof_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_CamoNet_Side_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_CamoNet_Side_Desert_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_CamoNet_Side_east | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_CamoNet_Side_nato | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_CamoNet_Tent2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_CamoNet_Tent2_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_HBarrier_1m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_HBarrier_4m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_HBarrier_6m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_HBarrier_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_HBarrier_Round | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_PowerGenerator | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_Radar_Mobile1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_Radar_Mobile2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_Radar_Mobile3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_ReinforcedTank1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_ReinforcedTank1_Grass | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_ReinforcedTank2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_ReinforcedTank2_Grass_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_ReinforcedTank2_Grass_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_ReinforcedTank2_Grass_Top | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_SatelliteAntenna_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_SatelliteAntenna_01_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_SatelliteAntenna_01_Small_Wall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_Tent_Big1_Desert_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_Tent_Big5_Desert_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_WiredFence | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_WiredFence_Gate | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mil_WiredFenceD | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Minaret1_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Minaret2_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mine_Conveyer1_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mine_Conveyer1_Begin | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mine_Conveyer1_EndBuild | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mine_Conveyer2_Build | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mine_Heap | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mine_Heap_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mine_Hopper_Build | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mine_Hopper_Build_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mine_Rail | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mine_Rail_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mine_Rail_Switch | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mine_Rail_Tram | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Mine_Tunnel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_AdvertColumn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Antenna | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_BagFence_3m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_BagFence_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_BagFence_Round | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Barbedwire | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Barbedwire_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Barricade | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Bench1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Bench2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Bench3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Bench4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Bench5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Bench6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Bench7 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Bench8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Bench9 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_BoardsPack1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_BoardsPack2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_BoardsPack3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Boogieman | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_BoundaryStone | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_BoundaryStone_Plastic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_BoundaryStone_Tube | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_BoxWooden | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Carousel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Carousel_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Chair_Camp1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Chair_Camp2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Chair_Plastic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_CinderBlock | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_CinderBlocks | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Coil | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_ConcreteBlock1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_ConcreteBlock1_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_ConcreteBlock2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_ConcreteBlock2_Damaged | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_ConcreteBlock2_Stripes | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_ConcretePanels | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_ConcretePipe | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_ConcretePipe_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_ConcretePipe_Gate | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Cover_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Cover_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_CrabCages | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_CrashBarrier | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_CrashBarrier_01_4m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_CrashBarrier_01_4m_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_CrashBarrier_01_8m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_CrashBarrier_01_8m_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_CrashBarrier_01_Double_8m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_CrashBarrier_01_Double_8m_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_CrashBarrier_01_End_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_CrashBarrier_01_End_L_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_CrashBarrier_01_End_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_CrashBarrier_01_End_R_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_CrashBarrier_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_DeconShower_Large | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_DragonTeeth | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_DragonTeeth_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_DragonTeeth_Multiple | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_DragonTeeth_Multiple_RedWhite | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_DragonTeeth_Single | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_DragonTeeth_Single_RedWhite | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Drainage | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_FeedRack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_FishingGear1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_FishingGear2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Flagpole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Football_Gate | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Football_Line | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Football_Line_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Football_Line_HCircle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Fountain | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Fountain_Frozen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Gantry | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Gantry_Sign | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Gantry_SignSupport | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Gantry_SignSupport_destroyed1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Gantry_SignSupport_destroyed2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_GasMeterCabinet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_GContainer_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Gunrack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_HayBale | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_HayBale_Decayed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_HayBale_Packed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_HayBale_Packed_Stack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Haystack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Hedgehog_Concrete | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Hedgehog_Concrete_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Hedgehog_Iron | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_JerseyBarrier | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_JerseyBarrier_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_JerseyBarrier_Dam_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_JerseyBarrier_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_JerseyBarrier_End_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_JerseyBarrier_End_Dam_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_JerseyBarrier_End_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_JerseyBarrier_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_JerseyBarrier_Split | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_JerseyBarrier_Split_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_JerseyBarrier_Split_Dam_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_JerseyBarrier_Split_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_MysteriousBell | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_NoticeBoard1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_NoticeBoard2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Obstacle_Bridge | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Obstacle_Crawl | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Obstacle_Cross | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Obstacle_Pass | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Obstacle_Ramp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Obstacle_RunAround | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Pallet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Pallets1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Pallets2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Pallets3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_PedestrianOverpass_5m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_PedestrianOverpass_pillar | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_PedestrianOverpass_Stairs_Left | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_PedestrianOverpass_Stairs_Right | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Pipes | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Pipes_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_PostBox1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_PostBox2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Range_Line | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Range_Line_dispersions | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Range_Pistol | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Range_Roof | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Range_Single | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Razorwire | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_RazorWire_Single | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_RazorWire_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_RoadBarrier | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_RoadBarrier_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_RoadSteelPlate | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Sandbox | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_SatDish | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Seesaw | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_SewerCover | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_SnowPole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_StadiumBenches | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_StairBridge | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Sunshade | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_SupplyBox1_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_SupplyBox2_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_SupplyBox3_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_SurveyMarker_Cover | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_SurveyMarker_Post | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_SurveyMarker_Rod | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Table | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Table_Camp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Table_Camp_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Table_Large | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Table_Market | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Through_Trailer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Timbers1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Timbers2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Timbers3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Timbers4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Timbers_Log1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Timbers_Log2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Timbers_Log3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Timbers_Log4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Timbers_Log5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Tire | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Tire_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_TirePile | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_TirePile_Group | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_TirePile_Large | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_TrafficLights | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Transformer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Tree_Pavement1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Tree_Pavement2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Tree_Pavement3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Tree_Protector | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_Walkover | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_WindBreak | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_WoodBlock | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_WoodenCrate | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_WoodenCrate_3x | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_WoodenCrate_5x | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_WoodPile1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_WoodPile2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_WoodPile_Forest1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_WoodPile_Forest2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_WoodPile_Forest3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_WoodReserve | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_WoodTable_Indoor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Misc_WoodTable_Outdoor | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_model_plane_mig21_lines | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Monument_Bears | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Monument_Enoch1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Monument_Enoch2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Monument_plane_mig21 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Monument_plane_mig21_lines | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Monument_Soldiers | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Monument_Wall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Monument_War1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Monument_War2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Monument_Workcamp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_MooringBuoy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_MorsePoster | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_mudsakhal_0_2000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_mudsakhal_10_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_mudsakhal_10_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_mudsakhal_10_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_mudsakhal_10_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_mudsakhal_12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_mudsakhal_1_1000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_mudsakhal_30_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_mudsakhal_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_mudsakhal_60_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_mudsakhal_6konec1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_mudsakhal_7_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_old_mattress_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_PalletTrolley_01_yellow_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Panel_Concrete_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Panel_Concrete_1_Legacy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Panel_Concrete_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Panel_Concrete_2_Legacy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Panel_Concrete_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Panel_Concrete_Dam_Legacy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Panels_Concrete | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Panels_Concrete_Legacy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_PartyTent | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Path_Panels | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Path_Panels_Damaged | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_PatrolBoat_Military_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_piano_broken | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_picture_a | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_picture_b | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_picture_c | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_picture_d | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_picture_e | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_picture_f | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_picture_g | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete1_CornerIn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete1_CornerOut | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete1_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete1_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete1_L10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete1_L30 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete1_TBig | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete1_TSmall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete2_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete3_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete3_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete3_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete3_Fuel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete4_16m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete4_16m_NoSup | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete4_30deg | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete4_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete4_Steps | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete5_20m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete5_Corner_Inner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete5_Corner_Outer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Concrete5_T | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Crane2_Rails_4m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Crane2_Rails_4m_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Crane2_Rails_8m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Crane_Rails | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Crane_Rails_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Tube_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Tube_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Wooden1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Wooden1_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Wooden1_Pillars | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Wooden2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Wooden3_16m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Wooden3_30deg | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Wooden3_Barrels | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pier_Wooden3_Platform | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pillow_Fancy1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pillow_Fancy2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pillow_Flannel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pillow_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pillow_Old | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Big_18m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Big_18m_Ladder | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Big_9m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Big_SmallConL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Big_SmallConR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Big_Support | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Med_9m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Med_BuildL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Med_BuildR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Med_Ground1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Med_Ground2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_MedL_BuildR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_MedL_CornerL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_MedL_CornerR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_24m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_8m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_8m_MetalSup | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_8m_NoSup | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_8m_NoSup_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_Block | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_Curve | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_Curve45 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_Curve_NoSup | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_Ground | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_High_24m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_High_8m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_High_Curve | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_High_Ground | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_High_Ground2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_High_Ground2_NoSup | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_HorizontalValve | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small2_VerticalValve | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small_20m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small_Broken | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small_Ground1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small_Ground2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small_L45 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small_L90 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small_R45 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small_R90 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small_Stairs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small_U | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Pipe_Small_Valve | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_PipeFence_01_m_2m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_PipeFence_01_m_4m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_PipeFence_01_m_8m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_PipeFence_01_m_d | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_PipeFence_01_m_pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Plank_01_4m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Plank_01_8m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Angle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Angle_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Block | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Block_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Ramp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Ramp_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Stairs_20 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Stairs_20_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Stairs_30 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Stairs_30_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Stairs_30_WallL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Stairs_30_WallL_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Stairs_30_WallR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Stairs_30_WallR_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Stairs_Block | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Staris_Block_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Wall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform1_Wall_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform2_Angle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform2_Block | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform2_Enter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform2_Stairs_20 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform2_Stairs_30 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform2_Stairs_30_WallL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform2_Stairs_30_WallR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform2_Stairs_Block | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform2_Wall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Platform3_Block_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Poster_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_HV2_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_HV2_Line_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_HV2_Tower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_HV2_Wire | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_HV2_Wire_Main | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_HV3_Tower1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_HV3_Tower2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_HV_Line | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_HV_Line_80m_damaged | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_HV_Line_damaged | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_HV_Line_Turn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_HV_Line_TurnL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_HV_Line_TurnR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_HV_Tower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_ConcT | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood1_Trail_B | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood1_Trail_G | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood1_Trail_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood1_Trail_Y | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood4_A | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood4_A_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood4_A_J | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood4_A_J_Nest | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood4_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood4_Lamp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood5_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood5_End_rus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood5_J | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood5_J_Nest_rus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood5_J_rus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood5_rus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood6_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood6_H | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood6_H_Trail_B | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood6_H_Trail_G | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood6_H_Trail_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood6_H_Trail_Y | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Pole_Wood6_J | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Transformer_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_TransformerStation_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_TransformerStation_Cables | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Wire_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_Wire_50_Main | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Power_WireTel_50_Main | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Quarry_Conveyer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Quarry_ConveyerLong | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Quarry_HammerMill | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_quarrysakhal_0_2000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_quarrysakhal_10_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_quarrysakhal_10_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_quarrysakhal_10_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_quarrysakhal_10_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_quarrysakhal_12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_quarrysakhal_1_1000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_quarrysakhal_30_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_quarrysakhal_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_quarrysakhal_60_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_quarrysakhal_6konec1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_quarrysakhal_7_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rack_Carpets | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_racks | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_racks_broken | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_racks_crushed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Bridge_15 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Bridge_15_3tracks | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Bridge_15_Curve | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Bridge_15_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Bridge_40 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_ConcreteRamp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Crossing_Barrier | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Crossing_Block_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Crossing_Block_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_LineBreak_Concrete | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_LineBreak_Iron | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Platform_Cross | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Platform_Segment | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Platform_Start | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_PoleF | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_PoleT | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_PoleTT1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_PoleTT2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Signals | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_25_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_Down_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_Down_25_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_Down_40 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_Down_40_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_L25_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_L25_10_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_LB1_RE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_LB1_RE_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_LB_RE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_LB_RE_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_LE1_RB | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_LE1_RB_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_LE_RB | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_LE_RB_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_Passing_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_Passing_10_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_Passing_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_Passing_25_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_Passing_25_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_R25_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_R25_10_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_SP | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_SP_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_TurnOutL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_TurnOutL_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_TurnOutR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_TurnOutR_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_Up_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_Up_25_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_Up_40 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_Track_Up_40_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_25_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_40 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_40_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_8_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_L25_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_L25_10_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_L25_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_L25_5_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_L30_20 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_L30_20_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_R25_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_R25_10_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_R25_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_R25_5_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_R30_20 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_R30_20_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_TurnOutL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_TurnOutL_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_TurnOutR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rail_TrackE_TurnOutR_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Refugee_Tent_Big1_Desert_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Refugee_Tent_Big5_Desert_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Road_Sidewalk4_4m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Road_Sidewalk4_8m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Road_Sidewalk4_Border_2m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Road_Sidewalk4_Border_4m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Road_Sidewalk4_Border_8m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Road_Sidewalk4_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Road_Sidewalk4_Narrow_2m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Road_Sidewalk4_Narrow_4m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Road_Sidewalk4_Narrow_8m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Road_Sidewalk5_Narrow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Road_Sidewalk5_Narrow_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Road_Sidewalk5_Wide | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Road_Sidewalk5_Wide_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Road_Sidewalk_Stairs | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Road_sinkhole_sila | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_Bags_Curve | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_Bags_Curve_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_Bags_Curve_Desert_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_Bags_EndL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_Bags_EndL_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_Bags_EndL_Desert_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_Bags_EndR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_Bags_EndR_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_Bags_EndR_Desert_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_Bags_Long | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_Bags_Long_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_Bags_Long_Desert_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_CncBlock | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_CncBlock_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_CncBlocks_Long | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_CncBlocks_Long_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_CncBlocks_short | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_Pillbox | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_Wood_Long | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_Wood_Long_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_Wood_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roadblock_Wood_Small_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_RoadCone | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_RoadCone_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf1_0_2000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf1_10_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf1_10_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf1_10_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf1_10_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf1_12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf1_15_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf1_1_1000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf1_22_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf1_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf1_30_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf1_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf1_60_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf1_6_crosswalk | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf1_6konec | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf1_7_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf2_0_2000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf2_10_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf2_10_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf2_10_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf2_10_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf2_12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf2_15_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf2_1_1000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf2_22_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf2_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf2_30_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf2_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf2_60_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf2_6_crosswalk | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf2_6konec | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf2_7_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf3_0_2000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf3_10_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf3_10_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf3_10_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf3_10_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf3_12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf3_15_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf3_1_1000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf3_22_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf3_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf3_30_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf3_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf3_60_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf3_6konec | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partasf3_7_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partcity_0_2000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partcity_10_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partcity_10_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partcity_10_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partcity_10_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partcity_12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partcity_15_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partcity_1_1000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partcity_22_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partcity_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partcity_30_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partcity_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partcity_60_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partcity_6konec | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partcity_7_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partgrav_0_2000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partgrav_10_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partgrav_10_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partgrav_10_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partgrav_10_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partgrav_12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partgrav_15_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partgrav_1_1000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partgrav_22_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partgrav_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partgrav_30_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partgrav_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partgrav_60_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partgrav_6konec | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partgrav_7_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partkr_t_asf1_asf2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partkr_t_asf1_asf3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partkr_t_asf1_city | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partkr_t_asf2_asf2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partkr_t_asf2_asf3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partkr_t_asf3_asf2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partkr_t_asf3_asf3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partkr_t_asf3_mud | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partkr_t_city_asf3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partkr_t_city_city | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partkr_t_mud_mud | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partkr_x_asf1_asf3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partkr_x_asf1_city | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partkr_x_asf2_asf3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partkr_x_city_city | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partkr_x_city_city_asf3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partmud_0_2000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partmud_10_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partmud_10_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partmud_10_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partmud_10_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partmud_12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partmud_15_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partmud_1_1000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partmud_22_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partmud_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partmud_30_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partmud_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partmud_60_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partmud_6konec | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partmud_7_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partpath_dirt_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partpath_dirt_30 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partpath_dirt_curve | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partpath_rock_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partpath_rock_30 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partpath_rock_curve | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_beton | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_beton_end1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_beton_end2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_dirt_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_dirt_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_dirt_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_end15 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_end33 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_main | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_main_40 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_poj_draha | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_poj_L_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_poj_L_1_end | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_poj_L_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_poj_L_2_end | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_poj_spoj | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_poj_spoj_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_poj_T_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunway_poj_T_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roads_Partrunwayold_40_main | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_RocketBase_FuelLine_01_30 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_RocketBase_FuelLine_01_6m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_RocketBase_FuelLine_01_90 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_RocketBase_FuelLine_01_end | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_RocketBase_FuelLine_01_pump | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roof_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roof_Collection | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Roof_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_Bricks1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_Bricks2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_Bricks3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_Concrete1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_Concrete2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_Concrete3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_DirtPile_Desert_Large | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_DirtPile_Desert_Medium1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_DirtPile_Desert_Medium2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_DirtPile_Desert_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_DirtPile_Large | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_DirtPile_Large_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_DirtPile_Medium1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_DirtPile_Medium1_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_DirtPile_Medium2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_Glass | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_Glass_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_Metal1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_Metal2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_Metal3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_Rocks1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_Rocks2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_Wood1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_Wood2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Rubble_Wood3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Chimney | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Church | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Church2_01_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Church2_02_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Church2_03_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Church2_04_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Church2_Proxy_overgrowth | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Construction_Building | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Corner1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Corner2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_DoorWall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_FuelStation_Shed_Takistan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Gate_City | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1B01_1_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1B01_2_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1C1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1M1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1M2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1M3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1M4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1M5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1S1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1S2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1W02_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1W03_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1W04_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1W05_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1W06_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1W07_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1W09_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1W11_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_1W12_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_2B01_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_2B02_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_2B03_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_2B04_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_2C1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_2C2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_2C4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_2M1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_2M2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_2S1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_2S2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_2W01_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_2W02_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_2W03_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_2W04_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_2W05_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_3C1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_3S1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_3S2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_House_Total | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBig1_Half_Proxy_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBig1_Half_Proxy_overgrowth | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBig1_Proxy_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBig1_Proxy_overgrowth | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBig1_Proxy_overgrowth_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBig1_Proxy_overgrowth_02_template | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBig1_Proxy_overgrowth_template | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBig2_Half_Proxy_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBig2_Half_Proxy_overgrowth | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBig2_Proxy_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBig2_Proxy_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBig2_Proxy_overgrowth | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBig3_Half_Proxy_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBig3_Half_Proxy_overgrowth | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBig3_Proxy_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBig3_Proxy_overgrowth | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBlock_2C1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBlock_2C_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBlock_Corner_Total | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBlock_Half | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseBlock_Total | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseSmall1_Half_Proxy_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseSmall1_Half_Proxy_overgrowth | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseSmall1_Proxy_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseSmall1_Proxy_02 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseSmall1_Proxy_overgrowth | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseSmall2_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseSmall2_Proxy_bricks | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_HouseSmall2_Proxy_overgrowth | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Mausoleum_Small1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Mausoleum_Small2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Mil_ControlTower_Proxy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Minaret1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Minaret2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Oil_DrillTower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Oil_Pump | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Rubble | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Store_CarService | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Store_Street1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Villa | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Ruin_Wall | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_SCBACylinder_01_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_SCUDMissile | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_SCUDMissile_Broken1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_SCUDMissile_Broken2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_SCUDMissile_Broken2_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Shed_Open_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Shed_Open_Big2_Complete | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Shed_Open_Big_Complete | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Shed_Open_Big_end | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Shed_Open_Sawmill | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Shed_Open_SideRoof | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Shed_Open_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Shed_Open_Small_Complete | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Shed_Open_Small_end | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ShellCrater1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ShellCrater1_Decal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ShellCrater1_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ShellCrater1_Desert_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ShellCrater1_Desert_Decal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ShellCrater1_Desert_Decal_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ShellCrater2_Debris | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ShellCrater2_Decal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ShellCrater2_Desert_Debris_lc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ShellCrater2_Desert_Debris_lc_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ShellCrater2_Large | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ShellCrater2_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk1_10m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk1_1m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk1_5m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk1_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk1_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk1_TCross | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk1_Turn_10deg | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk1_Turn_20deg | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk1_Turn_30deg | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk1_Turn_5deg | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk2_1m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk2_5m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk3_Border | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk3_Border_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk3_Narrow_12m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk3_Narrow_4m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk3_Narrow_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk3_Wide_12m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk3_Wide_4m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk3_Wide_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk3_WideB_4m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk6_6m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk6_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk6_EndL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk6_EndR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk7_6m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk7_EndL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk7_EndR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk8_6m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk8_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk8_EndL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk8_EndR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sidewalk8_T | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sign_Build_BlueCross | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sign_Build_Border_AD1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sign_Build_Border_AD2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sign_Build_Border_Bye1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sign_Build_Border_Bye2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sign_Build_Border_TK1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sign_Build_Border_TK2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sign_Petropavlovsk | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sign_Roadblock_Arrow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sign_Roadblock_Arrow_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sign_Roadblock_Stop | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sign_Roadblock_Stop_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Skilift_Rope_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Skilift_Rope_Middle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Skilift_Rope_Start | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Skilift_Tower_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Skilift_Tower_Middle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Skilift_Tower_Middle_Slope | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Skilift_Tower_Start | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sleeping_bag | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sleeping_bag_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Slum_Roof1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Slum_Roof2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Slum_Roof3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Slum_Roof4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Slum_Roof5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Slum_Roof6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Smokestack_Big_Ruin_Bottom | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Smokestack_Big_Ruin_Low | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Smokestack_Big_Ruin_Mid | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Smokestack_Big_Ruin_Up | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_SofaAvolon | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_SolarPowerPlant_Mirror | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_SolarPowerPlant_Mirror_Broken | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_SolarPowerPlant_Mirror_Ruins | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Sponge_01_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Stand_Kiosk | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Stand_Meat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Stand_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Stand_Water | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Statue_Aziz_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Statue_Aziz_Broken | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Statue_Enoch1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Statue_General | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Stockyard_OreMound1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Stockyard_OreMound2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Stockyard_Rail | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_stone1_sand | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_stone1_sand_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_stone2_sand | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_stone2_sand_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_stone3_sand | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_stone3_sand_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_stone4_sand | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_stone4_sand_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_stones_sand_erosion | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_stones_sand_erosion_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_StorageBox_Wooden | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Stretcher_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Stretcher_Green_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Stretcher_Green_Folded | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Stretcher_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Stretcher_Red_Folded | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_SunShade | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Table1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Table2_Small | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Tank_Medium | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Tank_Small_Gas | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Tank_Small_Rusty | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Tank_Small_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Target_Concrete1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Target_Concrete2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Target_Concrete_Block | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Target_Concrete_Ramp | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Target_Support | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Taxiway_0_2000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Taxiway_10_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Taxiway_10_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Taxiway_10_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Taxiway_10_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Taxiway_12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Taxiway_15_75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Taxiway_1_1000 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Taxiway_22_50 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Taxiway_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Taxiway_30_25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Taxiway_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Taxiway_60_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Taxiway_6konec | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Taxiway_7_100 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Teapot | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Terrace_S1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Terrain_Livonia_ForestPatch | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Terrain_Livonia_GrassPatch | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_TirePile | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Tisy_AirShaft | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Tisy_Garages_Grass_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Tisy_Garages_Grass_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Tisy_RadarPlatform_Bot | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Tisy_RadarPlatform_Mid | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_TKInd | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_TKStreet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_TKStreet_Double | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_TKVillage | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_ToolTrolley_02_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Train_Wagon_Flat_Industrial_Barrels_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Train_Wagon_Flat_Industrial_Planks_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Transmitter_Box | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Transmitter_Small1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Transmitter_Small2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_TransportCart | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Tribune | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Tunnel_Biathlon_Left | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Tunnel_Biathlon_Left_anthoxanthum | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Tunnel_Biathlon_Left_elytrigia | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Tunnel_Biathlon_Right | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Tunnel_Biathlon_Right_anthoxanthum | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Tunnel_Biathlon_Right_elytrigia | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Underground_Corridor_Main_Gate_L | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Underground_Corridor_Main_Gate_R | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Underground_Pipes_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Urn1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Vase1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Vase2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Vase3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Vase4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_B1_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_B1_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_B1_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_B2_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_B2_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_B2_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_BackAlley_01_l_1m_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_BackAlley_01_l_gap_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_BackAlley_02_l_1m_F | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Barricade1_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Barricade1_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Bremer_High | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Bremer_High_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Bremer_High_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Bremer_Low | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Bremer_Low_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Bremer_Low_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Bremer_Medium | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Bremer_Medium_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Bremer_Medium_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Canal_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Canal_Desert_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CBrk_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CBrk_5_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CBrk_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CBrk_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CBrk_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CGry_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CGry_5_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CGry_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CGry_Corner_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CGry_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CGryLow_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CGryLow_End1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CGryLow_End2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Cnc_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Cnc_Desert_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CncBarrier_4Block | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CncBarrier_Block | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CncSmall_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CncSmall_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CncSmall_Desert_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CncSmall_Desert_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CYel_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CYel_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CYel_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_CYel_End2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen1_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen1_5_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen1_5_Hole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen1_5_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen2_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen2_6_Hole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen2_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen3_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen3_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen3_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen3_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen4_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen4_4_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen4_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen4_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen4_D_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen4_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen5_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen5_10_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen5_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen5_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen6_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen6_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen7_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Fen7_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_FenForest_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_FenForest_5_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_FenForest_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_FenG_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_FenG_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_FenR_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_FenR_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_FenStadium | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_FenVineyard | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_FenVineyard_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_FenW_7 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_FenW_7_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_FenW_7_S | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_ForFieldFen_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_ForFieldFen_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_ForFieldFen_end | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_GarbCont | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_GarbCont_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Gate_CGry | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Gate_IndCnc4_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Gate_IndCnc4_Desert_Low | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc2_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc2_Desert_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc3_1_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc3_1_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc3_2_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc3_2_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc3_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc3_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc4_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc4_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc4_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc4_Desert_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc4_Desert_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc4_Desert_8_Graffiti | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc4_Desert_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc4_Desert_Low_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc4_Desert_Low_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc4_Desert_Low_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc4_Desert_Low_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc4_Desert_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc4_Low_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc4_Low_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc4_Low_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc4_Low_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc4_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc_4_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc_Desert_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc_Desert_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc_Desert_4_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc_Desert_End_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc_Desert_End_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc_Desert_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc_End_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc_End_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCnc_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCncH_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCncH_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCncH_Desert_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndCncH_Desert_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_3_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_3_D_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_3_Hole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_3_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_9 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_9_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_Desert_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_Desert_3_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_Desert_3_D_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_Desert_3_Hole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_Desert_3_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_Desert_9 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_Desert_9_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_Desert_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_Desert_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_Desert_Pole_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc2_Pole_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc_3_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc_3_Hole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc_9 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndFnc_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndVar1_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndVar1_5_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndVar1_5_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndVar1_5_D_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndVar1_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndVar2_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndVar2_5_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndVar2_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndVar3_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndVar3_5_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_IndVar3_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M1_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M1_5_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M1_5_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M1_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M2_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M2_5_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M3_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M3_Dam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M3_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M4_10_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M4_10_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M4_10_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M5_10 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M5_10_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M5_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M5_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M5_Hole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_M5_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_MilCnc_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_MilCnc_Corner | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_MilCncBarrier | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Mosque_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Mosque_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_PipeFence_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_PipeFence_4_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_PipeFence_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_PipeFenceWall_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_PoleWall_5_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_PoleWall_5_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_PoleWall_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Railing_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Railing_1_EndL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Railing_1_EndR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Railing_1_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Railing_1_Slope | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Railing_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Railing_2_Slope | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Railing_EndL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Railing_EndR | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_S1_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_S1_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_S1_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_S1_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_SilageWall_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_SilageWall_5_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_SilageWall_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Stone | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Stone2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Stone2D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Stone3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Stone3D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_StoneD | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin6_1_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin6_1_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin6_2_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin7_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin7_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin7_Blue_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin7_Blue_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin7_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin8_LowBlue_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin8_LowBlue_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin8_LowBlue_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin8_LowGreen_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin8_LowGreen_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin8_LowGreen_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin8_LowRed_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin8_LowRed_8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin8_LowRed_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin_4_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Tin_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_TinCom_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_TinCom_9 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_TinCom_9_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_TinCom_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_VilVar1_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_VilVar1_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_VilVar2_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_VilVar2_4_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_VilVar2_4_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_VilVar2_4_END | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_VilVar2_Green_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_VilVar2_Green_4_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_VilVar2_Green_4_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_VilVar2_Green_4_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_VilVar2_Green_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_VilVar2_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_VilVar2_Red_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_VilVar2_Red_4_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_VilVar2_Red_4_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_VilVar2_Red_4_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_VilVar2_Red_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood1_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood1_5_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood1_5_pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood1D_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood1D_5_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood1D_5_pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood2_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood2_5_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood2_5_END | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood2_5_END_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood2_5_nolc | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood2_5_pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood3_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood3_4_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood4_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood4_End1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood4_End2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood4_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood5_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood5_4_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood5_4_D | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood5_4_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood5_4_Pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_Wood6_6 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_WoodF_5 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_WoodF_5_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_WoodF_5_END | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_WoodVil_4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_WoodVil_4_2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wall_WoodVil_4_pole | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Walls_End | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_water_pond_50x50m | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_WaterPipe | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_WaterReservoir | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_WaterSpring_Sakhal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_WhiteBoard | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_WhiteBoard_Laboratory | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wooden_Single_Bed_01 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Workshop_Box | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_BMP1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_BMP1_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_BMP1_NoPlacement_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_BMP1_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_BMP1_TK_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_BMP2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_BMP2_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Boat_Small1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Boat_Small2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Boat_Small3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_BRDM | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_BRDM_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Bulldozer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Bulldozer_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_C130J_Engine | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_C130J_Wing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Chinook | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Chinook_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_CrawlerCrane_Arm | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_CrawlerCrane_cabin | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_CrawlerCrane_Tracks | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Decal_Big | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Decal_Big_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Decal_Big_NoLC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Decal_Big_NoLC_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Decal_Small1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Decal_Small1_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Decal_Small1_NoLC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Decal_Small1_NoLC_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Decal_Small2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Decal_Small2_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Decal_Small2_NoLC | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Decal_Small2_NoLC_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Digger | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_DollyConverter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_DollyConverter_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_HMMWV | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_HMMWV_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_KA137 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_M113_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_M113_TK_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_M1A2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_M1A2_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Mi24_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Mi24_TK_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Mi8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Mi8_Crashed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_MTVR_Cargo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_MTVR_Cargo_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_MTVR_Fuel | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_MTVR_Fuel_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_MTVR_Water | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_MTVR_Water_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_PowGen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_SantasSleigh | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_SCUDLauncher_Empty | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_SCUDLauncher_Empty_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Ship_Big_BackA | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Ship_Big_BackB | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Ship_Big_Castle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Ship_Big_FrontA | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Ship_Big_FrontB | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Ship_Big_Lifeboat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Ship_Medium_Back | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Ship_Medium_Front | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Stealth_Helicopter_Tail | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Stryker | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Stryker_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_T62_Hull_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_T62_Hull_TK_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_T62_Turret_TK | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_T62_Turret_TK_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_T72_Chassis | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_T72_Chassis_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_T72_Turret | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_T72_Turret_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Trailer_Cistern | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Trailer_Double_Container | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Trailer_Double_Container_Empty | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Trailer_Flat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Trailer_Flat_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Trailer_Single_Container | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Train_742_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Train_742_Blue_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Train_742_Blue_Mil_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Train_742_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Train_742_Red_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Train_742_Red_Mil_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Train_Wagon_Flat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Train_Wagon_Flat_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Train_Wagon_Flat_Mil_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Train_Wagon_Tanker | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Train_Wagon_Tanker_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Train_Wagon_Tanker_Mil_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_UAZ_Aban1_Police | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_UAZ_Aban2_Police | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Uaz_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_UH1Y | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Ural | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StaticObj_Wreck_Ural_DE | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SteakKnife | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SteelheadTrout | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SteelheadTroutFilletMeat | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Stone | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StoneKnife | retain | 50 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StorageBox_Wooden | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Strategic | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:StunBaton | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurgicalGloves_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurgicalGloves_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurgicalGloves_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurgicalGloves_LightBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurgicalGloves_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurgicalMask | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurrenderDummyItem | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorF_Baty | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorF_Eva | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorF_Frida | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorF_Gabi | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorF_Helga | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorF_Irena | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorF_Judy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorF_Keiko | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorF_Linda | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorF_Maria | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorF_Naomi | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorFemale_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Boris | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Cyril | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Denis | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Elias | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Francis | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Guo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Hassan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Indar | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Jose | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Kaito | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Lewis | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Manua | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Mirek | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Niki | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Oliver | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Peter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Quinn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Rolf | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Seth | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorM_Taiki | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:SurvivorMale_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sweater_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sweater_ChristmasBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sweater_ChristmasColorbase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sweater_ChristmasGreen | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sweater_ChristmasRed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sweater_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sweater_Gray | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sweater_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sweater_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Switchable_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Sword | retain | 49 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Syringe | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:T56TankerHelmet_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:T56TankerHelmet_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:T56TankerHelmet_Tan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TacticalBaconCan | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TacticalBaconCan_Opened | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TacticalGloves_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TacticalGloves_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TacticalGloves_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TacticalGloves_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TacticalGoggles | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TacticalShirt_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TacticalShirt_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TacticalShirt_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TacticalShirt_ION_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TacticalShirt_ION_Tan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TacticalShirt_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TacticalShirt_Tan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TaloonBag_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TaloonBag_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TaloonBag_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TaloonBag_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TaloonBag_Violet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TankerHelmet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TannedLeather | retain | 4 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TelescopicBaton | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TelnyashkaShirt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TentBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TerritoryFlag | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TerritoryFlagKit | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TerritoryFlagKitPlacing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TestObject | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TetracyclineAntibiotics | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Thermometer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ThickFramesGlasses | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ThinFramesGlasses | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Thing | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ThingEffect | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ThingEffectFeather | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ThingEffectLight | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TireRepairKit | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TLRLight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Tomato | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TomatoSeeds | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TomatoSeedsPack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Torch | retain | 5 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Torch_Video | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TorsoCover_Improvised | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TortillaBag | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TortillaBag_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TortillaBag_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TrackSuitJacket_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TrackSuitJacket_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TrackSuitJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TrackSuitJacket_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TrackSuitJacket_LightBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TrackSuitJacket_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TrackSuitPants_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TrackSuitPants_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TrackSuitPants_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TrackSuitPants_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TrackSuitPants_LightBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TrackSuitPants_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TraditionalBoots_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TraditionalBoots_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TraditionalBoots_DarkBrown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TraditionalSandalShoes_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TraditionalSandalShoes_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TraditionalSandalShoes_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TraditionalSandalShoes_LightBrown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TraditionalSandalShoes_NavyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Transmitter_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Transport | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Trap_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TrashCan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Tripod | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TripwireTrap | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Cargo | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Cargo_Blue | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Cargo_Grey | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Cargo_Orange | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Chassis | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Chassis_Blue | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Chassis_Grey | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Chassis_Orange | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Covered | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Covered_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Covered_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Door_1_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Door_1_1_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Door_1_1_BlueRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Door_1_1_GreenRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Door_1_1_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Door_1_1_OrangeRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Door_2_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Door_2_1_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Door_2_1_BlueRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Door_2_1_GreenRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Door_2_1_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Door_2_1_OrangeRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Hood | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Hood_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Hood_BlueRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Hood_GreenRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Hood_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Hood_OrangeRust | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Wheel | retain | 4 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_Wheel_Ruined | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_WheelDouble | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Truck_01_WheelDouble_Ruined | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TruckBattery | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TruckDrive | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TrumpetParts | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TShirt_10thAnniversary | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TShirt_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TShirt_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TShirt_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TShirt_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TShirt_Dyed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TShirt_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TShirt_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TShirt_OrangeWhiteStripes | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TShirt_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TShirt_RedBlackStripes | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TShirt_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TTSKOBoots | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TTsKOJacket_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TTsKOJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TTSKOPants | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TunaCan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TunaCan_Opened | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TurbanHat_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TurbanHat_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TurbanHat_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TurbanHat_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TurbanHat_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TurbanHat_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TurbanHat_NavyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TurbanHat_Pink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TurbanHat_Purple | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TurbanHat_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TurbanHat_SkyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TurbanHat_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:TurbanHat_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:UKAssVest_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:UKAssVest_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:UKAssVest_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:UKAssVest_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:UKAssVest_Khaki | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:UKAssVest_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:UKAssVest_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:UndergroundBreadcrumbHandle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:UndergroundStash | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:UndergroundStashSnow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:UndergroundTriggerHandle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:UniversalLight | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:UnknownFoodCan | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:UnknownFoodCan_Opened | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Ushanka_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Ushanka_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Ushanka_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Ushanka_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:USMCJacket_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:USMCJacket_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:USMCJacket_Woodland | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:USMCPants_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:USMCPants_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:USMCPants_Woodland | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:VitaminBottle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:VomitBloodGround | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:VomitGround | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WalleyePollock | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WalleyePollockFilletMeat | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Watchtower | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WatchtowerKit | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WatchtowerKitPlacing | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WaterBottle | retain | 13 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WaterproofBag_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WaterproofBag_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WaterproofBag_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WaterproofBag_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Waterskin_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Waterskin_Natural | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WeaponCleaningKit | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WeldingMask | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Wellies_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Wellies_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Wellies_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Wellies_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Wellies_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Whetstone | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WildboarPelt | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WineBottle | retain | 9 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WinterCoif_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WinterCoif_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WinterCoif_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WinterCoif_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WinterCoif_Skull | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WinterMilitaryCoat_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WinterMilitaryCoat_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WinterMilitaryCoat_DarkGrey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WinterMilitaryCoat_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WitchHat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WitchHood_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WitchHood_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WitchHood_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WitchHood_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WitchHoodCoif_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WitchHoodCoif_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WitchHoodCoif_ColorBase | excluded-definition | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WitchHoodCoif_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WolfPelt | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WolfSteakMeat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WomanSuit_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WomanSuit_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WomanSuit_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WomanSuit_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WomanSuit_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WomanSuit_DarkGrey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WomanSuit_Khaki | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WomanSuit_LightGrey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WomanSuit_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WomensShalwarPants_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WomensShalwarPants_NavyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WomensShalwarPants_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WomensShalwarPants_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WomensShalwarPants_Pink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WomensShalwarPants_Purple | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WomensShalwarPants_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoodAxe | retain | 51 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoodenCrate | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoodenHook | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoodenLog | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoodenPlank | retain | 4 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoodenStick | retain | 29 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolCoat_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolCoat_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolCoat_BlackCheck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolCoat_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolCoat_BlueCheck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolCoat_BrownCheck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolCoat_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolCoat_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolCoat_GreyCheck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolCoat_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolCoat_RedCheck | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolGloves_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolGloves_ChristmasBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolGloves_ChristmasRed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolGloves_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolGloves_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolGloves_Tan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolGloves_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolGlovesFingerless_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolGlovesFingerless_ChristmasBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolGlovesFingerless_ChristmasRed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolGlovesFingerless_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolGlovesFingerless_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolGlovesFingerless_Tan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WoolGlovesFingerless_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WorkingBoots_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WorkingBoots_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WorkingBoots_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WorkingBoots_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WorkingBoots_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WorkingBoots_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WorkingGloves_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WorkingGloves_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WorkingGloves_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WorkingGloves_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WorkingGloves_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:WorldContainer_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Worm | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Wreck_Mi8 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Wreck_Mi8_Crashed | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Wreck_SantasSleigh | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Wreck_UH1Y | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Wrench | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:XmasBaseballBat | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:XmasLights | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Zagorky | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Zagorky_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZagorkyChocolate | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZagorkyPeanuts | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ArmyOfficer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_BlueCollarFat_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_BlueCollarFat_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_BlueCollarFat_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_BlueCollarFat_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_BlueCollarFat_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_CitizenANormal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_CitizenANormal_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_CitizenANormal_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_CitizenANormal_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_CitizenANormal_LT_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_CitizenBSkinny | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_CitizenBSkinny_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_Clerk_Normal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_Clerk_Normal_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_Clerk_Normal_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_Clerk_Normal_LT_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_Clerk_Normal_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_Clerk_Normal_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ClerkFat_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ClerkFat_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ClerkFat_BluePattern | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ClerkFat_GreyPattern | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ClerkFat_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_DoctorSkinny | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_DoctorSkinny_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_eastSoldier_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_eastSoldier_Heavy_Navy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_eastSoldier_Normal_Navy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_HikerSkinny_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_HikerSkinny_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_HikerSkinny_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_HikerSkinny_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_HikerSkinny_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Zmbf_IonSoldier_Normal_1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_JoggerSkinny_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_JoggerSkinny_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_JoggerSkinny_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_JoggerSkinny_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_JournalistNormal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_JournalistNormal_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_JournalistNormal_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_JournalistNormal_LT_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_JournalistNormal_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_JournalistNormal_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_MechanicNormal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_MechanicNormal_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_MechanicNormal_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_MechanicNormal_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_MechanicNormal_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_MilkMaidOld_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_MilkMaidOld_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_MilkMaidOld_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_MilkMaidOld_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_MilkMaidOld_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_MilkMaidOld_LT_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_NurseFat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_NurseFat_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_NurseFat_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ParamedicNormal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ParamedicNormal_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ParamedicNormal_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ParamedicNormal_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_PatientOld | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_PatientOld_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_PatientOld_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_PatrolNormal_Autumn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_PatrolNormal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_PatrolNormal_PautRev | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_PatrolNormal_Summer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_PatrolNormal_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_PoliceWomanNormal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_PoliceWomanNormal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_Runner_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ShortSkirt_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ShortSkirt_beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ShortSkirt_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ShortSkirt_brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ShortSkirt_checks | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ShortSkirt_green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ShortSkirt_grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ShortSkirt_LT_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ShortSkirt_red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ShortSkirt_stripes | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ShortSkirt_white | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_ShortSkirt_yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_SkaterYoung_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_SkaterYoung_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_SkaterYoung_Striped | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_SkaterYoung_Violet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_SoldierNormal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_SoldierNormal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_SurvivorNormal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_SurvivorNormal_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_SurvivorNormal_LT_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_SurvivorNormal_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_SurvivorNormal_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_SurvivorNormal_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenRural_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenRural_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenRural_Flowers | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenRural_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenRural_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenRural_Pink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenRural_Purple | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenRural_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenRural_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanA_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanA_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanA_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanA_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanA_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanB_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanB_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanB_Flowers | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanB_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanB_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanB_Pink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanB_Purple | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanB_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanB_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanC_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanC_NavyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanC_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanC_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanC_Pink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanC_Purple | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanC_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanD_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanD_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanD_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanD_Purple | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiCitizenUrbanD_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiOilRigWorker_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiOilRigWorker_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiOilRigWorker_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiOilRigWorker_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiPoliceWoman | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiPoliceWoman_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_takiPoliceWoman_Heavy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_usSoldier_Heavy_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_usSoldier_Heavy_Woodland | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_usSoldier_normal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_usSoldier_normal_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_usSoldier_normal_Woodland | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_VillagerOld_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_VillagerOld_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_VillagerOld_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_VillagerOld_LT_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_VillagerOld_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbF_VillagerOld_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM__Runner_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_CitizenASkinny_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_CitizenASkinny_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_CitizenASkinny_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_CitizenASkinny_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_CitizenASkinny_LT_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_CitizenASkinny_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_CitizenBFat_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_CitizenBFat_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_CitizenBFat_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_CitizenBFat_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_ClerkFat_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_ClerkFat_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_ClerkFat_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_ClerkFat_Khaki | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_ClerkFat_LT_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_ClerkFat_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_CommercialPilotOld_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_CommercialPilotOld_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_CommercialPilotOld_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_CommercialPilotOld_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_CommercialPilotOld_LT_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_CommercialPilotOld_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_ConstrWorkerNormal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_ConstrWorkerNormal_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_ConstrWorkerNormal_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_ConstrWorkerNormal_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_ConstrWorkerNormal_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_DoctorFat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_DoctorFat_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_DoctorFat_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_eastSoldier_Heavy_Navy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_eastSoldier_normal_Navy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_FarmerFat_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_FarmerFat_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_FarmerFat_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_FarmerFat_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_FarmerFat_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_FarmerFat_LT_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_FirefighterNormal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_FirefighterNormal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_FishermanOld_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_FishermanOld_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_FishermanOld_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_FishermanOld_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_FishermanOld_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Gamedev_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Gamedev_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Gamedev_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Gamedev_Gray | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HandymanNormal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HandymanNormal_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HandymanNormal_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HandymanNormal_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HandymanNormal_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HandymanNormal_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HeavyIndustryWorker | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HeavyIndustryWorker_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HermitSkinny_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HermitSkinny_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HermitSkinny_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HermitSkinny_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HermitSkinny_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HikerSkinny_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HikerSkinny_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HikerSkinny_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HikerSkinny_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HunterOld_Autumn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HunterOld_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HunterOld_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HunterOld_Spring | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HunterOld_Summer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_HunterOld_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_IonSoldier_Normal_1_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_IonSoldier_Normal_1_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_IonSoldier_Normal_1_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_IonSoldier_Normal_1_Tan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_IonSoldier_Normal_2_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_IonSoldier_Normal_2_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_IonSoldier_Normal_2_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_IonSoldier_Normal_2_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_IonSoldier_Normal_3 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_IonSoldier_Normal_3_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Jacket_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Jacket_beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Jacket_black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Jacket_blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Jacket_bluechecks | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Jacket_brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Jacket_greenchecks | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Jacket_grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Jacket_khaki | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Jacket_LT_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Jacket_magenta | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Jacket_stripes | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_JoggerSkinny_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_JoggerSkinny_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_JoggerSkinny_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_JournalistSkinny | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_JournalistSkinny_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_MechanicSkinny_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_MechanicSkinny_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_MechanicSkinny_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_MechanicSkinny_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_MechanicSkinny_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_MotobikerFat_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_MotobikerFat_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_MotobikerFat_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_MotobikerFat_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Mummy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_NBC_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_NBC_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_NBC_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_OffshoreWorker_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_OffshoreWorker_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_OffshoreWorker_Orange | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_OffshoreWorker_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_OffshoreWorker_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_ParamedicNormal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_ParamedicNormal_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_ParamedicNormal_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_ParamedicNormal_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_ParamedicNormal_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_PatientSkinny | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_PatientSkinny_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_PatientSkinny_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_PatrolNormal_Autumn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_PatrolNormal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_PatrolNormal_Flat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_PatrolNormal_PautRev | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_PatrolNormal_Summer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_PatrolNormal_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_PolicemanFat | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_PolicemanFat_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_PolicemanSpecForce | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_PolicemanSpecForce_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_PolicemanSpecForce_Heavy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_priestPopSkinny | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_priestPopSkinny_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_PrisonerSkinny | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_PrisonerSkinny_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_Santa | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_SkaterYoung_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_SkaterYoung_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_SkaterYoung_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_SkaterYoung_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_SkaterYoung_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_SkaterYoung_LT_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_SoldierNormal | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_SoldierNormal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenRural_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenRural_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenRural_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenRural_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenRural_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenRural_NavyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenRural_SkyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenRural_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanA_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanA_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanA_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanA_Cream | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanA_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanB_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanB_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanB_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanB_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanB_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanB_NavyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanB_SkyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanB_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanC_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanC_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanC_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanC_BlueBright | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanC_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanC_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiCitizenUrbanC_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiHermitA_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiHermitA_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiHermitA_NavyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiHermitB_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiHermitB_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiHermitB_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiHiker_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiHiker_Beige | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiHiker_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiHiker_NavyBlue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiHiker_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiImam | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiImam_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiImam_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiOilRigWorker_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiOilRigWorker_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiOilRigWorker_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiOilRigWorker_Yellow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiPoliceman | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiPoliceman_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiPoliceman_Heavy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiSoldier_Normal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiSoldier_Normal_Olive | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiSoldier_Normal_Tan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiSoldier_Officer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_takiSoldier_Officer_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_usSoldier_Heavy_Woodland | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_usSoldier_normal_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_usSoldier_normal_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_usSoldier_normal_Woodland | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_usSoldier_Officer_Convoy | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_usSoldier_Officer_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_VillagerOld_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_VillagerOld_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_VillagerOld_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_VillagerOld_LT_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmbM_VillagerOld_White | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmijovkaCap_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmijovkaCap_Blue | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmijovkaCap_Brown | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmijovkaCap_ColorBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmijovkaCap_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZmijovkaCap_Red | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZombieBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZombieFemaleBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZombieMaleBase | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZSh3PilotHelmet | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZSh3PilotHelmet_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZSh3PilotHelmet_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:Zucchini | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZucchiniSeeds | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgVehicles:ZucchiniSeedsPack | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:AK101 | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:AK101_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:AK101_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:AK101_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:AK74 | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:AK74_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:AK74_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:AK74_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:AKM | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:AKM_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:AKM_Gold | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:AKM_TESTBED | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:AKS74U | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:AKS74U_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:AKS74U_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Archery_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:ASVAL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Aug | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Aug_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:AugShort | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:B95 | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:B95_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:B95_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:B95_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:BoltActionRifle_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:BoltActionRifle_ExternalMagazine_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:BoltActionRifle_InnerMagazine_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Colt1911 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Colt1911_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Crossbow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Crossbow_Autumn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Crossbow_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Crossbow_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Crossbow_Summer | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Crossbow_Wood | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:CZ527 | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:CZ527_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:CZ527_Black | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:CZ527_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:CZ527_desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:CZ527_Green | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:CZ527_winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:CZ527_Woodland | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:CZ550 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:CZ550_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:CZ61 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:CZ61_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:CZ75 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:CZ75_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:DartGun | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Deagle | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Deagle_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Deagle_Gold | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:DefaultWeapon | excluded-definition | 3 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Derringer_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Derringer_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Derringer_Grey | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Derringer_Pink | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Engraved1911 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:FAL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:FAL_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:FAMAS | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Famas_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Flaregun | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Flaregun_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:FNX45 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:FNX45_arrow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:FNX45_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Glock19 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Glock19_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Glock19_Tan | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:GP25 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:GP25_Standalone | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:GP25Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Groza | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Groza_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Izh18 | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Izh18_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Izh18Shotgun | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Izh18Shotgun_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Izh43Shotgun | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Izh43Shotgun_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Launcher_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:LauncherCore | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:LAW | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:LAWBase | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:LeeEnfield | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:LeeEnfield_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:LongHorn | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:LongHorn_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Luger | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Luger_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:M14 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:M14_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:M16A2 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:M16A2_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:M203 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:M203_Standalone | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:M203Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:M249 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:M249_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:M4A1 | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:M4A1_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:M4A1_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:M4A1_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:M79 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:M79_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Magnum | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Magnum_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Magnum_Gold | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:MakarovIJ70 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:MakarovIJ70_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:MakarovPB | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:MakarovPB_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:MKII | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:MKII_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Mosin9130 | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Mosin9130_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Mosin9130_Black | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Mosin9130_Camo | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Mosin9130_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Mosin9130_Green | retain | 3 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Mosin9130_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Mosin9130_Woodland | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Mp133Shotgun | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Mp133Shotgun_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Mp133Shotgun_PistolGrip | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:MP18 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:MP18_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:MP5K | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:MP5K_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:NonlethalCore | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:NonlethalPistol | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:NonlethalRifle | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:P1 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:P1_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Pistol_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:PistolCore | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:PM73Rak | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:PM73Rak_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:PP19 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:PP19_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:PVCBow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:QuickieBow | retain | 2 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:R12 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:R12_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:RecurveBow | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Red9 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Red9_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Repeater | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Repeater_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Rifle_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:RifleCore | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:RPG7 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:RPG7Base | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Ruger1022 | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Ruger1022_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Saiga | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Saiga_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SawedoffB95 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SawedoffFAMAS | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SawedoffIzh18 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SawedoffIzh18Shotgun | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SawedoffIzh43Shotgun | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SawedoffMagnum | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SawedoffMagnum_Gold | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SawedoffMosin9130 | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SawedoffMosin9130_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SawedoffMosin9130_Black | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SawedoffMosin9130_Camo | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SawedoffMosin9130_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SawedoffMosin9130_Green | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SawedoffMosin9130_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SawedoffMosin9130_Woodland | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SCARH | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SCARH_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SCARH_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SCARL | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SCARL_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SCARL_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Scout | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Scout_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Scout_Chernarus | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Scout_Livonia | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Shockpistol | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Shockpistol_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Shockpistol_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Shotgun_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SKS | retain | 1 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SKS_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SKS_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SKS_Desert | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SKS_Green | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SKS_Winter | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SKS_Woodland | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SSG82 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SSG82_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SV98 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SV98_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SVD | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SVD_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:SVD_Wooden | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Trumpet | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Trumpet_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:UMP45 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:UMP45_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:UnderSlugGrenadeM4 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Vikhr | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:VSS | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:VSS_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Weapon_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Winchester70 | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Winchester70_Base | excluded-definition | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Winchester70_Black | retain | 0 | UNKNOWN / NOT_DERIVED |
| CfgWeapons:Winchester70_Green | retain | 0 | UNKNOWN / NOT_DERIVED |

### Exhaustive recipe decision classification

All literal alternatives and result multiplicities are retained below; dynamic/custom semantics remain in the full census.
An empty literal-result list can denote in-place mutation or unresolved custom output; it does not prove a no-op.

| Recipe | Source status | Exact literal input slots | Exact literal result calls | Decision | Anchor |
| --- | --- | --- | --- | --- | --- |
| AttachHolster | unregistered | {"0": ["PlateCarrierBlank"], "1": ["CarrierHolsterSolo"]} | ["PlateCarrierHolster"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/AttachHolster.c:1 |
| AttachHolsterPouch | registered | {"0": ["PlateCarrierPouches"], "1": ["CarrierHolsterSolo"]} | ["PlateCarrierComplete"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/AttachHolsterPouch.c:1 |
| AttachPouch | unregistered | {"0": ["PlateCarrierBlank"], "1": ["CarrierPouches"]} | ["PlateCarrierPouches"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/AttachPouch.c:1 |
| AttachPouchesHolster | registered | {"0": ["PlateCarrierHolster"], "1": ["CarrierPouches"]} | ["PlateCarrierComplete"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/AttachPouchesHolster.c:1 |
| BloodTest | registered | {"0": ["BloodTestKit"], "1": ["BloodSyringe", "BloodBagFull", "BloodBagIV"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/BloodTest.c:1 |
| ChelateWater | registered | {"0": ["ChelatingTablets"], "1": ["Pot", "CanisterGasoline", "DisinfectantAlcohol", "Canteen", "WaterBottle", "FilteringBottle", "GlassBottle", "WineBottle", "WaterPouch_ColorBase", "Barrel_ColorBase", "Cauldron", "AyranBottle"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/ChelateWater.c:1 |
| CleanRags | disabled | {"0": ["Rag"], "1": ["Pot", "CanisterGasoline", "Canteen", "WaterBottle", "FilteringBottle", "GlassBottle", "WaterPouch_ColorBase", "Barrel_ColorBase", "AyranBottle"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/CleanRags.c:1 |
| CleanWeapon | registered | {"0": ["WeaponCleaningKit"], "1": ["DefaultWeapon", "DefaultMagazine", "ItemSuppressor"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CleanWeapon.c:1 |
| CloseGunCase | registered | {"0": ["GunCase_ColorBase"], "1": ["GunCaseKeys_Colorbase"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CloseGunCase.c:1 |
| CloseScientificBriefcase | registered | {"0": ["ScientificBriefcase"], "1": ["ScientificBriefcaseKeys"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CloseScientificBriefcase.c:1 |
| CraftArmbandFlag | registered | {"0": ["Flag_Base"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "Akinaka"]} | ["Armband_", "Armband_", "Armband_"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftArmbandFlag.c:1 |
| CraftArmbandRag | registered | {"0": ["Rag"], "1": ["SewingKit"]} | ["Armband_White"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftArmbandRag.c:1 |
| CraftArmbandRaincoat | registered | {"0": ["Raincoat_ColorBase"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "BrickTrowel", "Akinaka"]} | ["Armband_", "Armband_", "Armband_", "Armband_", "Armband_"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftArmbandRaincoat.c:1 |
| CraftArrow | disabled | {"0": ["ChickenFeather"], "1": ["Ammo_SharpStick"]} | ["Ammo_ArrowPrimitive"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/CraftArrow.c:1 |
| CraftArrowBone | disabled | {"0": ["Ammo_ArrowPrimitive"], "1": ["Bone"]} | ["Ammo_ArrowBoned"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/CraftArrowBone.c:1 |
| CraftBait | disabled | {"0": ["Worm"], "1": ["Hook"]} | ["Bait"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/CraftBait.c:1 |
| CraftBaseBallBatBarbed | registered | {"0": ["BarbedWire"], "1": ["BaseballBat"]} | ["BarbedBaseballBat"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftBaseBallBatBarbed.c:1 |
| CraftBaseBallBatNailed | registered | {"0": ["Nail"], "1": ["BaseballBat"]} | ["NailedBaseballBat"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftBaseBallBatNailed.c:1 |
| CraftBloodBagIV | registered | {"0": ["StartKitIV"], "1": ["BloodBagFull"]} | ["BloodBagIV"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftBloodBagIV.c:1 |
| CraftBoneBait | disabled | {"0": ["Worm"], "1": ["BoneHook"]} | ["BoneBait"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/CraftBoneBait.c:1 |
| CraftBoneHook | registered | {"0": ["Bone"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Iceaxe", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["BoneHook"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftBoneHook.c:1 |
| CraftBoneKnife | registered | {"0": ["Bone"], "1": ["Stone", "SmallStone"]} | ["BoneKnife"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftBoneKnife.c:1 |
| CraftBow | unregistered | {"0": ["Rope"], "1": ["LongWoodenStick"]} | ["QuickieBow"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/CraftBow.c:1 |
| CraftBurlapStrips | registered | {"0": ["BurlapSack"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Iceaxe", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["BurlapStrip"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftBurlapStrips.c:1 |
| CraftCamoNetShelter | disabled | {"0": ["CamoNet"], "1": ["LongWoodenStick"]} | ["CamoNetShelter"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/CraftCamoNetShelter.c:1 |
| CraftChristmasLightsHeadband | registered | {"0": ["ChristmasHeadband_Trees", "ChristmasHeadband_Antlers", "ChristmasHeadband_Gingerbread"], "1": ["XmasLights"]} | ["ChristmasHeadband"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftChristmasLightsHeadband.c:1 |
| CraftCookingStand | registered | {"0": ["WoodenStick"], "1": ["LongWoodenStick", "SharpWoodenStick"]} | ["CookingStand"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftCookingStand.c:1 |
| CraftCourierBag | registered | {"0": ["BurlapSack"], "1": ["Rope"]} | ["CourierBag"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftCourierBag.c:1 |
| CraftDrysackBag | registered | {"0": ["WaterproofBag_ColorBase"], "1": ["Rope"]} | ["DrysackBag_"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftDrysackBag.c:1 |
| CraftFeathers | registered | {"0": ["Sickle", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "KukriKnife", "FangeKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "FarmingHoe", "Shovel", "FieldShovel", "BoneKnife", "Iceaxe", "Scimitar", "DonerKnife", "BrickTrowel"], "1": ["Akinaka", "Inventory_Base"]} | ["ChickenFeather"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftFeathers.c:1 |
| CraftFenceKit | registered | {"0": ["Rope"], "1": ["WoodenStick", "Ammo_SharpStick"]} | ["FenceKit"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftFenceKit.c:1 |
| CraftFireplace | registered | {"0": ["WoodenStick", "Firewood", "Rag", "BandageDressing", "Paper", "ItemBook", "Bark_Birch", "Bark_Oak", "Bark_Palm", "MorsecodeLeaflet_blood", "MorsecodeLeaflet_fire", "MorsecodeLeaflet_coffee"], "1": ["WoodenStick", "Firewood", "Rag", "BandageDressing", "Paper", "GiftWrapPaper", "ItemBook", "Bark_Birch", "Bark_Oak", "Bark_Palm", "EyeMask_ColorBase", "MorsecodeLeaflet_blood", "MorsecodeLeaflet_fire", "MorsecodeLeaflet_coffee"]} | ["Fireplace"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftFireplace.c:1 |
| CraftFishNetTrap | registered | {"0": ["Netting"], "1": ["MetalWire"]} | ["FishNetTrap"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftFishNetTrap.c:1 |
| CraftFishingRod | registered | {"0": ["Rope"], "1": ["LongWoodenStick", "SharpWoodenStick"]} | ["ImprovisedFishingRod"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftFishingRod.c:1 |
| CraftFoxHeaddress | registered | {"0": ["FoxPelt"], "1": ["LeatherSewingKit"]} | ["Headdress_Fox"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftFoxHeaddress.c:1 |
| CraftGasMask_Filter_Improvised | registered | {"0": ["WaterBottle"], "1": ["NioshFaceMask"]} | ["GasMask_Filter_Improvised"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftGasMask_Filter_Improvised.c:1 |
| CraftGhillieAttachment | registered | {"0": ["Netting"], "1": ["BurlapStrip"]} | ["GhillieAtt_Tan"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftGhillieAttachment.c:1 |
| CraftGhillieBushrag | registered | {"0": ["Netting"], "1": ["BurlapStrip"]} | ["GhillieBushrag_Tan"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftGhillieBushrag.c:1 |
| CraftGhillieHood | registered | {"0": ["Netting"], "1": ["BurlapStrip"]} | ["GhillieHood_Tan"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftGhillieHood.c:1 |
| CraftGhillieSuit | registered | {"0": ["Netting"], "1": ["BurlapStrip"]} | ["GhillieSuit_Tan"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftGhillieSuit.c:1 |
| CraftGhillieTop | registered | {"0": ["Netting"], "1": ["BurlapStrip"]} | ["GhillieTop_Tan"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftGhillieTop.c:1 |
| CraftGorkaHelmetComplete | disabled | {"0": ["GorkaHelmet"], "1": ["GorkaHelmetVisor"]} | ["GorkaHelmetComplete_"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/CraftGorkaHelmetComplete.c:1 |
| CraftGutsRope | registered | {"0": ["Guts"], "1": ["Sickle", "KukriKnife", "FangeKnife", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["Rope"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftGutsRope.c:1 |
| CraftHandDrillKit | registered | {"0": ["Bark_Oak"], "1": ["WoodenStick", "Ammo_SharpStick"]} | ["HandDrillKit"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftHandDrillKit.c:1 |
| CraftHandDrillKitBirch | registered | {"0": ["Bark_Birch"], "1": ["WoodenStick", "Ammo_SharpStick"]} | ["HandDrillKitBirch"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftHandDrillKitBirch.c:1 |
| CraftHandDrillKitPalm | registered | {"0": ["Bark_Palm"], "1": ["WoodenStick", "Ammo_SharpStick"]} | ["HandDrillKitPalm"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftHandDrillKitPalm.c:1 |
| CraftImprovisedBag | registered | {"0": ["WoodenStick"], "1": ["CourierBag"]} | ["ImprovisedBag"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftImprovisedBag.c:1 |
| CraftImprovisedExplosive | registered | {"0": ["SmallProtectorCase"], "1": ["ElectronicRepairKit"]} | ["ImprovisedExplosive"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftImprovisedExplosive.c:1 |
| CraftImprovisedLeatherBag | registered | {"0": ["WoodenStick"], "1": ["FurCourierBag"]} | ["FurImprovisedBag"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftImprovisedLeatherBag.c:1 |
| CraftLeatherBelt | registered | {"0": ["LizardPelt"], "1": ["LeatherSewingKit"]} | ["LeatherBelt_Lizard"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftLeatherBelt.c:1 |
| CraftLeatherCourierBag | registered | {"0": ["WildboarPelt"], "1": ["Rope"]} | ["FurCourierBag"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftLeatherCourierBag.c:1 |
| CraftLeatherHippack | registered | {"0": ["LizardPelt"], "1": ["LeatherSewingKit"]} | ["LeatherHippack_Lizard"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftLeatherHippack.c:1 |
| CraftLeatherSack | registered | {"0": ["TannedLeather"], "1": ["LeatherSewingKit"]} | ["LeatherSack_Brown"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftLeatherSack.c:1 |
| CraftLeatherSheath | registered | {"0": ["LizardPelt"], "1": ["LeatherSewingKit"]} | ["LizardKnifeSheath"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftLeatherSheath.c:1 |
| CraftLongTorch | registered | {"0": ["Rag"], "1": ["LongWoodenStick", "SharpWoodenStick"]} | ["LongTorch"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftLongTorch.c:1 |
| CraftMetalWire | registered | {"0": ["BarbedWire"], "1": ["Pliers"]} | ["MetalWire"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftMetalWire.c:1 |
| CraftMortarMix | registered | {"0": ["MortarMix"], "1": ["Pot", "CanisterGasoline", "Canteen", "WaterBottle", "FilteringBottle", "GlassBottle", "WineBottle", "WaterPouch_ColorBase", "Barrel_ColorBase", "AyranBottle"]} | ["MortarMix_Opened"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftMortarMix.c:1 |
| CraftRabbitSnare | registered | {"0": ["WoodenStick"], "1": ["MetalWire"]} | ["RabbitSnareTrap"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftRabbitSnare.c:1 |
| CraftRag | registered | {"0": ["Sickle", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "KukriKnife", "FangeKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "FarmingHoe", "Shovel", "FieldShovel", "BoneKnife", "Iceaxe", "BrickTrowel", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"], "1": ["Inventory_Base"]} | ["Rag"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftRag.c:1 |
| CraftRagRope | registered | {"0": ["Rag"], "1": ["Rag"]} | ["Rope"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftRagRope.c:1 |
| CraftSalineBagIV | registered | {"0": ["StartKitIV"], "1": ["SalineBag"]} | ["SalineBagIV"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftSalineBagIV.c:1 |
| CraftShelterKit | registered | {"0": ["Rope"], "1": ["WoodenStick", "Ammo_SharpStick"]} | ["ShelterKit"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftShelterKit.c:1 |
| CraftSmallFishTrap | registered | {"0": ["WaterBottle"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Iceaxe", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["SmallFishTrap"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftSmallFishTrap.c:1 |
| CraftSpearBone | registered | {"0": ["BoneKnife"], "1": ["LongWoodenStick", "SharpWoodenStick"]} | ["SpearBone"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftSpearBone.c:1 |
| CraftSpearStone | registered | {"0": ["StoneKnife"], "1": ["LongWoodenStick", "SharpWoodenStick"]} | ["SpearStone"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftSpearStone.c:1 |
| CraftSplint | registered | {"0": ["BandageDressing", "Rag", "DuctTape", "Shemag_ColorBase"], "1": ["WoodenStick"]} | ["Splint"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftSplint.c:1 |
| CraftStoneKnife | registered | {"0": ["SmallStone"], "1": ["SmallStone", "Stone"]} | ["StoneKnife"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftStoneKnife.c:1 |
| CraftSuppressor | registered | {"0": ["WaterBottle"], "1": ["DuctTape"]} | ["ImprovisedSuppressor"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftSuppressor.c:1 |
| CraftTannedLeather | registered | {"0": ["Pelt_Base"], "1": ["GardenLime"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftTannedLeather.c:1 |
| CraftTerritoryFlagKit | registered | {"0": ["Rope"], "1": ["WoodenStick", "Ammo_SharpStick"]} | ["TerritoryFlagKit"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftTerritoryFlagKit.c:1 |
| CraftTorch | registered | {"0": ["Rag"], "1": ["WoodenStick", "Ammo_SharpStick"]} | ["Torch"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftTorch.c:1 |
| CraftTripWire | registered | {"0": ["WoodenStick"], "1": ["MetalWire"]} | ["TripwireTrap"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftTripWire.c:1 |
| CraftTruck01DoubleWheel | registered | {"0": ["Truck_01_Wheel"], "1": ["Truck_01_Wheel"]} | ["Truck_01_WheelDouble"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftTruck01DoubleWheel.c:1 |
| CraftWatchtowerKit | registered | {"0": ["Rope"], "1": ["WoodenStick", "Ammo_SharpStick"]} | ["WatchtowerKit"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftWatchtowerKit.c:1 |
| CraftWaterskin | registered | {"0": ["TannedLeather"], "1": ["LeatherSewingKit"]} | ["Waterskin_Natural"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftWaterskin.c:1 |
| CraftWitchHoodCoif | registered | {"0": ["WitchHood_ColorBase"], "1": ["Chainmail_Coif"]} | ["WitchHoodCoif_"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftWitchHoodCoif.c:1 |
| CraftWoodenCrate | registered | {"0": ["WoodenPlank"], "1": ["Nail"]} | ["WoodenCrate"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftWoodenCrate.c:1 |
| CraftWoodenHook | registered | {"0": ["WoodenStick"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Iceaxe", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["WoodenHook", "WoodenHook"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftWoodenHook.c:1 |
| CraftWoodenPlank | registered | {"0": ["WoodenLog"], "1": ["Hacksaw", "HandSaw"]} | ["WoodenPlank"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CraftWoodenPlank.c:1 |
| CutOutPepperSeeds | registered | {"0": ["GreenBellPepper"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["PepperSeeds"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CutOutPepperSeeds.c:1 |
| CutOutPumpkinSeeds | registered | {"0": ["Pumpkin"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "KitchenKnife", "SteakKnife", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "FarmingHoe", "Shovel", "Crowbar", "Hammer", "Mace", "Wrench", "LugWrench", "Screwdriver", "SledgeHammer", "BaseballBat", "Pickaxe", "Sword", "WoodAxe", "FirefighterAxe", "Hatchet", "HandSaw", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["PumpkinSeeds", "SlicedPumpkin", "SlicedPumpkin"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CutOutPumpkinSeeds.c:1 |
| CutOutSeeds | unregistered | {} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/CutOutSeeds.c:1 |
| CutOutTomatoSeeds | registered | {"0": ["Tomato"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["TomatoSeeds"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CutOutTomatoSeeds.c:1 |
| CutOutZucchiniSeeds | registered | {"0": ["Zucchini"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["ZucchiniSeeds"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/CutOutZucchiniSeeds.c:1 |
| DeCraftArmband | unregistered | {"0": ["Armband_ColorBase"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["Rag"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/DeCraftArmband.c:3 |
| DeCraftBow | unregistered | {"0": ["QuickieBow"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["LongWoodenStick"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/DeCraftBow.c:1 |
| DeCraftCamoNetShelter | registered | {"0": ["CamoNetShelter"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["LongWoodenStick", "CamoNet"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftCamoNetShelter.c:1 |
| DeCraftCarrierComplete | unregistered | {"0": ["PlateCarrierComplete"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["PlateCarrierBlank", "CarrierHolsterSolo", "CarrierPouches"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/DeCraftCarrierComplete.c:1 |
| DeCraftCarrierHolster | unregistered | {"0": ["PlateCarrierHolster"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["PlateCarrierBlank", "CarrierHolsterSolo"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/DeCraftCarrierHolster.c:1 |
| DeCraftCarrierPouches | unregistered | {"0": ["PlateCarrierPouches"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["PlateCarrierBlank", "CarrierPouches"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/DeCraftCarrierPouches.c:1 |
| DeCraftCookingStand | registered | {"0": ["CookingStand"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["WoodenStick"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftCookingStand.c:1 |
| DeCraftCourierBag | registered | {"0": ["CourierBag"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["BurlapSack", "Rope"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftCourierBag.c:1 |
| DeCraftDetonator | registered | {"0": ["RemoteDetonator"], "1": ["Screwdriver"]} | ["Battery9V"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftDetonator.c:3 |
| DeCraftFishNetTrap | registered | {"0": ["FishNetTrap"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["MetalWire", "Netting"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftFishNetTrap.c:1 |
| DeCraftFishingRod | registered | {"0": ["ImprovisedFishingRod"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["LongWoodenStick", "Rope"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftFishingRod.c:1 |
| DeCraftGhillieAttachment | registered | {"0": ["GhillieAtt_ColorBase"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["Netting", "BurlapStrip"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftGhillieAttachment.c:1 |
| DeCraftGhillieBushrag | registered | {"0": ["GhillieBushrag_ColorBase"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["Netting", "BurlapStrip"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftGhillieBushrag.c:1 |
| DeCraftGhillieHood | registered | {"0": ["GhillieHood_ColorBase"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["Netting", "BurlapStrip"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftGhillieHood.c:1 |
| DeCraftGhillieSuit | registered | {"0": ["GhillieSuit_ColorBase"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["Netting", "BurlapStrip"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftGhillieSuit.c:1 |
| DeCraftGhillieTop | registered | {"0": ["GhillieTop_ColorBase"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["Netting", "BurlapStrip"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftGhillieTop.c:1 |
| DeCraftHandDrillKit | registered | {"0": ["HandDrillKit"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["WoodenStick"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftHandDrillKit.c:1 |
| DeCraftHandDrillKitBirch | registered | {"0": ["HandDrillKitBirch"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["WoodenStick"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftHandDrillKitBirch.c:1 |
| DeCraftHandDrillKitPalm | registered | {"0": ["HandDrillKitPalm"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["WoodenStick"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftHandDrillKitPalm.c:1 |
| DeCraftImprovisedBag | registered | {"0": ["ImprovisedBag"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["WoodenStick", "BurlapSack"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftImprovisedBag.c:1 |
| DeCraftImprovisedLeatherBag | registered | {"0": ["FurImprovisedBag"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["WoodenStick", "WildboarPelt"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftImprovisedLeatherBag.c:1 |
| DeCraftLeatherCourierBag | registered | {"0": ["FurCourierBag"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "BoneKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["WildboarPelt", "Rope"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftLeatherCourierBag.c:1 |
| DeCraftLeatherSack | registered | {"0": ["LeatherSack_ColorBase"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["TannedLeather"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftLeatherSack.c:1 |
| DeCraftSnareTrap | registered | {"0": ["RabbitSnareTrap"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["MetalWire"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftSnareTrap.c:1 |
| DeCraftSpear | registered | {"0": ["Spear"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["LongWoodenStick"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftSpear.c:1 |
| DeCraftSplint | registered | {"0": ["Splint"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["WoodenStick"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftSplint.c:1 |
| DeCraftTripWire | registered | {"0": ["TripwireTrap"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["MetalWire"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftTripWire.c:1 |
| DeCraftTruck01DoubleWheel | registered | {"0": ["Truck_01_WheelDouble"], "1": ["Crowbar", "LugWrench"]} | ["Truck_01_Wheel", "Truck_01_Wheel"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftTruck01DoubleWheel.c:1 |
| DeCraftWaterskin | registered | {"0": ["Waterskin_ColorBase"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["TannedLeather"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftWaterskin.c:1 |
| DeCraftWoodenCrate | registered | {"0": ["WoodenCrate"], "1": ["Crowbar", "WoodAxe", "Hatchet", "FirefighterAxe"]} | ["WoodenPlank", "Nail"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DeCraftWoodenCrate.c:1 |
| DisinfectItem | registered | {"0": ["DisinfectantSpray", "DisinfectantAlcohol", "IodineTincture"], "1": ["Inventory_Base"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/DisinfectItem.c:1 |
| DrainLiquid | unregistered | {"0": ["Pot", "CanisterGasoline", "Canteen", "WaterBottle", "FilteringBottle", "GlassBottle", "WineBottle", "WaterPouch_ColorBase", "Barrel_ColorBase", "AyranBottle", "AyranBottle"], "1": ["Pot", "CanisterGasoline", "Canteen", "WaterBottle", "FilteringBottle", "GlassBottle", "WineBottle", "WaterPouch_ColorBase", "Barrel_ColorBase"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/DrainLiquid.c:1 |
| ExtinguishTorch | registered | {"0": ["Torch", "Broom"], "1": ["Pot", "CanisterGasoline", "DisinfectantAlcohol", "Canteen", "WaterBottle", "FilteringBottle", "GlassBottle", "WineBottle", "WaterPouch_ColorBase", "Barrel_ColorBase", "AyranBottle"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/ExtinguishTorch.c:1 |
| FillGasMask_Filter | registered | {"0": ["CharcoalTablets"], "1": ["GasMask_Filter", "GasMask_Filter_Improvised"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/FillGasMask_Filter.c:1 |
| FillSyringe | registered | {"0": ["InjectionVial"], "1": ["Syringe"]} | ["ClearSyringe"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/FillSyringe.c:1 |
| FuelChainsaw | registered | {"0": ["Chainsaw"], "1": ["Pot", "CanisterGasoline", "DisinfectantAlcohol", "Canteen", "WaterBottle", "FilteringBottle", "GlassBottle", "WineBottle", "WaterPouch_ColorBase", "Barrel_ColorBase", "AyranBottle"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/FuelChainsaw.c:1 |
| LoadMagazine | unregistered | {"0": ["Ammunition_Base"], "1": ["Magazine_Base"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/LoadMagazine.c:1 |
| OpenCan | registered | {"0": ["BakedBeansCan", "PeachesCan", "TacticalBaconCan", "SpaghettiCan", "SardinesCan", "UnknownFoodCan"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "KitchenKnife", "SteakKnife", "StoneKnife", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "CanOpener", "FarmingHoe", "Shovel", "FieldShovel", "Crowbar", "Hammer", "Mace", "Wrench", "LugWrench", "Screwdriver", "SledgeHammer", "BaseballBat", "NailedBaseballBat", "BarbedBaseballBat", "XmasBaseballBat", "PipeWrench", "Pickaxe", "WoodAxe", "FirefighterAxe", "Hatchet", "HandSaw", "Pliers", "Spear", "Pitchfork", "BoneKnife", "MeatTenderizer", "Cleaver", "Sword", "Iceaxe", "BrickTrowel", "Scimitar", "DonerKnife", "Akinaka"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/OpenCan.c:1 |
| OpenGunCase | registered | {"0": ["GunCase_ColorBase"], "1": ["GunCaseKeys_Colorbase"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/OpenGunCase.c:1 |
| OpenScientificBriefcase | registered | {"0": ["ScientificBriefcase"], "1": ["ScientificBriefcaseKeys"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/OpenScientificBriefcase.c:1 |
| PaintAK101 | disabled | {"0": ["Spraycan_ColorBase"], "1": ["AK101"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintAK101.c:1 |
| PaintAK10130Mag | disabled | {"0": ["Spraycan_ColorBase"], "1": ["Mag_AK101_30Rnd"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintAK10130Mag.c:1 |
| PaintAK74 | disabled | {"0": ["Spraycan_ColorBase"], "1": ["AK74"]} | ["AK74_"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintAK74.c:1 |
| PaintAK7430Mag | disabled | {"0": ["Spraycan_ColorBase"], "1": ["Mag_AK74_30Rnd"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintAK7430Mag.c:1 |
| PaintAK74HndgrdBlack | disabled | {"0": ["Spraycan_Black"], "1": ["AK74_Hndgrd"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintAK74HndgrdBlack.c:1 |
| PaintAK74HndgrdCamo | disabled | {"0": ["Spraycan_Green"], "1": ["AK74_Hndgrd"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintAK74HndgrdCamo.c:1 |
| PaintAK74WoodBttstckBlack | disabled | {"0": ["Spraycan_Black"], "1": ["AK74_WoodBttstck"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintAK74WoodBttstckBlack.c:1 |
| PaintAK74WoodBttstckCamo | disabled | {"0": ["Spraycan_Green"], "1": ["AK74_WoodBttstck"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintAK74WoodBttstckCamo.c:1 |
| PaintAKFoldingBttstck | disabled | {"0": ["Spraycan_ColorBase"], "1": ["AK_FoldingBttstck"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintAKFoldingBttstck.c:1 |
| PaintAKMDrumMag | disabled | {"0": ["Spraycan_ColorBase"], "1": ["Mag_AKM_Drum75Rnd"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintAKMDrumMag.c:1 |
| PaintAKMPalm30Mag | disabled | {"0": ["Spraycan_ColorBase"], "1": ["Mag_AKM_Palm30Rnd"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintAKMPalm30Mag.c:1 |
| PaintAKPlasticBttstck | disabled | {"0": ["Spraycan_ColorBase"], "1": ["AK_PlasticBttstck"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintAKPlasticBttstck.c:1 |
| PaintAKRailHndgrd | disabled | {"0": ["Spraycan_ColorBase"], "1": ["AK_RailHndgrd"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintAKRailHndgrd.c:1 |
| PaintAKS74U | disabled | {"0": ["Spraycan_ColorBase"], "1": ["AKS74U"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintAKS74U.c:1 |
| PaintAKS74UBttstck | disabled | {"0": ["Spraycan_ColorBase"], "1": ["AKS74U_Bttstck"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintAKS74UBttstck.c:1 |
| PaintAKWoodBttstckBlack | disabled | {"0": ["Spraycan_Black"], "1": ["AK_WoodBttstck"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintAKWoodBttstckBlack.c:1 |
| PaintAKWoodBttstckCamo | disabled | {"0": ["Spraycan_Green"], "1": ["AK_WoodBttstck"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintAKWoodBttstckCamo.c:1 |
| PaintB95 | disabled | {"0": ["Spraycan_ColorBase"], "1": ["B95"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintB95.c:1 |
| PaintBallisticHelmet | disabled | {"0": ["Spraycan_ColorBase"], "1": ["BallisticHelmet_ColorBase"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintBallisticHelmet.c:1 |
| PaintCMAG10 | disabled | {"0": ["Spraycan_ColorBase"], "1": ["Mag_CMAG_10Rnd"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintCMAG10.c:1 |
| PaintCMAG20 | disabled | {"0": ["Spraycan_ColorBase"], "1": ["Mag_CMAG_20Rnd"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintCMAG20.c:1 |
| PaintCMAG30 | disabled | {"0": ["Spraycan_ColorBase"], "1": ["Mag_CMAG_30Rnd"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintCMAG30.c:1 |
| PaintCMAG40 | disabled | {"0": ["Spraycan_ColorBase"], "1": ["Mag_CMAG_40Rnd"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintCMAG40.c:1 |
| PaintCz527 | disabled | {"0": ["Spraycan_ColorBase"], "1": ["CZ527"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintCz527.c:1 |
| PaintCz527CamoBlack | disabled | {"0": ["Spraycan_Black"], "1": ["CZ527_Green"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintCz527CamoBlack.c:1 |
| PaintCz527CamoGreen | disabled | {"0": ["Spraycan_Green"], "1": ["CZ527_Black"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintCz527CamoGreen.c:1 |
| PaintDarkMotohelmet | disabled | {"0": ["Spraycan_ColorBase"], "1": ["DarkMotoHelmet_ColorBase"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintDarkMotohelmet.c:1 |
| PaintFirefighterAxe | disabled | {"0": ["Spraycan_ColorBase"], "1": ["FirefighterAxe"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintFirefighterAxe.c:1 |
| PaintGhillieAttBlack | disabled | {"0": ["Spraycan_Black"], "1": ["GhillieAtt_Woodland"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintGhillieAttBlack.c:1 |
| PaintGhillieAttGreen | disabled | {"0": ["Spraycan_Green"], "1": ["GhillieAtt_Tan"]} | ["GhillieAtt_Woodland"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintGhillieAttGreen.c:1 |
| PaintGhillieAttGreenMossy | disabled | {"0": ["Spraycan_Green"], "1": ["GhillieAtt_Mossy"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintGhillieAttGreenMossy.c:1 |
| PaintGhillieBushragBlack | disabled | {"0": ["Spraycan_Black"], "1": ["GhillieBushrag_Woodland"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintGhillieBushragBlack.c:1 |
| PaintGhillieBushragGreen | disabled | {"0": ["Spraycan_Green"], "1": ["GhillieBushrag_Tan"]} | ["GhillieBushrag_Woodland"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintGhillieBushragGreen.c:1 |
| PaintGhillieBushragGreenMossy | disabled | {"0": ["Spraycan_Green"], "1": ["GhillieBushrag_Mossy"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintGhillieBushragGreenMossy.c:1 |
| PaintGhillieHoodBlack | disabled | {"0": ["Spraycan_Black"], "1": ["GhillieHood_Woodland"]} | ["GhillieHood_Mossy"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintGhillieHoodBlack.c:1 |
| PaintGhillieHoodGreen | disabled | {"0": ["Spraycan_Green"], "1": ["GhillieHood_Tan"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintGhillieHoodGreen.c:1 |
| PaintGhillieHoodGreenMossy | disabled | {"0": ["Spraycan_Green"], "1": ["GhillieHood_Mossy"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintGhillieHoodGreenMossy.c:1 |
| PaintGhillieSuitBlack | disabled | {"0": ["Spraycan_Black"], "1": ["GhillieSuit_Woodland"]} | ["GhillieSuit_Mossy"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintGhillieSuitBlack.c:1 |
| PaintGhillieSuitGreen | disabled | {"0": ["Spraycan_Green"], "1": ["GhillieSuit_Tan"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintGhillieSuitGreen.c:1 |
| PaintGhillieSuitGreenMossy | disabled | {"0": ["Spraycan_Green"], "1": ["GhillieSuit_Mossy"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintGhillieSuitGreenMossy.c:1 |
| PaintGhillieTopBlack | disabled | {"0": ["Spraycan_Black"], "1": ["GhillieTop_Woodland"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintGhillieTopBlack.c:1 |
| PaintGhillieTopGreen | disabled | {"0": ["Spraycan_Green"], "1": ["GhillieTop_Tan"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintGhillieTopGreen.c:1 |
| PaintGhillieTopGreenMossy | disabled | {"0": ["Spraycan_Green"], "1": ["GhillieTop_Mossy"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintGhillieTopGreenMossy.c:1 |
| PaintGorkaHelmet | disabled | {"0": ["Spraycan_ColorBase"], "1": ["GorkaHelmet"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintGorkaHelmet.c:1 |
| PaintGorkaHelmetComplete | disabled | {"0": ["Spraycan_ColorBase"], "1": ["GorkaHelmetComplete"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintGorkaHelmetComplete.c:1 |
| PaintM4A1 | disabled | {"0": ["Spraycan_ColorBase"], "1": ["M4A1"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintM4A1.c:1 |
| PaintM4CQBBttstck | disabled | {"0": ["Spraycan_ColorBase"], "1": ["M4_CQBBttstck"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintM4CQBBttstck.c:1 |
| PaintM4MPBttstck | disabled | {"0": ["Spraycan_ColorBase"], "1": ["M4_MPBttstck"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintM4MPBttstck.c:1 |
| PaintM4MPHndgrd | disabled | {"0": ["Spraycan_ColorBase"], "1": ["M4_MPHndgrd"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintM4MPHndgrd.c:1 |
| PaintM4OEBttstck | disabled | {"0": ["Spraycan_ColorBase"], "1": ["M4_OEBttstck"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintM4OEBttstck.c:1 |
| PaintM4PlasticHndgrd | disabled | {"0": ["Spraycan_ColorBase"], "1": ["M4_PlasticHndgrd"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintM4PlasticHndgrd.c:1 |
| PaintM4RISHndgrd | disabled | {"0": ["Spraycan_ColorBase"], "1": ["M4_RISHndgrd"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintM4RISHndgrd.c:1 |
| PaintMosin | disabled | {"0": ["Spraycan_ColorBase"], "1": ["Mosin9130", "Mosin9130_Black", "Mosin9130_Green", "Mosin9130_Camo"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintMosin.c:1 |
| PaintMosinCamoBlack | disabled | {"0": ["Spraycan_Black"], "1": ["Mosin9130_Green"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintMosinCamoBlack.c:1 |
| PaintMosinCamoGreen | disabled | {"0": ["Spraycan_Green"], "1": ["Mosin9130_Black"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintMosinCamoGreen.c:1 |
| PaintMotohelmet | disabled | {"0": ["Spraycan_ColorBase"], "1": ["MotoHelmet_ColorBase"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintMotohelmet.c:1 |
| PaintRuger1022 | disabled | {"0": ["Spraycan_ColorBase"], "1": ["Ruger1022"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintRuger1022.c:1 |
| PaintSKS | disabled | {"0": ["Spraycan_ColorBase"], "1": ["SKS"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintSKS.c:1 |
| PaintSawedoffMosin | disabled | {"0": ["Spraycan_ColorBase"], "1": ["SawedoffMosin9130"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintSawedoffMosin.c:1 |
| PaintSawedoffMosinCamoBlack | disabled | {"0": ["Spraycan_Black"], "1": ["SawedoffMosin9130_Green"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintSawedoffMosinCamoBlack.c:1 |
| PaintSawedoffMosinCamoGreen | disabled | {"0": ["Spraycan_Green"], "1": ["SawedoffMosin9130_Black"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintSawedoffMosinCamoGreen.c:1 |
| PaintZSh3PilotHelmet | disabled | {"0": ["Spraycan_ColorBase"], "1": ["ZSh3PilotHelmet"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PaintZSh3PilotHelmet.c:1 |
| PatchItem | disabled | {"0": ["LeatherSewingKit", "SewingKit", "TireRepairKit"], "1": ["Inventory_Base"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PatchItem.c:1 |
| PeelPotato | registered | {"0": ["PotatoSeed"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "KitchenKnife", "SteakKnife", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "Sword", "Screwdriver", "Hatchet", "HandSaw", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["Potato"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/PeelPotato.c:1 |
| PokeHolesBarrel | registered | {"0": ["Barrel_ColorBase"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "KitchenKnife", "SteakKnife", "HayHook", "Iceaxe", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["BarrelHoles_"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/PokeHolesBarrel.c:1 |
| PourLiquid | unregistered | {"0": ["Pot", "CanisterGasoline", "Canteen", "WaterBottle", "FilteringBottle", "GlassBottle", "WineBottle", "WaterPouch_ColorBase", "Barrel_ColorBase", "AyranBottle", "AyranBottle"], "1": ["Pot", "CanisterGasoline", "Canteen", "WaterBottle", "FilteringBottle", "WineBottle", "GlassBottle", "WaterPouch_ColorBase", "Barrel_ColorBase"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PourLiquid.c:1 |
| PrepareAnimal | unregistered | {"1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "SKS_Bayonet", "BoneKnife", "Screwdriver", "Iceaxe", "Scimitar", "DonerKnife", "Akinaka"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PrepareAnimal.c:1 |
| PrepareCarp | registered | {"0": ["Carp"]} | ["CarpFilletMeat", "CarpFilletMeat"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/PrepareCarp.c:1 |
| PrepareCatfish | registered | {"0": ["Catfish"]} | ["CatfishFilletMeat", "CatfishFilletMeat"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/PrepareCatfish.c:1 |
| PrepareChicken | registered | {"0": ["DeadChicken_ColorBase"]} | ["Bone"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/PrepareChicken.c:1 |
| PrepareFish | unregistered | {} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/PrepareFish.c:1 |
| PrepareFox | registered | {"0": ["DeadFox"]} | ["Bone", "FoxPelt"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/PrepareFox.c:1 |
| PrepareLizard | registered | {"0": ["DeadLizard"]} | ["Bone", "LizardPelt"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/PrepareLizard.c:1 |
| PrepareMackerel | registered | {"0": ["Mackerel"]} | ["MackerelFilletMeat", "MackerelFilletMeat"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/PrepareMackerel.c:1 |
| PrepareRabbit | registered | {"0": ["DeadRabbit"]} | ["Bone", "RabbitPelt"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/PrepareRabbit.c:1 |
| PrepareSteelheadTrout | registered | {"0": ["SteelheadTrout"]} | ["SteelheadTroutFilletMeat", "SteelheadTroutFilletMeat", "RedCaviar"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/PrepareSteelheadTrout.c:1 |
| PrepareWalleyePollock | registered | {"0": ["WalleyePollock"]} | ["WalleyePollockFilletMeat", "WalleyePollockFilletMeat"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/PrepareWalleyePollock.c:1 |
| PurifyWater | registered | {"0": ["PurificationTablets"], "1": ["Pot", "CanisterGasoline", "DisinfectantAlcohol", "Canteen", "WaterBottle", "FilteringBottle", "GlassBottle", "WineBottle", "WaterPouch_ColorBase", "Barrel_ColorBase", "Cauldron", "AyranBottle"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/PurifyWater.c:1 |
| RecipeTest | unregistered | {"0": ["BloodTestKit"], "1": ["BloodSyringe"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/RecipeTest.c:1 |
| RefuelTorch | disabled | {"0": ["Rag"], "1": ["Torch", "LongTorch"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/RefuelTorch.c:3 |
| RepairElectric | registered | {"0": ["ElectronicRepairKit"], "1": ["Inventory_Base"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/RepairElectric.c:1 |
| RepairEpoxy | registered | {"0": ["EpoxyPutty"], "1": ["Inventory_Base", "DefaultWeapon"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/RepairEpoxy.c:1 |
| RepairEyePatch | disabled | {"0": ["EyePatch_Improvised"], "1": ["Rag"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/RepairEyePatch.c:1 |
| RepairPlanks | registered | {"0": ["WoodenPlank"], "1": ["WoodenCrate", "SeaChest"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/RepairPlanks.c:1 |
| RepairWithLeatherSewingKit | registered | {"0": ["LeatherSewingKit"], "1": ["Inventory_Base"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/RepairWithLeatherSewingKit.c:1 |
| RepairWithPliers | registered | {"0": ["Pliers"], "1": ["Chainmail", "Chainmail_Coif", "Chainmail_Leggings", "WitchHoodCoif_ColorBase"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/RepairWithPliers.c:1 |
| RepairWithRags | disabled | {"0": ["HeadCover_Improvised", "HandsCover_Improvised", "LegsCover_Improvised", "FeetCover_Improvised", "FaceCover_Improvised", "TorsoCover_Improvised"], "1": ["Rag"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/RepairWithRags.c:1 |
| RepairWithSewingKit | registered | {"0": ["SewingKit"], "1": ["Inventory_Base"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/RepairWithSewingKit.c:1 |
| RepairWithTape | registered | {"0": ["DuctTape"], "1": ["Inventory_Base", "DefaultWeapon", "DefaultMagazine"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/RepairWithTape.c:1 |
| RepairWithTireKit | registered | {"0": ["TireRepairKit"], "1": ["Inventory_Base"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/RepairWithTireKit.c:1 |
| SawOFFB95 | registered | {"0": ["B95"], "1": ["Hacksaw"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/SawoffB95.c:1 |
| SawOffIzh18 | registered | {"0": ["Izh18"], "1": ["Hacksaw"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/SawOffIzh18.c:1 |
| SawOffIzh18Shotgun | registered | {"0": ["Izh18Shotgun"], "1": ["Hacksaw"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/SawOffIzh18Shotgun.c:1 |
| SawOffMagnum | registered | {"0": ["Magnum", "Magnum_Gold"], "1": ["Hacksaw"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/SawoffMagnum.c:1 |
| SawWoodenLog | registered | {"0": ["Hacksaw", "HandSaw", "WoodAxe", "Hatchet", "FirefighterAxe"], "1": ["WoodenLog"]} | ["Firewood", "Firewood", "Firewood"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/SawWoodenLog.c:1 |
| SawoffFAMAS | registered | {"0": ["FAMAS"], "1": ["Hacksaw"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/SawoffFAMAS.c:1 |
| SawoffMosin | registered | {"0": ["Mosin9130"], "1": ["Hacksaw"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/SawoffMosin.c:1 |
| SawoffMosinPainted | disabled | {"0": ["Mosin9130_Black", "Mosin9130_Green", "Mosin9130_Camo"], "1": ["Hacksaw"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/SawoffMosinPainted.c:1 |
| SawoffShotgunIzh43 | registered | {"0": ["Izh43Shotgun"], "1": ["Hacksaw"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/SawoffShotgunIzh43.c:1 |
| SharpenBroom | registered | {"0": ["Broom"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["WoodenStick", "SharpWoodenStick"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/SharpenBroom.c:1 |
| SharpenLongStick | registered | {"0": ["LongWoodenStick"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["SharpWoodenStick"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/SharpenLongStick.c:1 |
| SharpenMelee | registered | {"0": ["Whetstone"], "1": ["Inventory_Base"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/SharpenMelee.c:1 |
| SharpenStick | unregistered | {"0": ["WoodenStick"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Screwdriver", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["Ammo_SharpStick"] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/SharpenStick.c:1 |
| SplitBroom | registered | {"0": ["Broom", "Broom_Birch"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["WoodenStick", "LongWoodenStick"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/SplitBroom.c:1 |
| SplitFirewood | registered | {"0": ["Firewood"], "1": ["Hacksaw", "HandSaw", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe"]} | ["WoodenStick"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/SplitFirewood.c:1 |
| SplitLongWoodenStick | registered | {"0": ["LongWoodenStick", "SharpWoodenStick"], "1": ["Sickle", "KukriKnife", "FangeKnife", "Hacksaw", "HandSaw", "KitchenKnife", "SteakKnife", "HayHook", "StoneKnife", "Cleaver", "CombatKnife", "Jambiya;", "HuntingKnife", "Machete", "CrudeMachete", "OrientalMachete", "Crowbar", "Pickaxe", "WoodAxe", "Hatchet", "FirefighterAxe", "Sword", "AK_Bayonet", "M9A1_Bayonet", "Mosin_Bayonet", "SKS_Bayonet", "BoneKnife", "Scimitar", "DonerKnife", "BrickTrowel", "Akinaka"]} | ["WoodenStick"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/SplitLongWoodenStick.c:1 |
| SplitStones | registered | {"0": ["Stone"], "1": ["Pickaxe", "SledgeHammer", "Hammer", "Mace"]} | ["SmallStone", "SmallStone", "SmallStone"] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/SplitStones.c:1 |
| UpgradeTorchWithLard | registered | {"0": ["Lard"], "1": ["Torch", "LongTorch"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/UpgradeTorchWithLard.c:1 |
| UpgradeTorchWithLiquidFuel | registered | {"0": ["Bottle_Base", "Barrel_ColorBase"], "1": ["Torch", "LongTorch"]} | [] | REUSE-CANDIDATE; runtime pending | 4_World/Classes/Recipes/Recipes/UpgradeTorchWithLiquidFuel.c:1 |
| WriteLetter | unregistered | {"0": ["Pen_ColorBase"], "1": ["Paper"]} | [] | HOLD; explicit semantic/registration review | 4_World/Classes/Recipes/Recipes/WriteLetter.c:1 |

### Exhaustive declared action-path classification

No-item-add-call-observed is a source-adapter statement, not proof an action is unreachable.
Constructor candidates, inherited behavior, player/global overloads and unresolved bindings remain in the input artifact.

| Action class | Observed path kind | Item-source status | Ancestry / runtime | Declaration |
| --- | --- | --- | --- | --- |
| ActionActionBuildPartNoTool | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionBuildPart.c:543 |
| ActionActivateTrap | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionActivateTrap.c:16 |
| ActionAnimateCarSelection | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/Vehicles/ActionAnimateCarSelection.c:1 |
| ActionAnimateMotorbikeSeat | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/Vehicles/ActionAnimateMotorbikeSeat.c:1 |
| ActionAnimateSeats | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/Vehicles/ActionAnimateSeats.c:1 |
| ActionArmExplosive | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionArmExplosive.c:16 |
| ActionAttach | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionAttach.c:7 |
| ActionAttachExplosivesTrigger | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionAttachExplosivesTrigger.c:9 |
| ActionAttachOnProxy | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionAttachOnProxy.c:1 |
| ActionAttachOnSelection | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionAttachOnSelection.c:1 |
| ActionAttachOnTentProxy | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionAttachOnTentProxy.c:1 |
| ActionAttachOnTrap | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionAttachOnTrap.c:1 |
| ActionAttachPowerSourceToPanel | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionAttachPowerSourceToPanel.c:2 |
| ActionAttachSeeds | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionAttachSeeds.c:1 |
| ActionAttachToConstruction | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionAttachToConstruction.c:6 |
| ActionAttachWheels | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionAttachWheels.c:2 |
| ActionAttachWithSwitch | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionAttachWithSwich.c:1 |
| ActionBandageBase | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionBandageBase.c:1 |
| ActionBandageSelf | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionBandageSelf.c:15 |
| ActionBandageTarget | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionBandageTarget.c:15 |
| ActionBase | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/ActionBase.c:51 |
| ActionBiteCharcoalTablets | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionBiteCharcoalTablets.c:1 |
| ActionBitePainkillerTablets | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionBitePainkillerTablets.c:1 |
| ActionBitePurificationTablets | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionBitePurificationTablets.c:1 |
| ActionBiteTetracyclineAntibiotics | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionBiteTetracyclineAntibiotics.c:1 |
| ActionBiteVitaminBottle | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionBiteVitaminBottle.c:1 |
| ActionBreakLongWoodenStick | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionBreakLongWoodenStick.c:12 |
| ActionBuildOven | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionBuildOven.c:9 |
| ActionBuildPart | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionBuildPart.c:33 |
| ActionBuildPartHandsGeneric | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionBuildPart.c:377 |
| ActionBuildPartInstantDebug | other ActionBase path | no-item-add-call-observed | conditional_definition | 4_World/Classes/UserActionsComponent/Actions/Instant/ActionBuildPartInstant.c:3 |
| ActionBuildPartSwitch | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionBuildPartSwitch.c:2 |
| ActionBuildShelter | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionBuildShelter.c:2 |
| ActionBuildStoneCircle | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionBuildStoneCircle.c:9 |
| ActionBurnSewSelf | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionBurnSewSelf.c:10 |
| ActionBurnSewTarget | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionBurnSewTarget.c:10 |
| ActionBuryAshes | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionBuryAshes.c:9 |
| ActionBuryBody | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionBuryBody.c:9 |
| ActionCPR | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionCPR.c:11 |
| ActionCarDoors | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/Vehicles/ActionCarDoors.c:1 |
| ActionCarDoorsOutside | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/Vehicles/ActionCarDoorsOutside.c:1 |
| ActionCarHornLong | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Vehicles/ActionCarHorn.c:214 |
| ActionCarHornShort | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Vehicles/ActionCarHorn.c:70 |
| ActionCheckPulse | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionCheckPulse.c:2 |
| ActionCheckPulseTarget | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionCheckPulseTarget.c:9 |
| ActionClapBearTrapWithThisItem | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionClapBearTrapWithThisItem.c:1 |
| ActionClose | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionClose.c:1 |
| ActionCloseBarrel | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionCloseBarrel.c:1 |
| ActionCloseBarrelHoles | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionCloseBarrelHoles.c:1 |
| ActionCloseCarDoors | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/Vehicles/ActionCloseCarDoors.c:1 |
| ActionCloseCarDoorsOutside | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/Vehicles/ActionCloseCarDoorsOutside.c:1 |
| ActionCloseDoors | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionCloseDoors.c:1 |
| ActionCloseFence | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionCloseFence.c:1 |
| ActionCollectBloodSelf | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionCollectBloodSelf.c:9 |
| ActionCollectBloodTarget | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionCollectBloodTarget.c:9 |
| ActionCollectSampleSelf | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionCollectSampleSelf.c:9 |
| ActionCollectSampleTarget | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionCollectSampleTarget.c:9 |
| ActionCombinationLockUnlock | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionCombinationLockUnlock.c:1 |
| ActionConstructionPartInfoContinuous | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionPartInfo.c:1 |
| ActionConstructionPartInfoInteract | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionPartInfo.c:204 |
| ActionConsume | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionConsume.c:9 |
| ActionConsumeSingle | other ActionBase path | comment-disabled-only | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionConsumeSingle.c:1 |
| ActionContinuousBase | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/ActionContinuousBase.c:120 |
| ActionCookOnStick | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCookOnStick.c:11 |
| ActionCoverHeadSelf | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCoverHeadSelf.c:9 |
| ActionCoverHeadTarget | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCoverHeadTarget.c:9 |
| ActionCraft | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCraft.c:9 |
| ActionCraftArmband | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCraftArmband.c:9 |
| ActionCraftBolts | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCraftBolts.c:11 |
| ActionCraftBoltsFeather | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCraftBoltsFeather.c:11 |
| ActionCraftBoneKnife | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCraftBoneKnife.c:9 |
| ActionCraftBoneKnifeEnv | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCraftBoneKnifeEnv.c:11 |
| ActionCraftImprovisedEyePatch | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCraftImprovisedEyePatch.c:9 |
| ActionCraftImprovisedFaceCover | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCraftImprovisedFaceCover.c:11 |
| ActionCraftImprovisedFeetCover | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCraftImprovisedFeetCover.c:11 |
| ActionCraftImprovisedHandsCover | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCraftImprovisedHandsCover.c:11 |
| ActionCraftImprovisedHeadCover | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCraftImprovisedHeadCover.c:12 |
| ActionCraftImprovisedLegsCover | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCraftImprovisedLegsCover.c:11 |
| ActionCraftImprovisedTorsoCover | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCraftImprovisedTorsoCover.c:11 |
| ActionCraftRopeBelt | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCraftRopeBelt.c:9 |
| ActionCraftStoneKnifeEnv | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCraftStoneKnifeEnv.c:11 |
| ActionCreateGreenhouseGardenPlot | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCreateGreenhouseGardenPlot.c:9 |
| ActionCreateIndoorFireplace | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionCreateIndoorFireplace.c:1 |
| ActionCreateIndoorOven | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionCreateIndoorOven.c:1 |
| ActionDeCraftDrysackBag | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDeCraftDrysackBag.c:9 |
| ActionDeCraftRopeBelt | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDeCraftRopeBelt.c:12 |
| ActionDeCraftWitchHoodCoif | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDeCraftWitchHoodCoif.c:9 |
| ActionDebug | other ActionBase path | no-item-add-call-observed | conditional_definition | 4_World/Classes/UserActionsComponent/Actions/Instant/ActionDebug.c:15 |
| ActionDeconstructShelter | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionPackShelter.c:1 |
| ActionDefibrilateBase | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionDefibrilateBase.c:1 |
| ActionDefibrilateSelf | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionDefibrilateSelf.c:9 |
| ActionDefibrilateTarget | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionDefibrilateTarget.c:9 |
| ActionDeployBase | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/DeployActions/ActionDeployBase.c:19 |
| ActionDeployHuntingTrap | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/DeployActions/ActionDeployHuntingTrap.c:1 |
| ActionDeployObject | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/DeployActions/ActionDeployObject.c:7 |
| ActionDestroyCombinationLock | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDestroyCombinationLock.c:10 |
| ActionDestroyPart | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDestroyPart.c:9 |
| ActionDestroyPartInstantDebug | other ActionBase path | no-item-add-call-observed | conditional_definition | 4_World/Classes/UserActionsComponent/Actions/Instant/ActionDestroyPartInstant.c:3 |
| ActionDetach | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionDetach.c:6 |
| ActionDetachBattery | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionDetachBattery.c:1 |
| ActionDetachFromTarget | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionDetachFromTarget.c:1 |
| ActionDetachFromTarget_SpecificSlot | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionDetachFromTarget.c:134 |
| ActionDetachFromTarget_SpecificSlot_MetalSheets | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionDetachFromTarget.c:221 |
| ActionDetachFromTarget_SpecificSlot_WoodenLogs | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionDetachFromTarget.c:205 |
| ActionDetachFromTarget_SpecificSlot_WoodenPlanks | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionDetachFromTarget.c:213 |
| ActionDetachFromTarget_SpecificSlotsCategory | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionDetachFromTarget.c:169 |
| ActionDetachFromTarget_SpecificSlotsCategory_Barrel | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionDetachFromTarget.c:229 |
| ActionDetachFromTarget_SpecificSlotsCategory_WoodenCrate | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionDetachFromTarget.c:237 |
| ActionDetachPowerSourceFromPanel | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionDetachPowerSourceFromPanel.c:2 |
| ActionDialCombinationLock | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDialCombinationLock.c:11 |
| ActionDialCombinationLockOnTarget | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDialCombinationLockOnTarget.c:11 |
| ActionDigGardenPlot | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDigGardenPlot.c:9 |
| ActionDigInStash | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDigInStash.c:9 |
| ActionDigOutStash | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDigOutStash.c:9 |
| ActionDigWorms | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDigWorms.c:17 |
| ActionDisarmExplosive | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDisarmExplosive.c:9 |
| ActionDisarmExplosiveWithRemoteDetonator | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDisarmExplosiveWithRemoteDetonator.c:9 |
| ActionDisarmExplosiveWithRemoteDetonatorUnpaired | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDisarmExplosiveWithRemoteDetonatorUnpaired.c:9 |
| ActionDisarmMine | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDisarmMine.c:9 |
| ActionDisinfectBase | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionDisinfectSelf.c:9 |
| ActionDisinfectPlant | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDisinfectPlant.c:9 |
| ActionDisinfectPlantBit | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionDisinfectPlantBit.c:12 |
| ActionDisinfectSelf | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionDisinfectSelf.c:20 |
| ActionDisinfectTarget | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionDisinfectTarget.c:10 |
| ActionDismantleGardenPlot | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDismantleGardenPlot.c:9 |
| ActionDismantleOven | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDismantleOven.c:9 |
| ActionDismantlePart | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDismantlePart.c:23 |
| ActionDismantlePartInstantDebug | other ActionBase path | no-item-add-call-observed | conditional_definition | 4_World/Classes/UserActionsComponent/Actions/Instant/ActionDismantlePartInstant.c:3 |
| ActionDismantleStoneCircle | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDismantleStoneCircle.c:9 |
| ActionDrainLiquid | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDrainLiquid.c:11 |
| ActionDrink | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDrink.c:9 |
| ActionDrinkAlcohol | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionDrinkAlcohol.c:2 |
| ActionDrinkCan | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDrinkCan.c:1 |
| ActionDrinkCookingPot | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDrinkCookingPot.c:1 |
| ActionDrinkDisinfectant | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionDrinkDisinfectant.c:2 |
| ActionDrinkDisinfectant2 | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionDrinkDisinfectant2.c:2 |
| ActionDrinkPondContinuous | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDrinkPondContinuous.c:9 |
| ActionDrinkThroughContinuous | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDrinkThroughContinuous.c:1 |
| ActionDrinkWellContinuous | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDrinkWellContinuous.c:9 |
| ActionDrinkWellContinuousBucket | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDrinkWellContinuousBucket.c:2 |
| ActionDropItem | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionDropItem.c:30 |
| ActionDropItemSimple | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionDropItemSimple.c:1 |
| ActionDummyContinuousRelease | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDummyRelease.c:2 |
| ActionEat | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionEat.c:45 |
| ActionEatBig | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionEat.c:9 |
| ActionEatCan | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionEatCan.c:10 |
| ActionEatCereal | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionEatCereal.c:1 |
| ActionEatCharcoalTablets | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionEatCharcoalTablets.c:1 |
| ActionEatFruit | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionEatFruit.c:9 |
| ActionEatMeat | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionEatMeat.c:9 |
| ActionEatPainkillerTablets | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionEatPainkillerTablets.c:1 |
| ActionEatPillFromBottle | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionEatPillFromBottle.c:1 |
| ActionEatPurificationTablets | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionEatPurificationTablets.c:1 |
| ActionEatSmall | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionEat.c:64 |
| ActionEatSmallCan | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionEatCan.c:42 |
| ActionEatSnowContinuous | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionEatSnowContinuous.c:9 |
| ActionEatTabletFromWrapper | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionEatTabletFromWrapper.c:1 |
| ActionEatTetracyclineAntibiotics | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionEatTetracyclineAntibiotics.c:1 |
| ActionEatVitaminBottle | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionEatVitaminBottle.c:1 |
| ActionEmptyBottleBase | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionEmptyBottleBase.c:23 |
| ActionEmptyCookingPot | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionEmptyCookingPot.c:1 |
| ActionEmptyMagazine | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionEmptyMagazine.c:14 |
| ActionEmptySeedsPack | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionEmptySeedsPack.c:6 |
| ActionEnterLadder | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionEnterLadder.c:2 |
| ActionExitLadder | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionExitLadder.c:1 |
| ActionExtinguishFireplaceByExtinguisher | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionExtinguishFireplaceByExtinguisher.c:13 |
| ActionExtinguishFireplaceByLiquid | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionExtinguishFireplaceByLiquid.c:13 |
| ActionExtinquishTorchVideo | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionExtinquishTorchVideo.c:1 |
| ActionFeedCharcoalTablets | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionFeedCharcoalTablets.c:1 |
| ActionFeedPainkillerTablets | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionFeedPainkillerTablets.c:1 |
| ActionFeedPurificationTablets | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionFeedPurificationTablets.c:1 |
| ActionFeedTetracyclineAntibiotics | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionFeedTetracyclineAntibiotics.c:1 |
| ActionFeedVitaminBottle | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionFeedVitaminBottle.c:11 |
| ActionFertilizeSlot | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionFertilizeSlot.c:11 |
| ActionFillBottleBase | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionFillBottleBase.c:29 |
| ActionFillBottleSnow | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionFillBottleSnow.c:1 |
| ActionFillBrakes | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Vehicles/ActionFillBrakes.c:11 |
| ActionFillCoolant | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Vehicles/ActionFillCoolant.c:11 |
| ActionFillFuel | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Vehicles/ActionFillFuel.c:11 |
| ActionFillGeneratorTank | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionFillGeneratorTank.c:11 |
| ActionFillObject | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionFillObject.c:9 |
| ActionFillOil | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Vehicles/ActionFillOil.c:11 |
| ActionFishingNew | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionFishingNew.c:157 |
| ActionFoldBandanaToHead | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionFoldBandanaToHead.c:1 |
| ActionFoldBandanaToMask | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionFoldBandanaToMask.c:1 |
| ActionFoldBaseBuildingObject | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionFoldBaseBuildingObject.c:9 |
| ActionFoldEntityToSlot | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionFoldEntityToSlot.c:1 |
| ActionFoldMap | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionFoldMap.c:3 |
| ActionFoldObject | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionFoldObject.c:1 |
| ActionForceABite | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionForceABite.c:9 |
| ActionForceABiteCan | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionForceABiteCan.c:2 |
| ActionForceASip | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionForceASip.c:1 |
| ActionForceBiteCharcoalTablets | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionForceBiteCharcoalTablets.c:1 |
| ActionForceBitePainkillerTablets | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionForceBitePainkillerTablets.c:1 |
| ActionForceBitePurificationTablets | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionForceBitePurificationTablets.c:1 |
| ActionForceBiteTetracyclineAntibiotics | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionForceBiteTetracyclineAntibiotics.c:1 |
| ActionForceBiteVitaminBottle | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionForceBiteVitaminBottle.c:1 |
| ActionForceConsume | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionForceConsume.c:9 |
| ActionForceConsumeSingle | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionForceConsumeSingle.c:9 |
| ActionForceDrink | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionForceDrink.c:9 |
| ActionForceDrinkAlcohol | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionForceDrinkAlcohol.c:2 |
| ActionForceDrinkDisinfectant | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionForceDrinkDisinfectant.c:2 |
| ActionForceFeed | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionForceFeed.c:9 |
| ActionForceFeedCan | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionForceFeedCan.c:1 |
| ActionForceFeedMeat | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionForceFeedMeat.c:10 |
| ActionForceFeedSmall | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionForceFeed.c:38 |
| ActionGagSelf | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionGagSelf.c:1 |
| ActionGagTarget | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionGagTarget.c:1 |
| ActionGetInTransport | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionGetInTransport.c:1 |
| ActionGetOutTransport | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionGetOutTransport.c:23 |
| ActionGiveBloodSelf | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionGiveBloodSelf.c:16 |
| ActionGiveBloodTarget | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionGiveBloodTarget.c:9 |
| ActionGiveSalineSelf | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionGiveSalineSelf.c:9 |
| ActionGiveSalineTarget | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionGiveSalineTarget.c:9 |
| ActionHandcuffTarget | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionHandcuffTarget.c:2 |
| ActionHandsPartSwitch | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionHandsPartSwitch.c:2 |
| ActionHarvestCrops | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionHarvestCrops.c:9 |
| ActionITest | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionITest.c:1 |
| ActionIgniteFireplaceByAir | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionIgniteFireplaceByAir.c:9 |
| ActionInjectEpinephrineSelf | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionInjectEpinephrineSelf.c:1 |
| ActionInjectEpinephrineTarget | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionInjectEpinephrineTarget.c:1 |
| ActionInjectMorphineSelf | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionInjectMorphineSelf.c:1 |
| ActionInjectMorphineTarget | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionInjectMorphineTarget.c:1 |
| ActionInjectSelf | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionInjectSelf.c:1 |
| ActionInjectTarget | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Medical/ActionInjectTarget.c:1 |
| ActionInsertSparkplug | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionInstallSparkplug.c:7 |
| ActionInstantBase | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/ActionInstantBase.c:1 |
| ActionInteractBase | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/ActionInteractBase.c:38 |
| ActionInteractCodeLockBase | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionInteractCodeLockBase.c:1 |
| ActionInteractCodeLockItem | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionInteractCodeLockItem.c:13 |
| ActionInteractLoopBase | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/ActionInteractLoopBase.c:32 |
| ActionLightItemOnFire | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionLightItemOnFire.c:9 |
| ActionLightItemOnFireWithBlowtorch | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionLightItemOnFireWithBlowtorch.c:9 |
| ActionLightTorchVideo | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionLightTorchVideo.c:1 |
| ActionLoadMagazine | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionLoadMagazine.c:9 |
| ActionLoadMagazineQuick | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionLoadMagazine.c:86 |
| ActionLockAttachment | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionLockAttachment.c:20 |
| ActionLockDoors | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionLockDoors.c:9 |
| ActionLockedDoors | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionOpenDoors.c:101 |
| ActionLowerFlag | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionLowerFlag.c:2 |
| ActionMeasureBattery | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionMeasureBattery.c:1 |
| ActionMeasureTemperatureSelf | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionMeasureTemperatureSelf.c:9 |
| ActionMeasureTemperatureTarget | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionMeasureTemperatureTarget.c:9 |
| ActionMineBase | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionMineTree.c:17 |
| ActionMineBush | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionMineBush.c:11 |
| ActionMineBushByHand | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionMineBushByHand.c:1 |
| ActionMineRock | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionMineRock.c:11 |
| ActionMineRock1H | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionMineRock.c:60 |
| ActionMineTree | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionMineTree.c:66 |
| ActionMineTreeBark | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionMineTreeBark.c:1 |
| ActionMixMortarAtWater | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionMixMortarAtWater.c:23 |
| ActionMixMortarAtWell | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionMixMortarAtWell.c:2 |
| ActionMountBarbedWire | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionMountBarbedWire.c:19 |
| ActionNextCombinationLockDial | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionNextCombinationLockDial.c:1 |
| ActionNextCombinationLockDialOnTarget | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionNextCombinationLockDialOnTarget.c:1 |
| ActionObtainLiquidBase | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionObtainLiquidBase.c:36 |
| ActionOpen | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionOpen.c:1 |
| ActionOpenBarrel | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionOpenBarrel.c:1 |
| ActionOpenBarrelHoles | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionOpenBarrelHoles.c:1 |
| ActionOpenCarDoors | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/Vehicles/ActionOpenCarDoors.c:1 |
| ActionOpenCarDoorsOutside | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/Vehicles/ActionOpenCarDoorsOutside.c:1 |
| ActionOpenDoors | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionOpenDoors.c:1 |
| ActionOpenFence | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionOpenFence.c:1 |
| ActionOperatePanel | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionOperatePanel.c:1 |
| ActionOperatePanelPowerStation | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionOperatePanelPowerStation.c:1 |
| ActionPackGift | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionPackGift.c:9 |
| ActionPackTent | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionPackTent.c:9 |
| ActionPickBerry | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionPickBerry.c:10 |
| ActionPickUpBricks | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionPickUpBricks.c:16 |
| ActionPickUpMotorbike | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/Vehicles/ActionPickUpMotorBike.c:1 |
| ActionPickupChicken | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionPickupChicken.c:2 |
| ActionPin | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionPin.c:1 |
| ActionPlaceFireplaceIndoor | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionPlaceFireplaceIndoor.c:1 |
| ActionPlaceFireplaceIntoBarrel | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionPlaceFireplaceIntoBarrel.c:1 |
| ActionPlaceObject | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionPlaceObject.c:9 |
| ActionPlaceOnGround | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionPlaceOnGround.c:10 |
| ActionPlaceOvenIndoor | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionPlaceOvenIndoor.c:1 |
| ActionPlantSeed | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionPlantSeed.c:1 |
| ActionPlugIn | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionPlugIn.c:1 |
| ActionPlugIntoFence | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionPlugIntoFence.c:2 |
| ActionPlugTargetIntoThis | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionPlugTargetIntoThis.c:1 |
| ActionPourLiquid | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionPourLiquid.c:11 |
| ActionPullBodyFromTransport | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionPullBodyFromTransport.c:1 |
| ActionPullOutPlug | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionPullOutPlug.c:1 |
| ActionPushBoat | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionPushBoat.c:17 |
| ActionPushCar | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionPushCar.c:56 |
| ActionPushObject | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionPushObject.c:113 |
| ActionRaiseFlag | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRaiseFlag.c:9 |
| ActionRaiseMegaphone | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRaiseMegaphone.c:11 |
| ActionReadPaper | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionReadPaper.c:30 |
| ActionRefuelTorch | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRefuelTorch.c:1 |
| ActionRemovePlant | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionRemovePlant.c:1 |
| ActionRemoveSeed | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionRemoveSeed.c:1 |
| ActionRepackTent | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionRepackTent.c:43 |
| ActionRepairBoatChassis | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairBoatChassis.c:1 |
| ActionRepairBoatEngine | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairBoatEngine.c:9 |
| ActionRepairCarChassis | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairCarChassis.c:4 |
| ActionRepairCarChassisWithBlowtorch | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairCarChassisWithBlowtorch.c:9 |
| ActionRepairCarEngine | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairCarEngine.c:4 |
| ActionRepairCarEngineWithBlowtorch | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairCarEngineWithBlowtorch.c:9 |
| ActionRepairCarPart | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairCarPart.c:15 |
| ActionRepairCarPartWithBlowtorch | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairCarPartWithBlowTorch.c:9 |
| ActionRepairItemWithBlowtorch | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairItemWithBlowtorch.c:9 |
| ActionRepairMotorbikeChassis | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairMotorbikeChassis.c:1 |
| ActionRepairMotorbikeChassisWithBlowtorch | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairMotorbikeChassisWithBlowtorch.c:9 |
| ActionRepairMotorbikeEngine | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairMotorbikeEngine.c:1 |
| ActionRepairMotorbikeEngineWithBlowtorch | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairMotorbikeEngineWithBlowtorch.c:9 |
| ActionRepairMotorbikePart | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairMotorbikePart.c:12 |
| ActionRepairMotorbikePartWithBlowTorch | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairMotorbikePartWithBlowTorch.c:9 |
| ActionRepairPart | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairPart.c:39 |
| ActionRepairShelter | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairShelter.c:2 |
| ActionRepairTent | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairTent.c:19 |
| ActionRepairTentPart | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairTentPart.c:19 |
| ActionRepairVehiclePartBase | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairVehiclePartBase.c:19 |
| ActionRepairWithToolFromHands | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionRepairWithToolFromHands.c:2 |
| ActionRepositionPluggedItem | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionRepositionPluggedItem.c:1 |
| ActionResetCodeOnCodeLock | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionResetCodeOnCodeLock..c:1 |
| ActionResetKitchenTimer | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionResetKitchenTimer.c:9 |
| ActionRestrainSelf | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRestrainSelf.c:23 |
| ActionRestrainTarget | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRestrainTarget.c:23 |
| ActionSawPlanks | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionSawPlanks.c:40 |
| ActionSequentialBase | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/ActionSequentialBase.c:10 |
| ActionSetAlarmClock | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionSetAlarmClock.c:13 |
| ActionSetKitchenTimer | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionSetKitchenTimer.c:13 |
| ActionSewSelf | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionSewSelf.c:9 |
| ActionSewTarget | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionSewTarget.c:9 |
| ActionShave | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionShave.c:9 |
| ActionShaveTarget | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionShaveTarget.c:9 |
| ActionSidePlateInteract | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/Vehicles/ActionSidePlateInteract.c:1 |
| ActionSingleUseBase | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/ActionSingleUseBase.c:29 |
| ActionSkinning | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionSkinning.c:29 |
| ActionSortAmmoPile | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionSortAmmoPile.c:10 |
| ActionSplintSelf | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionSplintSelf.c:9 |
| ActionSplintTarget | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionSplintTarget.c:9 |
| ActionStartEngine | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Vehicles/ActionStartEngine.c:9 |
| ActionStartEngineBoat | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Vehicles/ActionStartEngineBoat.c:9 |
| ActionStartEngineMotorbike | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Vehicles/ActionStartEngineMotorBike.c:9 |
| ActionStopEngine | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Vehicles/ActionStopEngine.c:1 |
| ActionStopEngineBoat | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Vehicles/ActionStopEngineBoat.c:1 |
| ActionStopEngineMotorbike | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Vehicles/ActionStopEngineMotorBike.c:1 |
| ActionStripCarrierVest | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionStripCarrierVest.c:10 |
| ActionSwapItemToHands | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTakeItemToHands.c:124 |
| ActionSwitchLights | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/Vehicles/ActionSwitchLights.c:1 |
| ActionSwitchSeats | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/Vehicles/ActionSwitchSeats.c:2 |
| ActionTakeABite | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTakeABite.c:11 |
| ActionTakeABiteCan | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTakeABiteCan.c:2 |
| ActionTakeASip | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTakeASip.c:1 |
| ActionTakeArrow | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTakeArrow.c:1 |
| ActionTakeArrowToHands | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTakeArrowToHands.c:1 |
| ActionTakeFireplaceFromBarrel | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTakeFireplaceFromBarrel.c:2 |
| ActionTakeFireplaceIndoor | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTakeFireplaceIndoor.c:2 |
| ActionTakeHybridAttachment | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTakeHybridAttachment.c:2 |
| ActionTakeHybridAttachmentToHands | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTakeHybridAttachmentToHands.c:2 |
| ActionTakeItem | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTakeItem.c:6 |
| ActionTakeItemToHands | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTakeItemToHands.c:1 |
| ActionTakeMaterialToHands | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTakeMaterialToHands.c:2 |
| ActionTakeMaterialToHandsSwitch | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTakeMaterialToHandsSwitch.c:2 |
| ActionTakeOvenIndoor | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTakeOvenIndoor.c:2 |
| ActionTestBloodSelf | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionTestBloodSelf.c:9 |
| ActionTestBloodTarget | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Medical/ActionTestBloodTarget.c:9 |
| ActionToggleNVG | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionToggleNVG.c:1 |
| ActionToggleNVMode | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionToggleNVMode.c:2 |
| ActionTogglePlaceObject | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTogglePlaceObject.c:1 |
| ActionTogglePlaceObjectDigging | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTogglePlaceObjectDigging.c:2 |
| ActionToggleTentOpen | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionToggleTentOpen.c:1 |
| ActionTransferLiquid | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionTransferLiquid.c:25 |
| ActionTriggerRemotely | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTriggerRemotely.c:1 |
| ActionTuneFrequency | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionTuneFrequency.c:11 |
| ActionTuneFrequencyOnGround | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTuneFrequencyOnGround.c:1 |
| ActionTuneRadioStation | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionTuneRadioStation.c:11 |
| ActionTurnOffAlarmClock | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOffAlarmClock.c:9 |
| ActionTurnOffHeadtorch | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOffHeadtorch.c:1 |
| ActionTurnOffHelmetFlashlight | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOffHelmetFlashlight.c:1 |
| ActionTurnOffPowerGenerator | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTurnOffPowerGenerator.c:1 |
| ActionTurnOffSpotlight | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTurnOffSpotlight.c:1 |
| ActionTurnOffTransmitter | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOffTransmitter.c:9 |
| ActionTurnOffTransmitterOnGround | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTurnOffTransmitterOnGround.c:1 |
| ActionTurnOffWeaponFlashlight | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOffWeaponFlashlight.c:1 |
| ActionTurnOffWhileInHands | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOffWhileInHands.c:1 |
| ActionTurnOffWhileOnGround | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTurnOffWhileOnGround.c:1 |
| ActionTurnOnAlarmClock | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOnAlarmClock.c:9 |
| ActionTurnOnChemlight | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOnChemlight.c:2 |
| ActionTurnOnHeadtorch | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOnHeadtorch.c:1 |
| ActionTurnOnHeatpack | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOnHeatpack.c:1 |
| ActionTurnOnHelmetFlashlight | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOnHelmetFlashlight.c:1 |
| ActionTurnOnPowerGenerator | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTurnOnPowerGenerator.c:1 |
| ActionTurnOnSpotlight | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTurnOnSpotlight.c:1 |
| ActionTurnOnTransmitter | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOnTransmitter.c:9 |
| ActionTurnOnTransmitterOnGround | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTurnOnTransmitterOnGround.c:1 |
| ActionTurnOnWeaponFlashlight | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOnWeaponFlashlight.c:1 |
| ActionTurnOnWhileInHands | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOnWhileInHands.c:1 |
| ActionTurnOnWhileOnGround | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionTurnOnWhileOnGround.c:1 |
| ActionTurnValve | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionTurnValve.c:9 |
| ActionTurnValveUndergroundReservoir | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionTurnValveUndergroundReservoir.c:9 |
| ActionUncoverHeadBase | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionUncoverHeadSelf.c:10 |
| ActionUncoverHeadSelf | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionUncoverHeadSelf.c:44 |
| ActionUncoverHeadTarget | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionUncoverHeadTarget.c:9 |
| ActionUnfoldBandana | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionUnfoldBandana.c:1 |
| ActionUnfoldEntity | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionUnfoldEntity.c:2 |
| ActionUnfoldMap | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionUnfoldMap.c:168 |
| ActionUngagSelf | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionUngagSelf.c:1 |
| ActionUngagTarget | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionUngagTarget.c:1 |
| ActionUnlockDoors | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionUnlockDoors.c:9 |
| ActionUnlockShippingContainer | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionUnlockContainerDoor.c:1 |
| ActionUnmountBarbedWire | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionUnMountBarbedWire.c:9 |
| ActionUnpackBox | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionUnpackBox.c:9 |
| ActionUnpackGift | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionUnpackGift.c:9 |
| ActionUnpin | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionUnpin.c:1 |
| ActionUnplugThisByCord | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionUnplugThisByCord.c:1 |
| ActionUnrestrainSelf | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionUnrestrainSelf.c:48 |
| ActionUnrestrainTarget | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionUnrestrainTarget.c:55 |
| ActionUnrestrainTargetHands | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionUnrestrainTargetEmpty.c:27 |
| ActionUpgradeTorchFromGasPump | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionUpgradeTorchFromGasPump.c:9 |
| ActionUseRangefinder | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionUseRangefinder.c:10 |
| ActionUseUndergroundLever | interact | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionUseUndergroundLever.c:1 |
| ActionUseUndergroundPanel | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionUseUndergroundPanel.c:1 |
| ActionVehicleHornLong | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Vehicles/ActionVehicleHorn.c:202 |
| ActionVehicleHornShort | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/Vehicles/ActionVehicleHorn.c:60 |
| ActionViewBinoculars | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionViewBinoculars.c:1 |
| ActionViewCompass | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionViewCompass.c:21 |
| ActionViewOptics | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionViewOptics.c:1 |
| ActionWashHandsItem | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionWashHandsItem.c:2 |
| ActionWashHandsItemContinuous | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWashHandsItemContinuous.c:9 |
| ActionWashHandsSnow | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWashHandsSnow.c:9 |
| ActionWashHandsWater | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWashHandsWater.c:9 |
| ActionWashHandsWaterOne | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionWashHandsWaterOne.c:12 |
| ActionWashHandsWell | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWashHandsWell.c:9 |
| ActionWashHandsWellOne | interact | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Interact/ActionWashHandsWellOne.c:12 |
| ActionWashHeadItemContinuous | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWashHeadItemContinuous.c:9 |
| ActionWashHeadWater | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWashHeadWater .c:9 |
| ActionWashHeadWell | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWashHeadWell.c:9 |
| ActionWashHeadWettingClothesBase | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWashHeadWettingClothesBase.c:1 |
| ActionWaterGardenSlot | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWaterGardenSlot.c:11 |
| ActionWaterPlant | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWaterPlant.c:11 |
| ActionWetClothingFromContainer | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWetClothingFromContainer.c:34 |
| ActionWetClothingInHandsBase | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWetClothingInHandsBase.c:22 |
| ActionWetClothingInHandsWater | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWetClothingInHandsWater.c:3 |
| ActionWetClothingInHandsWell | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWetClothingInHandsWell.c:3 |
| ActionWorldCraft | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWorldCraft.c:34 |
| ActionWorldCraftCancel | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionWorldCraftCancel.c:1 |
| ActionWorldCraftSwitch | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionWorldCraftSwitch.c:2 |
| ActionWorldFlagActionSwitch | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionWorldFlagActionSwitch.c:12 |
| ActionWorldLiquidActionSwitch | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionWorldLiquidActionSwitch.c:3 |
| ActionWringClothes | continuous | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionWringClothes.c:12 |
| ActionWritePaper | continuous | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionWritePaper.c:38 |
| ActionZoomIn | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionZoomIn.c:1 |
| ActionZoomOut | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionZoomOut.c:1 |
| AnimatedActionBase | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/AnimatedActionBase.c:145 |
| FirearmActionAttachMagazine | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Weapons/FirearmActionAttachMagazine.c:11 |
| FirearmActionAttachMagazineQuick | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Weapons/FirearmActionAttachMagazine.c:225 |
| FirearmActionBase | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Weapons/FirearmActionBase.c:1 |
| FirearmActionDetachMagazine | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Weapons/FirearmActionDetachMagazine.c:151 |
| FirearmActionDetachMagazine_Old | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Weapons/FirearmActionDetachMagazine.c:14 |
| FirearmActionLoadBullet | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Weapons/FirearmActionLoadBullet.c:1 |
| FirearmActionLoadBulletQuick | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Weapons/FirearmActionLoadBullet.c:82 |
| FirearmActionLoadMultiBullet | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Weapons/FirearmActionLoadMultiBullet.c:1 |
| FirearmActionLoadMultiBulletQuick | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Weapons/FirearmActionLoadMultiBullet.c:94 |
| FirearmActionLoadMultiBulletRadial | other ActionBase path | no-item-add-call-observed | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Weapons/FirearmActionLoadMultiBullet.c:171 |
| FirearmActionMechanicManipulate | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Weapons/FirearmActionMechanicManipulate.c:1 |
| FirearmActionUnjam | other ActionBase path | source-add-call | declared ancestry; runtime UNKNOWN | 4_World/Classes/UserActionsComponent/Actions/Weapons/FirearmActionUnjam.c:1 |

### Unresolved possible action ancestry retained

These classes lack a resolved ActionBase path; they were not silently rejected as confirmed non-actions.

| Class | Unresolved reasons |
| --- | --- |
| AK74_Hndgrd | ambiguous_definition |
| AK74_WoodBttstck | ambiguous_definition |
| AKS74U_Bttstck | ambiguous_definition |
| AK_FoldingBttstck | ambiguous_definition |
| AK_PlasticBttstck | ambiguous_definition |
| AK_PlasticHndgrd | ambiguous_definition |
| AK_RailHndgrd | ambiguous_definition |
| AK_WoodBttstck | ambiguous_definition |
| AK_WoodHndgrd | ambiguous_definition |
| ActionDismantleDebugData | conditional_definition |
| ActionInfoDebugData | conditional_definition |
| ActionManager | conditional_definition |
| AlarmClock_Blue | ambiguous_definition |
| AlarmClock_ColorBase | ambiguous_definition |
| AlarmClock_Green | ambiguous_definition |
| AlarmClock_Red | ambiguous_definition |
| AnimEditor | ambiguous_definition,complex_alias,conditional_alias,conditional_definition |
| AnimPhysMove | conditional_definition |
| AnimPhysOwnerState | conditional_definition |
| Animal | ambiguous_definition,conditional_definition,header_unresolved |
| Anniversary_FireworksLauncher | ambiguous_definition |
| AntiChemInjector | ambiguous_definition |
| AntiHazard_Preset | conditional_definition |
| AntiPestsSpray | ambiguous_definition |
| ArrayBoxDraw | conditional_definition,header_unresolved |
| ArrayBreadcrumbDraw | conditional_definition,header_unresolved |
| AtlasBipod | ambiguous_definition |
| BBMaterials_Preset | conditional_definition |
| BarbedBaseballBat | ambiguous_definition |
| BaseContainer | ambiguous_definition,complex_alias |
| BaseSoundComponent | conditional_definition |
| BaseballBat | ambiguous_definition |
| BasicCamera | conditional_definition |
| BasicEntity | conditional_definition |
| Blend2D | header_unresolved |
| BloodTestKit | ambiguous_definition |
| Boat | ambiguous_definition,conditional_definition,header_unresolved |
| BoatMove | conditional_definition |
| BoatOwnerState | conditional_definition |
| BoatScript | ambiguous_definition,conditional_definition,header_unresolved |
| BoatScriptMove | conditional_definition |
| BoatScriptOwnerState | conditional_definition |
| Boat_01_Black | ambiguous_definition,conditional_definition,header_unresolved |
| Boat_01_Blue | ambiguous_definition,conditional_definition,header_unresolved |
| Boat_01_Camo | ambiguous_definition,conditional_definition,header_unresolved |
| Boat_01_ColorBase | ambiguous_definition,conditional_definition,header_unresolved |
| Boat_01_Orange | ambiguous_definition,conditional_definition,header_unresolved |
| Bot | conditional_definition |
| BotActionBase | conditional_definition |
| BotAttack | conditional_definition |
| BotDestroyEntityInHands | conditional_definition |
| BotDropEntityInHands | conditional_definition |
| BotEatEntityInHands | conditional_definition |
| BotEventAttacked | conditional_definition |
| BotEventBase | conditional_definition |
| BotEventEndFail | conditional_definition |
| BotEventEndOK | conditional_definition |
| BotEventEndTimeout | conditional_definition |
| BotEventEntityAttached | conditional_definition |
| BotEventEntityDetached | conditional_definition |
| BotEventEntityInHands | conditional_definition |
| BotEventEntityInHandsOpened | conditional_definition |
| BotEventEntitySpawned | conditional_definition |
| BotEventHandsEmpty | conditional_definition |
| BotEventHuntedTargetInSight | conditional_definition |
| BotEventHuntedTargetLost | conditional_definition |
| BotEventObstacle | conditional_definition |
| BotEventOnItemInHandsChanged | conditional_definition |
| BotEventSelectedTarget | conditional_definition |
| BotEventStart | conditional_definition |
| BotEventStartDebug | conditional_definition |
| BotEventStop | conditional_definition |
| BotEventValidForward | conditional_definition |
| BotEventWaitTimeout | conditional_definition |
| BotFSM | conditional_definition,header_unresolved |
| BotGuardAnd | conditional_definition |
| BotGuardBase | conditional_definition |
| BotGuardDebugEventMatches | conditional_definition |
| BotGuardHasItemInHands | conditional_definition |
| BotGuardNot | conditional_definition |
| BotGuardOr | conditional_definition |
| BotHunt | conditional_definition |
| BotHunt_Hunting | conditional_definition |
| BotHunt_Tracking | conditional_definition |
| BotMoveForward | conditional_definition |
| BotMovementRandomizer | conditional_definition |
| BotOpenEntityInHands | conditional_definition |
| BotPerformAction | conditional_definition |
| BotSelectZombieTarget | conditional_definition |
| BotSpawnDead | conditional_definition |
| BotSpawnEntityInHands | conditional_definition |
| BotStanceRandomizer | conditional_definition |
| BotStateBase | conditional_definition |
| BotStateIdle | conditional_definition |
| BotStateMachineData | conditional_definition |
| BotTestAttachAndDropCycle | conditional_definition |
| BotTestAttachAndDropCycle_Attaching | conditional_definition |
| BotTestAttachAndDropCycle_Detaching | conditional_definition |
| BotTestItemMoveBackAndForth | conditional_definition |
| BotTestItemMoveBackAndForth_MoveFromSlotToSlot | conditional_definition |
| BotTestSpamUserActions | conditional_definition |
| BotTestSpamUserActions_GetEntityFromSlot | conditional_definition |
| BotTestSpamUserActions_Start | conditional_definition |
| BotTestSwapG2H | conditional_definition |
| BotTestSwapInternal | conditional_definition |
| BotTestSwapInternalC2H | conditional_definition |
| BotTestSwapWithCorpse | conditional_definition |
| BotTimedWait | conditional_definition |
| BotTrigger | conditional_definition |
| BotTurnToValidForward | conditional_definition |
| BotWaitForChangeInHands | conditional_definition |
| BotWaitForEmptyHands | conditional_definition |
| Bot_TestSpawnDeadSelectBury | conditional_definition |
| Bot_TestSpawnOpen | conditional_definition |
| Bot_TestSpawnOpenDestroy | conditional_definition |
| Bot_TestSpawnOpenDrop | conditional_definition |
| Bot_TestSpawnOpenEat | conditional_definition |
| BoxDraw | conditional_definition |
| BoxDrawCenterGizmo | conditional_definition |
| BoxDrawCornerGizmo | conditional_definition |
| BoxDrawGizmo | conditional_definition |
| BrassKnuckles_ColorBase | ambiguous_definition |
| BrassKnuckles_Dull | ambiguous_definition |
| BrassKnuckles_MenAtArms | ambiguous_definition |
| BrassKnuckles_Shiny | ambiguous_definition |
| BreadcrumbDraw | conditional_definition |
| BreadcrumbGizmo | conditional_definition |
| BuildResourceContext | conditional_definition |
| BunkerBroadcastComponentDebugData | conditional_definition |
| BurlapSack | ambiguous_definition |
| ButtonAttribute | conditional_definition |
| ButtstockBase | ambiguous_definition |
| CallQueue | header_unresolved |
| CameraToolsMenuClient | conditional_definition |
| CameraToolsMenuServer | conditional_definition |
| CanOpener | ambiguous_definition |
| Candle | ambiguous_definition |
| CannabisSeeds | ambiguous_definition |
| CannabisSeedsPack | ambiguous_definition |
| Car | ambiguous_definition,conditional_definition,header_unresolved |
| CarMove | conditional_definition |
| CarOwnerState | conditional_definition |
| CarScript | ambiguous_definition,conditional_definition,header_unresolved |
| CarScriptMove | conditional_definition |
| CarScriptOwnerState | conditional_definition |
| CargoGrid | conditional_definition |
| CargoList | ambiguous_definition,conditional_definition |
| Cassette | ambiguous_definition |
| CharacterEntity | conditional_definition |
| CharacterStepsDebug | conditional_definition |
| ChickenFeather | ambiguous_definition |
| CigarettePack_Chernamorka | ambiguous_definition |
| CigarettePack_ColorBase | ambiguous_definition |
| CigarettePack_Merkur | ambiguous_definition |
| CigarettePack_Partyzanka | ambiguous_definition |
| CivilianSedan | ambiguous_definition,conditional_definition,header_unresolved |
| CivilianSedan_Black | ambiguous_definition,conditional_definition,header_unresolved |
| CivilianSedan_TEST | ambiguous_definition,conditional_definition,header_unresolved |
| CivilianSedan_Wine | ambiguous_definition,conditional_definition,header_unresolved |
| ClearSyringe | ambiguous_definition |
| ClockBase | ambiguous_definition |
| ConstructionDebug | conditional_definition |
| ConstructionDismantleDebugData | conditional_definition |
| CrashDebugData | conditional_definition |
| Crowbar | ambiguous_definition |
| DateTimeUtcAsInt | ambiguous_definition,conditional_alias,conditional_definition |
| DayZPlayer | ambiguous_definition,conditional_definition,header_unresolved |
| DayZPlayerImplement | ambiguous_definition,conditional_definition,header_unresolved |
| DayZPlayerImplementMove | conditional_definition |
| DayZPlayerImplementOwnerState | conditional_definition |
| DayZPlayerMove | conditional_definition |
| DayZPlayerOwnerState | conditional_definition |
| DoorTestCamera | ambiguous_definition |
| DragQueue | header_unresolved |
| DrawGizmoBase | conditional_definition |
| DummyDoxygenClass | conditional_definition |
| EasterEgg | ambiguous_definition |
| ElectronicRepairKit | ambiguous_definition |
| EnvDebugData | conditional_definition |
| EnvDebugMiscData | conditional_definition |
| EnvDebugPlayerData | conditional_definition |
| EnvDebugWeatherData | conditional_definition |
| Epinephrine | ambiguous_definition |
| EpoxyPutty | ambiguous_definition |
| FSMBase | header_unresolved |
| FSMTransition | header_unresolved |
| Fabric | ambiguous_definition |
| Fal_FoldingBttstck | ambiguous_definition |
| Fal_OeBttstck | ambiguous_definition |
| FallDamageDebugData | conditional_definition |
| Farmer_Preset | conditional_definition |
| FeatureTimeAccel | conditional_definition |
| FireExtinguisher | ambiguous_definition |
| FireworksBase | ambiguous_definition |
| FireworksLauncher | ambiguous_definition |
| Fisherman_Preset | conditional_definition |
| FreshSpawn_Preset | conditional_definition |
| FryingPan | ambiguous_definition |
| Game | conditional_definition |
| GameViewer | ambiguous_definition,complex_alias,conditional_alias,conditional_definition |
| GeneratedResources | conditional_definition |
| GenericComponent | conditional_definition |
| GenericComponentClass | conditional_definition |
| GenericEntity | conditional_definition |
| GenericTerrainEntity | conditional_definition |
| GenericWorldEntity | conditional_definition |
| GenericWorldFogEntity | conditional_definition |
| GenericWorldLightEntity | conditional_definition |
| GeyserDebugData | conditional_definition |
| GhillieAtt_ColorBase | ambiguous_definition |
| GhillieAtt_Desert | ambiguous_definition |
| GhillieAtt_Mossy | ambiguous_definition |
| GhillieAtt_Tan | ambiguous_definition |
| GhillieAtt_Winter | ambiguous_definition |
| GhillieAtt_Woodland | ambiguous_definition |
| GorkaHelmetVisor | ambiguous_definition |
| Groza_LowerReceiver | ambiguous_definition |
| GunCaseKeys_Blue | ambiguous_definition |
| GunCaseKeys_Colorbase | ambiguous_definition |
| GunCaseKeys_Orange | ambiguous_definition |
| GunCaseKeys_Red | ambiguous_definition |
| HFSMBase | header_unresolved |
| Hammer | ambiguous_definition |
| HandFSM | header_unresolved |
| HandSaw | ambiguous_definition |
| HandcuffKeys | ambiguous_definition |
| Handcuffs | ambiguous_definition |
| Hatchback_02 | ambiguous_definition,conditional_definition,header_unresolved |
| Hatchback_02_Black | ambiguous_definition,conditional_definition,header_unresolved |
| Hatchback_02_Blue | ambiguous_definition,conditional_definition,header_unresolved |
| Hatchback_02_TEST | ambiguous_definition,conditional_definition,header_unresolved |
| HayHook | ambiguous_definition |
| Helicopter | ambiguous_definition,conditional_definition,header_unresolved |
| HelicopterAuto | ambiguous_definition,conditional_definition,header_unresolved |
| HelicopterScript | ambiguous_definition,conditional_definition,header_unresolved |
| HescoBox | ambiguous_definition |
| Human | ambiguous_definition,conditional_definition,header_unresolved |
| IEntityComponentSource | ambiguous_definition,complex_alias,conditional_alias,conditional_definition |
| IEntitySource | ambiguous_definition,complex_alias |
| Iceaxe | ambiguous_definition |
| InjectionVial | ambiguous_definition |
| InputManager | conditional_definition |
| InventoryDebug | conditional_definition |
| Inventory_Base | ambiguous_definition |
| JsonFileLoader | header_unresolved |
| KitchenTimer | ambiguous_definition |
| LeatherSewingKit | ambiguous_definition |
| LightAI | ambiguous_definition,conditional_definition,header_unresolved |
| LightAIBase | ambiguous_definition,conditional_definition,header_unresolved |
| LightEntity | conditional_definition |
| Link | header_unresolved |
| LongWoodenStick | ambiguous_definition |
| LugWrench | ambiguous_definition |
| M249_Bipod | ambiguous_definition |
| M249_Hndgrd | ambiguous_definition |
| M249_RisHndgrd | ambiguous_definition |
| M4_CQBBttstck | ambiguous_definition |
| M4_MPBttstck | ambiguous_definition |
| M4_MPHndgrd | ambiguous_definition |
| M4_OEBttstck | ambiguous_definition |
| M4_PlasticHndgrd | ambiguous_definition |
| M4_RISHndgrd | ambiguous_definition |
| MP5_PlasticHndgrd | ambiguous_definition |
| MP5_RailHndgrd | ambiguous_definition |
| MP5k_StockBttstck | ambiguous_definition |
| Mace | ambiguous_definition |
| MainMenuWorldData | conditional_definition |
| Man | ambiguous_definition,conditional_definition,header_unresolved |
| ManBase | ambiguous_definition,conditional_definition,header_unresolved |
| Material | ambiguous_definition,complex_alias |
| MeatTenderizer | ambiguous_definition |
| MenuBase | conditional_definition |
| MenuBindAttribute | conditional_definition |
| MenuManager | conditional_definition |
| MessTin | ambiguous_definition |
| MessageBox | conditional_definition |
| MetaFile | ambiguous_definition,complex_alias,conditional_alias,conditional_definition |
| Military_Light_Preset | conditional_definition |
| ModelEntity | conditional_definition |
| Morphine | ambiguous_definition |
| Mosin_Bayonet | ambiguous_definition |
| Motorbike | ambiguous_definition,conditional_definition,header_unresolved |
| MotorbikeMove | conditional_definition |
| MotorbikeOwnerState | conditional_definition |
| MotorbikeScript | ambiguous_definition,conditional_definition,header_unresolved |
| MotorbikeScriptMove | conditional_definition |
| MotorbikeScriptOwnerState | conditional_definition |
| Motorbike_01_Blue | ambiguous_definition,conditional_definition,header_unresolved |
| Motorbike_01_ColorBase | ambiguous_definition,conditional_definition,header_unresolved |
| Motorbike_01_Red | ambiguous_definition,conditional_definition,header_unresolved |
| Motorbike_01_Yellow | ambiguous_definition,conditional_definition,header_unresolved |
| Motorbike_02_ColorBase | ambiguous_definition,conditional_definition,header_unresolved |
| Motorbike_02_Red | ambiguous_definition,conditional_definition,header_unresolved |
| MyBotTrigger | conditional_definition |
| NailedBaseballBat | ambiguous_definition |
| Nails | ambiguous_definition |
| OFSMBase | header_unresolved |
| Oculus | conditional_definition |
| OffroadHatchback | ambiguous_definition,conditional_definition,header_unresolved |
| OffroadHatchback_Blue | ambiguous_definition,conditional_definition,header_unresolved |
| OffroadHatchback_TEST | ambiguous_definition,conditional_definition,header_unresolved |
| OffroadHatchback_White | ambiguous_definition,conditional_definition,header_unresolved |
| Offroad_02 | ambiguous_definition,conditional_definition,header_unresolved |
| Offroad_02_Beige | ambiguous_definition,conditional_definition,header_unresolved |
| Offroad_02_TEST | ambiguous_definition,conditional_definition,header_unresolved |
| P1907_Bayonet | ambiguous_definition |
| PP19_Bttstck | ambiguous_definition |
| Paddle | ambiguous_definition |
| Param1 | header_unresolved |
| Param10 | header_unresolved |
| Param2 | header_unresolved |
| Param3 | header_unresolved |
| Param4 | header_unresolved |
| Param5 | header_unresolved |
| Param6 | header_unresolved |
| Param7 | header_unresolved |
| Param8 | header_unresolved |
| Param9 | header_unresolved |
| ParamEnumArray | header_unresolved |
| ParticleEditor | ambiguous_definition,complex_alias,conditional_alias,conditional_definition |
| Pawn | conditional_definition |
| PawnMove | conditional_definition |
| PawnOwnerState | conditional_definition |
| Pen_Black | ambiguous_definition |
| Pen_Blue | ambiguous_definition |
| Pen_ColorBase | ambiguous_definition |
| Pen_Green | ambiguous_definition |
| Pen_Red | ambiguous_definition |
| PepperSeeds | ambiguous_definition |
| PepperSeedsPack | ambiguous_definition |
| Person | conditional_definition |
| Physics | ambiguous_definition,complex_alias |
| Physics6DOFJoint | ambiguous_definition,complex_alias |
| Physics6DOFSpringJoint | ambiguous_definition,complex_alias |
| PhysicsBallSocketJoint | ambiguous_definition,complex_alias |
| PhysicsBlock | ambiguous_definition,complex_alias |
| PhysicsConeTwistJoint | ambiguous_definition,complex_alias |
| PhysicsFixedJoint | ambiguous_definition,complex_alias |
| PhysicsGeom | ambiguous_definition,complex_alias |
| PhysicsHingeJoint | ambiguous_definition,complex_alias |
| PhysicsJoint | ambiguous_definition,complex_alias |
| PhysicsSliderJoint | ambiguous_definition,complex_alias |
| Pipe | ambiguous_definition |
| PipeWrench | ambiguous_definition |
| PlantMaterial | ambiguous_definition |
| PlayerBase | ambiguous_definition,conditional_definition,header_unresolved |
| PlayerBaseClient | ambiguous_definition,conditional_definition,header_unresolved |
| PlayerBaseMove | conditional_definition |
| PlayerBaseOwnerState | conditional_definition |
| PlayerStat | header_unresolved |
| PluginDiagMenu | conditional_definition,modded_order_not_evaluated |
| PluginDiagMenuClient | conditional_definition,modded_order_not_evaluated |
| PluginDiagMenuClientModded | conditional_definition,header_unresolved |
| PluginDiagMenuModded | conditional_definition,header_unresolved |
| PluginDiagMenuServer | conditional_definition,modded_order_not_evaluated |
| PluginInventoryDebug | conditional_definition |
| PluginUndergroundTriggerManager | conditional_definition |
| PoliceBaton | ambiguous_definition |
| PotatoSeed | ambiguous_definition |
| PresetSpawnBase | conditional_definition |
| PumpkinSeeds | ambiguous_definition |
| PumpkinSeedsPack | ambiguous_definition |
| RebuildingSpawner | conditional_definition |
| Red9Bttstck | ambiguous_definition |
| RemoteDetonator | ambiguous_definition |
| RemoteDetonatorReceiver | ambiguous_definition |
| RemoteDetonatorTrigger | ambiguous_definition |
| RenderTarget | conditional_definition |
| RenderTargetClass | conditional_definition |
| ResourceManager | ambiguous_definition,complex_alias,conditional_alias,conditional_definition |
| ResourceManagerPlugin | conditional_definition |
| ResourceName | ambiguous_definition |
| RoboclientUtils | conditional_definition |
| Rope | ambiguous_definition |
| SCAR_PrecisionBttstck | ambiguous_definition |
| SCAR_StockBttstck | ambiguous_definition |
| SKS_Bayonet | ambiguous_definition |
| Saiga_Bttstck | ambiguous_definition |
| SalineBag | ambiguous_definition |
| SalineBagIV | ambiguous_definition |
| ScientificBriefcaseKeys | ambiguous_definition |
| ScriptCamera | conditional_definition |
| ScriptCameraClass | conditional_definition |
| ScriptComponent | conditional_definition |
| ScriptEditor | ambiguous_definition,complex_alias,conditional_alias,conditional_definition |
| ScriptLight | conditional_definition |
| ScriptLightClass | conditional_definition |
| ScriptModel | conditional_definition |
| ScriptModelClass | conditional_definition |
| Sedan_02 | ambiguous_definition,conditional_definition,header_unresolved |
| Sedan_02_Grey | ambiguous_definition,conditional_definition,header_unresolved |
| Sedan_02_Red | ambiguous_definition,conditional_definition,header_unresolved |
| Sedan_02_TEST | ambiguous_definition,conditional_definition,header_unresolved |
| SeedBase | ambiguous_definition |
| SeedPackBase | ambiguous_definition |
| SewingKit | ambiguous_definition |
| SharpWoodenStick | ambiguous_definition |
| SignalInput | conditional_definition |
| SimpleCircularBuffer | header_unresolved |
| SimpleMovingAverage | header_unresolved |
| SledgeHammer | ambiguous_definition |
| Spear | ambiguous_definition |
| SpearBone | ambiguous_definition |
| SpearStone | ambiguous_definition |
| Splint | ambiguous_definition |
| StartKitIV | ambiguous_definition |
| SurfaceInfo | ambiguous_definition,complex_alias |
| SurfaceProperties | ambiguous_definition,complex_alias |
| SurvivorBase | ambiguous_definition,conditional_definition,header_unresolved |
| TSelectableActionInfoArray | header_unresolved |
| TSelectableActionInfoArrayEx | header_unresolved |
| TimerQueue | header_unresolved |
| TomatoSeeds | ambiguous_definition |
| TomatoSeedsPack | ambiguous_definition |
| Transport | ambiguous_definition,conditional_definition,header_unresolved |
| TransportMove | conditional_definition |
| TransportOwnerState | conditional_definition |
| Truck_01_Base | ambiguous_definition,conditional_definition,header_unresolved |
| Truck_01_Cargo | ambiguous_definition,conditional_definition,header_unresolved |
| Truck_01_Chassis | ambiguous_definition,conditional_definition,header_unresolved |
| Truck_01_Covered | ambiguous_definition,conditional_definition,header_unresolved |
| Truck_01_Covered_Blue | ambiguous_definition,conditional_definition,header_unresolved |
| Truck_01_Covered_Orange | ambiguous_definition,conditional_definition,header_unresolved |
| Truck_01_Covered_TEST | ambiguous_definition,conditional_definition,header_unresolved |
| Truck_02 | ambiguous_definition,conditional_definition,header_unresolved |
| UndergroundBreadcrumbHandle | conditional_definition |
| UndergroundTriggerDrawBase | conditional_definition |
| UndergroundTriggerEditorCustomListElement | conditional_definition |
| UndergroundTriggerEditorDialog | conditional_definition |
| UndergroundTriggerEditorDiscardBreadcrumbsDialog | conditional_definition |
| UndergroundTriggerEditorMenu | conditional_definition |
| UndergroundTriggerEditorPopupBase | conditional_definition |
| UndergroundTriggerEditorReloadDialog | conditional_definition |
| UndergroundTriggerEditorRenameBreadcrumbDialog | conditional_definition |
| UndergroundTriggerEditorRenameDialog | conditional_definition |
| UndergroundTriggerHandle | conditional_definition |
| Update117_Preset | conditional_definition |
| Update118_Preset | conditional_definition |
| VRDevice | conditional_definition |
| VRDevice_PS4 | conditional_definition |
| VRHandEntity | conditional_definition |
| Van_01 | ambiguous_definition,conditional_definition,header_unresolved |
| WBModuleDef | ambiguous_definition,complex_alias,conditional_alias,conditional_definition |
| WBProgressDialog | conditional_definition |
| WeaponCleaningKit | ambiguous_definition |
| WeaponFSM | header_unresolved |
| WeaponLiftDiag | conditional_definition |
| WeaponLiftDiagData | conditional_definition |
| Whetstone | ambiguous_definition |
| WidgetSource | ambiguous_definition,complex_alias |
| Workbench | conditional_definition |
| WorkbenchPluginAttribute | conditional_definition |
| WorkbenchToolAttribute | conditional_definition |
| WorldEditorIngame | conditional_definition |
| WorldEntity | conditional_definition |
| WorldEntityClass | conditional_definition |
| WorldsMenu | conditional_definition |
| WorldsMenuClass | conditional_definition |
| Wrench | ambiguous_definition |
| XmasBaseballBat | ambiguous_definition |
| XmasLights | ambiguous_definition |
| Zombie | ambiguous_definition,conditional_definition,header_unresolved |
| ZucchiniSeeds | ambiguous_definition |
| ZucchiniSeedsPack | ambiguous_definition |
| array | header_unresolved |
| map | header_unresolved |
| multiMap | header_unresolved |
| set | header_unresolved |
| vobject | ambiguous_definition,complex_alias |

### Primary source anchor hashes

The following inspected native files are also covered by the complete shared source manifest.

| Source path | SHA-256 |
| --- | --- |
| 4_World/Classes/Recipes/RecipeBase.c | 88211d21144f20828981ba3f9663057c010cdf13ac38babc6648e7d8382f1178 |
| 4_World/Classes/Recipes/Recipes/CraftRag.c | a4a162599fa7438155f012a2dfc5720c1c1edd7c6fad55e9c222dcea0fd927ec |
| 4_World/Classes/Recipes/Recipes/DeCraftWoodenCrate.c | 56bbd375ab7d51f371b5f9c8657fbc1d31f84859d7af0a51545298b9d856cee4 |
| 4_World/Classes/Recipes/Recipes/RepairWithPliers.c | ac4d741c371079ab6ac9310d69b48854ca8badb7c8fead814ee3b1166dd98c51 |
| 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionCraftRopeBelt.c | 25376107c4f27286e4dbb1631a958c0d1dc73f6ef48aa3b14bc3fb38a7832a09 |
| 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDeCraftRopeBelt.c | 262d38865bb9d97715846bdce6b9024228bef05feb1745e81fd8e12af7b120da |
| 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairCarChassis.c | 10c86caaaf2d67af31c87bcc32686ae33c4e98e2ed8c65a9f6221a3c346dbc07 |
| 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairTentPart.c | e7d7681f638db1d254279e981ffa395dc4b5a767de10421ce426d5a5808769ef |
| 4_World/Entities/ItemBase.c | 05a51f125766ca9cff4d0e5fed82ccdd209942aaf5dc30e8a2df7120be2e49c5 |
| 4_World/Entities/ItemBase/Clothing/RopeBelt.c | 735736911436c07c8e6de832f0b8c09295ac3863d83339838a442a5f285fc1ba |
| 4_World/Entities/ItemBase/Gear/Crafting/crafting.c | 7b5131d2c40028d47034dcdd7ae0ffee46102da2f56a62855dc597d3a9d34ee6 |
| 4_World/Plugins/PluginBase/PluginRepairing.c | dcba7eccfc9182e1110f4e5542c2a493f29dec1138bdefaf6c8c119fcbbc0bbc |
| 4_World/Static/MiscGameplayFunctions.c | 40a02625fba5ac9dd28568e511d988f5ed5e91cdc0177af1a07c3a0f9097d4e2 |



## V1 implemented set

2026-11-17 active user decision: complete the justified V1 set before client
connection; earlier design HOLDs do not prevent the selected source work. This
appendix records source/offline results only. Runtime acceptance and production
enablement stay pending. The original design record above is preserved.

The implementation report is
[scratchpad-review/v1-crafting/REPORT.md](../../scratchpad-review/v1-crafting/REPORT.md).
It records the complete recipe table, packed-config hashes/offsets, every new
native API anchor, actual RED/GREEN output and in-game checklist. The central
disposition is: N1 executable complete decisions added to the existing audit;
N2/N3 explicitly invoked diagnostic source authored; N4 external runner remains
separately owned and unimplemented here; N5/N7 actual native readback/acceptance
remain pending; N6 authored synthetic guards/conservation pass, native failure
cases remain pending. No missing engine experiment is marked accepted.

## Final V1 recipe table

Every HC row consumes exactly one empty loose source, preserves the original
tool entity, charges the stated absolute health wear and requires tool health
**strictly greater** than wear at completion. Ordinary rows exclude ruined
sources; the final row admits only damage level 4. Quantities below are native
stack units, not full stacks; e.g. MetalWire 1 does not mean quantity 50.

| Registered subclass / input | Tool | Output / fixed yield | Wear; animation units | Evidence and design decision |
| --- | --- | --- | --- | --- |
| HCSalvageCamoNet / CamoNet | Cutting set C below | Netting 1 | 5; 2 | Camping config C1: textile source. Native G1 consumes this exact Netting in the existing camouflage chain. One fragment is the existing loss policy, not an inferred full-net recovery. |
| HCSalvageCableReel / CableReel | Pliers | MetalWire 1 | 5; 2 | C1 explicitly defines a passive wired device, cordLength=15, socket/plug types and cord texture. Recover one wire unit; no conversion of plastic housing or invention of an electronics kit. Refuse plugged reels and reels powering any device. |
| HCRecoverLargeLeather / LeatherJacket_{Beige,Black,Brown,Natural}; LeatherStorageVest_{Beige,Black,Brown,Natural} | C | TannedLeather 2 | 5; 2 | L3/L5: exact concrete material selections; kit type 3/cost 25. Existing large-panel balance retained. A vest with either grenade attachment is rejected; jacket/vest cargo must be empty. |
| HCRecoverMediumLeather / LeatherPants_{Beige,Black,Brown,Natural}; LeatherShirt_Natural; **LeatherGloves_Beige; LeatherHat_Beige** | C | TannedLeather 1 | 5; 2 | L1/L2/L3/L4: concrete garment config and material/repair evidence. New gloves/hat use the existing single-panel recovery rule, following the former belt mechanism's one-unit result, not a native leatherYield calculation. Pants/shirt balance retained. |
| HCRecoverBatWood / BaseballBat; XmasBaseballBat | Hacksaw or HandSaw | WoodenStick 2 | 5; 2 | B1: both exact configs have soundImpactType=wood and bat damage materials. Destructive downgrading; no replacement bat. |
| HCRecoverNailedBat / NailedBaseballBat | Hacksaw or HandSaw | WoodenStick 1 AND Nail 4 | 8; 3 | B1 plus native CraftBaseBallBatNailed.c:13,23,27,34,47 proves bat + 12 nails. Recover four nails and reduced wood; the nail co-product is mandatory and audited. |
| HCRecoverBarbedBat / BarbedBaseballBat | Pliers | MetalWire 1 | 8; 3 | B1 contains barbed-wire damage material; native CraftBaseBallBatBarbed.c:26,31,32,36,49 proves BarbedWire consumption and result. Existing raw-wire recovery deliberately discards bat/remaining wire. |
| HCRecoverRuinedCrate / ruined WoodenCrate ONLY | Crowbar, WoodAxe, Hatchet or FirefighterAxe | WoodenPlank 1 AND Nail 2 | 20; 3 | C1: wood impact/material. Native CraftWoodenCrate.c:15,21,27,31,36,40 proves 8 planks + 16 nails; salvage recovers 1/8 of each, destroys the crate and cannot rebuild it. Native DeCraftWoodenCrate.c:12 excludes ruined sources despite ruined branches in Do:85. This HC row deliberately makes that separate ruined use reachable. |

Brace notation expands only the four named exact classes; runtime source
matching has no prefix or inheritance wildcard. All quantities and timing here
are explicit balance choices, not measurements of real material mass or seconds.
Native `4_World/Classes/Recipes/RecipeBase.c:95` multiplies animation units
by `CRAFTING_TIME_UNIT_SIZE` (`3_Game/constants.c:675`, value 4).

C is the existing 36 exact native cutting alternatives, observed in native
`CraftRag.c:23–59`, `CraftBurlapStrips.c:31–63`,
`DeCraftGhillieAttachment.c:36–67`, `DeCraftCourierBag.c:36–67`:

```
KitchenKnife AK_Bayonet Akinaka BoneKnife BrickTrowel Cleaver CombatKnife
Crowbar CrudeMachete DonerKnife FangeKnife FarmingHoe FieldShovel
FirefighterAxe Hacksaw HandSaw Hatchet HayHook HuntingKnife Iceaxe Jambiya
KukriKnife M9A1_Bayonet Machete Mosin_Bayonet OrientalMachete Pickaxe
SKS_Bayonet Scimitar Screwdriver Shovel Sickle SteakKnife StoneKnife Sword WoodAxe
```

G1: Native `4_World/Classes/Recipes/Recipes/PluginRecipesManagerBase.c:27–28`
already registers `CraftGhillieAttachment` and its reverse. The forward recipe
in `CraftGhillieAttachment.c:15,21,27,31,36,40,46,51` consumes Netting 1 plus
BurlapStrip 2 and creates **one GhillieAtt_Tan**, with native averaged condition.
HC adds no color, slot, material, host compatibility or duplicate registration.
The resulting rifle attachment/visuals still require actual client checks.

## Config evidence

Read installed packed config entries locally with a temporary standard-library
RAP reader, without launching the game. No config dump, asset, private profile
or decoder output is bundled. These are T0 packed-config observations; they do
not prove merged live config, inventory eligibility or physical yield. Binary
offsets replace line numbers for these binary entries. All entries are under
`/home/david/.cache/hollow-country/wine-server-20261116/addons/`.

| Ref | PBO entry; SHA-256 of config bytes | Exact observations / byte offsets |
| --- | --- | --- |
| L1 | characters_gloves.pbo/config.bin; 269902f105209baebd30dc56eaad0f98ace55476b422e26a9a43a2368038f51a | LeatherGloves_ColorBase@27079: kits [3], costs [25]; LeatherGloves_Beige@28767: scope 2, leather_gloves_Beige material selections. Script declares concrete class at Entities/ItemBase/Clothing/LeatherGloves_ColorBase.c:3. |
| L2 | characters_headgear.pbo/config.bin; ae7c5ebe2fd14336bf9d63e93ccb7694f5cdacb3573f1a9549d5b05cdc268a66 | LeatherHat_ColorBase@93014: kits [5,2], costs [30,25]; LeatherHat_Beige@94766: scope 2, Hat_Leather_beige material. Script concrete class at Clothing/LeatherHat_ColorBase.c:22. Its native repair policy differs from gloves. |
| L3 | characters_tops.pbo/config.bin; 523fca6cf170b64886d2cee86bf9552b887945202be1ecaeda3341d28df80280 | LeatherJacket_ColorBase@105118: kits [3], costs [25], cargo [6,4]; concrete Natural@106314/Beige@107161/Brown@107969/Black@108802 have leather jacket materials. LeatherShirt_ColorBase@141720: kits [3], costs [25], cargo [3,3]; Natural@142897 concrete. Shirt recovery is retained native/config-supported design, not a new inference from its filename. |
| L4 | characters_pants.pbo/config.bin; 99abff5cb0dfef6be270b2112e7ca620889d721bfd5e14634730c61d37186fc0 | LeatherPants_ColorBase@50723: kits [3], costs [25], cargo [3,2]; Natural@51917/Beige@52962/Brown@53828/Black@54692 use leather pants materials. |
| L5 | characters_vests.pbo/config.bin; 185cab0dcf3293b4b2bbe22e4a10d7189c93e1b346ff1aed29d51b63e135fa58 | LeatherStorageVest_ColorBase@22424: kits [3], costs [25], cargo [5,5], two grenade slots; Natural@23690/Beige@24397/Brown@25094/Black@25791 use leather storage materials. |
| C1 | gear_camping.pbo/config.bin; 82747c89eb78c8a3a9408aa540024d3a93df0e19613c3a167c3444e4248e87bb | CamoNet@123889: textile. WoodenCrate@127895: wood/wooden-case material. CableReel@138132, EnergyManager@139466: cord/socket/plug component fields; kits [5,7], costs [30,25]. |
| B1 | weapons_melee.pbo/blunt/config.bin; 98771daec00a4f60c7e45ca97d70be13e7964d7210ed475f95671dae5cde5e55 | BaseballBat@474, NailedBaseballBat@1699, BarbedBaseballBat@2949, XmasBaseballBat@4527: scope 2, wood impact and bat health materials; BarbedBaseballBat includes Barbed_wire_bloody health materials. |
| D1 | characters_data.pbo/config.bin; 0b06d07ef89fb0e100d6fe9eb52575590cbfeeb0483df98fb198945ddbdd5860 | SurvivorBase@2429 supplies Back/Hands slots; SurvivorMale_Base@140482 is scope 0; SurvivorM_Mirek@142111 is concrete scope 2. Native PlayerBase.c:359–410 constructs native player systems; no custom player controller is introduced. |
| D2 | characters_backpacks.pbo/config.bin; 4df08829cb89fe989a0b8c2fdf8502b0efddb17d88fbfacb03639549940c83ae | MountainBag_ColorBase@18910 cargo [7,8]; MountainBag_Blue@20694 concrete scope 2. Native Clothing/MountainBag_ColorBase.c:1,3 supplies script classes. |

## Repair policy and exclusions

No new repair permissions, kit costs, pristine upgrade or ruined-item repair is
introduced. Where packed arrays prove a pair, use the already registered native
recipe and PluginRepairing; no second HC repair subclass is necessary.

| Config-supported target | Preserved native pair / observed costs |
| --- | --- |
| Beige gloves; jacket; pants; existing storage vests/shirt | LeatherSewingKit type 3, cost 25; native RepairWithLeatherSewingKit.c:61–77. |
| Beige leather hat | DuctTape type 5/cost 30 or SewingKit type 2/cost 25; RepairWithTape.c:63–84 and RepairWithSewingKit.c:61–77. **LeatherSewingKit is excluded**: L2 does not list type 3. Material appearance never grants a repair pair. |
| CableReel | DuctTape type 5/cost 30 or ElectronicRepairKit type 7/cost 25; RepairWithTape.c:63–84 / RepairElectric.c:61–82. Connectivity, condition and live native eligibility still apply. |

Costs are config observations, not a promise that one button press consumes
exactly that quantity. Native PluginRepairing.c:29 calculates actual health and
cost; :92 checks CanRepair; :121 validates kit type; :143 resolves indexed cost.
Native player skill/health ceilings remain in force. Both targets and tools
retain their actual entities for native maintenance.

Evidence-backed exclusions and retained native scope:

- No generic Battery9V/radio/WalkieTalkie/device decomposition. Existence,
  depleted energy, class name, mass, or electronic repair-kit compatibility
  proves no harvestable fastener/wire quantity. CableReel is the explicit cord
  case; barbed bat is the explicit native component case.
- No generic ruined garment, gun, radio, tool or container salvage. The ruined
  crate has proved wood/nails, separate eligibility and irreversible 8:1 loss.
  All other normal recovery rows continue refusing ruined sources.
- No Leather* wildcard or recovery of lizard/fur goods as finished tanned leather.
  Native CraftLeatherBelt/Sheath/Hippack.c:26 use LizardPelt, not TannedLeather;
  the retired HC belt conversion stays retired. Native leather sack/waterskin
  and boar-pelt bag recovery stay native. Non-beige gloves/hats remain outside
  this selected extension, rather than silently becoming eligible by ancestry.
- No new green ghillie, proxy, attachment slot or blanket rifle host support.
  G1 is the complete supported existing-asset camouflage route.
- Native rag/cloth, strips/rope, courier/improvised bags, fishing nets, ghillie
  forward/reverse, wood/stone/bone/knife/hook, wire/trap and practical storage
  paths remain preserved. Cooking, contamination, hygiene and medical actions
  keep native state/effects. Their complete census stays in N1; preservation is
  not certification that every native callback has been executed.
- All 74 disabled recipe declarations (including painting) and 17 unregistered
  declarations remain holds. No class is enabled just because an output exists.
  ActionRepairWithToolFromHands remains test-only. All 55 unresolved recipe
  literal references remain in retained source evidence, not guessed new items.
- Positive config observations nominate maintenance acquisition, never grant
  permissions. Empty/nonpositive/missing repair arrays are explicit exclusions
  or UNKNOWN for regular-kit extensions; special Pliers/Plank/Fabric actions
  are not dismissed as useless.

## Conservation and server authority

Existing HCSalvageRecipe completion guards are shared by both new garment
alternatives: same original ingredient handles; owned loose inventory only;
no cargo or attachments on source/tool; no worn item, corpse, ground/shared
source, dying/unconscious actor, pending deletion, ruined/exhausted tool or
reentrant completion. Completion runs server-side through the native manager.
Tool delta is negative health, destroy=false, quantity delta zero; no tool
replacement/refill or client inventory controller is introduced.

Expected outputs are checked before ingredient consumption. Missing/partial or
wrong-quantity allocations discard only that invocation's provisional outputs.
Source condition/wetness/agents are snapshotted before mutation. Ordinary output
health is 75% of source health; ruined-crate raw materials are fixed 10%, not
pristine replacement equipment. Wetness/agents transfer deliberately; quantity,
energy, ammo and unrelated state do not get generic variable copying.

The offline graph checks every exact HC source alternative and all mandatory
co-products against the existing native boundary, including forward/reverse
leather, net/ghillie, crate and nailed-bat paths. New glove/hat synthetic budgets
are explicitly two hide accounting units -> one panel; these are balance units,
not measurements or native leatherYield. Resource-positive and cross-material
mutations are rejected. Existing behavioral adapters now exercise the new
alternatives for ownership, tool-wear boundaries, retained handles, allocation
failure and result quantities. None of this proves native atomicity or crash
recovery; two-client contention remains an acceptance check.


## Installed native API anchors

All paths below are relative to
`/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`.
These are inspected declarations/implementations, not runtime evidence.

| Authored use | Installed file:line |
| --- | --- |
| GetGame / GetPlugin | 3_Game/gameplay.c:636; 4_World/Plugins/PluginManager.c:327 |
| IsServer, GetTime, GetPlayers, CreatePlayer, ObjectDelete | 3_Game/Global/Game.c:1120,1535,945,332,705 |
| ConfigIsExisting, ConfigGetType, ConfigGetInt, ConfigGetIntArray, ConfigGetFloatArray, ConfigGetBaseName | 3_Game/Global/Game.c:612,546,539,585,578,602 |
| GetType, IsKindOf, IsAlive, GetHealth, GetHealth01, GetMaxHealth, SetHealth, SetHealth01 | 3_Game/Entities/Object.c:467,511,517,994,1001,1008,1015,1100 |
| GetDamageZones, GetHealthLevel, IsRuined, CanBeRepairedToPristine | 3_Game/Entities/Object.c:1153,1171,1219,1356 |
| Delete, IsSetForDeletion, GetHierarchyRootPlayer, GetInventory, GetCompEM | 3_Game/Entities/EntityAI.c:779,812,882,1884,3409 |
| GetIdentity, GetHumanInventory; IsUnconscious, GetItemInHands | 3_Game/Entities/Man.c:21,81; 4_World/Entities/ManBase/PlayerBase.c:3925,6733 |
| GetCargo, AttachmentCount, CreateAttachment, IsAttachment, CreateInInventory | 3_Game/Systems/Inventory/Inventory.c:138,205,209,410,876 |
| CreateInHands; CargoBase.GetItemCount | 3_Game/Systems/Inventory/HumanInventory.c:44; 3_Game/Systems/Inventory/Cargo.c:28 |
| CanBeRepairedByCrafting, HasQuantity, GetQuantity, SetWet, GetWet, TransferAgents, GetAgents | 4_World/Entities/ItemBase.c:870,3485,3490,3692,3721,3997,4003 |
| Magazine.GetAmmoCount | 4_World/Entities/ItemBase/Magazine/Magazine.c:68 |
| IsPlugged, GetPluggedDevicesCount, GetEnergy | 3_Game/tools/Component/ComponentEnergyManager.c:905,1188,1246 |
| GetAction, GetInputType, InitializeActions/GetActions | 4_World/Classes/UserActionsComponent/ActionManagerBase.c:214; ActionBase.c:230; 4_World/Entities/ItemBase.c:223,235 |
| GetValidRecipes, PerformRecipeServer, RegisterRecipe, RecipeIDFromClassname / cached list | 4_World/Plugins/PluginBase/PluginRecipesManager.c:93,317,443,470,42 |
| Repair, CalculateHealth, CanRepair, indexed repair costs | 4_World/Plugins/PluginBase/PluginRepairing.c:3,29,92,143 |
| Init, fields, InsertIngredient, AddResult, SpawnItems, ApplyModificationsResults, ApplyModificationsIngredients | 4_World/Classes/Recipes/RecipeBase.c:88,23–63,159,198,215,268,373 |
| CheckRecipe, PerformRecipe, CanDo, Do, GetID; deferred ingredient deletion | 4_World/Classes/Recipes/RecipeBase.c:479,521,551,563,568,362 |
| Native override parameter names | Same RecipeBase.c declarations above; inherited modded RegisterRecipies in 4_World/Classes/Recipes/Recipes/PluginRecipesManagerBase.c:14 |
| JSON MakeData with predeclared out args | 3_Game/tools/JsonFileLoader.c:85 |
| ClassName, typename.ToString, Class.Cast, array.Count/Clear/Find/Insert | 1_Core/proto/EnScript.c:37,78,94,380,385,394,407 |
| string.Substring/Length/Contains | 1_Core/proto/EnString.c:113,199,286 |

The existing HCGetRegisteredSalvage helper reads native cached instances in
HCCraftingRegistryAudit.c:5; it is not an invented native API. Native repair
recipe CanDo/Do anchors: CleanWeapon.c:47/53; RepairElectric.c:61/72;
RepairEpoxy.c:62/73; RepairWithSewingKit.c:61/72;
RepairWithLeatherSewingKit.c:61/72; RepairWithTape.c:63/74;
RepairWithTireKit.c:61/72; SharpenMelee.c:61/72; RepairPlanks.c:62;
RepairWithPliers.c:64/69 (all under 4_World/Classes/Recipes/Recipes/).


N1 actual full-population readback: 7,389 config classes; 234 recipe decisions
(133 preserve-native, 10 maintenance, 74 disabled holds, 17 unregistered holds);
460 actions (439 preserved, 20 maintenance, one test hold); 469 unresolved ancestry
cases; all 2,302 positive metadata links and 2,118 bindings retained. All 3,056
native source files were rehashed against both existing source censuses. No
config/script identity, array element typing or working repair pair is inferred.

Actual final verification: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover
-s tests/unit -v`: 2,502 tests, OK (one Windows-only skip);
`python3 -B -m tools.validate.bdd`: 1,299 tests, OK (same skip), 61 bound offline
scenarios; runtime acceptance NOT EXECUTED. Diagnostic + syntax/identifier checks
passed 21 tests. The report preserves initial actual failures and passing commands.

No change to README, config.cpp, HCModule, fuel policy or other modules was made.
For acceptance, compile DayZDiag and normal PBO, craft every supported variant
and check actual quantities/health/identity/cargo/attachments, run the full
maintenance queue with isolated owned fixtures and observed deletion, then test
interruption/full inventory/reconnect/two-client competition. Rifle wrap
visibility and host slots need both clients. Benchmark budgets stay provisional.
