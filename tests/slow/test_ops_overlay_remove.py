"""Explicit synthetic receipts/files; no DayZ behavior is established."""
import io
import zipfile
import importlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.package import economy, travel, loot_boost


class Removal(unittest.TestCase):
    def setUp(self):
        self.ops = importlib.import_module('tools.package.overlay_remove')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mission = Path(self.tmp.name) / 'mission'
        self.mission.mkdir()
        (self.mission / 'cfgeconomycore.xml').write_bytes(b'<economycore/>')

    def install_receipts(self):
        # Explicit synthetic stack: loot owns a travel-generated types file.
        folder = self.mission / travel.MANAGED
        (folder / 'ce').mkdir(parents=True)
        before, after = b'<economycore/>', b'<economycore><!--travel--></economycore>'
        (self.mission / 'cfgeconomycore.xml').write_bytes(after)
        receipt = {'schema': 1, 'before': economy.sha(before), 'after': economy.sha(after)}
        (folder / 'core.backup').write_bytes(before)
        for name in travel.CE_FILES:
            data = b'<types/>'
            (folder / name).write_bytes(data)
            receipt[name] = economy.sha(data)
        (folder / 'receipt.json').write_bytes(economy.encode(receipt))
        managed = self.mission / loot_boost.MANAGED
        managed.mkdir()
        name = travel.MANAGED + '/ce/types.xml'
        boosted = b'<types><!--boosted--></types>'
        (self.mission / name).write_bytes(boosted)
        row = {'name': name, 'before': economy.sha(b'<types/>'),
               'after': economy.sha(boosted), 'backup': '00.backup'}
        (managed / '00.backup').write_bytes(b'<types/>')
        (managed / 'receipt.json').write_bytes(economy.encode({
            'schema': 1, 'kind': 'hollow-country-loot-boost',
            'runtime_acceptance': 'pending', 'files': [row]}))

    def snapshot(self):
        return {str(p.relative_to(self.mission)): p.read_bytes()
                for p in self.mission.rglob('*') if p.is_file()}

    def test_reverse_stack_restores_exact_bytes_without_storage_changes(self):
        self.install_receipts()
        (self.mission / 'storage_1').mkdir()
        (self.mission / 'storage_1' / 'players.db').write_bytes(b'synthetic save')
        result = self.ops.remove(self.mission, ('loot', 'vehicles'), stopped=True)
        self.assertEqual(result['removed'], ['loot', 'vehicles'])
        self.assertEqual(self.snapshot(), {'cfgeconomycore.xml': b'<economycore/>',
                                         'storage_1/players.db': b'synthetic save'})
        self.assertEqual(self.ops.remove(self.mission, ('loot', 'vehicles'), stopped=True)['removed'], [])

    def test_later_layer_drift_refuses_before_any_live_rollback(self):
        self.install_receipts()
        (self.mission / 'cfgeconomycore.xml').write_bytes(b'operator drift')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'core drift'):
            self.ops.remove(self.mission, ('loot', 'vehicles'), stopped=True)
        self.assertEqual(self.snapshot(), before)

    def test_dry_run_exercises_real_rollbacks_only_on_scratch(self):
        self.install_receipts()
        before = self.snapshot()
        self.ops.remove(self.mission, ('loot', 'vehicles'), dry_run=True)
        self.assertEqual(self.snapshot(), before)

    def test_stop_ack_and_inventory_gap_refuse_without_mutation(self):
        self.install_receipts()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'stopped'):
            self.ops.remove(self.mission, ('loot', 'vehicles'))
        with self.assertRaisesRegex(ValueError, 'inventory.*receipt'):
            self.ops.remove(self.mission, stopped=True)
        self.assertEqual(self.snapshot(), before)

    def test_symlink_in_receipt_tree_refuses_without_following(self):
        self.install_receipts()
        (self.mission / 'linked').symlink_to(self.tmp.name, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.ops.remove(self.mission, ('loot', 'vehicles'), stopped=True)

    def test_unknown_overlay_refuses(self):
        with self.assertRaisesRegex(ValueError, 'overlay'):
            self.ops.remove(self.mission, ('typo',), stopped=True)

    def test_direct_cli_from_other_directory(self):
        result = subprocess.run([sys.executable, '-B', str(Path(self.ops.__file__)),
                                 '--mission', str(self.mission), '--overlays', 'loot', 'vehicles',
                                 '--dry-run'], cwd=self.tmp.name, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('runtime=PENDING', result.stdout)


class PortableHandoff(unittest.TestCase):
    def test_removal_helper_is_packaged_and_passes_handoff_validation(self):
        from tools.package import pbo
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            addon, mission = root / 'addon', root / 'mission'
            addon.mkdir()
            mission.mkdir()
            (addon / 'config.cpp').write_text('class Synthetic {};')
            blob = pbo.handoff(addon, mission)
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                self.assertIn('tools/package/overlay_remove.py', archive.namelist())
            pbo.verify_handoff(blob)
