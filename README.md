# Hollow Country

Private DayZ survival overhaul for ChernarusPlus and 3–6-player co-op.
Development and local server tests run here; the final mod will be transferred
to a friend's server. See [the execution spec](docs/specs/001-survival-overhaul/spec.md),
[plan](docs/specs/001-survival-overhaul/plan.md) and
[task graph](docs/specs/001-survival-overhaul/task-graph.json).

Project tracking: [P0–P8 milestones](https://github.com/d-addison/hollow-country/milestones),
[all task issues](https://github.com/d-addison/hollow-country/issues) and
[issue-to-spec index](docs/PROJECT_TRACKING.md).
Browse [docs](docs/README.md), [research](research/README.md),
[tests](tests/README.md) and [tools](tools/README.md) for area guides.
See [contribution and issue workflow](CONTRIBUTING.md) and
[measurement templates](metrics/README.md) for ongoing work.

Current work: the `mods/HollowCountry` addon, native-source research and tested
offline CE auditing, paired benchmark comparison, evidence validation and BDD.
Source/package implementation is proceeding before the user's client connection.
Native mod compilation/loading and gameplay acceptance remain pending; the
vanilla server has reached CE initialization and connection readiness.
See the [runtime integration contract](docs/RUNTIME_IMPLEMENTATION_CONTRACT.md)
and [addon development guide](docs/MOD_DEVELOPMENT.md); the
[task ledger](docs/specs/001-survival-overhaul/tasks.md) records precise status.
See [gameplay coverage and gaps](docs/MODULE_STATUS.md) before using a development package.
The imported handoff below preserves the original design. Session decisions in
[ADR-017](docs/adr/ADR-017-local-coop-development.md) supersede its initial
mandatory two-machine setup. Two clients remain required for multiplayer tests.

Run local offline checks with Python 3.12 and no third-party dependencies:

```sh
python3 -B -m unittest discover -s tests/unit -v
python3 -B -m tools.validate.project
python3 -B -m tools.validate.runtime
python3 -B -m tools.validate.bdd
python3 -B -m unittest discover -s tools/setup -v
```

Tools: [CE audit](tools/audit/README.md),
[benchmark comparator](tools/benchmark/README.md),
[evidence schema](tools/validate/evidence.py).
Native Windows setup: [local server runbook](docs/LOCAL_WINDOWS_SETUP.md).
All committed test inputs are synthetic. Offline PASS cannot certify engine
eligibility, collision, audio, multiplayer behavior or real performance.

## Original handoff

**Status:** specification and R&D handoff, not an implemented or verified game mod.  
**Specification version:** 1.0.0-draft | **Prepared:** 2026-11-16  
**Target baseline:** DayZ PC stable **1.30.164289** (published 2026-11-03; reverify at R&D start).  
**Target map:** ChernarusPlus first (provisional operating assumption; not a final user preference).  
**Repository:** intended **private GitHub repository**, not created or populated by this handoff.

## Start here

1. Read [docs/SPECIFICATION.md](docs/SPECIFICATION.md): complete product requirements, game rules, architecture, system design, dependencies, exclusions, and acceptance criteria.
2. Read [docs/RND_CAPABILITY_MATRIX.md](docs/RND_CAPABILITY_MATRIX.md): **verify** engine/tool capabilities before implementing anything. Mark evidence with observed results, not assumptions.
3. Execute [docs/SETUP_AND_EXECUTION.md](docs/SETUP_AND_EXECUTION.md) in order: private repo, two-machine development environment, baseline capture, prototype, implementation gates.
4. Follow [docs/TESTING_PERFORMANCE.md](docs/TESTING_PERFORMANCE.md) for regression, multiplayer, determinism, game-world rule, and perf tests.
5. Use [docs/DECISIONS_AND_RISKS.md](docs/DECISIONS_AND_RISKS.md) for confirmed decisions, unresolved choices, licenses, known engine constraints, and decision records.
6. Pass [NEXT_SESSION_PROMPT.md](NEXT_SESSION_PROMPT.md) into a new ChatGPT session along with this folder or ZIP.
7. Review [docs/SOURCES.md](docs/SOURCES.md) for official documentation, version, and license reference links.

## Hard constraints

- **Physics/fairness:** no silent physically impossible infected, magical tracking, attacks through walls, phantom horde pop-ins, or objects blocking legitimate access.
- **Performance:** optimization is a design constraint; benchmark every change; bound script work, objects, spawns, networking, and persistence; prefer native functionality.
- **Reuse-first:** official settings and Central Economy first, then native script hooks, then tested external dependencies, then minimally-scoped custom components.
- **Gameplay:** survival-first but rewarding; soft tier progression with believable exceptions and dynamic conditions; chance to loot every accessible building/meaningful area; visible plus searchable opportunities; broad, believable crafting; persistent interior layout.
- **Infected:** dynamic hordes **and** local chain reactions; methodical search; persistent but escapable pursuit; ordinary individual infected, dangerous groups; behavior/location-based variants with individual differences; advanced stealth subject to real sound constraints; meaningful injuries.
- **Environment:** two computers (client/development and dedicated server), multiplayer authority from day one; private GitHub, possible public distribution later; minimal external mod dependencies.

## Handoff condition

The package is **design documentation only**. No DayZ executable, game installation, mod code, CI runner, private GitHub repository, benchmark, local server, or engine/API experiment has been set up by the author. R&D must check every game-specific function against the installed stable version before creating production implementations. When a requirement is engine-blocked, record evidence and propose a measurable alternative rather than claiming a fix.

## Repository guidance

Use a GitHub **private** repository with branch protections, issues and small PRs. Never commit purchased game assets, unpacked proprietary files, keys, passwords, server credentials, Steam tokens, or third-party Workshop PBOs. The source of any Bohemia CE examples retains its own license; read the licensing notes before copying configurations into the repo.
