"""Read-only independent checks. Synthetic data stays in this scratch directory."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from tools.setup import taped_light_probe as p,probe_runtime as rt
from tools.audit import taped_light_report as r
from tests.unit import test_taped_light_report as f,test_taped_light_probe as pf

def report_case(name,proxies,**fields):
 row=f.row('AK74','slot_host',f.gun_slots(weapon_model=False),f.good_gun_lights(),proxies=proxies)
 row.update(fields)
 report=r.build_report(f.classification([f.host('AK74','slot_host')]),f.observations([row]))
 slot=report['hosts'][0]['lights']['UniversalLight']['slots']['weaponFlashlight']
 print('REPORT',name,json.dumps(dict(verdict=slot['verdict'],reason=slot['reason'],model=slot['evidence'].get('model_evidence'))))

report_case('conflicting exact proxy readbacks',[f.proxy(),dict(f.proxy(),cfg_exists=False,model='',inventory_slots=[])])
report_case('known positive plus unscanned tail',[f.proxy()],proxy_count=99,proxy_scan_complete=False)
report_case('unrelated proxy / wrong slot',[f.proxy('/dz/proxies/some_other',slots=('pistolFlashlight',))])
report_case('other placeholder / same native slot',[f.proxy('/dz/proxies/some_other',slots=('weaponFlashlight',))])
report_case('missing model value',[f.proxy(model='')])
report_case('missing inventory slot value',[f.proxy(slots=())])
report_case('invalid proxy suffix',[f.proxy(number='garbage')])
report_case('missing instance suffix',[dict(f.proxy(),selection='proxy:'+f.LIGHT_PROXY_PATH)])
report_case('positive alongside cfg-absent row',[f.proxy(),f.proxy('/dz/proxies/absent',exists=False)])

types=pf.proxy_types();config=pf.proxy_config()
types['AK74']['proxies']=(pf.LIGHT_UNIVERSAL_PROXY,)
config['CfgNonAIVehicles Proxyweaponlight_universal']['inventorySlot']=['unrelated%d'%i for i in range(8)]+['weaponFlashlight']
world=pf.World(types=types,config=config);pf.run_hook(world,slots=pf._NoSelectionSlots)
obs=pf.observations_of(world)
joined=r.build_report(pf.classification(),obs)
slot=next(h for h in joined['hosts'] if h['class']=='AK74')['lights']['UniversalLight']['slots']['weaponFlashlight']
print('HOOK slot cap',json.dumps(dict(native_config_slots=9,emitted_slots=len(pf.host_row(obs,'AK74')['proxies'][0]['inventory_slots']),proxy_scan_complete=pf.host_row(obs,'AK74')['proxy_scan_complete'],variant_attach_ok=pf.host_row(obs,'AK74')['prereq_variant']['lights'][0]['per_slot'][2]['attach_ok'],slot_verdict=slot['verdict'],reason=slot['reason'])))

for name,hook in {
 'one-line method / numeric':'class HC : CustomMission { void F(int n) { string row=""; row += n; } }',
 'one-line method / duplicate':'class HC : CustomMission { void F() { int value; int value; } }',
 'same-line next method / numeric':'class HC : CustomMission\n{\n void A() {} void F(int n) { string row=""; row += n; }\n}',
 'comment-split operators':'class HC : CustomMission\n{\n void F() { string row = '+(' +\n'.join(['"x"']*28))+'; }\n}',
 'inline control / compound':'class HC : CustomMission\n{\n void F(int n) { string row=""; if (true) row += n; }\n}',
}.items():
 print('LINT',name,json.dumps(dict(methods=len(list(rt._function_bodies(rt._clean(hook)))),max_plus=rt.max_statement_plus(hook),issues=rt.lint_hook(hook,explicit_numbers=True))))

# Only aggregate counts from the local native observations are printed; never serialize the source or report.
local=Path('/home/david/.cache/hollow-country/experiments/taped-light-probe-003')
cls=json.loads((local/'classification.json').read_text())
obs=json.loads((local/'observations.json').read_text())
result=r.build_report(cls,obs)
print('NATIVE aggregate',json.dumps(result['denominators'],sort_keys=True))
from collections import Counter
print('NATIVE pending reasons',json.dumps(dict(Counter(reason for host in result['hosts'] if host['verdict']=='pending' for reason in host['reasons'])),sort_keys=True))
hook=p.render_hook(p.select_targets(cls))
print('FULL HOOK',json.dumps(dict(bytes=len(hook),sha256=hashlib.sha256(hook).hexdigest(),max_plus=rt.max_statement_plus(hook.decode()),lint=rt.lint_hook(hook.decode(),native_types=rt.native_type_names('/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289'),explicit_numbers=True))))
