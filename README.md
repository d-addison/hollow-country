# Hollow Country

A server and client survival overhaul for DayZ Standalone 1.30.

[Features](#features) · [Required mod stack](#required-mod-stack) · [Install](#install) · [Server settings](#server-settings-reference) · [Admin tools](#admin-tools) · [Documentation](#documentation-and-contributing)

**DayZ PC · ChernarusPlus · All rights reserved**

Hollow Country adds finite scavenging, salvage, infected behaviour, shared navigation and a persistent world of survivors, incidents and environmental clues. The server owns world changes and inventory transfers. Players can explore, avoid trouble or follow a lead without accepting a quest.

## Features

Every feature is on by default. The [current source record](docs/MODULE_STATUS.md#current-source-changes--rounds-r8r11-2026-11-20) lists the remaining native checks for this build. Each feature can be switched off with the settings and opt-out markers listed with it. Installed loot and vehicle overlays use stopped-server receipt rollback. Inventory sizing can be removed by generating, reviewing and signing a replacement addon; see [installation](#install).

Set an `Enable…` or `Enabled` preference to `false` to disable its feature; `Disabled` opt-outs instead use `true`. Switches shared by several features disable that whole area. Setting names below refer to the tables in [Server settings](#server-settings-reference). A server opt-out such as `fuel_siphon.disable` means an empty file under `HollowCountry/acceptance/` in the server profile, absent by default. Remove it and restart to restore the preference. Missing routes or actors are described beside the affected feature.

Each feature has one compact test mark: *Tested locally* requires a recorded gameplay observation; *In-game test pending* means gameplay is unverified. Acceptance uses DayZDiag and a normal signed PBO/server, with at most one client. No feature below has a DayZ gameplay verdict. Offline checks and server compilation do not establish one.

The authored Chernarus coverage resolves 88 localities, 528 finite AI sites and
523 story sites, with connected road candidates and habitat membership tied to
stock data. Catalog size does not increase active population caps. Native route surveys, site binding and shelter access/rain checks remain pending.
Both story schedulers now use free window capacity; all 74 shelter scenes remain enabled.

### Searching and loot

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Finite searching** | Searching takes time and draws from finite supplies; searched places retain depletion history. | `EnableSearch=true`; `MaxBoundSearchSites=256`; `interior_search.disable`. | *In-game test pending* |
| **House and cabinet search** | House search names unavailable supply. Bound cabinets offer a six-second search after a server-confirmed site check, including refresh sites; decorative cabinets do not offer it. | `EnableSearch=true`; `interior_search.disable`. | *In-game test pending* |
| **Furnished interiors** | Compatible houses receive contextual furniture and clutter through 294 paged interior templates, within the existing prop caps. Native fit, doors, stairs and wider measurements remain unverified; unsuitable rooms retain vanilla interiors. [#199](https://github.com/d-addison/hollow-country/issues/199) | `EnableInteriors=true`; `MaxActiveInteriors=12`, `MaxPropsPerInterior=5`, `MaxFurnishedProps=1500`; `interior_placement.disable`. | *In-game test pending* |
| **Floor spots and scarcity** | The installed economy adds 250 contextual floor points across 58 building groups and scales ordinary loot by 2 while keeping weapons and ammunition separately budgeted. The floor policy retains the extra points for clothing and exact garbage (Paper only), moves compatible displaced demand to shelves and reports unplaced capacity. Receiving containers retain native-derived loot capacity (28 zero-capacity containers and 239 stranded points corrected in generation). | Loot-point `Multiplier=2.0`; `SearchDensityScale=0` keeps density scale 1; installed overlays require rollback. | *In-game test pending* |
| **Firearms and ammunition** | Native weapons, SNAFU Weapons and Tactical Flava use selected classes and family budgets, so recolours share scarcity. The authored native roster has 78 weapon classes in 53 families, 50 magazine classes and 47 ammunition sources; modded magazines spawn 10–100% full. A generated compatibility addon guards weapon-pack bipod sway when hands are empty or hold a non-weapon; release integration and native verification remain pending. Pristine and worn weapons skip the jam roll; damaged weapons retain native jam behaviour. See the [firearms reference](docs/FIREARMS.md). | `CfgHollowCountry Firearms noJamMaxHealthLevel=1` controls the no-jam threshold (-1 restores native rolls); package selections and family budgets are install-time controls; `--no-datamined` omits the datamined additions. | *In-game test pending* |
| **Military zones and outposts** | 196 overlay scenes place 3,559 vanilla objects at military zones, outposts and camps: tents, barriers, crates, parked vehicles and story props rather than bare tents. 17 zones carry higher loot tiers, and military-only primaries share a map-wide budget sized around four Tisy kits. Every class retains nominal and minimum of at least one; civilian Prison/Police routes remain available. | Map overlay layers under `config/map-overlays/layers/`; installed and rolled back by the friend installer. | *In-game test pending* |
| **Useful equipment and storage** | Clothing, packs, tools, food and medical ingredients use contextual finite supply routes, including all 21 reviewed equipment floor rows, while missing acquisition routes remain tracked. The broad item-coverage pass was reverted in `0321022f` and is being redone as a curated vanilla-only pass; it is not completed coverage. Backpack rows scale by 1.5; eligible small items occupy less space. Ancestry-based rules cover the declared stack, with 570 vanilla and 51 stack overrides; 187 weapon-pack attachment and magazine overrides cap slot dimensions at vanilla scale. Only declared packs receive overrides. Native water contamination and medicine rules remain intact; see [equipment coverage](docs/EQUIPMENT_COVERAGE.md). | `inventory-sizes.json` controls package-time size rules; `--no-datamined` omits additional supply entries. | *In-game test pending* |
| **Shelf and surface loot** | 1,072 above-floor points on raised surfaces such as shelves and counters across 119 building classes, checked for reach (including optional furniture), collision support, enclosure and item clearance before shipping; with the 250 floor points that makes 1,322 points in 140 building groups. The 3,000-point target is open ([#274](https://github.com/d-addison/hollow-country/issues/274)). | Installed with the loot-point overlays; rolled back by the friend installer. | *In-game test pending* |
| **Revisit supplies** | World history schedules later searches against finite stock rather than refilling every restart. | `EnableWorld=true`, `EnableSearch=true`; `SearchDensityScale=0`. | *In-game test pending* |

### Crafting, recovery and lights

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Salvage and recovery** | Recover netting from camo nets, wire from reels or barbed bats, leather panels, and wood or nails from suitable bats and ruined crates. Fabric and teddy recovery use guarded recipes, tools and finite ingredients. Tailor all four colours of leather pants or storage vests from three or four panels respectively, consuming ten sewing-kit quantity units. | `EnableCrafting=true`. | *In-game test pending* |
| **Construction and fortification** | Vanilla fence, watchtower, flag, shelter and light kits remain craftable. Claimed buildings support fortification; AI sites fortify around authored anchors with durable slot reservations and requeue after ownership returns. | Native kit recipes; normal claim and AI-site policies apply. | *In-game test pending* |
| **Fuel siphoning** | Siphon real fuel from a stationary car with its engine off into a compatible bottle or jerry can. Transfers debit the tank and respect container capacity. | `fuel_siphon.disable` turns it off. | *In-game test pending* |
| **Taped weapon lights** | Tape a weapon light to a compatible native gun slot; removal returns the same light and battery without refunding tape, including lights missing an older build marker. Cross-slot pairs cover TLRLight on 22 rail rifles and UniversalLight on seven pistols. | `taped_light.disable`; set `Disabled=true` on an individual pair receipt to opt out. | *In-game test pending* |
| **Taped pack lights** | Pack mount catalogues and per-pair preferences control a light carried on a backpack. Pack and helmet mounts and all 29 cross-slot weapon pairs are admitted unverified. Exact helmet and pack slots support held mount/remove and held/worn toggles; per-pair opt-outs apply to the mounted slot. Gap: unsupported native slot pairs remain refused. [#58](https://github.com/d-addison/hollow-country/issues/58) | `EnableTapedPackMounts=true` (also when absent); pair receipt `Disabled=true` opts out; `taped_light.disable`. | *In-game test pending* |
| **Taped helmet lights** | Helmet mount pairs use native attachment and beam ownership, respect their own receipt opt-outs and report shared taped-light availability. | `taped_helmet.disable` opts out of helmet mounts; `taped_light.disable` disables taped lights. | *In-game test pending* |

### Infected

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Packs and perception** | Nearby infected adopt bounded pack routes and respond to perceived contact rather than a hidden live player position. | `EnableInfected=true`; `InfectedBindRadius=30`, `MaxBindQueriesPerTick=2`; `infected_pack_routes.disable`, `infected_ce_adoption.disable`, `infected_vision.disable`, `infected_contact_guard.disable`. | *In-game test pending* |
| **Local alerts** | Nearby infected relay an encounter through bounded local alert chains. | `EnableAlertChains=true`; `infected_supplementary_chains.disable`. | *In-game test pending* |
| **Investigation and memory** | Infected investigate observed clues and retain bounded encounter memory instead of tracking a player everywhere. | `EnableInfected=true`, `EnableWorld=true`; `infected_investigation.disable`. | *In-game test pending* |
| **Persistent hordes** | Horde membership and recovery account for living members across world state changes. | `EnableHordes=true`; `MaxActiveHordes=4`, `MaxActiveHordeMembers=160`; `infected_horde_routes.disable`, `infected_member_recovery.disable`. | *In-game test pending* |
| **Horde migration** | World history assigns movement along authored patrol waypoints. | `EnableWorld=true`; `EnableHordes=true`. | *In-game test pending* |
| **Doors and door pressure** | Door policies let eligible infected open or pressure doors without blocking player routes; wreck and vehicle ancestry is excluded from door scans. | `EnableInfected=true`. | *In-game test pending* |
| **Climbing and vulnerable positions** | Chasing infected can attempt a native vault toward an unreachable target 0.5–2.2 m above and within 2.5 m horizontally, using bounded obstacle rays and native landing. Four concurrent attempts and a six-second cooldown bound the work. Ladder traversal has no native command and remains deferred; shadow diagnostics only. | `EnableInfected=true`. | *In-game test pending* |
| **Postures and visual variety** | Appearance substitutions and role policies use native stance, idle and crawler wake modes. Calm crawlers can rest in catalogued rooms or near tracked corpses; gunfire and native wake logic interrupt rest. Bounded crawler groups idle at authored wrecks, roadsides, churches, gas stations and buildings; fresh bodies appear out of sight under a cap that counts corpses. Standing idle bodies and bounded corridor movement for waking groups are included; routes release on visibility, combat, expiry or ownership loss. A few infected per town spawn through the vanilla CE already crawling (small shares of the town event weights). The sitting, sleeping, lying and kneeling classes are withdrawn from the CE until a server crash in the pose command is fixed ([#315](https://github.com/d-addison/hollow-country/issues/315)). Every substitution keeps a positive donor weight and unchanged event totals. Legacy `MaxTracked=24` migrates in memory to 256; other operator values remain. Distant idle tracking recycles at most one eligible record per scan without deleting or moving infected, and herds use separate lease capacity. [#121](https://github.com/d-addison/hollow-country/issues/121) | `EnableInfectedVariety=true`; `infected_variety.disable`; `EnableGroupScaling=true` controls group-size scaling; LOD `VarietyNonCalmHoldSeconds=600`; variety `StandingRiserEvery=2`, `EnableMigration=true`, `PosedFreshEvery=3`, `MaxPosed=24` (0 off). | *In-game test pending* |
| **Melee against infected** | Heavy hits to the head can kill outright, heavy leg hits cripple and repeated arm hits weaken attacks; head and leg bonuses apply to infected only. Poise replaces stun locks with a short stagger immunity. Blocks cost stamina and can be broken or countered, swing cost follows weapon weight, and players can turn while swinging. Attacking from a block plays the bash in place as a no-damage shove that knocks infected back. | `EnableMelee=true`; melee profile `HeadExecute`, `LegCripple`, `ArmWeaken`, `InfectedPoise`, `StaggerImmunitySeconds=1.5`, `WeightStamina`. | *In-game test pending* |
| **Sitters** | Original sitting, sleeping, lying-rise and kneeling-feed animations supply the poses and their get-up transitions, within the server-wide cap. CE infected of every stock family can spawn posed. The pose command starts from a settled Move with preflighted binds ([#315](https://github.com/d-addison/hollow-country/issues/315), fixed). | `EnableInfectedVariety=true`; `MaxPosed=24`; `infected_poses.disable` opts out; admin `sitter` uses normal admission. | *Boot and one-client check passed (build 141)* |
| **Death reactions** | Death selection changes the native default to an impulse reaction while preserving corpse access. The engine exposes no infected ragdoll API. | `infected_deaths.disable` turns it off. | *In-game test pending* |
| **Distance-based infected work** | Infected LOD reduces distant work. Eight inland ChernarusPlus seeds support virtual herds that materialise near players under observer checks. Older settings migrate to schema 3 and add seeds to empty lists; non-empty custom lists and schema-2 opt-outs are preserved. | `EnableInfected=true`; profile `HollowCountry/Infected/lod.json`: `EnableLOD=true`, `EnableVirtualHerds=true`; distance and population defaults are listed below. | *In-game test pending* |

### Stamina, groups and navigation

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Stamina and weight** | Continuous movement uses one quarter of normal drain, recovery is 2.5 times normal and the weight penalty is halved. Client-ready resynchronisation retries the server profile after connection (server replies at most once per connection per 10 seconds). Separate stamina and weight bars show effort and burden; jumping and melee retain native costs. | Stamina `Settings.Enabled=true`, `ContinuousExertionScale=0.25`, `RecoveryScale=2.5`, `WeightPenaltyScale=0.5`. | *In-game test pending* |
| **Groups and shared map** | Invite teammates, manage membership and use world/map teammate icons. Press M, the rebindable DayZ map key, to pan, zoom and share editable markers and notes. | `EnableGroups=true`. | *In-game test pending* |
| **Team pings and death pins** | Group pings and death-pin permissions restrict information to eligible teammates. | `EnableTeamPing=true`; `EnableGroups=true`. | *In-game test pending* |
| **Discovery and received leads** | Shelter discoveries and received leads add appropriate group pins without exposing unreceived information. | `EnableTravel=true`, `EnableLeads=true`; `EnableGroups=true` for shared pins; group members share visited places when `ShareDiscovery=true` in `$profile:HollowCountry/Groups/settings.json` (default). | *In-game test pending* |
| **Familiarity** | Foraging familiarity improves with use, decays and resets on character death. Records are capped; bounded summaries report awards, skips and persistence. | `EnableProgression=true`; `MaxFamiliarityRows=0` selects the built-in cap of 128. | *In-game test pending* |
| **Survival alignment** | Visual seasons leave native warmth and clothing rules intact; there is no added meal-heat bonus. Stamina remains owned by the stamina profile. | Always enabled; native food and warmth rules apply. | *In-game test pending* |

### Travel, wrecks and vehicles

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Trail shelters** | Shared shelters offer places to stop and record discoveries. Five regional exterior scenes use stock roofs with access keepouts, budgeted placement and discovery only after completion. All 74 scenes remain enabled; bounded nearby layout retries check ground support and report placement refusals. Native access/rain checks remain pending. | `EnableTravel=true`; regional `Enabled=true`; regional `Enabled=false` opts out. | *In-game test pending* |
| **Wreck salvage** | Eligible wrecks hold finite parts rather than an unlimited salvage source. The server records claims and refuses unsupported wrecks; bounded summaries report use and successful salvage. | `EnableTravel=true`. | *In-game test pending* |
| **Repairable transport** | The installed travel roster adds 23 Expansion vehicles and finite repair parts: repairable common cars, many bikes and a few boats. Event budgets cover 39 cars, seven trucks, 28 motorbikes, six boats and four rare aircraft; bicycles use their separate overlay. These are configured populations, not observed counts. RaG vehicle repairs and bicycle animations come from the published dependencies. | `EnableTravel=true` controls travel services; installed vehicle/bicycle overlays need rollback to remove. | *In-game test pending* |
| **Vehicle recovery** | The vehicle-flip action checks nearby helpers or a crowbar, then applies at most three bounded torque/lift impulses with safety checks and a cooldown; summaries distinguish attempts from successful recovery. | `EnableVehicleFlip=true`. | *In-game test pending* |
| **Helicopters** | Expansion helicopter support tracks world aircraft and caps CE spawn fuel without creating vehicles. A four-aircraft CE budget keeps helicopters rare. The crash/landing incident bridge lives in the Expansion AI addon after its vehicle dependency. Gap: ambient AI overflight has no flight port. [#147](https://github.com/d-addison/hollow-country/issues/147) | `helicopters.disable`; `Helicopters.WorldCap=4`, `Helicopters.SpawnFuelMaxFraction=0.1`. | *In-game test pending* |

### AI world

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **AI sites and patrols** | The Expansion AI addon supplies armed patrols and checkpoints at configured sites. Each of five roles has five coherent kit archetypes, varied wear and scarce personal supplies; firearm odds remain unchanged. Fresh group replacement preserves physical bodies and finite inventories. Actor counts share the server AI limits; the provider has ordinary damage and finite ammunition. | Addon provider `Enabled=true`; `pve_patrols.disable`; `AILimits.MaxActiveSites=15`, `AILimits.MaxActiveAI=72`. | *In-game test pending* |
| **Zone guards** | Each military zone is held by AI, overrun by military infected or abandoned. States shift over days within a cooldown and a daily change cap, and guarded zones hold richer loot. Guards use moderate difficulty. Only explicitly listed sites are held while zone initialization and a live guard or replacement infected group support the hold; a dedicated work slot schedules guard ticks. | `HCZoneGuards.Disabled=false`; `CooldownDays=2`, `MaxChangesPerDay=2`, `MaxOverrunMembers=6`; zones in `mission/hollow-country/ai/zones.json`. | *In-game test pending* |
| **AI routines and movement** | Bounded role schedules choose funded activities from perceived danger and local time. Formations and movement styles follow context; smoke cover and infected lures spend real carried items. Mechanics walk to cars and repair with real parts and tools. Gap: role-specific raid dispatch lacks a public group-offer port. [#146](https://github.com/d-addison/hollow-country/issues/146) | Role `Enabled=true`; `role_activities.disable`, `ai_tactics.disable`; formation `Disabled=false`, tactics `Disabled=false`; `ai/car-repair.json` `Enabled=true`. | *In-game test pending* |
| **Perceived world incidents** | Native gas zones, crashes, actual gunfire, smoke and source-owned scene/raid/horde receipts prompt bounded avoid, investigate, react or flee leases. A member must perceive the incident; sight uses a raycast and AI receive no hidden player coordinates. | `world_incidents.disable`, `incident_response.disable`; `incidents.json`, `ai-incident-response.json`. | *In-game test pending* |
| **AI self-defence and gestures** | Survivors react to raised weapons, surrender and perceived greetings. A greeting needs fresh mutual sight and a greeting-specific acknowledgement. Neutral hits and kills feed bounded faction betrayal memory. Attack, rescue-shot, near-miss and grudge-expiry responses await [play checks](https://github.com/d-addison/hollow-country/issues/139). | `EnableEncounters=true`; `ai/sites.json`: `MaxSignalWorkPerSecond=8`, `MaxBetrayalRows=128`, `BetrayalRetentionSeconds=172800`; `ai_trade_emote_ack.disable` opts out of trade acknowledgement. | *In-game test pending* |
| **Scavengers and pickers** | One ledger party seeds per surveyed scavenger site. Groups of 2–6 walk need-driven runs, search up to three houses through the same finite reservations as players and carry up to three real house items home to their camp crate. The owning picker can prepare a due house refresh. Combat and remembered danger can abort a run; full crates leave goods on the carrier, lootable from its body. Journaled custody prevents replay after restart. Surveyed endpoint crates retain finite stock and player-clear refill checks. An invalid cache section is refused by name (`[HC Pickers] caches refused reason=...`) and the module reports degraded. | `EnableEncounters=true`; `pve_patrols.disable`, `scavenge_runs.disable`; `RunMaxMembers=6`, `RunMaxCarriedHouseGoods=3`; source defaults `MaxConcurrentTrips=1`, `PartyCooldownSeconds=900`; `ai/picker-routes.json` controls routes, stock and cache limits below. | *In-game test pending* |
| **AI trade and caravans** | Friendly funded camps barter real carried surplus. Existing groups walk bounded installed-road routes, greet in mutual sight, exchange items and return. Confirmed cargo loss debits both camp allocations once; uncertain restart receipts are quarantined. | `EnableEncounters=true`; `ai_caravans.disable`, `ai_trade_emote_ack.disable`; `ai/trade-recipes.json` and `ai/caravans.json` tune pairing, stock and journeys below. | *In-game test pending* |
| **Faction conflict** | Opposed live parties fight under native combat observation. Distant conflicts update territory within a durable daily quota without inventing actor deaths or loot. Territory outcomes persist; existing infected can pressure camps. | `EnableEncounters=true`, `EnableWorld=true`; profile `faction-conflict.json`: `Enabled=true`, `FarMeters=1500`, `CooldownSeconds=604800`, `MaxDailyOutcomes=2`; further limits below. | *In-game test pending* |
| **Holdouts** | Killable, lootable survivor groups occupy places with real caches. Configurable site respawn defaults to 900 seconds, depleted-group replacement to 600 seconds and camp raid lockout to 1800 seconds; corpses and caches are not refilled. | `EnableEncounters=true`; `AILimits.HoldoutMin=3`, `AILimits.HoldoutMax=6`, `AILimits.MaxHoldouts=48`. | *In-game test pending* |
| **Camps and neighbours** | Fire, shelter and storage support recognition, three tiers, visitor eligibility and mailboxes. Warned probes can pressure mature camps from day 14. Visitor parties walk in through native doors to look over a mature camp (tier 3, day 14 or later, at most every three real days) and leave without taking anything. Claim-only bases with physical stored cargo become encounter targets after 14 held days, with independent durable cooldowns and attendance checks. | `EnableCamps=true`; `camp_probes.disable`; `camp_visitors.disable`; `AILimits.CampMin=2`, `AILimits.CampMax=6`, `AILimits.MaxCamps=32`, `AILimits.MaxCampItems=64`. | *In-game test pending* |
| **Camp respawn and claims** | Eligible groups use camp respawn. One building claim per group restricts construction and setting native door locks to group members; native unlocking, lockpick wear and raids retain their rules. Member visits renew the claim. | `EnableCampRespawn=true`, `EnableCamps=true`, `EnableGroups=true`; `building_claims.disable`; `building-claims-config.json`: `ExpiryDays=30`, `VisitRadiusMeters=25`, `ActionReachMeters=2`. | *In-game test pending* |
| **Settlements and world materialisation** | Persistent settlement records select occasional occupation, parties or traces. Materialisation and its addon bridge bind world proposals to actors; settlement decay records changes over time. | `EnableWorld=true`, `EnableEncounters=true`; `AILimits.MaxOccupiedPlaces=15`, `AILimits.MaxMaterialized=15`, `AILimits.OccupationMin=3`, `AILimits.OccupationMax=8`. | *In-game test pending* |
| **Base containers** | Native tents, barrels, chests and crates count as storage wherever they are placed. Storage-only camps start at tier one and gain hearth recognition when a real burning fire arrives. Native inventory owns every item. | `EnableCamps=true`, `EnableGroups=true`; `base_containers.disable`; `AILimits.MaxCamps=32`, `AILimits.MaxCampItems=64`. | *In-game test pending* |
| **Unattended camp theft** | An outbound picker already in pickup range can carry one eligible real item from an unattended camp crate through its existing custody chain. Attendance and observer checks guard pickup and deposit; carrier loss retains physical cargo. A crate refused for this crate alone (attended, observed, home, empty) is skipped and the scan continues. An observed home defers the deposit for up to `PartyCooldownSeconds` (900 s), then the normal durable refusal leaves the item on its carrier. | `EnableCamps=true`, `EnableEncounters=true`; `camp_theft.disable`; `camp-theft-config.json` has `MaxAttemptsPerDay=1`, `MaxAttendancePlayers=32`, `AttendanceRangeMeters=500`, `ObserverRangeMeters=500`. | *In-game test pending* |
| **Base raids** | A raider party can hit an unattended claimed base after a warning, with its group online elsewhere. Raiders walk native routes, keep native door rules and carry one real item out through a journaled custody move; probe cooldowns and live attendance checks still apply. | `EnableCamps=true`, `EnableEncounters=true`; `base_raid.disable` (`camp_probes.disable` also turns it off); `base-raid-config.json` has `WarningSeconds=300`, `RaidSeconds=600`, `NoticeRangeMeters=40`, `AttendanceRangeMeters=500`. | *In-game test pending* |

### Events and situations

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Situation director** | Durable incidents let players observe, exploit or ignore nearby trouble. Leased parties walk to hostile funded camps; capped infected use eligible hidden points. Original routes and actual actor outcomes are retained. Pinned survivors hold at their shelter while threats are live; road caravan attacks use nearby road threat points. Wreck-pinned survivors and leased-party smoke retries are included. Raid and column parties can borrow a qualified existing car, drive a bounded road route, dismount and continue on foot; player drivers take priority. | `EnableEncounters=true`; `events.disable`, `events_sites.disable`, `w38_situations.disable`, `w38_raids.disable`, `w38_transit.disable`, `convoys.disable`; `W38Situations.*` controls below. | *In-game test pending* |
| **Scenes and police incidents** | Last stands, quarantine, evacuation and police scenes leave contextual props and clues. Stages expire without requiring a quest; summaries count observed completions, and situation heartbeats explain missing source/store prerequisites. | `EnableEncounters=true`; `events_sites.disable`. | *In-game test pending* |
| **Roadside encounters** | 16 encounter types (convoy ambushes, crashed helicopters, field hospitals, police evidence, smuggler exchanges and others) keep a target of 48 active across 202 distinct CE groups at spread-out anchors, each with weapons, medical or supply crates. | Central economy event files `hc-events.xml` and `hc-eventspawns.xml`; installed last and rolled back first. | *In-game test pending* |
| **Radio reports and Morse** | A powered PersonalRadio receives faction reports and Morse clues on the correct channel; received leads can be shared with the group. Bounded summaries report radio use and success. | `EnableLeads=true`. | *In-game test pending* |
| **Dead drops** | A finite dead-drop cache gives a place to investigate; another survivor may already have taken its contents. Three scene cache events at Kamenka, Staroye and Kumyrna use CE-created SmallProtectorCase containers and may reoffer after closure and the two-hour cooldown. | `EnableEncounters=true`. | *In-game test pending* |
| **Body stories and notes** | Owned situation deaths retain the original corpse and bind delayed story receipts without recreating inventory. Rare paper notes carry contextual leads, capped at one per scene and ten across the world. | `EnableLeads=true`. | *In-game test pending* |
| **Burn events and story chains** | Story kits and burn incidents lease existing physical stock. The event owner opens, ticks and closes the HC-41 native incident lease; live registered crashes and direct cargo ancestry bind eligible spoils without creating, cloning or refilling them. Gap: loose crash loot has no exposed engine incident-membership API. [#147](https://github.com/d-addison/hollow-country/issues/147) | `EnableEncounters=true`; `w38_incidents.disable`, `w38_rewards.disable`; `EnableStories=true`, `ArrivalSeconds=21600`, `Window=4`. | *In-game test pending* |
| **Persistent stories and escalation** | New stories arrive on a persistent six-hour schedule; both schedulers admit arrivals when occupied rows are below the window. Retained catalogs can hold 12 rows; authored catalogs remain capped at four. Capped escalation changes world pressure over time. Holdouts retry founding after a lost cache and report recovery attempts. | `EnableWorld=true`; `EnableStories=true`, `ArrivalSeconds=21600`, `Window=4`. | *In-game test pending* |
| **Event spoils** | Physical reward caches expose existing incident items. Empty receipts do not consume stock history; claimed supplies remain finite. | `EnableEncounters=true`; `w38_rewards.disable`, `w38_incidents.disable`; `W38Situations.MaxIncidents=64`, `W38Situations.MaxIncidentItems=16`. | *In-game test pending* |

### Ecology, wildlife and foraging

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Wildlife and habitats** | Native brains retain animal behaviour. The habitat overlay mixes sheep and mouflon in the existing sheep event and retains hare territory declarations. Bounded eligibility checks cover animals against infected and wolves against server AI. Seasonal territory records, positive blood-damage clues, observed carcasses and bounded animal/infected or wolf/AI contact receipts feed world memory. Observation and goals publish separate readiness; disabling world incidents reports clues unavailable while independent carcass/contact work continues. Default-on ecology adds dawn/dusk inland-shore visits, field grazing inputs, gradual herd home bias and slow native pack drift toward a pressure town that changes over days. Short native input leases and existing pack waypoints never teleport bodies; consumption transactions, target ports, CE respawn reweighting and attraction/crows remain unavailable. Native verification is pending. [#149](https://github.com/d-addison/hollow-country/issues/149) | `EnableAmbientLife=true`; `Ecology/cycle.json`: `Enabled=true`, `Animals=true`, `Infected=true`, `MaxHerds=32`, `MaxMovers=8`, `HerdDriftHours=6`, `TownShiftDays=2`, `InfectedStepSeconds=600`, `SummarySeconds=300`; `ecology_migration.disable`, `wildlife_providers.disable`; provider `Enabled=true`, `TargetPairsEnabled=true`; habitat `Enabled=true` is an install-time preference, removed by rollback. | *In-game test pending* |
| **Carcasses** | Two authored red-deer sites use permanent economy allocations to create finite carcasses out of player sight. Spent sites do not refill after restart; native corpse handling supplies the body. Creation alternates with maintenance capped at four cost-one items, with spawn/refusal summaries; contact recording respects `TargetPairsEnabled`. | `EnableAmbientLife=true`; provider `CarcassesEnabled=true`, `MaxCarcasses=2`, `CarcassClass="Animal_CervusElaphus"`; `wildlife_providers.disable`; `EnableSignsOfLife=true` for flies. | *In-game test pending* |
| **Forage and herbs** | Forage nodes retain finite claims and refill delays. Seven supplements include four native mushroom classes; all use the same finite reservation and custody path throughout the visual year. Native food and herb semantics remain intact. | `EnableForage=true`; `EnableProgression=true` controls familiarity. | *In-game test pending* |

### Atmosphere

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **Lighting and weather** | Lighting and weather-day profiles alter dusk, overcast and storms while keeping nights readable. The installer automatically generates delegated weather from pinned stock XML and retains backups. Staging on another drive moves next to the mission file; a residual cross-device move is refused with the target unchanged. | `EnableAtmosphere=true`, `EnableGrade=true`; `atmosphere.disable`; installer `--no-weather` omits weather delegation. | *In-game test pending* |
| **Colour grade** | A rebindable grade control cycles personal colour-grade intensity from 0 to 100% in 10% steps; zero restores the vanilla presentation. Server grade and presentation defaults reach clients; a saved client preference takes priority, and a zero server grade stops an active effect. | `EnableGrade=true`; `ClientPresentationMask=15`, grade bit 2. | *In-game test pending* |
| **Visual seasons** | A running-server clock changes visual seasons, presentation and forecasts without new cold penalties, and resumes after a delayed checkpoint. Native snowfall remains available. Gap: white winter ground has no supported live terrain/surface provider. [#150](https://github.com/d-addison/hollow-country/issues/150) | `EnableVisualSeasons=true`; `PhaseSeconds=604800`, `CheckpointSeconds=60`. | *In-game test pending* |
| **Autumn falling leaves** | Client-local leaf emitters sample nearby birch/beech canopies during autumn and clean up indoors, underground, when the snapshot expires or when presentation stops. | `SeasonLeaves.Enabled=true`; `season_leaves.disable`; client `HollowCountrySeasonLeaves` preference; grade 0 also stops leaves. | *In-game test pending* |
| **Cellars and darkness** | Cellar survey and presentation code identify interiors needing darker presentation; the operator-only sampler records geometry when the server profile contains `HollowCountry/measure-cellars`. Darker cellars are admitted without a measured room qualification yet. | `EnableAmbientLife=true`; `ClientPresentationMask=15` governs the available client layers; players can turn darker cellars off with the `HollowCountryDarkCellars` client preference; remove `HollowCountry/measure-cellars` to stop the sampler. | *In-game test pending* |
| **Signs of life** | Real burning fireplaces supply chimney smoke and firelight. Hidden funded holdout ignition transfers real kindling and wood and consumes a match; carcass flies provide separate clues. | `EnableSignsOfLife=true`; `ClientPresentationMask=15`, signs bit 4. | *In-game test pending* |
| **Environmental hints and sound** | Local hints and environmental sound add presentation around world activity. Forest wind uses a native sound attached to the local player so it remains audible while moving. | `EnableAmbientLife=true` controls server admission; `ClientPresentationMask=15`, hints bit 1 and ambient bit 8 control clients. | *In-game test pending* |

### Persistence, administration and performance

| Feature | Player experience and operation | Switches and tuning | Test |
| :--- | :--- | :--- | :--- |
| **World persistence** | World, settlement, camp, lead and item-transfer journals retain history. Shared saves stage work; debug snapshots encode individual rows and resume verified file promotion across bounded slices, with a configurable 300-second capture interval. Turning shared saves off refuses dependent owners at startup, including camps/claims and weather/seasons; owner barrier and shutdown saves remain. | `EnableWorld=true`; profile `performance.json`: `EnableSharedSaves=true` (registry `Performance.EnableSharedSaves`); set `false` and restart to disable shared saves. | *In-game test pending* |
| **Admin test kit** | Authorised operators use Pause for status, the map and normal world commands. HCX declares its COT script dependency and registers permission `HollowCountry.Admin`; that permission or the private HC allowlist grants access, with live revocation checks. `campvisit` and `campraid` include eligible claim-only bases; `camptier` remains hearth-only. `dormant` requests the normal fresh-body queue. | `EnableAdminMap=true`; `AdminControls.disable` opts out of world controls; `COTAuthorization.disable` opts out of COT grants. | *In-game test pending* |
| **Debug snapshot and map** | Read-only snapshots feed a browser map and the admin Map tab with counts and world/AI layers. Group pins use a rolling anonymous sweep, rather than a simultaneous world sample. Notices retain identifiable layer names with exact omission counts. Verified staged replacement cannot provide native atomic rename. | `EnableDebugSnapshot=true`, `EnableAdminMap=true`. | *In-game test pending* |
| **Admin M map** | Allowlisted admins see AI units and convoys, vehicles, crash and gas events, animals, hordes, infected packs, claimed bases, HC sites and vanilla CE points as coloured pins on the normal M map, with zoom clusters, a legend with per-layer toggles and click details. No map item is needed. Non-admins receive nothing; positions never feed the AI. | `EnableAdminMap=true`; `AdminWorld.RefreshSeconds`, `RowsPerTick`, `MaxRows`, `MaxDraw`. | *In-game test pending* |
| **Loot map** | The admin Map tab runs a bounded loot query, acknowledges it and retains the latest successful marks. | `EnableAdminMap=true`; see [debug map controls](docs/DEBUG_MAP.md). | *In-game test pending* |
| **Placement support** | HC placements and queued CE loot measure their bottom against nearby support. Corrections are capped at 3 m for props, 25 m for spawner structures and 2.5 m for CE items; unsupported placements are refused. CE processing retains at most 16,384 entries and uses four items per shared-budget slice. Native food/firework overrides that omit the CE callback remain a coverage gap. | Existing placement owners and shared work budget; `[HC Ground]` reports results. | *In-game test pending* |
| **Activity and wiring diagnostics** | Bounded summaries report alert/memory caps, search refresh, house search, interiors, siphoning, crafting, radio, vehicle recovery, salvage, decay and materializer work; missing refresh state reports `state_fault`. Activity reports distinguish ACTIVE, INERT, SILENT, NO_SIGNAL and WAITING using declared counters; readiness alone does not prove gameplay. Static wiring checks cover spawn routes, settings reads, CE indexes, zeroed rows and bundle imports. | [Activity check](docs/ACTIVITY_CHECK.md), [wiring audit](docs/WIRING_AUDIT.md); `python3 -B -m tools.release.activity_check <server.RPT>`. | *In-game test pending* |
| **Shared tick budget** | Forty consumer IDs share one work allowance, including infected LOD, bases, conflict, trade and situations. Each consumer retains a first-work starvation allowance; retained cursors resume later. | `TickIntervalMs=1000`, `MaxTickWorkItems=32`; `Performance.SliceMs=4`, `Performance.EcologyRowsPerTick=4`, `Performance.InteriorStepsPerTick=1`, `Performance.HoldoutRowsPerTick=1`; area switches disable consumers. | *In-game test pending* |

## Required mod stack

Server and clients load these published Workshop items in the order declared by the [dependency manifest](tools/setup/workshop_mods.json). Third-party mods are used as published; never repack them. The two Hollow Country addons are loaded after their dependencies. Players must subscribe to both Expansion-Licensed and Expansion-Vehicles as well as the other listed items.

| Order | Workshop item | Install folder | Why it is loaded |
| :--- | :--- | :--- | :--- |
| 1 | [Community Framework](https://steamcommunity.com/sharedfiles/filedetails/?id=1559212036) | `@CF` | Shared framework for COT and Expansion. |
| 2 | [Community Online Tools](https://steamcommunity.com/sharedfiles/filedetails/?id=1564026768) | `@COT` | Operator administration and local test support. |
| 3 | [Dabs Framework](https://steamcommunity.com/sharedfiles/filedetails/?id=2545327648) | `@DabsFramework` | Expansion UI/framework dependency. |
| 4 | [Expansion-Core](https://steamcommunity.com/sharedfiles/filedetails/?id=2291785308) | `@Expansion-Core` | Base services for Expansion addons. |
| 5 | [Expansion-Licensed](https://steamcommunity.com/sharedfiles/filedetails/?id=2116157322) | `@Expansion-Licensed` | Licensed assets required by Expansion Vehicles. |
| 6 | [Expansion-Vehicles](https://steamcommunity.com/sharedfiles/filedetails/?id=2291785437) | `@Expansion-Vehicles` | Vehicle and helicopter dependency. |
| 7 | [Expansion-AI](https://steamcommunity.com/sharedfiles/filedetails/?id=2792982069) | `@Expansion-AI` | Human AI actors, navigation and AI animations. |
| 8 | [Expansion-Navigation](https://steamcommunity.com/sharedfiles/filedetails/?id=2792984722) | `@Expansion-Navigation` | Map/GPS navigation support. |
| 9 | [SNAFU Weapons](https://steamcommunity.com/sharedfiles/filedetails/?id=2443122116) | `@SnafuWeapons` | Selected additional firearm classes. |
| 10 | [Tactical Flava](https://steamcommunity.com/sharedfiles/filedetails/?id=2646817942) | `@TacticalFlava` | Selected firearm and equipment classes. |
| 11 | [RaG_Core](https://steamcommunity.com/sharedfiles/filedetails/?id=3556131153) | `@RaG_Core` | Dependency for RaG vehicles. |
| 12 | [RaG_Immersive_Vehicles](https://steamcommunity.com/sharedfiles/filedetails/?id=3105330157) | `@RaG_Immersive_Vehicles` | Published dependency for the overhaul. |
| 13 | [Ambient Animals Pack](https://steamcommunity.com/sharedfiles/filedetails/?id=3114410963) | `@AmbientAnimals` | Ambient animal content. |
| 14 | [Survivor Animations](https://steamcommunity.com/sharedfiles/filedetails/?id=2918418331) | `@SurvivorAnimations` | Animation dependency for bicycles. |
| 15 | [DayZ-Bicycle](https://steamcommunity.com/sharedfiles/filedetails/?id=2971190303) | `@DayZ-Bicycle` | Rideable bicycles. |
| 16 | [Hollow Country](https://steamcommunity.com/sharedfiles/filedetails/?id=3841628320) | `@HollowCountry` | Core overhaul and client presentation. |
| 17 | [Hollow Country Expansion AI](https://steamcommunity.com/sharedfiles/filedetails/?id=3841637854) | `@HollowCountryExpansionAI` | Connects the world systems to Expansion AI and owns the vehicle landing incident hook. |

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
4. Start the server, inspect admission/refusal logs and join with a matching client. Keep runtime acceptance pending until the relevant feature is played, with at most one client.

Follow the [friend-server AI runbook](docs/FRIEND_SERVER_AI_RUNBOOK.md), [installation and rollback guide](docs/INSTALL_ROLLBACK.md) and [friend-server configuration](docs/FRIEND_SERVER.md) for exact commands, backups and recovery. Runtime flags do not remove installed mission content. The bundled `tools/package/overlay_remove.py --mission <mission> --overlays loot vehicles --server-stopped` rehearses receipt rollback before applying it; stop the server and retain recovery data. For inventory rollback, supply `--addon-source <source>` or `--addon-pbo <pbo>` with `--pbo-out <output>`: the helper writes an unsigned replacement, receipt and config diff. Review, sign and install that replacement separately; retain the original addon for recovery.

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
| `MaxTickWorkItems` | `32` | Shared tick work allowance; 1–256. Starvation prevention can add up to 39 cost-one items. |
| `MaxActiveHordes` | `4` | Active horde cap; 1–12. |
| `MaxActiveHordeMembers` | `160` | Active member cap; 1–256. |
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

### Infected climbing profile

Optional `gc-infected-climb.json` uses the existing `InfectedClimb.*` registry. Missing fields
retain defaults; explicit `Enabled=false` opts out. Native vault outcomes remain unverified.

| Key | Type | Default | Range |
| :--- | :--- | :--- | :--- |
| `Enabled` | bool | `true` | false / true |
| `MinHeightMetres` | float | `0.5` | 0.3–1 |
| `MaxHeightMetres` | float | `2.2` | 1.2–2.5 |
| `MaxHorizontalMetres` | float | `2.5` | 0.5–3 |
| `FacingDegrees` | float | `35` | 5–60 |
| `CooldownSeconds` | float | `6` | 2–60 |
| `Concurrent` | int | `4` | 1–8 |
| `RouteCacheSeconds` | float | `3` | 1–15 |
| `OutcomeCapSeconds` | float | `8` | 3–15 |
| `RetireAttempts` | int | `12` | 3–50 |

### Wildlife provider and habitat controls

Mission `ecology/HCWildlife-providers.json` contains the unprefixed fields below. `EnableAmbientLife=false`, provider `Enabled=false` or `wildlife_providers.disable` disables the provider. `CarcassesEnabled=false` and `TargetPairsEnabled=false` disable the respective paths independently.

| Registry key | Default | Effect |
| :--- | :--- | :--- |
| `WildlifeProviders.Version` | `1` | Configuration format. |
| `WildlifeProviders.TickMs` | `5000` | Provider interval in milliseconds. |
| `WildlifeProviders.WorkUnits` | `4` | Per-slice work allowance. |
| `WildlifeProviders.MaxCarcasses` | `2` | Permanent carcass allocation cap. |
| `WildlifeProviders.MaxPairs` | `8` | Retained target-pair cap. |
| `WildlifeProviders.MaxPairChecksPerTick` | `4` | Pair checks per provider tick. |
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
| seasons: `MaxUncheckpointedSeconds` | `300` | Maximum uncheckpointed clock time in seconds; clock progress resumes after checkpoint lag while valid seasonal consumers remain available. |
| seasons: `MaxClockDeltaSeconds` | `10` | Maximum accepted clock step in seconds. |
| stories: `Version` | `1` | Story format. |
| stories: `EnableStories` | `true` | False disables story arrivals. |
| stories: `ArrivalSeconds` | `21600` | New-story interval in seconds: six hours. |
| stories: `Window` | `4` | Story arrival window size. |

### Light mount preferences

The [light-mount config](config/hollow-country-light-mounts.json) is a legacy offline mirror. Its cross-slot fields and the [backpack manifest](mission/hollow-country/lights/backpack-mounts.json) catalogue defaults do not turn off the admitted pairs. Runtime `EnableTapedPackMounts` defaults to `true`, including when the key is absent. Pack, helmet and the 29 cross-slot weapon pairs carry *In-game test pending*.

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

### Additional registered module profiles

Registry prefixes identify owners. Unless noted, use the unprefixed key in the named JSON under the profile’s `HollowCountry/` directory. Restart after editing. Bounds below come from the checked-in registry; they are validation limits, not measured performance guarantees.

#### Performance: `performance.json`

Budgeted interior pack startup and snapshot cadence. Pack limits are cooperative; native calls cannot be interrupted.

| Registry key | Default | Allowed range |
| :--- | :--- | :--- |
| `Performance.InteriorPackOnlineMs` | `25` | 1–50 |
| `Performance.InteriorPackEmptyMs` | `150` | 1–250 |
| `Performance.InteriorPackUnitsPerTick` | `4096` | 2–65536 |
| `Performance.DebugSnapshotIntervalSeconds` | `300` | 30–3600 |

#### Convoys: `convoys.json`

One borrowed world car per run. `convoys.disable` opts out; cars must be qualified and routes bounded. Distances are metres, speeds km/h and durations seconds.

| Registry key | Default | Allowed range |
| :--- | :--- | :--- |
| `Convoys.Version` | `1` | 1–1 |
| `Convoys.MaxConvoys` | `1` | 1–1 |
| `Convoys.SeekObjects` | `256` | 1–1024 |
| `Convoys.MaxSeekScans` | `8` | 1–32 |
| `Convoys.MaxRouteNodes` | `128` | 2–256 |
| `Convoys.MaxPlanNodes` | `4000` | 2–40000 |
| `Convoys.RoadNodesPerTick` | `256` | 1–1024 |
| `Convoys.RoadNodesPerWorkUnit` | `8` | 1–64 |
| `Convoys.ExitAttempts` | `3` | 1–10 |
| `Convoys.SeekMeters` | `60.0` | 5–200 |
| `Convoys.SeekSeconds` | `15.0` | 1–300 |
| `Convoys.PlayerClaimMeters` | `150.0` | 50–1000 |
| `Convoys.BoardMeters` | `4.0` | 1–10 |
| `Convoys.ApproachSeconds` | `120.0` | 10–600 |
| `Convoys.BoardSeconds` | `60.0` | 5–300 |
| `Convoys.ExitSeconds` | `10.0` | 1–120 |
| `Convoys.NodeReachMeters` | `8.0` | 1–50 |
| `Convoys.ArriveMeters` | `20.0` | 1–100 |
| `Convoys.DismountMeters` | `120.0` | 0–500 |
| `Convoys.MaxApproachMeters` | `60.0` | 5–200 |
| `Convoys.MinDriveMeters` | `150.0` | 50–2000 |
| `Convoys.MaxDriveMeters` | `1500.0` | 150–5000 |
| `Convoys.DetourMeters` | `400.0` | 0–2000 |
| `Convoys.CruiseKmh` | `25.0` | 5–60 |
| `Convoys.TurnKmh` | `10.0` | 3–60 |
| `Convoys.SpeedBandKmh` | `3.0` | 1–20 |
| `Convoys.TurnRadians` | `0.5` | 0.05–1.6 |
| `Convoys.SteerGain` | `2.0` | 0.1–8 |
| `Convoys.Throttle` | `0.6` | 0.05–1 |
| `Convoys.BrakeStrength` | `0.6` | 0.05–1 |
| `Convoys.StopKmh` | `2.0` | 0.5–10 |
| `Convoys.StopSeconds` | `8.0` | 1–60 |
| `Convoys.StallMeters` | `3.0` | 0.5–50 |
| `Convoys.StallSeconds` | `15.0` | 3–120 |
| `Convoys.MaxDriveSeconds` | `600.0` | 30–1800 |

#### HearthFires: `hearth-fires.json`

Real fireplace observation and funded ignition. `Enabled=false` opts out. Distances are metres; `AttemptSeconds` bounds retry memory.

| Registry key | Default | Allowed range |
| :--- | :--- | :--- |
| `HearthFires.Enabled` | `true` | 0–1 |
| `HearthFires.MaxHearths` | `64` | 1–256 |
| `HearthFires.MaxObjects` | `128` | 1–512 |
| `HearthFires.MaxInventory` | `64` | 1–256 |
| `HearthFires.HearthsPerTick` | `4` | 1–32 |
| `HearthFires.HousesPerScan` | `16` | 1–64 |
| `HearthFires.MaxLit` | `4` | 1–24 |
| `HearthFires.MaxSmoke` | `2` | 1–24 |
| `HearthFires.QueryRadius` | `30` | 1–100 |
| `HearthFires.AnchorTolerance` | `0.35` | 0.05–1 |
| `HearthFires.ActorRange` | `3` | 0.5–5 |
| `HearthFires.ObserverRadius` | `500` | 100–2000 |
| `HearthFires.AttemptSeconds` | `60` | 10–3600 |

#### PerceptionRing: `settings.json`

This is a nested shared settings object. Spawn exclusion is max(view, hearing) plus margin, followed by the configured band; defaults give 1100–1500 metres.

| Registry key | Default | Allowed range |
| :--- | :--- | :--- |
| `PerceptionRing.ViewRangeMeters` | `1000` | 100–5000 |
| `PerceptionRing.HearingRangeMeters` | `1000` | 100–5000 |
| `PerceptionRing.SpawnMarginMeters` | `100` | 1–500 |
| `PerceptionRing.SpawnBandMeters` | `400` | 1–2000 |

#### Helicopters: `helicopters.json`

`helicopters.disable` opts out. The world cap reports population pressure; it does not delete player aircraft. Ambient AI overflight remains pending a flight port. Additional unregistered selector fields are `ProviderPatch="DayZExpansion_Vehicles_Scripts"` and `VehicleClasses=["Expansion_Helicopter"]`.

| Registry key | Default | Allowed range |
| :--- | :--- | :--- |
| `Helicopters.Version` | `1` | 1–1 |
| `Helicopters.MaxTracked` | `16` | 1–64 |
| `Helicopters.WorldCap` | `4` | 0–64 |
| `Helicopters.MaxTypeCache` | `128` | 1–512 |
| `Helicopters.SpawnFuelMaxFraction` | `0.1` | 0–0.35 |

#### Radio: `radio.json`

Optional radio tuning; receiver-frequency membership remains unobserved.

| Registry key | Default | Allowed range |
| :--- | :--- | :--- |
| `Radio.ChannelCountLimit` | `64` | 1–64 |

#### AISites: `expansion-ai-sites.json`

Fields live inside `Policy`. Zero role timers inherit `AIRespawnSeconds`; zero activation scale selects native site scale. `ai-respawn.disable` opts out of fresh replacement.

| Registry key | Default | Allowed range |
| :--- | :--- | :--- |
| `AISites.SchemaVersion` | `1` | 1–1 |
| `AISites.MinPlayerDistance` | `200` | 200–7500 |
| `AISites.LineOfSightRange` | `1000` | 200–1500 |
| `AISites.MaxLegLength` | `400` | 50–600 |
| `AISites.CacheClearRadius` | `300` | 100–1000 |
| `AISites.AIRespawnSeconds` | `900` | 0–604800 |
| `AISites.PatrolRespawnSeconds` | `0` | 0–604800 |
| `AISites.HoldoutRespawnSeconds` | `0` | 0–604800 |
| `AISites.MilitaryRespawnSeconds` | `0` | 0–604800 |
| `AISites.MemberReplaceSeconds` | `600` | 0–604800 |
| `AISites.RaidCooldownFloorSeconds` | `0` | 0–604800 |
| `AISites.ActivationRadiusScale` | `0` | 0–2.0 |

#### AICamps: `ai-camp-policy.json`

Finite founding/reserve allocations and camp routine timing. Existing durable clocks migrate without replaying stock; explicit operator timing is retained.

| Registry key | Default | Allowed range |
| :--- | :--- | :--- |
| `AICamps.FoundingStock` | `48` | 1–256 |
| `AICamps.FoundingPopulation` | `12` | 1–128 |
| `AICamps.CampAllocation` | `24` | 1–256 |
| `AICamps.ReserveCap` | `144` | 1–256 |
| `AICamps.ReserveRegenPerDay` | `12` | 1–256 |
| `AICamps.ReserveDaySeconds` | `86400` | 3600–604800 |
| `AICamps.ReservePopulationCap` | `36` | 1–128 |
| `AICamps.ReservePopulationRegenPerDay` | `3` | 1–128 |
| `AICamps.BivouacCost` | `1` | 1–256 |
| `AICamps.HouseholdCost` | `2` | 1–256 |
| `AICamps.StableCost` | `4` | 1–256 |
| `AICamps.HubCost` | `8` | 1–256 |
| `AICamps.GrowthSeconds` | `3600` | 60–604800 |
| `AICamps.UpkeepSeconds` | `86400` | 3600–604800 |
| `AICamps.RaidLockoutSeconds` | `1800` | 60–604800 |
| `AICamps.RoleSeconds` | `120` | 60–3600 |
| `AICamps.RoutineRangeMeters` | `30` | 1–30 |
| `AICamps.ArrivalToleranceMeters` | `1` | 1–1 |

#### SeasonLeaves: `auditleaves_settings.json`

Client-local profile, with a packaged mission template. `Enabled=false`, `season_leaves.disable` or client profile key `HollowCountrySeasonLeaves=0` opts out. Grade at zero stops emitters too.

| Registry key | Default | Allowed range |
| :--- | :--- | :--- |
| `SeasonLeaves.Enabled` | `true` | 0–1 |
| `SeasonLeaves.SampleSeconds` | `0.5` | 0.1–2 |
| `SeasonLeaves.QuerySeconds` | `10` | 2–120 |
| `SeasonLeaves.QueryRadius` | `12` | 2–30 |
| `SeasonLeaves.MaxObjects` | `64` | 1–256 |
| `SeasonLeaves.LifetimeSeconds` | `3` | 0.5–10 |
| `SeasonLeaves.MinTreeHeight` | `3` | 1–10 |
| `SeasonLeaves.MaxTreeHeight` | `40` | 10–60 |
| `SeasonLeaves.CanopyFraction` | `0.75` | 0.25–1 |

### Mission policy additions

These are authored mission inputs, not fields in the shared settings file. Preserve finite stock and restart receipts when changing them. Scene/route arrays hold authored data; replacing them does not establish native access or geometry.

#### [picker-routes.json](mission/hollow-country/ai/picker-routes.json)

Need-driven runs; `scavenge_runs.disable` opts out. Distances are metres and durations seconds. House goods use separate receipts from the primary trip item; deposit occurs one item per funded tick after observed arrival.

| Key | Default |
| :--- | :--- |
| `RunMinMembers` | `2` |
| `RunMaxMembers` | `6` |
| `RunMaxHousesPerRun` | `3` |
| `RunMaxCarriedHouseGoods` | `3` |
| `RunMaxHouseAttempts` | `6` |
| `RunMaxHouseCandidates` | `8` |
| `RunHouseSearchRadiusMeters` | `120.0` |
| `RunHouseSearchSeconds` | `6.0` |
| `RunHouseWalkSeconds` | `90.0` |
| `RunNeedStashItems` | `8` |
| `RunNeedPercentSpring` | `100` |
| `RunNeedPercentSummer` | `80` |
| `RunNeedPercentAutumn` | `130` |
| `RunNeedPercentWinter` | `160` |
| `RunNeedRecheckSeconds` | `600` |
| `RunDangerHeatAvoid` | `0.35` |
| `RunDangerClueSeconds` | `3600` |
| `RunDangerMaxClues` | `16` |
| `RunCombatAbortSeconds` | `20` |
| `RunMaxPartiesPerCamp` | `1` |
| `RunMaxActiveRuns` | `1` |

#### [variety-runtime.json](mission/hollow-country/infected/variety-runtime.json)

Fresh bodies, including corpses, share `MaxFreshBodies`. `MaxPosed=0` stops new posed holds; `PosedFreshEvery=0` opts out of posed selection, `StandingRiserEvery=0` opts out of standing selection and `EnableMigration=false` stops corridor movement. `infected_poses.disable`, `infected_variety.disable` are independent opt-outs.

| Key | Default |
| :--- | :--- |
| `SchemaVersion` | `1` |
| `MaxSites` | `64` |
| `MaxFreshBodies` | `3` |
| `PosedFreshEvery` | `3` |
| `MaxPosed` | `24` |
| `GroupMembers` | `3` |
| `ContextRange` | `40` |
| `InterestRange` | `1000` |
| `RequestRange` | `1500` |
| `MinSpawnDistance` | `120` |
| `VisibilityRange` | `1100` |
| `MaxObservers` | `8` |
| `GroupSpacing` | `4` |
| `AutomaticIntervalSeconds` | `600` |
| `StandingRiserEvery` | `2` |
| `EnableMigration` | `true` |
| `CorridorRangeMetres` | `80` |
| `MaxMigrationMetres` | `480` |
| `MigrationLifetimeSeconds` | `60` |
| `MigrationScanSeconds` | `5` |

#### [HCWildlife-providers.json](mission/hollow-country/ecology/HCWildlife-providers.json)

Seasonal route records use the authoritative season phase. Clues require world incidents; missing dependencies degrade observation while carcass/contact work remains independent. Animal goal requests are admitted unverified because no native goal/feeding port exists.

| Key | Default |
| :--- | :--- |
| `SeasonalRoutesEnabled` | `true` |
| `CluesEnabled` | `true` |
| `InteractionObservationEnabled` | `true` |
| `ClueLifetimeSeconds` | `300` |

#### [car-repair.json](mission/hollow-country/ai/car-repair.json)

Real parts and compatible tools only; `Enabled=false` opts out. Walking, custody, work range and car claims are rechecked before commits.

| Key | Default |
| :--- | :--- |
| `Version` | `1` |
| `Enabled` | `true` |
| `SearchRadiusMeters` | `600.0` |
| `MaxActiveGroups` | `2` |
| `MaxKnownCars` | `512` |
| `CooldownSeconds` | `900` |
| `ClaimSeconds` | `1800` |
| `WorkSecondsPerStep` | `20` |
| `WorkRangeMeters` | `4.0` |
| `StashRangeMeters` | `15.0` |
| `WalkMetersPerSecond` | `1.6` |
| `WalkSlackSeconds` | `120` |
| `MaxAttemptsPerCar` | `3` |
| `MaxScanItems` | `96` |
| `StepSeconds` | `2` |
| `MaxRouteNodes` | `64` |
| `MechanicToolClasses` | `["Wrench", "LugWrench"]` |

#### [auditshelter_scenes.json](mission/hollow-country/travel/auditshelter_scenes.json)

Five loaded regional exterior scenes plus 69 extra authored scene candidates; the extras need shared catalog registration before placement. `Enabled=false` opts out. Runtime visibility, access and rain cover remain pending.

| Key | Default |
| :--- | :--- |
| `SchemaVersion` | `1` |
| `Enabled` | `true` |
| `ObserverDistance` | `1100` |
| `WorkUnits` | `24` |
| `BoundsToleranceSquared` | `0.04` |

#### [floor-policy.json](mission/hollow-country/loot-points/floor-policy.json)

Install-time floor/shelf classification. `enabled=false` omits this policy on generation; installed overlays require receipt rollback. Compatible capacity transfers retain group bounds and unchanged geometry.

| Key | Default |
| :--- | :--- |
| `enabled` | `true` |
| `floor_categories` | `["clothes"]` |
| `floor_classes` | `["Paper"]` |
| `floor_class_patterns` | `[]` |
| `shelf_categories` | `["tools", "containers", "food", "books"]` |
| `floor_tag` | `"floor"` |
| `shelf_tag` | `"shelves"` |
| `floor_container_names` | `["lootFloor", "lootGround", "lootHCFloor"]` |
| `height_checked_container_names` | `["loot"]` |
| `extra_floor_container_names` | `["lootHCFloor"]` |
| `floor_band_m` | `0.75` |
| `capacity` | `{"enabled": true, "max_container_lootmax": 12, "preserve_tolerance": 0.1}` |

### Camp, world, search and actor limits

These optional profiles live under `$profile:HollowCountry/`. Keys below are
unprefixed inside each profile; the registry uses the section prefix. Restart to
reload. Missing fields keep declared defaults and invalid values report refusal
or restore defaults through the owning loader. Limits do not grant readiness:
`HCGetOperationalStatus` / `HCOperationalStatus.HCPublish` report actual provider
and store state. Features remain on by default with the opt-outs listed here.

#### CampGroup: `camp-group-config.json`

Camp scans/saves, map pins, trails, team-ping history and debug slices; feature opt-outs remain EnableCamps, EnableGroups and EnableTeamPing.

| Key | Default | Allowed range |
| :--- | :--- | :--- |
| `CampFireCandidates` | `128` | 1–128 |
| `CampPlayers` | `32` | 1–32 |
| `CampTickSeconds` | `5` | 1–60 |
| `CampScanSeconds` | `600` | 30–3600 |
| `CampProbeScanSeconds` | `30` | 5–600 |
| `CampSaveSeconds` | `600` | 60–3600 |
| `CampBindDistanceSq` | `145` | 1–145 |
| `PinLimit` | `64` | 1–64 |
| `LeadPins` | `5` | 1–5 |
| `TrailPins` | `48` | 1–48 |
| `ShelterQueries` | `20` | 1–20 |
| `TrailRadiusMeters` | `40` | 1–40 |
| `PinRefreshSeconds` | `60` | 5–600 |
| `PinLogSeconds` | `600` | 60–3600 |
| `PinLogGroups` | `1` | 1–4 |
| `TeamPingRows` | `90` | 1–90 |
| `TeamPingSeconds` | `60` | 10–60 |
| `TeamPingCooldownSeconds` | `10` | 1–60 |
| `TeamPingPruneRows` | `32` | 1–32 |
| `TeamPingLogSeconds` | `60` | 10–600 |
| `TeamPingRadiusMeters` | `5` | 1–5 |
| `DebugGroups` | `1` | 1–4 |
| `DebugPins` | `32` | 1–32 |

#### WorldRuntime: `world-runtime.json`

Shared save scheduling and retained world facts/leads/scenes; EnableSharedSaves=false opts out of shared saves. Lower retention limits preserve loaded custody and fixed schema ceilings.

| Key | Default | Allowed range |
| :--- | :--- | :--- |
| `SaveJobLimit` | `32` | 1–32 |
| `SaveScanLimit` | `32` | 1–32 |
| `SaveFirstDelaySeconds` | `30` | 0–3600 |
| `SaveStaggerSeconds` | `1` | 0–60 |
| `SaveCoalesceSeconds` | `60` | 1–3600 |
| `SaveFlushStageLimit` | `64` | 1–64 |
| `SaveScanSliceMs` | `4` | 1–4 |
| `BudgetDeferredLogSeconds` | `600` | 1–3600 |
| `MaxFacts` | `256` | 1–256 |
| `MaxSiteMemories` | `256` | 1–256 |
| `MaxLeads` | `64` | 1–64 |
| `MaxGroupLeads` | `5` | 1–5 |
| `MaxScenes` | `8` | 1–8 |
| `MaxNotes` | `10` | 1–10 |
| `MaxTheftRows` | `1024` | 1–1024 |
| `MaxTheftPerCamp` | `32` | 1–32 |
| `MaxSalvage` | `64` | 1–64 |
| `FactLifetimeSeconds` | `604800` | 1–604800 |

#### SearchLimits: `search-limits.json`

Search retries, refresh records and journal maintenance; EnableSearch=false opts out. Work alternates within the shared tick budget.

| Key | Default | Allowed range |
| :--- | :--- | :--- |
| `RetryDelayMs` | `10000` | 1000–60000 |
| `RetryAttempts` | `3` | 1–12 |
| `RefreshRecordsPerMinute` | `32` | 1–32 |
| `RefreshMaxRecords` | `4096` | 1–4096 |
| `RefreshMinSeconds` | `172800` | 60–2592000 |
| `RefreshJitterSeconds` | `172800` | 0–2592000 |
| `JournalMaxEntries` | `4096` | 1–4096 |
| `RetirementRecentEntries` | `2048` | 1–2048 |
| `CompactRowsPerMinute` | `32` | 1–32 |
| `LegacyFilesPerMinute` | `32` | 1–32 |

#### SignsOfLife: `signs-of-life.json`

Firelight, chimney and fly scan limits; EnableSignsOfLife=false opts out.

| Key | Default | Allowed range |
| :--- | :--- | :--- |
| `MaxFlies` | `6` | 0–6 |
| `MaxObjects` | `512` | 1–512 |
| `MaxForceLit` | `24` | 0–24 |
| `HouseRadius` | `125` | 1–125 |
| `FlyRadius` | `25` | 1–25 |
| `ScanSeconds` | `10` | 10–3600 |
| `ColdC` | `10` | -40–40 |
| `SummarySeconds` | `60` | 60–3600 |
| `SummaryAreas` | `6` | 1–6 |
| `SnapshotPlayers` | `90` | 1–90 |

#### LeatherTailoring: `leather-tailoring.json`

Recipe ingredients and duration; Enabled=false opts out. Deploy matching profiles to clients before recipe registration.

| Key | Default | Allowed range |
| :--- | :--- | :--- |
| `Enabled` | `true` | boolean |
| `PantsPanels` | `3` | 2–8 |
| `VestPanels` | `4` | 3–8 |
| `KitUnits` | `10` | 1–100 |
| `AnimationUnits` | `2` | 1–10 |

#### Signals: `signals.json`

Physical gesture cooldown and bounded notices; Enabled=false opts out. No dialogue, trading or quest flow.

| Key | Default | Allowed range |
| :--- | :--- | :--- |
| `Enabled` | `true` | boolean |
| `CooldownMs` | `30000` | 1000–3600000 |
| `MaxNotices` | `128` | 1–128 |

#### BodyStories: `body-stories.json`

Original owned corpse receipts and bounded maintenance; EnableLeads=false opts out.

| Key | Default | Allowed range |
| :--- | :--- | :--- |
| `MaxBodies` | `3` | 1–3 |
| `MaxActiveTraces` | `10` | 1–10 |
| `MaxSceneTraces` | `3` | 1–3 |
| `MaintenanceSeconds` | `20` | 1–300 |

#### ActorReach: `gc-actors-reach.json`

Bounded infected reach evaluation; Enabled=false opts out. Native capability policies still govern individual actions.

| Key | Default | Allowed range |
| :--- | :--- | :--- |
| `Enabled` | `true` | boolean |
| `Slots` | `16` | 1–16 |
| `EvaluationsPerTick` | `6` | 1–6 |
| `Vehicles` | `8` | 1–8 |
| `ContextSeconds` | `10` | 1–180 |
| `MaxLifetimeSeconds` | `180` | 1–180 |
| `InitialVaultDelaySeconds` | `2` | 0.1–15 |
| `VehicleContactMetres` | `1.9` | 0.1–1.9 |
| `VaultContactMetres` | `1.2` | 0.1–1.2 |
| `NavmeshSampleMetres` | `0.5` | 0.05–0.5 |
| `NavmeshHeightToleranceMetres` | `0.7` | 0.05–0.7 |
| `VaultOutcomeSeconds` | `3` | 1–10 |
| `VehicleHitSeconds` | `2` | 2–60 |
| `VehicleMemorySeconds` | `60` | 2–60 |
| `SummarySeconds` | `60` | 1–600 |
| `WorkSliceMilliseconds` | `4` | 0.1–4 |
| `DoorNavmeshCost` | `1000` | 1–1000 |

#### ActorDefence: `gc-actors-defence.json`

Bounded AI self-defence, perception memory and grudge duration; Enabled=false opts out.

| Key | Default | Allowed range |
| :--- | :--- | :--- |
| `Enabled` | `true` | boolean |
| `GRUDGE_CAP` | `64` | 1–64 |
| `SHOT_WINDOW_CAP` | `6` | 1–6 |
| `SHOT_SPACING_MS` | `750` | 750–60000 |
| `LOS_MEMORY_MS` | `15000` | 1–15000 |
| `SEED_WINDOW_MS` | `20000` | 1–20000 |
| `RESCUE_WINDOW_MS` | `30000` | 1–30000 |
| `RAYCASTS_PER_SHOT` | `4` | 1–4 |
| `INFECTED_RADIUS` | `25.0` | 1–25 |
| `PASS_RADIUS` | `4.0` | 0.1–4 |
| `PASS_REACH` | `200.0` | 1–200 |
| `PASS_MARGIN` | `2.0` | 0.1–2 |
| `CLOSE_RADIUS` | `12.0` | 0.1–12 |
| `FIGHT_THREAT` | `0.6` | 0.1–0.6 |
| `ORIGIN_REACH` | `150.0` | 1–150 |
| `HitHoldMs` | `240000` | 1–240000 |
| `KillHoldMs` | `300000` | 1–300000 |
| `MissHoldMs` | `90000` | 1–90000 |

### Optional gameplay and presentation tuning

The following profiles tune their existing owners. Values are `key=default`; nested names belong to the named object. Distances use the units in the key or owning policy, durations are seconds unless named `Ms`, and hours use the native clock. The linked definitions contain coupled bounds (for example vault heights, weather windows and snapshot heartbeat/TTL). Missing keys retain defaults; invalid tuning is defaulted or refused by its owner with a diagnostic. Client profiles are local to each client.

<details>
<summary>Infected/config.json: Doors</summary>

[Validation](mods/HollowCountry/scripts/4_World/Infected/c1InfectedTunables.c)

| Key | Default |
| :--- | :--- |
| `OpenMinSeconds` | `6` |
| `OpenMaxSeconds` | `10` |
| `HitsMin` | `4` |
| `HitsMax` | `6` |
| `HitInterval` | `1.5` |
| `Grace` | `3.0` |
| `MaxStep` | `2.0` |
| `Cooldown` | `45.0` |
| `WatchSeconds` | `10.0` |
| `WatchRadius` | `8.0` |
| `NearRadius` | `2.5` |
| `DoorRadius` | `2.0` |

</details>

<details>
<summary>Infected/config.json: Reach</summary>

[Validation](mods/HollowCountry/scripts/4_World/Infected/c1InfectedTunables.c)

| Key | Default |
| :--- | :--- |
| `ElevatedMin` | `0.8` |
| `ElevatedMax` | `2.3` |
| `VaultMin` | `0.8` |
| `VaultMax` | `2.0` |
| `VaultLow` | `1.1` |
| `VaultHigh` | `1.6` |
| `VaultConcurrent` | `4` |
| `VaultCooldown` | `15.0` |
| `UnreachableQuietSeconds` | `6.0` |
| `VaultHorizontal` | `1.6` |
| `VaultFacing` | `25.0` |

</details>

<details>
<summary>Infected/config.json: Vision</summary>

[Validation](mods/HollowCountry/scripts/4_World/Infected/c1InfectedTunables.c)

| Key | Default |
| :--- | :--- |
| `FactorMin` | `0.6` |
| `FactorMax` | `1.3` |
| `DarkFactor` | `0.75` |
| `LightDay` | `1.1` |
| `LightNight` | `1.5` |
| `LightNightIncrement` | `0.4` |
| `DuskStart` | `19.0` |
| `NightStart` | `21.0` |
| `DawnStart` | `5.0` |
| `DawnEnd` | `7.0` |

</details>

<details>
<summary>Infected/config.json: Memory</summary>

[Validation](mods/HollowCountry/scripts/4_World/Infected/c1InfectedTunables.c)

| Key | Default |
| :--- | :--- |
| `DecaySeconds` | `259200.0` |
| `CohortBase` | `3` |
| `CohortHeat` | `3` |
| `ResponseBase` | `6` |
| `ResponseHeat` | `6` |
| `CellMetres` | `500.0` |
| `LoudnessGain` | `0.35` |
| `SuppressedLoudness` | `0.15` |

</details>

<details>
<summary>Infected/config.json: Chain</summary>

[Validation](mods/HollowCountry/scripts/4_World/Infected/c1InfectedTunables.c)

| Key | Default |
| :--- | :--- |
| `ClueTTL` | `30.0` |
| `MinStrength` | `0.2` |
| `MaxHops` | `2` |
| `Attenuation` | `0.5` |
| `EmissionAge` | `2.0` |
| `TrackedCap` | `24` |
| `RootCap` | `8` |

</details>

<details>
<summary>Infected/config.json: Navigation</summary>

[Validation](mods/HollowCountry/scripts/4_World/Infected/c1InfectedTunables.c)

| Key | Default |
| :--- | :--- |
| `SampleRadius` | `1.5` |
| `VerticalTolerance` | `1.5` |
| `WaypointRadius` | `1.5` |
| `SearchRing` | `24.0` |

</details>

<details>
<summary>Infected/config.json: LevelOfDetail</summary>

[Validation](mods/HollowCountry/scripts/4_World/Infected/c1InfectedTunables.c)

| Key | Default |
| :--- | :--- |
| `ObserverSpeed` | `60.0` |
| `SampleAge` | `3.0` |
| `HitQuiet` | `120.0` |
| `PosedFallback` | `12` |

</details>

<details>
<summary>infected-variety.json: GroupScaling</summary>

[Validation](mods/HollowCountry/scripts/4_World/Infected/c1InfectedTunables.c)

| Key | Default |
| :--- | :--- |
| `Solo` | `0.6` |
| `DuoIncrement` | `0.2` |
| `Trio` | `1.0` |
| `PartyIncrement` | `0.1` |
| `LargeParty` | `1.3` |

</details>

<details>
<summary>infected-variety.json: Variety</summary>

[Validation](mods/HollowCountry/scripts/4_World/Infected/c1InfectedTunables.c)

| Key | Default |
| :--- | :--- |
| `DormantShare` | `0.6666666666666666` |
| `RunnerDay` | `0.08` |
| `RunnerNightIncrement` | `0.07` |
| `DormantBase` | `0.55` |
| `DormantNightReduction` | `0.25` |
| `DormantRainReduction` | `0.15` |
| `DormantMin` | `0.1` |
| `DormantMax` | `0.6` |
| `WakeBase` | `0.8` |
| `WakeNightIncrement` | `0.2` |
| `WakeRainReduction` | `0.3` |
| `WakeMin` | `0.4` |
| `WakeMax` | `1.0` |

</details>

<details>
<summary>Infected/config.json</summary>

[Validation](mods/HollowCountry/scripts/4_World/Infected/HCInfectedState.c)

| Key | Default |
| :--- | :--- |
| `HordeCooldownSeconds` | `180` |

</details>

<details>
<summary>seasons.json</summary>

[Validation](mods/HollowCountry/scripts/3_Game/Atmosphere/c2_AtmosConfig.c)

| Key | Default |
| :--- | :--- |
| `SNAPSHOT_TTL_SECONDS` | `90.0` |
| `SNAPSHOT_HEARTBEAT_SECONDS` | `30.0` |
| `FOG_BLEND_HOURS` | `0.5` |
| `BASELINE_FOG` | `0.04` |
| `SUMMER_RAIN_SCALE` | `0.5` |
| `AUTUMN_RAIN_MIN` | `0.45` |
| `AUTUMN_FOG_MIN` | `0.18` |
| `WINTER_FOG_MIN` | `0.08` |
| `AUTUMN_CLOUD_MIN` | `0.75` |
| `WINTER_CLOUD_MIN` | `0.8` |
| `SNOW_CLOUD_THRESHOLD` | `0.6` |
| `WINTER_SNOWFALL` | `0.55` |
| `SPRING_GRADE` | `0.06` |
| `SUMMER_GRADE` | `0.04` |
| `AUTUMN_GRADE` | `0.14` |
| `WINTER_GRADE` | `0.12` |
| `AutumnRainCloudThreshold` | `0.65` |
| `FogDayStartHour` | `5` |
| `FogDayEndHour` | `20` |

</details>

<details>
<summary>atmosphere-presentation.json (client)</summary>

[Validation](mods/HollowCountry/scripts/3_Game/Atmosphere/c2_AtmosConfig.c)

| Key | Default |
| :--- | :--- |
| `GradeDefaultPercent` | `60` |
| `GradeDawnHour` | `8` |
| `GradeDawnBlendHours` | `2` |
| `GradeDuskHour` | `18` |
| `GradeDuskBlendHours` | `4` |
| `GradeCloudWeight` | `0.45` |
| `GradeFogWeight` | `0.25` |
| `GradeRainWeight` | `0.3` |
| `GradeDesaturation` | `0.12` |
| `GradeDampDesaturation` | `0.1` |
| `GradeTintRed` | `0.025` |
| `GradeDampTintRed` | `0.015` |
| `GradeTintGreen` | `0.005` |
| `GradeTintBlue` | `0.012` |
| `GradeContrast` | `0.025` |
| `GradeDampContrast` | `0.015` |
| `GradeVignette` | `0.025` |
| `GradeDampVignette` | `0.025` |
| `LightDawnStart` | `5` |
| `LightDawnEnd` | `6` |
| `LightDuskStart` | `19` |
| `LightDuskEnd` | `20` |
| `DuskStart` | `16` |
| `DuskPeak` | `18` |
| `DuskEnd` | `20` |
| `DuskColdHour` | `18.5` |
| `CloudThreshold` | `0.55` |
| `FogCloudWeight` | `0.15` |
| `StormThreshold` | `0.65` |
| `StormBand` | `0.15` |
| `CloudBand` | `0.25` |
| `StormWeightBase` | `0.12` |
| `StormWeightGain` | `0.38` |
| `CloudWeight` | `0.35` |
| `DuskWeight` | `0.3` |
| `BlendStep` | `0.1` |
| `HowlGapMinSeconds` | `600` |
| `HowlGapMaxSeconds` | `900` |
| `LayerGapMinSeconds` | `180` |
| `LayerGapMaxSeconds` | `300` |
| `SoundStartupSeconds` | `45` |
| `SoundVolume` | `0.2` |

</details>

<details>
<summary>weather.json</summary>

[Validation](mods/HollowCountry/scripts/4_World/Weather/HCWeatherConfig.c)

| Key | Default |
| :--- | :--- |
| `BadDayBuckets` | `1` |
| `FogMorningBuckets` | `3` |
| `FogStartHour` | `5` |
| `FogPeakHour` | `7` |
| `FogEndHour` | `9` |
| `FogBaseline` | `0.04` |
| `FogMorningLevel` | `0.6` |
| `NightStartHour` | `20` |
| `NightEndHour` | `5` |
| `NightCloudCap` | `0.55` |
| `StormCloud` | `0.95` |
| `WetCloud` | `0.72` |
| `RainCloudThreshold` | `0.65` |
| `StormCloudThreshold` | `0.85` |
| `StormDurationSeconds` | `90.0` |
| `RainStopSeconds` | `90.0` |
| `MorningFogLift` | `0.2` |
| `CalmCloud` | `0.25` |
| `PlainCloud` | `0.35` |
| `BadCloud` | `0.98` |
| `BadRain` | `0.9` |
| `StormRain` | `0.85` |
| `WetRain` | `0.25` |
| `CalmWind` | `2` |
| `NightWind` | `4` |
| `BadWind` | `16` |
| `StormWind` | `14` |
| `WetWind` | `8` |
| `PlainWind` | `4` |
| `CycleSeconds` | `7200` |
| `BadStormStartSeconds` | `1800` |
| `WetStartSeconds` | `2700` |
| `StormStartSeconds` | `3600` |
| `StormEndSeconds` | `5400` |
| `BadWindCloudThreshold` | `0.65` |
| `WetEndRainThreshold` | `0.02` |
| `CalmHours` | `3` |
| `StormWindDirection` | `0.8` |
| `PlainWindDirection` | `-1.2` |
| `DistanceBase` | `0.015` |
| `DistanceMorningLift` | `0.04` |
| `DistanceCloudLift` | `0.01` |
| `HeightBase` | `50` |
| `HeightMorningLift` | `40` |
| `WindDampingDivisor` | `20` |

</details>

<details>
<summary>forage-config.json</summary>

[Validation](mods/HollowCountry/scripts/4_World/Forage/HCForage.c)

| Key | Default |
| :--- | :--- |
| `CellCap` | `3` |
| `TotalCap` | `40` |
| `RecordCap` | `40` |
| `LiveCap` | `40` |
| `DelaySeconds` | `1800` |
| `FamiliarityReductionSeconds` | `180` |
| `SpotOffsetX` | `45` |
| `SpotOffsetZ` | `155` |
| `SpotSpacing` | `55` |
| `FloraStartMonth` | `6` |
| `FloraEndMonth` | `11` |
| `BerryStartMonth` | `6` |
| `BerryEndMonth` | `8` |
| `MushroomStartMonth` | `9` |
| `MushroomEndMonth` | `11` |
| `FloraRollSides` | `10` |

</details>

<details>
<summary>vehicle-flip.json</summary>

[Validation](mods/HollowCountry/scripts/4_World/Vehicles/HCVehicleFlip.c)

| Key | Default |
| :--- | :--- |
| `ReachMeters` | `5.0` |
| `Helpers` | `3` |
| `TorqueMassScale` | `0.4` |
| `LiftMassScale` | `0.1` |
| `Pulses` | `3` |

</details>

<details>
<summary>wreck-salvage-config.json</summary>

[Validation](mods/HollowCountry/scripts/4_World/Vehicles/HCWreckSalvage.c)

| Key | Default |
| :--- | :--- |
| `WheelWeight` | `2` |
| `SparkPlugWeight` | `20` |
| `BatteryWeight` | `15` |
| `RadiatorWeight` | `15` |
| `HeadlightWeight` | `20` |
| `ScrapWeight` | `28` |
| `BudgetMinimum` | `1` |
| `BudgetRollSides` | `3` |
| `ActionSeconds` | `8.0` |
| `ReachMeters` | `2.0` |
| `CompletionGraceMs` | `500` |

</details>

<details>
<summary>fuel-siphon.json</summary>

[Validation](mods/HollowCountry/scripts/4_World/Actions/c3FuelSiphonConfig.c)

| Key | Default |
| :--- | :--- |
| `ReachMeters` | `2.0` |
| `ContactToleranceMeters` | `0.5` |
| `MaxSessions` | `96` |
| `LeaseMs` | `10000` |
| `DiagnosticStepSeconds` | `1.0` |
| `RepeatSeconds` | `0.5` |

</details>

<details>
<summary>signals.json</summary>

[Validation](mods/HollowCountry/scripts/4_World/Actions/HCActionAskForNews.c)

| Key | Default |
| :--- | :--- |
| `CooldownMs` | `30000` |

</details>

<details>
<summary>progression-config.json</summary>

[Validation](mods/HollowCountry/scripts/4_World/Progression/HCProgression.c)

| Key | Default |
| :--- | :--- |
| `GainPeriodSeconds` | `60` |
| `SavePeriodSeconds` | `60` |

</details>

<details>
<summary>radio.json</summary>

[Validation](mods/HollowCountry/scripts/4_World/Leads/HCRadioChatter.c)

| Key | Default |
| :--- | :--- |
| `ReportRangeMetres` | `1000.0` |
| `MaxListeners` | `32` |
| `ChannelCountLimit` | `64` |
| `LocalsMHz` | `87.8` |
| `VolunteersMHz` | `89.5` |
| `ScavengersMHz` | `91.3` |
| `RaidersMHz` | `94.6` |
| `TravellersMHz` | `96.6` |
| `BroadcastGapSeconds` | `600` |

</details>

<details>
<summary>escalation.json</summary>

[Validation](mods/HollowCountry/scripts/4_World/World/HCEscalationClock.c)

| Key | Default |
| :--- | :--- |
| `InfectedWeek` | `0.25` |
| `InfectedFortnight` | `0.55` |
| `InfectedCap` | `1.0` |
| `RaidersWeek` | `0.1` |
| `RaidersFortnight` | `0.35` |
| `RaidersCap` | `1.0` |
| `ScarcityWeek` | `0.15` |
| `ScarcityFortnight` | `0.4` |
| `ScarcityCap` | `1.0` |
| `HorizonDays` | `30` |

</details>

<details>
<summary>admin-teleport.json</summary>

[Validation](mods/HollowCountry/scripts/4_World/Admin/HCAdminTeleport.c)

| Key | Default |
| :--- | :--- |
| `Version` | `1` |
| `ConfigBytes` | `4096` |
| `SiteBytes` | `262144` |
| `Enabled` | `true` |
| `IncludeActiveSituations` | `true` |
| `BuildingQueryRadiusM` | `100` |
| `MaxBuildingObjects` | `128` |
| `MaxDestinations` | `256` |
| `MaxNameEntries` | `512` |
| `RowsPerTick` | `8` |
| `PageSize` | `32` |
| `SearchAttempts` | `16` |
| `SearchStepM` | `4` |
| `GroundOffsetM` | `0.2` |
| `ClearanceWidthM` | `1` |
| `ClearanceHeightM` | `2` |
| `MaxSlopeDeltaM` | `0.4` |
| `BoundaryMarginM` | `2` |

</details>

<details>
<summary>admin-tour.json (owner test tool, off by default)</summary>

[Validation](mods/HollowCountry/scripts/4_World/Admin/HCAdminTeleport.c). When the file is present and `Enabled=true`, the first connected authorized admin is moved through the admin teleport catalogue, one stop every `DwellSeconds`. Each stop uses the admin teleport's normal safe-ground checks. The RPT logs `[HC Tour]` lines. It is not for players and is not shipped enabled.

| Key | Default |
| :--- | :--- |
| `Enabled` | `false` |
| `StartDelaySeconds` | `60` |
| `DwellSeconds` | `90` |
| `FirstStop` | `0` |
| `MaxStops` | `0` (all) |
| `LabelFilter` | `""` (all) |

</details>

<details>
<summary>incidents.json</summary>

[Validation](mods/HollowCountry/scripts/4_World/World/HCWorldIncidents.c)

| Key | Default |
| :--- | :--- |
| `Version` | `1` |
| `MaxIncidents` | `32` |
| `SweepPerTick` | `4` |
| `MaxResponders` | `1` |
| `MergeMeters` | `5` |
| `SightHeightMeters` | `1` |

</details>

<details>
<summary>role-activities.json</summary>

[Validation](mods/HollowCountryExpansionAI/scripts/4_World/HCXAIRoleActivities.c)

| Key | Default |
| :--- | :--- |
| `Enabled` | `true` |
| `EnableCarRepair` | `true` |
| `GroupsPerTick` | `1` |
| `MaxActive` | `4` |
| `CooldownSeconds` | `300` |
| `RetrySeconds` | `30` |
| `DangerMemorySeconds` | `120` |
| `SupplyNeedBelow` | `4` |
| `NightStartHour` | `20` |
| `NightEndHour` | `6` |
| `LogSeconds` | `60` |
| `MaxTableRows` | `64` |
| `MaxConfigBytes` | `32768` |
| `TicketCycle` | `1000000` |
| `PerceivedInfectedMeters` | `100` |

</details>

<details>
<summary>ai-incident-response.json</summary>

[Validation](mods/HollowCountryExpansionAI/scripts/4_World/HCXAIIncidentResponse.c)

| Key | Default |
| :--- | :--- |
| `Version` | `1` |
| `MaxLeases` | `4` |
| `StepsPerTick` | `2` |
| `LeashMeters` | `900` |
| `CooldownSeconds` | `300` |
| `MaxCooldowns` | `32` |
| `ArriveMeters` | `15` |
| `ProtectionLevel` | `0.5` |
| `MaxRoutePoints` | `32` |

</details>

<details>
<summary>expansion-ai-formations.json</summary>

[Defaults](mods/HollowCountryExpansionAI/data/defaults/expansion-ai-formations.json)

| Key | Default |
| :--- | :--- |
| `SchemaVersion` | `1` |
| `Disabled` | `false` |
| `GroupsPerTick` | `2` |
| `RefreshSeconds` | `6` |
| `MinMembers` | `2` |
| `RoadSurfaces` | `["cp_asphalt"]` |
| `NearBuildingRadius` | `18.0` |
| `TownRadius` | `90.0` |
| `RegroupSeconds` | `45` |
| `ThreatPercent` | `20` |
| `ColumnSpacing` | `3.0` |
| `WedgeSpacing` | `4.0` |
| `StaggerSpacing` | `4.5` |
| `TightSpacing` | `2.0` |
| `SpreadSpacing` | `9.0` |
| `RegroupSpacing` | `2.5` |
| `ColumnLane` | `0.8` |
| `WedgeWidth` | `1.0` |
| `StaggerWidth` | `0.6` |
| `SpreadDepth` | `0.35` |
| `LookOutDegrees` | `55.0` |
| `SpacingJitter` | `0.3` |
| `JogPercentRoad` | `40` |
| `JogPercentOpen` | `30` |
| `JogPercentTown` | `10` |
| `JogPercentTight` | `5` |
| `JogPercentRegroup` | `80` |
| `PaceEpochSeconds` | `120` |
| `PauseChancePercent` | `12` |
| `PauseMinSeconds` | `4` |
| `PauseMaxSeconds` | `12` |
| `PauseCooldownSeconds` | `90` |
| `JunctionTurnDegrees` | `50.0` |
| `JunctionRadius` | `8.0` |
| `JunctionPauseSeconds` | `6` |

</details>

<details>
<summary>expansion-ai-tactics.json</summary>

[Defaults](mods/HollowCountryExpansionAI/data/defaults/expansion-ai-tactics.json)

| Key | Default |
| :--- | :--- |
| `SchemaVersion` | `1` |
| `Disabled` | `false` |
| `SmokeDisabled` | `false` |
| `LureDisabled` | `false` |
| `LureAllowFull` | `false` |
| `SmokeExclude` | `"Contaminated"` |
| `LureTypes` | `"SardinesCan\|TunaCan\|BakedBeansCan\|PeachesCan\|SpaghettiCan\|TacticalBaconCan\|UnknownFoodCan\|WaterBottle"` |
| `LureNoisePath` | `"CfgVehicles SurvivorBase NoiseActionDefault"` |
| `CapWindowSec` | `600` |
| `SmokeCooldownSec` | `90` |
| `SmokeGroupCap` | `3` |
| `SmokeFireEvents` | `2` |
| `FireWindowSec` | `8` |
| `NearMissMeters` | `6.0` |
| `SmokeMinThreatMeters` | `15.0` |
| `SmokeMaxThreatMeters` | `120.0` |
| `SmokeThrowMeters` | `12.0` |
| `SmokeThreatFractionPct` | `40` |
| `SmokeActivationTries` | `4` |
| `ActivateWaitSec` | `10` |
| `ThrowForceMin` | `20.0` |
| `ThrowForceMax` | `60.0` |
| `ThrowLiftPct` | `40` |
| `LureCooldownSec` | `120` |
| `LureGroupCap` | `3` |
| `LureMinInfected` | `3` |
| `LureMinInfectedMeters` | `12.0` |
| `LureMaxInfectedMeters` | `60.0` |
| `LureThrowMeters` | `25.0` |
| `LureLandDelayMs` | `1200` |
| `LureNoiseMultPct` | `100` |
| `TickActors` | `4` |
| `ScanLimit` | `48` |
| `TrackedGroups` | `32` |
| `CheckEverySec` | `2` |

</details>

Role `Activities` and `Rules` arrays choose role matching and weighted activities; incident `Kinds` and response rules hold bounded perception/range/lease policies. Use their owning definitions when authoring rows; they do not grant AI new senses. Floor category/allowlist arrays are acquisition policy, and loadout named sets choose coherent kits rather than additive rewards.

## Admin tools

The [admin test kit](docs/ADMIN_TEST_KIT.md) accepts the server-owned COT permission `HollowCountry.Admin` as well as the private HC allowlist. Enable `EnableAdminMap`, grant the permission or configure the private allowlist, restart and use the rebindable Pause key. Status, kit availability and nearby lists are read-only. World commands exercise normal module logic and return named refusal reasons; they do not bypass caps or grant loot.

`AdminControls.disable` under the acceptance directory disables world controls after restart. `camptier` accepts 0–3; normal camp scans can reclassify the result. `campvisit` and `campraid` ask the camp visitor and base-raid owners for a physical party (visitor policy: tier 3, day 14 or later, three real days since the last visit; `camp_visitors.disable` turns visits off); refusals name their reason and consume no cooldown. `dormant` delegates to the infected variety fresh-body queue. COT permissions are checked against the authenticated connected player on each request; unavailable services and revoked permissions deny COT-based access. `COTAuthorization.disable` disables that permission route while retaining the private allowlist.

The Map tab displays snapshot layers, routes and per-layer counts. The loot map runs a bounded query and retains the last successful marks. `EnableDebugSnapshot` controls export; `EnableAdminMap` controls authorised in-game access. The [debug map guide](docs/DEBUG_MAP.md) covers the local browser map, snapshot freshness, layer caps and query controls. Keep exported maps and profiles private. Grant the registered `HollowCountry.Admin` permission in COT; older COT setup notes may predate this binding.

## Performance

The intended test load is **3–6 players**. Recorded boots do not establish a tested player capacity. Performance budgets remain provisional until measurements with that load; larger-server capacity is unproven.

`TickIntervalMs=1000` sets the core cadence. `MaxTickWorkItems=32` is shared across forty consumers. For cost-one requests, starvation prevention permits up to 71 items in a tick; heavier requests and measured charges can exceed that unit total. This is a work allowance, not a millisecond frame-time guarantee. `[HC TickWork]` reports shared usage and starvation; `[HC CostTotal]` and `[HC Cost]` report aggregate and module costs. Building-class first resolves, event preflight, ecology and world saves still need native cost observations; target-load capacity remains provisional in [#138](https://github.com/d-addison/hollow-country/issues/138).

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
| 12 | `HC_WORK_BASE_RAID` | Warned base raid work. |
| 13 | `HC_WORK_ROLES` | Role activity scheduling and leases. |
| 14 | `HC_WORK_FORMATION` | Formation and movement styling. |
| 15 | `HC_WORK_CARFIX` | Real-part car repairs. |
| 16 | `HC_WORK_HEARTH` | Real fireplace observation and ignition. |
| 17 | `HC_WORK_INCIDENTS` | World incident registry sweeps. |
| 18 | `HC_WORK_INCIDENT_RESPONSE` | Perceived incident response. |
| 19 | `HC_WORK_AI_RESPAWN` | Fresh AI group replacement. |
| 20 | `HC_WORK_SEARCH_COMPACT` | Search-session compaction. |
| 21 | `HC_WORK_SHELTER` | Regional shelter placement. |
| 22 | `HC_WORK_AI_SITES` | AI locality candidate paging and site maintenance. |
| 23 | `HC_WORK_STORY_INDEX` | Story index parsing. |
| 24 | `HC_WORK_AI_ROUTES` | Regional AI route qualification. |
| 25 | `HC_WORK_POLICE_BIND` | Police supply binding. |
| 26 | `HC_WORK_ROADS` | Road graph loading and path search. |
| 27 | `HC_WORK_INFECTED_VARIETY` | Infected variety work. |
| 28 | `HC_WORK_INFECTED_VARIETY_ROUTES` | Infected variety routes. |
| 29 | `HC_WORK_SITUATION_RUNTIME` | Situation runtime. |
| 30 | `HC_WORK_SITUATION_SMOKE` | Situation smoke retries. |
| 31 | `HC_WORK_ADMIN_VISITOR` | Admin visitor requests. |
| 32 | `HC_WORK_TACTICS_SCAN` | AI tactics scans. |
| 33 | `HC_WORK_AI_TRADE_PRODUCER` | AI caravan production. |
| 34 | `HC_WORK_CONVOY_ROUTE` | Convoy route work. |
| 35 | `HC_WORK_CONVOY_RUN` | Convoy runtime. |
| 36 | `HC_WORK_SEARCH_COVERAGE` | Search coverage. |
| 37 | `HC_WORK_SEARCH_RETIREMENT` | Search retirement. |
| 38 | `HC_WORK_WILDLIFE` | Wildlife maintenance and carcass creation. |
| 39 | `HC_WORK_ZONE_GUARDS` | Dynamic military zone guards. |

Package hash caching serializes read/merge/replace with persistent OS-held locks; process exit releases ownership. Stop older lock-file builds before switching protocols. Windows contention remains unverified.

`Performance.*` controls bound retained ecology/interior/holdout slices and shared save work. The save target is cooperative: native probes, file reads and owner barrier/shutdown flushes cannot be preempted.

## Milestones

- **Current test build:** finite survival, AI activity, 23 added Expansion vehicles, map-wide authored sites, paged interiors and configurable owner limits are in source/packages; integration gaps are named above and in-game acceptance remains pending.
- **Server acceptance:** DayZDiag and normal signed PBO/server boots, then at most one client for visibility, sound, inventory, persistence and privacy checks. Capacity budgets remain provisional; no additional people are required for acceptance.
- **Coverage correction:** the reverted item pass (`0321022f`) is being replaced with curated vanilla-only acquisition routes.
- **Later:** item, food and clothing variety mods are [on hold (#232)](https://github.com/d-addison/hollow-country/issues/232).

## Documentation and contributing

- [Operator documentation](docs/README.md): configuration, persistence, backups and recovery.
- [Addon development](docs/MOD_DEVELOPMENT.md): source layout and package workflow.
- [Tools](tools/README.md): standard-library tooling, installers and validators.
- [Tests](tests/README.md): fast Python tooling: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit`; nightly/on-demand tiers use `-s tests/slow` (slow tooling) and `-s tests/legacy` (quarantined Enforce translators/source contracts). Offline checks do not establish DayZ behavior.
- [Contributing](CONTRIBUTING.md): contribution requirements.

Report bugs through [GitHub issues](https://github.com/d-addison/hollow-country/issues), with the build, feature, expected/actual result and sanitised refusal/log lines. Do not attach credentials, identifiers, private profiles or third-party assets. Missing runtime behaviour remains open until tested on DayZDiag and a normal signed PBO/server; sound, visibility and replication need one client.

## License and assets

Copyright © 2026 David Addison. **All rights reserved.** No open-source or public reuse license is granted. Third-party materials retain their owners' terms; see the [provenance inventory](docs/PROVENANCE_AND_LICENSES.md).

Game files, full vanilla dumps, purchased assets, Workshop packages, signing private keys, credentials and runtime profiles do not belong in this repository. The repository is public; no reuse license is granted. Published third-party Workshop dependencies are never repacked.
