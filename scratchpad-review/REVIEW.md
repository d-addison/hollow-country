Verdict: **BLOCK** for commit b9d2d154c23843208152268c50cccbbcea6a6a99, parent fb05ff1.

The sampler is suitable for further source work, but its report can positively classify precedence without observing an opportunity for either controller to act. Keeping runtime_acceptance=pending does not make that evidence label accurate.

Review scope: source and synthetic offline tests only. No DayZ, Wine, PowerShell, /mnt/d staging, git metadata mutation, production edits, commits or pushes. The archive, test temp directories, reproductions and logs are under scratchpad-review/. The required docs/SPECIFICATION.md and docs/specs/001-survival-overhaul/spec.md are absent from this checkout; cat reported “No such file or directory” for each. AGENTS.md, docs/RUNTIME_IMPLEMENTATION_CONTRACT.md, .banso/config.yaml and the task brief were read. No missing native experiment is accepted.

1. **P1 — Range coincidence is promoted to candidate_governs without a usable weather experiment.** tools/audit/weather_report.py:448–456, 436, 473–475. A stock trace at .3 and candidate trace at .65, with candidate overcast limits .6–.7, produces candidate_governs even when both runs are frozen, weather_time never advances and XML enable=false. Both values fit independent Chernarus startup random picks. A second trace yields candidate_governs with actual=.9, forecast=.3, live limits=0..1 rather than candidate .8..95, and every next_change=1000 while the observation window ends at weather_time=150. No forecast boundary was observed. The hook's own docstring promises constant no-tick weather cannot discriminate, but comparison ignores those diagnostics. Cache evidence: ChernarusPlus.c:75–77 chooses startup overcast .2..75; Weather.c:125–144 delegates at forecast computation; WorldData.c:563–566 sets overcast transition/hold ranges of 600..900 seconds. Six samples at the permitted five-second interval only span 25 seconds. Minimal fix: separate range compliance from precedence inference; retain sample timing/next-change progress and require an active, unfrozen, sufficiently long observation window before classifying precedence. Disabled XML, non-ticking weather, no observed forecast cycle, or contradictory controller evidence must stay pending/not-discriminating. Even qualified random pairs should be labelled consistent with candidate limits rather than asserting sole controller ownership: XML limits and world-script forecasts can coexist. Add frozen, startup-only, conflicting-live-limit and transition tests. Reproductions: test_frozen_non_ticking_runs_do_not_establish_precedence and test_no_forecast_boundary_and_conflicting_limits_do_not_establish_precedence.

2. **P2 — compare() does not enforce a matched control and treatment.** tools/audit/weather_report.py:425–433, 462–470. It checks only different cfgweather hashes and variant labels. It discards source, stock hash and hook pins from each plan and never compares header versions or timing settings. A stock header for 1.29 plus a candidate header for 1.30, with different source launch-plan, hook and stock hashes, returns complete/candidate_governs with no issues. Minimal fix: preserve and require matching engine/world, source/runtime configuration, stock cfgweather ancestry, generated hook hash and sampling parameters. Require candidate stock_sha256 to equal the control's staged cfgweather hash. Missing or incompatible provenance should make comparison pending. Reproduction: test_incompatible_plan_sources_and_builds_make_comparison_pending.

3. **P2 — Default candidate admission does not reconstruct against stock even though stock is available.** tools/setup/weather_probe.py:514–522, 568–581. Without --candidate-source, validate_candidate verifies internal consistency and explicit overrides only. Checking the profile's source_sha256 against stock later does not establish that the candidate was generated from it. Starting with a valid candidate, change fog/limits/max to .5 without changing the profile or delta inventory, then recompute candidate/report/manifest digests: stage() accepts it and records source_verified=false. Thus the experimental treatment can contain unreported changes. This concerns provenance consistency, not cryptographic authenticity of unsigned manifests. Minimal fix: reconstruct through atmosphere's public generator/validator against the verified stock input before build_runtime; compare the admitted candidate bytes with the reconstruction. Alternatively require an explicit pinned source rather than silently downgrading to integrity-only validation. Keep the stock read pinned against replacement. Reproduction: test_unreported_candidate_drift_is_refused_against_available_stock.

4. **P2 — Duplicate JSON fields silently discard conflicting observations.** tools/audit/weather_report.py:237. An actual field written as `"actual": 0.1, "actual": 0.9` is accepted as .9; evaluate returns complete with no issues. Schema key-set checks cannot detect duplicates after json.loads collapses them. Minimal fix: use an object_pairs_hook that rejects repeated keys at every object depth, convert that ValueError into the existing malformed/pending path, and use the same policy for plan JSON. Reproduction: test_duplicate_json_keys_make_run_pending.

5. **P2 — Numeric overflow escapes malformed-input handling and the documented CLI codes.** tools/audit/weather_report.py:88–89, 276, 560. A JSON integer 10**400 in actual is well below input limits, but float(value) raises OverflowError. The row parser and CLI do not catch it: CLI prints a traceback and exits 1 instead of returning a pending report (3). Deep JSON also needs a bounded/caught recursion policy. Minimal fix: convert conversion overflow into ValueError at _number, and normalize bounded decoder recursion failures into malformed-input issues. Do not merely catch everything at main, because malformed observation rows are documented as pending. Reproductions: test_overflowed_numeric_value_is_pending_instead_of_crashing and test_overflow_cli_does_not_escape_with_a_traceback.

6. **P2 — Hook tests do not protect the safety and measurement behavior they claim to cover.** tests/unit/test_weather_probe.py:178–217. All 70 weather tests remain green after each independent mutation: disable the elapsed-duration guard; disable existing-output refusal; write sentinel before end record; swap actual/forecast getter bindings; disable watchdog completion; schedule every sample with delay=0. The sentinel test compares positions of function definitions rather than invocation order. Minimal fix: add tests that fail for these supplied mutations, checking emitted field/getter associations and guard, scheduling, and write effects using source-coupled execution with explicit synthetic adapters. Keep native compilation/runtime qualification pending; offline adapters do not prove engine behavior. Mutation scripts, individual diffs and full logs are retained.

7. **P3 — Insufficient comparison evidence still returns overall complete/exit 0.** tools/audit/weather_report.py:448–450, 470, 479, 542–544. With four samples per run and the default minimum six, every phenomenon has evidence=pending, yet compare status is complete and _emit returns 0. This also occurs through the public evaluate(min_samples=...) API with otherwise complete runs. Minimal fix: make aggregate comparison status pending when any required evidence is pending; preserve structural completeness separately if useful. Reproduction: test_comparison_below_min_samples_is_pending. Separately, repeated/non-monotonic game_ms are not validated: six distinct seq values at the same game_ms are accepted as complete. Validate elapsed/order/interval plausibility alongside the measurement gates in finding 1.

8. **P3 — _ensure_purpose() should be replaced by a real integrator-owned row and a refusal check.** tools/setup/weather_probe.py:533–535, 565. setdefault does not overwrite a row, and a conflicting fixed-hook row is correctly refused by diagnostic_mission._hook_for; no fixed-hook substitution was reproduced. However, a missing row is silently inserted into private process-global state, including before rt.begin can fail. An existing generated-hook row with the wrong manifest kind/prerequisites is silently retained and staging succeeds with kind=disposable-something-else. Minimal fix: remove the private-registry mutation, add the actual row in the owning module, and validate the expected row before staging, just as _check_launcher_row refuses unavailable integration. This finding concerns the fallback, not the integrator's outstanding rows, which are out of scope. Reproductions: test_missing_purpose_should_be_refused_without_mutating_shared_registry (a recommended refusal-policy assertion), test_conflicting_generated_purpose_metadata_should_be_refused; fixed-hook conflict test passes.

Native/source checks found no additional compile blocker. Manually checked the called Weather/WeatherPhenomenon getter return types and six declared float out parameters; GetDate's five declared int out parameters; GetWorldName/GetVersion declared string out parameters; GetGame/IsServer/GetWorld/GetWeather/GetTime/GetCallQueue; ScriptCallQueue.CallLater; string Length/Substring/Replace/IndexOf; int and float conversions; and FileExist/MakeDirectory/OpenFile/CloseFile/FPrintln against the supplied cache. GetMissionWeather/GetWeatherUpdateFrozen are plain field reads. The other weather getters are documented native accessors, with no visible script mutation. The hook invokes no weather setter; unknown native internals are not claimed proven side-effect-free.

Generated text has no prohibited type-name identifiers, leading boolean operators, ternaries, duplicate locals or exponent literals under the installed-type lint. The maximum '+' count is 8 and concatenations use explicit numeric conversions. CallLater uses one-shot calls, count/cap/watchdog bounds are present, sample/write paths are confined to the probe profile, the sentinel is called after the end append, and earlier output is refused. FPrintln/CloseFile return void, so write-error accounting only detects open failures; truncated/missing output must continue to be rejected by the report. A watchdog cannot interrupt a synchronous hang, as documented. Default cap=1830000ms, watchdog=1920000ms and launcher wait=35 minutes. Fresh storage/profiles and ordinary hash/refusal checks use the shared runtime; the absent launcher integration row is deliberately not counted as a finding. Reset/enable, zero-client ticking, float.ToString precision, native compile and normal server acceptance remain unobserved; source checks are not runtime evidence.

Commands and actual results (run from this worktree unless another cwd is shown):

```text
git show b9d2d15 > scratchpad-review/commit.diff
git archive b9d2d15 | tar -x -C scratchpad-review/baseline
```

Both completed with exit 0. The archive isolates test writes from repository source; TMPDIR is the sibling scratchpad-review/tmp because diagnostic_mission correctly refuses staging inside its own source checkout.

```text
cwd=scratchpad-review/baseline
TMPDIR=/code/hc-worktrees/weather-review/scratchpad-review/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p 'test_weather*.py' -v
Ran 70 tests in 0.499s
OK
exit 0

cwd=scratchpad-review/baseline
TMPDIR=/code/hc-worktrees/weather-review/scratchpad-review/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_probe_runtime tests.unit.test_atmosphere -v
Ran 39 tests in 0.601s
OK
exit 0

TMPDIR=/code/hc-worktrees/weather-review/scratchpad-review/tmp PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/review_cases.py
Ran 13 tests in 0.140s
FAILED (failures=10, errors=1)
exit 1
```

The review tests intentionally assert the missing behavior; no fixes were applied. Two checks pass: null phenomena becomes pending without a None-iteration crash, and a conflicting fixed-hook purpose is refused. Selected actual counterexample output:

```text
four-sample comparison: complete pending
wrong generated purpose: staged; manifest kind= disposable-something-else
duplicate actual key: complete []
frozen/no tick: {"evidence": "candidate_governs", "clock_advanced": false, "frozen": {"values": [true], "any_true": true, "all_true": true, "consistent": true}, "enable": false}
incompatible runs: complete candidate_governs []
missing purpose: staged; shared registry mutated= True
overflow CLI: 1 OverflowError: int too large to convert to float
repeated game_ms: complete []
unreported fog drift: staged; source_verified= False
```

```text
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/mutate.py
M1_disable_duration_check                 SURVIVED exit 0
M2_disable_existing_output_refusal        SURVIVED exit 0
M3_write_sentinel_before_end_record       SURVIVED exit 0
M4_swap_actual_and_forecast_getters       SURVIVED exit 0
M5_disable_watchdog_finish                SURVIVED exit 0
M6_schedule_samples_without_interval      SURVIVED exit 0
M7_remove_duplicate_seq_guard             KILLED   exit 1
M8_ignore_sentinel                       KILLED   exit 1
```

Every mutation ran the same 70-test discovery command in its own fresh Python process; the archived source file was restored in finally after each run. Harness exit 0. Full output is in weather-tests.log, shared-tests.log, review-cases.log, M1…M8 logs and mutation-results.json.

An additional Python source check against /home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289 printed:

```text
native type names: 7190
shared compile-shape issues: []
local statement issues: []
maximum plus operators per statement: 8
default cap_ms: 1830000
default watchdog_ms: 1920000
default wait_minutes: 35
```

The full repository discovery suite was not run: unrelated tests can create git repositories and invoke Windows PowerShell, contrary to this review's confinement. No production fix or green fix-validation is claimed.

Final byte comparison used `git show b9d2d15:<path>` for all four reviewed files against both the worktree and restored scratch archive. Actual output:

```text
All four reviewed worktree files and scratch baseline files match b9d2d15 byte-for-byte.
four-sample comparison: status=complete, evidence=pending, exit=0
```

`GIT_OPTIONAL_LOCKS=0 git diff --exit-code` exited 0 with no output. Final `GIT_OPTIONAL_LOCKS=0 git status --short` showed only the pre-existing `?? .banso-brief.md` and the permitted `?? scratchpad-review/`.
