# Reading AI affiliation

Issue #256, affiliation cues; source implementation 2026-11-20. Native compile,
boot and one-client gameplay acceptance are pending. Visual cues ship with the
existing AI sites feature, without a new setting or module.

| Faction | Display name | Armband | Site flag |
| --- | --- | --- | --- |
| Locals | Zimovniki | Green (`Armband_Green`) | `Flag_NAPA` |
| Volunteers | Dobrovoltsy | Blue (`Armband_Blue`) | `Flag_CDF` |
| Scavengers | Sborshchiki | Yellow (`Armband_Yellow`) | `Flag_Bear` |
| Raiders | Volki | Red (`Armband_Red`) | `Flag_Chedaki` |
| Travellers | Travellers | White (`Armband_White`) | `Flag_White` |

These are Hollow Country identification conventions, not changes to the native
flags' lore. A colour identifies affiliation, not guaranteed safety: perception,
self-defence and betrayal still govern reactions. No player trading or talking
is introduced. Unknown/custom factions keep their own equipment and get no flag.

The five shipped role loadouts have a guaranteed armband: Holdout green, Patrol
blue, Scavenger yellow, Raider red, Traveller white. Shared role loadouts can
serve several factions (including transient raiders using the patrol loadout).
The existing site's `SetupAI` callback therefore replaces a mismatched armband
with the patrol's resolved faction colour after the provider applies its loadout.
Only this spawn-time cue is replaced; role weapons, supply odds and kit variants
are unchanged. Operator loadouts used by this path receive the same correction.

Site markings use vanilla `StaticFlagPole`, fully built with a raised decorative
flag. At most 16 poles exist per director, with one candidate and one tracked owner inspected per tick and
two shared AI-sites work units requested by the existing director. Only occupied, non-transient sites are
marked; wandering transient groups carry their affiliation on their arms. A
candidate sits eight metres east and north of the site/house anchor at terrain
height. Placement waits until players are at least 200 m away and the director's
observer raycast cannot see it. A 3 m House veto and a 64-object query-result cap
refuse unsuitable candidates. There is one placement attempt per occupied
lifecycle; a refused candidate is not retried continuously. Marking coverage is
therefore conservative, and door clearance still requires native inspection.

Poles are removed when the site's group becomes empty or disappears (on its
next cursor visit), when rotation removes its state, and all tracked poles are removed on director stop. Native
`ECE_NOPERSISTENCY_WORLD` and `ECE_NOPERSISTENCY_CHAR` exclude them from saves;
no journal, lifetime refresh or new persistence schema is added. The decorative
pole suppresses vanilla's loose construction-kit creation, flag removal,
player raising/lowering, damage and refresher-time additions. Ordinary static
poles retain native behaviour. Flags provide no collectible scenery loot.

## API and config evidence

Read-only installed vanilla `characters_tops.pbo/config.bin` declares all five
armbands with scope 2, inheriting the `Armband` slot from `Armband_ColorBase`.
`gear_camping.pbo/config.bin` declares all five flags with scope 2 and contains
`StaticFlagPole : TerritoryFlag`. Native scripts 1.30.164289 provide
`StaticFlagPole.FullyBuild`, `BaseBuildingBase.CreateConstructionKit`,
`TerritoryFlag.AnimateFlagEx` / `AddRefresherTime01`, inventory attachment
creation, attachment release checks and the no-persistence creation flags.
Installed Expansion `eAIDynamicPatrol.c:376–394` applies a loadout before
`SetupAI`; the patrol's `m_Faction` supplies the resolved faction even for the
first member before the group faction is assigned. No provider source
is copied into this change.

## Warning deferred

Installed Expansion `eAIBase.c:10857–10860` documents that
`Expansion_SetEmote` queues an emote until its FSM can enter `PlayEmote`.
Threat processing and combat can cancel emotes; scheduling one cannot establish
that a hostile AI warns before firing. No safe pre-engagement warning hook was
established from the installed API. The radius/line-of-sight warning is deferred;
there is no new player scan, warning cooldown table or combat suppression.

## Native checks still required

The lead must run the native compile gate and boot, then inspect with one server
and at most one client: all five armbands (including a transient raider with a
shared patrol loadout); flag factory/build/replication and readability before
contact; absence of loose kits, collectible flags and lifetime refresh; door and
navigation clearance; group-empty, zone-state change, stop/restart and crash
cleanup without saved duplicates. Existing operator loadouts may override or
need reprovisioning before the updated JSON is consumed. No engine acceptance
or multiplayer proof is claimed; target-load costs remain provisional.
