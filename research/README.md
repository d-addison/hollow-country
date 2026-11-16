# Research and recorded observations

This directory holds source research, installation inventory and bounded
experiment results. Each record states its evidence layer and remaining gates.
The [active specification](../docs/specs/001-survival-overhaul/spec.md) governs
requirements; none of these offline records establishes completed gameplay.

| Record | What it establishes |
| --- | --- |
| [Native setup dry run](P0-native-setup-dry-run.md) | User-observed installed-file WhatIf success after the hash fix, native synthetic CI and remaining runtime gate. |
| [Verification record](VALIDATION-2026-11-16.md) | Executed offline checks, review fixes and pending native gates. |
| [P0 build inventory](P0-build-inventory.md) | Observed installation/build/tool details; runtime checks remain pending. |
| [Official CE source research](official-sources-2026-11-16.md) | Pinned upstream revision, documented interfaces, license/source references and file hashes. |
| [Installed CE experiment](experiments/EXP-CE-offline-audit.md) | Read-only installed-file comparison, raw XML findings, regressions and unresolved alias concerns. |
| [Installed CE audit JSON](evidence/installed-ce-audit.json) | Machine-readable raw counts, diagnostics and mission-relative input hash provenance. |
| [Native execution](experiments/EXP-native-access-completion.md) | Actual official signing tools and DayZ compiler/core self-test/initialization under Wine; Windows and client gates remain separate. |
| [Completion review](experiments/EXP-completion-review.md) | Independent findings, reproductions and resolutions for current source work. |
| [Deployment completion](experiments/EXP-deployment-completion.md) | Transactional install/recovery/rollback tests and input-bound review corrections. |
| [Coverage preparation](experiments/EXP-coverage-completion.md) | Pinned export candidate authoring, synthetic regressions and missing real geometry. |

The installed CE experiment records matching hashes for six compared source
files; the auditor processes four of them. Its unresolved possible aliases are
retained, and raw point counts do not establish eligible loot or verified
building classnames. Consult the record for exact observation time and limits.

To inspect an explicit mission snapshot again, set `DAYZ_SERVER_MISSION` to the
local mission directory and run from the repository root:

```sh
python3 -B -m tools.audit.ce_audit --mission "$DAYZ_SERVER_MISSION"
```

This prints JSON and reads the mission without editing it. Exit 1 means audit
diagnostics contain errors; the recorded installed snapshot retains unresolved
aliases. See [audit usage](../tools/audit/README.md) and the experiment for scope.

[build-planning-artifacts.py](build-planning-artifacts.py) regenerates planning
artifacts; it is a maintainer tool, not a CE experiment or an acceptance test.
Record new observations with exact source/build identity, reproducible commands,
hashes, outcomes and unmet gates. Keep vanilla XML, assets, profiles, signing
keys and full game dumps outside Git. Use [test instructions](../tests/README.md)
to distinguish synthetic tooling checks from runtime evidence.
