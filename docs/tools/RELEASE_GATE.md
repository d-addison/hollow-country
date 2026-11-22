# Release readiness gate (R3)

Lead-only native workflow; workers test this tooling with fakes. Python tests
establish orchestration behaviour, never DayZ or multiplayer acceptance.

```sh
python3 -B -m tools.release.release_gate --commit FULL_40_CHARACTER_SHA \
  --bundle /mnt/e/HollowCountryLocal/candidate \
  --previous-bundle /mnt/e/HollowCountryLocal/previous
```

The tool writes `release-gate-verdict.json` (override with `--verdict`) and prints
one JSON verdict plus a short summary. It stops at the first failure. The input
commit must be a full lowercase SHA; abbreviated refs and HEAD are refused.
No publishing, committing or merging occurs. Bundles must remain unchanged
throughout the run. Use an isolated test server with retained storage for upgrades.

Owner targets live in [`config/acceptance-targets.json`](../../config/acceptance-targets.json).
The shared `tools.release.acceptance_targets.load_targets` loader rejects missing or
unknown keys, invalid types and invalid ranges. Missing/invalid policy refuses the
gate before native work and refuses release activity checks. Preland settings
consistency also validates this policy. Boot settle and benchmark fields record
the current checkstart default and provisional owner load; they do not change
checkstart or establish measured benchmark acceptance.

Failed release build children expose only authored refusal lines beginning with
`refused:`, `Refused`, `FAIL` or `error:` from stdout and stderr. The shared
Workbench privacy filter masks home folders and 17-digit identifiers and drops
identity-bearing messages before output is limited to 20 lines of 300 characters.
The command still fails with its short executable-name diagnostic. Preland also
checks HC-E026: two fresh collection factory results in one call are errors;
other fresh argument results are reviewed warnings, with unresolved ownership
reported separately as HC-O026. Native collection Insert/InsertAt adoption is
exempt only where the declared element type is `ref`.

Order:

1. Compile that commit using `compile_gate`; require PASS with
   `mission-loaded-runtime-json` explicitly. Other successful compile statuses
   do not satisfy this release contract.
2. Require the candidate `BUILD_MANIFEST.json` commit to match exactly.
3. Install the previous bundle, boot for a minute, gracefully stop, install the
   candidate with the same server/storage, boot and stop. Refuse error/readiness
   failures and store quarantine evidence. While
   `upgrade_from_previous_release_required` is true, a missing `--previous-bundle`
   refuses the release; only with it false is the step omitted (no upgrade claimed).
4. Install the candidate and run `checkstart --start` with `--settle-minutes`
   from `soak_minutes` and an overall deadline of that duration plus 15 minutes. Audit its one fresh RPT through `rpt_summary` and
   `tick_cost_report.perf_rules`: apply `max_script_errors`, `max_vme_server` and `perf_r2_max_ms` from the
   targets file. Failed self-tests, quarantine and failed/absent readiness refuse.
5. Run `activity_check --release` on the server and fresh client RPT together;
   `activity_requires_active_for_default_on` controls whether INERT features fail.
6. Print the one-tester checklist and wait up to 900 seconds (configurable with
   `--client-timeout`, maximum 3600) for all mapped client features to be ACTIVE
   with positive counts. Apply `client_max_vme`, `max_script_errors` and `client_max_missing_textures`
   from the targets file to client errors.

The tester should join during the soak, open the M map, inventory, group menu
and admin window, and enter an AI site and event radius. The checklist is also
printed before soak so activity can exist before step 5. The client RPT must
be created during this run; stale reports cannot satisfy smoke. Profiles use
the retail Windows LocalAppData/DayZ location, resolved without printing it;
custom launchers can supply `--client-profiles`. The existing Start-LocalClient
launcher does not override retail profiles or expose an RPT discovery API.
Server defaults match `checkstart`; override `--profiles`, `--server-root` and
`--workshop-content` together for a different installation.

## Branch model

Which branch carries what. Passing a gate establishes compile and boot behaviour for
one server plus at most one client, never multiplayer behaviour.

| Branch | Takes | Runs where |
| :--- | :--- | :--- |
| `main` | Server bug fixes and crash fixes only. | The friend server, from the published release bundle. |
| `dev` | The feature and framework waves, and their follow-up fixes. | Local dev and test only. |

- **`main` is the server line.** It takes only bug fixes and crash fixes that the
  friend server needs. No feature, framework or content wave lands on it directly.
  Everything the friend server runs is a commit on `main`.
- **`dev` takes the waves.** Worker branches are cut from `dev` and the lead merges
  them into it. `dev` has its own gate: after a merge the lead runs the pre-land checks
  (`python3 -B -m tools.validate.preland`) and, for any `mods/**/*.c` change, the
  native compile gate until it reaches the Mission marker. A wave is not ready for
  `main` on a compiling build alone.
- **`dev` merges to `main` only after a gated, soaked wave.** The wave must have
  passed the `dev` gate and then a clean soak on the exact commit, with this gate's
  requirements: no SCRIPT (E) error, no VM exception, no perf R2 above 20 ms, and
  every default-on feature reporting activity.
- **At most one release per day.** A release is one published bundle built from one
  `main` commit. A crash fix is the exception to waiting: it ships alone,
  immediately, as its own release, and is not bundled with anything else. Broaden
  the affected feature only after one clean soak of the fix.
- **Unlanded branches are archived, not deleted.** A branch that will not land is
  tagged `archive/<branch>` (for example `archive/hc/w39-wildlife`) before the branch
  is removed. Salvage later from the tag with `git show` or `git diff`; the tag is
  the only record, so tag first.

A release is cut from a `main` commit with `tools/release/*`, which build from a clean
worktree at that commit and write `BUILD_MANIFEST.json`. Bundle data comes from the
repository at that commit, never from a server profile or an old install snapshot.
Nothing lands on `main` while the friend-bundle cycle runs, and the cycle pins an
explicit full commit hash. GitHub Releases and Workshop uploads follow the owner's
approval for that release. The friend runbook is separate and is not changed here.

## Integration prerequisites (currently unverified)

The current activity checker lacks `--release` and has no shared `[HC Use]`
release parser. It must gain release-mode validation in its owning workstream;
this gate deliberately refuses unsupported arguments. It does not fall back to
ordinary ACTIVE/WAITING activity acceptance.

Smoke signals must be registered by the owning feature workstreams and exposed
as client-scoped activity features using the shared `[HC Use]` format. Supply
six distinct mappings, one for each checklist category:

```text
--smoke-use map=MODULE/FEATURE
--smoke-use inventory=MODULE/FEATURE
--smoke-use groups=MODULE/FEATURE
--smoke-use admin=MODULE/FEATURE
--smoke-use ai=MODULE/FEATURE
--smoke-use event=MODULE/FEATURE
```

These are placeholders for real registered module/feature names, not invented
counter names. Missing mappings fail closed. Current expectations cannot prove
all six actions. No native acceptance or successful R3 run is claimed until
these prerequisites and the lead's engine experiments are complete.

## Native host lock (R18) and capacity check (R15)

`host_lock(holder)` is a nonblocking context manager using `fcntl.flock` at
`~/.cache/hollow-country/host.lock`, expanded at runtime and never printed.
JSON metadata contains `holder`, `pid`, `started`. Refusal names only a safe tool
label. Do not delete the inode: the OS releases a crashed holder's lease.
`HC_HOST_LOCK` carries matching metadata to descendants; reentry additionally
requires that the holder PID is the current process or a live ancestor.
Unrelated processes cannot borrow a lease using stale environment metadata.
Keep the outer holder alive while its synchronous children run.

The release gate holds the lease across all steps and cleanup. Compile,
friendcycle, checkstart when starting, Workbench compilation, and Diag
launch/refresh hold it throughout their synchronous operation. Attach-only
checkstart and Diag plan/log do not claim it. Checkstart and Diag intentionally
leave launched processes running when their commands return; this lease is not
a background process supervisor. Existing process guards still apply, and the
lead must end standalone native sessions before running another native tool.

Compilation queries the exact `DayZ_x64.exe` image through read-only winproc.
Running or unknown client state refuses; `--allow-client` is the explicit owner
override. Prepare-only packaging does not launch a native compiler.

Server cleanup uses only CloseMainWindow and bounded waiting. A failed graceful
close fails the verdict and requires operator intervention; no forced kill or
stop command is used. No client is launched or stopped by this gate. Only
`rpt_summary.filtered` output is printed; raw RPTs are never printed or saved in
the verdict. Keep verdicts local until reviewed.
