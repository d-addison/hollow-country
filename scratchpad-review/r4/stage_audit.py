from pathlib import Path
import sys,hashlib
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source-copy'))
from tests.unit import test_interior_sampler as m
from tools.setup import interior_sampler as s
case=m.SamplerWorkspace();case.setUp()
try:
 plan=case.stage(native_scripts=Path('/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289'))
 hook=s.render_hook(plan['targets'])
 init=(case.dest/'mpmissions/dayzOffline.chernarusplus/init.c').read_bytes()
 tail=init[init.index(b'\n\n// Hollow Country DISPOSABLE'):]
 print('Synthetic stage, current shared runtime; status:',plan['status'])
 print('Rendered hook:',len(hook),hashlib.sha256(hook).hexdigest())
 print('Staged hook:',len(tail),hashlib.sha256(tail).hexdigest())
 print('Byte-identical:',hook==tail,'plan hash matches:',plan['probe']['hook_sha256']==hashlib.sha256(hook).hexdigest())
 print('Launcher problems:',case.launcher_problems(plan,'interior-sampler-plan.json'))
finally:case.doCleanups()
