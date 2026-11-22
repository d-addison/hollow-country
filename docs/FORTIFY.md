# Fortification packs (barricades and shelter-scale kits)

Status: source and offline checks only, **implemented-unverified**. No native compile, boot or
in-game run has been done for this feature; nothing here is multiplayer-proven.

Two optional Workshop packs are supported: a barricade pack (door, double-door and window
barricades that attach to existing buildings) and a base-kit pack (shelter-scale kits only).
Hollow Country never references either pack's script classes. All pack knowledge sits in one
bridge class (`HCFortifyBridge`) that works on config names only (`Object.IsKindOf`,
`ConfigIsExisting`), so a server without the packs boots and the module reports `enabled=false`.
The packs are Workshop dependencies: they are never repacked, patched or redistributed.

## Pack terms and size

| Pack | Licence / terms | Client download |
| --- | --- | --- |
| Barricade pack | AGPL-3.0 (recorded in the issue; the packed addon carries an AGPL credits string; no licence file ships in the Workshop folder) | about 154 MB |
| Base-kit pack | No licence file or licence text ships with it; treat as all rights reserved by the author and use it only as a Workshop dependency | about 55 MB |

Sizes were measured from the installed Workshop folders on the dev host. The author's
Workshop description was not available offline, so the kit pack's redistribution terms remain
unconfirmed; that is why nothing from either pack is copied into the repository.

## Behaviour

1. **Claim-member-only building.** Placing a pack kit or building a part on a pack barricade
   goes through the native action finish on the server. If the position is covered by a Hollow
   Country building claim, only members of that claim's group may place or build; otherwise the
   action is refused with a reason code and a player status line. On ground no claim covers,
   building is allowed while `FortifyUnclaimedBuild` is true and refused (`unclaimed_building`)
   when it is false. An unavailable claim service refuses (`claim_unavailable`); the claim gate is
   never bypassed. Dismantling and destruction stay native.
2. **Raiders breach, visitors never do.** A barricaded doorway blocks the raider's line of
   sight to the door. The raid logic records the barricade that stopped the ray and treats it as
   the breach target for raiders only. Each raid step, when the raider stands within about 4 m with the
   barricade in sight, it applies one bounded damage step through the same damage path as
   infected. Traders and visitors never target, breach or path through a barricade. There is no
   teleport and no impassable wall: the barricade is destroyed part by part or the raid gives up
   under the existing raid timers.
3. **Infected door pressure.** The infected door watcher already queries objects near a watched
   door. A standing door barricade among them redirects the pressure from the door to the
   barricade: its weakest standing part loses health in proportion to elapsed time over
   `FortifyBreachSeconds` (heavy infected take half the window; one pressure step is capped at 5 s
   and at the existing door `MaxStep`). When a part reaches the ruined level the native
   construction code destroys that part. No instant destroy and no immune wall. If the server
   disables base damage (the vanilla `disableBaseDamage` setting) the breach is refused with
   `damage_disabled`, never overridden, and the refusal does not refresh the door's hot-priority
   stamp, so other doors are not starved.
4. **Shelter-scale kits only.** From the base-kit pack the allowed kits are the single door,
   small window, low wall, wood storage and floor hatch kits. Foundations, walls, ceilings, roofs,
   floors, pillars, gates, stairs, ramps, full doors and windows and the prefab base kit are refused
   (`rag_scale_excluded`). If the kit pack's build-anywhere option is on, every kit from that pack is
   refused (`rag_build_anywhere_on`) and a warning line is printed at start; the server operator
   switches it off in the pack's own config (Hollow Country never writes it).
5. **Counters.** `[HC Ready] module=Fortify` is printed at start; `[HC Use]` counters
   `fortify_placed`, `fortify_refused` and `barricade_breached` are registered through
   `HCModuleReadiness`.

## Settings

| Setting | Default | Range | Meaning |
| --- | --- | --- | --- |
| `EnableFortify` | true | bool | Master switch; the module is also off while no pack is present |
| `FortifyUnclaimedBuild` | true | bool | Allow pack building on ground no claim covers |
| `FortifyBreachSeconds` | 90 | 10..900 | Seconds for sustained pressure to ruin the weakest standing part |

Missing keys in an existing profile keep their defaults (no wipe, no boot failure).

## Log lines

- `[HC Ready] module=Fortify enabled=<bool> ready=<bool> reason=<code> runtime=PENDING`
- `[HC Fortify] started barricade_pack=<0|1> kit_pack=<0|1> breach_seconds=<n> runtime=PENDING`
- `[HC Fortify] refused reason=<code> runtime=PENDING` (at most one per 60 s, no identities)
- `[HC Use] module=Fortify feature=fortify_placed|fortify_refused|barricade_breached count=<n>`

Reason codes: `rag_scale_excluded`, `rag_build_anywhere_on`, `claim_not_member`,
`claim_unavailable`, `unclaimed_building`, `damage_disabled`, `no_breakable_part`.

## Limits and unproven items

- Whether a barricade origin falls inside the infected door query radius of the door's sound
  position is unproven; the in-game check decides whether the door-watch radius needs a different
  anchor.
- Shelter-kit doors and windows are scale-gated but are not raider breach targets; only the
  barricade pack's door barricades are.
- Boot, compile, client smoke and multiplayer behaviour are all unproven. The activity floors need a
  player to place and a breach to happen, so a soak without that scenario will not move them.
