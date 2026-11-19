# Infected animation pipeline (posed infected)

Status: source authored; native playback, skinning and two-client acceptance **PENDING**.
The owner requests source/package implementation before connecting a client. Missing native
verdicts are admitted unverified, never evidence of observed DayZ behaviour. The shared admission
edit below is required before poses 2–4 are selected; this worker does not own that file.

## Build route

```
python3 -B tools/anim/build_infected_clips.py --addons <installed-DayZServer>/Addons --out <external-build-dir>
python3 -B tools/anim/build_anims_addon.py --addons <installed-DayZServer>/Addons --out <external-build-dir>
```

No Blender, Workbench or PowerShell is needed for this route. Neither build was run for #225;
the lead performs asset generation and native inspection. Generated clips, preview data, graph
interfaces and PBOs stay outside Git. Never commit installed game assets or vanilla graph copies.

The standard-library generator reads only `z_hermit_m.xob` HEAD skeleton rest records from installed
`characters_zombies.pbo`: parent-local translations and rest rotations (`rig.load_skeleton`).
It turns the pelvis to face +Z, then authors rotations, offsets and analytic two-bone IK. It never
reads vanilla `.anm` keys. `stand_pose` is our own A-pose-derived stand; untouched bones retain
skeleton rest transforms. Helpers stay at the origin; no entity root motion is authored.

Every idle has a closed sinusoidal cycle including matching first/last frames. Every get-up starts
on its idle's neutral frame and ends exactly on our `stand_pose` before the graph blends to vanilla.
These are construction properties, not measured native seams or a guarantee against foot sliding.
Intermediate stages use smooth local quaternion/translation interpolation; contact and ground
penetration still need inspection. All clips use the existing SET6 writer and common skeleton bone
list. `preview.py` and the optional Blender preview show only our FK, never engine playback.

| Command int | Mode | Clips | Seconds idle / get-up | Authored route |
|---|---|---|---|---|
| 1 | sit_wall | hc_sit_wall_idle / hc_sit_wall_getup | 4 / 1.6 | seated, crouch, stand |
| 2 | prone_sleep | hc_prone_sleep_idle / hc_prone_sleep_getup | 4 / 2.6 | side sleeping, all fours, crouch, stand |
| 3 | riser | hc_lie_rise_idle / hc_lie_rise_getup | 4 / 2.8 | supine loose limbs, sitting, crouch, stand |
| 4 | feed_kneel | hc_feed_kneel_idle / hc_feed_kneel_getup | 1.2 / 2.0 | both knees down, dipping torso/working hands, crouch, stand |

`hc_lie_face_down_idle` / `hc_lie_face_down_getup` (4 / 2.8 s) are also authored and packaged
for inspection. They are an alternate pair, not randomly selected or bound to command 3: its shipped
state remains supine. Selecting another idle while a scripted command is running is not supported.
The body never consumes or creates food/loot through these visual clips.

## Graph and package

Only `HC_ZmbM_Sitter` uses our graph. Every vanilla infected keeps the native graph.
`build_anims_addon.py` generates our `.agr` with DZ references to the installed template, sync table
and vanilla Locomotion/Combat/Interaction sheets, plus our `hc_poses.agf`. It extracts the required
ControlTemplate declarations at build time and appends `HCPose`, `HCPoseFrom` (both ints 0–4) and
synchronized `CMD_HC_POSE`. Vanilla declarations keep their order. No vanilla Debug panel or sheet
is copied. No `.ast` is shipped.

Our `.asi` uses the installed vanilla instance as `ParentTemplates`; it contains only our slot
resource overrides. The installed template has only three unused Default animations, so #225
also uses unused **animation names** in Idles. The GroupSelect nodes select Idles columns, but the
installed sheets reference `Idles.Idle01`, never Idle02/03/04. Build-time `check_dead_slots` verifies
each name exists in the template and instance and refuses if any vanilla sheet mentions it.
This is text evidence; native internal use of an apparently dead slot remains unverified.

| Template slot | Own clip |
|---|---|
| Default.Normal.z_erc_idle_fight01 | hc_sit_wall_idle |
| Default.Normal.z_erc_attack_up_combo03 | hc_sit_wall_getup |
| Idles.VarA.Idle02 | hc_prone_sleep_idle |
| Idles.VarA.Idle03 | hc_prone_sleep_getup |
| Idles.VarA.Idle04 | hc_lie_rise_idle |
| Idles.VarB.Idle02 | hc_lie_rise_getup |
| Idles.VarB.Idle03 | hc_feed_kneel_idle |
| Idles.VarB.Idle04 | hc_feed_kneel_getup |

The source graph adds three state pairs beside SitWall. Each follows:

```
Vanilla -> Idle      CMD_HC_POSE == N; blend 0.6 s
Idle -> GetUp        CMD_HC_POSE == 0 AND HCPoseFrom == N; blend 0.2 s
GetUp -> Vanilla     RemainingTimeLess(0.25); PostEval 1; blend 0.25 s
Idle/GetUp -> Vanilla  death, hit light/heavy, crawl, attack or vault; blend 0.15 s
```

`HCPoseCommand.HCSend` binds/sets `HCPoseFrom` before issuing the synchronized command.
It records the leaving pose from the last positive command. Each state has its own get-up, so
one wake cannot select another pose's get-up. The graph-variable replication/order is unproven;
especially check waking on a remote client and a client joining during the rise. The command
resends held poses every 2 s for streaming clients. It never re-enters a pose during the rise.

Native API evidence (installed scripts-1.30.164289, paths relative to snapshot):
`3_Game/Entities/DayZAnimal.c:10,14,35` BindCommand, BindVariableInt, GetAnimInterface;
`3_Game/Anim/AnimCommand.c:27,29` PreAnim_CallCommand and PreAnim_SetInt;
`3_Game/Entities/DayZInfected.c:67,77,123` scripted command, finish flag and start;
`4_World/Entities/Creatures/Infected/ZombieBase.c:203-231` vanilla command handling order.
The adapter header retains the remaining native citations. No Expansion API was added.

The PBO contains config, script, our AGF, generated AGR/ASI and ten generated `.anm` clips.
Stage/sign it beside HollowCountry.pbo inside `@HollowCountry/addons` with the same development key.
The server and both clients must load identical files. No new mission data or module slot is needed.

## Runtime integration and exact lead edit (#225)

The configurable cap already exists: `HCInfectedVarietyConfig.MaxPosed=12`, bounds 0–64,
missing-field restoration, mission JSON and startup line. `MaxPosed=0` opts out. There is no
`MAX_POSED` constant to replace. The dormant/LOD budgets and server-wide held-slot accounting,
including a rising body, remain authoritative. No new settings or numerical gameplay limits
are introduced by #225.

Existing `PosedFreshEvery=3` selects every third fresh body; zero or
`$profile:HollowCountry/acceptance/infected_poses.disable` opts out. The adapter also checks that
marker on direct requests. Pose 0 remains unconditional cleanup. The existing context policy selects
wreck=3, roadside=2, gas_station=4, church/building=1 after admission. It uses normal tracked
materialization, shared per-tick work and every-player visibility/clearance vetoes. No new spawn,
teleport, alert, inventory, provider or gameplay controller is introduced.

**Required integration outside this worker's file scope:** in
`mods/HollowCountry/scripts/4_World/Infected/Variety/HCPostureAdmission.c`, replace the final
sit-only return of `HCCanEnter` with:

```c
        return mode == "sit_wall" || mode == "prone_sleep" || mode == "riser" || mode == "feed_kneel";
```

In `HCPostureRefusal`, replace the sit-only return and the following ASSET_NOT_AUTHORED branch with:

```c
        if (mode == "sit_wall" || mode == "prone_sleep" || mode == "riser" || mode == "feed_kneel") { return "none_graph_admitted_unverified"; }
```

In `HCLine`, change the sit-only `if` to:

```c
        if (mode == "sit_wall" || mode == "prone_sleep" || mode == "riser" || mode == "feed_kneel")
```

Keep existing rise durations (2.6, 2.8, 2.0 for poses 2–4). Update comments describing these modes
as unshipped. The four-row support queue is unchanged; feeding is already included in the tier-C
startup line. Keep status derived through `HCGetOperationalStatus` / `HCOperationalStatus.HCPublish`;
no hard-coded ready override. No HCModule/config.cpp/MISSION_FILES/settings registry edit is needed.
Until this edit lands the existing sitter fallback remains active; source authoring alone does not
change admission. The additional `[HC Variety] anim_poses=source_authored` line reports each mode's
actual `HCTierCState`, so it cannot falsely claim the integration landed. While enabled poses lack shared admission,
`HCFault()` exposes `anim_poses_shared_admission_pending` through the existing operational-status
hook and logs it once through `HCRefuse`. The fault disappears after the lead edit and restart;
no missing native verdict is treated as a fault.

## Lead native acceptance

Build externally, inspect previews/contact, then DayZDiag and a normal signed PBO/server with two
clients. Spawn the class, request each pose 1–4 server-side before its command starts (or let the
fresh Variety contexts select it). Test alert/proximity/noise/damage wake, one complete rise,
death/hit/attack interruption, late join during idle and rise, deletion and cap release. Test
MaxPosed=0, cadence=0 and the disable marker. Re-enable and ensure capped fresh materialization
remains hidden from both viewpoints. Never use a teleport to fix a visible pose or blocked door.

Grep boot RPT:

- `[HC Variety] max_posed=12 bounds=0..64 opt_out=MaxPosed=0 runtime=PENDING`
- `[HC Variety] anim_poses=source_authored prone_sleep=admitted_unverified riser=admitted_unverified feed_kneel=admitted_unverified acceptance=native_two_client_pending runtime=PENDING` (after lead integration)
- `[HC Variety] tier_c=custom_graph`
- `[HC Variety] posed_fresh_every=`

Grep exercise RPT: `[HollowCountryAnims] pose request pose=2` (and 3/4),
`pose command started pose=`, `pose released posed=`, `pose refused reason=max_posed_budget=`.
All new adapter diagnostics include `runtime=PENDING`. Also inspect `SCRIPT (E)`, `Virtual Machine
Exception`, `Cannot load`, `Unknown command`, `CMD_HC_POSE`, `HCPoseFrom`, `hc_infected` and
`HCMasterControl` errors on server and clients.

Known limits: upright collision capsule on lying bodies; no root motion; hand-authored transitions
can slide feet or intersect terrain; native inheritance, dead slots and variable replication are
unverified. Ground/contact targets (sleep pelvis <=0.25 m, quiet lying sway <=2 cm, closed loops,
standing seam <=SEAM_METRES) still require generated-asset inspection. No assets were generated
or inspected in this confined run, and no animation fidelity or performance acceptance is claimed.
