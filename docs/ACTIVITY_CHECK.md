# Runtime activity audit

Run from the repository or the release bundle:

```sh
python3 -B -m tools.release.activity_check server.RPT
python3 -B -m tools.release.activity_check server.RPT --json
python3 -B -m tools.release.activity_check server.RPT --client-rpt client.RPT --json
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
These integrations remain server-only; use the standalone checker to include a
companion client RPT.
If the catalogue is missing or invalid, these integrations print
`activity=unavailable count=0`; this is an audit error, never an activity pass.

## Declare a signal

Each entry in `config/activity-expectations.json` belongs to a module token from
`[HC Ready] module=... enabled=true`. Feature IDs are stable, short public tokens.
One module may have several feature entries. All 64 module names in the
current source survey have non-null signals, including the unregistered Morse
compatibility shell; entries are reported only when their module is observed enabled in this RPT.
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
Owners with no tick hook need a bounded periodic reporting hook when runtime
work has no existing receipt. The checker does not change gameplay. The shared
taped-light runtime now counts successful exact-host wearable operations in its
existing five-minute summary.

The catalogue uses existing receipts from the declared input scope. For example, infected sampling,
ecology visits and debug snapshot points prove those operations ran, not their
visual/gameplay outcome. `[HC Reached] first_s` is a numeric first-operation marker,
not a population count, and uses `present` (as does the SignsOfLife area marker).
The catalogue audit found no ID fields used as counts; trade's `observed_complete`
flag deliberately retains `max` with floor 1, so zero never proves completion.
AI site activity requires actors, not qualified routes or controllers. Wearable
mounting uses successful native custody operations, never authored/admitted pairs.
The `scope` field distinguishes `runtime` (default), `transport`, `client`, and
`diagnostic` evidence and is included in text and JSON results. Grade, Lighting
and Polish use the shared presentation tuning send receipt (`transport`); this
proves only a send, not delivery, rendering or a specific layer being enabled.
OptionalPacks is a subscription-only shell with no gameplay tick: its
`config-probed` diagnostic proves the probe ran and cannot establish CE animal or
bicycle activity. Such diagnostic evidence is explicitly separate from runtime
work and must never be cited as gameplay activity. SurvivalAlignment declares the
client stamina HUD receipt; supply it using `--client-rpt client.RPT` alongside
the server RPT. A server-only RPT can leave it SILENT/WAITING. Client
HUD evidence does not establish stamina rates. A missing declaration still
produces NO_SIGNAL; a declared but absent receipt remains an activity finding
after its observation window.

## Windows and player presence

The optional companion client RPT must come from the same build and play session
as the server RPT; the operator must establish that pairing. The checker does not
infer session identity from private identifiers. The server remains the sole
source of enabled modules, server clocks, player presence and non-client signals.
Only `scope=client` declarations consume companion lines; client receipts in the
server input cannot satisfy them. Client readiness markers are neither required
nor used. Client-scoped windows count elapsed timestamp time from the first
timestamp in the companion file, independently of server readiness and player
events. This includes client startup/menu time, so capture one boot and connect
within the declared window. A late HUD receipt counts as a sample but cannot
satisfy an expired window. Missing receipts remain SILENT/WAITING, and malformed
or unreadable companion input (including fewer than two valid timestamps) exits
6. The same privacy filter and bounded reader apply to both files. JSON reports
`client_rpt_observed` and, when supplied, `client_minutes`. `elapsed_minutes` on
client rows uses that client clock; `needs_player` retains the catalogue's
server-only policy but requires no server-style connect event in companion mode.
`rpt_summary` and `checkstart` continue to report their server-only audit; companion
evidence is available through this standalone command.

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

## Current signal map (round r11)

Existing `[HC Reached] first_s` operation markers cover AI incident lease steps,
AI role leases, admin request dispatch, body death checks, camp respawn reservations,
camp maintenance, dead-drop row checks, escalation clock steps, picker trip steps,
search supply binding, weather ticks, world rows, incident sweeps and living AI
actor checks. Their `present` reduction accepts a zero-second first operation.
These markers prove the named code path ran, not its gameplay outcome. They are
bounded to one line per feature per boot by HCReached; its shared 64-token cap
can still make later markers silent if exhausted. No new reached tokens are added.

| Modules | Signal and limitation |
| --- | --- |
| Crafting | `completed_total`; successful recipes only |
| LootRefresh | `refreshed_total`; zero timers or maintenance alone is insufficient |
| Events | Situation `started_total`; refusals/source/store totals are not successes |
| Scenes | `placed_total`; notes/work/refusals are not placements |
| Radio / Morse compatibility | `delivered_total`; no player trade/talk requirement |
| SettlementDecay | `changed_total`; rows inspected alone are insufficient |
| Materializer | `materialized_total`; proposals/claims alone are insufficient |
| VehicleFlip | `pulses_total`; requests/refusals alone are insufficient |
| WreckSalvage | `created_total`; debit without creation is insufficient |
| Progression | Window `gains`; skip/persistence totals are not gains |
| Holdouts | Occupied/alert ledger rows; actor/cache recovery still unproven |
| Groups | Group member samples from MapPins; group edits/delivery still unproven |
| ZoneGuards | `actors_spawned`; authored sites/initialisation alone are insufficient |
| TapedLight | Native `attached` + `detached` successful operations |
| TapedHelmetMounts / TapedPackMounts | Exact-host `helmet_operations` / `pack_operations` in the shared HC-7 summary |
| Grade / Lighting / Polish | Shared presentation RPC send, scope `transport` |
| OptionalPacks | Config probe only, scope `diagnostic` |
| SurvivalAlignment | Stamina HUD shown, scope `client`; needs a client RPT |

Other previously declared signals retain their existing operations/populations.
All cumulative totals use `max`, never `sum`. Regexes capture named fields without
anchoring the end of a summary, so search refresh accepts signed/unavailable
`timers=-1` and trailing `state_fault=<token>` without counting either as activity.
Situation summaries accept the extra `source_w`, `source_total`, `store_w`,
`store_total` fields after `identity_total` without counting prerequisites as starts.

Optional cross-owner extension: `auditroutes` owns HCMealBuffs.c. If server-side
SurvivalAlignment evidence is required, it must report actual stamina integration
operations through that owner; the current startup drain/recovery settings and
`hooks=0` receipt cannot prove them. The companion client option makes the current
HUD declaration observable without that extension. No other worker's source is changed here.

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
| SearchBinding | house-bound | WAITING | none | 0 |
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

## Round r11 declaration and parser rehearsal (2026-11-20)

The catalogue changed from 64 entries / 30 null signals to 64 entries / zero null
signals. A source survey found 64 GetName overrides and no undeclared module names.
The newest local profile RPT was copied read-only to scratch for this rehearsal:
`DayZServer_x64_2026-11-20_12-24-42.RPT`, 30,355,568 bytes at copy time. It is a later
snapshot of the same growing build-117 log used above, not a boot of these changes.
The copy and temporary validation logs were removed after rehearsal.

Observed enabled modules: 63. Observation exposure: 123.027 server minutes and
60.500 player-present minutes. Standalone checker output (exit 8):

```text
totals ACTIVE=20 INERT=15 SILENT=26 NO_SIGNAL=0 WAITING=2
activity=inert count=41
```

One ACTIVE result is OptionalPacks' configuration-probe diagnostic, explicitly
`scope=diagnostic`; it is not runtime gameplay evidence. None of the transport or
client-scoped declarations was ACTIVE in this old server log. The removed
NO_SIGNAL findings became real declared observations or visible SILENT/WAITING
findings; this is not evidence that the remaining gameplay bugs are fixed.
Newer r10 summaries are absent from this build-117 snapshot. The next boot must
exercise the current build and investigate the remaining activity findings.

Focused in-memory parser rehearsal (no unit tests or Enforce translator):

```text
14 changed counter/marker/transport formats: PASS
14 privacy-rejected counter lines: PASS
zero situation starts with positive source/store prerequisites: stays zero
Python source compilation: PASS
enforce_lint: pass findings=1 new=0 stale=0 native=yes
enforce_perf: pass findings=65 new=0
git diff --check: PASS
```

The search fixture included `timers=-1` and `state_fault=store_unavailable`;
the situation fixture included both new source/store window and total counters.
Successful exact-host wearable counters are emitted by the existing HC-7 summary
every five minutes, with saturating totals and no extra readiness lines or
per-action logs. Native Object.c:467 GetType was inspected before adding host
classification. No settings keys, modules, gameplay gates or unit tests were added.
No existing tests target the changed Python checker. Native compile and boot are
reserved for the lead; exact-host custody counting, current-build server/client
observations, light geometry and all gameplay acceptance remain pending. The
one-server/at-most-one-client bar remains unchanged; multiplayer is not proven.

Suggested README/MODULE_STATUS wording for the lead:
“Activity signals are declared for all 64 module names; build-117 replay reports
NO_SIGNAL=0, with 41 remaining activity findings. Transport, client and diagnostic
evidence is labelled separately; current-build native compile/boot and gameplay
acceptance remain pending.”

## Companion client review fix (round r11)

The standalone checker now accepts `--client-rpt` so SurvivalAlignment's existing
client HUD receipt can satisfy its declaration. Previously the supported command
accepted only a server RPT, making that client declaration unobservable. Server
readiness still selects enabled features; companion lines cannot enable modules,
contribute server counters or change server player exposure. Client windows use a
separate clock and need no server readiness/connect markers in the client file.
Server-only integrations keep the same activity result, including explicit
`client_rpt_observed=false` metadata.

Focused ephemeral Python-tooling rehearsal (no test files added or updated):

```text
companion HUD receipt inside window: ACTIVE, scope=client
receipt after 30-minute window: INERT, samples=1, value=none
missing receipt after window: SILENT
midnight, privacy filtering, enabled-module authority, clock isolation: PASS
CLI JSON success and invalid companion input exit=6: PASS
standalone/server integration result parity: PASS
catalogue: 64 entries, zero null signals
Python source compilation: PASS
enforce_lint: pass findings=1 new=0 stale=0 native=yes
enforce_perf: pass findings=65 new=0
```

No existing unit tests target this checker; no new unit tests, settings or Enforce
changes were added for this review fix. Current-build paired server/client native
observation remains unproven. The companion file must be paired by the operator;
HUD visibility establishes neither native stamina rates nor multiplayer behavior.
No cross-owner change is required to consume the declared HUD signal. Suggested
README/MODULE_STATUS addition: “The standalone activity checker accepts a paired
client RPT for client-scoped HUD evidence; native gameplay acceptance is pending.”

Final server-only replay used a read-only copy of the same build-117 RPT, now
38,738,991 bytes, with 67.314 player-present minutes. The temporary copy was removed:

```text
totals ACTIVE=20 INERT=17 SILENT=24 NO_SIGNAL=0 WAITING=2
activity=inert count=41
client_rpt_observed=false
git diff --check: PASS
```

This newer snapshot still has 41 findings; it is not a current-build paired
server/client acceptance run.


## Neon R3 RPT ceilings and R4 ratchet (B-03 / W4-09)

`tools.audit.rpt_config_audit` supplies all 15 section 3.5 taxonomy matchers.
Rows 1 (No entry) and 3 (Trying to access error value) are separate. Specific
categories take precedence over row 4's generic Warning Message fallback.
Unknown diagnostics appear as category 0 in sanitized numeric diagnostic rows
and `unclassified_count`; raw excerpts and resource/config names are never emitted.
`taxonomy_complete=true` means matcher coverage, not that every observed line was
classified. Oversized lines are counted separately. Local category-pattern overrides
are for investigations; release auditing always uses the built-in matchers.

`release_gate.audit` applies the same bounded reader and taxonomy to server RPTs,
including upgrade boots and the final soak audit. Every occurrence counts, including
dependency-caused and vanilla lines; provenance and baseline matches do not subtract
from totals. It rejects a count above `rpt_category_ceilings`, unclassified diagnostics,
oversized lines, and an unmeasured (`null`) ceiling. Client checks retain their
separate VME/texture limits. The acceptance-target loader requires exactly the 15
category IDs as JSON string keys, nonnegative integer counts (never booleans or
floats), or explicit `null` for missing measurements. Unknown policy keys are errors.

Initial ceilings for rows 1–14 come from the recorded Build 159 section 3.5 census.
These are provisional regression limits, not acceptance of outstanding defects.
Row 15 has no measured count and remains `null`, so release is blocked until the
lead supplies a complete current/vanilla census. Do not replace missing evidence
with zero. The final zero/vanilla targets and the Build 164 unclassified backlog
remain pending lead RPT verification. Rerun the full taxonomy before tightening
ceilings; changes to category boundaries invalidate comparisons with older audits.
Never raise a ceiling simply to pass a candidate.

R4 now requires timestamped, same-boot Hive init-finished and module readiness
evidence through the shared `ReadinessTiming` parser. Missing/invalid timing,
multiple boots, pending enabled modules or late readiness reject release. Its
limit is the smaller of `readiness_max_after_hive_seconds` and
`readiness_ratchet_max_after_hive_seconds`. Hive init-finished is the established
vanilla baseline; the existing owner allowance is 30 seconds after that marker.
The ratchet starts at that owner cap and must be tightened against measured boots,
never increased to admit regression. It cannot exceed the owner cap. This worker
change provides offline tooling evidence only; native compile, a fresh census,
soak, paired client smoke and upgrade acceptance remain lead-owned and unverified.
