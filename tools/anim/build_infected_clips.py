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


def two_bone(pose, upper, lower, end, target, pole):
    """Place ``end`` at ``target`` by swinging ``upper`` and ``lower``; the elbow/knee bends toward ``pole``."""
    a = pose.pos(upper)
    l1 = rig.vlen(rig.vsub(pose.pos(lower), a))
    l2 = rig.vlen(rig.vsub(pose.pos(end), pose.pos(lower)))
    to = rig.vsub(target, a)
    d = min(max(rig.vlen(to), abs(l1 - l2) + 1e-4), l1 + l2 - 1e-4)
    axis = rig.vnorm(to)
    along = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(l1 * l1 - along * along, 0.0))
    side = rig.vsub(pole, rig.vscale(axis, sum(p * q for p, q in zip(pole, axis))))
    mid = rig.vadd(rig.vadd(a, rig.vscale(axis, along)), rig.vscale(rig.vnorm(side), h))
    pose.aim(upper, lower, rig.vsub(mid, a))
    pose.aim(lower, end, rig.vsub(target, pose.pos(lower)))


HIP_SEAT_Y = 0.11   # hip joints above the ground when sitting on it
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
    return p


def seat_on_hips(p, hips):
    """Move the pelvis so the midpoint of the two hip joints lands on ``hips``."""
    mid = rig.vscale(rig.vadd(p.pos('LeftUpLeg'), p.pos('RightUpLeg')), 0.5)
    p.set_root_pos('Pelvis', rig.vadd(p.pos('Pelvis'), rig.vsub(hips, mid)))


def sit_wall_pose(stand, breath=0.0, sway=0.0):
    """Sitting on the ground, back against a wall or tree behind (-Z), knees up, head hanging.

    ``breath`` and ``sway`` in -1..1 animate the chest and the head without moving the root.
    """
    p = stand.copy()
    # Pelvis: tilted back and lowered onto the ground; the torso follows the pelvis.
    p.rotate_world('Pelvis', rig.qaxis(X, -18))
    seat_on_hips(p, (0.0, HIP_SEAT_Y, -0.04))
    # Slumped chest, breathing in the upper spine, hanging head with a slow sway.
    p.rotate_world('Spine2', rig.qaxis(X, 8 + 1.6 * breath))
    p.rotate_world('Spine3', rig.qaxis(X, 6 + 1.2 * breath))
    p.rotate_world('Neck', rig.qaxis(X, 12 + 2.0 * sway))
    p.rotate_world('Head', rig.qaxis(Y, 14 + 5.0 * sway))
    p.rotate_world('Head', rig.qaxis(X, 10 + 1.5 * breath))
    # Legs: knees up, feet flat on the ground in front.
    for side, sx in (('Left', -1.0), ('Right', 1.0)):
        hip = p.pos(side + 'UpLeg')
        foot = (hip[0] + sx * 0.12, 0.09, hip[2] + 0.52 + (0.04 if side == 'Right' else 0.0))
        two_bone(p, side + 'UpLeg', side + 'Leg', side + 'Foot', foot, (sx * 0.25, 1.0, 0.4))
        ankle = p.pos(side + 'Foot')
        p.aim(side + 'Foot', side + 'ToeBase', rig.vsub((ankle[0] + sx * 0.03, 0.02, ankle[2] + 0.15), ankle))
    # Left forearm rests over the left knee; the right arm hangs with the hand on the ground.
    knee = p.pos('LeftLeg')
    two_bone(p, 'LeftArm', 'LeftForeArm', 'LeftHand', (knee[0] + 0.06, knee[1] + 0.02, knee[2] + 0.10),
             (-1.0, -0.3, -0.4))
    hip = p.pos('RightUpLeg')
    two_bone(p, 'RightArm', 'RightForeArm', 'RightHand', (hip[0] + 0.24, 0.05 + 0.01 * breath, hip[2] + 0.02),
             (1.0, 0.0, -0.6))
    return p


def crouch_forward_pose(stand):
    """Get-up midpoint: feet drawn under, chest over the knees, hands pushing on the knees."""
    p = stand.copy()
    p.rotate_world('Pelvis', rig.qaxis(X, 38))
    p.set_root_pos('Pelvis', (0.0, 0.42, -0.12))
    p.rotate_world('Neck', rig.qaxis(X, -20))
    for side, sx in (('Left', -1.0), ('Right', 1.0)):
        hip = p.pos(side + 'UpLeg')
        foot = (hip[0] + sx * 0.05, 0.09, 0.08)
        two_bone(p, side + 'UpLeg', side + 'Leg', side + 'Foot', foot, (sx * 0.15, 0.3, 1.0))
        ankle = p.pos(side + 'Foot')
        p.aim(side + 'Foot', side + 'ToeBase', rig.vsub((ankle[0], 0.02, ankle[2] + 0.15), ankle))
        knee = p.pos(side + 'Leg')
        two_bone(p, side + 'Arm', side + 'ForeArm', side + 'Hand', (knee[0], knee[1] + 0.04, knee[2] + 0.02),
                 (sx, -0.2, -0.5))
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
    for f in range(n + 1):                      # last frame equals the first: closed loop
        ph = 2 * math.pi * f / n
        poses.append(sit_wall_pose(stand, breath=math.sin(2 * ph), sway=math.sin(ph)))
    return poses


def build_sit_wall_getup(stand, seconds=1.6):
    n = int(round(seconds * FPS))
    sit, mid = sit_wall_pose(stand), crouch_forward_pose(stand)
    poses = []
    for f in range(n + 1):
        t = f / n
        if t < 0.45:
            poses.append(blend(sit, mid, _smooth(t / 0.45)))
        else:
            poses.append(blend(mid, stand, _smooth((t - 0.45) / 0.55)))
    return poses



def prone_sleep_pose(stand, breath=0.0):
    """Side sleeper: hips low, bent legs, one cheek above the supporting forearm."""
    p = stand.copy()
    p.rotate_world('Pelvis', rig.qaxis((0, 0, 1), 87))
    seat_on_hips(p, (0.0, 0.19, 0.0))
    p.rotate_world('Spine3', rig.qaxis(X, 9 + 0.6 * breath))
    p.rotate_world('Neck', rig.qaxis(X, 14))
    for side, sx in (('Left', -1.0), ('Right', 1.0)):
        hip = p.pos(side + 'UpLeg')
        two_bone(p, side + 'UpLeg', side + 'Leg', side + 'Foot',
                 (hip[0] + 0.62, 0.09 + (sx + 1) * 0.07, 0.25), (0, 0.3, 1))
        shoulder = p.pos(side + 'Arm')
        two_bone(p, side + 'Arm', side + 'ForeArm', side + 'Hand',
                 (shoulder[0] - 0.14, 0.09 + (sx + 1) * 0.08, 0.21), (0, 0, -1))
    return p


def lie_rise_pose(stand, breath=0.0, face_down=False):
    """Loose supine or prone body. Variant is authored here, never sampled from a clip."""
    p = stand.copy()
    p.rotate_world('Pelvis', rig.qaxis(X, 89 if face_down else -89))
    seat_on_hips(p, (0.0, 0.17, 0.0))
    p.rotate_world('Head', rig.qaxis(Y, 18))
    p.rotate_world('Spine3', rig.qaxis(X, 0.4 * breath))
    direction = 1.0 if face_down else -1.0
    for side, sx in (('Left', -1.0), ('Right', 1.0)):
        two_bone(p, side + 'UpLeg', side + 'Leg', side + 'Foot',
                 (sx * 0.22, 0.10, -direction * 0.70), (sx, 0.4, 0))
        two_bone(p, side + 'Arm', side + 'ForeArm', side + 'Hand',
                 (sx * 0.43, 0.08, direction * 0.17), (sx, 0.2, -direction))
    return p


def kneel_pose(stand, dip=0.0, all_fours=False):
    """Knees down, toes behind; hands support the roll or work at ground level."""
    p = stand.copy()
    p.rotate_world('Pelvis', rig.qaxis(X, 65 if all_fours else 36 + 12 * dip))
    seat_on_hips(p, (0.0, 0.42, -0.10))
    p.rotate_world('Spine3', rig.qaxis(X, 12 + 8 * dip))
    p.rotate_world('Neck', rig.qaxis(X, 8))
    for side, sx in (('Left', -1.0), ('Right', 1.0)):
        hip = p.pos(side + 'UpLeg')
        two_bone(p, side + 'UpLeg', side + 'Leg', side + 'Foot',
                 (hip[0] + sx * 0.06, 0.10, -0.49), (sx * 0.15, -1, 0.8))
        two_bone(p, side + 'Arm', side + 'ForeArm', side + 'Hand',
                 (sx * (0.28 if all_fours else 0.16), 0.07, 0.40 + sx * 0.035 * dip),
                 (sx, 0.2, -0.3))
    return p


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
        'hc_feed_kneel_idle': to_anim(bones, authored_idle(stand, kneel_pose, 1.2)),
        'hc_feed_kneel_getup': to_anim(bones, authored_getup(
            [feed, crouch, stand], 2.0, (0, 0.45, 1))),
    }


def preview_json(parents, clip):
    frames = []
    for f in range(clip.frames):
        pose = rig.pose_from_clip(parents, clip, f)
        frames.append({n: [round(c, 4) for c in pose.pos(n)] for s in PREVIEW_SEGMENTS for n in s})
    return {'fps': clip.fps, 'segments': PREVIEW_SEGMENTS, 'frames': frames}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--addons', required=True, help='installed DayZ (or DayZServer) Addons folder, read only')
    ap.add_argument('--out', default='build/anims', help='output folder (outside git)')
    args = ap.parse_args(argv)
    parents, rest, bones = rig.load_skeleton(args.addons)
    os.makedirs(os.path.join(args.out, 'clips'), exist_ok=True)
    os.makedirs(os.path.join(args.out, 'preview'), exist_ok=True)
    for name, clip in build_all(parents, rest, bones).items():
        data = anm.write(clip)
        with open(os.path.join(args.out, 'clips', name + '.anm'), 'wb') as h:
            h.write(data)
        with open(os.path.join(args.out, 'preview', name + '.json'), 'w') as h:
            json.dump(preview_json(parents, clip), h)
        print('wrote %s.anm frames=%d bytes=%d' % (name, clip.frames, len(data)))
    # Our standing pose, preview only (no .anm): start/end of the preview sequences.
    stand = to_anim(bones, [stand_pose(rig.rest_pose(parents, rest, bones))])
    with open(os.path.join(args.out, 'preview', 'reference_stand.json'), 'w') as h:
        json.dump(preview_json(parents, stand), h)
    return 0


if __name__ == '__main__':
    sys.exit(main())
