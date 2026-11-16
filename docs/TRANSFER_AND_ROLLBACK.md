# Private transfer and rollback

Status: **procedure, not an exercised deployment**. No release PBO or gameplay
acceptance exists yet. Target is friend's 3–6-player server; OS/build/access
details are pending. Do not transfer the repository as a game asset bundle.

1. Confirm friend's platform, client/server exact build, ChernarusPlus mission,
   optional mod list/load order, free space and prior save schema. Run vanilla
   baseline first. Recalibrate local shared-host budgets on destination hardware.
2. Build with installed official Addon Builder; sign using the local private key.
   Keep private key outside source/package. Verify PBO signatures with official
   DSCheckSignatures; include public key only as needed for server verification.
3. Record source commit, build/tool versions, per-file SHA-256, enabled feature
   flags, mission override diff, dependency/license inventory and migration ID.
   Package only original authored mod/config and permitted outputs. Exclude game
   executables/assets, Workshop content, profiles, credentials and private keys.
4. Stop destination server gracefully; confirm process exits before copying its
   entire mission storage/profile state to a timestamped backup. Hash backup and
   prove restore on a copy. Never overwrite the only backup or silently wipe.
5. Install under a versioned mod directory. Review the minimal mission patch,
   server mod argument/load order and public verification key. Keep signature
   checking and exact build matching enabled. Start with optional flags off.
6. Connect normal clients; verify startup/CE/script logs, join/reconnect, search
   depletion, crafting, two-client sync, restart persistence, audio and horde
   observation. Capture B0–B8 metrics and original catalog tests. Enable modules
   one at a time only after their evidence gates pass.
7. Rollback: stop gracefully; restore previous mod/config AND its matching backup
   schema/save as one set. Never run old scripts on new state without a tested
   backward migration. Restart, join and verify stable layouts/counts/depletion.

No public hosting, Internet firewall/port forwarding, Workshop publishing or
remote admin setup is included. Choose an authorized private transfer mechanism
when the friend is ready. Record real commands and outcomes in
`research/experiments/EXP-transfer.md` once executed; retain pending status now.
