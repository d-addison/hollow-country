# Map overlays

Overlays are native ObjectSpawner JSON plus Central Economy `mapgrouppos.xml` rows.
`config/map-overlays/profile.json` and `layers/` select the sites; the reusable kit
library does not place a site merely by defining it. Features are intended to ship
default-on through the placement profile. No client inventory or scripted loot is used.

## Kits (2026-11-20)

All seven original IDs remain. The catalog grows from 46 to 79 vanilla classes and
from seven to 27 kits. The original library had 103 pieces / 11 loot-bearing pieces;
the complete library now has 488 pieces / 83 loot-bearing pieces. These totals
describe one instance of every kit, not simultaneous deployed objects. The 20 new
kits contain 15–24 pieces each. Every kit, including the original seven, has two
to four objects with installed mission loot prototypes. Original checkpoint,
comms-post and mg-nest kits exchange one wire segment for a guard shelter while
keeping their original piece counts; field-hospital enables its existing shower
prototype. These changes require the placement owner to regenerate affected sites.

| Kit ID | Pieces | CE objects | Tier hint | Story |
| --- | ---: | ---: | ---: | --- |
| `abandoned-checkpoint` | 18 | 3 | 3 | A road inspection team left its paperwork beside a disabled patrol vehicle; staggered barriers and empty supply crates mark an orderly checkpoint that stopped receiving orders. |
| `ammo-dump` | 20 | 4 | 4 | A dispersed ammunition transfer point was abandoned mid-unload; open containers and a cargo truck flank pallet stacks behind blast screens. |
| `bandit-roadblock` | 18 | 3 | 3 | A stolen cargo vehicle and improvised inspection desk turned a rural road into an extortion point; the sleeping shelter sits behind the ambush position. |
| `checkpoint` | 14 | 2 | 3 | A two-lane-wide road checkpoint |
| `comms-post` | 13 | 2 | 4 | A radio post |
| `crashed-convoy` | 20 | 4 | 4 | The lead vehicle veered off the road and the convoy halted under fire; scattered cargo leads from a truck to a hastily established casualty station. |
| `field-hospital` | 13 | 2 | 3 | A medical camp |
| `field-hq` | 21 | 4 | 4 | A command element packed its maps and abandoned the last working radio; the protected signals desk and orderly tent row contrast with a hurried vehicle departure. |
| `fob-compound` | 24 | 4 | 4 | A forward base had settled into routine: a command tent, two sleeping rows and a fortified watch position surround an empty parade and delivery lane. |
| `forward-outpost` | 24 | 2 | 4 | A walled outpost |
| `fuel-depot` | 20 | 3 | 4 | A refuelling detachment left a tanker in the service bay and spare cans at the pump crew desk; guarded storage sits clear of the fuel tanks. |
| `helicopter-lz` | 21 | 4 | 4 | A forward landing zone became a recovery site when the evacuation helicopter crashed beyond its perimeter; ground crew staging survives beside the empty pad. |
| `hunter-camp` | 15 | 3 | 2 | Hunters turned a caravan pull-off into a long stay: a cooking corner, stacked firewood and an observation hide look over the track. |
| `mass-grave-cleanup` | 21 | 3 | 3 | A burial and decontamination detail abandoned its machinery beside a fresh mass grave; triage, wash-down and bagged protective equipment mark the final work shift. |
| `medevac-station` | 19 | 3 | 3 | Casualties were sorted between the triage desk and two treatment tents while an evacuation pickup waited outside; stretchers still line the transfer route. |
| `mg-nest` | 11 | 2 | 4 | A fortified nest with a sandbag arc facing the approach, HBarrier wings, razor wire in front and a crate pair behind |
| `mortar-pit` | 18 | 3 | 4 | An artillery crew withdrew with the weapons but left its revetment, ammunition handling area and plotting station intact. |
| `motor-pool` | 19 | 4 | 4 | A repair and recovery crew cannibalised an APC beside two parked logistics trucks; tools and transit cases remain outside the workshop tent. |
| `overrun-camp` | 21 | 4 | 4 | A tent row was breached at the eastern perimeter; an abandoned APC, skewed furniture and a trail of discarded medical supplies lead out through the gap. |
| `police-blockade` | 16 | 3 | 3 | Police attempted traffic diversion while a military guard team handled detainee screening; two abandoned cruisers and a document desk show where the queue stopped. |
| `quarantine-post` | 20 | 3 | 3 | A roadside screening station separated arrivals from the clean treatment row; a discarded protective bag trail marks the containment breach. |
| `radio-relay` | 20 | 3 | 4 | A remote relay kept broadcasting after the convoy stopped coming; a radar trailer, twin masts and a sheltered operator station dominate the skyline. |
| `refugee-camp` | 20 | 4 | 2 | A bus delivered families to a relief camp that outlived its supplies; folding beds, shared meals and a registration desk remain between two shelter rows. |
| `sniper-overwatch` | 16 | 3 | 4 | An observation team watched the valley from two offset fighting positions; a radio and spare equipment sit behind the covered withdrawal route. |
| `supply-drop-site` | 18 | 3 | 4 | A ground team recovered an air-delivered consignment into open containers, then abandoned the sorting line; separated transit crates trace the movement from drop to truck. |
| `supply-dump` | 15 | 3 | 4 | A fenced supply yard |
| `tent-camp` | 13 | 2 | 3 | Two military tents either side of a central path, a camo-net table area at the back, a sandbag cover line and razor wire at the front, crates and a fuel tank at the edges. |

Tier and threat hints are descriptive placement guidance. They do not override CE
area tiers, prototype usage tags, item `nominal`/`min`, or event budgets. Placement
must put tier 3–4 kits in matching areas, and the economy owner controls weapon
availability. A civilian wreck in a military kit retains its civilian prototype.
Crates, radios, cots and tables are static dressing; loot comes only from pieces
marked `proto`, joined to existing CE prototype groups. No loot is created on an
arbitrary tabletop by these kits. Interior point additions are owned separately.

## Layout contract

Offsets are metres: `dx` right of the site heading, `dz` forward; yaw is relative to
that heading. The new kits use +z as the intended road/arrival approach. Checkpoints
keep a seven metre centre lane, and large camp structures are farther out. The LZ
has a wider empty pad. Nests face the authored approach; tents form separated rows,
vehicles occupy shoulder/service bays, and clutter follows the casualty, cargo or
breach story. Treatment, cooking, generator and fuel areas are separated. Mortar-pit
is a vacated artillery emplacement, without a working weapon or invented class.

`clear` validation checks object centres only. It does not prove model bounds or
that a doorway faces the road. `footprint_reserve_m` in classes.json is a conservative
authoring reserve, explicitly **not measured geometry**. Wide nets, grave meshes,
antenna bases, lamps and irregular wrecks particularly need native inspection.
Furniture is kept outside building doorways and is not placed on unmeasured raised
surfaces. Radios, lights, generators, tanks and vehicles are inert scenery; no
power, navigation, light emission or functional machinery is asserted.

## Installed-data evidence

Read-only CfgVehicles derap used `tools.audit.pbo_config.read_configs` against the
installed vanilla structure PBOs. All 79 entries have a resolved model, scope and
parent recorded; all referenced models were found as .p3d members in the installed
structure PBO indexes. `loot_group` is an exact name join with the installed
Chernarus+ `mapgroupproto.xml`, including false values for dressing. No assets or
config dumps are distributed. Scope 1 world props are retained; inventory visibility
is not required by the native spawner. Definition evidence does not prove spawning.

The inspected native 1.30.164289 `3_Game/ObjectSpawner.c` uses `CreateObjectEx` for
class names and updates the pathgraph. Direct P3D spawning is restricted to its
plants/rocks path allowlist; these kits therefore use class names exclusively.
The spawner enables no-lifetime/static placement by default. CE rows, rather than
the scenery objects, request bounded ordinary economy loot through prototypes.

## Validation and scratch rehearsal

The existing `_validate_compositions`, `validate`, `place_site`, `install` and
`rollback` functions were used without changes to tools/package/map_overlay.py.
All 27 compositions pass spacing, clear-lane, class and exact loot-prototype checks.
The existing `tests.slow.test_map_overlay_compositions` suite passes all 32 checks;
no tests or tooling were changed. `git diff --check` also passes.
Each kit was independently fitted against installed mission baseline group rows,
installed into a private scratch mission copy and rolled back with both installer
inputs SHA-256 identical to their original bytes. Candidate sites may repeat across
these separate exercises: this is installer evidence, not a deployable combined layer.
Mass-grave-cleanup and radio-relay required broader searches around successful
candidate centres, with no relaxed clearance, height or flatness limits.

The live mission already had overlays installed. Rehearsals copied its saved
`hollow-country-overlays/mapgrouppos.backup` and `gameplay.backup` into the scratch
copy, plus installed prototype and economy-core inputs. The live mission was never
written. Validating directly against its current group positions would incorrectly
count existing overlay rows as vanilla obstructions.

Final rehearsal tail:

```text
TOTAL 488 objects 83 CE groups; 27 / 27 kits rehearsed
```

Placement handoff: against that saved pre-overlay baseline, the existing layer
coordinates have six validation errors after the legacy shelter replacements:
`military-outposts-v1/o04` (height spread), `o06` (3.1 m to barracks), `o07`
(height spread and median mismatch), and `roadside-checkpoints-v1/r02`, `r05`
(insufficient height-support rows). Regenerate those sites and reference the new
kit IDs in placement-owned layers. No schema change is required; kits remain
within the current 32-piece validator limit. Physical road direction, line of fire,
doorway access and ground contact still need a native placement survey.

No DayZ boot or client observation was performed for these scenes. Pending gates:
CreateObjectEx success/RPT, terrain and model pivots, collision/doors, pathgraph,
rendering and static lights, actual CE loot eligibility/positions/quantities,
restart behavior and performance at the target 3–6-player load. Acceptance remains
one server plus at most one client; multiplayer behavior is not proven.

## Ground contact (2026-11-22)

`config/map-overlays/ground-contact.json` (kind `hollow-country-overlay-ground-contact`) is a
repository-side sidecar: for each of the 74 overlay classes it records `contact_low_m` (the lowest
visible-LOD point relative to the pivot) and `geometry_low_m` (the lowest geometry-LOD point).
Two classes are listed under `unmeasured` (decals without a readable visual LOD). It is produced by
`tools.audit.world_mesh_audit --contact-out` from the installed models; no model data is shipped.

`tools.package.map_overlay ground` uses it to check every placement offline: class contact plus the
authored `dy` must land within 0.15 m of the ground, or the placement is reported `floating` or
`sunk`. A class with no entry, which is not listed as unmeasured, fails validation. The r1 result was
3,459 OK, 0 floating, 0 sunk, with the 100 decal placements unmeasured.

At runtime `HCGroundSnap` (3_Game/Core) rests the footprint's lowest ground point (3x3 samples)
under the visible bottom. Slope beyond the authored allowance refuses the prop. HC loot follows its
building's shift, and floating HC loot drops onto the surface below. The sidecar is not read at
runtime. Native evidence still pending: `[HC Ground] placement source=object_spawner layers=7 ...
legacy=0`, `[HC Ground] source=ce_ours shifted= retried= settled=`, and an in-game look at a tent,
a camo net and a loot pile.

## Layers (2026-11-20, r5 placement)

All seven layers in `config/map-overlays/profile.json` ship enabled. The r5
refresh preserves **196 site identities** (189 composition sites and seven
standalone military tents). Its starting r4 data expands to **2,826 objects and
415 CE rows**; the earlier 307-row report predates the r4 composition edits.
Every v2 site now uses its `requested_composition`; v1 composition sites upgrade
to the corresponding rich kit wherever the combined placement permits it. The standalone tents retain their vanilla class.
No kit redesign or scripted loot spawning is involved. CE rows still join the
installed vanilla `mapgroupproto.xml`; the economy owns loot and tier eligibility.

| Layer | Sites | Objects, r4 → r5 | CE rows, r4 → r5 |
| --- | ---: | ---: | ---: |
| `civilian-stories-v2` | 56 | 840 → 1046 | 118 → 182 |
| `inland-discoveries-v2` | 42 | 612 → 802 | 90 → 141 |
| `military-outposts-v1` | 9 | 140 → 159 | 18 → 27 |
| `military-tents-v1` | 7 | 7 → 7 | 7 → 7 |
| `military-zones-v2` | 68 | 1024 → 1319 | 146 → 233 |
| `roadside-checkpoints-v1` | 5 | 70 → 82 | 10 → 13 |
| `supply-dumps-v1` | 9 | 133 → 144 | 26 → 28 |
| **Total** | **196** | **2,826 → 3,559** | **415 → 631** |

Placement preserves site IDs and `planning_origin` anchors. It regenerates
positions and headings against the real kit pieces, including o04/o06/o07 and
r02/r05. Named military sites first search within 1,800 m of their named centre. The combined packing search may use alternatives out to 3,000 m when needed;
`area_anchor_distance_m` records the resulting distance. These geographic labels
are not measured military boundaries. Inland finds
prefer the original north/west core (`z >= 7000` and either `x < 6500` or
`z >= 12000`), with a broader interior fallback (`z >= 5000` and either
`x < 12000` or `z >= 12000`).
Civilian scenes may move farther to find evidence supporting their wider kits.

Candidates, 15-degree headings and alternative placement order are deterministic.
A fixed-seed conflict-repair pass (three attempts of 3,000 moves), followed
by bounded backtracking (20,000 nodes, at most 256
alternatives per story site) allocates military v1/v2, inland and civilian sites together. This keeps
large inland kits from losing their scarce flat patches to earlier military
placements. Story alternatives are capped at four per 55 m grid cell. Every piece clears vanilla group origins by
16 m, separate sites retain 55 m between centres, and separate sites' pieces
retain 16 m during planning. Guard candidates are reserved against later props.
Distances from vanilla buildings are origin distances, not measured model bounds.

Each composition records `support_radius_m` (60, 90 or 120 m for military compositions;
60, 75, 90 or 120 m for inland and civilian stories; standalone tents retain
60 or 90 m). Every piece requires
at least three stock group rows inside that radius, no more than 1.5 m height
spread, and no more than 0.8 m deviation from their median. The same radius is
used for the site's support-plane slope limit of 3 percent. The 90 m and 120 m neighbourhoods
allow height support across the wider rich-kit footprints; smaller radii remain
available where larger neighbourhoods cross a height change. The 120 m option
adds candidate patches needed by the complete rich-kit layout; it increases
the distance over which height is inferred, without measuring intervening terrain. Validation rechecks each
piece and guard slot using its site's recorded radius. `placement_evidence`
records the sample count, median, spread, slope proxy and nearest group origin.

These are offline evidence rules. The binary WRP has no decoded terrain raster
or road network available to this tool. `terrain_measured`, `roads_surveyed`,
`prop_bounds_measured` and `guard_navmesh_verified` remain false. Native ground
contact, slope, road clearance, door access, collision, yaw, navigation, CE loot
and target-load cost remain unproven. All layers remain `runtime-unverified`;
no engine experiment is accepted by this refresh.

Military v2 and all four military v1 layers carry `zone_id`, `zone_role`
(`hq`, `perimeter`, `outpost`, `depot`) and 2–6 `guard_slots` per site, including
the standalone tents. Slots lie inside the authored site envelope: the composition footprint, an
explicit `guard_apron_m=8` perimeter allowance for dense legacy layouts when
needed, or within 28 m of a standalone tent. They clear prop origins by 8 m and rotated authored
`footprint_reserve_m` rectangles by a 2 m apron, plus 16 m from vanilla group
origins. Authored reserves are not measured collision boxes. Native navmesh and
physical walkability must be inspected before treating the positions as accepted.

`mission/hollow-country/ai/zones.json` is generated from the enabled layers by
`map_overlay.py`. The top level is exactly `{"zones": [...]}`, matching the runtime
JsonFileLoader DTO; there is no `schema` field. Coordinates are rounded to
0.1 m and the compact file is required to stay below 60 KB. The schema of each
record in `zones` is:

- `id`, `area`: stable slug and display area.
- `center`: selected HQ/outpost site origin `[x,y,z]`, in world metres.
  Prefer HQ, then outpost, depot and perimeter; break ties by distance to the
  mean site position and qualified ID. `radius_m` is the farthest site distance
  plus 60 m, capped at the runtime limit of 2,000 m. This is the patrol influence
  envelope; named cluster membership in `sites` can extend beyond it.
- `tier`: geographic proxy (4 for the higher military areas, otherwise 3), not
  a CE area override.
- `sites`: qualified `layer-id/site-id` references, since v2 layers reuse IDs.
- `guard_slots`: 3–6 authored positions `[x,y,z]` from the selected anchor
  site, supplemented by nearby cluster slots only when needed to reach three.
  The runtime accepts at most eight slots and spawns at most six members. All
  military sites retain their own 2–6 slots in the layer metadata.
- `default_state`: `held`, `overrun` or `abandoned`, an initial state seed.

The catalog contains **17 zones**: **7 held / 6 overrun / 4 abandoned**
(41.2% / 35.3% / 23.5%). Four of six higher-tier zones start held, compared
with three of eleven lower-tier zones. All 98 military sites carry metadata,
with **562 per-site guard candidates**. The runtime catalog selects **98 slots**
across its anchor sites and occupies **7,151 bytes**. Rounded slots are rechecked
against authored prop reserves; four edge candidates are omitted after rounding.
Eighteen site members lie beyond their anchor’s capped 2,000 m patrol radius.
Their layer metadata remains available; expanding runtime influence needs the
zoneguards owner to change its radius contract and revisit overlapping zones.

Zone state seeds use SHA-256 ordering with a 0.3 rank bias toward held
for higher tiers; this increases their held share while retaining higher-tier
overrun zones.
Runtime guards, infected, richer guarded loot and transitions over days belong
to the zone/story workers. Regenerating the source must not reset saved runtime
state. The release bundle copies authored mission JSON from the repo. The zoneguards
module consumes `hollow-country/ai/zones.json` in the mission; subsequent state
belongs to its runtime journal.

Profile caps remain 7,000 objects / 1,200 CE rows overall and 3,500 objects / 600
CE rows per layer. Refreshed layer caps match those bounds. They are packaging
limits; performance budgets remain provisional for the target 3–6 players.

Use a private stock mission copy, rolling back any earlier overlays first:

```bash
python3 -B -m tools.package.map_overlay refresh-plan --mission /tmp/hc-placement/mission --out config/map-overlays/layers --zones-out mission/hollow-country/ai/zones.json
python3 -B -m tools.package.map_overlay validate --mission /tmp/hc-placement/mission
python3 -B -m tools.package.map_overlay report
python3 -B -m tools.package.map_overlay zones --out /tmp/hc-placement/zones.json
python3 -B -m tools.package.map_overlay install --target /tmp/hc-placement/mission
python3 -B -m tools.package.map_overlay rollback --target /tmp/hc-placement/mission
```

`refresh-plan` validates all seven layers against stock rows and installed
prototypes before writing layers or zones. `zones` regenerates only the compact
zone contract. The overlay installer backs up and hashes `cfggameplay.json` and
`mapgrouppos.xml`, writes one spawner per layer, and refuses drift during rollback.
It does not modify the separate authored mission JSON payload. The scratch
mission was recovered from a read-only installed copy using its overlay receipt:
11,679 stock rows, SHA-256
`3eeaad9786a73c339f61f6e6ad203f0732e36b88f27333978cc8b4beece9cec4`.

Rehearsal on the scratch mission (stock row inventory above):

```text
INSTALL spawners=7 objects=3559 CE_rows_added=631 stock_rows=11679 installed_rows=12310
ROLLBACK all_mission_files=byte-exact cfggameplay.json=byte-exact mapgrouppos.xml=byte-exact zones.json=byte-exact
INSTALL repeat=byte-exact; COMPOSE repeat=byte-exact; ZONES regeneration=byte-exact
UNCACHED_REGEN all_7_layers=byte-exact zones.json=byte-exact
ZONE_CONTRACT sample-compatible, 0.1 m coordinates, 7151 bytes, 3..8 slots, radius <= 2000 m
```

All 166 v2 composition sites use their requested rich kit. Twelve of 23 v1
composition sites upgrade; eleven retain their original kit because a compatible
rich alternative does not fit the combined layout. Standalone tents remain seven.
The named o04/o06/o07/r02/r05 placements pass the same per-piece height,
clearance and slope-proxy validation as the complete set.

Focused tooling tests: 69/70 pass, including all 32 composition tests. The sole
failure is the unchanged r4 allowlist assertion in
`tests/slow/test_map_overlay.py:397` (`79 < 60`); its owner must adjust the stale
cap for the 79 reviewed classes. No Enforce files changed and no native compile
or gameplay acceptance is claimed.

`docs/MAP_OVERLAYS.md` is still ignored by the repository's `/docs/*` rule.
The lead must allowlist or explicitly include this assigned document; the
placement worker does not own `.gitignore` or write git metadata.

## v1-test-16 static mesh review

Reviewed 2026-11-24. Offline measurements classify authoring risks, not engine behaviour.

### Placement paths

All 164 contact findings belong to legacy overlay compositions, not interior templates or
new site archetypes. `map_overlay.expand_layer` carries each composition `dy` into the
world position and `_ground_sidecar` copies it to `pivot`. On HC spawner layers,
`ObjectSpawnerHandler.SpawnObject` calls `HCGroundSnap.Place`: target Y is the lowest
footprint terrain plus that pivot. It corrects terrain height, preserving the authored
visible-bottom offset. It refuses non-loot props on excessive slope/height; loot props
can remain at their authored height when correction exceeds 25 m. None of these 164
findings can therefore be dismissed as runtime_corrected.

New site-composer output enters the same spawner and deferred `HCSpawnDeferred` path;
its `site_composer.object_rows` uses surveyed `pieces[id].center_y` (zero if absent),
not a legacy composition dy. There is no independent runtime composer snap.
No current contact finding comes from that path. Interior-template `Spawn` calls
`HCGroundSnap.Snap` after orientation: it uses collision bounds and a downward ray,
with a bounded higher retry for a buried bottom. Success depends on support and
correction bounds; merely calling Snap does not prove visible contact. No current
contact finding comes from an interior template.

### Definite floating fixes

60 `StaticObj_Wreck_MTVR_Cargo` placements used `dy=0.19`. Current full-client visual
contact is -0.033902 m, so the runtime sidecar leaves a 0.156098 m gap. Setting
`dy=0.04` leaves 0.006098 m, inside both audit and composer tolerances. This also
passes the older committed contact reference (-0.187 m, 0.15 m composer tolerance).
The difference between old contact metadata and the current client is retained as
a live-review concern, rather than regenerating unrelated reference classes.

Layers store site references to compositions, not expanded prop rows; production
`map_overlay compose` regenerates the affected spawner rows and their ground sidecars.
No receipt-bearing layer is hand-edited and no site identity or heading is replanned.

| Layer | Keys (all StaticObj_Wreck_MTVR_Cargo) | dy before → after |
| --- | --- | --- |
| overlay:civilian-stories-v2 | s004-p02, s006-p03, s007-p02, s012-p02, s014-p03, s015-p02, s020-p02, s022-p03, s023-p02, s028-p02, s030-p03, s031-p02, s036-p02, s038-p03, s039-p02, s044-p02, s046-p03, s047-p02, s051-p02, s053-p03, s055-p02, s056-p02 | 0.19 → 0.04 |
| overlay:inland-discoveries-v2 | s004-p04, s007-p03, s009-p03, s010-p02, s012-p01, s016-p04, s019-p03, s021-p03, s022-p02, s024-p01, s028-p04, s031-p03, s033-p03 | 0.19 → 0.04 |
| overlay:military-zones-v2 | s004-p04, s007-p03, s009-p03, s010-p02, s012-p01, s016-p04, s019-p03, s021-p03, s023-p01, s027-p04, s029-p03, s031-p03, s032-p02, s034-p01, s036-p04, s039-p03, s042-p04, s046-p03, s047-p01, s051-p03, s052-p02, s061-p03, s063-p01, s066-p01 | 0.19 → 0.04 |
| overlay:supply-dumps-v1 | d08-p03 | 0.19 → 0.04 |

### Sinking placements require a client check

The current full-client minima disagree with the committed contact reference. Tents
may have buried skirts/pegs or below-floor geometry; police wreck visual minima lie
well below their collision minima. Raising them mechanically to the lowest vertex
could float the occupied floor or wheels. There is no authoring evidence that these
104 loot-bearing placements were intentionally buried, and the runtime sidecar does
not eliminate the discrepancy. Each remains `needs_live`, never intended or accepted.

For each identity below, inspect it on one client after its site is admitted, record
`[HC Ground] placement` including legacy/refused counts and the object transform;
check ground contact on level and sloping sides, floor/wheel/step height, entry and
loot reach. Distinguish buried non-walkable skirts or debris from a buried usable
surface. Preserve before/after screenshots and RPT evidence; then classify intended
with authoring evidence, or correct the measured pivot and rerun the audit.

| Class | Current visible minimum / committed reference (m) | Exact live check |
| --- | --- | --- |
| Land_Medical_Tent_Big | -0.831865 / 0.000 | At this exact site/key after ground placement, inspect tent floor, doorway step, pegs and skirt; enter and reach CE loot. Confirm the usable floor is not buried before changing dy. |
| Land_Mil_Tent_Big2_3 | -0.233435 / 0.000 | At this exact site/key after ground placement, inspect tent floor, doorway step, pegs and skirt; enter and reach CE loot. Confirm the usable floor is not buried before changing dy. |
| Land_Mil_Tent_Big4 | -1.253074 / 0.000 | At this exact site/key after ground placement, inspect tent floor, doorway step, pegs and skirt; enter and reach CE loot. Confirm the usable floor is not buried before changing dy. |
| Land_Wreck_Caravan_MGreen | -0.159176 / -0.067 | At this exact site/key after ground placement, inspect wheel/body contact, below-ground debris and CE loot reach. Confirm whether the usable wreck is buried before changing dy. |
| Land_Wreck_sed01_aban1_police | -0.806117 / -0.058 | At this exact site/key after ground placement, inspect wheel/body contact, below-ground debris and CE loot reach. Confirm whether the usable wreck is buried before changing dy. |
| Land_Wreck_sed01_aban2_police | -0.531272 / -0.049 | At this exact site/key after ground placement, inspect wheel/body contact, below-ground debris and CE loot reach. Confirm whether the usable wreck is buried before changing dy. |

### Vanilla visual cost review

Counts are triangles in the lowest numeric visual LOD, not a performance measurement.
The installed class-family comparison below decodes the same client models as the
audit. Equal-cost aliases, damage skins or different functional shapes are not a
lighter equivalent. Thirty models have no lighter equivalent in their reviewed
vanilla family and retain their authored role. Six need visual comparison before
acceptance or replacement; they remain failing. These decisions do not accept target-load performance.

| Class | Triangles | Verdict and family comparison |
| --- | ---: | --- |
| Land_Container_1Mo | 4814 | needs_live: 4814 triangles. Lighter family candidates need visual/door/damage equivalence review: Land_Container_1Bo (4734). |
| Land_Container_1Moh | 5244 | needs_live: 5244 triangles. Lighter family candidates need visual/door/damage equivalence review: Land_Container_1Bo (4734), Land_Container_1Mo (4814). |
| Land_Medical_Tent_Big | 6994 | triangle_cost_accepted: 6994 triangles. No lighter equivalent in the installed vanilla Medical_Tent_Big family; the family contains only this model. Retain its authored tent silhouette and function. |
| Land_Medical_Tent_Shower | 15353 | triangle_cost_accepted: 15353 triangles. No lighter equivalent in the installed vanilla Medical_Tent_Shower family; the family contains only this model. Retain its authored tent silhouette and function. |
| Land_Mil_Fortified_Nest_Small | 8961 | triangle_cost_accepted: 8961 triangles. No lighter equivalent in the installed vanilla Mil_Fortified_Nest_Small family; the family contains only this model. Retain its authored building silhouette and function. |
| Land_Mil_GuardTower | 6154 | triangle_cost_accepted: 6154 triangles. No lighter equivalent in the installed vanilla Mil_GuardTower family; the family contains only this model. Retain its authored building silhouette and function. |
| Land_Mil_Tent_Big4 | 7580 | triangle_cost_accepted: 7580 triangles. No lighter equivalent in the installed vanilla Mil_Tent_Big4 family; the family contains only this model. Retain its authored tent silhouette and function. |
| Land_Wreck_Caravan_MGreen | 17152 | triangle_cost_accepted: 17152 triangles. No lighter equivalent in the installed vanilla Wreck_Caravan_MGreen family; all decoded aliases/skins have equal or greater cost. Retain its authored wreck silhouette and function. |
| Land_Wreck_Ikarus | 14622 | triangle_cost_accepted: 14622 triangles. No lighter equivalent in the installed vanilla Wreck_Ikarus family; all decoded aliases/skins have equal or greater cost. Retain its authored wreck silhouette and function. |
| Land_Wreck_Lada_Green | 15566 | triangle_cost_accepted: 15566 triangles. No lighter equivalent in the installed vanilla Wreck_Lada_Green family; all decoded aliases/skins have equal or greater cost. Retain its authored wreck silhouette and function. |
| Land_Wreck_Uaz | 16595 | triangle_cost_accepted: 16595 triangles. No lighter equivalent in the installed vanilla Wreck_Uaz family; all decoded aliases/skins have equal or greater cost. Retain its authored wreck silhouette and function. |
| Land_Wreck_offroad02_aban2 | 27501 | triangle_cost_accepted: 27501 triangles. No lighter equivalent in the installed vanilla Wreck_offroad02_aban2 family; all decoded aliases/skins have equal or greater cost. Retain its authored wreck silhouette and function. |
| Land_Wreck_sed01_aban1_police | 34362 | needs_live: 34362 triangles. Lighter family candidates need visual/door/damage equivalence review: Land_Wreck_sed01_aban2_police (32180), Land_Wreck_sed01_aban1_black (34260), Land_Wreck_sed01_aban1_white (34260), Land_Wreck_sed01_aban1_wine (34260), Land_Wreck_sed01_aban2_black (32109), Land_Wreck_sed01_aban2_white (32109), Land_Wreck_sed01_aban2_wine (32109). |
| Land_Wreck_sed01_aban2_police | 32180 | triangle_cost_accepted: 32180 triangles. Lower-count ordinary sedan skins lack police livery; the police damage-2 variant has no lighter police equivalent. Retain the authored police wreck role. |
| StaticObj_Container_1C | 5770 | needs_live: 5770 triangles. Lighter family candidates need visual/door/damage equivalence review: Land_Container_1Aoh (5244), Land_Container_1Bo (4734), Land_Container_1Mo (4814), Land_Container_1Moh (5244), StaticObj_Container_1Nr2 (5754). |
| StaticObj_Container_1D | 5770 | needs_live: 5770 triangles. Lighter family candidates need visual/door/damage equivalence review: Land_Container_1Aoh (5244), Land_Container_1Bo (4734), Land_Container_1Mo (4814), Land_Container_1Moh (5244), StaticObj_Container_1Nr2 (5754). |
| StaticObj_Dead_MassGrave_8m | 9412 | triangle_cost_accepted: 9412 triangles. No lighter equivalent in the installed vanilla Dead_MassGrave_8m family; the family contains only this model. Retain its authored prop silhouette and function. |
| StaticObj_Furniture_foldingbed_open | 5800 | triangle_cost_accepted: 5800 triangles. No lighter equivalent in the installed vanilla Furniture_foldingbed_open family; the family contains only this model. Retain its authored prop silhouette and function. |
| StaticObj_Furniture_hospital_transport_bed | 3498 | triangle_cost_accepted: 3498 triangles. No lighter equivalent in the installed vanilla Furniture_hospital_transport_bed family; the family contains only this model. Retain its authored prop silhouette and function. |
| StaticObj_Mil_CamoNet_Side_east | 2232 | triangle_cost_accepted: 2232 triangles. No lighter equivalent in the installed vanilla Mil_CamoNet_Side_east family; all decoded aliases/skins have equal or greater cost. Retain its authored prop silhouette and function. |
| StaticObj_Mil_HBarrier_4m | 5547 | triangle_cost_accepted: 5547 triangles. No lighter equivalent in the installed vanilla Mil_HBarrier_4m family; the family contains only this model. Retain its authored prop silhouette and function. |
| StaticObj_Mil_HBarrier_6m | 8357 | triangle_cost_accepted: 8357 triangles. No lighter equivalent in the installed vanilla Mil_HBarrier_6m family; the family contains only this model. Retain its authored prop silhouette and function. |
| StaticObj_Misc_BagFence_3m | 2572 | triangle_cost_accepted: 2572 triangles. No lighter equivalent in the installed vanilla Misc_BagFence_3m family; the family contains only this model. Retain its authored prop silhouette and function. |
| StaticObj_Misc_BagFence_Round | 6253 | triangle_cost_accepted: 6253 triangles. No lighter equivalent in the installed vanilla Misc_BagFence_Round family; the family contains only this model. Retain its authored prop silhouette and function. |
| StaticObj_Misc_Razorwire | 7728 | triangle_cost_accepted: 7728 triangles. No lighter equivalent in the installed vanilla Misc_Razorwire family; the family contains only this model. Retain its authored prop silhouette and function. |
| StaticObj_Misc_RoadBarrier | 2075 | needs_live: 2075 triangles. Lighter family candidates need visual/door/damage equivalence review: StaticObj_Misc_RoadBarrier_2 (182). |
| StaticObj_Roadblock_Bags_Long | 8542 | triangle_cost_accepted: 8542 triangles. No lighter equivalent in the installed vanilla Roadblock_Bags_Long family; the family contains only this model. Retain its authored prop silhouette and function. |
| StaticObj_Roadblock_CncBlocks_Long | 2440 | triangle_cost_accepted: 2440 triangles. No lighter equivalent in the installed vanilla Roadblock_CncBlocks_Long family; all decoded aliases/skins have equal or greater cost. Retain its authored prop silhouette and function. |
| StaticObj_Wreck_BMP2 | 8632 | triangle_cost_accepted: 8632 triangles. No lighter equivalent in the installed vanilla Wreck_BMP2 family; all decoded aliases/skins have equal or greater cost. Retain its authored wreck silhouette and function. |
| StaticObj_Wreck_Digger | 15362 | triangle_cost_accepted: 15362 triangles. No lighter equivalent in the installed vanilla Wreck_Digger family; the family contains only this model. Retain its authored wreck silhouette and function. |
| StaticObj_Wreck_MTVR_Cargo | 21039 | triangle_cost_accepted: 21039 triangles. No lighter equivalent in the installed vanilla Wreck_MTVR_Cargo family; all decoded aliases/skins have equal or greater cost. Retain its authored wreck silhouette and function. |
| StaticObj_Wreck_Mi8_Crashed | 14237 | triangle_cost_accepted: 14237 triangles. No lighter equivalent in the installed vanilla Wreck_Mi8_Crashed family; all decoded aliases/skins have equal or greater cost. Retain its authored wreck silhouette and function. |
| StaticObj_Wreck_PowGen | 2704 | triangle_cost_accepted: 2704 triangles. No lighter equivalent in the installed vanilla Wreck_PowGen family; the family contains only this model. Retain its authored wreck silhouette and function. |
| StaticObj_Wreck_Stryker | 54896 | triangle_cost_accepted: 54896 triangles. No lighter equivalent in the installed vanilla Wreck_Stryker family; all decoded aliases/skins have equal or greater cost. Retain its authored wreck silhouette and function. |
| StaticObj_Wreck_Trailer_Cistern | 12049 | triangle_cost_accepted: 12049 triangles. No lighter equivalent in the installed vanilla Wreck_Trailer_Cistern family; the family contains only this model. Retain its authored wreck silhouette and function. |
| StaticObj_Wreck_Ural | 11277 | triangle_cost_accepted: 11277 triangles. No lighter equivalent in the installed vanilla Wreck_Ural family; all decoded aliases/skins have equal or greater cost. Retain its authored wreck silhouette and function. |

### Classification contract

`config/world-mesh-classification.json` contains only outstanding findings. Each row
binds the exact measurement, reason, class and placement identity, plus repository
evidence. New/changed findings and stale/duplicate rows fail, as do policy changes.
`real` and `needs_live` always fail. Fixes disappear from the active classification;
the table above preserves all 60 original real identities. The original 200 verdicts
are: real 60 (fixed), needs_live 110, triangle_cost_accepted 30, intended 0,
runtime_corrected 0. No runtime acceptance or multiplayer claim is made.

### Tower corner

The sole active forward-outpost site is `military-outposts-v1/o02` (heading 0).
Local tower position moves (-13.25, 0.47, 6.0) → (-13.25, 0.47, 16.0), world
(4436.75, 341.194792, 9421.0) → (4436.75, 341.194792, 9431.0).
Its Geometry bounds are x=-17.273586..-11.946311, z=13.304224..25.917276.
These have no AABB overlap with any other composition piece, including all walls
and crates; no container is present. They clear the central x=-3.5..3.5 lane.
The tent bounds end at z=8.004910, leaving 5.299314 m to the tower, beyond
the audit door sweep plus radius (1.8 m); the tower does not block its entrance apron.
The tower exposes no decoded door planes or Paths LOD segments, so offline apron
tests cannot establish entry clearance. Native ladder, door operation and sightline
along the lane still need the lead client smoke.

### Every pending live identity

Apply the exact check in each classification row; the tables above describe the class-specific checks.

| Group | Class | Keys |
| --- | --- | --- |
| class-level | Land_Container_1Mo | class-level |
| class-level | Land_Container_1Moh | class-level |
| class-level | Land_Wreck_sed01_aban1_police | class-level |
| class-level | StaticObj_Container_1C | class-level |
| class-level | StaticObj_Container_1D | class-level |
| class-level | StaticObj_Misc_RoadBarrier | class-level |
| overlay:civilian-stories-v2 | Land_Medical_Tent_Big | s001-p01, s002-p04, s006-p01, s008-p01, s009-p01, s010-p04, s014-p01, s016-p01, s017-p01, s018-p04, s022-p01, s024-p01, s025-p01, s026-p04, s030-p01, s032-p01, s033-p01, s034-p04, s038-p01, s040-p01, s041-p01, s042-p04, s046-p01, s048-p01, s049-p01, s050-p04, s053-p01, s054-p01 |
| overlay:civilian-stories-v2 | Land_Wreck_Caravan_MGreen | s003-p01, s011-p01, s019-p01, s027-p01, s035-p01, s043-p01 |
| overlay:civilian-stories-v2 | Land_Wreck_sed01_aban1_police | s005-p01, s013-p01, s021-p01, s029-p01, s037-p01, s045-p01, s052-p01 |
| overlay:civilian-stories-v2 | Land_Wreck_sed01_aban2_police | s005-p02, s013-p02, s021-p02, s029-p02, s037-p02, s045-p02, s052-p02 |
| overlay:inland-discoveries-v2 | Land_Medical_Tent_Big | s005-p01, s005-p02, s012-p04, s017-p01, s017-p02, s024-p04, s029-p01, s029-p02, s035-p01, s035-p02 |
| overlay:inland-discoveries-v2 | Land_Mil_Tent_Big2_3 | s010-p01, s011-p03, s022-p01, s023-p03 |
| overlay:inland-discoveries-v2 | Land_Mil_Tent_Big4 | s001-p01, s011-p01, s013-p01, s023-p01, s025-p01 |
| overlay:military-outposts-v1 | Land_Mil_Tent_Big4 | o01-p01, o03-p01 |
| overlay:military-zones-v2 | Land_Medical_Tent_Big | s005-p01, s005-p02, s012-p04, s017-p01, s017-p02, s023-p04, s034-p04, s037-p01, s037-p02, s043-p01, s043-p02, s047-p04, s054-p01, s054-p02, s063-p04, s066-p04 |
| overlay:military-zones-v2 | Land_Mil_Tent_Big2_3 | s010-p01, s011-p03, s022-p03, s032-p01, s033-p03, s052-p01, s065-p03 |
| overlay:military-zones-v2 | Land_Mil_Tent_Big4 | s001-p01, s011-p01, s013-p01, s022-p01, s024-p01, s033-p01, s035-p01, s048-p01, s055-p01, s065-p01 |
| overlay:supply-dumps-v1 | Land_Medical_Tent_Big | d09-p01, d09-p02 |

### Worker validation snapshot (2026-11-24)

Strict preland against `000c2899` finished with exit 1. Client geometry and staged
CE mission inputs were supplied via `HC_GENERATED_GEOMETRY_ADDONS` and `HC_CE_MISSION`.
The supplied original raw audit and original census pointer were absent on this host.
A fresh client audit reproduced the reported inventory (200 findings: 104 sinking,
60 floating, 36 visual costs over 37 classes). No exact-hash census copy was found
locally. `preland --native-census` now forwards an original census to regeneration
and digest checks when one is provided; the mesh audit itself does not consume it.

Final mesh result: 76 classes, 140 raw findings, 110 blocking `needs_live` rows,
30 reviewed visual-cost acceptances, 0 unclassified, 0 classification errors.
The 505 existing static coverage skips remain: incomplete/unavailable door selections,
missing Geometry LODs and live-terrain shelter retries. These are not native evidence.
The 60 original floating findings are gone and no new finding was introduced.

Production `map_overlay compose` regenerated all 16 install-time files in scratch,
including the 60 corrected wreck rows and the moved tower. Layers retain composition
references, so there is no committed expanded layer to hand-edit. The generator's
17 available comparisons passed; strict regeneration still fails on four gaps:
optional weapon verification reports (two), ImageToPAA interop, and the original
native census for new-building byte reproduction.

Digest receipts remain stale following the known #339 merge. The check reports
input/source/output drift for `ai_route_precompute`, `admin_world_catalog`,
`military_loot`, `loot_slack`, `inventory_sizes`, `variety_packs`, `firearms`,
`loot_point_preserve`, `gui_icons`, `economy`, `gen_modules`, `ai_patrols` and
`anims_config`; two optional weapon reports and the original `new_buildings` census
are unavailable. The changed compositions also invalidate the `new_buildings` input
receipt; without its exact original census, byte reproduction and receipt refresh
remain blocked. No unrelated receipts or generated outputs were refreshed.

The 74 directly relevant audit/preland tooling tests passed; preland's changed-file
mapping also passed all 317 selected tooling tests. No native process was started.
Status: implemented-unverified, with the live checks above and host gaps outstanding.

Check | Result | Scope
--- | --- | ---
enforce_lint | pass | full tree
enforce_perf | pass | full tree
layout_lint | pass | full tree
cfgconvert_check | pass | changed addons (non-mod change: full tree)
settings_consistency | pass | full tree
wiring_audit | pass | full tree
regenerate_all | FAIL (skipped/unavailable coverage) | full tree
generated_digests | FAIL (digest receipt verification) | full tree
mission_sources | pass | full tree
hygiene | pass | full tree
hc_events | pass | full tree
ce_slot_pressure | pass | full tree
world_mesh_audit | FAIL (1) | full tree
asset_lint | no applicable inputs (assets_src holds no built MLOD/IR) | full tree
unit_tests_changed | pass | changed files
