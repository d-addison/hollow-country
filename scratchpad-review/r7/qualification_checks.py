"""Independent synthetic qualification probes, plus read-only native duplicate diagnosis."""
from pathlib import Path
import sys,json,copy,tempfile
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]))
tempfile.tempdir=str(ROOT/'tmp')
from tests.unit import test_taped_light_probe as p,test_taped_light_report as f
from tools.audit import taped_light_report as r

def judge(observations, name='AK74', classification=None):
    result=r.build_report(classification or p.classification(),observations)
    host=next(h for h in result['hosts'] if h['class']==name)
    light='TLRLight' if name.startswith('FNX') else 'UniversalLight'
    slot='pistolFlashlight' if name.startswith('FNX') else 'weaponFlashlight'
    return host['lights'][light]['slots'][slot],result

for label,changes,config in [
 ('positive',{},None),('no_view',{'view':None},None),('no_config',{},{}),
 ('bare_only',{}, {'CfgNonAIVehicles weaponlight_universal':{'model':'/dz/weapons/attachments/light/weaponlight_universal.p3d','inventorySlot':['weaponFlashlight']}}),
 ('wrong_lod_names',{'lods':('VIEW_PILOT','geometryView','1.000')},None),
 ('failed_view_list',{'view_unlisted':True},None),('failed_lod_list',{'lods_unlisted':True},None),
 ('over_128_lods',{'lods':tuple('res%d'%n for n in range(129))},None),
]:
    types=p.proxy_types();types['AK74'].update(changes)
    world=p.World(types=types,config=config);p.run_hook(world,slots=p._NoSelectionSlots)
    observations=p.observations_of(world);slot,result=judge(observations)
    row=p.host_row(observations,'AK74')
    print('SYNTHETIC',json.dumps({'case':label,'view_lod':row['view_lod'],'lod_list_ok':row['lod_list_ok'],'cfg_exists':row['proxies'][0]['cfg_exists'],'cfg_tried_exists':row['proxies'][0]['cfg_tried_exists'],'verdict':slot['verdict'],'reason':slot['reason'],'live':len(world.live())},sort_keys=True))
    assert slot['verdict']==('qualified' if label=='positive' else 'pending')
    assert not world.live()
    before={k:copy.deepcopy(result[k]) for k in ['denominators','integrity','acceptance','unobserved_axes']}
    for diag in [None,[],{'string_self_test':3},{'string_self_test':{'sample':'bad','last_slash':999}}, {'cfg_nonai_scan':{'child_count':-1,'scanned':999,'complete':True,'proxy_named':999,'weaponlight_children':[]}}]:
        changed=copy.deepcopy(observations);changed['diagnostics']=diag
        after=r.build_report(p.classification(),changed)
        assert all(after[k]==v for k,v in before.items()),(label,diag)
print('HEADER_DIAGNOSTICS 8 scenarios x 5 malformed/changed headers: verdict aggregates, integrity and acceptance unchanged')

world=p.World(types=p.catalogue(),config={})
p.run_hook(world)
obs=p.observations_of(world)
slot,_=judge(obs)
row=p.host_row(obs,'AK74')
print('CURRENT_HOOK_SELECTION_ROUTE',json.dumps({'view_lod':row['view_lod'],'proxy_rows':len(row['proxies']),'verdict':slot['verdict'],'reason':slot['reason'],'live':len(world.live())},sort_keys=True))
assert slot['verdict']=='qualified' and not row['view_lod'] and not row['proxies'] and not world.live()

for flag in ['selection_on_model','memory_point','bone_index']:
    slots=f.gun_slots(weapon_model=False)
    slots[2][flag]=0 if flag=='bone_index' else True
    row=f.row('AK74','slot_host',slots,f.good_gun_lights())
    slot,result=judge(f.observations([row]),classification=f.classification([f.host('AK74','slot_host')]))
    print('LEGACY_ROUTE',json.dumps({'evidence':flag,'proxy_keys_present':'proxies' in row,'verdict':slot['verdict'],'reason':slot['reason']},sort_keys=True))
    assert slot['verdict']=='qualified'

local=Path('/mnt/d/HollowCountryLocal/taped-light-probe-005/profiles/HCTapedLightProbe/observations.json')
obs=json.loads(local.read_text())
cls=json.loads(Path('/home/david/.cache/hollow-country/experiments/taped-light-probe-003/classification.json').read_text())
for name in ['FNX45','FNX45_arrow']:
    host=next(h for h in obs['hosts'] if h['class']==name)
    slots_before,_=judge(obs,name,cls)
    seen={};duplicates=[];unique=[]
    for entry in host['proxies']:
        key=r._proxy_name(entry['selection'])
        if key in seen:
            a={k:v for k,v in seen[key].items() if k not in ['selection','sep_slash','sep_backslash']}
            b={k:v for k,v in entry.items() if k not in ['selection','sep_slash','sep_backslash']}
            duplicates.append({'identity':key,'lookups_equal':a==b,'raw_separator_counts':[(seen[key]['sep_slash'],seen[key]['sep_backslash']),(entry['sep_slash'],entry['sep_backslash'])]})
        else:seen[key]=entry;unique.append(entry)
    altered=copy.deepcopy(obs)
    h=next(h for h in altered['hosts'] if h['class']==name)
    h['proxies']=unique;h['proxy_count']=len(unique)
    slot_after,_=judge(altered,name,cls)
    print('NATIVE_DUPLICATE_DIAGNOSIS',json.dumps({'class':name,'duplicates':duplicates,'before':[slots_before['verdict'],slots_before['reason']],'after_synthetic_dedup':[slot_after['verdict'],slot_after['reason']]},sort_keys=True))
    assert all(d['lookups_equal'] for d in duplicates)
    assert slot_after['verdict']=='pending' and slot_after['reason']=='view_lod_absent_on_server'
