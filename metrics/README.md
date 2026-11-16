# Measurement templates

Copy [benchmark-template.csv](benchmark-template.csv) or
[loot-evaluation-template.csv](loot-evaluation-template.csv) to an external
experiment directory. Templates contain headers only, never measurements.
Record exact build, commit, scenario, seed, player count and workload; pair
repeated baseline/candidate runs with matching hardware/mission/warmup context.

Follow [testing/performance](../docs/TESTING_PERFORMANCE.md) and the
[comparator format](../tools/benchmark/README.md). Proposed budgets require
calibration at the intended 3–6-player load. Synthetic fixtures under tests are
not runtime data. Commit sanitized summaries and artifact hashes, not profiles,
saves, player identifiers or full logs containing private data.
