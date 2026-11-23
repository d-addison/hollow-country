# Workbench script compile check

Developer preflight: DayZ Tools Workbench compiles the full script stack
(game data, Workshop dependencies, our packed addons) in about 3-4 minutes with
no manual clicks. It does **not** replace the native server compile gate, boot
or readiness checks (truth order: native boot > compile gate > lint > tests).

**Qualified 2026-11-21** on WorkbenchApp.exe sha256 `16085382d1c2609b…`
(DayZ Tools 1.30): the clean tree passed and a scratch-only broken control
failed at `HCCompileBrokenControl.c:5`. `route_qualified` is true only for a
passing run on a build listed in `QUALIFIED_WORKBENCH` in
`tools/release/wb_compile.py`. A new DayZ Tools build stays unqualified until
both runs below are repeated and its hash is added.

```sh
python3 -B -m tools.setup.winproc query WorkbenchApp.exe   # must print {"state": "gone"}
python3 -B -m tools.release.wb_compile                       # current tree, default --seconds 240
python3 -B -m tools.release.wb_compile --commit HEAD --keep-scratch
python3 -B -m unittest tests.unit.test_wb_compile
```

Exit 0 = `passed`; 1 = `compile_failed`, `wb_only`, `unverified`, `timeout`,
`incomplete_logs` or `tool_failed`; 2 = blocked (Workbench already running),
`controller_failed` or `cleanup_unconfirmed` (scratch kept; do not delete it
until the owned Workbench has exited).

## Route

`WorkbenchApp.exe -loadAddons -mod=<deps;@HollowCountry;@HollowCountryExpansionAI;@HCWorkbenchTool>
-profiles=<scratch>\profile -wbmodule=ScriptEditor -plugin=HC_CompileCheck`, cwd
`Bin\Workbench`.

- `-loadAddons` mounts the installed game data; Workbench's game runtime then
  compiles every script module (GameLib, Game, World, Mission) at start.
- Dependencies are the compile gate's `compatibility_inputs` Workshop items,
  mounted read-only in place from the Workshop content folder. No Workshop code
  is copied into the repo or the scratch, except the partial exclusion below,
  which copies the remaining PBOs of one item into the Windows TEMP scratch only.
- Our two addons are packed into `%TEMP%\hc-wbcompile-*` from the selected tree
  (`--tree`, or `--commit` via a read-only `git archive`).
- The scratch tool mod `@HCWorkbenchTool` adds one probe file per module that
  references an authored class from that module and raises a marked
  `[Obsolete("hc_wb_probe <module>")]` warning. All three markers present
  proves our files were inside the compiled modules. Observed:
  Game 995 files, World 3785, Mission 684.

The verdict comes from the logs only: `passed` requires Mission loaded, all
three probe markers, no blocking diagnostic, complete logs and a confirmed
owned-process exit. A zero exit code or plugin receipt alone never passes.

## Popups and dialogs (no manual clicks)

No command-line flag or setting suppresses the authorization prompt (none in
the exe strings or the Workbench script API). The controller answers exactly
three dialog kinds. Each is matched by exact title and by
`GetWindowThreadProcessId` == the PID of the Workbench it started. The answer is
a message posted to that one window: no focus change, no `SendKeys`, no global
input, no clicks on coordinates. Each kind has a per-run limit.

| Dialog | Source | Answer |
| --- | --- | --- |
| `Script Authorization Required` | a vanilla or dependency script asks to call `OpenFile` | **N&o to All** (`O` mnemonic). Denying is the safe direction: no script gains file access; the compile does not need it |
| `Error: Plugin<Name>` | DabsFramework Workbench plugins fail to load a project.cfg (7 per run) | OK (Enter) |
| `Enfusion engine`, class `#32770` | engine assertion at shutdown, `enf_scriptmodule.cpp` line 599 "Script is leaking!" (2 per run) | Ignore (`IDIGNORE`); Abort would end the process abruptly. The text is also in `crash_*.log` |

Once `Module: Mission` (or a compile failure) appears in `script_*.log`, the
controller waits 5 s, then posts `WM_CLOSE` to the owned `Workbench - *` main
window. It answers the shutdown assertions and repeats the close request at most
3 times, 20 s apart, within 150 s. It never uses `Stop-Process`, `taskkill` or
`.Kill()`. A refused shutdown reports `cleanup_unconfirmed`.

The controller runs as a detached Windows PowerShell from `<scratch>\controller.ps1`
(shell-execute, so no inherited WSL handles). It writes `controller-started.txt`
and an atomic `controller-receipt.json`. WSL interop drops
(`UtilAcceptVsock ... accept4 failed 110`) killed the earlier pipe-attached
controller while Workbench stayed open. Python now only reads the receipt file.
The launch is never retried. A named mutex and an in-lock `Get-Process`
re-check prevent a second Workbench.

## Logs

Read from `<scratch>\profile` only: `script_*.log`, `error_*.log`,
`warning_*.log`, `crash_*.log` (bounded at 16 MiB). `stderr.txt` is never read:
the Steam client writes a Steam ID there. Messages are masked (home folders,
17-digit ids) and filtered with `rpt_summary.filtered`. Classification uses the
masked line so a dropped message keeps its location. Duplicate lines repeated
across `script_*` and `error_*` count once. `--keep-scratch` keeps the folder.

Classes: `ours` (HollowCountry, HollowCountryExpansionAI or the tool mod path),
`known_vanilla` (`KNOWN_VANILLA` patterns or a `scripts/N_*` vanilla location),
`dependency` (any other mounted mod location), `probe` (our markers),
`compile_failure` (`Can't compile`, `Failed to load ... script`),
`wb_only` (below) and `unclassified`. Blocking: `ours`, `compile_failure` and
`unclassified` errors. A bare engine `Assertion failed` header is read together
with its `Reason:` line.

### `wb_only`: Workbench-only diagnostics

`WB_ONLY` in `tools/release/wb_compile.py` lists message patterns for
diagnostics that Workbench raises as errors but the Wine compile gate and the
retail server accept (they log the same FIX-ME lines as warnings and compile on).
A match is keyed by the message only, never by file, and wins over the `ours`
location. Current pattern: `Overriding function ... but not marked as 'override'`.

Workbench then aborts the module (`Can't compile "<Module>" script module!`), so
the rest of the stack is unchecked. The verdict is therefore `wb_only`, never
`passed` and never `compile_failed` for that cause alone:

- `status: wb_only` only when every blocking error is a module-abort line
  (`Can't compile "X" script module`, `Failed to load X script`) beside a
  `wb_only` entry. The entries are listed under `wb_only` with their location.
- Any other error in the same output (ours, unclassified, `Script validation
  failed`, a cascade such as `Bad type`) keeps `compile_failed`. Nothing is
  suppressed.
- A `wb_only` line in a run that still reached Mission with every probe marker
  and no other error is `passed`; the entry is still listed.

Observed 2026-11-22 in the calibration corpus: a historical parent where the
`modded class ObjectSpawnerHandler` redefined the vanilla static
`SpawnObjects()` without `override` was reported at
`HCGroundObjectSpawner.c:8`. DayZDiag refuses the same source
(commit `a74d2879`); the Wine gate and retail compile it. The raw Workbench line
was not kept, so the pattern uses the documented wording. The next calibration
run confirms it: see below.

## Triage (clean tree, 2026-11-21)

| Class | Errors | Warnings | Content |
| --- | --- | --- | --- |
| (a) ours | 0 | 0 | after the fix below |
| probe | 0 | 3 | one marker per module |
| (b) dependency | 2 | 0 | DabsFramework Workbench plugin VM exception, `pluginlaunchgamebase.c:5` NULL `launch_settings` (editor plugin, not game code) |
| (c) known vanilla | 11 | 129-152 | shutdown leak report (`Leaked '...' script instance`, `Total Leaks`) and its assertion; `Missing script declaration` / `Method not linked` (CF `cf_lifecycleevents.c`, vanilla `areadamage.c`, `human.c`, `object.c`, `game.c`); one vanilla `is obsolete` |

The noise below is plain engine output, not a `SCRIPT (E/W)` diagnostic, so it
never counts toward the verdict. Per run: ~955 `No entry` (CfgWorlds/CfgVehicles/
heatHazeNoise), 16 imageset `Unknown object type`, 20 `skeletons.anim.xml`,
12 `.emat`, 5 `STR_DN_*`. UAGestureSlot/UAEmote duplicates, Heli InputAccess,
offline shader cache, DayZSetting.xml and "Config file deleted" are seen only in
the Workbench console. They are listed in `KNOWN_VANILLA` in case they reach a log.

Class (a) fixed (2026-11-21): `HCGroundObjectSpawner.c`. The `modded class
ObjectSpawnerHandler` redefined the vanilla static `SpawnObjects()` and
`SpawnObject(ITEM_SpawnerObject)` without `override`; Workbench could not compile
Game. Both are marked `override static` (commit `91a364d1`). Historical commits
before it still trigger the Workbench-only diagnostic, which is now `wb_only`.

## Dependency exclusions (Workbench only)

Workbench compiles `FIX-ME` diagnostics as errors; the game runtime and the
server compile gate log the same lines as warnings and compile on. Two
dependency sources therefore stop Workbench's World module and are left out of
its mount. Each run reports them under `inputs`:

- `2646817942` (Tactical Flava), whole item: `script_a` has brace-less method
  bodies, `Missing function scope` x12. Neither HollowCountry nor
  HollowCountryExpansionAI requires it.
- `3114410963` (Ambient Animals), only `dayz_seagull.pbo`:
  `seagull_base.c,110 Unmatched brackets` x1. HCX needs this item's otter,
  rat, raven and squirrel addons, so its other PBOs are mounted.
- Uncovered: `hollowcountry_weapon_pack_guards.pbo` requires `script_a` and
  is not mounted. The server compile gate covers it.

## Broken control (qualification)

Build it in a scratch copy only, never in the worktree:

```sh
scratch=$(mktemp -d /tmp/hc-wb-broken-XXXXXX)
tar --exclude=./.git --exclude=./.claude -cf - . | tar -C "$scratch" -xf -
cat > "$scratch/mods/HollowCountry/scripts/3_Game/HCCompileBrokenControl.c" <<'CONTROL'
class HCCompileBrokenControl
{
    void Probe()
    {
        HCCompileDeliberatelyMissingType broken;
    }
}
CONTROL
python3 -B -m tools.release.wb_compile --tree "$scratch"
rm -rf -- "$scratch"
```

Observed: exit 1, `compile_failed`, first error `ours`
`HollowCountry/scripts/3_Game/hccompilebrokencontrol.c:5` "Unknown type
'HCCompileDeliberatelyMissingType'", then `Can't compile "Game" script
module!`. Cascade `Bad type 'JsonFileLoader'` errors follow, and they are absent
on the clean tree.

## Shared host helpers

`wb_compile`, `diag_session` and `wine_compile_probe` take WSL/Windows path
translation, PowerShell quoting and link/reparse refusal from
`tools/setup/probe_core.py`; host locking is the shared `tools/release/host_lock.py`
lease. Translation is lexical and covers `/mnt/<drive>` paths only: a non-drive
path, `..`, a reserved Windows name or a control character is refused before any
Windows command runs (no `wslpath` call). Each module keeps its own isolation
policy on top (`wine_compile_probe.safe` still refuses Steam, `.git` and the
checkout; `diag_session.windows` also refuses `;`, quotes and newlines).

## Not qualified

- `HC_CompileCheck` `RunCommandline` was never observed firing (its prints never
  appear), so `plugin_returned` and `script_editor_validation` stay false. The
  verdict does not depend on them.
- Workbench is stricter than the runtime for `FIX-ME`. The excluded dependency
  sources and the guard PBO are compiled only by the server gate.
- This is a compile check: no boot, config runtime, gameplay or multiplayer
  result. The native server compile gate remains required for Enforce changes.

## Calibration

The historical corpus in `tools/release/wb_calibrate.py` records native compile
fixes and their reasons from git subjects. Every fix must exist and its first
parent must be an ancestor of local `main`; the runner validates the entire
corpus before launching a compiler, even with `--only`.

Lead only, while the owner is not playing: run the current drivers against
read-only snapshots of each fix's parent (expected `compile_failed`) and fix
(expected `passed`). Workers test this orchestration with fakes and never start
Workbench or the native gate. Calls are sequential; the drivers retain their
own shared host locking. A missing Workbench installation refuses the run.

```sh
python3 -B -m tools.release.wb_calibrate --out /tmp/hc-wb-calibration
python3 -B -m tools.release.wb_calibrate --only 47f27ad5 386809e1 --gate --out /tmp/hc-wb-calibration-native
python3 -B -m unittest tests.unit.test_wb_calibrate
```

`--out` is a directory outside the repository; it receives `agreement.json`
and `agreement.md`. Without it a unique `hc-wb-calibrate-*` directory is created
under the job's `TEMP` (or Python's temporary directory). Locations in reports
are source-relative or basenames. Each row side references a sibling `<fix>-<side>.log`
containing at most the last 200 lines (each capped at 2,000 characters) of tool
stdout/stderr, with home folders, 17-digit ids and identity-bearing diagnostics
redacted before writing. No raw output is printed. Reports checkpoint after every invocation.
Use a distinct output directory for each run to retain previous evidence.

`--gate` also runs the native gate at each parent. Its verdict requires the
gate's terminal `FAIL status=compiler-error` plus an emitted source script error
or compile-failure diagnostic, or `PASS status=initialized|timeout|mission-loaded-runtime-json`
with the explicit zero-error Mission message. Missing/ambiguous verdicts,
preparation-only output, prerequisites, crashes, other failure statuses and
inconsistent exit codes stay unverified with a reason and an output tail. The first available error `file:line` is
recorded for Workbench and native failures. A parent accepted by Workbench, a
fix rejected by Workbench, or a native verdict differing from Workbench is a
disagreement. Inconclusive outcomes are checkpointed and remaining sides/rows
continue by default; `--stop-on-inconclusive` restores early stopping. The
summary counts agree, disagree, inconclusive, incomplete (pending sides) and
expected-only rows. Any inconclusive/incomplete evidence yields exit 2 even
when other rows disagree.

An exact prelaunch `blocked` / `Workbench process state: unknown` result retries
the driver at most twice with exponential backoff (0.5 s, then 1 s; three state
queries total). The driver returns this result before staging or launching
Workbench. Running processes and all post-launch outcomes are never retried. Each
WB receipt records `state_query_retries`; exhausted unknown queries remain
inconclusive.

A `wb_only` WB side (see Logs) is neither agreement nor disagreement: the row
counts under `wb_only` in the summary, its first error is the Workbench-only
location, and the native parent verdict is still recorded. The run exits 2
(status `wb_only`) unless a row disagrees (exit 1) or has inconclusive evidence
(exit 2, `incomplete`). `--stop-on-inconclusive` does not stop on `wb_only`.
Never read a `wb_only` row as WB agreement.

Calibration review notes (each checked against the code and its test):

| Note | State | Where |
| --- | --- | --- |
| Tail per row side | implemented: bounded, redacted `<fix>-<side>.log` referenced from each side | `test_persists_redacted_bounded_tail_and_reference`, `test_output_tail_redacts_json_escaped_windows_folder_and_identity_fields` |
| Continue after an inconclusive row | implemented: default continues, `--stop-on-inconclusive` stops | `test_inconclusive_continues_all_sides_and_rows`, `test_explicit_stop_on_inconclusive` |
| Retry the Workbench state query | implemented: prelaunch `unknown` only, two retries with exponential backoff, never after launch | `test_unknown_prelaunch_state_retries_but_running_does_not` |
| WB-only diagnostic | implemented: `wb_only` class and status, keyed by message | `test_wb_only_override_diagnostic_is_not_a_failure_but_never_a_pass`, `test_wb_only_never_hides_another_error_or_missing_evidence`, `test_wb_only_row_is_neither_agreement_nor_disagreement` |
| `wiring_audit --ratchet` and CfgAmmo | fixed: CfgAmmo is a configured root and a missing root only retains the baseline entries that depend on it, so `--ratchet` no longer refuses; with the installed index it reports `Ratchet missing roots: none` | `tests.unit.test_wiring_audit` (`test_ratchet_prunes_independent_entries_with_missing_roots`) |

The table below is filled only from lead runs of the full corpus with `--gate`;
a row without a native result stays blank rather than being inferred.

Calibration status: 0/13

Current state (2026-11-22): the orchestration is complete and unit-tested with fakes; no lead
run of the full corpus has been recorded, so no row is agreed. The first lead run must also
confirm the `wb_only` pattern: the rows whose parent still carries the non-`override`
`ObjectSpawnerHandler` redefinitions (before commit `a74d2879`) should report
`wb_parent=wb_only` with first error `HCGroundObjectSpawner.c:8`. If such a row reports
`compile_failed` instead, read its `<fix>-wb_parent.log`, take the exact Workbench line and
correct `WB_ONLY` in `tools/release/wb_compile.py` (add a test with that line).

Lead command for the next run (owner not playing; one instance per host; allow about an hour):

```sh
agent-run --memory 12G -- python3 -B -m tools.release.wb_calibrate --gate --out /tmp/hc-wb-calibration-$(date +%Y%m%d)
```

Then fill the table below from `agreement.md`, set the status line above to
`<agree>/13`, and keep the logs (`<fix>-wb_parent.log`, `<fix>-wb_fix.log`,
`<fix>-native_parent.log`, each at most 200 lines, redacted).

The line above is read by `tools/release/test_queue.py` (agreed rows / corpus rows). Update it
only from a lead run; the second number must equal the number of rows in the `CORPUS` of
`tools/release/wb_calibrate.py` (the docs check fails otherwise).

Exit 0 means all selected expectations matched (`expected_only` without
`--gate`, `agree` with it); 1 means disagreement; 2 means refusal or incomplete
evidence. A subset or `expected_only` result does not qualify replacement of the
native gate. The lead must run the full corpus with `--gate`, investigate every
disagreement and fill the table below. These are compile results only; boot,
gameplay and multiplayer acceptance remain separate.

| Fix | Reason | WB parent | First error | WB fix | Native parent | Agreement |
| --- | --- | --- | --- | --- | --- | --- |
