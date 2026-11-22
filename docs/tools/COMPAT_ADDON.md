# HC compat config addon (W4-01) and compat stringtable (W4-02)

`tools/package/compat_addon.py` builds `hollowcountry_compat.pbo`, a small config-only addon that
fills config entries our dependency stack leaves missing, by inheritance. It copies, patches and
repacks nothing of any dependency: no class bodies, assets, scripts or text. Every emitted class is
`class <Name>: <Parent> { scalar and array properties };`, with the parents forward-declared.

Status: built at bundle time and wired into the release path (wave C). No dependency rule is filled
(see "No dependency rules yet"), so the PBO currently carries `config.cpp` and the compat
stringtable only. Nothing here is runtime evidence: the lead runs the compile gate and a boot.

## Release wiring

- `tools.release.release` runs the generator into its scratch tree before the compile gate, copies
  the PBO(s) into `@HollowCountryExpansionAI/addons`, signs them with the usual key (rows come from
  `tools.release.ship_inputs.signing_inputs`, so the gate and the release share one catalogue) and
  writes a `compat_addon` receipt into `BUILD_MANIFEST.json`. The receipt's `native_compile` is set
  to `passed` only after the gate passed.
- `tools.release.compile_gate` generates the same PBO(s) from the selected tree and stages them
  beside the HCX PBO; every cataloged compat PBO must be staged or the gate refuses.
- `tools.release.friendcycle` and `tools.setup.friend_bundle` compare the receipt with the shipped
  PBO hashes (`compat_addon.check_receipt`) and refuse a bundle that drifted from its build.
  `friend_install` already copies our own PBOs generically and moves a retired one to backup, so an
  upgrade over an older profile repairs itself.
- Workshop publication of the HCX item does not list these PBOs yet; see the open items at the end.

## Optional provider PBOs

A rule that needs an addon which is not always installed carries `provider: "<slot>"` (slots
`a` to `f`, neutral on purpose). The file's `providers` list maps `{"slot", "item"}` to the Workshop
item. Such rules are emitted into a separate `hollowcountry_compat_<slot>.pbo` with its own nested
prefix and CfgPatches class, requiring the base compat patch plus the rule's `requires`. The
base PBO never requires an optional addon, because that would stop boot where the addon is absent.

The gate is the same as the weapon-pack guard: the item must be declared (and not `publish`) in
`tools/setup/workshop_mods.json`; undeclared means no PBO and receipt status `absent`; declared but
not installed under the Workshop root refuses generation. A rule without a provider may require
only mandatory addons (our own patches plus what our own configs require, minus the release-injected
optional blocks). A provider rule must require at least one non-mandatory addon, and its parent must
be an upstream class or a class of the base PBO, never one from another provider PBO.

## Use

    python3 -B -m tools.package.compat_addon --out <new-dir> [--source] [--workshop <221100>] [--manifest <json>]

`--out` must not exist. It receives `hollowcountry_compat.pbo`, any generated provider PBOs and
`compat-addon.json` (hashes, `requiredAddons`, rule and string counts, `pbos`, per-slot `optional`
entries, `runtime: PENDING`; no machine paths or Workshop ids). `--source` also writes the plain
`config.cpp` and `stringtable.csv` under `source/` (provider configs under `source/<slot>/`) for a
CfgConvert check. `--rules` is repeatable; by default `compat_rules.json` plus
`compat_vehicles.json` (W4-04, same schema) when that file exists.

The base PBO uses the registered nested prefix `HollowCountryExpansionAI\compat` (two PBOs with one
prefix in one folder crash the native server; provider PBOs register their own), the CfgPatches
class `HollowCountryCompat`, and requires `HollowCountryExpansionAI` plus the addons each rule names,
so it loads after them. Output is deterministic: sorted rules, parents before children, stable
stringtable order. Class, property and requires names are compared case-insensitively (the engine
does), `x` and `x[]` are one property name, integers must fit int32, exponent floats are refused,
and strings may not contain comment or directive markers. All generated text and the receipt must
pass the public-output token check.

## Rule schema (`compat_rules.json`, schema 1)

File keys: `schema`, `addon`, `providers`, `own_rules`, `dependency_rules` (`_doc` is ignored).

- `addon.required_addons`: must name CfgPatches classes of our own `mods/*/config.cpp` (checked).
- `own_rules`: derived from this repo's own data (our CE types, our config.cpp). Empty today: none
  of our own classes needs a compat entry.
- `dependency_rules`: the slot the lead fills from native RPT evidence (rpt_config_audit
  `No entry` rows). `requires` and `evidence` are mandatory here.

Rule fields: `id` (unique, `[A-Za-z0-9_-]`, emitted only as a comment), `section` (one of
`CfgVehicles`, `CfgWeapons`, `CfgMagazines`, `CfgAmmo`, `CfgNonAIVehicles`), `class`, `parent` (the
upstream class it inherits from), `requires` (CfgPatches names that define the parent), optional `provider` (slot), `set`
(`name`: number or printable ASCII string without quotes; `name[]`: bounded list of those; no
bool, null or nested objects) and `evidence` (a short note, never emitted).
Duplicate ids, duplicate target classes, inheritance cycles and self-inheritance are refused
(case-insensitively).
Keep dependency class names out of `mods/`, `mission/`, `config/` and docs; rule rows live here only.

## No dependency rules yet

The newest local server RPT (`--rpt` mode of the stringtable tool plus the `No entry` rows) was
reviewed. The missing-entry rows are overwhelmingly nested sub-entries (damage zones, optics and
beam sub-classes) of vanilla and third-party base classes. The schema forbids nested entries, and a
rule's parent must be proven upstream, so no safe inheritance-only rule can be derived from those
rows. The slot stays empty until a row names a top-level class whose parent and defining addon are
verified from the installed config; the generator and the provider path are ready for it.

## Compat stringtable

`tools/package/compat_stringtable.py` turns `compat_strings.json` (`{"key": "STR_...", "text": ...}`
rows in our own words) into a deterministic quoted `stringtable.csv` with the vanilla language
columns, all carrying our text. An empty list writes no table and the PBO carries `config.cpp` only.

    python3 -B -m tools.package.compat_stringtable --rpt <RPT> [--rpt <RPT>]
    python3 -B -m tools.package.compat_stringtable --out <new-file>

`--rpt` lists the `STR_*` keys on category 12 (localization) lines of an RPT that
`compat_strings.json` does not cover yet; keys and counts only. The file covers the non-vanilla
keys seen in the reviewed RPT, in our own wording. The remaining missing keys are vanilla UI keys
and are deliberately not provided here: shadowing vanilla text is not a compat fix.

## Checks

- `python3 -B -m unittest tests.unit.test_compat_addon tests.unit.test_compat_stringtable tests.unit.test_compile_gate_ship_inputs`
- Native: `--source` output through CfgConvert, then the PBO under the compile gate and a boot; the
  expected effect is fewer `No entry` and zero missing `STR_*` lines. Until that runs, the addon is
  "generated, runtime PENDING".

## Open items

- `tools/package/workshop_publish.py` lists only the guard PBO as an extra PBO of the HCX item and
  refuses other files, so a Workshop upload would reject the compat PBO(s). It needs the same
  change in `tools/validate/package_manifest.py`; neither is part of the compat scope.
- The compile gate with the compat PBO(s) staged and a one-server boot have not been run for this
  change; the lead runs them.
