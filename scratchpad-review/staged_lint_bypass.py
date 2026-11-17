"""Show the expression-check bypass reaches the real stager, using only a synthetic mission."""
import json,sys,tempfile
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'head'));tempfile.tempdir=str(ROOT/'tmp')
from tools.setup import taped_light_probe as p,probe_runtime as rt
from tests.unit import test_taped_light_probe as f
real=p.render_hook

def render(*a,**kw):
    text=real(*a,**kw).decode()
    index=text.rfind('}')
    extra='    void HCReviewComplexity() {\n        string row = '+' + '.join(['"x"']*28)+';\n    }\n'
    return (text[:index]+extra+text[index:]).encode()
with tempfile.TemporaryDirectory() as td:
    root=Path(td);source=f.make_source_runtime(root/'vanilla');dest=root/'taped-light-test'
    hook=render(p.select_targets(f.classification()))
    print('bad_hook_max_statement_plus=',rt.max_statement_plus(hook.decode()))
    print('bad_hook_lint=',rt.lint_hook(hook.decode(),explicit_numbers=True))
    with mock.patch.object(p,'render_hook',side_effect=render):
        result=p.stage(source,dest,f.classification(),battleye_sha256=f.SYNTH_BE_SHA,_wsl_parent=root)
    print('stage_status=',result['status'],'plan_exists=',(dest/p.PLAN_NAME).exists())
