"""Synthetic missions, native declarations and receipts; never engine evidence."""
import copy
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.setup import infected_death_probe as receipt_io


class FuelSiphonProbeTests(unittest.TestCase):
    def setUp(self):
        self.probe = importlib.import_module('tools.setup.fuel_siphon_probe')
        self.temp = tempfile.TemporaryDirectory(prefix='hc-synthetic-siphon-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'stock'; self.source.mkdir()
        self.original = (b'// SYNTHETIC, no game assets\nvoid main() { Hive ce = CreateHive(); if (ce) ce.InitOffline(); }\nclass CustomMission : MissionServer {}\n'
                         b'Mission CreateCustomMission(string path) { return new CustomMission(); }\n')
        (self.source/'init.c').write_bytes(self.original)
        (self.source/'synthetic.xml').write_text('<synthetic/>')
        self.scripts = self.root/'synthetic-interfaces'
        for name, tokens in self.probe.INTERFACES.items():
            path = self.scripts/name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('\n'.join(tokens))
        self.dest = self.root/'fresh.chernarusplus'

    def prepare(self, **overrides):
        args = dict(x=6500, z=6500, rate_ml=1000, cap_ml=1000, fuel_liters=2,
                    car_class='OffroadHatchback', vessel_class='CanisterGasoline', run_id='a'*32)
        args.update(overrides)
        return self.probe.prepare_probe(self.source, self.dest, self.scripts, **args)

    def receipt(self):
        return dict(schema=1, kind=self.probe.KIND, run_id='a'*32, world='chernarusplus',
                    mode='stock-ce', ce_disabled_control=False,
                    gameplay_acceptance=False, ce_acceptance=False,
                    engine_version='synthetic-1.30', server_context=True, complete=True,
                    failed=False, reason='', ticks=10, frames=30, elapsed_seconds=3,
                    max_observed_clients=0, car_class='OffroadHatchback',
                    vessel_class='CanisterGasoline', actor_class='SurvivorM_Mirek',
                    car_spawned=True, actor_spawned=True, vessel_spawned=True,
                    actor_has_identity=False, component_index=17, component_result=1,
                    fuel_selection='refill', component_names=['refill'],
                    start_calls=1, finish_calls=1, end_calls=1, replay_calls=1,
                    start_valid=True, finish_valid=True, end_pair_valid=True,
                    sampled=True, transfer_attempted=True, lock_released=True,
                    diagnostic_status='observed_exact_transfer_nondurable',
                    replay_refused=True, replay_unchanged=True, conservation_observed=True,
                    donor_capacity_liters=42, donor_before_liters=2, donor_after_liters=1,
                    vessel_before_ml=0, vessel_after_ml=1000, vessel_max_ml=20000,
                    planned_ml=1000, debit_ml=1000, credit_ml=1000,
                    start_ms=1000, finish_ms=2100, gasoline_confirmed=True,
                    cleanup_requested=True, car_deleted=True, actor_deleted=True,
                    vessel_deleted=True, production_acceptance=False, durable_acceptance=False)

    def validate(self, value, **overrides):
        path = self.root/'result.json'; path.write_text(json.dumps(value))
        args = dict(outer_timed_out=False, outer_elapsed_seconds=5)
        args.update(overrides)
        return self.probe.validate_result(path, self.dest, **args)

    def test_factory_preserved_normal_server_and_hashes(self):
        marker = self.prepare()
        body = (self.dest/'init.c').read_text()
        self.assertEqual((self.source/'init.c').read_bytes(), self.original)
        self.assertIn('class HCFuelSiphonProbeMission : CustomMission', body)
        self.assertIn('return new HCFuelSiphonProbeMission()', body)
        self.assertIn('super.OnInit();', body)
        self.assertNotIn('DIAG_DEVELOPER', body)
        self.assertEqual(marker['max_owned'], dict(car=1, vessel=1, actor=1))
        self.assertEqual(marker['outer_timeout_seconds'], 90)
        self.assertTrue(marker['interfaces'])
        self.assertEqual(set(marker['files']), {'init.c', 'synthetic.xml'})

    def test_valid_synthetic_receipt_is_only_nondurable_observation(self):
        self.prepare(); result = self.validate(self.receipt())
        self.assertTrue(result['inprocess_observation_complete'])
        self.assertFalse(result['production_acceptance'])
        self.assertFalse(result['durable_acceptance'])

    def test_native_integer_boolean_receipt_passes_without_changing_numeric_fields(self):
        self.prepare()
        native={key:int(value) if type(value) is bool else value
                for key,value in self.receipt().items()}
        result=self.validate(native)
        self.assertTrue(result['inprocess_observation_complete'])
        self.assertFalse(result['production_acceptance'])
        self.assertFalse(result['durable_acceptance'])

    def test_every_native_boolean_flag_rejects_invalid_types_missing_and_wrong_polarity(self):
        self.prepare(); original=self.receipt()
        native={k:int(v) if type(v) is bool else v for k,v in original.items()}
        self.assertTrue(self.validate(native)['inprocess_observation_complete'])
        for field in (k for k,v in original.items() if type(v) is bool):
            for value in (1.0,0.0,'1','0',None,2,-1,1-native[field]):
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                    self.validate(dict(native,**{field:value}))
            missing=dict(native); del missing[field]
            with self.subTest(field=field,missing=True),self.assertRaises(ValueError):
                self.validate(missing)

    def test_bounds_reject_before_any_staging(self):
        for kw in (dict(x=float('nan')), dict(z=True), dict(rate_ml=0), dict(rate_ml=10001),
                   dict(cap_ml=1001), dict(fuel_liters=0), dict(fuel_liters=101),
                   dict(outer_timeout_seconds=181), dict(outer_timeout_seconds=14),
                   dict(outer_timeout_seconds=True),
                   dict(car_class='Car";Inject'), dict(actor_class='../Human'),
                   dict(run_id='old'), dict(rate_ml=0.00000001)):
            with self.subTest(kw=kw), self.assertRaises(ValueError): self.prepare(**kw)
            self.assertFalse(self.dest.exists())

    def test_fresh_only_and_no_overlap(self):
        self.prepare()
        with self.assertRaises(ValueError): self.prepare()
        with self.assertRaises(ValueError):
            self.probe.prepare_probe(self.source, self.source/'child', self.scripts,
                x=10,z=10,rate_ml=1000,cap_ml=1000,fuel_liters=2,
                car_class='Car',vessel_class='Vessel')

    def test_previous_instrumentation_and_runtime_storage_refused(self):
        (self.source/'storage_1').mkdir()
        with self.assertRaises(ValueError): self.prepare()
        (self.source/'storage_1').rmdir()
        (self.source/self.probe.MARKER).write_text('{}')
        with self.assertRaises(ValueError): self.prepare()

    def test_bad_native_interface_refused(self):
        name = next(iter(self.probe.INTERFACES))
        (self.scripts/name).write_text('// missing API')
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(self.dest.exists())

    def test_path_links_and_other_git_tree_refused(self):
        linked = self.root/'linked'; linked.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(ValueError): self.probe._safe(linked)
        (self.root/'.git').mkdir()
        with self.assertRaises(ValueError): self.prepare()

    def test_callbacks_replay_and_cleanup_must_be_observed(self):
        self.prepare(); good = self.receipt()
        changes = {k:False for k in ('car_spawned','actor_spawned','vessel_spawned','start_valid',
            'finish_valid','end_pair_valid','sampled','transfer_attempted','lock_released',
            'replay_refused','replay_unchanged','conservation_observed','gasoline_confirmed',
            'cleanup_requested','car_deleted','actor_deleted','vessel_deleted','complete','server_context')}
        changes.update(start_calls=0, finish_calls=0, end_calls=0, replay_calls=0, ticks=1,
            actor_has_identity=True, max_observed_clients=1, component_index=-1,
            component_result=0, component_names=['not_refill'], failed=True, reason='callback-not-run',
            diagnostic_status='proposal_only_nonatomic_observation', production_acceptance=True,
            durable_acceptance=True, run_id='b'*32, finish_ms=1000)
        for key, value in changes.items():
            row = copy.deepcopy(good); row[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(row)

    def test_conservation_and_operator_caps_reject(self):
        self.prepare(); good = self.receipt()
        for changes in (dict(donor_after_liters=2), dict(donor_after_liters=0),
            dict(vessel_after_ml=1001), dict(vessel_before_ml=1), dict(credit_ml=1001),
            dict(debit_ml=999), dict(planned_ml=0), dict(vessel_max_ml=999),
            dict(donor_before_liters=float('inf')), dict(credit_ml=True)):
            row = dict(good, **changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.validate(row)

    def test_timeout_evidence_required_even_with_complete_receipt(self):
        self.prepare()
        for kw in (dict(outer_timed_out=True), dict(outer_timed_out=0),
                   dict(outer_elapsed_seconds=91), dict(outer_elapsed_seconds=float('nan')),
                   dict(outer_elapsed_seconds=True)):
            with self.subTest(kw=kw), self.assertRaises(ValueError): self.validate(self.receipt(), **kw)

    def test_staged_drift_and_duplicate_json_keys_refused(self):
        self.prepare(); path=self.root/'duplicate.json'
        path.write_text('{"schema":1,"schema":1}')
        with self.assertRaises(ValueError): self.probe.validate_result(path,self.dest,
            outer_timed_out=False,outer_elapsed_seconds=5)
        (self.dest/'init.c').write_text('// changed after receipt')
        with self.assertRaises(ValueError): self.validate(self.receipt())

    def test_native_fixture_calls_real_action_and_observes_owned_cleanup(self):
        self.prepare(); body=(self.dest/'init.c').read_text()
        for token in ('GetActionComponentsForSelectionName(', 'GetViewGeometryLevel()',
            'GetActionComponentNameList(', 'GetRefillPointPosWS()', 'CreatePlayer(null,',
            'GetHumanInventory().CreateInHands(', 'SetQuantity(0, false)',
            'HCActionSiphonFuel.ConfigureDiagnostic(true,', '.OnStartServer(',
            '.OnFinishProgressServer(', '.OnEndServer(', 'HCActionSiphonFuel.TransferDiagnostic(',
            'HCActionSiphonFuel.ValidateLive(', 'ObjectDelete(m_CarObject)',
            'ObjectDelete(m_ActorObject)', 'ObjectDelete(m_VesselObject)',
            'm_Receipt.car_deleted = !m_CarObject;', 'owned-deletion-unconfirmed'):
            self.assertIn(token, body)
        self.assertEqual(body.count('CreateObjectEx('),1)
        self.assertEqual(body.count('CreatePlayer(null,'),1)
        self.assertEqual(body.count('GetHumanInventory().CreateInHands('),1)
        self.assertNotIn('SelectPlayer(',body)
        self.assertNotIn('RegisterActions',body)
        self.assertNotIn('SetSynchDirty',body)

    def test_recovery_callbacks_and_initial_receipt_precede_native_fixture(self):
        self.prepare(); body=(self.dest/'init.c').read_text()
        init=body[body.index('override void OnInit()'):body.index('bool HCSiphonSave()')]
        # A native abort during the synchronous first spawn must leave callbacks
        # already installed and a partial receipt, rather than lose all cleanup.
        first_tick=init.index('HCSiphonTick();')
        self.assertLess(init.index('CallLater(HCSiphonTick,'),first_tick)
        self.assertLess(init.index('.Insert(HCSiphonFrame)'),first_tick)
        self.assertIn('HCSiphonSave()',init[:first_tick])


    def test_receipt_hash_pins_the_single_validated_snapshot(self):
        self.prepare()
        path = self.root/'result.json'
        good = json.dumps(self.receipt()).encode()
        bad = json.dumps(dict(self.receipt(), run_id='b'*32,
                             complete=False, failed=True,
                             reason='changed-after-validation')).encode()
        path.write_bytes(good)
        original_read = self.probe._read
        receipt_reads = []

        def replace_after_read(candidate, limit):
            data = original_read(candidate, limit)
            if Path(candidate) == path:
                receipt_reads.append(data)
                path.write_bytes(bad)
            return data

        with patch.object(self.probe, '_read', side_effect=replace_after_read), \
                patch.object(receipt_io, '_read', side_effect=replace_after_read):
            result = self.probe.validate_result(
                path, self.dest, outer_timed_out=False,
                outer_elapsed_seconds=5)
        self.assertEqual(self.probe._sha(good), result['receipt_sha256'])
        self.assertEqual([good], receipt_reads)
        self.assertEqual(bad, path.read_bytes())

    def test_complete_receipt_with_duplicate_key_is_rejected(self):
        self.prepare()
        path = self.root/'duplicate-complete.json'
        raw = json.dumps(self.receipt())
        path.write_text(raw[:-1] + ', "complete": true}')
        with self.assertRaises(ValueError):
            self.probe.validate_result(
                path, self.dest, outer_timed_out=False,
                outer_elapsed_seconds=5)


    def test_explicit_180_budget_preserves_native_watchdogs_and_timeout_rejection(self):
        marker = self.prepare(outer_timeout_seconds=180)
        self.assertEqual(180, marker['outer_timeout_seconds'])
        body = (self.dest/'init.c').read_text()
        for token in ('now - m_Started > 60', 'now - m_CleanupStarted > 2',
                      'm_Receipt.ticks > 1000', 'm_Receipt.frames > 20000'):
            self.assertIn(token, body)
        result = self.validate(self.receipt(), outer_elapsed_seconds=179)
        self.assertTrue(result['inprocess_observation_complete'])
        with self.assertRaises(ValueError):
            self.validate(self.receipt(), outer_elapsed_seconds=181)
        with self.assertRaises(ValueError):
            self.validate(self.receipt(), outer_timed_out=True,
                          outer_elapsed_seconds=179)


    def test_ce_control_omits_only_guarded_init_and_preserves_context(self):
        for braced in (False, True):
            call = 'if (ce) { ce.InitOffline(); }' if braced else 'if (ce) ce.InitOffline();'
            text = 'void main() { Hive ce = CreateHive(); ' + call + ' int year = 2026; }'
            expected = text.replace('ce.InitOffline();', '' if braced else '{}')
            self.assertEqual(text.encode(), self.probe._ce_control(text.encode(), 'stock-ce'))
            self.assertEqual(expected.encode(),
                self.probe._ce_control(text.encode(), 'ce-disabled-control'))

    def test_ce_control_rejects_ambiguous_code_not_comments_or_strings(self):
        base = b'void main() { Hive ce = CreateHive(); if (ce) ce.InitOffline(); }'
        decorated = base + b' // ce.InitOffline();\nstring label = "ce.InitOffline();";'
        self.assertEqual(decorated.replace(b'if (ce) ce.InitOffline();', b'if (ce) {}'),
            self.probe._ce_control(decorated, 'ce-disabled-control'))
        for data in (base.replace(b'if (ce)', b'if (false)'),
                     base + b'void extra() { ce.InitOffline(); }',
                     base + b'void main() {}',
                     b'#ifdef X\n' + base + b'\n#endif'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.probe._ce_control(data, 'ce-disabled-control')

    def test_control_manifest_hook_and_receipt_pin_mode_without_ce_acceptance(self):
        marker = self.prepare(mode='ce-disabled-control')
        body = (self.dest / 'init.c').read_text()
        self.assertIn('Hive ce = CreateHive(); if (ce) {}', body)
        self.assertEqual(self.original, (self.source / 'init.c').read_bytes())
        self.assertEqual('ce-disabled-control', marker['mode'])
        self.assertTrue(marker['ce_disabled_control'])
        self.assertFalse(marker['gameplay_acceptance'])
        self.assertFalse(marker['ce_acceptance'])
        self.assertIn('string mode = "ce-disabled-control";', body)
        self.assertIn('bool ce_disabled_control = true;', body)
        receipt = dict(self.receipt(), mode='ce-disabled-control', ce_disabled_control=True)
        result = self.validate(receipt)
        self.assertEqual('ce-disabled-control', result['mode'])
        self.assertTrue(result['ce_disabled_control'])
        self.assertFalse(result['gameplay_acceptance'])
        self.assertFalse(result['ce_acceptance'])
        with self.assertRaises(ValueError):
            self.validate(self.receipt())

    def test_stock_default_and_unattributed_or_mismatched_receipts(self):
        marker = self.prepare()
        self.assertEqual('stock-ce', marker['mode'])
        self.assertFalse(marker['ce_disabled_control'])
        self.assertIn('if (ce) ce.InitOffline();', (self.dest / 'init.c').read_text())
        for changes in (dict(mode='ce-disabled-control'), dict(ce_disabled_control=True),
                        dict(mode=True), dict(ce_acceptance=True), dict(gameplay_acceptance=True)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.validate(dict(self.receipt(), **changes))
        for key in ('mode', 'ce_disabled_control'):
            receipt = self.receipt()
            del receipt[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                self.validate(receipt)
        path = self.dest / self.probe.MARKER
        del marker['mode']
        path.write_text(json.dumps(marker))
        with self.assertRaises(ValueError):
            self.validate(self.receipt())

    def test_invalid_mode_refused_before_staging(self):
        for value in (True, None, 0, 'fallback', 'stock-ce; injected'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.prepare(mode=value)
            self.assertFalse(self.dest.exists())

    def test_control_preserves_bom_crlf_and_stock_date_context(self):
        original = (b'\xef\xbb\xbfvoid main()\r\n{\r\n Hive ce = CreateHive();\r\n'
            b' if (ce)\r\n  ce.InitOffline();\r\n int year = 2026;\r\n}\r\n')
        self.assertEqual(original, self.probe._ce_control(original, 'stock-ce'))
        self.assertEqual(original.replace(b'ce.InitOffline();', b'{}'),
            self.probe._ce_control(original, 'ce-disabled-control'))

    def test_manifest_attribution_requires_exact_boolean_control_and_false_claims(self):
        for mode in ('stock-ce', 'ce-disabled-control'):
            marker = dict(mode=mode, ce_disabled_control=mode == 'ce-disabled-control',
                          gameplay_acceptance=False, ce_acceptance=False)
            self.assertEqual(mode, self.probe._attribution(marker))
            for key in marker:
                row = dict(marker)
                del row[key]
                with self.subTest(mode=mode, missing=key), self.assertRaises(ValueError):
                    self.probe._attribution(row)
            for key in ('ce_disabled_control', 'gameplay_acceptance', 'ce_acceptance'):
                for bad in (0, 1, None, 'false'):
                    with self.subTest(mode=mode, key=key, bad=bad), self.assertRaises(ValueError):
                        self.probe._attribution(dict(marker, **{key: bad}))


if __name__ == '__main__': unittest.main()
