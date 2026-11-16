# Local vanilla runtime — P0

Status: **staged and independently checked; launch/join/restart pending**.
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

The user has the native Start-Process command. Next evidence: actual PID and
process readiness, all listener bindings, mission initialization and startup
errors, normal-client join, inventory/respawn/reconnect, graceful shutdown,
stopped-runtime backup and saved-state restart. No success is inferred before
these observations. The runtime is isolated; never rerun its creation script
over the existing directory.
