# P0 inventory — 2026-11-16

Status: inventory observed; game behavior and P0 completion **pending**.
Both official installations are now present in the registered D: Steam library.

| Item | Evidence |
|---|---|
| Client root | `G:\SteamLibrary\steamapps\common\DayZ` |
| Steam manifest | app 221100, build ID 26403755, StateFlags 4 |
| DayZ_x64.exe | 25,956,920 bytes; file 1.30.164.289; product 1.30.164289.70 |
| DayZDiag_x64.exe | 28,775,480 bytes; same versions |
| Tools | `D:\SteamLibrary\steamapps\common\DayZ Tools`; app 830640, build 26405911, StateFlags 4; AddonBuilder, BankRev and signing executables present |
| Server | `D:\SteamLibrary\steamapps\common\DayZServer`; app 223350, build 26220720, StateFlags 4; executable version 1.30.164.289, product 1.30.164289.70; stock ChernarusPlus mission present |
| Native scripts | `dta/scripts.pbo`, 14,401,120 bytes; no loose source found; not yet unpacked with official tools |
| CPU | AMD Ryzen 7 9800X3D 8-Core Processor, from /proc/cpuinfo |
| GPU | NVIDIA GeForce RTX 5070 Ti; 16,303 MiB reported, driver 616.92 via nvidia-smi |
| Agent host | WSL2 kernel 6.6.87.2-microsoft-standard-WSL2, x86-64 |
| WSL allocation | 14 visible logical CPUs, approximately 37.2 GiB RAM, 8 GiB swap; physical Windows RAM/OS unknown |
| Space | Initial available: C 135.20 GiB, D 1282.94 GiB, E 367.31 GiB, G 78.43 GiB, workspace 45.14 GiB |

PE version-resource strings were read from local binaries, not inferred from
Steam build ID. The official stable patch notes independently document matching
1.30.164289 on 2026-11-03:
https://dayz.com/article/game-update/dayz-badlands-out-now/dayz-steam-patch-notes

## Reproduction

Read registered library paths from
`/mnt/c/Program Files (x86)/Steam/steamapps/libraryfolders.vdf`; check manifests
`appmanifest_221100.acf`, `appmanifest_830640.acf`, `appmanifest_223350.acf` in each
library. Record only selected version/install fields, not Steam account fields.
Read PE `FileVersion` and `ProductVersion` resource strings and file sizes for
client and diagnostic executables. `/proc/cpuinfo`, `/proc/meminfo`, `statvfs`
and `/usr/lib/wsl/lib/nvidia-smi` establish the listed host observations.

Windows PowerShell launch failed in sandbox and in the approved outside-sandbox
retry, ending `UtilAcceptVsock: accept4 failed 110`. A separate approved
`cmd.exe /c start steam://install/830640` attempt failed identically. No successful
Windows launch, tool installation, server join or game test is inferred.

## Next gate

Establish Windows launch path, Tools project drive
and official extraction; stock local server join and diagnostics; signed normal
PBO load. All CAP engine status levels remain unchanged by inventory alone.
Use shared-host metrics for local tests and recalibrate on friend's destination.
