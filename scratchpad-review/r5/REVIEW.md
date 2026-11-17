# hc-weather-review-005 — 099f96f

**Verdict: MERGE-WITH-FIXES.** All three r4 findings are **FIXED** for their reproductions. No remaining positive-evidence path with an assessed actual or any forecast outside the declared tolerance was found. One new P2 diagnostic error and one P3 emitted-description mismatch remain. Neither recreates the r4 false-positive blocker. No new P0/P1 finding.

## Ranked findings

1. **P2 — The new post-transition Boolean confuses insufficient evidence with an observed range failure.** `tools/audit/weather_report.py:940–941`. A valid three-sample candidate with actuals and forecasts all `.9`, against `.8..95`, has no exempt prefix and no actual violations. Actual output is:

   ```json
   {"candidate_status":"insufficient_samples","evidence":"pending","values_in_range":true,"values_in_range_after_initial_transition":false,"raw_actual_outside_limits":0,"initial_transition":{"samples":0,"ended_by":"actual_reached_initial_forecast","last_seq":null,"actual_outside_limits":0,"outside_samples":[]},"candidate_actual_range":{"min":0.9,"max":0.9}}
   ```

   The new field and the emitted note advertise a description of sampled actuals after the transition, but the field is derived from the sample-count verdict. Thus the same clean observations acquire a false range Boolean solely because there are fewer than six. The pair correctly remains pending; this is a contradictory diagnostic, not a positive-evidence bypass.

   **Minimal fix:** with the existing no-range/null guard, compute this field from `candidate["actual_violations"] == 0`, leaving minimum-sample gating in `candidate_status` and `evidence`. Alternatively emit null explicitly for insufficient samples and document that policy. Add short clean and short violating cases, keeping evidence pending in both. The first policy's failing behavioral reproduction is `supplemental.py:test_short_clean_run_does_not_claim_post_transition_actuals_outside`; output is in `supplemental.log`. No production fix was made.

2. **P3 — Every emitted report still describes the superseded exemption.** `tools/audit/weather_report.py:150–152` (`NON_CLAIMS`, emitted by both single and compare). It says out-of-range actuals before forecast attainment or a scheduled change are not violations, without the first-entry endpoint or earliest-end qualification. On the r4 fog trace `[.3,.4,.72,.1,.75,...]`, the code correctly ends the window at seq 2 and counts seq 3 as a violation. Seq 3 nevertheless precedes forecast attainment at seq 4, so this emitted sentence says it is excused. The module's main status/transition descriptions and the comparison notes have been corrected; the emitted prose is not consistent everywhere.

   **Minimal fix:** describe the prefix before the earliest of forecast attainment, first entry into limits, or first scheduled change; state that the ending sample is assessed and a nonending window is not excused. Update the emitted-description regression to check this shared text. `supplemental.py:test_emitted_transition_prose_matches_first_entry_rule` fails on the old text. This is a documentation correction, not an implementation blocker.

## R4 finding closure

| R4 finding | Status | Actual r5 output |
|---|---|---|
| P1: post-entry excursion hidden by transition | **FIXED** | Overcast starts `.81`, then `.4,.6,.75`: `candidate_values_outside_limits`, `violates_candidate`, window `samples=0`, `values_in_range=false`. Fog enters at seq 2, exits at seq 3: window `samples=2`, `actual_entered_limits`, `violates_candidate`, `attribute_evidence=null`; no positive label survives even though the current pattern matches. |
| P2: raw `values_in_range` follows excused status | **FIXED** | Synthetic initial interpolation: `values_in_range=false`, raw range `.3..9`. Native fog/overcast: raw outside counts `22/23`, raw Boolean false, scoped Boolean true. The short-run issue above concerns the newly added sibling field. |
| P2: cycle gate masks known violations | **FIXED** | Six `.99` forecasts against `.8..95` with a noncrossing countdown: `candidate_values_outside_limits`, forecast outside count `6`. Committed no-cycle actual-violation test passes too. |

All seven r4 adversarial tests pass unchanged after copying the script into r5 so its existing relative `baseline` path selects 099f96f. Nonending windows remain unexcused; the scheduled-change sample itself remains assessed; malformed/duplicate/nonfinite native-file copies stay pending.

The earlier r4 scripts were also rerun. `review_cases.py` passes 13/13. Verbatim `new_cases.py` fails 1/4 because of its obsolete synthetic absolute deadlines; verbatim `round3_cases.py` fails 4/8 because it expects the old `limits_not_observed_applied` name. The unchanged adapters already present in r4 pass 4/4 and 8/8. Both verbatim failure logs are retained; no new adaptation was needed.

## Positive-label and scope checks

Inspection confirms `_evidence` checks usable/enough samples, then assessed actual/whole-run forecast violations, before any positive-evidence return. The same guard protects current-only treatments, per-attribute labels and `supported_attribute_evidence`. Unsupported treatments and untreated phenomena introduce no alternate positive-label path. `complete` means processing completed, not compliance or runtime acceptance.

The independent synthetic oracle in `supplemental.py` checked 5,296 traces: all 4^6 actual sequences over `.3,.85,.9,.99` with a cycling in-range forecast, plus 1,200 seeded combinations of actuals, forecasts and six countdown patterns. It independently computes the earliest endpoint and checks all assessed actuals and every forecast, including the ending and last samples. Actual output: `traces=5296, positives=320, false_positives=0`. A further 56 current-only/mixed placements reject all 54 assessed violations and explicitly distinguish the two permitted initial out-of-range prefixes. These are finite synthetic checks, not exhaustive proof or DayZ evidence.

`within_candidate` is explicitly an actual-only status after the transition, with a boundary tolerance. It can coexist with an out-of-range forecast; the pair's evidence then becomes `candidate_values_outside_limits`. The main docstring and pair notes honestly scope it, and raw ranges/counts remain visible. Finding 2 is the remaining emitted scope-description defect.

## Two changed pre-existing fixtures

The assertions were preserved. Both edits remove an unrelated known violation so the tests still reach their intended pending/progression decision:

| Fixture | Original fixture on r5 | Changed fixture on r5 |
|---|---|---|
| `tests/unit/test_weather_report.py:470` — one pending treated phenomenon | Fog actual/forecast outside counts `6/6`; correctly `complete / candidate_values_outside_limits`. | Fog actual/forecast `.75`, countdown `1000`: outside counts `0/0`, boundary/cycle false; `pending`, reason `no forecast countdown (next_change) ran out in the candidate run`. The overcast-positive and whole-comparison-pending assertions remain. |
| `tests/unit/test_weather_report.py:530` — conflicting live limits without a boundary | Forecast `.3` outside `.8..95` six times; correctly `complete / candidate_values_outside_limits`. | Forecast `.9` is in range; conflicting live `0..1` and noncrossing countdown remain; result `pending` with the same no-boundary reason. `assert_not_established` is unchanged. |

These edits keep their original intent; they do not weaken a genuine negative-evidence assertion. New committed tests separately require negative evidence for actual and forecast violations without a cycle. The original/changed fixture outputs are retained in `supplemental.log`.

## Native evidence

The exact compare CLI returned rc 0, `status=complete`, `coverage=complete`, `issues=[]`. Fog has `samples=22, ended_by=actual_entered_limits`; overcast has `samples=23, ended_by=actual_reached_initial_forecast`. Both have `candidate_live_limits_read_back`, with positive limits/time-limits/current attribute readbacks, raw `values_in_range=false`, scoped Boolean true, `runtime_acceptance=pending`, `feature_complete=false`.

An independent stdlib reader, importing neither report nor fixtures, finds 241 contiguous samples and zero write errors in each run; both observation files match their cache copies byte for byte. Independent raw checks find fog first inside at seq 22 (`.719221`) and overcast at seq 23 (`.98`); there are no actuals outside the tolerance from their respective assessed endpoints onward and no outside candidate forecasts anywhere. Raw candidate ranges remain `.0312421..8` and `.2877..99`. These are sampled observations from one pair, not proof of intervening frames, controller precedence, production enablement or runtime acceptance. See `independent-raw.log`, `real-pair.log`, `real-pair-summary.log`.

## Commands and actual output

Read-only inspection included `cat AGENTS.md`, the Banso CLI skill, the runtime contract, `git show 099f96f`, the r4 review and scripts. The requested `docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md` are absent: the read command returned `No such file or directory` for both. No lifecycle or agent-panel command was run.

Preparation, rc 0:

```sh
mkdir -p scratchpad-review/r5/baseline scratchpad-review/r5/tmp
git archive 099f96f tools tests mods | tar -x -C scratchpad-review/r5/baseline
cp scratchpad-review/r4/{adversarial_cases.py,review_cases.py,new_cases.py,new_cases_adapted.py,round3_cases.py,round3_cases_adapted.py,mutate.py,mutate_new.py,mutate_round3.py,mutations_adapted.py,independent_raw.py} scratchpad-review/r5/
git show 099f96f > scratchpad-review/r5/round5.diff
```

Every Python invocation used `PYTHONDONTWRITEBYTECODE=1` and `-B`; test commands used `TMPDIR=/code/hc-worktrees/weather-review-3/scratchpad-review/r5/tmp`. Discovery/module commands ran from the archived baseline. Script commands ran from the worktree root. Full stdout/stderr is saved in the named logs.

| Command | Actual output | rc / log |
|---|---|---|
| `python3 -B -m unittest discover -s tests/unit -p 'test_weather*.py' -v` | `Ran 180 tests in 1.107s` / `OK` | 0, `weather-tests.log` |
| `python3 -B -m unittest tests.unit.test_probe_runtime tests.unit.test_atmosphere -v` | `Ran 74 tests in 0.878s` / `OK` | 0, `adjacent-tests.log` |
| `python3 -B scratchpad-review/r5/adversarial_cases.py` | `Ran 7 tests in 0.123s` / `OK` | 0, `adversarial-cases.log` |
| `python3 -B scratchpad-review/r5/review_cases.py` | `Ran 13 tests in 0.121s` / `OK` | 0, `review-cases.log` |
| `python3 -B scratchpad-review/r5/new_cases.py` | `Ran 4 tests in 0.056s` / `FAILED (failures=1)` | 1, `new-cases-verbatim.log` |
| `python3 -B scratchpad-review/r5/round3_cases.py` | `Ran 8 tests in 0.020s` / `FAILED (failures=4)` | 1, `round3-cases-verbatim.log` |
| `python3 -B scratchpad-review/r5/new_cases_adapted.py` | `Ran 4 tests in 0.068s` / `OK` | 0, `new-cases-adapted.log` |
| `python3 -B scratchpad-review/r5/round3_cases_adapted.py` | `Ran 8 tests in 0.018s` / `OK` | 0, `round3-cases-adapted.log` |
| `python3 -B scratchpad-review/r5/mutations_adapted.py` | M1–M8, N1–N5, R1–R8 each `KILLED`, each mutant exit 1 | harness 0, `mutations.log`, exact patches and individual logs adjacent |
| `python3 -B scratchpad-review/r5/fix_mutations.py` | W1–W7 each `KILLED`, failures respectively `9,8,3,2,2,2,5`, each mutant exit 1 | harness 0, `fix-mutations.log` |
| `python3 -B scratchpad-review/r5/supplemental.py` | `Ran 5 tests in 3.879s` / `FAILED (failures=2)` — findings 1 and 2; other three checks pass | 1, `supplemental.log` |
| `python3 -B -m tools.audit.weather_report compare --stock /mnt/d/HollowCountryLocal/weather-probe-001-stock --candidate /mnt/d/HollowCountryLocal/weather-probe-001-candidate` | `complete`, coverage `complete`, issues `[]`; details above | 0, `real-pair.log` |
| `python3 -B scratchpad-review/r5/independent_raw.py` | both `samples=241`, `seq_contiguous=true`, `cache_matches=true`; candidate forecasts outside `0` | 0, `independent-raw.log` |
| `python3 -B scratchpad-review/r5/summarize.py` | independent assessed violations `[]` for each phenomenon; all 28 mutation outcomes and test summaries | 0, `real-pair-summary.log` |

The 21 prior mutation intents were mechanically relocated in r4; that adapter is reused unchanged here. The seven new mutation intents reverse first-entry handling, entry-sample assessment, raw-Boolean independence, violation-before-cycle ordering, forecast checks, nonending-window protection and scheduled-change-sample assessment. This independently establishes **28 named killed mutations**, not the worker's unverified total of 62. M5's killed run raises a `KeyError` because disabling the watchdog removes the expected end record; R1 also has seven behavioral assertion failures. These are mutation consequences, not baseline import or environment errors.

Full required discovery was attempted too:

```text
python3 -B -m unittest discover -s tests/unit -v
Ran 2191 tests in 37.192s
FAILED (errors=169, skipped=1)
exit 1; all-tests.log

git archive 099f96f | tar -x -C scratchpad-review/r5/baseline
exit 0

python3 -B -m unittest discover -s tests/unit -v
Ran 2232 tests in 42.425s
FAILED (failures=1, errors=155, skipped=1)
exit 1; all-tests-full-archive.log
```

The initial archive omitted files needed by unrelated suites. Expanding it removed that setup error. The complete-archive run still cannot pass with this task's confined temporary directory: 40 errors reject deployment destinations inside source checkouts; 114 reject probe files inside Git checkouts; one downstream `UnboundLocalError` follows a refused probe setup. The sole assertion failure is a deployment CLI returning `Deployment refused: destination must be outside Steam and source checkouts`. No permission boundary or test was changed to bypass these restrictions. The full suite is **not green**; the weather and adjacent suites are green. This limitation does not supply evidence of a weather regression.

An initial supplemental expectation incorrectly treated an out-of-range very first actual as assessed. The implementation correctly excused that one-sample prefix. The review script was corrected to explicitly assert that exception; its original output is preserved in `supplemental-initial.log`. The final failures above reproduce the two reported findings.

All writes are under `scratchpad-review/r5/`, including temporary fixtures and archived mutation targets. `integrity.log` records `git diff --exit-code` returning 0, status showing only the pre-existing `.banso-brief-005.md` and r5 artifacts, and byte identity of production/test/probe sources with 099f96f, including the restored archive. No repository source edits, Git state changes, commits, index operations, DayZ/Wine/PowerShell execution or writes under `/mnt/d` were performed. No production fix or native acceptance is claimed.
