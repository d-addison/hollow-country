# Civilian interior loot points

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
