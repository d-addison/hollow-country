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
  (create the `HollowCountry` folder first). If absent the core writes defaults there. All seven feature
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
- `interior_search` needs `interior_placement` (search also needs a started layout, `EnableInteriors` and
  `EnableSearch`). Placement needs your own `<profiles>\HollowCountry\interiors.json` and the measured
  catalog; without them the log says `missing/invalid manifest configuration; disabled`. The search
  economy binder (`HCSearchBinding`, registered before Interiors) binds a finite native supply when CE has
  settled; if it refuses, the log says `[HC Search Binding] refused: <reason>` and search stays refused.
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
configuration is missing. Batch B (pending landing) supplies the actual `cfggameplay.json` values.

### 6. Launch gap

The repo has no script that starts a persistent modded server or a modded client.
`tools/setup/Start-LocalClient.ps1` launches the vanilla client with no mods ("no mods requested") against
the running loopback server. Start the modded server and the modded client yourself with the `-mod=`
argument above and standard DayZ launch options. `Invoke-NativeSmoke.ps1` is a bounded disposable
smoke run with `verifySignatures=0` and BattlEye off. It is not for this session.

### 7. Rollback

Stop the server first and keep the failed candidate's logs.

- Addon: restore the previous `@HollowCountry` folder (and its matching client version), or remove the
  `-mod=` argument from the server and the client.
- Route B install: `python tools/package/deploy.py rollback --destination D:\HollowCountryPrivate --transaction <id> --server-stopped`.
  An interrupted install: `recover --destination ... --action abort` (or `resume`).
- Markers: delete the files under `<profiles>\HollowCountry\acceptance\`. No profile file means closed.
- Settings and state: restore the matching `settings.json` and storage backup from step 2. Never wipe a
  live save as a shortcut.
- CE changes, if you made any with `tools/package/economy.py`: `economy.py rollback --target <mission folder>`.

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
| #31 | Stamina drain and recovery | none; `HCStaminaConfiguration.Qualified` (closed but unused: stamina is controlled by `stamina.json`, not a marker) | Spawn on the server with the default `stamina.json` (experimental and enabled). Sprint on flat ground from full stamina to empty and time it, then rest and time the refill. Repeat with `Settings.Enabled` false (or the `vanilla` profile) for a baseline. Also jump and swing a melee weapon. | Intended: continuous drain at 50% of vanilla (about twice the sprint time) and recovery 25% faster (125%); jumps and melee keep normal cost. If `Stamina blocked` is logged the module did not engage and you see vanilla behavior. | `Created enabled stamina profile: 50% continuous drain, 125% recovery` on first run, and `Stamina blocked` on failure | [ ] | [ ] | |
| #31 | Weight bar and stamina bar HUD | none | Open the inventory, add and remove heavy items, watch the weight bar and the stamina bar. | Both bars show and the weight bar moves with load. Heavier load shortens endurance. | none (HUD observation); `Stamina blocked` if the profile fails | [ ] | [ ] | |
| #37 | Groups: create, rename, leave, disband (solo) | none; preference EnableGroups | Press M, use Create group, Rename, Leave, Disband in the group layout. Invite, Accept, Decline, Kick and Transfer lead need a second client (deferred). | Group is created and renamed on the server and the buttons enable and disable correctly. | `[HC Groups]` (absence of `service inactive` or `start refused`) | [ ] | [ ] | |
| #37 | Group icons (world and map) | none | With a group of one, look for your own group icon in the world and on the map. Teammate icons need a second client (deferred). | Own entry appears with the configured visibility. No icon for non-members. | `[HC Groups]` | [ ] | [ ] | |
| #37 | Interactive map (M): markers | none | Press M (the native map key). Double-click the map to place a marker, then New marker, Save marker, Delete marker. Pan and zoom. | Marker persists across closing and reopening the map and is removed on delete. Shared sync with others is deferred. | `[HC Groups]` | [ ] | [ ] | |
| #33 | Events and the O menu | none; preference in the events config | Press O (UAHollowCountryEvents). Use Join, Leave, Refresh, Close. | Menu opens with the layout. Without both event markers (see the reviewed-sites row below) expect no missions and no rewards. | `[HC Events] enabled preference, no active missions` and `[HC Events] optional menu input UAHollowCountryEvents is not declared/bound` | [ ] | [ ] | |
| — | Interiors: placement | `$profile:HollowCountry/acceptance/interior_placement.enable` (`HCInteriorRules.PlacementAccepted`, closed) | Needs `<profiles>\HollowCountry\interiors.json`. Create the marker, restart, walk to a measured Chernarus house with the diagnostic trial off. Look for furnishings, then use the doors, stairs and usual route. Remove the marker and restart to confirm placement stops. | Without the marker no placement happens. With it, bounded furnishing appears in the measured houses (24 props at most per interior) and doors, stairs and routes stay usable. If the config is missing you get the disabled line instead. | `[HC Interiors] placement EXPERIMENTAL local acceptance opt-in (interior_placement.enable)`; without it `[HC Interiors] placement disabled: collision/nav/replication proof pending` | [ ] | [ ] | |
| — | Interiors: search storage | `$profile:HollowCountry/acceptance/interior_search.enable` (`HCInteriorRules.SearchAccepted`, closed); also needs `interior_placement.enable` | Create both markers, restart, look at a cupboard or wardrobe in a placed house and use Search storage (6 s continuous action). Move away to cancel. | The search proof is opened, but on this build the action is still refused server-side because no search economy is bound (`BindSearchEconomy` has no caller). Record the refusal. Mark Pass only if a grant happens once per site and survives restart. | `[HC Interiors] search EXPERIMENTAL local acceptance opt-in (interior_search.enable)`; without it `[HC Interiors] search disabled: durable commit/CE/two-client proof pending`; also `[HC Search Supply]` | [ ] | [ ] | |
| — | CE coverage and loot economy | none; CE delta via economy.py (optional) | Only if you installed a CE delta: fly or walk across several towns and compare loot tiers. Otherwise skip and mark not run. | Loot appears where it fits the building type. No duplicate loot after restart. | `[HC Search Economy]` | [ ] | [ ] | |
| #52 | Crafting: salvage recipes | preference EnableCrafting | With the right tool in hands or inventory, combine: camo net, cable reel, large and medium leather, wooden bat, nailed bat, barbed bat, ruined crate (8 recipes). Tools: knife family, pliers, hacksaw or handsaw, crowbar or axe. | Each recipe takes time, needs its tool, damages or consumes as designed and yields the listed materials. Missing tool means no recipe. | `Crafting definition/config checks passed; runtime acceptance PENDING` | [ ] | [ ] | |
| #53 | Fuel siphon from a car | `$profile:HollowCountry/acceptance/fuel_siphon.enable` (and `HCFuelSiphonQualification.Qualified`) | Create the marker, restart the server. Hold an empty bottle or jerry can in hands, stand at a parked car (engine off, not moving, fuel above zero) at the fuel selection and choose Siphon fuel. Interrupt once, then complete once. | Fuel leaves the car tank and enters the container: finite, capped by container space, no refund on cancel mismatch. Without the marker the action never starts. | `Fuel siphon EXPERIMENTAL local acceptance opt-in active` (marker present) or `Fuel siphon not admitted` (absent); on error `Fuel siphon receipt mismatch` | [ ] | [ ] | |
| #56 | Taped light (flashlight on gun) | `HCTapedLightAdmission.Qualified` (closed); marker `$profile:HollowCountry/acceptance/taped_light.enable` | Read the start log. Create the marker, restart, carry duct tape and a flashlight, hold a native light-slot gun, use the tape-light action, toggle the light, then use Remove. Relog once with the light taped. | No marker: the action is refused and the light stays in inventory. With the marker: the flashlight attaches through the native light slot (no item created or deleted), the beam follows the gun, Remove returns the same flashlight, and the attachment survives the relog. Hosts outside the native light-slot pairs are post-v1 (#58). Known P2: a vanilla-attached light shows Remove but is denied. | `[HollowCountry] Taped light EXPERIMENTAL local acceptance opt-in active; runtime acceptance PENDING`, `[HollowCountry] Taped light not admitted; runtime acceptance PENDING`, `[HollowCountry] Taped light result=<n> runtime acceptance PENDING` | [ ] | [ ] | |
| #19 #44 | Infected: capability admission and variants | `HCInfectedQualification.CEAdoptionQualified` and `HCInfectedQualification.NativePackRoutesQualified` (closed); markers `$profile:HollowCountry/acceptance/infected_ce_adoption.enable` and `$profile:HollowCountry/acceptance/infected_pack_routes.enable` | Start the server and read the log. Then create `infected_ce_adoption` and `infected_pack_routes` (one at a time is fine), restart, wait for a cohort to be adopted or a pack route to run, and walk near infected in two or three towns (civilian and military). | No marker: the admission line lists requested versus admitted paths with reasons such as `ce_adoption_unqualified`; native behavior retained. With a marker: that path reads `admitted=1 reason=admitted`; CE adoption adopts and tracks native cohorts (needs `EnableHordes`), pack routes let the module steer an owned native pack. If prerequisites fail the module logs `[HC Infected] disabled: ...`. | `[HC Infected] capability admission`, then `[HC Infected] CE adoption EXPERIMENTAL local acceptance opt-in (infected_ce_adoption.enable)` or `[HC Infected] native pack routes EXPERIMENTAL local acceptance opt-in (infected_pack_routes.enable)` | [ ] | [ ] | |
| #20 #22 | Infected: doors and line of sight | none (source behavior) | Close a door between you and an infected, then open it. Break line of sight and re-acquire. | Infected use native door and perception behavior; no teleport and no omniscient tracking. | `[HC Infected]` | [ ] | [ ] | |
| #21 #22 | Infected: audio cues | none | Listen to footsteps, shuffling and contact sounds at distance and behind obstacles. Single-client only; the multi-client audio comparison is deferred. | Surfaces, distance and obstacles change what you hear. | `[HC Infected]` | [ ] | [ ] | |
| #19 #44 | Infected: injury and leg crawlers | `HCInfectedProfiles.ContactGuardQualified` (closed); marker `$profile:HollowCountry/acceptance/infected_contact_guard.enable` | Take a leg hit from an infected (or shoot one in the leg) and watch the movement. For the contact guard, create the marker, restart, stand behind a thin wall or fence an infected cannot reach through and let it swing, then retreat and check whether a delayed hit lands. | Wounded movement is readable, and a leg hit can make a crawler. Without the marker the guard stays pending. With it, an infected that cannot reach you has its strike suppressed (an experimental filter: a queued strike may still land, which is what this tests). | `[HC Infected] contact guard EXPERIMENTAL local acceptance opt-in (infected_contact_guard.enable)`; without it `[HC Infected] contact guard pending native wall-hit qualification` | [ ] | [ ] | |
| #21 #22 | Infected: investigation | `HCInfectedQualification.InvestigationQualified` (closed); marker `$profile:HollowCountry/acceptance/infected_investigation.enable` | Create the marker and restart. Make a noise (fire a suppressed or unsuppressed shot, break a window) out of sight of nearby infected, then watch whether up to two of them go to the last observed spot, search, and give up. Note which infected join in and which do not (injured crawlers, engaged and grouped infected do not). | Without the marker no scripted investigation occurs; native reaction only. With it, a bounded investigation toward a frozen observation (not your live position), no omniscient tracking and no teleport. Needs the native pack prerequisites. | `[HC Infected] investigation EXPERIMENTAL local acceptance opt-in (infected_investigation.enable)` and `investigation requested=1 admitted=1` in the admission line; without it `investigation_unqualified` | [ ] | [ ] | |
| #21 | Infected: alert chains | `HCInfectedQualification.SupplementaryChainsQualified` (closed); marker `$profile:HollowCountry/acceptance/infected_supplementary_chains.enable` | Create the marker and restart. Fight an infected in a group of several and watch whether neighbors relay the alarm, with and without a wall or distance between them. Needs `EnableAlertChains`. A second client is deferred, so judge relay audibility only from your own position. | Without the marker no scripted relay occurs. With it, neighbors can pick up a relayed alarm (bounded hops and cooldown, native hearing rules). Two-client audibility stays deferred. | `[HC Infected] supplementary chains EXPERIMENTAL local acceptance opt-in (infected_supplementary_chains.enable)`; without it `supplementary_chains_unqualified` in the admission line | [ ] | [ ] | |
| #21 | Infected: hordes | `HCInfectedQualification.MemberRecoveryQualified` and `HCInfectedQualification.HordeStimulusRoutesQualified` (closed); markers `$profile:HollowCountry/acceptance/infected_member_recovery.enable` and `$profile:HollowCountry/acceptance/infected_horde_routes.enable`; horde routes also needs `infected_pack_routes.enable` (and `infected_ce_adoption.enable` for a cohort to exist) | Create the markers you want, restart, wait and move around for at least one save interval, kill a member, then restart the server once. For horde routes, make a noise near a cohort and watch it retarget toward the clue rather than toward you. | Without markers no horde materialization; the state journal is validated and kept verbatim and population is unchanged. With member recovery, restart reconciles known members and retires dead or missing ones. With horde routes (plus pack routes), a cohort retargets to a bounded clue with a stall and cooldown. Without pack routes the reason is `horde_stimulus_routes_requires_pack_routes`. | `[HC Infected] member recovery EXPERIMENTAL local acceptance opt-in (infected_member_recovery.enable)` and `[HC Infected] horde stimulus routes EXPERIMENTAL local acceptance opt-in (infected_horde_routes.enable)`; without them `horde_stimulus_routes_unqualified` | [ ] | [ ] | |
| — | Infected: deaths | none | Kill an infected and observe the corpse, loot access and fall or fold. | Native death. A folded or ragdoll-like death is a feasibility goal only; full ragdoll is unconfirmed. | none | [ ] | [ ] | |
| #34 | Ecology | none; preference in ecology config | Watch animals and infected near water and food sources for a few minutes. | Observation and path adapter only: coverage partial, feeding and drinking and resource movement unsupported, native brains preserved. | `[HC Ecology] enabled observation/path adapter` or `[HC Ecology] explicitly disabled by operator` | [ ] | [ ] | |
| #63 #34 | Ecology migration (cohorts follow resources) | `HCEcologyMigrationQualification.Qualified` (closed); marker `$profile:HollowCountry/acceptance/ecology_migration.enable` plus the infected markers listed above | Create `ecology_migration`, `infected_pack_routes`, `infected_horde_routes` and `infected_investigation`, restart, and watch an infected cohort near a town for several minutes. | No marker: ordinary pack retargets are unchanged. With the markers: a complete cohort is submitted to migration instead of the ordinary route; an incomplete or refused cohort gets no fallback route (it holds). Failures quarantine migration, not the infected module. | `[HC Ecology] migration EXPERIMENTAL local acceptance opt-in; runtime acceptance PENDING`, `[HC Ecology] migration journal ready; schedules=...` or `[HC Ecology] migration not admitted; runtime acceptance PENDING` | [ ] | [ ] | |
| #15 #42 | Search economy binder | the interior markers (`interior_placement`, `interior_search`) | With both interior markers and a started layout, wait for CE to settle after start, then search a container in the evidenced house. | Search draws from a finite native supply: no item is created from nothing, a searched source is not refilled, and a refusal leaves search refused. | `[HC Search Binding] finite native supply bound; runtime acceptance PENDING`, `[HC Search Binding] refused: <reason>` or `[HC Search Binding] unavailable: register/start SearchBinding before Interiors; search remains refused` | [ ] | [ ] | |
| #13 #14 #20 | Interiors pack (profile install) | the interior markers | Install the pack with `python3 tools/package/interiors_profile.py install` (see its `--help`) into the server profile, start, and visit the one evidenced house. Roll back with its `rollback` command. | The pack installs with a receipt and rolls back cleanly. Only one house is evidenced on this build; measured layouts and rooms for the rest are still pending, so other houses stay vanilla. | `[HollowCountry]` interiors lines; `missing/invalid manifest configuration; disabled` when no pack is installed | [ ] | [ ] | |
| #36 | Expansion AI PvE patrols (optional addon) | `HCXAIQualification.Qualified` (closed); marker `$profile:HollowCountry/acceptance/pve_patrols.enable` | Subscribe to CF, Dabs Framework, Expansion-Animations, Expansion-Core (2291785308) and Expansion-AI (2792982069); load them and `@HollowCountryExpansionAI` after them. Merge `ai/AISettings.merge.json`, create the marker, restart (each restart is a fresh WorldSession) and walk near a patrol route. | Patrols spawn on the reviewed routes with leases, are retired on stop, and never spawn without the marker. Without Expansion the addon logs and does nothing. Known P2: the lease journal is never pruned, so after the history cap delete `expansion-ai-leases.json`. | `[HC Expansion AI] EXPERIMENTAL local acceptance opt-in (pve_patrols.enable); qualification pending` | [ ] | [ ] | Expansion is CC BY-NC-ND: subscribe only, never repack. |
| #35 | Weather and atmosphere | none; weather candidate via `tools/package/atmosphere.py` | If you installed a weather candidate, wait through a cycle (or time-accelerate) and note fog, overcast and light. | Changing atmosphere that stays readable and fair. No candidate installed means mark not run. | none (visual); check that the server log has no weather parse errors | [ ] | [ ] | |
| #30 | Firearms roster (vanilla, datamined vanilla, optional SNAFU allowlist) | none; SNAFU is Workshop 2443122116, never bundled, not installed locally | Spawn each supported firearm and fire it. SNAFU rows only if you installed that mod. | Weapons behave natively. Without the SNAFU mod the allowlist stays closed (fail-closed). | none until the firearms worker lands | [ ] | [ ] | |
| — | cfggameplay: temperatures | none; `enableCfgGameplayFile = 1;` | Stand outside through a day or night cycle, compare body temperature and shivering with vanilla. | Seasonal temperatures colder than vanilla but not harsh. | none (gameplay file values) | [ ] | [ ] | |
| — | cfggameplay: spawn kit | none; `enableCfgGameplayFile = 1;` | Create a new character and read the inventory. | Hardscrabble kit: worn randomised civilian clothes and one small item, no weapons. | none | [ ] | [ ] | |
| — | cfggameplay: weapon obstruction | none; `enableCfgGameplayFile = 1;` | Raise a weapon against a wall and against open air. | Weapon obstruction by nearby objects applies. | none | [ ] | [ ] | |
| — | cfggameplay: wet weight | none; `enableCfgGameplayFile = 1;` | Wear gear in the rain, check weight in the inventory, then dry it. | Wet gear weighs more than dry. | none | [ ] | [ ] | |
| — | cfggameplay: hit indicator | none; `enableCfgGameplayFile = 1;` | Take a hit (infected or fall) and watch the screen. | A stronger hit indicator than vanilla. | none | [ ] | [ ] | |
| — | cfggameplay: leg hits make crawlers | none; `enableCfgGameplayFile = 1;` | Take a leg hit and watch the movement. | A leg hit puts the player into a crawl as configured. | none | [ ] | [ ] | |

Rows tagged with "—" have no issue number found in the repo sources. Fill in the number when you map
results back to GitHub.

## Features pending landing

These are on worker branches and not in this checkout. Each row is unverifiable until the worker lands
and a rebuild is installed. Do not tick Pass for any row here until the landing commit is part of the
installed build. The marker column says what to re-run: regenerate the inventory (`acceptance_markers.py`)
after landing and add any new marker to the table above.

| Issue | Feature | Marker | Player steps (one client) | Expected observation | RPT line to grep | Pass | Fail | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| #35 | Weather (worker branch) | unknown until landed | Re-run the weather row. | pending landing: weather candidate and gate to be listed | `[HC Weather]` (name to confirm) | [ ] | [ ] | |
| #33 | Events (worker branch): reviewed sites, reach-the-site and recover-the-cache | `$profile:HollowCountry/acceptance/events.enable` AND `$profile:HollowCountry/acceptance/events_sites.enable` (both required; `HCEventQualification.Qualified` and `HCEventSitesGate.Qualified` stay closed) | Create both markers, restart the server, join with one client. Press O and Join a mission on a reviewed site (kamenka-supply-cache near 2512 / 2054, staroye-traffic-cache near 10676 / 4579, kumyrna-ambush-cache near 8393 / 5998; each is a stock static-event origin plus a (6.0, 10.4) offset, source-reviewed, not field-surveyed). Reach the site: walk to the marked point, stay within 15 m for 10 s. Recover the cache: find the SmallProtectorCase at the same point, pick it up (it must be in your inventory or hands), then open it and take the items. Restart the server once and look for the case again. | pending landing: reach-the-site completes only after about 10 s of continuous presence within 15 m and not from farther away. A case holding up to 4 vanilla items (BandageDressing, TunaCan, Matchbox, Chemlight_Green, MetalWire, Battery9V, Rag; at most 3 cases and 12 items per server session) appears at the site only once per site per session, and the recover mission completes when you carry it. After the restart a new session gets its own fresh allowance and no old case persists. If the case cannot hold every item it is kept with the partial content and logged; a point with unsuitable terrain height is refused with a log line. Surveyed stays false: report a site that is unreachable, inside geometry or overlapped by wrecks. | `[HC Events] EXPERIMENTAL local acceptance opt-in for reviewed sites and reward caches`, `[HC Events] reward cache created site` (with `items n/m`), `[HC Events] reward cache refused for site` or `reward journal fault` on refusal | [ ] | [ ] | |
| #37 | Groups r2 (worker branch) | unknown until landed | Re-run the group and map rows. | pending landing: second-round group behavior | `[HC Groups]` | [ ] | [ ] | |
| #52 | Crafting r2 (worker branch) | unknown until landed | Re-run the crafting row with the audited recipe set. | pending landing: extra recipes beyond the eight | `[HollowCountry] Crafting` | [ ] | [ ] | |
| — | Deaths (worker branch, feasibility) | unknown until landed | Kill infected and players; check corpse access and loot. | pending landing: fold or ragdoll-like deaths if feasible | not defined yet | [ ] | [ ] | |
| — | Noise/vision (worker branch) | unknown until landed | Make noise and break line of sight at different distances. | pending landing: hearing and vision rules for infected | `[HC Infected]` | [ ] | [ ] | |
| — | Batch A pathgraph (worker branch) | unknown until landed | Walk infected through doors and stairs; watch for stuck behavior. | pending landing: path graph behavior | not defined yet | [ ] | [ ] | |
| — | Batch B cfggameplay (worker branch) | `enableCfgGameplayFile = 1;` | Re-run the six cfggameplay rows. | pending landing: the actual `cfggameplay.json` values | none | [ ] | [ ] | |
| #30 | Firearms (worker branch) | unknown until landed | Re-run the firearms row, including the SNAFU allowlist if installed. | pending landing: the roster and allowlist | not defined yet | [ ] | [ ] | |
| — | Build-identity fix (worker branch) | unknown until landed | Start the server and read the build-support lines. | pending landing: scope is not documented in this checkout; confirm from the worker's PR | `[HC Infected] disabled: unsupported native source build` | [ ] | [ ] | |

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

These cannot give a "pass" this session, only a recorded refusal or a "not testable": taped light (service
unhooked, no qualified host), the infected complex paths (CE adoption, pack routes, investigation,
supplementary chains, member recovery, horde stimulus routes, contact guard) and interior placement and
search when run without their markers (each has a marker, see the gate list), CE coverage correction (needs a delta), events sites (three source-reviewed, none field-surveyed; recorded as a refusal if unreachable), ecology feeding and migration
(unsupported), weather (pending landing) and deaths (feasibility).
