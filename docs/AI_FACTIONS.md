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

## Pre-engagement warning — #276

Built 2026-11-21, default-on for recognised HC camp/patrol actors enrolled by
`HCXAffiliationCues.Actor`. Native compile, boot and one-client verification are
pending (EXP-L3); no gameplay acceptance is claimed. Existing readiness output
is retained; no extra module, scheduler, world scan or targeting system is added.

For a currently selected human contact with provider LOS and a fresh geometry
check, non-hostile factions warn at 40–80 m: turn/look and raise toward the
observed player, request the native heavy-melee vocalisation and send status
text. After 1.5 s, attempt one real chambered-round warning discharge. Normal
provider fire at that contact is held while the player remains in that band
with their weapon lowered. Closing to 40 m or raising a weapon engages without
an eight-second timer; hostile factions skip warnings. Accepted defence and
betrayal remain authoritative. Backing outside 80 m, losing observation or
lowering a weapon outside 40 m clears cached aggression; surrender still uses
the existing classifier. A lowered weapon does not prevent proximity engagement
inside 40 m.

The shot uses native `Weapon.Fire` with an explicit trajectory toward terrain
12 m perpendicular to the observed player's approach. It does not call
Expansion's target-based ballistic solver. Terrain must be 1–8 m below the
origin, with a clear ray ending at the intended ground point and no object
intersections. Unsafe terrain, obstruction, an empty/non-firearm hand, a busy
weapon manager, non-bullet/explosive ammunition, or failed native fire leaves the shout/text fallback. There is
one attempt, no retries, queued burst, ammo creation or refill. Native chamber
state is used to rebuild/synchronise the weapon FSM; Expansion's existing client
shot RPC requests presentation. **The offset/raycast is not proof against native
ricochet, dispersion or other projectile behaviour. The never-hit requirement
remains an open native acceptance condition.**

Admission is shared across actors: at most one warning/shot attempt per player
identity per 60 s, also one per actor per 60 s. The session-only table retains
at most 64 opaque keys, reclaiming only expired cooldowns. No identities are
printed or persisted. Each actor holds one selected contact and one admitted
shot recipient; target changes cannot transfer the pending shot. Existing
per-target stance records remain capped at eight actors. Fire interlock receipts
expire after 2 s without fresh threat evaluation. No new tick loop is added;
one admitted attempt performs one terrain raycast. Work/cost at target load
remains provisional.

Observed API references (installed APIs only, no provider implementation copied):

- Native `4_World/Entities/Core/Inherited/Weapon.c:35,57–58,74–79,11`:
  muzzle selection, fire eligibility, explicit native fire, chamber state and sync.
- Native `4_World/Entities/Firearms/Weapon_Base.c:667–705`:
  `RandomizeFSMState` derives state from real chambers/magazine, including spent rounds.
- Native `3_Game/Global/Game.c:1176`, `Global/DayZPhysics.c:199`:
  `SurfaceY`, `RaycastRV`; `1_Core/proto/EnConvert.c:153,156,233`: vector helpers.
- Native `4_World/Entities/ManBase/PlayerBase.c:6924,7779`:
  `MessageStatus`, `RequestSoundEvent` (voice event, no melee action).
- Installed Expansion `ai_scripts.pbo/4_World/DayZExpansion_AI/Entities/AI/eAIBase.c`:
  `eAI_CanFire:1276`, `eAI_FireWeaponOnClient:1189`, `eAI_UpdateFSM:7071`,
  `RaiseWeapon:9755`, `LookAtPosition:9937`, `AimAtPosition:9944`.
- Installed Expansion `Entities/Weapons/Firearms/Weapon_Base.c:60,157,166`:
  native-fire delegation and client presentation interfaces. Existing target/LOS
  and defence API references remain in the `HCXStance.c` header.

Lead checks, one server plus at most one client: compile and ready lines;
peaceful 80 m approach/shout/text/aim then exactly one audible warning shot;
real chamber/magazine delta of one and subsequent cycling/reload; no hit or
client ghost hit, including uneven ground, walls, slopes, shotgun/burst/auto
weapons and ricochet cases; clear fallback for no gun, no ammo and unsafe path;
40 m engagement, raised-weapon engagement, lowering/backing-off and surrender;
hostile factions skip warnings; both cooldowns across multiple actors,
reconnect/respawn, interrupted LOS and target switches. Check RPT:
`[HollowCountry] Stance warning: shout + text; keep back 40m; runtime=PENDING`,
`[HollowCountry] Stance warning_shot fired offset=12m runtime=PENDING` or
`[HollowCountry] Stance warning_shot fallback=...`,
`[HollowCountry] Stance hostile: faction, closing within 40m or raised weapon`,
and `[HollowCountry] Stance de-escalated: weapon lowered or outside caution range`.
Larger-load and multiplayer behaviour are not proven.

## Native checks still required

The lead must run the native compile gate and boot, then inspect with one server
and at most one client: all five armbands (including a transient raider with a
shared patrol loadout); flag factory/build/replication and readability before
contact; absence of loose kits, collectible flags and lifetime refresh; door and
navigation clearance; group-empty, zone-state change, stop/restart and crash
cleanup without saved duplicates. Existing operator loadouts may override or
need reprovisioning before the updated JSON is consumed. No engine acceptance
or multiplayer proof is claimed; target-load costs remain provisional.
