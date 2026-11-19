# Outstanding work

Snapshot 2026-11-19, at the wave 10 landing (after `cf10c1d`). This is a working list, not a status claim. Nothing in Hollow Country has been accepted in play yet. "Built" means the source compiles and the local server boots it with 0 script errors.

The only native evidence behind this list is local boot 065: the friend bundle at `cf10c1d`, installed through the friend installer. It had 0 script errors, one `[HC CostTotal]` line plus 8 `[HC Cost]` lines per window, `[HC Infected] degraded reason=posture_owner_start_pending` at start, and the Interiors template pack loading `files=182`. Everything else below is source, unit tests and review. Landed features that read "refused", "off" or "inert" ship that way on purpose: each stays closed until a provider or a survey is observed.

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

Landed on main since the 2026-11-18 snapshot, so no longer in flight:

- audit wave 1 (HC-1, HC-2, HC-4 to HC-9), then HC-3 siphon, HC-5 gestures and betrayal, HC-10 AI custody and the config-driven AI caps;
- checks WP-1 to WP-7 (#153 to #159, #165, #166);
- the #163 installer rollback, #164 clock skew, #167 admin refusals, #169 to #178 persistence, camp, ecology and zero-fill follow-ups;
- audit waves 2 to 4: HC-12 to HC-53 (HC-32 as a roster validation), HC-56, HC-57, HC-59, HC-60 and HC-61 (section 6 lists what each one actually gates);
- the #168 operator requests, including the admin loot map and the search density scale;
- the #135 and #138 review rounds (section 3 lists what remains);
- wave 10: the #191 loot map, Stop cost, subset pin and infected variety fixes, the #183 subset pins (closed), #168 (closed), and the #160 baseline burn-down from 132 to 19 findings;
- wave 11: the #192 review P3 fixes (Expansion AI, events, crafting, loot and infected), the #160 HC-S005 burn-down, the HC-52 backpack mount manifest loader (#58), the HC-48 habitat boot line (#149), the HC-35 trade slot release and module registration (#145), and the debug map Camps layer with per-layer counts;
- wave 12: the #193 wave 11 review follow-ups (journal and event labels, wreck enroll reasons with their own player text, the trade slot released only after the idle save, the HC-48 counts read from the habitat manifest, a configurable infected non-calm hold, a restored `HerdWorld` default, the pack `not_started` reason), the admin loot map tick budget and kept marks, Wine noise ignored in signature checks with a PBO hash cache, the debug map lead-ledger and Scenes layers (registry cap 20, fair admin wire), and the last #160 HC-S001/HC-S005 entries;
- wave 13: the #194 wave 12 review follow-ups (the trade log refusal, the HC-48 manifest tally with `manifest_bytes`/`manifest_cap` and a 64 KB read cap, one `lod.json` restore line, the site `spawn skipped` line, the loot map running tick budget, `min_rows_per_tick` and kept-mark filter labels, an LRU PBO hash cache with unique temp files, strict Wine `err:` lines in signature checks), the shared per-tick work budget (#138), the `EnableTapedPackMounts` setting with per-pair receipts (#58), and the debug map pickers, group-pins and materializer-proposals layers.
- wave 14: the #195 wave 13 review follow-ups (a separate detached-recycle consumer id, Interiors expired locks freed on start, behavioural refresh-resume and recycle budget harnesses, typed `Checked` and ISO `CheckDate` receipt checks with a 64 KB receipt ceiling, debug picker getters gated on a ready journal, test-only lead debug getters removed, a rounded-up loot map cadence, the kept-mark label tied to the last ok run, a hash cache keyed on inode and ctime with an orphan temp sweep).
- wave 15: the #196 wave 14 review follow-ups (the core tick loop leaves at once when a module stops the server, a named `HCGroupIO.HC_RAW_READ_CAP`, a Gregorian `CheckDate` check, per-pair receipt rows for the 29 cross-slot weapon pairs, the admin Notice cut on entry boundaries with `+N more`, the kept-mark label in the loot map legend, a merging hash cache write, and the null-trip picker, expired-lock takeover and ctime harnesses).
- waves 16 and 17: physical admin `campvisit`/`campraid` paths and camp visitor parties (#203, with claim-only targets in #212), the admin `dormant` command on the infected variety fresh-body queue, bounded crawler groups at authored place roles (#121, follow-ups in #213), warned base raids (#151), wildlife providers (#149), the picker CacheLoot field check and the zero-filled first-survivor story row on boot, plus lint rules HC-E010 (FileHandle assigned 0) and HC-E011 (Enforce keyword as a variable name);

Now:

| Item | State |
| --- | --- |
| Next wave | The #197 wave 15 review follow-ups; republish the Workshop items and friend bundle once a batch is stable |
| This refresh | `docs/OUTSTANDING.md` only |
| HC-55 floor-loot dispositions (#179) | Branch `hc/w21-surfaces` is not landed and is held for an owner decision (section 10) |

Friend server: the last server report was Workshop build 034 / bundle v1-test-9. A newer build is not recorded here as published. The stamina and inventory changes need a Workshop update on every client and the server, so they only reach the friend server with the next publish.

## 2. Playtest and friend-server bugs

- **Pause shows no admin menu.**
  - The server answers admins only. Build 034 adds client notices so the key no longer fails silently. The admin-window refusals (#167) are fixed in `44792d6`.
  - The friend must add the owner's Steam64 ID to `profiles\HollowCountry\admins.json` and restart.
  - Still to confirm on the friend server.
- **Search spinning then doing nothing.**
  - Fixed in `64b22ab`: cabinets no longer offer it, and house search names its refusal reason.
  - Still to confirm in play. If it recurs, collect the `[HC Search Houses] refused reason=...` lines.
- **#168 follow-ups** (issue closed; none of the fixes has been seen on the friend server):
  - **Checkpoint props.** Two checkpoints failed to place their roadside table (`native factory` at komarovo-east, `building within 25m` at novaya-south). The retry change is in `530eaa9`. Which class the factory accepts, and whether the novaya-south point needs moving, are not confirmed;
  - the gunfire caution (80 m for 10 s) is documented as deliberate in docs/FRIEND_SERVER.md. Whether it should be limited to targeted fire is an owner decision (section 10).
- **#162 leftovers:**
  - The Expansion AI crash with a raw vanilla M249 given through COT is only contained by `HCXWeaponGuard`. The exact class, versions and stack still need capturing. An upstream Expansion report was drafted but not filed (section 10).
  - The live AI layer on the admin map has not been seen in play.
- **#152:** the pilot cabinet search prompt needs a server-known site list (a site-known RPC like the house-search preview sites) before it can return. Open until a pilot site is configured again or the pilot path is retired.

## 3. Known defects and review follow-ups

- **#191** wave 9 review follow-ups. Landed in wave 10: the loot map tick cap (row deadline reset after the query), the post-ack export failure, the ack-sized client window, the AdminMap start refusals, Ecology pinned in the Stop cost lines with `*_maxsum_*` naming, the subset pins copied into `hc61.class_pins` with the parsed-field scope documented and a parent-class drift test, and the infected variety retry hold on a non-calm mind state. Still open:
  - the 0-byte pending-file path assumes `ReadFile` returns 0 for an empty file (native check);
  - `HCJsonFields.Check` scanning of `HCWreckSalvage` (up to 2 MB, twice) is unmeasured;
  - Interiors: regenerate the template pack. Blocked on a native door phase 2 census;
  - native loot map checks: the Map tab EditBox and Run button, the immediate ack, the `lootmap_job_running` refusal, the layer surviving a snapshot, query and render cost.
- **#192** wave 10 review follow-ups: landed in wave 11 except the kept-on-purpose notes (the `HCSearchHouses.Commit` BUSY reason, the module-wide wreck start reason).
- **#193** wave 11 review follow-ups: landed in wave 12; the light-mount setting and per-pair receipt landed in wave 13. Still open: the trade provider is unbound (refusal-only), and the native checks (unmapped manifest keys, `static const` DTO members, the 0-byte pending file).
- **#194** wave 12 review follow-ups: landed in wave 13. Still open: a file rewritten with the same size and mtime outside the 2 s racy window keeps its cached hash (inherent to the size+mtime key), and the native checks.
- **#195** wave 13 review follow-ups: landed in wave 14. The remaining P3s and native checks moved to #196.
- **#196** wave 14 review follow-ups: tick budget, receipt, debug map and loot map/hash cache P3s, plus the carried native checks (3 to 6 player `[HC TickWork]` measurement, live debug layers, two-client wire check). Landed in wave 15; the remaining P3s and native checks move to #197.
- **#197** wave 15 review follow-ups: the two remaining bare raw read caps, the weapon-pair admission path, `receipts_checked` mixing pack and weapon rows, and the carried P3s and native checks. Local boot 072b (setting on, one weapon row marked for the test, then restored) read all 31 receipt rows natively: `receipts=ok receipts_checked=1`, no `receipt_unknown_pair`.
- **#138** performance:
  - Building resolves are cached and deferred interior updates are cancelled on stop (`a8b87e8`, `21efae6`). The Ecology save runs staged (HC-29). Per-module cost lines now print at Stop.
  - Still open: re-measure every module with 3 to 6 players connected and record p50, p95 and max. The first resolve per building class still pays the native position query (132 ms was the worst seen locally); the issue's options of a smaller query or per-building registration were not taken.
- **#135** infected LOD and virtual herds. Review rounds landed; tiers are on by default and virtual herds are off. Still open:
  - the native experiments (`AIAgent.SetKeepInIdle`, `EntityAI.DisableSimulation`, network range and client frame time with many infected in view);
  - raising the posed budget (still 12/12/12) only after measurement;
  - the distance bands are not confirmed against gunshot and network ranges (about 1 km);
  - nothing is measured with 3 to 6 players.
- **Tick-budget design (done in wave 13):** HCServer owns one shared `HCUnitBudget` per tick (`MaxTickWorkItems`), drawn by Infected sampling, Interiors lock expiry and the search bind, maintenance and refresh loops; each consumer gets one forced unit per tick so none starves (six consumers since wave 14, so a tick does at most `MaxTickWorkItems + 5` items). `[HC TickWork]` prints `shared_used_max` and `shared_starved` once per 60 s window. `test_all_modules_tick_within_shared_work_budget` is a normal test now. Unmeasured natively.
- **Unfiled review P2s** (carried, not re-checked): the event preflight can hitch at start; (the admin map wire squeeze on `ai-units` is addressed in wave 12 by the fair per-layer split). Review notes also left HC-45/47/59/35 P2/P3s in commit bodies (for example a cancelled trade journal keeps the single slot).
- **Unresolved engine findings** (docs/MODULE_STATUS.md, docs/INFECTED_DEATHS.md):
  - the native crash when creating an infected with `ECE_INITAI` (run 065);
  - stock CE timing out in `ce.InitOffline` under Wine;
  - the infected periodic journal never appearing (runs 014 and 016).
- **Out of scope, native limits:** infected cannot follow through window or crawl gaps or into deep water, and their turn rate around pillars is limited (docs/INFECTED_CHEESE_AUDIT.md).

## 4. V1 feature gaps

Carried from the 2026-11-18 snapshot unless a commit changed them.

- **Interiors:** the measured catalog and layout fit still cover a tiny part of the 11,679 stock placements (the HC-53 ledger and 8 priority-building inputs are offline audit data only). The rest stay vanilla as `pending-measurement`.
- **Search:** the shared CE allocator and reconciliation, and a durable inventory and ledger commit, are not built (HC-54). HC-56 furnishing themes ship measured-only. The tenement and office CE inputs (HC-57) have 8 selected points; the office survey is pending.
- **Infected:**
  - The measured room catalog, safe horde abstraction and activation, and a complete variant roster are missing. HC-45 admits only the native crawler idle hold; sit, prone sleep and risers refuse until native proof. HC-14 appearance substitutions and HC-46 route drift are authored but inert until observed or surveyed.
  - Death reactions only change DEFAULT to IMPULSE, because the engine has no infected ragdoll API. Whether that looks different is unobserved.
- **Events:**
  - Three sites are source-reviewed, but none is field-surveyed. Nonzero rewards stay blocked.
  - Search and rescue, defend and evacuate, moving convoys and branching chains are still not built. HC-38 replaced the quest UI with durable situations; HC-39 raids ship off; HC-40 transit refuses until route clearance is verified.
- **PvE groups:** patrols, rescues, escorts and convoys are still "to evaluate" in the README.
- **Map information layers:** still Planned; the layers are not chosen.
- **Crafting:** HC-22 useful supply and HC-30 fabric and teddy recoveries are built behind guarded registration. The full action audit for the remaining routes is open.
- **Ecology:** no feeding, drinking or resource-seeking, because no supported API was found.
- **Weather:** no profile installs automatically. Lighting and volumetric fog are separate feasibility work. White terrain is `pending` (HC-50).
- **Firearms** (docs/FIREARMS.md):
  - HC-21 family budgets and HC-61 subset pins are built. 9 variants absent from stock types use a new type-entry install path that is still unproven.
  - Optics are deferred until an optics mod is chosen.
  - The Tactical Flava optics subset is pending.
- **Admin kit gaps** (docs/ACCEPTANCE_CHECKLIST.md, not re-checked since HC-25):
  - no COT role authorisation;
  - a fresh `dormant` spawn is refused;
  - forced tiers, visits and raids are skipped.
- **Debug map** (docs/DEBUG_MAP.md): Camps, lead-ledger and Scenes are layers now, and `snapshot.json` carries per-layer shown/total counts; the admin wire splits its caps fairly per layer and reports `layers_unsent`. Pickers, group pins and materializer proposals are layers since wave 13 (ids withheld); a lead at an unknown place counts as `unplaced`, not in `total`. `camps total=48 shown=24` is the 48-holdout catalogue against the 24-row layer cap, not a double count. Snapshot writes are not atomic, because the engine has no rename. The loot map layer is built and unobserved.
- **Animations** (docs/ANIMATION_PIPELINE.md):
  - The sleep, get-up, kneel-feed and feed-to-stand clips wait on the sitter working natively.
  - An own `.ast` template is the fallback if the dead slot is used.
- **Camp theft** stays off (fail closed) until lock state is defined.
- **Taped lights #58:**
  - Helmet mounts (HC-23) are a fail-closed catalogue. Backpack mounts (HC-52) load `mission/hollow-country/lights/backpack-mounts.json` at boot. The operator setting `EnableTapedPackMounts` (default false) gates them and publishes `off reason=setting_off`; with it on, `mission/hollow-country/lights/pair-receipts.json` is read once (bounded by `MaxReceiptBytes`) and a pair needs `Checked=true`. `Qualified()` is still false, so no pair attaches.
  - The approved cross-slot pairs, TLRLight on 22 rail rifles and UniversalLight on 7 pistols, stay disabled behind a setting. Each pair needs its own client check. Still to do: client checks for every pair. Since wave 15 the receipt sheet has 31 rows (the 2 pack pairs plus the 29 weapon pairs as `cross_<Host>_<Light>`, all `Checked=false`, `MaxReceiptBytes` 32768); the weapon-pair admission path itself is not built yet.

## 5. V3 features (open epics)

All follow the same rules:

- the server is authoritative;
- world changes happen only out of every player's sight;
- AI are not omniscient;
- loot is finite;
- counts and per-tick work are bounded;
- every feature logs one admission line and has its own off switch.

Owner direction: players may watch, raid or ambush AI, but there is no trading, dialogue or quests with them. Sections 4 and 6 hold the landed pieces; this table is the remaining scope. #143 (camps) is closed.

| Issue | Landed (all runtime pending) | Remaining scope |
| --- | --- | --- |
| #121 Infected variety | HC-14 substitutions, HC-45 crawler idle hold, HC-46 route drift, HC-47 threat matrix | Bounded crawler groups at authored place roles and the fresh-body queue are in source (native acceptance pending). Standing risers and surveyed routes are in #213. Sleepers and sit postures wait on native proof; role postures; woken groups; day/night and weather behaviour; tier C animations |
| #144 AI scavenging runs | HC-34 single-item custody journal, HC-43 locality candidates and Raider/Traveller loadouts | The route stays hard-refused until a verified provider exists; the return receipt is not wired; an open P2 from review |
| #145 AI-to-AI trade | HC-35 barriers: one reciprocal recipe, journaled exchange | Provider refuses `TRADE_RENDEZVOUS_EMOTE_ACK_UNVERIFIED`; the module is registered and prints its refusal at boot; a terminal journal releases the single slot; no provider is bound; HC-36 caravan is wired but refused (corridor unsurveyed, provider callbacks unverified) |
| #146 Faction territories | HC-37 conflict outcomes from observed actors | `COMBAT_PROVIDER_UNVERIFIED`; no territory shifting or distant resolution evidence |
| #147 Exploitable situations | HC-38 lifecycle, HC-39 raid profiles (ship off), HC-40 transit profiles (refused), HC-41 incident leases (source refuses), HC-42 story kits, pinned survivor holds, road caravan threat points (review follow-ups #210) | Provider and route-clearance evidence, a surveyed corridor, a verified CE incident source |
| #148 AI react to emotes | HC-5 gestures and betrayal memory | Emote acknowledgement is unverified in play; the #139 grudge checks |
| #149 Living wildlife | HC-15 observation baseline, HC-48 habitat dispositions, HC-49 observed carcasses, finite wildlife carcasses and bounded native eligibility (wave 17) | Authored carcasses refuse (`AUTHORED_CORPSE_CE_ADMISSION_UNPROVEN`); the HC-48 boot line prints habitat dispositions and refusals (runtime pending); predators, herds and animals against AI and infected |
| #150 Visual seasons | HC-6 clock, HC-50 white-terrain receipt, HC-51 forecast, client snapshot and presentation | White terrain `pending` (dynamic terrain API unproven); the client view is unchecked; variant dependencies (HC-60 shortlist, `admitted=0`) |
| #151 Light player bases | HC-17 per-group claims and construction denial, HC-16 funded camps, warned physical base raid (`base_raid.disable`; adapter coverage #211) | Claim expiry rule (section 10); breakable-door and claim-vulnerability checks; respawn question (section 10) |

Also decided, still to build or confirm:

- every eligible settlement and island gets occasional AI activity or traces (HC-18, HC-43 provide the selection; no play evidence);
- new stories arrive on a persistent schedule, and completed ones never replay (HC-19 built, unobserved);
- Morse traffic is folded into radio reports (HC-20 built, unobserved);
- forage familiarity resets on death (HC-13 built, unobserved).

## 6. Audit plan work packages (HC-11 to HC-64)

Built means landed on main, compiled and booted locally. Gate shows the default that ships.

- **Not built:**
  - HC-11 current requirements and player docs, with one pending task per outstanding slice;
  - HC-54 composed finite search on the native continuous action;
  - HC-55 floor and surface loot deltas (held, #179);
  - HC-58 native vehicle recovery impulses. No landing was found in the log; the `HC-58` text in one acceptance-doc commit refers to the helmet mount marker;
  - HC-62 exact-source playable package, HC-63 first native boot, off and recovery slice, HC-64 two-client and target-load evidence.
- **Built, open or gated:**
  - HC-16 camp life, HC-17 claims, HC-18 locality paging, HC-19 stories, HC-20 radio with Morse: built, unobserved;
  - HC-12 forage reclamation, HC-13 familiarity per life, HC-33 forage and routes (5 unresolved rows with named refusals), HC-22 useful supply, HC-30 recoveries: built, unobserved;
  - HC-14 infected appearances (rollback refuses without a receipt), HC-45 postures (crawler only), HC-46 routes (inert), HC-47 threat matrix (unproven reach refused);
  - HC-15 wildlife baseline, HC-48 habitats (inert events), HC-49 carcasses (authored refused), HC-59 shelters and finite wreck parts (shelter survey backlog of 5);
  - HC-34 custody journal and HC-35 trade (provider refused), HC-36 caravan (corridor refused), HC-37 faction outcomes (provider unverified), HC-38 to HC-42 situations (see section 5), HC-43 loadouts, HC-44 trace receipts;
  - HC-50 white terrain (pending), HC-51 seasonal presentation (wired, off when seasons are off);
  - HC-21 firearm family budgets, HC-61 subset pins (class pins copied in from a local verify; SNAFU verify stays unverified locally for missing vendor files);
  - HC-23 helmet catalogue and HC-52 backpack pairs (closed gates);
  - HC-24 staged interior pack index, HC-31 cellar slice (stair samples stay pending), HC-53 disposition ledger (offline only), HC-56 furnishing, HC-57 tenement inputs;
  - HC-32 travel roster validation and optional repair composition;
  - HC-60 variant shortlist (research record, `admitted=0`);
  - HC-25 admin snapshots, HC-26 group ping and death-pin privacy, HC-27 presentation controls, HC-28 store recovery, HC-29 bounded ecology tick and saves (calibration still has to be measured on the target load).

## 7. Runtime acceptance still pending

Every README feature row reads "Built · not played". Still to observe:

- **V1 checklist:** about 105 unchecked pass cells across the per-feature, V2 and later tables (docs/LOCAL_ACCEPTANCE_V1.md, counted by pattern).
- **V2 experiments:** 27 of the 28 in docs/experiments/v2-experiments.json are PENDING. EXP-D1, the Expansion-Animations conflict, is a fallback whose wording re-check is pending.
- **#139 AI self-defence in play:**
  - punch, shoot and kill responses;
  - near-miss fight-or-flight;
  - rescue shots that do not provoke;
  - grudge expiry;
  - the cost of the near-miss ray.
- **The guided owner session** (30 to 45 minutes) with the admin test kit. Every kit command, the browser map and the new admin Map tab (loot map Run control, immediate ack, running-job refusal) are uninspected in game.
- **Two clients needed for:**
  - group invite, accept, kick and leader change;
  - marker sync and group ping privacy;
  - event and season-snapshot visibility;
  - reconnect;
  - infected audio from two positions;
  - gunshot audibility;
  - infected perception of two players;
  - door and crawl state;
  - camp theft, radio, holdouts, scenes, signs of life, bikes, herd drift and mailbox privacy.
- **Persistence:** respawn, and restart after a stopped server. The HC-28 recovery and the 0-byte pending-file path are unobserved natively.
- **Infected:**
  - death visuals and replication;
  - corpse loot;
  - anti-cheese reach (attack during chase, vault landing, vehicle damage);
  - door pressure (#136).
- **Animations PBO:** never loaded by a server or client yet. Replication and late-joiner poses are unknown.
- **Interiors:**
  - rendered clearance and replication;
  - the baked-target action;
  - the startup cost with the 182-file template pack (boot 065 loaded it; cost with players is unmeasured).
- **Loot boost:** the `lootHCFloor` containers, density and cost.
- **Firearms:**
  - roster spawns, firing and ammo;
  - re-running the weapons-pack verifier on the server copy;
  - event-only classes.
- **Map overlay layers:** pieces may float or clip by up to about 1 m; heading and road alignment are assumptions.
- **COT permissions:** joined-client checks.
- **Friend installer and server report:** the installer rollback (#163) and the case-insensitive path compare have not run against real steamcmd on Windows.
- **Combined load (#78 / EXP-P2):** 8 AI and 2 hordes with 3 to 6 players. Every performance budget, including `[HC CostTotal]` and per-module `[HC Cost]` figures, stays provisional until this is measured.

## 8. Checks, audits and tooling debt

- **#160 WP-8 (done in wave 12):** the lint baseline is down to 1 finding (`new=0 stale=0`) from 132 at `cf10c1d`: the reviewed-safe HC-E006 `HCSearchHouseJournal.Open` substring. HC-S001, HC-S002, HC-S003 and HC-S005 are all at 0, and `LEGACY_BASELINE` in `tools/validate/enforce_json.py` is empty. The lint accepts a bare positive `m_*Printed`/`m_*Finished` re-entry guard as idempotent.
- **Settings registry (#158, done):** boot prints the effective shared settings; `settings_consistency` validates them.
- **Readiness lines (#157, done):** every module prints `ready`, `degraded`, `off` or `started`, and HCServer prints per-module readiness on a settings failure.
- **Pre-push hook:** suggested in audit/CHECKS.md, not installed.
- **S003 resolution is name-based**, so the lint is heuristic there.
- **Native-only compile traps** are caught only by a boot (for example the `Queue` field name). The lint covers the known ones.
- **Measurements:** 3 to 6 player cost has not been measured for infected reach, the debug snapshot, the loot map or the AI follow-ups.

## 9. Doc fixes

- Done on 2026-11-18: the stamina wording, docs/DEBUG_MAP.md pointing at the implemented admin map (#123), docs/LOCAL_ACCEPTANCE_V1.md no longer calling the repo private, the README marking the Expansion-Animations conflict as unverified (EXP-D1), and the audit/CHECKS.md finding count. Done in wave 12: audit/CHECKS.md finding count and the WP-5/WP-6 status.
- Open:
  - docs/LOCAL_ACCEPTANCE_V1.md: no exact unchecked-row total exists; section 7 here uses a count by pattern.

## 10. Questions for the owner

1. **Claim expiry:** how long an absence expires a group's building claim? The provisional default is 14 server days since a member's last visit. Does any member's visit renew it?
2. **Claimed building and respawn:** should the fresh-character camp respawn stay, or should a claimed building give storage and recognition only?
3. **Trucks:** keep them on stock CE spawn and repair, or include them in the HC travel override?
4. **Optics:** which optics mod, if any, passes the "clean" bar? This unblocks the deferred optics rows.
5. **Expansion M249 crash:** should the drafted upstream report go to the Expansion maintainers? It would be posted publicly, from your account.
6. **#179 extra floor loot:** keep the 1,222 HC-9 extra points live and land only the disposition record (A, the lead's recommendation), quarantine all of them until native qualification (B), or quarantine only families a native sampler run flags (C)?
7. **Two-client testing:** is a second client (a friend or a second account) available for the two-client rows in section 7?
8. **Target load:** the plan targets 3 to 6 players, and an older handoff mentioned about 90. Is 3 to 6 still the target for budgets?
9. **Wipe and event pacing:**
   - Are there map and character wipe rules for the friend server?
   - How often should events and stories arrive?
10. **Autonomous validation spec (002):** its 30 tasks assume an automated client, which the acceptance rules exclude. Retire it, or keep the parts that don't need one?
11. **Cold and wet overlay:** HC-2 wanted to retire the V1 cold/wet gameplay overlay (temperature deltas and wetness modifiers) as well as the warm-meal bonus. Only the meal bonus was dropped; the overlay stays because "no cold penalties" was read as being about the seasons. Should the overlay go too?
12. **Gunfire caution:** HC patrols widen their caution on any audible shot within 80 m for 10 s. Keep this as documented, or limit it to targeted fire?

The old question on #57 history is closed with the issue.
