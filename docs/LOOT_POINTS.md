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
