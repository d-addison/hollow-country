# Testing, Verification and Performance Engineering Plan

**Applies to all modules, including the shared support layer.** All game behavior claims need a real client/server test. Offline Python simulations validate authored logic, not DayZ's native CE, physics, navmesh, replication or client audio.

## 1. Testing pyramid and environments

| Layer | Tool/environment | Can prove | Cannot prove |
|---|---|---|---|
| T0 static/schema | Python/standard XML/JSON validators, unit tests | Syntax, types, unknown keys, recipe cycles, deterministic sampling, config integrity | Actual DayZ loadability or runtime effects |
| T1 offline simulation | Seeded Python reference models | Expected distributions, invariant checks, algorithm cost trends, deterministic replay | Native CE restock, collision, infected and client sync |
| T2 DayZDiag | Workbench/Diag local diagnostic | Enforce Script behavior, profiling, CE tool fixtures, some movement and asset visibility | Real dedicated two-client network behavior |
| T3 dedicated LAN | Separate server + normal DayZ client(s) | PBO load, actual CE, persistence, network authoritative actions, performance | Full real-world population unless load is representative |
| T4 multiplayer adversarial | At least two simultaneous clients, controlled latency | Race/dupe, synchronization, different view/audio, horde behavior | Large server scale without supplemental load |
| T5 endurance/performance | Dedicated server and representative load/route | Resource leaks, CPU spikes, persistence inflation, scalability | Unsupported future DayZ game versions |

Test combinations: `vanilla`, `CE-only`, `interiors-only`, `crafting-only`, `AI-only`, `hordes-only`, `all on`; perform an optional compatibility set with common Workshop mods only after core vanilla tests pass.

## 2. Fixture control and reproducibility

Every run stores game build, server and client executable versions, git commit, exact mod/PBO hashes, mission, map, economy files/hashes, machine hardware/OS, player count, actual active infected and object counts, weather/time, test location/class, RNG seed where controlled, tool/log settings, warmup and sample duration. Run same route/scenario multiple times; DayZ CE and AI have uncontrolled stochastic/native states, so use observed distributions and confidence intervals rather than claiming identical execution from a custom seed.

Canonical baseline fixtures:

- **MAP-APT:** identified apartment block with multiple floors and known poor vanilla loot coverage.
- **MAP-MIL:** identified white double military bunk-bed barracks type, actual classname to be confirmed.
- **MAP-HOME:** small vanilla house with kitchen, bedroom and at least one exterior door.
- **MAP-GAR:** shed/garage/industrial workshop.
- **MAP-DOOR:** open doorway with reproducible player lure, obstacles and approach angles.
- **MAP-STREET:** gunshot chain reaction region with controlled infected population.
- **MAP-HORDE:** player-visible and out-of-view horde transitions along tested world route.
- **MAP-AUDIO:** surfaces/interiors, corridors/stairs, sound occlusion test points.

Do not publish invented coordinates; fill in fixture file from installed game exploration.

## 3. Functional test catalog (priority keyed IDs)

### Native CE, loot coverage and progression

| Test | Scenario | Pass criterion |
|---|---|---|
| CE-001 | Vanilla CE baseline manifest | Known input files parsed and versioned; no silent missing files |
| CE-002 | Minimal override to one test item | DayZ loads new file, controlled change observed, no CE error |
| CE-003 | Apartment class coverage | Non-zero tested eligible loot opportunity, correct type and placement |
| CE-004 | Double-white bunk barracks coverage | Same as CE-003; classname and geometry verified |
| CE-005 | House and garage context | Item category distribution plausible by room/use and approved exceptions |
| CE-006 | Scarcity routes | For each essential, ≥2 plausible acquisition contexts in design; observed chance >0 in controlled samples |
| CE-007 | High-tier progression | More likely in high risk vs low risk by design, but rare exceptions still possible |
| CE-008 | Item diversity | Repeated top-common items not consuming nearly all useful opportunities; thresholds set after baseline |
| CE-009 | World economy caps | No uncontrolled high-tier item inflation when optional search loot enabled |
| CE-010 | Loot reset | Restart/reconnect doesn't duplicate items or refill depleted container |
| CE-011 | Invalid config | Validator rejects malformed XML, negative values, unknown/duplicate entries where checks exist |
| CE-012 | Outdoor areas | Outdoor area inventory audit finds valid opportunities without blanket random drops |

### Interiors, placement and searching

| Test | Scenario | Pass criterion |
|---|---|---|
| INT-001 | Same building class, different instances | At least two different validated themes/layout IDs observed |
| INT-002 | Repeat startup with same world state | Same layout/ID and correct object count (no duplicates) |
| INT-003 | Restart after search | Correct depletion/remaining objects, no new materials generated |
| INT-004 | Player and infected door/stairs | No new blocked path/door swing; compare against same vanilla building |
| INT-005 | Floor/terrain placement | No object below floors, buried in terrain, suspended or clipping walls |
| INT-006 | Two-client sync | Both see same furnishings, search state and loot result |
| INT-007 | Simultaneous searches | Exactly one claim or documented split semantics; no dupe |
| INT-008 | Full/inaccessible cupboard | UI reports no access/empty appropriately, action not triggered through wall |
| INT-009 | Player proximity lifecycle | No visible pop-in or disappearance, no reset during reload |
| INT-010 | Object budget | All test layouts comply with per-building collider/entity/replication cap |
| INT-011 | Building class not supported | Clean fallback to vanilla, no crash or misplaced object |

### Crafting, conservation and abuse

| Test | Scenario | Pass criterion |
|---|---|---|
| CRF-001 | Camo net conversion pilot | Authorized tools/inputs consumed and outputs delivered as actually supported |
| CRF-002 | Incorrect/missing/ruined tools | Reject or appropriately degrade; no free product |
| CRF-003 | Craft cancellation or death | Item state consistent, no committed output without required input |
| CRF-004 | Two clients craft on same material | Only one valid successful transaction |
| CRF-005 | Full inventory / disconnect | Item delivered through justified fallback or action aborted atomically |
| CRF-006 | Conversion graph | No infinite cycle with net positive useful resource or durability value |
| CRF-007 | Recipe and inventory compatibility | No broken stacks/attachments, all output classes exist |

### AI perception, physical fairness, doors, searching, injury

| Test | Scenario | Pass criterion |
|---|---|---|
| AI-001 | Open doorway, repeated approach angles | Entry success vs vanilla measured; no custom regression, stuck events quantified |
| AI-002 | Closed/unlocked door by variant | Only specified profiles may open/force; physically visible/audible and consistent |
| AI-003 | Locked/blocked door | No inexplicable open/phase; base locks respected per rules |
| AI-004 | Line-of-sight loss | Search last-known observed position, not hidden moving player location |
| AI-005 | Methodical building search | Visits viable nearby anchors; doesn't teleport, silently materialize or know exact hide spot |
| AI-006 | Legitimate player escape | Quiet LOS break/diversion sometimes succeeds; no unbounded pursuit from cheat state |
| AI-007 | Variant trade-offs | Stalker is measurably quieter/slower, forceful infected louder/slower, randomized differences bounded |
| AI-008 | Leg damage/crawler | Actual supported animation/state and movement change, no normal sprint on destroyed legs |
| AI-009 | Server restart/profile | Transient agents recover gracefully; no broken memory/target references |
| AI-010 | Native path fails | Safe fallbacks, never teleport/no-clip through solid object |
| AI-011 | Hit through wall | No new damage through solid collision; record inherited engine defect separately |
| AI-012 | Two-client observation | Same meaningful door/injury/attack result, no desync exploit |

### Audibility and advanced stealth

| Test | Scenario | Pass criterion |
|---|---|---|
| AUD-001 | Walk/run/crawl on concrete/wood/grass | Physically appropriate event perceived on two clients where native supports |
| AUD-002 | Stairs, landing and open door approach | No unexplained silent approach attributable to our changes |
| AUD-003 | Behind closed door/wall | Occlusion/attenuation plausible, not obviously omnidirectional 'magic' audio |
| AUD-004 | Stealth stalker | Lower realistic sound/activity from slower motion; never unconditional zero-volume |
| AUD-005 | Door bashing | Audible hit follows actual contacts; no loop without animation/contact |
| AUD-006 | Source/distance | Sound linked to correct origin and distance, not duplicated every tick |
| AUD-007 | Known engine bug surface | Classify inherited 1.30 missing sound issue; do not falsely mark fixed |

### Chain reactions, horde logic, pop-in and fairness

| Test | Scenario | Pass criterion |
|---|---|---|
| HOR-001 | Local gunshot reaction | Bounded local infected/hearing radius reaction, realistic delay |
| HOR-002 | Infected vocalization chain | Nearby recipients alert; hop/TTL/cooldown cap prevents infinite propagation |
| HOR-003 | Indoor scavenging noise | Audible action attracts eligible nearby agents without omniscience |
| HOR-004 | Horde roam | Record moves/updates coarse-grain, same group ID persists |
| HOR-005 | Horde responds to genuine cue | Moves toward cue within physical path constraints, not exact player coords |
| HOR-006 | Two observer visibility | No forced spawn/despawn/teleport within either player's view |
| HOR-007 | Hysteresis/return | Repeated radius crossing doesn't respawn or lose members incorrectly |
| HOR-008 | Global entity cap | No unlimited infected growth or activation spike under multiple stimuli |
| HOR-009 | Restart while roaming | Saved logical record reloads, no doubling members/loot |
| HOR-010 | Native CE interaction | Horde activations don't silently bypass global population limits |
| HOR-011 | Overload degradation | Degrade simulation detail or defer activity, never skip fundamental sound/collision |

### Networking/persistence/security

| Test | Scenario | Pass criterion |
|---|---|---|
| NET-001 | High latency/delayed RPC | Server validates action and returns consistent state |
| NET-002 | Packet duplication/retry | Idempotent request, no duplicate loot/craft/horde action |
| NET-003 | Disconnect during search/craft | Atomic state recovery; no 'half consumed' unrecoverable state |
| NET-004 | Concurrent late join | Client learns relevant state without downloading entire building database |
| NET-005 | Persist crash/restart | Backups/migrations work, corruption doesn't silently erase world |
| NET-006 | Wrong config/schema | Fail safely with clear error, disable affected subsystem rather than corrupting state |
| NET-007 | Malicious arbitrary item request | Invalid remote item/action blocked at server |
| NET-008 | Server-only secrets | No private credentials in repo/client package/logs |

## 4. Performance benchmark plan

### Critical metrics

- Server: frame time p50/p95/p99, frame FPS (if available), spikes, CPU/thread usage, memory baseline and leak slope, script time, per-function call counts and allocations, entity count, active collision/physics objects, network data rate and packet/replication size, CE warnings/queues, startup and restart duration, persistence write volume/latency.
- Client: avg FPS, 1% low frame rate, stutters, CPU/GPU/RAM, network RTT/packet jitter, asset/object streaming/visible pop-in, audio concurrency.
- Behavior: infected successful path completion rate, time to reach doorway, stuck rate, target reacquisition false positives, audible cue detection, horde max active/abstract ratio, number of prompts/search actions per building, item rarity/progression outcomes.

### Representative scenarios

1. **B0 vanilla idle:** empty stock mission and known fixtures, no added mods.
2. **B1 vanilla town traversal:** controlled movement through built-up area with existing infected/loot.
3. **B2 CE-only economy:** same world/test, added spawn points and CE overrides only.
4. **B3 interior object sweep:** 0, 5, 10, 20 (or safer) added tested props per building; observe slope.
5. **B4 scavenging burst:** 2 players search multiple sites concurrently, observe authority and write spikes.
6. **B5 infected active town:** baseline infected then new variant logic, at equal active count.
7. **B6 chain-reaction stress:** repeated gunshots/door bangs; confirm bounded recipients and no runaway loops.
8. **B7 horde distant/near transitions:** abstract and materialized states, visibility, CPU spikes and network.
9. **B8 full integration:** all modules enabled, multi-hour endurance with representative actions and restarts.

### Provisional nonbinding targets

| Metric | Initial hypothesis | How to set final gate |
|---|---|---|
| Overall server FPS | Aim for stable 60 FPS if stock server hardware can sustain | Determine vanilla median and p95 under planned population; user approves |
| Added steady-state server frame time | ≤5% regression vs calibrated vanilla scenario | Review spikes and confidence intervals, not just average |
| Full-world continuous scans | Zero needless per-frame scans | Code review + profiler call count |
| Idle interiors | Near-zero per-frame compute | Compare idle cost with/without placements |
| Active infected | Global cap required, actual number TBD | Determine server hardware capacity and game feel |
| Alert propagation | Finite TTL/hops/recipient caps | Tune with stress; no exponential queue growth |
| Player-visible horde spawn/despawn | Zero **introduced** pop-ins in controlled observation tests | Two-client recordings and replay |
| Duplicate loot/crafting on race | Zero | Adversarial multi-client tests |
| Movement/door physics cheats | Zero **introduced** cases | Video/hit logs + native control group |

**Important:** Benchmarks cannot be meaningfully judged before machine specs, target players and vanilla baseline exist. Do not call a feature 'optimized' because a code path is O(1) while it causes expensive engine entity/network work.

### Statistical/reproducibility notes

Use multiple runs, paired comparisons when practical, warmed-up and cold-start separately, plot distribution rather than averages only; report sample counts and uncertainty. Entity spawning and CE are stochastic; custom seeded simulations supplement, not replace game observation. For a claimed improvement in doorway navigation, compare success counts by building/door/angle and error class against vanilla, not just aggregate success. Profile excessive logs as a potential confounder; production verbose diagnostics should be disabled or sampled.

## 5. Failure policy and triage

**Release blockers:** duplication, irreversible persistence loss, nonrecoverable server crash, client action bypass, dramatic frame spikes, nonphysical teleport/attack, silent approaches **introduced or amplified by our logic**, unavoidable player-observable horde pop-ins, blocked entry paths from new interiors. **Potential engine-limited known issue:** vanilla audio/nav bugs which cannot be safely fixed by exposed mods; keep comparison evidence and don't falsely claim resolved. If a feature cannot be implemented within constraints, de-scope that feature after an ADR—not the physical rules.

Triage severity: Critical (crash/dupe/data loss/physics-cheat/performance collapse), High (consistent broken interaction/path/audio, major desync), Medium (specific layout/loot imbalance, rare path stalls), Low (cosmetic/diagnostics). Each bug has version, steps, fixtures, logs/videos, source commit and baseline comparison.

## 6. Test evidence and automated jobs

For every PR attach: changed configuration and source hashes; T0 static tests; relevant T1 simulation summary; T2/T3 reproducible run; **two-client** evidence for network/audio/visibility features; B* benchmark CSV with before/after and exact hardware. A GitHub workflow may run T0/T1 cheaply, but T2–T5 remain local/manual or on a secured compatible self-hosted runner after setup. Do not mark T2–T5 automated until proven executable.

CSV schemas are supplied in `metrics/benchmark-template.csv` and `metrics/loot-evaluation-template.csv`. Repeated trials and perf graphs should be archived with references/hashes rather than committing gigabytes of raw videos/logs.
