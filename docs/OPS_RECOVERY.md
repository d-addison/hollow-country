# HC-28 recovery operations

Source/package implementation for HC-28, supporting #143/#144. Runtime acceptance
and production enablement remain **pending**. Synthetic tests do not establish
DayZ persistence, native inventory consistency, replication or disk durability.
The active Round 2 brief supersedes the original mandatory-receipt design.

## Boot and shutdown contract

Normal boots require **no recovery receipt**. With no files, the world creates a
fresh ledger, escalation creates a fresh epoch, and groups start with no members.
An empty group state directory is valid; its first committed triple is revision
1. A restore receipt's group revision may be zero (no committed group journal).
An existing incomplete journal never falls back to an empty group state.

World, escalation and groups call `HCPersistenceDisposition.HCLoad` before their
store admission. The first call initializes recovery; later module calls reuse
that session result. The modules register their lifecycle attempts separately
from their write gates. This ensures that closing one gate cannot remove the
session marker before the other modules finish their shutdown flushes.

Each store validates its own files. World and escalation reject a retained
`.tmp`, a missing primary with a `.bak`, invalid JSON/schema, corrupt backup or
regression against the backup's watermark. Groups retain the existing bounded
immutable intent/image/commit protocol: the highest revision must be complete,
parse correctly and agree with its receipts. No automatic rollback, refund,
completion-history reset or replay is performed.

Observed damage quarantines **that store only**. Quarantine closes its write
gate and retains the original files at their original paths. It never deletes,
renames or replaces player data. IO/config/clock failures also close only the
owning store's gate, without pretending those failures prove file damage.
Healthy stores continue and flush at Stop. World ticks stop at a closed world
gate; escalation ticks consult only the escalation gate. `EnableWorld=false`
requires neither world nor escalation files and does not prevent group startup.

`recovery-active.intent` records a running HC session. An intent left after a
crash produces `warning=unclosed_native_session` followed by ordinary independent
file validation. Its presence alone never quarantines a store. The final store
module Stop removes the marker after module flushes and closes the remaining
session gates. An unsuccessful marker cleanup logs a warning. This marker is
not proof that native inventory finished saving.

## One-time restore attestation

Stop the server and preserve the damaged installation before operator recovery.
Restore HC state and the matching native persistence from the same stopped
backup, including completed history, group ACLs, stashes and inventory. Never mix
an old HC journal with newer native inventory: spent resources and completed
transactions cannot be inferred or repaired safely from those files alone.

Place these two optional files together under `$profile:HollowCountry` only when
performing an explicit paired restore:

- `recovery-hc.json`: Version=1, Generation (1..1000000000), WorldName,
  PairedRestore=true, NativeBackupId (1..128 characters), WorldLength/WorldHash,
  EscalationLength/EscalationHash, GroupRevision (0..1000000000),
  GroupLength/GroupHash.
- `recovery-native.json`: Version=1, matching Generation/WorldName/NativeBackupId,
  StoppedPairAttested=true.

The IDs are operator attestations, **not an engine generation oracle**. HC checks
bounded byte length and native `string.Hash()` for the explicitly restored
images. A zero length/hash denotes an absent world/escalation image; group
revision zero requires zero group length/hash. With World disabled, its two
image checks are skipped. Hash is an accidental mismatch check, not a
cryptographic signature. Do not calculate production receipts with the Python
synthetic hash used in tests.

On successful restore admission both receipts move to their original filenames
plus `.consumed-<utc>`. Both complete archives are verified before either active
name is removed. The consumed files are retained indefinitely; they never pin
subsequent normal saves/restarts. A missing half, malformed/mismatched receipt,
archive collision or failed consume refuses that restore attempt, retains
evidence and logs `recovery=attestation_refused`, without classifying another
store as damaged. Correct the operator attestation before retrying.

The installed engine exposes **no rename primitive**. The supported logical
rename uses `CopyFile`, bounded readback, then `DeleteFile` of the active name
only after both archived images verify. It is not atomic or fsync. A crash
between source removals can leave one active receipt plus both consumed images;
startup then refuses the incomplete attestation. Preserve all copies and have
the operator complete/reissue the restore pair while stopped. Neither receipt
content nor its final archival copy is discarded. No invented `RenameFile` API
or native inventory write is used.

File/JSON/schema validation still belongs to the individual stores after byte
attestation. An attestation accepted for matching bytes does not assert gameplay
admission or runtime acceptance of those bytes.

## Supported native primitives and framework reuse

Inspected read-only snapshot: `~/.cache/hollow-country/native-scripts/scripts-1.30.164289`.

- `1_Core/proto/EnSystem.c:397,417,425,443,462`: FileExist, OpenFile,
  ReadFile, CloseFile, FPrint; `:525,528,531`: MakeDirectory, DeleteFile, CopyFile.
  `:520..522`: FindFile, FindNextFile, CloseFindFile (existing group enumeration).
- `1_Core/proto/EnString.c:199,223,240`: Length, Hash, IndexOf;
  `1_Core/proto/EnConvert.c:30`: integer ToString;
  `1_Core/proto/EnDebug.c:96`: Print.
- `3_Game/Global/Game.c:1120,934`: IsServer, GetWorldName;
  `3_Game/tools/JsonFileLoader.c:69,85`: LoadData, MakeData.
- UTC reuses `HCGroupClock.Utc`; store saves retain `HCSaveJob`/
  `HCSaveScheduler`, bounded `HCGroupIO`, verified temp/backup/readback and
  immutable group revision receipts. No new scheduler or gameplay controller.

Recovery hooks are implemented in the existing world/escalation lifecycle and
in a modded group lifecycle link, preserving its RPC attach/detach owner. Group
store Fault and internal service Stop close only the group gate. No HCModule,
registry or config.cpp edits are needed from the lead. `.gitignore` explicitly
includes this runbook. No new distances or calibrated performance claims.

## TDD receipts and trace

Trace: HC-28/#143/#144 -> `.banso-writer/inputs/task.md` (original package) ->
`.banso-writer/inputs/task-r2.md` (binding review corrections) -> store/lifecycle
sources -> `tests/unit/test_hc_recovery.py` and `test_v2_world.py`.
`docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md` are absent
from this confined worktree. The available brief and runtime implementation
contract supplied the design input; no missing engine experiment is accepted.

Actual Round 2 behavioral RED, before implementation:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_recovery -v
AssertionError: False is not true : normal boot must not require restore receipts
AssertionError: False is not true : one damaged store cannot refuse all admission
AssertionError: False is not true : unclosed intent is a warning, not damage
AssertionError: False is not true : first boot must not require restore receipts
AssertionError: False is not true                           [group revision 0]
AssertionError: ... : restore attestation must be consumed  [group revision 9]
Ran 5 tests; FAILED (failures=6)
```

Additional actual RED before pair validation:

```text
AssertionError: True is not false : damaged pair or revision regression must refuse world
AssertionError: True is not false : corrupt clock pair or watermark regression must refuse
```

Both corrupt-backup and older-primary subcases failed for each store. Synthetic
ports explicitly provide files, DTO decoding, checksum, UTC and scheduler/native
IO boundaries; authored recovery, store and lifecycle decisions execute.

A further RED check found that a legitimate persisted admin-day epoch change
was mistaken for damage: `AssertionError: False is not true : persisted admin
epoch change must remain valid`. Backup comparison now permits that adjustment
while rejecting a regressing saved UTC watermark.

Final GREEN (all use explicit synthetic fixtures; no native acceptance):

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_recovery test_v2_world -v
Ran 13 tests; OK

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_recovery test_v2_world test_script_syntax test_enforce_locals test_script_identifiers test_hygiene -v
Ran 66 tests; OK

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_admin_test_kit test_event_integration test_group_native_checks test_group_persistence test_group_round2 test_group_server test_hc_ai_signals test_hc_recovery test_hc_unit_budget test_hygiene test_v1_combined_flags test_v2_escalation test_v2_holdouts test_v2_materializer test_v2_pins test_v2_world -v
Ran 389 tests; OK (expected failures=1)

python3 -B -m tools.validate.enforce_lint --no-native
enforce_lint: pass findings=133 new=0 stale=0 native=no
```

The affected module list comes from `rg -l -F` over the changed store/class
names, test filenames, runbook name and `.gitignore` in `tests/unit`. The sole
expected failure is the existing combined-module work-budget check; it is not
reclassified as accepted. No full test discovery was run.

## Native checks still to run

Compile and boot the exact authored source with DayZDiag, then package and test
a normal signed PBO/server. Record exact source/PBO/mission/config/dependency
hashes and check that there are no script or CE errors. Proposed log substrings
to observe, not claimed boot results:

```text
[HC Plan] HC-28 generation=... recovery=validate_each_store ... runtime=PENDING
[HC Plan] HC-28 store=world recovery=quarantined ... files=preserved runtime=PENDING
[HC Plan] HC-28 warning=unclosed_native_session action=validate_each_store runtime=PENDING
[HC Plan] HC-28 recovery=attestation_refused ... quarantine=0 runtime=PENDING
```

On a private disposable installation:

1. Boot without files; save, stop cleanly and boot again repeatedly. Verify the
   marker is absent after Stop and changing images need no receipts.
2. Restore a genuine stopped HC/native pair. Verify receipts survive under
   `.consumed-<utc>`, then save/restart again without active attestations.
3. Crash during debit and each save stage. Test retained intent alone with
   healthy files, corrupt JSON/backups, missing primary plus backup, partial
   highest group triple and revision/watermark regressions. Check isolation:
   corrupt world with healthy groups/escalation, then each other store fault.
4. Close a store gate mid-session. Stop and confirm that healthy stores retain
   their unsaved progress while quarantined bytes remain unchanged. Test World
   off with groups on and no escalation files, and an empty group directory.
5. Interrupt attestation archival/removal, and test archive name collisions.
   Preserve evidence and verify explicit restore refusal without data mutation.
6. With two clients, verify retained inventories/ACLs/stashes and no duplicate
   loot, refund/replay, replenished cargo or lost/restarted completion history.

Native inventory consistency and benchmark budgets for the intended 3–6 players
remain provisional until measured. Source authoring does not require client join.
