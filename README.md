<div align="center">

# HOLLOW COUNTRY

**A survival overhaul for DayZ.**

Richer places to search. More reasons to salvage. Infected encounters grounded in the world.

[Scavenging](#scavenge-with-purpose) · [Crafting](#make-what-you-find-useful) · [Infected](#the-infected-remember) · [Phase 2](#the-road-ahead--phase-2)

**IN DEVELOPMENT** · DayZ PC · ChernarusPlus first · All rights reserved

</div>

---

## Your guide to the country

Read the room. Travel light. Leave quietly.

Hollow Country aims to make ordinary survival decisions matter again. A neglected
apartment could be worth searching. A damaged item could be worth carrying. A
gunshot could change the route home. Familiar buildings should tell different
stories, and the world should offer more to do without requiring a mission list.

This guide covers **the whole mod vision, including Phase 2**, not just the
current build. **Being built** means work exists but the complete feature still
needs testing. **Planned** means implementation remains. **Feasibility testing**
means DayZ's limits may require a different approach. The experimental gameplay
systems currently default to disabled.

## Scavenge with purpose

**Being built · Loot, interiors and searching**

| Change | What it means for your next run |
| :--- | :--- |
| **More places worth checking** | Accessible buildings and meaningful spaces should have a sensible chance of supplies, including neglected apartments and military accommodation. A chance is not a guarantee. |
| **Coherent loot and variety** | Look for supplies where they belong, with less repetitive junk and more useful finds. |
| **Soft progression** | Better equipment comes through exploration and risk, while essentials retain multiple acquisition routes. |
| **Varied familiar houses** | Existing buildings gain compatible furnishings, clutter and histories that reward observation. Doors, stairs and routes must remain usable. |
| **Visible and searchable finds** | Check suitable cupboards, wardrobes and storage as well as floors. Searching takes time and exposes you to danger. |
| **A place remembers** | Restarting should not refill a searched cupboard or reroll a house into another free supply cache. |

Searching and visible loot must share a finite economy. Previous visits,
depletion and the character of a location should matter.

## Make what you find useful

**Being built · Crafting and salvage**

Repair, reuse, disassembly and salvage should give appropriate existing items a
believable purpose, balanced against materials, tools, wear and time.

The first prototypes recover netting from a camo net, wire from a cable reel and
leather from an empty leather belt. **These are starting points, not a finished
crafting feature.** A full audit of existing items and recipes will determine the
complete, justified set of changes. This does not mean a recipe for every object:
additions and exclusions must make sense for survival and the economy.

**Planned · Phase 2: fuel siphoning.** Suitable cars should offer gasoline when
you have appropriate equipment and a compatible container. Transfers must draw
from actual finite fuel, respect capacity and stop safely when interrupted.
Decorative wrecks will not become endless petrol stations. Supported vehicles,
tools and any finite wreck supplies remain part of the audit.

## The infected remember

**Being built · Infected, local alerts and persistent hordes**

Infected should pressure you through what they can perceive: sightings, sounds
and clues from an encounter. Nearby infected may relay an alarm, turning a
careless fight into a local problem. Breaking contact and choosing a quieter
route should remain meaningful ways to escape.

The intended experience includes distinct infected roles and trade-offs,
investigation of observed clues, coherent group movement and persistent hordes.
Room traversal, door interactions, injuries and audible warnings must behave
fairly. Infected must not secretly track your live position or teleport into
pursuit. Changes to distant hordes must preserve the population and never make
infected appear in view.

**Feasibility testing · Phase 2: death reactions.** More convincing folding or
ragdoll-like deaths are a goal. The result depends on DayZ's animation and
physics capabilities and must preserve corpse access, loot and multiplayer
consistency. Full ragdoll is not confirmed.

## The road ahead — Phase 2

These features are part of the intended whole experience. They are not yet
available as a qualified gameplay package.

### Travel together

| Planned system | Intended experience |
| :--- | :--- |
| **Extended stamina** | More practical travel through an original stamina model that keeps exertion, recovery and load meaningful. |
| **Weight display** | See your burden and understand how it affects endurance. |
| **Groups** | Team membership with teammate icons both in the world and on the map; visibility rules configurable by the server. |
| **Interactive map** | Press **M** to pan and zoom the map and share group markers. The action should be rebindable. |
| **Useful information** | Appropriate navigation, discovery and mission layers, without exposing information your group should not know. Exact layers remain to be selected. |

Group information must respect membership and privacy through death, leaving,
reconnecting and stale position reports.

### Choose your own trouble

**Planned · PvE groups, missions and events**

Follow a radio lead, investigate an incident, recover supplies or take part in an
encounter—or pass it by and continue surviving. Events should fit the world's
scarcity and danger, with rewards drawn from a controlled economy.

AI players and groups are a goal. Native support comes first; a maintained AI
dependency may be used if needed and suitable. Armed patrols, rescues, escorts and
convoys are possibilities to evaluate, not confirmed mission types. Navigation,
combat fairness, performance and permissions determine the supported roster.

Northmen's public events and map experience are references. Hollow Country will
use independent work or appropriately permitted dependencies.

### A world with its own rhythm

| Direction | Intended impact |
| :--- | :--- |
| **Ecology** | More believable movement around food, water and resources, investigating animals and infected separately. |
| **Migration** | Reasons for familiar routes to change over time, grounded in supported movement and population behavior. |
| **More firearms** | A believable mix of wood-stock and conventional modern weapons from existing permitted mods, appropriate to the setting. No new gun assets are planned. |
| **Weather and lighting** | Stronger atmosphere and changing travel conditions using supported controls while preserving readable, fair gameplay. |
| **Existing DayZ mechanics** | Audit and extend useful native systems where they improve the whole survival experience. |

Ecology, migration and visual changes need feasibility testing. This is not a
promise of a new renderer or unrestricted wildlife simulation. Base-building
expansion and futuristic equipment are outside the mod's direction.

## A day in Hollow Country

```mermaid
flowchart LR
    A["Choose a route"] --> B["Search and read the surroundings"]
    B --> C["Repair, salvage and manage your load"]
    C --> D["Avoid, distract or fight infected"]
    D --> E["Follow an optional lead—or head home"]
    E --> F["Share discoveries with your group"]
    F --> A
```

This illustrates the intended survival loop, including planned features. Actual
in-game screenshots will follow when the corresponding experience can be
captured and verified.

## Where we are

Experimental search and interior systems, salvage prototypes and infected clue
and alert logic exist. Some code has compiled and initialized in a real DayZ
server. Full inventory recovery, navigation, audio, multiplayer behavior, balance
and performance still need qualification.

Every area requires a full audit of relevant existing content and behavior.
Pilots are checkpoints: a feature finishes only when its agreed scope is
implemented, documented and validated. Unsupported ideas and exclusions must be
explained rather than silently dropped.

## For server owners and contributors

Setup, settings, backups and rollback live in the [operator guide](docs/README.md)
and [installation guide](docs/INSTALL_ROLLBACK.md). Source and testing details
live in [addon development](docs/MOD_DEVELOPMENT.md), [tools](tools/README.md),
[tests](tests/README.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

The development build is not yet qualified for live-server use. ChernarusPlus is
the first map; compatibility across maps and server setups is a goal, including
servers around 90 players. That capacity has not been demonstrated. Workshop
preparation is planned; there is no Workshop release yet.

## Roadmap

Current work closes native gameplay, persistence, multiplayer and performance
gates for the components above. The
[execution queue](https://github.com/d-addison/hollow-country/issues/39) groups
outstanding work into dependency-ordered batches, followed by integrated
qualification. Follow the [milestones](https://github.com/d-addison/hollow-country/milestones)
for progress.

Internal testing runs throughout development, leading to one consolidated
Phase 2 playtest once the candidate satisfies its required checks. Follow the
[crafting audit](https://github.com/d-addison/hollow-country/issues/52),
[fuel siphoning](https://github.com/d-addison/hollow-country/issues/53) and
[whole-feature completion criteria](https://github.com/d-addison/hollow-country/issues/54)
for those work streams.

## License and assets

Copyright © 2026 David Addison. **All rights reserved.** No open-source or public
reuse license is granted. Third-party materials retain their owners' terms; see
the [provenance inventory](docs/PROVENANCE_AND_LICENSES.md).

Game files, purchased assets, Workshop packages, signing private keys, credentials
and runtime profiles do not belong in this repository.
