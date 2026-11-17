"""Independent synthetic edge checks; all fixtures remain in scratchpad-review/tmp."""
import copy,json,os,sys,tempfile
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'head'))
tempfile.tempdir=str(ROOT/'tmp')
from tools.setup import probe_runtime as rt,diagnostic_mission as dm,taped_light_probe as p,ce_probe as ce
from tools.audit import taped_light_report as r
from tests.unit import test_taped_light_report as f,test_taped_light_probe as pf,test_ce_probe as cf

def wrap(body,style='normal'):
    if style=='inline': return 'class HCCheck : CustomMission\n{\n    void F(int count) {\n        string row;\n'+body+'\n    }\n}\n'
    text='class HCCheck : CustomMission\n{\n    void F(int count)\n    {\n        string row;\n'+body+'\n    }\n}\n'
    if style=='crlf':text=text.replace('\n','\r\n')
    if style=='indent':text=text.replace('    void F','        void F').replace('    {\n        string','        {\n        string')
    return text

chain='        row = '+ ' + '.join(['"x"']*28)+';'
for label,body,style in [('27 plus normal',chain,'normal'),('27 plus multiline',chain.replace(' + ','\n            + '),'normal'),('27 plus inline brace',chain,'inline'),('27 plus CRLF',chain,'crlf'),('27 plus 8-space indent',chain,'indent'),('plus in literal','        row = "'+'+'*50+'";','normal'),('increments','        count++; count += 1;','normal'),('compound bare int','        row += count;','normal'),('compound with literal','        row += "n=" + count;','normal'),('parenthesized bare int','        row = "n=" + (count);','normal'),('normal bare int','        row = "n=" + count;','normal')]:
    hook=wrap(body,style)
    print('LINT '+json.dumps({'case':label,'max':rt.max_statement_plus(hook),'issues':rt.lint_hook(hook,explicit_numbers=True)},sort_keys=True))

hook=ce.render_hook(cf.targets_for(),export_delay_s=30,census_delay_s=240).decode()
print('CE_NUMBERS '+json.dumps({'max':rt.max_statement_plus(hook),'default_issues':rt.lint_hook(hook),'strict_first_three':rt.lint_hook(hook,explicit_numbers=True)[:3]},sort_keys=True))

def baseline():return f.classification([f.host('AK74','slot_host')]),f.observations([f.row('AK74','slot_host',f.gun_slots(),f.good_gun_lights())])

def show(label,alter):
    c,o=baseline();alter(c,o)
    try:
        result=r.build_report(c,o);h=result['hosts'][0]
        print('REPORT '+json.dumps({'case':label,'host':h['verdict'],'light':h['lights']['UniversalLight']['verdict'],'light_reasons':h['lights']['UniversalLight']['reasons'],'integrity':result['integrity']['issues'],'control_hits':result['control']['unexpected_attachments'],'slots':h['lights']['UniversalLight']['slots']},sort_keys=True))
    except Exception as e:print('REPORT '+json.dumps({'case':label,'exception':repr(e)}))

show('control found despite failed create',lambda c,o:o['hosts'][0]['lights'][0]['per_slot'][2].update(found_type='Flashlight'))
show('representative found despite failed create',lambda c,o:o['hosts'][0]['lights'][2]['per_slot'][2].update(can_add=False,attach_ok=False))
show('control can_add but creation failed',lambda c,o:o['hosts'][0]['lights'][0]['per_slot'][2].update(can_add=True))
show('zero spawn cleanup despite all observations',lambda c,o:o['counters'].update(spawned=0,deleted=0))
show('negative attach_ok and timeouts',lambda c,o:o['counters'].update(attach_ok=-1,timeouts=-1,residual_other=-1))

def variant(c,o):
    h=o['hosts'][0];h['prereq']=f.prereq_obs('weaponHandguardAK');h['lights']=f.refusal_lights();h['prereq_variant']=f.variant_obs('weaponHandguardAK',[f.good_gun_lights()[2]])
show('variant evidence baseline',variant)

def run_stage(label,make_patch):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);source=pf.make_source_runtime(root/'vanilla');dest=root/'taped-light-test'
        state={}
        try:
            with make_patch(root,source,dest,state):
                plan=p.stage(source,dest,pf.classification(),battleye_sha256=pf.SYNTH_BE_SHA,_wsl_parent=root)
            state['outcome']='ACCEPTED'
        except Exception as e:state['outcome']=type(e).__name__+': '+str(e)
        state.update(plan_exists=(dest/p.PLAN_NAME).exists(),symlinks=[str(x.relative_to(dest)) for x in dest.rglob('*') if x.is_symlink()])
        print('FD '+json.dumps(dict(case=label,**state),sort_keys=True))

from contextlib import ExitStack

def final_walk_swap(root,source,dest,state):
    stack=ExitStack();real_launch=rt.launcher_problems;real_child=dm._open_child_dir
    active=False;in_walk=False;done=False
    real_walk=dm.walk_plain
    def walk(*a,**kw):
        nonlocal in_walk
        in_walk=True
        try:return real_walk(*a,**kw)
        finally:in_walk=False
    def launch(*a,**kw):
        nonlocal active
        active=True
        return real_launch(*a,**kw)
    def child(fd,name):
        nonlocal done
        descriptor=real_child(fd,name)
        if active and in_walk and name=='db' and not done:
            done=True
            target=dest/'mpmissions/dayzOffline.chernarusplus/db';outside=root/'moved-db'
            target.rename(outside);target.symlink_to(outside,target_is_directory=True)
            state['swapped_during_final_walk']=True
        return descriptor
    stack.enter_context(mock.patch.object(rt,'launcher_problems',side_effect=launch))
    stack.enter_context(mock.patch.object(dm,'walk_plain',side_effect=walk))
    stack.enter_context(mock.patch.object(dm,'_open_child_dir',side_effect=child))
    return stack
run_stage('db swapped after final walk opened it',final_walk_swap)

def before_leaf_swap(root,source,dest,state):
    real_child=dm._open_child_dir;done=False
    def child(fd,name):
        nonlocal done
        descriptor=real_child(fd,name)
        # Source battleye already holds the DLL; destination battleye is empty until this first write.
        if name=='battleye' and not done and (dest/'battleye').exists() and not (dest/'battleye/BEServer_x64.dll').exists():
            done=True
            original=dest/'battleye';outside=root/'moved-write-dir'
            original.rename(outside);original.symlink_to(outside,target_is_directory=True)
            state['swapped_after_open']=True
        return descriptor
    # A context exit snapshot verifies the residual write even if staging raises.
    class C:
        def __enter__(self):self.patch=mock.patch.object(dm,'_open_child_dir',side_effect=child);self.patch.start()
        def __exit__(self,*exc):
            self.patch.stop();state['outside_written']=(root/'moved-write-dir/BEServer_x64.dll').exists()
            state['outside_bytes']=(root/'moved-write-dir/BEServer_x64.dll').stat().st_size if state['outside_written'] else 0
    return C()
run_stage('battleye moved after directory open before leaf write',before_leaf_swap)
