# Contributing to Hollow Country

Start with [project tracking](docs/PROJECT_TRACKING.md), the
[active spec](docs/specs/001-survival-overhaul/spec.md) and [plan](docs/specs/001-survival-overhaul/plan.md).
Select the matching issue, read its prerequisites and agree a disjoint write
scope before parallel work. Do not treat completed offline tooling as native
feasibility proof. The full product remains tracked through P0–P8.

For each change, update affected requirement/AC/test mappings and record a
failing behavioral test before the smallest implementation. Run:

```sh
python3 -B -m unittest discover -s tests/unit -v
python3 -B -m tools.validate.project
python3 -B -m tools.validate.bdd
python3 -B -m unittest discover -s tools/setup -v
```

Follow [Banso commands](docs/BANSO_WORKFLOW.md) for spec, plan and graph checks.
New or changed BDD steps require explicit bindings and actual executed tests.
For native work, inspect the installed API first; attach pinned build/commit,
sanitized artifact hashes, relevant multiplayer and performance results, and
rollback evidence. Keep unobserved acceptance unchecked and complex features off.

Use the bug/spec issue templates and PR template. Link the task issue, summarize
resulting behavior and actual validation, and record unresolved limitations.
Update canonical spec/plan/graph before regenerating tracking descriptions; put
execution evidence in issue comments. Close an issue only after its scoped
acceptance is satisfied. Leave its phase milestone open until every native gate
for that phase passes.

Source is private. Do not commit game dumps/assets, Workshop packages, profiles,
credentials or private signing keys. Public/Workshop publication is unauthorized.
