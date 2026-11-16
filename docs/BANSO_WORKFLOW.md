# Banso workflow reproduction

The full feature lives at `docs/specs/001-survival-overhaul/`. Use explicit
`--feature 001-survival-overhaul`; no global current-feature assumption is needed.
The installed Banso version is 0.0.1; source research used `/code/banso` commit
`07fd315a7`. Installed CLI behavior is authoritative for the commands below.

```sh
banso --feature 001-survival-overhaul spec lint
banso --feature 001-survival-overhaul tasks validate docs/specs/001-survival-overhaul/task-graph.json
banso workflow validate .banso/workflows/hollow-country.yaml
banso bdd validate tests/features/offline.feature
banso bdd validate tests/features/runtime.feature
banso --feature 001-survival-overhaul workflow run hollow-country --pipeline verify-offline --headless
```

This installed CLI's legacy phase gate reads `.banso/specs/<feature>.md` and
`.banso/plans/<feature>.md`. Those ignored local adapters point to the canonical
tracked files; recreate them in a fresh checkout before invoking phase commands:

```sh
mkdir -p .banso/specs .banso/plans
ln -s ../../docs/specs/001-survival-overhaul/spec.md .banso/specs/001-survival-overhaul.md
ln -s ../../docs/specs/001-survival-overhaul/plan.md .banso/plans/001-survival-overhaul.md
```

Create adapters only when absent; inspect any existing adapter rather than
overwriting it. Root `spec.md` is also a tracked relative convenience link.
Do not force phase gates. `verify-offline` executes tooling tests and bindings;
it cannot complete gameplay acceptance, P0 runtime checks or the P8 release.

Tasks were authored against the handoff and validated with Banso's canonical
task-graph schema. Parallel implementation and independent review used the
session's native subagent tools with disjoint write scopes. No Banso contracts
execution or runtime test is implied by task-graph validation.

Generic `banso verify --format json` reported WARN, with no failed domains at the
time checked: missing Claude hook integration, absent implementation markers and
reserved Banso-spec coverage checks. Its structural performance result is not a
game benchmark. These warnings are retained rather than hidden with unrelated
markers or fabricated specifications. Context-fit estimates are also absent;
task validation warns and cannot enforce that optional admission check.
