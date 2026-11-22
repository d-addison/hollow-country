"""Original synthetic BVH exercises offline tooling; no engine-behaviour claim."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.anim import anm, retarget, rig

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/anim/synthetic_walk.bvh'
LICENCE = b'Original synthetic test motion, licensed CC-BY-4.0 by Hollow Country contributors.'
MANIFEST = {'licence': 'CC-BY-4.0', 'source_url': 'https://example.org/synthetic-walk',
            'attribution': 'Synthetic motion: Hollow Country contributors', 'licence_path': 'licence.txt'}


class RetargetTests(unittest.TestCase):
    def setUp(self):
        self.source = retarget.read_bvh(FIXTURE)
        # Target rest skeleton from fixture data, centimetres -> metres. No game data.
        self.bones = (['Scene_Root'] + list(rig.ROOT_EXTRAS) +
                      [retarget.DEFAULT_MAP[j.name] for j in self.source.joints] + list(rig.TAIL_EXTRAS))
        self.parents = {'Scene_Root': None}
        self.rest = {'Scene_Root': ((0, 0, 0), rig.IDENTITY)}
        for name in rig.ROOT_EXTRAS + rig.TAIL_EXTRAS:
            self.parents[name] = 'Scene_Root'
            self.rest[name] = ((0, 0, 0), rig.IDENTITY)
        for j in self.source.joints:
            name = retarget.DEFAULT_MAP[j.name]
            self.parents[name] = retarget.DEFAULT_MAP[j.parent] if j.parent else 'Scene_Root'
            self.rest[name] = (rig.vscale(j.offset, 0.01), rig.FACING if name == 'Pelvis' else rig.IDENTITY)

    def clip(self, source=None, **kwargs):
        return retarget.retarget(source or self.source, self.parents, self.rest, self.bones,
                                 manifest=kwargs.pop('manifest', MANIFEST), licence=LICENCE, **kwargs)

    def assertRotation(self, a, b, places=5):
        self.assertAlmostEqual(abs(sum(x * y for x, y in zip(a, b))), 1, places=places)

    def test_fixture_roundtrip_and_root_scaling(self):
        clip = self.clip()
        decoded = anm.read(anm.write(clip))
        expected_frames = int(FIXTURE.read_text().split('Frames:')[1].split()[0])
        self.assertEqual(decoded.frames, expected_frames)
        self.assertEqual([b.name for b in decoded.bones], self.bones)
        rest = rig.rest_pose(self.parents, self.rest, self.bones)
        src_rest = self.source.pose()
        root = self.source.joints[0].name
        scale = retarget._leg_length(rest, ('LeftUpLeg', 'LeftLeg', 'LeftFoot')) / retarget._leg_length(
            src_rest, ('LeftUpLeg', 'LeftLeg', 'LeftFoot'))
        for index, frame in enumerate(self.source.frames):
            expected = rig.vadd(rest.pos('Pelvis'), rig.vscale(rig.vsub(
                self.source.pose(frame).pos(root), src_rest.pos(root)), scale))
            for a, b in zip(decoded.bone('Pelvis').t.values[index], expected):
                self.assertAlmostEqual(a, b, places=4)
        record = clip.provenance['inputs'][0]
        self.assertEqual(record['attribution'], MANIFEST['attribution'])
        self.assertEqual(record['sha256'], hashlib.sha256(FIXTURE.read_bytes()).hexdigest())

    def test_identity_rest_maps_to_identity(self):
        source = copy.deepcopy(self.source)
        source.frames = [tuple(0 for _ in frame) for frame in source.frames]
        for bone in self.clip(source).bones:
            for q in bone.q.values:
                self.assertRotation(q, rig.IDENTITY)

    def test_nonidentity_target_rest_and_delta(self):
        self.rest['LeftArm'] = (self.rest['LeftArm'][0], rig.qaxis((0, 0, 1), 30))
        rest = rig.rest_pose(self.parents, self.rest, self.bones)
        clip = self.clip()
        for n in self.bones:
            self.assertRotation(clip.bone(n).q.values[0], rest.local[n][1])
        for i, values in enumerate(self.source.frames):
            source_world = self.source.pose(values).world()
            actual = rig.pose_from_clip(self.parents, clip, i).world()
            for j in self.source.joints:
                n = retarget.DEFAULT_MAP[j.name]
                expected = rig.qmul(source_world[j.name][1], rest.world()[n][1])
                self.assertRotation(actual[n][1], expected)

    def test_source_naming_families(self):
        cmu = {k: v for k, v in retarget.DEFAULT_MAP.items() if k.islower()}
        for aliases in (retarget.STYLE_MAP, cmu):
            inverse = {}
            for source, target in aliases.items():
                inverse.setdefault(target, source)
            source = copy.deepcopy(self.source)
            rename = {j.name: inverse.get(retarget.DEFAULT_MAP[j.name], j.name) for j in source.joints}
            for joint in source.joints:
                joint.name = rename[joint.name]
                joint.parent = rename.get(joint.parent)
            clip = self.clip(source)
            self.assertEqual([b.name for b in clip.bones], self.bones)

    def test_channel_order(self):
        joint = self.source.joints[0]
        values = list(self.source.frames[0])
        values[joint.channels.index('Zrotation')] = 30
        values[joint.channels.index('Xrotation')] = 40
        expected = rig.qmul(rig.qaxis((0, 0, 1), 30), rig.qaxis((1, 0, 0), 40))
        self.assertRotation(self.source.pose(values).local[joint.name][1], expected)
        self.assertTrue(any(j.end_sites for j in self.source.joints))
        source = copy.deepcopy(self.source)
        root = source.joints[0]
        root.channels = ('Zrotation', 'Xposition', 'Yposition', 'Zposition', 'Xrotation', 'Yrotation')
        values = [0.0] * len(source.frames[0])
        values[0], values[1] = 90, 2
        actual = source.pose(values).pos(root.name)
        for a, b in zip(actual, rig.vadd(root.offset, (0, 2, 0))):
            self.assertAlmostEqual(a, b)

    def test_malformed_and_bounded_input(self):
        text = FIXTURE.read_text()
        frames_header = 'Frames: ' + str(len(self.source.frames))
        cases = [('', 'syntax'), (text.replace('OFFSET', 'BROKEN', 1), 'syntax'),
                 (text + ' 0', 'trailing_data'), (text.rsplit(' ', 1)[0], 'syntax'),
                 (text.replace('Frame Time: 0.03333333333333333', 'Frame Time: nan'), 'number_range'),
                 (text.replace(frames_header, 'Frames: -1'), 'integer'),
                 (text.replace(frames_header, 'Frames: ' + str(retarget.MAX_FRAMES + 1)), 'count_limit'),
                 (text.replace('Zrotation Xrotation Yrotation', 'Zrotation Zrotation Yrotation', 1), 'channels')]
        for bad, reason in cases:
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, 'bvh.' + reason):
                retarget.parse_bvh(bad)
        with mock.patch.object(retarget, 'MAX_JOINTS', len(self.source.joints) - 1):
            with self.assertRaisesRegex(ValueError, 'joint_limit'):
                retarget.parse_bvh(text)
        with mock.patch.object(retarget, 'MAX_SAMPLES', len(self.source.frames[0])):
            with self.assertRaisesRegex(ValueError, 'motion_limit'):
                retarget.parse_bvh(text)
        with mock.patch.object(retarget, 'MAX_BYTES', len(text.encode()) - 1):
            with self.assertRaisesRegex(ValueError, 'file_limit'):
                retarget.parse_bvh(text)

    def test_required_map_and_duplicate_refusals(self):
        with self.assertRaisesRegex(ValueError, 'map.required_bone:LeftFoot'):
            self.clip(mapping={'LeftFoot': None})
        with self.assertRaisesRegex(ValueError, 'map.duplicate_target'):
            self.clip(mapping={'RightFoot': 'LeftFoot'})

    def test_licence_refusals_and_pins(self):
        for change in ({'licence': 'GPL-3.0-only'}, {'licence': 'free use'},
                       {'attribution': ''}, {'sha256': '0' * 64}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.clip(manifest=dict(MANIFEST, **change))
        with mock.patch.object(retarget.licence_gate, 'evaluate', return_value=
                               retarget.licence_gate.verdict('blocked', ['test.refused'])):
            with self.assertRaisesRegex(ValueError, 'licence.refused'):
                self.clip()

    def test_provisional_polish(self):
        clip = self.clip(loop_frames=len(self.source.frames) // 2)
        for bone in clip.bones:
            self.assertEqual(bone.t.values[0], bone.t.values[-1])
            self.assertEqual(bone.t.values[0], bone.t.values[1])
            self.assertEqual(bone.t.values[-1], bone.t.values[-2])
            self.assertRotation(bone.q.values[0], bone.q.values[-1])
            self.assertRotation(bone.q.values[0], bone.q.values[1])
        poses = [rig.rest_pose(self.parents, self.rest, self.bones) for _ in self.source.frames]
        for i, pose in enumerate(poses):
            pose.set_root_pos('Pelvis', rig.vadd(pose.pos('Pelvis'), (i * .001, 0, 0)))
        start = poses[0].pos('LeftFoot')
        retarget.lock_feet(poses, self.source.frame_time)
        for pose in poses:
            for a, b in zip(pose.pos('LeftFoot'), start):
                self.assertAlmostEqual(a, b)

    def test_noninteger_fps_resampling(self):
        source = copy.deepcopy(self.source)
        source.frame_time = 1 / 29.97
        clip = self.clip(source)
        self.assertEqual(clip.frames, round((len(source.frames) - 1) * source.frame_time * clip.fps) + 1)
        self.assertLessEqual(abs((clip.frames - 1) / clip.fps -
                                 (len(source.frames) - 1) * source.frame_time), .5 / clip.fps)

    def test_cli_output_and_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'manifest.json').write_text(json.dumps(MANIFEST))
            (root / 'map.json').write_text('{}')
            (root / 'licence.txt').write_bytes(LICENCE)
            args = ['--bvh', str(FIXTURE), '--map', str(root / 'map.json'), '--manifest',
                    str(root / 'manifest.json'), '--out', str(root / 'build'), '--addons', 'unused']
            with mock.patch.object(rig, 'load_skeleton', return_value=(self.parents, self.rest, self.bones)):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(retarget.main(args), 0)
            self.assertEqual(anm.read((root / 'build/clips/retargeted.anm').read_bytes()).frames,
                             len(self.source.frames))
            receipt = root / 'build/provenance/retargeted'
            provenance = json.loads((receipt / 'provenance.json').read_bytes())
            self.assertTrue(retarget.licence_gate.evaluate(provenance, root=receipt)['shippable'])
            with contextlib.redirect_stderr(io.StringIO()):
                args[args.index('--out') + 1] = str(root / 'mods/forbidden')
                self.assertEqual(retarget.main(args), 1)
            self.assertFalse((root / 'mods').exists())
            (root / 'escape').mkdir()
            (root / 'elsewhere').mkdir()
            (root / 'escape/clips').symlink_to(root / 'elsewhere', target_is_directory=True)
            args[args.index('--out') + 1] = str(root / 'escape')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(retarget.main(args), 1)
            self.assertFalse(any((root / 'elsewhere').iterdir()))


if __name__ == '__main__':
    unittest.main()
