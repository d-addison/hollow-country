# Site archetypes

Authored templates for composed map locations (roadblocks, camps, crashes, depots). They answer the
owner's 11-22 complaint that generated locations were a random scatter of props: every site is now one
story with a reason to be at its spot, a frame taken from the world (road tangent, approach, view or fall
line) and parts placed relative to a named part. Status: templates and schema only. The composer
(`tools/package/site_composer.py`, wave W4) will consume them; nothing here places an object yet, and no
template establishes in-game behaviour. Layers, `classes.json` and the map overlay are unchanged.

Files: `config/sites/archetypes/<id>.json` (15 templates) and `config/sites/archetypes/schema.json`.
Check: `python3 -B -m unittest tests.unit.test_site_archetypes` validates every template against the schema
and against `config/map-overlays/classes.json` (every class vanilla and already verified there; no pack classes).

## How a site is built

1. The composer picks a spot that satisfies the archetype's `location` predicates (section Location predicates).
2. It builds the frame: origin plus a forward axis. In a road frame the axis is the road centreline tangent
   (forward as named by `frame.forward`); `s` is metres along it and `side`/`offset_m` the lateral distance.
3. The anchor part is placed first; every other part is placed relative to a named part (`of`) or the frame.
   `of: origin` is the frame origin; `external_anchors` name vanilla buildings (farm holdout only).
4. Yaw intent is in `align` and `faces`; the composer subtracts the class `front_yaw_deg` (W1 geometry).
5. If the derived yaw does not fit, the candidate spot is rejected. Nothing is rotated to make room.

Rules shared by all templates: the carriageway stays passable (every barrier set has a gap of at least
3.5 m, no vehicle wreck closes a lane, as `classes.json` collision notes require); the guard shed class is not
used (the installed model has an empty view geometry); loot rows only on classes that have an installed
loot prototype; no scripted loot and no objects inside vanilla buildings.

## Archetype table

| Archetype | Frame (kind, forward) | Anchor | Objects | Loot rows | Max per map | Spacing same / any (m) |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `military-checkpoint` | road, toward_protected | `Land_Mil_Fortified_Nest_Small` | 20 | 2 | 6 | 2500 / 300 |
| `police-roadblock` | road, into_town | `Land_Wreck_sed01_aban1_police` | 16 | 2 | 6 | 2500 / 300 |
| `quarantine-post` | road, into_town | `Land_Medical_Tent_Big` | 19 | 2 | 4 | 2500 / 300 |
| `bandit-roadblock` | road, toward_settlement | `StaticObj_Wreck_MTVR_Cargo` | 18 | 2 | 6 | 2500 / 300 |
| `crashed-convoy` | road, travel_direction | `StaticObj_Wreck_MTVR_Cargo` | 13 | 2 | 5 | 2500 / 300 |
| `fuel-stop` | road, toward_larger_road | `StaticObj_Wreck_Trailer_Cistern` | 13 | 2 | 4 | 2500 / 300 |
| `military-camp` | approach, toward_road_access | `Land_Mil_Tent_Big1_1` | 24 | 3 | 8 | 1500 / 300 |
| `supply-dump` | approach, along_access_track | `Land_Container_1Mo` | 22 | 4 | 4 | 2000 / 300 |
| `field-hospital` | approach, toward_road_access | `Land_Medical_Tent_Big` | 16 | 3 | 4 | 2000 / 300 |
| `overwatch-post` | view, view_sector | `Land_Mil_Fortified_Nest_Small` | 11 | 2 | 6 | 1000 / 300 |
| `helicopter-crash` | fall_line, downhill | `StaticObj_Wreck_Mi8_Crashed` | 12 | 0 | 4 | 2500 / 300 |
| `refugee-camp` | approach, from_road_into_camp | `Land_Wreck_Ikarus` | 21 | 2 | 4 | 3000 / 300 |
| `hunter-camp` | view, toward_open_side | `Land_Wreck_Caravan_MGreen` | 12 | 1 | 6 | 1500 / 300 |
| `mass-grave` | approach, toward_dirt_road | `StaticObj_Dead_MassGrave_8m` | 12 | 1 | 3 | 3000 / 300 |
| `farm-holdout` | building, yard_approach | `vanilla farmhouse (external anchor)` | 12 | 0 | 6 (per holdout) | 300 / 300 |

Totals at the per-map maximums: 70 composed sites (budget 75) and about 1167 objects (budget 1,800; the
farm holdout dressing follows the live holdouts and is counted apart). Object and loot counts are the maximum
instances a template can emit; a loot row is one proto object, and the composer measures the real
mapgrouppos rows against the 300-row cap.

## Operator reference

Closed set of 11 operators; a template cannot use anything else. Units are metres and degrees. `s` is
arc length along the frame axis from the origin, positive forward. In a road frame the lateral distance of
`shoulder` is measured from the road edge; elsewhere from the axis. `count` and several distances may be
a `[min, max]` range the composer picks from with a seed of the site id (no `Math.Random`).

| Operator | Meaning | Required fields | Rule the W5 validator enforces |
| --- | --- | --- | --- |
| `in_lane` | Object on the carriageway, long axis along the tangent | `s`, `lane`; optional `angle_deg`, `jitter_deg`, `align` | Centre within 1.5 m of the lane centre; at least 3.5 m stays passable. Road frame only. |
| `across_lane` | `count` objects spanning the carriageway, long axis perpendicular, optional chicane | `s`, `count`; optional `gap_m` (3.5 m or more), `faces` | Spans the road width; gap at least 3.5 m; front toward `faces`. Road frame only. |
| `shoulder` | Beside the road, `offset_m` beyond the road edge | `side` (left or right), `s`, `offset_m`; optional `angle_deg`, `faces`, `align` | 0.5 to 6 m from the edge, never on the lane. Road frame only. |
| `offroad` | Away from the axis at `offset_m` | `side` (left, right or center), `s`, `offset_m` | At least 8 m from the centreline in a road frame; same side as named. |
| `row` | `count` objects in a line at `spacing_m` | `count`, `spacing_m`, `faces` or `align`, and either `s`/`side`/`offset_m` or `of`/`dist_m`; `run` is forward or lateral | Equal spacing within 0.5 m; yaw within 10 degrees of target. |
| `ring` | `count` objects on an arc of radius `r_m` round `of` | `of`, `r_m`, `count`, `arc_deg`, `centre_on`, `faces` (`of` for seats and beds, `outward` for sandbags and wire); optional `centre` when `of` is `origin` | Facing error at most 15 degrees (social) or 20 (defensive). |
| `facing` | One object at `dist_m` from `of`, front toward it | `of`, `dist_m`, `from` (front, back, left, right or road_side) | Facing error at most 15 degrees. |
| `beside` | Next to another part, in its frame | `of`, `dist_m`, `side` (left, right, forward or back) | Inherits that part's yaw within 10 degrees. |
| `behind` | Behind another part, in its frame | `of`, `dist_m` | Inherits that part's yaw within 10 degrees. |
| `scatter` | Small litter in a named zone, seeded by site id | `zone`, `count`, `min_gap_m` | Inside the zone, at least `min_gap_m` apart, no lane, no door apron; only small props of at most 3 x 3 m, never hard pieces or loot. |
| `on_slope` | Placed from the survey grid by terrain | `mode`: `fall_line` (long axis along the downhill direction) or `crest` (at the view crest) | Grade and view rules; refused above the archetype's slope limit. |

Other part fields: `anchor` (exactly one per template, placed first); `loot: proto` (see Loot); `class` as one
name or a variant list of classes sharing a role (the composer picks one by site id); `guard_post` (becomes a
guard slot, see Story items); `stack_on` (a declared stack such as a crate on a pallet, `dist_m` 0, the only
allowed overlap); `variant` (the part exists only in that site variant); `optional` (skipped when its `of`
anchor is missing); `reverse_slope` (placed behind the crest, out of the view); `instance` (`first`, `last`
or `all` when `of` is a row: `beside` and `behind` repeat per instance unless an instance is named, while
`row`, `ring`, `facing` and scatter zones use the centroid of the instances).

Yaw sources: `align` is `road` (road tangent), `anchor` (the anchor part's yaw), `contour` or `fall_line`;
`faces` is a part id, or `forward`, `-forward`, `outward` (away from `of` or the origin), `axis` (toward the
frame axis, so doors face the lane or road), `view` (the view sector) or `of`. A negative `angle_deg` turns
anticlockwise, positive clockwise, relative to the forward axis.

Scatter zones (`zones[]`): `disc` (radius `r_m`), `cone` (`r_m`, `arc_deg`, `dir`) or `strip` (length `r_m`,
`width_m`, `dir`), anchored on a part; `dir` is forward, -forward, uphill, downhill, left, right, outward or toward_road.

## Location predicates

All keys are optional (at least two per template) and all are tested by the composer at plan time against
the road graph, the stock mapgrouppos and the site survey; they are not tested in game.

| Key | Meaning |
| --- | --- |
| `road` | surface (asphalt, gravel, dirt), `straight_m`, `max_turn_deg`, `max_grade_pct`, `min_chain_m` (no junction for that length), `bend_or_grade` (prefer a bend or grade) |
| `at_junction`, `junction_m` | the site sits at a junction of degree 3 or more, or lies `[min, max]` from the nearest one |
| `settlement_edge_m`, `base_m` | range from the outer houses of a Village or Town cluster, or from a vanilla military base; `near_any` makes the two alternatives |
| `medical_building_m`, `no_vanilla_within_m` | prefer a vanilla medical building within this range; keep clear of vanilla fuel stations by this distance |
| `road_access_m_max`, `road_distance_m` | off-road sites: a reachable road access point within this range, or `[min, max]` distance from roads |
| `water_m_max`, `prefer_water_m` | hard or preferred distance to a pond or stream |
| `slope_pct`, `slope_pct_max` | footprint grade range or limit |
| `tree_free_radius_m`, `cover_within_m`, `forest_edge` | survey tree rules: open ground, cover nearby, trees on one side and open opposite |
| `highest_flat_within_m`, `crest`, `hidden_from_road` | terrain choices: highest flat ground, a crest that covers a road or base approach, out of sight of the main road |
| `not_in` | excluded zones: `military` or `town_core` |

## Loot

A part with `loot: proto` emits mapgrouppos rows for its installed loot prototype group; only classes whose
`classes.json` `loot_group` is true can carry it. A template has 1 to 4 rows (a part with `count` n emits n)
or none with a `loot_none_reason` (the helicopter wreck has no prototype and the stock crash event keeps
owning crash loot; the farm holdout never adds loot). The `loot_theme` keeps stories matched: `civilian`
(civilian wrecks, containers, medical tents), `military` (military buildings, tents, wrecks, containers),
`medical` (medical tents, containers) and `scavenged` (civilian and military wrecks, containers). Items and
tiers stay with the Central Economy; no scripted loot and no extra nominals.

## Story items

`story_items.note` names a note key placed on a table part (the existing note ledger places it; the keys
below are names only, ledger wiring is a later wave): `bandit-toll-ledger`, `triage-roster`, `hunter-journal`, `cleanup-manifest`, `outpost-roster`, `checkpoint-duty-log`, `police-shift-log`, `quarantine-triage-log`, `refugee-registry`.
`story_items.ai` lists the parts flagged `guard_post`; they become guard slots in the zone contract (1.5 m
behind the part front, facing its `faces` target) and AI is only ever spawned through the existing systems
and the HC bridge. `zone_role` (hq, perimeter, outpost, depot) marks the military archetypes that join the
zone contract. No omniscient AI and no unlimited alerts come from a template.

## Owner-facing stories

What to look for in game (one client), per archetype. Offline templates do not prove any of it.

### `military-checkpoint` (Military checkpoint)

A road inspection team still holds a lane 400 m outside the base: nest and sandbags on the near shoulder, a chicane of barriers, concrete blocks facing traffic and a flag over the post.

- Where: On an asphalt or gravel road 250 to 600 m outside a vanilla military base, on a straight of at least 60 m, not at a junction mouth. The road runs toward the base.
- You see: A nest on the near shoulder with sandbags in an arc facing the incoming road, a staggered barrier chicane and a second concrete-block chicane 15 m out, a second nest on the far shoulder watching the exit, a desk and crate, a flagpole behind the post. Traffic can still pass through the gaps.
- How many: up to 6 on the map, 2500 m apart from the same story and 300 m from any other composed site.
- Lead note: `checkpoint-duty-log`, on the table part.

### `police-roadblock` (Abandoned police roadblock)

Two police cars were nosed into a V across the approach to a town, barriers staggered behind them. The desk and chair are still on the shoulder and hazmat bags are stacked on the town side.

- Where: On the asphalt road into a Village or Town cluster, 150 to 400 m from its first houses, on a straight run.
- You see: Two police wrecks nosed into a V across the lanes with a 3.5 m gap at the apex, barriers staggered on both sides, a desk and chair on the shoulder facing the road, hazmat bags in a row on the town side.
- How many: up to 6 on the map, 2500 m apart from the same story and 300 m from any other composed site.
- Lead note: `police-shift-log`, on the table part.

### `quarantine-post` (Quarantine post)

A medical team set up at the edge of town to screen everyone coming in: a tent facing the road, a shower tent beside it, a fence line with beds and hazmat bags, and a barrier that funnels traffic through one gap.

- Where: On the main road at a town edge (0 to 150 m from the outer houses), preferably within 600 m of a vanilla medical building.
- You see: A big medical tent with its door toward the road, a shower tent beside it, a wire fence line with beds and hazmat bags between the tent and the road, a table in front of the tent door and a barrier chicane on the road.
- How many: up to 4 on the map, 2500 m apart from the same story and 300 m from any other composed site.
- Lead note: `quarantine-triage-log`, on the table part.

### `bandit-roadblock` (Bandit roadblock)

Bandits stopped a cargo truck on a country road and turned it into a toll point: barriers at both ends, a nest on the shoulder, a desk for the toll, and a sleeping camp tucked behind cover.

- Where: On a gravel or dirt country road 500 to 2500 m from settlements, on a long stretch without junctions and with cover (trees) within 30 m.
- You see: A cargo truck wreck in one lane, barriers and hedgehogs at both ends with a 3.5 m gap, a nest on the shoulder looking down the road, a toll desk with a chair facing it, and a sleeping camp 14 m off the road (fire, three beds round it, wood pile).
- How many: up to 6 on the map, 2500 m apart from the same story and 300 m from any other composed site.
- Lead note: `bandit-toll-ledger`, on the table part.

### `crashed-convoy` (Crashed convoy)

A supply convoy was ambushed on an open stretch: the cargo truck stands in its lane, the lead vehicle is nose-down in the ditch, an escort is stuck behind it and the last one jackknifed on the far shoulder. Spilled crates lie on the downhill side.

- Where: On a straight of at least 120 m outside towns, ideally on a grade or at a bend.
- You see: A cargo truck in its lane, an armoured car nose-down in the ditch ahead of it, an escort truck behind, a last vehicle jackknifed on the far shoulder, and crates, canisters and trash scattered on the downhill side. The road stays drivable.
- How many: up to 5 on the map, 2500 m apart from the same story and 300 m from any other composed site.

### `fuel-stop` (Roadside fuel stop)

Where the road forks, travellers once refuelled from a cistern trailer: two small tanks stand behind it, canisters wait on pallets, a Lada is parked nose to the tanks and a container holds the spares.

- Where: At a road junction with no vanilla fuel station within 1.5 km, on a flat shoulder of the larger road.
- You see: A cistern trailer on the shoulder aligned to the road, two small tanks behind it, a pallet with canisters stacked on it, a Lada parked nose to the tanks and a container with the spares.
- How many: up to 4 on the map, 2500 m apart from the same story and 300 m from any other composed site.

### `military-camp` (Military forward camp)

A forward outpost on the highest flat ground above the base approach: tent rows facing a central lane that opens to the access road, camo nets over each tent, a nest at the mouth and barriers on the open sides.

- Where: 300 to 900 m from a vanilla military base, on the highest flat ground within 500 m that has a road within 150 m.
- You see: Two rows of two tents facing a central lane that opens to the access road, camo nets beside each tent, a radio tent with an antenna at the back, a nest at the lane mouth, barriers closing the sides and rear, a camp table with three seats in the lane.
- How many: up to 8 on the map, 1500 m apart from the same story and 300 m from any other composed site.
- Lead note: `outpost-roster`, on the table part.

### `supply-dump` (Supply dump)

Containers in two rows along the access track, each with pallets and a crate at its door, razor wire round the open sides and a guard tower at the corner covering the lane.

- Where: Road-served flat ground 100 to 500 m from a vanilla military base or depot, within 120 m of a road.
- You see: Two rows of two containers along the access track, a pallet and crate at each door, razor wire round the sides and back, a guard tower at the corner covering the lane.
- How many: up to 4 on the map, 2000 m apart from the same story and 300 m from any other composed site.

### `field-hospital` (Field hospital)

A medical team set up two tents with their doors toward the road so ambulances could reach them: a casualty line of beds and a treatment table in front, a shower tent at the side. A medevac variant marks a landing square on the flat side.

- Where: At the edge of a town (60 to 300 m) or of a base (100 to 400 m), flat, within 80 m of a road, near water if there is any.
- You see: Two medical tents side by side with their doors toward the road, a shower tent at the end, a casualty line of beds and a treatment table in front, bandage and hazmat litter. The medevac variant adds four landing lights marking a 20 m square on the flat side.
- How many: up to 4 on the map, 2000 m apart from the same story and 300 m from any other composed site.
- Lead note: `triage-roster`, on the table part.

### `overwatch-post` (Overwatch post)

A lookout nest sits on the crest above a road or a base approach: sandbags in an arc facing the view, a camo net behind the nest and a tent pitched out of sight on the reverse slope.

- Where: On a hill crest with at least a 20 m drop over 300 m in a sector that covers a road or a base approach, slope 10 % or less at the post.
- You see: A nest at the crest facing the view with sandbags in a 120 degree arc, a camo net behind it, a crate beside it and a tent 15 m behind the crest on the reverse slope, out of sight of the road.
- How many: up to 6 on the map, 1000 m apart from the same story and 300 m from any other composed site.

### `helicopter-crash` (Helicopter crash)

A transport helicopter came down on a slope in open ground: the wreck rests nose downhill, debris is strewn up the slope along its approach path and one crate was thrown ahead. Nobody camped here.

- Where: Open ground with no trees within 25 m, slope 3 to 12 %, 300 to 1500 m from roads.
- You see: A crashed transport helicopter lying nose downhill, debris spread up the slope behind it in a 40 m cone along its approach path and one crate thrown ahead. No tents, no furniture, no camp.
- How many: up to 4 on the map, 2500 m apart from the same story and 300 m from any other composed site.

### `refugee-camp` (Refugee camp)

A bus brought people this far and the camp grew around a lane running in from the road: tent rows on both sides, a fire with seats in the middle, a registration desk at the mouth and a shower tent at the downhill end.

- Where: 200 to 600 m outside a town beside the main road, flat, near water (pond or stream within 300 m) when the map has any.
- You see: A bus on the road shoulder at the lane mouth, a registration desk and chair facing the road, three tents on each side of a central lane, a fire with five seats and a wood pile in the lane centre, a shower tent at the far downhill end.
- How many: up to 4 on the map, 3000 m apart from the same story and 300 m from any other composed site.
- Lead note: `refugee-registry`, on the table part.

### `hunter-camp` (Hunter woodland camp)

A hunter parked a caravan at the forest edge with its back to the trees and its door to the open ground: a fire in front, seats and a folding bed round it, a wood pile behind, a camp table beside. Nothing military.

- Where: At a forest edge (trees within 15 m on one side, open ground opposite), 800 m or more from roads, near water when possible.
- You see: A caravan with its back to the trees and its door to the open ground, a fire 10 m in front of it, three seats and a folding bed round the fire, a wood pile behind the caravan and a camp table beside it. Nothing military.
- How many: up to 6 on the map, 1500 m apart from the same story and 300 m from any other composed site.
- Lead note: `hunter-journal`, on the table part.

### `mass-grave` (Mass grave clean-up site)

Out of sight of the main road, a clean-up crew buried the dead in a pit off a dirt track: a digger beside it, hazmat bags in a row on the far side, and a tent with a table at the track end where the crew logged the work.

- Where: Outside a town, 50 to 200 m off a dirt road, behind a slope or tree line as seen from the main road.
- You see: A pit with a digger beside it facing the pit, a row of hazmat bags on the far side, and at the dirt-track end a tent with a table and chair where the crew logged the work.
- How many: up to 3 on the map, 3000 m apart from the same story and 300 m from any other composed site.
- Lead note: `cleanup-manifest`, on the table part.

### `farm-holdout` (Farm holdout dressing)

Survivors fortified a farm: sandbags and barriers in arcs facing the yard approach with the door aprons left clear, a wreck parked beside the barn to block the gate, and crates stacked in the yard. Nothing is placed inside buildings.

- Where: A vanilla farm building cluster away from towns; the frame is the farmhouse's own yaw and the holdout feature chooses which farms are used.
- You see: Sandbag and barrier arcs round the farmhouse facing the yard approach (door aprons stay clear), crates beside the house and, if the farm has a barn, a wreck parked beside it to block the gate. Nothing is placed inside buildings.
- How many: one dressing per live holdout (the holdout limit is 6); at least 300 m apart.

## Authoring choices that differ from the design draft

- Wrecks never close a lane (classes.json says so), so the bandit roadblock and the crashed convoy are
  `passable` with a 3.5 m gap; changing `lane` to `blocking` is a one-field edit if the owner wants a hard block.
- The guard shed class is not used anywhere; nests stand in for it, as the composition library already does.
- The refugee, field hospital and military camp lanes run toward the road access (`toward_road_access` or
  `from_road_into_camp`), and their entry parts (nest or desk) sit at the mouth facing the road.
- The farm holdout is dressing only: it adds no composed site, counts apart from the 75-site budget and
  leaves the holdout feature in charge of which farms are used.

