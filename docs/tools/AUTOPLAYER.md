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
| fixtures | AISelfDefence | hit_reaction | impossible: fire/melee | fixture fx_shoot_held |
| fixtures | AITactics | fire_events | impossible: fire/melee | fixture fx_shoot_held |
| fixtures | AITactics | tactic_chosen | driven | fixture fx_tactic |
| fixtures | AITrade | trade_completed | driven | fixture fx_trade |
| fixtures | CampRespawn | respawn_reserved | driven | fixture fx_camp_setup; timer |
| fixtures | Camps | camp_recognised, maintenance_step, pathgraph_refresh | driven | fixture fx_camp_setup |
| fixtures | CookingCompat | cooking_config_rpc_refused, cooking_dish_cooked | driven | fixture fx_cooking |
| fixtures | FactionConflict | encounters_observed, outcome_recorded | driven | fixture fx_conflict |
| fixtures | FactionConflict | journal_committed | driven | fx_conflict_journal BEFORE fx_conflict; forced BOTH_REMAIN, journal persistence only; runtime evidence pending |
| fixtures | FoodCompat | food_compat_guard, food_compat_refused | driven | fixture fx_food |
| fixtures | Fortify | barricade_breached | driven | fixture fx_barricade; setting |
| fixtures | Fortify | fortify_placed | driven | fixture fx_kit_place |
| fixtures | Fortify | fortify_refused | driven | fixture fx_kit_refuse |
| fixtures | Holdouts | camp_committed, occupied_holdouts | driven | fixture fx_holdout_due |
| fixtures | InfectedMemory | heat_recorded, memory_cells | impossible: fire/melee | fixture fx_shoot_held |
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
| idle | FactionConflict | territory_regrowth | driven | timer:30m |
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
| manual | Cellars | visual_applied | owner_check | `cellar` now attempts a bounded walk; a reachable floor and renderer admission still need native proof before moving this counter to walk_town |
| manual | TeamPing | ping_delivered | friend_playtest | delivery of a team ping to another player needs a second player; one client has no recipient |
| manual | TeamPing | ping_recipients | friend_playtest | delivery of a team ping to another player needs a second player; one client has no recipient |

## Physically impossible or not claimable on one scripted client

| Item | Reason |
|---|---|
| Firing a gun | `DayZPlayerImplement.c:1161-1210` calls `GetWeaponManager().Fire(weapon)` only when `pInputs.IsAttackButtonDown()` / `IsAttackButton()` are true (`human.c:120/:122`, synced inputs). `WeaponManager.c:485 Fire` runs `ProcessWeaponEvent(WeaponEventTrigger)` locally. The server replays the synced input stream, so a client-only `Fire` only desyncs. `UAInput.SyncedOverride` is compiled only under `INPUT_OVERRIDE` (`UAInput.c:172-190`). The combat step therefore raises, aims and reloads for real, then logs `fire=unsupported:no-native-client-entry-for-fire-input`. |
| Melee | Light and heavy attacks read the same synced inputs (`DayZPlayerMeleeFightLogic_LightHeavy.c:137/:151`, `human.c:75 IsMeleeWeaponAttack`). No override exists for them (`OverrideMeleeEvade` at `human.c:265` is evade only). |
| Confirming a kill by the bot | Follows from the two rows above. Kills stay with the fixtures (`fx_melee`, `fx_shoot_held`, `fx_site_patrol_kill`). The combat step confirms only a target that something else killed (`IsAlive() == false` on a target it was tracking) and never claims to have killed it. |
| TeamPing delivery (`ping_recipients`, `ping_delivered`) | One client has no recipient. The item stays friend_playtest. |
| Cellars visual (`Cellars/visual_applied`) | The `cellar` step now attempts the walk and records bounded refusal evidence. The item stays owner_check until a reachable floor and the renderer-owned counter are proved natively; shared cellar admission is enabled but qualification remains unverified. Only the lighting look is subjective. |
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
| `route` | `points` (flat x,z list of 2..64 waypoints), `gait`, `arrive_m`, `timeout_s` | `HCDriverRoute` (HCClientDriverNav.c) walks the waypoints in order; the default route uses the `scav-chernogorsk` site's own waypoint line (`route:site:scav-chernogorsk`, walk_town phase). Each leg is a walker leg in hand-over mode: 8 s without 1 m of progress climbs one rung of the stuck ladder: back up 2 s (walk speed, angle 180), sidestep +45 degrees for 2 s, sidestep -45 degrees for 2 s, then door (`open_door` on a door in reach of where the player stands, 72 rays, at most 6 s, never walking). Still stuck after four rungs: REFUSED `stuck-exhausted`. 10 m of progress since the last stuck spell restarts the ladder; a reached waypoint resets it. | `arrived waypoint=<n>/<n> climbs=<n> doors=<n> remaining_m=<m>` |
| `combat` | `range_m` (10..150), `timeout_s` | `HCDriverCombat` (HCClientDriverCombat.c). Takes the first rifle from the inventory to the hands (`PredictiveTakeEntityToHands`, 8 s), then reloads once with the vanilla reload key path `PlayerBase.QuickReloadWeapon` when `GetMagazineToReload` finds a magazine (Unjam, AttachMagazine, SwapMagazine or the bullet action, with the WeaponManager checks). Scans every second (`GetObjectsAtPosition3D`, reused arrays) for the nearest live `DayZInfected` or identity-less `PlayerBase` (a server AI) that one `RaycastRV` from the head can see. Raises with `OverrideRaise` and turns and pitches the camera onto it with `OverrideAimChangeX/Y` (an axis whose error does not shrink in a second flips its sign). On target for 0.5 s counts `engaged`. A target that dies while tracked counts `dead_seen`; 3 s out of sight or beyond 1.2 x range counts `lost`; 20 s per target; at most 3 targets and 3 reloads (re-reload when the magazine and chamber are empty). Bleeding, a falling health tendency or a critical health level lowers the weapon and sprints 40 m away from the threat (`retreated=1`). Fire and melee are never attempted. OK with `engaged` > 0 or after a retreat; refused `no-target-within-<range>m` when nothing was in sight; timeout `not-aimed` otherwise. Default route: the `combat` phase, right after walk_town (`range_m` 60, 180 s). | `engaged=<n> lost=<n> dead_seen=<n> reloads=<n> armed=<0\|1> retreated=<0\|1> fire=unsupported` |
| `loot` | `range_m` (5..80), `max_items` (1..10), `timeout_s` | `HCDriverLoot` (HCClientDriverLoot.c). One `GetObjectsAtPosition3D` query per pick (reused arrays, at most 512 objects read) for loose items (`GetHierarchyParent` null, not ruined, within 2.5 m of the player's height). Picks the lowest tier, then the nearest: 0 a magazine the carried rifle takes (`WeaponManager.CanAttachMagazine`/`CanSwapMagazine`), 1 ammunition, 2 food (`Edible_Base`), 3 drink (`Bottle_Base`, `SodaCan_ColorBase`), 4 medical (bandage, rag, disinfectant, tablets, morphine, epinephrine), 5 a map (`ItemMap`); everything else is left lying. Walks to it and takes it with `ActionTakeItem` through `Can` and `PerformActionStart` (the F key). A take counts only once the synced hierarchy puts the item under the player (`GetHierarchyRootPlayer`). When `Can` fails (pockets full) it drops one junk item with `PredictiveDropEntity` and tries once more; junk is a carried cargo item that is not worn, held, attached, a weapon, magazine, food, drink, medical, map or part of the test kit. A failed walk or take skips that item (64-entry skip map). OK with `taken` > 0; refused `no-loot-within-<range>m` when nothing wanted lies in range, `could-not-take` when nothing could be taken; timeout `nothing-taken`. Default route: the `loot` phase, after `combat` (40 m, 4 items, 300 s). | `taken=<n> dropped=<n> seen=<n> skipped=<n> mag/ammo/food/drink/med/map=<a/b/c/d/e/f>` |
| `survive` | `mode` (need or always), `timeout_s` (10..600) | `HCDriverSurvive` (HCClientDriverSurvive.c). Three tasks in order: bandage when `IsBleeding()` (a `BandageDressing` or `Rag`), drink (`Bottle_Base`/`SodaCan_ColorBase` with quantity), eat (`Edible_Base` that is not a medical edible). Mode `need` drinks or eats only when the HUD's water or energy tendency falls or its level is at least WARNING (VirtualHud, the client's own display state); `always` drinks and eats whatever it carries. Each task takes the item to the hands (`PredictiveTakeEntityToHands`, 8 s), then starts the first of the item's own `ContinuousDefaultActionInput` actions whose `Can` passes (`ActionBandageSelf`, `ActionDrink`, `ActionEat*`) through `PerformActionStart`, the hold-left-mouse path. Eating and drinking release the button (`EndActionInput`) after 8 s; a bandage runs until the bleeding stops (30 s cap). Credit comes from synced state only: bleeding stopped, or the item's quantity dropped or the item was used up. OK when any task was credited or nothing was needed; refused `none-done` otherwise; the reasons are listed (`no-bandage`, `no-drink`, `no-food`, `<task>-not-allowed`, `<task>-not-consumed`, `still-bleeding`). Default route: the `survive` phase after forest, mode `always` (after the town loot and the forage pickup). | `bandaged=<0\|1> ate=<0\|1> drank=<0\|1> missing=<reasons\|none>` |
| `vehicle` | `range_m` (5..80), `seconds` (2..60), `throttle` (0.1..1.0), `timeout_s` (30..600) | `HCDriverVehicle` (HCClientDriverVehicle.c) and the pedal holder `HCDriverCarInput` (4_World/HCDriverCarInput.c). One `GetObjectsAtPosition3D` query for the nearest intact `CarScript` whose driver seat (the crew index with `GetSeatAnimationType` == `VEHICLESEAT_DRIVER`) is empty; the default route runs it right after `flip`, so it is the `fx_car_side` car flipped back onto its wheels. Walks to `CrewEntryWS` of the driver seat, then casts one `RaycastRV` per frame from the head through the door (a 5 x 6 grid, at most 30 rays) until the nearest hit is the car, its component maps to the driver seat (`CrewPositionIndex`) and `ActionGetInTransport.Can` passes, and starts the get-in with `PerformActionStart`. Seated once `GetCommand_Vehicle` is not getting in and `CrewDriver` is the player (12 s). Starts the engine with `ActionStartEngine` when `Can` passes (the car's own battery, plugs, fuel and engine decide; nothing is repaired or refuelled; a refusal is `note=engine-did-not-start`). With the engine on, the modded `CarScript.OnInput` (after super, client only, only for the car the local player drives) sets `SetThrottle`, `SetSteering` 0, `SetBrake` and `SetHandbrake` 0 for `seconds`, shifting a manual box to first as the DIAG drive does; then brakes to below 1 km/h (8 s cap), stops the engine with `ActionStopEngine` and gets out with `ActionGetOutTransport`. Out of time while seated still brakes and gets out. OK once the player stands outside again after the engine ran and the car displaced at least 1 m; refused `no-free-car-within-<range>m`, `driver-door-not-usable`, `get-in-not-completed`, `left-the-car`, `get-out-not-allowed` or `get-out-not-completed`. | `seated=<0\|1> engine=<0\|1> drove_m=<n> top_kmh=<n> out=<0\|1>` and `note=` when set |
| action `open_door` | none | Same raycast scan as `close_door`, with `ActionOpenDoors` (Can() fails for a locked or open door; never forced). The actions phase runs it right after `close_door`. | `completed-client-side` |

## Failure handling (no cheating)

| State | How the bot sees it (client-visible) | Recovery |
|---|---|---|
| Stuck | `walk`: no 1 m of progress for 20 s, two alternating sidesteps, then timeout `stuck sidesteps=2`. `route`: 8 s without progress per rung | `route` backs off 2 s, sidesteps +45 and -45 degrees for 2 s each, then scans doors in reach for up to 6 s. Then `refused detail=stuck-exhausted`. Never a teleport or a position fix. |
| Calibration obstruction | Clearance contact or <0.30 m sample displacement at speed >=2 | Rotate the set, report `probe-blocked` for displacement obstruction, and retry within eight sets x four rays. Exhaustion refuses `calib-blocked`; a fitted gain other than the ray model refuses `probe-frame-unsupported`. |
| Dead | `!player.IsAlive()` or no player during an open step | Close the non-respawn step `refused detail=player-dead`, request vanilla respawn, then recalibrate and continue at the next step. At most three recoveries per program; a fourth concludes `unscripted-death-limit`. Recovery has a 60 s deadline, including the player gap; expiry concludes `unscripted-death-timeout`. Scripted `respawn` bypasses the alive/hold/calibration gates. |
| Unconscious or hit/stagger | `IsUnconscious()`, `GetCommand_Damage()` or `GetCommandModifier_Damage()` | Release movement, aim, raise, vehicle and action input; hold the same step with its timers frozen for up to 60 s, then resume. One `hold reason=unconscious` or `hold reason=hit` line per continuous hold; timeout `hold-timeout reason=<state>` if it does not recover. |
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
   `refused detail=stuck-exhausted` line follows four logged rungs; `doors` above 0 shows the door rung
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
   A run waiting 60 s without readiness refuses `movement-or-controls-not-ready`.
2. Use `mirror` (the client and server each override their controller through the existing
   leased path). Requests are degrees in the observed build: `input_angle=90`, while
   `cur_angle=1.57` is the filtered movement angle in radians. The declaration itself does
   not specify override units or world-frame conversion (`3_Game/human.c:253-256`);
   `GetCurrentInputAngle` is unfiltered and `GetCurrentMovementAngle` filtered (`:459-470`).
   The scripts do not establish that mirrored overrides add together. Each endpoint writes
   one angle, rather than adding it to a prior angle.

   Soak 203's forward vector <-6.80,4.41> has bearing -57.04 degrees; right
   <9.44,-6.93> has bearing +126.28 degrees, a wrapped separation of -176.68 degrees.
   Thus a request +90 was antiparallel, and the old camera-yaw clearance rays checked
   unrelated bearings. `right_offset=-90` on a refused run was a default diagnostic,
   not a measured fit. The diagonal's roughly 0.1 m per 0.5 s at speed 3 is obstruction
   evidence and cannot qualify an angle model.

   Native source distinguishes horizontal model orientation (facing) from aim heading
   (`3_Game/dayzplayer.c:1097-1102`). `GetMovement` returns a local direction, whereas
   `GetHeadingAngle` describes camera heading (`3_Game/human.c:21-28`). The ordinary
   `HeadingModel` calls `RotateOrient` (`4_World/Entities/DayZPlayerImplement.c:1715`);
   that visible code only adjusts orientation beyond 0.95*pi aim/facing separation
   (`DayZPlayerImplementHeading.c:64-114`). It does **not** show a lowered weapon causing
   the body to face movement. The animation/native conversion is opaque. Constant
   `GetDirection`, heading and camera readings do not prove the actual animation frame.
   Consequently **the exact native cause of the 180-degree reversal remains unresolved**;
   a +2 mapping below is an observed candidate, not an engine API claim.
3. Probe requests are now **0, +45, +22.5, -45** (`fwd`, `right`, `diag`, `left`), each
   speed 3 for 4 s, then Stop and settle 2 s. For the observed candidate gain +2 these
   test forward, right, diagonal and left rather than repeating the forward line backwards.
   Five real samples at 0.5–2.5 s record positions, current speed/angle, raw input angle,
   body direction, controller heading, local movement, model speed, stance and camera.
   Native readouts: `human.c:22,28,459-470,1183-1184,1470`,
   `3_Game/Entities/Object.c:287,314,338`, `3_Game/Global/Game.c:732`.
   Probe lines retain their fields and add `ray_bearing=B body=Y` before `clear_m`.
   Legacy summary names `b90`, `b45`, `bm90` now mean the right/diag/left **world-bearing
   targets**, not the numeric requests. Read `req_angle` in each probe line.
4. Before each probe, cast one chest-height, terrain-following 16 m geometry ray ignoring
   the player (`3_Game/Global/DayZPhysics.c:199`, `3_Game/Global/Game.c:1176`). Its bearing
   is `body + measured_offset + 2*request`, using model direction yaw
   (`3_Game/Entities/Object.c:314`) rather than raw camera yaw. Initially the offset is
   zero, so the first ray uses expected body heading. A successful forward probe supplies
   `measured_offset = Wrap180(forward_bearing - body - 2*forward_request)`;
   all subsequent rays use that observed frame. This offset survives a blocked-set rotation.
   The first ray remains an expectation: the historical all-zero body readings cannot
   reveal the unexplained north-west frame before any motion has been observed.

   A ray contact logs `probe=blocked` with no movement request. Any sample interval below
   0.30 m with current speed >=2, including the final interval to Stop, instead logs
   `calib retry reason=probe-blocked bearing=B rotation=N` after the completed probe line.
   Both cases discard the set and rotate 45 world degrees (22.5 requested degrees), then
   restart at forward. At most **eight sets x four rays**, one ray per update; exhaustion
   is `calib-blocked bearings=<...> rotations=8 rays=N`. This bounds drive/settle pairs
   to 32 (192 s nominal), plus readiness and frame overshoot.

   Low-speed stalls retain `probe-stalled`. Body change >5 degrees during a probe, or
   camera change >5 degrees relative to the set's start, gives `probe-frame-changing`.
   Displacement must exceed 0.30 m. After Stop, drift projected back toward the start
   above 0.20 m refuses `server-correction`; forward/sideways settle drift is allowed.
   Three of five command-angle samples must match the request within 15 degrees,
   accepting the observed radians readout as well as degrees.
5. Fit actual wrapped request differences against gains +1,-1,+2,-2. The training and
   both held-out residuals must each be <=15 degrees. Since clearance used expected
   gain +2, another fitted gain refuses `probe-frame-unsupported`; inconsistent bearings
   refuse `angle-fit-mismatch`. Command disagreement gives `command-angle-mismatch`.
   A consistent +2 fit gives `reason=frame-probe scale=2 frame=body
   apply=measured-body-frame aim=disabled`. Steering reads live body yaw plus the measured
   offset and divides desired relative bearing by the fitted gain. There is no aim override,
   position write or teleport. These are conservative empirical checks, **not native proof**
   that this spawn supports a correct calibration.

   On a good run, expect four probe lines with `req_angle=0.00,45.00,22.50,-45.00`,
   five samples each, `moved_m>0.30`, `back_m<=0.20`, and summary bearings approximately
   `B, Wrap180(B+90), Wrap180(B+45), Wrap180(B-90)`. The summary must report
   `calib result=ok variant=mirror ... reason=frame-probe ... scale=2 frame=body`,
   all three residuals within 15 degrees and `controls=0`. Subsequent ray bearings must
   agree with those expected travel directions. If these conditions fail, calibration
   remains refused; there is no automatic promotion of historical samples.
6. Startup failures retry after 15 s, at most three startup runs; on-demand walk/route
   retries share the four-run per-entity cap. Step timers start after calibration.
   No native experiment was run for this change. A native-correct movement-frame contract
   cannot be established from these scripts or the obstructed historical probes alone.
   The fixture now searches a fixed west/northwest field shortlist **only at initial
   character creation**, under the existing `autoplayer-initial-spawn` profile marker.
   The server accepts the first dry candidate with at most 2 m total height range across
   its center and four terrain samples at +/-4 m, and clear 16 m geometry rays on world
   bearings 0/90/180/270. Rays run from chest height (1.2 m) to terrain height +1.2 m at
   each endpoint, matching the client probe check. Native APIs:
   `3_Game/Global/Game.c:1176,1196-1197` (`SurfaceY`, `SurfaceIsSea`, `SurfaceIsPond`),
   `3_Game/Global/DayZPhysics.c:199` (`RaycastRV`, geometry type, ignore argument).
   No player exists at this point, so the ray's ignore argument is null; there is no
   player entity to intersect. Work is bounded to 12 candidates x four rays, once per
   creation, with early refusal on water, slope or contact. Four clear cardinal rays
   are a clearance screen, not a guarantee about diagonal paths or reachable loot.

   Candidate indices are **one-based**, in this fixed order (all within 1.48 km of the
   old <6500,2500> point). These are field-search coordinates, not a completed native
   geometry survey; the server checks them at runtime:

   | Candidates | Coordinates <x,z>, in order | Area rationale |
   | --- | --- | --- |
   | 1–4 | <5500,2800>, <5400,2800>, <5300,2800>, <5200,2800> | Western field belt first: stay west of the northwest urban fringe, with a shorter approach back to town. |
   | 5–8 | <5500,3000>, <5400,3000>, <5300,3000>, <5200,3000> | Next inland band: alternatives if the nearer fringe has walls, fences or unsuitable slopes. |
   | 9–12 | <5500,3200>, <5400,3200>, <5300,3200>, <5200,3200> | Farther northwest band: spread the search beyond the nearer obstructions while keeping the town approach local. |

   Success: `[HC Driver] spawn fixture=1 initial=1 at=<x,z> candidate=<i> checked=<n>`.
   Exhaustion: `[HC Driver] spawn fixture=1 initial=1 at=<6500,2500> candidate=fallback
   reason=<first failure> checked=12`, where the reason is `water`, `slope` or `blocked`
   from candidate 1. Exhaustion retains the old point without asserting clearance.
   This substitutes only the position passed to `super.OnClientNewEvent`, before
   `CreateCharacter` (`5_Mission/mission/missionServer.c:549,573,589`); persistence login
   and existing characters do not use this hook. No position or orientation write is made.
   Fixed yaw at creation was not added: neither `OnClientNewEvent` nor `CreateCharacter`
   takes yaw (`missionServer.c:499,549`); vanilla calls `CreatePlayer` with radius 0 and
   spec `"NONE"` (`missionServer.c:502`, `3_Game/Global/Game.c:332`), which also has no
   orientation argument. `Object.c:311` sets orientation on an existing entity and is
   outside this fixture's scope.

   `rg SPAWN_XZ mods/HollowCountryTest` has no matches. The constant actually lives in
   `tools/testing/driver_script.py:29` and seeds planner position/last-walk-target and
   the first `near()` decision; it does not generate targets by coordinate offsets.
   Authored police/scavenger town targets remain sensible local destinations, but the
   first-walk timeout still estimates distance from the old point. The first police walk
   has a 179 s timeout versus 1.09–1.51 km from the shortlist (390–539 s at the planner's
   assumed 2.8 m/s jog); standalone `walk_town` gets 335 s versus 1.31–1.71 km
   (468–610 s). These initial timeouts can expire before arrival. Updating the planner's
   initial-distance budget is needed follow-up in `tools/testing/driver_script.py`,
   outside this change's owned files. Actual travel and obstacle avoidance remain
   unverified. The `walk_town`
   route, site search, combat, climb and cellar steps need town surroundings but explicitly
   walk/route there. Standalone combat/loot phases call `near(TOWN)` first; vehicle has
   its own local car fixture. Generic actions `search`, `close_door`, `open_door`, `salvage`
   and `flip` depend on nearby suitable objects and may refuse if run at an open spawn.
   Loot within 40 m, climb/cellar within 100 m, and combat within 60 m also still need their
   respective local targets after arrival. No step logic or planner constant was changed;
   broader action targeting would require a separate change.

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

   The server additionally logs its own frame on the first **applied** frame of each
   serial (after issuing the overrides, `frames=1`) and in `HCMoveClose` (before clearing
   overrides). Both phases share a separate **64-line per-player lifetime cap**; the
   existing 128-line `server-move` cap is unchanged. A serial that never applies has no
   start line, but can have a close line with `frames=0`; request fields are the last
   accepted request, or zero if no request was accepted. Cap exhaustion can truncate pairs.

   ```text
   [HC Driver] server-frame serial=<S> phase=start yaw=<deg> dir=<x,z> pos=<x,z> req_angle=<deg> req_speed=<s> cmd_angle=<v> frames=1
   [HC Driver] server-frame serial=<S> phase=close yaw=<deg> dir=<x,z> pos=<x,z> req_angle=<deg> req_speed=<s> cmd_angle=<v> frames=<n>
   ```

   Numbers except serial/frames have two decimals (positions rounded to 0.01 m).
   `yaw` is the server entity's `GetOrientation()[0]` in degrees; `dir` is
   `GetDirection()` x/z; `pos` is `GetPosition()` x/z
   (`3_Game/Entities/Object.c:301-305,314,287`). `cmd_angle` is the raw
   `HumanCommandMove.GetCurrentMovementAngle()` (`3_Game/human.c:458-460`), or `n/a`
   if the move command no longer exists at close. The native comment describes
   -180..180 but the client has observed radians; retain the raw value as evidence.
   This is a command readout at the callback, not proof that the just-issued override
   has already affected animation. The client `calib probe=... serial=<S>` already logs
   the same serial (`HCClientDriver.LogProbe`), allowing a join with both server phases.
   No identity data is logged. Compare equivalent wrapped yaw values: if the server yaw
   is about -54 degrees while the client's body/camera/dir yaw reads 0, the frame split
   is confirmed. If server yaw also reads 0, the offset comes from somewhere else.
   A yaw offset alone still cannot explain the historical antiparallel right probe;
   compare start/close direction and command angles before attributing a cause.
   No native runtime experiment has yet tested this diagnostic or the spawn shortlist.

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
   | Dead / unconscious / hit command / not in move command / missing controller | `dead` / `unconscious` / `hit` / `command-change` / `no-controller` |
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

### Round 10a: movement robustness (#368)

Sprint requests speed 3 at angle 0 regardless of calibration success. It never triggers an
on-demand probe. It still requires the move command, controller and ready controls; result
reasons are `no-move-command`, `no-input-controller`, `not-ready` or `no-movement`.
The existing startup calibration remains; this change removes sprint's mapping dependency.

`HCDriverStepHold` gates ordinary steps before any step or nested-loop timer advances;
scripted respawn runs before this gate. Alive
unconscious players and full-body/additive hit commands release input without discarding the
walker leg or route/action phase. Native evidence: `3_Game/human.c:1559` returns
`HumanCommandFullBodyDamage` from `GetCommand_Damage()`; `:1616` returns the light-hit
`HumanCommandDamage` modifier from `GetCommandModifier_Damage()`; `3_Game/Entities/Man.c:63`
provides `IsUnconscious()`. A continuous hold logs once, lasts at most 60 s, and resumes the
same step. Death refuses the current non-respawn step with `player-dead`, then requests
vanilla respawn through the same helper as scripted `respawn`
(`5_Mission/GUI/InGameMenu.c:346-365`; menu lookup/entry: `3_Game/tools/UIManager.c:4,160`).
Recovery waits for a distinct loaded player with movement ready, resets calibration via
`calib reset reason=respawn`, and continues the next step after fresh calibration.
The recovery deadline is 60 s of local engine time (`3_Game/Global/Game.c:1535`), including
missing/unloaded-player ticks. Three recoveries are allowed per program; the count survives
player resets. A fourth death concludes `unscripted-death-limit`; expiry concludes
`unscripted-death-timeout`. Even death during the final step completes recovery before done.
Scripted `respawn` dispatches on a dead player and continues through the no-player gap;
its own timeout and readiness checks remain active before normal calibration resumes.

```text
[HC Driver] unscripted-death step=<id> respawn=ok|timeout recoveries=<n>
[HC Driver] conclude reason=unscripted-death-limit|unscripted-death-timeout
```

The `conclude` reason precedes the existing unchanged `done run=...` receipt, so the campaign
parser still recognizes completion. These are driver receipts, never feature counters.
Native actions can be interrupted by the engine: their existing completion checks still
apply after recovery; frozen driver timers do not pause the engine's action animation.

Every walker leg initially longer than 15 m watches 3.5-second position-delta windows of
steady commands (at most 10 degrees of heading change, at least 3 m displacement). Holds,
turns, hitches longer than 5 s and sidestep recovery discard these windows. Two consecutive windows with >20-degree
error in the same direction correct `HeadingOffset` by `Clamp(actual-commanded,-30,30)`.
Corrections are globally spaced by at least 5 s, including across route legs. The next
command uses the corrected offset. Actual bearing uses positions only, even when heading,
body and movement readouts are dead; no position is written.

A new loaded player entity clears calibration results, run/attempt counters, retry waits,
angle scale/sign, frame selection/offset and walker observations. The first player is
initialization; subsequent entities log `calib reset reason=respawn` and receive the normal
readiness wait and fresh four-probe calibration. Missing-player ticks preserve the prior
entity marker so the reset is detected after a gap.

The existing **4854091** RPC now carries a server-to-owner close reply `(serial, reason)`;
request schema is unchanged. It is reliable and sent once per closed serial to the owning
identity only (`3_Game/gameplay.c:104-117`). The client drops stale replies and expected
`none` Stop replies. A matching abnormal close releases input, reports the server reason
and refuses the active step (or calibration probe), without waiting for its movement timeout.
Serials explicitly stopped for a temporary hold log abnormal closes but cannot refuse the
suspended step, even if the reply arrives after recovery. Server-observed `hit` and
`unconscious` closes release movement and remain recoverable, including a short hit that
finishes between client ticks; the server checks both native damage commands before applying input.

Route recovery has exactly four rungs: back-up, side-right (+45), side-left (-45), door.
Each new 8 s no-progress spell advances one rung; movement rungs last 2 s and the door scan
lasts at most 6 s. Another stuck spell after rung 4 refuses `stuck-exhausted`. Ten metres
of fresh progress or a completed waypoint resets the ladder. No waypoint is skipped.

Lead-only native evidence to collect (placeholders S, D, O, N are step/number fields):

```text
[HC Driver] step=S kind=sprint result=ok detail=start=<...> end=<...> moved_m=N cmd=N controls=0 sprinted-Ns
[HC Driver] step=S hold reason=unconscious
[HC Driver] step=S hold reason=hit
[HC Driver] frame_correct step=S delta=D offset=O
[HC Driver] calib reset reason=respawn
[HC Driver] lease_closed reason=lease-expired
[HC Driver] step=S stuck rung=1 maneuver=back-up
[HC Driver] step=S stuck rung=2 maneuver=side-right
[HC Driver] step=S stuck rung=3 maneuver=side-left
[HC Driver] step=S stuck rung=4 maneuver=door
[HC Driver] step=S kind=route result=refused detail=start=<...> end=<...> moved_m=N cmd=N controls=0 stuck-exhausted waypoint=... climbs=4 doors=... remaining_m=...
```

Use one server/client: sprint after refused calibration; interrupt each step family with a
light hit, full-body stagger and recoverable unconsciousness; verify one hold line and the
same step resumes, then check a >60 s hold and a death. On a long straight leg with dead
readouts, perturb the frame offset and confirm two qualifying windows before a correction,
<=30 degrees per correction and >=5 s spacing. Respawn after reaching the calibration cap
and observe a fresh run=1 / attempt=1 probe sequence. Delay movement refreshes beyond 500 ms
and verify the server's `lease-expired` summary is followed by client `lease_closed` and
step refusal; ensure normal Stop and stale replies do not refuse later steps. Obstruct a
town route and verify all four rungs, their durations, exhaustion and progress resets.
These are test-driver diagnostics: **no new `[HC Use]` counters**; existing `[HC Ready]` and
feature-owned `[HC Use]` lines remain the evidence for the actual features reached.

`fx_site_patrol_kill` is registered with the same dev fixture flags as `fx_shoot`/`fx_melee`.
The existing `enforce_lint` gate now checks every test addon `HCOwns` literal `fx_` comparison
against `HCAdminCatalog` registrations (HC-E055), catching rejection before provider dispatch.
This command catalog does not feed `tools.package.admin_world_catalog`'s map-anchor outputs;
its generated artifacts and digests need no regeneration for this row.

### Round 10b: step kinds for unreachable counters (#368)
These kinds are in `HCClientDriverExtra.c` and the builder in `tools/testing/driver_script.py`. A client `result=ok` is never evidence on its own. The server `[HC Use]` counter is the evidence.

| Kind | Fields | What it does | Server evidence |
|---|---|---|---|
| `search_site` | `site, timeout_s` | Walks to the named site's nearest building with doors, goes in to previewed storage, then runs the existing six-second search action | `Interiors/house_search_completed`, `SearchBinding/house_bound` |
| `take_lead` | `timeout_s` | Takes nearby Paper through the real take action, then `write use=taken` | `NotesCompat/notes_lead_tracked`, `notes_lead_protected` |
| `raise` | `range_min_m, range_max_m, seconds, timeout_s` | Approaches a non-hostile HC faction of another group to 40-80 m, then aims and raises through native input; never fires | `v2-expansion-living-world/caution_warn` |
| `hold_ring` | `to, hold_s, timeout_s` | Walks to a materializer ring point and holds within its drift limit | `Materializer/actors_materialized`, `MaterializerBridge/party_materialized`, `Pickers/trip_started` |
| `respawn` | `timeout_s` | After `fx_die`, calls vanilla `InGameMenu.GameRespawn(true)` (5_Mission/GUI/InGameMenu.c:339-365) and waits for movement readiness; the server picks the camp | `CampRespawn/respawn_reserved` |

Example client lines: `[HC Driver] step=s16 kind=raise result=ok detail=reason=raised-neutral fire=none`, `... kind=search_site result=ok detail=reason=search-site-completed-client-side`, `... kind=hold_ring result=ok detail=reason=ring-held`, `... kind=respawn result=ok detail=reason=respawn-movement-ready`, `... kind=take_lead result=ok detail=reason=lead-candidate-write-action-started-rpc-sent`.

Known limits, unverified in DayZ:
- Lead identity is not replicated to the client, so `take_lead` picks Paper and only the server counters prove it was a lead.
- The ring point is fixed from mission data (1300 m west of the police site anchor). A live eligible row there is not guaranteed.
- `search_site` needs reachable admitted storage and available CE supply.

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

## `climb`: elevated haven for an infected siege

`{"kind":"climb","range_m":100,"hold_s":90,"timeout_s":360}` searches for the
nearest building with a native ladder, walks to ladder 0's bottom, enters using
`ActionEnterLadder`, climbs using the local player's movement controller, exits
at the top, holds there, and re-enters the same ladder to descend. The `walk_town`
phase runs infected combat, then one `fx_shoot_held` admin fixture immediately
before this step to draw nearby infected. The fixture must be authorized and the
player must have a fireable held weapon and AI within 60 m; its own result proves
whether noise occurred.

The schema accepts `range_m` 5–150, `hold_s` 1–600 and `timeout_s` 10–1800,
with timeout strictly greater than hold. One object query is scanned incrementally
in a work budget; entry uses at most 40 real rays, one per frame. Action conditions
retain the native approach-side, distance and component checks. No target component
is invented, no command is started directly, and no position is written.

Native evidence: `3_Game/Entities/Building.c:23-25` exposes ladder endpoints but does
not document their coordinate space. The driver logs `climb coordinates raw_bottom=…
model_bottom=… raw_top=… model_top=… space=<world|model>` once. Like the siege anchor,
it provisionally converts when the raw bottom is more than 50 m from the building;
invalid or unelevated endpoints are refused. `ActionEnterLadder.c:19-114,117-150`
checks the real geometry target and starts `StartCommand_Ladder` through the client
action manager. `ActionExitLadder.c:15-31` exits when `CanExit()` permits it.
`3_Game/human.c:253-256` supplies speed/angle overrides and `:1512` reads the command.

The result line is `[HC Driver] climb building=<type> ladder=<i> top_y=<m>
held_s=<s> result=<ok|refused|unsupported> detail=<reason>`. `top_y` is the observed
player height after the top exit (zero if never reached). `ok` requires observed
native command exits at the top and bottom and the completed hold. Missing client
entry yields `unsupported`; approach, action, endpoint or timeout failures yield
`refused`. On timeout while attached, movement is released every frame and the
normal exit action is attempted. A receiver-local clock bounds draining at
`timeout_s + 30 s`, including while normal alive/hold gates would suspend the
step. At that cap it prints exactly once:

```text
[HC Driver] step=S kind=climb result=fail detail=reason=climb-drain-timeout command=<native command id>
```

Input stays released. The driver advances only after `MovementReady` passes and
the ladder command is absent. If this has not happened within another 60 s,
the driver stops with `[HC Driver] done run=<run> reason=climb-stuck`, allowing
the soak's existing 120 s tail to finish. This diagnostic is followed by the normal
count summary (`done run=... steps=... ok=... refused=... unsupported=... timeout=...`),
which the existing soak parser requires to arm that tail. No cancellation or position write is used.

This path is unverified until a native run. Inspect both endpoint readings, entry
from each end, forward/backward movement, the 90 s hold, and return to ground.
Also test timeout during ascent and descent: no subsequent step may begin while
`GetCommand_Ladder()` is present. A successful climb alone does not prove a siege:
an ambient infected must target the elevated player and give up. Server evidence is
`[HC Nav] siege start anchor=<mesh|ladder> members=<m> n=<n>` and
`[HC Use] module=InfectedSiege feature=siege_started count=<n>`; a ladder anchor also
emits `feature=ladder_guard`. The driver manufactures no feature counters.

## `cellar`: bounded cellar walk and refusal evidence

The `walk_town` phase adds `cellar` after its interior, combat and climb steps,
with `range_m=100`, `hold_s=20`, `timeout_s=240`. Its `classes_from` field is an
embedded array of class names generated from `mission/hollow-country/cellars/classes.json`
(currently 28 survey candidates). It is not a client file path. Schema limits are
1–64 unique class names, range 5–150 m, hold 1–600 s, timeout 10–1800 s, and
timeout strictly greater than hold. The builder marks the resulting position uncertain.

`HCClientDriverCellar.c` makes one bounded-radius `GetObjectsAtPosition3D` query
(`3_Game/Global/Game.c:930`), scans it incrementally with `HCWorkBudget` (64 units),
and keeps the four nearest matching buildings. It approaches a native door sound
position (`Entities/Building.c:73`), uses the existing vanilla door action restricted
to that building, and walks inward using `HCDriverRoute` and its recovery ladder.
Each entered building gets four downward geometry rays, one per tick, from two
interior columns and two starting depths below terrain, ending 12 m below terrain.
`DayZPhysics.RaycastRV` (`3_Game/Global/DayZPhysics.c:130-143,199`) must return an
upward-facing hit on that building more than 2 m below `SurfaceY`. The total is
at most 16 floor probes per step; the existing door helper has its separate bounded
action rays. These sparse probes may miss a cellar and are not a complete survey.

The route walks toward the lowest detected floor. Horizontal arrival alone cannot
pass: the actual player must be more than 2 m below terrain, report
`IsSoundInsideBuilding()` (`Entities/Man.c:37`), and have the renderer-owned
`HCCellarsClient.HCVisualActive()` receipt continuously for the hold. A bounded
breadcrumb list records the downward walk; the return follows it in reverse through
the same door and requires an outside-building reading before success. No depth,
lighting state, admission receipt or feature counter is written by the driver.

```text
[HC Driver] cellar building=<type> pos=<x,z> depth_m=<observed depth> result=ok
[HC Driver] step=S kind=cellar result=ok detail=returned
[HC Driver] cellar result=refused reason=no-cellar-floor tried=<type>@<x,z>;...
[HC Driver] cellar result=refused reason=cellar-route-blocked tried=<type>@<x,z>;...
[HC Driver] step=S kind=cellar result=refused detail=reason=<reason>
```

The refusal evidence lists at most four tried buildings; an empty `tried=` means
the query had no matching instance. Inaccessible doors, failed routes, missing
inside readings, or a floor without a renderer receipt cannot pass. Current shared
admission is enabled with reason `admitted_unverified_native_cellar_qualification_pending`;
the stale disabled wording in `HCCellarsClient.c` does not describe that gate's
current return value. This implementation does **not** yet establish that
`Cellars/visual_applied` is driven. Do not change
`soak_phases.json` on offline evidence. After native proof, the lead should remove
`manual["Cellars/visual_applied"]` and add
`features["Cellars/visual_applied"] = "walk_town"`; the subjective cellar look stays owner.

Native proof must cover door coordinates/approach, collision-bound coordinate space,
ray normals and real floor depth, a reachable downward route, the continuous 20 s
hold, and the same-door return. The existing module must emit
`[HC Use] module=Cellars feature=visual_applied count=<n>` and
`[HollowCountry] V2 client cellars visual=below_terrain_inside_building` during that
walk. Existing preference opt-outs remain respected; changing admission or preferences
is outside this worker's scope.

## ai_clear: attributed full clear, death and respawn (#334)

`ai_clear` is the last driven campaign phase, immediately before idle, with a nominal
15-minute budget. It uses existing `walk`, `stand`, `admin` and `respawn` steps.
The offline preflight considers authored guard slots of initially held zones within
1800 m of the preceding planned position, preferring guards over the police fallback.
A second distinct candidate must be within 500 m of the first. Each walk records its
choice and `reason=held-guard-slot-or-police;reach=bounded-foot` in the plan index,
uses the existing stuck/arrival checks and arrives within 50 m of the authored slot.
These are bounded on-foot candidates, not proof of navmesh reachability or live AI.
In particular, the preceding mission step can move to a runtime published mission;
the offline planner cannot know its final position. The native walk result and the
fixture's requester/member 500 m checks must validate that case. No position is written.

When run from the normal join spawn, the choices are Balota's first held guard slot
(6652.3, 2907.0), then police-chernogorsk (6564.47, 2551.96), about 366 m apart.
The full default route's last known authored point is Bor South Rest, so its candidate
is Zelenogorsk's held guard slot (2148.1, 3565.1); there is no second authored candidate
within 500 m. Runtime live patrol selection can differ: the fixture prefers a different
site on the second invocation, then zone guards, police-chernogorsk, and other nearby
live director patrols, choosing the nearest live member within each preference class.
No eligible candidate produces a refusal without a kill. A preflight with no nearby
candidate produces a skip note and no death or respawn.

The steps are: walk in; stand 20 seconds for radius/caution observations; invoke
`fx_incident` and `fx_tactic`; request the attributed clear; stand 200 seconds (the
fixture stops at 180); stand 120 seconds beside that site; approach the second site
when available; stand 20 seconds, request the health clear, stand 200 then 120 seconds;
finally `fx_die` and one CampRespawn attempt with a 180-second timeout. Without a second
authored candidate, health mode is still requested at the first location and can refuse
`no-patrol`. There is no existing stand-until-server-line step, so 200 seconds is always
used. No existing step resolves the runtime death position, so the return walk is skipped.
Travel, hold timeouts and respawn can make the phase longer than its 25-minute budget.

The existing admin RPC transports an integer, and the client accepts only digits.
Thus `admin cmd=fx_site_clear value=0` encodes `mode=attributed` (also the default),
and `value=1` encodes `mode=health`. Literal `mode=...` text cannot cross that RPC;
support would require changing client/RPC files outside this task's scope. The help
row exposes the numeric choices. `fx_site_patrol_kill` is unchanged.

The new test-only fixture uses native scripts-1.30.164289
`3_Game/Entities/Object.c:1128-1138`:
`ProcessDirectDamage(int damageType, EntityAI source, string componentName, string ammoName,
vector modelPos, float damageCoef = 1.0, int flags = 0)`.
The source is the authenticated requester, damage type is `DamageType.FIRE_ARM`
(`3_Game/DamageSystem.c:10-13`), damage zone is empty/global, ammo is `Bullet_556x45`,
model position is zero and the damage multiplier is 1000. The installed native
`weapons_projectiles.pbo/config.bin` was inspected with the existing config reader:
`CfgAmmo/Bullet_556x45` has parent `Bullet_Base`, scope 1. The fixture also checks that
class in the live config (`3_Game/Global/Game.c:612`). Binary configs have no line numbers.
Health mode uses `Object.c:1015 SetHealth("", "", 0)`. Supporting entity APIs are
`Object.c:215/287/517` (pending deletion, position, alive); the one non-repeating
one-second callback chain uses `Game.c:1535/1550` and `2_GameLib/tools.c:61`.

`3_Game/Entities/EntityAI.c:1104 EEKilled(Object killer)` is observed by a test-only
override of the native `PlayerBase.c:1214` ancestor, which then calls `super`. It never fabricates a kill event. Attributed mode
waits one tick for a deferred EEKilled (`last=requester-eekilled-deferred`), then stops with
`refused:attribution-unconfirmed` if the event still does not name the exact requester.
After the first kill, a patrol that is gone or a spent member budget reports `result=terminal`
(`last=patrol-gone` or `last=member-budget`), not a refusal. A native experiment must establish that this API actually
produces lethal requester-attributed damage through this build's full event chain.
If it fails, the lead must use the existing `fx_shoot_held` pattern (requester's held
weapon, nearest AI within 60 m), rather than crediting an unattributed death. That
fallback cannot safely be fired automatically after an already lethal unconfirmed
hit, since it could kill a different member. No native experiment was run here.

Each tick first checks mission finishing and never re-arms afterward. Entity references
across callbacks are weak. The fixture snapshots at most 16 live members before damage,
re-resolves through the public hold accessors before each subsequent kill, and waits for
both `HCDeathHeld()==false` and six seconds after the preceding kill. No group is read
while held. It stops on public `m_HCLive=false` after a kill, its initial member budget,
16 kills, a refusal, or 180 seconds. `last=` describes observed public state, not a claim
to have read an RPT line. The report independently verifies the actual terminal logs.
The fixture never increments a counter and never sets `m_HCFinished`.

Both modes should naturally reach `SitePatrols/death-hold-armed` per death and
`SitePatrols/death-hold-released` after clean non-final deaths, or the diagnostic
`SitePatrols/death-hold-deferred`. The final kill is terminal and is not expected to
release. Attributed mode additionally exercises the attacker-dependent defence
`SeedTarget`, adapter `RecordKill` (only when an encounter is actually bound), and
Stance attacker memory; these calls do not each imply a separate use counter.
Health mode cannot prove those paths. `AISelfDefence/hit_reaction` is conditional on a
natural hit reaction, never an unconditional phase requirement. The approach/fixtures
seek `optional-expansion-human-ai/site_radius_entered`,
`v2-expansion-living-world/caution_warn`, `AIIncidents/response_started` and
`AITactics/tactic_chosen`; the final respawn seeks `CampRespawn/respawn_reserved`.
The campaign suppresses the earlier fixtures-phase death when ai_clear is selected,
because CampRespawn has an 1800-second per-account cooldown
(`HCCampRespawn.c:120-153`). The three existing reach rows still tied to fixtures
(`BodyStories/body_observed`, `BodyStories/death_checked`, `CampRespawn/respawn_reserved`)
are now explicitly unresolved; the lead owns remapping after native proof. No counter
mapping or activity expectation was changed.

Exact evidence to retain (placeholders denote values, not invented log wording):

```text
[HC Test] fx_site_clear site=<id> mode=<attributed|health> start=1 reason=live-patrol-selected
[HC Test] fx_site_clear site=<id> kind=<zone|site> mode=<attributed|health> kill=<k> members_left=<n> held_ms=<ms>
[HC Test] fx_site_clear site=<id> mode=<attributed|health> result=<terminal|timeout|refused:reason> kills=<k> elapsed_s=<s> last=<observation>
[HCX SitePatrol] death_hold armed site=<id> kills=<n>
[HCX SitePatrol] death_hold_deferred reason=DEATH_HOLD_STALE site=<id>
[HC Expansion AI] site <id> cleared-at=<ts> saved=<b>
[HC Expansion AI] site <id> despawned (intact=false)
[HC ZoneGuards] zone=<id> from=held to=abandoned
[HC Use] module=SitePatrols feature=death-hold-armed count=<n>
[HC Use] module=SitePatrols feature=death-hold-released count=<n>
[HC Use] module=SitePatrols feature=death-hold-deferred count=<n>
[HC Use] module=AIIncidents feature=response_started count=<n>
[HC Use] module=AITactics feature=tactic_chosen count=<n>
[HC Use] module=AISelfDefence feature=hit_reaction count=<n>
[HC Use] module=optional-expansion-human-ai feature=site_radius_entered count=<n>
[HC Use] module=v2-expansion-living-world feature=caution_warn count=<n>
[HC Use] module=CampRespawn feature=respawn_reserved count=<n>
```

Use counts are cumulative (an optional `fixture=<n>` suffix is retained by the normal
counter system); compare before/after each mode in the native RPT, rather than attributing
an entire run's totals to a mode. There is no clean-release text line beyond the existing
use counter. `cleared-at` can also describe a partial raid, so it alone does not prove
terminal teardown. The ai_clear report keeps the fixture, armed/deferred, cleared-at,
despawned and abandoned lines for its selected sites and reports each site's despawn
count, plus cumulative hold/hit-reaction receipts grouped by the mode start markers.
A receipt observed in a window is not an attributable delta; missing receipts are unproven.
Exactly one despawn line is required, with zero and duplicates marked FAIL.

Suspected production defect, deliberately untouched: `HCXAISitePatrols.c:311-350`
releases the hold only after `!HCHasGroup()` following provider despawn. If the provider
slot remains set after the last member disappears, subsequent held ticks may re-enter
`HCEndPatrol`. Measure across the 120-second observation. Note that `wasLive` guards the
`Despawned` callback, so repeated entry might still emit only one despawn line; a count
of one cannot alone disprove repeated entry. Do not assert `m_HCFinished`; zone guards
set that only in `HCXZoneGuards.c:447 OnStop`.

`BodyStories/body_observed` is excluded: it requires owned deaths at transient,
materialized situation sites (`HCBodyStories.c:100-262`), excluding police and zone sites.
All infected-family counts observed in this phase are excluded as confounded:
abandonment enables `HCXZoneGuards.c:425-439 StepOverrun`, which can spawn infected
300–1000 m away. Existing `Campaign.run` server/client process monitoring already ends
a server-crash run mid-phase (`soak_campaign.py`, the `wait_for` call monitoring both
images); no second crash/shutdown path was added. These are offline changes, not native
or multiplayer proof; the lead runs the compile gate after merge, then the experiment.

`fx_conflict_journal` runs before `fx_conflict` because the latter may leave a quota
slot pending across the driver's three-second fixture interval. Run it every soak:
registration makes `FactionConflict/journal_committed` INERT if no finish commits.
One synthetic row per boot uses the normal death/finish/world save barriers, with
`fixture=1`; it proves no real AI binding, disengagement or body death behavior.
At 96 journal rows the headroom guard refuses; history is never pruned, so the
disposable testbed eventually needs a wipe. Native compile, soak and restart
checks remain pending.


Journal selection first prefers an opposed cell, then uses the farthest
pending/far/leased-qualified place (catalog-order ties) with a world-data faction
other than raiders satisfying Relation(raiders, faction) == -1. This journal-only
fallback needs no territory, strength or fresh world. The former no-opposed
failure now queues forced BOTH_REMAIN; only exhausted qualified selection refuses.
Crash after durable bind remains UNKNOWN_RESTART, never fixture promotion/apply;
durable finish before stop applies normally next boot without fixture receipts.
Approaching the place defers publication until FAR. fx_conflict continues to
exclude an unapplied journal place. All runtime checks remain pending.

Selection refusals keep their matching prefix and use these fixed formats:

```text
[HC Admin] cmd=fx_conflict_journal result=refused reason=no-eligible-distant-opposed-cell places=N pending=a near=b leased=c not_opposed=d fixture=1
[HC Admin] cmd=fx_conflict result=refused reason=no-eligible-distant-opposed-cell places=N pending=a near=b leased=c active=d budget=e held=f not_opposed=g daily_cap=0|1 fixture=1
[HC Admin] cmd=fx_conflict_journal result=ok reason=fixture-journal-queued forced=1 places=N pending=a near=b leased=c not_opposed=d fixture=1
[HC Plan] HC-37 fixture_journal_bound encounter=conflict:<n> place=<id> left=raiders right=<f> fixture=1 forced=1
```

`daily_cap` is computed once before the fx_conflict place loop. Its `budget`
count combines place cooldown and global daily-cap exclusions: with
`daily_cap=0` it is exactly the number of places on cooldown; with `daily_cap=1`
it counts every place that reached that filter. Each place increments only its first failing filter, in
pending / near / leased order, followed by active / budget / held / not_opposed
for fx_conflict. On a journal selection refusal,
`pending + near + leased + not_opposed == places`. `not_opposed` counts places,
not faction pairs. Forced success includes the same journal selection counts;
normal success remains `fixture-journal-queued` with no forced suffix. The bound
line adds ` forced=1` only for fallback; completion formats stay unchanged.
Kit fallback remains `fixture-journal-available`, with no state change or callback
capacity spent. Other refusal tokens and their guards are unchanged.
