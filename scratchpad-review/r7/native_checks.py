"""Inspect installed source declarations; never compile or execute the engine."""
import sys,re,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'head'))
from tools.setup import probe_runtime as rt,taped_light_probe as p,ce_probe as ce
from tests.unit import test_taped_light_probe as pf,test_ce_probe as cf
cache=Path('/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289')
names=rt.native_type_names(cache)
print('native_declared_type_names=',len(names))
for name,hook in [('taped',p.render_hook(p.select_targets(pf.classification())).decode()),('ce',ce.render_hook(cf.targets_for(),export_delay_s=30,census_delay_s=240).decode())]:
 print(json.dumps(dict(hook=name,methods=len(list(rt._function_bodies(rt._clean(hook)))),max_statement_plus=rt.max_statement_plus(hook),lint=rt.lint_hook(hook,native_types=names,explicit_numbers=name=='taped')),sort_keys=True))
for file,pattern in [('3_Game/Systems/Inventory/Inventory.c',r'proto native EntityAI (?:FindAttachment|CreateAttachmentEx)\('),('3_Game/InventorySlots.c',r'GetSlotIdFromString|IsSlotIdValid'),('4_World/Entities/ItemBase/Switchable_Base/UniversalLight.c',r'FindAttachment\(|hasRailFunctionality|weaponHandguard'),('4_World/Entities/Firearms/AKM.c',r'AK_RailHndgrd'),('4_World/Entities/Firearms/AK101.c',r'AK_RailHndgrd'),('4_World/Entities/Firearms/M4A1.c',r'M4_RISHndgrd'),('4_World/Entities/Firearms/MP5.c',r'MP5_RailHndgrd')]:
 path=cache/file
 if not path.exists():
  candidates=list(cache.rglob(Path(file).name))
  if len(candidates)!=1:print('UNRESOLVED',file,[str(x) for x in candidates]);continue
  path=candidates[0]
 for n,line in enumerate(path.read_text().splitlines(),1):
  if re.search(pattern,line):print(str(path.relative_to(cache))+':'+str(n)+': '+line.strip())
