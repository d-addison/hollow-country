"""Static native declaration and generated-source audit; no engine execution."""
import hashlib
import json
from pathlib import Path
import re
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source'))
from tools.setup import interior_sampler as samp
from tools.setup import probe_runtime as rt
from tests.unit import test_interior_sampler as ts
cache=Path.home()/'.cache/hollow-country/native-scripts/scripts-1.30.164289'
types=rt.native_type_names(cache)
for label,targets,frame in [('default',ts.sampler_targets(),()),('max',ts.sampler_targets(per_class=16),[(name,float(i),0.0,1.0) for name in ('Land_HouseBlock_2F1','Land_Mil_Barracks2') for i in range(32)])]:
    hook=samp.render_hook(targets,frame_points=frame).decode()
    (HERE/(label+'-hook.c')).write_text(hook)
    issues=samp.lint_sampler_hook(hook,native_types=types)
    print(json.dumps({'hook':label,'bytes':len(hook.encode()),'sha256':hashlib.sha256(hook.encode()).hexdigest(),
                      'native_types':len(types),'lint':issues,'max_plus':max(n for _,n in samp.statement_plus_counts(hook))}))
    clean=samp._blank(hook)
    print('External member calls:',','.join(sorted(set(re.findall(r'\.([A-Za-z_]\w*)\s*\(',clean)))))
    print('Loop headers:')
    for n,line in enumerate(clean.splitlines(),1):
        if re.search(r'\b(for|while)\s*\(',line): print(f'{label}-hook.c:{n}: {line.strip()}')
patterns={
 '3_Game/Entities/Building.c':r'proto native .*\b(GetDoorCount|IsDoorOpen|IsDoorOpened|IsDoorOpenedAjar|IsDoorClosed|IsDoorLocked|OpenDoor|CloseDoor|GetDoorSoundPos)\(',
 '3_Game/Global/DayZPhysics.c':r'proto .*RaycastRV\(',
 '3_Game/AI/AIWorld.c':r'proto .*\b(SetFlags|SetCost|FindPath|SampleNavmeshPosition)\(',
 '1_Core/proto/EnEntity.c':r'proto .*\b(CoordToLocal|CoordToParent|GetParent|GetPosition)\(',
 '3_Game/Entities/Object.c':r'proto .*\b(ClippingInfo|GetType|GetOrientation)\(',
 '3_Game/Global/World.c':r'proto .*GetAIWorld\(',
 '3_Game/Global/Game.c':r'proto .*\b(IsServer|GetWorld|SurfaceY|GetObjectsAtPosition3D|GetWorldName|GetVersion|GetTime)\(|ScriptCallQueue GetCallQueue\(',
 '1_Core/proto/EnSystem.c':r'\b(OpenFile|FPrint|CloseFile|FileExist|MakeDirectory|Print)\(',
}
for rel,pattern in patterns.items():
    p=cache/rel
    if not p.exists(): print('MISSING '+rel); continue
    for n,line in enumerate(p.read_text(errors='replace').splitlines(),1):
        if re.search(pattern,line): print(f'{rel}:{n}: {line.strip()}')
# Additional core declarations whose exact file is discovered in the authoritative snapshot.
need=re.compile(r'^\s*(?:proto|static|void|ScriptCallQueue|private proto).*\b(CallLater|GetCallQueue|AsciiToString|ToString|Substring|Replace|Length|Distance|AbsFloat|Sqrt)\(')
for p in sorted(cache.rglob('*.c')):
    if not (p.relative_to(cache).parts[0] in ('1_Core','2_GameLib') or p.name=='game.c' or 'scriptcallqueue' in p.name.lower()): continue
    for n,line in enumerate(p.read_text(errors='replace').splitlines(),1):
        if need.search(line): print(f'{p.relative_to(cache)}:{n}: {line.strip()}')
