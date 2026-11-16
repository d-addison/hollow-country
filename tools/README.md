# Offline tools and local setup

Python utilities use the standard library. Run the commands below from the
repository root; `-B` suppresses bytecode files. These utilities inspect authored
inputs or supplied evidence and do not establish completed gameplay.

| Tool | Purpose and details |
| --- | --- |
| [GitHub roadmap sync](project/sync_github.py) | Dry-run preview or explicit `--apply` to maintain all phase milestones/task issues; [policy and index](../docs/PROJECT_TRACKING.md). |
| [CE auditor](audit/ce_audit.py) | Bounded mission XML/source audit; [usage](audit/README.md), [installed findings](../research/experiments/EXP-CE-offline-audit.md). |
| [Benchmark comparator](benchmark/compare.py) | Repeated paired CSV summaries with explicit context/budget checks; [usage and manifest format](benchmark/README.md). |
| [Project validator](validate/project.py) | Planning mappings, acceptance coverage and task dependency integrity. |
| [Evidence validator](validate/evidence.py) | Version-1 capability manifest admission and artifact verification; `--help` documents its schema. |
| [BDD bindings](validate/bdd.py) | Execute the explicitly bound offline feature's behavioral suites. |
| [Windows runtime staging](setup/New-LocalVanillaRuntime.ps1) | Prepare a fresh external vanilla runtime using the [pinned installed inventory](setup/installed-vanilla-baseline.json); does not launch it. |

Planning and bound offline checks:

```sh
python3 -B -m tools.validate.project
python3 -B -m tools.validate.bdd
```

Set `DAYZ_SERVER_MISSION` to an explicit local mission snapshot to audit it:

```sh
python3 -B -m tools.audit.ce_audit --mission "$DAYZ_SERVER_MISSION"
```

The auditor prints JSON. Optional `--output FILE` saves it; its parent must exist.
`--known-types FILE` supplies a classname catalog. Raw XML points and alias hints
are not observed engine eligibility or classname confirmation. Other declared CE
file kinds are checked for presence/hash, with their schemas explicitly unaudited.

Replace the example paths with actual supplied evidence:

```sh
python3 -B -m tools.validate.evidence /path/to/evidence/manifest.json
python3 -B -m tools.benchmark.compare --baseline before.csv --candidate after.csv
```

The comparator remains `INCOMPLETE` without an explicit calibrated
`--max-regression-pct NUMBER`, verified sidecar context and repeated comparable
pairs. Object-count changes require `--allow-object-count-change` and are reported.
Evidence validation checks declarations and artifacts; it cannot authenticate
native observations or turn an offline result into runtime acceptance.

For Windows staging, inspect script parameters in native Windows PowerShell and
preview with `-WhatIf`. Staging targets a fresh directory outside the repository;
it neither launches a server nor proves join/reconnect, persistence or PBO load.
Installation paths and hashes are local inventory, not portable runtime proof.
Follow [local Windows setup](../docs/LOCAL_WINDOWS_SETUP.md), the [setup runbook](../docs/SETUP_AND_EXECUTION.md) and current
[inventory](../research/P0-build-inventory.md), then record actual unmet/observed
gates. See [tests](../tests/README.md) for regression and setup-static commands.
