# V1 groups and map source implementation — #37 / #31

Status: source and offline behavior implemented. Native compilation, rendered UI,
normal PBO/server acceptance, multiplayer privacy and production enablement remain
**PENDING**. No DayZ, Wine, PowerShell, client connection, deployment, publication,
commit, staging or other git metadata mutation was performed.

## Inputs and scope

Read AGENTS.md, README “Travel together”, issue #37 (via `gh issue view 37 --json
title,body` after the default view hit GitHub's classic-project deprecation),
MODULE_STATUS's groups row, the runtime implementation contract, all group sources,
layouts and tests, and the Events client/public DTO. The two requested private
specification files (`docs/SPECIFICATION.md` and
`docs/specs/001-survival-overhaul/spec.md`) are absent from this checkout and were
not found in the searched local locations. They were not recreated or treated as
accepted evidence. The active user's complete-v1 task contract is the design input.

Applied the Banso CLI skill's dispatched-worker guidance. No lifecycle, dispatch,
repository or git-write commands were run. The task specification, implementation
plan and completion trace are recorded below because docs and orchestrator state
are outside this writer's scope.

## Specification / plan / task trace

| Task / acceptance behavior | Implementation | Acceptance status |
| --- | --- | --- |
| Owner/officer/member, bounded authenticated permissions | Additive persisted Officers list; operation 13 SET_ROLE; server rules and map roster/buttons | Authored; synthetic permission and journal checks pass; native migration pending |
| Navigation grid and own coordinates | Clipped 1 km canvas grid requires a carried map; coordinates also require a non-ruined, turned-on GPS | Authored; native inventory/coordinate/rendering checks pending |
| Discovery without unexplored points | Server-only catalog; proximity sampled from live server player positions; persisted per-account visits; optional current-group union | Authored; synthetic radius/cap/revocation/scheduling/journal checks pass; native observation pending |
| Known mission layer | Fresh Events public rows displayed beside the map; expired/inactive rows excluded | Authored; synthetic freshness and public-row checks pass; no spatial event hook exists |
| LOS and powered matching handheld radio rules | Server filters each teammate position before serialization; current head-bone view ray; global ray budget; owned inventory and working PersonalRadio frequency intersection | Authored; synthetic filtering/equipment/budget/obstruction checks pass; two-client acceptance pending |
| Scale, colour-safe differentiation and rebinding guidance | Independent icon and label scale; blue/orange/yellow with text prefixes and white labels on dark backgrounds; native map input retained | Authored; native layouts, font sizing, input and accessibility checks pending |
| Existing rate, TTL, session/replay, stale and membership rules | Existing service/client/journal flow retained; new role changes advance membership epoch; discoveries use existing commit quota/failure handling | Existing and new offline checks pass; actual RPC and restart behavior pending |

Implementation order: failing behavior first; extend additive DTOs/rules; wire the
native server adapters and bounded discovery transaction; add map overlays and
role controls; extend opt-in policy fixture; run group/full/BDD checks and static
source review. No unperformed engine experiment is marked accepted.

## Files

Existing sources changed:

- `mods/HollowCountry/scripts/3_Game/Groups/HCGroupData.c`
- `mods/HollowCountry/scripts/3_Game/Groups/HCGroupProtocol.c`
- `mods/HollowCountry/scripts/4_World/Groups/HCGroupRules.c`
- `mods/HollowCountry/scripts/4_World/Groups/HCGroupService.c`
- `mods/HollowCountry/scripts/4_World/Groups/HCGroupNativeChecks.c`
- `mods/HollowCountry/scripts/5_Mission/Groups/HCGroupClient.c`
- `mods/HollowCountry/scripts/5_Mission/Groups/HCGroupMapMenu.c`
- `mods/HollowCountry/scripts/5_Mission/Groups/HCGroupWorldIcons.c`
- `mods/HollowCountry/gui/layouts/hc_group_map.layout`
- `mods/HollowCountry/gui/layouts/hc_group_icon.layout`

New sources:

- `mods/HollowCountry/scripts/4_World/Groups/HCGroupVisibility.c`
- `mods/HollowCountry/scripts/4_World/Groups/HCGroupPlaces.c`
- `mods/HollowCountry/scripts/5_Mission/Groups/HCGroupMapLayers.c`

Tests changed: `tests/unit/test_group_server.py`, `test_group_persistence.py`,
`test_group_native_checks.py`, `test_group_ui.py`; new
`tests/unit/test_v1_groups.py`. The group-server `load_tests` hook includes the new
V1 behaviors in the stable existing groups BDD binding. `tools/validate/bdd.py`
ends unchanged: changing its filename pattern conflicted with the repository's
pinned-binding test, so coverage is extended through unittest's standard hook.
Full discovery consequently executes the V1 suite both directly and through the
existing group-server suite; these are repeated offline checks, not independent
validation.

No core/settings/config/input/package/README/docs/Events files changed. No game
assets or vanilla source were copied into the worktree. The accompanying evidence
files contain authored synthetic test output and API locations only.

## Permissions and migration

| Operation | Owner | Officer | Member |
| --- | --- | --- | --- |
| Invite | Yes | Yes | No |
| Kick | Other members/officers | Ordinary members only | No |
| Create marker | Yes | Yes | Yes |
| Edit/delete marker and note | Any | Any | Own only |
| Rename | Yes | Yes | No |
| Set officer/member role | Yes | No | No |
| Transfer ownership/disband | Yes | No | No |
| Leave | After transfer if others remain | Yes | Yes |

Roles are account-owned. Owner remains `OwnerId`; officers are a unique subset of
members. Existing records lacking `Officers` initialize it empty, preserving the
existing owner and giving other accounts ordinary membership. New `Explorers`
initializes empty. Wire version 2 and durable/receipt version 1 remain additive;
intent/image/commit receipts still verify the original serialized bytes, and the
next successful journal write includes new fields. No old image is rewritten at
startup and no fallback to an older ACL is introduced. Explicit null/invalid lists
still fail validation. Native JSON field-initializer and receipt behavior must be
checked on an actual old journal before accepting migration. Use matching rebuilt
client/server PBOs; mixed addon versions have not been qualified.

Promotion/demotion is owner-only and revision checked. Demotion, role change,
transfer, kick and leave remove stale officer entries as appropriate; role changes
advance the membership epoch and cancel outstanding group invitations. Officer
invitations validate the inviter's current rank. Discovery sharing is computed
from current membership and never copied into another account's durable visits.

## Groups-owned operator JSON

Existing bounded loader: `$profile:HollowCountry/Groups/settings.json`, maximum
8,192 bytes, SchemaVersion 1. Missing additive keys use these defaults; existing
explicit preferences are retained. No HCSettings additions are needed.

| Key | Default | Valid values / behavior |
| --- | --- | --- |
| NavigationLayer | true | Boolean; custom grid/readout on map |
| DiscoveryLayer | true | Boolean; server observation and visited overlays |
| MissionLayer | true | Boolean; known-events list |
| ShareDiscovery | false | Boolean; current-group visited union when true |
| MaxLOSRaysPerTick | 32 | Integer 1–256; shared across tick and RPC-triggered snapshots |
| MaxDiscoveries | 64 | Integer 1–256; per account and maximum transmitted unique union |
| MaxExplorers | 256 | Integer 1–512; persistent account records; no automatic eviction |
| DiscoveryIntervalSeconds | 5.0 | 5–300 seconds; up to six peers per pass, round robin beyond six |
| IconScale | 1.0 | 0.75–2.0; world and custom map icons |
| LabelScale | 1.0 | 0.75–2.0; world/map labels and own navigation readout |
| RequireLOS | false (existing) | Now supported; direct head-to-head native view ray must pass |
| RequireRadio | false (existing) | Now supported; both carry a working, non-ruined PersonalRadio with a shared actual tuned frequency |
| RequireGPS | false (existing) | Existing native MapNavigationBehaviour GPS/ALL gate on both teammate position endpoints remains |

Own-coordinate readout always requires both map and turned-on GPS, even when
RequireGPS is false. Native GPSReceiver's IsTurnedOn delegates to its working
energy manager. The custom grid needs a map but no GPS. The native printed map
remains a normal map, including its own printed place names; the visited overlay
represents observed visits rather than pretending to hide printed cartography.

Optional catalog: `$profile:HollowCountry/Groups/places.json`, bounded read of
65,536 bytes, shape:

```json
{"SchemaVersion":1,"Places":[{"Id":"operator-place-id","Name":"Place name","Position":[100,0,200],"Radius":100}]}
```

This is a schema example, not a supplied or qualified world location. At most 256
unique entries; IDs 1–128 characters, names 1–64; no newline/tab controls; radius
5–500 m; positions finite, within supported coordinate and current-world bounds.
Missing catalog reads native `CfgWorlds <world> Names`: at most 512 children / 256
valid named points, 100 m default radius. No native data file is copied or written.
Malformed/oversized supplied catalogs or over-budget native catalogs refuse
startup with a diagnostic. An empty native Names collection gives no POIs; review
the actual world's catalog before accepting default coverage. Operators can use
an explicit empty catalog or disable DiscoveryLayer. Use stable IDs; do not
repurpose an existing place ID for a new location.

Visits store the observed place name/position/radius, so a later catalog edit does
not turn an old visit into knowledge of an unvisited new position. Discovery scans
at most 6 × 256 distance candidates per pass and commits all additions once.
Per-account/global/store limits stop additions rather than evicting known history;
a store quota refusal leaves the prior committed image authoritative. Sampling
records observed proximity, not every possible brief crossing between samples.

Inventory scans reject inventories above 512 native entries and retain up to eight
unique working handheld frequencies. LOS quota exhaustion removes the position;
no positive visibility result is cached. Default 32 rays accommodates the 30
ordered teammate pairs in a six-player roster in one position batch. Full/SYNC
snapshots also consume that quota, so busy periods may temporarily suppress icons.
These bounds are provisional until measured at the target load.

## Actual RED / GREEN records

All fixtures are explicitly synthetic. They execute authored method bodies via
restricted syntax/native adapters; they do not compile Enforce or prove engine,
network, UI, persistence durability or performance behavior.

- Initial RED: [RED.txt](RED.txt): 6 tests, 2 failures / 4 errors for missing role,
  discovery and adapter implementations; officer assignment returned INVALID and
  LOS/radio settings were rejected. The missing-method/file errors are expected
  absence failures after fixing the test harness setup.
- Client integration RED: [RED-integration.txt](RED-integration.txt): operation 13
  was refused by the existing client operation limit. Extended it to 13; original
  role payload remains frozen across retry.
- Policy-fixture RED: [RED-native-fixture.txt](RED-native-fixture.txt): operation 13
  missing from successful cases. Added promotion, officer invitation, unauthorized
  promotion rejection and demotion to the opt-in fixture.
- LOS RED: [RED-head-los.txt](RED-head-los.txt): expected current head heights
  0.3/1.6, observed fixed 1.5/1.5. Now reads current native head bones and rejects
  unavailable bones before raycasting.
- Discovery RED: [RED-discovery-batch.txt](RED-discovery-batch.txt): expected six
  observed accounts in one transaction, observed one. Now samples a batch of six.
- GPS RED: [RED-gps-power.txt](RED-gps-power.txt): switched-off GPS incorrectly
  counted. Now calls native ItemGPS.IsTurnedOn.
- [RED-migration.txt](RED-migration.txt) exposed a limitation of the synthetic JSON
  adapter: nested DTO defaults were not represented. The adapter now explicitly
  initializes nested DTOs; this does **not** establish native migration behavior.
- Focused GREEN command:
  `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_v1_groups.py -v`:
  **13 tests, OK**, [GREEN-focused.txt](GREEN-focused.txt).
- Full final command:
  `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v`:
  **2,515 tests, OK (1 skipped)**; [GREEN-full.txt](GREEN-full.txt).
- BDD final command: `python3 -B -m tools.validate.bdd`:
  **61 scenarios, 1,311 tests, OK (1 skipped)**; [GREEN-bdd.txt](GREEN-bdd.txt). Runtime acceptance is NOT EXECUTED.
- Static review: [LINT.txt](LINT.txt), no group Enforce shape issues. Existing
  FindFile's `/*` glob is excluded from the comment-marker heuristic. Repository
  syntax/identifier tests also run in full discovery. `git diff --check` is clean.

Earlier broad checks caught the pinned BDD pattern conflict and an in-flight
synthetic adapter mismatch while the final GPS guard was being authored. Final
verification is rerun after freezing source and tests; only those final logs are
GREEN evidence.

## Native API evidence and Events boundary

[API-EVIDENCE.md](API-EVIDENCE.md) cites the exact pinned installed cache files and
line numbers for the inventory, ItemMap/ItemGPS/ItemCompass, handheld Transmitter,
energy manager, PlayerBase/head bones, raycast, MapWidget, MapMenu, UIScriptedMenu,
widget, input, file/JSON, collection and numeric APIs inspected/used. These source
locations are interface evidence, not observed results.

The mission layer consumes `HCEventClient.Get`, `Fresh`, `GetView` and
`SetBrowsing`; it never reads server mission sites, objectives, participant
positions or the private event director. Public `HCEventPublicRow` has no
coordinates. Therefore spatial mission pins are an integration gap, not invented
coordinates. If pins are required, Events owners need to add an optional
recipient-filtered `HasKnownPosition` / `KnownPosition` public field (or an equally
narrow known-location accessor), server-populated only after knowledge admission,
with freshness/cancellation/revocation tests. Groups can then consume that public
hook. No Events edits were made. The existing Events browse cadence/rate controls
are reused while the group map is open.

## In-game checks on the local server, one client

These are pending manual checks, not completed experiments:

1. Compile the final addon in DayZDiag, then build/load matching normal PBOs. Check
   every changed layout loads; no unsupported widget class or script API error.
2. Fresh profile, existing settings and explicit disables: verify the bounded
   settings file, native Names/default catalog and optional supplied catalog.
   Invalid/oversized input must refuse startup without damaging state.
3. Open M and a rebound native map action; pan, wheel zoom, place/edit/reload a
   marker and 512-character note; ensure typing M in edits does not close it.
   Verify map and other native/scripted menus retain their input behavior.
4. Add/remove map and GPS, switch GPS off and drain/remove its battery. Grid only
   with map; own coordinates only with map plus working GPS. Check coordinates
   and grid registration against the actual world and native map projection.
5. Visit a reviewed catalog location inside/outside its radius, wait a scan, and
   restart/reconnect. Verify only observed entries persist; unvisited entries
   never appear in the snapshot. Test invalid IDs and quota refusal on a copied
   local profile. Death/respawn must clear transient positions without destroying
   account visits.
6. Load a copied old journal with no new fields; confirm unchanged owner/member
   ACL, empty officers/visits, verified highest-revision recovery and next-write
   migration. Test torn/corrupt latest triples only on disposable copies.
7. Exercise scale 0.75/1/2 and small/large resolutions. Check text contrast,
   clipping, marker overlap, prefixes and control usability. The scale keys cover
   the new pins/readout; existing native editor/list/button sizing stays native.
8. Run the opt-in HCGroupNativeChecks synthetic policy fixture if the local
   diagnostic harness exposes it; its completion remains policy evidence only.
   Verify the known-events list and its disabled/stale presentation with whatever
   event knowledge the local server legitimately provides.

## Two-client-only acceptance, deferred

- Officer invitation/rename/kick permissions, owner-only role changes and transfer,
  concurrent marker edit conflicts, role demotion and stale invitation revocation.
- World/map positions agree; wall, door, foliage, prone/crouched and head-bone LOS
  cases. Inspect outgoing server DTOs as well as rendered icons. Test quota
  exhaustion, SYNC/request bursts and recovery on the next budget interval.
- Powered matching handheld channel, mismatched frequencies, battery exhaustion,
  switch-off, transfer/drop, multiple radios, ruined devices and base radios.
  Forbidden coordinates must never enter the recipient's RPC.
- Leave/kick/disband, death/unconsciousness, disconnect/reconnect, late full/position
  packets and server restart revoke transient teammate information correctly.
- Discovery sharing off/on: a second account gains only current group visits and
  loses them after leave/kick; shared entries are not persisted as its own visits.
- Events knowledge remains recipient-specific; no new event knowledge is created
  by opening the map. Event cancellation and freshness clear the list.
- Combined traffic, UI cost and ray/inventory/scan budgets with the intended 3–6
  players, plus input/mod compatibility and normal signed addon loading.

## Remaining integration / acceptance gaps

No HCSettings, input XML, module registry, config.cpp or PBO-tool edits are required
for these groups-owned additions. Core should rebuild/package both endpoints,
review README/MODULE_STATUS wording (roles/layers and LOS/radio now authored,
validation still pending), and retain issue #37/#31 runtime work. This writer did
not change those owned files or close either issue. Spatial event pins need the
public known-position hook described above. Default native POI coverage and all
rendering/network/durability/performance claims remain unqualified. Independent
review and the required DayZDiag/normal-server/two-client checks remain open.
