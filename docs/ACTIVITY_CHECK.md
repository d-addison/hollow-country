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
`config-probed` diagnostic proves the probe ran and cannot establish CE animal
activity. Such diagnostic evidence is explicitly separate from runtime
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


### Paired stock/candidate capture for R3 categories 2 and 15

The lead uses `python3 -B -m tools.testing.stock_capture plan` first, then
`stage`, `run --yes --minutes 125`, and `restore`. Workers only inspect and
statically check this tool; they never start the server. The default observation
is the full soak campaign idle length (currently 125 minutes), at least the R3
release soak length. Match the candidate's **whole observation length**, including
its driven phases, by increasing `--minutes` when necessary. The server must be
idle; the shared host lock and exact process checks guard stage, run and restore.
Only the existing graceful CloseMainWindow stop is used. Steam, BattlEye and
signature checks stay enabled; no mod arguments are passed.

“Stock” means the pinned, complete pre-install Chernarus tree in the earliest
`friend_install` backup, verified against that run's journal and the install
receipt layout. The next completed install backed up the same tree. The tool
checks the whole inventory, including byte-exact `cfgeconomycore.xml`,
`cfggameplay.json`, `mapgrouppos.xml`, `db/types.xml` and event files; it rejects
HC init hooks, HC folders, persistence, links and unrecognized entries. Repository
vanilla-row comparisons alone cannot prove a whole stock mission. Missing or
changed evidence causes refusal, never a guessed baseline or download.

Staging creates fresh scratch profiles and a stock mission beside the server,
plus a uniquely named mission copy under `mpmissions`. Its copied config changes
only the mission template and port. Live missions, profiles, config and storage
are untouched. A write-ahead receipt drives `restore`; saved RPTs and duration
receipts remain under the sibling `stock-capture/captures` directory.

For example, use `pair --candidate-rpt CANDIDATE.RPT --stock-rpt STOCK.RPT
--candidate-minutes 125 --stock-minutes 125 --output ceiling-proposal.json`
(with the actual equal observation lengths). Pairing uses the unchanged built-in
`totals_audit` taxonomy and verifies one successful boot and timestamp coverage;
the only additional time allowed is the bounded graceful shutdown window.
All 15 numeric category rows show candidate, stock, signed excess and current
ceiling. Categories 2 and 15 propose `max(candidate_count, stock_count)` without
scaling or subtracting stock warnings. Unclassified/oversized diagnostics remain
explicit blockers. No raw warning text, resource names or identities appear in
the output. The lead reviews the classified warnings and applies any justified
proposal by hand; the tool never edits acceptance targets. A ceiling is never
raised merely to pass a candidate. This capture and offline proposal do not
establish release acceptance.

The R3 campaign ends `walk_ai` with the dev-only `fx_site_patrol_kill`, after the
30-second wait at police-chernogorsk, followed by 20 seconds standing. It uses
the real director-owned patrol (at least two live members, no pending spawn),
kills exactly one via native global `SetHealth`, and leaves its timer registered.
The bounded `[HC Test]` receipt reports the site, result and live members before/after;
only HC's death hook and update produce the required `SitePatrols/death_hold_armed`
and `death_hold_released` counters. `death_hold_deferred` stays diagnostic because
normal next-frame cleanup need not reach its stale report boundary. Test code
never bumps counters; a receipt alone proves neither hold release nor crash survival.

# Soak 185c counter investigation

Source review against native scripts 1.30.164289, 2026-11-24. Engine validation remains pending. No engine, compile gate, driver, phase map or test mod was run or changed. The worktree has no AGENTS.md (nor do its parent directories). Git metadata is read-only; the writer owns the eventual commit SHA. Commit message: `fix(counters): repair stamina request routing and peer activity evidence`.

## Four-counter disposition

| Counter | Cause and change | Exercise / remaining evidence |
|---|---|---|
| SurvivalAlignment/stamina_applied | Stamina RPC_REQUEST collided with presentation tuning at 4854011. The tuning DayZGame override consumes that ID on the server without forwarding; the stamina override can likewise consume tuning on the client. Moved the stamina request to unused 4854012. Tightened the count to require a changed HC-scaled rate and an actual native stamina change; added bounded first-step/rejection diagnostics. | Sprint after an enabled client receipt. The server's HC-2 `stamina=on` already proves enabled staging at module start. Its zero after the reported sprint is not explained by missing client receipt alone; first-step/sample diagnostics must resolve execution and rejected samples next run. No fabricated count or speculative rate change. SHA assigned by banso after exit. |
| SurvivalAlignment/stamina_hud_shown | Blocked when no enabled client receipt arrives. The RPC collision is a definite product bug. Client inventory also omitted the zero row until first use; now registered at client HCUseBegin. Activity row requires client evidence. | Join, receive settings, stand conscious with menus closed and native HUD visible. The widget's existing real Show/sample path remains the only increment. SHA assigned by banso. |
| Polish/hint_shown | Filename guard rejected otherwise opaque native IDs containing characters outside its narrow alphabet, then permanently faulted without explaining why. Encode unsafe bytes injectively (including percent), preserve existing safe filenames and original matching ID, bound filename length, initialize the loaded DTO, and log missing-ID/profile/save failures. Client zero row and client-scoped activity evidence added. | Boot alone cannot trigger it. Fresh valid unshown state plus at least 30 s accumulated live play, a closed menu, successful staged save, matching nonempty native ID and NotificationSystem are required. The supplied RPT cannot distinguish an empty ID, rejected filename, exhausted history or failed save; the new diagnostics do. SHA assigned by banso. |
| InfectedVariety/actor_woken | Not a placement bug established by dormant=0. That is a census of currently dormant living tracked actors, not a historical placement or all-infected count. A separate real accounting bug existed: successful proximity/cap-repair/shot wakes only updated m_Woken, omitting HCUse. Added increments for those successful returns (at most 32 tick wakes and 3 shot wakes); native callback/damage paths keep their own counts. | Not a bug in an empty join: needs an eligible dormant actor and a real proximity/noise/damage wake. Town traversal or a controlled dormant encounter; forest alone guarantees nothing. SHA assigned by banso. |

## Stamina transport and execution

- `mods/HollowCountry/scripts/3_Game/Survival/HCStaminaConfiguration.c:27`: unique request ID; `3_Game/Atmosphere/HCPresentationTuningSync.c:9` and `:57` show the conflicting old ID and swallowing override. Link order determines which consumer wins; neither can safely share the ID.
- `HCStaminaConfiguration.c:263`: ServerLoaded resets then LoadServer runs synchronously. `:250` installs the HC fields before `:258` stages the validated profile. Added a server staged/enabled receipt at `:259`. The provided HC-2 drain=0.25/recovery=2.5/stamina=on line could only follow successful enabled staging; the initial passthrough banner is not the final state. Server Enabled has no timer: only reset/cleanup can clear it after admission (`:147`, `:351`). Thus code supports enabled during the same mission, but does not prove a handler sample during the sprint.
- Native `3_Game/CfgGameplayHandler.c:81` calls the mission then game load hooks; `:94` sends `Param1<CfgGameplayJson>(m_Data)` at target null; `:102` reads the object and replaces m_Data. Native `1_Core/proto/Serializer.c:3-9` explicitly documents deep class/member serialization, with NonSerialized as the opt-out, and `:57-58` declares Write/Read. HC fields have no such opt-out. There is no hand-written stamina field whitelist in native CFG sync. Matching client/server script DTOs include the modded fields by this contract; actual wire receipt still needs the next native run.
- Native `3_Game/DayZGame.c:3141` invokes Event_OnRPC, then routes a target object to target.OnRPC or target-null CFG sync to CfgGameplayHandler (`:3159`). The request is a game-level target-null RPC, but the old same-ID override could stop it before that native path. `HCStaminaConfiguration.c:320` requests once per session; `:331` resends with the existing per-session 10 s cooldown; disconnect removes the cooldown entry. No settings are accepted from clients. `:281` accepts only a replaced native DTO; `:307` stages/logs it or buffers it until session start (`:368`).
- `mods/HollowCountry/scripts/4_World/Survival/HCStaminaIntegration.c:38`: disabled delegates unchanged to native. `:51-67` validates owner and sample before scaling; `:69-86` preserves native event depletion/multipliers and increments only after a changed scaled-rate step changes stamina. Native `4_World/Classes/StaminaHandler.c:614-653` applies the rate, event costs, clamp, cap snap and authority sync. Native PlayerBase creates its handler at `4_World/Entities/ManBase/PlayerBase.c:414` and updates it at `:3300`. No source-only claim that the server ran an accepted sprint sample is warranted from the supplied excerpts.
- `mods/HollowCountry/scripts/5_Mission/Survival/HCStaminaHUD.c:88` gates on Enabled; `:239-245` shows the root before counting. It samples at most once per 0.25 s; none of its visibility guards or event counters were bypassed.

## Peer counters and activity audit

`mods/HollowCountry/scripts/4_World/Core/HCModuleReadiness.c:35` registers process-local slots. `:68` auto-registers on first real use and immediately prints the first positive value. `:146` emits cumulative counts; `:157` emits changed counts including the initial zero; `:255` resets the mission inventory; `:277` now declares these three client rows. `:302` intentionally declares client features on the server as well. Those server zeros are declarations, not failed replication: counters are not replicated.

`mods/HollowCountry/scripts/5_Mission/Operations/HCUseLifecycle.c:13` previously registered ClientUI (and radius observations) on the client. A client stamina/hint increment was already able to reach evidence without any server RPC because HCUse auto-registers and prints it. Missing client rows do not prove a broken dump or lost increment; they mean the event never reached HCUse. The new declaration makes that distinction visible even at zero.

`tools/release/activity_check.py:248` selects client-scoped regular activity signals separately. `:393-417` reads `--client-rpt` with its own clock and server module enablement. Release mode reads cumulative maxima from both RPTs (`:162`); `:64` and `:113` restrict release_smoke rows to non-fixture client counts. The HUD and hint rows use their exact counter feature names and scope=client/release_smoke=true; applied stamina and actor wakes are runtime rows. Without --client-rpt, server zeros cannot satisfy HUD or hints. The existing HUD expectation was named stamina-hud-shown; it is now stamina_hud_shown to match its release-counter key.

## Hints and placement limits

`mods/HollowCountry/scripts/5_Mission/Polish/HCHints.c:143-195` validates/opens the bounded state and starts fresh history at 30 s. `:264-285` advances one save stage per owner update and only queues a notification after commit with a living recipient and matching native ID. `:289` sets a shared 180 s cooldown before saving; `:324` offers context/condition hints then first-hour general guidance (topic 19 first for an ordinary fresh stand). `:353-404` needs a living player and nonempty ID, advances played time, suppresses menu/unconscious/absent notification system, and checks at 5 s intervals. Previously shown topics, interrupted files and invalid history are not replayed or silently reset.

Native `3_Game/DayZGame.c:2178` merely returns m_DatabaseID; `3_Game/Services/BiosUserManager.c:125-129` supplies it from OnUserDatabaseId. The cache does not document a filename-safe alphabet or prove it changes every life. The existing per-life claim therefore remains unqualified; the patch preserves ID matching and never substitutes an account fallback or prints the ID. An empty ID still waits and now explains why. A 185c-specific hints cause cannot be asserted without its ID/profile outcome. `3_Game/Client/Notifications/NotificationSystem.c:215-230` returns no handle and may defer when full; hint_shown proves a real native enqueue, not pixels or immediate visibility. New logs say queued accordingly.

`mods/HollowCountry/scripts/4_World/Infected/Variety/HCInfectedVarietyModule.c:276` counts currently living dormant/runner actors only. `:333` requires an erect player within 6 m and clear geometry for proximity wake. `:489-504` admits only calm eligible crawlers outside assigned/search groups, with corpse/catalog/authored context and available pose budgets; it does not place a dormant actor merely because a player joins. The fresh queue at `4_World/Infected/Variety/HCInfectedVariety.c:523-590` needs an admissible authored site, interest, hidden position and clearance. No placement fault follows from one zero census. `HCInfectedVarietyNative.c:184-203` returns true only when it actually clears dormant state; it does not itself call HCRecordWake. Consequently counting the bounded tick/shot returns at module `:170`/`:180` does not double-count its separately recorded native callback and damage wakes.

## Phase-map corrections for lead

Do not edit the phase map or driver in this worker.

- stamina_applied: sprint after client receipt, with enough stamina to change; boot/stand at full capacity is insufficient.
- stamina_hud_shown: real join plus enabled receipt, live conscious stand with closed menus and visible HUD.
- hint_shown: fresh valid unshown hint history, nonempty native ID, at least 30 s live play plus staged-save completion and closed menus. Returning history may need an unshown context and the 180 s cooldown; boot alone is not a claim.
- actor_woken: remove unconditional join/stand coverage. Use walk_town to find an eligible dormant actor, then stand within 6 m with sight, or exercise a controlled real noise/damage wake. Walk_forest is valid only if it actually encounters a qualifying actor. Movement alone is not proof.

## Next-run RPT evidence

Client should receive `Stamina client receipt staged=1 enabled=1 runtime=PENDING` (native bool formatting may be true/false), followed by `Stamina client HUD shown stamina_bar=1 weight_bar=1 runtime=PENDING`. Sprint should produce `[HC Use] module=SurvivalAlignment feature=stamina_applied count=1`; HUD should produce its corresponding client HC Use count=1.

For fresh valid hint state, expect `[HC Use] module=Polish feature=hint_shown count=1` and `Hints client notification queued runtime=PENDING`, then nonzero `V2 client hints shown=` at shutdown. Otherwise inspect `Hints client waiting reason=native_character_id_unavailable`, `Hints client state refused reason=id_or_profile_invalid`, or `Hints client save failed`. Those lines omit identity/path data. All three client zero rows should now exist even if the real events do not happen.

Server should print `Stamina server profile staged=... enabled=...`, and on a valid request `Stamina client config resent enabled=...`. Each handler logs first_step with enabled/authority once; the first rejected enabled sample logs owner/dt/stamina/cap/rate. These are diagnostics, never use-counter increments. A real proximity/shot wake must now increase actor_woken as well as the existing infected wake summary.

## Validation and handoff

Ran `timeout 900 agent-run --memory 2G -- python3 -B -m tools.validate.preland --native-scripts ~/.cache/hollow-country/native-scripts/scripts-1.30.164289 --changed 721e23c4` on the final source. Exit 1: enforce_lint pass (findings=0/new=0/stale=0/native=yes); enforce_perf pass (19 baseline/new=0/stale=0); layout, cfgconvert, settings consistency, wiring, mission sources, hygiene and event policy pass. Regeneration compared 16 available artefacts successfully and skipped five host-dependent checks. Staged CE mission was unavailable; world_mesh_audit reported 200 findings/581 skipped, an expressly permitted exception for this worker. No engine compile was invoked. Activity expectation loader accepted all four rows; git diff --check passed.

The additional, unresolved preland failure is generated_digests: all 16 receipts conservatively include every config JSON, including activity-expectations.json. A read-only comparison of local_snapshot against each stored inputs map found exactly one difference per receipt: config/activity-expectations.json. Its stored hash matches 721e23c4. This failure comes from this worker's authorized expectation changes, not unrelated baseline drift. Available fresh byte comparisons passed; receipt refresh still requires the lead's ownership of config/generated-digests.json and the unavailable host inputs for the remaining artefacts. That file was not edited. This handoff is not a claim of a clean preland/DONE gate. The detailed final output is in /tmp/v16-zerocounters-preland-final.log on this worker.

Additional native APIs used by the filename fix: `1_Core/proto/EnString.c:86` ToAscii, `:113` Substring, `:199` Length. The loop visits at most 128 ID bytes once at state open; it never runs a filesystem retry loop. The initial validation caught HC-E006 on the hex alphabet access; the final source explicitly checks its bounds and lint passes.

No SHA exists yet for these edits because this run cannot write git metadata. `.banso-writer/commit-message` contains the subject above for the automatic writer. The lead still needs next-run evidence to identify the server's zero accepted stamina steps and the particular 185c hint-state failure; the patch fixes established routing/filename/accounting faults and provides bounded diagnostics without inventing either outcome.
