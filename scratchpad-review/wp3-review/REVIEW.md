# WP3 review: infected competence probe (commit c40dcd8)

Reviewer: Sonnet 5.5. Read-only review; only files under this directory were written
(`hook_default.c`, `mutate.py`, `mutate2.py`, `mutation_results.txt`, `mutation_pairs.txt`).
The mutation harness ran on a throwaway copy of `tools/` and `tests/`; the copy was deleted.

## Verdict: MERGE-WITH-FIXES

The registration, cache citations, compile shape and receipt honesty are sound. Staging works unpatched.
Three defects keep the first run from being useful, and one is a validator/hook contradiction:

1. F1: the structure query and the geometry rays use the authored Y, not terrain height.
2. F2: the validator rejects the hook's own `trial_time_budget` output.
3. F3: the crawl and limb stimulus does not reach the native crawl path, so those trials cannot see a crawl.

None needs a redesign. F1 to F4 should be fixed before staging a real run. The rest can follow.

## Ranked findings

### F1 (High, hook correctness): spawn/anchor/ray heights are absolute authored Y, not terrain

- `infected_competence_probe.py:315` (`GetObjectsAtPosition3D(anchor, 2.0, ...)`, a 3D sphere).
- `:337` (`rayBegin = spawnPoint + Vector(0, 0.8, 0)`).
- `:428` (`CreateObjectEx(..., spawnPoint, ...)`).
- `:129-130` (default Y = 0.0).
- Scenario:
  - The default fixture, and any `--trials-json` whose Y is not the exact terrain height, puts the rays 0.8 m above Y.
  - On inland Chernarus the ground is far above Y=0, so the rays run underground.
  - A 2 m sphere at Y=0 will not contain a building origin that sits at ground level.
  - So the structure query returns `structure_missing_ambiguous_or_query_budget`. Every default server trial is inconclusive, deterministically.
  - If the structure query is satisfied but Y is slightly off, `footprint_geometry` reports hit bits for the wrong volume.
  - `check_trials` accepts Y from -100 to 2000, so nothing forces a correct value.
- Pattern to follow:
  - `death_selection_probe.py:538-539` resolves `GetGame().SurfaceY(x, z)` before creating anything.
  - `SurfaceY` is `Game.c:1176`: `proto native float SurfaceY(float x, float z)`.
  - `taped_light_probe.py:218` does the same.
- Minimal fix, in `HCICStep` after `HCICSetup`:
  - set `anchor[1] = GetGame().SurfaceY(anchor[0], anchor[2])` and `spawnPoint[1] = GetGame().SurfaceY(spawnPoint[0], spawnPoint[2])`;
  - widen the 2.0 m radius or add a Y tolerance, because a building origin can sit above or below `SurfaceY` on slopes;
  - add `SurfaceY` to `NATIVE`.
- Alternative: have the trial schema drop Y and treat it as terrain-derived only.

### F2 (High, validator vs hook contradiction): the hook's own time-budget outcome is refused by the validator

- Hook: `:480-485` marks a trial `trial_time_budget` when `elapsed > PER_TRIAL + 1000`. `:514` (`HCICNext`) then writes `elapsed_ms = GetTime() - m_TrialBegin`, which is at least that value.
- Validator: `:747` requires `elapsed_ms` in `0..per_trial_ms + 1000` for every row.
- Demonstrated (temp stage, receipt with one inconclusive `trial_time_budget` row at `elapsed_ms=6070`):
  `time-budget row REFUSED: trial elapsed must be an integer 0..6000`
- Scenario: a server hiccup during one trial yields a legitimate inconclusive row, and the whole receipt becomes unvalidatable instead of counting one inconclusive.
- Minimal fix:
  - apply the `per_trial_ms + 1000` bound only to `completed` rows;
  - for `inconclusive` rows bound by the plan cap, `len(trials) * (per_trial_ms + 1100) + 30000`;
  - add a test with a `trial_time_budget` row.

### F3 (Medium-High, probe validity): `crawl_transition` and `limb_damage` use a stimulus that does not enter the native crawl path

- The hook calls `DecreaseHealth("LeftLeg","Health", legHealth)` at `:468`. `Object.c:1034` is a plain `proto native` health setter.
- `m_CrawlTransition` is assigned in one place only: `ZombieBase.c:1000`, inside `EEHitBy` (`:981`) via `EvaluateCrawlTransitionAnimation` (`:826`). `m_IsCrawling` flips only in `HandleCrawlTransition` (`:811-818`).
- It is unobserved whether `DecreaseHealth` raises `EEHitBy`. The report itself concedes this (REPORT gap 5).
- Consequence:
  - `crawling=false` after the stimulus is the expected outcome under either hypothesis, so a "completed" `crawl_transition` row carries no information.
  - It still counts in `completed`.
  - Nothing in the validator requires that the left-leg health actually fell (demonstrated: a completed limb/crawl row with unchanged health is accepted).
- `Object.c:1138` proves `ProcessDirectDamage(int damageType, EntityAI source, string componentName, string ammoName, vector modelPos, float damageCoef = 1.0, int flags = 0)`.
  - That is the hit-path entry the brief named.
  - The writer's report does not say why it was not used.
- Minimal fixes (either):
  - (a) use `ProcessDirectDamage` for `crawl_transition` with a config-checked stock ammo, and keep `DecreaseHealth` only for `limb_damage`;
  - (b) keep it, but make the validator require `left_after < left_before` for completed `limb_damage` and `crawl_transition` rows, and relabel `crawl_transition` as "hit-path not exercised".
- Related, Low: `spawn_lifecycle`, `mind_no_target`, `footprint_geometry` and `door_state` run the identical code path (spawn, rays, two samples). Only the door read and the damage kinds differ. `completed=5` therefore overstates distinct coverage. State that in `report` output.

### F4 (Medium): `maxPlayers = 0` config rewrite rests on unobserved engine behavior

- `_no_clients_config` at `:587-597`, applied in `stage` at `:626-628`.
- No other probe touches `serverDZ.cfg`, and no evidence shows that 0 is admitted or means "no clients" (it could be refused, or treated as unlimited).
- The hook already aborts the run on any identity (`HCICNoClients`), and no client is launched.
- Scenario: the first real run fails to start, or behaves unlike what the plan states, and the cause is a config change nobody asked for.
- Minimal fix: stage the stock config unchanged and keep the hook's identity abort. If the lock-out is wanted, record it in the plan as a pending native experiment, not as a control.
- Mutation E13 (the receipt-side config check) also survived; see F6.

### F5 (Medium, honesty): `validate`/`report` output does not mention fixture status

- `validate()` return value at `:808-812`.
- The plan carries `fixture_status` per trial, and the docstring and REPORT say the default is unqualified.
- Demonstrated: a synthetic default-fixture receipt with 6 completed trials prints `denominator: attempted 6, completed 6, inconclusive 0, client_required 3`, with no placeholder flag.
- Scenario: someone later reads "6/6 completed" without the plan.
- Minimal fix: add `fixture_status_counts` and a limitation line (for example "N trials used unqualified-candidate fixtures; not the #18 building/angle denominator") when any trial is `unqualified-candidate`. Also print a one-line warning from `stage` when `--trials-json` is omitted.
- Placeholder clarity as shipped: the default is unqualified in the docstring (`:6-9`), in each trial's `fixture_status`, and in REPORT. It is not clear in the runtime outputs, hence this finding.

### F6 (Medium, test strength): the generated hook's behavior is asserted only by substring; many validator guards have no direct test

Full mutation list in `mutation_results.txt`. 75 single-line mutations were run: 23 killed, 52 survived.

- Hook behavior survivors. The hook tests check only `assertIn(api, hook)` and lint.
  - removing the per-trial and per-receipt `deleted` increments (H2, H3);
  - removing `HCICCleanup()` from `HCICNext` and `HCICFinish`, or from `OnMissionFinish` (H5, H6, H7);
  - removing the `spawned = 1` bookkeeping (H8);
  - the no-client abort (H9);
  - the global cap check (H10);
  - the output-size cap (H11);
  - the sentinel text (H12);
  - the door-loop bound (H13);
  - the `m_Owned = null` reset (H14);
  - the leg-health guard (H15);
  - the ray count (H16);
  - ECE flags (H17);
  - the watchdog scheduling (H18);
  - the query bound (H19);
  - the structure-ambiguity rule (H20);
  - the client-required skip (H1).
  - Only H4 (removing `ObjectDelete`) was killed.
- Validator survivors, genuinely untested because no other check masks them:
  - client-required row with `spawned`, `samples`, `doors`, `geometry`, `elapsed_ms` or a mismatching `reason` (C3 to C8);
  - the `observed == (status == completed)` rule (D4);
  - completed row with 0 samples, or `spawned != 1` (E1, E2);
  - door rows outside `door_state` (E6);
  - sample `target`/`alive` contamination (E7);
  - array bounds (E9);
  - the reason length bound (E10);
  - door index order (E12);
  - the receipt-side no-client config check (E13).
- Stage and `check_trials` survivors:
  - native verification (S2);
  - lint refusal (S3);
  - the spawn within 20 m rule (S4);
  - `fixture_status` (S5);
  - support-state mismatch (S6);
  - canonical reason (S7);
  - duplicate id (S8);
  - the plus-count refusal (S9);
  - the 100-trial cap (S10);
  - the position bounds (S11);
  - `max_spawned_entities` and `wait_minutes` (S12, S13).
- Several pairs mask each other:
  - V1/V2 (per-row cleanup vs totals);
  - V4/V12 (unknown kind vs identity);
  - E14/E15 (init hash vs init endswith hook);
  - C1/C2 (observed vs status).
  - Removing both of a pair is killed (`mutation_pairs.txt`), so those are redundancy, not holes.
  - The cleanup count (V1/V2) and the unknown-kind refusal (V4/V12) are therefore protected, but only in pairs. A test with `assertRaisesRegex` for each message would pin them individually.
- Root cause: `test_refuse_hash_unknown_kind_client_observations_and_cleanup_lies` uses bare `assertRaises(ValueError)`, so any other ValueError satisfies it.
- Minimal fix:
  - parametrise the mutation list with an expected message regex per case;
  - add one client-required mutation per field;
  - add static hook-structure tests, for example:
    - every `CreateObjectEx` result is stored in `m_Owned`;
    - `HCICCleanup` is called from `HCICNext`, `HCICFinish` and `OnMissionFinish`;
    - `HCICCleanup` contains both `deleted` increments;
    - the `client_required` branch contains no `CreateObjectEx`;
    - loop bounds appear literally;
  - add negative tests for `check_trials` and for `stage` on lint or native drift.

### F7 (Low): `client_required` elapsed time is measured, not forced to zero

- `HCICNext` at `:514` writes `GetTime() - m_TrialBegin` for every trial, including `client_required` ones. The validator at `:759` demands exactly `elapsed_ms == 0` there.
- `GetTime()` is mission time in ms (`Game.c:1534`). It is probably identical within a frame, but a 1 ms tick would make a correct receipt unvalidatable. Demonstrated: `elapsed 1ms REFUSED: client_required trial cannot be observed`.
- Fix: in the client branch of `HCICStep` skip the `HCICNext` timing, or have `HCICNext` leave `elapsed_ms` at 0 when `support_state == "client_required"`.

### F8 (Low): validator is lenient on extra keys and thin on kind-specific evidence

- Extra keys inside samples, doors and the top-level document are accepted. Demonstrated: `samples[0]['attack_observed']=True` is accepted. Only the trial row's key set is exact.
- Door evidence is required for `door_state` only. Nothing checks that kind-specific data differs (see F3).
- Fix: set-compare the keys of samples, doors and the document.

### F9 (Info): deletion accounting attests calls, not absence

- The hook increments `deleted` right after `ObjectDelete` (`:502-505`). `ObjectDelete` is `void` (`Game.c:705`).
- The validator's `spawned == deleted` is therefore tautological against the hook. REPORT acknowledges this, and `limitations` says so.
- Optional improvement: after the last trial, run `GetObjectsAtPosition3D` at each spawn point and record the residual `ZombieBase` count.

### F10 (Info): launcher_problems with the plan file present

- With the plan file present, `launcher_problems` returns `['runtime files differ from staged_files']`. By design, the plan file is not in `staged_files`, same as weather (`test_weather_probe.py:855-859`).
- With the plan file held aside it returns `[]`.
- The new test never calls `launcher_problems` itself. `stage` runs it through `write_plan`, so this is covered indirectly.

## 1. Native API citations

All 46 `NATIVE` rows pass `verify_native` against the cache. I re-read each line independently.

Key signatures:

| API | Cache line | Result |
|---|---|---|
| `CreateObjectEx(string, vector, int, int=RF_DEFAULT)` returns `Object` | `3_Game/Global/Game.c:703` | OK |
| `ObjectDelete(Object)` void | `Game.c:705` | OK |
| `ECE_PLACE_ON_SURFACE` = 1060 | `3_Game/CE/CentralEconomy.c:38` | OK |
| `ECE_INITAI` = 2048 | `CentralEconomy.c:18` | OK |
| `GetObjectsAtPosition3D(vector, float, out array<Object>, out array<CargoBase>)` | `Game.c:930` | OK |
| `GetWorldName(out string)` | `Game.c:932` | OK |
| `GetVersion(out string)` | `Game.c:942` | OK |
| `IsServer` | `Game.c:1120` | OK |
| `GetPlayerIndentities(out array<PlayerIdentity>)` | `Game.c:1166` | OK |
| `GetTime()` int, mission ms | `Game.c:1535` | OK |
| `GetCallQueue(int)`, `CallLater(func, int, bool, ...)` | `Game.c:1550`, `2_GameLib/tools.c:61` | OK |
| `DayZInfected.GetInputController()` returns `DayZInfectedInputController` | `3_Game/Entities/DayZInfected.c:107` | OK; `ZombieBase` uses it at `ZombieBase.c:252` |
| `GetMindState()` int, `GetTargetEntity()` `EntityAI` | `DayZInfectedInputController.c:9-10` | OK |
| `Building.GetDoorCount`, `IsDoorOpen(int)`, `IsDoorLocked(int)` | `3_Game/Entities/Building.c:31,34,55` | OK; `Building : EntityAI`, so `Building.Cast` is legal |
| `RaycastRV(beg, end, out vector, out vector, out int, ...)` | `3_Game/Global/DayZPhysics.c:199` | OK; the hook declares all three out arguments before the call and uses the default `ObjIntersectView` |
| `GetHealth(string, string)` | `Object.c:994` | OK |
| `DecreaseHealth(string, string, float)` | `Object.c:1034` | OK |
| `ZombieBase.IsCrawling()` | `4_World/Entities/Creatures/Infected/ZombieBase.c:1090` | OK; script-defined, returns `m_IsCrawling` |
| `OpenFile`, `ReadFile(FileHandle, void, int)` | `1_Core/proto/EnSystem.c:417,425` | OK; the `string` buffer is documented, and `JsonFileLoader.c:19` does the same |
| `$mission:` paths | `CfgGameplayHandler.c:3`, `ScriptConsole.c:72` | OK; the REPORT's ScriptConsole citation is a constant, but stock reads `$mission:` files via `JsonFileLoader` |
| `JsonFileLoader<T>.MakeData(T, out string, out string, bool)` | `JsonFileLoader.c:85` | OK |

Notes:

- ZombieBase spawn and delete:
  - Class `ZmbF_JournalistNormal_Blue` with `ECE_PLACE_ON_SURFACE|ECE_INITAI` matches the stock debug spawn at `4_World/Plugins/PluginBase/PluginDayZInfectedDebug.c:367`, which additionally passes `ECE_EQUIP_ATTACHMENTS`. Omitting equip is harmless and arguably cleaner.
  - Every `CreateObjectEx` result is retained in `m_Owned` (an `Object`) before the `ZombieBase` cast, and `HCICCleanup` deletes `m_Owned` even if the cast failed.
  - At most one entity is live: `HCICNext` cleans up before scheduling the next step.
  - Cleanup also runs from `HCICFinish` and `OnMissionFinish`.
  - Bound: 100 trials at most; at most one entity per server trial (`max_spawned_entities` = count of server trials).
- Damage and crawl:
  - `ProcessDirectDamage` is proven at `Object.c:1138` but is not used (F3).
  - `DecreaseHealth` is the only damage API used.
  - The writer's forbidden-token test also bans `ProcessDirectDamage(`, `StartCommand_Crawl(`, `SetPosition(`, `OpenDoor(` and similar.
- Door reads use only `GetDoorCount`/`IsDoorOpen`/`IsDoorLocked`: no door controller, no `OpenDoor`/`CloseDoor`/`LockDoor`.
- `RaycastRV` does not use the `with`/`ignore` filters, so a ray that hits the zombie itself would count as a hit. The zombie is not yet spawned during geometry, so this is fine.
- `verify_native` only does a substring match of the API name on the cited line. Three `ToString` rows (`EnConvert.c:30,115,138`) are only weakly pinned; a signature-level check would be stronger. Not a defect.
- Not in the ledger, but verified present:
  - `CALL_CATEGORY_SYSTEM` (`3_Game/tools/tools.c:8`);
  - `FileMode` (`EnSystem.c:382`);
  - `CargoBase` (`Cargo.c:6`);
  - `PlayerIdentity`;
  - `JsonFileLoader`.

No unobserved API is used. Misuse risk: F1 (terrain Y) and F3 (stimulus).

## 2. Compile shape

Default render (`hook_default.c`): 15760 bytes, SHA-256 `d9a39d78...d8854`, identical to the writer's hash.

- Binary `+` per statement: my own statement splitter, independent of `probe_runtime`, found 1 maximum. A raw count including string-literal `+` gives 2. Limit is 8. A render with 100 trials also passed lint (61053 bytes against `MAX_HOOK_BYTES` 262144).
- Explicit `ToString`:
  - Numeric members are stringified with `.ToString()` (`GetHealth(...).ToString()` and `vector.ToString()` at `EnConvert.c:138`).
  - The only `+` on strings is `"status=" + outcome`, where `outcome` is a string.
  - `lint_hook(explicit_numbers=True)` returned `[]`.
- Identifier collisions against engine types:
  - I rebuilt a broader type set from all class, enum and typedef names in the cache (7518 names, against `native_type_names` 7190).
  - The only overlaps are type uses (`Building`, `Object`, `string` and similar), with no variable or member named after an engine type.
- No line starting with `||` or `&&`; no ternary.
- Duplicate locals:
  - My per-method scan found none in the 14 methods.
  - Locals inside `for` bodies in `HCICGeometry` are single-declared.
- Out arguments are declared before the call:
  - `structureName`, `anchor`, `spawnPoint` before `HCICSetup`;
  - `contactPoint`, `contactDirection`, `contactComponent` before `RaycastRV`;
  - `worldName`, `buildName`, `outputData`, `outputError` likewise;
  - `identities` is created before `GetPlayerIndentities`.
- Overrides: `OnInit()` and `OnMissionFinish()` take no parameters, matching `missionServer.c:85` and `gameplay.c:702`.
- Loops: the structure scan is `<128`, rays `<4`, doors `<16`. No `while`.
- `probe_runtime` lint: passes (`[]` with the real cache and `explicit_numbers=True`).
- Serialization: the JSON field sets of `HCICTrial`, `HCICSample` and `HCICReceipt` match the validator's exact key set.

## 3. Semantics and honesty

- `client_required` trials are not spawned and are not emitted as observed:
  - the hook sets status `client_required` and `observed=false`, and creates no entity;
  - the validator refuses `observed=True`, a non-`client_required` status, `spawned`, `samples`, `doors`, `geometry`, any elapsed time, a mismatching reason, and extra row keys.
  - Some of these refusals are not individually tested (F6).
- Refusals demonstrated by tests or probes: incomplete sentinel, partial status, hook-sha mismatch (receipt, plan, sidecar, init bytes), unknown kind, `clients != 0`, foreign world or build, short denominator, cleanup mismatch.
- Denominator: attempted, completed, inconclusive, client_required. It satisfies attempted = completed + inconclusive and attempted + client_required = planned. It does not include `planned` explicitly; adding it would help.
- No gameplay controller, teleport, door blocking or fake sound is present. The authored `DecreaseHealth` is an explicit diagnostic stimulus (F3 on its worth).
- Bounds hold: entities (1 live, at most 1 per server trial), trials (1 to 100), per-trial wait (1000 to 60000 ms), global cap, watchdog, output (262144 bytes written and read), array sizes, query size. The 100-trial, 60 s render gives `wait_minutes` 106, within the launcher's 5 to 120.
- Default fixture:
  - Position `[6500,0,2500]`, anchor `[6505,0,2500]`, `Land_House_1W01`, `fixture_status=unqualified-candidate`. It is labelled unqualified in the docstring, in each plan trial and in REPORT.
  - It is not surfaced in `validate`/`report` output (F5), and Y=0 makes every default trial inconclusive (F1).
- Proposal for real positions without shipping dumps:
  - The repo already parses stock mapgrouppos in `tools/setup/ce_probe.py:79` (`parse_placements`, `select_placements` with evenly spaced picks). `tools/audit/interior_survey.py` and `tools/setup/interior_measurement_probe.py` already treat stock origins as the live-match radius policy.
  - Add a `survey` subcommand that:
    - reads the operator's local stock `mapgrouppos.xml` (read-only; the path is an argument);
    - picks N classes (for example from `mapgroupproto.xml` groups with usage) and M placements per class via `select_placements`;
    - uses `group pos` as the anchor, with Y recomputed natively by `SurfaceY` (F1);
    - derives the spawn offset from `rpy` yaw, for example 3 m in front of the origin, then relies on the hook's four rays to refuse blocked spawns;
    - emits `trials.json` with `fixture_status` set to a new value such as `stock-derived`, recording the stock file SHA-256 and the selection parameters;
    - never copies the XML. Only the chosen coordinates and class names are emitted, as a few lines of operator-local output kept out of git.
  - Door counts and open/locked states are read at runtime by `GetDoorCount`, so the survey needs no door data.
  - Position-class coverage claims (#18 building, angle and door-state denominators) still need the operator to pick buildings with doors.

## 4. Registration

- `LAUNCHER_ROW`, `PURPOSE_ROW`, `PURPOSE`, `PLAN_NAME` match the rows added in `probe_runtime.py:816-818`, `diagnostic_mission.py:117-120` and `Start-CEProbeServer.ps1:116`. The new registration test checks all four, including the PowerShell table and ValidateSet via `launcher_kind_table` and `launcher_validate_set`.
- Unpatched staging into a temp dir: succeeds (`staged ok; hook d9a39d78...`). No registry patching was needed.
- `launcher_problems(plan, dest, PLAN_NAME)`:
  - `[]` with the plan file held aside, the same convention as `test_weather_probe.py:855-859`;
  - `['runtime files differ from staged_files']` with the plan file in place (by design, F10).
- The other probe suites (`test_ce_probe`, `test_weather_probe`, `test_taped_light_probe`) stay green: 204 tests, OK. This covers the changed `test_ce_probe.py` regex.

## 5. Test strength

See F6 and `mutation_results.txt` / `mutation_pairs.txt`. 23 killed, 52 survived. Of the survivors, V1/V2, V4/V12, E14/E15 and C1/C2 are redundant pairs (both removed is killed). The rest are single-point survivors.

## 6. Focused tests

```
$ PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence tests.unit.test_probe_runtime -v
...
Ran 87 tests in 4.380s

OK
```

```
$ PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_ce_probe tests.unit.test_weather_probe tests.unit.test_taped_light_probe
Ran 204 tests in 8.887s

OK
```

## Other commands run (actual output, abridged)

```
$ git show c40dcd8 --stat   # 7 files, 1116 insertions, 3 deletions
$ python3: render_hook() -> 15760 bytes, sha d9a39d78fc6c6d47dc6e0f0f96b38d34b4f82416b6ab69bac52c4b56356d8854
max plus 1 ; lint_hook(..., explicit_numbers=True) -> [] ; verify_native -> 46 rows
identifier collisions (types only): Building CargoBase DayZInfectedInputController DayZPhysics FileHandle FileMode JsonFileLoader Object PlayerIdentity ZombieBase array bool float int string vector
leading ||/&&: [] ; ternary: [] ; duplicate locals: none
100-trial render: 61053 bytes, lint [] ; wait_minutes 106
staged ok; launcher_problems (plan file present): ['runtime files differ from staged_files']
launcher_problems (plan file held aside): []
time-budget row REFUSED: trial elapsed must be an integer 0..6000
client elapsed 1ms REFUSED: client_required trial cannot be observed
extra sample key accepted: True
limb_damage completed w/o any health change accepted: {attempted 6, completed 6, inconclusive 0, client_required 3}
default-fixture receipt report: denominator attempted 6, completed 6, inconclusive 0, client_required 3 (no fixture flag in output)
git status --short -> ?? scratchpad-review/  (no repository file modified)
```

Mutation harness results are in `mutation_results.txt` and `mutation_pairs.txt` in this directory.

## Suggested fix order

1. F1: terrain Y for the anchor and spawn, with a test that renders the hook and asserts `SurfaceY` is used.
2. F2: relax the inconclusive elapsed bound, with a test.
3. F3(b): validator requires leg health to fall for limb and crawl rows. Decide whether to switch to `ProcessDirectDamage` for crawl.
4. F4: do not rewrite `maxPlayers`, or mark it as a pending experiment.
5. F5: print the fixture status in `validate` and `report`.
6. F6, F7, F8: tighten the tests, force client-row elapsed to 0, require exact key sets.

Runtime acceptance stays pending in all cases; none of the above changes that.
