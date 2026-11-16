# Measurement templates

Copy [benchmark-template.csv](benchmark-template.csv) or
[loot-evaluation-template.csv](loot-evaluation-template.csv) to an external
experiment directory. Templates contain headers only, never measurements.
Record exact build, commit, scenario, seed, player count and workload; pair
repeated baseline/candidate runs with matching hardware/mission/warmup context.

Follow the [comparator format](../tools/benchmark/README.md). Proposed budgets
require calibration at the workload being qualified. Synthetic fixtures are not
runtime data. Keep raw captures local; attach sanitized summaries and artifact
hashes to the tracking issue rather than committing profiles, saves or player data.
