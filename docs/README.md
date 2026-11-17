# Hollow Country handbook

Use the [field guide](../README.md) for the component overview and roadmap.

| Purpose | Guide |
| :--- | :--- |
| Install, upgrade, recover and roll back | [Installation and rollback](INSTALL_ROLLBACK.md) |
| Friend server: mods each player needs, build and ports | [Friend server](FRIEND_SERVER.md) |
| Connect to a local vanilla test server | [Local connection check](LOCAL_SERVER_TEST.md) |
| Configure and develop the addon | [Addon development](MOD_DEVELOPMENT.md) |
| Understand component boundaries and current gates | [Module status](MODULE_STATUS.md) |
| Review shared runtime interfaces | [Runtime integration contract](RUNTIME_IMPLEMENTATION_CONTRACT.md) |
| Review ownership and dependencies | [Provenance and licenses](PROVENANCE_AND_LICENSES.md) |
| Find official documentation | [Sources](SOURCES.md) |

Internal specifications, interviews, agent state, machine inventories and raw
experiment records are local development material. They are excluded from Git.
Track deliverables through [issues](https://github.com/d-addison/hollow-country/issues)
and [milestones](https://github.com/d-addison/hollow-country/milestones).

See [tools](../tools/README.md) for commands and [tests](../tests/README.md) for
portable regression checks. Passing offline tests does not establish gameplay,
multiplayer, persistence or production capacity.
