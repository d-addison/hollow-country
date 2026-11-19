# Outstanding work

Source snapshot: 2026-11-19, through `c37d3598`. The [README](../README.md)
describes the implemented product and operator controls. Here, **built** means
source/data landed; it does not mean the current combined build compiled,
booted or passed gameplay acceptance. Nothing has a DayZ gameplay verdict yet.
Older boot records establish only the exact compilation/startup observations
recorded for those builds.

Features default on with named settings or acceptance-file opt-outs. Gates
waiting only for runtime verdicts admit unverified through `HCV2Admission`.
Missing providers, data, surveys and assets remain real gaps. Readiness derives
from `HCGetOperationalStatus` / `HCOperationalStatus.HCPublish`, independently
of runtime acceptance. All budgets remain provisional for **3–6 players**.

## Landed since the previous README

The 97 commits after `60cb491a` include these changes; all are *In-game test pending*
or *Needs a two-player test* as marked in the README.

| Area | Implemented change | Remaining work |
| :--- | :--- | :--- |
| Dependency stack | Expansion-Licensed and Expansion-Vehicles are active between Core and AI; the manifest defines server/client order. | Matching packaged server/client loading. |
| Wearable lights, HC-23/52 | Exact helmet/pack slots, mount/remove/toggle actions, durable per-pair opt-outs and shared-adapter status; cross-slot weapon pairs remain admitted unverified. | Native slot/beam geometry, custody, restart and two-player replication; unsupported pairs remain refused ([#58](https://github.com/d-addison/hollow-country/issues/58)). |
| Infected, HC-14/45/46/47 | Standing idle bodies, bounded variety-group corridor movement, budget-independent safety release and rotating candidate selection. Authored sitter/rise selection uses `PosedFreshEvery=3`; `MaxPosed=12`, range 0–64, 0 off. | Flat sleeper, lying-riser and kneeling-feed clips/graph states ([#121](https://github.com/d-addison/hollow-country/issues/121)); native route/pose/door/reach observations ([#213](https://github.com/d-addison/hollow-country/issues/213)). |
| Shelters, HC-59 | Five regional exterior scenes at stock roof anchors, access keepouts, observer retry/rollback and complete-only discovery; packaged with a dedicated budget consumer. | Native access, collision, rain cover and two-player visibility ([#200](https://github.com/d-addison/hollow-country/issues/200)). |
| Search and pickers, HC-34/54 | Shared finite player/AI house reservations, separate compaction budget and owning-picker refresh preparation. Need-driven 2–6 member runs consider seasonal need, remembered danger and combat abort. Up to three physical house goods return to the camp crate through durable custody; full crates retain goods on carriers and bodies. | Normal server inventory/depletion, death, full-crate, combat, interruption and paired Hive/journal restart checks ([#144](https://github.com/d-addison/hollow-country/issues/144), [#224](https://github.com/d-addison/hollow-country/issues/224)). |
| AI activity and kits, HC-43 | Role scheduling, formations, movement styles, real-item smoke/lures and real-part car repair; five archetypes for each of five role kits. Fresh group replacement preserves corpses and finite inventory, with configurable short timers and operator-default adoption. | Native selection, walking, parts, quantities, wear, body access and replication. Role-specific raid dispatch remains a missing public offer port ([#146](https://github.com/d-addison/hollow-country/issues/146)). |
| Camps, claims and raids, HC-16/17 | Claim-only bases with physical cargo become encounter targets after 14 held days; independent durable cooldowns, admin targeting and live attendance rechecks. Adapter guard coverage landed. | Warned visits/raids, native doors, theft custody and two-player attendance ([#211](https://github.com/d-addison/hollow-country/issues/211), [#212](https://github.com/d-addison/hollow-country/issues/212)). |
| Situations, HC-38/39/40 | Wreck-pinned survivors, leased-party smoke retry, dead-party completion and a borrowed-world-car convoy branch. Foreign drivers retain control; the whole crew must dismount before walking resumes. | Road driving, seats, timeout/release, interrupted leases and normal PBO/two-client acceptance ([#210](https://github.com/d-addison/hollow-country/issues/210)). |
| Native incidents, HC-41 | Event owner opens, ticks and closes the native lease; registered live crashes support direct cargo ancestry. Caps and summaries derive from registered policy and operational status. | Loose CE crash loot has no engine incident-membership API ([#147](https://github.com/d-addison/hollow-country/issues/147)); no loose-stock attribution is invented. |
| Perceived incidents | Source-owned gas, crash, gunfire, smoke, scene, raid and horde receipts feed bounded AI response leases with actual member perception and LOS checks. Spawn rings include bounded coastal land selection. | Native perception, gas-route safety and two-player visibility/sound; no AI radio receiver or airdrop observer is implemented ([#147](https://github.com/d-addison/hollow-country/issues/147)). |
| Wildlife, HC-15/48/49 | Seasonal territory records, blood-damage/carcass clues and bounded contact receipts; independent finite carcass/contact providers. Observation and goals publish separate readiness; world-incidents opt-out reports clues unavailable. | Safe animal destination, target and feeding ports are absent; requested goals are admitted unverified. Attraction/crows and actual goal execution remain missing ([#149](https://github.com/d-addison/hollow-country/issues/149)). |
| Seasons, HC-50/51 | Read-only authoritative phase, configurable weather/presentation and default-on bounded client autumn falling leaves. | White terrain has no supported live surface provider; native seasonal presentation and two-player leaves remain pending ([#150](https://github.com/d-addison/hollow-country/issues/150)). |
| Hearths | Smoke/firelight observes real burning fireplaces; hidden funded holdouts transfer actual fuel and consume matches. Expired attempt reclamation is fair under budget pressure. | Native fuel consumption, smoke/glow, lifecycle and two-player sight. |
| Crafting, HC-22/30 | Four leather-glove supply routes and water ledger decisions resolved; finite tailoring produces all four colours of leather pants/vests from panels and sewing-kit quantity. | Native recipe registration, conditions, capacity and failure/recovery ([#229](https://github.com/d-addison/hollow-country/issues/229)). |
| Floor loot, HC-55 | Default-on clothing/listed-clutter floor policy retains points, moves compatible displaced demand to shelves and reports unplaced capacity; geometry and group bounds remain unchanged. | Native CE eligibility, density and cost ([#179](https://github.com/d-addison/hollow-country/issues/179), [#199](https://github.com/d-addison/hollow-country/issues/199)). |
| Administration, HC-25 | COT `HollowCountry.Admin` binding with live grant/revoke checks and private allowlist fallback; bounded admin-only destination catalogue; exact snapshot omission counts. | Joined-client access, revocation/recovery, snapshot secrecy and landing safety ([#203](https://github.com/d-addison/hollow-country/issues/203)). |
| Packaging and diagnostics | Reviewable unsigned inventory-overlay replacement, corrected exported XML headers, OS-held hash-cache merge locks, bounded interior startup and incremental debug encoding. | Windows locking/installer recovery and native timings ([#197](https://github.com/d-addison/hollow-country/issues/197), [#222](https://github.com/d-addison/hollow-country/issues/222)). |

## Remaining source, data and asset gaps

- **Interior coverage, HC-24/31/53/56/57:** the coverage tool reports stock,
  placed and qualifying measured classes, census rejection reasons and remaining
  sampler runs. Available census inputs do not satisfy the door-phase/native-run
  contract; no measurement is fabricated. Wider room/prop geometry, door census,
  cellar stairs and office coverage remain open; unqualified interiors stay
  vanilla ([#199](https://github.com/d-addison/hollow-country/issues/199)).
- **Native limits:** no infected ragdoll API, supported animal goal/feeding port,
  live winter terrain provider or loose CE incident-membership API was found.
  Infected window/crawl gaps, deep water and pillar turn limits remain engine
  constraints; see [the reach audit](INFECTED_CHEESE_AUDIT.md).
- **AI integration:** role-specific raid offers need a public group-specific
  sense/warn/offer port; player interaction remains physical observation,
  ambush and raiding. There are no player trades, dialogue, quests, rewards or
  hidden AI knowledge. AI radio learning, airdrop observation and autonomous
  helicopter overflight lack ports. Existing caravan/barter and faction outcome
  code is built; wider funded pair data and acceptance remain open
  ([#145](https://github.com/d-addison/hollow-country/issues/145),
  [#146](https://github.com/d-addison/hollow-country/issues/146)).
- **Content, HC-60/61:** additional variant dependencies remain a research
  shortlist. Optics selection and the deferred optics subset remain open; verify
  event-only/new firearm classes and family budgets on the server. The supplier
  ledger now has decisions rather than unresolved leather/water rows.
- **Later:** item, food and clothing variety mods are
  [on hold (#232)](https://github.com/d-addison/hollow-country/issues/232).
- **Traceability, HC-11/62/63/64:** exact-source package, documentation and
  runtime acceptance records still need reconciliation for the combined build;
  missing experiments must never be marked accepted. The
  [runtime contract](RUNTIME_IMPLEMENTATION_CONTRACT.md),
  [module status](MODULE_STATUS.md) and older acceptance documents contain
  historical wording; current feature defaults are in the README.

## Runtime acceptance

Run DayZDiag and normal signed PBO/server checks for the combined build. No
current feature is *Tested locally* in the gameplay sense. Source checks,
synthetic fixtures and older successful boots do not establish current gameplay.

- **Inventory and persistence:** finite house search, picker carried goods,
  full/refused camp crates, body looting, interrupted custody and restart;
  claims, camps, forage, stories and incident allocation recovery. Back up Hive
  and all HC journals together. Verify temporary/backup/empty pending files;
  native verified-copy stores do not provide atomic rename or fsync.
- **AI:** kit loading, slot compatibility, smoke/lure stock, real-part repairs,
  convoy seats/driving/dismount, native route restoration and finite respawns.
  Exercise self-defence, rescue shots, near misses and grudge expiry
  ([#139](https://github.com/d-addison/hollow-country/issues/139)).
- **Infected:** pose/rise/wake, corpse access, horde materialisation/folding,
  appearance substitutions, idle/simulation behaviour, reach and door pressure
  ([#135](https://github.com/d-addison/hollow-country/issues/135),
  [#136](https://github.com/d-addison/hollow-country/issues/136)). Historical
  `ECE_INITAI` creation crashes, CE startup timeouts and missing infected periodic
  journals still require native follow-up; see [module status](MODULE_STATUS.md).
- **Two players:** sight-safe world changes, infected perception/audio, gunfire,
  smoke/light/leaf visibility, native door state, wearable beams, group membership,
  markers/pings/death pins, reconnect and late join, radio/mailbox privacy,
  camp attendance/theft/raids, bicycles, shelters, scenes and wildlife clues.
- **Administration:** Pause access, COT live grant/revoke and unavailable service,
  allowlist recovery, all kit commands, destination safety, Map tab Run/ack,
  running-query refusal, retained loot marks and bounded snapshot notices.
- **Economy and installer:** floor/shelf tags, compatible capacity, glove/water
  supply, weapon/ammo families and event-only classes, overlay rollback and
  signed inventory replacement on the server platform. Old cabinet-prompt reports
  ([#152](https://github.com/d-addison/hollow-country/issues/152)) need rechecking
  against the current six-second server-bound action, not the retired refusal.
- **Performance:** measure p50/p95/max with 3–6 players, including 8 AI and 2
  hordes, first building resolves, event preflight, startup pack parsing, snapshot
  encoding, loot-map queries and saves
  ([#138](https://github.com/d-addison/hollow-country/issues/138)). The 22
  independent consumers retain starvation allowances; `MaxTickWorkItems=32`
  permits up to 53 cost-one units, with heavier/measured charges beyond that.
  No frame-time guarantee or larger-server capacity is established.

Useful native log substrings:

```text
[HC TickWork]
[HC CostTotal]
[HC Cost]
[HC Plan] HC-41
feature=NativeIncidents
CE_CRASH_LOOSE_STOCK_ATTRIBUTION_PENDING
reason=CE_INSTANCE_MEMBERSHIP_API_UNEXPOSED
W2_OBSERVATION_AVAILABLE
AUDITWILD_MEMORY
AUDITWILD_GOALS_PENDING
feature=WildlifeGoals
W2_CLUE_DEPENDENCY
```

After activity, inspect `[HC Pickers] run goods=` for deposited/retained outcomes
and `[HC Admin] cmd=snapshot result=ok reason=delivered` after an authorised
snapshot request. `runtime=PENDING` and admitted-unverified status remain until
actual acceptance is recorded; an operational `ready` line does not replace it.

## Tooling and review debt

- Lint baseline: one reviewed HC-E006 entry, `findings=1 new=0 stale=0`
  ([#160](https://github.com/d-addison/hollow-country/issues/160)). Native-only
  compile traps still require a boot; offline heuristics are incomplete.
- The settings registry and consistency validator cover scoped owners. The
  [README settings tables](../README.md#server-settings-reference) list new
  registry rows and module-owned tuning; explicit opt-outs remain authoritative.
- Packaging hash-cache merges now use persistent OS-held locks rather than
  deleting presumed stale lock files. Stop older builds before switching lock
  protocols. Existing old-protocol behavioural assertions remain untouched under
  the owner's unit-test override; Windows contention is unverified.
- Historical wave review issues #191–#197 retain their native checks. Raw read
  caps, weapon receipt admission, trade-log recovery and snapshot notice fixes
  landed; no old refusal should be treated as evidence of the current code.
- The reported Expansion-Animations / Survivor Animations conflict remains
  unverified locally. Expansion-Animations stays outside the stack.
- Installer rollback and path comparison still need server-platform checks
  ([#163](https://github.com/d-addison/hollow-country/issues/163)).

## Owner decisions and deferred questions

Current decisions are 3–6 players, source/package work before client join,
default-on features with opt-outs, and no invented runtime evidence. Claim
expiry is implemented as 30 running-server days, renewed by member visits;
camp respawn is enabled. Older 14-day expiry and larger-load assumptions are
superseded.

Remaining choices: optics dependency; truck travel-overlay scope; wipe/story
pacing; whether to retire the autonomous-client validation spec; treatment of
the remaining cold/wet overlay; and whether perceived-gunfire caution should
change. An Expansion M249 crash still needs a sanitised class/version/stack
capture; any upstream public report requires separate authorisation. Private
source work does not authorise public or Workshop publication.
