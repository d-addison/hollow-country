# Infected deaths: native audit and supported selection (#32)

Status: source implemented, runtime acceptance PENDING. Nothing here has been
observed in DayZ. Offline tests prove the authored decision table and the
generated probe bytes only; they never establish DayZ behavior, animation
appearance, replication, collision, loot access or cleanup.

Citations are `file:line` relative to the inspected native script cache
(`scripts-1.30.164289`, engine 1.30.164289), written without the home path.
"Observed" means seen in a recorded run; everything else is read from source.

## 1. Native death path (read from source)

| Step | Where | Notes |
| --- | --- | --- |
| Death animation types | `3_Game/Entities/DayZInfected.c:29-34` | `ANIM_DEATH_DEFAULT=0`, `IMPULSE=1`, `BACKSTAB=2`, `NECKSTAB=3`. What each one looks like is not in script and is unobserved. |
| Native command | `3_Game/Entities/DayZInfected.c:110` | `proto native void StartCommand_Death(int pType, float pDirection)`; `COMMANDID_DEATH` at `:6`. The animation and any physics behind it are engine-side. |
| Hit handling, kill sync | `3_Game/Entities/DayZInfected.c:138-174` | `EEHitBy` runs the vanilla shock/leg handling then, once `!IsAlive()`, sends `SyncEvents.SendEntityKilled` once (`:174`). |
| Heavy-hit override | `3_Game/Entities/DayZInfected.c:131,193-202` | Public `m_HeavyHitOverride`, set for Torso/Head shock damage at or above `LEG_CRIPPLE_THRESHOLD = 74.0` (`:129`). Left set on a dead infected, so it is readable at death evaluation. |
| Death type and direction fields | `4_World/Entities/Creatures/Infected/ZombieBase.c:346-347` | `m_DamageHitDirection`, `m_DeathType`. |
| Selection hook | `ZombieBase.c:363` | `bool EvaluateDeathAnimationEx(EntityAI pSource, ZombieHitData data, out int pAnimType, out float pAnimHitDir)`; calls `EvaluateDeathAnimation` (`:370`). |
| Hook caller | `ZombieBase.c:981-993` | `EEHitBy` calls `super.EEHitBy` first (`:983`), then, if `!IsAlive()`, `EvaluateDeathAnimationEx(source, data, m_DeathType, m_DamageHitDirection)` (`:993`). |
| Vanilla type choice | `ZombieBase.c:373-376` | `doPhxImpulse = ConfigGetInt("cfgAmmo "+ammo+" doPhxImpulse") > 0`, then `pAnimType = doPhxImpulse`: only ammo with that flag gets IMPULSE. |
| Vanilla impulse | `ZombieBase.c:382-388` | If `doPhxImpulse`, vanilla itself calls `dBodyApplyImpulse(this, impulse)` with `80 * m_TransportHitVelocity` (y forced to 120). This happens inside `super`, so a mod override cannot undo it. |
| Direction | `ZombieBase.c:379,929-948` | `ComputeHitDirectionAngle`: 0 = source in front, sign from the cross product, range +-180. |
| Command start | `ZombieBase.c:198-217,349-361` | `CommandHandler` calls `HandleDeath` (`:211`); when `!IsAlive() \|\| m_FinisherInProgress` it calls `StartCommand_Death(m_DeathType, m_DamageHitDirection)` (`:353`), sets `m_MindState = -1` and `SetSynchDirty()` (`:356`). |
| Finishers | `ZombieBase.c:1060-1087` | `IsBeingBackstabbed()` returns `m_FinisherInProgress`; `SetBeingBackstabbed` sets BACKSTAB/NECKSTAB (`:1074,1078`) or DEFAULT (`:1082`) and `m_FinisherInProgress = true` (`:1086`). |
| Heavy-hit classification | `ZombieBase.c:907` | `hitAnimation > 0 \|\| m_HeavyHitOverride` (alive hit reactions; reused by the policy so "heavy" means the same thing). |
| Kill event | `3_Game/Entities/EntityAI.c:1104` | `EEKilled`, "called on server when the entity is killed". `DayZAnimal.c:237-241` overrides it and notes it is never called on clients in multiplayer (DAYZ-28269). |
| Client-side hit | `EntityAI.c:1153`, `ZombieBase.c:1014` | `EEHitByRemote` is only for the client that caused the hit. |
| Debug reference | `4_World/Plugins/PluginBase/PluginDayZInfectedDebug.c:429` | Vanilla's own debug tool calls `StartCommand_Death(deathType, deathDir)` with a chosen type and angle, so selecting a type is an intended, supported usage of the native command. |

EEKilled versus EEHitBy ordering is not observed. The design does not depend
on it: the decision is made inside the `EEHitBy` call chain, before the next
`CommandHandler` starts the death command.

## 2. Authority and replication

| Aspect | Server-authoritative | Replicated | Mod may influence |
| --- | --- | --- | --- |
| Which death type/direction is chosen | yes (`EEHitBy` chain, `ZombieBase.c:993`) | by the engine, mechanism unobserved | yes: through `EvaluateDeathAnimationEx` outputs only |
| Death command start | yes (`HandleDeath`, `ZombieBase.c:349-356`) | script side is `SetSynchDirty` + `m_MindState = -1` only | no (left vanilla) |
| Animation playback on clients | engine | unobserved | no |
| Physics impulse | vanilla `dBodyApplyImpulse` (`ZombieBase.c:388`) | unobserved | no: tied to ammo `doPhxImpulse`, applied in `super` |
| Kill sync / killer data | yes (`DayZInfected.c:174`) | yes | no |
| Corpse, collision, loot/skinning, cleanup | engine and CE | unobserved | no (left vanilla); skinning component is created in server-only `EEKilled` (`DayZAnimal.c:240`) |

## 3. Supported result selected

The only supported lever found is the DEFAULT-versus-IMPULSE choice (and the
direction, which is left to vanilla). Source:
`mods/HollowCountry/scripts/4_World/Infected/HCInfectedDeathPolicy.c` (pure
scalar policy) and `HCInfectedDeath.c` (admission + the single override).

Policy, in order:

1. Finisher in progress: unchanged.
2. Vanilla already chose anything other than DEFAULT (IMPULSE from
   `doPhxImpulse`, BACKSTAB/NECKSTAB): unchanged.
3. Leg zones (`LeftLeg`, `RightLeg`): DEFAULT (vanilla knee fold stays).
4. Not heavy (`hitAnimation > 0 || m_HeavyHitOverride`): DEFAULT.
5. Not frontal (`|direction| <= 60`, NaN refused): DEFAULT.
6. Torso or Head: IMPULSE. Any other zone: DEFAULT.

Net: the single departure from vanilla is upgrading a heavy, frontal torso or
head kill from DEFAULT to the native IMPULSE animation. No velocity, impulse,
teleport, health, animation-instance or client-owned state is added; corpse,
collision, loot and cleanup stay on the vanilla path. Whether IMPULSE actually
looks like a folding or ragdoll-like fall is the open question the paired
controls exist to answer. If the rendered controls show no visible difference,
the correct disposition is "no selectable variant", not acceptance.

Admission mirrors `HCFuelSiphonQualification`: `Qualified()` returns false;
the override is on by default and is turned off only by the opt-out marker
`$profile:HollowCountry/acceptance/infected_deaths.disable`, probed once per
process and logged as EXPERIMENTAL with runtime acceptance PENDING. Decisions
are logged at most 16 times per process.

## 4. Unsupported (explicit disposition)

- Full or per-limb infected ragdoll: unsupported. `PhysicsSetRagdoll`,
  `PhysicsIsRagdoll` and `PhysicsSetSimpleDeath` exist only on `Human`/player
  (`3_Game/human.c:1449-1452`, class `Human` at `:1359`); `DayZInfected` and
  `DayZCreatureAI` (`DayZAnimal.c:191`) have no ragdoll API. The player path
  itself carries a TODO (`4_World/Entities/DayZPlayerImplement.c:2454`,
  "Temporary code until we have a ragdoll command"). A mod cannot create the
  capability from script; `1_Core/proto/EnWorld.c:184` only exposes a RAGDOLLS
  debug flag.
- Generic physics (`dBodyActive`, `dBodyApplyImpulse` at
  `1_Core/proto/EnPhysics.c:64,141`) exists but applying it to an animating
  creature is exactly the velocity hack this project forbids, and vanilla
  already does it for `doPhxImpulse` ammo.
- Visible difference between DEFAULT and IMPULSE: unobserved (no render
  evidence; animation graphs are not in the script cache).
- Per-client replication of the chosen type: unobserved; a single-client check is
  needed before any production claim.
- Ammo `doPhxImpulse`/`hitAnimation` values: the cached `config.bin` is too
  small to read them offline, so the policy reads them at runtime through
  `ConfigGetInt` exactly as vanilla does.
- Corpse collision, loot access and cleanup: unobserved, left vanilla.

## 5. Prior runs

| Run | What it observed |
| --- | --- |
| run 043 | Five-case probe, stock CE. Outer budget ended during map entity loading. No mission init, no receipt. |
| run 047 | Stock CE with `InitOffline` kept, 180 s outer. Mission initialized; the victim spawned with `ECE_PLACE_ON_SURFACE\|ECE_INITAI` and a health-only kill was seen inside the synchronous OnInit (`dead_observed=1`, `frames=0`). No SYSTEM callback ran and no death command was recorded; status timeout. |
| run 062 | Compile failure: a continuation line began with `\|\|` (script_log syntax error at the guard). Fixed by keeping each guard on one line. |
| run 064 | Compile failure: override parameter names differed from the prototype, giving "Can't find variable". Fixed by using `pSource/pAnimType/pAnimHitDir/pDt/pCurrentCommandID/pCurrentCommandFinished`. |
| run 065 | Compiled; the Tick callback ran, the owned Stone source spawned, then an engine access violation ("Illegal read ... at 0x0") in `Spawn`, crash log frame `hcdeathselection.c:247` (the victim `CreateObjectEx(... , ECE_INITAI)`), about 7 s after mission load. Receipt held only the begin-time save (frames 0, no cases); status timeout, cleanup confirmed. |

### The ECE_INITAI crash: what is and is not known

Evidence: the only successful infected creation (run 047) used
`ECE_PLACE_ON_SURFACE|ECE_INITAI` with stock CE running; the crashing creation
(run 065) used `ECE_INITAI` alone with CE initialization omitted. Every vanilla
creation in the cache passes both (`PluginDayZInfectedDebug.c:367`,
`PlayerBase.c:6812`, `PluginDeveloper.c:454`).

`ECE_PLACE_ON_SURFACE` is 1060 = `ECE_CREATEPHYSICS|ECE_UPDATEPATHGRAPH|ECE_TRACE`
(`3_Game/CE/CentralEconomy.c:38`; `ECE_INITAI = 2048` at `:18`). So run 065
created an AI creature without `ECE_CREATEPHYSICS`, without a path-graph update
and without a surface trace, in a CE-less world. The leading hypothesis is
that AI initialization without those flags dereferences a null pointer; the
alternative is the CE-less AI world itself. Neither is proven. The crash cannot
be attributed from the log alone, and the control that separates the two
(stock CE) is impractical under Wine because `InitOffline` stalls (runs 052,
058, 061).

The probe therefore gained `spawn_profile` so the next run changes exactly the
creation flags and nothing else:

| Profile | Flags | Purpose |
| --- | --- | --- |
| `initai-only` (default when absent) | `ECE_INITAI` | Reproduces run 065 byte for byte. Not for new evidence. |
| `surface-initai` | `ECE_PLACE_ON_SURFACE\|ECE_INITAI` | Vanilla debug flags and the run-047 spawn. Run this first. |
| `surface-only` | `ECE_PLACE_ON_SURFACE` | No AI agent. If `surface-initai` still crashes, this separates "creation" from "AI init". A creature without an agent may never start the death command; the validator then refuses it, which is the correct outcome. |

## 6. Native paired-control probe (stage only)

`tools/setup/death_selection_probe.py` stays CE-disabled and fixed-world. New,
all optional (absent = the previous probe, byte for byte, checked against the
committed version): `spawn_profile`, and `selection: "policy"`, which adds the
production policy file to the addon and replaces the forced case-1 IMPULSE with
`HCInfectedDeathPolicy.SelectDeathType(...)`. In policy mode the fixture sets
`m_HeavyHitOverride = true` before the fatal MeleeFist torso hit in case 1 only,
and the receipt records `policy_type` and `heavy_override`. The validator then
requires case 0 (vanilla) to leave type 0 and case 1 to show policy type, after
type and command type all equal to 1, with a frontal observed direction
(`|hit_direction| <= 60`). A rear direction means the source must be moved to
the other side and the run repeated; it is never accepted.

Stage (writes files only; no launch). Run from the repository root, with a fresh
`$EXP` that does not exist yet:

```
SERVER=~/.cache/hollow-country/wine-server-20261116
NATIVE=~/.cache/hollow-country/native-scripts/scripts-1.30.164289
EXP=~/.cache/hollow-country/experiments/compile-084-death-selection
mkdir -p "$EXP"
python3 -m tools.setup.death_selection_probe \
  --stock-init "$SERVER/mpmissions/dayzOffline.chernarusplus/init.c" \
  --interfaces "$NATIVE" --destination "$EXP/stage" \
  --victim 6500 6500 --source 6500 6502 \
  --spawn-profile surface-initai --selection policy \
  --policy-source mods/HollowCountry/scripts/4_World/Infected/HCInfectedDeathPolicy.c
```

The tool stages `init.c`, the addon sources, the manifest and the packed
`@HCDeathSelectionProbe/addons/hc-death-selection.pbo` (its packer reproduces
the run-065 PBO byte for byte from the run-065 bundle). Then assemble a fresh
experiment, exactly as run 065 was laid out:

```
mkdir -p "$EXP/profiles" "$EXP/storage"
cp -r "$SERVER/mpmissions/dayzOffline.chernarusplus" "$EXP/death.chernarusplus"
cp "$EXP/stage/init.c" "$EXP/death.chernarusplus/init.c"
cp -r "$EXP/stage/@HCDeathSelectionProbe" "$EXP/@HCDeathSelectionProbe"
mkdir "$EXP/battleye" && cp "$SERVER/battleye/BEServer_x64.dll" "$EXP/battleye/"
cp ~/.cache/hollow-country/experiments/compile-065-death-selection/serverDZ.cfg "$EXP/serverDZ.cfg"
```

Launch, owner-run only, one profile per fresh experiment because a crash kills
the process. Use `DayZDiag_x64.exe ... -server` for the DayZDiag control or
`DayZServer_x64.exe` for the normal server, the environment of the existing
Wine harness (`WINEPREFIX` = the isolated prefix, `WINEARCH=win64`,
`WINEDEBUG=-all`) and a 180 s outer cap:

```
W() { printf 'Z:%s' "${1//\//\\}"; }
cd "$EXP" && timeout -s TERM 180 xvfb-run -a /usr/lib/wine/wine64 "$SERVER/DayZServer_x64.exe" \
  -ip=127.0.0.1 -port=2402 -config="$(W "$EXP/serverDZ.cfg")" -profiles="$(W "$EXP/profiles")" \
  -storage="$(W "$EXP/storage")" -BEpath="$(W "$EXP/battleye")" -mod="$(W "$EXP/@HCDeathSelectionProbe")" \
  -mission="$(W "$EXP/death.chernarusplus")" -doLogs -adminLog -noPause
```

Afterwards validate `profiles/hc-death-selection-result.json` with
`validate_receipt` against the staged files, passing the real outer outcome and
duration; scan `crash_*.log` for an access violation first. If
`surface-initai` crashes, stage a new experiment with `--spawn-profile
surface-only` and compare. There is no committed runner for this probe: runs
062-065 used an out-of-repo runner, and `tools/setup/wine_compile_probe.py` only
runs the older five-case probe. The staged layout and command above are taken
from the run-065 report.

What a clean receipt would and would not show: that the override ran once, the
policy chose IMPULSE for a heavy frontal torso kill, the death command received
that type and direction unchanged, and cleanup was observed. It would not show
how either variant looks, how the connected client presents the fall, or anything about
collision or loot. Those need a rendered side-by-side (DayZDiag with a client
window, vanilla ammo versus the opt-in marker) and client presentation on one
connected client. `HCInfectedDeathQualification.Qualified()` stays false until that
evidence exists and is reviewed.

## 7. Cost and bounds

The override adds one config integer lookup, one pure policy call and at most 16
log lines per process, on the server only, once per kill. There are no loops,
timers, RPCs, entities or persisted state, so cost does not grow with horde
size. This bound is by construction and has not been measured on target load.
