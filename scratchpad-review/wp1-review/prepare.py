from pathlib import Path
import hashlib
import json
import shutil
import subprocess
ROOT = Path.cwd()
OUT = ROOT / 'scratchpad-review/wp1-review'
paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', '92cbffc'], text=True).splitlines()
manifest = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}
(OUT / 'source-hashes.json').write_text(json.dumps(manifest, indent=2) + '\n')
shutil.copytree(ROOT, OUT / 'source-copy', ignore=shutil.ignore_patterns('.git', 'scratchpad-review', '__pycache__'))
print(f'Copied {len(manifest)} tracked source inputs; excluded .git and recursive scratch artifacts.')
