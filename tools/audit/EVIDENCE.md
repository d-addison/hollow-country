# CE audit TDD evidence

Scope: T0 offline validation with Python standard-library unittest. All source
edits are within `tools/audit/**`, `tests/unit/test_ce_audit.py` and
`tests/fixtures/ce/**`. Namespace packages require no shared `__init__.py` edits.
Tests create/clean temporary synthetic missions under `tests/fixtures/ce/`.

Command used for each suite run, always with bytecode writes disabled:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_ce_audit.py -v
```

1. Tests and synthetic fixtures were written before `ce_audit.py` existed.
   A syntax typo in the test file was corrected before recording the baseline.
   [red.txt](evidence/red.txt): **31 tests, 31 errors**, each missing
   `tools.audit.ce_audit`. No implementation existed at this point.
2. The first implementation passed all 31 tests. Review then identified five
   additional failure cases; new tests were added before their fixes.
   [red-review.txt](evidence/red-review.txt): **36 tests, 4 failures and 1 error**.
   Failures covered partial coverage totals, protecting unaudited declared files,
   failed-source status and unresolvable mission paths.
3. After those fixes, [green.txt](evidence/green.txt): **36 tests passed**.
   This includes subprocess CLI tests for determinism, unknown catalogs, output
   preservation, invalid reports, usage failures and bytecode suppression.

Coverage also includes every required missing/malformed XML input, invalid roots,
duplicates, negative/noninteger/nonfinite counts, min/nominal ordering, quantity
sentinels, flags, point/placement vectors and dimensions, rotations, unresolved
aliases, modular discovery and non-merging of other CE kinds, path containment,
provenance changes, relocation stability, source/node/depth/byte limits and
UTF-8/UTF-16 DTD rejection.

The final CLI smoke run is stored at
[synthetic-report.json](evidence/synthetic-report.json). It uses only the
clearly synthetic fixtures and optional synthetic catalog; its zero-point
warning is expected. Output hashes cover exact fixture bytes, not the tool's
source or an installed game build.

No DayZ engine, game scripts, production mission changes, eligibility proof,
verified building classnames, performance baseline or deployment is claimed.
