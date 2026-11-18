# W6 #60 measured cellar darkness

Source implementation and packaging only. No measured cellar coordinates ship.
The W5 client darkness fallback remains unchanged and yields to native underground
presence. A default install runs no sampler and installs no underground triggers.

The authored class list covers 28 candidate vanilla Residential/Houses models.
Class/model strings were checked against the local installed-config cache
(`structures_residential.pbo`, vanilla) without copying any configs or assets.
They are survey candidates, not confirmed cellar classes. The model path is
checked again through runtime `ConfigGetText` before probing each instance.

The local specifications are absent in this dispatched worktree. Read-only
reference copies of `docs/SPECIFICATION.md` and
`docs/specs/001-survival-overhaul/{spec,plan,tasks}.md` were inspected in the main
checkout. Current
W6 owner decisions take precedence. Trace: #60, FR-011, NFR-001/003/005/006;
shared interfaces follow `docs/RUNTIME_IMPLEMENTATION_CONTRACT.md`.

## Specification, plan and task disposition

- [x] Write one synthetic generator/overlay smoke, record actual RED, implement,
  then record GREEN. Offline JSON checks are not engine evidence.
- [x] Reuse the module registry, core tick and shared verified JSON store. Enumerate
  tiles by cursor, probe at most one building at a time and intersect class boxes.
- [x] Author a standard-library generator using the installed underground schema,
  two triggers per eligible instance, world-space stair breadcrumbs and a hard
  4,096-carrier cap including existing stock rows.
- [x] Reuse optional overlay receipts/backups for merge, drift refusal, rollback
  and export stripping. Add only the authored class list and this guide to the
  package allowlist. The existing bundle installer copies the JSON at its mission
  path; no shared core hook is needed.
- [ ] Identify actual cellar classes/rooms with the native sampler and review its
  boxes. Confidence is a coverage ratio, not acceptance or a statistical guarantee.
- [ ] Survey real stair endpoints. Automatic identification is deliberately skipped:
  collision rays cannot reliably distinguish the actual usable stair route. The
  generator reports missing anchors and emits no triggers for those classes.
- [ ] Windows native compile, DayZDiag, normal signed PBO/server, two-client
  day/night, exterior/upper-floor, torch/NVG, entry/exit, death/rejoin and restart
  checks. Native underground also owns sound attenuation and presence; verify
  those effects. Production enablement and target-load budgets remain pending.

## Local measurement run (lead)

1. Land source and compile normally on Windows. Install the authored mission overlay
   so `hollow-country/cellars/classes.json` exists inside the actual mission. The
   existing private handoff/bundle installer includes it; for a direct local
   rehearsal, copying that authored file to the same mission-relative path is enough.
2. With the server stopped, create the empty marker
   `<profiles>/HollowCountry/measure-cellars`. Start the local server. No client is
   needed to author or execute the sampler, though native ray/map availability
   must be checked in its actual server run.
3. Wait for `[HC Cellars] sampler done`. The scan is intentionally spread over
   many core ticks. The loader gets buildings in 128m tiles, processes at most
   16 returned objects/tick, then up to 3 seed columns (21 rays) or 4 validation
   points (12 rays, plus at most 2 anchor rays)/tick. Native query allocations
   cannot be capped by this API: results over 4,096 abort before cursor work.
   Global bounds are 8,192 instances, 64 classes and a 4 MiB JSON store. Initial
   incomplete and final complete images each use the existing store, once each.
4. Inspect `<profiles>/HollowCountry/cellars-measured.json`. Only `Complete: true`
   is usable. Remove the marker before the next server start to avoid rerunning.
   Interrupted runs leave an incomplete output; interrupted store promotions leave
   `.tmp` for manual recovery, never silently revert to `.bak`.
5. A seed first measures an upward-facing, owner-hit ground floor near terrain
   height, then probes below that measured floor. It requires the cellar floor,
   ceiling and all four walls to hit that same building. Nine points check flat
   floor, ceiling and unobstructed center rays. Successful instance boxes intersect
   into one class box. Rejected instances stay listed as `Eligible: false`.
   Different room selections can make a class inconsistent and prevent generation.
6. For reviewed cellar classes, copy the ORIGINAL authored class list to
   `<profiles>/HollowCountry/cellar-classes.json` (do not use the output JSON).
   Add local, player-height `StairTop` and `StairBottom` vectors at the actual
   stairs and set `StairsMeasured: true`. Bottom must be inside the reviewed room
   box and top must be at least 0.75m higher. Probe checks only confirm a floor
   below those authored anchors; they do not prove stair reachability. Rerun the
   sampler with the marker present. The profile override is local and never ships.

## Generation, install and rollback

From the repository, with output outside any repository:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.audit.cellar_triggers --measured /external/profiles/HollowCountry/cellars-measured.json --out /external/cellar-candidate
```

`cfgundergroundtriggers.json` contains full `Size` extents and yaw-oriented boxes.
The outer stair envelope uses two world-space breadcrumbs and `UseLinePointFade`;
the inner box uses `EyeAccommodation: 0` and no breadcrumbs. No custom carrier,
RPC or client-owned state is introduced. Confidence must be strictly greater
than 0.85 by default; `--min-confidence` can raise that threshold. The sibling
`cellar-trigger-report.json` reports excluded classes and rejected instances.
Both files are local build output and must never enter source control or bundles.

Stop the server before installation or rollback:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.audit.cellar_triggers --install /external/cellar-candidate --mission /external/mission
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.audit.cellar_triggers --rollback --mission /external/mission
```

If the mission has no trigger file, installation requires
`--native-baseline /external/installed-world/cfgundergroundtriggers.json`, read
from the installed Chernarus data. This prevents masking the native fallback.
Existing trigger rows retain their indices and bytes are backed up under
`hollow-country-cellars/receipt.json`; install and rollback refuse drift. Restart
after either operation. Bundle export restores the pre-overlay bytes in memory
and removes the cellar receipt and generated additions. Do not use generic bundle
rollback to remove this separate local overlay: use the cellar rollback first.

Native references: installed `scripts-1.30.164289/3_Game/UndergroundAreaLoader.c`
69–99 (DTO), 105–132 (loader), 156–169 (carriers);
`4_World/Entities/ScriptedEntities/Triggers/UndergroundTrigger.c` 10 (index cap),
90–118 (size/type), 164–186 (entry/exit);
`4_World/Classes/UndergroundHandlerClient.c` 203–277 (world stair breadcrumbs).
The sampler header cites every native query, transform, raycast and file API.

## Limits and runtime evidence still needed

This produces one conservative rectangular room candidate per building instance,
not complete connected-cellar topology. The terrain-adjacent ground-floor search
band, model-space collision bounds, normal direction, geometry-LOD ray ownership,
coarse 5x5 seed grid and nine-point clearance must be verified in the native run.
Unusual entrances, slopes, tilted buildings, missed rooms or mismatched models
are rejected or can be missed; confidence does not establish coverage of all
Chernarus cellar designs. Stair-envelope spill into adjacent rooms or upper
floors and actual lighting/eye-accommodation behavior need visual inspection.
Only reviewed measurements should be installed for testing. Nothing observed in
DayZ yet.
