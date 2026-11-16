# EXP-vanilla-startup — unmodded local startup

Observed 2026-11-16. Native startup evidence for FR-002/FR-011, AC-002,
Banso T003; baseline warning input for T005. Neither task is closed.
Read [active spec](../../docs/specs/001-survival-overhaul/spec.md),
[plan](../../docs/specs/001-survival-overhaul/plan.md) and
[tasks](../../docs/specs/001-survival-overhaul/tasks.md) for remaining gates.

## Snapshot provenance

Read-only source: local `vanilla-p0-001/profiles`. Collection began
**2026-11-16T19:46:05.783468Z** (14:46:05 EST). Files were read sequentially,
not atomically together. Each read was bounded to its pre-read byte length;
SHA-256 covers that exact original byte prefix, including line endings.
Line references are 1-based decoded physical lines within that prefix.

**Live log set still growing; incomplete capture.** Earlier inspection showed
RPT/error sizes 629,184/81,424 bytes; these reached 634,897/87,955 bytes by
capture. The script file remained 10,578 bytes. The RPT prefix also matched a
19:45:43Z read; temporary stability does not establish completion. Later hashes
of complete files may differ. Raw logs remain outside the repository.

| Profile-relative filename | Bytes | Lines | SHA-256 |
| --- | ---: | ---: | --- |
| `DayZServer_x64_2026-11-16_14-42-32.RPT` | 634897 | 6271 | `6f936bccd52c187602e6262a3cf8ddf60efd72275d458815d6e9e501efcc0214` |
| `script_2026-11-16_14-42-32.log` | 10578 | 62 | `aa29d0b743f98d93664fa0d77c974123a4a84c55ed377b202a6f2b0ce8a04198` |
| `error_2026-11-16_14-42-32.log` | 87955 | 819 | `a043b888cb755712b952ed86a34cbab190fb4ffa55da3f7d5a43212cd822478f` |

Source modification times at capture: RPT 19:45:24.222588Z;
script 19:43:46.363699Z; error 19:45:43.042229Z.
Marker times below are log-local EST on 2026-11-16; the error header explicitly
pairs local and UTC times. Endpoints and identifiers are omitted.

## Startup markers

The RPT launch line contains no `-mod` or `-serverMod` argument. This records
the observed unmodded launch, not an independent integrity audit of installed
files. `<run>` below replaces only the local run root; path separators are
normalized. Other marker text is quoted exactly or explicitly an excerpt.

| RPT line | Local time | Marker / value | Established observation |
| --- | --- | --- | --- |
| 7 | Header | `Version 1.30.164289.70` | Executable-reported build |
| 995 | 14:42:52.502 | `FileSystem: Adding relative directory '<run>/mpmissions/dayzOffline.chernarusplus' to filesystem under name mission` | Selected mission mounted; path sanitized |
| 1952 | 14:43:14.777 | `Module: Mission; loaded 219x files; 469x classes` | Mission script load reported; excerpt |
| 1971 | 14:43:15.363 | `[CE][Hive] :: Initializing OFFLINE` | Literal CE mode label |
| 1972 | 14:43:15.363 | `[StorageDirs] :: Selected storage directory: <run>/storage/storage_1/` | Persistence directory selected; path sanitized |
| 4396 | 14:43:29.779 | `[CE][Hive] :: Empty storage folder, reinitializing ...` | CE reports empty storage |
| 6099 | 14:43:47.297 | `[CE][Hive] :: Initializing of spawners done.` | Spawner initialization marker reached |
| 6100 | 14:43:47.304 | `[CE][Hive] :: Init sequence finished.` | CE initialization completion marker reached |
| 6101 | 14:43:47.304 | `Player connect enabled` | Server-side connection readiness; no client join proof |
| 6107 | 14:43:47.894 | `[IdleMode] Entering IN - save processed` | Literal idle/save message; no restart proof |
| 6108 | 14:43:47.894 | `[Shutdown] Shutting down in 1800 seconds (30 minutes).` | Future countdown; no completed shutdown proof |

RPT 4055–4057 reports 436 prototypes, 831 containers, 11,074 points,
75 dispatches and 264 proxies. A second load (4060–4062) reports 0 prototypes,
55 containers, 232 points, 0 dispatches and 0 proxies. Keep these loads separate;
no effective merge or eligible loot opportunities are inferred. Lines 4064–4065
report `Group`: 11,679 groups and `Dirt`: 0 groups, each with `groups failed: 0`,
largest group range 34.2. This does not resolve the offline audit's unknown names
or erase other CE diagnostics.

## Grouped CE diagnostics

Method: select RPT lines containing `[CE]` and either literal `WARNING` or
`!!!`; partition by message family. **63 entries across 10 families**.
The 84 `[CE][Storage]` lines reporting `ver:0 stamp:0, valid:NO` are outside
that filter and recorded separately; they do not establish a failed restore.

| Family | Entries | Observed detail |
| --- | ---: | --- |
| Empty preset | 1 | `Xmas_Ammo_Small` |
| Missing cargo preset | 12 | `Xmas_Ammo_Small` |
| Groups have no points | 1 | Message reports **5 groups**, not five warning entries; does not enumerate all groups |
| Ignored nonexistent type | 7 | `CeramicPot_Black`, `CeramicPot_Gray`, `CeramicPot_Natural`, `CeramicPot_White`, `Glock_Tan`, `Static_FrozenScientist_DE`, `ZmbM_takiCitizenUrbanB_BlueBright` |
| Ignored nonspawnable type | 1 | `ChristmasTree`; message asks whether scope is public |
| Skipped nonexistent event | 1 | `VehicleTransitBus` |
| Point removal | 21 | `Land_BusStation_wall_bench` 12, `Land_Shed_M1` 3, `Land_Shed_W1` 2, `Land_Boat_Small1` 2, `Land_Boat_Small2` 1, `Land_Shed_M3` 1; coordinates omitted |
| Container LootMax below event child LootMax | 11 | `StaticAirplaneCrate` 9, `StaticPoliceSituation` 1, `StaticTrain` 1 |
| Requested loot exceeds possible loot | 7 | `StaticAirplaneCrate` 6, `StaticPoliceSituation` 1 |
| Boat initialization spawn shortfall | 1 | `VehicleBoat`: 15 < 17, within 51 attempts |

Source ranges: presets 4038–4050; no-point message 4058; types/event 4077–4085;
point removals 5006–5646; loot-limit messages 5695–5922; boat message 5978.
These are vanilla-run observations, not diagnoses of harmlessness, fatality,
root cause or a required modfix.

## Script and error counts

Script prefix: **22 SCRIPT (W)** entries, **0 SCRIPT (E)** entries:
19 missing script declarations, 2 methods not linked, 1 obsolete method.
The declarations name `HumanInputController` twice, `BotStateMachineData`
13 times, `RoboclientUtils` 4 times. The obsolete message names
`UpdatePathgraphDoorByAnimationSourceName` and suggests
`UpdatePathgraphEntityState`; neither API is validated here.
Another 31 `WineBottle::OnQuantityChanged` messages are explicitly `[INFO]`
about undefined liquid type and are not counted as script warnings.

Error prefix: **614 (W)** and **44 (E)** entries, 658 total. Count only
severity-tagged lines, excluding context lines:

| Family | (W) | (E) |
| --- | ---: | ---: |
| ENTITY: unknown object class | 386 | 0 |
| ENTITY: missing door geometry selection components | 195 | 0 |
| ENTITY: required class inheritance | 0 | 31 |
| SCRIPT: missing declaration / unlinked / obsolete | 22 | 0 |
| GUI: missing localization strings | 9 | 0 |
| PHYSICS: second driver parsing Crew | 2 | 0 |
| WORLD: preset item ignored / preset load error | 0 | 5 |
| ANIMATION: cannot load skeleton XML / failed open | 0 | 4 |
| MATERIAL: cannot load material | 0 | 2 |
| AUDIO: missing sound shader | 0 | 1 |
| RESOURCES: failed open | 0 | 1 |
| Total | 614 | 44 |

Script warnings repeat in script/error/RPT files: do not add these per-source
counts as unique incidents. CE/error messages may also overlap semantically.
The table does not exhaust untagged RPT messages. Separate literal RPT family
counts: `Warning: No components` 1,933; `PerfWarning:` 350;
`Warning Message:` 452; `Convex ` 892. These are not severity assessments.

## Limits and outstanding evidence

Startup reached CE completion and connection enablement despite the recorded
diagnostics. This does not classify messages as harmless or fatal, demonstrate
a gameplay defect, or justify a mod fix. No game/config changes were made.
No client join, respawn, inventory operation, reconnect, completed shutdown,
persistence restart, signed mod load, DayZDiag experiment, two-client behavior
or 3–6-player performance benchmark is established here. T003 and T005 remain
incomplete; budgets remain provisional. Main owns native user workflow, other
documents and GitHub. This worker writes only this report.

## Report validation

Inline standard-library contract: actual initial red was
`AssertionError: False is not true : startup evidence report missing`;
1 test, 1 failure, exit 1. The smallest change was this document alone.
The same command then passed: 1 test, OK, exit 0. This verifies report presence,
required facts/limits and basic identifier sanitization; it does not execute
DayZ or prove behavior. No persistent test file was added.

Exact red/green command, from repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from pathlib import Path
import unittest
class StartupReportContract(unittest.TestCase):
 def test_sanitized_startup_report_exists_with_evidence_and_limits(self):
  p=Path('research/experiments/EXP-vanilla-startup.md')
  self.assertTrue(p.is_file(), 'startup evidence report missing')
  text=p.read_text()
  for marker in ['1.30.164289.70','Player connect enabled','Init sequence finished.','storage_1','SHA-256','still growing','22','614','44','client join','shutdown','T003','T005']:
   self.assertIn(marker,text)
  import re
  self.assertIsNone(re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b|\b7656119\d{10}\b',text))
unittest.main(verbosity=2)
PY
```
