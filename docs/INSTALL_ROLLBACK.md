# Private portable package installation and rollback

This procedure covers development-package installation and rollback. Gameplay,
signed normal-server loading, production installation and save-schema migration
require separate validation. See [module status](MODULE_STATUS.md) and the
[issue tracker](https://github.com/d-addison/hollow-country/issues).

`tools/package/deploy.py` uses Python 3.10+ and the standard library. Run the
trusted helper beside the trusted repository `pbo.py`, or from the repository
with `python -m tools.package.deploy`. It accepts the existing verified
**private unsigned-development ZIP** format. It never executes archive helpers.
Distribute source privately and compare a package SHA-256 received through a
trusted channel before installation. Container checksums detect corruption;
they are not an addon signature or proof of who produced the package.

Before any member is opened, the installer checks declared entry count,
aggregate uncompressed bytes and each member's size. Limits are 8,192 entries,
64 MiB total uncompressed content and a 2 MiB manifest. Accepted members then
stream in chunks of at most 64 KiB, with declared-size and overrun checks,
before the existing container verifier runs. Stored and deflated ZIP methods
are accepted; other compression methods are refused. The compressed archive
itself is limited to 128 MiB. These checks bound admitted content, not total
Python heap usage while parsing and verifying it.

## Installation layout and ownership

Choose an existing local directory outside Steam, every source checkout and
the filesystem root. A missing destination is refused. The directory must be
on a local filesystem supporting same-volume renames and filesystem locks.
Avoid network shares, synchronized folders, junctions and mount arrangements
that separate the two managed children onto different volumes.

```text
D:\HollowCountryPrivate\                 # existing destination
  profiles\                             # external; installer does not edit
  storage\                              # external; installer does not edit
  other-mods\                           # external; installer does not edit
  HollowCountryPackage\                 # managed active tree
    @HollowCountry\addons\hollowcountry.pbo
    @HollowCountry\mod.cpp
    mission\hollow-country\...
    tools\package\...
    manifest.json
  .hollow-country-deploy\                # managed journal and backups
    owner
    lock
    state.json
    transactions\<transaction-id>\
      journal.json
      before\                           # exact prior package tree, if any
      result.json
    quarantine\                         # preserved interrupted metadata writes
```

Only the two managed children are owned. Existing unrelated siblings are
preserved. A pre-existing active tree without owned metadata, an unrecognized
metadata directory, case aliases, symlinks/reparse points, hardlinked managed
files, special files or path traversal cause refusal. Files and even empty
directories added to the managed active tree count as drift. Keep operator
settings, mission saves, storage and profiles **outside** that tree.

The installer copies the entire verified ZIP payload into the active tree,
including packaged instructions and CE templates. It does not merge templates
into an actual mission, install a key, alter launch options, change features,
start a server or weaken signature enforcement. CE changes remain a separate
explicit operation using the existing `economy.py` procedure.

## Plan, install and upgrade

1. Stop the server, client tools and every other process that writes the target.
   Make a separate verified backup of runtime profiles, mission storage and
   configuration before the first runtime test. The installer does not open or
   copy these opaque saves. `--server-stopped` is an operator acknowledgement,
   not process detection or proof that the world was saved cleanly.
2. Keep a trusted tool copy **outside the managed active tree** so recovery
   remains available while that tree is parked. Use a fresh existing destination
   for initial installation. Keep experiments separate from a live server until
   the runtime handoff is accepted.
3. Run the read-only plan. It verifies the ZIP, PBO source manifest, managed
   state and current active bytes. Plan emits JSON and writes nothing.
4. Install and save the JSON transaction ID. Upgrade and rollback require the
   same stopped-server discipline. Repeating the same package installation is
   an idempotent no-op after verifying current bytes.

PowerShell example; adapt the ZIP filename to the actual verified artifact:

```powershell
$python = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
$tool = 'C:\HollowCountryTrustedTools\deploy.py'
$zip = 'C:\HollowCountryIncoming\hollow-country-0.1.0-dev.zip'
$destination = 'D:\HollowCountryPrivate'
& $python $tool plan --zip $zip --destination $destination
& $python $tool install --zip $zip --destination $destination --server-stopped

# Later, with the server stopped, validate and install a new ZIP:
$next = 'C:\HollowCountryIncoming\hollow-country-next-dev.zip'
& $python $tool plan --zip $next --destination $destination
& $python $tool upgrade --zip $next --destination $destination --server-stopped
```

The example tool directory must also contain the trusted `pbo.py`; copy both
from the same reviewed source revision. Unix equivalent:

```bash
python3 tools/package/deploy.py plan --zip /private/incoming/build.zip --destination /private/runtime
python3 tools/package/deploy.py install --zip /private/incoming/build.zip --destination /private/runtime --server-stopped
```

Exit code 0 means the package operation completed or was already complete;
JSON reports `status`, `transaction`, `idempotent` and runtime acceptance
`pending`. A refusal prints a reason to stderr and exits nonzero. Preserve logs
and destination metadata after failures. The active mod path for later approved
runtime testing is `D:\HollowCountryPrivate\HollowCountryPackage\@HollowCountry`.
Native signed deployment needs the separately verified signing workflow; this
ZIP installer intentionally accepts the development manifest contract only.

## Package migration and world-save migration are separate

`migrate` is an explicit alias for a verified **package upgrade**:

```powershell
& $python $tool migrate --zip $next --destination $destination --server-stopped
```

It preserves every external profile/storage byte because those paths are never
opened for mutation. It does not rewrite DayZ saves, convert Hollow Country
runtime schemas, reconcile live inventories, reset building epochs, migrate CE
ownership, or declare old saves compatible with new scripts.

A gameplay schema change needs its own versioned migration step: back up the
stopped server's saves; migrate a disposable copy; test load/restart and state
invariants in the pinned DayZ build; then test exact restore with the previous
signed package and matching save snapshot. Package rollback alone cannot undo
state written by a newer runtime. Never silently wipe or restore profiles to
make an incompatible mod load. Those native save-migration gates remain open.

### Runtime migration runner (`HCMigrationRunner`)

The mod itself carries a boot-time runner for persisted Hollow Country profile
files. It runs once per server start inside the persistence admission, after the
recovery attestation is accepted and before any store module opens its file.
It keeps no ledger: each boot every registered step inspects its target file, so
a crash at any point leaves a state the next boot classifies and repairs. No
step that changes behaviour is registered until a plan names the schema change;
with none registered the runner only prints the line below and a self-test
receipt. Native behaviour is `runtime=PENDING` until the lead's boot check.

Step contract: one step per target file, compared case-folded (a second step on
the same target is refused at registration as `duplicate_target`, and a second
step reusing an id on another target as `duplicate_id`; both close the step's
store on every boot until the build changes, because the registry is rebuilt
from the code at each server start). Registering the same id on the same target
twice is a no-op. A step's declared store must be the one the recovery gate maps
its target to (a store file declared ungated or gated by another store is refused
as `step_invalid_store`), and targets with `.`/`..` segments are refused as
`step_invalid_target`.
A schema change on a file that already has a step edits that step: `current` is
what this build writes and `old` widens to every earlier schema. The step's
classifier must return unknown for every torn prefix of any text it calls
current or old, and for an empty file; this is the load-bearing invariant the
torn-commit recovery below relies on. A step with no store gate (`""`) is never
deferred; if the runner's own self-test fails, every registered step is refused
and its store closed for that boot.

Per step, with target `T`, scratch image `P` (`T.mig-<id>.tmp`) and backup `B`
(`T.pre-<id>.bak`, then `.bak2`..`.bak4` when a slot holds other bytes):

1. Classify `T` as current, old, newer or unknown. Current is skipped; newer or
   unknown is refused and never edited.
2. Copy `T` to the first free backup slot and read it back. An occupied slot with
   different bytes is evidence and is never overwritten or deleted.
3. Write the full migrated image `P`; it must itself classify as current.
4. Delete `T`, copy `P` over it, read `T` back, then delete `P`. The native API has
   no rename, so this step is not atomic; `P` and `B` stay until readback passes.

Every receipt is one RPT line: `[HC Migrate] id=<id> action=<applied|skipped|refused> reason=<r>`.
A refusal (or a step deferred past the boot budget of 8 steps / 250 ms) closes only
that step's store for this boot through the shared quarantine line
`[HC Plan] HC-28 store=<name> recovery=quarantined reason=migration_<r> files=preserved`.
Deferred steps then finish one per tick, so the next boot is clean. No file is
deleted or wiped to make a refusal go away.

A leftover `P` is deleted only when it is provably ours: beside a current `T` an
empty file or one identical to `T`; beside an old `T` an empty file, a torn prefix
of the image about to be written, a copy of `T`, or an image a retained backup
slot reproduces through the transform. A complete current `P` without that proof
may be the only newest copy (for example after you restored an older `T`), so it
is kept and the step refuses. Any other `P` is kept and the step refuses
(`pending_conflicts_current`, `pending_conflicts_old`). If `P` cannot be deleted
after a verified commit the store is closed for that boot (`pending_delete_failed`).
The next boot removes it only if the delete then succeeds (`current_pending_removed`);
if it still fails the step refuses as `current_pending_cleanup_failed` and the store
stays closed on every boot until you remove `P` by hand.

| Interruption | Next boot |
| --- | --- |
| Before or during the backup copy | `T` is still old; a torn backup slot is skipped, a fresh slot is used |
| After backup, before or during `P` | `T` is old; stale `P` is deleted and recomputed, an identical backup is reused |
| After `P`, before deleting `T` | Same as above |
| After deleting `T`, before the copy | `T` absent and `P` present: `P` is restored only if a backup slot proves it descends from that backup (old class plus the deterministic transform reproduces `P`) -> `recovered_missing_target` |
| During the copy over `T` | `T` is a readable empty file or a torn prefix of `P`: same proof, then `recovered_torn_commit`. Any other readable content is refused as `target_schema_unknown`; an unreadable or oversize `T` is refused as `target_unreadable` and never replaced |
| After the copy, before deleting `P` | `T` is current; the stale `P` is removed (`current_pending_removed`) |
| Newer schema on disk (a rollback of the mod without the saves) | `refused reason=newer_schema`; install the matching mod version, or restore the matching `B` by hand with the server stopped |

Operator steps for a refusal (server stopped, every file kept until you decide):

- `backup_slots_full`: all four `.pre-<id>.bak*` slots hold other bytes. Compare
  them with `T`; move the ones you no longer need out of the profile folder (do
  not delete the only copy of anything), then start the server again.
- `pending_provenance_missing`: `P` exists but no backup slot proves it descends
  from an old file. Do not copy `P` over `T`. If `T` is intact and old, move `P`
  aside; the next boot recomputes it. If `T` is missing or torn, restore the
  matching `.pre-<id>.bak*` over `T` by hand, move `P` aside, and start again.
- `target_schema_unknown` with `P` present: `T` is not a prefix of `P`. Keep both,
  restore `T` from the matching backup (or from your own snapshot), move `P`
  aside and start again. Never copy `P` over an unrecognised `T`.
- `target_schema_unknown` without `P`: `T` is not a format this build knows;
  restore the matching backup or the matching mod version.
- `pending_conflicts_current` / `pending_conflicts_old`: `P` is not the image this
  build would write. Inspect it, move it aside, start again. If `P` is a complete
  image newer than `T` (you restored an older `T`), keep `P` and decide by hand
  which of the two you want before starting again.
- `target_unreadable` with `P` present: `T` is oversize or cannot be opened, so it
  is evidence and is never replaced from `P`. Check the file size, permissions and
  whether another program holds it; fix that or restore `T` from a backup, keep
  `P`, and start again. Do not delete either file to clear the refusal.
- `pending_image_invalid`: `P` is empty, unreadable or does not classify as current
  (a torn or foreign scratch image). If `T` is intact move `P` aside and start
  again; if `T` is missing or torn restore the matching `.pre-<id>.bak*` over `T`
  first.
- `commit_failed_pending_kept`: the copy of `P` over `T` or its readback failed
  (disk full, a lock, antivirus). `P` and `B` are kept and `T` may be missing or
  partial. Free space or remove the lock and start again: a missing or torn `T` is
  recovered from `P` automatically. If it repeats, restore `B` over `T` by hand and
  move `P` aside.
- `pending_cleanup_failed`: a stale `P` beside an old `T` is ours but could not be
  deleted, so nothing was migrated. `T` is untouched. Remove the lock or fix the
  folder permissions, or delete that one `P` by hand, and start again.
- `current_pending_cleanup_failed`: `T` is current and an identical or empty `P`
  could not be deleted. The store stays closed on every boot until `P` is gone;
  delete that one `P` by hand (or fix the permissions) and start again.
- `duplicate_target` / `duplicate_id` / `step_invalid_*`: a defect in the build's
  step list, not in your data. The affected store stays closed on every boot until
  the build changes; no file edit helps. Install the build that fixes it or the
  previous release.
- `selftest_failed`: the runner's own file IO on its scratch probe files failed
  (read-only or full profile folder, a lock). Every registered step is refused and
  its store closed for that boot. Read the
  `[HC SelfTest] name=migration_runner pass=false detail=<d>` line, fix the folder
  problem, remove any `migrate-selftest.probe*` scratch files, and start again.

To undo a migration by hand with the server stopped, copy the `.pre-<id>.bak`
file back over the target and install the previous PBOs. `storage_*` (the DayZ
hive) is never touched. The runner never prunes `.pre-` backups; delete them only
after the release has proven stable.

## Exact package rollback

Keep the installation/upgrade transaction ID from stdout. Rollback accepts only
the current forward transaction; it refuses an older target while a newer
upgrade remains applied. The operation stages a verified copy of that
transaction's `before` snapshot, parks the current tree, publishes the prior
tree, then commits a new journaled state. File names and bytes, including the
original manifest, match the previous installation. Backups are retained; no
history is silently pruned. Unix ownership/ACLs and timestamps are not the
rollback acceptance contract; the saved tree rename preserves original backup
metadata, but reconstruction guarantees the recorded file bytes and tree shape.

```powershell
& $python $tool rollback --destination $destination --transaction '<32-hex-upgrade-transaction-id>' --server-stopped
```

Repeating that exact rollback command is a no-op. It never rolls back a second
generation by accident. To undo an earlier upgrade, explicitly supply that
earlier forward transaction ID after the newer one has been undone. Rolling
back the initial installation removes the active slot by parking it in the
rollback transaction; external profiles and unrelated data remain present.

Any altered active file, missing file, extra empty directory, invalid journal,
changed receipt, unsafe path or altered target backup causes refusal. Preserve
the evidence and reconcile it explicitly; there is no `--force` deletion,
overwrite, stale-lock break or profile-reset option.

## Interrupted operations and recovery

An immutable pending journal is published before package mutations. Prepared
files are individually flushed, then complete tree hashes are checked. An
upgrade renames active → transaction `before`, renames staged → active, and
atomically replaces `state.json`. That state replacement is the commit point.
The OS releases the exclusive file lock if the process dies.

Stop all destination writers, retain the whole directory, then choose:

```powershell
# Cancel an uncommitted operation and restore its original package:
& $python $tool recover --destination $destination --action abort --server-stopped

# Finish a fully prepared operation after examining its journal:
& $python $tool recover --destination $destination --action resume --server-stopped
```

| Observed interruption | `abort` | `resume` |
| --- | --- | --- |
| Journal only / partial staging | Restores or retains original; preserves staged debris | Refuses incomplete staging |
| Staging complete | Retains original | Publishes staged package and commits |
| Original parked, replacement not published | Restores original backup | Publishes complete stage and commits |
| Replacement published, state not committed | Parks replacement and restores original | Checks replacement and commits |
| State already committed | Finalizes the committed receipt | Finalizes the committed receipt |
| Recovery interrupted | Repeats its persisted decision | Repeats its persisted decision |
| Drift, ambiguous slots or corrupt authoritative metadata | Refuses; preserves evidence | Refuses; preserves evidence |

A committed operation is not automatically reversed by `recover --action abort`;
use an explicit targeted rollback. A persisted recovery decision wins if a
retry supplies a different action. Unpublished partial metadata is moved into
`quarantine`, and unpublished package writes remain under their transaction;
neither is deleted. Repeated recovery after completion reports no pending work.

A complete metadata bootstrap interrupted before its directory rename can be
promoted by recovery. Incomplete/unrecognized bootstrap ownership or corrupted
authoritative state is deliberately refused; preserve it for manual inspection.
No active package is modified before initialization completes.

## Search house journal crash points

The house-search journal is per-record JSON, one file per step under its own
root (`entry_`, `claim_`, `attempt_`, `result_` and `compact_` with the slot
number, plus the retired-supply archive). Since Wave C every write and delete
runs through the shared save scheduler, one native call per stage (the first
stage of a new file also makes two existence probes), in strict first-in
first-out queue order (queue pops are ordered removals; the engine's plain
array remove would move the last element forward and break the order). The bytes on disk are unchanged: a journal written by an older
build loads as is, and an older build reads a journal written by this one. A
new file is created directly at its final name (no rename step) and read back
and byte-compared; an existing name is never overwritten. Entry, claim,
attempt and result writes are synchronous barriers: the caller does not
proceed until the file is verified. The compact intent, the five compaction
removals and the removal of old `spent_*` tombstones are routine staged work.
No journal file is ever deleted by a recovery decision except as the last
step of a completed compaction. Nothing here is a world wipe, and none of
these states needs operator action unless the table says the journal is
preserved.

| Crash point (process dies after) | State on disk | Next boot |
| --- | --- | --- |
| Entry create started, file partial | `entry_<n>` torn, nothing else for the slot | Self-repair: the torn entry is removed and the slot is free; the supply was never handed out. A torn entry that has any claim, attempt, result or compact file beside it is not this case and faults with a reason |
| Entry create finished | `entry_<n>` complete | Row restored as available (phase 0) |
| Claim create started, partial | `entry_<n>` plus torn `claim_<n>` | Claim does not match: row restored as quarantined, never searchable again |
| Claim complete, no attempt | `entry_<n>`, `claim_<n>` | Intent without result: row restored as quarantined (spent for good) |
| Attempt partial or complete, no result | claim plus torn or complete `attempt_<n>` | Quarantined, as above |
| Result partial or missing after the native move | claim, attempt, torn or no `result_<n>` | Quarantined; a result that does not match its claim is never trusted |
| Torn `entry_<n>` while the directory listing missed a claim, attempt, result or compact file | torn entry plus a sibling the listing did not show | Boot probes each sibling by exact name before deleting; if any exists the journal faults with a reason and deletes nothing, so a possibly handed-out supply is never freed |
| Torn `compact_<n>` whose entry is invalid, or whose supply is already in the archive | `compact_<n>` unreadable, entry failing a boot check or its supply recorded | The torn intent is removed only after the entry passes every boot check and its supply is not recorded. Otherwise the journal faults with a reason and `compact_<n>` is kept, so a transient read failure retries on the next boot |
| Result complete | claim, attempt, `result_<n>` phase 2, 3 or 4 | Restored as spent, quarantined or no-transfer as recorded, except that phase 2 without an `attempt_<n>` is restored as quarantined |
| Compact intent queued, not yet created | terminal slot files only | Nothing lost; the slot is compacted again by the normal pass |
| Compact intent created, file partial | torn `compact_<n>` plus the slot files | Self-repair: removals and the archive checkpoint are queued only after the intent was read back, so the slot is untouched. The torn intent is removed and the row is restored as terminal (never available) and compacted again later. Only an unreadable intent with an unreadable or missing entry faults and is preserved |
| Compact intent complete, retirement archive not yet checkpointed | `compact_<n>` plus all slot files | Boot re-runs the cleanup: archive checkpoint first, then the removals below |
| Archive checkpointed, no removal done | `compact_<n>` plus all slot files, supply listed in the archive | Boot repeats the same removals; the archive entry is idempotent |
| Removal of `claim_<n>`, `attempt_<n>`, `result_<n>` or `entry_<n>` done, others pending | `compact_<n>` and a subset of the slot files | Boot finishes the remaining removals (missing files are accepted); a half-removed slot is never restored as an entry |
| All four removed, `compact_<n>` not yet removed | `compact_<n>` only | Boot removes it; slot becomes free |
| Compact intent removed | slot empty | Slot free for reuse; the supply stays known through the archive |
| Legacy `spent_<supply>` removal pending or interrupted | old tombstone still present, supply also in the archive | Supply still counts as known; the tombstone is migrated and removed again in the background |
| Slot reused: removals of the old slot done, new `entry_<n>` partial | torn `entry_<n>`, no `compact_<n>` (it is removed before the create starts) | Torn-entry self-repair above: slot free, nothing handed out |
| Slot reused: crash while the old slot's removals are still queued | `compact_<n>` and a subset of the old slot files; the new entry was never started | Boot finishes the old compaction first; the reuse is simply retried later |
| Queue full (no crash) | whatever was already verified | Routine producers stop at 16 queued operations (at most 3 creates), so a claim barrier normally finds room and drains at most about 70 native calls. If the queue is ever full, the barrier drains it before enqueueing; it never faults the claim. Routine work waits and retries |
| Writer failure (no crash) | whatever was already verified | A failed barrier write refuses the caller with a reason and the journal is preserved rather than guessed. The journal reports this itself and does not make the world save module report not ready |

Slot reuse is safe because the queue is first in, first out (ordered pops): the
removals of a slot's previous files, `compact_<n>` last, always precede the next
create for that slot, so a crash leaves either the old slot still compactable or
the new entry alone. Legacy `spent_<supply>` names are indexed once at boot (up
to 65,536). Past that the index is incomplete: boot checks the exact tombstone
file for each live entry instead of the index, and until the legacy files have
drained (32 per minute) every supply not already recorded in a journal row or
the archive is treated as known, so no new supply is bound while draining.
The index is dropped only after two consecutive empty directory scans, and a
legacy file is removed only when the archive image holding its supply has
committed. Nothing
about this table is proven in game; it follows from the code and from the
recovery rules above, which are unchanged. Runtime acceptance stays PENDING.

## Validation and limits

Run the behavioral suite on disposable temporary directories:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_deploy.py -v
```

Tests cover real file operations and subprocess termination, package roundtrips,
profile sentinels, both recovery outcomes, idempotence and tampered data. They
do not establish Windows filesystem behavior, actual save compatibility, native
module loading, public-key authenticity, native gameplay or destination-server
rollback. The Windows reparse guard is exercised with explicit synthetic stat
attributes; an actual NTFS junction test still belongs in native validation.

The transaction protocol assumes a trusted local directory with no hostile
concurrent namespace changes. Locks coordinate this utility, not arbitrary
editors or administrators. Portable Python cannot close every cross-platform
check/use race against another local process replacing directories. Rejecting
links does not grant protection against a hostile machine owner.

Files are flushed before rename and parent directories are flushed on POSIX.
Python's Windows standard library has no portable directory flush, so tests
establish process-crash recovery, not unconditional power-loss durability on
every filesystem/controller. A failed rename, disk-full write or corrupt commit
stops the operation and retains evidence for explicit recovery. Retention is
bounded at 128 transactions; reaching it refuses additional changes. Do not
manually delete journals or backups to bypass that limit; archive and review
the deployment history before establishing a fresh owned destination.

## Friend server installation

Development target: DayZ Standalone 1.30, ChernarusPlus, 3–6 players. Features
are being built and V2 preferences default on. Native compilation, normal signed
PBO/server tests, client joins, persistence and single-client checks remain pending.
Nothing in a bundle build establishes DayZ behavior or production acceptance.

The server and every client use this ordered list. Subscribe to the original
Workshop items; never repack, modify or redistribute them.

| Item | Workshop ID | Installed server folder |
| :--- | :--- | :--- |
| Community Framework | 1559212036 | `@CF` |
| Community Online Tools | 1564026768 | `@COT` |
| Dabs Framework | 2545327648 | `@DabsFramework` |
| Expansion Core | 2291785308 | `@Expansion-Core` |
| Expansion AI | 2792982069 | `@Expansion-AI` |
| Expansion Navigation (GPS) | 2792984722 | `@Expansion-Navigation` |
| SNAFU Weapons | 2443122116 | `@SnafuWeapons` |
| Tactical Flava | 2646817942 | `@TacticalFlava` |
| RaG_Core | 3556131153 | `@RaG_Core` |
| RaG Immersive Vehicles | 3105330157 | `@RaG_Immersive_Vehicles` |
| Ambient Animals Pack | 3114410963 | `@AmbientAnimals` |
| Hollow Country | 3841628320 | `@HollowCountry` |
| Hollow Country Expansion AI | 3841637854 | `@HollowCountryExpansionAI` |

Expansion-Animations is intentionally not loaded; Expansion-AI brings its own AI animations. Survivor Animations and DayZ-Bicycle were retired on 2026-11-22 (see the upgrade note in INSTALL_ROLLBACK.md); an existing subscription is harmless and is no longer loaded.

### Upgrade note: Survivor Animations and DayZ-Bicycle retired (2026-11-22)

Both Workshop items are dropped. Survivor Animations references about 130 animation
files its own package does not ship, and DayZ-Bicycle needs it; the owner chose to
drop both rather than patch third-party content. The vanilla motorbikes stay.

Upgrading an existing server needs no wipe. Bikes and bicycle parts that players left in
the world, in inventories or in tents are dropped by the engine when the world loads once the
mods are gone; no Hollow Country data references them. This has not been observed yet and is
checked at the first retail boot after the upgrade. Ask players to empty bike cargo before the
upgrade so nothing of value is inside a bike that disappears.

- Remove `@SurvivorAnimations` and `@DayZ-Bicycle` from the server and client `-mod` lines.
- `workshop_sync` keeps both folders in a `retired` list in `tools/setup/workshop_mods.json`,
  so an older receipt that names them still loads; sync no longer downloads or loads them.
- The friend installer removes what the Workshop receipt recorded for the retired folders:
  their files and their copied `.bikey` files in `keys/`. A file that changed since the
  install is left in place and listed. `workshop_sync rollback` removes the same files.
  A key the receipt does not record is not touched; delete it from `keys/` by hand.
  A root `keys/*.bikey` is also kept when any live `@*/keys` folder (not only the ones the
  receipt names) or the bundle's own `keys/` folder provides the same key name (compared
  ignoring case) or the same bytes, so an author key several mods share is never deleted;
  the plan prints "kept shared key <path>: <reason>". A kept key stays on the server but its
  row leaves the Workshop receipt (unless a mod folder the receipt keeps holds the same key
  under the exact same name), so the receipt stays valid and a rollback never deletes a key
  another mod needs. A receipt an earlier release already left with such an orphaned key row
  repairs itself when it is loaded: the row is dropped with a WARN naming the mod folder or
  bundle key that provides it, and the key file is never touched. A key row no other key
  backs is still refused (a receipt that names a key this tool never copied).
- The start-server.bat step removes a retired folder from `-mod=` or `-serverMod=` only when
  the Workshop receipt recorded that folder as created by this installer and the Workshop
  step removes it (or removed it in an earlier run: the install receipt keeps a
  `retired_removed` list for that). A retired folder the operator brought themselves stays
  in their list and the preview prints a WARN for it.
- An existing install that carried the bicycle overlay upgrades the normal way: the friend
  installer runs `bundle-rollback`, which restores the byte-exact backup recorded in the
  receipt (it does not depend on the current pack list), then `bundle-apply` installs the
  stack without any bicycle events or spawns. Do the same by hand with `bundle-rollback`
  followed by `bundle-apply` when not using the installer.
- Unsubscribing in Steam is optional; a leftover subscription is never loaded.

COT owner roles stay private in the server profile; see [COT permissions](COT_PERMISSIONS.md).
Admin ids are never written to git.

The manifest's `living_packs` group contains both RaG items and Ambient Animals. COT and Navigation are in `pve_patrols`. Select `base,snafu,tactical_flava,living_packs,pve_patrols` for the full
stack. The friend bundle selects these groups by default. Copy public `.bikey`
files to the server `keys` directory. Keep signing private keys outside the bundle.

Build both owned addons with `tools/package/Build-Sign-Verify.ps1`; HCX uses the
`HollowCountryExpansionAI` PBO prefix. The bundle expects signed addons from that
build, with matching public keys:

```sh
python3 -B -m tools.setup.friend_bundle build --mission /private/server/mpmissions/dayzOffline.chernarusplus --profiles /private/server/profiles --mod /private/build/@HollowCountry --addon /private/build/@HollowCountryExpansionAI --server-cfg /private/server/serverDZ.cfg --out /private/friend-bundle
```

The applied source mission supplies only HC-owned overlay files and minimal
core/gameplay changes. Untouched stock files (`init.c`, `db/globals.xml`,
`db/types.xml`, map placement/prototype files, weather files) never ship. Changed
CE rows live in HC overlay directories and registration/default changes live in
`mission-patches.json`; gameplay changes contain only changed leaf values. Optional
pack output and backups are stripped. Missing travel CE or authored optional
overlay sources refuse the build. All authored mission JSON, including the scene
catalog `hollow-country/events/scene-chains.json`, installs at its mission path.
CE building coverage is excluded; rerun its native sampler against the friend's
own mission separately. No sampler input or output is transported.

Install Python 3.10+ on the friend server. Install DayZ Server and obtain the
original dependencies with the friend's own Steam account. Keep numeric folders
under `steamapps/workshop/content/221100` for overlay generation; copy the mods
under the @ names above for the launch script. Copy only our signed @ folders,
public keys, selected profile configuration and `start-server.bat` from the bundle.
Merge the `serverDZ-hollow-country.txt` settings into the friend's own config;
keep passwords local, `verifySignatures = 2`, BattlEye on, and enableCfgGameplayFile.
The template in serverDZ.cfg must name the target mission. Forward UDP 2302–2305
and query UDP 27016. Keep the profile and CE storage outside the bundle/source.

Use the friend's own stock `dayzOffline.chernarusplus`, copied outside Steam and
outside this bundle/source checkout. Stop the server and all mission writers.
From the bundle folder run:

```sh
python -m tools.package.optional_overlays bundle-plan --mission /private/server/mpmissions/dayzOffline.chernarusplus
python -m tools.package.optional_overlays bundle-apply --mission /private/server/mpmissions/dayzOffline.chernarusplus --workshop-dir /steamapps/workshop/content/221100
```

`bundle-plan` previews the authored merge. `bundle-apply` requires the default
living-pack sources plus Navigation and RaG_Core, rehearses the merge and travel/optional plans on scratch,
then writes a backup receipt before any mission file mutation. It installs the
base merge, travel CE and Ambient/RaG/GPS overlays, then the loot boost last. Each installer
has its own receipt, including the first installation. Unknown existing overlay
files and conflicting edited values refuse. Interrupted installs remain reversible
using those receipts; preserve every receipt and backup. No stock mission is
replaced wholesale. Do not merge another CE owner for the same class/event.

**Loot boost (on by default).** `bundle-apply` finishes with `tools/package/loot_boost.py`, which
regenerates the change from the friend's own installed mission bytes (no vanilla file ships):
non-firearm `nominal`/`min` in `db/types.xml` and registered HC CE types files, group/container
`lootmax` in `mapgroupproto.xml` and `RespawnTypes` in `db/globals.xml` (capped at 64) are
multiplied by `Multiplier` in `mission/hollow-country/loot-points/settings.json` (default 2.0,
range 1.0-4.0). Weapons/explosives categories (firearms, ammunition, magazines, attachments),
the firearms roster, uncategorized rows and every container that lists weapons or explosives keep their stock values; added spots never carry those categories.
It also merges `loot-points/additions.json`: model-derived floor points per building family
(kitchen food, garage/shed tools, police and military at existing weapon scarcity, medical,
fire, civic and residential), at most 12 points per building and 3000 in total. Its own
receipt and byte-exact backups live in `hollow-country-loot-boost`; rollback undoes it first.
`InitialSpawn`, `RespawnLimit`, `RespawnAttempt` and cleanup values are unchanged. Native CE
acceptance of the added containers and the entity/performance cost are not yet observed.


The guided friend installer (`python -m tools.setup.friend_install`) keeps its
run journal and backups under `hollow-country-install-backups/<run>/`. After an
interruption, `--check` reports pending work without changing files; rerun with
`--apply` and the server stopped to recover before installing. Recovery restores
or removes a target only when its live bytes match a recorded installer write;
bytes already equal to the baseline need no change. Files created where a target
was previously absent and files inside mission trees receive the same checks.
If bytes match neither, recovery leaves them untouched, lists every conflict and
its backup path, and retains `rollback_pending`. A previously absent target has
no original backup file; the listed path identifies its place in the run backup.
Keep the journal and backups, compare the conflicting files, and reconcile them
by hand before retrying. An older journal without written hashes can require this
manual review. Never delete the journal to bypass a conflict. Identical dependency
files are recorded as unchanged and receive no backup.

A hard exit (power loss, killed process) while a mission writer is running leaves
mission-tree bytes the installer could not record. The journal marks the tree
before the writer starts, so the next `--check` says "hard exit inside a mission
writer". Recovery then refuses with `rollback_pending` and names `--repair`.
`--apply --repair` (or answering `y` to "repair these (each backed up)? [y/N]" in
an interactive run) restores the whole mission tree from that run's verified
backup and then installs normally. A typed `y` allows that tree restore only: it does
not turn on `--repair`, so edited mod files, keys and the launcher are still refused
or kept exactly as they are. Before the restore, a copy of the partial tree is made
under a temporary name and renamed to `hard-exit-partial-<run id>` inside the run
backup once it is complete (the path is printed; a later attempt on the same run
adds `-2`, `-3`, so no stash is ever overwritten, and an unfinished temporary copy
is removed on the next try; if it cannot be removed the run refuses as `stash_cleanup` and
names it, so a leftover is never reused). A copy that fails halfway therefore never counts as a
stash, and the operator's mission edits are still in the tree for the retry. Without
that explicit step nothing in the tree is changed.

`--rollback <run>` is mostly a pre-restart tool. A run-created folder the server
has since written into is kept ("kept non-empty folder <path>") and everything else
is still undone. After the server has booted, files such as Expansion's
`AISettings.json` are rewritten on start, so the rollback refuses with a conflict
and changes nothing; that is the safe outcome. An interrupted `--rollback <run>`
is finished by rerunning `--rollback <run> --apply`; that call restores only that
run and installs nothing.

The installer also repairs itself. A dry run and `--check` print a **Repair
preview** of exactly what `--apply --repair` would change: managed files that are
missing or were edited, retired files left behind by an older release, files from a
partial previous install, and `db/globals.xml` values to carry forward. `--apply`
without `--repair` still refuses on edited managed files and names the flag. With
`--repair` each replaced file is copied into the run backup first and the run ends
with a **Repair receipt** whose rows equal the preview; it is also stored under
`repairs` in `hollow-country-install-receipt.json`. A second run reports nothing to
repair. Files the installer does not manage and world saves (`storage_*`) are never
deleted. An install receipt that is not valid JSON text is rebuilt under `--repair`
instead of blocking the install (`receipt_invalid`; the old bytes go to the run
backup). A receipt that cannot be opened at all (locked, permission denied, a folder
in its place) is never rebuilt: the run refuses with `receipt_unreadable` and the
reason, and converges on a later run once the cause is fixed. A receipt with an
unknown layout is never rebuilt (`receipt_invalid` says so). A file the installer did not write
that `--yes` replaces gets the same preview and receipt row as any repair.

An operator-edited `start-server.bat` is never replaced wholesale. `--repair` (and
`--yes` for a launcher the installer did not write) merges the `-mod=` and `-serverMod=`
lists and keeps the port, `-profiles`, `-cpuCount` and every other argument. The values
are read as whole tokens (quoted up to the closing quote, so `"-mod=@A;@Base Building Plus"`
stays intact; otherwise up to the next whitespace). The merged list is the bundle's
folders in bundle order, then every entry the installer does not manage in the operator's
own order (the operator's other mods and an operator `-serverMod=` list are kept). Entries
are compared by their last path component, ignoring case and slash style, so
`C:\mods\@CF` and `.\@CF` count as the bundle's `@CF` and are replaced by the bundle form.
All bundle folders of both lists are installer-managed for both: one the operator listed
in the other argument moves to the argument the bundle puts it in. Retired folders (the
manifest's `retired` list) are removed only when this installer installed them (see the
retired-dependencies note above). The preview names each mod as `added`, `removed`
(retired), `moved`, `replaced` (path form), `kept` or WARN (a retired folder the installer
did not install), and the old file goes to the run backup. `@rem`, `rem` and `::` lines
are comments. Only the unedited launcher an older bundle wrote is
replaced as a whole. A launcher that cannot be merged (no `-mod=` argument, not UTF-8
text, a value built from a `%variable%` or holding `!` (delayed expansion) or `^`, an
unclosed quote), recorded or not, is a
refusal with that reason under `--repair` and `--yes` alike: fix it by hand or move it
away. `install-hollow-country.bat`
never passes `--repair`; `--check` reports such a launcher as `launcher_problem` with the
same reason (not as a wrong mod order). In an interactive run the installer instead asks "repair
these (each backed up)? [y/N]" when the preview has blocked rows.

Operator `db/globals.xml` values survive an upgrade. The installer rebuilds the
bytes it wrote last time from the loot receipt, treats every variable that differs
from them as the operator's own, undoes the old boost, applies the new one, then
re-applies the operator's values (BOM and line endings are preserved; comments are
kept only where they exist in the new file). A variable the operator removed comes
back with a WARN. A boosted variable that is back at its pre-boost value counts as
a reset, not tuning: the installer warns and applies the boost again. The whole file put
back to its stock bytes is read the same way (every boosted variable is a reset). To keep
the stock value on purpose, run with `--keep-stock-globals`: the variables that are back at
stock are recorded as an opt-out in the install receipt (`globals_optout`), the run keeps
their stock values, and no later run applies the boost to them again (the plan lists them).
`globals_optout` must be a list of variable names; any other value is refused as
`receipt_optout_invalid` and `--apply --repair` rebuilds the list from the loot-boost state
on disk (the variables at their stock value), keeping the rest of the receipt. A receipt
rebuilt by `--repair` because it was not valid JSON keeps the opt-out too: from the old
text when the array is still readable, otherwise from the loot-boost state.
The run lists each carried value and keeps the operator's exact file in the run
backup. When the receipt or backup cannot prove what the installer wrote, the file
is left untouched and the run refuses with the reason. After a carry-forward the
file no longer equals the loot receipt's recorded result, so use
`python -m tools.setup.friend_install --rollback <run>` (or rerun the installer)
instead of the standalone `bundle-rollback`. `--rollback <run>` restores the
files of that one run from its backup and refuses any file edited since the run.

Rollback with the server stopped:

```sh
python -m tools.package.optional_overlays bundle-rollback --mission /private/server/mpmissions/dayzOffline.chernarusplus
```

Rollback rehearses before changing live files, then undoes the loot boost, optional packs,
travel and the base merge, restoring the friend's own exact bytes. Drift refuses instead
of overwriting changes. It does not wipe the hive or remove persisted bikes or
animals. Restore profile configuration separately from your stopped-server backup.

The action **Tape light to weapon** accepts weapon lights only, consumes tape on
mounting and returns no tape on removal. Handheld flashlights are not accepted.
This is the intended action contract; validate the native action on joined clients.

After the lead's Windows compile, inspect the normal server logs for
`[HollowCountry] V2 admission feature=` (the `HCV2Admission` helper output),
subsequent errors, scene catalog diagnostics and optional provider
diagnostics. Each V2 module must print exactly one admission line. Bundle CLI
output (`HC bundle bundle-apply complete; runtime acceptance pending`) establishes
installer completion only. All gameplay acceptance remains pending.

Workshop metadata preparation remains owner-operated and Unlisted. Use
`python -m tools.package.workshop_publish prepare` (`tools/package/workshop_publish.py`) with a signed owned mod;
`--item addon` selects HCX. The alternative is DayZ Tools **Publisher**, pointed at
the prepared content folder, with **Unlisted** visibility. After an authorized
upload, `record` stores the item's published ID. Preparation sends no credentials;
Steam handles its interactive login and Steam Guard. Public/Workshop publishing
is not authorized by this fix task; these are operator instructions only.

The dependency helper is `tools/setup/workshop_sync.py`. Preview subscriptions
and server folder copies using:

```sh
python -m tools.setup.workshop_sync plan --server-root /private/server --workshop-content /steamapps/workshop/content/221100 --groups base,snafu,tactical_flava,living_packs,pve_patrols
```

Its `fetch` command asks Steam to download subscriptions with the owner's own
interactive account; `install` copies the original signed files into the server
folders and writes a receipt; `rollback` removes only files that receipt owns.
Run installs/rollbacks with the server stopped. The Workshop title remains
**Hollow Country Expansion AI (server)** for continuity, while every player loads
`@HollowCountryExpansionAI` in `-mod` after `@HollowCountry`. The full argument is:

```text
-mod=@CF;@COT;@DabsFramework;@Expansion-Core;@Expansion-Licensed;@Expansion-Vehicles;@Expansion-AI;@Expansion-Navigation;@SnafuWeapons;@MoreFoodV2;@CookZ;@UncuepasCivilianClothing;@WindstridesClothingPack;@AdditionalMedicSupplies;@dzr_notes;@BuildingFortifications;@gebsfish;@TacticalFlava;@RaG_Core;@RaG_BaseBuilding;@RaG_Immersive_Vehicles;@AmbientAnimals;@HollowCountry;@HollowCountryExpansionAI
```
