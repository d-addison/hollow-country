# Vanilla firearm test abundance (HC-21)

The owner’s 2026-11-20 **3× vanilla/stock** decision supersedes r4’s 1.5–2×
profile. Test abundance ships default-on. These are CE configuration budgets;
spawn, loading, firing and target-load acceptance remain pending. Acceptance uses
one server and at most one client; 3–6-player budgets remain provisional.

`economy_profile` in `tools/package/firearms_roster.json` selects `test-abundance`
(default) or `scarcity`. The embedded `scarcity_policy` retains its historical
entries and caps unchanged. Regenerate and reinstall through the bundle flow;
editing deployed JSON does not replace XML or reset CE storage.

The inspected stock mission has **906 weapon nominal**, including 13 crossbows.
The brief’s 444 is the historical scarcity proposal, not vanilla stock. Every positive-stock
weapon row receives exactly **3× its own native nominal and min**. Zero-stock or
absent recolours use their reviewed native parent row as the baseline; this adds
**1,110 nominal** separately from the native rows’ **2,718**. The justification on
each roster entry names that parent. LeeEnfield, MP18 and Luger have entirely
zero-stock families, so their historical authored baselines (12/8, 4/2, 6/4) receive
3× separately: **66 nominal**. The enabled total is **3,894**, of which **3,855 are
firearms** and 39 crossbows. Parent baselines are explicit exceptions, not claimed
positive stock. Family envelopes sum these per-row allowances rather than sharing
a parent budget across recolours.
No positive minimum exceeds its nominal. Family envelopes are recomputed explicitly.

All 78 vanilla weapon rows have explicit usage and tiers. Aug, FAL and M4A1 retain
ContaminatedArea **and** gain Military usage, with Tier3/4 values. SKS_Black and
SKS_Green gain the missing `weapons` category, Military usage and Tier2–4 values.
Only these two named category additions are permitted by both generator and installer;
other native categories, flags, quantities, assemblies and cost remain unchanged.

Positive native magazines, ammo and vanilla attachment support use **3× native
nominal/min**, keeping their stock ratio to the native gun rows. Three zero-stock
reviewed magazines use 3× their historical authored 20-item baseline (60 total);
the stock-absent MakarovPB magazine uses 3× its parent’s 60 (180 total).
Ammo budgets count both loose piles and boxes; their maximum-cartridge envelopes
remain explicit. Restock remains bounded at 300 seconds for guns and 180 for vanilla
support. Shared ammo pools and integral magazines mean item ratios are not per-gun
loadout guarantees.

Both optional allowlists now store the inspected pack’s **own shipped CE nominal/min**
where a row exists. `test_abundance_multiplier: 2.0` applies to guns, magazines and
ammo by default, including the friend installer’s `apply_weapon_packs` path.
CLI `--nominal-scale 1` selects the pack baseline; explicit nominal/tier scales remain
bounded to 0.25–4 effective scale. Existing optics/attachment budgets remain unchanged.
Some concrete verified classes have no shipped CE row: their prior authored baselines
remain explicit exceptions, listed in the rehearsal below. Every selected weapon
and support class retains a positive nominal and a usage route. A deliberate zero requires a reason in the shared zero allowlist; generation
and installed-layer checks refuse silent zeroing or empty usage. Optional
family and shared aggregate validation ceilings cover the supported 4× maximum;
ceilings are validation bounds, not extra spawned items. Both packs still require
matching local verification and ordinary Workshop dependencies; nothing is repacked.

## #314 role routes and fill burst (2026-11-21)

The pack default is now 2× rather than 3×. `military_loot.apply` allocates the
existing military ceilings first, then expands routes. A Military firearm gains
Police access without escaping its shared scarcity budget or assigned military
tier. This changes CE rows only; no point geometry or container capacities change.

Role routes derive from the selected weapon's existing role/usage and class family,
then from magazine, ammo, `optic_requires` and attachment `fits` edges. Hunting
weapons and archery gain Farm/Town/Village and tiers 1–4; police-role weapons and
Police-only native families gain Prison (the native Scout establishes the prison
firearm role). Recolours share their family's routes. Support receives the union
of carrier routes and tiers while retaining existing routes. Ammo compatibility
alone does not turn a military rifle into a hunting rifle: receiver role matters.
The explicit role-to-usage rules are in `military_loot.role_routes`; there is no
per-pack firearm-name exception table. Custom library policies stay unchanged.

Pack types retain native firearm semantics: category `weapons`, no item tag
restriction. This admits matching vanilla floor/shelf/ground containers; adding
a new category or a restrictive shelf tag would incorrectly remove valid points.
Native variants preserve their donor's category/tags. The offline coverage census
checks positive nominals, map-count flags, usage, category, explicit tag intersection,
placed group tiers and positive point/container/group capacity. It does not test
item fit or engine random selection. Use `python3 -B -m tools.package.ce_slot_pressure
<mission> --coverage` for the census and uncovered container records.

Offline rehearsal retains the current local build-138 registration order and all
other type layers, substituting only owned CE rows. Coverage below uses the stock
native point geometry; pressure uses the current installed geometry. All 726 selected
modded classes remain positive and have at least one compatible placed vanilla
group/container/tier. A class may appear in multiple usages; these are eligibility
counts, not spawned populations.

| Vanilla usage | Before | After |
| --- | ---: | ---: |
| Coast | 0 | 0 |
| ContaminatedArea | 0 | 0 |
| Farm | 1 | 208 |
| Firefighter | 0 | 0 |
| Historical | 0 | 0 |
| Hunting | 40 | 209 |
| Industrial | 0 | 0 |
| Lunapark | 0 | 0 |
| Medic | 0 | 0 |
| Military | 693 | 693 |
| Office | 0 | 0 |
| Police | 128 | 691 |
| Prison | 0 | 130 |
| School | 0 | 0 |
| SeasonalEvent | 0 | 0 |
| Town | 28 | 210 |
| Village | 41 | 210 |

The installed geometry gives the same coverage counts except Police before is 133.

Peak `ce_slot_pressure` estimate: **0.681 before → 0.668 after**, below the **0.80**
limit, with no pressure problems. The new peak is 14,185 nominal / approximately
21,220 slots; this is a shared broad route set, not a military-only count. A separate
fresh scratch install verified all 501 SNAFU and 204 TF classes against the real
installed dependencies, generated/installed both layers, and passed the exact
`check_weapon_packs` receipt and reverse-rollback check used by `friend_install --check`.
The actual deployed mission was not modified; the lead must reapply the new bundle
before running the complete friend-install check. No DayZ process was started.

The census deliberately reports zero for usages with no selected firearm/support
analogue; it does not assign guns to medical, school, office, industrial, firefighter
or coastal points merely to fill a table. The inspected native `weapons` rows also
have no positive stock routes in those usages. Non-weapon categories in hunting
or police groups remain outside these firearm tools' scope. Native fill experiments
remain pending: compare minute 0–1 `LootRespawner ... is hard to place, performance
drops` counts against build 135's 24,382; inspect deer stands/cabins, police and
military points with one server and at most one client. No runtime claim follows
from the offline pressure gate passing.

<!-- HC21-GENERATED-BEGIN -->
## Current authored family policy

Generated from `tools/package/firearms_roster.json`: 77 weapon classes, 53 weapon families, 49 magazine classes and 47 ammo sources (loose, boxed, tracer and specialist).

Weapon nominal ceiling: **3684**; with datamined rows omitted: **2479**. These are provisional CE proposals for 3–6 players; runtime acceptance remains pending.

| Family | Nominal / min cap | Explicit member shares (nominal / min) |
| --- | --- | --- |
| Mosin9130 | 465 / 366 | `Mosin9130` 135/105; `Mosin9130_Woodland` 60/51; `Mosin9130_Black` 135/105; `Mosin9130_Winter` 135/105 |
| SKS | 228 / 162 | `SKS` 4/2; `SKS_Woodland` 5/3; `SKS_Black` 1/1; `SKS_Desert` 5/3; `SKS_Green` 1/1; `SKS_Winter` 1/1 |
| Izh18 | 150 / 141 | `Izh18` 150/141 |
| Izh18Shotgun | 165 / 150 | `Izh18Shotgun` 165/150 |
| Izh43Shotgun | 90 / 78 | `Izh43Shotgun` 90/78 |
| Repeater | 90 / 72 | `Repeater` 90/72 |
| Winchester70 | 63 / 45 | `Winchester70` 21/15; `Winchester70_Black` 21/15; `Winchester70_Green` 21/15 |
| CZ527 | 450 / 411 | `CZ527` 75/69; `CZ527_Woodland` 75/66; `CZ527_Camo` 75/69; `CZ527_Green` 75/69; `CZ527_desert` 75/69; `CZ527_winter` 75/69 |
| B95 | 162 / 126 | `B95` 54/42; `B95_Black` 54/42; `B95_Green` 54/42 |
| LeeEnfield | 36 / 24 | `LeeEnfield` 36/24 |
| MP18 | 12 / 6 | `MP18` 12/6 |
| Luger | 18 / 12 | `Luger` 18/12 |
| SVD | 24 / 12 | `SVD_Wooden` 1/1; `SVD` 1/1 |
| Mp133Shotgun | 30 / 24 | `Mp133Shotgun` 30/24 |
| Magnum | 78 / 63 | `Magnum` 75/60; `Magnum_Gold` 3/3 |
| AKM | 9 / 6 | `AKM` 1/1 |
| Colt1911 | 93 / 72 | `Colt1911` 78/66; `Engraved1911` 15/6 |
| Makarov | 210 / 180 | `MakarovIJ70` 210/180 |
| P1 | 150 / 138 | `P1` 150/138 |
| Glock19 | 120 / 105 | `Glock19` 120/105 |
| FNX45 | 42 / 36 | `FNX45` 42/36 |
| CZ75 | 60 / 54 | `CZ75` 60/54 |
| Ruger1022 | 105 / 75 | `Ruger1022` 105/75 |
| M16A2 | 12 / 6 | `M16A2` 1/1 |
| AK74 | 18 / 12 | `AK74` 1/1 |
| MP5K | 48 / 39 | `MP5K` 48/39 |
| Saiga | 36 / 30 | `Saiga` 5/3 |
| AK101 | 12 / 6 | `AK101` 1/1 |
| AKS74U | 24 / 15 | `AKS74U` 1/1 |
| ASVAL | 9 / 6 | `ASVAL` 1/1 |
| Aug | 3 / 3 | `Aug` 3/3 |
| AugShort | 12 / 9 | `AugShort` 1/1 |
| CZ550 | 42 / 36 | `CZ550` 42/36 |
| CZ61 | 15 / 12 | `CZ61` 15/12 |
| Crossbow | 39 / 21 | `Crossbow_Autumn` 15/9; `Crossbow_Black` 15/9; `Crossbow_Wood` 9/3 |
| Deagle | 90 / 75 | `Deagle` 75/69; `Deagle_Gold` 15/6 |
| Derringer_Grey | 60 / 45 | `Derringer_Grey` 60/45 |
| FAL | 6 / 3 | `FAL` 6/3 |
| FAMAS | 24 / 18 | `FAMAS` 5/3 |
| LongHorn | 75 / 60 | `LongHorn` 75/60 |
| M14 | 6 / 3 | `M14` 1/1 |
| M4A1 | 3 / 3 | `M4A1` 3/3 |
| M79 | 9 / 3 | `M79` 9/3 |
| MKII | 90 / 81 | `MKII` 90/81 |
| PM73Rak | 15 / 12 | `PM73Rak` 15/12 |
| PP19 | 42 / 33 | `PP19` 42/33 |
| R12 | 18 / 15 | `R12` 18/15 |
| SSG82 | 36 / 30 | `SSG82` 36/30 |
| SV98 | 6 / 3 | `SV98` 1/1 |
| Scout | 18 / 12 | `Scout` 3/3; `Scout_Chernarus` 15/9 |
| UMP45 | 36 / 30 | `UMP45` 36/30 |
| VSS | 18 / 12 | `VSS` 1/1 |
| Vikhr | 12 / 6 | `Vikhr` 1/1 |

### Cartridge ceilings

Each nominal/min is multiplied by `unit_rounds`: native pile maximum or box resource count. Detachable magazines have separate item budgets; loaded rounds and carrier throughput remain unmeasured.

| Ammo family | Nominal / min maximum cartridges | Sources |
| --- | --- | --- |
| Ammo_762x54 | 6420 / 4500 | `Ammo_762x54` 180/135 × 20; `AmmoBox_762x54Tracer_20Rnd` 21/9 × 20; `AmmoBox_762x54_20Rnd` 45/36 × 20; `Ammo_762x54Tracer` 75/45 × 20 |
| Ammo_762x39 | 10200 / 7080 | `Ammo_762x39` 300/210 × 20; `AmmoBox_762x39Tracer_20Rnd` 21/9 × 20; `AmmoBox_762x39_20Rnd` 54/45 × 20; `Ammo_762x39Tracer` 135/90 × 20 |
| Ammo_308Win | 6420 / 4080 | `Ammo_308Win` 150/90 × 20; `AmmoBox_308WinTracer_20Rnd` 21/9 × 20; `AmmoBox_308Win_20Rnd` 60/45 × 20; `Ammo_308WinTracer` 90/60 × 20 |
| Ammo_22 | 21750 / 16500 | `Ammo_22` 270/210 × 50; `AmmoBox_22_50Rnd` 165/120 × 50 |
| Ammo_12gaSlug | 3600 / 2400 | `Ammo_12gaSlug` 300/195 × 10; `AmmoBox_12gaSlug_10Rnd` 60/45 × 10 |
| Ammo_12gaPellets | 3600 / 2700 | `Ammo_12gaPellets` 300/225 × 10; `AmmoBox_00buck_10rnd` 60/45 × 10 |
| Ammo_45ACP | 7125 / 4875 | `Ammo_45ACP` 225/150 × 25; `AmmoBox_45ACP_25rnd` 60/45 × 25 |
| Ammo_9x19 | 9750 / 7125 | `Ammo_9x19` 300/225 × 25; `AmmoBox_9x19_25rnd` 90/60 × 25 |
| Ammo_357 | 7200 / 4800 | `Ammo_357` 270/195 × 20; `AmmoBox_357_20Rnd` 90/45 × 20 |
| Ammo_380 | 12600 / 10500 | `Ammo_380` 300/255 × 35; `AmmoBox_380_35rnd` 60/45 × 35 |
| Ammo_556x45 | 6120 / 3780 | `Ammo_556x45` 150/90 × 20; `AmmoBox_556x45Tracer_20Rnd` 21/9 × 20; `AmmoBox_556x45_20Rnd` 60/45 × 20; `Ammo_556x45Tracer` 75/45 × 20 |
| Ammo_545x39 | 4560 / 2400 | `Ammo_545x39` 75/39 × 20; `AmmoBox_545x39Tracer_20Rnd` 27/15 × 20; `AmmoBox_545x39_20Rnd` 51/36 × 20; `Ammo_545x39Tracer` 75/30 × 20 |
| Ammo_12gaRubberSlug | 1680 / 1350 | `AmmoBox_12gaRubberSlug_10Rnd` 48/30 × 10; `Ammo_12gaRubberSlug` 120/105 × 10 |
| Ammo_9x39 | 2940 / 1740 | `AmmoBox_9x39AP_20Rnd` 15/6 × 20; `AmmoBox_9x39_20Rnd` 21/9 × 20; `Ammo_9x39` 66/42 × 20; `Ammo_9x39AP` 45/30 × 20 |
| Ammo_40mm_Chemgas | 15 / 9 | `Ammo_40mm_Chemgas` 15/9 × 1 |
| Ammo_40mm_Explosive | 24 / 15 | `Ammo_40mm_Explosive` 24/15 × 1 |
| Ammo_40mm_Smoke_Black | 45 / 24 | `Ammo_40mm_Smoke_Black` 45/24 × 1 |
| Ammo_40mm_Smoke_Green | 45 / 24 | `Ammo_40mm_Smoke_Green` 45/24 × 1 |
| Ammo_40mm_Smoke_Red | 45 / 24 | `Ammo_40mm_Smoke_Red` 45/24 × 1 |
| Ammo_40mm_Smoke_White | 45 / 24 | `Ammo_40mm_Smoke_White` 45/24 × 1 |
| Ammo_HuntingBolt | 375 / 270 | `Ammo_HuntingBolt` 75/54 × 5 |

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
`sum(nominal * unit_rounds)` and `sum(min * unit_rounds)`. Boxes, tracer and AP rows use the selected native-based support budgets;
their item counts and maximum-cartridge envelopes are reported separately. Native `quantmin/quantmax`, flags,
cost, loading, firing and repair definitions are retained. Categories remain native except
the two explicitly reviewed missing SKS categories described above. Placement and restock follow the selected authored profile. Magazines retain
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

## 2026-11-20 r5 scratch rehearsal

Read-only inputs: the installed mission’s native CE files, recorded rollback inputs,
and each local pack’s shipped types XML and verifier evidence. The installed bundle’s
full rollback refused unrelated `db/events.xml` drift. On the scratch copy only, the
recorded bundle receipt supplied the baseline core; CE inputs were recovered from
validated earlier-layer backups. The live mission was never written.

The native copied stock nominal total is 21,090. Table baselines for optional packs
include the explicitly authored missing-row exceptions below. Vanilla support baselines
exclude the separately stated absent/zero-row allowances. Weapon totals include crossbows.

| Layer | Kind | Native/shipped baseline | r4 proposal | r5 default |
| --- | --- | ---: | ---: | ---: |
| vanilla | weapon | 906 | 2,009 | 3,894 |
| vanilla | magazine | 624 | 2,204 | 2,112 |
| vanilla | ammo | 1,615 | 4,845 | 4,845 |
| vanilla | attachment | 372 | 1,164 | 1,116 |
| SNAFU | weapon | 197 | 352 | 591 |
| SNAFU | magazine | 178 | 1,273 | 534 |
| SNAFU | ammo | 14 | 352 | 42 |
| SNAFU | attachment | 6,887 | 6,887 | 6,887 |
| TF | weapon | 313 | 336 | 939 |
| TF | magazine | 249 | 890 | 747 |
| TF | ammo | 93 | 168 | 279 |
| TF | attachment | 5,383 | 5,383 | 5,383 |

Across all three layers: weapons **2,697 → 5,424** (+2,727), magazines
**4,367 → 3,393** (−974), ammo item/pile rows **5,365 → 5,166** (−199),
attachments **13,434 → 13,386** (−48). Net CE nominal change from r4: **+1,506**.
The resulting aggregate ratios are 0.626 magazine items and 0.952 loose/boxed ammo
items per weapon nominal; compatible sources are checked per gun, not inferred from
aggregate ratios. Ammo and magazine scaling is 3× each positive baseline, matching
gun-row scaling; quantities and carrier throughput remain engine-owned.

The checked-in 470-row CE overlay preserves every unrelated row and changes total
nominal **10,673 → 12,418** (+1,745). Fresh combined economy plus both optional layers
has effective CE nominal **45,079** before ordinary loot boost, versus native-only
**21,090** (+23,989, including existing non-weapon and attachment policies). With
ordinary 2× loot boost and the main r4 geometry, effective nominal is **61,245**
(+40,155 versus unboosted native-only); that boost does not multiply roster gun/support
budgets again. These sums describe file overrides, never observed world populations.

### Missing shipped CE rows

These exceptions use the prior authored nominal/min as a baseline, multiplied by 3.
No native or vendor nominal is claimed for them.

| Pack | Class | Authored baseline nominal/min | Default nominal/min |
| --- | --- | ---: | ---: |
| SNAFU | `SNAFUMDAR_30rndMagB` | 8/4 | 24/12 |
| SNAFU | `SNAFUMDAR_30rndMagT` | 8/4 | 24/12 |
| SNAFU | `SNAFUMDAR_60rndMagB` | 8/4 | 24/12 |
| SNAFU | `SNAFUMDAR_60rndMagT` | 8/4 | 24/12 |
| SNAFU | `SNAFU_Bren_30rdMag` | 8/4 | 24/12 |
| SNAFU | `SNAFU_G3A3_20rdMag` | 8/4 | 24/12 |
| SNAFU | `SNAFU_M60_100rdMag` | 8/4 | 24/12 |
| SNAFU | `SG552_Gun` | 2/1 | 6/3 |
| SNAFU | `SN_AKM` | 2/1 | 6/3 |
| SNAFU | `SNAFUDSASA58_Gun` | 2/1 | 6/3 |
| SNAFU | `SNAFU_M4556_Modular10_GUN` | 2/1 | 6/3 |
| SNAFU | `SNAFU_M4556_Modular14DV_GUN` | 2/1 | 6/3 |
| SNAFU | `SNAFUMDARSBR_Black` | 2/1 | 6/3 |
| SNAFU | `SNAFUMDARSBR_Green` | 2/1 | 6/3 |
| SNAFU | `SNAFUMDARSBR_Tan` | 2/1 | 6/3 |
| SNAFU | `SNAFUMDARCAR_Black` | 2/1 | 6/3 |
| SNAFU | `SNAFUMDARCAR_Green` | 2/1 | 6/3 |
| SNAFU | `SNAFUMDARCAR_Tan` | 2/1 | 6/3 |
| SNAFU | `SNAFUMDARRIF_Black` | 2/1 | 6/3 |
| SNAFU | `SNAFUMDARRIF_Green` | 2/1 | 6/3 |
| SNAFU | `SNAFUMDARRIF_Tan` | 2/1 | 6/3 |
| SNAFU | `SNAFU_AK5C` | 2/1 | 6/3 |
| SNAFU | `SNAFU_BR18` | 2/1 | 6/3 |
| SNAFU | `SNAFU_Bren` | 2/1 | 6/3 |
| SNAFU | `SNAFU_G3A3` | 2/1 | 6/3 |
| SNAFU | `SNAFU_M60` | 2/1 | 6/3 |
| SNAFU | `SNAFU_RDB` | 2/1 | 6/3 |
| SNAFU | `SNAFU_M70` | 2/1 | 6/3 |
| TF | `TF_Mag_SWORD_Mk18_10Rnd` | 18/9 | 54/27 |
| TF | `TF_Ammo_40mm_HEDP` | 48/24 | 144/72 |
| TF | `TF_M24` | 6/3 | 18/9 |
| TF | `TF_SWORD_Mk18_Mjolnir` | 6/3 | 18/9 |

### Rehearsal output tail

Base `economy.generate/write_delta/install_delta` and optional
`apply_weapon_packs` are the friend bundle’s existing entry points. The final
rehearsal also completed reverse-stack rollback and reinstall with matching reports.

```text
base economy generate/install PASS
optional weapons SNAFU: verify verified types=501
optional weapons SNAFU: generate types=501 firearm_nominal=591
optional weapons SNAFU: installed; receipt and rollback backup written; runtime=PENDING
optional weapons TF: verify verified types=206
optional weapons TF: generate types=206 firearm_nominal=939
optional weapons TF: installed; receipt and rollback backup written; runtime=PENDING
reverse-stack rollback PASS
friend base economy entry points PASS 3894
loot install PASS
vanilla weapons 78 min/median 401 1744
SNAFU firearms 176 min/median 401 1744
TF firearms 56 min/median 401 1744
under20 []
REHEARSAL PASS runtime=PENDING
```

Full `shipped_points()` currently refuses **81 overlapping groups** between
`additions.json` and `additions-interiors.json`. Those files belong to other workers.
The successful geometry rehearsal explicitly used the requested main r4
`additions.json` plus current receivers/floor policy. The full friend geometry install
remains blocked until the lead reconciles that overlap; it is not called accepted.

### Eligible prototype points per weapon

Counted from the final stock prototype plus main r4 additions and receivers using
`loot_boost.plan/install` and `loot_floor_policy._scan/_matches`: positive group and
container capacity, category intersection, usage intersection and retagged shelf
eligibility. Counts are unique prototype point opportunities, not multiplied by
building placements. Map area tiers, dynamic-event semantics, clearance and actual
native spawn acceptance are unobserved. Min/median: **401 / 1,744** in each layer;
all 310 weapon rows exceed 20. Vanilla includes three crossbows.

| Layer | Weapon | Eligible proto points |
| --- | --- | ---: |
| vanilla | `Mosin9130` | 401 |
| vanilla | `Mosin9130_Woodland` | 401 |
| vanilla | `SKS` | 1,744 |
| vanilla | `SKS_Woodland` | 1,744 |
| vanilla | `Izh18` | 401 |
| vanilla | `Izh18Shotgun` | 401 |
| vanilla | `Izh43Shotgun` | 401 |
| vanilla | `Repeater` | 401 |
| vanilla | `Winchester70` | 401 |
| vanilla | `CZ527` | 401 |
| vanilla | `CZ527_Woodland` | 401 |
| vanilla | `B95` | 401 |
| vanilla | `LeeEnfield` | 401 |
| vanilla | `MP18` | 515 |
| vanilla | `Luger` | 2,355 |
| vanilla | `SKS_Black` | 1,744 |
| vanilla | `SKS_Desert` | 1,744 |
| vanilla | `SKS_Green` | 1,744 |
| vanilla | `SKS_Winter` | 1,744 |
| vanilla | `Mosin9130_Black` | 401 |
| vanilla | `Mosin9130_Winter` | 401 |
| vanilla | `SVD_Wooden` | 1,744 |
| vanilla | `Mp133Shotgun` | 401 |
| vanilla | `Magnum` | 2,355 |
| vanilla | `AKM` | 1,744 |
| vanilla | `Colt1911` | 2,355 |
| vanilla | `MakarovIJ70` | 2,355 |
| vanilla | `P1` | 2,355 |
| vanilla | `Glock19` | 2,355 |
| vanilla | `FNX45` | 2,355 |
| vanilla | `CZ75` | 2,355 |
| vanilla | `Ruger1022` | 2,355 |
| vanilla | `M16A2` | 1,744 |
| vanilla | `AK74` | 1,744 |
| vanilla | `MP5K` | 515 |
| vanilla | `Saiga` | 1,744 |
| vanilla | `SVD` | 1,744 |
| vanilla | `MakarovPB` | 2,355 |
| vanilla | `Winchester70_Black` | 401 |
| vanilla | `Winchester70_Green` | 401 |
| vanilla | `B95_Black` | 401 |
| vanilla | `B95_Green` | 401 |
| vanilla | `CZ527_Camo` | 401 |
| vanilla | `CZ527_Green` | 401 |
| vanilla | `CZ527_desert` | 401 |
| vanilla | `CZ527_winter` | 401 |
| vanilla | `AK101` | 1,744 |
| vanilla | `AKS74U` | 1,744 |
| vanilla | `ASVAL` | 1,744 |
| vanilla | `Aug` | 1,744 |
| vanilla | `AugShort` | 1,744 |
| vanilla | `CZ550` | 401 |
| vanilla | `CZ61` | 515 |
| vanilla | `Crossbow_Autumn` | 2,355 |
| vanilla | `Crossbow_Black` | 2,355 |
| vanilla | `Crossbow_Wood` | 2,355 |
| vanilla | `Deagle` | 2,355 |
| vanilla | `Deagle_Gold` | 2,355 |
| vanilla | `Derringer_Grey` | 2,355 |
| vanilla | `Engraved1911` | 2,355 |
| vanilla | `FAL` | 1,744 |
| vanilla | `FAMAS` | 1,744 |
| vanilla | `LongHorn` | 2,355 |
| vanilla | `M14` | 1,744 |
| vanilla | `M4A1` | 1,744 |
| vanilla | `M79` | 1,744 |
| vanilla | `MKII` | 2,355 |
| vanilla | `Magnum_Gold` | 2,355 |
| vanilla | `PM73Rak` | 515 |
| vanilla | `PP19` | 515 |
| vanilla | `R12` | 1,744 |
| vanilla | `SSG82` | 401 |
| vanilla | `SV98` | 1,744 |
| vanilla | `Scout` | 1,744 |
| vanilla | `Scout_Chernarus` | 1,744 |
| vanilla | `UMP45` | 515 |
| vanilla | `VSS` | 1,744 |
| vanilla | `Vikhr` | 1,744 |
| SNAFU | `GCGN_BenelliM4` | 401 |
| SNAFU | `GCGN_HK416` | 1,744 |
| SNAFU | `GCGN_M110_Black` | 1,744 |
| SNAFU | `GCGN_M110_Green` | 1,744 |
| SNAFU | `GCGN_M110_Tan` | 1,744 |
| SNAFU | `GCGN_M1Garand` | 2,252 |
| SNAFU | `GCGN_M200` | 1,744 |
| SNAFU | `GCGN_M200_Tan` | 1,744 |
| SNAFU | `SNAFU_M200Green` | 1,744 |
| SNAFU | `SNAFU_M200SNOW` | 1,744 |
| SNAFU | `GCGN_M249` | 1,744 |
| SNAFU | `GCGN_M700` | 401 |
| SNAFU | `GCGN_M82_Barret` | 1,744 |
| SNAFU | `GCGN_MP7` | 2,252 |
| SNAFU | `GCGN_Vepr` | 401 |
| SNAFU | `GCGN_Vityaz` | 2,252 |
| SNAFU | `AA12_Gun` | 1,744 |
| SNAFU | `ACR_Gun` | 1,744 |
| SNAFU | `HK416_Gun` | 1,744 |
| SNAFU | `SNHK417_Gun` | 1,744 |
| SNAFU | `IA2_Gun` | 1,744 |
| SNAFU | `MK18_Gun` | 1,744 |
| SNAFU | `SNSA58_Gun` | 1,744 |
| SNAFU | `SCAR_Gun` | 1,744 |
| SNAFU | `SG550_Gun` | 1,744 |
| SNAFU | `SG552_Gun` | 1,744 |
| SNAFU | `Spas12_Gun` | 1,744 |
| SNAFU | `Tec9_Gun` | 2,252 |
| SNAFU | `VR80_Gun` | 1,744 |
| SNAFU | `SNAFU_AK103A` | 1,744 |
| SNAFU | `SNAFU_AK12A` | 1,744 |
| SNAFU | `SNAFU_AK19` | 1,744 |
| SNAFU | `SNAFU_AK308` | 1,744 |
| SNAFU | `SN_Auto_Shotgun` | 1,744 |
| SNAFU | `SN_Glock19` | 2,252 |
| SNAFU | `SN_M870` | 401 |
| SNAFU | `SN_M9` | 2,252 |
| SNAFU | `SN_Mp443` | 2,252 |
| SNAFU | `SNAFU_PDW_9mm` | 1,744 |
| SNAFU | `SNAFU_PDW_45ACP` | 1,744 |
| SNAFU | `SNAFU_PL14HQP` | 2,252 |
| SNAFU | `SNAFU_RPK16_Black` | 1,744 |
| SNAFU | `SNAFU_RPK16_Green` | 1,744 |
| SNAFU | `SNAFU_RPK16_Tan` | 1,744 |
| SNAFU | `SN_Springfield` | 2,252 |
| SNAFU | `SNAFU_TP82S` | 401 |
| SNAFU | `SN_USP` | 2,252 |
| SNAFU | `SNAFU_AEK545_Gun` | 1,744 |
| SNAFU | `SN_AKM` | 1,744 |
| SNAFU | `SNAFU_AWM_GUN` | 1,744 |
| SNAFU | `SNAFU_CZ805_Gun` | 1,744 |
| SNAFU | `SNAFU_KAC_Gun` | 1,744 |
| SNAFU | `SNAFU_Agram_GUN` | 2,252 |
| SNAFU | `SNAFU_AS50_GUN` | 1,744 |
| SNAFU | `SNAFU_CALI_GUN` | 1,744 |
| SNAFU | `SNAFU_Fort12_GUN` | 2,252 |
| SNAFU | `SNAFU_MP9_GUN` | 2,252 |
| SNAFU | `SNAFU_MPX_GUN` | 2,252 |
| SNAFU | `Snafu_PKP_Black_GUN` | 1,744 |
| SNAFU | `Snafu_PKP_NBlack_GUN` | 1,744 |
| SNAFU | `SNAFUAX50_GUN` | 1,744 |
| SNAFU | `SNAFUM24_GUN` | 1,744 |
| SNAFU | `SNAFUM98B_Atac_GUN` | 1,744 |
| SNAFU | `SNAFUM98B_Digi_GUN` | 1,744 |
| SNAFU | `SNAFUM98B_Ger_GUN` | 1,744 |
| SNAFU | `SNAFUM98B_Mc_GUN` | 1,744 |
| SNAFU | `SNAFUM98B_Snow_GUN` | 1,744 |
| SNAFU | `SNAFUM98B_Wood_GUN` | 1,744 |
| SNAFU | `SNAFURSASS_Wood_GUN` | 1,744 |
| SNAFU | `SNAFURSASS_od_GUN` | 1,744 |
| SNAFU | `SNAFURSASS_dkmc_GUN` | 1,744 |
| SNAFU | `SNAFUT5000_Dkmcc_GUN` | 1,744 |
| SNAFU | `SNAFUT5000_Snow_GUN` | 1,744 |
| SNAFU | `SNAFUT5000_Wood_GUN` | 1,744 |
| SNAFU | `SNAFUVECTOR_9mm_GUN` | 2,252 |
| SNAFU | `SNAFUVECTOR_45acp_GUN` | 2,252 |
| SNAFU | `SNAFU_SR25_Gun` | 1,744 |
| SNAFU | `SNAFU_ADAR_Modular16_GUN` | 1,744 |
| SNAFU | `SNAFU_AR15_Modular16_GUN` | 1,744 |
| SNAFU | `SNAFUDSASA58_Gun` | 1,744 |
| SNAFU | `SNAFU_LVOA556_GUN` | 1,744 |
| SNAFU | `SNAFU_M300BK` | 1,744 |
| SNAFU | `SNAFU_M300TAN` | 1,744 |
| SNAFU | `SNAFU_M300Green` | 1,744 |
| SNAFU | `SNAFU_M4300AC_10_GUN` | 1,744 |
| SNAFU | `SNAFU_M4300AC_14_GUN` | 1,744 |
| SNAFU | `SNAFU_M4300AC_16_GUN` | 1,744 |
| SNAFU | `SNAFU_M4300AC_14DV_GUN` | 1,744 |
| SNAFU | `SNAFU_M4556_Modular10_GUN` | 1,744 |
| SNAFU | `M4_6933_Gun` | 1,744 |
| SNAFU | `SNAFU_M4556_Modular14_GUN` | 1,744 |
| SNAFU | `SNAFU_M4556_Modular16_GUN` | 1,744 |
| SNAFU | `SNAFU_M4556_Modular14DV_GUN` | 1,744 |
| SNAFU | `GCGN_M4A1` | 1,744 |
| SNAFU | `SNAFUMDARSBR_Black` | 1,744 |
| SNAFU | `SNAFUMDARSBR_Green` | 1,744 |
| SNAFU | `SNAFUMDARSBR_Tan` | 1,744 |
| SNAFU | `SNAFUMDARCAR_Black` | 1,744 |
| SNAFU | `SNAFUMDARCAR_Green` | 1,744 |
| SNAFU | `SNAFUMDARCAR_Tan` | 1,744 |
| SNAFU | `SNAFUMDARRIF_Black` | 1,744 |
| SNAFU | `SNAFUMDARRIF_Green` | 1,744 |
| SNAFU | `SNAFUMDARRIF_Tan` | 1,744 |
| SNAFU | `SNAFU_MK4710Gun` | 1,744 |
| SNAFU | `SNAFU_MK4716Gun` | 1,744 |
| SNAFU | `SNAFU_Saint556_Gun` | 1,744 |
| SNAFU | `SNAFU_Saint_Gun` | 1,744 |
| SNAFU | `SNAFU_AR15SPRBK` | 1,744 |
| SNAFU | `SNAFU_AR15SPRTAN` | 1,744 |
| SNAFU | `SNAFUAR15_SPR_Black_GUN` | 1,744 |
| SNAFU | `SNAFUAR15_SPR_Tan_GUN` | 1,744 |
| SNAFU | `SNAFUVSSK` | 1,744 |
| SNAFU | `SNAFUKivaari_Black_GUN` | 1,744 |
| SNAFU | `SNAFUKivaari_Tan_GUN` | 1,744 |
| SNAFU | `SNAFUKivaari_Grey_GUN` | 1,744 |
| SNAFU | `SNAFUKivaari_Snow_GUN` | 1,744 |
| SNAFU | `SNAFU_MAR10_Black_GUN` | 1,744 |
| SNAFU | `Snafu_ScarH_Black_GUN` | 1,744 |
| SNAFU | `Snafu_ScarH_DKMC_GUN` | 1,744 |
| SNAFU | `Snafu_ScarH_OD_GUN` | 1,744 |
| SNAFU | `Snafu_ScarH_Snow_GUN` | 1,744 |
| SNAFU | `Snafu_ScarH_Tan_GUN` | 1,744 |
| SNAFU | `SNAFUSR3_Vikhr` | 1,744 |
| SNAFU | `SR3_Vikhr_Gun` | 1,744 |
| SNAFU | `SNAFU_AK5C` | 1,744 |
| SNAFU | `SNAFU_BR18` | 1,744 |
| SNAFU | `SNAFU_Bren` | 1,744 |
| SNAFU | `SNAFUChiappaRhino` | 2,252 |
| SNAFU | `SNAFU_G3A3` | 1,744 |
| SNAFU | `SNAFU_M60` | 1,744 |
| SNAFU | `SNAFUPPSh` | 2,252 |
| SNAFU | `SNAFU_RDB` | 1,744 |
| SNAFU | `SNAFURPD` | 1,744 |
| SNAFU | `SNAFUSten` | 2,252 |
| SNAFU | `SNAFUSWM629` | 2,252 |
| SNAFU | `SNAFUMagnum500` | 2,252 |
| SNAFU | `SNAFUAlligator` | 1,744 |
| SNAFU | `SNAFUAPS` | 2,252 |
| SNAFU | `SNAFUTAR21_Black` | 1,744 |
| SNAFU | `SNAFUTAR21_Tan` | 1,744 |
| SNAFU | `SNAFUTAR21_Green` | 1,744 |
| SNAFU | `SNAFUASh12` | 1,744 |
| SNAFU | `SNAFUAUG` | 1,744 |
| SNAFU | `SNAFUAUG_BK` | 1,744 |
| SNAFU | `SNAFUDVL10M2` | 1,744 |
| SNAFU | `SNAFUFAMAS` | 1,744 |
| SNAFU | `SNAFUGevar_Grey` | 1,744 |
| SNAFU | `SNAFUGevar_Black` | 1,744 |
| SNAFU | `SNAFUGevar_Green` | 1,744 |
| SNAFU | `SNAFUGevar_Tan` | 1,744 |
| SNAFU | `SNAFUGM6Lynx` | 1,744 |
| SNAFU | `SNAFUHoneyBadger_Black` | 1,744 |
| SNAFU | `SNAFUHoneyBadger_Tan` | 1,744 |
| SNAFU | `SNAFUKH9` | 1,744 |
| SNAFU | `SNAFUM1A_Black` | 401 |
| SNAFU | `SNAFUM1A_Green` | 401 |
| SNAFU | `SNAFUM1A_Tan` | 401 |
| SNAFU | `SNAFUM96` | 1,744 |
| SNAFU | `SNAFUMarlin1895` | 401 |
| SNAFU | `SNAFUMk12` | 1,744 |
| SNAFU | `SNAFUP90` | 1,744 |
| SNAFU | `SNAFUPPSKN` | 2,252 |
| SNAFU | `SNAFUSA80` | 1,744 |
| SNAFU | `SNAFUSRSA2` | 1,744 |
| SNAFU | `SNAFUTac21` | 1,744 |
| SNAFU | `SNAFUThompsonMk2` | 2,252 |
| SNAFU | `SNAFUUzi` | 2,252 |
| SNAFU | `SNAFU_M1918A2` | 2,252 |
| SNAFU | `SNAFU_M70` | 1,744 |
| SNAFU | `SNAFU_U100` | 1,744 |
| SNAFU | `SNAFU_M14` | 1,744 |
| SNAFU | `SNAFU_M76` | 1,744 |
| SNAFU | `SNAFU_SKS` | 1,744 |
| SNAFU | `SNAFU_Trenchgun` | 401 |
| SNAFU | `SNAFU_FRF2` | 1,744 |
| SNAFU | `SNAFU_M48` | 401 |
| TF | `TF_ADAR2_15` | 401 |
| TF | `TF_AK101` | 1,744 |
| TF | `TF_AK102` | 1,744 |
| TF | `TF_AK103` | 1,744 |
| TF | `TF_AK104` | 1,744 |
| TF | `TF_AK105` | 1,744 |
| TF | `TF_AK105_Bullpup` | 1,744 |
| TF | `TF_AK74M` | 1,744 |
| TF | `TF_AKM` | 1,744 |
| TF | `TF_AKMN` | 1,744 |
| TF | `TF_AKS74U` | 1,744 |
| TF | `TF_AN94` | 1,744 |
| TF | `TF_AN94M` | 1,744 |
| TF | `TF_Anzio20` | 1,744 |
| TF | `TF_FiveSeven` | 2,252 |
| TF | `TF_M14_DMR` | 1,744 |
| TF | `TF_M14_EBR` | 1,744 |
| TF | `TF_M14_STD` | 1,744 |
| TF | `TF_M1A_Black` | 401 |
| TF | `TF_M1A_OD` | 401 |
| TF | `TF_M1A_Tan` | 401 |
| TF | `TF_M4A1` | 1,744 |
| TF | `TF_M4A1_CQBR` | 1,744 |
| TF | `TF_M79` | 1,744 |
| TF | `TF_M79_AOR1` | 1,744 |
| TF | `TF_MAR10` | 1,744 |
| TF | `TF_SCAR_L_FDE` | 1,744 |
| TF | `TF_SCAR_L_Black` | 1,744 |
| TF | `TF_SCAR_L_CQC_FDE` | 1,744 |
| TF | `TF_SCAR_L_CQC_Black` | 1,744 |
| TF | `TF_SCAR_H_FDE` | 1,744 |
| TF | `TF_SCAR_H_Black` | 1,744 |
| TF | `TF_SCAR_H_CQC_FDE` | 1,744 |
| TF | `TF_SCAR_H_CQC_Black` | 1,744 |
| TF | `TF_SCAR_20_FDE` | 1,744 |
| TF | `TF_SCAR_20_Black` | 1,744 |
| TF | `TF_SCAR_20_Shd` | 1,744 |
| TF | `TF_MK47_CQBR` | 1,744 |
| TF | `TF_MK47` | 1,744 |
| TF | `TF_MP443` | 2,252 |
| TF | `TF_OTs_12_Tiss` | 1,744 |
| TF | `TF_OTs_14_Groza` | 1,744 |
| TF | `TF_MakarovPB` | 2,252 |
| TF | `TF_VPO136` | 401 |
| TF | `TF_VPO190` | 401 |
| TF | `TF_AEK999` | 1,744 |
| TF | `TF_M16A4` | 1,744 |
| TF | `TF_M240` | 1,744 |
| TF | `TF_M249` | 1,744 |
| TF | `TF_PKM` | 1,744 |
| TF | `TF_PKP` | 1,744 |
| TF | `TF_SR25` | 1,744 |
| TF | `TF_SVCh308` | 1,744 |
| TF | `TF_SVCh` | 1,744 |
| TF | `TF_M24` | 1,744 |
| TF | `TF_SWORD_Mk18_Mjolnir` | 1,744 |

The four scoped existing Python modules ran 197 checks; seven assertions retain
r4 fixed shares/floors, half-min assumptions or positive support-row assumptions and
fail under the new stock-based policy. Their files are outside this worker’s edit
scope; the lead must update those expectations. No Enforce changed, so native compile
and performance gates were not run. Neither this rehearsal nor Python checks
establishes DayZ spawns, firing, loading, single-client or multiplayer behaviour.

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
`tools/package/tactical_flava_allowlist.json`; tests: `tests/slow/test_tactical_flava_optional.py`. Config is
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
- Ordinary loot keeps the owner's approximately 2x target. The default 3× native firearm family and support budgets above remain provisional; effective spawn totals are unobserved.
- The roster nominals are proposals; effective CE merging and world totals are unobserved.
- The SNAFU class list rests on one version (1.28.1); the verifier must be re-run on the real server copy.
- Signed packaging of the roster/SNAFU deltas and signature handling for a signed server are pending.
- The census can see no event-only classes from files; event/carrier activity at runtime is unobserved.
- Offline checks never establish DayZ behaviour; no single-client behaviour was exercised.
- Tactical Flava: rights review pending (no licence file); the script-risk census and collision check are static
  and the local-session checks above are unrun; the authored M14 adapter pre-attach needs native acceptance; all numbers are
  proposals and no runtime acceptance exists.
