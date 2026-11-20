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

Source implementation 2026-11-20; native compile, boot and one-client playback
acceptance remain pending. Recognised HC site actors are enrolled by the same
spawn-time callback that assigns their faction armband. The cue is default-on
with those actors; unrelated Expansion actors are not enrolled. No setting or
module is added, and the existing module readiness output is unchanged.

After Expansion processes its current target and line of sight, an enrolled,
living, conscious, unrestrained AI can request one native heavy-melee vocalisation
(`EPlayerSoundEventID.MELEE_ATTACK_HEAVY`) on first seeing a living human player
within 80 m. This reuses a nonverbal native combat vocalisation, not spoken
dialogue, and starts no melee action. The AI must regard the player as an enemy,
have its weapon lowered, be outside the fighting FSM and melee, and have active
threat below Expansion's 0.4 fighting threshold. Actors already engaging do not
warn. A target change, loss of LOS or leaving the radius ends that contact; a
cooldown refusal is not retried during uninterrupted contact.

The server allows at most one request per AI and per player identity every
60 seconds. The session-only identity table holds at most 64 opaque keys; at
capacity it can reclaim one expired row, otherwise it refuses the cue. It never
evicts a live cooldown, retains no player objects and neither logs nor persists
identities. AI contact tracking holds one weak player reference per actor. Each
targeting update does constant work except an eligible admission at table
capacity, which checks at most 64 rows. There is no player/world scan, extra
raycast, queue, persistence, combat suppression or engagement delay. Cooldowns
count requests because a client can refuse a voice event under native sound
priority rules; no repeated playback attempts are made.

Installed API review (API names and observed ordering only; no provider code
copied):

| Class / method | Finding |
| --- | --- |
| `eAIBase.eAI_Targeting`, `eAI_OnUpdate`, `eAI_UpdateFSM`; `ExpansionWorld.eAI_OnUpdate` | Selected hook: targeting and LOS finish before the later FSM update in both normal and distributed update modes. The simulation-disabled path passes `checkLOS=false` and is excluded. |
| `eAIBase.EnforceLOS`, `eAI_HasLOS` | Uses only the current target's provider LOS, including its normal 0.15 s cache interval. Non-current target caches can be stale and are not used. |
| `eAIBase.eAI_AddTarget`, `eAI_GetTargetInformationState`, `PlayerIsEnemy`; `eAIPlayerTargetInformation.CalculateThreat` | Acquisition/threat alone does not establish visibility. The selected hook additionally requires current-target LOS and the provider's hostility decision. |
| `eAIBase.DetermineThreatToSelf`, `ReactToThreatChange`; `eAITargetInformationState.UpdateThreat` | Threat can rise gradually or jump after aggression. Only the below-0.4 pre-engagement case is eligible; threat is never rewritten. |
| `eAICallbacks.OnTargetSelected`, `OnLOS`, `OnActiveThreatLevelChanged` | Callbacks exist before FSM processing, but a transition-only callback would miss entry into 80 m while an already-visible target approaches. |
| `eAIState_Fighting.OnEntry`, `eAIState_Fighting_FireWeapon.OnEntry` / `OnUpdate`, `eAIBase.TryFireWeapon` | Combat/fire hooks are too late for a not-yet-engaged warning and are left unchanged. |
| `eAIBase.Expansion_SetEmote`, `Expansion_PlayEmote`; `eAIState_PlayEmote.Guard` | Queued emotes are unsuitable: the guard rejects raw threat above 0.2, raised weapons and fighting. Direct emotes introduce gesture locks and asynchronous cancellation. Neither route is used. |

Native 1.30.164289 evidence: `PlayerBase.RequestSoundEvent` /
`RequestSoundEventEx` / `SendSoundEventEx` sends the native replicated sound
event, while `CheckSoundEvent` plays it on receipt. `MeleeAttackHeavyEvent`
registers voice animation event 17; `MeleeAttackSoundEvents.CanPlay` needs no
melee action, and damage audio keeps priority. Installed vanilla
`sounds_hpp.pbo/config.bin` declares the male/female heavy-melee voice shaders.
`EmoteTaunt` exists in native scripts but is deliberately not started.

The lead must still run native compile and boot, then use one server and at most
one client to check audible warning/shot ordering, native voice range and helmet
attenuation, faction hostility, LOS/occlusion and 80 m entry, both 60-second
cooldowns (including respawn/reconnect), contact re-entry, and unchanged combat
response. Sound replication and client priority may affect what is heard before
a shot; source ordering is not an engine acceptance result. Larger-load cost
remains provisional; no multiplayer proof is claimed.

## Native checks still required

The lead must run the native compile gate and boot, then inspect with one server
and at most one client: all five armbands (including a transient raider with a
shared patrol loadout); flag factory/build/replication and readability before
contact; absence of loose kits, collectible flags and lifetime refresh; door and
navigation clearance; group-empty, zone-state change, stop/restart and crash
cleanup without saved duplicates. Existing operator loadouts may override or
need reprovisioning before the updated JSON is consumed. No engine acceptance
or multiplayer proof is claimed; target-load costs remain provisional.
