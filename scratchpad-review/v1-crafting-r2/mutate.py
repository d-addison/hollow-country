"""Reapply review mutations to fresh copies of this fix; never alter worktree."""
import ast, concurrent.futures, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path.cwd(); OUT=ROOT/'scratchpad-review/v1-crafting-r2'
tree=ast.parse((ROOT/'scratchpad-review/v1-crafting-sonnet-review/mut/run.py').read_text())
mods=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MODS' for t in n.targets)) if False else None
# Evaluate only constant path and list assignments, not the review runner body.
env={}
for n in tree.body:
    if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('C','S','D','MODS','SUBSET') for t in n.targets):
        exec(compile(ast.Module(body=[n],type_ignores=[]),'<review-constants>','exec'),env)
selected={'M14','D04','A03'}|{f'D{i:02}' for i in range(7,22)}
mods=[m for m in env['MODS'] if m[0].split()[0] in selected]
# P3 hoisted this expression; preserve D07's semantic charset removal.
mods=[(name,path,'if (!alphabet.Contains(character))' if name.startswith('D07 ') else old,new) for name,path,old,new in mods]
subset=env['SUBSET']
files=subprocess.check_output(['git','ls-files','-z'],text=True).split('\0')
files=[f for f in files if f and not f.startswith(('scratchpad-review/','.banso')) and (ROOT/f).is_file()]

def run(mutation=None):
    with tempfile.TemporaryDirectory(prefix='hc-crafting-r2-') as folder:
        w=Path(folder)
        for name in files:
            to=w/name;to.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,to)
        name='BASELINE'
        if mutation:
            name,path,old,new=mutation;p=w/path;text=p.read_text()
            if old not in text:raise AssertionError('missing mutation pattern '+name)
            p.write_text(text.replace(old,new,1))
        result=subprocess.run([sys.executable,'-B','-m','unittest',*subset],cwd=w,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True)
        output=result.stdout+result.stderr
        ident=name.split()[0];(OUT/(ident+'.log')).write_text(output)
        failures=[s for s in output.splitlines() if s.startswith(('FAIL:','ERROR:','Ran ','OK','FAILED'))]
        status=('GREEN' if result.returncode==0 else 'RED') if not mutation else ('survived' if result.returncode==0 else 'killed')
        report=dict(id=ident,name=name,status=status,returncode=result.returncode,results=failures)
        print(json.dumps(report),flush=True)
        return report

baseline=run()
if baseline['returncode']:sys.exit('baseline failed')
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    results=list(pool.map(run,mods))
(OUT/'mutant-results.json').write_text(json.dumps(results,indent=2)+'\n')
if any(r['status']!='killed' for r in results):sys.exit(1)
