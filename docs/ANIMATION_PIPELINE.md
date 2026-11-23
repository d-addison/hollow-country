# Infected animation pipeline (posed infected)

Status: source authored; native playback, skinning and single-client acceptance **PENDING**.
The owner requests source/package implementation before connecting a client. Missing native
verdicts are admitted unverified, never evidence of observed DayZ behaviour. Shared admission
for poses 1–4 is integrated; missing native experiments remain pending.

## Build route

```
python3 -B tools/anim/build_infected_clips.py --addons <installed-DayZServer>/Addons --out <external-build-dir>
python3 -B tools/anim/build_anims_addon.py --addons <installed-DayZServer>/Addons --out <external-build-dir>
```

This is the only authoritative clip build route: the standard-library SET6 writer
(`tools/anim/anm.py`). The old Workbench TXA-to-ANM plugin (`tools/anim/workbench/HC_TxaBuild.c`) is
retired for clip builds (2026-11-22): it never ran, is in no build or package route, and stays in the
tree only as a deprecated prior-art file for a future non-SET6 Workbench probe.

No Blender, Workbench or PowerShell is needed for this route. Neither build was run for #225;
the lead performs asset generation and native inspection. Generated clips, preview data, graph
interfaces and PBOs stay outside Git. Never commit installed game assets or vanilla graph copies.

The standard-library generator reads only `z_hermit_m.xob` HEAD skeleton rest records from installed
`characters_zombies.pbo`: parent-local translations and rest rotations (`rig.load_skeleton`).
It turns the pelvis to face +Z, then authors rotations, offsets and analytic two-bone IK. It never
reads vanilla `.anm` keys. `stand_pose` is our own A-pose-derived stand; untouched bones retain
skeleton rest transforms. Helpers stay at the origin; no entity root motion is authored.

Joint frames (2026-11-22, owner report "sleep zombies head/arms are backwards"): bone positions
alone do not fix a limb's twist, and the old two-bone IK left elbows and knees flexing about
arbitrary axes (sleeper elbows 102/116 degrees off the mesh hinge, supine elbows 166, face-down knees
112/114: bent backwards). Poses derived from `stand_pose` now carry the mesh hinge axes (the rest
pose's own small elbow/knee bend, `hinge_axes`), and `two_bone` twists the upper bone so every bend
is on that hinge, plus a small inward shin turn with knee bend (`SHIN_SCREW`). Lying poses are
authored in body axes after the pelvis roll (`body_turn`, body-frame IK targets), never about
world axes, which twist a lying spine or roll a lying head. The SET6 codec was ruled out: vanilla
lying clips read anatomically right in our FK, and write/read changes local rotations by at most
0.003 degrees. The builder refuses to write clips (exit 1) unless `check_anatomy` passes on every
frame as written: head yaw/pitch/roll to Spine3 within 80/60/45, elbow and knee bend axis within
60/30 degrees of the hinge once bent 20, upper arm not behind the torso plane (forward >= -0.5 in the
chest frame), and bone twists within Arm 80, ForeArm 35, UpLeg 45, Leg 35
(`tests/unit/test_anim_anatomy.py`, skipped without the installed game). The lying clips now use
independent support poses: the left-side sleeper curls its knees with its lower hand under the
cheek, wakes head-first, uncurls toward its palms, tucks a knee and rises through an uneven squat;
the supine corpse has slack, asymmetrically splayed limbs and jerks into a sit before bracing to one
side and rising from a knee; the face-down alternate keeps its arms by its head before pushing up,
drawing its knees under and rising. Four-second lying loops combine shallow breathing harmonics
and a small hand twitch, with identical first/last frames. World-space limb targets hold support
contacts, lift transferred extremities, and keep both feet planted through a trailing-head lurch
and settle. Get-up durations and exact idle/stand endpoints are unchanged. Preview JSON carries
`Skull` and `Face` points to show head direction. These are offline FK art passes; the in-game look,
skinning, graph blends and terrain contact remain **PENDING** the lead's one-client check.

Every idle has a closed sinusoidal cycle including matching first/last frames. Every get-up starts
on its idle's neutral frame and ends exactly on our `stand_pose` before the graph blends to vanilla.
These are construction properties, not measured native seams or a guarantee against foot sliding.
Intermediate stages use smooth local quaternion/translation interpolation; contact and ground
penetration still need inspection. All clips use the existing SET6 writer and common skeleton bone
list. `preview.py` and the optional Blender preview show only our FK, never engine playback.

The optional Blender preview (`tools/anim/blender/hc_preview.py`) is pinned to **Blender 5.2 LTS**
(5.2.4, owner 2026-11-21; portable install outside Git). Qualified 2026-11-21: headless
`blender.exe -b --factory-startup` rendered `hc_sit_wall_idle` to a 121-frame 640x480 MP4 after
selecting `media_type = 'VIDEO'` (Blender 5.x lists FFMPEG only for video media). Earlier 5.1 runs
are not evidence for 5.2.

Add `--strip [N]` (default 8) after the three positional arguments to skip the video and render N
evenly spaced keyframes (first and last included) as `<name>-34-fNNN.png` stills plus one 4-column
contact sheet `<name>-34-sheet.png` (fixed EEVEE sample count, Standard view transform) for
deterministic visual diffing. Frame selection and layout are unit tested
(`tests/unit/test_anim_preview.py`); the render itself is **PENDING** a lead run on Blender 5.2 LTS.

Female posed infected: config-level parity is enforced by `ce_variants.py` (ZombieMaleBase and
ZombieFemaleBase `enfanimsys` must equal ZombieBase for the installed build, else it fails). Female
outfits still render on `z_hermit_m.xob`; whether that skinning looks right is native-only and stays
**PENDING** with the single-client acceptance (no rest-bone `.xob` metadata comparison is done offline).

| Command int | Mode | Clips | Seconds idle / get-up | Authored route |
|---|---|---|---|---|
| 1 | sit_wall | hc_sit_wall_idle / hc_sit_wall_getup | 4 / 1.6 | seated, crouch, stand |
| 2 | prone_sleep | hc_prone_sleep_idle / hc_prone_sleep_getup | 4 / 2.6 | left-side sleeper (head on lower arm), all fours, crouch, stand |
| 3 | riser | hc_lie_rise_idle / hc_lie_rise_getup | 4 / 2.8 | supine, arms beside the body, knees a little up, head turned; sitting, crouch, stand |
| 4 | feed_kneel | hc_feed_kneel_idle / hc_feed_kneel_getup | 1.2 / 2.0 | both knees down, dipping torso/working hands, crouch, stand |

`hc_lie_face_down_idle` / `hc_lie_face_down_getup` (4 / 2.8 s) are also authored and packaged
for inspection. They are an alternate pair, not randomly selected or bound to command 3: its shipped
state remains supine. Selecting another idle while a scripted command is running is not supported.
The body never consumes or creates food/loot through these visual clips.

## Graph and package

Only the public posed classes use our graph: the admin/herd `HC_ZmbM_Sitter` and the generated per-outfit
`HC_Zmb{M,F}_{Sitter,Sleeper,Riser,Feeder}_<outfit>` children, which the CE spawns as children of the vanilla
infected events (`infected/variants.json`). The generated `HC_Zmb{M,F}_Crawler_<outfit>` children and every
vanilla infected keep the native graph.
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
check waking on the connected client and reconnect during the rise. The command
resends held poses every 2 s for streaming clients. It never re-enters a pose during the rise.

Native API evidence (installed scripts-1.30.164289, paths relative to snapshot):
`3_Game/Entities/DayZAnimal.c:10,14,35` BindCommand, BindVariableInt, GetAnimInterface;
`3_Game/Anim/AnimCommand.c:27,29` PreAnim_CallCommand and PreAnim_SetInt;
`3_Game/Entities/DayZInfected.c:67,77,123` scripted command, finish flag and start;
`4_World/Entities/Creatures/Infected/ZombieBase.c:203-231` vanilla command handling order.
The adapter header retains the remaining native citations. No Expansion API was added.

The PBO contains config, script, our AGF, generated AGR/ASI and ten generated `.anm` clips.
Stage/sign it beside HollowCountry.pbo inside `@HollowCountry/addons` with the same development key.
The server and the connected client must load identical files. No new mission data or module slot is needed.

## Runtime integration

The configurable cap already exists: `HCInfectedVarietyConfig.MaxPosed=24`, bounds 0–64,
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

Shared posture admission was integrated in `06c22697`:
`HCPostureAdmission.HCCanEnter`, `HCPostureRefusal` and `HCLine` admit
`sit_wall`, `prone_sleep`, `riser` and `feed_kneel` unverified. Existing rise
durations for poses 2–4 remain 2.6, 2.8 and 2.0 seconds. Readiness still derives
through `HCGetOperationalStatus` / `HCOperationalStatus.HCPublish`; admission
supplies no native playback verdict. No additional shared edit is required.

The CE route (`44fa9fc2`, `ec6b12d1`) exposes all five HC variant classes through seven
vanilla events at 2–6% weight. All 57 substitutions preserve positive stock donor weights
and event sums; the city HC share is 5/106. This route is independent of fresh-body
materialization. `EnableInfectedVariety=false`, `infected_variety.disable` or
`infected_poses.disable` leaves CE variants standing and counts `refused_optout`;
wake/release stays available. Crawlers retain the vanilla graph and native crawl request.

`26fc6ac8` raises exact legacy `MaxTracked=24` to 256 in memory, logging one
`[HC Infected] config_migration MaxTracked legacy=24 now=256` line without rewriting
the profile; other operator values are honoured. `fbc8685a` recycles at most one eligible
far idle tracking record per bounded scan and separates herd lease capacity; it never
deletes or moves an infected. Native roster admission, CE playback, wake, crawler fall,
replication and the cost of 24 simultaneous holds remain **PENDING**. Inspect
`ce_variant_classes` (expected public=5/5) and `ce_variants` (first at 120 s, then every
300 s) for spawned/posed/playing/crawling/refused/woken/risen/interrupted counts.

## Lead native acceptance

Build externally, inspect previews/contact, then DayZDiag and a normal signed PBO/server with at most one
client. Spawn the class, request each pose 1–4 server-side before its command starts (or let the
fresh Variety contexts select it). Test alert/proximity/noise/damage wake, one complete rise,
death/hit/attack interruption, late join during idle and rise, deletion and cap release. Test
MaxPosed=0, cadence=0 and the disable marker. Re-enable and ensure capped fresh materialization
remains hidden from the connected client. Never use a teleport to fix a visible pose or blocked door.

Grep boot RPT:

- `[HC Variety] max_posed=24 bounds=0..64 opt_out=MaxPosed=0 runtime=PENDING`
- `[HC Variety] anim_poses=source_authored prone_sleep=admitted_unverified riser=admitted_unverified feed_kneel=admitted_unverified`; inspect the accompanying `runtime=PENDING` diagnostic
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
standing seam <=SEAM_METRES) are checked offline on our FK (2026-11-22 build: sleep pelvis 0.20 m,
lying sway <= 8 mm); the in-game look still requires the lead's client inspection, and no
animation fidelity or performance acceptance is claimed.
