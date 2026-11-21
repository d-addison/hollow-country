"""Catalog provenance and release refusal; no DayZ behaviour is established."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.package import admin_world_catalog as catalog
from tools.release import ship_inputs


class AdminWorldCatalogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name, data in catalog.local_inputs(catalog.ROOT).items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.output = self.root / catalog.CATALOG
        self.output.parent.mkdir(parents=True)
        # Generate the expected header through the actual generator, with a tiny
        # stock CE fixture; no remote input or literal digest/version snapshots.
        stock = b'<eventposdef><event name="Test"><pos x="1" z="2"/></event></eventposdef>'
        with mock.patch.object(catalog, 'ROOT', self.root), \
                mock.patch.object(catalog.urllib.request, 'urlopen') as fetch, \
                contextlib.redirect_stdout(io.StringIO()):
            fetch.return_value.__enter__.return_value.read.return_value = stock
            catalog.generate()
        offline = mock.patch.object(catalog.urllib.request, 'urlopen',
                                    side_effect=AssertionError('check must stay offline'))
        self.fetch = offline.start()
        self.addCleanup(offline.stop)

    def assert_stale(self):
        with self.assertRaisesRegex(ValueError, 'stale admin world catalog; regenerate'):
            catalog.check(self.root)

    def test_generated_catalog_passes_without_fetching_stock(self):
        before = self.output.read_bytes()
        catalog.check(self.root)
        self.assertEqual(self.output.read_bytes(), before)
        self.fetch.assert_not_called()

    def test_every_local_input_change_is_refused(self):
        for name, data in catalog.local_inputs(self.root).items():
            with self.subTest(name=name):
                path = self.root / name
                path.write_bytes(data + b'\n')
                self.assert_stale()
                path.write_bytes(data)
        catalog.check(self.root)

    def test_overlay_addition_and_removal_are_refused(self):
        added = self.root / 'config/map-overlays/layers/test-added.json'
        added.write_text('{}')
        self.assert_stale()
        added.unlink()
        existing = next((self.root / 'config/map-overlays/layers').glob('*.json'))
        data = existing.read_bytes()
        existing.unlink()
        self.assert_stale()
        existing.write_bytes(data)
        catalog.check(self.root)

    def test_optional_ce_removal_and_addition_are_refused(self):
        for name in catalog.CE_INPUTS:
            with self.subTest(name=name):
                path = self.root / name
                data = path.read_bytes()
                path.unlink()
                self.assert_stale()
                # Record a catalog generated without that optional input.
                # Reuse the recorded stock sha just as the offline checker does.
                stock = self.output.read_text().splitlines()[2].split(': ', 1)[1]
                without = catalog.inputs_digest(catalog.local_inputs(self.root), stock)
                original = self.output.read_text()
                header = original.splitlines()[3]
                self.output.write_text(original.replace(header, '// Inputs digest: ' + without))
                catalog.check(self.root)
                path.write_bytes(data)
                self.assert_stale()
                self.output.write_text(original)

    def test_missing_and_invalid_provenance_are_refused(self):
        original = self.output.read_text()
        for line in original.splitlines()[1:4]:
            with self.subTest(line=line.split(':', 1)[0]):
                self.output.write_text(original.replace(line, line.split(':', 1)[0] + ': invalid'))
                self.assert_stale()
        stock_line = original.splitlines()[2]
        self.output.write_text(original.replace(stock_line, '// Stock CE sha256: ' + '0' * 64))
        self.assert_stale()
        self.output.unlink()
        self.assert_stale()

    def test_missing_required_local_input_is_refused(self):
        (self.root / catalog.JSON_INPUTS[0]).unlink()
        self.assert_stale()

    def release_build(self, calls):
        def run(command, cwd):
            calls.append((command, cwd))
            if command[2:] == ['-m', 'tools.package.admin_world_catalog', '--check']:
                catalog.check(cwd)
        return ship_inputs.build_anims(self.root, self.root / 'addons', self.root / 'scratch', run)

    def test_shared_release_build_checks_catalog_before_builders(self):
        calls = []
        package = self.release_build(calls)
        self.assertEqual(calls[0][0][2:], ['-m', 'tools.package.admin_world_catalog', '--check'])
        self.assertEqual(calls[0][1], self.root)
        self.assertEqual(len(calls), 4)  # catalog check, two builders, PBO verification
        self.assertEqual(package.name, 'HollowCountryAnims.pbo')
        path = self.root / catalog.JSON_INPUTS[0]
        path.write_bytes(path.read_bytes() + b'\n')
        calls.clear()
        with self.assertRaisesRegex(ValueError, 'stale admin world catalog'):
            self.release_build(calls)
        self.assertEqual(len(calls), 1)

    def test_checked_in_catalog_passes_offline_cli(self):
        with contextlib.redirect_stdout(io.StringIO()):
            catalog.main(['--check'])
        self.fetch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
