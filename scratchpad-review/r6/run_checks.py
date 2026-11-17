"""Run confined r5 reproductions against the reviewed snapshot."""
from pathlib import Path
import os,subprocess,sys,json
ROOT=Path(__file__).resolve().parent
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(ROOT/'tmp'))
checks=[('focused-tests',[sys.executable,'-B','-m','unittest','tests.unit.test_probe_runtime','tests.unit.test_ce_probe','tests.unit.test_diagnostic_mission','tests.unit.test_flashlight_matrix','tests.unit.test_taped_light_probe','tests.unit.test_taped_light_report','-v'],ROOT/'head')]
checks.extend((name,[sys.executable,'-B',str(ROOT/(name+'.py'))],ROOT.parents[1]) for name in ['view_regressions','red_regressions','new_red_regressions','remaining_regressions','mutations','new_mutations','guard_mutations','native_api_audit','deep_checks','residual_race'])
for name,argv,cwd in checks:
    result=subprocess.run(argv,cwd=cwd,env=ENV,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (ROOT/(name+'.log')).write_text(result.stdout)
    print(json.dumps({'check':name,'argv':argv,'cwd':str(cwd),'exit':result.returncode}),flush=True)
    if name=='focused-tests':
        print('\n'.join(line for line in result.stdout.splitlines() if line.startswith(('Ran ','FAILED','OK'))),flush=True)
    else: print(result.stdout,flush=True)
