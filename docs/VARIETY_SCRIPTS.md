# Variety packs: script-side integration (issue 232)

Scope: the script side of four Workshop packs: a writable-notes pack, a cooking pack, a food pack and a
medical-supplies pack. Pack selection, economy rows, dispositions and shipped profile settings are owned by
the packs track and are not described here. No pack code or assets are copied into this repo; pack configs
were read only for class names and properties. Pack class names are deliberately not listed in this file.

## Licence terms and client download size

Sizes are the Workshop-reported file size (what a client downloads).

| Pack | Client download | Terms summary |
| --- | --- | --- |
| Writable notes | about 14 MB | Everything allowed with a link; repacking and use of code explicitly permitted. We still do not repack. |
| Cooking | about 63 MB | No usage statement on the Workshop page. The bundled credits list third-party model and icon sources with their own licences (one attribution licence, one editorial no-AI licence). Treat as use-as-published only; never repack or redistribute. |
| Food | about 112 MB | Free to use on a server; repacking, redistributing or claiming assets is prohibited. Never repack or patch. |
| Medical supplies | about 55 MB | Monetisation allowed under the official monetisation agreement. The main PBO must not be repacked or re-uploaded; the separate CC PBO may be. We use neither as a repack. |

Nothing from any pack is shipped in the HC bundle. HC only reads them through the engine at runtime.

## Design

HC core cannot compile-reference pack classes: a missing pack would be a compile error and the server would not
boot. The integration therefore uses vanilla base classes plus a runtime config probe (class existence in the
vehicles config), with no CfgPatches-gated PBO. The compat modules stay disabled with their pack absent (no
`[HC Ready]` line, no audit row). Most hooks are pass-through to `super` without the pack. Three hooks act with
or without the pack because they protect an HC invariant on vanilla classes (a lead note stays intact):

- the lead-note write/read RPC drop (`Paper.OnRPC`),
- the write-action veto (`ActionWritePaper.ActionCondition`),
- the recipe veto (`RecipeBase.CheckRecipe`: vanilla fireplace and letter recipes accept any paper).

Their counters only count when the notes pack is present (the module is disabled otherwise).

Files (all under `mods/HollowCountry/scripts/4_World`):

- `Leads/HCNoteLedger.c`: lead-note identity predicate and the vanilla-class hooks.
- `Compat/HCNotesCompat.c`: module `NotesCompat`, probe, counters, recipe veto.
- `Compat/HCFoodCompat.c`: module `FoodCompat` (probe, temperature-init guard) and module `CookingCompat`
  (probe, dish counter, config-RPC refusal).

### Load order requirement

Script layering is last-loaded-wins: a mod loaded later wraps the ones loaded before it. `tools/setup/workshop_mods.json`
ranks HC at 80, so every pack must rank below 80 (HC wraps the packs). Two things depend on the order:

- The notes pack and HC both register a read and a write action. The action constructor keeps the first instance of
  an action type, so a duplicate is harmless; the de-dup in `HCNoteLedger.c` only tidies the list and nothing
  breaks if it does not run.
- The cooking pack handles its config RPC after calling `super`, so the HC refusal of that RPC takes effect only
  when HC wraps the cooking pack (HC loaded above it). With the pack above HC the RPC reaches the pack handler
  and `cooking_config_rpc_refused` stays at zero. The one-client check below catches that.

The notes-pack lead-note guards (`Paper.OnRPC`, write-action veto, recipe veto) call the guard before `super`
so they hold in either order for the hooks HC owns. Pack handlers that bypass `super` shadow only layers below them.

### Writable notes versus lead notes

A lead note is a vanilla paper item carrying an HC note id (or, for legacy saves, vanilla paper with stored
text). The predicate requires the exact vanilla paper type, so a pack's writable note type can never be a lead
note and can never be assigned a lead id (`HCAssignNote` refuses non-vanilla types).

- Server `Paper.OnRPC` drops write and read-sync RPCs addressed to a lead note, then chains `super` for every
  other note (so the pack's own handler still runs for its notes).
- The vanilla write action is vetoed in `ActionCondition` when the item or target is a lead note.
- Crafting recipes (`RecipeBase.CheckRecipe`) refuse a lead note as an ingredient, so a recipe cannot consume or
  convert it.
- The action constructor de-duplicates read/write actions after both layers register theirs.

Result: lead notes cannot be overwritten, erased or pin-moved by a player, and a written pack note is never
promoted to a lead note. This does not make a lead note indestructible: the indoor-fireplace action and fireplace
kindling attachment accept any paper, and the hearth-fire code that burns paper does not skip lead notes, so a
lead note can still be burned. Closing that is a change in the hearth-fire code, outside this module.

### Persistence

HC stores no extra field on the paper. The lead ledger keeps its own records and re-identifies a restored paper
by id or by its stored text, and records expire. Both mean a lead note self-repairs after a restart whether or
not the notes pack is present. The vanilla paper serialises its note text through the engine; the notes pack
extends the note data object with members, and whether that changes the stored layout cannot be read from
scripts (the serialisation is native). So adding or removing the pack on an existing save is a lead check, not a
proven property (see the one-client checks).

### Cooking pack

- Recipes are server-authoritative vanilla recipes. No client-side item creation or client-trusted result path
  was found; the one client-trusted input is the pack's server-config sync RPC, which a client could use to
  overwrite the server config. `CookingCompat` refuses that RPC from clients on a multiplayer server
  (`cooking_config_rpc_refused`; needs HC loaded above the pack, see load order). The module is enabled whenever
  the cooking pack is present, independent of the food pack.
- `cooking_dish_cooked` counts a cooking pass that changed a stage and left a finished pack dish in the pot
  (a `Cooking.CookWithEquipment` hook after `super`; the result is unchanged). It needs HC above the pack because
  the pack's dish path does not call `super`.
- Excluded classes are removed by economy rows (packs track); there is no script deny list. The lead supplies
  the excluded class list to the economy owner.

Residual, not guarded from our side: a null dereference when a finished dish cannot be created in the pot.
The pack override does not call `super` on its dish path, the creation call is native, and a guard would have
to wrap the pack's own override, which we cannot reference at compile time. It must be fixed upstream. Text to
send to the author:

> Cooking pack (Workshop id 3302732231), file `Scripts/4_World/modded/cooking.c`, lines 127-129, in the
> `CookWithEquipment` override: `CreateInInventory(dish.name)` is assigned to `createdDish` and
> `createdDish.SetTemperatureDirect(...)` is called without a null check. `CreateInInventory` returns null when
> the pot's cargo has no room for the new dish, which gives a null-pointer error in the server RPT (the
> following `SetFrozen` and `InsertAgent` calls dereference it too, and the ingredients were already removed
> above, so they are lost). Repro, by reading and not yet seen in game: cook a recipe whose `numDishes`
> dish items do not fit the pot's cargo once the ingredients are removed, and watch the server RPT for the
> null-pointer line from `cooking.c`. Suggested fix: `if (!createdDish) { break; }` (and keep the ingredients
> when nothing could be created).

RPT line to confirm this source: a null-pointer script error whose stack names the `CookWithEquipment`
override of `cooking.c` at line 129.

### Food pack

The `InitTemperature` crash report could not be reproduced by reading: the pack does not override the 1.30
method. The guard verifies the contract that vanilla 1.30 relies on (a mission, its world data, and a typed
entity config when the config temperature is used) for pack entities only (type name carries the pack tag).
It is applied to the two item roots the pack uses: the food root (`Edible_Base`) and the container root
(`Inventory_Base`, which covers loot boxes and bundles). `EntityAI` itself is in a lower script layer and cannot
be modded from `4_World`, so it is not hooked. A passing entity counts `food_compat_guard` (pass-through
evidence). A failing one is skipped (the item keeps its default temperature), counts `food_compat_refused` and
the first refusal of each reason prints `[HC Food] food_compat_refused reason=<no_mission|no_world_data|
no_entity_type>`. `food_compat_refused` is a fault counter: it registers on first refusal and has no activity row.
Non-pack items always go straight to `super`.

Bundle opening: the bundle's `Open()` override creates the item with `CreateObjectEx` and calls methods on the
result without a null check (the bundle base script under `scripts/4_world/entities/itembase/inventory_base` in the food pack, lines 48-50). The pack
override does not call `super` and the creation call is native, so no guard exists on our side. The call returns
null only when the configured spawn class does not exist. Four class names in the pack's box lists do not
exist in its config (a candy bar, a cake, a jar and a water bottle variant); in the box `Open()` the result is
unused, so they are harmless there. If an `Open` ever raises a null-pointer script error, the RPT stack names
`Open` in the bundle base script or a loot box script of that folder; that line confirms the source.

### Medical supplies pack

Its stamina-type effect uses the native recovery-modifier registry. HC stamina passes the native multiplier
through, so the two multiply with HC `RecoveryScale`; the pack cannot replace the HC stamina config. No guard is
needed. Excluded crafted items are an economy matter (above).

## Counters

| Module | Feature | Meaning |
| --- | --- | --- |
| `NotesCompat` | `notes_lead_protected` | A real refusal kept a lead note intact: `rpc` (write/read RPC dropped), `write_action` (write action vetoed) or `recipe` (recipe ingredient refused). Prints `[HC Notes] lead_protected reason=<how>` on the first of each reason. |
| `NotesCompat` | `notes_lead_tracked` | A lead note id was assigned on spawn or restore. Assignment evidence only; nothing was refused. |
| `NotesCompat` | `write_rpc_passed` | A client note write RPC (not a lead note) passed through to the pack handler. Pass-through evidence; the server does not confirm a stored note. |
| `FoodCompat` | `food_compat_guard` | Pack food, box or bundle passed the temperature-init contract guard. |
| `FoodCompat` | `food_compat_refused` | Fault counter, no activity row: the guard skipped the init; the first of each reason prints `[HC Food] food_compat_refused reason=<reason>`. |
| `CookingCompat` | `cooking_dish_cooked` | A cooking pass left a finished pack dish in the pot. |
| `CookingCompat` | `cooking_config_rpc_refused` | Fault counter, no activity row: a client config RPC was refused. |

The modules are enabled only when their pack is present, so activity rows apply only to runs with the pack.
Fault counters register on first use so the audit never expects them in normal play.

## One-client checks

1. Pick up a lead note and try to write on it with a pen: refused, text unchanged, `notes_lead_protected` rises
   and the `[HC Notes] lead_protected` line names the reason.
2. Write a pack note with a pen: it saves, reads back, `write_rpc_passed` rises, and it is not tracked as a lead.
3. Relog and read both again; `notes_lead_tracked` rises when the lead note is restored.
4. Spawn pack food, a loot box and a bundle and open the box and the bundle: no script error and
   `food_compat_guard` rises. A `food_compat_refused` line is a contract refusal to investigate.
5. Cook a pack dish (with a free slot in the pot): `cooking_dish_cooked` rises and there is no script error.
6. Persistence lead check (the layout effect of the notes pack cannot be read from scripts): with a save that
   holds a lead note and a written note, add the notes pack, boot, relog and read both notes; then remove the
   pack, boot and read the lead note. Expect: no script error on boot or load, the lead note text and id intact
   (restored by the ledger), and the written note text intact or empty but never a crash. Any load error or lost
   lead note text is a finding.
7. Confirm there are no script errors on boot with each pack removed in turn.
8. Load order: with HC ranked above the cooking pack, a config RPC from the client is dropped
   (`cooking_config_rpc_refused` rises only on a multiplayer server).
