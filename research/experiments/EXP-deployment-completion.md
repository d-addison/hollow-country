# EXP: Portable deployment transaction completion

Date: 2026-11-16. Scope: private development source/package installation only.
Requirements: FR-012, NFR-001/004/005/006, AC-011/012, T023/T025. This evidence
does not close either task's native integration, save migration, multiplayer,
performance, signed-load or destination-server acceptance requirements.

Read inputs: AGENTS.md, docs/SPECIFICATION.md, canonical feature spec,
docs/MODULE_STATUS.md, runtime implementation contract and existing package/PBO
and economy tooling. No engine API was introduced. Shared files, canonical
spec/plan/task artifacts and existing verifier were left to the coordinator.

## Scoped execution plan and results

| Step | Acceptance and execution | Result |
| --- | --- | --- |
| 1. Specify ownership | One managed package slot plus metadata; external profiles and missions untouched; require stopped writers | Implemented and documented |
| 2. Verify source | Call existing `pbo.verify_handoff`; strictly check duplicate JSON keys, private-development contract, source PBO allowlist and regular ZIP members | Implemented; negative behavioral tests |
| 3. Transactional install | Publish immutable journal, flush stage, hash complete tree, park old tree, activate new tree, atomically commit state, record receipt | Implemented; real temporary filesystem tests |
| 4. Package migration | Explicit upgrade/migrate, retain exact previous package bytes, preserve external save sentinels | Implemented; no world-save conversion |
| 5. Rollback | Target current forward transaction ID, restore exact tree bytes, repeated same target is a no-op | Implemented; multi-generation roundtrip |
| 6. Recovery | Explicit abort/resume, persist decision, finalize committed state, refuse partial resume and drift, retain unpublished data | Implemented; checkpoint and real process-exit tests |
| 7. Validate and hand off | Record actual RED/GREEN, executable BDD, standard-library runbook with pending native gates | Completed within assigned new files |

Implementation: `tools/package/deploy.py` (standard library, Python >=3.10).
Behavioral suite: `tests/unit/test_deploy.py`. Runbook:
`docs/INSTALL_ROLLBACK.md`. Synthetic fixtures:
`tests/fixtures/deploy/`. No real destination was installed or modified and no
commit was made by this scoped worker.

## Observed TDD evidence

Commands ran from `/code/dayzsa_mods` with `PYTHONDONTWRITEBYTECODE=1`.
Output files preserve actual command results rather than hypothetical failures:

| Evidence file under tests/fixtures/deploy | Actual observation |
| --- | --- |
| `tdd-red.txt` | Initial import failed because deploy.py did not exist |
| `tdd-integration.txt` | First implementation: 18 tests passed |
| `tdd-red-journal-drift.txt` | 23 tests, 2 failures: altered historical journal was accepted; fabricated receipt was detected only after recovery moved package data |
| `tdd-red-paths.txt` | 26 tests, 6 reported failures/subfailures: four path cases including a custom Steam library, nonregular ZIP handling and resulting destination mutation check |
| `tdd-red-bdd.txt` | Executable scenario binding failed on the not-yet-created feature fixture |
| `tdd-green.txt` | Initial source freeze: 27 tests passed in 6.709 seconds, including four executed deployment BDD scenarios |
| `tdd-red-zip-bounds.txt` | CR-01 regression: 30 tests, 4 failures/subfailures proving decompression before manifest admission, unbounded stream read, and missing entry-count/aggregate preflight |
| `tdd-red-zip-methods-windows-lock.txt` | 32 tests, 2 failures and 1 error: BZIP2/LZMA members opened before rejection; simulated Windows byte lock blocked metadata validation |
| `tdd-green-zip-bounds.txt` | Reviewed source freeze: 32 tests passed in 6.357 seconds, including four executed deployment BDD scenarios |

The journal fix verifies receipt hashes and installed history before mutation.
The path fix recognizes custom Steam libraries by their `steamapps` child,
applies Windows-safe component rules on POSIX, and refuses special/reparse ZIP
entries. The BDD driver binds and executes every Given/When/Then line in
`deployment.feature`; unknown steps fail. Gherkin text alone is not counted as
execution.

Final reproduction command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_deploy.py -v
```

The existing package regression suite was also run against the coordinator's
current `pbo.py`: `env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover
-s tests/unit -p test_package.py -v`; all 16 tests passed. The verifier source
was not edited by this worker.

## Independent review CR-01 correction

The independent review identified `ZipFile.read('manifest.json')` occurring
before the 2 MiB metadata size check. Its 8,282-byte compressed archive expanded
to an 8 MiB manifest, and the reviewer measured roughly 22 MiB peak allocation
before rejection. This was a concrete defect; eventual `ValueError` was not
adequate admission control.

The exact in-memory review reproduction was rerun after the fix: 8,282-byte
compressed ZIP, 8,388,608-byte declared manifest, rejection before opening it,
and 59,166 bytes peak traced allocation on this Linux run. The descriptive
measurement and frozen source hashes are recorded in
`tests/fixtures/deploy/zip-bounds-review-reproduction.json`; the regression uses
observed member reads rather than a platform-dependent heap threshold.

The new regression generates that synthetic space-only manifest and observes
`ZipFile.open`: no member may be opened and the existing verifier must not run.
Separate reduced-budget fixtures prove count and aggregate preflight happens
before reading any member. A valid-package regression records every stream read
before the existing verifier, fails any unbounded or over-64-KiB request, and
requires all members to have been read before legacy verification.

The fix checks all ZipInfo declarations first: at most 8,192 entries, 64 MiB
aggregate uncompressed content, 2 MiB manifest and 64 MiB per other member.
Every admitted member is then streamed through bounded 64 KiB reads with
declared-length checks and a one-byte overrun probe. The extracted bounded data
is reused rather than re-read after verification. The existing verifier still
checks container payload hashes and the PBO source manifest and was not edited.
Only stored/deflated methods are admitted: the installed standard library's
ZipExtFile path caps zlib decompression, whereas its BZIP2/LZMA paths can allocate
output before applying a read cap. Both rejected methods have regression tests.
These are content bounds, not a claim that Python heap use equals the limits.

Windows CI compatibility was reviewed in the same scope. Reserved device names,
ADS and trailing-dot names are tested through the lexical guard without asking
Windows to create them. Metadata validates the lock file's type/link/size without
reading its byte: Windows byte-range locks can deny a read through a second
handle, even in the lock-owning process. A synthetic PermissionError regression
demonstrated the previous read and now passes. Actual native Windows CI remains
the execution check; these local results were obtained on Linux.

After the fix, the existing package suite was rerun: all 16 tests passed in
0.015 seconds. Only assigned deployment source/tests/fixtures/runbook/report
were changed; coverage's UTF-16 correction belongs to the coordinator. No live
destination deployment or commit was performed.

Tests exercise fresh install, upgrade/migrate, exact retained backups, targeted
and repeated rollback, preserved external profile/unrelated-file sentinels,
read-only planning, stale transaction refusal, corrupt ZIP/source/private
distribution refusal, source/Steam/path/link guards, active/backup/journal/
receipt drift, process-held lock exclusion, metadata quarantine and staged
write failure.

Recovery coverage includes journal-only, partial staging, complete staging,
parked original, published replacement, committed state and written receipt.
Recovery is itself interrupted at deactivation, restoration and receipt writing;
its persisted decision is retried. Four subprocesses actually call `os._exit`
at partial staging, backup rename, activation and state commit. Parent-process
recovery then proves OS lock release and the expected commit boundary on this
Linux filesystem. `BaseException` checkpoints provide additional boundary
coverage. Injected disk failure is explicitly synthetic; no actual disk-full
experiment or physical power cut was performed.

## Safety and limits

There is no force-overwrite, public publishing, external command execution,
automatic feature enablement, server launch, profile reset or private-key
installation. No assets, purchased script dumps, keys or real profiles are in
the fixtures. Runtime profile preservation is opaque byte preservation, not
semantic DayZ-save migration. `migrate` deliberately means package migration.

Windows reparse rejection uses the native stat attribute bit; the suite checks
it with synthetic stat data. Actual NTFS junction handling, Windows locking and
rename behavior still need native Windows validation. POSIX directory flush is
implemented; Python does not offer equivalent portable Windows directory flush.
Power-failure durability is not established. A trusted quiescent local
destination is required; advisory locks do not stop unrelated writers or close
all hostile cross-platform namespace races.

Backups guarantee file names, bytes and directory shape. Restoring Unix ACLs,
ownership or exact timestamps is not part of the byte-exact package contract.
History is retained up to 128 transactions and refuses further growth; no
automatic deletion or history compactor was introduced. Corrupt authoritative
metadata or an incomplete unrecognized bootstrap is preserved and refused.
No source/package installation result is treated as DayZ runtime evidence.

The coordinator separately reported official signing/checking utilities
successfully checking the previous `796175f` PBO under Wine. This worker did
not reproduce or extend that experiment. That report does not sign this
development ZIP, prove the current source revision, establish native Windows
loading or accept world-save migration. T025 remains open for the actual
signed destination handoff, save backup/restore and join/restart observations.

## Native smoke dependency/config addendum

The coordinator reported Wine probe 006 compiled World and probe 007 failed
BattlEye initialization despite `BattlEye=0`. Its Wine harness correction adds
an explicit fresh BE path/DLL plus required stock `instanceId`,
`guaranteedUpdates`, and `shardId`. This addendum addresses the corresponding
gap in `tools/package/Invoke-NativeSmoke.ps1`; it does not claim to reproduce
those Wine observations or establish Windows DayZ execution.

This scoped correction changes only the smoke PowerShell helper, its tests in
`tests/unit/test_package.py`, and this addendum. The existing package writer and
other helpers remain under coordinator ownership. No commit or native server
launch was made by this worker.

The smoke config now includes `instanceId=1`, `guaranteedUpdates=1`, and the
six-character local shard `hcdev1`, matching the local harness's values and
the installed stock fields. It creates a fresh runtime `battleye` directory,
copies only `battleye/BEServer_x64.dll` from the supplied server installation,
and passes the isolated directory with `-BEpath`. The installed BE directory
is never used as the writable BE path. `BattlEye=0` remains an explicit smoke
setting, not an assumption that initialization cannot load its DLL.

The copy follows `New-LocalVanillaRuntime.ps1`'s read-only .NET SHA-256 and
`[IO.File]::Copy(..., $false)` pattern: reject reparse ancestors, snapshot source
length/hash before runtime creation, recheck source before copying, refuse
overwrite, verify the staged length/hash, then recheck source. The smoke report
records source path, isolated path, DLL bytes, and source/staged SHA-256. These
are bindings to the local input snapshot, not independent Steam authenticity
or the setup script's fixed build-baseline acceptance. Dependency checks remain
after the ShouldProcess return, preserving the existing synthetic WhatIf checks
without requiring a real DLL, Python, or server launch in a dry run.

Actual TDD command, run before and after implementation:

```bash
env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_package.py -v
```

RED: 19 discovered tests, 2 failures and 1 native-only skip. The emitted config
had no `instanceId` assignment, and the helper had no verified isolated BE
dependency. GREEN: 19 discovered tests, 18 passed and 1 native-only skip
(`OK (skipped=1)`, local Linux run). The two new portable tests check the actual
emitted config and dependency capture/copy/launch ordering. They are source
contracts, not executed PowerShell or DayZ behavior.

The third test runs only on native Windows. It parses the actual smoke script
with the native PowerShell AST parser, imports just its four copy/hash/check
functions, and executes them against temporary original synthetic text. It
checks exact copy/source preservation, existing-destination refusal, same-size
source hash drift before any copy, and same-size staged hash drift. It invokes
no server. Native execution is pending; the coordinator must include
`python -B -m unittest discover -s tests/unit -p test_package.py -v` in the
Windows CI job to run it. The current deployment/coverage Python steps alone
do not execute this package test. Native syntax/helper acceptance and real DayZ
initialization remain separate gates.

## Final portable-delivery checklist (independent, read-only inspection)

Final artifact generation and installation checks belong to the coordinator.
This review wrote no source or delivery files. An ephemeral in-memory build
observed 20 manifested payload files, identical standalone/ZIP PBO bytes, and
the exact hashed `docs/INSTALL_ROLLBACK.md`. Generated metadata was private-only,
unsigned-development, runtime pending, release false, signature null. Counts and
hashes must be observed again after the final source freeze.

1. Freeze the addon, helpers and guides; record the actual source revision and
   final hashes. Do not reuse the earlier `796175f` PBO/signature/build-info or
   native log as proof for changed final bytes. The portable guide is now both
   emitted and allowed by `pbo.verify_handoff`; the old Downloads archive lacks
   that new guide/helper set and must remain distinguishable.
2. Use a fresh proposed Windows output directory
   `C:\Users\David\Downloads\HollowCountry-Development-20261116-final-v2`
   (WSL equivalent below). From `/code/dayzsa_mods`, the coordinator's exact
   build/structural verification commands are:

   ```bash
   hc_delivery=/mnt/c/Users/David/Downloads/HollowCountry-Development-20261116-final-v2
   mkdir "$hc_delivery"
   python3 -B -m tools.package.pbo pbo --addon mods/HollowCountry --out "$hc_delivery/hollowcountry.pbo"
   python3 -B -m tools.package.pbo verify "$hc_delivery/hollowcountry.pbo"
   python3 -B -m tools.package.pbo handoff --addon mods/HollowCountry --mission mission/hollow-country --out "$hc_delivery/hollow-country-private-dev.zip"
   python3 -B -m tools.package.pbo verify "$hc_delivery/hollow-country-private-dev.zip"
   ```

   Output files are exclusive-create: choose another fresh directory if it
   already exists. `handoff` rebuilds its own PBO from the addon, not from the
   separately built PBO argument. Assert their exact bytes match after freeze.
   Do not pass `--release`; it deliberately refuses the gated release.
3. Inspect ZIP metadata in addition to the CLI success: `distribution` must be
   `private-only`, `status` `unsigned-development`, `runtime_acceptance`
   `pending`, `release_allowed` false, and `signature` null. Assert both guides
   (`docs/INSTALL_ROLLBACK.md` and the mission guide), operator settings and
   `deploy.py`/`coverage.py` are present and hashed. All feature defaults stay
   off. The CLI prints status/file count, not all these fields.

   **Observed verifier limitation:** changing only `distribution` to `public`
   or `runtime_acceptance` to `accepted` in an in-memory manifest was accepted
   by `pbo.verify_handoff`; `deploy._bundle` rejected both. The writer currently
   emits the correct values. Structural verification alone does not enforce
   those two metadata fields; the coordinator owns any verifier tightening.
4. Extract the verified ZIP into a fresh `final-v2\handoff` directory. For the
   final-v2 directory above, PowerShell setup and the read-only install plan are:

   ```powershell
   $hcDelivery = Join-Path $env:USERPROFILE 'Downloads\HollowCountry-Development-20261116-final-v2'
   $hcPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
   $hcZip = Join-Path $hcDelivery 'hollow-country-private-dev.zip'
   $hcBundle = Join-Path $hcDelivery 'handoff'
   Expand-Archive -LiteralPath $hcZip -DestinationPath $hcBundle
   $hcDestination = Join-Path $hcDelivery 'install-check'
   New-Item -ItemType Directory -Path $hcDestination
   & $hcPython (Join-Path $hcBundle 'tools\package\deploy.py') plan --zip $hcZip --destination $hcDestination
   ```

   Destination must already exist and be outside Steam/source. Only after
   confirming all writers are stopped, the coordinator may exercise `install
   --zip $hcZip --destination $hcDestination --server-stopped`, capture its
   transaction ID, then `rollback --destination $hcDestination --transaction
   <that-id> --server-stopped` through the same helper. This is a disposable
   package check, not a live-server deployment. The active mod path is
   `$hcDestination\HollowCountryPackage\@HollowCountry`; profiles/storage stay
   external. A bare `@HollowCountry` directly under install-check is incorrect.
5. Sign the **final exact PBO** separately. On native Windows, with existing
   external matching key paths already assigned to `$hcPrivate`/`$hcPublic`,
   the exact supported orchestration is:

   ```powershell
   & $hcPython (Join-Path $hcBundle 'tools\package\sign.py') --pbo (Join-Path $hcDelivery 'hollowcountry.pbo') --tools 'D:\SteamLibrary\steamapps\common\DayZ Tools' --private-key $hcPrivate --public-key $hcPublic --out (Join-Path $hcDelivery 'signed-development\@HollowCountry')
   ```

   The output must be fresh. Check the exit code and preserve signing-report,
   tool hashes and positive checker log. The official low-level commands are
   `DSSignFile.exe <private-key> <pbo>` and `DSCheckSignatures.exe <addons-dir>
   <public-keys-dir>`. Linux `sign.py` has no Wine option; a Wine run requires
   the coordinator's separately explicit official-tool invocation, fresh local
   staging and an accurately recorded Wine execution environment.
6. **Signature integration constraint:** ZIP/handoff/deploy currently support
   unsigned-development only. Adding `.bisign`/`.bikey` inside that ZIP fails
   its allowlist; adding them to its managed active tree creates drift and
   blocks future upgrade/rollback. Retain the signed runtime addon separately
   from the managed development-package slot. Keep its `.bisign` beside the
   exact PBO, copy launcher `mod.cpp` from the verified handoff into that
   separate addon, and place only the public `.bikey` in the actual stopped
   server's `keys` when that later install is authorized. Inventory/hash the
   signed tree and metadata together; never transfer the private key. The
   unsigned ZIP manifest must not be relabelled signed without a separately
   implemented signed-package contract.
7. Record SHA-256/size for final PBO, ZIP, signature, public key and guides in
   fresh delivery metadata; bind signing and compiler reports to that PBO hash.
   Label signed-development separately from unsigned-development. Windows CI
   helper tests, Wine engine observations, native Windows engine loading,
   signature acceptance, two-client behavior and friend-server/save rollback
   remain distinct evidence. No installation or final signing was executed by
   this read-only review.
