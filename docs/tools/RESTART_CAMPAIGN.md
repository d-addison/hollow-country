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
| C | opt in, one per flag | 5 min idle | One store locked before launch; require read_unavailable within 180 seconds of the first Ready/world-load line (bounded by SERVER_READY_MINUTES), release about 20 seconds later, require recovery. Repeat flags for staggered world/custody/intent cycles. |
| D | opt in, one per flag | at least 40 min | Keep one store locked through attempt 12 and graceful shutdown; then a separate normal 5-minute D-readback cycle verifies retained file images and read_ok. |
| E | opt in, always last | 1 min | Freshly stage another profile copy from originals and a separate mission copy. Remove HC's XAI adapter, the installed folder defining `DayZExpansion_AI_Scripts`, and HollowCountryTest. No client. Judge boot/readiness/stop/crash only. |

The default total is 25 planned minutes. Boot, launcher, join and graceful-stop waits are additional.
A's driver completion window is 600 seconds; a refusal, timeout or missing completion receipt fails the cycle.
A successful driver receipt is followed by observation until at least three minutes after join. The helper uses the existing initial-spawn marker and fixtures;
it does not teleport the player. Fixture failures are evidence failures, not synthetic successes.

The lead must confirm the owner is not playing before `--yes`. The shared
`tools.release.host_lock` lease is held across staging, every boot, stop, reporting and restore.
Any running or unknown DayZ, DayZServer, or launcher state refuses launch or restore.
The campaign uses `WindowsHost.stop` (CloseMainWindow, up to 240 seconds), requests client close then server close even when a stop request fails, and collects those errors.
It never asks the windowless launcher to close. It polls launcher, client, then server for up to another
240 seconds; an independently confirmed gone state resolves a lost interop reply. It never escalates to a forced kill.
A crash or stop failure ends the loop; remaining cycles are `unrun`. When anything remains running,
the tool leaves staging in place and prints **stop DayZ by hand, then run restore**.

## Lead commands and native experiment

Do not start with a full fault campaign. Run the single-store, single-boot native micro-experiment:

```sh
python3 -B -m tools.testing.restart_campaign probe-lock --store world --yes
```

This is a real XAI-on server boot, with no client. It stages a copy containing an existing committed
world.json, holds one read-only share-none Windows handle, and requires
`[HC Persistence] store=world read_unavailable` within three minutes of the first `[HC Ready]` or world-store load line, with the entire wait
bounded by `SERVER_READY_MINUTES`. It then stops gracefully with the
handle still held, releases the helper, compares world.json/.bak/.tmp byte hashes, and restores.
There must be no Fresh/quarantine path, changed locked-store bytes, crash, SCRIPT (E), or VME.
No store prints a save SUCCESS line; the old save-line check was a no-op (custody SAVE FAILED is not success). The helper acknowledges
start/close, closes in `finally`, responds to a release file, and self-expires after 75 minutes.
It is never killed. Missing or escaped/symlinked store paths are refused before opening.
A native Fresh path can emit read_ok without a Fresh log: unexpected read_ok while the lock remains
held is also a hard abort, not a successful read.

A successful probe writes a per-store prerequisite receipt with the commit SHA under `probes/probe-<store>.json`, outside `last-run`; a failed new probe clears
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
repeat probes after changing that environment. Probe reports live in `probes/<store>/`, separately from
`last-run`; a normal run preserves them. Repeating a probe replaces only that store's probe report.

**FileExist under share-none** is an abort finding. The exclusive handle may make FileExist return false,
which can enter Fresh or `world_interrupted_pair` rather than read_unavailable. Polling notices quarantine,
Fresh, and unexpected read_ok immediately and requests graceful shutdown while preserving the lock.
The final hashes show any changes; a missing read_unavailable fails even if no explicit Fresh line exists.
This experiment remains mandatory and unverified until the lead runs it on Windows.

C compares the locked store's primary/backup/temp hashes before locking and immediately **after**
release acknowledgment, never while the share-none handle is open. This checks that the locked window
did not change the images. Saves after read_recovered are legitimate; C does not compare
the locked store again after stop. Probe-lock and D retain the before-lock versus after-stop byte comparison, with the
helper released after shutdown and before hashing. Other stores may change in all fault modes.
Byte hashes are the actual data-integrity check; no store emits a save SUCCESS line.
D-readback compares the locked store's retained primary/backup/temp bytes before it loads, and requires
world/custody/intent read_ok. Other stores are allowed to change during D.

Interrupted runs may leave the lock helper alive. `restore` first requires all game images gone; it then
signals the helper and refuses removal while its recorded Windows PID is alive or unknown.
A close acknowledgment, or winproc confirmation that the recorded PID is gone, permits restore.
Run restore again after closure. Old markers without a valid recorded PID remain unknown and require inspection.
Do not delete the staged profile or lock markers by hand while the helper is active.

## Exact evidence

Every clean stop, including E, requires exactly one `[HC Teardown]` line in its own server RPT.
With XAI on, exactly one bridge teardown line is also required. Neither grammar has yet been seen
in a real clean-stop RPT; the lead must validate both on the native host:

```text
[HC XAI Bridge] teardown retired_released=<n> retained=<n>
[HC Teardown] shelters_skipped=<n> pathgraph_skipped=<n> callbacks_removed=<n> packs_released=<n> rpc_skipped=<n>
```

All cycles require `Player connect enabled`, zero SCRIPT (E), zero VME / Virtual Machine Exception,
and no `crash_*.log`, dump, `0xc0000374`, `0xc0000005`, Unhandled exception, Access violation,
or Exception code diagnostic. Lines beginning with an `[HC ` tag (after an optional RPT timestamp/SCRIPT prefix)
are ignored for crash classification, so `[HC Tour] label="Incident crash"` is ordinary content.
Ordinary boots, including E, require readiness markers and the last verdict per enabled module to be ready,
using the imported rpt_summary readiness grammar and failure rule. A disabled Sites module with
`ready=false` is allowed; AIRoles catalog_loading may be superseded by its later ready=true verdict.
Pending-read probe/D boots record readiness but permit the intentional read-pending degradation.
E requires no driver or bridge teardown counters and refuses before launch if a remaining installed PBO's
CfgPatches.requiredAddons still names a removed addon. Unreadable/encrypted inventories also refuse.
This checks config.cpp and rapified config.bin, not just PBO hash parity.

A requires the client line `[HC Driver] connect session start`, the server's client `-> GAME LOADED`
state transition, and `[HC Driver] done run=restart-<cycle> ...` with no refused/unsupported/timeout steps.
The report retains no player identity from the join line. The real death should produce:

```text
[HC Test] fx_site_patrol_kill patrol=<authored-site> result=ok members_before=<n> members_after=<n-1>
[HC Expansion AI] site police-chernogorsk cleared-at=<UTC-seconds> saved=<n>
```

The first cycle must have a timestamped successful fixture kill line above or the real
`[HCX SitePatrol] death_hold armed site=police-chernogorsk kills=<n>` line
(`HCTestReachFixtures.c:196`, `HCXAISitePatrols.c:92`). The first such event is the lockout baseline,
not the boot time or a conditional cleared-at save trace. On subsequent boots, measure to the first
police site-spawn attempt (`site police-chernogorsk spawn refused/held/skipped:` or
`DIAGNOSTIC spawn of site police-chernogorsk`). The report records `patrol_killed_at_utc` and
`first_spawn_attempt_at_utc`. RPT clock times are mapped to the nearest date of the boot on the host's
local clock; the WSL and Windows local timezones must agree for UTC labels to be accurate.
Below 600 seconds require `spawn refused: raided site lockout`; at or above 600 seconds report
`not_applicable(elapsed=<s>)`. Missing timestamped evidence is unobservable.

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
Every domain has an explicit previous-save → next-restore row. **All eight round-trip domains are
unobservable with the current logs**: no store emits a save SUCCESS line or comparable unconditional
save/restore row counts. Byte hashes remain the real data check. Missing comparable logs are unobservable,
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
A new normal run replaces only the previous `last-run`; probe evidence stays under `probes/<store>/`.
Each per-store prerequisite receipt includes `commit_sha`. Preserve a store probe before repeating that probe.
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

Before each launch the tool verifies that the staged start-bat uses the copied config/profile and expected
test-addon presence, and that the config names the expected mission template. A failed replacement refuses launch.
Live polling resolves per-launch log files once each peer has an RPT and tails them with byte offsets.
Transient log reads and unknown process replies tolerate up to `soak_campaign.UNREADABLE_POLLS` consecutive polls;
a confirmed gone process aborts immediately. Crash-file polling uses shallow scans of the resolved log directories.
