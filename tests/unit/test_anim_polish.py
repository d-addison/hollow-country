"""Synthetic skeletons and BVH only; no vanilla clip, graph or mesh. Offline tooling, no engine claim."""
import contextlib
import io
import itertools
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.anim import anm, ik_polish, retarget, rig

LEG = 0.45
X, Y = (1, 0, 0), (0, 1, 0)


def skeleton():
    """Scene_Root > Pelvis > {Left,Right}UpLeg > Leg > Foot > ToeBase, metres, legs bent forward."""
    parents = {'Scene_Root': None, 'Pelvis': 'Scene_Root'}
    rest = {'Scene_Root': ((0.0, 0.0, 0.0), rig.IDENTITY), 'Pelvis': ((0.0, 0.95, 0.0), rig.IDENTITY)}
    for side, sx in (('Left', -0.1), ('Right', 0.1)):
        for name, parent, offset in ((side + 'UpLeg', 'Pelvis', (sx, 0.0, 0.0)),
                                     (side + 'Leg', side + 'UpLeg', (0.0, -LEG, 0.0)),
                                     (side + 'Foot', side + 'Leg', (0.0, -LEG, 0.0)),
                                     (side + 'ToeBase', side + 'Foot', (0.0, -0.05, 0.15))):
            parents[name] = parent
            rest[name] = (offset, rig.IDENTITY)
    return parents, rest


def drifting(frames, step, bend=True, parents_rest=None):
    parents, rest = parents_rest or skeleton()
    poses = []
    for i in range(frames):
        local = dict(rest)
        if bend:
            for side in ('Left', 'Right'):
                local[side + 'UpLeg'] = (rest[side + 'UpLeg'][0], rig.qaxis(X, -25))
                local[side + 'Leg'] = (rest[side + 'Leg'][0], rig.qaxis(X, 50))
        local['Pelvis'] = ((step * i, 0.95, 0.0), rig.IDENTITY)
        poses.append(rig.Pose(parents, local))
    return poses


def ankle_rows(poses, side):
    return [p.pos(side + 'Foot') for p in poses]


def lengths(pose):
    return [rig.vlen(rig.vsub(pose.pos(b), pose.pos(a))) for side in ('Left', 'Right')
            for a, b in ((side + 'UpLeg', side + 'Leg'), (side + 'Leg', side + 'Foot'))]


DT = 1 / 30


class FootLockTests(unittest.TestCase):
    def test_contact_feet_are_planted_and_bones_keep_their_length(self):
        poses = drifting(30, 0.002)
        before = [lengths(p) for p in poses]
        report = ik_polish.polish_poses(poses, DT)
        for side in ('Left', 'Right'):
            row = report.feet[side]
            self.assertEqual([(0, 29)], row['intervals'])
            self.assertGreater(row['slide_before'], 0.02)
            self.assertLess(row['slide_after'], 0.0015)
            spread = [rig.vlen(rig.vsub(v, ankle_rows(poses, side)[0])) for v in ankle_rows(poses, side)]
            self.assertLess(max(spread), 0.0015)
        for a, b in zip(before, [lengths(p) for p in poses]):
            for x, y in zip(a, b):
                self.assertAlmostEqual(x, y, places=6)
        self.assertEqual(0, report.unreachable_frames)
        self.assertEqual(0.0, report.pelvis_shift_max)

    def test_pelvis_path_is_untouched_when_every_pin_is_reachable(self):
        poses = drifting(30, 0.002)
        ik_polish.polish_poses(poses, DT)
        for i, pose in enumerate(poses):
            for a, b in zip(pose.pos('Pelvis'), (0.002 * i, 0.95, 0.0)):
                self.assertAlmostEqual(a, b, places=9)

    def test_toe_heading_is_held_while_planted(self):
        poses = drifting(30, 0.002)
        for i, pose in enumerate(poses):          # source foot slowly turns while "planted"
            pose.rotate_world('LeftFoot', rig.qaxis(Y, 0.4 * i))
        ik_polish.polish_poses(poses, DT)
        headings = []
        for pose in poses:
            d = rig.vsub(pose.pos('LeftToeBase'), pose.pos('LeftFoot'))
            headings.append(math.degrees(math.atan2(d[0], d[2])))
        self.assertLess(max(headings) - min(headings), 0.5)

    def test_out_of_reach_pins_use_a_bounded_pelvis_assist(self):
        poses = drifting(60, 0.0025, bend=False)
        report = ik_polish.polish_poses(poses, DT)
        self.assertGreater(report.pelvis_shift_max, 0.0)
        self.assertLessEqual(report.pelvis_shift_max, ik_polish.Config().max_pelvis_shift + 1e-9)
        for side in ('Left', 'Right'):
            self.assertLess(report.feet[side]['slide_after'], report.feet[side]['slide_before'])
            self.assertLess(report.feet[side]['slide_after'], 0.004)
        for pose in poses:
            for length in lengths(pose):
                self.assertAlmostEqual(length, LEG, places=6)

    def test_supplied_contacts_replace_detection_and_are_validated(self):
        poses = drifting(30, 0.002)
        report = ik_polish.polish_poses(poses, DT, contacts={'Left': [(5, 20)]})
        self.assertEqual([(5, 20)], report.feet['Left']['intervals'])
        self.assertEqual([], report.feet['Right']['intervals'])
        for bad in ({'Left': [(5, 99)]}, {'Left': [(-1, 3)]}, {'Left': [(4, 2)]}):
            with self.assertRaisesRegex(ValueError, 'ik.contacts'):
                ik_polish.polish_poses(drifting(30, 0.002), DT, contacts=bad)

    def test_short_or_fast_feet_are_not_contacts(self):
        poses = drifting(30, 0.02)                  # 0.6 m/s pelvis: feet are swinging
        report = ik_polish.polish_poses(poses, DT)
        self.assertEqual([], report.feet['Left']['intervals'])
        flags = ik_polish.detect_contacts([(0.0, 0.0)] * 2 + [(0.5, 0.0)] + [(0.0, 0.0)] * 3, 0.0, ik_polish.Config())
        self.assertEqual([(3, 5)], flags)

    def test_velocity_limit_never_adds_speed(self):
        config = ik_polish.Config(max_joint_dps=30.0, blend_frames=0)
        poses = drifting(30, 0.002)
        report = ik_polish.polish_poses(poses, DT, contacts={'Left': [(10, 29)]}, config=config)
        self.assertGreater(report.velocity_limited, 0)
        limit = math.radians(30.0) * DT
        for bone in ('LeftUpLeg', 'LeftLeg', 'LeftFoot'):
            for a, b in zip(poses, poses[1:]):
                self.assertLessEqual(ik_polish._angle(a.local[bone][1], b.local[bone][1]), limit + 1e-6)

    def test_deterministic_and_inputs_validated(self):
        one, two = drifting(30, 0.002), drifting(30, 0.002)
        ik_polish.polish_poses(one, DT)
        ik_polish.polish_poses(two, DT)
        for a, b in zip(one, two):
            self.assertEqual(a.local, b.local)
        with self.assertRaisesRegex(ValueError, 'ik.frame_limit'):
            ik_polish.polish_poses([], DT)
        with mock.patch.object(ik_polish, 'MAX_FRAMES', 5):
            with self.assertRaisesRegex(ValueError, 'ik.frame_limit'):
                ik_polish.polish_poses(drifting(6, 0.0), DT)
        with self.assertRaisesRegex(ValueError, 'ik.frame_time'):
            ik_polish.polish_poses(drifting(6, 0.0), 0)
        with self.assertRaisesRegex(ValueError, 'ik.config'):
            ik_polish.polish_poses(drifting(6, 0.0), DT, config=ik_polish.Config(reach=2.0))
        poses = drifting(6, 0.0)
        for pose in poses:
            del pose.local['RightLeg']
        with self.assertRaisesRegex(ValueError, 'ik.chain_bone:RightLeg'):
            ik_polish.polish_poses(poses, DT)

    def test_retarget_foot_lock_is_the_ik_pass(self):
        poses = drifting(30, 0.002)
        report = retarget.lock_feet(poses, DT)
        self.assertIsInstance(report, ik_polish.Report)
        self.assertLess(report.feet['Left']['slide_after'], 0.0015)


class ClipTests(unittest.TestCase):
    def clip_from(self, poses, parents):
        clip = anm.Anim(fps=30, frames=len(poses))
        for name in parents:
            bone = anm.Bone(name)
            for f, pose in enumerate(poses):
                t, q = pose.local[name]
                bone.t.frames.append(f)
                bone.t.values.append(tuple(t))
                bone.q.frames.append(f)
                bone.q.values.append(tuple(q))
            clip.bones.append(bone)
        return clip

    def test_retargeted_clip_polish_survives_the_codec(self):
        parents, _ = skeleton()
        poses = drifting(30, 0.002)
        clip = self.clip_from(poses, parents)
        untouched = clip.bone('Scene_Root').q.values[:]
        report = ik_polish.polish_clip(clip, parents)
        decoded = anm.read(anm.write(clip))
        self.assertEqual(30, decoded.frames)
        rows = [rig.pose_from_clip(parents, decoded, f).pos('LeftFoot') for f in range(30)]
        self.assertLess(max(rig.vlen(rig.vsub(v, rows[0])) for v in rows), 0.003)
        self.assertEqual([(0, 29)], report.feet['Left']['intervals'])
        self.assertEqual(untouched, decoded.bone('Scene_Root').q.values)
        for name in ('LeftUpLeg', 'LeftLeg', 'LeftFoot', 'Pelvis'):
            self.assertEqual(30, len(decoded.bone(name).q.values))

    def test_clip_rotation_keys_keep_one_hemisphere(self):
        parents, _ = skeleton()
        clip = self.clip_from(drifting(30, 0.002), parents)
        ik_polish.polish_clip(clip, parents)
        for name in ('LeftUpLeg', 'LeftLeg', 'LeftFoot'):
            values = clip.bone(name).q.values
            for a, b in zip(values, values[1:]):
                self.assertGreaterEqual(sum(x * y for x, y in zip(a, b)), 0)

    def test_clip_limits_and_missing_bones_are_refused(self):
        parents, _ = skeleton()
        clip = self.clip_from(drifting(30, 0.002), parents)
        with mock.patch.object(ik_polish, 'MAX_FRAMES', 10):
            with self.assertRaisesRegex(ValueError, 'ik.frame_limit'):
                ik_polish.polish_clip(clip, parents)
        clip.bones = [b for b in clip.bones if b.name != 'LeftFoot']
        with self.assertRaisesRegex(ValueError, 'ik.chain_bone:LeftFoot'):
            ik_polish.polish_clip(clip, parents)


def bvh_text(frames=40, step_cm=0.2):
    """Hips (translated, YXZ-free fixture order Z X Y) with bent legs, centimetres, planted feet drifting."""
    def joint(name, offset, depth, tail):
        pad = ' ' * depth
        return ('%sJOINT %s\n%s{\n%s OFFSET %s\n%s CHANNELS 3 Zrotation Xrotation Yrotation\n%s%s}\n'
                % (pad, name, pad, pad, ' '.join(map(str, offset)), pad, tail, pad))
    def leg(side, x):
        foot = joint(side + 'ToeBase', (0, -5, 15), 4, '')
        foot = joint(side + 'Foot', (0, -45, 0), 3, foot)
        shin = joint(side + 'Leg', (0, -45, 0), 2, foot)
        return joint(side + 'UpLeg', (x, 0, 0), 1, shin)
    text = ('HIERARCHY\nROOT Hips\n{\n OFFSET 0 95 0\n CHANNELS 6 Xposition Yposition Zposition '
            'Zrotation Xrotation Yrotation\n' + leg('Left', -10) + leg('Right', 10) + '}\nMOTION\n'
            'Frames: %d\nFrame Time: %r\n' % (frames, DT))
    rows = []
    for i in range(frames):
        row = [step_cm * i, 0, 0, 0, 0, 0]
        for _ in ('Left', 'Right'):
            row += [0, -25, 0, 0, 50, 0, 0, -25, 0, 0, 0, 0]
        rows.append(' '.join(repr(float(v)) for v in row))
    return text + '\n'.join(rows) + '\n'


class BvhTests(unittest.TestCase):
    def test_euler_roundtrip_for_every_channel_order(self):
        axes = {'X': X, 'Y': Y, 'Z': (0, 0, 1)}
        q0 = rig.qnorm((0.1, 0.2, 0.3, 0.9))
        for order in itertools.permutations('XYZ'):
            name = ''.join(order)
            angles = ik_polish.euler_degrees(q0, name)
            q = rig.IDENTITY
            for axis, value in zip(name, angles):
                q = rig.qmul(q, rig.qaxis(axes[axis], value))
            self.assertAlmostEqual(abs(sum(a * b for a, b in zip(q, q0))), 1.0, places=9, msg=name)
        with self.assertRaisesRegex(ValueError, 'ik.gimbal'):
            ik_polish.euler_degrees(rig.qaxis(X, 90), 'ZXY')
        with self.assertRaisesRegex(ValueError, 'ik.bvh_channels'):
            ik_polish.euler_degrees(rig.IDENTITY, 'XXY')

    def test_write_bvh_is_a_faithful_roundtrip(self):
        source = retarget.parse_bvh(bvh_text())
        again = retarget.parse_bvh(ik_polish.write_bvh(source, source.frames))
        self.assertEqual([(j.name, j.parent, j.offset, j.channels, j.end_sites) for j in source.joints],
                         [(j.name, j.parent, j.offset, j.channels, j.end_sites) for j in again.joints])
        self.assertEqual(source.frames, again.frames)
        self.assertEqual(source.frame_time, again.frame_time)

    def test_polish_bvh_plants_feet_and_leaves_other_channels(self):
        source = retarget.parse_bvh(bvh_text())
        frames, report = ik_polish.polish_bvh(source)
        out = retarget.parse_bvh(ik_polish.write_bvh(source, frames))
        self.assertEqual(len(source.frames), len(out.frames))
        self.assertEqual(len(source.frames[0]), len(out.frames[0]))
        touched = set()
        for joint in source.joints:
            for f in range(len(frames)):
                if frames[f][joint.start:joint.start + len(joint.channels)] != source.frames[f][joint.start:joint.start + len(joint.channels)]:
                    touched.add(joint.name)
        self.assertLessEqual(touched, {'Hips', 'LeftUpLeg', 'LeftLeg', 'LeftFoot', 'RightUpLeg', 'RightLeg', 'RightFoot'})
        self.assertGreater(report.feet['Left']['slide_before'], 0.01)
        poses = [out.pose(v) for v in out.frames]
        rows = [p.pos('LeftFoot') for p in poses]
        self.assertLess(max(rig.vlen(rig.vsub(v, rows[0])) for v in rows) * 0.01, 0.0015)
        self.assertLess(report.feet['Left']['slide_after'], 0.0015)

    def test_unit_is_inferred_for_centimetres_and_overridable(self):
        source = retarget.parse_bvh(bvh_text())
        one = ik_polish.polish_bvh(source)[1]
        metres = ik_polish.polish_bvh(source, unit=1.0)[1]      # thresholds then read as 100x tighter in space
        self.assertEqual([(0, 39)], one.feet['Left']['intervals'])
        self.assertNotEqual(one.feet['Left']['slide_before'], metres.feet['Left']['slide_before'])

    def test_refuses_a_bvh_without_leg_chains_or_with_odd_channels(self):
        text = bvh_text().replace('LeftToeBase', 'LToe').replace('LeftFoot', 'LFoot')
        with self.assertRaisesRegex(ValueError, 'ik.bvh_chain:Left'):
            ik_polish.polish_bvh(retarget.parse_bvh(text))

    def test_cli_writes_bvh_reports_and_refuses_mods(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'in.bvh').write_text(bvh_text())
            out = root / 'out/clip.bvh'
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(0, ik_polish.main(['--bvh', str(root / 'in.bvh'), '--out', str(out), '--report']))
            lines = stdout.getvalue().splitlines()
            self.assertTrue(lines[0].startswith('ik_polish: wrote frames=40'))
            self.assertEqual(40, json.loads(lines[1])['frames'])
            self.assertEqual(40, len(retarget.parse_bvh(out.read_text()).frames))
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(1, ik_polish.main(['--bvh', str(root / 'in.bvh'), '--out', str(root / 'mods/x.bvh')]))
                self.assertEqual(1, ik_polish.main(['--bvh', str(root / 'missing.bvh'), '--out', str(out)]))
            self.assertNotIn(folder, stderr.getvalue())
            self.assertFalse((root / 'mods').exists())


if __name__ == '__main__':
    unittest.main()
