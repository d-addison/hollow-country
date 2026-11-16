---
status: draft
owner: d-addison
updated: 2026-11-16
---
# Plan: Hollow Country

## Architecture

Native CE owns ordinary world loot and population first. Interiors own stable
building/layout/site identities and request bounded allocations from Loot.
Crafting extends native actions and server inventory transactions. Infected adds
only proven decisions; native physics/navigation/animation/audio remain authority.
One addon at mods/HollowCountry owns shared settings, bounded module lifecycle,
and server mission hooks; see docs/RUNTIME_IMPLEMENTATION_CONTRACT.md. Offline Python audit/benchmark/evidence tools have no
runtime gameplay role. See the full handoff for data models and invariants.

## Data and transaction design gates

WorldIdentity = map/build/schema/reset epoch. BuildingInstance = class + verified
quantized transform + collision discriminator; layout ID never depends on pointer
or iteration order. Site = instance/site/schema + durable depletion + allocation
ledger. Craft = validated native inventory transaction. Stimulus = audible origin,
time, category, provenance, TTL/hop budget. Memory contains observed clues only.
Horde = ID/epoch/count/anchor/route/materialized members with global occupancy.
Exact native classes, save and RPC signatures wait for installed-script spikes.
Crash journal and inventory atomicity are unproven until actual failure injection;
disable search/crafting if safe recovery cannot be established.

## Parallel work and gates

Immediate independent leaves: T006 CE audit, T007 benchmark comparator, T008
evidence validator, plus read-only platform/source research while T001 planning
is authored. Their write sets are disjoint. T009 integrates them. P1 economy and
P5 native AI research overlap after P0 runtime proof; interiors and recipe research
can also proceed independently after P0. User authorized source/package authoring before client join. Installed-script API
inspection and offline regressions permit that work; predecessor runtime evidence
remains mandatory for acceptance and production enablement.
The graph is a complete roadmap, not a claim every leaf is executable today.

## Implementation Tasks

### T001: P0 — Private source, confirmed decisions and lossless traceability

- Depends: none.
- Scope: docs/specs/001-survival-overhaul/spec.md, docs/specs/001-survival-overhaul/traceability.json.
- Acceptance: AC-001; All confirmed requirements and catalog tests mapped; private repository verified; no assets/secrets committed.
- Behavior tests: NET-008.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T002: P0 — Inventory local official binaries, host and sources

- Depends: T001.
- Scope: research/P0-build-inventory.md.
- Acceptance: AC-002; Exact client/server/Tools versions and paths, actual OS/hardware, source pins; missing installs explicit.
- Behavior tests: CE-001.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T003: P0 — Install official Tools and Server; vanilla local join

- Depends: T002.
- Scope: research/P0-server-launch.md.
- Acceptance: AC-002; Vanilla Chernarus local join, respawn, inventory, reconnect and persistence restart observed with logs.
- Behavior tests: NET-004, NET-005.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T004: P0 — Diagnostic hello-world, official package and signature smoke test

- Depends: T003.
- Scope: research/P0-first-mod.md, mods/HollowCountry/scripts/4_World/Core/HCNativeSelfTests.c, tools/package/Invoke-NativeSmoke.ps1, mods/HollowCountry/config.cpp, mods/HollowCountry/scripts/3_Game/HCSettings.c, mods/HollowCountry/scripts/4_World/Core/HCServer.c, mods/HollowCountry/scripts/5_Mission/HCMissionServer.c.
- Acceptance: AC-002; Inspect current scripts, verify diagnostic hook then signed PBO in normal client/server, record hashes; no unproven API.
- Behavior tests: NET-006, NET-008.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T005: P0 — Native baseline fixtures and 3–6-player budget calibration

- Depends: T003.
- Scope: research/P0-baseline.md, metrics/baseline.csv.
- Acceptance: AC-009; Verified building fixtures, controlled repeated warm/cold runs, host contention, proposed p95/p99/client budgets approved.
- Behavior tests: CE-001, AI-001, AUD-001.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T006: P0 — TDD native CE offline audit and modular input validation

- Depends: T001.
- Scope: tools/audit/ce_audit.py, tests/unit/test_ce_audit.py.
- Acceptance: AC-003; Recorded red/green; malformed/duplicate/nonfinite/negative inputs rejected; raw point/placement counts and hashes; no engine eligibility claim.
- Behavior tests: CE-001, CE-011.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T007: P0 — TDD repeated paired benchmark comparator

- Depends: T001.
- Scope: tools/benchmark/compare.py, tests/unit/test_benchmark.py.
- Acceptance: AC-009; Recorded red/green; incompatible evidence rejected; p95/p99 and client lows checked; missing calibrated thresholds/manifests INCOMPLETE.
- Behavior tests: HOR-008.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T008: P0 — TDD evidence promotion validator

- Depends: T001.
- Scope: tools/validate/evidence.py, tests/unit/test_evidence.py.
- Acceptance: AC-010; Recorded red/green; runtime promotions require build/method/artifact hashes, two-client and performance evidence; missing/tampered files fail.
- Behavior tests: NET-006.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T009: P0 — Spec/task integrity, executable offline BDD and static CI

- Depends: T006, T007, T008.
- Scope: tools/validate/project.py, tests/unit/test_project_contract.py, tests/features/offline.feature, .github/workflows/static.yml, tools/validate/runtime.py, tests/unit/test_runtime_settings.py, config/hollow-country-settings.json.
- Acceptance: AC-012; Unmapped IDs/cycles fail, all behavior bindings execute; Banso spec/plan/task/BDD checks run; inexpensive static CI excludes game builds.
- Behavior tests: NET-008.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T010: P1 — Audit actual CE snapshot and identify apartment/barracks

- Depends: T004, T005, T006.
- Scope: research/experiments/EXP-CE-coverage.md, metrics/building_coverage.csv.
- Acceptance: AC-004; Pinned local source hashes, exact classes/positions and eligible point evidence; zero raw points not mistaken for verified no-loot.
- Behavior tests: CE-001, CE-003, CE-004, CE-012.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T011: P1 — Minimal supported CE coverage fix and controlled comparison

- Depends: T010.
- Scope: mission/hollow-country/README.md, research/experiments/EXP-CE-override.md, tools/package/economy.py, tests/unit/test_economy_contract.py, mission/hollow-country/cfgeconomycore.append.xml.
- Acceptance: AC-004; Observed correct override/point update mechanism, valid placements and zero CE errors; backup/rollback and matched benchmark.
- Behavior tests: CE-002, CE-003, CE-004, CE-011.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T012: P3 — Contextual economy routes and conservative budgets

- Depends: T011.
- Scope: research/experiments/EXP-loot-balance.md, metrics/loot_routes.csv, mission/hollow-country/ce/types.xml, mission/hollow-country/economy-profiles/contextual-pilot.json.
- Acceptance: AC-004; Essentials have two credible routes; soft high-tier exceptions, diversity and world counts measured; tune rates only after baseline.
- Behavior tests: CE-005, CE-006, CE-007, CE-008, CE-009, CE-012.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T013: P2 — Native object and furniture targeting feasibility

- Depends: T004, T005.
- Scope: research/experiments/EXP-interior-feasibility.md.
- Acceptance: AC-005; One verified house, safe asset catalog, target/proxy feasibility and 0/5/10/20 prop sweep; no blocked doors/nav regression.
- Behavior tests: INT-004, INT-005, INT-008, INT-010, INT-011.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T014: P2 — Stable building identity and three persistent layouts

- Depends: T013.
- Scope: research/experiments/EXP-interiors-implementation.md, research/experiments/EXP-layout-persistence.md, mods/HollowCountry/scripts/4_World/Interiors/HCInteriorCatalog.c, mods/HollowCountry/scripts/4_World/Interiors/HCInteriorModule.c.
- Acceptance: AC-005; Three layouts/two histories for tested class, deterministic instance IDs with collision handling; restart/migration idempotence and two-client sync.
- Behavior tests: INT-001, INT-002, INT-004, INT-005, INT-006, INT-009, INT-010, INT-011.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T015: P3 — Server search allocation and crash-safe depletion

- Depends: T012, T014, T008.
- Scope: research/experiments/EXP-interiors-implementation.md, research/experiments/EXP-search-transaction.md, mods/HollowCountry/scripts/4_World/Interiors/HCInteriorAction.c, mods/HollowCountry/scripts/4_World/Interiors/HCInteriorStore.c.
- Acceptance: AC-005; Server range/LOS/item whitelist, quota and depletion journal; two-client same-site retry/crash/full inventory no duplication; no drawer refill.
- Behavior tests: INT-003, INT-006, INT-007, INT-008, CE-009, CE-010, NET-001, NET-002, NET-003, NET-005, NET-007.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T016: P4 — Vanilla recipe audit and three salvage pilot definitions

- Depends: T004.
- Scope: research/experiments/EXP-salvage-feasibility.md.
- Acceptance: AC-006; Avoid duplicate vanilla recipes; three useful permitted pilots including camo-net feasibility; typed material and wear ledger, no positive resource cycles.
- Behavior tests: CRF-001, CRF-006, CRF-007.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T017: P4 — Native authoritative salvage implementation

- Depends: T016, T008.
- Scope: research/experiments/EXP-crafting-implementation.md, research/experiments/EXP-salvage-transaction.md, mods/HollowCountry/scripts/4_World/Crafting/HCSalvageRecipe.c, mods/HollowCountry/scripts/4_World/Crafting/HCRecipeRegistration.c, mods/HollowCountry/scripts/4_World/Crafting/HCCraftingModule.c.
- Acceptance: AC-006; Inspect native transaction semantics before atomicity design; cancellation/death/disconnect/tool wear/full inventory and two-client races all observed.
- Behavior tests: CRF-001, CRF-002, CRF-003, CRF-004, CRF-005, CRF-006, CRF-007, NET-001, NET-002, NET-003, NET-007.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T018: P5 — Risk-first native AI doorway/LOS/door/audio/injury experiments

- Depends: T004, T005.
- Scope: research/experiments/EXP-AI-native.md.
- Acceptance: AC-007; Timebox 100 doorway trials where practical, two-client audio surfaces, current hooks/hitpoints; document inherited bugs, no speculative fix.
- Behavior tests: AI-001, AI-003, AI-008, AI-010, AI-011, AUD-001, AUD-002, AUD-003, AUD-007.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T019: P5 — Smallest proven competence and injury corrections

- Depends: T018.
- Scope: research/experiments/EXP-infected-implementation.md, research/experiments/EXP-AI-competence.md, mods/HollowCountry/scripts/4_World/Infected/HCInfectedNative.c.
- Acceptance: AC-007; Evidence-backed hooks, actual contacts and lock policy; bounded fallback; never teleport or bypass collisions; native control unregressed.
- Behavior tests: AI-001, AI-002, AI-003, AI-008, AI-010, AI-011, AI-012, AUD-005, AUD-006.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T020: P6 — Observed-memory investigation and two variant trade-offs

- Depends: T019.
- Scope: research/experiments/EXP-infected-implementation.md, research/experiments/EXP-AI-search.md, mods/HollowCountry/scripts/4_World/Infected/HCInfectedPolicy.c, mods/HollowCountry/scripts/4_World/Infected/HCInfectedNavigation.c.
- Acceptance: AC-007; Last observed clues expire; reachable room anchors and bounded retries; player can escape; slower stalker remains audible to two clients; reject blanket health/damage inflation, sample variable densities below cap, verify recognizable variant appearance and location tendencies against native controls.
- Behavior tests: AI-004, AI-005, AI-006, AI-007, AI-009, AI-012, AUD-001, AUD-002, AUD-003, AUD-004, AUD-006.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T021: P7 — Native-first local audible chains with bounded propagation

- Depends: T018, T020.
- Scope: research/experiments/EXP-infected-implementation.md, research/experiments/EXP-alert-chain.md, mods/HollowCountry/scripts/4_World/Infected/HCInfectedModule.c.
- Acceptance: AC-008; Native hearing first; real audible provenance, spatial nearby query, TTL/hops/attenuation/dedupe/cooldown/rate/queue caps; no hidden coordinates.
- Behavior tests: HOR-001, HOR-002, HOR-003, HOR-008, HOR-011.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T022: P7 — Persistent horde accounting and safe activation

- Depends: T020, T021.
- Scope: research/experiments/EXP-infected-implementation.md, research/experiments/EXP-horde-lifecycle.md, mods/HollowCountry/scripts/4_World/Infected/HCInfectedState.c.
- Acceptance: AC-008; Finite shared CE budget, persistent identity/epoch/member reconciliation, reachable routes, two-observer safe activation and hysteresis, no duplicate or visible spawning.
- Behavior tests: HOR-004, HOR-005, HOR-006, HOR-007, HOR-008, HOR-009, HOR-010, HOR-011.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T023: P8 — Combined modules, authority, migration and adversarial regression

- Depends: T015, T017, T022.
- Scope: research/experiments/EXP-integration.md, docs/MODULE_STATUS.md, docs/RUNTIME_IMPLEMENTATION_CONTRACT.md.
- Acceptance: AC-011; Individual and combined flags, malformed RPC, late join/crash/restart, corruption/migration/backup and throttling tests; all original test catalog covered.
- Behavior tests: NET-001, NET-002, NET-003, NET-004, NET-005, NET-006, NET-007, NET-008.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T024: P8 — Paired performance, endurance and destination capacity

- Depends: T023, T007.
- Scope: research/experiments/EXP-performance.md, metrics/candidate.csv.
- Acceptance: AC-009; Repeat controlled runs at 3–6-player intended load; p95/p99/client lows/memory/net/write slopes pass calibrated budgets; record host contention and friend hardware recheck.
- Behavior tests: HOR-008, HOR-011.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

### T025: P8 — Signed private handoff, install, clean rollback and legal inventory

- Depends: T023, T024.
- Scope: docs/TRANSFER_AND_ROLLBACK.md, research/experiments/EXP-transfer.md, tools/package/pbo.py, tools/package/sign.py, tools/package/Build-Sign-Verify.ps1, tests/unit/test_package.py, mission/hollow-country/INSTALL_AND_ROLLBACK.md.
- Acceptance: AC-011; Pinned package hashes/signatures, no assets or secrets; friend OS/build verified, save backup, install/join/restart and rollback exercised; no public release.
- Behavior tests: NET-005, NET-006, NET-008.
- Method: write failing test/scenario, inspect native surface, smallest change, green + regression + performance; runtime tests require real artifacts.

## Risks and rollback

| Risk | Response |
|---|---|
| Missing Tools/server or Windows interop unavailable | Continue independent offline work; report exact failure; no runtime success claim |
| Native nav/audio/targeting not exposed | Timebox experiment; reproducible obstacle + ADR; no physics cheats |
| Search/crafting partial commits | Crash and two-client tests; block release until recovery is proven |
| Furnishing or hordes exceed budget | Reduce counts/detail; keep collision/audio fairness; disable feature |
| Live save schema change | Back up, migrate on copy, test restore; no silent wipe |
| Unknown friend's host | Portable manifest/runbook now, destination test later |

Gate exit requires requirement coverage, executed tests, pinned artifacts and
matched baseline/candidate data. Missing runtime prerequisites leave dependent
tasks pending. Final alpha is not accepted until P8 and destination smoke test.
