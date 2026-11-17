# Hollow Country tools

Python utilities use the standard library. Run from the repository root with
Python 3.12; `-B` suppresses bytecode. Tools inspect authored inputs or supplied
evidence and do not establish completed gameplay.

| Tool | Purpose |
| :--- | :--- |
| [CE auditor](audit/README.md) | Bounded mission XML, source and coverage audit. |
| [Item utility cohorts](audit/item_utility.py) | Indexes every admitted item, recipe, action and repair-kit candidate without dropping ambiguous source identities; supplied metadata does not prove repair compatibility. |
| [Benchmark comparator](benchmark/README.md) | Paired measurements with explicit context and calibrated budgets. |
| [Package tools](package/README.md) | Source containers, CE candidates, signing helpers and install/recovery/rollback. |
| [Runtime settings validator](validate/runtime.py) | Operator flags, limits and dependencies. |
| [Evidence validator](validate/evidence.py) | Capability manifest and artifact admission; see `--help`. |
| [Repository hygiene](validate/hygiene.py) | Bounded content, rights-notice and documentation-link checks. |
| [BDD runner](validate/bdd.py) | Executes explicitly bound offline behavioral suites. |
| [Diagnostic mission preparation](setup/diagnostic_mission.py) | Creates a fresh isolated mission for narrow native storage probes. |
| [Wine compiler probe](setup/wine_compile_probe.py) | Bounded local engine experiment with retained errors and owned-process cleanup; explicit external paths required. |
| [Actor-free startup control](setup/native_startup_runner.py) | Compares fixed stock-CE and CE-disabled startup modes with correlated lifecycle and real callback receipts; requires explicit execution and isolated paths. |
| [House measurement preparation](setup/interior_measurement_probe.py) | Prepares a fixed CE-disabled bundle to observe existing houses and checks correlated native returns; no launch, placement, room-fit or CE-eligibility approval. |
| [Process observations](setup/process_observation.py) | Read-only bounded Linux counter and log-metadata sampling for an explicitly owned PID; unavailable data stays explicit. Callers retain startup deadlines and cleanup. |
| [Fuel fixture runner](setup/fuel_probe_runner.py) | Fixed owned-entity diagnostic observation, conservation/replay receipt admission and bounded process cleanup; no autonomous player or durable transaction claim. |
| [Death fixture preparation](setup/infected_death_probe.py) | Prepares five fixed infected-death observations and checks bounded correlated receipts; launch through the compiler probe. |
| [Stamina transport controls](setup/stamina_transport_probe.py) | Inspects pinned configuration interfaces and prepares isolated controls; no connected-client synchronization claim. |
| [Native actor adapter](testing/native_autotest.py) | Prepares disposable diagnostic harness/direct-actor missions and checks result structure; no client control or gameplay acceptance claim. |

```sh
python3 -B -m tools.validate.runtime
python3 -B -m tools.validate.hygiene
python3 -B -m tools.validate.bdd
python3 -B -m tools.audit.ce_audit --help
python3 -B -m tools.benchmark.compare --help
```

Set `DAYZ_SERVER_MISSION` to a local mission snapshot before auditing:

```sh
python3 -B -m tools.audit.ce_audit --mission "$DAYZ_SERVER_MISSION"
```

Raw XML points are not observed engine eligibility. Benchmark comparison remains
incomplete without comparable repeated runs, verified context and an explicit
calibrated budget. Evidence validation checks supplied declarations and artifacts;
it cannot authenticate observations or convert offline results into acceptance.

Keep game installations, extracted native interfaces, machine inventories,
profiles, experiment outputs and planning records outside versioned deliverables.
The setup helpers use disposable external destinations; a forced stop is not a
persistence test. See [tests](../tests/README.md) for regression commands.

Startup controls add no actors. The `ce-disabled-control` mode omits only the
stock `ce.InitOffline()` call, retaining explicit mode attribution in evidence.
Its success does not establish ordinary CE startup or gameplay. Both modes need
real balanced SYSTEM update/queue observations; initialization alone cannot pass.
The explicit `--without-addon-control` flag omits only `-mod`, retaining the
staged PBO's validation and hashes. Reports identify that omission separately
from the stock-CE/CE-disabled mode; the default still requests the addon.

The startup runner keeps its 90-second default. An explicit `--startup-seconds`
option admits at most 600 seconds for startup, with an explicit total budget of
at most 674 seconds covering a separate 60-second fixture and 12-second cleanup.
No timeout automatically increases those allowances. Startup and fuel report
consumers must use their runner's `read_report()` and require that run's zero
exit code; a `.pending` sibling means publication is incomplete.
