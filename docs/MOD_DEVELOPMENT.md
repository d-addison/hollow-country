# Hollow Country addon development

The authored addon lives in `mods/HollowCountry`. It contains original script
and config text only. Installed DayZ assets and extracted native script sources
remain outside the repository. The server lifecycle is in `HCServer.c`; module
registration uses the shared [integration contract](RUNTIME_IMPLEMENTATION_CONTRACT.md).

## Configuration

The server creates `$profile:HollowCountry/settings.json` on first addon start.
The reviewed operator template is [config/hollow-country-settings.json](../config/hollow-country-settings.json).
All six feature flags default false. Edit only with the server stopped, retain a
backup, and validate the operator file before installing it:

```sh
python3 -B -m tools.validate.runtime --help
python3 -B -m tools.validate.runtime
```

Search requires interiors; hordes and alert chains require infected. Every module
also validates its own configuration and persistence. Enabling a flag does not
establish safe gameplay or bypass a module's independent acceptance checks.
Unknown native behavior must be tested on an isolated profile and storage copy.

## Validation order

1. Run unit tests, operator settings admission, project integrity and executable
   offline BDD. These validate authored policies, data and tooling.
2. Build with the installed official Tools; load the addon into DayZDiag and a
   normal dedicated server. Capture exact build/source/package hashes, compiler
   output and native self-test logs. A PBO container checksum is not a signature.
3. Test individual features, then combined flags, against the catalog in
   [TESTING_PERFORMANCE.md](TESTING_PERFORMANCE.md). Include malformed inputs,
   cancellation, full inventories, concurrency, crash/restart and save recovery.
4. Use two real clients for replication, authority, visibility and sound, then
   measure the intended 3–6-player load against calibrated performance budgets.
5. Sign with a private key kept outside Git; hand off only approved authored
   content, signatures and the public verification key. Exercise clean rollback.

The user has deferred client connection. Offline checks and installed API
inspection continue now; native compilation and all unobserved acceptance remain
open in [the task ledger](specs/001-survival-overhaul/tasks.md). The vanilla server
startup report is not a mod smoke test. Do not copy experimental packages into a
friend's live save or weaken signature verification to make them load.

## Persistence and rollback

Use separate profiles/storage for every experiment. Back up only after graceful
shutdown and preserve the original world identity, schema and configuration
alongside the backup. Restore the matching configuration and persistence pair;
never repair a damaged depletion ledger by silently deleting it. Reverting an
addon does not undo items already granted into a world save. Restore the tested
save backup when reverting a gameplay experiment.

The bounded unsigned compiler smoke helper is a separate development experiment:
it creates a fresh private mission/profile/storage and explicitly disables
signature checking there. It must never target the existing vanilla runtime or
a live server. A successful unsigned smoke cannot satisfy signed package loading
or client acceptance. Use its report to diagnose compilation, then perform the
normal signed smoke separately.
