# Optional PvE AI data

## HC AI sites (shipped, the default when the addon runs)

`sites.json` is our own site policy: 7 patrols (4 police stations, 3 military
sites), 5 scavenger parties of 2–3 that roam qualified routes between loot
buildings, and 5 holdouts of 2–3 survivors who keep to one house with one
`WoodenCrate` or `SeaChest` cache. Its coordinates were chosen once from the
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
| (empty file) | `$profile:HollowCountry/acceptance/pve_patrols.enable` (the opt-in) |

At start `HCXAISiteDirector` admits the sites only when the engine build and
world match the policy, the addon and its dependencies are in `CfgPatches`,
Expansion AI and AIPatrol settings are loaded with recruiting off and no
unlimited reload, every loadout file exists, the observer is native eAI
perception and the opt-in marker is present. It then binds holdouts to their
house (nearest object of `HouseClass`), qualifies each route by navmesh
sampling and `FindPath` (at most 4 work items per tick), and caches the result
by SHA-256 of route plus build in `$profile:HollowCountry/expansion-ai-routes.json`.
Each qualified site becomes an `eAIDynamicPatrol` that Expansion's own trigger
spawns when a player is inside `ActivationRadius`; HC refuses the spawn within
`MinPlayerDistance` (200 m) of a player, in a player's line of sight, or past the
24-AI / 8-site budgets, checks each later group member at the formation point
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

## Event patrol examples (lease path)

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

After review, merge `Missions` into the server's separately prepared
`$profile:HollowCountry/expansion-ai.json`, retaining verified build/artifact/session
identities, budgets and observer policy. No automatic overwrite is performed.
Trusted server hooks must still bind route survey/loadout digests to evidence.

`AISettings.merge.json` is a field merge into the owner's existing
`$profile:ExpansionMod/Settings/AISettings.json`, not a replacement settings file.
Preserve all other fields and its version. Pinned Expansion reads this profile
file in `ExpansionAISettings.OnLoad()`; the source evidence was recorded in the local W1.1 report (not shipped).
There is no supported global `UnlimitedReload` JSON field in that class. Keep
Expansion admin unlimited-reload controls OFF; any nonzero effective global mask
closes HC admission even if this merge and the per-actor finite setting are used.

The server-only opt-in is the empty file
`$profile:HollowCountry/acceptance/pve_patrols.enable`, cached until restart.
For the event lease path `HCXAIQualification.Qualified()` remains false. Opt-in
does not provide missing artifact, route, observer or durable inventory hooks. No profile JSON, route
example or marker supplies those trusted capabilities.

## Expansion's own patrols

HC events own AI spawning. Pinned Expansion AI 1.9.84 otherwise generates
`$mission:expansion/settings/AIPatrolSettings.json` with `Enabled: 1` and default
patrols (police and wreck object patrols plus roaming patrols) that spawn when a
player comes near, with their own loadouts and reload rules. `AIPatrolSettings.override.json`
is our configuration, not an Expansion file, installed at
`<mission>/expansion/settings/AIPatrolSettings.json` (the launcher backs up any existing file).
It sets `m_Version` to the pinned `VERSION` (32), so Expansion loads it without
converting or saving, and `Enabled: 0` with no `Patrols`, so `eAIDynamicPatrol`
spawns nothing. `AILocationSettings.json` only holds roaming waypoints and no-go
areas and needs no change. `tools/setup/wine_compile_probe.py --expansion-patrol-settings` stages
it into a disposable mission copy; any rewrite by Expansion is reported as drift.

## Operator policy and readiness

The addon reads its policy only from `$profile:HollowCountry/expansion-ai.json`
and writes a template there on first start; no policy is generated by tools. A
policy is admissible only with observed values: world session, world/artifact/
dependency digests, budgets, an observer policy and routes with survey and
loadout digests. At server start the addon installs a local trusted hook port
(once, only when Expansion AI is loaded) that reports live build/world/clock but
keeps every receipt verification flag false. The startup line
`[HC Expansion AI] readiness (...) Ready=...` names the first unmet policy
requirement, the Expansion AI settings state, unfair globals and the unverified
receipt flags; it is logged again once when Expansion AI settings first load.
