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
