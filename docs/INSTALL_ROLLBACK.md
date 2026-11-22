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

| Interruption | Next boot |
| --- | --- |
| Before or during the backup copy | `T` is still old; a torn backup slot is skipped, a fresh slot is used |
| After backup, before or during `P` | `T` is old; stale `P` is deleted and recomputed, an identical backup is reused |
| After `P`, before deleting `T` | Same as above |
| After deleting `T`, before the copy | `T` absent and `P` present: `P` is restored only if a backup slot proves it descends from that backup (old class plus the deterministic transform reproduces `P`) -> `recovered_missing_target` |
| During the copy over `T` | `T` is an empty file or a torn prefix of `P`: same proof, then `recovered_torn_commit`. Any other content is refused as `target_schema_unknown` |
| After the copy, before deleting `P` | `T` is current; the stale `P` is removed (`current_pending_removed`) |
| Newer schema on disk (a rollback of the mod without the saves) | `refused reason=newer_schema`; install the matching mod version, or restore the matching `B` by hand with the server stopped |

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
by hand before retrying. A hard exit before a mission writer records its result,
or an older journal without written hashes, can require this manual review.
Never delete the journal to bypass a conflict. Identical dependency files are
recorded as unchanged and receive no backup.

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
-mod=@CF;@COT;@DabsFramework;@Expansion-Core;@Expansion-AI;@Expansion-Navigation;@SnafuWeapons;@TacticalFlava;@RaG_Core;@RaG_Immersive_Vehicles;@AmbientAnimals;@HollowCountry;@HollowCountryExpansionAI
```
