# Hollow Country

A server and client survival overhaul for DayZ Standalone 1.30.

[Features](#features) · [Required mod stack](#required-mod-stack) · [Install](#install) · [Server settings](#server-settings-reference) · [Admin tools](#admin-tools) · [Documentation](#documentation-and-contributing)

**DayZ PC · ChernarusPlus · All rights reserved**

Hollow Country adds finite scavenging, salvage, infected behaviour, shared navigation and a persistent world of survivors, incidents and environmental clues. The server owns world changes and inventory transfers. Players can explore, avoid trouble or follow a lead without accepting a quest.

## Features

Every feature is on by default. Each one can be switched off with the settings and opt-out markers listed with it. Installed loot and vehicle overlays use stopped-server receipt rollback. Gap: inventory sizing has no receipt rollback; removing it requires a rebuilt addon. [#203](https://github.com/d-addison/hollow-country/issues/203)

A setting of `false` disables its feature; switches shared by several features disable that whole area. Setting names below refer to the tables in [Server settings](#server-settings-reference). An opt-out such as `fuel_siphon.disable` means an empty file under `HollowCountry/acceptance/` in the server profile, absent by default. Remove it and restart to restore the preference. Missing routes or actors are described beside the affected feature.

Each feature has one small test mark. **Tested locally** means recorded working gameplay. **In-game test pending** means server startup exists but playing has not confirmed the behaviour. **Needs a two-player test** means sound, visibility, privacy or replication needs two clients. Descriptions name any missing part beside the affected feature.

### Searching and loot

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Finite searching** | Searching takes time and draws from finite supplies; searched places retain depletion history. | `EnableSearch=true`; `MaxBoundSearchSites=256`; `interior_search.disable`. | *In-game test pending* |
| **House and cabinet search** | House search names unavailable supply. Bound cabinets offer a six-second search after a server-confirmed site check, including refresh sites; decorative cabinets do not offer it. | `EnableSearch=true`; `interior_search.disable`. | *In-game test pending* |
| **Furnished interiors** | Compatible houses receive contextual furniture and clutter with bounded props. Gap: missing measured prop boxes and building placements leave unqualified interiors vanilla. [#199](https://github.com/d-addison/hollow-country/issues/199) | `EnableInteriors=true`; `MaxActiveInteriors=12`, `MaxPropsPerInterior=5`, `MaxFurnishedProps=1500`; `interior_placement.disable`. | *Needs a two-player test* |
| **Floor spots and scarcity** | The installed economy adds contextual floor spots across 149 building types and scales ordinary loot by 2 while keeping weapons and ammunition separately budgeted. Gap: the 1,222 extra floor points have no keep-or-quarantine disposition. [#179](https://github.com/d-addison/hollow-country/issues/179) | Loot-point `Multiplier=2.0`; `SearchDensityScale=0` keeps density scale 1; installed overlays require rollback. | *In-game test pending* |
| **Firearms and ammunition** | Native weapons, SNAFU Weapons and Tactical Flava use selected classes and family budgets, so recolours share scarcity. The authored native roster has 78 weapon classes in 53 families, 50 magazine classes and 47 ammunition sources; see the [firearms reference](docs/FIREARMS.md). | Package selections and family budgets are install-time controls; `--no-datamined` omits the datamined additions. | *In-game test pending* |
| **Useful equipment and storage** | Clothing, packs, tools, food and medical ingredients use contextual finite supply routes, including all 17 equipment floor-supply additions. Backpack rows scale by 1.5; eligible small items occupy less space. Native water contamination and medicine rules remain intact; see [equipment coverage](docs/EQUIPMENT_COVERAGE.md). | `inventory-sizes.json` controls package-time size rules; `--no-datamined` omits additional supply entries. | *In-game test pending* |
| **Revisit supplies** | World history schedules later searches against finite stock rather than refilling every restart. | `EnableWorld=true`, `EnableSearch=true`; `SearchDensityScale=0`. | *In-game test pending* |

### Crafting, recovery and lights

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Salvage and recovery** | Recover netting from camo nets, wire from reels or barbed bats, leather panels, and wood or nails from suitable bats and ruined crates. Fabric and teddy recovery use guarded recipes, tools and finite ingredients. | `EnableCrafting=true`. | *In-game test pending* |
| **Fuel siphoning** | Siphon real fuel from a stationary car with its engine off into a compatible bottle or jerry can. Transfers debit the tank and respect container capacity. | `fuel_siphon.disable` turns it off. | *In-game test pending* |
| **Taped weapon lights** | Tape a weapon light to a compatible native gun slot; removal returns the same light and battery without refunding tape. Cross-slot pairs cover TLRLight on 22 rail rifles and UniversalLight on seven pistols. | `taped_light.disable`; set `Disabled=true` on an individual pair receipt to opt out. | *Needs a two-player test* |
| **Taped pack lights** | Pack mount catalogues and per-pair preferences control a light carried on a backpack. Pack and helmet mounts and all 29 cross-slot weapon pairs are admitted without two-player confirmation. Gap: a host/light pair missing its native attachment slot is refused by name while other pairs remain available. [#58](https://github.com/d-addison/hollow-country/issues/58) | `EnableTapedPackMounts=true` (also when absent); pair receipt `Disabled=true` opts out; `taped_light.disable`. | *Needs a two-player test* |
| **Taped helmet lights** | Helmet mount pairs retain native attachment and beam requirements. | `taped_helmet.disable` opts out of helmet mounts; `taped_light.disable` disables taped lights. | *Needs a two-player test* |

### Infected

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Packs and perception** | Nearby infected adopt bounded pack routes and respond to perceived contact rather than a hidden live player position. | `EnableInfected=true`; `InfectedBindRadius=30`, `MaxBindQueriesPerTick=2`; `infected_pack_routes.disable`, `infected_ce_adoption.disable`, `infected_vision.disable`, `infected_contact_guard.disable`. | *Needs a two-player test* |
| **Local alerts** | Nearby infected relay an encounter through bounded local alert chains. | `EnableAlertChains=true`; `infected_supplementary_chains.disable`. | *Needs a two-player test* |
| **Investigation and memory** | Infected investigate observed clues and retain bounded encounter memory instead of tracking a player everywhere. | `EnableInfected=true`, `EnableWorld=true`; `infected_investigation.disable`. | *In-game test pending* |
| **Persistent hordes** | Horde membership and recovery account for living members across world state changes. | `EnableHordes=true`; `MaxActiveHordes=2`, `MaxActiveHordeMembers=24`; `infected_horde_routes.disable`, `infected_member_recovery.disable`. | *In-game test pending* |
| **Horde migration** | World history assigns movement along authored patrol waypoints. | `EnableWorld=true`; `EnableHordes=true`. | *In-game test pending* |
| **Doors and door pressure** | Door policies let eligible infected open or pressure doors without blocking player routes. | `EnableInfected=true`. | *Needs a two-player test* |
| **Reach and vulnerable positions** | Reach policies use attacks and steering against accessible low roofs, ladders and vehicles. There is no teleport correction. | `EnableInfected=true`. | *In-game test pending* |
| **Postures and visual variety** | Appearance substitutions and role policies use native stance, idle and crawler wake modes. Calm crawlers can rest in catalogued rooms or near tracked corpses; gunfire and native wake logic interrupt rest. Bounded crawler groups idle at authored wrecks, roadsides, churches, gas stations and buildings; fresh bodies appear out of sight under a cap that counts corpses. Gap: standing risers, surveyed migration routes and custom animation transitions remain missing. [#213](https://github.com/d-addison/hollow-country/issues/213) | `EnableInfectedVariety=true`; `infected_variety.disable`; `EnableGroupScaling=true` controls group-size scaling; LOD `VarietyNonCalmHoldSeconds=600`. | *Needs a two-player test* |
| **Sitters** | An original sitting-infected animation supplies the sitter pose. | `EnableInfectedVariety=true`; admin `sitter` uses normal admission. | *Needs a two-player test* |
| **Death reactions** | Death selection changes the native default to an impulse reaction while preserving corpse access. The engine exposes no infected ragdoll API. | `infected_deaths.disable` turns it off. | *Needs a two-player test* |
| **Distance-based infected work** | Infected LOD reduces distant work. Eight inland ChernarusPlus seeds support virtual herds that materialise near players under observer checks. Older settings migrate to schema 3 and add seeds to empty lists; non-empty custom lists and schema-2 opt-outs are preserved. | `EnableInfected=true`; profile `HollowCountry/Infected/lod.json`: `EnableLOD=true`, `EnableVirtualHerds=true`; distance and population defaults are listed below. | *Needs a two-player test* |

### Stamina, groups and navigation

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Stamina and weight** | Continuous movement uses one quarter of normal drain, recovery is 2.5 times normal and the weight penalty is halved. Separate stamina and weight bars show effort and burden; jumping and melee retain native costs. | Stamina `Settings.Enabled=true`, `ContinuousExertionScale=0.25`, `RecoveryScale=2.5`, `WeightPenaltyScale=0.5`. | *In-game test pending* |
| **Groups and shared map** | Invite teammates, manage membership and use world/map teammate icons. Press M, the rebindable DayZ map key, to pan, zoom and share editable markers and notes. | `EnableGroups=true`. | *Needs a two-player test* |
| **Team pings and death pins** | Group pings and death-pin permissions restrict information to eligible teammates. | `EnableTeamPing=true`; `EnableGroups=true`. | *Needs a two-player test* |
| **Discovery and received leads** | Shelter discoveries and received leads add appropriate group pins without exposing unreceived information. | `EnableTravel=true`, `EnableLeads=true`; `EnableGroups=true` for shared pins; group members share visited places when `ShareDiscovery=true` in `$profile:HollowCountry/Groups/settings.json` (default). | *Needs a two-player test* |
| **Familiarity** | Foraging familiarity improves with use, decays and resets on character death. Records are capped. | `EnableProgression=true`; `MaxFamiliarityRows=0` selects the built-in cap of 128. | *In-game test pending* |
| **Survival alignment** | Visual seasons leave native warmth and clothing rules intact; there is no added meal-heat bonus. Stamina remains owned by the stamina profile. | Legacy `EnableMealBuffs=true` is retained for compatibility and has no thermal effect. | *In-game test pending* |

### Travel, wrecks and vehicles

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Trail shelters** | Shared shelters offer places to stop and record discoveries. Gap: all five additional candidates stay excluded; stock roof anchors are checked, but native path samples and usable room/prop data are missing. [#200](https://github.com/d-addison/hollow-country/issues/200) | `EnableTravel=true`. | *In-game test pending* |
| **Wreck salvage** | Eligible wrecks hold finite parts rather than an unlimited salvage source. The server records claims and refuses unsupported wrecks. | `EnableTravel=true`. | *In-game test pending* |
| **Repairable transport** | The installed travel content includes common cars needing real parts, a few boats and many bicycles. RaG vehicle repairs and bicycle animations come from the published dependencies. | `EnableTravel=true` controls travel services; installed vehicle/bicycle overlays need rollback to remove. | *Needs a two-player test* |
| **Vehicle recovery** | The vehicle-flip action checks nearby helpers or a crowbar, then applies at most three bounded torque/lift impulses with safety checks and a cooldown. | `EnableVehicleFlip=true`. | *In-game test pending* |

### AI world

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **AI sites and patrols** | The Expansion AI addon supplies armed patrols and checkpoints at configured sites. Actor counts share the server AI limits; the provider has ordinary damage and finite ammunition. | Addon provider `Enabled=true`; `pve_patrols.disable`; `AILimits.MaxActiveSites=15`, `AILimits.MaxActiveAI=72`. | *In-game test pending* |
| **AI self-defence and gestures** | Survivors react to raised weapons, surrender and perceived greetings. A greeting needs fresh mutual sight and a greeting-specific acknowledgement. Neutral hits and kills feed bounded faction betrayal memory. Gap: attack, rescue-shot, near-miss and grudge-expiry responses need play checks. [#139](https://github.com/d-addison/hollow-country/issues/139) | `EnableEncounters=true`; `ai/sites.json`: `MaxSignalWorkPerSecond=8`, `MaxBetrayalRows=128`, `BetrayalRetentionSeconds=172800`; `ai_trade_emote_ack.disable` opts out of trade acknowledgement. | *Needs a two-player test* |
| **Scavengers and pickers** | One ledger party seeds per surveyed scavenger site. Existing Expansion groups walk outbound and return routes with real-item custody and restored patrols. Surveyed endpoint crates use finite authored stock and player-clear refill checks. An invalid cache section is refused by name (`[HC Pickers] caches refused reason=...`) and the module reports degraded. | `EnableEncounters=true`; `pve_patrols.disable`; source defaults `MaxConcurrentTrips=1`, `PartyCooldownSeconds=900`; `ai/picker-routes.json` controls routes, stock and cache limits below. | *In-game test pending* |
| **AI trade and caravans** | Friendly funded camps barter real carried surplus. Existing groups walk bounded installed-road routes, greet in mutual sight, exchange items and return. Confirmed cargo loss debits both camp allocations once; uncertain restart receipts are quarantined. | `EnableEncounters=true`; `ai_caravans.disable`, `ai_trade_emote_ack.disable`; `ai/trade-recipes.json` and `ai/caravans.json` tune pairing, stock and journeys below. | *In-game test pending* |
| **Faction conflict** | Opposed live parties fight under native combat observation. Distant conflicts update territory within a durable daily quota without inventing actor deaths or loot. Territory outcomes persist; existing infected can pressure camps. | `EnableEncounters=true`, `EnableWorld=true`; profile `faction-conflict.json`: `Enabled=true`, `FarMeters=1500`, `CooldownSeconds=604800`, `MaxDailyOutcomes=2`; further limits below. | *In-game test pending* |
| **Holdouts** | Killable, lootable survivor groups occupy places with real caches and a seven-day return lockout, including downtime. | `EnableEncounters=true`; `AILimits.HoldoutMin=3`, `AILimits.HoldoutMax=6`, `AILimits.MaxHoldouts=48`. | *In-game test pending* |
| **Camps and neighbours** | Fire, shelter and storage support recognition, three tiers, visitor eligibility and mailboxes. Warned probes can pressure mature camps from day 14. Visitor parties walk in through native doors to look over a mature camp (tier 3, day 14 or later, at most every three real days) and leave without taking anything. Gap: claim-only camps without a recognised hearth are never visited or raided. [#212](https://github.com/d-addison/hollow-country/issues/212) | `EnableCamps=true`; `camp_probes.disable`; `camp_visitors.disable`; `AILimits.CampMin=2`, `AILimits.CampMax=6`, `AILimits.MaxCamps=32`, `AILimits.MaxCampItems=64`. | *Needs a two-player test* |
| **Camp respawn and claims** | Eligible groups use camp respawn. One building claim per group restricts construction and setting native door locks to group members; native unlocking, lockpick wear and raids retain their rules. Member visits renew the claim. | `EnableCampRespawn=true`, `EnableCamps=true`, `EnableGroups=true`; `building_claims.disable`; `building-claims-config.json`: `ExpiryDays=30`, `VisitRadiusMeters=25`, `ActionReachMeters=2`. | *Needs a two-player test* |
| **Settlements and world materialisation** | Persistent settlement records select occasional occupation, parties or traces. Materialisation and its addon bridge bind world proposals to actors; settlement decay records changes over time. | `EnableWorld=true`, `EnableEncounters=true`; `AILimits.MaxOccupiedPlaces=15`, `AILimits.MaxMaterialized=15`, `AILimits.OccupationMin=3`, `AILimits.OccupationMax=8`. | *In-game test pending* |
| **Base containers** | Native tents, barrels, chests and crates count as storage wherever they are placed. Storage-only camps start at tier one and gain hearth recognition when a real burning fire arrives. Native inventory owns every item. | `EnableCamps=true`, `EnableGroups=true`; `base_containers.disable`; `AILimits.MaxCamps=32`, `AILimits.MaxCampItems=64`. | *In-game test pending* |
| **Unattended camp theft** | An outbound picker already in pickup range can carry one eligible real item from an unattended camp crate through its existing custody chain. Attendance and observer checks guard pickup and deposit; carrier loss retains physical cargo. A crate refused for this crate alone (attended, observed, home, empty) is skipped and the scan continues. An observed home defers the deposit for up to `PartyCooldownSeconds` (900 s), then the normal durable refusal leaves the item on its carrier. | `EnableCamps=true`, `EnableEncounters=true`; `camp_theft.disable`; `camp-theft-config.json` has `MaxAttemptsPerDay=1`, `MaxAttendancePlayers=32`, `AttendanceRangeMeters=500`, `ObserverRangeMeters=500`. | *Needs a two-player test* |
| **Base raids** | A raider party can hit an unattended claimed base after a warning, with its group online elsewhere. Raiders walk native routes, keep native door rules and carry one real item out through a journaled custody move; probe cooldowns and live attendance checks still apply. Gap: behavioral coverage of the adapter guards [#211](https://github.com/d-addison/hollow-country/issues/211). | `EnableCamps=true`, `EnableEncounters=true`; `base_raid.disable` (`camp_probes.disable` also turns it off); `base-raid-config.json` has `WarningSeconds=300`, `RaidSeconds=600`, `NoticeRangeMeters=40`, `AttendanceRangeMeters=500`. | *Needs a two-player test* |

### Events and situations

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Situation director** | Durable incidents let players observe, exploit or ignore nearby trouble. Leased parties walk to hostile funded camps; capped infected use eligible hidden points. Original routes and actual actor outcomes are retained. Pinned survivors hold at their shelter while threats are live; road caravan attacks use nearby road threat points. Gap: vehicle convoys and vehicle-pinned survivors [#210](https://github.com/d-addison/hollow-country/issues/210); crash-loot attribution [#147](https://github.com/d-addison/hollow-country/issues/147). | `EnableEncounters=true`; `events.disable`, `events_sites.disable`, `w38_situations.disable`, `w38_raids.disable`, `w38_transit.disable`; `W38Situations.*` controls below. | *In-game test pending* |
| **Scenes and police incidents** | Last stands, quarantine, evacuation and police scenes leave contextual props and clues. Stages expire without requiring a quest. | `EnableEncounters=true`; `events_sites.disable`. | *Needs a two-player test* |
| **Radio reports and Morse** | A powered PersonalRadio receives faction reports and Morse clues on the correct channel; received leads can be shared with the group. | `EnableLeads=true`. | *Needs a two-player test* |
| **Dead drops** | A finite dead-drop cache gives a place to investigate; another survivor may already have taken its contents. | `EnableEncounters=true`. | *Needs a two-player test* |
| **Body stories and notes** | Bodies and rare paper notes carry contextual leads. Notes are capped at one per scene and ten across the world. | `EnableLeads=true`. | *Needs a two-player test* |
| **Burn events and story chains** | Story kits and burn incidents lease existing physical stock. Native crash observations and direct cargo ancestry bind eligible spoils without creating, cloning or refilling them. Gap: crash-loot attribution remains incomplete. [#147](https://github.com/d-addison/hollow-country/issues/147) | `EnableEncounters=true`; `w38_incidents.disable`, `w38_rewards.disable`; `EnableStories=true`, `ArrivalSeconds=21600`, `Window=4`. | *In-game test pending* |
| **Persistent stories and escalation** | New stories arrive on a persistent six-hour schedule; completed stories do not replay. Capped escalation changes world pressure over time. | `EnableWorld=true`; `EnableStories=true`, `ArrivalSeconds=21600`, `Window=4`. | *In-game test pending* |
| **Event spoils** | Physical reward caches expose existing incident items. Empty receipts do not consume stock history; claimed supplies remain finite. | `EnableEncounters=true`; `w38_rewards.disable`, `w38_incidents.disable`; `W38Situations.MaxIncidents=64`, `W38Situations.MaxIncidentItems=16`. | *In-game test pending* |

### Ecology, wildlife and foraging

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Wildlife and habitats** | Native brains retain animal behaviour. The habitat overlay mixes sheep and mouflon in the existing sheep event and retains hare territory declarations. Bounded eligibility checks cover animals against infected and wolves against server AI. Gap: resource seeking/consumption, seasonal territory routes, blood trails and carcass attraction remain missing. [#149](https://github.com/d-addison/hollow-country/issues/149) | `EnableAmbientLife=true`; `ecology_migration.disable`, `wildlife_providers.disable`; provider `Enabled=true`, `TargetPairsEnabled=true`; habitat `Enabled=true` is an install-time preference, removed by rollback. | *In-game test pending* |
| **Carcasses** | Two authored red-deer sites use permanent economy allocations to create finite carcasses out of player sight. Spent sites do not refill after restart; native corpse handling supplies the body. | `EnableAmbientLife=true`; provider `CarcassesEnabled=true`, `MaxCarcasses=2`, `CarcassClass="Animal_CervusElaphus"`; `wildlife_providers.disable`; `EnableSignsOfLife=true` for flies. | *In-game test pending* |
| **Forage and herbs** | Forage nodes retain finite claims and refill delays. Seven supplements include four native mushroom classes; all use the same finite reservation and custody path throughout the visual year. Native food and herb semantics remain intact. | `EnableForage=true`; `EnableProgression=true` controls familiarity. | *In-game test pending* |

### Atmosphere

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Lighting and weather** | Lighting and weather-day profiles alter dusk, overcast and storms while keeping nights readable. The installer automatically generates delegated weather from pinned stock XML and retains backups. Staging on another drive moves next to the mission file; a residual cross-device move is refused with the target unchanged. | `EnableAtmosphere=true`, `EnableGrade=true`; `atmosphere.disable`; installer `--no-weather` omits weather delegation. | *In-game test pending* |
| **Colour grade** | A rebindable grade control cycles personal colour-grade intensity from 0 to 100% in 10% steps; zero restores the vanilla presentation. | `EnableGrade=true`; `ClientPresentationMask=15`, grade bit 2. | *In-game test pending* |
| **Visual seasons** | A running-server clock changes visual seasons, presentation and forecasts without new cold penalties. Native snowfall remains available. Gap: white winter ground has no supported live terrain/surface provider. [#150](https://github.com/d-addison/hollow-country/issues/150) | `EnableVisualSeasons=true`; `PhaseSeconds=604800`, `CheckpointSeconds=60`. | *Needs a two-player test* |
| **Cellars and darkness** | Cellar survey and presentation code identify interiors needing darker presentation; the operator-only sampler records geometry when the server profile contains `HollowCountry/measure-cellars`. Darker cellars are admitted without a measured room qualification yet. | `EnableAmbientLife=true`; `ClientPresentationMask=15` governs the available client layers; players can turn darker cellars off with the `HollowCountryDarkCellars` client preference; remove `HollowCountry/measure-cellars` to stop the sampler. | *Needs a two-player test* |
| **Signs of life** | Lit windows, chimney smoke and carcass flies provide environmental clues. | `EnableSignsOfLife=true`; `ClientPresentationMask=15`, signs bit 4. | *Needs a two-player test* |
| **Environmental hints and sound** | Local hints and environmental sound add presentation around world activity. | `EnableAmbientLife=true` controls server admission; `ClientPresentationMask=15`, hints bit 1 and ambient bit 8 control clients. | *Needs a two-player test* |

### Persistence, administration and performance

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **World persistence** | World, settlement, camp, lead and item-transfer journals retain history. Shared saves stage work; debug snapshot encoding and verified file promotion spread across eight ticks. Turning shared saves off refuses dependent owners at startup, including camps/claims and weather/seasons; owner barrier and shutdown saves remain. | `EnableWorld=true`; profile `performance.json`: `EnableSharedSaves=true` (registry `Performance.EnableSharedSaves`); set `false` and restart to disable shared saves. | *In-game test pending* |
| **Admin test kit** | Allowlisted admins use Pause for status and normal commands. `camptier` persists a tier from 0 to 3 until normal reclassification. `campvisit` and `campraid` request a physical visit or warned raid on a recognised camp through normal eligibility, attendance, cooldown and warning; `dormant` queues a fresh crawler group at the nearest variety place. Gaps: COT-role access ([#203](https://github.com/d-addison/hollow-country/issues/203)); claim-only camps cannot be targeted ([#212](https://github.com/d-addison/hollow-country/issues/212)). With `AdminControls.disable` the camp tier kit line names the opt-out. | `EnableAdminMap=true`; `AdminControls.disable` disables world controls; server admin allowlist controls access. | *In-game test pending* |
| **Debug snapshot and map** | Read-only snapshots feed a browser map and the admin Map tab with counts and world/AI layers. Group pins use a rolling anonymous sweep, rather than a simultaneous world sample. Verified staged replacement cannot provide native atomic rename. | `EnableDebugSnapshot=true`, `EnableAdminMap=true`. | *Needs a two-player test* |
| **Loot map** | The admin Map tab runs a bounded loot query, acknowledges it and retains the latest successful marks. | `EnableAdminMap=true`; see [debug map controls](docs/DEBUG_MAP.md). | *In-game test pending* |
| **Shared tick budget** | Twelve consumer IDs share one work allowance, including infected LOD, bases, conflict, trade and situations. Each consumer retains a first-work starvation allowance; retained cursors resume later. | `TickIntervalMs=1000`, `MaxTickWorkItems=32`; `Performance.SliceMs=4`, `Performance.EcologyRowsPerTick=4`, `Performance.InteriorStepsPerTick=1`, `Performance.HoldoutRowsPerTick=1`; area switches disable consumers. | *In-game test pending* |

## Required mod stack

Server and clients load these published Workshop items in this order. Third-party mods are used as published; never repack them. The two Hollow Country addons are loaded after their dependencies.

| Order | Workshop item | Install folder | Why it is loaded |
| :--- | :--- | :--- | :--- |
| 1 | [Community Framework](https://steamcommunity.com/sharedfiles/filedetails/?id=1559212036) | `@CF` | Shared framework for COT and Expansion. |
| 2 | [Community Online Tools](https://steamcommunity.com/sharedfiles/filedetails/?id=1564026768) | `@COT` | Operator administration and local test support. |
| 3 | [Dabs Framework](https://steamcommunity.com/sharedfiles/filedetails/?id=2545327648) | `@DabsFramework` | Expansion UI/framework dependency. |
| 4 | [Expansion Core](https://steamcommunity.com/sharedfiles/filedetails/?id=2291785308) | `@Expansion-Core` | Base services for Expansion addons. |
| 5 | [Expansion AI](https://steamcommunity.com/sharedfiles/filedetails/?id=2792982069) | `@Expansion-AI` | Human AI actors, navigation and AI animations. |
| 6 | [Expansion Navigation](https://steamcommunity.com/sharedfiles/filedetails/?id=2792984722) | `@Expansion-Navigation` | Map/GPS navigation support. |
| 7 | [SNAFU Weapons](https://steamcommunity.com/sharedfiles/filedetails/?id=2443122116) | `@SnafuWeapons` | Selected additional firearm classes. |
| 8 | [Tactical Flava](https://steamcommunity.com/sharedfiles/filedetails/?id=2646817942) | `@TacticalFlava` | Selected firearm and equipment classes. |
| 9 | [RaG_Core](https://steamcommunity.com/sharedfiles/filedetails/?id=3556131153) | `@RaG_Core` | Dependency for RaG vehicles. |
| 10 | [RaG Immersive Vehicles](https://steamcommunity.com/sharedfiles/filedetails/?id=3105330157) | `@RaG_Immersive_Vehicles` | Vehicle repair and interaction content. |
| 11 | [Ambient Animals Pack](https://steamcommunity.com/sharedfiles/filedetails/?id=3114410963) | `@AmbientAnimals` | Ambient animal content. |
| 12 | [Survivor Animations](https://steamcommunity.com/sharedfiles/filedetails/?id=2918418331) | `@SurvivorAnimations` | Animation dependency for bicycles. |
| 13 | [DayZ-Bicycle](https://steamcommunity.com/sharedfiles/filedetails/?id=2971190303) | `@DayZ-Bicycle` | Rideable bicycles. |
| 14 | [Hollow Country](https://steamcommunity.com/sharedfiles/filedetails/?id=3841628320) | `@HollowCountry` | Core overhaul and client presentation. |
| 15 | [Hollow Country Expansion AI](https://steamcommunity.com/sharedfiles/filedetails/?id=3841637854) | `@HollowCountryExpansionAI` | Connects the world systems to Expansion AI. |

Expansion-Animations is deliberately not loaded. A reported conflict with Survivor Animations, which DayZ-Bicycle requires, has not been reproduced locally; Expansion AI supplies its own AI animations.

## Install

Players:

1. Subscribe to [Hollow Country](https://steamcommunity.com/sharedfiles/filedetails/?id=3841628320), [Hollow Country Expansion AI](https://steamcommunity.com/sharedfiles/filedetails/?id=3841637854) and every dependency in the table above.
2. Let Steam finish downloading, then load the same items as the server in the listed order. Reconnect after updating both server and clients.
3. Join the server. M opens the map; the mod's additional bindings are rebindable in DayZ Controls.

Server owners:

1. Download the **latest test build friend server bundle** from [GitHub Releases](https://github.com/d-addison/hollow-country/releases). Install third-party Workshop items separately.
2. Stop the server and back up the mission, profile, persistent storage and existing addon/settings files. Use the bundle installer and its pinned package/dependency checks; retain the install receipt for rollback.
3. Install the mission/economy overlays, both Hollow Country addons and their public signing keys. Use the load order above on the server and clients; configure signature checking and review the settings below.
4. Start the server, inspect admission/refusal logs and join with a matching client. Keep runtime acceptance pending until the relevant feature is played; use two clients for the marked features.

Follow the [friend-server AI runbook](docs/FRIEND_SERVER_AI_RUNBOOK.md), [installation and rollback guide](docs/INSTALL_ROLLBACK.md) and [friend-server configuration](docs/FRIEND_SERVER.md) for exact commands, backups and recovery. Runtime flags do not remove installed mission content. The bundled `tools/package/overlay_remove.py --mission <mission> --overlays loot vehicles --server-stopped` rehearses receipt rollback before applying it; stop the server and retain recovery data. Inventory removal requires a rebuilt addon and is refused by this helper. [#203](https://github.com/d-addison/hollow-country/issues/203)

## Server settings reference

The shared operator input is [mission settings](mission/hollow-country/operator/settings.json), mirrored in [config defaults](config/hollow-country-settings.json) and validated against the [shared settings registry](tools/validate/shared_settings.json). The live server reads `HollowCountry/settings.json` under its profile. Preserve explicit operator choices and restart after changes. Defaults below are the checked-in values, not proof of in-game results. See the [operator guide](docs/README.md) for the separate module profiles and state files.

### Feature switches

All switches in this table default to `true`. Set a switch to `false` to turn off its named area. Diagnostics, client presentation and installed overlays have separate controls.

| Key | Default | Effect |
| :--- | :--- | :--- |
| `EnableInteriors` | `true` | Interior furnishing and placement. |
| `EnableSearch` | `true` | Search binding and finite search actions. |
| `EnableCrafting` | `true` | Additional recovery recipes. |
| `EnableInfected` | `true` | Infected processing, door pressure and reach. |
| `EnableHordes` | `true` | Horde work within the infected system. |
| `EnableAlertChains` | `true` | Supplementary local infected alerts. |
| `EnableGroups` | `true` | Group membership, shared map, markers and pins. |
| `EnableAtmosphere` | `true` | Native atmosphere/weather preference. |
| `EnableGrade` | `true` | Grade/lighting admission and weather-day profiles. |
| `EnableAmbientLife` | `true` | Ecology, optional pack diagnostics, cellar and polish admission; installed overlays remain. |
| `EnableSignsOfLife` | `true` | Signs-of-life server module. |
| `EnableTravel` | `true` | Shelters, wreck salvage and travel discoveries. |
| `EnableWorld` | `true` | World ledger, escalation, settlement decay, memory, horde migration and search refresh. |
| `EnableLeads` | `true` | Leads, radio/Morse, notes and body stories. |
| `EnableCamps` | `true` | Camp recognition, tiers, mailbox and visitor/probe eligibility. |
| `EnableEncounters` | `true` | World materialisation, AI trade/conflict, holdouts, pickers, scenes and dead drops. |
| `EnableInfectedVariety` | `true` | Infected variant/role policies. |
| `EnableDebugSnapshot` | `true` | Read-only debug snapshot collection/export. |
| `EnableAdminMap` | `true` | Authorised HC admin menu, Map tab and commands. |
| `EnableCampRespawn` | `true` | Camp respawn; also needs camps and groups. |
| `EnableTeamPing` | `true` | Group ping handling. |
| `EnableVehicleFlip` | `true` | Vehicle recovery with bounded torque/lift impulses and safety checks. |
| `EnableMealBuffs` | `true` | Legacy compatibility field; no meal heat hooks or thermal bonus. |
| `EnableForage` | `true` | Finite forage nodes and recovery. |
| `EnableProgression` | `true` | Per-character-life forage familiarity. |
| `EnableGroupScaling` | `true` | Infected group-size scaling; variety module can run for this alone. |
| `EnableTapedPackMounts` | `true` | Pack light admission; a missing key also enables mounts. Individual pairs can opt out. |

### Shared work, density and format

| Key | Default | Effect |
| :--- | :--- | :--- |
| `SchemaVersion` | `1` | Shared settings format; only 1 is accepted. |
| `ClientPresentationMask` | `15` | Client layers: hints=1, grade=2, signs=4, ambient=8. Add allowed bits; 0 disables all four. Range 0–15. |
| `TickIntervalMs` | `1000` | Core tick interval in milliseconds; 500–10000. |
| `MaxTickWorkItems` | `32` | Shared tick work allowance; 1–256. Starvation prevention can add up to eleven cost-one items. |
| `MaxActiveHordes` | `2` | Active horde cap; 1–8. |
| `MaxActiveHordeMembers` | `24` | Active member cap; 1–64. |
| `MaxActiveInteriors` | `12` | Concurrent active interior cap; 1–32. |
| `MaxPropsPerInterior` | `5` | Per-layout prop cap; 1–20. |
| `MaxFurnishedProps` | `1500` | Total furnishing cap; 0–2000. |
| `MaxBoundSearchSites` | `256` | Bound search-site cap; 1–1024. |
| `InfectedBindRadius` | `30` | Native infected binding query radius in metres; 5–60. |
| `MaxBindQueriesPerTick` | `2` | Infected binding query cap per tick; 1–8. |
| `MaxFamiliarityRows` | `0` | 0 selects the built-in 128-row familiarity cap; explicit positive cap up to 128. |
| `SearchDensityScale` | `0` | 0 selects scale 1; explicit range 0.5–2. Scales search-site/interior budgets within their limits; does not multiply firearm stock. |

### AI limits

`AILimits` is the shared object containing the following defaults. These caps are provisional; actor counts are not a measured server capacity. Min/max pairs set group sizes. Set `EnableEncounters=false` to disable the encounter area; provider patrols also have their own `Enabled` preference.

| Key | Default | Effect |
| :--- | :--- | :--- |
| `AILimits.MaxLiveGroups` | `15` | Concurrent live AI group cap. |
| `AILimits.MaxLiveAI` | `72` | Concurrent live AI actor cap. |
| `AILimits.OccupationMin` | `3` | Minimum occupation group size. |
| `AILimits.OccupationMax` | `8` | Maximum occupation group size. |
| `AILimits.HoldoutMin` | `3` | Minimum holdout group size. |
| `AILimits.HoldoutMax` | `6` | Maximum holdout group size. |
| `AILimits.PartyMin` | `2` | Minimum travelling party size. |
| `AILimits.PartyMax` | `6` | Maximum travelling party size. |
| `AILimits.PatrolMin` | `2` | Minimum patrol size. |
| `AILimits.PatrolMax` | `5` | Maximum patrol size. |
| `AILimits.CampMin` | `2` | Minimum AI camp group size. |
| `AILimits.CampMax` | `6` | Maximum AI camp group size. |
| `AILimits.MaxOccupiedPlaces` | `15` | Occupied-place record cap. |
| `AILimits.MaxParties` | `24` | Party record cap. |
| `AILimits.MaxMaterialized` | `15` | Materialised world record cap. |
| `AILimits.FactionStrengthMax` | `24` | Faction strength ceiling. |
| `AILimits.MaxActiveSites` | `15` | Active provider-site cap. |
| `AILimits.MaxActiveAI` | `72` | Active provider-actor cap. |
| `AILimits.MaxEncounters` | `15` | Encounter record cap. |
| `AILimits.MaxHoldouts` | `48` | Holdout record cap. |
| `AILimits.MaxCamps` | `32` | Camp record cap. |
| `AILimits.MaxCampItems` | `64` | Item cap per camp. |
| `AILimits.WorldSeed` | `18473` | Deterministic world-selection seed. |
| `AILimits.MaxObservedAI` | `1024` | Observed AI record cap. |

### Performance, situations and camp theft profiles

These registry prefixes identify separate owners, not nested objects in `HollowCountry/settings.json`. Under the server profile's `HollowCountry/`, `performance.json` uses unprefixed `Performance.*` fields, `w38-situations.json` uses unprefixed `W38Situations.*` fields, and generated `camp-theft-config.json` uses unprefixed `CampTheft.*` fields. For example, write `"EnableSharedSaves": false` in `performance.json`. Situation overrides must contain every policy field; omitted performance keys retain defaults. Restart after editing.

| Registry key | Default | Effect |
| :--- | :--- | :--- |
| `W38Situations.Version` | `1` | Configuration format. |
| `W38Situations.ScanRows` | `8` | Situation candidates examined per slice. |
| `W38Situations.MaxConcurrent` | `1` | Concurrent situation cap. |
| `W38Situations.MaxThreats` | `3` | Placed threat cap. |
| `W38Situations.MaxMembers` | `6` | Borrowed party member cap. |
| `W38Situations.MaxRouteNodes` | `32` | Situation route-node cap. |
| `W38Situations.MaxIncidents` | `64` | Physical incident history cap. |
| `W38Situations.MaxIncidentItems` | `16` | Existing items exposed per incident. |
| `W38Situations.PhysicalScanObjects` | `64` | Native object scan cap. |
| `W38Situations.PhysicalScanCargo` | `16` | Native cargo scan cap. |
| `W38Situations.MaxRaidMeters` | `600` | Maximum raid approach in metres. |
| `W38Situations.ShelterMeters` | `20` | Shelter proximity in metres. |
| `Performance.EnableSharedSaves` | `true` | Shared save scheduler preference; false refuses dependent owners before startup. |
| `Performance.SliceMs` | `4` | Cooperative per-slice time guard in milliseconds; native calls cannot be interrupted. |
| `Performance.SaveStageTargetMs` | `10` | Cooperative save-stage target in milliseconds; new peaks are logged. |
| `Performance.EcologyRowsPerTick` | `4` | Maximum ecology rows per tick. |
| `Performance.InteriorStepsPerTick` | `1` | Maximum interior steps per tick. |
| `Performance.HoldoutRowsPerTick` | `1` | Maximum holdout rows per tick. |
| `CampTheft.Version` | `1` | Configuration format. |
| `CampTheft.MaxAttemptsPerDay` | `1` | Global daily theft attempt cap; debit persists in picker receipts. |
| `CampTheft.MaxAttendancePlayers` | `32` | Owning-group attendance scan cap. |
| `CampTheft.AttendanceRangeMeters` | `500` | Attendance radius in metres. |
| `CampTheft.ObserverRangeMeters` | `500` | Observer radius in metres. |

Situation policy also retains `InfectedClass="ZmbM_CitizenASkinny_Brown"` and `RoadSurface="cp_asphalt1"`. The legacy `Enabled=false` in `events/raids.json` is a decoding field; the default-on runtime uses `w38_raids.disable` to opt out. `w38_situations.disable` disables the situation provider; `w38_transit.disable`, `w38_incidents.disable` and `w38_rewards.disable` disable their respective paths.

### Picker, trade and conflict controls

Mission inputs are under `mission/hollow-country/ai/`. `EnableEncounters=false` disables these services. `pve_patrols.disable` opts out of the Expansion site provider. `ai_caravans.disable` opts out of caravan movement; `ai_trade_emote_ack.disable` opts out of AI trade. These exchanges are between AI parties; players can watch or raid them.

| File / key | Default | Effect |
| :--- | :--- | :--- |
| picker-routes.json: `MaxLegMeters` | `400.0` | Maximum surveyed leg length in metres. |
| picker-routes.json: `ArrivalRangeMeters` | `2.5` | Observed arrival range in metres. |
| picker-routes.json: `MapExtentMeters` | `16000` | Survey coordinate bound. |
| picker-routes.json: `MaxRoutes` | `8` | Survey route cap. |
| picker-routes.json: `MaxWaypoints` | `8` | Survey waypoints per route. |
| picker-routes.json: `MaxScannedObjects` | `128` | Endpoint native object scan cap. |
| picker-routes.json: `MaxCargoScan` | `16` | Endpoint cargo inspection cap. |
| picker-routes.json: `CacheClass` | `"WoodenCrate"` | Native endpoint crate class. |
| picker-routes.json: `CacheCooldownSeconds` | `604800` | Player-clear refill delay in seconds. |
| picker-routes.json: `CacheMaxItems` | `16` | Items per source crate cap. |
| picker-routes.json: `CacheMaxLootRows` | `8` | Authored stock row cap. |
| trade-recipes.json: `TimeoutSeconds` | `300` | Exchange timeout in seconds. |
| trade-recipes.json: `TransferRangeMeters` | `2.5` | Native transfer range in metres. |
| trade-recipes.json: `GestureRequests` | `3` | Bound on greeting requests. |
| trade-recipes.json: `InventoryScanLimit` | `64` | Bound on native inventory inspection. |
| trade-recipes.json: `OfferIntervalSeconds` | `900` | Interval between offers in seconds. |
| trade-recipes.json: `MinimumCampReserve` | `4` | Minimum retained camp supply. |
| trade-recipes.json: `LossSupplyDebit` | `1` | Allocation loss per camp on confirmed journey loss. |
| trade-recipes.json: `MaxLossReceipts` | `128` | Retained loss receipt cap. |
| trade-recipes.json: `PairCandidatesPerTick` | `1` | Camp pair candidates per tick. |
| trade-recipes.json: `MinimumCampMembers` | `2` | Minimum eligible party members. |
| caravans.json: `ArrivalRangeMeters` | `2.5` | Observed arrival range in metres. |
| caravans.json: `CooldownSeconds` | `900` | Delay between journeys in seconds. |
| caravans.json: `MaxTripHistory` | `16` | Retained journey history cap. |
| caravans.json: `RoadDataPath` | `"DayZExpansion/AI/Scripts/Data/Roads/ChernarusPlus.roads"` | Installed Expansion road graph input. |
| caravans.json: `RoadMapWidth` | `14200` | Road graph map width. |
| caravans.json: `RoadMapHeight` | `15500` | Road graph map height. |
| caravans.json: `MaxRoadNodes` | `40000` | Road graph node cap. |
| caravans.json: `MaxRoadDegree` | `8` | Road junction degree cap. |
| caravans.json: `RoadWorkPerTick` | `256` | Road search work per tick. |
| caravans.json: `MaxRouteNodes` | `128` | Road route-node cap. |
| caravans.json: `MaxApproachMeters` | `100` | Maximum approach to road in metres. |
| caravans.json: `MaxJourneyMeters` | `250` | Maximum journey length in metres. |
| caravans.json: `ReturnTimeoutSeconds` | `600` | Return timeout in seconds. |
| caravans.json: `RoadNodesPerWorkUnit` | `8` | Road search nodes charged per shared work unit. |

Picker `CacheLoot` contains `TunaCan` ×2, `Rag` ×2, `WaterBottle` ×1 and `Mag_IJ70_8Rnd` ×1. Homes start empty; sources receive this capped stock. The five routes use `HomeIndex=0`, `SourceIndex=2`. Existing crates are adopted without replaying stock. Source defaults `MaxConcurrentTrips=1`, `PartyCooldownSeconds=900` and `TransferRangeMeters=2.5` are compiled defaults, not JSON operator keys; the single journal remains the structural trip limit.

Trade recipe `RecipeId="bandage-for-food"` exchanges `LeftClass="BandageDressing"` for `RightClass="TunaCan"`. Caravan identity fields retain `CorridorId="hc36-first-corridor"`, `FromCamp="funded-source"`, `ToCamp="friendly-destination"` and `SurveySha256=""`; the live provider uses bounded installed-road search, not that empty survey receipt as proof.

`HollowCountry/faction-conflict.json` under the server profile contains `Version=1`, `Enabled=true`, `FarMeters=1500`, `CooldownSeconds=604800`, `MaxDailyOutcomes=2`, `MaxPlayers=64`, `PressureMeters=120` and `ResolveEqualStrength=true`. Set `Enabled=false` to stop conflict production. Far outcomes affect territory only; nearby resolutions require observed combat or new casualties.

`HollowCountry/building-claims-config.json` contains `Version=1`, `ExpiryDays=30`, `VisitRadiusMeters=25` and native `ActionReachMeters=2`. Claim expiry counts running-server absence; member presence renews it. `building_claims.disable` disables claims; `base_containers.disable` disables native storage recognition; `camp_probes.disable` disables probes. These use the existing camps/groups owners and caps.

### Infected distance and herd profile

`HollowCountry/Infected/lod.json` under the server profile uses `SchemaVersion=3`. Set `EnableLOD=false` to stop distance classification or `EnableVirtualHerds=false` to stop virtual herds. Migration from settings schema 2 to 3 adds eight seeds to an empty list while preserving explicit false preferences and custom non-empty seeds. Partial or invalid profiles are refused without overwriting them.

| Key | Default | Effect |
| :--- | :--- | :--- |
| `FullRange` / `IdleRange` | `300` / `1000` | Full and idle distance bands in metres. |
| `MinSpawnDistance` / `MaterializeRange` / `FoldRange` | `120` / `900` / `1000` | Materialisation and folding distances in metres. |
| `VisibilityRange` | `1500` | Provisional observer margin in metres. |
| `ClassifyPerTick` | `12` | Classification row cap. |
| `MaxMaterialized` / `MaxPerHerd` / `MaxObservers` | `12` / `6` / `6` | Materialised member, per-herd member and observer caps. |
| `RegrowSeconds` | `1800` | Herd recovery interval in seconds. |
| `PosedBudget` / `PosedFullBudget` / `PosedIdleBudget` | `12` / `12` / `12` | Posed infected caps. |
| `VarietyNonCalmHoldSeconds` | `600` | Delay before reconsidering a non-calm crawler for rest. |
| `HerdWorld` | `"chernarusplus"` | World for default herd seeds. |
| `MemberTypes` | `[]` | Empty selects five native civilian infected classes. |
| `Herds` | Eight inland seeds | Bor, Sosnovka, Pulkovo, Dolina, Polana, Sinystok, Kamensk and northeast woods; each seed defaults to `Radius=60`, `HeadCount=12`. |

### Wildlife provider and habitat controls

Mission `ecology/HCWildlife-providers.json` contains the unprefixed fields below. `EnableAmbientLife=false`, provider `Enabled=false` or `wildlife_providers.disable` disables the provider. `CarcassesEnabled=false` and `TargetPairsEnabled=false` disable the respective paths independently.

| Registry key | Default | Effect |
| :--- | :--- | :--- |
| `WildlifeProviders.Version` | `1` | Configuration format. |
| `WildlifeProviders.TickMs` | `5000` | Provider interval in milliseconds. |
| `WildlifeProviders.WorkUnits` | `16` | Per-slice work allowance. |
| `WildlifeProviders.MaxCarcasses` | `2` | Permanent carcass allocation cap. |
| `WildlifeProviders.MaxPairs` | `8` | Retained target-pair cap. |
| `WildlifeProviders.MaxPairChecksPerTick` | `32` | Pair checks per provider tick. |
| `WildlifeProviders.PairLifetimeMs` | `10000` | Target-pair lifetime in milliseconds. |
| `WildlifeProviders.PairCooldownMs` | `30000` | Target-pair retry cooldown in milliseconds. |
| `WildlifeProviders.MaxPlayerChecks` | `16` | Observer cap; overflow refuses placement. |
| `WildlifeProviders.MinPlayerDistanceM` | `200.0` | Minimum player exclusion distance in metres. |
| `WildlifeProviders.Enabled` | `true` | Provider preference; false disables this provider. |
| `WildlifeProviders.CarcassesEnabled` | `true` | False disables authored carcasses. |
| `WildlifeProviders.TargetPairsEnabled` | `true` | False disables native target-pair eligibility filtering. |

`CarcassClass="Animal_CervusElaphus"`, `WorldName="chernarusplus"` and the two authored `Sites` bind carcass allocations. Back up `hc149-wildlife-allocations.json` with world storage; restart does not reset spent sites. Native animal brains and original population/timing/range fields remain in control. `ecology/habitat-overrides.json` uses `Enabled=true`; set it to `false` before generating/installing overlays to omit the habitat change. Existing installs need receipt rollback. Missing stock environment/events inputs refuse the install rather than producing a partial habitat overlay.

### Stamina profile

[Stamina package configuration](config/hollow-country-stamina.json) selects the custom profile. `Settings` is its nested runtime settings object; `Settings.Enabled=false` disables custom stamina. Rates affect continuous movement and recovery, not discrete jump/melee costs.

| Key | Default | Effect |
| :--- | :--- | :--- |
| `SchemaVersion` | `1` | Package format. |
| `Profile` | `"custom"` | Selects custom profile. |
| `Experimental` | `true` | Records the unqualified profile status. |
| `Settings.SchemaVersion` | `1` | Runtime stamina format. |
| `Settings.Enabled` | `true` | Enable custom stamina; false restores native handling. |
| `Settings.ContinuousExertionScale` | `0.25` | Continuous movement drain multiplier. |
| `Settings.RecoveryScale` | `2.5` | Recovery multiplier. |
| `Settings.WeightPenaltyScale` | `0.5` | Native weight-penalty multiplier; weight still limits endurance. |

### Visual seasons and stories

[Season defaults](config/hollow-country-seasons.json) control the running-server season clock, not the world calendar or survival temperature. [Story defaults](config/hollow-country-stories.json) control new-story arrivals.

| File / key | Default | Effect |
| :--- | :--- | :--- |
| seasons: `SchemaVersion` | `1` | Season format. |
| seasons: `EnableVisualSeasons` | `true` | False disables visual seasons and their presentation. |
| seasons: `PhaseSeconds` | `604800` | Seconds of running-server time per season: seven days. |
| seasons: `CheckpointSeconds` | `60` | Clock checkpoint interval in seconds. |
| seasons: `MaxUncheckpointedSeconds` | `120` | Maximum uncheckpointed clock time in seconds. |
| seasons: `MaxClockDeltaSeconds` | `10` | Maximum accepted clock step in seconds. |
| stories: `Version` | `1` | Story format. |
| stories: `EnableStories` | `true` | False disables story arrivals. |
| stories: `ArrivalSeconds` | `21600` | New-story interval in seconds: six hours. |
| stories: `Window` | `4` | Story arrival window size. |

### Light mount preferences

The [light-mount config](config/hollow-country-light-mounts.json) is a legacy offline mirror. Its cross-slot fields and the [backpack manifest](mission/hollow-country/lights/backpack-mounts.json) catalogue defaults do not turn off the admitted pairs. Runtime `EnableTapedPackMounts` defaults to `true`, including when the key is absent. Pack, helmet and the 29 cross-slot weapon pairs carry *Needs a two-player test*.

Set `"Disabled": true` on a pair in [pair receipts](mission/hollow-country/lights/pair-receipts.json) to opt out of that pair. An omitted `Disabled` means enabled. Create `$profile:HollowCountry/acceptance/taped_helmet.disable` to opt out of helmet mounts, or `taped_light.disable` under the same acceptance directory to disable taped lights. A missing native attachment slot refuses only the named pair; see [#58](https://github.com/d-addison/hollow-country/issues/58).

| File / key | Default | Effect |
| :--- | :--- | :--- |
| `Disabled` | `false` (absent) | Per-pair runtime opt-out in pair receipts. |
| `crossSlotLights` | `true` | Legacy offline mirror value; does not disable admitted weapon pairs. |
| `permittedPairIds` | `[]` | Legacy offline mirror list. |
| `DefaultCrossSlotLights` | `true` | Cross-slot weapon lights on by default in the pack-manifest catalogue. |
| `DefaultPermittedPairIds` | `[]` | Legacy pack-manifest catalogue list. |
| `MaxPermittedPairIds` | `2` | Manifest cap on exact compiled pack pair IDs. |
| `MaxReceiptBytes` | `32768` | Manifest read cap for per-pair receipts, in bytes. |
| `MaxReceiptBytesCeiling` | `65536` | Hard receipt size ceiling in bytes. |

### Installed loot and inventory rules

These are package-time inputs. Changing a file alone does not change an already installed mission or PBO. Regenerate/install the relevant content and use receipt-based rollback to remove it. Runtime feature flags do not restore vanilla inventory sizes or loot tables.

| File / key | Default | Effect |
| :--- | :--- | :--- |
| inventory: `schema_version` | `1` | Inventory generator format. |
| inventory: `backpack_row_multiplier` | `1.5` | Multiply eligible backpack cargo rows, rounded up; retain shell size. |
| inventory: `medical_max_area` | `2` | Maximum area eligible for medical-item shrinking. |
| inventory: `general_areas` | `[3, 4]` | Eligible general item areas before shrinking. |
| inventory: `small_tool_max_weight_grams_exclusive` | `500` | Tool weight must be below this many grams. |
| inventory: `square_tie` | `"shrink_width"` | Dimension shortened for square items. |
| inventory: `medical_addons` | `["DZ_Gear_Medical"]` | Native addon categories treated as medical. |
| inventory: `consumable_addons` | `["DZ_Gear_Consumables", "DZ_Gear_Food", "DZ_Gear_Drinks", "DZ_Gear_Cultivation"]` | Native addon categories treated as consumables. |
| inventory: `tool_addons` | `["DZ_Gear_Tools", "DZ_Gear_Navigation", "DZ_Gear_Optics", "DZ_Gear_Traps"]` | Native addon categories treated as tools. |
| inventory: `medical_include` | `["BandageDressing", "Rag", "SewingKit", "TetracyclineAntibiotics", "PainkillerTablets", "CharcoalTablets", "VitaminBottle", "PurificationTablets", "Epinephrine", "Morphine", "IodineTincture", "DisinfectantAlcohol"]` | Explicit medical eligibility classes. |
| inventory: `consumable_include` | `["Matchbox", "PetrolLighter", "Candle", "GasMask_Filter_Improvised"]` | Explicit consumable eligibility classes. |
| inventory: `exclude` | `{}` | Explicit per-class exclusions. |
| inventory: `exclude_ancestor_names` | `["Weapon_Base", "Rifle_Base", "Pistol_Base", "Archery_Base", "Launcher_Base", "ItemSuppressor", "ItemBarrel", "ItemStock", "ItemHandguard", "ItemBayonet", "ItemOptics_Base"]` | Weapon/attachment ancestry excluded from shrinking. |
| inventory: `exclude_addon_prefixes` | `["DZ_Weapons_Firearms", "DZ_Weapons_Pistols", "DZ_Weapons_Archery", "DZ_Weapons_Shotguns", "DZ_Weapons_Launchers", "DZ_Weapons_Nonlethal", "DZ_Weapons_Optics", "DZ_Weapons_Supports", "DZ_Weapons_Muzzles", "DZ_Weapons_Lights", "DZ_Weapons_Magazines", "DZ_Weapons_Underslung"]` | Weapon/attachment addon prefixes excluded from shrinking. |
| inventory: `exclude_inventory_slot_prefixes` | `["weapon", "pistol", "suppressor"]` | Exclude weapon, pistol and suppressor attachment slots from shrinking. |
| loot-points: `Multiplier` | `2.0` | Ordinary loot boost from [loot-point settings](mission/hollow-country/loot-points/settings.json); firearm budgets are separate. |

The inventory file’s `reviewed_overrides` is the per-class size result catalogue, rather than an additional tuning switch.

The [loot dispositions](config/loot-dispositions.json) catalogue contains per-class acquisition decisions, not operator switches. The [variant dependency inventory](config/hollow-country-variant-dependencies.json) and [winter terrain inventory](config/hollow-country-winter-terrain.json) are feasibility records, not runtime inputs; neither activates additional wildlife, infected variants or white terrain. [Firearm family budgets](docs/FIREARMS.md) and [equipment routes](docs/EQUIPMENT_COVERAGE.md) document the installed content in detail.

## Admin tools

The [admin test kit](docs/ADMIN_TEST_KIT.md) uses the HC admin allowlist independently of COT permissions. Enable `EnableAdminMap`, add authorised operators to the server's `admins.json`, restart and use the rebindable Pause key. Status, kit availability and nearby lists are read-only. World commands exercise normal module logic and return named refusal reasons; they do not bypass caps or grant loot.

`AdminControls.disable` under the acceptance directory disables world controls after restart. `camptier` accepts 0–3; normal camp scans can reclassify the result. `campvisit` and `campraid` ask the camp visitor and base-raid owners for a physical party (visitor policy: tier 3, day 14 or later, three real days since the last visit; `camp_visitors.disable` turns visits off); refusals name their reason and consume no cooldown. `dormant` delegates to the infected variety fresh-body queue. COT roles do not grant HC access. [#203](https://github.com/d-addison/hollow-country/issues/203)

The Map tab displays snapshot layers, routes and per-layer counts. The loot map runs a bounded query and retains the last successful marks. `EnableDebugSnapshot` controls export; `EnableAdminMap` controls authorised in-game access. The [debug map guide](docs/DEBUG_MAP.md) covers the local browser map, snapshot freshness, layer caps and query controls. Keep exported maps and profiles private. Configure COT separately using the [COT permissions guide](docs/COT_PERMISSIONS.md).

## Performance

The intended test load is **3–6 players**. Recorded boots do not establish a tested player capacity. Performance budgets remain provisional until measurements with that load; larger-server capacity is unproven.

`TickIntervalMs=1000` sets the core cadence. `MaxTickWorkItems=32` is shared across twelve consumers. For cost-one requests, starvation prevention permits up to 43 items in a tick; heavier requests and measured charges can exceed that unit total. This is a work allowance, not a millisecond frame-time guarantee. `[HC TickWork]` reports shared usage and starvation; `[HC CostTotal]` and `[HC Cost]` report aggregate and module costs. Building-class first resolves, event preflight, ecology and world saves still need target-load measurement in [#138](https://github.com/d-addison/hollow-country/issues/138).

| Consumer ID | Constant | Work |
| :--- | :--- | :--- |
| 0 | `HC_WORK_INFECTED` | Infected sampling. |
| 1 | `HC_WORK_INTERIORS` | Interior lock expiry. |
| 2 | `HC_WORK_SEARCH_BIND` | Search binding. |
| 3 | `HC_WORK_SEARCH_MAINT` | Search maintenance and coverage reporting. |
| 4 | `HC_WORK_SEARCH_REFRESH` | Revisit refresh. |
| 5 | `HC_WORK_SEARCH_DETACHED` | Detached search-slot recycling. |
| 6 | `HC_WORK_LOD_CLASSIFY` | Infected distance classification. |
| 7 | `HC_WORK_LOD_HERD` | Virtual herd work. |
| 8 | `HC_WORK_BASES` | Native base storage recognition. |
| 9 | `HC_WORK_CONFLICT` | Faction conflict. |
| 10 | `HC_WORK_TRADE` | Caravan pairing, cargo and road search. |
| 11 | `HC_WORK_SITUATIONS` | Situation scans, threat placement and physical spoils. |

`Performance.*` controls bound retained ecology/interior/holdout slices and shared save work. The save target is cooperative: native probes, file reads and owner barrier/shutdown flushes cannot be preempted.

## Documentation and contributing

- [Operator documentation](docs/README.md): configuration, persistence, backups and recovery.
- [Addon development](docs/MOD_DEVELOPMENT.md): source layout and package workflow.
- [Tools](tools/README.md): standard-library tooling, installers and validators.
- [Tests](tests/README.md): offline checks and the limits of their evidence.
- [Contributing](CONTRIBUTING.md): contribution requirements.

Report bugs through [GitHub issues](https://github.com/d-addison/hollow-country/issues), with the build, feature, expected/actual result and sanitised refusal/log lines. Do not attach credentials, identifiers, private profiles or third-party assets. Missing runtime behaviour remains open until tested on DayZDiag and a normal signed PBO/server; sound, visibility and replication need two clients.

## License and assets

Copyright © 2026 David Addison. **All rights reserved.** No open-source or public reuse license is granted. Third-party materials retain their owners' terms; see the [provenance inventory](docs/PROVENANCE_AND_LICENSES.md).

Game files, full vanilla dumps, purchased assets, Workshop packages, signing private keys, credentials and runtime profiles do not belong in this repository. Source stays private and is not licensed for reuse. Published third-party Workshop dependencies are never repacked.
