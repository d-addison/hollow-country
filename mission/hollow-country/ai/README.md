# Optional PvE patrol data

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

`AISettings.merge.json` is a manual field merge into the owner's existing
`$profile:ExpansionMod/Settings/AISettings.json`, not a replacement settings file.
Preserve all other fields and its version. Pinned Expansion reads this profile
file in `ExpansionAISettings.OnLoad()`; the source evidence was recorded in the local W1.1 report (not shipped).
There is no supported global `UnlimitedReload` JSON field in that class. Keep
Expansion admin unlimited-reload controls OFF; any nonzero effective global mask
closes HC admission even if this merge and the per-actor finite setting are used.

The server-only opt-in is the empty file
`$profile:HollowCountry/acceptance/pve_patrols.enable`, cached until restart.
`HCXAIQualification.Qualified()` remains false. Opt-in does not provide missing
artifact, route, observer or durable inventory hooks. No profile JSON, route
example or marker supplies those trusted capabilities.
