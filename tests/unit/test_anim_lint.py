"""anim_lint rules on the repository config plus synthetic BVH/SET6 inputs; no game data."""
import contextlib
import io
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.anim import anm, rig
from tools.validate import anim_lint, preland

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/anim/synthetic_walk.bvh'
BODY = ('Pelvis', 'Spine', 'Spine2', 'Spine3', 'Neck', 'Head', 'LeftArm', 'LeftForeArm', 'LeftHand',
        'RightArm', 'RightForeArm', 'RightHand', 'LeftUpLeg', 'LeftLeg', 'LeftFoot',
        'RightUpLeg', 'RightLeg', 'RightFoot')
RIG = ['Scene_Root', *rig.ROOT_EXTRAS, *BODY, *rig.TAIL_EXTRAS]


def codes(rows):
    return sorted({row.split()[0] for row in rows})


def clip(fps=30, frames=30, names=RIG, mutate=None):
    out = anm.Anim(fps=fps, frames=frames)
    for name in names:
        bone = anm.Bone(name)
        for f in range(frames):
            bone.t.frames.append(f)
            bone.t.values.append((0.0, 0.9 if name == 'Pelvis' else 0.0, 0.0))
            bone.q.frames.append(f)
            bone.q.values.append(rig.IDENTITY)
        out.bones.append(bone)
    if mutate:
        mutate(out)
    return out


class Files:
    def __init__(self, test):
        self.dir = tempfile.TemporaryDirectory()
        test.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)

    def anm(self, name, data):
        path = self.root / name
        path.write_bytes(anm.write(data) if not isinstance(data, bytes) else data)
        return path

    def text(self, name, text):
        path = self.root / name
        path.write_text(text)
        return path


class ConfigTests(unittest.TestCase):
    def test_repository_config_and_clip_names_pass_offline(self):
        rows, notes = anim_lint.run([])
        self.assertEqual([], rows)
        self.assertTrue(any('not run' in n and 'unavailable' not in n and 'skip' not in n.lower() for n in notes))

    def test_parser_reads_the_real_tree(self):
        tree = anim_lint.parse_config(anim_lint.CONFIG.read_text(encoding='utf-8'))
        sitter = tree.child('CfgVehicles').child('HC_ZmbM_Sitter')
        self.assertEqual('ZmbM_HermitSkinny_Beige', sitter.parent)
        self.assertEqual('"hermit_newbindpose.xob"', sitter.child('enfanimsys').fields['skeletonName'])
        for bad in ('class A {', 'class A { x };', 'class'):
            with self.assertRaises((ValueError, IndexError)):
                anim_lint.parse_config(bad)

    def lint(self, mutate):
        text = mutate(anim_lint.CONFIG.read_text(encoding='utf-8'))
        files = Files(self)
        path = files.text('config.cpp', text)
        rows, _ = anim_lint.run([], config=path)
        return rows

    def test_female_class_on_another_skeleton_is_flagged(self):
        marker = 'class HC_ZmbF_Feeder_ZmbF_BlueCollarFat_Green'
        rows = self.lint(lambda t: t.replace(
            t[t.index(marker):].split('meshObject = "dz\\characters\\zombies\\z_hermit_m.xob"', 1)[0] +
            'meshObject = "dz\\characters\\zombies\\z_hermit_m.xob"',
            t[t.index(marker):].split('meshObject = "dz\\characters\\zombies\\z_hermit_m.xob"', 1)[0] +
            'meshObject = "dz\\characters\\zombies\\z_hermit_f.xob"', 1))
        self.assertIn('HC-A050', codes(rows))
        self.assertTrue(any('HC_ZmbF_Feeder_ZmbF_BlueCollarFat_Green meshObject' in r for r in rows))

    def test_prefix_and_path_rules(self):
        rows = self.lint(lambda t: t.replace('class HC_ZmbM_Sitter:', 'class ZmbM_Sitter:', 1))
        self.assertTrue(any('defined outside the HC_ prefix' in r for r in rows))
        rows = self.lint(lambda t: t.replace('graphname = "HollowCountryAnims\\anims', 'graphname = "DZ\\anims', 1))
        self.assertTrue(any('graphname is outside' in r for r in rows))
        rows = self.lint(lambda t: t.replace('startnode = "HCMasterControl"', 'startnode = "MasterControl"', 1))
        self.assertTrue(any('startnode' in r for r in rows))
        rows = self.lint(lambda t: t.replace('units[] = {"HC_ZmbM_Sitter"', 'units[] = {"ZmbM_Sitter"', 1))
        self.assertTrue(any('CfgPatches unit' in r for r in rows))
        rows = self.lint(lambda t: t.replace('dir = "HollowCountryAnims"', 'dir = "Other"', 1))
        self.assertTrue(any('CfgMods dir' in r for r in rows))
        rows = self.lint(lambda t: t.replace('class HollowCountryAnims\n    {\n        units', 'class Other\n    {\n        units', 1))
        self.assertTrue(any('CfgPatches must define' in r for r in rows))
        self.assertTrue(self.lint(lambda t: t + '\nclass broken {'))

    def test_stock_comparison(self):
        ours = {'HC_ZmbM_Sitter': {'meshObject': anim_lint.MESH_ALLOWED, 'skeletonName': anim_lint.SKELETON_NAME}}
        stock = {c: dict(ours['HC_ZmbM_Sitter']) for c in ('ZombieBase', 'ZombieMaleBase', 'ZombieFemaleBase')}
        findings = anim_lint.Findings()
        anim_lint.lint_stock_parity(ours, stock, findings)
        self.assertEqual([], findings.rows)
        stock['ZombieFemaleBase']['meshObject'] = 'dz\\characters\\zombies\\z_hermit_f.xob'
        del stock['ZombieMaleBase']
        anim_lint.lint_stock_parity(ours, stock, findings)
        self.assertEqual(2, len(findings.rows))
        self.assertEqual(['HC-A050'], codes(findings.rows))

    def test_require_installed_fails_without_addons(self):
        rows, notes = anim_lint.run([], require_installed=True)
        self.assertEqual(['HC-A050'], codes(rows))
        with tempfile.TemporaryDirectory() as folder:
            rows, _ = anim_lint.run([], addons=Path(folder))
            self.assertEqual(['HC-A050'], codes(rows))
            self.assertIn('cannot be read', rows[0])


class BvhTests(unittest.TestCase):
    def check(self, text, name='hc_walk.bvh', **kwargs):
        path = Files(self).text(name, text)
        return anim_lint.run([path], **kwargs)[0]

    def test_fixture_is_clean_apart_from_the_name_rule(self):
        self.assertEqual([], anim_lint.run([FIXTURE], name_rule=False)[0])
        rows = anim_lint.run([FIXTURE])[0]
        self.assertEqual(['HC-A001'], codes(rows))
        self.assertIn('tests/fixtures/anim/synthetic_walk.bvh', rows[0])

    def test_frame_rate_and_length(self):
        text = FIXTURE.read_text()
        self.assertIn('HC-A010', codes(self.check(text.replace('Frame Time: 0.03333333333333333', 'Frame Time: 0.5'))))
        with mock.patch.object(anim_lint, 'MAX_SECONDS', 0.05):
            self.assertIn('HC-A010', codes(self.check(text)))

    def test_missing_or_unknown_bones(self):
        text = FIXTURE.read_text().replace('LeftHand', 'LeftPalm')
        rows = self.check(text)
        self.assertEqual(['HC-A020'], codes(rows))
        self.assertIn('skeleton: map.required_bone:LeftHand', rows[0])
        self.assertIn('HC-A020', codes(self.check('not a bvh')))

    def test_exact_rig_bone_set_is_used_when_given(self):
        path = Files(self).text('hc_walk.bvh', FIXTURE.read_text())
        findings = anim_lint.Findings()
        anim_lint.lint_bvh(path, 'hc_walk.bvh', findings, rig_bones=[b for b in RIG if b != 'LeftHand'])
        self.assertEqual(['HC-A020'], codes(findings.rows))

    def test_root_motion_sanity(self):
        lines = FIXTURE.read_text().splitlines()
        first = next(i for i, l in enumerate(lines) if l.startswith('0 0 4 0'))
        jump = lines[:first] + [lines[first].replace('0 0 4 0', '0 0 400 0', 1)] + lines[first + 1:]
        rows = self.check('\n'.join(jump) + '\n')
        self.assertIn('HC-A030', codes(rows))
        self.assertTrue(any('jumps' in r for r in rows))
        rows = self.check(FIXTURE.read_text(), in_place=True)
        self.assertTrue(any('in-place clip travels' in r for r in rows))
        high = lines[:first] + [lines[first].replace('0 0 4 0', '0 300 4 0', 1)] + lines[first + 1:]
        self.assertTrue(any('vertical excursion' in r for r in self.check('\n'.join(high) + '\n')))

    def test_joint_speed(self):
        lines = FIXTURE.read_text().splitlines()
        first = next(i for i, l in enumerate(lines) if l.startswith('0 0 4 0'))
        spin = lines[:first] + [lines[first].replace('0 0 4 0 0 0', '0 0 4 170 0 0', 1)] + lines[first + 1:]
        self.assertTrue(any('deg/s' in r for r in self.check('\n'.join(spin) + '\n')))


class AnmTests(unittest.TestCase):
    def check(self, data, name='hc_pose_idle.anm', rig_bones=None, **kwargs):
        files = Files(self)
        findings = anim_lint.Findings()
        anim_lint.lint_anm(files.anm(name, data), name, findings, rig_bones=rig_bones, **kwargs)
        return findings.rows

    def test_clean_clip_passes_with_and_without_exact_rig(self):
        self.assertEqual([], self.check(clip()))
        self.assertEqual([], self.check(clip(), rig_bones=RIG))

    def test_naming_rate_and_length(self):
        self.assertEqual(['HC-A001'], codes(self.check(clip(), name='zA_erc_idle.anm')))
        self.assertIn('HC-A010', codes(self.check(clip(fps=5))))
        self.assertIn('HC-A010', codes(self.check(clip(fps=30, frames=700))))
        self.assertIn('HC-A010', codes(self.check(clip(frames=1))))

    def test_bone_set(self):
        short = [n for n in RIG if n != 'LeftHand']
        self.assertEqual(['HC-A020'], codes(self.check(clip(names=short))))
        self.assertEqual(['HC-A020'], codes(self.check(clip(), rig_bones=short)))
        rows = self.check(clip(names=RIG + ['vanilla clip']))
        self.assertEqual(['HC-A020'], codes(rows))
        self.assertIn('HC-A020', codes(self.check(b'FORMxxxx')))

    def test_key_and_value_sanity(self):
        def bad_quat(c):
            c.bone('Head').q.values[3] = (0.0, 0.0, 0.0, 3.0)
        self.assertTrue(any('unit quaternion' in r for r in self.check(clip(mutate=bad_quat))))

        def bad_keys(c):
            c.bone('Head').q.frames[4] = 2
        self.assertTrue(any('keys out of range' in r for r in self.check(clip(mutate=bad_keys))))

    def test_root_motion(self):
        def move(c):
            c.bone('EntityPosition').t.values[5] = (0.0, 0.0, 0.5)
        self.assertTrue(any('EntityPosition carries root motion' in r for r in self.check(clip(mutate=move))))
        self.assertEqual([], self.check(clip(mutate=move), allow_root_motion=True))

        def teleport(c):
            c.bone('Pelvis').t.values[5] = (0.0, 0.9, 3.0)
        self.assertTrue(any('pelvis moves' in r for r in self.check(clip(mutate=teleport))))

    def test_joint_speed(self):
        def flip(c):
            c.bone('Head').q.values[3] = rig.qaxis((0, 1, 0), 120)
        self.assertTrue(any('deg/s' in r for r in self.check(clip(mutate=flip))))


class DriverTests(unittest.TestCase):
    def test_selection_of_changed_files(self):
        self.assertIsNone(anim_lint.changed_inputs(['mods/HollowCountry/config.cpp', 'docs/x.md']))
        self.assertIsNone(anim_lint.changed_inputs(['tests/fixtures/anim/synthetic_walk.bvh']))
        self.assertEqual([], anim_lint.changed_inputs(['tools/anim/retarget.py']))
        self.assertEqual([], anim_lint.changed_inputs(['mods/HollowCountryAnims/config.cpp']))
        self.assertEqual([], anim_lint.changed_inputs(['assets_src/anim/gone.bvh']))

    def test_main_output_and_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(0, anim_lint.main([]))
        self.assertIn('anim_lint: pass files=0 findings=0', out.getvalue())
        files = Files(self)
        path = files.text('notes.txt', 'x')
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(1, anim_lint.main([str(path)]))
        self.assertNotIn(str(files.root), out.getvalue())
        self.assertIn('anim_lint: FAIL', out.getvalue())


class PrelandHookTests(unittest.TestCase):
    def args(self, **kwargs):
        base = dict(addons=Path('/nonexistent-addons'), strict=False)
        base.update(kwargs)
        return mock.Mock(**base)

    def step(self, paths, result=(0, ''), **kwargs):
        with mock.patch.object(preland, 'run_check', return_value=preland.CheckResult(*result)) as run, \
                contextlib.redirect_stdout(io.StringIO()):
            return preland.anim_lint_step(self.args(**kwargs), paths), run

    def test_runs_only_for_changed_animation_files(self):
        self.assertIsNone(self.step(None)[0][0] if False else preland.anim_lint_step(self.args(), None))
        for paths in ([], ['docs/note.md'], ['mods/HollowCountry/config.cpp']):
            row, run = self.step(paths)
            self.assertIsNone(row)
            run.assert_not_called()
        row, run = self.step(['tools/anim/ik_polish.py'])
        self.assertEqual(('anim_lint', 'pass', 'changed files'), row[0])
        self.assertEqual('tools.validate.anim_lint', run.call_args[0][0])
        self.assertEqual([], run.call_args[0][1])

    def test_failure_and_missing_installed_input_are_visible(self):
        row, _ = self.step(['tools/anim/ik_polish.py'], result=(1, 'HC-A020 x'))
        self.assertEqual(('FAIL (1)', True, False), (row[0][1], row[1], row[2]))
        row, _ = self.step(['tools/anim/ik_polish.py'],
                           result=(0, 'NOTE female stock comparison and exact rig bone set not run (no installed Addons)'))
        self.assertEqual(('pass (stock comparison not run)', False, True), (row[0][1], row[1], row[2]))
        row, run = self.step(['tools/anim/ik_polish.py'], strict=True)
        self.assertEqual(['--require-installed'], run.call_args[0][1])

    def test_installed_addons_are_passed_through(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'x.pbo').write_bytes(b'')
            _, run = self.step(['tools/anim/ik_polish.py'], addons=Path(folder))
        self.assertEqual(['--addons', folder], run.call_args[0][1])


if __name__ == '__main__':
    unittest.main()
