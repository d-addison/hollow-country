# Task execution status

The canonical dependencies and writable scopes are in `task-graph.json`; detailed
done conditions are in `plan.md`. This ledger never substitutes for those gates.

| Tasks | State | Remaining acceptance |
|---|---|---|
| T001 | Complete | Private source pushed; all 48 requirements and 68 tests mapped |
| T002 | Partial | Windows OS/physical memory and native Tools execution still unobserved |
| T003 | Installations observed; runtime pending | Native Windows staging, vanilla join/respawn/reconnect/restart evidence |
| T004–T005 | Pending P0 runtime | Native script inspection, signed smoke test and measured baseline |
| T006–T008 | Complete for offline utility scope | Independent reviews and integrated Banso pipeline passed; native feature acceptance remains separate |
| T009 | Complete for offline foundation | Banso pipeline and remote static CI passed; native P0 remains gated |
| T010–T022 | Gated roadmap | Required native feasibility evidence before gameplay implementation |
| T023–T025 | Gated roadmap | Combined multiplayer, performance and destination install/rollback proof |

The friend can provide a second DayZ client later. Initial staging requests
loopback binding only; multiplayer reachability remains a separate setup step.
No gameplay module, runtime performance result or multiplayer acceptance is
claimed by the offline research utilities.

See [verification evidence](../../../research/VALIDATION-2026-11-16.md) and
[GitHub tracking](../../PROJECT_TRACKING.md) for the linked roadmap.
Source commit `1bd1e23` passed [GitHub CI](https://github.com/d-addison/hollow-country/actions/runs/43939865618).
T001 and T006–T009 can close for their scoped deliverables; P0's milestone
remains open because native baseline/smoke/performance evidence is pending.
