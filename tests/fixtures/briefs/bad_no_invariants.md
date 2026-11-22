# Task wf-ev2fx: fix round for the Events persistence module

Task: wf-ev2fx: Opus cross-review fix round for p-events2
Kind: persistence
Worktree: example worktree (branch rt/wf-ev2fx)

The friend's server can never be wiped: every on-disk state must load or self-repair. Fix the P1 where
torn_preservation_failed refuses forever, the P2 police receipt listing cap, and the P3 items.

## Goal

Make the Events journal and the police receipt cache self-repair so no on-disk state refuses forever on the
friend server after a torn write.

## Owned files

- `mods/HollowCountry/scripts/4_World/Events/HCEventJournal.c`
- `mods/HollowCountry/scripts/4_World/Events/HCEventRuntime.c`

## Checks

```
agent-run --memory 2G -- python3 -B -m tools.validate.enforce_lint --native-scripts <native scripts cache>
agent-run --memory 2G -- python3 -B -m tools.validate.enforce_perf --strict-baseline
```

## Base branch

dev

## Report format

List every crash cut point you touched and its recovery, plus the checks you ran with their results.
