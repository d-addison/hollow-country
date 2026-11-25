# Release readiness gate (R3)

Lead-only native workflow; workers test this tooling with fakes. Python tests
establish orchestration behaviour, never DayZ or multiplayer acceptance.

```sh
python3 -B -m tools.release.release_gate --commit FULL_40_CHARACTER_SHA \
  --bundle /mnt/e/HollowCountryLocal/candidate \
  --previous-bundle /mnt/e/HollowCountryLocal/previous \
  --client-mode scripted --client-timeout 3600 \
  --smoke-use map=ClientUI/map_open \
  --smoke-use inventory=ClientUI/inventory_open \
  --smoke-use groups=Groups/menu_open \
  --smoke-use admin=AdminMap/window_open \
  --smoke-use ai=optional-expansion-human-ai/site_radius_entered \
  --smoke-use event=Events/mission_radius_entered
```

The tool writes `release-gate-verdict.json` (override with `--verdict`) and prints
one JSON verdict plus a short summary. It stops at the first failure. The input
commit must be a full lowercase SHA; abbreviated refs and HEAD are refused.
No publishing, committing or merging occurs. Bundles must remain unchanged
throughout the run. Use an isolated test server with retained storage for upgrades.

Owner targets live in [`config/acceptance-targets.json`](../../config/acceptance-targets.json).
The gate reads both owner targets and activity expectations from the candidate
commit before acquiring the host lock.
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

1. Compile that commit using `compile_gate` and require a verified clean
   Mission load. The older `mission-loaded-runtime-json` PASS certifies Mission.
   An `initialized` or `timeout` PASS also needs the explicit clean Mission marker.
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
6. Print the client checklist and wait up to 900 seconds (configurable with
   `--client-timeout`, maximum 3600) for all mapped client features to be ACTIVE
   with positive counts. Apply `client_max_vme`, `max_script_errors` and `client_max_missing_textures`
   from the targets file to client errors. Also require the
   [client compile evidence check](CLIENT_COMPILE_CHECK.md) on the fresh client
   RPT and all sibling script logs, on each poll and before success. Missing
   completion or any compile error is a hard failure regardless of counters;
   use a fresh isolated client profile to avoid mixing sessions.

### Client mode

`--client-mode scripted` (the default, owner 2026-11-24) needs no person. Before
the install the gate builds and signs the dev-only test addon
(`tools.testing.test_addon`), writes the R3 step file
(`python3 -B -m tools.testing.driver_script plan --route r3`) and stages both in
one new folder next to the server root, `release-gate-client`, marked as the
gate's own. A watcher launches one real client through the BattlEye launcher
(the soak campaign's `WindowsHost.launch_client` and `client_arguments`) once
the fresh soak RPT says `Player connect enabled`. The client loads the
candidate's mods from the server root, the Workshop dependencies by id (the
campaign's dependency parity check refuses a mismatch before anything starts)
and the test addon last; the server runs the installed candidate unchanged and
never loads the test addon. The client RPT is read from the staged profile.
The scripted client opens the M map (map and group controls), the inventory and
the admin window, then walks on foot from outside into one AI site activation
radius and one published mission zone, in, out and in again until the server's
own radius receipt arrives (docs/tools/AUTOPLAYER.md). It stays connected
through activity validation. Cleanup closes the client first (the campaign's
graceful CloseMainWindow path), confirms `DayZ_BE.exe` and `DayZ_x64.exe` are
gone, removes the folder, then stops the server. A client that cannot be
confirmed gone leaves the folder in place and fails the verdict. The verdict
records `client_mode` and `client` (`scripted client`). Pass `--client-root`
for a client install the campaign cannot discover. The test addon is built from
the checkout running the gate; it is never part of the bundle. The two-step
route takes up to 55 minutes, so give the client step `--client-timeout 3600`.

`--client-mode human` keeps the one-tester path below (`--client-profiles`
belongs to it).

The tester should join during the soak, open the M map with group controls,
inventory and admin window, and approach an AI site and published mission zone
from outside their radii. Stay in each area long enough for the server sampler
to observe the crossing. The checklist is also
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

## Smoke evidence

The six mappings above are client-scoped cumulative `[HC Use]` counters in
`config/activity-expectations.json`. The Hollow Country M menu opens both
the map and the group controls. The AI site director samples its existing site
activation geometry, and the event owner samples the live public mission circle.
Both require an observed outside position followed by an inside position for
the same living character and radius, then send a one-int observation only to
that character's identity. The receipt carries no site details or player data.
Fixture counts and server log lines cannot satisfy client evidence; the
scripted client counts nothing itself and only reads the server's receipt.
Native delivery, observations, the scripted client and a full R3 pass remain
unverified.

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
stop command is used. Only the scripted client mode launches and stops a client,
through the same graceful path. Only
`rpt_summary.filtered` output is printed; raw RPTs are never printed or saved in
the verdict. Keep verdicts local until reviewed.
