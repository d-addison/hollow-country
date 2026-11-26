# DayZ update round 2 worker report

Implemented the review fixes and banso integration on the existing worker tree.
No git metadata writes, push, merge, native tools, installed-directory writes,
timer installation, daemon start/stop, release or upload were performed.
`BRIEF.md` was already modified at entry and was not edited by this worker.

## Files changed

- `.gitignore`: include only authored banso config/workflow; keep runtime state ignored.
- `.banso/config.yaml`: DayZ friction reaction and project daemon port 9746.
- `.banso/workflows/hollow-country.yaml`: preserve main-checkout pipelines, remove
  the verify-offline hardcoded native path, add check/prepare/bump pipelines.
- `tools/release/dayz_update.py`: legacy-receipt semantics, experimental branch,
  HTTPS allowlist including redirects, JSON output contract, dependency config
  refresh on bump, conditional event/decision adapters, notify, timer and queue.
- `tools/setup/workshop_sync.py`: bounded standalone ACF reader and copy-time
  receipt timestamps, preserved across receipt repair/retirement and partial syncs.
- `tools/setup/systemd/hc-dayz-update-check.service` and `.timer`: main-checkout
  six-hour checks, random delay, persistence and 1G memory cap.
- `tests/unit/test_dayz_update.py`: synthetic parsing/state/install, notification,
  timer dry-run and dirty/unpushed/non-bump queue-refusal coverage; no network.
- `docs/tools/DAYZ_UPDATE.md`: banso commands, declarations versus enforcement,
  timer, friction/notice behavior, queue and effective-port workaround.
- This report.

## Validation

`python3 -B -m unittest tests.unit.test_dayz_update tests.slow.test_workshop_sync`:
111 targeted tests passed. The required preland command additionally selected
1,018 tests from the entire origin/dev diff; this includes earlier work on this
branch. No full-suite command was invoked directly.

Workflow validation and all three pipeline dry-runs exited 0. The real check
pipeline exited 0; reaction processing skipped because there was no update event.
The live API exposes `experimental_public` for server 223350 (buildid 3889697);
client and Tools have no experimental branch today. Installed apps equal the pin.

Port 9746 had no listener. Ordinary config resolution/daemon status failed on the
confined environment's unwritable global layout root. Using temporary existing
layout roots via environment variables allowed read-only effective-config checks:
project-only effective daemon.port = 9740; with BANSO_DAEMON_PORT=9746 it is 9746.
No user/global configuration was edited. The service supplies that environment
variable and the runbook explains the higher-layer reset.

The reaction schema was confirmed from banso source: IngestedEvent, ReactionConfig,
ReactionRule, EventFilter and the tagged ReactionAction enum. The current executor
rejects ShellScript reactions; no ShellScript rule existed. The configured reaction
uses EmitFriction, and the conditional event adapter invokes the local notify command
for pending.md. No HttpWebhook is configured.

R3 limitation: EmitFriction also ignores its configured event_type/message in the
current banso executor. It appends generic reaction/dispatched to
friction-events.jsonl, whereas friction list reads friction-log.jsonl. Therefore
the human-readable friction-list notice cannot be delivered by this reaction
implementation; the local pending.md notice works. /code/banso was not edited. Banso's deterministic capability
sandbox/egress declarations are not enforcement; Python validates network hosts.

## Pin sites intentionally retained

The build pin remains 1.30.164289. Current dependency config values therefore stay
at this build; future bump updates every `native_scripts`/`game_build` key in the
two requested configs. Their observed snapshot/exact_version evidence remains
historical. Existing docs, receipts, audit data and tools' file:line/observed-native
citations retain 164289. No executable default still hardcodes that build. The
explicit AGENTS preland cache argument remains supported. The main-checkout AGENTS
was read because this worktree and its parent directories contain no AGENTS.md.

## Temporary prepare smoke

The rehearsal used a temporary cache/report root, not the live 164289 cache.
All file paths and hashes were compared, plus the three examples below. The
rehearsal directory was removed afterwards. This is offline source evidence;
native gate, soak, client smoke and R3 acceptance remain pending.

## Prepare output and comparison

```text
Report: /tmp/hc-dayz-round2-prepare-t4iibv_i/reports/1.30.164289/report.md
Extraction: entries=3076 sha256=09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a
API changes: full=0 referenced=0
symbols: PASS
names_index: PASS
enforce_lint: PASS
enforce_perf: PASS
Exit: 0
File count: existing=3076 extracted=3076; all names/hashes identical=True
3_Game/Global/Game.c: old=04e61c19198a0b942b9b72fffca02358d9dca136c1c552bfb3a6193e79a59c2b new=04e61c19198a0b942b9b72fffca02358d9dca136c1c552bfb3a6193e79a59c2b
3_Game/Weather.c: old=1e3fe3272d1302365d6777540afcec878ac6ed5fae5650db4bc152b0088c623b new=1e3fe3272d1302365d6777540afcec878ac6ed5fae5650db4bc152b0088c623b
4_World/Entities/ManBase/PlayerBase.c: old=3e931a7ea9912fa75632c3171b6bc18381e14b931feb92952015629e873e032e new=3e931a7ea9912fa75632c3171b6bc18381e14b931feb92952015629e873e032e
```

## Offline check output

```text
Pin: 1.30.164289 (offline; remote data skipped)
App/dependency | Installed client / server | Pin | Public | Experimental | Exe | State
--- | --- | --- | --- | --- | --- | ---
Client | 26403755 | 26403755 | ? | ? | 1.30.164289 | unknown(network)
Server | 26220720 | 26220720 | ? | ? | 1.30.164289 | unknown(network)
Tools | 26405911 | 26405911 | ? | ? | ? | unknown(network)
Workshop 1559212036 | 1791897978 / ? | ? | ? | ? | ? | unknown(network)
Workshop 1564026768 | 1793367435 / ? | ? | ? | ? | ? | unknown(network)
Workshop 2545327648 | 1792592577 / ? | ? | ? | ? | ? | unknown(network)
Workshop 2291785308 | 1795192096 / ? | ? | ? | ? | ? | unknown(network)
Workshop 2116157322 | 1794246265 / ? | ? | ? | ? | ? | unknown(network)
Workshop 2291785437 | 1795192142 / ? | ? | ? | ? | ? | unknown(network)
Workshop 2792982069 | 1794246327 / ? | ? | ? | ? | ? | unknown(network)
Workshop 2792984722 | 1795192106 / ? | ? | ? | ? | ? | unknown(network)
Workshop 2443122116 | 1792351053 / ? | ? | ? | ? | ? | unknown(network)
Workshop 3534507229 | 1759241041 / ? | ? | ? | ? | ? | unknown(network)
Workshop 3302732231 | 1780929871 / ? | ? | ? | ? | ? | unknown(network)
Workshop 1762444175 | 1729295344 / ? | ? | ? | ? | ? | unknown(network)
Workshop 1797720064 | 1792162502 / ? | ? | ? | ? | ? | unknown(network)
Workshop 2579252958 | 1792396940 / ? | ? | ? | ? | ? | unknown(network)
Workshop 2752192852 | 1776077309 / ? | ? | ? | ? | ? | unknown(network)
Workshop 2670506982 | 1792434218 / ? | ? | ? | ? | ? | unknown(network)
Workshop 2757509117 | 1792819235 / ? | ? | ? | ? | ? | unknown(network)
Workshop 2646817942 | 1794129483 / ? | ? | ? | ? | ? | unknown(network)
Workshop 3556131153 | 1793568736 / ? | ? | ? | ? | ? | unknown(network)
Workshop 3157695626 | 1792284289 / ? | ? | ? | ? | ? | unknown(network)
Workshop 3105330157 | 1793654025 / ? | ? | ? | ? | ? | unknown(network)
Workshop 3114410963 | 1792676576 / ? | ? | ? | ? | ? | unknown(network)
Workshop 3841628320 | 1795388251 / ? | ? | ? | ? | ? | unknown(network)
Workshop 3841637854 | 1795388328 / ? | ? | ? | ? | ? | unknown(network)
Note: server receipt predates timestamps; run workshop_sync
Exit: 2
```

## Online check output

```text
Pin: 1.30.164289
App/dependency | Installed client / server | Pin | Public | Experimental | Exe | State
--- | --- | --- | --- | --- | --- | ---
Client | 26403755 | 26403755 | 26403755 | ? | 1.30.164289 | current
Server | 26220720 | 26220720 | 26220720 | 3889697 | 1.30.164289 | current
Tools | 26405911 | 26405911 | 26405911 | ? | ? | current
CF | 1791897978 / ? | ? | 1791897978 | ? | ? | current
Community-Online-Tools | 1793367435 / ? | ? | 1793367435 | ? | ? | current
Dabs Framework | 1792592577 / ? | ? | 1792592577 | ? | ? | current
DayZ-Expansion-Core | 1795192096 / ? | ? | 1795192096 | ? | ? | current
DayZ-Expansion-Licensed | 1794246265 / ? | ? | 1794246265 | ? | ? | current
DayZ-Expansion-Vehicles | 1795192142 / ? | ? | 1795192142 | ? | ? | current
DayZ-Expansion-AI | 1794246327 / ? | ? | 1794246327 | ? | ? | current
DayZ-Expansion-Navigation | 1795192106 / ? | ? | 1795192106 | ? | ? | current
SNAFU Weapons | 1792351053 / ? | ? | 1792351053 | ? | ? | current
MoreFood V2 | 1759241041 / ? | ? | 1759241041 | ? | ? | current
CookZ | 1780929871 / ? | ? | 1780929871 | ? | ? | current
Uncuepas Civilian Clothing | 1729295344 / ? | ? | 1729295344 | ? | ? | current
WindstridesClothingPack | 1792162502 / ? | ? | 1792162502 | ? | ? | current
AdditionalMedicSupplies | 1792396940 / ? | ? | 1792396940 | ? | ? | current
dzr_notes | 1776077309 / ? | ? | 1776077309 | ? | ? | current
Building Fortifications | 1792434218 / ? | ? | 1792434218 | ? | ? | current
gebsfish | 1792819235 / ? | ? | 1792819235 | ? | ? | current
Tactical Flava | 1794129483 / ? | ? | 1794129483 | ? | ? | current
RaG_Core | 1793568736 / ? | ? | 1793568736 | ? | ? | current
RaG_BaseBuilding | 1792284289 / ? | ? | 1792284289 | ? | ? | current
RaG_Immersive_Vehicles | 1793654025 / ? | ? | 1793654025 | ? | ? | current
Ambient Animals Pack | 1792676576 / ? | ? | 1792676576 | ? | ? | current
Hollow Country | 1795388251 / ? | ? | 1795388251 | ? | ? | current
Hollow Country Expansion AI (server) | 1795388328 / ? | ? | 1795388328 | ? | ? | current
Note: server receipt predates timestamps; run workshop_sync
Exit: 0
```

## Real banso check pipeline tail

```text
Workflow 'hollow-country' completed in 928ms
  dayz-update-check    pass     928ms
Steps:
  dayz-update-check/check                pass     861ms
  dayz-update-check/ingest-update-if-needed pass     59ms
  dayz-update-check/react-to-events      skip     0ms
Overall: pass
2026-11-26T19:31:59.418804Z  WARN could not record invocation telemetry write misses error=could not open ~/.banso/telemetry/invocation-misses-v1.jsonl: Read-only file system (os error 30)
2026-11-26T19:32:01.638515Z  WARN could not record invocation telemetry write misses error=could not open ~/.banso/telemetry/invocation-misses-v1.jsonl: Read-only file system (os error 30)
Exit: 0
```

## Required preland result

Command (DayZ Tools disabled for this confined worker):

```sh
HC_NO_DAYZ_TOOLS=1 python3 -B -m tools.validate.preland --native-scripts ~/.cache/hollow-country/native-scripts/scripts-1.30.164289 --changed origin/dev
```

Exit 1. Enforce lint/perf, settings, wiring, mission checks and dayz_build passed.
Host-only checks remain visibly pending. The failures are:

- Eleven generated digest receipt mismatches, listed below; regeneration's byte
  comparisons pass for available inputs. These generated artifacts and their
  receipt were not changed in this round.
- Hygiene/docs drift flags the pre-existing BRIEF.md:123 example of an optional
  dayz_build CLI that was not added; the brief was left untouched.
- Nine interior_resolve_probe tests fail because the checked-in catalog lacks
  sufficient Land_Garage_Row_Big instances. That tool/catalog was not changed.

The broad changed-test selection is from origin/dev, not just this round's files.
Synthetic R3/R4 test output in the complete log is test data, not native acceptance.
Native compile, soak and client/R3 gates were not run.

```text
preland: running generated_digests (full tree)
FAIL ai_route_precompute committed input/source/output digest differs
FAIL admin_world_catalog committed input/source/output digest differs
FAIL military_loot committed input/source/output digest differs
FAIL loot_slack committed input/source/output digest differs
FAIL inventory_sizes committed input/source/output digest differs
FAIL variety_packs committed input/source/output digest differs
FAIL firearms committed input/source/output digest differs
SKIP loot_point_preserve full DayZ client Addons unavailable (dedicated-server PBOs strip visual meshes)
SKIP snafu_optional weapon pack verification report unavailable
SKIP tactical_flava_optional weapon pack verification report unavailable
SKIP gui_icons ImageToPAA converter unavailable
SKIP new_buildings full DayZ client Addons unavailable (dedicated-server PBOs strip visual meshes)
FAIL economy committed input/source/output digest differs
FAIL gen_modules committed input/source/output digest differs
FAIL ai_patrols committed input/source/output digest differs
FAIL anims_config committed input/source/output digest differs

Check | Result | Scope
--- | --- | ---
enforce_lint | pass | full tree
enforce_perf | pass | full tree
layout_lint | needs-host-check: layout_lint: texture counts {"skipped": 0, "unresolved": 0} | full tree
cfgconvert_check | skipped: DayZ Tools disabled by HC_NO_DAYZ_TOOLS (worker restriction) | full tree
settings_consistency | pass | full tree
wiring_audit | pass | full tree
regenerate_all | needs-host-check: SKIP loot_point_preserve existing validation passed; byte regeneration: full DayZ client Addons unavailable (dedicated-s | full tree
generated_digests | FAIL (digest receipt verification) | full tree
mission_sources | pass | full tree
hygiene | FAIL (1) | full tree
hc_events | pass | full tree
ce_slot_pressure | skipped: staged CE mission not provided (--ce-mission or HC_CE_MISSION) | full tree
overlay_vanilla | skipped: host mission not provided (--overlay-mission or HC_OVERLAY_MISSION) | full tree
world_mesh_audit | skipped: DOOR_SELECTION_UNAVAILABLE_OR_INCOMPLETE, FULL_CLIENT_VISUALS_REQUIRED, GEOMETRY_LOD_EMPTY_OR_MISSING, LIVE_TERRAIN_AND_SHELTER_RETRIES_REQUIRED | full tree
asset_lint | no applicable inputs (assets_src holds no built MLOD/IR) | full tree
dayz_build | pass | full tree
unit_tests_changed | FAIL (1) | changed files
preland: FAILED; engine compile/boot acceptance remains separate
Exit: 1
```
