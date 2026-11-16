---
status: draft
owner: d-addison
updated: 2026-11-16
target_version: v0.1.0
priority: high
---
# Spec: Hollow Country survival overhaul

## Context

Hollow Country enriches scavenging in existing DayZ buildings and makes infected
groups dangerous through believable behavior. The complete product contract is
[SPECIFICATION.md](../../SPECIFICATION.md). Its confirmed GOV/DEV/LOOT/INT/CRFT/AI/
PHY/AUD requirements are incorporated, not replaced by offline tooling.
`traceability.json` maps every original requirement and retains every original
test. The handoff is design input, not proof of implementation.

## Confirmed session changes

- Name: Hollow Country. Initial map: ChernarusPlus, now confirmed.
- Develop and run the local test server here; final server belongs to a friend.
  Target is 3–6 players. Remote server access does not block local development.
- Supersede initial mandatory two-machine setup; still require two simultaneous
  clients for race, audio and visibility acceptance. See ADR-017.
- Private GitHub: `d-addison/hollow-country`. No public or Workshop publication.
  Deliver a portable transfer package and rollback without purchased game files.
- User subsequently requested implementation before their client connection.
  Client join/playtesting is deferred, not a prerequisite for authoring source.
  Installed-source API inspection remains mandatory; runtime acceptance and
  production feature enablement remain gated on actual observations.

## Goals

Deliver all four modules through P0–P8 with native config before custom code,
bounded work, server authority, persistence and measured improvement. Keep every
requirement actionable even when unavailable runtime evidence prevents acceptance.
Complete independent offline engineering while resolving engine setup.

## Non-Goals

No new building meshes, native navmesh replacement, arbitrary abundance multiplier,
restricted assets, public services or speculative gameplay hooks. Python reference
tools never substitute for Enforce Script and actual game observations.

## Functional Requirements

- FR-001: Map every handoff requirement and test to a task, criterion and evidence
  layer; record user deltas and unmet gates without dropping scope.
- FR-002: Inventory client/Diag/Tools/server; observe vanilla local join/reconnect,
  diagnostic hello-world and signed normal PBO client/server load.
- FR-003: Audit CE inputs/modular references without changing originals; reject
  invalid data; report raw points, placements, unknown groups and input hashes.
  Raw points are not observed eligible loot opportunities.
- FR-004: Identify apartments/barracks in game; make a minimal supported CE-only
  change and measure spawn coverage, diversity, inflation and overhead.
- FR-005: Three safe existing-asset layouts for one verified house, two histories,
  stable IDs, schema migration and no restart reroll or object duplication.
- FR-006: Server-allocated, range/LOS-validated, exactly-once search; durable
  depletion and quota transactions across concurrent requests, crash and retries.
- FR-007: Three useful native recipe/action extensions after vanilla audit; tool
  wear, interruption/full inventory safety, material conservation and no races.
- FR-008: Measure door/navigation/injury/audio and actual exposed hooks first;
  proven extensions with vanilla fallback, observed memories, escapable pursuit
  and distinct profile trade-offs. No hidden live player tracking.
- FR-009: Both bounded local audible chains and persistent moving hordes; finite
  TTL/hops/recipients, shared population budget, two-observer safe transitions,
  hysteresis and crash reconciliation; no visible pop-in or teleport.
- FR-010: Compare repeated paired baseline/candidate p95/p99 frame time and client
  1% lows; reject incompatible, invalid or incomplete performance evidence.
- FR-011: Capability promotions require exact build/method/test IDs and hashed
  runtime artifacts; two clients for network/audio/visibility acceptance.
- FR-012: Cheap static CI; complex features default off pending acceptance;
  reproducible local package/sign/transfer/install/migrate/rollback procedures.
- FR-013: Infected difficulty must not rely on blanket health/damage inflation.
  Population density remains varied below the global cap, with recognizable
  variant appearance and location tendencies, verified against native controls.

## Non-Functional Requirements

- NFR-001: TDD/SDD/BDD: requirement → failing behavioral test → smallest change →
  passing test → relevant runtime observation. Gherkin syntax is not execution.
- NFR-002: Zero introduced collision cheats, through-wall damage, silence fixes,
  blocked paths, duplication or omniscience. Keep native control evidence.
- NFR-003: No unbounded per-frame scans, objects, recipients, RPCs or writes.
  Calibrate at 3–6 players; the handoff's 5% ceiling remains a proposal.
- NFR-004: Server owns gameplay commits; versioned idempotent state, crash-safe
  bounded persistence, backup, migration and reversibility are mandatory.
- NFR-005: Standard-library Python offline tools; official runtime tools first;
  no purchased assets, private signing keys or restricted Workshop code in Git.
- NFR-006: Offline models cannot establish native behavior. Pending experiments
  remain pending; an engine-blocked claim needs a reproducible obstacle.

## Acceptance Criteria

- [ ] AC-001: No unmapped original requirement/test; machine-check task graph,
  dependencies and explicit blocked gates. #domain:foundation
- [ ] AC-002: Vanilla join/restart, diagnostic hook, signed packaging and normal
  PBO load observed on pinned build. #domain:platform
- [ ] AC-003: Offline CE tests reject corrupt/duplicate/negative data and verify
  deterministic raw coverage, hashes and explicit unknowns. #domain:loot
- [ ] AC-004: CE-003/004 pass in game for verified apartment/barracks, with no CE
  errors, inflation or sampled coverage regression. #domain:loot
- [ ] AC-005: INT-001–INT-011 pass for three layouts, restart persistence and
  concurrent claims without blocked paths or cloning. #domain:interiors
- [ ] AC-006: CRF-001–CRF-007 pass for three pilots; camo-net variant or a measured
  alternative if its required asset/API is unavailable. #domain:crafting
- [ ] AC-007: AI-001–AI-012 and AUD-001–AUD-007 have native controls, measured
  results, safe fallbacks and explicit engine limits. Compare health/damage with
  native controls, sample low/high density areas below the cap, and test variant
  recognition and location tendencies; reject blanket stat inflation and
  permanently dense populations. #domain:infected
- [ ] AC-008: HOR-001–HOR-011 pass with chains and hordes together, no observer
  pop-in or global population cap bypass. #domain:infected
- [ ] AC-009: Comparator rejects incomplete/incompatible/uncalibrated evidence;
  actual repeated benchmarks meet approved budgets. #domain:performance
- [ ] AC-010: Evidence tests reject unsupported promotion, tampered/missing files
  and one-client network acceptance. #domain:foundation
- [ ] AC-011: NET-001–NET-008 and module combinations pass; private transfer,
  clean install, migration and rollback exercised. #domain:integration
- [ ] AC-012: CI executes real offline behavioral tests; T2–T5 remain pending
  until real game artifacts satisfy release gates. #domain:foundation

## Open Questions

Resolve installations and hardware through discovery. Need second test client,
approved performance ceilings after baseline, observed building classes and tested
assets before runtime acceptance. Friend's OS/build/transfer method are required
before destination installation, not local R&D. Vanilla-first compatibility; loot
rates, recipes, replenishment/wipe rules, prop counts and horde sizes are measured
pilot decisions. See `interview.md`; do not invent permanent preferences.
