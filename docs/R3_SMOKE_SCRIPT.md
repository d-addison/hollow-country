# R3 one-client smoke route — planned, unverified

This is an exercise plan, not runtime evidence or a release pass. Owner decision
2026-11-21: **no waivers**. Every registered default-on `[HC Use]` counter must
be ACTIVE after the 30-minute soak plus one-client smoke on the exact release
commit. Build 156's supplied list has 67 INERT counters; the companion
[JSON plan](../tools/release/r3_smoke_plan.json) contains exactly those 67. Reconcile
against registration on the candidate commit: other counters and subsequent
workers' changes remain part of R3. One server plus at most one client is the
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
  `mission/hollow-country/INSTALL_AND_ROLLBACK.md:83-84` documents 4x day / 32x
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
  `HCModuleReadiness.c:53-67` prints locally; no counter-forwarding RPC is present.
  Audit with `python3 -B -m tools.release.activity_check <server.RPT> --release
  --client-rpt <client.RPT>` (replace placeholders with private paths).
  `tools/release/activity_check.py:52-112` merges counter maxima from both logs.
  Do not manufacture log lines. Activity alone does not check soak length, errors,
  textures or upgrade: the lead must run the entire scripted R3 gate unchanged.

## Verified controls used by this script

Paths in this table are repo-relative source references. Existing controls are
unverified in this run; their presence in code does not prove native operation.

| Control | Source evidence | What it actually permits |
| --- | --- | --- |
| Pause, HC authorization and request queue | `mods/HollowCountry/inputs.xml:38`; `mods/HollowCountry/scripts/4_World/Admin/HCAdminModule.c:249`, `:412`; `mods/HollowCountry/scripts/5_Mission/Admin/HCAdminMenu.c:484` | Authenticated menu; one-command queue, throttle and replay checks. |
| Overview status/list/snapshot and Map | `mods/HollowCountry/scripts/4_World/Admin/HCAdminModule.c:481`, `:509`, `:591`; `mods/HollowCountry/scripts/5_Mission/Admin/HCAdminMenu.c` | Read state and snapshots; no bodies, supplies or use credit for a probe. |
| Infected sitter/horde | `mods/HollowCountry/scripts/4_World/Admin/HCAdminDirectors.c:93`, `:154`; dispatch `HCAdminModule.c:613-623` in same directory | One tracked sitter on clear ground 8 m ahead; horde adopts an existing eligible calm cohort, not an arbitrary spawn. |
| World scene, radio, deaddrop | `mods/HollowCountry/scripts/4_World/Admin/HCAdminDirectors.c:266`, `:566`, `:617` | Normal scene director; held-radio cooldown prime; nearest finite drop maintenance. Success reply alone is insufficient. |
| Economy forage, loot | `mods/HollowCountry/scripts/4_World/Admin/HCAdminDirectors.c:745`, `:661` | Prime normal forest node work; age oldest real pending search timer. Neither grants inventory. |
| AI & Camps camp/holdout | `mods/HollowCountry/scripts/4_World/Admin/HCAdminDirectors.c:403`, `:441` | Existing row within 100 m; normal criteria/cooldowns. `camp` cannot create a hearth/camp. |
| Weather | `mods/HollowCountry/scripts/4_World/Weather/HCWeatherDaysModule.c:198-218`; dispatch `mods/HollowCountry/scripts/4_World/Admin/HCAdminModule.c:563` | Codes 0 clear override, 1 plain, 2 calm, 3 fog, 4 bad. Foreign weather controller refuses. |
| Group creation and status ping | `mods/HollowCountry/scripts/5_Mission/Groups/HCGroupMapMenu.c:351`; `mods/HollowCountry/inputs.xml:24-34`; `mods/HollowCountry/scripts/4_World/Groups/HCTeamPing.c:303-318` | M roster, Create group; Numpad7 OK. Sender counts as a snapshot recipient, so solo exercise works; remote delivery remains untested. |
| Earplugs and grade | `mods/HollowCountry/inputs.xml:16-26`; `mods/HollowCountry/scripts/5_Mission/QoL/HCEarplugs.c:60-68` | Earplugs intentionally unbound: bind in Controls. Grade K cycles intensity. |
| Mount, flip, salvage actions | `mods/HollowCountry/scripts/4_World/Actions/HCTapedLightActions.c:9`; `HCActionFlipVehicle.c:27`, `HCActionSalvageWreck.c:38` in same directory | Exact contextual labels used below; ordinary server-owned custody/safety paths. |

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
   **Melee/hit_processed, parity_probe**. Fire a genuine unsuppressed round into
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
engine (`mods/HollowCountry/scripts/4_World/World/HCDeadDrops.c:158`, `:232`).

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
- [ ] Observe actual optional `Old_Bike` / `Animal_Otter` CE instances if available:
  **OptionalPacks/bicycle_seen, animal_seen**. Server EEInit counts first actual
  instantiation, so player proximity is not required; a vanilla bicycle substitute,
  different animal or config existence is insufficient.

## Stop 3 — Bor woodland and South Rest, 25–40/45 minutes

Drive/walk north toward **Bor South Rest (3100.955811, 249.415558, 4238.387207)**,
`mission/hollow-country/travel/route-surveys.json` existing shelter entry.
This also supplies the `bor-farm` LOD seed X/Z in
`mods/HollowCountry/scripts/4_World/Infected/LOD/HCInfectedLODStore.c:108`.
Stop on actual woodland surface en route; the shelter itself is not guaranteed
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
3. [ ] Walk into the completed shelter discovery radius and open M with map/solo
   group, or use an actually received group lead: **MapPins/pins_published**.
   User-created markers do not hit this call site; unplaced shelter cannot qualify.
4. [ ] At safe nearby open camp ground, combine stick + rag, place `Fireplace`,
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
  `HCInfectedReachNative.c:302-354` in `4_World/Infected/Reach/` and
  `HCVehicleFlip.c:114-154,200-215` in `4_World/Vehicles/` hold the decisive guards.
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
  (`mods/HollowCountryExpansionAI/scripts/4_World/Admin/HCXAdminWorldSources.c:13-21`),
  not its path. Observe the actual travelled segment in-world; a bounded
  authenticated route-node display would be an additional read-only proposal.
  Compare the actual segment to these nodes before placing an empty obstruction. Park on a traversed segment, keep doors/pedestrian
  escape and alternate road open, withdraw normally, wait three low-progress
  samples (default >=15 seconds), then require a real recovery rung and remove
  obstruction by driving it. AI may avoid it; qualification remains pending.
  `HCXAIStuckRecovery.c:88-112` counts successful rungs, not elapsed waiting.
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
  for BodyStories. `mods/HollowCountryExpansionAI/scripts/4_World/gapcode_body_scene.c:34-90`
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
  physical `Animal_Otter`/`Old_Bike` fixture, if later implemented, must be labelled
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

- [ ] `AIIncidents/response_started` — `admin_action` **implemented-unverified**, command `fx_incident`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXAIIncidentResponse.c:598`.
  Lead-only test profile: `EnableSmokeFixtures=true` (OFF by default). Create a real recorded incident near a real eligible HC patrol through normal gameplay. Run fx_incident from the lead admin position. The nearest recorded incident and nearest eligible group are queued for at most 60 seconds; the normal role scheduler must pass its busy checks and revalidate perception, range, cooldown, cap and claim before HCStartLease. Require the real response_started line with fixture=1. Selection alone earns nothing.
- [ ] `AIRoles/activity_started` — `server_soak`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXAIRoleActivities.c:680`.
- [ ] `AISelfDefence/hit_reaction` — `client_action`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXDefence.c:310`.
- [ ] `AITactics/tactic_chosen` — `admin_action` **implemented-unverified**, command `fx_tactic`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXAITactics.c:677`.
  Lead-only test profile: `EnableSmokeFixtures=true` (OFF by default). Let an existing HC group perceive a real hostile threat or infected. Run fx_tactic; the nearest living owned member with real perception is prioritized for the next normal evaluation. Keep real stock, cooldown and policy guards. Require tactic_chosen with fixture=1 after a successful real throw or smoke drop; an inventory scan alone earns nothing.
- [ ] `AITrade/trade_completed` — `admin_action` **implemented-unverified**, command `fx_trade`; `mods/HollowCountry/scripts/4_World/World/HCAITrade.c:535`.
  Lead-only test profile: `EnableSmokeFixtures=true` (OFF by default). Run fx_trade near two real finite-reserve transient camps. With no retained plan, it ranks live qualified camp rows by distance and offers the nearest two through normal HCCandidate only if their relationship and supply qualify. It conservatively refuses if that pair fails; it does not enumerate all pairs. An existing retained plan keeps its one funded pair. Ready, cadence and receipt-cap guards remain in force; normal HCPlan resolves real stock, route, greeting and reciprocal custody. Require trade_completed with fixture=1; no stock or acknowledgements are injected.
- [ ] `AdminMap/request` — `admin_action`; `mods/HollowCountry/scripts/4_World/Admin/HCAdminModule.c:648`.
- [ ] `AdminMap/window_open` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Admin/HCAdminMenu.c:484`.
- [ ] `BodyStories/body_observed` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Leads/HCBodyStories.c:245`.
- [ ] `CampRespawn/respawn_reserved` — `client_action`; `mods/HollowCountry/scripts/4_World/Camps/HCCampRespawn.c:152`.
- [ ] `Camps/camp_recognised` — `client_action`; `mods/HollowCountry/scripts/4_World/Camps/HCCampModule.c:686`.
- [ ] `CellarSampler/class_measured` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Interiors/HCCellarSampler.c:434`.
- [ ] `Cellars/visual_applied` — `not_deterministic`; `mods/HollowCountry/scripts/5_Mission/Atmosphere/HCCellarsClient.c:89`.
- [ ] `ClientUI/earplugs_applied` — `client_action`; `mods/HollowCountry/scripts/5_Mission/QoL/HCEarplugs.c:68`.
- [ ] `ClientUI/inventory_open` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Operations/HCUseLifecycle.c:26`.
- [ ] `ClientUI/map_open` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Operations/HCUseLifecycle.c:35`.
- [ ] `Crafting/recipe_completed` — `client_action`; `mods/HollowCountry/scripts/4_World/Crafting/HCCraftingModule.c:30`.
- [ ] `DeadDrops/cache_bound` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/World/HCDeadDrops.c:245`.
- [ ] `FactionConflict/outcome_recorded` — `admin_action`, **implemented-unverified**, `fx_conflict`; `mods/HollowCountry/scripts/4_World/World/HCFactionConflict.c:795`.
- [ ] `Forage/item_picked` — `client_action`; `mods/HollowCountry/scripts/4_World/Forage/HCForage.c:460`.
- [ ] `Forage/item_spawned` — `admin_action`; `mods/HollowCountry/scripts/4_World/Forage/HCForage.c:721`.
- [ ] `Grade/grade_applied` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Atmosphere/HCGradeSettingsClient.c:123`.
- [ ] `Groups/group_mutated` — `client_action`; `mods/HollowCountry/scripts/4_World/Groups/HCGroupService.c:587`.
- [ ] `Groups/menu_open` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Groups/HCGroupMapMenu.c:477`.
- [ ] `Holdouts/camp_committed` — `admin_action`, **implemented-unverified**, `fx_holdout_due`; `mods/HollowCountry/scripts/4_World/World/HCHoldouts.c:558`.
- [ ] `HordeMigration/route_advanced` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Infected/HCHordeMigration.c:642`.
- [ ] `InfectedDoors/door_action` — `client_action`; `mods/HollowCountry/scripts/4_World/Infected/Doors/HCInfectedDoors.c:570`.
- [ ] `InfectedLOD/herd_materialized` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Infected/LOD/HCInfectedLOD.c:885`.
- [ ] `InfectedMemory/heat_recorded` — `client_action`; `mods/HollowCountry/scripts/4_World/Infected/HCInfectedMemory.c:287`.
- [ ] `InfectedReach/strike_landed` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Infected/Reach/HCInfectedReachModule.c:801`.
- [ ] `InfectedReach/vault_started` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Infected/Reach/HCInfectedReachModule.c:663`.
- [ ] `InfectedReach/vehicle_battered` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Infected/Reach/HCInfectedReachModule.c:812`.
- [ ] `InfectedVariety/actor_woken` — `admin_action`; `mods/HollowCountry/scripts/4_World/Infected/Variety/HCInfectedVarietyModule.c:121`.
- [ ] `Interiors/house_search_completed` — `client_action`; `mods/HollowCountry/scripts/4_World/Loot/HCSearchHouses.c#HCSearchHouses.HCCommitReservation`.
- [ ] `Leads/lead_received` — `client_action`; `mods/HollowCountry/scripts/4_World/Leads/HCLeadModule.c:433`.
- [ ] `Lighting/blend_applied` — `admin_action`; `mods/HollowCountry/scripts/5_Mission/Atmosphere/HCLightingClient.c:176`.
- [ ] `LootRefresh/timer_rearmed` — `admin_action`; `mods/HollowCountry/scripts/4_World/Loot/HCSearchRefresh.c#HCSearchRefreshModule.OnTick`.
- [ ] `MapPins/pins_published` — `client_action`; `mods/HollowCountry/scripts/4_World/Groups/HCGroupPins.c:123`.
- [ ] `Materializer/actors_materialized` — `admin_action`, **implemented-unverified**, `fx_materialize`; `mods/HollowCountry/scripts/4_World/World/HCWorldMaterializer.c:520`.
- [ ] `MaterializerBridge/party_materialized` — `admin_action` **implemented-unverified**, command `fx_materialize`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXMaterializerBridge.c:99`.
  Lead-only test profile: `EnableSmokeFixtures=true` (OFF by default). Use fx_materialize on an existing short unclaimed proposal; fx_bridge is kit guidance only (use fx_materialize). Let normal admission and out-of-sight materialization run. The bridge retains proposal.Fixture through the real attributed SiteSpawned callback. Require party_materialized with fixture=1; selection or admission earns nothing.
- [ ] `Melee/hit_processed` — `client_action`; `mods/HollowCountry/scripts/4_World/Melee/HCMeleeModule.c:93`.
- [ ] `Melee/parity_probe` — `client_action`; `mods/HollowCountry/scripts/4_World/Core/Melee/HCMeleeTargetingParity.c:117`.
- [ ] `Notes/note_read` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Leads/HCNoteLedger.c:333`.
- [ ] `OptionalPacks/animal_seen` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Core/HCOptionalPackUse.c:22`.
- [ ] `OptionalPacks/bicycle_seen` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Core/HCOptionalPackUse.c:37`.
- [ ] `Pickers/trip_started` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/World/HCPickers.c:1076`.
- [ ] `Polish/hint_shown` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Polish/HCHints.c:259`.
- [ ] `Polish/sound_played` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Atmosphere/HCEnvSound.c:106`.
- [ ] `Progression/familiarity_gained` — `client_action`; `mods/HollowCountry/scripts/4_World/Progression/HCProgression.c:484`.
- [ ] `Radio/report_delivered` — `admin_action`; `mods/HollowCountry/scripts/4_World/Leads/HCRadioChatter.c:503`.
- [ ] `Scenes/scene_placed` — `admin_action`; `mods/HollowCountry/scripts/4_World/Scenes/HCScenesModule.c:590`.
- [ ] `SearchBinding/house_bound` — `client_action`; `mods/HollowCountry/scripts/4_World/Loot/HCSearchBinding.c#HCSearchBinding.NoteHouseBound`.
- [ ] `SignsOfLife/flies_created` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Atmosphere/HCSignsOfLifeClient.c:260`.
- [ ] `SignsOfLife/light_observed` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Atmosphere/HCSignsOfLifeClient.c:258`.
- [ ] `SignsOfLife/smoke_observed` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Atmosphere/HCSignsOfLifeClient.c:259`.
- [ ] `SurvivalAlignment/stamina_applied` — `client_action`; `mods/HollowCountry/scripts/4_World/Survival/HCStaminaIntegration.c:73`.
- [ ] `SurvivalAlignment/stamina_hud_shown` — `client_action`; `mods/HollowCountry/scripts/5_Mission/Survival/HCStaminaHUD.c:244`.
- [ ] `TapedHelmetMounts/light_mounted` — `client_action`; `mods/HollowCountry/scripts/4_World/Survival/HCTapedLightService.c:418`.
- [ ] `TapedLight/light_mounted` — `client_action`; `mods/HollowCountry/scripts/4_World/Survival/HCTapedLightService.c:417`.
- [ ] `TapedPackMounts/light_mounted` — `client_action`; `mods/HollowCountry/scripts/4_World/Survival/HCTapedLightService.c:419`.
- [ ] `TeamPing/ping_delivered` — `client_action`; `mods/HollowCountry/scripts/4_World/Groups/HCTeamPing.c:141`.
- [ ] `VehicleFlip/impulse_applied` — `not_deterministic`; `mods/HollowCountry/scripts/4_World/Vehicles/HCVehicleFlip.c:215`.
- [ ] `WreckSalvage/part_created` — `client_action`; `mods/HollowCountry/scripts/4_World/Vehicles/HCWreckSalvage.c:681`.
- [ ] `ZoneGuards/guards_posted` — `server_soak`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXZoneGuards.c:220`.
- [ ] `optional-expansion-human-ai/actor_spawned` — `server_soak`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXAISitePatrols.c:204`.
- [ ] `optional-expansion-human-ai/convoy_astar` — `admin_action` **implemented-unverified**, command `fx_convoy_stuck`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXAIStuckRecovery.c:103`.
  Lead-only test profile: `EnableSmokeFixtures=true` (OFF by default). Run fx_convoy_stuck near an existing walking journey or driving convoy whose own anchored motion check is already due. Observe normal sampling; only a real rung-3 recovery may request the normal planner/FIFO. The per-request fixture mark follows the journey FIFO into the planner. Require a real successful A* outcome and convoy_astar use line with fixture=1; a queued journey diagnostic must also carry fixture=1. Completion, refusal and queue removal clear attribution. Lead native compile and runtime fixture evidence remain pending. No sample or stuck outcome is forced.
- [ ] `optional-expansion-human-ai/stuck_recovery` — `admin_action` **implemented-unverified**, command `fx_convoy_stuck`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXAIStuckRecovery.c:178`.
  Lead-only test profile: `EnableSmokeFixtures=true` (OFF by default). Run fx_convoy_stuck near an existing walking journey or driving convoy whose own anchored motion check is already due. It marks only the nearest eligible observer, preserving all samples, timestamps and ladder state. Allow normal motion observation and recovery (journey rung 3 still uses the FIFO). Require a real recovery_step and stuck_recovery with fixture=1. Moving normally may produce no recovery; do not teleport or fabricate a stuck sample.
- [ ] `v2-expansion-living-world/actor_admitted` — `server_soak`; `mods/HollowCountryExpansionAI/scripts/4_World/HCXStance.c:184`.
