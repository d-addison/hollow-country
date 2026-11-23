# Interior loot points

Current round-7 generator output: **1,247 above-floor points / 139 building
classes**, including optional furniture in approach and eye-segment checks. The
shipped merge contains **2,469 HC points / 184 groups**. Same-input unplaced
demand falls **636 → 614**. The requested 3,000 above-floor points remains unmet
by **1,753**; native acceptance remains pending. See the
final section for current reproduction, coverage and installer evidence. Earlier
rounds below are retained as historical evidence.

## Historical round-4 baseline

`mission/hollow-country/loot-points/additions-interiors.json` adds **587 new
surface points in 104 civilian building groups**, using the `additions.json`
schema. All points use `lootHCSurface` and the native `shelves` tag. They add CE
placement opportunities, not items outside the CE or additional item nominals.

| Family | Groups | New points |
| --- | ---: | ---: |
| Residential houses and flats | 48 | 242 |
| Garages, sheds, workshops and industrial buildings | 20 | 114 |
| Shops and food premises | 10 | 78 |
| Civic buildings, offices, schools and churches | 15 | 65 |
| Police | 6 | 48 |
| Medical | 3 | 24 |
| Fire stations | 2 | 16 |
| **Total** | **104** | **587** |

Sources are the operator's installed vanilla building and furniture PBOs and
stock mission prototype data, inspected read-only on 2026-11-20. Every point has
parallel `surface_sources` evidence: furniture model, proxy byte offset in the
building model, upright transform, local top coordinate and surface role.
`sources.model_surfaces` records furniture-member SHA-256 and bounds; each group
pins its entire stock prototype with `stock_sha256` and its building-model member
with `building_model_sha256`. No asset or vanilla dump is
included. Installed other-map prototypes were inspected too; all admitted groups
come from the Chernarus stock prototype.

The ODOL version-56 bounds format was checked against all five native-measured
props in `tools/package/interior_prop_boxes.json`; the largest discrepancy was
0.000000470 m. Points use closed flat-top furniture: cupboards, wardrobes,
bookshelves, lockers, desks, workbenches, tables, counters, freezers, tool crates,
bathroom cabinets and church stone lids. Open cabinet tops use their closed
counterpart's footprint to exclude swung doors. A bounding box alone is not a
measurement of the rendered top polygon; actual support and item fit remain
pending native inspection.

The transformation is `model = translation + local.x * basisX + local.y * basisY
+ local.z * basisZ`, then `stock = (model.z, model.y, -model.x)`. Each point sits
5 mm above the recorded top. Larger tops have 0.33 m edge insets; narrow tops get
one centred point. Candidates within 0.35 m horizontally and 0.30 m vertically
of existing CE points or another admitted point are excluded. Near-floor tops
are excluded. Where a repository interior template exists, its native model box
also bounds admission, and its path, hash and box are recorded on the group.
`interior_catalog.py` and `interior_templates.py` were reviewed for coordinate and
measurement conventions. Optional runtime `PropSlots` never provide unconditional
support: those props are not present in every building instance.

The file respects the current caps: eight surface points per group, four added
container slots, forty group slots, and 3,000 points per overlay. Categories are
contextual **per group**: household food/tools/books/clothes, workshop tools and
containers, civic books/tools, medical tools, police books/tools, and fire-station
tools/clothes. Stock usage restrictions still apply. The schema has only one
surface container per group; kitchen-only food versus wardrobe-only clothing
within one house cannot currently be expressed. Its validator also rejects the
weapon category, so police ammo/pistol points need a loader/schema change.

The requested **300 groups / 3,000 new points remains unfulfilled**. Inspection
found 219 civilian model groups across the available mission prototypes with
resolvable installed models, 127 with furniture proxies; only 104 yielded
admissible new points. Blindly lifting floor coordinates, using optional props,
or counting absent classes would not establish surface support. More coverage
needs measured baked-in shelves, beds, window sills, loft beams and other actual
surfaces. These are not done, as are per-point categories and point-specific
fit dimensions. The fixed loader range/height (0.30/0.50 m) particularly needs
native checking on narrow cupboard and locker tops.

For integration, the loot-points worker must load and merge `additions-*.json`
with `additions.json` by group and disjoint container names, preserving stock
pins. The release packaging owner must include this file wherever loot-point
inputs are allowlisted (including `tools/package/pbo.py`'s mission allowlist).
The base loader currently reads only `additions.json`; this file is intended to
be default-on when that integration lands. No loader or package code was edited
in this worker's scope. The repository currently ignores new `docs/*` files; the
integration owner must allowlist or explicitly add this requested document.

To disable this overlay, omit `additions-interiors.json` from the loader's input
set before building/installing. For an already installed overlay, roll back the
receipted loot boost and reinstall with this file omitted; removing a source JSON
alone does not undo generated `mapgroupproto.xml` changes.

Scratch rehearsal used the installed mission's verified pre-boost receipt
backups and copied only the registered CE install inputs into
`/tmp/hc-interiorpts/mission`. `parse_overlay` accepted this file and a scratch-only
merge with existing additions. All 587 point transforms, recorded top heights and
stock-point separation checks passed. The actual `install`/`rollback` functions
completed, with byte-exact restoration of all eight copied input files. Tail:

```text
baseline points 1222 after 1809
install: groups_added=172 points_added=1809 stale=[]
floor policy: transferred 188 -> 372; unplaced 1501 -> 1317
floor nonclothing slots after: 0.0 -> 0.0
rollback byte-exact PASS files=8
```

These are offline estimates, not observed loot spawns. Native CE admission,
physical support, reachability, ceiling clearance, item overlap, persistence and
performance remain pending one-server/at-most-one-client validation. Multiplayer
behaviour is not proven.

## Round 5 interior expansion (2026-11-20)

This section supersedes the r4 counts, bounds-only placement method and loader
integration assumptions above. The generator is now
`tools/package/interior_points_gen.py`. It inspects the installed vanilla
structure configs, baked-in furniture proxies and highest-detail visual mesh
faces. It never uses optional runtime `PropSlots` as guaranteed CE support.
The repository template catalog supplies class/Box provenance, not proof that a
search-site bounding box encloses every piece of architectural furniture.

A geometry check uncovered an r4 height error: some models have a nonzero
`bounding_center`, which must be restored to their stored vertices before the
proxy transform. The bus-station table demonstrates this independently: the
restored tabletop agrees with native shelf y=0.560379 to approximately 1 micrometre,
whereas the old bounds-only points were at y=0.102565. New points have an additional
5 mm lift. This is an offline coordinate cross-check, not a collision observation.

Every point records its actual supporting triangle, visual LOD/face index, local
coordinate and restored model centre. Furniture additionally records the member
name, member hash, upright proxy transform and proxy byte offset. Each building
pins its stock CE group and P3D member. No model, texture, full mesh or vanilla
config dump is included. Display geometry is evidence of a real surface; it does
not establish the engine's collision or loot-placement behaviour.

Admission requires a horizontal upward face, at most 25 mm vertical variation,
and support at four offsets 12 cm from the candidate centre. Existing CE points
and other additions exclude candidates within 0.60 m horizontally / 0.30 m
vertically. Closed furniture admits only the exposed top. Open shelves can admit
lower tiers with at least 0.55 m clearance. Baked-in ledges must be 0.35–2.20 m
above a nearby native room-floor point, outside native floor planes, and under a
ceiling 0.55–3.50 m above the candidate. This rejects roofs, broad floor surfaces,
uncovered exterior ledges and unsupported guesses. Doorway clearance and
reachability still require native inspection. Distinct furniture roles share
admission before the 32-point group cap; no dense building monopolizes the file.

Contextual roles include kitchen counters, bathroom cabinets, wardrobes, lockers,
bed mattresses, repair benches, desks, medical trays and architectural ledges.
Native categories remain **per group**, because the current schema has one
`lootHCSurface` container per group. Residential groups allow food, tools, books,
clothes and containers; medical buildings use native `tools`; police and military
buildings allow weapons; native Hunting cabins also allow weapons. Native item
usage restrictions still apply. Per-point food/wardrobe/medicine restrictions
need a loader/schema extension owned outside this worker's scope. Weapon/ammo
surface eligibility is already permitted by the current loader. These additions
provide CE capacity and do not create items, bypass CE or change type nominals.

The read-only decoder is `tools/audit/odol56.py`, a clean-room MIT reader for
ODOL version 56 models written for this repository; nothing external is
downloaded and no Blender installation or asset conversion is used. It reads
the LOD table and resolutions, named selections, proxies (path and matrix),
bounds, memory points, and the vertices, normals, faces and textures of every
LOD (Geometry, Fire Geometry and Paths included). It fails closed with a typed
`OdolError` (`UnsupportedVersion`, `UnsupportedCompression`, `MalformedModel`)
on any other version, on an unsupported compressed block, or on a LOD whose
layout does not parse exactly to its end. Models are never written out.
`READER_REVISION` and `READER_HASHES` in `interior_points_gen.py` are legacy
output provenance: shipped overlays embed them, so they stay fixed to keep
regenerated files byte-identical. They no longer select any code to download.
The `--reader` argument of the generator, audit and preservation CLIs is a
legacy, optional, ignored option; no CLI requires it. Reproduce from the
same installed vanilla build, unmodified stock prototype and stock map positions:

```sh
python3 -B -m tools.package.interior_points_gen \
  --addons "$DAYZ_ADDONS" --stock-proto "$STOCK_PROTO" \
  --map-pos "$STOCK_MAP_POS"
```

All inputs are read-only. Use the verified pre-boost prototype from the install
receipt when starting from an installed mission. Output ordering, float rounding,
role scheduling and source pins are deterministic. The output lists each refused
building group and its reason, plus map instance counts for admitted groups.
The caps are 32 surface points per group, at most 12 added container slots and
16,000 aggregate points across overlays; the loader retains its 40-slot group
budget logic. Its fixed 0.30 m range and 0.50 m height still require native fit
checks on narrow tops and with large items.

Integration remains blocked by two pre-existing issues outside this worker's
assigned files. `tools/package/loot_boost.py::shipped_points` rejects every
repeated group, including matching stock pins with disjoint floor/surface
containers. It needs to merge those containers while refusing conflicting pins,
repeated container ownership and repeated coordinates, then validate the complete
aggregate. `tools/package/pbo.py::MISSION_FILES` also omits
`loot-points/additions-interiors.json`; the package owner needs to include it.
These changes are necessary for default-on release integration. The explicit
scratch merge used below does not establish that the current shipped loader works.

The requested 300 building groups cannot be represented usefully in this stock
Chernarus building set: after excluding wrecks, wells, containers, train cars and
small boats, the prototype has 287 eligible types and the map places 217 of them
(9,546 instances). That is an upper bound which still includes some non-room
structures. Unplaced other-map variants, car wrecks and unsupported coordinates
must not be counted as covered interiors merely to satisfy a numeric target.
Groups that fail the support criteria remain listed in `sources.rejected_groups`.
Baked-in lofts, beams and sills which fail clearance/support sampling remain
unplaced; no absent engine experiment is accepted.

Physical support under the engine's actual geometry, door/stair clearance,
reachability, item dimensions, CE tag matching and placement, persistence,
restart behaviour and performance remain unproven in DayZ. Acceptance still needs
one server and at most one client. Nothing here proves multiplayer behaviour or
3–6-player performance. No Enforce source changed, so Enforce lint and the native
compile gate are not applicable to this worker's diff. No unit tests were added
or changed; validation uses the actual packaging and floor-policy functions.

Clothing eligibility is another policy limitation: declaring `clothes` on a
wardrobe-top container does not make a type tagged only `floor` match `shelves`.
The current `loot_floor_policy.retag_types` leaves floor-eligible clothing tags
unchanged. The policy owner needs to preserve floor eligibility while explicitly
allowing suitable clothing on raised receivers if wardrobe clothing is required.
No such tag rewrite or per-spot category isolation is claimed by this point data.

### Final round-5 counts and rehearsal

Authored **3,925 surface points across 201 groups**, versus r4 **587 / 104**: a net increase of **3,338 points and 97 groups**. The point target is exceeded; the 300-group target remains unmet. Of these groups, **148** occur in the stock map positions, covering **5,646 building instances**. The other **53** are stock-prototype variants with no placement in this map; they are not counted as occupied map coverage. The placed types contain **2,850 distinct point coordinates**, repeated by CE across their instances.

| Family | Groups | Surface points |
| --- | ---: | ---: |
| civic | 33 | 604 |
| fire | 2 | 64 |
| garage_shed | 43 | 822 |
| kitchen | 9 | 235 |
| medical | 4 | 94 |
| military | 34 | 915 |
| police | 6 | 192 |
| residential | 70 | 999 |
| **Total** | **201** | **3,925** |

The final overlay SHA-256 is `ed388f75cc8be3e89efd0f112014a3ff43c53e2286a1625dd7d1de8c93b22387` (3,974,715 bytes). Every final source hash, stock-group pin, proxy transform and supporting-plane height was replayed. Maximum height-rounding error was 0.5 micrometres; points on shared triangle edges allowed up to 2 micrometres of horizontal evidence-rounding tolerance. All 3,925 points passed. This checks static coordinates, not engine collision.

Rehearsal used read-only installed mission inputs and verified pre-boost receipt backups copied into a disposable scratch mission. A separate frozen stock prototype was used for generation. The loader's own `parse_overlay` accepted both this file and an explicit merge with `additions.json`: **227 groups / 5,147 points**, no stale pins. The merge asserts matching stock pins and disjoint container ownership; **123 groups** require that merge behaviour. Current `loot_boost validate` still exits 1 at the shipped-loader duplicate-group guard, as described above.

The controlled comparison replays the r4 file and the new file against identical CE inputs and the current floor policy. Transfers rise **1,431 → 1,642**; unplaced demand falls **532 → 323**, a reduction of **209 slots**. Displaced demand changes **1,963 → 1,965**, explaining why transfer growth is 211 rather than 209. The brief's historical **1,501 → 608** figures are retained as historical references; this input snapshot does not reproduce 608, so the current reduction is not attributed against that different baseline. The policy retains its **six explicitly allowed Military weapon-floor exception slots**; no exception was added here.

Actual packaging-function output tail:

```text
surface replay PASS groups=201 points=3925 max_height_error_m=0.000000500
merged parse_overlay PASS groups=227 points=5147 stale=[]
floor policy transferred 1431 -> 1642; unplaced 532 -> 323; exception slots 6
install PASS changed_files=6 points=5147
rollback byte-exact PASS restored=6 inputs_checked=8
shipped CLI validate exit=1 (disjoint-container group overlap blocker)
```

The real `install`/`rollback` path restored all eight copied inputs byte-for-byte, including the six files changed by installation. Generator syntax and `git diff --check` also passed. No live mission was written. Native spawning, support/clearance, single-client observation and release integration remain pending.

`docs/LOOT_POINTS.md` is currently untracked and ignored by `/docs/*`; the lead must explicitly include this appended document when landing it. This worker did not change `.gitignore` or write git metadata.

## Round 6 shelf reach audit (#256, 2026-11-20)

This section supersedes the round-5 shelf counts and its bounds-only reach
qualification. `tools/package/loot_reach_audit.py` audits every authored
`lootHCSurface` container in `additions*.json`. Floor containers are counted but
are outside this shelf-only check. Settings and family/policy JSON files are
not coordinate overlays. The tool uses the in-repo ODOL reader
(`tools/audit/odol56.py`), installed vanilla building/furniture PBO members, the unmodified
stock prototype, `interior_catalog.py`, `interior_templates.py`, measured
`interior_prop_boxes.json`, and the authored interior templates. Assets and
unpacked model/memory data remain external and are never written by this tool.
Its `--reader` option is a legacy argument, optional and ignored.

```sh
python3 -B -m tools.package.loot_reach_audit \
  --addons "$DAYZ_ADDONS" --stock-proto "$STOCK_PROTO" \
  --report "$HC_INTERIOR_WORK/reach.json"
# Review the refusal report, then remove points with insufficient static evidence:
python3 -B -m tools.package.loot_reach_audit \
  --addons "$DAYZ_ADDONS" --stock-proto "$STOCK_PROTO" \
  --report "$HC_INTERIOR_WORK/reach-before.json" --fix
```

The static admission checks are deliberately conservative:

- Resolve and verify stock group/building/support-member pins before assessing
  coordinates. Re-read support triangles and replay proxy transforms; require
  support at the centre and four 12 cm offsets rather than trusting saved evidence.
- Require the point within the building's visual envelope and above an actual
  building geometry floor at a nearby native CE floor-anchor level. An envelope
  alone does not establish a room footprint.
- Reject geometry within the 50 cm loot height and horizontal box cross sections.
  Include upright baked furniture/clutter proxies, using visual triangles as
  conservative blockers where a proxy has no decoded geometry LOD.
- Require a stance within 1 m horizontally, with the shelf 0.25–1.8 m above its
  floor, 1.8 m standing clearance and a sampled 22 cm body radius. Require a clear
  eye-to-item segment and a clear same-storey corridor to a native CE floor anchor
  within 6 m; sample corridor floor support every 25 cm. The native CE anchor is
  a room reference, not proof a player can navigate there from the entrance.
- Treat every optional interior PropSlot history as a possible obstruction; union
  its authored box with the rotated, offset native prop box when measured. Optional
  props never supply unconditional surface support. Template search-site bounds
  are not used as building bounds or evidence of collision-free access.

`--fix` drops refused points, removes their parallel `surface_sources`, adjusts
container `lootmax` with the existing loader formula, and removes empty containers
and groups. It preserves categories, tags, stock pins and remaining source evidence.
A source-build/pin mismatch refuses execution instead of deleting points based on
another build. Failure counts overlap when a point fails multiple checks. The
read-only command exits 1 for refusals; a fix reports the original failures and
exits 0 after validating the resulting overlay schema. It remains an offline
filter, not a native acceptance gate.

The decoded memory LODs are inventoried, but their presence does not establish
walkability. Door animations, locked doors, stairs, irregular or tilted/nested
proxies, collision components not decoded by the ODOL reader, complete item
volume/placement range, continuous body collision, terrain around each instance,
CE placement and actual vicinity/search interaction need native observation.
The finite static samples can conservatively reject good points and cannot prove
that every retained point works in DayZ. One server and at most one client must
check those remaining gates; multiplayer behaviour and target-load performance
remain unproven. Features remain default-on; no new settings or Enforce code were
introduced by this audit.

Round-6 rehearsal baseline (current checkout and copied installed mission inputs):
`install` wrote **5,147 HC points / 227 groups / 350 containers**, with no stale
stock pins. Eight files changed; `rollback` restored all **13** copied inputs
byte-for-byte. The current floor policy reported **2,197 displaced / 1,733
transferred / 464 unplaced** slots. This differs from the historical round-5
snapshot and is the baseline for the round-6 comparison. It is an offline install
and rollback observation, not a CE spawning observation.

### Building-frame correction

The round-5 centre-restoration rule is valid for supporting furniture proxies,
but was incorrectly generalized to baked building vertices. Stock CE positions
match the building's **stored vertices without adding the building bounding
centre**. Nine stock floor anchors across `Land_House_1W01`,
`Land_BusStation_building` and `Land_City_PoliceStation` matched the unshifted
geometry planes within **0.000256 m**; adding the centre displaced their floors
by metres. Independently, the bus-station native table shelf matched its restored
furniture-proxy plane within **0.000000684 m**. These are different local frames.
The audit uses unshifted building visual/geometry/roadway LODs and restored
furniture-local meshes before applying proxy transforms. Geometry and roadway
LODs both supply floor evidence. An initial audit using restored building centres
was discarded and the original overlay restored before the corrected pass.

Baked ledge evidence with a nonzero restored building centre is refused as
`building_frame_mismatch`; coordinates are dropped, rather than translating them
onto what may actually be a floor or an exterior ledge. Thus the retained data
never claims the old shifted evidence proves a real shelf. The generator owner
must correct `interior_points_gen.py` to use the building's stock CE frame for
baked surfaces and floor comparisons, then rerun the reach audit before replacing
these data. Regenerating with the unchanged generator would reintroduce the error.
No generator file was changed within this worker's scope.

### Final round-6 counts and install rehearsal

The corrected audit removes **3,826 / 3,925** shelf candidates and retains **99
points across 33 groups**. Of those groups, **29** occur in the stock map positions
(**495 building instances**); unplaced variants are not counted as occupied map
coverage. All **1,222 floor points** remain byte-for-byte unchanged. The shipped
merge therefore changes **5,147 → 1,321 HC points**, **227 → 154 groups**, and
**350 → 182 added containers**. This deliberately gives up the historical 3,000
surface-point target rather than retain shifted or insufficiently evidenced
coordinates. Refusals include conservative evidence failures; these counts are
not a claim that 3,826 points were observed failing in the engine.

| Static refusal class | Points (overlapping counts) |
| --- | ---: |
| Building frame mismatch | 2,679 |
| Floating or insufficient edge support | 2,676 |
| Wall/furniture box overlap | 980 |
| Outside supported room footprint | 965 |
| Under furniture or ceiling | 926 |
| Above reach or no nearby same-floor anchor | 604 |
| No clear standing space | 233 |
| Outside building bounds | 209 |
| No clear floor approach | 48 |
| Wall/furniture occludes eye-to-item segment | 15 |

The audit examined **201 buildings**, all with decoded roadway LODs, **7,257
upright proxy instances** and **5,968 memory selections**. Two buildings lacked a
decoded memory LOD; **44** proxy member references were unresolved, and **241**
proxy instances used a visual blocker fallback. These are explicit limits of the
static evidence, not accepted engine experiments. A fresh read-only pass checks
the retained overlay independently. The data records refusal counts by class and
group, its previous input hash, and the conservative reach limits in
`sources.reach_audit`; detailed local reports retain refused coordinates.

The actual installer wrote **1,321 HC points / 154 groups / 182 containers**, with
**no stale stock pins**. It changed eight copied files, and rollback restored all
**13 inputs byte-for-byte**. Against the identical baseline, floor-policy
transfers changed **1,733 → 1,425**, unplaced demand **464 → 770**, and displaced
demand **2,197 → 2,195**. The reduction in usable capacity is explicit; this audit
does not compensate by creating loot outside CE or changing item nominals.

Verification also checked that every retained coordinate and parallel source is
an exact subsequence of the original input, with categories, tags, families and
stock pins preserved. Only capacities, empty group/container removal and audit
provenance changed around those removals. No live mission was written. No unit
tests were added or modified; no existing test module targets this new utility.
Enforce lint/performance checks and native compilation are not applicable because
no `.c` files changed. Native CE spawning, physical item fit, doorway/stair access,
vicinity/search interaction and one-server/at-most-one-client observation remain
pending; issue #256's native reachability acceptance is not claimed complete.

Final verification tail:

```text
fresh read-only reach audit PASS shelf_points=99 failures=0
exact retained coordinate/source subsequence PASS; floor overlay unchanged
merged overlay parse PASS groups=154 points=1321
install PASS HC_points=1321 containers=182 stale=[] changed_files=8
rollback byte-exact PASS inputs=13
syntax PASS; git diff --check PASS
```

The retained 33 building groups have decoded memory/roadway LODs and no unresolved
proxy member references; 74 proxy instances still require visual blocker
fallbacks. All native acceptance limits above remain in force. Scratch inputs,
the scratch reports are moved outside the worktree before
handoff because `.scratch/` is not ignored in this checkout. The lead should
ignore that directory if future briefs continue to prescribe it for local dumps.

## Round 6 generator frame repair and renewed surfaces (2026-11-20)

This section supersedes the preceding 99-point result as the shipped interior
point set. The preceding refusal report remains the historical diagnosis, not a
reason to regenerate the old shifted points. Both disjoint-container merging and
packaging integration are present in this checkout; the round-5 integration
blockers above are historical.

`interior_points_gen.py` now explicitly reads baked building meshes with
`restore_center=False`. Its vertices, floor comparisons, ceiling rays and saved
support triangles therefore share the stock CE model frame. Furniture meshes
retain centre restoration before the upright proxy transform. The stock axis
conversion remains `(model.z, model.y, -model.x)`; no building-centre translation
is applied after that conversion. A fresh replay of the same first three native
floor anchors in each of `Land_House_1W01`, `Land_BusStation_building` and
`Land_City_PoliceStation` matched the geometry/roadway floors within 0.000256 m
(maxima by building: 0.000001, 0.000256 and 0.000003 m). This is static coordinate
evidence, not a native interaction test. A separate replay through the generator's
own highest-detail visual meshes put all nine anchors within 0.000369 m of the
unshifted floor faces. The previous restoration moved house floors by 2.923910 m,
bus-station floors by approximately 0.611985 m, and police floor comparisons by
up to 6.689900 m; one house anchor missed the shifted horizontal mesh entirely.

Candidate sampling now uses a 0.30 m lattice, triangle and face-bounds centres,
and inset/midline samples along narrow surfaces. The five existing measured
native prop boxes in `interior_prop_boxes.json` are unchanged. For matching
furniture members their footprint centres seed additional candidates; height is
snapped to the actual supporting visual triangle, with the existing 5 mm lift
and five 12 cm footprint support samples. A box does not supply unconditional
support or replace the mesh. Its source hash is recorded in the generated data.
Additional inspected vanilla support models include stacked/folding/hospital
beds, wall-unit cabinets, sink cabinets and benches. These provide candidates
only where their actual horizontal surfaces pass every check.

Crucially, the generator runs the unchanged `loot_reach_audit.Audit.check` before
spacing and the 32-point group cap. A refused top cannot consume a slot or exclude
a nearby reachable alternative. Round-robin selection still shares capacity
between furniture roles and baked ledges. The 0.60 m separation, native-point
exclusion, reach, standing clearance, eye segment, optional-prop obstruction and
floor-approach thresholds are unchanged. Generated provenance records the
candidate checks and overlapping refusal counts. A separate read-only audit of
the emitted overlay is required as the final static check; no audit threshold was
relaxed to improve the count. Use the existing round-5 reproduction command with
the corrected generator; no manual JSON editing or follow-up pruning is needed.

Rehearsal copies only registered CE type inputs, globals, core/limits definitions
and the prototype to a disposable mission outside the repository. The installed
live prototype differs from its loot receipt's post-install hash, so it is not
used as stock. Every selected pre-boost receipt backup is instead checked against
its recorded `before` hash and restored **only into the scratch copy**. Both
historical and regenerated overlays use those identical frozen inputs and the
current shipped floor policy. No live mission or profile is written.

### Regenerated counts and controlled install comparison

The regenerated file contains **917 points across 121 building classes**:
**818 more points and 88 more surface groups** than the pruned set. Of those
classes, **102** are placed in the frozen stock map positions, covering **3,152
building instances** and **790 distinct placed-type point coordinates**. The
other **19** stock-prototype variants have no instances in this map and are not
counted as occupied coverage. All **1,222 original floor points** remain unchanged.
The generated surface file is 1,044,399 bytes, SHA-256
`6b8370b906833f7f3d25559b0e57daf65d350ff9cb23a1b3f9dd76aa65f7e06a`.

| Family | Surface groups | Surface points |
| --- | ---: | ---: |
| Civic | 16 | 86 |
| Fire | 2 | 4 |
| Garage/shed | 21 | 171 |
| Kitchen/shop | 10 | 94 |
| Medical | 3 | 51 |
| Military | 19 | 196 |
| Police | 6 | 122 |
| Residential | 44 | 193 |
| **Total** | **121** | **917** |

Support roles are 605 baked ledges, 97 cabinet/shelf points, 96 kitchen-counter
points, 77 desk/table points, 33 repair-bench points, eight wardrobe tops and one
bed-mattress point. Merely adding a model to the candidate set does not imply
that its tops will pass reach/clearance; high locker tops and obstructed beds,
for example, do not become accepted points by naming their role.

The generator checks **51,818 candidates** before final spacing/capping. Its
stored overlapping refusal counts include 16,205 outside a supported room
footprint, 15,902 under furniture/ceilings, 14,851 with wall/furniture box overlap,
10,237 without standing space, 6,821 without a reachable floor anchor, 1,886
occluded from the eye and 1,806 without a clear floor approach. No candidate
checks report frame mismatch, transform mismatch or floating/edge support. These
are candidate counts, not unique surfaces or observed engine failures.
**The 3,000-point target remains unmet by 2,083 points.** Of 287 eligible stock
types, 162 yield no admitted top and four have no resolvable model. Their reasons
remain in generated provenance; no floor lifting, optional-prop support, duplicate
loot or relaxed audit limit compensates for the shortfall.

| Same-input rehearsal | Original r5 overlay | Pruned r6 overlay | Regenerated r6 overlay |
| --- | ---: | ---: | ---: |
| Surface points | 3,925 | 99 | 917 |
| Surface groups | 201 | 33 | 121 |
| Total authored HC points | 5,147 | 1,321 | 2,139 |
| Authored HC groups | 227 | 154 | 175 |
| Added HC containers | 350 | 182 | 270 |
| Floor-policy transferred demand | 1,733 | 1,425 | 1,551 |
| Floor-policy unplaced demand | 464 | 770 | 644 |
| Floor-policy displaced demand | 2,197 | 2,195 | 2,195 |

The new set recovers **126 transferred slots** and removes **126 unplaced slots**
versus the pruned overlay. It does not reproduce the original overlay's capacity:
that overlay contained insufficiently evidenced points. The two-slot displaced
change explains why its transfer difference and unplaced difference are not
identical. The current policy retains **21 weapon-floor exception slots** in all
three rehearsals; that policy is unchanged here.

The actual shipped merge and installer accept the regenerated overlay with no
stale stock pins. Installation changes eight files. Rollback restores all **11
copied input files byte-for-byte**, and removes the scratch receipt directory.
The rehearsal uses only the installer's actual registered inputs, not storage,
profiles, Workshop data or a copied live installation. Offline capacity changes
do not establish native CE placement or item spawning.

A fresh **read-only** audit of the emitted file passes **917 checked / zero
refusals**, without `--fix`. It inspects 121 buildings, all with decoded roadway
LODs, 6,317 upright proxy instances and 4,613 memory selections. The evidence
still has **22 unresolved proxy member references**, **213 visual blocker
fallbacks**, and **one building without decoded memory**. These remain explicit
static-model limitations: zero recorded refusals does not establish complete
collision coverage or make those missing engine experiments accepted.

Final verification tail:

```text
stock frame anchors PASS n=9 geometry/roadway_max_error_m=0.000256
corrected generator visual anchors PASS n=9 max_error_m<0.000369
fresh read-only reach audit PASS shelf_points=917 refused=0 failure_counts={}
floor overlay byte-exact vs HEAD PASS points=1222
merged overlay parse/install PASS HC_points=2139 groups=175 containers=270 stale=[]
floor policy transferred 1425 -> 1551; unplaced 770 -> 644
install PASS changed_files=8
rollback byte-exact PASS inputs=11
Python syntax PASS; generated data restricted-string check PASS; git diff --check PASS
```

No new settings, Enforce changes, unit tests or Python Enforce harnesses were
introduced. No existing test module targets the changed utilities; no unit suite
was run. Enforce lint/performance and the native compile gate are not applicable
to this Python/data/documentation diff. The prior worker's audit utility is
retained without changes to its admission limits. Scratch mission inputs, the
diagnostic reports remain outside the worktree. The supplied
reproduction command generates the audited file directly.

Physical item support and fit, actual CE tag admission/spawning, complete
collision and doorway/stair access, vicinity/search interaction, persistence,
restart behaviour and performance remain unproven in DayZ. Acceptance still
requires one server and at most one client; multiplayer behaviour is not proven.
The 3,000-point expansion target and unresolved static-model evidence remain
open, and issue #256's native reachability acceptance is not claimed complete.

Suggested lead-owned README/MODULE_STATUS wording: “Default-on interior loot
adds 917 statically audited above-floor points in 121 classes (2,139 total HC
points / 175 merged groups); frame repair and scratch install/rollback pass;
3,000-point target and native CE/reach/fit/restart acceptance remain pending.”
No loader, packaging, settings or other-owner file changes are needed for this
regenerated set in the current checkout. The lead owns native acceptance and
updates to those summary documents.

## Round 7 optional-furniture reach correction and denser sampling (2026-11-20)

This section supersedes the round-6 counts and its claim that optional props
already obstructed every part of the reach witness. Issue
[#274](https://github.com/d-addison/hollow-country/issues/274) identified the gap:
standing positions and loot positions respected optional furniture, but corridor
and eye rays only respected building geometry and baked furniture proxies.

The audit now intersects each existing corridor ray and the eye-to-item segment
with the solid bounds of every optional `PropSlot`, conservatively unioned across
all authored histories. These are the same bounds already expanded to include
independently measured native prop extents. A closed-segment slab test catches
crossing, tangent and wholly contained segments, including endpoints inside a
prop, parallel rays and zero-length segments. Optional furniture supplies no
support. All previous geometry, support, spacing, standing, footprint, floor
continuity, rise and reach checks remain in force with their original limits.

The corrected read-only audit refuses **two of the original 917 points**, both
in `Land_Tisy_KitchenRoom`, for `no_clear_floor_approach`. The refused original
stock coordinates are `(10.918402, -3.313365, -1.738918)` and
`(10.870401, -3.313365, -2.4)`. Its other **915 points** pass. The generator applies
this correction before admission, so these unsupported approach witnesses cannot
consume capacity or exclude a nearby valid alternative.

The generator samples actual upward horizontal mesh faces on a **0.15 m lattice**
(previously 0.30 m), retaining triangle centres, face-bounds centres, measured prop
centres and inset/midline samples. This changes candidate discovery, not final
spacing or support tolerances. Additional inspected installed vanilla model names
cover bar shelves, racks, shop counters with tills, kitchen tables, washing
machines, electric stoves, pianos, beds/stretchers, sofas, benches, gym boxes and
closed boxes. Each still requires a real supporting triangle and all five
12 cm footprint samples, 50 cm item-box clearance and an audited reach witness.
No floor coordinates are lifted and no runtime prop becomes guaranteed support.

Dense generation may stop a candidate after its first failed support, room or
clearance stage;
it cannot admit a candidate without completing every check. Generated refusal
counts therefore describe evaluated stages and are not directly comparable to
round 6's overlapping all-stage counts. The independent read-only audit retains
its full refusal reporting and must pass on every emitted point.

Read-only sources are the installed vanilla PBOs and the live mission's verified
pre-boost receipt backups. Only registered CE inputs and limit definitions are
copied into disposable storage outside the repository. The stock prototype pin
and map-position pin match round 6. Type inputs reflect the currently installed
mission and differ from the historical round-6 rehearsal: identical-input
round-7 comparisons, rather than its historical 644, establish the unplaced
demand change. The round-7 original-overlay baseline is **636 unplaced / 1,534
transferred / 2,170 displaced**; removing only the two newly refused points gives
**637 unplaced / 1,533 transferred / 2,170 displaced**. These are offline capacity
estimates, not observed spawn counts.

### Generated coverage and controlled installation

The round-7 file contains **1,247 points / 139 classes**, an increase of **330
points (36.0%) / 18 classes** over round 6. No previously admitted class loses
coverage or its point count. The **3,000-point target remains unmet by 1,753**.
The four missing-model classes and 144 classes with no admissible top remain
listed in `sources.rejected_groups`; no unresolved class is filled with guesses.

| Family | Classes before | Classes after | Points before | Points after |
| --- | ---: | ---: | ---: | ---: |
| Civic | 16 | 16 | 86 | 98 |
| Fire | 2 | 2 | 4 | 5 |
| Garage/shed | 21 | 24 | 171 | 195 |
| Kitchen/shop | 10 | 10 | 94 | 110 |
| Medical | 3 | 3 | 51 | 51 |
| Military | 19 | 27 | 196 | 338 |
| Police | 6 | 6 | 122 | 162 |
| Residential | 44 | 51 | 193 | 288 |
| **Total** | **121** | **139** | **917** | **1,247** |

Of the admitted classes, **114 are placed / 3,654 instances / 1,070 placed-type
coordinates**, versus 102 / 3,152 / 790 previously. The remaining **25 classes**
are unplaced stock-prototype variants and do not count as occupied map coverage.
The unchanged eligible universe is 287 stock types, 217 placed types and 9,921
map instances. Nine admitted classes reach the unchanged 32-point cap.

Admitted support roles are **611 baked ledges, 214 bed/mattress points, 114
kitchen-counter points, 99 cabinet/shelf points, 87 desk/table points, 69 bench/
seat points, 44 repair-bench points and nine wardrobe tops**. Appliance
candidates produced no admitted appliance-top points; inspected names alone
never establish a shippable surface. All 18 newly covered
class names and their evidence are available in the generated group map. These
include two airfield/industrial variants, a garage row, seven residential/ruin/
slum variants, seven military variants and a workshop.

The generator evaluates **117,088 candidates**, admits 1,247 after spacing/caps,
and refuses **115,841** at the following stages. In this run each refusal has
one reported reason; later reasons are deliberately not evaluated after refusal.
This table is not an all-stage comparison against round 6.

| Candidate refusal reason | Count |
| --- | ---: |
| Outside supported room footprint | 31,406 |
| No clear standing space | 27,092 |
| Under furniture or ceiling | 23,505 |
| Above reach or no nearby floor anchor | 14,937 |
| Wall/furniture box overlap | 8,383 |
| Wall/furniture occludes eye-to-item segment | 6,575 |
| No clear floor approach | 3,882 |
| Outside building bounds | 61 |
| **Total refused candidates** | **115,841** |

No checked candidate reports a frame, transform or floating/edge-support error.
The two original kitchen coordinates refused by the corrected audit are absent;
the regenerated kitchen has **seven points versus six previously**, using valid
alternative witnesses. The file is 1,474,307 bytes, SHA-256
`39bdbfffd7e9b8f60fd76c83ea32faff7e48ed09ba0664ccb78740f263f73ee8`.

| Same-input round-7 rehearsal | Original 917 points | Furniture-fix-only 915 | Expanded 1,247 |
| --- | ---: | ---: | ---: |
| Floor-policy transferred demand | 1,534 | 1,533 | 1,556 |
| Floor-policy unplaced demand | 636 | 637 | 614 |
| Floor-policy displaced demand | 2,170 | 2,170 | 2,170 |
| Retained weapon-floor exception slots | 21 | 21 | 21 |

The expanded shipped merge installs **2,469 HC points / 184 groups / 288
containers**, versus 2,139 / 175 / 270. There are no stale stock pins. Installation
changes eight copied files; rollback restores all **11 inputs byte-for-byte**
and removes its receipt directory. All **1,222 original floor points** remain
byte-exact against HEAD. The extra placement coordinates are not additional item
nominals or unlimited slots: existing container and group capacity caps remain.

The independent fresh read-only audit passes **1,247 checked / zero refusals**,
without `--fix`. All 139 buildings have decoded roadway LODs; the pass inspects
6,753 upright proxy instances and 4,996 memory selections. Static evidence still
has **44 unresolved proxy member references, 219 visual blocker fallbacks and
one building without decoded memory**. More admitted classes expose more of
these missing references than round 6's 22 / 213 / one. A passing point audit
does not establish complete collision coverage or accept any missing engine
experiment. The earlier numeric-suffix proxy-name probe found no additional
resolvable upright proxies; unresolved references are not silently guessed.

Verification tail:

```text
original-overlay full audit: 917 checked; 2 optional-prop approach refusals
full-audit stage-reordering replay PASS identical report
segment/AABB manual boundary smoke PASS
generation: checked=117088 admitted=1247 refused=115841
fresh read-only reach audit PASS shelf_points=1247 refused=0 failure_counts={}
floor overlay byte-exact vs HEAD PASS points=1222
merged parse/install PASS HC_points=2469 groups=184 containers=288 stale=[]
floor policy transferred 1534 -> 1556; unplaced 636 -> 614
install PASS changed_files=8
rollback byte-exact PASS inputs=11
Python syntax PASS files=2; restricted strings PASS; git diff --check PASS
Enforce lint/perf/native compile N/A (.c unchanged); unit suite not run
```

Suggested lead-owned README/MODULE_STATUS wording: “Default-on interior loot
adds 1,247 statically audited above-floor points in 139 classes (2,469 total HC
points / 184 merged groups); optional-furniture corridor/sight checks and scratch
install/rollback pass; 3,000-point target and native CE/reach/fit/restart acceptance
remain pending.” No other-owner source changes are needed for this overlay;
the lead owns these summary edits and native acceptance. Keep issue #274 open
for the remaining target and engine evidence.

Reproduce with the round-5 generator command above,
using the verified pre-boost prototype and stock map positions. Then run the
independent audit without `--fix`:

```sh
python3 -B -m tools.package.loot_reach_audit \
  --addons "$DAYZ_ADDONS" --stock-proto "$STOCK_PROTO" \
  --report "$HC_INTERIOR_WORK/reach-report.json"
```

No settings, Enforce code or floor-overlay changes are part of this pass. No new
unit tests or Enforce harnesses are written, and no existing test module targets
the two changed utilities. Only the changed Python utilities receive syntax and
manual boundary checks; no unit suite is run. Enforce lint/performance and native
compilation do not apply to this Python/data/documentation diff. The lead still
owns the native boot and gameplay observation.

Native CE admission/spawning, physical support and item fit, complete collision
coverage, doors/stairs and approach access, vicinity/search interaction,
persistence, restart behaviour and performance remain unproven. Acceptance needs
one server and at most one client; multiplayer behaviour is not proven. No
missing engine experiment is accepted by the static checks or the rehearsal.

## Surface-point preservation after fa0c2ac8

Owner: 2026-11-20, full coverage: no place stays vanilla-only. Every removal needs an explicit, reasoned refusal reported by a check. Native acceptance remains pending.

`fa0c2ac8` used dedicated-server PBOs for visual generation/reach checks. Those models strip visual detail: its Chapel root visual LOD has 144 faces, while the prior evidence cites face 1452. The installed full-client Chapel, Office1 and Barracks1 model hashes exactly match `335915c6`; they are not obsolete geometry. Rechecking on server PBOs falsely called existing furniture tops unsupported. Some server collision representations also differ. All 1,292 prior surface coordinates pass the unchanged support/reach rules on the full-client assets, including the seven refused against server collision. The support-v3 slope rule is a relaxation of v2, not a reason to discard these points.

The generator and reach auditor now reject an identifiable dedicated-server-only addon folder as a visual source. Collision auditing can still use such a folder explicitly; it cannot establish rendered support. Use full-client assets for the combined visual/collision qualification. Do not refresh historical visual evidence to server-stripped meshes. The guard recognizes the server executable beside addons; copied addon-only directories still require the operator to identify their source correctly.

Prior-layout merging now preserves passing prior coordinates before adding compatible new points. The preservation utility re-reads both layouts, verifies actual stock proxy transforms, refreshes evidence only through current installed triangles, and records every excluded coordinate. Area/spacing caps govern additions; prior valid coordinates are not silently replaced. No admission margin, native stock coordinate, lootmax policy or item quantity multiplier was relaxed.

### Counts and attribution

| Revision | Surface points | Floor points | Total | All HC types | Placed HC types |
| --- | ---: | ---: | ---: | ---: | ---: |
| 335915c6 | 1,292 | 443 | 1,735 | 180 | 160 |
| fa0c2ac8 | 1,079 | 679 | 1,758 | 227 | 201 |
| Corrected | 1,301 | 679 | 1,980 | 224 | 202 |

Placed coverage is 202 of the previously counted 263 placed stock types, not full coverage. The unfilled types and native experiments remain open. No type loses points relative to `335915c6`, in either overlay. All 1,735 original coordinates survive unchanged. The 58 combined per-type losses in `fa0c2ac8` are eliminated.

Counts below concern **coordinates omitted**, not net point counts: replacing a coordinate can keep a type's count unchanged. There were 889 omissions across all types; 507 belonged to the 64 types whose surface count fell. Every one is restored. The emitted overlay contains the exact coordinates, historical rule results and decisions under `sources.point_preservation`; the check verifies completeness against both hashed input files.

| Original omission cause | All types | 64 types with falling surface counts | Remaining vs 335915c6 |
| --- | ---: | ---: | ---: |
| Stripped-server visual reach refusal | 531 | 408 | 0 |
| Stripped-server collision support refusal | 7 | 7 | 0 |
| Surface spacing replacement | 319 | 92 | 0 |
| Surface area-cap replacement | 32 | 0 | 0 |
| New support-v3 rule, with the same assets | 0 | 0 | 0 |
| Floor-v2 spacing/discs against new floors | 0 | 0 | 0 |
| Partition/cache artefact attributed to fa0c2ac8 | 0 | 0 | 0 |
| Nondeterminism attributed | 0 | 0 | 0 |

The historical reach results were `floating_or_edge_support` for 530 points and `outside_building_bounds` for 21 (20 overlap), hence 531 unique points. Historical collision results were `no_collision_support_within_8cm` for six and `collision_support_footprint_edge` for one. These are false refusals from the asset choice: none remains on the full-client meshes. Floor generation never edits surface coordinates; its surface-overlay option skips already covered groups.

Chapel is restored to **2 surface points**, Fortified Nest Big to **1**, and Slum House6 to **1**; each has zero floor points. All pass fresh full-client support and reach checks.

### Per-type attribution for the 64 surface-count losses

V = stripped-server visual refusal; C = stripped-server collision refusal; S = spacing replacement. Cap replacements are zero in this subset. Counts are omitted coordinates; all are restored.

| Type | Surface 335915 → fa0c → corrected | V | C | S |
| --- | ---: | ---: | ---: | ---: |
| Land_Castle_Gate | 1 → 0 → 1 | 1 | 0 | 0 |
| Land_CementWorks_SiloBig1A | 6 → 4 → 6 | 4 | 0 | 2 |
| Land_Chapel | 2 → 0 → 2 | 2 | 0 | 0 |
| Land_Church4 | 5 → 3 → 5 | 3 | 0 | 0 |
| Land_Church4_Dam | 5 → 3 → 5 | 3 | 0 | 0 |
| Land_Church4_Lightblue | 5 → 3 → 5 | 3 | 0 | 0 |
| Land_Church4_Red | 5 → 3 → 5 | 3 | 0 | 0 |
| Land_Church4_White | 5 → 3 → 5 | 3 | 0 | 0 |
| Land_Church4_Yellow_Dam | 4 → 3 → 4 | 4 | 0 | 0 |
| Land_City_PoliceStation | 32 → 30 → 32 | 11 | 0 | 7 |
| Land_City_PoliceStation_Enoch | 32 → 30 → 32 | 11 | 0 | 7 |
| Land_City_Stand_Grocery | 3 → 2 → 3 | 3 | 0 | 0 |
| Land_CoalPlant_Main | 4 → 3 → 4 | 1 | 0 | 3 |
| Land_Construction_Building | 17 → 0 → 17 | 17 | 0 | 0 |
| Land_Construction_House2 | 2 → 0 → 2 | 2 | 0 | 0 |
| Land_Factory_Lathes | 11 → 10 → 11 | 1 | 0 | 0 |
| Land_Farm_CowshedA | 1 → 0 → 1 | 1 | 0 | 0 |
| Land_Farm_CowshedB | 9 → 0 → 9 | 9 | 0 | 0 |
| Land_Farm_CowshedC | 3 → 0 → 3 | 3 | 0 | 0 |
| Land_FuelStation_Build | 4 → 0 → 4 | 4 | 0 | 0 |
| Land_FuelStation_Build_Enoch | 4 → 1 → 4 | 4 | 0 | 0 |
| Land_Garage_Office | 10 → 2 → 10 | 8 | 0 | 1 |
| Land_Garage_Row_Big | 8 → 2 → 8 | 8 | 0 | 0 |
| Land_HouseBlock_1F3 | 2 → 0 → 2 | 0 | 2 | 0 |
| Land_HouseBlock_1F_Corner | 12 → 6 → 12 | 6 | 0 | 4 |
| Land_HouseBlock_2F6 | 11 → 3 → 11 | 8 | 0 | 0 |
| Land_HouseBlock_3F_Corner1 | 30 → 19 → 30 | 12 | 0 | 0 |
| Land_HouseBlock_3F_Corner2 | 16 → 9 → 16 | 9 | 0 | 3 |
| Land_House_1B01_Pub | 25 → 10 → 25 | 16 | 0 | 8 |
| Land_House_1W02 | 3 → 2 → 3 | 1 | 0 | 2 |
| Land_House_1W03 | 9 → 5 → 9 | 5 | 0 | 3 |
| Land_House_1W04 | 4 → 1 → 4 | 3 | 0 | 1 |
| Land_House_1W07 | 11 → 8 → 11 | 4 | 0 | 5 |
| Land_House_1W10 | 7 → 5 → 7 | 2 | 0 | 5 |
| Land_House_1W10_Brown | 6 → 4 → 6 | 3 | 0 | 3 |
| Land_House_1W12_Brown | 6 → 5 → 6 | 1 | 0 | 5 |
| Land_House_1W13_Dam | 6 → 4 → 6 | 3 | 0 | 1 |
| Land_House_2B01 | 5 → 4 → 5 | 1 | 0 | 4 |
| Land_House_2B03 | 1 → 0 → 1 | 1 | 0 | 0 |
| Land_House_2W02 | 7 → 5 → 7 | 2 | 0 | 5 |
| Land_House_2W04 | 21 → 7 → 21 | 15 | 0 | 1 |
| Land_House_2W04_Yellow | 18 → 1 → 18 | 17 | 0 | 1 |
| Land_Mil_Airfield_HQ | 15 → 12 → 15 | 0 | 3 | 1 |
| Land_Mil_Barracks1 | 20 → 0 → 20 | 20 | 0 | 0 |
| Land_Mil_Barracks3 | 9 → 3 → 9 | 9 | 0 | 0 |
| Land_Mil_Barracks5 | 19 → 17 → 19 | 13 | 0 | 2 |
| Land_Mil_Barracks5_Basement | 7 → 6 → 7 | 5 | 0 | 1 |
| Land_Mil_ControlTower | 7 → 6 → 7 | 4 | 0 | 0 |
| Land_Mil_Fortified_Nest_Big | 1 → 0 → 1 | 1 | 0 | 0 |
| Land_Mil_Tent_Big2_4 | 5 → 4 → 5 | 1 | 0 | 2 |
| Land_Mil_Tent_Big2_5 | 8 → 6 → 8 | 6 | 0 | 0 |
| Land_Mil_Tent_Big4 | 4 → 2 → 4 | 4 | 0 | 0 |
| Land_Office1 | 28 → 5 → 28 | 23 | 0 | 5 |
| Land_Office2 | 4 → 1 → 4 | 3 | 0 | 1 |
| Land_Power_Station | 6 → 0 → 6 | 6 | 0 | 0 |
| Land_Radio_building | 8 → 3 → 8 | 6 | 0 | 0 |
| Land_Slum_House3 | 2 → 1 → 2 | 2 | 0 | 0 |
| Land_Slum_House6 | 1 → 0 → 1 | 0 | 1 | 0 |
| Land_Tisy_Barracks | 28 → 24 → 28 | 19 | 0 | 0 |
| Land_Tisy_HQ | 13 → 11 → 13 | 1 | 1 | 0 |
| Land_Tisy_KitchenRoom | 6 → 0 → 6 | 6 | 0 | 0 |
| Land_Tisy_RadarB_Base | 32 → 31 → 32 | 15 | 0 | 1 |
| Land_Village_PoliceStation | 31 → 16 → 31 | 23 | 0 | 4 |
| Land_Village_PoliceStation_Enoch | 31 → 16 → 31 | 23 | 0 | 4 |

### Every per-type count in both files

S/F means `additions-interiors.json` surface points / `additions.json` floor points. Zero means the type has no HC points in that file. This table covers the union of all types in both compared commits and the correction.

| Type | 335915c6 S/F | fa0c2ac8 S/F | Corrected S/F |
| --- | ---: | ---: | ---: |
| Land_Airfield_Radar_Tall | 0/1 | 0/1 | 0/1 |
| Land_Airfield_ServiceHangar_L | 0/12 | 2/12 | 0/12 |
| Land_Airfield_ServiceHangar_R | 0/12 | 1/12 | 0/12 |
| Land_Airfield_Small_Control | 32/7 | 32/7 | 32/7 |
| Land_Airfield_Small_Hangar | 3/0 | 4/0 | 3/0 |
| Land_Barn_Brick1 | 9/10 | 9/10 | 9/10 |
| Land_Barn_Brick2 | 0/3 | 0/3 | 0/3 |
| Land_Barn_Metal_Big | 0/12 | 0/12 | 0/12 |
| Land_Barn_Wood1 | 0/12 | 0/12 | 0/12 |
| Land_Barn_Wood2 | 0/12 | 0/12 | 0/12 |
| Land_Boathouse | 0/0 | 0/5 | 0/5 |
| Land_Bunker1_Double | 0/0 | 3/0 | 0/0 |
| Land_Bunker1_Right | 0/0 | 1/0 | 0/0 |
| Land_Bunker2_Double | 0/0 | 3/0 | 0/0 |
| Land_Bunker2_Right | 0/0 | 1/0 | 0/0 |
| Land_BusStation_building | 1/0 | 1/0 | 1/0 |
| Land_BusStop_City | 0/0 | 0/2 | 0/2 |
| Land_Camp_House_brown | 3/0 | 3/0 | 3/0 |
| Land_Camp_House_white | 2/0 | 2/0 | 2/0 |
| Land_Castle_Bergfrit2 | 0/7 | 0/7 | 0/7 |
| Land_Castle_Gate | 1/0 | 0/4 | 1/4 |
| Land_CementWorks_ExpeditionA | 0/1 | 0/1 | 0/1 |
| Land_CementWorks_ExpeditionC | 0/2 | 0/2 | 0/2 |
| Land_CementWorks_Hall1 | 0/1 | 2/1 | 2/1 |
| Land_CementWorks_Hall2_Brick | 1/0 | 3/0 | 1/0 |
| Land_CementWorks_Hall2_Grey | 0/12 | 0/12 | 0/12 |
| Land_CementWorks_MillB | 0/0 | 0/12 | 0/12 |
| Land_CementWorks_MillC | 0/0 | 0/12 | 0/12 |
| Land_CementWorks_RotFurnace | 0/0 | 0/12 | 0/12 |
| Land_CementWorks_SiloBig1A | 6/2 | 4/2 | 6/2 |
| Land_Chapel | 2/0 | 0/0 | 2/0 |
| Land_Church1_Yellow | 0/7 | 0/7 | 0/7 |
| Land_Church2_2 | 0/0 | 0/12 | 0/12 |
| Land_Church3 | 0/12 | 0/12 | 0/12 |
| Land_Church4 | 5/0 | 3/0 | 5/0 |
| Land_Church4_Dam | 5/0 | 3/0 | 5/0 |
| Land_Church4_Lightblue | 5/0 | 3/0 | 5/0 |
| Land_Church4_Red | 5/0 | 3/0 | 5/0 |
| Land_Church4_White | 5/0 | 3/0 | 5/0 |
| Land_Church4_Yellow_Dam | 4/0 | 3/0 | 4/0 |
| Land_City_FireStation | 6/10 | 14/10 | 6/10 |
| Land_City_Hospital | 20/2 | 20/2 | 20/2 |
| Land_City_PoliceStation | 32/11 | 30/11 | 32/11 |
| Land_City_PoliceStation_Enoch | 32/0 | 30/0 | 32/0 |
| Land_City_School | 32/2 | 32/2 | 32/2 |
| Land_City_Stand_FastFood | 2/0 | 2/0 | 2/0 |
| Land_City_Stand_Grocery | 3/0 | 2/0 | 3/0 |
| Land_City_Stand_News1 | 2/0 | 2/0 | 2/0 |
| Land_City_Stand_News2 | 0/0 | 0/1 | 0/1 |
| Land_City_Store | 28/12 | 28/12 | 28/12 |
| Land_City_Store_WithStairs | 0/1 | 1/1 | 1/1 |
| Land_CoalPlant_Main | 4/1 | 3/1 | 4/1 |
| Land_Construction_Building | 17/0 | 0/12 | 17/12 |
| Land_Construction_Crane | 0/0 | 0/2 | 0/2 |
| Land_Construction_House2 | 2/0 | 0/12 | 2/12 |
| Land_Container_1Aoh | 0/0 | 0/1 | 0/1 |
| Land_Factory_Lathes | 11/3 | 10/3 | 11/3 |
| Land_Factory_Small | 0/1 | 0/1 | 0/1 |
| Land_Farm_CowshedA | 1/4 | 0/4 | 1/4 |
| Land_Farm_CowshedB | 9/0 | 0/10 | 9/10 |
| Land_Farm_CowshedC | 3/0 | 0/2 | 3/2 |
| Land_FuelStation_Build | 4/0 | 0/2 | 4/2 |
| Land_FuelStation_Build_Enoch | 4/0 | 1/0 | 4/0 |
| Land_Garage_Big | 0/12 | 0/12 | 0/12 |
| Land_Garage_Office | 10/4 | 2/4 | 10/4 |
| Land_Garage_Row_Big | 8/0 | 2/0 | 8/0 |
| Land_Garage_Row_Small | 2/1 | 6/1 | 2/1 |
| Land_Garage_Small | 0/1 | 2/1 | 0/1 |
| Land_Guardhouse | 0/2 | 1/2 | 0/2 |
| Land_Hotel | 25/0 | 25/0 | 25/0 |
| Land_Hotel_Damaged | 2/0 | 2/0 | 2/0 |
| Land_HouseBlock_1F1 | 7/1 | 8/1 | 7/1 |
| Land_HouseBlock_1F2 | 3/4 | 5/4 | 3/4 |
| Land_HouseBlock_1F3 | 2/0 | 0/2 | 2/2 |
| Land_HouseBlock_1F4 | 0/4 | 0/4 | 0/4 |
| Land_HouseBlock_1F_Corner | 12/0 | 6/0 | 12/0 |
| Land_HouseBlock_2F1 | 4/0 | 6/0 | 4/0 |
| Land_HouseBlock_2F2 | 9/0 | 9/0 | 9/0 |
| Land_HouseBlock_2F3 | 6/0 | 6/0 | 6/0 |
| Land_HouseBlock_2F4 | 3/7 | 4/7 | 3/7 |
| Land_HouseBlock_2F5 | 2/0 | 2/0 | 2/0 |
| Land_HouseBlock_2F6 | 11/7 | 3/7 | 11/7 |
| Land_HouseBlock_2F7 | 1/0 | 1/0 | 1/0 |
| Land_HouseBlock_2F8 | 2/0 | 2/0 | 2/0 |
| Land_HouseBlock_2F9 | 2/3 | 2/3 | 2/3 |
| Land_HouseBlock_2F_Corner | 0/5 | 0/5 | 0/5 |
| Land_HouseBlock_3F1 | 0/1 | 2/1 | 0/1 |
| Land_HouseBlock_3F2 | 12/5 | 13/5 | 12/5 |
| Land_HouseBlock_3F_Corner1 | 30/12 | 19/12 | 30/12 |
| Land_HouseBlock_3F_Corner2 | 16/10 | 9/10 | 16/10 |
| Land_HouseBlock_5F | 12/7 | 14/7 | 13/7 |
| Land_House_1B01_Pub | 25/0 | 10/0 | 25/0 |
| Land_House_1W01 | 4/0 | 4/0 | 4/0 |
| Land_House_1W02 | 3/0 | 2/0 | 3/0 |
| Land_House_1W03 | 9/4 | 5/4 | 9/4 |
| Land_House_1W04 | 4/0 | 1/0 | 4/0 |
| Land_House_1W05 | 1/1 | 1/1 | 1/1 |
| Land_House_1W05_Yellow | 6/1 | 7/1 | 6/1 |
| Land_House_1W06 | 1/0 | 1/0 | 1/0 |
| Land_House_1W07 | 11/6 | 8/6 | 11/6 |
| Land_House_1W08 | 0/0 | 0/3 | 0/3 |
| Land_House_1W08_Brown | 1/1 | 1/1 | 1/1 |
| Land_House_1W09 | 1/0 | 1/0 | 1/0 |
| Land_House_1W09_Yellow | 9/0 | 10/0 | 9/0 |
| Land_House_1W10 | 7/0 | 5/0 | 7/0 |
| Land_House_1W10_Brown | 6/0 | 4/0 | 6/0 |
| Land_House_1W11 | 0/2 | 0/2 | 0/2 |
| Land_House_1W12 | 0/4 | 0/4 | 0/4 |
| Land_House_1W12_Brown | 6/0 | 5/0 | 6/0 |
| Land_House_1W13_Dam | 6/0 | 4/0 | 6/0 |
| Land_House_2B01 | 5/0 | 4/0 | 5/0 |
| Land_House_2B02 | 0/0 | 0/11 | 0/11 |
| Land_House_2B03 | 1/0 | 0/12 | 1/12 |
| Land_House_2B04 | 0/9 | 0/9 | 0/9 |
| Land_House_2W01 | 2/0 | 3/0 | 2/0 |
| Land_House_2W02 | 7/8 | 5/8 | 7/8 |
| Land_House_2W03 | 0/5 | 0/5 | 0/5 |
| Land_House_2W03_Brown | 4/1 | 5/1 | 4/1 |
| Land_House_2W04 | 21/3 | 7/3 | 21/3 |
| Land_House_2W04_Yellow | 18/1 | 1/1 | 18/1 |
| Land_Lighthouse | 0/0 | 0/1 | 0/1 |
| Land_Lunapark_Autodrome | 0/0 | 0/12 | 0/12 |
| Land_Lunapark_Carousel_Swan | 0/2 | 0/2 | 0/2 |
| Land_Lunapark_Shooting_Gallery | 0/0 | 0/2 | 0/2 |
| Land_Medical_Tent_Big | 0/4 | 0/4 | 0/4 |
| Land_Medical_Tent_Shower | 0/1 | 0/1 | 0/1 |
| Land_Mil_ATC_Big | 32/4 | 32/4 | 32/4 |
| Land_Mil_AircraftShelter | 0/0 | 0/3 | 0/3 |
| Land_Mil_Airfield_HQ | 15/0 | 12/0 | 15/0 |
| Land_Mil_Barracks1 | 20/0 | 0/10 | 20/10 |
| Land_Mil_Barracks2 | 1/0 | 1/0 | 1/0 |
| Land_Mil_Barracks3 | 9/5 | 3/5 | 9/5 |
| Land_Mil_Barracks4 | 3/0 | 4/0 | 3/0 |
| Land_Mil_Barracks5 | 19/0 | 17/0 | 19/0 |
| Land_Mil_Barracks5_Basement | 7/0 | 6/0 | 7/0 |
| Land_Mil_Barracks6 | 32/0 | 32/0 | 32/0 |
| Land_Mil_Barracks6_Old | 32/0 | 32/0 | 32/0 |
| Land_Mil_Barracks_Round | 1/0 | 1/0 | 1/0 |
| Land_Mil_ControlTower | 7/0 | 6/0 | 7/0 |
| Land_Mil_FireStation | 5/11 | 14/11 | 5/11 |
| Land_Mil_Fortified_Nest_Big | 1/0 | 0/0 | 1/0 |
| Land_Mil_Fortified_Nest_Watchtower | 7/0 | 7/0 | 7/0 |
| Land_Mil_GuardTower | 0/0 | 0/2 | 0/2 |
| Land_Mil_Guardhouse1 | 1/0 | 1/0 | 1/0 |
| Land_Mil_Guardhouse2 | 2/0 | 2/0 | 2/0 |
| Land_Mil_Tent_Big1_1 | 1/0 | 1/0 | 1/0 |
| Land_Mil_Tent_Big1_2 | 0/0 | 1/0 | 1/0 |
| Land_Mil_Tent_Big1_3 | 0/0 | 0/2 | 0/2 |
| Land_Mil_Tent_Big1_4 | 1/0 | 1/0 | 1/0 |
| Land_Mil_Tent_Big1_5 | 2/0 | 2/0 | 2/0 |
| Land_Mil_Tent_Big2_1 | 7/0 | 8/0 | 7/0 |
| Land_Mil_Tent_Big2_2 | 1/0 | 1/0 | 1/0 |
| Land_Mil_Tent_Big2_3 | 3/0 | 4/0 | 3/0 |
| Land_Mil_Tent_Big2_4 | 5/0 | 4/0 | 5/0 |
| Land_Mil_Tent_Big2_5 | 8/0 | 6/0 | 8/0 |
| Land_Mil_Tent_Big3 | 0/1 | 0/1 | 0/1 |
| Land_Mil_Tent_Big4 | 4/0 | 2/0 | 4/0 |
| Land_Mine_Building | 0/5 | 0/5 | 0/5 |
| Land_Misc_DeerStand2 | 0/0 | 0/1 | 0/1 |
| Land_Misc_FeedShack | 0/0 | 0/2 | 0/2 |
| Land_Misc_Greenhouse | 0/1 | 0/1 | 0/1 |
| Land_Misc_Polytunnel | 0/0 | 0/2 | 0/2 |
| Land_Misc_Scaffolding | 0/0 | 0/3 | 0/3 |
| Land_Office1 | 28/6 | 5/6 | 28/6 |
| Land_Office2 | 4/0 | 1/0 | 4/0 |
| Land_Office_Municipal2 | 32/0 | 32/0 | 32/0 |
| Land_Pier_Crane_B | 0/0 | 0/4 | 0/4 |
| Land_Power_Station | 6/8 | 0/8 | 6/8 |
| Land_Prison_Main | 32/0 | 32/0 | 32/0 |
| Land_Prison_Side | 32/10 | 32/10 | 32/10 |
| Land_Quarry_Main | 0/6 | 1/6 | 0/6 |
| Land_Radio_building | 8/1 | 3/1 | 8/1 |
| Land_Rail_Station_Big | 0/0 | 0/8 | 0/8 |
| Land_Rail_Station_Small | 2/0 | 2/0 | 2/0 |
| Land_Rail_Warehouse_Small | 0/2 | 2/2 | 0/2 |
| Land_Repair_Center | 0/4 | 0/4 | 0/4 |
| Land_Ruin_HouseBig1 | 2/0 | 2/0 | 2/0 |
| Land_Ruin_HouseBig1_NoIvy | 2/0 | 2/0 | 2/0 |
| Land_Ruin_HouseBig3_Half | 0/0 | 1/0 | 0/0 |
| Land_Ruin_HouseBig3_NoIvy_Half | 0/0 | 1/0 | 0/0 |
| Land_Ruin_HouseSmall2 | 0/0 | 1/0 | 1/0 |
| Land_Ruin_HouseSmall2_NoIvy | 0/0 | 1/0 | 1/0 |
| Land_Sawmill_Building | 2/0 | 3/0 | 2/0 |
| Land_Shed_Closed | 15/0 | 15/0 | 15/0 |
| Land_Shed_Closed2 | 2/0 | 3/0 | 2/0 |
| Land_Shed_W5 | 0/0 | 0/1 | 0/1 |
| Land_Shed_W6 | 0/2 | 0/2 | 0/2 |
| Land_Ship_Big_BackA | 0/3 | 0/3 | 0/3 |
| Land_Ship_Big_BackB | 0/7 | 0/7 | 0/7 |
| Land_Ship_Big_Castle | 0/12 | 0/12 | 0/12 |
| Land_Ship_Big_FrontA | 0/0 | 0/5 | 0/5 |
| Land_Ship_Big_FrontB | 0/6 | 0/6 | 0/6 |
| Land_Slum_House1 | 2/0 | 5/0 | 2/0 |
| Land_Slum_House3 | 2/0 | 1/0 | 2/0 |
| Land_Slum_House6 | 1/0 | 0/0 | 1/0 |
| Land_Smokestack_Big | 0/0 | 0/3 | 0/3 |
| Land_Smokestack_Medium | 0/0 | 0/3 | 0/3 |
| Land_Tenement_Big | 7/0 | 8/0 | 7/0 |
| Land_Tenement_Small | 7/0 | 8/0 | 7/0 |
| Land_Tisy_Barracks | 28/9 | 24/9 | 28/9 |
| Land_Tisy_Garages | 0/1 | 2/1 | 0/1 |
| Land_Tisy_Garages2 | 0/5 | 2/5 | 0/5 |
| Land_Tisy_HQ | 13/5 | 11/5 | 13/5 |
| Land_Tisy_KitchenRoom | 6/0 | 0/12 | 6/12 |
| Land_Tisy_RadarB_Base | 32/0 | 31/0 | 32/0 |
| Land_Tisy_RadarPlatform_Top | 0/12 | 0/12 | 0/12 |
| Land_Tower_TC2_Base | 0/0 | 0/12 | 0/12 |
| Land_Train_Wagon_Box | 0/0 | 0/1 | 0/1 |
| Land_Village_HealthCare | 24/3 | 28/3 | 25/3 |
| Land_Village_HealthCare_Enoch | 16/0 | 19/0 | 16/0 |
| Land_Village_PoliceStation | 31/0 | 16/0 | 31/0 |
| Land_Village_PoliceStation_Enoch | 31/0 | 16/0 | 31/0 |
| Land_Village_Pub | 17/3 | 17/3 | 17/3 |
| Land_Village_Store_Enoch | 11/0 | 11/0 | 11/0 |
| Land_Village_store | 11/0 | 11/0 | 11/0 |
| Land_Workshop1 | 2/0 | 2/0 | 2/0 |
| Land_Workshop3 | 4/0 | 5/0 | 5/0 |
| Land_Workshop4 | 0/0 | 0/3 | 0/3 |
| Land_Workshop5 | 0/0 | 0/3 | 0/3 |
| Land_Workshop_FuelStation | 14/0 | 14/0 | 14/0 |
| Land_Wreck_C130J_Cargo | 0/0 | 0/2 | 0/2 |
| Land_Wreck_Caravan_MGreen | 0/0 | 0/1 | 0/1 |
| Land_Wreck_Caravan_WBrown | 0/0 | 0/1 | 0/1 |
| Land_Wreck_Caravan_WGreen | 0/0 | 0/1 | 0/1 |
| Land_Wreck_Ikarus | 0/0 | 0/2 | 0/2 |
| Land_Wreck_offroad02_aban1 | 0/0 | 0/1 | 0/1 |
| Land_Wreck_offroad02_aban2 | 0/0 | 0/1 | 0/1 |
| Land_Wreck_sed01_aban1_black | 0/0 | 0/1 | 0/1 |
| Land_Wreck_sed01_aban1_white | 0/0 | 0/1 | 0/1 |
| Land_Wreck_sed01_aban1_wine | 0/0 | 0/1 | 0/1 |

### Explicit decisions for fa0c2ac8-only coordinates

Preserving old points also displaces some newer layout coordinates. The check accounts for all 667 candidate coordinates absent from the correction: 426 spacing replacements and 48 cap replacements, plus 192 points without full-client visual footprint support and one without a clear floor approach. Replacement coordinates remain represented by the preserved prior layout. The 193 physical refusals remain excluded. Every coordinate and reason appears in `candidate_not_selected`; no coordinate disappears without a decision. Floors lose zero coordinates against either commit.

The following table covers every type with a falling surface count relative to fa0c2ac8. F = full-client floating/edge refusal; R = no clear floor approach; S = spacing against preserved points; A = area cap. Counts concern all omitted candidate coordinates, including replacements.

| Type | fa0c → corrected surface | F | R | S | A |
| --- | ---: | ---: | ---: | ---: | ---: |
| Land_Airfield_ServiceHangar_L | 2 → 0 | 2 | 0 | 0 | 0 |
| Land_Airfield_ServiceHangar_R | 1 → 0 | 1 | 0 | 0 | 0 |
| Land_Airfield_Small_Hangar | 4 → 3 | 1 | 0 | 2 | 0 |
| Land_Bunker1_Double | 3 → 0 | 3 | 0 | 0 | 0 |
| Land_Bunker1_Right | 1 → 0 | 1 | 0 | 0 | 0 |
| Land_Bunker2_Double | 3 → 0 | 3 | 0 | 0 | 0 |
| Land_Bunker2_Right | 1 → 0 | 1 | 0 | 0 | 0 |
| Land_CementWorks_Hall2_Brick | 3 → 1 | 2 | 0 | 1 | 0 |
| Land_City_FireStation | 14 → 6 | 10 | 0 | 1 | 0 |
| Land_Garage_Row_Small | 6 → 2 | 4 | 0 | 0 | 0 |
| Land_Garage_Small | 2 → 0 | 2 | 0 | 0 | 0 |
| Land_Guardhouse | 1 → 0 | 1 | 0 | 0 | 0 |
| Land_HouseBlock_1F1 | 8 → 7 | 2 | 0 | 3 | 0 |
| Land_HouseBlock_1F2 | 5 → 3 | 2 | 0 | 3 | 0 |
| Land_HouseBlock_2F1 | 6 → 4 | 2 | 0 | 3 | 0 |
| Land_HouseBlock_2F4 | 4 → 3 | 1 | 0 | 2 | 0 |
| Land_HouseBlock_3F1 | 2 → 0 | 2 | 0 | 0 | 0 |
| Land_HouseBlock_3F2 | 13 → 12 | 1 | 0 | 5 | 0 |
| Land_HouseBlock_5F | 14 → 13 | 1 | 0 | 4 | 0 |
| Land_House_1W05_Yellow | 7 → 6 | 1 | 0 | 0 | 0 |
| Land_House_1W09_Yellow | 10 → 9 | 1 | 0 | 2 | 0 |
| Land_House_2W01 | 3 → 2 | 3 | 0 | 0 | 0 |
| Land_House_2W03_Brown | 5 → 4 | 2 | 0 | 0 | 0 |
| Land_Mil_Barracks4 | 4 → 3 | 3 | 0 | 1 | 0 |
| Land_Mil_FireStation | 14 → 5 | 10 | 0 | 1 | 0 |
| Land_Mil_Tent_Big2_1 | 8 → 7 | 4 | 0 | 2 | 0 |
| Land_Mil_Tent_Big2_3 | 4 → 3 | 2 | 0 | 2 | 0 |
| Land_Quarry_Main | 1 → 0 | 1 | 0 | 0 | 0 |
| Land_Rail_Warehouse_Small | 2 → 0 | 2 | 0 | 0 | 0 |
| Land_Ruin_HouseBig3_Half | 1 → 0 | 1 | 0 | 0 | 0 |
| Land_Ruin_HouseBig3_NoIvy_Half | 1 → 0 | 1 | 0 | 0 | 0 |
| Land_Sawmill_Building | 3 → 2 | 1 | 0 | 1 | 0 |
| Land_Shed_Closed2 | 3 → 2 | 1 | 0 | 1 | 0 |
| Land_Slum_House1 | 5 → 2 | 3 | 0 | 0 | 0 |
| Land_Tenement_Big | 8 → 7 | 3 | 0 | 5 | 0 |
| Land_Tenement_Small | 8 → 7 | 1 | 0 | 6 | 0 |
| Land_Tisy_Garages | 2 → 0 | 2 | 0 | 0 | 0 |
| Land_Tisy_Garages2 | 2 → 0 | 2 | 0 | 0 | 0 |
| Land_Village_HealthCare | 28 → 25 | 3 | 0 | 11 | 0 |
| Land_Village_HealthCare_Enoch | 19 → 16 | 3 | 0 | 11 | 0 |

### Reproduction and validation

Use the in-repo reader `tools/audit/odol56.py` (`--reader` is a legacy, ignored argument), full-client `DAYZ_CLIENT_ADDONS`, pristine installed `STOCK_PROTO`, and an external scratch directory `HC_WORK`. Do not use a server profile or an old install snapshot as bundle input. The original data is read from the exact committed repo files:

```sh
git show 335915c6:mission/hollow-country/loot-points/additions-interiors.json > "$HC_WORK/prior.json"
git show fa0c2ac8:mission/hollow-country/loot-points/additions-interiors.json > "$HC_WORK/candidate.json"
for index in 0 1 2 3; do
  agent-run --memory 3G -- python3 -B -m tools.package.loot_point_preserve \
    --prior "$HC_WORK/prior.json" --candidate "$HC_WORK/candidate.json" \
    --addons "$DAYZ_CLIENT_ADDONS" --stock-proto "$STOCK_PROTO" \
    --partition "$index" 4 --refresh-models --out "$HC_WORK/preserve-$index.json" &
done
wait
python3 -B -m tools.package.loot_point_preserve \
  --merge "$HC_WORK/preserve-0.json" "$HC_WORK/preserve-1.json" "$HC_WORK/preserve-2.json" "$HC_WORK/preserve-3.json" \
  --prior "$HC_WORK/prior.json" --candidate "$HC_WORK/candidate.json" \
  --out "$HC_WORK/regenerated.json"
python3 -B -m tools.package.loot_point_preserve --check \
  --prior "$HC_WORK/prior.json" --candidate "$HC_WORK/candidate.json" \
  --out mission/hollow-country/loot-points/additions-interiors.json
```

The checked-in historical omission audit is a hash-bound source receipt for fa0c2ac8, not a qualification of server visuals. To reproduce its annotated receipt too, export `sources.point_preservation.historical_candidate_loss_audit` to a local JSON and pass it as `--loss-audit` at merge. Without it, the coordinate/evidence selection is the same and the complete preservation check still runs; historical labels are not regenerated.

Checks: all 1,735 baseline coordinates remain; read-only receipt check reports zero unreported losses; deleting a Chapel coordinate makes that check fail. Merging the complete partitions in forward and reverse order produces byte-identical output. A dedicated-server visual-source control is refused before scanning. Python syntax passes; the 15 existing focused `tests.slow.test_loot_boost` tests pass. No unit tests or Enforce changes were added.

Fresh full-client reach audit: 1,301 surface points, zero refusals. Fresh floor collision audit: 679 checked, zero refusals. Independent combined collision audit: 1,980 checked, zero refusals. All asset work used `agent-run --memory 3G`, at most four concurrent partitions.

Pristine-mission `loot_boost.plan(..., points=loot_boost.shipped_points())` ran provision, rebalance and finish_receivers. Receivers report 265 introduced receiver/floor containers / 2,194 points, zero containers and zero points without capacity. A separate check also finds positive capacity on every HC-added surface/floor container. Reported unplaced demand is 477 (fa0c2ac8 reported 499); this is an offline estimate, not observed CE spawning. The floor-policy note again includes the owner's full-coverage provenance.

No server/client or native compile gate was run. Lead acceptance still requires one server and at most one client: no `Can't compile`, crash/stall or enabled `[HC Ready]` line with `ready=false`; expected interiors readiness shape is `[HC Ready] module=Interiors enabled=true ready=true reason=<actual reason> runtime=PENDING`. This Python/data change adds no new RPT line and readiness alone cannot prove CE behavior. Inspect actual CE spawning, item support, vicinity pickup/search access and restart retention at Chapel, Fortified Nest Big, Slum House6, Office1, 2W04 Yellow, Pub, police stations, Barracks1, Garage Office and HouseBlock 2F6. Native item fit, doorway/stair access, CE capacity/tag matching, persistence and target-load budgets remain unverified. Never claim multiplayer proven.

## Capacity and category layer (wh-loot 2026-11-22, wh-econ 2026-11-22)

Owner report from the live server: military buildings have many empty spots. Diagnosis (offline, from the stock
and generated missions used by the CE fill probe, `docs/tools/CE_FILL_PROBE.md`): the limiter is the per-group
and per-container `lootmax` of the Military, Police and Prison groups in `mapgroupproto.xml`, not `globals.xml`,
the CE item cap or the types totals. A Barracks6 group with 290 points allows 25 items and a Barracks3 group with
82 points allows 10, so most points can never be used. In the stock mission the effective Military slots are
about 21% of the physical points (1,869 of 9,065); after the 2x boost and the HC point additions about 43%
(7,195 of 16,899). Military weapon demand already exceeds its slots ("hard to place" lines), so more
capacity mostly helps the non-weapon Military rows and the shared Military weapon pools.

Owner request (wh-econ, 2026-11-22): every building needs more loot because the point additions raised the
physical points but not the limits. Three knobs in `mission/hollow-country/loot-points/settings.json`, all applied
by `tools/package/loot_boost.py` (`scale_capacity_proto`, `scale_types`, the scoped shelf limit in `plan`):

- `CapacityMultiplier` is a per-usage map `{usage: factor}` (factor 1.0 to 4.0, usage must be a vanilla
  `cfglimitsdefinition.xml` usageflag); the shipped map is in `settings.json` only. A group takes the largest factor among its usages that are in the map. Group `lootmax` becomes
  `min(sum of container limits, max(stock, min(ceil(lootmax x f), cap)))`, where `cap` is the group's
  `GroupLootmaxCap` (80 when the key is absent or lists no usage of the group); a group already above its cap keeps its
  limit.
  Every container with at least one non-firearm, non-explosive category becomes
  `max(current, min(points, ceil(current x f)))` (mixed containers now scale; weapon-only, explosive-only,
  category-less, zero and self-closing containers keep their limit). Non-firearm types rows whose every usage is
  Military, Police or Prison also get `nominal` and `min` x the Military factor, as before. The older single
  `MilitaryCapacityMultiplier` key still reads as `{Military, Police, Prison}: factor`; both keys together are refused.
- `GroupLootmaxCap` is `{Default: n, usage: n}` (integers 1 to 400, usage a vanilla usageflag): the most a scaled
  group limit may grow to. A group takes the largest cap among its usages (a usage without an entry counts as
  `Default`, 80 when `Default` is absent); the sum of the group's container limits still clamps it, so a cap above
  that sum changes nothing. Group `lootmax` and container capacity both bind the placeable slots, so Town, Military,
  Police, Prison, Medic and School carry a higher cap and a factor in `CapacityMultiplier` that lets the group limit
  reach the container capacity; the shipped values are in `settings.json` only. The receipt records the map in
  `knobs.group_cap` and the describe line `group lootmax cap` prints it; a receipt without it (an older install) still
  rolls back, because rollback restores the receipted bytes.
- `CategoryMultiplier` is `{category: target}` (food, tools, medical, containers, clothes, books; 1.0 to 10.0, so a
  target may exceed `Multiplier`; the shipped targets are in `settings.json` only). A row's `nominal` and `min` become at least `ceil(stock x target)`, so a target lifts only rows
  whose boost is lower than the target. Medical is a name
  class of tools rows (bandages, saline, injectors and so on); without a `medical` key it falls back to `tools`.
  Weapons, ammo, explosives and the firearms roster are never targeted.
- The shelf limit is scoped. The first plan finds the `usage/shelves` buckets whose nominal exceeds their point
  slots; the re-plan holds a shelf-routed row at 1x only when all of its usages are in that pressured set (a row
  with a usage that has slack keeps the boost), instead of holding every shelf row on the map. The describe line
  reports `shelf_boost_limited=[...]`.

A target at or below the factor a row already gets is a no-op for that row (`rows=` in the describe line counts the
rows it lifted). Held shelf rows are never raised by a target.

Supply side (owner interview 2026-11-22, targets in `economy-targets` of the wave brief): the same file carries
five more knobs, all read by `loot_boost.default_knobs` and recorded in the receipt as `knobs`.

- `UsageMultiplier` is `{usage: factor}` (1.0 to 8.0). A building-loot row's nominal and min factor is the largest
  entry over its usages; a usage without an entry counts as `Multiplier`, a row without usages keeps `Multiplier`.
  A usage with an entry replaces the legacy Military-adjacent step for rows that use it, and is sized to its owner
  target rather than to today's slots: it is never shelf-held (its remaining pressure stays in the budget report).
- `MilitaryTierMultiplier` is `{TierN: factor}` (0.5 to 4.0). A row with the Military usage gets an extra factor
  equal to the mean over its tier values (a row without tier values counts as 1.0), so Tier3/Tier4 rows outweigh
  Tier1/Tier2 rows. Groups carry no tier in `mapgroupproto.xml`, so this widens what a Tier3/Tier4 zone can draw,
  not the lootmax of a given building; per-building richness there comes from the point and capacity layers.
- `FirearmsMultiplier` is `{weapon, magazine, ammo, attachment: factor}` (1.0 to 4.0) over the quantity the roster
  rows already carry. Factor source: the authored `mission/hollow-country/ce/types.xml` (generated from
  `tools/package/firearms_roster.json`, with `config/military-loot.json` behind the Military pools) holds the 3x
  native travel layer; travel installs it before the boost, so `loot_boost` multiplies those bytes and the committed
  file stays untouched. Weapon-pack rows (optional packs) are not scaled here and stay 2x. The Military tier factor
  applies to roster rows too.
- `LootDamageMax` (0.0 to 1.0) lowers the `LootDamageMax` global to that ceiling and never raises a stock value;
  the receipt records `LootDamageMax=old->new` in `counts.globals`.
- `Refill` is `{RestockMin, RespawnTypesFactor}`. `RestockMin` (seconds, 0 = off) raises the `restock` of every row
  the boost touches that is below it; `RespawnTypesFactor` (0.25 to 4.0, 1.0 = off) multiplies the boosted
  `RespawnTypes` global. Both default to today's behaviour and the describe line `refill:` shows them; the lead tunes
  them after measuring.

The receipt records every changed globals variable as `old->new`; `loot_boost.globals_from_report` rebuilds the
installed bytes from it, which `friend_install.globals_installed_bytes` uses so upgrades recognise them.

Attachment coverage: every attachment the CE puts on a spawnable firearm (the `<attachments>` items and presets of
the loaded spawnabletypes files, or an injected `fits` table such as one read from the addon configs on a host)
must have a types row with nominal of at least 1 and a usage shared with a gun it fits. `plan` reports
`counts.attachments` (guns, attachments, ok, gaps by kind, repaired, rows still needed) and repairs `nominal` and
`usage` gaps in place; a gap with no row at all is listed as needing an authored row and never invented. Attachments
that fit a gun by inventory slot but are not on the CE spawn list need a host-side fit table, which cannot be
committed (game configs), so that wider check is `attachment_coverage(rows, fits)` with a measured table.

Rule (owner, 2026-11-22): `settings.json` is the single source of these numbers. `loot_boost` applies every knob
from the mission's own stock bytes on each install, after rolling back the previous receipt; no install-time
default and no second copy of the numbers exist in the installer, packer or docs. The receipt records the
effective `capacity_multiplier`, `category_multiplier` and `knobs`, and the overlay fingerprint covers `settings.json`
(it ships in the bundle's mission overlay), so an edited settings file is detected and reapplied from stock and
factors never compound. Rollback still reads receipts that carry the older `military_multiplier`.

Projection (offline, stock mission plus the travel layer; optional packs not staged; slots are the shipped points
(wh-points rounds merged) after the capacity map and group caps, `placement_budget` of the plan): total nominal about 89,500 (about 95,000 with the packs); food and medical about
3,500 each; roster weapons about 5,750 (about 6,250 with the pack weapons). The describe lines print the same
numbers for any install: `usage targets`, `military tiers`, `firearms`, `refill`, `attachment coverage`, and
`CE nominal=` for the total. Visible items are `min(nominal, slots)` per usage and tag, an offline estimate only.
Hunting is bounded by its points (about 5,000 in total), not by the capacity map, so its slots stay below the owner
target until more Hunting points exist; trimming its factor lowers nominal only where a row is not shared with another
usage (a row's factor is the largest over its usages).

Stock-mission rehearsal (offline, `plan(..., points=shipped_points())`, old single-factor layer against this one):
groups changed 114 to 165, containers 19 to 237; prototype `lootmax` 1,461 to 1,966 before and 1,880 to 2,742
now; weighted by placed buildings 5,054 to 7,230 before and 16,695 to 25,381 now (the map has more usages;
the two are not like for like); nominal by category
(stock to boosted): food 831 to 1,552 (was 831, held), containers 767 to 1,624 (was 1,196), medical 611 to
1,221, tools 5,871 to 11,598 (was 6,482 with medical inside), clothes 7,954 to 16,655 and weapons 3,677 to
3,677 unchanged; total 21,090 to 37,706 (was 31,400). `ce_slot_pressure --feasibility` on an installed copy:
demand 30,479 to 36,545, deficit 863 to 823, weapons unassigned 50 to 29 (Town shelves). Farm remains pressured
after its 1.25 factor, so Farm-only shelf rows stay at 1x. These are offline estimates and prove nothing about
CE spawning; the evidence after a boot is the census totals and the install line `capacity map {...}`.

## Round 8 point density and supported floors for the owner's usage targets (wh-points 2026-11-22)

Owner targets from the 11-22 interview (CE slots per usage): Town 21k or more, Farm about 12k, Military 10k or more,
Police 4.4k, Prison 450, Hunting 6.5k, Medic 3.2k, Firefighter 500, School about 1.1k. Slots here means
`min(group lootmax, sum over containers of min(container lootmax, points))`, measured offline on the staged final
`mapgroupproto.xml` and `mapgrouppos.xml` (full plan: scaled stock, per-usage CapacityMultiplier, HC overlays, new
buildings and the map layer), weighted by placed buildings. These are projections only; census totals and the
`[HC Use]` counters after a native boot are the evidence, and native acceptance stays pending.

What bound the slots: in every target usage the group `lootmax` was already below the sum of container capacity
(`grpLost` below), and the HC containers were sized by the older "one item per 15 m2, at most one per three points"
rule. Round 8 changes two things inside the existing generators, and nothing else:

1. **Point-density lootmax.** `interior_points_gen.density_lootmax(count, area, density)` sets the HC container
   `lootmax` to `max(old size-realistic value, ceil(points * density))`, at most `MAX_ADDED_LOOTMAX` (12) and never more
   than the number of points, so no point is asked to hold more than one item. Density is 0.75 for shelf containers
   and 0.5 for floor containers (floors stay the sparser option, per the floor policy). `--resize OVERLAY...` applies the
   rule to the shipped files; it is deterministic and idempotent and leaves points, evidence and categories alone, so
   the audits see the same coordinates. The three `added_lootmax` call sites of the generator use it, so a regeneration
   keeps the numbers. 71 floor groups and 120 shelf groups changed capacity; no point moved.
2. **Floor containers for groups that only had shelves.** `--floors --only LIST --surface-overlay ...` runs the floor
   pass for the named groups even though they already carry surface points. The surface overlay's family label is reused
   so both files agree on family and stock pin, groups with a floor container are skipped, and with
   `--merge-partitions --base additions.json` the audited new groups are added without touching existing ones. 43
   lootable groups (819 placed buildings) in the target usages had shelf points and no floor point; 39 took 260 floor
   points (clothes and paper per the floor policy, same lattice, spacing and collision support gate as before).
   Four were refused with reasons: `Land_Chapel` no spare floor cell, `Land_City_Stand_News1`, `Land_Mil_Tent_Big1_1` and
   `Land_Mil_Tent_Big1_4` no supported floor point.

Counts: `additions.json` 136 to 175 groups, 679 to 939 floor points; `additions-interiors.json` 142 groups and 1,301
surface points, unchanged. Total 2,240 points, under the 16,000 merged cap, and every floor container is within the
12-point limit.

### Slots per usage, before to after (offline projection)

| Usage | HC points | HC container capacity | slots before | slots after | container capacity after | target |
|---|---|---|---|---|---|---|
| Town | 8,643 to 10,896 | 3,359 to 6,200 | 15,062 | 18,056 | 21,294 | 21,000 |
| Farm | 4,623 to 4,637 | 2,900 to 3,115 | 8,217 | 8,658 | 8,898 | 12,000 |
| Military | 8,709 to 9,398 | 6,981 to 7,693 | 7,258 | 8,095 | 10,828 | 10,000 |
| Police | 1,801 to 2,101 | 1,346 to 1,562 | 2,128 | 2,272 | 3,665 | 4,400 |
| Prison | 134 to 146 | 115 to 125 | 160 | 160 | 324 | 450 |
| Hunting | 2,542 to 2,691 | 2,401 to 2,561 | 3,577 | 3,764 | 3,947 | 6,500 |
| Medic | 902 to 908 | 429 to 530 | 2,388 | 2,390 | 3,238 | 3,200 |
| Firefighter | 109 to 109 | 38 to 65 | 271 | 298 | 437 | 500 |
| School | 301 to 315 | 170 to 236 | 726 | 788 | 1,132 | 1,100 |

### What points cannot do, for wh-econ2

The group limit now binds, not the points: container capacity after Round 8 meets or passes the target in Town
(21.3k), Military (10.8k), Medic (3.2k) and School (1.1k), but the group `lootmax` holds slots at 18.1k, 8.1k, 2.4k and
0.8k. Raising the group limits (`MAX_GROUP_LOOTMAX` 40, `GROUP_CAPACITY_CAP` 80, the Multiplier and the per-usage
CapacityMultiplier, all in `loot_boost.py` and `settings.json`) is what closes that gap; the numbers above are the
ceiling they can reach. Group limit capacity left unused today, in slots: Town 3.2k, Military 2.7k, Police 1.4k, Medic
0.8k, School 0.3k, Prison 0.2k, Hunting 0.2k, Farm 0.2k, Firefighter 0.1k.
Farm (8.9k), Hunting (3.9k), Police (3.7k), Prison (0.3k) and Firefighter (0.4k) also lack container capacity: Hunting is
mostly tiny structures (deer stands, shacks) with a handful of points each, Police stations and Prison are already at the
80 group cap, and Farm needs the stock container limits (the Farm CapacityMultiplier) rather than more HC points. No
further unsupported or unreachable point was added to chase those numbers.

### Audits and validation

Commands (scratch directory outside the repo; client addons and the pristine stock proto):

```sh
agent-run --memory 2G -- python3 -B -m tools.package.interior_points_gen --addons "$A" --stock-proto "$S/mapgroupproto.xml" \
  --resize mission/hollow-country/loot-points/additions.json mission/hollow-country/loot-points/additions-interiors.json
for index in 0 1 2; do
  agent-run --memory 2G -- python3 -B -m tools.package.interior_points_gen --floors --addons "$A" --stock-proto "$S/mapgroupproto.xml" \
    --base mission/hollow-country/loot-points/additions.json --surface-overlay mission/hollow-country/loot-points/additions-interiors.json \
    --only "$HC_WORK/floor-groups.txt" --partition "$index" 3 --out "$HC_WORK/floor-$index.json"
done
agent-run --memory 2G -- python3 -B -m tools.package.interior_points_gen --floors --addons "$A" --stock-proto "$S/mapgroupproto.xml" \
  --base mission/hollow-country/loot-points/additions.json --only "$HC_WORK/floor-groups.txt" \
  --merge-partitions "$HC_WORK"/floor-?.json --out "$HC_WORK/merged.json"   # then replace additions.json
agent-run --memory 2G -- python3 -B -m tools.package.loot_reach_audit --addons "$A" --stock-proto "$S/mapgroupproto.xml"
agent-run --memory 2G -- python3 -B -m tools.package.loot_support_audit --addons "$A" --stock-proto "$S/mapgroupproto.xml"
```

The group list is the lootable groups of the target usages that have placed buildings, shelf points and no floor
container. Each new floor point was admitted only after the per-point collision support gate inside the partition
pass (refusal counts are kept under `sources.hc_floor_round8`), then both shipped audits were re-run on the final data.

Results on the final data: `loot_reach_audit` checked 1,301 shelf points and refused 0 (floor points are outside its
scope); `loot_support_audit` checked all 2,240 points (1,301 surface and 939 floor) and refused 0, with no failure
counts; `loot_point_preserve --check` reports `unreported_losses: 0`; the merged overlay parses (224 groups, 2,240
points) with every container inside the point and lootmax limits. Per-usage HC point counts, placed-building weighted,
before to after: Town 8,643 to 10,896, Farm 4,623 to 4,637, Military 8,709 to 9,398, Police 1,801 to 2,101, Prison 134 to
146, Hunting 2,542 to 2,691, Medic 902 to 908, Firefighter 109 to 109, School 301 to 315. The generated digests and
receipts that pin the overlay hashes are refreshed by the lead after merge.

## Round 9 dense floors for Medic, Hunting and Prison (wh-points 2026-11-22)

The brief asked for more supported points in Hunting, Medic and Prison groups so the projected slots reach Hunting
6.4k, Medic 3.1k and Prison 450 after the econ `GroupLootmaxCap` and `CapacityMultiplier` settings landed. The generator
gained three options (all additive, deterministic): `--only FILE` limits a scan to the named groups, `--replace` lets a
floor pass swap an existing group, and `--cells-per-point M2` sets a denser floor lattice than the default
(`loot_boost.CELLS_PER_POINT`) while the 1.5 m spacing, the per-point collision support gate and the 12-point container
cap stay. Surface regeneration over the same groups reproduced the shipped counts, so no surface points were added.
`--resize` must run last after any floor pass: the support-audit filter inside the pass recomputes the size-realistic
lootmax and would otherwise leave the round 8 floor groups with the smaller value.

Twenty groups were regenerated with the denser floor (hunting stands and cabins, the two Barracks/Castle structures,
Lunapark shooting gallery, Medical_Tent_Shower and Medical_Tent_Big, Village_HealthCare, City_Hospital, the two Prison
groups, Village_store); the overlay now holds 970 floor points in 175 groups (was 939) and 1,301 surface points in 142
groups. Gains came where floor space is supported: City_Hospital 2 to 12 floor points, Village_HealthCare 3 to 12,
Medical_Tent_Big 4 to 7, Medical_Tent_Shower 1 to 2, Castle_Bergfrit2 +5, Village_store +1.

### Projected slots

Slots are the sum over groups of `min(group lootmax, sum of min(container lootmax, points))`, read with the econ
placement budget. Two models are reported because they differ for Medic:

| usage | target | econ pre-map mission (before to after) | staged final map (before to after) |
| --- | --- | --- | --- |
| Hunting | 6,400 | 4,323 to 4,344 | 4,161 to 4,182 |
| Medic | 3,100 | 2,460 to 2,705 | 4,322 to 4,749 |
| Prison | 450 | 360 to 362 | 358 to 360 |
| Town | | 22,530 (unchanged) | 22,020 to 22,463 |
| Military | | 9,890 (unchanged) | 13,903 to 13,987 |
| Police | | 4,201 (unchanged) | 4,345 to 4,397 |
| Farm, School, Firefighter | | 12,014, 1,132, 518 (unchanged) | 12,243, 1,132, 518 (unchanged) |

The econ mission has only 9 `Land_Medical_Tent_Big` instances; the staged final map adds the map layer (65 tents), which
is why Medic differs by about 1,900 slots. Medic reaches its target on the final map.

### What points cannot raise

Hunting and Prison are bound by container lootmax, not by points. In the final map Hunting carries 4,989 points against a
container capacity of 4,189, and Prison 481 points against 358. In the Prison groups the HC containers already sit at the
hard limits (`MAX_FLOOR_POINTS` 12 and `MAX_SURFACE_POINTS` 32), and every group's slots equal its group lootmax
(Hospital 134, HealthCare 90, Tent_Big 35, Prison_Main 132, Prison_Side 228), so more points in those groups add nothing.
Hunting-only structures (deer stands, feed shack, trail roofs, camp houses) are small and have no spare supported floor
cells. Reaching 6.4k Hunting and 450 Prison therefore needs the stock-container lootmax or capacity levers in
`loot_boost.py` and `settings.json`, which are econ scope and untouched here.

### Audits and validation

`loot_support_audit` checked all 2,271 points (1,301 surface, 970 floor) and refused 0, with no failure counts;
`loot_reach_audit` checked the 1,301 shelf points and refused 0; `loot_point_preserve --check` reports
`unreported_losses: 0` (1,292 prior points); the unit tests of `tests.unit.test_interior_points_density` (5) and the hygiene check pass.
