# WP3 round 2 — infected competence probe (#18 / #19)

Runtime acceptance: **PENDING**. Source/package authoring only; no DayZ, Wine,
PowerShell, client launch, or write under `/mnt/d`. Git metadata was not written.
Registration rows are unchanged. This report and its evidence are local review
artifacts; no game XML/config, assets, native dumps, keys, profiles, or credentials
were copied into the repository.

## Files changed and requirement trace

- `tools/setup/infected_competence_probe.py`: F1–F8 and stock-placement survey.
- `tests/unit/test_infected_competence.py`: explicit synthetic fixtures, regression
  scenarios, per-case error regexes, independent client-field mutations, hook
  structure, staging negatives, survey derivation/refusals.
- `scratchpad-review/wp3-r2/`: this report, actual test output, mutation evidence
  and a supplemental runner for displaced mutation patterns.
- `.banso-writer/commit-message`: commit-message handoff only, excluded from commit.

Read `AGENTS.md`, the runtime implementation contract, the task brief and the
review/helper files. The worktree does not contain the ignored canonical
`docs/SPECIFICATION.md` / `docs/specs/001-survival-overhaul/{spec,plan,tasks}.md`;
read those from `/code/dayzsa_mods/` without modifying them. Current user decisions
supersede older destination/load statements there. Applied the Banso CLI skill's
confined-worker instructions; no orchestration/lifecycle or git writes performed.
This source task supports T018/T019, FR-008/FR-011, AC-007/AC-010 and the AI/injury
and audio experiment matrix. It does not accept those gameplay requirements.

## Implemented behavior

- F1: `HCICStep` records authored anchor/spawn Y, replaces both Y coordinates with
  `SurfaceY`, then records surface Y before querying, raycasting or spawning.
  Query radius is bounded at 5 m for origin-height tolerance; ambiguity and the
  128-object/proxy limits still refuse. Four explicit Y fields are validated;
  authored-height binding allows 1 cm for native float/string round trips.
- F2: completed rows keep `per_trial_ms + 1000`; inconclusive rows allow the plan
  cap `len(trials) * (per_trial_ms + 1100) + 30000`. Tests cover 6070 ms, the exact
  cap, cap + 1 and a completed overrun.
- F3: renamed `crawl_transition` to **`crawl_health_only`**. Its canonical reason
  explicitly says "hit-path not exercised". Both injury rows require declining
  left-leg health in the hook and receipt validator. `DecreaseHealth` remains a
  diagnostic health-only stimulus; there is no claim it calls `EEHitBy` or
  produces crawl. The four baseline kinds are one shared observation path;
  both injury kinds are one health-only path. Raw trial counts are repetitions,
  and `completed_observation_paths` reports each path once.
- F4: stage copies `serverDZ.cfg` byte-for-byte without a `maxPlayers` rewrite.
  Source/staged config hashes must agree. Client identities still abort the hook.
- F5: validate/report print `fixture_status_counts` across all planned trials and
  an explicit unqualified-fixture limitation. CLI stage warns when
  `--trials-json` is omitted. Counts include client-required fixtures and never
  establish the #18 building/angle denominator.
- F6: exact expected error regex per mutation; each client field tested
  independently, with coherent cleanup/totals for the spawned-field case.
  Method-scoped hook assertions cover cleanup at Next/Finish/mission end,
  ownership, both deletion increments, identity abort, global cap, output bound,
  sentinel text/order, door/ray/query loop bounds, ECE flags, watchdog, leg guard,
  ambiguity and client-required skip. Stage native-drift/lint and input/refusal
  tests preserve the requested boundaries.
- F7: `HCICNext` explicitly assigns zero elapsed time for client-required rows.
- F8: exact keys required in receipt document, samples, doors and trial records.
- Survey: `survey --mapgrouppos STOCK_XML --output trials.json` reads bounded XML
  through CE `parse_placements`, chooses sorted classes (default limit 3), and
  uses CE `select_placements` for evenly spaced entries (default 1 per class).
  `--classes`, `--class-limit`, `--per-class`, `--spawn-offset-m` customize selection.
  Anchor is the group position; candidate spawn offset defaults to 3 m with
  `x += 3*sin(yaw)`, `z += 3*cos(yaw)`, taking yaw from `rpy[2]` in degrees.
  Y is resolved only at runtime. Output is a JSON envelope containing
  `stock-derived` trials, stock SHA-256 and all selection parameters; stage
  retains the provenance in its plan. Existing output is refused. XML is never
  copied. All survey test XML is tiny and explicitly synthetic.

Native evidence: `Game.c:1176` proves the inspected `SurfaceY` signature and is
now in `NATIVE`. Re-read `ZombieBase.c:811–826,981–1000`: the crawl-transition
assignment is in `EEHitBy`, so the allowed health-only relabel was selected
instead of introducing a new ammo/damage hit-path experiment. Source inspection
and Python checks do not prove engine behavior.

## TDD evidence — actual commands and output

Tests were authored before the corresponding source fix. Each block below
contains the saved command's actual output, including failures. F6 is a test
strengthening change: an isolated copy with the reviewer's H5 cleanup removal
supplies the RED, and restoring the cleanup supplies the GREEN; production source
was never temporarily mutated. Other reviewer mutations also run only on copies.

### F1 terrain height

RED: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.HookTests.test_f1_surface_height_precedes_queries_and_spawn_and_is_recorded -v`

```text
test_f1_surface_height_precedes_queries_and_spawn_and_is_recorded (tests.unit.test_infected_competence.HookTests.test_f1_surface_height_precedes_queries_and_spawn_and_is_recorded) ... FAIL

======================================================================
FAIL: test_f1_surface_height_precedes_queries_and_spawn_and_is_recorded (tests.unit.test_infected_competence.HookTests.test_f1_surface_height_precedes_queries_and_spawn_and_is_recorded)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 58, in test_f1_surface_height_precedes_queries_and_spawn_and_is_recorded
    self.assertIn(call, step)
AssertionError: 'anchor[1] = GetGame().SurfaceY(anchor[0], anchor[2]);' not found in '\n    {\n        if (m_Done)\n            return;\n        if (!HCICNoClients())\n            return;\n        if (GetGame().GetTime() - m_Begin > 84900)\n        {\n            HCICFinish("partial");\n            return;\n        }\n        if (m_Index >= 9)\n        {\n            HCICFinish("complete");\n            return;\n        }\n        m_Trial = new HCICTrial;\n        string structureName;\n        vector anchor;\n        vector spawnPoint;\n        HCICSetup(m_Index, structureName, anchor, spawnPoint);\n        m_Receipt.trials.Insert(m_Trial);\n        m_TrialBegin = GetGame().GetTime();\n        if (m_Trial.support_state == "client_required")\n        {\n            m_Trial.status = "client_required";\n            HCICNext();\n            return;\n        }\n        Building structure = HCICStructure(structureName, anchor);\n        if (!structure)\n        {\n            m_Trial.reason = "structure_missing_ambiguous_or_query_budget";\n            HCICNext();\n            return;\n        }\n        if (!HCICGeometry(spawnPoint))\n        {\n            m_Trial.reason = "footprint_ray_hit";\n            HCICNext();\n            return;\n        }\n        m_Owned = GetGame().CreateObjectEx("ZmbF_JournalistNormal_Blue", spawnPoint, ECE_PLACE_ON_SURFACE|ECE_INITAI);\n        if (m_Owned)\n        {\n            m_Trial.spawned = 1;\n            m_Receipt.spawned = m_Receipt.spawned + 1;\n        }\n        m_Actor = ZombieBase.Cast(m_Owned);\n        if (!HCICSampleActor())\n        {\n            m_Trial.reason = "spawn_controller_or_no_target_control_failed";\n            HCICNext();\n            return;\n        }\n        if (m_Trial.kind == "door_state")\n        {\n            int doorCount = structure.GetDoorCount();\n            if (doorCount < 1 || doorCount > 16)\n            {\n                m_Trial.reason = "door_budget_or_no_doors";\n                HCICNext();\n                return;\n            }\n            for (int doorIndex = 0; doorIndex < doorCount && doorIndex < 16; doorIndex++)\n            {\n                HCICDoor doorRow = new HCICDoor;\n                doorRow.index = doorIndex;\n                doorRow.opened = structure.IsDoorOpen(doorIndex);\n                doorRow.locked = structure.IsDoorLocked(doorIndex);\n                m_Trial.doors.Insert(doorRow);\n            }\n        }\n        if (m_Trial.kind == "limb_damage" || m_Trial.kind == "crawl_transition")\n        {\n            float legHealth = m_Actor.GetHealth("LeftLeg", "Health");\n            if (legHealth <= 0 || legHealth > 10000)\n            {\n                m_Trial.reason = "invalid_initial_leg_health";\n                HCICNext();\n                return;\n            }\n            m_Actor.DecreaseHealth("LeftLeg", "Health", legHealth);\n        }\n        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCICObserve, 5000, false);\n    }\n\n'

----------------------------------------------------------------------
Ran 1 test in 0.001s

FAILED (failures=1)
```

GREEN: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.HookTests.test_f1_surface_height_precedes_queries_and_spawn_and_is_recorded -v`

```text
test_f1_surface_height_precedes_queries_and_spawn_and_is_recorded (tests.unit.test_infected_competence.HookTests.test_f1_surface_height_precedes_queries_and_spawn_and_is_recorded) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.001s

OK
```

### F1 authored float round trips

RED: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.StagingAndReceiptTests.test_f1_authored_height_roundtrip_and_invalid_height_receipts -v`

```text
test_f1_authored_height_roundtrip_and_invalid_height_receipts (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f1_authored_height_roundtrip_and_invalid_height_receipts) ... ERROR

======================================================================
ERROR: test_f1_authored_height_roundtrip_and_invalid_height_receipts (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f1_authored_height_roundtrip_and_invalid_height_receipts)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 510, in test_f1_authored_height_roundtrip_and_invalid_height_receipts
    probe.validate(self.dest)  # Enforce floats/ToString need a small numeric tolerance.
    ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/code/hc-worktrees/wp3-integ/tools/setup/infected_competence_probe.py", line 885, in validate
    raise ValueError('authored terrain height mismatch')
ValueError: authored terrain height mismatch

----------------------------------------------------------------------
Ran 1 test in 0.177s

FAILED (errors=1)
```

GREEN: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.StagingAndReceiptTests.test_f1_authored_height_roundtrip_and_invalid_height_receipts -v`

```text
test_f1_authored_height_roundtrip_and_invalid_height_receipts (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f1_authored_height_roundtrip_and_invalid_height_receipts) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.188s

OK
```

### F2 elapsed bounds

RED: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.StagingAndReceiptTests.test_f2_inconclusive_elapsed_uses_plan_cap_completed_keeps_tight_bound -v`

```text
test_f2_inconclusive_elapsed_uses_plan_cap_completed_keeps_tight_bound (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f2_inconclusive_elapsed_uses_plan_cap_completed_keeps_tight_bound) ... ERROR

======================================================================
ERROR: test_f2_inconclusive_elapsed_uses_plan_cap_completed_keeps_tight_bound (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f2_inconclusive_elapsed_uses_plan_cap_completed_keeps_tight_bound)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 265, in test_f2_inconclusive_elapsed_uses_plan_cap_completed_keeps_tight_bound
    self.assertEqual(probe.validate(self.dest)['denominator']['inconclusive'], 1)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/code/hc-worktrees/wp3-integ/tools/setup/infected_competence_probe.py", line 760, in validate
    _integer(row.get('elapsed_ms'), 0, plan['probe']['per_trial_ms'] + 1000, 'trial elapsed')
  File "/code/hc-worktrees/wp3-integ/tools/setup/infected_competence_probe.py", line 137, in _integer
    raise ValueError(f'{name} must be an integer {low}..{high}')
ValueError: trial elapsed must be an integer 0..6000

----------------------------------------------------------------------
Ran 1 test in 0.118s

FAILED (errors=1)
```

GREEN: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.StagingAndReceiptTests.test_f2_inconclusive_elapsed_uses_plan_cap_completed_keeps_tight_bound -v`

```text
test_f2_inconclusive_elapsed_uses_plan_cap_completed_keeps_tight_bound (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f2_inconclusive_elapsed_uses_plan_cap_completed_keeps_tight_bound) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.129s

OK
```

### F3 health-only evidence and shared coverage

RED: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.StagingAndReceiptTests.test_f3_health_only_labels_drop_and_shared_coverage -v`

```text
test_f3_health_only_labels_drop_and_shared_coverage (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f3_health_only_labels_drop_and_shared_coverage) ... FAIL

======================================================================
FAIL: test_f3_health_only_labels_drop_and_shared_coverage (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f3_health_only_labels_drop_and_shared_coverage)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 279, in test_f3_health_only_labels_drop_and_shared_coverage
    self.assertNotIn('crawl_transition', probe.KINDS)
AssertionError: 'crawl_transition' unexpectedly found in {'spawn_lifecycle': ('server_observable', 'Native spawn/state/delete at authored fixed position.'), 'mind_no_target': ('server_observable', 'Two native mind-state samples; target presence invalidates no-target control.'), 'door_state': ('server_observable', 'Read existing door open/locked state only; no contact or opening inference.'), 'footprint_geometry': ('server_observable', 'Four short view-geometry rays at spawn height; not LOS acquisition or full collision proof.'), 'limb_damage': ('server_observable', 'One LeftLeg DecreaseHealth stimulus; before/after limb health and alive state.'), 'crawl_transition': ('server_observable', 'One LeftLeg health decrease; before/after IsCrawling, without forcing transition or hit callback.'), 'player_los_chase': ('client_required', 'Requires a real connected player and paired LOS/chase observations; server-only has no target.'), 'player_wall_attack': ('client_required', 'Requires real player damage/attack observations through walls with two clients.'), 'audible_pursuit': ('client_required', 'Requires two clients hearing pursuit on surfaces, at distance and through occlusion.')}

----------------------------------------------------------------------
Ran 1 test in 0.001s

FAILED (failures=1)
```

GREEN: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.StagingAndReceiptTests.test_f3_health_only_labels_drop_and_shared_coverage -v`

```text
test_f3_health_only_labels_drop_and_shared_coverage (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f3_health_only_labels_drop_and_shared_coverage) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.126s

OK
```

### F4 unchanged server configuration

RED: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.StagingAndReceiptTests.test_stage_is_fresh_pinned_no_clients_and_never_launches -v`

```text
test_stage_is_fresh_pinned_no_clients_and_never_launches (tests.unit.test_infected_competence.StagingAndReceiptTests.test_stage_is_fresh_pinned_no_clients_and_never_launches) ... FAIL

======================================================================
FAIL: test_stage_is_fresh_pinned_no_clients_and_never_launches (tests.unit.test_infected_competence.StagingAndReceiptTests.test_stage_is_fresh_pinned_no_clients_and_never_launches)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 155, in test_stage_is_fresh_pinned_no_clients_and_never_launches
    self.assertEqual((self.dest / 'serverDZ.cfg').read_bytes(),
AssertionError: b'hostname = "SYNTHETIC";\nmaxPlayers = 0;\n' != b'hostname = "SYNTHETIC";\nmaxPlayers = 6;\n'

----------------------------------------------------------------------
Ran 1 test in 0.118s

FAILED (failures=1)
```

GREEN: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.StagingAndReceiptTests.test_stage_is_fresh_pinned_no_clients_and_never_launches -v`

```text
test_stage_is_fresh_pinned_no_clients_and_never_launches (tests.unit.test_infected_competence.StagingAndReceiptTests.test_stage_is_fresh_pinned_no_clients_and_never_launches) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.322s

OK
```

### F5 fixture status and stage warning

RED: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.StagingAndReceiptTests.test_f5_fixture_status_printed_and_default_stage_warning -v`

```text
test_f5_fixture_status_printed_and_default_stage_warning (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f5_fixture_status_printed_and_default_stage_warning) ... ERROR

======================================================================
ERROR: test_f5_fixture_status_printed_and_default_stage_warning (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f5_fixture_status_printed_and_default_stage_warning)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 304, in test_f5_fixture_status_printed_and_default_stage_warning
    self.assertEqual(result['fixture_status_counts'], {'unqualified-candidate': 9})
                     ~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
KeyError: 'fixture_status_counts'

----------------------------------------------------------------------
Ran 1 test in 0.129s

FAILED (errors=1)
```

GREEN: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.StagingAndReceiptTests.test_f5_fixture_status_printed_and_default_stage_warning -v`

```text
test_f5_fixture_status_printed_and_default_stage_warning (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f5_fixture_status_printed_and_default_stage_warning) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.142s

OK
```

### F7 explicit client elapsed zero

RED: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.HookTests.test_f7_client_elapsed_is_explicitly_zero -v`

```text
test_f7_client_elapsed_is_explicitly_zero (tests.unit.test_infected_competence.HookTests.test_f7_client_elapsed_is_explicitly_zero) ... FAIL

======================================================================
FAIL: test_f7_client_elapsed_is_explicitly_zero (tests.unit.test_infected_competence.HookTests.test_f7_client_elapsed_is_explicitly_zero)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 68, in test_f7_client_elapsed_is_explicitly_zero
    self.assertRegex(method, r'if \(m_Trial.support_state == "client_required"\)\s+m_Trial.elapsed_ms = 0;\s+else\s+m_Trial.elapsed_ms = GetGame\(\).GetTime\(\) - m_TrialBegin;')
AssertionError: Regex didn't match: 'if \\(m_Trial.support_state == "client_required"\\)\\s+m_Trial.elapsed_ms = 0;\\s+else\\s+m_Trial.elapsed_ms = GetGame\\(\\).GetTime\\(\\) - m_TrialBegin;' not found in '\n    {\n        HCICCleanup();\n        m_Trial.elapsed_ms = GetGame().GetTime() - m_TrialBegin;\n        m_Index = m_Index + 1;\n        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCICStep, 100, false);\n    }\n\n'

----------------------------------------------------------------------
Ran 1 test in 0.002s

FAILED (failures=1)
```

GREEN: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.HookTests.test_f7_client_elapsed_is_explicitly_zero -v`

```text
test_f7_client_elapsed_is_explicitly_zero (tests.unit.test_infected_competence.HookTests.test_f7_client_elapsed_is_explicitly_zero) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.002s

OK
```

### F8 exact receipt field sets

RED: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.StagingAndReceiptTests.test_f8_exact_nested_and_document_fields -v`

```text
test_f8_exact_nested_and_document_fields (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f8_exact_nested_and_document_fields) ... 
  test_f8_exact_nested_and_document_fields (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f8_exact_nested_and_document_fields) (location='document', remove=False) ... FAIL
  test_f8_exact_nested_and_document_fields (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f8_exact_nested_and_document_fields) (location='document', remove=True) ... FAIL
  test_f8_exact_nested_and_document_fields (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f8_exact_nested_and_document_fields) (location='sample', remove=False) ... FAIL
  test_f8_exact_nested_and_document_fields (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f8_exact_nested_and_document_fields) (location='sample', remove=True) ... FAIL
  test_f8_exact_nested_and_document_fields (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f8_exact_nested_and_document_fields) (location='door', remove=False) ... FAIL

======================================================================
FAIL: test_f8_exact_nested_and_document_fields (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f8_exact_nested_and_document_fields) (location='document', remove=False)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 323, in test_f8_exact_nested_and_document_fields
    with self.subTest(location=location, remove=remove), self.assertRaisesRegex(ValueError, message):
AssertionError: ValueError not raised

======================================================================
FAIL: test_f8_exact_nested_and_document_fields (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f8_exact_nested_and_document_fields) (location='document', remove=True)
----------------------------------------------------------------------
ValueError: total deleted must be an integer 0..100

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 323, in test_f8_exact_nested_and_document_fields
    with self.subTest(location=location, remove=remove), self.assertRaisesRegex(ValueError, message):
AssertionError: "document fields" does not match "total deleted must be an integer 0..100"

======================================================================
FAIL: test_f8_exact_nested_and_document_fields (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f8_exact_nested_and_document_fields) (location='sample', remove=False)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 323, in test_f8_exact_nested_and_document_fields
    with self.subTest(location=location, remove=remove), self.assertRaisesRegex(ValueError, message):
AssertionError: ValueError not raised

======================================================================
FAIL: test_f8_exact_nested_and_document_fields (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f8_exact_nested_and_document_fields) (location='sample', remove=True)
----------------------------------------------------------------------
ValueError: numeric sample required

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 323, in test_f8_exact_nested_and_document_fields
    with self.subTest(location=location, remove=remove), self.assertRaisesRegex(ValueError, message):
AssertionError: "sample fields" does not match "numeric sample required"

======================================================================
FAIL: test_f8_exact_nested_and_document_fields (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f8_exact_nested_and_document_fields) (location='door', remove=False)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 323, in test_f8_exact_nested_and_document_fields
    with self.subTest(location=location, remove=remove), self.assertRaisesRegex(ValueError, message):
AssertionError: ValueError not raised

----------------------------------------------------------------------
Ran 1 test in 0.135s

FAILED (failures=5)
```

GREEN: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.StagingAndReceiptTests.test_f8_exact_nested_and_document_fields -v`

```text
test_f8_exact_nested_and_document_fields (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f8_exact_nested_and_document_fields) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.125s

OK
```

### Survey candidates and refusals

RED: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_read_only_even_placements_yaw_provenance_and_stage tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output -v`

```text
test_survey_read_only_even_placements_yaw_provenance_and_stage (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_read_only_even_placements_yaw_provenance_and_stage) ... usage: python3 -m unittest [-h] {stage,validate,report} ...
python3 -m unittest: error: argument command: invalid choice: 'survey' (choose from 'stage', 'validate', 'report')
ERROR
test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) ... 
  test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) (message='DOCTYPE') ... ERROR
  test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) (message='no selected placements') ... ERROR
  test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) (message='finite rpy') ... ERROR
  test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) (message='rpy') ... ERROR
  test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) (message='missing selected classes') ... ERROR
  test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) (message='per class') ... ERROR
  test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) (message='spawn offset') ... ERROR
  test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) (message='1..100') ... ERROR

======================================================================
ERROR: test_survey_read_only_even_placements_yaw_provenance_and_stage (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_read_only_even_placements_yaw_provenance_and_stage)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/usr/lib/python3.12/argparse.py", line 1941, in parse_known_args
    namespace, args = self._parse_known_args(args, namespace)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2144, in _parse_known_args
    positionals_end_index = consume_positionals(start_index)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2121, in consume_positionals
    take_action(action, args)
  File "/usr/lib/python3.12/argparse.py", line 2001, in take_action
    argument_values = self._get_values(action, argument_strings)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2554, in _get_values
    self._check_value(action, value[0])
  File "/usr/lib/python3.12/argparse.py", line 2600, in _check_value
    raise ArgumentError(action, msg % args)
argparse.ArgumentError: argument command: invalid choice: 'survey' (choose from 'stage', 'validate', 'report')

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 150, in test_survey_read_only_even_placements_yaw_provenance_and_stage
    self.assertEqual(probe.main(['survey', '--mapgrouppos', str(stock), '--output', str(output_path),
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/code/hc-worktrees/wp3-integ/tools/setup/infected_competence_probe.py", line 876, in main
    args = parser.parse_args(argv)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1908, in parse_args
    args, argv = self.parse_known_args(args, namespace)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1943, in parse_known_args
    self.error(str(err))
  File "/usr/lib/python3.12/argparse.py", line 2677, in error
    self.exit(2, _('%(prog)s: error: %(message)s\n') % args)
  File "/usr/lib/python3.12/argparse.py", line 2664, in exit
    _sys.exit(status)
SystemExit: 2

======================================================================
ERROR: test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) (message='DOCTYPE')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/usr/lib/python3.12/argparse.py", line 1941, in parse_known_args
    namespace, args = self._parse_known_args(args, namespace)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2144, in _parse_known_args
    positionals_end_index = consume_positionals(start_index)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2121, in consume_positionals
    take_action(action, args)
  File "/usr/lib/python3.12/argparse.py", line 2001, in take_action
    argument_values = self._get_values(action, argument_strings)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2554, in _get_values
    self._check_value(action, value[0])
  File "/usr/lib/python3.12/argparse.py", line 2600, in _check_value
    raise ArgumentError(action, msg % args)
argparse.ArgumentError: argument command: invalid choice: 'survey' (choose from 'stage', 'validate', 'report')

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 197, in test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output
    self.assertEqual(probe.main(['survey', '--mapgrouppos', str(stock), '--output', str(output_path)] + arguments), 1)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/code/hc-worktrees/wp3-integ/tools/setup/infected_competence_probe.py", line 876, in main
    args = parser.parse_args(argv)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1908, in parse_args
    args, argv = self.parse_known_args(args, namespace)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1943, in parse_known_args
    self.error(str(err))
  File "/usr/lib/python3.12/argparse.py", line 2677, in error
    self.exit(2, _('%(prog)s: error: %(message)s\n') % args)
  File "/usr/lib/python3.12/argparse.py", line 2664, in exit
    _sys.exit(status)
SystemExit: 2

======================================================================
ERROR: test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) (message='no selected placements')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/usr/lib/python3.12/argparse.py", line 1941, in parse_known_args
    namespace, args = self._parse_known_args(args, namespace)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2144, in _parse_known_args
    positionals_end_index = consume_positionals(start_index)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2121, in consume_positionals
    take_action(action, args)
  File "/usr/lib/python3.12/argparse.py", line 2001, in take_action
    argument_values = self._get_values(action, argument_strings)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2554, in _get_values
    self._check_value(action, value[0])
  File "/usr/lib/python3.12/argparse.py", line 2600, in _check_value
    raise ArgumentError(action, msg % args)
argparse.ArgumentError: argument command: invalid choice: 'survey' (choose from 'stage', 'validate', 'report')

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 197, in test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output
    self.assertEqual(probe.main(['survey', '--mapgrouppos', str(stock), '--output', str(output_path)] + arguments), 1)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/code/hc-worktrees/wp3-integ/tools/setup/infected_competence_probe.py", line 876, in main
    args = parser.parse_args(argv)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1908, in parse_args
    args, argv = self.parse_known_args(args, namespace)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1943, in parse_known_args
    self.error(str(err))
  File "/usr/lib/python3.12/argparse.py", line 2677, in error
    self.exit(2, _('%(prog)s: error: %(message)s\n') % args)
  File "/usr/lib/python3.12/argparse.py", line 2664, in exit
    _sys.exit(status)
SystemExit: 2

======================================================================
ERROR: test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) (message='finite rpy')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/usr/lib/python3.12/argparse.py", line 1941, in parse_known_args
    namespace, args = self._parse_known_args(args, namespace)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2144, in _parse_known_args
    positionals_end_index = consume_positionals(start_index)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2121, in consume_positionals
    take_action(action, args)
  File "/usr/lib/python3.12/argparse.py", line 2001, in take_action
    argument_values = self._get_values(action, argument_strings)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2554, in _get_values
    self._check_value(action, value[0])
  File "/usr/lib/python3.12/argparse.py", line 2600, in _check_value
    raise ArgumentError(action, msg % args)
argparse.ArgumentError: argument command: invalid choice: 'survey' (choose from 'stage', 'validate', 'report')

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 197, in test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output
    self.assertEqual(probe.main(['survey', '--mapgrouppos', str(stock), '--output', str(output_path)] + arguments), 1)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/code/hc-worktrees/wp3-integ/tools/setup/infected_competence_probe.py", line 876, in main
    args = parser.parse_args(argv)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1908, in parse_args
    args, argv = self.parse_known_args(args, namespace)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1943, in parse_known_args
    self.error(str(err))
  File "/usr/lib/python3.12/argparse.py", line 2677, in error
    self.exit(2, _('%(prog)s: error: %(message)s\n') % args)
  File "/usr/lib/python3.12/argparse.py", line 2664, in exit
    _sys.exit(status)
SystemExit: 2

======================================================================
ERROR: test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) (message='rpy')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/usr/lib/python3.12/argparse.py", line 1941, in parse_known_args
    namespace, args = self._parse_known_args(args, namespace)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2144, in _parse_known_args
    positionals_end_index = consume_positionals(start_index)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2121, in consume_positionals
    take_action(action, args)
  File "/usr/lib/python3.12/argparse.py", line 2001, in take_action
    argument_values = self._get_values(action, argument_strings)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2554, in _get_values
    self._check_value(action, value[0])
  File "/usr/lib/python3.12/argparse.py", line 2600, in _check_value
    raise ArgumentError(action, msg % args)
argparse.ArgumentError: argument command: invalid choice: 'survey' (choose from 'stage', 'validate', 'report')

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 197, in test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output
    self.assertEqual(probe.main(['survey', '--mapgrouppos', str(stock), '--output', str(output_path)] + arguments), 1)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/code/hc-worktrees/wp3-integ/tools/setup/infected_competence_probe.py", line 876, in main
    args = parser.parse_args(argv)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1908, in parse_args
    args, argv = self.parse_known_args(args, namespace)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1943, in parse_known_args
    self.error(str(err))
  File "/usr/lib/python3.12/argparse.py", line 2677, in error
    self.exit(2, _('%(prog)s: error: %(message)s\n') % args)
  File "/usr/lib/python3.12/argparse.py", line 2664, in exit
    _sys.exit(status)
SystemExit: 2

======================================================================
ERROR: test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) (message='missing selected classes')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/usr/lib/python3.12/argparse.py", line 1941, in parse_known_args
    namespace, args = self._parse_known_args(args, namespace)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2144, in _parse_known_args
    positionals_end_index = consume_positionals(start_index)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2121, in consume_positionals
    take_action(action, args)
  File "/usr/lib/python3.12/argparse.py", line 2001, in take_action
    argument_values = self._get_values(action, argument_strings)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2554, in _get_values
    self._check_value(action, value[0])
  File "/usr/lib/python3.12/argparse.py", line 2600, in _check_value
    raise ArgumentError(action, msg % args)
argparse.ArgumentError: argument command: invalid choice: 'survey' (choose from 'stage', 'validate', 'report')

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 197, in test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output
    self.assertEqual(probe.main(['survey', '--mapgrouppos', str(stock), '--output', str(output_path)] + arguments), 1)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/code/hc-worktrees/wp3-integ/tools/setup/infected_competence_probe.py", line 876, in main
    args = parser.parse_args(argv)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1908, in parse_args
    args, argv = self.parse_known_args(args, namespace)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1943, in parse_known_args
    self.error(str(err))
  File "/usr/lib/python3.12/argparse.py", line 2677, in error
    self.exit(2, _('%(prog)s: error: %(message)s\n') % args)
  File "/usr/lib/python3.12/argparse.py", line 2664, in exit
    _sys.exit(status)
SystemExit: 2

======================================================================
ERROR: test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) (message='per class')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/usr/lib/python3.12/argparse.py", line 1941, in parse_known_args
    namespace, args = self._parse_known_args(args, namespace)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2144, in _parse_known_args
    positionals_end_index = consume_positionals(start_index)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2121, in consume_positionals
    take_action(action, args)
  File "/usr/lib/python3.12/argparse.py", line 2001, in take_action
    argument_values = self._get_values(action, argument_strings)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2554, in _get_values
    self._check_value(action, value[0])
  File "/usr/lib/python3.12/argparse.py", line 2600, in _check_value
    raise ArgumentError(action, msg % args)
argparse.ArgumentError: argument command: invalid choice: 'survey' (choose from 'stage', 'validate', 'report')

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 197, in test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output
    self.assertEqual(probe.main(['survey', '--mapgrouppos', str(stock), '--output', str(output_path)] + arguments), 1)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/code/hc-worktrees/wp3-integ/tools/setup/infected_competence_probe.py", line 876, in main
    args = parser.parse_args(argv)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1908, in parse_args
    args, argv = self.parse_known_args(args, namespace)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1943, in parse_known_args
    self.error(str(err))
  File "/usr/lib/python3.12/argparse.py", line 2677, in error
    self.exit(2, _('%(prog)s: error: %(message)s\n') % args)
  File "/usr/lib/python3.12/argparse.py", line 2664, in exit
    _sys.exit(status)
SystemExit: 2

======================================================================
ERROR: test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) (message='spawn offset')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/usr/lib/python3.12/argparse.py", line 1941, in parse_known_args
    namespace, args = self._parse_known_args(args, namespace)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2144, in _parse_known_args
    positionals_end_index = consume_positionals(start_index)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2121, in consume_positionals
    take_action(action, args)
  File "/usr/lib/python3.12/argparse.py", line 2001, in take_action
    argument_values = self._get_values(action, argument_strings)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2554, in _get_values
    self._check_value(action, value[0])
  File "/usr/lib/python3.12/argparse.py", line 2600, in _check_value
    raise ArgumentError(action, msg % args)
argparse.ArgumentError: argument command: invalid choice: 'survey' (choose from 'stage', 'validate', 'report')

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 197, in test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output
    self.assertEqual(probe.main(['survey', '--mapgrouppos', str(stock), '--output', str(output_path)] + arguments), 1)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/code/hc-worktrees/wp3-integ/tools/setup/infected_competence_probe.py", line 876, in main
    args = parser.parse_args(argv)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1908, in parse_args
    args, argv = self.parse_known_args(args, namespace)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1943, in parse_known_args
    self.error(str(err))
  File "/usr/lib/python3.12/argparse.py", line 2677, in error
    self.exit(2, _('%(prog)s: error: %(message)s\n') % args)
  File "/usr/lib/python3.12/argparse.py", line 2664, in exit
    _sys.exit(status)
SystemExit: 2

======================================================================
ERROR: test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) (message='1..100')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/usr/lib/python3.12/argparse.py", line 1941, in parse_known_args
    namespace, args = self._parse_known_args(args, namespace)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2144, in _parse_known_args
    positionals_end_index = consume_positionals(start_index)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2121, in consume_positionals
    take_action(action, args)
  File "/usr/lib/python3.12/argparse.py", line 2001, in take_action
    argument_values = self._get_values(action, argument_strings)
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 2554, in _get_values
    self._check_value(action, value[0])
  File "/usr/lib/python3.12/argparse.py", line 2600, in _check_value
    raise ArgumentError(action, msg % args)
argparse.ArgumentError: argument command: invalid choice: 'survey' (choose from 'stage', 'validate', 'report')

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 197, in test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output
    self.assertEqual(probe.main(['survey', '--mapgrouppos', str(stock), '--output', str(output_path)] + arguments), 1)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/code/hc-worktrees/wp3-integ/tools/setup/infected_competence_probe.py", line 876, in main
    args = parser.parse_args(argv)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1908, in parse_args
    args, argv = self.parse_known_args(args, namespace)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/argparse.py", line 1943, in parse_known_args
    self.error(str(err))
  File "/usr/lib/python3.12/argparse.py", line 2677, in error
    self.exit(2, _('%(prog)s: error: %(message)s\n') % args)
  File "/usr/lib/python3.12/argparse.py", line 2664, in exit
    _sys.exit(status)
SystemExit: 2

----------------------------------------------------------------------
Ran 2 tests in 0.011s

FAILED (errors=9)
```

GREEN: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_read_only_even_placements_yaw_provenance_and_stage tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output -v`

```text
test_survey_read_only_even_placements_yaw_provenance_and_stage (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_read_only_even_placements_yaw_provenance_and_stage) ... ok
test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.147s

OK
```

### F6 mutation RED / restoration GREEN

Command setup and actual unittest command are recorded in each output. Both
commands execute in a disposable `/tmp` copy of authored tools/tests.

`See command in captured output` — [F6-RED.txt](F6-RED.txt)

```text
Isolated reviewer H5 mutation: remove HCICCleanup from HCICNext
$ /usr/bin/python3 -m unittest tests.unit.test_infected_competence.HookTests.test_hook_cleanup_ownership_guards_and_bounds_structure -v
test_hook_cleanup_ownership_guards_and_bounds_structure (tests.unit.test_infected_competence.HookTests.test_hook_cleanup_ownership_guards_and_bounds_structure) ... FAIL

======================================================================
FAIL: test_hook_cleanup_ownership_guards_and_bounds_structure (tests.unit.test_infected_competence.HookTests.test_hook_cleanup_ownership_guards_and_bounds_structure)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/tmp/wp3-r2-f6-red-3e51txrm/tests/unit/test_infected_competence.py", line 156, in test_hook_cleanup_ownership_guards_and_bounds_structure
    self.assertIn('HCICCleanup();', body(name), name)
AssertionError: 'HCICCleanup();' not found in '\n        if (m_Trial.support_state == "client_required")\n            m_Trial.elapsed_ms = 0;\n        else\n            m_Trial.elapsed_ms = GetGame().GetTime() - m_TrialBegin;\n        m_Index = m_Index + 1;\n        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCICStep, 100, false);\n    ' : HCICNext

----------------------------------------------------------------------
Ran 1 test in 0.003s

FAILED (failures=1)
```

`See command in captured output` — [F6-restored-GREEN.txt](F6-restored-GREEN.txt)

```text
Restore original cleanup call in isolated copy
$ /usr/bin/python3 -m unittest tests.unit.test_infected_competence.HookTests.test_hook_cleanup_ownership_guards_and_bounds_structure -v
test_hook_cleanup_ownership_guards_and_bounds_structure (tests.unit.test_infected_competence.HookTests.test_hook_cleanup_ownership_guards_and_bounds_structure) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.008s

OK
```

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence -v` — [F6-GREEN.txt](F6-GREEN.txt)

```text
test_bounds_and_injection_rejected (tests.unit.test_infected_competence.HookTests.test_bounds_and_injection_rejected) ... ok
test_check_trials_each_guard_and_plus_budget (tests.unit.test_infected_competence.HookTests.test_check_trials_each_guard_and_plus_budget) ... ok
test_compile_shape_against_real_cache (tests.unit.test_infected_competence.HookTests.test_compile_shape_against_real_cache) ... ok
test_f1_surface_height_precedes_queries_and_spawn_and_is_recorded (tests.unit.test_infected_competence.HookTests.test_f1_surface_height_precedes_queries_and_spawn_and_is_recorded) ... ok
test_f7_client_elapsed_is_explicitly_zero (tests.unit.test_infected_competence.HookTests.test_f7_client_elapsed_is_explicitly_zero) ... ok
test_hook_cleanup_ownership_guards_and_bounds_structure (tests.unit.test_infected_competence.HookTests.test_hook_cleanup_ownership_guards_and_bounds_structure) ... ok
test_server_trials_and_explicit_client_exclusions (tests.unit.test_infected_competence.HookTests.test_server_trials_and_explicit_client_exclusions) ... ok
test_client_required_each_field_refused_independently (tests.unit.test_infected_competence.StagingAndReceiptTests.test_client_required_each_field_refused_independently) ... ok
test_completed_records_require_kind_specific_evidence_and_pinned_build (tests.unit.test_infected_competence.StagingAndReceiptTests.test_completed_records_require_kind_specific_evidence_and_pinned_build) ... ok
test_f2_inconclusive_elapsed_uses_plan_cap_completed_keeps_tight_bound (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f2_inconclusive_elapsed_uses_plan_cap_completed_keeps_tight_bound) ... ok
test_f3_health_only_labels_drop_and_shared_coverage (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f3_health_only_labels_drop_and_shared_coverage) ... ok
test_f5_fixture_status_printed_and_default_stage_warning (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f5_fixture_status_printed_and_default_stage_warning) ... ok
test_f8_exact_nested_and_document_fields (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f8_exact_nested_and_document_fields) ... ok
test_missing_real_registration_fails_loudly_before_staging (tests.unit.test_infected_competence.StagingAndReceiptTests.test_missing_real_registration_fails_loudly_before_staging) ... ok
test_native_cache_required_and_config_duplicates_refused_before_writes (tests.unit.test_infected_competence.StagingAndReceiptTests.test_native_cache_required_and_config_duplicates_refused_before_writes) ... ok
test_output_budget_and_duplicate_keys_refused (tests.unit.test_infected_competence.StagingAndReceiptTests.test_output_budget_and_duplicate_keys_refused) ... ok
test_plan_and_staged_hook_tamper_refused (tests.unit.test_infected_competence.StagingAndReceiptTests.test_plan_and_staged_hook_tamper_refused) ... ok
test_receipt_denominator_and_inconclusive_are_honest (tests.unit.test_infected_competence.StagingAndReceiptTests.test_receipt_denominator_and_inconclusive_are_honest) ... ok
test_refuse_hash_unknown_kind_client_observations_and_cleanup_lies (tests.unit.test_infected_competence.StagingAndReceiptTests.test_refuse_hash_unknown_kind_client_observations_and_cleanup_lies) ... ok
test_refuse_incomplete_and_bad_sentinel (tests.unit.test_infected_competence.StagingAndReceiptTests.test_refuse_incomplete_and_bad_sentinel) ... ok
test_sidecar_and_hook_bytes_tamper_refused (tests.unit.test_infected_competence.StagingAndReceiptTests.test_sidecar_and_hook_bytes_tamper_refused) ... ok
test_stage_entity_and_wait_bounds_follow_explicit_trials (tests.unit.test_infected_competence.StagingAndReceiptTests.test_stage_entity_and_wait_bounds_follow_explicit_trials) ... ok
test_stage_is_fresh_pinned_no_clients_and_never_launches (tests.unit.test_infected_competence.StagingAndReceiptTests.test_stage_is_fresh_pinned_no_clients_and_never_launches) ... ok
test_stage_refuses_native_drift_and_lint_before_destination (tests.unit.test_infected_competence.StagingAndReceiptTests.test_stage_refuses_native_drift_and_lint_before_destination) ... ok
test_staged_config_and_each_init_binding_guard (tests.unit.test_infected_competence.StagingAndReceiptTests.test_staged_config_and_each_init_binding_guard) ... ok
test_survey_read_only_even_placements_yaw_provenance_and_stage (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_read_only_even_placements_yaw_provenance_and_stage) ... ok
test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) ... ok

----------------------------------------------------------------------
Ran 27 tests in 4.462s

OK
```

During test strengthening, the first full local test run exposed two incorrect
new test expectations: the default wait computes 6 minutes, and a reused
destination reports "destination must be fresh". Corrected those expectations;
no production change was needed for either. The complete initial output is in
[F6-baseline.txt](F6-baseline.txt), from
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence -v`.

## Final verification

The final source was verified with the following required commands. Runtime
acceptance remains pending regardless of these offline results.

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence tests.unit.test_probe_runtime -v`

```text
test_bounds_and_injection_rejected (tests.unit.test_infected_competence.HookTests.test_bounds_and_injection_rejected) ... ok
test_check_trials_each_guard_and_plus_budget (tests.unit.test_infected_competence.HookTests.test_check_trials_each_guard_and_plus_budget) ... ok
test_compile_shape_against_real_cache (tests.unit.test_infected_competence.HookTests.test_compile_shape_against_real_cache) ... ok
test_f1_surface_height_precedes_queries_and_spawn_and_is_recorded (tests.unit.test_infected_competence.HookTests.test_f1_surface_height_precedes_queries_and_spawn_and_is_recorded) ... ok
test_f7_client_elapsed_is_explicitly_zero (tests.unit.test_infected_competence.HookTests.test_f7_client_elapsed_is_explicitly_zero) ... ok
test_hook_cleanup_ownership_guards_and_bounds_structure (tests.unit.test_infected_competence.HookTests.test_hook_cleanup_ownership_guards_and_bounds_structure) ... ok
test_server_trials_and_explicit_client_exclusions (tests.unit.test_infected_competence.HookTests.test_server_trials_and_explicit_client_exclusions) ... ok
test_client_required_each_field_refused_independently (tests.unit.test_infected_competence.StagingAndReceiptTests.test_client_required_each_field_refused_independently) ... ok
test_completed_records_require_kind_specific_evidence_and_pinned_build (tests.unit.test_infected_competence.StagingAndReceiptTests.test_completed_records_require_kind_specific_evidence_and_pinned_build) ... ok
test_f1_authored_height_roundtrip_and_invalid_height_receipts (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f1_authored_height_roundtrip_and_invalid_height_receipts) ... ok
test_f2_inconclusive_elapsed_uses_plan_cap_completed_keeps_tight_bound (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f2_inconclusive_elapsed_uses_plan_cap_completed_keeps_tight_bound) ... ok
test_f3_health_only_labels_drop_and_shared_coverage (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f3_health_only_labels_drop_and_shared_coverage) ... ok
test_f5_fixture_status_printed_and_default_stage_warning (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f5_fixture_status_printed_and_default_stage_warning) ... ok
test_f8_exact_nested_and_document_fields (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f8_exact_nested_and_document_fields) ... ok
test_missing_real_registration_fails_loudly_before_staging (tests.unit.test_infected_competence.StagingAndReceiptTests.test_missing_real_registration_fails_loudly_before_staging) ... ok
test_native_cache_required_and_config_duplicates_refused_before_writes (tests.unit.test_infected_competence.StagingAndReceiptTests.test_native_cache_required_and_config_duplicates_refused_before_writes) ... ok
test_output_budget_and_duplicate_keys_refused (tests.unit.test_infected_competence.StagingAndReceiptTests.test_output_budget_and_duplicate_keys_refused) ... ok
test_plan_and_staged_hook_tamper_refused (tests.unit.test_infected_competence.StagingAndReceiptTests.test_plan_and_staged_hook_tamper_refused) ... ok
test_receipt_denominator_and_inconclusive_are_honest (tests.unit.test_infected_competence.StagingAndReceiptTests.test_receipt_denominator_and_inconclusive_are_honest) ... ok
test_refuse_hash_unknown_kind_client_observations_and_cleanup_lies (tests.unit.test_infected_competence.StagingAndReceiptTests.test_refuse_hash_unknown_kind_client_observations_and_cleanup_lies) ... ok
test_refuse_incomplete_and_bad_sentinel (tests.unit.test_infected_competence.StagingAndReceiptTests.test_refuse_incomplete_and_bad_sentinel) ... ok
test_sidecar_and_hook_bytes_tamper_refused (tests.unit.test_infected_competence.StagingAndReceiptTests.test_sidecar_and_hook_bytes_tamper_refused) ... ok
test_stage_entity_and_wait_bounds_follow_explicit_trials (tests.unit.test_infected_competence.StagingAndReceiptTests.test_stage_entity_and_wait_bounds_follow_explicit_trials) ... ok
test_stage_is_fresh_pinned_no_clients_and_never_launches (tests.unit.test_infected_competence.StagingAndReceiptTests.test_stage_is_fresh_pinned_no_clients_and_never_launches) ... ok
test_stage_refuses_native_drift_and_lint_before_destination (tests.unit.test_infected_competence.StagingAndReceiptTests.test_stage_refuses_native_drift_and_lint_before_destination) ... ok
test_staged_config_and_each_init_binding_guard (tests.unit.test_infected_competence.StagingAndReceiptTests.test_staged_config_and_each_init_binding_guard) ... ok
test_survey_read_only_even_placements_yaw_provenance_and_stage (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_read_only_even_placements_yaw_provenance_and_stage) ... ok
test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) ... ok
test_ce_probe_keeps_the_module_attributes_it_exported_before_the_shared_runtime (tests.unit.test_probe_runtime.CompatibilitySurfaceTests.test_ce_probe_keeps_the_module_attributes_it_exported_before_the_shared_runtime) ... ok
test_a_file_added_to_the_mission_after_verification_is_refused_and_never_copied (tests.unit.test_probe_runtime.CopyIntegrityTests.test_a_file_added_to_the_mission_after_verification_is_refused_and_never_copied) ... ok
test_a_mission_file_changed_after_verification_is_refused (tests.unit.test_probe_runtime.CopyIntegrityTests.test_a_mission_file_changed_after_verification_is_refused) ... ok
test_an_unexpected_staged_file_is_refused (tests.unit.test_probe_runtime.CopyIntegrityTests.test_an_unexpected_staged_file_is_refused) ... ok
test_clean_staging_still_succeeds_for_both_stagers (tests.unit.test_probe_runtime.CopyIntegrityTests.test_clean_staging_still_succeeds_for_both_stagers) ... ok
test_config_or_battleye_changed_after_verification_is_refused (tests.unit.test_probe_runtime.CopyIntegrityTests.test_config_or_battleye_changed_after_verification_is_refused) ... ok
test_mission_copy_rereads_the_destination_and_refuses_a_mismatch (tests.unit.test_probe_runtime.CopyIntegrityTests.test_mission_copy_rereads_the_destination_and_refuses_a_mismatch) ... ok
test_sensitive_entries_are_refused_even_when_the_launch_plan_lists_them (tests.unit.test_probe_runtime.CopyIntegrityTests.test_sensitive_entries_are_refused_even_when_the_launch_plan_lists_them) ... ok
test_symlinked_inputs_are_refused_before_anything_is_created (tests.unit.test_probe_runtime.CopyIntegrityTests.test_symlinked_inputs_are_refused_before_anything_is_created) ... ok
test_written_bytes_are_verified_against_the_admitted_hash (tests.unit.test_probe_runtime.CopyIntegrityTests.test_written_bytes_are_verified_against_the_admitted_hash) ... ok
test_a_staged_symlink_is_refused_even_without_admission (tests.unit.test_probe_runtime.DiagnosticMissionAdmissionTests.test_a_staged_symlink_is_refused_even_without_admission) ... ok
test_a_staged_symlink_with_the_same_bytes_never_passes_admitted_preparation (tests.unit.test_probe_runtime.DiagnosticMissionAdmissionTests.test_a_staged_symlink_with_the_same_bytes_never_passes_admitted_preparation)
The re-read must not follow a link: a same-byte symlink at the staged name would pass a following read. ... ok
test_exact_admitted_inventory_copies (tests.unit.test_probe_runtime.DiagnosticMissionAdmissionTests.test_exact_admitted_inventory_copies) ... ok
test_existing_purposes_keep_working_without_admission (tests.unit.test_probe_runtime.DiagnosticMissionAdmissionTests.test_existing_purposes_keep_working_without_admission) ... ok
test_inventory_drift_hash_drift_and_rejected_entries_are_refused (tests.unit.test_probe_runtime.DiagnosticMissionAdmissionTests.test_inventory_drift_hash_drift_and_rejected_entries_are_refused) ... ok
test_both_stagers_run_the_expression_lint_before_writing (tests.unit.test_probe_runtime.GeneratedHookExpressionTests.test_both_stagers_run_the_expression_lint_before_writing) ... ok
test_the_ce_probe_hook_passes_the_expression_lint_unchanged (tests.unit.test_probe_runtime.GeneratedHookExpressionTests.test_the_ce_probe_hook_passes_the_expression_lint_unchanged) ... ok
test_the_taped_light_hook_passes_with_headroom_below_the_native_maximum (tests.unit.test_probe_runtime.GeneratedHookExpressionTests.test_the_taped_light_hook_passes_with_headroom_below_the_native_maximum) ... ok
test_a_bare_int_float_or_bool_local_in_a_string_concatenation_is_flagged (tests.unit.test_probe_runtime.HookExpressionLintTests.test_a_bare_int_float_or_bool_local_in_a_string_concatenation_is_flagged) ... ok
test_a_bare_numeric_literal_or_numeric_returning_call_in_a_concatenation_is_flagged (tests.unit.test_probe_runtime.HookExpressionLintTests.test_a_bare_numeric_literal_or_numeric_returning_call_in_a_concatenation_is_flagged) ... ok
test_a_ref_or_autoptr_returning_method_is_linted_like_any_other (tests.unit.test_probe_runtime.HookExpressionLintTests.test_a_ref_or_autoptr_returning_method_is_linted_like_any_other)
Review 006: ``ref array<string> HCReview()`` was not recognised as a method header, so duplicate locals, an ... ok
test_a_statement_at_the_bound_is_accepted_in_every_layout (tests.unit.test_probe_runtime.HookExpressionLintTests.test_a_statement_at_the_bound_is_accepted_in_every_layout) ... ok
test_a_statement_over_the_bound_is_flagged_and_one_at_the_bound_is_not (tests.unit.test_probe_runtime.HookExpressionLintTests.test_a_statement_over_the_bound_is_flagged_and_one_at_the_bound_is_not) ... ok
test_a_vector_component_in_a_string_concatenation_is_a_bare_float (tests.unit.test_probe_runtime.HookExpressionLintTests.test_a_vector_component_in_a_string_concatenation_is_a_bare_float) ... ok
test_compound_assignment_into_a_string_is_a_concatenation (tests.unit.test_probe_runtime.HookExpressionLintTests.test_compound_assignment_into_a_string_is_a_concatenation) ... ok
test_control_flow_headers_are_not_mistaken_for_methods (tests.unit.test_probe_runtime.HookExpressionLintTests.test_control_flow_headers_are_not_mistaken_for_methods) ... ok
test_explicit_strings_and_numeric_destinations_stay_accepted_with_compound_and_parentheses (tests.unit.test_probe_runtime.HookExpressionLintTests.test_explicit_strings_and_numeric_destinations_stay_accepted_with_compound_and_parentheses) ... ok
test_explicit_to_string_and_plain_arithmetic_are_accepted (tests.unit.test_probe_runtime.HookExpressionLintTests.test_explicit_to_string_and_plain_arithmetic_are_accepted) ... ok
test_nested_call_arguments_are_checked_too (tests.unit.test_probe_runtime.HookExpressionLintTests.test_nested_call_arguments_are_checked_too) ... ok
test_parenthesised_numeric_terms_are_normalised_before_the_check (tests.unit.test_probe_runtime.HookExpressionLintTests.test_parenthesised_numeric_terms_are_normalised_before_the_check) ... ok
test_statements_are_counted_separately (tests.unit.test_probe_runtime.HookExpressionLintTests.test_statements_are_counted_separately) ... ok
test_the_bound_is_the_observed_native_maximum_and_cites_its_evidence (tests.unit.test_probe_runtime.HookExpressionLintTests.test_the_bound_is_the_observed_native_maximum_and_cites_its_evidence) ... ok
test_the_complexity_bound_holds_for_every_method_layout_not_just_the_generated_one (tests.unit.test_probe_runtime.HookExpressionLintTests.test_the_complexity_bound_holds_for_every_method_layout_not_just_the_generated_one) ... ok
test_the_complexity_bound_reports_the_line_of_a_statement_outside_any_method (tests.unit.test_probe_runtime.HookExpressionLintTests.test_the_complexity_bound_reports_the_line_of_a_statement_outside_any_method) ... ok
test_the_count_is_per_statement_across_lines_and_ignores_strings_and_compound_operators (tests.unit.test_probe_runtime.HookExpressionLintTests.test_the_count_is_per_statement_across_lines_and_ignores_strings_and_compound_operators) ... ok
test_the_numeric_rule_follows_the_same_method_layouts (tests.unit.test_probe_runtime.HookExpressionLintTests.test_the_numeric_rule_follows_the_same_method_layouts) ... ok
test_the_numeric_rule_is_opt_in_because_the_ce_hook_compiled_natively_without_it (tests.unit.test_probe_runtime.HookExpressionLintTests.test_the_numeric_rule_is_opt_in_because_the_ce_hook_compiled_natively_without_it) ... ok
test_every_launcher_precondition_holds_for_the_staged_runtime (tests.unit.test_probe_runtime.LauncherCompatibilityTests.test_every_launcher_precondition_holds_for_the_staged_runtime) ... ok
test_launcher_fixed_table_matches_the_taped_light_plan_and_probe_paths (tests.unit.test_probe_runtime.LauncherCompatibilityTests.test_launcher_fixed_table_matches_the_taped_light_plan_and_probe_paths) ... ok
test_launcher_wait_bounds_are_enforced_by_the_stager (tests.unit.test_probe_runtime.LauncherCompatibilityTests.test_launcher_wait_bounds_are_enforced_by_the_stager) ... ok
test_plan_arguments_equal_the_launcher_list_parsed_from_the_script (tests.unit.test_probe_runtime.LauncherCompatibilityTests.test_plan_arguments_equal_the_launcher_list_parsed_from_the_script) ... ok
test_a_crash_log_alone_does_not_end_the_wait (tests.unit.test_probe_runtime.LauncherCompileFailureTests.test_a_crash_log_alone_does_not_end_the_wait)
Native evidence: completed run taped-light-probe-003 wrote crash_2026-11-17_04-53-03.log for ... ok
test_compile_failure_breaks_the_loop_and_still_stops_the_server (tests.unit.test_probe_runtime.LauncherCompileFailureTests.test_compile_failure_breaks_the_loop_and_still_stops_the_server) ... ok
test_report_records_crash_logs (tests.unit.test_probe_runtime.LauncherCompileFailureTests.test_report_records_crash_logs) ... ok
test_script_log_reader_shares_the_file_and_reads_a_bounded_tail (tests.unit.test_probe_runtime.LauncherCompileFailureTests.test_script_log_reader_shares_the_file_and_reads_a_bounded_tail) ... ok
test_sentinel_takes_precedence_over_a_later_crash_check (tests.unit.test_probe_runtime.LauncherCompileFailureTests.test_sentinel_takes_precedence_over_a_later_crash_check) ... ok
test_wait_loop_reads_the_script_log_for_the_native_compile_refusal (tests.unit.test_probe_runtime.LauncherCompileFailureTests.test_wait_loop_reads_the_script_log_for_the_native_compile_refusal) ... ok
test_every_kind_has_distinct_plan_and_profile_directory (tests.unit.test_probe_runtime.LauncherKindTableTests.test_every_kind_has_distinct_plan_and_profile_directory) ... ok
test_infected_competence_probe_is_registered_with_its_module_rows (tests.unit.test_probe_runtime.LauncherKindTableTests.test_infected_competence_probe_is_registered_with_its_module_rows)
WP3 (#18 #19): the staged competence probe needs real rows, not test patches. ... ok
test_launcher_table_equals_the_python_table (tests.unit.test_probe_runtime.LauncherKindTableTests.test_launcher_table_equals_the_python_table) ... ok
test_validate_set_admits_exactly_the_table_kinds (tests.unit.test_probe_runtime.LauncherKindTableTests.test_validate_set_admits_exactly_the_table_kinds) ... ok
test_weather_and_interior_kinds_have_fixed_paths (tests.unit.test_probe_runtime.LauncherKindTableTests.test_weather_and_interior_kinds_have_fixed_paths) ... ok
test_weather_probe_has_its_own_generated_hook_purpose (tests.unit.test_probe_runtime.LauncherKindTableTests.test_weather_probe_has_its_own_generated_hook_purpose) ... ok
test_a_destination_battleye_directory_swapped_before_the_dll_write_writes_nothing_outside (tests.unit.test_probe_runtime.LinkRaceTests.test_a_destination_battleye_directory_swapped_before_the_dll_write_writes_nothing_outside) ... ok
test_a_directory_displaced_after_the_final_scan_opened_it_never_yields_a_plan (tests.unit.test_probe_runtime.LinkRaceTests.test_a_directory_displaced_after_the_final_scan_opened_it_never_yields_a_plan)
Sol review 003 P2: the final scan certified a retained descriptor of a directory that no longer ... ok
test_a_directory_moved_after_it_was_opened_but_before_the_leaf_write_is_still_refused (tests.unit.test_probe_runtime.LinkRaceTests.test_a_directory_moved_after_it_was_opened_but_before_the_leaf_write_is_still_refused)
Narrowed contract (documented in diagnostic_mission.py): a descriptor-anchored write cannot stop the ... ok
test_a_moved_directory_replaced_by_a_writer_with_the_same_bytes_is_a_known_undetected_residual (tests.unit.test_probe_runtime.LinkRaceTests.test_a_moved_directory_replaced_by_a_writer_with_the_same_bytes_is_a_known_undetected_residual)
PINNED RESIDUAL (Sol review 004, synthetic): a concurrent writer moves the opened battleye directory away ... ok
test_a_source_battleye_directory_swapped_for_a_symlink_right_before_the_dll_read_is_refused (tests.unit.test_probe_runtime.LinkRaceTests.test_a_source_battleye_directory_swapped_for_a_symlink_right_before_the_dll_read_is_refused) ... ok
test_a_staged_mission_file_swapped_for_a_symlink_before_the_final_tree_check_is_refused (tests.unit.test_probe_runtime.LinkRaceTests.test_a_staged_mission_file_swapped_for_a_symlink_before_the_final_tree_check_is_refused) ... ok
test_staging_is_refused_where_directory_descriptor_operations_are_unavailable (tests.unit.test_probe_runtime.LinkRaceTests.test_staging_is_refused_where_directory_descriptor_operations_are_unavailable) ... ok
test_the_concurrency_contract_names_what_is_guaranteed_and_the_matching_replacement_residual (tests.unit.test_probe_runtime.LinkRaceTests.test_the_concurrency_contract_names_what_is_guaranteed_and_the_matching_replacement_residual)
Sol review 004: the comment must not say a displaced destination always ends refused. It states the ... ok
test_the_drvfs_junction_residual_is_documented_and_left_to_the_launcher_reverification (tests.unit.test_probe_runtime.LinkRaceTests.test_the_drvfs_junction_residual_is_documented_and_left_to_the_launcher_reverification)
PINNED RESIDUAL, not a behavior test: O_NOFOLLOW and *at() calls cannot see an NTFS junction or ... ok
test_the_staged_root_replaced_after_the_final_scan_opened_it_never_yields_a_plan (tests.unit.test_probe_runtime.LinkRaceTests.test_the_staged_root_replaced_after_the_final_scan_opened_it_never_yields_a_plan) ... ok
test_python_and_launcher_accept_exactly_the_same_names (tests.unit.test_probe_runtime.NameRuleAlignmentTests.test_python_and_launcher_accept_exactly_the_same_names) ... ok
test_the_launcher_mirror_extractor_reads_the_real_script (tests.unit.test_probe_runtime.NameRuleAlignmentTests.test_the_launcher_mirror_extractor_reads_the_real_script) ... ok
test_the_staged_plan_check_applies_the_same_rule (tests.unit.test_probe_runtime.NameRuleAlignmentTests.test_the_staged_plan_check_applies_the_same_rule) ... ok
test_both_stagers_use_the_one_shared_implementation (tests.unit.test_probe_runtime.SharedSurfaceTests.test_both_stagers_use_the_one_shared_implementation) ... ok
test_server_arguments_are_exactly_the_launcher_list (tests.unit.test_probe_runtime.SharedSurfaceTests.test_server_arguments_are_exactly_the_launcher_list) ... ok
test_shared_module_never_launches_or_networks (tests.unit.test_probe_runtime.SharedSurfaceTests.test_shared_module_never_launches_or_networks) ... ok
test_the_real_stager_refuses_an_over_bound_statement_in_any_method_layout (tests.unit.test_probe_runtime.StagedHookComplexityTests.test_the_real_stager_refuses_an_over_bound_statement_in_any_method_layout) ... ok
test_aliases_of_the_verified_runtime_and_reserved_devices_are_refused_by_every_entry_point (tests.unit.test_probe_runtime.WindowsAliasTests.test_aliases_of_the_verified_runtime_and_reserved_devices_are_refused_by_every_entry_point) ... ok
test_launcher_name_rule_mirrors_the_python_rule (tests.unit.test_probe_runtime.WindowsAliasTests.test_launcher_name_rule_mirrors_the_python_rule) ... ok
test_plain_names_still_map_to_one_windows_child (tests.unit.test_probe_runtime.WindowsAliasTests.test_plain_names_still_map_to_one_windows_child) ... ok
test_the_protected_name_is_compared_after_windows_normalization (tests.unit.test_probe_runtime.WindowsAliasTests.test_the_protected_name_is_compared_after_windows_normalization) ... ok

----------------------------------------------------------------------
Ran 102 tests in 10.182s

OK
```

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit`

```text
.......................................................................................................................................................................................ce_probe: destination must be fresh; no overwrite
.................................ce_probe_report: refusing to write into the repository metrics/ directory
.ce_probe_report: census is not valid JSON: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
.ce_probe_report: refusing to overwrite /tmp/tmp4903jlr1/report.json
............................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................flashlight_matrix: classification output must be outside the source checkout
.flashlight_matrix: [Errno 17] File exists: '/tmp/tmpsnxj7n7s/classification.json'
..usage: python3 -m unittest classify [-h] (--rows ROWS | --manifest MANIFEST)
                                    [--manifest-sha256 MANIFEST_SHA256] --out
                                    OUT
python3 -m unittest classify: error: one of the arguments --rows --manifest is required
usage: python3 -m unittest classify [-h] (--rows ROWS | --manifest MANIFEST)
                                    [--manifest-sha256 MANIFEST_SHA256] --out
                                    OUT
python3 -m unittest classify: error: argument --manifest: not allowed with argument --rows
..........................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................s....................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................taped_light_report: Expecting value: line 1 column 1 (char 0)
.taped_light_report: report output must be outside the source checkout
.taped_light_report: [Errno 17] File exists: '/tmp/tmpahbzf2up/report.json'
............................................................................................................................................................................................................................................................................................................................................................................................................................................................................
----------------------------------------------------------------------
Ran 2390 tests in 142.785s

OK (skipped=1)
wrote /tmp/tmp4903jlr1/report.json and /tmp/tmp4903jlr1/report.csv
classification: hosts=1 slot=0 no_slot=1 excluded=0 lights=1 -> /tmp/tmpsnxj7n7s/classification.json
classification: hosts=1 slot=0 no_slot=1 excluded=0 lights=1 -> /tmp/tmp1n7927md/from-manifest.json
report: qualified=1 geometry_missing=0 excluded=1 pending=0 hosts=2 -> /tmp/tmpahbzf2up/report.json
```

The discovery skip is the existing native Windows PowerShell helper test, guarded by `os.name == "nt"` in `tests/unit/test_package.py:311`. No PowerShell was run.

### Default hook identity and native lint

Command (standard-library Python, no engine launch):

```python
from tools.setup import infected_competence_probe as probe, probe_runtime as rt
hook = probe.render_hook()
print(rt.sha256(hook), len(hook))
print(rt.lint_hook(hook.decode('ascii'),
                   native_types=rt.native_type_names(probe.DEFAULT_NATIVE),
                   explicit_numbers=True))
print(len(probe.verify_native(probe.DEFAULT_NATIVE)))
print(rt.max_statement_plus(hook.decode('ascii')))
```

Actual saved results from [hook-evidence.json](hook-evidence.json):

```json
{
  "default_hook_sha256": "6d009bbfa2a9daaf90358923b1f354868d455f5435c3f9d8599d6da45792ff19",
  "default_hook_bytes": 16903,
  "lint": [],
  "explicit_numbers": true,
  "native_rows": 47,
  "max_statement_plus": 1
}
```

## Mutation reruns against the final source

Both original reviewer scripts ran unchanged on a disposable copy of final
`tools/` and `tests/` at the path they require. The copy matched the final source
and tests after restoration; hashes are in
[final-source-identities.json](final-source-identities.json). The generated copy
has now been removed. No production source or git state was mutated by a harness.

**Executable mutation survivors: none.** The original single-mutation harness
killed 71 applicable mutations. Four original patterns no longer apply; its
printed `survivors:` list includes those `PATTERN_COUNT` entries, not four
executed survivors. All five paired mutations were killed. The adapted runner
killed five replacements covering those four stale patterns, splitting H1's two
client branches. No unmatched pattern is presented as an original-harness kill.

| Original pattern | Why it no longer matches | Adapted result |
|---|---|---|
| C9 whole client branch | New terrain-field client guard precedes existing checks | Removing current branch: KILLED |
| E13 no-client config check | `maxPlayers=0` normalization was removed | Removing current config binding guard: KILLED |
| S14 config rewrite | Rewrite function and literal were removed | Reintroducing rewrite into staged bytes: KILLED |
| H1 client-required skip | Required elapsed-zero fix adds a second occurrence | Mutating Step skip and Next zero branch independently: both KILLED |

Commands and complete actual output:

`PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 python3 scratchpad-review/wp3-review/mutate.py`

```text
V1 cleanup row spawned!=deleted KILLED
V2 totals spawned/deleted match KILLED
V3 receipt hook sha KILLED
V4 unknown kind KILLED
V5 exact row field set KILLED
V6 row count denominator KILLED
V7 clients==0 KILLED
V8 status complete KILLED
V9 sentinel KILLED
V10 world KILLED
V11 build KILLED
V12 identity mismatch KILLED
C1 client: observed KILLED
C2 client: status KILLED
C3 client: spawned KILLED
C4 client: samples KILLED
C5 client: doors KILLED
C6 client: geometry KILLED
C7 client: elapsed KILLED
C8 client: reason KILLED
C9 client whole branch PATTERN_COUNT=0
D1 counts client_required KILLED
D2 counts attempted KILLED
D3 counts status KILLED
D4 observed iff completed KILLED
E1 completed spawned==1 KILLED
E2 completed 2 samples KILLED
E3 completed geometry clear KILLED
E4 completed elapsed>=per KILLED
E5 door state needed KILLED
E6 door outside door trial KILLED
E7 target/alive in completed KILLED
E8 elapsed upper bound KILLED
E9 array bounds KILLED
E10 reason bounded KILLED
E11 limb range KILLED
E12 door index order KILLED
E13 config no-client PATTERN_COUNT=0
E14 init hash KILLED
E15 init endswith hook KILLED
E16 sidecar KILLED
S1 stage: registration check KILLED
S2 stage: native verify KILLED
S3 stage: lint KILLED
S4 check_trials spawn<=20m KILLED
S5 check_trials fixture status KILLED
S6 check_trials support mismatch KILLED
S7 check_trials reason canonical KILLED
S8 dup trial id KILLED
S9 max plus KILLED
S10 trial count cap KILLED
S11 bounds position KILLED
S12 max_spawned_entities KILLED
S13 wait_minutes KILLED
S14 config maxPlayers 0 PATTERN_COUNT=0
H1 hook: client_required skip PATTERN_COUNT=2
H2 hook: delete count receipt KILLED
H3 hook: delete count trial KILLED
H4 hook: ObjectDelete call KILLED
H5 hook: cleanup in next KILLED
H6 hook: cleanup in finish KILLED
H7 hook: cleanup in mission finish KILLED
H8 hook: spawned count KILLED
H9 hook: no-client abort KILLED
H10 hook: cap check KILLED
H11 hook: output cap KILLED
H12 hook: sentinel written first KILLED
H13 hook: door loop bound KILLED
H14 hook: owned deleted even if cast fails (m_Owned kept) KILLED
H15 hook: leg health bound KILLED
H16 hook: ray count KILLED
H17 hook: ECE flags KILLED
H18 hook: watchdog KILLED
H19 hook: query bound KILLED
H20 hook: structure ambiguity KILLED
survivors: ['C9 client whole branch', 'E13 config no-client', 'S14 config maxPlayers 0', 'H1 hook: client_required skip']
```

`PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 python3 scratchpad-review/wp3-review/mutate2.py`

```text
V1+V2 cleanup lies (both removed) KILLED
V4+V12 unknown kind (both removed) KILLED
E14+E15 staged init (both removed) KILLED
C1+C2 client observed/status both removed KILLED
D4+C? observed flag mismatch (E: status completed but observed False) KILLED
```

`PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/wp3-r2/mutation_supplement.py`

```text
C9 current whole client branch KILLED
E13 unchanged-config binding guard KILLED
S14 reintroduce maxPlayers rewrite in staged bytes KILLED
H1 client-required execution skip (first occurrence only) KILLED
H1/F7 client-required zero elapsed branch KILLED
survivors: []
```

The supplemental runner is [mutation_supplement.py](mutation_supplement.py);
each replacement's full failing test output is in
[adapted-mutation-1.txt](adapted-mutation-1.txt),
[adapted-mutation-2.txt](adapted-mutation-2.txt),
[adapted-mutation-3.txt](adapted-mutation-3.txt),
[adapted-mutation-4.txt](adapted-mutation-4.txt),
[adapted-mutation-5.txt](adapted-mutation-5.txt).

## Remaining gaps — no runtime acceptance or production enablement

- Actual DayZDiag compilation/execution and normal PBO/server testing remain
  pending. Native API signatures and static lint are source evidence only.
- Default fixtures remain unqualified. Stock-derived positions/bearings are
  candidates, with no verified building, entrance, reachable spawn, floor,
  orientation-sign or building/angle/door-state denominator. The 5 m match radius
  is bounded and conservative, not an empirically qualified slope/floor policy.
- Health-only stimuli do not exercise the damage hit callback or prove native
  crawl transitions, injury mobility, animation or replication. A genuine
  hit-path/config-checked-ammo experiment remains pending for T018/T019.
- Door reads, four short view rays and two state samples do not prove passage,
  collision volumes, LOS acquisition, wall-attack fairness or whole trajectories.
- F9 remains: `deleted` counts ObjectDelete calls, not observed absence. Native
  residual census/cleanup verification is pending; no residual check was invented.
- Watchdog/cap callbacks cannot interrupt a hung synchronous native call. Outer
  timeout, entity cleanup and config semantics still need native verification.
- Client-required rows perform no observations. Two simultaneous clients are
  required for LOS/chase, attacks, network/visibility and audible-pursuit acceptance.
- Hashes bind staged bytes, not authenticated observations against a malicious
  operator. Measured benchmark budgets at the intended 3–6-player load and the
  friend's eventual hardware remain pending.
- F10's existing inventory convention is unchanged: the plan file is excluded
  from `staged_files`; direct `launcher_problems` callers must hold the plan aside,
  as with existing probes. Staging uses the shared `write_plan` checks.

The requested code/test changes are complete. The canonical native experiment
and gameplay acceptance gates remain open.

## Initial F6 test-expectation correction output

This was a test-development correction, not claimed as evidence of a production
bug. Command:
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence -v`

```text
test_bounds_and_injection_rejected (tests.unit.test_infected_competence.HookTests.test_bounds_and_injection_rejected) ... ok
test_check_trials_each_guard_and_plus_budget (tests.unit.test_infected_competence.HookTests.test_check_trials_each_guard_and_plus_budget) ... ok
test_compile_shape_against_real_cache (tests.unit.test_infected_competence.HookTests.test_compile_shape_against_real_cache) ... ok
test_f1_surface_height_precedes_queries_and_spawn_and_is_recorded (tests.unit.test_infected_competence.HookTests.test_f1_surface_height_precedes_queries_and_spawn_and_is_recorded) ... ok
test_f7_client_elapsed_is_explicitly_zero (tests.unit.test_infected_competence.HookTests.test_f7_client_elapsed_is_explicitly_zero) ... ok
test_hook_cleanup_ownership_guards_and_bounds_structure (tests.unit.test_infected_competence.HookTests.test_hook_cleanup_ownership_guards_and_bounds_structure) ... ok
test_server_trials_and_explicit_client_exclusions (tests.unit.test_infected_competence.HookTests.test_server_trials_and_explicit_client_exclusions) ... ok
test_client_required_each_field_refused_independently (tests.unit.test_infected_competence.StagingAndReceiptTests.test_client_required_each_field_refused_independently) ... ok
test_completed_records_require_kind_specific_evidence_and_pinned_build (tests.unit.test_infected_competence.StagingAndReceiptTests.test_completed_records_require_kind_specific_evidence_and_pinned_build) ... ok
test_f2_inconclusive_elapsed_uses_plan_cap_completed_keeps_tight_bound (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f2_inconclusive_elapsed_uses_plan_cap_completed_keeps_tight_bound) ... ok
test_f3_health_only_labels_drop_and_shared_coverage (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f3_health_only_labels_drop_and_shared_coverage) ... ok
test_f5_fixture_status_printed_and_default_stage_warning (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f5_fixture_status_printed_and_default_stage_warning) ... ok
test_f8_exact_nested_and_document_fields (tests.unit.test_infected_competence.StagingAndReceiptTests.test_f8_exact_nested_and_document_fields) ... ok
test_missing_real_registration_fails_loudly_before_staging (tests.unit.test_infected_competence.StagingAndReceiptTests.test_missing_real_registration_fails_loudly_before_staging) ... ok
test_native_cache_required_and_config_duplicates_refused_before_writes (tests.unit.test_infected_competence.StagingAndReceiptTests.test_native_cache_required_and_config_duplicates_refused_before_writes) ... ok
test_output_budget_and_duplicate_keys_refused (tests.unit.test_infected_competence.StagingAndReceiptTests.test_output_budget_and_duplicate_keys_refused) ... ok
test_plan_and_staged_hook_tamper_refused (tests.unit.test_infected_competence.StagingAndReceiptTests.test_plan_and_staged_hook_tamper_refused) ... ok
test_receipt_denominator_and_inconclusive_are_honest (tests.unit.test_infected_competence.StagingAndReceiptTests.test_receipt_denominator_and_inconclusive_are_honest) ... ok
test_refuse_hash_unknown_kind_client_observations_and_cleanup_lies (tests.unit.test_infected_competence.StagingAndReceiptTests.test_refuse_hash_unknown_kind_client_observations_and_cleanup_lies) ... ok
test_refuse_incomplete_and_bad_sentinel (tests.unit.test_infected_competence.StagingAndReceiptTests.test_refuse_incomplete_and_bad_sentinel) ... ok
test_sidecar_and_hook_bytes_tamper_refused (tests.unit.test_infected_competence.StagingAndReceiptTests.test_sidecar_and_hook_bytes_tamper_refused) ... ok
test_stage_entity_and_wait_bounds_follow_explicit_trials (tests.unit.test_infected_competence.StagingAndReceiptTests.test_stage_entity_and_wait_bounds_follow_explicit_trials) ... FAIL
test_stage_is_fresh_pinned_no_clients_and_never_launches (tests.unit.test_infected_competence.StagingAndReceiptTests.test_stage_is_fresh_pinned_no_clients_and_never_launches) ... FAIL
test_stage_refuses_native_drift_and_lint_before_destination (tests.unit.test_infected_competence.StagingAndReceiptTests.test_stage_refuses_native_drift_and_lint_before_destination) ... ok
test_staged_config_and_each_init_binding_guard (tests.unit.test_infected_competence.StagingAndReceiptTests.test_staged_config_and_each_init_binding_guard) ... ok
test_survey_read_only_even_placements_yaw_provenance_and_stage (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_read_only_even_placements_yaw_provenance_and_stage) ... ok
test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output (tests.unit.test_infected_competence.StagingAndReceiptTests.test_survey_refuses_unsafe_missing_or_over_budget_inputs_without_output) ... ok

======================================================================
FAIL: test_stage_entity_and_wait_bounds_follow_explicit_trials (tests.unit.test_infected_competence.StagingAndReceiptTests.test_stage_entity_and_wait_bounds_follow_explicit_trials)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 314, in test_stage_entity_and_wait_bounds_follow_explicit_trials
    self.assertEqual(plan['probe']['wait_minutes'], 5)
AssertionError: 6 != 5

======================================================================
FAIL: test_stage_is_fresh_pinned_no_clients_and_never_launches (tests.unit.test_infected_competence.StagingAndReceiptTests.test_stage_is_fresh_pinned_no_clients_and_never_launches)
----------------------------------------------------------------------
ValueError: destination must be fresh; no overwrite

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/code/hc-worktrees/wp3-integ/tests/unit/test_infected_competence.py", line 353, in test_stage_is_fresh_pinned_no_clients_and_never_launches
    with self.assertRaisesRegex(ValueError, 'destination.*exist'):
AssertionError: "destination.*exist" does not match "destination must be fresh; no overwrite"

----------------------------------------------------------------------
Ran 27 tests in 4.946s

FAILED (failures=2)
```
