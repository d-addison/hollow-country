"""Offline, bounded BVH -> installed DayZ infected SET6 retargeting (stdlib only).

BVH must be Y-up/+Z-forward, with intrinsic rotations in declared channel order.
Offsets define the source rest pose (zero channels, never the first motion frame).
World-space rest deltas are applied to rig.rest_pose; unmapped optional target bones
retain their local rest transforms. Translation is pelvis travel relative to zero
channels, scaled by mean hip-knee-ankle length. Non-root translation is refused.

The JSON map is {source_joint: target_bone}; entries override DEFAULT_MAP, and null
excludes an alias. A LeftHip/LeftKnee/LeftAnkle hierarchy selects 100STYLE
Chest/Collar/Shoulder/Elbow/Wrist aliases. Required body bones must map uniquely. The manifest is a reviewed
local JSON object with licence (policy identifier), source_url, attribution and
licence_path (relative to the manifest). Optional sha256 and licence_sha256 pins
are checked. No network access occurs. Licence admission delegates to licence_gate;
unknown/free-use identifiers are refused until the shared policy admits them.

CLI writes clips/retargeted.anm, preview/retargeted.json and a provenance/retargeted/
folder containing pinned source/licence bytes and provenance.json. --addons (or
DAYZ_ADDONS) supplies the installed skeleton read-only. Output cannot be in mods/.
The provenance is an input admission receipt, not a sealed shipping candidate.

Optional contact-based root foot lock and C1 loop easing are PROVISIONAL polish,
pending native inspection; neither is a full IK solver. Loop easing closes to a
stationary seam (zero endpoint velocity) and removes root travel at the boundary.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit

from tools.anim import anm, rig
from tools.assets import licence_gate
from tools.assets.provenance import build_provenance

MAX_BYTES = 16 << 20
MAX_JOINTS = 256
MAX_DEPTH = 48
MAX_FRAMES = 65535                 # SET6 u16
MAX_SAMPLES = 2_000_000
REQUIRED_BONES = ('Pelvis', 'Spine', 'Spine2', 'Spine3', 'Neck', 'Head',
                  'LeftArm', 'LeftForeArm', 'LeftHand', 'RightArm', 'RightForeArm', 'RightHand',
                  'LeftUpLeg', 'LeftLeg', 'LeftFoot', 'RightUpLeg', 'RightLeg', 'RightFoot')
DEFAULT_MAP = {n: n for n in REQUIRED_BONES + ('LeftToeBase', 'RightToeBase',
                                             'LeftShoulder', 'RightShoulder')}
DEFAULT_MAP.update(dict(Hips='Pelvis', hips='Pelvis', lowerback='Spine', upperback='Spine2',
                        thorax='Spine3', lowerneck='Neck', head='Head',
                        lclavicle='LeftShoulder', rclavicle='RightShoulder',
                        lhumerus='LeftArm', lradius='LeftForeArm', lwrist='LeftHand',
                        rhumerus='RightArm', rradius='RightForeArm', rwrist='RightHand',
                        lfemur='LeftUpLeg', ltibia='LeftLeg', lfoot='LeftFoot', ltoes='LeftToeBase',
                        rfemur='RightUpLeg', rtibia='RightLeg', rfoot='RightFoot', rtoes='RightToeBase'))
STYLE_MAP = dict(Chest='Spine', Chest2='Spine2', Chest3='Spine3',
                 LeftCollar='LeftShoulder', RightCollar='RightShoulder',
                 LeftShoulder='LeftArm', LeftElbow='LeftForeArm', LeftWrist='LeftHand',
                 RightShoulder='RightArm', RightElbow='RightForeArm', RightWrist='RightHand',
                 LeftHip='LeftUpLeg', LeftKnee='LeftLeg', LeftAnkle='LeftFoot', LeftToe='LeftToeBase',
                 RightHip='RightUpLeg', RightKnee='RightLeg', RightAnkle='RightFoot', RightToe='RightToeBase')
AXES = {'X': (1, 0, 0), 'Y': (0, 1, 0), 'Z': (0, 0, 1)}
CHANNELS = {a + kind for a in AXES for kind in ('position', 'rotation')}


@dataclass
class Joint:
    name: str
    parent: str | None
    offset: tuple
    channels: tuple
    start: int
    end_sites: tuple


@dataclass
class BVH:
    joints: list
    frames: list
    frame_time: float
    raw: bytes

    def pose(self, values=None):
        local = {}
        for joint in self.joints:
            t, q = joint.offset, rig.IDENTITY
            for channel, value in zip(joint.channels, values[joint.start:joint.start + len(joint.channels)] if values is not None
                                      else [0.0] * len(joint.channels)):
                if channel.endswith('rotation'):
                    q = rig.qmul(q, rig.qaxis(AXES[channel[0]], value))
                else:
                    t = rig.vadd(t, rig.qrot(q, rig.vscale(AXES[channel[0]], value)))
            local[joint.name] = (t, rig.qnorm(q))
        return rig.Pose({j.name: j.parent for j in self.joints}, local)


def _number(token):
    try:
        value = float(token)
    except ValueError as exc:
        raise ValueError('bvh.number') from exc
    if not math.isfinite(value) or abs(value) > 1e12:
        raise ValueError('bvh.number_range')
    return value


def parse_bvh(text):
    """Parse hierarchy including End Sites and exact channel/frame cardinality."""
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('bvh.file_limit')
    raw = text.encode('utf-8')
    tokens = iter(m.group() for m in re.finditer(r'[{}]|[^\s{}]+', text.lstrip('\ufeff')))

    def take(expected=None):
        token = next(tokens, None)
        if token is None or len(token) > 128 or (expected is not None and token != expected):
            raise ValueError('bvh.syntax')
        return token

    def integer(limit, minimum=0):
        token = take()
        if not token.isascii() or not token.isdecimal():
            raise ValueError('bvh.integer')
        value = int(token)
        if not minimum <= value <= limit:
            raise ValueError('bvh.count_limit')
        return value

    joints, names, channel_count = [], set(), 0

    def joint(parent, depth):
        nonlocal channel_count
        if depth > MAX_DEPTH or len(joints) >= MAX_JOINTS:
            raise ValueError('bvh.joint_limit')
        name = take()
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.:-]*', name) or name in names:
            raise ValueError('bvh.joint_name')
        names.add(name)
        take('{')
        take('OFFSET')
        offset = tuple(_number(take()) for _ in range(3))
        take('CHANNELS')
        count = integer(6)
        channels = tuple(take() for _ in range(count))
        if len(set(channels)) != count or any(c not in CHANNELS for c in channels):
            raise ValueError('bvh.channels')
        if parent is not None and any(c.endswith('position') for c in channels):
            raise ValueError('bvh.nonroot_translation')
        item = Joint(name, parent, offset, channels, channel_count, ())
        joints.append(item)
        channel_count += count
        ends = []
        while True:
            token = take()
            if token == '}':
                break
            if token == 'JOINT':
                joint(name, depth + 1)
            elif token == 'End':
                take('Site')
                take('{')
                take('OFFSET')
                ends.append(tuple(_number(take()) for _ in range(3)))
                take('}')
                if len(ends) > 1:
                    raise ValueError('bvh.end_site')
            else:
                raise ValueError('bvh.hierarchy')
        item.end_sites = tuple(ends)

    take('HIERARCHY')
    take('ROOT')
    joint(None, 0)
    take('MOTION')
    take('Frames:')
    count = integer(MAX_FRAMES, 1)
    take('Frame')
    take('Time:')
    dt = _number(take())
    if not 1e-4 <= dt <= 1 or not channel_count or count * channel_count > MAX_SAMPLES:
        raise ValueError('bvh.motion_limit')
    frames = [tuple(_number(take()) for _ in range(channel_count)) for _ in range(count)]
    if next(tokens, None) is not None:
        raise ValueError('bvh.trailing_data')
    return BVH(joints, frames, dt, raw)


def _read(path, limit=MAX_BYTES):
    with Path(path).open('rb') as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('input.file_limit')
    return raw


def read_bvh(path):
    return parse_bvh(_read(path).decode('utf-8'))


def load_map(path):
    mapping = json.loads(_read(path, 65536))
    if (not isinstance(mapping, dict) or any(not isinstance(k, str) or
            (v is not None and not isinstance(v, str)) for k, v in mapping.items())):
        raise ValueError('map.invalid')
    return mapping


def admit_source(raw, manifest, licence):
    """Admit pinned local bytes using shared policy; return authoritative provenance."""
    if not isinstance(manifest, dict):
        raise ValueError('manifest.invalid')
    for field in ('licence', 'source_url', 'attribution'):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            raise ValueError('manifest.missing_' + field)
    url = urlsplit(manifest['source_url'])
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
        raise ValueError('manifest.source_url')
    hashes = [hashlib.sha256(data).hexdigest() for data in (raw, licence)]
    for key, value in zip(('sha256', 'licence_sha256'), hashes):
        if key in manifest and manifest[key] != value:
            raise ValueError('manifest.digest_mismatch')
    record = dict(source=manifest['source_url'], path='source.bvh', sha256=hashes[0],
                  licence_id=manifest['licence'], licence_path='licence.txt',
                  licence_sha256=hashes[1], attribution=manifest['attribution'])
    with tempfile.TemporaryDirectory(prefix='hc-retarget-') as folder:
        root = Path(folder)
        (root / 'source.bvh').write_bytes(raw)
        (root / 'licence.txt').write_bytes(licence)
        document = build_provenance(asset='retargeted', inputs=[record], toolchain=[],
                                    origin='tools.anim.retarget', root=root)
        result = licence_gate.evaluate(document, root=root)
    if not result['shippable']:
        raise ValueError('licence.refused:' + ','.join(result['reasons']))
    return document


def _mapping(source, bones, overrides):
    mapping = dict(DEFAULT_MAP)
    if {'LeftHip', 'LeftKnee', 'LeftAnkle'} <= {j.name for j in source.joints}:
        mapping.update(STYLE_MAP)
    mapping.update(overrides or {})
    reverse = {}
    for joint in source.joints:
        target = mapping.get(joint.name)
        if target is None:
            continue
        if target not in bones:
            raise ValueError('map.unknown_target:' + target)
        if target in reverse:
            raise ValueError('map.duplicate_target:' + target)
        reverse[target] = joint.name
    for name in REQUIRED_BONES:
        if name not in reverse:
            raise ValueError('map.required_bone:' + name)
    if reverse['Pelvis'] != source.joints[0].name:
        raise ValueError('map.pelvis_must_be_root')
    return reverse


def _leg_length(pose, names):
    return sum(rig.vlen(rig.vsub(pose.pos(b), pose.pos(a))) for a, b in zip(names, names[1:]))


def retarget(source, parents, rest, bones, *, manifest, licence, mapping=None,
             foot_lock=False, loop_frames=0):
    """Return an anm.Anim with .provenance; always admit the source before retargeting.

    Target skeleton arguments are exactly rig.load_skeleton's return values.
    """
    provenance = admit_source(source.raw, manifest, licence)
    if len(source.frames) * len(bones) > MAX_SAMPLES:
        raise ValueError('retarget.output_limit')
    reverse = _mapping(source, bones, mapping)
    target_rest = rig.rest_pose(parents, rest, bones)
    source_rest = source.pose()
    lengths = []
    for side in ('Left', 'Right'):
        chain = [side + suffix for suffix in ('UpLeg', 'Leg', 'Foot')]
        src = _leg_length(source_rest, [reverse[n] for n in chain])
        dst = _leg_length(target_rest, chain)
        if min(src, dst) <= 1e-8:
            raise ValueError('retarget.zero_leg_length')
        lengths.append((src, dst))
    scale = sum(p[1] for p in lengths) / sum(p[0] for p in lengths)
    poses = []
    sw, tw = source_rest.world(), target_rest.world()
    for values in source.frames:
        current = source.pose(values).world()
        pose = target_rest.copy()
        for bone in pose.order:
            if bone in reverse:
                src = reverse[bone]
                delta = rig.qmul(current[src][1], rig.qinv(sw[src][1]))
                pose.set_world_rot(bone, rig.qmul(delta, tw[bone][1]))
        root = reverse['Pelvis']
        travel = rig.vscale(rig.vsub(current[root][0], sw[root][0]), scale)
        pose.set_root_pos('Pelvis', rig.vadd(tw['Pelvis'][0], travel))
        poses.append(pose)
    if foot_lock:
        lock_feet(poses, source.frame_time)
    if loop_frames:
        blend_loop(poses, loop_frames)
    # SET6 stores integer FPS. Resample rather than silently changing clip speed.
    fps = max(1, round(1 / source.frame_time))
    count = max(1, round((len(poses) - 1) * source.frame_time * fps) + 1)
    if count > MAX_FRAMES or count * len(bones) > MAX_SAMPLES:
        raise ValueError('retarget.output_limit')
    clip = anm.Anim(fps=fps, frames=count)
    clip.provenance = provenance
    for name in bones:
        bone = anm.Bone(name)
        for frame in range(count):
            at = min(frame / fps / source.frame_time, len(poses) - 1)
            low = int(at)
            high = min(low + 1, len(poses) - 1)
            t0, q0 = poses[low].local[name]
            t1, q1 = poses[high].local[name]
            bone.t.frames.append(frame)
            bone.q.frames.append(frame)
            bone.t.values.append(rig.vlerp(t0, t1, at - low))
            bone.q.values.append(rig.qslerp(q0, q1, at - low))
        clip.bones.append(bone)
    return clip


def lock_feet(poses, dt, height=0.04, speed=0.15):
    """PROVISIONAL: hold slow, low feet via mean pelvis correction, no limb IK."""
    feet = ('LeftFoot', 'RightFoot')
    positions = [{n: p.pos(n) for n in feet} for p in poses]
    floor = min(v[1] for row in positions for v in row.values())
    anchors = {}
    for i, pose in enumerate(poses):
        corrections = []
        for name in feet:
            pos = positions[i][name]
            previous = positions[max(0, i - 1)][name]
            contact = pos[1] <= floor + height and rig.vlen(rig.vsub(pos, previous)) / dt <= speed
            if contact:
                anchors.setdefault(name, pos)
                corrections.append(rig.vsub(anchors[name], pos))
            else:
                anchors.pop(name, None)
        if corrections:
            correction = tuple(sum(v[a] for v in corrections) / len(corrections) for a in range(3))
            pose.set_root_pos('Pelvis', rig.vadd(pose.pos('Pelvis'), correction))


def blend_loop(poses, window):
    """PROVISIONAL C1 seam: cubic easing into a shared stationary endpoint pose."""
    if not isinstance(window, int) or window < 3 or 2 * window > len(poses):
        raise ValueError('loop.window')
    first, last = poses[0].copy(), poses[-1].copy()
    seam = {n: (rig.vlerp(first.local[n][0], last.local[n][0], 0.5),
                rig.qslerp(first.local[n][1], last.local[n][1], 0.5)) for n in first.local}
    # Duplicate seam samples enforce equal zero discrete endpoint velocities too.
    for edge in (range(window), range(len(poses) - 1, len(poses) - window - 1, -1)):
        for distance, index in enumerate(edge):
            u = max(0.0, (distance - 1) / (window - 2))
            weight = 1 - u * u * (3 - 2 * u)
            pose = poses[index]
            for n, (st, sq) in seam.items():
                t, q = pose.local[n]
                pose.local[n] = (rig.vlerp(t, st, weight), rig.qslerp(q, sq, weight))
            pose._world = None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for name in ('bvh', 'map', 'manifest', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--addons', default=os.environ.get('DAYZ_ADDONS'))
    parser.add_argument('--foot-lock', action='store_true')
    parser.add_argument('--loop-frames', type=int, default=0)
    args = parser.parse_args(argv)
    try:
        out = args.out.resolve()
        if any(part.casefold() == 'mods' for part in out.parts):
            raise ValueError('output.mods_forbidden')
        if not args.addons:
            raise ValueError('skeleton.supply_addons_or_DAYZ_ADDONS')
        raw = _read(args.bvh)
        manifest = json.loads(_read(args.manifest, 65536))
        if not isinstance(manifest, dict) or not isinstance(manifest.get('licence_path'), str):
            raise ValueError('manifest.licence_path')
        licence = _read(args.manifest.parent / manifest['licence_path'], 1 << 20)
        source = parse_bvh(raw.decode('utf-8'))
        skeleton = rig.load_skeleton(args.addons)
        clip = retarget(source, *skeleton, manifest=manifest, licence=licence, mapping=load_map(args.map),
                        foot_lock=args.foot_lock, loop_frames=args.loop_frames)
        segments = [(p, n) for n, p in skeleton[0].items() if p in skeleton[2] and n in skeleton[2]]
        preview = {'fps': clip.fps, 'segments': segments, 'frames': []}
        for frame in range(clip.frames):
            world = rig.pose_from_clip(skeleton[0], clip, frame).world()
            preview['frames'].append({n: [round(c, 4) for c in world[n][0]] for n in skeleton[2]})
        outputs = {'clips/retargeted.anm': anm.write(clip),
                   'preview/retargeted.json': json.dumps(preview).encode(),
                   'provenance/retargeted/source.bvh': raw,
                   'provenance/retargeted/licence.txt': licence,
                   'provenance/retargeted/provenance.json': json.dumps(clip.provenance, indent=2).encode()}
        # Resolve every destination before any writes, including preexisting directory symlinks.
        for name in outputs:
            destination = (out / name).resolve()
            if not destination.is_relative_to(out) or any(p.casefold() == 'mods' for p in destination.parts):
                raise ValueError('output.unsafe_destination')
        for name, data in outputs.items():
            destination = out / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        print('retarget: wrote clip frames=%d fps=%d licence=shippable' % (clip.frames, clip.fps))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        # Stable reason codes only; no local paths or exception payloads in CLI output.
        reason = str(exc) if type(exc) is ValueError and re.fullmatch(r'[A-Za-z0-9_:.,-]+', str(exc)) else 'input.invalid'
        print('retarget: refused ' + reason.split(':', 1)[0], file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
