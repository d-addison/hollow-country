# WP3 round 2 review: infected competence probe (c40dcd8 + 3bf9993, base 73241f6)

Reviewer: Sonnet 5.5, read-only. Wrote only under this directory (`lint.py`, `probe_validator.py`, `mutate.py`,
`hook_default.c`, `mutation_results.txt`). Mutants ran on throwaway copies of tools/ and tests/ (deleted). Staging
probes used a temp dir outside the checkout (the stager refuses paths inside it) and no repository file was edited.

## Verdict: FIX-THEN-MERGE

No P0 or P1. The hook is compile-clean, every native call is verified, registration is registration-only,
and the non-claims are honest. All eight round-1 fixes land in the hook. The receipt validator still does not bind
the placement evidence the F1 fix introduced, so "completed" can be claimed on inconsistent evidence.
Fix list (numbered, all small) is at the end.

## 1. Round-1 fixes F1 to F8

| Fix | Resolved? | Evidence |
|---|---|---|
| F1 terrain Y | Hook: yes. Validator side: PARTIAL | `SurfaceY` replaces both Y before query, rays and spawn (`infected_competence_probe.py:506-511`), query radius 5 m (`:406`), `Game.c:1176` pinned. Mutants H01/H02/H03 killed. But `validate` only checks the surface values are finite (`:888`). See P2-1. |
| F2 time budget | Yes (one strictness risk, P2-3) | Completed rows `<= per_trial+1000`, inconclusive rows `<=` plan cap (`:859-862`). Mutants V02/V03 killed. Hook `HCICObserve` still marks `trial_time_budget` at `:578`. |
| F3 crawl stimulus | Yes, via option (b) | Renamed `crawl_health_only` (`:64`); hook requires the leg to fall (`:593`) and validator does too (`:926-928`). V01 killed. Honest: reason text and limitations say "hit-path not exercised". `limb_damage` and `crawl_health_only` are the same stimulus; stated in limitations (`:953`). |
| F4 maxPlayers rewrite | Yes | `_no_clients_config` is gone. Staged config is source bytes (`:716-717`, `serverDZ.cfg` written verbatim at `probe_runtime.py:739`). S01 killed. Identity abort in the hook stays. |
| F5 fixture status | Yes | `fixture_status_counts` plus limitation line (`:943-947`); stage stderr warning (`:986-988`). S09 killed. |
| F6 test strength | PARTIAL | Many strong guards now, but 4 hook mutants and 6 validator or survey mutants survive (section 5). |
| F7 client elapsed | Yes | `HCICNext` explicit zero (`:622-625`). H06 killed. |
| F8 exact keys | Yes | Document, trial row, sample, door key sets are exact (`:828`, `:847`, `:905`, `:930`). V10/V17 killed. Door `locked`/`opened` bool checked. |

Stock-placement survey: works as claimed (`:179-229`). Fail-closed on missing or ambiguous `rpy`. The yaw convention
(`rpy[2]` in degrees, x += sin, z += cos) and whether stock rows carry yaw in `rpy` rather than an `a=` attribute are
unobserved offline. The spawn offset is explicitly "candidate bearing", so a wrong convention yields an
inconclusive row, not a false pass.

## 2. New correctness findings

### P2-1: validator does not bind the placement evidence; surface-Y substitution can hide a placement failure
- `infected_competence_probe.py:883-888` (authored vs plan only; surface only `_finite`), `:916-923` (position parsed, never compared).
- The hook discards the authored Y (`:508-509`) and spawns on `SurfaceY`. The receipt carries authored Y, surface Y
  and actual positions, but nothing relates them. Demonstrated on a staged plan with a synthetic receipt, all ACCEPTED:
  - every sample position `0 0 0` (nowhere near the spawn);
  - `anchor_surface_y=-5000`, `spawn_surface_y=99999`;
  - authored Y 0 (default fixture) with surface 20/21, by design, but a surveyed upper-floor or roof Y silently becomes terrain with no delta reported.
- Scenario: a spawn that fell through the world, snapped to a roof or was displaced by `ECE_PLACE_ON_SURFACE`
  still yields a `completed` row. The substitution is the exact kind of silent correction the project forbids.
- Fix: for completed rows require `sample[0].position` x/z within ~2 m of the plan spawn and y within ~3 m of
  `spawn_surface_y`; bound surface Y to the F1 range (-100..2000); and add per-trial `|authored - surface|` to
  `report` (flag a delta above a threshold when `fixture_status` is not `unqualified-candidate`).

### P2-2: hook no-target control and several hook constants are unpinned by tests
- Survivors H18 (removing `if (sampleRow.target) return false;`, `:472-473`), H05 (`:578` budget +1000), H07 (`:593` `>=` vs `>`), H17 (ray height `:428`).
- Without H18 the hook would record `completed` while a target is present, and the validator would then refuse the
  whole receipt (V15 killed) instead of counting one inconclusive. That is the F2 class of contradiction.
- Fix: add method-scoped assertions as in `test_hook_cleanup_ownership_guards_and_bounds_structure`.

### P2-3: strict completed lower bound is unobserved engine timing
- `:894-895`: `row['elapsed_ms'] < per_trial_ms` refuses a completed row.
- `elapsed_ms` is `GetGame().GetTime() - m_TrialBegin` (`:625`), but the delay is enforced by `CallLater` (`:568`). The call
  queue and `GetTime` are separate clocks and frame-quantised. A row at 4990 ms against a 5000 ms delay would make the
  whole first real run unvalidatable. It fails closed, but it is the same class of defect as round-1 F2.
- Fix: lower bound `per_trial_ms - 250` (or about 90 percent), documented as an unobserved-timer allowance. The
  upper bound has the same race, because `HCICObserve` and `HCICNext` each call `GetTime` (`:577`, `:625`); allow a
  little slack (+1100 is already used for the plan cap).

### P3 items
- P3-1: `reason` is not enumerated (`:870-871` only checks a 1..256 char string). I accepted a completed row with
  reason "totally fabricated reason", an inconclusive `trial_time_budget` row at 10 ms, `footprint_ray_hit` with all-zero rays and
  `structure_missing...` with `spawned=1` and samples. Fix: completed requires `two_endpoint_samples_only`; inconclusive reason must be in the
  hook's set, with simple cross-checks (ray hit bit for `footprint_ray_hit`, elapsed over the budget for `trial_time_budget`).
- P3-2: total elapsed across rows and `sample.mind` bounds are weak. `mind` is `-1..100` only; row sums are not checked against the plan cap.
- P3-3: `stock-derived` provenance is self-declared (`:237-244`): `stock_sha256` is never re-checked against an XML, and a hand-written JSON can carry the label (S11 survived).
  The plan limitation line covers only `unqualified-candidate`; stock- and operator-derived rows are still candidates
  (3 m bearing, unobserved convention). Add a line for those.
- P3-4: survey `float(...)` of an `rpy` attribute and `node.get('pos')` are covered by earlier validation, but an
  `AttributeError` would escape `main` (`:997` catches OSError, ValueError, KeyError, TypeError). Practically unreachable.

## 3. Enforce hook compile rules (default hook rendered to `hook_default.c`)
- `rt.lint_hook(..., native_types=<1.30 cache>, explicit_numbers=True)` returns `[]`; `rt.max_statement_plus` is 1 (limit 8).
- No ternary, no line starting with `||` or `&&` (my own regex over the rendered hook: nothing flagged).
- Loops bounded: `scanIndex < nearby.Count() && scanIndex < 128` (`:411`), `rayIndex < 4` (`:429`), `doorIndex < doorCount && doorIndex < 16` (`:547`). No `while`.
- Out args declared before the call: `worldName`, `buildName` (`:385-388`), `contactPoint`, `contactDirection`, `contactComponent` (`:439-441`), `structureName`, `anchor`, `spawnPoint` (`:494-497`), `outputData`, `outputError` (`:644-646`), `identities` (`:343`).
- No duplicate locals across sibling scopes: `legHealth` (Step) vs `currentLegHealth` (Observe); loop locals are per method.
  No local named like an engine type (`structure`, `hit`, `clear`, `chosen`, `candidate`, `nearby`).
- Explicit `ToString` everywhere (`:467-468`, `:470`, `:506-511`); `"status=" + outcome` is string + string. Enum members:
  `FileMode.READ/WRITE`, `CALL_CATEGORY_SYSTEM`, `ECE_PLACE_ON_SURFACE|ECE_INITAI` are qualified or constants.
- Native signatures checked in `~/.cache/hollow-country/native-scripts/scripts-1.30.164289/` (all match the line pinned in `NATIVE`):
  - `Game.c:703` `CreateObjectEx(string, vector, int, int=...)`, `:705` `ObjectDelete`, `:930` `GetObjectsAtPosition3D(vector,float,out array<Object>,out array<CargoBase>)`, `:1166` `GetPlayerIndentities(out array<PlayerIdentity>)`, `:1176` `float SurfaceY(float,float)`, `:1535` `int GetTime()`, `:932` `GetWorldName(out string)`, `:942` `GetVersion(out string)`.
  - `Object.c:994` `GetHealth(string,string)`, `:1034` `DecreaseHealth(string,string,float)`.
  - `DayZInfected.c:107` `GetInputController`, `DayZInfectedInputController.c:9` `GetMindState`, `:10` `GetTargetEntity`, `ZombieBase.c:1090` `IsCrawling`.
  - `Building.c:31` `GetDoorCount`, `:34` `IsDoorOpen`, `:55` `IsDoorLocked`; `DayZPhysics.c:199` `RaycastRV(..., out contactPos, out contactDir, out int)`.
  - `EnConvert.c:30/115/138` float and vector `ToString` overloads; `JsonFileLoader.c:85` `MakeData(T, out string, out string, bool)`; `CentralEconomy.c:38`, `:18`.
- `anchor[1].ToString()` and `v[1] = GetGame().SurfaceY(...)` follow shapes already used in `taped_light_probe.py:283` and
  `death_selection_probe.py:538-539`, `fuel_siphon_probe.py:651`.

## 4. Registration changes
- `probe_runtime.py` (one `LAUNCHER_PROBES` row), `diagnostic_mission.py` (one `_PURPOSES` row, same `hook=` contract as weather), `Start-CEProbeServer.ps1` (`ValidateSet` and one `$probes` entry): registration only.
  No existing row or branch edited; the ps1 has no per-kind branching beyond the table (`$Kind` appears only at `:10`, `:114-118`, `:125-128`, `:194`, `:217`).
- Staged plan lists the hash sidecar in `staged_files` (`:729-732`), so the launcher's "unexpected file" scan passes.
  `wait_minutes` (`:743-744`) matches the watchdog (`start + cap + 10000`) and stays below the launcher's 120 minute cap for 100 trials at 60 s.
- `test_ce_probe.py` and `test_probe_runtime.py` edits only widen the expected table and add one registration test. No regression.

## 5. Tests and mutation

```
$ cd /code/hc-worktrees/wp3-integ && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence tests.unit.test_probe_runtime tests.unit.test_ce_probe tests.unit.test_script_syntax
Ran 164 tests in 10.407s

OK
```

55 mutants on scratch copies, run against `tests.unit.test_infected_competence` (`mutation_results.txt`). 43 killed, 12 survived.

Killed: V01-V12, V15-V20, V22-V24 (validator bounds, key sets, cleanup, sidecar, client-row fields), H01-H04, H06, H08-H16
(SurfaceY, radius, ambiguity, cleanup, ray count, leg guard, identity abort, cap, door budget, ECE flags), S01, S02, S06-S10, S12.

Survived (12):
- V13 `len(samples) != 2` weakened to `< 1`: genuine gap, no test for a one-sample completed row.
- V14 version lookbehind removed (`21.30.164289` style): genuine P3 gap.
- V21 staged==source config check removed: near-equivalent, since the on-disk file is still hashed against the plan; only a self-consistent plan edit differs.
- H05, H07, H17, H18: genuine, see P2-2.
- S03 `sorted()` of classes removed: equivalent only when the XML order is already sorted; otherwise a determinism gap.
- S04 offset max 10 to 1000, S05 ambiguous-rpy check, S11 provenance required, S13 start-delay lower bound: genuine P3 test gaps.

## 6. Honesty of non-claims
Good. `runtime_acceptance: PENDING` in every report, the docstring says defaults are unqualified, the limitations list "synthetic/offline validation does not establish DayZ behavior", "hit-path not exercised; no crawl-transition inference", "two endpoint samples only", and that LOS, wall attacks and audibility need two-client trials.
Nothing claims acceptance. Remaining honesty gap is P3-3 (stock-derived and operator-surveyed rows are not flagged as candidates in the report).

## Numbered fix list (FIX-THEN-MERGE)
1. (P2-1) Bind placement evidence in `validate` (`:883-888`, `:916-923`): completed sample[0] position within tolerance of plan spawn x/z and of `spawn_surface_y`; surface Y within -100..2000; report `|authored - surface|` per trial and warn when a non-default fixture's delta is large.
2. (P2-2) Add hook-structure tests pinning `if (sampleRow.target) return false;`, `elapsed > PER_TRIAL + 1000`, `currentLegHealth >= m_LegBefore`, and the ray offset constants.
3. (P2-3) Relax the completed lower bound to allow clock skew (and mention the upper-bound race) at `:894-895` and `:859`, with a test at the boundary.
4. (P3-1) Enumerate allowed reasons per status; cross-check footprint and time-budget reasons.
5. (P3) Add a one-sample completed-row test, a `21.30.164289` version test, offset-range and rpy-ambiguity tests, and a limitation line for stock/operator-derived fixtures.
