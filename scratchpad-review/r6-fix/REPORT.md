# Interior sampler fix round 6 (#11) report

Files changed (uncommitted on top of 9cbef6f): tools/audit/interior_points.py, tools/setup/interior_sampler.py,
tests/unit/test_interior_points.py, tests/unit/test_interior_sampler.py. No git state changes.

## RED (actual logs in this directory)
- red-builder.log: `python3 -m unittest tests.unit.test_interior_points.Round6DoorRunEvidenceTests ...Round6CliTests ...Round6NumericOverflowTests`
  -> `Ran 16 tests`, `FAILED (failures=33, errors=27)` (OverflowError x16, SystemExit: 2 x10, "ValueError not raised" x17).
- red-hook.log: `python3 -m unittest tests.unit.test_interior_sampler.Round6DoorPhaseTests ...Round5DoorRunTests`
  -> `Ran 26 tests`, `FAILED (failures=8, errors=6)` (no IsDoorOpened/Closed in the hook, KeyError ajar_at_start / open_settle_ticks,
  no DOOR_SETTLE_TICKS, `'open-stalled' != 'done'`, `'not-restored' != 'done'`, "the open pass ran before the door actually opened").
- Note: the player-source door-evidence test was first written with a bad fixture (control-not-entered) and corrected after the builder change; its RED is not logged.

## GREEN
- red tests now pass; focused: `python3 -m unittest tests.unit.test_interior_sampler tests.unit.test_interior_points` -> `Ran 302 tests ... OK` (green-focused.log)
- full: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit` -> `Ran 2663 tests in 278.121s`, `OK (skipped=1)` (green-full.log)
- default hook `render_hook(sampler_targets())`: 75460 bytes, sha256 b539dae598a04e9046b360aeff5e8bb0630f0ba681d4a17b6a258317a2ceee14
  (r5: 72583 bytes 8fb3ab22...). Lint incl. native type names (7190 types) passes in the suite; max ' + ' per statement 8.

## Findings
1. P2 door_run evidence gates treatment: FIXED. `_door_run_problem` requires a dict with integer counts, state "done", opened>=1,
   opened<=count, opened+locked<=count, observed_open==opened, restored==opened, doors list of length count with 5-6 numeric fields.
   One invalid compared row makes door_semantics.observed false; report doors.invalid_rows and doors.problems (max 8); refusal
   kind door-semantics-unobserved (message names the first problem); CLI exit 2 with a report, no treatment. Negative builder and CLI
   tests: missing, not a record, no-change zeros, restored 0 / not-restored, open-stalled, observed 0, skipped, opened>count,
   count mismatch, negative, bool, string, state missing; player source too.
2. P2 actual door phase: FIXED offline. Hook uses IsDoorOpened/IsDoorOpenedAjar/IsDoorClosed through HCProbeDoorPhase (0 closed,
   1 open, 2 ajar, 3 other); IsDoorOpen is no longer called. Only unlocked, actually closed doors are opened; ajar/open/moving doors are
   untouched and counted (ajar_at_start, moving_at_start; per-door 6th field = phase code). Fixed delay (30) then a bounded settle
   (DOOR_SETTLE_TICKS 30) polling the actual phase after open and after close; open_settle_ticks/close_settle_ticks/settle_limit
   recorded. Open that stays unobserved -> state "open-stalled": open pass skipped, codes copied, open entered "untested", doors still
   closed. Close that stalls -> "not-restored" plus a Print warning. "done" only when all opened doors report closed. Mock
   SampBuilding now has requested state, actual phase, lag, stuck, tick (driven per hook step); DoorGatedNav follows the actual phase.
   A mutant that disables the settle poll is killed.
3. P2 CLI parse failures: FIXED. Parser errors raise a usage error; main writes a refusal report (kind invalid-input) when a safe
   --report is named (pre-scanned with the same abbreviation rules, outside the checkout, no '..', no overwrite) and returns 1;
   --help still exits 0. The Round3 test that expected SystemExit for --reach-source loose was updated accordingly.
4. P3 overflow: FIXED. `_number` catches OverflowError, so a 10**400 integer anywhere (frame, hits, box, door counts, grid) is
   census-invalid with a written report (CLI exit 1), not a traceback.

## Next native sampler run must show
- frame verdict rot90 for both calibration classes; door_run with opened>0, observed_open==opened, restored==opened, state "done"
  (now by actual phase); entered.open == "entered" with control tested; open_codes strictly above closed codes; lootFloor coverage >= 0.6.
- door_run.ajar_at_start / moving_at_start / open_settle_ticks / close_settle_ticks tell whether the 30-tick delay was enough.

## Remaining gaps
- Native frame and door behaviour (IsDoorOpened/Closed timing, navmesh reaction within the delay) unproven; the mock lag model is a REFERENCE.
- Thresholds provisional; Tenement_Big upper floors cannot pass; a stalled close leaves the door open (reported, no retry).
- Runtime acceptance pending; offline tests establish no DayZ behaviour.
