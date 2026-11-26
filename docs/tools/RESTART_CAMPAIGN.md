# Restart campaign (targeted, lead only)

`tools.testing.restart_campaign` repeats graceful stops on one copied **server profile**.
It collects restart evidence for #375 and persistence; it does not establish multiplayer behavior.
It never supplies release-class evidence or invokes the release gate or activity checker.
No Enforce scripts, counters, driver kinds, or fixtures are added.

The default `plan` writes nothing and needs no Windows interop:

```sh
python3 -B -m tools.testing.restart_campaign plan
python3 -B -m tools.testing.restart_campaign plan --fault-recover world --fault-recover custody --fault-recover intent --fault-exhaust world --no-xai
```

| Kind | Default cycles | Planned time each | Behavior and evidence |
| --- | ---: | ---: | --- |
| A | 3 | 5 min budget | XAI on, client joins, short driver completes, client leaves, graceful server stop. First cycle creates a solo group and ping, visits police-chernogorsk, asks `fx_site_patrol_kill`, searches scav-chernogorsk and flips/drives a fixture vehicle. Later A cycles revisit both places without repeating the kill. |
| B | 2 | 5 min idle | XAI on, no client; idle starts after connect enabled. Control for A's join/leave stops. |
| C | opt in, one per flag | 5 min idle | One store locked before launch; require read_unavailable within 180 seconds, release about 20 seconds later, require recovery. Repeat flags for staggered world/custody/intent cycles. |
| D | opt in, one per flag | at least 40 min | Keep one store locked through attempt 12 and graceful shutdown; then a separate normal 5-minute D-readback cycle verifies retained file images and read_ok. |
| E | opt in, always last | 1 min | Freshly stage another profile copy from originals and a separate mission copy. Remove HC's XAI adapter, the installed folder defining `DayZExpansion_AI_Scripts`, and HollowCountryTest. No client. Judge boot/readiness/stop/crash only. |

The default total is 25 planned minutes. Boot, launcher, join and graceful-stop waits are additional.
A's script has a roughly five-minute bound; a refusal, timeout or missing completion receipt fails the cycle.
A successful driver receipt is followed by observation until at least three minutes after join. The helper uses the existing initial-spawn marker and fixtures;
it does not teleport the player. Fixture failures are evidence failures, not synthetic successes.

The lead must confirm the owner is not playing before `--yes`. The shared
`tools.release.host_lock` lease is held across staging, every boot, stop, reporting and restore.
Any running or unknown DayZ, DayZServer, or launcher state refuses launch or restore.
The campaign uses `WindowsHost.stop` (CloseMainWindow, up to 240 seconds), confirms both client images
gone before requesting the server close, and never escalates to a forced kill.
A crash or stop failure ends the loop; remaining cycles are `unrun`. When anything remains running,
the tool leaves staging in place and prints **stop DayZ by hand, then run restore**.

## Lead commands and native experiment

Do not start with a full fault campaign. Run the single-store, single-boot native micro-experiment:

```sh
python3 -B -m tools.testing.restart_campaign probe-lock --store world --yes
```

This is a real XAI-on server boot, with no client. It stages a copy containing an existing committed
world.json, holds one read-only share-none Windows handle, and requires
`[HC Persistence] store=world read_unavailable` within three minutes. It then stops gracefully with the
handle still held, releases the helper, compares world.json/.bak/.tmp byte hashes, and restores.
There must be no Fresh/quarantine path, store save, crash, SCRIPT (E), or VME. The helper acknowledges
start/close, closes in `finally`, responds to a release file, and self-expires after 75 minutes.
It is never killed. Missing or escaped/symlinked store paths are refused before opening.
A native Fresh path can emit read_ok without a Fresh log: unexpected read_ok while the lock remains
held is also a hard abort, not a successful read.

A successful probe writes a per-store prerequisite receipt outside `last-run`; a failed new probe clears
that prerequisite. Repeat the micro-experiment for each other store before requesting its fault mode:

```sh
python3 -B -m tools.testing.restart_campaign probe-lock --store custody --yes
python3 -B -m tools.testing.restart_campaign probe-lock --store intent --yes
python3 -B -m tools.testing.restart_campaign run --yes
python3 -B -m tools.testing.restart_campaign run --yes --fault-recover world --fault-recover custody --fault-recover intent --fault-exhaust world --no-xai
python3 -B -m tools.testing.restart_campaign restore
```

`--fault-recover` or `--fault-exhaust` without a store value defaults to world.
Native probe receipts are local observations, not an assurance about a different Windows/engine build;
repeat probes after changing that environment. Inspect each probe's report before the next command replaces it.

**FileExist under share-none** is an abort finding. The exclusive handle may make FileExist return false,
which can enter Fresh or `world_interrupted_pair` rather than read_unavailable. Polling notices quarantine,
Fresh, and unexpected read_ok immediately and requests graceful shutdown while preserving the lock.
The final hashes show any changes; a missing read_unavailable fails even if no explicit Fresh line exists.
This experiment remains mandatory and unverified until the lead runs it on Windows.

The strict fault-cycle contract compares the locked store's three images before lock and after stop and
rejects any store save line (save_refused is allowed). C also records hashes immediately before unlock.
Consequently **even a recovered C boot fails if a subsequent legitimate save changes those images**.
The report retains read_recovered and its counter independently of that strict verdict; a recovery trace
alone is insufficient to pass the specified fault-cycle data invariant.
D-readback compares the locked store's retained primary/backup/temp bytes before it loads, and requires
world/custody/intent read_ok. Other stores are allowed to change during D.

Interrupted runs may leave the lock helper alive. `restore` first requires all game images gone; it then
signals the helper and refuses removal until its close acknowledgment exists. Run restore again after closure.
Do not delete the staged profile or lock markers by hand while the helper is active.

## Exact evidence

Each XAI-on clean stop must have exactly one of each line in its own server RPT:

```text
[HC XAI Bridge] teardown retired_released=<n> retained=<n>
[HC Teardown] shelters_skipped=<n> pathgraph_skipped=<n> callbacks_removed=<n> packs_released=<n> rpc_skipped=<n>
```

All cycles require `Player connect enabled`, zero SCRIPT (E), zero VME / Virtual Machine Exception,
and no crash log, dump, `0xc0000374`, Unhandled exception, Access violation, or other rpt_summary CRASH match.
Ordinary boots, including E, require at least one `[HC Ready]` line and every such line `ready=true`.
Pending-read probe/D boots record readiness but permit the intentional read-pending degradation.
E requires no driver or teardown counters and refuses before launch if a remaining installed PBO's
CfgPatches.requiredAddons still names a removed addon. Unreadable/encrypted inventories also refuse.
This checks config.cpp and rapified config.bin, not just PBO hash parity.

A requires the client line `[HC Driver] connect session start`, the server's client `-> GAME LOADED`
state transition, and `[HC Driver] done run=restart-<cycle> ...` with no refused/unsupported/timeout steps.
The report retains no player identity from the join line. The real death should produce:

```text
[HC Test] fx_site_patrol_kill patrol=<authored-site> result=ok members_before=<n> members_after=<n-1>
[HC Expansion AI] site police-chernogorsk cleared-at=<UTC-seconds> saved=<n>
```

The persisted cleared-at UTC timestamp is required on the first A cycle and is the lockout baseline. On a later boot less than 600 seconds
later, require presence of `spawn refused: raided site lockout`; its frequency is not asserted.
At 600 seconds or later report `not_applicable(elapsed=<s>)`. Missing death evidence is unobservable.

Normal later A/B/D-readback boots require positive counters with these exact feature names:

```text
[HC Use] module=World feature=world_read_ok count=<positive>
[HC Use] module=Materializer feature=custody_read_ok count=<positive>
[HC Use] module=LootRefresh feature=intent_read_ok count=<positive>
```

Fault evidence (substitute world, custody or intent for `<s>`):

```text
[HC Persistence] store=<s> read_unavailable
[HC Persistence] store=<s> reason=<s>_read_retrying attempt=<n> action=retry_in_session
[HC Persistence] store=<s> read_recovered attempt=<n>
[HC Persistence] store=<s> reason=<s>_read_exhausted attempt=12 action=retain_retry_next_boot
[HC Persistence] store=<s> save_refused reason=read_pending count=1
```

The upgrade-only **counters** are `<s>_read_recovered` and `<s>_save_read_pending`, under the modules
above. There are no `_read_retrying` or `_read_exhausted` counters. C requires read_recovered;
D requires exhaustion and save_read_pending. The report shows both counter observations, including absence.
Retry delays are 5/15/45/120 seconds, then 300 seconds per attempt; attempt 12 takes about 38 minutes.

## Round-trip domain visibility

The report compares previous-stop hashes against next-boot hashes for all nine store images. Those hashes
establish profile continuity; read_ok establishes a completed read, not equality of every restored domain.
Every domain has an explicit previous-save → next-restore row. Missing comparable logs are unobservable,
not a persistence pass. No additional Enforce trace is implemented.

| Domain | Existing save trace | Existing restore trace / counts | Verdict and proposed single trace format |
| --- | --- | --- | --- |
| World store | No unconditional row-count trace | `[HollowCountry] V2 world loaded day=<n> places=<n> facts=<n> factions=<n>` | Unobservable comparison; propose domain=world phase=save/restore rows and revision. |
| Custody | No unconditional row-count trace | `[HC Materializer] custody_load file=ai-custody.json relocation_depth=<n> loaded=<bool>`; loaded is a status, **not rows** | Unobservable; propose domain=custody phase=save/restore rows and revision. |
| Search refresh | None comparable | No unconditional restore-row count; intent_read_ok only | Unobservable; propose domain=search-refresh phase=save/restore rows and revision. |
| Groups | None comparable | None comparable | Unobservable; propose domain=groups phase=save/restore rows and revision. |
| Site ownership / cleared-at | `[HC Expansion AI] site police-chernogorsk cleared-at=<UTC> saved=<n>` | No unconditional matching restored epoch trace | Unobservable; propose domain=site-ownership phase=save/restore rows, cleared_at and revision. |
| Holdouts | No unconditional matching trace | Runtime holdout/reconcile events do not describe restored persisted rows | Unobservable; propose domain=holdouts phase=save/restore rows and revision. |
| Leads | `[HC Leads] open_save state=durable revision=<n>` (conditional) | No unconditional matching restored row count | Unobservable; propose domain=leads phase=save/restore rows and revision. |
| Vehicles | No comparable HC store trace | VehicleRetire is conditional upgrade activity, not a CE vehicle-count restore trace | Unobservable; propose domain=vehicles phase=save/restore rows and revision. |

A common proposed format is `[HC Persistence RoundTrip] domain=<domain> phase=<save-or-restore> rows=<n> revision=<n>`.
The JSON/Markdown report proposes this format for every unobservable domain. This tooling does not add it.

VehicleRetire's stored-vehicle hook queues only `Expansion_Landrover_Base`
(`HCVehicleRetire.c:31–41,350–356`), and the retirement path emits
`[HC Use] module=VehicleRetire feature=retired count=<positive>` at line 284.
It is upgrade-only: expect it in the first cycle at most if the copied profile/mission contains that
stored family. Driving a fresh fixture car does not guarantee it. The report lists what was observed;
absence is not fabricated activity, and repeated activity deserves inspection.

## Storage and recovery

Receipts and backups live under the restart tool's own cache directory,
`~/.cache/hollow-country/restart-campaign/staging/`; soak-campaign state is never touched.
Evidence is outside that staging directory at `restart-campaign/last-run/` so Stager's cleanup cannot erase it.
A new run replaces the previous `last-run`; preserve it elsewhere before another probe/run if needed.
Each cycle has its own directory, a `selection.json` containing `targeted: true` and its `fault` flag,
and separate server/client subdirectories containing only files absent from the pre-launch snapshot.
An absent or ambiguous fresh RPT fails attribution. Old logs are never selected by mtime.
The top-level `report.md` and `report.json` include unrun cycles, errors, stop outcomes, crash classification,
script/VME counts, teardown lines, read/row visibility, domain comparisons, lockout, and observed counters.
Evidence files retain native contents locally; reports extract fixed, non-identifying trace grammars.

Server `-profiles=soak-profiles` holds world.json, ai-custody.json and search-refresh.json plus their .bak/.tmp
images. Mission storage is a different persistence location. The campaign stages once for A/B/C/D and never
uses `--fresh-world-state`. E restores that staging and creates a separate profile generation and mission;
its files are excluded from all round-trip checks. Original profile bytes are never intentionally edited.
