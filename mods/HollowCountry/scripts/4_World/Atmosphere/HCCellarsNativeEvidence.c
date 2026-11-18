/*
Issue #60 / EXP-A3 / EnableAmbientLife -- SOURCE INSPECTION ONLY, 2026-11-17.
No runtime declarations: dark cellars remain unimplemented. No class has an
evidenced cellar box, so there is no catalog, module, carrier or emitted log.
Do not mistake this report for a completed feature or a native verdict.

Installed evidence root: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289
All script citations below are relative to that root.

SUPPORTED NATIVE PATH
3_Game/UndergroundAreaLoader.c:69-99 defines JsonUndergroundAreaTriggerData:
Comment, CustomSpawn, Tag, ParentNetworkId; three-float Position, Orientation,
Size arrays; EyeAccommodation, InterpolationSpeed, UseLinePointFade,
AmbientSoundType, AmbientSoundSet, Breadcrumbs. Breadcrumb fields are at :36-50.
The root is JsonUndergroundTriggers.Triggers (:1-3).
UndergroundAreaLoader.c:105-132 loads $mission:cfgundergroundtriggers.json,
falling back to dz/worlds/<world>/ce/cfgundergroundtriggers.json only if absent.
It does not merge a delta, and does not search a mission underground/ folder.
Path (a) would require an install-time merge into that mission-root file.

Prefer path (b) AFTER geometry is evidenced: the loader owns m_JsonData (:107),
creates indexed UndergroundTriggerCarrier entities with ECE_NONE (:156-165),
and sends the complete indexed data through its native RPC (:174-188).
5_Mission/mission/missionServer.c:91 loads/spawns stock carriers; :342,363 sends
the data on connect/ready. A later server module must preserve stock indices,
append bounded data and explicitly synchronize already-connected clients before
they need new indices. Creating a bare server UndergroundTrigger is insufficient.
No core hook is currently requested; no runtime integration has been authored.

4_World/Entities/ScriptedEntities/Triggers/UndergroundTrigger.c:1-69 describes
the replicated carrier/local-trigger split. :10 limits indices to 4095; :34-68
waits for client loader data, creates the trigger with ECE_LOCAL, parents it and
calls Init(data). :90-118 sets half-size extents, accommodation and trigger type;
without breadcrumbs, accommodation == 1 means OUTER, otherwise INNER.
:132-139 admits controlled players; :164-186 enters/leaves the native handler;
:190-201 maps INNER to FULL. Reuse these native trigger entities only; do not
substitute a solid prop, item, collision mesh or custom exposure controller.

NATIVE VISUAL/AUDIO OWNERSHIP
4_World/Classes/UndergroundHandlerClient.c:37-63 loads the native underground
lighting table and obtains the native PPE requester. :314-341 drives eye
accommodation and lighting; :345-357 attenuates EnvSounds2D using accommodation
unless AmbientSoundType selects a controller. :378-404 applies accommodation
and NVG exposure; :429-475 chooses the trigger and sets underground presence.
:510-538 uses the configured ambient controller/sound set and stops it on exit;
:541-580 handles entry/exit lighting, lightning suppression and sound cleanup.
3_Game/PPEManager/Requesters/PPERUndergroundAcco.c:3-5 sets the native eye
accommodation intensity. Hollow Country must not duplicate any of these loops.
Project 5_Mission/Atmosphere/HCLightingClient.c:88-99 already yields to native
underground presence/requester; it was read and left unchanged.

GEOMETRY BLOCKER (NO AUTHORED BOXES)
Read-only installed data inspection, using existing tools.audit.pbo_config:
- wine-server-20261116/mpmissions/dayzOffline.chernarusplus/
  cfgundergroundtriggers.json:1-7 has an empty Triggers array.
- wine-server-20261116/addons/worlds_chernarusplus_ce.pbo, member
  cfgundergroundtriggers.json:1-7, also has an empty Triggers array.
- structures_residential.pbo contains 28 Land_House_ config classes and 28
  Houses/House_*.p3d members (ODOL version 56). There is no cellar/basement-named
  config class or member. A bounded read of those models exposed no printable
  cellar/basement/underground label. structures_residential_bliss.pbo likewise
  has no cellar/basement-named member. This limited inspection DOES NOT prove
  that the models lack cellars or memory selections: no ODOL geometry decoder
  was added, and no selection coordinates were obtained from the engine.
- No existing project cellar measurement was found. Native scripts expose
  geometry access methods, not ordinary-house cellar coordinates.
3_Game/Entities/Object.c:345-358 ClippingInfo returns an object's clipping
min/max and radius. Whole-house bounds do not identify an interior room or its
ceiling; slicing off their bottom would invent a cellar box.
Object.c:98-118 GetLODS/GetLODName/GetLODByName, :382 GetSelectionList,
:451-454 memory-point access/existence, :862-874 selection positions and
ModelToWorld/WorldToModel can support an actual measurement.
3_Game/gameplay.c:179-197 provides Selection.GetName/GetVertexCount/
GetVertexPosition; :203-218 provides LOD names, GetSelections and vertex access.
Until those yield justified room bounds, every ordinary-house class is omitted.

EXACT NEXT EXPERIMENT FOR THE LEAD (NOT RUN)
1. In DayZDiag 1.30.164289, walk normally into a physically accessible cellar
   of one ordinary Chernarus house. Record its actual GetType, position and
   orientation; do not nominate a class from its appearance or model filename.
   Inspect that single building, with no world scan or measurement spawns.
2. Capture ClippingInfo as an enclosing sanity bound, then memory/geometry/
   roadway LOD selection names and model-space vertices using the APIs above.
   Cap inspection at 64 selections and 32 vertices per selection; abort rather
   than truncate a proposed bounding selection. Identify the cellar floor,
   walls, ceiling and doorway from engine data plus a walk-through. Capture
   screenshots and class/model/build provenance. If no defensible room bounds
   emerge, keep that class out and record the missing evidence.
3. In a disposable SINGLE-PLAYER diagnostic mission, open the stock editor with
   PluginUndergroundTriggerManager.GetInstance().EditorToggle(). Its definition
   at 4_World/Plugins/PluginBase/PluginUndergroundTriggerManager.c:358-368 rejects
   multiplayer. Author one box from the measured room bounds, never a guessed
   clipping-box fraction. Use EyeAccommodation 0.2 as an explicit probe value,
   InterpolationSpeed 7, empty Breadcrumbs and empty AmbientSoundType/Set to
   exercise native environmental attenuation without inventing a sound asset.
   Export using the stock UI; the manager's :770-821 writes Position,
   Orientation, Size and data to $mission:cfgundergroundtriggers.json. Keep this
   experimental mission and all native assets outside source control.
4. Restart with that file; walk through the doorway, cellar, stairs, floor above
   and exterior in daylight and at night, with a torch and NVG. Confirm darkness
   and ambient attenuation occur only inside, and recover on exit/death/rejoin.
   Script > Underground Areas > Show Breadcrumbs/Disable Darkening are defined
   in PluginDiagMenu/PluginDiagMenu.c:528-534; handler :585-591 displays native
   eye accommodation and lighting lerp. Compare with the darkening toggle and
   an unmodified mission; save screenshots/video, RPT and exported geometry.
5. Repeat on a normal dedicated server/PBO with TWO clients, including a client
   already connected when a carrier is added, late join, stream-out/in, reconnect
   and restart. Check each doorway remains traversable and infected still pass.
   Verify HCLightingClient logs native_underground on entry and later resumes
   weather blending. Record network/lighting/audio results; none are accepted now.

TRACEABILITY / TESTS / LOGS
EXP-A3 exists in docs/experiments/v2-experiments.json but its current question is
sky presets, not cellars; no verdict was changed and no fallback id substituted.
Future implementation uses EnableAmbientLife alone for enablement and prints
HCV2Admission.Line("Cellars", true, "EXP-A3", HCV2Gates.Qualified("EXP-A3"))
exactly once in OnStart, plus [HollowCountry] V2 cellars classes=<n> triggers=<n>.
Neither cellar line is emitted by this report. Existing client diagnostic:
[HollowCountry] V2 client lighting blend=native_underground weight=0
is conditional on actually entering a native area; it is not expected evidence
from this change. No client cellar hook is needed for native carriers.
No behavioral smoke or RED/GREEN was fabricated: this is content only, so the
owner's no-tests-for-pure-content exception applies. No new Python tooling,
mission installation, shared-core edit or gameplay implementation was added.
Legacy docs/SPECIFICATION.md and docs/specs/001-survival-overhaul/spec.md were
absent in this worktree; AGENTS.md, runtime contract and V2 spec/plan/tasks read.
Issue #60 remains incomplete: geometry, implementation, compile, two-client
audio/visibility checks and normal-server acceptance all remain outstanding.
Nothing observed in DayZ yet.
*/
