# Remaining-work execution plan

Baseline: source `796175f`, passing CI run 43950077596. This plan supplements
the canonical 25-task roadmap; it does not replace requirements or loosen gates.
User instruction: execute remaining work before client connection. Private source
and development artifacts may progress independently; multiplayer acceptance waits
for actual clients. Every work item ends with source review and recorded evidence.

## Execution rules

For each implementation: read installed native declarations and call sites;
write a failing behavioral test; retain the actual RED output; implement; run the
focused GREEN suite; review failure/restart boundaries; integrate the full suite.
Source-contract tests identify wiring but never establish native behavior.
Record unsupported capabilities as explicit blockers rather than imitating them
with hidden tracking, teleport, unsafe spawning, or invented measurement data.
Keep all default feature flags false until native acceptance permits promotion.

## Wave 1: independent source and platform work

| ID | Roadmap | Deliverable | Dependencies | Done evidence |
| --- | --- | --- | --- | --- |
| C01 | T002–T004 | Reinspect native launch access; attempt bounded official smoke; inventory exact blocker if unavailable | Existing verified package | Native process/report or exact failed invocation; no client needed |
| C02 | T014–T015 | Finite shared search allocation and recovery; schema migration and orphan handling | Installed APIs, existing interior store | RED/GREEN allocation, interrupted claim, quota, identity and migration tests; no duplicate grants |
| C03 | T020–T022 | Bounded audible propagation and semantic investigation; conservative persistent membership recovery | Native emitter/group/navigation surfaces | TTL/hop/recipient/dedupe/ownership/restart behavior tests, native citations; no hidden coordinates |
| C04 | T025 | Verified portable install/upgrade/journal recovery/rollback utility | Existing ZIP/PBO verification | Real temp-filesystem roundtrip, interrupted stages, drift and unsafe path tests |
| C05 | T010–T012 | Coverage intervention preparation and reviewable measured-point import | Stock CE audit | Strict coordinate provenance and import validation; never invent real building measurements |
| C06 | T017, T023 | Review crafting failure boundaries and integrated module lifecycle | Existing installed recipe audit | Concrete defects fixed with regressions; state engine atomicity limits explicitly |

C02, C03 and C04 have disjoint worker scopes. The coordinator owns C01, C05,
C06, plan/tracking and integration. Workers may add focused tests and reports;
only the coordinator updates shared configuration, packaging and project status.

## Wave 2: integration and executable delivery

| ID | Roadmap | Deliverable | Dependencies | Done evidence |
| --- | --- | --- | --- | --- |
| C07 | T009, T023 | Bind new meaningful scenarios and integrate verification | C02–C06 | All unit tests and executable offline BDD, project integrity, spec/plan checks and independent review |
| C08 | T004, T025 | Rebuild versioned private development PBO/ZIP and verify source manifests | C07 | Deterministic package hashes, strict validation, no purchased assets or signing keys |
| C09 | T001, T023–T025 | Update READMEs, status, roadmap issues and evidence | C07–C08 | Source commit and CI links; missing implementation separated from unperformed engine tests |

## Wave 3: native engine validation without a player

Run in a fresh isolated copy; preserve stock installation and profiles.

1. Compile/load the normal PBO on pinned DayZ Server; capture all compiler and
   lifecycle logs and bounded shutdown. Correct concrete compiler errors first.
2. Run authored native self-tests in the appropriate diagnostic build and record
   build/tool/config/source hashes. A normal server does not prove diagnostic hooks.
3. Generate a private development signing key outside Git with official tools;
   sign and check the actual PBO; verify normal signature-enforced loading.
4. Exercise configuration rejection, repeated init/shutdown, state migration and
   save/restart on copied runtime state; preserve failed artifacts for recovery.
5. Inspect/map verified house anchors and CE point exports using official tools.
   Measure layout fit, door clearance, coverage and engine eligibility. Offline
   guessed coordinates cannot satisfy these steps.

Windows execution remains the acceptance target. Actual DayZ and official signing
tools can also run under Wine from an isolated Linux-filesystem copy; record that
environment explicitly and keep Windows/client gates pending. The coordinator
has reached successful Game, World and Mission compilation, core script-VM
self-test and mission initialization on integrated build018, whose matching PBO
also passed the separate official signature checker. Diagnostic execution,
signature-enforced client/server loading and feature-specific checks remain gates.

## Execution ledger — 2026-11-16

- C01: Bounded actual-engine access and compiler investigation implemented;
  native Windows interop still times out. Compile-010 passed enabled Crafting
  definitions/config and core VM checks; 011/012/015 record oversized, malformed
  and unsupported-schema settings rejection without accepting gameplay. Actual
  integrated normal-server build018 under Wine loaded Game/World/Mission, passed
  core VM settings self-test and initialized with zero clients and forced stop.
  Its exact PBO and separate positive official signature check are pinned below.
  Probe017 used DayZDiag and the older 014 PBO: a native diagnostic plugin
  `GetPlugin`/`PluginItemDiagnostic.OnInit` stack error was observed; classifier
  status is `compiler-error`, not diagnostic acceptance or a proven mod compiler
  defect. Probe019 remains pending with no accepted outcome. Native Windows,
  diagnostic self-tests, signed client/server loading and clean restart remain open.
- C02: Finite shared search pool, exact actor-bound attempts/results, v2 journal
  sidecar migration and conservative orphan handling authored with focused checks.
  These are complete within the finite experimental escrow/recovery scope, not
  complete economy/search implementation. Shared CE debits, contextual supply,
  measured furnishings and durable native inventory transactions remain pending.
  The later 14-test interior/context candidate utility is a review seam only;
  neither runtime layout consumption nor contextual allocation is implemented.
- C03: Bounded native-emission relay chains, exact persistent storage identity
  recovery, IC-01 descriptors/IC-02 observed-clue retarget/IC-05 ambiguity guards,
  IC-03 route progress/purpose, IC-04 pre-transfer durable-intent source and CR-06
  fair scheduling are implemented and frozen. Nash's focused suite passed 69;
  independent review resolved CR-01–CR-08 on their respective snapshots. Actual
  014 compiled/admitted the infected module; 016 held 210.363 seconds with no
  journal observed. Periodic saving, native durable transfer/crash reconciliation
  and the cause of the absent journal remain unproven. C10 adds diagnostic room
  loading; C11 adds an unwired veto policy. Complete physical variants, actual
  room surveys and executable observer-safe abstraction/materialization are absent.
- C04: Transactional installer/upgrader/recovery/rollback authored; 32 checks
  including four executable BDD scenarios. Review CR-01 corrected oversized ZIP
  expansion before validation. Complete for its reviewed offline managed-package
  transaction scope; it neither migrates world saves nor proves the friend's
  Windows filesystem install/restart/rollback. Final-source remote CI is pending.
- C05: Pinned CE diagnostic-export candidate tool authored; nine checks. Review
  CR-02 corrected UTF-16 declaration bypass; nine economy regressions also pass.
  Candidate import is implemented; actual eligible map coverage correction is not.
  Real geometry, supported engine installation/merge and measured supply remain open.
  Separate [interior/context candidate seam](../../../research/experiments/EXP-interior-data-completion.md)
  is frozen with 14 focused tests: bounded provenance/schema/source checks and
  review exports, with explicit synthetic markers. Runtime loader wiring,
  contextual sampler, real measurements, CE debit and inventory commit remain missing.
- C06: Core settings read bounded to 16 KiB; interrupted lifecycle cleanup,
  live crafting admission and registered-recipe audits implemented with actual
  RED/GREEN regressions. CR-05 full-quantity precedence and related active native
  overrides corrected; 25 crafting tests passed. Nine actual-method lifecycle
  tests cover synthetic callback aborts/retries. Compile-010 executed enabled
  native Crafting startup checks; it did not execute crafts, mutation-rejection
  branches or lifecycle fault injection. Native inventory crash atomicity is unproven.
- C07: Earlier Banso integration passed 409 discovered tests and 18 canonical
  offline scenarios. Later frozen suites report Rooms 13, observer 23, hygiene 31,
  interior candidate 14 and current compiler-probe 30. These are focused counts,
  not one combined passing run. C10 independent review passed; C11/C12/interior
  candidate independent review and final full-suite/BDD/hygiene/spec integration
  require their actual final records. A historical 477-test attempt failed while
  workers were editing; it is not final GREEN. Traceability is not requirement completion.
- C08: Integrated build018 PBO compiled/initialized under Wine and the matching
  bytes passed the official signature checker. Its checksum/source/log bindings
  are recorded below. This completes that development-PBO compile/sign slice;
  final portable ZIP/manifests/notices, signature-enforced normal client/server
  loading, Windows, destination transfer/restore and any post-freeze rebuild remain pending.
- C09: READMEs, original 25-task issues and nine milestones exist. Final-source
  commit, remote CI, precise status/evidence synchronization and private delivery
  remain pending. No source-complete or release-ready claim is warranted.
- C10: [Rooms diagnostic loader](../../../research/experiments/EXP-room-catalog-completion.md)
  implemented and frozen; 13 actual-method synthetic tests passed and independent
  review found no outstanding finding in that scope. Fixed-path one-shot DIAG
  server import, strict field sets, build/world/class/pose/evidence admission,
  unique live-house match and staged deep-copy publication are present. The exact
  source is included in normal build018; the diagnostic import branch has not
  been accepted in the engine. Real measurements, parser/query probes, paths,
  sound/two-client behavior and normal-PBO catalog enablement remain pending/absent.
- C11: [Observer veto seam](../../../research/experiments/EXP-observer-transition.md)
  implemented and frozen; 23 authored-policy synthetic tests passed. Explicit
  unknown/stale/replay/rollback rejection, complete-input declarations, retained
  danger/grace and bounded hysteresis are present; exact source compiled in 018.
  No authoritative observer/camera provider or live caller is wired. Every
  transition permission remains false, including diagnostic readiness. Review,
  CE/member/durable-commit integration and two-client optics/spectator/visibility
  evidence remain prerequisites, not an implemented abstract/materialized lifecycle.
- C12: [Hygiene tooling](../../../research/experiments/EXP-hygiene-completion.md)
  implemented and frozen; 31 tests passed, working-tree scan reported no findings.
  Bounded Git discovery/content admission, local documentation-target checks,
  narrow secret scanning and provenance/license inventory are present. User's
  private all-rights-reserved notice and private-key ignore rule are authored;
  inspected CI now invokes hygiene and its Windows suite. Independent review,
  final staged-source scan and remote Windows/Linux CI remain pending. Third-party
  rights review remains open; scanning does not authenticate provenance, cover
  all secret formats/history or authorize public/Workshop publication.

Counts identify focused suites, not unique test totals or gameplay acceptance.

### Integrated build018 and diagnostic probe pins

[Actual compiler report](../../../research/evidence/compiler-018-integrated-wine.json):
`initialized`, actual DayZ Server under Wine, zero clients, forced stop,
`signature_verified=false`, `runtime_acceptance=pending`. Independently matched
the actual PBO checksum, all five cached report log hashes and current Rooms and
observer source entries byte-for-byte. The script log shows Game/World/Mission
loading, core settings self-test PASS and server initialization. It does not show
execution of the diagnostic loader or unwired observer policy.

- PBO SHA-256: `038a420209dbe4b830fbf41ba44e16be7e6c82fa9759a9bb32bf81a6bfd9cf6c`.
- Script log SHA-256: `d745c6ddbeb2fbe1b4b50c0d6b49a4e3335136b0f89525fb4e49c0e73d0f9a48`.
- [Separate official signing report](../../../research/evidence/signing-018-wine.json)
  pins the same PBO; [actual checker output](../../../research/evidence/signing-018-check.txt)
  says its signature is OK. Signature SHA-256:
  `d9e56a475daed57ada6db82af0865541bdb8b9d57534c4e0ebb2e17317b51500`.
  Public key SHA-256:
  `a942004764ccb51fd400bad960185f6b3eb77af249fb6d19a407f3134dc11ad9`.
  Signing status is development-only, release disallowed and runtime acceptance pending.
- [Probe017](../../../research/evidence/compiler-017-diagnostic-wine.json) used
  older PBO `e0868ee3a53639795e21e33c0f03412c3b1d8b30c4157caf9abc3fa5021642ce`;
  its diagnostic plugin error is retained, not suppressed or accepted.
- Probe019: pending at this ledger freeze; staged files/running process are not
  a completed report. No success/failure, diagnostic or persistence claim follows.

The current probe suite count of 30 is the coordinator's frozen result; this
doc-only reconciliation independently counted 30 test methods but did not rerun
their synthetic process/filesystem tests. Later changes require new artifact pins.

### Independent original-requirement/source audit

Read-only gameplay audit on 2026-11-16: reviewed original SPECIFICATION sections
0.1/3–8, canonical spec/plan/tasks/traceability, module status/runtime contract,
authored gameplay/config/mission source, tooling and experiment evidence. Only
this execution ledger was edited; no gameplay implementation or new delegation.
The audit began during concurrent editing; the table below is reconciled with
the later frozen reports and build018. Pending reviews are identified in C07.

**Conclusion: the overhaul is not source-complete.** Offline foundation tools
and reviewed experimental slices are implemented; several required runtime
capabilities are absent, not merely waiting for a client to observe them. The
following keeps concrete source work distinct from prerequisites that cannot be
replaced by synthetic fixtures or undocumented engine assumptions.

| Original requirements / roadmap | Source actually present | Concrete remaining implementation and its separate acceptance dependency |
| --- | --- | --- |
| LOOT-01–06; FR-003/004; T010–T012 | CE audit, source-bound five-item usage pilot, measured-export candidate importer and reversible install tooling | Default `mission/hollow-country/ce/types.xml` and `cfgeconomycore.append.xml` are no-ops. No real apartment/barracks coverage patch, room/context distribution or observed essential/high-tier routes. Validated policy/route definitions and sample-analysis tooling can progress; actual point data, CE merge/eligibility, rates, diversity and world counts require genuine exports/baselines. Importer completion is not a coverage fix. |
| LOOT-02/04/05; INT-02/03; FR-006; T012/T015 | `HCInteriorRules.Allocation` and `AllocateManifest` precommit only Rag/Battery9V/empty, capped at four/two per epoch; bounded contextual-policy candidate exporter now has 14 focused tests | Runtime contextual allocation remains missing: review-only room/history/risk/item-group records are not wired to sampling or existing manifests. Weights, rarity/condition/storage behavior, live CE debit/reconciliation and safe delivery still need source integration and native feasibility/balance evidence. A finite supplementary pool and candidate export are not shared global economy accounting. |
| INT-01/02/04; FR-005; T013–T014 | Stable identity, three two-prop/two-history layouts, manifest/journal migration and orphan quarantine; bounded measured-layout candidate validator/exporter authored | `HCInteriorCatalog.Get` still contains explicitly unmeasured trial transforms for one class. Candidate data is not read by any runtime layout loader. Guarded runtime consumption remains source work; approved records require actual house/asset/door/stair/collision surveys. Existing normal-build PlacementAccepted/SearchAccepted return false; removing them is not completion. |
| INT-03/04; FR-006; NFR-004; T015/T023 | Native server action, target/range/LOS/time/actor checks, monotonic reservation/attempt/result journal and conservative quarantine | Durable inventory-plus-ledger commit and CE allocation ownership are not supplied by these scripts. Search remains hard-gated. Baked-furniture/proxy targeting is not implemented beyond the three added storage prop classes. Native targeting and item-save/crash experiments must determine the safe design before claiming exactly-once delivery; permanent quarantine can sacrifice supply and does not prove atomicity. |
| CRFT-01; FR-007; T016–T017 | Three audited native salvage pilots, condition/wear/ownership checks, null-spawn/reentry guards and real enabled startup validation in 010 | Pilot source/config admission is implemented, not the original atomicity/interruption/race acceptance. Result spawn precedes native ingredient deletion; no durable transaction API/recovery proof is established. Run CRF/NET failure boundaries and scoped vanilla-graph/balance controls. No justified additional gameplay rewrite or broader recipe count is implied by this audit. |
| AI-03/04; PHY-01; FR-008; T019–T020 | Frozen sensed clues, expiry, bounded native route attempts and semantic-room ordering; C10 diagnostic loader/live-house binding now wired through BuildOrder, 13 tests and independent review, compiled in 018 | Shipment catalog remains empty and all binding is diagnostic-only. Real room surveys, native parser/query/doorway/stair/blocked-route controls, sound and client fairness remain pending. Normal-PBO catalog use is absent. A source loading path and compilation do not establish operational methodical search or normal-PBO parity. |
| AI-05/06/07/09/10; AUD-01; FR-013; T018–T020 | Seven descriptor names, opt-in stance-indexed civilian/military policy mappings, clue lifetime/anchor differences, native injury fallback | `ResolveVariant` maps stalker/heavy to ordinary policy; no quieter/slower stalker, pause/listen behavior, authentic heavy force or injury extension is implemented. IC-08 diagnostic capture/probe harness and pure bounded pause/listen policy are feasible coordinated source work. Real native movement/audio/contact/crawl/cleanup evidence and recognizable appearance/location distribution remain prerequisites; descriptor names are not completed variants. |
| AI-01/08; PHY-01; AUD-01; FR-008; T018–T019 | Native navigation filter plus default-off contact guard; vanilla doors/hits/crawl/audio otherwise retained | No proven open-door improvement, unlocked-door/force policy or leg/arm correction. Diagnostic controls and bounded capture can be authored after API inspection; authentic door strike/lock/contact behavior and two-client injury/audio must be measured before choosing any extension. Keeping native behavior is a safe fallback, not acceptance of the requested correction. |
| AI-02/04; AUD-01; FR-009; T021/T023 | Native voice hook, frozen visual/voice provenance, bounded attenuation/TTL/hop/dedupe/rate/recipient relays | No explicit search/door/crafting semantic-event bridge is authored; whether native hearing already covers these actions remains unobserved. Record actual action noise/native AI response first, then add only demonstrated missing event wiring. No generic event bus or fabricated rummage noise is justified solely by its absence. Native human audibility and chains-plus-hordes controls remain pending. |
| AI-02/06; PHY-01; FR-009; T022 | Finite existing-CE cohorts, persistent identities, ambiguity handling, owned-pack routes; IC-03 progress/purpose, IC-04 prepared durable-intent source and CR-06 fair scheduling frozen/reviewed; C11 unwired observer veto policy has 23 tests and compiled in 018 | No actual periodic journal appeared in 014/016; native save/transfer/crash recovery is unproven. `CanAbstract`/`CanMaterialize` and observer transition permission remain false: no distant abstract simulation or safe activation/deactivation exists. Complete observer/camera provider integration, restored activation, CE replenishment/population authority, member/corpse state and two-client grace/visibility need IC-09/native experiments before executable transitions can be designed. Adoption-only groups do not fulfill section 6.4. |
| GOV-03; FR-010; NFR-003; T005/T024 | Repeated paired benchmark comparator and strict evidence manifests; bounded experimental work caps | No measured server/client budget or actual representative paired/endurance data. Coverage/loot-route and full runtime metrics described in the spec are not delivered by `metrics/benchmark-template.csv` alone. Bounded export/analysis adapters for actually available counters can be authored; hardware, routes, native profiler/counter availability, 3–6-player samples and approved ceilings must supply evidence. No retrospective thresholds or made-up metric values. |
| GOV-01/02; DEV-01–03; FR-001/002/011/012; NFR-001/005/006; T001–T009/T025 | Private tracking, native-first addon, default-off settings, traceability/evidence/benchmark tools, bounded CI and packaging; integrated 018 Wine compile/self-test and matching positive official signature check | T001/T006–T009 are complete only for the recorded foundation/offline scope. Session revision permits one local development host; two simultaneous clients remain required for applicable gates. Native Windows/Diag, signature-enforced normal client/server load, original runtime catalogs, final-source CI and backed-up friend install/restore remain pending. No waiver follows from successful compilation or utility tests. |
| SPECIFICATION 8.3; GOV-01/03; DEV-03; T009/T025 | Issue templates, bounded Windows/Linux tests/package jobs and package allowlists; C12 documentation-file target, narrow secret and provenance/license checks authored with 31 tests and workflow invocation | Independent C12 review, final staged-tree hygiene and actual hosted CI remain pending. Third-party rights/authorship, unrecognized secret formats, history, remote links and unsupported Markdown constructs are not certified. Final changelog/tag/PR-review/branch-protection evidence also remains pending; hosted settings require actual inspection and coordination. |

The previously proposed IC-06 loader, IC-07 veto seam, hygiene checks and interior
candidate data seam now have frozen source as detailed above. Remaining source
follow-ups include guarded runtime consumption/contextual allocation, a trustworthy
observer provider where actual native surfaces permit it, IC-08 native-control
capture plus separately reviewed pause/listen policy, and available-counter
analysis adapters. These are coordination items, not newly dispatched work,
completed gameplay features or authority to enable production.
Live CE/inventory/door/visibility capabilities must retain their native feasibility
gates; no substitute spawn/delete/teleport mechanism is proposed.

### Follow-up execution assignments

The audit above describes its original snapshot. The coordinator subsequently
authorized these bounded source follow-ups under the existing roadmap issues:

| ID | Existing task | Deliverable | Verification and boundary |
| --- | --- | --- | --- |
| C10 | T020 | Strict diagnostic measured-room catalog loading and live-house binding | Actual RED/GREEN malformed/provenance/bounds/binding tests; no invented room records or normal-build activation |
| C11 | T022 | Veto-only observer transition inputs and hysteresis | Execute authored policies on stale/unknown/visible/spectator/optics/rollback cases; provider integration and both transition capabilities remain blocked |
| C12 | T009/T025 | Repository documentation, content/provenance and secret admission checks | Synthetic unsafe-content regressions and CI integration; never print matched secret contents or invent a license grant |

C10 belongs to the room-catalog worker, C11 to a separate observer-policy worker,
and C12 to the tooling worker. The coordinator continues actual engine probes,
BDD integration, final artifact/signature verification and remote CI. Independent
review covers each source freeze; new work invalidates earlier final-source pins.

Audit validation: `PYTHONDONTWRITEBYTECODE=1 python3 -m tools.validate.project`
passed (48 requirements, 68 original catalog tests, 25 tasks, no errors), and
`PYTHONDONTWRITEBYTECODE=1 python3 -m tools.validate.runtime` passed operator
settings admission. No full suite or gameplay test was rerun for this ledger-only
edit. All original acceptance criteria remain pending unless their existing
scoped evidence explicitly proves them; no task or requirement was waived.

Final C01–C12 doc-only reconciliation: `python3 -B -m tools.validate.project`
again passed (48 requirements, 68 original catalog tests, 25 tasks, zero errors).
`git diff --check` passed. Only this file was edited; frozen gameplay/reports were
read, not changed. Build018 checksum/log/source checks above were read-only.
No whole-suite, native diagnostic or client acceptance run was performed here.
Probe019 remains pending at this freeze regardless of later coordinator work.

## Remaining infected capabilities and dependency order

The detailed native API audit and task contracts are in
[EXP-infected-completion.md](../../../research/experiments/EXP-infected-completion.md).
These remain within the existing roadmap issues, not additional accepted scope:

1. [T020](https://github.com/d-addison/hollow-country/issues/20): IC-01 explicit
   profile policy, IC-02 observed-clue retarget and IC-05 ambiguous-member
   accounting have source implementations in this wave. Full recognizable
   variant behavior/distribution and native acceptance remain open.
2. [T022](https://github.com/d-addison/hollow-country/issues/22): IC-03 measured
   route progress/purpose and IC-04 pre-transfer durable reservation intent.
   Source and CR-06 scheduler fixes are frozen/reviewed; actual progress,
   prepared-transfer durability and crash recovery remain unaccepted. No journal
   appeared during 014/016; the cause is unresolved. Neither a fixed pilot route
   nor periodic JSON saving alone satisfies these gates.
3. T020/T022: finish IC-05 storage-event ordering and death/corpse reconciliation;
   run actual save/restart controls before permitting restored pack activation.
4. T020: IC-06 diagnostic loader/binding source is frozen/reviewed and included
   in 018. Survey and bind real semantic room catalogs; verify open doors,
   stairs, blocked approaches, expiry and normal-PBO parity. Synthetic anchors
   cannot populate the production catalog.
5. T022: IC-07 veto-input/hysteresis source is frozen with 23 tests; independent
   review and complete authoritative observer-provider integration remain open,
   followed by two-client long-range/optics/spectator controls. Diagnostic
   readiness never authorizes transition. Proximity alone cannot prove invisibility.
6. [T018–T019](https://github.com/d-addison/hollow-country/issues/18): IC-08
   diagnostic locomotion/audio/injury/door probes against native controls. Door
   forcing and stalker movement stay unavailable until authentic native behavior
   and cleanup are demonstrated.
7. T022: IC-09 prove CE ownership/replenishment, persistent member state and crash
   reservation transfer. Only then design executable abstract/materialized
   transitions; no spawn/delete or teleport workaround is authorized by a mock.

Separate remaining gates apply to CE geometry/eligibility (T010–T012), measured
interior fit and shared CE search accounting (T013–T015), native inventory commit
and multiplayer recipe behavior (T017), combined load/performance (T023–T024)
and the friend's backed-up signed install/restore (T025). Detailed protocols and
all original acceptance IDs remain in the canonical plan and testing catalog.

## Wave 4: later player and destination acceptance

The user has deferred connection; do not repeatedly request it during source work.
When available, run NET-001–008, INT-001–011, CRF-001–007, AI-001–012,
AUD-001–007, HOR-001–011 and CE-001–012 against their original catalog methods.
Use two simultaneous clients for claims, action races, audio, late joins,
visibility and safe horde transitions. Test cancellation, death/disconnect,
full inventory, server crash, corrupted state, migration and rollback.

Calibrate and repeat paired baseline/candidate performance at the intended 3–6
players: server p95/p99, client 1% lows, memory/network/write slopes and host
contention. Do not choose thresholds retrospectively to accept a regression.
Finally verify the friend's OS/build, stage a backed-up private install, join,
restart and perform byte-checked rollback. No public or Workshop release.

## Completion condition

All original requirements remain mapped to acceptance criteria and executable
methods. Source completion requires no unexplained missing implementation;
product completion additionally requires the native and multiplayer artifacts,
signed package, measured budgets and destination restore proof. A blocked gate
must name its prerequisite and reproduction, never silently become complete.
