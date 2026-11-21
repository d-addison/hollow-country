"""Offline packaging contracts only; never launch a native executable."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.release import compile_gate, release, ship_inputs
from tools.package import pbo


class ShipInputsTests(unittest.TestCase):
    def test_release_uses_shared_catalogue(self):
        # Identity ensures the gate reads the release's own catalogue, not a snapshot.
        self.assertIs(release.ship_inputs.signing_inputs, ship_inputs.signing_inputs)
        self.assertIn('ship_inputs.signing_inputs(guard_name)',
                      Path(release.__file__).read_text())

    def test_staged_set_and_missing_future_addon(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for guard in (None, compile_gate.weapon_pack_guards.PBO_NAME):
                rows = release.ship_inputs.signing_inputs(guard)
                staged = {}
                for name, mod, _ in rows:
                    relative = f'@{mod}/addons/{name}.pbo'
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b'fixture')
                    staged[relative] = path
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    compile_gate.validate_staged_pbos(staged, guard)
                self.assertIn(f'staged_pbos={len(rows)}', output.getvalue())
                future = ('future-addon', 'HollowCountry', 'future')
                with patch.object(ship_inputs, 'signing_inputs', return_value=rows + [future]):
                    with self.assertRaisesRegex(ValueError, 'release PBOs not staged:.*future-addon'):
                        compile_gate.validate_staged_pbos(staged, guard)
                next(iter(staged.values())).unlink()
                with self.assertRaisesRegex(ValueError, 'release PBOs not staged:'):
                    compile_gate.validate_staged_pbos(staged, guard)

    def test_animation_recipe_uses_selected_tree_and_installed_input(self):
        calls = []
        tree, addons, scratch = Path('/snapshot'), Path('/installed/Addons'), Path('/scratch')
        result = ship_inputs.build_anims(tree, addons, scratch,
                                        lambda command, cwd: calls.append((command, cwd)))
        self.assertEqual(result, scratch / 'anims/addons/HollowCountryAnims.pbo')
        for script in ('build_infected_clips.py', 'build_anims_addon.py'):
            matches = [(command, cwd) for command, cwd in calls
                       if tree / 'tools/anim' / script in command]
            self.assertEqual(1, len(matches), script)
            command, cwd = matches[0]
            self.assertEqual(cwd, tree)
            self.assertEqual(command[2:], [tree / 'tools/anim' / script,
                                          '--addons', addons, '--out', scratch / 'anims'])
        self.assertEqual(calls[-1][0][-1], result)
        self.assertIn('verify', calls[-1][0])

    def test_stage_includes_adapter_without_declared_pack_and_rebuilds_anims(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / 'base.pbo'
            package.write_bytes(b'base-fixture')
            animation = root / 'animation.pbo'
            animation.write_bytes(b'animation-fixture')
            with patch.object(ship_inputs, 'build_anims', return_value=animation) as build, \
                    patch.object(compile_gate.weapon_pack_guards, 'declared', return_value=False), \
                    patch.object(pbo, 'collect_addon', return_value={}), \
                    patch.object(pbo, 'pack', return_value=b'adapter-fixture'):
                for index in range(2):
                    with contextlib.redirect_stdout(io.StringIO()):
                        inputs = compile_gate.stage_release_pbos(root, package, {}, root / 'Addons',
                                                                 root / str(index))
                    self.assertTrue(inputs['server_mod'].is_file())
                    self.assertEqual(inputs['base_extra_pbos'][0].parent,
                                     root / str(index) / '@HollowCountry/addons')
                    self.assertEqual(inputs['base_extra_pbos'][0].read_bytes(), animation.read_bytes())
                self.assertEqual(build.call_count, 2)


if __name__ == '__main__':
    unittest.main()
