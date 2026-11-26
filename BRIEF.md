# Brief: v16 P3 follow-ups (worker, branch rt/v16-p3b, base rt/v16-p3)

Read AGENTS.md first. You are a worker: never start DayZ, DayZDiag, Workbench, the compile gate,
wb_compile, a soak, Blender or DayZ Tools. Do not push or merge; commit on this branch. Never print
home paths, Steam IDs, player names or admin IDs. Inspect the native script cache
(~/.cache/hollow-country/native-scripts/scripts-1.30.164289) before calling any engine API.
Keep work bounded per tick; no new ticks/scans. No unit tests except for item 7 (Python lint).

Owned files (only these): mods/HollowCountryExpansionAI/scripts/4_World/HCXAISitePatrols.c,
mods/HollowCountryExpansionAI/scripts/4_World/HCXAITactics.c,
mods/HollowCountry/scripts/4_World/Loot/HCSearchHouses.c,
mods/HollowCountry/scripts/4_World/Infected/HCInfectedRooms.c,
mods/HollowCountry/scripts/3_Game/Core/HCGroundSnap.c,
tools/validate/enforce_lint*.py and its unit test file, docs/pitfalls/enforce-pitfalls.md, audit/CHECKS.md,
docs/MODULE_STATUS.md (item 6 only). If a fix needs another file, stop and report instead.

Items (each: confirm the defect in code first; if it is not real, say so with file:line and skip it):
1. XAI death hold has no exit (issue #334, rc pre-audit P3-1). HCXAISitePatrols.c ~108-136: when the
   hold is armed while m_HCHold is null (kill before the hold exists, ~:277), after m_HCDeathOverflow
   (17+ kills or a null killed) or for a foreign hold, HCHeldDeathClean returns IDENTITY_MISSING, never
   terminal, so OnUpdate returns early forever (patrol never ends, site budget stays reserved,
   DEATH_HOLD_STALE every 10 s). Fix: end through the existing HCEndPatrol path immediately on the
   overflow/null-hold branch, and after a bounded number of stale reports (~60 s) otherwise. Keep the
   finished/destroyed check first. Log one reason-coded line when this exit fires.
2. Player house search sessions (HCSearchHouses.c) have no deadline sweep: a session whose actor stays
   present but never finishes is never released. Add a bounded sweep (a few sessions per existing tick,
   cursor-based) that releases sessions past a deadline derived from existing config/timeouts.
3. HCXAITactics.c: a record evicted from the per-group ledger loses its cooldown, so an evicted group
   skips its cooldown on re-entry. Make eviction keep the cooldown honest (e.g. evict the oldest-expired
   first, or refuse/back off instead of dropping a record still in cooldown). Bounded.
4. HCInfectedRooms.c BindTemplateHouses: houses already known as conflicts (ConflictKnown / conflict
   houses) spend the one cold admission per call (MAX_BIND_ADMISSIONS_PER_CALL) every time, which can
   starve real admissions. Skip known-conflict houses without spending the slot.
5. HCGroundSnap.c static containers grow without bound (P3-7). Cap them (bounded LRU or clear on a
   threshold) with a reason-coded log once when the cap is hit.
6. docs/MODULE_STATUS.md stale lists (P3-4): only fix entries that are verifiably stale against the code
   (list what you changed). Also P3-3: death-hold counters are not owned by any module, so
   activity_check never audits them; if an [HC Use] counter owner exists for XAI site patrols, register
   the death-hold exit there via the existing HCModuleReadiness.HCUse API; otherwise report.
7. Lint gap (gate 197): Enforce rejected `static string HCBit(bool value) { if (value) return "1"; return "0"; }`
   with "No return statement in function returning non-void". Add an enforce_lint rule (next free HC-E
   number) that flags a non-void method whose whole body is on one line and contains `if (...) return`
   followed by another `return`. Add focused unit tests for it. It must report 0 on the current tree.

Validation before DONE: python3 -B -m tools.validate.preland --native-scripts ~/.cache/hollow-country/native-scripts/scripts-1.30.164289 --changed rt/v16-p3
(world_mesh_audit is a known host-only failure; report others). Report per item: real/not real,
file:line, what changed, and the lint/perf tail.
