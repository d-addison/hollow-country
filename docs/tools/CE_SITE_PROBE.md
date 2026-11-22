# HC CE site probe (lead only)

This stages a vanilla runtime with HC CE data installed through `hc_events.install`.
It never launches DayZ. Use fresh storage for **each** treatment. Workers only run
`--dry-run`; native launch and inspection belong to the lead under the shared host
lock, with no other native tools or owner play session running.

Validate inputs on Linux without writing a runtime:

```sh
mkdir -p tmp/logs
python3 -B -m tools.setup.ce_site_probe stage --destination tmp/logs/ce-site-dry --dry-run
```

Real staging needs `/mnt/d/HollowCountryLocal`: the shared runtime verifier and
Windows launcher intentionally constrain destinations to named children of that
root. It copies the verified stock-backup mission from `vanilla-p0-001`; the
source remains read-only. No mods or profile snapshots are imported. In the
confined worker environment `/mnt/d` is read-only, so full staging is deferred
to the lead; the dry-run validates authored data and the generated hook locally.

```sh
python3 -B -m tools.setup.ce_site_probe stage \
  --destination /mnt/d/HollowCountryLocal/ce-site-current-001 --treatment current
```

On Windows, after acquiring the normal shared native-tool host lock:

```powershell
.\tools\setup\Start-CEProbeServer.ps1 -Runtime D:\HollowCountryLocal\ce-site-current-001 -Kind ce-site-probe
```

The hook measures every authored HC group/cache position and cache rings at
4/8/12 m over eight bearings. IDs are `event:siteNNN` and
`event:ringRR_B`. It samples 16 targets per timer tick (hard cap 400 targets).
`IsBoxColliding` measures geometry within a conservative box of half-width
`BLOCKER_RADIUS_M=2` and height 2 m above the ground; it includes objects whose
origins lie outside that box. `nearest` reports the nearest returned collider's
class and **origin** distance, scanning at most 512 returned colliders. Blocker
count still includes the entire returned list. Existing CE-spawned objects may
appear as blockers; inspect such observations before choosing a treatment.

The hook prints `[HC SiteProbe] done targets=N` and writes
`profiles/HCCESiteProbe/complete.txt` after a hold of at least 240 seconds **after
sampling**, hence at least four minutes after mission initialization. Configure
`--hold-seconds` and `--wait-minutes` at staging; timeout must have 120 seconds of
headroom. The launcher waits for the fixed sentinel and stops only its server.

Ingest the run's RPT (requires the probe rows and the native CE lines in that log):

```sh
python3 -B -m tools.setup.ce_site_probe ingest \
  --rpt /mnt/d/HollowCountryLocal/ce-site-current-001/profiles/DayZServer.RPT \
  --out tmp/logs/ce-site-current-measured.json
```

Use the actual RPT filename. `--plan PATH` overrides discovery of the plan one
level above `profiles`. Ingest refuses missing/duplicate targets, malformed rows,
coordinate drift, missing completion, or a different run binding. It records
all observations, including unusable sites, and counts VehicleRespawner failures
separately for `Init` and `Respawning`, retaining event names and amounts.
Provenance includes the pinned server exe SHA, a SHA of the sorted stock mission
file/hash manifest, exact probe-plan SHA, exact RPT SHA, staging date, ingest date
and treatment. The original logs and plan remain local evidence, not repo data.

```sh
python3 -B -m tools.setup.ce_site_probe stage \
  --destination /mnt/d/HollowCountryLocal/ce-site-measured-001 \
  --treatment measured --measurements tmp/logs/ce-site-current-measured.json
```

Native `float.ToString()` prints six significant digits, so a row echoes coordinates
only to about 0.1 m at 10 km. Ingest checks each echo against the plan within that print
precision and stores the exact plan coordinates.

For a cause-isolating lead diagnostic, `--treatment factorial --variants V.json
--measurements M.json` applies explicit per-event spawn-definition variants to the
installed `cfgeventspawns.xml` before the staged manifest is hashed: `y` (measured
terrain height), `zone` (`[dmin, dmax, r]`) and `angle` (replaces `a="-1"`). Every HC
event must be listed; `{}` is an explicit control. The variants are recorded in the
plan. A factorial runtime is evidence for choosing a fix, never a shipped treatment.

Run and ingest this second fresh runtime in the same way. The measured treatment
refuses missing group observations or coordinate drift. It emits terrain `y` on every
group position. Group anchors that fail the screen (water, slope above
`MAX_SLOPE_DEG=12`, or any geometry blocker inside the clearance box) stay in the
output, because CE retries other anchors and relocation needs native candidates.
The install report lists them under `measured_unusable_anchors`. It also emits and at least `MIN_CACHE_POSITIONS=3` usable measured positions per cache,
all within `CACHE_RADIUS_M=15` of its authored anchor (observer radius is 25 m).
Unusable cache candidates are retained in evidence but excluded from output.
Observations are never silently dropped.

After native review, the lead can commit the ingested JSON as
`mission/hollow-country/ce/hc-site-measurements.json`; the installer automatically
uses it and includes its bytes in receipt ownership. With that file absent,
output and source digest are unchanged. `current` always explicitly omits it,
so the control remains reproducible after measurements land. No measured data
or generated artifacts are included with this implementation. Run 003 (2026-11-22 UTC,
current treatment) is committed this way.

Event-definition variants are also available: `event` overrides `lifetime`, `restock`,
`saferadius`, `distanceradius`, `cleanupradius` or the `deletable`/`init_random`/
`remove_damaged` flags in the managed `events.xml`, and `"db": true` moves the event
definition into `db/events.xml`. Factorial-003 isolated `restock`: every HC fixed
event with restock 300 or 600 failed its VehicleRespawner Init and never spawned
during the hold, and every one with restock 0 (the vanilla static-event value)
spawned. Radii, `deletable` and the db move made no difference. HC events now ship
restock 0, and validation requires it.

This survey does not prove that adding `y` cures CE placement, that zero zones
are valid, that an entire composed scene fits, that candidates pass CE internal
rules, or that scene missions find their cases. It does not establish multiplayer
behavior or release acceptance. Compare native failure counts on both treatments,
inspect RPT/boot evidence and perform the owner's one-client scene-cache smoke.
