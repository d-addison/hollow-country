# Independent completion review — 2026-11-16

Reviewed the current working-tree completion diff against HEAD
`f18650d459766f6520e4700e124bb906fdbac68c`. Read-only review; this report is the
only file authored by the reviewer. No code/test changes or commits. Other workers
were modifying the shared tree during review, so relevant content hashes appear
below. Read the product specification, canonical feature spec and runtime module
contract before reviewing.

## Findings

### CR-01 — P2: Decompression occurs before the manifest size guard

**Location:** `tools/package/deploy.py:219–221`, `_bundle`.

`ZipFile.read('manifest.json')` decompresses and allocates the entire manifest
before `MAX_METADATA` is checked. The compressed archive limit does not bound its
uncompressed size. The authoritative verifier's aggregate uncompressed-size guard
(`tools/package/pbo.py:232`) runs later, after this allocation. Both `plan` and
installation therefore process an oversized manifest before rejecting the archive;
a sufficiently compressible input can exhaust memory during a nominally bounded
validation step. No destination writes are needed to trigger it.

**Actual read-only reproduction:** an 8,282-byte in-memory ZIP containing an
8,388,608-byte space-only manifest was read in full before rejection with
`handoff manifest exceeds metadata budget`. `tracemalloc` measured 22,488,904 bytes
of peak allocation during `_bundle`, exceeding the 2 MiB metadata budget.

```python
import io, zipfile
from pathlib import Path
from unittest.mock import patch
from tools.package import deploy

buffer = io.BytesIO()
with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    archive.writestr('manifest.json', b' ' * (8 * 1024 * 1024))
blob = buffer.getvalue()
original_read = zipfile.ZipFile.read
def observe_read(archive, name, *args, **kwargs):
    value = original_read(archive, name, *args, **kwargs)
    print(name, len(value))
    return value
with patch.object(deploy, '_read', return_value=blob):
    with patch.object(zipfile.ZipFile, 'read', observe_read):
        deploy._bundle(Path('in-memory.zip'))
# Prints manifest.json 8388608, then raises ValueError.
```

**Correction:** check entry count, declared total uncompressed bytes and the
manifest's `ZipInfo.file_size` before reading members. Read the manifest through
`ZipFile.open` with a `MAX_METADATA + 1` cap as a second bound. Add a regression
that observes whether an oversized manifest was read, rather than only asserting
that the eventual call raises.

### CR-02 — P2: UTF-16 bypasses the coverage XML declaration guard

**Location:** `tools/package/coverage.py:109`, through its imported
`tools/package/economy.py:44–48` XML loader.

The loader searches raw bytes for ASCII `<!DOCTYPE` and `<!ENTITY`, then passes
those bytes to `ElementTree`, which also accepts UTF-16. A UTF-16 document inserts
NUL bytes between those ASCII characters and bypasses both searches. Its internal
entity is expanded and the otherwise valid coverage candidate is accepted. This
contradicts the explicit declaration rejection policy and the coverage report's
claim that XML declarations are rejected. Hash binding does not prevent the
problem: correctly pinned bytes reproduce it.

**Actual read-only reproduction:** the following returned a candidate with one
added point at `1 0 0`, rather than rejecting the DTD/entity declaration:

```python
import hashlib
from tools.package import coverage

stock = (b'<prototype><group name="A" lootmax="0">'
         b'<container name="loot" lootmax="0"/></group></prototype>')
exported = (
    '<?xml version="1.0" encoding="UTF-16"?>'
    '<!DOCTYPE prototype [<!ENTITY p "1 0 0">]>'
    '<prototype><group name="A" lootmax="1">'
    '<container name="loot" lootmax="1"><point pos="&p;"/>'
    '</container></group></prototype>'
).encode('utf-16')
sha = lambda data: hashlib.sha256(data).hexdigest()
evidence = {
    'schema': 1, 'world': 'chernarusplus', 'build': '1.30.164289',
    'source_sha256': sha(stock), 'export_sha256': sha(exported),
    'groups': ['A'],
    'observations': [{'path': 'diag.log', 'sha256': sha(b'synthetic')}],
}
candidate, report = coverage.prepare(
    stock, exported, evidence, {'diag.log': b'synthetic'})
print(report['added_raw_points'], candidate)
```

**Correction:** enforce a documented UTF-8-only encoding before scanning/parsing,
or reject DTD/entity declarations at the parser level for every accepted encoding.
Test both UTF-16 byte orders. This reproduction demonstrates internal entity
expansion and a policy bypass; it does **not** demonstrate external-file disclosure
or claim that Python's XML entity amplification protections are absent.

## Other substantive checks

- Interior reserve/grant/finish ordering keeps the central allocation reserved
  before file/inventory work. Existing claim, attempt, result or hold markers
  block retry. Legacy schema-1 completions stay spent; schema-2 completions require
  the exact attempt/actor/schema match. Missing or ambiguous records quarantine
  rather than authorizing a replay. No additional duplicate-grant/refill defect
  was established in the reviewed source.
- `ReconcilePhase` prevents terminal states returning to available. Startup
  reconciles every allocation, including unavailable buildings; orphan journal
  paths stop the pool. The v2 sidecar compares the complete manifest without
  replacing old claim/result files. Holds remain blocking even when unreadable.
- Deployment intent, receipt and state comparisons cover the inspected commit,
  abort, restored-backup and interrupted temporary-metadata paths. Sticky recovery
  decisions prevent an opposite retry argument from reversing a recorded abort.
  No additional journal recovery corruption or unsafe overwrite was established.
  These were source checks; no filesystem-mutating deployment tests were run by
  this read-only reviewer.
- Infected recovery compares all four ID parts and class, requires the native
  storage-load marker, rejects duplicate/cross-group IDs, retains reservation
  counts and keeps recovered groups unresolved. It does not infer a replacement
  entity from position/class or reactivate a pack based on JSON alone. Roster
  comparison preserves the conflict latch between generations.
- Alert roots retain their original expiry, stop at two hops, dedupe emitters and
  recipients, cap root/queue/recipient counts, and use bounded recipient work.
  Propagation requires a native voice callback and does not synthesize another
  `AddNoise` call. No concrete unlimited propagation path was established.

## Installed native signature checks

Inspected the private installed script snapshot at
`/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289`;
no purchased script contents were copied into the repository.

| New/relevant override or call | Installed declaration | Result |
| --- | --- | --- |
| `ZombieBase.AfterStoreLoad()` | `3_Game/Entities/EntityAI.c:1419`, inherited `void AfterStoreLoad()` | Matching override; native comment identifies storage/DB load after children. |
| `ZombieBase.EOnInit(IEntity, int)` | `4_World/Entities/Creatures/Infected/ZombieBase.c:92` | Matching override. |
| `ProcessSoundVoiceEvent(AnimSoundVoiceEvent, out AbstractWave)` | Same native file, line 583 | Matching protected override; native server branch supplies the noise event. |
| `FightLogic(int, DayZInfectedInputController, float)` | Same native file, line 613 | Matching boolean signature. |
| `EntityAI.GetPersistentID(out int, out int, out int, out int)` | `3_Game/Entities/EntityAI.c:3374` | Declaration exists; recovery avoids the event-restricted lookup API. |
| `World.GetAIWorld()` | `3_Game/Global/World.c:116` | Correct world accessor used in navigation. |

An initial read found `GetGame().GetGetAIWorld()` in the horde-load call. A later
read showed `GetGame().GetWorldName()` at `HCInfectedModule.c:109`, corrected by
another worker during this review. This resolved observation is **not** counted
as an outstanding finding. The reviewer changed no source.

## Reviewed content pins

| File | SHA-256 |
| --- | --- |
| `tools/package/coverage.py` | `b17755615ed96cd2663b6118a831d779f5e1ffb3bf1cee6755e663ef359e54dc` |
| `tools/package/deploy.py` | `4cd038796395c6cd48831736d5b5ef59b3f3a0dbbda65e0bc6a0f6348509c14e` |
| `tools/package/economy.py` | `feb92ad7135aa085dedc01875f250ca334004faac4ac2274f80947c4c803ea86` |
| `HCInteriorSearchPool.c` | `3e325aa946208a8545c30879d5c643ad3728c819610ba01dd81323ba0a324322` |
| `HCInteriorStore.c` | `4fa56d4506de9e707805937ac6b38e0ebb5051caa63000ba289ca5647ba51de8` |
| `HCAlertChain.c` | `b60c35fcc45f46737e10d82bdec450421548cc9216a583741a955e79dcba91af` |
| `HCHordeRecovery.c` | `7ca22b3896779be8411fb8477b9826f364ed5a6fb94203fb1eb6d2ad5bca8e49` |

The two reproductions ran with `PYTHONDONTWRITEBYTECODE=1` and in-memory data only.
This review does not substitute for the coordinator's compiler iterations.

## Follow-up: fixes independently verified and Wine harness review

The coordinator reports actual engine compiler passes under Wine. The checks
below concern tool correctness and do not dispute that observed compiler result.
Read-only follow-up; again, only this report was edited by the reviewer.

### CR-01 resolved at the reviewed snapshot

`deploy._bundle` now checks member count, names, individual uncompressed sizes
and aggregate uncompressed size before opening any member. `_zip_member` reads
in chunks of at most 64 KiB, checks actual length and performs a one-byte overrun
probe before passing the archive to the existing verifier.

Actual independent checks, all in memory with `PYTHONDONTWRITEBYTECODE=1`:

- Original 8 MiB compressed-manifest reproduction: rejected with
  `ZIP member exceeds uncompressed byte budget`; **zero member opens**.
- Three-member fixture with synthetic `MAX_ENTRIES=2`: rejected before opening
  any member.
- Fixture with synthetic aggregate `MAX_BYTES=64`: rejected before opening any
  member.
- `_zip_member` with declared size 3 and an actual four-byte synthetic stream:
  rejected with `ZIP stream exceeds declared size or byte budget`.
- A matching three-byte stream returned `b'abc'`.

Inspected the new deployment regressions for these conditions. The reviewer did
not execute the deployment test class, whose setup creates temporary directories;
the independent probes above preserve the requested read-only scope.

### CR-02 resolved at the reviewed snapshot

`economy.xml` now decodes `utf-8-sig`, rejects decode errors, NUL characters and
DTD/entity declaration text before passing Unicode text to ElementTree.
Independently reran the original valid/hash-pinned candidate reproduction for
`utf-16`, `utf-16-le`, `utf-16-be` and `utf-32`: all four now raise `ValueError`.

Actual test command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_coverage_patch.py -v
```

Result: **9 tests passed**, including the encoding regression. Ordinary UTF-8
candidate preparation still passes the same suite.

### CR-03 — P2: Wine cleanup is tied to launcher lifetime, not group lifetime

**Location:** `tools/setup/wine_compile_probe.py:105–113`.

The harness starts a fresh process group, but skips all cleanup when the launcher
has already exited. A group can still contain live descendants after its leader
exits. The timeout fallback has the same problem: after sending TERM, it waits
only for the launcher; if the launcher exits while another group member survives,
the KILL fallback is never reached. Thus the deadline does not establish that the
owned server/display descendants stopped, and `forced_stop` can remain false
despite surviving processes. This is a process-lifecycle defect, independent of
whether a particular DayZ compiler run passed.

**Actual source-body reproduction:** parsed the `run` function with `ast`,
executed its actual `finally` body with a synthetic exited launcher
(`poll() == 0`, `returncode == 0`) and an otherwise empty in-memory filesystem
double. An observed `os.killpg` mock received **zero calls**; the report recorded
only the launcher exit. No actual server or file was created by this check.
To reproduce the underlying OS condition, a session-leading launcher can fork a
sleeping child and exit immediately: waiting/reaping that leader does not stop
its child's process group.

**Correction:** retain and clean up the owned group independently of launcher
`poll()`, tolerate ESRCH, wait for bounded group/owned-descendant termination,
and escalate surviving owned processes after the grace period even if the leader
exited. Test both an already exited leader and a leader that exits on TERM while
a child survives. Avoid broad prefix-wide kills, which could affect other runs.

### CR-04 — P2: Final log collection bypasses the probe's byte/time bounds

**Location:** `tools/setup/wine_compile_probe.py:94–95,115–116`.

The polling loop applies a 16 MiB per-file filter, but final report hashing calls
`read_bytes()` on every `.log`, `.rpt` and `.adm` file with no byte or file-count
limit. That work happens after the probe deadline and can allocate an entire
oversized log, including a log deliberately excluded by the polling loop. The
polling loop also has no aggregate byte/file-count budget, so many individually
admitted logs can consume unbounded aggregate work per pass.

**Actual source-body reproduction:** executed the same authored `finally` body
with an explicit synthetic `.log` whose declared size was 32 MiB, with its body
provided by a small in-memory double. `read_bytes` was called once with no size
check (`stat` called zero times). This proves the cap bypass without allocating
or writing a large file. It is not a claim that current engine logs reached that
size.

**Correction:** use a bounded file count and aggregate read budget for polling
and final collection. Stream hashes in fixed chunks within that budget; record
oversized/skipped logs explicitly rather than silently dropping them or reading
them wholesale. Apply the budget to `.adm` as well as `.log`/`.rpt`.

The existing synthetic classifier suite also passed independently:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_wine_compile_probe.py -v
```

Result: **5 tests passed**. Those tests check classification, and do not cover
the process cleanup or log bounds above.

### Follow-up content pins

| File | SHA-256 |
| --- | --- |
| `tools/package/deploy.py` | `34df41095883def5aa7ffca1dd694781fca2185b5693de17b5133b7ab022417a` |
| `tools/package/economy.py` | `c8d6fc8580917065b91fd55c9b6cb454286e687188e498bae658b94a769947fe` |
| `tools/package/coverage.py` | `b17755615ed96cd2663b6118a831d779f5e1ffb3bf1cee6755e663ef359e54dc` |
| `tests/unit/test_coverage_patch.py` | `b6cfadf2554e8bec6be7f0a457588b93e700dbb94987a31c229cd0418ef0c391` |
| `tests/unit/test_deploy.py` | `6a8de7271ad7cfac501b85f061cd3d39f8a019f04fedf281aa9695628a17b6b5` |
| `tools/setup/wine_compile_probe.py` | `d53ed511c3e4c071896fa48d5bd56a3ccf3d26ae3d9ede0b5acbde29b5eeab45` |
| `tests/unit/test_wine_compile_probe.py` | `5c1349c1944abfff49acf47478efe2cac4c55dd0a4af60ef613eb3848291c788` |

## Second follow-up: CR-03 and CR-04 resolved at reviewed snapshot

Independently inspected the new `stop_group` and `collect_logs`, plus both call
sites in `run`. The cleanup helper is now called whenever a launcher was created,
irrespective of its `poll()` result. It checks/signals the owned group, waits a
bounded grace period against group existence, and escalates to KILL independently
of leader exit. Missing-group races tolerate `ProcessLookupError`. This resolves
the concrete exited-leader/TERM-survivor paths in CR-03.

Polling and final hashing both use `collect_logs`: 512 discovered entries, 64 log
candidates, 16 MiB per file, 32 MiB aggregate and reads of at most 64 KiB. The helper
includes `.adm`, skips direct symlinks/nonfiles, and returns explicit skipped-log
reasons. It does not use the old uncapped `read_bytes()` path. This resolves CR-04.

### Actual independent checks

With `PYTHONDONTWRITEBYTECODE=1`, loaded `test_wine_compile_probe` from
`tests/unit` and ran all methods except the temporary-directory log test:
**8 tests passed**, including exited-leader cleanup, missing-group handling and
the classifier/config checks. The reviewer did not create test files.

Separately executed the actual `collect_logs` helper against explicit in-memory
path/stream doubles. All checks passed:

- 33-byte synthetic log with a reduced 32-byte per-file limit: skipped without
  opening it; the admitted five-byte `.adm` was hashed correctly.
- Five-byte log with a reduced one-byte aggregate budget: skipped without a read.
- 65 one-byte log candidates: exactly 64 hashes; candidate 65 was not read.
- 513 non-log entries: returned `discovery budget exceeded`.
- Every observed stream read requested a positive size no greater than 65,536.

These are independent source/helper checks. They do not claim a real process-tree
regression was executed by this reviewer.

### Recommended real-process regression

Add a Linux integration test using only disposable child processes: a session
leader starts a child that ignores TERM, confirms the child is ready, then exits.
After reaping the leader, invoke `stop_group` with a short bounded grace period
and verify that the child has terminated. Repeat with the leader initially alive
and exiting on TERM while its child continues to ignore TERM. Reap all test
children (a test-local subreaper can collect the orphan) and use independent outer
timeouts and a cleanup `finally`. Never signal a group not created by that test.
This would cover real OS behavior beyond the current mocked `group_alive` tests;
it is a validation recommendation, not an unresolved source defect.

### Compile-008 evidence independently inspected

Read the actual private `compile-008/compiler-report.json` and corresponding
script/RPT logs. The report records `status: initialized`, `forced_stop: true`,
launcher exit `-15`, client count zero and PBO SHA-256
`c71579a4d2f498771bcb81cbe7450a34ccc0522618d965432bfb7a39f0f273b4`.
The script log contains both the core-settings PASS in the native VM and the
server-initialized marker at 16:07:11.924/16:07:11.932 respectively. This supports
actual DayZ initialization under Wine. It does not establish clean save/restore,
and this older report does not constitute an end-to-end run of the latest harness
helpers. Missing startup dependencies are not classified as review defects.

| File | SHA-256 |
| --- | --- |
| `tools/setup/wine_compile_probe.py` | `709dbd44fe6cbf155cb6c242fab185c463a33be18863d89b8a21e1ab202744f1` |
| `tests/unit/test_wine_compile_probe.py` | `c98083cfd657b260887567592e690d396fc6b6feda95c4b2587b5a22b167cd99` |

All four concrete findings CR-01–CR-04 are now resolved at their independently
reviewed snapshots. No additional source defect is asserted by this follow-up.

## Final confirmation — real POSIX regression inspected and executed

CR-03 and CR-04 remain **resolved**. Rechecked the final `stop_group`,
`collect_logs` and their integration. Independently executed nine probe tests,
including `test_real_surviving_child_is_stopped_after_launcher_exits`:
**9 passed in 0.063 seconds**. The tenth suite method creates temporary log files;
the reviewer retained the read-only filesystem scope and used the already-passing
independent in-memory collection checks documented above instead.

The new real POSIX test creates a dedicated session/process group, reaps the
launcher, calls the actual cleanup helper and verifies that the remaining child
has exited or reached zombie state, with an owned-group cleanup fallback. The
child installs a TERM-ignore handler; the mocked cleanup regression separately
asserts the TERM/KILL sequence. This adds real OS coverage to the previously
mock-only lifecycle checks. No additional lifecycle regression is required to
resolve the reported defect.

Also confirmed the native-access report records the exact compile-008 native VM
PASS and initialization markers and explicitly retains the forced-stop limitation.
No missing startup dependency is classified as a code-review finding.

Final reviewed SHA-256 values:

- `tools/setup/wine_compile_probe.py`:
  `424ccfd8d482405f6a18a024adb3d98d2d5d9b9d30774c664442901d16e51773`
- `tests/unit/test_wine_compile_probe.py`:
  `45e68e0e79f71beb136f24caca07f11509ed5ea7d7da480c24708eeaef627d8d`

Final review disposition: **no outstanding findings from this review**. The
reviewer edited only this report and made no commits.

## Additional frozen core/crafting review

Reviewed only the requested `HCServer.c`, `HCCraftingRegistryAudit.c`,
`HCCraftingNativeChecks.c` and crafting admission-gate changes. Did not review or
edit Nash's active infected wave. Read-only checks; only this report was changed.

### CR-05 — P2: Cached full-quantity override escapes the crafting audit

**Location:** `mods/HollowCountry/scripts/4_World/Crafting/HCCraftingNativeChecks.c:20–21`.

The audit verifies `m_ResultSetQuantity[0]`, but does not reject
`m_ResultSetFullQuantity[0]`. The installed native
`4_World/Classes/Recipes/RecipeBase.c:296–302` checks the full-quantity flag first,
calls `SetQuantityMax()` when true, and only uses the configured quantity in the
`else` branch. Thus an incompatible mutation of the actual registered recipe can
pass the new audit while overriding the approved output quantity. For a stack
whose maximum exceeds the pilot quantity, crafting yields more units than the
audited material policy permits.

This is a conditional cache-drift/admission defect, not a claim that the authored
unmodified recipe currently has that flag enabled. `Configure` correctly sets it
false. It matters specifically because the new audit is intended to reject
mutated cached definitions rather than validate fresh defaults.

**Actual read-only reproduction:** executed the authored audit method through the
existing restricted translator with its explicit synthetic native DTOs:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import sys
sys.path.insert(0, 'tests/unit')
from test_crafting_completion import audit_context
cached, names, manager, context = audit_context()
print(context['run']())
cached[0].m_ResultSetFullQuantity = [True]
print(context['run']())
PY
```

Actual output: `True`, then `True`; the cached camo-net result still reports
quantity 2 while its full-quantity override is true. Installed source confirms
that native result application would select the override. No inventory objects
were spawned in this reproduction.

**Correction:** reject a true `m_ResultSetFullQuantity[0]` on these fixed-output
pilots, with a failing cached-instance mutation regression. Other overriding
native result fields should be checked where necessary to substantiate the
audit's stated invariants; this finding is limited to the demonstrated quantity
override.

### Core/native API conclusions and actual checks

- The core now tracks a module before calling `OnStart`, so an interrupted start
  leaves that module available to the next cleanup. Partial state is unwound
  before a new registry is admitted. Reverse removal is consistent with native
  array `Remove` semantics because each removal is at the last index.
- The crafting server gate now requires core `IsStarted()` as well as module
  start/validation and the live setting. Client preview returns before reading
  server profile/core state. No concrete authority bypass was established.
- Installed `PluginRecipesManager.c:42,443–453,470–475` confirms a readable
  `array<ref RecipeBase> m_RecipeList`, index-based `SetID` registration and
  `RecipeIDFromClassname` returning the stored index or -1. The new bounded
  registered-instance lookup agrees with that contract and rejects null,
  mismatched name/ID and out-of-range entries.
- Installed `RecipeBase.c:95,105,110,568` confirms the queried length,
  anywhere/repeatability and recipe-ID surfaces. No unsupported hook or native
  signature mismatch was found in the requested changes.
- The lifecycle tests use explicit synthetic callback aborts. Their result is
  source-control-flow evidence, not proof of Enforce runtime fault unwinding or
  guaranteed completion of a callback that itself aborts.

Actual commands independently run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_core_lifecycle.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p 'test_crafting*.py' -v
```

Results: **9 core tests passed; 18 crafting tests passed**. CR-05 demonstrates a
case not covered by that passing snapshot. No source or test was edited.

| Reviewed file | SHA-256 |
| --- | --- |
| `HCServer.c` | `dc2b4dcd496eaaea42be5d7ec65df4346c3db5c64136af029181bfa73349f0ed` |
| `HCCraftingRegistryAudit.c` | `6e1c5fe6426e24b1fe558a49b869f4a76994ac98f45f56d09be1bd221fb1d94a` |
| `HCCraftingNativeChecks.c` | `756b936290e9c1b42bf0a1608824ce63ba77fbf3f227239714d66a0001858c72` |
| `HCCraftingModule.c` | `ba821e10d38935be5f56c15df4c489857bb4066cab75a44854d097865317eaaf` |
| `test_core_lifecycle.py` | `bcf4b51fc22a905911c41ed04cc99ac3d786779a760da8f1f517d586a4d9c769` |
| `test_crafting_completion.py` | `f142369a5ae6f9e59b975fe13ae445939c96de158ea14c44398116b3240ba945` |

## Final infected 009 snapshot review and CR-05 resolution

Reviewed the frozen variant/stimulus, cohort retarget and membership-ambiguity
wave. Independently recomputed **all 14 SHA-256 entries** in
`tests/fixtures/runtime/infected-wave-source-freeze.json`: every entry matched,
including the eleven infected source files and three focused test files. This
review concerns that snapshot, not Nash's subsequent IC-03/IC-04 changes. The
associated compiler artifact records PBO
`8339c144c658862e293bd5eadba65cc6d81b1ea0f61959334230799ff4f87159`.

### CR-06 — P2: A rejected first-cohort retarget starves the second cohort

**Location:** `mods/HollowCountry/scripts/4_World/Infected/HCInfectedModule.c:378–381`
(fixed ascending cohort loop at line 341); rejection at
`HCInfectedNavigation.c:187–188` and `HCInfectedPolicy.c:135–145`.

`FinishSweep` decrements the sole shared route slot before calling `Retarget`.
The first cohort's live stimulus continues to satisfy `sweep.Clue` even when its
observation was already consumed or its cooldown/attempt limit makes retargeting
ineligible. Those cheap rejections therefore spend the slot on every sweep.
Because iteration always begins with cohort 0, cohort 1's fresh, eligible cue can
expire without any retarget attempt. This is lost stimulus handling, not an
unbounded native pathfinding claim.

Concrete synthetic case: two valid, moving, unengaged, fully owned cohorts with
live packs. Cohort 0 accepted observation 9 at time 10, with expiry 30, next
retarget 20, last-observed 9 and one spent attempt. Cohort 1 receives observation
11 with expiry 20, last-observed -1, next-retarget 0 and zero attempts. On every
sweep at times 12 through 19, cohort 0's unchanged live clue consumes the slot
and is rejected. Cohort 1 passes the actual scalar eligibility policy throughout
that window but is never called; its clue expires at 20. Neither pack need expire
or stall during this sequence.

**Actual read-only check:** extracted the exact `FinishSweep` retarget block
(from its `record.State != 5 && record.State != 6` guard through the closing brace
before the retirement branch), translated only its braces, `if`, boolean
operators, literal `true` and decrement into Python, and executed it in the
authored ascending order. Synthetic pack `Retarget` callbacks counted calls and
delegated eligibility to the existing `policy_functions()['RetargetAllowed']`.
For each time in `range(12, 20)`, the global slot was reset to one. Inputs were:

```python
# now, nextAllowed, observed, lastObserved, expires, attempts, owns, engaged
first  = (now, 20, 9, 9, 30, 1, True, False)
second = (now,  0, 11, -1, 20, 0, True, False)
```

The actual policy returned false for `first` and true for `second` on each sweep.
Actual scheduling output:

```text
actual scheduling block; calls: [8, 0] ; accepts: [0, 0]
second clue eligible at every sweep 12..19, expires at 20 without any Retarget call
```

**Correction:** make scheduling fair between cohorts (for example, rotate the
starting cohort), or distinguish a cheap eligibility rejection from a charged
native path attempt before consuming the shared slot. Preserve charging for
failed geometry: blindly refunding every false `Retarget` result would also
refund actual pathfinding work. Add a behavioral regression with two cohorts,
one stale/cooldown/exhausted clue and one eligible short-lived cue; the latter
must receive an attempt before expiry. No implementation was made by reviewer.

Reviewed module SHA-256:
`0c33a624fbe663a15d6c166653a90ef672f7ab8a8a0e437c26a8dfdf2e4eeab1`.
Reviewed navigation SHA-256:
`2e4cf93662ac1367cd6118c675535ef0f11e0f6a4c1b9e38a61fb2e4eda4ee54`.
Reviewed policy SHA-256:
`45b8b0e767c6687ac35cf5743d116f99d820ec8d06c1d1b5d35645219d6ac0b0`.

No additional concrete defect was established in the requested frozen profile,
stimulus-selection or membership-ambiguity changes. The new checks preserve the
spent reservation and distinguish missing membership from observed death. No
new native override signature mismatch was identified in this wave. Deferred
durable intent/progress work is outside this snapshot review.

### Actual focused checks and CR-05 resolved

Independently ran, without source/test edits:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p 'test_infected*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p 'test_crafting*.py' -v
```

Actual results: **53 infected tests passed in 0.079s; 25 crafting tests passed
in 0.075s**. The current infected suite does not cover CR-06's two-cohort
scheduling interaction. The scheduling reproduction uses synthetic ownership and
time inputs; it makes no claim to have exercised AI movement in DayZ.

**CR-05 is resolved in the reviewed source.**
`HCCraftingNativeChecks.c:24–25` now rejects a cached full-quantity flag (and a
replacement override). Independently reran the original `audit_context()`
reproduction: unmodified cached definitions returned `True`; setting
`cached[0].m_ResultSetFullQuantity = [True]` returned **`False`**. The new
full-quantity regression exercises all three cached pilot definitions. Reviewed
the additional replacement/color/tool-quantity guards against the installed
`RecipeBase.c` result/spawn/ingredient branches; no further concrete active
override bypass was established in this correction. Native 010 remains a
separately recorded coordinator experiment, not a result asserted here.

| CR-05 resolution file | SHA-256 |
| --- | --- |
| `HCCraftingNativeChecks.c` | `cd966e7136621b86bb91e629b03e66f2227306783162c3aec8f5c355c268db0b` |
| `HCCraftingRegistryAudit.c` (unchanged) | `6e1c5fe6426e24b1fe558a49b869f4a76994ac98f45f56d09be1bd221fb1d94a` |
| `test_crafting_completion.py` | `49a7b335a6d55138c9b83df936ee2ab17a7bdd43bc241de23098b778e5cdbb09` |

Current review disposition: **CR-01 through CR-05 resolved; CR-06 open on the
009 frozen source above.** Only this report was edited; no commits.

## Seed/hold harness review — CR-07 and CR-08 resolved

Scope authorized for this follow-up: read-only review of
`tools/setup/wine_compile_probe.py`, temporary ownership of
`tests/unit/test_wine_compile_probe.py` for meaningful mocked-run regressions,
and this report. Reviewer made **no harness/gameplay implementation edits** and
no commits. Test edits are now complete for freeze.

Added **13 tests**, keeping all existing 13 tests. The mocked-run fixture uses
real temporary staging, the actual stored-PBO parser, actual seed reads/copies,
hashing and report serialization. Executables/DLLs/PBO content are explicitly
synthetic; Popen, process polling, the clock and log frames are mocked. No Wine
or DayZ launch occurs in those added tests. The existing real POSIX child-cleanup
regression remains present and passes.

### CR-07 — P2: Exited launcher could pass at hold completion

At reviewed pre-fix `wine_compile_probe.py:233–239`, a persistent initialization
marker and elapsed hold duration selected `initialized` before reaching
`process.poll()`. Synthetic initialization at time 0, hold 3, launcher alive
through time 2 but exited at time 3 returned `initialized` incorrectly.
`test_launcher_exit_at_hold_completion_cannot_pass_old_marker` actually failed
with `'initialized' == 'initialized'`. Cleanup/report assertions pass before
that failure; the defect was the reported success.

### CR-08 — P2: Log-read time could complete a hold beyond the deadline

The loop checked its deadline before `collect_logs`, but success did not recheck
it after the potentially time-consuming read. Synthetic duration 15, init at
time 12, hold 3, and a log read starting at time 14 and completing at time 16
returned `initialized` instead of `timeout`.
`test_log_collection_crossing_deadline_cannot_complete_hold_after_timeout`
actually failed with `'initialized' != 'timeout'`. Cleanup/report assertions also
pass before this failure.

Actual reviewer command before the coordinator's implementation correction:

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_wine_compile_probe -v
```

Actual RED: **26 tests in 0.094s, FAILED (failures=2)**, precisely CR-07/08.
Pre-fix harness SHA-256:
`4b40f9a27ed3508a9f8e73a1fa1d0550224adb910cff2fb0a3b9321130736286`.

The coordinator then changed only the implementation to check post-read deadline
and launcher poll before initialization/hold success. Independently reinspected
the guards at current lines 234–240 and reran the same command against the
**unchanged reviewer tests**: **26 tests in 0.108s, OK**. Both findings are
resolved in that source. Final harness SHA-256:
`15696e2e5bef260da8e60d4e6df4deda8c0352fc67978f57e10bc357572532da`.
Frozen reviewer test SHA-256:
`1fcacff71f47678826b1638a93efbebc25c24b6232ba6259c3eb1794dfdf2bfb`.

Additional passing behavioral coverage: hold timing starts at initialization,
late/no initialization times out, exit during hold fails, errors during hold
override old initialization markers, and polling exceptions still stop the
owned group and write a report. Seed tests accept all three files at exactly
64 KiB each, preserve originals, stage exact contents and verify reported hashes;
reject missing directories, oversized/unknown/fourth files, directories posing
as allowed files, file/root/ancestor symlinks **before staging or launch**; and
verify a growing file is read with exactly one bounded `read(65537)` call before
rejection. No additional seed defect was established.

The malformed-JSON run test deliberately supplies both `SCRIPT (E): JSON ERROR`
and the expected preserved-settings rejection marker. Actual status remains
**`compiler-error`**, original `b'{'` is preserved, and cleanup/report assertions
pass. The conservative classifier was not weakened or the error masked.

## Frozen IC-03/IC-04 infected follow-up — CR-06 resolved

Read-only review of Nash's new route progress/purpose, prepared adoption intent,
restart validation and scheduler changes, plus `test_infected_persistence.py`
and `test_infected_routes.py`. The freeze appeared during review. Independently
recomputed **all 16 file hashes** in
`tests/fixtures/runtime/infected-ic0304-source-freeze.json`: **all matched**.
Manifest SHA-256:
`77b6e03118b4938d95f6109d94ea020e927e0db82494796e58d92956552ffad5`.
No infected source/test edits were made by reviewer.

**CR-06 is resolved.** `HCInfectedModule.c:424–460` rotates cohort priority and
charges the shared slot only for `Retarget` outcomes 1/2. Native navigation now
returns 0 for pre-path eligibility rejection and 1 for a spent failed path
attempt, preserving cooldown/attempt charging. The regression executes the
authored scheduler with the original two-cohort stale/fresh inputs; cohort 1
receives its attempt before expiry. Its geometry-failure variant verifies that
a failed path remains charged rather than retried for free. The increased
minimum work cap and reserved slots account for both bounded eligibility scans.

IC-04: inspected the actual orchestration at `HCInfectedModule.c:530–586`.
The reservation and prepared stage are inserted and written/read back before
actor assignment and `pack.Start`. Failed preparation returns without transfer.
After transfer, success commits stage 2; failure/partial release records conflicted
stage 3, retains the reservation and quarantines. Failed outcome readback also
quarantines and releases owned packs. Store validation checks stage transitions
alongside existing ledger, roster and generation monotonicity; the narrowly
allowed prepared-to-commit state change requires identical identity/count/time
fields. Restart converts preparation to conflicted abort, clears active route
intent and never replays the transfer. No concrete replay, refund, duplicate
adoption or rollback bypass was established in the reviewed control flow.

IC-03: inspected `HCInfectedNavigation.c:27–40,251–321` and route snapshots.
The plan supplies one native waypoint at a time, advances after every surviving
owned member is observed inside that waypoint's radius, and distinguishes
completion, expiry, stall, interruption and ambiguous ownership. Progress is
measured toward the waypoint rather than arbitrary displacement. Failed release
retains its existing bounded ownership/retry handling. Route plan/destination
changes dirty the record; terminal results are captured before dropping packs.
The new reads of `BehaviourGroupInfectedPackWaypointParams.m_CenterPosition` and
`.m_Radius` and the `SetWaypoints` call agree with the installed
`3_Game/AI/AIGroupBehaviour.c:7–27`. No unsupported new native override was found.
Adoption now requires a sensed destination when native routing is requested;
no fixed coordinate offset substitutes for evidence.

Actual independent command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p 'test_infected*.py' -v
```

Result: **69 tests in 0.204s, OK**. In addition, executed the actual scalar
policies in memory with an explicit synthetic id=1/reserved=living=6/created=100
ledger: four outcomes (no native transfer, successful transfer, failed transfer,
partial/releasing transfer), each followed by restart; a crash immediately after
preparation followed by abort; attempted replay to prepared/commit; and six
individual reserved/living-increase mutations. All expected transitions passed
and the replay/increase mutations were rejected. These checks exercise source
decisions; no native movement, file durability or crash experiment is claimed.

| Reviewed frozen file | SHA-256 |
| --- | --- |
| `HCInfectedModule.c` | `92b0c21df8490644cb1a60318425199ed67c856dadab91fd1eae007593bf1c9d` |
| `HCInfectedNavigation.c` | `92024979a4d80a8ecaa9b0526015fe3349b15f87596a6528bfa6455dd4671928` |
| `HCInfectedPolicy.c` | `1185ecbf88c00c077123c86f472b6dac9af380d18f92e18c0fb6b114b895f691` |
| `HCInfectedState.c` | `0e2f106a18a68246a40dcd176d1b2afb0c0a966bcf96749a1169be0adb905467` |
| `test_infected_persistence.py` | `d5468039d689d7f38945d288c0c74edd733ce4d40eb06ef27e8565d8951ff54f` |
| `test_infected_routes.py` | `4f1f8a11b9564ed7b07d5c6d752479bbd79c879c110aea4b723d43255f10887b` |

No additional concrete defect was established in this frozen follow-up.
**CR-01 through CR-08 are resolved on their respective reviewed snapshots.**
This follow-up does not assert periodic Save from probe 013, bind this source to
an older PBO, or add new acceptance claims. Final reviewer mutation scope for
this turn: only the probe test file and this review report; no commits.

## Independent build014 binding of the reviewed IC-03/IC-04 snapshot

Completed the requested follow-up after Nash's final report appeared. The source
and regressions are exactly the frozen snapshot reviewed above: independently
rechecked all **16 current source/test hashes**, with no changes. The existing
independent **69 GREEN** run and control-flow review therefore apply to this
snapshot; no redundant source/test edit or test rerun was needed.

Independently opened the **actual** disposable build014 PBO and report from
`/home/david/.cache/hollow-country/wine-server-20261116/experiments/compile-014-infected`,
rather than relying on the worker's matched-entry list. Parsed the stored PBO
with `tools.package.pbo.parse` (including its checksum validation), checked the
whole-PBO SHA-256, then hashed every one of the **11 infected source entries**
against the frozen manifest. All matched. Also verified:

- Actual report SHA-256 equals the fixture's recorded report hash, and its
  parsed content equals the embedded report.
- `research/evidence/compiler-014-infected-wine.json` is byte-identical to the
  actual report.
- All **five actual log files** match their recorded SHA-256 values. Inspected
  their World/Mission load, native core PASS, infected admission and server INIT
  markers; no `SCRIPT(E)` occurs in those logs.
- Actual HC profile files equal the evidence list: settings and infected config
  only. No horde journal exists in this run. The recorded hold is **90.792s**,
  status `initialized`, forced stop true, zero clients.

| Independently verified artifact | SHA-256 |
| --- | --- |
| Actual build014 PBO | `e0868ee3a53639795e21e33c0f03412c3b1d8b30c4157caf9abc3fa5021642ce` |
| Actual build014 report | `edf32971d922a2e52ba81d697325e828db411dcf3cf6bfc4d3f0a2716e2c315b` |
| `infected-ic0304-compiler-014.json` | `71f1d82eaa7dda478da28e53b499263dedf0172ba97ce8e36ffa41b793399307` |

**Disposition unchanged: CR-06 resolved; no new concrete finding in the frozen
IC-03/IC-04/CR-06 source or regressions.** Build014 is now independently bound to
that exact reviewed source. CR-07/08 remain resolved on the unchanged verified
probe/test hashes above. This verifies compilation/init/module admission, not
periodic journal saving. Hubble's new Rooms work and Curie's observer wave are
explicitly excluded; the pre-existing frozen Rooms entry was checked only for
artifact identity. Only this report was edited during this follow-up; no commits.

## Probe ownership handback / longer hold verification

Coordinator resumed ownership of the probe test file and changed maximum hold
to 240 seconds, retaining the total duration bound of 300 seconds and the
post-read deadline/liveness guards. Reviewer made no test or implementation
changes after the handback. Independently inspected those limits and ran:

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_wine_compile_probe -v
```

The first attempt could not create temporary directories in the read-only
sandbox (16 environment errors). Reran with the approved escalation for synthetic
temporary staging: **27 tests in 0.114s, OK**, including the mocked 240-second hold,
deadline/liveness regressions, malformed-JSON precedence, and real POSIX cleanup.
No new concrete probe defect found; CR-07/08 remain resolved.

Current reviewed probe SHA-256:
`c328abf4cdf9f4bbf33451562614741ad88d9eb22cd76b83b4788c14620b9519`.
Current coordinator-owned test SHA-256:
`c2b0a6ff7f7f43a4add9f1fd1ce23e8a198677556218193f1d3b669e15dc536a`.
Native probe016 was still running when this check was requested; no native
hold/save conclusion is added. C10 Rooms, C11 observer, C12 hygiene and Russell's
candidate-only interior catalog seam await their separate freeze/review requests;
none is accepted by this probe-only follow-up. Only this report was edited.

## Native016 observation and pending wave boundaries

Independently read `compile-016-journal-long/compiler-report.json`: status
initialized, requested hold 210s / observed **210.363s**, forced stop true and zero
clients. Report SHA-256:
`6430c1bbbd3be8db57fcedcadcbdc7afd515339202e36f0980863ff38d8113e3`.
Its PBO hash is the independently reviewed build014 hash
`e0868ee3a53639795e21e33c0f03412c3b1d8b30c4157caf9abc3fa5021642ce`.
Actual HC profile files are settings and infected config only: no journal.
The cause remains unresolved; no periodic-save conclusion is asserted.

Checked available review artifacts: only the earlier wave and IC-03/IC-04 frozen
manifests are present. Relative to IC-03/IC-04, the only changed pinned file is
`HCInfectedRooms.c`, owned by Hubble's active C10 wave and excluded here. No
new freeze request/manifest is available for C10 Rooms, C11 observer, C12 hygiene
or the candidate interior-catalog seam. Those reviews remain pending; they are
not covered by the **no outstanding findings in the previously reviewed scope**
disposition. No implementation/test changes or commits; report-only update.

## Frozen C10 Rooms and diagnostic-mode probe review

Reviewed Hubble's frozen `HCInfectedRooms.c` and
`test_room_catalog_completion.py`, plus the completed
`EXP-room-catalog-completion.md`. **No concrete correctness or native-API finding
was established in this scope.** Independently confirmed frozen SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `HCInfectedRooms.c` | `eac8684b5bb24cf92fcdffa1e092652e27c1efca343313beaa03620c8faa0455` |
| `test_room_catalog_completion.py` | `c8d6ee336f65e7f301faee3f53ca2b92df84f4b91b289b32256393b454b37198` |

Inspected the bounded key preflight, reader, diagnostic gates, live-house lookup,
survey/anchor admission, staging/deep copy and publication, including the lazy
`BuildOrder` entry point. File I/O is attempted once until Clear, including failed
loads; manual bindings are preserved. The key pass rejects missing/unknown/
duplicate object fields and escaped aliases before native deserialization. The
native parser still owns grammar/value-type/array-shape validation; the report
accurately separates that from its synthetic parser double.

Document/survey build/world, measured assertion, evidence-ID length and revision
are checked; house matching requires unique exact class and close origin/pose.
Native lookup is limited to four queries and rejects results above 64 objects or
cargos before candidate iteration. Binding/survey/anchor limits reuse existing
policies. Every survey and anchor is copied into a staging array; the sole
publication assignment occurs after all records pass, so a later bad record
cannot publish earlier entries. No source path writes catalog data or changes
normal-PBO admission. Operator provenance assertions are not misrepresented as
verified measurements.

Independently inspected installed `GetObjectsAtPosition3D` at
`3_Game/Global/Game.c:930`, pose/transforms at
`3_Game/Entities/Object.c:305,873–874`, string methods in
`1_Core/proto/EnString.c`, and `JsonFileLoader.LoadData` in
`3_Game/tools/JsonFileLoader.c`. Queried declarations match this use; no new
unsupported override is introduced. No module-hook or gameplay-flag edit is
part of this room snapshot.

Actual independent commands and results:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_room_catalog_completion.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_infected_completion.py -v
```

**13 focused tests in 0.486s, OK; 21 adjacent tests in 0.047s, OK.** These execute
authored methods with explicit synthetic engine/JSON boundaries; they do not
establish native survey geometry or deserialization behavior.

Also reviewed the coordinator's narrow diagnostic probe addition: explicitly
selects `DayZDiag_x64.exe`, adds `-server`, records `diagnostic-server`, and checks
both Server/Diag names in the existing process guard. Deadline, byte/work bounds,
cleanup and error classification remain as previously reviewed. Server-mode
parameter agrees with the official [Workbench Script Debugging documentation](https://community.bistudio.com/wiki/DayZ%3AWorkbench_Script_Debugging).
Direct fetch returned 403; the official-domain search result exposed the
relevant server-mode section. No new concrete probe defect was found.

Actual independent probe command (approved escalation for synthetic temporary
staging): `env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_wine_compile_probe -v`.
**28 tests in 0.103s, OK**, including diagnostic executable/flag/report checks and
all earlier hold/error/seed/cleanup regressions. Reviewed probe SHA-256
`c30655f0190082993f27232d8d98f0b76e038b8ec6284be02e04571210713f15`;
test SHA-256 `269410bfc6720b6e209aa17dd6ea701d282af3f199d97606a30e0bc099a5f84d`.
Probe017 was still the coordinator's separate experiment using the older 014
PBO; no claim is made that it compiles or exercises this new Rooms source.

**No outstanding findings in the reviewed C10 Rooms/probe scope.** Observer,
hygiene and candidate interior-catalog waves remain separate pending reviews.
Reviewer changed only this report; no source/test edits or commits.
