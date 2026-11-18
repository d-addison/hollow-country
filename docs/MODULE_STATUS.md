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
| Interiors | Stable identities, three two-prop trial layouts/two histories, immutable manifest, bounded startup placement; conservative journal migration and orphan quarantine. Bounded measured-catalog import binds exact reviewed documents, live house identity and contextual item groups; 15 synthetic checks and native run 054 compilation. Run 060 read an existing house's native pose, bounds and coordinate transforms. #138 adds a bounded building-position resolve cache (cleared on stop), preserving resolve/#q diagnostics, and cancels deferred interior pathgraph calls on stop; synthetic regressions pass, runtime acceptance pending | Complete measured catalog and layout fit, navigation/collision/replication, native parser/import/migration/recovery trials. Normal-build placement and search remain hard-gated; measurements and imported metadata do not prove fit |
| Search | Native continuous action, server-owned target/range/LOS/time/lock checks, shared finite allocation pool and actor-bound reservation/attempt/result journal | Shared CE allocator/reconciliation and proven durable inventory/ledger commit. Native UI/audio/races/restart unobserved. Normal-build search is hard-gated |
| Crafting | Three native salvage recipes, fixed yields, ownership/type/condition checks, tool wear, null-spawn and completion guards. All 36 audited cutting-tool classes share registration, eligibility and completion rules. Native run 055 compiled with crafting enabled and passed registered-definition/config checks | Native inventory/ground behavior, tool wear, concurrency/crash safety, balance and compatible rifle wrap observation. The broader justified recipe scope remains under review |
| Full item audit and utility extensions | Whole-source recipe census; chunked in-engine configuration exporter preserves native type variants and unresolved fields; unhooked fuel arithmetic with binary32 no-creation checks. Run 035 enumerated all 7,389 classes across four roots/15 chunks. Bounded flashlight matrix retains every class; its raw-artifact shape exercise emitted 47,888 candidate pairs | Complete item/recipe/action and usefulness audit, broad justified crafting scope, native fuel action and durable conservation, taped flashlight mounting/switching/geometry and client qualification. Candidates do not establish compatible geometry or gameplay |
| Infected | Bounded visual-clue sampling, native voice provenance and bounded relay chains, native pack route validation, observed progress/purpose and fair retarget scheduling, durable pre-transfer cohort intent, semantic room catalog interface/order and exact storage-identity recovery. Every complex path (pack routes, adoption, member recovery, investigation, chains, stimulus routes) is admitted only by its own qualification and fails closed with a reason code; dormant journals load verbatim; one stimulus selection (visual > external heard > retained memory) is shared by chains and investigation; explicit four-entry variant map. Final source compiled and initialized under Wine (compile 079) | Real measured room catalog, safe horde abstraction/activation and a complete recognizable variant roster. Native route traversal/perception, relay audibility and restart recovery remain unobserved; no periodic journal appeared during the 90-second hold |
| Packaging | Original-source container/signing/smoke tooling; transaction-based install/upgrade/recovery/rollback. Official tools signed and positively verified the exact run 057 addon under Wine; that addon compiled and initialized | Signature-enforced server/client loading, client tests, combined load/performance and destination rollback |
| Stamina and weight | Native handler scaling, bounded server profile, authenticated client receipt/session reset and separate cached weight/stamina bars. Defaults request 0.25 continuous exertion, 2.5x recovery and half the vanilla weight penalty (0.875 units/kg above the native 6 kg free threshold; native 5-unit minimum and 100-unit maximum with native defaults). Schema 1 profiles missing WeightPenaltyScale default to 0.5; invalid profiles and explicit disables are preserved. Native discrete jump/melee costs are retained. Earlier run 046 compiled the previous wiring under Wine | Final-source enabled profile loading and native delivery/order including WeightPenaltyScale, prediction/modifier compatibility, rendered layout and connected-client gameplay validation with two clients. Earlier compilation does not establish the new defaults or synchronized custom stamina; DayZDiag and normal PBO/server acceptance remain pending |
| Taped flashlights | Unhooked mount/removal service, consumed-tape checks, identity/condition/energy conservation, full binding replay guards, bounded intent/image journal and native inventory observations/transfers. Thirty-six synthetic checks include unresolved-operation quarantine, intent before custody acquisition and an operation-bound terminal write after confirmed release. Native run 057 compiled this service and initialized under Wine | First-release scope is native light-slot pairs only (rail/handguard rifles and pistols); other hosts are post-v1 (#58). Qualified host/slot/geometry matrix, exclusive inventory custody integration, LOS provider, native mount/removal/switching, crash recovery and two-client presentation. No actual host is qualified or automatically enabled; journal readback does not establish crash durability |
| Groups and navigation | Enabled server preference, authenticated routing, permissions, invitations, markers/notes, immutable journals and ordered counters. Full positive signed epoch range through January 2038, checked expiry addition, durable clock watermark, rollback refusal and failed-commit handling now pass 99 focused checks with synthetic collaborators. Earlier run 038 compiled client recovery/map/menu/icons; its 41 synthetic native policy steps completed | Final-source compilation, native persistence/restart/RPC trials, additional map layers/roles, rendered controls, two-client privacy/races and load qualification. LOS/radio requirements remain unsupported and rejected; synthetic fixtures do not establish enabled group gameplay |
| Weather and atmosphere | Native XML candidate generator with pinned source, explicit operator profiles and preserved unspecified settings; 16 synthetic regressions including early rejection of unrelated directory entries. No-op generation preserved the four inspected official mission templates byte-for-byte | Native XML/storage/map-script interaction, profile balance, visibility, accessibility, performance and rollback. Lighting and volumetric fog remain separate feasibility work; no weather profile is automatically installed |
| Optional events | Bounded unhooked event definitions, opt-in participants, ordered server observations, revision/replay protection, expiry/cancellation and frozen definitions; 18 focused checks. Native run 042 compiled the director | Native observation/objective adapters, mission roster, AI integration, durable economy-backed rewards, persistence and client presentation. Nonzero rewards remain blocked |
| PvE AI groups | Bounded declaration audit for a source-pinned optional provider: dependency subset, finite-ammunition/damage settings and observer retirement context; 31 focused checks. User-approved policy permits reviewed built-in human-AI stuck recovery, including visible repositioning | No provider is installed or qualified. The recovery exception does not waive exact artifact admission, permissions, finite ammunition, ordinary damage or cleanup fairness. Native-first provider implementation, combat/navigation, encounter integration and measured capacity remain outstanding |
| Ecology and migration | Unhooked resource-attraction scheduler separates animals/infected, accepts fresh resource/path capabilities, bounds work and rejects replay/overflow/null input. Thirty-three policy checks cover session-bound receipts, partial acceptance, capacity and explicit retirement; independent boundary review passed. Native run 054 compiled and initialized the integrated policy under Wine | Native resource observation, movement provider, population capacity, route surveys, persistence and combined performance qualification. No feeding/drinking or migration is activated |
| Firearms roster, datamine census and optional SNAFU subset (#30) | Offline tools and data: `tools/package/firearms.py`, `firearms_roster.json`, `snafu_optional.py`, `snafu_allowlist.json`, `tools/audit/firearm_census.py`. Owner decisions of 2026-11-17 are applied: 2x scarcity (vanilla weapon nominal 342, max 28 per gun); datamined rows spawn at rare counts, marked `acceptance: pending-local`, with one switch (`--no-datamined`); SNAFU conservative 7 plus WW2 SMGs plus 5 modern military-tier arms. Install and rollback are hard-link and outside-path safe | Not observed in DayZ: spawns, firing, ammo, CE totals, the SNAFU load and signed packaging are all pending local acceptance. The Tactical Flava optics subset is pending. Nine stock-absent variants are deferred. Not production-enabled |

#135 infected LOD review follow-ups (source only): `Infected/lod.json` now
ships full AI through 300 m, idle through 1000 m, materialize through 900 m,
fold beyond 1000 m and visibility checks through 1500 m. These are provisional
design defaults derived from the 1 km gunshot/network planning scale in
`docs/OUTSTANDING.md` and the 1000 m visibility baseline in
`docs/LOCAL_ACCEPTANCE_V1.md`. The 300 m near-threat setting in
`mission/hollow-country/ai/README.md` supplies a near-action precedent; using
it for infected is a design assumption. The 100 m materialize/fold hysteresis
and 500 m observer margin are provisional design choices. No measured gunshot cutoff
is documented. All bands remain validated operator settings: full < idle,
materialize >= full, fold >= idle, min-spawn < materialize < fold <= visibility,
idle <= 2000 m and visibility <= 3000 m. Existing explicit settings are retained;
older inconsistent profiles are refused with the existing invalid-ranges line.
Virtual herds stay **OFF** by default and posed budgets stay 12/12/12. Startup
prints all bands. Recyclable dead/folded actor entries move to a separate
24-entry FIFO with oldest-entry eviction; unresolved horde recovery evidence
stays reserved. Head, chest and lateral sight samples start at each observer's
head bone; each sample checks view/fire geometry, so at most six actual casts
are needed per observer. Any clear sample or incomplete budget refuses the
transition. The per-attempt tick budget is `MaxObservers * 6` (default 36,
hard maximum 48), shared by all samples/observers, so every allowed observer
can be proven occluded; incomplete checks refuse. Stats print `rays_per_min`,
`ray_peak` and `ray_budget`. Shutdown performs no fold/delete: living members
remain included in persisted `Alive`, and session-held leases reserve surviving
bodies across module stop/start; deaths and external claims debit once, while
missing bodies return to virtual capacity. Reuses the LOD cursor, player roster,
observer gate, admission and shared save scheduler/journal. Tests execute authored
control flow with synthetic engine ports. DayZDiag, normal PBO/server restart,
two-client partial-cover/foliage/vehicle/optics checks and load at 3–6 players
remain **runtime acceptance pending**; stop/start handles are session-only and
cross-process body persistence must be checked natively. No shared HCSettings,
serverDZ network defaults or global settings JSON edits are required.

## Living Country — V2

V2 preferences admit their modules by default; experiment verdicts are logged
without blocking startup. Dependencies, content and persistence checks still
apply. Compilation and dedicated-server initialization do not establish gameplay
acceptance. Server flags below do not control client-local visuals or undo
installed mission overlays.

| Module | Flag | State |
| --- | --- | --- |
| Grade, Lighting, WeatherDays | `EnableGrade` (weather also respects `EnableAtmosphere`) | being built / runtime acceptance pending |
| OptionalPacks (AmbientAnimals, Bicycles), Polish (Hints, EnvSound) | `EnableAmbientLife` | being built / runtime acceptance pending |
| SignsOfLife | `EnableSignsOfLife` | being built / runtime acceptance pending |
| Shelters, WreckSalvage | `EnableTravel` | being built / runtime acceptance pending |
| MapPins | `EnableTravel` or `EnableLeads`, with each pin kind filtered | being built / runtime acceptance pending |
| World, Escalation | `EnableWorld` | being built / runtime acceptance pending |
| SettlementDecay, InfectedMemory, HordeMigration, LootRefresh | `EnableWorld` | being built / runtime acceptance pending |
| Leads, Radio, Morse, Notes, BodyStories | `EnableLeads` | being built / runtime acceptance pending |
| Camps (tiers, visitors, mailbox, theft eligibility, probes) | `EnableCamps` | being built / runtime acceptance pending |
| Materializer, FactionConflict | `EnableEncounters` | being built / runtime acceptance pending |
| Holdouts, Pickers, DeadDrops | `EnableEncounters` | being built / runtime acceptance pending |
| Scenes and scene chains | `EnableEncounters` | being built / runtime acceptance pending |
| Optional Expansion living-world addon (Factions, Stance, AskForNews, Checkpoints) | `EnableEncounters`, plus optional provider dependencies | being built / runtime acceptance pending |
| Client grade, lighting, signs of life, hints, environmental sound, map pins and Morse presentation | Client-local defaults; server flags apply to corresponding server modules only | being built / runtime acceptance pending |
| Travel CE content and optional animal/bicycle mission overlays | Installed content; flags alone do not roll it back | being built / runtime acceptance pending |

The [V2 acceptance checklist](LOCAL_ACCEPTANCE_V1.md#v2-living-country-scaffolding)
retains feature steps, missing observations and two-client checks. Operator
settings, profile files and dependency loading are in the [handbook](README.md#living-country--v2-operations).

## Earlier native diagnostics

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

## Inventory sizes — owner playtest 2026-11-18

Spec: owner's scoped request on base `915aef1`; the named legacy spec files and
shared brief were absent. Plan/tasks: behavioral RED → vanilla declarations →
JSON rules/inheritance → merged config → check/package/regressions. Source tasks
are implemented; runtime acceptance and the existing-test scope decision remain open.

Final counts: **76 backpacks, 20 one-slot medical, 474 general** (570 overrides,
24 verified defining addons). `config/inventory-sizes.json` records each actual
parent, defining CfgPatches addon/member and vanilla/new dimensions. The unchanged
`tools/audit/pbo_config.py` reads installed vanilla addons only. The cached workbook
has no sizes; all 570 parents match it. All requiredAddons names were verified in
vanilla PBOs, including existing DZ_Scripts in `dta/scripts.pbo`. No Workshop
content or vanilla dumps are generation inputs or shipped assets.

Backpack width/shell stays unchanged; rows become ceil(rows × 1.5), including
bases/variants without compounded scaling. General 2×2 becomes 1×2 by shrinking
width. Area-two tools must weigh strictly below 500g; categories/includes are
explicit in JSON. Excluded: 413 cargo holders, 113 firearms/weapon attachments,
751 definitions outside area rules, 72 area-two category/weight exclusions and
868 hidden/non-inventory definitions. Already-one-slot items need no override.
Only backpacks change itemsCargoSize; an excluded descendant cannot inherit a
changed shell/cargo. Public diagnostic variants follow their family.

One-slot medical changes: AntiChemInjector, BandageDressing, BloodBagEmpty,
BloodSyringe, CharcoalTablets, ChelatingTablets, ClearSyringe, DisinfectantAlcohol,
Epinephrine, IodineTincture, Morphine, PainkillerTablets, PurificationTablets, Rag,
SewingKit, StartKitIV, Syringe, TetracyclineAntibiotics, Thermometer, VitaminBottle.
InjectionVial/BloodTestKit were already one slot; larger bags/spray use the general
rule; splints/defibrillators stay unchanged.

RED: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_inventory_sizes.py -k medical_explicit -v`
→ `Ran 1 test`; `FAILED (failures=1)` (Rag/SewingKit/SyntheticMedicine missing).
GREEN: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_inventory_sizes.py -v`
→ final `Ran 22 tests in 0.112s`; `OK`. The final extra RED caught a cargo-only
child override permitting inherited shell shrink; the property-specific guard
fixed it and leaves the actual vanilla block unchanged.
`PYTHONDONTWRITEBYTECODE=1 python3 -m tools.package.inventory_sizes --addons /mnt/d/HollowCountryLocal/runtime-v1/addons --check`
→ exit 0: native manifest, deterministic block and addon coverage agree. A stale
temporary config returned exit 1 without writing. `--review-only --check` checks
authored consistency only and never verifies vanilla.

Package/config selection (`rg -l 'config.cpp' tests/unit` plus package/sign/PBO)
ran 749 tests in 183.854s: one failure, one skip. Full command
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v`
ran 5,878 tests in 390.830s: the same failure, one skip, three expected failures.
It included 21 inventory tests; the final extra regression/guard then passed the
22-test focused run and native check. The full suite is **not green**: unowned
`test_gameplay_delta.py:774` requires CfgVehicles to contain ZombieBase alone.
Approval for `/tmp/hc-inventory-existing-test.patch` is pending; its three
infected-leg tests pass in memory without changing that file.

Final unsigned PBO build/verify passed (255 entries). config.cpp remains text,
verified byte-for-byte after packing; signing operates on the unchanged opaque
PBO and its existing flow is retained. Git metadata was not written; the writer
commit message is set. DayZDiag, normal PBO/server/client loading, inventory fit,
persistence/reconnect, nesting safety and balance at 3–6 players remain **pending**.
Offline checks do not grant production acceptance.
