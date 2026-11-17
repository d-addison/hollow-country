"""Confirm surviving report mutants against every focused consumer, sequentially."""
from pathlib import Path
import os,json,subprocess
ROOT=Path(__file__).resolve().parent
mods=['tests.unit.test_probe_runtime','tests.unit.test_ce_probe','tests.unit.test_diagnostic_mission',
      'tests.unit.test_flashlight_matrix','tests.unit.test_taped_light_probe','tests.unit.test_taped_light_report']
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(ROOT/'tmp'))
for rec in json.loads((ROOT/'mutations.json').read_text()):
    if rec['exit'] or rec['file']!='tools/audit/taped_light_report.py':continue
    path=ROOT/'head'/rec['file'];source=path.read_text()
    try:
        assert source.count(rec['before'])==1
        path.write_text(source.replace(rec['before'],rec['after']))
        argv=['python3','-B','-m','unittest',*mods,'-q']
        result=subprocess.run(argv,cwd=ROOT/'head',env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    finally:path.write_text(source)
    (ROOT/'mutation-logs'/(rec['name']+'-full.log')).write_text(result.stdout)
    print(json.dumps(dict(name=rec['name'],argv=argv,exit=result.returncode,
          summary=[x for x in result.stdout.splitlines() if x.startswith(('Ran ','FAILED','OK'))])),flush=True)
