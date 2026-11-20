# CE encounter events

Authored 2026-11-20 for ChernarusPlus 1.30. **Native acceptance is pending.**
These scenes use the Central Economy's existing event lifecycle and loot placement.
There is no scripted loot generator, inventory transfer, new AI controller or
runtime module. They are default-on when the installer is wired into the bundle.
The active server installation was inspected read-only and has not been changed.

| Event (`StaticHC` prefix) | Nominal | Candidate anchors | Scene |
| --- | ---: | ---: | --- |
| ConvoyAmbush | 3 | 20 | Ural, abandoned UAZ, weapons and ration crates, wreck scars |
| ArmorRecovery | 2 | 20 | BMP, recovery Ural, weapons and ration crates, wreck scars |
| SupplyTruck | 2 | 20 | Ural, two weapons crates, medical and ration cargo |
| PoliceEvidence | 2 | 20 | Police wreck, abandoned UAZ, seized weapons and supplies |
| PrisonTransfer | 2 | 20 | Abandoned bus, police escort, weapons and medical cargo |
| BanditCache | 2 | 20 | Abandoned UAZ, two weapons crates, rations and medical cargo |
| SniperExtraction | 2 | 20 | Abandoned BRDM, weapons, medical and ration cargo |
| FieldHospital | 2 | 20 | Ural, UAZ, two medical crates, guarded weapons and ration cargo |
| TransportDown | 4 | 20 | UH-1Y crash, scattered weapons, medical and ration cargo |
| CargoSpill | 3 | 20 | Mi-8 crash, two weapons crates, medical and ration cargo |
| **Total** | **24** | **200** | **10 groups, 62 authored object entries** |

The 24 is the sum of the *new* event nominals, additional to stock events. It is a
target population, not an observed concurrent count. Each family has a 40- or
45-minute lifetime, 500 m safe radius, 800 m distance radius and 1000 m cleanup
radius, using the installed stock event field names. CE availability, players,
cleanup and persistence can reduce the actual population. Secondary populations
are disabled explicitly (`spawnsecondary="false"`, zero zone ranges); existing
stock encounters remain untouched apart from the anchor transfer described below.

## Evidence and geographic limits

`ce/hc-event-sites.json` records the exact original stock event and position
attributes for every anchor. All 200 coordinates are distinct, with minimum
separation 358.3 m. Sixty come from the installed `StaticHeliCrash` pool, providing
existing crash-clearance evidence for field scenes; 140 come from
`StaticPoliceCar`, providing existing roadside-wreck evidence. Selection spreads
anchors across Chernarus and excludes static contamination radii plus a 100 m
margin, using the installed `cfgeffectarea.json` as authoring evidence.

These are **200 new HC spawn registrations at existing vanilla locations**, not
200 newly surveyed geographic locations. The installer transfers them out of the
two source pools so stock and HC events cannot both select the same anchor. It
requires each original position to match exactly and leaves at least ten positions
in each source pool. On the inspected mission this leaves 35 helicopter and 160
police-car positions. All other event positions remain semantically unchanged.
Total mission position count stays 1647; the HC pool grows from zero to 200.

Stock roadside anchors establish that a wreck was intended there; they do not
prove clearance for the entire authored composition. The relative layouts and
orientations still need native inspection for slopes, roads, doors, floating or
buried objects, and player access. No new terrain coordinates, surface heights or
class-placement APIs were guessed. A C130, rail derailment, corpse props and a
contaminated lab scene are deferred: no surveyed footprint/rail layout or safe
new contamination configuration was established. Existing contaminated areas and
their restricted loot remain unchanged.

Evidence inspected locally:

- Installed `db/events.xml`, `cfgeventspawns.xml`, `cfgeventgroups.xml`,
  `cfgeconomycore.xml`, `mapgroupproto.xml`, `cfglimitsdefinition.xml`,
  `cfgeffectarea.json` and `db/types.xml`.
- The game's `structures_wrecks.pbo` and `structures_military.pbo` CfgVehicles:
  all twelve authored object identities resolve with scope 2. Native prototypes
  exist for the loot-bearing wrecks and all three supply-box variants. Decals
  are decorations with no loot policy.
- Pinned native `CrashBase.c` and helicopter wreck scripts: CE-created crashes
  use the existing engine creation callback and crash sound path. CE's XML
  parser itself is native, so installed working fields are the schema evidence.

Only class names, coordinates, selected point numbers and our authored scene data
ship. No game models, vanilla mission dumps or Workshop data ship.

## Loot ownership and bounds

Every scene contains `StaticObj_Misc_SupplyBox2_DE`. The receipt layer replaces
that existing prototype with `ce/hc-event-proto.xml`: Military usage, Tier3 and
Tier4 values, the weapons category, a shelves tag, and a maximum of three items.
The only three points are the native crate-top points (local height approximately
0.43 m); the installer checks them against the mission's existing point evidence.
No ground points are added. Group-level value selectors are evidenced by installed
Unique-valued prototypes, and Tier3/Tier4 are installed value flags.

This prototype replacement also affects stock uses of this same crate class. Its
stock food/medical sibling prototypes are preserved. Other wreck and supply-box
loot continues to use its native prototype, which can include ground points;
this is not a claim that every object in every scene is floor-free. Every
loot-bearing child uses `deloot="1"`, `lootmin="2"`, `lootmax="3"`. Scene objects
and their loot are bounded by event nominals and native CE accounting.

The crate provides a CE selection route for Tier3/4 military weapons and dynamic
event weapons (the installed SVD row, for example, has `deloot="1"`). It does not
force a particular gun to appear. Types budgets, usage/category/tag compatibility,
dynamic-event eligibility and exhaustion still apply. This worker adds no second
`types.xml` owner and changes no firearm nominal/min or optional weapon-pack data.
Native observation must establish exactly how the event selector combines these
filters. The gun-budget and optional-pack owners must retain compatible Military,
weapons, shelves and event eligibility policy for weapons intended here. Restricted
ContaminatedArea-only weapons are not reassigned by this layer.

## Bundle integration and rollback

`ce/events.xml` keeps its exact vehicle roster because travel validates it as an
exclusive vehicle registry; its only change is an explanatory comment. New CE
definitions live in `ce/hc-events.xml`. The installer merges the authored groups
and positions into the mission-root files and registers exactly one additional
`events.xml` via `cfgeconomycore.xml`.

The lead should include `tools/package/hc_events.py` in `friend_bundle.py`'s
`BUNDLE_TOOLS`, and add these five paths to `tools/package/pbo.py`'s
`MISSION_FILES` allowlist so existing source checks/export include them:

```text
ce/hc-events.xml
ce/hc-eventspawns.xml
ce/hc-eventgroups.xml
ce/hc-event-proto.xml
ce/hc-event-sites.json
```

The **single install call**, with source taken from the bundle's repository-authored
mission files, is:

```python
from tools.package import hc_events
hc_events.install(Path(bundle) / 'mission/hollow-country', mission)
```

Put that call last in both the scratch rehearsal and real apply stack, after
travel, optional overlays, loot boost and map placement overlays. This layer
changes the economy core, event spawns, event groups and group prototypes; later
writers must be reversed before it. The complete composed bundle still needs a
rehearsal by the lead, particularly if another layer removes native crate points.
Missing/different original anchor or point evidence refuses before writing.

Rollback must call `hc_events.rollback(mission)` **first**, before rolling back
those earlier layers. Wire this into bundle rollback, restore-originals and
installed-mission export cleanup as appropriate. These integration files are
outside this worker's scope and are not edited here. The repository currently
ignores new `docs/*` files; the lead must explicitly include `docs/EVENTS.md`
(for example with an allowlist exception in `.gitignore`) when landing it. The current bundle allowlist
will refuse the new sources until the lead adds them; this worktree alone does
not activate events in a built release.

Standalone commands from the repository or unpacked bundle, with the server stopped:

```sh
python3 -B -m tools.package.hc_events plan --mission <isolated-mission>
python3 -B -m tools.package.hc_events install --mission <isolated-mission>
python3 -B -m tools.package.hc_events rollback --mission <isolated-mission>
```

The self-contained `hollow-country-events/receipt.json` stores base64 original
bytes and before/after SHA-256 digests for every changed file. It is durable before
any mission mutation. A repeated complete install is idempotent; source changes
require rollback. Unknown managed files, symlinks, hardlinks and target drift
refuse. Rollback preflights all files before writing, accepts both pre-install and
installed bytes for interrupted-operation recovery, restores all original bytes,
and removes only this layer's generated files and directory. It does not erase
persisted hive entities; stop/restart and normal CE cleanup still apply.

## Scratch rehearsal, 2026-11-20

The installed mission configuration was copied to scratch, excluding hive storage
and logs. No live files were written. Effective event rows below include existing
registered overlays and are not an engine primary-spawner census.

| Measure | Before | Installed | Rolled back |
| --- | ---: | ---: | ---: |
| Effective event XML rows | 78 | 88 | 78 |
| Root event-position definitions | 38 | 48 | 38 |
| Root event groups | 83 | 93 | 83 |
| HC candidate positions | 0 | 200 | 0 |
| HC nominal sum | 0 | 24 | 0 |
| Stock heli candidate positions | 95 | 35 | 95 |
| Stock police-car candidate positions | 300 | 160 | 300 |

Rehearsal output tail:

```text
idempotent True
after effective_event_rows 88 HC_nominal 24
remaining_stock_positions StaticHeliCrash 35
remaining_stock_positions StaticPoliceCar 160
drift_refused encounter target drift: cfgeventgroups.xml True
rollback True byte_exact_all_files True
interrupted_after_write 1 byte_exact_all_files True
interrupted_after_write 3 byte_exact_all_files True
interrupted_after_write 6 byte_exact_all_files True
rehearsal PASS; native boot, placement, loot and lifecycle PENDING
```

CLI install/rollback also passed. Travel's source validator passed with its roster
unchanged. The existing focused `test_hc_travel_roster` run has one pass and two
failures, reproduced with the unchanged HEAD event file: it expects eight vehicle
families where the current roster has nine, and expects an `unreviewed event`
message where current travel raises `incomplete travel roster`. No tests were
added or changed, and no full suite was run. No Enforce code changed.

Still planned: composed-bundle export/install/rollback; native server boot with
no CE errors, crash, stall or enabled-module readiness failure; CE activation and
an observed active count; one-client inspections of every scene family and actual
Tier3/4/event firearm loot; pickup, cleanup, rotation, restart persistence, gas-zone
separation and frame cost. Multiplayer is not proven. The lead must add this
pending acceptance entry to `docs/MODULE_STATUS.md`; that file is outside scope.
