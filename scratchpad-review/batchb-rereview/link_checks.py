"""Synthetic filesystem attacks only; no production code or native runtime mutation."""
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from tests.unit.test_gameplay_delta import committed, synthetic_source
from tools.package import gameplay

HERE = Path(__file__).resolve().parent


class LinkChecks(unittest.TestCase):
    def fixture(self, root):
        source, stage, target = (root / n for n in ('source', 'stage', 'target'))
        synthetic_source(source)
        profile, preset = committed()
        gameplay.write_delta(stage, gameplay.generate(source, profile, preset))
        shutil.copytree(source, target)
        (target / 'init.c').write_bytes(b'// synthetic untouched neighbor\n')
        return stage, target

    def link(self, path, outside, kind):
        content = path.read_bytes() if path.exists() else b'synthetic unrelated outside data\n'
        outside.write_bytes(content)
        if path.exists() or path.is_symlink():
            path.unlink()
        if kind == 'hard':
            os.link(outside, path)
        else:
            path.symlink_to(outside)
        return content

    def test_existing_link_matrix_refuses_without_changes(self):
        cases = 0
        for operation in ('install', 'rollback'):
            names = ['cfggameplay.json']
            if operation == 'rollback':
                names += [gameplay.MANAGED + '/' + n for n in (
                    'cfggameplay.next', 'cfggameplay.backup', 'receipt.json', 'gear/hardscrabble.json')]
            for name in names:
                for kind in ('hard', 'symlink'):
                    for dry in (True, False):
                        with self.subTest(operation=operation, name=name, kind=kind, dry=dry):
                            with tempfile.TemporaryDirectory(dir=HERE / 'tmp') as tmp:
                                root = Path(tmp)
                                stage, target = self.fixture(root)
                                if operation == 'rollback':
                                    gameplay.install(stage, target)
                                outside, path = root / 'outside', target / name
                                content = self.link(path, outside, kind)
                                config = (target / 'cfggameplay.json').read_bytes()
                                with self.assertRaises(ValueError):
                                    if operation == 'install':
                                        gameplay.install(stage, target, dry_run=dry)
                                    else:
                                        gameplay.rollback(target, dry_run=dry)
                                self.assertEqual(outside.read_bytes(), content)
                                self.assertEqual((target / 'cfggameplay.json').read_bytes(), config)
                                self.assertTrue(path.is_symlink() if kind == 'symlink' else path.stat().st_nlink == 2)
                                cases += 1
        print(f'Existing-link matrix: {cases} cases refused; outside/config bytes unchanged.')

    def test_file_swaps_between_preflight_and_write_do_not_write_through(self):
        cases = 0
        original_writer = gameplay.write_fresh
        for operation in ('install', 'rollback'):
            names = [gameplay.MANAGED + '/' + n for n in (
                'cfggameplay.backup', 'receipt.json', 'gear/hardscrabble.json', 'cfggameplay.next')]
            if operation == 'rollback':
                names += ['cfggameplay.json']
            for name in names:
                for kind in ('hard', 'symlink'):
                    with self.subTest(operation=operation, name=name, kind=kind):
                        with tempfile.TemporaryDirectory(dir=HERE / 'tmp') as tmp:
                            root = Path(tmp)
                            stage, target = self.fixture(root)
                            original = (target / 'cfggameplay.json').read_bytes()
                            if operation == 'rollback':
                                gameplay.install(stage, target)
                            outside, injected = root / 'outside', []

                            def swap_then_write(path, data):
                                # Real preflight already finished. Inject a leaf link just
                                # before the real writer; do not replace writer behavior.
                                if not injected and (operation == 'rollback' or Path(path) == target / name):
                                    injected.append(self.link(target / name, outside, kind))
                                return original_writer(path, data)

                            with mock.patch.object(gameplay, 'write_fresh', new=swap_then_write):
                                if operation == 'install':
                                    gameplay.install(stage, target)
                                else:
                                    gameplay.rollback(target)
                            self.assertEqual(len(injected), 1)
                            self.assertEqual(outside.read_bytes(), injected[0])
                            if operation == 'install':
                                gameplay.rollback(target)
                            self.assertEqual((target / 'cfggameplay.json').read_bytes(), original)
                            self.assertFalse((target / 'cfggameplay.json').is_symlink())
                            self.assertEqual((target / 'init.c').read_bytes(), b'// synthetic untouched neighbor\n')
                            self.assertFalse((target / gameplay.MANAGED).exists())
                            cases += 1
        print(f'Preflight/write file swaps: {cases} cases; outside bytes unchanged and rollback byte-exact.')


if __name__ == '__main__':
    unittest.main(verbosity=2)
