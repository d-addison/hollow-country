# Automated validation tooling

This page describes what exists today in the autonomous validation framework (spec 002).
It is offline tooling. An automated result ranks below the owner's one-client smoke and
never proves multiplayer. A framework PASS supports a catalogue row; it never accepts an
original test, a feature or a release. No native adapter beyond the thin registered
wrappers listed below exists yet.

## What exists

| Part | Where | What it does |
| --- | --- | --- |
| Catalogue | `tests/catalog.json` | One row per original criterion plus program and phase-2 extension rows, each with its required capabilities, assertions and evidence requirements. Every assertion is unresolved until a qualified observation exists. |
| Capability inventory | `tests/capabilities.json`, `tools/testing/discovery.py` | Read-only discovery from repository seams and, with `--machine`, file presence of installed tools. Present never means working: a capability is `available`, `blocked` or `unknown`. Two-client, audio and load capabilities stay `unknown` (owner decision 2026-11-22). |
| Planner | `python3 -B -m tools.testing.automation tests/catalog.json` | Plans every row against the supplied capabilities and executes nothing. |
| Runner and driver registry | `python3 -B -m tools.testing.automation run <manifest> <new-output-dir>`, `tools/testing/drivers.py` | Runs only drivers resolved from the trusted registry. A manifest names driver ids and validated inputs; argv, cwd and environment are built in code and nothing runs through a shell. Offline drivers are builtin; a native driver runs only when named with `--trust`. Outcomes are PASS, FAIL, BLOCKED or NOTRUN; a zero exit without a terminal result is FAIL. |
| BDD bindings | `tools/validate/bdd.py`, `tests/features/*.feature` | `python3 -B -m tools.validate.bdd` binds the offline scenarios to unit-test files and fails closed on any changed name or step. `--runtime` checks the manual runtime protocol bindings; every runtime scenario stays BLOCKED. The 001 checks do not look at the 002 graph and print `002 graph: NOT CHECKED`. A binding whose test file is in no bound tier (`tests/unit`, `tests/slow`) makes the offline run fail with `No behavior tests for ...` and is an error in the integrity check (`unexecutable_bindings` must stay empty). Scenarios retired because their suite only translated Enforce source are listed, dated, at the foot of the offline feature file under `tests/features`. |
| Artifact store | `tools/testing/artifacts.py` | One fresh, write-once evidence root per run; every attempt in its own directory with a hash chain, so a failed retry cannot be replaced. Credential material is redacted or refused. Strict admission goes through `tools.validate.evidence.validate_strict`. |
| Coverage report | `python3 -B -m tools.testing.automation coverage <run-dir> <manifest>` | Lists every catalogue row with outcome, per-mode result, explicit acceptance state (always not accepted), human-review state and the concrete blocker with its next step. Reconciles ids exactly. The subcommand reads the run's capabilities only from a sealed `report.json` (its store validated, same run, store hash equal to the manifest on disk) and refuses any other report with a reason. The post-run hook never blocks `report.json`: a failure there is recorded as `coverage_error` in the report. |
| Integrity check | `python3 -B -m tools.validate.automation_drift` | Checks that the catalogue rows and ids, the feature-file tags, the BDD bindings, the driver registry and the capability inventory agree. An unknown or missing id is an error. |

## Registered drivers

`offline.*` drivers wrap existing repository validators. The `native.*` drivers are thin
registered wrappers over existing release tools (compile gate, attach-only boot check,
diagnostic session plan). Each one is refused unless it is named with `--trust`, and each
needs a capability the discovery report must list as available. The registry in
`tools/testing/drivers.py` is the source of truth; `deferred.task` is a recorded placeholder
that is never runnable.

## Native server and probe adapters (AV-T007, AV-T008)

`tools/testing/native_server.py` and `tools/testing/native_probe.py` add verdicts on top of
the existing launch tools; they do not launch anything themselves. Both register as native
drivers (`native.server_adapter`, `native.probe_adapter`, `native.probe_settings`), so
`automation lane` lists them as NOTRUN or BLOCKED and `automation run --trust <id>` can run
them on the owner's host. Shared bounded observation helpers (log freshness, process
ownership, socket parsing, confinement and file guards) live in `tools/testing/native_common.py`.

| Adapter | Wraps | Positive checker (all required) | Never claims |
| --- | --- | --- | --- |
| Server, `wine` provider | `tools.release.compile_gate` as one owned child, plus `tools.package.sign_wine` | The PBO hash computed before launch equals the hash the gate and the compiler report name; the signing report is bound to that PBO and re-hashed; logs are newer than the launch; Mission loaded; zero script and engine errors; an exact loopback socket owned by the child tree; no owned process and a free port after exit; the stock server files unchanged. | A client, a signature-enforced join (AV-T015, AV-T017), acceptance. |
| Server, `windows` provider (contract and judge; evidence is assembled by `windows_evidence` from an existing `checkstart` output, no launcher) | attach-only boot verdict | Pin, boot verdict `connect_enabled`, RPT proven newer than a stated start time, stock files unchanged. | Process or socket ownership, cleanup: these are unobservable here and listed as unobserved. |
| Probe, `core-selftests` | `wine_compile_probe --diagnostic --diagnostic-selftests` | Every requested subcase prints its own `[HC SelfTest] name=<subcase> pass=true` marker; default request is every name the source can print; a missing, failed or conflicting marker is a rejection; any SCRIPT (E) or engine error fails the run and stays listed; test hook identifiers are absent from the normal PBO bytes. | That the Diag build equals the normal server: every verdict lists the differences. |
| Probe, `settings-negatives` | `wine_compile_probe --settings-case <case>` | One boot per case; PASS only for the specified rejection plus original-file preservation. | Anything beyond rejection and preservation. |

Evidence is `zero-client-native` (server) or `diagnostic-native` (probe), client count 0, and
`not_accepted`. A verdict ends with one JSON line; the driver judge reads that line and
refuses a record that claims a client. Native runs take the shared host lock, refuse hosted
CI and an owner client that is running, and write only inside a fresh output directory.

```sh
python3 -B -m tools.testing.native_server plan          # providers, checks, controls; launches nothing
python3 -B -m tools.testing.native_server judge evidence.json
agent-run --memory 12G -- python3 -B -m tools.testing.native_server run --provider wine --tree .
agent-run --memory 12G -- python3 -B -m tools.testing.native_server control wrong_pin --tree .
python3 -B -m tools.testing.native_probe plan
agent-run --memory 12G -- python3 -B -m tools.testing.native_probe run --probe core-selftests --tree .
agent-run --memory 12G -- python3 -B -m tools.testing.native_probe control missing_subcase --tree .
```

The unit tests for both adapters are offline and synthetic (fake launcher, fake process and
socket tables); they prove the checks reject the specified bad cases and never establish DayZ
behaviour. A control exits 0 only when the specified rejection is observed.

## What does not exist yet

- No native adapter from AV-T009 onward (orchestration and fault control, geometry and data
  observation, client access, audio and performance capture) is implemented or registered.
  The documents above do not describe them as working, and the lane below reports them as
  blocked or not run. The server and probe adapters (AV-T007, AV-T008) are written and
  registered, but their native behaviour has not been run yet (see the next section).
- AV-T017, AV-T018, AV-T019 and AV-T022 (two licensed clients, network faults, audio
  judgement, six- and ninety-player load qualification) are in scope (owner, 2026-11-22) but
  not built yet; they stay NOTRUN with reason `in_scope_not_built`.
- No capability observes gameplay, so no catalogue row can pass a gameplay submethod today.

## Offline CI lane

The `Source and tooling validation` workflow (`.github/workflows/static.yml`) runs on
`push`, `pull_request` and manual dispatch with read-only contents access and no secrets.
Its automation job uses only the Python standard library: it runs the integrity check and
the unit tests of the bindings, runner, artifact store and coverage report. It downloads
no game file, Workshop content, credential or key and starts no native tool.

## Local native lane

```sh
python3 -B -m tools.testing.automation lane            # repository-only discovery
python3 -B -m tools.testing.automation lane --machine  # plus installed-tool file presence
```

The lane prints one bounded JSON report and launches nothing. For each registered native
driver it reports BLOCKED when a needed capability is not available, or NOTRUN when it
could be started by the owner. Tasks that are not built yet (the `deferred.task` placeholder) are reported NOTRUN. The lane never reports
PASS: a PASS exists only inside a sealed run of a trusted driver.

Rules the lane states and the native tools enforce:

- Native runs happen only on the owner's host, never in hosted CI. The lane refuses
  (exit 1) when `GITHUB_ACTIONS` or `CI` is true, and `automation run --trust` refuses the
  same way (exit 1, nothing read or run) before it looks at the manifest.
- One native run at a time; each native tool takes the shared host lock itself.
- A native run needs the capability report to list its capabilities as available, an
  explicit `--trust <driver id>` and an owner who is not playing on that host.
- The lead runs native gates serially after a merge; offline workers never start DayZ,
  DayZDiag or Workbench.
