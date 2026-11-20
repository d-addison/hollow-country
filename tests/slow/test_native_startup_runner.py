"""Synthetic processes/clocks/interfaces/receipts ONLY; no DayZ launch."""
from contextlib import ExitStack, redirect_stdout
import importlib
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch
import unittest

from tools.package import pbo
from tools.setup import native_startup_probe as probe
from tests.slow.test_native_startup_probe import STOCK, receipt


class StartupRunnerTests(unittest.TestCase):
    def setUp(self):
        self.runner=importlib.import_module('tools.setup.native_startup_runner')
        self.tmp=tempfile.TemporaryDirectory(prefix='hc-synthetic-startup-run-')
        self.addCleanup(self.tmp.cleanup); self.root=Path(self.tmp.name)
        self.server=self.root/'server'
        mission=self.server/'mpmissions/dayzOffline.chernarusplus'; mission.mkdir(parents=True)
        (mission/'init.c').write_bytes(STOCK)
        (self.server/'DayZServer_x64.exe').write_bytes(b'SYNTHETIC NOT EXECUTABLE')
        (self.server/'battleye').mkdir()
        (self.server/'battleye/BEServer_x64.dll').write_bytes(b'SYNTHETIC DLL')
        self.source=self.root/'fixture.pbo'; self.source.write_bytes(pbo.pack({'config.cpp':b'// SYNTHETIC'}))
        self.prefix=self.root/'prefix'; self.prefix.mkdir()
        self.scripts=self.root/'interfaces'
        for name,tokens in probe.INTERFACES.items():
            path=self.scripts/name; path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('\n'.join(tokens))
        self.experiment=self.root/'fresh'; self.now=0.
        self.process=Mock(pid=123456789,returncode=None)

    def invoke(self,**options):
        return self.runner.run(self.server,self.source,self.experiment,self.prefix,self.scripts,
            **dict(dict(seconds=25,execute=True),**options))

    def mocked(self,complete_at=3,mutate=None,log_delay=0,validation_delay=0,
               cleanup_delay=1,cleanup_error=False,survivor=False,death=False,
               final_complete=False,final_error=False,final_drift=False,final_skipped=False,
               staging_delay=0,final_poll_delay=0,preflight_code=1,foreign=False,
               final_input_drift=None,final_extra=None,ready_at=None,publication_delay=0,
               engine_crash=False,final_engine_crash=False,**options):
        original_file=Path.is_file; prepare=probe.prepare_probe; validate=probe.validate_result
        publish=self.runner._publish_report
        emitted=False; validated=False
        def write_receipt(partial=False):
            marker=json.loads((self.experiment/'startup.chernarusplus'/probe.MARKER).read_text())
            row=receipt(probe,run_id=marker['run_id'],mode=marker['mode'])
            row.update(startup_allowance_seconds=marker['clock_policy']['startup_seconds'],
                       outer_budget_seconds=marker['clock_policy']['total_seconds'])
            if ready_at is not None:
                row.update(startup_elapsed_seconds=ready_at-1,elapsed_seconds=self.now-ready_at)
            if partial: row.update(complete=0,callbacks_detached=0)
            if mutate: mutate(row)
            (self.experiment/'profiles'/probe.RESULT).write_text(json.dumps(row))
        def logs(path):
            nonlocal emitted
            text='[HollowCountry] Server initialized; SYNTHETIC'
            if engine_crash:text+='\nENGINE    (F): Crashed'
            if path==self.experiment:
                if final_input_drift:
                    target = self.experiment / final_input_drift
                    target.write_bytes(target.read_bytes() + b" SYNTHETIC DRIFT")
                if final_extra:
                    target = self.experiment / final_extra
                    if target.suffix:
                        target.write_bytes(b"SYNTHETIC EXTRA")
                    else:
                        target.mkdir()
                if final_complete: write_receipt()
                if final_error: text+='\nSCRIPT (E): synthetic final error'
                if final_engine_crash:text+='\nENGINE    (F): Crashed'
                if final_drift:
                    (self.experiment/'profiles'/probe.RESULT).write_text('{}')
                return text,{},({'synthetic':'unreadable'} if final_skipped else {})
            if complete_at is not None and self.now>=complete_at and not emitted:
                write_receipt(); emitted=True
            elif ready_at is not None and self.now>=ready_at and not emitted:
                write_receipt(partial=True)
            self.now+=log_delay
            return text,{},{}
        def sleep(seconds): self.now+=seconds
        def poll():
            nonlocal validated
            if validated: self.now+=final_poll_delay; validated=False
            return 1 if death else None
        def stop(process,grace=5):
            self.assertIs(process,self.process); self.now+=cleanup_delay
            if cleanup_error: raise RuntimeError('synthetic cleanup failure')
            process.returncode=-15; return True
        def stage(*args,**kwargs):
            result=prepare(*args,**kwargs); self.now+=staging_delay; return result
        def check(*args,**kwargs):
            nonlocal validated
            result=validate(*args,**kwargs); self.now+=validation_delay; validated=True; return result
        def preflight(*args,**kwargs):
            if foreign:
                self.experiment.mkdir(); (self.experiment/'foreign').write_text('other owner')
            return Mock(returncode=preflight_code)
        def delayed_publish(*args):
            self.now+=publication_delay
            return publish(*args)
        self.process.poll.side_effect=poll
        with ExitStack() as stack:
            stack.enter_context(patch.object(Path,'is_file',lambda p:True if p==self.runner.WINE else original_file(p)))
            stack.enter_context(patch.object(self.runner.shutil,'which',return_value='/synthetic/xvfb-run'))
            stack.enter_context(patch.object(self.runner.subprocess,'run',side_effect=preflight))
            self.launch=stack.enter_context(patch.object(self.runner.subprocess,'Popen',return_value=self.process))
            self.stop=stack.enter_context(patch.object(self.runner.wine,'stop_group',side_effect=stop))
            stack.enter_context(patch.object(self.runner.wine,'group_alive',return_value=survivor))
            stack.enter_context(patch.object(self.runner.wine,'collect_logs',side_effect=logs))
            stack.enter_context(patch.object(self.runner.time,'monotonic',side_effect=lambda:self.now))
            stack.enter_context(patch.object(self.runner.time,'sleep',side_effect=sleep))
            stack.enter_context(patch.object(probe,'prepare_probe',side_effect=stage))
            stack.enter_context(patch.object(probe,'validate_result',side_effect=check))
            stack.enter_context(patch.object(self.runner,'_publish_report',side_effect=delayed_publish))
            return self.invoke(**options)

    def test_execute_required_before_any_process_or_staging(self):
        with patch.object(self.runner.subprocess,'Popen') as launch, patch.object(self.runner.subprocess,'run') as cmd:
            for value in (False,1,None):
                with self.assertRaises(ValueError): self.invoke(execute=value)
        launch.assert_not_called(); cmd.assert_not_called(); self.assertFalse(self.experiment.exists())

    def test_bad_budget_or_mode_refused_without_launch(self):
        with patch.object(self.runner.subprocess,'Popen') as launch:
            for values in (dict(seconds=181),dict(seconds=14),dict(seconds=True),dict(mode='other')):
                with self.assertRaises(ValueError): self.invoke(**values)
        launch.assert_not_called(); self.assertFalse(self.experiment.exists())

    def test_live_receipt_is_admitted_then_cleanup_observed(self):
        result=self.mocked()
        self.assertEqual('startup-control-completed',result['status'])
        self.assertTrue(result['receipt_admitted_before_cleanup'])
        self.assertTrue(result['process_cleanup_confirmed']); self.assertLess(self.now,10)

    def test_fatal_engine_crash_stops_polling_and_revokes_prior_admission(self):
        for index,options in enumerate((dict(engine_crash=True,complete_at=None),dict(final_engine_crash=True))):
            with self.subTest(options=options):
                self.experiment=self.root/('fatal-'+str(index));self.now=0
                result=self.mocked(**options)
                self.assertEqual('engine-crash',result['status'])
                self.assertTrue(result['engine_error_observed'])
                self.assertIsNone(result['receipt'])
                self.assertLess(self.now,10)
                self.assertTrue(result['process_cleanup_confirmed'])
        self.assertFalse(result['gameplay_acceptance']); self.assertEqual(0,result['client_count'])
        self.assertEqual(result,json.loads((self.experiment/self.runner.REPORT).read_text()))
        self.assertTrue(self.launch.call_args.kwargs['start_new_session'])
        command=self.launch.call_args.args[0]
        self.assertIn('-mission='+self.runner.wine.win(self.experiment/'startup.chernarusplus'),command)
        settings=json.loads((self.experiment/'profiles/HollowCountry/settings.json').read_text())
        self.assertTrue(all(v is False for k,v in settings.items() if k.startswith('Enable')))

    def test_ce_disabled_remains_startup_control_only(self):
        result=self.mocked(mode='ce-disabled-control')
        self.assertEqual('startup-control-completed',result['status'])
        self.assertEqual('ce-disabled-control',result['receipt']['mode'])
        self.assertFalse(result['gameplay_acceptance'])

    def test_without_addon_control_changes_only_mod_argument_and_keeps_pins(self):
        with patch.object(self.runner.secrets,'token_hex',return_value='a'*32):
            with_addon=self.mocked()
            normal_command=list(self.launch.call_args.args[0])
            normal_root=self.runner.wine.win(self.experiment)
            self.experiment=self.root/'fresh-without-addon'; self.now=0
            self.process.returncode=None
            without_addon=self.mocked(without_addon_control=True)
        control_command=self.launch.call_args.args[0]
        control_root=self.runner.wine.win(self.experiment)
        expected=[arg.replace(normal_root,'EXPERIMENT') for arg in normal_command
                  if not arg.startswith('-mod=')]
        self.assertEqual(expected,[arg.replace(control_root,'EXPERIMENT') for arg in control_command])
        self.assertEqual(self.runner.SUCCESS,without_addon['status'])
        self.assertFalse(without_addon['addon_loaded'])
        self.assertFalse(without_addon['addon_load_requested'])
        self.assertEqual('without-addon-control',without_addon['control_label'])
        self.assertEqual('stock-ce',without_addon['mode'])
        self.assertFalse(without_addon['gameplay_acceptance'])
        self.assertFalse(without_addon['addon_feature_flags_enabled'])
        self.assertTrue(with_addon['addon_load_requested'])
        self.assertIsNone(with_addon['addon_loaded'])  # -mod alone is not observed loading.
        for field in ('pbo_sha256','settings_sha256','config_sha256','server_sha256',
                      'battleye_sha256','mission_manifest_sha256'):
            self.assertEqual(with_addon[field],without_addon[field],field)
        self.assertEqual(self.source.read_bytes(),
            (self.experiment/'@HollowCountry/addons/hollowcountry.pbo').read_bytes())

    def test_without_addon_control_still_refuses_invalid_pbo_before_launch(self):
        self.source.write_bytes(b'SYNTHETIC INVALID PBO')
        result=self.mocked(without_addon_control=True)
        self.assertEqual('probe-error',result['status']); self.launch.assert_not_called()
        self.assertFalse(self.experiment.exists())

    def test_without_addon_control_still_rejects_staged_pbo_drift(self):
        result=self.mocked(without_addon_control=True,
            final_input_drift='@HollowCountry/addons/hollowcountry.pbo')
        self.assertEqual('input-drift',result['status']); self.assertIsNone(result['receipt'])

    def test_without_addon_control_timeout_does_not_change_ce_mode_or_admit(self):
        result=self.mocked(without_addon_control=True,complete_at=None)
        self.assertEqual('timeout',result['status']); self.assertIsNone(result['receipt'])
        self.assertEqual('stock-ce',result['mode']); self.assertFalse(result['addon_loaded'])
        self.assertFalse(result['gameplay_acceptance'])

    def test_without_addon_flag_requires_exact_bool_before_process_or_staging(self):
        with patch.object(self.runner.subprocess,'Popen') as launch,patch.object(self.runner.subprocess,'run') as cmd:
            for value in (1,0,None,'true',1.0):
                with self.subTest(value=value),self.assertRaises(ValueError):
                    self.invoke(without_addon_control=value)
        launch.assert_not_called(); cmd.assert_not_called(); self.assertFalse(self.experiment.exists())

    def test_without_addon_cli_is_explicit_and_preserves_clock_options(self):
        paths=[]
        for name in ('server-root','source-pbo','experiment','prefix','scripts-root'):
            paths.extend(['--'+name,str(self.root/name)])
        with patch.object(self.runner,'run',return_value=dict(status=self.runner.SUCCESS)) as run:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0,self.runner.main(paths+['--without-addon-control',
                    '--startup-seconds','600','--seconds','674','--execute']))
        self.assertIs(True,run.call_args.kwargs['without_addon_control'])
        self.assertEqual('stock-ce',run.call_args.kwargs['mode'])
        self.assertEqual(600,run.call_args.kwargs['startup_seconds'])
        self.assertEqual(674,run.call_args.kwargs['seconds'])

    def test_explicit_600_startup_can_finish_stock_ce_after_old_outer_limit(self):
        result=self.mocked(complete_at=550,seconds=674,startup_seconds=600,
            mutate=lambda row:row.update(startup_elapsed_seconds=540.))
        self.assertEqual(self.runner.SUCCESS,result['status'])
        self.assertEqual('stock-ce',result['mode'])
        self.assertEqual(600,result['startup_allowance_seconds'])
        self.assertEqual(60,result['fixture_budget_seconds'])
        self.assertEqual(12,result['cleanup_reserve_seconds'])
        self.assertLessEqual(self.now,674)

    def test_startup_allowance_expires_without_readiness_despite_larger_total(self):
        result=self.mocked(complete_at=None,seconds=674,startup_seconds=600)
        self.assertEqual('timeout',result['status'])
        self.assertEqual('startup',result['timeout_phase'])
        self.assertLessEqual(self.now,602)

    def test_long_total_requires_explicit_valid_startup_option(self):
        with patch.object(self.runner.subprocess,'Popen') as launch:
            for args in (dict(seconds=674),dict(seconds=674,startup_seconds=True),
                         dict(seconds=674,startup_seconds=601),
                         dict(seconds=671,startup_seconds=600),
                         dict(seconds=675,startup_seconds=600),dict(startup_seconds=600)):
                with self.subTest(args=args),self.assertRaises(ValueError): self.invoke(**args)
        launch.assert_not_called(); self.assertFalse(self.experiment.exists())

    def test_phase_budget_anchors_fixture_once_and_rejects_clock_rollback(self):
        with patch.object(self.runner.time,'monotonic',side_effect=lambda:self.now):
            budget=self.runner._StartupBudget(674,600)
            self.now=550; budget.observe_ready(2.,540.)
            self.assertEqual(608,budget.fixture_deadline)
            self.now=560; budget.observe_ready(4.,540.)
            self.assertEqual(608,budget.fixture_deadline)
            with self.assertRaises(ValueError): budget.observe_ready(1.,540.)
            self.now=608
            with self.assertRaises(self.runner._Expired): budget.check()
            self.now=559
            with self.assertRaises(ValueError): budget.now()

    def test_partial_readiness_starts_separate_fixture_budget_and_never_renews_it(self):
        result=self.mocked(ready_at=550,complete_at=620,seconds=674,startup_seconds=600)
        self.assertEqual('timeout',result['status'])
        self.assertEqual('fixture',result['timeout_phase'])
        self.assertEqual(550,result['readiness_observed_outer_seconds'])
        self.assertEqual(610,result['fixture_deadline_outer_seconds'])
        self.assertIsNone(result['receipt']); self.assertLessEqual(self.now,612)

    def test_readiness_can_extend_past_startup_deadline_without_resetting_outer(self):
        result=self.mocked(ready_at=590,complete_at=620,seconds=674,startup_seconds=600)
        self.assertEqual(self.runner.SUCCESS,result['status'])
        self.assertEqual(650,result['fixture_deadline_outer_seconds'])
        self.assertEqual(674,result['outer_budget_seconds'])

    def test_cleanup_has_own_twelve_second_cap_even_with_large_unused_total(self):
        result=self.mocked(complete_at=550,cleanup_delay=13,seconds=674,startup_seconds=600,
            mutate=lambda row:row.update(startup_elapsed_seconds=540.))
        self.assertNotEqual(self.runner.SUCCESS,result['status'])
        self.assertIsNone(result['receipt'])
        self.assertEqual('cleanup',result['timeout_phase'])

    def test_default_total_is_still_ninety_without_implicit_long_startup(self):
        result=self.mocked(complete_at=None,seconds=90)
        self.assertEqual('timeout',result['status'])
        self.assertEqual(90,result['outer_budget_seconds'])
        self.assertEqual(78,result['startup_allowance_seconds'])
        self.assertFalse(result['startup_option_explicit'])
        self.assertLessEqual(self.now,90)

    def test_publication_timeout_reports_total_overrun_even_when_cleanup_limit_is_earlier(self):
        result=self.mocked(publication_delay=30)
        self.assertIsNone(result['receipt'])
        self.assertTrue(result['outer_budget_exceeded'])
        self.assertEqual('outer-budget-exceeded',result['status'])

    def test_publication_only_cleanup_overrun_is_not_reported_as_total_overrun(self):
        result=self.mocked(publication_delay=12)
        self.assertIsNone(result['receipt'])
        self.assertFalse(result['outer_budget_exceeded'])
        self.assertEqual('cleanup-budget-exceeded',result['status'])

    def test_phase_transition_cannot_cross_startup_limit_between_clock_reads(self):
        with patch.object(self.runner.time,'monotonic',side_effect=[0.,599.,600.,600.]):
            budget=self.runner._StartupBudget(674,600)
            with self.assertRaises(self.runner._Expired): budget.observe_ready(0,599.)

    def test_init_only_and_late_final_receipt_never_pass(self):
        result=self.mocked(complete_at=None,final_complete=True)
        self.assertEqual('timeout',result['status']); self.assertIsNone(result['receipt'])
        self.assertFalse(result['receipt_admitted_before_cleanup'])
        self.assertTrue(result['receipt_present_final']); self.assertLessEqual(self.now,25)

    def test_dead_process_cannot_admit_existing_receipt(self):
        result=self.mocked(complete_at=0,death=True)
        self.assertEqual('process-exited',result['status']); self.assertIsNone(result['receipt'])

    def test_stale_nonce_or_missing_callback_or_failed_receipt_refused(self):
        for index,change in enumerate((dict(run_id='b'*32),dict(frame_entries=0),dict(failed=1),dict(complete=0))):
            self.experiment=self.root/('case'+str(index)); self.now=0
            self.process.returncode=None
            result=self.mocked(mutate=lambda row:row.update(change))
            self.assertNotEqual('startup-control-completed',result['status']); self.assertIsNone(result['receipt'])

    def test_slow_validation_cannot_admit_after_deadline(self):
        result=self.mocked(complete_at=12,validation_delay=2)
        self.assertEqual('timeout',result['status']); self.assertIsNone(result['receipt'])

    def test_slow_final_poll_cannot_admit_after_deadline(self):
        result=self.mocked(complete_at=12,final_poll_delay=2)
        self.assertEqual('timeout',result['status']); self.assertIsNone(result['receipt'])

    def test_slow_logs_cannot_admit_after_deadline(self):
        result=self.mocked(complete_at=12,log_delay=2)
        self.assertEqual('timeout',result['status']); self.assertIsNone(result['receipt'])

    def test_staging_overrun_has_no_launch(self):
        result=self.mocked(staging_delay=14)
        self.assertEqual('timeout',result['status']); self.launch.assert_not_called()

    def test_cleanup_error_survivor_and_overrun_revoke(self):
        for index,options in enumerate((dict(cleanup_error=True),dict(survivor=True),dict(cleanup_delay=30))):
            self.experiment=self.root/('case'+str(index)); self.now=0; self.process.returncode=None
            result=self.mocked(**options)
            self.assertNotEqual('startup-control-completed',result['status']); self.assertIsNone(result['receipt'])

    def test_final_error_or_changed_receipt_or_skipped_logs_revoke(self):
        for index,options in enumerate((dict(final_error=True),dict(final_drift=True),dict(final_skipped=True))):
            self.experiment=self.root/('case'+str(index)); self.now=0; self.process.returncode=None
            result=self.mocked(**options)
            self.assertNotEqual('startup-control-completed',result['status']); self.assertIsNone(result['receipt'])

    def test_process_discovery_failure_or_existing_process_refuse_launch(self):
        for code in (0,2):
            result=self.mocked(preflight_code=code)
            self.assertEqual('probe-error',result['status']); self.launch.assert_not_called()
        self.assertFalse(self.experiment.exists())

    def test_foreign_mkdir_race_never_receives_owned_report(self):
        result=self.mocked(foreign=True)
        self.assertEqual('probe-error',result['status']); self.launch.assert_not_called()
        self.assertEqual(['foreign'],[p.name for p in self.experiment.iterdir()])


    def test_final_launch_input_drift_revokes_receipt(self):
        for index, relative in enumerate((
                "startup.chernarusplus/init.c",
                "@HollowCountry/addons/hollowcountry.pbo",
                "serverDZ.cfg", "battleye/BEServer_x64.dll")):
            with self.subTest(relative=relative):
                self.experiment = self.root / ("drift-" + str(index))
                self.now = 0
                self.process.returncode = None
                result = self.mocked(final_input_drift=relative)
                self.assertEqual("input-drift", result["status"])
                self.assertIsNone(result["receipt"])

    def test_new_mission_file_or_directory_revokes_receipt(self):
        for index, relative in enumerate((
                "startup.chernarusplus/unlisted.c",
                "startup.chernarusplus/unlisted-directory")):
            with self.subTest(relative=relative):
                self.experiment = self.root / ("extra-" + str(index))
                self.now = 0
                self.process.returncode = None
                result = self.mocked(final_extra=relative)
                self.assertEqual("input-drift", result["status"])
                self.assertIsNone(result["receipt"])


class StartupPublicationTests(unittest.TestCase):
    """In-memory I/O boundaries; execute the actual report publisher/reader."""

    def setUp(self):
        from types import SimpleNamespace
        self.runner = importlib.import_module("tools.setup.native_startup_runner")
        self.root = Path("/synthetic-startup-publication")
        self.path = self.root / self.runner.REPORT
        self.files = {}
        self.now = 1.0
        self.events = []
        self.fail_write = False
        self.fail_final_read = False
        self.fail_delete = False
        self.fail_rename = False
        self.late_read = False
        self.report = dict(schema=1, run_id="a"*32, status=self.runner.SUCCESS,
                           receipt={"synthetic": True})
        self.budget = SimpleNamespace(deadline=10.0, now=lambda: self.now)
        stack = ExitStack()
        self.addCleanup(stack.close)

        def write(path, data):
            self.events.append(("write", path))
            if path in self.files:
                raise FileExistsError(path)
            self.files[path] = data
            if self.fail_write and path.name.endswith(".tmp"):
                raise OSError("synthetic staged readback failure")

        def read(path, limit):
            self.events.append(("read", path))
            if path == self.path and self.fail_final_read:
                raise OSError("synthetic final readback failure")
            data = self.files[path]
            if len(data) > limit:
                raise ValueError("synthetic bounded read")
            if path == self.path and self.late_read:
                self.now = 11
            return data

        def rename(source, target):
            self.events.append(("rename", target))
            if self.fail_rename:
                raise OSError("synthetic rename failure")
            self.files[target] = self.files.pop(source)

        def unlink(path, **kwargs):
            self.events.append(("unlink", path))
            if path == self.path and self.fail_delete:
                raise OSError("synthetic undeletable report")
            if path in self.files:
                del self.files[path]
            elif not kwargs.get("missing_ok"):
                raise FileNotFoundError(path)

        for obj, name, value in (
                (self.runner, "_safe", lambda p: Path(p)),
                (self.runner, "_write", write),
                (probe, "_read", read),
                (self.runner.os, "replace", rename),
                (Path, "exists", lambda p: p in self.files),
                (Path, "unlink", unlink)):
            stack.enter_context(patch.object(obj, name, value))

    def publish(self):
        return self.runner._publish_report(self.path, self.report, self.budget)

    def test_success_is_verified_before_pending_guard_is_removed_last(self):
        self.publish()
        self.assertEqual(self.report, self.runner.read_report(self.path))
        guard = self.path.with_name(self.path.name + ".pending")
        self.assertNotIn(guard, self.files)
        before_reader = self.events.index(("unlink", guard))
        self.assertEqual(("read", self.path), self.events[before_reader - 1])

    def test_staged_write_failure_never_publishes_success(self):
        self.fail_write = True
        with self.assertRaises(OSError):
            self.publish()
        self.assertNotIn(self.path, self.files)

    def test_failed_final_read_stays_untrusted_even_when_report_cannot_be_removed(self):
        self.fail_final_read = self.fail_delete = True
        with self.assertRaises(OSError):
            self.publish()
        self.assertEqual(self.runner.SUCCESS,
                         json.loads(self.files[self.path])["status"])
        self.fail_final_read = False
        with self.assertRaises(ValueError):
            self.runner.read_report(self.path)

    def test_rename_failure_never_publishes_success(self):
        self.fail_rename = True
        with self.assertRaises(OSError):
            self.publish()
        self.assertNotIn(self.path, self.files)

    def test_late_final_readback_cannot_commit_success(self):
        self.late_read = True
        with self.assertRaises(self.runner._Expired):
            self.publish()
        with self.assertRaises((ValueError, KeyError)):
            self.runner.read_report(self.path)

    def test_cleanup_deadline_also_guards_final_publication(self):
        self.budget.deadline=100
        self.budget.cleanup_deadline=10
        self.late_read=True
        with self.assertRaises(self.runner._Expired): self.publish()
        with self.assertRaises((ValueError,KeyError)): self.runner.read_report(self.path)

    def test_existing_report_is_not_overwritten(self):
        self.files[self.path] = b"foreign report"
        with self.assertRaises(FileExistsError):
            self.publish()
        self.assertEqual(b"foreign report", self.files[self.path])

    def test_guard_appearing_during_read_invalidates_report(self):
        self.publish()
        original = probe._read

        def changed(path, limit):
            data = original(path, limit)
            self.files[self.path.with_name(self.path.name + ".pending")] = b"pending"
            return data

        with patch.object(probe, "_read", side_effect=changed):
            with self.assertRaises(ValueError):
                self.runner.read_report(self.path)


if __name__=='__main__': unittest.main()
