# Local debug map

From the repository root, with Python 3.10 or later:

```sh
python3 -m tools.webmap.server --snapshot '/path/to/server-profile/HollowCountry/debug/snapshot.json'
```

Open `http://127.0.0.1:8765/`. The listener always binds `127.0.0.1`; there is
no remote-bind option. `--port 8765` selects the port. Optional
`--map-image '/path/to/your-own/chernarus.png'` accepts a local PNG/JPG up to
32 MiB. No third-party packages, external scripts, map tiles or CDN are used.
Only the index, snapshot, sibling loot map and explicitly supplied image can be served. This is
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
This worker implements the server text registration; **in-game text input and
the longer client request/session lifetime still require lead wiring** in the
existing admin client/menu. No new RPC payload field or mission file is needed.

Each request starts one job, with no automatic repeat and one final reply.
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

Defaults live in `HCAdminLootMapLimits` (source defaults, not a JSON-loaded
configuration). The sole new distance is `QueryRadiusM=1000`, anchored to the
approximately 1 km native network bubble / rifle gunshot scale. It also gives
the square cell width; the containing circle covers the cell. The job uses
native world bounds, half-open cell ownership and a bounded set of already
observed entity handles to avoid overlap/moving-entity duplicates. It may still
miss an entity that moves into an already visited cell; it is not an atomic
world snapshot. Limits: one global job, one circle query per core tick, 32 rows
per step, 4096 objects/proxy cargos per query, 65536 scanned rows per job, 8192
matches, 32 classes, 1024 cells, 128 positions per reply/export, 300 seconds per
job, 30 seconds global request cooldown, 64 KiB export. Position clipping keeps
the observed counts and reports the omitted position count. Other caps produce
named refusals with explicitly partial observations. Count and elapsed-time
budgets use `HCUnitBudget` and `HCWorkBudget` with retained cursors.

Native `GetObjectsAtPosition` has no cursor, output-size bound or cancellation.
The post-query cap bounds retained/processed work, **not its native peak time
or allocation**. Measuring this call on the target 3–6-player load is mandatory
before production enablement; the caps are provisional. Missing CE/world
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
normal signed PBO/server, two-client privacy/replication and cost observations
remain pending; no engine experiment is accepted by this receipt.
