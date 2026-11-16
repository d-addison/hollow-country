# Documentation

Hollow Country now includes gameplay source implementation and offline tooling.
Native gameplay acceptance remains pending; the user deferred client connection
until implementation is ready. Start with the
[active feature specification](specs/001-survival-overhaul/spec.md): it records
session decisions that supersede assumptions in the original handoff.

| Find | Read |
| --- | --- |
| GitHub milestones and all roadmap issues | [Project tracking](PROJECT_TRACKING.md) |
| Full product requirements and native-first policy | [Specification](SPECIFICATION.md) |
| Current architecture and implementation order | [Feature plan](specs/001-survival-overhaul/plan.md) |
| Work breakdown and dependencies | [Tasks](specs/001-survival-overhaul/tasks.md), [task graph](specs/001-survival-overhaul/task-graph.json) |
| Requirement/test mapping | [Traceability](specs/001-survival-overhaul/traceability.json) |
| Confirmed preferences and local development decision | [Interview](specs/001-survival-overhaul/interview.md), [ADR-017](adr/ADR-017-local-coop-development.md) |
| Capability evidence and unresolved risks | [R&D matrix](RND_CAPABILITY_MATRIX.md), [decisions and risks](DECISIONS_AND_RISKS.md) |
| Test layers, runtime protocols and provisional budgets | [Testing and performance](TESTING_PERFORMANCE.md) |
| Setup sequence from the handoff | [Setup and execution runbook](SETUP_AND_EXECUTION.md) |
| Current native Windows staging procedure | [Local Windows setup](LOCAL_WINDOWS_SETUP.md) |
| Addon architecture, settings and validation order | [Addon development](MOD_DEVELOPMENT.md), [module contract](RUNTIME_IMPLEMENTATION_CONTRACT.md) |
| Authored functionality versus missing gameplay and validation | [Module status](MODULE_STATUS.md) |
| Reproduce the project workflow | [Banso commands](BANSO_WORKFLOW.md) |
| Private transfer and recovery requirements | [Transfer and rollback](TRANSFER_AND_ROLLBACK.md) |
| Source references and current observations | [Sources](SOURCES.md), [research index](../research/README.md) |

The setup runbook contains historical handoff status. Use the active spec and
[current installation inventory](../research/P0-build-inventory.md) for subsequent
decisions; inventory alone does not prove a successful game/server run.

From the repository root, check planning integrity with:

```sh
python3 -B -m tools.validate.project
```

See [tools](../tools/README.md) for audit/comparison commands and [tests](../tests/README.md)
for executable offline checks. Passing these checks does not complete DayZDiag,
normal PBO/server, multiplayer or performance acceptance.
