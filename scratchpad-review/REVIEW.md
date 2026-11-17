Verdict: **BLOCK** for `68b85e7429fa61b15a6aed442cd17bc491b5fab2`, parent `66892b4`, on `hc/weather-review-3`.

The original four reproductions now pass, and all 13 previously supplied mutations are killed. However, the new progression gate still produces a positive result from a canceled deadline. Treatment accounting also hides `current` changes, and the committed tests do not enforce the new readback quantifiers against mixed observations. These are source/offline findings, not DayZ observations.

Only `git show HEAD` / its three-file diff was reviewed for new findings. The unchanged probe was read to verify getter/clock claims; its SHA-256 equals its parent's: `2b3bfe1d64d4e0068e9f9c0437c482136f34ec69c0fd4743efc62b65801ddca4`. All writes, archived-source mutations, temporary fixtures and reports are under `scratchpad-review/`. No git metadata writes, DayZ, Wine, PowerShell, /mnt/d access, source edits outside scratch, commits, pushes or native acceptance were performed. The running native pair's results were not supplied or examined.

`AGENTS.md`, the task brief, the runtime implementation contract and Banso CLI guidance were read. `docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md` are absent in this checkout; `cat` reported “No such file or directory.” No lifecycle/panel command was run in this confined reviewer task. The requested normal-server/DayZDiag and client acceptance remain pending.

Ranked findings:

1. **P1 — A deadline canceled before its crossing still unlocks positive evidence.** `tools/audit/weather_report.py:487` (crossing at 481, positive cycle at 485–486). Give an otherwise valid, matched-provenance candidate six samples at weather times `0,30,60,90,120,150`; its deadline is `100` only at time 0, then `1000` at every subsequent sample. Its forecast stays `.9`; actual merely interpolates `.81..86`; live limits match the candidate. No sample reaches the replacement deadline, and neither deadline nor forecast changes at/after time 100. The code retains the minimum deadline, so it crosses obsolete 100 at time 120 and treats the already-present 1000 as a newly observed reschedule. Actual output: `complete / observed_limit_compliance`, `boundary_crossed.candidate=true`, `cycle_observed.candidate=true`. This defeats the new safety gate without requiring a probe defect. Minimal fix: track the active observed deadline, replace/invalidate it when it changes before crossing, and credit a post-crossing reschedule only relative to the deadline/forecast actually active immediately before that crossing. Add the canceled/postponed-deadline decision-table case and full comparison regression. See `round3_cases.py:23`, `round3-cases.log`.

2. **P2 — `current`-only treatments disappear, including in a complete mixed comparison.** `tools/audit/weather_report.py:588`, `:691`, `:702`, `:735` (the new `xml` summary at 428 also excludes `current`). The parser reads current values, but treatment detection only retains the three limit pairs. Change fog `current(actual,time,duration)` to `(.75,30,30)` while keeping its limit pairs unchanged. By itself this yields `pending`, `treated=[]`, fog `not_treated`, and “there is no treatment to compare.” Add an overcast limit treatment and it yields `complete`, `treated=['overcast']`, fog still `not_treated`, no issues. Thus the mixed result silently excludes a changed phenomenon, while the notes call it a phenomenon the candidate “does not change.” Minimal fix: retain/report current differences separately. Until initialization effects have their own supported experiment, label them explicitly unsupported/pending rather than unchanged; alternatively make the scope explicitly `not_limit_treated` and expose incomplete current-treatment coverage, so a complete *limit-only* comparison cannot be mistaken for coverage of the whole candidate. Do not assume a later sample must equal an initial current value. Two failing regressions are in `round3_cases.py:35` and `:42`. The supplied native candidate changes fog/overcast limits as well, so those two are detected; this finding does not claim the current run is omitted in its entirety.

3. **P2 — The committed tests allow weakening both critical readback quantifiers.** `tests/unit/test_weather_report.py:563`, `:576`, `:586`; protected production statements are `weather_report.py:601–602`. The positive and negative fixtures use homogeneous readbacks. Change candidate `all(...)` to `any(...)`: all **127** committed weather tests pass. Change stock `not any(...)` to `not all(...)`: all **127** pass again. These mutants permit a positive label with one stale candidate reading, or with one stock reading already equal to the candidate. Current production code handles both correctly; this is a demonstrated regression-coverage defect, not a claim that HEAD already uses the wrong quantifiers. Minimal fix: add one mixed-candidate and one mixed-stock behavioral comparison. The supplemental `ReadbackQuantifiers` tests pass on HEAD and fail on the corresponding mutants. See `round3-mutations.log`, `quantifier-checks.log`, and `round3_cases.py:50`.

Closure of the four ranked findings from hc-weather-review-002:

| Previous finding | Status | Rerun evidence |
|---|---|---|
| 1. In-range values incorrectly imply applied candidate limits | **FIXED** for its reproduction | Conflicting live `0..1` readings and candidate values `.86..91` now give `complete / limits_not_observed_applied`, with separate `values_in_range` and forecast-outside data. Application inference is no longer made from the range alone. Native nonapplication interpretation is discussed below. |
| 2. Unrelated/inert phenomena gate the targeted pair | **FIXED** for its reproductions | Unchanged zero snowfall is `not_treated`; the targeted overcast pair is complete. The synthetic 24-minute fog/wind schedules likewise return `complete []`. New finding 2 concerns a different, changed-current treatment. |
| 3. Merely passing a deadline counts as recomputation | **PARTIAL** | Original unchanged-deadline/interpolation case now returns `pending / pending`, boundary true but cycle false. Zero/expired deadlines are rejected. The canceled-deadline counterexample in new finding 1 remains falsely positive. |
| 4. Weather-clock, future-deadline and admitted-digest mutations survive | **FIXED** for all three named mutations | N1, N4 and N5 now exit 1 with 1, 4 and 2 test failures respectively. All other M1–M8 / N2–N3 remain killed. New finding 3 concerns additional mixed-readback mutants. |

The older admission/provenance/parser/registry/aggregate checks also remain green: `review_cases.py` passes **13/13** unchanged from the adapted prior-review script. Some very old comparison cases intentionally omit plans and are blocked by provenance too; `new_cases.py` and `round3_cases.py` use full matching plans to avoid that masking.

On the requested inference questions:

- **Stock-cycle relaxation:** sound for the explicitly limited descriptive comparison of sampled values and live limits; **not sound for a precedence claim**. A static stock run with actual `.3`, forecast `.3`, and deadline 1000 yields `complete / observed_limit_compliance` against a cycling candidate, with `cycle_observed={'stock':False,'candidate':True}`. That control does not demonstrate what the stock controller would select after its next cycle. Restoring its cycle would strengthen the control but would still not prove exclusive precedence from two random traces. The module now expressly disclaims precedence, leaves `runtime_acceptance=pending`, and allows engine limits/world forecasts to coexist. Preserve that scope; require a usable control cycle or direct controller evidence if later promoting this to a controller-precedence conclusion. No stock-cycle requirement is needed merely to compare live GetLimits readings.

- **`limits_not_observed_applied` as complete:** safe only as “the observation files were processed and the strict differential criterion was not met.” **It does not establish the native fact that XML limits were ignored.** A single early `0..1` reading followed by five correct `.8..95` readings gives `complete / limits_not_observed_applied` (single-run counts are `matching=5,total=6`). A synthetic time-limit readback of `30000..60000` against XML `30..60` gives the same complete label with no issues. A wrong getter could produce the same mismatch. These are explicit counterfactual fixtures, not evidence that those defects or delayed loading happened in DayZ. Source inspection shows the correct GetLimits/GetForecastChangeLimits/GetForecastTimeLimits mapping, and the clock test now kills the milliseconds substitution. Installed `3_Game/Weather.c:52,61,81,102,180` documents the requested getters and seconds, but cannot establish XML-load order or native output correctness. Preserve raw sequence/time/readback data; expose mismatch counts and an explicit unresolved native interpretation, especially for mixed early/late readings. If `complete` is intended to close #35 or declare native nonapplication, this case must instead be pending/inconclusive. I do not count the conservative descriptive label itself as a demonstrated extra production-code defect.

- **Current-only treatment:** yes, it is reported as `not_treated`; a wholly current-only candidate remains pending, whereas a mixed candidate can be complete while its current-only target disappears. Finding 2 gives the exact outputs and scope-safe fixes.

Commands and actual outputs (all Python stdlib, no native execution):

```text
mkdir -p scratchpad-review/baseline scratchpad-review/tmp
git show HEAD > scratchpad-review/head.diff
git archive HEAD | tar -x -C scratchpad-review/baseline
exit 0
```

The previous review's four scripts were copied into scratchpad-review. `mutate_new.py` alone was mechanically adapted to the renamed deadline variable/new `elif` branch for N4; its intended mutation is unchanged: remove the `next_change > time` guard. Original scripts in weather-review-2 were never modified. Review/new cases were otherwise unmodified.

From the archived commit (`scratchpad-review/baseline`), with `TMPDIR=/code/hc-worktrees/weather-review-3/scratchpad-review/tmp` and `PYTHONDONTWRITEBYTECODE=1`:

```text
python3 -m unittest discover -s tests/unit -p 'test_weather*.py' -v
Ran 127 tests in 0.861s
OK
exit 0

python3 -m unittest tests.unit.test_probe_runtime tests.unit.test_atmosphere -v
Ran 74 tests in 1.109s
OK
exit 0
```

From the worktree root, with the same environment:

```text
python3 scratchpad-review/review_cases.py
Ran 13 tests in 0.076s
OK
exit 0
four-sample comparison: pending pending
duplicate actual key: pending ["malformed JSON on line 2: duplicate JSON key 'actual'", ...]
overflow CLI: 3 <empty stderr>
repeated game_ms: pending ['game_ms does not increase between seq 0 and seq 1 (repeated or reversed timestamps)']

python3 scratchpad-review/new_cases.py
Ran 4 tests in 0.054s
OK
exit 0
unchanged deadline, interpolation only: pending pending boundary= True
boundary crossed + live limits 0..1 + forecast .3: complete limits_not_observed_applied live= {'matching': 0, 'total': 6} forecast_outside= 6
24 minute observation window: complete []
inert unchanged snowfall: complete overcast= observed_limit_compliance snowfall= not_treated []

python3 scratchpad-review/round3_cases.py
Ran 8 tests in 0.012s
FAILED (failures=3)
exit 1
canceled deadline: evidence=observed_limit_compliance, boundary_crossed.candidate=true, cycle_observed.candidate=true, status=complete
current only: pending treated=[] fog=not_treated issues=[... 'there is no treatment to compare']
mixed current + limits: complete treated=['overcast'] fog=not_treated issues=[]
one early mismatch, then 5 matches: complete limits_not_observed_applied counts={'matching': 5, 'total': 6}
hypothetical readback milliseconds: complete limits_not_observed_applied issues=[]
stock no cycle: complete observed_limit_compliance {'stock': False, 'candidate': True}
mixed candidate readbacks: limits_not_observed_applied
mixed stock readbacks: limits_not_observed_applied
```

Mutations each run the same committed 127-test discovery in a fresh Python process, altering only the archived copy, restoring in `finally`. Harness exit 0 means checks completed; each individual test-process exit is below. Logs and exact mutation diffs are retained.

```text
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/mutate.py
M1_disable_duration_check                     KILLED exit 1
M2_disable_existing_output_refusal             KILLED exit 1
M3_write_sentinel_before_end_record            KILLED exit 1
M4_swap_actual_and_forecast_getters            KILLED exit 1
M5_disable_watchdog_finish                     KILLED exit 1
M6_schedule_samples_without_interval          KILLED exit 1
M7_remove_duplicate_seq_guard                 KILLED exit 1
M8_ignore_sentinel                            KILLED exit 1

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/mutate_new.py
N1_weather_time_in_milliseconds               KILLED exit 1 (failures=1)
N2_swap_volfog_density_getters                KILLED exit 1
N3_remove_reconstruction                      KILLED exit 1
N4_drop_future_deadline_guard                 KILLED exit 1 (failures=4)
N5_reconstruction_pins_wrong_expected_hash     KILLED exit 1 (failures=2)

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/mutate_round3.py
R1_bypass_live_application                    KILLED exit 1
R2_ignore_stock_differential                  KILLED exit 1
R3_treat_every_attribute                      KILLED exit 1
R4_allow_no_treatment                         KILLED exit 1
R5_crossing_alone_is_cycle                    KILLED exit 1
R6_ignore_cycle_gate                          KILLED exit 1
R7_one_matching_candidate_readback            SURVIVED exit 0
R8_one_different_stock_readback               SURVIVED exit 0

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/quantifier_checks.py
{"version": "HEAD", "exit": 0}
{"version": "R7", "exit": 1}
{"version": "R8", "exit": 1}
```

This independently establishes **13/13 prior mutants killed** and **19 killed / 2 survived among 21 identified mutations**, rather than attesting to an unspecified worker set of 20. The worker's exact extra seven mutation definitions were not present in HEAD or the supplied previous-review scripts, so its specific “20 killed” count is unverified. New tests supply the missing quantifier checks without changing production source.

A final byte comparison against `git show HEAD:<path>` confirmed both the actual worktree and restored archived copies of weather_probe.py, weather_report.py and their two test files are unchanged. All failing behavioral tests remain review artifacts for the worker to fix; no implementation/green result for findings 1–2 is claimed. Native pair interpretation, XML/reset-load ordering, actual engine scheduling, normal-server/DayZDiag qualification and production enablement remain pending.
