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
  the diagnostic sampler started; every HC-31 receipt keeps `admitted=0` and
  `runtime=PENDING`. Off ticks perform no query or IO. Stop clears buffers and
  resets cursors. Interrupted outputs remain incomplete and require recovery.
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
   Boot and observe `[HC Plan] HC-31 cellar_measured=0 admitted=0 pending=28`
   with `state=ready`, `refused=measurement_only_native_stair_route_unobserved`
   and `runtime=PENDING`. This is a proposed diagnostic, not an observed log.
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

## TDD receipt and lead integration

Focused command:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_cellars -v
```

Actual RED: `AssertionError: 1 != 0 : failed stair sample was counted accepted`;
`Ran 1 test`, `FAILED (failures=1)`. After extending the same behavior to the
first-slice generator, RED: `KeyError: 'admitted'`, `FAILED (errors=1)`.
GREEN: same command, `Ran 1 test`, `OK`. The one synthetic behavioral test executes
authored sampler handlers and shared budgets through existing restricted ports,
then checks strict selection, all 28 dispositions, native DTO transforms, cap,
stock preservation, drift, rollback and off/stop cleanup. Offline evidence only.

Lead edits outside worker ownership:

- In HCCellarsModule.c keep the existing registration and V2 diagnostic. Add
  `protected ref HCOperationalStatus m_HC31Status = new HCOperationalStatus;`
  and `override HCOperationalStatus HCGetOperationalStatus() { return m_HC31Status; }`.
  In IsEnabled retain the settings/EnableAmbientLife predicate, publishing
  `m_HC31Status.HCPublish("off", "operator_preference_or_settings_off");` when
  false. Replace the stale `mode=client_below_terrain` Print with these exact
  startup statements for this currently unqualified handoff:

  ```c
  m_HC31Status.HCPublish("refused", "native_cellar_qualification_pending");
  Print("[HC Plan] HC-31 cellar_measured=0 admitted=0 pending=28 state=refused refused=native_cellar_qualification_pending runtime=PENDING");
  ```

  Add `override void OnStop() { m_HC31Status.HCStop(); }`. The sampler separately
  reports geometric counts once actually measured. A future bounded native
  qualification receipt may replace these initial zeros; it must identify
  individual measured entries, never promote an entire class. Do not let
  HCV2Admission.Admitted(preference), ancestry, SampleCount, Eligible or
  SliceSelected authorize production triggers. No config.cpp hook is needed.
- Module admission alone cannot gate the existing separate client depth
  heuristic. In `scripts/5_Mission/Atmosphere/HCCellarsClient.c`, replace the
  `m_HCCellars = new HCCellarsClient;` statement in MissionGameplay.OnInit with:

  ```c
  Print("[HC Plan] HC-31 client state=refused refused=unmeasured_depth_heuristic runtime=PENDING");
  ```

  Keep super.OnInit, the preference/authority checks and stop cleanup. This
  removes automatic terrain-depth darkness admission, leaves HCVisualActive
  false and preserves the native UndergroundHandlerClient fallback. This file
  is read-only for this worker; the required lead edit is **not implemented**.
- HC-11 records source implementation complete and native acceptance pending
  for HC-31, linking this guide, the six owned paths and both RED/GREEN receipts;
  keeps two representative qualifications and the remaining 26 tasks open.
- The read-only legacy test_v2_optional_overlays.py cellar fixture must add
  `TriggerDefaults` from the authored classes.json to its root measurement,
  and `Eligible=True, GeometryMeasured=True, StairAnchorsValid=True,
  SliceSelected=True` to its synthetic instance. Its old implicit-acceptance
  fixture now intentionally refuses. Keep its existing overlay/rollback assertions.

Guard command (actual result: `Ran 85 tests`, `OK`):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_cellars test_script_syntax test_enforce_locals test_script_identifiers test_hygiene test_enforce_lint test_enforce_formula_complexity -v
```

Legacy fixture check (actual result: `Ran 87 tests`, `FAILED (failures=1)`;
`authored TriggerDefaults required; no guessed distances`, followed by
`AssertionError: 2 != 0` in the cellar overlay smoke):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_script_syntax test_enforce_locals test_script_identifiers test_hygiene test_enforce_lint test_enforce_formula_complexity test_v2_optional_overlays -v
```
