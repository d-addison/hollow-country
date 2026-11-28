# Release readiness gate (R3)

Lead-only native workflow; workers test this tooling with fakes. Python tests
establish orchestration behaviour, never DayZ or multiplayer acceptance.

The compile gate defaults to raw shipped HC mission data from the gated tree's
`mission/hollow-country/`, selected by `tools.package.pbo.MISSION_FILES` (including
its validated route inventory). It pins bytes once, refuses missing allowlisted
files (`compile_gate: refused hc_mission_file_missing=<relative path>`) and
symlinks/special files (`hc_mission_irregular=<relative path>`), and ignores
regular files outside the allowlist. It never reads mission data from a profile
or server install. No `init.c`, economy or cfgeconomycore merge is performed;
friend-bundle install-time generated outputs stay absent.

Before boot (also in `--prepare-only`), successful selection prints
`compile_gate: hc_mission_files=<n> hc_mission_sha256=<digest>` and a byte count.
The digest hashes compact JSON sorted `[relative path, content SHA256]` pairs;
the probe JSON records `hc_mission_files`, `hc_mission_sha256` and
`hc_mission_bytes`. `--vanilla-mission` skips selection and prints
`compile_gate: hc_mission_files=0 mode=vanilla` for comparison runs.
Prepare-only never launches the probe and never establishes native acceptance.

The probe writes these bytes only beneath the fresh experiment's disposable
mission. When no mission copy exists, the same `mod-stack.chernarusplus` copy
path used for dependency mods creates one, even without dependencies. A shared
server target refuses with `hc_mission_shared_target` before writes. The complete
mission snapshot and final inventory verification include every HC file, retaining
`complete staged mission inventory drift` on mutation. The stock mission
budgets (256 entries, depth 12, 256 MiB) are unchanged. The staged HC data has
its own explicit caps, `HC_MISSION_MAX_ENTRIES = 1024` (files plus directories)
and `HC_MISSION_MAX_BYTES = 32 MiB`. A disposable copy holding `hollow-country/`
is snapshotted with the stock budget plus those caps. At 1228b548 the shipped set
is 515 files (541 entries), 11.65 MB. Exceeding a cap refuses with
`mission entry budget exceeded` or `mission byte budget exceeded`, plus the counts;
the gate never falls back to vanilla silently.

Only compile_gate supplies HC inputs by default. Existing diagnostic, item-audit,
group-checks, autotest and infected-death callers retain their current missions.
If a caller explicitly supplies HC inputs to the shared probe, the same staging
and snapshot checks apply to its disposable mission. The runtime JSON exemption,
`mission-loaded-runtime-json` status and every pass criterion are unchanged;
new non-exempt SCRIPT (E) errors still fail.

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
   `upgrade_from_previous_release_required` is true, missing both `--previous-bundle` and `--previous-release`
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

## Evidence contracts (#368 / #361, owner 2026-11-25)

Cleanup rereads each boot's final server RPT **after the process exits**. Any crash
indicator, including an exception or minidump after `Server modules stopped`,
refuses as `post-stop crash observed`. For the candidate soak, the clock span
from `[CE][Hive] :: Init sequence finished` to `Server modules stopped` must be
at least `soak_minutes`; missing/duplicate markers refuse. Midnight is supported.
The settle timer alone is insufficient. A short run reports, for example,
`soak duration insufficient measured_seconds=1194.028 required_minutes=30`.

Store quarantine checks use the named `STORE_QUARANTINE_MARKERS` inventory in
`release_gate.py`, with source citations: group recovery, ecology recovery and
migration, event cleanup, interior slots, infected cohorts, betrayal store,
staged-store recovery, and Sites persisted-state recovery. The refusal names
its marker, e.g. `store quarantine observed marker=ecology-recovery`. Native
infected release quarantine counts and the `group_quarantine` activity counter
are operational measurements and do not announce store quarantine.

Client texture accounting accepts only `Cannot load texture '<path>'`. Own
virtual roots come from authored `$PBOPREFIX$` files and the base CfgMods `dir`;
dependency roots come from PBO prefix headers under the Workshop items declared
in the installer's `tools/setup/workshop_mods.json`. No dependency root names
are guessed. Only paths under those roots count toward the texture limit.
Vanilla roots and bare tokens are reported as `vanilla_texture_noise=N`; other
unowned paths are separately reported as `other_texture_noise=N`. Animation,
XML-setting and particle-material messages are outside this texture count.

`--activity-evidence CAMPAIGN_RUN` adds activity from one full campaign. The run
must carry `selection.json`, `manifest.json` or `BUILD_MANIFEST.json` with an
exact candidate `commit`. All commits present must agree. Targeted selections
are refused. For an explicit full selection, `targeted` must be false; an
explicit `release_class=false` always refuses. The campaign's existing full-run
format removes `selection.json`: in that format retain its `report.md` (full
campaign header, no targeted-run label) and archive the exact candidate build
manifest beside it. A missing commit receipt refuses; the gate never substitutes
the checkout HEAD. The directory must have exactly one server RPT and at most
one client RPT. Server crashes, SCRIPT (E), compile errors and VM exceptions
refuse the evidence, even if counters are positive. The current campaign runner
does not archive the candidate build manifest automatically; the lead must
retain it with the run. A receipt alone does not repair a targeted or crashed run.

The union uses cumulative maxima, never sums checkpoints. Every positive row
records `active_runs` (`gate`, `campaign`, or both). Client smoke still requires
client evidence. `RELEASE_WAIVERS` must stay empty; the checker refuses any entry.
`OWNER_CHECKS` is a separate table with reason and owner date 2026-11-23. Its
sole current entry is TeamPing/ping_delivered: HCTeamPing.c:138-141 increments
only for another live group recipient (HCGroupService.HCPingDeliver). It always
prints `OWNER-CHECK`, never a pass, and is excluded from INERT failures. The
verdict lists owner checks. Cellars/visual_applied stays automated and blocking;
its pending cellar-entry driver is recorded in `soak_phases.json`.

R2 remains the existing per-owner cost check. R2b is the directly measured combined
per-tick `work_max` in `[HC Perf]`, rather than a sum of unrelated owner maxima.
Above `perf_r2_max_ms` it emits
`WARN perf_rule=R2b combined_work_max_ms=23.09 limit_ms=20` and never refuses.
Gate verdict JSON, `rpt_summary` JSON/text and release activity output expose the
warning. The campaign Markdown renderer in `tools/testing/soak_campaign.py`
does not yet copy this warnings field into `report.md`; that file is outside
this worker's allowed scope. It must consume the field before claiming that the
campaign Markdown report includes R2b warnings.

## Offline paired census and loot pressure

The 15 ceiling-controlled categories retain their stable IDs. Additional
informational classes distinguish vanilla/dependency engine noise (16) from HC
telemetry/diagnostics (17). HC-origin lines never enter engine noise. Compiler,
crash, script, readiness and self-test checks remain independent. Unrecognized
engine warnings and oversized lines still refuse. Skeleton XML resource errors
are classified as animation resources (7), including HC-origin resource paths.

Given equal-length stock and candidate captures, print counts side by side and
an **unapplied** proposed policy diff:

```sh
python3 -B -m tools.audit.rpt_config_audit CANDIDATE.RPT \
  --vanilla-rpt STOCK.RPT --propose-ceilings
```

This command writes no files and refuses an incomplete paired census. The lead
must first verify paired run lengths and review classified warnings; counts
alone do not establish an acceptable release. `tools.testing.stock_capture pair`
already checks equal declared capture lengths and actual timestamp exposure.
Ceilings remain unchanged until the lead applies a reviewed proposal. To append
a per-type category-2 breakdown, repeat `--types` for **all shipped/installed CE
types files in their load order**, and `--stock-types` for the paired stock types:

```sh
python3 -B -m tools.audit.rpt_config_audit CANDIDATE.RPT \
  --vanilla-rpt STOCK.RPT --propose-ceilings \
  --types INSTALLED/db/types.xml --types INSTALLED/hollow-country/ce/types.xml \
  --stock-types STOCK_MISSION/db/types.xml
```

Include the active optional-pack and travel CE types too. `--loot-settings`
defaults to the repository's shipped loot settings. Every observed item type
gets a count, nominal/min when found, paired stock quantities when found,
boost flag, usage multiplier and capacity multiplier. Missing rows remain
explicitly unresolved. Policy multipliers explain intended pressure; installed
quantities show the effective result after all transformations.

Offline analysis of the retained November 25 RPT (same category counts as the
brief; its receipt marks it targeted):

| Item | Placement warnings | Stock nominal/min | Installed nominal/min | Usage factor | Capacity factor |
| --- | ---: | ---: | ---: | ---: | ---: |
| CableReel | 60,147 | 80/50 | 281/176 | Industrial 3.5 | Industrial 1.0 |
| Pipe | 60,000 | 80/60 | 280/210 | Industrial 3.5 | Industrial 1.0 |
| GardenLime | 24,604 | 50/30 | 185/111 | Farm 3.7 | Farm 3.0 |
| CombinationLock | 2,030 | 60/40 | 223/149 | Farm 3.7 | Farm 3.0 |
| WoodAxe | 1,906 | 20/13 | 78/51 | Farm 3.7 | Village 3.0 |
| Izh43Shotgun | 1,752 | 30/26 | 144/125 | Town 4.0 | Hunting 4.0 |

There are 834 item types and 186,153 category-2 messages. The top three contribute
144,751 (77.8%); 177,525 (95.4%) occur in the first two RPT minutes. The three
largest are all boosted tool rows. Industrial supply grows 3.5x while its
capacity map has no Industrial entry (effective 1x); Farm supply grows 3.7x
against 3x capacity. This supports boosted supply plus initial-fill pressure,
rather than an across-the-board persistent 14x runtime increase. It does **not**
prove fresh storage: that needs the campaign staging receipt. Matching all
active installed CE files found quantities for 828 of 834 types; six remain
unresolved. Installed files are observational evidence and are not certified as
the candidate commit's shipped bytes. Repeat against the exact candidate bundle
and paired stock capture before proposing a ceiling.

## Previous release acquisition and the v1-test-15 obstruction

`--previous-release v1-test-15` is mutually exclusive with `--previous-bundle`.
It uses `gh release view` / `gh release download`, selects the single bundle ZIP,
extracts into the release cache under the user's cache directory, rejects unsafe
archive paths/symlinks and oversized archives, and verifies every file against
`bundle-manifest.json` with the shared installer verifier. A verified cached
copy is rechecked on reuse. Missing assets/manifests or changed files refuse.
The cache is `~/.cache/hollow-country/releases/<tag>/verified`.

The shipped v1-test-15 asset `friend-bundle-v1-test-15.zip` was downloaded and its
manifest verified offline. Its own Python map-overlay validator, against the
installed pristine Chernarus mission's vanilla rows, refuses five flatness checks:
`military-zones-v2/s016-p03`, `s016-p04`, `s030-p10`, `s031-p02`, `s031-p03`.
Their heights differ from local vanilla medians by 1.0-1.1 m, beyond the 0.8 m
tolerance. Its installer calls this validator during step 6 (`overlays-map`)
before applying map layers. A pristine previous installation therefore cannot
complete that path. The gate reports
`upgrade previous-install-refused reason=install failed code=overlays-map`
when the old installer reports that refusal; it does not install the candidate
or label the refusal a candidate failure.

The proven offline route is acquisition, manifest verification, then the old
bundle's own `map_overlay validate --source ... --mission ...`, which reaches
this refusal. No complete v1-test-15-to-candidate native upgrade route is proven.
A lead must supply a previously successful v1-test-15 installation and retained
storage, or choose and document an installable earlier baseline; neither is
silently substituted for the required previous-release test. Do not bypass the
validator or delete persistence/receipts to turn this into a pass.
