# HC-50: permitted white-terrain feasibility (#150)

Result: **unresolved; white terrain remains required and open**. No permitted,
version-pinned Chernarus winter dependency is identified in the available evidence.
No terrain assets, materials, textures or third-party config values were read,
copied or repacked. No dependency was acquired and no network request was made.
Runtime acceptance and production enablement remain pending/off respectively.

The machine-readable option record is
[hollow-country-winter-terrain.json](../config/hollow-country-winter-terrain.json).
It is research data, **not a runtime setting, enable switch or qualification
receipt**. Missing author, licence, version and coverage fields are explicitly
null/UNKNOWN; these are blockers, not accepted omissions. Editing the record
cannot make `HCWinterTerrainAdmission` report `supported`.

## Requirement and trace

The binding owner decision on 2026-11-18 requires roughly four weeks of accumulated
running-server time, roughly a week per phase, native falling snow in winter,
and a white-terrain feasibility outcome. Downtime pauses HC-6's clock. Falling
snow and colour grading do not satisfy white terrain. No seasonal cold,
temperature/clothing penalty or game-calendar manipulation is authorized.

Trace: supplied consolidated coverage task **HC-50 / #150**, depending on HC-6,
HC-60 and the landed Wave 3 interfaces; installer handoff HC-62; canonical
spec/plan/task reconciliation HC-11. `docs/OUTSTANDING.md` retains #150 and HC-50.
The required `docs/SPECIFICATION.md` and
`docs/specs/001-survival-overhaul/spec.md` are absent in this worktree. The copies
in the lead checkout were read only as design input (FR-011/012 and NFR-006);
active-session decisions supersede their older load/stamina/publication wording.
No canonical spec, plan or task file was changed outside worker ownership.

## Inspected capability evidence

Native citations below are relative to the installed read-only root
`~/.cache/hollow-country/native-scripts/scripts-1.30.164289/`. They establish
declarations and source behavior, not successful game observations.

| Surface inspected | Exact evidence and implication |
| --- | --- |
| Native snowfall | `3_Game/Weather.c:192` exposes `GetSnowfall`; `:306-321` describes overcast thresholds for the falling-snow phenomenon. No terrain accumulation/replacement is established by these methods. |
| Local snowflakes | `3_Game/Weather.c:323-328` explicitly says snowflake scale is unsynchronized; `3_Game/WorldData.c:195-198` updates that local effect. HC-50 adds no weather or client writer. |
| World/calendar | `3_Game/Global/World.c` includes dates, view distances, lighting, pathgraph, postprocess and grass-flattening surfaces; no live terrain/material replacement setter was found in the class. Calendar changes are disallowed regardless. |
| World material access | `3_Game/Global/World.c:137-162` illustrates a postprocess material and camera effect. A material handle is not evidence of world terrain ownership or safe replacement. |
| Object material/texture | `3_Game/Entities/EntityAI.c:2881-2884` declares setters on entities. No demonstrated mapping from Chernarus terrain/satellite layers, foliage or distant LOD to those entity selections exists. No traversal or texture-swapping controller is authored. |
| Surface/config inspection | `3_Game/Global/Game.c:449-611` exposes config readers; `:1169-1188` provides surface queries. `3_Game/SurfaceInfo.c:1-79` exposes surface properties/getters. Reading these does not expose a terrain setter; `GetByName` can create a handle even for an invalid name. |
| Existing Chernarus owner | `4_World/Classes/Worlds/ChernarusPlus.c` defines `ChernarusPlusData`. HC's `HCWeatherDaysModule.c` already owns the weather/HC-6 lifecycle. `mods/HollowCountry/config.cpp` registers the existing 4_World source directory and selects no winter addon. No new requiredAddon can be justified. |

This is a bounded negative finding: **`DYNAMIC_TERRAIN_API_UNPROVEN`**, not a claim
that no engine or permitted asset-side mechanism could ever exist. An authored
config patch cannot supply missing permitted terrain assets. Official installed
script/config interfaces were inspected; vanilla world asset/material archives
were not dumped and no third-party package values were inspected.

HC-6 reuse is read only: `HCVisualSeasons.HCActive()` supplies effective clock
admission; only an active clock's `HCSeason()` is read. Its existing phase length
is 604800 seconds. `HCVisualSeasonIO.HCLoadState/HCValid` require
`chernarusplus`, including persisted world identity. This rules out treating a
different winter world as a transparent replacement without further design.

HC-60's checked-in `winter-terrain-unidentified` record has no Workshop ID,
author/source, rights or exact version. Its refusal is
`NO_VERIFIED_TERRAIN_SOURCE_OR_RIGHTS`. Existing provenance entries identify
Expansion AI/Navigation, CF/COT, animal and vehicle dependencies;
none establishes a permitted white-terrain option. This is a compatibility input,
not proof of the actual current launch set or its success. Only public Workshop
page text may establish third-party author/licence details in a later research
pass. Availability, subscriptions and a familiar product name do not establish
permission. No named Workshop product is recommended here.

## Compared options

| Option | Decision | Coverage / restart boundary |
| --- | --- | --- |
| Native weather and existing colour controls | Continue existing owners; insufficient for this requirement | Snowfall does not prove white ground, satellite texture or foliage coverage. No HC-50 terrain change. |
| Live scripted material/texture replacement | Refused: `DYNAMIC_TERRAIN_API_UNPROVEN` | No verified terrain setter, replication, LOD/material ownership or safe reversal. No speculative controller. |
| Permitted seasonal dependency over the same Chernarus world | Preferred **research track**, unresolved | Public author/licence source, exact version and coverage unknown. Future trials require stopped server, matching server/client dependencies and restarts on entry, exit and rollback. |
| Separate winter map/mission | Unresolved, not a drop-in selection | Identity, storage, CE, locality content, situations and route compatibility unknown. HC-6 explicitly requires Chernarus. No mission switch, hive wipe or state migration is implemented. |

All options have explicit author/source, licence/source, exact version, terrain
coverage, restart policy and unknowns in the JSON. The two research slots are
categories, not identified products. Authored options = 4; identified Workshop
candidates = 0; admitted dependencies = 0; observed coverage = unknown.

## Supported source implementation

[HCWinterTerrainAdmission.c](../mods/HollowCountry/scripts/4_World/Weather/HCWinterTerrainAdmission.c)
implements a passive, bounded server receipt. It has no module registration,
tick, state file, scheduler, scan, player query, RPC, weather control or asset
mutation. It never returns `supported`. Missing/inactive HC-6 refuses; an active
phase leaves terrain pending, always effectively off. `HCReport` is a client or
absent-game no-op. No new distances were added.

Proposed boot diagnostics **implemented in the helper, integration pending;
never observed in DayZ**:

```text
[HC Plan] HC-50 white_terrain=pending dependency=none boundary=stopped-server-restart season=winter reason=NO_VERIFIED_TERRAIN_SOURCE_OR_RIGHTS refusal=DYNAMIC_TERRAIN_API_UNPROVEN effective=off admitted=0 observed=unknown runtime=PENDING
[HC Plan] HC-50 white_terrain=refused dependency=none boundary=stopped-server-restart season=unavailable reason=HC6_NOT_ADMITTED refusal=DYNAMIC_TERRAIN_API_UNPROVEN effective=off admitted=0 observed=unknown runtime=PENDING
```

Missing HC-6 uses `reason=HC6_UNAVAILABLE`. The restart field is the required
policy for future dependency trials, not an observed working mechanism.
`season` describes the active clock, not installed terrain. The one boot receipt
is a startup snapshot; it must not be presented as a live phase/material status.

## Exact lead integration (worker did not make these edits)

1. In `mods/HollowCountry/scripts/4_World/Weather/HCWeatherDaysModule.c`, inside
   its existing `modded class ChernarusPlusData` link, add a public read-only
   getter next to the existing `m_HCVisualSeasons` declaration:

   ```c
   HCVisualSeasons HCWinterTerrainSeasons() { return m_HCVisualSeasons; }
   ```

2. In `mods/HollowCountry/scripts/4_World/Core/HCServer.c`, in `Start()` after
   the module-start loop and `m_Started = true;`, emit exactly one boot receipt:

   ```c
   Mission hcWinterMission = GetGame().GetMission();
   ChernarusPlusData hcWinterWorld = null;
   HCVisualSeasons hcWinterSeasons = null;
   if (hcWinterMission) { hcWinterWorld = ChernarusPlusData.Cast(hcWinterMission.GetWorldData()); }
   if (hcWinterWorld) { hcWinterSeasons = hcWinterWorld.HCWinterTerrainSeasons(); }
   HCWinterTerrainAdmission.HCReport(hcWinterSeasons);
   ```

   Existing inspected native seams: `3_Game/Global/Game.c:1093` GetMission,
   `3_Game/gameplay.c:742` Mission.GetWorldData,
   `1_Core/proto/EnScript.c:94` Cast. No later modded-link call is introduced:
   the getter belongs to the same weather-owner link as its clock field.
   A disabled/unavailable owner supplies null or inactive state; no clock is
   started merely to produce this diagnostic.

3. `mods/HollowCountry/config.cpp`: **no edits**, no requiredAddons or settings
   references: none is verified. `HCModule.c`: **no edits**, no module slot.
   No new `mission/` files; **no `MISSION_FILES` additions** are needed.
4. HC-62's serialized HC-1/25 content manifest integration should name
   `HC-50` and `config/hollow-country-winter-terrain.json`, compute its actual
   bytes/hash, retain authored options 4 / selected dependencies 0 / admitted 0 /
   observed unknown, and report off/pending. Do not infer a native success count
   from this record. No such shared registry was edited here.
5. `.gitignore` currently excludes this assigned report via `/docs/*`. Add the
   exact exception `!/docs/WINTER_TERRAIN_OPTIONS.md` so the orchestrator's
   commit includes it. The worker left `.gitignore` and git metadata untouched;
   the full report exists in this worktree even though ordinary status omits it.

## HC-62 dependency / restart handoff

`tools/package/optional_overlays.py:195-225` plans installed overlay source hashes;
`:465-486` verifies drift and writes before/after mission-file receipts; rollback
uses that existing backup protocol. It is **not** a terrain licence/version,
dependency-order or material-coverage attestation. No terrain runtime receipt
port exists; this worker does not invent one or read Workshop values to fill it.

After identifying a permitted candidate from public Workshop text, HC-62 must
reuse the package dependency/receipt mechanism and bind the exact candidate
identity/version/content hashes, dependency order, baseline launch arguments,
public keys and matched server/client set. No terrain files enter HC packages.
Source/profile/mission/PBO hashes and inspection evidence must refer to that same
set. Any future admission path needs an actually inspected receipt interface;
the static research JSON must never be sufficient to promote support.

Before changing the external test stack, stop the server and preserve the paired
native world/inventory storage plus HC journals, including HC-34 custody and
HC-6 `visual-seasons.json` and its verified recovery companions. Never reset
seasons, stories, locality coverage, CE stock or custody to obtain a different
appearance. Existing receipts restore authored configuration; uncertain world
state is quarantined for review, never automatically replayed/refunded. No new
atomic rename/fsync guarantee is claimed for the engine store.

For a future qualifying dependency, restart the stopped server and the connected client
with the matched winter set. On exit/rollback, stop and restore the recorded
baseline set on all participants, then restart. Do not hot-swap materials or
alter the game date. A restart-required dependency cannot automatically follow
every HC-6 boundary mid-session: clock and installed appearance can disagree
until the qualified operator restart. This remains an explicit feasibility and
operational gap, not a completed four-season terrain cycle. Do not add a second
season clock or pause the admitted HC-6 clock to hide that mismatch.

## Validation and remaining native acceptance

Offline checks cannot establish terrain feasibility, licensing, Enforce compilation or game behavior.
Standard-library JSON validation checks each option's attribution/licence source, exact version,
coverage, restart policy and unknowns, explicit nulls for unidentified dependencies, and consistency
with HC-60's refusal. These checks validate the authored record; they do not resolve its missing
evidence.

The lead must compile/boot the exact integrated source in DayZDiag, then test a
normal signed PBO server. Grep `[HC Plan] HC-50`, verify one startup receipt,
exercise the operator-off path, stop/restart, and require no script/CE errors.
Those checks qualify only the refusal path while no dependency is selected.

Future candidate acceptance remains pending: inspect white ground and satellite
transitions, close and distant LOD/materials, roads, foliage, buildings, coastline,
islands and the full settlement spread using at most one client, including
join/reconnect and successive viewpoints. Record any uncovered area; no
quiet-by-design or uninspected-region exemption. Verify surface footsteps/audio,
occlusion/visibility, infected/AI navigation, doors, vehicle traction, CE and
persistent story/stock/custody parity against the exact current Expansion and
optional dependency stack. Refuse unexpected seasonal cold/clothing changes.
Exercise restart **to and from** winter and rollback without data reset, log
source/PBO/mission/config/dependency hashes, then measure server and single-client cost; target-load budgets remain provisional. Existing
LOD and budgets remain owned by their original modules; benchmarks are provisional.
White terrain stays open until those observations exist.
