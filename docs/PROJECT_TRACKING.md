# Project tracking

[All issues](https://github.com/d-addison/hollow-country/issues) · [Milestones](https://github.com/d-addison/hollow-country/milestones)

Every task in the full P0–P8 spec has an issue and a phase milestone. Read
[task status](specs/001-survival-overhaul/tasks.md) for the verified local state;
an open or closed issue alone cannot establish runtime acceptance.

| Issue | Scope |
|---|---|
| [T001](https://github.com/d-addison/hollow-country/issues/1) | P0: Private source, confirmed decisions and lossless traceability |
| [T002](https://github.com/d-addison/hollow-country/issues/2) | P0: Inventory local official binaries, host and sources |
| [T003](https://github.com/d-addison/hollow-country/issues/3) | P0: Install official Tools and Server; vanilla local join |
| [T004](https://github.com/d-addison/hollow-country/issues/4) | P0: Diagnostic hello-world, official package and signature smoke test |
| [T005](https://github.com/d-addison/hollow-country/issues/5) | P0: Native baseline fixtures and 3–6-player budget calibration |
| [T006](https://github.com/d-addison/hollow-country/issues/6) | P0: TDD native CE offline audit and modular input validation |
| [T007](https://github.com/d-addison/hollow-country/issues/7) | P0: TDD repeated paired benchmark comparator |
| [T008](https://github.com/d-addison/hollow-country/issues/8) | P0: TDD evidence promotion validator |
| [T009](https://github.com/d-addison/hollow-country/issues/9) | P0: Spec/task integrity, executable offline BDD and static CI |
| [T010](https://github.com/d-addison/hollow-country/issues/10) | P1: Audit actual CE snapshot and identify apartment/barracks |
| [T011](https://github.com/d-addison/hollow-country/issues/11) | P1: Minimal supported CE coverage fix and controlled comparison |
| [T012](https://github.com/d-addison/hollow-country/issues/12) | P3: Contextual economy routes and conservative budgets |
| [T013](https://github.com/d-addison/hollow-country/issues/13) | P2: Native object and furniture targeting feasibility |
| [T014](https://github.com/d-addison/hollow-country/issues/14) | P2: Stable building identity and three persistent layouts |
| [T015](https://github.com/d-addison/hollow-country/issues/15) | P3: Server search allocation and crash-safe depletion |
| [T016](https://github.com/d-addison/hollow-country/issues/16) | P4: Vanilla recipe audit and three salvage pilot definitions |
| [T017](https://github.com/d-addison/hollow-country/issues/17) | P4: Native authoritative salvage implementation |
| [T018](https://github.com/d-addison/hollow-country/issues/18) | P5: Risk-first native AI doorway/LOS/door/audio/injury experiments |
| [T019](https://github.com/d-addison/hollow-country/issues/19) | P5: Smallest proven competence and injury corrections |
| [T020](https://github.com/d-addison/hollow-country/issues/20) | P6: Observed-memory investigation and two variant trade-offs |
| [T021](https://github.com/d-addison/hollow-country/issues/21) | P7: Native-first local audible chains with bounded propagation |
| [T022](https://github.com/d-addison/hollow-country/issues/22) | P7: Persistent horde accounting and safe activation |
| [T023](https://github.com/d-addison/hollow-country/issues/23) | P8: Combined modules, authority, migration and adversarial regression |
| [T024](https://github.com/d-addison/hollow-country/issues/24) | P8: Paired performance, endurance and destination capacity |
| [T025](https://github.com/d-addison/hollow-country/issues/25) | P8: Signed private handoff, install, clean rollback and legal inventory |

Canonical [spec](specs/001-survival-overhaul/spec.md),
[plan](specs/001-survival-overhaul/plan.md),
[graph](specs/001-survival-overhaul/task-graph.json) and
[traceability](specs/001-survival-overhaul/traceability.json) remain authoritative.
Update these together when requirements or dependencies change. New bugs and
scope changes use the repository issue templates and link requirement/test IDs.

`python3 -B tools/project/sync_github.py` previews the roadmap; `--apply` creates
missing tracking and refreshes generated task bodies. It preserves issue states
and milestone dates. Review generated body changes before applying to avoid
overwriting manually edited task descriptions. Use issue comments for execution
evidence and discussion; keep the generated description tied to the spec.
