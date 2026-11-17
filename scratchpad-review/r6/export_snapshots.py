"""Recreate authored tools/tests snapshots only, without modifying Git metadata."""
from pathlib import Path
import io,subprocess,tarfile
ROOT=Path(__file__).resolve().parent
(ROOT/'tmp').mkdir(exist_ok=True)
for label,revision in [('head','0c9f4ec'),('parent','691b115')]:
    destination=ROOT/label
    assert not destination.exists(),destination
    destination.mkdir()
    data=subprocess.check_output(['git','archive',revision,'tools','tests'],cwd=ROOT.parents[1])
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:archive.extractall(destination,filter='data')
    print(label,revision,'tools/tests exported')
