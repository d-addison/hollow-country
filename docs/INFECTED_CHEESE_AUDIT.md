# Infected anti-cheese audit (#137)

Players climb onto cars, trains and other objects and punch the infected
below them without taking any hits back. This audit lists each cheese vector,
its native cause, whether the exposed script API can fix it, the fix and its
cost.

Native citations refer to the installed `scripts-1.30.164289` snapshot
(`~/.cache/hollow-country/native-scripts/`). Source lives in
`mods/HollowCountry/scripts/4_World/Infected/Reach/`. Every row is source-only.
Nothing here has been seen working in DayZ yet. DayZDiag, normal PBO/server
runs and single-client checks are still pending; target-load budgets remain provisional.

## Why the infected below cannot hit back (native cause)

- **Chasing infected cannot attack upward at all.** CHASE infected only have
  pitch −1 attacks, with 2.4 m reach (`DayZInfectedType.c:72-73`).
- **The fight up-attack reach is measured in 3D.** FIGHT has up attacks
  (pitch 1, 1.7 m, `DayZInfectedType.c:80-81`). The attack logic compares
  that 1.7 m against the 3D `vector.Distance` (`ZombieBase.c:743/:749`), and
  the WasHit branch checks the same 3D distance again (`:649`). An infected
  standing at a 1.5 m roof measures about 1.9 m to the player, so the up
  attack never fires.
- **A native gate also blocks elevated targets.** Both attack paths first
  call proto native `CanAttackToPosition` (`DayZInfected.c:115`,
  `ZombieBase.c:698/:746`). Its semantics are not exposed to script, and
  it refuses elevated targets.
- **Car occupants are exempt.** A vanilla hotfix returns early for any
  target with `GetCommand_Vehicle()` (`ZombieBase.c:689/:730`), so infected
  do nothing to players inside vehicles.
- **Infected only vault on demand.** They vault only when the native AI sets
  `IsVault()` (`DayZInfectedInputController.c:4`, `ZombieBase.c:433`).
  Vehicles and props normally do not trigger that.
- **The ground near a raised player can be off the walkable navmesh.** The
  AI then has nowhere to path to. It stands, re-paths or jitters under the
  player.

## Audit table

| Vector | Native cause | Exposed API can fix? | Fix | Cost |
|---|---|---|---|---|
| Car/truck roofs, hoods, beds | 3D reach plus `CanAttackToPosition` refusal | Yes, partly | **Fix 1, height-aware reach.** A target 0.8–2.3 m up and ≤1.7 m away horizontally gets a vanilla FIGHT up attack via `ChooseAttack(FIGHT, horizontal, 1)`. It hits a leg (`dmgZone_leftLeg/rightLeg`, `dayzplayer.c:481-482`) through `DamageSystem.CloseCombatDamageName` (`DamageSystem.c:23`). The strike needs a line verdict from our own ray. If the player stands on the vehicle and cannot be reached, **fix 3** batters the vehicle | Per admitted infected: O(1) per frame plus one `CanAttackToPosition`. Up to 1 ray per landed swing |
| Occupied vehicles | Vanilla occupant hotfix | Yes | **Fix 3, battering.** The swing targets the vehicle, never the occupant. On WasHit, one ray toward the vehicle is followed by `DamageSystem.CloseCombatDamage` (`DamageSystem.c:22`) on the struck component. Each vehicle takes at most one hit per 2 s, at most 8 vehicles are tracked, entries expire after 60 s, and battering stops on disengage | 1 ray per swing |
| Train cars, containers, low walls, rocks, deer stands | Same reach cause; these are static, non-Transport objects | Reach yes; damage to the object no | Fix 1 when 0.8–2.3 m. Above that, or with no line, **fix 4** applies. Static objects are never battered | As above |
| Ladders | The player is on a ladder above the infected | Reach yes | Fix 1 reaches the legs in the band. The navmesh filter excludes ladders, so infected never climb | As above |
| Platform vault (≤ about 2 m) | Vault only on the native `IsVault()` signal | Command yes, landing unknown | **Fix 2, a logged experiment.** It calls `StartCommand_Vault(type)` (`DayZInfected.c:109`; the debug plugin does the same, `PluginDayZInfectedDebug.c:401`) when the target is on a 0.8–2.0 m platform, ≤1.6 m away horizontally, ≤25° from facing, and a knee ray hits the platform. Limits: once per 15 s per infected, at most 4 at a time, no position writes. Each attempt logs whether the infected landed on top (Y rose ≥0.6 m). After 6 attempts with 0 landings, the session retires it as a **native limit**, and fixes 1 and 3 remain | ≤1 extra ray per evaluation while a candidate exists |
| Unreachable for N s | Navmesh near the target fails or sits far below it | Steering only | **Fix 4, back-off.** It triggers after 6 s without a reach hit while the target is ≥0.8 m up, ≤4 m away and off the walkable navmesh (`AIWorld.c:122`, same filter as `HCInfectedNavigation.c:110-111`). The infected retreats (walk, up to 3 m or 3 s), circles (tangent walk 2 s), then waits facing the target (3 s), then gets 4 s of cooldown. It uses only `OverrideMovementSpeed`/`OverrideHeading` (`DayZCreatureAIInputController.c:3/:9`), reapplied each frame and released as soon as the phase ends, the target comes down, the mind state changes or the target leaves 8 m. There are no position writes | 1 navmesh sample per evaluation |
| Noise draws nearby infected | — | Yes, already | No synthetic noise. A waiting infected stays in its native CHASE/FIGHT state and keeps vocalizing natively. The existing `HCAlertChain` relays only real native voice events (`ZombieBase.c:556` via `HCInfectedModule.NativeVoice`): at most 8 roots, at most 12 recipients, 15 m × strength, a two-ray geometry gate. Only infected that already target the player take part in reach or back-off. There is no omniscient retargeting | 0 new work |
| Closed doors | Native door handling | — | Owned by #136 (another worker, `Doors/`). Listed only | — |
| Windows and crawl gaps | The native AI cannot crawl through low gaps; window vaults depend on navmesh jump links | No (no script API adds navmesh links or a crawl-through) | **Native limit.** The native vault already handles fences and windows where links exist | — |
| Fences and vault points | Native `IsVault()` plus `GetVaultType` (`ZombieBase.c:401-443`) | Already native | No change. Fix 2 applies only to raised platforms | — |
| Deep water | The infected navmesh excludes swim polygons; infected have no swim command | No | **Native limit.** Fix 4 is not applied to water, since the target is lower, not elevated | — |
| Stairs and narrow corners | Native pathing; 3D reach on stair landings above the infected | Partly | Fix 1 covers a landing 0.8–2.3 m above the infected. The line ray stops hits through floors and walls | As fix 1 |
| Pillar dancing and kiting | Native turn rate; 30° fight cone (`ZombieBase.c:4`); native re-path | Only `OverrideTurnSpeed` (`DayZCreatureAIInputController.c:6`), whose semantics for infected are unverified | **Native limit, documented.** No change: forcing turn speed is an unobserved engine API | — |
| Loss of interest | Native perception decay | Already | Existing HC clue/investigation and the alert chain keep infected searching the last real cue. Unchanged | — |
| Doubled stamina vs outrunning | The HC stamina profile: drain 0.25, recovery 2.5 | Config | **Tuning knob only, unchanged.** See below | — |

## Stamina tuning knob (documented, not changed)

`config/hollow-country-stamina.json` → `Settings.ContinuousExertionScale`
(currently 0.25) and `Settings.RecoveryScale` (currently 2.5). These are read
by `3_Game/Survival/HCStaminaSettings.c` and `HCStaminaConfiguration.c` and
validated within 0.05..5.0. The current values let a player sprint about 4×
longer than vanilla, which makes outrunning infected trivial.

To make outrunning harder, raise `ContinuousExertionScale` toward 0.5 or 1.0,
or lower `RecoveryScale` toward 1.25 or 1.0. That is an owner decision, and
this issue does not change it.

## Bounds

- **Server only.** Nothing runs on clients.
- **Admission.** The infected itself asks to be admitted, at most once per
  second while it has no slot. It must be in CHASE or FIGHT, its native
  target must be a player within 4 m horizontally, and that player must be
  ≥0.8 m above it or seated in a vehicle. Slots are fixed at 16; a full table
  is refused and counted. A slot is held up to 10 s without context and 180 s
  at most.
- **Module tick** (HCServer cadence, `TickIntervalMs` 1000). At most 6
  evaluations inside a 4 ms `HCWorkBudget` slice, with the cursor retained.
  Each evaluation makes at most 4 native queries (a line ray, a floor ray or
  vehicle lookup, a vehicle-contact or platform ray, and a navmesh sample),
  so at most 24 per tick. There is no world scan and no `GetPlayers`.
- **Per frame** (admitted infected only). O(1) arithmetic, one
  `CanAttackToPosition` in MOVE frames (vanilla already calls it every
  attack frame), and at most 1 ray per landed swing.
- **Hooks.** Only `ZombieBase.ModCommandHandlerBefore` (`ZombieBase.c:203`).
  The WasHit frame is resolved and consumed there, so the composition does
  not depend on link order with `HCInfectedNative.c`'s FightLogic contact
  guard. Vanilla keeps precedence wherever its own attack would fire.

## Owner checks in game (local server, one client)

1. **Startup.** The server log has `[HollowCountry] V2 admission feature=InfectedReach`
   and `[HC Reach] started slots=16 evaluations_per_tick=6`.
2. **Fix 1.** Stand on a car roof or hood with an infected chasing you. Its
   swings should hit your legs: leg damage, and possibly bleeding or a broken
   leg through the native damage. The log shows `[HC Reach] first elevated strike landed`.
   - Repeat behind a wall or on a building's first floor. You should not be
     hit through it, and the `blocked=` count in `[HC Reach] summary` rises.
3. **Fix 3.** Sit in a car with infected around it. They should swing at the
   car, it should take damage, and you should not. The log shows
   `[HC Reach] first vehicle batter`.
   - Also stand on a truck roof higher than about 2.3 m.
4. **Fix 2.** Stand on a 1–2 m platform, such as a low wall or car hood.
   - Watch `[HC Reach] vault attempt` and `vault outcome landed_on_top=`.
   - `vault experiment retired: native limit observed` means the engine
     cannot end a vault on top, and that is recorded as the native limit.
5. **Fix 4.** Stand on a container roof or deer stand for 6 s or more.
   Infected should back off about 3 m, side-step, then face you.
   - The log shows `[HC Reach] first backoff`.
   - Nearby infected may arrive only through real native vocalizations
     (existing chain).
6. **Overload.** With more than 6 active, there is at most one
   `[HollowCountry] perf budget module=InfectedReach deferred=` line per
   600 s.

Check visible swings, vaults and vehicle damage on the connected client.

## Remaining gaps

- **Native attack command.** Whether `StartCommand_Attack` with a FIGHT up
  type plays correctly during CHASE is unobserved.
- **Vault landing.** Whether a vault ever lands on a vehicle or prop is
  unobserved, which is why fix 2 is an experiment.
- **Heading override.** Whether `OverrideHeading` takes an absolute yaw for
  infected is unverified. The code assumes the same convention as
  `DayZAnimal.c:466/:550`.
- **Vehicle damage.** How much zombie melee ammo damages each vehicle zone,
  and which impact sound plays, is unobserved.
- **Weapon damage path.** Leg-zone damage via `CloseCombatDamageName` with
  the AI hit-component name follows vanilla's own call. The resulting
  bleed and fracture rates are unmeasured.
- **Load cost.** The per-tick cost has not been measured at 3–6 players.
- **Out of scope.** Windows, crawl gaps, deep water and pillar turn rate
  remain native limits.
