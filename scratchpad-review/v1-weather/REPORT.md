# #35 v1 weather, lighting and atmosphere

Source/package implementation authored on `hc/v1-weather` from `1ae1be9`.
**Runtime acceptance and production qualification: PENDING.** No DayZ, Wine,
client connection, network, signing, Git staging, commit or push was performed.
The generated PBO was temporary, private, unsigned and removed after verification.

## Inputs and confined Banso spec / plan / tasks

Read AGENTS.md, README.md, MODULE_STATUS.md, RUNTIME_IMPLEMENTATION_CONTRACT.md,
the atmosphere generator/tests, weather report/probe, alert chain, fuel action,
and the installed 1.30.164289 native interfaces. The supplied #35 brief and active
user decisions are the specification for this writer. `gh issue view 35` was not
run because this run prohibits network access. `docs/SPECIFICATION.md` and
`docs/specs/001-survival-overhaul/spec.md` do not exist in this checkout.
`HCFuelSiphon.c` exists but has no `HCFuelSiphonQualification` in this revision;
the requested false qualification / one-probe experimental marker behavior is
implemented explicitly. No absent experiment is treated as accepted.

This is a dispatched Banso writer, with no selected feature/lifecycle artifacts.
The Banso CLI skill directs dispatched workers to follow their task contract and
leave orchestrator lifecycle commands alone. This confined ledger retains the
specification, plan and task traceability without editing unowned `.banso` or
documentation files. Source completion does not close engine acceptance tasks.

| Requirement / acceptance intent | Implementation and offline checks | Task status |
| --- | --- | --- |
| W1: supported, deterministic Chernarus weather; stronger morning valley fog; storm travel conditions and post-storm calm | Chernarus world-data override, native forecasts and volumetric fog; binary32 authored-policy and native-collaborator tests | Source DONE; DayZDiag / normal-server / balance PENDING |
| W2: one owner for every phenomenon, respecting XML/storage | Reserved script-delegation profile, canonical disabled XML root, bounded one-time server check, foreign mission-weather/freeze refusal | Source DONE; engine precedence/restart PENDING |
| W3: supported darker nights/interiors with server authority | Native synchronized gameplay DTO: dark-night preset 1 and disabled personal light; no custom renderer | Source DONE; two-client visibility/accessibility PENDING |
| W4: weather attenuation changes only relay range | One additional alert-chain radius assignment; native source-position sample mapped through pure bounded policy | Source DONE; synthetic integration GREEN; native chain admission/audio PENDING |
| W5: default-on preference with honest admission | Exactly one settings field; `Qualified()` remains false; one-process local opt-in marker and explicit EXPERIMENTAL / PENDING / BLOCKED logs | Source DONE; shared settings/fixture integration OPEN |
| W6: retain seasonal environment and native systems | Existing native/operator 12-month temperature curves and daylight logic remain in control | Retained; seasonal gameplay validation PENDING |

Plan executed: inspect native contracts; write and execute failing behavior tests;
add pure scalar policy; add admission and native world hooks; connect radius-only
attenuation; align the generator; execute focused, package, full unit and BDD
checks; leave runtime acceptance as an explicit subsequent local-server task.

## Files

- `mods/HollowCountry/scripts/4_World/Weather/HCAtmospherePolicy.c`: pure finite
  binary32-testable weather, fog, transition and relay arithmetic; no loops.
- `.../HCAtmosphereQualification.c`: server/core/preference/map admission,
  false production qualification, one-process marker probe and bounded delegated
  XML check. Reads at most 65,537 bytes and rejects beyond 65,536.
- `.../HCChernarusAtmosphere.c`: `modded class ChernarusPlusData`, default settings,
  native forecast ownership, volumetric fog and server gameplay lighting data.
- `.../HCAtmosphereLifecycle.c`: extends authored `HCServer.Start`, calls super
  first, then starts the admitted Chernarus world instance before normal joins.
  No new HCModule or registry entry is needed; the registry remains untouched.
- `.../HCAtmosphereRelay.c`: samples the native noise system at the emission
  position; disabled/unadmitted is an identity operation with no noise sampling.
- `mods/HollowCountry/scripts/4_World/Infected/HCAlertChain.c`: **one added line**
  immediately after the existing radius calculation. Nothing else changed.
- `mods/HollowCountry/scripts/3_Game/HCSettings.c`: **only** the single field
  `bool EnableAtmosphere = true;` added.
- `tools/package/atmosphere.py`: reserved `hc-v1-script` profile and `v1-script`
  CLI; explicit per-phenomenon ownership metadata and validation.
- `tests/unit/test_atmosphere.py`, `test_v1_weather.py`,
  `test_v1_weather_alerts.py`: explicit synthetic fixtures, authored scalar and
  hook execution, delegation CLI/metadata checks and actual alert processing.
- `tools/validate/bdd.py`: weather-row comment documents that its existing
  `test_atmosphere.py` binding also executes the v1 suites through `load_tests`.
  Scenario names/steps and all other rows are unchanged.
- This report and actual test/build outputs under `scratchpad-review/v1-weather`.
  `.banso-writer/commit-message` supplies the orchestrator's commit message.

There are no cfgweather/cfggameplay templates under `mission/hollow-country` in
this revision. None were invented or added. The delegated XML candidate is built
from an operator's pinned local stock mission and installed only in a later run.
Older generated reports without ownership metadata must be regenerated before
using this version's validator; hashes alone still do not establish provenance.

## Ownership and provisional profile

| Phenomenon / data | Owner after admission | When admission fails |
| --- | --- | --- |
| Overcast, normalized fog, rain, wind magnitude, wind direction, snowfall, storm thresholds | Chernarus script through native Weather APIs; XML root is disabled and non-reset | Original Chernarus/native code; no authored setters |
| Volumetric distance/height density and height bias | Script `CalculateVolFog`, only if native world config enables it | Original Chernarus/native behavior |
| Lighting preset and personal light restriction | Server gameplay DTO, distributed/consumed by native synchronization | Existing server/native settings |
| Temperature/month/daylight/environment curve | Existing native Chernarus + operator cfgGameplay curve | Same native systems |
| Supplementary alert relay range | Existing base radius times the authored native-environment scale | Exact existing base radius |

The reserved profile requires ChernarusPlus, `enable=false`, `reset=false`, and
empty XML overrides. It preserves every phenomenon subtree from the source and
canonicalizes only the disabled root serialization. A pinned source can be
reconstructed byte-for-byte. The script requires that canonical prefix at byte
zero, so comments containing disabled flags cannot masquerade as delegation.
This is a bounded ownership check, not a general XML parser or authenticated
manifest loader. The generator performs complete structural candidate validation.
Legacy explicit XML profiles still work for XML experiments; the v1 script
rejects them as owners and does not compete with them. Native MissionWeather or
frozen-controller flags also block startup. Engine precedence remains PENDING.

The two-hour native server-weather-clock cycle is deterministic: fair weather
for 0–2,700 s (cloud 0.35), gathering cloud for 2,700–3,600 s (0.72), storm cloud
for 3,600–5,400 s (0.95), then a calm forecast window for 5,400–7,200 s (0.25).
Nonstorm nights (before 05:00/from 20:00) use cloud 0.55, still below rain 0.65.
Storm threshold is 0.85; thunder timeout 90 s. Rain targets 0/0.25/0.85 according
to actual cloud, with wind targets 4/8/14 m/s and a hard 16 m/s envelope.
Cloud/direction forecasts transition for 300 s and hold for 300 s; rain/wind
transition for 180 s and hold for 120 s; normalized fog transitions for 300 s.
Snow remains zero on Chernarus. The calm window is a forecast window, not a
promise of instantly cleared skies: cloud descent, rainfall decay and native
callback timing must be measured. It creates travel windows, not a new calendar
weather simulator. Native initial/saved conditions interpolate into this profile.

Morning weight ramps from zero at 05:00 to one at 07:00 and back to zero at
09:00. Normalized fog is 0.04–0.24 (limit 0.25). Volumetric distance density is
`(0.015 + 0.04*morning + 0.01*cloud) * (1 - boundedWind/20)`, bounded by
0.003–0.065; height density 0.95; height bias 50–90 m. Wind is bounded 0–16 m/s
for this calculation. Transition requests are finite and bounded 0–900 s.
Missing volumetric support produces a PARTIAL diagnostic and retains normalized
fog; it never fabricates renderer support. These are provisional design limits,
not measured visibility, accessibility or performance budgets.

Native `NoiseSystem.GetEnvironmentNoiseReduction` returns **absolute noise
strength reduction**, not a normalized distance multiplier. Our explicit range
policy is `max(0.35, 1/(1+clamp(reduction,0,2)))`: scale is always **0.35–1.0**.
Negative finite reduction gives 1.0; missing/nonfinite readings use 0.35.
Invalid base radii return zero. No setting enlarges a valid base range. The
existing `15 * emission.Clue.Strength` remains the base. Sampling uses the
frozen `emission.Clue.Origin`, even if the emitter subsequently moves. TTL,
strength, hops, provenance, work limits, root/recipient caps, geometry checks,
cooldowns, native sound and alert qualification are unchanged. This mapping is a
balance policy, not a claim of acoustic unit conversion or native audibility.

## Actual RED / GREEN and integration checks

Commands ran from the worktree with Python standard-library tooling only.

- `RED-01.txt`: initial `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest
  tests.unit.test_atmosphere -v` ran 24 tests and failed with 2 failures / 7 errors:
  missing v1 CLI/profile helper, setting and source policy/admission hooks.
- `HARNESS-01.txt`: intermediate translator fixture rejected an inline `else`;
  the mechanical translator was corrected without changing policy behavior.
- `GREEN-01.txt`: atmosphere + syntax command, 38 tests passed.
- `RED-02-native-shapes.txt`: actual authored-source lint failed on an escaped
  quote. Replaced it with native `int.AsciiToString`, keeping each statement at
  at most five `+` operations. Native shapes subsequently passed.
- `GREEN-02.txt`: focused atmosphere/syntax/probe/report/infected-completion
  command, 246 tests passed.
- `RED-03-map-admission.txt`: actual behavior admitted an unsupported-world
  collaborator. Added a one-time native map check to the common gate, before
  marker probing; relays also stay inactive outside ChernarusPlus.
- `GREEN-03.txt`: the same 246 focused checks passed after map admission.
- `HARNESS-02.txt`: the new relay integration fixture initially passed a Python
  list where authored code requires the native array `Count()` method. Replaced
  it with the existing explicit synthetic Array adapter.
- `GREEN-final.txt`: final focused command:
  `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_atmosphere
  tests.unit.test_script_syntax tests.unit.test_weather_probe
  tests.unit.test_weather_report tests.unit.test_infected_completion -v`.
  **249 tests passed.** It includes the new actual alert-body
  tests with explicit native collaborators, gate/ownership/fog/lighting checks,
  binary32 policies and installed-source statement/prototype checks.
- `PACKAGE.txt`: temporary unsigned deterministic PBO build and verification;
  100 entries, prefix `HollowCountry`, all five new authored script payloads
  verified. SHA-256:
  `8fdc42a0e98413425c0d576fe59c7cca8b5a26d94192d9a3a8d957e40de575f0`.
  This establishes source packaging only, not compilation or signing.
- `FULL-UNIT-final.txt`: required final
  `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit`.
  **2,581 tests, 1 failure, 7 errors, 1 skipped.** The failure is the shared
  seven-flag contract; the seven errors are the unextended alert fixture below.
- `BDD-final.txt`: required final `python3 -B -m tools.validate.bdd`.
  **1,321 tests, 2 failures, 1 error, 1 skipped; 61 bound scenarios.** Both
  failures are repeated executions of the same shared settings contract. The
  error is the unrelated child-process race described below.
  Earlier `FULL-UNIT.txt` / `BDD.txt` are retained as intermediate attempts;
  those full suites overlapped later source/test edits and are not final evidence.

Known integration work outside this writer's ownership:

1. `test_runtime_settings.py` requires the exact seven-field template/validator
   contract, so adding the required eighth native flag fails its source/template
   equality. The coordinator must add `EnableAtmosphere: true` to the shared
   settings contracts/templates and update their expected flag set/count.
2. Seven `test_alert_chain.py` cases execute the changed native body with a
   synthetic scope that has no `HCAtmosphereRelay`. They raise NameError, as
   separately recorded in `INTEGRATION-alert-fixtures.txt` (10 tests, 7 errors).
   The fixture owner must supply that new explicit collaborator. The new owned
   v1 alert suite executes the same authored body with the collaborator and
   checks disabled identity, weather shrinkage, frozen source, and unchanged
   root lifetime/strength/hops/event. Existing tests were not hidden or patched.
3. The BDD run also encountered `ProcessLookupError` in
   `test_wine_compile_probe.py:714`, between `/proc` existence checking and
   reading the state of its synthetic Python child. This test does not run Wine
   or DayZ. The complete result is retained; a targeted recheck is recorded in
   `CHILD-RECHECK.txt` (**1 test passed**). This external test/lifecycle code was
   not edited.

Neither integration failure is a native gameplay result. The source/package
work must not be reported as a green integrated branch until those owners fix
their shared contracts and the final commands pass.

## Native API evidence

All citations refer to the inspected installed snapshot at
`~/.cache/hollow-country/native-scripts/scripts-1.30.164289/`; no native source
dump or game asset was copied into the repository. Citations are also placed in
the new script files. These establish interface availability, not runtime proof.

| Used native surface | Installed file:line |
| --- | --- |
| GetGame; IsServer | `2_GameLib/gameLib.c:4`; `3_Game/Global/Game.c:1120` |
| GetWorldName(out string) and string-returning overload; GetMission; GetDayTime | `3_Game/Global/Game.c:932`, `:934`, `:1093`, `:440` |
| GetWorldData; native Chernarus instance returned | `3_Game/gameplay.c:742`; `5_Mission/mission/missionBase.c:116`, `:188` |
| Class.Cast | `1_Core/proto/EnScript.c:94` |
| WeatherOnBeforeChange; weather/default fields; SetupWeatherSettings; CalculateVolFog | `3_Game/WorldData.c:251`, `:19`, `:36`, `:427`, `:414` |
| Chernarus override signatures / vanilla fog behavior | `4_World/Classes/Worlds/ChernarusPlus.c:82`, `:92`, `:468–515` |
| Default settings fields (rain/storm/times/calm/height/sudden chances) | `3_Game/WorldData.c:561–601` |
| EWeatherPhenomenon qualified members | `3_Game/Weather.c:10–20` |
| GetActual; Set; SetLimits | `3_Game/Weather.c:38`, `:49`, `:74` |
| Weather GetTime / GetOvercast / GetFog / GetRain / GetSnowfall / GetWindDirection / GetWindMagnitude | `3_Game/Weather.c:180`, `:183`, `:186`, `:189`, `:192`, `:199`, `:205` |
| SetStorm; GetWindSpeed; SetWindMaximumSpeed; SetRainThresholds | `3_Game/Weather.c:219`, `:248`, `:269`, `:303` |
| IsDynVolFogEnabled; distance/height density and height-bias setters | `3_Game/Weather.c:354`, `:360`, `:370`, `:381` |
| GetMissionWeather / GetWeatherUpdateFrozen; server-only forecast callback routing | `3_Game/Weather.c:392`, `:402`, `:115–145` |
| Public gameplay m_Data; PlayerData/WorldsData; disablePersonalLight; lightingConfig | `3_Game/CfgGameplayHandler.c:6`; `3_Game/CfgGameplayDataJson.c:16–17`, `:89`, `:192` |
| Native server gameplay synchronization / getters | `3_Game/CfgGameplayHandler.c:88–108`, `:129–138` |
| Server loads gameplay data and constructs world before core startup | `5_Mission/mission/missionServer.c:85–96`, `:161–166`; authored `scripts/5_Mission/HCMissionServer.c:3–6` |
| Dark-night preset 1 and native client lighting consumer | `3_Game/WorldLighting.c:11–22`; `4_World/Entities/ManBase/PlayerBase.c:6042–6058` |
| Personal-light server restriction consumed and applied on clients | `4_World/Entities/ManBase/PlayerBaseClient.c:39–55`, `:59–76` |
| Native/operator 12-month seasonal temperature support, retained | `3_Game/CfgGameplayDataJson.c:196–197`; `3_Game/CfgGameplayHandler.c:151–158`; `4_World/Classes/Worlds/ChernarusPlus.c:35–58`; `3_Game/WorldData.c:120–184` |
| GetNoiseSystem; GetEnvironmentNoiseReduction(vector pos) | `3_Game/Global/Game.c:738`; `3_Game/Noise.c:12–13` |
| float.MAX; Math.Floor | `1_Core/proto/EnConvert.c:112`; `1_Core/proto/EnMath.c:427` |
| FileExist / OpenFile / ReadFile / CloseFile; FileMode | `1_Core/proto/EnSystem.c:397`, `:417`, `:425`, `:443`, `:380–386` |
| string Length / IndexOf / ToLower; int.AsciiToString; Print | `1_Core/proto/EnString.c:199`, `:240`, `:171`; `1_Core/proto/EnConvert.c:44`; `1_Core/proto/EnDebug.c:96` |

`HCServer.Get/IsStarted/GetSettings/Start` and the new weather helpers are authored
interfaces, not invented native APIs. Existing alert geometry/inventory/sound
interfaces were not changed. No new server tick, RPC, entity scan or HCModule is
introduced. All new work is constant time per native forecast or existing
bounded relay recipient, plus once-per-process bounded file reads.

## Exclusions and acceptance limits

Excluded: new shaders, arbitrary exposure/gamma/contrast, client-only brightness
or postprocess darkness, new indoor occlusion/renderer passes, replacement sky
or lighting assets, fake weather sounds, per-client fog, and unsupported custom
lighting files. Native `WorldLighting` has a loader, but this implementation uses
only its existing synchronized preset through server data. It does not promise
identical rendering across displays or defeat modified clients. Existing
flashlights/NVG, doors, movement, inventory, entity visibility and audio are not
altered. Interior darkness comes from the server's personal-light restriction;
room-specific renderer darkness is not implemented or claimed.

Excluded from this source pass: other maps, persistent custom weather schedules,
calendar simulation, new temperature controllers and new fog-region entities.
The supported native seasonal curve is retained rather than duplicated. Weather
cycle state intentionally uses native server uptime and resets with the process;
native saved weather remains an initial interpolation condition (`reset=false`).
Controller/flag/marker changes require a full process restart and client
reconnect; hot reconfiguration/instant restoration of an already-applied weather
state is not offered. Removing the marker does not retroactively alter the
one-process admission result or erase saved native weather.

## Exact subsequent local-server acceptance protocol — all PENDING

1. Integrate the shared settings/template and alert-fixture contracts listed
   above. Re-run the two required final commands until both pass. Freeze the
   integrated source revision; record source/PBO/server/client build hashes,
   ChernarusPlus mission identity, launch arguments, settings and storage copy.
   Use a fresh external runtime/profile/storage, never the Steam mission or a
   friend's eventual server. Other feature qualification stays independent.
2. Build the actual source PBO with installed official tooling or the repository
   deterministic writer. The latter exact commands are:
   `python3 -B tools/package/pbo.py pbo --addon mods/HollowCountry --out <fresh-external-output>/hollowcountry.pbo`
   and `python3 -B tools/package/pbo.py verify <fresh-external-output>/hollowcountry.pbo`.
   Load that source/package in installed DayZDiag with the same mission and
   capture compiler output, core native self-tests and initialization. Any script
   compiler error fails this step. Then repeat with the normal dedicated server
   loading the PBO. A container checksum or initialization message alone does
   not complete weather acceptance. For signed normal-server acceptance use
   `tools/package/Build-Sign-Verify.ps1` with external private/public keys and
   verify signatures; never place keys or game files into this repository.
3. Prepare the delegation candidate from that isolated mission's untouched stock
   XML, before starting either process:

   ```sh
   python3 -B tools/package/atmosphere.py v1-script --source <isolated-stock-mission>/cfgweather.xml --output <fresh-external-weather-candidate>
   python3 -B tools/package/atmosphere.py validate --candidate <fresh-external-weather-candidate> --source <isolated-stock-mission>/cfgweather.xml
   ```

   Retain the original XML/hash/mission and candidate report/manifest outside the
   repository. Copy only the validated candidate XML into the isolated mission
   as `cfgweather.xml`. Do not add MissionWeather(true), frozen weather, another
   weather mod or a second mission weather setter. Leave native storage reset
   disabled. The source world-data package owns forecasts after admission.
4. Baseline/control run: use this same PBO and delegated XML but **no marker**.
   `EnableAtmosphere` defaults true. Confirm one PENDING admission log, no
   experimental profile log, native Chernarus forecasting, original lighting
   data and no environment sampling by the supplementary radius helper. Also
   run explicit `EnableAtmosphere=false` with a marker: expect DISABLED and the
   same native behavior. In fresh profiles test missing/noncanonical/enabled XML
   and unsupported-map admission: expect BLOCKED with no custom weather writes.
5. Stop the full process. In the directory supplied by the server's `-profiles`
   argument create `HollowCountry/acceptance/atmosphere.enable` (empty regular
   file is sufficient); leave `EnableAtmosphere=true`. Start a **fresh process**.
   Example normal-server argument contract, substituting actual isolated paths:
   `DayZServer_x64.exe -config=<runtime>/serverDZ.cfg -profiles=<profile> -mod=<runtime>/@HollowCountry -port=2302 -ip=127.0.0.1 -dologs -adminlog -netlog`.
   The copied server config must select the isolated ChernarusPlus mission and
   the observed query port; use the existing local-server setup for these paths.
   Confirm EXPERIMENTAL opt-in and script-owner logs, `Qualified()==false`, and
   absence of competing-controller or compiler errors. Record PARTIAL if the
   world configuration lacks native dynamic volumetric fog; that cannot pass
   valley-fog acceptance.
6. Observe at least one complete two-hour **native weather-clock** cycle plus
   transitions (recommend 150 minutes), using a bounded observation-only hook
   based on the existing `tools/setup/weather_probe.py` sampling surface. Record
   native MissionWeather/freeze, actual/forecast/time/limits, storm/rain/wind,
   dynamic fog capability/density/bias and game date/time. The existing probe
   stages a separate vanilla observation runtime; **its stock/candidate runs do
   not load or qualify this addon automatically**. Do not label its XML-only
   report an addon acceptance receipt. Independently verify no dual setters,
   native storage precedence, bad-travel interval and the post-storm calm
   interval with measured transition delay. Keep failures and unknowns explicit.
7. With **two real clients** on the same normal-server package/profile, observe
   dawn (05:00/07:00/09:00), day, dusk/night (20:00/23:00), storm and recovery.
   Repeat on a valley route and nearby ridge, and inside/outside the same
   buildings. Compare native dark-night preset 1 and personal-light restriction
   on both clients, including late join/reconnect, normal personal-light toggle,
   flashlights/NVG and permitted graphics settings. Check readable navigation,
   collision/doors, threat recognition and visibility fairness. Record captures
   from both views and their settings. Repeat representative January/July/autumn
   mission dates to check retained native seasonality; do not infer temperature
   or renderer behavior from offline arrays.
8. Relay acceptance additionally requires independently admitted infected chains
   or the coordinator's approved bounded native-chain fixture. This writer does
   **not** bypass infected qualification. With actual native vocalizations and
   the two clients, compare calm/storm native reduction at the frozen source,
   same base radius, recipient positions and geometry. Record the observed
   reduction, computed [0.35,1] scale/range, TTL/hops/caps and actual recipients;
   confirm no synthetic sound, target, extra hop or alert refresh. Test moving
   emitter, occlusion and boundary distances. If the chain dependency is not
   admitted, this acceptance step stays PENDING.
9. Repeat normal PBO/server startup after graceful save/restart, then remove the
   marker **while stopped** and restart/reconnect: vanilla control must return
   without a reset or duplicate controller. Exercise rollback by restoring the
   original XML, lighting/config/profile/storage pair and previous package.
   Compare both clients. A previously saved weather value is native storage,
   not proof of an active custom controller. Do not overwrite unrelated state.
10. Run the intended 3–6 player load with the combined package. Record server
    frame/tick time, client frame time, forecast and relay work, fog/lighting
    readability and alerts. Budgets remain provisional until measured here.
    Only actual DayZDiag, normal-server/PBO, two-client and load evidence can
    close the appropriate runtime rows. No offline test or marker opts the
    feature into production qualification.
