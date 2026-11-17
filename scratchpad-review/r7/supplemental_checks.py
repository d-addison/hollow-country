"""Sequential supplemental reruns after source-mutating scratch checks have finished."""
from pathlib import Path
import os,subprocess,sys,json
ROOT=Path(__file__).resolve().parent
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(ROOT/'tmp'))
checks=['snapshot_integrity','closure_checks','normalization_checks','compile_audit','extended_guard_mutations','native_basename_regression','native_checks','independent_checks','compare_ce_parent','all_api_audit','qualification_checks','native_observations']
for name in checks:
    argv=[sys.executable,'-B',str(ROOT/(name+'.py'))]
    p=subprocess.run(argv,cwd=ROOT.parents[1],env=ENV,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (ROOT/(name+'.log')).write_text(p.stdout)
    print(json.dumps({'check':name,'argv':argv,'cwd':str(ROOT.parents[1]),'exit':p.returncode}),flush=True)
    print(p.stdout,flush=True)
    assert p.returncode==0,name
