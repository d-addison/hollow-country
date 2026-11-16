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
