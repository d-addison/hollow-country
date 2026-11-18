# Optional PvE AI data

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
V2 additionally caps site activity at eight actors / two active sites; these are
provisional ceilings, not measured budgets. The module checks one owned actor
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
24-AI / 8-site legacy budgets (V2 further limits these to 8 AI / 2 sites), checks each later group member at the formation point
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
case-sensitive; anchors must match exactly. W1.4 must retain those IDs/positions or
supply its `Sites` JSON to the validator and update this snapshot and the routes.
There was no W1.4 mission/events file available when these examples were authored.

The adapter DTO adds `SiteId`, `GroupSize`, spawn positions, loop waypoints, actor,
faction and exact per-member equipment. `GroupSize == len(Spawns)`. The event
bridge retains the existing family-5 mapping `MissionId = SiteId + "-5"` and
`Anchor = Position`; it receives the mission ID and anchor, never player targets.
Each example gives each actor one Makarov, one spare eight-round magazine and two
clothing items. It does not replenish magazines, request tracking coordinates or
use Expansion's autonomous patrol spawner.

Validate against W1.4's real site manifest after landing:

```sh
python3 -m tools.package.ai_patrols \
  --patrols mission/hollow-country/ai/patrols.example.json \
  --sites mission/hollow-country/events/sites.json
```

For an offline contract check before W1.4 lands, pass
`mission/hollow-country/ai/event-sites.contract.json` as `--sites`. The tool
requires a JSON object containing `Sites: [{Id, Position, Reviewed, ...}]`; all
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
