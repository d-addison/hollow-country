"""Synthetic stock-shaped missions/interfaces/receipts; never run DayZ."""
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


STOCK = b'''// SYNTHETIC, not purchased mission contents.
void main()
{
    Hive ce = CreateHive();
    if ( ce )
        ce.InitOffline();
    int preserved = 7;
}
class CustomMission: MissionServer { void Preserved() {} }
Mission CreateCustomMission(string path) { return new CustomMission(); }
'''


def receipt(probe, run_id='a'*32, mode='stock-ce'):
    events = list(probe.LIFECYCLE)
    if mode == 'ce-disabled-control':
        events[events.index('CE_INIT_ENTER')] = 'CE_INIT_OMITTED'
        events.remove('CE_INIT_EXIT')
    events += ['QUEUE_ENTER', 'QUEUE_EXIT', 'UPDATE_ENTER', 'UPDATE_EXIT',
               'QUEUE_ENTER', 'QUEUE_EXIT', 'UPDATE_ENTER', 'UPDATE_EXIT']
    return dict(schema=1, kind=probe.KIND, run_id=run_id, mode=mode,
        server_context=1, world='chernarusplus', engine_version='1.30.synthetic',
        complete=1, failed=0, reason='', events=events, frame_entries=2,
        frame_exits=2, queue_entries=2, queue_exits=2, queue_update_ordinals=[0, 1],
        elapsed_seconds=1.0, callbacks_detached=1, ce_present=1,
        gameplay_acceptance=0, entities_created=0)


class NativeStartupProbeTests(unittest.TestCase):
    def setUp(self):
        self.probe = importlib.import_module('tools.setup.native_startup_probe')
        self.tmp = tempfile.TemporaryDirectory(prefix='hc-synthetic-startup-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stock = self.root/'stock'; self.stock.mkdir()
        (self.stock/'init.c').write_bytes(STOCK)
        (self.stock/'synthetic.xml').write_bytes(b'<synthetic/>')
        self.dest = self.root/'fresh.chernarusplus'
        self.scripts = self.root/'interfaces'
        for name, tokens in self.probe.INTERFACES.items():
            path = self.scripts/name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('\n'.join(tokens))

    def prepare(self, **kwargs):
        return self.probe.prepare_probe(self.stock, self.dest, self.scripts,
            **dict(dict(run_id='a'*32), **kwargs))

    def validate(self, row=None, **kwargs):
        path = self.root/'receipt.json'
        path.write_text(json.dumps(receipt(self.probe) if row is None else row))
        return self.probe.validate_result(path, self.dest,
            **dict(dict(outer_timed_out=False, outer_elapsed_seconds=20), **kwargs))

    def test_stock_factory_and_other_contents_are_preserved(self):
        manifest = self.prepare()
        generated = (self.dest/'init.c').read_text()
        self.assertIn('return new CustomMission();', generated)
        self.assertIn('void Preserved() {}', generated)
        self.assertIn('int preserved = 7;', generated)
        self.assertEqual(STOCK, (self.stock/'init.c').read_bytes())
        self.assertEqual(b'<synthetic/>', (self.dest/'synthetic.xml').read_bytes())
        self.assertEqual(1, generated.count('ce.InitOffline();'))
        self.assertEqual(hashlib.sha256(STOCK).hexdigest(), manifest['files']['init.c']['source_sha256'])
        self.assertTrue((self.dest/self.probe.MARKER).exists())

    def test_ce_disabled_omits_only_native_init_call_and_labels_result(self):
        self.prepare(mode='ce-disabled-control')
        generated = (self.dest/'init.c').read_text()
        self.assertNotIn('ce.InitOffline();', generated)
        self.assertIn('Hive ce = CreateHive();', generated)
        self.assertIn('int preserved = 7;', generated)
        self.assertIn('CE_INIT_OMITTED', generated)
        result = self.validate(receipt(self.probe, mode='ce-disabled-control'))
        self.assertEqual('ce-disabled-control', result['mode'])
        self.assertTrue(result['startup_control_complete'])
        self.assertFalse(result['gameplay_acceptance'])

    def test_live_only_callbacks_with_finite_budgets_and_lifecycle_brackets(self):
        self.prepare(); text = (self.dest/'init.c').read_text()
        self.assertEqual(1, text.count('super.OnInit();'))
        self.assertEqual(1, text.count('super.OnMissionStart();'))
        for token in ('MAIN_ENTER', 'CREATE_HIVE_ENTER', 'CREATE_HIVE_EXIT',
                      'CE_INIT_ENTER', 'CE_INIT_EXIT', 'MAIN_EXIT', 'INIT_ENTER',
                      'INIT_EXIT', 'START_ENTER', 'START_EXIT', 'QUEUE_ENTER',
                      'QUEUE_EXIT', 'UPDATE_ENTER', 'UPDATE_EXIT',
                      'CallLater(HCStartupQueue, 100, true)',
                      'Insert(HCStartupFrame)', 'Remove(HCStartupQueue)',
                      'Remove(HCStartupFrame)', 'frame_entries > 1024',
                      'queue_entries > 128', 'elapsed_seconds > 60'):
            self.assertIn(token, text)
        for forbidden in ('CreateObject', 'CreatePlayer', 'SetHealth(', 'SetWaypoints(',
                          'HCStartupQueue();', 'HCStartupFrame(', '.Tick(', '.Invoke('):
            if forbidden == 'HCStartupFrame(':
                self.assertEqual(1, text.count(forbidden))  # declaration only
            else:
                self.assertNotIn(forbidden, text)

    def test_bad_mode_nonce_and_ambiguous_main_refused_before_creation(self):
        for args in (dict(mode='arbitrary'), dict(run_id='../bad'), dict(run_id=True)):
            with self.subTest(args=args), self.assertRaises(ValueError): self.prepare(**args)
            self.assertFalse(self.dest.exists())
        for blob in (STOCK+STOCK, STOCK.replace(b'ce.InitOffline();', b'ce.InitOffline(); ce.InitOffline();'),
                     STOCK.replace(b'CreateHive()', b'OtherFactory()'),
                     STOCK.replace(b'void Preserved()', b'void OnInit()')):
            (self.stock/'init.c').write_bytes(blob)
            with self.assertRaises(ValueError): self.prepare()
            self.assertFalse(self.dest.exists())

    def test_comments_and_strings_cannot_supply_or_confuse_native_statements(self):
        fake = STOCK.replace(b'ce.InitOffline();', b'// ce.InitOffline();')
        (self.stock/'init.c').write_bytes(fake)
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(self.dest.exists())
        (self.stock/'init.c').write_bytes(STOCK+b'// } void main() { ce.InitOffline();\n')
        self.prepare()

    def test_missing_native_api_no_destination(self):
        (self.scripts/next(iter(self.probe.INTERFACES))).write_text('incompatible SYNTHETIC')
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(self.dest.exists())

    def test_fresh_external_paths_and_no_runtime_storage(self):
        (self.stock/'storage_1').mkdir()
        with self.assertRaises(ValueError): self.prepare()
        (self.stock/'storage_1').rmdir()
        with self.assertRaises(ValueError):
            self.probe.prepare_probe(self.stock, self.stock/'nested', self.scripts)
        self.prepare()
        with self.assertRaises(ValueError): self.prepare()

    def test_symlink_and_hardlink_inputs_refused(self):
        link = self.stock/'link.xml'; link.symlink_to(self.stock/'synthetic.xml')
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(self.dest.exists())

    def test_receipt_requires_both_actual_callback_paths_and_distinct_update_ordinals(self):
        self.prepare()
        for change in (dict(frame_entries=0), dict(frame_exits=1), dict(queue_entries=1),
                       dict(queue_exits=0), dict(queue_update_ordinals=[0, 0]),
                       dict(queue_update_ordinals=[0, 2]), dict(callbacks_detached=0),
                       dict(events=list(self.probe.LIFECYCLE))):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate(dict(receipt(self.probe), **change))
        self.assertTrue(self.validate()['startup_control_complete'])

    def test_partial_failed_stale_wrong_mode_or_nonzero_entities_never_pass(self):
        self.prepare()
        for change in (dict(complete=0), dict(failed=1), dict(reason='startup'),
                       dict(run_id='b'*32), dict(mode='ce-disabled-control'),
                       dict(entities_created=1), dict(server_context=0),
                       dict(gameplay_acceptance=1), dict(ce_present=0),
                       dict(schema=True), dict(frame_entries=1025), dict(elapsed_seconds=61)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate(dict(receipt(self.probe), **change))

    def test_timeout_elapsed_and_clock_bounds_are_mandatory(self):
        self.prepare()
        for kwargs in (dict(outer_timed_out=True), dict(outer_timed_out=0),
                       dict(outer_elapsed_seconds=181), dict(outer_elapsed_seconds=float('nan')),
                       dict(outer_elapsed_seconds=True)):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): self.validate(**kwargs)

    def test_staged_input_drift_and_path_traversal_markers_rejected(self):
        manifest = self.prepare()
        (self.dest/'synthetic.xml').write_bytes(b'drift')
        with self.assertRaises(ValueError): self.validate()
        (self.dest/'synthetic.xml').write_bytes(b'<synthetic/>')
        manifest['files']['../escape'] = manifest['files']['init.c']
        (self.dest/self.probe.MARKER).write_text(json.dumps(manifest))
        with self.assertRaises(ValueError): self.validate()

    def test_receipt_snapshot_is_read_once_and_same_bytes_are_hashed(self):
        self.prepare()
        path = self.root/'receipt.json'; data = json.dumps(receipt(self.probe)).encode()
        path.write_bytes(data); original = self.probe._read; calls = []
        def read(candidate, limit):
            if Path(candidate) == path:
                calls.append(candidate)
                return data if len(calls) == 1 else b'{}'
            return original(candidate, limit)
        with patch.object(self.probe, '_read', side_effect=read):
            result = self.probe.validate_result(path, self.dest,
                outer_timed_out=False, outer_elapsed_seconds=20)
        self.assertEqual(1, len(calls))
        self.assertEqual(hashlib.sha256(data).hexdigest(), result['receipt_sha256'])

    def test_duplicate_json_keys_and_oversized_receipts_rejected(self):
        self.prepare(); path = self.root/'receipt.json'
        for blob in (b'{"schema":1,"schema":1}', b' '* (self.probe.MAX_JSON_BYTES+1)):
            path.write_bytes(blob)
            with self.assertRaises(ValueError):
                self.probe.validate_result(path, self.dest, outer_timed_out=False, outer_elapsed_seconds=20)

    def test_hardlink_and_braced_stock_ce_pair(self):
        import os
        os.link(self.stock/'synthetic.xml',self.stock/'second.xml')
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(self.dest.exists())
        (self.stock/'second.xml').unlink()
        (self.stock/'init.c').write_bytes(STOCK.replace(b'if ( ce )\n        ce.InitOffline();',
            b'if ( ce ) { ce.InitOffline(); }'))
        self.prepare()
        self.assertIn('int preserved = 7;', (self.dest/'init.c').read_text())

    def test_reordered_lifecycle_and_unbalanced_checkpoint_rejected(self):
        self.prepare()
        for start,end in (('INIT_ENTER','INIT_EXIT'),('MAIN_ENTER','MAIN_EXIT'),
                          ('CREATE_HIVE_ENTER','CREATE_HIVE_EXIT'),('CE_INIT_ENTER','CE_INIT_EXIT')):
            row=receipt(self.probe); events=row['events']
            a,b=events.index(start),events.index(end); events[a],events[b]=events[b],events[a]
            with self.subTest(start=start),self.assertRaises(ValueError): self.validate(row)
        row=receipt(self.probe); row['events'].append('UPDATE_ENTER')
        with self.assertRaises(ValueError): self.validate(row)

    def test_native_bool_flags_are_exact_and_queue_waits_for_next_update(self):
        self.prepare()
        row=receipt(self.probe)
        for key in ('server_context','complete','callbacks_detached','ce_present'):
            row[key]=True
        row['failed']=False; row['gameplay_acceptance']=False
        self.assertTrue(self.validate(row)['startup_control_complete'])
        for value in (1.0,2,'true'):
            with self.assertRaises(ValueError): self.validate(dict(row,complete=value))
        self.assertIn('State.queue_update_ordinals[1] >= State.frame_exits',
            (self.dest/'init.c').read_text())

    def test_late_native_return_checkpoint_survives_watchdog_failure(self):
        self.prepare()
        text=(self.dest/'init.c').read_text()
        method=text.split('static void Mark(string checkpoint)',1)[1].split('static void HiveObserved',1)[0]
        # A late InitOffline RETURN must still be distinguished from a hang.
        self.assertIn('if (!State || State.complete) return;',method)
        self.assertLess(method.index('State.events.Insert(checkpoint)'),method.index('Check()'))


    def test_growth_after_inventory_rejects_before_destination_creation(self):
        inventory = self.probe.staging._inventory

        def grew(path):
            result = inventory(path)
            (self.stock / "synthetic.xml").write_bytes(b"x" * 12000)
            return result

        with patch.object(self.probe.staging, "MAX_TOTAL_BYTES", 10000):
            with patch.object(self.probe.staging, "_inventory", side_effect=grew):
                with self.assertRaises(ValueError):
                    self.prepare()
        self.assertFalse(self.dest.exists())

    def test_same_size_replacement_after_inventory_rejects_before_output(self):
        import os
        inventory = self.probe.staging._inventory

        def replaced(path):
            result = inventory(path)
            temporary = self.stock / "replacement"
            temporary.write_bytes(b"x" * len(b"<synthetic/>"))
            os.replace(temporary, self.stock / "synthetic.xml")
            return result

        with patch.object(self.probe.staging, "_inventory", side_effect=replaced):
            with self.assertRaises(ValueError):
                self.prepare()
        self.assertFalse(self.dest.exists())

    def test_generated_bytes_and_marker_reserve_fit_aggregate_entry_budgets(self):
        with patch.object(self.probe.staging, "MAX_TOTAL_BYTES", 1000):
            with self.assertRaises(ValueError):
                self.prepare()
        self.assertFalse(self.dest.exists())
        (self.stock / "empty").mkdir()
        with patch.object(self.probe.staging, "MAX_ENTRIES", 3):
            with self.assertRaises(ValueError):
                self.prepare()
        self.assertFalse(self.dest.exists())

    def test_extra_mission_files_and_empty_directories_are_not_unbound_evidence(self):
        self.prepare()
        for name, directory in (("extra.c", False), ("extra-directory", True)):
            target = self.dest / name
            if directory:
                target.mkdir()
            else:
                target.write_bytes(b"SYNTHETIC EXTRA")
            try:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    self.validate()
            finally:
                target.rmdir() if directory else target.unlink()
        self.assertTrue(self.validate()["startup_control_complete"])

    def test_mission_manifest_directory_traversal_and_depth_are_rejected(self):
        manifest = self.prepare()
        manifest["directories"] = ["../escape"]
        (self.dest / self.probe.MARKER).write_bytes(self.probe._encode(manifest))
        with self.assertRaises(ValueError):
            self.validate()


if __name__ == '__main__': unittest.main()
