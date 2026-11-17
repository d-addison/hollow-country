"""Explicit synthetic paths exercised through the actual generated-hook model and report."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'head'))
from tests.unit import test_taped_light_probe as f
from tools.audit import taped_light_report as r

def run(label,selection,model=None,ordinary=None):
    types=f.proxy_types()
    types['AK74']['view']=('components',selection)
    if ordinary is not None: types['AK74']['proxies']=(ordinary,)
    cfg=f.proxy_config()
    if model is not None: cfg['CfgNonAIVehicles Proxyweaponlight_universal']['model']=model
    world=f.World(types=types,config=cfg)
    hook=f.run_hook(world,slots=f._NoSelectionSlots)
    obs=f.observations_of(world)
    host=f.host_row(obs,'AK74');item=host['proxies'][0]
    result=r.build_report(f.classification(),obs)
    host_result=next(h for h in result['hosts'] if h['class']=='AK74')
    slot=host_result['lights']['UniversalLight']['slots']['weaponFlashlight']
    print(json.dumps({'case':label,'view_input':selection,'model_input':cfg['CfgNonAIVehicles Proxyweaponlight_universal']['model'],
        'cfg_class':item['cfg_class'],'cfg_exists':item['cfg_exists'],'emitted_view':item['view_selection'],
        'hook_view_path':str(hook.HCTLViewPath(hook.HCTLViewKey(f.S(selection)))),
        'report_view_path':r._view_path(selection),'verdict':slot['verdict'],'reason':slot['reason'],'live':len(world.live())},sort_keys=True),flush=True)
    return slot

base='/dz/weapons/attachments/light/weaponlight_universal'
cases=[('normal', 'proxy:'+base+'.001',None,'qualified'),
       ('case_slashes','PROXY:'+base.upper().replace('/','\\')+'.007',None,'qualified'),
       ('view_repeated_separator','proxy:'+base.replace('/attachments/','/attachments//')+'.001',None,'pending'),
       ('model_repeated_separator','proxy:'+base+'.001',base.replace('/attachments/','/attachments//')+'.p3d','pending'),
       ('both_repeated_separator','proxy:'+base.replace('/attachments/','/attachments//')+'.001',base.replace('/attachments/','/attachments//')+'.p3d','qualified'),
       ('view_trailing_slash','proxy:'+base+'/.001',None,'pending'),
       ('both_trailing_slash','proxy:'+base+'/.001',base+'/.p3d','pending'),
       ('longer_model','proxy:'+base+'_extra.001',None,'pending'),
       ('no_prefix',base+'.001',None,'pending')]
for label,selection,model,wanted in cases:
    assert run(label,selection,model)['verdict']==wanted,label
# Native-shaped ordinary selection: exact backward-slash bytes are explicit synthetic input.
slot=run('raw_ordinary_backslashes','proxy:'+base+'.001',ordinary='proxy:'+base.replace('/','\\')+'.001')
assert slot['verdict']=='qualified'  # round 6 defect is now fixed
