# DayZ update workflow

`config/dayz-build.json` is the schema-1 build pin: game version, installed Steam
buildids for client 221100, server 223350 and Tools 830640, and server scripts PBO
SHA-256. An optional `changelog_url` is included in the update issue checklist.
`HC_DAYZ_BUILD` selects a build for one process; an explicit `--native-scripts`
always wins over its default cache. Evidence citations retain their observed build.

Run from the repository root:

```sh
python3 -B -m tools.release.dayz_update check
python3 -B -m tools.release.dayz_update check --offline --json
python3 -B -m tools.release.dayz_update prepare --build auto
# Review the report and referenced API changes; fix lint findings before bumping.
python3 -B -m tools.release.dayz_update bump --build <major.minor.build>
python3 -B -m tools.release.dayz_update next --build <major.minor.build>
```

`check` reads manifests, bounded executable version metadata, the client Workshop
ACF, and the server Workshop receipt when present. Network mode queries public
and experimental Steam branches and Workshop titles/update times with a 10-second
timeout and generic `hollow-country-tools` User-Agent. Only public app/Workshop
identifiers are sent. No account information or credentials are sent.

The default Steam roots are `/mnt/g/SteamLibrary/steamapps` for client/Tools and
`/mnt/d/SteamLibrary/steamapps` for server; Tools also falls back to the latter.
Override with `--client-apps` / `--server-apps`. The server install is resolved
from its manifest, unless `--server-root` or the existing setup probe setting
`HC_SERVER_ROOT` is provided. All installed inputs are read only.

Rows are `current`, `update-available`, `installed-not-pinned`,
`experimental-only`, or `unknown(network)`. The last state also denotes missing
local comparison evidence: offline mode has no remote facts. Older
`workshop_sync` receipts contain file hashes but no `timeupdated`; these produce
`Note: server receipt predates timestamps; run workshop_sync` without failing a
known client comparison. Server freshness remains unproven until a successful sync.
New successful installs record source-client ACF timestamps in the receipt. A newer experimental branch requires review,
not automatic installation. Exit codes: **0** all rows current; **10** action
needed; **2** error or incomplete evidence (including missing network/local data).
Network or parse failures take precedence over actionable rows.

The client auto-updates through Steam. The server updates only when the owner
runs steamcmd. These commands neither update installations nor run steamcmd.

`prepare` requires the installed server executable to equal the target version.
It reads `dta/scripts.pbo`, refuses compressed/unsafe/oversized entries and symlink
cache targets, extracts into a temporary sibling directory, then renames it.
An existing cache is reused only when every file is identical. It records PBO
hash, entry count and byte count, builds the native symbol cache and emits the
names-only `tools/validate/data/vanilla_names_<build>.json`. No native source is
committed. The old pinned scripts must be available for the full signature diff.
The diff includes removed/changed classes, method overloads (including returns)
and field types/modifiers; conservative identifiers from `mods/**/*.c` select the
referenced subset. Full and filtered counts are both recorded.

Lint and perf run as Python subprocesses with the new `--native-scripts` context;
perf checks authored sources and does not claim native API validation. Reports
are `~/.cache/hollow-country/dayz-update/<build>/report.md` and `report.json`; the full `native-symbols.json` index is saved beside them.
The pin stays unchanged. Preparation returns 2 when index generation or either
validator fails; the report retains the results. For a safe same-build rehearsal:

```sh
python3 -B -m tools.release.dayz_update prepare --build auto \
  --cache-root /tmp/hc-dayz-rehearsal/native-scripts \
  --report-root /tmp/hc-dayz-rehearsal/reports
```

`bump` requires a matching prepare report, successful indexes and passing lint.
`--force 'reason'` permits a lint override and records the reason; it never bypasses
the prepared indexes or installed exe/PBO identity checks. It updates the pin with
current manifest ids and PBO hash, refreshes `native_scripts` and `game_build`
keys in both variant-dependencies and winter-terrain configs, then runs `tools.package.regenerate_all --check`.
Check mode does not change generated files: its output lists generator mismatches
that need separate regeneration/review. A failed regeneration returns 2 with the
pin already updated and diagnostics in the report. Inspect the diff and commit
through the normal operator workflow. `--report-root` selects rehearsal reports.

Preland checks client/server manifest ids against the pin. Unreadable manifests
produce `needs-host-check`; mismatches fail, with a stale-cache diagnostic when
the installed server is newer. Release packaging and the R3 release gate require
the same check to pass before native work. The CI profile explicitly excludes
installed manifest coverage. Confined workers run preland with
`HC_NO_DAYZ_TOOLS=1`: CfgConvert is visibly skipped and regeneration receives an
unavailable ImageToPAA path, leaving those host checks pending.

`next` prints the remaining checklist and a ready-to-file GitHub issue body titled
`DayZ <build>: update checklist`, with API summary and changelog link. No `gh`
command runs. Native steps default to pending; the lead may record completed
steps in the report's `native_steps` mapping (`workshop`, `compile`, `soak`,
`client`, `r3`, `publish`: `passed`) only after obtaining the relevant evidence.
The order is:

1. Review dependency changes with `tools.setup.workshop_sync plan`; the owner
   fetches/installs updated Workshop dependencies as needed.
2. Queue the compile gate through `tools.release.test_queue`, never while the
   owner is playing.
3. Friendcycle and a 30-minute soak through `tools.release.release_gate`.
4. Owner one-client smoke.
5. Complete the R3 release gate.
6. **Ask the owner** before any GitHub Release or Workshop upload.

Offline extraction, signature comparisons and lint/perf passes are source evidence.
They establish no DayZ compile, boot, gameplay, soak or client acceptance. Workers
must leave native execution to the lead host queue.

## Running it through banso

```sh
banso workflow validate .banso/workflows/hollow-country.yaml
banso workflow run hollow-country --pipeline dayz-update-check --headless
banso workflow run hollow-country --pipeline dayz-update-prepare --headless --input build=auto
banso workflow run hollow-country --pipeline dayz-update-bump --headless --input build=<major.minor.build>
# Add --dry-run to inspect any pipeline without executing its steps.
```

The check writes `.banso/pipeline-outputs/dayz-update/check.json`. Its
`action_needed` and `exit_code` retain the result; `--json-out` returns 0 for a
successful check including updates, and 2 for failures. Public branches come from
`branches.public`; the experimental server branch is `branches.experimental_public`.
Absent client/Tools experimental branches display `?`.

The event adapter only ingests a `dayz_update` event when action is needed. Events
contain public app/Workshop rows and build information, without personal paths or
identifiers. `react-to-events` processes the configured EmitFriction rule. In the current
banso source, EmitFriction ignores its event type/message and only records a
generic `reaction/dispatched` in `friction-events.jsonl`; `banso friction list`
reads `friction-log.jsonl`, so the requested human-readable friction notice remains
blocked by this banso implementation gap. The adapter runs the local-only
`notify --event <file>` command, which prints the notice and writes
`~/.cache/hollow-country/dayz-update/pending.md`. No webhook is configured.
The current banso reaction executor explicitly rejects ShellScript actions, so
notification runs in the deterministic adapter instead of a ShellScript rule.

Prepare and its explicit lint/perf follow-up use the extracted cache and write
reports in `.banso/pipeline-outputs/dayz-update/<build>/`. The validation adapter
also copies the report to the normal cache report directory. Bump requires an
explicit build, performs the regeneration check, then records a banso decision
with old/new builds, full/referenced API changes, lint/perf results and **native
gate and soak pending**. Its decision adapter also refreshes the cache report.

Banso validates workflow structure, resolves inputs with shell escaping, orders
steps and checks their exits. Update pipelines stop at the first failed step to
avoid consuming stale reports or emitting a decision after a failed bump. Deterministic step sandbox/egress declarations are
not enforced by banso. Network access is bounded in Python: HTTPS only to
`api.steamcmd.net` and `api.steampowered.com`, including redirect destinations,
with a 10-second timeout and bounded responses. Proxy environment settings are
ignored so requests only use those destinations. Preparation, notification and
timer management do not access the network. Native work uses the host test queue,
not banso's cargo/npm test-service grammar. Banso schedule entries currently have
no runtime executor; use the systemd user timer instead.

The lead installs the timer **after merge**, from the main checkout:

```sh
python3 -B -m tools.release.dayz_update timer install --dry-run
python3 -B -m tools.release.dayz_update timer install
python3 -B -m tools.release.dayz_update timer status
python3 -B -m tools.release.dayz_update timer remove --dry-run
```

Only the two `hc-dayz-update-check` units under `~/.config/systemd/user` are
managed. Installation resolves the main checkout via git metadata and renders
its working directory into the service. The timer runs every six hours, adds up
to 15 minutes of random delay, catches missed runs with `Persistent=true`, and
limits the check service with `MemoryMax=1G`. Removal disables the timer and
removes those units. Dry-run prints the systemctl commands without running them.
Ensure `banso` is installed in the service PATH (user local/cargo and system bins).
No timer is installed by a worker.

The project declares `daemon.port: 9746`; this port was unused during validation.
Higher banso config layers currently reset it to 9740 when they omit `daemon`.
The service therefore sets `Environment=BANSO_DAEMON_PORT=9746`; this yields an
effective port of 9746 without editing user/global configuration. In this confined
worker environment, ordinary `banso config --resolved` first fails on an
unwritable global layout root. The port comparison was read with temporary layout
environment overrides; no daemon was started or stopped.

After the bump commit is pushed, the lead can submit it:

```sh
python3 -B -m tools.release.dayz_update next --build <major.minor.build> --queue
```

This requires a clean tree, HEAD contained in a remote branch, a matching committed
pin and a bumped prepare report. It submits `preland,wb,gate` through
`tools.release.test_queue submit --commit <sha>`; it never executes native checks.
Without `--queue`, `next` continues to print the issue checklist only. Remote refs
must be current; the command does not fetch or push. The host queue holds native
work while the owner plays. Soak, client smoke, R3 and publication permission
remain separate owner steps.
