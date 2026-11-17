"""Independent synthetic rerun of the earlier report scenarios plus fix-round edge cases."""
import copy,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'head'))
from tests.unit import test_taped_light_report as f
from tools.audit import taped_light_report as report

def baseline():
    c=f.classification([f.host('AK74','slot_host')])
    o=f.observations([f.row('AK74','slot_host',f.gun_slots(),f.good_gun_lights())])
    return c,o

def show(label,alter):
    c,o=baseline()
    alter(c,o)
    try:
        r=report.build_report(c,o);h=r['hosts'][0]
        light=h['lights'].get('UniversalLight',{})
        print(json.dumps({'case':label,'host':h['verdict'],'reasons':h['reasons'],'light':light.get('verdict'),
                          'light_reasons':light.get('reasons'),'pair_counts':r['denominators']['host_light_pairs'],
                          'integrity':r['integrity']['issues']},sort_keys=True))
    except Exception as e:print(json.dumps({'case':label,'exception':type(e).__name__+': '+str(e)}))

def hidden(c,o):
    o['hosts'][0]['lights'][0]['per_slot'][2]['attach_ok']=True
    o['hosts'][0]['lights'].append(copy.deepcopy(o['hosts'][0]['lights'][0]))
    o['hosts'][0]['lights'][-1]['per_slot'][2]['attach_ok']=False

def noslot(c,o):
    c['hosts'][0].update(group='no_slot_host',native_light_slots=[])
    o['hosts'][0].update(group='no_slot_host',slots=[],lights=[])

cases=[
('baseline',lambda c,o:None),
('missing TLRLight row',lambda c,o:o['hosts'][0]['lights'].pop(1)),
('missing helmet slot observation',lambda c,o:o['hosts'][0]['slots'].pop(0)),
('missing can_add field',lambda c,o:o['hosts'][0]['lights'][2]['per_slot'][2].pop('can_add')),
('conflicting host slot duplicate',lambda c,o:o['hosts'][0]['slots'].insert(0,f.slot_obs('weaponFlashlight'))),
('conflicting light duplicate',lambda c,o:o['hosts'][0]['lights'].insert(0,f.light_obs('UniversalLight',[],False))),
('conflicting per-slot duplicate',lambda c,o:o['hosts'][0]['lights'][2]['per_slot'].insert(0,f.per_slot('weaponFlashlight','UniversalLight',can_add=False,attach_ok=False))),
('three duplicate preflights',lambda c,o:o['lights'].extend([copy.deepcopy(o['lights'][2]),copy.deepcopy(o['lights'][2])])),
('wrong spawned host type',lambda c,o:o['hosts'][0].update(type='OtherHost')),
('wrong preflight type and incompatible slots',lambda c,o:o['lights'][2].update(type='OtherLight',fits_native_slots=[])),
('different config slot',lambda c,o:c['hosts'][0].update(native_light_slots=['pistolFlashlight'])),
('partial overall status',lambda c,o:o.update(status='partial')),
('dirty cleanup',lambda c,o:o['counters'].update(deleted=9,residual_probe_types=1)),
('control attaches',lambda c,o:o['hosts'][0]['lights'][0]['per_slot'][2].update(attach_ok=True)),
('control attachment hidden by duplicate',hidden),
('null host slots',lambda c,o:o['hosts'][0].update(slots=None)),
('null light per_slot',lambda c,o:o['hosts'][0]['lights'][2].update(per_slot=None)),
('no-slot host with all evidence omitted',noslot),
('can_add false but attach_ok true',lambda c,o:o['hosts'][0]['lights'][2]['per_slot'][2].update(can_add=False)),
('negative cleanup counts',lambda c,o:o['counters'].update(spawned=-1,deleted=-1,census_total=-2,census_scanned=-2)),
('control preflight wrong type',lambda c,o:o['lights'][0].update(type='OtherControl')),
('control spawned false',lambda c,o:o['hosts'][0]['lights'][0].update(spawned=False)),
('representative class omitted from classification',lambda c,o:c['lights'].pop(1)),
]
for case,alter in cases:show(case,alter)

def variant(c,o,**extra):
    row=o['hosts'][0]
    row['prereq']=f.prereq_obs('weaponHandguardAK')
    row['lights']=f.refusal_lights()
    row['prereq_variant']=f.variant_obs('weaponHandguardAK',[f.good_gun_lights()[2]])
    for key,val in extra.items():row['prereq_variant'][key]=val
show('prerequisite missing variant',lambda c,o:(variant(c,o),o['hosts'][0].update(prereq_variant={'performed':False})))
show('prerequisite variant baseline',variant)
show('prerequisite wrong handguard',lambda c,o:variant(c,o,handguard='AK_PlasticHndgrd'))
show('prerequisite wrong fit',lambda c,o:(variant(c,o),o['hosts'][0]['prereq_variant']['lights'][0]['per_slot'][2].update(light_fits=False)))
show('prerequisite missing light_fits',lambda c,o:(variant(c,o),o['hosts'][0]['prereq_variant']['lights'][0]['per_slot'][2].pop('light_fits')))
show('prerequisite variant duplicate light',lambda c,o:(variant(c,o),o['hosts'][0]['prereq_variant']['lights'].append(copy.deepcopy(o['hosts'][0]['prereq_variant']['lights'][0]))))
show('control preflight missing',lambda c,o:o['lights'].pop(0))
show('control preflight spawned false',lambda c,o:o['lights'][0].update(spawned=False))
show('control per-slot fit conflicts with preflight',lambda c,o:o['hosts'][0]['lights'][0]['per_slot'][2].update(light_fits=True))
show('control preflight duplicate',lambda c,o:o['lights'].append(copy.deepcopy(o['lights'][0])))
