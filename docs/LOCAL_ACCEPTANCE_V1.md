# Hollow Country v1 local acceptance session

One local server and one real client, played by the owner. This checklist maps what you
observe back to GitHub issues. Nothing here is evidence until you record it: every row
starts unchecked, and runtime acceptance stays pending until a box is ticked with a log line.

Rules for this session (owner decisions):

- A local server plus one client can accept a feature. Two-client items are not tested here.
  They are listed under "Deferred two-client items" and become user bugs if they show up.
- There is no fake client and no scripted player. Offline unit tests never establish DayZ behavior.
- Capability admission is fail-closed. Most gates are hard-coded `static bool` source gates that return
  false. They flip in source only after local evidence; there is no operator override switch. Where a
  row's gate is closed, the correct observation on this build is the logged refusal reason, and the row
  can only be accepted after a local acceptance build flips that gate (a source change the owner decides on).
- The one operator-controlled opt-in is the empty profile file for the fuel siphon (see Markers).
- Never commit game assets, keys, profiles or logs. Source stays private; nothing here authorizes
  public or Workshop publishing.

The marker inventory is generated, not hand-maintained. Re-run it whenever a worker lands:

```sh
python3 -B tools/audit/acceptance_markers.py
```

A unit test fails if any marker or gate found in the source is missing from this document.

## Setup

All paths below are examples. Substitute your own. Do not store keys, profiles or logs in the repo.

### Session flow

The shortest path for the owner's local server plus one client: run plan first, apply second and rollback last. Each step names the section that has the
detail. Nothing in this flow launches DayZ or opens a network connection, and nothing in it is evidence.

1. Build, sign and verify the addon (section 1) and take the backups (section 2).
2. Preview with `plan`. It writes nothing; it prints every change, the exact PowerShell launch commands and
   any NOTE lines (unsigned mod, missing public key, server password):

   ```sh
   python3 -B tools/setup/local_test_session.py plan --server-root /mnt/d/HollowCountryLocal/runtime-001 \
     --mission /mnt/d/HollowCountryLocal/candidate/mpmissions/dayzOffline.chernarusplus \
     --profiles /mnt/d/HollowCountryLocal/profiles --mod /mnt/d/HollowCountryLocal/signed-001/@HollowCountry \
     --mod-dest /mnt/d/HollowCountryLocal/session/@HollowCountry
   ```

3. Run the same arguments with `apply`. It writes the receipt first, then a byte-exact `serverDZ.cfg` backup
   and only the managed keys, the fresh `@HollowCountry` copy, the `cfggameplay.json` delta with the spawn
   kit, the economy delta and the markers. Start the server and the client with the printed commands.
4. Play the per-feature rows below. Recreate or remove markers per row (section 4).
5. Run `rollback --server-root <same server root>` (section 7). It undoes what the receipt records, last in,
   first out, and refuses on drift rather than overwriting your edits.

Flags the launcher accepts, beyond the required `--server-root --mission --profiles --mod --mod-dest`:

- `--snafu <dir>` and `--tactical-flava <dir>`: the optional weapon mods' Workshop folders. They are read
  only and never copied; the launcher adds them to the printed `-mod=` list in the order SNAFU, Tactical
  Flava, then HollowCountry.
- `--install-key`: copy the public `.bikey` of HollowCountry (and of `--tactical-flava`) into
  `<server root>\keys`. Only public keys; it refuses when there is nothing to copy.
- `--markers all|none|<name,name>`: which acceptance markers to create (default `all`, which writes every
  marker the scan finds, including the infected and interior ones). Prefer an explicit list of the markers
  for the rows you are about to run, or `none`, and add the rest by hand later (section 4).
- `--economy-profile <name|none>` (default `contextual-pilot`; `baseline`, `diagnostic`), `--no-gameplay`,
  `--time-accel` (default 4), `--night-accel` (default 8, multiplies the day value), `--client-root`,
  `--game-port`, `--query-port`.

What the launcher does not do yet (all marked "(follow-up)", none of them exists as a flag):

- `--interiors` (follow-up): install the interiors data pack. Run `tools/package/interiors_profile.py` yourself
  (the Interiors pack row).
- `--expansion-ai` (follow-up): merge `ai/AISettings.merge.json` and add the Expansion mods. Do it by hand
  (the Expansion AI row).
- `--markers all-local` (follow-up): a marker set limited to the local-acceptance opt-ins that are safe to run
  together. Today `all` is the only bulk option.
- Not wired into the launcher either, and run by hand from their rows: the weather `cfgweather.xml` candidate
  and the CE coverage delta. The firearms roster is in the launcher's economy delta by default (`--no-roster`
  drops it); the SNAFU and Tactical Flava CE deltas install through `--snafu` and `--tactical-flava`.

### Workshop subscriptions

Subscribe in Steam on the machine that runs the server and on the client. Hollow Country never bundles,
repacks or re-hosts any of them, and nothing under `mods/`, `mission/` or `config/` names them.

- Base addon only: none.
- Optional Expansion AI path (`@HollowCountryExpansionAI`, the PvE patrols row): CF, Dabs Framework,
  Expansion-Animations, Expansion-Core (Workshop 2291785308) and Expansion-AI (Workshop 2792982069). Load
  them before `@HollowCountryExpansionAI`. Expansion is CC BY-NC-ND: subscribe only, never repack.
- Optional Tactical Flava subset (the Firearms rows): Tactical Flava, Workshop 2646817942. Its rights review
  is pending; it loads before HollowCountry and its key goes through `--install-key`.
- Optional SNAFU Weapons subset: Workshop 2443122116 (DPL-ND, server use allowed, no repack).

`tools/setup/workshop_sync.py` fetches and installs the server side of this list from the pinned
manifest `tools/setup/workshop_mods.json`. Players get the mods by subscribing. Once our
@HollowCountry is published as Unlisted, the DayZ launcher subscribes them to it automatically.
See docs/FRIEND_SERVER.md.

### 1. Build, sign and verify (Route A, recommended)

Run in native Windows PowerShell from the private source checkout. DayZ Tools must be installed
through Steam. `-Python` must be a real native Python 3.10+ (WindowsApps aliases are rejected).
Choose a fresh `-OutputRoot`; the script refuses an existing one. Keep the private key outside the
checkout and never copy it to the server.

```powershell
.\tools\package\Build-Sign-Verify.ps1 -AddonRoot mods\HollowCountry -OutputRoot D:\HollowCountryLocal\signed-001 `
  -ToolsRoot 'D:\SteamLibrary\steamapps\common\DayZ Tools' -Python C:\Path\To\python.exe `
  -PrivateKey D:\HollowCountryKeys\hollowcountry.biprivatekey -PublicKey D:\HollowCountryKeys\hollowcountry.bikey -WhatIf
```

Drop `-WhatIf` to run it. The script writes `<OutputRoot>\@HollowCountry\addons\hollowcountry.pbo` and
copies `mod.cpp` beside it. Signing uses the official DSSignFile and DSCheckSignatures through
`tools/package/sign.py`; the signature file (`.bisign`) is written beside the PBO and the public
`.bikey` goes under `<OutputRoot>\keys`. Record the SHA-256 of the PBO for the session notes.

Install it on the local server:

1. Stop the server.
2. Copy the whole `@HollowCountry` folder (addons and mod.cpp together) to a private folder outside Steam,
   for example `D:\HollowCountryLocal\candidate\@HollowCountry`. Before replacing an older copy, keep it
   and its hash.
3. Copy the public `.bikey` into the server `keys` folder. Never copy the private key.
4. Add the same addon to the server and to the client launch: `-mod=D:\HollowCountryLocal\candidate\@HollowCountry`
   (quote it if the path has spaces). This addon has client Game, World and Mission script modules, so a
   server-only mod argument is wrong. Do not use file patching as verification.

Route B (unsigned development ZIP) only works when the disposable server sets `verifySignatures = 0`.
Do not use it on a server that keeps signature checks:

```powershell
python tools/package/pbo.py handoff --addon mods/HollowCountry --mission mission/hollow-country --out D:\HollowCountryLocal\hollow-country-private-dev.zip
python tools/package/pbo.py verify D:\HollowCountryLocal\hollow-country-private-dev.zip
python tools/package/deploy.py plan --zip D:\HollowCountryLocal\hollow-country-private-dev.zip --destination D:\HollowCountryPrivate
python tools/package/deploy.py install --zip D:\HollowCountryLocal\hollow-country-private-dev.zip --destination D:\HollowCountryPrivate --server-stopped
```

The installed mod path is then `D:\HollowCountryPrivate\HollowCountryPackage\@HollowCountry`. Save the
JSON transaction ID from `install`. Full details: `docs/INSTALL_ROLLBACK.md` and
`mission/hollow-country/INSTALL_AND_ROLLBACK.md`.

### 2. Back up before the first run

With the server stopped, make a verified copy of the server profiles directory, the mission storage
directory and the mission folder. The installer does not touch these. Use a disposable mission, profile
and storage copy for this session, never a live save.

### 3. Operator settings and logs

- Copy `mission/hollow-country/operator/settings.json` to `<profiles>\HollowCountry\settings.json`
  (create the `HollowCountry` folder first). If absent the core writes defaults there. All eight feature
  preferences default to true; a preference is not an admission.
- Stamina profile template: `config/hollow-country-stamina.json`. If absent the stamina module writes its
  default profile and logs it.
- Logs: the server writes `.RPT` and `.log` files in the server profiles directory. Grep those. The
  "RPT line to grep" column below is a substring of a `Print` in the scripts.

### 4. Markers

Markers are empty files in the server profiles directory at `HollowCountry\acceptance\<name>.enable`.
Create them only for the features you are about to test, then remove them again afterwards. Preview first
(dry run, creates nothing), then apply. `--apply` refuses a destination inside any git checkout:

```sh
python3 -B tools/audit/acceptance_markers.py --write-profile-plan ~/dayz-profiles --only fuel_siphon
python3 -B tools/audit/acceptance_markers.py --write-profile-plan ~/dayz-profiles --only fuel_siphon --apply
```

On the Windows host, run the same commands with the profiles directory path you pass to the server
`-profiles` option. The profile-marker inventory on this checkout:

| Marker | File and class | Source |
| :--- | :--- | :--- |
| `$profile:HollowCountry/acceptance/fuel_siphon.enable` | `HCFuelSiphonQualification.LocalAcceptanceOptIn` | `mods/HollowCountry/scripts/4_World/Actions/HCFuelSiphon.c` |
| `$profile:HollowCountry/acceptance/atmosphere.enable` | `HCAtmosphereQualification.LocalOptIn` | `mods/HollowCountry/scripts/4_World/Weather/HCAtmosphereQualification.c` |
| `$profile:HollowCountry/acceptance/ecology_migration.enable` | `HCEcologyMigrationQualification.LocalAcceptanceOptIn` | `mods/HollowCountry/scripts/4_World/Ecology/HCEcologyMigrationNative.c` |
| `$profile:HollowCountry/acceptance/events.enable` | `HCEventQualification.LocalAcceptanceOptIn` | `mods/HollowCountry/scripts/4_World/Events/HCEventQualification.c` |
| `$profile:HollowCountry/acceptance/events_sites.enable` | `HCEventSitesGate.LocalAcceptanceOptIn` | `mods/HollowCountry/scripts/4_World/Events/HCEventSitesGate.c` |
| `$profile:HollowCountry/acceptance/infected_deaths.enable` | `HCInfectedDeathQualification.LocalAcceptanceOptIn` | `mods/HollowCountry/scripts/4_World/Infected/HCInfectedDeath.c` |
| `$profile:HollowCountry/acceptance/infected_vision.enable` | `HCInfectedVisionQualification.LocalAcceptanceOptIn` | `mods/HollowCountry/scripts/4_World/Infected/HCInfectedVision.c` |
| `$profile:HollowCountry/acceptance/infected_contact_guard.enable` | `HCInfectedProfiles.ContactGuardOptIn` | `mods/HollowCountry/scripts/4_World/Infected/HCInfectedProfiles.c` |
| `$profile:HollowCountry/acceptance/infected_ce_adoption.enable` | `HCInfectedQualification.CEAdoptionOptIn` | `mods/HollowCountry/scripts/4_World/Infected/HCInfectedState.c` |
| `$profile:HollowCountry/acceptance/infected_pack_routes.enable` | `HCInfectedQualification.NativePackRoutesOptIn` | `mods/HollowCountry/scripts/4_World/Infected/HCInfectedState.c` |
| `$profile:HollowCountry/acceptance/infected_investigation.enable` | `HCInfectedQualification.InvestigationOptIn` | `mods/HollowCountry/scripts/4_World/Infected/HCInfectedState.c` |
| `$profile:HollowCountry/acceptance/infected_supplementary_chains.enable` | `HCInfectedQualification.SupplementaryChainsOptIn` | `mods/HollowCountry/scripts/4_World/Infected/HCInfectedState.c` |
| `$profile:HollowCountry/acceptance/infected_member_recovery.enable` | `HCInfectedQualification.MemberRecoveryOptIn` | `mods/HollowCountry/scripts/4_World/Infected/HCInfectedState.c` |
| `$profile:HollowCountry/acceptance/infected_horde_routes.enable` | `HCInfectedQualification.HordeStimulusRoutesOptIn` | `mods/HollowCountry/scripts/4_World/Infected/HCInfectedState.c` |
| `$profile:HollowCountry/acceptance/interior_placement.enable` | `HCInteriorRules.PlacementOptIn` | `mods/HollowCountry/scripts/4_World/Interiors/HCInteriorRules.c` |
| `$profile:HollowCountry/acceptance/interior_search.enable` | `HCInteriorRules.SearchOptIn` | `mods/HollowCountry/scripts/4_World/Interiors/HCInteriorRules.c` |
| `$profile:HollowCountry/acceptance/taped_light.enable` | `HCTapedLightAdmission.LocalAcceptanceOptIn` | `mods/HollowCountry/scripts/4_World/Survival/HCTapedLightNative.c` |
| `$profile:HollowCountry/acceptance/pve_patrols.enable` | `HCXAIQualification.LocalAcceptanceOptIn` (optional `HollowCountryExpansionAI` addon) | `mods/HollowCountryExpansionAI/scripts/4_World/HCXAIQualification.c` |

Source gates (the `Qualified`/`Accepted` method itself returns false in source and no profile file flips
it). Each is listed again in the row that depends on it. Every gate below except
`HCStaminaConfiguration.Qualified` is opened for a local run only by its marker, through a server-only,
probe-once `...Admitted()` method that logs one `EXPERIMENTAL local acceptance opt-in (<name>.enable)`
line when the marker opens it; without the marker nothing changes and nothing extra is logged. Markers are
independent and never auto-open each other. Dependencies you must open yourself:

- `infected_horde_routes` steers native packs, so it needs `infected_pack_routes` too (without it the
  admission line says `horde_stimulus_routes_requires_pack_routes`).
- Ecology migration (`ecology_migration`) calls the pack-route and horde-route gates and takes its clues
  from investigation and supplementary chains, so it needs `infected_pack_routes`, `infected_horde_routes`
  and at least one of `infected_investigation` or `infected_supplementary_chains` to move anything.
- Template House search needs `interior_search`, `EnableInteriors`, `EnableSearch`, an admitted
  template pack and a started House service with a healthy journal. SearchBinding starts that service
  independently of the optional legacy pilot. Look for `[HC Search Houses] armed=1` and its readiness
  facts; existing stock-CE items are bound lazily, and empty sites report that they are empty.
  Placement has its own `interior_placement` marker. The legacy pilot additionally uses `interiors.json`
  and measured context binding; it is optional when templates load. All native/client acceptance stays pending.
- `HCStaminaConfiguration.Qualified` has no marker because nothing reads it: stamina is already enabled by
  `<profiles>\HollowCountry\stamina.json` (the default profile is experimental and enabled).
- Opening `infected_ce_adoption`, `infected_pack_routes` or `infected_investigation` makes the infected
  module check native pack prerequisites and work-budget minimums at start (`MaxTickWorkItems` 8, 9 or 24).
  A failure quarantines the whole infected module with `[HC Infected] disabled: <reason>`; read that line
  before concluding a path does not work. The default of 32 satisfies every minimum.

- `HCFuelSiphonQualification.Qualified`
- `HCAtmosphereQualification.Qualified`
- `HCEcologyMigrationQualification.Qualified`
- `HCEventQualification.Qualified`
- `HCEventSitesGate.Qualified`
- `HCInfectedDeathQualification.Qualified`
- `HCInfectedVisionQualification.Qualified`
- `HCStaminaConfiguration.Qualified`
- `HCInfectedProfiles.ContactGuardQualified`
- `HCInfectedQualification.CEAdoptionQualified`
- `HCInfectedQualification.NativePackRoutesQualified`
- `HCInfectedQualification.InvestigationQualified`
- `HCInfectedQualification.SupplementaryChainsQualified`
- `HCInfectedQualification.MemberRecoveryQualified`
- `HCInfectedQualification.HordeStimulusRoutesQualified`
- `HCInteriorRules.PlacementAccepted`
- `HCInteriorRules.SearchAccepted`
- `HCTapedLightAdmission.Qualified`
- `HCXAIQualification.Qualified`

### 5. Server gameplay configuration (enableCfgGameplayFile)

The stamina module and the cfggameplay batch need DayZ's native gameplay configuration. DayZ documents
this as: set `enableCfgGameplayFile = 1;` in `serverDZ.cfg`, and put a `cfggameplay.json` in the mission
folder. This is DayZ-documented behavior (see `docs/SOURCES.md` item 11), not something this repo has
verified. Stamina logs `Stamina blocked: native gameplay configuration unavailable` when the native
configuration is missing. The launcher's `apply` installs the `cfggameplay.json` delta and the Hardscrabble
spawn kit (`mission/hollow-country/gameplay-profiles/hollow-country-v1.json`) and sets
`enableCfgGameplayFile = 1;` for you. By hand, use `tools/package/gameplay.py generate`, `install` and
`rollback` against a stopped private mission copy. The six cfggameplay rows below check the result.

### 6. Launching

`local_test_session.py` prints the exact PowerShell commands for the modded server and the modded client
(it never runs them). Run them yourself in native Windows. `tools/setup/Start-LocalClient.ps1` launches a
vanilla client with no mods ("no mods requested") and is not the path for this session.
`Invoke-NativeSmoke.ps1` is a bounded disposable smoke run with `verifySignatures=0` and BattlEye off. It
is not for this session either. The launcher never changes BattlEye, `verifySignatures` or passwords.

### 7. Rollback

Stop the server first and keep the failed candidate's logs.

- Launcher session: `python3 -B tools/setup/local_test_session.py rollback --server-root <server root>`
  restores the `serverDZ.cfg` backup byte for byte, removes the mod copy, the gameplay and economy deltas
  and the markers it created, and recovers an interrupted `apply`. Do this first.
- Addon: restore the previous `@HollowCountry` folder (and its matching client version), or remove the
  `-mod=` argument from the server and the client.
- Route B install: `python tools/package/deploy.py rollback --destination D:\HollowCountryPrivate --transaction <id> --server-stopped`.
  An interrupted install: `recover --destination ... --action abort` (or `resume`).
- Markers: delete the files under `<profiles>\HollowCountry\acceptance\`. No profile file means closed.
- Settings and state: restore the matching `settings.json` and storage backup from step 2. Never wipe a
  live save as a shortcut.
- CE changes you made by hand, in the reverse of the order you installed them (last in, first out):
  `ce_coverage.py rollback --mission <mission folder>` before the economy delta, and
  `tactical_flava_optional.py rollback` before `snafu_optional.py rollback` before the roster or
  economy rollback (`economy.py rollback --target <mission folder>`, or `firearms.py rollback` for a
  roster-only install). An out-of-order rollback is refused. The interiors pack: `interiors_profile.py
  rollback`. Preview the launcher rollback with `--dry-run` first if you want to see what it will do.

## Per-feature checklist

Tick one of Pass or Fail per row and write the matching log line in Notes. "On this build" means the
current source with every closed gate left closed. Any row whose gate is closed is accepted only after
the owner flips that gate in a local acceptance build, or exercises it locally with that row's marker (see
the marker inventory). A marker run is experimental local evidence, not production enablement. An observation of the refusal line is recorded as
"gate closed as designed", not as a pass for the feature.

First, for every run: grep the log for `[HollowCountry] Server initialized` and
`[HollowCountry][SelfTest] Core settings PASS`. If you see `Core native self-test FAILED; no modules started`
stop and record it.

| Issue | Feature | Marker | Player steps (one client) | Expected observation | RPT line to grep | Pass | Fail | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| #25 | Spawn kit | none; `gear/hardscrabble.json` through the gameplay delta | Make a fresh character (or die and respawn) three times. Open the inventory each time. | Every spawn has a KitchenKnife and a BandageDressing, plus one small random item. Nothing else is added. | none (inventory observation) | [ ] | [ ] |  |
| #5 #24 | Server tick cost per module | none | Play for at least 10 minutes: run through a town, open doors, fight infected, use the O menu. Afterwards run `python3 -B -m tools.testing.perf_capture <server RPT>`. | One `[HC Perf]` line per 60 s window. Each line names `slowest_module`, `slowest_module_max_ms` and `slow_ticks`, and `mod_max` lists every active module. Budgets are provisional: record the numbers, not a pass or fail against them. | `[HollowCountry] Perf sampler started` and `[HC Perf] window=` | [ ] | [ ] |  |
| #5 #24 | Client FPS A/B | none | Stand at the same spot (e.g. Elektro church, noon, clear weather) with the same graphics settings, and note the FPS from the Steam overlay for 30 s in each case: (A) retail DayZ, vanilla server, no mods; (B) our server without SNAFU or Tactical Flava; (C) our server with everything. Run the DayZDiag cases separately, because the diagnostic binary itself costs frames. If the server runs on the same PC, write that down. | Each case's FPS is recorded. B close to A means the mod is not the cost. The C minus B gap is the weapons packs. A large A minus B gap goes to the perf issue with the `[HC Perf]` lines from the same window. | none (overlay observation) | [ ] | [ ] |  |
| #48 | Workshop dependency install (server) | none | On the server machine run `python3 -B tools/setup/workshop_sync.py plan` and then `install` with your own steamcmd login (the tool never asks for or stores credentials). Start the server with the printed `-mod=` and `-serverMod=` lines. Then run `rollback`. | `plan` lists every pinned item in load order. `install` creates only the `@Folder`s it reports and copies their keys. `rollback` removes exactly those folders and keys, and leaves any mod that was already there. | `[HollowCountry] Server initialized` with the printed mod line | [ ] | [ ] |  |
| #31 | Stamina drain and recovery | none; `HCStaminaConfiguration.Qualified` (closed but unused: stamina is controlled by `stamina.json`, not a marker) | Spawn on the server with the default `stamina.json` (experimental and enabled). Sprint on flat ground from full stamina to empty and time it, then rest and time the refill. Repeat with `Settings.Enabled` false (or the `vanilla` profile) for a baseline. Also jump and swing a melee weapon. | Intended: continuous drain at 50% of vanilla (about twice the sprint time) and recovery 25% faster (125%); jumps and melee keep normal cost. If `Stamina blocked` is logged the module did not engage and you see vanilla behavior. | `Created enabled stamina profile: 50% continuous drain, 125% recovery` on first run, and `Stamina blocked` on failure | [ ] | [ ] |  |
| #31 | Weight bar and stamina bar HUD | none | Open the inventory, add and remove heavy items, watch the weight bar and the stamina bar. | Both bars show and the weight bar moves with load. Heavier load shortens endurance. | none (HUD observation); `Stamina blocked` if the profile fails | [ ] | [ ] |  |
| #37 | Groups: create, rename, leave, disband (solo) | none; preference EnableGroups | Press M, use Create group, Rename, Leave, Disband in the group layout. Invite, Accept, Decline, Kick and Transfer lead need a second client (deferred). | Group is created and renamed on the server and the buttons enable and disable correctly. | `[HC Groups]` (absence of `service inactive` or `start refused`) | [ ] | [ ] |  |
| #37 | Group icons (world and map) | none | With a group of one, look for your own group icon in the world and on the map. Teammate icons need a second client (deferred). | Own entry appears with the configured visibility. No icon for non-members. | `[HC Groups]` | [ ] | [ ] |  |
| #37 | Interactive map (M): markers | none | Press M (the native map key). Double-click the map to place a marker, then New marker, Save marker, Delete marker. Pan and zoom. | Marker persists across closing and reopening the map and is removed on delete. Shared sync with others is deferred. | `[HC Groups]` | [ ] | [ ] |  |
| #45 | Map information layers | none; client-only toggles (the server settings still gate the discovery layer) | Press M. Use the toggle strip over the map: Events, Visited, Team, Markers and Grid; each label reads on or off after a click. Open the O menu first so there is a known event, then look for its pin on the map. Walk into a named place and look for a Visited pin. Carry a powered GPS and read the navigation text under the map, then take it away. | Known-event pins show only for events you can already see in the O menu (at most 32, removed as soon as event data goes stale). Visited places show as [Visited] followed by the place name (at most 32). Grid draws 1 km lines and the navigation text gives your own east and north coordinates in metres with a 1 km grid note, or says to carry a powered GPS. Toggles only hide drawing; they never reveal anything the server did not send. Teammate pins need a second client (deferred). | none (client UI); on a fault `[HC Groups] map centerPosition missing; using world centre` | [ ] | [ ] |  |
| #33 | Events and the O menu | none; preference in the events config | Press O (UAHollowCountryEvents). Use Join, Leave, Refresh, Close. | Menu opens with the layout. Without both event markers (events and events_sites; see the reviewed sites row after this one) expect no missions and no rewards. | `[HC Events] enabled preference, no active missions` and `[HC Events] optional menu input UAHollowCountryEvents is not declared/bound` | [ ] | [ ] |  |
| #33 #46 | Events: reviewed sites and finite reward caches | `$profile:HollowCountry/acceptance/events.enable` AND `$profile:HollowCountry/acceptance/events_sites.enable` (both required; `HCEventQualification.Qualified` and `HCEventSitesGate.Qualified` stay closed) | Create both markers, restart the server, join with one client. Press O and Join a mission on a reviewed site (kamenka-supply-cache near 2512 / 2054, staroye-traffic-cache near 10676 / 4579, kumyrna-ambush-cache near 8393 / 5998; each is a stock static-event origin plus a (6.0, 10.4) offset, source-reviewed and not field-surveyed; data in docs/events). Reach the site: walk to the marked point and stay within 15 m for 10 s. Recover the cache: find the SmallProtectorCase at the same point, pick it up (it must be in your inventory or hands), then open it and take the items. Restart the server once and look for the case again. | Reach-the-site completes only after about 10 s of continuous presence within 15 m, not from farther away. A case holding up to 4 vanilla items (BandageDressing, TunaCan, Matchbox, Chemlight_Green, MetalWire, Battery9V, Rag; at most 3 cases and 12 items per server session) appears at the site once per site per session, and the recover mission completes when you carry it. After the restart a new session gets a fresh allowance and no old case persists (only the container stays out of the world save). If the case cannot hold every item it is kept with the partial content and logged; a point with unsuitable terrain height is refused with a log line. Without both markers: no sites, no caches. Surveyed stays false: report a site that is unreachable, inside geometry or overlapped by wrecks. | `[HC Events] EXPERIMENTAL local acceptance opt-in for reviewed sites and reward caches`, `[HC Events] reward cache created site` (the item count follows it), `[HC Events] reward cache refused for site` or `reward journal fault` on refusal; without the sites marker `[HC Events] reviewed sites and reward caches not admitted` | [ ] | [ ] | A latched reward journal fault refuses every later grant for that session; read the line before concluding a site is broken. |
| — | Interiors: placement | `$profile:HollowCountry/acceptance/interior_placement.enable` (`HCInteriorRules.PlacementAccepted`, closed) | Needs `<profiles>\HollowCountry\interiors.json`. Create the marker, restart, walk to a measured Chernarus house with the diagnostic trial off. Look for furnishings, then use the doors, stairs and usual route. Remove the marker and restart to confirm placement stops. | Without the marker no placement happens. With it, bounded furnishing appears in the measured houses (5 props at most per layout, MaxPropsPerInterior 5) and doors, stairs and routes stay usable. If the config is missing you get the disabled line instead. | `[HC Interiors] placement EXPERIMENTAL local acceptance opt-in (interior_placement.enable)`; without it `[HC Interiors] placement disabled: collision/nav/replication proof pending` | [ ] | [ ] |  |
| — | Interiors: pathgraph update after placement | `$profile:HollowCountry/acceptance/interior_placement.enable` (same as placement) | With placement running, stand in or near a placed house with an infected in view and watch it route around the furnishings, through the door and up the stairs. Watch for infected standing still against a prop. | One deferred pathgraph update is queued per placed prop (at most 5 per layout) after the whole layout is placed. Infected route around props and keep using doors and stairs; stuck behavior is the failure. Offline tests prove neither the rebuild nor the routing. | `[HC Interiors] pathgraph update queued for` | [ ] | [ ] |  |
| — | Interiors: search storage | `$profile:HollowCountry/acceptance/interior_search.enable` (`HCInteriorRules.SearchAccepted`, closed); also needs `interior_placement.enable` | Create both markers, restart, look at a cupboard or wardrobe in a placed house and use Search storage (6 s continuous action). Move away to cancel. | The search proof is opened. Whether the action works then depends on the search economy binder (see the Search economy binder row): with a finite native supply bound it can grant once per site, otherwise it stays refused server-side and the refusal is the observation. Mark Pass only if a grant happens once per site and survives restart. | `[HC Interiors] search EXPERIMENTAL local acceptance opt-in (interior_search.enable)`; without it `[HC Interiors] search disabled: durable commit/CE/two-client proof pending`; also `[HC Search Supply]` | [ ] | [ ] |  |
| #11 | CE coverage and loot economy (installed economy delta) | none; the launcher installs the economy delta (profile contextual-pilot plus datamined items) unless `--economy-profile none` | After `apply`, fly or walk across several towns and compare loot tiers and building types. Apartment (tenement) coverage points are a separate step that needs a native sampler result this checkout does not ship (see Features pending landing); skip that part and mark it not run. | Loot appears where it fits the building type and tier. Tenements may still show no loot: the coverage delta is not installed without a native sampler result. No duplicate loot after restart. | `[HC Search Economy]` | [ ] | [ ] |  |
| #17 #52 | Crafting: salvage recipes (11) | preference EnableCrafting | With the right tool in hands or inventory, combine: camo net, cable reel, large and medium leather, wooden bat, nailed bat, barbed bat, ruined crate, and the three ruined recoveries (ruined large leather, ruined wooden bat, ruined nailed bat). 11 recipes in all. Tools: knife family, pliers, hacksaw or handsaw, crowbar or axe. | Each recipe takes time, needs its tool, damages or consumes as designed and yields the listed materials. Missing tool means no recipe. | `Crafting definition/config checks passed; runtime acceptance PENDING` | [ ] | [ ] |  |
| #53 | Fuel siphon from a car | `$profile:HollowCountry/acceptance/fuel_siphon.enable` (and `HCFuelSiphonQualification.Qualified`) | Create the marker, restart the server. Hold an empty bottle or jerry can in hands, stand at a parked car (engine off, not moving, fuel above zero) at the fuel selection and choose Siphon fuel. Interrupt once, then complete once. | Fuel leaves the car tank and enters the container: finite, capped by container space, no refund on cancel mismatch. Without the marker the action never starts. | `Fuel siphon EXPERIMENTAL local acceptance opt-in active` (marker present) or `Fuel siphon not admitted` (absent); on error `Fuel siphon receipt mismatch` | [ ] | [ ] |  |
| #56 | Taped light (flashlight on gun) | `HCTapedLightAdmission.Qualified` (closed); marker `$profile:HollowCountry/acceptance/taped_light.enable` | Read the start log. Create the marker, restart, carry duct tape and a flashlight, hold a native light-slot gun, use the tape-light action, toggle the light, then use Remove. Relog once with the light taped. | No marker: the action is refused and the light stays in inventory. With the marker: the flashlight attaches through the native light slot (no item created or deleted), the beam follows the gun, Remove returns the same flashlight, and the attachment survives the relog. Hosts outside the native light-slot pairs are post-v1 (#58). Known P2: a vanilla-attached light shows Remove but is denied. | `[HollowCountry] Taped light EXPERIMENTAL local acceptance opt-in active; runtime acceptance PENDING`, `[HollowCountry] Taped light not admitted; runtime acceptance PENDING`, `[HollowCountry] Taped light result=<n> runtime acceptance PENDING` | [ ] | [ ] |  |
| #19 #44 | Infected: capability admission and variants | `HCInfectedQualification.CEAdoptionQualified` and `HCInfectedQualification.NativePackRoutesQualified` (closed); markers `$profile:HollowCountry/acceptance/infected_ce_adoption.enable` and `$profile:HollowCountry/acceptance/infected_pack_routes.enable` | Start the server and read the log. Then create `infected_ce_adoption` and `infected_pack_routes` (one at a time is fine), restart, wait for a cohort to be adopted or a pack route to run, and walk near infected in two or three towns (civilian and military). | No marker: the admission line lists requested versus admitted paths with reasons such as `ce_adoption_unqualified`; native behavior retained. With a marker: that path reads `admitted=1 reason=admitted`; CE adoption adopts and tracks native cohorts (needs `EnableHordes`), pack routes let the module steer an owned native pack. If prerequisites fail the module logs `[HC Infected] disabled: ...`. | `[HC Infected] capability admission`, then `[HC Infected] CE adoption EXPERIMENTAL local acceptance opt-in (infected_ce_adoption.enable)` or `[HC Infected] native pack routes EXPERIMENTAL local acceptance opt-in (infected_pack_routes.enable)` | [ ] | [ ] |  |
| #20 #22 | Infected: doors and line of sight | none (source behavior) | Close a door between you and an infected, then open it. Break line of sight and re-acquire. | Infected use native door and perception behavior; no teleport and no omniscient tracking. | `[HC Infected]` | [ ] | [ ] |  |
| #21 #22 | Infected: audio cues | none | Listen to footsteps, shuffling and contact sounds at distance and behind obstacles. Single-client only; the multi-client audio comparison is deferred. | Surfaces, distance and obstacles change what you hear. | `[HC Infected]` | [ ] | [ ] |  |
| #19 #44 | Infected: injury and contact guard | `HCInfectedProfiles.ContactGuardQualified` (closed); marker `$profile:HollowCountry/acceptance/infected_contact_guard.enable` | Take a leg hit from an infected (or shoot one in the leg) and watch the movement. For the contact guard, create the marker, restart, stand behind a thin wall or fence an infected cannot reach through and let it swing, then retreat and check whether a delayed hit lands. | Wounded movement is readable, and a leg hit can make a crawler (the leg zone value itself is in the infected leg crawlers row at the end). Without the marker the guard stays pending. With it, an infected that cannot reach you has its strike suppressed (an experimental filter: a queued strike may still land, which is what this tests). | `[HC Infected] contact guard EXPERIMENTAL local acceptance opt-in (infected_contact_guard.enable)`; without it `[HC Infected] contact guard pending native wall-hit qualification` | [ ] | [ ] |  |
| #21 #22 | Infected: investigation | `HCInfectedQualification.InvestigationQualified` (closed); marker `$profile:HollowCountry/acceptance/infected_investigation.enable` | Create the marker and restart. Make a noise (fire a suppressed or unsuppressed shot, break a window) out of sight of nearby infected, then watch whether up to two of them go to the last observed spot, search, and give up. Note which infected join in and which do not (injured crawlers, engaged and grouped infected do not). | Without the marker no scripted investigation occurs; native reaction only. With it, a bounded investigation toward a frozen observation (not your live position), no omniscient tracking and no teleport. Needs the native pack prerequisites. | `[HC Infected] investigation EXPERIMENTAL local acceptance opt-in (infected_investigation.enable)`; the investigation segment of the `[HC Infected] capability admission` line reads requested=1 admitted=1 reason=admitted; without the marker it reads investigation_unqualified | [ ] | [ ] |  |
| #20 #35 #56 | Infected: vision (clothing, darkness and lights) | `HCInfectedVisionQualification.Qualified` (closed); marker `$profile:HollowCountry/acceptance/infected_vision.enable` | Create the marker and restart. Approach an infected at night (bright night is capped, not dark) with and without a lit flashlight or chemlight held, then in dark and in bright clothing, and note the distance at which it notices you each time. Remove the marker and repeat once. | Without the marker the vision range is exactly the native value. With it the range is multiplied by one clamped factor between 0.6 and 1.3 built only from your worn clothing visibility, a lit light held or worn and the world clock; it reads nothing about the infected or other players. All constants are provisional and unobserved. | `[HollowCountry] Infected vision EXPERIMENTAL local acceptance opt-in active; runtime acceptance PENDING` or `[HollowCountry] Infected vision not admitted; runtime acceptance PENDING` | [ ] | [ ] |  |
| #32 | Infected: deaths | `HCInfectedDeathQualification.Qualified` (closed); marker `$profile:HollowCountry/acceptance/infected_deaths.enable` | Create the marker and restart. Kill several infected with different ammunition and hit zones (rifle to the head, shotgun to the torso, a melee backstab or neckstab, a leg shot) and watch the fall. Look at each corpse and open its inventory. Remove the marker and repeat once for a baseline. | Without the marker the death is the native one. With it the death animation type is selected by the authored table; the corpse, collision, loot access and cleanup stay on the vanilla path, and the vanilla impulse for impulse ammunition cannot be undone. A folded or ragdoll-like death is a feasibility goal only; full ragdoll is unconfirmed. Only the first 16 decisions are logged. | `[HollowCountry] Infected deaths EXPERIMENTAL local acceptance opt-in active; runtime acceptance PENDING`, `[HollowCountry] Infected deaths not admitted; runtime acceptance PENDING` and `[HollowCountry] Infected death ammo=` | [ ] | [ ] |  |
| #21 | Infected: alert chains | `HCInfectedQualification.SupplementaryChainsQualified` (closed); marker `$profile:HollowCountry/acceptance/infected_supplementary_chains.enable` | Create the marker and restart. Fight an infected in a group of several and watch whether neighbors relay the alarm, with and without a wall or distance between them. Needs `EnableAlertChains`. A second client is deferred, so judge relay audibility only from your own position. | Without the marker no scripted relay occurs. With it, neighbors can pick up a relayed alarm (bounded hops and cooldown, native hearing rules). Two-client audibility stays deferred. | `[HC Infected] supplementary chains EXPERIMENTAL local acceptance opt-in (infected_supplementary_chains.enable)`; without it `supplementary_chains_unqualified` in the admission line | [ ] | [ ] |  |
| #21 | Infected: hordes | `HCInfectedQualification.MemberRecoveryQualified` and `HCInfectedQualification.HordeStimulusRoutesQualified` (closed); markers `$profile:HollowCountry/acceptance/infected_member_recovery.enable` and `$profile:HollowCountry/acceptance/infected_horde_routes.enable`; horde routes also needs `infected_pack_routes.enable` (and `infected_ce_adoption.enable` for a cohort to exist) | Create the markers you want, restart, wait and move around for at least one save interval, kill a member, then restart the server once. For horde routes, make a noise near a cohort and watch it retarget toward the clue rather than toward you. | Without markers no horde materialization; the state journal is validated and kept verbatim and population is unchanged. With member recovery, restart reconciles known members and retires dead or missing ones. With horde routes (plus pack routes), a cohort retargets to a bounded clue with a stall and cooldown. Without pack routes the reason is `horde_stimulus_routes_requires_pack_routes`. | `[HC Infected] member recovery EXPERIMENTAL local acceptance opt-in (infected_member_recovery.enable)` and `[HC Infected] horde stimulus routes EXPERIMENTAL local acceptance opt-in (infected_horde_routes.enable)`; without them `horde_stimulus_routes_unqualified` | [ ] | [ ] |  |
| #34 | Ecology | none; preference in ecology config | Watch animals and infected near water and food sources for a few minutes. | Observation and path adapter only: coverage partial, feeding and drinking and resource movement unsupported, native brains preserved. | `[HC Ecology] observation/path adapter started; native brains preserved` or `[HC Ecology] explicitly disabled by operator` | [ ] | [ ] |  |
| #63 #34 | Ecology migration (cohorts follow resources) | `HCEcologyMigrationQualification.Qualified` (closed); marker `$profile:HollowCountry/acceptance/ecology_migration.enable` plus the infected markers listed above | Create `ecology_migration`, `infected_pack_routes`, `infected_horde_routes` and `infected_investigation`, restart, and watch an infected cohort near a town for several minutes. | No marker: ordinary pack retargets are unchanged. With the markers: a complete cohort is submitted to migration instead of the ordinary route; an incomplete or refused cohort gets no fallback route (it holds). Failures quarantine migration, not the infected module. | `[HC Ecology] migration EXPERIMENTAL local acceptance opt-in; runtime acceptance PENDING`, `[HC Ecology] migration journal ready; schedules=...` or `[HC Ecology] migration not admitted; runtime acceptance PENDING` | [ ] | [ ] |  |
| #35 | Weather and bright nights | `HCAtmosphereQualification.Qualified` (closed); marker `$profile:HollowCountry/acceptance/atmosphere.enable`; preference EnableAtmosphere; `lightingConfig` is forced to 0 | Generate the delegated candidate with `python3 -B -m tools.package.atmosphere v1-script --source <mission cfgweather.xml> --output <candidate cfgweather.xml>`, keep the original, and use the candidate as the mission cfgweather.xml (this tool has no installer). Create the marker and restart (ChernarusPlus on 1.30.164289 or 1.30.164289.70 only). With the launcher's 4x day and 8x night values the night runs at 32x. Wait through dusk (20:00), night and dawn (05:00) and note light, cloud and rain. Remove the marker and restart once to confirm vanilla returns. | Nights stay bright (never dark) and your own light is untouched. From 20:00 to 05:00 the overcast cap is 0.55 and rain is capped, so no night storm; dawn restores the full range. The supplementary relay noise radius follows the atmosphere. Without the marker, with a missing or non-delegated cfgweather.xml, or on another map or build, vanilla stays in control and the log says why. Check the 32x figure against an in-game clock. | `[HollowCountry][Atmosphere] EXPERIMENTAL local acceptance opt-in; runtime acceptance PENDING; restart required to change marker`, `[HollowCountry][Atmosphere] EXPERIMENTAL ChernarusPlus script owner`, `[HollowCountry][Atmosphere] PENDING native acceptance; no atmosphere.enable marker; vanilla weather retained`, `[HollowCountry][Atmosphere] BLOCKED missing delegated cfgweather.xml; generate v1-script candidate; vanilla retained` | [ ] | [ ] | The BLOCKED and PENDING lines mean vanilla weather, which is the correct fail-closed result without the marker. |
| — | Camera mode (first person on foot, third person in vehicles) | none; serverDZ.cfg `thirdPersonView = 2` and `disable3rdPerson = 0` (the launcher sets both) | Start the server and read the log. Join with one client, press the camera key on foot, then get into a vehicle and press it again. | On foot you stay in first person; in a vehicle third person is available. The launcher plan marks thirdPersonView as a value to confirm in the session, so record what you saw. Any other logged mode means a key is missing or overridden. | `[HollowCountry] Camera mode: ` (the label after it should read first person on foot, third person in vehicles) | [ ] | [ ] |  |
| #15 #42 | Search economy binder | the interior markers (`interior_placement`, `interior_search`) | With both interior markers and a started layout, wait for CE to settle after start, then search a container in the evidenced house. | Search draws from a finite native supply: no item is created from nothing, a searched source is not refilled, and a refusal leaves search refused. | `[HC Search Binding] finite native supply bound; runtime acceptance PENDING`, `[HC Search Binding] refused: <reason>` or `[HC Search Binding] unavailable: register/start SearchBinding before Interiors; search remains refused` | [ ] | [ ] |  |
| #13 #15 #42 | Search in every covered house class (template pack) | the interior markers (`interior_placement`, `interior_search`) and the installed pack `$profile:HollowCountry/templates/` | Install the pack (`interiors_profile templates install --server-stopped`), restart, then try Search storage at a vanilla loot spot (shelf, floor or weapon point) in three different house types: a common village house, an apartment block and a shed or barn. Search again at the same spot, then reconnect and restart and try once more. | The pack loads (149 of 263 house classes searchable: 64 with rooms and furniture, 85 search-only whose rooms are still unproven). A search grants at most once per spot and never after a reconnect or restart. Search-only houses get no extra infected rooms or furniture. Houses outside the pack stay unsearchable. | `[HC Interiors] templates provisional; native clearance/path/audio/replication acceptance pending; files=`, `[HC Interiors] templates refused: <reason>`, `[HC Search Houses] lazy registry refused; house search stays refused`, `[HC Search Houses] site cap reached:` | [ ] | [ ] |  |
| #23 #24 #25 | Friend bundle | none | After the final local session, run `python3 -B -m tools.setup.friend_bundle build` as in `docs/FRIEND_SERVER.md` (Friend bundle), with `--addon`. Open the output. | One folder with `mpmissions/`, `profiles/`, `@HollowCountry/`, `@HollowCountryExpansionAI/`, `keys/`, `start-server.bat`, `serverDZ-hollow-country.txt`, `README.txt` and `bundle-manifest.json`. No `storage_*`, logs or passwords. The `-mod=` line matches the local session. | `bundle written: <n> files (left out ...)` | [ ] | [ ] |  |
| #15 #20 | Search noise (one noise per completed search) | the interior markers (`interior_placement`, `interior_search`) | With both interior markers and a bound supply, stand out of sight of an infected, complete a Search storage action, then cancel one and repeat a completed search of the same container. | One bounded native AI noise at your position, only on the transition from open to complete. Refusal, cancel, failure and repeat are silent. Whether nearby infected react is the observation; the noise is not a long-lived alert. | none (native AI reaction only; no log line is printed) | [ ] | [ ] |  |
| #13 #14 #20 | Interiors pack (profile install) | the interior markers | Install the pack with `python3 tools/package/interiors_profile.py install` (see its `--help`) into the server profile, start, and visit the one evidenced house. Roll back with its `rollback` command. | The pack installs with a receipt and rolls back cleanly. Only one house is evidenced on this build; measured layouts and rooms for the rest are still pending, so other houses stay vanilla. | `[HollowCountry]` interiors lines; `[HC Interiors] legacy pilot absent; template path in use` when templates load without the legacy pilot | [ ] | [ ] |  |
| #36 | Expansion AI PvE patrols (optional addon) | `HCXAIQualification.Qualified` (closed); marker `$profile:HollowCountry/acceptance/pve_patrols.enable` | Subscribe to the Expansion AI mods listed under Workshop subscriptions (CF, Dabs Framework, Expansion-Animations, Expansion-Core 2291785308, Expansion-AI 2792982069); load them, then `@HollowCountryExpansionAI` after them. Merge `ai/AISettings.merge.json`, create the marker, restart (each restart is a fresh WorldSession) and walk near a patrol route. | Patrols spawn on the reviewed routes with leases, are retired on stop, and never spawn without the marker. Without Expansion the addon logs and does nothing. Known P2: the lease journal is never pruned, so after the history cap delete `expansion-ai-leases.json`. | `[HC Expansion AI] EXPERIMENTAL local acceptance opt-in (pve_patrols.enable); qualification pending` | [ ] | [ ] | Expansion is CC BY-NC-ND: subscribe only, never repack. |
| #36 | Expansion AI diagnostic spawn (off by default) | marker `$profile:HollowCountry/acceptance/xai_diagnostic_spawn.enable` (`HCXAISiteDirector.DIAGNOSTIC`) | Only for a Wine or empty-server observation: create the marker, restart with the PvE patrol set, wait two minutes, then delete the marker and restart. Never leave it on for play. | The first site of each kind (patrol, scavenger party, holdout) spawns once with no player nearby, each logged; no further diagnostic spawns. | `[HC Expansion AI] DIAGNOSTIC marker present: one site of each kind spawns once with no player (Wine observation only)`, `[HC Expansion AI] DIAGNOSTIC spawn of site <id> (<kind>)` | [ ] | [ ] |  |
| #30 | Firearms: curated roster and datamined vanilla guns | none; the roster is a CE delta | The launcher's economy delta includes the roster by default (`--no-roster` leaves it out). By hand: `python3 -B -m tools.package.economy generate --source <stock mission copy> --profile mission/hollow-country/economy-profiles/contextual-pilot.json --roster tools/package/firearms_roster.json --out <delta dir>`, then `install --delta <delta dir> --target <stopped private mission copy>`. Spawn or find each firearm (37 weapons, 18 magazines, 12 ammunition types), load it and fire it. The datamined guns (Lee-Enfield, MP18, Luger and finished skins) are each pending local acceptance; `--no-roster-datamined` drops them. | Weapons behave natively at the 2x scarcity counts (weapon nominals total 342). A datamined gun that does not spawn, fire or take its ammunition is recorded and switched off, not hidden. | none (offline CE install; check the mission types file and in-game spawns) | [ ] | [ ] |  |
| #30 | Datamined non-weapon items (clothing, bags, tools) | none; rows are in the economy delta | After `apply` with the default economy profile, find or spawn a few of the 55 finished-but-unused vanilla items (leather jackets, hunting and winter gear, Drysacks, Iceaxe, FilteringBottle, CrabCan). | Items spawn at rare counts and work natively. `--no-datamined` on `economy generate` leaves them all out. | none (offline CE install; check in-game spawns) | [ ] | [ ] |  |
| #30 | Firearms: SNAFU Weapons subset | none; optional dependency, Workshop 2443122116, never bundled | Subscribe, then run `python3 -B -m tools.package.snafu_optional verify --install <SNAFU Workshop dir> --out <report outside Git>`, `generate --source <stock mission copy> --report <report> --out <delta dir>` and `install --delta <delta dir> --target <mission copy>` after the roster delta. Add `--snafu` to the launcher plan so the load order is right. Spawn and fire the 15 weapons (the conservative seven, WW2 submachine guns and five modern military-tier arms). | Without a verified report no SNAFU spawn entry is produced (fail-closed) and the base addon works without SNAFU. With it, weapons fire and take their SNAFU ammunition; signature behavior with a signed server is unobserved. | none (offline verify and install; check the report and in-game spawns) | [ ] | [ ] | Rollback is last in, first out: snafu_optional rollback before the roster or economy rollback. |
| #30 | Firearms: Tactical Flava subset | none; optional dependency, Workshop 2646817942, never bundled | Subscribe, then run `python3 -B -m tools.package.tactical_flava_optional verify --install <TF dir> --vanilla-addons <DayZ Addons> --out <report outside Git>`, `generate --source <stock mission copy> --report <report> --out <delta dir>` and `install --delta <delta dir> --target <mission copy>` after the roster and SNAFU deltas. Add `--tactical-flava <dir>` and `--install-key` to the launcher plan. Run the six local checks in docs/FIREARMS.md (vanilla M4A1 and Mosin attachments, key collisions, ZombieBase and ActionConstructor stacking, the M14 adapter with an Elcan optic, rifle slot changes) and fire each TF weapon. | Without a verified report nothing spawns. With it the 16 curated entries spawn and fire, vanilla weapons keep behaving normally, and the script log shows no stacking errors. Owner decision: Tactical Flava is accepted for this subset; confirm it locally. | none (offline verify and install; check the script log and in-game spawns) | [ ] | [ ] | Rights review of the TF item is pending; never repack. Roll back before the SNAFU and roster rollbacks. |
| — | cfggameplay: temperatures | none; `enableCfgGameplayFile = 1;` (the launcher sets it and installs the delta) | Stand outside through a day or night cycle, compare body temperature and shivering with vanilla. | Monthly minimum and maximum temperatures are 1 to 3 degrees colder than stock: colder than vanilla but not harsh. | none (gameplay file values) | [ ] | [ ] |  |
| — | cfggameplay: spawn kit | none; `enableCfgGameplayFile = 1;` | Create a new character several times and read the inventory. | Hardscrabble kit: a randomised civilian top, trousers and shoes (about 60 to 69 percent health) and one small item (Rag or a chemlight), no weapons. | none | [ ] | [ ] |  |
| — | cfggameplay: weapon obstruction | none; `enableCfgGameplayFile = 1;` | Raise a weapon against a wall and against open air. | Weapon obstruction by nearby objects applies (dynamic mode 1, static mode 2). | none | [ ] | [ ] |  |
| — | cfggameplay: wet weight | none; `enableCfgGameplayFile = 1;` | Wear gear in the rain, check weight in the inventory, then dry it. | Wet gear weighs more than dry, up to 2.25 times when drenched. | none | [ ] | [ ] |  |
| — | cfggameplay: hit indicator | none; `enableCfgGameplayFile = 1;` | Take a hit (infected or fall) and watch the screen. | A stronger directional hit indicator than vanilla (dark red, 3.5 s, post-process on). | none | [ ] | [ ] |  |
| — | Infected leg crawlers (addon config, not cfggameplay) | none; part of the HollowCountry addon config.cpp, so it needs the PBO rather than the gameplay file | Shoot or hit an infected in the leg a few times and watch whether it drops to a crawl sooner than vanilla. | An infected crawls after about half the leg damage vanilla needs (leg zone health 50 instead of 100). This is about infected, not a player crawl. Bosses that set their own zones stay vanilla. | none | [ ] | [ ] |  |

Rows tagged with "—" have no issue number found in the repo sources. Fill in the number when you map
results back to GitHub.

## Features pending landing

Everything that is on main is in the per-feature table above. These items are not: each is blocked on
something this checkout does not contain (a native measurement, an owner decision or a new install path).
Do not tick Pass for any row here until its blocker is closed in a landed commit and the build is
installed. After a landing, regenerate the marker inventory (`acceptance_markers.py`) and move the row up.

| Issue | Feature | Marker | Player steps (one client) | Expected observation | RPT line to grep | Pass | Fail | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| #11 | CE tenement coverage points | none; CE delta via `tools/package/ce_coverage.py` | Only after a native sampler run produces a result: `ce_coverage.py request`, run the sampler, then `generate`, `install` and later `rollback`. Walk through apartment blocks and check for loot. | pending landing: no native sampler result is shipped, so `ce_coverage.py validate` prints pending and no points are invented. Apartment prototypes have zero raw points on stock, so they show no loot until this lands. Barracks are not changed. | none (offline tool output; no script line) | [ ] | [ ] | Install after the economy delta; roll back before it. |
| #25 | Launcher follow-up | none | Use the launcher as written in Session flow. The three follow-up items are not available: `--interiors`, `--expansion-ai` and `--markers all-local`. | pending landing: the interiors pack, the Expansion AI settings merge and a limited all-local marker set are still done by hand. Passing an unknown flag is an argument error, not a feature. | none (launcher console output) | [ ] | [ ] |  |
| #30 | Rostered optics | none | Nothing to test: the roster and the SNAFU allowlist carry an empty optics block. | pending landing: deferred pending an owner decision. No vanilla or SNAFU optic is rostered; Tactical Flava optics are in the TF subset only. | none | [ ] | [ ] |  |
| #30 | Deferred datamined variants | none | Nothing to test: nine finished variants (MakarovPB, Winchester70_Black and _Green, B95_Black and _Green, CZ527_Camo, _Green, _desert and _winter) are absent from stock types. | pending landing: they need a new-type-entry install path, because the installer only overrides stock entries and refuses a type stock does not define. | none | [ ] | [ ] |  |
| #13 #14 #20 | Interiors measured layouts and rooms | none; the interior markers once a pack exists | Visit houses other than the one evidenced house. | pending landing: measured layouts and rooms for the rest need a reviewed native survey. Until then they stay vanilla and the pack reports them as pending-measurement. | `[HC Interiors] legacy pilot absent; template path in use` when templates load without the legacy pilot | [ ] | [ ] |  |
| #56 #58 | Taped light other hosts | none; same `taped_light.enable` marker as the per-feature row | Try the tape-light action on a host that is not one of the native light-slot pairs. | pending landing: hosts outside the native light-slot pairs are post-v1 (#58). Expect the action to be refused. | `[HollowCountry] Taped light not admitted; runtime acceptance PENDING` | [ ] | [ ] |  |

## Deferred two-client items

These need a second real client. The owner decision is not to test them in this session. If one shows up
in play, file it as a user bug with the log excerpt.

- Network: group invite, accept, decline, kick and transfer lead; synchronization of shared markers and
  teammate icons between two clients; event join and leave visibility for another player; reconnect and
  stale-position behavior for a group.
- Audio: infected footstep, shuffle and contact audio as heard from two positions at once; gunshot
  audibility at distance for another player.
- Visibility: infected perception of two players, group member visibility rules, and what a second player
  sees of an infected door or crawl state.

## Performance

The 3 to 6 player budgets (tick cost, work items, active hordes and members, interior counts) stay
provisional until measured on the target load. This single-client session does not measure them. Do not
read any "bounded pilot limit" in the settings as a promise.

## README v1 items with no testable observation on this build

These cannot give a "pass" this session, only a recorded refusal or a "not testable": taped light on hosts
outside the native light-slot pairs, the infected complex paths (CE adoption, pack routes, investigation,
supplementary chains, member recovery, horde stimulus routes, contact guard), interior placement and search
and the search economy binder when run without their markers (each has a marker, see the gate list), CE
tenement coverage (needs a native sampler result), events sites (three source-reviewed, none field-surveyed;
recorded as a refusal if unreachable), ecology feeding and migration (feeding unsupported; migration only
behind its marker), weather and bright nights and infected deaths and vision without their markers, and the
Expansion AI patrols without the optional mods.
