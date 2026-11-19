/*
W5 #60 / EXP-A3: installed-source evidence, NOT runtime acceptance.
Root: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289.

3_Game/UndergroundAreaLoader.c:69-99 defines JsonUndergroundAreaTriggerData;
:105-132 loads the mission-root cfgundergroundtriggers.json or the stock file;
:156-188 creates indexed carriers and sends the complete native data. The files
inspected in installed Chernarus mission/CE data contain an empty Triggers array.
4_World/Entities/ScriptedEntities/Triggers/UndergroundTrigger.c:1-69 defines
replicated carriers and client-local UndergroundTrigger (the native 1.30 name
is UndergroundTrigger, not UndergroundAreaTrigger). :90-118 Init uses measured
half-size extents; :164-186 enters/leaves UndergroundHandlerClient. No ordinary
house cellar bounds exist in the project survey. No boxes or carriers are
invented and no stock trigger indices, JSON or RPC are changed.

The retained, DISABLED heuristic is in HCCellarsClient.c: controlled player >2m below
GetGame().SurfaceY AND Man.IsSoundInsideBuilding(). Native 3_Game/Global/Game.c:
1176 and Entities/Man.c:37 expose those signatures; native 4_World/Classes/
Environment/Environment.c:511-513 uses that same inside query. This is a
heuristic, not measured room geometry; shallow/above-terrain cellars are omitted.
It never sets PlayerBase underground presence or gameplay state. HC-31 now
refuses allocation AND sampling through HCCellarAdmission; the shared admission
is false until a native qualification protocol is implemented and observed.

The separate local requester inherits the setter in 3_Game/PPEManager/Requesters/
PPERUndergroundAcco.c:1-6. Classes/UndergroundHandlerClient.c:18,39 names/loads
the stock underground lighting table, :314-341 applies eye/lighting, :378-404
handles NVG exposure. The fallback reuses that table and setter with a bounded
fade, yields entirely to native underground/NVG, and changes no audio or NVG
exposure. HCLightingClient yields the single user-table slot during the fallback.
HollowCountryDarkCellars profile string "0" disables before helper allocation.
EnableAmbientLife remains the server preference; neither that preference nor
the local visual preference bypasses the closed HC-31 qualification admission.
No settings RPC is introduced. The normal native underground path is unchanged.

HCCellarsModule self-registers and emits one HCV2Admission preference diagnostic
plus one HC-31 startup receipt with bounded authored/measured class counts.
HC-1 captures its cached refused/off status without repeating IO. Pending counts
retain all authored classes and admitted stays zero. EXP-A3 is unchanged; its
sky-preset question does not qualify the fallback or measured room geometry.
Lead validation PENDING: native Windows
compile, DayZDiag, normal PBO/server, two clients in a reachable cellar by day/
night, upper floor/exterior, torch/NVG, native-area transition, death/rejoin and
mission exit. Record building class, depth, inside query, RPT and screenshots.
Verify no persistent darkness, daylight illumination or multiplayer effects.
Nothing observed in DayZ yet.
*/
