# Admin test kit

One documented way to trigger and inspect every Hollow Country (HC) feature on a
test server. Runtime acceptance of every command here is pending: the commands are
authored and offline-tested only, and nothing has been observed in DayZ yet.

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
   the game's key binding options). The right panel holds the buttons below; the
   lower list shows the reply lines and the notice bar shows the short result.
3. Each command has a one second per-admin throttle, one queued command per server
   tick, and replayed tickets are refused. If a button seems to do nothing, wait a
   second and press again.

The menu has one shared value box, default `1`. The `day`, `memory` and `weather`
buttons read it; the value must be 1 to 4 decimal digits and the server validates
the range. Every other button ignores the box.

## Where the answer shows up

Every command prints one RPT line on the server and returns the same text to the
menu:

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
| Dormant infected | `dormant` | `kit` | refused by design |

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
