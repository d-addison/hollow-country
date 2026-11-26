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
local comparison evidence: offline mode has no remote facts, and older
`workshop_sync` receipts contain file hashes but no `timeupdated`. Such receipts
cannot establish timestamp freshness. A newer experimental branch requires review,
not automatic installation. Exit codes: **0** all rows current; **10** action
needed; **2** error or incomplete evidence (including missing network/local data).
If both actionable and unknown rows exist, action-needed takes precedence.

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
current manifest ids and PBO hash, then runs `tools.package.regenerate_all --check`.
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
