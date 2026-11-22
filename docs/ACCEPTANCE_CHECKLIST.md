# W6 admin session and W5 acceptance itinerary — #123, #133, #12, #50, #70, #78

Every result starts **PENDING**. The lead compiles and packages the landed source
natively on Windows first. This is one owner's session on a local dedicated
server with one real client, followed by a restart. The owner previously joined
the local server once without script errors; this W6 admin build has no native
compile or acceptance evidence yet. Synthetic tests, old startup notes and admission messages establish
neither gameplay acceptance nor production qualification. Target load is **3–6
players**; these capacity budgets are provisional and do not add people to acceptance.

Use the existing [setup, backups and rollback](LOCAL_ACCEPTANCE_V1.md#setup).
Keep build, settings, dependency versions and session start/end times with private
evidence outside the repository. Never copy dependencies into our addon. V2
preferences are on by default; preserve explicit operator disables. For each
enabled V2 module expect exactly one startup line with literal prefix
`[HollowCountry] V2 admission feature=` (the `HCV2Admission` producer), preference,
gate, qualified and result. Count within one server start and one input log: the
RPT may repeat script-log messages. `admitted unverified` is never a feature pass.

For each row record PENDING, PASS, FAIL, BLOCKED with the actual refusal, or
DEFERRED for a missing dependency; include time, visible result and log excerpt.
Owner decision (2026-11-19 evening): DayZDiag and normal PBO/server checks plus
at most one real client are the full acceptance bar. Record only what that
session demonstrates. Never bypass engine gates, teleport, add replacement loot,
block doors or erase journals to manufacture a pass.

## W6 admin test kit #133 and in-game map #123 — source implementation

All W6 outcomes remain **PENDING** native Windows compile, normal server/PBO
and DayZDiag checks. The owner joined a previous local build once; that is not
admin-tool evidence. The lead must add `Register(new HCAdminModule);` once in
`HCModuleRegistry.RegisterModules()` in Core/HCModule.c. No registry/core file
was edited by this worker. Client MissionGameplay/menu-factory extensions live
in the owned Admin directories and need no extra mission hook.

EnableAdminMap gates the server tools (default true, retain operator disables).
On first enabled startup it creates a private `$profile:HollowCountry/admins.json`
with `{"PlainIds":[]}`. Stop the server, populate **at most 32** actual plain IDs
privately, and restart. Never commit or paste IDs into evidence. Invalid, duplicate,
oversized or interrupted stores fail closed; recover retained .tmp/.bak normally.
Only the count is logged. Optional COT role authentication is **skipped**: this
round uses the explicit file allowlist and adds no COT dependency. Installed COT
has GetPermissionsManager/GetPlayer/HasRole methods; no COT files are read by HC.
Every server request checks the actual RPC sender's GetPlainId, including delayed
capture delivery. Non-admins receive no reply, map or player information. Their
refusal is logged at most once per plain ID per minute across a bounded 64-peer
cache; at saturation only one anonymous aggregate line per minute is emitted.

Press **Pause** (rebind “Hollow Country Admin Test Kit and Map” in Controls).
The menu opens only after an authenticated `status` reply. Off/non-admin sessions
time out without opening; no client/profile allowlist is trusted. Native chat
has only channel/name/text/colour (gameplay.c:407), not a trusted sender identity;
therefore `/hc` text is not used. Pause was absent from all 136 input/preset XML
members across 2,009 installed Workshop/vanilla PBOs scanned on 2026-11-18;
four compressed XML members were decoded in memory with size/checksum verification.
Numpad5 was bound in three alternate vanilla presets, so it was not chosen.
Existing HC inputs are retained. RPC ids **4853911** (request) and **4853912**
(reply) were unused in the full mods/ scan; menu id is 48539.
RPC id **4853913** is reserved for HC-51's server-to-client season snapshot:
three integers (version, revision, phase), targeted on join/ready/reconnect and
broadcast on phase changes and a 30-second heartbeat after first publication.
It accepts no client requests. Native transport and single-client acceptance remain
PENDING.

Buttons send `sitter`, `dormant`, `horde`, `scene`, `event`, `camp`, `holdout`,
`status`, `snapshot`, or `day` with the adjacent decimal field (clamped server-side
to 0–3650). At most one command is queued per core tick; each allowlisted admin
has a one-second ingress limit, replay tickets and a five-second snapshot limit.
There are no retries or automatic gameplay commands. Repeated commands may refuse
and never raise caps. One sitter body (including corpse) is allowed at a time,
inside the existing infected tracking/registration cap; it is created by string
class name eight metres forward only on conservatively clear flat ground. Missing
HC_ZmbM_Sitter refuses explicitly. The separate animation addon owns its pose.
Fresh `dormant` creation is **skipped/refused** because InfectedVariety exposes no
shared body lease or dormant-spawn policy; no forced native animation is invented.
`horde` asks normal CE adoption for an eligible existing cohort within 100 m;
normal member/group budgets, quarantine and genuine-cue requirements still apply.
`event` announces through the existing roster/director at the nearest reviewed
site; O remains the normal participation UI. `scene` tries the nearest unplaced
reviewed chain through normal Work only when due, without faking completion or
accelerating a live deadline. Observer/clearance refusal is expected near players.
`camp` and `holdout` reevaluate the nearest recognised site within 100 m using
normal state APIs; **unconditional forced tiers/visits/raids are skipped**. Real
criteria, cache/body availability, clocks, locks and warnings remain authoritative.
An `ok` camp evaluation does not imply its tier or visitor state changed.
`day` persists the escalation epoch through its normal verified store; it does
not age camps, advance scene deadlines, supply missing bodies or prove real days.

`status` returns one compact server-logged line per registered module (up to 64).
Enabled means core requested OnStart, not engine acceptance. Infected, events,
camps, holdouts, scenes, escalation and admin tools expose bounded counts/caps;
other modules explicitly report `active=n/a budget=n/a` until their owners expose
metrics. No IsEnabled call is repeated, since some modules load config there.

Request snapshot collects the same registered W5 contributors, one per core tick,
and delivers once to that admin. EnableDebugSnapshot must also be on for those
contributors. No snapshot file is polled or read by the client. The payload has at
most 512 total point/route vertices across 16 layers; whole routes are retained
or dropped. Truncation counts are logged. Select a layer and Toggle selected layer;
pins and route polylines follow it. The map supports native pan/zoom. Capture is
staggered, not simultaneous; it expires after 60 seconds and never auto-refreshes.
Labels/detail come from the shared snapshot. Candidate/abstract pins never mean
live bodies. Missing camps/scenes/pickers layers still require their owners'
contributors; see existing docs/DEBUG_MAP.md. Authenticated UI also expires after
60 seconds without a reply; press Pause to reauthenticate. No snapshot is sent
to non-admins, even if they manually send the RPC.

Suggested 30–45 minute rehearsal: 0–5 min join, authenticate, status/snapshot;
5–12 min sitter/real noise/kill and native horde attempt on open ground;
12–25 min walk to a reachable reviewed event/scene and exercise O/search/repair;
25–35 min inspect a real camp/holdout and day-cap status; 35–45 min record finite
balances, restore the original escalation day, restart and compare. Use the row
column below to select nearby work. Refused/unreachable/long-duration rows remain
BLOCKED or DEFERRED. End overlap normally. The connected client can complete the applicable in-game rows.

Spec/plan/tasks trace (Banso worker scope): requested specification files are
absent in this checkout; the supplied W6 task and runtime contract define the
specification. Plan: inspect shared/native APIs → RED synthetic sender smoke →
server authentication/queue/adapters → client menu/snapshot → GREEN affected
checks → lead's native compile/session. Source tasks for authentication, command
transport, gated director adapters, snapshot map and row mapping are implemented;
COT auth, fresh dormant creation, unconditional forced world transitions and
missing per-module metrics/contributors remain explicit gaps. Registration and
all native/runtime acceptance remain pending. No additional Python tool or
translator changes were added; the single smoke extends test_map_layers.py.

## 1. Join, record a baseline and check controls

| Row | README feature | One-client action and exact confirmation | Remaining native scope | Admin driver (Pause menu) |
| --- | --- | --- | --- | --- |
| A01 | Signed package, join, persistence | Join the signed server without a signature kick. Record `[HollowCountry] Server initialized` and `[HollowCountry][SelfTest] Core settings PASS`. Stop on `Core native self-test FAILED; no modules started`. | Native Windows compile, signed load and join pending. | `status`; record startup/admission separately |
| A02 | Extended stamina | With identical load/route, time sprint depletion and recovery versus a vanilla profile: intended drain 25%, recovery 250%; jumps/melee retain normal costs. First creation logs `Created enabled stamina profile: 25% continuous drain, 250% recovery`; `Stamina blocked` is a refusal. | Check prediction, delivery and reconnect on the connected client. | `status`; manual timed route |
| A03 | Stamina and weight bars | Add/remove heavy items; wet/dry equipment. See separate responsive bars and reduced endurance with load. Inventory remains server authoritative. | Check received state and prediction while changing load. | `status`; manual load/wetness change |
| A04 | Groups | M → create, rename, leave, create again. Confirm returned changes; `[HC Groups]` messages containing `service inactive` / `start refused` mean blocked. Absence of errors alone is no pass. | Check solo membership persistence and privacy after leaving/reconnecting. | `status`; M group workflow |
| A05 | Interactive map, shared markers/notes and icons | M → pan/zoom, create/edit/save a marker with a note, close/reopen, delete. Confirm coordinates/text and deletion. | Check own icons, saved marker/note edits and deletion after reconnect. | `snapshot` for admin layers; M for survivor markers |
| A06 | Useful information layers | Toggle Events, Visited, Team, Markers, Grid. Visit a named place; compare known O-menu events to pins. Carry then remove powered GPS; coordinates follow GPS access. No unknown player/event information. | Check only entitled information is displayed; unselected layers remain deferred. | `snapshot` + select layer / Toggle; M remains discovery-limited |
| A07 | Optional events | O → Refresh, Join, Leave, Close at a reviewed reachable site; confirm mission/objective and finite reward in the world. `[HC Events] enabled preference, no active missions` is empty state; `[HC Events] bind failed;` is not acceptance. Passing by remains allowed. | Check reachable sites and finite physical stock; no extra rewards or quest prompts. | `event`, then O Refresh/Join/Leave |

## 2. Search town, repair and salvage, then leave a noisy encounter

| Row | README feature | One-client action and exact confirmation | Remaining native scope | Admin driver (Pause menu) |
| --- | --- | --- | --- | --- |
| B01 | More places worth checking | Visit accessible houses, apartments and military accommodation; inspect floor/storage opportunities over repeated visits. Record coverage gaps. A single empty building does not prove broken loot. Compare the #12 CSV below. | Native CE eligibility, accessibility and geometry require observation. | `snapshot` for navigation; manual house search |
| B02 | Coherent loot, variety and soft progression | Compare civilian/industrial/medical/military finds for plausible supplies and risk progression while essentials retain multiple routes. Compare configured warnings with actual finds; never raise loot for a pass. | Spawn tags do not prove availability or balance. | `status`; manual loot comparison |
| B03 | Varied familiar houses | Compare layouts/histories in supported houses; walk stairs, every door and escape route. Context: `[HC Interiors] templates provisional; native clearance/path/audio/replication acceptance pending;`. A queued placement does not prove fit. | Inspect furniture visibility, clearance and occlusion; unmeasured layouts remain open. | `snapshot` for navigation; manual fit/door survey |
| B04 | Visible and searchable finds | Search supported cupboards/wardrobes/storage; time, interrupt, retry and inspect inventory/world items. Every obtained item debits the shared finite supply. | Interrupt, retry and reconnect; verify finite inventory custody. | `status`; manual finite search |
| B05 | A place remembers | Record depleted stock, layout and visible identities; revisit after travel and section 5 restart. No free refill/reroll or duplicated visible/search loot. | Check withdrawal/reconnect/restart conservation. | `status` before/after revisit and restart |
| B06 | Repair, reuse, disassembly, salvage | Exercise registered netting, cable/barbed-bat wire, leather, bat/stick, nailed-bat/ruined-crate wood/nail recoveries and cloth/rope/camouflage/repair/storage families where registered. Check tools, time, wear, input loss and finite output; unregistered candidates stay deferred. | Check inputs, outputs and interrupted completion; broader justified coverage remains open. | `status`; manually obtain inputs and craft |
| B07 | Fuel siphoning | With supported car, equipment/container, transfer finite fuel; interrupt, test nearly-full container and empty tank. Measure equal source loss/destination gain within precision; wrecks are not infinite petrol. | Check finite transfer, received state and restart interruption; unsupported hosts stay blocked. | `status`; manual supported fuel transfer |
| B08 | Improvised light mounts | `Tape light to weapon` on a native weapon-light slot; fit railed handguard if required. Confirm consumed tape, preserved light/battery and correct beam. Remove by hand, remount with new tape. | Inspect attachment, beam and sound; unsupported pairs remain refused. | `status`; manual taped-light action |
| B09 | Infected roles and trade-offs | Compare admitted appearances, sensible locations and broadly native health/damage. Context: `[HC Infected] capability admission`. Config entries alone do not prove visible variants. | Observe perception and appearance; unsupported role/stance maps stay native. | `sitter` at open flat ground; `dormant` explicitly refused (fresh-spawn policy absent) |
| B10 | Sight, sound, clues, investigation, local alerts | Break sight, make a real sound, move away. Observe clue investigation, bounded relays and escape without hidden live-position pursuit. Record admission reasons and `[HC Infected] native release status:` if emitted. | Observe cover, gunshot and relay audibility from successive positions; no hidden pursuit or unlimited alerts. | `horde`, then genuine sound/sight and escape; no synthetic alert |
| B11 | Coherent groups, persistent hordes | Observe natural movement/contact loss; record `[HollowCountry] infected horde budget used=` and quarantine/refusal. Repeat after restart with recorded membership where identity is available. | Check sight vetoes, hidden activation and corpse/roster consistency. | `horde` + `status` + `snapshot`; native adoption gates apply |
| B12 | Rooms, doors, injuries, crawling | Observe native traversal and door interactions; inflict leg injury and record supported crawl/limp. Doors/stairs stay usable, no repositioning or silent movement correction. | Check doors, crawl state and room visibility; unsupported behavior remains a gap. | `sitter`; manual traversal/injury; no forced crawl |
| B13 | Footsteps, shuffle, contact, warnings | Listen across surfaces, distance and cover, including stealthier variants. Record missing/unfair warnings with time/position. | Listen from successive positions across surfaces and cover. | `sitter` / `horde`; manual sound |
| B14 | Death reactions | Kill infected; inspect native reaction and corpse access/loot. `Infected deaths not admitted; runtime acceptance PENDING` means blocked. | Inspect corpse/animation consistency; full ragdoll remains an engine limitation. | `sitter`; manual kill/corpse inspection |

## 3. Travel through the Living Country

| Row | README feature | One-client action and exact confirmation | Remaining native scope | Admin driver (Pause menu) |
| --- | --- | --- | --- | --- |
| C01 | Hollow grade | Cycle bound control through 0–100% in 10% steps; 0 restores vanilla. Inspect persistence/stacking with native effects. Startup: `V2 admission feature=Grade`. | Rendered result and frame cost need observation. | `status`; normal grade control |
| C02 | Weather, lighting, changing days | Observe dusk/overcast/storm and readable bright night. Record `[HollowCountry] V2 weather day=` profile and atmosphere ownership/refusal. | Inspect visibility over real days and seasonal variation. | `day 0/7/14/30` changes escalation only; observe weather naturally |
| C03 | Ambient life | Visit water/farms; observe loaded small animals without duplicates. `[HollowCountry] V2 optional pack AmbientAnimals loaded=` confirms dependency presence only. | Observe animal visibility/audio and native population/resource behavior. | `snapshot` for navigation; manual animal observation |
| C04 | Signs of life | Observe lit windows, chimney smoke and carcass flies where supported. Compare `[HollowCountry] V2 signs of life day=` counts with actual effects. | Observe effects/audio and record client cost. | `holdout` + `snapshot`; manual effect observation |
| C05 | Trail shelters and group pins | Visit shelter; inspect passable props/entrances and map pin/lead slot. Record `[HollowCountry] V2 shelter placed name=` or `V2 shelter refused name=` and reason. | Inspect shelter and received pins/leads; refused sites remain gaps. | `snapshot` shelters layer; walk to site |
| C06 | Motorbikes, boats, common repairable cars | Find overlay vehicles; inspect missing parts, repair and ride/drive supported examples. Check oil/brake-fluid/parts against installed CE. | Check physics, seats, repairs and retained ownership; no scripted oil/brake effects are implied. | `snapshot` for navigation; manual repair/drive |
| C07 | Finite wreck salvage | Salvage supported wreck to exhaustion and retry. Compare `V2 wreck salvaged class=` and `V2 wreck salvage wrecks=` balances after restart. | Check conservation over repeat use and restart; unsupported wrecks grant nothing. | `status`; manual finite wreck salvage |
| C08 | Factions and hold-outs | Inspect supported houses/faction traces; kill/loot a materialized survivor and real cache. Record `V2 holdouts ready` then `V2 holdout raided id=`. Abstract/empty state is not a body. | Inspect body/cache stock and revisit after seven real days, including downtime. | `holdout` + `snapshot` holdouts layer; normal cache/body gates |
| C09 | Pickers | Compare finite stock before/after a legitimate visit; record `V2 picker visit phase=` and daily usage. `abstract=1` does not prove visible scavengers. | Check finite transfers; abstract state does not prove visible actors. | `status`; manual legitimate stock comparison |
| C10 | Dead drops | Follow a known lead; inspect finite contents, empty and revisit. Compare `V2 dead drop deposit id=` / `used=`; no free repeat/restart supply. | Empty and revisit the same finite drop. | `snapshot` dead_drops layer; manual finite withdrawal |
| C11 | Powered radio and faction chatter | Tune powered PersonalRadio to `V2 radio ready frequencies=` channel; confirm chatter, remove power/change channel. Match `V2 radio line freq=`. | Check channel/power exclusions, received audio and reconnect. | `status`; manual powered radio/channel test |
| C12 | Morse clues | Tune travellers channel; compare received clue to redacted `V2 morse clue player=` grid/target. Test power/channel/rate limits. | Check channel/power exclusions, delivery and rate limits. | `status`; manual travellers-channel test |
| C13 | Rumours, notes, body stories, shared leads | Follow received lead, inspect body story/rare note; record `V2 lead received source=`, `V2 body stories placed=`, `V2 notes world=`. At most one note/scene, ten worldwide. | Check received leads and finite notes/body stock; missing random selection alone is not failure. | `scene` + `snapshot` leads/events; follow legitimately delivered leads |
| C14 | Scenes and chains | Reach advertised last-stand/quarantine/evacuation site; inspect stage and follow clue or allow expiry. Match `V2 scene placed id=`, `V2 scene stage complete id=`, `V2 scenes active=`. | Inspect physical props, clues, expiry and cleanup at reviewed sites. | `scene` + `snapshot` events; reviewed due site and observer gates |

## 4. Make camp, revisit the world and inspect optional AI

| Row | README feature | One-client action and exact confirmation | Remaining native scope | Admin driver (Pause menu) |
| --- | --- | --- | --- | --- |
| D01 | Camp recognition, three tiers | Build around legitimate fire/shelter/storage; record `V2 camps recognised camp=` then `V2 camps tier camp=` when actual criteria are met. | Check ownership persistence; higher tiers need later play if criteria are unmet. | `camp`; reevaluates real criteria, preserves age/cooldown |
| D02 | Visitors, neighbours; mailbox retired | Inspect supported visitors; compare `V2 camps visitor camp=`, `V2 camps neighbours-lost camp=` and startup `mailbox=off`. Written notes in native storage receive no mailbox answer or conversation (HC-17 / #151). `abstract=1` is partial visitor state. | Observe visitors and long-term neighbour loss; check retired mailbox stays inactive. | `camp`; normal visitor eligibility only |
| D03 | Theft, safe locked storage | Compare unlocked/locked storage. `V2 camps theft camp=` requires a real finite transfer at an unattended camp; attended/locked storage stays protected. | Check attended refusal, then leave and return to inspect finite stock and custody logs. | `camp`; attended/locked protection retained |
| D04 | Warned day-14 tier-3 probes | At legitimate age/tier, record `V2 camps probe-warning camp=` before supported raid, then signs/retreat. `abstract=1` is not an armed raid. | Observe warning/raid results over real camp age; no altered-clock proof. | `day 14` + `camp`; escalation changes, real camp age/warnings remain mandatory |
| D05 | Capped escalation | Record `V2 escalation day=` multipliers through legitimate progression; confirm caps rather than unlimited growth. | Real-day balance and target-load scaling pending. | `day 0/7/14/30/3650` + `status`; admin exercise only, not real-day balance proof |
| D06 | Settlement decay | Revisit settlement; compare supported appearance/state to `V2 settlement decay towns=` / `V2 settlement visual refused town=`. | Inspect visible decay; refused materialization is not a visible result. | `day 14/30` + `status`; normal settlement gates |
| D07 | Infected memory, horde migration | Revisit active route; compare `V2 infected memory cells=`, `V2 herd drift id=`, `V2 herd drift members=` with finite native movement. | Check perception and hidden transitions, then revisit for long-term memory. | `horde` + `snapshot` infected layer; genuine cues only |
| D08 | Finite loot refresh | After configured cooldown revisit depleted house; refresh follows finite source/ledger, including restart, without duplicate visible/search supplies. | Check finite refresh, withdrawal and restart conservation. | `status`; manual cooldown/restart revisit |
| D09 | Ecology, resources, migration | Observe bounded cohort around resources. Record `[HC Ecology] observation_path=available`, `coverage=partial`; `feeding=unsupported`, `drinking=unsupported`, `migration=unsupported` are gaps. | No inspected feeding/wildlife-destination transaction means unsupported, not working ecology. | `snapshot` for navigation; unsupported ecology paths remain blocked |
| D10 | More firearms | Find/load/fire representative curated wood-stock, conventional modern and finished vanilla additions with proper ammo/magazines; inspect installed CE scarcity. Loaded subscriptions do not prove weapon function. | Inspect native weapons, attachments and audio; unsupported variants remain excluded. | `status`; manually find/fire weapons; no inventory injection |
| D11 | Optional Expansion patrols/checkpoints/faction stance | With optional dependencies, visit admitted reviewed site, observe stance and physical gestures. Confirm finite ammo/normal damage/fair movement. Match `[HC Expansion AI] sites admitted:`, `site ... spawn refused:` or `[HollowCountry] Checkpoints refused:`. | Observe combat, permissions and cleanup; no forced recovery teleport. | `snapshot` materializer_candidates/holdouts; candidate is not a live AI body |
| D12 | AI encounters from remembered events | Follow known event; compare `[HC Expansion AI] encounter bound:` to legitimate site patrol/result. No hidden live-position knowledge. | Observe encounters driven by known events; missing provider paths stay explicit. | `event` + O; normal optional AI provider/budget gates |
| D13 | Existing DayZ mechanics | Check supported cold/wet-weight, weapon obstruction and directional-hit settings while surviving; record concrete symptoms. This README direction is a native-system audit. | No promise of base-building expansion, futuristic gear, new renderer or unrestricted wildlife simulation. | `status`; manual native-system audit |

HC-17 / #151 round-3 source review: building claims count persisted online
`AbsentSeconds`, replacing the round-2 boot grace. No new distances: 25 m visit
radius and native action reach remain. Runtime acceptance pending. After
DayZDiag and normal PBO/server boots, grep
`[HC Plan] HC-17 expiry=online_absence window_days=`. Record absence before and
after regular stop/restart, verify visits reset it, 40 days of downtime do not
count, and accumulated online absence expires metadata across regular restarts.
Keep native container/item identities through expiry. Legacy rows without the
new field must load as 0; negative/over-policy counters must refuse. Observe
camp-level refusal after a camp fault and a successful Fail -> OnStart without
OnStop. With one client check distinct server-sent contention, changed-group,
persistence-fault and service-unavailable messages. Native lockpick/door restart
and heavy-infected vulnerability remain pending; no offline result accepts them.
See LOCAL_ACCEPTANCE_V1.md, HC-17 round 3, for spec/plan/task trace and actual
RED/GREEN records. Target-load budgets remain provisional for 3–6 players.

## 5. Restart and record the session — #12, #50, #70

Record inventory, house depletion/layout, markers/notes, camp tier, cache/wreck
balances. Log out, stop normally, restart same build/profile and rejoin. Compare
all recorded state; do not erase persistence to fix it. Check one new startup
admission per enabled V2 module, retaining explicit disables. Roll back against the
stopped private installation using existing instructions. Normal restart is only
one persistence case, not crash-recovery qualification.

Extract the two **server** files; keep outputs outside the repository:

```sh
python3 -B tools/testing/log_metrics.py --script-log /private/run/script.log --rpt /private/run/server.RPT > /private/run/log-metrics.json
python3 -B tools/testing/right_size.py /private/run/log-metrics.json --infected-cap 100 --animal-cap 40 > /private/run/cap-proposal.json
python3 -B tools/audit/loot_routes.py --mission /private/staged/dayzOffline.chernarusplus --overlay mission/hollow-country/ce/types.xml > /private/run/loot-route-gaps.csv
```

Caps **100/40 are placeholders**, not recommendations: supply current operator
caps. Omit either cap to hold it. Tools print only, never edit CE or raise loot.
All proposals are provisional; keep originals and repeat identical load before a
manual change. A one-client run cannot qualify or right-size the target load.

`log_metrics` JSON schema 1 includes `fps_samples`, `perf_windows`,
`module_max_ms`, `entity_samples`, `errors`, `admissions`, `feature_summaries` and
source labels/line/time references. It reuses the existing actual `[HC Perf]
window=` / `mod_max=Name:ms,...` parser, preserving other `[HollowCountry]` and
`[HC ...]` diagnostics. Third-party `TWO ANIMATION MODS` lines are filtered before
error counting. `SCRIPT (E)` and VM exception totals count matching lines per input,
not unique incidents; an incident may appear in both files. Steam/account IDs and
home-path tails are redacted; input paths and exception text are never printed.
Keep raw logs private. Files are capped at 256 MiB, lines at 65,536 characters;
invalid input exits 2. Each sample list holds 10,000 rows (admissions 1,024,
feature lines 512); overflow sets `truncated=true`, blocking sizing. Feature text
is capped at 2,000 characters. Split long sessions into matched time segments.

Only explicit server-FPS labels in the script log, or FPS monitor labels in the
**server RPT**, count as FPS. HC tick cadence (usually 1,000 ms) is not server frame
time. `entity_samples.scope=feature` may describe local counts/budgets rather than
a world census; sizing uses only `scope=monitor` RPT counts. `AI:` alone never
means eight human bodies. Missing telemetry stays missing, never synthesized.

`right_size` is a separate capacity-research tool requiring ten FPS samples, each carrying 3–6 players, and calibrated
HC windows whose complete player range is 3–6. This tool is outside acceptance; do not assemble extra clients to complete this checklist. Malformed/truncated evidence holds
caps. If adequate, FPS p10 below 20 or HC work p95 above 5 ms suggests a **trial
reduction of at most 10%** (integer floor) for a supplied cap whose nonzero
population was actually reported. Missing population/cap means zero delta.
Otherwise it holds. Thresholds are unmeasured heuristics; errors still require
investigation and reductions do not qualify a build.

The #12 CSV lists configured essential classes with fewer than two distinct usage
routes. Defaults explicitly cover water/food, medicine, cutting/fire tools, rope
and repairs; repeated `--essential ClassName` replaces this list. It reads
`db/types.xml`, declared CE `type="types"` files, and repeated explicit candidate
`--overlay types.xml` files. Use a complete staged mission to include generated
overlays; unrelated XML/uninstalled dependency content is not auto-discovered.
No `metrics/` artifact is created. Positive nominal, category, usage and no
crafted/deloot flag indicate **configured candidates**, not verified spawns.
Categories label usages without multiplying routes. Conflicting definitions use
only common usages and are flagged, without assuming native CE override order.
Missing/zero-nominal types have zero routes. Class availability, CE vocabulary,
dispatch/point eligibility, geometry/accessibility and non-CE acquisition
(crafting/foraging/hunting/water pumps) need separate review. Each CSV row says
`configured_only_runtime_pending`.

## 6. Combined-load scenario — #78 / EXP-P2

This procedure is **unexecuted**. Use one server and at most one client. Record
the actual load; 3–6-player capacity remains unmeasured and is not an acceptance requirement. Keep build, mission, weather,
location, settings and duration comparable between baseline and loaded runs.

1. Record ten minutes of baseline ordinary play with existing HC sampler enabled.
   Retain startup and calibrated windows. Use the server's supported monitoring
   to log FPS, players and infected/animal counts. Missing telemetry is a gap;
   never derive FPS from HC tick cadence.
2. Via the existing optional AI director and reviewed reachable sites, reach
   **eight live human AI bodies total**, including hold-outs/visitors/transient
   encounters sharing the global budget. Stay inside **8-body / 2-site**
   admissions and `HCWorldLimits`; no extra patrol alongside eight reservations.
   Missing provider/site admission means BLOCKED; no debug spawn/direct engine
   calls or dependency edits.
3. Bring **two legitimate hordes** into the same measurement interval through
   ordinary travel and actual observed stimuli, retaining horde/member caps.
   Record rosters/states and timestamped `[HollowCountry] infected horde budget used=`
   lines. Reservations/abstract populations are not live actors: confirm movement
   without teleports, duplicate population or forced in-view activation.
4. Hold overlap for ten minutes while searching town, opening doors, fighting,
   moving between sites and using M/O/radio. Record actual eight-body/two-horde
   overlap start/end, players, counts and cap/refusal messages. Lost actors/hordes
   shorten the valid interval. If normal admissions cannot safely reach the
   combination, mark BLOCKED; do not loosen budgets to fake it.
5. Extract matched baseline and overlap files separately:

   ```sh
   python3 -B tools/testing/log_metrics.py --script-log /private/combined-load/script.log --rpt /private/combined-load/server.RPT > /private/combined-load/log-metrics.json
   python3 -B tools/testing/right_size.py /private/combined-load/log-metrics.json --infected-cap 100 --animal-cap 40
   python3 -B -m tools.testing.perf_capture /private/combined-load/server.RPT
   ```

   Substitute real caps. Compare FPS, calibrated module maxima, HC work, population
   and errors with baseline. Keep raw evidence private; attach redacted extraction
   and overlap notes to #78 / EXP-P2. Proposals are printed only; no acceptance is
   recorded here.
6. End encounter normally, leave/rejoin, restart and inspect cleanup/finite stores.
   Check observer cleanup, ownership, AI/horde visibility and combat audio from
   the connected client; record only observed outcomes. Missing live
   body/site totals or FPS/population logging needs owning-worker telemetry;
   these offline tools add no runtime hook.

## W5 trace and remaining work

| Finding | Deliverable | Outcome |
| --- | --- | --- |
| #12 | `tools/audit/loot_routes.py`: staged mission/overlay CSV | Fixed offline reporting; runtime acquisition pending. |
| #50 | `tools/testing/log_metrics.py` and this README itinerary | Fixed tooling/docs; runtime rows pending native server and single-client observations. |
| #70 | `tools/testing/right_size.py`: printed conservative delta | Fixed proposal tooling; budgets provisional until measured at target load. |
| #78 | Section 6: eight human AI bodies plus two hordes, capture commands | Fixed procedure; execution/EXP-P2 acceptance pending. |

Requested `docs/SPECIFICATION.md` and
`docs/specs/001-survival-overhaul/spec.md` are absent from this worker checkout;
no spec/plan/task files are available here to update. The W6 source work is
tracked above. For the W5 tooling below, supplied task and
`RUNTIME_IMPLEMENTATION_CONTRACT.md` define scope. Plan: inspect native producers →
RED one synthetic CLI smoke → three read-only tools → GREEN → affected existing
suites → lead's native compile/session. The sole added smoke extends
`tests/unit/test_perf_capture.py`, covering redaction, calibrated timing,
reduction/solo hold and conflicting loot routes. The W5 reporting tools themselves require no runtime hook; W6 admin source
requires the single module registration described above.
