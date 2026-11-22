# Variety packs (Wave D, issue #232)

Nine owner-picked Workshop packs add variety to food, clothing, medical items, notes, fortifications,
fishing and shelter building. They are default-on Workshop dependencies that ship as plain `-mod` entries.
Hollow Country never repacks, patches or copies a pack; it reads installed config only, to learn class names
and numeric properties, and the economy rows below are authored by Hollow Country.

Status: implemented-unverified. Everything here is an offline estimate (`runtime=PENDING`): no DayZ behaviour,
spawn count or recipe is established until the lead's boot, soak and one-client smoke run on the exact commit.

## Packs

| Pack | Workshop id | Scope |
| --- | --- | --- |
| MoreFood V2 | 3534507229 | canned, jarred, bottled and packaged shelf food only |
| CookZ | 3302732231 | cooking recipes and their dishes (crafted only) |
| Uncuepas Civilian Clothing | 1762444175 | civilian clothing |
| Windstride's Clothing Pack | 1797720064 | clothing |
| AdditionalMedicSupplies | 2579252958 | subset: no energy, narcotics, methadone, pox, golden star or whistle items |
| dzr_notes | 2752192852 | player notes; admin tools never spawn |
| Building Fortifications | 2670506982 | fortification kits and the structures they build (crafted only) |
| gebsfish | 2757509117 | fishing gear, tackle, canned and packaged fish; no fishing clothing |
| RaG_BaseBuilding | 3157695626 | shelter-scale kits only (floor, wall, low wall, single door, small window, roof) |

DayZ Horse is not included.

## Where the data lives

* `tools/setup/workshop_mods.json`: each pack is a `side: client`, `publish: false` row in the
  `living_packs` group. The load order is owned by `friend_install` and the launcher.
* `config/variety-packs.json`: the authored, ordered, first-match rules per pack (match by name regex,
  ancestor, inventory slot, config root or parent), the licence text and the scope text.
* `config/variety-dispositions.json` (generated): one explicit disposition for every scope-2 class a pack adds.
* `mission/hollow-country/optional/variety-types.json` (generated): the CE rows per pack id plus the shipped
  settings files of that pack.
* `tools/package/variety_packs.py`: the generator (dev and CI only; it needs the installed packs and the stock
  mission). `python3 -B -m tools.package.variety_packs --report ...` prints the per-pack summary,
  `--write` regenerates and `--check` is wired into `tools.package.regenerate_all` and
  `tools.package.generated_digests`.
* `tools/package/variety_optional.py`: stdlib install-time overlay. A pack that is not loaded contributes no rows;
  `tools/package/optional_overlays.py` keeps source hashes, duplicate checks, category checks and rollback.

## Dispositions

Every class has exactly one of:

* `spawn`: nominal, lifetime, usage and category follow the closest vanilla peer (an explicit peer family, a
  peer slot with the mean of the category, or the nearest vanilla ancestor). Peer budgets are divided by the
  2x scarcity divisor; a family splits its budget over its members and never rounds a member to zero.
  Non-floor categories carry the shelf tag only, so nothing new appears as floor loot. The existing clothes
  floor policy is reused unchanged.
* `crafted`: nominal 0 and the `crafted` flag, lifetime 14400. Only a recipe, a catch or a build produces it.
  A crafted rule must give evidence: `script` (the class name occurs in the pack's own scripts) or `derived`
  (an opened or built state of a class that already has a disposition).
* `excluded`: the rule names the reason (for example out-of-setting items, admin tools, cosmetic duplicates,
  an owner-dropped subset). Excluded classes never spawn.

Guards: a nutrition value above 2x the peer median is reported and above 4x excluded; a clothing or gear size
above 1.5x the peer area is reported and above 2.0x excluded. A class no rule matches fails generation with the
class names listed, a crafted class that never appears in the pack scripts fails generation, and a peer without
a stock row fails generation. Nothing is zeroed silently.

The flooding totals (how many rows and how much nominal the packs add per category against the vanilla table)
are printed by the report mode and are an offline estimate only.

## Shipped settings

Third-party settings are shipped only where a pack has a file-based mechanism, and only with script evidence:
every key and the file name must appear in the pack's own scripts or generation fails.

* CookZ (mission root, `CookZ/CookZ_V003.json`): the pack reads a complete file, and a field it lacks reads as
  zero, so the full default set is written. The agent-removal chances are set to vanilla-like values rather than
  the pack's cure-everything defaults. The overlay writes the file only when it is absent, records it in the
  rollback receipt and rollback removes it; an operator's own file is never overwritten.
* gebsfish (profile root, `Gebs/general.json`): predator spawns and the treasure catch are switched off. The two
  sections are written complete because a missing field of a present section reads as zero; the pack backfills
  every other section itself.
* RaG_BaseBuilding (profile root, `RaG_Core/Configs/RaG_BaseBuilding/RaG_BaseBuilding.json`): craft toggles for
  all kits, shelter-scale kits on and every other kit off. The pack fills in the remaining fields from its own
  defaults.
* AdditionalMedicSupplies has no settings mechanism: the subset is enforced by the dispositions alone.

Profile files travel through the friend bundle profile catalogue as authored defaults. `friend_install` does not
merge these files, so an existing file on a server is reported as drift for the operator, never overwritten.

## Licences

None of the nine installed folders carries a licence file, so Workshop subscription terms apply to each of them.
Each is used only as an unmodified Workshop dependency: never repacked or patched, nothing copied into this
repository. Class names and numeric properties are read from the installed config for classification only.
The per-pack text is in `config/variety-packs.json`.

## Script-side concerns (other workers own these)

* Notes (dzr_notes) patches paper, the read action, the game class and the server mission; the note ledger and
  the duct-tape lock action need a compatibility check.
* CookZ writes its own file under the mission folder, uses the version name in the file name and zeroes absent
  fields; its default agent removal is 1.0.
* MoreFood V2 modifies edible base behaviour; check the temperature initialisation path for crashes.
* Fortifications: pathing, doors and its profile settings file.
* RaG_BaseBuilding: kits are gated by the craft toggles and the build book must be in hands to craft.
* gebsfish writes its own types and events files; Hollow Country never registers them.

## Checks

* `python3 -B -m tools.package.variety_packs --check --addons <Addons> --workshop <workshop> --source <stock mission>`
* `python3 -B -m tools.package.regenerate_all --check`
* `python3 -B -m unittest tests.unit.test_variety_packs tests.unit.test_variety_optional`
* The digest of the new artefacts is refreshed by the lead with `generated_digests --update`.
