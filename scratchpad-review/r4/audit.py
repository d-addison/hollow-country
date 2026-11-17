from pathlib import Path
import sys,json,hashlib,runpy
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.setup import interior_sampler as s,probe_runtime as rt
from tests.unit import test_interior_sampler as m
OUT=Path(__file__).resolve().parent
plan=json.loads(Path('/home/david/.cache/hollow-country/experiments/interior-sampler-002/interior-sampler-plan.json').read_bytes())
limits={k:plan['sampler'][k] for k in ('hit_limit','step_limit','building_ray_limit','run_ray_limit','path_limit','output_limit','intersect')}
limits['sample_delay_s']=plan['probe']['sample_delay_s']
for name,targets,kwargs in [('fixture',m.sampler_targets(),{}),('archive-targets',plan['targets'],limits)]:
 hook=s.render_hook(targets,**kwargs)
 (OUT/(name+'-hook.c')).write_bytes(hook)
 native=rt.native_type_names(Path('/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289'))
 print(name,'sha256',hashlib.sha256(hook).hexdigest(),'bytes',len(hook))
 print('shared lint:',rt.lint_hook(hook.decode(),native_types=native))
 print('sampler lint:',s.lint_sampler_hook(hook.decode(),native_types=native))
