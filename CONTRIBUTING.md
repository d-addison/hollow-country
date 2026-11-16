# Contributing to Hollow Country

Select an [issue](https://github.com/d-addison/hollow-country/issues), describe
the expected behavior and acceptance criteria, and agree on disjoint file scopes
before parallel implementation. Keep internal specifications, interviews and
agent records local; summarize reviewable decisions in the issue or pull request.

Use specification-driven development, behavioral scenarios and test-first changes.
Record an actual failing behavior, implement the change, and run the relevant
tests. New or changed offline scenarios require explicit executable bindings.

```sh
python3 -B -m unittest discover -s tests/unit -v
python3 -B -m tools.validate.runtime
python3 -B -m tools.validate.hygiene
python3 -B -m tools.validate.bdd
```

For native changes, inspect the installed DayZ API first and record the tested
build, source/package hashes, observed behavior and rollback result. Multiplayer,
visibility and audio changes require connected-client evidence. Keep incomplete
acceptance open and unqualified features disabled. Offline tests cannot establish
engine behavior or production capacity.

Pull requests should explain the behavior change, link the issue, summarize actual
validation and identify remaining limitations. Update operator documentation and
configuration examples when behavior changes. Close issues only when their scoped
acceptance has been satisfied.

Original source is private and all rights reserved. Do not commit game assets,
vanilla dumps, Workshop packages, runtime saves/profiles, credentials, signing
private keys, machine inventories, raw test outputs or local planning records.
Keep reusable synthetic fixtures and tests in Git. Publication requires a separate
decision; possession of a dependency does not grant redistribution rights.
