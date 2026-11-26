# Brief: automated DayZ-update workflow (worker, branch rt/dayz-update, base origin/dev)

Read AGENTS.md first. You are a worker: never start DayZ, DayZDiag, Workbench, the compile gate,
wb_compile, friendcycle, a soak, steamcmd, Blender or DayZ Tools. Never touch the server or client
install directories except to READ manifests/exes/PBOs. Do not push or merge; commit on this branch.
Never print home paths, Steam IDs or account names in output, docs or commits (print `~/...`).

## Goal
When Bohemia ships a DayZ build (client 221100, server 223350, DayZ Tools 830640) or a Workshop
dependency updates, one command tells us, and a second prepares everything offline so the lead only
has to queue the native gate/soak. Today the build `1.30.164289` is hardcoded in ~20 tool defaults
and the native-scripts cache (~/.cache/hollow-country/native-scripts/scripts-1.30.164289) was
extracted by hand (docs/RUNTIME_IMPLEMENTATION_CONTRACT.md:14-23).

## Items
1. Single build pin. Add `config/dayz-build.json` (schema 1): `build` ("1.30.164289"), `steam`
   buildids for 221100/223350/830640 as currently installed (read them from the appmanifests),
   `server_scripts_pbo_sha256` (contract value 09012cda...), `changelog_url` (optional). Add a small
   stdlib helper `tools/validate/dayz_build.py`: `pinned()`, `native_scripts_dir(build=None)`,
   `names_index_path(build=None)`, `symbols_cache_path(build=None)`; env `HC_DAYZ_BUILD` overrides
   for one run. Replace every hardcoded default in CODE (tools/**.py: native_symbols.BUILD/
   DEFAULT_SCRIPTS/DEFAULT_OUTPUT/NAMES_INDEX, preland.py NATIVE, enforce_lint DEFAULT_CACHE,
   release.py NATIVE_SCRIPTS, the tools/setup/*probe*.py and sampler defaults, drivers.py,
   optional_provider.py, layout_lint, experiments) with the helper. Leave docs, receipts, data/*
   evidence citations and comments that cite a file:line observed in 164289 as they are (they are
   evidence of where a fact was read); `rg -n 164289 tools` afterwards must show only such
   citations. AGENTS.md's preland command line keeps working (explicit --native-scripts wins).
2. `tools/release/dayz_update.py` (stdlib only), subcommands:
   - `check` (read-only): latest public + experimental (`branches.public/.experimental`) buildids
     from `https://api.steamcmd.net/v1/info/<appid>` for the three apps; installed buildids from
     the appmanifests (client+Tools: /mnt/g/SteamLibrary/steamapps, server: /mnt/d/SteamLibrary/
     steamapps; make roots options with these defaults and also honour existing path config if the
     repo has one - grep tools/setup for the server root setting); installed exe version via the
     UTF-16 version string of DayZ_x64.exe / DayZServer_x64.exe (bounded read); the pin. Workshop:
     for every id in tools/setup/workshop_mods.json POST GetPublishedFileDetails
     (api.steampowered.com, no key) for `time_updated` + title, compare with `timeupdated` in the
     client's workshop/appworkshop_221100.acf and the server receipt
     hollow-country-workshop-receipt.json if present. Output a markdown table + `--json`.
     States per row: current / update-available / installed-not-pinned / experimental-only /
     unknown(network). Exit 0 all current, 10 action needed, 2 error. `--offline` skips network.
     Network: 10 s timeout, generic User-Agent `hollow-country-tools`, no personal data sent.
   - `prepare [--build auto]`: refuse unless the installed SERVER exe version equals the target
     build. Extract server dta/scripts.pbo into native-scripts/scripts-<build> using the bounded
     reader in tools/audit/pbo_config.py (read_pbo_index/read_member; refuse compressed entries,
     absolute/`..` paths, symlink targets, entries over budget; write to a temp dir, then rename;
     never overwrite an existing different cache). Record sha256 + entry count. Then build the native
     symbol index for the new cache (native_symbols) and diff old pin vs new: removed/changed
     signatures of classes/methods/fields, filtered to the symbols our mods actually reference
     (use the lint's resolution data or a name scan of mods/**/*.c), plus a full unfiltered count.
     Emit data/vanilla_names_<build>.json via the existing --emit-names-index. Run enforce_lint
     and enforce_perf against the new cache (agent-run --memory 4G is the lead's habit; in the tool
     just call them as subprocesses with the new --native-scripts) and capture pass/fail lines.
     Write everything to ~/.cache/hollow-country/dayz-update/<build>/report.md + report.json.
     Does NOT change the pin.
   - `bump --build <b>`: refuses unless `prepare` reported for <b> and lint passed (or `--force`
     with a reason recorded in the report); writes config/dayz-build.json (steam ids from the
     manifests, the new sha256), and runs `tools.package.regenerate_all` check mode, printing the
     generated files it changed. Leaves committing to the operator.
   - `next`: prints the remaining manual/native steps for the target build, in order, from the
     report state: (a) workshop_sync plan/fetch for updated dependencies, (b) compile gate through
     tools.release.test_queue (never while the owner plays), (c) friendcycle + 30-min soak via the
     release gate, (d) one-client smoke, (e) R3 release gate, (f) ASK the owner before any
     GitHub Release / Workshop upload. Also prints a ready-to-file GitHub issue body (title
     "DayZ <build>: update checklist") with the API diff summary and changelog link. It never runs
     gh itself.
3. preland: add a `dayz_build` check: installed server/client buildids (appmanifests) vs the pin;
   pass when equal, `needs-host-check` when manifests are unreadable, FAIL when the server build is
   newer than the pin ("prepare+bump first: native cache is stale"). release.py R3 gate: same check
   is blocking.
4. Docs: docs/tools/DAYZ_UPDATE.md runbook (the flow above, exit codes, what is offline evidence
   vs DayZ evidence, Steam auto-update note: the client auto-updates, the server only via steamcmd
   by the owner). Link it from docs/tools index/README tools section and the contract paragraph.
5. Tests (asked for): tests for dayz_update only - manifest/acf parsing, exe version string parse
   on a synthetic buffer, the state table logic, PBO extraction refusals on a synthetic PBO, the
   symbol diff filter. No network in tests. Run only those tests plus the existing tests of files
   you touched.

## Gates before DONE
python3 -B -m tools.validate.preland --native-scripts ~/.cache/hollow-country/native-scripts/scripts-1.30.164289 --changed origin/dev
Also run `python3 -B -m tools.release.dayz_update check --offline` and `check` (network) and paste
their output in your report (they are read-only). Do NOT run prepare against the live cache dir
for 164289 except with --dry-run if you add one; a real `prepare` for 164289 into a temp
`--cache-root` is fine and is the best smoke test (it must reproduce the existing cache: compare
file count + a few sha256s against ~/.cache/hollow-country/native-scripts/scripts-1.30.164289).

## Report
Files changed, the check output, the prepare smoke comparison, any pin site you deliberately left.
