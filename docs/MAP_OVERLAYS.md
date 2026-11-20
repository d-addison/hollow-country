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

## Layers (2026-11-20)

All seven layers in `config/map-overlays/profile.json` are enabled by default.
The 2026-11-20 placement expansion grows the four-layer baseline from **30 sites,
350 objects and 49 CE rows** to **196 sites, 2,826 objects and 307 CE rows**.
Counts include the seven explicit tents as individual sites. Each CE row refers
to an installed vanilla `mapgroupproto.xml` group; the overlay never creates loot
items directly or overrides the economy's tier eligibility or quantity budgets.

| Layer | Sites | Objects | CE rows |
| --- | ---: | ---: | ---: |
| military-tents-v1 | 7 | 7 | 7 |
| military-outposts-v1 | 9 | 140 | 12 |
| supply-dumps-v1 | 9 | 133 | 25 |
| roadside-checkpoints-v1 | 5 | 70 | 5 |
| military-zones-v2 | 68 | 1,024 | 106 |
| inland-discoveries-v2 | 42 | 612 | 64 |
| civilian-stories-v2 | 56 | 840 | 88 |
| **Total** | **196** | **2,826** | **307** |

The military layer searches in fair rounds around NWAF, NEAF, Balota, Tisy,
Kamensk, VMC, Zelenogorsk, Myshkino, Pavlovo, Troitskoe, Severograd, Krasnostav,
Vybor, Stary Sobor, Green Mountain, Altar and the Prison Island approach. Each
has at least two sites in the current plan; NWAF has eight. Search centres are
geographic labels with a maximum 1,800 m search radius, not measured base
boundaries. Inland discovery candidates favour the northern/western interior
(`z >= 7000` and either `x < 6500` or `z >= 12000`). That is a geographic bias
for higher-tier military country, not verification of individual CE area flags.
Civilian candidates spread town-edge and isolated-structure finds across the map.

Every new site records `requested_composition` for one of the twenty scene-worker
kits. Until those kits land, `composition` uses an existing authored kit: all
166 new sites currently use those existing layouts. Re-running `expand-plan`
after merging the scene changes selects available requested kits and searches
again against their actual pieces. **Do not replace composition IDs in place:**
new footprints require a fresh placement plan, count report, validation and
scratch install. Detailed convoy, ridgeline, woodland and town-entry storytelling
remains dependent on the scene kits and native terrain/road inspection.

Planning is deterministic under stock XML row reordering: sorted candidates,
cardinal headings and SHA-256 coordinate ordering replace random selection.
Each new site's pieces retain at least 16 m from vanilla group origins, sites
retain 55 m between centres, and pieces of separate new sites are separated by
at least 16 m during planning. Every piece requires at least three vanilla rows
within 60 m, a maximum 1.5 m height spread and at most 0.8 m deviation from the
local median. Site centres additionally require a nondegenerate support plane
with slope at most 3 percent. `placement_evidence` records row counts, height
spread, support slope, nearest group distance and explicit terrain/road unknowns.
These distances describe object origins, not measured model collision bounds.

The installed Chernarus terrain is a binary WRP; no decoded height raster or road
network is available to this tool. Group origins remain the height evidence.
Deep woodland without sufficient rows is excluded. Offline checks cannot prove
ground contact, model fit, road clearance, door access, native yaw conventions,
CE loot spawning, individual loot tiers or target-load performance. All layers
remain `runtime-unverified`; their larger count is not gameplay acceptance.

Profile caps are 7,000 objects / 1,200 CE rows overall and 3,500 objects / 600 CE
rows per layer. The new layers also carry individual object/loot caps and the
16 m clearance / 3 percent support-slope requirements. Existing v1 layer caps
and positions are preserved. These are packaging bounds; runtime performance
budgets still need measurement with the target 3–6 players.

Use a **stock, private mission copy**, with previous overlays rolled back first:

```bash
python3 -B -m tools.package.map_overlay expand-plan --mission /tmp/hc-placement/mission --out config/map-overlays/layers
python3 -B -m tools.package.map_overlay validate --mission /tmp/hc-placement/mission
python3 -B -m tools.package.map_overlay report
python3 -B -m tools.package.map_overlay install --target /tmp/hc-placement/mission
python3 -B -m tools.package.map_overlay rollback --target /tmp/hc-placement/mission
```

`expand-plan` validates the combined retained/new layers against stock rows and
installed prototypes before writing the new layer files. The existing installer
still backs up and hashes exactly `cfggameplay.json` and `mapgrouppos.xml`, writes
one object-spawner file per enabled layer, and refuses drift during rollback.
The scratch rehearsal used a read-only copy of the installed mission and first
rolled its four existing overlays back to the pinned 11,679-row stock inventory
(SHA-256 `3eeaad9786a73c339f61f6e6ad203f0732e36b88f27333978cc8b4beece9cec4`).
No live mission is an installation target for this workflow.

Rehearsal result (2026-11-20, offline only):

```text
Installed addon class-name check: missing=0
INSTALL spawners=7 objects=2826 CE_rows_added=307 stock_rows=11679 installed_rows=11986
ROLLBACK cfggameplay.json=byte-exact mapgrouppos.xml=byte-exact managed_directory=removed
COMPOSE repeat=byte-exact
DETERMINISM reversed_stock_rows=byte-exact for all three new layers
```

The 70 existing focused overlay tests pass. Their obsolete sub-400-object
assertion now checks the configured total cap; no new tests were added.
Repository integration note: `/docs/*` currently ignores this new document.
The lead must allowlist `docs/MAP_OVERLAYS.md` for it to enter the release source;
the placement worker does not own `.gitignore`.
