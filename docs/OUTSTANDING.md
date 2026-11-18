# Outstanding work

Snapshot 2026-11-18, at `a5dafac`. This is a working list, not a status claim. Nothing in Hollow Country has been accepted in play yet. "Built" means the source compiles and the local server boots it with 0 script errors.

The list draws on four sources:

- open GitHub issues;
- owner decisions;
- the coverage audit plan (work packages HC-1 to HC-64);
- the tracked docs.

Sections:

1. In flight
2. Playtest and friend-server bugs
3. Known defects and review follow-ups
4. V1 feature gaps
5. V3 features
6. Audit plan work packages
7. Runtime acceptance still pending
8. Checks, audits and tooling debt
9. Doc fixes
10. Questions for the owner

## 1. In flight

| Item | State |
| --- | --- |
| #154 Checks WP-2: shared `HCRefusal` reason codes and report helper | Sol worker running |
| #156 Checks WP-4: tolerant, logged build-identity gate and lint rule HC-S004 | Sol worker finished; review and landing next |
| #159 Checks WP-7: older syntax tests onto the shared Enforce source model | Sol worker running |
| HC-1 to HC-10 (audit wave 1) | Worker output sits **unmerged** in its worktrees, based on `3ab98d0`. It needs review, a rebase onto main, focused tests and a native boot before it can land. |

The HC-1 to HC-10 packages are:

- **HC-1** effective module status;
- **HC-2** drop the warm-meal bonus and align stamina;
- **HC-3** finite production siphon;
- **HC-4** salvage state conservation;
- **HC-5** emote reactions and betrayal;
- **HC-6** four-week visual season clock;
- **HC-7** current taped-light pairs;
- **HC-8** large-building doors and claim vulnerability;
- **HC-9** recoverable 2x loot packaging;
- **HC-10** a single AI party and cargo identity.

Friend server: Workshop build 034 and bundle v1-test-9 are what the friend runs. **Nothing new goes to the Workshop or to Releases for the rest of 2026-11-18.**

## 2. Playtest and friend-server bugs

- **Pause shows no admin menu.**
  - The server answers admins only. Build 034 adds client notices so the key no longer fails silently.
  - The friend must add the owner's Steam64 ID to `profiles\HollowCountry\admins.json` and restart.
  - Still to confirm on the friend server.
- **Search spinning then doing nothing.**
  - Fixed in `64b22ab`: cabinets no longer offer it, and house search names its refusal reason.
  - Still to confirm in play. If it recurs, collect the `[HC Search Houses] refused reason=...` lines.
- **#162 follow-ups:**
  - Police-site events refused with `no_candidate`. Build 034 logs the constraint that refused; read it from the next server report.
  - The Expansion AI crash with a raw vanilla M249 given through COT is only contained by `HCXWeaponGuard`. The exact class, versions and stack still need capturing. An upstream Expansion report was drafted but not filed (see section 10).
  - The live AI layer on the admin map has not been seen yet.
- **#152:** the pilot cabinet search prompt needs a server-known site list before it can come back. It stays open until a pilot site is configured again or the pilot path is retired.

## 3. Known defects and review follow-ups

- **#163** Installer: a refusal after writes have started leaves a partial install.
- **#164** A backwards wall-clock step turns infected memory off. `HCInfectedMemory.Now()` calls `Fail()` on any read, admin `list` included.
- **#138** performance:
  - Ecology and WorldSaves tick spikes are spread across ticks (`2389e26`, `bd350b2`). They still need re-measuring with players.
  - The worst Interiors resolve is the native position query itself (132 ms for a query returning 2 objects). Options:
    - shrink the query to the template footprint;
    - resolve once per building and cache;
    - have buildings register themselves instead of being found by query.
- **#135** review follow-ups:
  - tombstone slots count against the herd cap;
  - the occlusion check is a single-point ray;
  - stop-time debit;
  - distance bands need re-basing on gunshot and network ranges (about 1 km).
- **Unfiled review P2s:**
  - The event preflight can hitch at start.
  - On the admin map wire cap, `ai-units` is the layer that gets squeezed.
- **Three expected-failure tests encode real defects** (audit/CHECKS.md):
  - `test_all_modules_tick_within_shared_work_budget`
  - `test_stop_removes_queued_interior_updates_as_well_as_core_tick`
  - `test_groups_null_context`
- **Unresolved engine findings** (docs/MODULE_STATUS.md, docs/INFECTED_DEATHS.md):
  - the native crash when creating an infected with `ECE_INITAI` (run 065);
  - stock CE timing out in `ce.InitOffline` under Wine;
  - the infected periodic journal never appearing (runs 014 and 016).
- **Out of scope, native limits:** infected cannot follow through window or crawl gaps or into deep water, and their turn rate around pillars is limited (docs/INFECTED_CHEESE_AUDIT.md).

## 4. V1 feature gaps

- **Interiors:** 1 of 11,679 placements is measured. The rest stay vanilla as `pending-measurement` until a measured catalog and layout fit exist (docs/MODULE_STATUS.md).
- **Search:** the shared CE allocator and reconciliation, and a durable inventory and ledger commit, are not built.
- **Infected:**
  - The measured room catalog, safe horde abstraction and activation, and a complete variant roster are missing.
  - Death reactions only change DEFAULT to IMPULSE, because the engine has no infected ragdoll API. Whether that looks different is unobserved.
- **Events:**
  - Three sites are source-reviewed, but none is field-surveyed.
  - Nonzero rewards stay blocked.
  - These mission families are not built: search and rescue, defend and evacuate, moving convoys, and branching chains.
- **PvE groups:** patrols, rescues, escorts and convoys are still "to evaluate" in the README.
- **Map information layers:** still Planned; the layers are not chosen.
- **Crafting:** the salvage recipes are starting points. The full item, recipe and action audit is open (audit plan HC-22, HC-30, HC-33).
- **Ecology:** no feeding, drinking or resource-seeking, because no supported API was found.
- **Weather:** no profile installs automatically. Lighting and volumetric fog are separate feasibility work.
- **Firearms** (docs/FIREARMS.md):
  - 9 variants absent from stock types need a new type-entry install path.
  - Optics are deferred until an optics mod is chosen.
  - The Tactical Flava optics subset is pending.
- **Admin kit gaps** (docs/ACCEPTANCE_CHECKLIST.md):
  - no COT role authorisation;
  - a fresh `dormant` spawn is refused;
  - forced tiers, visits and raids are skipped;
  - most modules report `active=n/a budget=n/a`.
- **Debug map** (docs/DEBUG_MAP.md):
  - Pickers, Camps, Scenes, group pins, all leads and materializer proposals have no layers yet, because those modules have no read accessors.
  - Snapshot writes are not atomic, because the engine has no rename.
- **Animations** (docs/ANIMATION_PIPELINE.md):
  - The sleep, get-up, kneel-feed and feed-to-stand clips wait on the sitter working natively.
  - An own `.ast` template is the fallback if the dead slot is used.
- **Camp theft** stays off (fail closed) until lock state is defined.
- **Taped lights #58:**
  - Part 2 (authored helmet and backpack mounts) is not built.
  - The approved cross-slot pairs, TLRLight on 22 rail rifles and UniversalLight on 7 pistols, stay disabled behind a setting. Each pair needs its own client check before it is enabled.

## 5. V3 features (open epics)

All follow the same rules:

- the server is authoritative;
- world changes happen only out of every player's sight;
- AI are not omniscient;
- loot is finite;
- counts and per-tick work are bounded;
- every feature logs one admission line and has its own off switch.

Owner direction: players may watch, raid or ambush AI, but there is no trading, dialogue or quests with them.

| Issue | Feature | Owner decisions that shape it |
| --- | --- | --- |
| #121 | Infected variety: sleepers, risers, role postures, place clusters, woken groups, day/night and weather behaviour, tier C animations | Sitter first; selected native unused variants, plus Workshop variants as dependencies only |
| #143 | AI survivor camps that grow, fall and improve over days | Four camp levels; AI repair and build bases out of sight |
| #144 | AI scavenging runs on finite house loot, back to camp stashes | Players can ambush a returning party |
| #145 | AI-to-AI trade caravans with real cargo | No trader UI |
| #146 | Shifting faction territories; AI against AI and against infected | Fights far from players resolve as logged data |
| #147 | Exploitable situations: survivors pinned, convoys attacked, camps raided | No quest prompts; the reward is what is physically there |
| #148 | AI react to emotes: wave, hands up, raised weapon; betrayal remembered | Built on #139 grudges; audit plan HC-5 |
| #149 | Living wildlife: seasonal herds, predator territories, carcasses, animals against AI and infected | All four parts |
| #150 | Visual seasons | 4-week cycle; falling snow, fog, colour; **white terrain wanted** (feasibility HC-50); no cold penalties |
| #151 | Light player bases: containers anywhere and one claimed building per group | Doors stay lockable; heavy infected can force them; claims expire after a long absence |

Also decided, still to build:

- every eligible settlement and island gets occasional AI activity or traces;
- new stories arrive on a persistent schedule, and completed ones never replay;
- Morse traffic is folded into radio reports;
- forage familiarity resets on death;
- the warm-meal bonus is dropped.

## 6. Audit plan work packages still to build (HC-11 to HC-64)

These come from the 2026-11-18 coverage audit (AIEV, CRAFT, BLDG, WORLD, LOOT, OPS), grouped by area.

- **Docs and tracking:**
  - HC-11 current requirements and player docs, with one pending task per outstanding slice.
- **Survival and craft:**
  - HC-12 reclaimable forage nodes;
  - HC-13 familiarity per character life;
  - HC-22 useful clothing, storage and essential routes;
  - HC-30 first common recovery recipes;
  - HC-33 native forage, water and essential-use routes.
- **AI society:**
  - HC-16 persistent camp life with resource-funded stages;
  - HC-18 sparse, fair locality selection;
  - HC-34 one real scavenging round trip;
  - HC-35 first AI-to-AI barter;
  - HC-36 one walking caravan corridor;
  - HC-37 faction encounters with physical outcomes;
  - HC-43 AI sites in every locality, plus the missing Raider and Traveller roles.
- **Stories and events:**
  - HC-19 new independent stories on a persistent schedule;
  - HC-20 radio clues with Morse folded in;
  - HC-38 first world opportunity, retiring the quest interface;
  - HC-39 camp raids and foot columns;
  - HC-40 passable roadblocks and exodus groups;
  - HC-41 reuse native CE incidents;
  - HC-42 regional story kits;
  - HC-44 factual notes and body stories.
- **Bases:**
  - HC-17 group building claims, no construction.
- **Infected:**
  - HC-14 unused native infected appearances;
  - HC-45 resting postures and risers;
  - HC-46 herd and noise routes around places;
  - HC-47 room, reach and vision threat matrix.
- **Wildlife:**
  - HC-15 native wildlife baseline;
  - HC-48 habitats, predators and target pairs;
  - HC-49 finite carcasses.
- **Seasons:**
  - HC-50 permitted white-terrain feasibility;
  - HC-51 seasonal weather and presentation.
- **Loot and firearms:**
  - HC-21 scarcity for whole firearm families;
  - HC-61 approved optional weapon adapters.
- **Lights:**
  - HC-23 first authored helmet mount;
  - HC-52 backpack mounts and guarded cross-slot lights.
- **Buildings and search:**
  - HC-24 bounded interior pack index (ties into #138);
  - HC-31 first measured cellar slice;
  - HC-53 building dispositions and a complete pack source;
  - HC-54 composed finite search on the native continuous action;
  - HC-55 floor and surface loot deltas;
  - HC-56 first furnishing themes;
  - HC-57 tenement and municipal-office CE inputs.
- **Vehicles and travel:**
  - HC-32 vehicle spawn and optional repair;
  - HC-58 native vehicle recovery impulses;
  - HC-59 regional travel shelters and finite wreck parts.
- **Variants:**
  - HC-60 shortlist of native and Workshop variant dependencies, with licences checked.
- **Operations:**
  - HC-25 useful debug and admin rows;
  - HC-26 group ping and death-pin privacy;
  - HC-27 client presentation controls;
  - HC-28 store recovery and paired backup;
  - HC-29 bounded ecology tick and save with attributable cost.
- **Qualification:**
  - HC-62 exact-source playable package;
  - HC-63 first native boot, off and recovery slice;
  - HC-64 two-client and target-load evidence.

## 7. Runtime acceptance still pending

Every README feature row reads "Built · not played". Still to observe:

- **V1 checklist:** 56 rows unticked (docs/LOCAL_ACCEPTANCE_V1.md).
- **V2 checklist:** 47 rows unticked (#69 to #135).
- **V2 experiments:** 27 of the 28 in docs/experiments/v2-experiments.json are PENDING. EXP-D1, the Expansion-Animations conflict, is a fallback whose wording re-check is pending.
- **#139 AI self-defence in play:**
  - punch, shoot and kill responses;
  - near-miss fight-or-flight;
  - rescue shots that do not provoke;
  - grudge expiry;
  - the cost of the near-miss ray.
- **The guided owner session** (30 to 45 minutes) with the admin test kit. Every kit command and the browser map are still uninspected in game.
- **Two clients needed for:**
  - group invite, accept, kick and leader change;
  - marker sync;
  - event visibility;
  - reconnect;
  - infected audio from two positions;
  - gunshot audibility;
  - infected perception of two players;
  - door and crawl state;
  - camp theft, radio, holdouts, scenes, signs of life, bikes, herd drift and mailbox privacy.
- **Persistence:** respawn, and restart after a stopped server.
- **Infected:**
  - death visuals and replication;
  - corpse loot;
  - anti-cheese reach (attack during chase, vault landing, vehicle damage);
  - door pressure (#136).
- **Animations PBO:** never loaded by a server or client yet. Replication and late-joiner poses are unknown.
- **Interiors:**
  - rendered clearance and replication;
  - the baked-target action;
  - the startup cost of 1,500 props.
- **Loot boost:** the `lootHCFloor` containers, density and cost.
- **Firearms:**
  - roster spawns, firing and ammo;
  - re-running the weapons-pack verifier on the server copy;
  - event-only classes.
- **Map overlay layers:** pieces may float or clip by up to about 1 m; heading and road alignment are assumptions.
- **COT permissions:** joined-client checks.
- **Friend installer and server report:** never run against real steamcmd on Windows.
- **Combined load (#78 / EXP-P2):** 8 AI and 2 hordes with 3 to 6 players. Every performance budget stays provisional until this is measured.

## 8. Checks, audits and tooling debt

- **#160 WP-8:** burn down the lint baseline to zero. The baseline holds 127 entries with a count of 144:
  - HC-S001: 60
  - HC-S002: 77
  - HC-S003: 6 (#154 removes these)
  - HC-E006: 1 (reviewed safe)
- **#157 WP-5:** every module logs `ready` or `off reason=`, and HCServer logs the modules it skips. Today they are skipped silently. Adds lint rule HC-S005.
- **#158 WP-6:** a shared settings registry. The observer and spawn distances (120, 200 and 300 m) currently drift unchecked. Boot prints `[HC Settings] effective ...`.
- **Pre-push hook:** suggested in audit/CHECKS.md, not installed.
- **S003 resolution is name-based**, so the lint is heuristic there.
- **Measurements:** 3 to 6 player cost has not been measured for infected reach, the debug snapshot or the AI follow-ups.

## 9. Doc fixes

- **Stamina:**
  - The code is 0.25 drain and 2.5x recovery, which the owner kept.
  - The README stamina row and docs/MODULE_STATUS.md still say half drain and 25% faster recovery.
  - The README status table says "doubled".
- **docs/DEBUG_MAP.md** still calls the admin map (#123) deferred, but it is implemented.
- **docs/LOCAL_ACCEPTANCE_V1.md** still calls the repo private.
- **README:** states the Expansion-Animations conflict as fact. It is an unverified report (EXP-D1).
- **audit/CHECKS.md:**
  - It still says 152 findings and "four E006".
  - Its work package table has no done markers (WP-0, WP-1 and WP-3 are done).

## 10. Questions for the owner

1. **Claim expiry:** how long an absence expires a group's building claim? The provisional default is 14 server days since a member's last visit. Does any member's visit renew it?
2. **Claimed building and respawn:** should the fresh-character camp respawn stay, or should a claimed building give storage and recognition only?
3. **Trucks:** keep them on stock CE spawn and repair, or include them in the HC travel override?
4. **Optics:** which optics mod, if any, passes the "clean" bar? This unblocks the deferred optics rows.
5. **Expansion M249 crash:** should the drafted upstream report go to the Expansion maintainers? It would be posted publicly, from your account.
6. **#57 history:** older public history contains about 77 internal paths. Leave it, or approve a remediation? A history rewrite needs your explicit approval.
7. **Two-client testing:** is a second client (a friend or a second account) available for the two-client rows in section 7?
8. **Target load:** the plan targets 3 to 6 players, and an older handoff mentioned about 90. Is 3 to 6 still the target for budgets?
9. **Wipe and event pacing:**
   - Are there map and character wipe rules for the friend server?
   - How often should events and stories arrive?
10. **Autonomous validation spec (002):** its 30 tasks assume an automated client, which the acceptance rules exclude. Retire it, or keep the parts that don't need one?
