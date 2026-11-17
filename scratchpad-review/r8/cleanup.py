"""Remove only generated authored exports and synthetic staging fixtures for this review."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parent
assert ROOT.name=='r8' and ROOT.parent.name=='scratchpad-review'
for name in ['head','parent','tmp']:
    path=ROOT/name
    if path.exists():shutil.rmtree(path)
print('Removed head, parent and tmp under scratchpad-review/r8; scripts, reports and logs retained.')
