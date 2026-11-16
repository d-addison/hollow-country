# Disposable diagnostic mission: native scalar/storage probe preparation

Status: preparer implemented and frozen; native hook compile/execution pending.
Scope: this report, `tools/setup/diagnostic_mission.py`, and
`tests/unit/test_diagnostic_mission.py` only. No PBO, gameplay, settings, production
flags, main Wine harness, Steam mission or other worker file was edited. No commit.
Traceability: canonical FR-002/FR-006/FR-011, NFR-001/NFR-005/NFR-006, AC-002/AC-005;
this prepares evidence collection and does not promote any runtime acceptance.

## Installed/source inspection and exact hook

Inspected private stock ChernarusPlus `init.c` in the isolated server cache and
installed `scripts-1.30.164289/5_Mission/mission/missionServer.c`:
`CustomMission: MissionServer`, `Mission CreateCustomMission(string path)` returns
`new CustomMission()`, and MissionServer has `override void OnInit()` calling its
superclass. Authored `scripts/5_Mission/HCMissionServer.c` already mods MissionServer
and starts HC through `super.OnInit(); HCServer.Get().Start();`.

The helper substitutes only that factory's instantiated class with
`HCDisposableDiagnosticMission` and appends an authored subclass extending
`CustomMission`. Its `OnInit()` calls `super.OnInit()` first, preserving the existing
CustomMission/modded MissionServer/native lifecycle. Under `DIAG_DEVELOPER` only,
with a valid server game and a per-instance once guard, it directly calls:

1. `HCInfectedSelfTests.Run()`; emits an explicit hook scalar result.
2. `HCInteriorSelfTests.RunStorageProbe(900001)`; emits an explicit hook storage result.

Both existing methods were inspected, including storage's fresh-epoch guard and
synthetic journal/serializer/recovery checks. The hook does not short-circuit the
storage call when the infected scalar check fails. BEGIN and explicit PASS/FAIL
markers distinguish reached/executed checks from admission logs. No timer, player,
inventory, AI entity, test API patch or feature activation was introduced. Stock
mission main/CE initialization and other stock behavior remain unchanged.

## API and bounded staging contract

```python
from tools.setup.diagnostic_mission import prepare_diagnostic_mission
provenance = prepare_diagnostic_mission(stock_mission, fresh_mission_destination)
mission_path = provenance["mission_path"]  # coordinator passes as -mission
```

The caller owns the unchanged PBO, diagnostic executable, fresh profile, settings,
launch, timeout and log collection. It must select actual diagnostic server mode
and a profile where reserved epoch 900001 does not exist. All ordinary module and
physical feature activation can remain false: the explicit mission calls do not
require module admission. `RunPolicySelfTests` config is not needed for this hook.
The helper never launches a process or writes config/profile/PBO files.

Preflight permits at most 256 entries, depth 12, 128 MiB per file, 256 MiB total,
and 64 KiB `init.c`. These are preparer bounds, not measured gameplay budgets.
The actual 80 MiB stock areaflags.map requires the file bound above. Copying is
streamed in bounded chunks. Unsupported factory shape, previously instrumented
source, symlinks/ancestors/dangling links, special files, overlapping paths,
parent traversal, source checkout and Steam paths are rejected. The destination
must be absent; writes use exclusive creation. Preflight errors create no output.
I/O failures preserve partial output without a completion marker and retries
refuse it. This is a local staging tool, not a sandbox against hostile concurrent
filesystem mutation; source metadata is rechecked before and after each copy.

Every original file gets source/staged SHA-256 and byte counts. Only init.c may
differ. Empty directories are preserved. The generated marker
`.hollow-country-diagnostic-mission.json` is written last and contains provenance,
the exact change description and hook hash. Purchased mission contents and
profiles stay outside the repository.

## Actual TDD and local copy observations

Tests were authored before the helper existed. Actual RED command:

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_diagnostic_mission.py -v`

Actual result: exit 1, `Ran 1 test`, `FAILED (errors=1)`; import failed with
`ImportError: cannot import name 'diagnostic_mission' from 'tools.setup'`.
This is missing-implementation RED, not an engine failure or a previously executed
behavioral branch. Implemented the helper, then the same command passed:
**Ran 13 tests in 0.013s; OK**. Synthetic fixtures explicitly cover exact stock
preservation/hash provenance and authored delta, lifecycle/diag/server/once guards,
no overwrite, dangling links, root/ancestor/entry symlinks, traversal, overlap,
Steam/source paths, unsupported/duplicate factory, entry/file/total/init/depth
budgets, FIFOs, empty directories and preserved partial-copy failures. No full
suite or CI was run for this bounded task.

The preparer was also executed against the actual cached stock mission, creating
fresh output only at:
`/home/david/.cache/hollow-country/wine-server-20261116/experiments/diagnostic-mission-preparer-001/mpmissions/dayzOffline.chernarusplus`.
Actual copied stock: **43 files, 108740480 source bytes**. All 42 non-init file
hash pairs matched. Exact init delta was independently asserted as the factory
substitution plus the authored appended hook. Source init remained unchanged.

- Stock init SHA-256: `73658fca45ade1c54d7ee729b31f78f3c27b46282ffd3d503d10b524b8a20afb`.
- Staged init SHA-256: `19ccac4be61848d9407f04a4b0df60919140f7dcd12742322c60da520d5c3e50`.
- Authored hook SHA-256: `8b4166f34a7168461b00c131ccfec145d2b4cedfb5bb5c5c8f28e709f630145d`.

## Pending actual experiment and interpretation

The coordinator will wire optional `--diagnostic-selftests` and `-mission` to the
main harness; this worker did not edit it or launch a competing engine instance.
Native017 diagnostic World/Mission compilation and admission were reported by the
coordinator, along with an actual SCRIPT(E) in PluginItemDiagnostic OnInit for
missing GetPluginConfigDebugProfile. Retain that failed diagnostic smoke. No API
patch/suppression was added. The new hook has not yet been compiled/executed in
DayZ; offline copy/hook checks cannot establish that it runs in this environment.
A native failure earlier in the superclass chain may prevent reaching the hook.

Record actual DIAG_DEVELOPER defines, unchanged PBO hash, executable/config/init
hashes, BEGIN and both result lines, PASS/FAIL, all SCRIPT(E), and actual reserved
profile epoch files. An explicit scalar/storage result can be reported with an
engine-error caveat; an unrelated SCRIPT(E) still prevents clean-smoke acceptance.
Absence of markers is unobserved execution, not passing execution. The storage
probe checks native serializer/file/reload/claim-state quarantine with synthetic
identities; it does not grant inventory or demonstrate inventory atomicity, real
crash/power-loss durability, infected periodic saving, gameplay, two clients,
performance or Windows acceptance. Runtime persistence gates remain pending.

## Frozen authored source hashes

- `tools/setup/diagnostic_mission.py`: `23b7261941f157a36955c5357ed3d571d2a9ccc345a697173b918cbbfc9853c5`.
- `tests/unit/test_diagnostic_mission.py`: `37d303f279f99308c1fc0a676196f50ec1ac63e0bd7e74b8edb1754b59189fbe`.


## Actual019 outcome: timeout, diagnostic mission execution unobserved

Reviewed preserved `research/evidence/compiler-019-diagnostic-storage-wine.json`
and the matching private script log. Report SHA-256:
`7af2e45f6220d288fdb94018f8e47aa71b9fe065f0b64628bdcf6b50ea981159`.
The actual diagnostic server under Wine ended **status timeout**, forced stop,
zero clients. PBO SHA-256:
`038a420209dbe4b830fbf41ba44e16be7e6c82fa9759a9bb32bf81a6bfd9cf6c`.
Diagnostic EXE SHA-256:
`4bbf370b1d479e0556e916d21213bafba383cbdd3a12c6e2518cd49c1ca64e70`.
The report embeds all 43 mission-file hashes and the same frozen authored hook
hash; staged init SHA-256 remained
`19ccac4be61848d9407f04a4b0df60919140f7dcd12742322c60da520d5c3e50`.

Actual Game and World module compilation was observed with SERVER, DIAG and
DIAG_DEVELOPER defines. **No Mission module, HC initialization, BEGIN, scalar or
storage results, or diagnostic PASS marker was observed.** No SCRIPT(E) was
observed in that script log; its absence does not make the timeout a clean smoke.
No HollowCountry profile files were observed. This run establishes neither native
hook execution nor storage-probe success. Preserve it as timeout/unobserved.

019 supplied `-mission=.../diagnostic-mission` without a terrain suffix. Bohemia's
[official terrain sample](https://community.bistudio.com/wiki/DayZ%3ATerrain_sample)
specifies `mission_name.terrain_name`; its
[modding example](https://community.bohemia.net/wiki/DayZ%3AModding_Basics?useskin=vector)
passes a directory ending `.ChernarusPlus` to `-mission`. Installed script
DayZGame.SetMissionPath receives a path from C++; terrain parsing is not exposed
in the inspected script. Missing suffix is a supported hypothesis, **not a
confirmed root cause**. The helper accepts arbitrary destination names; it does
not enforce terrain suffixes. Coordinator's map-qualified
`diagnostic.chernarusplus` retry020 is **pending**, without inferred success.

Utility and focused tests remain frozen at the hashes above; no implementation
or hook changes were made for this report addition. Coordinator reports the
integrated gate at 508 unit tests and 22 BDD scenarios; this worker independently
ran only the recorded 13 focused tests. No full suite/CI rerun or commits here.
