# HC-31 — First measured cellar slice

Source/package implementation for #60 / #151 access, FR-011 and NFR-003.
Runtime acceptance pending. All 28 queued classes are **pending native survey**;
there are **zero observed measured classes and zero admitted spaces** in this
handoff. No coordinates, measured boxes, game assets or native receipts ship.
Two representative stair-connected spaces still need measurement and native
qualification; the other 26 retain their individual `HC31-01`…`HC31-28` survey
IDs in `classes.json`. Selecting two spaces never promotes a class or its peers.

The current worktree omits `docs/SPECIFICATION.md` and
`docs/specs/001-survival-overhaul/{spec,plan,tasks}.md`. Their reference copies in
the lead checkout were read without edits. Active-session decisions supersede
those older documents. HC-11 owns consolidated spec → plan → task integration;
this guide records the HC-31 slice and unfinished native tasks. Shared interfaces
follow `docs/RUNTIME_IMPLEMENTATION_CONTRACT.md`.

## Implemented behavior

- Failed stair anchors produce `Eligible: false`,
  `Reason: stair_anchor_probe_failed`, and **no AcceptedInstances increment**.
  A failed instance never rewrites class-level authored `StairsMeasured`.
- `GeometryMeasured` records nine successful geometric checks;
  `StairAnchorsValid` records owner-hit floors below both surveyed endpoints.
  Neither proves that stairs or connected rooms are walkable. Missing anchors
  remain `stair_anchors_unmeasured`. Class dispositions remain pending, or
  refused for inconsistent boxes, with a reason and retained survey task.
- The sampler uses its retained tile/object/seed/check/summary cursors with
  HCUnitBudget (24 units/tick) and HCWorkBudget. One query/summary costs the
  entire slice; a seed costs 7 units; a validation point reserves 5 units,
  including possible final anchor checks; a cursor object costs 1 unit.
  Existing caps still limit work to 16 objects, 3 seeds or 4 validation points.
- Admission is marker-only diagnostic work, independent of furnishing. No
  second HC-24 pack reader or schema is introduced; HCInteriorPackIndex and
  its schema-2 leaf interface/schema-3 paged index remain owned by HC-24.
  No player query, furniture, inventory, door, RPC or live trigger mutation occurs.
- HCGetOperationalStatus returns cached HC-1 status. `ready` means only that
  the diagnostic sampler started; the Cellars module itself stays `refused`.
  Every HC-31 receipt keeps `admitted=0` and
  `runtime=PENDING`. Off ticks perform no query or IO. Stop clears buffers and
  resets cursors. Interrupted outputs remain incomplete and require recovery.
- HCCellarsModule emits one HC-31 count receipt per start, alongside its retained
  V2 preference diagnostic. Pending is the validated authored class-list count;
  measured counts distinct known classes with explicit instance `GeometryMeasured`
  in completed, zero-skipped-tile output. Scores, anchors and selection do not
  imply measured geometry or qualification. Missing output means zero measured;
  malformed, interrupted, duplicate/unknown classes or oversized input report
  `measurement_counts_unavailable`. Counts remain zero where unavailable; a
  validated authored pending count is retained. HC-1 caches the same refusal.
  The sampler uses `[HC Cellars] HC-31 sampler` for its separate lifecycle counts.
- Shared 3_Game HCCellarAdmission stays closed with
  `native_cellar_qualification_pending`. The retained client depth heuristic
  checks it before allocation and before sampling. Local preference and server
  EnableAmbientLife cannot open it; HCVisualActive stays false and the native
  underground lighting/audio path remains owner. No new settings RPC is added.
- Generation requires explicit `Eligible`, `GeometryMeasured`,
  `StairAnchorsValid` and `SliceSelected` booleans on each selected instance.
  Missing evidence fails closed. At most **two spaces / four native triggers**
  may be generated or installed. Skipped tiles refuse generation, rather than
  overstating survey coverage. Reports retain every input class and instance
  refusal, independently of the selected slice.
- The existing verified intent/backup/copy/readback store and optional overlay
  receipt/rollback protocol are reused. The generated report binds the trigger
  payload and reviewed measurement by SHA-256; install binds the report as a
  source too. Drift refuses. No rename/fsync guarantee is claimed.

## Native API evidence and refusal

Installed read-only source root:
`~/.cache/hollow-country/native-scripts/scripts-1.30.164289/`.

- N16 `3_Game/Entities/Object.c:370` collision bounds; `:873–874` model/world
  transforms; `3_Game/Global/DayZPhysics.c:130–144,199` owner-hit geometry rays.
  These expose geometry, **no automatic traversable-stair/connected-room proof**.
  Named refusal: `native_stair_route_unobserved`.
- N13 `3_Game/UndergroundAreaLoader.c:69–99` JSON DTOs; `:105–132` mission/world
  fallback selection; `:147–176` native carrier creation and sync.
- `4_World/Entities/ScriptedEntities/Triggers/UndergroundTrigger.c:10` indices
  0…4095; `:90–118` full Size extents and native trigger types; `:164–186`
  client entry/exit. `4_World/Classes/UndergroundHandlerClient.c:203–277` consumes
  world-space stair breadcrumbs. Lighting/audio remain native responsibilities.
- `4_World/Plugins/PluginBase/PluginUndergroundTriggerManager.c:1` is guarded
  by DIAG_DEVELOPER; it is a diagnostic authoring tool, not a production API
  for identifying stairs. No dependency on it is compiled into this sampler.
- Existing sampler header cites query, transforms, IO and scalar APIs.
  HCWorkBudget cites `3_Game/Global/Game.c:914` for the cooperative time guard.

## Native survey and rehearsal (lead)

1. Compile exact source with DayZDiag, then a normal signed PBO/server. Install
   the authored mission overlay at `hollow-country/cellars/classes.json`.
   Default installation has no marker and no additional underground triggers.
2. With server stopped, create `<profiles>/HollowCountry/measure-cellars`.
   On a fresh profile with the shipped class list, expect exactly one
   `[HC Plan] HC-31 cellar_measured=0 admitted=0 pending=28 state=refused refused=native_cellar_qualification_pending runtime=PENDING`.
   HC-1 must report `module=Cellars state=refused` with that refusal reason.
   The independent sampler should report `[HC Cellars] HC-31 sampler` with
   `state=ready` and `refused=measurement_only_native_stair_route_unobserved`.
   A client with its local preference on should report
   `[HC Plan] HC-31 client state=refused refused=native_cellar_qualification_pending runtime=PENDING`.
   These are expected diagnostics, not observed logs.
3. Wait for `[HC Cellars] sampler done`. A retained 128m tile scan queries a
   91m radius and owns origins using half-open tile bounds. Results over 4,096
   objects/cargos skip the tile and increment SkippedTiles; no full-coverage claim
   follows. Global caps: 8,192 instances, 64 classes, 4 MiB JSON, one active house.
   Native query allocations and serialization cannot be preempted; performance
   budgets remain provisional for 3–6 players.
4. Inspect `<profiles>/HollowCountry/cellars-measured.json`. Only `Complete: true`
   and `SkippedTiles: 0` may reach generation. A seed requires owner-hit ground
   floor, lower floor, ceiling and four walls; nine points require flat floor,
   ceiling and clear center rays. Class boxes intersect successful instances;
   incompatible intersections refuse generation. This is one rectangular room
   candidate, not a connected-room topology or exhaustive enterability census.
5. Survey real stair endpoints. Copy the ORIGINAL authored list, preserving
   all 28 survey tasks and TriggerDefaults, to
   `<profiles>/HollowCountry/cellar-classes.json`. Set local player-height
   StairTop/StairBottom and StairsMeasured only after manual measurement.
   Bottom must meet the measured room; top must be at least the existing 0.75m
   higher. Rerun. Endpoint floor rays do not establish a usable walking route.
6. Remove the marker. Preserve raw measurements externally. In an external
   review copy of the completed output, mark `SliceSelected: true` on at most
   two explicitly reviewed instances representing different stair/room layouts.
   Do not edit eligibility to bypass a refused sample. Missing measurements mean
   no selection, no generated trigger and no class-name enterability inference.

## Generation, installation and rollback

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.audit.cellar_triggers --measured /external/reviewed-cellars.json --out /external/cellar-candidate
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.audit.cellar_triggers --install /external/cellar-candidate --mission /external/mission
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.audit.cellar_triggers --rollback --mission /external/mission
```

Stop the server before installation or rollback; restart after either operation.
If the mission lacks cfgundergroundtriggers.json, install requires
`--native-baseline /external/installed-world/cfgundergroundtriggers.json`.
Existing native rows and indices remain first, with the combined 4,096 cap.
Rollback restores the exact previous bytes (or absence), including after using
an external native baseline. The managed receipt is
`hollow-country-cellars/receipt.json`. Bundle export strips this local overlay
and restores the original bytes; use cellar rollback before generic rollback.
Generated files, coordinates and receipts remain external/private.

The generator emits a bounded yaw-oriented room and a stair endpoint envelope,
world-space breadcrumbs, UseLinePointFade and native EyeAccommodation. Confidence
must exceed 0.85, but remains a probe ratio, never runtime qualification.
`cellar-trigger-report.json` lists all classes, pending/refused reasons, selected
count, generated count and hashes; `admitted` remains zero throughout rehearsal.
Install requires the matching HC-31 report, so legacy candidates must be resampled.

No new distances were introduced. Two existing generator distances moved into
`TriggerDefaults` in classes.json: StairEnvelopePaddingMeters = **0.75m** and
BreadcrumbRadiusMeters = **3m**. They are room-scale fractions (0.00075 and 0.003)
of the approximately **1000m** native network bubble / rifle hearing reference,
not visibility/hearing extensions. Overrides may shrink them; generation refuses
expansion beyond the authored limits. All other sampler distances are unchanged.

## Acceptance still pending

For each of the two selected spaces, retain exact source/PBO/mission/config and
installed dependency hashes, raw logs and two-client receipts externally. Walk
stairs in both directions, connected rooms, outside and upstairs by day and night;
check torch, NVG, native audio, death/rejoin and restart. Verify no effect spill,
no door/path blockage, no script/CE errors and native lighting/audio fallback.
Exercise marker-off ticks, mid-scan marker removal, stop/restart, interrupted store
recovery, overlay removal and byte-exact rollback. No production enablement until
DayZDiag AND normal PBO/server AND both clients pass. The other 26 remain native
survey/access tasks; absence of a probe result is pending coverage, not exclusion.

## TDD receipt and remaining integration

Round 2 focused command (run RED, then GREEN):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_cellars test_v2_optional_overlays -v
```

Actual RED: `Ran 4 tests`, `FAILED (failures=2)`:
`AssertionError: 0 != 1 : cellar startup must publish one measured-count receipt`;
legacy smoke printed `authored TriggerDefaults required; no guessed distances`
and failed with `AssertionError: 2 != 0`.
Actual GREEN: same command, `Ran 4 tests`, `OK`.
A further focused RED (`test_hc_cellars -v` with the same environment) recorded
`AssertionError: False is not true : sampler must not duplicate the module startup receipt`;
the combined focused command then returned `Ran 4 tests`, `OK` again.

Final guard commands:

```sh
rg -l -i cellar tests/unit
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_cellars test_enforce_lint test_v2_optional_overlays test_package test_script_syntax test_enforce_locals test_script_identifiers test_enforce_formula_complexity test_hygiene -v
python3 -B -m tools.validate.enforce_lint --no-native
```

The search returned test_hc_cellars, test_enforce_lint and
test_v2_optional_overlays. Actual GREEN: `Ran 120 tests`, `OK (skipped=1)`;
the existing Windows PowerShell execution check belongs to Windows CI.
Actual lint GREEN: `enforce_lint: pass findings=124 new=0 stale=0 native=no`.
No lint baseline additions or removals were necessary.

The existing single HC-31 behavioral test now also executes authored startup,
counting, cached HC-1 status, off/stop handling, repeat-start suppression,
interrupted/invalid/duplicate/unknown measurement refusal and closed client
initialization/sampling using explicit synthetic DTO/native IO ports. It retains
the stair failure, work budgets and generator/rollback checks from round 1.
The legacy overlay smoke supplies all four evidence booleans and synthetic
TriggerDefaults explicitly, retaining native DTO/overlay/rollback assertions.
No evidence requirement was relaxed. Offline evidence only.

Completed integration: HCCellarsModule status/receipt and retained registration;
shared admission and client allocation/sample guards; legacy synthetic fixture.
No edits to HCModule.c, config.cpp or furnishing readers are needed.

Remaining lead integration: HC-11 retains consolidated spec → plan → task
integration. No worker source edits remain deferred to the lead. Native survey,
qualification protocol/receipts, DayZDiag, normal PBO/server and two-client
acceptance remain pending as listed above. A future qualification protocol must
identify individual spaces; class ancestry, SampleCount, Eligible, selection and
HCV2Admission.Admitted(preference) must never promote an entire class.

Startup inputs reuse HCGroupJson/HCGroupIO with a 32 KiB authored-list limit and
its existing 1 MiB shared measurement-read cap, 64 classes and 8,192 instances.
Larger measurement JSON is refused for startup counts; no automatic fallback to
backup or partial file occurs. The sampler's configured serialization ceiling
remains 4 MiB, but shared HCGroupIO currently caps actual reads/writes at 1 MiB;
this shared framework limit is outside HC-31 ownership and is not native-tested.
Framework reused: HCOperationalStatus/HC-1, HCGroupJson/HCGroupIO,
HCV2Admission diagnostic, HCUnitBudget/HCWorkBudget, verified store and reversible
overlay protocol. HCCellarAdmission is the only new admission policy; it adds no
scheduler, RPC, geometry controller or distances. Nothing observed in DayZ yet.
