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
| [Benchmark comparison](unit/test_benchmark.py) | Synthetic repeated pairs, compatible contexts, explicit budgets and incomplete evidence. |
| [Evidence admission](unit/test_evidence.py) | Manifest requirements, artifact hashes/paths and unsupported capability promotions. |
| [Project contract](unit/test_project_contract.py) | Requirement/test mappings and task graph integrity. |
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
They are not executable offline acceptance. See the [testing plan](../docs/TESTING_PERFORMANCE.md)
for T0–T5 boundaries, repeated measurements and two-client requirements.

The [CE fixtures](fixtures/ce/README.md), [benchmark fixtures](fixtures/benchmark/)
and [evidence captures](fixtures/evidence/) are synthetic. Saved red/green logs
record historical runs; a fresh test run establishes the current suite result.
Tests create and clean temporary synthetic inputs, so execution requires write
access to their temporary locations, including fixture directories where used.

Setup-script static checks live outside `tests/unit`; run them separately:

```sh
python3 -B tools/setup/test_windows_setup_static.py
```

Those checks inspect authored PowerShell text and pinned inventory data. They do
not execute PowerShell or DayZ. See [tools](../tools/README.md) for utility usage.

Windows CI additionally executes deployment/coverage/package suites and actual
PowerShell verified-copy functions on synthetic bytes. Actual DayZ compilation
and lifecycle evidence is separate in
[the native execution experiment](../research/experiments/EXP-native-access-completion.md).
Wine runs of the official server do not establish native Windows/client behavior.
