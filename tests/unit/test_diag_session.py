"""Focused fake-install checks; these tests never run Windows or DayZ."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.setup import diag_session as diag
from tools.package import pbo
from tools.setup.winproc import InteropError, Result


class DiagSessionTests(unittest.TestCase):
    def setUp(self):
        lock = patch.object(diag, 'host_lock', return_value=contextlib.nullcontext())
        lock.start()
        self.addCleanup(lock.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.client = self.root / 'engine'
        self.server = self.root / 'server'
        self.workshop = self.root / 'workshop'
        self.parent = self.root / 'runtime'
        self.rows = []
        for rank, prefix in enumerate(('HollowCountry', 'HollowCountryExpansionAI')):
            source = self.repo / 'mods' / prefix
            self.put(source / 'config.cpp', ('class ' + prefix + ' {};').encode())
            self.put(source / 'scripts/4_World/example.c', b'class Example {};')
            self.put(source / 'gui/example.layout', b'Widget {}')
            self.put(source / 'data/settings.json', b'{}')
            self.put(source / 'data/lighting/preset.txt', b'lighting preset')
            self.rows.append(dict(folder='@' + prefix, publish=True, side='client', rank=rank + 1))
        self.rows.insert(0, dict(folder='@Dependency', publish=False, id='42', side='client', rank=0))
        self.put(self.workshop / '42/addons/dependency.pbo', b'dependency')
        self.put(self.client / 'DayZDiag_x64.exe', b'fake engine')
        self.put(self.client / 'steam_appid.txt', b'221100')
        self.put(self.client / 'dayz.gproj', b'GameProjectClass {}')
        self.put(self.client / 'engine.dll', b'fake dll')
        for name in ('Addons', 'dta'):
            self.put(self.client / name / 'stock.pbo', b'stock')
        mission = self.server / 'mpmissions' / diag.MISSION
        self.put(mission / 'init.c', b'void main() {}')
        self.put(mission / 'db/types.xml', b'<types/>')
        self.put(mission / 'storage_1/data/players.db', b'private persistence')
        self.put(mission / 'old.log', b'private log')
        self.manifest = patch.object(diag.workshop_sync, 'load_manifest', return_value={'mods': self.rows})
        self.manifest.start()
        self.addCleanup(self.manifest.stop)
        # Fake POSIX installation lives in a temporary dir; exercise real conversion separately.
        self.win = patch.object(diag, 'windows', side_effect=lambda path: 'D:' + str(path).replace('/', '\\'))
        self.win.start()
        self.addCleanup(self.win.stop)

    def put(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def plan(self, tag='unit', **kwargs):
        return diag.make_plan(tag, repo=self.repo, client=self.client, server=self.server,
                              workshop=self.workshop, parent=self.parent, **kwargs)

    def stage(self, plan):
        with patch.object(diag, 'guard_idle') as idle, patch(
                'tools.setup.friend_bundle.repo_profile_sources', return_value={'HollowCountry/settings.json': b'{}'}):
            diag.stage(plan)
        idle.assert_called_once_with(plan.runtime)

    def test_default_plan_writes_nothing_and_never_calls_interop(self):
        plan = self.plan()
        with patch.object(diag, 'make_plan', return_value=plan), patch.object(diag.winproc, 'run') as run:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(diag.main([]), 0)
            run.assert_not_called()
        self.assertFalse(plan.runtime.exists())
        self.assertIn('PLAN ONLY', output.getvalue())

    def test_manifest_order_sides_and_single_pair(self):
        self.rows.insert(1, dict(folder='@ServerDependency', publish=False, id='43', side='server', rank=1))
        self.put(self.workshop / '43/addons/server.pbo', b'server only')
        plan = self.plan(port=2502)
        expected = [diag.windows(self.workshop / '42')] + [
            diag.windows(plan.runtime / row['folder']) for row in self.rows if row['publish']]
        for is_server in (False, True):
            args = plan.arguments(is_server)
            self.assertIn('-mod=' + ';'.join(expected), args)
            self.assertIn('-filePatching', args)
            self.assertIn('-port=2502', args)
        self.assertTrue(any(arg.startswith('-serverMod=') for arg in plan.arguments(True)))
        self.assertFalse(any(arg.startswith('-serverMod=') for arg in plan.arguments(False)))
        script = plan.launch_script()
        self.assertEqual(script.count('=Start-Process '), 2)
        self.assertIn('Get-CimInstance', script)
        self.assertIn('WaitOne(0)', script)
        self.assertLess(script.index('Player connect enabled'), script.index('$client=Start-Process'))
        self.assertNotIn('taskkill', script.lower())
        self.assertNotIn('Stop-Process', script)
        self.assertIn('-ip=127.0.0.1', script)

    def test_without_drops_only_optional_packs(self):
        optional = sorted(diag.DIAG_OPTIONAL)[0]
        self.rows.insert(0, dict(folder=optional, publish=False, id='44', side='client', rank=0))
        self.put(self.workshop / '44/addons/pack.pbo', b'optional')
        self.assertIn(diag.windows(self.workshop / '44'), ';'.join(self.plan().mods('client')))
        plan = self.plan(without=[optional])
        self.assertEqual(plan.without, (optional,))
        self.assertNotIn(diag.windows(self.workshop / '44'), ';'.join(plan.mods('client')))
        self.assertIn(diag.windows(self.workshop / '42'), ';'.join(plan.mods('client')))
        required = next(row['folder'] for row in self.rows if row['folder'] not in diag.DIAG_OPTIONAL)
        with self.assertRaisesRegex(diag.Refused, 'optional weapon packs'):
            self.plan(without=[required])
        self.assertFalse(self.parent.exists())

    def test_core_only_loads_just_the_base_addon(self):
        plan = self.plan(core_only=True)
        self.assertEqual([item['folder'] for item in plan.items], [diag.CORE_FOLDER])
        self.assertEqual(list(plan.sources), [diag.CORE_FOLDER[1:]])
        self.assertEqual(set(plan.without), {row['folder'] for row in self.rows} - {diag.CORE_FOLDER})
        self.assertEqual(plan.arguments(False)[3], '-mod=' + diag.windows(plan.runtime / diag.CORE_FOLDER))

    def test_missing_dependency_refused_without_output_directory(self):
        (self.workshop / '42/addons').rename(self.workshop / '42/not-addons')
        with self.assertRaisesRegex(diag.Refused, 'dependency missing'):
            self.plan()
        self.assertFalse(self.parent.exists())

    def test_tag_port_and_symlink_refusals(self):
        for tag in ('../friend-local-1', 'a;b', 'a\n', 'x' * 41, '1' * 17):
            with self.subTest(tag=repr(tag)), self.assertRaises(diag.Refused):
                self.plan(tag)
        for port in (0, 65532):
            with self.assertRaises(diag.Refused):
                self.plan(port=port)
        self.parent.symlink_to(self.client, target_is_directory=True)
        with self.assertRaises(diag.Refused):
            self.plan()

    def test_stage_copies_loose_sources_and_only_config_in_bootstrap(self):
        plan = self.plan()
        self.stage(plan)
        for prefix, files in plan.sources.items():
            for rel, source in files.items():
                self.assertEqual((plan.runtime / prefix / rel).read_bytes(), source.read_bytes())
            bootstrap = plan.runtime / ('@' + prefix) / 'addons' / (prefix.lower() + '.pbo')
            parsed = pbo.parse(bootstrap.read_bytes(), prefixes=(prefix,))
            self.assertEqual(parsed, (prefix, {'config.cpp': files['config.cpp'].read_bytes()}))
        cfg = (plan.runtime / 'serverDZ.cfg').read_text()
        for setting in ('maxPlayers=6;', 'instanceId=1;', 'shardId="hcdia1";', 'BattlEye=0;', 'verifySignatures=0;', 'allowFilePatching=1;'):
            self.assertIn(setting, cfg)
        staged = plan.runtime / 'mpmissions' / diag.MISSION
        self.assertTrue((staged / 'db/types.xml').is_file())
        self.assertFalse((staged / 'storage_1').exists())
        self.assertFalse((staged / 'old.log').exists())
        self.assertTrue((plan.runtime / 'profiles/server/HollowCountry/settings.json').is_file())
        self.assertFalse(any((plan.runtime / 'profiles/client').iterdir()))
        self.assertEqual((self.workshop / '42/addons/dependency.pbo').read_bytes(), b'dependency')
        with self.assertRaises(FileExistsError):
            self.stage(plan)

    def test_running_or_unknown_state_refuses_before_writing(self):
        for response in (Result(1, 'busy', '', 1), Result(0, '', '', 1), InteropError('unknown')):
            plan = self.plan()
            options = {'side_effect': response} if isinstance(response, Exception) else {'return_value': response}
            with patch.object(diag.winproc, 'run', **options):
                with self.assertRaises((diag.Refused, InteropError)):
                    diag.stage(plan)
            self.assertFalse(plan.runtime.exists())

    def test_idle_query_is_exact_and_not_retried(self):
        with patch.object(diag.winproc, 'run', return_value=Result(0, 'HC_DIAG_IDLE\n', '', 1)) as run:
            diag.guard_idle(self.plan().runtime)
        self.assertEqual(run.call_args.kwargs['attempts'], 1)
        self.assertIn('ReparsePoint', run.call_args.args[1][0])

    def test_refresh_updates_adds_removes_sources_without_repacking_or_profiles(self):
        plan = self.plan()
        self.stage(plan)
        prefix = next(iter(plan.sources))
        bootstrap = plan.runtime / ('@' + prefix) / 'addons' / (prefix.lower() + '.pbo')
        before = bootstrap.read_bytes()
        source = self.repo / 'mods' / prefix
        (source / 'scripts/4_World/example.c').unlink()
        self.put(source / 'scripts/4_World/new.c', b'class New {};')
        self.put(source / 'data/settings.json', b'{"new":true}')
        plan = self.plan()
        with patch.object(diag.winproc, 'run', return_value=Result(0, 'HC_DIAG_PATHS_OK', '', 1)), \
                patch.object(diag.pbo, 'pack', side_effect=AssertionError('refresh must not pack')):
            diag.refresh(plan)
        self.assertFalse((plan.runtime / prefix / 'scripts/4_World/example.c').exists())
        self.assertEqual((plan.runtime / prefix / 'scripts/4_World/new.c').read_bytes(), b'class New {};')
        self.assertEqual(before, bootstrap.read_bytes())
        self.assertEqual((plan.runtime / 'profiles/server/HollowCountry/settings.json').read_bytes(), b'{}')

    def test_refresh_refuses_config_changes_before_writes(self):
        plan = self.plan()
        self.stage(plan)
        prefix = next(iter(plan.sources))
        self.put(self.repo / 'mods' / prefix / 'config.cpp', b'class Changed {};')
        with self.assertRaisesRegex(diag.Refused, 'config.cpp changed'):
            diag.refresh(self.plan())
        self.assertNotEqual((plan.runtime / prefix / 'config.cpp').read_bytes(), b'class Changed {};')

    def test_log_filter_reuses_privacy_policy_and_bounds_lines(self):
        log = self.root / 'diag.RPT'
        self.put(log, ('noise\n[HC Ready] module=Core ready=true\n'
                       'SCRIPT (E): error at /' 'home/example/private/script.c\n'
                       "Can\'t compile World\n[HC Debug] Steam ID 12345678901234567\n"
                       '[HC Debug] Player "Sensitive Person" joined\n' +
                       '[HC Debug] ' + 'x' * 18000 + '\n[HC Debug] remaining\n').encode())
        output = '\n'.join(diag.log_lines(log))
        self.assertIn('[HC Ready]', output)
        self.assertIn('SCRIPT (E)', output)
        self.assertIn('~/private/script.c', output)
        self.assertIn("Can't compile", output)
        for private in ('Sensitive Person', '12345678901234567', '/home/example', 'noise', 'x' * 100):
            self.assertNotIn(private, output)
        self.assertIn('remaining', output)

    def test_key_files_not_read_or_copied(self):
        prefix = next(row['folder'][1:] for row in self.rows if row['publish'])
        self.put(self.repo / 'mods' / prefix / 'keys' / 'private.biprivatekey', b'secret')
        files = self.plan().sources[prefix]
        self.assertFalse(any('keys/' in rel or 'private' in rel for rel in files))

    def test_launch_invocation_is_one_shot(self):
        plan = self.plan()
        with patch.object(diag, 'make_plan', return_value=plan), patch.object(diag, 'stage') as stage, \
                patch.object(diag.winproc, 'run', return_value=Result(0, 'done', '', 1)) as run, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(diag.main(['--launch']), 0)
        stage.assert_called_once_with(plan)
        run.assert_called_once()
        self.assertEqual(run.call_args.kwargs['attempts'], 1)

    def test_failed_or_ambiguous_launch_never_retries_or_cleans_up(self):
        for response in (Result(1, 'failed', '', 1), InteropError('ambiguous')):
            options = {'side_effect': response} if isinstance(response, Exception) else {'return_value': response}
            with patch.object(diag, 'make_plan', return_value=self.plan()), \
                    patch.object(diag, 'stage'), patch.object(diag.winproc, 'run', **options) as run, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(diag.main(['--launch']), 2)
            run.assert_called_once()
            self.assertEqual(run.call_args.kwargs['attempts'], 1)

    def test_refresh_refuses_receipt_traversal_and_hardlinked_outputs(self):
        plan = self.plan()
        self.stage(plan)
        prefix = next(iter(plan.sources))
        marker = plan.runtime / diag.MARKER
        original = marker.read_text()
        receipt = json.loads(original)
        receipt['files'][prefix].append('../outside.c')
        marker.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(diag.Refused, 'receipt'):
            diag.refresh(plan)
        marker.write_text(original)
        target = plan.runtime / prefix / 'config.cpp'
        (plan.runtime / 'outside-hardlink').hardlink_to(target)
        with patch.object(diag.winproc, 'run', return_value=Result(0, 'HC_DIAG_PATHS_OK', '', 1)):
            with self.assertRaisesRegex(diag.Refused, 'hard-linked'):
                diag.refresh(plan)

    def test_source_symlink_refused_before_reading(self):
        prefix = next(row['folder'][1:] for row in self.rows if row['publish'])
        source = self.repo / 'mods' / prefix
        (source / 'data/redirect.json').symlink_to(self.workshop / '42/addons/dependency.pbo')
        with self.assertRaisesRegex(diag.Refused, 'linked'):
            self.plan()

    def test_errors_never_echo_raw_interop_or_home_paths(self):
        with patch.object(diag, 'make_plan', side_effect=OSError('/' 'home/example/password-secret')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(diag.main([]), 2)
        self.assertNotIn('example', output.getvalue())
        self.assertNotIn('password-secret', output.getvalue())

    def test_windows_path_conversion_rejects_injection(self):
        self.win.stop()
        self.assertEqual(diag.windows(Path('/mnt/d/Folder With Space/session')), r'D:\Folder With Space\session')
        for path in ('/tmp/session', '/mnt/d/bad;injection', '/mnt/d/bad"arg', '/mnt/d/bad\narg'):
            with self.assertRaises(diag.Refused):
                diag.windows(Path(path))


if __name__ == '__main__':
    unittest.main()
