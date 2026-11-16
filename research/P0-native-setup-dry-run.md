# Native Windows setup dry run

2026-11-16, user-reported terminal evidence. Related: T003, FR-002, FR-012 and
[bug #26](https://github.com/d-addison/hollow-country/issues/26).

Initial Windows PowerShell execution failed at the first executable hash check:
the provider helper emitted a ProviderPath WhatIf message and no Hash property.
The original Linux static checks could not establish native behavior.

Fix commit `e3bf740` replaces provider hashing with read-only .NET SHA-256
streams and guaranteed disposal. Actual static regression: 7 tests, 2 failures
before the fix; all 7 pass afterward. [CI](https://github.com/d-addison/hollow-country/actions/runs/43941012695)
passed the existing offline suites and a new native Windows PowerShell synthetic
test of WhatIf non-creation, staging, source preservation and overwrite refusal.
Synthetic test files are not a DayZ server or engine observation.

The corrected .ps1 was copied to Windows Downloads and its SHA-256 matched
repository source: `98964897df2a32670edc0a8a032412b72c2fc16cbc0e00f089848cdfaf2d2c73`.
The user then ran the installed-file dry run and supplied:

```text
Source verified: 43 pinned mission files; runtime D:\HollowCountryLocal\vanilla-p0-001
Plan: stock backups, vanilla mission copy, isolated profiles/storage/BattlEye, 30-minute shutdown.
Server will NOT be launched. Requested game bind is 127.0.0.1:2302; native socket verification remains mandatory.
What if: Performing the operation "Create NEW isolated local vanilla runtime and stock backups" on target "D:\HollowCountryLocal\vanilla-p0-001".
```

A subsequent agent directory read confirmed that runtime did not yet exist.
Next: stage without WhatIf, inspect generated completion/launch files, then
native launch and bindings before client connection. T003 remains open; no
join/persistence, PBO, multiplayer or performance acceptance follows from this
successful dry run.
