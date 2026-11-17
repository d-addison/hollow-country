# B04 WP3 — infected native competence/contact/injury probe

Source/package tooling authored; runtime acceptance and production enablement **PENDING**.
No engine, Wine, PowerShell, git command or subagent was used. All staging occurred in
TemporaryDirectory fixtures under `/tmp`; no writes under `/mnt/d`. No native source,
assets, credentials, keys, local runtime or full vanilla dump added.

## Changed files and scope

- `tools/setup/infected_competence_probe.py`: new standard-library stager, generated native
  mission hook, native-cache evidence verification and `validate` / `report` commands.
- `tests/unit/test_infected_competence.py`: 13 offline behavioral/structural tests; every
  runtime/receipt fixture is explicitly synthetic.
- `scratchpad-review/wp3/REPORT.md`: this report.
- `.banso-writer/commit-message`: requested writer commit message (not committed by Banso).

`HCInfectedNative.c` unchanged: public native `ZombieBase.IsCrawling()` already supplies
read-only state. No shared modules, launcher, addon files, BDD bindings or spec files edited.
The shared registry dictionaries are monkeypatched **only inside tests**. Production staging
never registers itself and fails loudly before creating a destination if either real Python
registration is absent/mismatched. The PowerShell registration must also be integrated by WP1.

Read `AGENTS.md`, the runtime implementation contract, the #18/#19 acceptance/process rows,
Native API evidence/blockers and WP3 in the read-only B04 audit. The requested local
`docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/spec.md` are absent. Read the
audit-identified design copies under `/code/dayzsa_mods/docs/`, including its feature plan.
Those external copies are design input, not verified history or runtime evidence. This
source work follows FR-008, FR-011, NFR-001/002/003/006, AC-007 and T018/T019. WP1 retains
spec/plan/tasks/BDD/evidence integration; none of #18/#19's runtime criteria is accepted.

## Actual RED / GREEN

Initial command, run after writing tests and before implementing the module:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence -v
ImportError: cannot import name 'infected_competence_probe' from 'tools.setup' (unknown location)
Ran 1 test in 0.000s
FAILED (errors=1)
```

After initial implementation: `Ran 10 tests in 0.866s` / `OK`.
Then additional behavioral rejection cases were written before validator tightening:
`test_completed_records_require_kind_specific_evidence_and_pinned_build` failed all seven
counterexamples (wrong world/build, boolean client count, missing geometry, premature completion,
missing door states, extra client observation field). Actual result:
`Ran 13 tests in 1.146s` / `FAILED (failures=7)`.

Final focused GREEN:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_competence -v
Ran 13 tests in 1.500s
OK
```

Required regression commands, both exit 0:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit
Ran 2374 tests in 76.141s
OK (skipped=1)

python3 -B -m tools.validate.bdd
Ran 1276 tests in 35.137s
OK (skipped=1)
Bound offline scenarios: 61; runtime acceptance: NOT EXECUTED
```

The existing BDD command executes its current bindings; no new WP3 scenario binding is claimed.
Expected error-path messages from existing CLI tests were printed during both suites.

## Trial table

`N/` below means the exact read-only root
`/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`.
All nine kinds appear in the default plan. Each server trial uses at most one owned infected;
all three client trials are emitted only as `status=client_required`, `observed=false`, zero
entities/time and empty observation arrays, with the explicit reason in the plan and receipt.

| Kind | Support state | Native APIs (file:line) | What the hook can observe |
|---|---|---|---|
| `spawn_lifecycle` | server_observable | N/3_Game/Global/Game.c:703 CreateObjectEx, :705 ObjectDelete; N/3_Game/Entities/Object.c:287 GetPosition, :517 IsAlive | Spawn return/cast, two living state/position samples, deletion call accounting. Not a residual census or CE lifecycle proof. |
| `mind_no_target` | server_observable | N/3_Game/Entities/DayZInfected.c:107 GetInputController; N/3_Game/Entities/DayZInfectedInputController.c:9 GetMindState, :10 GetTargetEntity | Two endpoint mind states and target-presence flags; target presence makes the control inconclusive. No fresh visual provenance is inferred. |
| `door_state` | server_observable | N/3_Game/Global/Game.c:930 GetObjectsAtPosition3D; N/3_Game/Entities/Object.c:467 GetType; N/3_Game/Entities/Building.c:31 GetDoorCount, :34 IsDoorOpen, :55 IsDoorLocked | Existing nearby building's indexed open/locked states; neither mutates a door nor establishes infected contact, opening or bashing. |
| `footprint_geometry` | server_observable | N/3_Game/Global/DayZPhysics.c:199 RaycastRV; N/1_Core/proto/EnMath3D.c:18 Vector | Four 0.6m rays at authored spawn height +0.8m in default view geometry. Records hit bits and denies spawning if any ray hits. Not a complete collision capsule/clearance or player LOS test. |
| `limb_damage` | server_observable | N/3_Game/Entities/Object.c:994 GetHealth, :1034 DecreaseHealth; N/4_World/Entities/Creatures/Infected/ZombieBase.c:1090 IsCrawling | Before/after LeftLeg and RightLeg health, alive state and crawling after one LeftLeg health decrease bounded by initial health (0 < health <= 10000). No repeated damage. |
| `crawl_transition` | server_observable | Same injury APIs; native interpretation: N/4_World/Entities/Creatures/Infected/ZombieBase.c:811 HandleCrawlTransition, :826 EvaluateCrawlTransitionAnimation, :998 hit-path evaluation | Before/after IsCrawling following the same one-shot DecreaseHealth stimulus. Does **not** call hit/crawl handlers or force an animation. No crawl is an observation under this stimulus, not proof of a native hit/crawl defect. |
| `player_los_chase` | client_required | None executed | Requires a real connected player and paired LOS/chase observations; server-only has no player target. Never observed here. |
| `player_wall_attack` | client_required | None executed | Requires real player damage/attack observations through walls with two clients. Never observed here. |
| `audible_pursuit` | client_required | None executed | Requires two clients hearing pursuit on surfaces, at distance and through occlusion. AI noise metadata would not prove human audibility. Never observed here. |

## Bounds, artifacts and receipt interpretation

- 1..100 total trial records; default 9 (6 attempted server trials, 3 client-required exclusions).
- Start delay 5..600s, default 30s; per-trial wait 1000..60000ms, default 5000ms.
  A server trial exceeding wait +1000ms is inconclusive. Global cap is
  `trial_count * (per_trial_ms + 1100) + 30000`; a watchdog fires after start +cap +10000ms.
  Launcher wait is computed to include 3 boot minutes and remains within its 5..120 limit.
- One live owned entity maximum; no entity created for client exclusions. Normal next-trial,
  early exits, watchdog and mission shutdown call the same cleanup routine. Every owned
  CreateObjectEx return is retained as Object even if ZombieBase cast fails, then ObjectDelete
  is called. Counts represent delete calls; native disappearance still needs verification.
- Structure query radius 2m around the authored structure anchor; ambiguous/missing matches or
  more than 128 returned objects/proxy cargos yield inconclusive. Consumer loop <=128, doors
  <=16, rays exactly 4, samples <=2. Underlying native query allocation/call duration is not
  preemptible by script. No broad world/player scan, fake target or scripted sound.
- Hook output JSON is capped at 262144 bytes before writing; validation uses the same bounded
  read. It writes `$profile:HCInfectedCompetence/observations.json` then `complete.txt` last.
  Failed serialization/file opening or oversize output never writes a complete sentinel.
- The staged config changes exactly one literal `maxPlayers` to 0 (duplicates/nonliteral
  settings refused), records original/treated hashes and preserves the source runtime. Native
  identity-count checks abort if a client is present. Actual engine no-client admission with
  this config remains a native smoke-test obligation, not offline-proven behavior.
- The authored `$mission:hc-infected-hook-sha.txt` sidecar contains the actual hook SHA-256.
  The hook reads exactly 64 bytes and echoes it into the JSON. This avoids embedding a hash
  of itself. The staged mission manifest and plan inventory include/hash the sidecar.
- Validator regenerates the exact hook from the plan; checks actual hook SHA/size, sidecar,
  staged init suffix and init hash, no-client config, sentinel, exact trial identities/kinds,
  support states, observations, time/array bounds, finite samples and cleanup accounting.
  Unknown kinds, duplicate JSON keys, incomplete denominators, foreign world/build and any
  client-required observation are refused. Hashes bind bytes, not a malicious operator's
  authenticity or runtime provenance.
- `completed` means the observation procedure supplied its two endpoint samples and required
  kind-specific data; it is **not** a competence verdict. `attempted` counts each server trial
  initiated, including ones inconclusive before spawn. Therefore attempted = completed +
  inconclusive, and attempted + client_required = planned. A synthetic example validated in
  the focused test reports attempted=6, completed=5, inconclusive=1, client_required=3.

## Exact coordinator registration lines

Add to `tools/setup/diagnostic_mission.py::_PURPOSES`:

```python
'infected-competence-probe': ('disposable-infected-competence-probe', None,
                             ["server mode", "fresh storage and profiles", "no clients",
                              "inspect observation completeness separately from startup"]),
```

Add to `tools/setup/probe_runtime.py::LAUNCHER_PROBES`:

```python
"infected-competence-probe": ("infected-competence-probe-plan.json", "HCInfectedCompetence", "observations.json"),
```

Replace the launcher's current ValidateSet line in `tools/setup/Start-CEProbeServer.ps1` with:

```powershell
[ValidateSet('ce-probe', 'taped-light-probe', 'weather-probe', 'interior-sampler', 'infected-competence-probe')]
```

Add to its `$probes` table:

```powershell
'infected-competence-probe' = @{ Plan = 'infected-competence-probe-plan.json'; Directory = 'HCInfectedCompetence'; Output = 'observations.json' }
```

No launcher edits were made, and no launcher was invoked. Coordinator should add a dedicated
WP3 offline BDD binding under its shared ownership and retain missing runtime acceptance.

## Default staging hook

Default hook SHA-256: `d9a39d78fc6c6d47dc6e0f0f96b38d34b4f82416b6ab69bac52c4b56356d8854`

Default hook bytes: 15760. Maximum binary `+` per statement: 1 (limit 8).
Lint ran with `explicit_numbers=True` and all engine type names read from the pinned cache.
Default staging was exercised only in synthetic temporary runtimes with explicit registry
patches. Output receipt was synthetic. No actual default native run exists.

After coordinator integration, stage only with:

```text
python3 -B -m tools.setup.infected_competence_probe stage --source-runtime STOCK_RUNTIME --destination FRESH_RUNTIME --native-scripts /home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289 --trials-json SURVEYED_TRIALS.json
python3 -B -m tools.setup.infected_competence_probe validate FRESH_RUNTIME
python3 -B -m tools.setup.infected_competence_probe report FRESH_RUNTIME
```

`--trials-json` is a list with the shape returned by `default_trials()`; keep kind/support/reason
canonical, use unique plain IDs and vanilla structure class names, and replace both positions
with surveyed coordinates. Positions are XYZ triples; spawn must be within 20m of anchor.
`fixture_status` is either `unqualified-candidate` or `operator-surveyed`; operator labels
are not authenticated survey receipts. Omitting the input uses a clearly unqualified
Land_House_1W01 candidate at spawn [6500,0,2500], anchor [6505,0,2500]. These are **not known
measured building coordinates** and a default run can legitimately be entirely inconclusive.
Missing/ambiguous runtime class matching is never upgraded to coverage. The default fixture
is a staging example, not the #18 multi-building/angle/door-state denominator.

## Remaining gaps / dispositions

1. WP1 must add the four exact registrations above; production staging deliberately refuses
   missing Python rows. Current tests patch Python rows and do not certify PowerShell integration.
2. No DayZDiag compilation or engine execution, native config admission, residual deletion,
   normal PBO/server regression, client/network/audio/visibility proof or measured 3–6-player
   budget was performed. Native hung-call/crash cleanup depends on outer process teardown.
3. Need surveyed real vanilla building/door/spawn fixtures, broad building/angle/open/closed/
   locked controls, approximately 100 practical trials, repeated paired vanilla/candidate
   runs, continuous stuck/path/command observations and current-hook coverage. Two endpoint
   samples can miss intervening state transitions.
4. This harness uses native classes with no HC PBO. It does not exercise the candidate HC
   contact guard, voice bridge, route release or other current addon callbacks. Those remain
   explicitly unqualified in #18/#19. No contact-driven opening/bashing bridge was found in
   the audit; door reads cannot justify authoring a door controller or claiming a correction.
5. One-shot LeftLeg DecreaseHealth is not ProcessDirectDamage/EEHitBy. Right-leg damage,
   actual hit/ammo callbacks, fatal injury/crawl dynamics and two-client animation/attack
   effects remain to be measured. Both legs' current health is recorded without fabricating
   additional injury behavior. No speculative injury or competence correction is shipped.
6. Client-required LOS/chase, through-wall player attacks and audible pursuit are deferred
   with explicit reasons. Missing visual provenance, physical door contact and audibility
   are not inferred from geometry rays, retained targets or native AI noise.
7. Full-content compatibility, alternate/modded locks, source/build/artifact-to-native-run
   authentication, the no-regression control and calibrated performance remain coordinator
   evidence work. No requirement is removed or marked accepted by this source deliverable.

## Complete called-API citation ledger

Each row below was checked at its exact cached line by `verify_native`; no online API
substitute was used. Declarations/constants used by the hook are included. Crawl/hit
interpretation-only citations are in the trial table and are not hook calls.

| API / surface | File:line relative to N/ |
|---|---|
| `GetGame` | `2_GameLib/gameLib.c:4` |
| `OnInit` | `5_Mission/mission/missionServer.c:85` |
| `OnMissionFinish` | `3_Game/gameplay.c:702` |
| `IsServer` | `3_Game/Global/Game.c:1120` |
| `GetPlayerIndentities` | `3_Game/Global/Game.c:1166` |
| `GetTime` | `3_Game/Global/Game.c:1535` |
| `GetCallQueue` | `3_Game/Global/Game.c:1550` |
| `GetWorldName` | `3_Game/Global/Game.c:932` |
| `GetVersion` | `3_Game/Global/Game.c:942` |
| `CallLater` | `2_GameLib/tools.c:61` |
| `CreateObjectEx` | `3_Game/Global/Game.c:703` |
| `ObjectDelete` | `3_Game/Global/Game.c:705` |
| `GetObjectsAtPosition3D` | `3_Game/Global/Game.c:930` |
| `GetPosition` | `3_Game/Entities/Object.c:287` |
| `GetType` | `3_Game/Entities/Object.c:467` |
| `IsAlive` | `3_Game/Entities/Object.c:517` |
| `GetHealth` | `3_Game/Entities/Object.c:994` |
| `DecreaseHealth` | `3_Game/Entities/Object.c:1034` |
| `GetInputController` | `3_Game/Entities/DayZInfected.c:107` |
| `GetMindState` | `3_Game/Entities/DayZInfectedInputController.c:9` |
| `GetTargetEntity` | `3_Game/Entities/DayZInfectedInputController.c:10` |
| `IsCrawling` | `4_World/Entities/Creatures/Infected/ZombieBase.c:1090` |
| `GetDoorCount` | `3_Game/Entities/Building.c:31` |
| `IsDoorOpen` | `3_Game/Entities/Building.c:34` |
| `IsDoorLocked` | `3_Game/Entities/Building.c:55` |
| `RaycastRV` | `3_Game/Global/DayZPhysics.c:199` |
| `Cast` | `1_Core/proto/EnScript.c:94` |
| `Count` | `1_Core/proto/EnScript.c:380` |
| `Get` | `1_Core/proto/EnScript.c:399` |
| `Insert` | `1_Core/proto/EnScript.c:407` |
| `Vector` | `1_Core/proto/EnMath3D.c:18` |
| `ToString` | `1_Core/proto/EnConvert.c:30` |
| `ToString` | `1_Core/proto/EnConvert.c:115` |
| `ToString` | `1_Core/proto/EnConvert.c:138` |
| `Length` | `1_Core/proto/EnString.c:199` |
| `FileExist` | `1_Core/proto/EnSystem.c:397` |
| `OpenFile` | `1_Core/proto/EnSystem.c:417` |
| `ReadFile` | `1_Core/proto/EnSystem.c:425` |
| `CloseFile` | `1_Core/proto/EnSystem.c:443` |
| `FPrint` | `1_Core/proto/EnSystem.c:462` |
| `FPrintln` | `1_Core/proto/EnSystem.c:481` |
| `MakeDirectory` | `1_Core/proto/EnSystem.c:525` |
| `MakeData` | `3_Game/tools/JsonFileLoader.c:85` |
| `$mission:` | `5_Mission/GUI/ScriptConsole.c:72` |
| `ECE_PLACE_ON_SURFACE` | `3_Game/CE/CentralEconomy.c:38` |
| `ECE_INITAI` | `3_Game/CE/CentralEconomy.c:18` |
