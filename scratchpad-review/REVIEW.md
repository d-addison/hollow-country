Verdict: **BLOCK** for `66892b4ae737ae2cbf52736eaf029df3315d1b6c` on `hc/weather-review-2`.

The original staging, JSON and six hook-behavior defects are fixed. The remaining block is the experiment/report contract: the pair still cannot distinguish applied candidate limits from values merely falling inside them, and it requires unrelated forecast cycles that cannot reliably be observed within the requested 25 minutes. The hook itself has no additional source-level compile-shape blocker.

This is a read-only source/offline review. All new files and archives are under scratchpad-review/. No DayZ, Wine, PowerShell, /mnt/d staging, git metadata mutation, production changes, commits or pushes were performed. `AGENTS.md`, `docs/RUNTIME_IMPLEMENTATION_CONTRACT.md`, the Banso CLI skill and task brief were read. Both `docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md` are absent; `wc`/`cat` reported “No such file or directory”. No missing native experiment is accepted. All traces below are explicit synthetic data, never engine observations.

Ranked findings:

1. **P1 — The positive pair label still does not discriminate applied limits from coincidental values.** `tools/audit/weather_report.py:558` (positive return at 561; live-limit data computed at 430 but ignored here; comparison omits it at 625). With valid matched provenance, active enabled weather, a crossed deadline, stock overcast=.3 and candidate actual=.86..91, the pair returns `complete / observed_limit_compliance` even when **all six candidate live-limit readings remain 0..1 rather than .8..95**, and every candidate forecast is .3. The docstring at line 30 describes this as “the pair observed the limits being honoured”. The revised notes correctly disavow proof of precedence, but that does not supply the requested distinction. Chernarus' bad-weather branch itself picks overcast .6..1 (`4_World/Classes/Worlds/ChernarusPlus.c:213`), so .8..95 is not outside world-script support. Minimal fix: separate `observed_values_in_range` from `candidate_limits_applied`; carry and compare live `GetLimits` readings against each run's XML, require the distinctive candidate live-limit differential for an applied-limit conclusion, and expose conflicting forecasts/mission flags. Preserve unknown engine behavior as unknown. Engine limits and world-script forecast selection can coexist; do not make them mutually exclusive ownership labels. Reproduction: `test_crossed_boundary_does_not_override_conflicting_live_limits` in new_cases.py.

2. **P1 — Mandatory cycles for every phenomenon make a short targeted experiment inconclusive for unrelated reasons.** `tools/audit/weather_report.py:551`, `:620`, `:631`; timing default at `tools/setup/weather_probe.py:131`. A fully usable overcast pair becomes overall pending solely because unchanged snowfall has actual=forecast=0 and next_change=0. A 24-minute synthetic trace with fog's deadline=1805 and wind direction's=2205 also remains pending despite discriminating overcast observations. The tests deliberately give all six phenomena 100-second deadlines and even change the synthetic zero-limited snowfall forecast to .01 (`tests/unit/test_weather_report.py:95`), so they do not exercise this legitimate lack of useful progression. This is not a claim that native snowfall must have next_change=0: its actual native scheduling is unobserved. Visible native source nevertheless gives concrete reasons not to promise a short complete report: fog requests 1800 seconds outside the clear/morning exceptions (`ChernarusPlus.c:359`, `:380`); wind direction requests transition/hold parameters totaling overcast time + overcast hold + 1000 (`:222`), using 600..900-second time/hold settings (`3_Game/WorldData.c:563`–566). Exact native deadline mapping remains unmeasured. Minimal fix: designate the tested/overridden phenomena, keep unchanged/inert observations informational, and separate a complete observation run from inconclusive progression. Keep a per-target gate rather than merely removing the safety gate. Reproductions: `test_unchanged_zero_snowfall_does_not_block_targeted_overcast_result`, `test_plausible_24_minute_fog_and_wind_schedules`.

3. **P2 — Passing an old deadline is treated as observing forecast progression without a reschedule.** `tools/audit/weather_report.py:447`, `:440`. A candidate with actual=.81..86 interpolating toward a fixed forecast=.9 and **unchanged next_change=100 in every sample**, weather times 0..150, is considered boundary_crossed and gets the positive pair label. Nothing records a recomputation or a new deadline. `Weather.GetTime` is documented as elapsed server time (`3_Game/Weather.c:179`–180), so clock advance alone is not evidence that the weather controller ticked. Minimal fix: retain time/deadline/forecast observations and require evidence after the crossing that the deadline advanced or a new forecast was selected; actual interpolation alone must not qualify as a new forecast cycle. Otherwise label only elapsed deadline / interpolation, and leave controller progression unknown. Reproduction: `test_constant_future_deadline_is_not_observed_forecast_recomputation`.

4. **P2 — New measurement/admission mutations still survive.** `tests/unit/test_weather_probe.py:618` and reconstruction tests at `:784`; boundary tests in `tests/unit/test_weather_report.py:485`. All 111 weather tests pass when weather_time is emitted from `nowMs` instead of `weather.GetTime()` (`tools/setup/weather_probe.py:279`); this changes seconds to milliseconds and invalidates comparison to GetNextChange. They also pass if the future-deadline guard is removed (`weather_report.py:453`), or the admitted candidate digest comparison is disabled (`weather_probe.py:542`). The last check protects the exact bytes admitted before reconstruction if the candidate directory changes between its two reads. Minimal fix: assert the fake Weather.GetTime value and units in the source-coupled hook test; test already-expired/zero deadlines; simulate candidate replacement between initial admission and reconstruction and require refusal. These are additional gaps; all six original hook mutations are now killed.

Prior BLOCK findings, rerun against HEAD:

| Prior item | Status | Actual result |
|---|---|---|
| 1. Coincidence / frozen / no-cycle inference | **PARTIAL** | Original frozen/no-clock and no-boundary reproductions now give pending. `candidate_governs` was removed. The valid-provenance counterexamples in findings 1 and 3 remain positive. |
| 2. Matched provenance | **FIXED** | Incompatible versions/source/hook/stock ancestry give pending with explicit issues. Header and plan sampling are compared; missing plan blocks comparison. |
| 3. Reconstruction against stock | **FIXED** | Rehashed unreported fog drift is refused before destination creation; valid candidate records source_verified=True. Reconstruction uses held verified stock bytes, not caller-supplied source. |
| 4. Duplicate JSON fields | **FIXED** | Duplicate actual becomes pending with `malformed JSON on line 2: duplicate JSON key 'actual'`; plan decoder uses the same rejection policy. |
| 5. Overflow / recursion | **FIXED** | 10**400 becomes pending; CLI exits 3, empty stderr, no traceback. Deep nesting and nonfinite tests pass. |
| 6. Original six surviving hook mutations | **FIXED** | M1–M6 each killed by new tests. M7–M8 remain killed. Additional gaps are finding 4. |
| 7. Insufficient aggregate / repeated timestamps | **FIXED** | Four samples: pending/pending; repeated game_ms: pending with explicit timestamp issue. New over-broad scope is finding 2. |
| 8. Private registry fallback | **FIXED** | Missing, fixed-hook and wrong generated metadata rows refuse before creation, without registry mutation. Parent 0936083 supplies the real row; 82d3042 supplies launcher kinds. |

The original review_cases.py was copied and first run unchanged: 12 checks passed and one errored in its **print**, because it indexed the now-empty CLI stderr. Only that display was adapted to print `<empty stderr>`; the assertion was unchanged. The adapted run passes all 13. Some old comparison reproductions omit plans and are now also blocked by provenance; the new reproductions use full matching plans to avoid that masking. Full original and adapted logs are retained separately.

Candidate reconstruction and refusal audit: `load_candidate` admits integrity and captures XML bytes/hash; `rt.begin(...hold=("cfgweather.xml",))` verifies and holds stock without creating the destination; source SHA must match; atmosphere.validate_candidate(source=private-temp-file-of-held-stock) regenerates exact candidate bytes; its result must be source_verified and match the earlier admitted digest; only then does shared build_runtime write the destination. Shared check_unchanged rechecks source identities/hashes before/after copying. Successful treatment replaces only cfgweather.xml (init.c instrumentation is common to both runs). The explicit initial-digest guard exists and works, though its removal survives tests. The registry checker refuses the expected missing/conflicting rows and never inserts one. Both integration commits were inspected; the parent adds only its purpose row and regression, while HEAD adds the four scoped files.

Recommended native experiment:

**There is no parameter choice that guarantees the current pair report can deliver a discriminating answer within 25 minutes.** The control must remain stock, its native schedules cannot be shortened by candidate settings, and the report demands a future forecast boundary for every phenomenon. Longer sampling is not a guarantee either for a zero-limited/inert phenomenon. This is an experiment design limitation, not an observed native failure, and not a reason to run indefinitely. Two random traces also cannot prove exclusive controller precedence.

For a bounded first diagnostic pair, use the same `--start-delay-s 5 --interval-s 5 --samples 241 --wait-minutes 25` for both fresh runtimes. That gives a 1200-second observation span, last sample nominally at 1205 seconds after OnInit, cap=1235000ms, watchdog=1300000ms (21m40s), and required launcher wait=25 minutes including its three-minute boot allowance. These figures are per run; if the 25-minute budget means the sum of both sequential runs, a complete stock forecast-cycle experiment is even less supportable. Do not advertise this pair as guaranteed discriminating under the current gate.

Candidate: generate from the exact held stock; `enable=true`, `reset=false` with empty fresh storage. Suggested distinctive limits/current: **fog .70..80 / .75**, overcast **.97..99 / .98**; for these two phenomena use time limits 30..60 seconds, change limits .005..01, and current time=30, duration=30. Preserve other stock settings and snowfall=0..0. Validate with the normal atmosphere generator. Fog is the stronger intervention: visible Chernarus selections are .0..15, a morning exception .10..35, and clear .0..08 (`ChernarusPlus.c:355`–381), so .70..80 is outside those script forecast targets. Overcast alone is insufficient because bad-weather values include .97..99. This is a suggested measurement treatment, not a production profile.

After fixing findings 1–3, compare live-limit readbacks immediately (stock limits versus distinctive candidate limits), actual/forecast traces and mission_weather flags for the selected targets. If mission_weather is true, Weather.c:130–131 shows the script delegation bypass; if false, that fact does not by itself prove limits are ignored. Candidate limits may clamp world-script forecasts. Retain pending for progression not actually observed and report absence of a usable cycle honestly. This permits useful limited conclusions about effective limits within the budget, not an unconditional proof of precedence. Native compile, zero-client ticking, XML load/reset order, float formatting, DayZDiag/normal-server qualification and production enablement remain pending.

Native compile-shape audit:

An independent character lexer strips comments/string contents, splits statements on semicolons/braces regardless of physical lines, and counts every plus. Maximum=**8** (generated-hook.c line 89; corresponding template source line 233). All plus-bearing statement counts are in native-checks.log. Every numeric concatenation is explicitly converted with int.ToString or HCWPFloat → float.ToString → quoted string; ASCII code conversions are explicit. All 7190 cache type names were supplied to lint, and declared identifiers were separately compared: no collision. No leading `||`/`&&`, ternary, exponent literal, increment/compound assignment, or duplicate parameter/local per method was found. All six float out locals, five GetDate ints and GetWorldName/GetVersion strings precede their calls. One-shot count/cap/watchdog, existing-output refusal and end-before-sentinel behavior are covered by source-coupled synthetic tests.

The inline-brace bypass **is reproducible in shared lint** (`void F() { string s = "a" + ...; }`, 27 plus → shared lint []). The weather stager's additional statement_problems catches the same string with `statement has 27 '+' operators (max 8)`, so this does not create a generated-hook blocker here.

The hook contains no Set* / MissionWeather / SuppressLightningSimulation call and no gameplay, inventory, position, weather-setting or game-persistence write. It only registers its sampling callbacks, reads state, prints diagnostics, and writes its observations/sentinel in `$profile:HCWeatherProbe/`. Thus the source adds no gameplay/persistence mutation beyond intentional probe files; this is not a guarantee about native getter internals or zero timing overhead. super.OnInit retains normal mission initialization. Native compilation was not run.

Every external method/function called was checked against the installed cache, including string helpers and Print omitted from the module's API list. Full declarations and line citations follow in native-checks.log. Compact index (paths relative to supplied cache):

- GetGame: `2_GameLib/gameLib.c:4`; IsServer, GetWeather, CGame.GetTime, GetCallQueue, GetWorld, GetWorldName, GetVersion: `3_Game/Global/Game.c:1120,1371,1535,1550,931,932,942` respectively; GetDate: `3_Game/Global/World.c:28`; CallLater: `2_GameLib/tools.c:61`.
- GetActual/GetForecast/GetNextChange/GetLimits/GetForecastChangeLimits/GetForecastTimeLimits: `3_Game/Weather.c:38,41,52,61,81,102`; Weather.GetTime/GetOvercast/GetFog/GetRain/GetSnowfall/GetWindDirection/GetWindMagnitude: `:180,183,186,189,192,199,205`.
- GetWindSpeed/GetWindMaximumSpeed/IsDynVolFogEnabled/GetDynVolFogDistanceDensity/GetDynVolFogHeightDensity/GetDynVolFogHeightBias/GetMissionWeather/GetWeatherUpdateFrozen: `3_Game/Weather.c:248,263,354,364,374,385,392,402`.
- FileExist/OpenFile/CloseFile/FPrintln/MakeDirectory: `1_Core/proto/EnSystem.c:397,417,443,481,525`; FileMode.WRITE/APPEND: `:382,385,386`; int.ToString/int.AsciiToString/float.ToString: `1_Core/proto/EnConvert.c:30,44,115`; Substring/Replace/Length/IndexOf: `1_Core/proto/EnString.c:113,156,199,240`; Print: `1_Core/proto/EnDebug.c:96`; OnInit: `5_Mission/mission/missionServer.c:85`; CALL_CATEGORY_SYSTEM: `3_Game/tools/tools.c:8`.

Commands and actual results:

```text
git show HEAD > scratchpad-review/head.diff
git show HEAD~1 > scratchpad-review/parent.diff
git diff b9d2d15 HEAD -- tools/setup/weather_probe.py tools/audit/weather_report.py tests/unit/test_weather_probe.py tests/unit/test_weather_report.py > scratchpad-review/fix-vs-prior.diff
mkdir -p scratchpad-review/baseline scratchpad-review/tmp
git archive HEAD | tar -x -C scratchpad-review/baseline
All exit 0; diffs retained.
```

Test commands ran from scratchpad-review/baseline with TMPDIR=/code/hc-worktrees/weather-review-2/scratchpad-review/tmp and PYTHONDONTWRITEBYTECODE=1:

```text
python3 -m unittest discover -s tests/unit -p 'test_weather*.py' -v
Ran 111 tests in 0.886s
OK
exit 0

python3 -m unittest tests.unit.test_probe_runtime tests.unit.test_atmosphere -v
Ran 74 tests in 1.304s
OK
exit 0
```

From worktree root, same TMPDIR and PYTHONDONTWRITEBYTECODE=1:

```text
python3 scratchpad-review/review_cases.py
[unchanged first run]
Ran 13 tests in 0.089s
FAILED (errors=1)
IndexError in review script's print(result.stderr.splitlines()[-1])
exit 1

python3 scratchpad-review/review_cases.py
[after adapting only that display for empty stderr]
Ran 13 tests in 0.068s
OK
exit 0
four-sample comparison: pending pending
duplicate actual key: pending ["malformed JSON on line 2: duplicate JSON key 'actual'", ...]
frozen/no tick: {"evidence": "pending", "clock_advanced": false, "enable": false, ...}
incompatible runs: pending pending ["header version differs or is unknown: ...", ...]
no forecast boundary: {"evidence": "pending", ... "forecast_outside_limits": 6, "boundary_crossed": false, ...}
overflow CLI: 3 <empty stderr>
repeated game_ms: pending ['game_ms does not increase between seq 0 and seq 1 (repeated or reversed timestamps)']

python3 scratchpad-review/new_cases.py
Ran 4 tests in 0.047s
FAILED (failures=4)
exit 1
unchanged deadline, interpolation only: complete observed_limit_compliance boundary= True
boundary crossed + live limits 0..1 + forecast .3: complete observed_limit_compliance live= {'matching': 0, 'total': 6} forecast_outside= 6
24 minute observation window: pending ['fog: no forecast boundary (next_change) was crossed in the stock run', 'windDirection: no forecast boundary (next_change) was crossed in the stock run']
inert unchanged snowfall: pending overcast= observed_limit_compliance snowfall= pending ['snowfall: no forecast boundary (next_change) was crossed in the stock run']
```

Mutation commands (exit 0 for each harness; each mutant ran the same 111-test discovery command in a fresh process and was restored in finally):

```text
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/mutate.py
M1_disable_duration_check                 KILLED exit 1, failures=1
M2_disable_existing_output_refusal        KILLED exit 1, failures=3
M3_write_sentinel_before_end_record       KILLED exit 1, failures=1
M4_swap_actual_and_forecast_getters       KILLED exit 1, failures=1
M5_disable_watchdog_finish                KILLED exit 1, errors=1
M6_schedule_samples_without_interval      KILLED exit 1, failures=4
M7_remove_duplicate_seq_guard             KILLED exit 1, failures=1
M8_ignore_sentinel                       KILLED exit 1, failures=3

PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/mutate_new.py
N1_weather_time_in_milliseconds          SURVIVED exit 0
N2_swap_volfog_density_getters           KILLED   exit 1, failures=1
N3_remove_reconstruction                 KILLED   exit 1, failures=2
N4_drop_future_deadline_guard            SURVIVED exit 0
N5_reconstruction_pins_wrong_expected_hash SURVIVED exit 0
```

Additional verification commands:

```text
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/native_checks.py
independent maximum + operators: 8
leading boolean operators: []
ternaries: 0
Set* / weather mutator calls: []
native type names: 7190
declared identifiers colliding with native types: []
shared lint: []
local explicit-number/statement lint: []
[Every method: duplicate locals/params: []; all API citations resolve; out params declared before calls.]
inline-brace 27-plus shared lint: []
inline-brace 27-plus weather local lint: ["line 1: statement has 27 '+' operators (max 8); the native compiler refuses long formulas"]
exit 0

TMPDIR="$PWD/scratchpad-review/tmp" PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/stager_checks.py
stock ACCEPTED stock source_verified= None
valid reconstructed candidate ACCEPTED candidate source_verified= True
rehashed unreported fog drift REFUSED candidate differs from reconstruction with pinned source destination_exists= False
missing purpose REFUSED ... destination_exists= False
fixed hook substitution REFUSED ... destination_exists= False
wrong generated metadata REFUSED ... destination_exists= False
[registry unchanged: True for every scenario]
candidate changed between reads: REFUSED candidate cfgweather.xml changed during reconstruction
actual launcher row: ('weather-probe-plan.json', 'HCWeatherProbe', 'observations.json')
actual purpose row: ('disposable-weather-probe', None, ['server mode', 'fresh storage and profiles', 'no clients', 'inspect observation completeness separately from startup'])
exit 0
```

Full logs, mutation diffs, scripts and generated hook are adjacent to this report. Native source was inspected with `nl -ba`, `sed -n` and `rg` at the cited paths/lines. The full repository unittest discovery was not run because unrelated tests can invoke PowerShell or create git repositories, outside this review's confinement.

Final checks: `git show HEAD:<path>` byte comparison passed for all four reviewed worktree files **and** the restored scratch archive files. `GIT_OPTIONAL_LOCKS=0 git diff --exit-code` exited 0; `git status --short` showed only pre-existing `?? .banso-brief.md` and permitted `?? scratchpad-review/`.
