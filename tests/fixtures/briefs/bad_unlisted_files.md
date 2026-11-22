# Task wf-fort: fortification fix round

Task: wf-fort: Opus cross-review fix round for the fortification build
Kind: fix
Worktree: example worktree (branch rt/wf-fort)

## Goal

Fix every defect the reviewer found in the fortification module so doors, hatches and wall pieces behave
the same on the server and the client after a restart.

## Owned files

Everything in the Fortify module and its tests, plus any helper it needs, etc.

## Invariants

1. A fortified door never blocks the owner from opening it.
2. Rebuilding a piece never duplicates the materials that were spent.

## Failure table

| Failure mode | Expected handling |
|---|---|
| Piece placed on an invalid slope | Refuse with a reason code and keep the materials |

## Required evidence

`[HC Use] module=Fortify feature=door_open count=1` in the native boot.

## Base branch

main

## Checks

```
python3 -B -m tools.validate.hygiene
```

## Report format

Branch and commit sha, files changed, the exact checks run with results, and anything left undone.
