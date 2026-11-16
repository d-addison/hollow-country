# DayZ Survival Overhaul

Read docs/SPECIFICATION.md and docs/specs/001-survival-overhaul/spec.md before changes.
The handoff is design input, not runtime evidence. User decisions in the active
session supersede handoff assumptions. Development and local server testing happen
here; eventual server belongs to a friend; intended load is 3–6 players.

Use Banso spec/plan/tasks and TDD/SDD/BDD. Write a failing behavioral test first,
record its actual failure, implement the smallest change, and record the passing
command. Python tooling uses the standard library. Discover tests with
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v`.
Keep synthetic fixtures explicit. Offline tests never establish DayZ behavior.

Reuse official config and native systems first. Do not build gameplay controllers
on unobserved engine APIs. Production feature enablement requires DayZDiag and
normal PBO/server testing; network/audio/visibility changes require two clients.
Keep all planned requirements and deferred work traceable; never mark missing
engine experiments accepted. No teleports, omniscient AI, silent movement fixes,
blocked doors, unlimited alerts, duplicate loot or client-owned inventory state.

User now requests source/package implementation before connecting the client.
Do not block source authoring on client join. Inspect installed APIs first and
keep runtime acceptance/production enablement pending rather than claiming proof.
Use docs/RUNTIME_IMPLEMENTATION_CONTRACT.md for shared module interfaces/scopes.

Parallel workers own disjoint files. Do not change another worker's scope. Never
commit game assets, full vanilla dumps, Workshop mods, signing private keys,
credentials or local profiles. Source stays private. User authorized pushing to
the private `d-addison/hollow-country` repository; public/Workshop publishing is
not authorized.
Benchmark budgets remain provisional until measured on the target load.
