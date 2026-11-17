"""Re-create immutable review inputs under this scratch directory, without writing git metadata."""
import io,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
(ROOT/'tmp').mkdir(exist_ok=True)
for target,revision in [('base','76678fe'),('parent','fb05ff1'),('head','06e00be')]:
    destination=ROOT/target
    destination.mkdir(exist_ok=True)
    archive=subprocess.check_output(['git','archive',revision],cwd=ROOT.parent)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        source.extractall(destination,filter='data')
    print(target,revision,'exported')
