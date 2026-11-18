# Local debug map

From the repository root, with Python 3.10 or later:

```sh
python3 -m tools.webmap.server --snapshot '/path/to/server-profile/HollowCountry/debug/snapshot.json'
```

Open `http://127.0.0.1:8765/`. The listener always binds `127.0.0.1`; there is
no remote-bind option. `--port 8765` selects the port. Optional
`--map-image '/path/to/your-own/chernarus.png'` accepts a local PNG/JPG up to
32 MiB. No third-party packages, external scripts, map tiles or CDN are used.
Only the index, snapshot and explicitly supplied image can be served. This is
a read-only operator tool with no game commands or admin authentication.

The viewer re-reads the snapshot on each request (1 MiB maximum), checks the
version, coordinates and point/route bounds, and refuses an export while its
`.tmp` intent exists. Missing, partial or invalid exports return HTTP 503; the
page keeps its last valid display and shows the failure and last read time.
The browser polls every 15 seconds. No socket is opened by the offline smoke
test; its HTTP connection and profile/image bytes are explicit synthetic fixtures.

See [DEBUG_MAP.md](../../docs/DEBUG_MAP.md) for preferences, capture limits,
available/missing layers, image preparation, recovery and pending native checks.
