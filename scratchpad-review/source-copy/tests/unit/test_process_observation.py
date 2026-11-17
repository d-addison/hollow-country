"""Synthetic procfs/log metadata only; never launch or observe a game process."""
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class ProcessObservationTests(unittest.TestCase):
    def setUp(self):
        self.mod=importlib.import_module('tools.setup.process_observation')
        self.tmp=tempfile.TemporaryDirectory(prefix='hc-synthetic-proc-')
        self.addCleanup(self.tmp.cleanup); self.root=Path(self.tmp.name)
        self.proc=self.root/'proc'; self.pid=123; self.pgid=77; self.now=0.
        (self.proc/str(self.pid)).mkdir(parents=True)
        self.log=self.root/'server.RPT'; self.log.write_bytes(b'synthetic')
        self.write_proc()

    def write_proc(self,*,start=456,pgid=77,user=100,system=20,rss=10,read=1000,write=500):
        fields=['S']+['0']*21
        for index,value in {2:pgid,11:user,12:system,17:2,19:start,20:1048576,21:rss}.items():
            fields[index]=str(value)
        path=self.proc/str(self.pid)
        (path/'stat').write_text(f'{self.pid} (synthetic ) worker) '+ ' '.join(fields)+'\n')
        (path/'status').write_text('VmRSS:\t40 kB\nVmHWM:\t48 kB\nThreads:\t2\n')
        (path/'io').write_text(f'rchar: 9000\nwchar: 8000\nread_bytes: {read}\nwrite_bytes: {write}\n')

    def pin(self,**options):
        return self.mod.pin_owned_process(self.pid,self.pgid,proc_root=self.proc,
                                         **dict(dict(platform='linux'),**options))

    def observer(self,**options):
        return self.mod.ProcessObserver(self.pin(),proc_root=self.proc,log_paths=[self.log],
            clock=lambda:self.now,**dict(dict(platform='linux',clock_ticks=100,page_size=4096),**options))

    def test_pins_exact_owned_identity_with_parentheses_in_comm(self):
        pin=self.pin()
        self.assertEqual('available',pin['status'])
        self.assertEqual((123,77,456),(pin['pid'],pin['process_group_id'],pin['starttime_ticks']))

    def test_first_sample_captures_raw_counters_and_marks_delta_baseline(self):
        row=self.observer().sample(); p=row['process']
        self.assertEqual('available',p['status']); self.assertEqual(100,p['utime_ticks'])
        self.assertEqual(20,p['stime_ticks']); self.assertEqual(40960,p['rss_bytes'])
        self.assertEqual(49152,p['vmhwm_bytes']); self.assertEqual(40960,p['vmrss_bytes'])
        self.assertEqual(1000,p['read_bytes']); self.assertEqual(500,p['write_bytes'])
        self.assertIsNone(p['cpu_seconds_delta']); self.assertEqual('baseline',p['delta_status'])
        self.assertEqual('baseline',row['logs'][0]['event'])

    def test_two_second_seam_has_no_sleep_or_catch_up_loop(self):
        observer=self.observer(); observer.sample()
        self.now=1.999
        with patch.object(self.mod,'_read',side_effect=AssertionError('early read')):
            self.assertIsNone(observer.sample())
        self.now=2; self.assertIsNotNone(observer.sample())
        self.now=100; self.assertIsNotNone(observer.sample())
        self.assertEqual(3,observer.report()['sample_count'])

    def test_cpu_io_deltas_and_log_growth_are_observed_not_liveness(self):
        observer=self.observer(); observer.sample()
        self.write_proc(user=250,system=70,read=1600,write=900)
        self.log.write_bytes(b'synthetic-more'); self.now=2
        row=observer.sample(); p=row['process']
        self.assertEqual(2,p['cpu_seconds_delta'])
        self.assertEqual(600,p['read_bytes_delta']); self.assertEqual(400,p['write_bytes_delta'])
        self.assertEqual(5,row['logs'][0]['growth_bytes'])
        self.assertFalse(observer.report()['liveness_proven'])

    def test_pid_reuse_rejects_all_counters_and_never_reattaches(self):
        observer=self.observer(); observer.sample(); self.write_proc(start=999); self.now=2
        row=observer.sample()['process']
        self.assertEqual('rejected',row['status']); self.assertEqual('pid_reused',row['reason'])
        self.assertNotIn('utime_ticks',row)
        self.write_proc(); self.now=4
        with patch.object(self.mod,'_read',side_effect=AssertionError('reattached')):
            self.assertEqual('rejected',observer.sample()['process']['status'])

    def test_identity_change_during_counter_read_discards_mixed_snapshot(self):
        observer=self.observer(); original=self.mod._read
        def read(path,limit):
            data=original(path,limit)
            if Path(path).name=='io': self.write_proc(start=999)
            return data
        with patch.object(self.mod,'_read',side_effect=read):
            row=observer.sample()['process']
        self.assertEqual('rejected',row['status']); self.assertNotIn('read_bytes',row)

    def test_process_group_mismatch_refused_at_pin_and_sampling(self):
        self.write_proc(pgid=88); pin=self.pin()
        self.assertEqual('rejected',pin['status'])
        self.write_proc(); observer=self.observer(); self.write_proc(pgid=88)
        self.assertEqual('rejected',observer.sample()['process']['status'])

    def test_missing_process_is_unavailable_not_zero_usage(self):
        observer=self.observer(); (self.proc/str(self.pid)/'stat').unlink()
        p=observer.sample()['process']
        self.assertEqual('unavailable',p['status']); self.assertEqual('missing',p['reason'])
        self.assertNotIn('rss_bytes',p)

    def test_io_access_error_retains_cpu_and_explicit_unknown_io(self):
        observer=self.observer(); original=self.mod._read
        def read(path,limit):
            if Path(path).name=='io': raise PermissionError('synthetic denied')
            return original(path,limit)
        with patch.object(self.mod,'_read',side_effect=read): p=observer.sample()['process']
        self.assertEqual('partial',p['status']); self.assertEqual(100,p['utime_ticks'])
        self.assertIsNone(p['read_bytes']); self.assertEqual('permission_denied',p['errors']['io'])

    def test_missing_or_malformed_status_and_io_fields_are_explicit(self):
        observer=self.observer()
        (self.proc/str(self.pid)/'status').write_text('VmRSS: wrong kB\n')
        (self.proc/str(self.pid)/'io').write_text('read_bytes: 2\n')
        p=observer.sample()['process']
        self.assertEqual('partial',p['status'])
        self.assertIsNone(p['vmrss_bytes']); self.assertIsNone(p['write_bytes'])
        self.assertTrue(p['errors'])

    def test_counter_rollback_never_becomes_negative_usage(self):
        observer=self.observer(); observer.sample(); self.write_proc(user=1,read=1,write=1); self.now=2
        p=observer.sample()['process']
        self.assertIsNone(p['cpu_seconds_delta']); self.assertIsNone(p['read_bytes_delta'])
        self.assertEqual('counter_rollback',p['errors']['cpu_delta'])

    def test_log_rotation_truncation_and_missing_are_explicit(self):
        observer=self.observer(); observer.sample()
        self.log.write_bytes(b'x'); self.now=2
        self.assertEqual('truncated',observer.sample()['logs'][0]['event'])
        self.log.rename(self.root/'old.RPT'); self.log.write_bytes(b'new'); self.now=4
        row=observer.sample()['logs'][0]
        self.assertEqual('replaced',row['event']); self.assertIsNone(row['growth_bytes'])
        self.log.unlink(); self.now=6
        self.assertEqual('unavailable',observer.sample()['logs'][0]['status'])

    def test_log_contents_are_never_read(self):
        observer=self.observer(); original=self.mod._read
        def read(path,limit):
            self.assertNotEqual(self.log,Path(path)); return original(path,limit)
        with patch.object(self.mod,'_read',side_effect=read): observer.sample()

    def test_symlink_inputs_and_logs_are_refused_without_following(self):
        observer=self.observer(); stat=self.proc/str(self.pid)/'stat'
        stat.unlink(); stat.symlink_to(self.log)
        self.assertEqual('unavailable',observer.sample()['process']['status'])
        stat.unlink(); self.write_proc(); self.log.unlink(); self.log.symlink_to(stat)
        self.now=2
        self.assertEqual('unavailable',observer.sample()['logs'][0]['status'])

    def test_nonlinux_reports_unavailable_without_proc_reads(self):
        with patch.object(self.mod,'_read',side_effect=AssertionError('nonlinux proc read')):
            pin=self.pin(platform='win32')
            observer=self.mod.ProcessObserver(pin,platform='win32',clock=lambda:0)
            row=observer.sample()['process']
        self.assertEqual('unavailable',row['status']); self.assertEqual('unsupported_platform',row['reason'])

    def test_sample_and_serialized_byte_budgets_are_finite(self):
        observer=self.observer(max_samples=2)
        observer.sample(); self.now=2; observer.sample(); self.now=4
        with patch.object(self.mod,'_read',side_effect=AssertionError('after cap')):
            self.assertIsNone(observer.sample())
        self.assertEqual('sample_limit',observer.report()['stopped_reason'])
        self.assertEqual(2,observer.report()['sample_count'])
        self.now=0; observer=self.observer(max_bytes=2048)
        for index in range(20): self.now=index*2; observer.sample()
        report=observer.report()
        self.assertEqual('byte_budget',report['stopped_reason'])
        encoded=self.mod.encode_report(report)
        self.assertLessEqual(len(encoded),2048); self.assertEqual(len(encoded),report['encoded_bytes'])

    def test_invalid_options_and_clock_fail_closed(self):
        for options in (dict(max_samples=0),dict(max_samples=513),dict(max_bytes=2047),
                        dict(max_bytes=True),dict(clock_ticks=0),dict(page_size=True)):
            with self.subTest(options=options),self.assertRaises(ValueError): self.observer(**options)
        observer=self.observer(); observer.sample(); self.now=-1
        self.assertIsNone(observer.sample()); self.assertEqual('clock_invalid',observer.report()['stopped_reason'])
        self.now=float('nan'); observer=self.observer()
        self.assertIsNone(observer.sample()); self.assertEqual('clock_invalid',observer.report()['stopped_reason'])

    def test_proc_input_byte_limits_and_duplicate_fields_fail_explicitly(self):
        observer=self.observer(); (self.proc/str(self.pid)/'stat').write_bytes(b' '*(self.mod.MAX_PROC_BYTES+1))
        self.assertEqual('unavailable',observer.sample()['process']['status'])
        self.write_proc(); observer=self.observer()
        (self.proc/str(self.pid)/'io').write_text('read_bytes: 1\nread_bytes: 2\nwrite_bytes: 3\n')
        self.assertEqual('partial',observer.sample()['process']['status'])

    def test_report_is_detached_and_json_safe(self):
        observer=self.observer(); observer.sample()
        report=observer.report(); report['samples'].clear()
        fresh=observer.report(); self.assertEqual(1,fresh['sample_count'])
        self.assertEqual(fresh,json.loads(self.mod.encode_report(fresh)))

    def test_identity_and_platform_metadata_cannot_escape_report_budget(self):
        identity=self.pin(); identity.update(status='unavailable',reason='x'*10000)
        with self.assertRaises(ValueError): self.mod.ProcessObserver(identity)
        with self.assertRaises(ValueError): self.pin(platform='x'*10000)

    def test_every_identity_outcome_rejects_noninteger_start_ticks(self):
        identity=self.pin()
        invalid=({'private_blob':'synthetic'},[],b'synthetic','456',True,1.0,-1,1<<64)
        for status in ('available','unavailable','rejected'):
            for value in invalid:
                with self.subTest(status=status,value_type=type(value).__name__):
                    identity.update(status=status,reason=None if status=='available' else 'missing',
                                    starttime_ticks=value)
                    with self.assertRaises(ValueError): self.mod.ProcessObserver(identity)

    def test_unobserved_identity_ticks_allow_only_none_or_bounded_integer(self):
        identity=self.pin()
        for status in ('unavailable','rejected'):
            for value in (None,0,(1<<64)-1):
                identity.update(status=status,reason='missing',starttime_ticks=value)
                observer=self.mod.ProcessObserver(identity,clock=lambda:0)
                identity['starttime_ticks']={'private_blob':'synthetic'}
                self.assertEqual(value,observer.report()['identity']['starttime_ticks'])
                self.assertEqual(value,observer.sample()['process']['starttime_ticks'])
        identity.update(status='available',reason=None,starttime_ticks=None)
        with self.assertRaises(ValueError): self.mod.ProcessObserver(identity)

    def test_constructor_rejects_encoded_base_and_reserves_stop_bytes(self):
        identity=self.pin(); identity.update(status='unavailable',reason='missing',starttime_ticks=None)
        root=Path('/'+'é'*255)
        self.assertLessEqual(len(str(root).encode()),512)
        options=dict(proc_root=root,platform='linux',clock=lambda:float('nan'),
                     clock_ticks=100,page_size=4096)
        with patch.object(self.mod,'_read',side_effect=AssertionError('constructor reads')):
            generous=self.mod.ProcessObserver(identity,max_bytes=4096,**options)
            base_size=len(self.mod.encode_report(generous.report()))
            # This base fits 2KiB, but even its clock-stop report does not.
            self.assertLessEqual(base_size,2048)
            self.assertIsNone(generous.sample())
            self.assertGreater(len(self.mod.encode_report(generous.report())),2048)
            for limit in (2048,base_size+10):
                with self.subTest(limit=limit),self.assertRaises(ValueError):
                    self.mod.ProcessObserver(identity,max_bytes=limit,**options)
        self.assertIsNone(generous.sample())
        report=generous.report()
        self.assertEqual('clock_invalid',report['stopped_reason'])
        encoded=self.mod.encode_report(report)
        self.assertLessEqual(len(encoded),4096)
        self.assertEqual(len(encoded),report['encoded_bytes'])

    def test_extreme_clock_and_clock_access_error_are_explicit(self):
        observer=self.observer(); observer.clock=lambda:10**1000
        self.assertIsNone(observer.sample())
        self.assertEqual('clock_invalid',observer.report()['stopped_reason'])
        observer=self.observer()
        def denied(): raise OSError('synthetic clock error')
        observer.clock=denied
        self.assertIsNone(observer.sample())
        self.assertEqual('clock_invalid',observer.report()['stopped_reason'])

    def test_hardlinks_duplicate_logs_and_log_count_budget(self):
        duplicate=self.root/'duplicate.RPT'; os.link(self.log,duplicate)
        self.assertEqual('unavailable',self.observer().sample()['logs'][0]['status'])
        for paths in ([self.log]*2,[self.root/str(n) for n in range(9)]):
            with self.assertRaises(ValueError): self.mod.ProcessObserver(self.pin(),log_paths=paths)


if __name__=='__main__': unittest.main()
