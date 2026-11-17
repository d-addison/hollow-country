from pathlib import Path
import hashlib
import json
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
manifest = json.loads((OUT / 'source-hashes.json').read_text())
for root in [ROOT, OUT / 'source-copy']:
    changed = [p for p, digest in manifest.items() if not (root / p).is_file() or hashlib.sha256((root / p).read_bytes()).hexdigest() != digest]
    assert not changed, (str(root), changed)
    print(f'PASS: {len(manifest)} tracked inputs unchanged: {root}')
assert not list(OUT.rglob('*.pyc'))
assert not (OUT / 'source-copy/.git').exists()
print('PASS: copy excludes .git; review artifacts contain no Python bytecode.')
