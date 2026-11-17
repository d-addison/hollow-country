# Tests

These Python standard-library checks exercise offline tooling and authored data.
They require no DayZ installation and do not establish gameplay, native CE,
multiplayer, performance or release acceptance.

Run from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v
```

Run a focused suite by adding a pattern, for example:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_ce_audit.py -v
```

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
| [Group UTC clock](unit/test_group_clock.py) | Actual authored calendar/sampling methods across midnight, invalid dates and rollback; signed epoch limits remain tracked. |
| [Group fixture runner](unit/test_group_native_checks.py) | Opt-in synthetic policy fixtures and failure/completion-marker behavior; native VM results are recorded separately. |
| [Stamina integration](unit/test_stamina_integration.py) | Disabled fallback, bounded settings, authority and inputs passed to the native stamina handler; no connected-client prediction or HUD proof. |
| [Stamina HUD](unit/test_stamina_hud.py) | Separate weight/stamina samples, native HUD-hide flags, reference bounds and lifecycle with synthetic widgets; no rendered viewport proof. |
| [Event director](unit/test_event_director.py) | Bounded opt-in participation, server observations, replay/transition limits and blocked unimplemented rewards; no live mission or AI delivery. |
| [Item manifest reader](unit/test_item_compatibility_manifest.py) | Strict pinned contiguous export/coverage admission and hostile file controls; POSIX input opening fails closed on unsupported platforms. |
| [Fuel action](unit/test_siphon_fuel_action.py) | Server authority, leases, one-shot diagnostic debit/credit and mismatch refusal with synthetic native collaborators; no durable native fluid transaction proof. |
| [Infected death probe](unit/test_infected_death_probe.py) | Five-case mission preparation, result correlation, observed cleanup and timeout refusal; no rendered ragdoll or loot/replication acceptance. |
| [Automation planning](unit/test_automation.py) | Portable criteria, explicit capabilities and planning-only status; no gameplay execution or automatic acceptance. |
| [Benchmark comparison](unit/test_benchmark.py) | Synthetic repeated pairs, compatible contexts, explicit budgets and incomplete evidence. |
| [Evidence admission](unit/test_evidence.py) | Manifest requirements, artifact hashes/paths and unsupported capability promotions. |
| [BDD bindings](unit/test_bdd_bindings.py) | Exact scenario/step admission and rejection of unsupported or missing assertions. |
| [Runtime settings](unit/test_runtime_settings.py) | Operator JSON flags, limits and feature dependencies; no native serializer claim. |
| [Crafting contracts](unit/test_crafting_contract.py) | Salvage material ledger and native recipe source contracts; no transaction/crash proof. |
| [Interiors contracts](unit/test_interiors_contract.py) | Restricted scalar authored policies and source invariants; no native placement/transaction proof. |
| [Infected contracts](unit/test_infected_contract.py) | Restricted scalar authored policies, finite budgets and source invariants; no AI/audio/runtime proof. |
| [Package behavior](unit/test_package.py) | Deterministic containers, path/allowlist validation and signature command contracts; no native signature acceptance. |
| [Economy contracts](unit/test_economy_contract.py) | Synthetic profile/delta generation, isolated install and rollback; no effective CE merge/eligibility proof. |
| [CE candidates](unit/test_coverage_patch.py) | Hash-pinned synthetic geometry exports, minimal changes, encoding and point validation. |
| [Deployment](unit/test_deploy.py) | Real disposable filesystem transactions, process interruption, upgrade, recovery, drift refusal and byte-exact rollback; four executable deployment BDD scenarios. |
| [Crafting completion](unit/test_crafting_completion.py) | Actual authored admission and registry-audit methods with synthetic native objects. |
| [Infected completion](unit/test_infected_completion.py) | Bounded authored relay/recovery policies and wiring; no native audibility or population proof. |
| [Compiler probe](unit/test_wine_compile_probe.py) | Log classification, byte budgets and owned-process cleanup, including a real disposable surviving child. |
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
