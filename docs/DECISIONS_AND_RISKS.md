# Decisions, Assumptions, Engine Risks and Legal Review

Execution decisions: see [ADR-017](adr/ADR-017-local-coop-development.md).
Hollow Country / ChernarusPlus confirmed; local development server here,
friend's destination server later; 3–6 players. Private repository created at
`d-addison/hollow-country`. This supersedes the initial separate-machine block.

## Decision register

| ID | Status | Decision | Reason / consequence |
|---|---|---|---|
| ADR-001 | Accepted by user | Local experimentation first, separate dev/client and server machines, multiplayer-ready | No public service or hosted dependencies initially |
| ADR-002 | Accepted by user | Private GitHub repository now; future public Workshop release undecided | Repo must not be published or advertised as public |
| ADR-003 | Accepted by user | Reuse DayZ official settings and systems wherever possible; only extend missing parts | Native-first capability evidence required |
| ADR-004 | Accepted by user | Performance is non-negotiable | Feature regressions can block release regardless of visuals |
| ADR-005 | Accepted by user | B reward economy, B soft progression with C realism and D world state | No arbitrary loot abundance or rigid item restriction |
| ADR-006 | Accepted by user | Existing buildings and models, not custom house geometry | Dynamic interior == additive layout + searchable opportunities |
| ADR-007 | Accepted by user | Persistent layouts, broad salvage and mixed visible/searchable loot | Require stable identities, atomic search and material accounting |
| ADR-008 | Accepted by user | Hybrid infected profiles; dynamic hordes **AND** local chain reaction alerts | Two interdependent but separate controllers with caps |
| ADR-009 | Accepted by user | Methodical searches, persistent escapes, dangerous groups, balanced overall density | Limit individual power creep, reward stealth |
| ADR-010 | Accepted by user | Realistic audio/physics, advanced but physically audible stealth, injury effects | Never introduce cheating AI, wall clipping or silent movement |
| ADR-011 | Proposed / verify | ChernarusPlus as first test world | Matches Northmen reference and two concrete building examples |
| ADR-012 | Proposed / verify | Minimal shared support module with independent game feature modules | Separation without overengineering; one package may suffice initially |
| ADR-013 | Proposed / verify | Original CE remains source of truth for world loot; supplementary search quota | Avoid duplicate custom economy unless CE integration proves insufficient |
| ADR-014 | Proposed / verify | Distant hordes are abstract records, active hordes are actual existing infected entities | Performance and fairness must both be tested |
| ADR-015 | Proposed / verify | Precompute/build layouts offline first; runtime streaming is a last resort | Avoid thousands of dynamic entity operations, pop-in and persistence errors |
| ADR-016 | Proposed / verify | Initial performance budget ≤5% steady-state added server-frame time vs vanilla at tested load | Engineering hypothesis only; calibrate using hardware/target capacity |

## Important engine-specific risks

**R-01 Native infected pathing:** The game uses engine-controlled movement and navigation. Some doorway/path failures can be unfixable through scripts. Severity critical, likelihood high. **Mitigation:** baseline tests, direct hook inspection, physics-safe fallback, collisions-free interiors; do not claim universal fix.

**R-02 Perceived sound gap:** AI hearing and human client audio are separate channels. Even if a script knows an infected moved, it may not be possible to force accurate material-aware footsteps without duplicate sound or animation anomalies. Severity high, likelihood unknown. **Mitigation:** two-client audio fixtures, native triggers first, patch only observable gaps.

**R-03 Object count and nav regression:** More furnishing objects can hurt client/server FPS, physics, replication and infected entry. Severity critical, likelihood high at scale. **Mitigation:** offline precomputation; prop budgets; non-simulating/low-collision assets; no blocked doors; measure slope vs object count.

**R-04 Economy inflation / infinite search:** Adding per-container loot on top of CE can generate too many items or repeated-value exploits. Severity high. **Mitigation:** quota ledger, atomic claims, no auto-regen on access, cap high-tier items, CE audit and restart tests.

**R-05 Persistence and schema migrations:** Changing build or seed can reroll houses, reset drawers or clone props. Severity high. **Mitigation:** stable IDs, schema version, migrations, backups, idempotence, restart and crash-recovery tests.

**R-06 Hordes & chain reaction blowup:** Recursive alerts and spawning can cause exponential work/load or invisible enemies. Severity critical. **Mitigation:** attenuated event TTL/hop caps, per-source dedupe, LOD and global active entity budgets, never visible respawn.

**R-07 Private mod and license incompatibility:** Northmen Core and some Workshop mods may prohibit copying, modifying/repacking, or redistribution. Severity high. **Mitigation:** no copying; license inventory; use unmodified optional dependencies only if permitted; independent implementation based on documented APIs/behavior.

**R-08 DayZ game updates:** 1.30 changes code/config and has known issues; mod hooks may break. **Mitigation:** pinned baseline and generated diff against upstream, versioned compatibility matrix, smoke test each update, quick feature disable and rollback.

**R-09 Multiplayer races and authoritative state:** Simultaneous looting/crafting/door actions, reconnects or activation can dupe, desync, or create unphysical states. **Mitigation:** server authority, idempotent RPC, atomic inventory/site transition, two-client concurrency tests.

**R-10 GitHub Actions/hosting cost and reproducibility:** Hosted runners may lack DayZ binaries; runaway CI minutes/logs expensive. **Mitigation:** cheap static CI, local packaged tests, caps/concurrency, no auto-setup of game clients in hosted CI; track build/run cost.

## Licensing and publication checklist

- [ ] Determine applicable Bohemia games/modding licenses and whether full vanilla CE copies are derived works with attribution/share-alike requirements.
- [ ] **Official Bohemia DayZ-Central-Economy repository declares ADPL-SA**, with attribution, noncommercial, Arma/DayZ only, share-alike for derived materials. Review full license before incorporating derived config into public distribution; private repo does not mean license is irrelevant.
- [ ] Avoid committing extracted proprietary game assets/model dumps to private GitHub without explicit rights; use small authored diffs and instructions to obtain game files locally.
- [ ] Record licenses for examples, schemas, source snippets and third-party assets.
- [ ] Do NOT bundle, repack or modify restricted Workshop mods or Northmen-specific mods absent permission; a mod's Steam Workshop availability is not blanket license for reuse.
- [ ] Verify independent names/icons/textures/animations if releasing; keep project and Workshop publishing disabled until approval.
- [ ] Decide future source license separately; `private` does not mean a chosen open-source license.
- [ ] Keep client keys, remote access, signing private keys, Steam credentials, RCon secrets, logs with identifiable data and large binaries out of Git.

## Non-blocking unresolved decisions

- Actual server hardware OS, IP/network setup, server capacity/player count, target max active infected/horde size, renderer/client hardware and budgets.
- Concrete world population and progression rates, loot items that currently feel rare by classname, final recipes and archetype weights.
- Final mod/repo name, future license, optional third-party compatibility and public release date (none selected).
- Whether full map Chernarus interior variety is a v1 goal versus iterative subset; first milestone is small and measurable.
- Exact host OS: default explore Windows first for least ambiguous setup; Linux support a separate explicit compatibility experiment.

## Formal change management

Each newly approved user preference is recorded with new ADR ID, `SPECIFICATION.md` requirement delta, acceptance/test updates and migration effects. Each engine limitation gets a reproducible experiment (not a statement of impossibility by intuition), supported/blocked status and chosen fallback. Nothing should be marked implemented based on a passing offline simulation alone.
