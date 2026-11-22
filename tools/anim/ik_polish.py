"""Offline foot-lock and leg-IK cleanup for retargeted clips (stdlib only, bounded, deterministic).

Input is our intermediate format, a list of ``rig.Pose`` (one per frame, as retarget.py builds them),
a retargeted ``anm.Anim`` (with the installed skeleton) or a BVH. For each leg chain
(UpLeg/Leg/Foot[/ToeBase]) the pass

1. finds contact intervals per foot (low and slow ankle, at least ``min_contact_frames`` long) or takes
   caller supplied ones;
2. pins the ankle to the interval's mean position with a two-bone analytic IK (swing-only aim, so knee
   twist and pole side follow the source motion), easing in and out over ``blend_frames`` frames outside
   the interval, and holds the foot heading (yaw about the vertical, from the toe direction) while planted;
3. where a pinned foot is out of reach, shifts the pelvis toward it (smoothed, capped at
   ``max_pelvis_shift``); anything still out of reach is counted, never hidden;
4. limits the angular speed of the touched leg joints to the larger of ``max_joint_dps`` and the speed the
   source motion already had there, so the pass never adds a pop.

Foot pitch and roll are left as authored (heel-to-toe roll is real motion); only position and heading are
locked. This is an offline authoring aid: it asserts nothing about engine behaviour and writes no root
motion (the pelvis shift only moves the authored pelvis). Same input and config give the same output.

    python3 -B -m tools.anim.ik_polish --bvh in.bvh --out out.bvh [--report]
    python3 -B -m tools.anim.ik_polish --anm in.anm --addons <DayZ>/Addons --out out.anm [--report]
"""
import argparse
from bisect import bisect_right
from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import re
import struct
import sys

from tools.anim import anm, rig

MAX_FRAMES = 4000                 # a polish pass is O(frames x chain); 4000 frames is 133 s at 30 fps
MAX_BYTES = 16 << 20
CHAINS = {'Left': ('LeftUpLeg', 'LeftLeg', 'LeftFoot', 'LeftToeBase'),
          'Right': ('RightUpLeg', 'RightLeg', 'RightFoot', 'RightToeBase')}
UP = (0.0, 1.0, 0.0)


@dataclass(frozen=True)
class Config:
    contact_height: float = 0.04      # metres above the lowest ankle of the clip
    contact_speed: float = 0.15       # metres per second
    min_contact_frames: int = 3
    blend_frames: int = 3
    max_pelvis_shift: float = 0.05    # metres, per frame
    max_joint_dps: float = 720.0      # degrees per second for touched leg joints
    reach: float = 0.9999             # fraction of the straight leg length a pinned ankle may ask for


@dataclass
class Report:
    frames: int = 0
    feet: dict = field(default_factory=dict)      # side -> {intervals, slide_before, slide_after} (metres)
    unreachable_frames: int = 0
    pelvis_shift_max: float = 0.0
    velocity_limited: int = 0

    def as_dict(self):
        return dict(frames=self.frames, unreachable_frames=self.unreachable_frames,
                    pelvis_shift_max=round(self.pelvis_shift_max, 6),
                    velocity_limited=self.velocity_limited,
                    feet={side: dict(intervals=[list(i) for i in row['intervals']],
                                     slide_before=round(row['slide_before'], 6),
                                     slide_after=round(row['slide_after'], 6))
                          for side, row in sorted(self.feet.items())})


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _angle(a, b):
    """Rotation angle (radians) between two unit quaternions, shortest way."""
    return 2 * math.acos(min(1.0, abs(_dot(a, b))))


def _horizontal(v):
    return (v[0], 0.0, v[2])


def _smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def detect_contacts(heights_speeds, floor, config):
    """Contact intervals (first, last inclusive) from per-frame (height, speed) pairs."""
    flags = [h <= floor + config.contact_height and s <= config.contact_speed for h, s in heights_speeds]
    intervals, start = [], None
    for i, flag in enumerate(flags + [False]):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            if i - start >= config.min_contact_frames:
                intervals.append((start, i - 1))
            start = None
    return intervals


def _validate(poses, dt, chains, config):
    if not poses or len(poses) > MAX_FRAMES:
        raise ValueError('ik.frame_limit')
    if not isinstance(dt, (int, float)) or not 1e-4 <= dt <= 1:
        raise ValueError('ik.frame_time')
    if not (config.min_contact_frames >= 1 and config.blend_frames >= 0 and config.max_joint_dps > 0
            and 0.5 < config.reach <= 1.0 and config.max_pelvis_shift >= 0):
        raise ValueError('ik.config')
    for side, names in chains.items():
        if len(names) < 3:
            raise ValueError('ik.chain')
        for name in names[:3]:
            if any(name not in pose.local for pose in poses[:1]):
                raise ValueError('ik.chain_bone:' + name)


def _ankles(poses, chains, unit):
    return {side: [rig.vscale(p.pos(names[2]), unit) for p in poses] for side, names in chains.items()}


def _intervals(chains, ankles, dt, contacts, config):
    floor = min(v[1] for rows in ankles.values() for v in rows)
    result = {}
    for side in sorted(chains):
        if contacts is not None:
            rows = []
            for first, last in contacts.get(side, ()):
                if not (isinstance(first, int) and isinstance(last, int) and 0 <= first <= last < len(ankles[side])):
                    raise ValueError('ik.contacts')
                rows.append((first, last))
            result[side] = sorted(rows)
            continue
        pos, n = ankles[side], len(ankles[side])
        sample = []
        for i in range(n):
            lo, hi = max(0, i - 1), min(n - 1, i + 1)
            speed = rig.vlen(rig.vsub(pos[hi], pos[lo])) / ((hi - lo) * dt) if hi > lo else 0.0
            sample.append((pos[i][1], speed))
        result[side] = detect_contacts(sample, floor, config)
    return result


def measure_slide(ankles, intervals):
    """Largest horizontal distance of the ankle from its interval's mean position (metres)."""
    worst = 0.0
    for first, last in intervals:
        rows = ankles[first:last + 1]
        mean = tuple(sum(v[a] for v in rows) / len(rows) for a in range(3))
        for v in rows:
            worst = max(worst, rig.vlen(_horizontal(rig.vsub(v, mean))))
    return worst


def _weights(n, intervals, blend):
    """Per-frame (weight, interval index) with smoothstep ramps outside each interval."""
    out = [(0.0, -1)] * n
    for index, (first, last) in enumerate(intervals):
        for i in range(first, last + 1):
            out[i] = (1.0, index)
        for k in range(1, blend + 1):
            w = _smooth(1 - k / (blend + 1))
            for i in (first - k, last + k):
                if 0 <= i < n and w > out[i][0]:
                    out[i] = (w, index)
    return out


def _solve_leg(pose, names, target, reach):
    """Two-bone aim so the ankle goes to ``target``; True when it was reachable."""
    hip, knee, ankle = names[:3]
    h, k, a = pose.pos(hip), pose.pos(knee), pose.pos(ankle)
    l1, l2 = rig.vlen(rig.vsub(k, h)), rig.vlen(rig.vsub(a, k))
    to = rig.vsub(target, h)
    d = rig.vlen(to)
    if d < 1e-9 or l1 < 1e-9 or l2 < 1e-9:
        return False
    u = rig.vscale(to, 1 / d)
    dmax, dmin = (l1 + l2) * reach, abs(l1 - l2) * 1.0001 + 1e-9
    dc = min(max(d, dmin), dmax)
    along = (l1 * l1 - l2 * l2 + dc * dc) / (2 * dc)
    height = math.sqrt(max(0.0, l1 * l1 - along * along))
    hint = rig.vsub(k, h)
    pole = rig.vsub(hint, rig.vscale(u, _dot(hint, u)))
    if rig.vlen(pole) < 1e-6 * l1:                      # straight leg: bend forward (+Z, engine forward)
        pole = rig.vsub((0.0, 0.0, 1.0), rig.vscale(u, u[2]))
        if rig.vlen(pole) < 1e-6:
            pole = rig.vsub((1.0, 0.0, 0.0), rig.vscale(u, u[0]))
    pole = rig.vnorm(pole)
    knee_to = rig.vadd(rig.vadd(h, rig.vscale(u, along)), rig.vscale(pole, height))
    pose.aim(hip, knee, rig.vsub(knee_to, h))
    pose.aim(knee, ankle, rig.vsub(rig.vadd(h, rig.vscale(u, dc)), pose.pos(knee)))
    return d <= dmax + 1e-9


def _yaw(v):
    return math.atan2(v[0], v[2])


def _wrap(angle):
    return (angle + math.pi) % (2 * math.pi) - math.pi


def polish_poses(poses, dt, *, chains=None, contacts=None, config=None, unit=1.0, root='Pelvis'):
    """Polish ``poses`` (list of rig.Pose) in place; returns a Report.

    ``unit`` is metres per pose unit (0.01 for a centimetre BVH); thresholds are in metres.
    ``contacts`` is {side: [(first, last), ...]} frame indices, inclusive; default: detected.
    """
    config = config or Config()
    chains = dict(CHAINS if chains is None else chains)
    _validate(poses, dt, chains, config)
    if root not in poses[0].local:
        raise ValueError('ik.chain_bone:' + root)
    n = len(poses)
    report = Report(frames=n)
    ankles = _ankles(poses, chains, unit)
    intervals = _intervals(chains, ankles, dt, contacts, config)
    inv = 1.0 / unit
    # Anchors come from the source motion: mean ankle position and mean toe heading per interval.
    plans = {}
    for side, names in chains.items():
        rows = []
        for first, last in intervals[side]:
            span = ankles[side][first:last + 1]
            mean = tuple(sum(v[a] for v in span) / len(span) for a in range(3))
            heading = None
            if len(names) > 3 and names[3] in poses[0].local:
                sx = sz = 0.0
                for i in range(first, last + 1):
                    d = rig.vsub(poses[i].pos(names[3]), poses[i].pos(names[2]))
                    h = _horizontal(d)
                    if rig.vlen(h) > 1e-9:
                        h = rig.vnorm(h)
                        sx, sz = sx + h[0], sz + h[2]
                if math.hypot(sx, sz) > 1e-9:
                    heading = math.atan2(sx, sz)
            rows.append((mean, heading))
        plans[side] = (rows, _weights(n, intervals[side], config.blend_frames))
        report.feet[side] = dict(intervals=intervals[side], slide_before=measure_slide(ankles[side], intervals[side]),
                                 slide_after=0.0)
    originals = {b: [p.local[b][1] for p in poses] for names in chains.values() for b in names[:3]}

    # Pass 1: pelvis shift that brings out-of-reach pinned ankles back into range.
    shifts = [(0.0, 0.0, 0.0)] * n
    cap = config.max_pelvis_shift
    for i, pose in enumerate(poses):
        total = (0.0, 0.0, 0.0)
        for side, names in chains.items():
            rows, weights = plans[side]
            w, index = weights[i]
            if w <= 0.0:
                continue
            target = rig.vlerp(ankles[side][i], rows[index][0], w)
            h = rig.vscale(pose.pos(names[0]), unit)
            l1 = rig.vlen(rig.vsub(pose.pos(names[1]), pose.pos(names[0]))) * unit
            l2 = rig.vlen(rig.vsub(pose.pos(names[2]), pose.pos(names[1]))) * unit
            to = rig.vsub(target, h)
            excess = rig.vlen(to) - (l1 + l2) * config.reach
            if excess > 0:
                total = rig.vadd(total, rig.vscale(rig.vnorm(to), excess))
        shifts[i] = total
    window = config.blend_frames
    smoothed = []
    for i in range(n):
        lo, hi = max(0, i - window), min(n, i + window + 1)
        mean = tuple(sum(shifts[j][a] for j in range(lo, hi)) / (hi - lo) for a in range(3))
        # Smoothing may only lower a shift; never exceed the cap.
        length = rig.vlen(mean)
        if length > cap > 0:
            mean = rig.vscale(mean, cap / length)
        elif cap == 0:
            mean = (0.0, 0.0, 0.0)
        smoothed.append(mean)
    for i, pose in enumerate(poses):
        shift = smoothed[i]
        if rig.vlen(shift) > 1e-12:
            pose.set_root_pos(root, rig.vadd(pose.pos(root), rig.vscale(shift, inv)))
            report.pelvis_shift_max = max(report.pelvis_shift_max, rig.vlen(shift))

    # Pass 2: pin ankles and hold heading.
    unreachable = set()
    for i, pose in enumerate(poses):
        for side, names in chains.items():
            rows, weights = plans[side]
            w, index = weights[i]
            if w <= 0.0:
                continue
            mean, heading = rows[index]
            current = rig.vscale(pose.pos(names[2]), unit)
            target = rig.vscale(rig.vlerp(current, mean, w), inv)
            if not _solve_leg(pose, names, target, config.reach):
                unreachable.add((i, side))
            if heading is not None:
                d = _horizontal(rig.vsub(pose.pos(names[3]), pose.pos(names[2])))
                if rig.vlen(d) > 1e-9:
                    turn = _wrap(heading - _yaw(d)) * w
                    pose.rotate_world(names[2], rig.qaxis(UP, math.degrees(turn)))
    report.unreachable_frames = len({i for i, _ in unreachable})

    # Pass 3: never add angular speed above the limit (or above what the source already had).
    limit = math.radians(config.max_joint_dps) * dt
    for names in chains.values():
        for bone in names[:3]:
            before = originals[bone]
            previous = poses[0].local[bone][1]
            for i in range(1, n):
                t, q = poses[i].local[bone]
                allowed = max(limit, _angle(before[i - 1], before[i]))
                step = _angle(previous, q)
                if step > allowed + 1e-12:
                    q = rig.qslerp(previous, q, allowed / step)
                    poses[i].local[bone] = (t, rig.qnorm(q))
                    poses[i]._world = None
                    report.velocity_limited += 1
                previous = poses[i].local[bone][1]
    for side, names in chains.items():
        after = [rig.vscale(p.pos(names[2]), unit) for p in poses]
        report.feet[side]['slide_after'] = measure_slide(after, intervals[side])
    return report


# ---------------------------------------------------------------- retargeted clips (SET6)

def _dense(track, count, default):
    """Per-frame values of a track (linear between keys, held outside them)."""
    if not track.values:
        return [default] * count
    frames, values = track.frames, track.values
    out = []
    for f in range(count):
        at = bisect_right(frames, f) - 1
        if at < 0:
            out.append(tuple(values[0]))
        elif at >= len(frames) - 1 or frames[at] == f:
            out.append(tuple(values[at]))
        else:
            u = (f - frames[at]) / (frames[at + 1] - frames[at])
            a, b = values[at], values[at + 1]
            if track.comps == 4:
                out.append(rig.qslerp(tuple(a), tuple(b), u))
            else:
                out.append(rig.vlerp(tuple(a), tuple(b), u))
    return out


def polish_clip(clip, parents, *, chains=None, contacts=None, config=None, root='Pelvis'):
    """Polish a retargeted anm.Anim in place on the installed skeleton ``parents``; returns a Report.

    Only the leg bones' rotations and the pelvis translation are rewritten (dense keys); every other
    bone keeps its keys exactly.
    """
    chains = dict(CHAINS if chains is None else chains)
    count = clip.frames
    if count < 1 or count > MAX_FRAMES or clip.fps < 1:
        raise ValueError('ik.frame_limit')
    dense = {}
    for b in clip.bones:
        dense[b.name] = (_dense(b.t, count, (0.0, 0.0, 0.0)), _dense(b.q, count, rig.IDENTITY))
    touched = {root} | {name for names in chains.values() for name in names[:3]}
    for name in touched:
        if name not in dense:
            raise ValueError('ik.chain_bone:' + name)
    poses = [rig.Pose(parents, {n: (dense[n][0][f], rig.qnorm(dense[n][1][f])) for n in dense})
             for f in range(count)]
    report = polish_poses(poses, 1.0 / clip.fps, chains=chains, contacts=contacts, config=config, root=root)
    for name in sorted(touched):
        bone = clip.bone(name)
        ts, qs, previous = [], [], None
        for pose in poses:
            t, q = pose.local[name]
            if previous is not None and _dot(previous, q) < 0:
                q = tuple(-c for c in q)
            previous = q
            ts.append(tuple(t))
            qs.append(tuple(q))
        bone.t = anm.Track(3, list(range(count)), ts)
        bone.q = anm.Track(4, list(range(count)), qs)
        bone.ranges = None
        bone.flags = 0
    return report


# ---------------------------------------------------------------- BVH

def _matrix(q):
    x, y, z, w = q
    return ((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
            (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
            (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)))


def euler_degrees(q, order):
    """Intrinsic Tait-Bryan angles (degrees) for an axis ``order`` such as 'ZXY' (R = Ra Rb Rc)."""
    i, j, k = ('XYZ'.index(c) for c in order)
    if len({i, j, k}) != 3:
        raise ValueError('ik.bvh_channels')
    eps = 1 if (j - i) % 3 == 1 else -1
    r = _matrix(rig.qnorm(q))
    sin_b = max(-1.0, min(1.0, eps * r[i][k]))
    if math.sqrt(max(0.0, 1 - sin_b * sin_b)) < 1e-4:
        raise ValueError('ik.gimbal')
    beta = math.asin(sin_b)
    alpha = math.atan2(-eps * r[j][k], r[k][k])
    gamma = math.atan2(-eps * r[i][j], r[i][i])
    return tuple(math.degrees(v) for v in (alpha, beta, gamma))


def bvh_chains(source):
    """Leg chains in the BVH's own joint names, from retarget's alias maps."""
    from tools.anim import retarget
    names = {j.name for j in source.joints}
    mapping = dict(retarget.DEFAULT_MAP)
    if {'LeftHip', 'LeftKnee', 'LeftAnkle'} <= names:
        mapping.update(retarget.STYLE_MAP)
    reverse = {}
    for joint in source.joints:
        target = mapping.get(joint.name)
        if target is not None and target not in reverse:
            reverse[target] = joint.name
    chains = {}
    for side, bones in CHAINS.items():
        if not all(b in reverse for b in bones[:3]):
            raise ValueError('ik.bvh_chain:' + side)
        chains[side] = tuple(reverse[b] for b in bones if b in reverse)
    return chains, reverse.get('Pelvis', source.joints[0].name)


def polish_bvh(source, *, config=None, contacts=None, unit=None):
    """(new frame tuples, Report) for a parsed BVH; the hierarchy is unchanged."""
    chains, root = bvh_chains(source)
    if root != source.joints[0].name:
        raise ValueError('ik.bvh_root')
    by_name = {j.name: j for j in source.joints}
    if unit is None:
        pose = source.pose()
        length = sum(rig.vlen(rig.vsub(pose.pos(b), pose.pos(a))) for a, b in zip(chains['Left'][:3], chains['Left'][1:3]))
        unit = 0.01 if length > 10 else 1.0
    poses = [source.pose(values) for values in source.frames]
    report = polish_poses(poses, source.frame_time, chains=chains, contacts=contacts, config=config,
                          unit=unit, root=root)
    frames = [list(values) for values in source.frames]
    touched = [root] + [name for names in chains.values() for name in names[:3]]
    for name in touched:
        joint = by_name[name]
        rotations = [c for c in joint.channels if c.endswith('rotation')]
        order = ''.join(c[0] for c in rotations)
        if len(rotations) != 3:
            raise ValueError('ik.bvh_channels')
        for f, pose in enumerate(poses):
            t, q = pose.local[name]
            angles = euler_degrees(q, order)
            for channel, value in zip(rotations, angles):
                frames[f][joint.start + joint.channels.index(channel)] = value
            if name == root:
                positions = [c for c in joint.channels if c.endswith('position')]
                if joint.channels[:len(positions)] != tuple(positions):
                    raise ValueError('ik.bvh_channels')
                for channel in positions:
                    frames[f][joint.start + joint.channels.index(channel)] = t['XYZ'.index(channel[0])] - joint.offset['XYZ'.index(channel[0])]
    return [tuple(row) for row in frames], report


def write_bvh(source, frames):
    """BVH text with the source hierarchy and the given frames."""
    children = {}
    for joint in source.joints:
        children.setdefault(joint.parent, []).append(joint)
    lines = []

    def num(v):
        return repr(float(v))

    def emit(joint, depth, keyword):
        pad = '\t' * depth
        lines.append('%s%s %s' % (pad, keyword, joint.name))
        lines.append(pad + '{')
        lines.append('%s\tOFFSET %s' % (pad, ' '.join(num(v) for v in joint.offset)))
        lines.append('%s\tCHANNELS %d %s' % (pad, len(joint.channels), ' '.join(joint.channels)))
        for child in children.get(joint.name, ()):
            emit(child, depth + 1, 'JOINT')
        for end in joint.end_sites:
            lines.append(pad + '\tEnd Site')
            lines.append(pad + '\t{')
            lines.append('%s\t\tOFFSET %s' % (pad, ' '.join(num(v) for v in end)))
            lines.append(pad + '\t}')
        lines.append(pad + '}')

    lines.append('HIERARCHY')
    emit(source.joints[0], 0, 'ROOT')
    lines += ['MOTION', 'Frames: %d' % len(frames), 'Frame Time: %s' % num(source.frame_time)]
    lines += [' '.join(num(v) for v in row) for row in frames]
    return '\n'.join(lines) + '\n'


def _read(path, limit=MAX_BYTES):
    with Path(path).open('rb') as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('input.file_limit')
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--bvh', type=Path)
    source.add_argument('--anm', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--addons', default=os.environ.get('DAYZ_ADDONS'))
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args(argv)
    try:
        out = args.out.resolve()
        if any(part.casefold() == 'mods' for part in out.parts):
            raise ValueError('output.mods_forbidden')
        if args.bvh:
            from tools.anim import retarget
            bvh = retarget.parse_bvh(_read(args.bvh).decode('utf-8'))
            frames, report = polish_bvh(bvh)
            data = write_bvh(bvh, frames).encode()
        else:
            if not args.addons:
                raise ValueError('skeleton.supply_addons_or_DAYZ_ADDONS')
            clip = anm.read(_read(args.anm))
            parents = rig.load_skeleton(args.addons)[0]
            report = polish_clip(clip, parents)
            data = anm.write(clip)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        row = report.as_dict()
        print('ik_polish: wrote frames=%d unreachable=%d velocity_limited=%d' % (
            row['frames'], row['unreachable_frames'], row['velocity_limited']))
        if args.report:
            print(json.dumps(row, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, struct.error) as exc:
        reason = str(exc) if type(exc) is ValueError and re.fullmatch(r'[A-Za-z0-9_:.,-]+', str(exc)) else 'input.invalid'
        print('ik_polish: refused ' + reason.split(':', 1)[0], file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
