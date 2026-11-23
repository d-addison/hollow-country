# Optional PvE AI data

## Human AI limits (owner request 2026-11-18)

Edit the `AILimits` object in `$profile:HollowCountry/settings.json`, then restart.
The shipped template is `config/hollow-country-settings.json`; mission packaging
also carries `operator/settings.json`. Existing settings staging is reused, so
there is no second profile file to copy. `HCSettings.LoadFromProfile` creates
missing defaults with the existing bounded JSON loader. A pre-existing settings
file is preserved; an absent AILimits section keeps the constructor defaults.
`python3 -B -m tools.validate.runtime` validates the template before staging.

All keys are integers. An out-of-range value logs one `[HC AI] invalid
AILimits.<key> value=... default=...` line and restores that key's default. A
reversed min/max pair logs its two key names and restores the pair. Invalid JSON
or non-integer JSON that the native typed loader cannot decode still follows
the existing settings-file refusal; the Python validator reports those types.
The effective startup line begins `[HC AI] limits groups=15 ai=72 occupation=3-8`
and includes every key, `provisional=1 runtime=PENDING`.

| Key (inside AILimits) | Default | Valid range | Meaning |
|---|---:|---|---|
| `MaxLiveGroups` | 15 | 1..24 | Combined live/reserved human AI groups; pending full groups count. |
| `MaxLiveAI` | 72 | 1..128 | Combined human AI actors, including deferred members and unknown custody. |
| `OccupationMin` | 3 | 1..12 | Minimum new town/house occupation (Expansion house sites). |
| `OccupationMax` | 8 | 1..12 | Maximum new town/house occupation. |
| `HoldoutMin` | 3 | 1..12 | Minimum new base world holdout population. |
| `HoldoutMax` | 6 | 1..12 | Maximum new base world holdout population. |
| `PartyMin` | 2 | 1..12 | Minimum new travelling/scavenger party. |
| `PartyMax` | 6 | 1..12 | Maximum new travelling/scavenger party. |
| `PatrolMin` | 2 | 1..12 | Minimum new patrol/checkpoint population. |
| `PatrolMax` | 5 | 1..12 | Maximum new patrol/checkpoint population. |
| `CampMin` | 2 | 1..12 | Minimum settled camp refugee group (currently abstract). |
| `CampMax` | 6 | 1..12 | Maximum settled camp refugee group (currently abstract). |
| `MaxOccupiedPlaces` | 15 | 1..64 | Occupied logical holdouts (not an extra live-AI allowance). |
| `MaxParties` | 24 | 1..128 | Persisted logical parties. |
| `MaxMaterialized` | 15 | 1..24 | Simultaneous materializer proposals/leases, including custody debt. |
| `FactionStrengthMax` | 24 | 1..128 | Maximum abstract faction strength; not live bodies. |
| `MaxActiveSites` | 15 | 1..24 | Expansion authored plus transient site sub-budget. |
| `MaxActiveAI` | 72 | 1..128 | Expansion site actor sub-budget; cannot bypass MaxLiveAI. |
| `MaxEncounters` | 15 | 1..24 | Simultaneous event bindings to existing owned patrols. |
| `MaxHoldouts` | 48 | 24..128 | Persisted holdout/catalog rows; minimum retains the old 24-row capacity. |
| `MaxCamps` | 32 | 1..128 | Persisted player camps; these are not AI groups. |
| `MaxCampItems` | 64 | 1..128 | Item reference capacity per camp (the old CAMP_MEMBERS name meant items). |
| `MaxObservedAI` | 1024 | 1..8192 | Diagnostic scan ceiling; independent of admission so excess external AI remains visible. |
| `WorldSeed` | 18473 | 0..1000003 | Stable world population seed; change deliberately, never to refill survivors. |

The group/actor safety ceilings are 24/128, and each group has at most 12 members.
Sub-budgets may be larger than the global budget; the shared reservation still
wins. The default 72 actors can therefore prevent reaching 15 groups when many
large groups are active. Size selection is a bounded deterministic hash of
`WorldSeed` and stable row/site ID, inclusive of its kind's min/max; it does not
use process RNG or player count. `EnableGroupScaling` no longer changes human AI
populations. Existing survivors and durable populations are preserved rather
than increased to a newly selected group size. The legacy surveyed adapter selects a stable configured patrol size from an
unchanged prefix of surveyed spawn points. It refuses insufficient surveyed
positions rather than inventing coordinates; it is not the live event-provider path.

Legacy `MaxActiveAI` / `MaxActiveSites` in expansion-ai-sites.json are normalized
from AILimits on load, without rewriting the operator's file. Legacy adapter
MaxGroups/MaxActors remain compatibility/qualification data, not live capacity
controls. Site NumberOfAI/NumberOfAIMax templates advertise occupation 3..8,
patrol 2..5 and scavenger 2..6; Create chooses one fixed configured size. Routes,
loadouts, finite ammo, distance/visibility and qualification gates still apply.

`HCAIBudget` is the combined server reservation ledger. Materializer proposals
reserve before dispatch; transient sites reuse the exact lease ID. Authored
sites reserve before native Spawn, and the legacy adapter reserves before its
first journal/provider side effect. Full deferred populations stay charged.
The existing result/retirement paths release only after observed absence (or a
creation refusal with no bodies). On process startup, HC-10 CLAIMED rows finish unknown because transient groups
use Persist=false; their budget and identity/cargo custody return to the owner
store without replaying inventory or casualties. Quarantined debt remains held,
including above lowered limits. Unreadable custody blocks admission. No timeout
frees an in-process claimed group. External provider patrols must remain disabled.

Old 24-holdout / 12-party / 32-camp / 64-item saves fit the shipped limits.
Lowering below stored counts refuses loading with a log: holdout/camp stores
preserve the file; world.json uses its existing rejected-image/backup recovery
and fresh-world path. Back up world.json, holdouts.json, camps.json, ai-custody.json
and engine inventory together. Lower group-size limits do not refill or rewrite
old groups; saved member counts are validated against the 12-member safety
ceiling and only the configured maximum can be proposed.

Budgets are provisional until measured with 3–6 players. DayZDiag and normal
PBO/server acceptance, restart/custody recovery and two-client spawn visibility,
audio and replication checks remain pending. No engine experiment is accepted
by the offline tests. See [implementation record](#implementation-record-ai-caps-2026-11-18) for
the cap inventory, spec/plan/tasks, verification and native checks.

## V2 living people (LC-T401 HCX, T403–T406, T410)

The owner decision of 2026-11-17 admits these features when `EnableEncounters`
is true. `HCXLivingModule` self-registers without a core hook and prints one
`HCV2Admission` line each for Factions / EXP-L2, Stance / EXP-L3, AskForNews /
EXP-L6 and Checkpoints / EXP-L1. Experiment verdicts are diagnostic; an
`admitted unverified` line does not establish native acceptance. This preference
also admits the existing site director without its older acceptance marker.
With the preference false, the old marker still controls the older site path;
the new checkpoint sites, stance and news service stay off.

**Client packaging requirement:** load `@HollowCountryExpansionAI` with `-mod`
on both server and clients, after its Expansion dependencies and HollowCountry.
The local launcher, friend-bundle launcher and Workshop tooling now place it at
the end of the shared `-mod` list. Players subscribe to it when the server uses it.
Both peers need the faction
registrations and optional news target binding. The base action has no Expansion
dependency and offers no target without that binding.

`HCXFactions.c` registers original classes using the installed
`ai_scripts.pbo` extension attribute (`1_Core/DayZExpansion_AI/eAIRegisterFaction.c:6–21`;
World-layer precedent `4_World/DayZExpansion_AI/Factions/eAIFactionInfected.c:1–2`).
The reconciliation IDs are strings only: Locals (Zimovniki), Volunteers
(Dobrovoltsy), Scavengers (Sborshchiki), Raiders (Volki), Travellers. Each faction
is friendly to itself; Locals and Volunteers are allied; Raiders oppose the
other four; all remaining pairs are neutral. Site patrols map to Volunteers,
scavenger parties to Scavengers and holdouts to Locals. Raider and Traveller
classes are available to later materialization; this change adds no raider spawn.

Admission refuses and logs unlimited reload, recruiting, provider patrols,
looting other than NONE, or a provider route differing from the qualified static
route. No player coordinates are injected into the provider. The existing lower
accuracy, reduced awareness, melee variants and finite loadouts are retained.
The shared `AILimits` policy below defaults to 15 live groups / 72 live AI
across materializer, sites and the legacy adapter. These are provisional budgets. The module checks one owned actor
per tick and stops its player aggression if admission drifts.

Stance consumes only weapon raised/lowered, distance, nearby delivered gunfire
and static faction relation. Native provider perception must establish LOS and
a fresh native ray must agree. A raised weapon inside the caution range gets
the AD-04 hold emote plus text, followed by aim after two seconds and possible
hostility after eight seconds of continued observation. Lowering clears the
warning and active aggression. Lost LOS or a stale observation restarts the
warning. If the emote or notification slot is unavailable, escalation waits.
One shared limiter allows at most one warning/news notification per player per
30 seconds; identity is used only for that delivery quota, never stance.

The native **Ask for news** action revalidates a living, non-hostile AI and a
nearby living player on the server. It greets and invokes
`HCAskForNews.Rumour(vector pos)`, currently returning `""`; the honest fallback
is “Nothing new to tell you.” The world-ledger wave fills the hook with a real
recent event. There is no fabricated rumour or location feed today. A receipt
limits each stable site/member slot and server-owned group (solo players get a
solo quota) to one response per 86,400 real UTC seconds, including restarts.
The existing Groups service must be healthy to resolve that quota; unavailable
group state refuses talk rather than assuming a new solo group.
`$profile:HollowCountry/ask-for-news.json` has a bounded 256-row journal. Save
uses a verified pending file, backup and verified copy, following the installed
native file APIs; no native rename exists in the inspected dump. A pending file,
corruption or clock rollback refuses talk. Preserve the pending file and recover
the journal deliberately; publication is guarded, not an atomic rename.

Two additional source-reviewed **candidate** road-entry checkpoints are
`checkpoint-komarovo-east` and `checkpoint-novaya-south`, each with 2–3 Volunteer
guards. Their `Reviewed` flag records source review only. They reuse the existing
build/world, observer, route/navmesh, spawn and member admission. Coordinates
are authored proposals, not surveyed road or navmesh evidence. An empty native
`Land_Roadblock_Table` is placed independently of guard availability, only when
unobserved beyond 200 m for five seconds and clear of buildings within 25 m.
The fallback refuses unsafe/overfull surroundings and does not add loot,
barriers or door blockers. Existing nearby tables are adopted on restart.

Server grep strings (these are expected logs, not observations):

```text
[HollowCountry] V2 admission feature=Factions preference=on gate=EXP-L2
[HollowCountry] V2 admission feature=Stance preference=on gate=EXP-L3
[HollowCountry] V2 admission feature=AskForNews preference=on gate=EXP-L6
[HollowCountry] V2 admission feature=Checkpoints preference=on gate=EXP-L1
[HollowCountry] Living AI admission refused:
[HollowCountry] Stance warning: emote + text; lower weapon to de-escalate
[HollowCountry] Stance de-escalated: weapon lowered or outside caution range
[HollowCountry] Stance hostile: raised weapon persisted after 8s warning
[HollowCountry] AskForNews ready: server validation; one per NPC/group/86400s; rumour hook empty
[HollowCountry] AskForNews answered: npc=
[HollowCountry] AskForNews refused:
[HollowCountry] Checkpoints props present:
[HollowCountry] Checkpoints prop refused:
```

Client: `[HollowCountry] V2 client AskForNews action registered; optional HCX target binding required`.
The new synthetic smoke verifies the authored policy signature and lowering;
it never establishes DayZ behaviour. Native compile, DayZDiag, normal PBO/server
testing, faction synchronization, warning timing/aim and two-client visibility,
emote/notification and action checks remain pending. So do target-load budgets,
checkpoint surveys, ledger integration and a true warning-shot experiment.

## HC AI sites (shipped, the default when the addon runs)

`sites.json` is our own site policy: 9 patrols (4 town police stations, the 2
village police stations that anchor the event sites, 3 military sites), 5 scavenger parties of 2–3 that roam qualified routes between loot
buildings, and 5 holdouts of 2–3 survivors who keep to one house with one
`WoodenCrate` or `SeaChest` cache, plus the two V2 checkpoints above. The older
nineteen sites' coordinates were chosen once from the
stock `mapgrouppos.xml`/`mapgroupproto.xml` (read only; no dump is committed) by
`python3 -m tools.package.ai_patrols sites --mapgrouppos ... --mapgroupproto ... --out ...`.
`loadouts/HollowCountry_{Patrol,Scavenger,Holdout}.json` are Expansion loadout
files with finite, partly filled magazines.

Install paths (the local test launcher `--expansion-ai` installs all of them,
with backups, and its rollback restores them):

| Source | Server path |
| :--- | :--- |
| `sites.json` | `$profile:HollowCountry/expansion-ai-sites.json` |
| `loadouts/*.json` | `$profile:ExpansionMod/Loadouts/` |
| `AIPatrolSettings.override.json` | `$mission:expansion/settings/AIPatrolSettings.json` |
| `AISettings.merge.json` | field merge into the existing `$profile:ExpansionMod/Settings/AISettings.json` |

At start `HCXAISiteDirector` admits the sites only when the engine build and
world match the policy, the addon and its dependencies are in `CfgPatches`,
Expansion AI and AIPatrol settings are loaded with recruiting off and no
unlimited reload, every loadout file exists, the observer is native eAI
perception and either V2 `EnableEncounters` admits the director or no
`pve_patrols.disable` opt-out marker is present (the patrols are on by default).
It then binds holdouts to their
house (nearest object of `HouseClass`), qualifies each route by navmesh
sampling and `FindPath` (at most 4 work items per tick), and caches the result
by SHA-256 of route plus build in `$profile:HollowCountry/expansion-ai-routes.json`.
Each qualified site becomes an `eAIDynamicPatrol` that Expansion's own trigger
spawns when a player is inside `ActivationRadius`; HC refuses the spawn within
`MinPlayerDistance` (200 m) of a player, in a player's line of sight, or past the
shared `AILimits` budgets (15 groups / 72 AI by default), checks each later group member at the formation point
Expansion is about to use (same distance and sight rules; a refused member ends the
group at the members already placed), refuses despawn while the group is in combat, and forces
fair actors (finite reload, multipliers 1). Owned groups are journaled in
`expansion-ai-owned.json`; on restart any `HC:` group left over is despawned.
Holdout caches are journaled in `expansion-ai-caches.json` before any item is
created: seeded once per lifecycle, refilled only after the crate was emptied
and `CacheCooldownSeconds` passed, never while a player is near.

The diagnostic marker `$profile:HollowCountry/acceptance/xai_diagnostic_spawn.enable`
(off by default, never installed by the launcher) spawns the first site of each
kind once with no player, for Wine observation only.

## Event encounters (AI_ENCOUNTER)

When the event runtime starts an `AI_ENCOUNTER` (family 5) mission at
`coastal-police-source` or `inland-police-source`, `HCXAIEncounters` binds it to
an already-owned, route-qualified site patrol whose nearest route point is within
that site's `ActivationRadius` of the event anchor (`police-komarovo` and
`police-novaya-petrovka` are authored for this). It never spawns, moves, equips
or deletes an actor; the patrol stays director-owned and keeps every rule above.
Kills count only when the killed AI belongs to the bound patrol's native group.
At most 8 encounters are open at once; a refused or ended mission releases its
lease once. Lines to look for:
`[HC Expansion AI] encounters armed: session=xai-...`,
`encounter bound: lease=... site=...`, `encounter refused: ... nearest=... reason=...`
and `encounter kill observed: ...`. The authored waypoints are a proxy; the native
`site <id> route qualified` line is the evidence that a route exists.

## Retired lease-path examples

The earlier lease path (an operator `$profile:HollowCountry/expansion-ai.json`
policy, a local hook port and receipt verifiers) is retired: the addon no longer
loads that file and nothing installs it. The examples below are kept only for the
offline validator.

`patrols.example.json` contains one two-person finite-ammo example for each of the
existing reviewed police source sites. These are authored route proposals, not
surveyed placements. Their empty `SurveySha256` deliberately fails native profile
admission. The spawn heights and walkable paths must be measured in DayZ; do not
copy these routes into a live admitted profile until that work is complete.

The events boundary is only `Id` plus `Position` in world metres `[x, y, z]`.
`event-sites.contract.json` snapshots those fields and the source-review flag from
`HCEventSites.ChernarusPlus()`; it is not a second events configuration. IDs are
case-sensitive; anchors must match exactly. When the events site list changes, update
that snapshot and the routes in the same change.

Validate the examples against the snapshot:

```sh
python3 -m tools.package.ai_patrols \
  --patrols mission/hollow-country/ai/patrols.example.json \
  --sites mission/hollow-country/ai/event-sites.contract.json
```

The tool requires a JSON object containing `Sites: [{Id, Position, Reviewed, ...}]`; all
reviewed sites must have exactly one patrol. Bounds, IDs, exact anchors, group
sizes, route lengths, ammunition and loadout hashes are checked. Exit 0 means
structurally valid; `qualified` is always false. The loadout digest is SHA-256 of
UTF-8 JSON with sorted keys, compact separators and finite numbers only. A survey
digest is a reference to actual evidence, never an opt-in substitute.

These examples are not merged anywhere; the encounter path above uses the
shipped site patrols instead.

`AISettings.merge.json` is a field merge into the owner's existing
`$profile:ExpansionMod/Settings/AISettings.json`, not a replacement settings file.
Preserve all other fields and its version. Pinned Expansion reads this profile
file in `ExpansionAISettings.OnLoad()`; the source evidence was recorded in the local W1.1 report (not shipped).
There is no supported global `UnlimitedReload` JSON field in that class. Keep
Expansion admin unlimited-reload controls OFF; any nonzero effective global mask
closes HC admission even if this merge and the per-actor finite setting are used.

The merge also lowers Expansion's global aim and awareness (stock defaults: accuracy
0.35–0.95, threat 1000 m, noise 500 m, flanking 200 m) to accuracy 0.15–0.45, threat
300 m, noise 150 m and flanking 50 m, for any Expansion AI not spawned from our
sites. Site patrols set their own lower values per kind in `HCXAISiteRules`
(scavengers worst at 0.10–0.30). Damage multipliers stay 1.0. In each loadout some
`WEAPON` sets are melee only, and they use only items Expansion accepts as melee
(vanilla Shoulder/Melee slot). How this feels in play has not been observed yet.

The patrols are on by default. The server-only opt-out is the empty file
`$profile:HollowCountry/acceptance/pve_patrols.disable`, cached until restart.

## Expansion's own patrols

HC events own AI spawning. Pinned Expansion AI 1.9.84 otherwise generates
`$mission:expansion/settings/AIPatrolSettings.json` with `Enabled: 1` and default
patrols (police and wreck object patrols plus roaming patrols) that spawn when a
player comes near, with their own loadouts and reload rules. `AIPatrolSettings.override.json`
is our configuration, not an Expansion file, installed at
`<mission>/expansion/settings/AIPatrolSettings.json` (the launcher backs up any existing file).
It sets `m_Version` to the pinned `VERSION` (32), so Expansion loads it without
converting or saving, and `Enabled: 0` with no `Patrols`, so `eAIDynamicPatrol`
creates no provider-owned patrols. HC still creates its own qualified native
patrols directly. `AILocationSettings.json` only holds roaming waypoints and no-go
areas and needs no change. `tools/setup/wine_compile_probe.py --expansion-patrol-settings` stages
it into a disposable mission copy; any rewrite by Expansion is reported as drift.

## Readiness

The addon has no operator policy file. At start it logs that the lease path is
retired, then `HCXAIEncounters` arms once the site director reaches `run`
(ownership reconciled, routes qualified, patrols created) and takes its own
session token `xai-<ownership session>-<UTC seconds>` for the lease journal. The
line `[HC Expansion AI] readiness (...) AI_ENCOUNTER Ready=...` reports the
encounter state, the site phase, the qualified patrol count, the Expansion AI
settings state and any unfair globals. `Ready=1` means encounters can bind, not
that one has been observed in play.


## Implementation record: AI caps 2026-11-18

Source/package implementation against main `0413ad6` in `hc/ai-caps`. No commit,
staging, publication, native server run or client connection was performed by
this worker. Source stays private. Runtime acceptance and production enablement
remain pending. The owner requested larger, varied groups and up to 15 groups;
all budgets remain provisional until measured with 3–6 players.

### Prerequisite: HC-10 (separate change)

HC-10 (`fix(ai): persist materializer party and cargo custody`) landed before this
task. It added `HCAIPartyIdentity.c`, materializer custody persistence and bridge
custody/lifecycle handling. The limits work then
replaces HC-10's inherited four-actor reservation ceiling with the shared
12-member safety ceiling. The review fix below resolves prior-process claims
without replaying cargo, recycles completed identities after cooldown, and keeps
in-process CLAIMED/QUARANTINED identities exclusive. Claimed bodies are never
released by a timeout.
### Spec, plan and tasks

The repository instruction names `docs/SPECIFICATION.md` and
`docs/specs/001-survival-overhaul/spec.md`. Those files are absent from this
worktree; their existing counterparts in the lead checkout were read without
editing them. They are design input, not runtime evidence. The active owner
request overrides previous small pilot populations. This bounded change extends
LC-T402/materializer, T403–T406/living people, T410/camps and the HC-10 custody
contract; it does not accept missing EXP-L1/EXP-P2 experiments. Banso lifecycle
state is dispatcher-owned; this is the worker's spec/plan/task trace.

| Requirement / behavior | Implementation task | Source/offline status | Runtime status |
|---|---|---|---|
| One validated operator policy, default 15 groups / 72 actors | Add `HCSettings.AILimits`, reuse existing profile staging/loader and validator, print effective values | Implemented | DayZDiag / server startup pending |
| Occupation 3–8, holdout 3–6, party 2–6, patrol 2–5, camp 2–6 | Stable bounded hash of explicit WorldSeed and row/site ID; fixed provider population per group | Implemented | Geometry / native placement pending |
| Combined capacity across every human spawn path | Shared reserve-before-side-effect ledger; transient bridge reuses materializer ID | Implemented | Two-client deferred spawn/retirement pending |
| Preserve old saves and uncertain custody | Raise capacities; migrate canonical custody v1; finish prior-process claims unknown; retain quarantines | Implemented | Real save/restart/recovery pending |
| Operator-visible and traceable tuning | Key/range table, cap inventory, effective startup line and module status | Implemented | RPT confirmation pending |
| RED → smallest change → GREEN; full regression selection | Authored policy tests with explicit synthetic DTO/native/provider ports | Recorded below | Offline tests cannot establish DayZ behavior |
| Target load and production enablement | Measure 3–6 players; validate two-client audio/visibility/replication, normal PBO/server | Deferred | Pending; no measured budget accepted |

The plan uses the existing settings loader rather than a new ai.json because
settings.json already has bounded typed JSON loading, first-run provisioning,
operator staging, validation and startup ownership. A second file would duplicate
that path and its copy order. Existing files without AILimits retain defaults.
No HCModule.c, config.cpp, Admin, Survival or Loot edits are needed.

### Full cap inventory

Keys below are inside `settings.json:AILimits`; all defaults and validated ranges
are documented in [operator keys](#human-ai-limits-owner-request-2026-11-18). Safety ceilings are centralized in
`3_Game/World/HCAILimits.c`. They bound validation, not a second live allowance.

| Former location / cap | Old value | New key / source | Default |
|---|---|---|---|
| HCWorldMaterializer: MAX_PROPOSALS and proposal admission | 2 | MaxMaterialized (also global MaxLiveGroups) | 15 |
| HCWorldMaterializer: MAX_ACTORS, claim/debt admission, HC-10 actor_cap report | 8 | MaxLiveAI | 72 |
| MaterializerRow clamp / MAX_PER_PROPOSAL | 4 | Kind's configured maximum, additionally faction strength and SIZE_CEILING | Holdout 6, party 6, patrol 5, camp 6 |
| HC-10 HCAIPartyCustody.HCReservation, HCAIPartyResult survivors and materializer custody validation | 4 | HCAILimits.SIZE_CEILING; admission uses configured size | 12 safety ceiling |
| HCWorldLimits.STRENGTH; faction creation, regrowth, adjustment, save validator | 12 | FactionStrengthMax | 24 |
| HCWorldLimits.HOLDOUTS; world insert/load, holdout catalog/load/lights, materializer row spans, picker NextHouse saved index | 24 | MaxHoldouts | 48 |
| HCWorldLimits.OCCUPIED; world upsert/load and holdout occupancy | 6 | MaxOccupiedPlaces | 15 |
| HCWorldLimits.PARTIES; world insert/load and materializer row spans | 12 | MaxParties | 24 |
| HCWorldLimits.MATERIALIZED; persisted party admission | 2 | MaxMaterialized | 15 |
| HCWorldLimits.CAMPS; HCCampModule / HCCampStore row capacities | 32 | MaxCamps | 32 |
| HCWorldLimits.CAMP_MEMBERS; HCCampScan / camp state references | 64 | MaxCampItems (these are item references) | 64 |
| HCWorldData.HoldoutValid / HCHoldouts stored occupants ceiling | 3 | SIZE_CEILING for old/surviving rows; HoldoutMin/Max for new groups | 12 safety; 3–6 new |
| HCWorldData.PartyValid persisted size ceiling | 4 | SIZE_CEILING; PartyMin/Max for new travelling groups | 12 safety; 2–6 new |
| HCHoldouts.HCAdvanceOccupancy initial population | 1 | HoldoutMin / HoldoutMax | 3–6 |
| HCHoldouts.BindOccupant body registry | 18 | MaxLiveAI | 72 |
| HCPickers fresh party population | 2 | PartyMin / PartyMax | 2–6 |
| HCCampVisitors settlement / HCCampStore neighbour validation | 2 | CampMin / CampMax; SIZE_CEILING for stored survivors | 2–6; safety 12 |
| HCXAISitePolicy default MaxActiveSites / SiteRules validation | 8, accepted 1–8 | MaxActiveSites; GROUP_CEILING safety | 15; safety 24 |
| HCXAISitePolicy default MaxActiveAI / SiteRules validation | 24, accepted 1–24 | MaxActiveAI; AI_CEILING safety | 72; safety 128 |
| HCXAISites BudgetProblem / SpawnProblemFor global proposal/body checks | 2 / 8 | MaxLiveGroups / MaxLiveAI, plus shared HCAIBudget | 15 / 72 |
| HCXAISites authored/transient site sub-budgets / SiteRules.SpawnProblem | Legacy site policy fields | MaxActiveSites / MaxActiveAI normalized from settings | 15 / 72 |
| HCXAISites transient actor ceiling | 4 | Materializer's configured kind size, SIZE_CEILING validation | Up to 12 safety |
| HCXAISite DTO NumberOfAI / NumberOfAIMax | 2 / 3 | PatrolMin / PatrolMax | 2 / 5 |
| Expansion shipped occupation sites (both JSON files) | Mostly 3–4, holdout validator maximum 3 | OccupationMin / OccupationMax; template min/max | 3–8 |
| Expansion patrol / checkpoint sites, including shipped JSON | 2–4; checkpoint guards 2–3 | PatrolMin / PatrolMax; template min/max | 2–5 |
| Expansion scavenger sites | 2–3 | PartyMin / PartyMax; template min/max | 2–6 |
| SiteRules kind/member validation / former HCGroupMembers ceiling | Kind maxima 3/4, scaling maximum 8 | SIZE_CEILING; configured kind population at Create | 12 safety |
| HCXAIRules legacy profile maxima | MaxGroups 1–8 / MaxActors 1–32 | Compatibility validation against GROUP_CEILING / AI_CEILING; live admission reads settings | Safety 24 / 128; live 15 / 72 |
| HCXAIAdapter reservation gates | Legacy profile MaxGroups / MaxActors | MaxLiveGroups / MaxLiveAI + HCAIBudget | 15 / 72 |
| HCXAIAdapter surveyed group selection | All surveyed spawn positions; up to 8 | Stable PatrolMin/Max selection clamped to unchanged surveyed prefix | 2–5 |
| HCXAIRules surveyed route Spawns / profile Missions counts | 8 / 8 | SIZE_CEILING / GROUP_CEILING; config MaxLiveAI admission | Safety 12 / 24 |
| HCXAIEncounters.MAX_OPEN and binding retention | 8, retained 2× | MaxEncounters; retention still derived 2× | 15; retained 30 |
| HCXAILiveMap.MAX_UNITS diagnostic scan | 1024 | MaxObservedAI (independent of live admission) | 1024, safety 8192 |
| tools/package/ai_patrols.py source/mission count and surveyed member validation | 8 / 8 members | Shared authored ceilings mirrored for offline input validation | Safety 24 groups / 12 members |
| New combined live group ceiling | Separate materializer/site/adapter counters | MaxLiveGroups | 15 |
| New deterministic sizing seed | Implicit/fixed populations | WorldSeed | 18473 |

`HCWorldLimits.HOLDOUTS` and `.PARTIES` are compatibility aliases with safe
48/24 startup defaults; HCAILimits.Use replaces them with the validated policy.

The audit also inspected every spawn/reservation module and distinguished these
remaining structural, observation, native-population and work quotas. None grants
an additional human AI spawn allowance:

| Inspected module / remaining bound | Value / meaning | Disposition |
|---|---|---|
| HCWorldLimits.FACTIONS | Exactly 5 named identities with fixed catalog/relationships | Structural schema, not group count; stays fixed |
| World scenes/events | Scene/lead/note/prop/cargo quotas; event AI provider binds existing owned patrols | No additional human bodies; encounter cap above covers bindings |
| Ecology policy MaxActors / HCEcologyLimits.ACTORS | 32 observations of native CE animals/infected; ecology migration herd members up to 6 | Existing separate validated ecology policy; not human AI spawning |
| Groups MaxGroups | 32 player teams by default, validated 1–90; member/icon/discovery quotas | Player ACL/team system, not AI; untouched |
| Infected horde policies | 2 hordes / 24 existing infected; variety/LOD/reach observation budgets | Separate CE/infected systems outside owned scope; no human AI allowance |
| HCXAIPatrolDebug / HCXAILiveMap | 66 state visits, 64 member slots, 2 routes / 128 points; map 2×64 points | Diagnostic work/transport quotas; scan population ceiling is configurable above |
| HCXAIEncounters.MAX_KILLS | 16 journal kills serviced per tick | Work quota, not actor/group admission |
| HCXDefence / HCXDefencePolicy / HCXStance | 12 perception slots per grudge, 64 grudges, 6-shot window, 8 recent deaths/warnings, 16 observer gates | Bounded memory/observation work; no creation or body reservation |
| HC-10 custody / bridge; adapter journal/pruning | 256 custody/bridge records; adapter history remains separate | Custody covers both maximum world spans (128+128); oldest finished records evict, live/quarantined records never evict |
| Site policy, route/cache/ownership journals | 64 authored or cached rows, geometry points 2–8 / 2–6, waypoint/spatial limits | Catalog/geometry/history validation; up to 15 groups can be live |
| Materializer / camps / holdouts | 32 player-cache/work slots, 32 rows/ring, 4-unit slices; object/cargo/lighting/mailbox quotas | Bounded work, inventory and observer snapshots, not population policy |
| HCX adapter MaxItems/MaxTickWork/MaxLeaseHistory | Operator-qualified equipment/work/evidence budgets | Separate item/work policy; full AI count always charged globally |
| DTO HCWorldParty.Size initializer | 1 before row population is authored/loaded | Placeholder, not a spawning default; fresh picker draws configured size |

The scan regression targets human population comparisons and former population
constant names, allowing numeric safety ceilings only in HCAILimits. Work,
geometry, distance, item, identity and evidence quotas are intentionally excluded;
these cannot be accurately classified by scanning every numeric literal.

### Combined budget design

HCAIBudget lives in 3_Game so the base and optional addon share one server-process
ledger. Each row holds a unique owner ID and full actor reservation. Admission
requires both available group capacity and enough actors for the entire group,
before any native or journal side effect. Pending and deferred members count.

Materializer reserves bounded `lease:<durable sequence>` before offering its
proposal. Transient sites reuse that exact ID, making the bridge idempotent rather
than charging the same group twice. Authored sites use `site:<site id>`; the
surveyed adapter uses `adapter:<lease id>`. Its deterministic population uses only
an unchanged prefix of qualified surveyed positions, clamped to the available
count (at least one); no coordinate is manufactured. Site sub-budgets cannot exceed the
combined allowance. The synthetic integration test executes actual site Spawn
and adapter admission after a materializer reservation and checks exact-fill,
refusal and transient reuse.

Successful absent-body results, observed native authored despawn, and completed
adapter retirement release reservations. Creation refusal with no group can
release an authored site. Claimed materializer bodies are never timed out.
At process startup, CLAIMED rows become FINISHED_UNKNOWN and release their
reservations, since transient provider groups use Persist=false. Late results
release old reservations without applying guessed outcomes. Quarantined debt
is retained; unreadable custody blocks new admission. Save failures block every
spawn owner and print one loud diagnostic. This is conservative accounting,
not proof that native providers reconciled bodies. Existing external Expansion
patrols/player recruitment must remain disabled as required by provider admission;
HollowCountry cannot silently account for arbitrary third-party creation.

### Verification

All Python fixtures are explicitly synthetic; native arrays/strings/provider
calls are ports around the authored policy bodies. They establish source and
policy behavior, not native DayZ behavior. The earlier per-run test records were
removed with the modules they cited; the current checks are `tools.validate.preland`
and the native compile gate.

### Native API inspection and deferred acceptance

Read installed snapshot 1.30.164289 before authoring: `1_Core/proto/EnString.c:199`
Length, `:240` IndexOf, `:448` Get; `EnScript.c:380` Count, `:407` Insert,
`:470` RemoveOrdered; `EnDebug.c:96` Print. HC-10's inspected persistence APIs and
shared world store are cited in HCWorldMaterializer. Existing native settings
staging is reused. Read-only installed Expansion `eAIDynamicPatrol.c:580–640`
selects NumberOfAI/NumberOfAIMax and creates a group; `:691–729` clears a despawned
group then nulls m_Group. No provider source or game assets were copied.

Lead acceptance remains open:

1. Compile source with DayZDiag and build normal PBOs; boot the normal server with
   both addons. Confirm `[HC AI] limits groups=15 ai=72 occupation=3-8` and all
   effective keys, no compile errors, `runtime=PENDING` qualification logs.
2. Exercise absent/old settings, a negative/over-ceiling key and a reversed range.
   Confirm named fallback lines and unchanged operator files. Reload old saves;
   lower a count below stored rows and confirm logged refusal/recovery with backups.
3. With two clients, activate mixed occupation/patrol/party/materializer groups,
   including full deferred members. Verify combined admission stays within
   settings, with no visible pop-in, combat despawn, duplicate gear or ownership
   transfer. Observe death/despawn and reservation release, and group sizes across
   restart. Diagnostic map must still reveal excess external AI if present.
4. Interrupt/restart with claimed, quarantined and unreadable custody. Verify
   `custody restore finished_unknown=N runtime=PENDING`, budget released for
   Persist=false claims, and no duplicate party/cargo or replayed inventory.
   Quarantines and unreadable stores must still refuse new admission. Inject a
   failed save and verify `CUSTODY SAVE FAILED; ALL NEW AI BLOCKED` appears once.
5. Measure CPU, tick delays, networking, audio, visibility and AI navigation with
   3–6 players and varied sizes up to 15 groups / 72 actors. Native load results,
   geometry capacity and performance acceptance remain pending; do not enable a
   production release based on the offline suite.

### AI limits / HC-10 review fix round

Spec/plan/task trace (review P1s block landing): preserve one live party/cargo,
release clean refusals, recycle completed identities after the six-hour process
cooldown, recover nonpersistent claims at process startup, and retain visible
fail-closed persistence. Implementation reuses HCAIBudget, HCWorldStore's verified
intent/backup/readback barrier, and the existing bounded materializer interest
ring/work budgets. No HCModule.c or config.cpp integration edits are required.

| Review task | Source and behavioral validation |
|---|---|
| P1-1 refusal / completed identity retirement | Refusals delete claims; finished identities recycle; oldest finished history evicts at 256 rows; 300 successive claims and duplicate-live exclusion tested |
| P1-2 restart budget leak | OnStart/HCLoadCustody resolve prior-process CLAIMED rows to FINISHED_UNKNOWN and save once; no cargo/inventory or casualty replay; late callbacks release budget; same-process off/on retains claims |
| P2 partial fold-back | Release the confirmed-absent body reservation before world writes; log failure; never replay a partial debit |
| P2 short surveyed patrol | Clamp configured size to surveyed spawn count, retain requested-cap gate and at least one actor |
| P2 repeated site refusal | Shared-budget refusal diagnostic limited to one per site per 60 seconds |
| P2 custody save latch | Every failed save barrier blocks the shared budget, including existing-ID reserve attempts, and logs once |
| P3 bounds / defaults | Durable compact lease sequence; canonical v1-to-v2 migration; safe 48/24 aliases before Use |

The custody v2 sequence is saved before provider dispatch. It prevents stale
callbacks from a previous offer/restart from matching a fresh lease of the same
party; neither ID truncation nor a generation reset is used. FINISHED_UNKNOWN
records are evictable history; CLAIMED and QUARANTINED records are never evicted.
Cooldowns remain process-local. Restart returns identity/cargo authority to the
existing owner store; this code creates no inventory. Back up custody and its
owner stores together; v2 writes are not readable by the earlier v1-only build.

All disk, JSON, world, observer and provider ports in these fixtures were explicitly
synthetic. DayZDiag, normal PBO/server, native restart and two-client
inventory/visibility/retirement acceptance remain pending. No native gameplay
acceptance was performed.
