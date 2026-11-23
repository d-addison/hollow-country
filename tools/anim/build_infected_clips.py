"""Author Hollow Country infected pose clips as .anm files. Standard library only. Our own code.

The poses are written here as code (aim directions, lean angles, a breathing cycle) and applied
to the rest pose of the mesh skeleton (z_hermit_m.xob bone offsets and rest rotations, read from
the installed game at build time). No vanilla animation frame is used, and the repository holds
no game data. The generated .anm files are build outputs and stay outside git
(default: build/anims/clips/). See docs/ANIMATION_PIPELINE.md.

    python3 tools/anim/build_infected_clips.py \
        --addons /mnt/d/SteamLibrary/steamapps/common/DayZServer/Addons --out build/anims

writes clips/<name>.anm and preview/<name>.json (world joint positions per frame, for
tools/anim/preview.py and tools/anim/blender/hc_preview.py).
"""
import argparse
import json
import math
import os
import sys

if __package__ in (None, ''):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from tools.anim import anm, rig  # noqa: E402

FPS = 30
X = (1.0, 0.0, 0.0)
Y = (0.0, 1.0, 0.0)
Z = (0.0, 0.0, 1.0)
# Joints written to the preview JSON (segments for the stick/mannequin renderers).
PREVIEW_SEGMENTS = (
    ('Pelvis', 'Spine'), ('Spine', 'Spine2'), ('Spine2', 'Spine3'), ('Spine3', 'Neck'), ('Neck', 'Head'),
    ('Spine3', 'LeftArm'), ('LeftArm', 'LeftForeArm'), ('LeftForeArm', 'LeftHand'), ('LeftHand', 'LeftHandMiddle2'),
    ('Spine3', 'RightArm'), ('RightArm', 'RightForeArm'), ('RightForeArm', 'RightHand'),
    ('RightHand', 'RightHandMiddle2'),
    ('Pelvis', 'LeftUpLeg'), ('LeftUpLeg', 'LeftLeg'), ('LeftLeg', 'LeftFoot'), ('LeftFoot', 'LeftToeBase'),
    ('Pelvis', 'RightUpLeg'), ('RightUpLeg', 'RightLeg'), ('RightLeg', 'RightFoot'), ('RightFoot', 'RightToeBase'),
)


def _smooth(t):
    return t * t * (3 - 2 * t)


# Elbows and knees: (upper, lower, end). Their mesh hinge axes come from the skeleton rest pose.
LIMBS = tuple((s + a, s + b, s + c) for s in ('Left', 'Right')
              for a, b, c in (('Arm', 'ForeArm', 'Hand'), ('UpLeg', 'Leg', 'Foot')))


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def hinge_axes(rest):
    """Mesh hinge axis of each elbow and knee in its upper bone's frame: the bend normal of the rest pose.

    The rest pose bends each elbow and knee a little (about 15 and 10 degrees) the anatomical way,
    so its bend normal is the joint's hinge. Two-bone IK keeps every bend on this axis.
    """
    out = {}
    for upper, lower, end in LIMBS:
        a, m, e = rest.pos(upper), rest.pos(lower), rest.pos(end)
        n = rig.vnorm(rig.vcross(rig.vsub(m, a), rig.vsub(e, m)))
        out[upper] = rig.qrot(rig.qinv(rest.world()[upper][1]), n)
    return out


SHIN_SCREW = 0.08   # inward shin rotation per degree of knee bend (about 8 degrees at a 100 degree bend)


def two_bone(pose, upper, lower, end, target, pole):
    """Place ``end`` at ``target`` by swinging ``upper`` and ``lower``; the elbow/knee points toward ``pole``.

    When the pose carries the mesh hinge axes (``stand_pose`` sets them), the upper bone is also
    twisted about its own segment so the joint flexes about its mesh hinge: never against the
    flexion direction (hyperextension) or sideways, and the shin turns inward a little with the
    knee bend. Joint positions are the same either way.
    """
    a = pose.pos(upper)
    l1 = rig.vlen(rig.vsub(pose.pos(lower), a))
    l2 = rig.vlen(rig.vsub(pose.pos(end), pose.pos(lower)))
    to = rig.vsub(target, a)
    d = min(max(rig.vlen(to), abs(l1 - l2) + 1e-4), l1 + l2 - 1e-4)
    axis = rig.vnorm(to)
    along = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(l1 * l1 - along * along, 0.0))
    side = rig.vnorm(rig.vsub(pole, rig.vscale(axis, _dot(pole, axis))))
    mid = rig.vadd(rig.vadd(a, rig.vscale(axis, along)), rig.vscale(side, h))
    pose.aim(upper, lower, rig.vsub(mid, a))
    hinge = pose.hinges.get(upper)
    if hinge is not None:
        u = rig.vnorm(rig.vsub(mid, a))
        want = rig.vnorm(rig.vcross(side, axis))          # the bend normal, defined even for a straight limb
        have = rig.qrot(pose.world()[upper][1], hinge)
        have = rig.vnorm(rig.vsub(have, rig.vscale(u, _dot(have, u))))
        want = rig.vnorm(rig.vsub(want, rig.vscale(u, _dot(want, u))))
        turn = math.degrees(math.atan2(_dot(u, rig.vcross(have, want)), _dot(have, want)))
        pose.rotate_world(upper, rig.qaxis(u, turn))
    pose.aim(lower, end, rig.vsub(target, pose.pos(lower)))
    if hinge is not None and lower.endswith('Leg'):
        # Knee screw-home: the shin turns inward as the knee bends (SHIN_SCREW degrees per degree).
        a, b, c = pose.pos(upper), pose.pos(lower), pose.pos(end)
        u, v = rig.vnorm(rig.vsub(b, a)), rig.vnorm(rig.vsub(c, b))
        bend = math.degrees(math.acos(max(-1.0, min(1.0, _dot(u, v)))))
        inward = 1.0 if lower.startswith('Right') else -1.0   # +angle about the shin turns the toes to -X
        pose.rotate_world(lower, rig.qaxis(v, inward * SHIN_SCREW * bend))


def body_turn(pose, stand, bone, axis, degrees):
    """Rotate ``bone`` about a body axis of its parent (stand axes: X right, Y up, Z forward).

    A lying body carries these axes with it, so ``body_turn(.., X, 10)`` nods forward whatever
    the pelvis roll; ``rotate_world`` about a world axis would twist the spine instead.
    """
    parent = pose.parents[bone]
    frame = rig.qmul(pose.world()[parent][1], rig.qinv(stand.world()[parent][1]))
    pose.rotate_world(bone, rig.qaxis(rig.qrot(frame, axis), degrees))


HIP_SEAT_Y = 0.025   # hip joints above the ground when sitting on it
SEAM_METRES = 0.12  # our standing pose stays this close to the vanilla idle (joint positions; tested)


def stand_pose(rest):
    """Our standing infected pose, built from the mesh rest (A-pose) pose by our own code.

    Arms hang with soft elbows and the hands in front of the thighs, the head leans forward,
    the left foot is half a step ahead. It is the get-up's last frame, so the hand-over to the
    vanilla idle is an approximate seam that the vanilla graph blends.
    """
    p = rest.copy()
    p.rotate_world('Spine3', rig.qaxis(X, 3))
    p.rotate_world('Neck', rig.qaxis(X, 10))
    p.rotate_world('Head', rig.qaxis(X, 6))
    for side, sx, foot_z in (('Left', -1.0, 0.0), ('Right', 1.0, -0.07)):
        hip = p.pos(side + 'UpLeg')
        two_bone(p, side + 'UpLeg', side + 'Leg', side + 'Foot', (hip[0] + sx * 0.03, 0.104, foot_z),
                 (0.0, 0.0, 1.0))
        ankle = p.pos(side + 'Foot')
        p.aim(side + 'Foot', side + 'ToeBase', rig.vsub((ankle[0] + sx * 0.01, 0.02, ankle[2] + 0.135), ankle))
        two_bone(p, side + 'Arm', side + 'ForeArm', side + 'Hand', (sx * 0.30, 0.94, 0.06),
                 (sx * 0.5, 0.0, -1.0))
    # Every pose authored from the stand keeps its elbows and knees on the mesh hinges; the stand
    # itself is unchanged (its seam with the vanilla idle is tested).
    p.hinges = hinge_axes(rest)
    return p


def seat_on_hips(p, hips):
    """Move the pelvis so the midpoint of the two hip joints lands on ``hips``."""
    mid = rig.vscale(rig.vadd(p.pos('LeftUpLeg'), p.pos('RightUpLeg')), 0.5)
    p.set_root_pos('Pelvis', rig.vadd(p.pos('Pelvis'), rig.vsub(hips, mid)))


def _seated_foot(p, side, target, pole=(0.0, 0.2, 1.0)):
    two_bone(p, side + 'UpLeg', side + 'Leg', side + 'Foot', target, pole)
    ankle = p.pos(side + 'Foot')
    p.aim(side + 'Foot', side + 'ToeBase',
          rig.vsub((ankle[0], ankle[1] - 0.084, ankle[2] + 0.135), ankle))


def _seated_hand(p, side, target):
    sx = -1.0 if side == 'Left' else 1.0
    two_bone(p, side + 'Arm', side + 'ForeArm', side + 'Hand', target, (sx, -0.2, -0.6))
    # Slack fingers lie along the floor rather than pointing through it.
    p.aim(side + 'Hand', side + 'HandMiddle2', (sx * 0.035, 0.008, 0.10))


def sit_wall_pose(stand, breath=0.0, sway=0.0):
    """Asymmetric wall slump, fixed hips/soles and a slack ground hand."""
    p = stand.copy()
    p.rotate_world('Pelvis', rig.qaxis(X, -26))
    seat_on_hips(p, (0.0, HIP_SEAT_Y, -0.04))
    body_turn(p, stand, 'Spine2', X, 8 + 0.7 * breath)
    body_turn(p, stand, 'Spine3', X, 5 + 0.5 * breath)
    body_turn(p, stand, 'Neck', X, 17 + 1.3 * sway)
    body_turn(p, stand, 'Head', Z, 24 + 3 * sway)
    body_turn(p, stand, 'Head', Y, -12 + 3 * sway)
    body_turn(p, stand, 'Head', X, 12 + 2 * breath)
    for side, sx in (('Left', -1.0), ('Right', 1.0)):
        hip = p.pos(side + 'UpLeg')
        _seated_foot(p, side, (hip[0] + sx * 0.10, 0.104,
                              0.68 if side == 'Left' else 0.43), (sx * 0.25, 1.0, 0.4))
    knee = p.pos('RightLeg')
    _seated_hand(p, 'Right', (knee[0], knee[1] + 0.035, knee[2] + 0.04))
    _seated_hand(p, 'Left', (-0.25, 0.025, -0.18))
    return p


def crouch_forward_pose(stand):
    """Loaded crouch: chest forward of the hips, palms over the knees."""
    p = stand.copy()
    p.rotate_world('Pelvis', rig.qaxis(X, 43))
    p.set_root_pos('Pelvis', (0.0, 0.48, -0.10))
    body_turn(p, stand, 'Neck', X, -15)
    for side, sx in (('Left', -1.0), ('Right', 1.0)):
        _seated_foot(p, side, (sx * 0.133, 0.104, 0.0 if side == 'Left' else -0.07))
        knee = p.pos(side + 'Leg')
        _seated_hand(p, side, (knee[0], knee[1] + 0.04, knee[2] + 0.02))
    return p


def blend(a, b, t):
    local = {}
    for n, (ta, qa) in a.local.items():
        tb, qb = b.local.get(n, (ta, qa))
        local[n] = (rig.vlerp(ta, tb, t), rig.qslerp(qa, qb, t))
    return rig.Pose(a.parents, local)


def to_anim(bones, poses):
    """Anim over the clip bone list (no scale keys); constant tracks collapse to one key."""
    out = anm.Anim(fps=FPS, frames=len(poses))
    for name in bones:
        b = anm.Bone(name)
        ts = [ps.local.get(name, ((0.0, 0.0, 0.0), rig.IDENTITY))[0] for ps in poses]
        qs = []
        for ps in poses:
            q = ps.local.get(name, ((0, 0, 0), rig.IDENTITY))[1]
            if qs and sum(x * y for x, y in zip(q, qs[-1])) < 0:
                q = tuple(-c for c in q)          # keep the quaternion hemisphere continuous
            qs.append(q)
        for track, vals in ((b.t, ts), (b.q, qs)):
            if all(max(abs(x - y) for x, y in zip(v, vals[0])) < 1e-6 for v in vals):
                track.frames, track.values = [0], [tuple(vals[0])]
            else:
                track.frames, track.values = list(range(len(vals))), [tuple(v) for v in vals]
        out.bones.append(b)
    return out


def build_sit_wall_idle(stand, seconds=4.0):
    n = int(round(seconds * FPS))
    poses = []
    for f in range(n + 1):
        ph = 2 * math.pi * (f % n) / n
        breath = 0.65 * math.sin(ph) + 0.25 * math.sin(2 * ph) + 0.10 * math.sin(3 * ph)
        sway = 0.7 * math.sin(ph) + 0.3 * math.sin(3 * ph)
        p = sit_wall_pose(stand, breath, sway)
        body_turn(p, stand, 'RightHand', X, 3 * math.sin(3 * ph))
        poses.append(p)
    return poses


def _seated_rise(stand, keyposes, knots, seconds):
    """Ease each load phase separately, then solve support targets in world space."""
    n = int(round(seconds * FPS))
    poses = []
    for f in range(n + 1):
        t = f / n
        i = next((j for j in range(len(knots) - 1) if t <= knots[j + 1]), len(knots) - 2)
        phase = (t - knots[i]) / (knots[i + 1] - knots[i])
        u = _smooth(phase)
        a, b = keyposes[i:i + 2]
        p = blend(a, b, u)
        p.hinges = stand.hinges
        head_phase = min(1.0, phase * 1.7) if i == 0 else max(0.0, (phase - 0.12) / 0.88)
        head_u = _smooth(head_phase)
        for bone in ('Neck', 'Head'):
            ta, qa = a.local[bone]
            tb, qb = b.local[bone]
            p.local[bone] = (rig.vlerp(ta, tb, head_u), rig.qslerp(qa, qb, head_u))
        p._world = None
        for side in ('Left', 'Right'):
            pole = rig.vlerp(rig.vsub(a.pos(side + 'Leg'), a.pos(side + 'UpLeg')),
                             rig.vsub(b.pos(side + 'Leg'), b.pos(side + 'UpLeg')), u)
            target = rig.vlerp(a.pos(side + 'Foot'), b.pos(side + 'Foot'), u)
            target = (target[0], 0.104, target[2])
            travel = rig.vlen(rig.vsub(a.pos(side + 'Foot'), b.pos(side + 'Foot')))
            if travel > 0.04:
                lift = 0.08 if side == 'Left' else 0.055
                target = rig.vadd(target, (0, lift * math.sqrt(max(0.0, math.sin(math.pi * u))), 0))
            _seated_foot(p, side, target, pole)
            _seated_hand(p, side, rig.vlerp(a.pos(side + 'Hand'), b.pos(side + 'Hand'), u))
        poses.append(p)
    poses[0], poses[-1] = keyposes[0].copy(), stand.copy()
    return poses


def build_sit_wall_getup(stand, seconds=1.6):
    sit = build_sit_wall_idle(stand)[0]
    alert = sit_wall_pose(stand)
    body_turn(alert, stand, 'Head', X, -20)
    body_turn(alert, stand, 'Head', Z, -12)
    _seated_hand(alert, 'Right', (0.25, 0.025, -0.18))
    brace = alert.copy()
    body_turn(brace, stand, 'Spine3', X, 2)
    for side, sx in (('Left', -1.0), ('Right', 1.0)):
        _seated_hand(brace, side, (sx * 0.25, 0.025, -0.18))
    load = crouch_forward_pose(stand)
    load.set_root_pos('Pelvis', (0.0, 0.44, -0.10))
    for side, sx in (('Left', -1.0), ('Right', 1.0)):
        _seated_foot(load, side, (sx * 0.133, 0.104, 0.0 if side == 'Left' else -0.07))
        _seated_hand(load, side, (sx * 0.32, 0.025, -0.015))
    draw = load.copy()
    _seated_foot(draw, 'Right', sit.pos('RightFoot'), (0.0, 0.2, 1.0))
    mid = crouch_forward_pose(stand)
    settle = blend(mid, stand, 0.90)
    settle.hinges = stand.hinges
    body_turn(settle, stand, 'Spine3', Z, -3)
    for side in ('Left', 'Right'):
        _seated_foot(settle, side, stand.pos(side + 'Foot'))
    return _seated_rise(stand, [sit, alert, brace, draw, load, mid, settle, stand],
                        (0, 0.10, 0.18, 0.38, 0.57, 0.72, 0.90, 1), seconds)



SLEEP_HIP_Y = 0.20   # hip-joint midpoint above the ground, lying on the side
LIE_HIP_Y = 0.17     # the same lying on the back or front


def _body_axes(roll, hips):
    """(point, direction) maps from body axes (stand X right, Y up, Z forward; offsets from the hip
    midpoint) to world axes, for a body turned by ``roll`` with its hip midpoint on ``hips``."""
    return (lambda x, y, z: rig.vadd(hips, rig.qrot(roll, (x, y, z))),
            lambda x, y, z: rig.qrot(roll, (x, y, z)))


def prone_sleep_pose(stand, breath=0.0):
    """Side sleeper on the left side: knees drawn up, head on the lower forearm, upper arm draped forward.

    Authored in body axes and rolled onto the left side by the pelvis; the spine, neck and head
    turn about their parent's body axes (``body_turn``), so the face looks the way the chest does.
    """
    p = stand.copy()
    roll = rig.qaxis(Z, 87)                  # body up -> world -X, body right -> up: the left side is down
    p.rotate_world('Pelvis', roll)
    seat_on_hips(p, (0.0, SLEEP_HIP_Y, 0.0))
    at, way = _body_axes(roll, (0.0, SLEEP_HIP_Y, 0.0))
    # Back curled a little forward, chest lifted off the ground side; the breath is in the chest.
    body_turn(p, stand, 'Spine2', X, 6 + 0.5 * breath)
    body_turn(p, stand, 'Spine3', X, 5 + 0.5 * breath)
    body_turn(p, stand, 'Spine3', Z, -4)
    # Head facing the same way as the chest, chin a little down, tilted onto the lower forearm.
    body_turn(p, stand, 'Neck', X, 6)
    body_turn(p, stand, 'Neck', Z, 8)
    body_turn(p, stand, 'Head', Z, 6)
    # Legs bent: hips flexed, knees forward; the upper knee rests just ahead of the lower one.
    two_bone(p, 'LeftUpLeg', 'LeftLeg', 'LeftFoot', at(-0.12, -0.49, 0.27), way(-0.1, 0.0, 1.0))
    two_bone(p, 'RightUpLeg', 'RightLeg', 'RightFoot', at(-0.04, -0.46, 0.22), way(-0.3, 0.0, 1.0))
    # Lower arm forward on the ground, elbow flexed, hand under the cheek; upper arm draped forward,
    # its hand on the ground in front of the chest.
    two_bone(p, 'LeftArm', 'LeftForeArm', 'LeftHand', at(-0.14, 0.72, 0.20), way(0.1, 0.0, 1.0))
    two_bone(p, 'RightArm', 'RightForeArm', 'RightHand', at(-0.12, 0.60, 0.38), way(0.5, -0.3, 0.6))
    return p


def lie_rise_pose(stand, breath=0.0, face_down=False):
    """Loose body on its back (or front): arms beside the body, knees a little bent, head turned.

    Authored in body axes like ``prone_sleep_pose``. Variant is authored here, never sampled from a clip.
    """
    p = stand.copy()
    roll = rig.qaxis(X, 89 if face_down else -89)    # body up -> world -Z (back) or +Z (front)
    p.rotate_world('Pelvis', roll)
    seat_on_hips(p, (0.0, LIE_HIP_Y, 0.0))
    at, way = _body_axes(roll, (0.0, LIE_HIP_Y, 0.0))
    body_turn(p, stand, 'Spine3', X, 0.4 * breath)
    body_turn(p, stand, 'Head', Y, 18)               # face turned to one side
    ground = -1.0 if not face_down else 1.0          # body Z toward the ground
    for side, sx in (('Left', -1.0), ('Right', 1.0)):
        if face_down:   # legs nearly straight along the ground, knees a little bent
            two_bone(p, side + 'UpLeg', side + 'Leg', side + 'Foot', at(sx * 0.17, -0.81, 0.06),
                     way(sx * 0.2, 0.0, 1.0))
        else:           # knees a little up and out
            two_bone(p, side + 'UpLeg', side + 'Leg', side + 'Foot', at(sx * 0.20, -0.74, ground * 0.06),
                     way(sx * 0.4, 0.0, 1.0))
        two_bone(p, side + 'Arm', side + 'ForeArm', side + 'Hand', at(sx * 0.33, 0.02, ground * 0.06),
                 way(sx * 0.6, 0.0, -1.0))
    return p


def kneel_pose(stand, dip=0.0, all_fours=False):
    """Knees planted behind the feeding hands, shoulders folded toward a ground body."""
    p = stand.copy()
    p.rotate_world('Pelvis', rig.qaxis(X, 65 if all_fours else 78 + 7 * dip))
    seat_on_hips(p, (0.0, 0.40, -0.13))
    body_turn(p, stand, 'Spine3', X, 10 + 5 * dip)
    body_turn(p, stand, 'Neck', X, 10 + 5 * dip)
    for side, sx in (('Left', -1.0), ('Right', 1.0)):
        hip = p.pos(side + 'UpLeg')
        thigh = rig.vlen(rig.vsub(p.pos(side + 'Leg'), hip))
        shin = rig.vlen(rig.vsub(p.pos(side + 'Foot'), p.pos(side + 'Leg')))
        knee_z = hip[2] + math.sqrt(max(0.001, thigh * thigh - (hip[1] - 0.025) ** 2))
        foot_z = knee_z - math.sqrt(shin * shin - (0.104 - 0.025) ** 2)
        _seated_foot(p, side, (hip[0], 0.104, foot_z), (0, -1, 1))
        _seated_hand(p, side, (sx * (0.28 if all_fours else 0.18), 0.025, 0.44))
    return p


def _seated_feed_idle(stand, seconds=4.0):
    n = int(round(seconds * FPS))
    poses = []
    for f in range(n + 1):
        ph = 2 * math.pi * (f % n) / n
        dip = 0.55 * math.sin(ph) + 0.30 * math.sin(2 * ph) + 0.15 * math.sin(3 * ph)
        p = kneel_pose(stand, dip)
        body_turn(p, stand, 'Spine3', Y, 3 * math.sin(2 * ph))
        body_turn(p, stand, 'Head', Y, 5 * math.sin(2 * ph))
        lag = math.sin(ph - 0.18) + math.sin(0.18)
        body_turn(p, stand, 'Head', X, 5 * (lag - math.sin(ph)))
        for side, sx in (('Left', -1.0), ('Right', 1.0)):
            _seated_hand(p, side, (sx * 0.18, 0.025, 0.44))
            body_turn(p, stand, side + 'Hand', X, sx * 2 * math.sin(3 * ph))
        poses.append(p)
    return poses


def _seated_feed_getup(stand, seconds=2.0):
    feed = _seated_feed_idle(stand)[0]
    alert = kneel_pose(stand, -0.7)
    body_turn(alert, stand, 'Head', X, -18)
    half = kneel_pose(stand, -3.0)
    _seated_foot(half, 'Left', (-0.133, 0.104, 0.0), (0, 0.3, 1))
    _seated_hand(half, 'Left', (-0.20, 0.32, 0.27))
    mid = crouch_forward_pose(stand)
    return _seated_rise(stand, [feed, alert, half, mid, stand],
                        (0, 0.18, 0.42, 0.68, 1), seconds)


def authored_idle(stand, pose_fn, seconds):
    count = int(round(seconds * FPS))
    return [pose_fn(stand, math.sin(2 * math.pi * f / count)) for f in range(count + 1)]


def authored_getup(keyposes, seconds, knots):
    """Smooth authored stages, including the exact idle seam and our standing endpoint."""
    count = int(round(seconds * FPS))
    poses = []
    for frame in range(count + 1):
        t = frame / count
        segment = next((i for i in range(len(knots) - 1) if t <= knots[i + 1]), len(knots) - 2)
        amount = (t - knots[segment]) / (knots[segment + 1] - knots[segment])
        poses.append(blend(keyposes[segment], keyposes[segment + 1], _smooth(amount)))
    return poses


# Anatomy limits, checked on every frame of every clip (``anatomy_failures``). Angles in degrees.
# Our stand is the zero for the head; the mesh rest pose is the zero for hinges and twists.
# Ranges are anatomical; the installed vanilla infected clips (read only in diagnosis) sit
# inside them except for crawl attacks and a few door attacks.
HEAD_LIMITS = (('yaw', 80.0), ('pitch', 60.0), ('roll', 45.0))   # head relative to Spine3
HINGE_LIMITS = (('elbow', 60.0), ('knee', 30.0))   # bend axis off the mesh hinge (> 90 = bent backwards)
BENT = 20.0                                        # hinge axes are judged once the joint bends this far
UPPER_ARM_BEHIND = -0.5    # upper arm direction in the chest frame: forward component (sin) at least this
TWIST_LIMITS = (('Arm', 80.0), ('ForeArm', 35.0), ('UpLeg', 45.0), ('Leg', 35.0))   # about the bone axis


def _anat(pose, stand, bone):
    """The bone's body frame: identity in our stand (X right, Y up, Z forward)."""
    return rig.qmul(pose.world()[bone][1], rig.qinv(stand.world()[bone][1]))


def _yaw_pitch_roll(q):
    """Yaw about Y, then pitch about X (+ = nod down), then roll about Z (+ = top toward the left)."""
    f, r = rig.qrot(q, Z), rig.qrot(q, X)
    yaw = math.degrees(math.atan2(f[0], f[2]))
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, -f[1]))))
    r = rig.qrot(rig.qinv(rig.qmul(rig.qaxis(Y, yaw), rig.qaxis(X, pitch))), r)
    return yaw, pitch, math.degrees(math.atan2(r[1], r[0]))


def anatomy(pose, stand, rest):
    """Joint-frame measures of one pose (see the limits above). Positions alone do not show these."""
    m = {}
    chest = _anat(pose, stand, 'Spine3')
    m['head_yaw'], m['head_pitch'], m['head_roll'] = _yaw_pitch_roll(
        rig.qmul(rig.qinv(chest), _anat(pose, stand, 'Head')))
    for upper, lower, end in LIMBS:
        side = 'Left' if upper.startswith('Left') else 'Right'
        joint = 'elbow' if upper.endswith('Arm') else 'knee'

        def bend_normal(p):
            a, b, c = p.pos(upper), p.pos(lower), p.pos(end)
            u, v = rig.vnorm(rig.vsub(b, a)), rig.vnorm(rig.vsub(c, b))
            bend = math.degrees(math.acos(max(-1.0, min(1.0, _dot(u, v)))))
            return bend, rig.qrot(rig.qinv(p.world()[upper][1]), rig.vnorm(rig.vcross(u, v)))
        bend, n = bend_normal(pose)
        _, n_rest = bend_normal(rest)
        m['%s_%s_bend' % (side, joint)] = bend
        m['%s_%s_axis' % (side, joint)] = math.degrees(math.acos(max(-1.0, min(1.0, _dot(n, n_rest)))))
    for side in ('Left', 'Right'):
        arm = rig.vnorm(rig.vsub(pose.pos(side + 'ForeArm'), pose.pos(side + 'Arm')))
        m[side + '_upper_arm_forward'] = rig.qrot(rig.qinv(chest), arm)[2]
        for bone, _ in TWIST_LIMITS:
            d = rig.qmul(rig.qinv(rest.local[side + bone][1]), pose.local[side + bone][1])
            if d[3] < 0:
                d = tuple(-c for c in d)
            m['%s_%s_twist' % (side, bone)] = math.degrees(2 * math.atan2(d[0], d[3]))
    return m


def anatomy_failures(m):
    """Readable failures of ``anatomy`` measures; empty when the pose is anatomically valid."""
    out = []
    for key, limit in HEAD_LIMITS:
        if abs(m['head_' + key]) > limit:
            out.append('head %s %.0f > %.0f' % (key, m['head_' + key], limit))
    for side in ('Left', 'Right'):
        for joint, limit in HINGE_LIMITS:
            axis = m['%s_%s_axis' % (side, joint)]
            if m['%s_%s_bend' % (side, joint)] >= BENT and axis > limit:
                what = 'bent backwards' if axis > 90 else 'bent sideways'
                out.append('%s %s %s (axis %.0f > %.0f)' % (side, joint, what, axis, limit))
        if m[side + '_upper_arm_forward'] < UPPER_ARM_BEHIND:
            out.append('%s upper arm behind the torso (%.2f < %.2f)' % (
                side, m[side + '_upper_arm_forward'], UPPER_ARM_BEHIND))
        for bone, limit in TWIST_LIMITS:
            tw = m['%s_%s_twist' % (side, bone)]
            if abs(tw) > limit:
                out.append('%s%s twist %.0f > %.0f' % (side, bone, tw, limit))
    return out


def check_anatomy(parents, clips, stand, rest):
    """{clip: (worst measures, [(frame, failure)])} over every frame of the clips as written."""
    report = {}
    for name, clip in clips.items():
        worst, failures = {}, []
        for f in range(clip.frames):
            m = anatomy(rig.pose_from_clip(parents, clip, f), stand, rest)
            for k, v in m.items():
                if k.endswith('_axis') and m[k.replace('_axis', '_bend')] < BENT:
                    continue
                if k not in worst or (v < worst[k] if k.endswith('_forward') else abs(v) > abs(worst[k])):
                    worst[k] = v
            failures.extend((f, text) for text in anatomy_failures(m))
        report[name] = (worst, failures)
    return report


def build_all(parents, rest, bones):
    """Our clips from the mesh skeleton (``rig.load_skeleton``); no vanilla clip is read."""
    stand = stand_pose(rig.rest_pose(parents, rest, bones))
    crouch = crouch_forward_pose(stand)
    fours = kneel_pose(stand, all_fours=True)
    sleep = prone_sleep_pose(stand)
    lying = lie_rise_pose(stand)
    feed = kneel_pose(stand)
    return {
        'hc_sit_wall_idle': to_anim(bones, build_sit_wall_idle(stand)),
        'hc_sit_wall_getup': to_anim(bones, build_sit_wall_getup(stand)),
        'hc_prone_sleep_idle': to_anim(bones, authored_idle(stand, prone_sleep_pose, 4.0)),
        'hc_prone_sleep_getup': to_anim(bones, authored_getup(
            [sleep, fours, crouch, stand], 2.6, (0, 0.35, 0.65, 1))),
        'hc_lie_rise_idle': to_anim(bones, authored_idle(stand, lie_rise_pose, 4.0)),
        'hc_lie_rise_getup': to_anim(bones, authored_getup(
            [lying, sit_wall_pose(stand), crouch, stand], 2.8, (0, 0.40, 0.72, 1))),
        # Alternate face-down pair is authored and packaged for inspection; default pose 3 is supine.
        'hc_lie_face_down_idle': to_anim(bones, authored_idle(
            stand, lambda p, b: lie_rise_pose(p, b, face_down=True), 4.0)),
        'hc_lie_face_down_getup': to_anim(bones, authored_getup(
            [lie_rise_pose(stand, face_down=True), fours, crouch, stand], 2.8, (0, 0.38, 0.72, 1))),
        'hc_feed_kneel_idle': to_anim(bones, _seated_feed_idle(stand)),
        'hc_feed_kneel_getup': to_anim(bones, _seated_feed_getup(stand)),
    }


# Head pseudo-points for the previews, in the stand's head frame: the Head bone has no child, so
# without these a preview cannot show which way the head faces.
PREVIEW_HEAD_POINTS = (('Skull', (0.0, 0.09, 0.02)), ('Face', (0.0, 0.05, 0.11)))


def preview_json(parents, clip, stand=None):
    frames = []
    for f in range(clip.frames):
        pose = rig.pose_from_clip(parents, clip, f)
        frame = {n: [round(c, 4) for c in pose.pos(n)] for s in PREVIEW_SEGMENTS for n in s}
        if stand is not None:
            head = _anat(pose, stand, 'Head')
            for name, offset in PREVIEW_HEAD_POINTS:
                frame[name] = [round(c, 4) for c in rig.vadd(pose.pos('Head'), rig.qrot(head, offset))]
        frames.append(frame)
    return {'fps': clip.fps, 'segments': PREVIEW_SEGMENTS, 'frames': frames}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--addons', required=True, help='installed DayZ (or DayZServer) Addons folder, read only')
    ap.add_argument('--out', default='build/anims', help='output folder (outside git)')
    args = ap.parse_args(argv)
    parents, rest, bones = rig.load_skeleton(args.addons)
    built = build_all(parents, rest, bones)
    # Anatomy gate on the clips as written (quantized): no backwards or twisted joint ships.
    restp = rig.rest_pose(parents, rest, bones)
    report = check_anatomy(parents, {n: anm.read(anm.write(c)) for n, c in built.items()},
                           stand_pose(restp), restp)
    bad = {n: fails for n, (_, fails) in report.items() if fails}
    if bad:
        for name, fails in bad.items():
            print('ANATOMY FAIL %s: %d frames, e.g. frame %d: %s' % (name, len(fails), fails[0][0], fails[0][1]))
        return 1
    os.makedirs(os.path.join(args.out, 'clips'), exist_ok=True)
    os.makedirs(os.path.join(args.out, 'preview'), exist_ok=True)
    for name, clip in built.items():
        data = anm.write(clip)
        with open(os.path.join(args.out, 'clips', name + '.anm'), 'wb') as h:
            h.write(data)
        with open(os.path.join(args.out, 'preview', name + '.json'), 'w') as h:
            json.dump(preview_json(parents, clip, stand_pose(restp)), h)
        print('wrote %s.anm frames=%d bytes=%d' % (name, clip.frames, len(data)))
    # Our standing pose, preview only (no .anm): start/end of the preview sequences.
    stand = to_anim(bones, [stand_pose(restp)])
    with open(os.path.join(args.out, 'preview', 'reference_stand.json'), 'w') as h:
        json.dump(preview_json(parents, stand, stand_pose(restp)), h)
    return 0


if __name__ == '__main__':
    sys.exit(main())
