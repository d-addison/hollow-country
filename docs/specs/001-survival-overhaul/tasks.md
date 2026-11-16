# Task execution status

The canonical dependencies and writable scopes are in `task-graph.json`; detailed
done conditions are in `plan.md`. This ledger never substitutes for those gates.

| Tasks | State | Remaining acceptance |
|---|---|---|
| T001 | Complete | Private source pushed; all 48 requirements and 68 tests mapped |
| T002 | Partial | Windows OS/physical memory and native Tools execution still unobserved |
| T003 | Native staging and server startup observed; CE initialization completed | Client join/respawn/reconnect and persistence restart; see startup experiment |
| T004–T005 | Installed script snapshot inspected; actual Game/World/Mission compilation, core script-VM self-test, crafting/infected admission and official prior-PBO signature check under Wine | Final-source signed loading, native Windows/Diag and measured baseline |
| T006–T008 | Complete for offline utility scope | Independent reviews and integrated Banso pipeline passed; native feature acceptance remains separate |
| T009 | Complete for offline foundation | Banso pipeline and remote static CI passed; native P0 remains gated |
| T010–T022 | Experimental source and offline module regressions authored; reviewed findings fixed | Missing gameplay and native acceptance detailed in MODULE_STATUS.md; no completed overhaul claim |
| T023–T025 | Offline integration and transactional package install/recovery/rollback source authored; native gates open | Combined multiplayer, performance and destination install/rollback proof |

The user explicitly deferred client connection and requested mod implementation
first. That authorizes source/package work; it does not turn offline tests into
runtime acceptance. The friend can provide a second DayZ client later. Observed
gameplay sockets bind loopback; Steam query bound wildcard, documented separately.
No runtime performance result or multiplayer acceptance is claimed by offline
research utilities or source inspection.

See [verification evidence](../../../research/VALIDATION-2026-11-16.md) and
[GitHub tracking](../../PROJECT_TRACKING.md) for the linked roadmap.
Source commit `1bd1e23` passed [GitHub CI](https://github.com/d-addison/hollow-country/actions/runs/43939865618).
T001 and T006–T009 can close for their scoped deliverables; P0's milestone
remains open because native baseline/smoke/performance evidence is pending.

The [detailed completion plan](completion-plan.md) tracks C01–C12 and subsequent
engine/client/destination waves. New work includes finite shared search recovery,
bounded emission relays and exact member identity recovery, measured CE export
candidate preparation, durable cohort intent, observed route progress and fair
scheduling, plus transactional package deployment. Diagnostic measured-catalog,
observer-veto and repository-hygiene source follow-ups have focused passing tests.
Focused tests and review corrections are in `research/experiments/EXP-*-completion.md`.
Integrated Banso verification passed with 508 discovered tests and 22 bound scenarios;
actual integrated PBO compilation, signature and disposable install/rollback passed.
See [completion evidence](../../../research/VALIDATION-COMPLETION-2026-11-16.md)
for exact hashes and diagnostic failures. Hosted CI is tracked there; source work
does not close the original gameplay requirements.
