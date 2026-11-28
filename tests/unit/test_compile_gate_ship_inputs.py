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
        self.assertIn('ship_inputs.signing_inputs(guard_name, compat_names)',
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

    def test_compat_pbos_join_catalogue_and_staging_is_validated(self):
        compat = (ship_inputs.COMPAT_STEM + '.pbo',
                  ship_inputs.COMPAT_STEM + '_a.pbo')
        stems = {Path(name).stem for name in compat}
        base = {name for name, _, _ in ship_inputs.signing_inputs()}
        rows = ship_inputs.signing_inputs(None, compat)
        self.assertEqual({name for name, _, _ in rows} - base, stems)
        self.assertTrue(all(mod == 'HollowCountryExpansionAI'
                            for name, mod, _ in rows if name in stems))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = {}
            for name, mod, _ in rows:
                relative = f'@{mod}/addons/{name}.pbo'
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'fixture')
                staged[relative] = path
            with contextlib.redirect_stdout(io.StringIO()):
                compile_gate.validate_staged_pbos(staged, None, compat)
            staged = {r: p for r, p in staged.items() if not r.endswith('_a.pbo')}
            with self.assertRaisesRegex(ValueError, 'release PBOs not staged:'):
                compile_gate.validate_staged_pbos(staged, None, compat)

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


class HCMissionInputsTests(unittest.TestCase):
    def test_exact_shipped_allowlist_and_bytes(self):
        probe = compile_gate.probe
        tree = Path(__file__).resolve().parents[2]
        files = probe.hc_mission_inputs(tree)
        self.assertEqual(set(files), pbo.MISSION_FILES)
        self.assertTrue(pbo.route_inventory(files) <= set(files))
        for name, data in files.items():
            self.assertEqual(data, (tree / 'mission/hollow-country' / name).read_bytes())
        with patch.object(probe, 'HC_MISSION_MAX_ENTRIES', 16):
            with self.assertRaisesRegex(ValueError, 'mission entry budget exceeded'):
                probe.hc_mission_inputs(tree)

    def test_missing_irregular_and_extra_source(self):
        probe = compile_gate.probe
        scratch = Path(__file__).resolve().parents[2] / '.banso'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            tree = Path(temp)
            source = tree / 'mission/hollow-country'
            source.mkdir(parents=True)
            with patch.object(pbo, 'MISSION_FILES', {'one.json'}), \
                    patch.object(pbo, 'route_inventory'):
                with self.assertRaisesRegex(ValueError, 'refused hc_mission_file_missing=one.json'):
                    probe.hc_mission_inputs(tree)
                (source / 'one.json').write_bytes(b'{}')
                (source / 'extra.json').write_bytes(b'ignored')
                self.assertEqual(probe.hc_mission_inputs(tree), {'one.json': b'{}'})
                (source / 'extra.json').unlink()
                (source / 'extra.json').symlink_to(source / 'one.json')
                with self.assertRaisesRegex(ValueError, 'hc_mission_irregular=extra.json'):
                    probe.hc_mission_inputs(tree)

    def test_prepare_only_default_and_vanilla_never_launch(self):
        scratch = Path(__file__).resolve().parents[2] / '.banso'
        scratch.mkdir(exist_ok=True)
        for vanilla in (False, True):
            with tempfile.TemporaryDirectory(dir=scratch) as temp, contextlib.ExitStack() as stack:
                root = Path(temp)
                stack.enter_context(patch.object(compile_gate.probe, 'safe', side_effect=lambda p: Path(p)))
                stack.enter_context(patch('tools.release.host_lock.host_lock',
                                          return_value=contextlib.nullcontext()))
                stack.enter_context(patch.object(compile_gate, 'source_tree',
                    return_value=contextlib.nullcontext(root)))
                stack.enter_context(patch.object(compile_gate, 'ship_config'))
                stack.enter_context(patch.object(compile_gate, 'compatibility_inputs',
                    return_value=contextlib.nullcontext({})))
                stack.enter_context(patch.object(compile_gate, 'compat_inputs',
                    return_value=contextlib.nullcontext([])))
                stack.enter_context(patch.object(pbo, 'collect_addon', return_value={}))
                stack.enter_context(patch.object(pbo, 'pack', return_value=b'fixture'))
                stage = stack.enter_context(patch.object(compile_gate, 'stage_release_pbos',
                    return_value={} if vanilla else {'hc_mission_files': {'one.json': b'{}'}}))
                launch = stack.enter_context(patch.object(compile_gate.probe, 'run'))
                stack.enter_context(patch('sys.argv', ['compile_gate', '--prepare-only',
                    '--cache', str(root / 'cache')] + (['--vanilla-mission'] if vanilla else [])))
                output = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                self.assertEqual(compile_gate.main(), 0)
                launch.assert_not_called()
                self.assertEqual(stage.call_args.kwargs['hc_mission_tree'], None if vanilla else root)
                self.assertIn('hc_mission_files=0 mode=vanilla' if vanilla else
                              'hc_mission_files=1 hc_mission_sha256=', output.getvalue())


if __name__ == '__main__':
    unittest.main()
