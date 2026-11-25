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
  `fixture=1`. Round 2 adds only the initial-creation fixture documented below. The vehicle phase drives the car that the
  existing `fx_car_side` fixture already places.
- The driver logs one `[HC Driver] step=<id> kind=<kind> result=<ok|refused|unsupported|timeout>
  detail=<text>` line per step (the detail is capped at 240 characters), plus one `done` line.
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
- `3_Game/Vehicles/Transport.c:178`: `CrewSize`. `:182`: `CrewPositionIndex`. `:190`: `CrewMember`. `:194`: `CrewDriver`. `:200`: `CrewEntryWS(posIdx, out pos, out dir)`. `:356`: `OnInput(float dt)`. `:685`: `GetSeatAnimationType(posIdx)`; the driver seat is the index whose type is `DayZPlayerConstants.VEHICLESEAT_DRIVER` (`OffroadHatchback.c:121`).
- `3_Game/Vehicles/Car.c:102`: `GetSpeedometer`. `:105`: `GetSpeedometerAbsolute`. `:266`: `GearboxGetType`. `:185`: `SetSteering`. `:191`: `SetThrottle`. `:203`: `SetBrake`. `:209`: `SetHandbrake`. `:230`: `EngineIsOn`. `:248`: `GetGear`. `:260`: `ShiftTo`.
- `Car.c` enums: `:23` `CarGearboxType`, `:32` `CarGear`, `:57` `CarAutomaticGearboxMode`.
- `4_World/Entities/Vehicles/CarScript.c:1041`: `override void OnInput(float dt)` calls super. The DIAG drive pattern at `:1196-1207` is `ShiftTo(FIRST)`, then `SetThrottle`, `SetSteering`, `SetBrake`, `SetHandbrake`.
- Precedent in our tree: `HCXConvoyRuntime.c:711-719`, a modded `CarScript.OnInput` that calls super and then applies the inputs.
- `human.c:716`: `HumanCommandVehicle.GetTransport`. `:735`: `IsTransitioning`. `human.c:1528`: `GetCommand_Vehicle`.
- `3_Game/Global/DayZPhysics.c:199`: `RaycastRV(..., sorted)`; with `sorted` the contact component belongs to the nearest hit.

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

### Soak phases

`driver_script.PHASES`, `soak_campaign.PHASE_ORDER` and `soak_phases.json` carry the same order
(`soak_campaign plan`: phase map problems 0). The four playing phases each hold one step of their
kind; each one also runs alone (a targeted soak drives join, the phase and idle): `combat` and
`loot` walk to the `scav-chernogorsk` site first unless the route already stands within 400 m of
it, and `vehicle` places and flips the `fx_car_side` car first when no earlier `flip` ran (the
same setup-only fixture and the real flip action). Reach rows retain their phase names; the route order changes in round 2.
Native `[HC Driver]` lines are required to prove each step.

| # | Phase | Minutes | Steps |
|---|---|---|---|
| 1 | join | 5 | calibration, wait, stand, sprint, the four menus, admin status and snapshot, earplugs |
| 2 | group | 2 | create a solo group, team ping |
| 3 | walk_ai | 30 | walk to police-chernogorsk, stand |
| 4 | walk_town | 20 | walk to scav-chernogorsk, its street line as a `route`, stand |
| 5 | combat | 5 | `combat range_m=60 timeout_s=180` |
| 6 | loot | 6 | `loot range_m=40 max_items=4 timeout_s=300` |
| 7 | fixtures | 10 | the setup-only fixtures (fx_car_side first) |
| 8 | actions | 15 | craft, search, close and open a door, mount x2, salvage, flip, radio; admin radio, loot, decay, deaddrop |
| 9 | vehicle | 4 | `vehicle range_m=40 seconds=8 throttle=0.5 timeout_s=180` |
| 10 | walk_zone | 45 | walk west into the Balota zone, stand |
| 11 | scene | 12 | walk to scene-kamenka, scene, take, read, write x2 |
| 12 | forest | 8 | walk to Bor South Rest, forage, pick forage, stand |
| 13 | survive | 3 | `survive mode=always timeout_s=120` |
| 14 | mission | 30 | `enter zone=mission` |
| 15 | idle | 125 | stand (background and timer counters) |

| Kind | Fields | Behaviour | OK detail |
|---|---|---|---|
| `enter` | `zone` (site or mission), `sites` (flat x,z,r list, site only), `gait`, `hold_s`, `timeout_s` | Picks the nearest candidate the player is outside of. For a mission, the candidates are the published rows already on the client. Walks in, then holds inside. If the server has not confirmed, it walks out to radius + 40 m, holds outside, and walks back in. Each round doubles the hold, until `timeout_s`. One hold at least as long as the server's sampling cycle guarantees an outside sample followed by an inside sample. | `server-confirmed zone=<site\|mission> rounds=<n>` |
| `route` | `points` (flat x,z list of 2..64 waypoints), `gait`, `arrive_m`, `timeout_s` | `HCDriverRoute` (HCClientDriverNav.c) walks the waypoints in order; the default route uses the `scav-chernogorsk` site's own waypoint line (`route:site:scav-chernogorsk`, walk_town phase). Each leg is a walker leg in hand-over mode: 8 s without 1 m of progress climbs one rung of the stuck ladder: side-right 2 s, side-left 2 s, back up 2 s (walk speed, angle 180), door (`open_door` on a door in reach of where the player stands, 72 rays, never walking), then skip the waypoint once (the re-route; not for the last waypoint). Still stuck: REFUSED `stuck:<last rung>`. 10 m of progress since the last stuck spell restarts the ladder; a reached waypoint resets it. | `arrived waypoint=<n>/<n> climbs=<n> doors=<n> remaining_m=<m>` |
| `combat` | `range_m` (10..150), `timeout_s` | `HCDriverCombat` (HCClientDriverCombat.c). Takes the first rifle from the inventory to the hands (`PredictiveTakeEntityToHands`, 8 s), then reloads once with the vanilla reload key path `PlayerBase.QuickReloadWeapon` when `GetMagazineToReload` finds a magazine (Unjam, AttachMagazine, SwapMagazine or the bullet action, with the WeaponManager checks). Scans every second (`GetObjectsAtPosition3D`, reused arrays) for the nearest live `DayZInfected` or identity-less `PlayerBase` (a server AI) that one `RaycastRV` from the head can see. Raises with `OverrideRaise` and turns and pitches the camera onto it with `OverrideAimChangeX/Y` (an axis whose error does not shrink in a second flips its sign). On target for 0.5 s counts `engaged`. A target that dies while tracked counts `dead_seen`; 3 s out of sight or beyond 1.2 x range counts `lost`; 20 s per target; at most 3 targets and 3 reloads (re-reload when the magazine and chamber are empty). Bleeding, a falling health tendency or a critical health level lowers the weapon and sprints 40 m away from the threat (`retreated=1`). Fire and melee are never attempted. OK with `engaged` > 0 or after a retreat; refused `no-target-within-<range>m` when nothing was in sight; timeout `not-aimed` otherwise. Default route: the `combat` phase, right after walk_town (`range_m` 60, 180 s). | `engaged=<n> lost=<n> dead_seen=<n> reloads=<n> armed=<0\|1> retreated=<0\|1> fire=unsupported` |
| `loot` | `range_m` (5..80), `max_items` (1..10), `timeout_s` | `HCDriverLoot` (HCClientDriverLoot.c). One `GetObjectsAtPosition3D` query per pick (reused arrays, at most 512 objects read) for loose items (`GetHierarchyParent` null, not ruined, within 2.5 m of the player's height). Picks the lowest tier, then the nearest: 0 a magazine the carried rifle takes (`WeaponManager.CanAttachMagazine`/`CanSwapMagazine`), 1 ammunition, 2 food (`Edible_Base`), 3 drink (`Bottle_Base`, `SodaCan_ColorBase`), 4 medical (bandage, rag, disinfectant, tablets, morphine, epinephrine), 5 a map (`ItemMap`); everything else is left lying. Walks to it and takes it with `ActionTakeItem` through `Can` and `PerformActionStart` (the F key). A take counts only once the synced hierarchy puts the item under the player (`GetHierarchyRootPlayer`). When `Can` fails (pockets full) it drops one junk item with `PredictiveDropEntity` and tries once more; junk is a carried cargo item that is not worn, held, attached, a weapon, magazine, food, drink, medical, map or part of the test kit. A failed walk or take skips that item (64-entry skip map). OK with `taken` > 0; refused `no-loot-within-<range>m` when nothing wanted lies in range, `could-not-take` when nothing could be taken; timeout `nothing-taken`. Default route: the `loot` phase, after `combat` (40 m, 4 items, 300 s). | `taken=<n> dropped=<n> seen=<n> skipped=<n> mag/ammo/food/drink/med/map=<a/b/c/d/e/f>` |
| `survive` | `mode` (need or always), `timeout_s` (10..600) | `HCDriverSurvive` (HCClientDriverSurvive.c). Three tasks in order: bandage when `IsBleeding()` (a `BandageDressing` or `Rag`), drink (`Bottle_Base`/`SodaCan_ColorBase` with quantity), eat (`Edible_Base` that is not a medical edible). Mode `need` drinks or eats only when the HUD's water or energy tendency falls or its level is at least WARNING (VirtualHud, the client's own display state); `always` drinks and eats whatever it carries. Each task takes the item to the hands (`PredictiveTakeEntityToHands`, 8 s), then starts the first of the item's own `ContinuousDefaultActionInput` actions whose `Can` passes (`ActionBandageSelf`, `ActionDrink`, `ActionEat*`) through `PerformActionStart`, the hold-left-mouse path. Eating and drinking release the button (`EndActionInput`) after 8 s; a bandage runs until the bleeding stops (30 s cap). Credit comes from synced state only: bleeding stopped, or the item's quantity dropped or the item was used up. OK when any task was credited or nothing was needed; refused `none-done` otherwise; the reasons are listed (`no-bandage`, `no-drink`, `no-food`, `<task>-not-allowed`, `<task>-not-consumed`, `still-bleeding`). Default route: the `survive` phase after forest, mode `always` (after the town loot and the forage pickup). | `bandaged=<0\|1> ate=<0\|1> drank=<0\|1> missing=<reasons\|none>` |
| `vehicle` | `range_m` (5..80), `seconds` (2..60), `throttle` (0.1..1.0), `timeout_s` (30..600) | `HCDriverVehicle` (HCClientDriverVehicle.c) and the pedal holder `HCDriverCarInput` (4_World/HCDriverCarInput.c). One `GetObjectsAtPosition3D` query for the nearest intact `CarScript` whose driver seat (the crew index with `GetSeatAnimationType` == `VEHICLESEAT_DRIVER`) is empty; the default route runs it right after `flip`, so it is the `fx_car_side` car flipped back onto its wheels. Walks to `CrewEntryWS` of the driver seat, then casts one `RaycastRV` per frame from the head through the door (a 5 x 6 grid, at most 30 rays) until the nearest hit is the car, its component maps to the driver seat (`CrewPositionIndex`) and `ActionGetInTransport.Can` passes, and starts the get-in with `PerformActionStart`. Seated once `GetCommand_Vehicle` is not getting in and `CrewDriver` is the player (12 s). Starts the engine with `ActionStartEngine` when `Can` passes (the car's own battery, plugs, fuel and engine decide; nothing is repaired or refuelled; a refusal is `note=engine-did-not-start`). With the engine on, the modded `CarScript.OnInput` (after super, client only, only for the car the local player drives) sets `SetThrottle`, `SetSteering` 0, `SetBrake` and `SetHandbrake` 0 for `seconds`, shifting a manual box to first as the DIAG drive does; then brakes to below 1 km/h (8 s cap), stops the engine with `ActionStopEngine` and gets out with `ActionGetOutTransport`. Out of time while seated still brakes and gets out. OK once the player stands outside again after the engine ran and the car displaced at least 1 m; refused `no-free-car-within-<range>m`, `driver-door-not-usable`, `get-in-not-completed`, `left-the-car`, `get-out-not-allowed` or `get-out-not-completed`. | `seated=<0\|1> engine=<0\|1> drove_m=<n> top_kmh=<n> out=<0\|1>` and `note=` when set |
| action `open_door` | none | Same raycast scan as `close_door`, with `ActionOpenDoors` (Can() fails for a locked or open door; never forced). The actions phase runs it right after `close_door`. | `completed-client-side` |

## Failure handling (no cheating)

| State | How the bot sees it (client-visible) | Recovery |
|---|---|---|
| Stuck | `walk`: no 1 m of progress for 20 s, two alternating sidesteps, then timeout `stuck sidesteps=2`. `route`: 8 s without progress per rung | `route` climbs side-right, side-left, back up, open a door in reach through the vanilla action, skip the waypoint once. Then `refused detail=stuck:<rung>`. Never a teleport or a position fix. |
| Dead | `!player.IsAlive()` or no player | The current step ends `refused detail=player-unavailable`. The driver waits for a new character. It never respawns itself. The rest of the run continues once a player exists (the `IsPlayerLoaded` gate). |
| Unconscious | `IsUnconscious()` | Same as dead for the current step: all overrides are released and the step is refused. The next step waits for the player. |
| Bleeding | `IsBleeding()` | `combat` retreats. `survive` bandages with a bandage or rag from the inventory (`ActionBandageSelf`). With no bandage, it refuses with `no-bandage`. |
| Hungry or thirsty | VirtualHud energy/water seriousness of at least WARNING, or a falling tendency | `survive` eats or drinks the best item in the inventory. With none, it refuses with `no-food` / `no-drink`, and the next `loot` step looks for some. |
| In a car | `GetCommand_Vehicle()` | `vehicle` brakes and gets out with the vanilla action even when its time runs out; a car that will not start (`engine=0 note=engine-did-not-start`) is left as it is and the player gets out. Other steps run on foot only. |
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
7. `vehicle`: `kind=vehicle result=ok detail=seated=1 engine=1 drove_m=... out=1`. `engine=0
   note=engine-did-not-start` means the world car lacks a part or fuel (the bot never adds one);
   `engine=1` with `drove_m` below 5 means the `OnInput` setters were ignored on retail.
8. A release gate with `--client-mode scripted`: `release_gate=PASS`, with `"client_mode":
   "scripted"` in the verdict.

## Unsettled native risks

- Whether a retail client turns the character with `OverrideAimChangeX`, and whether the server
  sees overrides as real input. Navigation now avoids aim overrides; calibration and no-progress timeouts keep failures visible.
- Whether the server accepts a client running the test mod when the server does not load it.
  The key is shared, but the effect of the script difference is unknown.
- Whether `Car.SetThrottle` / `SetSteering` called from `OnInput` on the driver's client drive a
  retail car. Vanilla only does this under DIAG.
- VirtualHud levels arrive through `RPC_SYNC_DISPLAY_STATUS` (`PlayerBase.c:5740`). Their client
  cadence is unobserved.
- The map uses the test profile's vanilla 2D configuration when no group frame is available. The admin step needs the client
  on the admin allowlist of the local server.
- The server samples the site radius around `HCSiteAnchor` (not the first waypoint), scaled by
  `ActivationRadiusScale` and the perception-ring clamp. The `enter` step uses
  `max(600, ActivationRadius)` from repo data and holds well inside it (radius minus 60 m).
- A published mission must exist during the R3 window. With none, `enter zone=mission` refuses
  with `no-usable-candidates zone=mission published=0` after 15 s.
- R3 duration: soak minutes plus the client timeout must cover the walk-in. The R3 route stays
  near the spawn: it uses the nearest site candidate and the nearest mission row.

## Round 2: native movement diagnosis and setup (build 186 follow-up)

Round 1 has **no native successful walk**. Build 186 completed 95 steps with all five walks timing
out. The following changes require a new native run; offline tests prove planning only.

Native evidence below is relative to `scripts-1.30.164289`:

- `1_Core/proto/EnConvert.c:341-368` documents vector `(1,0,1)` as yaw 45 degrees and yaw 45 as
  `(0.707107,0,0.707107)`. Thus `atan2(dx,dz)` is consistent with engine yaw; swapping its
  arguments or blindly negating body yaw is not justified.
- `3_Game/human.c:25-31` distinguishes local movement direction from the **camera** heading,
  which `GetHeadingAngle()` returns in radians. Body `GetOrientation()[0]` need not equal that
  input frame. `human.c:253-262` declares the overrides but does not document their sign or frame;
  `:459-467` documents movement angles in degrees and speeds 0 idle, 1 walk, 2 run, 3 sprint.
  Round 1's speed values were valid.
- `4_World/Systems/Bot/Bot_MovementRandomizer.c:26-39` reapplies `ONE_FRAME` movement from the bot
  update. `5_Mission/GUI/CameraTools/CTEvent.c:50-51` and
  `4_World/Plugins/PluginBase/PluginDayzPlayerDebug_Ctrl.c:124-135` also demonstrate persistent
  enabled overrides. Persistent mode alone is therefore not proof of the failure.
- `4_World/Entities/ManBase/PlayerBase.c:3206-3211` supplies the exact script `CommandHandler`
  signature used by the client and server hook, which calls super. The mission queues one input
  request per frame; the local player's command callback applies the selected variant only
  in `HumanCommandMove`. It never starts a movement command or replaces an engine method.
- The native implementation of `OverrideAimChangeX` is opaque. Scripts establish per-tick radians
  (`human.c:30`), not that it turns the body during movement. Round 1 flipped the aim sign every
  second if heading error failed to shrink; that can oscillate indefinitely when aim does not turn
  the body. Navigation now makes no aim-change requests.

Build 189's four northbound probes reported current speed 3.0 and angle 0, but each settled
exactly at its start. The lead's one-server/one-scripted-client run supports server correction:
the old hook was excluded by `#ifndef SERVER`. Round 5 mirrors requests on the server, using
the retail controller methods demonstrated by the DEVELOPER-only native debug RPC
(`PluginDayzPlayerDebug.c:966`, `DayZPlayerImplement.c:3855–3866`); it does not use that RPC.
The predicted north-west bearing remains unqualified until movement survives settling.
Round 5 remains implemented-unverified until the lead's native checks.

1. Wait for ten continuous seconds alive, conscious and in `HumanCommandMove` with a controller
   and mission controls enabled. Missing/unloaded players reset this timer and release movement.
   A run waiting 60 s without readiness refuses.
2. Try `mirror` (client predicts, server applies), then `server` (server applies only), then
   `client` (client applies only, diagnostic). Every applying controller uses post-super ONE_FRAME.
   Request speed **3.0**, angle 0, for **4 s**, then Stop and settle **2 s**. Select the first
   variant with displacement **>0.30 m** and `back_m` **<=0.20 m** (round 7). A failed or corrected
   forward probe advances to the next variant. Client applied-frame counts are expected to be
   zero in `server`; use the correlated server summary to verify authoritative callbacks.
3. Re-run the right probe with the selected variant: speed 3.0, angle +90 for **4 s**, then Stop
   for **2 s**. Measure the forward camera bearing offset (`frame_offset`) and signed right
   bearing residual after that offset (`right_offset`), both to two decimals. A forward offset
   alone no longer rejects calibration; only the variant whose forward move survived settling
   can supply the frame used by navigation. The right turn must agree within 15 degrees.
   Each probe collects five observations at 0.5 s intervals (0.5 through 2.5 s), plus the Stop
   position and the position after settling. `sample_s` records actual times: clamped updates
   can delay samples; no observation is fabricated. `cur_speed` and `cur_angle` come from
   `HumanCommandMove`; `input_angle=idle` means `GetCurrentInputAngle` returned false.
   `dir` is the player's body direction xz. Exact line formats follow (values are illustrative
   placeholders; all measured positions, distances and bearing offsets have two decimals):

   ```text
   [HC Driver] calib probe=fwd variant=mirror serial=N req_speed=3.00 req_angle=0.00 pos=<x,z;x,z;x,z;x,z;x,z> cur_speed=<s;s;s;s;s> cur_angle=<a;a;a;a;a> input_angle=<a|idle;a|idle;a|idle;a|idle;a|idle> dir=<x,z;x,z;x,z;x,z;x,z> sample_s=<t;t;t;t;t> start=<x,z> stop=<x,z> settled=<x,z> moved_m=D settle_m=S back_m=B attempt=N duration_s=4.00 settle_s=2.00 samples=5
   [HC Driver] calib probe=right variant=mirror serial=N req_speed=3.00 req_angle=90.00 pos=<x,z;x,z;x,z;x,z;x,z> cur_speed=<s;s;s;s;s> cur_angle=<a;a;a;a;a> input_angle=<a|idle;a|idle;a|idle;a|idle;a|idle> dir=<x,z;x,z;x,z;x,z;x,z> sample_s=<t;t;t;t;t> start=<x,z> stop=<x,z> settled=<x,z> moved_m=D settle_m=S back_m=B attempt=N duration_s=4.00 settle_s=2.00 samples=5
   [HC Driver] calib result=ok|refused variant=mirror|server|client run=N reason=REASON forward=<x,z> right=<x,z> threshold_m=0.30 right_moved_m=D forward_settle_m=S right_settle_m=S correction_threshold_m=0.20 back_m=B facing=Y yaw=Y,Y,Y cmd=ID,ID applied_frames=N,N angle_sign=S frame_offset=O right_offset=O apply=measured-camera-frame|refused aim=disabled controls=0|1
   [HC Driver] server-move applied_frames=N refused=none|REASON serial=N
   ```

4. `moved_m` measures start to Stop; `settle_m` measures Stop to settled position. `back_m`
   projects that drift toward this probe's start (negative means continuing away). Only
   `back_m` above **0.20 m** (`correction_threshold_m`) counts as a server correction; settle
   drift that is not toward the start passes (round 7: soak 190t6's mirror probe moved 8.10 m with
   `settle_m=0.23 back_m=-0.15` and was wrongly refused under the old settle rule).
   A corrected forward probe tries the next variant; a corrected right probe ends with
   `reason=server-correction`. If every forward variant fails, the final reason is
   `server-correction` when the final probe is pulled back, otherwise `no-moving-variant`.
   For example, `variant=mirror serial=1 ... moved_m=8.00 settle_m=0.05 back_m=0.02` paired with
   `server-move applied_frames=240 refused=none serial=1` supports a working mirror forward
   probe. `moved_m=0.78 settle_m=0.78 back_m=0.78` fails that variant even if its server summary
   reports applied frames: server application still did not establish stable movement.
   `applied_frames=0 refused=command-change` identifies a server refusal. A `client` probe
   deliberately reports zero server frames. Server summaries alone never prove movement.
5. Calibration requires both displacements above 0.30 m, both settle distances <=0.20 m, and
   at least three of five command-angle samples per probe within 15 degrees of the request.
   Angle failure refuses as `command-angle-mismatch`; a right turn differing from the measured
   frame's +90 (or mirrored -90) by more than 15 degrees is `command-angle-motion-mismatch`.
   `AngleSign` carries a mirrored strafe into the walker. Other reasons include
   `right-no-movement`, readiness failures, or `frame-probe` for success. `Calibrated` becomes
   true only on `frame-probe`; result lines preserve measured offsets even on refusal.
6. States are readiness → forward drive → forward settle → right drive → right settle → result.
   A failed forward variant returns to forward drive with the next variant. A run has at most
   three forward probes and one right probe: **24 s nominal**, bounded by **26 s** of clamped
   update time including overshoot (12 s nominal when mirror moves), plus 60 s readiness and
   at most one update of overshoot. Startup failures retry after 15 s, at most three startup
   runs; a pre-movement retry shares the hard **four-run session cap**. Step timers start after
   calibration. Readiness loss stops immediately and refuses; an interrupted probe has no
   completed-probe line. At most four client probe lines and one result are emitted per run.
7. The test-only `HCDriverMoveWire.RPC_MOVE` allocation is **4854091** (global lint inventory).
   The reliable player-targeted request contains serial, speed, angle, lease seconds and an
   apply flag. `client` sends apply=false for a correlated zero-frame diagnostic summary.
   Active refreshes are spaced at least 125 ms, with a hard sliding ten-message/second cap
   including Stop. There are no idle refreshes. Stop sends lease=0 once; if throttled it retries
   until sent, and the server lease still bounds release. A serial identifies one continuous
   request/probe, not each refresh; the client probe line prints it for correlation.
   The server grants at most 500 ms from receipt using its own clock, never comparing unsynced
   client/server clocks. Refreshes must arrive before the prior deadline. Closed/stale serials
   cannot reactivate movement. Delivery age before the first receipt is not measured by this
   protocol and remains a native timing limitation to inspect.

   | Server input/state | Refusal reason |
   | --- | --- |
   | Missing sender, identity mismatch, or sender.GetPlayer differs from RPC target | `not-owner` (does not touch target controller) |
   | Incomplete payload or nonpositive serial | `malformed` |
   | More than ten messages in sliding 1000 ms | `rate-limit` |
   | Speed outside 0..3, including nonfinite values | `speed-range` |
   | Angle outside -180..180, including nonfinite values | `angle-range` |
   | Lease outside 0..0.5 seconds, including nonfinite values | `lease-range` |
   | Refresh after deadline, or deadline reached in callback | `lease-expired` |
   | Missing identity or disconnected player | `disconnected` |
   | Dead / unconscious / not in move command / missing controller | `dead` / `unconscious` / `command-change` / `no-controller` |
   | New serial replaces active request | Previous serial closes as `superseded` |
   | Stop (lease=0), otherwise valid | `none`, both overrides disabled |
   | Already closed or older serial | Ignored; keeps existing summary and cannot renew lease |

   Stop, release, step end, conclusion and shutdown disable both local overrides on the original
   controller. Client guards also clear on death, unconsciousness, lost movement command,
   disabled controls, changed local player, or expired 0.5 s lease. The server callback clears
   on lease expiry and life/command transitions; death and disconnect hooks clear before super.
   Each serial emits one server summary on close, with frames saturated at 1,000,000;
   summaries/refusals share a 128-line cap per player lifetime. Malformed/unowned packets use
   serial=0 when they cannot be safely correlated. No per-frame logging, position writes,
   teleports or increased speeds are used. Walk/route/sprint results retain `start`, `end`,
   `moved_m`, `cmd` and `controls`; sprint requires displacement.

`fx_site_patrol_kill` is registered with the same dev fixture flags as `fx_shoot`/`fx_melee`.
The existing `enforce_lint` gate now checks every test addon `HCOwns` literal `fx_` comparison
against `HCAdminCatalog` registrations (HC-E055), catching rejection before provider dispatch.
This command catalog does not feed `tools.package.admin_world_catalog`'s map-anchor outputs;
its generated artifacts and digests need no regeneration for this row.

### Initial creation and loadout fixtures

Reason: a random coastal spawn can be 10 km from the route and consume the soak without reaching a
feature. The isolated soak profile now contains `HollowCountry/autoplayer-initial-spawn`; only
that marker enables `HCDriverInitialSpawn`. It passes `(6500, terrain height, 2500)` to
`super.OnClientNewEvent`, before the entity exists. It never moves a living character.
Native hook: `5_Mission/mission/missionServer.c:549` is the exact new-character signature;
`:573-575` passes its position to character creation before native preset equipment processing,
and `:589` does so for default equipment. `:499-509` supplies the base creation implementation.
The cached stock Chernarus mission init overrides `CreateCharacter` without calling super; the
earlier `OnClientNewEvent` hook therefore avoids a bypassed base `CreateCharacter` fixture. Persistence reconnects are unaffected. This fixture is for
the isolated, single-client soak profile with fresh storage; do not use its marker on a shared
server. The first log is `[HC Driver] spawn fixture=1 initial=1 at=<6500,2500>`.

The route starts at that point, walks police Chernogorsk (~83 m), scavenger Chernogorsk (~228 m),
then its street route. Combat/loot/fixtures/actions/vehicle stay there before the westbound walk to
Balota and Kamenka, then the Bor shelter. Walk timeouts use actual planned leg lengths at 2.8 m/s
for jogging, with 2x travel allowance plus 120 s. Calibration and the initial sprint can displace
the start; that allowance covers their short distance. Each targeted phase still adds its own
approach walk. Campaign phase indices use actual route boundaries, never standalone step counts.

The existing **vanilla spawn-gear preset** (not a runtime spawn RPC) now prioritizes a ChernarusMap,
opened beans, water, Paper and Pen_Black; worn leather jacket and cargo trousers increase capacity.
Native `4_World/Classes/PlayerGearSpawn/CfgPlayerSpawnHandler.c:72-170` processes starting slots
and cargo; `:270-313` uses inventory capacity checks. Failure to fit a kit item remains a native
risk, reported as missing by the relevant step. This gear is selected only by the temporary soak
`cfggameplay.json` and fresh character creation. That test configuration also selects the vanilla
2D map (`UIData.use3DMap=false`, `MapData.ignoreMapOwnership=true`; accessors at
`3_Game/CfgGameplayHandler.c:417-440`), so the keyboard map path can open without the group service.
The staging receipt restores the original gameplay configuration and removes the copied profile.

### Other build 186 failures

| Build 186 steps | Round 2 handling (native verification pending) |
|---|---|
| s14/s18/s20/s79/s87 walk, s21 route | Measured frame/sign, command callback, no aim oscillation, nearby initial spawn, distance-based budgets and result displacement. |
| s03 sprint | Same callback; time alone cannot pass without displacement. |
| s08/s09 and 25 later admin commands | When `HCValid()` expires, send status, wait for its reply and authorization, then retry the original command. Tick pending requests during send retries too. Success records `session=refreshed`. A driver-only observer counts validated correlated replies; UI Revision expiry cannot complete a step. A refused reply remains refused with its server reason. Product `HCAdminClient.c:169-181,204` is unchanged. |
| s04 map | Vanilla 2D-map test configuration plus starting map. |
| s12 group | Explicit idempotent `Start` and `Update` drive the same handshake as `HCGroupGameplay.c:7-22`; wait up to 30 s. Distinguish absent snapshot, disabled server, pending transaction and server reply. No menu is required by `HCGroupClient.c:174-183,572-590`. A test-only observer adds `listening`, `session`, `sync_pending`, `frames`, `rejected` to readiness failures, distinguishing no reply from rejected snapshots. Build 186's generic reason cannot distinguish these; no group transport repair is claimed. |
| s13 ping | Solo request only after group readiness; delivery/recipient counters still need a second player. |
| s61 craft, s65/s66 mount, s67 salvage, s68 flip, s69 radio, s84 read, s86 write | P_PREP made one take-to-hands request and never retried or handled occupied hands. Native `3_Game/Entities/Man.c:178-189` can refuse busy input; `:422-437` supplies predictive swaps. Retry at 1 s intervals, swap occupied hands or stow the held item through inventory requests; refuse after 8 s with `hands-request-not-confirmed:inventory-busy-or-no-room`. |
| s62/s63/s64 search/doors | Still refuse `no-candidate-within-40m` when no local candidate exists; improved movement may reach real candidates. |
| s23 combat | Still refuses `no-target-within-60m` when no visible hostile is present; client firing remains unsupported. No weapon or target is created for this step. |
| s24 loot | Native inventory/action constraints still decide; refuses `could-not-take` when no observed item is taken. No loot replacement. |
| s83/s90 take/forage, s85 write taken | Still refuse no nearby item or `paper-missing:taken` if no world note was acquired. Starting paper supports the gear write; it does not pretend to be a scene note. |
| s78 vehicle | Closed door attachments were rejected as non-car hits. Now open the real driver door with `ActionOpenCarDoorsOutside`, confirm `CrewCanGetThrough`, and rescan for get-in. A rejected body hit does not end the scan before a later door hit can offer opening. Action waits start when the action is requested. Refuse explicitly for heavy hands, `CanGetIn`, door-open/get-in condition rejection, or an unconfirmed open. Failed scans include door/car/driver-seat hit counts. After normal get-out cleanup, an engine that never started or displacement below 1 m returns refused. Native outside-door conditions (`Interact/Vehicles/ActionCarDoorsOutside.c:21-65`) and get-in conditions (`ActionGetInTransport.c:34-80`) stay authoritative. |
| s92 survive | Starting food and drink address missing supplies; bounded hands retries also apply to survival and combat. Consumption still requires real actions and quantity change. Missing/blocked supplies remain refused. |
| s93 enter | Search client-published rows only, refuse after 15 s if none usable; reject a candidate beyond the remaining walk budget with distance. Reachable entries still walk out/in and await the real server receipt. |

The next client log order is `calib`, then s01 wait, s02 stand, s03 sprint (with displacement), s04
map, s08 status, s09 snapshot, s12 group, s13 ping, s14 walk, s18 walk and s19 route in the **campaign**
(the campaign inserts the patrol kill fixture after walk_ai). Later IDs are regenerated; consult
`soak_campaign plan` for them. The final `done` must follow all result lines. Calibration is a
separate startup probe and does not inflate the scripted step count or result totals.
