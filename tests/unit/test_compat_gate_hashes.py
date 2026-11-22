"""Offline checks of the compat sha plumbing between generator, gate, release and friendcycle.

Never launches a native executable; subprocess output is faked. Not DayZ behaviour."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tools.package import compat_addon
from tools.release import compile_gate, release


def receipt_for(blob, optional=()):
    return {'status': 'generated', 'pbo': compat_addon.PBO_NAME, 'pbos': [compat_addon.PBO_NAME],
            'sha256': hashlib.sha256(blob).hexdigest(), 'optional': list(optional)}


class CompatGateHashTests(unittest.TestCase):
    def test_sha_lines_roundtrip_and_ignore_other_output(self):
        shas = {compat_addon.PBO_NAME: 'a' * 64, compat_addon.slot_pbo('a'): 'b' * 64}
        lines = ['compile_gate: other=1', *compile_gate.compat_sha_lines(shas), 'noise']
        self.assertEqual(shas, compile_gate.parse_compat_shas(lines))
        self.assertEqual({}, compile_gate.parse_compat_shas(['compile_gate: staged_pbos=3']))

    def test_native_gate_reports_every_compat_sha(self):
        shas = {compat_addon.PBO_NAME: 'a' * 64, compat_addon.slot_pbo('a'): 'b' * 64}
        result = MagicMock(returncode=0, stdout='\n'.join(compile_gate.compat_sha_lines(shas)), stderr='')
        with patch.object(compile_gate, 'prerequisites', return_value=(Path('s'), Path('p'), None)), \
                patch.object(release.subprocess, 'run', return_value=result), \
                contextlib.redirect_stdout(io.StringIO()):
            gate = release.native_compile_gate(Path('tree'), 'c' * 40)
        self.assertTrue(gate['passed'])
        self.assertEqual(shas, gate['compat_sha256'])
        self.assertEqual([], compat_addon.check_hashes(
            {'status': 'generated', 'pbo': compat_addon.PBO_NAME, 'sha256': 'a' * 64,
             'optional': [{'slot': 'a', 'status': 'generated', 'pbo': compat_addon.slot_pbo('a'),
                           'sha256': 'b' * 64}]}, gate['compat_sha256']))

    def test_gate_without_compat_shas_never_matches_a_receipt(self):
        receipt = receipt_for(b'base')
        # A gate that printed nothing (or a receipt without a sha) must not pass as None == None.
        self.assertTrue(compat_addon.check_hashes(receipt, {}))
        self.assertTrue(compat_addon.check_hashes(receipt, None))
        self.assertTrue(compat_addon.check_hashes(dict(receipt, sha256=None), {compat_addon.PBO_NAME: None}))

    def staged(self, receipt_sha=None, blob=b'base pbo'):
        def run(command, **kwargs):
            out = Path(command[command.index('--out') + 1])
            out.mkdir(parents=True)
            (out / compat_addon.PBO_NAME).write_bytes(blob)
            (out / 'compat-addon.json').write_text(json.dumps(receipt_for(receipt_sha or blob)))
            return MagicMock(returncode=0, stdout='', stderr='')
        return run

    def test_compat_inputs_prints_all_shas_and_passes_addons(self):
        with tempfile.TemporaryDirectory() as temp:
            seen = []
            run = self.staged()

            def spy(command, **kwargs):
                seen.append([str(part) for part in command])
                return run(command, **kwargs)
            with patch.object(compile_gate.subprocess, 'run', side_effect=spy), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                with compile_gate.compat_inputs(Path(temp), Path('ws'), Path(temp), Path('vanilla')) as staged:
                    self.assertEqual([compat_addon.PBO_NAME], [path.name for path in staged])
            self.assertIn('--addons', seen[0])
            self.assertEqual({compat_addon.PBO_NAME: hashlib.sha256(b'base pbo').hexdigest()},
                             compile_gate.parse_compat_shas(output.getvalue().splitlines()))

    def test_compat_inputs_refuses_a_pbo_that_differs_from_its_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            run = self.staged(receipt_sha=b'another')
            with patch.object(compile_gate.subprocess, 'run', side_effect=run), \
                    contextlib.redirect_stdout(io.StringIO()), \
                    self.assertRaisesRegex(ValueError, 'differ from the generator receipt'):
                with compile_gate.compat_inputs(Path(temp), Path('ws'), Path(temp)):
                    pass


class DependencyStackTests(unittest.TestCase):
    def tree(self, temp):
        tree = Path(temp) / 'tree'
        (tree / 'tools/setup').mkdir(parents=True)
        (tree / 'tools/setup/workshop_mods.json').write_text(json.dumps({'schema': 1, 'mods': []}))
        return tree

    def test_declared_provider_loads_the_stack_without_the_weapon_pack(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()) as output:
            tree = self.tree(temp)
            workshop = Path(temp) / 'ws'
            (workshop / '1234567').mkdir(parents=True)
            mods = [workshop / '1234567']
            with patch.object(compile_gate.compat_addon, 'declared_providers', return_value={'a': '1234567'}), \
                    patch.object(compile_gate, 'dependency_stack', return_value=mods) as stack:
                with compile_gate.compatibility_inputs(tree, workshop, Path(temp)) as inputs:
                    self.assertEqual({'extra_mods': mods}, inputs)
            stack.assert_called_once()
            self.assertIn('compat_providers=1', output.getvalue())
            self.assertNotIn('server_extra_pbos', inputs)

    def test_no_provider_and_no_pack_loads_nothing(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()) as output:
            tree = self.tree(temp)
            with patch.object(compile_gate.compat_addon, 'declared_providers', return_value={}), \
                    patch.object(compile_gate, 'dependency_stack') as stack:
                with compile_gate.compatibility_inputs(tree, Path(temp), Path(temp)) as inputs:
                    self.assertEqual({}, inputs)
            stack.assert_not_called()
            self.assertIn('weapon_pack_guards=absent', output.getvalue())

    def test_declared_provider_missing_from_the_install_refuses(self):
        with tempfile.TemporaryDirectory() as temp:
            tree = self.tree(temp)
            with patch.object(compile_gate.compat_addon, 'declared_providers', return_value={'a': '1234567'}):
                with self.assertRaisesRegex(ValueError, 'provider missing'):
                    with compile_gate.compatibility_inputs(tree, Path(temp) / 'ws', Path(temp)):
                        pass


if __name__ == '__main__':
    unittest.main()
