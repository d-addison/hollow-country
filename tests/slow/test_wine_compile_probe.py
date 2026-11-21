"""Probe log classification uses synthetic text, not engine acceptance."""
import unittest
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import os
import subprocess
import shutil
import sys
import time
import hashlib
import io
import json
from contextlib import ExitStack

from tools.setup import wine_compile_probe as probe
from tools.release import compile_gate, release, ship_inputs


class MockedWineRunTests(unittest.TestCase):
    """Real staging/report I/O; synthetic process, clock and native log frames."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.server = self.root / 'server'
        (self.server / 'mpmissions/dayzOffline.chernarusplus').mkdir(parents=True)
        (self.server / 'mpmissions/dayzOffline.chernarusplus/init.c').write_bytes(b'// synthetic')
        (self.server / 'DayZServer_x64.exe').write_bytes(b'synthetic executable, never launched')
        (self.server / 'battleye').mkdir()
        (self.server / 'battleye/BEServer_x64.dll').write_bytes(b'synthetic DLL')
        self.source = self.root / 'synthetic.pbo'
        self.source.write_bytes(probe.pbo.pack({'config.cpp': b'// synthetic addon'}))
        self.experiment = self.root / 'experiment'
        self.process = Mock(pid=123456789, returncode=None)
        self.process.poll.return_value = None
        self.now = 0

    def run_mocked(self, frames=None, probe_seconds=15, final_logs='', launch_error=None, final_mutation=None, final_skipped=None, **kwargs):
        frames = frames or (lambda now: '[HollowCountry] Server initialized; synthetic')
        native_is_file = Path.is_file

        def is_file(path):
            return True if str(path) == '/usr/lib/wine/wine64' else native_is_file(path)

        def logs(root):
            if root == self.experiment:
                if final_mutation: final_mutation()
                return final_logs, {}, final_skipped or {}
            return frames(self.now), {}, {}

        def sleep(seconds):
            self.now += seconds

        def stop(process):
            self.assertIs(process, self.process)
            process.returncode = -15
            return True

        with ExitStack() as stack:
            stack.enter_context(patch.object(Path, 'is_file', is_file))
            stack.enter_context(patch.object(probe.shutil, 'which', return_value='/synthetic/xvfb-run'))
            stack.enter_context(patch.object(probe.subprocess, 'run', return_value=Mock(returncode=1)))
            self.launch = stack.enter_context(patch.object(probe.subprocess, 'Popen', return_value=self.process,
                                                         side_effect=launch_error))
            self.stop = stack.enter_context(patch.object(probe, 'stop_group', side_effect=stop))
            stack.enter_context(patch.object(probe, 'collect_logs', side_effect=logs))
            stack.enter_context(patch.object(probe.time, 'monotonic', side_effect=lambda: self.now))
            stack.enter_context(patch.object(probe.time, 'sleep', side_effect=sleep))
            return probe.run(self.server, self.source, self.experiment, self.root / 'prefix',
                             seconds=probe_seconds, **kwargs)

    def test_final_incomplete_logs_cannot_remain_clean_smoke(self):
        report = self.run_mocked(final_skipped={
            'hidden.rpt': 'log count or byte budget exceeded'})
        self.assertEqual('log-collection-incomplete', report['status'])
        self.assertFalse(report['engine_error_observed'])
        self.assert_cleaned_report(report)

    def test_gate_packages_reach_launched_mod_folders(self):
        """Exercise the gate/probe boundary against the release's own catalogue."""
        animation = self.root / 'HollowCountryAnims.pbo'
        animation.write_bytes(probe.pbo.pack({'config.cpp': b'// synthetic animation'},
                                            prefix='HollowCountryAnims'))
        adapter = self.root / probe.SERVER_MOD_PBO
        adapter.write_bytes(probe.pbo.pack({'config.cpp': b'// synthetic adapter'},
                                          prefix=probe.SERVER_MOD_PREFIX))
        guard = self.root / compile_gate.weapon_pack_guards.PBO_NAME
        guard.write_bytes(probe.pbo.pack({'config.cpp': b'// synthetic guard'},
                                        prefix=probe.pbo.GUARD_PREFIX))
        for index, declared in enumerate((False, True)):
            self.experiment = self.root / ('catalogue-' + str(index))
            self.now = 0
            self.process.returncode = None
            inputs = {'server_mod': adapter, 'server_extra_pbos': [guard] if declared else []}
            with patch.object(ship_inputs, 'build_anims', return_value=animation), \
                    patch.object(compile_gate.weapon_pack_guards, 'declared', return_value=declared):
                inputs = compile_gate.stage_release_pbos(
                    self.root, self.source, inputs, self.root / 'Addons', self.root / ('stage-' + str(index)))
            report = self.run_mocked(**inputs)
            staged = {path.relative_to(self.experiment).as_posix(): path
                      for path in self.experiment.glob('@*/addons/*.pbo')}
            expected = {f'@{mod}/addons/{name}.pbo'.casefold()
                        for name, mod, _ in release.ship_inputs.signing_inputs(guard.name if declared else None)}
            self.assertEqual({name.casefold() for name in staged}, expected)
            self.assertEqual(report['base_extra_pbos'], {animation.name.lower(): 'HollowCountryAnims'})
            command = self.launch.call_args.args[0]
            mod_arg = next(arg for arg in command if arg.startswith('-mod='))
            for folder in {path.parent.parent for path in staged.values()}:
                self.assertIn(probe.win(folder), mod_arg)
            self.assert_cleaned_report(report)

    def test_base_companion_drift_revokes_clean_initialization(self):
        animation = self.root / 'HollowCountryAnims.pbo'
        animation.write_bytes(probe.pbo.pack({'config.cpp': b'// synthetic animation'},
                                            prefix='HollowCountryAnims'))
        staged = self.experiment / '@HollowCountry/addons' / animation.name
        report = self.run_mocked(base_extra_pbos=[animation],
                                 final_mutation=lambda: staged.write_bytes(b'changed'))
        self.assertEqual(report['status'], 'input-drift')
        self.assert_cleaned_report(report)

    def test_invalid_base_companions_fail_before_staging_or_launch(self):
        cases = (
            ('hollowcountry.pbo', self.source.read_bytes(), 'duplicate or invalid base PBO filename'),
            ('duplicate.pbo', self.source.read_bytes(), 'duplicate PBO prefix'),
            ('broken.pbo', b'not a PBO', None),
            ('animation.txt', b'not a PBO', 'duplicate or invalid base PBO filename'),
        )
        for name, data, message in cases:
            companion = self.root / name
            companion.write_bytes(data)
            with self.subTest(name=name):
                with self.assertRaises(ValueError) as error:
                    self.run_mocked(base_extra_pbos=[companion])
                if message:
                    self.assertIn(message, str(error.exception))
                self.launch.assert_not_called()
                self.assertFalse(self.experiment.exists())

    def test_base_companions_cannot_overwrite_each_other(self):
        animation = self.root / 'HollowCountryAnims.pbo'
        animation.write_bytes(probe.pbo.pack({'config.cpp': b'// synthetic animation'},
                                            prefix='HollowCountryAnims'))
        other = self.root / 'hollowcountryanims.PBO'
        other.write_bytes(probe.pbo.pack({'config.cpp': b'// synthetic other'},
                                        prefix=probe.pbo.GUARD_PREFIX))
        with self.assertRaisesRegex(ValueError, 'duplicate or invalid base PBO filename'):
            self.run_mocked(base_extra_pbos=[animation, other])
        self.launch.assert_not_called()
        self.assertFalse(self.experiment.exists())

    def test_engine_fatal_during_polling_is_distinct_from_compile_or_timeout(self):
        report=self.run_mocked(lambda now:'ENGINE    (F): Crashed')
        self.assertEqual('engine-crash',report['status'])
        self.assertTrue(report['engine_error_observed'])
        self.assertLess(self.now,15)
        self.assert_cleaned_report(report)

    def test_final_engine_fatal_revokes_completed_smoke(self):
        report=self.run_mocked(final_logs='23:42:20.007 ENGINE    (F): Crashed')
        self.assertEqual('engine-crash',report['status'])
        self.assertTrue(report['engine_error_observed'])
        self.assert_cleaned_report(report)

    def test_final_input_drift_cannot_remain_clean_smoke(self):
        targets = (
            self.experiment / '@HollowCountry/addons/hollowcountry.pbo',
            self.experiment / 'serverDZ.cfg',
            self.experiment / 'battleye/BEServer_x64.dll',
            self.server / 'DayZServer_x64.exe',
            self.server / 'mpmissions/dayzOffline.chernarusplus/init.c',
        )
        for index, target in enumerate(targets):
            self.experiment = self.root / ('wine-drift-' + str(index))
            # Rebase staged targets to this fresh experiment.
            if 'experiment' in target.parts:
                target = self.experiment.joinpath(*target.relative_to(self.root / 'experiment').parts)
            self.now = 0
            self.process.returncode = None
            report = self.run_mocked(final_mutation=lambda:
                target.write_bytes(b'SYNTHETIC changed launch input'))
            with self.subTest(target=str(target)):
                self.assertEqual('input-drift', report['status'])
                self.assert_cleaned_report(report)

    def test_final_mission_added_file_or_directory_cannot_remain_clean(self):
        for index, directory in enumerate((False, True)):
            self.experiment = self.root / ('wine-inventory-' + str(index))
            self.now = 0
            self.process.returncode = None
            def mutate():
                target = self.server / 'mpmissions/dayzOffline.chernarusplus' / ('extra-dir' if directory else 'extra.c')
                if directory:
                    target.mkdir()
                else:
                    target.write_bytes(b'// synthetic extra source')
            report = self.run_mocked(final_mutation=mutate)
            self.assertEqual('input-drift', report['status'])
            self.assert_cleaned_report(report)

    def test_final_error_is_sticky_with_incomplete_logs_and_input_drift(self):
        report = self.run_mocked(final_logs='SCRIPT (E): synthetic failure',
            final_skipped={'hidden.rpt': 'byte budget exceeded'},
            final_mutation=lambda:
                (self.experiment / 'serverDZ.cfg').write_bytes(b'SYNTHETIC drift'))
        self.assertEqual('compiler-error', report['status'])
        self.assertTrue(report['engine_error_observed'])
        self.assert_cleaned_report(report)

    def test_final_diagnostic_mission_manifest_drift_is_rejected(self):
        (self.server / 'DayZDiag_x64.exe').write_bytes(b'SYNTHETIC diagnostic')
        stock = self.server / 'mpmissions/dayzOffline.chernarusplus/init.c'
        stock.write_bytes(b'class CustomMission: MissionServer {}; Mission CreateCustomMission(string path) { return new CustomMission(); }')
        report = self.run_mocked(diagnostic=True, diagnostic_selftests=True,
            final_mutation=lambda:
                (self.experiment / 'diagnostic.chernarusplus/.hollow-country-diagnostic-mission.json').unlink())
        self.assertEqual('input-drift', report['status'])
        self.assert_cleaned_report(report)

    def test_final_seed_drift_is_rejected(self):
        seed = self.root / 'seed'
        seed.mkdir()
        (seed / 'config.json').write_bytes(b'{}')
        report = self.run_mocked(state_seed=seed,
            final_mutation=lambda:
                (self.experiment / 'profiles/HollowCountry/Infected/config.json').write_bytes(b'{"changed":true}'))
        self.assertEqual('input-drift', report['status'])
        self.assert_cleaned_report(report)

    @staticmethod
    def synthetic_stage(source, destination, **kwargs):
        destination.mkdir()
        (destination / 'init.c').write_bytes(b'// synthetic staged hook')
        return {'kind': 'synthetic-' + kwargs['purpose'] + '-staging'}

    def assert_cleaned_report(self, report):
        self.stop.assert_called_once_with(self.process)
        self.assertTrue(report['forced_stop'])
        self.assertEqual(report['launcher_exit_code'], -15)
        self.assertEqual(json.loads((self.experiment / 'compiler-report.json').read_text()), report)
        self.assertTrue(self.launch.call_args.kwargs['start_new_session'])

    def death_run(self, complete_at=2, mutate=None, slow=False, **kwargs):
        """Synthetic staging boundary; real five-case receipt validator."""
        from tools.setup import infected_death_probe as death
        from tests.slow import test_infected_death_probe as fixtures

        def prepare(source, destination, scripts, **options):
            self.assertFalse(options['diagnostic_only'])
            destination.mkdir()
            data = b'// synthetic fixed death mission, never executed'
            (destination / 'init.c').write_bytes(data)
            manifest = dict(schema=1, kind=death.KIND, cases=list(death.CASES),
                            run_id=options['run_id'], spawn_xz=[options['x'], options['z']],
                            seconds_per_case=2, impulse=[0, 0, 0], allow_observers=False,
                            execution_mode='normal-server',
                            files={'init.c': {'staged_sha256': hashlib.sha256(data).hexdigest()}})
            (destination / death.MARKER).write_text(json.dumps(manifest))
            self.death_manifest = manifest
            return manifest

        def frames(now):
            text = '[HollowCountry] Server initialized; synthetic'
            if complete_at is not None and now >= complete_at:
                receipt = fixtures.InfectedDeathProbeTests.result(self, self.death_manifest)
                if mutate:
                    mutate(receipt)
                path = self.experiment / 'profiles' / death.RESULT
                path.write_text(json.dumps(receipt))
                if slow:
                    self.now += 2
                text += '\n[HC Infected Death] COMPLETE run=' + self.death_manifest['run_id']
            return text

        with patch.object(death, 'prepare_probe', side_effect=prepare) as staged:
            # Fifteen process seconds plus ten reserved cleanup seconds.
            kwargs.setdefault('probe_seconds', 25)
            report = self.run_mocked(frames, infected_death_scripts=self.root / 'interfaces',
                                     **kwargs)
        self.death_staged = staged
        return report

    def test_death_normal_server_waits_for_five_case_receipt_and_cleanup(self):
        report = self.death_run()
        self.assertEqual(2, self.now)
        self.assertEqual('infected-death-completed', report['status'])
        self.assertTrue(report['infected_death_requested'])
        self.assertFalse(report['infected_death_timed_out'])
        self.assertTrue(report['infected_death_receipt']['authoritative_observations_complete'])
        self.assertFalse(report['infected_death_receipt']['feature_complete'])
        self.assertEqual(self.death_manifest['run_id'], report['infected_death_run_id'])
        self.assertEqual('dedicated-server', report['executable_kind'])
        self.assertIn('-mission=' + probe.win(self.experiment / 'infected-death.chernarusplus'),
                      self.launch.call_args.args[0])
        self.assertFalse(any(arg.startswith('-autotest=') for arg in self.launch.call_args.args[0]))
        self.assertEqual('pending', report['runtime_acceptance'])
        self.assert_cleaned_report(report)

    def test_death_initialization_alone_times_out_without_acceptance(self):
        report = self.death_run(complete_at=None)
        self.assertEqual('timeout', report['status'])
        self.assertTrue(report['infected_death_timed_out'])
        self.assertIsNone(report['infected_death_receipt'])
        self.assert_cleaned_report(report)

    def test_death_explicit_startup_allowance_retains_short_fixture_and_total_bound(self):
        report = self.death_run(complete_at=100, probe_seconds=180)
        self.assertEqual('infected-death-completed', report['status'])
        self.assertEqual(180, report['infected_death_outer_budget_seconds'])
        self.assertEqual(170, report['infected_death_process_budget_seconds'])
        self.assertEqual(2, report['diagnostic_mission']['seconds_per_case'])
        self.assert_cleaned_report(report)

    def test_death_missing_cleanup_rejects_complete_marker(self):
        def corrupt(receipt):
            receipt['cases'][4]['cleanup_confirmed'] = False
        report = self.death_run(mutate=corrupt)
        self.assertEqual('infected-death-failed', report['status'])
        self.assertIsNone(report['infected_death_receipt'])
        self.assert_cleaned_report(report)

    def test_death_stale_nonce_rejected_even_with_all_five_cases(self):
        report = self.death_run(mutate=lambda value: value.update(run_id='not-current'))
        self.assertEqual('infected-death-failed', report['status'])
        self.assertIsNone(report['infected_death_receipt'])
        self.assert_cleaned_report(report)

    def test_death_receipt_after_log_read_deadline_never_promotes(self):
        report = self.death_run(complete_at=14, slow=True)
        self.assertEqual('timeout', report['status'])
        self.assertTrue(report['infected_death_timed_out'])
        self.assertIsNone(report['infected_death_receipt'])
        self.assert_cleaned_report(report)

    def test_death_launcher_exit_cannot_pass_an_old_complete_marker(self):
        self.process.poll.side_effect = lambda: 0 if self.now >= 2 else None
        report = self.death_run()
        self.assertNotEqual('infected-death-completed', report['status'])
        self.assertIsNone(report['infected_death_receipt'])
        self.assert_cleaned_report(report)

    def test_death_is_one_bounded_purpose_before_staging(self):
        with self.assertRaisesRegex(ValueError, 'normal server executable'):
            self.run_mocked(infected_death_scripts=self.root / 'interfaces', diagnostic=True)
        for options in ({'group_checks': True}, {'item_compatibility_audit': True},
                        {'diagnostic': True},
                        {'diagnostic': True, 'diagnostic_selftests': True},
                        {'diagnostic': True, 'native_autotest_scripts': self.root},
                        {'probe_seconds': 181}, {'hold_seconds': 1},
                        {'state_seed': self.root}, {'settings_case': 'malformed-json'}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.run_mocked(infected_death_scripts=self.root / 'interfaces', **options)
            self.assertFalse(self.experiment.exists())

    def test_hold_starts_at_initialization_and_waits_full_requested_time(self):
        report = self.run_mocked(lambda now: '[HollowCountry] Server initialized;' if now >= 5 else '', hold_seconds=3)
        self.assertEqual(report['status'], 'initialized')
        self.assertEqual(report['hold_seconds_observed'], 3)
        self.assertEqual(self.now, 8)
        self.assert_cleaned_report(report)

    def synthetic_dependency(self, name):
        mod = self.root / 'workshop' / name
        (mod / 'addons').mkdir(parents=True)
        (mod / 'addons' / (name + '.pbo')).write_bytes(b'synthetic dependency, never parsed')
        return mod

    def test_extra_mods_load_in_order_before_hc_and_are_referenced_in_place(self):
        first, second = self.synthetic_dependency('cf'), self.synthetic_dependency('core')
        before = sorted(p.relative_to(self.root) for p in (self.root / 'workshop').rglob('*'))
        report = self.run_mocked(extra_mods=[first, second])
        mods = [arg for arg in self.launch.call_args.args[0] if arg.startswith('-mod=')]
        self.assertEqual(mods, ['-mod=' + ';'.join([probe.win(first), probe.win(second),
                                                     probe.win(self.experiment / '@HollowCountry')])])
        self.assertEqual(report['extra_mods'], [str(first), str(second)])
        self.assertEqual(sorted(p.relative_to(self.root) for p in (self.root / 'workshop').rglob('*')), before)
        self.assertFalse(any(p.name == 'cf.pbo' for p in self.experiment.rglob('*')))
        self.assertEqual(report['status'], 'initialized')
        self.assert_cleaned_report(report)

    def test_extra_mods_run_on_a_disposable_mission_copy(self):
        stock = self.server / 'mpmissions/dayzOffline.chernarusplus'
        staged = self.experiment / 'mod-stack.chernarusplus'

        def dependency_writes():
            # Dependency mods (Expansion) write their own settings/storage into the mission.
            (staged / 'expansion/settings').mkdir(parents=True)
            (staged / 'expansion/settings/AIPatrolSettings.json').write_text('{}')
            (staged / 'storage_1/expansion/entitystorage').mkdir(parents=True)
        report = self.run_mocked(extra_mods=[self.synthetic_dependency('cf')], final_mutation=dependency_writes)
        self.assertIn('-mission=' + probe.win(staged), self.launch.call_args.args[0])
        self.assertEqual((staged / 'init.c').read_bytes(), b'// synthetic')
        self.assertEqual(sorted(p.name for p in stock.iterdir()), ['init.c'])
        self.assertEqual(report['status'], 'initialized')

    def test_dependency_output_allowance_never_admits_mission_tampering(self):
        staged = self.experiment / 'mod-stack.chernarusplus'
        cases = {'changed init': lambda: (staged / 'init.c').write_bytes(b'// changed'),
                 'new other file': lambda: (staged / 'other.c').write_bytes(b'// added'),
                 'removed init': lambda: (staged / 'init.c').unlink()}
        for index, (label, mutate) in enumerate(cases.items()):
            with self.subTest(label):
                if self.experiment.exists():
                    shutil.rmtree(self.experiment)
                report = self.run_mocked(extra_mods=[self.synthetic_dependency('cf' + str(index))],
                                         final_mutation=mutate)
                self.assertEqual(report['status'], 'input-drift')

    def test_without_extra_mods_new_expansion_output_is_still_drift(self):
        mission = self.server / 'mpmissions/dayzOffline.chernarusplus'
        report = self.run_mocked(final_mutation=lambda: (mission / 'expansion').mkdir())
        self.assertEqual(report['status'], 'input-drift')

    def test_extra_mod_rejections_precede_staging(self):
        valid = self.synthetic_dependency('cf')
        no_addons = self.root / 'workshop' / 'empty'
        no_addons.mkdir(parents=True)
        cases = {'duplicate': [valid, valid], 'missing': [self.root / 'absent'],
                 'no addons': [no_addons], 'inside checkout': [Path(probe.__file__).parents[2] / 'mods']}
        for label, mods in cases.items():
            with self.subTest(label), self.assertRaises(ValueError):
                self.run_mocked(extra_mods=mods)
            self.assertFalse(self.experiment.exists())

    def test_patrol_settings_are_staged_in_the_mission_copy_and_must_survive_unchanged(self):
        override = self.root / 'patrols.json'
        override.write_text('{"m_Version": 32, "Enabled": 0, "Patrols": [], "LoadBalancingCategories": {}}')
        staged = self.experiment / 'mod-stack.chernarusplus/expansion/settings/AIPatrolSettings.json'
        report = self.run_mocked(extra_mods=[self.synthetic_dependency('cf')], expansion_patrol_settings=override)
        self.assertEqual(staged.read_bytes(), override.read_bytes())
        self.assertEqual(report['expansion_patrol_settings_sha256'], hashlib.sha256(override.read_bytes()).hexdigest())
        self.assertEqual(report['status'], 'initialized')
        self.assertFalse((self.server / 'mpmissions/dayzOffline.chernarusplus/expansion').exists())
        shutil.rmtree(self.experiment)
        # A dependency rewriting the staged override (e.g. regenerating defaults) is drift.
        report = self.run_mocked(extra_mods=[self.synthetic_dependency('core')], expansion_patrol_settings=override,
                                 final_mutation=lambda: staged.write_text('{"Enabled": 1}'))
        self.assertEqual(report['status'], 'input-drift')

    def test_patrol_settings_require_the_mod_stack_and_a_json_object(self):
        override = self.root / 'patrols.json'
        for label, text, mods in (('no mod stack', '{"Enabled": 0}', []), ('not json', '{', None),
                                  ('not an object', '[]', None)):
            override.write_text(text)
            extra = [self.synthetic_dependency('dep-' + label.replace(' ', '-'))] if mods is None else mods
            with self.subTest(label), self.assertRaises(ValueError):
                self.run_mocked(extra_mods=extra, expansion_patrol_settings=override)
            self.assertFalse(self.experiment.exists())

    def test_profile_files_are_staged_hashed_and_must_survive_unchanged(self):
        sites = self.root / 'sites.json'
        sites.write_text('{"Sites": ["synthetic"]}')
        marker = self.root / 'marker'
        marker.write_bytes(b'')
        files = [('HollowCountry/expansion-ai-sites.json', sites), ('HollowCountry/acceptance/pve_patrols.enable', marker)]
        report = self.run_mocked(profile_files=files)
        self.assertEqual(report['status'], 'initialized')
        staged = self.experiment / 'profiles/HollowCountry/expansion-ai-sites.json'
        self.assertEqual(staged.read_bytes(), sites.read_bytes())
        self.assertEqual((self.experiment / 'profiles/HollowCountry/acceptance/pve_patrols.enable').read_bytes(), b'')
        self.assertEqual(report['profile_files_sha256'], {
            'HollowCountry/expansion-ai-sites.json': hashlib.sha256(sites.read_bytes()).hexdigest(),
            'HollowCountry/acceptance/pve_patrols.enable': hashlib.sha256(b'').hexdigest()})
        shutil.rmtree(self.experiment)
        report = self.run_mocked(profile_files=files, final_mutation=lambda: staged.write_text('{"Sites": []}'))
        self.assertEqual(report['status'], 'input-drift')

    def test_profile_files_refuse_unsafe_paths_duplicates_and_bad_json_before_staging(self):
        good = self.root / 'good.json'
        good.write_text('{}')
        bad = self.root / 'bad.json'
        bad.write_text('[')
        big = self.root / 'big.json'
        big.write_text('{"x": "' + 'a' * 70000 + '"}')
        cases = {'parent': [('../x.json', good)], 'absolute': [('/x.json', good)], 'empty part': [('a//x.json', good)],
                 'odd name': [('a/x y.json', good)], 'duplicate': [('a/x.json', good), ('a/x.json', good)],
                 'not json': [('a/x.json', bad)], 'oversized': [('a/x.json', big)], 'missing': [('a/x.json', self.root / 'no')],
                 'settings clash': [('HollowCountry/settings.json', good)]}
        for label, files in cases.items():
            with self.subTest(label), self.assertRaises(ValueError) as caught:
                self.run_mocked(profile_files=files, settings_case='malformed-json' if label == 'settings clash' else None)
            if label == 'settings clash':
                self.assertIn('--settings', str(caught.exception))
            self.assertFalse(self.experiment.exists())

    def test_hcx_is_staged_hashed_and_appended_to_shared_mod_list(self):
        addon = self.root / 'xai.pbo'
        addon.write_bytes(probe.pbo.pack({'config.cpp': b'// synthetic server addon'}, 'HollowCountryExpansionAI'))
        report = self.run_mocked(server_mod=addon)
        staged = self.experiment / '@HollowCountryExpansionAI/addons/hollowcountryexpansionai.pbo'
        self.assertEqual(staged.read_bytes(), addon.read_bytes())
        command = self.launch.call_args.args[0]
        self.assertIn('-mod=' + probe.win(self.experiment / '@HollowCountry') + ';' +
                      probe.win(staged.parent.parent), command)
        self.assertFalse(any(a.startswith('-serverMod=') for a in command))
        self.assertEqual(report['server_mod_sha256'], hashlib.sha256(addon.read_bytes()).hexdigest())
        self.assert_cleaned_report(report)

    def test_server_mod_must_be_a_parseable_pbo_before_staging(self):
        bad = self.root / 'bad.pbo'
        for blob in (b'not a pbo', probe.pbo.pack({'config.cpp': b'// main addon prefix'})):
            bad.write_bytes(blob)
            with self.subTest(blob=blob[:12]), self.assertRaises(ValueError):
                self.run_mocked(server_mod=bad)
            self.assertFalse(self.experiment.exists())

    def test_server_mod_drift_revokes_clean_initialization(self):
        addon = self.root / 'xai.pbo'
        addon.write_bytes(probe.pbo.pack({'config.cpp': b'// synthetic server addon'}, 'HollowCountryExpansionAI'))
        staged = self.experiment / '@HollowCountryExpansionAI/addons/hollowcountryexpansionai.pbo'
        report = self.run_mocked(server_mod=addon, final_mutation=lambda: staged.write_bytes(b'changed'))
        self.assertEqual(report['status'], 'input-drift')

    def test_default_run_has_no_server_mod_and_only_hc_mod(self):
        report = self.run_mocked()
        command = self.launch.call_args.args[0]
        self.assertFalse(any(a.startswith('-serverMod=') for a in command))
        self.assertIn('-mod=' + probe.win(self.experiment / '@HollowCountry'), command)
        self.assertEqual(report['extra_mods'], [])
        self.assertIsNone(report['server_mod_sha256'])

    def test_diagnostic_executable_requires_explicit_server_mode_and_report(self):
        (self.server / 'DayZDiag_x64.exe').write_bytes(b'synthetic diagnostic, never launched')
        report = self.run_mocked(diagnostic=True)
        command = self.launch.call_args.args[0]
        self.assertIn(str(self.server / 'DayZDiag_x64.exe'), command)
        self.assertIn('-server', command)
        self.assertEqual(report['executable_kind'], 'diagnostic-server')
        self.assert_cleaned_report(report)

    def test_selftests_require_diagnostic_and_fresh_mission(self):
        with self.assertRaisesRegex(ValueError, 'diagnostic'):
            self.run_mocked(diagnostic_selftests=True)
        self.assertFalse(self.experiment.exists())

    def test_item_audit_uses_normal_server_and_does_not_claim_export_completion(self):
        with patch('tools.setup.diagnostic_mission.prepare_diagnostic_mission',
                   side_effect=self.synthetic_stage) as prepare:
            report = self.run_mocked(item_compatibility_audit=True)
        prepare.assert_called_once_with(self.server / 'mpmissions/dayzOffline.chernarusplus',
                                        self.experiment / 'item-audit.chernarusplus', purpose='item-audit')
        self.assertIn('-mission=' + probe.win(self.experiment / 'item-audit.chernarusplus'),
                      self.launch.call_args.args[0])
        self.assertEqual(report['executable_kind'], 'dedicated-server')
        self.assertTrue(report['item_compatibility_audit_requested'])
        self.assertEqual(report['runtime_acceptance'], 'pending')
        self.assertNotIn('item_compatibility_audit_passed', report)
        self.assert_cleaned_report(report)

    def test_item_audit_cannot_combine_with_another_mission_hook(self):
        for kwargs in ({'diagnostic_selftests': True, 'diagnostic': True},
                       {'native_autotest_scripts': self.root / 'interfaces', 'diagnostic': True}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, 'one mission hook'):
                self.run_mocked(item_compatibility_audit=True, **kwargs)
            self.assertFalse(self.experiment.exists())

    def test_group_checks_stage_fixed_normal_server_mission_without_acceptance_claim(self):
        with patch('tools.setup.diagnostic_mission.prepare_diagnostic_mission',
                   side_effect=self.synthetic_stage) as prepare:
            report = self.run_mocked(group_checks=True)
        prepare.assert_called_once_with(self.server / 'mpmissions/dayzOffline.chernarusplus',
                                        self.experiment / 'group-checks.chernarusplus', purpose='group-checks')
        self.assertTrue(report['group_checks_requested'])
        self.assertIn('-mission=' + probe.win(self.experiment / 'group-checks.chernarusplus'),
                      self.launch.call_args.args[0])
        self.assertNotIn('group_checks_passed', report)
        self.assertEqual(report['runtime_acceptance'], 'pending')
        self.assert_cleaned_report(report)

    def test_group_checks_reject_other_mission_hooks_before_staging(self):
        for kwargs in ({'item_compatibility_audit': True},
                       {'diagnostic_selftests': True, 'diagnostic': True},
                       {'native_autotest_scripts': self.root / 'interfaces', 'diagnostic': True}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, 'one mission hook'):
                self.run_mocked(group_checks=True, **kwargs)
            self.assertFalse(self.experiment.exists())

    def test_native_autotest_waits_for_real_completion_and_keeps_engine_error(self):
        (self.server / 'DayZDiag_x64.exe').write_bytes(b'synthetic diagnostic')
        def prepare(source, destination, scripts, **kwargs):
            destination.mkdir()
            (destination / 'init.c').write_bytes(b'// synthetic native adapter boundary')
            return {'kind': 'synthetic-test-only', 'generated': {}}
        def frames(now):
            return ('SCRIPT (E): native plugin error\n[HollowCountry] Server initialized;\n' +
                    ('[HC Native Autotest] PASS; XML and logs still require verification' if now >= 3 else ''))
        with patch('tools.testing.native_autotest.prepare_autotest', side_effect=prepare):
            report = self.run_mocked(frames, diagnostic=True, native_autotest_scripts=self.root / 'interfaces')
        self.assertEqual(self.now, 3)
        self.assertEqual(report['status'], 'compiler-error')
        self.assertEqual(report['native_autotest_observation'], 'PASS-marker; XML verification required')
        self.assertIn('-mission=' + probe.win(self.experiment / 'native.chernarusplus'), self.launch.call_args.args[0])
        self.assertIn('-autotest=' + probe.win(self.experiment / 'native.chernarusplus/hc-autotest.json'), self.launch.call_args.args[0])
        self.assert_cleaned_report(report)

    def test_direct_actor_uses_authored_runner_without_native_harness_flag(self):
        (self.server / 'DayZDiag_x64.exe').write_bytes(b'synthetic diagnostic')
        def prepare(source, destination, scripts, **kwargs):
            self.assertEqual(kwargs['mode'], 'direct-actor')
            destination.mkdir()
            return {'kind': 'synthetic-test-only'}
        with patch('tools.testing.native_autotest.prepare_autotest', side_effect=prepare):
            report = self.run_mocked(lambda now: '[HC Native Actor] PASS authored assertions; not native harness acceptance',
                                     diagnostic=True, native_autotest_scripts=self.root / 'interfaces',
                                     native_actor_direct=True)
        self.assertEqual(report['native_autotest_observation'], 'PASS-marker; receipt verification required')
        self.assertFalse(any(arg.startswith('-autotest=') for arg in self.launch.call_args.args[0]))
        self.assert_cleaned_report(report)

    def test_native_autotest_cannot_use_normal_server_or_two_mission_hooks(self):
        for kwargs in ({'diagnostic': False}, {'diagnostic': True, 'diagnostic_selftests': True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.run_mocked(native_autotest_scripts=self.root / 'interfaces', **kwargs)
            self.assertFalse(self.experiment.exists())

    def native_timeout(self, frames, final_logs=''):
        (self.server / 'DayZDiag_x64.exe').write_bytes(b'synthetic diagnostic')
        def prepare(source, destination, scripts, **kwargs):
            destination.mkdir()
            return {'kind': 'synthetic-test-only'}
        with patch('tools.testing.native_autotest.prepare_autotest', side_effect=prepare):
            return self.run_mocked(frames, final_logs=final_logs, diagnostic=True,
                                   native_autotest_scripts=self.root / 'interfaces',
                                   native_actor_direct=True)

    def test_native_timeout_retains_started_state_and_engine_failure(self):
        report = self.native_timeout(lambda now: 'SCRIPT (E): synthetic error\n[HC Native Actor] BEGIN authored_direct_runner real_clients=0')
        self.assertEqual(report['status'], 'compiler-error')
        self.assertEqual(report['native_autotest_observation'], 'begun-but-incomplete')
        self.assertTrue(report['native_autotest_timed_out'])
        self.assertTrue(report['engine_error_observed'])
        self.assert_cleaned_report(report)

    def test_final_native_error_cannot_be_hidden_by_timeout(self):
        report = self.native_timeout(lambda now: '[HC Native Actor] BEGIN authored_direct_runner real_clients=0',
                                     final_logs='SCRIPT    (E): synthetic late error')
        self.assertEqual(report['status'], 'compiler-error')
        self.assertTrue(report['native_autotest_timed_out'])
        self.assertTrue(report['engine_error_observed'])
        self.assert_cleaned_report(report)

    def test_death_settings_rejection_cannot_admit_a_complete_receipt(self):
        original = self.run_mocked
        rejection = '[HollowCountry] Settings rejected; original file preserved: synthetic'
        def with_rejection(frames, **kwargs):
            return original(lambda now: frames(now) + '\n' + rejection, **kwargs)
        self.run_mocked = with_rejection
        report = self.death_run()
        self.assertEqual('settings-rejected', report['status'])
        self.assertIsNone(report['infected_death_receipt'])
        self.assert_cleaned_report(report)

    def test_final_settings_rejection_revokes_smoke_initialization(self):
        report = self.run_mocked(final_logs='[HollowCountry] Settings rejected; original file preserved: synthetic')
        self.assertEqual('settings-rejected', report['status'])
        self.assert_cleaned_report(report)

    def test_final_settings_rejection_revokes_death_completion(self):
        report = self.death_run(final_logs='[HollowCountry] Settings rejected; original file preserved: synthetic')
        self.assertEqual('settings-rejected', report['status'])
        self.assertIsNone(report['infected_death_receipt'])
        self.assert_cleaned_report(report)

    def test_final_smoke_error_overrides_initialization_and_sets_error_evidence(self):
        report = self.run_mocked(final_logs='SCRIPT (E): synthetic error flushed during cleanup')
        self.assertEqual(report['status'], 'compiler-error')
        self.assertTrue(report['engine_error_observed'])
        self.assertEqual(report['runtime_acceptance'], 'pending')
        self.assert_cleaned_report(report)

    def test_final_diagnostic_selftest_error_cannot_leave_initialized(self):
        (self.server / 'DayZDiag_x64.exe').write_bytes(b'synthetic diagnostic')
        stock = self.server / 'mpmissions/dayzOffline.chernarusplus/init.c'
        stock.write_bytes(b'class CustomMission: MissionServer {}; Mission CreateCustomMission(string path) { return new CustomMission(); }')
        report = self.run_mocked(diagnostic=True, diagnostic_selftests=True,
                                 final_logs='SCRIPT (E): synthetic late selftest error')
        self.assertEqual(report['status'], 'compiler-error')
        self.assertTrue(report['engine_error_observed'])
        self.assert_cleaned_report(report)

    def test_normal_poll_error_evidence_is_sticky_when_final_snapshot_is_empty(self):
        report = self.run_mocked(lambda now: 'SCRIPT (E): synthetic polling error')
        self.assertEqual(report['status'], 'compiler-error')
        self.assertTrue(report['engine_error_observed'])
        self.assert_cleaned_report(report)

    def test_native_launch_exception_is_not_a_deadline_timeout(self):
        (self.server / 'DayZDiag_x64.exe').write_bytes(b'synthetic diagnostic')
        def prepare(source, destination, scripts, **kwargs):
            destination.mkdir()
            return {'kind': 'synthetic-test-only'}
        with patch('tools.testing.native_autotest.prepare_autotest', side_effect=prepare):
            with self.assertRaisesRegex(OSError, 'synthetic launch failure'):
                self.run_mocked(diagnostic=True, native_autotest_scripts=self.root / 'interfaces',
                                launch_error=OSError('synthetic launch failure'))
        report = json.loads((self.experiment / 'compiler-report.json').read_text())
        self.assertFalse(report['native_autotest_timed_out'])
        self.assertEqual(report['status'], 'probe-error')
        self.assertEqual(self.now, 0)
        self.stop.assert_not_called()

    def test_native_poll_exception_is_not_a_deadline_timeout(self):
        def broken_log(now):
            raise OSError('synthetic native polling failure')
        with self.assertRaisesRegex(OSError, 'synthetic native polling failure'):
            self.native_timeout(broken_log)
        report = json.loads((self.experiment / 'compiler-report.json').read_text())
        self.assertFalse(report['native_autotest_timed_out'])
        self.assertEqual(report['status'], 'probe-error')
        self.assertEqual(self.now, 0)
        self.assert_cleaned_report(report)

    def test_native_begin_first_in_final_snapshot_is_preserved(self):
        report = self.native_timeout(lambda now: '', final_logs='[HC Native Actor] BEGIN authored_direct_runner real_clients=0')
        self.assertEqual(report['native_autotest_observation'], 'begun-but-incomplete')
        self.assertEqual(report['status'], 'timeout')
        self.assertTrue(report['native_autotest_timed_out'])
        self.assert_cleaned_report(report)

    def test_native_pass_first_in_final_snapshot_never_promotes_timeout(self):
        report = self.native_timeout(lambda now: '', final_logs='[HC Native Actor] PASS authored assertions; not native harness acceptance')
        self.assertEqual(report['native_autotest_observation'],
                         'PASS-marker; observed during final collection; receipt verification required')
        self.assertEqual(report['status'], 'timeout')
        self.assertTrue(report['native_autotest_timed_out'])
        self.assertEqual(report['runtime_acceptance'], 'pending')
        self.assert_cleaned_report(report)

    def test_native_pass_during_log_read_crossing_deadline_cannot_complete(self):
        marker = '[HC Native Actor] PASS authored assertions; not native harness acceptance'
        def slow_logs(now):
            if now == 14:
                self.now += 2
                return marker
            return ''
        report = self.native_timeout(slow_logs, final_logs=marker)
        self.assertEqual(report['status'], 'timeout')
        self.assertTrue(report['native_autotest_timed_out'])
        self.assertIn('observed during final collection', report['native_autotest_observation'])
        self.assert_cleaned_report(report)

    def test_final_native_fail_cannot_leave_an_earlier_pass_completed(self):
        report = self.native_timeout(lambda now: '[HC Native Actor] PASS authored assertions; not native harness acceptance',
                                     final_logs='[HC Native Actor] FAIL synthetic late assertion')
        self.assertEqual(report['native_autotest_observation'], 'FAIL-marker')
        self.assertEqual(report['status'], 'native-autotest-failed')
        self.assertFalse(report['native_autotest_timed_out'])
        self.assert_cleaned_report(report)

    def test_selftests_stage_separate_mission_and_preserve_native_error(self):
        (self.server / 'DayZDiag_x64.exe').write_bytes(b'synthetic diagnostic')
        stock = self.server / 'mpmissions/dayzOffline.chernarusplus/init.c'
        original = b'class CustomMission: MissionServer {}; Mission CreateCustomMission(string path) { return new CustomMission(); }'
        stock.write_bytes(original)
        report = self.run_mocked(lambda now: 'SCRIPT (E): native plugin error\n[HC Diagnostic Mission] PASS; no inventory/gameplay acceptance', diagnostic=True, diagnostic_selftests=True)
        self.assertEqual(report['status'], 'compiler-error')
        mission = self.experiment / 'diagnostic.chernarusplus'
        self.assertIn('-mission=' + probe.win(mission), self.launch.call_args.args[0])
        self.assertEqual(stock.read_bytes(), original)
        self.assertEqual(report['diagnostic_mission']['storage_probe_epoch'], 900001)
        self.assertIn(b'HCDisposableDiagnosticMission', (mission / 'init.c').read_bytes())
        self.assert_cleaned_report(report)

    def test_late_initialization_cannot_turn_deadline_into_hold_success(self):
        report = self.run_mocked(lambda now: '[HollowCountry] Server initialized;' if now >= 13 else '', hold_seconds=3)
        self.assertEqual(report['status'], 'timeout')
        self.assertLess(report['hold_seconds_observed'], report['hold_seconds_requested'])
        self.assertEqual(self.now, 15)
        self.assert_cleaned_report(report)

    def test_no_initialization_times_out_and_stops_owned_process(self):
        report = self.run_mocked(lambda now: '', hold_seconds=3)
        self.assertEqual(report['status'], 'timeout')
        self.assertEqual(report['hold_seconds_observed'], 0)
        self.assert_cleaned_report(report)

    def test_log_collection_crossing_deadline_cannot_complete_hold_after_timeout(self):
        def slow_logs(now):
            if now == 14:
                self.now += 2  # Bounded log I/O still takes wall-clock time.
            return '[HollowCountry] Server initialized;' if now >= 12 else ''
        report = self.run_mocked(slow_logs, hold_seconds=3)
        self.assert_cleaned_report(report)
        self.assertEqual(report['status'], 'timeout', 'the post-read deadline must precede hold success')

    def test_invalid_hold_values_are_rejected_before_staging_or_launch(self):
        for hold in (-1, 15, 241):
            with self.subTest(hold=hold), self.assertRaisesRegex(ValueError, 'hold'):
                self.run_mocked(hold_seconds=hold)
            self.launch.assert_not_called()
            self.assertFalse(self.experiment.exists())

    def test_long_world_startup_probe_remains_bounded_by_total_deadline(self):
        report = self.run_mocked(probe_seconds=300, hold_seconds=240)
        self.assertEqual(report['status'], 'initialized')
        self.assertEqual(report['hold_seconds_observed'], 240)
        self.assertEqual(self.now, 240)
        self.assert_cleaned_report(report)

    def test_launcher_exit_during_hold_cannot_pass_old_initialization_marker(self):
        self.process.poll.side_effect = lambda: 0 if self.now >= 1 else None
        report = self.run_mocked(hold_seconds=3)
        self.assertNotEqual(report['status'], 'initialized')
        self.assert_cleaned_report(report)

    def test_launcher_exit_at_hold_completion_cannot_pass_old_marker(self):
        self.process.poll.side_effect = lambda: 0 if self.now >= 3 else None
        report = self.run_mocked(hold_seconds=3)
        self.assert_cleaned_report(report)
        self.assertNotEqual(report['status'], 'initialized', 'hold success must still check launcher liveness')

    def test_script_error_during_hold_takes_precedence_and_cleans_up(self):
        report = self.run_mocked(lambda now: '[HollowCountry] Server initialized;\n' +
                                 ('SCRIPT (E): synthetic failure' if now >= 1 else ''), hold_seconds=3)
        self.assertEqual(report['status'], 'compiler-error')
        self.assert_cleaned_report(report)

    def test_negative_json_engine_error_is_not_masked_by_expected_rejection(self):
        report = self.run_mocked(lambda now: 'SCRIPT (E): JSON ERROR\n[HollowCountry] Invalid settings; original file preserved; features disabled: bad JSON',
                                 settings_case='malformed-json', hold_seconds=3)
        self.assertEqual(report['status'], 'compiler-error')
        self.assertTrue(report['settings_original_preserved'])
        self.assertEqual((self.experiment / 'profiles/HollowCountry/settings.json').read_bytes(), b'{')
        self.assert_cleaned_report(report)

    def test_polling_exception_still_stops_group_and_writes_report(self):
        def broken_log(now):
            raise OSError('synthetic polling failure')
        with self.assertRaisesRegex(OSError, 'synthetic polling failure'):
            self.run_mocked(broken_log, hold_seconds=3)
        report = json.loads((self.experiment / 'compiler-report.json').read_text())
        self.assertEqual(report['status'], 'probe-error')
        self.assert_cleaned_report(report)

    def test_all_three_maximum_size_seed_files_are_staged_and_hashed_without_mutation(self):
        seed = self.root / 'seed'
        seed.mkdir()
        originals = {name: bytes([index]) * 65536 for index, name in enumerate(
            ('config.json', 'hordes-a.json', 'hordes-b.json'))}
        for name, data in originals.items():
            (seed / name).write_bytes(data)
        report = self.run_mocked(state_seed=seed, hold_seconds=1)
        staged = self.experiment / 'profiles/HollowCountry/Infected'
        self.assertEqual({p.name for p in staged.iterdir()}, set(originals))
        for name, data in originals.items():
            self.assertEqual((staged / name).read_bytes(), data)
            self.assertEqual((seed / name).read_bytes(), data)
        self.assertEqual(report['state_seed_sha256'], {name: hashlib.sha256(data).hexdigest() for name, data in originals.items()})
        self.assert_cleaned_report(report)

    def test_seed_rejections_precede_staging_and_process_launch(self):
        for kind in ('missing', 'oversized', 'unknown', 'fourth-file', 'directory', 'file-link', 'root-link', 'ancestor-link'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=self.root) as temp:
                base = Path(temp)
                seed = base / 'seed'
                if kind != 'missing':
                    seed.mkdir()
                if kind == 'oversized':
                    (seed / 'hordes-a.json').write_bytes(b'x' * 65537)
                elif kind == 'unknown':
                    (seed / 'unexpected.json').write_bytes(b'{}')
                elif kind == 'fourth-file':
                    for name in ('config.json', 'hordes-a.json', 'hordes-b.json', 'extra.json'):
                        (seed / name).write_bytes(b'{}')
                elif kind == 'directory':
                    (seed / 'config.json').mkdir()
                elif kind == 'file-link':
                    target = base / 'outside.json'
                    target.write_bytes(b'synthetic outside seed')
                    (seed / 'config.json').symlink_to(target)
                elif kind in ('root-link', 'ancestor-link'):
                    (seed / 'nested').mkdir()
                    link = base / 'linked'
                    link.symlink_to(seed, target_is_directory=True)
                    seed = link / 'nested' if kind == 'ancestor-link' else link
                with self.assertRaises((ValueError, OSError)):
                    self.run_mocked(state_seed=seed, hold_seconds=1)
                self.launch.assert_not_called()
                self.stop.assert_not_called()
                self.assertFalse(self.experiment.exists())

    def test_seed_read_is_bounded_even_if_regular_file_grows(self):
        seed = self.root / 'seed'
        seed.mkdir()
        target = seed / 'hordes-a.json'
        target.write_bytes(b'x')
        native_open = Path.open
        stream = io.BytesIO(b'x' * 65538)
        read = Mock(wraps=stream.read)
        stream.read = read

        def opened(path, *args, **kwargs):
            return stream if path == target else native_open(path, *args, **kwargs)

        with patch.object(Path, 'open', opened), self.assertRaisesRegex(ValueError, '64 KiB'):
            self.run_mocked(state_seed=seed, hold_seconds=1)
        read.assert_called_once_with(65537)
        self.launch.assert_not_called()
        self.assertFalse(self.experiment.exists())


class WineCompilerProbeTests(unittest.TestCase):
    def test_infected_seed_is_bounded_and_rejects_unknown_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'config.json').write_bytes(b'{}')
            self.assertEqual(probe.read_state_seed(root), {'config.json': b'{}'})
            (root / 'hordes-a.json').write_bytes(b'x' * 65537)
            with self.assertRaises(ValueError):
                probe.read_state_seed(root)
            (root / 'hordes-a.json').unlink()
            (root / 'unexpected.json').write_bytes(b'{}')
            with self.assertRaises(ValueError):
                probe.read_state_seed(root)

    def test_negative_settings_fixtures_are_explicit_and_bounded(self):
        self.assertEqual(probe.negative_settings('malformed-json'), b'{')
        self.assertEqual(len(probe.negative_settings('oversized')), 16385)
        self.assertEqual(probe.negative_settings('unsupported-schema'), b'{"SchemaVersion":2}')
        with self.assertRaises(ValueError):
            probe.negative_settings('unknown')

    def test_settings_rejection_never_counts_as_initialization(self):
        self.assertEqual(probe.classify('[HollowCountry] Invalid settings; original file preserved; features disabled: bad JSON'), 'settings-rejected')
        self.assertEqual(probe.classify('[HollowCountry] Settings rejected; original file preserved: Unsupported settings schema'), 'settings-rejected')
        self.assertEqual(probe.classify('SCRIPT (E): compiler failed\n[HollowCountry] Settings rejected; original file preserved: error'), 'compiler-error')

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux Wine probe lifecycle')
    def test_real_surviving_child_is_stopped_after_launcher_exits(self):
        code = ('import os, signal, time\n'
                'child = os.fork()\n'
                'if child:\n'
                ' print(child, flush=True)\n'
                ' os._exit(0)\n'
                'signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
                'os.close(1)\n'
                'time.sleep(30)\n')
        process = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE,
                                   text=True, start_new_session=True)
        child = int(process.stdout.readline())
        process.wait(timeout=5)
        try:
            self.assertTrue(probe.stop_group(process, grace=0))
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                stat = Path(f'/proc/{child}/stat')
                if not stat.exists() or stat.read_text().split(') ', 1)[1].startswith('Z '):
                    break
                time.sleep(0.05)
            else:
                self.fail('owned surviving child still running after cleanup')
        finally:
            process.stdout.close()
            try:
                os.killpg(process.pid, probe.signal.SIGKILL)
            except ProcessLookupError:
                pass

    def test_cleanup_kills_surviving_group_after_leader_exit(self):
        process = Mock(pid=123, returncode=0)
        process.poll.return_value = 0
        with patch.object(probe, 'group_alive', side_effect=[True, True, False]), patch.object(probe.os, 'killpg') as kill, patch.object(probe.time, 'sleep'):
            self.assertTrue(probe.stop_group(process, grace=0))
        self.assertEqual([call.args[1] for call in kill.call_args_list], [probe.signal.SIGTERM, probe.signal.SIGKILL])

    def test_cleanup_tolerates_missing_group(self):
        process = Mock(pid=123)
        with patch.object(probe, 'group_alive', return_value=False), patch.object(probe.os, 'killpg') as kill:
            self.assertFalse(probe.stop_group(process, grace=0))
        kill.assert_not_called()

    def test_log_collection_enforces_individual_and_aggregate_budgets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'large.log').write_bytes(b'x' * 33)
            (root / 'small.adm').write_bytes(b'hello')
            with patch.object(probe, 'MAX_LOG_FILE', 32), patch.object(probe, 'MAX_LOG_TOTAL', 16):
                text, hashes, skipped = probe.collect_logs(root)
            self.assertEqual(text, 'hello')
            self.assertEqual(list(hashes), ['small.adm'])
            self.assertIn('large.log', skipped)
            with patch.object(probe, 'MAX_LOG_TOTAL', 1):
                text, hashes, skipped = probe.collect_logs(root)
            self.assertEqual(hashes, {})
            self.assertEqual(text, '')

    def test_disposable_config_has_required_native_server_identity(self):
        text = probe.configuration()
        for value in ('instanceId=1;', 'guaranteedUpdates=1;', 'shardId="hcdev1";',
                      'verifySignatures=0;', 'BattlEye=0;', 'maxPlayers=6;'):
            self.assertIn(value, text)

    def test_compiler_errors_override_initialization_marker(self):
        text = '[HollowCountry] Server initialized;\nSCRIPT    (E): bad override\n'
        self.assertEqual(probe.classify(text), 'compiler-error')

    def test_fatal_engine_crash_overrides_compiler_and_initialization(self):
        self.assertEqual('engine-crash',probe.classify(
            '[HollowCountry] Server initialized;\nSCRIPT (E): cascade\n23:42:20.007 ENGINE    (F): Crashed'))
        for text in ('ENGINE (E): Cannot run crashreport process...',
                     'ANIMATION (E): missing material', 'SCRIPT (W): Crashed variable'):
            self.assertIsNone(probe.classify(text))

    def test_settings_selftest_without_lifecycle_is_incomplete(self):
        self.assertIsNone(probe.classify('[HollowCountry][SelfTest] Core settings PASS'))

    def test_normal_engine_warnings_do_not_become_compiler_errors(self):
        text = 'ANIMATION (E): missing skeleton\nSCRIPT (W): missing declaration\n'
        self.assertIsNone(probe.classify(text))

    def test_full_initialization_is_still_only_a_smoke(self):
        self.assertEqual(probe.classify('[HollowCountry] Server initialized; flags false'), 'initialized')

    def test_popup_compile_failure_is_recognized(self):
        self.assertEqual(probe.classify('Can\'t compile "World" script module!'), 'compiler-error')


if __name__ == '__main__':
    unittest.main()
