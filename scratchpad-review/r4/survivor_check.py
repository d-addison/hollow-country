from pathlib import Path
import sys,unittest,io,contextlib
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE/'source-copy'))
from tools.setup import interior_sampler as s
from tests.unit import test_interior_sampler as st,test_interior_points as pt
src=Path(s.__file__).read_text()
def flatten(suite):
 for t in suite:
  if isinstance(t,unittest.TestSuite):yield from flatten(t)
  else:yield t
def run(label):
 suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (st,pt))
 suite=unittest.TestSuite(t for t in flatten(suite) if not t.id().endswith('test_every_mutated_condition_is_detected'))
 stream=io.StringIO()
 with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):r=unittest.TextTestRunner(stream=stream).run(suite)
 (HERE/(label+'.log')).write_text(stream.getvalue())
 print(label,'tests',r.testsRun,'failures',len(r.failures),'errors',len(r.errors))
run('all-interior-baseline')
old='if (result == 0)\n            return false;\n        return true;'
new='if (result <= 0)\n            return false;\n        return true;'
assert src.count(old)==1
exec(compile(src.replace(old,new,1),s.__file__,'exec'),s.__dict__)
run('all-interior-unknown-ray-clear')
