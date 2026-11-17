"""Run the real CLI using an immutable scratch export, then retain only aggregate evidence."""
from pathlib import Path
import json,hashlib,collections,subprocess,sys,os
ROOT=Path(__file__).resolve().parent
CACHE=Path('/home/david/.cache/hollow-country/experiments/taped-light-probe-003')
RUNTIME=Path('/mnt/d/HollowCountryLocal/taped-light-probe-005')
OBS=RUNTIME/'profiles/HCTapedLightProbe/observations.json'
SENTINEL=RUNTIME/'profiles/HCTapedLightProbe/complete.txt'
if not OBS.exists() or not SENTINEL.exists():
    print('NATIVE_UNAVAILABLE',{'observations':OBS.exists(),'sentinel':SENTINEL.exists()});sys.exit(0)
OUT=ROOT/'native-report.json'
assert not OUT.exists()
argv=[sys.executable,'-B','-m','tools.audit.taped_light_report','--classification',str(CACHE/'classification.json'),'--observations',str(OBS),'--out',str(OUT)]
run=subprocess.run(argv,cwd=ROOT/'head',env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(ROOT/'tmp')),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(ROOT/'native-cli.log').write_text(run.stdout)
print('COMMAND',' '.join(argv),'cwd',ROOT/'head','exit',run.returncode)
print(run.stdout.strip())
assert run.returncode==0
try:
    raw=OBS.read_bytes();o=json.loads(raw);r=json.loads(OUT.read_text())
    print('SENTINEL',SENTINEL.read_text().strip())
    print('OBSERVATIONS',json.dumps({'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'status':o['status'],'observed':o['observed'],'counters':o['counters']},sort_keys=True))
    print('NATIVE_DIAGNOSTICS',json.dumps(r['native_diagnostics'],sort_keys=True))
    hosts=[h for h in o['hosts'] if h.get('spawned')]
    for key in ['view_lod','view_list_ok','view_scan_complete','view_selection_count','proxy_count','proxy_scan_complete']:
        print('HOST_FIELD',key,json.dumps(dict(collections.Counter(str(h.get(key,'MISSING')) for h in hosts)),sort_keys=True))
    rows=[(h,x) for h in hosts for x in h.get('proxies',[])]
    print('PROXY_ROWS',json.dumps({'hosts_with_rows':sum(bool(h.get('proxies')) for h in hosts),'rows':len(rows),'nonempty_view':sum(bool(x.get('view_selection')) for _,x in rows),'vertex_ok':sum(x.get('view_vertex_ok') is True for _,x in rows),'cfg_exists':sum(x.get('cfg_exists') is True for _,x in rows)},sort_keys=True))
    for key in ['sep_slash','sep_backslash']:
        print('SEPARATORS',key,json.dumps(dict(collections.Counter(str(x.get(key)) for _,x in rows)),sort_keys=True))
    print('LOD_NAMES',json.dumps([{'names':k,'hosts':v} for k,v in collections.Counter(tuple(h.get('lod_names',[])) for h in hosts).items()],sort_keys=True))
    for key in ['lod_list_ok','lod_count','lod_names_complete','view_by_name']:
        print('HOST_FIELD',key,json.dumps(dict(collections.Counter(str(h.get(key,'MISSING')) for h in hosts)),sort_keys=True))
    tried=collections.Counter((tuple(x.get('cfg_tried',[])),tuple(x.get('cfg_tried_exists',[]))) for _,x in rows)
    print('CFG_TRIED',json.dumps([{'names':k[0], 'exists':k[1], 'rows':v} for k,v in sorted(tried.items())],sort_keys=True))
    print('DENOMINATORS',json.dumps(r['denominators'],sort_keys=True))
    print('INTEGRITY',json.dumps(r['integrity'],sort_keys=True))
    print('ACCEPTANCE',r['acceptance'],json.dumps(r['unobserved_axes'],sort_keys=True))
    print('PENDING_REASONS',json.dumps(dict(collections.Counter(reason for h in r['hosts'] if h['verdict']=='pending' for reason in h['reasons'])),sort_keys=True))
    print('SLOT_REASONS',json.dumps(dict(collections.Counter(s['reason'] for h in r['hosts'] for l in h.get('lights',{}).values() for s in l.get('slots',{}).values())),sort_keys=True))
    sys.path.insert(0,str(ROOT/'head'))
    from tools.setup import taped_light_probe as p
    from tools.audit import taped_light_report as report
    full=p.render_hook(p.select_targets(json.loads((CACHE/'classification.json').read_text())))
    init=(RUNTIME/'mpmissions/dayzOffline.chernarusplus/init.c').read_bytes()
    print('HOOK_IDENTITY',json.dumps({'bytes':len(full),'sha256':hashlib.sha256(full).hexdigest(),'present_exactly_in_native_init':full in init,'native_init_bytes':len(init),'native_init_sha256':hashlib.sha256(init).hexdigest()},sort_keys=True))
    print('PROXY_PARSE_KINDS',json.dumps(dict(collections.Counter(report._proxies(h)[0] for h in hosts)),sort_keys=True))
    for name in ['AK74','Glock19','FNX45','FNX45_arrow']:
        host=next(h for h in hosts if h['class']==name)
        item=next(x for x in host['proxies'] if 'weaponlight' in x['selection'])
        print('BAD_CONFIG_IDENTITY',json.dumps({'class':name,**{k:item[k] for k in ['selection','cfg_class','cfg_exists','model']}},sort_keys=True))
        if name.startswith('FNX'):
            print('DUPLICATE_SELECTIONS', name, json.dumps([x['selection'] for x in host['proxies']]))
finally:OUT.unlink()
