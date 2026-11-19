# Hollow Country

A server and client survival overhaul for DayZ Standalone 1.30.

[Features](#features) · [Required mod stack](#required-mod-stack) · [Install](#install) · [Server settings](#server-settings-reference) · [Admin tools](#admin-tools) · [Documentation](#documentation-and-contributing)

**DayZ PC · ChernarusPlus · All rights reserved**

Hollow Country adds finite scavenging, salvage, infected behaviour, shared navigation and a persistent world of survivors, incidents and environmental clues. The server owns world changes and inventory transfers. Players can explore, avoid trouble or follow a lead without accepting a quest.

## Features

All features are on by default by the owner's configuration policy. Operators can disable features through the settings or opt-out markers below. The checked-in pack-light and cross-slot defaults still differ from that policy; setting tables retain their actual values. Gap: some features still lack an independent operator switch, and installed economy/content overlays need an installer rollback rather than a runtime flag. [#NEW-off-switches]

A setting of `false` disables its feature; switches shared by several features disable that whole area. Setting names below refer to the tables in [Server settings](#server-settings-reference). An opt-out such as `fuel_siphon.disable` means an empty file under `HollowCountry/acceptance/` in the server profile, absent by default. Remove it and restart to restore the preference. An enabled preference does not supply missing routes, actors or client checks.

Each feature has one small test mark. **Tested locally** means recorded working gameplay. **In-game test pending** means server startup exists but playing has not confirmed the behaviour. **Needs a two-player test** means sound, visibility, privacy or replication needs two clients. The repository records no accepted gameplay feature yet; offline tests establish no DayZ behaviour. Descriptions cover the implemented feature and name any missing part beside it.

### Searching and loot

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Finite searching** | Searching takes time and draws from finite supplies; searched places retain depletion history. Gap: the composed native search action still lacks the shared economy allocator and durable inventory/ledger commit. [#NEW-finite-search] | `EnableSearch=true`; `MaxBoundSearchSites=256`; `interior_search.disable`. | *In-game test pending* |
| **House and cabinet search** | House search reports a refusal rather than silently granting loot when supply is unavailable. Gap: the pilot cabinet prompt has no server-known site list. [#152](https://github.com/d-addison/hollow-country/issues/152) | `EnableSearch=true`; `interior_search.disable`. | *In-game test pending* |
| **Furnished interiors** | Compatible houses receive contextual furniture and clutter with bounded props. Gap: most building placements lack measured clearance, and rendered fit and pathfinding remain unchecked. [#NEW-interior-coverage] | `EnableInteriors=true`; `MaxActiveInteriors=12`, `MaxPropsPerInterior=5`, `MaxFurnishedProps=1500`; `interior_placement.disable`. | *Needs a two-player test* |
| **Floor spots and scarcity** | The installed economy adds contextual floor spots across 149 building types and scales ordinary loot by 2 while keeping weapons and ammunition separately budgeted. Gap: 1,222 extra floor points still await a keep/quarantine decision and in-world inspection. [#179](https://github.com/d-addison/hollow-country/issues/179) | Loot-point `Multiplier=2.0`; `SearchDensityScale=0` keeps density scale 1; installed overlays require rollback. | *In-game test pending* |
| **Firearms and ammunition** | Native weapons, SNAFU Weapons and Tactical Flava use selected classes and family budgets, so recolours share scarcity. The authored native roster has 78 weapon classes in 53 families, 50 magazine classes and 47 ammunition sources; see the [firearms reference](docs/FIREARMS.md). Gap: ordinary acquisition, firing, ammunition and nine stock-absent variant entries remain unconfirmed; the optics subset is incomplete. [#NEW-firearm-acquisition] | Package selections and family budgets are install-time controls; `--no-datamined` omits the datamined additions. | *In-game test pending* |
| **Useful equipment and storage** | Clothing, packs, tools, food and medical ingredients gain contextual supply routes. Backpack rows scale by 1.5; eligible small items occupy less space. Native water contamination and medicine rules remain intact; see [equipment coverage](docs/EQUIPMENT_COVERAGE.md). Gap: refused leather/crafted routes and actual vessel contents still need confirmation. [#NEW-equipment-routes] | `inventory-sizes.json` controls package-time size rules; `--no-datamined` omits additional supply entries. | *In-game test pending* |
| **Revisit supplies** | World history schedules later searches against finite stock rather than refilling every restart. Gap: native restart and allocation reconciliation are unconfirmed. [#NEW-finite-search] | `EnableWorld=true`, `EnableSearch=true`; `SearchDensityScale=0`. | *In-game test pending* |

### Crafting, recovery and lights

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Salvage and recovery** | Recover netting from camo nets, wire from reels or barbed bats, leather panels, and wood or nails from suitable bats and ruined crates. Fabric and teddy recovery use guarded recipes, tools and finite ingredients. Gap: the remaining item/action routes do not yet have a complete effective audit. [#NEW-recovery-routes] | `EnableCrafting=true`. | *In-game test pending* |
| **Fuel siphoning** | Siphon real fuel from a stationary car with its engine off into a compatible bottle or jerry can. Transfers debit the tank and respect container capacity. Gap: an ordinary completed fuel transfer and interrupted/restart recovery have not been observed. [#NEW-fuel-transfer] | `fuel_siphon.disable` turns it off. | *In-game test pending* |
| **Taped weapon lights** | Tape a weapon light to a compatible native gun slot; removal returns the same light and battery without refunding tape. Cross-slot pairs cover TLRLight on 22 rail rifles and UniversalLight on seven pistols. Gap: native and cross-slot pairs lack two-client beam, attachment and recovery confirmation. [#58](https://github.com/d-addison/hollow-country/issues/58) | `taped_light.disable`; cross-slot mirror `crossSlotLights=false`, `permittedPairIds=[]`. | *Needs a two-player test* |
| **Taped pack lights** | Pack mount catalogues and per-pair receipts control a light carried on a backpack. Gap: geometry/attachment and two-client checks are missing, and `EnableTapedPackMounts=false` still contradicts the all-on policy. [#58](https://github.com/d-addison/hollow-country/issues/58) | `EnableTapedPackMounts=false`; `DefaultCrossSlotLights=false`, `DefaultPermittedPairIds=[]`; `taped_light.disable`. | *Needs a two-player test* |
| **Taped helmet lights** | Helmet mount pairs retain native attachment and beam requirements. Gap: catalogue admission has no two-client attachment or beam confirmation. [#58](https://github.com/d-addison/hollow-country/issues/58) | `taped_light.disable` turns off taped-light admission. | *Needs a two-player test* |

### Infected

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Packs and perception** | Nearby infected adopt bounded pack routes and respond to perceived contact rather than a hidden live player position. Gap: the measured room catalogue and native route/perception checks are incomplete. [#NEW-infected-navigation] | `EnableInfected=true`; `InfectedBindRadius=30`, `MaxBindQueriesPerTick=2`; `infected_pack_routes.disable`, `infected_ce_adoption.disable`, `infected_vision.disable`, `infected_contact_guard.disable`. | *Needs a two-player test* |
| **Local alerts** | Nearby infected relay an encounter through bounded local alert chains. Gap: audibility and perception from two player positions remain unconfirmed. [#NEW-infected-audio] | `EnableAlertChains=true`; `infected_supplementary_chains.disable`. | *Needs a two-player test* |
| **Investigation and memory** | Infected investigate observed clues and retain bounded encounter memory instead of tracking a player everywhere. | `EnableInfected=true`, `EnableWorld=true`; `infected_investigation.disable`. | *In-game test pending* |
| **Persistent hordes** | Horde membership and recovery account for living members across world state changes. Gap: safe native abstraction, activation and restart recovery remain unconfirmed. [#NEW-horde-recovery] | `EnableHordes=true`; `MaxActiveHordes=2`, `MaxActiveHordeMembers=24`; `infected_horde_routes.disable`, `infected_member_recovery.disable`. | *In-game test pending* |
| **Horde migration** | World history assigns movement along authored routes. Gap: migration routes come from patrol waypoints rather than a native navmesh survey. [#121](https://github.com/d-addison/hollow-country/issues/121) | `EnableWorld=true`; `EnableHordes=true`. | *In-game test pending* |
| **Doors and door pressure** | Door policies let eligible infected open or pressure doors without blocking player routes. Gap: native doorway traversal, door damage and replicated door state remain unconfirmed. [#NEW-infected-doors] | `EnableInfected=true`. | *Needs a two-player test* |
| **Reach and vulnerable positions** | Reach policies use attacks and steering against accessible low roofs, ladders and vehicles. There is no teleport correction. Gap: chase attacks, vault landings and vehicle damage remain unconfirmed; windows, crawl gaps and deep water retain native limits. [#NEW-infected-reach] | `EnableInfected=true`. | *In-game test pending* |
| **Postures and visual variety** | Appearance substitutions, role policies and the native crawler idle hold provide variety. Gap: sitting, prone sleepers, risers, wake transitions and the full recognisable roster lack native confirmation. [#121](https://github.com/d-addison/hollow-country/issues/121) | `EnableInfectedVariety=true`; `EnableGroupScaling=true` controls group-size scaling. | *Needs a two-player test* |
| **Sitters** | An original sitting-infected animation supplies the sitter pose. Gap: its animation package, late joins and replicated poses have no recorded client/server test. [#121](https://github.com/d-addison/hollow-country/issues/121) | `EnableInfectedVariety=true`; admin `sitter` uses normal admission. | *Needs a two-player test* |
| **Death reactions** | Death selection changes the native default to an impulse reaction while preserving corpse access. Gap: the visual difference, corpse loot and replication are unobserved; the engine exposes no infected ragdoll API. [#NEW-infected-deaths] | `infected_deaths.disable` turns it off. | *Needs a two-player test* |
| **Distance-based infected work** | Infected LOD reduces distant processing with bounded observation and population accounting. Gap: network ranges, simulation controls and client frame time are unmeasured; virtual herds remain off. [#135](https://github.com/d-addison/hollow-country/issues/135) | `EnableInfected=true`; separate infected LOD profile controls distance bands; see the [module reference](docs/MODULE_STATUS.md). | *Needs a two-player test* |

### Stamina, groups and navigation

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Stamina and weight** | Continuous movement uses one quarter of normal drain, recovery is 2.5 times normal and the weight penalty is halved. Separate stamina and weight bars show effort and burden; jumping and melee retain native costs. | Stamina `Settings.Enabled=true`, `ContinuousExertionScale=0.25`, `RecoveryScale=2.5`, `WeightPenaltyScale=0.5`. | *Needs a two-player test* |
| **Groups and shared map** | Invite teammates, manage membership and use world/map teammate icons. Press M, the rebindable DayZ map key, to pan, zoom and share editable markers and notes. Gap: invite races, membership privacy, reconnects and additional information layers remain unchecked or incomplete. [#NEW-group-map] | `EnableGroups=true`. | *Needs a two-player test* |
| **Team pings and death pins** | Group pings and death-pin permissions restrict information to eligible teammates. | `EnableTeamPing=true`; `EnableGroups=true`. | *Needs a two-player test* |
| **Discovery and received leads** | Shelter discoveries and received leads add appropriate group pins without exposing unreceived information. | `EnableTravel=true`, `EnableLeads=true`; `EnableGroups=true` for shared pins. | *Needs a two-player test* |
| **Familiarity** | Foraging familiarity improves with use, decays and resets on character death. Records are capped. | `EnableProgression=true`; `MaxFamiliarityRows=0` selects the built-in cap of 128. | *In-game test pending* |
| **Survival alignment** | Visual seasons leave native warmth and clothing rules intact; there is no added meal-heat bonus. Stamina remains owned by the stamina profile. | Legacy `EnableMealBuffs=true` is retained for compatibility and has no thermal effect. | *In-game test pending* |

### Travel, wrecks and vehicles

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Trail shelters** | Shared shelters offer places to stop and record discoveries on the group map. Gap: five shelter survey entries and rendered alignment/clearance remain unresolved. [#NEW-travel-surveys] | `EnableTravel=true`. | *In-game test pending* |
| **Wreck salvage** | Eligible wrecks hold finite parts rather than an unlimited salvage source. The server records claims and refuses unsupported wrecks. | `EnableTravel=true`. | *In-game test pending* |
| **Repairable transport** | The installed travel content includes common cars needing real parts, a few boats and many bicycles. RaG vehicle repairs and bicycle animations come from the published dependencies. Gap: placement, repairs, bike presentation and travel content are unconfirmed in play. [#NEW-travel-surveys] | `EnableTravel=true` controls travel services; installed vehicle/bicycle overlays need rollback to remove. | *Needs a two-player test* |
| **Vehicle recovery** | The vehicle-flip action validates recovery before changing a vehicle. Gap: native recovery impulses are not implemented, so this is not a confirmed way to right a car. [#NEW-vehicle-flip] | `EnableVehicleFlip=true`. | *In-game test pending* |

### AI world

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **AI sites and patrols** | The Expansion AI addon supplies armed patrols and checkpoints at configured sites. Actor counts share the server AI limits; the provider has ordinary damage and finite ammunition. Gap: site navigation and some checkpoint props remain unconfirmed. [#NEW-ai-sites] | Addon provider `Enabled=true`; `pve_patrols.disable`; `AILimits.MaxActiveSites=15`, `AILimits.MaxActiveAI=72`. | *In-game test pending* |
| **AI self-defence and gestures** | Survivors react to threats, observed gestures and remembered betrayal through the addon. Gap: punches, shots, near misses, rescue shots, grudge expiry and emote acknowledgement lack in-game checks. [#139](https://github.com/d-addison/hollow-country/issues/139) | `EnableEncounters=true`; addon limits bound signal work and memory. | *In-game test pending* |
| **Scavengers and pickers** | Picker records load surveyed routes and journal real-item custody for scavenging runs. Gap: the Expansion AI group walk and return receipt are not wired, so no picker trip walks yet. [#144](https://github.com/d-addison/hollow-country/issues/144) | `EnableEncounters=true`; `AILimits.PartyMin=2`, `AILimits.PartyMax=6`. | *In-game test pending* |
| **AI trade and caravans** | Trade exchanges real items between nearby AI parties using reciprocal, journalled transfers. Gap: no funded trade pair is offered, so no trade occurs yet; parties must already be close and caravan corridor/provider checks are incomplete. [#145](https://github.com/d-addison/hollow-country/issues/145) | `EnableEncounters=true`; `AILimits.MaxParties=24`. | *In-game test pending* |
| **Faction conflict** | Faction conflict records outcomes from observed actors and preserves finite faction strength. Gap: no opposed pair is offered, so conflict and territory shifts do not occur in play yet. [#146](https://github.com/d-addison/hollow-country/issues/146) | `EnableEncounters=true`; `AILimits.FactionStrengthMax=24`. | *In-game test pending* |
| **Holdouts** | Killable, lootable survivor groups occupy places with real caches and a seven-day return lockout, including downtime. | `EnableEncounters=true`; `AILimits.HoldoutMin=3`, `AILimits.HoldoutMax=6`, `AILimits.MaxHoldouts=48`. | *In-game test pending* |
| **Camps and neighbours** | Fire, shelter and storage support camp recognition, three tiers, visitors and mailboxes. Warned probes can pressure mature camps from day 14. Gap: unattended unlocked-crate theft stays disabled until lock state is defined; forced visits/raids remain unavailable. [#NEW-camp-interactions] | `EnableCamps=true`; `AILimits.CampMin=2`, `AILimits.CampMax=6`, `AILimits.MaxCamps=32`, `AILimits.MaxCampItems=64`. | *Needs a two-player test* |
| **Camp respawn and claims** | Eligible groups use camp respawn and a single building claim with construction restrictions. Gap: claim expiry, breakable doors and claim vulnerability lack acceptance. [#151](https://github.com/d-addison/hollow-country/issues/151) | `EnableCampRespawn=true`, `EnableCamps=true`, `EnableGroups=true`. | *Needs a two-player test* |
| **Settlements and world materialisation** | Persistent settlement records select occasional occupation, parties or traces. Materialisation and its addon bridge bind world proposals to actors; settlement decay records changes over time. | `EnableWorld=true`, `EnableEncounters=true`; `AILimits.MaxOccupiedPlaces=15`, `AILimits.MaxMaterialized=15`, `AILimits.OccupationMin=3`, `AILimits.OccupationMax=8`. | *In-game test pending* |

### Events and situations

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Situation director** | Durable situations expose incidents players can observe, exploit or ignore. Gap: the actor provider depends on the Expansion AI addon and client checks; moving convoys, rescue/evacuation branches, raid providers and surveyed corridors remain incomplete. [#147](https://github.com/d-addison/hollow-country/issues/147) | `events.disable`, `events_sites.disable`; `EnableEncounters=true`; `AILimits.MaxEncounters=15`. | *In-game test pending* |
| **Scenes and police incidents** | Last stands, quarantine, evacuation and police scenes leave contextual props and clues. Stages expire rather than forcing a quest. Gap: the three reviewed event sites lack field surveys and nonzero rewards remain blocked. [#147](https://github.com/d-addison/hollow-country/issues/147) | `EnableEncounters=true`; `events_sites.disable` for event-site admission. | *Needs a two-player test* |
| **Radio reports and Morse** | A powered PersonalRadio receives faction reports and Morse clues on the correct channel; received leads can be shared with the group. | `EnableLeads=true`. | *Needs a two-player test* |
| **Dead drops** | A finite dead-drop cache gives a place to investigate; another survivor may already have taken its contents. | `EnableEncounters=true`. | *Needs a two-player test* |
| **Body stories and notes** | Bodies and rare paper notes carry contextual leads. Notes are capped at one per scene and ten across the world. | `EnableLeads=true`. | *Needs a two-player test* |
| **Burn events and story chains** | Story kits and burn-event admission connect incidents to finite evidence and stock. Gap: the CE incident source still refuses, so complete funded burn chains lack in-game proof. [#147](https://github.com/d-addison/hollow-country/issues/147) | `EnableEncounters=true`; `EnableStories=true`, `ArrivalSeconds=21600`, `Window=4`. | *In-game test pending* |
| **Persistent stories and escalation** | New stories arrive on a persistent six-hour schedule; completed stories do not replay. Capped escalation changes world pressure over time. | `EnableWorld=true`; `EnableStories=true`, `ArrivalSeconds=21600`, `Window=4`. | *In-game test pending* |

### Ecology, wildlife and foraging

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Wildlife and habitats** | Native wildlife and Ambient Animals supply animal presence around suitable places; observation records separate animals from infected. Gap: feeding, drinking, resource seeking, herd/predator interactions and animal combat are incomplete; habitat events remain inert. [#149](https://github.com/d-addison/hollow-country/issues/149) | `EnableAmbientLife=true`; `ecology_migration.disable`; installed animal overlays need rollback. | *In-game test pending* |
| **Carcasses** | Observed carcasses support world traces such as flies. Gap: authored carcass spawning refuses without economy admission. [#149](https://github.com/d-addison/hollow-country/issues/149) | `EnableAmbientLife=true`; `EnableSignsOfLife=true` for visual traces. | *In-game test pending* |
| **Forage and herbs** | Forage nodes retain finite claims and refill delays; berries and herbs use the same table throughout the visual year. Native herb behaviour remains intact. Gap: five content/route rows retain named refusals. [#NEW-forage-routes] | `EnableForage=true`; `EnableProgression=true` controls familiarity. | *In-game test pending* |

### Atmosphere

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Lighting and weather** | Lighting and weather-day profiles alter dusk, overcast and storm conditions while keeping nights readable. Gap: weather profiles do not install automatically; profile balance, fog and native world-data interaction remain unchecked. [#NEW-weather-profiles] | `EnableAtmosphere=true`, `EnableGrade=true`; `atmosphere.disable`. | *In-game test pending* |
| **Colour grade** | A rebindable grade control cycles personal colour-grade intensity from 0 to 100% in 10% steps; zero restores the vanilla presentation. | `EnableGrade=true`; `ClientPresentationMask=15`, grade bit 2. | *In-game test pending* |
| **Visual seasons** | A running-server clock changes visual seasons without new cold penalties; the client receives seasonal presentation and forecasts. Gap: white winter terrain has no admitted source and client seasonal presentation is unchecked. [#150](https://github.com/d-addison/hollow-country/issues/150) | `EnableVisualSeasons=true`; `PhaseSeconds=604800`, `CheckpointSeconds=60`. | *Needs a two-player test* |
| **Cellars and darkness** | Cellar survey and presentation code identify interiors needing darker presentation; the operator-only sampler records geometry when the server profile contains `HollowCountry/measure-cellars`. Gap: native darkness depends on the Expansion AI addon/client checks, with stair geometry and coverage still unqualified. [#NEW-cellar-darkness] | `EnableAmbientLife=true`; `ClientPresentationMask=15` governs the available client layers; remove `HollowCountry/measure-cellars` to stop the sampler. | *Needs a two-player test* |
| **Signs of life** | Lit windows, chimney smoke and carcass flies provide environmental clues. | `EnableSignsOfLife=true`; `ClientPresentationMask=15`, signs bit 4. | *Needs a two-player test* |
| **Environmental hints and sound** | Local hints and environmental sound add presentation around world activity. | `EnableAmbientLife=true` controls server admission; `ClientPresentationMask=15`, hints bit 1 and ambient bit 8 control clients. | *Needs a two-player test* |

### Persistence, administration and performance

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **World persistence** | World, settlement, camp, lead and item-transfer journals retain history across restarts. A shared save scheduler stages work and handles recoverable files. Gap: restart recovery and empty pending-file readback remain unconfirmed natively. [#197](https://github.com/d-addison/hollow-country/issues/197) | `EnableWorld=true` disables world simulation; the shared save service has no independent operator switch. | *In-game test pending* |
| **Admin test kit** | Authorised admins use Pause to inspect status and exercise normal infected, world, camp and event commands. Actions keep normal caps and report refusal reasons. Gap: COT-role authorisation, fresh dormant spawning and some forced tier/visit/raid actions are unavailable. [#NEW-admin-kit] | `EnableAdminMap=true`; the server admin allowlist controls access. | *In-game test pending* |
| **Debug snapshot and map** | Read-only world snapshots feed a local browser map and the admin Map tab, with counts and selectable world/AI layers. Gap: live layers, UI controls and two-client visibility remain unconfirmed; snapshot replacement is not atomic. [#197](https://github.com/d-addison/hollow-country/issues/197) | `EnableDebugSnapshot=true`, `EnableAdminMap=true`. | *Needs a two-player test* |
| **Loot map** | The admin Map tab runs a bounded loot query, acknowledges it and retains the latest successful marks. Gap: query controls, running-job refusal, rendering and cost remain unconfirmed in DayZ. [#197](https://github.com/d-addison/hollow-country/issues/197) | `EnableAdminMap=true`; see [debug map controls](docs/DEBUG_MAP.md). | *In-game test pending* |
| **Shared tick budget** | Infected sampling, interior lock expiry and search work draw from one per-tick work allowance; each consumer retains a starvation-prevention unit. Gap: three-to-six-player frame times and per-module costs remain unmeasured. [#138](https://github.com/d-addison/hollow-country/issues/138) | `TickIntervalMs=1000`, `MaxTickWorkItems=32` tune shared work; disable individual consumers with their area switches. | *In-game test pending* |

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

Follow the [friend-server AI runbook](docs/FRIEND_SERVER_AI_RUNBOOK.md), [installation and rollback guide](docs/INSTALL_ROLLBACK.md) and [friend-server configuration](docs/FRIEND_SERVER.md) for exact commands, backups and recovery. Runtime flags do not remove installed mission content; use the installer receipt and rollback procedure for those changes.

## Server settings reference

The shared operator input is [mission settings](mission/hollow-country/operator/settings.json), mirrored in [config defaults](config/hollow-country-settings.json) and validated against the [shared settings registry](tools/validate/shared_settings.json). The live server reads `HollowCountry/settings.json` under its profile. Preserve explicit operator choices and restart after changes. Defaults below are the checked-in values, not proof of in-game results. See the [operator guide](docs/README.md) for the separate module profiles and state files.

### Feature switches

All switches in this table default to `true` except the explicitly shown pack-light exception. Set a switch to `false` to turn off its named area. Diagnostics, client presentation and installed overlays have separate controls.

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
| `EnableVehicleFlip` | `true` | Vehicle-recovery action preference; native impulse is missing. |
| `EnableMealBuffs` | `true` | Legacy compatibility field; no meal heat hooks or thermal bonus. |
| `EnableForage` | `true` | Finite forage nodes and recovery. |
| `EnableProgression` | `true` | Per-character-life forage familiarity. |
| `EnableGroupScaling` | `true` | Infected group-size scaling; variety module can run for this alone. |
| `EnableTapedPackMounts` | `false` | Pack light admission; checked-in false and per-pair checks remain exceptions to all-on policy. |

### Shared work, density and format

| Key | Default | Effect |
| :--- | :--- | :--- |
| `SchemaVersion` | `1` | Shared settings format; only 1 is accepted. |
| `ClientPresentationMask` | `15` | Client layers: hints=1, grade=2, signs=4, ambient=8. Add allowed bits; 0 disables all four. Range 0–15. |
| `TickIntervalMs` | `1000` | Core tick interval in milliseconds; 500–10000. |
| `MaxTickWorkItems` | `32` | Shared tick work allowance; 1–256. Starvation prevention can add up to five items. |
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

The [light-mount config](config/hollow-country-light-mounts.json) is an offline mirror, not a runtime settings file. Runtime pack defaults come from the [backpack manifest](mission/hollow-country/lights/backpack-mounts.json) `SettingsContract`. [Pair receipts](mission/hollow-country/lights/pair-receipts.json) record checks; changing a preference does not establish a valid mount. Pack, helmet and cross-slot checks are tracked in [#58](https://github.com/d-addison/hollow-country/issues/58).

| File / key | Default | Effect |
| :--- | :--- | :--- |
| `crossSlotLights` | `false` | Offline mirror: cross-slot preference, closed by default. |
| `permittedPairIds` | `[]` | Offline mirror: no allowed pack pairs by default. |
| `DefaultCrossSlotLights` | `false` | Runtime manifest default for cross-slot pack mounts. |
| `DefaultPermittedPairIds` | `[]` | Runtime manifest default allowed pack pair IDs. |
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

The Map tab displays snapshot layers, routes and per-layer counts. The loot map runs a bounded query and retains the last successful marks. `EnableDebugSnapshot` controls export; `EnableAdminMap` controls authorised in-game access. The [debug map guide](docs/DEBUG_MAP.md) covers the local browser map, snapshot freshness, layer caps and query controls. Keep exported maps and profiles private. Configure COT separately using the [COT permissions guide](docs/COT_PERMISSIONS.md).

## Performance

The intended test load is **3–6 players**. Recorded boots do not establish a tested player capacity. Performance budgets remain provisional until measurements with that load; larger-server capacity is unproven.

`TickIntervalMs=1000` sets the core cadence. `MaxTickWorkItems=32` is shared by infected sampling, interior lock expiry, search binding, maintenance, refresh and detached recycling. Starvation prevention gives each consumer one unit, so six consumers can use up to 37 items in a tick. This is a work-item limit, not a millisecond frame-time guarantee. `[HC TickWork]` reports shared usage and starvation; `[HC CostTotal]` and `[HC Cost]` report aggregate and module costs. Building-class first resolves, event preflight, ecology and world saves still need target-load measurement in [#138](https://github.com/d-addison/hollow-country/issues/138).

## Documentation and contributing

- [Operator documentation](docs/README.md): configuration, persistence, backups and recovery.
- [Addon development](docs/MOD_DEVELOPMENT.md): source layout and package workflow.
- [Tools](tools/README.md): standard-library tooling, installers and validators.
- [Tests](tests/README.md): offline checks and the limits of their evidence.
- [Contributing](CONTRIBUTING.md): contribution requirements.

Report bugs through [GitHub issues](https://github.com/d-addison/hollow-country/issues), with the build, feature, expected/actual result and sanitised refusal/log lines. Do not attach credentials, identifiers, private profiles or third-party assets. Missing runtime behaviour remains open until tested on DayZDiag and a normal signed PBO/server; sound, visibility and replication need two clients.

## License and assets

Copyright © 2026 David Addison. **All rights reserved.** No open-source or public reuse license is granted. Third-party materials retain their owners' terms; see the [provenance inventory](docs/PROVENANCE_AND_LICENSES.md).

Game files, full vanilla dumps, purchased assets, Workshop packages, signing private keys, credentials and runtime profiles do not belong in this repository. Source remains private; published third-party Workshop dependencies are never repacked.
