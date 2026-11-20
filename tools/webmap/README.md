# Local debug map

From the repository root, with Python 3.10 or later:

```sh
python3 -m tools.webmap.server --snapshot '/path/to/server-profile/HollowCountry/debug/snapshot.json'
```

Open `http://127.0.0.1:8765/`. The listener always binds `127.0.0.1`; there is
no remote-bind option. `--port 8765` selects the port. Optional
`--map-image '/path/to/your-own/chernarus.png'` accepts a local PNG/JPG up to
32 MiB. No third-party packages, external scripts, map tiles or CDN are used.
Only the index, snapshot, sibling loot map, explicitly supplied RPT overlay and image can be served. This is
a read-only operator tool with no game commands or admin authentication.

The viewer re-reads the snapshot on each request (1 MiB maximum), checks the
version, coordinates and point/route bounds, and refuses an export while its
`.tmp` intent exists. Missing, partial or invalid exports return HTTP 503; the
page keeps its last valid display and shows the failure and last read time.
The browser polls every 15 seconds. No socket is opened by the offline smoke
test; its HTTP connection and profile/image bytes are explicit synthetic fixtures.

See [DEBUG_MAP.md](../../docs/DEBUG_MAP.md) for preferences, capture limits,
available/missing layers, image preparation, recovery and pending native checks.

For #168 request 5, the server also accepts `lootmap <class-or-prefix>` through
the existing allowlisted admin RPC when both `EnableAdminMap` and
`EnableDebugSnapshot` are on. Examples: `lootmap BandageDressing` (exact known
class), `lootmap Ammo_` (prefix when no such class exists), `lootmap Ammo_*`
(explicit prefix). Matching is case sensitive. Only letters, digits and `_`
are allowed, with one optional trailing `*`; the input limit is 96 characters
including `*`. The server rechecks sender authority before work and delivery.
The server text registration is in `HCAdminModule`; the client sends it through
`HCAdminClient.HCLootMap(filter)` (same bounded filter check, same 104-character
wire limit). Like `snapshot`, the server answers at once with an ack (`started
ticket=<n> est_ticks=<n> cells=<n> tick_ms=<n> budget_ms=<n> final_reply=by_ticket`) under the ordinary 10 s
request timeout, so the admin client is free for the whole job: other commands
and reopening the menu work. A second `lootmap` while one runs is refused with
`lootmap_job_running`. The final marks reply arrives later and is matched by
the acked ticket; the client keeps its session and ticket for a window derived from
the deadline the server sent in the ack (`budget_ms`, the job tick cap times the
slower of the configured `TickIntervalMs` and a bounded running value of the cadence
`HCServer` delivers to the admin module, `HCAdminLootMap.HCSmoothTickMs`: each tick
moves it by `1/ObservedTickDivisor` of the gap and a sample is clamped to
`ObservedTickMaxMs`, so one slow or fast tick never sets the budget;
`HCAdminLootMap.HCBudgetMs`). `HCAdminLootMap.HCClientWindowSeconds`
adds `ReplyGraceSeconds`, never goes below `MinClientWaitSeconds=60` and never above
the largest-job ceiling `HCClientWaitSeconds()`; an ack without a readable `budget_ms`
gets the ceiling. The client then logs a client-timeout. A failure after the ack (for
example the final export write, `lootmap_export_failed`) is sent as that final ticketed
reply, so the client clears its ticket and shows the notice at once. Any refused or
failed final reply (`result=refused`) keeps the previous `lootmap` marks on the client
map and shows the reason (plus `previous lootmap marks kept; previous run filter=<filter>`);
`HCAdminClient.HCLootLayerStatus()` (also in `HCState()`) names the filter of the marks on the
map and `(previous run)` while they are kept; only an `ok` final reply,
including one with no matches, replaces the layer. If the session ends first
(`HCStop`), the client logs the dropped ticket and ignores the late final reply
(the server may still finish and writes its export). The reply marks replace
only the `lootmap` layer of the client map view and stay for `ViewSeconds`; a
later snapshot reply keeps that layer and each layer expires on its own timer.
In the admin menu's Map tab, type the class or prefix into the filter box and
press Run lootmap (disabled while a request is in flight). No new RPC payload
field or mission file is needed.

Each request starts one job, with no automatic repeat, one ack and one final reply.
An accepted request replaces the previous sibling
`$profile:HollowCountry/debug/lootmap.json` with `pending`, then writes the same
final observations used for the admin reply. The viewer reads this sibling
without a new command-line argument, even if `snapshot.json` is unavailable.
Toggle the `lootmap` layer and type a class prefix (or select Exact class).
The filter only changes the local display; it sends no game commands. The
timestamp is capture start UTC, not current freshness. Disconnect/stop cancels
the job and leaves `pending`; it never turns unfinished work into a completed
census. Completed historical exports remain dated until another request.
The existing loopback viewer has no game-identity authentication: it is an
operator tool for a private local profile, not an endpoint to expose to players.

The supported result is **ground world observations across ticks**, with a
per-observed-class count and native CE `nominal`. The installed snapshot
contributor path (`HCDebugSnapshot` / `HCAdminSnapshotWire.HCBuild`) has **no CE
enumerator**. Installed `3_Game/Global/Game.c:923` provides circle enumeration;
`3_Game/Entities/EntityAI.c:885,888` provides hierarchy parent and economy profile;
`3_Game/CE/CentralEconomy.c:754` provides the profile nominal. Cargo and carried
items are excluded; CE count flags are not reconstructed. All results carry
`census=refused_ce_inventory_enumeration_unavailable`. If no matching instance is
observed, nominal is explicitly unavailable: there is no installed per-class CE
profile lookup. A ground count of zero never proves a type does not exist.
`EconomyMap` is a developer/diagnostic TGA exporter, not a positions provider.
No DIAG-only CE call, spawn, deletion or inventory write is used.

The server prints one `[HC Plan] wp=168-5 state=started ...` line per accepted job with `rows_per_tick` and
`min_rows_per_tick` (`MinRowUnitsPerTick`).

Defaults live in `HCAdminLootMapLimits` (source defaults, not a JSON-loaded
configuration). The sole distance is `SubCellM=500`, the square sub-cell edge
for one query (it replaces the former fixed 1 km `QueryRadiusM`). The query
circle is the cell's half diagonal rounded up, so it covers the square; each
native circle (radius 354 m) covers about an eighth of the area of the former 1000 m-radius call. The job uses
native world bounds and half-open sub-cell ownership as the dedupe: each
observation is counted only by the sub-cell that owns its position, so
overlapping circles never double count a stationary entity and the job keeps no
seen-list (the former `m_Seen.Find` was O(n) per row). An entity that moves into
a sub-cell not yet visited after it was counted can still be counted twice; it is
not an atomic world snapshot.

Job arithmetic (derived, not a wall-clock guess; `HCAdminLootMap.HCJobTickCap`):
one sub-cell query per core tick, then rows until `MaxRowsPerStep=256` units are
spent. A row whose class does not match costs 1 unit (one `GetType` compare, no
cast); a match costs `MatchRowUnits=4`. The row loop has its own wall-clock
deadline, `RowDeadlineMs=4`, that starts after the native query, so a slow query
(which cannot be preempted) never spends its own rows' deadline and a cell costs
its query tick plus only the extra ticks its rows need. A tick therefore ends at
the end of a sub-cell, with the row-unit budget spent, or at the wall-clock
deadline. Progress is deterministic: the deadline is only consulted after
`MinRowUnitsPerTick=128` row units (clamped to `MaxRowsPerStep`) were spent, so a slow
row loop still advances at least that many units per tick. The tick cap is sized from
that guaranteed floor plus `TickCapHeadroomPercent=25` on the row term: `ticks <= cells
+ ceil(R / MinRowUnitsPerTick) * (1 + TickCapHeadroomPercent/100) + 1` with `R =
MaxItemsScanned + (MatchRowUnits-1)*MaxMatches`. For Chernarus (15360 m):
31 x 31 = 961 cells, `65536 + 3*8192 = 90112` units / 128 = 704 ticks, +25% = 880,
cap 1842 ticks (1842 s at the budgeted 1000 ms core tick; the former 256 cells at
32 rows per tick needed at least 256 + 2048 ticks against a 300 s cap). A core
tick slower than `MaxTickIntervalMs=1000` refuses with
`tick_interval_exceeds_job_budget` instead of silently missing the cap.
Exceeding the tick cap refuses `job_tick_cap` with explicitly partial
observations. Other limits: one global job, 4096 objects/proxy cargos per query,
65536 scanned rows per job, 8192 matches, 32 classes, 1024 cells, 128 positions
per reply/export, 30 seconds global request cooldown, 64 KiB export. The
client wait ceiling is the largest admitted job (`MaxCells`) at the budgeted tick
plus `ReplyGraceSeconds=30`; the actual window comes from the ack (above). Position clipping keeps the observed counts and reports
the omitted position count. Other caps produce named refusals with explicitly
partial observations. Count budgets use `HCUnitBudget` and `HCWorkBudget` with
retained cursors. The start line names `query_cost=unmeasured`.

Native `GetObjectsAtPosition` has no cursor, output-size bound or cancellation.
The post-query cap bounds retained/processed work, **not its native peak time
or allocation**. Measure this call on the native server with at most one client before
acceptance; the caps and target-load capacity remain provisional. Missing CE/world
availability refuses `ce_world_enumeration_unavailable`. Interrupted stores use
the existing verified intent/backup/copy/readback protocol; preserve `.tmp` and
`.bak` for recovery. The viewer refuses pending intents, malformed/zero-version
documents, oversized files, inconsistent counts and invalid coordinates.

Trace: #168 request 5 -> bounded server observation job / shared budgets /
sibling export / filtered layer -> `tests/unit/test_admin_lootmap.py`. The test
executes authored handlers with explicit synthetic native/file/identity/HTTP
ports. Initial RED (before implementation):
`AssertionError: Missing authored method HCAdminWire.HCIsLootMap in HCAdminWire.c`.
Focused GREEN command:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_admin_lootmap -v`
(`Ran 1 test; OK`). These are offline source checks only. Exact-source DayZDiag,
normal signed PBO/server, single-client privacy/replication and cost observations
remain pending; no engine experiment is accepted by this receipt.

Layer legend (w27): the page lists each layer's meaning and, for bounded layers
(for example `camps`), the optional snapshot `layerStats` row as
`N of M shown` with a truncated note. `layerStats` is validated when present and
optional, so older snapshots still load. Offline check only:
`tests/unit/test_debug_map_layers.py`; nothing observed in DayZ yet.

w28 (#193): the legend also describes `lead-ledger` (unexpired ledger rows at place
level, no group ids) and `scenes` (lease anchors, not an entity-presence claim) with
their `layerStats` rows. The in-game admin wire carries the same per-layer
`sent/total` in its Notice. Offline check only: `tests/unit/test_debug_map_layers.py`;
nothing observed in DayZ yet.

w29 (#194): the legend also describes `pickers`, `group-pins` (kind, position and
expiry only; no player ids or names) and `materializer-proposals` (active leases,
not the eligible `materializer_candidates` rows). A `layerStats` row may carry an
optional `unplaced` count (rows with no drawable position, kept out of `total`);
it is validated when present and shown in the legend. Offline check only:
`tests/unit/test_debug_map_layers.py`; nothing observed in DayZ yet.


## RPT refusals beside world state

Generate a layer from one or more **server RPTs**, keeping the output outside
this repository (the default is `/tmp/hollow-country-rpt-overlay.json` on this host):

```sh
python3 -B -m tools.webmap.rpt_overlay /path/to/server.RPT --out /tmp/hollow-country-rpt-overlay.json
python3 -B -m tools.webmap.server --snapshot /path/to/profile/HollowCountry/debug/snapshot.json --overlay /tmp/hollow-country-rpt-overlay.json
```

`--overlay` also works without `--snapshot`. With both options, the existing
snapshot layers (including contributed AI positions/routes) and sibling loot
map remain available. The viewer polls the supplied files every 15 seconds;
rerun the parser to update its historical RPT layer. It does not tail logs or
request an engine snapshot. An unavailable overlay is cleared with a visible
status, independently of the last valid world snapshot.

Each `rpt/<kind>` checkbox controls one of `route-refusal`, `ai-refusal`,
`event-bind`, `shelter-refusal`, `interior-warning`, or `incident`. Hover a point
for module, reason, occurrence count and metre coordinates. Refused-leg endpoints
are plotted as separate points, without inventing a traversable route. Counts
aggregate identical kind/module/reason/position observations across all input
files; repeated/overlapping logs will count twice. The CLI prints counts of
classified **lines** per kind, including `unplacedByKind` for diagnostics with
no valid coordinates or resolvable content ID; endpoint counts must not be summed as event counts.

The version-1 `FeatureCollection` uses DayZ **x,z metres**, not geographic
longitude/latitude. Each point has `kind`, `module`, `reason`, `position: [x,z]`
and `count` properties. Explicit coordinates take precedence: labelled
`pos/position/at/from/to/start/end/anchor/point/center/centre/waypoint` pairs or
x,y,z vectors, bracketed vectors, or `x=… z=…`. Native route `from=|x,y,z` and
`to=|x,y,z` are supported.

When a line has no valid coordinates, content IDs resolve against catalogues
loaded once from this checkout. Use `--catalog-root /path/to/checkout` to select
a different repository revision; the option expects a root containing `mission/`
and `mods/`. No server profile or installed-mod data is loaded. Sources are:

- `mission/hollow-country/ai/sites.json`: site first waypoint, holdout
  `HousePosition`, HC43 locality/cluster/region anchors (AI camp locations).
- `mission/hollow-country/ai/localities.json`: locality definitions; rows without
  coordinates do not invent a location. HC43 supplies authored locality anchors.
- `mission/hollow-country/events/story-sites.json`: authored event anchors.
- `mission/hollow-country/travel/auditshelter_scenes.json` and
  `travel/route-surveys.json`: regional shelter scene positions and region aliases.
- `mods/*/data/defaults/expansion-ai-sites.json` and
  `expansion-ai-localities.json`: fallback IDs absent from mission catalogues.
- `mods/HollowCountry/scripts/4_World/Events/HCEventSites.c`: the two literal
  source IDs and `Vector` positions. This reads data literals only. Event family
  suffixes `-1` through `-7` follow `HCEventRoster`'s authored ID construction.

Conflicting anchors for the same ID remain unresolved; a region with several
positions has no single inferred centre. Runtime-created camps without shipped
anchors also remain unresolved. ID matching accepts known catalogue tokens,
content fields such as `id=`, `site_id=`, `locality=`, `camp=` and `region=`,
`site <id> route/spawn ...`, and the semicolon-delimited event bind format.
Catalogue points show `catalogue anchor;` in their reason: these are authored
locations, not observed actor positions or proof of a valid route. Reasons retain
a reason/refusal token or short sanitized suffix, never the raw RPT line.

The summary includes `linesByKind`, `placedByKind`, `unplacedByKind`,
`coordinateLines`, `catalogLines`, feature count and catalogue load/conflict
counts. `unplaced` retains failed content IDs and counts (including a failed ID
on an otherwise placed line); `<no-id>` means no usable content ID was present.
This list retains at most 256 distinct kind/ID pairs and reports excess
occurrences in `unplacedIdsOmitted`. Explicit-coordinate lines need no ID lookup.
Endpoint/feature counts must not be summed as event counts.

Before classification, whole lines containing a 17-digit number, `Player "`,
`name=`, `uid`, or `steam id`/`steamid` are still dropped case insensitively.
The old blanket `id=` ban now exempts only `id`, `site_id`/`siteid`,
`locality_id`/`localityid`, `camp_id`/`campid`, `region_id`/`regionid` and
`mission_id`/`missionid` keys; other identity-style ID keys are dropped.
No filenames, timestamps or raw lines are written to the layer. UTF-8 and
BOM-marked UTF-16 RPTs stream with a 64 KiB line cap; oversized lines are skipped
whole. Catalogue files each cap at 10 MiB. The layer caps at 2,048 distinct points
and 1 MiB, reports omitted positions, and replaces the output via a sibling
temporary file. The loopback server validates each read, rejects identity
markers and serves only the approved feature fields.

Read-only validation on 2026-11-19 selected the **largest** `*.RPT` in
`/mnt/d/HollowCountryLocal/friend-local-1/profiles/` (now on E:) (2,643,500 bytes at read time).
This supersedes the earlier empty-layer probe of the two newest logs.

| Kind | linesByKind | Placed lines | Unplaced lines |
| --- | ---: | ---: | ---: |
| route-refusal | 24 | 19 | 5 |
| ai-refusal | 22 | 0 | 22 |
| event-bind | 3 | 2 | 1 |
| shelter-refusal | 2 | 0 | 2 |
| interior-warning | 0 | 0 | 0 |
| incident | 0 | 0 | 0 |

Total: **51 classified lines, 21 placed, 30 unplaced, 22 aggregated points**;
all placed lines used catalogue anchors, with zero explicit-coordinate lines.
There were 60 privacy-dropped lines, no oversized lines or omitted positions.
Top unresolved patterns were exclusively `<no-id>`: AI 22, route 5, shelter 2,
event bind 1. No unresolved named content IDs remained in this log. Eight
catalogue files loaded, resolving 2,445 IDs; 2,520 conflicting IDs (including
event-family aliases) were left unresolved rather than choosing an anchor.
No raw log lines or player identities were printed. Generated output passed the
same validator used by the viewer. Temporary synthetic checks also exercised
UTF-16, explicit-coordinate precedence, unknown IDs, shelter region and holdout
resolution, and every retained privacy ban. No unit tests were added or changed.

This establishes parsing of historical native diagnostics only. Live AI routes,
interactive browser alignment, operator-edited catalogue agreement and native
server/single-client behavior remain unverified. No game process was launched,
stopped or signalled; no multiplayer acceptance is claimed.
