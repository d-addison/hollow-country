"""Verify authored snapshots and actual generated hook after all mutation runs."""
from pathlib import Path
import hashlib,io,json,re,subprocess,sys,tarfile
ROOT=Path(__file__).resolve().parent
for label,rev in [('head','182db38'),('parent','73241f6')]:
    data=subprocess.check_output(['git','archive',rev,'tools','tests'],cwd=ROOT.parents[1])
    diffs=[];count=0
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive.getmembers():
            if member.isfile():
                count+=1
                if (ROOT/label/member.name).read_bytes()!=archive.extractfile(member).read():diffs.append(member.name)
    print('SNAPSHOT',label,rev,'files',count,'differences',diffs)
    assert not diffs
sys.path.insert(0,str(ROOT/'head'))
from tools.setup import taped_light_probe as p,probe_runtime as rt
from tests.unit import test_script_syntax as syn
cache=Path('/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289')
c=json.loads(Path('/home/david/.cache/hollow-country/experiments/taped-light-probe-003/classification.json').read_text())
hook=p.render_hook(p.select_targets(c)).decode()
prototypes=syn.native_prototypes(cache)
print('OVERRIDES',re.findall(r'\boverride\s+\w+\s+(\w+)\(([^)]*)\)',rt._clean(hook)))
print('ONINIT_INSTALLED_PROTOTYPES',sorted(prototypes.get('OnInit',())))
print('FULL_LINT',rt.lint_hook(hook,native_types=rt.native_type_names(cache),prototypes=prototypes,explicit_numbers=True))
print('LEADING_LOGICAL_OPERATORS',len(re.findall(r'^\s*(?:\|\||&&)',rt._clean(hook),re.M)))
print('HOOK_IDENTITY',len(hook.encode()),hashlib.sha256(hook.encode()).hexdigest())
print('TRACKED_DIFF',repr(subprocess.check_output(['git','diff','--no-ext-diff','--stat'],cwd=ROOT.parents[1],text=True)))
