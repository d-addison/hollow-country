"""Recreate unchanged authored test inputs; temporary files stay outside this copy."""
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for rel in ['tools', 'tests/unit', 'tests/features', 'tests/fixtures/runtime',
            'mods/HollowCountry/scripts/4_World/Infected']:
    shutil.copytree(ROOT / rel, HERE / 'isolated-source' / rel,
                    ignore=shutil.ignore_patterns('__pycache__'), dirs_exist_ok=True)
print('Copied unchanged authored inputs into scratch only; no native/game assets or git metadata copied.')
