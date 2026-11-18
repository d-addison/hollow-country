# Friend server runbook for an AI agent

Audience: an AI coding agent (or a careful human) working on the friend's Windows PC
that hosts the Hollow Country DayZ server. Follow the steps in order. Each step
names what to run, what success looks like and what to do when it fails. The
background and the reasons are in [FRIEND_SERVER.md](FRIEND_SERVER.md).

Status: this is a **test build**. Hollow Country compiles and starts on the
developer's Windows server with one client. Multiplayer and two-client behaviour
are not accepted yet. Report what you see; do not claim a feature works because
a log line appeared.

## Rules for the agent

- **Never ask for, type, read, store or log the Steam password or Steam Guard
  code.** The human operator types them into steamcmd themselves. You may run
  steamcmd in the operator's own terminal and wait.
- Never repack, modify, rename inside, or redistribute third-party Workshop mods
  (CF, COT, Dabs, Expansion, SNAFU, Tactical Flava, RaG, Ambient Animals,
  Survivor Animations, DayZ-Bicycle). Copy them as downloaded.
- Never modify the signed Hollow Country PBOs or their `.bisign` files; a changed
  byte breaks the signature and kicks every player.
- Keep `verifySignatures = 2` and BattlEye on. Do not disable either to "fix"
  a join error.
- Stop the server before any install, rollback or profile copy. Back up first
  (step 3). Never delete the `storage_*` folder (the persistence hive) unless the
  operator asks for a wipe in so many words.
- Keep `serverDZ.cfg` passwords local. Never paste them into chat, issues or logs.
- When a command refuses, read its message and fix the cause. Do not retry with
  force flags, do not hand-edit receipts, and do not copy files around the tool.

## Placeholders

Pick real paths with the operator and set them once per PowerShell session; every
command below uses these variables:

```powershell
$SERVER   = 'C:\DayZServer'
$STEAMCMD = 'C:\steamcmd'
$CONTENT  = "$STEAMCMD\steamapps\workshop\content\221100"
$BUNDLE   = 'C:\HollowCountry\friend-bundle-v1-test-6'
$SRC      = 'C:\HollowCountry\hollow-country'
$BACKUP   = 'C:\HollowCountry\backup-' + (Get-Date -Format 'yyyy-MM-dd-HHmm')
$MISSION  = "$SERVER\mpmissions\dayzOffline.chernarusplus"
```

| Name | Example | Meaning |
| :--- | :--- | :--- |
| `SERVER` | `C:\DayZServer` | the DayZ Server install (contains `DayZServer_x64.exe`) |
| `STEAMCMD` | `C:\steamcmd` | the steamcmd folder |
| `CONTENT` | `C:\steamcmd\steamapps\workshop\content\221100` | Workshop downloads (numeric folders) |
| `BUNDLE` | `C:\HollowCountry\friend-bundle-v1-test-6` | the extracted release bundle |
| `SRC` | `C:\HollowCountry\hollow-country` | a clone of the public source repo (tools only) |
| `BACKUP` | `C:\HollowCountry\backup-2026-11-18` | a new, empty backup folder |
| `MISSION` | `SERVER\mpmissions\dayzOffline.chernarusplus` | the live mission |

## 0. Prerequisites

1. Windows 10/11 x64, 16 GB RAM or more, about 30 GB free disk.
2. Python 3.10 or newer: `py -3 --version`. Standard library only; no pip installs.
3. steamcmd: download it from Valve and unzip it into `STEAMCMD`.
4. Git (optional, for `SRC`) and the GitHub CLI `gh` (optional, for downloads).
5. DayZ Server (Steam app 223350). The operator runs this and types their own
   login:
   ```powershell
   & "$STEAMCMD\steamcmd.exe" +force_install_dir "$SERVER" +login <operator steam name> +app_update 223350 validate +quit
   ```
   Success: `SERVER\DayZServer_x64.exe` exists. Game version must be 1.30.

## 1. Get the release and the tools

```powershell
gh release download v1-test-6 -R d-addison/hollow-country -p "friend-bundle-v1-test-6.zip" -D C:\HollowCountry
Expand-Archive C:\HollowCountry\friend-bundle-v1-test-6.zip -DestinationPath C:\HollowCountry
git clone https://github.com/d-addison/hollow-country.git "$SRC"
git -C "$SRC" checkout v1-test-6
```

Without `gh`, download the zip from the repository's Releases page. Use a new,
empty folder for every bundle version.

Check that the bundle is intact (every file against `bundle-manifest.json`):

```powershell
py -3 -I -c "import hashlib,json,pathlib,sys; b=pathlib.Path(sys.argv[1]); m=json.loads((b/'bundle-manifest.json').read_text()); bad=[f['path'] for f in m['files'] if hashlib.sha256((b/f['path']).read_bytes()).hexdigest()!=f['sha256']]; print('files:',len(m['files']),'bad:',bad or 'none')" "$BUNDLE"
```

Success: `bad: none`. Anything else: download the zip again; do not continue.

## 2. Stop the server

```powershell
Get-Process DayZServer_x64 -ErrorAction SilentlyContinue
```

If it is running, warn players, stop it with the operator's usual method (RCon
`#shutdown` or closing the console window), and wait until the command above
prints nothing.

## 3. Back up

```powershell
New-Item -ItemType Directory "$BACKUP"
Copy-Item "$SERVER\serverDZ.cfg" "$BACKUP\"
Copy-Item -Recurse "$SERVER\profiles" "$BACKUP\profiles"
Copy-Item -Recurse "$MISSION" "$BACKUP\dayzOffline.chernarusplus"
Copy-Item -Recurse "$SERVER\keys" "$BACKUP\keys"
Copy-Item "$SERVER\start-server.bat" "$BACKUP\" -ErrorAction SilentlyContinue
```

The mission copy includes `storage_*` (the hive), so it can be large. Keep the
backup until the operator confirms the new build plays well.

## 4. Remove a previous Hollow Country install (upgrades only)

Skip this on a fresh server. If `MISSION` contains Hollow Country receipts (files
named `*receipt*.json` or a `hollow-country*` folder), roll the old overlay back
first, from the new bundle:

```powershell
cd "$BUNDLE"
py -3 -m tools.package.optional_overlays bundle-rollback --mission "$MISSION"
```

If the new tool refuses because of an older receipt, run the same command from
the previous bundle folder. Rollback restores the friend's own mission bytes; it
does not wipe the hive. Drift (someone edited a file since install) refuses:
show the operator the file it names before going further.

Older test bundles (v1-test-5 and earlier) loaded `@Expansion-Animations` and
missed several mods. The new `start-server.bat` replaces that list; do not keep
the old one.

## 5. Download the Workshop dependencies

Preview, then download with the operator's own login (they type the password into
steamcmd), then copy into the server root:

```powershell
cd "$SRC"
py -3 -m tools.setup.workshop_sync plan --server-root "$SERVER" --workshop-content "$CONTENT" --groups base,snafu,tactical_flava,living_packs,pve_patrols
py -3 -m tools.setup.workshop_sync fetch --server-root "$SERVER" --steamcmd "$STEAMCMD\steamcmd.exe" --steam-user <operator steam name> --groups base,snafu,tactical_flava,living_packs,pve_patrols
py -3 -m tools.setup.workshop_sync install --server-root "$SERVER" --workshop-content "$CONTENT" --groups base,snafu,tactical_flava,living_packs,pve_patrols
```

`install` copies each item into `SERVER\@<Folder>` and its public `.bikey` into
`SERVER\keys`, and writes `hollow-country-workshop-receipt.json`. It refuses a
running server, a private key, a symlink or an overwrite of a different file.
`rollback` removes exactly what `install` added.

If the tool is unavailable, the bundle's `README.txt` lists every
`workshop_download_item 221100 <id>` line for a manual steamcmd session; copy
`CONTENT\<id>` to `SERVER\@<Folder>` under the names below and every `.bikey`
into `SERVER\keys`.

The server and every client load exactly this order:

```text
-mod=@CF;@COT;@DabsFramework;@Expansion-Core;@Expansion-AI;@Expansion-Navigation;@SnafuWeapons;@TacticalFlava;@RaG_Core;@RaG_Immersive_Vehicles;@AmbientAnimals;@SurvivorAnimations;@DayZ-Bicycle;@HollowCountry;@HollowCountryExpansionAI
```

Do **not** add `@Expansion-Animations`: it conflicts with Survivor Animations,
which DayZ-Bicycle needs. Expansion-AI brings its own AI animations.

## 6. Install the Hollow Country mods from the bundle

```powershell
Copy-Item -Recurse -Force "$BUNDLE\@HollowCountry" "$SERVER\"
Copy-Item -Recurse -Force "$BUNDLE\@HollowCountryExpansionAI" "$SERVER\"
Copy-Item "$BUNDLE\keys\*.bikey" "$SERVER\keys\"
Copy-Item "$BUNDLE\@HollowCountry\keys\*.bikey" "$SERVER\keys\"
Copy-Item "$BUNDLE\@HollowCountryExpansionAI\keys\*.bikey" "$SERVER\keys\"
Copy-Item -Force "$BUNDLE\start-server.bat" "$SERVER\"
```

Remove any older `@HollowCountry*` folder first if it holds PBO names that the new
one does not (`Remove-Item` only those two folders, after the backup). Check:
`SERVER\@HollowCountry\addons` has `hollowcountry.pbo` and `hollowcountryanims.pbo`,
each with a `.bisign`; `SERVER\@HollowCountryExpansionAI\addons` has
`hollowcountryexpansionai.pbo` and its `.bisign`.

Players subscribe to **Hollow Country** (Workshop 3841628320) and **Hollow Country
Expansion AI** (3841637854), plus every dependency above. Both are Public
Workshop items. The DayZ launcher offers the missing subscriptions when they join
from the server browser.

## 7. Server profile configuration

```powershell
Copy-Item -Recurse -Force "$BUNDLE\profiles\*" "$SERVER\profiles\"
```

This installs `profiles\HollowCountry\...` (settings, stamina, templates, the
21-site `expansion-ai-sites.json`, infected config) and the Expansion AI files
(`profiles\ExpansionMod\Settings\AISettings.json`, `profiles\ExpansionMod\Loadouts\HollowCountry_*.json`).

Upgrade note: an old `profiles\HollowCountry\expansion-ai-sites.json` with 17
sites must not survive; the copy above replaces it. If the operator keeps their
own file instead, delete it and the server writes the 21-site default from the
PBO on the next start (it never overwrites an existing file).

## 8. Mission overlay

```powershell
cd "$BUNDLE"
py -3 -m tools.package.optional_overlays bundle-plan --mission "$MISSION"
py -3 -m tools.package.optional_overlays bundle-apply --mission "$MISSION" --workshop-dir "$CONTENT"
```

Read the plan output before applying. `bundle-apply` needs the Ambient Animals,
Survivor Animations and Bicycle downloads under `CONTENT`; it rehearses on
scratch, writes backup receipts, then installs the base merge, travel CE and the
living-pack overlays. Success ends with
`HC bundle bundle-apply complete; runtime acceptance pending`. Keep every
receipt and backup it writes. A refusal names the conflicting file or value:
show it to the operator; do not edit around it.

## 9. serverDZ.cfg

Open `SERVER\serverDZ.cfg` and set each key from `BUNDLE\serverDZ-hollow-country.txt`
(replace the existing line, keep the operator's hostname and passwords):

```text
thirdPersonView = 2;
disable3rdPerson = 0;
serverTimeAcceleration = 4;
serverNightTimeAcceleration = 8;
enableCfgGameplayFile = 1;
verifySignatures = 2;
BattlEye = 1;
// inside class Missions { class DayZ { ... }; }
template = "dayzOffline.chernarusplus";
```

Without `thirdPersonView = 2` the server logs a camera WARNING with this fix.

## 10. Network

Allow inbound UDP 2302–2305 (game) and UDP 27016 (Steam query) in Windows
Firewall and forward the same ports on the router to this PC:

```powershell
New-NetFirewallRule -DisplayName "DayZ Server UDP" -Direction Inbound -Protocol UDP -LocalPort 2302-2305,27016 -Action Allow
```

## 11. Start and check the logs

```powershell
cd "$SERVER"; .\start-server.bat
```

Wait 2–4 minutes (the first start writes defaults and the CE loads). Then look in
the newest `SERVER\profiles\script_*.log` and `SERVER\profiles\DayZServer_x64_*.RPT`:

```powershell
$log = Get-ChildItem "$SERVER\profiles\script_*.log" | Sort-Object LastWriteTime | Select-Object -Last 1
Select-String -Path $log -Pattern 'SCRIPT\s+\(E\)' | Select-Object -First 20
Select-String -Path $log -Pattern 'V1 admission feature=|V2 admission feature=' | Measure-Object
Select-String -Path $log -Pattern '\[HollowCountry\] (Invalid settings|Settings rejected|Cannot)'
Select-String -Path $log -Pattern '\[HC Doors\] ready|\[HC Reach\] started|camera|WARNING' | Select-Object -First 20
```

Expected:

- No `SCRIPT (E)` lines from Hollow Country. `ManType`/`DayZAnimalType` config
  errors and `tf_bipodsway` spam come from vanilla or third-party mods; they also
  appear without Hollow Country and are not ours to fix.
- One `[HollowCountry] V1 admission feature=` or `V2 admission feature=` line per
  feature, most ending `result=admitted` or
  `admitted unverified: <gate> has no recorded native verdict` (normal for this
  test build).
- No `Invalid settings` or `Settings rejected` lines. If one appears, the
  message names the problem in `profiles\HollowCountry\settings.json`; restore the
  bundle copy.

A compile error stops the server at startup with a script error box or an
`SCRIPT (E)` block naming a file. Copy the first 40 lines of that block (no
passwords, no Steam IDs) into a GitHub issue on `d-addison/hollow-country`.

## 12. First join

The operator joins from the DayZ launcher server browser (or Direct Connect to
the public IP, port 2302) with the same mods subscribed. A signature kick means a
client is missing or has a different version of one mod: re-subscribe, never
lower `verifySignatures`.

Expansion map and marker options (2D/3D markers, the marker list) default **on**.
A player who sees them off has an old personal Expansion `settings.bin` in their
own DayZ profile; they turn the options on in the in-game Expansion settings
menu. Server-side map settings live in `MISSION\expansion\settings\MapSettings.json`,
which Expansion-Navigation creates on its first start with everything on.

## Turning features off

- A V2 feature: set its `Enable*` value to `false` in
  `profiles\HollowCountry\settings.json`, then restart.
- A V1 experimental feature: create an empty file
  `profiles\HollowCountry\acceptance\<gate>.disable` (the gate name is in its
  admission line), then restart. Delete the file to turn it back on.
- Stamina: `profiles\HollowCountry\stamina.json` (`ContinuousExertionScale`,
  `RecoveryScale`, each 0.05–5.0).

## Rollback

With the server stopped:

```powershell
cd "$BUNDLE"; py -3 -m tools.package.optional_overlays bundle-rollback --mission "$MISSION"
cd "$SRC";    py -3 -m tools.setup.workshop_sync rollback --server-root "$SERVER"
```

Then restore `serverDZ.cfg`, `profiles`, `keys` and `start-server.bat` from
`BACKUP`. Remove `SERVER\@HollowCountry` and `SERVER\@HollowCountryExpansionAI`.
Rollback never wipes the hive; persisted bikes and animals stay.

## Updating to a later bundle

Repeat steps 1–3, then 4 (rollback with the new bundle), 6, 7, 8 and 11. Players
get the new Hollow Country version from the Workshop automatically. Server and
clients must run the same version.

## Reporting

Report: bundle version, the `bad:` result of step 1, the admission line count,
any `SCRIPT (E)` blocks, and what players saw. Never include passwords, Steam
IDs, IP addresses of players or the operator's home paths.
