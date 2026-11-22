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
vehicles config), with no CfgPatches-gated PBO. With a pack absent every hook below is a pass-through to
`super` and the compat module stays disabled (no `[HC Ready]` line, no audit row).

Files (all under `mods/HollowCountry/scripts/4_World`):

- `Leads/HCNoteLedger.c`: lead-note identity predicate and the vanilla-class hooks.
- `Compat/HCNotesCompat.c`: module `NotesCompat`, probe, counters, recipe veto.
- `Compat/HCFoodCompat.c`: module `FoodCompat`, probe, temperature-init guard, config-RPC refusal.

### Load order requirement

Script layering is last-loaded-wins. The writable-notes pack overrides some read/write handlers without calling
`super`, which shadows every lower layer. HC must load above all four packs. In `tools/setup/workshop_mods.json`
HC ranks 80, so each pack must rank below 80. This is a hard requirement of the lead-note protection; if a pack
is ever ranked above HC the protection silently stops applying, and the one-client check below catches it.

### Writable notes versus lead notes

A lead note is a vanilla paper item carrying an HC note id (or, for legacy saves, vanilla paper with stored
text). The predicate requires the exact vanilla paper type, so a pack's writable note type can never be a lead
note and can never be assigned a lead id (`HCAssignNote` refuses non-vanilla types).

- Server `Paper.OnRPC` drops write and read-sync RPCs addressed to a lead note, then chains `super` for every
  other note (so the pack's own handler still runs for its notes).
- The vanilla write action is vetoed in `ActionCondition` when the item or target is a lead note.
- Crafting recipes (`RecipeBase.CheckRecipe`) refuse a lead note as an ingredient, so it cannot be consumed or
  converted by a pack recipe.
- The action constructor de-duplicates read/write actions after both layers register theirs.

Result: lead notes stay read-only and intact; a player cannot overwrite, erase or pin-move one; a written pack
note is never promoted to a lead note.

### Cooking pack

- Recipes are server-authoritative vanilla recipes. No client-side item creation or client-trusted result path
  was found; the one client-trusted input is the pack's server-config sync RPC, which a client could use to
  overwrite the server config. `FoodCompat` refuses that RPC from clients on a multiplayer server
  (`cookz_config_rpc_refused`).
- Residual, not guarded from our side: a null dereference after inventory creation in the pack's cooking code
  when the player has no free inventory slot. This is the pack's behaviour; report upstream.
- Excluded classes are removed by economy rows (packs track); there is no script deny list. The lead supplies
  the excluded class list to the economy owner.

### Food pack

The `InitTemperature` crash report could not be reproduced by reading: the pack does not override the 1.30
method. `modded Edible_Base.InitTemperature` guards pack food only: it verifies the mission, the world data and
the entity type config contract that vanilla 1.30 relies on, and skips the init (counting a guard hit) instead
of dereferencing a null. Non-pack food always goes straight to `super`.

### Medical supplies pack

Its stamina-type effect uses the native recovery-modifier registry. HC stamina passes the native multiplier
through, so the two multiply with HC `RecoveryScale`; the pack cannot replace the HC stamina config. No guard is
needed. Excluded crafted items are an economy matter (above).

## Counters

| Module | Feature | Meaning |
| --- | --- | --- |
| `NotesCompat` | `notes_lead_protected` | A lead note was assigned, restored, or a write/crafting/RPC attempt on one was refused. |
| `NotesCompat` | `notes_written` | A player note write was accepted by the server. |
| `FoodCompat` | `food_compat_guard` | Pack food passed through the temperature-init guard. |
| `FoodCompat` | `cookz_config_rpc_refused` | A client config RPC was refused (secondary, no activity row). |

The modules are enabled only when their pack is present, so activity rows apply only to runs with the pack.

## One-client checks

1. Pick up a lead note and try to write on it with a pen: refused, text unchanged, `notes_lead_protected` rises.
2. Write a pack note with a pen: it saves, reads back, `notes_written` rises, and it is not tracked as a lead.
3. Relog and read both again.
4. Spawn pack food and open a loot box: no script error, `food_compat_guard` rises.
5. Confirm there are no script errors on boot with each pack removed in turn.
