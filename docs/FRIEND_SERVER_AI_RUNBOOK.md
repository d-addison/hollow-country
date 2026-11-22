# Friend server runbook for an AI agent

Audience: an AI coding agent (or a careful human) working on the friend's Windows PC
that hosts the Hollow Country DayZ server. Follow the steps in order. Each step
names what to run, what success looks like and what to do when it fails. The
background and the reasons are in [FRIEND_SERVER.md](FRIEND_SERVER.md).

Status: this is a **test build**. Hollow Country compiles and starts on the
developer's Windows server with one client. The current combined build still needs DayZDiag, normal PBO/server and
single-client gameplay acceptance. Report what you see; do not claim a feature works because
a log line appeared.

## Rules for the agent

- **Never ask for, type, read, store or log the Steam password or Steam Guard
  code.** The human operator types them into steamcmd themselves. You may run
  steamcmd in the operator's own terminal and wait.
- Never repack, modify, rename inside, or redistribute third-party Workshop mods
  (CF, COT, Dabs, Expansion, SNAFU, Tactical Flava, RaG, Ambient Animals).
  Copy them as downloaded.
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

## Easy path (try this first)

The bundle ships a guided installer. From the extracted `BUNDLE` folder:

```powershell
cd "$BUNDLE"
.\install-hollow-country.bat                 # dry run: shows the ten steps, changes nothing
.\install-hollow-country.bat --apply         # after reading the dry run, with the server stopped
.\install-hollow-country.bat --check         # any time: verifies mod folders, keys, meta.cpp ids, -mod order
```

It checks the server folder and that the server is stopped (read only; it never stops anything), downloads the
Workshop dependencies through steamcmd, copies the mod folders and keys, applies the mission overlay with
`bundle-plan` then `bundle-apply`, installs the map overlay layers (step 6, `map_overlay validate` then `install`,
server stopped), copies the profiles, merges only the Hollow Country lines into `serverDZ.cfg` (backup first) and
writes `start-server.bat`.

steamcmd: the installer uses `--steamcmd <path>`, then the path it remembered from an earlier run
(`hollow-country-steamcmd.txt`), then `steamcmd` on PATH, and otherwise asks the operator for the path to
`steamcmd.exe` (or its folder). It always passes `--steamcmd` and an install folder to steamcmd, so downloads land
beside steamcmd and not in whatever folder it was started from. The operator types the Steam login name only
(no spaces); steamcmd asks for the password and the Steam Guard code itself, and you never see them. A name with
spaces or other characters is refused (`steam_user_invalid`) and is never echoed.

Only files that `bundle-manifest.json` lists are installed. Useful options: `--skip overlays-map` leaves the map
overlay layers out (`--skip` also takes `workshop`, `mods`, `overlay`, `profiles`, `cfg`, `launcher`); `--check`
also reports whether the map overlay receipt is present and intact (`missing_map_overlay`,
`damaged_map_overlay`, `outdated_map_overlay`). An intact receipt for the same layer set is already installed; for a
different layer set the installer asks the operator, rolls the old one back, then installs the new one.

**Never upload or share `hollow-country-install-backups\`.** It contains local passwords and an atomic
`<run>/run-journal.json`. A late refusal restores overwritten files and both overlays and removes files created
by that run, then says “rolled back: the server is as it was before this run”; saves and `storage_*` stay untouched.
If an undo fails, it stops and lists every remaining operation as `rollback_pending`. A crash is reported by
read-only `--check` as `install_interrupted` (or `rollback_pending` during undo). Keep the server stopped, fix the
reported cause, and rerun with `--apply`: recovery finishes before installation resumes. Backups are retained;
Steam download caches stay outside this server rollback. A prompt-time `serverDZ.cfg` edit is preserved.

### Upgrade preflight and recovery (#312)

The process check scopes readable Windows `ExecutablePath` values to the target
server folder. An unrelated server in another folder does not block. An unreadable
image path remains unknown; stop the target yourself before using
`--assume-stopped`, which skips the process check entirely. The installer never
stops or kills processes.

`--plan-only` and `--check` now detect receipt-owned `db/globals.xml` drift before
an upgrade; `--apply` refuses before its first write. The output includes exact
PowerShell commands to create an absent `.hc-recovery` mission copy, undo the
installed upper layers, and run `restore-originals` on that copy. Run each command
only after the preceding one succeeds. Keep the original mission as the backup.
This recovery still restores original globals: save operator tuning (including
`IdleModeStartup`, `IdleModeCountdown`, `RespawnTypes` and `RespawnLimit`) and
reapply reviewed values after installation. Automatic globals carry-forward is
not implemented. Never remove receipts to bypass drift. The full recovery and
mission swap procedure is in step 4 below.

Untouched profile defaults with CRLF or a UTF-8 BOM now match shipped history and
upgrade with a backup; other edits are kept. New bundles write profile JSON as
LF regardless of checkout. The profiles step ships complete Groups and infected
LOD settings and adds missing fields to existing JSON objects with a backup.
Existing values, including explicit opt-outs, arrays and schema versions, stay
unchanged; the native loader performs supported schema migrations. Invalid JSON
is preserved with a warning and requires manual repair. Expansion AISettings
retains its existing merge policy for HC-owned fields.

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
| `SRC` | `C:\HollowCountry\hollow-country` | a clone of the private source repo (tools only) |
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
prints nothing. Avoid killing the process (Task Manager, `Stop-Process`): a kill
during a save leaves `profiles/HollowCountry/*.json.tmp` files. The world store
finishes or drops an interrupted save on the next start and logs
`world interrupted save recovered`; other stores stay quarantined until you move
their `.tmp` file aside with the server stopped.

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
first. If weapon CE deltas were installed, undo them in reverse order before
`bundle-rollback` (the example assumes step 8a's SNAFU then Tactical Flava order):

```powershell
cd "$SRC"
py -3 -m tools.package.tactical_flava_optional rollback --target "$MISSION"
py -3 -m tools.package.snafu_optional rollback --target "$MISSION"
```

Skip commands for packs whose CE delta was never installed. Then, from the new bundle:

```powershell
cd "$BUNDLE"
py -3 -m tools.package.optional_overlays bundle-rollback --mission "$MISSION"
```

If the new tool refuses because of an older receipt, run the same command from
the previous bundle folder. Rollback restores the friend's own mission bytes; it
does not wipe the hive. Normal `bundle-rollback` refuses drift (edits made since
install). To discard tuning in receipt-owned files and upgrade safely, keep the
step 3 backup and work on a separate mission copy with the server stopped. Undo
optional weapon deltas first as above; map-overlay and other independent receipts
keep their own rollback commands. Roll the map overlay back before bundle
recovery (see **Rollback** below), since it shares `cfggameplay.json`, and roll the
infected mix back (`py -3 -m tools.package.infected_variety rollback --mission ...`),
since it shares `db/events.xml`; `restore-originals` refuses while either is installed. Then use
the new tool from the private checkout:

```powershell
$RECOVERY = "$BACKUP\mission-recovery"
Copy-Item -Recurse "$MISSION" "$RECOVERY"
cd "$SRC"
py -3 -m tools.package.optional_overlays restore-originals --mission "$RECOVERY"
```

Use a new, absent `RECOVERY` directory. `restore-originals` rehearses the entire
bundle recovery on scratch before writing the copy. It reports every drifted
receipt-owned file and restores byte-exact originals only after checking their
recorded SHA-256. It undoes loot boost, optional packs, travel and bundle layers
in reverse order, removing only their owned generated files and receipts. Unknown
managed files, unreadable receipts or a mismatched original hash refuse recovery;
keep the backup and reconcile manually. Files outside those receipts, including
`storage_*`, stay untouched. This command deliberately discards **all tuning in
owned files**, including `db/globals.xml`; save the desired values separately.

After success, move the current mission aside without deleting it, place the
recovered copy at `MISSION`, then continue steps 6–8a. Reapply reviewed tuning
after the new overlays are installed. Never delete receipts to bypass a refusal.
Recovery uses file-by-file atomic replacements, not a whole-mission transaction;
keep the server stopped and do not edit the copy concurrently. An I/O failure can
leave a partial recovery: preserve it and the backup for reconciliation.

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

Players must subscribe to both **Expansion-Licensed** (2116157322) and
**Expansion-Vehicles** (2291785437). The following order comes from
`tools/setup/workshop_mods.json` (ascending rank). The server and every client
load exactly this order:

```text
-mod=@CF;@COT;@DabsFramework;@Expansion-Core;@Expansion-Licensed;@Expansion-Vehicles;@Expansion-AI;@Expansion-Navigation;@SnafuWeapons;@TacticalFlava;@RaG_Core;@RaG_Immersive_Vehicles;@AmbientAnimals;@HollowCountry;@HollowCountryExpansionAI
```

Do **not** add `@Expansion-Animations`: Expansion-AI brings its own AI animations.
Survivor Animations and DayZ-Bicycle are retired (2026-11-22); remove `@SurvivorAnimations`
and `@DayZ-Bicycle` from any older `-mod` line.

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

This installs `profiles\HollowCountry\...` (settings, stamina, templates,
`expansion-ai-sites.json`, `expansion-ai-localities.json`, infected config) and the
Expansion AI files (`profiles\ExpansionMod\Settings\AISettings.json`,
`profiles\ExpansionMod\Loadouts\HollowCountry_*.json`). Runtime cursor files
are excluded from the friend bundle.

The server provisions missing site/locality policies from its PBO with
`HCProfileDefaults.Ensure`; existing operator files are never overwritten at
startup. The profile copy above is an explicit replacement, so retain any
operator edits in the step 3 backup. Keeping a customized 17-site, 21-site or
larger policy is supported: unknown catalog site IDs are skipped with one
startup diagnostic, and added operator sites receive single-site localities.

`profiles\HollowCountry\expansion-ai-localities.json` maps locality IDs to site
IDs and controls rotation timing. The shipped mission source is
`mission/hollow-country/ai/localities.json`, mirrored byte-for-byte in the addon.
`PageSize=0` uses the live `HCAILimits.MaxActiveSites` cap; legacy nonzero page
values also cannot shrink coverage below that cap. All eligible sites in a
visited locality can enter the page, including several sites in the same town.
When all sites fit the cap, their empty controllers remain armed across
rotation intervals. Beyond the cap, the durable cursor provides fair opportunities. Site-less
localities remain pending route/access work, with bounded pending logging;
they do not create speculative routes or imply observed world coverage.

With the server stopped and backed up, deleting `expansion-ai-localities.json`
adopts the shipped catalog on next startup. It does not reset AI caps, the site
policy, raid cooldowns, ownership or loot/cache journals. Set its `Enabled` to
`false` to use legacy per-site controllers instead of rotation.

A v1-test-14 leftover (temporary file deleted before origin was written, followed
by a shipped-policy change) can safely refuse adoption with
`[HC AI Defaults] refused file=<relative> reason=operator_modified` or
`reason=operator_unprovenanced` or `reason=legacy_backup_conflict`.
Stop the server, back up any operator edits,
and delete the affected profile policy file to adopt the current shipped image
on next startup.

The following files under `profiles\HollowCountry\` hold only rotation history:

- `expansion-ai-locality-rotation.json`: current cursor, per-locality site cursor,
  pending/observed coverage and retry history.
- `expansion-ai-locality-rotation.pending.json`: staged cursor checkpoint. A
  leftover file is logged and discarded on restart; load tries the primary,
  then `expansion-ai-locality-rotation.bak.json`.
- `expansion-ai-locality-rotation.bak.json`: preceding checkpoint, used if the
  primary is absent or invalid.

Deleting only the primary allows backup recovery. Deleting only the pending
file discards the interrupted checkpoint. To reset fairness/history completely,
stop the server, back up, then delete all three rotation files; next start
creates fresh cursor history. This never resets raid/loot state or proves
coverage. A cursor clock/save fault disables rotation for that process and
continues with legacy per-site controllers, preserving existing patrols.

Look for `[HC Plan] HC-18 localities=... page=... oldest_pending=... cursor=...`
at startup and adapter readiness. `state=off:rotation_fault_legacy_sites_retained`
means the cursor path fell back; `catalog_unknown_site skipped=...` reports
catalog/operator drift. Check for `route qualified`, cached route refusals and
normal native patrol creation/spawn logs as separate stages. Route outcomes use
the existing route cache; cached refusals survive restart. Successful routes
still rebuild geometry because that cache does not store snapped/skipped
waypoints. Native qualification, normal PBO/server behavior, single-client
observer/combat cleanup and restart recovery remain **runtime acceptance pending**
for this change. Larger-load performance is unmeasured and outside acceptance.

### Groups admission diagnostics (#242)

`operator/settings.json`'s `EnableGroups=true` is the global preference. The
service also requires `profiles/HollowCountry/Groups/settings.json` to load and
validate with `Enabled=true`. In both build `172e84d` and main `42761000`,
`HCGroupModule.IsEnabled` returns false for an unreadable/invalid local configuration
or a local opt-out. The old readiness derivation then reports the ambiguous
`not_started_or_disabled`; that is effective admission, not the global preference.

This revision distinguishes `core_groups_disabled`, `groups_settings_disabled`
and `groups_settings_unavailable_or_invalid` (a refusal). For the last reason,
look for `settings_missing_baseline_fields`, parse/read/recovery errors, or settings
validation failures. The loader requires the baseline keys, restores the supported
missing `ShareDiscovery` default, and migrates valid schema 1 to 2. Preserve local
settings and state; do not delete them to force startup. The issue report contains
no local settings values or specific loader refusal, so it cannot establish which
local gate failed. Enabling the global preference alone does not prove a bug in
the group service. Check a new server boot for the specific reason before changing
configuration. Native compilation, boot and a Groups exercise on one server with
at most one client remain pending.

## 8. Mission overlay

```powershell
cd "$BUNDLE"
py -3 -m tools.package.optional_overlays bundle-plan --mission "$MISSION"
py -3 -m tools.package.optional_overlays bundle-apply --mission "$MISSION" --workshop-dir "$CONTENT"
```

Read the plan output before applying. `bundle-apply` needs the Ambient Animals
download under `CONTENT`; it rehearses on
scratch, writes backup receipts, then installs the base merge, travel CE and the
living-pack overlays. Success ends with
`HC bundle bundle-apply complete; runtime acceptance pending`. Keep every
receipt and backup it writes. A refusal names the conflicting file or value:
show it to the operator; do not edit around it.

## 8a. Add the optional weapon packs to CE

Loading the Workshop mods in step 5 does not add their weapons to loot. After
`bundle-apply`, while the server is still stopped, use the private checkout's
**tools revision containing GitHub #161** for the commands below. Older tools
from `v1-test-6` refuse the bundle's three CE registrations; update the tools
checkout to the supplied fixed revision first. Keep the signed PBOs unchanged.

Use a fresh output directory outside the checkout for every attempt. The vanilla
Addons path must contain the installed game's own PBOs used for the ammo checks;
use the server's `Addons` directory below if present, otherwise set it to the
matching local DayZ install's `Addons` directory.

```powershell
$CEWORK = 'C:\HollowCountry\weapon-ce-' + (Get-Date -Format 'yyyy-MM-dd-HHmmss')
$VANILLA_ADDONS = "$SERVER\Addons"
cd "$SRC"
py -3 -m tools.package.snafu_optional verify --install "$CONTENT\2443122116" --out "$CEWORK\snafu-verification.json"
py -3 -m tools.package.tactical_flava_optional verify --install "$CONTENT\2646817942" --vanilla-addons "$VANILLA_ADDONS" --out "$CEWORK\tactical-verification.json"
```

Verify against the Workshop content folders above. The server copies contain
`addons`, `keys` and mod metadata, but omit the vendor `Readme_Terms/`,
`XML_and_Clasnames/` and `extra files/` folders. Those copies therefore fail with
`vendor-types-missing` / `terms-file-missing`; loading their PBOs does not supply
the verification evidence.

Both reports must say `verified` with zero missing/unverified classes. A refusal
or unverified report stops this step; read the reasons and reconcile the installed
copy or allowlist. Keep these reports outside Git; never copy Workshop assets or
verification output into the source checkout.

Generate and install SNAFU first, then generate Tactical Flava against the mission
**after** SNAFU is installed. Each delta pins its source bytes, so generating both
before installing either will cause the second install to refuse.

```powershell
py -3 -m tools.package.snafu_optional generate --source "$MISSION" --report "$CEWORK\snafu-verification.json" --out "$CEWORK\snafu-delta"
py -3 -m tools.package.snafu_optional install --delta "$CEWORK\snafu-delta" --target "$MISSION"
py -3 -m tools.package.tactical_flava_optional generate --source "$MISSION" --report "$CEWORK\tactical-verification.json" --out "$CEWORK\tactical-delta"
py -3 -m tools.package.tactical_flava_optional install --delta "$CEWORK\tactical-delta" --target "$MISSION"
```

For one pack, run only its verification, generation and installation commands.
Success leaves the bundle's three CE folders plus one folder per weapon pack
(five total with both packs). Known managed registrations are admitted, but a
class already in stock or any registered types file still refuses. Unknown CE
folders are named for explicit operator reconciliation; do not remove the guard
or hand-edit around it. Static verification and installation leave DayZDiag,
normal server/PBO and single-client acceptance pending.

Rollback is last installed first: Tactical Flava, SNAFU, then the bundle (see
Rollback below). If the packs were installed in the opposite order, reverse their
rollback commands. Roll back any later mission changes before these layers.

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
Select-String -Path $log -Pattern '\[HC Ready\] module=(Doors|Reach) |camera|WARNING' | Select-Object -First 20
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

## Seeing the AI (admin map, snapshot file, log)

Source implemented, runtime acceptance pending: nothing below has been observed in
DayZ yet. The addon lists every live Expansion AI unit, including patrols from
`AIPatrolSettings.json`, as layer `ai-units`. The older layer `ai` still shows only
HC-site patrols and their routes.

**Add yourself as an admin.** The server creates `profiles\HollowCountry\admins.json`
containing `{"PlainIds":[]}` on first start (`EnableAdminMap` must stay `true`).
Stop the server, put your Steam64 id in it, for example
`{"PlainIds":["7656119XXXXXXXXXX"]}` (at most 32, no duplicates), start the server
again. The log prints `[HC Admin] allowlist count=1`. Anyone not on the list gets
nothing; AI positions are never sent to other players.

**In game.**
1. Join the server and press **Pause** (Pause/Break). It is the input "Hollow Country
   Admin Test Kit and Map", rebindable in Controls. The window opens only after the
   server accepts you.
2. Press **Refresh** (snapshot). The server captures over a few seconds and the marks
   appear, at most once per 5 s per admin.
3. In the layer list, select `ai-units` and press the toggle button to show or hide it.
   Hover a mark: `ai-units: <faction> x<size> <state> [<source>] | source=... faction=...
   group=<id> size=<n> state=patrol|combat weapon=<class> name=<group name>`.
   `source=hc-site` is a group the HC site director owns (group name `HC:<site>`);
   `expansion` is every other Expansion AI group. `npc` marks stationary Expansion NPCs.
4. To confirm movement, press Refresh again a minute later and compare positions.
   One capture shows at most 128 units. If more are alive the window moves on at
   each capture, so keep refreshing to page through all of them.

**Snapshot file and local web map.** With `EnableDebugSnapshot` true the same layer is
written to `profiles\HollowCountry\debug\snapshot.json`. A capture starts 20 s after
the previous one ended (fixed) and then runs one contributor per core tick, so with the
default `TickIntervalMs` 1000 the file refreshes about every 30 s; the 20 s is not a
setting and only `TickIntervalMs` (500 to 10000) changes the rest. View it with the
read-only local viewer (see `tools/webmap/README.md`, #122):
`python3 -m tools.webmap.server --snapshot '<profile>/HollowCountry/debug/snapshot.json'`
and open `http://127.0.0.1:8765/`. It lists every layer in the file, so `ai-units` is a
checkbox there too.

**Log without a map.** The server prints every 5 minutes (first after 60 s):
`[HC XAI] live groups=N units=M expansion=a hc=b`. `groups` is groups with at least one
live AI, `units` the live AI bodies, `expansion` and `hc` split the groups by source.
`groups=0 units=0` long after players have been near patrol areas means nothing is
spawned (Expansion dynamic patrols spawn only near players). At start the log also says
`[HC XAI] live map contributors registered layer=ai-units`; without that line
`EnableDebugSnapshot` is off or the addon is not loaded.

**What COT can and cannot show** (from the installed COT scripts, read only):
- The COT map (`JMMapForm`) draws connected players, loot markers, markers and the safe
  zone; it has no AI.
- COT ESP has a "Player AI" view type (any man that is not a player). It draws only
  objects the admin's client has streamed, within the ESP radius around the admin
  (default 200 m, at most 1000 m), so it finds AI near you, not on the whole map. Enable
  the ESP "Player AI" permission for your role. Whether Expansion AI is classified there
  rather than as a player is not observed.
- Expansion AI lets a COT admin spectate one AI, which needs the AI's object in view.

### `[HC XAI] caches refused reason=backup_only_rollback`

The site cache journal is `HollowCountry/expansion-ai-caches.json` under the server
profile, with its crash-recovery intent `expansion-ai-caches.json.tmp` and the prior
committed image `expansion-ai-caches.json.bak`. At start, when neither the primary
nor the `.tmp` is a whole image and a `.bak` exists, the server refuses to load the
journal rather than guess that the older `.bak` matches the crates in the world. The
log line is printed once; the site cache feature stays off for that run and nothing is
reseeded or refilled from the old backup. The server cannot reset itself; recover by
hand with the server stopped:

1. Inspect the three files together (size and modified time). Keep a copy of all three
   in a folder outside the profile before changing anything.
2. If the primary or `.tmp` is a whole JSON object with `"SchemaVersion": 1` and a
   `Rows` list that is merely unreadable to the loader for another reason, fix or
   restore that file instead; do not use the `.bak`.
3. To accept the rollback: copy `expansion-ai-caches.json.bak` over
   `expansion-ai-caches.json` and delete the `.tmp`. The journal returns to the prior
   committed save, so a cache looted or refilled since then may be seeded or timed
   again.
4. To start the journal fresh: move the primary, `.tmp` and `.bak` out of the profile.
   Site caches are seeded again as the sites activate.
5. Start the server and look for the absence of the refusal line. The recovery path is
   source-built only; no native or soak evidence exists for it.

### `[HC Expansion AI] loadout default refused ... reason=torn_preserve_slots_full`

A shipped loadout file in `profiles\ExpansionMod\Loadouts\` that the server wrote and
that was torn by a crash (half-written, with our `<name>.json.hcdefault.tmp` intent still
beside it) is copied aside before it is replaced. The copy goes to the first free slot
`<name>.json.hcdefault.torn-0` to `.torn-4`. The server never deletes these copies, so
after five recoveries of the same loadout every later start refuses that loadout with the
reason above and the loadout stays missing. The other loadouts and the rest of the boot
are not affected. Clean up by hand with the server stopped:

1. Look at the `.torn-N` files for that loadout (size and modified time). They are
   evidence of earlier crashes; keep them outside the profile if you want them.
2. Delete (or move out of the `Loadouts` folder) the `<name>.json.hcdefault.torn-0` to
   `.torn-4` files for the refused loadout only. Do not touch `<name>.json` if it is a
   whole file, and do not touch files that are not ours.
3. Start the server. The loadout is recreated from the shipped default and the log shows
   `loadout default provisioned`. If it is refused again, a crash is tearing the write
   each start: report the RPT instead of cleaning up again.

An older build wrote a single `<name>.json.hcdefault.torn` file (no number). The current
build ignores it; it can be deleted at any time.

## Turning features off

- A V2 feature: set its `Enable*` value to `false` in
  `profiles\HollowCountry\settings.json`, then restart.
- A V1 experimental feature: create an empty file
  `profiles\HollowCountry\acceptance\<gate>.disable` (the gate name is in its
  admission line), then restart. Delete the file to turn it back on.
- Stamina: `profiles\HollowCountry\stamina.json` (`ContinuousExertionScale`,
  `RecoveryScale`, each 0.05–5.0).

## Rollback

With the server stopped, roll back weapon CE deltas before the bundle. These
commands assume step 8a's order; skip a pack command if its delta was never
installed. If an install failed or was interrupted, inspect its receipt and use
its rollback recovery before undoing earlier layers. Every rollback checks drift
and restores its predecessor's exact bytes; keep receipts until it succeeds.

```powershell
cd "$SRC"
py -3 -m tools.package.tactical_flava_optional rollback --target "$MISSION"
py -3 -m tools.package.snafu_optional rollback --target "$MISSION"
cd "$BUNDLE"; py -3 tools/package/map_overlay.py rollback --target "$MISSION"
cd "$BUNDLE"; py -3 -m tools.package.optional_overlays bundle-rollback --mission "$MISSION"
cd "$SRC";    py -3 -m tools.setup.workshop_sync rollback --server-root "$SERVER"
```

Roll the map overlay back before the bundle: it patched the same `cfggameplay.json`, and the mission rollback refuses
while it is in place. Both rollbacks are byte-exact. Then restore `serverDZ.cfg`, `profiles`, `keys` and `start-server.bat` from
`BACKUP`. Remove `SERVER\@HollowCountry` and `SERVER\@HollowCountryExpansionAI`.
Rollback never wipes the hive; persisted bikes and animals stay. If bundle rollback
refuses operator tuning, use step 4's `restore-originals` recovery on a separate
backed-up mission copy after undoing the weapon deltas and map overlay above.

## Updating to a later bundle

Repeat steps 1–3, then 4 (strict rollback or the documented `restore-originals`
recovery), 6, 7, 8, 8a (if wanted)
and 11. Players get the new Hollow Country version from the Workshop automatically. Server and
clients must run the same version.

## Reporting

Report: bundle version, the `bad:` result of step 1, the admission line count,
any `SCRIPT (E)` blocks, and what players saw. Never include passwords, Steam
IDs, IP addresses of players or the operator's home paths.

### Server report

After a play session, from `BUNDLE` run `.\server-report.bat` (or
`py -3 -m tools.setup.server_report --profiles "$SERVER\profiles"`). It reads the newest server `.RPT` and the
Hollow Country profile state (counts only) and writes `hollow-country-report-<UTC date-time>.md`: summary on top,
build and version, the `-mod` list, deduplicated `[HC ...]` lines, every `SCRIPT (E)` error with context,
`[HC Refusal] refused` (and older `[HC Search Houses] refused`) reason counts, AI lines, whether `Player connect enabled` was logged, crash and
minidump presence and Central Economy lines. It removes Steam64 ids, BattlEye GUIDs, IP addresses and ports, player
names on connect and disconnect lines, Windows user paths and any line that mentions a password, an admin
remote-console setting or a key, and it never writes more than 512 KB. Read the file once, then upload that file
only, in one of two ways:

1. Open a GitHub issue titled `Server report <date>` on `d-addison/hollow-country` using the "Server report"
   template (it adds the `server-report` label) and drag the `.md` file onto it.
2. Add the file under `reports/friend-server/` on a branch and open a pull request.

Never upload the raw `.RPT`, `.ADM` or `.mdmp` files or anything from the profiles folder. A report shows what the
server logged; it does not show that a feature works for players.

## #331: server crash about 3 minutes after start (v1-test-12 and v1-test-13)

v1-test-12 and v1-test-13 could crash the server a few minutes after start, while
a police supply event created its supply barrel. v1-test-14 creates the barrel in
one step and fixes the crash. **Install it with the normal upgrade (“Updating to a
later bundle”). Do not reset the server, wipe storage or edit any Hollow Country
file by hand.** The upgrade repairs the state the crash left behind by itself.

What the crash left behind: the profile folder
`$profile:HollowCountry/Events/police-cache-stock/` may contain a `<site>.txt` file
(the spent one-time grant) without the matching `<site>.pos` file. Older builds
treat that site as spent forever, so its police supply barrel never comes back.
Leave these files alone.

What v1-test-14 does once, the first time a police event runs at that site:

- If a supply barrel is still on the ground near the site, it keeps the old grant:
  `[HC Events] police grant orphan kept; <site>; reason=barrel_present runtime=PENDING`
- If no barrel is there, it writes a one-time `<site>.repair` marker at the moment
  it grants one new barrel (never earlier, so a restart before that point does not
  use up the repair):
  `[HC Events] police grant orphan repaired; <site>; runtime=PENDING`
  followed by
  `[HC Events] police cache created; <site>; stock=finite; refill=never runtime=PENDING`

The `.repair` marker means the one-time repair allowance is used. It never repeats,
so a repaired site cannot hand out a second barrel. If the server stops after the
marker is written but before the barrel exists, or the barrel cannot be created
(`police_cache_create_failed`), the allowance is still used and no barrel follows.
The repair runs only when a police event at that site needs a new barrel (no usable
police stock is lying nearby), so it may happen minutes or hours after the upgrade,
or not at all while stock lasts. A barrel seen near the site at any point before
the grant cancels the repair for that server run.

Report to the owner: whether the server stays up past 10 minutes, and any of the
lines above from the server RPT (site ids only, no player names).

## #162: police event refusal and unsupported AI weapons

The `coastal-police-source-7` and `inland-police-source-7` suffix is
`INFECTED_CLEAR=7`, not a building-presence objective (`PRESENCE=6`;
`mods/HollowCountry/scripts/3_Game/Events/HCEventRuntimeData.c:10-11`). Both source
positions and the `Land_Village_PoliceStation` class exactly match the installed
stock ChernarusPlus `mapgrouppos.xml`: nearest matching placement distance **0 m**
for each. The supplied local comparison file has SHA-256
`3b85edb5af5839adc440b81f6b57a6b5bd182456759688ce7348b3c7a17dcf44`.
It differs from the original authored source-review hash
`3eeaad9786a73c339f61f6e6ad203f0732e36b88f27333978cc8b4beece9cec4`;
this check establishes the two exact placement tuples, not whole-file identity
with that earlier review. Coordinates, provenance and gameplay search ranges
were retained.

Family 7 requires a live, undeleted `ZombieBase` with our `EEOnCECreate` candidate
signal inside the 60 m ground-centred sphere. A `no_candidate` refusal means that
none passed all those constraints at that instant. The supplied old log cannot
identify whether the sphere was empty, contained only dead/deleting infected, or
contained live infected without the signal. Do not call this a wrong police
anchor, assume CE spawning failed, or create replacement infected to satisfy it.
The candidate flag is deliberately not an authenticated CE allocation receipt
(`HCEventEconomyObservation.c:1-6,33-41`).

The HC refusal now includes `wanted=ZombieBase`, `radius_m=60`, a constraint
(`no_infected_in_radius`, `no_live_infected_in_radius` or
`no_ce_infected_in_radius`) and `nearest_candidate_m`. A number is the nearest
matching nondeleted object **observed inside the query**, including an ineligible
infected; `none_within_60` means no such object was observed within 60 m.
`unknown_query_refused` means no distance was measured. It does not imply a
nearest world object outside the query. Repeated unchanged constraints log once;
a changed constraint or successful recovery logs again. Late native population
remains retryable under the existing roster budget.

At startup, a separate 60 m bounded static-anchor preflight prints
`startup anchors checked=... unbindable=...`, listing each presence mission with a
missing class in the probe, an anchor beyond its 15 m bind radius, or ambiguous
anchors inside 15 m. An unreadable/overflowed probe prints
`startup anchor unresolved` and is not counted as a proven unbindable anchor.
These are observations of static binding constraints at startup, not a promise
that dynamically added objects can never bind. No infected absence is classified
as permanent, and retries remain available. The summary runs once per script
session, outside the repeating roster path.

### Missing-FSM AI weapon containment

**Do not spawn weapons into AI hands via COT. In particular, do not give an AI the
raw vanilla `M249` classname.** Use the bundled validated HC/Expansion loadout
weapons, and select concrete playable weapon classes when testing admin spawns.
If an AI already holds an affected weapon, disengage the encounter, remove that
specific weapon with the operator's normal admin inventory/delete controls, then
replace the actor through the existing managed encounter lifecycle with its
validated loadout. Do not delete the hive, repeatedly respawn the same weapon, or
hand it to a human as a workaround. If safe removal is unavailable, disable the
affected encounter and perform the operator's normal controlled restart. None of
those operations were performed by this source-only task.

Read-only installed-source findings (DayZ 1.30.164289):

- Native `4_World/Entities/Firearms/Machinegun/M249.c:1-3` is an empty subclass of
  `Weapon_Base`. `Weapon_Base.c:55` declares `m_fsm`; `:130` invokes
  `InitStateMachine`, whose default body is empty at `:133`. Without another mod
  implementing an FSM for that class, it has none. Native `:556-568` emits the
  reported save diagnostic for a missing **or nonrunning** FSM. That message
  alone does not prove the pointer was null for every possible weapon.
- Installed Expansion
  `4_World/DayZExpansion_AI/Entities/Weapons/Firearms/Weapon_Base.c:639-666`
  dispatches AI events and dereferences `m_fsm` at `:660` without a null guard;
  abort handling at `:669-684` dereferences it at `:676`. Its AI fire admission
  (`Entities/AI/eAIBase.c:1276-1297`) consults `weapon.CanFire()`, while native
  `Weapon_Base.c:1262-1267` checks chamber/jam/lift/damage, not FSM existence.
  The report's `:666` is a `super` call in this installed snapshot, so exact friend
  package/stack correspondence remains unverified.
- Installed COT
  `5_Mission/CommunityOnlineTools/modules/Object/JMObjectSpawnerModule.c:764-789`
  creates the requested class using `CreateObjectEx`; `:808-820` can move it into
  inventory, including hands. Successful object creation is not proof that the
  requested class implements a playable weapon FSM. No claim is made that COT
  removed a previously valid FSM or that every modded M249 has this defect.

The HC-owned `HCXWeaponGuard.c` link refuses weapon and abort events for AI when
`m_fsm` is null, before calling downstream handlers. It logs
`[HCX Weapon] ... reason=missing_fsm; weapon=<class>` once per weapon on the server.
Healthy AI and human dispatch retain downstream return values. A later nonnull
FSM can resume dispatch; the guard never constructs an FSM, drops or deletes an
item, changes ammunition, or edits third-party sources. This contains the
reported null-FSM event path; it does not repair an unsupported weapon or certify
all other third-party weapon paths. The actor may keep attempting the refused
action until the operator removes the weapon.

Inspected PBO SHA-256 values (not redistributed):

- Expansion `ai_scripts.pbo`:
  `b5a3d9e71d41e6bb4c9b2721e389b00920ffe8679c72e3b6fe3bacc90e89e2e2`.
- COT `scripts.pbo`:
  `f89fe49e0b3a44441154093e84a75c9e1119754c2d959a0196e09efa3cc8d76f`.

### Draft upstream report — not filed

Title: AI weapon event dispatch dereferences missing FSM for admin-spawned vanilla M249

Observed by friend operator on Hollow Country v1-test-7: an
admin-spawned M249 later held by eAI produces repeated `NULL pointer to instance`
errors in Expansion `weapon_base.c:666` on fire ticks; spawn also reports
`[wpnfsm] SaveCurrentFSMState: weapon without FSM`. Exact weapon classname,
friend dependency versions/hashes and complete sanitized stack still need capture.

Source diagnosis: native `M249 : Weapon_Base` has no FSM initializer; the base
initializer is empty. Installed Expansion AI `Weapon_Base.c:660` and `:676`
dereference `m_fsm` without checking it; `eAI_CanFire` does not test FSM presence.
The installed line 666 is a super call, so version/stack matching is pending.
COT can create a requested class and move it to hands without establishing that
it has a functioning weapon FSM. This identifies a guardable failure path;
reproduction and the exact creator/config interaction remain to be verified.

Suggested investigation: reject unsupported/no-FSM weapons before AI selection
or event dispatch; emit a bounded diagnostic and leave inventory handling to the
provider. Verify normal event/abort semantics and a supported rifle regression.
Reproduce on a disposable server using the exact friend versions, raw `M249`
versus a known supported rifle, with one client. HC has a local downstream
containment guard; no Expansion/COT files were modified or repacked. No upstream
issue was filed.

### Offline evidence and pending acceptance

Banso spec/plan/tasks for this follow-up are local planning artifacts under
`docs/specs/162-followups/` (ignored by repository policy). Canonical planning
files absent from this confined worktree were read from the primary checkout;
active session constraints take precedence. Banso status was unavailable because
its configured clone-root is read-only in this run; no lifecycle dispatch ran.

RED, before implementation:
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_162_followups -v`
→ `Ran 9 tests ... FAILED (failures=10)` (including subtests).
The failures included missing diagnostic fields/startup summary and
`missing authored HCX missing-FSM guard`.
Review RED for unreadable query/ground diagnostic cases:
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_162_followups.BindingDiagnostics.test_unreadable_startup_query_is_unknown_rather_than_proof_of_bad_anchor tests.unit.test_162_followups.BindingDiagnostics.test_unreadable_ground_still_identifies_the_wanted_class -v`
→ `Ran 2 tests ... FAILED (failures=2)`.

GREEN after implementation, same follow-up module command:
`Ran 11 tests ... OK`. Explicit synthetic collaborators execute the authored
Enforce bodies; an optional local read-only map test checks stock placements.
Native math/super/cast seams are explicit and do not simulate engine acceptance.

Pending: DayZDiag compilation, signed normal PBO/server reproduction with the
friend dependency set, supported weapon/abort regression, late native CE
population and candidate-flag observation at both sites, startup geometry
confirmation, and single-client replication/visibility tests. Offline passes do not
enable production or accept an unrun engine experiment. Performance at 3–6
players remains unmeasured.

Final validation commands and actual results for this source change:

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_162_followups tests.unit.test_event_police tests.unit.test_event_sites tests.unit.test_v1_events_behavior tests.unit.test_hcx_self_defence -v`
  → `Ran 133 tests ... OK`.
- `python3 -B -m tools.validate.enforce_lint`
  → `enforce_lint: pass findings=144 new=0 stale=0 native=yes`.
- `python3 -B -m tools.validate.hygiene` → `valid: true`.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit`
  → `Ran 5611 tests in 444.124s ... OK (skipped=1, expected failures=3)`.
- In-memory authored-only PBO pack/parse roundtrips succeeded for both addons:
  255 core files and 23 Expansion-adapter files, including `HCXWeaponGuard.c`.
  This is package-format validation, not signed/native runtime testing.

No debug/admin/snapshot contributor files changed. No network, Git metadata
mutation, third-party rewrite, public upload or DayZ/Windows process control was
used. The operator must still collect the missing native evidence above.
