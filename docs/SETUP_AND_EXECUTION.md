# Setup, Configuration, Implementation and Execution Runbook

**Audience:** the next engineering/R&D session. **State:** no private repo, local installation, compile, server or playtest was created during this handoff. All commands must be checked against the installed DayZ build and paths. Follow official instructions before automation.

## Guiding order

**R&D -> working environment -> stock baseline -> smallest native override -> actual testing -> feature-by-feature implementation -> integration -> performance optimization -> optional publishing.** If a phase fails, stop and document the reason; do not construct more layers on an unproven engine assumption.

## Day 0: GitHub private repo and safety controls

1. Create **private** GitHub repo under user's chosen account/name (explicit connection and auth required). GitHub may not yet be connected; package can be imported manually without changing this design.
2. Import this handoff including `.gitignore` and templates; do not include proprietary DayZ PBOs, game exports, complete third-party mod distributions, or credentials.
3. Turn on issue tracking; use `research`, `engine-blocked`, `config-only`, `scripts`, `performance`, `multiplayer`, `critical`, `license-review` labels. Protect `main` and use small reviewable branches/PRs.
4. Create initial ADR issues and milestone list P0–P8. Source `docs/SPECIFICATION.md` requirement IDs; every issue gets test/performance acceptance.
5. Ensure `.gitignore` includes `profiles`, logs, Steam installations, project drive, build outputs, RCon credentials, signing keys; place private values in machine-local `.env` (see `.env.example`).
6. Prefer conventional commits, changelog and automated test status; configure hosted GitHub Actions **only** for low-cost static validation after scripts exist. Limit concurrency/jobs and set cost alerts. The game/binaries are not assumed available on GitHub-hosted runners.
7. Establish legal inventory before copying source snippets: CE source repository license ADPL-SA; game assets and Workshop licenses have independent terms.

### Initial issue backlog, in the order that saves most wasted work

| ID | Deliverable | Definition of done |
|---|---|---|
| ISSUE-001 | Game/tool/server version inventory | Exact builds, install roots, paths, machine specs, available disk, source URLs |
| ISSUE-002 | LAN dedicated server baseline | Separate client joins, reconnects, logs, stock mission loads, no mods |
| ISSUE-003 | Diagnostic dev mode and minimal custom PBO | Script runs with file patching and after packaging in dedicated server |
| ISSUE-004 | Vanilla performance baseline | Repeatable test scenario + p95/99 and client FPS captured |
| ISSUE-005 | CE sources/diff and inventory | Correct 1.30 official files and field descriptions imported by reference, not proprietary dumps |
| ISSUE-006 | Apartment & barracks class identification | Verified classnames, locations, actual spawn points and sample observations |
| ISSUE-007 | AI doorway/footstep/injury baseline | Repeated reproducible test matrix and engine limitations |
| ISSUE-008 | First CE-only loot correction | Diffable override and tested spawn opportunities, no duplicate inflation |
| ISSUE-009 | Interior layout small prototype | 3 layouts for one existing house, perf and restart safety |
| ISSUE-010 | Searchable interaction technical spike | One cupboard/site: two clients, exactly-once claim |
| ISSUE-011 | First salvage recipe spike | One realistic new use of existing item; no material cycle |
| ISSUE-012 | AI behavior hooks and safe fallback | Event/door/sensory hooks measured and documented |
| ISSUE-013 | Bounded horde and alert design proof | Logical record, local audible propagation, non-pop-in activation |

## Stage P0a: Inventory machines and versions

Create `research/environment-2026-11-XX.md` containing:

- Client/dev machine CPU/GPU/RAM, OS build, Steam install, game version, tools version, free storage, monitor FPS settings.
- Dedicated server machine CPU/RAM/storage/OS, hostname and LAN IP (never include address/password in a public artifact), dedicated server build and install path, profile path, firewall status.
- Network link, latency, LAN ports, test account availability, admin access, backup location. Use a private LAN or VPN only if separately configured—do not publicly expose debug ports or RCon.
- Record pinned mod list as **vanilla** initially. Do not require Northmen-specific mods or a public community server.
- Timezone, command-output logs, local file encoding/path conventions and exact reproducible launch arguments (redact secrets).

**Default if user provides no OS:** use Windows dev machine with Steam DayZ Tools; Windows dedicated server as first documented path. If Linux server is desired, separate discovery for current release and exact compatible server build before designing PowerShell deploy scripts.

## Stage P0b: Install and smoke-test official tools

1. On Windows dev machine, install **DayZ**, launch once, and install **DayZ Tools** from Steam. Locate Workbench, Addon Builder, Central Economy Editor and `DayZDiag_x64.exe`. Follow [Bohemia Modding Basics](https://community.bistudio.com/wiki/DayZ:Modding_Basics) to build the `P:` project drive and configure File Patching.
2. Install **Git** and Python for offline audit/test utilities. Use editor of choice (Cursor/VS Code). Prefer official Workbench for DayZ script debugging. Optional third-party VS Code language tools should be evaluated for maintained support, not assumed mandatory.
3. On server machine, install official **DayZ Dedicated Server** and create a stock ChernarusPlus mission copied according to the official server documentation (not by copying unneeded game assets into Git). Set explicit profile and storage paths. Set password/access policy as required for LAN testing; firewall restricts to known LAN hosts.
4. Start vanilla dedicated server and join from dev client with the exact same game build. Confirm connect, respawn, inventory interaction, persistence through restart, and log location.
5. Follow [Workbench Script Debugging](https://community.bistudio.com/wiki/DayZ:Workbench_Script_Debugging) to launch DayZDiag and connect debugger in a test mission. For local diagnostic work, official docs demonstrate `-filePatching` and `-server -config=serverDZ.cfg`; **use them only in the appropriate local test context**, not generic production launch advice.
6. Create a **minimal authored mod**, based on [Modding Structure](https://community.bistudio.com/wiki/DayZ:Modding_Structure), with `config.cpp`, `CfgPatches`, `CfgMods` and one harmless log action. Validate script compile/load. Package with official Addon Builder and test the PBO on both normal client and dedicated server. Verify signatures and permitted keys workflow separately before relying on `verifySignatures`.
7. Capture engine/server logs, exact command lines, and screenshot/video showing successful two-machine join and script initialization. If unable, block implementation until environment works.

**Success artifacts:** `research/P0-build-inventory.md`, `research/P0-server-launch.md`, `research/P0-first-mod.md`, initial perf CSV, and `CAP-01/21/26/27` rows updated to Observed.

## Stage P0c: Baseline and diagnostic fixtures

Create a small list of **verified locations and building classnames** in actual ChernarusPlus: two residential houses, one apartment building, the double white military barracks type, one industrial garage and an open outdoor area. Capture coordinates privately, classnames, door counts, corridor widths and floor levels. Do not invent from internet nicknames. Separate pristine no-custom-object mission, economy-only test mission, and later feature test mission.

Baseline test conditions:

- One player, then two clients where available. Warmup and repeated identical route; fixed mission/time/weather and graphics where possible.
- Count original loot opportunities, actual visible item outcomes and low-value duplicates. Record items whose acquisition seems artificially rare; inspect CE flags and limits.
- 100+ repeat trials for a key doorway case where practical, multiple classes; alternate infected type, approach angle and door state. Record success/stuck/time and audio.
- Record p50/p95/p99 server frame time (or closest telemetry) and client 1% low frame rate, RAM, CE logs, active infected/objects.
- Store baseline results with SHA/version and timestamp; choose target player count only after hardware/perf capacity measured.

## Stage P1: Native CE changes before custom loot

1. Copy official original CE files into a **non-Git working path**, record version/hash and legal source. Parse `types.xml`, `mapgroupproto.xml`, `mapgrouppos.xml`, `cfgspawnabletypes.xml`, `events.xml`, `cfgeconomycore.xml` into offline audit utilities.
2. Export a building coverage report; distinguish inaccessible decor, world model only, known aliases and true 0-eligible-point buildings. Rank apartment and double-white military barracks top.
3. Verify exact classnames and spawn point deficits in DayZDiag. Follow CE Loot Spawn Edit instructions **in a diagnostic client with CE**, because some tools don't work in multiplayer.
4. Add a minimal, separate CE override via documented mission-file extension in `cfgeconomycore.xml`. If needed, export group prototype edits and review diffs line by line. Make backup before testing changes against saved CE persistence.
5. Run baseline/new economy on same fixture; quantify actual item spawns, distribution diversity and CE overhead. Apply no blanket 5× multiplier without measured rationale.
6. Generate reusable audit/validator that catches unknown classnames/duplicate types/impossible negative quantities/invalid XML/missing map groups (full schema only if engine verified). Record every validated filename.

**Exit:** apartment and barracks have valid controlled loot opportunities; other test buildings unregressed; no CE warnings/spawn starvation/obvious inflation. Engine confirms behavior.

## Stage P2: Static interior layout engineering

1. Inventory building geometry: existing baked furniture, movement paths, stairs, doors, terrain offset; identify room anchors and choose safe reusable prop classes.
2. Author 3 layouts for one house using existing assets only, distinct thematic histories. Use authored static JSON/object spawner first for fixed prototypes; do NOT claim it produces per-instance randomization.
3. Run object-count sweep (0/5/10/20 etc only if safe) and measure per-prop cost. Test collision, navigation, audio, client object sync.
4. Decide offline-precomputed world placement manifest vs limited runtime spawning using the evidence; record ADR and maximum object/collider limits.
5. Add stable building identity, persistent layout seed/id, schema migration and restart/reconnect tests. No layout reroll during normal restart.
6. Test two buildings of same class with different layouts and unique histories; sample log precisely why layout was chosen.

## Stage P3: Contextual visible + searchable loot

1. Define compact room, building, event and archetype tags. Start with 10–20 item-category examples, not the entire catalog.
2. Keep CE standard spawn-point loot where possible; use supplementary search sites for a *bounded* minority of loot opportunities.
3. Implement interaction with built-in furniture only after R&D verifies its targeting/collision. Back with server site identity and durable depleted state; never let the client generate items.
4. Build a server quota ledger or documented CE integration for custom content. Require deterministic seed, one-time claim, anti-duplication, class whitelist and compatibility check.
5. A/B test progression against vanilla, including multiple acquisition routes for civilian essentials and believable rare military surprises.

## Stage P4: Repurposing

1. Audit existing vanilla crafting recipes and actions first; don't duplicate recipes that already exist.
2. Prioritize salvage actions with high gameplay value and few novel assets: existing cloth -> straps/repair; net cutting -> wrap material if model/action works; tools/containers -> compatible useful byproducts.
3. Reject or rework anything requiring substantial new models until an explicit asset/effort review.
4. Implement server-authoritative transaction: tool + item validation -> timed action -> atomic consumption/condition wear -> output creation -> inventory fallback -> save.
5. Test race, disconnect, cancel, ruined tool, no space, stack sizes, cycles and materials conservation.

## Stage P5/P6: Infected competence, behavior and injury

1. Before code, reproduce open-door entry and audio bugs in vanilla. Capture whether script/animation hooks are exposed. Review current `ZombieBase` source, hitpoint definitions, door API, native AI investigation and audio triggers.
2. Evaluate available mods such as InediaInfectedAI/door bangers on isolated test server only after checking license and game compatibility. Benchmark the same fixtures; optional dependency may be rejected despite working if unmaintained, restricted or heavy.
3. Build minimal infected profile selection at spawn or supported lifecycle hook; avoid modifying every infected every tick. Two profiles first: ordinary vs cautious searcher with slower/quieter action and nonmagical senses.
4. Extend **existing** crawling leg injury if actually present and stable; observe animation/hit detection and client sync. Never force teleports or invisible animations to 'fix' broken paths.
5. Implement last-seen/search memory only if exposed data supports observed positions, not live hidden player coordinates. Use reachable waypoint anchors, sparse scheduled checks and native movement.
6. Add door interaction by profile with sound/cooldowns/valid door state, preserve locks/security/physics.

## Stage P7: Local reaction graph + abstract hordes

1. Determine what native infected sound/perception and CE infected event spawning can already achieve by configuration.
2. Implement one local bounded stimulus with spatial index, TTL, hop/recipient/cooldown limit, evidence provenance, and logging. Test gunshot, infected vocalization and scavenging noise.
3. Implement one horde as compact logical state with persistent ID/destination/count; simulate at low tick while remote; materialize only when not observable and with compatible CE/active count rules.
4. Preserve visual consistency in two-client observer test. Migrate horde between areas without ghosting, despawn in direct view or auto-spawn near target behind a wall.
5. Integrate alert chain -> horde interest and horde activity -> nearby local reaction; enforce global budgets, graceful throttling and no runaway recursion.
6. Stress at target population and choose fallback values that preserve believable behavior.

## Stage P8: Integration, hardening and possible release readiness

- Enable/disable each module independently and in combinations; detect conflicts (module matrix); separate master toggle and kill-switch flags.
- Verify loot/interior/crafting/AI interactions and economy balance. Test under restarts, server overload, late join and deliberate disconnections.
- Compare all performance and functional data to vanilla and previous milestone. If regression exceeds agreed ceiling or cheating physics emerges, block and fix/reduce scope.
- Security: client RPC manipulation, inventory duplication, malicious input, compromised player/remote admin, secret leakage. Keep RCon/debug private.
- Review license/IP/export rights and any asset dependency. Only publicize after explicit later decision.
- Produce tagged alpha with deployment instructions, known limitations, migration guide, rollback and test evidence.

## Working conventions for every change

**Issue title:** `[module][requirement-id] concise behavior`  
**PR must state:** vanilla capability explored, source URL/build, why custom code is needed, behavior examples, multiplayer authority/persistence effects, test fixtures, benchmark before/after, memory/net cost, rollback.  
**Feature flag:** every complex feature defaults off until tests pass.  
**Quality gate:** no crash/dupe, no unphysical sound/movement, no major perf regression, documented unresolved engine limits.  
**Logging:** structured ID-based logs with sampling and per-feature verbosity, disabled/minimal by default. Log-to-disk must not become performance bottleneck.  
**No false status:** Record accurate stage: not investigated -> documented -> observed -> prototype -> tested -> accepted.
