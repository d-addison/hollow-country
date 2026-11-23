# Admin test kit

One documented way to trigger and inspect every Hollow Country (HC) feature on a
test server. Runtime acceptance of every command here is pending: the commands are
authored and offline-tested only, and nothing has been observed in DayZ yet.

## Operator controls and removal (#203, w44)

Controls default on with `EnableAdminMap=true`. To opt out of the new controls,
create `$profile:HollowCountry/acceptance/AdminControls.disable` before startup;
remove it and restart to opt back in. The allowlist, one-command queue, ticket
replay guard and existing per-admin throttle remain authoritative. `status`
continues to use the existing operational-status hook: a ready admin transport
is not evidence that a missing body provider exists. Admission logs include
`feature=AdminControls` and `runtime=PENDING`. Once after a successful allowlist
startup, every camp and dormant control has an owner path, so no missing-controls line is
logged any more.

The server handlers and catalog registrations below are authored. The three camp
wire IDs use the existing authorized RPC ingress, replay guard and one-command
queue, and are offered by the catalog-driven UI. Runtime acceptance is pending.

| Command | Value | Behavior and limits |
| :--- | :--- | :--- |
| `camptier` | 0 to 3 | Persists the nearest recognised camp's tier through `HCCampModule.Commit` / `HCCampStore`. The entire candidate set must fit configured `HCAILimits.MaxCamps` and shared `HCTickWork().HCTake(1)` per row, otherwise no camp is changed. There is no new range cutoff. UTC rollback, inactive services and failed writes refuse; failed writes restore the previous in-memory tier. The next due normal camp scan reclassifies it. No clock aging, structures, claims, world facts, bodies or loot are fabricated. |
| `campvisit` | none | Selects a recognised camp under the same caps and asks `HCCampProbes.HCRequestVisitorParty` for a physical visit. The request goes through normal eligibility (tier 3, camp day 14 or later, not hidden, three real days since `LastVisit`), attendance, cooldown and shared budget checks. A naturally materialised party walks in through native doors, inspects storage and leaves; it never takes items, spawns in sight or teleports. A success debits `LastVisit` once. Refusals name a `CAMP_VISITOR_` or `BASE_RAID_` reason and change no cooldown. `camp_visitors.disable`, `camp_probes.disable` or `base_raid.disable` turns visits off. |
| `campraid` | none | Selects a recognised camp under the same caps and asks `HCCampProbes.HCRequestRaidParty` for the normal warned raid. The owner gets the camp warning first; nothing happens before `WarningSeconds`, and a returning group member or observer cancels it. A success debits `LastProbe`; refusals name a `BASE_RAID_` reason and change no cooldown. `camp_probes.disable` or `base_raid.disable` turns raids off. |
| `dormant` | none | Delegates to `HCInfectedVariety.HCAdminFreshDormant`: queues one fresh crawler group at the nearest authored variety place in range, under the normal fresh-body cap (corpses included). It refuses while variety is inactive or `infected_variety.disable` is present, for an invalid position, or while a request is already pending. No standing substitute or orphan body is created. |

Do not count successful tier persistence as a visitor/raid observation. Normal
camp classification, cooldowns, faction resources and observer-safe materializer
ownership still belong to their existing owners. Visits, raids and dormant groups
go through those owners' physical custody, routes and body outcomes; none has been
observed in DayZ yet. Camps that exist only as a building claim (no recognised
hearth camp row) cannot be targeted yet
([#212](https://github.com/d-addison/hollow-country/issues/212)). This worker introduces no new distances or numeric configuration fields;
0..3 is the existing camp store schema. COT-role authorization remains open; no
COT files or source were read during this work.

Catalog integration is applied in `scripts/3_Game/Admin/HCAdminCatalog.c`:
`camptier`, `campvisit` and `campraid` follow `camp`, with tier bounds 0 to 3.
Dormant help describes the variety fresh-body queue. `HCKnown`
continues to delegate to the catalog. `HCAdminStatus.c:HCAdminKit` lists the three
camp commands after `camp`; the dormant line is available only while infected
variety is active (`reason=variety-inactive` otherwise). Catalog/dispatch equality includes
`HCOperatorCommand`, and kit tests include all three IDs. No module slot,
MISSION_FILES entry, config.cpp or settings-registry edit is needed.

### Stopped-server overlay removal

Mission overlays run before feature settings and must be removed with their
receipt-backed installers. Stop the server, retain a backup, and run first:

```sh
python3 -B -m tools.package.overlay_remove --mission /path/to/private-mission --overlays loot vehicles --dry-run
python3 -B -m tools.package.overlay_remove --mission /path/to/private-mission --overlays loot vehicles --server-stopped
```

The command calls `loot_boost.rollback` then `travel.rollback`, newest first.
It rehearses both on a temporary mission copy before changing live files; a
later-layer drift refusal therefore leaves the live mission untouched. Each
installer still verifies its own receipts and backups at live rollback time.
This is resumable coordination, not a cross-installer atomic transaction: if an
external edit occurs during live rollback, preserve the remaining receipts,
reconcile the reported drift and rerun while stopped. Absent overlays are skipped.
`storage_*` saves are neither copied nor deleted. Symlinks, hard links and special
files in copied input refuse. Mission targets in Steam are rejected by the
existing target guard. `--server-stopped` is an operator acknowledgement, not a
process detector. Dry-run does not need that acknowledgement.

To remove just one layer, use `--overlays loot` or `--overlays vehicles`; receipt
drift still refuses incompatible ordering. Later optional/coverage installers
may pin travel's core or loot's prototype: remove those layers through their
existing receipt rollback commands first when the rehearsal requests it. This
tool does not silently remove unrelated installers. Output explicitly says
inventory was not removed and keeps `runtime=PENDING`.

**Inventory removal rebuilds the addon:** `inventory_sizes.py` generates a
`CfgVehicles` block inside the shared HC addon, so it is not a mission overlay.
Pass `--addon-source mods/HollowCountry` or `--addon-pbo <installed hollowcountry.pbo>`
together with `--pbo-out <new dir>` to remove it. The tool strips only the generated
block (it keeps the authored TortillaBag `helmetFlashlight` slot) and writes three
files: an unsigned `hollowcountry.no-inventory.pbo`, a receipt with sha256 values
and `runtime=PENDING`, and `config.cpp.diff`. Review the diff, then sign the PBO,
install it on the stopped server and give it to every client. Without an addon
source, `--overlays inventory` still refuses with `inventory receipt rollback
unavailable`. Feature flags alone cannot undo these bytes, and a loaded config
override only goes away after a restart on the replacement PBO.

### Native checks still required

With catalog integration applied, run DayZDiag and normal packaged server/client
loads with one client. Grep `feature=AdminControls`, `feature=CampVisitors`, `[HC CampVisitors] reserved walk=pending`,
`[HC Admin] cmd=camptier`, `cmd=campvisit`, `cmd=campraid`, `cmd=dormant`, and
`SCRIPT (E)`. Confirm the existing `status` owner row follows allowlist startup,
not catalog presence. With a recognised camp, test tiers 0 and 3, rejection of
out-of-schema raw values, save/restart and next-scan reclassification. A forced
tier must create no structures, items, world facts or actors. With the opt-out
file present at restart, tier writes and dormant requests must refuse; remove
it and restart to readmit controls. Verify an unallowlisted connected client cannot
run commands. Record visit/raid/dormant outcomes only from what the client
actually sees; a refusal reason is not an observed arrival. Rehearse removal against a disposable installed mission while stopped,
check byte hashes and untouched saves, then test a normal packaged restart.

### Spec, plan and tasks for this worker

Spec OPS-203: authorised commands use existing bounded owner services; missing
physical providers are explicit; stopped-server removal uses actual receipts and
never wipes saves. Given a stacked synthetic loot/travel installation, removal
restores exact bytes. Given later drift, rehearsal fails before any live write.
Given an invalid tier, unavailable camp or failed save, no successful tier change
is reported. Given missing body ports, no physical outcome is fabricated.

Plan: inspect the existing command/owner paths and installer functions; add
standard-library synthetic behavioral tests; add metadata-only camp adapter and
precise missing-hook adapters; coordinate receipt rollback through scratch;
document shared catalog integration, operator opt-out and acceptance gaps.

- [x] OPS-01: existing API/source inspection; shared budget, cap, persistence reuse.
- [x] OPS-02: tier adapter and missing-body refusal adapters; default-on opt-out.
- [x] OPS-03: loot/vehicle scratch rehearsal, live rollback, drift/link/stop guards.
- [x] OPS-04: focused behavioral tests and required static checks.
- [x] OPS-05: shared catalog/kit integration and corresponding shared test updates.
- [x] OPS-09: authorized catalog/RPC ingress regression; friend/PBO helper packaging
  and isolated bundle import, retaining explicit inventory refusal.
- [ ] OPS-06: physical dormant/visitor/raid ports and source/PBO inventory receipt rollback.
- [ ] OPS-07: COT-role access (explicitly excluded); shared save switch belongs to w45.
- [ ] OPS-08: DayZDiag, packaged server/client, single-client authorization/visibility,
  restart/persistence/removal and single-client cost observations; capacity budgets remain provisional.

The required specs were absent under this worktree's `docs/`; read-only copies
were subsequently inspected under `/code/dayzsa_mods/docs/`. Active owner decisions
and this worker's file boundaries take precedence. No git metadata or external
service was written, and no native/Expansion/COT source was copied.

Existing refusal expectations were retained: physical dormant spawning is still refused for a real
missing port, now explicitly named. Round 2 applies the catalog-set changes and retains the physical
refusal expectations. Offline results establish no DayZ behavior.

### Round 2 integration record (2026-11-19)

Spec/plan extension: expose the already-authored camp controls through the shared
catalog and kit; prove ingress authorization, unknown-ID refusal, throttle,
replay and bounded queue using authored methods and explicit synthetic RPC
out-parameter decoding; ship the removal coordinator with its existing helpers.
No new engine calls or settings were added. OPS-05 and OPS-09 are complete offline;
OPS-06 through OPS-08 remain open. Bundled `README.txt` contains removal commands,
stopped-server/backup instructions and the source-rebuild inventory limitation.

Offline results establish no DayZ behavior; no native acceptance follows from them.

## Which tool for what

| Need | Tool | Notes |
| :--- | :--- | :--- |
| Spawn vanilla items, vehicles, infected, animals; teleport; ESP; god mode; time; weather; player stats | COT (Community Online Tools) | COT has no knowledge of HC systems. A COT spawn bypasses HC caps, leases and persistence. |
| Spawn or clear Expansion AI, set faction, debug monitor | Expansion AI admin menu and chat commands | Gated by the `Admins` list in the Expansion AI settings. Independent of the HC allowlist. |
| Trigger, force, advance or inspect HC features | HC admin menu (this kit) | Goes through the HC allowlist, throttle, module caps and budgets. |

Rule of thumb: use COT to get yourself to the right place and time of day, then use
the HC admin menu to make the HC system do its normal work there. HC commands never
teleport you, never create loot, and never bypass a module's own caps. Where a
command cannot run for a real reason it refuses with a specific `reason`.

## Opening the HC admin menu

1. Stop the server, add your plain player id (at most 32 ids) to
   `$profile:HollowCountry/admins.json` as `{"PlainIds":[...]}`, and restart. The
   file is created on first start with `EnableAdminMap` on. Only listed admins may
   send commands. Never commit or paste ids (see `docs/ACCEPTANCE_CHECKLIST.md`).
2. Open the HC admin menu with the `UAHollowCountryAdmin` key binding (set it under
   the game's key binding options; the default is Pause). The window opens only
   after an authorized server reply. If that reply is late the client says
   "Still waiting for the server's admin reply..." once after 2.5 s; a silent
   server times out after ten seconds and the notification names `admins.json`
   and `EnableAdminMap`; silence does not prove that the user is not an admin.
   While the window is open, player movement and look are locked like other
   menus; Escape or the X button closes it. A session with no server reply for
   60 s closes the window and says so.
3. The centred dark window has a title, admin/request state, X close button,
   section tabs, scrolling command cards and a result console. Closing uses the
   existing scripted-menu focus/cursor/input lifecycle. Closing cancels any
   unsent read-only checks; an already sent request is not undone.

| Section | Commands / controls |
| :--- | :--- |
| Overview | `status`, `kit`, `list`, `snapshot`; **Run read-only checks** |
| Infected | `sitter`, `dormant`, `horde`, `clear`, `memory` |
| AI & Camps | `camp`, `holdout` |
| World & Events | `event`, `scene`, `radio`, `deaddrop`, `decay` |
| Economy | `loot`, `forage` |
| Time & Weather | `day`, `weather` |
| Map | Latest snapshot, route canvas, layer list and **Toggle layer** |

Each card provides a label, one-line explanation, read-only (green) or
world-changing (amber) tag, and **Run**. Position-dependent cards say that they
act at your position or inspect nearby state. Integer commands have their own
**− / value / +** controls, range and unit. Defaults are `1`: memory 0–3 shots,
weather 0–4 profiles, day 0–3650. Decimal input is validated and clamped; empty,
negative (for these nonnegative ranges), fractional, non-digit or overflowing
32-bit integer input is not sent. Future catalog ranges can use larger or signed
integers without another menu change.
Values reset to their catalog defaults when changing tabs.

Only one request is pending at a time. Action/value controls are disabled while
busy, including the 1.1-second client throttle (the server retains its one-second
per-sender limit and global queue cap of one). **Run read-only checks** sends
`status`, `kit`, then `list`, waiting for each validated reply and the throttle
before sending the next. No world-changing command runs automatically. A
10-second request timeout records an unknown server outcome and cancels remaining
checks without retrying. Changing tabs does not cancel the checks.

The Map section reuses the existing map, route projection, layer selection and
visibility toggle. Request a snapshot from Overview, then select Map. Marks
expire after 60 seconds as before. Routes reproject on snapshot/layer changes
and map mouse-wheel/release events; pan/zoom alignment still needs DayZ testing.

## Where the answer shows up

The console retains the latest **50 lines**, newest reply first, with local
`HH:MM:SS` timestamps, command names and green `ok` / red `refused` results. Reply
body lines keep their original order beneath the summary, wrap and grow vertically
inside the scroll area; text is not substring-truncated. A long reply can evict
older lines. Successful `status`, `kit` and `list` replies use their server notice
as the summary; other summaries retain the exact server result and reason.
Local validation/timeouts are explicitly labelled and are not server refusals.

Every command prints one result line on the server:

```
[HC Admin] cmd=<command> result=ok|refused reason=<reason>
```

Grep the server RPT for `[HC Admin] cmd=` to see every command, or for one command
such as `[HC Admin] cmd=horde`. A refusal is a normal outcome, not a bug: the
`reason` says which gate held.

## Discovering what is available

| Button | Command | What it does |
| :--- | :--- | :--- |
| Kit availability | `kit` | Prints one line per command: `[HC Admin] kit cmd=.. module=.. available=1\|0 reason=.. input=..`. Run it first. A command whose module is not running shows `available=0` and why. RPT: `[HC Admin] cmd=kit`, result `ok`, reason `bounded-command-list`. |
| State near me | `list` | Prints bounded nearby state: infected, infected-memory heat cells, dead drops, forage nodes, decaying towns. RPT: `[HC Admin] cmd=list`, result `ok`, reason `bounded-nearby-state`. |
| Module status | `status` | Module metrics for every running HC module, including infected memory, radio, dead drops, loot refresh, forage, settlement decay, weather days and body stories. RPT: `[HC Admin] cmd=status`. |
| Request snapshot | `snapshot` | Map layers: players, hold-outs, dead drops, shelters, events, leads, materializer candidates, infected LOD and variety. Needs `EnableDebugSnapshot`. Refusals: `EnableDebugSnapshot-off`, `snapshot-cooldown=5s`, `snapshot-queue-cap=1`. RPT: `[HC Admin] cmd=snapshot`. |

## HC commands

All commands act near the admin player's current position and respect the same
caps and budgets as the normal systems. "Hook" means the command primes the
owner's own normal tick; it never creates a parallel spawner or duplicate loot.

| Command | Input | What it does and caps | Common refusal reasons |
| :--- | :--- | :--- | :--- |
| `sitter` | none | Creates one sitter infected 8 m ahead through the normal infected admission. Cap: one admin sitter at a time (includes the corpse). | `infected-admission-unavailable`, `sitter-body-cap=1; includes-corpse`, `infected-tracking-or-registration-cap`, `forward-vector-unavailable`, `placement-clearance-or-query-cap; use-open-flat-ground`, `native-create-or-track-refused`, `class-missing-HC_ZmbM_Sitter` (shown by `kit`) |
| `clear` | none | Deletes only the admin sitter. Other infected are untouched. | `no-admin-sitter` |
| `dormant` | none | Always refused by design: fresh spawns are skipped and there is no shared body lease or dormant spawn policy. | `InfectedVariety-fresh-spawn-skipped; no-shared-body-lease-or-dormant-spawn-policy` |
| `horde` | none | Asks the normal infected module to adopt a native cohort within 100 m. Cohort size follows local heat (see `memory`); the horde budget and quarantine still apply. | `horde-admission-unavailable`, `horde-budget-cap`, `no-eligible-native-cohort-within-100m`, `horde-clock-unavailable`, `normal-adoption-refused` |
| `memory` | 0 to 3 | Records 0 to 3 shots of infected-memory heat in the 500 m cell at your position. Heat steers the next horde cohort size (3 + round(3 x heat), capped by what is available) and the alert response limit (6 + round(6 x heat)). Value 0 clears the cell. Reply shows `heat`, `cohort` and `alert_limit`. | `infected-memory-unavailable`, `heat-shots-0-to-3`, `heat-position-invalid`, `no-heat-in-this-cell` |
| `scene` | none | Places the nearest due reviewed scene through the normal scene director. Cap: 2 scene leases. | `scene-service-unavailable`, `scene-lease-cap=2`, `no-unplaced-reviewed-scene`, `scene-clock-unavailable`, `scene-not-due`, `normal-scene-director-refused` |
| `event` | none | Announces and starts the nearest reviewed event site through the normal event director. Join it with the normal rules. | `event-service-or-site-cap-unavailable`, `no-reviewed-event-site`, `roster-gate-or-normal-runtime-admission-refused`, `normal-event-director-code=N` |
| `camp` | none | Runs the normal camp evaluation on the nearest recognised camp within 100 m. No forced age, tier or theft. Cap: 32 observers. | `camp-service-unavailable`, `no-recognised-camp-within-100m`, `camp-clock-unavailable`, `camp-observer-cap=32`, `normal-camp-criteria-or-cooldown` |
| `holdout` | none | Runs the normal occupancy transition on the nearest hold-out within 100 m. No body or loot is fabricated. | `holdout-service-unavailable`, `no-holdout-within-100m`, `holdout-clock-unavailable`, `normal-occupancy-cooldown-cache-body-or-site-cap`, `holdout-persistence-refused` |
| `day` | 0 to 3650 | Sets the persisted escalation day. Camp age and other clocks are unchanged. | `escalation-clock-unavailable`, `escalation-persistence-refused` |
| `radio` | none | Clears the radio rate limit on a channel you can hear so the normal radio tick sends the next line. Requires a powered personal radio, receiving, tuned to 87.8, 89.5, 91.3, 94.6 or 96.6. Minimum gap between lines is 600 s. | `radio-service-unavailable`, `radio-channel-busy`, `radio-channel-save-refused`, `no-receiving-radio` |
| `deaddrop` | none | Makes the nearest dead drop within 1000 m due. The next 60 s tick runs the normal crate and one house-item deposit; needs a hold-out house and a player within 500 m of the crate. Cap: 4 deposits per drop. | `dead-drop-service-unavailable`, `no-dead-drop-within-1000m`, `dead-drop-quarantined`, `deposits-exhausted`, `dead-drop-persistence-refused` |
| `loot` | none | Ages the oldest pending loot-refresh timer so the next tick marks it ready. No loot is created; search that container again to see the refresh. | `loot-refresh-service-unavailable`, `no-pending-refresh-timer`, `loot-refresh-clock-behind`, `refresh-timer-save-refused` |
| `forage` | none | Clears the forage cell at your position so the normal tick can spawn one node when you stand in forest. Season months 6 to 11, forest surface, 30 m from players. Caps: 3 live nodes per 200 m cell and 40 total. | `forage-service-unavailable`, `forage-out-of-season` |
| `decay` | none | Queues the nearest town within 1000 m for the normal settlement decay step; visuals still follow the normal rules. | `decay-not-initialised`, `history-scan-in-progress`, `no-town-within-1000m` |
| `weather` | 0 to 4 | Overrides the HC weather-day profile for 1800 s: 0 clears the override, 1 plain, 2 calm, 3 fog, 4 bad. Fog shows 05:00 to 09:00 game time and bad shows by day, so set the time of day first. The override covers the next 63 days of seeds. Needs `EnableGrade` and `EnableAtmosphere`. | `weather-days-inactive`, `weather-code-0-clear-1-plain-2-calm-3-fog-4-bad`, `weather-clock-unavailable`, `no-matching-seed-day-within-64-days` |

Every command can also refuse with `live-sender-unavailable-or-player-cap=32` or
`module-unavailable` (the module is disabled or not running; `kit` shows which).

## RPT grep lines

Use `grep` on the server RPT with these exact prefixes:

| Command | Grep |
| :--- | :--- |
| `status` | `[HC Admin] cmd=status` |
| `snapshot` | `[HC Admin] cmd=snapshot` |
| `kit` | `[HC Admin] cmd=kit` (also `[HC Admin] kit cmd=` for the lines) |
| `list` | `[HC Admin] cmd=list` (also `[HC Admin] list ` for the lines) |
| `sitter` | `[HC Admin] cmd=sitter` |
| `clear` | `[HC Admin] cmd=clear` |
| `dormant` | `[HC Admin] cmd=dormant` |
| `horde` | `[HC Admin] cmd=horde` |
| `memory` | `[HC Admin] cmd=memory` |
| `scene` | `[HC Admin] cmd=scene` |
| `event` | `[HC Admin] cmd=event` |
| `camp` | `[HC Admin] cmd=camp` |
| `holdout` | `[HC Admin] cmd=holdout` |
| `day` | `[HC Admin] cmd=day` |
| `radio` | `[HC Admin] cmd=radio` |
| `deaddrop` | `[HC Admin] cmd=deaddrop` |
| `loot` | `[HC Admin] cmd=loot` |
| `forage` | `[HC Admin] cmd=forage` |
| `decay` | `[HC Admin] cmd=decay` |
| `weather` | `[HC Admin] cmd=weather` |

Module-side lines (what the normal system did after the hook) use the
`[HollowCountry] V2 ...` prefix, for example `V2 dead drop deposit`, `V2 radio line
freq=`, `V2 loot refresh refreshed=`, `V2 infected memory cells=`, `V2 settlement
decay towns=`. Grep `[HollowCountry]` after a command to see the effect.

## Feature coverage audit

| Feature | Trigger | Inspect | Gap |
| :--- | :--- | :--- | :--- |
| Infected sitter | `sitter`, `clear` | `list`, `status` | none |
| Horde adoption | `horde`, `memory` steering | `status`, `list` | none |
| Infected memory | `memory` | `list`, `status`, snapshot | none |
| Events | `event` | `status`, snapshot | none |
| Scenes | `scene` | `status` | none |
| Camps | `camp` | `status` | none |
| Hold-outs | `holdout` | `status`, snapshot | none |
| Escalation clock | `day` | `status` | none |
| Radio chatter | `radio` | `status` | needs a powered radio |
| Dead drops | `deaddrop` | `list`, `status`, snapshot | needs a nearby player |
| Loot refresh | `loot` | `status` | needs a searched container |
| Forage | `forage` | `list`, `status` | season and forest only |
| Settlement decay | `decay` | `list`, `status` | none |
| Weather days | `weather` | `status` | COT weather conflicts (see below) |
| Body stories | none | `status` | inspect-only: random, cap 3, no admin force |
| Infected variety, doors, reach, LOD | none | snapshot (variety, LOD) | no trigger; they follow normal infected play |
| Horde migration, shelters, wreck salvage, vehicle flip | none | snapshot (shelters) | no trigger yet; play normally |
| Signs of life, Morse, team ping, progression, crafting, meal buffs | none | none | no admin trigger; test by playing |
| Faction conflict, camp respawn, pickers, materializer | none | snapshot (materializer) | no admin trigger; test by playing |
| Dormant infected | `dormant` | `kit` | queues a fresh crawler group at the nearest variety place; refused at the fresh-body cap |

Wildlife, visual seasons and claim-a-building bases are not in the source yet, so
they have nothing to trigger.

## COT notes (read-only research, not shipped)

Citations are PBO-internal paths from the COT scripts package.

- Spawn infected: `4_World\CommunityOnlineTools\Classes\StaticFunctions.c:160-162`
  (`SpawnInfected`), vanilla list at `3_Game\CommunityOnlineTools\StaticFunctions.c:192`,
  key bindings and the `Entity.Spawn.Position` permission at
  `JMObjectSpawnerModule.c:368-369` and `:422-434`.
- Object spawner: `JMObjectSpawnerModule.c:591-662` and `JMObjectSpawnerForm.c:333-342`.
  Any class name works, including HC classes, but it bypasses HC lifecycle and caps.
- Teleport: `JMPlayerModule.c:1025`, `:1095`, `:1148`; teleport form
  `JMTeleportForm.c:1559-1572`; map teleport `JMMapForm.c:145`.
- Weather and time: `JMWeatherModule.c:114` (`SetDate`), `:152-190` (fog, overcast,
  rain), form `JMWeatherFormTabTime.c:148`.
- ESP: `JMESPModule.c` (zombie handling around 3138, delete/heal/move inputs 746-762).
- Vehicles: `JMVehiclesModule.c`. Player cheats: `JMConstants.c:15-18, 207-221`.
- Events module: `JMEventsModule.c:1-30` (no sidebar button), `JMEventsAdapter.c:41-67`
  (heli crash, contaminated zone, airdrop).

Caveat: the COT weather module changes `MissionWeather` and
`SetWeatherUpdateFreeze` (`JMWeatherModule.c:678-695, 887-902`). HC weather days
treat that as a foreign controller and stand down. After using COT weather, expect
the `weather` command to have no visible effect until the foreign control ends.

## Expansion AI notes

Citations are PBO-internal paths from the Expansion AI scripts package.

- `5_Mission\DayZExpansion_AI\eAICommandManager.c:17-21` registers AI, zombie, wolf,
  bear spawn and clear-all RPCs; handlers at `:422`, `:486`, `:511`, `:536`, `:562`,
  each admin-gated at `:454`, `:497`, `:522`, `:547`, `:570`.
- The admin list is `Admins` in the AI settings
  (`3_Game\DayZExpansion_AI\Settings\ExpansionAISettings.c:39`, `IsAdmin` at `:495-503`).
- Command menu: `5_Mission\DayZExpansion_AI\GUI\eAICommandMenu.c:75`, opened from
  `MissionGameplay.c:78-80`. Debug monitor: `ExpansionWorld.c:45-99`.
- Patrol debug and delete: `eAIPatrol.c:58-78`; survivor classes `eAISurvivor.c:42-89`.

Expansion-spawned AI is not owned by HC; use it to stage encounters, and use the HC
menu for HC-owned state.

## End-to-end test session checklist

1. Start the server with `EnableDebugSnapshot` on and your plain id in `admins.json`.
   Join with COT and Expansion loaded; check the RPT has no `SCRIPT (E)` lines.
2. Press `kit`. Note every command with `available=0` and its reason.
3. Press `status`, then `snapshot`. Confirm layers appear on the map.
4. With COT, move to open flat ground near a town at about 06:00. Press `sitter`
   (check 8 m ahead), then `clear`.
5. Press `memory` with value 2, then `list` to see the heat cell, then `horde`.
   Note the cohort size, then `memory` with value 0.
6. Near a reviewed scene or event site press `scene` and `event`. Join through the
   normal rules.
7. Near a camp, `camp`; near a hold-out, `holdout`; confirm the module RPT lines.
8. Carry a powered personal radio tuned to 94.6 and press `radio`; wait up to one
   tick for the line.
9. Near a dead drop with a player within 500 m, press `deaddrop`, wait 60 s, check
   `V2 dead drop deposit`.
10. Search a container, press `loot`, search it again.
11. In season (months 6 to 11) in forest, press `forage`, wait for one node.
12. Near a town press `decay`; after a few seconds look at the visuals.
13. Set the time with COT to 05:30, press `weather` with value 3 (fog); try value 4
    by day; value 0 to clear.
14. Press `day` with a new value and confirm `persisted-escalation-day`.
15. Record every `[HC Admin] cmd=` line in the test notes. Anything unobserved stays
    pending; nothing here is runtime acceptance.


## Adding an admin command

The shared `scripts/3_Game/Admin/HCAdminCatalog.c` is the command UI and ingress
allowlist's single source of truth. Add one `HCAdd(...)` line in an existing
section and implement the server handler in `HCDispatch` / `HCCommand` (or its
`HCExtra` helper). No button, layout, menu click branch or separate `HCKnown`
entry is needed. Metadata arguments are: wire id, section id, label, one-line
help, read-only flag, acts-at-my-position flag, integer flag, minimum, maximum,
default and unit. Non-value commands use `false, 0, 0, 0, ""` for the value fields.
For a new section, add one `HCSection(id, label, help)` declaration as well.

Keep value bounds aligned with the server's validation/clamps; the server remains
authoritative. Update command documentation and behavioral tests when introducing
new gameplay behavior. The UI tests compare the entire catalog against the
actual dispatch branches, including `HCExtra`, so dead cards and omitted handlers
fail offline. The existing kit-availability report remains separately maintained
server documentation; it is not used to build or enable UI cards.

Run the focused checks and standard-library layout linter:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_layout_lint -v
python3 -B -m tools.validate.layout_lint
python3 -B -m tools.validate.enforce_lint --no-native
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v
```

The layout linter checks braces, native/vanilla widget classes, duplicate names,
literal script lookups against the layouts loaded in that source file, and
layout paths against the packer's existing allowlist. A script using a root
supplied by another script produces an explicit review finding; dynamic lookup
names are outside its scope. This does not establish rendering or widget events.

## Admin UI implementation record (2026-11-18)

Banso spec / plan / tasks for this confined worker are recorded here within the
owned documentation. Base: `915aef1`, branch `hc/admin-ui`. The supplied shared
brief and both named spec paths were absent in this worktree; the specifications
were read from `/code/dayzsa_mods/docs/`. The active owner request takes precedence
over older assumptions. No git metadata changes or lifecycle dispatch were run.

Spec: expose all 20 existing wire commands across seven sections, preserve the
server's behavior, authentication/open path and native menu lifecycle, and keep
UI work and history bounded. Author original vanilla-only layouts; no COT source
was read, copied or adapted. Given a valid admin session, selecting a tab shows
that catalog section's cards. Given a pending request, Run cannot dispatch. Given
a reply, the console shows its result/reason and body; given a timeout, the batch
stops with no retry.

Plan: shared 3_Game catalog → server HCKnown delegation only → original window
and templates → generic menu cards → reply-driven client console and serial
read-only queue → deterministic lint, behavioral tests and package inspection.
Native evidence: installed `scripts-1.30.164289/1_Core/proto/EnWidgets.c` for all
used widget classes/methods/flags; `2_GameLib/tools.c` for ScriptInvoker;
`EnSystem.c` for timestamps; `EnConvert.c` for zero-padded time;
`3_Game/gameplay.c` for MapWidget; `UIScriptedMenu.c` for focus/cursor/input and
mouse events. Vanilla GUI layout syntax was inspected in the local cache's
`wine-server-20261116/dta/gui.pbo` (camera tool spacers/scroll and connection
dialogue wrapping), because the supplied `/mnt/d/.../gui.pbo` path was absent.
No native files are shipped.

Tasks / acceptance trace:

- [x] UI-01: catalog metadata, sections and HCKnown; dispatch-set and value-bound checks.
- [x] UI-02: centred window, tabs, cards, tags, validated/clamped value controls, map reuse.
- [x] UI-03: bounded timestamped console, busy controls, serial checks, timeout/cancel behavior.
- [x] UI-04: standard-library layout lint and deterministic behavioral tests; RED/GREEN below.
- [ ] UI-05: DayZDiag and normal packaged client/server load, all 20 buttons and refusal reasons,
  initial key notification, close/Escape/focus/input, tab highlighting, small-screen scrolling,
  wrapped full replies, map layers and pan/zoom route alignment; reconnect/death/expiry.
- [ ] UI-06: single-client visibility/authorization/snapshot behavior and single-client cost observations; larger-load budgets remain provisional.
  No runtime acceptance or production qualification is granted by offline checks.

Visual result is **unrendered until someone opens it in DayZ**. Budgets remain
provisional; runtime acceptance is pending.

Offline evidence is source checks only. `python3 -B tools/validate/layout_lint.py` reports zero admin
findings; its review findings are `HCMapOverlay`, `HCGrid`, `HCNavigation` and `HCKnownEvents` lookups in
`5_Mission/Groups/HCGroupMapLayers.c`. They exist in `hc_group_map.layout`, whose root is passed by
`HCGroupMapMenu`; the per-file linter cannot trace that borrowed root. No runtime acceptance follows.

## Admin-only test teleport (w67-admintp)

This explicit owner test tool moves only the allowlisted sender returned by
`HCAdminModule.HCPlayer(sender)`. It never moves AI or another player. It is
admitted unverified and defaults on; gameplay movement rules remain applicable
to gameplay systems. Native placement, collision and replication acceptance is
pending.

Use the existing HC admin menu Overview cards:

| Command | Value | Behavior |
| :--- | :--- | :--- |
| `tplist` | Page, 0..255 | Reads the server-built snapshot, returning at most `PageSize` lines as `index: name`. Page values clamp to the available pages. No coordinates or player identities are accepted from the client. |
| `tp` | Destination index, 0..255 | Clamps again on the server to the actual snapshot size. Refuses during catalog construction or if no tested ground candidate is available. Moves only the requesting live admin. |
| `tprefresh` | None | Explicitly rebuilds the destination snapshot over bounded core ticks, incorporating newly recognised camps/holdouts. Teleport refuses until rebuilding completes. Indices stay fixed between refreshes; run `tplist` again after refreshing. |

The snapshot includes the first waypoint of HC-authored Expansion AI sites,
recognised camp/claim encounter anchors, holdout house anchors and stock
`NameCityCapital`/`NameCity`/`NameVillage` localities. Localities use the same
CfgWorlds Names read pattern as `HCGroupPlaces.NativeNames`, with a retained
cursor instead of a synchronous scan. Sites use the operator's
`$profile:HollowCountry/expansion-ai-sites.json`, falling back to the existing
`$mission:hollow-country/ai/sites.json`. These are authored destinations, not a
claim of currently active AI. Incidents and events come first, then camps,
holdouts and localities; AI sites fill the slots left under `MaxDestinations`,
sampled at an even stride across the site list so every region stays
reachable. The Names scan examines the first `MaxNameEntries` entries. Refresh samples current camps/holdouts; it does not
reload site policy. Restart after changing site policy.

There is no public read-only active-situation position accessor on
`HCSituationDirector` in this base. The conditional nearest-active-situation
entry is therefore omitted; no private director state, body scan or AI knowledge
is fabricated. No new provider, mission data or module slot is required.

The existing allowlist, server RPC handler, ticket replay checks, per-admin
one-second command cadence and single-command core-tick queue are authoritative.
Unauthorized RPCs retain the anonymous `cmd=request` refusal before decoding.
`tp` also rechecks server authority, authorization, `EnableAdminMap`,
`HCOperatorControls`, both disable files and player state at execution. Vehicle
occupancy, unconsciousness and restraint refuse. Only the sender's live player
is resolved; there is no target-player argument.

`HCFindGround` examines at most `SearchAttempts` candidates, starting at the
anchor then testing cardinal offsets in `SearchStepM` rings. Every candidate
uses `HCTickWork().HCTake(1)` and the cooperative `HCPerfSlices`/`HCWorkBudget`
guard. Exhaustion refuses without moving. Ground placement uses
`GetGame().SurfaceY(x,z) + GroundOffsetM`, strict world bounds with clearance,
sea/pond rejection, five terrain-height samples and a native collision box
excluding only the requesting player. An obstructed building anchor is never
used as a fallback. This bounds source work; it cannot prove collision-box
behavior, clear ground, safe streaming or replication in DayZ.

Controls default on. Opt out with
`$profile:HollowCountry/acceptance/AdminTeleport.disable`,
`acceptance/AdminControls.disable` or `EnableAdminMap=false`.
Teleport checks the disable files at execution; restart after removing a file
that disabled startup. The automatically created owning config DTO is
`$profile:HollowCountry/admin-teleport.json`. Missing JSON fields retain the
listed defaults through `HCJsonFields`; invalid values refuse configuration.
Recovery uses the shared JSON store intent/backup guards. Stop the server before
editing this file, then restart.

| Config field | Default | Accepted range |
| :--- | :--- | :--- |
| `Version` | 2 | 1..2 (a version 1 file with the old 262144 `SiteBytes` default loads as 1048576) |
| `ConfigBytes` | 4096 | 4096 (fixed bootstrap schema cap) |
| `SiteBytes` | 1048576 | 4096..1048576 bytes |
| `Enabled` | true | boolean |
| `MaxDestinations` | 256 | 1..256 |
| `MaxNameEntries` | 512 | 1..2048 |
| `RowsPerTick` | 8 | 1..32 |
| `PageSize` | 32 | 1..64 |
| `SearchAttempts` | 16 | 1..64 |
| `SearchStepM` | 4 | 1..25 m |
| `GroundOffsetM` | 0.2 | 0.05..1 m |
| `ClearanceWidthM` | 1 | 0.5..3 m |
| `ClearanceHeightM` | 2 | 1.8..4 m |
| `MaxSlopeDeltaM` | 0.4 | 0.1..1 m |
| `BoundaryMarginM` | 2 | 1..10 m |

The 256 destination and 64 reply-line ceilings are protocol safety limits.
Numeric tuning lives in this owning DTO; it does not add HCSettings registry
fields. Effective readiness is derived through `HCGetOperationalStatus` and
`HCModuleReadiness.HCDerive`: catalog construction or a real config/site fault
makes the running AdminMap owner degraded; a successfully built catalog permits
ready with native acceptance pending. A missing native verdict never blocks it.
An explicitly disabled teleport leaves the existing transport available.

Native API evidence is recorded at the top of `HCAdminTeleport.c`, using the
installed `scripts-1.30.164289` cache. In particular,
`3_Game/Entities/Object.c:294` declares `SetPosition`, and
`4_World/Plugins/PluginBase/PluginDeveloper/DeveloperTeleport.c:141-143` uses the
server player's native `SetPosition` path. `3_Game/Global/Game.c:1176` declares
`SurfaceY`, `:1196-1197` declare water tests, `:1333` declares `IsBoxColliding`,
and `3_Game/Global/World.c:82` supplies world size. No Expansion API is called
and no Expansion source is copied.

### w67 spec, plan, tasks and behavioral evidence

Requirement: an authorized admin can inspect bounded destination indices and
jump to a checked ground candidate for testing; every invalid authority/state,
off switch, unavailable snapshot or failed ground search leaves the player
unmoved. Plan: reuse admin ingress and generic catalog picker, build the snapshot
incrementally from existing sources, derive status, then use native sender-only
placement. Source/test/doc tasks are complete; native acceptance tasks are open.

Offline checks establish no DayZ behavior; the native checklist below is open.

### w67 native checklist (pending)

Boot DayZDiag and a normal packaged server with matching clients. Grep
`feature=AdminTeleport`, `runtime=PENDING`, `[HC AdminTeleport]`,
`[HC Admin] cmd=tplist`, `[HC Admin] cmd=tprefresh`, `[HC Admin] cmd=tp dest=`
and `SCRIPT (E)`. The teleport result is
`[HC Admin] cmd=tp dest=<index> ok|refused reason=<reason>`; it includes no player
name, account identifier or destination name. `tplist` names destinations only
in the authorized reply, not in the server log.

With one client, verify an allowlisted admin can list several pages, refresh
and reach town, AI site, camp and holdout areas on clear terrain. Verify snapshot
building, water, a building obstruction, steep ground, world-edge candidates,
vehicle occupancy, unconsciousness, restraint and each opt-out refuse with no
movement. Confirm raw negative/oversized indices clamp server-side and existing
cadence/replay protections still apply. Confirm unrelated AI remain unchanged; observe loading, collision and network replication.
Record these results before accepting runtime behavior. No DayZ result is
established by the synthetic suite.
