# Brief: v16-uar. Use-after-remove audit + lint rule (crash class)

Branch rt/v16-uar (checked out in this worktree, base 0d6488d6 = rt/v16-integ). Enforce fixes + one lint rule.

## Why
Enforce: a non-ref variable of a NON-Managed class is a raw pointer, not nulled on free. When an
`array<ref T>` / `map<K, ref T>` holds the only ref, `Remove`/`RemoveOrdered`/`RemoveItem`/`Clear`/`Set`
(replacing) frees the object at once; any later read or write through a raw local is a use-after-free, and a
WRITE corrupts the heap (random later access violations, e.g. the soak-195 server crash in HCGroupService.Live).
Managed classes (anything deriving Managed: Object/EntityAI/PlayerBase, PlayerIdentity, Widget, classes declared
`: Managed`) auto-null their weak refs instead (then a later call is a NULL VME, also a bug if reached).
Two real cases are already fixed by the lead on another branch; do NOT touch them:
HCGroupService.Disconnected and HCXAISiteStore.HCCacheSeedRevert.

## Task
1. Triage every candidate in candidates.txt (next to this brief; a heuristic list, many are false positives: the
   use is on a `continue`/`return`/else path, the local is `ref`, the element type is Managed, or the container is
   not the only owner). For each, record verdict REAL / SAFE with a one-line reason (file:line). Also check the
   same files for the swap-remove form (`tail = arr[last]; arr.Remove(last)` then `tail` used) and for
   `map.Set(key, replacement)` freeing a previous value that a raw local still uses.
2. Fix each REAL one minimally: read what you need before removal, or hold the element in a `ref` local until done,
   then remove. No behaviour change otherwise.
3. Add lint rule HC-E0xx (next free id; follow tools/validate/enforce_lint's existing rule structure and its
   class/Managed resolution) "use after removing from an owning ref container": a raw local of a non-Managed class
   taken from container C (Get/[]/foreach/Find result), then C is mutated by Remove*/Clear/Insert-at-capacity
   is NOT needed — only Remove*/Clear/Set, then the local is dereferenced or passed on a path that does not
   first `return`/`continue`/`break`/reassign. Precision first: no new baseline rows; it must flag the two known
   cases on their pre-fix text (fixtures) and none of the SAFE ones. Focused unit tests for the rule only.

## Files you own
mods/**/scripts/**/*.c for the REAL fixes only (list them), tools/validate/enforce_lint*.py (the new rule),
tests/unit/test_enforce_lint*.py (rule fixtures). Do not touch Infected/HCInfectedRooms.c,
Infected/Variety/HCInfectedVarietyModule.c (another worker), Groups/HCGroupService.c, HCXAISiteStore.c.

## Done
Commit on rt/v16-uar (no attribution lines). Quote the summary lines of:
`agent-run --memory 4G -- python3 -B -m tools.validate.enforce_lint --native-scripts ~/.cache/hollow-country/native-scripts/scripts-1.30.164289 | grep 'enforce_lint: '`
`agent-run --memory 4G -- python3 -B -m tools.validate.enforce_perf`
and the focused tests. Report: the triage table (REAL/SAFE + reason), fixes, rule id and what it flags.
Never start DayZ, the compile gate, Workbench or a soak. Never claim multiplayer proven.

Do not commit BRIEF.md or candidates.txt.
