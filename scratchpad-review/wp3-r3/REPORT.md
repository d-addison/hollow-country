# WP3 fix round 3 — infected competence probe (#18)

All five numbered review fixes are implemented for source/offline scope. Runtime
acceptance and production enablement remain **PENDING**. No DayZ, Wine, client,
network, commit, push, git staging, or git-metadata write was performed. Only the two
owned Python files were edited, plus this round's review artifacts and the
excluded `.banso-writer/commit-message`. Registration files are unchanged.
Existing changes to `.banso-brief.md` and the round 2 review directory were left
untouched.

Read the round 2 Sonnet review and mutation definitions/results, `AGENTS.md`, and
`docs/RUNTIME_IMPLEMENTATION_CONTRACT.md`. The canonical specification and
`docs/specs/001-survival-overhaul/{spec,plan,tasks}.md` are absent here; they were
read from the sibling `/code/dayzsa_mods/` checkout without modifying them.
Applied the Banso CLI skill's confined-worker instructions; no lifecycle or
orchestrator commands were run. This source work supports T018/T019,
FR-008/FR-011 and AC-007/AC-010; missing native experiments remain pending.
The active user's 3–6-player/friend-server and private-source decisions control.

**Fix trace**

| Review fix | Implemented behavior and boundary coverage |
| --- | --- |
| 1 / P2-1 | Completed initial sample must lie within **2 m radial x/z distance** of the planned spawn and **3 m vertically** of `spawn_surface_y`, inclusive. Later endpoint movement is allowed. Both surface heights must be within **-100..2000 m**, inclusive, for every server row. Tests reject displaced/diagonal initial positions and out-of-range heights. |
| 1 / reporting | `placement_evidence` reports absolute authored/surface deltas for anchor and spawn for each server trial. `surface_delta_warning` is true when either delta exceeds **3 m** on a non-default fixture. Clients carry no terrain evidence. Operator-surveyed warnings and the exact 3 m boundary are tested. |
| 2 / P2-2 | Method-scoped assertions pin the no-target false return, `per_trial_ms + 1000` timeout branch/return before sampling, `currentLegHealth >= m_LegBefore`, and ray origin **0.8 m** plus all four **0.6 m** offsets. No hook change was needed. |
| 3 / P2-3 | Completed elapsed range is **per_trial_ms - 250 .. per_trial_ms + 1100**, inclusive. This is a provisional allowance for unobserved CallLater/GetTime skew and the Observe/Next race. At 5000 ms, tests accept **4750/6100**, reject **4749/6101**. The hook still times out at greater than **+1000 ms**. |
| 4 / P3 | Completed reason is exactly `two_endpoint_samples_only`; inconclusive reasons are the eight hook-emitted reasons in `OUTCOME_REASONS`; client reasons remain exactly the canonical reason for the planned kind. Structure-missing evidence must precede geometry/spawn. Footprint-hit evidence needs four rays including a hit, no entity/samples/doors. Timeout evidence needs an owned initial sample, clear rays, and elapsed strictly above the hook's +1000 ms budget. |
| 5 / P3 | New tests cover a single-sample completed row, `21.30.164289`, sorting before class selection/limiting, survey offsets (1/10 inclusive, outside rejected), ambiguous rpy, stock provenance refusal before writes, and the 5-second start-delay floor (0/4 rejected, 5 accepted). Reports flag stock-derived and operator-surveyed fixtures as candidates and disclose operator-supplied provenance, unchecked XML hash provenance, and unobserved bearing convention. |

The synthetic receipt helper now uses the hook's actual completed reason and
explicit plan-relative x/z plus synthetic surface Y. Structure and timeout
fixtures follow the hook's evidence sequence. All fixtures remain explicitly
synthetic. The two owned files now derive the default cache path from
`Path.home()` instead of recording a personal absolute home path.

**Actual RED / GREEN evidence**

Tests were written before validator changes. Eight new validation/report tests
failed against round 2, as did the strengthened stock-derived limitation test.
Their individual commands, actual output and exit codes are in
`RED-test_r3_*.txt` and
`RED-test_survey_read_only_even_placements_yaw_provenance_and_stage.txt`.

Eleven new tests protect behavior already present in round 2. Their actual RED
uses the review's exact mutants on disposable copies, with one targeted new test
per mutant. `RED-{H05,H07,H17,H18,V13,V14,S03,S04,S05,S11,S13}.txt` records those
failures. `red_mutation_results.txt` maps each failure to its test. Mutations were
never applied to production source. All **19 new tests** therefore have an actual
RED record; the existing stock-fixture test has a separate strengthened RED.

The first focused check found a test-only typo: the accepted start-delay assertion
named HCICStep rather than the existing HCICBegin callback. Its output is retained
in `focused-first-check.txt`. The assertion was corrected and S13 RED rerun; its
final RED contains only the intended 0/4-second failures.

Reproduction harness: `run_mutants.py` reads the review's literal mutation triples
without executing that script, copies only tools/tests to temporary directories,
and preserves actual subprocess output. `baseline` captured pre-fix source RED;
`red` records targeted mutant failures; `final` runs all probe tests per mutant.
The baseline mode is historical evidence and is expected to pass on fixed source.

GREEN command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence -v
```

`GREEN-focused.txt`: **47 tests passed**. This includes source-shape lint and
installed API citation checks; it does not establish engine compilation/runtime
semantics. `source-and-native-evidence.json` records source hashes, all **47**
verified native references, zero lint errors, and the unchanged hook-template
identity. Default rendered hook SHA-256:
`6d009bbfa2a9daaf90358923b1f354868d455f5435c3f9d8599d6da45792ff19`.

Final mutation command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/wp3-r3/run_mutants.py final
```

`mutation_results.txt` and `mutation-{ID}.txt`: **11 killed, 0 survived, 0 unmatched**.
Each full-module mutant run failed in its intended new regression test.

| Mutants | Outcome |
| --- | --- |
| H05, H07, H17, H18 | KILLED |
| V13, V14 | KILLED |
| S03, S04, S05, S11, S13 | KILLED |

Full discovery command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit
```

`GREEN-discovery.txt`: **2409 tests, OK (1 skipped), 126.710 s**; exit code 0.
The existing platform skip is not counted as runtime acceptance.

`git --no-optional-locks -c core.fsmonitor=false diff --check` for the two owned
files passed. No personal absolute home paths appear in those files or this
round's artifacts. The metadata commands used only read-only show/diff/status
with optional locks disabled and fsmonitor disabled.

**Remaining acceptance and scope**

Tolerances are documented provisional admission checks, not measured native
placement or clock guarantees. Authored/surface warnings require operator review;
they do not qualify a roof/upper-floor fixture. Candidate building coverage,
DayZDiag, normal PBO/server loading, cleanup residuals, hit-path/crawl behavior,
two-client LOS/wall/audio trials, and 3–6-player performance remain pending.
The review's unnumbered P3-2 observation about broad mind-state bounds and
aggregate elapsed time is unchanged; it was outside the requested numbered fix
list. No missing engine experiment or gameplay requirement is marked accepted.
