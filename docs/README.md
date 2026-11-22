# Hollow Country handbook

Use the [field guide](../README.md) for the features, dependency stack and milestones.

| Purpose | Guide |
| :--- | :--- |
| Install, upgrade, recover and roll back | [Installation and rollback](INSTALL_ROLLBACK.md) |
| Friend server: mods each player needs, build and ports | [Friend server](INSTALL_ROLLBACK.md#friend-server-installation) |
| Connect to a local vanilla test server | [Local connection check](LOCAL_SERVER_TEST.md) |
| Configure and develop the addon | [Addon development](MOD_DEVELOPMENT.md) |
| Trigger and inspect HC features on a test server | [Admin test kit](ADMIN_TEST_KIT.md) |
| Understand component boundaries and current gates | [Module status](MODULE_STATUS.md) |
| See every outstanding feature, fix, audit and owner question | [Outstanding work](OUTSTANDING.md) |
| Review shared runtime interfaces | [Runtime integration contract](RUNTIME_IMPLEMENTATION_CONTRACT.md) |
| Keep module tick, save and log cost bounded | [Performance practices](PERFORMANCE_PRACTICES.md) |
| Review ownership and dependencies | [Provenance and licenses](PROVENANCE_AND_LICENSES.md) |
| Find official documentation | [Sources](SOURCES.md) |

Internal specifications, interviews, agent state, machine inventories and raw
experiment records are local development material. They are excluded from Git.
Track deliverables through [issues](https://github.com/d-addison/hollow-country/issues)
and [milestones](https://github.com/d-addison/hollow-country/milestones).

See [tools](../tools/README.md) for commands and [tests](../tests/README.md) for
portable regression checks. Passing offline tests does not establish gameplay,
multiplayer, persistence or production capacity.

## Living Country — V2 operations

Living Country supplies persistent world history, finite supplies, camps, situations,
AI activity and client presentation in the test build. Features default on with
operator opt-outs. *In-game test pending*. Acceptance uses DayZDiag and a normal
PBO/server with at most one client. No gameplay verdict is recorded for the current build.
Compilation, startup and offline checks do not establish one.

The server reads these booleans from `$profile:HollowCountry/settings.json`.
All default to `true`. Preserve explicit operator choices; module-owned profile
fields have their own defaulting and validation rules. The complete [settings
reference](../README.md#server-settings-reference) lists shared and module tuning.

| Preference | Default | Server scope |
| :--- | :--- | :--- |
| `EnableGrade` | `true` | Grade/lighting admission diagnostics and weather-day profiles |
| `EnableAmbientLife` | `true` | Optional animal presence diagnostics and polish admission diagnostics |
| `EnableSignsOfLife` | `true` | Signs-of-life server module |
| `EnableTravel` | `true` | Shelters, wreck salvage and travel discovery pins |
| `EnableWorld` | `true` | World ledger, escalation, settlement decay, infected memory, horde migration and loot refresh |
| `EnableLeads` | `true` | Leads, radio, Morse clues, notes, body stories and received-lead pins |
| `EnableCamps` | `true` | Camp recognition, tiers, visitors, mailbox, theft eligibility and probes |
| `EnableEncounters` | `true` | Materializer, faction conflict, hold-outs, pickers, dead drops, scenes and optional AI encounters |

Stop the server, back up the profile, change the existing flag to a JSON boolean
such as `"EnableCamps": false`, then restart. Preserve the other settings and state
files. Check `[HollowCountry] V2 preferences ` for the resulting value. Inspect `HCV2Admission` and operational status lines for requested, off and degraded owners. `HCGetOperationalStatus` / `HCOperationalStatus.HCPublish` derive readiness from current dependencies; `ready` is not a gameplay verdict. Map pins share a
module that starts if either Travel or Leads is on; each pin kind follows its flag.

Client grade, lighting, signs of life, hints and environmental sound run locally
and default on; server flags do not transmit a client off switch. Bind the grade
control in DayZ's Controls and cycle to 0% to turn the grade off (default 60%).
Installed CE/config overlays also need their own rollback: setting a flag false
does not undo mission XML. For optional packs, stop the server and use the included
`tools/package/optional_overlays.py rollback --mission <mission>` before rolling
back any underlying CE installation. Existing persisted bikes/animals are retained.
Weather days additionally respect `EnableAtmosphere` and the existing delegated
weather owner.

In the server profile's `.RPT`/script logs, search for
`[HollowCountry] V2 admission feature=` (emitted by the `HCV2Admission` helper). For example, grade startup emits:

```text
[HollowCountry] V2 admission feature=Grade preference=on gate=EXP-A1 qualified=0 result=admitted unverified: EXP-A1 has no recorded native verdict
```

The preference admits a V2 module; the experiment verdict is diagnostic. An
admission line proves neither successful behaviour nor acceptance. Check subsequent
dependency, clock and persistence diagnostics too. Gate-free modules can emit
`gate=none qualified=1`; that also records no gameplay acceptance. Per-feature
steps and exact log substrings are in the [V2 acceptance checklist](LOCAL_ACCEPTANCE_V1.md#v2-living-country-scaffolding).
Client script logs include `[HollowCountry] V2 client grade intensity=`,
`[HollowCountry] V2 client lighting blend=`,
`[HollowCountry] V2 client signs of life lit=` and
`[HollowCountry] V2 client morse clues on; holder-only RPC; native acceptance pending`.

Keep the following V2 files with the server profile under `$profile:HollowCountry/`;
back up the whole directory with the server stopped. Files appear as their modules
run and save, rather than all being created at every startup.

| Profile file or directory | Contents |
| :--- | :--- |
| `settings.json` | Feature preferences and shared limits |
| `world.json`, `escalation.json` | World ledger and persistent escalation epoch |
| `settlement-decay.json`, `infected-memory.json` | Settlement history and infected clues |
| `leads.json`, `morse-rates.json` | Group leads, note/body reservations, radio channels and Morse rate limits |
| `holdouts.json`, `pickers.json`, `dead-drops.json`, legacy `CacheMoves/` (v1-test-5..9 only; old files left on a server are orphaned and harmless) | Encounter state and real-item transfer journals |
| `camps.json` | Camps, tiers, visitors, mailbox receipts, theft journal and probes |
| `scene-chains.json` | Scene stage and expiry state |
| `wreck-salvage.json`, `search-refresh.json` | Finite wreck supplies and search revisit history |
| `ask-for-news.json`, `ask-for-news.pending.json` | Physical-signal cooldown state and pending intent; no dialogue or quest flow |
| `expansion-ai.json`, `expansion-ai-sites.json` | Optional AI provider and reviewed-site configuration |
| `expansion-ai-leases.json`, `expansion-ai-leases.pending.json`, `expansion-ai-routes.json`, `expansion-ai-caches.json`, `expansion-ai-owned.json` | Optional AI leases, routes, caches and ownership state |

Keep adjacent `.tmp`, `.bak` and rejected images for recovery if a load fails;
do not delete them to force a fresh ledger. On the client, hints write
`$profile:HollowCountry/Polish/Hints/<characterId>.json` (with temporary/backup
images), while grade intensity uses the native profile key
`HollowCountryGradeIntensity` rather than a separate JSON file. Friend bundles
omit runtime state and local acceptance markers.

Server and clients use the [required stack](../README.md#required-mod-stack),
ordered by [the dependency manifest](../tools/setup/workshop_mods.json): CF, COT,
Dabs Framework, Expansion-Core, Expansion-Licensed, Expansion-Vehicles,
Expansion-AI, Expansion-Navigation, the weapons packs, RaG_Core, RaG Immersive
Vehicles, Ambient Animals Pack,
`@HollowCountry`, then `@HollowCountryExpansionAI`. Licensed and Vehicles are
active dependencies. The 23 added Expansion vehicle types and finite repair parts
are event-owned; four rare aircraft share the air budget. The landing incident
hook lives in the Expansion AI addon after the vehicle scripts.

Expansion-Animations is intentionally not loaded; Expansion-AI supplies its own AI
animations. Survivor Animations and DayZ-Bicycle were retired on 2026-11-22.

The Ambient Animals overlay applies by default during friend-bundle install.
The original Workshop items remain separate subscriptions; no third-party file is
repacked or distributed. Install-time CE changes do not establish gameplay acceptance.

## Coverage in this build

Source data resolves 88 localities, 528 finite AI sites and 523 story sites, plus
connected road candidates and habitat membership. The package contains 294 paged
interior templates. Another 69 shelter scene candidates require shared catalog
registration; road paging/site binding and indexed story consumption remain
integration gaps. None of these counts is native acceptance or a raised live cap.
The broad item pass was reverted in `0321022f` and is being redone as curated
vanilla-only acquisition coverage; see [Outstanding work](OUTSTANDING.md).

## Current operator controls

The [settings tables](../README.md#server-settings-reference) include the landed
convoy, perception-ring, helicopter, hearth, AI timer, leaf, performance and
module tuning fields, plus camp/group limits, world save/retention scheduling,
search retries/journals, local policy, body stories and actor reach/defence. Separate profiles
use unprefixed fields; shared
`PerceptionRing` is a nested object in `settings.json`. Existing operator-edited
AI defaults are retained; unchanged mod-written profiles can migrate with backups.

- Grant COT permission `HollowCountry.Admin` or configure the private HC allowlist.
  Connected-player permissions are checked on each request, including revocation.
  `COTAuthorization.disable` disables COT-based grants; `AdminControls.disable`
  disables world controls. `campvisit` and `campraid` include eligible claim-only
  bases; `camptier` remains hearth-only. Older admin/COT guides may predate this binding.
- Picker groups contain 2–6 members and carry up to three house goods through
  finite player/AI reservations. Full crates retain goods on carriers; death and
  restart never replay transfers. Keep the custody journal with world/Hive backups.
- Variety mission `MaxPosed=12` caps server-wide poses; 0 stops new posed holds.
  `PosedFreshEvery=3` selects the authored sitter when its addon exists. Sleep,
  lying-rise and kneeling-feed sources/graph states are authored and
  admitted unverified; native build, skinning and playback remain pending.
- Taped helmet/pack receipt `Disabled=true` applies to the actual mounted pair.
  `taped_light.disable` also disables their shared adapter; missing native slots
  refuse only the affected pair. Beam geometry and replication need one client.
- Client `auditleaves_settings.json` enables bounded autumn canopy leaves by
  default; `Enabled=false`, `season_leaves.disable` or native profile key
  `HollowCountrySeasonLeaves=0` opts out. A zero grade also stops the effect.
- Wildlife observation and requested animal goals publish separate status.
  `world_incidents.disable` makes clues unavailable while independent
  carcass/contact work continues. Animal goals are admitted unverified; the
  inspected native APIs supply no safe animal destination/target/feeding port.

Inventory rollback now generates an unsigned replacement addon with a config
diff and receipt from `--addon-source` or `--addon-pbo` plus `--pbo-out`. Review,
sign and install it separately; runtime flags cannot undo installed overlays.
Package hash-cache merges use OS-held locks; stop older lock-file builds before
switching protocols. Windows contention and crash recovery remain unverified.

After boot inspect `feature=NativeIncidents`, `[HC Plan] HC-41`,
`W2_OBSERVATION_AVAILABLE`, `AUDITWILD_MEMORY`, `AUDITWILD_GOALS_PENDING` and
`feature=WildlifeGoals`. Loose CE crash loot reports
`CE_CRASH_LOOSE_STOCK_ATTRIBUTION_PENDING` with
`reason=CE_INSTANCE_MEMBERSHIP_API_UNEXPOSED`; direct live-crash cargo ancestry
is available. An operator-disabled incident registry reports `W2_CLUE_DEPENDENCY`.
`[HC Pickers] run goods=` is an activity log, not a boot log. All remain
`runtime=PENDING` until observed on DayZDiag and a normal packaged server.
