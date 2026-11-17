# Batch B fast re-review

**No P0/P1 blockers found. The prior P1 is closed for the reviewed file-link cases.**

Reviewed the uncommitted fixes against `scratchpad-review/batchb-solreview/REPORT.md`, limited to link safety, normal install/rollback regressions, and the two P2 fixes. Production source and tests were read-only. All reviewer writes, temporary fixtures and logs are under this directory. No mutation testing, DayZ, Wine, network operations or git writes were performed.

## Prior P1 closure

`tools/package/gameplay.py:101-118` adds single-link regular-file validation and exclusive creation. `write_fresh` unlinks an existing leaf rather than opening its inode for writing, then uses `O_CREAT | O_EXCL` and `O_NOFOLLOW` where available. Install uses it for backup, receipt, gear and `cfggameplay.next`; rollback uses it for the replacement staging file. The final config switch uses `os.replace`, which replaces the destination directory entry rather than truncating a linked destination. Rollback validates managed files and the target config before its dry-run return or any write (`:453-471`); install validates its target config before the dry-run return (`:416-430`).

Two scratch-only behavioral checks in `link_checks.py` passed against the actual implementation:

- **Existing links: 24 cases.** Hard links and symlinks at rollback's `cfggameplay.next`, backup, receipt, gear and target config, plus install's target config, tested separately in dry-run and real mode. Every case raised `ValueError`; outside bytes, target config bytes and the injected link were unchanged.
- **Files swapped after preflight: 18 cases.** A wrapper injects a hard link or symlink immediately before calling the unchanged real writer. Install covers backup, receipt, gear and staging; rollback covers those four files plus the target config. Every outside file retained its original bytes, and every fixture completed byte-exact rollback with its neighboring `init.c` intact. This is filesystem event injection, not production-source mutation or mutation testing.

## Regression and P2 checks

The requested suite passes ordinary untouched install, dry-run without changes, byte-exact rollback, interrupted-install recovery, stale single-link staging replacement, drift refusal, and independent economy ownership. No new P0/P1 regression was found in the fix diff.

The preset's clothing ranges are now `0.6..0.69`. `validate_preset` enforces `0.6 <= healthMin < healthMax <= 0.69`, per-slot civilian-clothing allowlists, and the explicit small-item allowlist. The committed preset passes; weapon/ammunition, unlisted cargo, wrong-slot clothing, and invalid health regressions pass their rejection checks.

## Executed validation

Temporary files were redirected into this directory with `TMPDIR="$PWD/scratchpad-review/batchb-rereview/tmp"`.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_gameplay_delta -v
```

**44 tests, OK**, no skips, 0.225 seconds. Full output: `unit-tests.log`.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scratchpad-review/batchb-rereview -p link_checks.py -v
```

**2 tests, OK**, covering 42 synthetic cases, 0.171 seconds. Full output: `link-checks.log`.

The required specification paths are absent in this confined worktree; consulted their copies under `/code/dayzsa_mods/docs/`, the parent plan/tasks, and this worktree's runtime implementation contract. Active user scope takes precedence. These checks establish offline filesystem behavior for the exercised cases; DayZ/runtime acceptance remains pending.

Verdict: MERGE
