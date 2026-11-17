"""Print all conflict orders and failed-enumeration combinations as explicit synthetic evidence."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parent/'head'))
from tests.unit import test_taped_light_report as f
from tools.audit import taped_light_report as r

def judge(entries,view=None):
    row=f.row('AK74','slot_host',f.gun_slots(weapon_model=False),f.good_gun_lights(),proxies=entries)
    if view is not None:row.update(view)
    result=r.build_report(f.classification([f.host('AK74','slot_host')]),f.observations([row]))
    slot=result['hosts'][0]['lights']['UniversalLight']['slots']['weaponFlashlight']
    return {'verdict':slot['verdict'],'reason':slot['reason'],'qualified':result['denominators']['qualified']}
for label,second in [('missing_selection',dict(f.proxy(number='002'),view_selection='',view_vertex_ok=False,view_vertex=[])),('vertex',f.proxy(number='002',vertex=('10','20','30'))),('selection',f.proxy(number='002',view_selection='proxy:'+f.LIGHT_PROXY_PATH+'.002')),('flag',dict(f.proxy(number='002'),view_vertex_ok=False))]:
    for reverse in [False,True]:
        entries=[f.proxy(),second]
        if reverse:entries.reverse()
        result=judge(entries)
        print('CONFLICT',json.dumps({'case':label,'reverse':reverse,**result},sort_keys=True))
        assert result=={'verdict':'pending','reason':'proxy_evidence_malformed','qualified':0}
view=dict(f.VIEW_HOST,view_list_ok=False,view_scan_complete=False,view_selection_count=0)
for label,changes,entry,wanted in [('failed',{},f.proxy(view_selection='',vertex_ok=False),'view_enumeration_failed'),('false_with_count',{'view_selection_count':3},f.proxy(view_selection='',vertex_ok=False),'proxy_evidence_malformed'),('false_with_selection',{},f.proxy(),'proxy_evidence_malformed'),('false_with_complete',{'view_scan_complete':True},f.proxy(view_selection='',vertex_ok=False),'proxy_evidence_malformed')]:
    result=judge([entry],dict(view,**changes));print('ENUMERATION',json.dumps({'case':label,**result},sort_keys=True))
    assert result=={'verdict':'pending','reason':wanted,'qualified':0}
