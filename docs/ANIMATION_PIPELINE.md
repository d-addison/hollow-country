# Infected animation pipeline (posed infected)

Status: **experimental. Built offline only; not observed in DayZ.** No server or client has loaded
`HollowCountryAnims.pbo` yet. Runtime acceptance and production enablement are pending.

Goal: give infected new poses and a get-up from each ("bodies that rise"). **Sitter first:** only
the sit-against-a-wall-or-tree loop and its get-up are built, until they work natively. Sleep and
feed are specified at the end (asset spec) and refuse by name until authored. Only the new class `HC_ZmbM_Sitter` uses the pose layer. Every
vanilla infected keeps the vanilla graph.

## Route

```
tools/anim/build_infected_clips.py  pose code + installed standing frame -> build/anims/clips/*.anm
tools/anim/build_anims_addon.py     our sheet/clips/hook + references to the installed vanilla graph -> build/anims/addons/HollowCountryAnims.pbo
tools/anim/preview.py               build/anims/preview/*.json -> stick-figure GIFs (offline)
```

```
python3 tools/anim/build_infected_clips.py --addons /mnt/d/SteamLibrary/steamapps/common/DayZServer/Addons --out build/anims
python3 tools/anim/build_anims_addon.py   --addons /mnt/d/SteamLibrary/steamapps/common/DayZServer/Addons --out build/anims
python3 tools/anim/preview.py --out <dir> --name hc-sit-wall-idle build/anims/preview/hc_sit_wall_idle.json
```

The `build/` folder is gitignored. Both build scripts read the installed game and never write to it.

- **Clips: no vanilla animation frame is used.** Poses are written as code in
  `build_infected_clips.py`: lean angles, analytic two-bone IK for the arms and legs, and a
  breathing/sway cycle. The code starts from the rest pose of the `HC_ZmbM_Sitter` mesh skeleton,
  the HEAD bone records (parent-local rest translation and rotation per bone) of `z_hermit_m.xob`
  in the installed `characters_zombies.pbo` (`rig.load_skeleton`, `rig.rest_pose`). The pelvis
  gets a 180 degree turn about Y, because the mesh rests facing -Z and the clips face +Z. The rest
  pose is an A-pose, so `stand_pose` builds our standing pose from it: it leans the spine, neck and
  head, staggers the feet and lowers the arms by IK. Untouched bones keep their skeleton rest
  transforms.
  - **Bone list.** It is the mesh bones minus `LookAt`, both hip helpers and four fourth finger
    joints, plus `EntityPosition`, `Collision`, `RightHandIK_Helper`, `RightHandIK` and
    `LeftHandIK` held at the origin. The list matches the bone set of vanilla infected clips.
    Vanilla animates `RightHandIK_Helper`; ours holds it still.
  - **Seam.** The get-up ends on our stand, not on the vanilla idle. The distances to vanilla
    `zA_erc_idle01` frame 0 are 0.014 m at the pelvis, 0.056 m at the head, 0.070/0.046 m at the
    left/right hand and 0.036/0.049 m at the left/right foot; the largest joint distance is 0.119 m
    at `LeftForeArm`. The 0.25 s blend back to vanilla covers this seam (`SEAM_METRES = 0.12`).
  - **Vanilla clips are read only by tests.** They check the bone set, the seam, and that no
    shipped key matches any vanilla clip key.
  - The repo holds no game data, only the code.
- **Graph: no vanilla graph content is shipped.** `build_anims_addon.py` reads the installed
  `anims_workspaces.pbo` at build time only, and ships just two generated files:
  - `hc_infected.agr`. Our graph file references the vanilla template `infected.ast`, the sync
    table and the three vanilla sheets (`Locomotion.agf`, `Combat.agf`, `Interaction.agf`) by their
    `DZ/` paths. It declares the ControlTemplate interface the vanilla sheets and the engine bind
    to: 8 variables and 8 commands, names and default/min/max only, in vanilla order. After them it
    appends our `HCPose` variable and our synchronized `CMD_HC_POSE` command. It also adds our sheet
    `hc_poses.agf`, an empty Debug block with our own id, and `DefaultRunNode "HCMasterControl"`. The vanilla Debug panel (most of
    the vanilla file) is not carried.
  - `hc_infected.asi`. This is a child instance: `Template` is the vanilla `.ast` and
    `ParentTemplates` is the vanilla `infected_main.asi`, the engine's own inheritance (vanilla
    `player_main_1h_bandage.asi` inherits `player_main_1h.asi`, which inherits `player_main.asi`;
    `samples/zombie_commonsamples/zoWA.asi` inherits `zoW.asi`). It holds only our two lines.
  - **No `.ast` is shipped.** Our two clips fill two dead slots of the vanilla template:
    `Default.Normal.z_erc_idle_fight01` (sit loop) and `Default.Normal.z_erc_attack_up_combo03`
    (get-up). Both are declared in `infected.ast` and filled by `infected_main.asi`, but no vanilla
    sheet or graph names them, and no vanilla GroupSelect selects the `Default` group. Overriding
    them in our child instance therefore changes no vanilla state. The build refuses if a DayZ
    update starts using either slot (`check_dead_slots`).
  - **Residual for an owner decision.** The interface declarations (the 16 names with their
    default/min/max values) match vanilla lines, because any graph file that runs the vanilla
    sheets must declare them. They are generated from the installed game at build time and are
    not stored in the repo.
  - `test_shipped_members_carry_no_vanilla_graph_content` enforces all of this against the
    installed game. Every shipped `.agr`/`.asi` line that matches a vanilla line must be an
    interface declaration, a bare format keyword, one of our two slot names or a `DZ/` resource
    reference. The test also requires that no `DZ/anims/anm` clip line and no `.ast` is shipped.
  - `test_no_clip_key_matches_a_vanilla_frame_except_skeleton_rest` reads every SET6 clip in the
    installed infected animation PBO. For each bone, no shipped key may equal or lie within 2e-4
    of a vanilla key, unless the key is within 1e-3 of that bone's skeleton rest transform or of
    zero/identity. A bit-for-bit check alone would miss a copy: re-quantizing a copied frame
    changes its bits. Against the earlier build, whose stand came from vanilla idle frame 0, this
    test fails.
  - DayZ loads text graphs at runtime (the Dog mod is the precedent), so no Workbench graph compile
    step is used.
- **Addon.** `mods/HollowCountryAnims/` contains:
  - `config.cpp`, which defines `HC_ZmbM_Sitter : ZmbM_HermitSkinny_Beige` with its own
    `enfanimsys` and changes no vanilla class;
  - `hc_poses.agf`;
  - the server hook `scripts/4_World/HCPoseInfected.c`.

### Packaging (inside `@HollowCountry`)

`HollowCountryAnims.pbo` ships in `@HollowCountry/addons/` next to `HollowCountry.pbo`. There is
no separate Workshop item, and the base and anims PBOs always load together on the server and the
client. PBO members:

```
anims/infected/clips/hc_sit_wall_getup.anm
anims/infected/clips/hc_sit_wall_idle.anm
anims/infected/hc_infected.agr
anims/infected/hc_infected.asi
anims/infected/hc_poses.agf
config.cpp
scripts/4_World/HCPoseInfected.c
```

The prefix is `HollowCountryAnims`, and the trailer is a SHA-1 hash like `tools/package/pbo.py`
writes. The hook for `tools/package/` staging (not wired yet) has three parts:

- Run the two build commands, or take `build/anims/addons/HollowCountryAnims.pbo` as an input.
  `pbo.py collect_addon` refuses binary sources, so it cannot pack the `.anm` clips itself.
- Add `HollowCountryAnims` to `pbo.PREFIXES`, so that `pbo.py verify --prefix HollowCountryAnims`
  and `sign.py` accept it. Today both refuse with `exact HollowCountry prefix required`.
- Copy the PBO into `@HollowCountry/addons/` and sign it with the same development key as
  `HollowCountry.pbo`, so the existing `.bikey` covers both. `sign.py` wants a fresh `--out`
  folder for each call, so either sign into a temporary folder and copy the `.pbo` and `.bisign`
  across, or run `DSSignFile.exe` on both PBOs in the same `addons` folder.

### Graph layer (`hc_poses.agf`)

| From | To | Condition | Blend |
|---|---|---|---|
| Vanilla | SitWall | `CMD_HC_POSE` with int 1 | 0.6 s |
| SitWall | SitWallGetUp | `CMD_HC_POSE` with int 0 | 0.2 s |
| SitWallGetUp | Vanilla | 0.25 s before the clip ends | 0.25 s |
| SitWall / SitWallGetUp | Vanilla | any vanilla DEATH, HIT_LIGHT, HIT_HEAVY, CRAWL, ATTACK or VAULT command | 0.15 s |

The brief asked for a variable to drive this. We used a synchronized command instead, because every
vanilla infected command is `Synchronized 1` and we have not seen a plain graph variable replicate to
clients. The script still sets `HCPose`.

The get-up does not test `MovementSpeed`, which could be stale, and it does not test `HCPose`. If
`HCPose` did not replicate, a client would see the default 0 and stand the infected up at once.
`MovementSpeed` is not needed. In vanilla `ZombieBase.c` `CommandHandler`, the move command starts
again only after the current command finishes (lines 225-228), and ours finishes only after the
get-up. Every other command start has its own exit transition: death (:353), vault (:427/:438),
attack (:715/:760), crawl (:815) and hit (:888).

### Server hook (`HCPoseInfected.c`)

- **Requesting a pose.** `HC_ZmbM_Sitter` asks to sit by itself 2 s after its server-side `EEInit`.
  Spawning it by class name from an admin tool, the CE or script is enough. Server code may also
  call `HCRequestPose(1)` to sit or `HCRequestPose(0)` to get up.
  `HC_ZmbM_Sitter.HCSpawnSitting(pos, yaw)` is a test helper that spawns one sitter facing `yaw`.
- **Holding the pose.** `ModCommandHandlerBefore` (called first, `ZombieBase.c:203`) starts a scripted
  command, `HCPoseCommand`. That command holds the infected in place and sends `CMD_HC_POSE` again
  every 2 s for clients that stream in late. This was 10 s; the cost is one synchronized command
  per posed infected every 2 s.
- **Standing up.** When the mind state reaches ALERTED, the infected gets up. The command then
  finishes and vanilla handling takes over. Vanilla death, hit and attack handlers keep running the
  whole time.
- **Budget.** At most 12 infected can be posed server-wide (`MAX_POSED`). A sitter beyond the
  budget logs `pose refused budget=12` and stays a normal infected. There is no per-frame scan; the
  only per-frame work is one integer compare for each posed infected.
- **Native citations.** Every native call is cited with its file and line in the file header
  (`scripts-1.30.164289`).

## Proven and not proven

| Item | State |
|---|---|
| `.anm` SET6 codec | Proven offline: every installed SET6 clip (more than 200) re-encodes byte for byte (`tests/unit/test_anim_anm.py`). |
| Authored clips | Offline only. The sit loop closes, keeps the root still, puts the pelvis below 0.35 m and the head above 0.75 m, and keeps both feet above the ground. The get-up starts seated and ends within 2 cm of the standing frame. |
| Graph text | Offline only. It references the vanilla template, sheets and instance by path, and fills two dead vanilla slots. |
| Engine accepts `ParentTemplates` in a mod `.asi` and our override of the `Default` slots | **Not proven.** The vanilla files show the mechanism; the engine has not loaded ours. |
| Engine loads the graph, plays the clip, skins correctly, replicates the command | **Not proven.** Requires DayZDiag plus the normal PBO on the server and one client; two clients for visibility and late-join checks. |
| Workbench TXA route (`tools/anim/workbench/HC_TxaBuild.c`) | Not proven: Workbench did not load the plugin, and Windows interop was down. Optional; the direct writer replaces it. |
| Blender render (`tools/anim/blender/hc_preview.py`) | Untested: interop was down and no Linux Blender was run. Previews were made with `tools/anim/preview.py` instead. |

The previews are **stick figures from our own FK**, not DayZ. They show pose and timing only.

## Human GUI steps

None are needed for this route. As an optional fallback, if the engine rejects our `.anm` files,
use DayZ Tools > Workbench > Resource Manager. Drag a `.txa` exported from Blender into the Resource
Browser, then right-click it and choose Register and Rebuild. You can also run `HC_TxaBuild` headless
with `WorkbenchApp.exe -wbmodule=ResourceManager -plugin=HC_TxaBuild -hcArgs=<file>`.

## Native steps for the lead

1. Build the PBO with the two commands above. Sign it with the same development key as
   `HollowCountry.pbo`, and place the `.pbo` and `.bisign` in `@HollowCountry/addons/`.
2. Start the server and the client with `@HollowCountry` as usual; no extra `-mod` entry is needed.
3. Spawn `HC_ZmbM_Sitter` by class name from an admin or debug console, about 3 m from the player.
4. Within about 2 s it should sit. Walk into its view and confirm it gets up, chases and attacks.
   Then kill a second sitter while it is seated.
5. Grep the server RPT for these lines:
   - `[HollowCountryAnims] pose request pose=1`
   - `pose command started pose=1`
   - `pose released posed=`
   - `pose refused budget=12`
6. Grep both RPTs for errors:
   - `SCRIPT (E)`
   - `Virtual Machine Exception`
   - `hc_infected`
   - `HCMasterControl`
   - `Cannot load` / `Unknown command` / `CMD_HC_POSE`
   - `z_erc_idle_fight01` / `z_erc_attack_up_combo03`

## Risks

- **Graph match.** The server and every client need the same PBO. Shipping it inside
  `@HollowCountry` makes that the default.
- **Dead-slot reuse.** The engine or another mod might use the `Default` group natively. Nothing in
  the vanilla text graphs does, but only a native run can rule it out. If it does, the fallback is
  a small own template, an `.ast` holding only our group, which needs an owner decision.
- **Vanilla drift.** The graph references are regenerated from the installed game on every build.
  The build refuses in three cases: `MasterControl` is no longer the start node, the
  ControlTemplate holds more than variables and commands, or a slot we fill stops being dead.
- **Other mods.** Expansion-AI or other mods may override infected graphs or
  `ModCommandHandlerBefore`. Only our new class is affected, but check the load order.
- **Replication and late joiners.** Command replication to clients is assumed and must be observed.
  A late joiner may see the wrong pose for up to 2 s.
- **Leaving the pose.** Death, hit or vault from the seated pose leaves through a 0.15 s blend, so
  expect some popping. Corpses are vanilla.
- **Foot sliding.** The get-up has no root motion. The body rises in place, and the collision
  capsule stays where the infected stands.
- **Performance.** At most 12 posed infected server-wide, one graph, the trivial per-frame compare
  and one resend every 2 s per posed infected. This budget is provisional until measured at 3 to 6
  players.

## Riser, flat sleeper and feeding: feasibility and exact asset spec (audit #121)

Status: **server adapter, selection and admission are built; the three clip pairs are not
authored, so the three modes refuse by name.** Nothing here was observed in DayZ.

### Native feasibility (scripts-1.30.164289, read only)

- **A reverse of the native crawl does not exist.** `ZombieBase.c:811-826` `HandleCrawlTransition`
  only starts `StartCommand_Crawl` and sets `m_IsCrawling`; `:1089-1092` `IsCrawling` stays true and
  the crawl command is only the transition. Nothing in the script API leaves the crawl state, so a
  "crawler that stands up" cannot be built from native animation. A lying body that rises must be an
  own graph state on our own class, not a crawler.
- **The route is the proven sitter route.** The scripted command (`DayZInfected.c:67
  DayZInfectedCommandScript`, `:123 StartCommand_ScriptInst`) holds the body and sends the
  synchronized command `CMD_HC_POSE` with an int (`AnimCommand.c:27 PreAnim_CallCommand`, `:29
  PreAnim_SetInt`). The same command and int already carry poses 1 to 4; only the graph states and
  clips are missing. Vanilla death, hit, crawl, attack and vault commands still win in
  `ZombieBase.c:203-231` and leave the pose through the 0.15 s blend.
- **Collision capsule.** The capsule stays upright and in place, as for the sitter. A lying body is
  therefore a standing-height collider. That is a known limit of this route (no root motion).
- **Not provable offline:** that the engine loads the added states, plays the clips and replicates
  the int to late joiners. Those stay runtime=PENDING.

### What the server adapter already does (`HCPoseInfected.c`, `HCPostureAdmission.c`)

| Concern | Behaviour |
|---|---|
| Admission | `HCCanEnter` admits a tier-C mode only when its assets ship; a test forces admission, `hc_poses.agf` entry transitions and `build_anims_addon.CLIPS` to change together. Unshipped modes log `pose refused ... reason=ASSET_NOT_AUTHORED_<mode> runtime=PENDING` once per change. |
| Selection | `HCInfectedVarietyPolicy.HCPoseFresh`: every Nth fresh body (`PosedFreshEvery`, default 3, 0 or `acceptance/infected_poses.disable` opts out) is an `HC_ZmbM_Sitter`. Context picks the pose (wreck 3, roadside 2, gas station 4, church or building 1) and falls back to the shipped sit. |
| Wake | `HCVarietyWake` (proximity, noise, shot, damage, alert, cap, stop) calls `HCVarietyPoseWake`, which requests pose 0. The body rises once, held still by the scripted command. |
| Interruption | A hit, death, vault or attack replaces the script command; the slot is released and the graph leaves through the 0.15 s blend. No new pose is accepted while a rise plays. Deletion releases the slot. |
| Rise length | `HCPostureAdmission.HCRiseSeconds(pose being left)`, so each clip bounds its own rise. |
| Budget | 12 posed bodies server-wide (`MAX_POSED`) plus the Variety dormant and LOD posed budgets. |

### Assets still to author (original, no vanilla or Expansion frames)

Author each pair with the existing route: pose code in `tools/anim/build_infected_clips.py`, pick two
more dead `Default.Normal.z_erc_*` slots (the build's `check_dead_slots` refuses a live slot), add
both to `CLIPS`, add the states and transitions below to `hc_poses.agf`, then flip the mode in
`HCPostureAdmission.HCCanEnter` and the matching row of `HCRiseSeconds` if the clip length differs.

| Pose (`CMD_HC_POSE == N`) | Mode | Idle clip (loop, 30 fps) | Get-up clip (no loop) | Rise s |
|---|---|---|---|---|
| `CMD_HC_POSE == 2` | `prone_sleep` | `hc_prone_sleep_idle`: lies on one side, knees slightly bent, pelvis within 0.25 m of the ground, slow breathing, loop closes within 1 cm, root still | `hc_prone_sleep_getup`: roll to all fours, then crouch, then stand. Starts on the idle end frame, ends within 2 cm of the `stand_pose` frame | 2.6 |
| `CMD_HC_POSE == 3` | `riser` | `hc_lie_rise_idle`: lies on the back or face down (one authored variant each), limbs loose, no breathing sway beyond 2 cm, loop closes | `hc_lie_rise_getup`: push up to sitting, then stand, a 2.8 s body that visibly struggles; same seam rule | 2.8 |
| `CMD_HC_POSE == 4` | `feed_kneel` | `hc_feed_kneel_idle`: both knees down, torso dipping to the ground and back, hands working, 1.2 s cycle, loop closes | `hc_feed_kneel_getup`: kneel, crouch, stand | 2.0 |

Every clip: SET6 `.anm` written by `tools/anim/anm.py`, the same bone list as the sit clips, no key
within 2e-4 of any vanilla key (the existing shipped-clip test applies), pelvis and head limits
asserted offline like the sit clip, and the last get-up frame within `SEAM_METRES` of the stand.

Graph text to add per pose N with idle state `X` and get-up state `XGetUp` (same shape as `SitWall`):

```
Vanilla -> X       Duration 0.6   IsCommand(CMD_HC_POSE) && GetCommandI(CMD_HC_POSE) == N
X -> Vanilla       Duration 0.15  IsCommand(CMD_DEATH) || IsCommand(CMD_HIT_LIGHT) || IsCommand(CMD_HIT_HEAVY) || IsCommand(CMD_CRAWL) || IsCommand(CMD_ATTACK) || IsCommand(CMD_VAULT)
X -> XGetUp        Duration 0.2   IsCommand(CMD_HC_POSE) && GetCommandI(CMD_HC_POSE) == 0
XGetUp -> Vanilla  Duration 0.15  (same interruption condition)
XGetUp -> Vanilla  Duration 0.25  RemainingTimeLess(0.25), PostEval 1
```

The `X -> XGetUp` transition for several poses shares the condition `GetCommandI(CMD_HC_POSE) == 0`,
so the engine cannot tell which idle state it is leaving. Give each idle state its own exit
condition by also sending the leaving pose in a second int (`HCPoseFrom`, bound next to `HCPose`)
before the command, and test `GetVariableInt(HCPoseFrom) == N` in the three exits. This is the one
graph change that has no sitter precedent and needs the native check below.

### Native check for the lead once a pair ships

Spawn the class by name, confirm the idle pose, walk close and confirm one rise, shoot beside it and
confirm one rise, kill it mid-rise and confirm a normal corpse. Grep the RPT for `pose request`,
`pose command started`, `pose released`, `pose refused`, `SCRIPT (E)`, `Cannot load`. Two clients are
needed for late-join and visibility.

## Deferred clips estimates (after the sitter works natively)

The owner deferred these until the sit pose and its get-up work natively. The same route applies
to each:

- Write a pose function.
- Pick another dead vanilla slot, add it to `CLIPS`, and let `check_dead_slots` vet it.
- Add a state and its transitions to `hc_poses.agf`.

| Clip | Notes | Estimate |
|---|---|---|
| sleep on the ground (side, loop) | pelvis on its side, slow breathing | ~0.5 day |
| get up from sleep | roll to all fours, then crouch to stand | ~1 day |
| kneel to feed (loop) | knees down, torso dipping, hands working | ~0.5 day |
| feed to stand | kneel, crouch, stand | ~0.5 day |
| graph states for all of the above, plus pose ids 2 and 3 | same command, more int values | ~0.5 day |

Hand-keyed motion written as code will look stiff next to motion-captured vanilla clips. If the
owner wants better quality, author in Blender and export through the TXA route.
