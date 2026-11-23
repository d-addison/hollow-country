# HC-22 equipment and essential supply

Source/package implementation; runtime acceptance pending. HC-22 uses native CE,
recipes, repair, cargo and medical actions. No gameplay controller is added.
The named `contextual-pilot` profile selects this policy; other named/custom
profiles retain their existing proposal behavior. `--no-datamined` removes HC-22
unused-item rows and their new-type permissions. Existing stock remains intact.

## Specification → plan → task trace

| Requirement / dependency | Implemented slice | Acceptance / follow-up |
| --- | --- | --- |
| HC-22 useful clothing/storage | 59 authored and admitted candidate rows; zero floor refusals | Every newly admitted family needs native equip/store/repair/restart |
| HC-4/9 native supply, ordinary loot about 2x | 21 additional usage-only contextual entries; existing HC-9 multiplier unchanged | Observe acquisition and world counts with one client; capacity remains provisional |
| HC-21 firearm scarcity/support | Existing roster, family accounting and firearm new-type permissions unchanged | Reuse its qualification gates |
| HC-28 recovery | Reuse existing economy staged delta, receipt, backup, collision checks and rollback | Stop/restart and exact package rollback pending |
| Native water/meds/sharpening | Native vessels, purification, IV ingredients, emergency meds, Whetstone and repair-kit routes | Contents, potability, consumption, quantities and persistence pending |
| Leather/crafted/derived flags | 21 exact floor overrides clear crafted; TortillaBag_Desert also clears deloot | Named recipe/eligibility work remains open |
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
the prompt. Empty replies keep the existing 60-second retry while resident.
At cache pressure, a bounded sweep reclaims a completed negative reply or an
unsent empty entry so an unseen cabinet can request; in-flight requests and
positive sites remain resident. Existing EnableInteriors/EnableSearch settings
and interior_search.disable
remain the operator opt-outs. No setting, distance, work limit or module slot is
added. Single-client replication and native action acceptance remain pending.

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

The 21 floor proposals are enabled in the integrated `contextual-pilot`
generator. Exactly the reviewed DrysackBag colours, 13 leather rows, four
LeatherGloves colours and TortillaBag_Desert emit `crafted=0`; TortillaBag_Desert also emits `deloot=0`.
The source manifest retains stock flags for stock validation. Other profiles
retain those flags, and unrelated proposals cannot obtain this exception.
The installer compares the entire flags node against stock with only those
specific changes, retaining count flags, quantities, cost and other protected
fields. It does not add flags to the general mutable-field set.

The 21 rows retain nominal/min 2/1 for the 13 leather rows and TortillaBag_Desert,
and 3/1 for the three DrysackBag colours, plus 1/1 for four LeatherGloves colours:
nominal 41 / min 21 before HC-9.
All 59 proposals total nominal 137 before HC-9. Generation and installation
remain repo-only, using the staged economy workflow below. Regenerate an older
staged delta to include these floor flags. `--no-datamined` removes the additions.
Stock files are never rewritten, and rollback restores the mission byte-exactly.

`tests/unit/test_loot_w46.py::FloorAdmissionIntegration` runs the integrated
generator over an explicit synthetic stock mission. It checks all 59 rows,
exact flag changes, finite budgets, opt-out, installation and byte-exact rollback.
It no longer rewrites an obsolete copy of generator source. These tests establish
package behavior only; ordinary CE acquisition remains runtime=PENDING.

Native follow-up: compile with DayZDiag, boot the normal PBO/server, then use one
client at a configured original and refresh-pilot cabinet. Confirm that only
bound cabinets offer Search storage, the connected client respects custody/locks, a
restart preserves depletion, disabled search removes grants, and an unavailable
provider produces no prompt. Check furnishing refusal classes individually;
open doors and use stairs at every subsequently qualified placement. The 21
floor rows require separate acquisition, finite world-count and rollback tests
using the regenerated overlay. Bundle verification is offline evidence only;
DayZDiag and normal PBO/server acceptance remain pending.

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
`economy-report.json` supply section, `authored=59`, `admitted=59`,
`floor_refused=0`, `observed=0`, `extra_cold=0`; admission counts XML proposals,
not CE observations. The 59 rows total nominal 137 **before HC-9**. Counts are
configuration budgets, not simultaneous loot or supply measured in play.
`refused_by_route` and `refused_by_reason` are empty for these proposals.
The broader ledger separately retains eight unresolved leather definitions,
water contents uncertainty and stock/craft supply. These counts are not a
complete census and do not accept missing native experiments.

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
bundles omit this policy ledger and do not support standalone HC-22 economy
installation. The bundle builder regenerates the contextual-pilot delta with the
release firearms roster in the private checkout, after rolling back the CE stack
on scratch. It exports the fresh pre-boost XML and matching core registration,
and refuses generation failures or an exported types mismatch. The friend
installer merges this overlay and applies HC-9 once. The export lists still omit
the policy ledger. If the ledger is absent, HC-22 generation (including `--no-datamined`) or installation refuses
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
| Native drysack | WaterproofBag colour + Rope → DrysackBag colour; finite floor rows also admitted | Empty-container craft/decraft, ingredient consumption and restart pending |
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
| `LeatherJacket_Natural` | native clothing / visual variant | Hunting / Village | 2 / 1 |
| `LeatherJacket_Beige` | native clothing / visual variant | Hunting / Village | 2 / 1 |
| `LeatherJacket_Brown` | native clothing / visual variant | Hunting / Village | 2 / 1 |
| `LeatherJacket_Black` | native clothing / visual variant | Hunting / Village | 2 / 1 |
| `LeatherShoes_Natural` | native clothing / visual variant | Hunting / Village | 2 / 1 |
| `LeatherShoes_Beige` | native clothing / visual variant | Hunting / Village | 2 / 1 |
| `LeatherShoes_Brown` | native clothing / visual variant | Hunting / Village | 2 / 1 |
| `LeatherShoes_Black` | native clothing / visual variant | Hunting / Village | 2 / 1 |
| `LeatherHat_Natural` | native clothing / visual variant | Hunting / Village | 2 / 1 |
| `LeatherHat_Beige` | native clothing / visual variant | Hunting / Village | 2 / 1 |
| `LeatherHat_Brown` | native clothing / visual variant | Hunting / Village | 2 / 1 |
| `LeatherHat_Black` | native clothing / visual variant | Hunting / Village | 2 / 1 |
| `LeatherShirt_Natural` | native clothing / visual variant | Hunting / Village | 2 / 1 |
| `LeatherGloves_Natural` | native clothing / visual variant | Hunting / Village | 1 / 1 |
| `LeatherGloves_Beige` | native clothing / visual variant | Hunting / Village | 1 / 1 |
| `LeatherGloves_Brown` | native clothing / visual variant | Hunting / Village | 1 / 1 |
| `LeatherGloves_Black` | native clothing / visual variant | Hunting / Village | 1 / 1 |
| `DrysackBag_Green` | cargo pack | Coast / Village | 3 / 1 |
| `DrysackBag_Orange` | cargo pack | Coast / Village | 3 / 1 |
| `DrysackBag_Yellow` | cargo pack | Coast / Village | 3 / 1 |
| `TortillaBag_Desert` | cargo pack | Military | 2 / 1 |

## Floor flag overrides and unknown eligibility

The 21 reviewed rows use ordinary floor flags in the candidate overlay. Only their
`crafted` flag may clear; only TortillaBag_Desert may also clear `deloot`.
The other four count flags remain stock-identical. No name-based exception
exists in the route audit: it counts only usages whose actual XML flags permit
floor supply. Multiple stock/overlay definitions still contribute only common
routes because CE merge order remains unobserved.

LeatherPants and LeatherStorageVest (Natural/Beige/Brown/Black) retain
`HC22_CRAFTED_CATEGORY_NO_RECIPE`. LeatherGloves in those four colours are
admitted floor proposals with nominal/min 1/1 each. Crafted config/category, a
public definition or a suggestive name does not establish an active clothing recipe.
Craft-owner work must establish a real route; none is invented here.
TortillaBag_Desert emits `deloot=0` in the named pilot overlay; actual floor
acquisition and finite replenishment remain unqualified.

The new bandanas add nominal 15 to the existing five-pattern native family
nominal 60 before HC-9. This is an explicit ordinary-clothing addition; the
twofold HC-9 pass still applies once. No firearm family budget is borrowed.
Actual bandana acquisition and outfit balance remain unmeasured.

## Water, medical and finite craft routes

`WaterBottle` remains an uncategorised native/carrier item; the existing route
checker still reports its floor route unresolved. The ledger records
`native-carrier` with no refusal; water contents remain unobserved. A vessel
count never counts as drinkable water.
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
| N10 | `3_Game/CE/CentralEconomy.c:310` SpawnAnalyze and `:394` SpawnLoot are diagnostic/native spawning declarations, not an eligibility getter or proof of normal CE acquisition. No new spawning call is introduced. Only the 21 reviewed HC-22 floor rows override crafted/deloot as described above. |

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
   `[HC Plan] HC-22 supply admitted=59 floor_refused=0 extra_cold=0 state=on authored=59 observed=0 runtime=PENDING`.
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
Use one client for inventory presentation, interrupted custody and restart checks.

Actually fill/purify/drink each vessel, observe the liquid/agents/quantity and
native effects; repeat after restart. Find medical ingredients and Whetstone
through their native routes, craft both IV types and a drysack, repair a damaged
compatible item and retain quantity/health readback. Neither a synthetic fixture,
a native class export nor a debug-spawned item establishes ordinary acquisition.
The full candidate review, target-load budget and production promotion remain
pending. Distances added by HC-22: **none**.

## Historical HC-22 offline RED / GREEN record

The following records describe earlier refusal policy; current W46 behavior and
counts are documented above and tested against the integrated generator.

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
  `tests/slow/test_datamined_items.py::UsefulSupply`, using the explicitly
  synthetic `stock_mission` fixture. Covers all three bandanas, all 17 admitted
  floor overrides, rehashed nominal drift, stock spelling/case collisions,
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
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.slow.test_datamined_items.UsefulSupply tests.slow.test_friend_bundle.FriendBundleTests.test_exported_economy_install_refuses_missing_repo_only_supply_ledger -v
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
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.slow.test_script_syntax tests.unit.test_enforce_locals tests.slow.test_script_identifiers tests.unit.test_hygiene -v
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.validate.hygiene
```

Results: `Ran 53 tests` / `OK`; repository report `valid=true`, `errors=[]`.
Framework reused: existing bounded row/disposition parsers, CE extension and
collision checks, immutable manifest hashes, staged delta, receipt and byte-exact
rollback. No runtime framework or engine API was added; no new distances.

Additional dependent-reader checks (required by the shared worker brief):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.slow.test_hc_firearm_families tests.slow.test_friend_install tests.unit.test_gameplay_delta tests.unit.test_local_test_session tests.slow.test_optional_ce_composition tests.slow.test_optional_gun_scale tests.slow.test_snafu_optional tests.slow.test_tactical_flava_optional tests.slow.test_v2_optional_overlays tests.slow.test_ce_coverage tests.slow.test_enforce_formula_complexity -v
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

## W46 round 1 verification record (historical)

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
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_loot_w46 tests.unit.test_search_preview_sites tests.unit.test_search_economy_houses tests.unit.test_v1_combined_rpc tests.unit.test_enforce_lint tests.slow.test_script_syntax tests.unit.test_enforce_locals tests.slow.test_script_identifiers tests.unit.test_hygiene -v
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


## W46 round 2 review fixes

P1: the integrated generator now clears the floor-blocking flags only for the
17 reviewed rows. P2: cache pressure reclaims negative/unsent entries without
evicting in-flight requests or positive sites. The obsolete source-rewriting
fixture was replaced by integrated generation/install/rollback behavior.
P3: current accounting and overlay regeneration instructions are updated above.

Actual RED command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_loot_w46.FloorAdmissionIntegration tests.unit.test_loot_w46.CabinetSites.test_decorative_cabinets_cannot_starve_a_bound_cabinet -v
```

Result: `Ran 2 tests`, `FAILED (failures=2)`. Actual assertions:
`AssertionError: '1' != '0'` for the generated Drysack crafted flag;
`AssertionError: Lists differ: ['StaticObj_Furniture_case_a_x255y0z0w0'] != ['StaticObj_Furniture_case_a_x256y0z0w0']`
when decorative cabinet 257 could not send a request.
The additional throttled-unsent behavioral test also failed before its fix:
`AssertionError: 1 != 2` (one request instead of the required second request).

GREEN cache/source/common-brief command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_loot_w46 tests.unit.test_search_preview_sites tests.unit.test_v1_combined_rpc tests.slow.test_script_syntax tests.unit.test_enforce_locals tests.slow.test_script_identifiers tests.unit.test_hygiene -v
```

Result: `Ran 91 tests`, `OK`. The integrated floor test additionally passes
with the independent exact-17 allowlist and stock-preservation assertion.
Installer regression cases reject changed count flags, restored crafted/deloot,
unreviewed-row flag changes, extra flag attributes and changed cost before writes.
The audit test credits only actual emitted floor flags and retains conservative
common-route accounting for conflicting definitions.

`python3 -B -m tools.validate.enforce_lint --no-native`:
`enforce_lint: pass findings=1 new=0 stale=0 native=no`.
The full focused/affected commands and their results are recorded in the writer
commit message. No shared registry, mission-file list or settings edit is needed.
DayZDiag, normal PBO/server, single-client checks and target-load measurements
remain pending. Nothing observed in DayZ yet.

Broad focused/package/friend run: 841 reported checks, including one loader error
and one Windows-only PowerShell skip; 839 executed tests passed. The only loader
error was the firearm-family suite's sibling import (`test_firearms_roster`).
The required path fixes the invocation without source changes:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest tests.slow.test_hc_firearm_families -v
```

Result: `Ran 1 test`, `OK`. Across that broad run and the corrected module rerun,
840 tests passed and one Windows-only check was skipped. The additional affected
economy/package group ran 270 tests, `OK`. The final cache/source group ran 91
tests, `OK`. The independent exact-17 integration test also ran once, `OK`.
These are overlapping suites; their counts must not be summed as unique tests.
Nothing observed in DayZ yet.
