# Installed native declarations inspected

All paths below are relative to
`~/.cache/hollow-country/native-scripts/scripts-1.30.164289/`.
Declarations/call-site inspection proves availability only, not behavior.
No vanilla source/assets are included in this change.

| API | Native file:line |
| --- | --- |
| GetGame | 3_Game/gameplay.c:636 |
| IsServer / GetTickTime / GetWorldName(out) | 3_Game/Global/Game.c:1120 / :914 / :932 (value overload :934) |
| GetObjectsAtPosition3D | 3_Game/Global/Game.c:930 (out object/cargo arrays) |
| Object IsPendingDeletion / GetPosition / GetType / IsAlive / IsRuined | 3_Game/Entities/Object.c:215 / :287 / :467 / :517 / :1219 |
| EntityAI GetHierarchyRootPlayer / GetHierarchyParent | 3_Game/Entities/EntityAI.c:882 / :885 |
| EEOnCECreate | 3_Game/Entities/EntityAI.c:1414; preceding line explicitly says **CE/Debug** |
| EEKilled(Object killer) | 3_Game/Entities/EntityAI.c:1104 |
| EEItemLocationChanged(oldLoc,newLoc) | 3_Game/Entities/EntityAI.c:976; native ItemBase override 4_World/Entities/ItemBase.c:987; old/new owner use :994–998 |
| InventoryLocation.GetParent | 3_Game/Systems/Inventory/InventoryLocation.c:52 |
| Man.GetIdentity / PlayerIdentity.GetId / GetPlayer | 3_Game/Entities/Man.c:21; 3_Game/gameplay.c:368 / :375 |
| IsUnconscious / IsPlayerDisconnected | 3_Game/Entities/Man.c:63; 4_World/Entities/ManBase/PlayerBase.c:2638 |
| Class.Cast (including derived type Cast syntax) | 1_Core/proto/EnScript.c:94 (native example :86) |
| string.ToType / typename.Spawn | 1_Core/proto/EnString.c:95; 1_Core/proto/EnConvert.c:544; guarded native usage 3_Game/Entities/EntityAI.c:1072–1078 |
| Vector / vector.DistanceSq | 1_Core/proto/EnMath3D.c:18; 1_Core/proto/EnConvert.c:210 |
| int.ToString / vector.ToString | 1_Core/proto/EnConvert.c:30 / :138 |
| Math.Min / Math.Max | 1_Core/proto/EnMath.c:553 / :566 |
| ScriptInvoker.Insert / Remove | 2_GameLib/tools.c:120 / :122 |
| Math.Floor / RandomIntInclusive | 1_Core/proto/EnMath.c:427 / :54 |
| array Count / Clear / Find / Insert / Remove / RemoveOrdered | 1_Core/proto/EnScript.c:380 / :385 / :394 / :407 / :463 / :470 |
| string Length / Hash / IndexOf / LastIndexOf / Contains / Trim / Substring / ToInt | 1_Core/proto/EnString.c:199 / :223 / :240 / :253 / :286 / :304 / :113 / :20 |
| FileExist / OpenFile / ReadFile / CloseFile / FPrint | 1_Core/proto/EnSystem.c:397 / :417 / :425 / :443 / :462 |
| FindFile / FindNextFile / CloseFindFile / MakeDirectory / DeleteFile | 1_Core/proto/EnSystem.c:520 / :521 / :522 / :525 / :528 |
| Print | 1_Core/proto/EnDebug.c:96 |
| JsonFileLoader.LoadData / MakeData | 3_Game/tools/JsonFileLoader.c:69 / :85 |
| serializer Write / Read; ScriptRPC.Send | 1_Core/proto/Serializer.c:57 / :58; 3_Game/gameplay.c:117 |
| DayZGame.Event_OnRPC dispatch | 3_Game/DayZGame.c:991 / :3141–3144 |
| GetWorkspace / GetUIManager / GetPlayer | 3_Game/Global/Game.c:85 / :943 / :944 |
| Widget Enable / FindAnyWidget / Unlink / Workspace.CreateWidgets | 1_Core/proto/EnWidgets.c:126 / :169 / :173 / :181 |
| TextWidget.SetText | 1_Core/proto/EnWidgets.c:195 |
| TextListbox ClearItems / SelectRow / GetSelectedRow / AddItem | 1_Core/proto/EnWidgets.c:427 / :429 / :430 / :442 |
| UIScriptedMenu Close / SetID / Init / OnShow / OnHide / Update / OnClick | 3_Game/tools/UIScriptedMenu.c:31 / :146 / :163 / :173 / :184 / :195 / :238 |
| UIManager EnterScriptedMenu / GetMenu / FindMenu | 3_Game/tools/UIManager.c:4 / :59 / :160 |
| GetUApi / GetInputByName / UAInput.LocalPress | 3_Game/InputAPI/UAInput.c:279 / :218 / :60 |
| IsControlDisabled interface | 3_Game/gameplay.c:792 |

The optional non-native API is in the unchanged addon:
`mods/HollowCountryExpansionAI/scripts/4_World/HCXAIAdapter.c:446` defines
`HCExpansionAIEventProvider`. It forwards Ready/Start/Observe/Stop/Gone to
HCXAIService.Adapter and StartLease/ObserveLease/StopLease/Gone, preserving that
addon's admission, ownership, cleanup and fairness checks. No direct eAI calls
were added. No trusted ownership/artifact/observer hooks were fabricated.
