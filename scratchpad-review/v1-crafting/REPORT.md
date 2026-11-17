# V1 crafting and salvage — #17 / #52

2026-11-17. Source implementation and offline verification only. No DayZ,
DayZDiag, Wine, PowerShell, client join, PBO build or native craft was run.
Runtime acceptance and production enablement remain pending.

## Result and scope

Extended the existing N1 audit rather than creating another inventory census.
Completed the four beige garment shortlist entries: jacket and pants were
already implemented; gloves and hat now join the registered one-panel family.
The final HC set is eight registered `HCSalvageRecipe` subclasses, 22 exact
source alternatives and 588 source/tool combinations. Registration order/count
remain identical on both peers. Native crafting, camouflage and repair systems
supply the other supported uses; there are no duplicate ghillie or repair recipes.

Added explicitly invoked N2/N3 diagnostic source. It observes metadata and real
manager routes and optionally executes the ten native maintenance recipes on
new, owned fixtures. No constructor, startup hook, module change, RPC or timer
invokes it. A caller must supply/persist the complete pinned queue, poll cleanup
and enforce an external process deadline. This file is not a completed N4 runner.

The worktree lacks the ignored specification/research inputs. Required design
documents were read from `/code/dayzsa_mods/docs/` and the existing experiment
from `/code/dayzsa_mods/research/experiments/`. The experiment is preserved in
this worktree with a **V1 implemented set** appendix. Active user decisions take
precedence over the earlier HOLD decisions. No shared `docs/`, README, config,
HCModule, fuel policy, other module, Git index or Git metadata was edited.

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

## N1 complete decision readback

`build_audit` retains original source records and adds compact index-linked
decisions. Registered native uses are preserved, ten maintenance recipes and
twenty action declarations selected for qualification, disabled/unregistered/test
holds retained, material conversion UNKNOWN and inventory eligibility unevaluated.
Only UNKNOWN-unresolved-ancestry records enter the unresolved ancestry list;
ordinary non-action script classes are not mislabelled unresolved.

Actual local readback admitted the existing four-root native035 manifest and
all fifteen chunks, then rehashed all 3,056 native files against **both** source
census manifests. A second admission checked expected manifest SHA-256
`4ae9b31bb9d2e090a9afeaaaa13db008d5cd1fc035b11929a2ae4c2e5c27d8e8`
and rehashed all sixteen consumed files. EnumerationComplete=true;
FullCoverage=false because unverified array elements/variant fields remain.
Shared source manifest:
`b7ed9fa47f1285f8aa436c18fc9c8681a7e017b2441a7923c8eae0f2a019af33`.

| Retained population | Actual result |
| --- | --- |
| Config classes | 7,389: 1,510 positive-list, 1,293 nonpositive-only, 53 empty, 4,533 absent repair arrays |
| Recipes | 234: 133 preserve-native + 10 maintenance + 74 disabled holds + 17 unregistered holds |
| Action candidates | 460: 439 preserve-native + 20 maintenance + 1 test-only hold |
| Unresolved possible action ancestry | 469 |
| Positive kit/target metadata links | 2,302 across nine observed kit IDs; still not native eligibility |
| Bindings / recipe references | All 2,118 / 2,344 retained; all unresolved/conditional evidence retained |
| Source files / bytes | 3,056 / 13,952,124; full read-only file rehash |
| Qualification | runtime_qualified=false; production_enablement=false |

Input artifact locations remain local: native035 under
`experiments/compile-035-four-root-audit/.../native-item-audit-all/`, recipes
`item-review-035-full-20261116/crafting-census.json`, actions
`action-audit-full-r2-20261116/action-census.json`, all beneath the native cache.
No complete export or source census is copied into this commit.

## Diagnostic invocation and limits

Caller creates `HCItemUtilityDiagnostic`, calls
`Begin(totalRows, true, true, fixturePosition, executeRepairs, maxMillis, maxBytes)`
only on an empty disposable server/profile, then submits fresh request/observation
DTOs in sequential Index order. A request includes exact ConfigRoot, ItemClass,
KitIndex (-1 metadata; 0..8 kits; 9 plank; 10 pliers; 11 Fabric) and explicit
CreationReviewed. Persist only rows for which ObserveNext returns true. Retry
the same pending index after cleanup; never reuse a captured row. Call Stop on
abort and keep PollCleanup/Summary observations until native deletion confirms.
Do not discard a live diagnostic or substitute a delete request for confirmation.

Boundaries: one active diagnostic, 1..262,144 supplied rows, maximum 60 seconds
per instance, 128 KiB..64 MiB byte allowance (default 16 MiB), <=128 repair-array
values, <=64 ancestors, <=32 zones, <=512 recipe/action-map entries, twenty
action observations and <=16,000 serialized string units per row. Byte accounting
uses a conservative UTF-8 bound plus framing. Budget expiry conserves Remaining
and emits a partial summary. No silent pilot/sample cap replaces a queue.

Creation has a reviewed concrete allowlist plus caller review; every other
supplied class still emits metadata with creation pending. Scope 0/1 and unsafe
or unreviewed definitions are never spawned. Fixtures are one identityless native
Mirek actor, one MountainBag_Blue, one target in hands and one tool in bag, at most
four explicit live allocations. Raw allocations are counted and retained even
after failed casts; only owned allocations are deleted. No existing player/item
is accepted. Tests require empty-server opt-in; an isolated deployment must also
prevent clients joining during the external run.

The nine kits are WeaponCleaningKit, SewingKit, LeatherSewingKit, Whetstone,
DuctTape, TireRepairKit, ElectronicRepairKit, EpoxyPutty and Blowtorch. The ten
recipe names are CleanWeapon, RepairElectric, RepairEpoxy, RepairWithSewingKit,
RepairWithLeatherSewingKit, RepairWithTape, RepairWithTireKit, SharpenMelee,
RepairPlanks and RepairWithPliers. Pliers/Plank keep native special semantics;
Blowtorch/Fabric are action routes, not invented generic repair recipes.

Acquisition calls real object eligibility methods, actual ActionManagerBase
registry/item input maps, actual cached recipe lookup and GetValidRecipes.
CanRepairObserved=false preserves UNKNOWN when PluginRepairing is unavailable
or the route is special. Action membership is labelled condition-unexecuted;
missing registry is pending. No second ActionConstructor registry is fabricated.
Native ItemBase.RemoveAction logic (in ItemBase.c:295–297) reads the local
player; a headless initialization failure must remain pending, never bypassed.

Execution is opt-in and limited to discovered, cached, zero-result maintenance
recipes using the actual manager PerformRecipeServer, with owned target/tool
and a living conscious fixture actor. The source initializes only newly allocated
target health to 40%, snapshots target/tool global and zone health, quantity,
wetness, agents, cargo/attachments, magazine ammo and energy, records one attempt
before native entry and records same-handle observations afterward. It does not
execute vehicle/deployed-zone/blowtorch actions or assert a native repair succeeded.

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

## Actual RED / GREEN

All test fixtures/adapters are explicitly synthetic. The adapter executes
authored method bodies; it does not compile Enforce or reproduce engine state.

1. N1 decision test first failed with `KeyError: 'decision_table'`. After the
   decision table was implemented, `python3 -B -m unittest
   tests.unit.test_item_utility -v` passed 27 tests. A follow-up non-action
   case actually failed with `['Unresolved'] != ['OrdinaryItem', 'Unresolved']`;
   narrowing to the exact unresolved status restored the same 27-test GREEN.
2. `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_v1_crafting -v`
   initially failed twice: `False is not true` for LeatherGloves_Beige and
   LeatherHat_Beige. Adding those two exact alternatives made it pass; existing
   family/completion/conservation checks exercise them too.
3. Initial diagnostic tests actually errored with missing
   `HCItemUtilityDiagnostic.c` (six errors). After source authoring, six tests
   passed. Adapter ++/Find support fixes were harness issues, not engine results.
4. `...test_v1_crafting_diagnostic.UtilityDiagnosticTests.test_dead_unconscious_or_deleting_diagnostic_actor_cannot_execute -v`
   failed three subcases with `True is not false`; adding the actor-state guard
   passed. `...test_missing_repair_manager_and_special_routes_are_unknown_not_negative -v`
   failed `missing authored method: ObserveRepairEligibility`; implementing the
   observed/unknown distinction passed.
5. The first discovery run ran 2,500 tests with one failure/one skip: the old
   all-Crafting source assertion banned diagnostic CreateInInventory too. The
   assertion now checks the gameplay salvage source. Focused recovery/audit/
   diagnostic tests then passed 97 tests (before the last two diagnostic cases).
6. Diagnostic plus syntax/identifier command:
   `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_v1_crafting_diagnostic tests.unit.test_script_identifiers tests.unit.test_script_syntax -v`
   passed **21 tests**. Includes real opt-in gates, queue and byte/time bounds,
   clock wrap, replay, actor/ownership guards, registry observations, missing
   repair plugin, and cleanup accounting using synthetic native boundaries.

Final commands and actual output:

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v
Ran 2502 tests in 107.768s
OK (skipped=1)

python3 -B -m tools.validate.bdd
Ran 1299 tests in 55.677s
OK (skipped=1)
Bound offline scenarios: 61; runtime acceptance: NOT EXECUTED

git diff --check
(exit 0; no output)
```

The single skipped helper requires native Windows PowerShell execution and
belongs to Windows CI. No Windows or game process was started. Final logs are
local `/tmp/hc-v1-crafting-final-unittest.log` and
`/tmp/hc-v1-crafting-final-bdd.log`; the important results are retained here.

## Native local-server checklist / remaining gaps

| Task / requirement | Source or offline disposition | Required native run |
| --- | --- | --- |
| N1 | Complete executable decision register over supplied full census | Re-pin fresh export/censuses before qualification. |
| N2/N3 | Explicit bounded metadata, object, action-map, recipe discovery and optional in-place execution source authored | DayZDiag compilation; real supplied-queue acquisition; fresh profile; verified actor/kit placement and cleanup. Unreviewed creation remains pending per class. |
| N4 | Outside owned scope; no runner authored | Implement secure admission, queue generation, exact invocation receipts, persistence, external deadline and process ownership in tools/setup; never infer total coverage from Summary.Complete alone. |
| N5 | Full 2,302 positive-reference denominator retained | Read back every candidate native verdict/pending reason; preserve 49 surplus-cost anomalies and all unknown element kinds. |
| N6 / CRF-001–007 | Authored guards, quantities, failures and conservation offline-tested | Below: actual mutation/failure/state assertions. Current source initializes a 40% empty fixture only; ruined/exhausted/interruption/loaded-zone variants remain native qualification work. |
| N7 / #17 / #52 acceptance | PENDING | Normal PBO/server, signed clients and two-client contention; target load 3–6 players. No production acceptance or benchmark result here. |

In-game procedure for the local-server run:

1. Compile the exact source with installed 1.30.164289 DayZDiag, then package
   and load the normal mod on server and both clients. Confirm all eight recipe
   IDs/order are identical and disabled server crafting cannot commit.
2. For each of the 22 exact sources and its legal tools, craft once with an
   empty loose owned item. Check exact output stack quantities/co-products,
   source removal and the **same tool handle**, charged health and unchanged
   quantity. Specifically cut beige gloves and hat: exactly one leather each.
   Test all 36 cutting alternatives across the family; no inferred child types.
3. Equip each garment first, insert cargo into jacket/pants/vest, attach a
   grenade to a vest; no recipe may consume the equipped/nonempty source.
   Repeat with wrong owner, ground/corpse source, attachments on tool, pending
   deletion, dead/unconscious actor and tools at wear-1, wear, wear+epsilon.
4. Confirm ordinary recipes reject ruined items. Ruin an empty WoodenCrate and
   salvage it with health>20 tool: one plank + two nails at 10% health, crate
   destroyed. A healthy crate uses its native dismantle path instead. Rebuild
   attempts must require additional real materials; no pristine crate appears.
5. Plug CableReel into power and separately connect a consumer. Both block
   recovery; unplug all connections to obtain exactly one wire unit. No source
   energy/component survives as a duplicated item.
6. Craft Netting from CamoNet, combine Netting 1 + BurlapStrip 2 using the
   already native ghillie recipe, then attach GhillieAtt_Tan only to actual
   supported hosts. Both clients must see the same wrap, condition and removal;
   no new green appearance/unsupported slot is expected.
7. Exercise native supported repair pairs above with damaged targets and real
   kit depletion. Check target/tool handles, cargo, attachment identities,
   ammo, energy, agents/wetness and damage zones. Hat + leather kit must remain
   excluded by native policy. Test plank/pliers/Fabric/blowtorch separately,
   including deployed selections, fuel use and interruption cleanup.
8. Interrupt crafts, fill inventory, disconnect/reconnect, delete/move a source
   during action, and have two clients compete for the same source/tool. Capture
   server and both client results: at most one complete set, no consumed source
   on failed allocation, no duplicate loot or client-owned committed state.
9. Separately invoke the diagnostic on the disposable locked server, starting
   with executeRepairs=false; stream the **whole** N1-derived queue. Record every
   metadata-only/unsafe/missing registry/cast/budget result and conserved pending
   denominator. Then execute approved maintenance fixture routes. Confirm all
   owned objects actually disappear before accepting cleanup. An empty registry,
   stalled callback, unobserved action or PARTIAL receipt cannot pass.

Needed changes outside owned scope are only the N4 external diagnostic runner
and later evidence/status updates in shared docs/README after actual acceptance.
No HCModule/config startup registration is requested for this diagnostic.

## Files

- `tools/audit/item_utility.py`: index-linked executable N1 decisions.
- `tests/unit/test_item_utility.py`: retained population/unknown/hold decisions.
- `mods/HollowCountry/scripts/4_World/Crafting/HCSalvageRecipe.c`: two exact
  beige garment additions to the existing registered subclass.
- `tests/unit/test_crafting_families.py`, `test_crafting_contract.py`,
  `test_v1_crafting.py`: full alternative behavior and explicit conservation.
- `mods/HollowCountry/scripts/4_World/Crafting/HCItemUtilityDiagnostic.c` and
  `tests/unit/test_v1_crafting_diagnostic.py`: N2/N3 source and synthetic behavior.
- Ignored `research/experiments/EXP-full-item-scope-decisions.md`: appended
  V1 implementation, evidence and pending-task disposition.
- This report; `.banso-writer/commit-message` selects the external writer's
  commit message. No Git write was performed by this worker.
