# Tests

These Python standard-library checks exercise offline tooling and authored data.
They require no DayZ installation and do not establish gameplay, native CE,
multiplayer, performance or release acceptance.

Run only files relevant to the change, from the repository root:

```sh
timeout 300 python3 -B -m unittest tests.unit.test_ce_audit
```

Do not run the full unit suite. The coverage inventory below describes existing
checks, including legacy source/translator contracts awaiting review; it does
not endorse those techniques or grant native acceptance.

| Suite | Coverage |
| --- | --- |
| [CE audit](unit/test_ce_audit.py) | Synthetic XML, declared sources, catalogs, raw coverage, numeric/path validation and CLI behavior. |
| [Crafting census](unit/test_crafting_audit.py) | Bounded whole-source inventory, raw provenance, disabled registrations and ambiguous inheritance; no live recipe or item-utility proof. |
| [Effective item exporter](unit/test_item_compatibility_audit.py) | Typed metadata, four declared roots, bounded contiguous chunks and terminal-manifest contracts; geometry and live item eligibility remain unproven. |
| [Flashlight candidate matrix](unit/test_flashlight_matrix.py) | Every input class stays counted, ambiguous roles stay explicit and pair enumeration is bounded; no mounting or geometry proof. |
| [Weather candidates](unit/test_atmosphere.py) | Native XML preservation, strict profiles, source reconstruction and fresh candidate output; no effective weather/lighting acceptance. |
| [Group server](unit/test_group_server.py) | Authored permissions, state, quota, replay and snapshot policies with synthetic engine/storage adapters. |
| [Group client](unit/test_group_client.py) | Session quarantine, request-counter recovery, frozen retries and delayed-reply cases with synthetic transport. |
| [Group map](unit/test_group_ui.py) | Draft preservation, marker constraints, native menu dispatch and layout bindings; no rendered widget acceptance. |
| [Group UTC clock](unit/test_group_clock.py) | Actual authored calendar/sampling methods across midnight, invalid dates, rollback and the signed epoch ceiling in January 2038. |
| [Group persistence](unit/test_group_persistence.py) and [RPC](unit/test_group_rpc.py) | Authored journal recovery, durable UTC watermark, authenticated ordering and failed-commit boundaries with synthetic native collaborators; no real restart or multiplayer proof. |
| [Group fixture runner](unit/test_group_native_checks.py) | Opt-in synthetic policy fixtures and failure/completion-marker behavior; native VM results are recorded separately. |
| [Stamina integration](unit/test_stamina_integration.py) | Disabled fallback, bounded settings, authority and inputs passed to the native stamina handler; no connected-client prediction or HUD proof. |
| [Stamina configuration](unit/test_stamina_configuration.py) | Fresh enabled moderate profiles (50% continuous drain, 25% faster recovery), preserved existing profiles, bounded reads, native receipt guards and session reset; no actual client network delivery proof. |
| [Stamina HUD](unit/test_stamina_hud.py) | Separate weight/stamina samples, native HUD-hide flags, reference bounds and lifecycle with synthetic widgets; no rendered viewport proof. |
| [Event director](unit/test_event_director.py) | Bounded opt-in participation, server observations, replay/transition limits and blocked unimplemented rewards; no live mission or AI delivery. |
| [Ecology policy](unit/test_ecology_rules.py) | Bounded fresh resource/path inputs, separate species/resource eligibility, session-bound receipts, partial acceptance, capacity and explicit retirement; no real perception or movement provider. |
| [Item manifest reader](unit/test_item_compatibility_manifest.py) | Strict pinned contiguous export/coverage admission and hostile file controls; POSIX input opening fails closed on unsupported platforms. |
| [Whole-content review](unit/test_item_review.py) | Complete input denominators, separate config/script inheritance, explicit ambiguity and bounded link work; no item-usefulness or craftability approval. |
| [Action source inventory](unit/test_action_audit.py) | Whole-source action calls, methods, item callbacks, ambiguity and analysis-work limits; no evaluated dispatch or effective gameplay claim. |
| [Utility cohorts](unit/test_item_utility.py) | Complete admitted metadata/source denominators, repeated declaration IDs, ambiguous repair-kit candidates and bounded indexed links; no repair compatibility or usefulness approval. |
| [Taped-light service](unit/test_taped_light_service.py) | Consumed tape, hand removal, item/energy conservation, full binding replay, damaged journals and recovered-history quarantine with synthetic custody; no qualified native host or attachment geometry. |
| [Stamina transport controls](unit/test_stamina_transport_probe.py) | Pinned native interfaces, local/context controls and finite numeric tolerance; no connected-client RPC acceptance. |
| [Fuel action](unit/test_siphon_fuel_action.py) | Server authority, leases, one-shot diagnostic debit/credit and mismatch refusal with synthetic native collaborators; no durable native fluid transaction proof. |
| [Fuel observation probe](unit/test_fuel_siphon_probe.py) | Native-interface admission, explicitly attributed stock-CE/CE-disabled controls, correlated conservation/callback/cleanup receipts and deadlines; no autonomous player proof. |
| [Fuel process runner](unit/test_fuel_probe_runner.py) | Fixed launch opt-in, fresh staging, live receipt admission, total wall-clock limits and owned process cleanup; synthetic process tests never establish actual fuel movement. |
| [Infected death probe](unit/test_infected_death_probe.py) | Five-case mission preparation, result correlation, observed cleanup and timeout refusal; no rendered ragdoll or loot/replication acceptance. |
| [Death selection diagnostic](unit/test_death_selection_probe.py) | Source-pinned native selection overrides, real damage/command callback contracts, bounded samples and cleanup receipts; no successful native death or rendered folding claim. |
| [Startup control](unit/test_native_startup_probe.py) and [process runner](unit/test_native_startup_runner.py) | Fixed actor-free stock-CE and CE-disabled controls, nonce-bound callback receipts, actual snapshot/entry budgets, final mission/launch-input checks, guarded report publication and cleanup; CE-disabled success cannot establish normal startup or gameplay. |
| [Process observations](unit/test_process_observation.py) | Pinned Linux PID/group/start time, bounded counter and log-metadata sampling, explicit unavailable data, reuse/rollback rejection and report limits; no game readiness, progress or deadlock proof. |
| [Automation planning](unit/test_automation.py) | Portable criteria, explicit capabilities and planning-only status; no gameplay execution or automatic acceptance. |
| [Benchmark comparison](unit/test_benchmark.py) | Synthetic repeated pairs, compatible contexts, explicit budgets and incomplete evidence. |
| [Evidence admission](unit/test_evidence.py) | Manifest requirements, artifact hashes/paths and unsupported capability promotions. |
| [BDD bindings](unit/test_bdd_bindings.py) | Exact scenario/step admission and rejection of unsupported or missing assertions. |
| [Runtime settings](unit/test_runtime_settings.py) | Operator JSON flags, limits and feature dependencies; no native serializer claim. |
| [Crafting contracts](unit/test_crafting_contract.py) | Salvage material ledger and native recipe source contracts; no transaction/crash proof. |
| [Interiors contracts](unit/test_interiors_contract.py) | Restricted scalar authored policies and source invariants; no native placement/transaction proof. |
| [Infected contracts](unit/test_infected_contract.py) | Restricted scalar authored policies, finite budgets and source invariants; no AI/audio/runtime proof. |
| [Package behavior](unit/test_package.py) | Deterministic containers, path/allowlist validation and signature command contracts; no native signature acceptance. |
| [Optional AI provider](unit/test_optional_provider.py) | Pinned dependency declarations, effective finite-ammunition/damage policy, bounded observer retirement receipts and an explicit exception for reviewed human-AI stuck recovery; no installed provider or authenticated evidence. |
| [Economy contracts](unit/test_economy_contract.py) | Synthetic profile/delta generation, isolated install and rollback; no effective CE merge/eligibility proof. |
| [CE candidates](unit/test_coverage_patch.py) | Hash-pinned synthetic geometry exports, minimal changes, encoding and point validation. |
| [Deployment](unit/test_deploy.py) | Real disposable filesystem transactions, process interruption, upgrade, recovery, drift refusal and byte-exact rollback; four executable deployment BDD scenarios. |
| [Crafting completion](unit/test_crafting_completion.py) | Actual authored admission and registry-audit methods with synthetic native objects. |
| [Salvage tools](unit/test_salvage_tools.py) | All 36 audited exact cutting classes across registration, eligibility and startup checks, with original tool handles retained; no native wear, inventory or concurrency proof. |
| [Measured interior import](unit/test_interior_measured_catalog.py) | Strict bounded source documents, schema-key remapping, explicit build admission, unique live-house binding and context-group restrictions with synthetic native adapters; no measured layout fit or production placement proof. |
| [House measurements](unit/test_interior_measurement_probe.py) | Fixed bounded acquisition bundle, pinned stock defaults/reference points, native pose and transform receipts, callback cleanup and strict scope; no room fit, clearance or loot eligibility proof. |
| [Whole interior survey](unit/test_interior_survey.py) | Complete placement/prototype/native-row denominators, explicit reviewed pose batches and nonce-bound acquisition merges; failed, repeated and unmeasured cases remain unresolved. |
| [Infected completion](unit/test_infected_completion.py) | Bounded authored relay/recovery policies and wiring; no native audibility or population proof. |
| [Compiler probe](unit/test_wine_compile_probe.py) | Compile/fatal-engine-crash classification, byte budgets, owned-process cleanup and fixed five-case death receipt/deadline admission. Includes a real disposable surviving child; mocked receipts do not prove native deaths. |
| [Native actor adapter](unit/test_native_autotest.py) | Bounded diagnostic mission generation and result admission; synthetic tests do not prove actor movement. |
| [Core lifecycle](unit/test_core_lifecycle.py) | Execute authored lifecycle methods on interrupted synthetic callbacks and cleanup retries. |
| [Infected profiles and clues](unit/test_infected_wave.py) | Authored profile, membership ambiguity and frozen-clue policies. |
| [Durable cohort intent](unit/test_infected_persistence.py) | Pre-transfer journal ordering, schema/generation admission and no replay after ambiguous transfer; no native CE transaction proof. |
| [Observed routes](unit/test_infected_routes.py) | Actual authored fair scheduler and progress policies on synthetic positions and clues. |
| [Measured room catalogs](unit/test_room_catalog_completion.py) | Bounded diagnostic document admission, unique house binding and atomic registration on synthetic native collaborators. |
| [Observer vetoes](unit/test_observer_transition.py) | Execute authored veto/hysteresis code on explicit synthetic observations; transition/provider capabilities remain blocked. |
| [Repository hygiene](unit/test_hygiene.py) | Real disposable Git trees; content bounds, private-key/token refusal, link validation and rights-notice admission. |

The bound [offline feature](features/offline.feature) executes its associated
behavioral suites through:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.validate.bdd
```

[Runtime scenarios](features/runtime.feature) are manual, pending protocols.
They are not executable offline acceptance. Native tests require recorded build,
scenario, repeated measurements and connected clients where applicable.

The [CE fixtures](fixtures/ce/README.md), [benchmark fixtures](fixtures/benchmark/)
are synthetic. Captured result logs stay local; a fresh test run establishes the
current suite result.
Tests create and clean temporary synthetic inputs, so execution requires write
access to their temporary locations, including fixture directories where used.

Windows CI additionally executes deployment/coverage/package suites and actual
PowerShell package guards on synthetic bytes. Actual DayZ compilation and
lifecycle evidence is maintained separately in local experiment records.
Wine runs of the official server do not establish native Windows/client behavior.

## Portable acceptance ledger

[catalog.json](catalog.json) retains all 68 original acceptance cases and extends
the ledger with program and Phase 2 criteria, including fuel siphoning and taped
flashlights. Each row includes its criterion, required capabilities, unresolved
assertions, evidence requirements and related issues. Input provenance hashes
identify the design snapshot; the local design documents are not needed to load
the catalog. These rows describe work to qualify, not completed executable tests.

Generate a planning report without a game installation:

```sh
python3 -B -m tools.testing.automation tests/catalog.json
python3 -B -m tools.testing.automation tests/catalog.json --select CRF-004
```

The optional repeatable `--capability NAME=available|blocked|unknown` flag declares
capabilities for planning. [capabilities.json](capabilities.json) lists the initial
unknown capability inventory; it is not a machine probe or a credentials file.
Unspecified capabilities stay unknown. A declaration cannot qualify gameplay.

The planner executes nothing: it never emits a PASS or FAIL. Original gameplay
cases remain BLOCKED even if capabilities are declared available; supported
offline modes can only become NOTRUN. Exit 0 means the report was generated,
not that its criteria passed. Invalid catalogs or arguments exit 2. Real adapters,
criterion-specific oracles and fresh native/client/load evidence remain required
before this ledger can serve as an execution report.


## Proposed test policy — audit round 1 (2026-11-20)

A test should fail when a contract or invariant breaks, rather than when an
implementation is reorganized or authored content changes. For Python tooling,
prefer real calls with disposable files or small synthetic inputs: conservation,
round trips, byte-identical rollback, deterministic output, schema validation,
refusal before mutation, and relationships derived from the actual input. Check
that the input set is nonempty when an empty fixture would make the test vacuous.
An independently computed expectation must constrain the output; merely comparing
two calls to the same implementation is insufficient behavior coverage.

Do not assert Enforce source substrings, regexes, statement order, class-name
lists, line numbers or prose. Do not execute Enforce through Python translations.
A Python tool that parses source may be tested with invented source fixtures;
that tests the Python parser, never Enforce behavior. Parsing config.cpp as data
for class references is likewise a data integrity check, not a source-text pin.
The evidence order remains native boot/RPT, native compile gate, lint, then Python
tests. A boot needs no compile error, crash or stall and no enabled module with
ready=false. Native experiments remain planned or deferred until observed on one
server and at most one client; offline checks never establish multiplayer proof.

Literal expectations copied from authored catalogs, tuning, counts, names or
prose are prohibited. Production literal pins are allowed only for external
contracts, with an adjacent `# External contract: ...` comment identifying the
stock snapshot/hash, schema consumer/version, or wire format and explaining why
it must remain fixed. Read the pin from its authoritative manifest rather than
duplicating it in tests. A schema version is a contract only when a consumer
requires it; an ordinary setting value is not. Synthetic fixture inputs may use
invented literals; expected behavior must follow from those inputs or a documented
contract. Such fixtures must stay small and must not copy an authored catalog.
Update code, invariants and external-contract comments together when the contract
changes; do not regenerate snapshots just to make a change pass.

## Static audit and proposed follow-up batches

Run `python3 -B -m tools.validate.test_audit` for every file's category counts and
the suite summary. Add `--json` for per-method assertion kinds, literal-operand
counts, detected reads, tools imports and classification evidence. Neither mode
imports test modules, executes fixtures, nor runs a suite. Output uses relative
repository paths. Ordering and JSON keys are deterministic.

A/B/C/E are exclusive recommendations per AST test definition. File counts overlap
when a file mixes categories. Helpers and files without test definitions are also
listed, with zero tests. Counts exclude dynamically generated cases and subTest
iterations. A is a source/translation candidate; B is a possible data snapshot;
C is an invariant or tooling-behavior candidate; E is an external-pin candidate.
D overlaps those categories and flags parse errors, missing local import targets
and possibly unbound Python globals. Global assignments in fixture setup are
recognized. Dynamic imports/exec, imported helper internals, inherited tests,
path aliases and the meaning of synthetic literals cannot be fully resolved
statically. In particular, absence of a D diagnostic never means a test passes.
These are review queues, not an automated deletion list: inspect each assertion
and keep synthetic tooling cases that a heuristic marks B. Existing E candidates
still need the external-contract comment checked or added in a later batch.

Baseline static categories (each cell is files / AST test definitions):

| Suite | A source | B snapshot | C invariant/tooling | D static candidate | E external pin |
| --- | ---: | ---: | ---: | ---: | ---: |
| legacy | 248 / 2707 | 50 / 522 | 148 / 1919 | 0 / 0 | 2 / 2 |
| slow | 1 / 2 | 31 / 499 | 69 / 1703 | 0 / 0 | 6 / 6 |
| unit | 0 / 0 | 5 / 26 | 20 / 399 | 0 / 0 | 2 / 2 |

After pilot static categories (each cell is files / AST test definitions):

| Suite | A source | B snapshot | C invariant/tooling | D static candidate | E external pin |
| --- | ---: | ---: | ---: | ---: | ---: |
| legacy | 244 / 2680 | 50 / 522 | 151 / 1925 | 0 / 0 | 2 / 2 |
| slow | 1 / 2 | 30 / 498 | 69 / 1704 | 0 / 0 | 6 / 6 |
| unit | 0 / 0 | 5 / 26 | 21 / 402 | 0 / 0 | 2 / 2 |

Observed pilot runs (pass / total test methods; errors are not counted as passes):

| File | Before | After |
| --- | ---: | ---: |
| legacy/test_infected_variety_install.py | 11 / 13 | 10 / 10 |
| legacy/test_infected_variety_routes.py | 0 / 10 | 4 / 4 |
| legacy/test_infected_variety_w56.py | 3 / 8 | 2 / 2 |
| legacy/test_infected_variety_w60.py | 0 / 7 | 1 / 1 |
| slow/test_s4_floorloot.py | 18 / 18 | 18 / 18 |
| **Pilot total** | **32 / 56** | **35 / 35** |

The baseline observed D overlay is **legacy: 4 files / 24 failing methods**;
slow: 0 / 0; unit: not sampled beyond the new classifier fixture. Static D is
zero in this checkout. The dynamic translator error cannot be established by
Python AST name resolution. After the pilot the five files have no failures or
skips. The classifier's own fixture file adds **3 / 3** passing tests separately.


Confirmed baseline pilot failures are separate from static D candidates: 24 test
methods across the four infected files produced 26 error reports (two extra
subTest reports), all from `NameError: HCHordeLimits` in the existing translator
fixture dependency. The passing source checks were also removed from the pilot.
The baseline floorloot file passed in this checkout, including the AmmoBox case;
this run did not reproduce the failure described in the brief. No other test
files were run. The stock events.xml and infected addon were both available and
matched the manifest hashes; no native stock data was added to the repository.

The checked-out manifest and addon still contain Sitter, Sleeper, Riser and Feeder
alongside Crawler, despite the brief describing their withdrawal on main. Pilot
expectations follow checked-out inputs without changing game content or pinning
the current destination roster. The three former runtime/translator pilot files
now check manifest relationships, stock event conservation, referential integrity
against parsed authored/stock config, and install/rollback. The synthetic installer
coverage remains; the floorloot authored snapshots now check policy membership,
supply conservation and idempotence. All native behavior remains unverified.

Next batches, each with review and only its changed test files run:

1. `tests/legacy/`: review the 148 files / 1,702 definitions classified entirely A first, grouped by
   subsystem (infected/horde, interiors, groups/stamina, then remaining runtime
   modules). Delete source-text/translator checks after identifying their lint,
   compile or boot replacement. Keep missing native scenarios traceable rather
   than marking them accepted. Do not delete shared helper files until imports
   are checked. Then handle mixed files method by method, preserving tooling C/E.
2. `tests/legacy/`: review the remaining 96 files with mixed A methods and
   convert B candidates (50 files / 522 methods, overlapping mixed files) in
   catalog/config/economy families to
   derived coverage, uniqueness, valid references, conservation and rollback.
   Review D/import dependencies within each batch; record observed failure causes
   without repairing a Python Enforce simulator.
3. `tests/slow/`: review the two A candidates in `test_enforce_formula_complexity.py`
   and convert B candidates (30 files / 498 methods) in authored economy, loot, map
   and packaging snapshots in separate subsystem batches. Retain synthetic
   transaction, refusal, capacity and recovery checks, including floorloot.
4. `tests/unit/`: preserve Python-tool behavior tests. Review B candidates
   (5 files / 26 methods: automation, enforce_perf, inventory_sizes,
   item_compatibility_manifest and portable_catalog) for
   synthetic-fixture false positives before converting actual production pins;
   document E external contracts. Keep source-census/parser fixture coverage.

Only the five named pilot files were rewritten in this round. Nothing outside
them was deleted. The classifier has a small three-test synthetic fixture file.
