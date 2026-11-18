# Hollow Country handbook

Use the [field guide](../README.md) for the component overview and roadmap.

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

V2 is **being built / runtime acceptance pending**. Its systems are in the
development build and on by default; dedicated-server compilation and startup
do not establish gameplay acceptance. Multiplayer behaviour awaits group sessions.

The server reads these booleans from `$profile:HollowCountry/settings.json`.
All default to `true`, including when absent from an older settings file.

| Preference | Default | Server scope |
| :--- | :--- | :--- |
| `EnableGrade` | `true` | Grade/lighting admission diagnostics and weather-day profiles |
| `EnableAmbientLife` | `true` | Optional animal/bicycle presence diagnostics and polish admission diagnostics |
| `EnableSignsOfLife` | `true` | Signs-of-life server module |
| `EnableTravel` | `true` | Shelters, wreck salvage and travel discovery pins |
| `EnableWorld` | `true` | World ledger, escalation, settlement decay, infected memory, horde migration and loot refresh |
| `EnableLeads` | `true` | Leads, radio, Morse clues, notes, body stories and received-lead pins |
| `EnableCamps` | `true` | Camp recognition, tiers, visitors, mailbox, theft eligibility and probes |
| `EnableEncounters` | `true` | Materializer, faction conflict, hold-outs, pickers, dead drops, scenes and optional AI encounters |

Stop the server, back up the profile, change the existing flag to a JSON boolean
such as `"EnableCamps": false`, then restart. Preserve the other settings and state
files. Check `[HollowCountry] V2 preferences ` for the resulting value. Each V2 module must print exactly one `HCV2Admission` line, including disabled modules; verify this in the native server log. Map pins share a
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
| `holdouts.json`, `pickers.json`, `dead-drops.json`, `CacheMoves/` | Encounter state and real-item transfer journals |
| `camps.json` | Camps, tiers, visitors, mailbox receipts, theft journal and probes |
| `scene-chains.json` | Scene stage and expiry state |
| `wreck-salvage.json`, `search-refresh.json` | Finite wreck supplies and search revisit history |
| `ask-for-news.json`, `ask-for-news.pending.json` | Talk rate-limit state and pending intent |
| `expansion-ai.json`, `expansion-ai-sites.json` | Optional AI provider and reviewed-site configuration |
| `expansion-ai-leases.json`, `expansion-ai-leases.pending.json`, `expansion-ai-routes.json`, `expansion-ai-caches.json`, `expansion-ai-owned.json` | Optional AI leases, routes, caches and ownership state |

Keep adjacent `.tmp`, `.bak` and rejected images for recovery if a load fails;
do not delete them to force a fresh ledger. On the client, hints write
`$profile:HollowCountry/Polish/Hints/<characterId>.json` (with temporary/backup
images), while grade intensity uses the native profile key
`HollowCountryGradeIntensity` rather than a separate JSON file. Friend bundles
omit runtime state and local acceptance markers.

The default subscribed stack loads CF, Dabs Framework, Expansion-Core, Expansion-AI,
the weapons packs, Ambient Animals Pack, Survivor Animations, DayZ-Bicycle,
`@HollowCountry`, then `@HollowCountryExpansionAI` on server and every client.
The [friend server guide](INSTALL_ROLLBACK.md#friend-server-installation) lists the IDs and exact installed folders.

Expansion-Animations is intentionally not loaded: it conflicts with Survivor Animations, which DayZ-Bicycle requires; Expansion-AI brings its own AI animations.

Bicycle and Ambient Animals overlays apply by default during friend-bundle install.
The original Workshop items remain separate subscriptions; no third-party file is
repacked or distributed. Install-time CE changes do not establish gameplay acceptance.
