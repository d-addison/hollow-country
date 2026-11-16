# Gameplay implementation and remaining work

This file distinguishes authored functionality from missing implementation and
unperformed validation. The private development package is not the completed
overhaul. All original requirements remain in the spec, task graph and issues.
User instruction to implement before connecting permits source work; it does
not waive runtime evidence or make hard-gated features operational.

| Area | Authored now | Still missing or gated |
| --- | --- | --- |
| Shared runtime | Server lifecycle, 16 KiB configuration reader, module registry, real elapsed time; actual compiler/core script-VM self-test/initialization under Wine | Final-source repeat, native Windows, diagnostic and signed loading gates |
| Economy | Stock audit, conservative profile/delta tooling, isolated install and exact rollback; pinned measured-export candidate preparation | Verified apartment/barracks coverage correction; observed engine merge/eligibility; measured contextual routes and budgets |
| Interiors | Stable identities, three two-prop trial layouts/two histories, immutable manifest, bounded startup placement; conservative journal migration and orphan quarantine | Actual house transforms and measured layout fit, navigation/collision/replication, native migration/recovery trials. Normal-build placement is hard-gated |
| Search | Native continuous action, server-owned target/range/LOS/time/lock checks, shared finite allocation pool and actor-bound reservation/attempt/result journal | Shared CE allocator/reconciliation and proven durable inventory/ledger commit. Native UI/audio/races/restart unobserved. Normal-build search is hard-gated |
| Crafting | Three native salvage recipes, fixed yields, ownership/type/condition checks, tool wear, null-spawn and completion guards; live core admission and registered-recipe audits passed in actual DayZ under Wine | Native inventory/ground behavior, concurrency/crash safety, balance and compatible rifle wrap observation |
| Infected | Bounded visual-clue sampling, native voice provenance and bounded relay chains, native pack route validation, observed progress/purpose and fair retarget scheduling, durable pre-transfer cohort intent, semantic room catalog interface/order and exact storage-identity recovery; actual DayZ compilation/admission under Wine | Real measured room catalog, safe horde abstraction/activation and a complete recognizable variant roster. Native route traversal/perception, relay audibility and restart recovery remain unobserved; no periodic journal appeared during the 90-second hold |
| Packaging | Original-source container/signing/smoke tooling; transaction-based install/upgrade/recovery/rollback; official signature check succeeded on the earlier PBO under Wine | Final-source signing and native module loading, client tests, combined load/performance and destination rollback |

Evidence is under `research/experiments/EXP-*-implementation.md` and the
[independent source review](../research/experiments/EXP-core-review.md).
Offline translated scalar tests check a restricted subset of authored policies;
source assertions inspect contracts. Neither is an Enforce compiler or engine.

The Windows interop socket from this agent session times out. The user launched
the vanilla server, whose CE startup is recorded separately. Copying the official
executables to a private Linux filesystem cache enabled actual DayZ compiler and
official signing tools under Wine. A bounded isolated run compiled all modules,
passed the core script-VM self-test and reached initialization. Integrated run 018
repeated this successfully; official tools verified its development signature.
Diagnostic 017 emitted a native plugin error and is a failed smoke. See the
[completion evidence](../research/VALIDATION-COMPLETION-2026-11-16.md) for exact
artifacts, offline verification and disposable package rollback. This does not
establish native Windows or multiplayer acceptance.
Client connection remains deferred. No task requiring unobserved gameplay is closed.

See the [completion plan](specs/001-survival-overhaul/completion-plan.md) and
`research/experiments/EXP-*-completion.md` for the current work and evidence.
