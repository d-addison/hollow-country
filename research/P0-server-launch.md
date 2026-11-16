# Local vanilla runtime — P0

Status: **staging checked; native server startup observed; client/restart pending**.
Task T003, FR-002/FR-012, AC-002. The friend supplies a second client later.

The user executed the reviewed script without WhatIf in native Windows
PowerShell. It reported staged-only success and wrote launch-plan.json last.
Staging timestamp: `2026-11-16T19:37:44.3387571Z`.
Runtime: `D:\HollowCountryLocal\vanilla-p0-001`.

Read-only verification from the agent then checked:

- All 43 installed mission files and all 43 stock-backup copies match the
  previously pinned sizes/hashes; installed server/config/BattlEye hashes match.
- All 43 staged mission files match the generated manifest. Only db/messages.xml
  differs from stock, as designed for the 30-minute graceful shutdown countdown.
- Backup config matches stock; staged config matches its manifest and differs
  only in the four declared hostname/player/signature/build assignments.
- Staged BattlEye DLL matches its installed pin; launch arguments use separate
  runtime mission/storage/profiles/BattlEye paths, with requested loopback binding.

Result: PASS, no mismatches. Launch-plan.json SHA-256:
`c24af06a5d38c2e0a3d07242e0b0d9d45ce7396f1630e91534eae2a0bed58715`.
This record does
not include game XML, copied assets, profiles or player identifiers.

The user subsequently ran Start-VerifiedLocalServer.ps1. Its native observation
records PID 47296 alive across six samples; game UDP 2302/2304 bound 127.0.0.1,
Steam query UDP 27016 bound 0.0.0.0, and TCP 64981 bound 127.0.0.1. The process
is therefore not wholly loopback-bound. No firewall/router changes were made.
The RPT reaches CE initialization and player connection enablement, with
diagnostics recorded in [the startup experiment](experiments/EXP-vanilla-startup.md).

The user deferred connecting until source implementation is complete. Client
join, inventory/respawn/reconnect, stopped-runtime
backup and saved-state restart remain unverified. No mod was loaded in this run.
Never rerun the runtime creation script over the existing directory.

## Scheduled shutdown observation

The same RPT later records saving/locking at 15:12:50 EST, termination countdown
at 15:13:50, and `Termination successfully completed` at 15:13:59.160 EST
(20:13:59 UTC). This establishes the scheduled termination marker for this run,
not native process/socket inspection after exit or a persistence restore test.
The storage tree contains 32 files; existence alone does not validate their data.
Final captured RPT: 640395 bytes, SHA-256
`1e465bb768c3683baf28dc2f09912526e98650f69da3df165e04ef94a325a98c`.
Error log: 88954 bytes, SHA-256
`d1ee624086a44d4d8ab772ea0fa86b42a9d088e4b99e16bcf645170807573fff`.
Script log: 10620 bytes, SHA-256
`3a0b199dbdbcb7cfdb91805893bce26bf10e1f0ccd2aa43258416fdb3c9daa35`.
The final RPT also reports a resource leak; no claim of clean diagnostics is made.
