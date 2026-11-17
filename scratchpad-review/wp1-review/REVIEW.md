# B04 WP1 review — 92cbffc against 73241f6

**Verdict: BLOCK.** The new admission gates stop fresh complex gameplay entry points, but D1 is incomplete for dormant journals and startup quarantine. Three P2 findings below have source-body counterexamples. No fresh native transfer/route/relay bypass was demonstrated with the shipped six false qualifications.

Reviewed `git show 92cbffc` (full diff retained in [commit.diff](commit.diff)), AGENTS.md, the supplied audit's D1/default-on table, WP1 ownership and reachability notes, its counterexample file, runtime integration contract, callers and collaborators. `HEAD` is `92cbffc251f90087eb666b60727e16222cc30adf`. The requested `docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md` do not exist in this checkout or its committed docs tree; no local feature spec/plan/tasks were available. This review does not infer their contents or mark requirements accepted.

## Ranked findings

1. **P2 — Unadmitted recovery still retires and persists an earlier journal.**

   **Locations:** `mods/HollowCountry/scripts/4_World/Infected/HCInfectedModule.c:154`, `:166`, **`:743`**, `:830`, `:845`; `HCInfectedState.c:455`.

   **Failure scenario:** Keep `EnableHordes=true` and all six preferences true with the shipped false qualifications. An earlier valid committed cohort loads as unresolved state 6, with a null runtime pack. The load still changes its restart metadata and startup marks the snapshot dirty. OnTick's pack-slot loop, which runs even for null packs, changes that unresolved record to terminal state 5 at age 3600 without consulting admission. The periodic save, or dirty shutdown save, persists it. Later reconciliation skips state 5. Thus qualifying recovery later cannot account for that pending roster through the recovery seam. Reservations remain spent; this finding does **not** claim a refill or duplicate entities.

   **Evidence:** `review_checks.py::test_unadmitted_recovery_does_not_retire_and_save_a_previously_pending_journal` executes the authored OnTick body with a valid synthetic state-6 journal. Before allowing the synthetic save, it executes the authored snapshot and roster validators against real scalar policies. Actual result: `State=5, Living=3, Reserved=3, events=['save']`, while all admitted flags are false. No native storage or transfer is simulated as proven.

   **Minimal fix:** Give dormant journals an explicit nonmutating admission disposition. When no relevant journal capability is admitted, preserve the existing slots/reservations without enrolling their records into normal sweep/expiry/writeback processing. Apply this to startup, tick and shutdown; do not simply suppress Reconcile or reset/delete the journal. Keep cleanup of native resources already owned in the current process available. Add restart/timer/shutdown tests with nonempty committed and prepared journals and both requested/unqualified and explicitly disabled recovery.

2. **P2 — An unadmitted horde preference still quarantines native-only startup.**

   **Location:** `mods/HollowCountry/scripts/4_World/Infected/HCInfectedModule.c:101`.

   **Failure scenario:** With the shipped all-false qualifications, default preferences, and a core-valid `MaxTickWorkItems=4` (also applies to 5–7), the remaining `settings.EnableHordes` term triggers whole-module quarantine: `hordes/routing require at least eight bounded work items`. All six complex paths are closed, yet this requested preference prevents the module's safe fallback from starting. Describe is never printed on this path. The new startup test explicitly asserts the surviving preference condition instead of testing its behavior.

   **Evidence:** The authored OnStart body returns unhealthy with exactly that quarantine in `test_closed_capabilities_do_not_quarantine_native_only_startup_at_valid_core_budget`. A default-budget positive control reaches healthy and logs admission once.

   **Minimal fix:** Compute the extra work prerequisite from admitted work, including any explicitly admitted active journal lifecycle, rather than the raw horde preference. Retain the generic minimum of four and the existing limits for work that actually runs. Couple this with finding 1 so dormant journals do not justify an otherwise unnecessary active-work requirement.

3. **P2 — The old preference dependency rejects an explicit disable before admission can explain it.**

   **Locations:** `mods/HollowCountry/scripts/4_World/Infected/HCInfectedState.c:31`; `HCInfectedModule.c:92`–99; contrast `HCInfectedState.c:154`.

   **Failure scenario:** An operator sets only `EnableNativePackRoutes=false` and leaves the default `EnableHordeStimulusRoutes=true`. IsValid rejects that preference combination, so OnStart quarantines the entire module with `invalid limits` before Resolve can return its per-path disposition. This happens even when both qualifications are false. The resolver test for this combination passes an otherwise invalid config directly into Resolve and therefore misses the real startup outcome.

   **Evidence:** `test_explicit_pack_disable_does_not_quarantine_unqualified_stimulus_preference` executes the authored IsValid and OnStart bodies and gets `('quarantine', 'invalid limits')`. The operator file is not rewritten, but one explicit disable disables unrelated paths too.

   **Minimal fix:** Move this capability dependency out of scalar/schema validation into admission, preserving the explicit pack-route disable. The existing Resolve dependency reason already handles the hypothetical stimulus-qualified/pack-unadmitted case. Exercise this through startup for both unknown and hypothetical qualified states.

These are retained behaviors left reachable by the admission integration, not claims that all cited underlying statements were first introduced by this commit. They are within the requested D1 review, rather than requests to implement WP2–WP9.

## Reachability, coverage and compile review

| Entry/caller | Review result |
| --- | --- |
| Mission → core registry → module OnStart/OnTick/OnStop | Reachable through the existing registry and core SYSTEM queue. Core inserts requested modules before OnStart, so quarantined instances still receive ticks/stops; their healthy guard prevents normal work. No additional infected timer was found. |
| TryAdopt and its periodic caller | Admission guard precedes capture, reserve, prepare/outcome saves and assignment. Requested/unqualified CE adoption produces no new adoption intent. Its caller still schedules no-op adoption ticks. |
| Cohort pack Start | Uses admitted NativePackRoutes after admitted CEAdoption. No separate load-time native pack recreation exists. |
| SampleActor → visual sampling / TryInvestigate | Sampling and MayInvestigate use admitted Investigation. Heard clues require admitted supplementary chains. Pack creation follows MayInvestigate. |
| NativeVoice → NativeEmission; OnTick → ProcessPending | Both relay entry points are gated. NativeVoice still registers, queues an emitter-local voice and updates dedupe/cooldown fields while unadmitted; OnTick still copies that voice into actor.Clue. This is not complete internal quiescence, but the shared selector excludes actor.Clue, and no unadmitted relay/investigation/retarget consuming it was found. Native sound still calls super exactly once. |
| Membership/adoption clue selection | Hearing parameter requires admitted SupplementaryChains. Visual sampling is independently gated. No hidden target coordinate source is newly added. |
| Reconcile | Sole module caller uses admitted MemberRecovery. Dormant journal processing outside that call remains finding 1. |
| FinishSweep → RetargetCohorts | Sole caller uses admitted HordeStimulusRoutes. Its remaining raw preference read at Module:483 is redundant under this caller and not a demonstrated bypass. Retarget reserve also uses admission. |
| Pack maintenance, RetryPendingReleases, Track recycling, Quarantine, ReleasePacks, OnStop | Maintenance/cleanup is not admission-gated. In a fresh process all pack/search/release collections start empty; persisted journals create null pack slots, not live packs. Retaining cleanup for resources already owned is appropriate. Persistent record mutation/save outside cleanup is finding 1. |

The tests translate authored bodies, erase types and use explicit synthetic collaborators. The 28 admission tests execute Resolve/Evaluate/Describe and selected module bodies, but startup checks are source-string assertions; tick fixtures have empty Groups/Packs and replace FinishSweep/SampleActor; FinishSweep's retarget test has no groups and stubs RetargetCohorts. Capture, pack Start, Reconcile and relay bodies are recorder stubs in these admission tests. They prove caller gating, not native or full lifecycle behavior. Importing the TestCase as `Admission` in the persistence module also causes unittest to rediscover its methods; test totals are not counts of unique proofs.

[Mutation results](mutation-results.json): **8/8 killed by assertion failures**, with no translator errors, after individually opening CE adoption, cohort pack start, investigation, visual sampling, NativeEmission, Reconcile, ProcessPending and FinishSweep retarget. Each mutation was made only in the disposable source copy and restored. The unchanged admission baseline was 28 OK. These mutations substantiate the tested guards; they do not cover the dormant/startup gaps.

Compile checklist: all eight existing syntax/identifier tests passed using `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`, including installed visible type names and override parameters. Additional source inspection/checks found no new ternary, leading logical operator, duplicate parameter/local across sibling scopes, undeclared out argument, changed override signature, or implicit scalar string concatenation. New Flag returns literal strings; max binary `+` per added statement is 6. The new qualification/admission/self-test code has no loops; changed module branches retain bounded collections/counters. Describe was exercised across all 4096 preference/qualification combinations: six segments, no newline, maximum **473 characters**. There is one normal-start Describe Print per successful startup; DIAG opt-in self-tests have a separate additional diagnostic. Early quarantines can skip the normal log, as above. Resolve's reason codes and disable precedence are otherwise consistent with the claims. No Enforce compiler, DayZ, Wine, PowerShell, PBO/server, two-client or load test ran. D2–D4 and all native acceptance remain pending.

## Executed commands and actual output

All output files and scripts are in this directory. No repository source or Git metadata was edited. Inspection included `cat AGENTS.md`, the Banso CLI/review skill instructions (the CLI dispatched-worker guidance was applied; no generic panel/lifecycle was launched), `git show --stat 92cbffc`, `git show --format=fuller 92cbffc`, `git show 92cbffc`, `git diff-tree --no-commit-id --name-only -r 92cbffc`, `git rev-parse HEAD`, `git ls-tree -r --name-only 92cbffc docs`, and `cat`/`sed`/`nl`/`rg` over the named audit/source/tests and narrow installed AI signatures. The missing-spec cat failed with `No such file or directory` for both requested paths. No git add/commit/init was executed.

For the test commands, TMPDIR was the absolute `scratchpad-review/wp1-review/tmp` directory; PYTHONDONTWRITEBYTECODE=1 throughout. Full suite processes inherited `PYTHONPATH=/code/hc-worktrees/b04-wp1/scratchpad-review/wp1-review/guard`. [guard/sitecustomize.py](guard/sitecustomize.py) rejects Git mutation (including synthetic fixture init/add), DayZ, Wine and PowerShell launches before execution. Production tests and their guards were not edited.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_defaults tests.unit.test_infected_persistence tests.unit.test_infected_completion tests.unit.test_infected_admission -v
```

[focused.log](focused.log), exit 0:

```text
Ran 94 tests in 0.281s
OK
```

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v
```

[discover.log](discover.log), actual checkout, exit 1:

```text
Ran 2407 tests in 55.351s
FAILED (failures=38, errors=314, skipped=1)
```

The same command from the unchanged `source-copy` with the sibling review TMPDIR, exit 1 ([discover-copy.log](discover-copy.log)):

```text
Ran 2407 tests in 61.218s
FAILED (failures=1, errors=190, skipped=1)
```

The first run's in-checkout temp location trips checkout staging guards and downstream assertions. In the copy, 114 errors report `probe files must be outside every Git checkout`, 40 report destination/source-checkout exclusion, 35 are prohibited synthetic Git initialization, and one is a test-local uninitialized result after staging refusal. The remaining failure is the deployment CLI's checkout guard. [results-summary.log](results-summary.log) retains diagnostic counts. These are confinement/test-harness limitations, not evidence of 190 infected regressions. **The writer's 2407 OK was not reproduced; no full-suite green is claimed.** Guards were not relaxed to obtain one.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_script_syntax tests.unit.test_script_identifiers -v
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/wp1-review/review_checks.py
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/wp1-review/prepare.py
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/wp1-review/mutations.py
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/wp1-review/compile_audit.py
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/wp1-review/summarize.py
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/wp1-review/verify_inputs.py
```

Actual summaries:

```text
# compile-shapes.log — exit 0
Ran 8 tests in 0.663s
OK
# review-checks.log — exit 1, expected RED counterexamples
Ran 4 tests in 0.036s
FAILED (failures=3)
# mutation-baseline.log — exit 0
Ran 28 tests in 0.093s
OK
# mutations.log — exit 0
8/8 guard-removal mutants killed; original source untouched.
# compile-audit.log — exit 0
Describe: all 4096 preference/qualification combinations bounded to 473 characters; exactly six segments.
# provenance.log — exit 0
PASS: 301 tracked inputs unchanged: /code/hc-worktrees/b04-wp1
PASS: 301 tracked inputs unchanged: /code/hc-worktrees/b04-wp1/scratchpad-review/wp1-review/source-copy
PASS: copy excludes .git; review artifacts contain no Python bytecode.
```

The initial counterexample run had `Ran 4 tests in 0.042s` / `FAILED (failures=2, errors=1)` because the reviewer fixture omitted m_MemberCap/m_GroupCap; [review-checks-initial.log](review-checks-initial.log) preserves it. The fixture was corrected and strengthened with real journal validation before the final three assertion failures. No product change was made. The generated source copy was removed after provenance checks to avoid delivering duplicate authored source; `prepare.py` recreates it for mutation reproduction. All writes remained under the review directory; no `.banso-writer` commit-message file was created under the stricter read-only review scope.
