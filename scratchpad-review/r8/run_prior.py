"""Run carried reproductions and compile/API checks, confined to scratch."""
from pathlib import Path
import os, subprocess, json
ROOT=Path(__file__).resolve().parent
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(ROOT/'tmp'))
for name in ['red_regressions','new_red_regressions','remaining_regressions','residual_race',
             'compile_audit','native_checks','all_api_audit','extended_guard_mutations']:
    argv=['python3','-B',str(ROOT/(name+'.py'))]
    run=subprocess.run(argv,cwd=ROOT.parents[1],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (ROOT/(name+'.log')).write_text(run.stdout)
    print(json.dumps(dict(argv=argv,exit=run.returncode)),flush=True)
    print('\n'.join(x for x in run.stdout.splitlines() if x.startswith(('Ran ','FAILED','OK','AUDIT','EXTERNAL','{','native_'))),flush=True)
