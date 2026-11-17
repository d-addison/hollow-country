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
