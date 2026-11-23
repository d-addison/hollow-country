"""Anatomy gate for the authored infected clips (tools/anim/build_infected_clips.py).

Joint positions cannot show a backwards elbow or a twisted head, so the builder checks joint
frames on every frame (``check_anatomy``). These tests need the installed game skeleton
(DAYZ_ADDONS, default: the local DayZServer Addons folder) and skip without it. Offline only:
nothing here shows how the engine plays the clips.
"""
import math
import os
import unittest

from tools.anim import anm, rig
from tools.anim import build_infected_clips as clips

ADDONS_DIR = os.environ.get('DAYZ_ADDONS', '/mnt/d/SteamLibrary/steamapps/common/DayZServer/Addons')
HAVE_GAME = all(os.path.isfile(os.path.join(ADDONS_DIR, p)) for p in (rig.CLIP_PBO, rig.WORKSPACE_PBO))
LYING_IDLES = ('hc_prone_sleep_idle', 'hc_lie_rise_idle', 'hc_lie_face_down_idle')
GETUPS = ('hc_sit_wall_getup', 'hc_prone_sleep_getup', 'hc_lie_rise_getup', 'hc_lie_face_down_getup',
          'hc_feed_kneel_getup')
JOINTS = ('Pelvis', 'Spine3', 'Neck', 'Head', 'LeftArm', 'RightArm', 'LeftForeArm', 'RightForeArm',
          'LeftHand', 'RightHand', 'LeftUpLeg', 'RightUpLeg', 'LeftLeg', 'RightLeg', 'LeftFoot', 'RightFoot')


@unittest.skipUnless(HAVE_GAME, 'installed DayZ addons not present')
class Anatomy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parents, rest, bones = rig.load_skeleton(ADDONS_DIR)
        cls.parents = parents
        cls.rest = rig.rest_pose(parents, rest, bones)
        cls.stand = clips.stand_pose(cls.rest)
        cls.shipped = {n: anm.read(anm.write(c)) for n, c in clips.build_all(parents, rest, bones).items()}

    def poses(self, name):
        clip = self.shipped[name]
        return [rig.pose_from_clip(self.parents, clip, f) for f in range(clip.frames)]

    def test_every_frame_of_every_clip_passes(self):
        report = clips.check_anatomy(self.parents, self.shipped, self.stand, self.rest)
        self.assertEqual(len(report), 10)
        for name, (_, failures) in report.items():
            self.assertEqual(failures[:3], [], name)

    def test_lying_idles_rest_on_the_ground_and_breathe_in_place(self):
        for name in LYING_IDLES:
            poses = self.poses(name)
            first = poses[0]
            self.assertLessEqual(first.pos('Pelvis')[1], 0.25, name)
            sway = max(rig.vlen(rig.vsub(p.pos(j), first.pos(j))) for p in poses for j in JOINTS)
            self.assertLessEqual(sway, 0.02, name)
            for j in JOINTS:
                self.assertGreater(first.pos(j)[1], 0.03, '%s %s below the ground' % (name, j))
                self.assertLess(first.pos(j)[1], 0.45, '%s %s off the ground' % (name, j))
                self.assertLess(rig.vlen(rig.vsub(poses[-1].pos(j), first.pos(j))), 1e-3, name)  # loop closes

    def test_sleeper_lies_on_its_side_with_head_on_the_lower_arm(self):
        p = self.poses('hc_prone_sleep_idle')[0]
        self.assertLess(p.pos('LeftArm')[1] + 0.2, p.pos('RightArm')[1])        # left side down
        self.assertLess(p.pos('LeftHand')[1], p.pos('Head')[1])                  # lower hand under the head
        self.assertLess(rig.vlen(rig.vsub(p.pos('LeftHand'), p.pos('Head'))), 0.25)
        m = clips.anatomy(p, self.stand, self.rest)
        self.assertLess(abs(m['head_yaw']), 15)                                   # faces where the chest does
        for side in ('Left', 'Right'):
            self.assertGreater(m[side + '_upper_arm_forward'], 0.5, side)        # arms forward
            self.assertGreater(m[side + '_elbow_bend'], 60, side)                # elbows flexed
            self.assertGreater(m[side + '_knee_bend'], 60, side)                 # legs bent

    def test_getups_end_on_our_standing_pose(self):
        for name in GETUPS:
            last = self.poses(name)[-1]
            for j in ('Pelvis', 'Head', 'LeftHand', 'RightHand', 'LeftFoot', 'RightFoot'):
                self.assertLess(rig.vlen(rig.vsub(last.pos(j), self.stand.pos(j))), 0.02, '%s %s' % (name, j))

    def test_backwards_elbow_and_twisted_upper_arm_fail(self):
        p = self.stand.copy()
        a, b, c = p.pos('LeftArm'), p.pos('LeftForeArm'), p.pos('LeftHand')
        u, v = rig.vnorm(rig.vsub(b, a)), rig.vnorm(rig.vsub(c, b))
        bend = math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(u, v))))))
        p.rotate_world('LeftForeArm', rig.qaxis(rig.vnorm(rig.vcross(u, v)), -(bend + 50)))
        failures = clips.anatomy_failures(clips.anatomy(p, self.stand, self.rest))
        self.assertTrue(any(f.startswith('Left elbow bent backwards') for f in failures), failures)

        p = self.stand.copy()
        p.rotate_world('RightArm', rig.qaxis(rig.vnorm(rig.vsub(p.pos('RightForeArm'), p.pos('RightArm'))), 120))
        failures = clips.anatomy_failures(clips.anatomy(p, self.stand, self.rest))
        self.assertTrue(any(f.startswith('RightArm twist') for f in failures), failures)

    def test_head_turned_about_a_world_axis_on_a_lying_body_fails(self):
        p = self.stand.copy()
        p.rotate_world('Pelvis', rig.qaxis(clips.X, -89))      # on its back
        p.rotate_world('Head', rig.qaxis(clips.Y, 60))         # world up: a roll for a body on its back
        failures = clips.anatomy_failures(clips.anatomy(p, self.stand, self.rest))
        self.assertTrue(any(f.startswith('head roll') for f in failures), failures)


if __name__ == '__main__':
    unittest.main()
