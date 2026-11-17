"""Literal observation-text comparison with the parent, allowing exactly the three added read-back fields."""
import importlib,re,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
added=re.compile(r'"handguard_found_type":"[^\"]*","handguard_slot_occupied":(?:true|false),"handguard_rail_functional":(?:true|false),')

def fixture(version):
    for name in list(sys.modules):
        if name in ('tools','tests') or name.startswith(('tools.','tests.')):del sys.modules[name]
    sys.path[:]=[str(ROOT/version)]+[p for p in sys.path if p not in (str(ROOT/'head'),str(ROOT/'parent'))]
    return importlib.import_module('tests.unit.test_taped_light_probe')
for scenario,kwargs in [('default',{}),('stuck_and_background',dict(stuck=('PlainBag',),background=3)),('class_timeout',dict(spawn_ms=600)),('watchdog_partial',dict(spawn_ms=15000))]:
    outputs=[]
    for version in ('parent','head'):
        f=fixture(version);world=f.World(**kwargs);f.run_hook(world)
        outputs.append((world.files[f.OUTPUT_PATH], '\n'.join(world.printed)))
    a,b=outputs;stripped=added.sub('',b[0])
    print(scenario,'literal_equal=',a[0]==b[0],'equal_after_only_three_new_fields_removed=',a[0]==stripped,'print_equal=',a[1]==b[1],'parent_bytes=',len(a[0]),'head_bytes=',len(b[0]),'sha_after_strip=',hashlib.sha256(stripped.encode()).hexdigest())
