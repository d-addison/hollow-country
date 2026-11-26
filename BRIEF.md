# Brief: v16-bindcap. Bound the room template bind per call (perf R2 27 ms, release blocker)

Branch rt/v16-bindcap (already checked out here, base 0d6488d6 = rt/v16-integ). Enforce only.

## Evidence (soak 195, server RPT; one player)
`perf_rule=R2 owner=InfectedVariety stage=module heaviest=posture_candidate ms=27.130 window=3` (limit 20 ms,
config/acceptance-targets.json perf_r2_max_ms; tools/release/release_gate.py:347-351 refuses it).
`[HC Step] owner=InfectedVariety window=3 ... posture=270773 ... place_fits=268289` (raw TickCount, 10000/ms):
one HCVarietyPlaceFits call (Variety/HCInfectedVarietyModule.c:369-374) cost 26.8 ms. The next window it cost
0.5 ms, so the cost is the COLD bind: HCInfectedRoomCatalog.BuildProductionOrder (Infected/HCInfectedRooms.c:1531)
-> BindTemplateHouses (:1473): GetObjectsAtPosition3D r=s_BindRadius (30 m), a filter loop over up to
MAX_TEMPLATE_CANDIDATES=1024 objects (House.Cast, GetPosition, GetType, ClassRow), then AdmitTemplateHouse for up
to MAX_TEMPLATE_FOUND=16 houses. Search packs reach the same bind through BuildOrder (:1523).

## What to build
1. Make one BindTemplateHouses call bounded and resumable, so no single call does the full cold bind:
   - cap NEW admissions per call (cached houses re-stamp cheaply and do not count); the houses found but not yet
     admitted are admitted on later calls for the same area (a small static pending set keyed by House, weak
     refs re-checked for null, bounded, cleared when the clue moves away or on the catalog reset paths that clear
     s_TemplateBindings). Keep the ambiguity check (TemplateAmbiguous) against the full found list.
   - bound the filter loop: process at most a fixed number of candidate objects per call (choose and justify the
     number; Enforce costs roughly a few µs per object here) and do not re-run the native query on every call
     for the same clue while a partial scan is pending (reuse the held candidate list with weak refs, or re-query
     only when the clue moves > a few metres). Keep s_BindQueryCap semantics (native queries per tick).
   - a partially bound area returns the bindings that already exist (no fake "fits"); the variety caller treats
     "not yet bound" as not fitting this time, exactly as today's empty result.
2. Instrument: split the existing helper timing so the next soak shows where the cost is. Add sub-timings
   (native query, filter loop, admissions) to the existing InfectedVariety [HC Step] helpers line or a sibling
   rooms line on the same cadence (no new per-tick spam; reuse the existing window reporter). Raw TickCount units
   like the existing fields.
3. Target: the worst single InfectedVariety tick under ~8 ms on a cold dense town, with the per-call caps chosen
   from your static estimate; state the estimate and how the soak line will confirm or refute it.

## Rules
Inspect native APIs in ~/.cache/hollow-country/native-scripts/scripts-1.30.164289 before calling them and cite
them. Non-Managed classes held by non-ref variables are raw pointers (not nulled on free); House/Object are
Managed (weak refs auto-null). No `vector / float` in Enforce (multiply by 1.0/x). No duplicate local names in
sibling scopes. Keep work bounded per tick; no new [HC Use] counters; do not change activity expectations.

## Files you own
mods/HollowCountry/scripts/4_World/Infected/HCInfectedRooms.c,
mods/HollowCountry/scripts/4_World/Infected/Variety/HCInfectedVarietyModule.c (helper reporting only).

## Done
Commit on rt/v16-bindcap (no attribution lines). Run lint and perf and quote their summary lines:
`agent-run --memory 4G -- python3 -B -m tools.validate.enforce_lint --native-scripts ~/.cache/hollow-country/native-scripts/scripts-1.30.164289 | grep 'enforce_lint: '`
`agent-run --memory 4G -- python3 -B -m tools.validate.enforce_perf`
Report: the caps, the per-call cost estimate, the new evidence line text, and any behaviour change. Never start
DayZ, the compile gate, Workbench or a soak; the lead runs the gate. No unit tests. Never claim multiplayer proven.
