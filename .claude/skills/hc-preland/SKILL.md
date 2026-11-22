---
name: hc-preland
description: Pick and run the right Hollow Country pre-land checks for a diff. Use before reporting a worker task done or before landing a merge.
---

# Checks for a diff

Rules and exact flags live in `AGENTS.md`. Run every check under `agent-run --memory 2G` with a 900 s timeout;
exit 137 means out of memory, wait a few minutes and retry once, never raise the cap. Never run DayZ, DayZDiag,
Workbench or the native compile gate in a worker.

| Changed | Run |
|---|---|
| `mods/**/*.c` | `python3 -B -m tools.validate.enforce_lint --native-scripts <native scripts cache>` (new=0) and `python3 -B -m tools.validate.enforce_perf --strict-baseline` (new=0) |
| Python under `tools/` | `python3 -B -m unittest <module>` for each changed file only, then `python3 -B -m tools.validate.hygiene` ("valid": true) |
| Rule messages, or comments citing a build or issue in `mods/**/*.c` | `python3 -B -m tools.validate.pitfall_cards` regenerates `docs/pitfalls`; `--check` must pass |
| A worker brief | `python3 -B -m tools.validate.brief_lint <brief.md>` |
| Layout, imageset, texture or icon | the texture check must resolve every path; the lead does the one-client open check |

Lead only, after merge: `python3 -B -m tools.validate.preland --native-scripts <native scripts cache>` (full run;
workers use `--changed origin/main`), then for any `.c` change
`agent-run --memory 12G -- python3 -B -m tools.release.compile_gate --tree .`, which must reach the Mission
marker and is never run while the owner is playing.

Do not edit baseline JSON except to remove stale rows with the tool's own ratchet. Report the exact commands
and their one-line results. A skipped or "not available" check is a failure, not a pass.
