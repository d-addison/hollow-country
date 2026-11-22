# Friend server installation

Development target: DayZ Standalone 1.30, ChernarusPlus, 3–6 players. Features
are being built and V2 preferences default on. Native compilation, normal signed
PBO/server tests, client joins, persistence and single-client checks remain pending.
Nothing in a bundle build establishes DayZ behavior or production acceptance.

The server and every client use this ordered list. Subscribe to the original
Workshop items; never repack, modify or redistribute them. Players must also
subscribe to Expansion-Licensed and Expansion-Vehicles, in the manifest order below.

| Item | Workshop ID | Installed server folder |
| :--- | :--- | :--- |
| Community Framework | 1559212036 | `@CF` |
| Community Online Tools | 1564026768 | `@COT` |
| Dabs Framework | 2545327648 | `@DabsFramework` |
| Expansion Core | 2291785308 | `@Expansion-Core` |
| Expansion-Licensed | 2116157322 | `@Expansion-Licensed` |
| Expansion-Vehicles | 2291785437 | `@Expansion-Vehicles` |
| Expansion AI | 2792982069 | `@Expansion-AI` |
| Expansion Navigation | 2792984722 | `@Expansion-Navigation` |
| SNAFU Weapons | 2443122116 | `@SnafuWeapons` |
| Tactical Flava | 2646817942 | `@TacticalFlava` |
| RaG_Core | 3556131153 | `@RaG_Core` |
| RaG Immersive Vehicles | 3105330157 | `@RaG_Immersive_Vehicles` |
| Ambient Animals Pack | 3114410963 | `@AmbientAnimals` |
| Hollow Country | 3841628320 | `@HollowCountry` |
| Hollow Country Expansion AI | 3841637854 | `@HollowCountryExpansionAI` |

Expansion-Animations is intentionally not loaded; Expansion-AI brings its own AI animations. Survivor Animations and DayZ-Bicycle were retired on 2026-11-22 (see the upgrade note in INSTALL_ROLLBACK.md); an existing subscription is harmless and is no longer loaded.

The manifest's `living_packs` group contains Ambient Animals. Select `base,snafu,tactical_flava,living_packs,pve_patrols` for the full
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
base merge, travel CE and Ambient overlays, then the loot boost last. Each installer
has its own receipt, including the first installation. Unknown existing overlay
files and conflicting edited values refuse. Interrupted installs remain reversible
using those receipts; preserve every receipt and backup. No stock mission is
replaced wholesale. Do not merge another CE owner for the same class/event.

**Loot boost (on by default).** `bundle-apply` finishes with `tools/package/loot_boost.py`, which
regenerates the change from the friend's own installed mission bytes (no vanilla file ships):
non-firearm `nominal`/`min` in `db/types.xml` and registered HC CE types files, group/container
`lootmax` in `mapgroupproto.xml` and `RespawnTypes` in `db/globals.xml` (capped at 64) are
multiplied by `Multiplier` in `mission/hollow-country/loot-points/settings.json` (default 2.0,
range 1.0-4.0). Weapons/explosives categories (firearms, ammunition, magazines, attachments),
the firearms roster, uncategorized rows and weapons-only containers keep their stock values.
It also merges `loot-points/additions.json`: model-derived floor points per building family
(kitchen food, garage/shed tools, police and military at existing weapon scarcity, medical,
fire, civic and residential), at most 12 points per building and 3000 in total. Its own
receipt and byte-exact backups live in `hollow-country-loot-boost`; rollback undoes it first.
`InitialSpawn`, `RespawnLimit`, `RespawnAttempt` and cleanup values are unchanged. Native CE
acceptance of the added containers and the entity/performance cost are not yet observed.


The guided friend installer (`python -m tools.setup.friend_install`) keeps its
run journal and backups under `hollow-country-install-backups/<run>/`. After an
interruption, `--check` reports pending work without changing files; rerun with
`--apply` and the server stopped to recover before installing. Recovery restores
or removes a target only when its live bytes match a recorded installer write;
bytes already equal to the baseline need no change. Files created where a target
was previously absent and files inside mission trees receive the same checks.
If bytes match neither, recovery leaves them untouched, lists every conflict and
its backup path, and retains `rollback_pending`. A previously absent target has
no original backup file; the listed path identifies its place in the run backup.
Keep the journal and backups, compare the conflicting files, and reconcile them
by hand before retrying. A hard exit before a mission writer records its result,
or an older journal without written hashes, can require this manual review.
Never delete the journal to bypass a conflict. Identical dependency files are
recorded as unchanged and receive no backup.

The installer's **Profiles** step also handles upgrades from v1-test-9 or earlier:
if `profiles/HollowCountry/holdouts.json` has legacy `Version: 1` (unfunded) or
`Version: 2` (funded, before camp reserves) state or invalid JSON, it moves that file and any existing `holdouts.json.bak`
and `holdouts.json.tmp` beside it into the same run's backup folder, retaining
their relative paths. `--plan-only` lists each planned move in plain words;
`--apply` requires the server stopped. Each move uses the run journal, and
`hollow-country-install-receipt.json` lists the relative filenames under
`holdouts_moved`. Installer rollback/recovery restores their exact original bytes.
This preserves the old image for recovery and allows the mod to create fresh
funded state; it does not convert old occupants or reserves. A current `Version: 3`
image and its companions stay untouched, as do orphan companions when the main
file is absent. Unknown schemas stay untouched for manual inspection.
`--check` reports a separate `holdouts` line: PASS for absent or funded-schema
state, FAIL for legacy, invalid JSON or unsupported schemas, even when profile
writes are skipped. This schema check establishes no native load or gameplay
result; DayZ runtime acceptance remains pending.

**Upgrading a hand-kept settings.json.** The server restores each missing V2/W5
bool key to its declared default, which is `true`, so a hand-kept settings.json
from before those keys existed will switch those features on when it loads. The
installer's shipped templates carry every key, so a bundle install does not
change anything. Only int zero-fill has been observed natively. Bool handling
for absent keys is the declared-default restore in `HCApplyLegacy`, and no DayZ
run has confirmed it. To keep a feature off, set its key to `false` explicitly.
Nothing observed in DayZ yet.

Rollback with the server stopped:

```sh
python -m tools.package.optional_overlays bundle-rollback --mission /private/server/mpmissions/dayzOffline.chernarusplus
```

Rollback rehearses before changing live files, then undoes the loot boost, optional packs,
travel and the base merge, restoring the friend's own exact bytes. Drift refuses instead
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

Publish checklist step, needs the owner's go-ahead for that release: at the next publish of
either owned item, remove the two retired dependency Workshop ids (Survivor Animations
2918418331 and DayZ-Bicycle 2971190303) from the required items of both Workshop pages (Hollow
Country 3841628320 and Hollow Country Expansion AI 3841637854), in the Workshop page editor.
Neither mod is loaded any more, so a page that still lists them makes new subscribers download
content that is not used. Confirm the ids against the `retired` list in
`tools/setup/workshop_mods.json` before editing.

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
-mod=@CF;@COT;@DabsFramework;@Expansion-Core;@Expansion-Licensed;@Expansion-Vehicles;@Expansion-AI;@Expansion-Navigation;@SnafuWeapons;@TacticalFlava;@RaG_Core;@RaG_Immersive_Vehicles;@AmbientAnimals;@HollowCountry;@HollowCountryExpansionAI
```

## Release notes (2026-11-19 persistence recovery)

- Rows already lost on old installs cannot be recovered by this upgrade. In
  particular, the old progression v1-to-v2 migration could discard familiarity
  rows before players joined. The corrected migration preserves surviving legacy
  rows for their first living pickup; it cannot reconstruct previously lost rows.
- Leftover ecology pending files, including zero-byte and whitespace-only files,
  are copied and verified before their active name is removed. The last promoted
  checkpoint then loads, or the ordinary fresh-store path runs. Consumed receipt
  and pending quarantine archives retain the newest eight canonical UTC names
  per source file. Older archives are pruned; live files and the newest archive
  are preserved. Copy, readback and removal failures still preserve the pending
  evidence and refuse ecology admission. Runtime acceptance remains pending.

## Operator notes (2026-11-18 batch)

None of these behaviors has been observed in DayZ yet. They describe the source.

**Persistence and loot.** Upgrading does not require wiping `storage_1`; keep it.
Do not wipe it to "regenerate" loot either: native CE does not spawn a large
batch at boot after a wipe (`Initially (re)spawned:0` even with `InitialSpawn
100`). It refills the map at roughly 150–250 items a minute, and with stock
`IdleModeStartup 1` / `IdleModeCountdown 60` it refills nothing while the
server is empty. HC state
lives under `$profile:HollowCountry`. A store that finds damaged or unpaired files
quarantines only itself and keeps every file. The other stores start normally.
See [OPS_RECOVERY.md](OPS_RECOVERY.md), including the one-time `.bak` note for
worlds that were reset by an older build.

**Expansion's own patrols.** HC owns AI spawning. Install our
`AIPatrolSettings.override.json` as `$mission:expansion/settings/AIPatrolSettings.json`
(`Enabled: 0`, no `Patrols`, no `LoadBalancingCategories`). Without it Expansion
also spawns its default police, wreck and roaming patrols. With provider patrols
enabled, HC refuses every site with `provider patrols must be off`. That message
is this precondition, not a crash. `acceptance/pve_patrols.disable` turns HC's own
patrols off and does not fix it. See
[Expansion's own patrols](../mission/hollow-country/ai/README.md#expansions-own-patrols).

**AI policy keys** (`$profile:HollowCountry/expansion-ai-sites.json`). A profile
written by an older build keeps working: an absent key, or one set to 0, uses the
default (the HC-5 keys also log one `[HC Plan] HC-5 policy <key> absent; default <n>`
line). A non-zero value outside its range is refused with a named log line.

| Key | 0 / absent means | Allowed range |
| :--- | :--- | :--- |
| `RaidCooldownFloorSeconds` | built-in six-hour / seven-day floors | 1800–604800 |
| `ActivationRadiusScale` | 1.0 | 0.5–2.0; the result is clamped to `MinPlayerDistance`+50 … 1200 m |
| `MaxSignalWorkPerSecond` | 8 | HC-5 gesture/betrayal work |
| `MaxBetrayalRows` | 128 | HC-5 betrayal memory rows |
| `BetrayalRetentionSeconds` | 172800 (48 h) | HC-5 betrayal memory lifetime |

AI group sizes and counts come from the `AILimits` settings section (3–8 per
occupation group, 10–15 groups by default). See the
[AI README](../mission/hollow-country/ai/README.md) for every key.

**Searchable-location density** (`$profile:HollowCountry/settings.json`). Stop
and restart the server after changing `SearchDensityScale`. Missing or `0` means
1.0; other values must be 0.5–2.0. Invalid numeric values restore only this key
to `0` and log `[HC Settings] invalid SearchDensityScale`; the profile file is
preserved. Offline validation rejects invalid values before staging.

The scale multiplies the four configured budgets, rounds down to whole counts,
and clamps each result to its validated range. Explicit `MaxFurnishedProps: 0`
stays zero. With the shipped base budgets, the effective caps are:

| Budget | Scale 0.5 | Scale 1 (or 0) | Scale 2 | Validated maximum |
| :--- | ---: | ---: | ---: | ---: |
| `MaxBoundSearchSites` | 128 | 256 | 512 | 1024 |
| `MaxActiveInteriors` | 6 | 12 | 24 | 32 |
| `MaxPropsPerInterior` | 2 | 5 | 10 | 20 |
| `MaxFurnishedProps` | 750 | 1500 | 2000 | 2000 |

These are admission budgets, not promised observed locations. Existing authored
catalog bounds still apply (currently five props per furnished house and 1500
template props). Callers hard-cap the interior budgets at 5 props per house and
1500 template props, so a scale above 1 barely changes interiors; it mainly raises
`MaxBoundSearchSites` and the active-house cap. The retired `interiors.json` pilot no
longer takes part in these caps. The setting changes
neither search yield nor CE inventory, and never creates replacement loot.
Feature preferences and native clearance/provider gates remain authoritative.
Runtime acceptance and performance at 3–6 players remain pending.

Both shipped settings files include every registry key, including optional
zero-valued settings, because native JSON loading zero-fills absent scalars.
Existing profiles may omit `SearchDensityScale` safely. The shared registry
`tools/validate/shared_settings.json` records key, type, default, minimum,
maximum and owner; `HCSettings` uses its checked compiled mirror. Before
packaging, validate registry/default/range agreement and operator input from the
private source checkout with:

```sh
python3 -B -m tools.validate.runtime /path/to/profile/HollowCountry/settings.json
```

Startup prints one `[HC Settings] summary SchemaVersion=<version> nondefault_count=<count>`
plus `[HC Settings] effective <key>=<value>` for each non-default scalar setting;
Non-default density budgets show their scaled caps, and a non-default
`SearchDensityScale` shows its resolved multiplier. The Interiors readiness reason reports the template pack state; admission still requires native testing.

**Gunfire and AI caution.** This is deliberate: any audible shot within 80 m of
an AI widens its caution range to 80 m for 10 s. A firefight nearby makes groups
wary; a distant shot does not.

**Optional Workshop weapons (default on; test abundance, 2026-11-21).**
Run `install-hollow-country.bat --apply` against the stopped friend or local server.
Its weapon step follows the base mission and map overlays, reads the selected
Workshop dependencies, verifies the installed config, generates CE entries, then
installs both weapon layers. An absent pack prints `absent; skipped`; a present
pack whose terms, pinned classes, models or support fail verification is refused
without installing that pack. The whole mission change is rehearsed on scratch
before application and covered by the friend installer's recovery journal.
The bundle includes our tools/allowlists, never third-party PBOs or copied configs.
Keep the original Workshop downloads available through `--workshop-content`:
server mod copies contain PBOs and keys but omit the terms/vendor catalogue.

The static roster contains 176 SNAFU and 55 Tactical Flava firearms, plus their
verified magazines, loose pack ammo and functional attachments. Military firearm
budgets remain shared across packs and native rows; adding Police access happens
after allocation. Hunting weapons also reach Farm/Town/Village points throughout
tiers 1–4. Police families reach Prison, and magazines/ammo/attachments inherit
the routes of the weapons they feed or fit. Native patches, testbeds and unresolved
or duplicate definitions stay in each allowlist's `excluded` list. Individual
config subset pins remain authoritative for the expanded pack roster.

Each allowlist has one `test_abundance_multiplier` knob, now **`2.0`** under the
owner's 2026-11-21 #314 decision (previously 3.0); `--nominal-scale 1` selects the
pack baseline. Military allocation can further lower a row to its shared budget.
Generation also accepts `--nominal-scale X` (0.25–4.0), overriding that knob, and
repeatable `--tier-scale common|uncommon|rare=X`. Effective scales remain in
0.25–4.0; a positive CE minimum never rounds below 1. Family ceilings permit
up to four times the authored shares; the shared firearm ceiling is 3000 nominal /
1500 minimum across both packs. These are provisional test envelopes, not measured
native world caps. Vanilla ammo uses the separate vanilla economy policy.

Verification reports and staging are created outside Git in temporary folders;
each installed managed folder retains `verification.json`, `receipt.json` and
`core.backup`. Reapplying verifies on scratch and preserves byte-identical installs.
The friend installer removes these layers in reverse order before changing earlier
mission/map layers. For manual removal, **before** the earlier `bundle-rollback`, run:

```sh
python -m tools.package.tactical_flava_optional rollback --target /private/server/mpmissions/dayzOffline.chernarusplus
python -m tools.package.snafu_optional rollback --target /private/server/mpmissions/dayzOffline.chernarusplus
```

Only run each rollback when its managed folder exists. Preserve receipts/backups;
drift refuses. Direct `optional_overlays bundle-apply` handles the base layers;
use the guided installer to add the weapon layers. Scratch verification, CE
registration and exact rollback do not prove DayZ spawning, firing, attachment
assembly, persistence or balance. Those remain pending one-server/one-client
observation; multiplayer and target-load performance are unproven.

**Infected variety (HC-14).** This is optional and restart-bound. Stop the server, then:

```sh
python3 -B -m tools.package.infected_variety install --mission "$HC_MISSION" --stock-events "$HC_STOCK_EVENTS"
python3 -B -m tools.package.infected_variety install --mission "$HC_MISSION" --off
python3 -B -m tools.package.infected_variety rollback --mission "$HC_MISSION"
```

`--stock-events` must be the installed, unmodified `db/events.xml`, which has to
match the pinned hash. Install refuses edited target events and preserves all
other edits. Off and rollback restore the original bytes. Install also writes a
receipt, and rollback refuses if that receipt is missing while the mission still
carries the substitutions.

Two placements are part of the mix. The male navy soldier outfit has 2 shares in each
coastal tier (`InfectedCityTier1`, `InfectedVillageTier1`) and nowhere else; the heavy
navy classes stay out. The four winter medic outfits are seasonal: add
`--season winter`, or `--season-profile "$HC_PROFILE"` to read the season from the
persisted `HollowCountry/visual-seasons.json` clock, and install moves 2 shares each
from the matching non-winter medic outfit. The season is recorded in the receipt. CE
cannot be changed while the server runs, so a season change needs a stop, the
rollback command, and a new install. An install without a season, or with a missing or
invalid clock, places no winter outfits.
