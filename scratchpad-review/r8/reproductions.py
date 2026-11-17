"""Independent explicit synthetic fixtures; assertions never establish DayZ behavior."""
from pathlib import Path
import copy,json,sys,unittest
from unittest import mock
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'head'))
from tools.setup import taped_light_probe as p,probe_runtime as rt
from tools.audit import taped_light_report as r
from tests.unit import test_taped_light_probe as pf,test_taped_light_report as f

def judge(items, facts=None, slots=None):
    row=f.row('AK74','slot_host',slots or f.gun_slots(weapon_model=False),f.good_gun_lights(),proxies=items,facts=facts)
    result=r.build_report(f.classification([f.host('AK74','slot_host')]),f.observations([row]))
    slot=result['hosts'][0]['lights']['UniversalLight']['slots']['weaponFlashlight']
    return [slot['verdict'],slot['reason']]

def emit(name, value): print(name,json.dumps(value,sort_keys=True),flush=True)

class NativeNullRegression(unittest.TestCase):
    def test_unavailable_lod_is_unknown_without_invoking_null_instance(self):
        original=pf.ModelLod.GetSelections
        def selections(lod,out):
            if lod.entity.GetType()=='AK74':
                raise RuntimeError("SYNTHETIC null/unavailable LOD instance was dereferenced")
            return original(lod,out)
        def truth(lod): return lod.entity.GetType()!='AK74'
        world=pf.World(types=pf.proxy_types())
        # Engine-reported name is available; script instance is unavailable, as the archive's VM error reports.
        with mock.patch.object(pf.ModelLod,'__bool__',truth,create=True),mock.patch.object(pf.ModelLod,'GetSelections',selections):
            pf.run_hook(world,slots=pf._NoSelectionSlots)
        obs=pf.observations_of(world)
        self.assertFalse(any(l['list_ok'] for l in pf.host_row(obs,'AK74')['res_lods']))

class LegacyNameRegression(unittest.TestCase):
    def test_model_evidence_requires_the_name_the_producer_queried(self):
        for flag in ['selection_on_model','memory_point','bone_index']:
            with self.subTest(flag=flag):
                slots=f.gun_slots(weapon_model=False);slots[2][flag]=0 if flag=='bone_index' else True
                slots[2]['selection']=''
                self.assertNotEqual('qualified',judge(None,slots=slots)[0])

class UnknownIsNotNegativeRegression(unittest.TestCase):
    def test_failed_resolution_listing_is_unknown_even_without_a_candidate_proxy(self):
        facts=dict(f.res_host(dict(name='1',list_ok=False,selection_count=0,scan_complete=False)),
                   lod_list_ok=True,lod_count=1,lod_names=['1'],lod_names_complete=True,view_by_name=False)
        for items in [[],[f.proxy('/dz/weapons/attachments/optics/optic_acog',slots=('weaponOptics',),
                                res=[f.res_entry('1','',list_ok=False)])]]:
            with self.subTest(proxies=len(items)):
                self.assertEqual('pending',judge(items,facts)[0])

def carried():
    for label, second in [('selection',f.proxy(number='002',res_selection='proxy:'+f.LIGHT_PROXY_PATH+'.002')),
                          ('missing',f.proxy(number='002',res_selection='')),
                          ('vertex',f.proxy(number='002',vertex=('10','20','30'))),
                          ('flag',dict(f.proxy(number='002'),res_lods=[f.res_entry(selection='proxy:'+f.LIGHT_PROXY_PATH+'.001',vertex_ok=False)]))]:
        for reverse in [False,True]:
            items=[f.proxy(),second]
            if reverse: items.reverse()
            v=judge(items); emit('CONFLICT',dict(case=label,reverse=reverse,result=v))
            assert v==['pending','proxy_evidence_malformed']
    for label, changes in [('normal',{}),('backslashes',{'proxies':(pf.LIGHT_UNIVERSAL_PROXY.replace('/','\\'),)}),
                            ('failed_with_populated_array',{'res_unlisted':True}),
                            ('different_whole_path',{'res':('proxy:/dz/weapons/attachments/light/weaponlight_universal_extra.001',)}),
                            ('one_sided_repeated_separator',{'res':('proxy:/dz/weapons//attachments/light/weaponlight_universal.001',)}),
                            ('both_repeated_separator',{'res':('proxy:/dz/weapons//attachments/light/weaponlight_universal.001',)})]:
        types=pf.proxy_types();types['AK74'].update(changes)
        config=pf.proxy_config()
        if label=='both_repeated_separator':config['CfgNonAIVehicles Proxyweaponlight_universal']['model']='/dz/weapons//attachments/light/weaponlight_universal.p3d'
        world=pf.World(types=types,config=config);pf.run_hook(world,slots=pf._NoSelectionSlots)
        obs=pf.observations_of(world);h=pf.host_row(obs,'AK74')
        result=r.build_report(pf.classification(),obs)
        s=next(x for x in result['hosts'] if x['class']=='AK74')['lights']['UniversalLight']['slots']['weaponFlashlight']
        emit('HOOK_CASE',dict(case=label,result=[s['verdict'],s['reason']],lods=h['res_lods'],cfg=h['proxies'][0]['cfg_class'],live=len(world.live())))
        assert not world.live()
    for flag in ['selection_on_model','memory_point','bone_index']:
        slots=f.gun_slots(weapon_model=False);slots[2][flag]=0 if flag=='bone_index' else True
        emit('LEGACY_ROUTE',dict(flag=flag,result=judge(None,slots=slots)))
        # Demonstrate current report does not check the claimed selection's name (an inherited weakness).
        slots[2]['selection']=''
        emit('LEGACY_EMPTY_NAME',dict(flag=flag,result=judge(None,slots=slots)))
    world=pf.World(types=pf.catalogue(),config={});pf.run_hook(world)
    obs=pf.observations_of(world);joined=r.build_report(pf.classification(),obs)
    s=next(x for x in joined['hosts'] if x['class']=='AK74')['lights']['UniversalLight']['slots']['weaponFlashlight']
    emit('CURRENT_HOOK_LEGACY',dict(result=[s['verdict'],s['reason']],res_lods=pf.host_row(obs,'AK74')['res_lods'],proxies=pf.host_row(obs,'AK74')['proxies'],live=len(world.live())))
    # Same-named LODs are distinct ordered entries; do not deduplicate by name.
    lods=[dict(name='0',list_ok=False,selection_count=0,scan_complete=False),dict(name='0',list_ok=True,selection_count=3,scan_complete=True)]
    facts=dict(f.res_host(*lods),lod_list_ok=True,lod_count=2,lod_names=['0','0'],lod_names_complete=True,view_by_name=False)
    item=f.proxy(res=[f.res_entry('0','',list_ok=False),f.res_entry('0','proxy:'+f.LIGHT_PROXY_PATH+'.001')])
    emit('DUPLICATE_LOD_POSITIVE',judge([item],facts));assert judge([item],facts)[0]=='qualified'
    item['res_lods'].reverse();emit('DUPLICATE_LOD_SWAPPED',judge([item],facts))
    for label,hook in [('one_line','class HC : CustomMission { void F() { int v; int v; } }'),
                       ('second_method','class HC : CustomMission\n{\n void A() {} void F(int n) { string row=""; row += n; }\n}'),
                       ('inline_control','class HC : CustomMission\n{\n void F(int n) { string row=""; if (true) row += n; }\n}')]:
        emit('LINT_LIMIT',dict(case=label,methods=len(list(rt._function_bodies(rt._clean(hook)))),issues=rt.lint_hook(hook,explicit_numbers=True)))

if __name__=='__main__':
    if '--null-red' in sys.argv or '--null-fixed' in sys.argv:
        if '--null-fixed' in sys.argv:
            original_render=p.render_hook
            def fixed_render(*args,**kwargs):
                text=original_render(*args,**kwargs).decode()
                before='                    selectionsListed = scanLod.GetSelections(lodSelections);'
                after='                    selectionsListed = false;\n                    if (scanLod)\n                        selectionsListed = scanLod.GetSelections(lodSelections);'
                assert text.count(before)==1
                return text.replace(before,after).encode()
            p.render_hook=fixed_render
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(NativeNullRegression)
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        sys.exit(not result.wasSuccessful())
    elif '--legacy-red' in sys.argv:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(LegacyNameRegression))
        sys.exit(not result.wasSuccessful())
    elif '--unknown-red' in sys.argv:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(UnknownIsNotNegativeRegression))
        sys.exit(not result.wasSuccessful())
    else: carried()
