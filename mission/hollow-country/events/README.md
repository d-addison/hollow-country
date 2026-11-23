# Reviewed scenes (LC-T309, LC-T310; issues #93, #94, #120)

`HCScenesModule` self-registers and follows `EnableEncounters`. EXP-S3's verdict
is printed once and does not disable an enabled V2 preference. No core hook is
needed. The mission files are already in `tools/package/pbo.py`'s `MISSION_FILES`,
and the shared `HCObserverTransitionGate.CanTransition(vector pos, float far)`
interface is present in this checkout. Native compilation remains pending.

The original six kits remain: last stand, quarantine checkpoint, evacuation
point, supply drop remains, convoy wreck, and survivor distress camp. The #120
follow-up adds four variants (ten kits total):

| Kit ID | Empty static scenery |
| :--- | :--- |
| `supply-drop-opened` | Open container shell, three scattered metal crates and a pallet. |
| `convoy-roadside` | Military MTVR cargo-truck and UAZ wrecks beside the authored access strip, plus an empty crate. |
| `quarantine-cordon` | Barriers, tent, stop sign and two static hazard/body bags. |
| `survivor-cold-camp` | Small camo-net shelter, cold fireplace model, bed, chair and bag. |

`scene-provenance.json` records 22 installed vanilla classes, their resolved
models, actual P3D member presence and stock mapgroupproto presence or absence.
Checks used the existing read-only `tools.audit.pbo_config` reader directly on
installed vanilla PBOs, including inherited model resolution for spent casings.
No assets or vanilla files are included.
`Surveyed` remains false: source review does not establish safe native placement.

`scene-chains.json` contains four finite chains using the existing
`HCEventMission` format and INVESTIGATION family. It loads from
`$mission:hollow-country/events/scene-chains.json`; if that file is absent, the
same authored defaults are compiled into `HCSceneChains.Defaults()`. Invalid
existing content fails closed. When v1 Events is admitted, placed stages are
also offered through its normal optional investigation UI and journal. V2's
timed environmental director uses no fabricated player identities or progress.

The first two chains start when unobserved placement is possible; the third
starts after 36 real hours. `scene-relief-route` starts after 72 real hours at
the existing Kamenka anchor: `supply-drop-opened` → `quarantine-cordon` →
`survivor-cold-camp`. The first Kamenka chain now starts with `convoy-roadside`,
so all four additions are wired into the authored catalog. No new sites are
introduced. Any lease still owning a reused anchor, including closing/partial
cleanup, refuses a new placement until its handles are gone.

Stages last six real hours, expire independently
after twelve, and subsequent stages open six hours after safe cleanup. Downtime
counts. A missed deadline, failed placement, missing prop or failed director
operation cancels the whole chain. A completed stage can wait for safe cleanup
without becoming expired. At most two kits exist at once; work visits one chain
per ten seconds. Terminal chains are retained and never replayed or refilled.

Existing profile images keep their pinned catalog, including the previous
three-chain schedule and original convoy kit. The fourth chain and new convoy
variant enter fresh scene state only. This update never resets completed chains
or silently rewrites an ongoing stage; preserve existing profile state.

All creation and deletion use the shared observer gate at 500 m, including
partial placement cleanup and shutdown retries. Placement requires an exact
reviewed anchor, native building-door keepouts of 4 m plus each prop's footprint,
clearance from nearby building/wreck bounds, an 8 m authored access strip and
bounded terrain checks. Footprint radii and actual routes still need EXP-S3.
The native sphere query allocates its result before the 128-object refusal;
that bound is not an engine-side query limit or a measured performance budget.

No usable loot or containers are created or moved. The last-stage cache is empty
static scenery. Casings are the verified spent-cartridge model rendered as
static clutter. The open container shell and cold fireplace are also rendered
as static models only; neither their inventory classes nor FireplaceBase hooks
run. Hazard/body bags are vanilla HouseNoDestruct props, never player corpses.
Nonzero rewards remain blocked by v1's COMPLETE rule. Any future
real scene loot must move through the existing qualified journal transfer path;
there is no creation fallback, direct inventory move or grant/refill loop here.

Durable state and the pinned authoring plan live at
`$profile:HollowCountry/scene-chains.json`. Saves verify a new `.tmp` intent, back
up the current image to `.bak`, install and read back the new image, then remove
the intent. An existing intent, corrupt image, clock rollback, or missing image
with a surviving backup refuses admission; neither backup nor defaults silently
replace state. Preserve those files for explicit offline operator recovery.
The installed script APIs expose CopyFile/DeleteFile but no rename; this is
fail-closed transactional admission, **not filesystem-atomic rename or fsync**.
That exact persistence requirement remains a gap for a native/platform solution.

Server log patterns:

```text
[HollowCountry] V2 admission feature=Scenes preference=on gate=EXP-S3 qualified=0 result=admitted unverified: EXP-S3 has no recorded native verdict
[HollowCountry] V2 scenes active=<n> chains=<n> placed=<n> refused=<n>
[HollowCountry] V2 scene placed id=<chain> stage=<index> kit=<kind> layout=<0-7>
[HollowCountry] V2 scene stage complete id=<chain> stage=<index>
[HollowCountry] V2 scene chain cancelled id=<chain> stage=<index> reason=<reason>
[HollowCountry] V2 scenes persistence refused; preserve scene-chains.json/.tmp/.bak for recovery
```

The summary is printed at startup and at most once per 600 seconds. Counters are
process-local; `placed` counts created props, including partial kits. Stages are
zero-based. There is no new client script or client log line; scene replication
and the optional existing event UI require single-client checking.

The single offline smoke retains expiry/cancellation and door keepout coverage,
checks each new kit against the verified class/model records, refuses a
synthetic door underneath every new prop, and exercises the reused-site guard
with a closing lease. The existing translator is unchanged.
Native compile, DayZDiag, normal PBO/server behavior, single-client visibility,
collision, doors/routes, restart persistence and target-load budgets remain
pending. Nothing in the offline tests establishes observed DayZ behavior.
