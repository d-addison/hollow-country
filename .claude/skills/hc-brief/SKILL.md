---
name: hc-brief
description: Write a Hollow Country worker brief to template v2 and lint it before dispatch. Use when about to write, revise or dispatch a brief for a worker, fix round or reviewer.
---

# Write a worker brief

1. Copy `docs/briefs/TEMPLATE.md` to a local file outside the repo (briefs are never committed).
2. Fill every section: goal, owned files, invariants, failure table, required evidence, base branch,
   checks, report format. Set `Kind:` in the header.
3. Crash, persistence and dependency-boundary briefs also need `Design review: <reviewer> <YYYY-MM-DD>`.
   A brief that owns a store, journal, save or bridge `.c` file must declare one of those kinds.
4. Owned files are listed one path per bullet and are disjoint from every other worker in the wave.
5. Invariants are numbered and testable. For stored data say what an old profile does (migrate at start,
   never refuse forever). The failure table has a handling column on every row.
6. Name the evidence line the lead will look for (`[HC Use]`, `[HC SelfTest]` or `[HC Ready]`).
7. Point the worker at the cards for the paths it owns: `.c` files read `docs/pitfalls/enforce-pitfalls.md`;
   stores, journals and loaders read `persistence.md`; `mods/HollowCountryExpansionAI` and bridge files read
   `dep-bridge.md`; tick and save-step code reads `perf-tick.md`.
8. Lint before dispatch; pass every brief of the wave at once so overlapping owned files are caught:

```
python3 -B -m tools.validate.brief_lint brief-a.md brief-b.md
```

A brief with findings is not dispatched. The linter checks shape only; the lead still checks the invariants.
