"""Make the ambiguous 'rsplit/endswith check' claim precise with independent counterexamples."""
from pathlib import Path
import types,sys,io,contextlib,unittest,json
sys.path.insert(0,str(Path(__file__).resolve().parent/'head'))
from tools.audit import taped_light_report as original
from tests.unit import test_taped_light_report as f
src=Path(original.__file__).read_text()
base='/dz/weapons/attachments/light'
item=dict(f.proxy(),selection='proxy:'+base+'/.p3d.001',cfg_class='Proxy',model=base+'/.p3d',view_selection='proxy:'+base+'/.p3d.001')
def verdict(mod):
    row=f.row('AK74','slot_host',f.gun_slots(weapon_model=False),f.good_gun_lights(),proxies=[item])
    result=mod.build_report(f.classification([f.host('AK74','slot_host')]),f.observations([row]))
    slot=result['hosts'][0]['lights']['UniversalLight']['slots']['weaponFlashlight']
    return [slot['verdict'],slot['reason']]
for name,before in [('only_rsplit',' or not path.rsplit("/", 1)[-1]'),('only_endswith',' or path.endswith("/")'),('both_rsplit_and_endswith',' or not path.rsplit("/", 1)[-1] or path.endswith("/")')]:
    assert src.count(before)==1
    m=types.ModuleType('tools.audit.extended_guard_mutant');m.__file__=original.__file__
    exec(compile(src.replace(before,''),name,'exec'),m.__dict__)
    f.report=m;log=io.StringIO()
    with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):result=unittest.TextTestRunner(stream=log).run(unittest.defaultTestLoader.loadTestsFromModule(f))
    Path(__file__).with_name(name+'.log').write_text(log.getvalue())
    print(json.dumps({'mutation':name,'before':before,'after':'','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'counterexample':item['selection'],'baseline':verdict(original),'mutant':verdict(m)},sort_keys=True))
f.report=original
