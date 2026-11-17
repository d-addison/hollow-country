import shutil, subprocess, sys, os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
HERE = Path(__file__).resolve().parent; BASE = HERE/'base'
C='mods/HollowCountry/scripts/4_World/Crafting/'
S=C+'HCSalvageRecipe.c'; D=C+'HCItemUtilityDiagnostic.c'
M=[('M10c add LeatherGloves_Black + count 8', S, [('if (index == 6) return "LeatherHat_Beige";','if (index == 6) return "LeatherHat_Beige"; if (index == 7) return "LeatherGloves_Black";'),('if (seed == "HCRecoverMediumLeather") return 7;','if (seed == "HCRecoverMediumLeather") return 8;')]),
 ('M14 server check dropped (full)', S, [('if (!GetGame().IsServer())\n            return;','')]),
 ('D20 m_Execute gate dropped (full)', D, [('!m_Execute || ','')]),
 ('D04 SafeConcrete allow all (full)', D, [('if (root != "CfgVehicles")\n            return false;','return true;')])]
def one(m):
    name,f,reps=m; w=HERE/('wf_'+name.split()[0]); 
    if w.exists(): shutil.rmtree(w)
    shutil.copytree(BASE,w); p=w/f; t=p.read_text()
    for a,b in reps:
        assert a in t, a
        t=t.replace(a,b,1)
    p.write_text(t)
    r=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests/unit'],cwd=w,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True)
    fails=[l.split(' (')[0] for l in r.stderr.splitlines() if l.startswith(('FAIL:','ERROR:'))][:2]
    shutil.rmtree(w)
    return '%s %s %s'%(name,'SURVIVED' if r.returncode==0 else 'killed',fails)
with ThreadPoolExecutor(2) as ex:
    for l in ex.map(one,M): print(l,flush=True)
