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

## Fix round 2 (Opus review of 3db39d4c; same rules and owned files)
F1 (P1) HCXAISitePatrols.c:49-52 + HCUse sites: revert the counter owner to "SitePatrols" (HCXUseRegistry.c:44-46,
   r3_smoke_plan.json:1004-1028 already own SitePatrols/*). Remove the constructor HCRegisterUse lines. Do NOT add
   feature counters for death-hold-exit / death-hold-deferred (failure paths stay 0 in a healthy soak -> INERT fails
   R3); keep them as reason-coded Print lines only. Verify: python3 -B -c "from tools.release.activity_check import
   check_smoke_plan; check_smoke_plan()" raises nothing.
F2 (P2) HCXAISitePatrols.c:126-127,153-156: the new exits call HCEndPatrol with live members, skipping Despawn's
   combat veto (DespawnAllowed ~:332) and the player-proximity check (~:334-344) -> survivors vanish in front of a
   player. Before ending, apply the same veto + player-distance checks; if refused, release the hold (HCReleaseHold)
   and mark the patrol not to resume (no new spawns/assignments) and keep deferring the end until the checks allow it.
   One reason-coded line when the exit fires and when it is vetoed (rate-limited by the existing 10 s report clock).
F3 (P2) HCSearchHouses.c:556-559: End(session.Owner) with Owner==null (picker sessions, PickerAuthority) ends every
   picker session. Use: if (session.PickerAuthority) { if (!m_Busy) m_Sessions.Remove(m_SessionSweepNext); } else
   End(session.Owner); and count swept non-picker sessions in the existing house_interrupted counter if one exists.
F4 (P2) HCXAITactics.c:517-520: at capacity, evict the oldest record whose SmokeUntil/LureUntil have passed and whose
   cap window expired (bounded scan of s_Groups, <= TrackedGroups); return null only when every record is still in
   cooldown, and count that in a separate counter/summary field (not s_Throttled).
F5 (P3) HCGroundSnap.c:155-171: do not wipe live footprints. When s_Dead is large (e.g. >= half of the slots), compact
   (rebuild arrays + s_Cells without tombstones); at the live cap refuse new Adds with one reason-coded log line. Fix
   the comment (cache loss changes CE spawn height inside still-standing buildings).
Validate as before (preland --changed rt/v16-p3, lint, perf). Commit as a new commit on top of 3db39d4c.
