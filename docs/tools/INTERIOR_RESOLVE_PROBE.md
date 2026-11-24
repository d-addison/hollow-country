# Disposable Interiors building-resolve probe

Status: tooling only; native compile and measurements pending. Never changes
`HCInteriorPlacementCursor.c`. Stage/ingest never launch anything. Only the lead
runs the staged mission under DayZDiag, with no owner session active.

The default selects three distinct, evenly spaced furnishing-catalog origins for
each of the seven heavy classes (Barracks3 and Barracks4 separately), plus
Land_City_Stand_News1 and Land_Shed_Closed2 (Land_Garage_Row_Big left the set on 2026-11-24:
the regenerated template pack has no furnished garage rows). These are provisional
cheap controls, not measured performance claims. `--per-class 1..16` refuses when
any class has fewer catalog instances; the default includes all three Closed2
entries. Plans pin furnishing pages, geometry templates, stock init and generated
payload hashes. No purchased assets or logs enter the repo.

## Installed API inventory

References below are relative to the installed **1.30.164289 scripts cache**.
These are observed declarations, not proof they resolve static landscape buildings.
All independent point-query families below are exercised, one native call per
server `OnUpdate`, with its repeat on the immediately following update.

| Probe API | Native declaration and parameters |
| --- | --- |
| query2d_small / query2d_tile | `3_Game/Global/Game.c:923`, GetObjectsAtPosition, radius 0.05 / 0.531 |
| query3d_zero / query3d_small / query3d_current | `3_Game/Global/Game.c:930`, GetObjectsAtPosition3D, radius 0 / 0.05 / 0.75 |
| ray_geom / ray_view | `3_Game/Global/DayZPhysics.c:199`, RaycastRV, Geom / View, nearest contact |
| ray_proxy | Same file `:208`, RaycastRVProxy; params `:49–91`, Geom; object and parent `:98–111` |
| box / box_geom / box_proxy | `3_Game/Global/Game.c:1333`, `:1366`, `:1368`; 0.1 m edges; Geom primary/secondary. Proxy params/results: `3_Game/IsBoxCollidingGeometryProxyClasses.c:13`, `:29–40` |
| bullet_ray / bullet_sphere | `3_Game/Global/DayZPhysics.c:211`, `:213`; BUILDING layer (`:6`), sphere radius 0.05 |
| sphere_overlap / cylinder_overlap / capsule_overlap / box_overlap | Same file `:222–228`; BUILDING; 0.05 m radius/extents, capsule height 0.1. Callback `:115–122`; Object inherits IEntity at `3_Game/Entities/Object.c:64` |
| sphere_query | `1_Core/proto/EnWorld.c:271`; 0.05 m radius, fixed 257-entity buffer, fmask -1. Legacy declaration has no mask semantics or vanilla call sites: experimental all-bits mask |
| trace_move | Same file `:254`, params `:218–226`, ENTS flag `:179`; straight downward line, null callback. Legacy declaration has no vanilla call sites: experimental |

Other exposed ways require information unavailable from class + origin:
`CGame.GetObjectByNetworkId` (`3_Game/Global/Game.c:356`) needs network IDs;
`FindEntity` (`2_GameLib/gameLib.c:119`) and `FindEntityByName/ID`
(`1_Core/proto/EnWorld.c:23–24`) need entity names/IDs, not class names.
`TraceLineToEntity` (`:214`) already requires the entity.
`GeometryOverlapBullet`, `EntityOverlapBullet`, `EntityOverlapSingleBullet`
(`3_Game/Global/DayZPhysics.c:216–220`) need a geometry/entity handle; no additional
class/origin resolver. Active entity enumeration (`1_Core/proto/EnWorld.c:27–29`)
is a broad scan of simulated entities and is excluded. RaycastRVExt (`DayZPhysics.c:202`)
is commented out and must not be called. No direct static class+origin lookup was
found in the inspected Game, World, EnWorld, entity and physics interfaces.

Supporting references: timing `1_Core/proto/EnSystem.c:106` (raw CPU ticks);
server/update `3_Game/Global/Game.c:1120`, `5_Mission/mission/missionBase.c:85`;
init `5_Mission/mission/missionServer.c:85`; position/type
`3_Game/Entities/Object.c:287`, `:467`; vector distance
`1_Core/proto/EnConvert.c:210`; identity transform `1_Core/proto/EnMath3D.c:256`.
Casts/arrays/sets: `1_Core/proto/EnScript.c:94`, `:380`, `:399`, `:407`,
`:743`, `:750`, `:758`; printing `1_Core/proto/EnDebug.c:96`; numeric/boolean
strings `1_Core/proto/EnConvert.c:3`, `:30`, `:115`.

## Lead commands

First validate without staging or Windows interop:

```sh
python3 -B -m tools.setup.interior_resolve_probe stage --tag resolve-all-01 --dry-run
```

Stage a fresh vanilla DayZDiag runtime using `diag_session.make_plan/stage` and the
existing diagnostic-mission instrumentation. HC gameplay addons are omitted so
their schedulers cannot pre-touch the buildings. This deliberately avoids the
retail probe launcher's fixed allowlist; it does not alter shared launcher files.

```sh
python3 -B -m tools.setup.interior_resolve_probe stage --tag resolve-all-01
```

Lead only, launch the staged mission with the existing `diag_session` runner
(one server and one client). This checks idle state and payload hash first:

```sh
python3 -B - <<'PY'
from tools.setup import interior_resolve_probe as probe
from tools.setup import diag_session as ds
from tools.release.host_lock import host_lock
with host_lock('diag_session'):
    plan = probe.staged_plan('resolve-all-01')
    result = ds.winproc.run('powershell', [plan.launch_script()], attempts=1, timeout=240)
    if result.returncode:
        raise SystemExit('Launch failed; preserve runtime; do not retry automatically.')
PY
```

After `[HC ResolveProbe] summary`, stop both processes normally. Choose the server
RPT explicitly; never concatenate runs. Ingest refuses incomplete, reordered,
duplicate, mixed-token or malformed probe measurements and existing output:

```sh
python3 -B -m tools.setup.interior_resolve_probe ingest \
  --rpt /mnt/d/HollowCountryLocal/diag-resolve-all-01/profiles/server/SELECTED_SERVER.RPT \
  --plan /mnt/d/HollowCountryLocal/diag-resolve-all-01/interior-resolve-probe.json \
  --out /tmp/interior-resolve-all-01.json --ticks-per-ms 10000
```

For cold comparisons repeat the stage/run/ingest sequence with a **fresh tag and
process** for each `--api NAME` from the table. Example:
`stage --tag resolve-ray-01 --api ray_geom`. Use that tag in the launch snippet and
ingest paths. This is necessary because APIs later in an all-API run inherit
warming. API order rotates by target in the all-API run; `order=0` identifies first
probe contact, not guaranteed engine-cold geometry. OS/engine caches, geometry shared by instances of one class, and the one
client may still warm geometry. Repeat fresh-process runs in reverse API order to
check that confound; no client movement/teleport or broad warmup scan is added.

## Interpretation and limits

Each parseable measurement logs run token, target index/class, API, order, pair
(0 first / 1 repeat), raw ticks, found and cap status, followed by a summary count.
After a 60-second settle delay, exactly one call runs per update. Default runtime
is 60 seconds plus 1,140 server frames. Filtering is bounded to 256 results per
container; overflows refuse a found result. Native calls themselves cannot be
preempted; this is a disposable cost experiment, not a production budget fix.

Queries/overlaps use catalog origin. Rays use the first measured room anchor,
or box center when no rooms exist, transformed by catalog yaw, from 60 m above
to 30 m below. A box center is only a footprint candidate: an irregular/hollow
building, roof hole or nearer collider can yield a miss. Found requires exactly
one distinct Object with exact class and origin within 0.75 m, matching HCFilter's
origin tolerance; proxy parents are checked. This does not validate tilt, doors,
prop placement or multiplayer behaviour.

JSON preserves all raw rows and per-class/API first_ms and repeat_ms arrays,
per-pair found arrays, aggregate found, and first_touch_ms (only order 0). The
10,000 ticks/ms default is the owner's host observation, not an engine guarantee;
override it for another host. Timing excludes allocation/filter/logging and thus
cannot by itself prove the complete tick meets R2. Bullet overlap callback work
is included in its native call's time. Recommendation is conservative: every
sample must resolve within 20 ms before an API is named as a candidate. No
recommendation accepts a gameplay change. Repeated expensive calls support the
geometry-cost hypothesis; a first-contact-only spike across APIs supports cold
loading. Neither conclusion is established until the lead obtains native logs.
