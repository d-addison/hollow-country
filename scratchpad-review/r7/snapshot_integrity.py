"""Compare scratch source inputs with read-only git archives."""
from pathlib import Path
import io,tarfile,subprocess
ROOT=Path(__file__).resolve().parent
for label,revision in [('head','c1ffaea'),('parent','0c9f4ec')]:
    data=subprocess.check_output(['git','archive',revision,'tools','tests'],cwd=ROOT.parents[1])
    diffs=[];count=0
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive.getmembers():
            if member.isfile():
                count+=1
                if (ROOT/label/member.name).read_bytes()!=archive.extractfile(member).read():diffs.append(member.name)
    print(label,revision,'files',count,'differences',diffs)
    assert not diffs
