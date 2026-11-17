"""Distinguish coverage gaps from a mutant still contained by independent validation."""
import importlib.util
import json
from pathlib import Path
import subprocess
import os
import sys
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
CHILD='''import importlib.util,sys,unittest
import tools.audit
name='tools.audit.taped_light_report'
spec=importlib.util.spec_from_file_location(name,sys.argv[1])
mod=importlib.util.module_from_spec(spec)
sys.modules[name]=mod
spec.loader.exec_module(mod)
tools.audit.taped_light_report=mod
spec=importlib.util.spec_from_file_location('adversarial',sys.argv[2])
tests=importlib.util.module_from_spec(spec)
sys.modules['adversarial']=tests
spec.loader.exec_module(tests)
if sys.argv[3]=='identity_guard':
    from tests.unit import test_taped_light_report as t
    classification=t.classification([t.host('Base','slot_host'),t.host('Base_Red','slot_host')])
    observations=t.observations([t.row('Base','slot_host',t.gun_slots(),t.good_gun_lights())])
    result=mod.build_report(classification,observations)
    record=t.by_class(result,'Base_Red')
    print(record['verdict'],record['reasons'])
    assert record['verdict']=='pending'
    sys.exit(0)
suite=unittest.defaultTestLoader.loadTestsFromName('adversarial.AdversarialTests.'+sys.argv[3])
result=unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
'''
results=[]
for ident,test in [('B00','test_unknown_case_slots_do_not_implicate_native_slot'),
                   ('M03','test_unknown_case_slots_do_not_implicate_native_slot'),
                   ('B00','test_class_spelling_alone_collapses'),
                   ('M08','test_class_spelling_alone_collapses'),
                   ('B00','identity_guard'),('M07','identity_guard')]:
    p=subprocess.run([sys.executable,'-c',CHILD,str(OUT/'mutants'/ident/'taped_light_report.py'),
                      str(OUT/'test_adversarial.py'),test],cwd=ROOT,
                     env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT)),
                     text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (OUT/('survivor-'+ident+'-'+test+'.log')).write_text(p.stdout)
    results.append(dict(id=ident,test=test,returncode=p.returncode,output=p.stdout))
(OUT/'survivor-results.json').write_text(json.dumps(results,indent=2)+'\n')
for r in results:
    print(r['id'],r['test'],'PASS' if r['returncode']==0 else 'FAIL')
