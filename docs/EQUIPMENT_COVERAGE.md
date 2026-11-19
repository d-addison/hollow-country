# HC-22 equipment and essential supply

Source/package implementation; runtime acceptance pending. HC-22 uses native CE,
recipes, repair, cargo and medical actions. No gameplay controller is added.
The named `contextual-pilot` profile selects this policy; other named/custom
profiles retain their existing proposal behavior. `--no-datamined` removes HC-22
unused-item rows and their new-type permissions. Existing stock remains intact.

## Specification → plan → task trace

| Requirement / dependency | Implemented slice | Acceptance / follow-up |
| --- | --- | --- |
| HC-22 useful clothing/storage | 55 authored proposals; 38 admitted candidate rows; 17 named floor refusals | Every newly admitted family needs native equip/store/repair/restart |
| HC-4/9 native supply, ordinary loot about 2x | 21 additional usage-only contextual entries; existing HC-9 multiplier unchanged | Measure acquisition and world counts at 3–6 players |
| HC-21 firearm scarcity/support | Existing roster, family accounting and firearm new-type permissions unchanged | Reuse its qualification gates |
| HC-28 recovery | Reuse existing economy staged delta, receipt, backup, collision checks and rollback | Stop/restart and exact package rollback pending |
| Native water/meds/sharpening | Native vessels, purification, IV ingredients, emergency meds, Whetstone and repair-kit routes | Contents, potability, consumption, quantities and persistence pending |
| Leather/crafted/derived flags | Native flags retained; unsupported floor entries withheld | Named recipe/eligibility work remains open |
| 2,001 candidate review | Explicit queue in loot-dispositions.json; remaining count unknown | Identity-complete review is pending; these 131 decisions are not 131 qualified candidates |
| No seasonal cold / native armour | `extra_cold=0`; native insulation/protection unchanged | No new thermal requirement |

Required `docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md`
are absent in this worktree; a focused filename search found no replacements.
The dispatched HC-22 specification/plan/task brief and active owner decisions
supply this slice's design input. HC-11 owns integration into the consolidated
Banso trace; no missing experiment is marked accepted here.

## W46 follow-up: cabinet membership and building refusals (#152 / #199)

Implemented source: the runtime action now asks the existing preview RPC/cache
for a cabinet **instance** known to the server's binding service. Original sites
require a healthy economy; configured refresh sites also require their live
refresh provider. An identical decorative cabinet, including one at the same
pose, cannot borrow the cached reply. The server retains all geometry, lock,
finite-supply, revisit and journal checks before transfer. The cache and sender
throttle keep their existing caps. Positive cabinet replies expire using the
existing three-second retry interval; the last positive remains usable while
renewing so renewal cannot cancel the six-second action. A negative reply removes
the prompt. Empty replies keep the existing 60-second retry. Existing EnableInteriors/EnableSearch settings and interior_search.disable
remain the operator opt-outs. No setting, distance, work limit or module slot is
added. Two-client replication and native action acceptance remain pending.

The furnishing follow-up logs each admitted pack's named class refusal through
HCServer.HCTickWork/HCTakeFor using the existing search-maintenance consumer.
The cursor resumes after budget refusal and prints once per pack pin. It reads
the loaded class rows, so clearance/path/door failures do not disable unrelated
search or furnishing. Existing HCGetOperationalStatus continues to derive pack
readiness; no new code publishes a constant ready state. Grep:

```text
[HC Search Cabinets] site-known RPC listening; server binding required runtime=PENDING
[HC Interiors] building=<class> furnishing_refused=<reason> search=<disposition> runtime=PENDING
```

No additional layout is claimed qualified. The reviewed source database
`tools/package/interior_prop_boxes.json` contains zero Props. Native sampler
runs 110–114 and 120 and the installed template pack exist locally, but the
strict authored-theme builder still requires measured furniture boxes. Building
room/path measurements cannot substitute for those boxes or a door/stair
clearance verdict. The frozen legacy pack has one evidenced house pose and no
measured catalog. Its evidence file and the template builder/assembler are
outside W46 ownership. Pack hashes are retained rather than hand-editing an
invalid generated manifest. The per-class runtime refusal is the safe fallback;
additional furniture remains open for the placement owner.

The 17 floor proposals are **not enabled in this checkout**. The unchanged
generator rejects admitting their native crafted/deloot flags with
`HC22_UNQUALIFIED_FLOOR_FLAGS`; changing only this worker's ledger would break
all contextual-pilot generation. W46 requested ownership of the tooling and
has not received that scope extension. A concrete integration patch is staged
for the lead at `.banso-writer/loot-floor-admission.patch` (not a committed
artifact). It changes only:

1. `tools/package/datamined_items.py`: admit the exact shipped 17 proposals
   through a fixed allowlist and whole-row equality check, retaining all native
   flags. Altered/unreviewed crafted/deloot proposals still refuse.
2. `config/loot-dispositions.json`: for those 17 classes only, set
   route=native-floor, floor_admitted=true, refusal=null; retain pending-native
   eligibility and append the owner's unverified-admission evidence.
3. `tests/unit/test_datamined_items.py`: update the two old refusal/count tests
   to 55 admitted / zero refused; retain the altered-bandana flag rejection.

The proposed admission retains nominal/min 2/1 for the 13 leather proposals and
TortillaBag_Desert, and 3/1 for the three DrysackBag colours: nominal 37 / min 17
additional proposals before HC-9, total nominal 133 across 55 rows. No flag is
cleared to manufacture native floor eligibility. In particular, ordinary floor
acquisition with crafted/deloot flags remains runtime=PENDING; native testing
must establish whether another native physical route is needed. The existing
`--no-datamined` opt-out still removes the additions.

`tests/unit/test_loot_w46.py::FloorAdmissionIntegrationFixture` applies that
exact policy to a **local fixture copy** of the tool and ledger over an explicit
synthetic stock mission. It verifies 55 finite proposals, stock-identical flags,
operator opt-out, installation and byte-exact rollback. This passing fixture is
not production integration or DayZ evidence. The existing refusal tests remain
unchanged in the checkout because its production policy remains unchanged.
No source outside W46's assigned files/new Loot-prefixed sources was edited.

Native follow-up: compile with DayZDiag, boot the normal PBO/server, then use two
clients at a configured original and refresh-pilot cabinet. Confirm that only
bound cabinets offer Search storage, both clients respect custody/locks, a
restart preserves depletion, disabled search removes grants, and an unavailable
provider produces no prompt. Check furnishing refusal classes individually;
open doors and use stairs at every subsequently qualified placement. The 17
floor rows require separate acquisition, finite world-count and rollback tests
after the lead integrates their patch.

## Small inputs and accounting

[loot-dispositions.json](../config/loot-dispositions.json) records each selected
class's purpose, route, evidence, refusal and unknown native eligibility. Its
`floor_admitted` flag selects **HC-22 unused-item additions only**; false on a
stock-floor item means the native stock supplies it without a second HC-22 row.
Every `eligibility` remains `pending-native`. The parser caps the ledger at 256
entries / 1 MiB. No whole-content scanner or new census engine is introduced.

The existing whole-item workbook was read for selected class identities and
craft links, not for runtime eligibility. Snapshot SHA-256:
`2fe8154743c671182fcf5ef3be448109ce4e2b4fcd340f98a86b68ede62b6983`.
Its `inventory_eligibility=NOT_EVALUATED` and config ancestry never prove wear,
cargo, repair or an attainable recipe. The 997-entry older unspawned census is
also distinct from the plan's 2,001-candidate queue. Raw inputs stay external.

The generator reuses the essential-route parser, stock budget validator,
`datamined_items` row/config parser and the single economy delta. In the
`economy-report.json` supply section, `authored=55`, `admitted=38`,
`floor_refused=17`, `observed=0`, `extra_cold=0`; admission counts XML proposals,
not CE observations. The 38 rows total nominal 96 **before HC-9**. Counts are
configuration budgets, not simultaneous loot or supply measured in play.
`refused_by_route` distinguishes 13 unresolved routes, three native-craft routes
and one native-carrier route. `refused_by_reason` counts 16
`HC22_CRAFTED_FLOOR_UNPROVEN` and one `HC22_EVENT_CARRIER_UNQUALIFIED`.
The broader ledger separately retains twelve unresolved leather definitions,
water contents uncertainty and stock/craft supply. These are outside the
17 withheld proposals; the counts must not be presented as a complete census.

Three absent bandanas use an independent, fixed non-weapon allowlist and the
`supply_new_type_classes` manifest field. The installer compares their complete
XML against the shipped row, including flags, category, quantity and cost.
Install validates only the named new-type proposal against its disposition;
generation still checks every proposal. The installer also compares the report's
`dispositions_sha256` with the current ledger and refuses missing/different
digests with `HC22_DISPOSITIONS_HASH_MISMATCH` before any target write.
The HC-21 `new_type_classes` field remains firearm-parent permissions only.
Unregistered or rehashed altered bandana proposals refuse before writing.
Stock, extension and cross-source duplicate/case collisions remain refused.

Economy generation/installation is **repo-only**: run from the private checkout
with `config/loot-dispositions.json` available. Portable PBO handoffs and friend
bundles omit this policy ledger and do not support HC-22 economy installation.
The smaller packaging fix deliberately retains those export lists. If the ledger
is absent, HC-22 generation (including `--no-datamined`) or installation refuses
with `HC22_DISPOSITIONS_MISSING`; no target data is written. Existing non-pilot
profiles do not read this ledger. Ordinary friend-bundle installation remains
separate from the optional economy delta workflow.

## Useful outfits and storage routes

| Outfit / use | Native source and intended pieces | Repair / cargo qualification |
| --- | --- | --- |
| Civilian | Town/Village TShirt, Jeans, Hoodie, Raincoat, Sneakers; three new bandana colours | Native slots and repair-kit compatibility pending; no HC weather penalty |
| Occupational | Industrial/Farm CargoPants_Blue and WorkingGloves_Brown gain Village; WorkingBoots_Brown stock retained | Native wear, cargo capacity and leather/sewing-kit eligibility pending |
| Medical | Medic blue scrubs shirt/pants/hat gain Town; native paramedic and nurse stock retained | Full outfit acquisition, native slots and repair pending |
| Military | Native BDU/USMC woodland stock; selected coats, pilot/Gorka variants and packs below | Native armour protection unchanged; no extra armour class restored |
| Civilian storage | TaloonBag_Blue gains Town; DryBag_Blue and all three WaterproofBag colours gain Village | Actual cargo fit, wetness behavior, capacity and persistence pending |
| Native drysack | WaterproofBag colour + Rope → DrysackBag colour; no extra floor copy | Empty-container craft/decraft, ingredient consumption and restart pending |
| Repair / sharpening | LeatherSewingKit gains Hunting; Whetstone gains Industrial/Hunting alongside Farm | Native kit matching and finite tool wear pending; no new recipe |

The following table enumerates every HC-22 admitted unused-item proposal.
All purposes retain native wear/use/repair/cargo qualification as pending.

| Class | Purpose | Candidate floor context | Nominal / min |
| --- | --- | --- | --- |
| `AssaultBag_Winter` | cargo pack | Military | 1 / 0 |
| `Attack2Bag_Black` | cargo pack | Military | 1 / 0 |
| `Attack2Bag_Yeger` | cargo pack | Military | 1 / 0 |
| `Bandana_Blue` | native clothing / visual variant | Town / Village | 5 / 3 |
| `Bandana_Pink` | native clothing / visual variant | Town / Village | 5 / 3 |
| `Bandana_Yellow` | native clothing / visual variant | Town / Village | 5 / 3 |
| `BoonieHat_Winter` | native clothing / visual variant | Hunting | 2 / 1 |
| `BudenovkaHat_Gray` | native clothing / visual variant | Town / Village | 2 / 1 |
| `ColdOperationBoots_Camo` | native clothing / visual variant | Military | 2 / 1 |
| `ColdOperationBoots_Green` | native clothing / visual variant | Military | 2 / 1 |
| `ColdOperationBoots_Grey` | native clothing / visual variant | Military | 2 / 1 |
| `CoyoteBag_Winter` | cargo pack | Military | 1 / 0 |
| `CrabCan` | canned food | Coast / Village | 8 / 5 |
| `DownJacket_Blue` | native clothing / visual variant | Town / Village | 2 / 1 |
| `DownJacket_Green` | native clothing / visual variant | Town / Village | 2 / 1 |
| `DownJacket_Orange` | native clothing / visual variant | Town / Village | 2 / 1 |
| `DownJacket_Red` | native clothing / visual variant | Town / Village | 2 / 1 |
| `FilteringBottle` | water vessel; filter effectiveness/contents pending | Hunting / Medic | 1 / 0 |
| `GorkaEJacket_Winter` | native clothing / visual variant | Military | 2 / 1 |
| `GorkaPants_Winter` | native clothing / visual variant | Military | 2 / 1 |
| `HunterPants_Spring` | native clothing / visual variant | Hunting | 6 / 4 |
| `HuntingBag_Hannah` | cargo pack | Hunting | 1 / 1 |
| `HuntingJacket_Spring` | native clothing / visual variant | Hunting | 6 / 4 |
| `HuntingVest_Winter` | native clothing / visual variant | Hunting | 2 / 1 |
| `Iceaxe` | tool | Farm / Industrial | 3 / 1 |
| `PilotJacket_Black` | native clothing / visual variant | Hunting / Military | 3 / 1 |
| `PilotJacket_Brown` | native clothing / visual variant | Military / Village | 3 / 1 |
| `PilotJacket_Yellow` | native clothing / visual variant | Military / Village | 2 / 1 |
| `SkiGloves_90s` | native clothing / visual variant | Town / Village | 2 / 1 |
| `SkiGloves_Blue` | native clothing / visual variant | Town / Village | 2 / 1 |
| `SkiGloves_Red` | native clothing / visual variant | Town / Village | 2 / 1 |
| `SkiGoggles_BlackYellow` | native clothing / visual variant | Town / Village | 2 / 1 |
| `SkiGoggles_WhiteClear` | native clothing / visual variant | Town / Village | 2 / 1 |
| `SkiGoggles_WhiteDark` | native clothing / visual variant | Town / Village | 2 / 1 |
| `TortillaBag_Winter` | cargo pack | Military | 2 / 1 |
| `WinterMilitaryCoat_Brown` | native clothing / visual variant | Military | 2 / 1 |
| `WinterMilitaryCoat_DarkGrey` | native clothing / visual variant | Military | 2 / 1 |
| `WinterMilitaryCoat_Grey` | native clothing / visual variant | Military | 2 / 1 |

## Refusals and unknown eligibility

These proposals retain their authored budgets for review, but the named pilot
emits no replacement row for them. Their native stock zero nominals and flags
remain untouched; no flags are cleared to manufacture a floor route.

| Class | Retained route | Named refusal |
| --- | --- | --- |
| `LeatherJacket_Natural` | unresolved | `HC22_CRAFTED_FLOOR_UNPROVEN` |
| `LeatherJacket_Beige` | unresolved | `HC22_CRAFTED_FLOOR_UNPROVEN` |
| `LeatherJacket_Brown` | unresolved | `HC22_CRAFTED_FLOOR_UNPROVEN` |
| `LeatherJacket_Black` | unresolved | `HC22_CRAFTED_FLOOR_UNPROVEN` |
| `LeatherShoes_Natural` | unresolved | `HC22_CRAFTED_FLOOR_UNPROVEN` |
| `LeatherShoes_Beige` | unresolved | `HC22_CRAFTED_FLOOR_UNPROVEN` |
| `LeatherShoes_Brown` | unresolved | `HC22_CRAFTED_FLOOR_UNPROVEN` |
| `LeatherShoes_Black` | unresolved | `HC22_CRAFTED_FLOOR_UNPROVEN` |
| `LeatherHat_Natural` | unresolved | `HC22_CRAFTED_FLOOR_UNPROVEN` |
| `LeatherHat_Beige` | unresolved | `HC22_CRAFTED_FLOOR_UNPROVEN` |
| `LeatherHat_Brown` | unresolved | `HC22_CRAFTED_FLOOR_UNPROVEN` |
| `LeatherHat_Black` | unresolved | `HC22_CRAFTED_FLOOR_UNPROVEN` |
| `LeatherShirt_Natural` | unresolved | `HC22_CRAFTED_FLOOR_UNPROVEN` |
| `DrysackBag_Green` | native-craft | `HC22_CRAFTED_FLOOR_UNPROVEN` |
| `DrysackBag_Orange` | native-craft | `HC22_CRAFTED_FLOOR_UNPROVEN` |
| `DrysackBag_Yellow` | native-craft | `HC22_CRAFTED_FLOOR_UNPROVEN` |
| `TortillaBag_Desert` | native-carrier | `HC22_EVENT_CARRIER_UNQUALIFIED` |

LeatherPants and LeatherStorageVest (Natural/Beige/Brown/Black), plus
LeatherGloves in those four colours, retain
`HC22_LEATHER_RECIPE_UNESTABLISHED`. Crafted config/category, a public
definition or a suggestive name does not establish an active clothing recipe.
Craft-owner work must establish a real route; none is invented here.
TortillaBag_Desert retains native `deloot=1`; event/carrier identity and
acquisition remain unqualified.

The new bandanas add nominal 15 to the existing five-pattern native family
nominal 60 before HC-9. This is an explicit ordinary-clothing addition; the
twofold HC-9 pass still applies once. No firearm family budget is borrowed.
Actual bandana acquisition and outfit balance remain unmeasured.

## Water, medical and finite craft routes

`WaterBottle` remains an uncategorised native/carrier item; the existing route
checker still reports its floor route unresolved. The ledger names
`HC22_WATER_CONTENTS_UNOBSERVED`. A vessel count never counts as drinkable water.
`PurificationTablets` gains Village; Canteen retains Hunting/Military; the rare
FilteringBottle proposal retains Medic/Hunting. Read quantity, liquid type,
agents, health and actual location on the server when qualifying these routes.
Do not force clean/full contents or refill a vessel during restart.

Native `WaterBottle.EEOnCECreate` can insert cholera. The purification recipe
requires a nonempty, unfrozen vessel and consumes one tablet; it preserves
heavy-metal agents. FilteringBottle's consumption filter masks cholera and
heavy metal, and consumption damages the bottle. These are inspected source
semantics, not observed potability. Water type, other agents, bottle condition,
fill/transfer behavior, effects on consumption and restart all need native checks.

Bandage, disinfectant and iodine retain the existing native routes and profile
contexts. Charcoal gains Village; Morphine and Epinephrine gain Town. Native
TetracyclineAntibiotics and PainkillerTablets retain Medic. StartKitIV, SalineBag,
BloodBagEmpty and BloodTestKit gain Village alongside Medic. No medicine class,
medical effect or full blood bag is synthesized. Native recipes consume
StartKitIV plus SalineBag → SalineBagIV, or StartKitIV plus genuinely collected
BloodBagFull → BloodBagIV. These derived outputs keep stock floor nominal zero.
Blood typing/collection and safe administration remain native acceptance work.

`Whetstone` is the inspected native sharpening ingredient. `SharpenMelee` calls
PluginRepairing; kit matching and item health control eligibility. This work
adds supply contexts, never a universal-sharpening rule. Dry-container crafting
consumes real ingredients; neither its output nor a fresh cargo copy is added
by HC-22.

## Installed API evidence

All paths below are relative to
`~/.cache/hollow-country/native-scripts/scripts-1.30.164289/`.
No new Enforce API call is authored by this content/tooling slice.

| Key | Inspected declarations / limits |
| --- | --- |
| N2 | `4_World/Entities/ItemBase.c:3319` SetQuantity default disallows client; `:3871` SetLiquidType; `:4003` GetAgents; `:4140` CanPutInCargo; `:4154` CanPutAsAttachment. InventoryLocation's native validity/type/parent declarations are in `3_Game/Systems/Inventory/InventoryLocation.c:42-60`; config ancestry alone is insufficient. |
| N2 water | `4_World/Entities/ItemBase/Edible_Base/Bottle_Base/WaterBottle.c:60-79` CE/debug agent insertion; `FilteringBottle.c:61-77` agent filtering and consumption damage. |
| N3 | `4_World/Classes/Recipes/Recipes/CraftDrysackBag.c:23-55` ingredients, consumed inputs, colour-derived result and empty-bag condition; `PluginRecipesManagerBase.c:160` registration. `4_World/Classes/UserActionsComponent/Actions/Continuous/ActionDeCraftDrysackBag.c:37-54` server-side empty-container decraft. |
| N3 repair | `4_World/Plugins/PluginBase/PluginRepairing.c:92-128` health/kit checks; `4_World/Classes/Recipes/Recipes/SharpenMelee.c:27,67-94` Whetstone plus native repair handler; `RepairWithSewingKit.c:61-66` and `RepairWithLeatherSewingKit.c:61-66` item-specific crafting eligibility. |
| N3 meds | `4_World/Classes/Recipes/Recipes/PurifyWater.c:27-44,70-78`; `CraftSalineBagIV.c:27-46`; `CraftBloodBagIV.c:27-46`; `PluginRecipesManagerBase.c:91-105,166-167` native registrations. |
| N10 | `3_Game/CE/CentralEconomy.c:310` SpawnAnalyze and `:394` SpawnLoot are diagnostic/native spawning declarations, not an eligibility getter or proof of normal CE acquisition. No new spawning call is introduced. Crafted/deloot flags stay unchanged. |

## Lead integration (HC-62; reserved shared files)

No HCModule, registration block or addon config edit is needed. The content
boot receipt is **proposed and not yet implemented/observed in this worktree**.
The lead must make this exact integration through its bounded manifest path:

1. In `mods/HollowCountry/scripts/4_World/Core/HCServer.c`, after content manifest
   admission, feed one `HC-22 supply` entry to the HC-62 content contributor.
   Supply `economy-report.json`'s `supply` values and exact admitted delta/report,
   `config/loot-dispositions.json`, profile and datamined-row SHA-256 values.
   Check the selected/installed manifest before reporting admission; a repository
   file or static constant does not establish that CE loaded it.
2. In lead-owned
   `mods/HollowCountry/scripts/4_World/Operations/HCOperationalContributors.c`
   (not yet present at this base), add the fixed content entry and one bounded
   diagnostic. Expected candidate fields for this source are:
   `[HC Plan] HC-22 supply admitted=38 floor_refused=17 extra_cold=0 state=on authored=55 observed=0 runtime=PENDING`.
   Off (`--no-datamined`) must report `state=off admitted=0 floor_refused=0`.
   Missing/drifted manifest must report `state=refused admitted=0` with a named
   manifest/hash refusal. Do not hard-code these counts as native observations.
   Cache through HC-1 status; no recurring scan, per-content module or CE success
   claim. Reset the cached content contribution on stop/restart.
3. HC-11 should link HC-22's completed source tasks and still-pending native
   checks/recipe refusals into its consolidated spec/plan/tasks. No HC-22 file
   outside this package was edited. Existing essential-route CSV is unchanged.
4. Round 2 appends the lead-authorized `!/docs/EQUIPMENT_COVERAGE.md` exception
   to `.gitignore` so this document is tracked. Git metadata is read-only in
   this worker run; the Banso writer owns the eventual commit.

## Native acceptance still required

Use exact-source DayZDiag compile/boot, then normal signed PBO/server with the
same source/PBO/mission/config/dependency hashes. Inspect the integrated
`[HC Plan] HC-22 supply` receipt and all script/CE errors. A diagnostic line is
content admission evidence only. Run an off-path install/restart/rollback too.

Sample every admitted family: native floor acquisition, pickup/equip/unequip,
real cargo storage, compatible repair, finite tool/ingredient consumption,
stop/restart persistence and no duplicated item identity or cargo. Include
bandana models/slots, coats, pilot/Gorka/ski/hunting clothes, bags, CrabCan,
FilteringBottle and Iceaxe. Check civilian, occupational, medical and military
outfits in their listed contexts; no armour or temperature changes are expected.
Use two clients for inventory presentation and simultaneous custody checks.

Actually fill/purify/drink each vessel, observe the liquid/agents/quantity and
native effects; repeat after restart. Find medical ingredients and Whetstone
through their native routes, craft both IV types and a drysack, repair a damaged
compatible item and retain quantity/health readback. Neither a synthetic fixture,
a native class export nor a debug-spawned item establishes ordinary acquisition.
The full candidate review, target-load budget and production promotion remain
pending. Distances added by HC-22: **none**.

## Offline RED / GREEN record

Round 1 added no persistent test module under its original content-only brief. The
existing in-memory generator/parser fixtures and a focused executable assertion
were used. This exact command failed before implementation with
`AssertionError: HC-22 missing bandana floor admissions` (exit 1), and passed
after implementation with `HC-22 supply admission GREEN` (exit 0):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -c 'import json; from pathlib import Path; from tools.package import economy as e; f=e.generate(Path("/mnt/d/HollowCountryLocal/backups-v1/dayzOffline.chernarusplus.stock"),json.loads(Path("mission/hollow-country/economy-profiles/contextual-pilot.json").read_bytes())); names={n.get("name") for n in e.xml(f["ce/types.xml"],"types")}; assert {"Bandana_Blue","Bandana_Pink","Bandana_Yellow"} <= names, "HC-22 missing bandana floor admissions"; assert not {"DrysackBag_Green","LeatherJacket_Natural","TortillaBag_Desert"} & names, "HC-22 unqualified floor flags"; print("HC-22 supply admission GREEN")'
```

Focused regression command:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_datamined_items test_economy_contract test_loot_routes test_firearms_roster test_hc_firearm_families test_local_test_session -v
```

Result: **329 tests, OK**. Installed-config checks are static evidence; the
remaining fixtures are explicitly synthetic. A separate in-memory check reused
`test_datamined_items.stock_mission` to confirm counts `(55,38,17,0,0)`, byte-exact
install/rollback, disabled admission and rejection of rehashed new-bandana
nominal/quantity/cost drift before writes. Result: GREEN.

Required source checks:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_script_syntax test_enforce_locals test_script_identifiers test_hygiene -v
```

Result: **53 tests, OK**. These checks do not establish DayZ behavior.

## Round 2 behavioral coverage and packaging review

Review trace: HC-22 / P2-1, P3-1, P3-2 and P3-4.

- [x] P2-1: persistent stdlib behavioral coverage in
  `tests/unit/test_datamined_items.py::UsefulSupply`, using the explicitly
  synthetic `stock_mission` fixture. Covers all three bandanas, all 17 named
  floor refusals, rehashed nominal drift, stock spelling/case collisions,
  unreviewed permissions, missing decisions, crafted/deloot flags and legacy
  non-pilot behavior. Rejected installs retain exact target bytes.
- [x] P3-1: validate the named new-type proposal only; require the report's
  disposition digest to match the current repository ledger. Tampered/null/
  missing digests, a missing supply report and changed ledger bytes refuse.
- [x] P3-2: retain repo-only economy generation/install with the named
  `HC22_DISPOSITIONS_MISSING` refusal. An isolated subprocess imports tools
  from a synthetic exported friend bundle and verifies refusal before writes.
  No BUNDLE_TOOLS or PBO helper-list changes are required for this choice.
- [x] P3-4: report `floor_refused`, `refused_by_route` and `refused_by_reason`;
  native-craft/carrier routes are no longer counted as unresolved routes.
  The disabled pilot reports zero floor admissions/refusals and empty counts.
- [ ] Native acceptance, content-status integration and target-load budgets
  remain pending as specified above. Source tests do not accept these tasks.

RED was recorded before production edits with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_datamined_items.UsefulSupply tests.unit.test_friend_bundle.FriendBundleTests.test_exported_economy_install_refuses_missing_repo_only_supply_ledger -v
```

The corrected-fixture RED run executed 13 tests and ended
`FAILED (failures=4, errors=5)`. Actual failure lines included:

```text
ValueError: HC22_MISSING_DISPOSITION: SyntheticUnrelatedProposal
AssertionError: ValueError not raised
FileNotFoundError: [Errno 2] No such file or directory: .../absent-ledger.json
AssertionError: 'unresolved' unexpectedly found in ...
ImportError: cannot import name 'firearms' from 'tools.package' (unknown location)
```

These respectively exposed whole-proposal install validation, absent digest
checking, missing ledger diagnostics, mislabeled counts, and the exported
installer reaching an unavailable optional dependency before ledger refusal.
The second digest subcase also encountered state left by the first unexpectedly
successful install; it is not claimed as an independent product failure.
No production check was temporarily disabled. Existing admission/refusal
safeguards passed on first meaningful execution. The first draft of the tests
incorrectly expected nominal 3 instead of the shipped 5, and initially generated
a collision fixture after adding the stock bandana; both test-fixture mistakes
were corrected before this recorded RED run. Those are not product defects.

After the smallest production changes, the same command returned
`Ran 13 tests` / `OK`. The exported test also caught exception chaining exposing
`FileNotFoundError`; the named refusal now suppresses that irrelevant traceback.
Later missing-report/digest and off-count subcases passed on first execution.

Final requested regression command:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_datamined_items test_economy_contract test_firearms_roster test_loot_boost test_loot_routes test_package test_package_manifest test_friend_bundle -v
```

Result: `Ran 280 tests` / `OK (skipped=1)`. The skipped test is the native
Windows PowerShell smoke-helper check, which belongs to Windows CI.

Required source/hygiene regression command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_script_syntax tests.unit.test_enforce_locals tests.unit.test_script_identifiers tests.unit.test_hygiene -v
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.validate.hygiene
```

Results: `Ran 53 tests` / `OK`; repository report `valid=true`, `errors=[]`.
Framework reused: existing bounded row/disposition parsers, CE extension and
collision checks, immutable manifest hashes, staged delta, receipt and byte-exact
rollback. No runtime framework or engine API was added; no new distances.

Additional dependent-reader checks (required by the shared worker brief):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_firearm_families tests.unit.test_friend_install tests.unit.test_gameplay_delta tests.unit.test_local_test_session tests.unit.test_optional_ce_composition tests.unit.test_optional_gun_scale tests.unit.test_snafu_optional tests.unit.test_tactical_flava_optional tests.unit.test_v2_optional_overlays tests.unit.test_ce_coverage tests.unit.test_enforce_formula_complexity -v
```

This invocation ran 544 entries: 543 tests passed and one module-loader entry
failed with `ModuleNotFoundError: No module named 'test_firearms_roster'` because
`test_hc_firearm_families` uses a top-level fixture import. This was a command
setup error, not a behavioral failure. The correctly configured focused rerun:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_firearm_families -v
```

returned `Ran 1 test` / `OK`. No source change was needed for that rerun.
The initial aggregate command is honestly recorded as `FAILED (errors=1)`;
there are no remaining failed behavioral checks.

Commit message supplied to the Banso writer in `.banso-writer/commit-message`:
`fix(economy): test HC-22 supply and bind installs to ledger policy`.
No staging, commit or publication was performed by this worker.

## W46 verification record

RED before cabinet implementation:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_loot_w46 -v
```

Actual failure: `AttributeError: type object 'HCSearchPreviewSites' has no attribute 'PilotKey'`;
`Ran 4 tests`, `FAILED (errors=4)`. Before the refusal reporter was authored,
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_loot_w46.InteriorCoverage -v`
failed with `AssertionError: False is not true : missing bounded per-building furnishing refusal reporter`.
The subsequent behavioral reporter fixture verifies cursor resumption, covered-row
skips, print-once behavior and pack-revision reset.

GREEN final focused source/readers/common-brief command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_loot_w46 tests.unit.test_search_preview_sites tests.unit.test_search_economy_houses tests.unit.test_v1_combined_rpc tests.unit.test_enforce_lint tests.unit.test_script_syntax tests.unit.test_enforce_locals tests.unit.test_script_identifiers tests.unit.test_hygiene -v
python3 -B -m tools.validate.enforce_lint --no-native
```

The isolated lead patch was also applied with `patch -p1` under a temporary
directory, then its updated `UsefulSupply` suite ran against copied tool/ledger
modules: `Ran 12 tests`, `OK`. No worker-owned or unowned production file was
changed by that rehearsal. This is additional fixture coverage, not a claim
that the 17-route integration has landed.

A renewal regression was caught before its fix with:
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_loot_w46.CabinetSites.test_pilot_request_round_trip_is_instance_bound_and_expires -v`.
Actual RED: `AssertionError: False is not true : refreshing membership must not cancel a six-second search`.
The corrected cache retains its positive membership during renewal and drops it
on a negative reply; the fixture covers the full six-second action window.

Final W46 results: the focused command above ran **149 tests, OK**;
`enforce_lint: pass findings=1 new=0 stale=0 native=no`.
No setting was changed, so settings-registry validation was not required.
No new mission data file, module slot or shared package registration is needed.
Nothing observed in DayZ yet.
