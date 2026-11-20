# Vanilla firearm test abundance (HC-21)

The 2026-11-20 owner decision supersedes the earlier 2x scarcity policy. **TEST ABUNDANCE ships
on by default; runtime acceptance remains pending.** Quantity and route proposals are for local
testing with one server and at most one client; 3–6-player budgets remain provisional.

The single knob is `economy_profile` in `tools/package/firearms_roster.json`: `test-abundance`
(default) or `scarcity`. The embedded `scarcity_policy` preserves the previous entries and family
caps exactly. Switch the knob, regenerate the release economy, then reinstall through the supported
bundle flow; editing a deployed JSON alone does not replace CE XML or reset existing CE storage.
The selector is shared by firearms generation, combined `economy.generate` and installer validation.
Friend-bundle export already passes the roster with `include_datamined=True` and
`include_roster_datamined=True`; no optional-pack or installer changes are required.

Abundance entries are explicit authored numbers derived from the inspected installed stock
`db/types.xml`. Ordinary weapons use at least ceil(stock nominal × 1.5), military rifles and
long rifles/snipers at least stock × 2; every class has a floor of 6. Previous roster shares × 3
are also a floor. Parent-derived variants use their inspected parent's stock count when absent;
zero-stock variants retain at least 6, never an inferred live spawn. Min is ceil(nominal / 2),
restock 300 seconds. Family envelopes are recalculated from these shares, so the old caps cannot
silently clamp abundance back to scarcity. All 78 weapon classes (including 3 crossbows) have
explicit replacement usage and nonempty Tier1–4 values.

Military weapons use Military Tier2–4; high-end AK101/AK74, ASVAL/VSS, SVD/SV98, M4, AUG,
FAL (native LAR class), M14 and Scout use Tier3–4. Native CE has tier eligibility rather than a
per-row numeric tier weight: restricting high-end weapons to Tier3/4 is the intended weighting.
Police SMGs use Police, hunting rifles use Hunting/Village, pistols use Town/Village/Police/Military.
M4/FAL/AUG are therefore no longer restricted to ContaminatedArea usage. Native flags, quantities,
categories, tags and assemblies remain unchanged; native dynamic-event `deloot` flags remain and
may affect which routes actually spawn a weapon.

The 50 magazines and 47 ammo sources use at least 3× stock and 4× their former roster nominal,
with a floor of 12, half min and 180-second restock. The 48 native CE-listed positive-stock
optics, stocks, handguards and suppressors use at least 3× stock, floor 12 and the same restock/min.
Support has explicit broad usage and Tier1–4. This includes loose/boxed/tracer/AP ammo without
inventing compatibility, integral optics or cylinder loot. The old `optics` placeholder records a
historical optional-pack decision; vanilla optics now have ordinary `attachment` support entries.
Native carrier definitions and default assemblies are preserved and still validated.

<!-- HC21-GENERATED-BEGIN -->
## Current authored family policy

Generated from `tools/package/firearms_roster.json`: 78 weapon classes, 53 weapon families, 50 magazine classes and 47 ammo sources (loose, boxed, tracer and specialist).

Weapon nominal ceiling: **2009**; with datamined rows omitted: **1584**. These are provisional CE proposals for 3–6 players; runtime acceptance remains pending.

| Family | Nominal / min cap | Explicit member shares (nominal / min) |
| --- | --- | --- |
| Mosin9130 | 142 / 71 | `Mosin9130` 90/45; `Mosin9130_Woodland` 40/20; `Mosin9130_Black` 6/3; `Mosin9130_Winter` 6/3 |
| SKS | 70 / 35 | `SKS` 28/14; `SKS_Woodland` 18/9; `SKS_Black` 6/3; `SKS_Desert` 6/3; `SKS_Green` 6/3; `SKS_Winter` 6/3 |
| Izh18 | 84 / 42 | `Izh18` 84/42 |
| Izh18Shotgun | 83 / 42 | `Izh18Shotgun` 83/42 |
| Izh43Shotgun | 48 / 24 | `Izh43Shotgun` 48/24 |
| Repeater | 48 / 24 | `Repeater` 48/24 |
| Winchester70 | 46 / 23 | `Winchester70` 18/9; `Winchester70_Black` 14/7; `Winchester70_Green` 14/7 |
| CZ527 | 212 / 106 | `CZ527` 50/25; `CZ527_Woodland` 50/25; `CZ527_Camo` 50/25; `CZ527_Green` 50/25; `CZ527_desert` 6/3; `CZ527_winter` 6/3 |
| B95 | 108 / 54 | `B95` 36/18; `B95_Black` 36/18; `B95_Green` 36/18 |
| LeeEnfield | 36 / 18 | `LeeEnfield` 36/18 |
| MP18 | 12 / 6 | `MP18` 12/6 |
| Luger | 18 / 9 | `Luger` 18/9 |
| SVD | 18 / 9 | `SVD_Wooden` 6/3; `SVD` 12/6 |
| Mp133Shotgun | 24 / 12 | `Mp133Shotgun` 24/12 |
| Magnum | 44 / 22 | `Magnum` 38/19; `Magnum_Gold` 6/3 |
| AKM | 12 / 6 | `AKM` 12/6 |
| Colt1911 | 51 / 26 | `Colt1911` 39/20; `Engraved1911` 12/6 |
| Makarov | 210 / 106 | `MakarovIJ70` 105/53; `MakarovPB` 105/53 |
| P1 | 75 / 38 | `P1` 75/38 |
| Glock19 | 60 / 30 | `Glock19` 60/30 |
| FNX45 | 21 / 11 | `FNX45` 21/11 |
| CZ75 | 30 / 15 | `CZ75` 30/15 |
| Ruger1022 | 53 / 27 | `Ruger1022` 53/27 |
| M16A2 | 12 / 6 | `M16A2` 12/6 |
| AK74 | 18 / 9 | `AK74` 18/9 |
| MP5K | 24 / 12 | `MP5K` 24/12 |
| Saiga | 24 / 12 | `Saiga` 24/12 |
| AK101 | 8 / 4 | `AK101` 8/4 |
| AKS74U | 16 / 8 | `AKS74U` 16/8 |
| ASVAL | 6 / 3 | `ASVAL` 6/3 |
| Aug | 6 / 3 | `Aug` 6/3 |
| AugShort | 8 / 4 | `AugShort` 8/4 |
| CZ550 | 28 / 14 | `CZ550` 28/14 |
| CZ61 | 8 / 4 | `CZ61` 8/4 |
| Crossbow | 22 / 11 | `Crossbow_Autumn` 8/4; `Crossbow_Black` 8/4; `Crossbow_Wood` 6/3 |
| Deagle | 46 / 23 | `Deagle` 38/19; `Deagle_Gold` 8/4 |
| Derringer_Grey | 30 / 15 | `Derringer_Grey` 30/15 |
| FAL | 6 / 3 | `FAL` 6/3 |
| FAMAS | 16 / 8 | `FAMAS` 16/8 |
| LongHorn | 38 / 19 | `LongHorn` 38/19 |
| M14 | 6 / 3 | `M14` 6/3 |
| M4A1 | 6 / 3 | `M4A1` 6/3 |
| M79 | 6 / 3 | `M79` 6/3 |
| MKII | 45 / 23 | `MKII` 45/23 |
| PM73Rak | 8 / 4 | `PM73Rak` 8/4 |
| PP19 | 21 / 11 | `PP19` 21/11 |
| R12 | 12 / 6 | `R12` 12/6 |
| SSG82 | 24 / 12 | `SSG82` 24/12 |
| SV98 | 6 / 3 | `SV98` 6/3 |
| Scout | 16 / 8 | `Scout` 6/3; `Scout_Chernarus` 10/5 |
| UMP45 | 18 / 9 | `UMP45` 18/9 |
| VSS | 12 / 6 | `VSS` 12/6 |
| Vikhr | 8 / 4 | `Vikhr` 8/4 |

### Cartridge ceilings

Each nominal/min is multiplied by `unit_rounds`: native pile maximum or box resource count. Detachable magazines have separate item budgets; loaded rounds and carrier throughput remain unmeasured.

| Ammo family | Nominal / min maximum cartridges | Sources |
| --- | --- | --- |
| Ammo_762x54 | 6420 / 3240 | `Ammo_762x54` 180/90 × 20; `AmmoBox_762x54Tracer_20Rnd` 21/11 × 20; `AmmoBox_762x54_20Rnd` 45/23 × 20; `Ammo_762x54Tracer` 75/38 × 20 |
| Ammo_762x39 | 10200 / 5120 | `Ammo_762x39` 300/150 × 20; `AmmoBox_762x39Tracer_20Rnd` 21/11 × 20; `AmmoBox_762x39_20Rnd` 54/27 × 20; `Ammo_762x39Tracer` 135/68 × 20 |
| Ammo_308Win | 6420 / 3220 | `Ammo_308Win` 150/75 × 20; `AmmoBox_308WinTracer_20Rnd` 21/11 × 20; `AmmoBox_308Win_20Rnd` 60/30 × 20; `Ammo_308WinTracer` 90/45 × 20 |
| Ammo_22 | 21750 / 10900 | `Ammo_22` 270/135 × 50; `AmmoBox_22_50Rnd` 165/83 × 50 |
| Ammo_12gaSlug | 3600 / 1800 | `Ammo_12gaSlug` 300/150 × 10; `AmmoBox_12gaSlug_10Rnd` 60/30 × 10 |
| Ammo_12gaPellets | 3600 / 1800 | `Ammo_12gaPellets` 300/150 × 10; `AmmoBox_00buck_10rnd` 60/30 × 10 |
| Ammo_45ACP | 7125 / 3575 | `Ammo_45ACP` 225/113 × 25; `AmmoBox_45ACP_25rnd` 60/30 × 25 |
| Ammo_9x19 | 9750 / 4875 | `Ammo_9x19` 300/150 × 25; `AmmoBox_9x19_25rnd` 90/45 × 25 |
| Ammo_357 | 7200 / 3600 | `Ammo_357` 270/135 × 20; `AmmoBox_357_20Rnd` 90/45 × 20 |
| Ammo_380 | 12600 / 6300 | `Ammo_380` 300/150 × 35; `AmmoBox_380_35rnd` 60/30 × 35 |
| Ammo_556x45 | 6120 / 3080 | `Ammo_556x45` 150/75 × 20; `AmmoBox_556x45Tracer_20Rnd` 21/11 × 20; `AmmoBox_556x45_20Rnd` 60/30 × 20; `Ammo_556x45Tracer` 75/38 × 20 |
| Ammo_545x39 | 4560 / 2320 | `Ammo_545x39` 75/38 × 20; `AmmoBox_545x39Tracer_20Rnd` 27/14 × 20; `AmmoBox_545x39_20Rnd` 51/26 × 20; `Ammo_545x39Tracer` 75/38 × 20 |
| Ammo_12gaRubberSlug | 1680 / 840 | `AmmoBox_12gaRubberSlug_10Rnd` 48/24 × 10; `Ammo_12gaRubberSlug` 120/60 × 10 |
| Ammo_9x39 | 2940 / 1500 | `AmmoBox_9x39AP_20Rnd` 15/8 × 20; `AmmoBox_9x39_20Rnd` 21/11 × 20; `Ammo_9x39` 66/33 × 20; `Ammo_9x39AP` 45/23 × 20 |
| Ammo_40mm_Chemgas | 15 / 8 | `Ammo_40mm_Chemgas` 15/8 × 1 |
| Ammo_40mm_Explosive | 24 / 12 | `Ammo_40mm_Explosive` 24/12 × 1 |
| Ammo_40mm_Smoke_Black | 45 / 23 | `Ammo_40mm_Smoke_Black` 45/23 × 1 |
| Ammo_40mm_Smoke_Green | 45 / 23 | `Ammo_40mm_Smoke_Green` 45/23 × 1 |
| Ammo_40mm_Smoke_Red | 45 / 23 | `Ammo_40mm_Smoke_Red` 45/23 × 1 |
| Ammo_40mm_Smoke_White | 45 / 23 | `Ammo_40mm_Smoke_White` 45/23 × 1 |
| Ammo_HuntingBolt | 375 / 190 | `Ammo_HuntingBolt` 75/38 × 5 |

### Formerly off-roster positives

All 32 are retained explicitly. Counts follow the selected economy profile; skin members share the family ceiling. `review-native-budget` preserves SV98 while refusing functional acceptance.

| Class | Disposition | Family |
| --- | --- | --- |
| `AK101` | keep-native-budget | AK101 |
| `AKS74U` | keep-native-budget | AKS74U |
| `ASVAL` | keep-native-budget | ASVAL |
| `Aug` | keep-native-budget | Aug |
| `AugShort` | keep-native-budget | AugShort |
| `CZ550` | keep-native-budget | CZ550 |
| `CZ61` | keep-native-budget | CZ61 |
| `Crossbow_Autumn` | keep-native-budget | Crossbow |
| `Crossbow_Black` | keep-native-budget | Crossbow |
| `Crossbow_Wood` | keep-native-budget | Crossbow |
| `Deagle` | keep-native-budget | Deagle |
| `Deagle_Gold` | keep-native-budget | Deagle |
| `Derringer_Grey` | keep-native-budget | Derringer_Grey |
| `Engraved1911` | keep-native-budget | Colt1911 |
| `FAL` | keep-native-budget | FAL |
| `FAMAS` | keep-native-budget | FAMAS |
| `LongHorn` | keep-native-budget | LongHorn |
| `M14` | keep-native-budget | M14 |
| `M4A1` | keep-native-budget | M4A1 |
| `M79` | keep-native-budget | M79 |
| `MKII` | keep-native-budget | MKII |
| `Magnum_Gold` | keep-native-budget | Magnum |
| `PM73Rak` | keep-native-budget | PM73Rak |
| `PP19` | keep-native-budget | PP19 |
| `R12` | keep-native-budget | R12 |
| `SSG82` | keep-native-budget | SSG82 |
| `SV98` | review-native-budget | SV98 |
| `Scout` | keep-native-budget | Scout |
| `Scout_Chernarus` | keep-native-budget | Scout |
| `UMP45` | keep-native-budget | UMP45 |
| `VSS` | keep-native-budget | VSS |
| `Vikhr` | keep-native-budget | Vikhr |

Named pending refusals:

- `HC21_NATIVE_WORLD_CAP_UNOBSERVED`
- `HC21_CARRIER_SUPPLY_UNMEASURED`
- `HC21_LOADED_MAGAZINE_ROUNDS_UNMEASURED`
- `HC21_AI_AMMO_RUNTIME_PENDING`
- `HC21_SV98_FUNCTION_PENDING`
- `HC21_NATIVE_CLASS_COVERAGE_UNQUALIFIED`

<!-- HC21-GENERATED-END -->

## Generator and supply semantics

`python3 -m tools.package.firearms summary` regenerates the marked summary above from the validated roster.
The policy file contains authored class names, budgets and route metadata, not native config bodies or assets.
Both generators call the same `roster_items`/`family_totals` policy. Generation refuses over-cap shares,
unknown positive ammo/box/magazine rows, missing effective compatible ammo/magazines and missing declared
native carrier references. `check_effective_support` repeats family validation immediately before install,
so a rehashed staged recolour cannot bypass the family cap. Native weapon identification still depends on
the separately inspected class/config evidence; unknown future weapon ancestry requires re-audit.

```sh
python3 -m tools.package.firearms generate --source <stock-mission-copy> --out <fresh-delta-dir>
python3 -m tools.package.firearms generate --with-items --source <stock-mission-copy> --out <fresh-delta-dir>
python3 -m tools.package.firearms generate --no-datamined --source <stock-mission-copy> --out <fresh-delta-dir>
```

Weapon and magazine families use item counts. Ammo families use maximum cartridge equivalents:
`sum(nominal * unit_rounds)` and `sum(min * unit_rounds)`. Boxes, tracer and AP rows take shares from their
existing loose-round allowance; they do not add a second allowance. Native `quantmin/quantmax`, flags,
categories, cost, loading, firing and repair definitions are retained. Placement and restock follow the selected authored profile. Magazines retain
separate item caps; actual filled-magazine rounds and attached/carrier throughput remain pending measurement.
The empty `AmmoBox` storage container is not an ammunition box and remains native container loot.

Family caps describe configured CE replenishment proposals, **not hard world inventory caps**: native
hoarding/player/cargo flags remain unchanged. There is no new aggregate CE controller, scavenging injector,
AI refill path, telemetry loop or save system. The general HC-9 boost consumes the expanded roster exclusion
set; all named ammo, magazine and weapon rows remain excluded. Runtime actor inventories must still debit
finite real ammunition; this package cannot establish that behavior.

The generated family table above records the selected profile's exact member shares. Historical scarcity
shares are preserved in `scarcity_policy`; test abundance raises them explicitly. Engraved/gold variants
still share a declared family envelope. These counts remain provisional for 3–6 players.

### Native parts and carrier routes

Declared M4/AK/FAL attachment routes reuse the stock `cfgspawnabletypes.xml` entries with positive chances.
They are useful native assembly routes, not newly imposed firing prerequisites. The generator creates no
new assembly definitions and does not copy carrier definitions onto parent-derived recolours. Abundance
raises existing positive-stock loose CE parts and optics as additional acquisition routes. `AugOptic` and Magnum
cylinder/ejector (including gold parts) remain native integral/default assembly metadata, never new CE loot.
Ordinary clones use donor fields plus the authored budgets, usage and tiers, reusing stock spelling case-insensitively.
SV98's existing compatible CE magazine is retained, but the older config census flags incomplete evidence;
its spawn/load/fire/unload/repair acceptance remains explicitly refused pending functional evidence.

Read-only installed evidence inspected for this change (all paths relative to
`~/.cache/hollow-country/native-scripts/scripts-1.30.164289/`):

- `4_World/Entities/ItemBase/Magazine/Magazine.c:68-88`: native cartridge counts and server mutations.
- `4_World/Entities/Firearms/Weapon_Base.c:324-326,1262-1266`: native chamber/firing checks.
- `4_World/Entities/Firearms/AutomaticRifle/AUG.c:68-76`: short AUG's native optic assembly.
- `4_World/Entities/Firearms/Pistol/Magnum.c:179-195,404-413`: native cylinder/ejector assembly.
- `4_World/Entities/Core/Inherited/InventoryItem.c:1147-1153`: native box action registration.
- `4_World/Classes/UserActionsComponent/Actions/Continuous/ActionUnpackBox.c:40-94`: server-side
  `CfgVehicles/Resources` lookup and replacement with configured cartridge count.
- `3_Game/CE/CentralEconomy.c:746`: native CE API declaration; no aggregate firearm-family cap API
  is invoked or inferred from this interface.

Installed `weapons_ammunition.pbo` configs were read with the existing bounded PBO reader: `CfgMagazines/count`
provides pile maxima, and each `CfgVehicles/AmmoBox_*/Resources/<ammo>/value` matches the declared box rounds.
Native carrier references were checked read-only against the installed stock mission. Neither check runs DayZ.

## Economy integration and preserved scarcity

`economy.generate` and the firearms entry points select the same roster policy. The installer
checks parent-derived rows against that selected policy's full reviewed parent row with authored
budget, usage and tier changes; unrelated fields remain exact. Case aliases reuse stock spelling.
The historical `keep-native-budget` disposition identifies retained native classes, not an assertion
that their test counts equal stock. SV98 functional acceptance remains pending.

Selecting `scarcity` restores the old 444 weapon nominal / 323 min proposal (394 / 293 with
datamined rows omitted), 360 magazine nominal / 248 min and 11,644 / 8,194 maximum-cartridge
ammo proposal. That historical mode restores its old placement fields too. The new loose optics/parts
support rows are absent in scarcity, leaving their stock CE policy intact.

## 2026-11-20 scratch rehearsal

Read-only evidence: installed mission `db/types.xml`, `cfglimitsdefinition.xml` and
`cfgspawnabletypes.xml`. The inspected copy differs from the lead's earlier live-107 measurement
(409 nominal / approximately 122 Tier4-eligible): its 63 stock-backed overridden weapon classes
sum to **406** nominal against **882** stock, with **102** Tier4-eligible nominal. Seven additional
parent-derived rows give 70 overridden rows, 420 nominal and 110 Tier4-eligible nominal. These are
file sums, not observed world populations. Case-insensitive class matching is used throughout.

| Comparison set | Before nominal | After nominal | Before Tier4-eligible nominal | After Tier4-eligible nominal |
| --- | ---: | ---: | ---: | ---: |
| Same 63 stock-backed overrides | 406 | 1,620 | 102 | 1,620 |
| Same 70 installed overrides including parent-derived rows | 420 | 1,925 | 110 | 1,925 |
| Complete 78-class authored roster | 444 (preserved scarcity) | 2,009 | inherited stock placement, not a fixed authored total | 2,009 |

The 78 weapon rows include **75 firearms and 3 crossbows**; firearms alone total **1,987** nominal.
The generated combined economy has **311 rows**, including all **223 roster rows**: 78 weapons,
50 magazines (**2,204** nominal), 47 ammo sources (**4,845** nominal item/pile rows, **104,559**
maximum-cartridge equivalents) and 48 optics/part rows (**1,164** nominal). Every weapon has explicit
usage and nonempty tiers; all meet the 1.5× stock floor, and authored military/long rifles meet the
2× stock floor and minimum 6. The checked-in CE overlay matches generated roster fields exactly and
retains unrelated authored rows. No duplicate class rows were added.

Top 20 generated weapon rows, ordered by nominal descending then class:

| Class | Nominal | Min | Usage | Tiers |
| --- | ---: | ---: | --- | --- |
| `MakarovIJ70` | 105 | 53 | Military, Police, Town, Village | Tier1, Tier2, Tier3, Tier4 |
| `MakarovPB` | 105 | 53 | Military, Police, Town, Village | Tier1, Tier2, Tier3, Tier4 |
| `Mosin9130` | 90 | 45 | Hunting, Village | Tier1, Tier2, Tier3, Tier4 |
| `Izh18` | 84 | 42 | Hunting, Village | Tier1, Tier2, Tier3, Tier4 |
| `Izh18Shotgun` | 83 | 42 | Hunting, Village | Tier1, Tier2, Tier3, Tier4 |
| `P1` | 75 | 38 | Military, Police, Town, Village | Tier1, Tier2, Tier3, Tier4 |
| `Glock19` | 60 | 30 | Military, Police, Town, Village | Tier1, Tier2, Tier3, Tier4 |
| `Ruger1022` | 53 | 27 | Military, Police, Town, Village | Tier1, Tier2, Tier3, Tier4 |
| `CZ527` | 50 | 25 | Hunting, Village | Tier1, Tier2, Tier3, Tier4 |
| `CZ527_Camo` | 50 | 25 | Hunting, Village | Tier1, Tier2, Tier3, Tier4 |
| `CZ527_Green` | 50 | 25 | Hunting, Village | Tier1, Tier2, Tier3, Tier4 |
| `CZ527_Woodland` | 50 | 25 | Hunting, Village | Tier1, Tier2, Tier3, Tier4 |
| `Izh43Shotgun` | 48 | 24 | Hunting, Village | Tier1, Tier2, Tier3, Tier4 |
| `Repeater` | 48 | 24 | Hunting, Village | Tier1, Tier2, Tier3, Tier4 |
| `MKII` | 45 | 23 | Military, Police, Town, Village | Tier1, Tier2, Tier3, Tier4 |
| `Mosin9130_Woodland` | 40 | 20 | Hunting, Village | Tier1, Tier2, Tier3, Tier4 |
| `Colt1911` | 39 | 20 | Military, Police, Town, Village | Tier1, Tier2, Tier3, Tier4 |
| `Deagle` | 38 | 19 | Military, Police, Town, Village | Tier1, Tier2, Tier3, Tier4 |
| `LongHorn` | 38 | 19 | Military, Police, Town, Village | Tier1, Tier2, Tier3, Tier4 |
| `Magnum` | 38 | 19 | Military, Police, Town, Village | Tier1, Tier2, Tier3, Tier4 |

Rehearsal used an isolated `/tmp/hc-gunqty/` mission copied from the installed files. The installed
release lacks the economy rollback receipt, so `friend_bundle.fresh_economy` on an untouched copy
refuses with `no valid receipt and unexpected managed content; rollback refuses deletion`.
The existing receipt safety check was preserved. Only the scratch copy was then prepared with stock
CE registrations and no HC managed directories. On that clean scratch, the actual bundle helper,
`economy.generate(..., include_datamined=True, roster=..., include_roster_datamined=True)`,
`economy.install_delta` and rollback completed. The installed server was never written.

Rehearsal output tail:

```text
friend_bundle.fresh_economy generated 311 rows
economy.install_delta OK
economy.rollback OK: source hashes restored
scarcity selector OK: 444 weapon nominal
abundance floor/tiers/min and authored/export consistency OK
scarcity selector generate/install/rollback OK: 444 nominal, source bytes restored
```

Focused existing tooling checks (no new tests):

```sh
python3 -B -m unittest tests.slow.test_firearms_roster tests.slow.test_hc_firearm_families tests.slow.test_economy_contract
```

Result: **Ran 77 tests / OK**. Existing scarcity assertions now explicitly exercise the archived
selector; synthetic usage vocabularies and reviewed-parent expectations reflect authored replacement
routes. The older fixed seven-row overlay fixture now allows additional authored CE rows.

Still unproven in DayZ: native CE merging, restock rates, usable shelf eligibility and placement,
actual gun/ammo/magazine/optic acquisition, attachment compatibility with optional packs, SV98 function,
server boot/error output and one-client inventory/assembly/use. Native dynamic-event flags remain
unchanged and need observation. No multiplayer or 3–6-player performance proof is claimed.
The loot-point worker owns the reported zero-compatible-shelf problem. The bundle owner needs to
reconcile missing economy receipts on existing installed release copies if export from those copies
is required; the clean-input generation path itself passes.

## Historical 2026-11-18 HC-21 evidence and remaining native work

One explicitly synthetic behavioral test exercises both authored generators, caps, effective support,
carrier admission, the HC-9 boost exclusion and the datamined off path:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_firearm_families -v
```

Actual RED: `AssertionError: {...32 classes...} is not false : positive off-roster firearms bypass scarcity`.
Extending the same test to rehashed staged cap inflation also produced actual RED:
`AssertionError: ValueError not raised`. After implementation, the command reports `Ran 1 test` / `OK`.
Round-2 spec → plan → tasks: implement the two shared economy seams; lock native scarcity and
cartridge arithmetic; reject orphan magazines and validate custom policy; run installed-stock generation;
then run the entire consumer suite. The active round-2 brief is the specification; shared Banso artifact
reconciliation remains HC-11's scope. No native experiment is accepted by these source changes.

Round-2 test-first command (before implementation):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_firearms_roster -v
```

Actual RED: `Ran 42 tests` / `FAILED (failures=96, errors=5)` (native-budget mismatches include
subtest failures). Representative actual failures: `AssertionError: 30 not less than or equal to 28 : MKII`,
`AssertionError: ValueError not raised` for direct economy carrier admission,
`StopIteration` for a missing reviewed roster name, the installer rejection
`ValueError: new class must exactly clone its reviewed parent at 2x scarcity: MakarovPB`,
and `FileNotFoundError` from the attempted shipped-policy read during a custom-policy check.
The orphan assertion named all five unreferenced magazines. After implementation, the same command
reports `Ran 42 tests` / `OK`, including both generators, the local-session composition seam,
installer tamper refusals and byte-exact rollback.

Read-only installed-stock checks (2026-11-18), using the server install location from the existing
probe tools: `/mnt/d/SteamLibrary/steamapps/common/DayZServer/mpmissions/dayzOffline.chernarusplus`.
The stock `db/types.xml` has no positive ammo/box/magazine row outside the roster; hunting bolts and
rubber slugs are already accounted for. Flares/beanbags do not trigger the positive-row refusal in this
installed snapshot, so no exception allowlist was needed. Unknown future positive support still refuses.

```text
REAL_STOCK firearms GENERATED weapon_nominal=444 family_budget=444 families=53 runtime=PENDING
REAL_STOCK firearms-off GENERATED weapon_nominal=394 family_budget=444 families=53 runtime=PENDING
REAL_STOCK economy-default GENERATED weapon_nominal=444 family_budget=444 families=53 runtime=PENDING
REAL_STOCK local-session-default GENERATED identical_to_economy=True
REAL_STOCK stock_unchanged=True
```

Both CLIs returned `Offline operation complete; DayZ runtime acceptance pending.` with exit 0.
The economy run used the shipped contextual-pilot profile, default roster and default non-weapon items;
the local-session composition seam produced identical `ce/types.xml` bytes. Outputs were temporary and
outside Git. Source input and carrier bytes were compared before/after. No vanilla files were copied into
Git. `stat -c %s tools/package/firearms_roster.json` reports **57,790 bytes**, below the unchanged 60,000
limit after dropping empty part lists and compacting repeated prose. No banned text occurs in
`mods/`, `mission/` or `config/`.

Round-2 consumer verification uses the requested module selection, with the unit fixture directory
on the import path because existing tests import sibling fixtures by bare module name:

```sh
export PYTHONPATH=.:tests/unit
mods=$(rg -l -e 'firearms|economy|datamined_items|loot_boost|local_test_session' tests/unit | sed 's#tests/unit/##;s#\.py##;s#^#tests.unit.#' | tr '\n' ' '); PYTHONDONTWRITEBYTECODE=1 python3 -m unittest $mods
```

The literal command without that import path ran 1,404 tests and reported two import errors
(`test_firearms_roster` and `test_pbo_config` sibling fixtures), one skip and one expected failure.
Actual GREEN with that import path: **Ran 1,427 tests / OK (skipped=1, expected failures=1)**.
The additional 19 modules matching `snafu_optional|tactical_flava_optional|pbo|friend_bundle` but not
the supplied regex ran **693 tests / OK**, for **2,120 consumer tests** across both runs.
These are offline tests, not DayZ observations.

Lead native acceptance: exact-source DayZDiag compile/boot, then normal signed PBO/server; no script or CE
errors; source/PBO/mission/config/dependency hashes; receipt/off-path/stop/restart checks. For every retained
family, spawn/load/fire/unload/repair, acquire/restock/hoard, consume finite AI ammo and verify persistence.
Use one client for inventory/attachment presentation. SV98 requires its own functional evidence before
acceptance. No production enablement, server deployment or publication is authorized by this document.

The remaining optional-pack evidence below is historical research and pending qualification. It is retained
for rights/support traceability; HC-21 neither re-verifies dependencies nor changes their admission.

## 2. Datamine census

`tools/audit/firearm_census.py` (with `tools/audit/pbo_config.py`, a bounded streaming PBO and
rapified-config reader) classifies every `scope=2` weapon class by cross-referencing `types.xml`,
`cfgspawnabletypes`, `cfgrandompresets`, event files and `db/events.xml`, and checks model, hand-animation
and magazine presence. Inputs are read only; the full output goes outside Git:

```
python3 -m tools.audit.firearm_census --addons LABEL=<dir> [--addons ...] --mission <mission dir> \
        --out ~/.cache/hollow-country/firearm-census-<date>
```

The tool refuses any output directory inside a Git checkout. The 2026-11-17 run (static evidence only):

| Classification | Classes |
| --- | --- |
| spawning | 61 |
| nominal-zero (finished, stock nominal 0) | 43 |
| missing-from-types | 32 |
| scope-not-public | 5 |
| event-only | 0 |
| unknown | 0 |

141 weapon classes plus 69 abstract scope-0 bases. Two classes were flagged as suspected unfinished (`SV98`, `DartGun`). HC-21 now retains the existing
SV98 CE budget with an explicit review disposition; functional evidence is still pending. DartGun remains unproposed.

Datamined classes enabled at rare counts, pending local acceptance: `LeeEnfield`, `MP18`, `Luger`, `SKS_Black`,
`SKS_Desert`, `SKS_Green`, `SKS_Winter`, `Mosin9130_Black`, `Mosin9130_Winter` and `SVD_Wooden` (see the generated family policy).
The nine parent-derived variants and the PB magazine are now authored as pending-local candidates under
family budgets; they are no longer deferred. Case aliases reuse existing CE rows. Every datamined candidate needs native spawn, firing and ammo trials; inventory/attachment presentation requires one client.

## 3. Optional SNAFU Weapons subset

Item: SNAFU Weapons, Steam Workshop 2443122116 (about 3.66 GB, version 1.28.1, last updated 2026-10-18).
Code: `tools/package/snafu_optional.py`; data: `tools/package/snafu_allowlist.json`.

### Rights inventory

Primary source: the installed terms file `Readme_Terms/Mod_Terms_Of _Use_DPL_ND.pdf` (6 pages, sha256
`2bb0e30c7b17c487e67151a0a7cf9fc094062b861ecb9e79ff277bfe86696daf`), the DayZ Public License - No
Derivatives (DPL-ND). Relevant clauses:

- Section 2(a)(1): the license grants rights to "reproduce and Share the Licensed Material ... for
  NonCommercial and DAYZOnly purposes only" and to produce but "not Share Adapted Material".
- Section 3(a): sharing requires attribution, a notice that refers to the license and "indicate if You
  modified the Licensed Material"; "You do not have permission under this Public License to Share Adapted
  Material."
- Section 2(a)(5)(b): "No downstream restrictions".

Secondary sources (the web page is read after the installed PDF):

- Workshop page https://steamcommunity.com/sharedfiles/filedetails/?id=2443122116 and the Steam API record
  https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/ (item 2443122116; the page
  itself was rate-limited, so the API description was read). The description repeats the DPL-ND text and
  adds author conditions: use on a server "provided it is not repackaged or redistributed"; monetized
  servers and commercial use "only with prior written permission"; no modification, repackaging or
  redistribution of PBO content; "You are permitted to create override configuration files for your server
  pack"; "Do not reupload this mod to the Steam Workshop or any other platform", including bundled packs.

Consequences for this project (the stricter reading is applied; this is engineering notes, not legal advice):

- Hollow Country is private, noncommercial and DayZ only. Using the Workshop copy on our own server is the
  intended use.
- No SNAFU file is bundled, copied, vendored, re-hosted or committed: no PBOs, models, textures, vendor
  XML, class dumps, keys or the terms PDF. The repository holds only class names and our own XML numbers
  (an override-style economy delta).
- The delta never ships SNAFU material, so there is no "Adapted Material" to share. Do not add SNAFU files
  to any Hollow Country package, and do not publish a Workshop collection that re-hosts them. A Workshop
  dependency listing (a link) is not a repack.
- Keep the SNAFU author credited if our own pages ever name the optional dependency.
- Monetization of a server using SNAFU needs the SNAFU team's written permission; ours is not monetized.
- If the terms PDF changes, the verifier reports `terms-changed-since-review` and generation stays
  closed until the terms are re-read and the hash in the allowlist is updated on purpose.

### Allowlist (conservative seven, WW2 SMGs, modern military handful)

`snafu_allowlist.json` declares `"status": "unverified"` permanently; verification is per install and lives
in a report outside Git. Owner decision 2026-11-17: keep the conservative seven, add the WW2 submachine guns,
and add a handful of modern high-tier military arms alongside the native M4A1 and friends. The subset is
15 weapons, 6 magazines and 4 SNAFU-specific ammunition types (25 entries).

Conservative seven (unchanged):

| Class | Role | Why |
| --- | --- | --- |
| `SNAFUMarlin1895` | wood, rare | Wood-stock lever rifle; `SNAFU_Ammo_45_70mm` |
| `SNAFUSWM629` | modern, rare | S&W 629 revolver; `SNAFU_Ammo_44` |
| `SN_M870` | wood, uncommon | Pump shotgun on the vanilla 12 gauge pool |
| `SN_USP` | modern, uncommon | Service pistol, vanilla .45 ACP plus `SN_USP_Mag` |
| `SNAFU_M48` | wood, uncommon | Wood-stock bolt rifle (WW2 pack folder, conventional); vanilla .308 |
| `SNAFU_Trenchgun` | wood, rare | Wood-stock pump shotgun (WW2 pack folder); vanilla 12 gauge |
| `GCGN_M1Garand` | wood, rare | Wood-stock semi-auto; `GCGN_Ammo_3006` |

Added by the owner decision (all `Military` usage, `Tier3`/`Tier4` value only, rare, nominal 2 / min 1,
lifetime 7200, restock 1800; no civilian usage):

| Class | Role | Magazines | Ammunition |
| --- | --- | --- | --- |
| `SNAFUThompsonMk2` | WW2 SMG | `SNAFUThompsonMk2_30rdMag` | vanilla `Ammo_45ACP` |
| `SNAFUPPSh` | WW2 SMG | `SNAFUPPSh_71rdMag` | `SNAFU_Ammo_762x25` (6 / 4) |
| `SNAFUSten` | WW2 SMG | `SNAFUSten_32rdMag` | vanilla `Ammo_9x19` |
| `SNAFU_AK103A` | modern rifle | vanilla AKM magazines | vanilla `Ammo_762x39` |
| `HK416_Gun` | modern carbine | vanilla STANAG | vanilla `Ammo_556x45` |
| `SCAR_Gun` | modern rifle | vanilla STANAG | vanilla `Ammo_556x45` |
| `SNAFU_MPX_GUN` | modern SMG | `SNAFU_MPX_30rnd_Mag` | vanilla `Ammo_9x19` |
| `SNHK417_Gun` | modern battle rifle | `SNHK417_Mag` | vanilla `Ammo_308Win` |

The five new SNAFU magazines are rare 3 / 2 (lifetime 14400). Nothing futuristic is allowlisted.
`excluded` in the file records what stays out and why: futuristic and modular tactical rifles and PDWs (ACR,
AUG, TAR-21, Vector, P90, KH9), anti-materiel and heavy snipers, machine guns, the other pack automatics
(PPSKN, Uzi, M1A, M14), exotic or novelty weapons (Alligator, TP-82, Vikhr, VSS, Lynx), reskins of vanilla
weapons (SN_AKM, SN_Glock19, SNAFU_SKS, SN_M9), `SNAFU_M70` (magazine array includes `Mag_AKM_Drum_TEST`) and
the modern arms considered but not chosen (`GCGN_HK416`, `MK18_Gun`, `SNAFU_CZ805_Gun`, `SNAFUSA80`,
`SNAFU_G3A3` and `SG552_Gun` which are not in the vendor types list, `GCGN_MP7` and `SNAFU_KAC_Gun` which need
a second foreign ammunition economy, `GCGN_Vityaz`, `SNAFU_SR25_Gun`).

### Verifier and fail-closed generation

```
python3 -m tools.package.snafu_optional verify --install <SNAFU Workshop folder> \
        --out ~/.cache/hollow-country/snafu-verify-<date>/verification.json
python3 -m tools.package.snafu_optional generate --source <stock mission copy> \
        --report <verification.json> --out <new delta dir>
```

`verify` is read only and bounded (64 PBOs, header and `config.bin` members only, 8 MiB limits on the
terms file and vendor XML; symlinks refused). Per class it checks: defined in the right `Cfg*` root;
defined in exactly one PBO; `scope` resolves to 2 or more; the model exists in a PBO; the class is in the
vendor `XML_and_Clasnames/SNAFU_types.xml`; every allowlisted magazine is accepted and verified; every
listed ammunition is in `chamberableFrom` and (for SNAFU ammunition) has a defined bullet class. Install
level checks: `meta.cpp` `publishedid`, at least one PBO, terms hash. Result per class is `verified`,
`missing` (not defined) or `unverified` (defined, check failed, with reasons).

Dependency updates (#183): with `hc61.class_pins`, a Workshop update that changes whole PBOs but leaves every
pinned class unchanged does not fail `verify`. If `dependency_pins` are still recorded, each changed, added or
removed PBO is listed as `install warning: HC61_DEPENDENCY_UPDATED:<pbo>` (also in the report as
`install.warnings` and `dependency_changed: true`); a pinned-class change still fails with
`HC61_SUBSET_PIN_DRIFT:<class>`. Whole-PBO hashes are cached by absolute path, size and mtime_ns in
`~/.cache/hollow-country/pbo-hash/` (override `HC_HASH_CACHE_DIR`); a corrupt cache is ignored, and a file
modified in the last two seconds is not cached. Nothing observed in DayZ yet.

`generate` refuses unless the report is for this exact allowlist hash, has no install problems, a matching
terms hash and every class individually `verified`. It writes complete new `types.xml` entries (flags and
category set from our own template, usage/value from the allowlist) into the separate managed folder
`hollow-country-snafu/ce`. It refuses classes that stock or the vanilla roster already define.

Real-install result (2026-11-17, `~/.cache/hollow-country/snafu-verify-2026-11-17-r2/verification.json`, 11
PBOs, `publishedid` 2443122116, terms hash matches): 25 of 25 verified, 0 missing, 0 unverified. For the eight
added weapons: each is defined in one `CfgWeapons` class with `scope` 2, its model path exists in a PBO, it is
listed in the vendor `SNAFU_types.xml`, every allowlisted magazine is defined with `scope` 2 and is accepted
by the weapon, and every listed ammunition is in `chamberableFrom`. `GCGN_M1Garand` carries the note
`empty-magazine-entry-ignored` (its magazine array is `['']`). Negative controls (a class absent from the
install, a wrong ammunition, a changed terms hash) turn the report `unverified` and generation refuses.
This is static: it shows the names, scope, models and ammo links exist in the installed files, not that a
weapon fires, loads, spawns or balances.

### Dependency, install, update and rollback

- Required on the server and every client that joins: subscribe to SNAFU Weapons (about 3.66 GB) and load
  it alongside Hollow Country. Players who skip it cannot load a server that requires it, and the items
  cannot work without it; signature behaviour with a signed server is unobserved. The base Hollow Country addon never references SNAFU and works
  without it (enforced by a test); running without SNAFU simply means not installing the delta.
- Install is offline and private: generate, then `install --delta <dir> --target <stopped private mission
  copy>`. Install requires the stock files to match the report sources, and works on top of the roster delta.
- Rollback is last in first out: `snafu_optional rollback` first, then `firearms rollback`. An out of order
  roster rollback is refused (core drift). Rollback restores the previous `cfgeconomycore.xml` byte for
  byte (tested, and on a copy of the real stock files).
- Update: when the Workshop item updates, re-run `verify` on the server copy; if any class is not `verified`
  do not regenerate. Remove the delta (`rollback`) if a class disappears, then re-curate the allowlist.

## 3b. Datamined non-weapon items (economy delta)

`tools/package/datamined_items.json` lists unused-but-finished vanilla clothing, bags and tools
(55 rows: Leather jackets/shoes/hats/shirt, hunting and winter gear, Drysacks, Iceaxe, FilteringBottle,
CrabCan and extras) with modest rare budgets. `economy.generate` emits them as complete-entry rows in the
managed `hollow-country/ce/types.xml`, beside any profile `add_usage` rows.

- Only nominal, min, lifetime, restock, usage and value change. Flags, cost and quantities stay
  stock-identical; `economy.install_delta` refuses any other change. The category is never changed; it is
  added only to `FilteringBottle` (the one row whose stock entry has none), and only as `tools`, both named in
  `economy.CATEGORY_ADDED`; any other category name is refused.
- Three Bandana rows have no stock entry and are listed in the report but not emitted (install refuses types
  stock lacks). Leather pants and storage vests are craft outputs and are not rows.
- Every row is `acceptance: pending-local`; the report repeats it. Switch all rows off with
  `economy generate --no-datamined` (or `include_datamined=False`).
- One delta, one install. The profile, the firearms roster and these rows are composed by one generate and
  installed and rolled back once, because every Hollow Country delta uses the single managed folder
  `hollow-country/ce` (a second install fails the source-hash check):

  ```
  python3 -m tools.package.economy generate --source <stock mission copy> --profile <profile.json> \
      --roster tools/package/firearms_roster.json --out <new delta dir>
  python3 -m tools.package.economy install  --delta <delta dir> --target <stopped private mission copy>
  python3 -m tools.package.economy rollback --target <that mission copy>
  ```

  `python3 -m tools.package.firearms generate --with-items [--profile <profile.json>] ...` produces the same
  composed delta; without `--with-items` it stays roster-only. Both CLIs install and roll back through the same
  code. `economy.generate(..., roster=...)` is the library entry.
- Switches: `--no-datamined` (economy) leaves the datamined non-weapon items out; the roster's datamined
  weapon and magazine rows are left out by `--no-roster-datamined` (economy) or `--no-datamined` (firearms).
- Generation refuses a class that two sources would both change (profile `add_usage`, roster entry, datamined
  item), case-insensitively, before anything is written.
- Per-class install permissions come from the manifest: profile rows stay usage-only, roster rows
  (`firearms_classes`) may also change nominal, min, lifetime, restock and value, datamined item rows
  (`datamined_classes`, each must be a shipped row) the same. Flags, cost and quantities are stock-identical for
  all of them. Mutable tags are compared only as direct `<type>` children; a nested child inside a retained
  tag (for example `<flags><nominal/></flags>`) is a change and is refused.
- `economy.install()` called directly keeps its usage-only default. Rollback is byte-exact and keeps the
  hard-link and outside-path refusals.
- The SNAFU delta keeps its own managed folder and still installs on top of the composed delta (rollback last
  in, first out).
- Pending: CE spawn of rows with stock nominal 0 is unobserved, including Leather and Drysack rows whose
  stock flags carry `crafted="1"`; per-row local acceptance; 3-6 player budgets.

## 4. Tactical Flava (optional)

Item: Tactical Flava (TF), Steam Workshop 2646817942, installed read-only on the operator machine and read
from there. We never repack, copy, bundle or re-host any TF file; the repository holds only TF class names and
our own economy numbers. Code: `tools/package/tactical_flava_optional.py`; data:
`tools/package/tactical_flava_allowlist.json`; tests: `tests/unit/test_tactical_flava_optional.py`. Config is
read with the extended `tools/audit/pbo_config.py` (rapified `config.bin` plus the plain-text `config.cpp` that
the `weapon_a` addon ships).

### Rights: rights review pending

The installed item has no licence file. The only static file we hash is the vendor `extra files/readme.txt`
(sha256 `c42804ca177e504668f253e0459894e27959615387f87d8fef5723534455c0fc`), which is a readme and not a
licence. The Steam page forbids monetisation and repacks and is silent on using the item as a dependency. The
rights review is pending; the allowlist records `license: none-recorded`, `redistribution: none`,
`dependency_use: unstated`, `review: pending`. Nothing is bundled and a hosted server must not depend on TF
until the owner finishes that review. Verification fails closed if the readme hash changes.

### Curated subset (owner KEEP list)

Lifetime and restock follow the SNAFU convention: weapons and optics 7200/1800, magazines 14400/0. Counts are
nominal/min and proposals only.

| Class | nominal/min | Usage | Value |
|---|---|---|---|
| `TF_AK74M` | 4/2 | Military | Tier2 Tier3 |
| `TF_M1A_Black` | 5/2 | Village Hunting | Tier3 Tier4 |
| `TF_M14_STD` | 3/1 | Military | Tier3 Tier4 |
| `TF_VPO190` | 8/4 | Village Hunting Farm | Tier2 Tier3 |
| `TF_MP443` | 8/4 | Military Police | Tier2 Tier3 |
| `TF_M24` | 2/1 | Military | Tier4 |
| `TF_ElcanSpecterDROptic_Black` | 3/1 | Military | Tier3 Tier4 |
| `TF_ElcanSpecterDROptic_FDE` | 2/1 | Military | Tier3 Tier4 |
| `TF_ElcanSpecterDR_6xOptic_Black` | 2/1 | Military | Tier3 Tier4 |
| `TF_ElcanSpecterDR_6xOptic_FDE` | 1/0 | Military | Tier3 Tier4 |
| `TF_Mag_M14_10Rnd` | 12/6 | Military Hunting | Tier3 Tier4 |
| `TF_Mag_M14_20Rnd` | 6/3 | Military | Tier3 Tier4 |
| `TF_Mag_VPO190_4Rnd` | 10/5 | Village Hunting Farm | Tier2-4 |
| `TF_Mag_MP443_18Rnd` | 8/4 | Military Police | Tier2 Tier3 |
| `TF_Mag_AK74_Bakelit30Rnd` | 8/4 | Military | Tier2-4 |
| `TF_M14_Adapter` | 0/0 | attachment-only | Military Tier3 Tier4 |

`TF_M24` has no entry in TF's own types file, so ours is authored here. Every weapon uses vanilla loose ammo
that is already in stock types (`Ammo_545x39`, `Ammo_308Win`, `Ammo_9x19`); the verifier checks each TF magazine
bullet equals a vanilla loose-ammo bullet that the weapon lists in `chamberableFrom`. PKM, the machine guns,
anti-materiel and `.338` rifles, TF-only ammunition, launchers, the 9x39 and specops guns, SCAR/SR25/MK47 and the
near-vanilla AK and M4A1 families, the grenades, other optics and NVGs, armour and camo stay cut; the allowlist
`excluded` list records each with its reason.

### M14 adapter (`weaponDMRAdapter`)

`TF_M14_STD` lists the attachment slots `weaponWrap`, `suppressorImpro`, `weaponDMRAdapter`, `weaponOptics` and
`weaponOpticsHunting`. The TF script `TF_M14_DMR_Base.CanReceiveAttachment` refuses every optic unless the
`weaponDMRAdapter` slot holds an adapter, so `TF_M14_STD` cannot mount any Elcan without `TF_M14_Adapter`. The
adapter is therefore in the allowlist as an attachment-only entry (nominal 0, `fits: [TF_M14_STD]`, and
`optic_requires: [TF_M14_Adapter]` on the rifle). `TF_M1A_Black` has no adapter slot and takes optics directly.
`TF_M24` has no `weaponOptics` slot, so the Elcan `fits` lists are `TF_AK74M`, `TF_M1A_Black`, `TF_M14_STD`.
Current source correction: `tactical_flava_optional._spawnable_types` authors the adapter pre-attachment.
The earlier missing-spawnabletypes gap is closed in source; native assembly and optics acceptance remain pending.

### Script-risk census (unobserved at runtime)

Loading any TF addon pulls in its scripts. Static census of `script_a`, `grenades_a`, `clothing_a` and
`weapon_a`; dropping `grenades_a` is impossible because it shares `script_a`, so everything below loads
regardless of the allowlist.

| ID | Severity | Finding |
|---|---|---|
| S1 | high | `Optics.c` modded `M4_CarryHandleOptic`/`BUISOptic.CanPutAsAttachment` returns true only for `TF_M4A1_Base`/`TF_M16A4_Base` parents, so a vanilla M4A1 may lose its BUIS and carry handle |
| S2 | high | `Vanilla_M4.c` and `AKM_Vanilla.c`: `M4A1_Base`/`AKM_Base.CanReceiveAttachment` skip `super` and can null-dereference |
| S3 | medium | `Weapon_Base.SetActions` adds flip/bipod actions to every weapon; the vanilla Mosin9130 gets bipod actions and `BoltActionBipodRecoil` |
| S4 | medium | `PlayerBase` attachment hooks run for all players |
| S5 | medium | `DayZPlayerImplementAiming.CalculateWeight` override with an unsafe cast |
| S6 | medium | `DayZGame.FirearmEffects` explosive-ammo hook (inert unless explosive ammo spawns) |
| S7 | medium | grenades stack: net-sync variables `m_TFTeargasLevel` and `m_TFWPState` on `PlayerBase`/`ZombieBase`, `MDF_PHOSPHORUS` 616, `MDF_TEARGAS` 617, `NTF_TFPOISONED` 42, PPE requesters, 12 vanilla knives with `CutOutBurningShard` actions |
| S8 | low | `SmershBag` inverted cargo check |
| S9 | low | 10 armour-camo recipes plus `OpenZinkBox` always registered |
| S10 | low | keybinds `UAToggleBipod` (T), `UAToggleMagni` (I), `UAToggleVisor` (L); `weapon_a` redefines `UAToggleBipod` on T inside TF |
| S11 | low | HAMR power modded `DayZPlayerImplement` |
| S12 | low | `TF_Magazines.c` `AmmoData` is commented out by an unterminated comment |
| C1 | high | `clothing_a` appends `Shoulder`, `Melee` and `Shoulder1..30` slots to vanilla `Rifle_Base` |
| C2 | high | `weapon_a` replaces attachment arrays of vanilla M4A1, AK74, AK101, AKM and Mosin9130, and the magazine arrays of the FAL, Aug, M16A2 and AK74 bases |
| C3 | low | boots `IsHighBoots`, `PlateCarrierVest` mappack and `ImprovisedSuppressor` slots |
| N1 | info | no RPCs registered |

### Collision check against Hollow Country

Static check of `mods/HollowCountry` against TF:

- No modifier or notifier use in our scripts, so no collision with `MDF_PHOSPHORUS` 616, `MDF_TEARGAS` 617 or
  `NTF_TFPOISONED` 42. No `RegisterNetSyncVariable` or `SetSynchDirty`, so no net-sync name or ID collision.
- Our only keybind is `UAHollowCountryEvents` on `O`; TF binds T, I and L. Overlap with vanilla keybindings
  is unchecked offline.
- Our RPC IDs are 4853701-3 (groups) and 4853801-2 (events); TF registers none.
- Same-method overlaps: `ZombieBase.EEKilled`, `ActionConstructor.RegisterActions`, and recipe registration
  (`RegisterRecipies`, TF on `PluginRecipesManagerBase`, ours on `PluginRecipesManager`). Every override on both
  sides calls `super`; stacking order depends on load order and is untested.
- TF also overrides `ZombieBase` constructor/`CommandHandler`/`OnVariablesSynchronized`, `PlayerBase`
  `Init`/`EEKilled`/`OnVariablesSynchronized`/`EOnPostFrame`/`CanReceiveAttachment`/`CanReleaseAttachment`/
  `EEItemAttached`/`EEItemDetached`, and `DayZGame.FirearmEffects`; we do not override those.

Result: no ID, keybind or RPC collision found; the residual risks are the stacked overrides and the unchecked
vanilla keybind overlap.

### Local-session checks (pending, with TF loaded)

1. A vanilla M4A1 still takes its BUIS and carry handle (S1).
2. Vanilla Mosin and AK attachments still work (C2) and the Mosin gains no stray bipod actions (S3).
3. T, I and L do not collide with vanilla or Hollow Country keys (S10, `UAToggleBipod`).
4. `ZombieBase.EEKilled` and `ActionConstructor.RegisterActions` stack with ours without errors in the script log.
5. `TF_M14_STD` with `TF_M14_Adapter` accepts an Elcan; `TF_M24`, `TF_VPO190`, `TF_MP443` and `TF_AK74M` fire, load and spawn.
6. Rifle slot changes (C1) leave vanilla rifles and clothing behaving normally.

### Verification, install and rollback

- `verify --install <Workshop item> --vanilla-addons <DayZ Addons> --out <dir>/verification.json` reads
  the install read-only, and the evidence file records per class `verified` or the failing reasons: defined once,
  scope 2, model present, magazines accepted by the weapon, magazine bullet equal to a vanilla loose-ammo bullet,
  vanilla ammo in `chamberableFrom`, optic/attachment slot present on every `fits` weapon, and `optic_requires`.
  Append (`+=`) arrays are reported, never treated as full replacements. Paths in reports are printed with `~`.
- `generate` refuses unverified, drifted or colliding input (classes already in stock, the roster or SNAFU) and
  writes only our own `types.xml` delta. `install` composes on top of the roster and SNAFU deltas.
- Rollback is last in first out: `tactical_flava_optional rollback` first, then `snafu_optional rollback`, then
  `firearms rollback`. Out-of-order SNAFU or roster rollback is refused while TF is installed (core drift). TF rolls back
  by restoring the previous `cfgeconomycore.xml` byte for byte (tested). When a TF update changes the item,
  re-run `verify`; if any class is not `verified`, do not regenerate; the owner rolls back and re-curates.
- Static verification shows names, scope, models and ammo links; it does not show that anything fires, loads,
  spawns or balances. Runtime acceptance stays pending.

## 5. Pending, honestly

- No native/local acceptance for any roster or SNAFU entry: normal PBO/server load, CE spawn and error
  trials, firing and ammo acceptance per weapon, 3-6 player counts.
- Every datamined row (`acceptance: pending-local`) needs local acceptance before any production use, or the
  owner switches them off with `--no-datamined`. The nine parent-derived weapon variants are authored in the candidate; none has native functional acceptance.
- Ordinary loot keeps the owner's approximately 2x target. Firearm family caps and ammo ceilings are separate provisional budgets; effective spawn totals are unobserved.
- The roster nominals are proposals; effective CE merging and world totals are unobserved.
- The SNAFU class list rests on one version (1.28.1); the verifier must be re-run on the real server copy.
- Signed packaging of the roster/SNAFU deltas and signature handling for a signed server are pending.
- The census can see no event-only classes from files; event/carrier activity at runtime is unobserved.
- Offline checks never establish DayZ behaviour; no single-client behaviour was exercised.
- Tactical Flava: rights review pending (no licence file); the script-risk census and collision check are static
  and the local-session checks above are unrun; the authored M14 adapter pre-attach needs native acceptance; all numbers are
  proposals and no runtime acceptance exists.
