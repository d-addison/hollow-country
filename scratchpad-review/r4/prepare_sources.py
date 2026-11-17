"""Recreate review-only copies under r4; no git metadata is copied or changed."""
from pathlib import Path
import shutil,subprocess
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
count=0
for raw in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).split(b'\0'):
 if not raw:continue
 name=raw.decode();src=ROOT/name
 if not src.is_file():continue
 dst=HERE/'source-copy'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst);count+=1
(HERE/'tmp').mkdir(exist_ok=True)
print('Copied tracked source files:',count)
