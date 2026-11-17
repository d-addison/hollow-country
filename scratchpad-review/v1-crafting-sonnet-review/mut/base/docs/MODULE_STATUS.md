# Gameplay implementation and remaining work

This file distinguishes authored functionality from missing implementation and
unperformed validation. The private development package is not the completed
overhaul. Outstanding work is tracked in
[issues](https://github.com/d-addison/hollow-country/issues).
Source implementation does not waive runtime evidence or make gated features
operational.

All feature preferences now default enabled. Explicit operator disables are
preserved. Missing measured content, dependencies, providers or trusted receipts
still prevent admission and must be reported. An enabled preference alone is
not proof that its gameplay is operational.

| Area | Authored now | Still missing or gated |
| --- | --- | --- |
| Shared runtime | Server lifecycle, 16 KiB configuration reader, module registry, real elapsed time; actual compiler/core script-VM self-test/initialization under Wine. Native Windows vanilla join, movement, inventory and reconnect passed on 2026-11-17 | Final-source addon compilation, native Windows addon loading, diagnostic and signed loading gates |
| Economy | Stock audit, conservative profile/delta tooling, isolated install and exact rollback; pinned measured-export candidate preparation | Verified apartment/barracks coverage correction; observed engine merge/eligibility; measured contextual routes and budgets |
| Interiors | Stable identities, three two-prop trial layouts/two histories, immutable manifest, bounded startup placement; conservative journal migration and orphan quarantine. Bounded measured-catalog import binds exact reviewed documents, live house identity and contextual item groups; 15 synthetic checks and native run 054 compilation. Run 060 read an existing house's native pose, bounds and coordinate transforms | Complete measured catalog and layout fit, navigation/collision/replication, native parser/import/migration/recovery trials. Normal-build placement and search remain hard-gated; measurements and imported metadata do not prove fit |
| Search | Native continuous action, server-owned target/range/LOS/time/lock checks, shared finite allocation pool and actor-bound reservation/attempt/result journal | Shared CE allocator/reconciliation and proven durable inventory/ledger commit. Native UI/audio/races/restart unobserved. Normal-build search is hard-gated |
| Crafting | Three native salvage recipes, fixed yields, ownership/type/condition checks, tool wear, null-spawn and completion guards. All 36 audited cutting-tool classes share registration, eligibility and completion rules. Native run 055 compiled with crafting enabled and passed registered-definition/config checks | Native inventory/ground behavior, tool wear, concurrency/crash safety, balance and compatible rifle wrap observation. The broader justified recipe scope remains under review |
| Full item audit and utility extensions | Whole-source recipe census; chunked in-engine configuration exporter preserves native type variants and unresolved fields; unhooked fuel arithmetic with binary32 no-creation checks. Run 035 enumerated all 7,389 classes across four roots/15 chunks. Bounded flashlight matrix retains every class; its raw-artifact shape exercise emitted 47,888 candidate pairs | Complete item/recipe/action and usefulness audit, broad justified crafting scope, native fuel action and durable conservation, taped flashlight mounting/switching/geometry and client qualification. Candidates do not establish compatible geometry or gameplay |
| Infected | Bounded visual-clue sampling, native voice provenance and bounded relay chains, native pack route validation, observed progress/purpose and fair retarget scheduling, durable pre-transfer cohort intent, semantic room catalog interface/order and exact storage-identity recovery. Every complex path (pack routes, adoption, member recovery, investigation, chains, stimulus routes) is admitted only by its own qualification and fails closed with a reason code; dormant journals load verbatim; one stimulus selection (visual > external heard > retained memory) is shared by chains and investigation; explicit four-entry variant map. Final source compiled and initialized under Wine (compile 079) | Real measured room catalog, safe horde abstraction/activation and a complete recognizable variant roster. Native route traversal/perception, relay audibility and restart recovery remain unobserved; no periodic journal appeared during the 90-second hold |
| Packaging | Original-source container/signing/smoke tooling; transaction-based install/upgrade/recovery/rollback. Official tools signed and positively verified the exact run 057 addon under Wine; that addon compiled and initialized | Signature-enforced server/client loading, client tests, combined load/performance and destination rollback |
| Stamina and weight | Native handler scaling, bounded server profile, authenticated client receipt/session reset and separate cached weight/stamina bars. Fresh profiles now request 50% continuous running drain and 25% faster recovery; existing profiles and explicit disables are preserved. Native weight capacity and discrete jump/melee costs are retained. Earlier run 046 compiled the previous wiring under Wine | Final-source enabled profile loading and native delivery/order, prediction/modifier compatibility, rendered layout and connected-client gameplay validation. Earlier compilation does not establish the new default profile or synchronized custom stamina |
| Taped flashlights | Unhooked mount/removal service, consumed-tape checks, identity/condition/energy conservation, full binding replay guards, bounded intent/image journal and native inventory observations/transfers. Thirty-six synthetic checks include unresolved-operation quarantine, intent before custody acquisition and an operation-bound terminal write after confirmed release. Native run 057 compiled this service and initialized under Wine | First-release scope is native light-slot pairs only (rail/handguard rifles and pistols); other hosts are post-v1 (#58). Qualified host/slot/geometry matrix, exclusive inventory custody integration, LOS provider, native mount/removal/switching, crash recovery and two-client presentation. No actual host is qualified or automatically enabled; journal readback does not establish crash durability |
| Groups and navigation | Enabled server preference, authenticated routing, permissions, invitations, markers/notes, immutable journals and ordered counters. Full positive signed epoch range through January 2038, checked expiry addition, durable clock watermark, rollback refusal and failed-commit handling now pass 99 focused checks with synthetic collaborators. Earlier run 038 compiled client recovery/map/menu/icons; its 41 synthetic native policy steps completed | Final-source compilation, native persistence/restart/RPC trials, additional map layers/roles, rendered controls, two-client privacy/races and load qualification. LOS/radio requirements remain unsupported and rejected; synthetic fixtures do not establish enabled group gameplay |
| Weather and atmosphere | Native XML candidate generator with pinned source, explicit operator profiles and preserved unspecified settings; 16 synthetic regressions including early rejection of unrelated directory entries. No-op generation preserved the four inspected official mission templates byte-for-byte | Native XML/storage/map-script interaction, profile balance, visibility, accessibility, performance and rollback. Lighting and volumetric fog remain separate feasibility work; no weather profile is automatically installed |
| Optional events | Bounded unhooked event definitions, opt-in participants, ordered server observations, revision/replay protection, expiry/cancellation and frozen definitions; 18 focused checks. Native run 042 compiled the director | Native observation/objective adapters, mission roster, AI integration, durable economy-backed rewards, persistence and client presentation. Nonzero rewards remain blocked |
| PvE AI groups | Bounded declaration audit for a source-pinned optional provider: dependency subset, finite-ammunition/damage settings and observer retirement context; 31 focused checks. User-approved policy permits reviewed built-in human-AI stuck recovery, including visible repositioning | No provider is installed or qualified. The recovery exception does not waive exact artifact admission, permissions, finite ammunition, ordinary damage or cleanup fairness. Native-first provider implementation, combat/navigation, encounter integration and measured capacity remain outstanding |
| Ecology and migration | Unhooked resource-attraction scheduler separates animals/infected, accepts fresh resource/path capabilities, bounds work and rejects replay/overflow/null input. Thirty-three policy checks cover session-bound receipts, partial acceptance, capacity and explicit retirement; independent boundary review passed. Native run 054 compiled and initialized the integrated policy under Wine | Native resource observation, movement provider, population capacity, route surveys, persistence and combined performance qualification. No feeding/drinking or migration is activated |

Native run 042 also compiled the unregistered fuel diagnostic action: live
server authority, actor/car/vessel leases, one-shot debit/readback/credit and
mismatch refusal. Its 26 focused checks use synthetic native collaborators.
Actual fuel movement, compatible tools/vehicles, crash/save recovery and ordinary
client action registration remain outstanding. A fixed five-case infected death
probe now runs through a receipt-aware bounded normal-server harness. Actual run
043 under Wine exhausted its 80-second startup/observation budget before mission
initialization; cleanup completed within the 90-second outer bound. No case or
death receipt was observed. Rendered corpse/loot/replication checks remain open.
The first fixed-purpose fuel run, 045, also timed out during startup with no
receipt or fuel movement observed; owned-process cleanup was confirmed.
Fresh runs 047 (death) and 048 (fuel) used an explicit 180-second outer startup
allowance, preserving the 60-second fixture watchdog and all receipt checks.
Both initialized, then timed out without a complete receipt. Death reached its
health-only case; fuel created its three owned entities but recorded no action
start or transfer. No update frames were recorded in the partial fuel receipt.
Outer-process cleanup was confirmed. Actor-free control 051 then completed
three balanced SYSTEM updates and two queue callbacks when only ce.InitOffline
was omitted. Matching stock-CE control 052 timed out inside that call before
main returned, with no callbacks; cleanup was confirmed. The bounded observation
ended before ce.InitOffline returned. Its roughly 104-second observation inside
that call does not establish a permanent stall, a native Windows cause, or either
gameplay fixture's acceptance. Run 058 then separated an explicit 600-second
startup allowance from the 60-second callback fixture. It again ended without
CE_INIT_EXIT or any SYSTEM callback, taking 605.265 seconds including 5.063
seconds of confirmed process cleanup. This is a failed stock-CE diagnostic under
Wine, not evidence of a permanent engine stall or a native Windows cause.
Run 061 then omitted only the addon launch argument while retaining stock CE
and fresh isolated storage. It reproduced the missing CE return/callbacks and
timed out after 173.024 seconds, including 5.022 seconds of confirmed cleanup.
This reproduces the bounded failure without requesting the addon; it does not
identify the underlying engine/environment cause or prove ordinary Windows
startup fails.

CE-disabled fuel control 063 compiled and initialized, then reached one SYSTEM
update and three ticks. Its owned car, actor and vessel spawned and the actual
refill component was identified, but live range/LOS/eligibility validation refused
the action. No transfer was attempted. The failed receipt observed deletion of
all three owned entities and the outer harness confirmed process cleanup in
81.491 seconds. This narrows the diagnostic failure without accepting fuel use.

Death-selection diagnostic 065 compiled after concrete syntax fixes in failed
runs 062/064. Its scheduled spawn callback executed, then the native engine
crashed creating the infected in the CE-disabled control. No damage/death
observation completed. Outer cleanup was confirmed; the historical report also
reached its timeout. The harness now detects the engine's fatal crash marker
directly and revokes success even if the crash appears during final collection.
The cause of the native creation crash remains unresolved.

CE-disabled measurement run 060 completed in 73.866 seconds with one balanced
SYSTEM update and queue callback and confirmed process cleanup. It identified
one reviewed existing `Land_House_1W01`, read collision/clipping returns and
round-tripped four basis points and 18 stock XML reference points. It created no
entities. Twenty focused preparation/receipt checks pass. The native bounds'
coordinate basis remains unqualified; these observations do not establish room
labels, furniture clearance, door/stair routes, rendered fit, replication or
runtime loot eligibility. Earlier run 059 exposed a reserved parameter name in
the generated mission; that compile failure was corrected before run 060.

Whole-survey tooling retains all 11,679 stock placements, 436 prototypes and
7,389 native metadata rows. Twenty-two behavioral checks cover reviewed bounded
batches and strict acquisition merges. Admitting run 060 measures exactly one
placement; 11,678 remain unmeasured. Model metadata and a measured pose do not
qualify room labels, furnishing fit, navigation or CE eligibility.

Raw experiment records and machine inventories are maintained locally.
The whole-content review workbook retained all 7,389 native classes and all 234
source recipe classes across 3,056 installed script files. Its 2,344 references
include 55 unresolved references, including one malformed vanilla literal;
all 9,674 possible links were emitted. Enumeration and matching do not establish
craftability, useful balance or the complete effective item/action audit.
A separate full-source action census retained 460 candidates, 2,118 call
observations, 32,603 declarations including 365 global functions, and 301
categorized item callbacks.
Its 399 unresolved calls and 473 unresolved ancestries remain explicit;
effective dispatch and gameplay usefulness still require examination.
A bounded utility index now retains those complete admitted cohorts together,
including 180 repeated declaration-ID records, 3,595 repair-target observations,
nine kit classes and 2,302 possible kit/target links. Its 26 synthetic checks pass.
Array element typing and actual compatibility remain unknown; file admission and
authenticity are separate from internal source-manifest consistency.
Offline translated scalar tests check a restricted subset of authored policies;
source assertions inspect contracts. Neither is an Enforce compiler or engine.

Actual DayZ compiler and official signing tools have run under Wine in an
isolated local environment. A bounded run compiled all modules,
passed the core script-VM self-test and reached initialization. Integrated run 018
repeated this successfully; official tools verified its development signature.
Run 057 subsequently compiled the current addon, initialized and held for 10.021
seconds. Official DSSignFile and DSCheckSignatures then signed and positively
verified that exact PBO, whose SHA-256 is
`82066928e46f669f81f9d4be38795ed12142069937cb52e5fa2128a4d9795d48`.
The development key remains outside the repository. This verification does not
establish signature-enforced client/server loading or approve a release.
Diagnostic 017 emitted a native plugin error and is a failed smoke. See the
issue tracker for validation summaries and outstanding gates. These observations
do not establish native Windows or multiplayer acceptance.
Tasks requiring unobserved gameplay remain open.
