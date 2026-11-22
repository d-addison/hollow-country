# Offline world mesh audit

Run from the checkout:

```sh
python3 -B -m tools.audit.world_mesh_audit --addons /external/DayZ/Addons --report /tmp/world-mesh-report.json
```

`--bounds-out FILE` additionally writes the proposed measured-bounds update for
`config/map-overlays/classes.json` (see "Measured bounds" below). `--addons` defaults to the shared
release `ship_inputs.ADDONS`. Models are decoded by the clean-room ODOL56 reader
`tools/audit/odol56.py`; there is no external reader and `--reader` is a legacy,
ignored option. The report's `reader_revision` and `reader_sha256` fields are
legacy provenance constants from `interior_points_gen` (kept so shipped outputs
stay byte-identical, see [REGENERATE.md](REGENERATE.md)). Installed PBOs are indexed and read in place, without
asset extraction, dumps or changes to placement data. Full-client Addons are
needed for visual cost evidence; dedicated-server stripped meshes produce SKIP.

Missing Addons print SKIP and return zero. Invalid available inputs or
findings return nonzero. `--require-installed` also returns nonzero for any
SKIP, including unresolved classes, missing Geometry, incomplete door selections
or unavailable section counts. A permissive `pass` with skips is incomplete.
JSON goes to `--report`, or stdout when omitted, followed by SKIP reason lines
and `world_mesh_audit: pass|fail checked=N findings=N skipped=N`.
`checked` counts decoded placed classes, findings/skipped count report records.
There are no timestamps or installation paths in the report. Ordering is stable.

Inputs and loaders:

- All `config/map-overlays/layers/*.json`, including disabled layers, expanded
  with `map_overlay.load_source/expand_layer` and `compositions.json`. This is
  the same expansion that produces native `Objects` spawner files at install.
- `mission/hollow-country/interiors/templates/t-*.json` `PropSlots`, consumed
  by `HCInteriorTemplates` and `HCInteriorTemplatePlacement`. Positions and
  orientations use the host model frame; evidence and furnished-instance rows
  do not create duplicate placement records.
- `mission/hollow-country/travel/auditshelter_scenes.json` `Scenes` and
  `AdditionalScenes`: host class and three base slots. `HCShelterModule.PlaceProp`
  supplies grill/chair/box classes, replaces Y with `SurfaceY`, and tries shifted
  layouts. The audit inventories those classes but explicitly skips live terrain,
  retry-layout clearance and apron verdicts. It does not simulate the controller.
- Native `Objects` JSON under `mission/`, if shipped, using `name`, `pos`,
  `ypr`, and `scale`. `HCGroundObjectSpawner` consumes these via
  `cfggameplay.objectSpawnersArr`; overlay spawner files are generated during
  installation rather than maintained as a second shipped data set. Ground snap
  requires runtime support rays and cannot be established offline.

The single `POLICY` block at the top of the tool defines review thresholds:
centre-to-origin distance above **0.5 m**, absolute lowest Geometry Y above
**0.10 m**, lowest numeric visual LOD above **2,000 triangles** or **20 sections**.
Lowest means the smallest numeric visual resolution below 1000 (LOD0 when
present), matching the existing generator; a cheaper distant LOD cannot hide cost. Polygon faces
contribute `vertices - 2` triangles. Section counts use the ODOL reader's
`lod.sections`, not material or texture counts. Door clearance is a **0.6 m
diameter**, **1.8 m tall** vertical cylinder swept **1.5 m each way** along the
horizontal normal of a Geometry door-leaf selection. Contact tolerance is
**5 mm** for piece/host intersection checks. The path-walk values are listed in
the same block (`path_step_over_m`, `path_sample_step_m`, `stair_min_slope`). These are provisional audit policy,
not measured engine or player-load budgets.

Each finding/skip has a reason code and, for model/placement checks, a class.
Key finding codes are `PIVOT_OFFSET`, `FLOATING_ORIGIN`, `SINKING_ORIGIN`,
`PIECE_AABB_OVERLAP`, `HOST_GEOMETRY_ENCROACHMENT`,
`VIEW_GEOMETRY_EMPTY_OR_MISSING`, `DOOR_APRON_INTERSECTION`,
`VISUAL_TRIANGLE_COST`, `VISUAL_SECTION_COST`, `STAIR_PATH_INTERSECTION` and
`PATH_LOD_INTERSECTION`. Placement findings include
group/key and the other piece or host. Model metrics retain Geometry bounds,
centre, bottom and visual costs. Bounds use actual Geometry vertices; standalone
props restore their bounding centre, while hosts and `Land_` buildings follow
the existing support audit's raw building frame.

Paths and stairs: every host (interior template or shelter model) with a Paths
LOD (4e15) has its path faces read as polylines of consecutive vertices. A
segment rising more than **0.30 m per metre** of horizontal run (or vertical) is a
stair flight. An agent column (**0.3 m** radius, **1.8 m** tall above the path
point) is sampled every **0.10 m** along each segment; a placed prop whose box meets
the column and is taller than the **0.20 m** step-over height is a finding:
`STAIR_PATH_INTERSECTION` for stair segments, `PATH_LOD_INTERSECTION` for level
ones (with the number of segments hit). Hosts are listed in the report's `hosts`
rows (`paths_lod`, `path_segments`, `stair_segments`); a host with no Paths LOD has
no authored path and is recorded, not skipped. Shelter terrain rows are not checked
(live Y). The sampled column approximates a walk along the authored path; it is not
the engine navmesh and not an infected-traversal proof.

Measured bounds: classes in `classes.json` that are not placed anywhere are
measured too (Geometry LOD only; no placement checks) and listed under
`catalog_bounds`; classes that cannot be measured are `CLASS_BOUNDS_UNMEASURED`
skips. `--bounds-out` writes `{classes: {name: geometry_min_m, geometry_max_m,
size_m, footprint_m, footprint_reserve_m, reserve_status}, unmeasured}` with
millimetre rounding, `applied: false`. `reserve_status` compares the authored
reserve with the measured X/Z footprint ignoring axis order (the catalogue does
not define it): `RESERVE_COVERS_MEASURED`, `RESERVE_BELOW_MEASURED` or `NO_RESERVE`.
The proposal is never applied automatically; the lead reviews it and updates the
catalogue by hand (P3.5). Reading models needs the installed Addons; without them
the run skips and no proposal is written.

Box overlaps are conservative candidates, especially for rotated/hollow pieces.
Host checks intersect the placed box with baked Geometry triangles; proxy marker
faces are excluded and referenced stock proxy solids are not expanded. Enclosed
solid volumes without intersecting triangle surfaces are not detected. Door leaf
planes approximate a closed threshold; missing/unusable selections are explicit
SKIPs. View Geometry is checked for **all** placed classes as a conservative
superset of interactive/searchable props, since runtime scripts decide action
availability; a finding on a decorative class requires review. Origin Y findings
are model-relative risks, not claims about final terrain contact. Runtime props
outside these authored data families are outside this inventory.

This task does not wire the audit into preland. The report's `wiring_needed`
field describes the future adapter: invoke this module with installed inputs,
retain the JSON report and require installed checks. Offline tests and reports
never establish DayZ placement, action, collision or multiplayer behavior.

## DamageZones census (WD-2B-1)

`tools/audit/damagezones_census.py` is a separate offline reader of installed config
data, kept beside the mesh audit because it uses the same bounded PBO reader and the
same installed folders:

```sh
python3 -B -m tools.audit.damagezones_census --addons /external/DayZ/Addons --addons /external/built-addons --report /tmp/dz-census.json
```

`--addons` may repeat (default: the shared release `ship_inputs.ADDONS`); give the
vanilla Addons first, then the built mod PBOs and any optional Workshop folder, as
later folders patch earlier classes the way load order does. It decodes only
`CfgVehicles/*/DamageSystem/DamageZones/*` (parent, `Health/hitpoints`) and `scope`
from `config.bin` members; compressed members and unknown entries are counted as
`config_unreadable`.

Output is counts under a fixed vocabulary, never class names, paths or a vanilla dump:
four families (vanilla infected, HC infected variants named with the mod prefix,
AI-actor classes, vanilla survivors) over spawnable (scope 2) classes, and a fixed zone
list. Per family and zone: how many classes carry the zone, a histogram of resolved
hit points, and the zone's parent link (which vocabulary zone it inherits). Zone parents
resolve in the class that declared the link, so a later patch to the base leg zone shows
up in every class that inherits it and not in classes that redeclare their own hit
points. Per family the `right_leg` block answers whether the right leg inherits the left
leg and whether the resolved hit points match. Families with no installed class are
`SKIP` reasons (`HC_INFECTED_NOT_INSTALLED`, `EAI_ACTORS_NOT_INSTALLED`, ...); missing
folders are `ADDONS_UNAVAILABLE`. Skips return zero unless `--require-installed`.

It reads config files only: it does not show how the engine applies zones to posed or
crawling bodies, and the numbers are not an acceptance result.
