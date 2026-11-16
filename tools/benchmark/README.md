# Offline paired benchmark comparator

Run from the repository root using Python 3 (standard library only):

```sh
python3 -m tools.benchmark.compare --baseline before.csv --candidate after.csv \
  --max-regression-pct 3 --output comparison.json
```

The threshold above is an example, not a recommended or calibrated DayZ target.
Supply a threshold only after calibration and approval for the intended hardware,
players and baseline. No threshold is inferred from the provisional targets in
`docs/TESTING_PERFORMANCE.md`.

JSON is printed to stdout; `--output` also writes the same report. Exit codes:
0 = PASS, 1 = FAIL, 2 = INCOMPLETE or INVALID (or an argparse usage error).
INVALID means malformed evidence or incomparable pairing. INCOMPLETE means an
aggregate gate cannot be accepted: threshold, verified manifest context or
repeated pairs are missing. It takes precedence over any descriptive metric
failures; those failures remain visible in the report.

## CSV validation and pairing

All columns from `metrics/benchmark-template.csv` must exist exactly once.
Additional named columns are allowed but do not affect pairing or verification.
Rows must have the header's field count. Identity fields must be nonempty;
notes may be empty. Numeric fields must be finite and nonnegative. Seed, players,
active populations/objects and errors must be integers. All frame-time/FPS
metrics must be strictly positive and errors must be zero on both sides.
Run IDs must be unique within a file; each file must describe one git commit.

Pairing is exact on scenario, seed, game build, player count, active infected,
hordes, interiors and objects. Git commits must **differ**, and run IDs need not
match across files. Rows can be reordered. Missing/extra pairs are INVALID,
never silently discarded. Identical pairing keys are ambiguous and rejected:
use a shared `pair_id` in each side's manifest to identify individual repeats.
Each side of every pair must supply the same pair_id when it is used.

`--allow-object-count-change` explicitly permits intentional changes to
`active_objects`; all other population fields must still match. Every changed
object count is listed in the report, and distinct before/after object-count
contexts have separate aggregates. If relaxing object matching makes pairing
ambiguous, use manifest pair_id values. The switch does not establish causation.

## Sidecar manifests

The CSV template has no hardware, mission, warmup or sample-duration columns.
By default the comparator reads `before.csv.manifest.json` and
`after.csv.manifest.json`. Override locations with `--baseline-manifest FILE`
and `--candidate-manifest FILE`. Each manifest has this structure (identifiers
below are placeholders, not game measurements):

```json
{
  "runs": {
    "run-001": {
      "hardware": "exact server AND client hardware/OS identity or content hash",
      "mission": "exact mission/map/economy/config identity or content hash",
      "warmup_seconds": 60,
      "sample_seconds": 120,
      "pair_id": "optional-shared-repeat-identifier"
    }
  }
}
```

Hardware and mission identifiers must be nonempty strings. Warmup must be
finite and nonnegative (zero denotes cold start); sample duration must be
finite and positive. These fields must match across each pair. Mixed warmup,
duration, hardware or mission contexts form separate aggregate groups.
Missing sidecars, missing run entries or missing fields are unverified and
prevent PASS. Explicitly requested missing files, malformed JSON, duplicate
JSON keys, invalid field values and mismatched contexts are INVALID. Extra run
entries are permitted so a manifest can cover an evidence archive/subset.

Manifest verification checks supplied declarations and equality. It cannot
verify hardware, warmup execution, provenance or actual measurements. Record the
other reproducibility details required by the testing plan (executables,
mod/PBO hashes, route, weather, logging settings, etc.) in the evidence archive;
this deliberately small manifest does not replace that plan.

## Aggregate rule and limits

Require at least two pairs per comparable scenario/context group. Seeds and
pair IDs identify repeats and are excluded from aggregate grouping; different
scenarios, builds, populations, objects and manifest contexts stay separate.
For each pair and metric:

- p95/p99 server frame ms regression = 100 * (candidate - baseline) / baseline.
- Client 1% low FPS regression = 100 * (baseline - candidate) / baseline.

Positive means worse. For each metric, the arithmetic mean of paired percentage
regressions must be at most the supplied threshold. This is **not** the percentage
change of aggregate means. The report includes each pair, baseline/candidate
means, minimum/maximum and sample standard deviation of paired percentages.
It does not pool quantiles, estimate a confidence interval, claim significance,
or gate unrequested metrics. Spikes remain visible in individual pair results
and spread; an aggregate gate can pass despite an individual outlier.

This is an offline evidence comparator. PASS only describes the supplied data
under the stated aggregate rule. It does not execute DayZ, prove native runtime
behavior or performance, authenticate evidence, or grant release acceptance.
The committed fixtures are synthetic unit-test inputs, not benchmark evidence.

## Tests and TDD capture

```sh
python3 -B -m unittest discover -s tests/unit -p test_benchmark.py -v
```

`tests/fixtures/benchmark/tdd-red.txt` records the failing run before the module
existed; `tdd-green.txt` records the final passing run. Tests use temporary files
inside `tests/fixtures/benchmark/` and do not require dependencies or game files.
