# Gameplay implementation and remaining work

This file distinguishes authored functionality from missing implementation and
unperformed validation. The current test package is not the completed
overhaul. Outstanding work is tracked in
[issues](https://github.com/d-addison/hollow-country/issues).
Source implementation does not waive runtime evidence or make gated features
operational.

All feature preferences now default enabled. Explicit operator disables are
preserved. Missing measured content, dependencies, providers or trusted receipts
still prevent admission and must be reported. An enabled preference alone is
not proof that its gameplay is operational.

## Current source changes — rounds r8–r14, 2026-11-20

This record supersedes older implementation snapshots below. All features ship with enabled
preferences. Every change here has **native status PENDING**: final-source compile, boot with
no enabled module reporting `ready=false`, and the relevant gameplay exercise on one server
with at most one client remain unverified. Counters, source checks and historical boots do
not accept a feature. Capacity at 3–6 players remains provisional.

| Change / source | Current implementation | Unverified gates / follow-up |
| --- | --- | --- |
| Admin M map (v1-test-11) | Default-on allowlist-only M-map stream; 3,161 versioned repository/official-CE catalog anchors, live HCX AI/convoy, native transport/crash/gas registries, existing debug layers, ecology cohort, horde/pack and claim read seams; bounded chunked RPCs, pooled coloured pins, zoom clusters, legend, hit details, existing loot query | Native admin-client check PENDING. Lead compile/boot, sender denial and zero non-admin payload, close/disconnect/timeout, static cache/reopen, pan/zoom/clusters/details, vehicle provider lifecycle coverage, loot results and target-load timing. Animal rows are the bounded ecology cohort, not a whole-world census; static pins are candidates, not live presence. Existing debug contributors retain their owner sampling/caps and require EnableDebugSnapshot. One server plus at most one client; no multiplayer claim |
| Round r14 (`7e40fdc9`..`baae4cec`, #275 #287 #305 #306 #312) | AI site survey keeps qualifying past the 1,500 s boot window, nearest sites first; policy-only counters. Route start-up admits one bounded page per visit. Events expiry/cleanup journals, infected variety scans, heavy Interiors queries and every staged-save file call yield across ticks with named `[HC Step]` stages. Periodic status lines print on change or every 30 min; R3 counts repeats per rolling 60 min. Seasons checkpoints leave a lagging queue at half the loss cap. Lint HC-E018/E019. Friend installer: scoped process probe, `--assume-stopped`, globals drift preflight, BOM/CRLF profiles, Groups/LOD field merges | Native timing (16 ms ceiling), full survey completion, journal recovery after interruption, the real 102→current upgrade on the friend server |
| Ground support (`ffc24c7b`, #279) | Transformed bounding-box bottom plus support rays; props capped at 3 m, spawner structures 25 m, CE items 2.5 m. HC placements and HCX props share the service; CE queue cap 16,384, four per shared-budget slice. `[HC Ground]` reports per-source results | Native contact, collision and placement appearance; food/firework classes omitting `super.EEOnCECreate` remain uncovered |
| No-jam rule (`f54f0b5f`) | Pristine/worn skip `Weapon_Base.JamCheck`; `noJamMaxHealthLevel=1`, -1 restores native rolls | Native firing, damage thresholds and pack compatibility |
| Inventory sizing (`5c5454c7`, `cc387582`, #280) | Ancestry/dependency-based stack rules retain 570 vanilla overrides and add 51 stack overrides; 187 declared-pack attachment/magazine overrides cap dimensions at vanilla scale. Stale size tables refuse release; rollback covers both outputs | Signed addon loading, inventory fit, attachment/cargo interactions and rollback |
| Native infected climb (`119ece77`, #281) | Default-on `InfectedClimb.*` scoped registry; unreachable target 0.5–2.2 m up, within 2.5 m, two bounded obstacle rays, native vault/landing. Four concurrent attempts, 6 s cooldown; retires after 12 attempts without reaching the top | Native vault landing, shared-budget/concurrency behaviour, outcome counters; ladders remain shadow diagnostics because no native infected ladder command is available |
| Supported loot points (#274/#279, density2 round 2) | Full-client re-audit restores every coordinate from `335915c6`: 1,301 surface + 679 floor = 1,980 HC points in 224 types (202 of 263 placed stock types). Dedicated-server stripped PBOs no longer authorize visual refusals; prior-first selection and coordinate-level receipts prevent silent losses. [Per-type counts and refusal evidence](LOOT_POINTS.md#surface-point-preservation-after-fa0c2ac8) | Native support, vicinity access, CE spawning/tag matching and restart retention remain pending; 3,000 surface-point target and full placed coverage remain open; target-load budgets unmeasured |
| Military CE budget (`7aa4c46b`) | Military-only primaries share a map budget around four Tisy kits. Every class keeps nominal/min >=1; missing/zeroed rows refuse generation. Scout, Scout_Chernarus and R12 retain Prison/Police routes; modded magazines 10–100% full | Observed CE mix and per-class availability; budget balance |
| Activity check (`214f384f`) | Declared signals classify ACTIVE / INERT / SILENT / NO_SIGNAL / WAITING. `rpt_summary` and `checkstart` include the report without changing their exit codes. Build 117 report: 13 / 12 / 1 / 29 / 8 respectively | Declared counters and active gameplay evidence for every enabled owner; ACTIVITY is distinct from readiness and acceptance |
| Static wiring and bundle (`74782d19`, `fae2405c`, `17514ec3`) | Audit covers spawn routes, unread settings, unreferenced classes, CE index gaps, zeroed spawnable rows (W009) and installer import closure (W010). Bundle adds imported audit/interior/probe modules and military-loot/disposition inputs, including floor-policy collision validator | New release install/upgrade and live spawn routes; static presence is not gameplay evidence |
| CE infected variety (#316, owner 2026-11-21) | All 19 stock infected CE families receive 153 substitution rows / 145 distinct outfit-preserving male/female posed/crawler subclasses generated from pinned stock events and validated stock config bases. Weight share is 9.4–10%, except NBCYellow: five of ten integer weights (50%) expose all five modes. Donors stay positive; event min/max totals and population_delta=0 are unchanged. Default-on composition/accessories retain receipt rollback and generated donor attachment coverage | Native CE spawning in every family, observed population/mix, female skinning, accessory/corpse inventory, clean readiness and target-load budgets remain unverified; install summaries are offline evidence only |
| Herd composition (#316) | Default-on `HCC1Variety.EnableComposition` uses five authored stock CE context palettes, excludes leased outfit/model families and favours mixed sexes/silhouettes within existing caps (`MemberTypes` overrides retain their selection) | Clean boot/readiness, visible group mix, fold/re-materialization, switch-off rollback and target-load timing unverified; registry row integration by lead |
| Route/activity variety (#316 lever 6) | Default-on `HCC1Variety.EnableActivityVariation` varies nearby authored corridors, traversal order and 2–4 m waypoint radii under existing work budgets; the dormant chance carries a stable ±0.08 per-sleep-place bias | Clean ready=true boot, route/door/release and day/rain observations with one server and at most one client remain pending |
| Infected capacity (`26fc6ac8`, following migration revert `5f143709`) | Exact legacy `MaxTracked=24` becomes 256 in memory with one migration line; other values honoured and profile untouched. `MaxPosed=24` | Native roster headroom, persistence and held-pose cost; no multiplayer or target-load verdict |
| Listed zone holds (#284, `2d9cd91b`) | Holds only explicitly listed sites after zone init while guards or live replacement infected are operational. Dedicated work slot 39, `Performance.TickWeight_ZONE_GUARDS=1` (1–64) | Native mixed/dynamic zone states, site release/reacquisition, moderate guard difficulty and tick cost |
| Holdout recovery (#285, `cfbfb6e4`) | Phase 3 retries founding after losing a cache; `recovery_attempts_window` reports attempts | Native cache loss, refounding and finite inventory conservation |
| Infected tracking (#286, `fbc8685a`) | At most one far idle record beyond max(1000 m, IdleRange) released per bounded scan; routes, offers, clues and recent hits protected. Separate herd lease capacity; no deletion or repositioning | Native recycling, fresh variety admission, horde/lease continuity and cost |
| Season clock (#287, `649447a2`) | Clock resumes after checkpoint lag; valid seasonal consumers stay available. Shipped `MaxUncheckpointedSeconds` now 300 s (was 120) | Native checkpoint delay/recovery, persistence and seasonal consumer continuity |
| Stamina resync (#288, `0c8cef3d`) | Client asks again when active; server replies at most once per connection per 10 s | Native join/reconnect ordering, prediction and UI |
| COT permission (#289, `783ebe18`) | HCX requires `JM_COT_Scripts` and binds `HollowCountry.Admin` unconditionally | Native load order, authorised access and revocation |
| Moving wind (#290, `9d9fe091`) | Native forest-wind sound attaches to local player, replacing null environment sound | One-client audibility while moving, cleanup and indoor transitions |
| Story windows (#291, `d51c2d36`) | Both schedulers admit arrivals below occupied window capacity; retained catalogs may hold 12 rows, authored catalogs stay capped at 4 | Story 6 admission, retained save migration, arrival timing and restart |
| Taped weapon lights (#292, `c3b37bc1`) | Detach no longer needs pre-existing build marker; bounded attach/detach/failure summaries | Native attachment, same light/battery conservation and legacy-marker detach |
| Floor containers (#293, `de5da9ab`) | Receiving containers retain native-derived lootmax; generator refuses zero-capacity HC point containers. 28 containers / 239 stranded points before, zero after | Native CE receiving-container spawns, capacity, loot accessibility and rollback |
| Familiarity counters (#294, `70de14d1`) | Bounded awards, skips and persistence summaries explain zero-record sessions | Native award/skip paths, save/reload and life reset |
| Carcass fairness (#295, `df4a4d60`) | Creation alternates with maintenance capped at four cost-one items; registered WorkUnits 16→4, MaxPairChecksPerTick 32→4 (legacy ranges remain 1–64). Runtime clamps legacy values; TargetPairsEnabled gates contact recording; spawn/refusal summaries | Native out-of-sight CE-funded carcass creation, fairness, permanent allocation and persistence |
| Scene cache missions (#296, `a33269c5`) | Kamenka/Staroye/Kumyrna cache events merge through normal collision checks/rollback; CE creates SmallProtectorCase. Closed missions may reoffer after existing two-hour cooldown | Native CE cache bind, mission close/reoffer, finite custody and rollback |
| Roadside groups (#297, `791d6694`) | 16 types target 48 active across 202 distinct groups instead of shared groups | CE active counts (40+ goal), spatial spread and encounter contents |
| Infected/loot/craft counters (#298, `b7495fda`) | Bounded alert-chain (including memory cap), refresh, house-search, interiors, siphon and crafting counters; missing refresh state reports state_fault | Native action attempts/successes, counter interpretation and activity coverage |
| World/event/radio counters (#299, `4101ca3a`) | Scene completions count observations; situation heartbeat names missing source/store; bounded radio, flip, salvage, decay and materializer counters | Native completions, source/store recovery and activity coverage |
| Door census (#300, `1f1ab722`) | Door census and pressure skip wreck/vehicle config ancestry | Native wreck exclusion while real building doors remain usable |
| Shelter support (#301, `c83c6dba`) | Bounded nearby grounded layout retries and regional placed/refused summaries; all 74 scenes enabled | Native terrain support, doors/access, rain cover and discovery |
| Weapon-pack sway (#302, `e92c0d15`) | Separate generated compatibility PBO guards empty/non-weapon hands with native 1.30 weighting | Release PBO integration remains assigned to packguard; native load/sway and no null exception |
| Client presentation (#303, `6c0f76bb`) | Server grade/presentation defaults reach clients; saved client preference wins; zero server grade stops active effect | Native delivery, saved preference priority, zero-effect cleanup and reconnect |
| Construction (#304, `c8d7b7aa`) | Fence/watchtower/flag/shelter/light kits restored; claim-aware building fortification; AI anchor fortifying uses durable slot reservations and requeues after ownership returns. r11 removes four stale kit UnregisterRecipe calls | Native recipe ordering and kit craft/place, claim checks, ownership changes, AI reservations and restart |

The r11 carcass defaults and JSON ZoneGuards performance row now match their compiled
declarations. The unused meal-buff preference has been retired from the shared registry,
settings DTO and config defaults; SurvivalAlignment remains always enabled. The full
settings consistency check currently requires the lead to remove the retired field from
`mission/hollow-country/operator/settings.json`. Admission logging also needs the coordinated
auditroutes change before native compilation. Existing profile loads use the native JSON
deserializer without an HC unknown-key rejection; old-profile loading remains a native gate. The
checker does not require InfectedClimb rows in the main JSON mirror; those ten keys already
live in the separate 3_Game registry. Extending automatic scoped-profile checking needs a
coordinated change in `tools/validate/settings_consistency.py`; no duplicate registration
was introduced here.

## Earlier implementation snapshots

Older tables and round notes preserve evidence for their stated source versions. Their old
caps, disabled defaults and integration gaps are superseded by the current record above
and the README. They are not current feature-disable instructions. Teleport recovery is
not permitted; native navigation owns movement. Historical compile successes do not
accept the final source or any missing native experiment.

| Area | Authored now | Still missing or gated |
| --- | --- | --- |
| Shared runtime | Server lifecycle, 16 KiB configuration reader, module registry, real elapsed time; actual compiler/core script-VM self-test/initialization under Wine. Native Windows vanilla join, movement, inventory and reconnect passed on 2026-11-17 | Final-source addon compilation, native Windows addon loading, diagnostic and signed loading gates |
| Economy | Stock audit, conservative profile/delta tooling, isolated install and exact rollback; pinned measured-export candidate preparation | Verified apartment/barracks coverage correction; observed engine merge/eligibility; measured contextual routes and budgets |
| Interiors | Stable identities, three two-prop trial layouts/two histories, immutable manifest, bounded startup placement; conservative journal migration and orphan quarantine. Bounded measured-catalog import binds exact reviewed documents, live house identity and contextual item groups; 15 synthetic checks and native run 054 compilation. Run 060 read an existing house's native pose, bounds and coordinate transforms. HC-24 now admits schema-2 and paged schema-3 packs through one retained startup job, shared tick budgets and atomic publication; stop/refusal clears the job. #138 adds a bounded building-position resolve cache (cleared on stop), preserving resolve/#q diagnostics, and cancels deferred interior pathgraph calls on stop; synthetic regressions pass, runtime acceptance pending | Complete measured catalog and layout fit, navigation/collision/replication, native parser/import/migration/recovery trials. Normal-build placement and search remain hard-gated; measurements and imported metadata do not prove fit |
| Search | Native continuous action, server-owned target/range/LOS/time/lock checks, shared finite allocation pool and actor-bound reservation/attempt/result journal | Shared CE allocator/reconciliation and proven durable inventory/ledger commit. Native UI/audio/races/restart unobserved. Normal-build search is hard-gated |
| Crafting | Three native salvage recipes, fixed yields, ownership/type/condition checks, tool wear, null-spawn and completion guards. All 36 audited cutting-tool classes share registration, eligibility and completion rules. Native run 055 compiled with crafting enabled and passed registered-definition/config checks | Native inventory/ground behavior, tool wear, concurrency/crash safety, balance and compatible rifle wrap observation. The broader justified recipe scope remains under review |
| Full item audit and utility extensions | Whole-source recipe census; chunked in-engine configuration exporter preserves native type variants and unresolved fields; unhooked fuel arithmetic with binary32 no-creation checks. Run 035 enumerated all 7,389 classes across four roots/15 chunks. Bounded flashlight matrix retains every class; its raw-artifact shape exercise emitted 47,888 candidate pairs | Complete item/recipe/action and usefulness audit, broad justified crafting scope, native fuel action and durable conservation, taped flashlight mounting/switching/geometry and client qualification. Candidates do not establish compatible geometry or gameplay |
| Infected | Bounded visual-clue sampling, native voice provenance and bounded relay chains, native pack route validation, observed progress/purpose and fair retarget scheduling, durable pre-transfer cohort intent, semantic room catalog interface/order and exact storage-identity recovery. Every complex path (pack routes, adoption, member recovery, investigation, chains, stimulus routes) is admitted only by its own qualification and fails closed with a reason code; dormant journals load verbatim; one stimulus selection (visual > external heard > retained memory) is shared by chains and investigation; explicit four-entry variant map. Final source compiled and initialized under Wine (compile 079) | Real measured room catalog, safe horde abstraction/activation and a complete recognizable variant roster. Native route traversal/perception, relay audibility and restart recovery remain unobserved; no periodic journal appeared during the 90-second hold |
| Packaging | Original-source container/signing/smoke tooling; transaction-based install/upgrade/recovery/rollback. Official tools signed and positively verified the exact run 057 addon under Wine; that addon compiled and initialized | Signature-enforced server/client loading, client tests, combined load/performance and destination rollback |
| Stamina and weight | Native handler scaling, bounded server profile, authenticated client receipt/session reset and separate cached weight/stamina bars. Defaults request 0.25 continuous exertion, 2.5x recovery and half the vanilla weight penalty (0.875 units/kg above the native 6 kg free threshold; native 5-unit minimum and 100-unit maximum with native defaults). Schema 1 profiles missing WeightPenaltyScale default to 0.5; invalid profiles and explicit disables are preserved. Native discrete jump/melee costs are retained. Earlier run 046 compiled the previous wiring under Wine | Final-source enabled profile loading and native delivery/order including WeightPenaltyScale, prediction/modifier compatibility, rendered layout and connected-client gameplay validation with one client. Earlier compilation does not establish the new defaults or synchronized custom stamina; DayZDiag and normal PBO/server acceptance remain pending |
| Taped flashlights | Unhooked mount/removal service, consumed-tape checks, identity/condition/energy conservation, full binding replay guards, bounded intent/image journal and native inventory observations/transfers. Thirty-six synthetic checks include unresolved-operation quarantine, intent before custody acquisition and an operation-bound terminal write after confirmed release. Native run 057 compiled this service and initialized under Wine | First-release scope is native light-slot pairs only (rail/handguard rifles and pistols); other hosts are post-v1 (#58). Qualified host/slot/geometry matrix, exclusive inventory custody integration, LOS provider, native mount/removal/switching, crash recovery and single-client presentation. No actual host is qualified or automatically enabled; journal readback does not establish crash durability |
| Groups and navigation | Enabled server preference, authenticated routing, permissions, invitations, markers/notes, immutable journals and ordered counters. Full positive signed epoch range through January 2038, checked expiry addition, durable clock watermark, rollback refusal and failed-commit handling now pass 99 focused checks with synthetic collaborators. Earlier run 038 compiled client recovery/map/menu/icons; its 41 synthetic native policy steps completed | Final-source compilation, native persistence/restart/RPC trials, additional map layers/roles, rendered controls, single-client privacy/reconnect and cost observations. LOS/radio requirements remain unsupported and rejected; synthetic fixtures do not establish enabled group gameplay |
| Weather and atmosphere | Native XML candidate generator with pinned source, explicit operator profiles and preserved unspecified settings; 16 synthetic regressions including early rejection of unrelated directory entries. No-op generation preserved the four inspected official mission templates byte-for-byte | Native XML/storage/map-script interaction, profile balance, visibility, accessibility, performance and rollback. Lighting and volumetric fog remain separate feasibility work; no weather profile is automatically installed |
| Optional events | Bounded unhooked event definitions, opt-in participants, ordered server observations, revision/replay protection, expiry/cancellation and frozen definitions; 18 focused checks. Native run 042 compiled the director | Native observation/objective adapters, mission roster, AI integration, durable economy-backed rewards, persistence and client presentation. Nonzero rewards remain blocked |
| PvE AI groups | Bounded declaration audit for a source-pinned optional provider: dependency subset, finite-ammunition/damage settings and observer retirement context; 31 focused checks. Native navigation owns AI movement; teleport recovery is forbidden | No provider is installed or qualified. Exact artifact admission, permissions, finite ammunition, ordinary damage and cleanup fairness remain required. Native-first provider implementation, combat/navigation, encounter integration and measured capacity remain outstanding |
| Ecology and migration | Built, native verification pending: default-on day-cycle herbivore field/shore surveys, short navmesh-checked native input leases for walking/grazing/drinking, home-area bias over hours, and town-pressure phases over UTC days. Existing infected owner offers complete native packs (up to 40) one 80 m waypoint step per 600 s through a crash-safe prepare/completion journal; no bodies are created, regrouped or teleported. Shared tick admission, one combined animal/infected path attempt per tick, 32 herd homes, eight animal leases, settings registry and save scheduler are wired. `Ecology/cycle.json` supplies global/animal/infected off switches; core emits the Ecology readiness receipt and periodic `[HC Ecology]` lease/route summaries | Lead native compile and one-server/at-most-one-client boot pending. Verify input override release on threat/death/expiry, shore classification and approach, actual grazing/drinking presentation, pack ownership/interruption/arrival, cadence across restart and interrupted-store refusal, settings-off, and combined target-load cost. Counters describe leases/command requests, not feeding transactions or arrival. No inspected animal destination setter or runtime CE weight setter: CE respawn weighting stays unchanged; only existing packs drift. Home identities are reacquired on restart; terrain shore survey can miss narrow water, dawn/dusk uses fixed 05–08/17–20 game hours, 64-town catalog is capped, and legacy full migration journals can refuse new enrollment. Ecology currently uses direct shared-pool admission within worker scope; a core consumer slot/fairness integration and target-load profiling remain pending |
| Animal composition (#316 lever 5) | Install-time `Ecology.EnableCompositionVariety` defaults on; existing cattle/deer/goat/wolf and hen selections plus supplied rabbit/rat/raven palettes vary within unchanged event budgets and ambient caps, with receipt rollback | Native boot/RPT summary hook, visible compositions, group-size distributions, natural activity/flight, dependency rendering and stop/restart rollback on one server with at most one client remain pending |
| Firearms roster, datamine census and optional SNAFU subset (#30) | Offline tools and data: `tools/package/firearms.py`, `firearms_roster.json`, `snafu_optional.py`, `snafu_allowlist.json`, `tools/audit/firearm_census.py`. Owner decisions of 2026-11-17 are applied: 2x scarcity (vanilla weapon nominal 342, max 28 per gun); datamined rows spawn at rare counts, marked `acceptance: pending-local`, with one switch (`--no-datamined`); SNAFU conservative 7 plus WW2 SMGs plus 5 modern military-tier arms. Install and rollback are hard-link and outside-path safe | Not observed in DayZ: spawns, firing, ammo, CE totals, the SNAFU load and signed packaging are all pending local acceptance. The Tactical Flava optics subset is pending. Nine stock-absent variants are deferred. Not production-enabled |
| Melee (2026-11-20) | Default-on `EnableMelee` and 32 scoped `Melee.*` settings. Infected head executes and leg cripples through `HCMeleeExecute`/`HCMeleeCripple` CfgAmmo (zombies only; PvP unchanged), weak-arm transitions, light-stagger poise with forced heavy counters, player stagger immunity and block-to-counter, weight-scaled stamina, LIGHT in-place distance with connect-time client sync (RPC 4854010), turn while swinging (200/120 deg/s) and a guard shove on the vanilla kick/push path. Wine compile gate: World module compiles with zero script errors | Unverified gates: Windows boot ready line; MEL-05 PvP unchanged; MEL-10/MEL-11; nested ProcessDirectDamage to EEHitBy re-entry; GetDamageZonePos frame; client sync delivery; turn/lunge jitter and correction snaps; shove stagger on infected; `HCMeleeShove` ammo row not yet added (falls back to Dummy_Heavy) |
| ZoneGuards (2026-11-20) | Default-on HCX module: per-zone states held / overrun / abandoned, bounded daily escalation transitions (max 2 per day, 2-day cooldown), guards through the shared HCX patrol path (3-6 per zone), up to 6 military infected per overrun zone, persistent state in the profile; 3 sample zones ship in `ai/zones.sample.json` | Unverified gates: Windows boot ready line; spawning, perception and moderate difficulty; cleanup; persistence and wipe; transitions over days; target-load cost; more zones beyond the three samples |
| #316 pose variation | Pose commands default ON without PoseCommand.enable; acceptance/infected_poses.disable remains the kill switch. Shared ZombieBase hook admits only marked HC classes, retaining native outfit/sex/military script ancestry. Both sexes inherit identical ZombieBase.enfanimsys mesh/skeleton/graph/instance in pinned 1.30.164289 config; female poses included. Existing MaxPosed, staggered fresh-body admission, bind preflight, settled-Move start and calm deadlines remain; face-down selection deferred (graph modes 1–4) | Lead native compile/boot pending; unverified: every male/female pose/get-up, threat/hit/reach wake, deadline/cursor latency, reconnect, slot release and switch-off behaviour on one server plus at most one client. Default-on decision isolated in HCPoseCommandAdmission.c for revert if #315 recurs |
| CE posed and crawling infected (#315 fix landed, native pending) | be9d2322 fixes the missing constructor argument with StartCommand_Script(new HCPoseCommand(this)); no StartCommand_ScriptInst call. Posed CE children restored across all stock families; default-on command admission isolated in HCPoseCommandAdmission.c. Caps, bind preflight, settled-Move start and infected_poses.disable retained. RPT: [HC Variety] ce_variant_classes, ce_variants; [HollowCountryAnims] pose request, pose binds, pose command started | **Blocked:** native verification of the landed #315 fix remains pending; no engine experiment accepted. Lead must check crash-free boot/readiness, CE crawl/fall, male/female pose playback/get-up/client skinning and kill switch. CE speeds remain vanilla (herd locomotion roles unchanged) |
| CE encounters and loot points (r5, 2026-11-20) | 16 HC event types at nominal 48 over 202 anchors (min separation 401 m), installed last and rolled back first; firearms at 3x stock nominal/min; 227 loot point groups / 5,147 points (201 interior surface groups, 3,925 surface points) merged across `additions.json` and `additions-interiors.json` | Unverified gates: live CE active counts, anchor terrain/road clearance, actual loot tiers and spawning, surface point fit in buildings, economy cost at target load |
| Loot in ungrouped buildings (2026-11-20) | `loot-points/new-buildings.json` adds 9 loot groups and 362 map rows for Chernarus buildings that had no stock group. Rows come from the pinned ChernarusPlus.wrp (11,679/11,679 stock rows reproduced). Wreck UAZ, tractor and closed trailer copy their `_DE` twins. Military towers, water towers, Church2_1, Office_Municipal1 and two cement works classes get audited floor points with containers, lootmax and categories from vanilla analogs. `loot_boost` applies it all-or-nothing against the stock mapgrouppos hash. Rows within 80 m of event sites or 150 m of map overlay anchors are dropped. Refused: Misc_Toilet_Mobile, CementWorks_MillA, Castle_Donjon and Wreck_C130J_2 | Unverified gates: CE loading the new groups (no proto/pos errors in RPT), loot spawning at the points, items reachable in game, Office_Municipal1 upper floors, a native census for the refused classes |

#135 infected LOD review follow-ups (source only): `Infected/lod.json` now
ships full AI through 300 m, idle through 1000 m, materialize through 900 m,
fold beyond 1000 m and visibility checks through 1500 m. These are provisional
design defaults derived from the 1 km gunshot/network planning scale in
`docs/OUTSTANDING.md` and the 1000 m visibility baseline in
`docs/LOCAL_ACCEPTANCE_V1.md`. The 300 m near-threat setting in
`mission/hollow-country/ai/README.md` supplies a near-action precedent; using
it for infected is a design assumption. The 100 m materialize/fold hysteresis
and 500 m observer margin are provisional design choices. No measured gunshot cutoff
is documented. All bands remain validated operator settings: full < idle,
materialize >= full, fold >= idle, min-spawn < materialize < fold <= visibility,
idle <= 2000 m and visibility <= 3000 m. Existing explicit settings are retained;
older inconsistent profiles are refused with the existing invalid-ranges line.
Virtual herds stay **OFF** by default and posed budgets stay 12/12/12. Startup
prints all bands. Recyclable dead/folded actor entries move to a separate
24-entry FIFO with oldest-entry eviction; unresolved horde recovery evidence
stays reserved. Head, chest and lateral sight samples start at each observer's
head bone; each sample checks view/fire geometry, so at most six actual casts
are needed per observer. Any clear sample or incomplete budget refuses the
transition. The per-attempt tick budget is `MaxObservers * 6` (default 36,
hard maximum 48), shared by all samples/observers, so every allowed observer
can be proven occluded; incomplete checks refuse. Stats print `rays_per_min`,
`ray_peak` and `ray_budget`. Shutdown performs no fold/delete: living members
remain included in persisted `Alive`, and session-held leases reserve surviving
bodies across module stop/start; deaths and external claims debit once, while
missing bodies return to virtual capacity. Reuses the LOD cursor, player roster,
observer gate, admission and shared save scheduler/journal. Tests execute authored
control flow with synthetic engine ports. DayZDiag, normal PBO/server restart and
single-client partial-cover/foliage/vehicle/optics checks remain **runtime acceptance pending**.
Target-load budgets remain provisional; stop/start handles are session-only and
cross-process body persistence must be checked natively. No shared HCSettings,
serverDZ network defaults or global settings JSON edits are required.

## Round r6 — 2026-11-20 (source landed; native boot 115 pending)

All of these ship default-on. None has been observed in DayZ yet; "pending"
means the gameplay is unverified, not that it is switched off.

- Settings (#268): horde caps 4 active / 160 members in shipped defaults and mission settings.
- Lint (#244 #266 #269 #270): HC-E014..E017; HC-E016 also covers bracketed and grouped handle checks (#273 open).
- Compile gate: friendcycle runs the native gate under Wine (12 GiB cap); missing-data JSON reports after Mission loads do not fail it.
- Infected doors: door pressure policy plus a client pressure cue. Pending.
- Camp allegiance (#267): respawned camp members keep their camp's allegiance. Pending.
- Shared pacing (#256): hordes, scene stages and AI situations reserve through one director (2 per 1 km, 300 s spacing, 900 s decay; CE events exempt); finished stages release their active slot. Pending; #272 open.
- Clues: lead notes name direction and distance from 88 named localities. Pending.
- Group ping: bounded teammate map ping with server-relative expiry. Pending.
- Hints: contextual recipe and action tips plus a recipe help list. Pending.
- Story index: parsing continues while Scenes waits for a checkpoint. Pending.
- First common car: CE part rows so one common car is repairable (docs/VEHICLES.md). Pending.
- Journeys: caravans and herds walk real native paths (multi-point waypoints use ONCE). Pending.
- AI affiliation: faction armbands and up to 16 site flags (docs/AI_FACTIONS.md); pre-engagement shout/text, aim and single real-round offset warning shot built (80m warn / 40m or raised-weapon engage, bounded cooldowns). Native verification pending: EXP-L3 trajectory/ricochet safety, ammo/FSM/client presentation and de-escalation; never-hit acceptance remains open.
- Military zones: the 17 primary zones split into 30 envelopes of at most 2 km, so all 98 guard sites sit inside one. Pending.
- Boot perf (#271): Holdouts publication, interior resolve misses, save promotion and HCX readiness diagnostics are staged or sampled. Timings pending.
- Interior surface loot: 1,301 statically audited surfaces in 142 types, plus 679 floor points (1,980 points / 224 merged types; 202 placed). Every `335915c6` point is retained; the stripped-server visual refusals from `fa0c2ac8` are corrected. [Coordinate receipts and per-type comparison](LOOT_POINTS.md#surface-point-preservation-after-fa0c2ac8). Native CE/support/access/restart gates, full coverage and the 3,000-point target stay open (#274). Pending.

## Living Country — V2

V2 preferences admit their modules by default; experiment verdicts are logged
without blocking startup. Dependencies, content and persistence checks still
apply. Compilation and dedicated-server initialization do not establish gameplay
acceptance. Server flags below do not control client-local visuals or undo
installed mission overlays.

| Module | Flag | State |
| --- | --- | --- |
| Grade, Lighting, WeatherDays | `EnableGrade` (weather also respects `EnableAtmosphere`) | being built / runtime acceptance pending |
| OptionalPacks (AmbientAnimals, Bicycles), Polish (Hints, EnvSound) | `EnableAmbientLife` | being built / runtime acceptance pending |
| SignsOfLife | `EnableSignsOfLife` | being built / runtime acceptance pending |
| Shelters, WreckSalvage | `EnableTravel` | being built / runtime acceptance pending |
| MapPins | `EnableTravel` or `EnableLeads`, with each pin kind filtered | being built / runtime acceptance pending |
| World, Escalation | `EnableWorld` | being built / runtime acceptance pending |
| SettlementDecay, InfectedMemory, HordeMigration, LootRefresh | `EnableWorld` | being built / runtime acceptance pending |
| Leads, Radio, Morse, Notes, BodyStories | `EnableLeads` | being built / runtime acceptance pending |
| Camps (tiers, visitors, mailbox, theft eligibility, probes) | `EnableCamps` | being built / runtime acceptance pending |
| Materializer, FactionConflict | `EnableEncounters` | being built / runtime acceptance pending |
| Holdouts, Pickers, DeadDrops | `EnableEncounters` | being built / runtime acceptance pending |
| Scenes and scene chains | `EnableEncounters` | being built / runtime acceptance pending |
| Optional Expansion living-world addon (Factions, Stance, AskForNews, Checkpoints) | `EnableEncounters`, plus optional provider dependencies | being built / runtime acceptance pending |
| Client grade, lighting, signs of life, hints, environmental sound, map pins and Morse presentation | Client-local defaults; server flags apply to corresponding server modules only | being built / runtime acceptance pending |
| Travel CE content and optional animal/bicycle mission overlays | Installed content; flags alone do not roll it back | being built / runtime acceptance pending |

The [V2 acceptance checklist](LOCAL_ACCEPTANCE_V1.md#v2-living-country-scaffolding)
retains feature steps, missing observations and single-client checks. Operator
settings, profile files and dependency loading are in the [handbook](README.md#living-country--v2-operations).

## Earlier native diagnostics

Native run 042 also compiled the unregistered fuel diagnostic action: live
server authority, actor/car/vessel leases, one-shot debit/readback/credit and
mismatch refusal. Its 26 focused checks use synthetic native collaborators.
Actual fuel movement, compatible tools/vehicles, crash/save recovery and ordinary
client action registration remain outstanding. A fixed five-case infected death
probe now runs through a receipt-aware bounded normal-server harness. Actual run
043 under Wine exhausted its 80-second startup/observation budget before mission
initialization; cleanup completed within the 90-second outer bound. No case or
death receipt was observed. Rendered corpse/loot/replication checks remain open.
The first fixed-purpose fuel run, 045, also timed out during startup with no
receipt or fuel movement observed; owned-process cleanup was confirmed.
Fresh runs 047 (death) and 048 (fuel) used an explicit 180-second outer startup
allowance, preserving the 60-second fixture watchdog and all receipt checks.
Both initialized, then timed out without a complete receipt. Death reached its
health-only case; fuel created its three owned entities but recorded no action
start or transfer. No update frames were recorded in the partial fuel receipt.
Outer-process cleanup was confirmed. Actor-free control 051 then completed
three balanced SYSTEM updates and two queue callbacks when only ce.InitOffline
was omitted. Matching stock-CE control 052 timed out inside that call before
main returned, with no callbacks; cleanup was confirmed. The bounded observation
ended before ce.InitOffline returned. Its roughly 104-second observation inside
that call does not establish a permanent stall, a native Windows cause, or either
gameplay fixture's acceptance. Run 058 then separated an explicit 600-second
startup allowance from the 60-second callback fixture. It again ended without
CE_INIT_EXIT or any SYSTEM callback, taking 605.265 seconds including 5.063
seconds of confirmed process cleanup. This is a failed stock-CE diagnostic under
Wine, not evidence of a permanent engine stall or a native Windows cause.
Run 061 then omitted only the addon launch argument while retaining stock CE
and fresh isolated storage. It reproduced the missing CE return/callbacks and
timed out after 173.024 seconds, including 5.022 seconds of confirmed cleanup.
This reproduces the bounded failure without requesting the addon; it does not
identify the underlying engine/environment cause or prove ordinary Windows
startup fails.

CE-disabled fuel control 063 compiled and initialized, then reached one SYSTEM
update and three ticks. Its owned car, actor and vessel spawned and the actual
refill component was identified, but live range/LOS/eligibility validation refused
the action. No transfer was attempted. The failed receipt observed deletion of
all three owned entities and the outer harness confirmed process cleanup in
81.491 seconds. This narrows the diagnostic failure without accepting fuel use.

Death-selection diagnostic 065 compiled after concrete syntax fixes in failed
runs 062/064. Its scheduled spawn callback executed, then the native engine
crashed creating the infected in the CE-disabled control. No damage/death
observation completed. Outer cleanup was confirmed; the historical report also
reached its timeout. The harness now detects the engine's fatal crash marker
directly and revokes success even if the crash appears during final collection.
The cause of the native creation crash remains unresolved.

CE-disabled measurement run 060 completed in 73.866 seconds with one balanced
SYSTEM update and queue callback and confirmed process cleanup. It identified
one reviewed existing `Land_House_1W01`, read collision/clipping returns and
round-tripped four basis points and 18 stock XML reference points. It created no
entities. Twenty focused preparation/receipt checks pass. The native bounds'
coordinate basis remains unqualified; these observations do not establish room
labels, furniture clearance, door/stair routes, rendered fit, replication or
runtime loot eligibility. Earlier run 059 exposed a reserved parameter name in
the generated mission; that compile failure was corrected before run 060.

Whole-survey tooling retains all 11,679 stock placements, 436 prototypes and
7,389 native metadata rows. Twenty-two behavioral checks cover reviewed bounded
batches and strict acquisition merges. Admitting run 060 measures exactly one
placement; 11,678 remain unmeasured. Model metadata and a measured pose do not
qualify room labels, furnishing fit, navigation or CE eligibility.

Raw experiment records and machine inventories are maintained locally.
The whole-content review workbook retained all 7,389 native classes and all 234
source recipe classes across 3,056 installed script files. Its 2,344 references
include 55 unresolved references, including one malformed vanilla literal;
all 9,674 possible links were emitted. Enumeration and matching do not establish
craftability, useful balance or the complete effective item/action audit.
A separate full-source action census retained 460 candidates, 2,118 call
observations, 32,603 declarations including 365 global functions, and 301
categorized item callbacks.
Its 399 unresolved calls and 473 unresolved ancestries remain explicit;
effective dispatch and gameplay usefulness still require examination.
A bounded utility index now retains those complete admitted cohorts together,
including 180 repeated declaration-ID records, 3,595 repair-target observations,
nine kit classes and 2,302 possible kit/target links. Its 26 synthetic checks pass.
Array element typing and actual compatibility remain unknown; file admission and
authenticity are separate from internal source-manifest consistency.
Offline translated scalar tests check a restricted subset of authored policies;
source assertions inspect contracts. Neither is an Enforce compiler or engine.

Actual DayZ compiler and official signing tools have run under Wine in an
isolated local environment. A bounded run compiled all modules,
passed the core script-VM self-test and reached initialization. Integrated run 018
repeated this successfully; official tools verified its development signature.
Run 057 subsequently compiled the current addon, initialized and held for 10.021
seconds. Official DSSignFile and DSCheckSignatures then signed and positively
verified that exact PBO, whose SHA-256 is
`82066928e46f669f81f9d4be38795ed12142069937cb52e5fa2128a4d9795d48`.
The development key remains outside the repository. This verification does not
establish signature-enforced client/server loading or approve a release.
Diagnostic 017 emitted a native plugin error and is a failed smoke. See the
issue tracker for validation summaries and outstanding gates. These observations
do not establish native Windows or native gameplay acceptance.
Tasks requiring unobserved gameplay remain open.

## Inventory sizes — owner playtest 2026-11-18

Spec: owner's scoped request on base `915aef1`; the named legacy spec files and
shared brief were absent. Plan/tasks: behavioral RED → vanilla declarations →
JSON rules/inheritance → merged config → check/package/regressions. Source tasks
are implemented; runtime acceptance and the existing-test scope decision remain open.

Final counts: **76 backpacks, 20 one-slot medical, 474 general** (570 overrides,
24 verified defining addons). `config/inventory-sizes.json` records each actual
parent, defining CfgPatches addon/member and vanilla/new dimensions. The unchanged
`tools/audit/pbo_config.py` reads installed vanilla addons only. The cached workbook
has no sizes; all 570 parents match it. All requiredAddons names were verified in
vanilla PBOs, including existing DZ_Scripts in `dta/scripts.pbo`. No Workshop
content or vanilla dumps are generation inputs or shipped assets.

Backpack width/shell stays unchanged; rows become ceil(rows × 1.5), including
bases/variants without compounded scaling. General 2×2 becomes 1×2 by shrinking
width. Area-two tools must weigh strictly below 500g; categories/includes are
explicit in JSON. Excluded: 413 cargo holders, 113 firearms/weapon attachments,
751 definitions outside area rules, 72 area-two category/weight exclusions and
868 hidden/non-inventory definitions. Already-one-slot items need no override.
Only backpacks change itemsCargoSize; an excluded descendant cannot inherit a
changed shell/cargo. Public diagnostic variants follow their family.

One-slot medical changes: AntiChemInjector, BandageDressing, BloodBagEmpty,
BloodSyringe, CharcoalTablets, ChelatingTablets, ClearSyringe, DisinfectantAlcohol,
Epinephrine, IodineTincture, Morphine, PainkillerTablets, PurificationTablets, Rag,
SewingKit, StartKitIV, Syringe, TetracyclineAntibiotics, Thermometer, VitaminBottle.
InjectionVial/BloodTestKit were already one slot; larger bags/spray use the general
rule; splints/defibrillators stay unchanged.

RED: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_inventory_sizes.py -k medical_explicit -v`
→ `Ran 1 test`; `FAILED (failures=1)` (Rag/SewingKit/SyntheticMedicine missing).
GREEN: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_inventory_sizes.py -v`
→ final `Ran 22 tests in 0.112s`; `OK`. The final extra RED caught a cargo-only
child override permitting inherited shell shrink; the property-specific guard
fixed it and leaves the actual vanilla block unchanged.
`PYTHONDONTWRITEBYTECODE=1 python3 -m tools.package.inventory_sizes --addons /mnt/d/HollowCountryLocal/runtime-v1/addons --check`
→ exit 0: native manifest, deterministic block and addon coverage agree. A stale
temporary config returned exit 1 without writing. `--review-only --check` checks
authored consistency only and never verifies vanilla.

Package/config selection (`rg -l 'config.cpp' tests/unit` plus package/sign/PBO)
ran 749 tests in 183.854s: one failure, one skip. Full command
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v`
ran 5,878 tests in 390.830s: the same failure, one skip, three expected failures.
It included 21 inventory tests; the final extra regression/guard then passed the
22-test focused run and native check. The leg-zone check in `test_gameplay_delta.py`
was then scoped to the ZombieBase block, and the full suite is green.

Final unsigned PBO build/verify passed (255 entries). config.cpp remains text,
verified byte-for-byte after packing; signing operates on the unchanged opaque
PBO and its existing flow is retained. Git metadata was not written; the writer
commit message is set. DayZDiag, normal PBO/server/client loading, inventory fit,
persistence/reconnect and nesting safety remain **pending**; target-load balance is unmeasured and outside acceptance.
Offline checks do not grant production acceptance.


## HC-12 / HC-13 forage — round 2, 2026-11-18

Spec: the owner's P1–P3 correction on `4f889bd` supersedes that commit's
unconditional visibility refusal and calendar-independent content. The two
AGENTS-named specs and their plan/tasks are absent from this worktree; the
primary checkout copies were read as design input. Current session decisions
remain authoritative. Source acceptance is distinct from native acceptance.

Plan/tasks (source complete, runtime pending):

- P1: restore default-open admission followed by the existing forest/water/slope,
  geometry and 30m player-distance vetoes. Restore June–November herb chance,
  summer SambucusBerry/CaninaBerry and autumn mushrooms/CaninaBerry. Log pending
  visibility/native-generator coexistence once at Start; invent no engine API.
  The synthetic Start/tick/spawn/pickup test reclaims an expired record at the
  40-record cap, materializes an item, applies familiarity to refill delay,
  rejects duplicate pickup rewards and verifies character death/new-life reset.
- P2: archive the validated legacy image to `progression.v1.json` before
  conversion. Carry scores into v2 for a currently observed living account
  with a nonzero native character ID; other rows stay in v2 as bounded
  deferred rows (`LegacyDeferred`) and map once on that account's first living
  pickup, or reset on an observed death (#169). Emit one `[HC Plan] HC-13 legacy`
  line with `migrated`, `deferred` and `dropped_over_cap` counts. An archive
  byte-identical to the current v1 image lets an interrupted migration continue.
  Archive failure leaves v1 untouched. Existing archives are never overwritten;
  a v1/archive collision requires operator recovery before another migration.
- P2: `GetPersistentID(0,0,0,0)`, unavailable character handles and empty identity
  results earn no familiarity and create no shared row. The native method has
  no success return; all-zero is treated as unknown. Log character-ID refusal
  once per module Start. Allocation/reconnect/restart/death stability remains an
  engine experiment even though the inspected API declares restart stability.
- P2: pickups mark forage and familiarity dirty with no synchronous file I/O.
  Routine checkpoints wait at least 60 seconds since the last successful save;
  Stop flushes. Creation retains its pre-spawn durable reservation, and death
  retains its synchronous familiarity tombstone barrier. Those barriers can
  save sooner than a routine checkpoint. A crash before a pickup checkpoint
  can retain the previous reservation timer and lose recent familiarity gains;
  records never reconstruct picked items.
- P3: optional `MaxFamiliarityRows` accepts 0..128; absent/0 resolves to 128.
  Lower positive values evict oldest gain time first (zero-gain/dead rows use
  their reset/decay epoch), preserving array/cursor order. Apply lowered caps to
  loaded stores durably before admission and make room for new accounts.
  Forage resets `m_Deferred` on Stop and every Start, including disabled Start.

Actual RED, `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_forage_round2 -v`:

- `AssertionError: 1 != 0 : eligible default candidate must materialize`
- `AssertionError: '' != 'BoletusMushroom'`
- `legacy rows must be archived before conversion` (archive missing)
- `AssertionError: 3 != 4 : pickup must not synchronously save`
- `AssertionError: 2 != 128` and `Unknown field MaxFamiliarityRows`
- `AssertionError: 0 != 40 : Stop must reset deferred receipts`

P1 GREEN with `tests.unit.test_hc_forage tests.unit.test_v2_world` appended:
`Ran 6 tests`; `OK`. P2/P3 GREEN, same focused command: `Ran 7 tests`; `OK`.
The identity-restart single-method RED was
`AssertionError: 2 != 1 : a later Start gets one fresh bounded diagnostic`;
after the reset fix, the full focused module GREEN was `Ran 8 tests`; `OK`.
The seasonal expectations in test_v2_world and admin forage behavior are unchanged.

Pending: DayZDiag compilation/boot, normal PBO/server tests, single-client placement,
visibility/pop-in and replication, native generator coexistence, persistence-ID
allocation/reconnect/restart/death, pickup/crash/restart and archive recovery,
plus single-client performance observations; target-load budgets remain provisional. No production qualification is asserted.

Final GREEN, exact requested selection:

```sh
mods=$(rg -l -e 'HCForage|forage|progression' tests/unit | sed 's#tests/unit/##;s#\.py##;s#^#tests.unit.#' | tr '\n' ' '); PYTHONDONTWRITEBYTECODE=1 python3 -m unittest $mods tests.unit.test_script_syntax tests.unit.test_enforce_locals tests.unit.test_script_identifiers tests.unit.test_hygiene
```

Result: `Ran 252 tests in 17.592s`; `OK`.
`python3 -B -m tools.validate.enforce_lint --no-native`:
`enforce_lint: pass findings=133 new=0 stale=0 native=no`.
Additional settings/survival regressions: `python3 -B -m unittest tests.unit.test_runtime_settings tests.unit.test_survival_ideas -v`
→ `Ran 12 tests`; `OK`. `git diff --check` passed. Changed Enforce files have
at most 8 plus operators per statement. No commit/push or game execution was run;
Banso's writer owns the eventual local commit.
||||||| parent of 0de6dbc (Integrate HC-24 staged template pack admission and fix paging limits)
[Operator keys](../mission/hollow-country/ai/README.md) and
[cap inventory / implementation record](../mission/hollow-country/ai/README.md#implementation-record-ai-caps-2026-11-18) record
save compatibility, invalid-key fallback logs, deterministic world-seed sizing
and all deferred checks. HC-10 custody persistence was applied as a separate
prerequisite. No HCModule/config.cpp/Admin changes are needed. Offline evidence
is source/policy verification only; DayZDiag, normal PBO/server, single-client
visibility/audio/replication checks remain pending. Target-load budgets are provisional and outside acceptance.
Budgets are provisional until measured; production enablement is not established.
[Operator keys](../mission/hollow-country/ai/README.md) and
[cap inventory / implementation record](../mission/hollow-country/ai/README.md#implementation-record-ai-caps-2026-11-18) record
save compatibility, invalid-key fallback logs, deterministic world-seed sizing
and all deferred checks. HC-10 custody persistence was applied as a separate
prerequisite. No HCModule/config.cpp/Admin changes are needed. Offline evidence
is source/policy verification only; DayZDiag, normal PBO/server, single-client
visibility/audio/replication checks remain pending. Target-load budgets are provisional and outside acceptance.
Budgets are provisional until measured; production enablement is not established.


## HC-24 interior template pack index — round 2, 2026-11-18

Source/package integration complete; **runtime acceptance pending**. Trace:
the dispatched HC-24 brief and active round-2 integration request, [pack contract](INTERIOR_TEMPLATES_CONTRACT.md),
[runtime interfaces](RUNTIME_IMPLEMENTATION_CONTRACT.md) and
[remaining HC-24 work](OUTSTANDING.md#6-audit-plan-work-packages-still-to-build-hc-11-to-hc-64).
The named `docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md`
are absent from this checkout. HC-11 owns the shared master spec/plan/tasks;
no missing engine experiment is accepted by this source update.

Plan/tasks implemented: real strict schema tables → retained metadata admission
→ budgeted leaves with unchanged semantic validation → atomic publication and
receipt → stop/refusal cleanup. The existing `HCInteriorsModule` lifecycle chain
is extended inside the owned `HCInteriorTemplates.c`: no registration, config,
placement cursor or other worker's module file changes are required. The bridge
runs before the existing template extension's instance guard, so a missing
optional pilot cannot prevent loading. `HCStep=1` ends the entire module tick.
At most eight load slices run per tick, with shared `HCWorkBudget` checks before
each leaf; the existing placement loop, gameplay limits and opt-in gates remain.
The raw `load_ticks` diagnostic spans staged startup, including time between ticks;
it is not a per-tick CPU benchmark.

Accounting has one owner (`HCInteriorPackJob`): 610 leaves, up to 16 pages and
one root, at most 627 reads / 20 MiB. `pack_chunks` excludes the root and includes
pages plus leaves. The 610/611 boundary fixture explicitly starts from synthetic
ready metadata; canonical per-list caps remain unchanged (608 possible leaves).
Schema-2 leaf bytes and all published reader data are preserved. The builder
keeps all eligible templates up to 512; metadata paging replaces the obsolete
single-index byte budget. Diagnostics parse each root strictly once and log
only the root, page zero (when present) and first leaf per lifecycle.

Actual RED → GREEN records (all fixtures synthetic; stdlib only):

| Behavior / focused test | Actual RED | GREEN |
| --- | --- | --- |
| `test_hc_template_pack.TemplatePackTests.test_complete_bounded_pack_refuses_damage_and_migrates_without_gameplay_changes` | `AssertionError: False is not true` after removing injected strict tables | `ok` using real strict source |
| `test_interior_templates.ClassRowTests.test_paged_index_keeps_every_template_up_to_512` | `AssertionError: 512 != 97` | `ok`: 512 kept, one excess template refused |
| `test_hc_template_pack.TemplatePackTests.test_610_leaves_plus_16_pages_count_once_and_leaf_611_refuses` | `AssertionError: '' is not true : 609` | `ok`: 610 admitted, 611 refused through job and reader |
| `test_hc_template_pack.TemplatePackTests.test_receipt_order_bounded_read_logs_and_single_strict_dispatch` | `['pack-index'] != ['index', 'pack-index']` | `ok`: one strict parse, three read logs and ordered receipt |
| `test_interior_templates_runtime.InteriorTemplatesRuntimeTests.test_reader_stages_both_schemas_without_reloading_and_resets_on_stop` | `True is not false : startup must retain a job and yield before leaves` | `ok`: exact matching reader data, one read per file, budget deferral and restart |
| `test_interior_templates_runtime.InteriorTemplatesRuntimeTests.test_reader_propagates_job_refusal_and_clears_partial_admission` | `AssertionError: False is not true` (missing pack refusal diagnostic) | `ok`: exact job reason retained, partial rows cleared, no retry |
| `test_interior_templates_runtime.InteriorTemplatesRuntimeTests.test_module_tick_finishes_admission_and_stop_cancels_pending_load` | `1 not greater than 1 : module tick must advance pending pack even without a legacy owner`; further two-page RED: `2 != 7 : HCStep=1 must yield to the next module tick` | `ok`: actual lifecycle bodies progress, yield, finish once and stop |

Exact focused RED/GREEN invocation: prefix each test above with
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest ` and
suffix ` -v`. Cap/diagnostic REDs ran together as
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_template_pack -v`.
The initial strict RED used
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_template_pack test_interior_templates.TemplateBuildTests.test_paged_index_keeps_every_template_up_to_512 -v`:
it recorded the behavioral strict failure plus an unrelated selection error
(`TemplateBuildTests` was corrected to `ClassRowTests` before the builder RED).
The two reader REDs ran together by their complete test names. The existing
`test_hc_unit_budget.SourceContractTests.test_interior_load_time_is_logged_in_raw_ticks_once`
also caught the changed retained timer variable; its raw-tick contract is preserved.

Final verification command (all named-file readers found by `rg`, plus required checks):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_template_pack test_interior_templates test_interior_templates_runtime test_local_test_session test_tilt_rule test_house_search_flow test_hc_unit_budget test_infected_production_rooms test_interiors_profile test_server_report test_script_syntax test_enforce_locals test_script_identifiers test_hygiene test_friend_bundle -v
python3 -B -m tools.validate.enforce_lint --no-native
```

Final result: **`Ran 655 tests in 104.951s` / `OK`**. Enforce lint:
**`pass findings=126 new=0 stale=0 native=no`**. `git diff --check` passed.
Git metadata was not written; the writer commit message is supplied separately.

Native API declarations were inspected in the pinned 1.30.164289 snapshot:
`EnSystem.c:106,417,425,443` (timer/read/close), `EnString.c:240` (dispatch probe),
`EnScript.c:380,394,407,902,917` (arrays/maps), `EnConvert.c:30`,
`EnDebug.c:96`, `Game.c:914,1120` and `JsonFileLoader.c:69`.
No engine API, world scan, save scheduler, distance or production gate is added.
The source check also found no statement above eight `+` operators and no
foreach receiver other than a named local/member in the three changed scripts.

Expected native log text (placeholders are observed pack-specific numbers,
not offline evidence):

```text
[HC Plan] HC-24 pack_chunks=0 classes=0 refused=none state=pending hash_refused=runtime_sha256_unavailable runtime=PENDING
[HC Plan] HC-24 read=index.json bytes=<bytes> length=<length> runtime=PENDING
[HC Plan] HC-24 read=index-000.json bytes=<bytes> length=<length> runtime=PENDING
[HC Plan] HC-24 read=classes-000.json bytes=<bytes> length=<length> runtime=PENDING
[HC Plan] HC-24 pack_chunks=<pages+leaves> classes=<classes> refused=none state=ready hash=offline-receipt runtime=PENDING
[HC Plan] HC-24 pack_chunks=<pages+leaves> classes=<classes> refused=none state=off hash=offline-receipt runtime=PENDING
```

Schema 2 omits the page read. Missing-root control must emit exactly
`[HC Plan] HC-24 pack_chunks=0 classes=0 refused=pack_missing state=refused runtime=PENDING`.
A missing page/leaf emits
`[HC Plan] HC-24 pack_chunks=<successful reads minus root> classes=0 refused=file_size_or_read:<file> state=refused runtime=PENDING`.
There must be no later ready receipt after refusal in that lifecycle.

Still deferred: exact-source DayZDiag compile/boot (including the modded lifecycle
chain), normal PBO/server admission for both schemas and the full authored pack,
missing/corrupt page/leaf controls, stop/restart/off-path observation, installer
rollback and hashes, physical fit/navigation/audio/replication qualification and
single-client cost measurement. Existing single-client acceptance remains pending; larger-load budgets stay provisional.
Runtime checks pins/bindings/schema/read sizes; SHA-256 authenticity still belongs
to the offline installer receipt. Nothing here enables production gameplay.
