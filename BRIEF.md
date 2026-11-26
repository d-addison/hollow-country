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

## Round 2 (lead review of 5730737d + banso integration; same rules)
R0 (fix) Workshop server freshness: `check` online exits 2 forever because the server receipt (hollow-country-workshop-receipt.json written by tools/setup/workshop_sync.py) holds hashes only. Make workshop_sync.py also record each item's client timeupdated (from appworkshop_221100.acf) at copy time; in `check`, a receipt without stamps is a Note "server receipt predates timestamps; run workshop_sync" and does NOT force exit 2 when apps and client Workshop items are otherwise known (exit 10 only on a real update, 2 only on network/parse failure). Experimental column shows "?" while steamcmd returns public: verify the branch key name in the live api.steamcmd.net response and fix if wrong. Also make `bump` update the native_scripts path and game_build strings in config/hollow-country-variant-dependencies.json and config/hollow-country-winter-terrain.json (or have preland flag them when they differ from the pin), and update tests.

## Round 2: banso integration (same branch rt/dayz-update; same worker rules)
Facts from the banso source (/code/banso; read-only, do not edit it):
- `banso workflow run <name> --pipeline <p> --headless [--input k=v]` runs one pipeline of
  .banso/workflows/<name>.yaml (action_groups_b.rs:948-971). `banso workflow validate <file>` is the loader check.
- `banso schedule add/once` store entries that NOTHING executes today (schedule.rs:114-122 empty workflow;
  deferred.rs:229 check_timers has no runtime caller). Do not rely on it.
- Step `capabilities.sandbox/egress` are parsed (egress = service names, not hostnames) but not enforced for
  deterministic steps. Declare them honestly anyway; enforce the network allowlist inside the Python tool.
- `banso test-service` checks are a fixed cargo/npm grammar; our native work goes through tools.release.test_queue.
- Notifications: a step can run `banso events ingest <file.json>` (events_cmd.rs:82) and a `reactions:` rule in
  .banso/config.yaml (EmitFriction / HttpWebhook / ShellScript, crates/banso-engine/src/reaction/actions.rs:16-33)
  handles it, processed by the `react-to-events` builtin step or `banso events watch`. Read those files for the
  exact event JSON and reactions schema before writing them; if the schema can't be confirmed from source, stop
  and report instead of guessing.
- `banso decision new` writes .banso/decisions/*.yaml (decision_cmd.rs:3-41).

Items:
R1. Pipelines in .banso/workflows/hollow-country.yaml (same file, new pipelines; keep the existing ones):
    `dayz-update-check` (python3 -B -m tools.release.dayz_update check --json-out .banso/pipeline-outputs/
    dayz-update/check.json; exit 0 when the check itself worked, including "update available" - the state is in
    the JSON; capabilities read-only + egress [] is wrong for this step, so declare network/egress as accurately
    as the schema allows and note in a comment that banso does not enforce it); then a step that, only when
    check.json says action needed, runs `banso events ingest` with a dayz_update event (build/workshop rows,
    no paths/ids of people); then `react-to-events`.
    `dayz-update-prepare` (input `build`, default auto): prepare, then enforce_lint + enforce_perf against the new
    cache, writing to .banso/pipeline-outputs/dayz-update/<build>/.
    `dayz-update-bump` (input `build`): bump, regenerate_all check, then `banso decision new` recording
    old->new build, API diff summary (counts + the referenced-symbol changes), lint/perf result and that the
    native gate/soak are still pending (never "passed").
    All must pass `banso workflow validate .banso/workflows/hollow-country.yaml` and a `--dry-run`.
R2. Fix the existing verify-offline preland step: no hardcoded scripts-1.30.164289; let preland's default
    (now the pin helper) supply it, or use `$(python3 -B -m tools.validate.dayz_build --native-scripts)` if you
    add that CLI.
R3. Reactions in .banso/config.yaml: on the dayz_update event, EmitFriction (so `banso friction list` shows
    "DayZ update available: ...") and, if a ShellScript reaction exists, run
    `python3 -B -m tools.release.dayz_update notify --event <file>` which only prints/writes
    ~/.cache/hollow-country/dayz-update/pending.md (no network, no gh). No HttpWebhook (no endpoint configured).
R4. Trigger: banso cannot schedule, so ship a systemd user timer in tools/setup/systemd/
    (hc-dayz-update-check.service + .timer, every 6 h, RandomizedDelaySec 15 min, Persistent=true) that runs
    `banso workflow run hollow-country --pipeline dayz-update-check --headless` in the repo main checkout,
    with MemoryMax=1G. Add `dayz_update timer install|status|remove` that copies/enables/disables them under
    ~/.config/systemd/user (prints the systemctl commands with --dry-run; never touches anything else).
    Do NOT install it yourself; the lead does after merge.
R5. `dayz_update next --queue`: instead of only printing, submit the compile gate via
    `tools.release.test_queue submit --commit <sha> --checks preland,wb,gate` for the bump commit (refuses on a
    dirty tree or unpushed commit). Without --queue it keeps printing.
R6. Daemon port: .banso/config.yaml gets its own `daemon.port` (pick an unused port, e.g. 9746; check the
    config schema in crates/banso-core/src/config.rs ~1019 for the key name) so `banso daemon status` stops
    reporting the foreign daemon on 9740. Do not start or stop any daemon.
R7. docs/tools/DAYZ_UPDATE.md: a "Running it through banso" section (commands above, what banso enforces and what
    it does not, the timer, friction/pending.md). Tests only for the new Python (notify, timer dry-run text,
    next --queue refusal).
Validate: preland --changed origin/dev, banso workflow validate, the three pipelines with --dry-run, and one real
`banso workflow run hollow-country --pipeline dayz-update-check --headless` (read-only; paste its tail).
R6 addendum (banso CONFIG-DAEMON-PORT-MERGE1): a project daemon.port is overwritten by any higher config layer that
omits `daemon` (~/.banso/overrides.yaml, team/global). After setting it, check the effective port with
`banso config show` (or `banso daemon status`) and report it. If it is overwritten, do not edit user/global banso
config; instead set Environment=BANSO_DAEMON_PORT=<port> in the systemd service (R4) and document the env var in
DAYZ_UPDATE.md.
