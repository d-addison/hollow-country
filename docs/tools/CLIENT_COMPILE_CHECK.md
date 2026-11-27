# Client compile evidence (#369 item 2)

Option **(b)** is the supported path: a lead checks logs from one real client.
No native experiment was run to qualify a headless client compiler for this change.
The Wine gate explicitly launches `DayZServer_x64.exe`
(`tools/release/compile_gate.py:3`, native invocation at `:474`). Workbench's
qualified route compiles at GUI startup (`tools/release/wb_compile.py:3`),
excludes dependency sources (`:73`–`:82`), and stages only the two required
script addons plus its probe (`:298`–`:339`), without the test addon's client
driver. Neither wrapper implements a client-defines switch or qualifies the
same staged PBO stack without SERVER. A new defines flag alone would not prove
that coverage. The existing real client path uses `DayZ_BE.exe` with
`-exe DayZ_x64.exe`, `-profiles` and `-doLogs`
(`tools/testing/soak_campaign.py:667`–`:671`, launcher at `:746`).

## Lead one-client check

1. Select the exact candidate commit and its bundle/BUILD_MANIFEST.json. Use the
   same client PBOs and dependency versions as that bundle. Include the dev-only
   test addon when testing the campaign driver. Record the candidate alongside
   the retained logs; the parser cannot establish build provenance from text.
2. Use the existing locked R3 launcher (`tools.release.release_gate`, scripted
   default or `--client-mode human`) or the locked `tools.testing.soak_campaign
   run --yes` flow. Never launch alongside the owner's session. Keep the existing
   bounded startup/join/soak budgets; R3's `--client-timeout` is 900 seconds by
   default and at most 3600. The read-only parser itself starts no processes and
   needs no host lock.
3. Use a fresh isolated client profile with `-doLogs`. Retain its client RPT and
   **every script log from that same launch**, including a failed startup that
   never reaches the menu. Do not substitute the server RPT. Archive failed logs
   before another attempt; do not mix previous sessions in the profile.
4. Reach the menu, join the server, then open the map/group controls, inventory
   and admin window; exercise the existing AI/event route. A compile dialog,
   failed startup or absent completion evidence is a hard failure. Preserve the
   ordinary VME/texture and activity checks. A menu-only compile check does not
   satisfy the full smoke.
5. After the client exits, run the checker below. No compile errors plus either
   `Module: Mission; loaded <positive count>x files` in the captured logs or
   `[HC Driver] step=<step id> kind=<kind>` establishes compile completion
   (the receipt is emitted by `5_Mission/HCClientDriverSteps.c:91`). A Game-layer
   connection trace alone does not establish Mission compilation. Missing,
   unreadable, oversized or incomplete evidence fails. Warnings alone do not
   fail. Compile-class lines are `Can't compile` / `Cannot compile`, `Compile
   error`, `Multiple declaration of function`, `Script validation failed`, and
   failed/unable/cannot script or module loads. These remain compile-class even
   inside `SCRIPT (E)` lines. Other `SCRIPT (E)` lines (any spacing) count as
   `runtime_errors`; they do not fail this compile check. It scans
   at most 32 files, 64 MiB total and 16 KiB per line; exceeding a bound fails.

```sh
python3 -B -m tools.release.client_compile_check --rpt /tmp/hc-candidate/client.RPT
```

By default this reads **all** sibling `script_*.log` files as well as the RPT.
With explicit logs, repeat `--script-log` for every script log belonging to the
launch. A clean verdict is:

```text
client_compile_check: PASS reason=clean logs=<count> errors=0 runtime_errors=0 complete=true
```

Only counts and reason codes are printed; log lines and paths are not echoed.
`errors` (also exposed as `compile_errors` in the result dict) counts only
compile-class lines. `reason=compile_errors` takes precedence over completion;
otherwise the reason is `clean` or `completion_missing`. Runtime-only logs with
completion produce PASS/exit 0 while showing a positive `runtime_errors` count;
missing completion still produces FAIL/exit 1. Invalid/unavailable logs also fail
closed. The release still requires zero client `SCRIPT (E)` and zero VMEs:
`release_gate` refuses `runtime_errors` above `max_script_errors` (RPT plus every
script log; its RPT audit alone would miss script-log-only errors), and the
campaign report adds a `client_script_errors` audit row (`zero` when any were seen,
exit 8). `activity_check` / `rpt_summary` verification remains mandatory.

Exit status is 0 for PASS, 1 for failed evidence. This check adds no gameplay
feature or `[HC Use]` counter. Existing smoke counters remain mandatory.

## Build-185 regression proof (lead, pending)

The old client log is not in the repository. Copy the **original failing
build-185 client RPT** to `/tmp/hc-build185/client.RPT` and its same-launch script
log to `/tmp/hc-build185/script.log` (repeat the flag if there are more). Then run:

```sh
python3 -B -m tools.release.client_compile_check --rpt /tmp/hc-build185/client.RPT --script-log /tmp/hc-build185/script.log
```

Expected: exit 1 and `client_compile_check: FAIL reason=compile_errors` with
`errors` greater than zero. The source evidence should contain
`Multiple declaration of function 'Connect'` and may also contain
`Can't compile "Game" script module!`. No completion marker is needed to reject
this failure. These are diagnostic signatures, not a claim to have inspected the
missing historical log. If it cannot be recovered, the lead must retain logs from
an isolated known-bad build-185 client launch through the same locked procedure;
a synthetic test establishes parser behavior only. Repeat with the fixed exact
candidate and require PASS plus the full smoke's existing `[HC Use]` evidence.

## Campaign and R3 plumbing

The campaign checks for client compile errors while waiting for a join, using
both RPT and sibling script logs; compile-class errors follow the existing
graceful cleanup path. The first runtime-class error logs one verdict without
aborting the campaign so verification retains the rest of the soak evidence.
Driver polls reuse unchanged file metadata and read appended bytes from the last
complete line, rechecking unfinished lines. Truncation, replacement or same-size
edits restart that file; the cache retains only the current bounded set of logs.
Its final report always adds an `audit / client_compile / join` result. FAIL
counts as broken and makes `report`/`run` return 8 even when activity counters
would otherwise pass. Missing/incomplete logs cannot become an active result.

R3 checks the same evidence on each client smoke poll and again before accepting
positive activity counters. A failure raises `client compile check failed:
<reason>`, fails the `client` step and yields `release_gate=FAIL`. The existing
shared host lock and cleanup remain in force. Both integrations discover sibling
script logs, so fresh profile isolation is required; old compile diagnostics fail
conservatively and old runtime errors remain in the reported counts. Neither
the checker nor offline tests prove multiplayer behavior
or replace the lead's exact-commit R3 native experiment.
