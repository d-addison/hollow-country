"""Synthetic licence-chain, trust-boundary and immutable-bundle checks."""
import copy
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.assets import licence_gate as gate
from tools.assets import provenance as prov


class AssetLicenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.input = self.component()

    def component(self, licence='CC0-1.0', *, name='original'):
        payload = b'synthetic original geometry'
        licence_text = ('Synthetic licence fixture: ' + licence).encode()
        path = name + '.dat'
        licence_path = name + '.licence.txt'
        (self.root / path).write_bytes(payload)
        (self.root / licence_path).write_bytes(licence_text)
        return dict(source='own-work:' + name, path=path, sha256=prov.digest(payload),
                    licence_id=licence, licence_path=licence_path,
                    licence_sha256=prov.digest(licence_text), attribution='Fixture author')

    def document(self, record=None, **kwargs):
        return prov.build_provenance(asset='fixture', inputs=[record or self.input],
                                     toolchain=kwargs.pop('toolchain', []),
                                     origin=kwargs.pop('origin', 'own-work'),
                                     root=self.root, **kwargs)

    def seal(self, document):
        (self.root / 'provenance.json').write_text(json.dumps(document), encoding='utf-8')
        files = {p.relative_to(self.root).as_posix(): prov.digest(p.read_bytes())
                 for p in self.root.rglob('*') if p.is_file()
                 and p.name not in ('manifest.json', 'candidate.sha256')}
        manifest = json.dumps({'files': files}, sort_keys=True).encode()
        (self.root / 'manifest.json').write_bytes(manifest)
        (self.root / 'candidate.sha256').write_text(prov.digest(manifest) + '\n', encoding='ascii')
        return self.root / 'provenance.json'

    def assertBlocked(self, document):
        result = gate.audit(self.seal(document))
        self.assertEqual(result['verdict'], 'blocked', result)
        self.assertFalse(result['shippable'])

    def test_clean_cc0_and_cli_pass(self):
        path = self.seal(self.document())
        self.assertTrue(gate.audit(path)['shippable'])
        out = StringIO()
        with redirect_stdout(out):
            code = gate.main([str(path)])
        lines = out.getvalue().splitlines()
        self.assertEqual(code, 0)
        self.assertEqual(len(lines), 1)
        self.assertTrue(json.loads(lines[0])['shippable'])
        process = subprocess.run(['python3', '-B', '-m', 'tools.assets.licence_gate', str(path)],
                                 cwd=prov.ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(process.returncode, 0, process.stdout)
        self.assertEqual(json.loads(process.stdout), gate.audit(path))
        self.assertEqual(process.stderr, '')

    def test_seeded_restricted_and_unknown_licences_refuse(self):
        licences = ['CC-BY-4.0', 'MIT', 'BSD-3-Clause', 'Apache-2.0', 'CC-BY-NC-4.0', 'CC-BY-ND-4.0', 'GPL-3.0-only',
                    'LGPL-2.1-only', 'unstated', 'MIT OR GPL-3.0-only', '', None, {}]
        for licence in licences:
            with self.subTest(licence=licence):
                record = copy.deepcopy(self.input)
                record['licence_id'] = licence
                self.assertBlocked(self.document(record))

    def test_original_requires_pinned_provenance_and_authorship_notice(self):
        record = self.component('HC-Original')
        self.assertTrue(gate.audit(self.seal(self.document(record)))['shippable'])
        self.assertBlocked(self.document(dict(record, attribution='')))
        record.pop('licence_path')
        self.assertBlocked(self.document(record))

    def test_asset_lint_licence_request_requires_provenance(self):
        from tools.assets import finisher
        from tools.validate import asset_lint
        from tests.unit.test_asset_pipeline import cube
        asset = finisher.finish({0: cube()}, budgets={0: 12})
        def checked(licence, path=None):
            result = asset_lint.lint(asset, source_licence=licence, provenance_path=path)
            return not any(f['id'] == 'HC-A016' for f in result['findings'])
        self.assertFalse(checked('HC-Original'))
        path = self.seal(self.document(self.component('HC-Original')))
        self.assertTrue(checked('HC-Original', path))
        self.assertFalse(checked('CC0-1.0', path))
        path = self.seal(self.document(self.component('CC-BY-4.0')))
        self.assertFalse(checked('CC-BY-4.0', path))
        path = self.seal(self.document(self.component('CC0-1.0')))
        self.assertTrue(checked('CC0-1.0', path))

    def test_every_policy_source_licence_with_notice_passes(self):
        for licence in gate.load_policy()['source_licences']:
            with self.subTest(licence=licence):
                doc = self.document(self.component(licence))
                self.assertTrue(gate.audit(self.seal(doc))['shippable'])

    def test_missing_required_fields_and_unparseable_pins_refuse(self):
        for field in self.input:
            with self.subTest(field=field):
                record = copy.deepcopy(self.input)
                del record[field]
                self.assertBlocked(self.document(record))
        for field in ('sha256', 'licence_sha256'):
            for value in ('', 'unpinned', None, ['not-a-digest']):
                record = dict(self.input, **{field: value})
                self.assertBlocked(self.document(record))

    def test_cc_by_requires_attribution(self):
        record = self.component('CC-BY-4.0')
        record['attribution'] = ' '
        self.assertBlocked(self.document(record))

    def test_unparseable_licence_bytes_refuse_even_with_matching_hash(self):
        for payload in (b'', b'  \n', b'\xff', b'licence\x00text'):
            (self.root / self.input['licence_path']).write_bytes(payload)
            record = dict(self.input, licence_sha256=prov.digest(payload))
            self.assertBlocked(self.document(record))

    def test_explicit_component_blocks_override_permissive_claims(self):
        for row in gate.load_policy()['blocked_components']:
            for name in row['names']:
                with self.subTest(name=name):
                    record = dict(self.input, name=name, licence_id='MIT')
                    self.assertBlocked(self.document(record))
                    record = dict(self.input, source='https://example.invalid/' + name)
                    self.assertBlocked(self.document(record))

    def test_polyhaven_preview_and_unpinned_download_refuse(self):
        sources = ['https://cdn.polyhaven.com/asset_img/preview.png',
                   'https://cdn.polyhaven.com/%61sset_img/preview.png',
                   'https://polyhaven.com/a/fixture',
                   'https://dl.polyhaven.org/file/fixture.zip?preview=1']
        for source in sources:
            with self.subTest(source=source):
                self.assertBlocked(self.document(dict(self.input, source=source)))

    def test_polyhaven_requires_pinned_cc0_archive_on_approved_host(self):
        policy = gate.load_policy()['poly_haven']
        source = 'https://' + policy['archive_hosts'][0] + '/fixture' + policy['archive_suffixes'][0]
        record = dict(self.input, source=source, acquisition='archive')
        self.assertTrue(gate.audit(self.seal(self.document(record)))['shippable'])
        for change in ({'licence_id': 'MIT'}, {'sha256': ''},
                       {'source': source.replace('https:', 'http:')},
                       {'source': source.replace(policy['archive_hosts'][0], 'example.invalid', 1),
                        'name': 'Poly Haven'}):
            self.assertBlocked(self.document(dict(record, **change)))

    def test_external_gpl_tool_caps_whole_chain(self):
        for licence in gate.load_policy()['external_process_only']:
            tool = dict(self.component(licence, name='tool'), name='tool', version='1.0',
                        external_process=True, shipped=False)
            document = self.document(toolchain=[tool])
            result = gate.audit(self.seal(document))
            self.assertEqual(result['verdict'], 'internal_only')
            self.assertFalse(result['shippable'])
            out = StringIO()
            with redirect_stdout(out):
                self.assertEqual(gate.main([str(self.root / 'provenance.json')]), 1)
            for change in ({'external_process': False}, {'shipped': True},
                           {'version': ''}, {'shipped': 0}):
                self.assertBlocked(self.document(toolchain=[dict(tool, **change)]))

    def test_nc_nd_lgpl_tools_refuse_even_as_external_process(self):
        for licence in ('CC-BY-NC-4.0', 'CC-BY-ND-4.0', 'LGPL-3.0-only', 'unstated'):
            tool = dict(self.component(licence, name='tool'), name='tool', version='1',
                        external_process=True, shipped=False)
            self.assertBlocked(self.document(toolchain=[tool]))

    def test_tampered_payload_licence_manifest_and_seal_refuse(self):
        document = self.document()
        for filename in (self.input['path'], self.input['licence_path'],
                         'manifest.json', 'candidate.sha256', 'provenance.json'):
            with self.subTest(filename=filename):
                path = self.seal(document)
                target = self.root / filename
                before = target.read_bytes()
                target.write_bytes(before + b'changed')
                self.assertFalse(gate.audit(path)['shippable'])
                target.write_bytes(before)

    def test_resealed_input_digest_tamper_still_refuses(self):
        document = self.document()
        (self.root / self.input['path']).write_bytes(b'changed')
        self.assertBlocked(document)

    def test_extra_missing_and_symlink_files_refuse(self):
        path = self.seal(self.document())
        extra = self.root / 'unlisted.dat'
        extra.write_bytes(b'extra')
        self.assertFalse(gate.audit(path)['shippable'])
        extra.unlink()
        payload = self.root / self.input['path']
        before = payload.read_bytes()
        payload.unlink()
        self.assertFalse(gate.audit(path)['shippable'])
        payload.symlink_to(self.input['licence_path'])
        self.assertFalse(gate.audit(path)['shippable'])
        payload.unlink()
        payload.write_bytes(before)
        self.assertTrue(gate.audit(path)['shippable'])

    def test_manifest_traversal_and_duplicate_json_refuse(self):
        self.seal(self.document())
        for manifest in (json.dumps({'files': {'../outside': self.input['sha256']}}),
                         '{"files":{},"files":{}}'):
            raw = manifest.encode()
            (self.root / 'manifest.json').write_bytes(raw)
            (self.root / 'candidate.sha256').write_text(prov.digest(raw), encoding='ascii')
            self.assertFalse(gate.audit(self.root / 'provenance.json')['shippable'])

    def test_worker_cannot_supply_authority_at_any_depth(self):
        for field in prov.AUTHORITATIVE:
            for payload in ({field: True}, {'stats': [{field: True}]}):
                with self.subTest(field=field, payload=payload):
                    with self.assertRaises(prov.Refusal):
                        self.document(worker_output=payload)
                    with self.assertRaises(prov.Refusal):
                        prov.verify_provenance(payload, from_worker=True)
        with self.assertRaises(prov.Refusal):
            prov.verify_provenance(self.document(), from_worker=True)
        doc = self.document(worker_output={'tris': 12})
        self.assertNotIn('tris', doc)

    def test_worker_schema_accepts_only_non_authoritative_metadata(self):
        doc = self.document()
        for field in prov.AUTHORITATIVE:
            del doc[field]
        self.assertEqual(prov.verify_provenance(doc, from_worker=True), doc)

    def test_forged_authority_and_waivers_refuse(self):
        document = self.document()
        for change in ({'shippable': False}, {'licence_gate': {}},
                       {'waived': ['licence']}, {'origin': ''}, {'schema': 'provenance.v1'}):
            self.assertBlocked(dict(document, **change))
        self.assertBlocked(self.document(waived=['quality']))
        raw = self.document(origin='ops:raw_bpy')
        self.assertEqual(raw['licence_gate']['verdict'], 'internal_only')

    def test_committed_note_digest_and_disk_bytes_are_both_required(self):
        note = 'README.md'
        committed = subprocess.run(['git', 'show', 'HEAD:' + note], cwd=prov.ROOT,
                                   capture_output=True, check=True).stdout
        attestation = dict(value=True, note=note, note_sha256=prov.digest(committed))
        self.assertTrue(prov.verified_attestation(attestation))
        self.assertTrue(self.document(attestations=[attestation])['shippable'])
        for change in ({'note_sha256': '0' * 64}, {'note': '../README.md'},
                       {'note': 'missing.md'}):
            invalid = dict(attestation, **change)
            self.assertFalse(prov.verified_attestation(invalid))
            self.assertBlocked(self.document(attestations=[invalid]))
        (self.root / note).write_bytes(committed + b'changed')
        with patch.object(prov.subprocess, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, committed, b'')
            self.assertFalse(prov.verified_attestation(attestation, self.root))
        (self.root / 'uncommitted.md').write_bytes(b'new note')
        self.assertFalse(prov.verified_attestation(dict(value=True, note='uncommitted.md',
                                                       note_sha256=prov.digest(b'new note')), self.root))

    def test_false_attestations_do_not_count_as_clearance_or_restrict_clean_inputs(self):
        self.assertFalse(prov.verified_attestation({'value': False}))
        self.assertTrue(self.document(attestations=[{'value': False}])['shippable'])
        restricted = dict(self.input, licence_id='CC-BY-NC-4.0')
        self.assertBlocked(self.document(restricted, attestations=[{'value': False}]))

    def test_invalid_schema_json_and_policy_fail_closed(self):
        for payload in ([], None, {}, {'schema': prov.SCHEMA}):
            self.assertEqual(gate.evaluate(payload, root=self.root)['verdict'], 'blocked')
        for data in (b'{', b'{"x":NaN}', b'{"x":1,"x":2}', b'\xff'):
            with self.assertRaises(prov.Refusal):
                prov.load_json(data)
        with patch.object(gate, 'POLICY_PATH', self.root / 'missing-policy.json'):
            self.assertBlocked(self.document())
        broken_policy = self.root / 'broken-policy.json'
        broken_policy.write_text('{}', encoding='ascii')
        with patch.object(gate, 'POLICY_PATH', broken_policy):
            self.assertBlocked(self.document())

    def test_hardlinks_and_directory_symlinks_refuse(self):
        path = self.seal(self.document())
        link = self.root / 'linked.dat'
        link.hardlink_to(self.root / self.input['path'])
        self.assertFalse(gate.audit(path)['shippable'])
        link.unlink()
        directory_link = self.root / 'linked-directory'
        directory_link.symlink_to(self.root, target_is_directory=True)
        self.assertFalse(gate.audit(path)['shippable'])
        directory_link.unlink()
        self.assertTrue(gate.audit(path)['shippable'])

    def test_malformed_cli_input_is_one_blocked_json_line(self):
        for args in ([], ['missing.json'], ['one', 'two']):
            out = StringIO()
            with redirect_stdout(out):
                self.assertEqual(gate.main(args), 1)
            self.assertEqual(len(out.getvalue().splitlines()), 1)
            self.assertEqual(json.loads(out.getvalue())['verdict'], 'blocked')


if __name__ == '__main__':
    unittest.main()
