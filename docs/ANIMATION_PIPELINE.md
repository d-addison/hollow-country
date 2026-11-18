# Infected animation pipeline (posed infected)

Status: **experimental. Built offline only; not observed in DayZ.** No server or client has loaded
`HollowCountryAnims.pbo` yet. Runtime acceptance and production enablement are pending.

Goal: give infected new poses and a get-up from each ("bodies that rise"). **Sitter first:** only
the sit-against-a-wall-or-tree loop and its get-up are built, until they work natively. Sleep and
feed are deferred (see the end). Only the new class `HC_ZmbM_Sitter` uses the pose layer. Every
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

- **Clips.** Poses are written as code in `build_infected_clips.py`: lean angles, analytic two-bone
  IK for the arms and legs, and a breathing/sway cycle. That code is applied to frame 0 of the
  installed vanilla erect idle and written as a SET6 `.anm` with `tools/anim/anm.py`. The skeleton
  hierarchy comes from the installed `hermit_newbindpose.xob` (`tools/anim/rig.py`). The repo
  holds no game data, only the code.
- **Graph: no vanilla graph content is shipped.** `build_anims_addon.py` reads the installed
  `anims_workspaces.pbo` at build time only, and ships just two generated files:
  - `hc_infected.agr`. Our graph file references the vanilla template `infected.ast`, the sync
    table and the three vanilla sheets (`Locomotion.agf`, `Combat.agf`, `Interaction.agf`) by their
    `DZ/` paths. It declares the ControlTemplate interface the vanilla sheets and the engine bind
    to: 8 variables and 8 commands, names and default/min/max only. To that it adds our `HCPose`
    variable, our synchronized `CMD_HC_POSE` command, our sheet `hc_poses.agf`, an empty Debug
    block with our own id, and `DefaultRunNode "HCMasterControl"`. The vanilla Debug panel (most of
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
| SitWall | SitWallGetUp | `CMD_HC_POSE` with int 0, or `MovementSpeed > 0.5` | 0.2 s |
| SitWallGetUp | Vanilla | 0.25 s before the clip ends | 0.25 s |
| SitWall / SitWallGetUp | Vanilla | any vanilla DEATH, HIT_LIGHT, HIT_HEAVY, CRAWL, ATTACK or VAULT command | 0.15 s |

The brief asked for a variable to drive this. We used a synchronized command instead, because every
vanilla infected command is `Synchronized 1` and we have not seen a plain graph variable replicate to
clients. The script still sets `HCPose`.

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

## Deferred clips (after the sitter works natively)

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
