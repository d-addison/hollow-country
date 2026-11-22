# Task wx-journal: Events journal survives a torn file

Task: wx-journal: preserve a torn Events journal and keep starting
Kind: persistence
Worktree: example worktree (branch rt/wx-journal)
Design review: Opus 2026-11-20

## Goal

After a power loss leaves a torn Events journal, the next start preserves one copy, loads the last complete
revision and keeps the Events module running instead of refusing at every boot.

## Owned files

- `mods/HollowCountry/scripts/4_World/Events/HCEventJournal.c`
- `mods/HollowCountry/scripts/4_World/Events/HCEventRuntime.c`
- `tests/unit/test_example_journal.py`

## Invariants

1. A torn file is preserved once per revision; a second boot never creates a second copy.
2. The original is deleted only after the copy is verified by byte count.
3. The journal never refuses forever: after three failed boots it proceeds with the last complete revision.

## Failure table

| Failure mode | Reason code or signal | Expected handling |
|---|---|---|
| Torn file holds NUL bytes | torn_nul | Compare by byte count, copy, then delete the original |
| Copy cannot be verified | torn_copy_failed | Keep the original, count the attempt, escalate after three boots |
| Read-only torn file | torn_readonly | Keep it, print one reason line, load the last complete revision |

## Required evidence

`[HC Use] module=Events feature=journal_repair count=1` in the native boot after a seeded torn file.

## Base branch

dev at 2d2c075c.

## Checks

```
agent-run --memory 2G -- python3 -B -m tools.validate.enforce_lint --native-scripts <native scripts cache>
agent-run --memory 2G -- python3 -B -m tools.validate.enforce_perf --strict-baseline
python3 -B -m unittest tests.unit.test_example_journal
python3 -B -m tools.validate.hygiene
```

## Report format

Under 400 words: branch and commit sha, files changed, every crash cut point touched with its recovery,
the exact checks run with results, and anything left undone or uncertain.
