"""Review-only in-memory minimal guards; no production implementation or native proof."""
from pathlib import Path
import json,sys,unittest
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import reproductions as repro
r=repro.r
original_model=r._model_evidence
original_slots=r._host_slots
def model_guard(host_slot,slot,proxies):
    result=original_model(host_slot,slot,proxies)
    if result[0]=='none' and proxies[0]=='ok':
        res=proxies[3]
        if res is None or not res['complete']:
            return 'pending','client_required',None
    return result
def name_guard(row,slot_names,reasons):
    result=original_slots(row,slot_names,reasons)
    entries={entry['slot']:entry for entry in row['slots']}
    for name,values in result.items():
        if values is not None and (values['selection_on_model'] or values['memory_point'] or values['bone_index']>=0):
            selection=entries[name].get('selection')
            if not isinstance(selection,str) or not selection:
                result[name]=None;reasons.add('slot_evidence_invalid')
    return result
r._model_evidence=model_guard;r._host_slots=name_guard
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in
    [repro.LegacyNameRegression,repro.UnknownIsNotNegativeRegression])
result=unittest.TextTestRunner(verbosity=2).run(suite)
cache=Path('/home/david/.cache/hollow-country/experiments')
c=json.loads((cache/'taped-light-probe-003/classification.json').read_text())
o=json.loads((cache/'taped-light-probe-006/observations.json').read_text())
changed=r.build_report(c,o)
print('PROPOSED_GUARDS_NATIVE_DENOMINATORS',json.dumps(changed['denominators'],sort_keys=True))
assert changed['denominators']['qualified']==0
sys.exit(not result.wasSuccessful())
