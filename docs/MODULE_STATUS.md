# Gameplay implementation and remaining work

This file distinguishes authored functionality from missing implementation and
unperformed validation. The private development package is not the completed
overhaul. All original requirements remain in the spec, task graph and issues.
User instruction to implement before connecting permits source work; it does
not waive runtime evidence or make hard-gated features operational.

| Area | Authored now | Still missing or gated |
| --- | --- | --- |
| Shared runtime | Server lifecycle, bounded configuration, module registry, real elapsed time, native self-test source | Native compilation, actual lifecycle/self-test logs, signed loading |
| Economy | Stock audit, conservative profile/delta tooling, isolated install and exact rollback | Verified apartment/barracks coverage correction; observed engine merge/eligibility; measured contextual routes and budgets |
| Interiors | Stable identities, three two-prop trial layouts/two histories, immutable manifest, bounded startup placement source | Actual house transforms and measured layout fit, navigation/collision/replication, migration/orphan recovery. Normal-build placement is hard-gated |
| Search | Native continuous action, server-owned target/range/LOS/time/lock checks, finite allocation and claim journal | Shared CE allocator/reconciliation and proven durable inventory/ledger commit. Native UI/audio/races/restart unobserved. Normal-build search is hard-gated |
| Crafting | Three native salvage recipes, fixed yields, ownership/type/condition checks, tool wear, null-spawn and completion guards | Native compilation/config checks, inventory/ground behavior, concurrency/crash safety, balance and compatible rifle wrap observation |
| Infected | Bounded visual-clue sampling, native voice provenance, navmesh-validated native pack routes, nearby-anchor investigation, finite existing-CE cohorts and conservative persistence source | Semantic room catalog/order, persistent member recovery, safe horde abstraction/activation, supplementary audible chains and a complete recognizable variant roster. Native movement/perception/fairness remain unobserved |
| Packaging | Original-source container/signing/smoke tooling | Actual official signature verification, native module loading, client tests, combined load/performance and destination rollback |

Evidence is under `research/experiments/EXP-*-implementation.md` and the
[independent source review](../research/experiments/EXP-core-review.md).
Offline translated scalar tests check a restricted subset of authored policies;
source assertions inspect contracts. Neither is an Enforce compiler or engine.

The Windows interop socket from this agent session times out. The user launched
the vanilla server, whose CE startup is recorded separately; Hollow Country has
not run there. Native compiler/smoke output is the next executable gate. Client
connection remains deferred. No task requiring unobserved gameplay is closed.
