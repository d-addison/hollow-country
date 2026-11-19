# W5 #122: debug world snapshot and local map

Source implementation only. No client has connected; native Windows compile,
DayZDiag and normal PBO/server qualification are pending. Offline Python tests
establish no DayZ behavior. This document is the bounded W5 spec/plan/task record
for the debug worker: `docs/SPECIFICATION.md` and
`docs/specs/001-survival-overhaul/spec.md` were absent in this worktree. The
existing runtime implementation contract and active owner instructions apply.

## Requirements and implementation

| Finding / task | Source result | Remaining evidence or gap |
| --- | --- | --- |
| #122 snapshot module and shared contributor API | Implemented in `4_World/Debug/`; registry extension self-registers the module | Lead must add default-true `HCSettings.EnableDebugSnapshot`; native compile pending |
| #122 disabled cost and bounded work | Disabled module has no allocated buffers, contributor registration, capture or file I/O; one Describe per core tick using a cursor | Native timer cost and target 3–6-player load remain unmeasured |
| #122 JSON and persistence | Exact version-1 envelope; native JSON encoding of all dynamic point/route values; `.tmp`, backup, copy and readback using existing HCGroupIO | True atomic replacement skipped: installed engine has no rename primitive; see recovery |
| #122 read-only contributors | Players, holdouts, camps (w27), lead ledger and scenes (w28), pickers, group pins and materializer proposals (w29 #194; all register in the module), live dead-drop caches, shelter catalog/placed state, events, received leads, eligible materializer ledger candidates | Missing layers listed below; no private state, entity search or provider claims |
| #122 local web map | Stdlib server bound to 127.0.0.1; bounded re-read, toggles, hover, route lines, 15 s polling, grid/towns and optional operator image | Interactive browser inspection and native JSON interoperability pending |
| #122 diagnostics | One HCV2Admission call per module lifecycle instance; success summary at most once per 600 real seconds | RPT lines must be observed by lead; none asserted here |
| #123 in-game admin map | Implemented separately: `4_World/Admin/HCAdminModule.c`, `HCAdminStatus.c`, `5_Mission/Admin/HCAdminClient.c`, `HCAdminMenu.c`, gated by `EnableAdminMap` and `profiles/HollowCountry/admins.json`; see `docs/ADMIN_TEST_KIT.md` | Two-client replication and visibility checks pending |

## Operation

The lead adds **only** `bool EnableDebugSnapshot = true` to the existing
HCSettings schema at landing. The worker references that exact field without
editing shared core files. No core start/tick/stop hook, config.cpp, input or RPC
change is needed: `modded class HCModuleRegistry` registers
`HCDebugSnapshotModule`. Core already invokes module lifecycle methods.

On a server running ChernarusPlus, start a capture every 20 seconds. Capture is
staggered, one contributor per existing approximately one-second core tick;
the completed file appears after the last contributor (first export around
26 seconds with the seven built-ins, up to 35 seconds with 16 slots; the cap is now 24).
Subsequent cycle starts remain 20 seconds apart at normal core cadence. Stalls
do not trigger catch-up writes; a cycle finishes before another can begin.
This is a view gathered over several ticks, not a transactionally simultaneous
world state. Turning the preference off requires the usual server settings
reload/restart; existing exported files are retained and may be stale.

The file is `$profile:HollowCountry/debug/snapshot.json`. Its shape is:

```json
{"version":1,"time":1199145600,"map":"chernarusplus","layers":{"example":[{"id":"synthetic","x":6700,"z":2600,"label":"Synthetic example","detail":"Illustration only"}]},"routes":[{"layer":"example","id":"synthetic-route","label":"Illustration only","points":[[6700,2600],[6800,2700]]}],"layerStats":[{"layer":"example","total":1,"shown":1,"truncated":0}]}
```

`time` is the world calendar at capture start, converted to Unix-style seconds
with minute precision via `GetWorld().GetDate` and existing
`HCGroupClock.CalendarUtc`. It is **not** wall-clock freshness, UTC telemetry or
evidence of an observed location. Unsupported dates outside the shared calendar
converter's positive integer epoch range stop export with a diagnostic.
Map coordinates are metres, x east and z north, bounded to `[0,15360]`.

Run the operator tool on the machine that can read the profile:

```sh
python3 -m tools.webmap.server --snapshot '/path/to/profile/HollowCountry/debug/snapshot.json' --port 8765
```

Open `http://127.0.0.1:8765/`. Optional background:

```sh
python3 -m tools.webmap.server --snapshot '/path/to/profile/HollowCountry/debug/snapshot.json' --map-image '/outside/repository/chernarus.png'
```

On Windows the same module invocation accepts a Windows path and can use `py -3`
instead of `python3`. Python 3.10+ and a modern browser are sufficient. No
external services or dependency installation are needed. The tool has no
commands for changing the game. Keep it local: this debugging snapshot contains
player display names and hidden server locations and is not a player discovery
feed. A successful browser read says only that the file was valid at that read;
check its filesystem modification time if the exporter has stopped.

## Bounds and shared API

`HCDebugContributor.HCDescribe(HCDebugSnapshot snapshot)` is called only by an
enabled capture. `HCRegister` retains a ref, is idempotent by object identity,
and caps the registry at 24 contributors (`HC_REGISTRY_CAP`, raised from 20 in w29 #194: 12 built-ins, 6 module singletons, 3 Expansion AI pages = 21 used). `HCUnregister` releases membership;
an in-progress capture skips contributors unregistered before their turn.
Built-ins register on start and unregister on stop; external Infected/AI owners
must use the same lifecycle. No dependency on the optional AI addon is introduced.

Each contributor must keep its own computation cheap and bounded; the API can
cap emitted data, not arbitrary work inside another owner's Describe. Each
Describe can add at most 64 points and 8 routes, each with 2–64 vertices. The
entire snapshot caps at 1024 points, 128 routes and 1 MiB of encoded JSON. Extra
registrations/rows/routes are ignored. Labels, details, IDs and layer names cap
at 128/256/96/48 bytes in Enforce; bad coordinates or invalid routes are dropped.
Point IDs are scoped to their layer and diagnostic only. Route input is copied.
The exporter never modifies player, inventory, provider or gameplay state.

Wire-cap split (w27, w28): the 1024-point cap is `MAX_POINTS`. Shared `AddPoint`
callers (ai-units, players, holdouts, events, ...) fill at most
`MAX_POINTS - DEBUG_LAYER_POINTS` = 876; hardened layers call
`HCAddLayerPoint` against their own `DEBUG_LAYER_POINTS` = 148 share (raised from 88 in
w29 #194; `MAX_POINTS` stays 1024), split by named caps: `camps` `CAMP_LAYER_CAP` 24 +
`lead-ledger` `LEAD_LAYER_CAP` 56 + `scenes` `SCENE_LAYER_CAP` 8 + `pickers`
`PICKER_LAYER_CAP` 4 + `group-pins` `GROUP_PIN_LAYER_CAP` 32 + `materializer-proposals`
`PROPOSAL_LAYER_CAP` 24 = 148. Neither side can squeeze the other and the total
never exceeds 1024 on the wire. The new caps are named constants, not tuned
numbers: the picker owner holds one trip, the group-pin cap (32) matches the
group-service `MaxGroups` default and the layer reports the true total beyond it,
and the proposal cap (24) is the upper clamp of `HCAILimits.MaxMaterialized`
(default 15), the bound on active leases.
Each hardened layer reports `HCNoteLayer(layer, total, shown)`; the document
carries up to 16 `layerStats` rows `{layer,total,shown,truncated,unplaced}` where
`truncated` is 1 when `shown < total`. `unplaced` (w29 #194) counts rows that exist
but have no drawable position (a lead whose target place is unknown, a picker trip
with no known position); they are **not** part of `total`, so `total` is the number
of drawable rows and `shown <= total`. The field is 0 for layers that never produce
such rows and is optional in the viewer. The viewer validates the rows when present
(old snapshots without them stay valid) and prints them in its legend.

Admin wire (w28 #193, `HCAdminSnapshotWire`): caps are 512 marks, routes kept whole,
and w29 #194 raises the named layer cap `MAX_WIRE_LAYERS` from 16 to 24 so the three
new layers fit beside the existing 16. The 512 marks are no longer filled in insertion order.
A water-fill allocator gives every sent layer `512 / layers` first and shares what
small layers leave unused among layers that still have rows, so a late layer
(`camps`, `lead-ledger`, `scenes`) is no longer dropped first and `ai-units` is
bounded rather than starved. A layer's allowance covers its points first, then
whole routes that fit. w29 #194: allowance a layer cannot use (a route that does not
fit whole inside its share) is redistributed by a second water-fill to layers that
still have unsent points, never beyond a layer's own rows or the 512-mark cap. The reply
`Notice` (<=1024 bytes; the client replaces a snapshot reply's `Lines`, so Notice is
the carried channel) lists `layers=name:sent/total,...` with names clipped to 24
bytes, plus `layers_unsent=N` for layers beyond the 24-layer cap, and `unplaced=name:n,...`
only for layers with a nonzero unplaced count. `total` is the
wire demand (points + route vertices) plus any contributor-side loss from the
document's `layerStats` (`total - shown`), so a truncated `camps` reads
`camps:24/30`. `dropped=` stays the wire-only loss. Runtime pending.

Per-tick work is one of these (plus <=16 membership/cursor operations), or one
bounded final serialize/write; there is no full-map spatial scan:

| Contributor | Bound / meaning |
| --- | --- |
| Players | One GetPlayers roster fetch, <=64 inspected slots with a cursor; cache reused by leads; roster IDs are transient |
| Holdouts | <=24 existing public Snapshot clones; house position and ledger state, not a body-presence claim |
| Camps (`camps`, w27/w28) | `HCDebugCampSitesContributor` takes the holdouts contributor's registry slot (cap `HC_REGISTRY_CAP`). w28: it reads **one** `HCHoldouts.Snapshot` per row per capture (<=24 JSON round trips, was 48) and feeds both layers from that row: the existing `holdouts` layer (routine/occupants detail) and one `camps` row per site (id, house position, ledger state only). The overlap is kept on purpose rather than deduped: `camps` is the privacy-reduced operator view with its own point share and `layerStats`, `holdouts` the full-detail shared-pool view, and `ai-camps` (owner-registered, logical level/supply/population) stays a separate layer at the same positions; dropping either would lose a view for no saving once the snapshot is read once. No player ids or names; runtime pending. Boot 069 showed `camps total=48 shown=24`: **not a double count**. `total` is `HCHoldouts.Count()`, the real size of the holdout catalog (the `MaxHoldouts` default is 48); only the first `CAMP_LAYER_CAP` (24) rows are read and drawn, so `shown=24` with `truncated=1` is the honest report that 24 catalog rows are omitted. Each row is counted once (the `holdouts` and `camps` layers are separate layers fed from the same row, not summed into one total). Pinned by `CampsLayer` tests |
| Lead ledger (`lead-ledger`, w28) | `HCDebugLeadLedgerContributor` reads `HCWorldClock.UTC()` **once per Describe** (w29 #194; it used to be once per getter call) and passes it to the one-pass batch getter `HCLeadModule.HCDebugLeadRows(now, output)` (new file `Debug/HCDebugLeadRows.c`: unexpired rows only, scan <= `HC_DEBUG_LEAD_SCAN` 64, copies with group id withheld; never `Select`/`Latest`). Leads at an unknown place are counted in `unplaced`, not in `total`. <=`LEAD_LAYER_CAP` (56) rows at the authored named place: kind and expiry only. Separate from the older `leads` layer (what online recipients received); registered as a module built-in; runtime pending |
| Scenes (`scenes`, w28) | `HCDebugScenesContributor` reads `HCScenesModule.HCDebugGet/HCDebugLeaseCount/HCDebugLease` (detached `HCDebugSceneLeaseRow`: chain id, stage, anchor, placing/placed/closing, due/expiry). <=`SCENE_LAYER_CAP` (8) rows; lease anchors, not an entity-presence claim; runtime pending |
| Pickers (`pickers`, w29 #194) | `HCDebugPickersContributor` reads `HCPickers.Get().HCDebugPickerCount/HCDebugPicker` (detached `HCDebugPickerRow`: phase, locator `actor`/`source`/`home`/`none`, position, generation; no party, cargo, actor or home ids). <=`PICKER_LAYER_CAP` (4) rows; a trip with no known position is `unplaced`. The provider route is refused/unsurveyed, so the layer is expected to be empty until a trip runs; trip state is not a body-presence claim; runtime pending |
| Group pins (`group-pins`, w29 #194) | `HCDebugGroupPinsContributor` reads `HCGroupService.HCDebugPins(cap, output)`: for each stored group (<= `MaxGroups`) it asks the existing `HCGroupPins.Collect` (which already runs on every Broadcast; the death-pin collector prunes expired rows as it always does) and returns detached `HCDebugGroupPinRow` rows with kind (`ping`/`death`/`lead`/`trail`/`pin`, from the id prefix), position and expiry only. Pin id, name, group and player id are withheld; point ids are anonymous capture indices. Pins are server-side, so the layer is possible. <=`GROUP_PIN_LAYER_CAP` (32) rows, true total in the stat row; empty when the group service is unhealthy or the pins module is off; per-recipient presentation filters are not applied (this is the server view, not what a client sees); runtime pending |
| Materializer proposals (`materializer-proposals`, w29 #194) | `HCDebugProposalsContributor` reads `HCWorldMaterializer.HCDebugGet/HCDebugProposalCount/HCDebugProposal`: the **active leases** (queued/claimed/finished/materialized, age in seconds, actor cap, kind, place), detached `HCDebugProposalRow`. This differs from `materializer_candidates` (eligible ledger rows, no lease). The getters never call `Next`, expiry, claim or resolve. <=`PROPOSAL_LAYER_CAP` (24); lease state, not a live-body claim; runtime pending |
| Dead drops | <=8 public Cache handles; unbound/dormant caches omitted; no inventory enumeration |
| Shelters | Current catalog <=6 rows (hard loop cap 64); explicit catalog/not-placed or catalog-reports-placed detail |
| Events | One existing runtime clone (store ceiling 4 MiB, default 1 MiB), <=32 run rows and <=64 points; closed runs omitted; <=8 delivery objective lines |
| Live AI (`ai-units`, addon) | Every live eAI unit, <=128 per capture over two 64-point pages with a cursor across captures; faction, group id/size, source `expansion` or `hc-site`, state, weapon class; layer `ai` keeps HC-site patrols and routes |
| Received leads | <=8 cached players with a cursor; deduplicated authoritative group/solo keys; <=8×64 ledger checks, <=64 result rows; only online recipients represented |
| Materializer candidates | <=36 existing MaterializerRow reads; named-place ledger candidates explicitly marked as neither queued proposals nor live bodies |

Delivery lines are straight source-to-destination objective links, not surveyed
paths or AI patrols. Real patrol routes render through AddRoute when the owning
Infected/AI contributor supplies them. The offline fixture's route is synthetic.

The default canvas grid uses the existing approximate authored town centres
from `mods/HollowCountry/scripts/3_Game/World/HCWorldData.c` (Fresh), with the
same coordinates copied into index.html. They are orientation labels, not
surveyed geometry or additional runtime entities.

## Missing public state: deliberately skipped

| Area | Why a truthful complete layer cannot currently be authored here |
| --- | --- |
| Pickers (resolved w29 #194) | `HCDebugPickerCount/HCDebugPicker` added to `HCPickers`; see the `pickers` row above. The provider route is still refused, so no live trip has been observed |
| Scenes (resolved w28) | Owner getters added (`HCDebugGet`, `HCDebugLeaseCount`, `HCDebugLease`); see the `scenes` row above. Chain-level state beyond lease rows (completed chains, story schedule) is still not exported |
| Group pins (resolved w29 #194) | `HCGroupService.HCDebugPins` added; it reads the owner's own group records (no ACL/store clone) and exports kind/position/expiry only; see the `group-pins` row above |
| All leads / offline recipients (resolved w28) | `lead-ledger` layer reads the new owner getters (group ids withheld). The `leads` layer still shows online recipients only |
| Active materializer proposals (resolved w29 #194) | `Next` still **claims** a reservation and runs expiry and is never called from debug; the new read-only lease getters expose the active lease list instead (`materializer-proposals`) |
| Infected / optional AI addon | Owned and registered by their workers using the shared API; no duplicate contributor or dependency here |

To finish these gaps, their owners can register bounded HCDebugContributor
implementations in existing start/stop paths. This needs no new shared-core
hook. If a future public read seam is preferred, it must expose bounded copied
rows and must not scan buildings, claim work, commit state or resolve inventory.

## File consistency and recovery

The installed engine exposes CopyFile/DeleteFile and no rename/replace API.
**True atomic file replacement is skipped.** `HCDebugJsonStore.HCSaveText`
uses the existing HCGroupIO bounded write/read helpers and the existing
HCV2ThreatStore's temp-intent/backup/copy/readback protocol. It keeps `.tmp`
on any failure after creating intent, preserves the previous completed image
as `.bak`, and stops exporting on failure. The fixed envelope is authored text;
native JsonFileLoader serializes layers/routes, escaping all dynamic strings.
No Enforce field is named `map`, which is a native type name.

The local HTTP server refuses any `.tmp` intent (before and after read), caps
the read to 1 MiB plus one sentinel byte, and validates schema/coordinates/caps.
It returns 503 for missing, truncated or invalid data. The browser retains its
previous valid display with a visible error. These checks mitigate partial
reads; they are not an OS atomic rename/fsync guarantee. There is no automatic
fallback to `.bak` and no silent reset after an interrupted write.

If export stops, stop the game server, preserve snapshot.json/.tmp/.bak outside
the repository and inspect them. For disposable debugging only, the operator
can remove this **debug directory's** three snapshot files and restart to
regenerate. Never remove gameplay stores to repair a debug export. A missing
primary beside `.bak`, stale `.tmp`, directory failure, unsupported world/date
or copy/readback failure stops the exporter. No repeated failure-log flood.

`HCDebugJsonStore.HCSaveText` is the owned raw-JSON seam the lead could promote
to Core to consolidate the existing repeated verified-copy protocol. It was
needed because the schema's literal map key cannot be an Enforce field name;
it makes no new atomicity claim.

## Optional map image from your own installation

1. In your own licensed local DayZ installation/tooling, export or capture a
   flat ChernarusPlus overview. Extract only your own game data locally if
   needed; do not download tiles or commit/distribute extracted textures.
2. If your local texture exporter produces PAA/TGA, use your local texture
   viewer/image editor to convert it into PNG or JPEG. The viewer accepts these
   two formats only; it does not decode game textures or unpack PBOs.
3. Crop the image to the **entire** 15360×15360 m terrain bounds, with x=0 west
   at the left, z=15360 north at the top, and z=0 south at the bottom. Remove UI
   borders/legends. Use a square image; land-only crops misalign markers.
4. Save it outside the repository (maximum 32 MiB), pass `--map-image`, and check
   orientation against known town centres. Missing/invalid images fall back to
   the grid. No image, texture, PBO, tile or external asset is supplied here.

## Validation record and native checks still due

Exactly one new behavioral smoke lives in `tests/unit/test_webmap.py`, using
synthetic profile/image bytes and an in-memory HTTP connection (no sockets).

RED command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_webmap -v`

Actual RED line: `ModuleNotFoundError: No module named 'tools.webmap'`
and `FAILED (errors=1)`.

GREEN command: the same command. Actual GREEN line:
`test_local_readonly_map_rereads_bounded_complete_snapshots (tests.unit.test_webmap.WebmapSmoke.test_local_readonly_map_rereads_bounded_complete_snapshots) ... ok`
and `Ran 1 test` / `OK`.

Required checks: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_script_identifiers tests.unit.test_enforce_locals tests.unit.test_script_syntax tests.unit.test_webmap -q`
returned `Ran 16 tests in 4.861s` / `OK` after the final UTF8-safe text change.

Existing modules that read the changed source directly or scan/package the
addon: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_build_identity tests.unit.test_acceptance_markers tests.unit.test_native_wiring_batch_a tests.unit.test_gameplay_delta tests.unit.test_search_preview_sites tests.unit.test_v1_combined_rpc tests.unit.test_snafu_optional tests.unit.test_tactical_flava_optional tests.unit.test_workshop_sync tests.unit.test_package -q`
returned `Ran 363 tests in 39.102s` /
`OK (skipped=1, expected failures=1)`. The skip is the Windows-only PowerShell
helper test, not run here; the existing expected failure is the groups null
context case. No existing pin was updated. No full discover, Git, network,
DayZ, Wine or PowerShell run was performed. Inline JavaScript passed
`node --check`; the CLI's `--help` completed. No interactive browser result is
claimed.

The lead must compile the landed settings field and source on Windows, start
DayZDiag and the normal PBO/server, verify native serializer output matches the
documented envelope (including empty layers/routes), check timing, stop/restart,
directory/write faults and preference-off behavior, and review an actual live
snapshot in a browser. Infected/AI routes require their contributors to land.
Production acceptance and target-load benchmark budgets remain pending. Any
future network/visibility feature still requires two clients.

RPT substrings to grep (expected source diagnostics, not observed results):

```text
[HollowCountry] V2 admission feature=DebugSnapshot preference=on gate=W5-122 qualified=0 result=admitted unverified:
[HollowCountry] debug snapshot points=
[HollowCountry] debug snapshot disabled: world/date/store fault; preserve snapshot.json, .tmp and .bak
```

The success line continues `points=<n> routes=<n> bytes=<n>` and prints only on
first success and at least 600 real seconds later. Admission deliberately
records unverified native status. None of these lines establishes acceptance.

## #123 design (now implemented)

An in-game admin map should consume a server-built bounded DTO through an
authenticated, rate-limited admin-only request, sharing contributor data and
caps but never granting clients filesystem paths or gameplay authority. Keep
authorization in a core-owned server hook, use distinct core-owned RPC IDs and
input/menu registration, and evaluate redaction separately from existing
player discovery pins. `EnableAdminMap` is a separate preference. Design the
failure path, stale timestamps, byte/route limits and client rendering budget
before wiring. Requires native Windows compile, normal server/PBO testing and
two clients for authentication, replication and visibility checks. #122 itself adds
no RPC, permission gate or UI; the admin map that followed lives under `Admin/`.
