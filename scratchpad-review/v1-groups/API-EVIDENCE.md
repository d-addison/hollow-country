# Pinned native API evidence

Root: `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`. These are source declarations/usages, not runtime acceptance.

| API / inspected type | Cache file:line |
| --- | --- |
| `proto native void SetPos` | `1_Core/proto/EnWidgets.c:140` |
| `proto native void SetSize` | `1_Core/proto/EnWidgets.c:141` |
| `proto native void SetColor` | `1_Core/proto/EnWidgets.c:144` |
| `void GetScreenPos` | `1_Core/proto/EnWidgets.c:153` |
| `void GetScreenSize` | `1_Core/proto/EnWidgets.c:154` |
| `Widget CreateWidgets` | `1_Core/proto/EnWidgets.c:181` |
| `void SetTextExactSize` | `1_Core/proto/EnWidgets.c:193` |
| `bool LoadImageFile` | `1_Core/proto/EnWidgets.c:257` |
| `bool SetImage` | `1_Core/proto/EnWidgets.c:267` |
| `void DrawLine` | `1_Core/proto/EnWidgets.c:343` |
| `void Clear()` | `1_Core/proto/EnWidgets.c:344` |
| `void SetText(` | `1_Core/proto/EnWidgets.c:195` |
| `string GetText` | `1_Core/proto/EnWidgets.c:349` |
| `int AddItem` | `1_Core/proto/EnWidgets.c:442` |
| `void ClearItems` | `1_Core/proto/EnWidgets.c:427` |
| `SelectRow` | `1_Core/proto/EnWidgets.c:429` |
| `GetSelectedRow` | `1_Core/proto/EnWidgets.c:430` |
| `FindAnyWidget` | `1_Core/proto/EnWidgets.c:169` |
| `void Show` | `1_Core/proto/EnWidgets.c:125` |
| `void Unlink` | `1_Core/proto/EnWidgets.c:173` |
| `class MapWidget` | `3_Game/gameplay.c:322` |
| `ClearUserMarks` | `3_Game/gameplay.c:324` |
| `AddUserMark` | `3_Game/gameplay.c:325` |
| `SetMapPos` | `3_Game/gameplay.c:327` |
| `SetScale` | `3_Game/gameplay.c:329` |
| `MapToScreen` | `3_Game/gameplay.c:332` |
| `ScreenToMap` | `3_Game/gameplay.c:333` |
| `string GetName` | `3_Game/gameplay.c:362` |
| `string GetId` | `3_Game/gameplay.c:368` |
| `ConfigGetText(string` | `3_Game/Global/Game.c:449` |
| `ConfigGetFloatArray` | `3_Game/Global/Game.c:578` |
| `ConfigGetChildName` | `3_Game/Global/Game.c:594` |
| `ConfigGetChildrenCount` | `3_Game/Global/Game.c:611` |
| `GetWorldName(` | `3_Game/Global/Game.c:932` |
| `GetPlayer()` | `3_Game/Global/Game.c:944` |
| `GetPlayers(` | `3_Game/Global/Game.c:945` |
| `GetWorkspace` | `3_Game/Global/Game.c:85` |
| `GetWorld()` | `3_Game/Global/Game.c:931` |
| `GetTickTime` | `3_Game/Global/Game.c:914` |
| `GetInput()` | `3_Game/Global/Game.c:728` |
| `GetUIManager` | `3_Game/Global/Game.c:943` |
| `GetScreenPos(` | `3_Game/Global/Game.c:963` |
| `GetScreenPosRelative` | `3_Game/Global/Game.c:965` |
| `GetCurrentCameraPosition` | `3_Game/Global/Game.c:731` |
| `GetCurrentCameraDirection` | `3_Game/Global/Game.c:732` |
| `ConfigGetVector` | `3_Game/Global/Game.c:532` |
| `bool	RaycastRV` | `3_Game/Global/DayZPhysics.c:199` |
| `GetBonePositionWS` | `3_Game/Entities/Object.c:238` |
| `GetPosition()` | `3_Game/Entities/Object.c:287` |
| `bool IsAlive` | `3_Game/Entities/Object.c:517` |
| `bool IsRuined` | `3_Game/Entities/Object.c:1219` |
| `GetHierarchyRootPlayer()` | `3_Game/Entities/EntityAI.c:882` |
| `GameInventory GetInventory` | `3_Game/Entities/EntityAI.c:1884` |
| `ComponentEnergyManager GetCompEM` | `3_Game/Entities/EntityAI.c:3409` |
| `bool EnumerateInventory` | `3_Game/Systems/Inventory/Inventory.c:127` |
| `int CountInventory` | `3_Game/Systems/Inventory/Inventory.c:134` |
| `class ItemTransmitter extends` | `4_World/Entities/Core/Inherited/InventoryItem.c:14` |
| `GetTunedFrequency()` | `4_World/Entities/Core/Inherited/InventoryItem.c:18` |
| `class ItemGPS` | `4_World/Entities/Core/Inherited/InventoryItem.c:53` |
| `class ItemCompass` | `4_World/Entities/Core/Inherited/InventoryItem.c:116` |
| `class ItemMap extends` | `4_World/Entities/Core/Inherited/InventoryItem.c:1187` |
| `class TransmitterBase` | `4_World/Entities/ItemBase/TransmitterBase.c:2` |
| `bool IsTransmitter` | `4_World/Entities/ItemBase/TransmitterBase.c:39` |
| `class PersonalRadio` | `4_World/Entities/ItemBase/TransmitterBase/PersonalRadio.c:1` |
| `MapNavigationBehaviour GetMapNavigationBehaviour` | `4_World/Entities/ManBase/PlayerBase.c:3652` |
| `GetBoneIndexByName("Head")` | `4_World/Entities/ManBase/PlayerBase.c:2454` |
| `override bool IsUnconscious` | `4_World/Entities/ManBase/PlayerBase.c:3925` |
| `EMapNavigationType GetNavigationType` | `4_World/Entities/ItemBase/MapNavigationBehaviour.c:46` |
| `bool IsWorking()` | `3_Game/tools/Component/ComponentEnergyManager.c:925` |
| `Round(` | `1_Core/proto/EnMath.c:413` |
| `Max(` | `1_Core/proto/EnMath.c:566` |
| `RandomIntInclusive` | `1_Core/proto/EnMath.c:46` |
| `void OnShow()` | `3_Game/tools/UIScriptedMenu.c:173` |
| `void OnHide()` | `3_Game/tools/UIScriptedMenu.c:184` |
| `void Close()` | `3_Game/tools/UIScriptedMenu.c:31` |
| `void SetID` | `3_Game/tools/UIScriptedMenu.c:146` |
| `GetHourMinuteSecondUTC` | `1_Core/proto/EnSystem.c:76` |
| `GetYearMonthDayUTC` | `1_Core/proto/EnSystem.c:100` |
| `OpenFile(` | `1_Core/proto/EnSystem.c:406` |
| `ReadFile(` | `1_Core/proto/EnSystem.c:425` |
| `CloseFile(` | `1_Core/proto/EnSystem.c:413` |
| `MakeDirectory(` | `1_Core/proto/EnSystem.c:525` |
| `FileExist(` | `1_Core/proto/EnSystem.c:397` |
| `FindFile(` | `1_Core/proto/EnSystem.c:520` |
| `FindNextFile(` | `1_Core/proto/EnSystem.c:521` |
| `CloseFindFile(` | `1_Core/proto/EnSystem.c:522` |
| `DeleteFile(` | `1_Core/proto/EnSystem.c:528` |
| `FPrint(` | `1_Core/proto/EnSystem.c:455` |

| Additional API / type | Cache file:line |
| --- | --- |
| `GetBoneIndexByName` | `3_Game/human.c:1417` |
| `ItemGPS.IsTurnedOn`; powered receiver override | `4_World/Entities/Core/Inherited/InventoryItem.c:55`; `4_World/Entities/ItemBase/Gear/Navigation/GPSReceiver.c:83` |
| `MapMarkerTypes.GetMarkerTypeFromID` | `5_Mission/GUI/MapMarkersInfo.c:36` |
| `InventoryTraversalType.PREORDER` | `3_Game/gameplay.c:7` |
| `World.GetWorldSize` | `3_Game/Global/World.c:82` |
| `JsonFileLoader.LoadData`, `MakeData` | `3_Game/tools/JsonFileLoader.c:69`, `:85` |
| `ScriptRPC.Send` | `3_Game/gameplay.c:117` |
| `LocalPress_ID` | `3_Game/tools/input.c:61` |
| Native map opening / position / zoom reference | `5_Mission/GUI/MapMenu.c:85`, `:97`, `:98` |
| `MapWidget` / `CanvasWidget` / `ImageWidget` / `TextWidget` / `TextListboxWidget` / `EditBoxWidget` / `ButtonWidget` | `3_Game/gameplay.c:322`; `1_Core/proto/EnWidgets.c:341`, `:247`, `:189`, `:439`, `:347`, `:381` |
| `FrameWidget` layout node | `1_Core/proto/EnWidgets.c:31` |
| Native procedural colour texture syntax | `4_World/Entities/ExplosivesBase/RemoteDetonator.c:9` |
| Managed arrays `Count`, `Clear`, `Find`, `Get`, `Insert`, `Remove` | `1_Core/proto/EnScript.c:380`, `:385`, `:394`, `:399`, `:407`, `:463` |
| Managed sets `Count`, `Get`, `Find`, `Insert` | `1_Core/proto/EnScript.c:743`, `:750`, `:749`, `:758` |
| Managed maps `Get`, `Set`, `Count`, `Clear` | `1_Core/proto/EnScript.c:852` (class methods below this declaration) |
| Strings `Length`, `Hash`, `IndexOf`, `Substring`, `Trim`, `Contains` | `1_Core/proto/EnString.c:199`, `:223`, `:240`, `:113`, `:304`, `:286` |
| Explicit numeric `ToString` | `1_Core/proto/EnConvert.c:30` |

`ItemCompass` was inspected but no new compass/heading API is used. Existing
native `UAMapToggle` input remains unchanged; the group implementation does not
bind a physical M key or introduce input XML. `HCEventClient` is authored,
not an engine API: `mods/HollowCountry/scripts/5_Mission/Events/HCEventClient.c:76`
(`SetBrowsing`), `:82` (`Fresh`), `:95` (`GetView`). Its public row schema is
`mods/HollowCountry/scripts/3_Game/Events/HCEventTransportData.c:32`; it has no
position field. Map marks use only this player's known public rows as text.
