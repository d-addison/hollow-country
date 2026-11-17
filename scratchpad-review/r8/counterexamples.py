"""Explicit counterexamples for surviving mutations, using unmodified root imports."""
from pathlib import Path
import copy,json,sys,types
from unittest import mock
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]))
from tools.audit import taped_light_report as original
from tools.setup import taped_light_probe as p
from tests.unit import test_taped_light_report as f,test_taped_light_probe as pf
src=Path(original.__file__).read_text()
def mutant(before,after):
    assert src.count(before)==1
    mod=types.ModuleType('tools.audit.review_counterexample');mod.__file__=original.__file__
    exec(compile(src.replace(before,after),'<report-counterexample>','exec'),mod.__dict__)
    return mod
def judge(mod,item,facts=None):
    row=f.row('AK74','slot_host',f.gun_slots(weapon_model=False),f.good_gun_lights(),proxies=[item],facts=facts)
    result=mod.build_report(f.classification([f.host('AK74','slot_host')]),f.observations([row]))
    s=result['hosts'][0]['lights']['UniversalLight']['slots']['weaponFlashlight']
    return [s['verdict'],s['reason'],s['evidence'].get('resolution_vertex')]
def emit(label,value):print(label,json.dumps(value,sort_keys=True),flush=True)
for label,before,after,item,facts in [
 ('row_list_flag_disagrees_with_host','or name != lod["name"] or listed != lod["list_ok"]','or name != lod["name"]',
  f.proxy(res=[f.res_entry('0','',list_ok=False),f.res_entry('1','proxy:'+f.LIGHT_PROXY_PATH+'.001')]),
  dict(f.res_host(('0',3),('1',3)),lod_list_ok=True,lod_count=2,lod_names=['0','1'],lod_names_complete=True,view_by_name=False)),
 ('overflow','return numbers if all(math.isfinite(number) for number in numbers) else None','return numbers',f.proxy(vertex=('1e999','0','0')),None),
 ('trailing_newline','_NUMBER_TEXT.fullmatch(item)','_NUMBER_TEXT.match(item)',f.proxy(vertex=('1\n','0','0')),None),
 ('numeric_prefix_lod','not _RES_LOD_NAME.fullmatch(name) or total < 0','not _RES_LOD_NAME.match(name) or total < 0',
  f.proxy(res=[f.res_entry('1junk','proxy:'+f.LIGHT_PROXY_PATH+'.001')]),
  dict(f.res_host(('1junk',3)),lod_list_ok=True,lod_count=2,lod_names=['memory'],lod_names_complete=False,view_by_name=False)),
]:
    mod=mutant(before,after)
    emit('REPORT_COUNTEREXAMPLE',dict(case=label,baseline=judge(original,item,facts),mutant=judge(mod,item,facts)))
aliases=[f.proxy(),dict(f.proxy(),selection='proxy:'+f.LIGHT_PROXY_PATH[1:]+'.001')]
row=f.row('AK74','slot_host',f.gun_slots(weapon_model=False),f.good_gun_lights(),proxies=aliases)
mod=mutant('if known is reading:','if True:')
emit('COLLAPSE_INTERNAL',dict(baseline_rows=len(original._proxies(row)[1]),mutant_rows=len(mod._proxies(row)[1])))
# The fixture's count and index checks are correlated. Decouple them to test each guard's real purpose.
real_index=pf.ModelSelection.GetLODVertexIndex
real_count=pf.ModelSelection.GetVertexCount
def index_missing(sel,index):return -1 if 'weaponlight_universal' in str(sel.name).lower() else real_index(sel,index)
def count_missing(sel):return 0 if 'weaponlight_universal' in str(sel.name).lower() else real_count(sel)
for label,method,callback,before,after in [
 ('index_minus_one_with_positive_count','GetLODVertexIndex',index_missing,
  'matchSelection.GetVertexCount() > 0 && matchSelection.GetLODVertexIndex(0) != -1','matchSelection.GetVertexCount() > 0'),
 ('zero_count_with_valid_index','GetVertexCount',count_missing,
  'matchSelection.GetVertexCount() > 0 && matchSelection.GetLODVertexIndex(0) != -1','matchSelection.GetLODVertexIndex(0) != -1'),
]:
    results=[]
    render=p.render_hook
    for change in [False,True]:
        world=pf.World(types=pf.proxy_types())
        def render_mutant(*a,**kw):
            text=render(*a,**kw).decode();assert text.count(before)==1
            return text.replace(before,after).encode()
        try:
            with mock.patch.object(pf.ModelSelection,method,callback),mock.patch.object(p,'render_hook',render_mutant if change else render):
                pf.run_hook(world,slots=pf._NoSelectionSlots)
            joined=original.build_report(pf.classification(),pf.observations_of(world))
            s=next(x for x in joined['hosts'] if x['class']=='AK74')['lights']['UniversalLight']['slots']['weaponFlashlight']
            results.append([s['verdict'],s['reason']])
        except Exception as exc:results.append(type(exc).__name__+': '+str(exc))
    emit('HOOK_COUNTEREXAMPLE',dict(case=label,baseline=results[0],mutant=results[1]))
