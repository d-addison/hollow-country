# Hollow Country #30 firearms — read-only review

2026-11-17. One review pass, no mutation testing, no DayZ/Wine/network execution.
Reviewed the requested parser, census, roster, optional dependency, economy diff,
documentation and four new test modules. Production files and git state were not
modified. Authored artifacts are confined to this directory.

## P1 blockers

### 1. Rollback can overwrite a file outside the mission through `core.next`

- Location: `tools/package/snafu_optional.py:505–524`, especially line 522.
- Confidence: high; reproduced with a synthetic behavioral regression.
- After a valid install, create a hard link from
  `hollow-country-snafu/core.next` to an operator file outside the mission.
  Preflight accepts this expected filename, and `economy.child` rejects only
  symlinks, not hard links. `write_bytes(backup)` truncates the shared inode before
  `os.replace` runs. Rollback succeeds while the outside file's original bytes
  are replaced with the economy-core backup. No race or changed source code is
  needed; the link must exist before rollback and reference a writable file on
  the same filesystem.
- This violates both path containment and refusal of drift, and can destroy
  unrelated operator data. The synthetic fixture places its outside file within
  this scratch directory, outside its synthetic mission.
- Fix: never truncate a pre-existing fixed staging pathname. Use an exclusively
  created fresh regular file and atomic replacement; refuse unexpected or
  multiply linked existing staging files before modifying anything. Apply the
  same correction to the shared `economy.rollback` path at line 332, which has
  the pre-existing version of this defect and is reused by firearms rollback.
- Regression: `test_review_regressions.py:33`.

### 2. The default roster activates unused vanilla weapons without local acceptance

- Location: `tools/package/firearms_roster.json:193–241`,
  `tools/package/firearms.py:147–157`, and `docs/FIREARMS.md:35–36`.
- Confidence: high; reproduced with a synthetic generation test and corroborated
  against installed stock files, without launching the game.
- `LeeEnfield`, `MP18` and `Luger` have stock nominal zero and are classified
  `nominal-zero` by the existing static census. They are placed in the active
  `entries` array with positive nominals 6, 2 and 3, rather than the deferred
  proposal list. Default generation emits those counts; installation has no
  local-acceptance gate. Documentation explicitly says they are enabled while
  also recording local acceptance as pending for every entry.
- The owner rule covers datamined unused vanilla, including these three, not
  only variants missing from `types.xml`. Presence, public scope and asset
  completeness are insufficient acceptance evidence. A pending label on an
  installable delta does not keep these entries proposal-only.
- Fix: keep these three and their newly enabled support entries in the deferred
  proposal until local acceptance is recorded. Preserve any trial counts as
  proposals; require explicit acceptance before including them in the ordinary
  installable roster. Source authoring and a separately explicit local trial
  remain possible without claiming production acceptance.
- Regression: `test_review_regressions.py:58`.

## P2 observations

- `snafu_optional.py:488–490,501–524`: the receipt records
  `verification_sha256`, but rollback never checks `verification.json` against
  it. A changed verification file is silently deleted. Check its digest before
  changing the core or deleting managed content. Reproduced by
  `test_review_regressions.py:47`; this affects evidence preservation rather
  than the ordinary byte-exact core restoration.
- `firearm_census.py:53–58` and `snafu_optional.py:529–533`: the outside-Git checks
  inspect lexical absolute paths, allowing an external symlinked ancestor to
  resolve into a checkout. Resolve existing ancestors or reject symlinked
  ancestors before output creation, particularly to keep full census dumps out
  of Git. Static inspection finding; no full dump was written during review.

## Checks with no additional blocker found

- PBO reads use fixed header chunks, header/name/entry limits, and a 64 MiB
  member limit checked before `read(size)`. Rap parsing checks input size,
  class/body/array counts, nesting and offsets. No direct unbounded allocation
  from a declared PBO member length was found. This is not a fuzzing or aggregate
  memory-usage qualification.
- Default `economy.install` still permits only usage changes. The additive
  `mutable` argument does not widen its default; existing economy tests and the
  budget-change refusal test pass.
- Literal SNAFU searches found no references in `mods/`, `mission/` or `config/`,
  or in nonoptional base Python packaging. The supplied independence and asset
  exclusion tests pass. No Workshop assets were copied.
- Allowlist validation and generation fail closed for absent/unverified reports,
  mismatched allowlist hashes and individually unverified classes in the tested
  workflow. The committed allowlist remains `unverified`. A report is static
  operator-supplied evidence, not runtime acceptance or an authenticated artifact.
- All 60 vanilla roster names exist in installed Chernarus stock `types.xml`.
  All 30 support ammo/magazine names were located in installed official configs:
  27 in base weapon/ammunition configs and the three Lee-Enfield/MP18/Luger
  magazines in `nasdara/addons/weapons_nasdara.pbo`. Their bullet references
  resolve in the scanned official projectile config. The cached full census
  also agrees with the 30 weapons' declared chamber and magazine lists. This
  establishes static definition presence only; DLC availability on the eventual
  server/client combination remains unobserved.
- Existing tests establish ordinary byte-exact install/rollback and last-in,
  first-out restoration for synthetic missions. They do not cover the hard-link
  escape above or establish actual CE merge/spawning behavior.

## Validation record

Requested command, run unchanged:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_pbo_config tests.unit.test_firearm_census tests.unit.test_firearms_roster tests.unit.test_snafu_optional tests.unit.test_economy
Ran 68 tests; FAILED (errors=1).
ModuleNotFoundError: No module named 'tests.unit.test_economy'
```

The four firearms modules' 67 tests passed; the only error was the nonexistent
module name. Substituted the existing economy contract module:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_pbo_config tests.unit.test_firearm_census tests.unit.test_firearms_roster tests.unit.test_snafu_optional tests.unit.test_economy_contract
Ran 76 tests; OK.
```

All existing economy-named modules were also run:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_economy_contract tests.unit.test_search_economy tests.unit.test_search_economy_integration tests.unit.test_search_economy_native tests.unit.test_search_economy_policy tests.unit.test_search_economy_recovery
Ran 68 tests; OK.
```

There are 135 distinct passing existing tests across these commands.

Review regressions, intentionally left failing against unchanged production code:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scratchpad-review/firearms-solreview -p 'test_review_regressions.py' -v
Ran 3 tests; FAILED (failures=3).
```

Actual failures:

1. Default delta contains positive counts for `LeeEnfield`, `MP18`, `Luger`.
2. Outside marker bytes become the XML economy-core backup during rollback.
3. Changed verification file does not cause the expected `ValueError`.

No implementation fix or green regression run was attempted in this read-only
review. No source mutation testing was performed.

The required specification files are absent from this isolated worktree; their
copies under `/code/dayzsa_mods/docs/` were consulted, along with the worktree's
runtime implementation contract. Active-session owner decisions, private scope
and the 3–6-player target take precedence over older specification assumptions.
Native acceptance, production enablement, DLC behavior and measured balance
remain pending.

Verdict: FIX-THEN-MERGE
