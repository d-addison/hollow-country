# R3 one-client smoke route — planned, unverified

This is an exercise plan, not runtime evidence or a release pass. Owner decision
2026-11-21: **no waivers**. Every registered default-on `[HC Use]` counter must
be ACTIVE after the 30-minute soak plus one-client smoke on the exact release
commit, except explicitly listed OWNER-CHECK counters (owner decision 2026-11-23).
The [JSON plan](../tools/release/r3_smoke_plan.json) now enumerates all 130 source
registrations; the earlier plan contained 76 entries, not the previously documented 75.
Coverage is checked against the candidate source tree by `activity_check --check-plan`.
One server plus at most one client is the
acceptance limit. This cannot establish multiplayer behaviour.

**There is no verified all-counter route under 45 minutes in current code.**
The compact route below budgets about 40–45 minutes of play **after staging**, with
shared actions overlapping. It covers every `client_action`/`admin_action` entry
and provides attempt stops for the uncertain entries. It cannot guarantee their
success. A missing required world state, unsupported cellar, unqualified journey,
empty finite stock, absent native command or INERT receipt blocks release; elapsed
observation allowances never convert failure to acceptance. Do not erase journals,
refill finite stock, or replace a missing exercise with a probe.

## Evidence and preparation, before the play clock

- [ ] Lead records candidate commit and build manifest, runs the serial native
  compile/boot checks and prepares the normal release gate. This worker ran no
  DayZ, DayZDiag, Workbench, native compile or runtime experiment.
- [ ] Keep all features enabled. Use a disposable **private** rehearsal profile,
  retaining provenance and journals for the measured window; separately test upgrade
  from the previous release. Preparation is not a substitute for upgrade evidence.
- [ ] Install the declared dependencies, CE overlays, search manifests, scene,
  route and template data from that commit. Do not use another profile as bundle data.
- [ ] Authenticate the owner with existing `HollowCountry.Admin` permission or
  private HC allowlist. Never paste identifying configuration, snapshots or raw logs
  into public documentation. No generic HC spawn menu is assumed here.
- [ ] Gather genuine supplies before the measured route: `ChernarusMap`,
  `KitchenKnife`, `CamoNet`, `Mich2001Helmet`, `TortillaBag`, two loose
  `UniversalLight` items, working `Battery9V`, sufficient `DuctTape`,
  `PersonalRadio`, `Crowbar`, `Wrench`, a weapon with real ammunition and dressings.
  Carry kindling/fuel/ignition (`ShortWoodenStick`, `Rag`, `Firewood`, `Matches`).
  A serviceable car, pitched `SmallTent`, native storage (`WoodenCrate`) and a
  lit-capable residential hearth must already be available or gathered normally.
  HC does not have a verified kit-grant command. Preparation can exceed 45 minutes.
- [ ] Park transport on open ground in Chernogorsk; prepare an empty sideways
  nonruined car separately only if a safe native rollover is practical. Do not
  move players/AI by teleport. Never park across a door or required escape.
- [ ] Select an in-game date in June–November for forage. Confirm actual daylight
  for lighting and a later hour >=18 for house light observation; smoke requires
  native base temperature <10 C by default. These are separate predicates.
  the `serverTimeAcceleration` and `serverNightTimeAcceleration` settings in `mission/hollow-country/INSTALL_AND_ROLLBACK.md` document 4x day / 32x
  night settings, but these do not guarantee cold weather or qualify a cellar.
  Schedule the measured boot/window accordingly; otherwise add a real wait.
  HC `day` changes escalation, **not** solar time or the calendar. HC `weather`
  does not set temperature or clock. No invented time-setting menu is used.
- [ ] Before boot, enable the existing private `HollowCountry/measure-cellars`
  marker for the real diagnostic survey. It is read at startup, not dynamically.
  Preserve its output; a measured class still has no native cellar qualification.
- [ ] Lead runs the full **30-minute** soak on this commit. Watch zero SCRIPT (E),
  zero VMEs, no R2 >20 ms, no crash/stall or enabled ready=false. Check all
  `[HC SelfTest] name=<name> pass=<true|false> detail=<short text>` lines; false
  fails. Do not treat absence of player activity as success. Start/observe
  distant conflict, dead-drop maintenance, optional CE spawns and cellar survey
  now (SearchBinding has its own player-driven counter, `SearchBinding/house_bound`, in
  the House search step below); AI activation may still require the subsequent client.
- [ ] Keep same-window server and client RPTs. Client counters stay local:
  `HCModuleReadiness.c#HCModuleReadiness.HCRegisterUse..HCUse` prints locally; no counter-forwarding RPC is present.
  Audit with `python3 -B -m tools.release.activity_check <server.RPT> --release
  --client-rpt <client.RPT>` (replace placeholders with private paths).
  `tools.release.activity_check.scan_release` merges counter maxima from both logs.
  Do not manufacture log lines. Activity alone does not check soak length, errors,
  textures or upgrade: the lead must run the entire scripted R3 gate unchanged.

## Verified controls used by this script

Paths in this table are repo-relative source references. Existing controls are
unverified in this run; their presence in code does not prove native operation.

| Control | Source evidence | What it actually permits |
| --- | --- | --- |
| Pause, HC authorization and request queue | `UAHollowCountryAdmin` in `mods/HollowCountry/inputs.xml`; `mods/HollowCountry/scripts/4_World/Admin/HCAdminModule.c#HCAdminModule.HCAuthorized`, `#HCAdminModule.HCDispatch`, `#HCAdminModule.HCReceive`; `mods/HollowCountry/scripts/5_Mission/Admin/HCAdminMenu.c#HCAdminMenu.OnShow` | Authenticated menu; one-command queue, throttle and replay checks. |
| Overview status/list/snapshot and Map | `mods/HollowCountry/scripts/4_World/Admin/HCAdminModule.c#HCAdminModule.HCStatus`, `#HCAdminModule.HCList`, `#HCAdminModule.HCReceive`; `mods/HollowCountry/scripts/5_Mission/Admin/HCAdminMenu.c` | Read state and snapshots; no bodies, supplies or use credit for a probe. |
| Infected sitter/horde | `mods/HollowCountry/scripts/4_World/Admin/HCAdminDirectors.c#HCInfectedModule.HCAdminSitter`, `#HCInfectedModule.HCAdminHorde`; dispatch `HCAdminModule.c#HCAdminModule.HCOperatorCommand` in same directory | One tracked sitter on clear ground 8 m ahead; horde adopts an existing eligible calm cohort, not an arbitrary spawn. |
| World scene, radio, deaddrop | `mods/HollowCountry/scripts/4_World/Admin/HCAdminDirectors.c#HCScenesModule.HCAdminNearestScene`, `#HCRadioChatter.HCAdminRadio`, `#HCDeadDrops.HCAdminDeadDrop` | Normal scene director; held-radio cooldown prime; nearest finite drop maintenance. Success reply alone is insufficient. |
| Economy forage, loot | `mods/HollowCountry/scripts/4_World/Admin/HCAdminDirectors.c#HCForageModule.HCAdminForage`, `#HCSearchRefreshModule.HCAdminDue` | Prime normal forest node work; age oldest real pending search timer. Neither grants inventory. |
| AI & Camps camp/holdout | `mods/HollowCountry/scripts/4_World/Admin/HCAdminDirectors.c#HCCampModule.HCAdminCamp`, `#HCHoldouts.HCAdminHoldout` | Existing row within 100 m; normal criteria/cooldowns. `camp` cannot create a hearth/camp. |
| Weather | `mods/HollowCountry/scripts/4_World/Weather/HCWeatherDaysModule.c#ChernarusPlusData.HCAdminBucket..HCAdminWeather`; dispatch `mods/HollowCountry/scripts/4_World/Admin/HCAdminModule.c#HCAdminModule.HCExtra` | Codes 0 clear override, 1 plain, 2 calm, 3 fog, 4 bad. Foreign weather controller refuses. |
| Group creation and status ping | `mods/HollowCountry/scripts/5_Mission/Groups/HCGroupMapMenu.c#HCGroupMapMenu.OnClick`; the `UAHollowCountryLookPing` and `UAHollowCountryPing*` inputs in `mods/HollowCountry/inputs.xml`; `mods/HollowCountry/scripts/4_World/Groups/HCTeamPing.c#HCGroupService.HCPingDeliver` | M roster, Create group; Numpad7 OK. Sender counts as a snapshot recipient, so solo exercise works; remote delivery remains untested. |
| Earplugs and grade | the `UAHollowCountryGrade` input in `mods/HollowCountry/inputs.xml`; `mods/HollowCountry/scripts/5_Mission/QoL/HCEarplugs.c#HCEarplugs.RequestRestore`, `#HCEarplugs.Apply` | Earplugs intentionally unbound: bind in Controls. Grade K cycles intensity. |
| Mount, flip, salvage actions | `mods/HollowCountry/scripts/4_World/Actions/HCTapedLightActions.c#HCActionMountTapedLight`; `HCActionFlipVehicle.c#HCActionFlipVehicle`, `HCActionSalvageWreck.c#HCActionSalvageWreck` in same directory | Exact contextual labels used below; ordinary server-owned custody/safety paths. |

## Stop 1 — Chernogorsk police and scavenger loop, 0–18 minutes

Start by ordinary travel at **(6564.47, 14.31, 2551.96)**, police-chernogorsk
waypoint 0 in `mission/hollow-country/ai/sites.json`. Nearby scavenger home is
**(6790.94, 9.52, 2580.32)**; source waypoint is **(6534.4, 14.77, 2454.83)**
in `mission/hollow-country/ai/picker-routes.json`. Coordinates are anchors,
not promises of a usable cellar, cabinet, wreck, road surface or AI spawn.

1. [ ] Join alive, close menus, show normal HUD, sprint and recover:
   **SurvivalAlignment/stamina_applied, stamina_hud_shown**. Open inventory
   (default Tab), M roster/map and authorized Pause window; run Overview status
   then snapshot: **ClientUI/inventory_open, map_open; Groups/menu_open;
   AdminMap/window_open, request**. Bind and cycle earplugs, restore preferred
   volume: **ClientUI/earplugs_applied**. With actual `ChernarusMap` in inventory,
   create a solo group or owner-rename it, then close menu and Numpad7:
   **Groups/group_mutated; TeamPing/ping_delivered**.
2. [ ] Hold `Mich2001Helmet`, carry loose `UniversalLight` and `DuctTape`, choose
   **Tape light to held item**. Repeat with held `TortillaBag` and the second
   loose light: **TapedLight/light_mounted; TapedHelmetMounts/light_mounted;
   TapedPackMounts/light_mounted**. Complete **Salvage netting from camo net**
   using `CamoNet` + `KitchenKnife`: **Crafting/recipe_completed**. Check real
   inventory changes. Shared mount service counts the helmet mount for TapedLight;
   a separate gun mount is optional additional coverage.
3. [ ] In daylight outdoors, allow grade startup (K if intensity zero) and run
   Time & Weather -> **weather 4**; await actual positive lighting blend:
   **Grade/grade_applied; Lighting/blend_applied**. Return override to **0** after
   observation. Positive blend requires actual sun/elevation and excludes native
   underground. Stay conscious; keep menus closed long enough for a saved unseen
   contextual hint: **Polish/hint_shown**. Three-minute hint limiter can overlap.
4. [ ] Pause -> Economy
   -> **loot**, wait next normal refresh tick: **LootRefresh/timer_rearmed**.
   At a supported roadside wreck, hold `Wrench` -> **Salvage wreck**, finish and
   inspect the created part: **WreckSalvage/part_created**. Decorative furniture,
   unsupported wrecks and empty/unbound searches can refuse; do not count refusal.
   In a House with a template search site, stand within 2.5 m of the site, run the
   native search action to its commit and take the found item:
   **Interiors/house_search_completed; SearchBinding/house_bound** (one commit counts for both).
   Empty, refused or interrupted searches do not count.
5. [ ] On clear flat ground use Infected -> **sitter**; let pose settle, then
   approach/noise/hit to produce a real wake: **InfectedVariety/actor_woken**.
   Land an ordinary close melee hit on an infected:
   **Melee/hit_processed, parity_probe**. Swing at an infected through a closed door or
   thin wall (default `Melee.WallVeto=true`: a `wall_veto ... mode=veto` line and the hit is refused; set `WallVeto=false` in `melee.json` for log-only, `mode=log` and the hit still lands), then through the open doorway (no wall_veto line): **Melee/wall_veto**. Fire a genuine unsuppressed round into
   safe ground: **InfectedMemory/heat_recorded**. Let an eligible chasing infected
   open an ordinary shut unlocked door while leaving escape and swing clear:
   **InfectedDoors/door_action**. Leave original infected corpse for client flies:
   **SignsOfLife/flies_created**. Alternatively drop actual rotten `Apple` on the
   ground; cargo food and human corpses are excluded by the client fly path.
6. [ ] With a real live HC AI away from infected, land one nonfatal ordinary hit
   and retreat: **AISelfDefence/hit_reaction**. Make this the final hostile action
   after calm AI observations. Observe eligible owned AI in the area during the
   same stop: **AIRoles/activity_started; v2-expansion-living-world/actor_admitted;
   optional-expansion-human-ai/actor_spawned**. These require their own real
   provider paths; actor_spawned counts a live site-patrol actor that passed its fairness
   check, so site presence or config readiness alone cannot stand in for a spawn.
7. [ ] Run World & Events -> **scene**, leave placement out of sight and await
   complete healthy placement: **Scenes/scene_placed**. Hold powered receiving
   `PersonalRadio` **in hands**, tune 87.8 MHz or actual authored faction channel,
   run **radio** and wait for real report in range: **Radio/report_delivered**.
   Read genuine HC-ledger `Paper` using native Read if one was delivered:
   **Notes/note_read; Leads/lead_received**. A plain paper, arbitrary death or
   non-lead radio line does not satisfy these paths.
8. [ ] Attempt qualified local conditions from the JSON at this same stop:
   **AIIncidents/response_started; AITactics/tactic_chosen;
   HordeMigration/route_advanced; InfectedReach/strike_landed, vault_started,
   vehicle_battered; MaterializerBridge/party_materialized;
   Materializer/actors_materialized; BodyStories/body_observed;
   Holdouts/camp_committed; Pickers/trip_started;
   optional-expansion-human-ai/convoy_astar, stuck_recovery; AITrade/trade_completed;
   Cellars/visual_applied**. These are conditional, not extra success claims.
   Use the appendix and JSON prerequisites; if unmet, record blocker and move on.
   No available HC command guarantees an owned transient situation, funded trade
   pair, cellar, convoy or tactic. Do not waste the whole route retrying blind.
9. [ ] Attempt recovery on the staged sideways car: seats empty, engine off,
   settled physics; hold `Crowbar`, remain outside expanded vehicle bounds,
   hold **Try to right vehicle (3 people or crowbar)**:
   **VehicleFlip/impulse_applied**. A righting outcome is separate from an impulse.
   Drive only ordinary serviceable transport for remaining stops.

## Stop 2 — Balota and finite drop, 18–25 minutes

Drive west along the coast. Zone `balota-cf3bbed7` center is
**(3900, 4.9, 2330)** in `mission/hollow-country/ai/zones.json` (default held).
The labels/radii of overlapping zones are authored data, not surveyed geography.
The finite drop `hc-drop-balota` is at **x=4086,z=3005**, terrain Y resolved by
engine (`mods/HollowCountry/scripts/4_World/World/HCDeadDrops.c#HCDeadDrops.OnStart`, `#HCDeadDrops.OnTick`).

- [ ] Approach listed held sites without watching their spawn points. Let normal
  guard work produce real guards: **ZoneGuards/guards_posted**. A held-state value
  alone does not count; budgets and actual owned sites govern admission.
- [ ] Pause -> Overview **list** or Map snapshot near the drop; run World & Events
  -> **deaddrop** within 1000 m. New placement requires observers **beyond 500 m**;
  withdraw normally and return only after maintenance binds:
  **DeadDrops/cache_bound**. The existing adapter help mentions nearby players
  for deposits, but this counter is cache binding, **not** a requested deposit.
  No crate refill or arbitrary supplied loot is permitted. Prefer a finite cache
  created during the player-free soak; preserve its identity/history.
- [ ] Observe an actual optional `Animal_Otter` CE instance if available:
  **OptionalPacks/animal_seen**. Server EEInit counts first actual
  instantiation, so player proximity is not required; a different animal or
  config existence is insufficient.

## Stop 3 — Bor woodland and Drozhino Hay Refuge, 25–40/45 minutes

Drive/walk north toward **the Bor woodland point (3100.955811, 249.415558, 4238.387207)**,
the retained driver forest waypoint (retired shelter alias).
This also supplies the `bor-farm` LOD seed X/Z in
`mods/HollowCountry/scripts/4_World/Infected/LOD/HCInfectedLODStore.c#HCInfectedLODConfig.HCSeedDefaults`.
Stop on actual woodland surface en route; the waypoint itself is not guaranteed
forest terrain. Keep any pitched tent/hearth away from the herd hazard area.

1. [ ] On `cp_conifer_`/`cp_broadleaf_` surface leave vehicle, run Economy ->
   **forage**, move >=30 m away from candidate slot in the same 200 m cell and
   allow the normal three-slot cycle. Find and Take that actual tracked item:
   **Forage/item_spawned, item_picked; Progression/familiarity_gained**.
   Wait through the forest sound startup/layer timer and a five-second playback
   sample: **Polish/sound_played**. No new mushroom or familiarity is inferred
   from a timer reset. Remain long enough for real node maintenance.
2. [ ] Approach Bor seed naturally with hidden candidates, within activation range;
   require actual leased bodies: **InfectedLOD/herd_materialized**. Keep threats
   away from camp before the respawn exercise. Use ordinary movement/combat;
   no invisible relocation or deletion to make the area safe.
3. [ ] Travel normally to **Drozhino Hay Refuge (2585.119873, 202.433472, 5360.409668)**,
   `mission/hollow-country/travel/route-surveys.json` existing_shelters,
   `mods/HollowCountry/scripts/4_World/Travel/HCShelterCatalog.c:179`
   (placed variant=0 in soak 206 and chain 207). Bor South Rest is retired; its replacement, Zabolotye Track Barn
   (1634.676147, 311.890808, 9857.233398; alternate
   1495.934204, 247.642349, 10660.052734), awaits runtime placement and cannot
   supply discovery evidence until it actually places. Walk into Drozhino's completed shelter discovery
   radius and open M with map/solo
   group, or use an actually received group lead: **MapPins/pins_published**.
   User-created markers do not hit this call site; unplaced shelter cannot qualify.
4. [ ] Return normally to the safe Bor open camp ground used by the camp/respawn
   smoke-plan rows; these build their own tent, crate and hearth and do not need
   the catalog shelter. There, combine stick + rag, place `Fireplace`,
   add fuel, ignite and stay nearby as a real group member until durable
   recognition: **Camps/camp_recognised**. Existing private camp history may
   prevent a second camp for the same group. Use its real hearth instead; do
   not erase state. Native tent/storage within 12 m must establish tier >=1.
5. [ ] Visit a prequalified residential hearth in Bor village by ordinary travel.
   House must be `Land_House_*` with real fireplace/chimney selections, and its
   native `FireplaceIndoor` must actually burn. Add fuel/kindling and ignite;
   observe outside within range. At hour >=18 or <7:
   **SignsOfLife/light_observed**. At native base temperature below ColdC
   (default 10 C): **SignsOfLife/smoke_observed**. Fuel and the real hearth must
   remain lit. If these time/temperature predicates are absent, this is an
   additional wait, not something `day` or `weather` guarantees. Ground camp
   fire cannot replace indoor house observations.
6. [ ] Leave original carried-item evidence and stash only normal inventory at
   camp; finish all dangerous/gear-dependent checks first. With safe real camp,
   pitched shelter/storage and intact allegiance, die normally and select native
   Respawn: **CampRespawn/respawn_reserved**. Cooldown is 1800 real seconds;
   do this once, last. Successful native fresh-character placement is intended
   gameplay, not teleporting a living character as a fix. Alive-avatar shortcuts,
   unsupported camp tiers and nearby hazards must refuse. Recheck HUD/UI after
   respawn as needed; do not extend claims beyond this single client.

## Conditional setups and smallest proposed hooks

Every JSON `not_deterministic` entry has an explicit physical/setup proposal.
The family A commands below are **implemented-unverified**; other hooks remain
unimplemented proposals. No command establishes runtime acceptance. Existing physical worlds, ordinary actions and
existing HC controls must be tried first. A selectable evaluator does not turn an
ineligible setup into a deterministic test; the lead must qualify it in-engine.

| Family | Proposed files and guard | Minimal permitted change |
| --- | --- | --- |
| A: select existing eligible work | `mods/HollowCountry/scripts/3_Game/Admin/HCAdminCatalog.c`, `mods/HollowCountry/scripts/4_World/Admin/HCAdminModule.c`, and relevant owning class named by each JSON source; dependency operations stay in `mods/HollowCountryExpansionAI/scripts/4_World/HCXExpansionBridge.c` | New explicitly default-off smoke-fixture preference; existing authenticated `HCAuthorized` / `HollowCountry.Admin` ingress, replay guard, throttle, one-command queue and shared HCWorkBudget. Select one **existing** eligible incident/group, world proposal, due holdout, opposition cell, fact/scene, picker lease, trade pair, or convoy; schedule its normal owner work. Return reason-coded refusal. No budget/cooldown/LOS/stock/journal bypass, fake facts or direct HCUse calls. |
| B: prioritize real measurement | `mods/HollowCountry/scripts/4_World/Interiors/HCCellarSampler.c` and admin catalog/ingress above if exposed | Default-off region/class-priority input, marker still required, existing bounded native ray/summary work retained. Report actual geometry. No synthetic measurement or visual qualification from sample count. |
| C: finite physical fixture | Admin catalog/ingress above, a proposed bounded fixture owner under `mods/HollowCountry/scripts/4_World/Admin/`, optional-pack native creation through appropriate owners | Default off, existing admin permission, one fixture receipt/cap and shared work admission. Ground/collision/observer-safe empty vehicle, real otter/bike, or a low physical test obstacle; no attached loot, CE duplication, player/AI position writes or inventory grants. Native EEInit, attack/vault/physics must still do the real work. It establishes only the exercised feature, not CE availability or natural frequency. |

Family A base fixtures are **implemented-unverified**. On a private lead test
profile only, set `EnableSmokeFixtures=true` before boot (default false; off on
friend servers). Authenticated Pause -> AI & Camps exposes `fx_holdout_due`,
`fx_conflict`, and `fx_materialize`; `kit` reports eligibility/refusal. Each uses
the existing replay/throttle/single-command core-tick queue. A command's `ok`
means selection only. Retain `[HC Admin] cmd=fx_... fixture=1`, the real owner
outcome with `fixture=1`, and its `[HC Use] ... fixture=<n>` receipt. Fixture
counts remain ACTIVE; there are no waivers. All native checks remain pending.

- `fx_holdout_due`: nearest existing allocated, unrefunded populated camp with
  positive supply, a naturally due upkeep/growth/alert-clear step, elapsed
  lockouts, available site and linked cache. Queues normal occupancy stages;
  cache, loot, caps and verified-save guards still decide the outcome.
- `fx_conflict`: nearest existing distant opposed pair/cell, with no pending
  territory receipt, claimed materializer lease, active provider fight or fact
  cooldown/daily-cap exclusion. Prioritizes normal `HCConflictStep`; durable
  quota admission is still required there. Selection may refuse its work budget.
- `fx_materialize`: nearest existing naturally offered unclaimed unexpired
  proposal with 1–2 actors and allowed custody. Prioritizes normal `Next`/claim;
  provider spawn guards remain authoritative. Observe its ordinary journey end
  and successful fold-back; never force Result, end, deletion or death.

Pending integration outside batch A: add-on fixture providers register through
`HCAdminModule.HCRegisterFixtureProvider` and report off-state kit refusals using
`HCAdminFixtures.HCEnabled()`. Add-on commands still need shared catalog entries.
`HCWorldProposal.Fixture` reaches the normal provider claim; Expansion-side
spawn/outcome logs and counters must consume that flag in their owning batch.
Batch A does not establish that every provider-side line is fixture-tagged.
Generated digest receipts also need lead regeneration after integration; they
are outside this worker's owned files. These are blockers, never waivers.

Detailed priority setups:

- **Reach / flip:** survey a real low platform with clear native landing; use
  player's normal climb and infected native targeting. Use an occupied stationary
  car for vehicle batter, then a **different**, empty settled sideways car plus
  crowbar for flip. Native ray must hit the real car component. No door obstruction.
  `HCInfectedReachNative.c#ZombieBase.HCReachHitLegs..HCReachHitVehicle` in `4_World/Infected/Reach/` and
  `HCVehicleFlip.c#HCVehicleFlipModule.HCCandidate..HCReady` and `#HCVehicleFlipModule.OnTick` in `4_World/Vehicles/` hold the decisive guards.
- **Horde / LOD:** use police-chernogorsk-loop actual nodes in
  `mission/hollow-country/infected/route-surveys.json`, starting
  (6564.47,14.31,2551.96), plus a genuine shot cue. A cohort must physically finish
  its segment; lagging members cannot be teleported or dropped from accounting.
  Bor herd materialization needs observer-safe hidden terrain; directly spawning
  an infected does not exercise the lease path.
- **Convoy / stuck:** `mission/hollow-country/travel/route-surveys.json` ->
  `gapcov_routes.routes[id=gapcov-road-chernogorsk]` names road nodes
  **19811,19813,19819,19816,19817,19823,19820,19822**, length 137.849 m, status
  **authored-candidate-native-pending**. It does not establish an active convoy.
  The current authorized snapshot gives only position/phase/reason
  (`mods/HollowCountryExpansionAI/scripts/4_World/Admin/HCXAdminWorldSources.c#HCAdminWorldSources.StepAI`),
  not its path. Observe the actual travelled segment in-world; a bounded
  authenticated route-node display would be an additional read-only proposal.
  Compare the actual segment to these nodes before placing an empty obstruction. Park on a traversed segment, keep doors/pedestrian
  escape and alternate road open, withdraw normally, wait three low-progress
  samples (default >=15 seconds), then require a real recovery rung and remove
  obstruction by driving it. AI may avoid it; qualification remains pending.
  `HCXAIStuckRecovery.c#HCXAIStuckRecovery.HCFixtureStuck..HCSummary` counts successful rungs, not elapsed waiting.
  A* must plan a **real journey**; standalone graph probing cannot satisfy it.
- **Trade / pickers:** Chernogorsk picker home/source are the exact anchors above;
  source/home containers, real item custody, under-supplied home and walking lease
  must all exist. Trade is AI-to-AI `BandageDressing` for `TunaCan`, minimum camp
  reserve 4, minimum members 2, offer interval 900 s, transfer range 2.5 m in
  `mission/hollow-country/ai/trade-recipes.json`. It requires actual movement and
  reciprocal transfers. `ai/caravans.json` still has placeholder FromCamp/ToCamp
  and empty SurveySha256; do not treat it as a prepared native corridor. If no
  real eligible pair/route exists, record the binding blocker, not success.
- **Owned death / materializer:** ordinary permanent patrol death is insufficient
  for BodyStories. `mods/HollowCountryExpansionAI/scripts/4_World/gapcode_body_scene.c#HCGapBodySceneProducer.HCObserve..HCPublish`
  requires a materialized transient party, active retained situation and the same
  real delayed world fact. Kill a real member in actual combat and retain original
  corpse/inventory. MaterializerBridge counts that known proposal's actual spawn;
  Materializer counts its **ended lease fold-back**, not creation. Waiting for a
  refusal/timeout without materialized bodies does not satisfy either outcome.
- **Notes / scenes / drops / conflict:** a normal scene must fully place; note
  must be genuine ledger `Paper` with exact text/id and unexpired fact. No note
  cloning or manual ledger write. Drops bind only finite real caches; pre-stage
  during observer-free soak. Distant faction outcome is the world data branch;
  actual local combat is a different path. Existing selection predicates still
  decide whether any of these are available in the window.
- **Cellars:** no repository-authored candidate supplies a qualified walkable
  below-terrain room for this test. Survey the listed classes, find real stairs,
  record coordinates, verify depth >2 m, inside-building true and native
  underground/NV requesters **inactive**. A vanilla underground area suppresses HC
  presentation. If there is no eligible room, a qualified physical cellar content
  change and its normal admission is required; a forced PPE start would be fake
  exercise. Whole-world sampler completion has no proven 30-minute bound.
- **Optional packs:** ordinary CE instantiation is preferred. A finite admin
  physical `Animal_Otter` fixture, if later implemented, must be labelled
  fixture evidence. Counter sees ancestry via real EEInit, never a config read.
  No generic COT/Expansion spawn menu is asserted or relied on by this script.

**Dominant time:** acquiring/staging finite items and vehicles, funded AI pair/
source inventory and native route bindings; real caravan/party completion and
900-second trade offer cadence; whole-world cellar scan; natural darkness and
cold predicates. These can exceed the smoke budget independently. Raising a
counter manually, changing its meaning, silent movement corrections, teleporting
players/AI, spawning duplicated loot or adding a release waiver is forbidden.

## Closeout checklist

- [ ] Lead retains exact-commit server and one-client logs and activity JSON.
  All registered default-on rows, including those already ACTIVE in build 156,
  must now report ACTIVE with count>0. No WAIVED, INERT, missing registration,
  failed self-test, ready=false, script error, VME or missing texture is accepted.
- [ ] Inspect real effects/items/UI as well as counters. `parity_probe` is a real
  hit diagnostic, `tactic_chosen` starts a scan, `impulse_applied` proves a pulse,
  and provider admission proves only its stated guard path. Do not claim more.
- [ ] Complete full release gate including 30-minute soak/perf and upgrade.
  Any new hook/code change invalidates previous exact-commit release evidence
  and needs lead serial compile, boot, soak and client rerun. No native experiment
  was performed by this documentation worker; all runtime checkboxes remain open.
- [ ] Keep issue/release status implemented-unverified until merged, gate PASS and
  actual `[HC Use] module=<Module> feature=<feature> count=<n>` closing evidence.
  Do not publish private raw RPTs or identifying roster/admin information.

## Per-counter reconciliation

Each row points into the companion JSON for the full predicate, steps, timing and
prerequisites. Check only after an observed positive counter in this candidate's
logs; every checkbox below is deliberately unchecked.

- [ ] `AIIncidents/response_started` — `admin_action` **implemented-unverified**, command `fx_incident`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXAIIncidentResponse.c#HCXAIIncidentResponse.HCStartLease`.
  Lead-only test profile: `EnableSmokeFixtures=true` (OFF by default). Create a real recorded incident near a real eligible HC patrol through normal gameplay. Run fx_incident from the lead admin position. The nearest recorded incident and nearest eligible group are queued for at most 60 seconds; the normal role scheduler must pass its busy checks and revalidate perception, range, cooldown, cap and claim before HCStartLease. Require the real response_started line with fixture=1. Selection alone earns nothing.
- [ ] `AIRoles/activity_started` — `server_soak`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXAIRoleActivities.c#HCXAIRoleActivities.OnTick`.
- [ ] `AISelfDefence/hit_reaction` — `client_action`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXDefence.c#HCXDefence.OnHit`.
- [ ] `AITactics/tactic_chosen` — `admin_action` **implemented-unverified**, command `fx_tactic`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXAITactics.c#HCXAITactics.ExecuteSmoke`.
  Lead-only test profile: `EnableSmokeFixtures=true` (OFF by default). Let an existing HC group perceive a real hostile threat or infected. Run fx_tactic; the nearest living owned member with real perception is prioritized for the next normal evaluation. Keep real stock, cooldown and policy guards. Require tactic_chosen with fixture=1 after a successful real throw or smoke drop; an inventory scan alone earns nothing.
- [ ] `AITrade/trade_completed` — `admin_action` **implemented-unverified**, command `fx_trade`; `mods/HollowCountry/scripts/4_World/World/HCAITrade.c#HCTradeTransaction.HCMoveStep`.
  Lead-only test profile: `EnableSmokeFixtures=true` (OFF by default). Run fx_trade near two real finite-reserve transient camps. With no retained plan, it ranks live qualified camp rows by distance and offers the nearest two through normal HCCandidate only if their relationship and supply qualify. It conservatively refuses if that pair fails; it does not enumerate all pairs. An existing retained plan keeps its one funded pair. Ready, cadence and receipt-cap guards remain in force; normal HCPlan resolves real stock, route, greeting and reciprocal custody. Require trade_completed with fixture=1; no stock or acknowledgements are injected.
- [ ] `AdminMap/request` — `admin_action`; `mods/HollowCountry/scripts/4_World/Admin/HCAdminModule.c#HCAdminModule.HCCommand`.
- [ ] `AdminMap/window_open` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Admin/HCAdminMenu.c#HCAdminMenu.OnShow`.
- [ ] `BodyStories/body_observed` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Leads/HCBodyStories.c#HCBodyStories.HCObserveBody`.
- [ ] `CampRespawn/respawn_reserved` — `client_action`; `mods/HollowCountry/scripts/4_World/Camps/HCCampRespawn.c#HCCampRespawnModule.HCChoose`.
- [ ] `Camps/camp_recognised` — `client_action`; `mods/HollowCountry/scripts/4_World/Camps/HCCampModule.c#HCCampModule.OnTick`.
- [ ] `CellarSampler/class_measured` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Interiors/HCCellarSampler.c#HCCellarSampler.HCSummaryTick`.
- [ ] `Cellars/visual_applied` — `not_deterministic`; `mods/HollowCountry/scripts/5_Mission/Atmosphere/HCCellarsClient.c#HCCellarsClient.HCSample`.
- [ ] `ClientUI/earplugs_applied` — `client_action`; `mods/HollowCountry/scripts/5_Mission/QoL/HCEarplugs.c#HCEarplugs.Apply`.
- [ ] `ClientUI/inventory_open` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Operations/HCUseLifecycle.c#InventoryMenu.OnShow`.
- [ ] `ClientUI/map_open` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Operations/HCUseLifecycle.c#MapMenu.OnShow`.
- [ ] `Crafting/recipe_completed` — `client_action`; `mods/HollowCountry/scripts/4_World/Crafting/HCCraftingModule.c#HCCraftingGate.RecordCraft`.
- [ ] `DeadDrops/cache_bound` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/World/HCDeadDrops.c#HCDeadDrops.OnTick`.
- [ ] `FactionConflict/journal_committed` — `admin_action`, **implemented-unverified**, `fx_conflict_journal`; durable death/finish and TerritoryApplied journal receipts only.
- [ ] `FactionConflict/outcome_recorded` — `admin_action`, **implemented-unverified**, `fx_conflict`; `mods/HollowCountry/scripts/4_World/World/HCFactionConflict.c#HCWorldModule.HCApplyQuotaOutcome`.
- [ ] `Forage/item_picked` — `client_action`; `mods/HollowCountry/scripts/4_World/Forage/HCForage.c#HCForageModule.HCReleaseNode`.
- [ ] `Forage/item_spawned` — `admin_action`; `mods/HollowCountry/scripts/4_World/Forage/HCForage.c#HCForageModule.HCResumeSpawn`.
- [ ] `Grade/grade_applied` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Atmosphere/HCGradeSettingsClient.c#HCGradeSettingsClient.Update`.
- [ ] `Groups/group_mutated` — `client_action`; `mods/HollowCountry/scripts/4_World/Groups/HCGroupService.c#HCGroupService.Commit`.
- [ ] `Groups/menu_open` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Groups/HCGroupMapMenu.c#HCGroupMapMenu.OnShow`.
- [ ] `Holdouts/camp_committed` — `admin_action`, **implemented-unverified**, `fx_holdout_due`; `mods/HollowCountry/scripts/4_World/World/HCHoldouts.c#HCHoldouts.PublishState`.
- [ ] `HordeMigration/route_advanced` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Infected/HCHordeMigration.c#HCNativeInfectedPack.V2Tick`.
- [ ] `InfectedDoors/door_action` — `client_action`; `mods/HollowCountry/scripts/4_World/Infected/Doors/HCInfectedDoors.c#HCInfectedDoorsModule.Apply`.
- [ ] `InfectedLOD/herd_materialized` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Infected/LOD/HCInfectedLOD.c#HCInfectedLODModule.HCLODMaterializeStep`.
- [ ] `InfectedMemory/heat_recorded` — `client_action`; `mods/HollowCountry/scripts/4_World/Infected/HCInfectedMemory.c#HCInfectedMemory.Add`.
- [ ] `InfectedReach/strike_landed` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Infected/Reach/HCInfectedReachModule.c#HCInfectedReachModule.CountStrike`.
- [ ] `InfectedReach/vault_started` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Infected/Reach/HCInfectedReachModule.c#HCInfectedReachModule.ClimbStarted`.
- [ ] `InfectedReach/vehicle_battered` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Infected/Reach/HCInfectedReachModule.c#HCInfectedReachModule.CountBatter`.
- [ ] `InfectedVariety/actor_woken` — `admin_action`; `mods/HollowCountry/scripts/4_World/Infected/Variety/HCInfectedVarietyModule.c#HCInfectedVarietyModule.HCRecordWake`.
- [ ] `Interiors/house_search_completed` — `client_action`; `mods/HollowCountry/scripts/4_World/Loot/HCSearchHouses.c#HCSearchHouses.HCCommitReservation`.
- [ ] `Leads/lead_received` — `client_action`; `mods/HollowCountry/scripts/4_World/Leads/HCLeadModule.c#HCLeadModule.ReceivePlayer`.
- [ ] `Lighting/blend_applied` — `admin_action`; `mods/HollowCountry/scripts/5_Mission/Atmosphere/HCLightingClient.c#HCLightingClient.Tick`.
- [ ] `LootRefresh/timer_rearmed` — `admin_action`; `mods/HollowCountry/scripts/4_World/Loot/HCSearchRefresh.c#HCSearchRefreshModule.OnTick`.
- [ ] `MapPins/pins_published` — `client_action`; `mods/HollowCountry/scripts/4_World/Groups/HCGroupPins.c#HCGroupPins.Collect`.
- [ ] `Materializer/actors_materialized` — `admin_action`, **implemented-unverified**, `fx_materialize`; `mods/HollowCountry/scripts/4_World/World/HCWorldMaterializer.c#HCWorldMaterializer.HCArchiveCustodyFile`.
- [ ] `MaterializerBridge/party_materialized` — `admin_action` **implemented-unverified**, command `fx_materialize`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXMaterializerBridge.c#HCXMaterializerBridge.SiteSpawned`.
  Lead-only test profile: `EnableSmokeFixtures=true` (OFF by default). Use fx_materialize on an existing short unclaimed proposal; fx_bridge is kit guidance only (use fx_materialize). Let normal admission and out-of-sight materialization run. The bridge retains proposal.Fixture through the real attributed SiteSpawned callback. Require party_materialized with fixture=1; selection or admission earns nothing.
- [ ] `Melee/hit_processed` — `client_action`; `mods/HollowCountry/scripts/4_World/Melee/HCMeleeModule.c#HCMeleeLog.Event`.
- [ ] `Melee/parity_probe` — `client_action`; `mods/HollowCountry/scripts/4_World/Core/Melee/HCMeleeTargetingParity.c#HCMeleeTargetingParity.Observe`.
- [ ] `Melee/wall_veto` — `client_action`; `mods/HollowCountry/scripts/4_World/Core/Melee/HCMeleeWall.c#HCMeleeWall.Vetoes`.
- [ ] `Notes/note_read` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Leads/HCNoteLedger.c#HCNoteLedger.Read`.
- [ ] `OptionalPacks/animal_seen` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Core/HCOptionalPackUse.c#AnimalBase.EEInit`.
- [ ] `Pickers/trip_started` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/World/HCPickers.c#HCModuleRegistry.RegisterModules`.
- [ ] `Polish/hint_shown` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Polish/HCHints.c#HCHints.HCAdvanceSave`.
- [ ] `Polish/sound_played` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Atmosphere/HCEnvSound.c#HCEnvSound.Update`.
- [ ] `Progression/familiarity_gained` — `client_action`; `mods/HollowCountry/scripts/4_World/Progression/HCProgression.c#HCProgressionModule.HCAwardForage`.
- [ ] `Radio/report_delivered` — `admin_action`; `mods/HollowCountry/scripts/4_World/Leads/HCRadioChatter.c#HCRadioChatter.OnTick`.
- [ ] `Scenes/scene_placed` — `admin_action`; `mods/HollowCountry/scripts/4_World/Scenes/HCScenesModule.c#HCScenesModule.Work`.
- [ ] `SearchBinding/house_bound` — `client_action`; `mods/HollowCountry/scripts/4_World/Loot/HCSearchBinding.c#HCSearchBinding.NoteHouseBound`.
- [ ] `SignsOfLife/flies_created` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Atmosphere/HCSignsOfLifeClient.c#HCSignsOfLifeClient.Reconcile`.
- [ ] `SignsOfLife/light_observed` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Atmosphere/HCSignsOfLifeClient.c#HCSignsOfLifeClient.Reconcile`.
- [ ] `SignsOfLife/smoke_observed` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Atmosphere/HCSignsOfLifeClient.c#HCSignsOfLifeClient.Reconcile`.
- [ ] `SurvivalAlignment/stamina_applied` — `client_action`; `mods/HollowCountry/scripts/4_World/Survival/HCStaminaIntegration.c#StaminaHandler.ProcessStaminaChanges`.
- [ ] `SurvivalAlignment/stamina_hud_shown` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Survival/HCStaminaHUD.c#HCStaminaHUD.Update`.
- [ ] `TapedHelmetMounts/light_mounted` — `client_action`; `mods/HollowCountry/scripts/4_World/Survival/HCTapedLightService.c#HCTapedLightService.Run`.
- [ ] `TapedLight/light_mounted` — `client_action`; `mods/HollowCountry/scripts/4_World/Survival/HCTapedLightService.c#HCTapedLightService.Run`.
- [ ] `TapedPackMounts/light_mounted` — `client_action`; `mods/HollowCountry/scripts/4_World/Survival/HCTapedLightService.c#HCTapedLightService.Run`.
- [ ] `TeamPing/ping_delivered` — `client_action`; `mods/HollowCountry/scripts/4_World/Groups/HCTeamPing.c#HCTeamPingModule.HCReceive`.
- [ ] `VehicleFlip/impulse_applied` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Vehicles/HCVehicleFlip.c#HCVehicleFlipModule.OnTick`.
- [ ] `WreckSalvage/part_created` — `client_action`; `mods/HollowCountry/scripts/4_World/Vehicles/HCWreckSalvage.c#HCWreckSalvageModule.Complete`.
- [ ] `ZoneGuards/guards_posted` — `server_soak`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXZoneGuards.c#HCXZoneGuards.ActorSpawned`.
- [ ] `optional-expansion-human-ai/actor_spawned` — `server_soak`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXAISitePatrols.c#HCXAISitePatrol.SetupAI`.
- [ ] `optional-expansion-human-ai/convoy_astar` — `admin_action` **implemented-unverified**, command `fx_convoy_stuck`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXAIStuckRecovery.c#HCXAIStuckRecovery.HCRouteUsed`.
  Lead-only test profile: `EnableSmokeFixtures=true` (OFF by default). Run fx_convoy_stuck near an existing walking journey or driving convoy whose own anchored motion check is already due. Observe normal sampling; only a real rung-3 recovery may request the normal planner/FIFO. The per-request fixture mark follows the journey FIFO into the planner. Require a real successful A* outcome and convoy_astar use line with fixture=1; a queued journey diagnostic must also carry fixture=1. Completion, refusal and queue removal clear attribution. Lead native compile and runtime fixture evidence remain pending. No sample or stuck outcome is forced.
- [ ] `optional-expansion-human-ai/stuck_recovery` — `admin_action` **implemented-unverified**, command `fx_convoy_stuck`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXAIStuckRecovery.c#HCXAIStuckRecovery.HCRecovered`.
  Lead-only test profile: `EnableSmokeFixtures=true` (OFF by default). Run fx_convoy_stuck near an existing walking journey or driving convoy whose own anchored motion check is already due. It marks only the nearest eligible observer, preserving all samples, timestamps and ladder state. Allow normal motion observation and recovery (journey rung 3 still uses the FIFO). Require a real recovery_step and stuck_recovery with fixture=1. Moving normally may produce no recovery; do not teleport or fabricate a stuck sample.
- [ ] `v2-expansion-living-world/actor_admitted` — `server_soak`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXStance.c#HCXLivingModule.OnTick`.
- [ ] `v2-expansion-living-world/caution_warn` — `server_soak`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXCautionObservation.c#HCXCautionObservation.Observe`.
  Neutral AI at about 50 m, raise a weapon: it faces you and shouts without firing; lower within 3 s (`AILimits.CautionGraceSeconds`) and no shots follow; keep it raised and it turns hostile after about 3 s. Require `count>=1` and the first-warn line with `grace_s=3 fire=none`.

Coverage is checked by `python3 -B -m tools.release.activity_check --check-plan` and by
`regenerate_all`. The plan includes registrations for disabled and upgrade-only owners.
Registration is not activity; every newly enumerated exercise remains unverified until observed.
TeamPing/ping_delivered is an OWNER-CHECK (owner decision 2026-11-23).
Melee/wall_veto increments before the blocking-mode return in HCMeleeWall.c:78, and
its campaign reach remains fixtures / fx_melee.

### HC-37 forced journal fixture

Owner 2026-11-26 authorizes `fx_conflict_journal`: a forced BOTH_REMAIN fixture
labelled `fixture=1`, separate from `fx_conflict`'s no-forced-outcomes selection
exercise above. Private lead-only profile, `EnableSmokeFixtures=true`, world
recovered, healthy FactionConflict outcome owner and idle journal required. Run
BEFORE `fx_conflict` (its quota slot may still be pending three seconds later).
Kit probes never spend callback capacity or change journal/cursors/once state.
Nearest FAR opposed unleased place without live transient is preferred in one
bounded pass, with raiders explicitly on the left. If no opposed cell qualifies,
the journal alone falls back to the FARTHEST pending/far/leased-qualified place
from the command position (catalog order breaks ties), paired with the first
world-data faction other than raiders with Relation(raiders, faction) == -1.
Fallback requires neither strength nor territory and does not depend on world age. There is no conflict budget
call, fact, quota, strength or territory change. One row per boot; at 96 rows
headroom refuses and the disposable testbed eventually needs a wipe, not pruning.
Always run this fixture in soaks: otherwise the registered journal_committed
feature may be INERT. This exercise verifies journal persistence only, not real
AI HCOffer, HCSurveyed, HCOwns, HCDisengaged or body death writes.

Expected RPT order (unrelated shared-save/status lines may interleave):

```text
[HC Plan] HC-37 fixture_journal_bound encounter=conflict:<n> place=<id> left=raiders right=<f> fixture=1
[HC Plan] HC-37 encounter=conflict:<n> observed=0 outcome=OBSERVING state=ready refusal=RECEIPT_PENDING runtime=PENDING
[HC Admin] cmd=fx_conflict_journal result=ok reason=fixture-journal-queued fixture=1
[HC Plan] HC-37 encounter=conflict:<n> observed=0 outcome=OBSERVING state=ready refusal=CARGO_TRANSFER_UNVERIFIED runtime=PENDING
[HC Plan] HC-37 encounter=conflict:<n> observed=1 outcome=OBSERVING state=ready refusal=none runtime=PENDING
[HC Plan] HC-37 encounter=conflict:<n> observed=3 outcome=BOTH_REMAIN state=ready refusal=OUTCOME_RECEIPT_PENDING runtime=PENDING
[HC Plan] HC-37 encounter=conflict:<n> observed=3 outcome=BOTH_REMAIN state=ready refusal=CARGO_TRANSFER_UNVERIFIED runtime=PENDING
[HC Use] module=FactionConflict feature=journal_committed count=1 fixture=1
[HC Plan] HC-37 fixture_journal_applied encounter=conflict:<n> requested=<r> durable=<d> fixture=1
```

The synchronous bind logs precede the admin reply (unlike the proposed brief
order). The use count is cumulative and may exceed 1 if real encounters completed
first; `fixture=1` is the first fixture count. `requested` is the captured applied
revision, `durable` the journal revision at the commit gate (`durable >= requested`).
Only `kit` prints `fx_conflict_journal available=1 reason=fixture-journal-available
fixture=1` in its reply (unavailable probes report their reason instead).
Refused command reply format: `[HC Admin] cmd=fx_conflict_journal result=refused
reason=<token> fixture=1`.

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

With EnableSharedSaves on, the scheduler prints the following only at a new peak,
after a completed image; it is not an unconditional per-image assertion:

```text
[HC Save] job=FactionConflictOutcomes stages=<s> max_stage_ticks=<m> total_ticks=<t> scheduler_ticks=<j> max_stages_per_tick=<p> stage_limit=<l> slowest_stage=<i> op=<op> runtime=PENDING
[HC Use] module=WorldSaves feature=stage_written count=<c>
```

The WorldSaves use receipt is the fallback shared-save activity evidence (it is
aggregate and cumulative; retain the fixture's durable applied line as the
journal-specific proof). Benign interleavings include
`refusal=TERRITORY_PUBLICATION_PENDING`, `awaiting_surveyed_opposed_pair` and
`provider_absent_base_only`. Stay farther than 1500 m from the selected place;
if a player approaches before publication the barrier waits until FAR again.

Must be absent: `outcome_receipt_waiting`, `outcome_receipts_not_durable_at_stop`,
`OUTCOME_STORE_UNCERTAIN`, `[HC Save] job=FactionConflictOutcomes state=failed`,
`perf_rule=R2 owner=FactionConflict`; next boot no
`RESTART_OUTCOME_STORE_UNCERTAIN`. Crash after durable bind must recover as
UNKNOWN_RESTART without fixture promotion/completion; stop while observing must
save UNKNOWN_STOP or name not-durable failure. Stop after durable finish before
completion must apply normally on restart with no fixture counter/applied line.
Native compile to Mission, soak, fault/crash/restart and one-client checks remain
pending; source/preland evidence alone accepts none of these experiments.

Failure handling below is source evidence; engine experiments remain pending.
`HFC` means `mods/HollowCountry/scripts/4_World/World/HCFactionConflict.c`;
`HTO` means `mods/HollowCountry/scripts/4_World/World/HCTerritoryOutcomes.c`.

| Case | Expected | Handled by |
| --- | --- | --- |
| EnableSmokeFixtures off | EnableSmokeFixtures-off; no row | HFC:305; HCAdminFixtures.c:27 |
| Module refused/unhealthy, config/job null | conflict-owner-unavailable; no row | HFC:308, HFC:316 |
| Outcome job faulted before health poll | conflict-owner-unavailable; no row | HFC:316 |
| Dirty journal/current encounter/bind/finish/quota pending | conflict-journal-busy; no row | HFC:319-320 |
| Second run this boot | fixture-journal-once; no row | HFC:321-322 |
| Rows >= MAX_ROWS - 32 (96) | journal-history-headroom; no row | HFC:323-324 |
| No opposed cell anywhere; a pending/far/leased-qualified place exists | fixture-journal-queued forced=1 with counts; raiders/hostile row, BOTH_REMAIN; territory/strength/quota/facts unchanged | HFC:1235, HFC:1278, HFC:1299 |
| Every place pending/near/leased | no-eligible-distant-opposed-cell places=N pending=a near=b leased=c not_opposed=0; no row | HFC:1265, HFC:1297 |
| Forced row, crash after bind durable | UNKNOWN_RESTART; never promoted/pending/applied; next boot selection unaffected | HFC:152, HFC:195; HTO:99 |
| Forced row finished durable, not applied, then stop | Next boot applies via HCConflictObserved; no publish, fixture line or counter | HFC:269, HFC:1466 |
| Forced place goes near before apply | TERRITORY_PUBLICATION_PENDING until FAR | HFC:272, HFC:1476 |
| fx_conflict after forced journal | HCFixtureJournalHolds excludes journal place; selection refusal includes counts and daily_cap | HFC:401, HFC:1205, HFC:1221 |
| Kit apply=false with fallback | Available; no state change or callback capacity spent | HFC:361, HFC:1299 |
| Invalid fixture pre-check | fixture-row-invalid; no insertion or module refusal | HFC:347-359; HTO:122 |
| Kit apply=false | No callback capacity spent; no journal/cursor/once change | HFC:360-361; HCAdminFixtures.c:76 |
| Callback exhausted | conflict-callback-budget; no row | HFC:362-363 |
| HCRequestSave=0 or mid-image job fault | OUTCOME_STORE_UNCERTAIN; never promoted, no counter; WorldSaves owner not faulted | HFC:365, HFC:451, HFC:676, HFC:803 |
| Real offer while fixture current | ENCOUNTER_OR_HISTORY_CAP; no second OBSERVING row (assuming earlier production offer guards pass) | HFC:747 |
| Player within 1500 m before apply | TERRITORY_PUBLICATION_PENDING until FAR; territory unchanged | HFC:270, HFC:1397, HFC:1403 |
| Stop during bind/finish | OBSERVING becomes UNKNOWN_STOP and saves (a stop between the death step and the resolve leaves one synthetic death in that UNKNOWN_STOP row; nothing consumes it); otherwise durable finish retained; failure names reason | HFC:547, HFC:562 |
| Crash after durable bind while OBSERVING | HCRecover UNKNOWN_RESTART; volatile fixture identity lost, no fixture promotion/finish | HFC:152, HFC:195; HTO:99 |
| Stop after durable finish before completion | Next boot applies durable BOTH_REMAIN normally, no fixture line/counter | HFC:547, HFC:588, HFC:268, HFC:949 |
| Zero bound actors on tick | Guarded return before modulo and HCReached.Mark | HFC:825 |

I1 production edits are confined to RegisterUses, OnStart, OnStop, OnTick,
HCFinishObserved, HCCompleteObserved and HCServiceWorld's territory/commit loop.
The extra territory-loop predicate defers only the fixture until its finish
completion, preserving counter-before-applied receipt order. I2 BOTH_REMAIN
reaches the existing world barrier without a publish call. I3 format and Version
are unchanged and the boot flag permits one inserted row. I4 no fixture state is
persisted; recovery is unchanged. I5 selection is one work-budgeted place/faction
pass; prospective validation copies at most 95 existing row references.

Review notes/deviations: selection makes no port calls. The existing claimed-lease
exclusion also excludes every live transient: HCXFactionCombatAdapter.HCActiveAt
requires HCLeaseAtPlace, which requires the proposal to be claimed
(HCXFactionCombatAdapter.c:69 and :140).
The supplied Opus design review was applied; no Opus diff review has been run in
this worker. The confined-run instruction supersedes local commit: edits only,
commit message supplied through `.banso-writer/commit-message`, no Git writes or
push. Native runtime checks are reserved for the lead.

Lead review fold-in (Opus code review of the fixture): fx_conflict skips the journal fixture's place until that row
is applied (HCFactionConflict.HCFixtureJournalHolds), and the driver stands 60 s after fx_conflict_journal, so the
two fixtures never share a place. The fixture id clears once fixture_journal_applied prints. Accepted deviation
from I1: the territory loop's `fixtureFinishPending` predicate (HFC:267-268) touches the production path for the
fixture id only.
