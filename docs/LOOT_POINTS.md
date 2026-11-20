# Interior loot points

Current round-6 generator output: **917 above-floor points / 121 building
classes**, using the corrected stock CE frame and unchanged reach checks. The
shipped merge contains **2,139 HC points / 175 groups**. The requested 3,000
above-floor points remains unmet; native acceptance remains pending. See the
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
surfaces. These remain deferred, as do per-point categories and point-specific
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

The read-only decoder is an external, hash-pinned dependency from
[DayZObjectBuilder](https://github.com/SXDIST/DayZObjectBuilder/tree/e272780131dc10fe798bad321dca2c96894e993e/DZObjectBuilder/io).
Only its three pure-Python reader files are needed; no Blender installation or
asset conversion is used. The generator checks each source SHA-256 before import.
The third-party decoder is not vendored into this repository. Reproduce from the
same installed vanilla build, unmodified stock prototype and stock map positions:

```sh
HC_INTERIOR_WORK=$(mktemp -d /tmp/hc-interior2.XXXXXX)
python3 -B - "$HC_INTERIOR_WORK" <<'PY'
from pathlib import Path
import sys
from urllib.request import urlopen
from tools.package.interior_points_gen import READER_REVISION, READER_HASHES
folder = Path(sys.argv[1])
base = 'https://raw.githubusercontent.com/SXDIST/DayZObjectBuilder/'
for name in sorted(READER_HASHES):
    url = base + READER_REVISION + '/DZObjectBuilder/io/' + name
    with urlopen(url, timeout=30) as response:
        (folder / name).write_bytes(response.read())
PY
python3 -B -m tools.package.interior_points_gen \
  --addons "$DAYZ_ADDONS" --stock-proto "$STOCK_PROTO" \
  --map-pos "$STOCK_MAP_POS" --reader "$HC_INTERIOR_WORK"
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
not coordinate overlays. The tool uses the generator's external, SHA-256-pinned
ODOL reader, installed vanilla building/furniture PBO members, the unmodified
stock prototype, `interior_catalog.py`, `interior_templates.py`, measured
`interior_prop_boxes.json`, and the authored interior templates. Assets and
unpacked model/memory data remain external and are never written by this tool.
The reader acquisition recipe is in the round-5 section above.

```sh
python3 -B -m tools.package.loot_reach_audit \
  --addons "$DAYZ_ADDONS" --stock-proto "$STOCK_PROTO" \
  --reader "$HC_INTERIOR_WORK" --report "$HC_INTERIOR_WORK/reach.json"
# Review the refusal report, then remove points with insufficient static evidence:
python3 -B -m tools.package.loot_reach_audit \
  --addons "$DAYZ_ADDONS" --stock-proto "$STOCK_PROTO" \
  --reader "$HC_INTERIOR_WORK" --report "$HC_INTERIOR_WORK/reach-before.json" --fix
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
proxies, collision components not decoded by the external reader, complete item
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
the external reader and local reports are moved outside the worktree before
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
external reader and diagnostic reports remain outside the worktree. The supplied
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
