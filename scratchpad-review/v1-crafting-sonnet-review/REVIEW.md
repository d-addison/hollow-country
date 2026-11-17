# Cross-model review: V1 crafting/salvage (#17 #52), commit 41c0676 on eb9ceb8

Reviewer: Sonnet 5.5. Review only; no tracked file edited, no git state change.
Mutants were run on a scratch copy under `mut/` in this folder.

## Verdict: FIX-THEN-MERGE

The runtime delta is small and sound: two exact beige garment sources join the
existing registered `HCRecoverMediumLeather` recipe, and a new
explicitly-invoked diagnostic is added. The gameplay path conserves material,
and every gameplay guard I mutated was killed. Blocking items are hygiene
(personal paths committed) and scope honesty (the Black/Brown/Natural gloves and
hats and ruined garment/bat salvage are excluded without evidence). The
diagnostic is not registered, performs no mutation unless called, and is bounded,
but the tests do not exercise most of its safety gates.

## 5. Full-suite result

`cd /code/hc-worktrees/v1-crafting && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit`
-> `Ran 2502 tests in 111.836s`, `OK (skipped=1)` (matches the writer's report).

## Scope table (every family in the brief)

| Family | Status | Evidence |
| --- | --- | --- |
| N1 executable decision table | implemented (thin) | `tools/audit/item_utility.py:44-160` `_decisions`, hooked at `:168`. Maps cohorts to decisions; `material_conversion` is hard-coded `UNKNOWN` for all 7,389 classes, so it does not record any V1 decision (see P2-3). |
| EXT-LEATHER-RECOVERY | implemented, **partial** | Jacket/vest/pants/shirt were already registered; this commit adds only `LeatherGloves_Beige`, `LeatherHat_Beige` (`HCSalvageRecipe.c:154-155`, count 5->7 at `:121`). Install config also has concrete Black/Brown/Natural gloves and hats (grep of `characters_gloves.pbo`/`characters_headgear.pbo` in the wine-server cache finds each name once, same pattern as the four jacket/pants colours). Excluding them is a scope choice, not an evidence-backed exclusion (P1-2). |
| EXT-CAMO-VISUALS | justified-exclusion (native reuse) | Verified native `PluginRecipesManagerBase.c:27-28` registers `CraftGhillieAttachment`/`DeCraftGhillieAttachment`; `CraftGhillieAttachment.c:27,36,46` Netting + BurlapStrip -> `GhillieAtt_Tan`; min quantities 1 and 2 at `:15,:21`. The paint recipes are inside a `/* */` block (`PluginRecipesManagerBase.c:173-234`), which supports "no green". No duplicate HC recipe. HC CamoNet -> Netting row exists (pre-existing). |
| EXT-RUINED-SALVAGE | implemented, **crate only**; other families weakly excluded | `HCRecoverRuinedCrate` (`HCSalvageRecipe.c:462-472`, ruled by `:263-264,:390-391`). Native `DeCraftWoodenCrate.c:12` (`m_MaxDamageIngredient[0] = 3`) refuses ruined and `:121-127` ruined branch is unreachable: verified. Ruined leather garments/bats are refused by the ordinary rows but no native fact says their material is unsupported; the same config evidence that proves leather for pristine garments applies (P1-3). |
| EXT-MECHANICAL-ELECTRICAL | justified-exclusion beyond existing rows | CableReel (`:413-419`) and BarbedBaseballBat (`:454-460`) pre-exist. `CraftBaseBallBatBarbed.c:23,44` / `CraftBaseBallBatNailed.c:13,23,44` verified. `EnergyManager` in the camping config is the component sub-class of each powered item, not a separate item. Native wire-consuming recipes are only CraftMetalWire, FishNetTrap, Nailed/Barbed bat, WoodenCrate, RabbitSnare, TripWire; reverse recipes exist for FishNetTrap, TripWire. No native proof for battery/radio component decomposition, so the exclusion is reasonable. (`RabbitSnare` has no `DeCraft*` file: worth a native check, P3-4.) |
| EXT-REPAIR-POLICY | justified-exclusion (native kept) | No HC repair recipe. Config bytes for gloves/hat/CableReel `repairableWithKits`/`repairCosts` match the report (hat kit types 5 and 2, cost 30/25; CableReel 5 and 7). Hat + LeatherSewingKit correctly stays native-excluded. |
| EXT-CUT-TOOLS | implemented (pre-existing) | 36 tools in `HCSalvageTools.ToolAt` (`HCSalvageRecipe.c:50-85`). |
| EXT-NATIVE-CHAIN-COVERAGE | preserved native, qualification pending | Nothing duplicated; the diagnostic is the qualification vehicle (not yet run). |
| EXT-LEGACY-RECIPES (74 disabled / 17 unregistered) | held | Hold, not an evidence-backed exclusion per row, but outside README items. |
| N2/N3 diagnostic | implemented (source only) | `HCItemUtilityDiagnostic.c` (575 lines). |

## Findings

### P1

**P1-1 Committed personal home paths (hygiene will fail after rebase).**
`.banso-brief.md:13,38`, `scratchpad-review/v1-crafting/REPORT.md:81,259` are
tracked in 41c0676 (`git show --stat HEAD`) and contain an absolute personal home path.
Main already has the `local_absolute_path` hygiene rule (1ae1be9,
`tools/validate/hygiene.py` `_LOCAL_HOME`), which refuses exactly this, so the
merge breaks hygiene. The brief and review scratchpad are also not source.
Fix: drop `.banso-brief.md` and `scratchpad-review/` from the commit (or
replace the paths with `~`). Keep only `mods`, `tests`, `tools`.

**P1-2 Gloves/hats only Beige; other colours excluded without evidence.**
`HCSalvageRecipe.c:152-155`; REPORT.md:125-126 ("remain outside this selected
extension"). The installed configs contain concrete Black/Brown/Natural
gloves and hats beside Beige, and jackets/vests/pants are covered in all four
colours. Under "every item ships in v1" this leaves an inconsistent half.
Failure scenario: a player finds `LeatherGloves_Brown` and cannot do what works
for the Beige pair. Fix: read the three colour entries per item from the same
config entries L1/L2 (scope 2, leather material selection, kit types), add
the exact names at indices 7..12 with `SourceCount` 13, update `MEDIUM` in
`test_crafting_families.py:9`, the fixture materials in
`test_crafting_contract.py:55-58` and `test_v1_crafting.py`. If the writer
finds a config reason (scope not 2, non-leather material) record that as the
exclusion with the byte offsets.

**P1-3 Ruined salvage limited to the crate with no evidence for other families.**
`HCSalvageRecipe.c:263-264` and REPORT.md:119 ("No generic ruined garment...").
The brief's EXT-RUINED-SALVAGE asks for deliberate irreversible salvage into
fewer raw materials wherever native config proves the material. The writer uses
the same material proof (leather selections; wood bat materials) for pristine
rows. A ruined LeatherJacket/Pants/Vest/Hat/Gloves and ruined bats (B1) are
the obvious cases. Fix: either add ruined-only sibling subclasses (damage 4,
`m_HCRuinedOnly = true`, yield strictly below the pristine yield, e.g. 1 for
jackets, still 1 for small garments only if pristine is >1; wood bat 1 stick)
or write an explicit exclusion naming the evidence (for example that the
material is unproven for that class). "Not specified" is not an exclusion.

### P2

**P2-1 Diagnostic safety gates are not exercised by tests.** Mutants (below)
that survive: SafeConcrete allow-all (D04), ValidRequest charset removal (D07),
index replay check removal (D08), PollCleanup ignoring `m_Bag` (D09), scope!=2
and CreationReviewed gates (D11, D12), ancestry depth bound (D13), end-of-queue
stop (D15), zone cap (D16), Complete ignoring Partial (D17), serialized row cap
(D18), non-identityless actor (D19), `m_Execute` opt-in in `CanExecute` (D20),
partial flag (D21). The test file only drives `Begin`, `BudgetAllows`,
`CanExecute`, `PollCleanup`, `ObserveNext` (with stubs), `DeletePair`,
`KitAt/RecipeAt`, `ObserveRepairEligibility`, `ObserveAction`. Because
`ObserveObjects`, `ValidRequest`, `SafeConcrete`, `EnsureActor`, `Summary`
and `Stop` are where it creates a player, creates items, sets health and calls
`PerformRecipeServer` (`:312-322, :394-457`), these are the load-bearing code.
Fix: add adapter tests for `ValidRequest` (spaces, `;`, 129 chars, index
mismatch), `SafeConcrete` (unlisted class false), `ObserveObjects` gates
(creation reviewed/unreviewed, scope), `Summary` (partial and complete), and a
`PollCleanup` case with only `m_Bag` set.

**P2-2 Server-authority guard in `PerformRecipe` is untested.** Mutant M14
(removing `if (!GetGame().IsServer()) return;`, `HCSalvageRecipe.c:311-312`)
survived the crafting test subset. (Also survives the full suite; see "Mutation results (full suite)".) Fix: add a test that `PerformRecipe` on a non-server
game neither calls `super.PerformRecipe` nor mutates ingredients.

**P2-3 N1 table does not carry the V1 decisions.** `item_utility.py:130-132`
hard-codes `material_conversion='UNKNOWN'`, `inventory_eligibility=
'NOT_EVALUATED'` for every config class, including the ones V1 now recovers
(gloves, hat). The "executable decision table" cannot answer "what is decided for
LeatherHat_Beige". Test A03 (empty/nonpositive cohort -> exclude) also survives.
Fix: add a small exact map of the HC rows (class, recipe, status
implemented/excluded, evidence id) merged into `config_classes`, and a test that
every `HCSalvageSources` class appears as `hc-recovery`.

**P2-4 `test_crafting_contract.py:162-166` weakens the no-mutation contract.**
The `AddQuantity|CreateInInventory|CreateObjectEx|ObjectDelete|RPCSingleParam`
ban now checks only `HCSalvageRecipe.c`, so `HCNativeCraftingSafety.c`,
`HCDrysackSafety.c`, `HCCraftingModule.c` and any future crafting file are
unprotected. Fix: scan every `Crafting/*.c` except `HCItemUtilityDiagnostic.c`
(and the existing fuel policy file if it needs it).

**P2-5 Replay after a script abort can orphan a handle.** `HCItemUtilityDiagnostic.c:408-411`
assigns `m_TargetObject`/`m_ToolObject` unconditionally. If a native null
dereference (for example `ItemBase.RemoveAction` reading the local player,
installed `ItemBase.c:295-297`, reached from `GetActions` -> `InitializeActions`
at `:235-240`) aborts `ObserveObjects` mid-row before `DeletePair`, the caller
retries the same index; hands are full, `CreateInHands` returns null and the
first handle is overwritten (not deleted until the actor tree is deleted).
Cleanup still occurs at Stop because the actor owns the object, but
`m_CreatedObjects`/`DeleteRequests` accounting and `Created` are wrong.
Fix: at the top of `ObserveObjects` (after the gates) `if (m_TargetObject || m_ToolObject) { Stop("stale-fixture-partial"); return; }`.

### P3

1. `HCItemUtilityDiagnostic.c:272-288` uses literals 0 and 3 for config types;
   the sibling `HCItemCompatibilityAudit.c:293-297` uses `CT_INT`/`CT_ARRAY`.
   Use the constants (observed values match: `test_item_compatibility_audit.py:25`).
2. `HCItemUtilityDiagnostic.c:253` calls `.Contains` on a string literal; every
   other call site in the repo uses a local variable (for example
   `HCTapedLightService.c:20`). Hoist the alphabet into a local to avoid an
   unverified compile form.
3. The diagnostic is always compiled into the production PBO (4_World) though
   it can create a player and mutate items. Repo precedent for gating exists
   (`#ifdef DIAG_DEVELOPER`, `HCInteriorSelfTests.c:31`). Gate the class body or
   confirm acceptance of shipping it; nothing instantiates it (rg over `mods`
   finds only the file itself), so it is inert.
4. `test_v1_crafting.py:87` `assertIs(tool, [material, tool][1])` is a
   tautology, and the gloves/hat test never asserts the output type
   `TannedLeather` or the tool wear value (only `m_ResultSetQuantity == [1]`).
   Mutant M05 (yield) is killed elsewhere, but an output-type mutant for these
   two sources would rely on family tests only. Fix: assert the result item and wear.
5. Native check suggestion: `CraftRabbitSnare.c` exists but no `DeCraftRabbitSnare`
   file exists; confirm in-game whether a native dismantle action covers it,
   otherwise add it as a candidate for EXT-MECHANICAL.
6. The V1 appendix lives only in the git-ignored `research/experiments/
   EXP-full-item-scope-decisions.md` (9,426 lines in the worktree), so the
   evidence trail is not in the commit except through REPORT.md, which P1-1
   asks to remove. Keep the evidence table in a tracked doc owned by the
   next docs pass.

## 1. Correctness review

- Conservation: `HCSalvageRecipe.c:234` destroys the source
  (`m_IngredientDestroy[0] = true`; mutant M06 killed); outputs are created by
  native `SpawnItems` (`:353-367`) and discarded if counts/types mismatch
  (`:323-351`, mutant M22 killed); ingredients are only consumed after outputs
  are verified (`:378-383`). Yields 1 (gloves, hat) match pants/shirt;
  the fixture budgets (2 hide units -> 1 panel) are synthetic and stated
  as such.
- Retained container / attachment refusal: `:273-281` refuses worn
  (`IsAttachment`), attachments and non-empty cargo on both source and tool; mutants
  M02, M03, M07, M11 killed. Gloves/hats have no cargo but worn items are
  attachments of the player, so equipped gloves/hat are refused.
- Server authority: `:311-312` returns on clients; commit happens only through
  the native manager server path; no RPC added. Test gap P2-2.
- Tool: `:296` requires health strictly above wear (mutant M01 killed), the
  tool is never destroyed (M18 killed) and wear is applied by native
  `m_IngredientAddHealth[1]` (`:235`).
- Ruined crate: `:263-264` `GetHealthLevel() == 4`, min/max damage 4 (`:469-470`),
  health 10% (`:390-391`, M17 killed); native crate refuses ruined (verified
  above) so no overlap, and a healthy crate cannot reach this row (M08 killed).
- `HCItemUtilityDiagnostic.c` production use: not registered. `rg` over `mods`,
  `config` and tools finds the class only in its own file and the test; no
  constructor, module hook, timer or RPC. Compiled into the PBO though (P3-3).
- Mutation by the diagnostic: yes, but only when a caller invokes `Begin` with
  explicit opt-in and an empty server: `CreatePlayer` (`:315`),
  `CreateAttachment` (`:319`), `CreateInHands` (`:408`), `CreateInInventory`
  (`:410`), `SetHealth01` on its own fixture (`:419`), `ObjectDelete`
  (`:505,524,529`), and `PerformRecipeServer` only when `executeRepairs` is
  true and `CanExecute` passes (`:448-452`). All objects are its own
  allocations; no existing player/item is accepted.
- Bounded: yes. 1..262,144 rows (`:215`), 60,000 ms (`:215,:236`), 128 KiB..64 MiB
  (`:217,:238`), 128 array values (`:290`), 64 ancestors (`:299`), 32 zones
  (`:342`), 512 recipes/actions (`:362,:434`), 20 actions (`:421`), 16,000-char
  row (`:466`). All loops have constant or checked bounds. `s_Active` is static
  and cleared only by `PollCleanup`, so a discarded instance blocks later runs
  (documented in the file header; acceptable for a diagnostic).

## 2. Native API verification (installed 1.30.164289, scripts cache)

- `RecipeBase.c:88,215,268,373,521,551,563` declarations match the override
  parameter names/types in `HCSalvageRecipe.c:283,308,353,369,378,385`
  (`ingredients`, `player`, `spawned_objects`, `sorted`, `results`, `result`,
  `specialty_weight`). `RecipeBase.c:1` `MAX_NUMBER_OF_INGREDIENTS = 2`;
  `RecipeBase.c:36` `m_NumberOfResults` is public (used by the diagnostic at `:369`).
- `PluginRecipesManager.c:93` `GetValidRecipes(item1,item2,array<int> ids,player)`
  and `:317` `PerformRecipeServer(int id, item_a, item_b, player)`: calls at
  `HCItemUtilityDiagnostic.c:433,451` match.
- `PluginRepairing.c:92` `CanRepair(ItemBase repair_kit, Object item, string damage_zone = "")`:
  call at `:391` matches.
- `Game.c:332` `CreatePlayer(identity, name, pos, radius, spec)`, `:545-546`
  `ConfigGetType`, `:578,585` array getters, `:602` `ConfigGetBaseName(out)`,
  `:705` `ObjectDelete`, `:945` `GetPlayers(out array<Man>)`: usages match.
- `ActionManagerBase.c:214` static `GetAction(typename)`,
  `ActionBase.c:230` `GetInputType()`, `ItemBase.c:235` `GetActions(typename, out array<ActionBase_Basic>)`;
  `ActionBase : ActionBase_Basic` (`ActionBase.c:51`) so `Find(action)` is valid.
  All 20 action classes in `ActionAt` (`:157-179`) exist in 4_World (grep each).
- `HumanInventory.c:44` `CreateInHands(string)`; `ItemBase.c:870` `CanBeRepairedByCrafting`;
  `Object.c:1153` `GetDamageZones(out TStringArray)`, `:1356` `CanBeRepairedToPristine`;
  `JsonFileLoader.c:85` `MakeData(T, out string, out string, bool)`.
- Evidence checks: `CraftWoodenCrate.c:15,21` (8 planks, 16 nails),
  `CraftBaseBallBatNailed.c:13` (12 nails), `CraftBaseBallBatBarbed.c:13`
  (12 barbed wire), `CraftGhillieAttachment.c:15,21`: all match the report.
  Config strings for `LeatherGloves_Beige`, `LeatherHat_Beige`, `CamoNet`,
  `CableReel`, `WoodenCrate` are present in the installed PBOs.

## 3. Compile-rule scan of the new and changed Enforce source

- No line starts with `||` or `&&` (rg); no ternary (rg ` ? `); at most 3
  `+` per statement (awk); explicit `typename.ToString()` at `:424`; no
  enum members; all loops bounded; no duplicate locals across sibling scopes
  (each loop variable and local name is unique per method); out args are
  declared before the call (`ancestor` `:297`, `payload/error` `:461-462`,
  `actions` `:359`, `players` `:219`); no overrides in the new file; no
  identifier equal to an engine type (also checked by `test_script_identifiers`
  and `test_script_syntax`, both pass). Remaining unverified forms are in P3-1/2.

## 4. Mutation results (scratch copies; killed unless stated)

Test subset: the 12 crafting/diagnostic/audit/syntax test modules.

Gameplay: killed M01 tool `<` for `<=`, M02 cargo check, M03 attachment check,
M04 hat dropped, M05 yield 1->2, M06 source not destroyed, M07 worn allowed,
M08 ruined flag off, M09 output health 1.0, M10b count 8 without item,
M11 ownership check, M12 type recheck, M13 plugged reel, M15 nail 4->8,
M16 crate nails 2->16, M17 ruined condition, M18 tool destroyed, M19 reentrancy
guard, M20 registration dropped, M21 registration reorder, M22 mismatch not
discarded. Survived: M10 (adds `LeatherGloves_Black` at index 7 but leaves count
7: equivalent mutant; the matching combined mutant M10c is below), **M14 server
check dropped (subset)**.

Diagnostic killed: D01 empty-server, D02 opt-in, D03 isolation, D05 time bound,
D06 results, D10 queue cap, D14 delete count, D22 `s_Active`.
Diagnostic survived: D04, D07, D08, D09, D11, D12, D13, D15, D16, D17, D18,
D19, D20, D21 (see P2-1).

Audit: killed A01 production flag, A02 disabled hold, A04 test-only hold;
survived A03 (empty cohort).

## Mutation results (full suite, scratch copies)

Full `tests/unit` run per mutant on a scratch copy. The copy has no `.git`, so
`test_repository_ignore_policy_excludes_local_private_keys_and_artifacts`
errors in every run including an unmutated one; it is a harness artefact and
is ignored below. A mutant counts as killed only if another test fails.

- M10c (add `LeatherGloves_Black` at index 7 and raise the count to 8):
  killed by `test_audit_checks_mutated_cached_recipe_instead_of_new_pristine_instance`
  (a genuine FAIL). This confirms the count/index pair is guarded, but only
  through the native-checks test, and the fixture families test does not
  assert the full source list against the config (see P1-2 fix).
- M14 (server check dropped in `PerformRecipe`): **survived** the full suite.
  P2-2 stands.
- D20 (`m_Execute` gate dropped in `CanExecute`): **survived** the full
  suite. A diagnostic can reach `PerformRecipeServer` without the executeRepairs
  opt-in. Part of P2-1.
- D04 (`SafeConcrete` allow-all): **survived** the full suite. Part of P2-1.

Totals over all mutants: gameplay 21 killed, 2 survived (M10 equivalent, M14);
diagnostic 8 killed, 14 survived; audit 3 killed, 1 survived; M10c killed.

