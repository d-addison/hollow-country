# HC compat config addon (W4-01) and compat stringtable (W4-02)

`tools/package/compat_addon.py` builds `hollowcountry_compat.pbo`, a small config-only addon that
fills config entries our dependency stack leaves missing, by inheritance. It copies, patches and
repacks nothing of any dependency: no class bodies, assets, scripts or text. Every emitted class is
`class <Name>: <Parent> { scalar and array properties };`, with the parents forward-declared.

Status: generator, rule schema and tests only. It is not wired into release, friendcycle, signing or
the compile gate (wave C1 / W4-06), and no rule is filled yet, so nothing here is runtime evidence.
Whether the PBO is built per release or committed stays an owner decision; the generator works
either way: committed generator, committed rules, generated output that is never committed.

## Use

    python3 -B -m tools.package.compat_addon --out <new-dir> [--source]

`--out` must not exist. It receives `hollowcountry_compat.pbo` and `compat-addon.json` (hashes,
`requiredAddons`, rule and string counts, `runtime: PENDING`; no machine paths). `--source` also
writes the plain `config.cpp` and `stringtable.csv` under `source/` for a CfgConvert check.
`--rules` is repeatable; by default `compat_rules.json` plus `compat_vehicles.json` (W4-04, same
schema) when that file exists.

The PBO uses the already registered nested prefix `HollowCountryExpansionAI\compat` (two PBOs with
one prefix in one folder crash the native server), the CfgPatches class `HollowCountryCompat`, and
requires `HollowCountryExpansionAI` plus the addons each rule names, so it loads after them.
Output is deterministic: sorted rules, parents before children, stable stringtable order.

## Rule schema (`compat_rules.json`, schema 1)

File keys: `schema`, `addon`, `own_rules`, `dependency_rules` (`_doc` is ignored).

- `addon.required_addons`: must name CfgPatches classes of our own `mods/*/config.cpp` (checked).
- `own_rules`: derived from this repo's own data (our CE types, our config.cpp). Empty today: none
  of our own classes needs a compat entry.
- `dependency_rules`: the slot the lead fills from native RPT evidence (rpt_config_audit
  `No entry` rows). Starts empty. `requires` and `evidence` are mandatory here.

Rule fields: `id` (unique, `[A-Za-z0-9_-]`, emitted only as a comment), `section` (one of
`CfgVehicles`, `CfgWeapons`, `CfgMagazines`, `CfgAmmo`, `CfgNonAIVehicles`), `class`, `parent` (the
upstream class it inherits from), `requires` (CfgPatches names that define the parent), `set`
(`name`: number or printable ASCII string without quotes; `name[]`: bounded list of those; no
bool, null or nested objects) and `evidence` (a short note, never emitted).
Duplicate ids, duplicate target classes, inheritance cycles and self-inheritance are refused.
Keep dependency class names out of `mods/`, `mission/`, `config/` and docs; rule rows live here only.

## Compat stringtable

`tools/package/compat_stringtable.py` turns `compat_strings.json` (`{"key": "STR_...", "text": ...}`
rows in our own words) into a deterministic quoted `stringtable.csv` with the vanilla language
columns, all carrying our text. An empty list writes no table and the PBO carries `config.cpp` only.

    python3 -B -m tools.package.compat_stringtable --rpt <RPT> [--rpt <RPT>]
    python3 -B -m tools.package.compat_stringtable --out <new-file>

`--rpt` lists the `STR_*` keys on category 12 (localization) lines of an RPT that
`compat_strings.json` does not cover yet; keys and counts only. The lead adds the rows.

## Checks

- `python3 -B -m unittest tests.unit.test_compat_addon tests.unit.test_compat_stringtable`
- Native: `--source` output through CfgConvert, then the PBO under the compile gate and a boot; the
  expected effect is fewer `No entry` and zero missing `STR_*` lines. Until that runs, the addon is
  "generated, runtime PENDING".
