"""Synthetic processes/clocks/interfaces/receipts ONLY; no DayZ launch."""
from contextlib import ExitStack
import importlib
import json
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch
import unittest

from tools.package import pbo
from tools.setup import native_startup_probe as probe
from tests.unit.test_native_startup_probe import STOCK, receipt


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
               final_input_drift=None,final_extra=None,**options):
        original_file=Path.is_file; prepare=probe.prepare_probe; validate=probe.validate_result
        emitted=False; validated=False
        def write_receipt():
            marker=json.loads((self.experiment/'startup.chernarusplus'/probe.MARKER).read_text())
            row=receipt(probe,run_id=marker['run_id'],mode=marker['mode'])
            if mutate: mutate(row)
            (self.experiment/'profiles'/probe.RESULT).write_text(json.dumps(row))
        def logs(path):
            nonlocal emitted
            text='[HollowCountry] Server initialized; SYNTHETIC'
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
                if final_drift:
                    (self.experiment/'profiles'/probe.RESULT).write_text('{}')
                return text,{},({'synthetic':'unreadable'} if final_skipped else {})
            if complete_at is not None and self.now>=complete_at and not emitted:
                write_receipt(); emitted=True
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
