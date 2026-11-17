# B04 WP6 — stimulus contract (#21)

Runtime acceptance and production enablement remain pending.

## TDD evidence

Initial harness attempts reported `return = None` and `else = None` translation errors; corrected before source implementation. Those errors are test harness defects, not product counterexamples.

Definitive RED, before either production file changed:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_alert_chain tests.unit.test_horde_stimulus -v
```

Actual selected output lines:

```text
test_hops_attenuation_emitter_and_recipient_dedupe_inherit_root (tests.unit.test_alert_chain.AlertChainTests.test_hops_attenuation_emitter_and_recipient_dedupe_inherit_root) ... ok
test_missing_inherited_root_cannot_seed_fresh_root (tests.unit.test_alert_chain.AlertChainTests.test_missing_inherited_root_cannot_seed_fresh_root) ... ok
test_native_adapter_explicitly_labels_seed_and_relay_as_heard (tests.unit.test_alert_chain.AlertChainTests.test_native_adapter_explicitly_labels_seed_and_relay_as_heard) ... FAIL
test_queue_hard_cap_16_root_cap_8_and_root_id_exhaustion (tests.unit.test_alert_chain.AlertChainTests.test_queue_hard_cap_16_root_cap_8_and_root_id_exhaustion) ... ok
test_radius_strength_cooldown_geometry_and_dead_recipients_fail_closed (tests.unit.test_alert_chain.AlertChainTests.test_radius_strength_cooldown_geometry_and_dead_recipients_fail_closed) ... ok
test_recipient_cap_12_work_limit_and_scan_limit_24 (tests.unit.test_alert_chain.AlertChainTests.test_recipient_cap_12_work_limit_and_scan_limit_24) ... ok
test_recipient_rotation_and_two_bounded_geometry_tests_remain (tests.unit.test_alert_chain.AlertChainTests.test_recipient_rotation_and_two_bounded_geometry_tests_remain) ... ok
test_root_ttl_30_queue_window_2_and_no_lifetime_refresh (tests.unit.test_alert_chain.AlertChainTests.test_root_ttl_30_queue_window_2_and_no_lifetime_refresh) ... ok
test_server_alive_noncalm_and_tracked_limit_are_required (tests.unit.test_alert_chain.AlertChainTests.test_server_alive_noncalm_and_tracked_limit_are_required) ... ok
test_cohort_comparison_uses_category_then_recency_then_strength (tests.unit.test_horde_stimulus.HordeStimulusTests.test_cohort_comparison_uses_category_then_recency_then_strength) ... FAIL
test_expired_future_invalid_strength_and_hops_are_never_chosen (tests.unit.test_horde_stimulus.HordeStimulusTests.test_expired_future_invalid_strength_and_hops_are_never_chosen) ... 
test_expired_future_invalid_strength_and_hops_are_never_chosen (tests.unit.test_horde_stimulus.HordeStimulusTests.test_expired_future_invalid_strength_and_hops_are_never_chosen) ... FAIL
test_frozen_selection_never_refreshes_original_or_copy (tests.unit.test_horde_stimulus.HordeStimulusTests.test_frozen_selection_never_refreshes_original_or_copy) ... FAIL
test_individual_helper_and_cohort_wrapper_agree_for_same_inputs (tests.unit.test_horde_stimulus.HordeStimulusTests.test_individual_helper_and_cohort_wrapper_agree_for_same_inputs) ... FAIL
test_live_observed_visual_beats_newer_sound_and_reports_reason (tests.unit.test_horde_stimulus.HordeStimulusTests.test_live_observed_visual_beats_newer_sound_and_reports_reason) ... FAIL
test_memory_is_explicit_but_never_promoted_to_observation (tests.unit.test_horde_stimulus.HordeStimulusTests.test_memory_is_explicit_but_never_promoted_to_observation) ... FAIL
test_nonadmitted_heard_input_is_ignored_including_self_voice (tests.unit.test_horde_stimulus.HordeStimulusTests.test_nonadmitted_heard_input_is_ignored_including_self_voice) ... FAIL
test_sound_beats_expired_visual_or_unknown_retained_memory (tests.unit.test_horde_stimulus.HordeStimulusTests.test_sound_beats_expired_visual_or_unknown_retained_memory) ... 
test_source_slots_do_not_upgrade_wrong_provenance (tests.unit.test_horde_stimulus.HordeStimulusTests.test_source_slots_do_not_upgrade_wrong_provenance) ... FAIL
AssertionError: Missing authored contract: HCHordeStimulus.c: Category(
AssertionError: Missing authored contract: HCHordeStimulus.c: Category(
AssertionError: Missing authored contract: HCHordeStimulus.c: Category(
AssertionError: Missing authored contract: HCHordeStimulus.c: Category(
AssertionError: Missing authored contract: HCHordeStimulus.c: Category(
AssertionError: Missing authored contract: HCHordeStimulus.c: Category(
AssertionError: Missing authored contract: HCHordeStimulus.c: Category(
AssertionError: Missing authored contract: HCHordeStimulus.c: Category(
AssertionError: Missing authored contract: HCHordeStimulus.c: Category(
AssertionError: Missing authored contract: HCHordeStimulus.c: Category(
AssertionError: Missing authored contract: HCHordeStimulus.c: Category(
AssertionError: Missing authored contract: HCHordeStimulus.c: Category(
AssertionError: Missing authored contract: HCHordeStimulus.c: Category(
AssertionError: Missing authored contract: HCHordeStimulus.c: Category(
AssertionError: Missing authored contract: HCHordeStimulus.c: Category(
AssertionError: Missing authored contract: HCHordeStimulus.c: Category(
AssertionError: Missing authored contract: HCHordeStimulus.c: Category(
Ran 18 tests in 0.947s
FAILED (failures=18)
exit=1
```

GREEN using the same command after implementation:

```text
Ran 18 tests in 1.523s
OK
exit=0
```

After strengthening the queue-cap fixture to avoid a root-cap false positive,
focused verification used the same command again:

```text
Ran 18 tests in 2.832s
OK
exit=0
```

Regression checks:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit
```

```text
Ran 2379 tests in 78.556s
OK (skipped=1)
exit=0
```

```sh
python3 -B -m tools.validate.bdd
```

```text
Ran 1276 tests in 31.579s
OK (skipped=1)
Bound offline scenarios: 61; runtime acceptance: NOT EXECUTED
exit=0
```

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p 'test_script_*.py' -v
```

```text
Ran 8 tests in 0.893s
OK
exit=0
```

The full discovery includes the existing infected wave/routes/completion suites
that inspect both source files. Expected negative-case CLI diagnostics appeared
in full/BDD output; neither command reported test failures. The two new suites
are covered by full discovery; their dedicated Gherkin binding is a WP1 follow-up,
not claimed by the 61 existing bound scenarios.

## Files changed and traceability

Production/test write set:

- `mods/HollowCountry/scripts/4_World/Infected/HCHordeStimulus.c`: explicit
  category/reason enums, classifier, shared selector, shared cohort comparison
  and wrapper; freezing preserves every clue field without mutation.
- `mods/HollowCountry/scripts/4_World/Infected/HCAlertChain.c`: explicit heard
  provenance on seed and emitted clue, source-contract documentation and native
  citations. No control flow, limits, geometry, positions or time calculations
  changed.
- `tests/unit/test_horde_stimulus.py`: nine synthetic behavioral tests executing
  authored source, including a 100-case visual/heard/admission matrix comparing
  individual selector results with frozen cohort choices.
- `tests/unit/test_alert_chain.py`: nine synthetic tests executing authored relay
  bodies with explicit native collaborators; two-ray presence is source-checked.

Requested delivery files: this report and `.banso-writer/commit-message`.
No shared Module/State/Navigation/Policy/Profiles file was edited.

Read AGENTS.md, runtime contract, audit §6.3 category row, unranked priority note,
WP6 ownership row and all three audit counterexamples. Those counterexamples
concern WP2/WP4 and remain untouched. The requested spec paths are absent in this
worktree. Read the audit-identified design copies at
`/code/dayzsa_mods/docs/SPECIFICATION.md` and
`/code/dayzsa_mods/docs/specs/001-survival-overhaul/spec.md`, plus their plan,
completion plan and task ledger. Their equivalence to historical worktree specs
is unproven. Active instructions override their later public/load assumptions;
this task remains private source work with a 3–6-player provisional target.

Banso/SDD mapping: #21 / audit WP6 / SPECIFICATION §6.3 / FR-009 and NFR-001,
NFR-002, NFR-003, NFR-005, NFR-006. Scope tasks: define contract → authored-source
RED → implement selector and adapter labels → focused GREEN → full regression
and existing BDD → WP1 integration handoff. No orchestrator lifecycle, git, native
process, public publication or write under `/mnt/d` was performed.

## Selector contract and integration request

Exact public signature:

```c
static HCInfectedClue SelectClue(HCInfectedClue visual, HCInfectedClue heard, bool admitExternalHeard, float now, out int reason)
```

Returns the original chosen clue or null. `ChooseClue(actor, now, hearing)` calls
this selector with `hearing && actor.HeardExternally`, then copies all fields for
cohort use. `PreferClue` uses the same `Category` classification, followed by
newer Observed, then greater Strength; an exact tie retains the previous clue.

| Category | Meaning | Eligible destination |
| --- | --- | --- |
| NONE=0 | null input | No |
| MEMORY=1 | expired, unknown-provenance or otherwise invalid retained evidence | No |
| HEARD=2 | live provenance 1, actual external local native voice | Only when admitted in the heard slot |
| VISUAL=3 | live provenance 2 from a qualified visual observation adapter | Only in the visual slot |

A newer sound cannot override live qualified visual evidence. A valid sound wins
when the visual clue is expired or unknown. An expired visual reference is memory,
not current visual evidence. IsLive also rejects future timestamps, invalid TTL,
strength and hop values. Unknown/expired memory cannot supply a destination or
be revived by selection. Wrong-slot provenance is rejected. Nonadmitted hearing
is not inspected or selected, including self-vocalization. No hidden coordinates,
entity queries, timestamp updates or new source adapters are introduced.

Live provenance 2 is a bounded observation sample, not proof of continuous LOS.
The producer must establish visual qualification; a retained native target plus
geometry cannot do that. WP2/WP1 still own that separate defect and admission.
When visual evidence is unknown it must remain unknown/invalidated, not be stamped
as new provenance 2. This selector intentionally adds no unobserved sight API.

The Module owner should replace the initial block in `TryInvestigate`, from
`HCInfectedClue clue;` through the two visual/heard selection `if` blocks, with
exactly:

```c
        int stimulusReason;
        bool admitExternalHeard = m_Chains && m_Config.EnableSupplementaryChains && actor.HeardExternally;
        HCInfectedClue clue = HCHordeStimulus.SelectClue(actor.Visual, actor.Heard, admitExternalHeard, m_Now, stimulusReason);
```

Continue immediately with the existing `bool observedClue = clue != null;` and
all existing investigation admission/work/route logic. `stimulusReason` is
declared before the out call. WP1 must additionally combine its qualification
admission with `admitExternalHeard`; requested preferences alone cannot qualify a
path. This replacement is a handoff, not an edit applied to the shared Module.
The test matrix proves agreement between the helper intended for the individual
caller and the existing cohort wrapper, not that the old Module caller is fixed.

| Reason code | Name | Return |
| --- | --- | --- |
| 0 | HC_STIMULUS_NO_ADMISSIBLE_CLUE | null; absent, nonadmitted or wrong-slot input |
| 1 | HC_STIMULUS_SELECTED_VISUAL | live qualified visual clue |
| 2 | HC_STIMULUS_SELECTED_HEARD | admitted live heard clue |
| 3 | HC_STIMULUS_RETAINED_ONLY | null; memory/invalid evidence with no eligible alternative |

An ignored heard input cannot affect the reason. If eligible visual evidence is
present, it wins immediately without inspecting hearing. Category codes and
reason codes are separate enum domains; their numeric values are not interchangeable.

## Limits preserved and pinned

- At most 8 live roots; root IDs stop before 2,000,000,000; inherited missing,
  duplicate, exhausted or expired roots cannot restart while the clue is live.
- Root lifetime at most 30 seconds; relay expiry remains the original root expiry.
  Queued emissions expire after the two-second processing window or clue expiry.
- At most two hops; each relay halves normalized strength; no forced relay sound.
- Queue cap at most 16 and lower requested caps respected; actors count 1–24.
- At most 12 deduped recipients per root, including seed; emitter dedupe prevents
  repeats; external recipients receive a ten-second cooldown.
- One tracked scan charged per work item, including rejection and queue removal;
  bounded actor scan, shared work quota and rotating recipient cursor preserved.
- Conservative radius 15 × strength, live/cooldown checks, policy acceptance and
  at most two geometry rays preserved. Geometry is not proof of player audibility.

A whitespace/comment-normalized comparison against the read-only audit source
confirmed all pre-existing HCAlertChain code is identical after removing only
the two new explicit `Provenance = 1` writes. Syntax/identifier tests passed using
the installed cache. A separate read-only source check found no ternary or
leading logical operator and maximum '+' counts per statement of 0 (stimulus)
and 2 (chain), below the limit of 8. No new logging or string conversion exists.

## Native API evidence

Inspected directly under
`/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`:

| Native surface retained in alert code | file:line |
| --- | --- |
| GetGame / IsServer | `3_Game/gameplay.c:636`; `3_Game/Global/Game.c:1120` |
| IsAlive / GetPosition | `3_Game/Entities/Object.c:517`; `3_Game/Entities/Object.c:287` |
| GetMindStateSynced / native voice callback | `4_World/Entities/Creatures/Infected/ZombieBase.c:182`; `4_World/Entities/Creatures/Infected/ZombieBase.c:556` |
| MINDSTATE_CALM | `3_Game/Entities/DayZInfected.c:13` |
| Math.Min / vector.DistanceSq | `1_Core/proto/EnMath.c:553`; `1_Core/proto/EnConvert.c:210` |
| RaycastRV, including out arguments | `3_Game/Global/DayZPhysics.c:199` |
| Fire/view intersection enum | `3_Game/constants.c:33`; `3_Game/constants.c:34` |
| Array Count/Clear/Find/Insert/Remove | `1_Core/proto/EnScript.c:380`, `:385`, `:394`, `:407`, `:463` |
| Set Count/Clear | `1_Core/proto/EnScript.c:743`, `:744` |

The stimulus selector uses authored DTO/policy methods only. No new native API
is called. Native declarations are source evidence, not new engine observations.

## Remaining gaps

1. WP1 must apply the exact TryInvestigate replacement, combine qualified
   capability admission, and bind the new behavioral suites into its Gherkin
   ownership. Existing individual Module logic still has the audited inconsistency.
2. WP2/WP1 must resolve visual producer qualification and invalidate unknown sight;
   this helper cannot authenticate a clue already mislabeled provenance 2.
3. DayZDiag compilation, normal PBO/server validation, source-bound runtime
   qualification, two-client sound/visibility correlation, real native hearing and
   geometry behavior remain pending. Python translations are not an Enforce VM.
4. Gunshot/rummage/other adapters remain native-only until measured gaps justify
   a supplementary adapter. Complete multi-category native coverage is not claimed.
5. Work limits are preserved pilot bounds, not measured budgets at 3–6 players.
   Runtime load, delay, environmental attenuation and overload fairness need trials.

No broad issue, experiment, gameplay acceptance or production feature was marked
accepted by this source package.
