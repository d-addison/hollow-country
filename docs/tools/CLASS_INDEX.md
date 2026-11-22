# Class-name index

`tools/validate/class_index.py` records which object and ammo classes the installed stack
declares, so `wiring_audit` (W007 CE types, W008 literal spawn classes, W001/W001b scope and
parent resolution) can tell a truly undefined class from one that merely lives in a pack.

```sh
python3 -B -m tools.validate.class_index            # writes ~/.cache/hollow-country/class-index.json
python3 -B -m unittest tests.unit.test_class_index
```

## What is read and stored

- Sources, in load order: the vanilla `Addons` folder, every DLC folder of the same install
  (`<install>/<dlc>/addons`, source id `vanilla:<dlc>`; folders starting with `!` are skipped),
  then every non-published entry of `tools/setup/workshop_mods.json` by rank (source id = Workshop
  item id; the published Hollow Country items are repository sources and are not indexed).
- Per PBO, every `config.bin` and `config.cpp` member is decoded with `tools.audit.pbo_config`
  (bounded, uncompressed members only). Only direct children of `CfgVehicles`, `CfgWeapons`,
  `CfgMagazines` and `CfgAmmo` are kept, and for each only the class name, parent name, declared
  `scope` and the source id. Forward declarations (`class X;`) are not definitions. A later source
  refines an earlier row; an absent parent or scope never erases a known one.
- The file lives only under `~/.cache/hollow-country` and is never committed. No other config value,
  asset, path or Workshop code is stored.

## Coverage is exact

The file lists `coverage`: the source ids whose archives were all decoded. An archive that cannot
be decoded is recorded as unreadable and removes its source from coverage; the tool then exits 1.
It also stores the SHA-256 of the manifest it was built for. `wiring_audit` treats a missing file,
a source missing from coverage, a missing root or a different manifest as incomplete: its
notes name the gap and W007/W008 keep the "cache absence is not proof" wording. Only a complete
index turns absence into "the declared stack does not declare it".

Rebuild after a Workshop update, a manifest change or a game update.
