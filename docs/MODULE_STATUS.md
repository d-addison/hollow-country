# Gameplay implementation and remaining work

This file distinguishes authored functionality from missing implementation and
unperformed validation. The private development package is not the completed
overhaul. Outstanding work is tracked in
[issues](https://github.com/d-addison/hollow-country/issues).
Source implementation does not waive runtime evidence or make gated features
operational.

| Area | Authored now | Still missing or gated |
| --- | --- | --- |
| Shared runtime | Server lifecycle, 16 KiB configuration reader, module registry, real elapsed time; actual compiler/core script-VM self-test/initialization under Wine | Final-source repeat, native Windows, diagnostic and signed loading gates |
| Economy | Stock audit, conservative profile/delta tooling, isolated install and exact rollback; pinned measured-export candidate preparation | Verified apartment/barracks coverage correction; observed engine merge/eligibility; measured contextual routes and budgets |
| Interiors | Stable identities, three two-prop trial layouts/two histories, immutable manifest, bounded startup placement; conservative journal migration and orphan quarantine | Actual house transforms and measured layout fit, navigation/collision/replication, native migration/recovery trials. Normal-build placement is hard-gated |
| Search | Native continuous action, server-owned target/range/LOS/time/lock checks, shared finite allocation pool and actor-bound reservation/attempt/result journal | Shared CE allocator/reconciliation and proven durable inventory/ledger commit. Native UI/audio/races/restart unobserved. Normal-build search is hard-gated |
| Crafting | Three native salvage recipes, fixed yields, ownership/type/condition checks, tool wear, null-spawn and completion guards; live core admission and registered-recipe audits passed in actual DayZ under Wine | Native inventory/ground behavior, concurrency/crash safety, balance and compatible rifle wrap observation |
| Full item audit and utility extensions | Whole-source recipe census; chunked in-engine configuration exporter preserves native type variants and unresolved fields; unhooked fuel arithmetic with binary32 no-creation checks. Run 035 enumerated all 7,389 classes across four roots/15 chunks. Bounded flashlight matrix retains every class; its raw-artifact shape exercise emitted 47,888 candidate pairs | Complete item/recipe/action and usefulness audit, broad justified crafting scope, native fuel action and durable conservation, taped flashlight mounting/switching/geometry and client qualification. Candidates do not establish compatible geometry or gameplay |
| Infected | Bounded visual-clue sampling, native voice provenance and bounded relay chains, native pack route validation, observed progress/purpose and fair retarget scheduling, durable pre-transfer cohort intent, semantic room catalog interface/order and exact storage-identity recovery; actual DayZ compilation/admission under Wine | Real measured room catalog, safe horde abstraction/activation and a complete recognizable variant roster. Native route traversal/perception, relay audibility and restart recovery remain unobserved; no periodic journal appeared during the 90-second hold |
| Packaging | Original-source container/signing/smoke tooling; transaction-based install/upgrade/recovery/rollback; official signature check succeeded on the earlier PBO under Wine | Final-source signing and native module loading, client tests, combined load/performance and destination rollback |
| Stamina and weight | Scalar load/exertion policy and default-off native handler integration; continuous rates pass through native event subtraction, clamp and recovery. Run 034 compiled and initialized the hook under Wine; 29 focused offline checks | Trusted configuration loading/synchronization, prediction/modifier compatibility, stamina/weight bars and connected-client gameplay validation. No active stamina change yet |
| Groups and navigation | Default-off server rules, authenticated routing, permissions, invitations, markers/notes, immutable journals and wire-version-2 counter floors. Client recovery/retries, draft preservation, map/menu/icons and consistent UTC sampling compiled in normal server run 038 under Wine. All 41 opt-in synthetic policy steps completed in the native VM | Calendar/epoch range limits, native persistence/restart/RPC trials, rendered widget instantiation and controls, two-client privacy/races and load qualification. Synthetic native fixtures do not establish enabled group gameplay |
| Weather and atmosphere | Native XML candidate generator with pinned source, explicit operator profiles and preserved unspecified settings; 15 synthetic regressions. No-op generation preserved the four inspected official mission templates byte-for-byte | Native XML/storage/map-script interaction, profile balance, visibility, accessibility, performance and rollback. Lighting and volumetric fog remain separate feasibility work; no weather profile is automatically installed |

Raw experiment records and machine inventories are maintained locally.
Offline translated scalar tests check a restricted subset of authored policies;
source assertions inspect contracts. Neither is an Enforce compiler or engine.

Actual DayZ compiler and official signing tools have run under Wine in an
isolated local environment. A bounded run compiled all modules,
passed the core script-VM self-test and reached initialization. Integrated run 018
repeated this successfully; official tools verified its development signature.
Diagnostic 017 emitted a native plugin error and is a failed smoke. See the
issue tracker for validation summaries and outstanding gates. These observations
do not establish native Windows or multiplayer acceptance.
Tasks requiring unobserved gameplay remain open.
