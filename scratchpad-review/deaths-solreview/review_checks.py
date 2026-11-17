"""Offline reviewer checks. Every fixture and mutation is confined to this directory."""
import contextlib
import copy
import hashlib
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'tests/unit')]
os.environ['TMPDIR'] = str(OUT / 'tmp')
sys.dont_write_bytecode = True
p = importlib.import_module('tools.setup.death_selection_probe')
t = importlib.import_module('test_death_selection_probe')
d = importlib.import_module('test_infected_death_selection')
h = importlib.import_module('test_infected_contract')
syntax = importlib.import_module('test_script_syntax')

def safe(text):
    return text.replace(str(Path.home()), '~')

def record(name, value):
    print(name + ': ' + json.dumps(value, sort_keys=True))

interfaces = {n: '\n'.join(v).encode() for n,v in p.INTERFACES.items()}
policy = (d.POLICY).read_bytes()
req = t.request()
files = p.generate_probe(t.STOCK, req, interfaces, run_id='a'*32)
legacy_text = subprocess.run(['git', 'show', 'HEAD:tools/setup/death_selection_probe.py'], cwd=ROOT, check=True, capture_output=True).stdout
legacy_path = OUT / 'legacy_probe.py'
legacy_path.write_bytes(legacy_text)
spec = importlib.util.spec_from_file_location('legacy_death_probe', legacy_path)
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
old = legacy.generate_probe(t.STOCK, req, interfaces, run_id='a'*32)
record('legacy_exact_bundle_identity', {name: files[name] == old[name] for name in files})
record('legacy_hashes', {name: hashlib.sha256(value).hexdigest() for name,value in files.items()})

native = p.inspect_interfaces(Path.home() / '.cache/hollow-country/native-scripts/scripts-1.30.164289')
record('real_installed_interface_generation', len(p.generate_probe(t.STOCK, dict(req, selection='policy'), native, run_id='a'*32, policy_source=policy)))
policy_files = p.generate_probe(t.STOCK, dict(req, selection='policy'), interfaces, run_id='a'*32, policy_source=policy)

def validate(row):
    return p.validate_receipt(json.dumps(row).encode(), policy_files, outer_timed_out=False, outer_elapsed_seconds=80)['status']

# Data mutants: internally contradictory observations, not actual native runs.
row = t.policy_receipt(p, policy_files)
for c in row['cases']:
    c['command_elapsed'] = c['delete_elapsed'] - .01
record('receipt_late_command_only_10ms_observation', validate(row))
row = t.policy_receipt(p, policy_files)
for c in row['cases']:
    for s in c['samples']:
        s['death_processed'] = 0
record('receipt_death_never_processed', validate(row))
row = t.policy_receipt(p, policy_files)
for c in row['cases']:
    c['samples'][-1]['frame'] = c['command_frame']
    c['delete_frame'] = c['command_frame'] + 2
record('receipt_no_later_sample_frame', validate(row))

# Production policy path is an authored source path; inherited _read refuses it.
try:
    p._read(d.POLICY, p.MAX_POLICY_BYTES)
except ValueError as exc:
    record('cli_read_production_policy_from_checkout', str(exc))

# Exercise CLI exclusivity with a scratch-only input-reader stub. This is necessary
# because production's mission reader refuses all fixtures inside the checkout.
# It preserves bounded bytes while bypassing ONLY the external-mission-path rule.
# Exercise CLI exclusivity on synthetic interfaces; no process launch.
cli = OUT / 'cli_fixture'
cli.mkdir(exist_ok=True)
(cli / 'init.c').write_bytes(t.STOCK)
(cli / 'policy.c').write_bytes(policy)
# Repeated reviewer runs must also stage into a fresh fixture directory.
if (cli/'stage').exists():
    import shutil
    shutil.rmtree(cli/'stage')
for name, blob in interfaces.items():
    path = cli / 'native' / name
    path.parent.mkdir(exist_ok=True, parents=True)
    path.write_bytes(blob)
original_read = p._read
def scratch_read(path, limit):
    path = Path(path).resolve()
    assert OUT in path.parents
    blob = path.read_bytes()
    assert 0 < len(blob) <= limit
    return blob
p._read = scratch_read
with contextlib.redirect_stdout(io.StringIO()):
    p.main(['--stock-init', str(cli/'init.c'), '--interfaces', str(cli/'native'), '--destination', str(cli/'stage'),
            '--victim', '100', '100', '--source', '102', '100', '--policy-source', str(cli/'policy.c'), '--run-id', 'a'*32])
p._read = original_read
m = json.loads((cli/'stage'/p.MARKER).read_bytes())
record('cli_policy_source_without_selection', {'cases': m['cases'], 'policy_staged': (cli/'stage'/p.POLICY).exists()})

# Real Python primitive input types cannot inject code into numeric vectors/enumerated strings.
rejected = []
for key,value in [('spawn_profile', 'surface-only\"); Print(\"INJECT\"); //'), ('selection', 'policy\nclass X {}'),
                  ('victim_position', ['100\"; Print(\"INJECT\");',10,100]), ('source_position',[float('nan'),10,100])]:
    try:
        p.generate_probe(t.STOCK, dict(req, **{key:value}), interfaces, run_id='a'*32)
    except ValueError:
        rejected.append(key)
record('request_injection_rejected', rejected)

# Parse packed stored PBO independently, including lengths and trailing checksum.
blob = p.pack_addon(policy_files)
import struct
pos=21
while True:
    end=blob.index(b'\0',pos); key=blob[pos:end]; pos=end+1
    if not key: break
    end=blob.index(b'\0',pos); val=blob[pos:end]; pos=end+1
    assert (key,val)==(b'prefix',b'HCDeathSelectionProbe')
entries=[]
while True:
    end=blob.index(b'\0',pos); name=blob[pos:end]; pos=end+1
    words=struct.unpack_from('<5I',blob,pos);pos+=20
    if not name: break
    assert words[:4]==(0,0,0,0)
    entries.append((name.decode().replace('\\','/'),words[4]))
for name,size in entries:
    assert blob[pos:pos+size]==policy_files['addon/'+name]
    pos+=size
assert blob[pos]==0 and hashlib.sha1(blob[:pos]).digest()==blob[pos+1:]
record('independent_pbo_parse', {'entries':len(entries),'payload_bytes':pos,'checksum_ok':True})

# Focused baseline: run shipped tests, redirect tests' temp files into permitted scratch.
classes=[t.DeathSelectionTests,t.DeathSelectionExtensionTests,d.SelectionPolicyTests,d.ProductionSourceContractTests,d.AuditDocumentTests,syntax.ScriptSyntaxBehavior]
def run_tests(classes, exclude_cli=False):
    suite=unittest.TestSuite()
    for cls in classes:
        for test in unittest.defaultTestLoader.loadTestsFromTestCase(cls):
            if exclude_cli and test._testMethodName == 'test_cli_stages_from_installed_interfaces_without_executing_anything':
                continue
            suite.addTest(test)
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=1).run(suite)
    return result,safe(stream.getvalue())
result,log=run_tests(classes)
(OUT/'focused.log').write_text(log)
record('focused_baseline',{'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)})

# Each source mutant is a complete scratch copy. The production files never change.
source_policy=d.POLICY.read_text()
source_death=d.DEATH.read_text()
source_probe=Path(p.__file__).read_text()
mutants=[
 ('policy_front_90', 'policy', 'return 60.0;', 'return 90.0;'),
 ('policy_ignore_finisher', 'policy', 'if (finisher)', 'if (false)'),
 ('policy_ignore_ammo_heavy', 'policy', 'ammoHitAnimation > 0', 'ammoHitAnimation > 100'),
 ('policy_overwrite_native', 'policy', 'nativeType != DayZInfectedDeathAnims.ANIM_DEATH_DEFAULT', 'nativeType < 0'),
 ('production_reverse_server_guard','death','if (!GetGame().IsServer())','if (GetGame().IsServer())'),
 ('production_reverse_admission','death','if (!HCInfectedDeathQualification.Admitted())','if (HCInfectedDeathQualification.Admitted())'),
 ('production_invert_heavy_input','death','ammoHitAnimation, m_HeavyHitOverride, data.m_DamageZone','ammoHitAnimation, !m_HeavyHitOverride, data.m_DamageZone'),
 ('probe_wrong_surface_flags','probe','"surface-only": "ECE_PLACE_ON_SURFACE"','"surface-only": "ECE_INITAI"'),
 ('probe_allow_side_policy_receipt','probe','POLICY_FRONT_HALF_ANGLE = 60','POLICY_FRONT_HALF_ANGLE = 180'),
 ('packer_bad_entry_length','probe','0, 0, 0, 0, len(entries[name])','0, 0, 0, 0, len(entries[name])+1'),
 ('probe_alter_legacy_ce_guard','probe','if (!ce) return;','if (ce == null) return;'),
]
summary=[]
original_source=h.SOURCE
for name,kind,before,after in mutants:
    directory=OUT/'mutants'/name
    directory.mkdir(parents=True,exist_ok=True)
    pp=directory/'HCInfectedDeathPolicy.c'; dp=directory/'HCInfectedDeath.c'; module_path=directory/'death_selection_probe.py'
    text={'policy':source_policy,'death':source_death,'probe':source_probe}[kind]
    assert text.count(before)==1,(name,text.count(before))
    pp.write_text(text.replace(before,after) if kind=='policy' else source_policy)
    dp.write_text(text.replace(before,after) if kind=='death' else source_death)
    d.POLICY=pp;d.DEATH=dp;h.SOURCE=directory
    selected=[d.SelectionPolicyTests,d.ProductionSourceContractTests] if kind!='probe' else [t.DeathSelectionTests,t.DeathSelectionExtensionTests]
    if kind=='probe':
        module_path.write_text(text.replace(before,after))
        ms=importlib.util.spec_from_file_location('tools.setup.death_selection_probe',module_path)
        mutant=importlib.util.module_from_spec(ms);ms.loader.exec_module(mutant)
        sys.modules['tools.setup.death_selection_probe']=mutant
    result,log=run_tests(selected, exclude_cli=True)
    (directory/'focused.log').write_text(log)
    status='KILLED' if result.failures or result.errors else 'SURVIVED'
    item={'name':name,'status':status,'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)}
    summary.append(item);record('mutant',item)
    d.POLICY=Path(ROOT/'mods/HollowCountry/scripts/4_World/Infected/HCInfectedDeathPolicy.c')
    d.DEATH=Path(ROOT/'mods/HollowCountry/scripts/4_World/Infected/HCInfectedDeath.c')
    h.SOURCE=original_source
    sys.modules['tools.setup.death_selection_probe']=p
(OUT/'mutations.json').write_text(json.dumps(summary,indent=2)+'\n')
