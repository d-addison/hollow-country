# Runtime activity audit

Run from the repository or the release bundle:

```sh
python3 -B -m tools.release.activity_check server.RPT
python3 -B -m tools.release.activity_check server.RPT --json
python3 -B -m tools.release.activity_check server.RPT --expectations config/activity-expectations.json
```

The default catalogue is located relative to the tool, independent of the working
directory. The checker streams bounded RPT lines and retains numeric aggregates,
module tokens and counts only. It shares `rpt_summary.filtered()` and its bounded
line reader. It never prints raw RPT lines, input paths, player identities or regex
exceptions. Oversized lines are discarded using the summary reader's policy.
Local expectation files are trusted operator configuration, including their regexes.

`rpt_summary` includes the same results in its JSON `activity` section and text
report. `checkstart` prints `activity=ok|inert count=N` at the end of observation.
Neither tool changes its boot verdict or exit codes because of activity findings.
If the catalogue is missing or invalid, these integrations print
`activity=unavailable count=0`; this is an audit error, never an activity pass.

## Declare a signal

Each entry in `config/activity-expectations.json` belongs to a module token from
`[HC Ready] module=... enabled=true`. Feature IDs are stable, short public tokens.
One module may have several feature entries. Every registered module name in the
current source survey has an entry, including the unregistered Morse compatibility
shell; entries are reported only when their module is observed enabled in this RPT.
An enabled module not in the catalogue automatically produces `NO_SIGNAL` with
feature `undeclared`, so adding a new module cannot silently bypass the audit.
Missing readiness markers are not proof that a module is disabled: a file with no
readiness markers at all is an input error, and the catalogue cannot diagnose an
unlogged module that never reaches readiness registration.

Example (a cumulative counter, so use `max`):

```json
{
  "module": "InfectedVariety",
  "feature": "variety-activity",
  "signal": {
    "tag": "[HC Infected]",
    "regex": "variety dormant=(?P<dormant>\\d+) woken=(?P<woken>\\d+) runners=(?P<runners>\\d+)",
    "fields": ["dormant", "woken", "runners"]
  },
  "comparison": "max",
  "floor": 1,
  "window_minutes": 30,
  "needs_player": true
}
```

The root object has `schema_version: 1` and a `features` array. `signal` is either
null or an object with an exact bracketed RPT tag, a Python regex and named numeric
fields. Each matching sample sums those fields, except for `present`;
`comparison` combines samples:

| Comparison | Meaning | Use |
| --- | --- | --- |
| `max` | Largest sample within the window | Cumulative counters or live population peaks |
| `sum` | Add samples within the window | Per-interval deltas only; repeated cumulative logs inflate this |
| `last` | Final sample within the window | A required end-of-window value |
| `present` | 1 when any valid numeric sample appears within the window | First-operation timestamps/markers, including zero or subsecond values; floor must be 1 |

Values must be finite and nonnegative. `floor` is a positive inclusive minimum
(`value >= floor`); for counters a floor of 1 means at least one operation/entity.
Presence proves only that the declared marker appeared, regardless of its numeric
magnitude. Do not use `present` on success flags that also print zero on failure;
require their success value instead. Windows are
finite, nonnegative minutes. Never use a configuration limit, registration count,
refusal count, ready boolean, authored definition count or capability admission as
proof of runtime work. `source` and `suggested_counter_location` are maintenance
metadata; the latter identifies the owner to instrument when `signal` is null.
Owners with no tick hook need a bounded periodic reporting hook added to their
lifecycle, rather than another startup-only receipt. No gameplay code is changed
by this tool.

The catalogue uses existing server receipts only. For example, infected sampling,
ecology visits and debug snapshot points prove those operations ran, not their
visual/gameplay outcome. `[HC Reached] first_s` is a numeric first-operation marker,
not a population count, and uses `present` (as does the SignsOfLife area marker).
The catalogue audit found no ID fields used as counts; trade's `observed_complete`
flag deliberately retains `max` with floor 1, so zero never proves completion.
AI site activity requires actors, not qualified routes or
controllers. Client-only appearance and startup mounting receipts have no reliable
server activity counter and remain `NO_SIGNAL`.

## Windows and player presence

The observation clock starts at the first privacy-safe `[HC Ready]` marker in the
RPT, including a pending or disabled module's marker. Later readiness updates do
not reset it. Timestamped RPT lines advance this clock; midnight is handled, and
small backward timestamps from interleaved logging are clamped. Use one boot per
RPT. Signals from server start, including OnStart work before readiness, are
retained with zero window exposure; startup does not consume either observation
window. Signals after their
window are counted as printed samples but cannot satisfy the activity floor.
`value` is the aggregate inside the window; `samples` counts all matching numeric
samples since server start, including startup and late samples.

For `needs_player: true`, the window counts cumulative minutes with observed player
presence after the first readiness marker. Thus an empty server does not condemn
player-triggered features. Existing native player connect/leave session
markers are reduced to bounded counts before privacy filtering, using the existing
report's event and connect-enabled patterns. No name or identifier is retained.
The existing `[HC Expansion AI] group scale players=N` and
`[HC InfectedLOD] stats ... players=N` runtime observations correct that count.
Configuration `players=N` budgets are excluded. `Player connect enabled` grants
connection permission and never establishes presence. Missing presence markers
leave a player-dependent window waiting; JSON exposes presence-observation counts
and accumulated player minutes so this limitation is visible. Connection events
can precede actual character control; presence does not establish a qualifying
nearby encounter, group action or manual experiment.

## Read the result

| Status | Meaning |
| --- | --- |
| `ACTIVE` | Declared aggregate met its inclusive floor inside its window |
| `INERT` | Window elapsed and numeric signal printed, but in-window aggregate missed the floor |
| `SILENT` | Window elapsed without any matching numeric signal since server start |
| `NO_SIGNAL` | Enabled feature has no declared signal, including unknown enabled modules |
| `WAITING` | Floor not met and eligible window has not elapsed (or timestamps are insufficient) |

Every enabled feature gets one line, followed by totals and the compact summary.
`count` includes `INERT`, `SILENT` and `NO_SIGNAL`. Exit 0 means only `ACTIVE` and/or
`WAITING`; exit 8 means one or more activity findings (including `NO_SIGNAL`, so
missing instrumentation cannot yield a clean exit). Exit 6 means unreadable or
invalid input, including an RPT without readiness markers. JSON errors are also
JSON. Argument syntax errors also exit 6 and never echo supplied arguments.

Floors/windows are provisional operator audit policy, not measured target-load
budgets. The catalogue deliberately allows longer windows for settlement changes,
trade, refresh and conditional experiments. `INERT`/`SILENT` require investigation:
no qualifying encounter, a manual marker that was never enabled, old build log
formats or delayed startup can explain them. `ACTIVE` proves only the named signal,
never full gameplay correctness, native acceptance or multiplayer behaviour.
Readiness boot acceptance still requires the separate native compile/boot gate.

## Instrumentation backlog

The following lifecycle owners lack a suitable numeric runtime counter. Add bounded
periodic successful-operation counts there (and the relevant action/provider), then
replace the null declaration. Startup-only owners need a reporting hook. Morse is
folded into Radio and is not registered; it is listed for source-name completeness.

| Module | Instrumentation owner (`file:function`) |
| --- | --- |
| AIIncidents | `mods/HollowCountryExpansionAI/scripts/4_World/HCXAIIncidentResponse.c:OnTick` |
| AIRoles | `mods/HollowCountryExpansionAI/scripts/4_World/HCXAIRoleActivities.c:OnTick` |
| AdminMap | `mods/HollowCountry/scripts/4_World/Admin/HCAdminModule.c:OnTick` |
| BodyStories | `mods/HollowCountry/scripts/4_World/Leads/HCBodyStories.c:OnTick` |
| CampRespawn | `mods/HollowCountry/scripts/4_World/Camps/HCCampRespawn.c:OnStart` |
| Camps | `mods/HollowCountry/scripts/4_World/Camps/HCCampModule.c:OnTick` |
| Crafting | `mods/HollowCountry/scripts/4_World/Crafting/HCCraftingModule.c:OnStart` |
| DeadDrops | `mods/HollowCountry/scripts/4_World/World/HCDeadDrops.c:OnTick` |
| Escalation | `mods/HollowCountry/scripts/4_World/World/HCEscalationClock.c:OnTick` |
| Events | `mods/HollowCountry/scripts/4_World/Events/HCEventModule.c:OnTick` |
| Grade | `mods/HollowCountry/scripts/4_World/Atmosphere/HCGradeModule.c:OnStart` |
| Groups | `mods/HollowCountry/scripts/4_World/Groups/HCGroupModule.c:OnTick` |
| Holdouts | `mods/HollowCountry/scripts/4_World/World/HCHoldouts.c:OnTick` |
| Lighting | `mods/HollowCountry/scripts/4_World/Atmosphere/HCLightingModule.c:OnStart` |
| Morse | `mods/HollowCountry/scripts/4_World/Leads/HCRadioChatter.c:OnTick` |
| OptionalPacks | `mods/HollowCountry/scripts/4_World/Atmosphere/HCOptionalPacksModule.c:OnStart` |
| Pickers | `mods/HollowCountry/scripts/4_World/World/HCPickers.c:OnTick` |
| Polish | `mods/HollowCountry/scripts/4_World/Polish/HCPolishModule.c:OnStart` |
| Scenes | `mods/HollowCountry/scripts/4_World/Scenes/HCScenesModule.c:OnTick` |
| SearchBinding | `mods/HollowCountry/scripts/4_World/Loot/HCSearchBinding.c:Attempt` |
| SurvivalAlignment | `mods/HollowCountry/scripts/4_World/Survival/HCMealBuffs.c:OnStart` |
| TapedHelmetMounts | `mods/HollowCountry/scripts/4_World/Survival/HCTapedHelmetMounts.c:OnStart` |
| TapedLight | `mods/HollowCountry/scripts/4_World/Survival/HCTapedLightNative.c:OnStart` |
| TapedPackMounts | `mods/HollowCountry/scripts/4_World/Survival/HCTapedPackMounts.c:OnStart` |
| WeatherDays | `mods/HollowCountry/scripts/4_World/Weather/HCWeatherDaysModule.c:OnTick` |
| World | `mods/HollowCountry/scripts/4_World/World/HCWorldModule.c:OnTick` |
| WorldIncidents | `mods/HollowCountry/scripts/4_World/World/HCWorldIncidents.c:OnTick` |
| WreckSalvage | `mods/HollowCountry/scripts/4_World/Vehicles/HCWreckSalvage.c:OnTick` |
| ZoneGuards | `mods/HollowCountryExpansionAI/scripts/4_World/HCXZoneGuards.c:OnTick` |
| v2-expansion-living-world | `mods/HollowCountryExpansionAI/scripts/4_World/HCXStance.c:OnTick` |


## Build 117 RPT calibration (2026-11-20)

Read-only evidence: newest `DayZServer_x64_2026-11-20_12-24-42.RPT`, copied locally
for rehearsal and removed afterward. This snapshot is 16,611,862 bytes and
supersedes the earlier growing-log calibration. The observed span after first
readiness is 75.017 minutes; player-present exposure is 54.449 minutes.
There are 63 enabled modules. Standalone and integrated JSON activity sections
agree; the existing summary outcome remains `connect_enabled` (exit 0).

On the same snapshot, before the review fixes:

```text
totals ACTIVE=12 INERT=9 SILENT=5 NO_SIGNAL=29 WAITING=8
activity=inert count=43
```

After retaining startup signals and using presence for first-operation timestamps:

```text
totals ACTIVE=13 INERT=12 SILENT=1 NO_SIGNAL=29 WAITING=8
activity=inert count=42
standalone_exit=8
```

Notes is now ACTIVE (`world=2`, one startup sample). CellarSampler and Cellars each
printed one startup sample with `cellar_measured=0`; they correctly change from
SILENT to INERT. Radio likewise changes from SILENT to INERT with one zero-valued
startup sample. Infected's first-operation timestamp is now represented as
presence (`value=1`), independent of how many seconds that operation took.
SignsOfLife still has no matching marker and remains SILENT.

Full non-ACTIVE list (`none` means no valid in-window observation, not zero):

| Module | Feature | Status | Observed | Numeric samples (including startup/late) |
| --- | --- | --- | --- | --- |
| AIIncidents | runtime-activity | NO_SIGNAL | none | 0 |
| AIRoles | runtime-activity | NO_SIGNAL | none | 0 |
| AISelfDefence | threats-applied | WAITING | 0 | 6 |
| AITactics | fire-events | WAITING | none | 0 |
| AITrade | trade-completed | WAITING | 0 | 1 |
| AdminMap | runtime-activity | NO_SIGNAL | none | 0 |
| BodyStories | runtime-activity | NO_SIGNAL | none | 0 |
| CampRespawn | runtime-activity | NO_SIGNAL | none | 0 |
| Camps | runtime-activity | NO_SIGNAL | none | 0 |
| CellarSampler | cellars-measured | INERT | 0 | 1 |
| Cellars | cellars-measured | INERT | 0 | 1 |
| Crafting | runtime-activity | NO_SIGNAL | none | 0 |
| DeadDrops | runtime-activity | NO_SIGNAL | none | 0 |
| Escalation | runtime-activity | NO_SIGNAL | none | 0 |
| Events | runtime-activity | NO_SIGNAL | none | 0 |
| FactionConflict | encounters-observed | WAITING | 0 | 2 |
| Grade | runtime-activity | NO_SIGNAL | none | 0 |
| Groups | runtime-activity | NO_SIGNAL | none | 0 |
| Holdouts | runtime-activity | NO_SIGNAL | none | 0 |
| HordeMigration | drifting-cohorts | INERT | 0 | 2 |
| InfectedReach | reach-actions | INERT | 0 | 6 |
| InfectedVariety | variety-activity | INERT | 0 | 7 |
| Leads | active-leads | INERT | 0 | 8 |
| Lighting | runtime-activity | NO_SIGNAL | none | 0 |
| LootRefresh | loot-refreshed | WAITING | 0 | 1 |
| MapPins | pins-sampled | INERT | 0 | 8 |
| MaterializerBridge | actors-spawned | INERT | 0 | 7 |
| OptionalPacks | runtime-activity | NO_SIGNAL | none | 0 |
| Pickers | runtime-activity | NO_SIGNAL | none | 0 |
| Polish | runtime-activity | NO_SIGNAL | none | 0 |
| Progression | forage-familiarity | WAITING | none | 0 |
| Radio | reports-received | INERT | 0 | 1 |
| Scenes | runtime-activity | NO_SIGNAL | none | 0 |
| SearchBinding | runtime-activity | NO_SIGNAL | none | 0 |
| SettlementDecay | towns-changed | WAITING | none | 0 |
| SignsOfLife | area-sampled | SILENT | none | 0 |
| SurvivalAlignment | runtime-activity | NO_SIGNAL | none | 0 |
| TapedHelmetMounts | runtime-activity | NO_SIGNAL | none | 0 |
| TapedLight | runtime-activity | NO_SIGNAL | none | 0 |
| TapedPackMounts | runtime-activity | NO_SIGNAL | none | 0 |
| TeamPing | ping-recipients | INERT | 0 | 67 |
| VehicleFlip | flip-pulses | WAITING | none | 0 |
| WeatherDays | runtime-activity | NO_SIGNAL | none | 0 |
| World | runtime-activity | NO_SIGNAL | none | 0 |
| WorldIncidents | runtime-activity | NO_SIGNAL | none | 0 |
| WreckSalvage | runtime-activity | NO_SIGNAL | none | 0 |
| ZoneGuards | runtime-activity | NO_SIGNAL | none | 0 |
| hcxai-live-map | live-ai-units | INERT | 0 | 15 |
| optional-expansion-human-ai | site-actors | INERT | 0 | 15 |
| v2-expansion-living-world | runtime-activity | NO_SIGNAL | none | 0 |

`ACTIVE`: DebugSnapshot, Ecology, Forage, Infected, InfectedDoors, InfectedLOD, InfectedMemory, Interiors, Materializer, Melee, Notes, Shelters, WorldSaves.

Interiors completed 1,500 props about 43 minutes after first readiness, so its
window is 60 minutes. Infected Variety printed seven numeric samples with every
activity field zero and is INERT. These observations calibrate audit rules;
they do not accept missing native experiments or establish multiplayer behaviour.

The declaration audit checked every captured field: the two `first_s` markers use
`present`; no captured IDs are treated as counts. Trade's completion flag requires
one, rather than mere presence of its zero/one diagnostic. Progression familiarity
is a positive score printed after successful gains, not a timestamp or identifier.
Other captured fields are operation/entity/population counts.

Validation tails for the review fixes:

```text
presence zero/subsecond/positive before and after readiness: PASS (6 cases)
startup max/sum/last; readiness clock; late exclusion; no-ready output: PASS
presence floor validation: PASS
Python source compilation: PASS
standalone/integrated JSON: identical; summary outcome=connect_enabled
standalone_exit=8
integrated_exit=0
git diff --check: PASS
```

The reducer rehearsal explicitly uses a server-time window; Notes' real declaration
uses player time. No unit tests were added or updated; no existing tests target
these changed tools. No Enforce files changed, so Enforce lint/perf and the native
compile/boot gate were not run. The actual `checkstart` server/process watch was
not exercised. No new native acceptance or multiplayer claim follows from this
parser correction.
