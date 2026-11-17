"""Re-run the three probe fixture faults identified in the prior review, writing only here."""
import concurrent.futures
import importlib.util
import json
from pathlib import Path
OUT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('writer_mutations',OUT.parent/'r9-fix'/'mutations.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.OUT=OUT
cases=[('Q'+case[0][1:],*case[1:]) for case in m.CASES if case[0] in ('P08','P09','P10')]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    records=list(pool.map(m.run,cases))
(OUT/'probe-mutation-results.json').write_text(json.dumps(records,indent=2)+'\n')
