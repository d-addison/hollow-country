"""Adapt only reviewer patterns displaced by the required fixes; disposable copies."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[2]
report = Path(__file__).resolve().parent
mutations = [
    ('C9 current whole client branch', '        if client:\n            if any(', '        if False:\n            if any(', 1),
    ('E13 unchanged-config binding guard',
     "    if (rt.sha256(config) != plan['config_treatment']['staged_sha256'] or\n            plan['config_treatment']['staged_sha256'] != plan['config_treatment']['source_sha256'] or\n            plan['config_treatment'].get('unchanged') is not True):",
     '    if False:', 1),
    ('S14 reintroduce maxPlayers rewrite in staged bytes',
     "    config = context['source']['config_bytes']",
     "    context['source']['config_bytes'] = re.sub(rb'maxPlayers\\s*=\\s*\\d+\\s*;', b'maxPlayers = 0;', context['source']['config_bytes'])\n    config = context['source']['config_bytes']", 1),
    ('H1 client-required execution skip (first occurrence only)',
     'if (m_Trial.support_state == "client_required")', 'if (false)', 2),
    ('H1/F7 client-required zero elapsed branch',
     'if (m_Trial.support_state == "client_required")\n            m_Trial.elapsed_ms = 0;',
     'if (false)\n            m_Trial.elapsed_ms = 0;', 1),
]
with tempfile.TemporaryDirectory(prefix='wp3-r2-adapted-mutations-') as temp:
    root = Path(temp)
    for name in ('tools', 'tests'):
        shutil.copytree(repo / name, root / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    module = root / 'tools/setup/infected_competence_probe.py'
    original = module.read_text()
    survivors = []
    for index, (label, old, new, expected) in enumerate(mutations):
        assert original.count(old) == expected, (label, original.count(old))
        module.write_text(original.replace(old, new, 1))
        command = [sys.executable, '-B', '-m', 'unittest', 'tests.unit.test_infected_competence']
        result = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        (report / f'adapted-mutation-{index + 1}.txt').write_text(
            label + '\n$ ' + ' '.join(command) + '\n' + result.stdout + result.stderr)
        print(label, 'KILLED' if result.returncode else 'SURVIVED', flush=True)
        if result.returncode == 0:
            survivors.append(label)
    module.write_text(original)
print('survivors:', survivors)
if survivors:
    sys.exit(1)
