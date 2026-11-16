# Conservative CE coverage candidate preparation

C05 / T010–T012 / FR-003–004 / AC-003–004. Offline implementation, not an
apartment or barracks fix. No real geometry or native eligibility is invented.

`tools/package/coverage.py` consumes the exact stock prototype bytes, a complete
diagnostic export, explicit changed group names, exact build/world and hashed
observation artifacts. It rejects source/export drift, missing/tampered evidence,
unrequested edits, category/usage changes, deleted/modified existing points,
unknown groups/containers, duplicate points, nonfinite/out-of-bounds local
coordinates, unsafe paths, external entities and excessive lootmax changes.
Only requested group nodes are replaced in a stock-derived full-file candidate.
Unchanged XML is preserved semantically, not byte-for-byte formatting.

This follows the actual installed `mapgroupproto.xml` group/container/point XML
surface already audited in EXP-CE-offline-audit.md. It deliberately does not
claim that CE supports modular prototype overrides. A fresh review directory
receives candidate XML and a hash/provenance report; no mission is installed.
Hashes establish artifact identity, not the truth of a claimed observation.

TDD command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_coverage_patch.py -v
```

Actual initial RED: test import failed with `ImportError: cannot import name
'coverage' from 'tools.package'`; one failed discovery test. After implementing
the module, the initial six behavioral tests passed. Additional point metadata,
XML declaration and duplicate-group regressions extend those checks.

Independent review CR-02 reproduced a UTF-16 internal-entity bypass in the shared
XML loader. The new regression failed for UTF-16, little-endian and big-endian
inputs before the fix. The loader now decodes UTF-8 (optional BOM) before checking
declarations and rejects NULs and other encodings. All nine coverage tests and
nine economy tests pass after the correction. No external disclosure was shown.

Native acceptance still needs a genuine official export, measured house/point
geometry, supported isolated mission installation, eligibility and collision
trials, unchanged world budgets, CE logs and paired performance controls. There
is no real-map point data in the synthetic tests and no default CE patch.
