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
