# Round 10 fix report (taped-light #56)

Source of the work: Sol review of r9 (`scratchpad-review/r9-solreview/REPORT.md`, MERGE-WITH-FIXES). Synthetic fixtures only; offline tests establish no DayZ behavior. Acceptance stays PENDING.

## Files changed
- `tools/audit/taped_light_report.py`
- `tests/unit/test_taped_light_report.py` (new class `ConflictPrecedenceTests`, 12 tests, plus `import itertools`)
- Not changed: `tools/setup/taped_light_probe.py`, `tests/unit/test_taped_light_probe.py`, the rendered Enforce hook.

## P2-1 parse-error exits drop conflicts
- `_proxies` now always returns the 5-tuple `(kind, rows, truncated, res, conflict)`. Unreadable entries (bad row, unparseable name, non-legacy class mismatch) and legacy whole-path class rows no longer return early: they set the status flag and the scan continues, so readable conflicting rows are still collected. Pre-loop failures return `("malformed", [], False, None, None)`; kind "malformed" yields no rows.
- `_implicated` reads `proxies[4]` for any kind. `_model_evidence` checks the implicated conflict first (before the generic malformed check, selection route, refusal), with `conflict: True`. `_evaluate_host` adds the sibling-scoped `proxy_alias_conflict` whenever `proxies[4]` is set. Independent pairs are not invalidated.
- RED (`RED1-report.log`): 11 tests, failures=16, errors=20. The 20 errors are `IndexError: tuple index out of range` on `parsed[4]` for the old 1-tuple `("mismatch",)`/`("malformed",)` (the dropped conflict); the 16 failures are rule A (below).
- GREEN: new class OK.

## P2-2 rule A spelling signature
- `lookup` now uses `_path(values["model"])`; `res_key` uses `_selection_key(selection)` = `_proxy_name` (path normalised, instance number kept) with raw-text fallback. Slot names, vertices, counts, exists flags stay exact. Raw rows/diagnostics unchanged (a test asserts the raw model is kept).
- RED: 16 `AssertionError: {'slots': frozenset({'weaponFlashlight'}), 'all': False} is not None` (spelling variants of model path and resolution selection falsely a conflict, 8 each, both orders). GREEN: collapse into one row, `server_qualified`, `proxy_alias_collapsed == 1`.
- Substantive differences (model basename, other model, resolution instance, vertex, slot-name case, slot count) are still conflicts: tested.

## P3 tests
- M03 killer: `test_conflict_slot_names_are_exact_so_a_case_changed_name_implicates_no_native_slot`.
- M08 killer: `test_a_config_class_spelling_alone_collapses` and `test_a_config_class_spelling_of_two_instances_is_still_one_class`.
- Reviewer adversarial cases ported: legacy-mismatch (6 permutations, with a native selection), unreadable sibling (6 permutations x refusal/selection), model-path and resolution spelling collapse (both orders), class spelling alone, three-reading union (6 permutations), case-changed slot names. Added: wrong-class sibling permutations, unrelated-conflict scope under bad siblings, unchanged status without a conflict.

## Verification
- Focused: `python3 -m unittest tests.unit.test_taped_light_report tests.unit.test_taped_light_probe`: Ran 316, OK (`GREEN-focused.log`, `GREEN-focused2.log`; with `tests.unit.test_script_syntax` also OK).
- Full suite once: `Ran 2441 tests in 121.145s`, `OK (skipped=1)` (`full.log`). `git diff --check` clean.
- Reviewer scripts: `r9-solreview/test_adversarial.py` 8 OK (was 16 failures); `r8-sol-review/test_review_regressions.py` 6 OK. Note that running the former rewrote the tracked `r9-solreview/counterexamples.json` scratch file.
- Mutants (`mutations.py`, `mutations-x11.py`; baseline 297 tests per run, CLI/stager excluded): M03 KILLED, M08 KILLED, X1 (old ok-only implicated) KILLED, X2 (malformed drops conflict) KILLED, X3 (mismatch drops conflict) KILLED, X4 (host reason ok only) KILLED, X5 (malformed before implicated) KILLED, X6 (raw model path) KILLED, X7 (raw res selection) KILLED, X8 (res instance number dropped) KILLED, X9 (unreadable sibling stops scan) KILLED, X10 (legacy sibling stops scan) KILLED, X12 (model basename dropped) KILLED. X11 (wrong-class sibling stops scan) first SURVIVED; added `test_a_conflict_survives_a_wrongly_named_config_class_sibling_in_every_order`, then KILLED.
- probe-006 rejoin (classification probe-003 + observations probe-006), unchanged: server_qualified=26 geometry_missing=0 not_server_evidencable=415 excluded=141 pending=2 hosts=584; pairs 26/28/830/2; integrity no issues; R12 and Mich2001Helmet pending (`pending_client`); no `proxy_alias_conflict` host (`rejoin.log`).

## Remaining gaps
- Generic malformed evidence that is not an alias conflict (an unreadable sibling with no conflicting copies) still loses to a native refusal on a slot, as before r10; only implicated conflicts take precedence over refusals.
- Native compile, DayZDiag, PBO/server and two-client checks remain pending.
