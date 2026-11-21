# Offline world mesh audit

Run from the checkout:

```sh
python3 -B -m tools.audit.world_mesh_audit --addons /external/DayZ/Addons --reader /external/pinned-reader --report /tmp/world-mesh-report.json
```

`--reader` defaults to `HC_GENERATED_READER`; `--addons` defaults to the shared
release `ship_inputs.ADDONS`. The reader revision and file hashes come directly
from `interior_points_gen.Reader`, as described in [REGENERATE.md](REGENERATE.md).
No reader is vendored. Installed PBOs are indexed and read in place, without
asset extraction, dumps or changes to placement data. Full-client Addons are
needed for visual cost evidence; dedicated-server stripped meshes produce SKIP.

Missing reader/Addons print SKIP and return zero. Invalid available inputs or
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
contribute `vertices - 2` triangles. Section counts use the pinned reader's
`lod.sections`, not material or texture counts. Door clearance is a **0.6 m
diameter**, **1.8 m tall** vertical cylinder swept **1.5 m each way** along the
horizontal normal of a Geometry door-leaf selection. Contact tolerance is
**5 mm** for piece/host intersection checks. These are provisional audit policy,
not measured engine or player-load budgets.

Each finding/skip has a reason code and, for model/placement checks, a class.
Key finding codes are `PIVOT_OFFSET`, `FLOATING_ORIGIN`, `SINKING_ORIGIN`,
`PIECE_AABB_OVERLAP`, `HOST_GEOMETRY_ENCROACHMENT`,
`VIEW_GEOMETRY_EMPTY_OR_MISSING`, `DOOR_APRON_INTERSECTION`,
`VISUAL_TRIANGLE_COST` and `VISUAL_SECTION_COST`. Placement findings include
group/key and the other piece or host. Model metrics retain Geometry bounds,
centre, bottom and visual costs. Bounds use actual Geometry vertices; standalone
props restore their bounding centre, while hosts and `Land_` buildings follow
the existing support audit's raw building frame.

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
