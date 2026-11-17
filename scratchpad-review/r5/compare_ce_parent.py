"""Compare literal bytes for synthetic CE inputs using isolated git snapshots."""
import datetime,importlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
TMP=ROOT/'tmp'/'ce-parent-comparison'
TMP.mkdir(exist_ok=True)

def modules(version):
    for name in list(sys.modules):
        if name=='tools' or name.startswith('tools.') or name=='tests' or name.startswith('tests.'):
            del sys.modules[name]
    sys.path[:]=[str(ROOT/version)]+[p for p in sys.path if p not in (str(ROOT/'head'),str(ROOT/'parent'))]
    return tuple(importlib.import_module(n) for n in ('tools.setup.ce_probe','tools.setup.diagnostic_mission','tests.unit.test_ce_probe'))

old=modules('parent')
public={name:sorted(k for k in vars(m) if not k.startswith('_')) for name,m in zip(('ce_probe','diagnostic_mission','test_ce_probe'),old)}
new=modules('head')
for label,m in zip(public,new):
    missing=sorted(set(public[label])-set(vars(m)))
    print('PUBLIC',label,'baseline_count=',len(public[label]),'missing=',missing)
print('MAX_HOOK_BYTES=',new[1].MAX_HOOK_BYTES)
print('test helpers=',[n for n in public['test_ce_probe'] if callable(getattr(new[2],n)) and not n[0].isupper()])
source=TMP/'vanilla'
new[2].make_source_runtime(source)
treatment=TMP/'treatment.xml'
treatment.write_bytes(new[2].TREATMENT_PROTO)
now=datetime.datetime(2026,11,17,0,0,tzinfo=datetime.timezone.utc)
for mode in ('control','treatment'):
    outputs=[]
    dest=TMP/'ce-probe-test'
    for version in ('parent','head'):
        ce,dm,fixture=modules(version)
        kwargs={'now':now,'battleye_sha256':fixture.SYNTH_BE_SHA,'_wsl_parent':TMP}
        if mode=='treatment': kwargs['treatment_mapgroupproto']=treatment
        ce.stage(source,dest,**kwargs)
        outputs.append({p.relative_to(dest).as_posix():p.read_bytes() for p in dest.rglob('*') if p.is_file()})
        shutil.rmtree(dest)
    a,b=outputs
    names=set(a)|set(b)
    different=[n for n in sorted(names) if a.get(n)!=b.get(n)]
    print('BYTE-COMPARE',mode,'files=',len(a),len(b),'differences=',different)
    for n in different:
        if n.endswith('.json'):
            print(n,'parsed_equal=',json.loads(a[n])==json.loads(b[n]))
