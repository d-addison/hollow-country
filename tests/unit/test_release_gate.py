"""Release orchestration fakes every native operation."""
import contextlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, call, patch

from tools.release import compile_gate, release_gate as gate
from tools.release.host_lock import LockRefused
from tools.release import acceptance_targets as policy
from tests.unit.test_rpt_config_audit import SAMPLE_LINES

TARGETS = policy.load_targets()


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        # Synthetic policy measurements; production category 15 is unmeasured.
        self.targets = dict(TARGETS, rpt_category_ceilings={key: 0 for key in TARGETS['rpt_category_ceilings']})
        policy_patch = patch.object(gate, 'load_targets', return_value=self.targets)
        policy_patch.start()
        self.addCleanup(policy_patch.stop)

    def args(self, **kwargs):
        return SimpleNamespace(commit='a' * 40, **kwargs)

    def test_order(self):
        steps = Mock()
        with patch.object(gate, 'host_lock', return_value=contextlib.nullcontext()):
            result = gate.run_gate(self.args(), steps)
        self.assertTrue(result['passed'])
        self.assertEqual([call[0] for call in steps.mock_calls],
                         ['compile', 'manifest', 'upgrade', 'soak', 'activity', 'client', 'stop'])

    def test_first_failure_stops_progress_and_cleans_up(self):
        for failed in ('compile', 'manifest', 'upgrade', 'soak', 'activity', 'client'):
            steps = Mock()
            getattr(steps, failed).side_effect = gate.Refused('failed')
            with patch.object(gate, 'host_lock', return_value=contextlib.nullcontext()):
                result = gate.run_gate(self.args(), steps)
            self.assertFalse(result['passed'])
            self.assertEqual(result['failed_step'], failed)
            self.assertEqual(steps.mock_calls[-1][0], 'stop')
            self.assertEqual(steps.mock_calls[-2][0], failed)

    def test_lock_refusal_runs_nothing(self):
        steps = Mock()
        with patch.object(gate, 'host_lock', side_effect=LockRefused('native host busy: holder=friendcycle')):
            result = gate.run_gate(self.args(), steps)
        self.assertFalse(result['passed'])
        self.assertEqual(result['failed_step'], 'host_lock')
        self.assertFalse(steps.mock_calls)

    def test_manifest_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp)
            manifest = bundle / 'BUILD_MANIFEST.json'
            manifest.write_text(json.dumps({'commit': 'b' * 40}))
            steps = gate.NativeSteps(self.args(bundle=bundle))
            with self.assertRaisesRegex(gate.Refused, 'commit mismatch'):
                steps.manifest()
            manifest.write_text(json.dumps({'commit': 'a' * 40}))
            with self.assertRaisesRegex(gate.Refused, 'strict generated-artefact'):
                steps.manifest()
            waived = {'strict': False, 'waived_unavailable': [{'artefact': 'x', 'reason': 'unavailable'}]}
            manifest.write_text(json.dumps({'commit': 'a' * 40, 'generated_digests': waived}))
            with self.assertRaisesRegex(gate.Refused, 'strict generated-artefact'):
                steps.manifest()
            strict = {'strict': True, 'waived_unavailable': []}
            manifest.write_text(json.dumps({'commit': 'a' * 40, 'generated_digests': strict}))
            steps.manifest()

    def test_compile_requires_exact_status(self):
        steps = gate.NativeSteps(self.args())
        for output, accepted in [('compile_gate: PASS status=timeout', False),
                                  ('compile_gate: FAIL status=mission-loaded-runtime-json', False),
                                  ('compile_gate: PASS status=mission-loaded-runtime-json', True)]:
            with patch.object(gate, 'command', return_value=output):
                if accepted:
                    steps.compile()
                else:
                    with self.assertRaises(gate.Refused):
                        steps.compile()

    def test_client_running_and_unknown_refusal(self):
        for state, reads in (('running', 1), ('unknown', compile_gate.CLIENT_STATE_READS)):
            with patch('tools.setup.winproc.process_state', return_value=state) as query:
                with self.assertRaisesRegex(ValueError, 'client state=' + state):
                    compile_gate.require_client_idle(sleep=lambda seconds: None)
                self.assertEqual(query.call_args_list, [call('DayZ_x64.exe')] * reads)
        with patch('tools.setup.winproc.process_state', return_value='gone'):
            compile_gate.require_client_idle()
        with patch('tools.setup.winproc.process_state', side_effect=('unknown', 'gone')) as query:
            compile_gate.require_client_idle(sleep=lambda seconds: None)
            self.assertEqual(query.call_args_list, [call('DayZ_x64.exe')] * 2)
        with patch('tools.setup.winproc.process_state') as query:
            compile_gate.require_client_idle(True)
            query.assert_not_called()

    def test_release_activity_option_is_required(self):
        args = self.args()
        steps = gate.NativeSteps(args)
        steps.rpt, steps.client_rpt = Path('server.RPT'), Path('client.RPT')
        with patch.object(gate, 'capture') as call:
            steps.activity()
        self.assertIn('--release', call.call_args.args[1])

    def test_audit_uses_common_summary_and_perf(self):
        with tempfile.TemporaryDirectory() as temp:
            rpt = Path(temp) / 'test.RPT'
            rpt.write_text('12:00:00 Player connect enabled\n12:00:00 [CE][Hive] :: Init sequence finished\n12:00:01 [HC Ready] module=Core enabled=true ready=true\n')
            with patch.object(gate, 'perf_rules', return_value=iter([f"perf_rule=R2 ms={TARGETS['perf_r2_max_ms'] + 0.001}"])):
                with self.assertRaisesRegex(gate.Refused, 'R2'):
                    gate.audit(rpt)
            for line in ('SCRIPT    (E): error', 'VME', '[HC SelfTest] name=x pass=false',
                         'store quarantined', "Can't load texture"):
                rpt.write_text(line + '\n')
                with self.assertRaises(gate.Refused):
                    gate.audit(rpt, client=True)

    def test_rpt_ceilings_count_every_category_at_boundary(self):
        header = ('12:00:00 Player connect enabled\n'
                  '12:00:00 [CE][Hive] :: Init sequence finished\n'
                  '12:00:01 [HC Ready] module=Core enabled=true ready=true\n')
        with tempfile.TemporaryDirectory() as temp:
            rpt = Path(temp) / 'synthetic.RPT'
            for category, sample in SAMPLE_LINES.items():
                with self.subTest(category=category):
                    measured = sample + '\n'
                    ceiling = len(measured.splitlines())
                    targets = dict(self.targets, rpt_category_ceilings={
                        **self.targets['rpt_category_ceilings'], str(category): ceiling})
                    rpt.write_text(header + measured)
                    gate.audit(rpt, targets=targets)
                    rpt.write_text(header + measured + measured)
                    with self.assertRaisesRegex(gate.Refused, f'R3 category={category} count='):
                        gate.audit(rpt, targets=targets)
                    # Provenance never subtracts dependency-caused diagnostics.
                    rpt.write_text(header + measured)
                    targets['rpt_category_ceilings'][str(category)] = 0
                    with self.assertRaisesRegex(gate.Refused, f'R3 category={category} count='):
                        gate.audit(rpt, targets=targets)

    def test_missing_ceiling_and_incomplete_census_fail_closed(self):
        header = ('12:00:00 Player connect enabled\n'
                  '12:00:00 [CE][Hive] :: Init sequence finished\n'
                  '12:00:01 [HC Ready] module=Core enabled=true ready=true\n')
        with tempfile.TemporaryDirectory() as temp:
            rpt = Path(temp) / 'synthetic.RPT'
            for key in self.targets['rpt_category_ceilings']:
                rpt.write_text(header)
                targets = dict(self.targets, rpt_category_ceilings={
                    **self.targets['rpt_category_ceilings'], key: None})
                with self.assertRaisesRegex(gate.Refused, 'ceiling unavailable'):
                    gate.audit(rpt, targets=targets)
            for line in ('Unknown synthetic diagnostic', 'x' * (gate.rpt_config_audit.MAX_LINE + 1)):
                rpt.write_text(header + line + '\n')
                with self.assertRaisesRegex(gate.Refused, 'R3 incomplete RPT census'):
                    gate.audit(rpt)

    def test_r4_requires_same_boot_timing_and_enforces_ratchet(self):
        limit = self.targets['readiness_ratchet_max_after_hive_seconds']
        def clock(seconds):
            return f'{int(seconds // 3600):02}:{int(seconds // 60 % 60):02}:{seconds % 60:06.3f}'
        header = '00:00:00 Player connect enabled\n00:00:00 [CE][Hive] :: Init sequence finished\n'
        ready = '[HC Ready] module=Core enabled=true ready=true\n'
        with tempfile.TemporaryDirectory() as temp:
            rpt = Path(temp) / 'synthetic.RPT'
            rpt.write_text(header + clock(limit) + ' ' + ready)
            gate.audit(rpt)
            rpt.write_text(header + clock(limit + 0.001) + ' ' + ready)
            with self.assertRaisesRegex(gate.Refused, 'R4'):
                gate.audit(rpt)
            rpt.write_text(header + clock(limit) + ' ' + ready)
            tighter = dict(self.targets, readiness_ratchet_max_after_hive_seconds=limit / 2)
            with self.assertRaisesRegex(gate.Refused, 'R4'):
                gate.audit(rpt, targets=tighter)
            for content in ('Player connect enabled\n' + ready,
                            header + ready,
                            header + clock(limit) + ' ' + ready + header):
                rpt.write_text(content)
                with self.assertRaisesRegex(gate.Refused, 'R4'):
                    gate.audit(rpt)

    def test_soak_duration_comes_from_targets(self):
        steps = gate.NativeSteps(self.args(client_profiles=Path('client'), bundle=Path('bundle')))
        with patch.object(steps, 'install'), patch.object(steps, 'boot') as boot, patch.object(gate, 'emit'):
            steps.soak()
        boot.assert_called_once_with(Path('bundle'), TARGETS['soak_minutes'])

    def test_error_limits_come_from_targets(self):
        cases = [('SCRIPT (E): synthetic', 'max_script_errors', False),
                 ('VME', 'max_vme_server', False),
                 ('VME', 'client_max_vme', True),
                 ('missing texture', 'client_max_missing_textures', True)]
        with tempfile.TemporaryDirectory() as temp:
            rpt = Path(temp) / 'test.RPT'
            header = '12:00:00 Player connect enabled\n12:00:00 [CE][Hive] :: Init sequence finished\n12:00:01 [HC Ready] module=Core enabled=true ready=true\n'
            for line, key, client in cases:
                with self.subTest(key=key):
                    limit = TARGETS[key]
                    rpt.write_text(header + (line + '\n') * limit)
                    gate.audit(rpt, client=client)
                    rpt.write_text(header + (line + '\n') * (limit + 1))
                    with self.assertRaises(gate.Refused):
                        gate.audit(rpt, client=client)
                    changed = dict(self.targets, **{key: limit + 1})
                    with patch.object(gate, 'load_targets', return_value=changed):
                        gate.audit(rpt, client=client)

    def test_perf_boundary_comes_from_targets(self):
        with tempfile.TemporaryDirectory() as temp:
            rpt = Path(temp) / 'test.RPT'
            rpt.write_text('12:00:00 Player connect enabled\n12:00:00 [CE][Hive] :: Init sequence finished\n12:00:01 [HC Ready] module=Core enabled=true ready=true\n')
            limit = TARGETS['perf_r2_max_ms']
            with patch.object(gate, 'perf_rules', return_value=[f'perf_rule=R2 ms={limit}']):
                gate.audit(rpt)
            with patch.object(gate, 'load_targets', return_value=dict(self.targets, perf_r2_max_ms=limit / 2)), \
                    patch.object(gate, 'perf_rules', return_value=[f'perf_rule=R2 ms={limit}']):
                with self.assertRaises(gate.Refused):
                    gate.audit(rpt)

    def test_missing_policy_refuses_before_native_steps(self):
        steps = Mock()
        with patch.object(gate, 'load_targets', side_effect=policy.TargetsError('acceptance targets missing keys')), \
                patch.object(gate, 'host_lock') as lock:
            result = gate.run_gate(self.args(), steps)
        self.assertFalse(result['passed'])
        self.assertEqual(result['failed_step'], 'acceptance_targets')
        self.assertIn('acceptance targets', result['reason'])
        lock.assert_not_called()
        self.assertFalse(steps.mock_calls)

    def test_cleanup_failure_prevents_pass(self):
        steps = Mock()
        steps.stop.side_effect = gate.Refused('graceful stop failed')
        with patch.object(gate, 'host_lock', return_value=contextlib.nullcontext()):
            self.assertFalse(gate.run_gate(self.args(), steps)['passed'])

    def test_upgrade_runs_previous_then_candidate_on_same_install(self):
        args = self.args(previous_bundle=Path('old'), bundle=Path('new'))
        steps = gate.NativeSteps(args)
        calls = Mock()
        steps.install, steps.boot, steps.stop = calls.install, calls.boot, calls.stop
        steps.upgrade()
        upgrade_minutes = calls.boot.call_args_list[0].args[1]
        self.assertGreater(upgrade_minutes, 0)
        self.assertEqual(calls.mock_calls, [
            unittest.mock.call.install(Path('old')), unittest.mock.call.boot(Path('old'), upgrade_minutes),
            unittest.mock.call.stop(), unittest.mock.call.install(Path('new')),
            unittest.mock.call.boot(Path('new'), upgrade_minutes), unittest.mock.call.stop()])

    def test_missing_previous_bundle_follows_upgrade_target(self):
        for required in (True, False):
            with self.subTest(required=required):
                targets = dict(TARGETS, upgrade_from_previous_release_required=required)
                steps = gate.NativeSteps(self.args(previous_bundle=None), targets=targets)
                steps.boot = Mock()
                if required:
                    with self.assertRaises(gate.Refused):
                        steps.upgrade()
                else:
                    steps.upgrade()
                steps.boot.assert_not_called()

    def test_client_smoke_waits_for_all_mapped_positive_features(self):
        mappings = [f'{category}=Core/{category}' for category in gate.CATEGORIES]
        args = self.args(smoke_use=mappings, client_timeout=10)
        steps = gate.NativeSteps(args)
        steps.rpt, steps.client_rpt = Path('server.RPT'), Path('client.RPT')
        rows = [dict(module='Core', feature=category, scope='client', status='ACTIVE', value=1)
                for category in gate.CATEGORIES]
        with patch.object(gate, 'audit'), patch.object(gate, 'emit'), \
                patch.object(gate.activity_check, 'scan', return_value={'features': rows}):
            steps.client()
        rows[0]['value'] = 0
        with patch.object(gate, 'audit'), patch.object(gate, 'emit'), \
                patch.object(gate.activity_check, 'scan', return_value={'features': rows}), \
                patch.object(gate.time, 'monotonic', side_effect=[0, 11]):
            with self.assertRaisesRegex(gate.Refused, 'timeout'):
                steps.client()

    def test_missing_smoke_mapping_fails_closed(self):
        steps = gate.NativeSteps(self.args(smoke_use=[], client_timeout=1))
        with patch.object(gate, 'emit'), self.assertRaisesRegex(gate.Refused, 'six distinct'):
            steps.client()

    def test_failed_graceful_stop_never_escalates(self):
        steps = gate.NativeSteps(self.args())
        steps.started = True
        with patch.object(gate.winproc, 'run', return_value=gate.winproc.Result(2, '', '', 1)) as call:
            with self.assertRaisesRegex(gate.Refused, 'graceful'):
                steps.stop()
        self.assertEqual(call.call_count, 1)
        self.assertTrue(steps.started)

    def test_unknown_server_refuses_before_install(self):
        steps = gate.NativeSteps(self.args())
        with patch.object(gate.winproc, 'process_state', return_value='unknown'), \
                patch.object(gate.winproc, 'run') as native:
            with self.assertRaises(gate.Refused):
                steps.install(Path('bundle'))
        native.assert_not_called()


class AcceptanceTargetsTests(unittest.TestCase):
    def test_loader_matches_owner_json(self):
        self.assertEqual(TARGETS, json.loads(policy.DEFAULT_TARGETS.read_text()))

    def test_invalid_or_missing_policy_refuses(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'targets.json'
            with self.assertRaisesRegex(policy.TargetsError, 'missing'):
                policy.load_targets(path)
            invalid = [([], 'object'), ({**TARGETS, 'unknown': True}, 'unknown')]
            for key in TARGETS:
                missing = dict(TARGETS)
                del missing[key]
                invalid.append((missing, 'missing keys: ' + key))
                changed = dict(TARGETS)
                changed[key] = None
                invalid.append((changed, 'invalid type: ' + key))
            invalid += [(dict(TARGETS, soak_minutes=True), 'invalid type'),
                        (dict(TARGETS, perf_r2_max_ms=float('nan')), 'finite'),
                        (dict(TARGETS, settle_minutes=-1), 'nonnegative'),
                        (dict(TARGETS, target_players_min=TARGETS['target_players_max'] + 1), 'player range')]
            for data, reason in invalid:
                with self.subTest(reason=reason):
                    path.write_text(json.dumps(data))
                    with self.assertRaisesRegex(policy.TargetsError, reason):
                        policy.load_targets(path)
            path.write_text('{')
            with self.assertRaisesRegex(policy.TargetsError, 'invalid JSON'):
                policy.load_targets(path)

    def test_nested_ceilings_and_ratchet_types_are_strict(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'targets.json'
            for value in (True, -1, 1.5, '1', [], {}, float('inf'), float('nan')):
                key = next(iter(TARGETS['rpt_category_ceilings']))
                data = dict(TARGETS, rpt_category_ceilings={**TARGETS['rpt_category_ceilings'], key: value})
                path.write_text(json.dumps(data))
                with self.subTest(value=value), self.assertRaises(policy.TargetsError):
                    policy.load_targets(path)
            for ceilings in ({}, {**TARGETS['rpt_category_ceilings'], 'unknown': 0}):
                path.write_text(json.dumps(dict(TARGETS, rpt_category_ceilings=ceilings)))
                with self.assertRaisesRegex(policy.TargetsError, 'every known RPT category'):
                    policy.load_targets(path)
            for value in (True, None, 0, -1, float('nan'), float('inf'),
                          TARGETS['readiness_max_after_hive_seconds'] + 1):
                path.write_text(json.dumps(dict(TARGETS, readiness_ratchet_max_after_hive_seconds=value)))
                with self.subTest(value=value), self.assertRaises(policy.TargetsError):
                    policy.load_targets(path)
            # Unmeasured is valid configuration, but never valid release evidence.
            path.write_text(json.dumps(dict(TARGETS, rpt_category_ceilings={
                key: None for key in TARGETS['rpt_category_ceilings']})))
            self.assertTrue(all(value is None for value in policy.load_targets(path)['rpt_category_ceilings'].values()))

    def test_preland_settings_rejects_bad_targets_before_other_validation(self):
        from tools.validate import settings_consistency
        from contextlib import redirect_stdout
        from io import StringIO
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / 'targets.json'
            output = StringIO()
            with patch.object(policy, 'DEFAULT_TARGETS', missing), \
                    patch.object(settings_consistency, 'check_consistency') as settings, \
                    patch('sys.argv', ['settings_consistency']), redirect_stdout(output):
                result = settings_consistency.main()
            self.assertTrue(result)
            self.assertEqual(json.loads(output.getvalue())['status'], 'fail')
            settings.assert_not_called()

    def test_recorded_boot_settle_matches_checkstart_parser(self):
        # Stop at argument parsing; no native execution or process queries.
        parse = gate.checkstart.argparse.ArgumentParser.parse_args
        class Parsed(Exception):
            pass
        def capture(parser, argv):
            args = parse(parser, argv)
            self.assertEqual(args.settle_minutes, TARGETS['settle_minutes'])
            raise Parsed
        with patch.object(gate.checkstart.argparse.ArgumentParser, 'parse_args', capture):
            with self.assertRaises(Parsed):
                gate.checkstart.main(['--bundle', 'synthetic'])
