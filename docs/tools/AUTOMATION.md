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
| BDD bindings | `tools/validate/bdd.py`, `tests/features/*.feature` | `python3 -B -m tools.validate.bdd` binds the offline scenarios to unit-test files and fails closed on any changed name or step. `--runtime` checks the manual runtime protocol bindings; every runtime scenario stays BLOCKED. The 001 checks do not look at the 002 graph and print `002 graph: NOT CHECKED`. Bindings whose test file is no longer in the tree make the offline run fail with `No behavior tests for ...`; the integrity check lists them as `unexecutable_bindings`. |
| Artifact store | `tools/testing/artifacts.py` | One fresh, write-once evidence root per run; every attempt in its own directory with a hash chain, so a failed retry cannot be replaced. Credential material is redacted or refused. Strict admission goes through `tools.validate.evidence.validate_strict`. |
| Coverage report | `python3 -B -m tools.testing.automation coverage <run-dir> <manifest>` | Lists every catalogue row with outcome, per-mode result, explicit acceptance state (always not accepted), human-review state and the concrete blocker with its next step. Reconciles ids exactly. |
| Integrity check | `python3 -B -m tools.validate.automation_drift` | Checks that the catalogue rows and ids, the feature-file tags, the BDD bindings, the driver registry and the capability inventory agree. An unknown or missing id is an error. |

## Registered drivers

`offline.*` drivers wrap existing repository validators. The `native.*` drivers are thin
registered wrappers over existing release tools (compile gate, attach-only boot check,
diagnostic session plan). Each one is refused unless it is named with `--trust`, and each
needs a capability the discovery report must list as available. The registry in
`tools/testing/drivers.py` is the source of truth; `deferred.task` is a recorded placeholder
that is never runnable.

## What does not exist yet

- No native adapter from AV-T007 onward (orchestration and fault control, geometry and data
  observation, client access, audio and performance capture) is implemented or registered.
  The documents above do not describe them as working, and the lane below reports them as
  blocked or not run.
- AV-T017, AV-T018, AV-T019 and AV-T022 (two licensed clients, network faults, audio
  judgement, six- and ninety-player load qualification) are deferred by the owner on
  2026-11-22 and stay NOTRUN with reason `deferred_owner_2026-11-22`.
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
could be started by the owner. Deferred tasks are reported NOTRUN. The lane never reports
PASS: a PASS exists only inside a sealed run of a trusted driver.

Rules the lane states and the native tools enforce:

- Native runs happen only on the owner's host, never in hosted CI. The lane refuses
  (exit 1) when `GITHUB_ACTIONS` or `CI` is true.
- One native run at a time; each native tool takes the shared host lock itself.
- A native run needs the capability report to list its capabilities as available, an
  explicit `--trust <driver id>` and an owner who is not playing on that host.
- The lead runs native gates serially after a merge; offline workers never start DayZ,
  DayZDiag or Workbench.
