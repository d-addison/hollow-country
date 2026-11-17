"""Synthetic process, clock, declarations and receipts. Never launch DayZ."""
from contextlib import ExitStack
import importlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from tools.package import pbo
from tools.setup import fuel_siphon_probe as fuel
from tests.unit import test_fuel_siphon_probe as fixtures


class FuelProbeRunnerTests(unittest.TestCase):
    def setUp(self):
        self.runner=importlib.import_module('tools.setup.fuel_probe_runner')
        self.temp=tempfile.TemporaryDirectory(prefix='hc-synthetic-fuel-runner-')
        self.addCleanup(self.temp.cleanup); self.root=Path(self.temp.name)
        self.server=self.root/'server'
        mission=self.server/'mpmissions/dayzOffline.chernarusplus'; mission.mkdir(parents=True)
        (mission/'init.c').write_text('void main() { Hive ce = CreateHive(); if (ce) ce.InitOffline(); }\nclass CustomMission : MissionServer {}\n'
            'Mission CreateCustomMission(string path) { return new CustomMission(); }\n')
        (self.server/'DayZServer_x64.exe').write_bytes(b'SYNTHETIC never executable')
        (self.server/'battleye').mkdir()
        (self.server/'battleye/BEServer_x64.dll').write_bytes(b'SYNTHETIC DLL')
        self.source=self.root/'synthetic.pbo'
        self.source.write_bytes(pbo.pack({'config.cpp':b'// SYNTHETIC'}))
        self.prefix=self.root/'prefix'; self.prefix.mkdir()
        self.scripts=self.root/'synthetic-interfaces'
        for name,tokens in fuel.INTERFACES.items():
            path=self.scripts/name; path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('\n'.join(tokens))
        self.experiment=self.root/'experiment'; self.now=0.
        self.process=Mock(pid=123456789,returncode=None)
        self.process.poll.return_value=None
        self.options=dict(x=6500,z=6500,rate_ml=1000,cap_ml=1000,fuel_liters=2,
            car_class='OffroadHatchback',vessel_class='CanisterGasoline',seconds=25,execute=True)

    def invoke(self, **options):
        return self.runner.run(self.server,self.source,self.experiment,self.prefix,
                               self.scripts,**dict(self.options,**options))

    def mocked(self,complete_at=3,mutate=None,log_delay=0,validation_delay=0,
               cleanup_delay=1,cleanup_error=False,group_survives=False,death_at=None,
               final_complete=False,final_error=False,launch_error=None,staging_delay=0,
               final_poll_delay=0,preflight_code=1,foreign_experiment=False,
               final_settings_error=False, final_mutation=None,engine_crash=False,final_engine_crash=False):
        original_is_file=Path.is_file; original_prepare=fuel.prepare_probe
        original_validate=fuel.validate_result; emitted=False; validated=False
        def is_file(path):
            return True if str(path)=='/usr/lib/wine/wine64' else original_is_file(path)
        def receipt():
            marker=json.loads((self.experiment/'fuel.chernarusplus'/fuel.MARKER).read_text())
            row=fixtures.FuelSiphonProbeTests.receipt(NS(probe=fuel))
            row['run_id']=marker['run_id']
            if 'mode' in marker:
                row.update(mode=marker['mode'], ce_disabled_control=marker['ce_disabled_control'])
            if mutate: mutate(row)
            (self.experiment/'profiles'/fuel.RESULT).write_text(json.dumps(row))
        def logs(path):
            nonlocal emitted
            text='[HollowCountry] Server initialized; SYNTHETIC'
            if engine_crash:text+='\nENGINE    (F): Crashed'
            if path==self.experiment:
                if final_mutation: final_mutation()
                if final_complete: receipt(); text+='\n[HC Siphon Probe] COMPLETE run=late'
                if final_error: text+='\nSCRIPT (E): SYNTHETIC final compiler error'
                if final_engine_crash:text+='\nENGINE    (F): Crashed'
                if final_settings_error:
                    text+='\n[HollowCountry] Settings rejected; original file preserved: SYNTHETIC'
                return text,{},{}
            if complete_at is not None and self.now>=complete_at and not emitted:
                receipt(); emitted=True
                text+='\n[HC Siphon Probe] COMPLETE'
            self.now+=log_delay
            return text,{},{}
        def sleep(seconds): self.now+=seconds
        def poll():
            nonlocal validated
            if validated:
                self.now+=final_poll_delay; validated=False
            return 1 if death_at is not None and self.now>=death_at else None
        def stop(process,grace=5):
            self.assertIs(process,self.process); self.now+=cleanup_delay
            if cleanup_error: raise RuntimeError('SYNTHETIC cleanup failure')
            process.returncode=-15; return True
        def prepare(*args,**kwargs):
            result=original_prepare(*args,**kwargs); self.now+=staging_delay; return result
        def validate(*args,**kwargs):
            nonlocal validated
            result=original_validate(*args,**kwargs); self.now+=validation_delay
            validated=True; return result
        def preflight(*args,**kwargs):
            if foreign_experiment:
                self.experiment.mkdir()
                (self.experiment/'foreign.txt').write_text('not owned')
            return Mock(returncode=preflight_code)
        self.process.poll.side_effect=poll
        with ExitStack() as stack:
            stack.enter_context(patch.object(Path,'is_file',is_file))
            stack.enter_context(patch.object(self.runner.shutil,'which',return_value='/synthetic/xvfb-run'))
            self.preflight=stack.enter_context(patch.object(self.runner.subprocess,'run',side_effect=preflight))
            self.launch=stack.enter_context(patch.object(self.runner.subprocess,'Popen',return_value=self.process,side_effect=launch_error))
            self.stop=stack.enter_context(patch.object(self.runner.wine,'stop_group',side_effect=stop))
            stack.enter_context(patch.object(self.runner.wine,'group_alive',return_value=group_survives))
            stack.enter_context(patch.object(self.runner.wine,'collect_logs',side_effect=logs))
            stack.enter_context(patch.object(self.runner.time,'monotonic',side_effect=lambda:self.now))
            stack.enter_context(patch.object(self.runner.time,'sleep',side_effect=sleep))
            stack.enter_context(patch.object(fuel,'prepare_probe',side_effect=prepare))
            stack.enter_context(patch.object(fuel,'validate_result',side_effect=validate))
            return self.invoke()

    def test_explicit_execute_required_before_any_process_or_staging(self):
        with patch.object(self.runner.subprocess,'Popen') as launch, patch.object(self.runner.subprocess,'run') as command:
            with self.assertRaises(ValueError): self.invoke(execute=False)
            with self.assertRaises(ValueError): self.invoke(execute=1)
        launch.assert_not_called(); command.assert_not_called()
        self.assertFalse(self.experiment.exists())

    def test_bad_budgets_and_fixture_fail_before_any_launch(self):
        for values in (dict(seconds=181),dict(seconds=True),dict(seconds=14),
                       dict(rate_ml=0),dict(cap_ml=1001),dict(x=float('nan'))):
            with self.subTest(values=values), patch.object(self.runner.subprocess,'Popen') as launch:
                with self.assertRaises(ValueError): self.invoke(**values)
                launch.assert_not_called()
        self.assertFalse(self.experiment.exists())

    def test_admitted_receipt_stops_promptly_and_records_cleanup(self):
        report=self.mocked()
        self.assertEqual('fuel-probe-completed',report['status'])
        self.assertTrue(report['receipt']['inprocess_observation_complete'])
        self.assertTrue(report['process_cleanup_confirmed'])
        self.assertLess(self.now,10)
        self.assertFalse(report['production_acceptance'])
        self.assertEqual(report,json.loads((self.experiment/'fuel-probe-report.json').read_text()))
        command=self.launch.call_args.args[0]
        self.assertIn(str(self.server/'DayZServer_x64.exe'),command)
        self.assertNotIn('-server',command)
        self.assertTrue(self.launch.call_args.kwargs['start_new_session'])
        settings=json.loads((self.experiment/'profiles/HollowCountry/settings.json').read_text())
        self.assertTrue(all(value is False for key,value in settings.items() if key.startswith('Enable')))
        self.assertIn('-mission='+self.runner.wine.win(self.experiment/'fuel.chernarusplus'),command)

    def test_initialization_only_times_out_with_cleanup_reserve(self):
        report=self.mocked(complete_at=None)
        self.assertEqual('timeout',report['status']); self.assertIsNone(report['receipt'])
        self.assertTrue(report['timed_out']); self.assertLessEqual(self.now,25)
        self.assertEqual(12,report['cleanup_reserve_seconds']); self.stop.assert_called_once()

    def test_engine_crash_stops_before_timeout_and_late_crash_revokes_receipt(self):
        for index,options in enumerate((dict(engine_crash=True,complete_at=None),dict(final_engine_crash=True))):
            with self.subTest(options=options):
                self.experiment=self.root/('fatal-'+str(index));self.now=0
                report=self.mocked(**options)
                self.assertEqual('engine-crash',report['status'])
                self.assertTrue(report['engine_error_observed'])
                self.assertIsNone(report['receipt'])
                self.assertLess(self.now,10)
                self.assertTrue(report['process_cleanup_confirmed'])

    @staticmethod
    def native_flags(row):
        row.update({key:int(value) for key,value in row.items() if type(value) is bool})

    def test_native_integer_terminal_receipt_is_admitted_before_cleanup(self):
        report=self.mocked(mutate=self.native_flags)
        self.assertEqual('fuel-probe-completed',report['status'])
        self.assertTrue(report['receipt_admitted_before_cleanup'])
        self.assertTrue(report['process_cleanup_confirmed']); self.assertLess(self.now,10)

    def test_native_integer_failure_is_terminal_and_never_admitted(self):
        def failed(row):
            self.native_flags(row); row.update(complete=0,failed=1)
        report=self.mocked(mutate=failed)
        self.assertEqual('fuel-probe-failed',report['status'])
        self.assertFalse(report['receipt_admitted_before_cleanup'])
        self.assertIsNone(report['receipt']); self.assertLess(self.now,10)

    def test_invalid_terminal_flag_types_refuse_promptly(self):
        for index,(field,bad) in enumerate((f,b) for f in ('complete','failed')
                for b in (1.0,0.0,'1','0',None,2,-1)):
            self.experiment=self.root/('invalid-flag-'+str(index)); self.now=0
            self.process.returncode=None
            def malformed(row):
                self.native_flags(row); row[field]=bad
            report=self.mocked(mutate=malformed)
            with self.subTest(field=field,bad=bad):
                self.assertEqual('fuel-probe-failed',report['status'])
                self.assertIsNone(report['receipt']); self.assertLess(self.now,10)

    def test_native_flags_preserve_deadline_and_cleanup_revocation(self):
        for index,options in enumerate((dict(complete_at=12,validation_delay=2),
                                       dict(group_survives=True),dict(final_settings_error=True))):
            self.experiment=self.root/('native-revocation-'+str(index)); self.now=0
            self.process.returncode=None
            report=self.mocked(mutate=self.native_flags,**options)
            self.assertNotEqual('fuel-probe-completed',report['status'])
            self.assertIsNone(report['receipt'])

    def test_failed_callback_replay_cleanup_nonce_and_conservation_rejected(self):
        # Separate fixtures avoid reusing any fresh experiment/profile.
        for change in (dict(finish_calls=0),dict(replay_refused=False),dict(car_deleted=False),
                       dict(run_id='b'*32),dict(vessel_after_ml=1001),dict(reason='native-callback-interrupted')):
            with self.subTest(change=change):
                self.experiment=self.root/('case-'+str(len(list(self.root.glob('case-*')))))
                self.now=0
                report=self.mocked(mutate=lambda row:row.update(change))
                self.assertEqual('fuel-probe-failed',report['status'])
                self.assertIsNone(report['receipt']); self.stop.assert_called_once()

    def test_receipt_crossing_deadline_during_log_read_rejected(self):
        report=self.mocked(complete_at=12,log_delay=2)
        self.assertEqual('timeout',report['status']); self.assertIsNone(report['receipt'])

    def test_receipt_crossing_deadline_during_validation_rejected(self):
        report=self.mocked(complete_at=12,validation_delay=2)
        self.assertEqual('timeout',report['status']); self.assertIsNone(report['receipt'])

    def test_final_live_process_check_crossing_deadline_rejects_admission(self):
        report=self.mocked(complete_at=12,final_poll_delay=2)
        self.assertEqual('timeout',report['status']); self.assertIsNone(report['receipt'])

    def test_staging_consumes_same_total_budget_no_late_launch(self):
        report=self.mocked(staging_delay=14)
        self.launch.assert_not_called(); self.stop.assert_not_called()
        self.assertEqual('timeout',report['status'])

    def test_dead_process_cannot_supply_historical_valid_receipt(self):
        report=self.mocked(complete_at=3,death_at=3)
        self.assertEqual('process-exited',report['status']); self.assertIsNone(report['receipt'])
        self.stop.assert_called_once()

    def test_final_late_completion_does_not_promote_timeout(self):
        report=self.mocked(complete_at=None,final_complete=True)
        self.assertEqual('timeout',report['status']); self.assertIsNone(report['receipt'])
        self.assertTrue(report['receipt_present_final'])

    def test_cleanup_survivor_or_error_cannot_pass(self):
        report=self.mocked(group_survives=True)
        self.assertEqual('cleanup-incomplete',report['status'])
        self.assertFalse(report['process_cleanup_confirmed'])
        self.experiment=self.root/'cleanup-error'; self.now=0
        report=self.mocked(cleanup_error=True)
        self.assertEqual('cleanup-failed',report['status'])
        self.assertIn('SYNTHETIC cleanup failure',report['cleanup_error'])

    def test_total_cleanup_overrun_revokes_admitted_success(self):
        report=self.mocked(cleanup_delay=24)
        self.assertEqual('outer-budget-exceeded',report['status'])
        self.assertTrue(report['timed_out']); self.assertIsNone(report['receipt'])

    def test_launch_error_is_not_fabricated_timeout(self):
        report=self.mocked(launch_error=OSError('SYNTHETIC launch failure'))
        self.assertEqual('probe-error',report['status']); self.assertFalse(report['timed_out'])
        self.stop.assert_not_called()

    def test_final_engine_error_revokes_receipt(self):
        report=self.mocked(final_error=True)
        self.assertEqual('compiler-error',report['status']); self.assertIsNone(report['receipt'])

    def test_concurrent_destination_creation_is_never_collected_or_written(self):
        report=self.mocked(foreign_experiment=True)
        self.launch.assert_not_called()
        self.assertEqual('probe-error',report['status'])
        self.assertEqual(['foreign.txt'],sorted(path.name for path in self.experiment.iterdir()))

    def test_native_already_running_or_failed_process_discovery_never_launches(self):
        for code in (0,2):
            with self.subTest(code=code):
                report=self.mocked(preflight_code=code)
                self.launch.assert_not_called(); self.assertFalse(self.experiment.exists())
                self.assertEqual('probe-error',report['status'])

    def test_invalid_pbo_rejected_before_launch_or_experiment_creation(self):
        self.source.write_bytes(b'not an authored PBO')
        report=self.mocked()
        self.launch.assert_not_called(); self.assertFalse(self.experiment.exists())
        self.assertEqual('probe-error',report['status'])


    def test_final_settings_rejection_revokes_success_or_timeout_receipt(self):
        for complete_at in (3, None):
            with self.subTest(complete_at=complete_at):
                self.experiment = self.root/('settings-final-'+str(complete_at))
                self.now = 0
                report = self.mocked(
                    complete_at=complete_at, final_settings_error=True)
                self.assertEqual('settings-rejected', report['status'])
                self.assertIsNone(report['receipt'])


    def test_explicit_180_budget_allows_late_startup_and_keeps_cleanup_reserve(self):
        self.options['seconds'] = 180
        report = self.mocked(complete_at=100)
        self.assertEqual('fuel-probe-completed', report['status'])
        self.assertEqual(180, report['outer_budget_seconds'])
        self.assertEqual(168, report['process_budget_seconds'])
        self.assertEqual(12, report['cleanup_reserve_seconds'])
        self.assertTrue(report['process_cleanup_confirmed'])
        self.assertLess(self.now, 180)

    def test_explicit_180_budget_still_times_out_without_receipt(self):
        self.options['seconds'] = 180
        report = self.mocked(complete_at=None)
        self.assertEqual('timeout', report['status'])
        self.assertTrue(report['timed_out'])
        self.assertIsNone(report['receipt'])
        self.assertTrue(report['process_cleanup_confirmed'])
        self.assertLessEqual(self.now, 180)


    def test_final_launch_or_complete_mission_drift_revokes_receipt(self):
        targets = (
            '@HollowCountry/addons/hollowcountry.pbo', 'serverDZ.cfg',
            'battleye/BEServer_x64.dll', 'fuel.chernarusplus/init.c',
            'fuel.chernarusplus/' + fuel.MARKER,
        )
        for index, relative in enumerate(targets):
            self.experiment = self.root / ('final-drift-' + str(index))
            self.now = 0
            self.process.returncode = None
            report = self.mocked(final_mutation=lambda:
                (self.experiment / relative).write_bytes(b'SYNTHETIC drift'))
            with self.subTest(relative=relative):
                self.assertEqual('input-drift', report['status'])
                self.assertIsNone(report['receipt'])
                self.assertTrue(report['process_cleanup_confirmed'])
                self.assertEqual(report, self.runner.read_report(
                    self.experiment / self.runner.REPORT))

    def test_final_mission_extra_missing_directory_and_link_are_rejected(self):
        for index, change in enumerate(('extra', 'missing', 'directory', 'link')):
            self.experiment = self.root / ('mission-inventory-' + str(index))
            self.now = 0
            self.process.returncode = None
            def mutate():
                mission = self.experiment / 'fuel.chernarusplus'
                if change == 'extra':
                    (mission / 'unexpected.c').write_bytes(b'// synthetic')
                elif change == 'missing':
                    (mission / 'init.c').unlink()
                elif change == 'directory':
                    (mission / 'unexpected').mkdir()
                else:
                    (mission / 'unexpected.c').symlink_to(self.source)
            report = self.mocked(final_mutation=mutate)
            with self.subTest(change=change):
                self.assertEqual('input-drift', report['status'])
                self.assertIsNone(report['receipt'])

    def test_final_executable_drift_revokes_receipt(self):
        report = self.mocked(final_mutation=lambda:
            (self.server / 'DayZServer_x64.exe').write_bytes(b'SYNTHETIC drift'))
        self.assertEqual('input-drift', report['status'])
        self.assertIsNone(report['receipt'])

    def test_final_engine_error_remains_sticky_with_input_drift(self):
        report = self.mocked(final_error=True, final_mutation=lambda:
            (self.experiment / 'serverDZ.cfg').write_bytes(b'SYNTHETIC drift'))
        self.assertEqual('compiler-error', report['status'])
        self.assertIsNone(report['receipt'])

    def test_successful_report_requires_guarded_publication(self):
        report = self.mocked()
        path = self.experiment / self.runner.REPORT
        self.assertEqual(report, self.runner.read_report(path))
        self.assertFalse(path.with_name(path.name + '.pending').exists())

    def test_failed_published_readback_keeps_success_artifact_untrusted(self):
        original_read = fuel._read
        original_unlink = Path.unlink
        def read(path, limit):
            if Path(path).name == self.runner.REPORT:
                raise OSError('SYNTHETIC published readback failure')
            return original_read(path, limit)
        def unlink(path, *args, **kwargs):
            if path.name == self.runner.REPORT:
                raise OSError('SYNTHETIC cannot remove failed report')
            return original_unlink(path, *args, **kwargs)
        with patch.object(fuel, '_read', side_effect=read), patch.object(Path, 'unlink', unlink):
            report = self.mocked()
        path = self.experiment / self.runner.REPORT
        self.assertEqual('report-write-error', report['status'])
        self.assertIsNone(report['receipt'])
        self.assertEqual('fuel-probe-completed', json.loads(path.read_text())['status'])
        self.assertTrue(path.with_name(path.name + '.pending').exists())
        with self.assertRaisesRegex(ValueError, 'publication incomplete'):
            self.runner.read_report(path)

    def test_report_verification_overrun_revokes_publication(self):
        original_read = fuel._read
        def read(path, limit):
            data = original_read(path, limit)
            if Path(path).name == self.runner.REPORT:
                self.now += 30
            return data
        with patch.object(fuel, '_read', side_effect=read):
            report = self.mocked()
        self.assertEqual('outer-budget-exceeded', report['status'])
        self.assertTrue(report['timed_out'])
        self.assertIsNone(report['receipt'])
        with self.assertRaises((ValueError, OSError)):
            self.runner.read_report(self.experiment / self.runner.REPORT)


    def test_explicit_ce_control_admits_only_matching_mode_receipt(self):
        self.options['mode'] = 'ce-disabled-control'
        report = self.mocked()
        self.assertEqual('fuel-probe-completed', report['status'])
        self.assertEqual('ce-disabled-control', report['mode'])
        self.assertTrue(report['ce_disabled_control'])
        self.assertEqual(report['mode'], report['receipt']['mode'])
        self.assertFalse(report['gameplay_acceptance'])
        self.assertFalse(report['ce_acceptance'])
        self.assertTrue(report['process_cleanup_confirmed'])
        self.assertIn('if (ce) {}',
            (self.experiment / 'fuel.chernarusplus/init.c').read_text())
        self.assertEqual(report, self.runner.read_report(self.experiment / self.runner.REPORT))

    def test_default_stock_mode_and_control_mismatch_no_admission(self):
        report = self.mocked()
        self.assertEqual('stock-ce', report['mode'])
        self.assertFalse(report['ce_disabled_control'])
        self.assertIn('if (ce) ce.InitOffline();',
            (self.experiment / 'fuel.chernarusplus/init.c').read_text())
        self.experiment = self.root / 'mode-mismatch'
        self.now = 0
        self.process.returncode = None
        self.options['mode'] = 'ce-disabled-control'
        report = self.mocked(mutate=lambda row:
            row.update(mode='stock-ce', ce_disabled_control=False))
        self.assertEqual('fuel-probe-failed', report['status'])
        self.assertIsNone(report['receipt'])

    def test_invalid_mode_is_rejected_before_process_or_staging(self):
        with patch.object(self.runner.subprocess, 'Popen') as launch, patch.object(
                self.runner.subprocess, 'run') as preflight:
            for mode in (True, None, 0, 'unknown'):
                with self.subTest(mode=mode), self.assertRaises(ValueError):
                    self.invoke(mode=mode)
        launch.assert_not_called()
        preflight.assert_not_called()
        self.assertFalse(self.experiment.exists())

    def test_control_retains_timeout_and_final_input_veto(self):
        self.options['mode'] = 'ce-disabled-control'
        report = self.mocked(complete_at=None)
        self.assertEqual('timeout', report['status'])
        self.assertIsNone(report['receipt'])
        self.assertTrue(report['process_cleanup_confirmed'])
        self.experiment = self.root / 'control-drift'
        self.now = 0
        self.process.returncode = None
        report = self.mocked(final_mutation=lambda:
            (self.experiment / 'fuel.chernarusplus/init.c').write_bytes(b'// drift'))
        self.assertEqual('input-drift', report['status'])
        self.assertIsNone(report['receipt'])

    def test_report_reader_rejects_unattributed_or_inconsistent_ce_mode(self):
        report = self.mocked()
        path = self.experiment / self.runner.REPORT
        for key in ('mode', 'ce_disabled_control', 'gameplay_acceptance', 'ce_acceptance'):
            row = dict(report)
            del row[key]
            path.write_text(json.dumps(row))
            with self.subTest(missing=key), self.assertRaises(ValueError):
                self.runner.read_report(path)
        for changes in (dict(mode='ce-disabled-control'), dict(ce_disabled_control=0),
                        dict(gameplay_acceptance=True), dict(ce_acceptance=True)):
            path.write_text(json.dumps(dict(report, **changes)))
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.runner.read_report(path)


if __name__=='__main__': unittest.main()
