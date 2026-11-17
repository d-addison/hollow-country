# Interior sampler/builder fix round 5 (issue #11) - writer report

Worktree /code/hc-worktrees/interior-r5 (branch hc/interior-r5, base 726f003). No git state changed.

## Files changed (only the four owned files)
- tools/audit/interior_points.py (builder)
- tools/setup/interior_sampler.py (sampler hook + stager)
- tests/unit/test_interior_points.py
- tests/unit/test_interior_sampler.py

## Method: RED then GREEN (logs in scratchpad-review/r5-fix/)
- red-builder.log: `Ran 22 tests ... FAILED (failures=19, errors=15)` -> builder GREEN `Ran 119 tests ... OK`
- red-census-invalid.log (ported r3 follow-up 1): `AssertionError: 'census-invalid' != 'invalid-input'`, `Ran 123 tests ... FAILED (failures=7)`
- red-hook.log (frame check, door run, stager): `Ran 20 tests in 0.759s / FAILED (failures=6, errors=16)`
- GREEN: `python3 -m unittest tests.unit.test_interior_points` -> `Ran 123 tests ... OK`;
  `tests.unit.test_interior_sampler` -> `Ran 150 tests ... OK`;
  the 20 RED tests -> `Ran 20 tests ... OK`.
- Full suite (interior-r5-full.log in the session scratchpad): `Ran 2634 tests in 191.171s / OK (skipped=1)`.

## Default hook
`render_hook(sampler_targets())` (no frame points): 72583 bytes, sha256 8fb3ab227278c2e20159b352703d2b5e29576d0e71c5e4c95e22991ad4bd1b94.
The staged hook adds `HCProbeFrameAdd` loaders, so the staged plan's probe.hook_sha256 differs from the default; read it from the plan.
lint_sampler_hook is clean (also against the 1.30.164289 native type names, 7190 types).

## What changed
Builder: two-way stock<->sampler transform (stock_to_sampler/sampler_to_stock; sampler=(-z,y,x) of stock), refusal unless a native frame verdict (as-is/rot90) is recorded; calibration and _covering gate on lootFloor only (shelves/weapons reported, not scored); _edit_group converts back to the stock frame; class_candidates/eligible require control tested, an "entered" stage, and door open/closed fields whose reached counts strictly increase (else refusal "door semantics unobserved"); a report is always written on refusal, CLI exits 1.
Sampler hook: frame check (2 vertical RaycastRV per stock lootFloor point, as-is and rot90, from the building ray budget); every door recorded (cap 64, was 4) with locked/open flags; "entered" control stage after a passed control (inside point 1 m behind the door, path from the outside entrance must end inside the box); later doors are tried until one enters; reach codes run with doors as found, then unlocked closed doors are opened (OpenDoor), a bounded wait (30 ticks of 100 ms, m_HCProbeDoorDelayTicks), codes run again (open_codes/open_player_codes, own path counters open_paths/open_player_paths, reach_diag strict_open/player_open), doors are closed again (CloseDoor) and re-observed; a ray-capped/output-capped building is not opened ("skipped-capped"); nothing is locked, moved or deleted. Filters and tolerances unchanged. Stager: holds mapgroupproto.xml, inlines up to 32 lootFloor points per calibration class (even stride), refuses a class with none, writes plan["frame_check"] and plan["door_run"].
Compile rules kept: no engine-type identifiers, no leading `||`/`&&`, no ternary, no duplicate sibling locals, <= 8 '+' per statement, explicit ToString, bounded loops, no comments/else in hook methods. Helper methods that would return vector/PGFilter were made void members-setters (HCProbeUseFilter/HCProbeUseEntrance) because the offline transpiler models only void/bool/int/float/string returns.

## r4 findings
- P2-1 (control must prove entry): FIXED in builder (control-not-entered refusal) and hook (entered stage). Offline only.
- P2-2 (always write the report on refusal): FIXED (builder and CLI; every refusal kind, including census-invalid and invalid-input).
- Opus causes 1a (closed doors), 1b (frame), 1d (container scope): code paths in place; NOT proven natively.

## What the next native sampler run must show for calibration to pass
1. row["frame"] records for both calibration classes giving a rot90 verdict (rot hits >= 0.8 fraction, margin >= 0.25 over as-is, >= 4 records).
2. door_run: opened > 0, observed_open == opened, restored == opened, state "done".
3. entered.<source>.open == "entered" with reach.state "tested" (closed may be "not-entered").
4. open_codes reaching strictly more cells than the doors-as-found codes (the door-semantics check).
5. lootFloor coverage >= 0.6 after the rot90 transform for each calibration class.

## Remaining gaps
- Frame verdict and door semantics are unproven natively; offline tests never establish DayZ behaviour. Runtime acceptance stays pending.
- Thresholds (0.8 fraction, 0.25 margin, 4 records, 30-tick delay) are provisional.
- The open pass assumes the native navmesh reacts to OpenDoor within the delay; OpenDoor may animate and AI door polys may update later.
- Tenement_Big upper floors cannot pass (no stair/ladder access with the walk filter).
- The entered check samples the mesh at SurfaceY under the inside point, so a door on an upper level would be read "not-entered".
- Open-pass rays share the building ray budget; a close-to-limit building may leave open-pass cells -1.

## Ported r3 follow-ups
1. census-invalid refusal identity report (kind census-invalid, census/stock sha256, reach_source, empty funnel; CLI writes it and exits 1): real TDD, RED log red-census-invalid.log. r5 difference: bad parameters yield an "invalid-input" report.
2. Unknown (-1) final-gap ray maps to gap_blocked, plus battery check `unknown-final-gap-ray`: characterization test (the hook already fails closed), mutation-checked against a mutant of HCProbeBlocked.
