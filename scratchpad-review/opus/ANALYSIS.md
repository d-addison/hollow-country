# Opus analysis of interior-sampler-003 refusal (#11) — input to fix round 5

Source: Opus 5.5 investigator, read-only, at 88054db (r3; r4 726f003 is this branch's HEAD).
[V] verified from census/stock/source, [I] inferred. NS = ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
Census: ~/.cache/hollow-country/experiments/interior-sampler-003/census.json (also -001, -002).
Analyst scripts: /tmp/claude-1000/-code-dayzsa-mods/c2f49688-a754-49e7-ae80-940623b5a25a/scratchpad/an/
Sol r4 review (still-open items): /code/hc-worktrees/interior-r3/scratchpad-review/r4/REVIEW.md

## 1a. Reach = a path from outside reaches the point; closed doors block it
Control only checks outside-box -> point 10 m out. Both filters SetCost(PGAreaType.DOOR_CLOSED, 1000) (sampler ~1396-1400).
[V] Tenement_Small: reached cells only in the stairwell strip x≈-2..1, z≈0..6; paths stop on landings.
[V] Barracks2: only door 0 [7.12,0.08,2.00] reached; rooms behind inner doors code 0.
[V] HouseBlock_2F1: only the two door thresholds; upper-floor paths end on ground floor (vertical gap 7.4 m).
[V] Tenement_Big: only ground stairwell; upper seeds snap 15-29.8 m down -> no filtered navmesh within 1.5 m upstairs.
[V] Control failures: #5 Tenement_Big no outside navmesh (stage 4); #11 HouseBlock drifted to neighbours (gaps 2.6-4.3 m).
[I] FindPath (NS/3_Game/AI/AIWorld.c:98) returns true with a partial path ending at the last reachable polygon.
[V] Stock HouseBlock/Barracks points sit behind inner doors -> calibration measured the method, not the building.

## 1b. Stock vs sampler frame mismatch (safety-critical)
Builder compares stock positions with sampler hits directly in `calibrate`/`_covering`; `_edit_group` writes candidate
x,y,z straight into lootFloor with no conversion.
[V] 18/52 Barracks2 stock points fall outside the building box as-is (box x ±12.88, z ±5.16; stock x -2.71..2.30, z -6.62..9.06).
[V] Stock lootFloor points with a detected cell at same height (±0.15) within 0.75 m:
  as-is: HouseBlock 3/8, Barracks 4/11; rotate +90° (x,z)->(-z,x): 8/8 and 11/11; swap: 4-6/8, 9/11; rotate -90°: 0/8, 9/11.
[I] Stock frame is rotated +90° from the sampler frame. Needs native confirmation before emitting.

## 1c/1d
[V] Player and strict filters give identical 8355 rows (same door cost; extra flags irrelevant).
[V] Calibration scores all stock containers; shelf/weapon points 0.4-1.0 m above floor can never be covered by a floor
sampler. HouseBlock shares its box with 2F5/2F2 (1195 "other" hits).

## APIs (all NS/)
World.GetAIWorld 3_Game/Global/World.c:116; AIWorld.c: PGPolyFlags :1-26, DOOR_OPENED/DOOR_CLOSED :46/:47,
SetFlags/SetCost :65/:67, FindPath :98, RaycastNavMesh :110, SampleNavmeshPosition :122.
Building.c (3_Game/Entities/): GetDoorIndex/GetDoorCount :28/:31, IsDoorOpen/IsDoorClosed/IsDoorLocked :34/:52/:55,
OpenDoor/CloseDoor/UnlockDoor :61/:64/:70, GetDoorSoundPos/GetNearestDoorBySoundPos :73/:82.
IsBoxCollidingGeometry Game.c:1366; RaycastRV DayZPhysics.c:199; CoordToParent/CoordToLocal EnEntity.c:473/:499.

## Recommended server reach rule (all required)
1. Current clearance/snap/waist checks, tolerances unchanged (snap 0.5, end 0.5, sample radius 1.5).
2. Each door recorded not-locked, opened with OpenDoor, observed IsDoorOpen, closed afterwards (throwaway server only).
3. Path from the outside entrance with the unchanged strict filter ends within 0.5 m of the point.
4. Control is "tested" AND has a new "entered" stage (path to ~1 m inside the door). Outside-only no longer counts (r4 P2-1).
5. Doors-open run strictly increases reached counts over the doors-closed baseline, else "door semantics unobserved" -> refuse.
6. Calibration passes on frame-corrected, lootFloor-only stock points of HouseBlock_2F1 and Barracks2 at threshold 0.6.
Ladder/jump/climb-only points excluded. Tenement_Big upper floors cannot pass -> client session or emit nothing.

## Smallest next change
1. Frame evidence: next sampler run casts a vertical RaycastRV at each stock lootFloor point under both as-is and
   rotate+90 transforms and records hits (frame verdict input). Offline ce-probe-001 sphere_samples comparison is the
   lead's job, not the worker's.
2. Builder tools/audit/interior_points.py: two-way stock<->sampler transform, refuse unless a native frame verdict is
   recorded; calibrate/_covering transform stock first and gate on lootFloor only (report shelves/weapons ungated);
   _edit_group converts back to the stock frame before writing; class_candidates/eligible require control tested +
   entered + open/closed door comparison fields; always write the report on refusal (r4 P2-2).
3. Sampler tools/setup/interior_sampler.py: HCProbeReachSetup records door count + lock/open state + sound pos for every
   door (lift the 4-door cap for the record); add "entered" control stage. HCProbeReachHit/HCProbePath: run with doors as
   found, open unlocked doors, fixed delay, run again, close them; store codes for both runs per hit. Filters/tolerances
   unchanged. Optional Tenement_Big diagnostic: include-all/exclude-none SampleNavmeshPosition (diagnostic only).
4. Failing tests first (synthetic fixtures): refuse without frame verdict; rotate+90 round trip is identity; calibration
   uses lootFloor only; refuse when open/closed comparison missing or not increasing; refuse when control lacks "entered".
