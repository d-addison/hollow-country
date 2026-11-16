# Repository hygiene completion — 2026-11-16

Scope: `tools/validate/hygiene.py`, `tests/unit/test_hygiene.py`, this report;
subsequently authorized `LICENSE.md`, `docs/PROVENANCE_AND_LICENSES.md` and the
single `*.biprivatekey` addition to `.gitignore`. No package, shared README,
workflow, roadmap or other worker's report was edited. No commit, live deployment
or publication was performed.

## Requirement and decision record

SPECIFICATION §8.3 explicitly requests documentation-link checks, license lint
and secret scanning in cheap CI. Canonical FR-012/NFR-005 and T009/T025 require
private reproducible delivery without purchased assets or private keys. Inspection
of the existing workflow and project/evidence validators found no repository-wide
implementation of these three checks. Package allowlists and `.gitignore` alone
do not detect force-added private material or broken documentation targets.

The user subsequently decided: keep private, all rights reserved; original
authored code belongs to David Addison; no open reuse grants; no ownership claim
or grant over Bohemia assets. Root `LICENSE.md` records that decision, and
`docs/PROVENANCE_AND_LICENSES.md` inventories categories and remaining third-party
review. This supersedes the earlier unresolved project-license choice. It does
not resolve attribution/rights for any third-party quotations, snippets or later
imports, authorize public/Workshop release, or establish authorship by scanning.

## Delivered behavior

- Discover actual Git tracked files plus unignored candidates, including
  force-added ignored files. Reject a nested directory masquerading as the root.
- Bound each Git output before UTF-8 decoding to 2 MiB, with a 15-second child
  watchdog; bound entries to 8192, each file to 8 MiB and aggregate admitted input
  to 64 MiB. Complete size preflight before opening any candidate contents.
- Reject restricted game/archive/executable/private-key paths, runtime profiles,
  restricted import directories, known binary magic and non-text payloads.
  Whole vanilla economy filenames are limited to the existing explicit
  `tests/fixtures/ce/synthetic_*` fixture scope, not silently whitelisted everywhere.
- Reject links, reparse paths, hardlinks, special files and changed-file identity.
  POSIX reads use anchored no-follow descriptors. Preserve Banso's exact existing
  root `spec.md` alias to `docs/specs/001-survival-overhaul/spec.md`: hash the link
  bytes without opening through it; admit its target independently. Redirected
  aliases fail. Git's Windows plain-text alias checkout also remains supported.
- Detect precise private-key headers and GitHub token formats in UTF-8/BOM and
  BOM-marked UTF-16. Emit one finding per offending file and stop matching at the
  first occurrence. Output contains only rule code, sanitized path and line.
  Never emit matched contents, snippets, rejected-file hashes, exception text or
  Git stderr. A credential embedded in a filename is redacted too.
- Inventory admitted working bytes with path, byte count and SHA-256. Validate
  required governance documents and the user's private rights-reserved notice.
  Keep `third_party_rights: pending-human-review` and publication false.
- Validate local inline/image/full-reference Markdown file targets against
  admitted repository candidates, decoding URL path escapes and refusing path
  escape. Ignore code examples; never fetch remote links or read external targets.

`*.biprivatekey` was genuinely absent from `.gitignore`; `*.key` does not cover
that extension. The new rule suppresses accidental untracked-key candidates;
force-added keys remain visible to the validator and cause failure. The actual
external signing key was not opened, copied, hashed, staged or otherwise used.

## Actual TDD evidence

Command for every focused round:

```sh
python3 -B -m unittest discover -s tests/unit -p test_hygiene.py -v
```

1. Initial RED: exit 1, one import error because the new hygiene module did not
   exist. The first implementation then passed 24 behavioral tests.
2. Additional actual behavioral RED: 27 tests, two failures. The valid Banso
   alias was rejected with `unsafe_file`; repeated synthetic credential markers
   caused 8,404,128 traced bytes, exceeding the 4,194,300-byte regression bound.
3. Ignore-policy RED: 28 tests, three failures including the two above. Copying
   the actual repository ignore policy into a synthetic Git repository left
   `synthetic.biprivatekey` visible and rejected, proving the missing ignore rule.
4. GREEN: 28 tests passed after exact-alias admission, bounded reads based on the
   admitted file size, first-match-only secret detection and the new ignore rule.
5. Discovery-bound RED: 31 tests, one failure. Setting the Git output budget to
   128 bytes did not cause `repository_discovery`; output was not yet bounded.
6. Final focused GREEN: **31 tests passed in 0.358 seconds**, exit 0, after bounded
   subprocess output admission. Additional regressions prove preflight never
   opens oversized inputs and source replacement after preflight is refused.

All secret/asset examples are explicitly synthetic; tests assemble credential
markers rather than storing a complete marker in the test source or TDD logs.
No scanner bypass for synthetic credential files exists. The executable
Given-ignored-key / When-force-added / Then-refuse test exercises real Git
discovery. Existing canonical BDD bindings were left to their coordinator.

A separate final measurement of the 1,048,575-byte synthetic repeated-marker
input peaked at **2,136,278 traced bytes**, emitted one finding, and included no
matched contents or offending-file hash. This is a regression measurement on
this Python/Linux host, not a cross-platform performance guarantee.

## Compatibility verification and integration request

The actual repository hygiene scan passed with zero findings; inventory counts
changed as parallel workers added files. Planning integrity passed: 48
requirements, 68 catalog tests, 25 tasks. Runtime-settings admission passed.
`git diff --check` passed at inspection.

One broad integration attempt used the required command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v
```

It ran **477 tests in 12.839 seconds**, exit 1: 9 failures, 2 errors, 1 skip.
The shared tree was still changing; failure output included the other worker's
active `test_observer_transition.py` work. Do not report the whole project GREEN
from this attempt. The coordinator must rerun after all source scopes freeze.
No native Windows execution or DayZ evidence is established by this work.

Minimal coordinator-owned `.github/workflows/static.yml` addition to the offline
job, before development artifact creation:

```yaml
- name: Private source provenance license and secret hygiene
  run: python3 -B -m tools.validate.hygiene
```

Normal unit discovery already includes all 31 hygiene tests. Run the command
again after staging all intended files; force-added ignored files are checked.
Keep JSON output in the job log or runner-temporary storage, not as a self-hashing
repository manifest. Source freeze paths are `tools/validate/hygiene.py`,
`tests/unit/test_hygiene.py`, `LICENSE.md`, `docs/PROVENANCE_AND_LICENSES.md`, this
report, and the authorized ignore-rule edit. Shared README links, workflow edits
and final package inclusion of notices remain coordinator-owned.

## Explicit limits

This is a working-tree guard, not a scan of ignored machine state, Git history,
remote services or archive contents. Secret detection is deliberately narrow:
generic passwords, other providers' tokens and unfamiliar credential formats
need review. It does not certify that a text file is independently authored or
lawfully redistributable. Rights inventory and source hashes are not legal
approval or provenance authentication. Fixture naming is not proof of synthetic
authorship; humans must preserve that invariant.

Markdown checks cover file targets, not heading anchors, remote URL availability,
shortcut references or all CommonMark constructs. Windows/non-dirfd reads require
an immutable checkout and do not defend against a concurrent hostile writer.
Native Windows behavior still needs its CI run; symlink-dependent tests may skip
on Windows hosts lacking link permission. Exact canonical Banso alias handling
is the only symlink exception. Runtime/production/publication gates remain intact.
