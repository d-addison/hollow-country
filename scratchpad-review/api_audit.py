from pathlib import Path
import re
root=Path('/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289')
checks={
'3_Game/gameplay.c':r'^DayZGame GetGame\(',
'3_Game/Global/Game.c':r'(?:proto|ScriptCallQueue).*\b(?:GetObjectsAtPosition3D|GetWorld|GetWorldName|GetVersion|IsServer|GetTime|GetCallQueue)\(',
'3_Game/Global/World.c':r'proto.*GetAIWorld\(',
'3_Game/Global/DayZPhysics.c':r'proto static bool\s+RaycastRV\(',
'3_Game/AI/AIWorld.c':r'proto.*\b(?:SetFlags|SetCost|FindPath|SampleNavmeshPosition)\(',
'3_Game/Entities/Building.c':r'proto.*\b(?:GetDoorCount|GetDoorSoundPos)\(',
'3_Game/Entities/Object.c':r'(?:proto.*\b(?:GetPosition|GetOrientation|ClippingInfo)|string GetType)\(',
'1_Core/proto/EnEntity.c':r'proto.*\b(?:CoordToParent|CoordToLocal)\(',
'1_Core/proto/EnConvert.c':r'proto.*\b(?:ToString|AsciiToString|Distance)\(',
'1_Core/proto/EnScript.c':r'proto.*\b(?:Cast|Count|Get|Find|Insert)\(|typedef array<vector>',
'1_Core/proto/EnString.c':r'proto.*\b(?:Substring|Replace|Length)\(',
'1_Core/proto/EnMath.c':r'proto.*Sqrt\(',
'1_Core/proto/EnMath3D.c':r'^proto native vector Vector\(',
'1_Core/proto/EnSystem.c':r'^proto.*\b(?:FileExist|OpenFile|CloseFile|FPrintln|MakeDirectory)\(',
'1_Core/proto/EnDebug.c':r'^proto void Print\(',
'2_GameLib/tools.c':r'proto void CallLater\(',
'5_Mission/mission/missionServer.c':r'override void OnInit\(',
}
for name,pattern in checks.items():
 hits=[(i,l.strip()) for i,l in enumerate((root/name).read_text(encoding='latin1').splitlines(),1) if re.search(pattern,l)]
 assert hits,name
 for i,l in hits:print(f'{name}:{i}: {l}')
