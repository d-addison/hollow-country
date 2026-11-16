# R&D Capability and Reuse Matrix

Execution update, 2026-11-16: client and dedicated server binaries inspected at
1.30.164289; DayZ Tools/Server installed by user on D:. These are inventory
observations only: **no engine CAP row promoted**. See
`../research/P0-build-inventory.md` and
`../research/official-sources-2026-11-16.md` for pinned upstream hashes, exact
documentation support and limitations. Local server first, 3–6 players; two
simultaneous clients still required for network/audio/visibility acceptance.

**Purpose:** prevent speculative rewriting of systems DayZ already supplies. **Initial status: documentation verified ≠ engine behavior validated**. The next session must fill experiment IDs with local evidence before coding custom systems. This matrix is a living tracker.

## Evidence levels

- **D — Documented:** exact official documentation / changelog supports existence or mechanism.
- **O — Observed:** tested on our installed build, reproducible command and logs/screenshots included.
- **P — Prototyped:** small controlled implementation works with defined benchmark and multiplayer behavior.
- **A — Accepted:** regression and performance gates pass in production-like game launch.
- **B — Blocked:** demonstrated engine/API obstacle; workaround or de-scope decided in ADR.
- **H — Hypothesis:** existing docs are insufficient or indirect; not assumed usable.

For every feature, record: version, source, test, `Docs / Observed / Prototype / Accept / Blocked`, performance cost, multiplayer risk, whether stock settings suffice, and a rollback. Templates in `templates/EXPERIMENT.md`.

## Engine/tooling first-pass matrix

| ID | Objective | Existing surface to explore FIRST | Initial evidence | Short R&D test | Decision rule |
|---|---|---|---|---|---|
| CAP-01 | Official CE override | `cfgeconomycore.xml` `<ce>` + mission XML | D | Small `types.xml` override changes controlled item | If works, no duplicate CE spawn system |
| CAP-02 | Item rarity/tiers | `db/types.xml`, usage/value and count flags | D | Document 10 troublesome classes and spawn distribution | Prefer config before scripted balancing |
| CAP-03 | Empty building coverage | `mapgroupproto.xml`, CE editor and DayZDiag Loot Spawn Edit | D | Count and edit apartment / white military barracks spawn points | Prefer official loot point modification |
| CAP-04 | World event loot | CE `events.xml`, `cfgeventspawns.xml` and dynamic events | D | Create stock-style event in isolated test mission | Avoid separate event scheduler unless needed |
| CAP-05 | Random cargo/attachments | `cfgspawnabletypes.xml`, `cfgrandompresets.xml` | D | Change compatible item cargo pattern and verify | Reuse if contextual variation sufficient |
| CAP-06 | Gameplay JSON | `cfggameplay.json`, `enableCfgGameplayFile=1` | D | Add one harmless setting, confirm applied | Avoid custom handling for exposed option |
| CAP-07 | Object Spawner | `objectSpawnersArr`, JSON object placement | D | Static 5-prop building with two clients and restart | Good for fixed authored layouts, not procedural by itself |
| CAP-08 | Low-cost static entities | 1.30 `disableSimulation` for house-based entities | D for patch note, H for application | Compare entity overhead/collision/client sync | Only use when exact object class supports it |
| CAP-09 | Built-in furniture interactions | Action target/selection of existing building geometry | H | Can a client target a cupboard/fridge inside a specific building? | If no, try limited proxy; don't claim universal support |
| CAP-10 | Building stable identity | World classname + position/rotation and mission data | H | Restart and verify stable identity, duplicates, quantization | Persist layout only after robust ID established |
| CAP-11 | CE accounted custom search loot | CE API / count flags / controlled additive ledger | H | Confirm custom allocation impacts economy correctly | If not, use conservative separate bounded budget |
| CAP-12 | Craft recipes/actions | Official game actions and RecipeBase-like mechanisms | H until tested | Basic tool+material->output, interrupted action | Extend native rather than build custom UI |
| CAP-13 | Infected leg damage/crawling | Current `ZombieBase` scripts, hitpoints and native animation | H (historical source exists) | Shoot leg; observe transition/restart/sync | Reuse existing transition when reliable |
| CAP-14 | Infected open doorway navigation | Native AI / building navmesh | D for known limitations | 100 trials in multiple houses; compare control | Do not custom pathfind without demonstrable access |
| CAP-15 | Door state / unlock / opening | `Building` script API and native door logic | H | Door index detection, vanilla lock vs barricade, two clients | Separate door interaction from navigation |
| CAP-16 | AI event hooks | infected stimulus / damage / attack / movement hooks | H | Instrument native events without invasive tick | Use native hooks if accurate; no global polls |
| CAP-17 | AI LOS/last-seen info | Actual Enforce Script/perception exposure | H | Does API provide observed location, not truth? | No cheat using current player position after LOS lost |
| CAP-18 | Audible action events | actual sound vs AI hearing and footstep events | H | Two-client recorded audio with motion/surfaces | Only patch where presentation can be fixed |
| CAP-19 | Group and local alerts | Vanilla infected calls, audio radius, CE zones | H | Trigger vocalization; measure nearby reaction | Prefer native behavior; bound custom cascade |
| CAP-20 | Roaming horde foundations | CE event/zone controllers and server entities | H | Group spawn/movement/despawn persistence | Build abstract controller only if native config can't meet goal |
| CAP-21 | Multiplayer replication | CfgMods, native RPC/sync, class events | D for mod structure; H for specific API | Two clients same search/door/horde action | Server commits, client mirrors |
| CAP-22 | Save/persistence | CE Hive and custom server profile serialization | H | Restart, crash/recover, version changes | No unvalidated high-volume custom DB writes |
| CAP-23 | Script profiler | DayZDiag Script Profiler | D | Capture time/call counts/allocations from sample script | Include in every feature benchmark |
| CAP-24 | CE diagnostic exports | DayZDiag Loot Spawn Edit, CSV economy exports | D | Export, compare, parse on local project | Build off-engine audit around exported truth |
| CAP-25 | Dedicated server telemetry | `serverDZ.cfg`/logs/diagnostic options | D | Capture server FPS, crash/CE logs, profile data | Verify exact option flags before scripts are generated |
| CAP-26 | Fast iteration | Workbench + DayZDiag file patching | D | Change harmless script and observe recompile/reload | Use only in trusted local dev |
| CAP-27 | PBO build/sign | DayZ Tools Addon Builder and mod loading structure | D | Tiny mod builds, signs, loads on client + server | Gate production testing on a real PBO |
| CAP-28 | 1.30 collision/nav issue | Official current patch known issues | D | Baseline buggy doorway and surface routes | File engine report, avoid unphysical workaround |
| CAP-29 | External behavior mods | Zen's Zombie Door Bangers, InediaInfectedAI etc. | H for current license/compatibility | Benchmark in isolated unmodified mission | Reference or optional dependency; don't copy protected assets |
| CAP-30 | Multiplayer load simulation | Native simulated player config/other tools | D for config parameter, H for realism | Validate available version and representative scenario | Never equate synthetic clients with actual players |

## Critical research tracks, in execution order

### Track A — Engine/platform assumptions, *blocking P1*

1. Read installed 1.30 stable scripts and official Modding Basics; create first test PBO and a two-machine LAN server. Capture actual executable build and mod log.
2. Extract CE snapshot legitimately through official tools and compare with public licensed reference. Record which files can be extended via `ce` folder, and how group prototypes/positions are updated without whole-mission copy.
3. Identify exact apartment and barracks building classnames and map locations in *actual* Chernarus installation. Don't guess prefab classnames from user nickname.
4. Confirm `Diag Menu` commands necessary for editing only work under diagnostic single-player CE and which export paths they use.

### Track B — Navigation/audio feasibility, *timebox before building P5/P7*

1. Choose 3–5 vanilla houses/barracks with different door layouts; capture approach trajectories and trigger states. Test open doorway entry from multiple angles with multiple infected types; record entry rate and stuck incidents.
2. Compare door closed/unlocked/locked states, building class/door index mapping and access controls; do not bypass base security.
3. Record footstep and voice cues at fixed distances inside/outside on two clients. Separate no audio from spatial occlusion, animation and attenuation bugs.
4. Shoot/hit infected legs under repeatable condition and determine if native crawling synchronizes, persists to death, changes velocity and attacks properly.
5. Evaluate existing AI mod separately on same fixtures, no other gameplay mods; check license, current 1.30 compatibility, memory and active-infected count.
6. Create feasibility ADR before promising native navigation improvements, smart indoor waypoint pathing, new crawling variants, or per-surface footstep patching.

### Track C — Interiors search feasibility, *blocking Level 4*

1. Inventory all accessible target building classes/anchors; classify baked furniture versus existing movable/pickup objects.
2. Test built-in furniture interaction targets; determine if action can identify site without networking an entity per drawer.
3. Author one layout with only tested prop classes, check floor offsets, door arcs, stair widths, roof/wall clipping, navmesh and two-client synchronization.
4. Restart with players absent/present; verify persistent identity and no duplicates.
5. Measure cost per added prop (client 1% low, server frame, replication, RAM); use slope estimate to size entire-map ambition before mass placement.

### Track D — CE loot accounting, *blocking significant custom loot*

1. Quantify default CE count flags, restocking and spawn point availability; never infer item rarity solely from `nominal`.
2. Change one item's eligible location in override; inspect observed occupancy in controlled condition after correct economy refresh/persistence handling.
3. Prototype a 'searchable' pre-allocated item with irreversible local claim; test exactly-once with two clients and server restart.
4. Compare world item budget against vanilla and a custom simulation. Establish policy for keeping custom items from inflating CE's effective economy.

## Risk-led stop/go rules

- If infected cannot be directed through a particular doorway due to native navmesh and script hooks provide no correction, **do not implement teleports, no-clip movement or direct target-coordinate chasing**. Mark blocked, minimize furniture collision and ship a truthful AI subset with measurable gains.
- If client footstep audio is missing in native engine and no supported audio hook can repair it without duplicates/desync, log known limitation, investigate file a bug, and do not present a partial patch as a full physics fix.
- If custom search loot cannot be atomically persisted and counted against budgets, defer release of the search loot feature; ship static CE improvements first.
- If dense furnishing or persistent hordes exceed frame-time/network budget, reduce active counts/visual complexity before hacking around with invisible spawns or gameplay cheats.
- If Workshop dependencies require unauthorized reupload/repack/modify rights, do not include them; either use them unmodified under terms, build independent permitted behavior, or omit.

## Sources / version notes

See [SOURCES.md](SOURCES.md). Most reliable: Bohemia Modding Basics, Modding Structure, Central Economy Configuration, mission-file modding, Gameplay Settings, Object Spawner, Diag Menu, Workbench Script Debugging, Server Configuration and PC 1.30 patch notes. Treat third-party projects as leads until locally tested.
