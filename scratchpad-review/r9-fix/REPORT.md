# Taped-light audit fix round 9 (issue #56) - writer report

Source/test authoring only; nothing run against DayZ, Wine or the network. Acceptance stays PENDING (tier S, client pending).
The rendered Enforce hook was NOT changed (only the synthetic emulator in the probe tests), so no new lint surface.

## Files changed
- tools/audit/taped_light_report.py
- tests/unit/test_taped_light_report.py (new class AliasConflictScopeTests, new TierSTests test)
- tests/unit/test_taped_light_probe.py (emulator: bone_object="other", bone_serial, World.lifecycle; two new/strengthened tests)
- tools/setup/taped_light_probe.py: unchanged. Scratch only: scratchpad-review/r9-fix/.

## Implementation
- `_proxies` now returns ("ok", rows, truncated, res, conflict). A conflict (one identity read two ways, or one config class
  read two ways) records every slot any contradicting copy lists (exact names) and `all` when a copy's slot list was cut. The
  contradicting identities/classes yield no rows; coherent aliases still collapse to one row.
- `_implicated(proxies, slot)` + `_model_evidence`: an implicated slot gets pending/proxy_evidence_malformed with
  `conflict: True`, ahead of selection evidence. An unrelated slot is judged on the remaining rows.
- `_evaluate_slot`: a conflict-marked model returns pending before any attach/refusal/prerequisite branch (P2-1).
- `_evaluate_light`: the no-compatible-slot exit is pending when the conflict implicates a slot the host owns.
- `_evaluate_host`: host reason `proxy_alias_conflict` (host pending), added to SIBLING_SCOPED_REASONS so it does not
  invalidate independently valid pairs (P2-2).
- P2-3: exact `slot in set(item["inventory_slots"])` and exact `set(slot_names)` for the other-light-slot test; casefolding kept
  only for proxy paths and config class spellings.
- P2-4: `_spawn_control` returns {"status":"malformed"} for a non-dict before any membership test.

## RED (before implementation), scratchpad-review/r9-fix/RED1-report.log
`python3 -m unittest tests.unit.test_taped_light_report.AliasConflictScopeTests tests.unit.test_taped_light_report.TierSTests`
-> `Ran 36 tests`, `FAILED (failures=27, errors=5)`:
- P2-1: 12 subtests fail in test_a_light_alias_conflict_keeps_the_pair_pending_whatever_the_attach_outcome_in_either_order
  (direct refusal, accepted attach, create failed, satisfied/unmet/missing prerequisite, variant refused; both orders), plus
  test_a_light_alias_conflict_keeps_a_light_that_fits_no_host_slot_pending, test_a_host_without_a_native_light_slot_stays_pending_for_the_conflict,
  test_an_implicated_slot_is_withheld_even_when_the_model_names_a_selection_for_it.
- P2-2: test_an_unrelated_alias_conflict_keeps_the_host_pending_and_an_independent_light_pair_valid (3 conflict=True orders),
  test_copies_that_disagree_about_the_slot_..., test_a_copy_with_a_truncated_slot_list_..., test_two_identities_reading_one_config_class_two_ways_...
- P2-3: test_proxy_slot_membership_is_exact_and_case_sensitive [weaponflashlight, WEAPONFLASHLIGHT, WeaponFlashlight],
  test_another_light_slot_is_recognised_only_by_its_exact_name.
- P2-4: test_a_mistyped_spawn_control_is_malformed_and_never_aborts_the_report: ERROR for null, number, float, true, false (TypeError).
- P3-1: R02/P08/P09/P10 tests pass on correct code; their RED is the mutant failing (below).

## GREEN
- GREEN1-report.log: `Ran 179 tests ... OK` (tests.unit.test_taped_light_report)
- GREEN2-probe.log: `Ran 125 tests ... OK` (tests.unit.test_taped_light_probe)
- Sol's scratch regressions (r8-sol-review/test_review_regressions.py): `Ran 6 tests ... OK` (was 3 failures, 1 error).

## Mutants (scratchpad-review/r9-fix/mutations.py; in-memory 286-test suite, CLI/stager excluded as in the review)
- R02 (coherent aliases kept as duplicate rows): KILLED, failures=3 (test_coherent_aliases_collapse_into_exactly_one_parsed_evidence_row)
- P08 (bone identity -> presence): KILLED, failures=1 (test_the_bone_object_after_attach_is_compared_with_the_attached_light [a distinct live object])
- P09 (variant HCTLSlotBones removed): KILLED, failures=1 (test_the_variant_host_reads_its_own_bones_after_its_handguard)
- P10 (control immediate release removed): KILLED, failures=1 (test_the_control_is_deleted_before_the_next_object_is_spawned)
- R03 reintroduced (case-insensitive slot membership): KILLED, failures=10
- Extra mutants on the new logic, all KILLED: N1 conflict not outranking attach (12), N2 conflict implicates every slot (3),
  N3 implicates none (44), N4 truncation not implicating all (1), N5 host loses conflict reason (22), N6 reason invalidates
  every pair (3), N7 no-compatible exit ignores conflict (1), N8 non-dict spawn_control unguarded (errors=5), N9 first copy only (14).
- RED logs for P3: RED2-R02.log, RED2-P08.log, RED2-P09.log, RED2-P10.log.

## Full suite (scratchpad-review/r9-fix/full.log)
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit` -> `Ran 2430 tests in 121.367s`, `OK (skipped=1)`.
`git diff --check` clean.

## probe-006 rejoin (classification probe-003 + observations probe-006, current report)
server_qualified=26 geometry_missing=0 not_server_evidencable=415 excluded=141 pending=2 hosts=584.
Pairs: server_qualified 26, geometry_missing 28, not_server_evidencable 830, pending 2. Integrity: cleanup clean, no issues.
R12 and Mich2001Helmet pending with pending_client. No proxy_alias_conflict anywhere (identical to the r8 counts).

## Remaining gaps / decisions for review
- Judgement calls: a conflict implicating a slot the host owns makes a light that fits none of the host's slots pending
  (no_compatible_native_slot would otherwise ignore it); a host with no native light slot is host-pending with its pairs left
  not_server_evidencable. A conflict among copies that all list unknown/no slots implicates nothing but the host-level reason.
- Generic malformed proxy evidence (bad name, own-bookkeeping contradictions) is still host-wide and still loses to a native
  refusal in the refusal branches; only alias conflicts were changed, as the review specified.
- Emulator additions (bone_serial, bone_object="other", World.lifecycle) are synthetic; nothing here proves engine behavior.
  Real native compile, DayZDiag, PBO/server testing and two-client checks remain pending.
