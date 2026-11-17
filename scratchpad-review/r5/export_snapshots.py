"""Re-create immutable compatibility inputs inside r5, without writing git metadata.

Default: only tools/tests. --discovery also exports the complete authored HEAD
tree. Do not rerun broad discovery: its synthetic Git fixtures violate this
review's no-Git-write constraint, and checkout guards prevent full completion.
"""
import io
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parent
(ROOT / 'tmp').mkdir(exist_ok=True)
for label, revision in (('base', '76678fe'), ('parent', '509d47b'), ('head', '691b115')):
    destination = ROOT / label
    destination.mkdir(exist_ok=True)
    data = subprocess.check_output(['git', 'archive', revision, 'tools', 'tests'], cwd=ROOT.parents[1])
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(destination, filter='data')
    print(label, revision, 'tools/tests exported')
if '--discovery' in sys.argv:
    destination = ROOT / 'discovery'
    destination.mkdir(exist_ok=True)
    data = subprocess.check_output(['git', 'archive', '691b115'], cwd=ROOT.parents[1])
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(destination, filter='data')
    print('full authored 691b115 exported; synthetic Git tests must not be run')
