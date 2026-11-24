# Local connection check

Start the prepared vanilla server before opening the game. Keep Steam open and
use the installed DayZ client with no mods for this baseline.

The client launcher accepts the game and Steam query ports together:

```text
-connect=127.0.0.1:2302:27016 -port=2302
```

Use the ports actually observed on your server. In this configuration, UDP 2302
is the game port and UDP 27016 is the Steam query port. A query response alone
does not establish that a player can join.

With the game closed, the repeatable Windows helper is:

```powershell
powershell.exe -NoProfile -File .\tools\setup\Start-LocalClient.ps1 -ClientRoot 'D:\SteamLibrary\steamapps\common\DayZ' -WhatIf
powershell.exe -NoProfile -File .\tools\setup\Start-LocalClient.ps1 -ClientRoot 'D:\SteamLibrary\steamapps\common\DayZ'
```

Replace `ClientRoot` with your installed client directory. The helper requires
one running DayZ server bound to the requested loopback game port and refuses
to launch a second game. `-WhatIf` reviews the launch without starting it.

The observed Windows baseline on build 1.30.164289.70 passed connection,
movement, inventory and reconnect on 2026-11-17. Earlier launches without the
explicit query port returned unreachable; the explicit-port launch connected.
The server recorded the player connection and world transfer, and the tester
confirmed movement, inventory and successful reconnect.

After joining, log out to the main menu and use **Play** to rejoin the local
server. Check the displayed server name before joining. Baseline results apply
to vanilla only; signed addon loading and each gameplay feature require their
own tests. The prepared baseline runtime shuts down after its scheduled
30-minute session.

## Hollow Country local server = the friend install

The local Hollow Country test server is installed exactly as FRIEND_SERVER.md tells the
friend. There are no hand-copied mod folders or mission files and no per-tool installs.
This keeps local boots valid evidence for the friend server.

1. Start from a stock DayZServer folder (a copy of the Steam DayZServer install).
2. Build the friend bundle with `tools/setup/friend_bundle.py build` from the clean
   bundle source plus the signed `@HollowCountry` and `@HollowCountryExpansionAI`.
3. With the server stopped, run the bundle's installer against that folder:
   `py -3 -m tools.setup.friend_install --server-root <server> --plan-only`, then
   `--apply`, then `--check`. That is `install-hollow-country.bat` for the friend.
4. Start the server with the bundle's `start-server.bat` and read the RPT in
   `<server>\profiles`.

Every new build goes through the same bundle and installer. Mission JSON and profile
defaults then reach the local server the same way they reach the friend. When an installer
step refuses on the local server, treat it as a friend-install bug and fix the tool. Do not
patch the local folder by hand.

The older `local-v1-test-1` folder, which had runtime binaries and was patched by hand, is
kept only as rollback history.

## Loot boost on the local test session

`tools/setup/local_test_session.py apply` installs the loot boost by default as the last CE
layer (after economy, optional deltas, travel and CE coverage) and rolls it back first. It
multiplies non-firearm loot and `RespawnTypes` by `Multiplier` from
`mission/hollow-country/loot-points/settings.json` (default 2.0) and merges the contextual
building points from `loot-points/additions.json`. `--loot-multiplier N` (1.0-4.0) overrides the
setting, `--no-loot-boost` leaves it out and `--loot-boost` turns any skip advisory into a
refusal. Firearms, ammunition, magazines, attachments and explosives keep their scarcity.
`plan` prints a `loot boost (x2 ...)` line with per-family point counts. CE spawns on the added
`lootHCFloor` containers, the real loot density and the server cost remain pending native checks.

## Soak client join diagnosis (2026-11-24)

The archived 11:35:38 server RPT disproves a skipped CLI connect for this run:
`SteamGameServer_Init(0,8766,2302,27016,3,1.30.164289)` confirms the game/query
ports, and at 11:38:08 authentication rejects the client with code 146 because
DayZ-Expansion-Vehicles is newer on the client. All 33 Vehicles PBO filenames
match between the resolved Workshop client and staged server copies, but
`vehicles_scripts.pbo` differs in SHA-256. The lead must reconcile the installed
dependency versions before rerunning; this change does not update dependencies.

Read-only inspection of 3,140 script entries across the resolved client stack
(including the two own addons) found no override of `DayZGame.OnInitialize`,
`ConnectLaunch`, `ConnectFromCLI`, `Connect` or `GetLoadState`, and no dependency
assignment to the vanilla game/load state fields. CF's `scripts.pbo`,
`3_Game/CommunityFramework/Game/DayZGame.c` (`DayZGame.OnEvent`) delegates to
super; COT's `scripts.pbo`, `5_Mission/CommunityOnlineTools/MissionMainMenu.c`
(`MissionMainMenu.OnMissionStart`) delegates to super and obtains its menu.
Dabs' `Scripts.pbo`, `5_Mission/DabsFramework/GUI/MainMenu.c` (`MainMenu.Refresh`)
and Expansion Core's `core_scripts.pbo`,
`5_Mission/DayZExpansion_Core/GUI/MainMenu/MainMenu.c` (`MainMenu.Refresh`)
customize menu presentation through super. Expansion's `MissionMainMenu`
constructor initializes Expansion's game state. No CLI-blocking menu override
was found in CF, COT, Dabs, Expansion Core/AI/Vehicles/Navigation or the loaded
variety packs. No third-party source was extracted or retained. No connect
reissue is installed: it would not resolve the native authentication rejection.

The dev-only test addon traces `[HC Driver] connect initialize load=<n>
game=<n> cli=<bool>`, `entry load=<n> game=<n>`, `returned load=<n> game=<n>`,
`initialized load=<n> game=<n>`, and `session start`, `session fail`, `session end`.
The usual join order is initialize, entry, returned, initialized, session
start; asynchronous session events can interleave. The native
`CGame.Connect(menu, address, port, password)` is `proto native` and cannot be
overridden (a client compile error, build 185), so its result is not traced: a
rejected connection shows as session fail/end. A skipped attempt produces
initialize/initialized without entry. Initialization is logged once, with at most
16 entry/returned pairs and 16 session events per process. CLI values, addresses,
passwords and event payloads are never printed. All overrides delegate to super.
Native compilation and runtime acceptance remain lead checks.

`soak_campaign.CLIENT_JOIN_SECONDS = 360` bounds the join from the BattlEye
launch, including client startup, with the existing 30-second polling interval.
Both `[HC Driver] connect session start` in the client RPT and the server RPT's
`SetClientState` transition `MISSION RECEIVED -> GAME LOADED` for a client identity
must be seen before accepting driver completion or idling. The server's own `__SERVER__`
identity (`MISSION SELECTED -> PLAYER ASSIGNED`) never counts; until soak 185b the check
waited for that line and refused a client that had joined and finished its steps. The earlier `CREATED -> CONNECTED` transition is insufficient: it also
occurs before a version rejection. On timeout the refusal is
`client never joined: <last safe [HC Driver] connect line>` (or `no connect line`).
The existing graceful shutdown and restore path still runs on refusal. If a
process cannot be confirmed stopped, restore remains deferred until it is safe.

Before building, staging or launching, the campaign compares the size and SHA-256
of every PBO in the resolved shared dependency folders (case-insensitive names).
Only PBOs in the actual mod list are read; own addons loaded from the server root
share the same files and are excluded. A match logs `dependency parity: <n> folders ok`.
A mismatch refuses with `dependency mismatch: <folder> (<n> pbo differ; players get
kick 146; rerun friend_install --apply)`. Reconcile dependencies before retrying.
During the join wait a new server kick line immediately refuses with
`client never joined: kicked <code> (<reason>)`; the player prefix and identity
values are removed. Shutdown and restore still run on either refusal.

With the full-client geometry input set, the offline mesh audit reports 110
blocking findings and 505 skips on both this branch and `ddd8c2d1`; the complete
reports match. Its 140 raw findings include 30 accepted triangle-cost findings.
This is a pre-existing placement/mesh audit failure, separate from soak joining.

## Scripted client without a person (2026-11-24)

Two runs drive one real client with the dev-only test addon, so nobody has to play
(docs/tools/AUTOPLAYER.md):

- the soak campaign (`python3 -B -m tools.testing.soak_campaign run`) stages the test
  profile and runs every phase, now including `mission` (on foot into a published
  mission zone from outside);
- the release gate's client step (`python3 -B -m tools.release.release_gate ...`,
  `--client-mode scripted`, the default) runs the R3 route only: the M map with group
  controls, the inventory, the admin window, then one AI site radius and one published
  mission zone, entered from outside. The gate leaves the server installation untouched;
  the test addon loads on the client only (docs/tools/RELEASE_GATE.md).

Both use the same join path as the campaign above: dependency parity before anything
starts, the BattlEye launcher once the server logs `Player connect enabled`, a graceful
client close before the server and restore only once both client images are gone. The
local client must be on the admin allowlist of the profile in use for the admin window
step; otherwise that step logs `result=refused` and the R3 admin signal stays absent.
Read the result from the `[HC Driver] step=` lines in the client RPT: an `enter` step
ends `result=ok detail=server-confirmed zone=<site|mission> ...` only when the server's
own radius receipt arrived; `no-published-mission`, `not-confirmed` and `stuck` are
refusals and timeouts, never a pass. Native behaviour of the scripted client is
unverified until the lead's first run.
