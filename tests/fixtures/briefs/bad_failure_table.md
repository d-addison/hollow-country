# Task wf-grouphandles: raw group handles must not outlive their group

Task: wf-grouphandles: raw eAIGroup handles must not outlive their group
Kind: crash
Worktree: example worktree (branch rt/wf-grouphandles)

## Goal

Replace every raw group handle held past the lifetime of its group with a hold or a group id, so no later
call touches freed memory in the Expansion AI adapters.

## Owned files

- `mods/HollowCountryExpansionAI/scripts/4_World/HCXAIRoleActivities.c`
- `mods/HollowCountryExpansionAI/scripts/4_World/HCXExpansionBridge.c`

## Invariants

1. Every stored group handle is either held or resolved by id before each use.
2. No new spawns and no behaviour change outside the handle lifetime.

## Failure table

| Failure mode | Reason code |
|---|---|
| Group freed while a lease still names it | group_gone |
| Group id reused by a new group | group_reused |

## Required evidence

Boot shows no native access violation.

## Base branch

main

## Checks

```
agent-run --memory 2G -- python3 -B -m tools.validate.enforce_lint --native-scripts <native scripts cache>
agent-run --memory 2G -- python3 -B -m tools.validate.enforce_perf --strict-baseline
```

## Report format

Branch and commit sha, per-site approach with file and line, any site left unchanged and why.
