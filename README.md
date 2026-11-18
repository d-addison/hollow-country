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
means DayZ's limits may require a different approach. Feature preferences default
to **enabled**. A system still needs its supported content and dependencies;
missing prerequisites are reported rather than treated as working gameplay.

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

The first salvage recipes cut netting from a camo net, pull wire from a cable
reel or a barbed bat, recover leather panels, saw bats into sticks, and break
nailed bats and ruined crates down for wood and nails. Each recipe needs the
right tool and takes time. **These are starting points, not a finished
crafting feature.** A full audit of existing items and recipes will determine the
complete, justified set of changes. This does not mean a recipe for every object:
additions and exclusions must make sense for survival and the economy.
Cloth, rope, camouflage, repair materials and practical storage are among the
uses being reviewed, alongside the tools needed to work them.

**Being built · Phase 2: fuel siphoning.** Suitable cars should offer gasoline when
you have appropriate equipment and a compatible container. Transfers must draw
from actual finite fuel, respect capacity and stop safely when interrupted.
Decorative wrecks will not become endless petrol stations. Supported vehicles,
tools and any finite wreck supplies remain part of the audit.

**Being built · Phase 2: improvised light mounts.** Use duct tape to fix a
weapon light to a suitable gun, keeping your hands available. Peel the light off by
hand when you need it elsewhere. Mounting consumes the tape; removing the light
does not recover it, and mounting again needs fresh tape. The first release covers
rifles and pistols whose own model already carries a light, including those that
need a railed handguard fitted first, so the beam starts where the gun expects it.
The action reads **Tape light to weapon** and accepts weapon lights only. Backpacks, helmets and other guns remain planned extensions.

## The infected remember

**Being built · Infected, local alerts and persistent hordes**

Infected should pressure you through what they can perceive: sightings, sounds
and clues from an encounter. Nearby infected may relay an alarm, turning a
careless fight into a local problem. Breaking contact and choosing a quieter
route should remain meaningful ways to escape.

The intended experience includes distinct infected roles and trade-offs,
investigation of observed clues, coherent group movement and persistent hordes.
Roles should be recognizable through appearance and believable locations, with
different abilities to open, force or be stopped by doors. Individual health and
damage should remain broadly familiar; occasional concentrations should create
danger without turning every location into a permanent swarm.
Room traversal, door interactions, injuries and audible warnings must behave
fairly. Infected must not secretly track your live position or teleport into
pursuit. Changes to distant hordes must preserve the population and never make
infected appear in view.
Supported injury effects should also make wounded movement readable, including
leg injuries and crawling where the native behavior permits it.

Footsteps, shuffling and contact sounds should help you read a threat, including
stealthier variants. Surfaces, distance and obstacles should affect what you hear.

**Feasibility testing · Phase 2: death reactions.** More convincing folding or
ragdoll-like deaths are a goal. The result depends on DayZ's animation and
physics capabilities and must preserve corpse access, loot and multiplayer
consistency. Full ragdoll is not confirmed.

## The road ahead — Phase 2

These features are part of the intended whole experience. Some are already in the
development build; none is yet a qualified gameplay package.

### Travel together

**Being built · Stamina, groups and the shared map**

| System | Intended experience |
| :--- | :--- |
| **Extended stamina** | Half the continuous movement drain and 25% faster recovery by default. Weight still limits capacity; jumps and melee retain their normal costs. Server owners can tune the balance. |
| **Stamina and weight bars** | See your exertion and burden, and understand how your load affects endurance. |
| **Groups** | Team membership with teammate icons both in the world and on the map; visibility rules configurable by the server. |
| **Interactive map** | Press **M**, DayZ's own map key (rebind it in the game's controls), to pan and zoom the map and share editable group markers and notes. |
| **Useful information** | *Planned.* Appropriate navigation, discovery and mission layers, without exposing information your group should not know. Exact layers remain to be selected. |

Group information must respect membership and privacy through death, leaving,
reconnecting and stale position reports.

### Choose your own trouble

**Being built · Events · Planned · PvE groups**

Follow a radio lead, investigate an incident, recover supplies or take part in an
encounter—or pass it by and continue surviving. Events should fit the world's
scarcity and danger, with rewards drawn from a controlled economy. Press **O**
(rebindable) to see the events you know about. Events run only at reviewed
sites, and no site has been reviewed yet.

AI players and groups are a goal. Native support comes first; a maintained AI
dependency may be used if needed and suitable. An optional companion addon can
connect events to DayZ Expansion AI where a server already runs it; Hollow
Country itself does not require it. Armed patrols, rescues, escorts and
convoys are possibilities to evaluate, not confirmed mission types. Navigation,
combat fairness, performance and permissions determine the supported roster.
Human AI may use the selected provider's built-in stuck recovery, including
visible repositioning. This exception does not apply to infected or hordes.

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

## Living Country — V2

You should be able to read the country through its weather, abandoned places
and the traces of other survivors. These systems are in the development build
and await play-testing; the descriptions below are the experience being built.

| System | What it means for your next run | State |
| :--- | :--- | :--- |
| **Hollow grade and atmosphere** | Set your own colour-grade intensity from 0–100% in 10% steps; 0 restores vanilla. Bind the grade control in DayZ's Controls to cycle it. Dusk, overcast and storm lighting and changing weather days should give each journey a mood while nights stay bright. | **Being built** |
| **Ambient life and signs of life** | Watch for small animals around water and farms, lit windows, chimney smoke and flies around carcasses. These are clues to read as you travel. | **Being built** |
| **Travel and repair projects** | Discover shared trail shelters and group map pins. Look for many bikes, a few boats and common cars that need real parts and repairs. DayZ-Bicycle, Survivor Animations and Ambient Animals Pack are default subscriptions; their mission overlays apply at install time. | **Being built** |
| **Survivor factions and hold-outs** | Meet the traces of local families, volunteers, scavengers, raiders and travellers. Hold-out survivors are intended to be killable and lootable, with real caches and a seven-day lockout before anyone moves back in. There is no reputation ladder, trading or recruiting. | **Being built** |
| **Pickers and dead drops** | Other scavengers should move real supplies through houses and caches. A dead drop gives you a place to investigate, with finite contents that someone else may already have taken. | **Being built** |
| **Radio, leads and body stories** | Carry a powered PersonalRadio to receive faction chatter and Morse clues on the right frequency. Follow rumours, notes and the stories around bodies, then share received leads with your group. Paper notes stay rare: at most one per scene and ten world-wide. | **Being built** |
| **Camps and neighbours** | Build around your fire, shelter and storage to have your camp recognised, then grow through three tiers. Visitors and a mailbox should bring news. Theft is limited to unlocked crates at unattended camps; locked storage stays safe. Tier-3 camps may attract warned raider probes from day 14. | **Being built** |
| **Scripted scenes and chains** | Read a last stand, quarantine or evacuation scene, then decide whether to follow its next clue. Stages can expire, so you can pass a story by without taking on a mission list. | **Being built** |
| **The world changing** | Expect capped escalation, settlement decay, infected memory and horde migration to change familiar routes. Revisited houses should refresh searches against finite supplies, and wreck salvage should offer a limited stock of parts. | **Being built** |
| **Optional Expansion AI addon** | With the server's optional AI dependencies, encounter patrols and checkpoints, read faction stance and use “Ask for news”. Encounters draw on the world's remembered events rather than knowledge of your live position. | **Being built** |

The seven-day hold-out lockout and day-14 camp pressure use real days, including
server downtime. Shelters, visitors and scenes must leave doors and routes usable;
loot remains finite wherever you find it.

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

Everything below is in the development build, on by default, and compiles and
starts on a dedicated server. Each feature logs one admission line at start-up
and can be switched off on its own. None has been accepted by playing it yet:
features are accepted one by one on a local server, and behaviour that needs
several players is checked in group sessions.

| Area | In the build | State |
| :--- | :--- | :--- |
| Search, interiors and loot | Finite search economy, furnished interiors, about twice vanilla loot with extra contextual floor spots in 149 building types; firearms and ammunition stay scarce | Built · not played |
| Crafting and recovery | Recovery families, fuel siphoning, taped lights | Built · not played |
| Infected | Packs, alerts, investigation, hordes, doors they can open or force, and reach against players on low roofs, ladders and vehicles (attacks and steering only, no teleports) | Built · not played |
| Travel together | Stamina doubled, separate weight and stamina bars, groups and the shared map | Built · not played |
| Living Country (V2) | Every system in the table above | Built · not played |
| Admin test kit | Admin-only map snapshot, module status and test triggers for sitters, hordes, scenes, events, hold-outs and camps | Built · not played |
| Death and idle animations | A sitting infected pose built from our own keyframes | Built · not played |

Balance and performance still need measuring on the target load of three to six
players. Every area requires a full audit of relevant existing content and
behaviour, and a feature finishes only when its agreed scope is implemented,
documented and validated. Unsupported ideas and exclusions must be explained
rather than silently dropped.

## For server owners and contributors

Setup, settings, backups and rollback live in the [operator guide](docs/README.md)
and [installation guide](docs/INSTALL_ROLLBACK.md). Source and testing details
live in [addon development](docs/MOD_DEVELOPMENT.md), [tools](tools/README.md),
[tests](tests/README.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

The development build is not yet qualified for live-server use. ChernarusPlus is
the first map; compatibility across maps and server setups is a goal, including
servers around 90 players. That capacity has not been demonstrated. The mod and
its optional Expansion AI addon are on the Steam Workshop as development builds;
a friend-server bundle ships as a GitHub pre-release, with a
[step-by-step runbook](docs/FRIEND_SERVER_AI_RUNBOOK.md).

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
for those work streams. Extensions agreed for after the first release are tracked in the
[post-v1 milestone](https://github.com/d-addison/hollow-country/milestone/12).

## License and assets

Copyright © 2026 David Addison. **All rights reserved.** No open-source or public
reuse license is granted. Third-party materials retain their owners' terms; see
the [provenance inventory](docs/PROVENANCE_AND_LICENSES.md).

Game files, purchased assets, Workshop packages, signing private keys, credentials
and runtime profiles do not belong in this repository.

Default server dependencies and install folders are documented in the
[friend server guide](docs/INSTALL_ROLLBACK.md#friend-server-installation). Our two installed folders are
`@HollowCountry` and `@HollowCountryExpansionAI`; load both on server and clients.
V2 is on by default. All feature rows remain **Being built** and runtime acceptance
is pending. Native Windows compilation, normal PBO/server testing and two-client
checks are still required; offline packaging checks establish no DayZ behavior.

Expansion-Animations is intentionally not loaded: it conflicts with Survivor Animations, which DayZ-Bicycle requires; Expansion-AI brings its own AI animations.
