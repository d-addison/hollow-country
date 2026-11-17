# Cross-model review: Hollow Country groups/map v1 (#37, #31)

Reviewer: Sonnet 5.5. Subject: commit 932cb96 on base eb9ceb8 (`git diff eb9ceb8 932cb96 -- mods tests tools gui`).
Review only. No tracked file edited, no git state change. Mutants ran in the scratch copy `mut/` only.

## Verdict: FIX-THEN-MERGE

No P0 or P1 found. The server-side privacy and role design is sound. The mutation run shows
half of the new guards are not pinned by any test, and there are two server perf/starvation issues
worth fixing before the local acceptance run. Runtime behaviour is unobserved and stays pending.

## Test results

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit`: Ran 2515 tests, OK (skipped=1)
(full output in unit.txt; the `| tail -3` view shows trailing tool-noise lines, the real result is the
"Ran 2515 tests ... OK (skipped=1)" line). Offline tests are a Python translation of the .c rules, not an
engine compile, so they prove nothing about DayZ behaviour.

## Findings

### P2-1 LOS ray budget starves the later peers; default MaxMembers=8 exceeds default MaxLOSRaysPerTick=32
- HCGroupService.c:374-375 (budget), :497 (Broadcast), :550-553 (POSITIONS loop), :503 (reset); HCGroupData.c:15.
- Scenario: RequireLOS on. One group of 8 needs 8 x 7 = 56 rays per snapshot round, one ray per (source, recipient)
  pair. Budget is 32 per Tick and shared by every group and by Broadcast + POSITIONS in the same Tick. The peer
  iteration order never changes, so the last peers in `m_Peers` lose all teammate positions every cycle
  (fail closed, no leak, but permanent starvation, not rotation). A Tick that runs a discovery Broadcast (FULL, up to
  30 rays for 6 peers) followed by the POSITIONS loop (30 more) also blanks the second pass for 6 players.
  Two groups of 4 (24 rays) fit; one group of 6 plus a discovery commit does not.
- Fix: carry a per-pair cached verdict (source, recipient, expiry about 1 s, keyed on both uids) so a pair
  is raycast at most once per second; rotate the starting peer index each Tick; skip the POSITIONS loop for the Tick in which
  Broadcast already sent FULL frames (they carry positions); raise the default to at least MaxMembers x (MaxMembers - 1) or
  document that RequireLOS caps useful group size at 5. Add a test with 8 members asserting every member eventually gets rays.

### P2-2 Discover clones and reserialises the entire store every 5 s even when nothing can change
- HCGroupService.c:386-387 (Clone before any distance test), :398-401, HCGroupRules.c:657 (RecordVisit validates before the distance test).
- Scenario: 6 peers x 256 catalog places = 1536 RecordVisit calls per pass; each does TextValid on uid (3 Contains + Trim), PlaceValid
  (two more TextValid + range checks) and only then the distance test. Clone is a full MakeData + LoadData round trip of
  a state of up to 262144 bytes. Both run unconditionally on the game thread every DiscoveryIntervalSeconds even when no one is near a POI.
  Expected cost is a periodic multi-ms server hitch (unmeasured; benchmark budgets stay provisional).
  If the store is at MaxStoreBytes, Commit returns LIMIT every pass and the whole cost repeats forever with no backoff.
- Fix: pre-validate the catalog once at Load (already done), do the squared-distance reject first, collect hits into a
  small list, and Clone only when the list is non-empty and not already recorded. On LIMIT, back off (for example skip Discover for 60 s).

### P2-3 Surviving mutants: role and privacy guards with no behavioural test (mutation score 31 / 62 killed)
Survivors that are real, non-equivalent gaps:
- Permission matrix: M03 (officer may TRANSFER) and M04 (officer may DISBAND) survived. HCGroupRules.c:458 is the only guard
  and `test_officer_matrix_and_owner_only_role_assignment` never exercises those two ops as an officer.
- Stale officer cleanup: M05 (kick, HCGroupRules.c:~488) and M06 (leave, :442) survived. A kicked officer who is re-invited could
  keep officer rights if cleanup regressed (StateValid would instead Stop() the whole module; neither outcome is tested).
- Journal validation: M13 (officer not a member), M14 (owner listed as officer), M15 (invite from a non-officer inviter) survived:
  HCGroupRules.c:223 and the invite check in StateValid. A tampered or regressed journal loads without a test failing.
- Discovery privacy and bounds: M21 (ShareDiscovery ignores group membership, HCGroupRules.c:712) survived. It would leak other groups'
  discoveries to the caller. M18 (MaxExplorers, :677), M19 (DiscoveryLayer off in RecordVisit, :657), M23 (KnownPlaces unbounded, :720),
  M24 (layer off still lists, :704) also survived.
- Server wiring: M30 (unconscious peers still visible, HCGroupService.c:363), M31 (ray budget never reset, :503), M41 and M42
  (places only on FULL to a live peer, :486), M43 (Discover alive/unconscious check, :396), M44 (examined bound of 6, :390),
  M61 (roster roles never set, :464), M62 (startup refusal when the place catalog fails to load) survived.
- Equipment: M39 (inventory over-budget fails closed, HCGroupVisibility.c:13/16) and M40 (base/static transmitter accepted, :27) survived.
- Client: M45 (expired missions listed, HCGroupMapLayers.c:117), M49 (own coordinates without a GPS, :87), M50 (NavigationLayer setting
  ignored, :65), M51 and M52 (client accepts unbounded Places or a bad Role, HCGroupClient.c:271, :306), M56-M58 (PlaceValid radius,
  ExplorersValid MaxExplorers and duplicate visits) survived.
- Fix: add one failing-first test per survivor above. Highest value first: M21, M03/M04, M05/M06, M13-M15, M31, M30, M43.
  Equivalent or near-equivalent and not required: M00 (baseline) and M12 (SET_ROLE with Role=2 silently demotes instead of INVALID; harmless).

### P2-4 Same-vehicle teammates and bone pose are unobserved; LOS may hide teammates riding together
- HCGroupVisibility.c:49-65.
- Scenario: `RaycastRV(..., ignore=source, ObjIntersectView, NEARESTCONTACT)` ignores only the source. If source and recipient share a car or
  heli, the nearest view-geometry contact can be the vehicle itself, so `hits.Get(0) != recipient` and both vanish from each other (fails closed, no leak).
  Whether a dedicated server evaluates `GetBonePositionWS("Head")` for remote players with a current pose is also unobserved.
- Fix: also pass the source's parent vehicle (`source.GetParent()`) to be ignored, or treat players with the same `GetParent()` as visible; record the
  server-bone and vehicle cases as pending DayZDiag items (local server plus one client is enough for server-bone, two clients for the rest).

### P3-1 Protocol version unchanged while the wire format changed
- HCGroupProtocol.c:5 (`VERSION = 2`), HCGroupData.c:36, :84, :106 (`Version = 2`).
- Scenario: Snapshot gains Places, Member.Role and many Settings fields; request gains Role and Op 13. An old client against a new server passes the
  Version check and then reads a mis-framed stream. Bump to 3 so SnapshotValid refuses cleanly. Journal SchemaVersion stays 1 with additive
  Officers and Explorers; a rollback to the old build silently drops them on the next save. Note it in the changelog.

### P3-2 Journal copies full place objects per explorer; entries never evicted
- HCGroupRules.c:696 (`found.Visits.Insert(place)`), REPORT.md "no automatic eviction".
- Scenario: each account stores up to 64 full copies (id, name, position, radius, about 120 B) so a renamed or removed catalog entry leaves stale
  names, and 256 explorers x 64 x 120 B is about 2 MB against MaxStoreBytes=262144; past the quota every discovery and every group edit returns LIMIT.
  Fine for 3-6 players, not for a long-lived server.
- Fix: store place ids only and resolve against the catalog at KnownPlaces; evict explorers that are not in any group and unseen for N days.

### P3-3 Equipment scans are uncached and repeated per pair; client redraws reload every icon
- HCGroupService.c:366-367 (Read called per source/recipient pair): 56 pairs x 2 reads x up to 512 items for 8 members, each 2 s.
  Cache one HCGroupEquipment per peer per Tick.
- HCGroupMapLayers.c:53 (LoadImageFile every Pin every 0.25 s) and :66 (inventory scan every Draw). Load the texture once, scan at 1 Hz.

### P3-4 Map and GPS semantics are narrower than native on some configs
- HCGroupMapLayers.c:66-67: HasMap ignores `CfgGameplayHandler.GetMapIgnoreMapOwnership()`. On a server with that flag set the grid still wants an item.
  Decide and document.
- :87-89 / HCGroupVisibility.c:23: client coordinates need a powered GPS (IsTurnedOn), whereas server `HasGPS` (HCGroupService.c:352-358) is possession-based
  (`MapNavigationBehaviour` sets the GPS bit when a GPS item is in the inventory, regardless of power). The "Carry a GPS" text is wrong for an unpowered GPS.
- HCGroupPlaces.c:16, :33, :49: if the native Names list has more than 256 valid entries the module refuses at start (latched, fail closed, documented).
  Not checked against a real world config.

## Correctness and privacy conclusions (no defect found)
- Server never sends forbidden data: positions are produced only in `Member()` (HCGroupService.c:421-433) after the alive, GPS (when RequireGPS),
  distance (when WorldIcons only), radio and LOS gates. Candidates carry no position. Places go only in FULL frames to a live peer
  (:486) and are the personal visits plus, only with ShareDiscovery, those of current group members (HCGroupRules.c:711-715). The catalog is never sent.
- Revocation: kick, leave, transfer and disband all Broadcast FULL; places for a former group disappear because KnownPlaces is a view of current membership.
  Dead peers get no positions (Member alive gate) and no places; visits persist by account id so reconnect restores them. Cached client Places
  survive a POSITIONS frame by design but are replaced by the next FULL.
- Role checks are only in `HCGroupRules.Apply` (server); the client sends a request Role that is range-checked (Role < 0 or > 1 gives INVALID) and the owner role cannot be assigned.
  Client state is a display cache.
- Migration: Officers and Explorers default to empty arrays, so existing journals load; StateValid bounds officers (not owner, member of group, unique),
  explorers (count, per-account visits, unique place ids) and places (radius 5-500, valid position). Clone and Commit keep the byte cap.
- UAMapToggle is bound once: `HCGroupGameplay.c:32` (unchanged by this diff, opens the HC menu before native `super.OnUpdate`) and the close in
  HCGroupMapMenu.c:150. Native only reacts to it when GetMapIgnoreMapOwnership() is on and a menu is not open (missionGameplay.c:606-612); HC opens first, so no double open.

## Native API verification (scripts-1.30.164289)
- `DayZPhysics.RaycastRV(..., ObjIntersectView, radius, CollisionFlags.NEARESTCONTACT)` exists (EnDebug.c / DayZPhysics); argument order and constants match.
- `Human.GetBoneIndexByName` (human.c:1417) and `Object.GetBonePositionWS` (Object.c:238) exist. Whether the server returns a posed head bone is NOT observed.
- `ItemMap` (InventoryItem.c:1187), `ItemGPS` (:53) with `IsTurnedOn()` = `GetCompEM().IsWorking()` (GPSReceiver.c:83-86),
  `PersonalRadio extends TransmitterBase extends ItemTransmitter` with `GetTunedFrequency()` (InventoryItem.c:18) and `IsTransmitter()` (TransmitterBase.c:39) exist.
  The IsTransmitter filter excludes entertainment radios.
- `MapNavigationBehaviour.GetNavigationType()` is possession-based (MapNavigationBehaviour.c:46-95) and does not read the cfgGameplay ignore-ownership flags.
  Those are read only in MapMenu.c:117-118, :262 and missionGameplay.c:606. The server `HasGPS` therefore ignores them as required.
- `CfgGameplayHandler.GetMapIgnoreMapOwnership` and `GetMapIgnoreNavItemsOwnership` exist (CfgGameplayHandler.c:438, :443).
- Unobserved engine behaviour (keep pending, not accepted): RaycastRV against players with ObjIntersectView returns the player object;
  server head-bone pose; ConfigGetFloatArray on `CfgWorlds <world> Names ... position`; MapWidget.MapToScreen under pan and zoom; CanvasWidget.DrawLine layering over MapWidget.

## Compile-rule scan (changed .c files)
No findings: no identifier equal to an engine type; no line starting with `||` or `&&`; no ternary; no duplicate locals across sibling scopes;
out args (`contact`, `normal`, `component`, `left/top/width/height`) declared before the call; no statement with more than 8 `+`;
`ToString()` explicit on every int concatenation; every loop bounded (`cell <= 50`, `examined < 6`, `used >= 32`, `mHCUsed >= 602`, 512-item scans);
enum members qualified (`HCGroupRole.OFFICER`, `HCGroupOp.SET_ROLE`, `HCEventStatus.ANNOUNCED`); override parameter names match the engine (`OnUpdate(float timeslice)`).

## Bounded traffic and budgets
- FULL snapshot adds Places (at most MaxDiscoveries=64 x about 120 B), sent on mutation, SYNC and discovery commit only; POSITIONS frames stay position-only.
- Per-Tick budgets: LOS rays 32 (see P2-1); discovery 6 peers per pass every 5 s (see P2-2); equipment scans capped at 512 items (see P3-3).
- Client Draw runs at 4 Hz with at most 602 pooled pins and 102 DrawLine calls.

## Mutation table (scratch copy, 62 mutants plus baseline; 31 killed, 31 survived, 0 pattern-missing)
Killed: M01 M02 M07 M08 M09 M10 M11 M16 M17 M20 M22 M25 M26 M27 M28 M29 M32 M33 M34 M35 M36 M37 M38 M46 M47 M48 M53 M54 M55 M59 M60.
Survived: M03 M04 M05 M06 M12 M13 M14 M15 M18 M19 M21 M23 M24 M30 M31 M39 M40 M41 M42 M43 M44 M45 M49 M50 M51 M52 M56 M57 M58 M61 M62.
Descriptions and patterns are in run_mutants.py; per-mutant output is in mutants.txt. M00 (baseline) survived as expected.

## Required before merge
1. P2-3: add failing-first tests for at least M21, M03/M04, M05/M06, M13-M15, M31.
2. P2-1 and P2-2: cache LOS verdicts and skip the clone when no place is in range, or record them as accepted limits with a measured budget.
3. P2-4: ignore the shared vehicle in HasLOS or record it as a pending DayZDiag item.
Everything else can follow as tracked P3 items. Runtime acceptance and production enablement remain pending.
