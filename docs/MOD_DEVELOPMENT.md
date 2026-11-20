# Hollow Country addon development

The authored addon lives in `mods/HollowCountry`. It contains original script
and config text only. Installed DayZ assets and extracted native script sources
remain outside the repository. The server lifecycle is in `HCServer.c`; module
registration uses the shared [integration contract](RUNTIME_IMPLEMENTATION_CONTRACT.md).

## Configuration

The server creates `$profile:HollowCountry/settings.json` on first addon start.
The reviewed operator template is [config/hollow-country-settings.json](../config/hollow-country-settings.json).
All feature preferences default true. Existing explicit disables are preserved.
Edit only with the server stopped, retain a
backup, and validate the operator file before installing it:

```sh
python3 -B -m tools.validate.runtime --help
python3 -B -m tools.validate.runtime
```

Search requires interiors; hordes and alert chains require infected. Every module
also validates its own configuration and persistence. Enabling a flag does not
establish safe gameplay or bypass a module's independent acceptance checks.
Unknown native behavior must be tested on an isolated profile and storage copy.

## Experimental stamina profile

The separate `$profile:HollowCountry/stamina.json` file controls the experimental
stamina handler. It is read once when native gameplay configuration loads, with a
16 KiB limit. A missing profile is created with the enabled moderate balance
below, then read through the same bounded parser. An existing disabled or invalid
file is preserved; invalid input retains native behavior and reports the reason.
The matching operator template is
[config/hollow-country-stamina.json](../config/hollow-country-stamina.json):

```json
{
  "SchemaVersion": 1,
  "Profile": "custom",
  "Experimental": true,
  "Settings": {
    "SchemaVersion": 1,
    "Enabled": true,
    "ContinuousExertionScale": 0.5,
    "RecoveryScale": 1.25
  }
}
```

Both `Experimental` and `Settings.Enabled` must be true for isolated experimental
activation. Scales must be finite within `0.05–5.0`. This balance halves
continuous movement drain and multiplies positive recovery by 1.25; native
jump/melee depletion and weight-based capacity remain intact.
To disable it explicitly, set both flags false and both scales to 1.0;
`Profile: "vanilla"` requires disabled settings and unit scales.
Restart the mission and reconnect clients after editing. The server carries the
settings in native gameplay configuration; the client admits only the native
server receipt during an active session. Session reset clears activation.

Run 046 compiled the earlier default-off wiring in normal DayZ Server under Wine.
Enabled loading, native network delivery/order, prediction, reconnect and rendered
HUD agreement still require qualification before production use.

## Native compile gate

The gate packages `mods/HollowCountry` and calls the existing Wine compiler
probe. Supply a complete isolated server copy on a Linux filesystem and its
reusable Wine prefix. **Execution launches `DayZServer_x64.exe` and stops its
owned process group**; the active session must permit this. The probe refuses
another Linux-visible DayZ server. Never use the live server installation.

```sh
python3 -B tools/release/compile_gate.py --server-root "$HC_SERVER_ROOT" --prefix "$HC_WINE_PREFIX"
python3 -B tools/release/compile_gate.py --commit 37e68fb4 --server-root "$HC_SERVER_ROOT" --prefix "$HC_WINE_PREFIX"
python3 -B tools/release/compile_gate.py --commit HEAD --server-root "$HC_SERVER_ROOT" --prefix "$HC_WINE_PREFIX"
```

`--tree "$HC_CHECKOUT"` selects another checkout (default: current directory).
`--commit` exports the exact tracked commit into a temporary detached source tree
under `~/.cache/hollow-country/compile-gate/` and removes it even on failure.
`git archive` is used instead of a worktree, so the gate never writes Git
metadata. Uncommitted files are excluded in commit mode.

Exit is nonzero for `Can't compile`, `Cannot compile`, any `SCRIPT (E)`
(conservatively including cascades), missing/incomplete logs, crash, timeout,
input drift or failure to initialize. Output includes up to twelve first
privacy-filtered errors and `wall_seconds`, including packaging and cleanup.
Raw logs stay in fresh cache run directories outside Git. `--seconds` controls
the probe budget (15..900, default 300; use 900 on a busy host); staging and cleanup add to wall time.
Only content-addressed PBO bytes, the isolated install and Wine prefix are
reused; profiles, storage and compile observations are always fresh. No compiler
speedup is established. Wine compilation does not accept native Windows boot,
module readiness, gameplay, client delivery or multiplayer behavior.

**History validation, 2026-11-19.** `--commit 37e68fb4` failed natively in
42.6 s with the six `Undefined function 'HCInteriorMeasuredCatalogCursor.HCAt'` /
`HCRange` / `HCSetContent` errors that broke that build (lint HC-E012 reports the
same six). `--commit HEAD` (5218d8de) compiled GameLib, Game and World without a
`SCRIPT (E)` line, then timed out at 300 s while loading the world, before the
Mission module. The host load average was about 35 on 14 cores (a Windows server,
Workbench and four workers). A HEAD pass under the 900 s budget on a quiet host is
still unmeasured.

**Headless Workbench: unverified / blocked.** The `HC_TxaBuild.c` pattern and
installed `dayz.gproj` syntax informed this planned single-instance invocation:
`workbenchApp.exe -gproj=<Windows-TEMP-scratch>/hc_compile.gproj -wbmodule=ResourceManager -plugin=HC_CompileGateExit -doLogs`.
The scratch project would combine native modules with `37e68fb4` HC scripts;
the plugin would call `Workbench.Exit(0)`. The controller had a 900-second outer
timeout, reserved cleanup time and kill restricted to its own PID, with
stdout/stderr and scratch `.log`/`.rpt` files as proposed error channels.

Absolute `cmd.exe`/`powershell.exe` interop works despite absence from PATH.
`cmd.exe /c echo %TEMP%` resolved in 0.065 s; no D: scratch writes were attempted.
The guarded attempt returned in 10.095 s without a compile receipt. Follow-up
inspection confirmed one Workbench instance predating the attempt and no
experiment scratch directory. The guard prevented a second instance; no owned
PID was created or killed. TEMP write/staging, machine-readable compiler errors,
catching HCAt and speed relative to Wine remain unverified. Retry when the
existing Workbench has exited and isolated Wine execution is authorized.

## Fixed native observation probes

The development helpers provide fixed disposable missions for infected death and
fuel-transfer observations. Inspect their CLI options before supplying isolated
server, prefix, PBO, native-interface and fresh experiment paths:

```sh
python3 -B -m tools.setup.wine_compile_probe --help
python3 -B -m tools.setup.fuel_probe_runner --help
python3 -B -m tools.setup.native_startup_runner --help
```

The death purpose is `--infected-death-scripts`; fuel requires explicit
`--execute` and bounded fixture inputs. Initialization cannot finish either
purpose. Fresh nonces, admitted receipts and confirmed owned-entity cleanup are
required. A fixed internal fixture watchdog remains 60 seconds; an explicit
outer budget allows map startup and process cleanup. The original 90-second
attempts timed out before mission initialization and remain failed attempts.
Server observations cannot establish rendered corpse physics, player input,
connected-client action behavior or durable save recovery.

The actor-free startup control records entry/exit around mission lifecycle,
CreateHive and InitOffline, plus real SYSTEM update and queue callbacks. Its
explicit `ce-disabled-control` mode omits only InitOffline for comparison with
`stock-ce`; it is a diagnostic environment, not a gameplay profile. Run the
controls serially against fresh directories. A returned mission initialization
message does not establish that main or economy initialization has completed.
The runner rechecks the complete staged mission and launch inputs after cleanup.
Consume its persisted reports through `native_startup_runner.read_report()` and
require a zero CLI exit. A sibling `.pending` file marks incomplete publication;
reading a success-shaped JSON file alone is insufficient. Verified readback and
rename do not establish filesystem crash durability or authenticate the engine.

## Validation order

The [local connection guide](LOCAL_SERVER_TEST.md) records the explicit game and
Steam query port launch and the observed vanilla Windows baseline. Vanilla join,
movement, inventory and reconnect passed on 2026-11-17; addon loading and feature
acceptance remain separate.

1. Run unit tests, operator settings admission, repository hygiene and executable
   offline BDD. These validate authored policies, data and tooling.
2. Build with the installed official Tools; load the addon into DayZDiag and a
   normal dedicated server. Capture exact build/source/package hashes, compiler
   output and native self-test logs. A PBO container checksum is not a signature.
3. Test individual features, then combined flags, against their tracked issue
   acceptance criteria. Include malformed inputs,
   cancellation, full inventories, concurrency, crash/restart and save recovery.
4. Use at most one real client for server delivery, authority, visibility and sound, then
   measure representative workloads against calibrated performance budgets.
5. Sign with a private key kept outside Git; hand off only approved authored
   content, signatures and the public verification key. Exercise clean rollback.

Record unobserved acceptance in the
[issue tracker](https://github.com/d-addison/hollow-country/issues).
A vanilla server startup is not a mod smoke test. Test experimental packages
against disposable storage and retain signature verification for signed loading.

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
