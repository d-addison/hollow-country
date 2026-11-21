"""Receipt checks use synthetic files, never an installed game or translated Enforce."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.package import generated_digests as digests
from tools.package import regenerate_all


class DigestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.contract = digests.Contract('fixture', 'tools.package.fixture', ('output.txt',), ('input.txt',))
        files = {'output.txt': b'fresh', 'input.txt': b'policy',
                 'tools/package/fixture.py': b'from tools.package import helper\n',
                 'tools/package/helper.py': b'VALUE = 1\n',
                 'tools/package/generated_digests.py': b'# adapter\n',
                 'tools/package/regenerate_all.py': b'# aggregate\n'}
        for name, data in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.addCleanup(patch.stopall)
        patch.object(digests, 'ROOT', self.root).start()
        # Explicit root preserves test isolation despite Python's bound defaults.
        original = digests.local_snapshot
        patch.object(digests, 'local_snapshot', side_effect=lambda c: original(c, self.root)).start()
        self.real_installed_snapshot = digests.installed_snapshot
        patch.object(digests, 'installed_snapshot', return_value={'build': 'fixture-build'}).start()
        patch.object(digests, 'regenerate', return_value={'output.txt': b'fresh'}).start()

    def record(self):
        return dict(verified=True, **digests.fresh_record(self.contract, {}))

    def invoke(self, *args):
        with patch.object(digests, 'contracts', return_value=(self.contract,)), contextlib.redirect_stdout(io.StringIO()) as output:
            code = digests.main(list(args))
        return code, output.getvalue()

    def manifest(self, record):
        path = self.root / digests.MANIFEST
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'schema': 1, 'artefacts': {self.contract.name: record}}))
        return path

    def test_fresh_record_binds_inputs_transitive_sources_and_outputs(self):
        record = self.record()
        for name in ('input.txt', 'tools/package/fixture.py', 'tools/package/helper.py'):
            self.assertEqual(digests.sha((self.root / name).read_bytes()), record['inputs'][name])
        digests.verify_record(self.contract, record, {})
        for name in ('input.txt', 'output.txt', 'tools/package/helper.py'):
            path = self.root / name
            original = path.read_bytes()
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                digests.verify_record(self.contract, record, {})
            path.write_bytes(original)

    def test_changed_input_cannot_be_blessed_with_stale_output(self):
        old = self.record()
        path = self.manifest(old)
        (self.root / 'input.txt').write_bytes(b'new policy')
        with patch.object(digests, 'regenerate', return_value={'output.txt': b'new output'}):
            code, output = self.invoke('--update')
        self.assertEqual(1, code)
        self.assertIn('output.txt', output)
        self.assertEqual(old, json.loads(path.read_bytes())['artefacts'][self.contract.name])
        self.assertEqual(b'fresh', (self.root / 'output.txt').read_bytes())

    def test_update_accepts_only_matching_bytes_and_check_is_read_only(self):
        path = self.manifest({'verified': False})
        self.assertEqual(0, self.invoke('--update')[0])
        before = path.read_bytes()
        self.assertEqual(0, self.invoke('--check')[0])
        self.assertEqual(before, path.read_bytes())

    def test_missing_installed_is_skip_only_for_permissive_cli(self):
        path = self.manifest(self.record())
        before = path.read_bytes()
        with patch.object(digests, 'installed_snapshot', side_effect=digests.MissingInput('fixture unavailable')):
            code, output = self.invoke('--check')
            self.assertEqual(0, code)
            self.assertIn('SKIP fixture', output)
            self.assertEqual(1, self.invoke('--check', '--require-installed')[0])
            self.assertEqual(0, self.invoke('--update')[0])
        self.assertEqual(json.loads(before), json.loads(path.read_bytes()))

    def test_installed_identity_and_output_inventory_drift_refused(self):
        record = self.record()
        with patch.object(digests, 'installed_snapshot', return_value={'build': 'changed'}), self.assertRaises(ValueError):
            digests.verify_record(self.contract, record, {})
        record['outputs'] = {}
        with self.assertRaises(ValueError):
            digests.verify_record(self.contract, record, {})

    def test_data_file_additions_are_detected_and_receipt_is_not_its_own_input(self):
        record = self.record()
        self.manifest(record)
        digests.verify_record(self.contract, record, {})
        (self.root / 'config/new-policy.json').write_text('{}')
        with self.assertRaises(ValueError):
            digests.verify_record(self.contract, record, {})

    def test_input_race_during_generation_refused(self):
        def generate(*_):
            (self.root / 'input.txt').write_bytes(b'changed during generation')
            return {'output.txt': b'fresh'}
        with patch.object(digests, 'regenerate', side_effect=generate), self.assertRaises(ValueError):
            self.record()

    def test_external_deltas_record_hashes_and_do_not_claim_committed_bytes(self):
        contract = digests.Contract('fixture', self.contract.module, (), ('input.txt',), ('ce/types.xml',))
        with patch.object(digests, 'regenerate', return_value={'external/ce/types.xml': b'delta'}):
            record = digests.fresh_record(contract, {})
        self.assertEqual({}, record['outputs'])
        self.assertEqual({'ce/types.xml': digests.sha(b'delta')}, record['external_outputs'])

    def test_manifest_inventory_removal_and_unverified_receipts_fail(self):
        path = self.manifest({'verified': False})
        self.assertEqual(1, self.invoke('--check')[0])
        path.write_text(json.dumps({'schema': 1, 'artefacts': {}}))
        self.assertEqual(1, self.invoke('--check')[0])

    def test_stock_xml_identity_includes_carriers_and_core_extensions(self):
        from tools.package.economy import INPUTS
        source = self.root / 'stock'
        for rel in (*INPUTS, 'cfgspawnabletypes.xml', 'custom/registered-types.xml'):
            path = source / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'<fixture/>')
        contract = digests.Contract('economy', 'tools.package.economy', ())
        values = {'source': source}
        before = self.real_installed_snapshot(contract, values)
        for rel in ('cfgspawnabletypes.xml', 'custom/registered-types.xml'):
            path = source / rel
            path.write_bytes(b'<changed/>')
            self.assertNotEqual(before, self.real_installed_snapshot(contract, values))
            path.write_bytes(b'<fixture/>')
        (source / 'custom/new.xml').write_bytes(b'<fixture/>')
        self.assertNotEqual(before, self.real_installed_snapshot(contract, values))

    def test_release_refuses_and_names_artefact_without_packaging(self):
        result = subprocess.CompletedProcess([], 1, 'FAIL fixture stale input\n', '')
        with patch.object(digests.subprocess, 'run', return_value=result) as run, contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(ValueError):
                digests.verify_release(self.root, self.root / 'addons', self.root / 'workshop')
        self.assertIn('FAIL fixture', output.getvalue())
        command = run.call_args.args[0]
        self.assertIn('--require-installed', command)
        self.assertEqual(self.root, run.call_args.kwargs['cwd'])


if __name__ == '__main__':
    unittest.main()
