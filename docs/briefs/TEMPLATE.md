# Worker brief template (v2)

Copy this file, fill every section, then run
`python3 -B -m tools.validate.brief_lint <brief.md>`; a brief that fails the lint is not dispatched.
Briefs are local working files and are never committed; this template is the only committed copy.
Keep local absolute paths, Steam ids and player names out of anything that is committed.

The linter checks structure only: every section below must exist and hold real content (no empty
section, no `TBD`, `<placeholder>` or `n/a`). It cannot judge whether the invariants are right; that is the
lead's job before dispatch.

## Header

```
Task: <wave>-<short-name>: <one-line title>
Kind: <feature | fix | crash | persistence | dependency-boundary | tooling | docs>
Worktree: <worktree path> (branch <branch>)
Design review: <reviewer> <YYYY-MM-DD>
```

`Kind` is required. `crash`, `persistence` and `dependency-boundary` briefs also need the `Design review:`
line (reviewer and date of the design review that happened before dispatch). Other kinds omit it. A brief
whose owned files touch a store, journal, save or bridge file must declare one of those three kinds.

## Goal

One short paragraph: the behaviour that must be true after the change, and why it is needed now.

## Owned files

List every file the worker may change, one per bullet, as a repo-relative path or a glob that stays inside
one directory tree. Lists are disjoint from every other worker in the wave (`brief_lint --peers` checks it).
A change outside this list means stop and report; do not widen the list in the worker.

- `path/to/File.c`
- `tests/unit/test_example.py`

## Invariants

Numbered, testable statements: ordering, priority, idempotence, bounds, and what must never happen.
For stored data include what an existing profile with the old format does (migrate, or ignore and log; never
refuse forever).

1. <statement a reviewer can check against the diff>

## Failure table

Every refusal, crash point and bad input, with the reason code, what is retried and what is preserved.
Every row has all three columns filled.

| Failure mode | Reason code or signal | Expected handling |
|---|---|---|
| <what goes wrong> | <code or log line> | <retry, preserve, repair or refuse with reason> |

## Required evidence

The exact line the lead looks for in the native boot or smoke, and the feature it proves. At least one of
`[HC Use] module=<Module> feature=<feature> count=<n>`, `[HC SelfTest] name=<name> pass=true detail=<text>`
or `[HC Ready] ...`. Tooling and docs briefs may write `none: <reason>` instead.

## Base branch

`dev` or `main`, plus the base sha. `main` only takes server bug and crash fixes.

## Checks

Commands the worker runs before reporting, with memory caps. Enforce changes need the lint and perf checks;
Python changes need the unit tests of the changed files and the hygiene check.

```
agent-run --memory 2G -- python3 -B -m tools.validate.enforce_lint --native-scripts <native scripts cache>
agent-run --memory 2G -- python3 -B -m tools.validate.enforce_perf --strict-baseline
python3 -B -m unittest <module>
python3 -B -m tools.validate.hygiene
```

## Report format

What the worker's final message contains: branch and commit sha(s), files changed, the exact checks run
with results, the evidence line to look for, and anything left undone or uncertain. State a word limit.
