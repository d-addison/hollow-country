# Experimental implementation verification

This supersedes the offline-foundation snapshot only for the new implementation.
It does not complete the overhaul or promote any native gameplay capability.

Final source: 250 discovered unit tests, 10 bound offline BDD scenarios and seven
setup static tests. The Banso `verify-offline` pipeline passed all four steps
after the final routing correction: behavioral tests, executable scenarios,
setup static checks and operator settings admission (13696 ms total).

```sh
banso --feature 001-survival-overhaul workflow run hollow-country --pipeline verify-offline --headless
```

Spec lint passed with zero errors/warnings; task graph validated 25 tasks in 12
waves (optional Estimate warnings retained); workflow and BDD syntax validated.
Project integrity preserves all 48 requirements and 68 original catalog tests.
All 136 local Markdown links checked at the preceding integration snapshot
resolved. Whitespace and recognized secret-pattern checks passed. Root and
packaged operator defaults are semantically identical, all feature flags false.

Independent core/crafting/interiors review resolved elapsed-time and deferred
deletion findings in source. Independent infected review resolved release
ownership, minimum adoption work, native membership/route status and scan
starvation findings. Final scoped results: interiors 21, crafting 11, infected
20, economy/package 25, settings five. Actual red/green records and restricted
test-harness limitations are preserved in the experiment reports and fixtures.
Native self-tests are authored but unexecuted.

The PBO and private ZIP passed strict format/checksum/manifest/source checks;
hashes and the failed native invocation are in [first mod](P0-first-mod.md).
The package was extracted into a fresh Downloads folder. No proprietary assets,
native dump, signing key or runtime save was included. These are unsigned
development artifacts, not a signed or accepted release.

Native Windows PowerShell/DayZ launch failed at WSL interop before execution;
the requested smoke directory/report was absent. The independently observed
vanilla startup and scheduled successful termination remain separate from mod
validation. Client connection is deferred by the user. Missing gameplay,
native compilation/signing, durable transactions, two-client tests, actual CE
eligibility, calibrated performance and destination rollback remain open in
[module status](../docs/MODULE_STATUS.md) and the roadmap issues.

Commit `796175f8e919145d59c04921c1dee44c2db7a45c` passed
[GitHub CI run 43950077596](https://github.com/d-addison/hollow-country/actions/runs/43950077596).
Both offline validation/artifact packaging and native Windows PowerShell
syntax/synthetic setup/package guards passed. These Windows checks do not run
DayZ: no native DayZ engine exists on that hosted runner.
