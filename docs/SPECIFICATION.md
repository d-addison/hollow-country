# DayZ Standalone — Survival Overhaul: Product & Technical Specification

> Execution update (2026-11-16): project is **Hollow Country**, ChernarusPlus
> confirmed, local development/test server here, eventual friend's server for
> **3–6 players**. ADR-017 supersedes the initial separate-machine prerequisite.
> Canonical execution artifacts live in `docs/specs/001-survival-overhaul/`.
> Gameplay requirements below remain in force; runtime acceptance is pending.

**Document:** SPEC-001 | **Version:** 1.0.0-draft | **Date:** 2026-11-16 | **Status:** user-preference complete, engine research and implementation NOT completed  
**Next execution stage:** reproduce official tooling and vanilla baseline on separate client and server machines, then run timeboxed capability experiments.  
**Game baseline:** PC stable 1.30.164289 (2026-11-03), verify at next-session start.  
**Initial world assumption:** ChernarusPlus, because the examples and Northmen reference are based there; do not interpret this as permanently excluding other maps.  
**Distribution:** private GitHub source repository; possible future independent Workshop release, not authorized for publication now.

> **Normative vocabulary.** **MUST** = mandatory acceptance criterion, **SHOULD** = important preference that may be revised through a recorded decision, **MAY** = optional implementation. **CONFIRMED** = direct user preference; **PROPOSED** = engineering design subject to validation; **R&D** = capability unconfirmed and must be tested. Prioritize evidence over wording whenever engine realities differ.

## 0. Executive project definition

Build a performance-first, modular, multiplayer-correct DayZ Standalone overhaul that uses native features, existing configs and official tools wherever possible. Extend rather than reinvent game systems; write a custom subsystem only when experiments show a specific missing capability. Deliver richer scavenging, varied pre-existing interiors, more useful found items, and competent infected with physically coherent senses, mobility and audio. **Both dynamic persistent hordes and nearby infected chain reactions are required.** The overhaul must remain recognizably DayZ and should not depend on Northmen proprietary packages.

The four planned game modules are **Loot & Economy**, **Interiors & Scavenging**, **Crafting & Salvage**, and **Infected & Hordes**. A tiny, shared server-authoritative support layer may provide config, reproducible RNG, event routing, lightweight state/persistence, diagnostics and toggles. Avoid a giant general-purpose framework without demonstrated reuse.

### 0.1 Confirmed design decisions (immutable until user changes them)

| ID | Requirement / exact preference | Acceptance interpretation |
|---|---|---|
| GOV-01 | Local experimentation first; private GitHub repo now, public release only maybe | No public repository, publication, or live-server distribution without separate approval |
| GOV-02 | Northmen server experience is a gameplay reference, not a dependency | Match general survival/progression feel, but audit vanilla separately; never assume rights to Northmen Core |
| DEV-01 | Two-machine environment | Separate development/game client and dedicated local test server, on a private network initially |
| DEV-02 | Multiplayer-ready from first code | Server-authoritative gameplay and networking contracts even if first playtests involve one client |
| DEV-03 | Minimal external dependencies | Vanilla & official tools first; external mods only with clear value, license and compatibility evidence |
| GOV-03 | Hyper-efficient, optimized implementation mandatory | Performance budgets and profile evidence gate acceptance |
| LOOT-01 | Survival-first but rewarding scavenging | Difficulty preserved, ordinary exploration often worthwhile; no universal loot guarantees |
| LOOT-02 | Soft tier progression with realism and world-dynamic elements | Primary B (soft risk/geography), plus C (believable placement), plus D (events/depletion/history) |
| LOOT-03 | Every accessible building and meaningful area gets a *chance* at loot | Coverage audit includes neglected apartments and double white military bunk-bed barracks |
| LOOT-04 | Better item variety, less duplicated junk in identical places | Address categories, repeated positions, low utility, rarity and overspecialization |
| LOOT-05 | Essentials and civilian supplies should not be arbitrarily unobtainable | Multiple acquisition routes; soft scarcity without removing exploration or risk |
| LOOT-06 | Higher-tier military loot should feel attainable through risks | Measurable progression; no guarantee of weapons or rare equipment |
| INT-01 | Reuse existing house/building models and floor plans | No replacing/rebuilding architecture or requiring custom house models |
| INT-02 | Existing houses have varied interiors and building histories | Additive furnishings/clutter, selected compatible layouts, coherent loot profiles |
| INT-03 | Mixed visible and searchable loot | Search cupboards, wardrobes, fridge/cabinets where practical; no loot faucet |
| INT-04 | Persistent layout lifecycle | A building's layout survives restarts until explicit reset/wipe/controlled migration |
| CRFT-01 | Broad multi-use item repurposing | Existing items can be cut, dismantled, salvaged, combined; e.g., camo net -> camo wraps, if assets/APIs permit |
| AI-01 | Infected should be competent before being more powerful | Fix navigation/doors, targeting, audio and physical bugs as far as exposed APIs allow |
| AI-02 | Dynamic hordes AND local chain reactions | Hordes may move and persist; alert events propagate locally without teleport/magical information |
| AI-03 | Methodical building searches | Investigate reachable rooms/last-known place and noise; no perfect tracking |
| AI-04 | Persistent but fair pursuit | Breaking LOS, silence, diversion and plausible escape must work |
| AI-05 | Individuals relatively ordinary; groups dangerous | Threat from numbers, positioning, behaviors; not blanket inflated health/damage |
| AI-06 | Balanced population density | Familiar overall numbers with occasional concentrations, not permanent dense swarms |
| AI-07 | Hybrid visual/location cues plus individual variation | Variants have recognizable tendencies but no absolute predictability |
| AI-08 | Door B/C mix | Different variants attempt unlocked doors, bash/force doors, or remain blocked; reliable open-door passage prerequisite |
| AI-09 | Advanced stealth variants allowed | Stealth must still produce believable footsteps, shuffles, contact and other noises according to actions/surfaces |
| AI-10 | Expanded injury effects | Investigate existing crawl transition from leg injury and extend hit/mobility effects only when supported |
| PHY-01 | Real-world game rules still apply | No collision violations, silent impossible ambushes, omniscience, impossible speed or sound propagation |
| AUD-01 | Realistic audio behavior | Appropriate audible locomotion/action sounds with distance, surface and obstacles where achievable |

### 0.2 Goals and non-goals

**Goals:** Make apartments, underused barracks, residential interiors, industrial yards and other areas meaningfully searchable; reduce pointless repetition; improve loot location/context and the utility of mundane items; make infected competent and readable; test every feature with performance and multiplayer constraints; maintain optionality for future Workshop release and third-party compatibility.

**Non-goals for v1:** Original building geometry replacement; massive new custom maps; cinematic cutscenes or fully bespoke animation assets; new weapon systems or vehicles; full rewriting of DayZ Central Economy; complete replacement of native navmesh; human tactical NPCs; forced trader/quest economy; Northmen proprietary assets; custom graphics beyond what is needed for gameplay; monetization. New asset work is permitted only as a small, separately approved exception when unavoidable.

### 0.3 Quality attributes and priorities

1. World physics, fairness and audio consistency (hard).
2. Server and client performance and stability (hard).
3. Multiplayer correctness, persistence safety and item duplication prevention (hard).
4. Coherence and exploratory reward of survival loop (hard).
5. Modularity, maintainability, predictable builds and low dependency count.
6. Visual flair, unusually complex AI, and bespoke assets (secondary; cut first if costs exceed value).

## 1. Native-first capability and decision policy

**For each requested behavior, perform the following before coding:**

1. Identify official DayZ server config, Central Economy XML, mission data, gameplay JSON, object-spawner mechanism, existing class hooks and diagnostic APIs.
2. Check the exact mechanism in the installed stable build. **An online API page alone is not proof it works for our scenario.**
3. Prototype using existing config/data first; quantify result and performance.
4. Extend with small server/client scripts only for the missing delta; use built-in lifecycle/event hooks wherever possible.
5. Consider optional third-party dependencies ONLY when licenses and interoperability are acceptable; document whether existing code is merely a reference.
6. Author a custom subsystem only after demonstrating why earlier stages are insufficient.
7. Add a test, metric, rollback/feature flag and source citation for every extension.

**Verified official starting surfaces:** Central Economy `types.xml`, `cfgspawnabletypes.xml`, `cfgrandompresets.xml`, `mapgroupproto.xml`, `mapgrouppos.xml`, `events.xml`, `cfgeventspawns.xml`, `cfgeconomycore.xml` extensions; `cfggameplay.json`; Object Spawner; DayZDiag CE loot editing/profiling; DayZ Tools Workbench and Addon Builder; normal `CfgPatches`/`CfgMods` Enforce scripts. **Research-required:** whether particular callbacks can observe damage, doors, footsteps, infected perception and CE ownership reliably; live spawn placement, navigation, and dynamic sound controls. See R&D matrix.

**No 'native' assumptions:** `-filePatching` is a dev feature, not a substitute for a production PBO/signature workflow. Static Object Spawner JSON is evaluated at mission start and is not, by itself, a streamed/persistent procedural interior service. Vanilla infected navigation is partly native; changing script decisions does not rebuild navmesh. Script profiler measures script calls but not all native costs.

## 2. Shared domain model (proposed interfaces)

All schemas below are conceptual contracts; actual Enforce Script classes, file formats and event hooks are **R&D deliverables**.

- **WorldIdentity:** map key, game build, world seed, schema version, optional reset epoch.
- **BuildingDefinition:** vanilla building classname, variant family, room/anchor definitions, static-vs-collidable eligibility, loot categories, exclusions, verified transforms, door locations and test fixtures.
- **BuildingInstance:** stable world-position/orientation identity + building class + epoch; interior layout ID/seed; archetype; searchable-container depletion state and item ledger reference. Beware float precision: choose quantized coordinates and identity collision handling; do NOT use an unstable runtime pointer or instance ordering.
- **Archetype:** probabilistic building history (normal, looted, family home, survivor shelter, workshop, improvised aid station, abandoned evacuation, etc.), compatible props, clutter budget, search sites, rarity modifiers, exceptions.
- **LootPolicy:** item groups, rarity/risk/region weights, storage location tags, acquisition routes, caps/budgets, economy ownership and fallback rules.
- **SearchableSite:** world object or anchor ID, interaction prerequisites, content seed or precommitted allocation, depleted/changed state, search duration/noise and UI response.
- **SalvageRecipe:** deterministic inputs/amounts, eligible tools, conditions, loss/quality and durability effects, outputs, no free resources or zero-cost conversion cycles.
- **InfectedProfile:** behavioral archetype + deterministic individual variation; sensory/alert thresholds; attention decay; door policy; search policy; mobility/injury constraints; sound profile; aggression and group affinity.
- **Stimulus:** emitted location and time; physical category (footstep/door/scavenge/gunshot/vocalization/impact); source, estimated intensity and lifetime; evidence provenance; not direct player coordinate injection.
- **AlertMemory:** last **observed** target location, hearing cue hypotheses, uncertainty and expiration; sensor provenance; confidence may decay; no true target location after LOS break.
- **HordeRecord:** persistent logical group ID, membership budget, anchor/path/intended destination, group state, activity/interest, last known stimuli, materialized member IDs, lifecycle epoch and unload safeguards.
- **PerformanceBudget:** per-system work limits and stats; overload behavior must degrade noncritical AI detail rather than skip collision/audio rules.

**Module boundaries:** `Core` owns versioned config/seed/diagnostics/event queue (not all gameplay). `Loot` integrates with Central Economy and owns supplementary item budgets. `Interiors` owns building-layout identity, object-placement and searchable-site state; it asks Loot for allocations. `Crafting` owns player actions and item changes; it does not spawn world loot. `Infected` owns supplementary decisions, group state and sensory cues; native engine owns actual physics/navigation/animations wherever possible. The integration layer only publishes semantic events (`ScavengeSound`, `DoorImpact`, `InfectedVocalized`, `BuildingLooted`, `HordeInterestChanged`).

**Network contract:** Server exclusively commits loot, inventory mutations, container depletion, variants, horde state and door changes. Clients may render cues and request interactions; server rechecks range, LOS, eligibility, occupancy, item durability and inventory transaction. Replicate only visible/player-relevant deltas, never the whole world model or unneeded RNG state. Inspect native RPC/synchronization primitives before creating custom network protocol. Version and validate any custom RPC.

**State lifecycle:** Predictable initialization -> building discovery/registration -> layout assignment -> selective entity placement -> interaction -> changed state journal -> bounded periodic persistence -> graceful shutdown -> reload/migration. Persist state atomically or with recoverable snapshots/journaling; version schema; backups; restart tests; repeated init must be idempotent. Never reroll layouts or create loot simply because players reconnect. Distinguish loot taken by player from intentionally resetting a depleted site.

## 3. Loot & Economy system (LOOT)

### 3.1 Product behavior

- Every accessible vanilla structure and genuinely exploitable outdoor area MUST have at least one *eligible opportunity* to yield loot after coverage changes, even if any given instance can be empty. No mandate to fill every room or every building instance.
- Prioritize apartment blocks, notoriously nearly empty white double military barracks with bunks, residential houses, sheds/garages, industrial compounds, outdoor utility areas and abandoned vehicles where existing events/config allow.
- Spawn context MUST normally make sense: kitchen/pantry -> food/cookware; bathroom/clinic -> medical and hygiene; bedroom/wardrobe -> clothes, bags, batteries; workshops/garages -> repair, hardware; rural home -> hunting/household; barracks -> civilian/personal effects, uniforms/maintenance and occasional military gear.
- Preserve tasteful exceptions from survivor histories, movement of goods during collapse, emergency events and rare finds; do not enforce unrealistic rigid item-to-room categories.
- Economy MUST support survival-first reward: most explorations present a *chance* of useful progression; rare finds remain special; basic tools and mundane supplies need multiple credible acquisition locations.
- Reduce repetitive items in identical fixed slots through increased valid spawn spots, broader weighted item classes, archetypes, persistent low-volume searchable sites and varied building histories. Never multiply objects indiscriminately.
- Higher military tier should be difficult but attainable through risk. Avoid single exclusive farming routes and 'all or nothing' rarity. Maintain distinct civilian and military equipment benefits and tradeoffs.
- Account for preexisting world items, player inventory/storage (where CE count flags apply), searchable allocations, scavenged supplies and restock/depletion to avoid economic inflation and dupes. Compare CE flags in the actual build.
- Naturally preserve depletion: recently looted buildings can remain barren; no new item generated by opening the same drawer a second time. Explicit configurable replenishment is possible only after a justified policy/trigger and persistence safeguards.

### 3.2 Native-first execution sequence

1. Snapshot official mission economy and live baseline; record hash and version. Inspect `types.xml`, flags (`nominal`, `min`, `restock`, `lifetime`, storage/hoarder count flags etc.), usage/value/tier tags and `cfgspawnabletypes.xml`; do not blindly change unknown fields.
2. Audit `mapgroupproto.xml` building prototypes and `mapgrouppos.xml` group placement; count containers, valid spawn points, class coverage, and anomalies. Validate map family and aliases before concluding there are no points.
3. Use DayZDiag > Central Economy > Loot Spawn Edit (single-player CE mode where required) and official CE Editor to add test points; export and compare. Do not assume all diagnostic menu actions work in dedicated multiplayer.
4. Add separate CE override/append files through `cfgeconomycore.xml` where officially supported; make original changes generated, reviewable and revertible. Where an XML type cannot be modularly overridden, document the precise supported workflow.
5. Perform spawn/occupancy/collision tests inside actual map; measure CE spawn-search overhead and item counts as well as gameplay reward.
6. Only after gaps remain, prototype contextual per-room searchable allocations. Keep custom pool supply governed by quota/precommitment independent of client repeat interactions.

### 3.3 Proposed distribution model

For a *supplementary* search site: choose context of `building_class + room/function + archetype + risk_region + depletion/world_state + item_group`, with a seeded weighted sampler and rarity caps. This is not a promise to replace CE's native weighting. Consistency requirements: probability normalization; explicit no-result outcome; no possible item outside registered types; compatible storage size; durability condition; protected rare caps; no infinite-loot interaction loops; no deterministic public seed exploitation; server-authoritative selection. Consider an allocation record created on building initialization, with contents committed at first authorized search; claim/consume must be atomic.

### 3.4 Balance telemetry and acceptance

Generate machine-readable `building_coverage.csv`, `loot_routes.csv`, and `economy_audit.json`, including counts of buildings with 0 spawn points; spawn-point density; valid categories per location; observed visible vs searchable outcomes; repeated-item concentration; distribution of time/structures searched before acquiring essentials; high-tier acquisition routes; world-level item quantities; and CE warning/error diagnostics. Use reproducible seeds and actual CE smoke tests (simulations are only model/unit tests). No arbitrary target values are officially fixed yet: choose targets after measuring vanilla and getting user approval. Hard rule: every selected accessible **class** has a valid loot opportunity (excluding inaccessible geometry and intentionally non-searchable decorative structures) and no generated duplicate item.

## 4. Dynamic Interiors & Scavenging system (INT)

### 4.1 Bounds

- Preserve all vanilla exterior building assets, geometry, baked furniture, floor plans, navmesh and map files.
- Vary **additive** props, movable furnishings if assets support, storage/search interactions, visible clutter, item placement, and coherent human histories.
- A single *building class* can have multiple compatible archetypes/layout IDs. Layouts must be authored/validated per building geometry; do NOT blindly scatter props around room volumes.
- Baked-in furniture cannot be individually removed by simple world scripting. Avoid claiming 'replacing' an existing kitchen cabinet if it is part of model geometry.
- Interiors should differ persistently from one another, and retain a chosen layout across restarts and reconnects. Regeneration at a wipe or explicit admin migration only.
- Search sites include existing visible cabinet/wardrobe/desk/fridge where interactions are technically feasible (proxy targeting if necessary) plus explicit containers. Do not require thousands of independently networked interactive entities.
- Environment conveys story: ransacked property, ordinary family home, shelter, improvised clinic, former workshop, abandoned camp/evacuation; no ungrounded RPG loot markers.

### 4.2 Implementation options (in increasing cost)

**Level 0 — CE spawn-point enhancement:** different loot placements within existing buildings; *no new decorative assets*. Minimum-vital prototype for apartments and military barracks.

**Level 1 — static, per-instance setup:** Use Object Spawner to place authored props and fixed test layouts **at mission start**. It uses JSON configured in `cfggameplay.json`, and can be heavy at full map scale. Object Spawner alone does **not** assign per-building random variants or stream dynamic rooms. Test performance on a small test district first.

**Level 2 — lightweight data-driven per-building layouts:** Use a precomputed manifest mapping stable world building instance IDs to seeds/layout IDs; either generate approved Object Spawner JSON **offline** or script spawn a bounded set of objects at mission startup. Prefer offline generation if server startup and object count fit. Retain deterministic identities and exact transforms, with collision tests and object budgets.

**Level 3 — activated/streamed furnishing:** Only if Level 2 fails performance targets, evaluate proximity-based activation of noninteractive visual props while keeping loot/ownership/persistence server-authoritative. HARD requirement: no visible pop-in, no player/AI clipping, no container regeneration, no missed/duplicated net events, and unloaded entities not used to erase player-placed/looted state. Defer unless benchmark evidence justifies complexity.

**Level 4 — searching baked-in furniture:** Investigate native action system, compatible object selections and proxies; if targetable, interact on building+site ID rather than adding one continuously running entity per drawer. One server-side search authority per site. Some built-in furniture may remain non-targetable: ship an invisible/visible interaction proxy only after validating usability, occlusion and overhead; otherwise omit that site transparently.

### 4.3 Placement and world rules

- Coordinate representation: authored positions **relative to building transform**; validate yaw, height/floor, object bounding boxes, door swing arcs, spawn points, windows, stairs and line of movement.
- Never create new collisions that invalidate tested player paths, doors, ladders or infected travel. Dynamic AI navmesh cannot be assumed to re-bake around our props: collision-heavy objects either banned in paths or paired with measured AI safe routes.
- Hard per-building budgets for networked/static objects, collision-enabled objects, active physics and interactive sites. Budget levels vary by archetype and building size, set after benchmark, not guessed.
- Avoid dynamic physics for cosmetic clutter; prefer already existing decorative assets where terms allow and low-cost static, non-simulating entities where API permits. The 1.30 patch notes mention `disableSimulation` for house-based entities—R&D must validate exact applicability, syntax and lifecycle.
- Layout changes and loot depletion must not occur while an occupied building is unloaded/reloaded due to simple player distance, or during routine server restart.

### 4.4 Example user stories / acceptance

- A player searches three visually identical houses; they have distinct, plausible interior themes and differentiated loot; reopening one emptied dresser yields no new items.
- An apartment floor with multiple rooms can yield visible and searchable loot, but an individual apartment may be barren because it was ransacked or already visited.
- A white military bunk-bed barracks is no longer a systematic waste of exploration: it has tested spawn opportunities with believable military/personal supply distribution.
- Players and infected pass through open doorways reliably at the baseline engine rate or better; furnishings never increase stuck incidents relative to the unobstructed control.
- Restart restores layout ID, existing props and depletion exactly once, without cloning items or leaving ghost actions.

## 5. Crafting, Salvage and Item Utility (CRFT)

**Intent:** give common/rare items multiple *plausible* uses. Items should become more useful and world exploration less frustrating without creating resources from nothing.

**Core domains:** cutting cloth and nets, creating camouflage accessories/wraps, reclaiming rope/straps/hardware, fixing damaged clothes, salvaging mechanical/electrical parts, improvising storage and tools, reusing compatible repair components and dismantling unusable equipment. A crafted result must reflect authentic physics/utility, not unlimited upgrades.

**Illustrative recipe (NOT a validated current DayZ craftable item):** camouflage net + cutting tool yields configurable net strips and cord at a cost to the net and tool condition; strips + bindings + compatible rifle can yield a camouflage wrap if vanilla-compatible attachments/visual asset work can be demonstrated. If adding a new weapon attachment entails new models/materials, first attempt a functionally equivalent configuration-driven or existing-model method. Do not promise visible wraps until proven.

**Recipe contract:** typed inputs and amounts, required tool class, quality/damage thresholds, tool consumption/wear, crafting time/noise, output class/stack amount, fallback if inventory full, input/output server transaction, duplication avoidance, animation/UI compatibility, net material balance and reverse-cycle economy invariants.

**Design rules:** common items have multiple categories of valid uses but not every object gets a nonsensical recipe; irreversible conversions have meaningful yield losses; salvage ruined gear is possible only if justified; damage and wear influence outcome; container value and inventory mass/volume remain meaningful; new recipes integrate with current DayZ actions rather than adding an independent crafting UI unnecessarily. Log crafting results with low-cost instrumentation and track recipe use as balance signal.

**Testing:** property-based material conservation on recipe graph, no infinite positive-yield conversion cycles, invalid input blocking, disconnect/reconnect mid-craft, multiplayer simultaneous requests, interrupted actions, full inventory, tool destroyed mid-action, server restart and stack splitting.

## 6. Infected Competence, Perception, Injury, Variants (AI)

### 6.1 Behavioral first principles

- An infected's next action derives from **sensed information**, an explicit remembered clue, current abilities and group response. The controller MUST NOT read hidden live player positions to pursue after LOS loss.
- Audible movement/interaction sounds correspond to action, speed, materials and distance. Quiet variants are careful and may move slower, limit vocalizations and take quieter paths; they are **not physically silent**. Perceived quietness must make sense to two observing clients.
- Infected cannot attack through solid walls, phase through doors, jump between unreachable floors, ignore collision, or suddenly teleport to an engagement. Fail-safe when native pathfinder cannot solve route: investigate/search, move to valid anchor, disengage, or report blocked navigation—no fake wall-crossing fix.
- Visual reactions should fit LOS, lighting and obstruction, subject to what engine exposes. No omniscient room scan.
- A long pursuit must gradually lose confidence if target disappears and gives no clues; re-acquisition requires new observation or plausible stimulus. Diversions and stealth must be viable.
- Injuries reduce relevant mobility, range, attack speed/reach or stability; injured infected must not sprint normally on destroyed legs. Verify native crawling mechanism and avoid claiming specific bone-break animations without tests.
- Threat is principally in dangerous numbers, not all individuals having massive health, damage, or super-speed.

### 6.2 Variant system (PROPOSED; configure probabilities)

| Variant | Sensory/personality tendency | Doors / mobility | Trade-off |
|---|---|---|---|
| Ordinary wanderer | Slow/variable attention, follows close cues | Navigates open passage, maybe tries unlocked door | Easily distracted, commonly isolated |
| Reactive infected | Quick to sounds and nearby alarms | Rushes reachable routes, may strike closed door | Loud, less careful searching |
| Persistent searcher | Retains last-known position, checks nearby reachable points | May investigate doors, search room anchors | Longer search time, not exact target tracking |
| Careful stalker | Deliberately quieter locomotion, pauses/listens | Attempts unobstructed/accessible entries | Slow/less explosive, still audible and visible |
| Forceful/heavy | Slow but persistent, effective door bashing | Can force certain doors after audible effort | Slow, loud, constrained by solid materials |
| Group responder | Heeds nearby calls; joins disturbances | Acts as group member, no global hive mind | Alert spread attenuates and expires |
| Injured/crawler | Leg impairment, lower physical profile | Only routes actually accessible while crawling | Slow, limited reach and uneven ground problems |

Archetypes are blended with individual traits and location/appearance cues; they do not imply special 'boss' models. Military location may influence probabilities but never grants special abilities without trade-offs. Persist per-entity variation only if required by game lifecycle; otherwise spawn-seeded stable traits until despawn.

### 6.3 Local chain reactions (AI-CR)

- On a **real** audible event (gunshot, infected scream, fight, forced door, rummaging), publish a stimulus with source, origin, intensity, timestamp, category, and TTL. Avoid requiring all events to be custom when vanilla AI already reacts adequately.
- Query **spatially nearby** eligible infected/horde anchors; use native hearing first where reliable. Apply distance falloff, environmental attenuation if available, and conservative approximations if not. Events shouldn't propagate around impossible geometry as exact target coordinates.
- A responder may emit another **audible** scream/call, creating a *bounded* second-order reaction. Prevent a zero-cost exponential cascade: hop limit, decay, deduplication of event IDs, per-entity cooldowns, rate limits, maximum recipients, and max active group budget. Propagation may be less deterministic due to dynamic geometry but must not be magical.
- Visual cues and reaction delay fit animation and sound. Priority order: visible threat > compelling sound > remembered clue > idle.
- Never call a full-world scan for each scream, shot or frame. Use native query radii/spatial partitions if exposed; otherwise maintain compact index updated only on movement/registration.

### 6.4 Dynamic persistent hordes (AI-HD)

**Hordes and local chain reactions MUST coexist.** A horde is a **logical, stateful group** of infected with a believable origin, a size budget, purpose/migration direction, last stimuli, and activation radius. Local alerts can attract a horde, and a horde's audible/visible activity can alert nearby isolated infected. Recruits do not instant-teleport into the group.

**Lifecycle:** Dormant/abstract -> motivated (world event or nearby stimulus) -> route selection -> approach/roam -> player proximity activation -> normal infected entities -> engagement/search -> de-escalate -> abstract again when safe and unobserved. All transitions use spatial/visibility checks, grace periods, and no despawn/reappearance where players can observe it. Log horde IDs and approximate anchor route, not per-tick positions.

**Horde principles:** credible migration, occasional naturally occurring concentration; finite counts and replenishment; no hidden 'spawn behind player'; bounded active entity counts; surviving horde members preserve important identity/state when possible; no automatic omniscient player seeking; if horde loses target it may continue investigating last cue, roam or disperse. Do not imply native navmesh supports arbitrary roads/rooms: test waypoint travel and fallback when blocked.

**Performance approach:** distant simulation as group anchors + coarse periodic decisions; spatial activation for actual infected; reuse CE infected/event spawning where possible to avoid duplicate populations; only nearby groups use expensive perception/search interactions. Use a global occupancy budget so activations cannot exceed agreed server load. LOD transition must not alter physical reality in a player-observable way. 'Network LOD' and simulation LOD are independent decisions.

### 6.5 Door and room search behavior

**First gate:** native infected enters an already-open doorway (different door states; multiple buildings and approach angles) without a mod-induced regression. For closed doors, profiles range from blocked or temporary banging -> unlocked opening (only where script APIs/animations support reliably) -> repeated, audible forced entry (only doors that can logically be opened/broken). Never magically open locked/structurally solid obstacles. Verify interaction by building class and door index, including rebuilt structures and modded locks. Avoid bypassing a player's locked base in a way not explicitly configured. Stop banging when target evidence expires, unless variant's suspicion justifies delay.

**Methodical search:** Last-seen position and stimuli lead to a small set of reachable room/door anchors. Search progresses through waypoints with LOS and timeouts; no per-tick exhaustive raycast of every room. Search may terminate at blocked navigation; uncertainty increases over time. A cautious searcher can pause and listen, but should emit audible locomotion. Profile exact native locomotion/path hooks before implementing scripted route nudges.

### 6.6 Injury, sound, fairness

**Injury:** R&D confirm `ZombieBase` leg damage/crawling in current scripts, actual hit-point names, transition state sync, locomotion/attack range; do not implement speculative limb damage APIs from outdated examples. Improve using current hit/health events where possible. Different leg damage thresholds may change speed or crawler transition; arms/head effects only when animations and gameplay rules make them credible. No gore/dismemberment models assumed.

**Sound:** Build an audio test matrix for walk/run/crawl, stairs, floors, grass, concrete, clutter, door hits, attack vocalizations, path occlusion, distance and two-client perception. Distinguish AI hearing signal from player-rendered sound; an infected being detectable by AI does NOT prove that a human player hears it. The 1.30 patch notes mention missing footstep audio on some prop/wall surfaces; classify engine defect if unfixable. Do not play synthetic redundant sounds every tick; prefer existing sound hooks/animations and one-shot material-aware fixes only where supported.

### 6.7 AI failover / guardrails

Native pathfinding failure -> bounded retry/alternate validated waypoint -> fall back to last reachable location, investigate or disengage; never teleport or ignore collisions. Broken custom decision loop -> profile fallback to vanilla logic. Overloaded server -> decrease decision cadence/distant LOD and group activation, not enemy audible cues, hit registration, LOS fairness or authoritative physics. Preserve ability to disable each behavior via server config without wiping unrelated persistence.

## 7. Performance, scalability & resource management (PERF)

Performance is **release-blocking**. Avoid any architecture which requires continuous polling of all buildings, per-frame global infected queries, unconstrained object placement, full-area RPC state broadcasts or synchronous save storms.

### 7.1 Performance objectives (initial hypotheses; calibrate by vanilla baseline)

- **Provisional target:** 60 server FPS at the eventual agreed load and hardware, *if vanilla can attain it.* This is NOT a universal DayZ performance promise. Compare to vanilla in identical scenarios.
- **Provisional regression ceiling:** ≤5% median/steady-state extra server frame-time cost for core features under the agreed target load; ALSO gate p95/p99 frame-time spikes and client 1% lows. The 5% figure is an engineering starting point for discussion, not a user-approved bound.
- **Zero** unnecessary per-frame global scans; near-zero per-frame idle building work; bounded operations and rates.
- Instrument client avg/1% low FPS; server FPS/frame time distribution and spikes; CPU/thread use; RAM; active entities/colliders; script profiler time/calls/allocations; network bandwidth/RPC counts; CE spawn queue; persistence writes; startup/restart times; warnings/crashes.
- Test load scenarios: one client, representative two-client co-op, and synthetic/real target-concurrency levels after hardware and player target are known. Native server simulated-player support should be verified and its AI/perf representativeness stated; do not claim it is full human-equivalent load.

### 7.2 Bounded work requirements

- Loot economy primarily static/config-driven; offline auditing/generation instead of live heavy probability searches.
- Interiors use mostly static precomputed layouts; object budgets, no per-building tick, no unbounded physics or replication; only persist changes.
- Crafting is action-driven; no background full-inventory scans; server commits atomic mutations.
- Infected supplementary controllers update only relevant active entities; distance-/interest-based cadence with upper cap, action revalidation, sparse world event index.
- Hordes use lightweight abstract state when distant and actual infected only near legitimate observation; activation budgets, hysteresis and grace periods; no popping in view.
- Audio event propagation is sparse, deduplicated and bounded; no global audio-target loops.
- Batched persistence with bounded latency/write size and crash-safe recovery; no saving entire world per loot interaction.
- Network uses interest management and deltas; no broadcast of all building contents/horde history to every player.
- Cache immutable building class/room metadata, not unbounded runtime entities. Avoid premature pooling if lifecycle leaks and stale references can't be tested.

### 7.3 Perf gates and test methodology

A feature only merges if baseline and candidate test use same game build, map, mission, seeds, time/weather conditions where possible, client settings, hardware, game population, and scripted/player path; capture warmup time, fixed test duration, multiple runs, p50/p95/p99 and source commit. Require measurable no regression in pathing/collision/audio alongside raw performance. Where CI cannot execute DayZ, use local reproducible benchmark scripts and store result artifacts plus hardware fingerprint in private repo issue/PR.

## 8. Toolchain, deployment and repository design

### 8.1 Official toolchain

**Client/dev machine (Windows):** DayZ game, DayZ Tools via Steam (Workbench, Addon Builder, Central Economy Editor), DayZDiag executable, Git, Python 3.11+ (or otherwise supported), editor (Cursor/VS Code), PowerShell 7 optionally, a project drive `P:` if official docs require it. Verify current version requirements. Start with official DayZ Modding Basics and Workbench Script Debugging. Use file-patching in local diagnostic iterations, package/sign PBOs for normal client/server integration tests. **Do not enable file patching on public/prod servers.**

**Server machine (OS TBD):** Official DayZ Dedicated Server installed by Steam/SteamCMD, isolated profiles and writable storage, LAN/private connection, matching game version/mod manifest, saved configuration, log collection. A Windows dedicated server is the default low-friction test path until hardware/OS is known; determine current Linux compatibility separately if relevant. Do not expose RCon, admin credentials, game port or debug ports to the Internet by default; allow LAN traffic only as needed.

**Developer loop:** edit -> validate -> DayZDiag fast test and Workbench logs/debugger -> native PBO package -> deploy to dedicated server and client -> script/unit/data tests -> controlled multiplayer interaction -> profile/measure -> rollback if needed. Every change ideally has reproducible launch arguments and log/metrics capture scripts; never silently overwrite source CE configs.

### 8.2 Repository/module layout (proposed)

```text
/
  README.md
  NEXT_SESSION_PROMPT.md
  docs/{SPECIFICATION,RND_CAPABILITY_MATRIX,SETUP_AND_EXECUTION,TESTING_PERFORMANCE,DECISIONS_AND_RISKS,SOURCES}.md
  docs/adr/ADR-*.md
  research/experiments/EXP-*.md
  config/schemas/                    # custom validated data schemas, not game asset dumps
  config/presets/{baseline,playtest}/ # authored supplementary config/CE diffs after audit
  mission/                            # only authored overrides; no copy of full game
  mods/Core/                          # only when common code becomes necessary
  mods/Loot/
  mods/Interiors/
  mods/Crafting/
  mods/Infected/
  tools/{audit,simulate,validate,package,deploy,benchmark}/
  tests/{unit,static,fixtures,integration,performance}/
  metrics/                            # CSV/report schemas and baseline comparisons
  templates/
  .github/workflows/                  # cheap static checks only initially
```

Suggested prefix/class namespace `DZSO_` pending naming/license audit. Build individual PBO/mod packages only as needed; modular folder boundaries need not imply one independent Workshop item per feature. Avoid circular dependencies; `Core` should stay minimal. Custom metadata should identify compatible game build, schema and dependencies; verify actual `CfgPatches.requiredAddons` and `CfgMods` module registration in a successful smoke test.

### 8.3 GitHub, CI and release safeguards

- **Private GitHub**: repository user-owned, protect default branch, PR reviews and checks, semantic version tags, changelog and issue templates. No rights to Northmen proprietary packages assumed.
- **CI initial jobs:** Python syntax/tests, XML/JSON parsing + schema checks, economy diffs and duplicate type detection, recipe graph invariants, data-layout transform checks, docs links/manual checklist, license lint, secret scan; small, bounded action usage. No claim hosted GitHub runners have DayZ/game tools installed or legally distributable.
- **Local build and integration:** DayZ Tools + dedicated server live on your machines. If later using a self-hosted runner, secure it for untrusted PRs and cap job minutes/storage. Avoid cost surprises: concurrency limits, action budgets/alerts, cancel redundant builds, no expensive always-on workflows.
- **Signing/distribution:** Research Bohemia public-key/signature build workflow; keep private keys off Git, use locally managed secrets. Workshop publishing OFF by default, explicitly gated, with separate license/asset review.
- **Safe state:** backups before persistence schema changes, clean rollback to stock `mission` + versioned mod build, no unannounced wipe.

## 9. Detailed acceptance criteria, by layer

**Platform / tools**: vanilla dedicated server + separate client connected; config version logged; diagnostic script hello-world works; built signed PBO tested in non-file-patching normal client; server restarts without unexpected state reset; baseline metrics captured. No claims of success without actual run artifacts.

**Loot**: all sampled accessible test building types have valid eligible spawn-point or searchable opportunities; apartments/barracks demonstrably fixed; contextual distributions are believable and less repetitive; target acquisition difficulty calibrated against vanilla; rare-route logic not zero probability or ubiquitous; no obvious CE overload or duplicate allocation.

**Interiors**: >=3 validated layouts for one chosen residential class and >=2 different history archetypes; consistent per-instance setup, restart persistence, no obstruction; two clients see same props; no collision/nav regression; building remains discoverable and searchable.

**Crafting**: >=3 high-value repurposing recipes as pilot (one camo-net-related if feasible), no duplication and no profitable material loops, realistic condition/wear, interrupted action safe, two-client race safe.

**AI**: measure open-door navigation against vanilla; verify no magic target tracking, no unexpected through-wall attacks, audible movements; one methodical room search can be observed without exact location cheating; two distinct profiles with trade-offs; injuries alter movement in supported cases; reliable fallback when native path fails.

**Hordes and alerts**: one gunshot can produce local bounded chain reaction, horde attracted only if cue is physically plausible, persistently roaming group state and safe activation/deactivation, two observers see consistent location/size, no visible pops/teleports, defined global cap. Test network/persistence/restarter race scenarios.

**Performance**: feature budget under agreed target load, no unbounded loops/objects/RPC storms; benchmark record for each milestone, healthy p95/p99 latencies, functional fallbacks when overloaded. Safety/fairness never disabled to gain FPS.

## 10. Delivery phases and dependency ordering

- **P0 — R&D and environment:** establish repo (private), local tools, server/client, version/profiles, source/capability matrix, vanilla baseline. **Exit:** documented logs and a successful minimal mod load + reconnect.
- **P1 — Native CE coverage:** audit all relevant buildings, focus apartments + white double bunk-bed military barracks; edit spawn points/overrides; profile CE. **Exit:** controlled evidence loot opportunities exist without chronic inflation.
- **P2 — Static interior prototypes:** 1 residential building, 3 compatible layouts, fixed object budgets, new searchable interactions behind feature flag. **Exit:** persistent identity, safe navigation and two-client consistency.
- **P3 — Loot realism & economy balance:** contextual categories, weighted archetypes/rarity, seasonal/event rules only when justified, simulator and CE accounting. **Exit:** measured satisfying gameplay; no loot faucet.
- **P4 — Crafting & salvage:** native recipe/action extensions, tools/wear/material conservation, 3 pilot chains and scalable registry. **Exit:** multiplayer-safe atomic transactions and clean client feedback.
- **P5 — Infected competence/physics baseline:** record vanilla bug matrix for doors, LOS, sound, injury; evaluate existing mods as references, then implement smallest tested improvements. **Exit:** measurable gains without new magic physics or worse navigation.
- **P6 — Investigation and variants:** methodical search, behavior blend, stealth trade-offs, injury mobility; fallbacks. **Exit:** player can plausibly hide/escape and encounter distinct but fair infected.
- **P7 — Local chain reactions and dynamic hordes:** bounded audible alert graph + abstract/dynamic horde controller, avoid duplicate vanilla infected counts. **Exit:** reproducible multi-client horde interactions and controlled perf.
- **P8 — Integration / stress / polish:** combine scavenging noises, histories, loot, crafting and infected; regression suites, migration and rollback, license/publication audit. **Exit:** user-approved playtest profile and acceptance record.

P5 *research* should run in parallel with P1/P2 (risk-first). P7 should not be fully implemented before native navigation/behavior feasibility is measured. Each phase uses short experiments and a stop/go gate to avoid sinking effort into impossible engine behavior.

## 11. Explicit unresolved inputs vs default assumptions

The preferences above are complete for first R&D; no need to re-interview before beginning. Exact values below are intentionally **not fabricated**:

1. Server CPU, RAM, OS, storage, network, client specs and which machine runs DayZ Tools; confirm before performance threshold calibration. Two machines known, specs unknown.
2. Planned target player count, intended maximum simultaneous infected, horde sizes and desired median vs p99 performance; first take vanilla benchmark then propose budgets.
3. Final map(s); Chernarus first is a reasonable default, not explicitly locked.
4. Specific loot/item pain points by classname, inventory mods/version and preferred rarity multipliers; gather during economy audit instead of guessing.
5. Public-facing mod name, repository owner/name and licensing choice; choose private repo name during setup; do not invent repository link.
6. Whether existing BaseBuilding/CodeLock/other Workshop mods should be included in compatibility matrix (not needed for vanilla-first P0); no permission to bundle Northmen Core.
7. How many building classes to support before alpha and which archetypes to ship; choose after coverage audit and performance feasibility.
8. Desired seasonality, rare event frequency, scavenging respawn policy, server wipe rules and horde migration style; use conservative pilot defaults as documented experiments, not permanent assumptions.
9. Max extra installed size/download budget and acceptance of any custom non-vanilla visual assets; default none.

**Important:** Unresolved values do not block P0/P1 R&D. A blocked engine capability should generate an experiment report and decision record, not endless speculative code.

## 12. Next-session operating instruction

The next session should execute the checklist in `NEXT_SESSION_PROMPT.md`. It must not claim the private repository was created, the server connected, or engine behavior verified unless an actual connector/local run proves it. R&D must produce evidence cards, tool versions, capability matrix updates, and prioritized first issues, then set up the dev/server environment, run baseline, plan implementation, code, test, profile and report gates. Prefer tested official mechanisms at every step. Every nontrivial custom feature must carry its acceptance tests and performance measurements in the same change.
