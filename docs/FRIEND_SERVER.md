# Friend server installation

Development target: DayZ Standalone 1.30, ChernarusPlus, 3–6 players. Features
are being built and V2 preferences default on. Native compilation, normal signed
PBO/server tests, client joins, persistence and two-client checks remain pending.
Nothing in a bundle build establishes DayZ behavior or production acceptance.

The server and every client use this ordered list. Subscribe to the original
Workshop items; never repack, modify or redistribute them.

| Item | Workshop ID | Installed server folder |
| :--- | :--- | :--- |
| Community Framework | 1559212036 | `@CF` |
| Community Online Tools | 1564026768 | `@COT` |
| Dabs Framework | 2545327648 | `@DabsFramework` |
| Expansion Core | 2291785308 | `@Expansion-Core` |
| Expansion AI | 2792982069 | `@Expansion-AI` |
| Expansion Navigation | 2792984722 | `@Expansion-Navigation` |
| SNAFU Weapons | 2443122116 | `@SnafuWeapons` |
| Tactical Flava | 2646817942 | `@TacticalFlava` |
| RaG_Core | 3556131153 | `@RaG_Core` |
| RaG Immersive Vehicles | 3105330157 | `@RaG_Immersive_Vehicles` |
| Ambient Animals Pack | 3114410963 | `@AmbientAnimals` |
| Survivor Animations | 2918418331 | `@SurvivorAnimations` |
| DayZ-Bicycle | 2971190303 | `@DayZ-Bicycle` |
| Hollow Country | 3841628320 | `@HollowCountry` |
| Hollow Country Expansion AI | 3841637854 | `@HollowCountryExpansionAI` |

Expansion-Animations is intentionally not loaded: it conflicts with Survivor Animations, which DayZ-Bicycle requires; Expansion-AI brings its own AI animations.

The manifest's `living_packs` group contains Ambient Animals, Survivor Animations
and Bicycle. Select `base,snafu,tactical_flava,living_packs,pve_patrols` for the full
stack. The friend bundle selects these groups by default. Copy public `.bikey`
files to the server `keys` directory. Keep signing private keys outside the bundle.

Build both owned addons with `tools/package/Build-Sign-Verify.ps1`; HCX uses the
`HollowCountryExpansionAI` PBO prefix. The bundle expects signed addons from that
build, with matching public keys:

```sh
python3 -B -m tools.setup.friend_bundle build --mission /private/server/mpmissions/dayzOffline.chernarusplus --profiles /private/server/profiles --mod /private/build/@HollowCountry --addon /private/build/@HollowCountryExpansionAI --server-cfg /private/server/serverDZ.cfg --out /private/friend-bundle
```

The applied source mission supplies only HC-owned overlay files and minimal
core/gameplay changes. Untouched stock files (`init.c`, `db/globals.xml`,
`db/types.xml`, map placement/prototype files, weather files) never ship. Changed
CE rows live in HC overlay directories and registration/default changes live in
`mission-patches.json`; gameplay changes contain only changed leaf values. Optional
pack output and backups are stripped. Missing travel CE or authored optional
overlay sources refuse the build. All authored mission JSON, including the scene
catalog `hollow-country/events/scene-chains.json`, installs at its mission path.
CE building coverage is excluded; rerun its native sampler against the friend's
own mission separately. No sampler input or output is transported.

Install Python 3.10+ on the friend server. Install DayZ Server and obtain the
original dependencies with the friend's own Steam account. Keep numeric folders
under `steamapps/workshop/content/221100` for overlay generation; copy the mods
under the @ names above for the launch script. Copy only our signed @ folders,
public keys, selected profile configuration and `start-server.bat` from the bundle.
Merge the `serverDZ-hollow-country.txt` settings into the friend's own config;
keep passwords local, `verifySignatures = 2`, BattlEye on, and enableCfgGameplayFile.
The template in serverDZ.cfg must name the target mission. Forward UDP 2302–2305
and query UDP 27016. Keep the profile and CE storage outside the bundle/source.

Use the friend's own stock `dayzOffline.chernarusplus`, copied outside Steam and
outside this bundle/source checkout. Stop the server and all mission writers.
From the bundle folder run:

```sh
python -m tools.package.optional_overlays bundle-plan --mission /private/server/mpmissions/dayzOffline.chernarusplus
python -m tools.package.optional_overlays bundle-apply --mission /private/server/mpmissions/dayzOffline.chernarusplus --workshop-dir /steamapps/workshop/content/221100
```

`bundle-plan` previews the authored merge. `bundle-apply` requires all three default
living-pack sources, rehearses the merge and travel/optional plans on scratch,
then writes a backup receipt before any mission file mutation. It installs the
base merge, travel CE and Bicycle/Ambient overlays in that order. Each installer
has its own receipt, including the first installation. Unknown existing overlay
files and conflicting edited values refuse. Interrupted installs remain reversible
using those receipts; preserve every receipt and backup. No stock mission is
replaced wholesale. Do not merge another CE owner for the same class/event.

Rollback with the server stopped:

```sh
python -m tools.package.optional_overlays bundle-rollback --mission /private/server/mpmissions/dayzOffline.chernarusplus
```

Rollback rehearses before changing live files, then undoes optional packs, travel
and the base merge, restoring the friend's own exact bytes. Drift refuses instead
of overwriting changes. It does not wipe the hive or remove persisted bikes or
animals. Restore profile configuration separately from your stopped-server backup.

The action **Tape light to weapon** accepts weapon lights only, consumes tape on
mounting and returns no tape on removal. Handheld flashlights are not accepted.
This is the intended action contract; validate the native action on joined clients.

After the lead's Windows compile, inspect the normal server logs for
`[HollowCountry] V2 admission feature=` (the `HCV2Admission` helper output),
subsequent errors, scene catalog diagnostics and optional provider
diagnostics. Each V2 module must print exactly one admission line. Bundle CLI
output (`HC bundle bundle-apply complete; runtime acceptance pending`) establishes
installer completion only. All gameplay acceptance remains pending.

Workshop publishing is owner-operated. Both owned items are **Public** since
2026-11-18 (owner decision); `--visibility unlisted` remains available. Use
`python -m tools.package.workshop_publish prepare --visibility public` (`tools/package/workshop_publish.py`) with a signed owned mod;
`--item addon` selects HCX. The base item also carries the signed
`hollowcountryanims.pbo` (the HollowCountryAnims addon, built from installed
data by `Build-Sign-Verify.ps1`, never from Git) with its own `.bisign`. The
alternative is DayZ Tools **Publisher**, pointed at the prepared content folder,
with Public or Unlisted visibility. After an upload, `record` stores the item's
published ID. Preparation sends no credentials; Steam handles its interactive
login and Steam Guard. A friend operator never publishes; they only subscribe.

An AI agent setting up the friend's server follows
[FRIEND_SERVER_AI_RUNBOOK.md](FRIEND_SERVER_AI_RUNBOOK.md) step by step.

The dependency helper is `tools/setup/workshop_sync.py`. Preview subscriptions
and server folder copies using:

```sh
python -m tools.setup.workshop_sync plan --server-root /private/server --workshop-content /steamapps/workshop/content/221100 --groups base,snafu,tactical_flava,living_packs,pve_patrols
```

Its `fetch` command asks Steam to download subscriptions with the owner's own
interactive account; `install` copies the original signed files into the server
folders and writes a receipt; `rollback` removes only files that receipt owns.
Run installs/rollbacks with the server stopped. The Workshop title remains
**Hollow Country Expansion AI (server)** for continuity, while every player loads
`@HollowCountryExpansionAI` in `-mod` after `@HollowCountry`. The full argument is:

```text
-mod=@CF;@COT;@DabsFramework;@Expansion-Core;@Expansion-AI;@Expansion-Navigation;@SnafuWeapons;@TacticalFlava;@RaG_Core;@RaG_Immersive_Vehicles;@AmbientAnimals;@SurvivorAnimations;@DayZ-Bicycle;@HollowCountry;@HollowCountryExpansionAI
```
