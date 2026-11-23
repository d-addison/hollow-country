# Interior templates contract (T1–T6)

Status: an interface contract for parallel work, not runtime evidence. Every component stays
`pending` until the DayZDiag, normal-PBO and one-client checks in docs/LOCAL_ACCEPTANCE_V1.md
pass.

Owner decisions (2026-11-17): search on CE points in every class; furniture only where a
template passes clearance (≤1,500 props); sampler data is provisional room evidence; classes that
can't be measured stay vanilla with an exclusion reason.

This replaced the single-house pilot gates (`HCInteriorCatalog.BUILDING`,
`HCInteriorMeasuredCatalog`) with class-level templates in the model frame. Templates bind
lazily to each instance through `Object.ModelToWorld`/`WorldToModel` (native
`3_Game/Entities/Object.c#Object.ModelToWorld`, `#Object.WorldToModel`). The legacy `interiors.json` pilot is retired (owner,
2026-11-22): the server ignores an existing `interiors.json` and prints exactly one
`[HC Interiors] legacy pilot retired: interiors.json ignored` line; the file is neither
required nor deleted. The pack lives in its own directory.

## 1. Files under `$profile:HollowCountry/`

| Path | Built by | Read by | Cap |
| --- | --- | --- | --- |
| `templates/index.json` | T6 | T3, T4, T5 | 1 file |
| `templates/classes-NNN.json` | T2 (from the T1 config census) | T3, T4 | ≤16 chunks × ≤160 rows |
| `templates/t-NNNN.json`, one per covered class | T2 | T3, T4, T5 | ≤512 files |
| `templates/furnish-NNN.json` | T2 | T3 | ≤16 chunks × ≤128 rows |
| `templates/search-groups-NNN.json` | T5 tool | T5 | ≤64 chunks |
| `templates/state/*` (runtime journals) | T3, T5 | T3, T5 | — |

`NNN` and `NNNN` are zero-padded decimals, contiguous from 0. No other names are read. T6
assembles, pins and installs the tree.

**Size and read rule.** Every file is ASCII JSON of at most **32,767 bytes**. That is the
existing limit for measured files (`HCInteriorMeasuredCatalog.c#HCInteriorMeasuredCatalog.MeasuredResolve`, `interiors_profile.py`).
Read with the bounded pattern at `HCInteriorMeasuredCatalog.c#HCInteriorMeasuredCatalog.MeasuredRequested..MeasuredRead`:
`OpenFile` → `ReadFile(handle, text, cap + 1)` → refuse unless `count == text.Length()` and
1 ≤ length ≤ cap → strict key pass (unknown/duplicate/missing keys refuse, as `MeasuredStrict`) →
`JsonFileLoader<T>.LoadData` (native `JsonFileLoader`). Never `LoadFile`.

The whole pack is ≤610 files and ≤20 MiB. It is read once in `OnStart` and never on ticks.
`ReadFile` byte semantics are not yet observed natively, so the first DayZDiag run logs count and
length for one file of each kind.

**Text rules.** Ids, classes and items pass `HCSearchRules.TextValid` (≤128 chars); hashes pass
`HCSearchRules.PinValid`; vectors are finite `[x, y, z]` arrays passing `HCInteriorRules.SaneVector`
(model frame within ±512). DTOs are flat, no inherited JSON members (`HCInfectedRooms.c#HCInfectedRoomDocument`).

## 2. Frames, instances and pins

**Model frame.** All template coordinates are building model-local metres (the frame of
`ModelToWorld` and the sampler's `CoordToLocal`). Convert `mapgroupproto.xml` points only with
`tools/audit/interior_points.py stock_to_sampler(point, frame)`. `frame` comes from
`frame_verdict(census)` on a native census. The observed verdict so far is `rot90`
(stock = (z, y, −x)). A class with no verdict is excluded as `frame_unverified`.

**Instances.** Furnish rows copy `mapgrouppos.xml` `pos`/`a`. At runtime, exactly one live object
of the class must lie within 0.75 m (the template placement resolver in
`HCInteriorTemplatePlacement.c`). Orientation comes from the live object and must be yaw-only. Nonzero
pitch or roll refuses with `tilted`.

**Pins (in `index.json`).** `Sources` maps names to SHA-256: `mapgroupproto`, `mapgrouppos`,
`types`, `cfgspawnabletypes`, `cfglimitsdefinition`, `census-<run_id>` per T1 run, `generator`
(T2), `search-generator` (T5); every chunk is listed with its SHA-256. `SourcePin` = SHA-256 of
canonical `Sources` JSON and becomes the search `SourcePin`/`EvidencePin`. Script checks syntax
and binding only, never recomputes SHA-256; the trust boundary is the operator install receipt.

## 3. `index.json`

```json
{"SchemaVersion": 2, "Kind": "hc-interior-templates", "WorldName": "chernarusplus",
 "Build": "1.30.164289", "PackId": "<32 hex>", "SourcePin": "<sha256>", "Frame": "rot90",
 "Provisional": true, "Sources": {"mapgroupproto": "<sha256>", "...": "..."},
 "ClassFiles": [{"File": "classes-000.json", "Sha256": "<sha256>"}],
 "TemplateFiles": [{"File": "t-0000.json", "BuildingClass": "Land_House_1W01", "Sha256": "<sha256>"}],
 "FurnishFiles": [{"File": "furnish-000.json", "Sha256": "<sha256>"}],
 "GroupFiles": [{"File": "search-groups-000.json", "Sha256": "<sha256>"}]}
```

`Build` must pass `HCBuildIdentity.Matches`. `Provisional` must be `true`; script refuses `false`
until runtime acceptance exists.

## 4. `classes-NNN.json`: the full House denominator

```json
{"SchemaVersion": 2, "Chunk": 0, "Rows": [
 {"BuildingClass": "Land_House_1W01", "Rooms": "covered", "Furniture": "covered", "Search": "covered"},
 {"BuildingClass": "Land_Wreck_Volha", "Rooms": "not_enterable", "Furniture": "not_enterable", "Search": "no_ce_points"}]}
```

Rows across all chunks equal every loaded `CfgVehicles` subclass of `House`, each once, ≤2,048
(existing check, `HCInfectedRooms.c#HCInfectedRoomCatalog.ProductionHash..ProductionClassIndex`). Each field is `covered` or a reason: existing
`unmeasured`, `not_enterable`, `path_pending`, `door_pending`, `unsupported_geometry`; new
`frame_unverified`, `clearance_failed`, `no_ce_points`, `not_in_mapgrouppos`, `over_budget` (T4
adds them to `ProductionDisposition`). A class with any `covered` field has exactly one
`TemplateFiles` row; others have none and stay vanilla.

## 5. `t-NNNN.json`: class template

```json
{"SchemaVersion": 2, "BuildingClass": "Land_House_1W01", "TemplateId": "land_house_1w01-v1",
 "Box": {"Min": [-6,-3,-5], "Max": [6,4,5]},
 "Evidence": [{"Kind": "native-room-survey-v1", "RunId": "<32 hex>", "Sha256": "<census sha256>"}],
 "Rooms": [{"Id": 1, "Label": "room", "Min": [-5,-2.6,-4], "Max": [-0.5,0.2,0.5],
            "Anchor": [-2.7,-2.5,-1.8], "FloorY": -2.55, "Cells": 21}],
 "KeepOuts": [{"Kind": "door", "Index": 0, "Min": [-0.6,-2.6,3.5], "Max": [0.9,-0.4,5.1]},
              {"Kind": "stair", "Index": 0, "Min": [3,-2.6,-1], "Max": [4.2,1.5,2]},
              {"Kind": "ce-point", "Index": 7, "Min": [1,-2.6,1], "Max": [1.8,-1.6,1.8]}],
 "PropSlots": [{"Id": 1, "Room": 1, "Type": "StaticObj_Furniture_case_a",
                "Position": [-4.2,-2.55,-3.1], "Orientation": [90,0,0],
                "Bounds": {"Min": [-4.6,-2.55,-3.5], "Max": [-3.8,-0.6,-2.7]}, "History": ["family"]}],
 "SearchSites": [{"Id": 1, "Room": 1, "Center": [1.4,-1.8,1.4], "Radius": 0.8,
                  "Source": "lootshelves", "Points": [12,13], "Groups": ["g-0042"]}]}
```

**Rooms** (1–16): `Anchor` ⊂ room box ⊂ `Box` ⊂ ±512; anchors ≥1 m apart (existing
`ValidateProductionHouse` rules). A room is a cluster of sampler floor cells reachable on the
navmesh with doors open (reach 1) with ≥1.9 m clearance, split by floor band (`BAND_TOLERANCE`
0.25) and at door keep-outs. `Label` is `room` unless reviewed; never guessed from names.

**KeepOuts** (≤32): `door` = `GetDoorSoundPos` model point grown by a 1.2 m swing, clipped to
`Box`; `stair` = cell columns rising >0.35 m per 1 m cell; `ce-point` = each CE point's `range`
horizontally and `height` vertically.

**PropSlots** (≤ `MaxPropsPerInterior`, default 5): `Type` is a `HCInteriorCatalog.SearchType`
case or a decoration type from `tools/package/interior_catalog.py PILOT` and passes
`ConfigIsExisting`. `Bounds` (T2's conservative per-type boxes, pinned via `generator`) lie inside
the slot's room, intersect no keep-out, and leave ≥0.6 m of floor to any door keep-out and ≥0.3 m to any stair keep-out, so doors
and stair landings are never blocked (runtime `HCInteriorTemplatePlacement.StairLandingClear` repeats the stair rule). `History` ⊆ {`family`, `ransacked`}. No passing slot → `Furniture: clearance_failed`.

**SearchSites** (1–24): `Radius` 0.25–**8.0** m; `Source` ∈ `lootshelves`, `loot`, `lootFloor`,
`lootweapons`; `Points` are stock point indices (document order within that container); `Center`
is their converted centroid and every point plus its `range` lies in the sphere; `Groups` lists
1–8 group ids. Sites may overlap `ce-point` keep-outs.

## 6. Search context (T5)

```json
{"SchemaVersion": 2, "Chunk": 0, "Groups": [{"Id": "g-0042", "Usages": ["Village"],
  "Container": "lootshelves", "Categories": ["tools"], "Tags": ["shelves"], "Items": ["Hammer", "Pliers", "Rag"]}]}
```

**Groups.**
- There is one group per distinct (class usage set, container name, categories, tags) in `mapgroupproto`.
- `Items` are 1–256 sorted, unique `types.xml` classes with `nominal > 0` whose `usage`
  intersects `Usages` (or is absent), `category` is in `Categories`, and `tag` intersects `Tags`
  (or is absent). Value tiers are positional and are not filtered offline.
- A group with more than 256 items is refused. A class left with no sites becomes `Search: over_budget`.
- `Items` is a filter, never a source. Search transfers only CE items that already exist in the
  sphere (`HCSearchSupplyProvider.c#HCSearchSupplyProvider.Collect`, `HCSearchNativeSupply.c#HCSearchSupplyRegistry`). Nothing is created,
  refilled or duplicated, and the only move is a server-side `TakeToDst`.

**Runtime context.** Each bound site builds one existing `HCInteriorSearchContext`:

| Field | Value |
| --- | --- |
| `InstanceId` | House key: class plus quantized live transform, as in `HCInteriorCandidate.Key()` |
| `LayoutId`, `History`, `Room` | `TemplateId`, `""`, `room-<Room>` |
| `GroupId` | The `Groups` ids joined with `+` |
| `SourcePin`, `EvidencePin` | `index.SourcePin` |
| `MeasuredRecordSha256` | The template's `Sha256` in the index |
| `Items` | Union of the group items |

The site id is `<InstanceId>_site<Id>_v2`. The volume is
`HCSearchSiteVolume{Center = house.ModelToWorld(Center), Radius}`; yaw-only placement keeps the
radius valid.

**Targeting.** T5 owns `HCInteriorAction.c`. With `CCTCursor(1.8)`, the server accepts either:
- (a) a House target: `target.GetObject()` or `target.GetParent()` is a `House` of a
  `Search: covered` class, `house.WorldToModel(target.GetCursorHitPos())` is inside a site
  sphere, and the player is within 2.5 m of that site's world centre (the existing 6.25 m² check);
- (b) a placed searchable prop (the current path).

Templates are server profile data, so the client preview accepts any `House` cursor target; the
server decides and a refusal only logs. It is unobserved whether a cursor on baked building geometry yields a usable target (CAP-09). If
it does not, only placed props are searchable, and that fallback is reported.

## 7. `furnish-NNN.json`

```json
{"SchemaVersion": 2, "Chunk": 0, "Rows": [{"Slot": 0, "BuildingClass": "Land_House_1W01",
  "Position": [1598.03,304.51,8970.62], "Yaw": 15.04, "Props": [1, 3], "History": "family"}]}
```

- `Slot` 0..1499, unique across chunks; `Props` are template slot ids that all allow `History`.
- Totals: ≤ **1,500 props**, ≤5 per house, one row per instance.
- T2 selects deterministically from `PackId`, towns first (stable across restarts, INT-04). A
  changed pack is a new `PackId` under the existing manual epoch migration, never rerolled in place.

## 8. Runtime budgets and lazy binding

The lead adds new settings to `3_Game/HCSettings.c` with bounds validation; workers only read them.

| Setting | Default | Bounds | Meaning |
| --- | --- | --- | --- |
| `MaxFurnishedProps` | 1500 | 0..2000 | Props placed once in `OnStart` |
| `MaxPropsPerInterior` (exists) | 5 | 1..20 | Slots per house |
| `MaxActiveInteriors` (exists) | 12 | 1..32 | Search houses bound at once; least recently used idle house released first |
| `MaxBoundSearchSites` | 256 | 1..1024 | Sites with registered supply per epoch; journal ≤4,096 entries |
| `SearchBindRadius` | 2.5 m | fixed | Player to site centre |
| `InfectedBindRadius` | 30 m | 5..60 | Clue to house origin |
| `MaxBindQueriesPerTick` | 2 | 1..8 | Spatial queries per tick, within `MaxTickWorkItems` |

**Placement (T3).** Runs once in `OnStart` before players join, through the existing
`PlaceCandidate` path. There is no live-tick furnishing. The startup cost of 1,500 props is
unmeasured. The lead measures it with `HCPerfSampler` and lowers `MaxFurnishedProps` if needed,
without changing the schema.

**No periodic player scan.**
- **Search (T5).** The first valid server-side search start binds the site. It runs one
  `GetObjectsAtPosition3D` over the site sphere, registers and journals the existing CE items, then
  lets the action proceed.
- **Infected (T4).** `BuildProductionOrder` binds when it receives an observed clue. It runs one
  `GetObjectsAtPosition3D(clue, InfectedBindRadius)` and keeps the `Rooms: covered` houses in a
  least-recently-used cache: ≤64 houses, ≤16 anchors each, ≤256 anchors total.

## 9. Infected room anchors (T4)

Template `Rooms` replace the per-instance `Buildings` in `Infected/production-rooms.json`. Each
room becomes one `HCInfectedOwnedProductionRoomAnchor`:

| Anchor field | Value |
| --- | --- |
| `Id`, `LocalPosition` | `Room.Id`, `Anchor` |
| `LocalMin`, `LocalMax` | The room box |
| `SourceRunId`, `SourceSha256` | `Evidence[0]` |
| `EvidenceKind` | `native-room-survey-v1` |

- House box = template `Box`; world anchor = `house.ModelToWorld(Anchor)`. The live `House` is
  pinned by exact type, yaw only, as `ResolveBuilding` does; changed or ambiguous refuses.
- The legacy `production-rooms.json` still loads. If it and the templates both exist, log
  `rooms_conflict` and use neither.
- On success, log `rooms_templates_provisional_path_audio_doors_pending` and add
  `classes=<covered>/<denominator>`.

## 10. Ownership (disjoint files)

Enforce paths are under `mods/HollowCountry/`.

| Task | Writes only | Notes |
| --- | --- | --- |
| T1 | `tools/setup/interior_sampler.py` | All-class batch plans (≤64 targets per run), `native_run_id`, House config census, door rows |
| T2 | new `tools/package/interior_templates.py`, new `tests/slow/test_interior_templates.py` | Census plus stock XML to `classes-*`, `t-*`, `furnish-*`; imports `tools/audit/interior_points.py`, never copies it |
| T3 | `scripts/4_World/Interiors/*` except `HCInteriorAction.c` | Loader, placement, shared reader API |
| T4 | `scripts/4_World/Infected/HCInfectedRooms.c` | Class anchors, lazy bind |
| T5 | `scripts/4_World/Loot/*`, `scripts/4_World/Interiors/HCInteriorAction.c`; new `tools/package/search_context.py`, new `tests/slow/test_search_context.py` | Groups, lazy site bind, House targeting |
| T6 | `tools/package/interiors_profile.py` | Assembles, pins, validates, installs and rolls back `templates/`; starts after the T2 and T5 tools land |
| Lead | `scripts/3_Game/HCSettings.c`, this contract | Native runs, Wine compile, perf capture, install |

**Shared reader API.** T3 owns it; T4 and T5 call it.

| Signature | Returns |
| --- | --- |
| `static bool HCInteriorTemplates.Loaded()` | Whether the pack loaded |
| `HCInteriorTemplateClassRow ClassRow(string cls)` | The class row |
| `HCInteriorTemplate Template(string cls)` | The class template |
| `HCInteriorSearchGroup Group(string id)` | A search group |
| `string SourcePin()` | The index `SourcePin` |

Each returns `null` or `""` when the item is absent or the pack was refused. Until T3 lands, T4
and T5 code against these exact signatures, using a test-only stub in their own tests.

## 11. Test commands

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.slow.test_interior_templates tests.slow.test_interior_points -v   # T2
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.slow.test_search_context -v  # T5
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v                                              # all, before review
```

Each task records its failing test first, then the passing command (AGENTS.md). Synthetic
fixtures carry `"Synthetic": true` in fixture metadata only, never in a pack. Offline tests prove
only the schema and refusal behaviour.

## 12. Lead native steps; what stays pending

1. T1 batches of ≤64 targets (about 5–8 runs) on the local server. Census files stay outside Git.
2. One batched Wine compile (`tools/setup/wine_compile_probe.py`) after T3, T4 and T5 land.
3. DayZDiag: log per-kind `ReadFile` count and length, the frame verdict, and resolve/refuse counts.
4. Normal server: `interiors_profile.py install --target <profiles>/HollowCountry`, then a
   one-client walk covering clearance, doors, stairs, baked search (CAP-09) and infected rooms.
5. `HCPerfSampler` at startup and during play with 1,500 props.

Pending until observed: rendered clearance, replication, the baked-target action, CE value-tier
fit, 1,500-prop startup cost, and single-client behaviour (a user test).
