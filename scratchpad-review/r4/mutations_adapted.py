"""Prior 21 mutation intents on round 4. Operates only on the archived copy; restores in finally."""
import ast
import difflib
import json
import os
from pathlib import Path
import subprocess
import sys

here=Path(__file__).resolve().parent
base=here/'baseline'
all_mutations=[]
for name in ('mutate.py','mutate_new.py','mutate_round3.py'):
    scope={}
    for node in ast.parse((here/name).read_text()).body:
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('PROBE','REPORT','MUTATIONS'):
            exec(compile(ast.Module(body=[node],type_ignores=[]),name,'exec'),scope)
    all_mutations.extend(scope['MUTATIONS'])

# Equivalent sites moved with the countdown model and per-attribute label refactor.
adapt={
 'N4_drop_future_deadline_guard': ('near_end = 0 < left_a <=', 'near_end = left_a <='),
 'R1_bypass_live_application': ('ok = detail[key]["candidate_live_matches_candidate_xml"] and detail[key]["stock_live_differs_from_candidate_xml"]','ok = True'),
 'R2_ignore_stock_differential': ('ok = detail[key]["candidate_live_matches_candidate_xml"] and detail[key]["stock_live_differs_from_candidate_xml"]','ok = detail[key]["candidate_live_matches_candidate_xml"]'),
 'R3_treat_every_attribute': ('attributes = [key for key in _ATTRIBUTES if not _close(stock["xml"][key], candidate["xml"][key])]','attributes = list(_ATTRIBUTES)'),
 'R6_ignore_cycle_gate': ('if live and not candidate["cycle_observed"]:', 'if False:'),
}
results=[]
for name,relative,old,new in all_mutations:
    if name in adapt:
        old,new=adapt[name]
    path=base/relative
    original=path.read_text()
    assert original.count(old)==1,(name,original.count(old))
    mutant=original.replace(old,new)
    try:
        path.write_text(mutant)
        proc=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests/unit','-p','test_weather*.py','-v'],
                 cwd=base,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(here/'tmp')),
                 capture_output=True,text=True)
        (here/(name+'.log')).write_text(proc.stdout+proc.stderr)
        (here/(name+'.diff')).write_text(''.join(difflib.unified_diff(original.splitlines(True),mutant.splitlines(True),fromfile=relative,tofile=relative)))
        result=dict(mutation=name,exit=proc.returncode,result='SURVIVED' if proc.returncode==0 else 'KILLED',adapted=name in adapt)
        results.append(result)
        print(json.dumps(result),flush=True)
    finally:
        path.write_text(original)
(here/'mutations.json').write_text(json.dumps(results,indent=2)+'\n')
