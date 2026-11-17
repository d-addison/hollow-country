"""Review-only scratch copies; no game, native source copies, or repository edits."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORLD = Path('mods/HollowCountry/scripts/4_World')
P = WORLD / 'Interiors/HCInteriorPathgraph.c'
M = WORLD / 'Interiors/HCInteriorModule.c'
N = WORLD / 'Infected/HCInfectedNavigation.c'
V = WORLD / 'Infected/HCInfectedNative.c'
OWN = 'foreach (Object ownedObject : created) m_Objects.Insert(ownedObject);'
CALL = 'HCInteriorPathgraph.Schedule(created);'
SUPER = 'super.ProcessSoundVoiceEvent(sound_event, aw);'


def replace_once(text, old, new):
    assert text.count(old) == 1, (old, text.count(old))
    return text.replace(old, new, 1)


MUTANTS = [
    ('baseline', None, '', ''),
    ('a1_remove_schedule', M, CALL, ''),
    ('a1_raise_cap', P, 'MAX_OBJECTS = 8;', 'MAX_OBJECTS = 800;'),
    ('a1_wrong_delay', P, 'DELAY_MS = 100;', 'DELAY_MS = 1000;'),
    ('a1_repeat_updates', P, 'DELAY_MS, false, placedObject', 'DELAY_MS, true, placedObject'),
    ('a1_no_server_guard', P, ' || !GetGame().IsServer()', ''),
    ('a1_no_null_prop_guard', P, 'if (!placedObject) continue;', ''),
    ('a1_dead_schedule_branch', M, CALL, 'if (false) { ' + CALL + ' }'),
    ('a1_return_before_schedule', M, OWN, OWN + '\n        return;'),
    ('a1_remove_rollback_return', M, 'Print("[HC Interiors] partial layout rolled back; no search site");\n                return;', 'Print("[HC Interiors] partial layout rolled back; no search site");'),
    ('a1_queue_reused_props', M, 'if (object) created.Insert(object);\n            }', '}\n            if (object) created.Insert(object);'),
    ('a17_enable_visual_sampling', N, 'static bool VisualSamplingAvailable()\n    {\n        return false;', 'static bool VisualSamplingAvailable()\n    {\n        return true;'),
    ('a17_invert_visual_gate', N, 'if (!visualObserved)', 'if (visualObserved)'),
    ('a17_noise_target', V, SUPER, SUPER + '\n        if (GetGame().IsServer() && sound_event.m_NoiseParams) GetGame().GetNoiseSystem().AddNoiseTarget(GetPosition(), 1, sound_event.m_NoiseParams);'),
    ('c4_remove_super', V, SUPER, ''),
    ('c4_conditional_super', V, SUPER, 'if (GetGame().IsServer()) { ' + SUPER + ' }'),
    ('c4_super_after_adapter', V, SUPER, 'HCInfectedModule.Instance.NativeVoice(this, sound_event);\n        ' + SUPER),
]


def digest():
    paths = sorted((ROOT / 'mods').rglob('*')) + sorted((ROOT / 'tests/unit').glob('*.py'))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths if p.is_file()}


before = digest()
results = []
for name, relative, old, new in MUTANTS:
    dest = HERE / 'mutants-validated' / name
    if dest.exists():
        raise SystemExit('Fresh scratch destination required: ' + str(dest))
    shutil.copytree(ROOT / 'mods', dest / 'mods')
    (dest / 'tests/unit').mkdir(parents=True)
    for filename in ('test_native_wiring_batch_a.py', 'test_alert_chain.py', 'test_horde_stimulus.py', 'test_infected_contract.py'):
        shutil.copy2(ROOT / 'tests/unit' / filename, dest / 'tests/unit' / filename)
    if relative is not None:
        path = dest / relative
        path.write_text(replace_once(path.read_text(), old, new))
    command = ['python3', '-m', 'unittest', 'discover', '-s', 'tests/unit',
               '-p', 'test_native_wiring_batch_a.py', '-v']
    proc = subprocess.run(command, cwd=dest, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output = proc.stdout.replace(str(Path.home()), '~')
    (dest / 'focused.log').write_text(output)
    if relative is None and proc.returncode:
        raise SystemExit('Baseline failed; mutation results invalid. See baseline/focused.log')
    result = {'id': name, 'file': str(relative) if relative else None,
              'old': old, 'new': new, 'exit': proc.returncode,
              'outcome': ('PASS' if relative is None else 'SURVIVED') if proc.returncode == 0 else 'KILLED',
              'failed_tests': [line for line in output.splitlines() if line.startswith(('FAIL:', 'ERROR:'))]}
    results.append(result)
    print(name + ': ' + result['outcome'], flush=True)

assert before == digest(), 'Source tree changed during review'
(HERE / 'mutation-results.json').write_text(json.dumps(results, indent=2) + '\n')
(HERE / 'source-sha256.json').write_text(json.dumps(before, indent=2) + '\n')
