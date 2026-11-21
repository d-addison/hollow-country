# Experimental headless Workbench compile check

**Native qualification pending.** This is developer tooling, not a replacement
for the native server compile gate or boot/readiness checks. No speedup, gameplay
or multiplayer result is established. The current tree and deliberately broken
scratch-copy controls have **not** run through Workbench in this session.

Run from the repository root in WSL, with Windows DayZ Tools installed:

```sh
python3 -B -m tools.release.wb_compile
python3 -B -m tools.release.wb_compile --commit HEAD --seconds 120
python3 -B -m unittest tests.unit.test_wb_compile -v
python3 -B -m tools.validate.enforce_lint --native-scripts ~/.cache/hollow-country/native-scripts/scripts-1.30.164289
```

`--tree PATH` selects an authored tree; `--commit COMMIT` uses the existing
compile gate's read-only `git archive` snapshot helper. It never writes git
metadata. An older commit without `HC_CompileCheck.c` cannot run this plugin.
The default is the current tree, including edits. `--workbench PATH` and
`--native-scripts PATH` override the installed-tool and native-source locations.
`--action-path 'Validate Scripts'` is the **unverified** candidate menu path;
slash-separated parent menu labels can be supplied after inspecting the UI.
The plugin source and installed project template must be available.

The driver prints one JSON object. Exit 0 requires the native engine text
`Script validation successful.`, the plugin's `action_returned` receipt, tool
exit 0, complete bounded captured logs and no error. Errors take precedence over
success. Compile failures, tool failures, incomplete evidence and timeout exit 1;
preflight/staging/controller failures exit 2. `errors` contains `file`, numeric
`line` and privacy-filtered `message`. Unknown locations are null, not invented.
For example, native `SCRIPT (E)` followed by `scripts/4_World/file.c(42)` becomes
`{"file":"scripts/4_World/file.c","line":42,...}`. Identity-bearing diagnostics
are suppressed after determining the failure verdict, so privacy filtering
cannot turn a failure into a pass. `route_qualified` remains false even if a run
returns `passed`, until the controls below establish this route's behaviour.

## What is implemented

- Select authored script roots through `ship_inputs.signing_inputs()`, also
  used by `compile_gate`; currently base HC and the Expansion AI adapter.
  Animation PBOs have no script root. It does not duplicate the release catalogue.
- Copy only `.c` sources into a unique Windows `%TEMP%/hc-wbcompile-*` directory;
  reject symlinks. Copy native modules 1–5 and native editor/Workbench sources,
  plus the original HC plugin. No native/Workshop code or assets enter git.
- Derive the scratch `.gproj` from installed `dayz.gproj`, retaining native
  module names, order and entry points. Append selected HC paths to the matching
  native module Paths blocks. The game filesystem root points at the scratch
  directory. Template shape drift fails closed.
- Invoke `WorkbenchApp.exe -gproj=<scratch>/hc_compile.gproj
  -wbmodule=ScriptEditor -plugin=HC_CompileCheck
  -hcCompileAction="Validate Scripts"`, with the executable's folder as cwd.
  The plugin dispatches `ScriptEditor.ExecuteAction(menuPath)` and exits.
- Refuse an existing Workbench instance or unknown process state, query again
  inside a Windows named mutex immediately before launch, and never retry a
  launch. PowerShell retains the started process object, waits for the bounded
  deadline, and kills only that object on timeout or exceptional cleanup.
  It never kills by name or touches a pre-existing process. A manually launched
  Workbench can still race the last check; the mutex coordinates these drivers.
- Capture redirected stdout/stderr and scratch `.log`/`.rpt` files, up to 16 MiB
  total. No shared tool/profile logs are read or deleted. Scratch sources/logs
  are removed after confirmed completion. If controller/cleanup confirmation is
  lost, the unique TEMP folder is retained for local recovery; do not delete it
  until the owned process has exited. A Python outer timeout leaves Windows ownership
  with the controller (it does not kill PowerShell and abandon its child),
  reports cleanup unconfirmed, and never infers successful compilation.

## Observed versus assumed

Read directly from installed DayZ Tools `Bin/Workbench/dta/scripts.pbo`:

| Installed declaration | Observation |
| --- | --- |
| `1_Core/WorkbenchAPI/Modules/ScriptEditor.c` | No direct compile/reload method |
| `1_Core/WorkbenchAPI/Modules/WBModuleDef.c` | `ExecuteAction(array<string> menuPath, bool bKeepFocus=true)` returns bool; `GetCmdLine` exists |
| `1_Core/WorkbenchAPI/Workbench.c` | `GetModule`, `Exit(int)`, `GetWBGameScriptModule`, `GetWBScriptModule` exist |
| `1_Core/WorkbenchAPI/Plugins/WorkbenchPlugin.c` | `RunCommandline` event exists |
| Installed `dayz.gproj` | Native core/gameLib/game/world/mission/workbench paths and syntax |

The prior `tools/anim/workbench/HC_TxaBuild.c` supplies the plugin launch pattern.
The installed executable's strings contain `-gproj`, `-wbmodule`, `-plugin`,
`-validate`, `&Validate Scripts`, `&Reload Scripts`,
`Script validation successful.` and `Script validation failed.`. These strings
are static observations, **not a successful CLI or menu-action experiment**.
No `-help` launch was made while Workbench was running. `-validate` is not used:
its semantics have not been observed.

Still assumed/unverified: the candidate single-element action path, whether
ExecuteAction blocks until validation finishes, whether the engine logs its
completion on a captured channel, scratch filesystem mounting in native
Workbench, and validation of every intended preprocessor variant/module.
If action dispatch is asynchronous or logs only to an uncaptured shared log,
the driver returns nonzero for missing completion evidence. A zero tool exit or
plugin receipt alone cannot pass. The API's bool proves action dispatch only.

The default project does **not** stage the declared Workshop dependency script
stack, generated guards, CfgMods/config changes, addon config definitions or
release-time animation inputs. The adapter may report missing dependency types.
Do not suppress these errors or label a base-only check as full-stack acceptance.
A validated dependency-mount strategy remains lead work before using this as a
required full-release gate. `ship_inputs` selects the same authored catalogue;
this tool does not claim input equivalence with the server compile gate.

Session observations (2026-11-21): the initial read-only process query found an
existing Workbench, so no launch occurred. A subsequent driver invocation found
it gone, resolved Windows TEMP, then returned `status=unavailable`, exit 2:
`Read-only file system` creating its unique TEMP directory through the WSL mount.
No Workbench process was started, so neither native compile control ran.
Focused Python tooling tests: 9 passed. Required native-aware lint:
`pass findings=1 new=0 stale=0 native=yes`; performance lint `new=0`.
The repository lint scans its configured source scope; this is not native
compilation of the new Workbench plugin. The worker was forbidden to start game
executables, so the server compile gate remains for the lead.

## Lead qualification commands

After closing Workbench normally and using a WSL environment with a writable
Windows TEMP mount:

```sh
python3 -B -m tools.setup.winproc query WorkbenchApp.exe
python3 -B -m tools.release.wb_compile --tree "$PWD" --seconds 120
```

Expected first command: `state=gone` (its query exit code is 1). Preserve the
second command's filtered JSON and wall time. If it returns unverified or
`action_refused`, inspect the Script Editor menu labels and rerun with the exact
observed `--action-path`. Do not accept an invented menu path or missing engine
completion receipt. Observe whether validation is synchronous before changing
plugin exit timing. Resolve the full declared dependency mount before claiming
a complete HC/adapter pass.

Create the deliberately broken control entirely in local scratch, never in the
worktree, and run the same driver against it:

```sh
scratch=$(mktemp -d /tmp/hc-wb-broken-XXXXXX)
mkdir -p "$scratch/mods" "$scratch/tools/workbench"
cp -R mods/HollowCountry mods/HollowCountryExpansionAI "$scratch/mods/"
cp tools/workbench/HC_CompileCheck.c "$scratch/tools/workbench/"
cat > "$scratch/mods/HollowCountry/scripts/3_Game/HCCompileBrokenControl.c" <<'CONTROL'
class HCCompileBrokenControl
{
    void Probe()
    {
        HCCompileDeliberatelyMissingType broken;
    }
}
CONTROL
python3 -B -m tools.release.wb_compile --tree "$scratch" --seconds 120
rm -rf -- "$scratch"
```

Require nonzero exit, `compile_failed`, and an error for
`HCCompileBrokenControl.c:5`. This scratch control is not a unit test or
translator harness. Failure at another missing dependency does not qualify the
control: first resolve the baseline dependency stack and get a clean pass.
No game process is started by these commands.

For the separate native server gate, the lead can run the existing authorized
isolated environment command:

```sh
python3 -B -m tools.release.compile_gate --commit HEAD
```

That command starts a server and was not run by this worker. To wire Workbench
into `compile_gate.py` later, invoke this module as a bounded preflight, consume
its JSON/exit code, and retain the native server check until both controls and
stack/define/module equivalence are proven. No change to `compile_gate.py` is
included here. Missing prerequisites must remain an explicit failed/unverified
preflight, never a successful compile receipt.

Writer handoff: this new document is ignored by the repository rule `/docs/*`.
The lead must arrange its inclusion through the shared ignore-policy change; this
worker owns neither `.gitignore` nor git metadata and did not alter either.
