Verdict: **BLOCK** for `77c274f95e91774ae7665f928f101feca39ba713` (rounds 3 and 4 against `68b85e7`). Review identity: hc-weather-review-004, gpt-6.1-sol.

The three ranked findings from hc-weather-review-003 are FIXED for their reproductions. The native pair reproduces the integrator's result, and all 21 prior mutation intents are killed. Round 4 introduces a new false-positive path: the initial-transition exemption can swallow an excursion **after the actual has already entered the limits**, even with positive current readback. There are also two reporting defects. No P0 found.

1. **P1 — The transition exemption can hide a post-entry limit violation.** `tools/audit/weather_report.py:503`, `:506`, `:548`. The window ends only at attainment of the *forecast*, or a scheduling event; it does not end when the actual first enters the allowed range. An explicitly synthetic overcast trace has limits `.8..95`, actuals `[.81,.4,.6,.75,.9,.9,.9,.9]`, forecast `.9`, countdowns `[100,70,40,10,100,70,40,10]`, with normal 30 s sampling and full matching provenance. It starts within limits, then exits them at seq 1–3. Actual output: `candidate_status=within_candidate`, `values_in_range=true`, `evidence=candidate_live_limits_read_back`, and all three excursions appear only under `initial_transition.outside_samples`. A second synthetic fog trace with `.7..8` limits, current `(.75,120,240)`, actuals `[.3,.4,.72,.1,.75,...]` and the matching 360 s countdown enters at seq 2, exits at seq 3, then reaches the target at 120 s. Output remains `complete`, `within_candidate`, with **all three** limits/time_limits/current attribute labels positive. Thus even current readback does not protect the exemption. This demonstrates a report error on observations, not an assertion that DayZ generated these traces.

   Minimal fix: exempt only a contiguous initial prefix outside the allowed limits, ending no later than the first in-range actual (and still ending at a scheduling change). If the first actual is in range, there is no out-of-range prefix to excuse. Preserve the existing no-ending-window safeguard, raw ranges and forecast checks. This preserves the real pair's initial out-of-range prefix while counting subsequent exits. Add both counterexamples as behavioral regressions. See `adversarial_cases.py:13` and `:24`, actual failures in `adversarial-cases.log`.

2. **P2 — `values_in_range` now claims the raw values were inside when they were not.** `tools/audit/weather_report.py:928`. It is derived from the status after excusing initialization, rather than the sampled values. This occurs on the **unmodified native pair**: fog has raw range `.0312421..8` against `.7..8` with 22 initial out-of-range samples; overcast has `.2877..99` against `.97..99` with 23. Both get `values_in_range=true`. The report retains the ranges and transition counts, so the evidence is recoverable, but its Boolean contradicts those observations and its note about values inside limits. The defect also reproduces with a wholly reasonable synthetic initial interpolation, independently of finding 1.

   Minimal fix: compute this Boolean from all raw actuals/range endpoints. If callers also need the adjusted assessment, expose an explicitly scoped `values_in_range_after_initial_transition` field. Clarify the scope of `within_candidate` wherever presented; it is not whole-run compliance. See `test_values_in_range_describes_the_raw_samples`, `adversarial-cases.log`, `real-pair-summary.log`.

3. **P2 — A known out-of-range forecast can be masked by the cycle gate.** `tools/audit/weather_report.py:798` (violation branch at `:803`). Use six otherwise usable candidate samples with in-range actual `.9`, out-of-range forecast `.99` against `.8..95`, and countdown `900,870,840,810,780,750`. Output: `evidence=pending`, reason “no forecast countdown ... ran out,” although `candidate_forecast_outside_limits=6`. The counts are retained and no positive label is issued; the defect is that the promised negative evidence label becomes an unmet-progression result. The same ordering masks already observed actual violations. A sampled violation does not require waiting for a forecast cycle.

   Minimal fix: after validating usable/enough samples, check actual/forecast violations before the boundary/cycle/change gates. Keep the progression diagnostics separately. Add a no-cycle out-of-range forecast case. See `test_forecast_outside_is_reported_even_without_a_cycle`, `adversarial-cases.log`.

Prior finding closure, with actual output:

| Prior finding | Status | Rerun output |
|---|---|---|
| 003-1: canceled deadline unlocks positive evidence | **FIXED** | `canceled deadline: evidence=pending, boundary_crossed.candidate=false, cycle_observed.candidate=false; status=pending`. Both original constant replacement and committed decreasing replacement cases pass. |
| 003-2: current-only treatments disappear | **FIXED** | `current only: complete treated=['fog'] fog=current_inconclusive issues=[]`; mixed case `complete treated=['overcast','fog'] fog=current_inconclusive issues=[]`. Current is assessed and visible; insufficient XML keys remain explicitly unsupported/pending. |
| 003-3: mixed readback quantifiers lack regression protection | **FIXED** | Both mixed cases yield `inconclusive_readback`. R7 now `KILLED exit=1 (failures=2)`; R8 `KILLED exit=1 (failures=1)` against the committed suite. |
| 002-1: range alone implies applied limits | **FIXED** | Conflicting live limits plus out-of-range forecast: `complete candidate_values_outside_limits`, live matching `0/6`, forecasts outside `6`. Mixed live readings with an otherwise valid forecast yield `complete inconclusive_readback`, matching `5/6`, rather than an application claim. |
| 002-2: unrelated/inert phenomena gate treatment | **FIXED** | `inert unchanged snowfall: complete overcast=candidate_live_limits_read_back snowfall=not_treated []`; countdown-adapted 24-minute case `complete []`. |
| 002-3: passing a deadline alone implies cycle | **FIXED** for its reproduction | `unchanged deadline, interpolation only: pending pending boundary=False`; committed decreasing-countdown-to-zero case reports boundary true, cycle false. New finding 1 is a different false-positive path. |
| 002-4: weather-clock, future-deadline and digest mutants survive | **FIXED** | N1/N4/N5 all `KILLED exit=1`, with 1/4/2 failures respectively. N4 necessarily targets the positive-countdown guard after the countdown-model change, rather than the deleted absolute-time guard. |

The prior scripts were first run verbatim. `review_cases.py` passed 13/13. `new_cases.py` failed 1/4 because its old 24-minute fixture wrote absolute deadlines; `round3_cases.py` failed 4/8 solely because it expected the replaced `limits_not_observed_applied` label. These are not concealed regressions: both original logs are retained. The review-only adapters change that obsolete label to `inconclusive_readback` and convert explicit synthetic absolute deadlines into remaining seconds; they change no assertions about canceled deadlines, treatment visibility or quantifiers. Adapted runs pass 4/4 and 8/8. Five mutation sites were mechanically relocated after refactoring; the exact resulting patches and `adapted` flags are retained. These results establish 21 named mutation intents killed, not an unspecified mutation total.

The transition endpoint checks themselves behave as specified: attainment of the first forecast ends the window; each forecast change, countdown exhaustion, and countdown rise ends it; the ending sample is assessed, not excused. The committed endpoint tests pass. Supplemental output for a forecast change at seq 3 is `outside_samples=[0,1,2]`, violations `[3,4,5]`. A window that never ends yields `samples=0, ended_by=None`, `violates_candidate`, six violations. Forecasts are never removed from the outside count, including inside a transition; however the evidence-label ordering has the limitation in finding 3. None of these endpoint tests rules out the post-entry excursion in finding 1.

I independently read the raw JSON-lines and XML using `independent_raw.py`, without importing the report or its fixtures. Both observation files match the archived cache copies byte for byte. The raw results are in `independent-raw.log`; the report's exact CLI JSON is in `real-pair.log`.

| Observation | Stock | Candidate |
|---|---|---|
| Samples / write errors | 241 / 0 | 241 / 0 |
| Sequences | contiguous 0–240 | contiguous 0–240 |
| mission_weather | false at every sample | true at every sample |
| update_frozen | false at every sample | false at every sample |
| XML enable / reset | 0 / 0 | 1 / 1 |
| Live fog limits / time limits, every sample from seq 0 | `0..1 / 300..3600` | `.7..8 / 30..60` |
| Live overcast limits / time limits, every sample from seq 0 | `0..1 / 300..3600` | `.97..99 / 30..60` |
| First fog / overcast forecasts | `0 / .221753` | `.75 / .98`, exactly candidate current.actual |
| Raw fog actual range | `0..00813179` | `.0312421..8` |
| Raw overcast actual range | `.0753319..221753` | `.2877..99` |

For candidate fog and overcast, seq 0 weather time is `5.30286`, countdown `354.986`; `120+240−5.30286=354.69714`, residual `+0.28886 s`. Across the initial unchanged-forecast segment the residual is about `−.545..+.39156 s`. Both targets are first sampled exactly at seq 23, weather time `120.253`; the preceding sample at `115.256` has fog `.719221` and overcast `.949907`. Thus convergence is sampled in `(115.256,120.253]`, not measured to subsecond precision. The first changed forecasts are sampled at seq 71, time `361.886`; fog has 10 detected forecast changes, overcast 7. **Every sampled forecast, initial and later, is in its candidate limits; every sampled actual from seq 23 onward is in them.** This is sampled evidence, not a claim about every intervening frame.

Both stock actual ranges are entirely outside the candidate's limits, and none of the stock live readings matches the candidate's treated limit/time-limit pairs. The stock first forecasts also differ from the candidate current.actual targets. These facts support the report's limited differential labels. Both stock fog and overcast show a forecast change in these files, so the stock-cycle relaxation is immaterial to this specific pair. Allowing a noncycling stock control remains sound only for descriptive readback comparison, not controller characterization or precedence. The synthetic no-stock-cycle reproduction remains `complete candidate_live_limits_read_back {'stock':False,'candidate':True}`, with acceptance pending and explicit non-claims. The candidate changes enable/reset, limits/time limits and current together, with only one run each: the pair does not isolate their separate causal effects.

The 1 s countdown tolerance and 10 s convergence slack are honest **as disclosed provisional matching bands**. They are explicit constants, emitted in `current_readback.tolerances` with `provisional=true`, and repeated in the non-claims. The first residual and convergence bracket are consistent with them. One pair does not calibrate scheduler timing or establish that convergence at, for example, 129 s is correct for time=120; the current rule would accept that as within its declared slack. The 10 s slack is broader than this pair's roughly 5 s sampling resolution requires. Preserve its provisional status; do not turn the result into an exact timing or native acceptance claim. The `candidate_current_read_back` label is explicitly defined as the three observed pattern checks plus the differing stock first forecast, not direct proof that XML caused them. That limited label is defensible. The Boolean in finding 2 is the demonstrated overclaim on the actual pair.

Malformed/duplicate robustness checks on in-memory copies of the native candidate remain conservative. Clean input gives `complete []`; a duplicate sample gives `pending ['duplicate sample seq 0 on line 3']`; a duplicate actual key, nonfinite `1e9999`, null record, and malformed phenomenon object all give pending with parse/structure issues. The two exponent strings present in the stock observations are `9.89125e-06` and `5.51835e-05`; the real stock run parses successfully. Direct numeric checks also accept `5.51835e-05`, `-1.2E+2`, `0e0` with their correct numeric values. No new P0–P2 parsing or stock-differential implementation issue was found in these checks. These checks are not exhaustive fuzzing.

Commands and actual outputs (full per-test output remains in the adjacent logs):

```text
git diff 68b85e7 77c274f -- tools/audit/weather_report.py tests/unit/test_weather_report.py tools/setup/weather_probe.py
git show 4dbe816 -- tools/audit/weather_report.py
git show 77c274f -- tools/audit/weather_report.py tests/unit/test_weather_report.py
exit 0; outputs saved as reviewed.diff, round3.diff, round4.diff

mkdir -p scratchpad-review/r4/baseline scratchpad-review/r4/tmp
git archive 77c274f tools tests mods | tar -x -C scratchpad-review/r4/baseline
exit 0
```

Python invocations used `PYTHONDONTWRITEBYTECODE=1`, `-B`, and `TMPDIR=/code/hc-worktrees/weather-review-3/scratchpad-review/r4/tmp`. The first two test commands ran from the archived `scratchpad-review/r4/baseline`; the others ran from the worktree root.

```text
python3 -B -m unittest discover -s tests/unit -p 'test_weather*.py' -v
Ran 169 tests in 0.947s
OK
exit 0

python3 -B -m unittest tests.unit.test_probe_runtime tests.unit.test_atmosphere -v
Ran 74 tests in 0.883s
OK
exit 0

python3 -B scratchpad-review/r4/review_cases.py
Ran 13 tests in 0.055s
OK
exit 0

python3 -B scratchpad-review/r4/new_cases.py
Ran 4 tests in 0.050s
FAILED (failures=1)
exit 1

python3 -B scratchpad-review/r4/round3_cases.py
Ran 8 tests in 0.015s
FAILED (failures=4)
exit 1

python3 -B scratchpad-review/r4/adapt_prior.py
Adapted only obsolete evidence label and explicit synthetic absolute deadlines to remaining seconds.
exit 0

python3 -B scratchpad-review/r4/new_cases_adapted.py
Ran 4 tests in 0.040s
OK
exit 0

python3 -B scratchpad-review/r4/round3_cases_adapted.py
Ran 8 tests in 0.017s
OK
exit 0

python3 -B scratchpad-review/r4/mutations_adapted.py
M1–M8: each KILLED exit=1
N1–N5: each KILLED exit=1
R1–R8: each KILLED exit=1
harness exit 0; exact JSON output in mutations.log / mutations.json

python3 -B scratchpad-review/r4/adversarial_cases.py
Ran 7 tests in 0.080s
FAILED (failures=4)
exit 1
The two excursion tests, raw-values Boolean test, and no-cycle negative-label test fail.
The nonending-window, scheduled-endpoint, and malformed/exponent guard tests pass.

python3 -B -m tools.audit.weather_report compare --stock /mnt/d/HollowCountryLocal/weather-probe-001-stock --candidate /mnt/d/HollowCountryLocal/weather-probe-001-candidate
exit 0
status=complete coverage=complete issues=[]
fog / overcast: candidate_status=within_candidate
limits / time_limits: candidate_live_limits_read_back
current: candidate_current_read_back
runtime_acceptance=pending feature_complete=false
full stdout: real-pair.log; extracted fields: real-pair-summary.log

python3 -B scratchpad-review/r4/independent_raw.py
exit 0; exact output: independent-raw.log
stock/candidate samples=241, write_errors=0, seq_contiguous=true, cache_matches=true
candidate fog/overcast: first_countdown_residual=.28886, reached=[23,"120.253",target]
candidate fog/overcast: forecasts_outside_count=0, actual_outside_after_target=[]
```

Initial native-reading harness execution encountered an unmatched closing parenthesis in this review's own script; it was corrected only under r4 and rerun successfully. No native evidence or production code was modified to obtain any result.

`AGENTS.md`, both Banso CLI/review skill texts, the runtime contract, the task brief, and the prior review were read. The task's explicit single-reviewer and write confinement override the generic panel/lifecycle workflow; no Banso lifecycle/panel command was run. `docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md` are absent; the read command actually returned “No such file or directory” for each. Installed `3_Game/Weather.c` was read locally to cross-check the getter comments; it is not copied into the review artifacts. The probe AST excluding its module docstring is identical to `68b85e7`.

All writes were confined to `scratchpad-review/r4/`, including archived-source mutation targets and temporary fixtures. The four production/test files inspected are byte-identical to `git show 77c274f:<path>`; the mutation archive was restored to the same bytes. `git diff --exit-code` returned 0 with empty output. `git status --porcelain=v1` shows only the pre-existing untracked `.banso-brief-004.md` and this review's `scratchpad-review/r4/`. See `integrity.log`. No git metadata writes, commits, index changes, DayZ, Wine, PowerShell or writes under `/mnt/d` were performed. Runtime acceptance and production enablement remain pending; no implementation or green fix for these new findings is claimed.
