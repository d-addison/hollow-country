"""Independent single-fault mutants, imported from scratch; original modules untouched."""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / 'tools/audit/taped_light_report.py'
CHILD = '''import importlib.util,sys,unittest
import tools.audit
name='tools.audit.taped_light_report'
spec=importlib.util.spec_from_file_location(name,sys.argv[1])
mod=importlib.util.module_from_spec(spec)
sys.modules[name]=mod
spec.loader.exec_module(mod)
tools.audit.taped_light_report=mod
suite=unittest.defaultTestLoader.loadTestsFromNames(['tests.unit.test_taped_light_report','tests.unit.test_taped_light_probe'])
def leaves(s):
    for t in s:
        if isinstance(t,unittest.TestSuite): yield from leaves(t)
        elif '.CliTests.' not in t.id() and '.StagerTests.' not in t.id(): yield t
result=unittest.TextTestRunner().run(unittest.TestSuite(leaves(suite)))
sys.exit(not result.wasSuccessful())
'''
# Each case is independent and must match exactly once in current source.
CASES = [
 ('M01','drop all proxy rows after the second (late contradiction ignored)',
  '    for entry in entries:\n        values = _proxy_row(entry, res)',
  '    for entry in entries[:2]:\n        values = _proxy_row(entry, res)'),
 ('M02','forget conflicts between distinct instances of one config class',
  'elif lookups.setdefault(klass, (lookup, name))[0] != lookup:',
  'elif False:'),
 ('M03','casefold conflict slot names (widens conflict scope)',
  'slot in conflict["slots"]',
  'slot.casefold() in {name.casefold() for name in conflict["slots"]}'),
 ('M04','hide truncated conflicting copies when the first copy was complete',
  'conflict["all"] = conflict["all"] or lookup[3] > len(lookup[2])',
  'conflict["all"] = lookup[3] > len(lookup[2])'),
 ('M05','allow proxy model mismatch to qualify',
  'if not item["cfg_exists"] or _path(item["model"]) != item["path"]:',
  'if not item["cfg_exists"]:'),
 ('M06','qualify missing per-light native observation',
  'if light_entry is MISSING:\n        return _pending("light_not_observed")',
  'if light_entry is MISSING:\n        return {"verdict":"server_qualified", "reasons":[], "slots":{}}'),
 ('M07','borrow the first observed host row for every missing concrete variant',
  'rows_by_class.get(entry["name"], []) if entry["group"] != "excluded" else []',
  'rows_by_class.get(entry["name"], rows[:1]) if entry["group"] != "excluded" else []'),
 ('M08','compare config-class identity with case-sensitive spelling',
  'klass = values["cfg_class"].casefold()',
  'klass = values["cfg_class"]'),
 ('M09','return every coherent alias as a separate evidence row',
  'if first and name not in conflict["names"]',
  'if name not in conflict["names"]'),
]


def run(case):
    key,description,before,after=case
    src=SOURCE.read_text()
    assert src.count(before)==1,(key,src.count(before))
    folder=OUT/'mutants'/key
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/'taped_light_report.py'
    path.write_text(src.replace(before,after))
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT),TMPDIR=str(folder))
    proc=subprocess.run([sys.executable,'-c',CHILD,str(path)],cwd=ROOT,env=env,text=True,
                        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
    (folder/'output.log').write_text(proc.stdout)
    record=dict(id=key,description=description,result='KILLED' if proc.returncode else 'SURVIVED',
                returncode=proc.returncode,summary=[line for line in proc.stdout.splitlines()
                    if line.startswith(('Ran ','FAILED','OK','FAIL:','ERROR:'))])
    print(json.dumps(record),flush=True)
    return record

if __name__=='__main__':
    baseline=OUT/'mutants'/'B00'
    baseline.mkdir(parents=True,exist_ok=True)
    (baseline/'taped_light_report.py').write_text(SOURCE.read_text())
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT),TMPDIR=str(baseline))
    p=subprocess.run([sys.executable,'-c',CHILD,str(baseline/'taped_light_report.py')],cwd=ROOT,env=env,
                     text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
    (baseline/'output.log').write_text(p.stdout)
    assert p.returncode==0,p.stdout
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        records=list(pool.map(run,CASES))
    (OUT/'mutation-results.json').write_text(json.dumps(records,indent=2)+'\n')
