# Scripted player (autoplayer)

Owner goal (2026-11-24): a scripted client that walks, loots, fights, eats, drives and opens menus,
so the soak and the release gate need no person at the keyboard. This page covers what the
scripted client can and cannot do on a retail client, which native entry points it uses, and how
it recovers from failures. The code is dev-only and lives in `mods/HollowCountryTest` (never
shipped); the step files come from `tools/testing/driver_script.py`.

Truth order still applies: an offline plan or unit test never shows DayZ behaviour. Every new
step kind stays unverified until a native run logs its `[HC Driver]` line (see "Native
verification order").

## Rules the bot follows

- It plays like a player. It uses only the local player's `HumanInputController` overrides, the
  client action manager (`ActionManagerClient.PerformActionStart`) with real raycast targets,
  and the predictive inventory requests a mouse drag would send. It never teleports, never calls
  `SetPosition` and never spawns an item server-side instead of looting. It has no god mode, never
  increments a counter itself, and never reads anything that only the server knows.
- Setup fixtures (`HCTestSetupFixtures`, `HCTestReachFixtures`) stay admin-gated, server-side and
  `fixture=1`. The autoplayer adds no new fixture. The vehicle phase drives the car that the
  existing `fx_car_side` fixture already places.
- The driver logs one `[HC Driver] step=<id> kind=<kind> result=<ok|refused|unsupported|timeout>
  detail=<text>` line per step (the detail is capped at 160 characters), plus one `done` line.
  It never prints a name, an id, an address or a path.
- Work per frame is bounded. Each frame runs one step update, casts at most one raycast and makes
  at most one object query per scan period, and reuses its arrays.

## Coverage

### R3 smoke categories (release gate client step)

| Category | Signal | Before | Autoplayer step |
|---|---|---|---|
| map | ClientUI/map_open | driven (`menu map`, opens the HC M map like the key, b7a2ba72) | R3 route `menu map` |
| inventory | ClientUI/inventory_open | driven (`menu inventory`) | R3 route `menu inventory` |
| groups | Groups/menu_open | driven (the HC M map is the group menu) | R3 route `menu map` |
| admin | AdminMap/window_open | driven (`menu admin`, ticks HCAdminClient, b7a2ba72) | R3 route `menu admin` |
| ai | optional-expansion-human-ai/site_radius_entered | the walk_ai walk happened to cross a radius | new `enter zone=site` step: walks out, then in, and holds until the server confirms |
| event | Events/mission_radius_entered | the walk_zone walk only counts if a mission happened to be published there | new `enter zone=mission` step: reads the published mission zones the client already has (HCMissionBeaconStore), walks in from outside, and holds until the server confirms |

Since 2026-11-24 all six categories run without a person through
`release_gate --client-mode scripted` (the default). The human path is
`--client-mode human`.

### Every default-on feature in the reach map

The table is generated from `tools/testing/soak_phases.json`. Each module/phase/how group is one
row. The Class column has these values:

- **driven**: a step, a setup fixture or background timers reach the feature on one client today.
- **new driver work**: the autoplayer adds the step that reaches it.
- **impossible: fire/melee**: a scripted retail client cannot press fire or melee (see
  "Physically impossible"). The setup fixture keeps the feature covered, and a human trigger
  remains the only player path.
- **friend_playtest**: needs a second player. This is never claimed.
- **owner_check**: no repo data and no allowed movement can reach it on one scripted client.

| Phase | Module | Features | Class | How |
|---|---|---|---|---|
| actions | Crafting | completed_operations, recipe_completed | driven | steps action:craft; gear |
| actions | DeadDrops | cache_bound, cache_row_checked | driven | steps admin:deaddrop |
| actions | InfectedDoors | door_pressure | driven | steps action:close_door; fixture fx_barricade |
| actions | InfectedDoors | nav_door_action | driven | steps action:close_door,action:search |
| actions | Interiors | house_search_completed | driven | steps action:search |
| actions | LootRefresh | refreshed_operations, timer_rearmed | driven | steps admin:loot |
| actions | Morse | reports_delivered | driven | steps action:radio,admin:radio; gear |
| actions | Radio | delivered_operations, report_delivered | driven | steps action:radio,admin:radio; gear |
| actions | SearchBinding | house_bound | driven | steps action:search |
| actions | SettlementDecay | changed_operations, prop_placed | driven | steps admin:decay |
| actions | TapedHelmetMounts | light_mounted, native_wearable_operations | driven | steps action:mount; gear |
| actions | TapedLight | light_mounted, native_light_operations | driven | steps action:mount; gear |
| actions | TapedPackMounts | light_mounted, native_wearable_operations | driven | steps action:mount; gear |
| actions | VehicleFlip | impulse_applied, pulses_operations | driven | steps action:flip; fixture fx_car_side; gear |
| actions | WreckSalvage | part_created, parts_created | driven | steps action:salvage; fixture fx_wreck; gear |
| fixtures | AIIncidents | lease_step, response_started | driven | fixture fx_incident |
| fixtures | AISelfDefence | hit_reaction | impossible: fire/melee | fixture fx_shoot |
| fixtures | AITactics | fire_events | impossible: fire/melee | fixture fx_shoot |
| fixtures | AITactics | tactic_chosen | driven | fixture fx_tactic |
| fixtures | AITrade | trade_completed | driven | fixture fx_trade |
| fixtures | CampRespawn | respawn_reserved | driven | fixture fx_camp_setup; timer |
| fixtures | Camps | camp_recognised, maintenance_step, pathgraph_refresh | driven | fixture fx_camp_setup |
| fixtures | CookingCompat | cooking_config_rpc_refused, cooking_dish_cooked | driven | fixture fx_cooking |
| fixtures | FactionConflict | encounters_observed, outcome_recorded | driven | fixture fx_conflict |
| fixtures | FoodCompat | food_compat_guard, food_compat_refused | driven | fixture fx_food |
| fixtures | Fortify | barricade_breached | driven | fixture fx_barricade; setting |
| fixtures | Fortify | fortify_placed | driven | fixture fx_kit_place |
| fixtures | Fortify | fortify_refused | driven | fixture fx_kit_refuse |
| fixtures | Holdouts | camp_committed, occupied_holdouts | driven | fixture fx_holdout_due |
| fixtures | InfectedMemory | heat_recorded, memory_cells | impossible: fire/melee | fixture fx_shoot |
| fixtures | Materializer | materialized_operations | driven | fixture fx_materialize |
| fixtures | Melee | hit_processed, parity_probe, wall_veto, zombie_hit_bonuses | impossible: fire/melee | fixture fx_melee |
| fixtures | OptionalPacks | animal_seen | driven | fixture fx_animal |
| fixtures | OptionalPacks | config_probed | driven | fixture fx_animal; boot |
| fixtures | WorldIncidents | incident_recorded, incident_sweep | driven | fixture fx_conflict,fx_incident |
| fixtures | optional-expansion-human-ai | convoy_astar, nav_stuck_recovery, stuck_recovery | driven | fixture fx_convoy_stuck |
| forest | Forage | forage_spawned, item_picked, item_spawned | driven | steps action:pickup_forage,admin:forage,walk:shelter:Bor South Rest |
| forest | Polish | sound_played | driven | steps stand,walk:shelter:Bor South Rest |
| forest | Progression | familiarity_gained, forage_gains | driven | steps action:pickup_forage,walk:shelter:Bor South Rest |
| group | Groups | group_mutated, members_sampled | driven | steps group:create_solo,ping |
| group | Groups | menu_open | driven | steps menu:map |
| group | MapPins | pins_published, pins_sampled | driven | steps group:create_solo,ping |
| idle | CellarSampler | cellars_measured, class_measured | driven | marker+timer |
| idle | Cellars | cellars_measured | driven | marker+timer |
| idle | DebugSnapshot | snapshot_points, snapshot_saved | driven | timer |
| idle | Interiors | props_placed | driven | timer |
| idle | Pickers | trip_started, trip_step | driven | steps walk:site:scav-chernogorsk; timer |
| idle | Shelters | regional_props_placed | driven | timer |
| idle | VehicleRetire | retired | driven | boot |
| idle | WorldSaves | save_stages, stage_written | driven | timer |
| join | AdminMap | catalog_auto_refresh | driven | steps menu:admin; timer |
| join | AdminMap | request, request_dispatched | driven | steps admin:snapshot,admin:status |
| join | AdminMap | window_open | driven | steps menu:admin |
| join | ClientUI | earplugs_applied | driven | steps action:earplugs |
| join | ClientUI | inventory_open | driven | steps menu:inventory |
| join | ClientUI | map_open | driven | steps menu:map |
| join | Grade | grade_applied, presentation_sent | driven | steps stand; boot |
| join | GunPile | piles_placed | driven | boot |
| join | Infected | actor_bound, actor_sampled | driven | steps stand; boot |
| join | InfectedLOD | herd_materialized, tier_changed, tracked_infected | driven | steps stand; boot |
| join | InfectedVariety | actor_woken, variety_activity | driven | steps stand; boot |
| join | Lighting | blend_applied, presentation_sent | driven | steps stand; boot |
| join | Polish | hint_shown, presentation_sent | driven | steps stand; boot |
| join | SurvivalAlignment | stamina_applied, stamina_hud_shown | driven | steps sprint |
| join | WeatherDays | profile_applied, weather_tick | driven | boot+timer |
| join | World | row_simulated, world_row | driven | boot+timer |
| scene | Leads | active_leads, lead_received | driven | steps action:read,admin:radio,admin:scene |
| scene | Notes | note_read | driven | steps action:read,action:take |
| scene | Notes | world_notes | driven | steps action:read,action:take,admin:scene,walk:scene:scene-kamenka |
| scene | NotesCompat | notes_lead_protected | driven | steps action:take,action:write,admin:scene |
| scene | NotesCompat | notes_lead_tracked | driven | steps action:read,action:take,admin:scene |
| scene | NotesCompat | write_rpc_passed | driven | steps action:write; gear |
| scene | Scenes | scene_placed, scenes_placed | driven | steps admin:scene,walk:scene:scene-kamenka |
| walk_ai | AIRoles | activity_started, lease_started, routes_pending | driven | steps walk:site:police-chernogorsk; timer |
| walk_ai | AISelfDefence | threats_applied | driven | steps walk:site:police-chernogorsk; timer |
| walk_ai | Materializer | actors_materialized, custody_lease_ceiling_backup_retire_failed, custody_lease_ceiling_torn | driven | steps walk:site:police-chernogorsk; timer |
| walk_ai | MaterializerBridge | actors_spawned, party_materialized | driven | steps walk:site:police-chernogorsk; timer |
| walk_ai | ObjectSpawner | pathgraph_refresh | driven | steps walk:site:police-chernogorsk; timer |
| walk_ai | SitePatrols | death_hold_armed, death_hold_deferred, death_hold_released | driven | steps walk:site:police-chernogorsk; fixture fx_site_patrol_kill |
| walk_ai | Sites | composed_sites, ground_refused_rows, orphan_sweep, site_refusals | driven | boot+timer |
| walk_ai | ZoneGuards | guard_actors_spawned, guards_posted | driven | steps walk:site:police-chernogorsk; timer |
| walk_ai | hcxai-live-map | live_ai_units, report_published | driven | steps walk:site:police-chernogorsk; timer |
| walk_ai | optional-expansion-human-ai | actor_spawned, cache_save_busy, nav_routes, regional_road_site_binding, route_cache, site_actors | driven | steps walk:site:police-chernogorsk; timer |
| walk_ai | optional-expansion-human-ai | site_radius_entered | driven | steps walk:site:police-chernogorsk |
| walk_ai | v2-expansion-living-world | actor_admitted, caution_warn, owned_actor_checked | driven | steps walk:site:police-chernogorsk; timer |
| walk_town | BodyStories | body_observed, death_checked | driven | steps walk:site:scav-chernogorsk; timer |
| walk_town | Infected | door_locked_skip, flow_reuse, group_quarantine, nav_deferred, nav_find_path, nav_forced, pack_door_open, repath_ok, route_cache_hit, straggler_drop, stuck_strike | driven | steps walk:site:scav-chernogorsk; timer |
| walk_town | InfectedDoors | door_action | driven | steps walk:site:scav-chernogorsk; timer |
| walk_town | InfectedReach | backoff_started, nav_vault_started, reach_actions, strike_landed, vault_started, vehicle_battered | driven | steps walk:site:scav-chernogorsk; timer |
| walk_town | Interiors | inspect_native_skipped, inspect_query_heavy, nav_pathgraph_refresh, pathgraph_refresh, prop_placed, resolve_binding_mismatch, resolve_deleted_retry, resolve_heavy_ray_miss, resolve_query_fallback, resolve_query_heavy, resolve_ray_fallback, resolve_ray_hit, resolve_ray_hit_alt, resolve_startup_deferred, resolve_tile_slow, resolve_tiled_routed | driven | steps walk:site:scav-chernogorsk; timer |
| walk_town | Scenes | retire_retry_cap | driven | steps walk:site:scav-chernogorsk; timer |
| walk_town | Shelters | pathgraph_refresh, shelter_placed | driven | steps walk:site:scav-chernogorsk; timer |
| walk_town | SignsOfLife | area_sampled, flies_created, light_observed, smoke_observed | driven | steps walk:site:scav-chernogorsk; timer |
| walk_zone | Ecology | animal_observed, cohort_visited | driven | steps walk:zone:balota-cf3bbed7; timer |
| walk_zone | Escalation | clock_step, state_advanced | driven | steps walk:zone:balota-cf3bbed7; timer |
| walk_zone | Events | cache_filled, container_refilled, container_replaced, mission_marker, mission_notice, police_barrel_recreated, police_supply_bound, situation_started, situations_started | driven | steps walk:zone:balota-cf3bbed7; timer |
| walk_zone | Events | mission_radius_entered | driven | steps walk:zone:balota-cf3bbed7 |
| walk_zone | HordeMigration | drifting_cohorts, nav_route_advance, route_advanced | driven | steps walk:zone:balota-cf3bbed7; timer |
| walk_zone | InfectedSiege | siege_noise, siege_started | driven | steps walk:zone:balota-cf3bbed7; timer |
| walk_zone | NavInf | haven_seen | driven | steps walk:zone:balota-cf3bbed7; timer |
| manual | Cellars | visual_applied | owner_check | needs the client more than 2 m below terrain inside a building (HCCellarsClient); no repo data names a cellar and a player may not be teleported, so the owner walks into one cellar the sampler measured |
| manual | TeamPing | ping_delivered | friend_playtest | delivery of a team ping to another player needs a second player; one client has no recipient |
| manual | TeamPing | ping_recipients | friend_playtest | delivery of a team ping to another player needs a second player; one client has no recipient |

## Physically impossible or not claimable on one scripted client

| Item | Reason |
|---|---|
| Firing a gun | `DayZPlayerImplement.c:1161-1210` calls `GetWeaponManager().Fire(weapon)` only when `pInputs.IsAttackButtonDown()` / `IsAttackButton()` are true (`human.c:120/:122`, synced inputs). `WeaponManager.c:485 Fire` runs `ProcessWeaponEvent(WeaponEventTrigger)` locally. The server replays the synced input stream, so a client-only `Fire` only desyncs. `UAInput.SyncedOverride` is compiled only under `INPUT_OVERRIDE` (`UAInput.c:172-190`). The combat step therefore raises, aims and reloads for real, then logs `fire=unsupported:no-native-client-entry-for-fire-input`. |
| Melee | Light and heavy attacks read the same synced inputs (`DayZPlayerMeleeFightLogic_LightHeavy.c:137/:151`, `human.c:75 IsMeleeWeaponAttack`). No override exists for them (`OverrideMeleeEvade` at `human.c:265` is evade only). |
| Confirming a kill by the bot | Follows from the two rows above. Kills stay with the fixtures (`fx_melee`, `fx_shoot`, `fx_site_patrol_kill`). The combat step confirms only a target that something else killed (`IsAlive() == false` on a target it was tracking) and never claims to have killed it. |
| TeamPing delivery (`ping_recipients`, `ping_delivered`) | One client has no recipient. The item stays friend_playtest. |
| Cellars visual (`Cellars/visual_applied`) | Needs the client more than 2 m below terrain inside a building. No repo data names a cellar, and the bot may not teleport. The item stays owner_check. |
| Multiplayer anything | The acceptance bar is one server plus at most one client. Never claimed. |

## Native APIs (scripts-1.30.164289)

Paths are relative to `~/.cache/hollow-country/native-scripts/scripts-1.30.164289`.

**Movement and aim**

- `3_Game/human.c:7-12`: `HumanInputControllerOverrideType {DISABLED, ENABLED, ONE_FRAME}`.
- `3_Game/human.c:17`: `HumanInputController`.
- `3_Game/human.c:28`: `GetHeadingAngle`. `:31`: `GetAimChange`.
- `3_Game/human.c:253`: `OverrideMovementSpeed` (0 idle, 1 walk, 2 run, 3 sprint).
- `3_Game/human.c:256`: `OverrideMovementAngle` (degrees, -180..180).
- `3_Game/human.c:259`: `OverrideAimChangeX`. `:262`: `OverrideAimChangeY` (radians per tick).
- `3_Game/human.c:265`: `OverrideMeleeEvade`. `:268`: `OverrideRaise`. `:274`: `OverrideFreeLook`.
- `3_Game/human.c:1458`: `Human.GetInputController`.
- `3_Game/human.c:83`: `IsWeaponRaised`. `:86`: `WeaponADS`.
- `Object.c:305`: `GetOrientation`.

**Weapons**

- `4_World/Classes/Weapons/WeaponManager.c:79`: `CanFire`.
- `:91`: `CanAttachMagazine(wpn, mag, reservationCheck=true)`. `:132`: `CanSwapMagazine`.
- `:398`: `AttachMagazine(mag, control_action=NULL)`. `:408`: `SwapMagazine`. `:423`: `LoadBullet`.
- `:485`: `Fire`. Not used; see above.
- `:772`: `StartAction`. Its client path sends `ScriptInputUserData` with an `InventoryReservation`.
- `:874`: `IsRunning`.
- `PlayerBase.c:2047`: `GetWeaponManager`. `PlayerBase.c:9051/:9065`: the vanilla drag-and-drop path into `AttachMagazine`.

**Melee**

- `DayZPlayerMeleeFightLogic_LightHeavy.c:137/:151`: input reads only, no entry point.

**Inventory**

- `Man.c:178`: `PredictiveTakeEntityToHands`. `:381`: `PredictiveTakeEntityToInventory`.
- `Man.c:422`: `PredictiveSwapEntities`. `:533`: `PredictiveTakeOrSwapAttachment`.
- `PlayerBase.c:9104`: `PredictiveDropEntity`. `:1010`: `CanDropEntity`. `:6733`: `GetItemInHands`.
- `Inventory.c:127`: `EnumerateInventory`.
- `ActionTakeItem.c:6`: take from the ground. `ActionDropItem.c:30`.

**Using items**

- `ActionManagerClient.c:804`: `PerformActionStart`. `:798`: `PerformAction`.
- `ActionManagerClient.c:1335`: `SetIgnoreAutomaticInputEnd`. `:286`: `EndActionInput`. `:278`: `RequestEndAction`.
- `ActionManagerBase.c:91`: `GetRunningAction`. `:214`: static `GetAction(typename)`.
- `ActionBase.c:968`: `Can(player, target, item)`. `ActionTargets.c:125`: the `ActionTarget` constructor.
- `ItemBase.c:235`: `GetActions(typename, out array<ActionBase_Basic>)`.
- `ActionInput.c:627`: `ContinuousDefaultActionInput`. `:654`: `DefaultActionInput`.
- Consuming: `ActionEat.c:9`, `ActionEatCan.c:10`, `ActionDrink.c:9`, `ActionDrinkCan.c:1`, `ActionConsume.c:9`.
- Medical: `ActionBandageSelf.c:15`, `ActionBandageBase.c:1`.

**Vehicles**

- `ActionGetInTransport.c` (CCTCursorNoRuinCheck). It needs a raycast component with `CrewPositionIndex(component) >= 0`, an empty seat, `CrewCanGetThrough` and `CanReachSeatFromDoors`.
- `ActionStartEngine.c:9` (the driver seat, no target). `ActionStopEngine.c:1`. `ActionGetOutTransport.c:23`.
- `3_Game/Vehicles/Transport.c:182`: `CrewPositionIndex`. `:190`: `CrewMember`. `:194`: `CrewDriver`. `:356`: `OnInput(float dt)`.
- `3_Game/Vehicles/Car.c:102`: `GetSpeedometer`. `:185`: `SetSteering`. `:191`: `SetThrottle`. `:203`: `SetBrake`. `:209`: `SetHandbrake`. `:230`: `EngineIsOn`. `:248`: `GetGear`. `:260`: `ShiftTo`.
- `Car.c` enums: `:23` `CarGearboxType`, `:32` `CarGear`, `:57` `CarAutomaticGearboxMode`.
- `4_World/Entities/Vehicles/CarScript.c:1041`: `override void OnInput(float dt)` calls super. The DIAG drive pattern at `:1196-1207` is `ShiftTo(FIRST)`, then `SetThrottle`, `SetSteering`, `SetBrake`, `SetHandbrake`.
- Precedent in our tree: `HCXConvoyRuntime.c:711-719`, a modded `CarScript.OnInput` that calls super and then applies the inputs.
- `human.c:716`: `HumanCommandVehicle.GetTransport`.

**Doors**

- `ActionOpenDoors.c:1`. Its condition at `:40/:52` is `GetDoorIndex(target.GetComponentIndex())` and `CanDoorBeOpened`.
- `3_Game/Entities/Building.c:28`: `GetDoorIndex`. `:34`: `IsDoorOpen`. `:55`: `IsDoorLocked`. `Building.OpenDoor` is server-only and never used.

**Navigation**

- `AIWorld.c:70`: `AIWorld`. `:98`: `FindPath`. `:59`: `PGFilter`. `World.c:116`: `GetAIWorld`.
- The navmesh is not shown to exist on a retail client. Routes come from repo-data waypoints (`ai/sites.json` waypoints, zones, shelters and scene sources), and the navigator walks straight legs with the stuck ladder below.

**Targeting**

- `DayZPhysics.c:199`: `RaycastRV`. `iType` defaults to `ObjIntersectView`, which is a line-of-sight test.
- `Game.c:930`: `GetObjectsAtPosition3D`.
- `3_Game/Entities/DayZInfected.c:104`: `DayZInfected`. `ZombieBase.c:1`: `ZombieBase`.
- An AI human is a `PlayerBase` with no `GetIdentity()`. The client sees this for every networked player, so it is not server-only knowledge.
- `Object.c:517`: `IsAlive`.

**Survival state (client-visible only)**

- `PlayerBase.c:1066`: `IsBleeding`, from synced bits at `:1072-1088`.
- `PlayerBase.c:2987`: `GetVirtualHud`.
- `4_World/Classes/VirtualHud/DisplayStatus.c:96`: `GetElement`. `4_World/Classes/VirtualHud/DisplayElementBase.c:55`: `GetValue`.
- `4_World/Classes/VirtualHud/DisplayElementTendency.c:3-27`: tendency is `value & 7` (above 3 is negative) and seriousness is `value >> 3` (`DSLevels`: NORMAL, WARNING, CRITICAL, BLINKING, EXTRA).
- `4_World/Classes/VirtualHud/_constants.c:9` (`eDisplayElements`): `DELM_TDCY_HEALTH`, `DELM_TDCY_ENERGY` (hunger), `DELM_TDCY_WATER` (thirst), `DELM_BADGE_BLEEDING`.
- The server-only stat getters (`PlayerBase.c:5455-5482`) are never used.
- `PlayerBase.c:3925`: `IsUnconscious`. `:3966`: `GetBrokenLegs`. `:2219`: `IsRestrained`.

## Step kinds added by the autoplayer

All new steps have the same contract as the old ones: one `[HC Driver]` line, and no fake success.

| Kind | Fields | Behaviour | OK detail |
|---|---|---|---|
| `enter` | `zone` (site or mission), `sites` (flat x,z,r list, site only), `gait`, `hold_s`, `timeout_s` | Picks the nearest candidate the player is outside of. For a mission, the candidates are the published rows already on the client. Walks in, then holds inside. If the server has not confirmed, it walks out to radius + 40 m, holds outside, and walks back in. Each round doubles the hold, until `timeout_s`. One hold at least as long as the server's sampling cycle guarantees an outside sample followed by an inside sample. | `server-confirmed zone=<site\|mission> rounds=<n>` |
| `route` | `points` (flat x,z list of 2..64 waypoints), `gait`, `arrive_m`, `timeout_s` | `HCDriverRoute` (HCClientDriverNav.c) walks the waypoints in order; the default route uses the `scav-chernogorsk` site's own waypoint line (`route:site:scav-chernogorsk`, walk_town phase). Each leg is a walker leg in hand-over mode: 8 s without 1 m of progress climbs one rung of the stuck ladder: side-right 2 s, side-left 2 s, back up 2 s (walk speed, angle 180), door (`open_door` on a door in reach of where the player stands, 72 rays, never walking), then skip the waypoint once (the re-route; not for the last waypoint). Still stuck: REFUSED `stuck:<last rung>`. 10 m of progress since the last stuck spell restarts the ladder; a reached waypoint resets it. | `arrived waypoint=<n>/<n> climbs=<n> doors=<n> remaining_m=<m>` |
| `combat` | `range_m` (10..150), `timeout_s` | `HCDriverCombat` (HCClientDriverCombat.c). Takes the first rifle from the inventory to the hands (`PredictiveTakeEntityToHands`, 8 s), then reloads once with the vanilla reload key path `PlayerBase.QuickReloadWeapon` when `GetMagazineToReload` finds a magazine (Unjam, AttachMagazine, SwapMagazine or the bullet action, with the WeaponManager checks). Scans every second (`GetObjectsAtPosition3D`, reused arrays) for the nearest live `DayZInfected` or identity-less `PlayerBase` (a server AI) that one `RaycastRV` from the head can see. Raises with `OverrideRaise` and turns and pitches the camera onto it with `OverrideAimChangeX/Y` (an axis whose error does not shrink in a second flips its sign). On target for 0.5 s counts `engaged`. A target that dies while tracked counts `dead_seen`; 3 s out of sight or beyond 1.2 x range counts `lost`; 20 s per target; at most 3 targets and 3 reloads (re-reload when the magazine and chamber are empty). Bleeding, a falling health tendency or a critical health level lowers the weapon and sprints 40 m away from the threat (`retreated=1`). Fire and melee are never attempted. OK with `engaged` > 0 or after a retreat; refused `no-target-within-<range>m` when nothing was in sight; timeout `not-aimed` otherwise. Default route: once after the walk_town route (`range_m` 60, 180 s). | `engaged=<n> lost=<n> dead_seen=<n> reloads=<n> armed=<0\|1> retreated=<0\|1> fire=unsupported` |
| `loot` | `range_m` (5..80), `max_items` (1..10), `timeout_s` | `HCDriverLoot` (HCClientDriverLoot.c). One `GetObjectsAtPosition3D` query per pick (reused arrays, at most 512 objects read) for loose items (`GetHierarchyParent` null, not ruined, within 2.5 m of the player's height). Picks the lowest tier, then the nearest: 0 a magazine the carried rifle takes (`WeaponManager.CanAttachMagazine`/`CanSwapMagazine`), 1 ammunition, 2 food (`Edible_Base`), 3 drink (`Bottle_Base`, `SodaCan_ColorBase`), 4 medical (bandage, rag, disinfectant, tablets, morphine, epinephrine), 5 a map (`ItemMap`); everything else is left lying. Walks to it and takes it with `ActionTakeItem` through `Can` and `PerformActionStart` (the F key). A take counts only once the synced hierarchy puts the item under the player (`GetHierarchyRootPlayer`). When `Can` fails (pockets full) it drops one junk item with `PredictiveDropEntity` and tries once more; junk is a carried cargo item that is not worn, held, attached, a weapon, magazine, food, drink, medical, map or part of the test kit. A failed walk or take skips that item (64-entry skip map). OK with `taken` > 0; refused `no-loot-within-<range>m` when nothing wanted lies in range, `could-not-take` when nothing could be taken; timeout `nothing-taken`. Default route: after the walk_town combat (40 m, 4 items, 300 s). | `taken=<n> dropped=<n> seen=<n> skipped=<n> mag/ammo/food/drink/med/map=<a/b/c/d/e/f>` |
| `survive` | `mode` (need or always), `timeout_s` (10..600) | `HCDriverSurvive` (HCClientDriverSurvive.c). Three tasks in order: bandage when `IsBleeding()` (a `BandageDressing` or `Rag`), drink (`Bottle_Base`/`SodaCan_ColorBase` with quantity), eat (`Edible_Base` that is not a medical edible). Mode `need` drinks or eats only when the HUD's water or energy tendency falls or its level is at least WARNING (VirtualHud, the client's own display state); `always` drinks and eats whatever it carries. Each task takes the item to the hands (`PredictiveTakeEntityToHands`, 8 s), then starts the first of the item's own `ContinuousDefaultActionInput` actions whose `Can` passes (`ActionBandageSelf`, `ActionDrink`, `ActionEat*`) through `PerformActionStart`, the hold-left-mouse path. Eating and drinking release the button (`EndActionInput`) after 8 s; a bandage runs until the bleeding stops (30 s cap). Credit comes from synced state only: bleeding stopped, or the item's quantity dropped or the item was used up. OK when any task was credited or nothing was needed; refused `none-done` otherwise; the reasons are listed (`no-bandage`, `no-drink`, `no-food`, `<task>-not-allowed`, `<task>-not-consumed`, `still-bleeding`). Default route: end of the forest phase, mode `always` (after the town loot and the forage pickup). | `bandaged=<0\|1> ate=<0\|1> drank=<0\|1> missing=<reasons\|none>` |
| `vehicle` | `seconds`, `throttle`, `timeout_s` | Walks to the nearest car (the `fx_car_side` car once it is flipped back). Raycasts for a seat component, then uses `ActionGetInTransport` and `ActionStartEngine`. Drives through a test-only holder that a modded `CarScript.OnInput` reads after calling super. Then brakes, stops the engine and gets out (`ActionGetOutTransport`). | `drove_m=<n> engine=<0\|1>` |
| action `open_door` | none | Same raycast scan as `close_door`, with `ActionOpenDoors` (Can() fails for a locked or open door; never forced). The actions phase runs it right after `close_door`. | `completed-client-side` |

## Failure handling (no cheating)

| State | How the bot sees it (client-visible) | Recovery |
|---|---|---|
| Stuck | `walk`: no 1 m of progress for 20 s, two alternating sidesteps, then timeout `stuck sidesteps=2`. `route`: 8 s without progress per rung | `route` climbs side-right, side-left, back up, open a door in reach through the vanilla action, skip the waypoint once. Then `refused detail=stuck:<rung>`. Never a teleport or a position fix. |
| Dead | `!player.IsAlive()` or no player | The current step ends `refused detail=player-unavailable`. The driver waits for a new character. It never respawns itself. The rest of the run continues once a player exists (the `IsPlayerLoaded` gate). |
| Unconscious | `IsUnconscious()` | Same as dead for the current step: all overrides are released and the step is refused. The next step waits for the player. |
| Bleeding | `IsBleeding()` | `combat` retreats. `survive` bandages with a bandage or rag from the inventory (`ActionBandageSelf`). With no bandage, it refuses with `no-bandage`. |
| Hungry or thirsty | VirtualHud energy/water seriousness of at least WARNING, or a falling tendency | `survive` eats or drinks the best item in the inventory. With none, it refuses with `no-food` / `no-drink`, and the next `loot` step looks for some. |
| Restrained, broken legs | `IsRestrained()`, `GetBrokenLegs()` | Movement steps refuse with `restrained` or continue at walk speed. There is no healing shortcut. |
| Menu stuck open | `GetUIManager().GetMenu()` | The menu step closes only the menu it opened. Other steps refuse with `another-menu-open`. |

## Release-gate scripted client

`python3 -B -m tools.release.release_gate ... --client-mode scripted` (the default) does the
following:

1. Builds the test addon. It stages `@HollowCountryTest` into the server root and a test client
   profile with the R3 step file (`driver_script write --route r3`), using the soak campaign's
   `Stager`, with its receipt and restore.
2. Lets the soak boot run. A background watcher waits for `Player connect enabled` in the fresh
   server RPT, then launches the client through `WindowsHost.launch_client` with
   `client_arguments` / `client_mods` (the same launch the soak campaign uses).
3. Runs the client step from the staged profile's RPT. The checklist and the verdict say
   "scripted client", never "tester".
4. Cleanup stops the client first, then the server (graceful), then restores the staging.

Risk: the server must accept a client that loads the test mod. The test mod is signed with the
same dev key as the local build, so it is in the server's keys. This is unverified on retail.
`--client-mode human` keeps the old path.

## Native verification order (lead only, one server plus one client)

1. Join: `[HC Driver] step=s04 kind=menu result=ok detail=opened-and-closed` (map) and
   `[HC Driver] step=s07 kind=menu result=ok detail=opened-and-closed` (admin), with `[HC Use]`
   rows `ClientUI/map_open`, `Groups/menu_open` and `AdminMap/window_open` above 0.
2. `--route r3`: `kind=enter result=ok detail=server-confirmed zone=site ...` and
   `... zone=mission ...`, with `optional-expansion-human-ai/site_radius_entered` and
   `Events/mission_radius_entered` above 0 in the client RPT.
3. `route`: `kind=route result=ok detail=arrived waypoint=4/4 climbs=... doors=...`. A
   `refused detail=stuck:<rung>` line names the last rung tried; `doors` above 0 shows the door rung
   opened one. `kind=action ... open_door result=ok` follows `close_door` in the actions phase.
4. `combat`: `kind=combat result=ok detail=engaged=... fire=unsupported`. Expect `engaged` to be
   at least 1 near town infected.
5. `loot`: `kind=loot result=ok detail=taken=...`.
6. `survive`: `kind=survive result=ok detail=...`.
7. `vehicle`: `kind=vehicle result=ok detail=drove_m=...`. Below 5 m means the `OnInput` setters
   were ignored on retail.
8. A release gate with `--client-mode scripted`: `release_gate=PASS`, with `"client_mode":
   "scripted"` in the verdict.

## Unsettled native risks

- Whether a retail client turns the character with `OverrideAimChangeX`, and whether the server
  sees overrides as real input. The walker's aim-sign adaptation and the no-progress timeout keep
  a failure visible.
- Whether the server accepts a client running the test mod when the server does not load it.
  The key is shared, but the effect of the script difference is unknown.
- Whether `Car.SetThrottle` / `SetSteering` called from `OnInput` on the driver's client drive a
  retail car. Vanilla only does this under DIAG.
- VirtualHud levels arrive through `RPC_SYNC_DISPLAY_STATUS` (`PlayerBase.c:5740`). Their client
  cadence is unobserved.
- The map step needs the group frame to be enabled when it runs. The admin step needs the client
  on the admin allowlist of the local server.
- The server samples the site radius around `HCSiteAnchor` (not the first waypoint), scaled by
  `ActivationRadiusScale` and the perception-ring clamp. The `enter` step uses
  `max(600, ActivationRadius)` from repo data and holds well inside it (radius minus 60 m).
- A published mission must exist during the R3 window. With none, `enter zone=mission` refuses
  with `no-published-mission` after its timeout.
- R3 duration: soak minutes plus the client timeout must cover the walk-in. The R3 route stays
  near the spawn: it uses the nearest site candidate and the nearest mission row.
