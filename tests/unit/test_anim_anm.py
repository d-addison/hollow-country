"""Hollow Country animation pipeline: .anm codec, authored sit clip, graph build and addon sources.

Synthetic fixtures are explicit and hand-written. Tests that need the installed game read it
from DAYZ_ADDONS (default: the local DayZServer Addons folder) and are skipped when it is absent.
Nothing here is DayZ runtime evidence: the engine has not played any of these clips yet.
"""
import os
from pathlib import Path
import re
import struct
import unittest

from tools.anim import anm, rig
from tools.anim import build_infected_clips as clips
from tools.anim import build_anims_addon as addon

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / 'mods' / 'HollowCountryAnims'
ADDONS_DIR = os.environ.get('DAYZ_ADDONS', '/mnt/d/SteamLibrary/steamapps/common/DayZServer/Addons')
HAVE_GAME = all(os.path.isfile(os.path.join(ADDONS_DIR, p)) for p in (rig.CLIP_PBO, rig.WORKSPACE_PBO))


def _synthetic():
    a = anm.Anim(fps=30, frames=3)
    root = anm.Bone('Scene_Root')
    root.t = anm.Track(3, [0], [(0.0, 0.0, 0.0)])
    root.q = anm.Track(4, [0], [(0.0, 0.0, 0.0, 1.0)])
    pelvis = anm.Bone('Pelvis')
    pelvis.t = anm.Track(3, [0, 1, 2], [(0.0, 1.0, 0.0), (0.0, 0.9, 0.1), (0.0, 0.8, 0.2)])
    pelvis.q = anm.Track(4, [0, 2], [(0.5, 0.5, -0.5, -0.5), (0.0, 0.0, 0.0, 1.0)])
    a.bones = [root, pelvis]
    return a


class AnmCodec(unittest.TestCase):
    def test_synthetic_roundtrip_layout_and_values(self):
        blob = anm.write(_synthetic())
        self.assertEqual(blob[:4], b'FORM')
        self.assertEqual(blob[8:16], b'ANIMSET6')
        self.assertEqual(struct.unpack('>I', blob[4:8])[0], len(blob) - 8)
        self.assertEqual(blob[20:28], b'FPS\0\0\0\0\x04')
        back = anm.read(blob)
        self.assertEqual((back.fps, back.frames, [b.name for b in back.bones]), (30, 3, ['Scene_Root', 'Pelvis']))
        p = back.bone('Pelvis')
        self.assertEqual(p.t.frames, [0, 1, 2])
        self.assertEqual(p.q.frames, [0, 2])
        for got, want in zip(p.t.values, [(0.0, 1.0, 0.0), (0.0, 0.9, 0.1), (0.0, 0.8, 0.2)]):
            for g, w in zip(got, want):
                self.assertAlmostEqual(g, w, places=4)
        self.assertEqual(anm.write(back), blob)   # re-encode of a read clip is byte exact

    @unittest.skipUnless(HAVE_GAME, 'installed DayZ addons not present')
    def test_installed_set6_clips_reencode_byte_exact(self):
        from tools.audit import pbo_config as pc
        path = os.path.join(ADDONS_DIR, rig.CLIP_PBO)
        index = pc.read_pbo_index(path)
        checked = 0
        for e in index['entries']:
            if not e['name'].lower().endswith('.anm'):
                continue
            data = pc.read_member(path, index, e['name'], max_bytes=8 << 20)
            if data[12:16] != b'SET6':
                continue
            self.assertEqual(anm.write(anm.read(data)), data, e['name'])
            checked += 1
        self.assertGreater(checked, 200)


@unittest.skipUnless(HAVE_GAME, 'installed DayZ addons not present')
class AuthoredClips(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parents, cls.ref = rig.load_reference(ADDONS_DIR)
        cls.built = clips.build_all(cls.parents, cls.ref)

    def test_sit_idle_is_an_in_place_closed_loop_on_the_ground(self):
        sit = self.built['hc_sit_wall_idle']
        self.assertEqual([b.name for b in sit.bones], [b.name for b in self.ref.bones])
        self.assertEqual(sit.fps, 30)
        self.assertGreaterEqual(sit.frames, 90)
        ep = sit.bone('EntityPosition')
        for v in ep.t.values:
            self.assertAlmostEqual(rig.vlen(v), 0.0, places=4)        # no root motion
        for b in sit.bones:
            for tr in (b.t, b.q):
                if len(tr.values) > 1:
                    for x, y in zip(tr.values[0], tr.values[-1]):
                        self.assertAlmostEqual(x, y, places=3, msg=b.name)  # loop closes
        for f in (0, sit.frames // 2):
            pose = rig.pose_from_clip(self.parents, sit, f)
            self.assertLess(pose.pos('Pelvis')[1], 0.35)
            self.assertGreater(pose.pos('Head')[1], 0.75)
            self.assertLess(pose.pos('Spine3')[2], pose.pos('LeftLeg')[2])   # back behind the knees
            for foot in ('LeftFoot', 'RightFoot', 'LeftToeBase', 'RightToeBase'):
                self.assertGreater(pose.pos(foot)[1], -0.03, foot)

    def test_getup_starts_seated_and_ends_on_the_standing_reference(self):
        up = self.built['hc_sit_wall_getup']
        first = rig.pose_from_clip(self.parents, up, 0)
        last = rig.pose_from_clip(self.parents, up, up.frames - 1)
        stand = rig.pose_from_clip(self.parents, self.ref, 0)
        self.assertLess(first.pos('Pelvis')[1], 0.35)
        for bone in ('Pelvis', 'Head', 'LeftHand', 'RightFoot'):
            self.assertLess(rig.vlen(rig.vsub(last.pos(bone), stand.pos(bone))), 0.02, bone)
        ep = up.bone('EntityPosition')
        for v in ep.t.values:
            self.assertAlmostEqual(rig.vlen(v), 0.0, places=4)

    def test_written_clips_read_back(self):
        for name, clip in self.built.items():
            back = anm.read(anm.write(clip))
            self.assertEqual(back.frames, clip.frames, name)


VANILLA_AGR = '''AnimSrcGraph {
 AnimSetTemplate "{0000000000000001}DZ/anims/workspaces/infected/infected_main/infected.ast"
 AnimSyncTable "{0000000000000002}DZ/anims/workspaces/infected/synctable.asy"
 ControlTemplate AnimSrcGCT "{0000000000000003}" {
  Variables {
   AnimSrcGCTVarFloat MovementSpeed {
    DefaultValue 0
   }
  }
  Commands {
   AnimSrcGCTCmd CMD_DEATH {
    Synchronized 1
   }
  }
 }
 Debug AnimSrcGD "{0000000000000003}" {
  DebugControlGroups {
   AnimSrcDebugCtlGroup "Synthetic debug panel" {
   }
  }
 }
 GraphFilesResourceNames {
  "{0000000000000004}DZ/anims/workspaces/infected/infected_main/Locomotion.agf"
 }
 DefaultRunNode "MasterControl"
}
'''
VANILLA_AW = '''BaseSource "{0000000000000007}DZ/anims/workspaces/infected/infected_main/infected.aw" {
 AnimSetTemplate "{0000000000000001}DZ/anims/workspaces/infected/infected_main/infected.ast"
 AnimSetInstances {
  "{0000000000000008}DZ/anims/workspaces/infected/infected_main/infected_main.asi"
 }
}
'''


class GraphBuild(unittest.TestCase):
    def setUp(self):
        self.files = addon.build_graph(VANILLA_AGR, VANILLA_AW)

    def test_graph_declares_the_interface_and_references_vanilla_by_path(self):
        self.assertEqual(sorted(self.files), ['anims/infected/hc_infected.agr', 'anims/infected/hc_infected.asi'])
        agr = self.files['anims/infected/hc_infected.agr']
        self.assertIn('"{0000000000000001}DZ/anims/workspaces/infected/infected_main/infected.ast"', agr)
        self.assertIn('DZ/anims/workspaces/infected/synctable.asy', agr)
        self.assertIn('DZ/anims/workspaces/infected/infected_main/Locomotion.agf', agr)
        self.assertIn('HollowCountryAnims/anims/infected/hc_poses.agf', agr)
        self.assertEqual(agr.count('AnimSrcGCTVarFloat MovementSpeed'), 1)
        self.assertEqual(agr.count('AnimSrcGCTCmd CMD_DEATH'), 1)
        self.assertRegex(agr, r'AnimSrcGCTCmd CMD_HC_POSE \{\s*Synchronized 1')
        self.assertIn('AnimSrcGCTVarInt HCPose', agr)
        self.assertIn('DefaultRunNode "HCMasterControl"', agr)
        self.assertNotIn('Synthetic debug panel', agr)
        self.assertNotIn('{0000000000000003}', agr)

    def test_instance_inherits_vanilla_and_holds_only_our_lines(self):
        asi = self.files['anims/infected/hc_infected.asi']
        self.assertIn('Template "{0000000000000001}DZ/anims/workspaces/infected/infected_main/infected.ast"', asi)
        self.assertRegex(asi, r'ParentTemplates \{\s*"\{0000000000000008\}DZ/anims/workspaces/infected/'
                              r'infected_main/infected_main.asi"\s*\}')
        lines = re.findall(r'AnimSetInstanceSource_Line "([^"]+)" \{\s*Resource "([^"]+)"', asi)
        self.assertEqual([slot for slot, _ in lines], [slot for slot, _ in addon.CLIPS])
        for _, res in lines:
            self.assertIn('HollowCountryAnims/anims/infected/clips/', res)
        self.assertNotIn('DZ/anims/anm', asi)

    @unittest.skipUnless(HAVE_GAME, 'installed DayZ Addons not found')
    def test_shipped_members_carry_no_vanilla_graph_content(self):
        import tempfile
        parents, ref = rig.load_reference(ADDONS_DIR)
        with tempfile.TemporaryDirectory() as tmp:
            for name, clip in clips.build_all(parents, ref).items():
                with open(os.path.join(tmp, name + '.anm'), 'wb') as h:
                    h.write(anm.write(clip))
            files = addon.collect(ADDONS_DIR, tmp)
        self.assertEqual(sorted(n for n in files if n.startswith('anims/infected/hc_infected')),
                         ['anims/infected/hc_infected.agr', 'anims/infected/hc_infected.asi'])
        agr_v, aw_v = addon.read_vanilla(ADDONS_DIR)
        ast_v, asi_v, sheets_v = addon.read_vanilla_slot_sources(ADDONS_DIR)
        # Our slots are dead vanilla slots: in the template, filled by the vanilla instance,
        # referenced by no vanilla sheet, so overriding them changes no vanilla state.
        for slot, _ in addon.CLIPS:
            group, column, anim = slot.split('.')
            self.assertRegex(ast_v, r'Name "%s"\s*Animations \{[^}]*"%s"[^}]*\}\s*Columns \{[^}]*"%s"'
                             % (group, re.escape(anim), column))
            self.assertIn('"%s"' % slot, asi_v)
            self.assertNotIn(anim, sheets_v)
        vanilla = set()
        for text in (agr_v, aw_v, ast_v, asi_v, sheets_v):
            vanilla |= {ln.strip() for ln in text.splitlines()}
        interface = {ln.strip() for ln in addon.vanilla_interface(agr_v).splitlines()}
        # format keywords with no name, and the names of the two slots our lines fill
        interface |= {'AnimSetInstanceSource_Line "%s" {' % slot for slot, _ in addon.CLIPS}
        grammar = r'^([A-Za-z]+ \{|[{}])$'
        for member in ('anims/infected/hc_infected.agr', 'anims/infected/hc_infected.asi'):
            text = files[member].decode('utf-8')
            self.assertNotIn('DZ/anims/anm', text)
            self.assertNotIn('AnimSrcDebug', text)
            for ln in text.splitlines():
                s = ln.strip()
                if s in vanilla and s not in interface and not re.match(grammar, s):
                    # besides the ControlTemplate interface, only resource references by path may match
                    self.assertRegex(s, r'^((AnimSetTemplate|AnimSyncTable|Template) )?"\{[0-9A-F]{16}\}DZ/',
                                     '%s: vanilla line %r' % (member, s))

    def test_pose_sheet_returns_to_vanilla_on_engine_commands(self):
        sheet = (ADDON / 'anims' / 'infected' / 'hc_poses.agf').read_text()
        self.assertIn('AnimSrcNodeStateMachine HCMasterControl', sheet)
        self.assertIn('Child "MasterControl"', sheet)
        for slot, _ in addon.CLIPS:
            self.assertIn('Source "%s"' % slot, sheet)
        for cmd in ('CMD_DEATH', 'CMD_HIT_LIGHT', 'CMD_HIT_HEAVY', 'CMD_CRAWL', 'CMD_ATTACK', 'CMD_VAULT'):
            self.assertIn('IsCommand(%s)' % cmd, sheet)
        self.assertIn('GetCommandI(CMD_HC_POSE) == 0', sheet)
        for node in re.findall(r'Child "([^"]+)"', sheet):
            if node != 'MasterControl':
                self.assertRegex(sheet, r'AnimSrcNode\w+ "?%s"? \{' % re.escape(node))


class AddonSources(unittest.TestCase):
    def test_config_repoints_only_the_new_class(self):
        cfg = (ADDON / 'config.cpp').read_text()
        self.assertIn('class HC_ZmbM_Sitter: ZmbM_HermitSkinny_Beige', cfg)
        self.assertIn('graphname = "HollowCountryAnims\\anims\\infected\\hc_infected.agr";', cfg)
        self.assertIn('defaultinstance = "HollowCountryAnims\\anims\\infected\\hc_infected.asi";', cfg)
        self.assertIn('startnode = "HCMasterControl";', cfg)
        self.assertIn('skeletonName = "hermit_newbindpose.xob";', cfg)
        self.assertNotRegex(cfg, r'class ZombieBase\b[^;]')
        self.assertEqual(cfg.count('class enfanimsys'), 1)

    def test_repository_holds_no_game_derived_files(self):
        for p in ADDON.rglob('*'):
            if p.is_file():
                self.assertIn(p.suffix, ('.cpp', '.c', '.agf', ''), str(p))

    def test_hook_drives_the_pose_through_a_synchronized_command(self):
        src = (ADDON / 'scripts' / '4_World' / 'HCPoseInfected.c').read_text()
        self.assertIn('class HC_ZmbM_Sitter extends ZmbM_HermitSkinny_Base', src)
        self.assertIn('BindCommand("CMD_HC_POSE")', src)
        self.assertIn('PreAnim_CallCommand', src)
        self.assertIn('override bool ModCommandHandlerBefore', src)
        self.assertIn('MAX_POSED', src)
        self.assertIn('override void EEInit()', src)   # sits by itself when spawned by class name


if __name__ == '__main__':
    unittest.main()
