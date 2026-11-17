"""Read installed declarations only; do not export native sources."""
from pathlib import Path
import json,re,sys,collections
ROOT=Path(__file__).resolve().parent
# Use the immutable checkout as mutation reruns may temporarily alter the scratch export.
sys.path.insert(0,str(ROOT.parents[1]))
from tools.setup import taped_light_probe as p,probe_runtime as rt
CACHE=Path('/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289')
c=json.loads(Path('/home/david/.cache/hollow-country/experiments/taped-light-probe-003/classification.json').read_text())
hook=rt._clean(p.render_hook(p.select_targets(c)).decode())
calls=set(re.findall(r'\b([A-Za-z_]\w*)\s*\(',hook))
own={m.group(2) for m,b,s in rt._function_bodies(hook)}
external=calls-own-{'if','while','for','array','return'}
pattern=re.compile(r'^\s*(?:(?:static|proto|native|override|protected|private|owned|ref|notnull|autoptr|external)\s+)*([\w<>]+)\s+('+'|'.join(sorted(external))+r')\s*\(')
found=collections.defaultdict(list)
for path in sorted(CACHE.rglob('*.c')):
    relative=str(path.relative_to(CACHE))
    for n,line in enumerate(path.read_text(errors='replace').splitlines(),1):
        m=pattern.match(re.sub(r'/\*.*?\*/', '', line))
        if m and m[1] not in {'return','new','else'}:
            found[m[2]].append((relative,n,line.strip()))
preferred=['1_Core/proto/EnScript.c','1_Core/proto/EnString.c','1_Core/proto/EnConvert.c','1_Core/proto/EnSystem.c','1_Core/proto/EnDebug.c','1_Core/proto/EnWorld.c','1_Core/proto/EnFile.c','3_Game/Entities/Object.c','3_Game/Entities/EntityAI.c','3_Game/Global/Game.c','3_Game/Systems/Inventory/Inventory.c','3_Game/Systems/Inventory/InventorySlots.c','3_Game/gameplay.c','3_Game/tools/utilityclasses.c','5_Mission/Mission/MissionBase.c']
for name in sorted(external):
    entries=sorted(found[name], key=lambda x:(preferred.index(x[0]) if x[0] in preferred else 999,x[0],x[1]))
    # Same method name has different receiver-specific declarations; preserve the base signatures, not arbitrary mod overrides.
    chosen=[x for x in entries if x[0] in preferred]
    if not chosen:chosen=entries[:2]
    print(name)
    for file,n,line in chosen:print(f'  {file}:{n}: {line}')
missing=sorted({name for name in external if not found.get(name)})
print('EXTERNAL_API_COUNT',len(external),'MISSING',missing)
assert not missing
