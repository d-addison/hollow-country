"""#203 inventory overlay removal: explicit synthetic addon sources and mission receipts.

Nothing here observes DayZ. A replacement PBO is a reviewable, unsigned artefact;
installation, signing and client redistribution remain operator steps.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.package import economy, inventory_sizes, loot_boost, overlay_remove, pbo, travel

TORTILLA = ('    class TortillaBag: Clothing { itemsCargoSize[] = {7, 12}; attachments[] = '
            '{"Chemlight", "WalkieTalkie", "Backpack_1", "NBCBag", "helmetFlashlight"}; };\n')
HEAD = ('class CfgPatches\n{\n    class HollowCountry\n    {\n        requiredAddons[] = '
        '{"DZ_Data", "DZ_Characters_Backpacks"};\n    };\n};\nclass CfgVehicles\n{\n'
        '    class ZombieBase;\n    class Foreign: ZombieBase { itemSize[] = {1, 1}; };\n    class Clothing;\n')
BLOCK = ('    ' + inventory_sizes.BEGIN + '\n'
         '    // Vanilla-derived playtest values; DayZ runtime acceptance pending.\n'
         '    class AlarmClock_ColorBase;\n'
         '    // backpacks; DZ_Characters_Backpacks; x.pbo:config.bin; vanilla itemsCargoSize 8x8 -> 8x12\n'
         '    class Bag_One: AlarmClock_ColorBase { itemsCargoSize[] = {8, 12}; };\n'
         + TORTILLA +
         '    // END_PLACEHOLDER\n')
TAIL = '};\nclass CfgWeapons\n{\n    class Scout_Base;\n};\n'


def config(block=True):
    text = HEAD
    if block:
        text += BLOCK.replace('    // END_PLACEHOLDER\n', '    ' + inventory_sizes.END + '\n')
    return text + TAIL


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.addon = self.root / 'addon'
        (self.addon / 'scripts/3_Game').mkdir(parents=True)
        (self.addon / 'config.cpp').write_text(config())
        (self.addon / 'inputs.xml').write_text('<Inputs/>')
        (self.addon / 'scripts/3_Game/A.c').write_text('class A {};\n')
        self.mission = self.root / 'mission'
        self.mission.mkdir()
        (self.mission / 'cfgeconomycore.xml').write_bytes(b'<economycore/>')
        self.out = self.root / 'out'

    def ops(self, **extra):
        return overlay_remove.remove(self.mission, ('inventory',), stopped=True,
                                     addon_source=self.addon, pbo_out=self.out, **extra)

    def snapshot(self, root):
        return {str(p.relative_to(root)): p.read_bytes() for p in Path(root).rglob('*') if p.is_file()}


class PureStrip(Base):
    def test_strip_removes_only_generated_block_and_keeps_authored_slots(self):
        original = config()
        new, report = overlay_remove.strip_inventory_block(original)
        self.assertNotIn(inventory_sizes.BEGIN, new)
        self.assertNotIn('Bag_One', new)
        self.assertIn('class Foreign: ZombieBase', new)
        self.assertTrue(new.startswith(HEAD))
        self.assertTrue(new.endswith(TAIL))
        self.assertIn('requiredAddons[] = {"DZ_Data", "DZ_Characters_Backpacks"}', new)
        self.assertIn('class TortillaBag: Clothing { attachments[] = {"Chemlight", "WalkieTalkie", '
                      '"Backpack_1", "NBCBag", "helmetFlashlight"}; };', new)
        self.assertNotIn('itemsCargoSize', new.split('class Foreign')[1].split('class CfgWeapons')[0]
                         .replace('itemSize', ''))
        self.assertEqual(report['removed_classes'], ['Bag_One', 'TortillaBag'])
        self.assertEqual(report['retained_authored'], ['TortillaBag'])
        # Parent already declared outside the block must not be declared twice.
        self.assertEqual(new.count('class Clothing;'), 1)

    def test_no_block_is_a_noop_and_removed_marker_is_idempotent(self):
        self.assertEqual(overlay_remove.strip_inventory_block(config(False))[1]['status'], 'no_generated_block')
        once, _ = overlay_remove.strip_inventory_block(config())
        again, report = overlay_remove.strip_inventory_block(once)
        self.assertEqual(again, once)
        self.assertEqual(report['status'], 'no_generated_block')

    def test_foreign_or_malformed_block_content_refuses(self):
        for bad in (config().replace('    class AlarmClock_ColorBase;\n',
                                     '    class AlarmClock_ColorBase;\n    class Operator { itemSize[] = {9, 9}; };\n'),
                    config().replace('    ' + inventory_sizes.END + '\n', ''),
                    config().replace('{8, 12}', '{8, 12}; damage = 5')):
            with self.assertRaises(ValueError):
                overlay_remove.strip_inventory_block(bad)

    def test_generator_refuses_to_regenerate_over_removed_config(self):
        once, _ = overlay_remove.strip_inventory_block(config())
        with self.assertRaisesRegex(ValueError, 'removed'):
            inventory_sizes.update_config(once, [])

    def test_constants_match_the_generator(self):
        self.assertEqual(overlay_remove.INVENTORY_BEGIN, inventory_sizes.BEGIN)
        self.assertEqual(overlay_remove.INVENTORY_END, inventory_sizes.END)
        self.assertEqual(overlay_remove.AUTHORED_SLOT_ROWS, inventory_sizes.AUTHORED_SLOT_ROWS)


class RebuildFromSource(Base):
    def test_writes_reviewable_unsigned_pbo_receipt_and_diff(self):
        before = self.snapshot(self.addon)
        result = self.ops()
        self.assertEqual(result['inventory']['status'], 'rebuilt')
        self.assertEqual(result['runtime'], 'PENDING')
        self.assertEqual(self.snapshot(self.addon), before)  # source never edited
        blob = (self.out / 'hollowcountry.no-inventory.pbo').read_bytes()
        prefix, entries = pbo.parse(blob)
        self.assertEqual(prefix, pbo.PREFIX)
        self.assertNotIn(inventory_sizes.BEGIN, entries['config.cpp'].decode())
        self.assertEqual(entries['inputs.xml'], b'<Inputs/>')
        self.assertEqual(entries['scripts/3_Game/A.c'], b'class A {};\n')
        receipt = json.loads((self.out / 'hollowcountry.no-inventory.receipt.json').read_text())
        self.assertEqual(receipt['pbo_sha256'], hashlib.sha256(blob).hexdigest())
        self.assertEqual(receipt['source_config_sha256'], hashlib.sha256(config().encode()).hexdigest())
        self.assertEqual(receipt['removed_classes'], ['Bag_One', 'TortillaBag'])
        self.assertEqual(receipt['runtime'], 'PENDING')
        self.assertEqual(receipt['signed'], False)
        diff = (self.out / 'config.cpp.diff').read_text()
        self.assertIn('-    class Bag_One: AlarmClock_ColorBase', diff)

    def test_rebuild_is_deterministic(self):
        self.ops()
        first = (self.out / 'hollowcountry.no-inventory.pbo').read_bytes()
        other = self.root / 'out2'
        overlay_remove.remove(self.mission, ('inventory',), stopped=True,
                              addon_source=self.addon, pbo_out=other)
        self.assertEqual(first, (other / 'hollowcountry.no-inventory.pbo').read_bytes())

    def test_dry_run_writes_nothing_but_reports(self):
        result = overlay_remove.remove(self.mission, ('inventory',), dry_run=True,
                                       addon_source=self.addon, pbo_out=self.out)
        self.assertEqual(result['inventory']['status'], 'rebuilt')
        self.assertTrue(result['dry_run'])
        self.assertFalse(self.out.exists())

    def test_installed_pbo_path_needs_no_source_checkout(self):
        installed = self.root / 'installed.pbo'
        installed.write_bytes(pbo.pack(pbo.collect_addon(self.addon)))
        result = overlay_remove.remove(self.mission, ('inventory',), stopped=True,
                                       addon_pbo=installed, pbo_out=self.out)
        self.assertEqual(result['inventory']['status'], 'rebuilt')
        entries = pbo.parse((self.out / 'hollowcountry.no-inventory.pbo').read_bytes())[1]
        self.assertNotIn(inventory_sizes.BEGIN, entries['config.cpp'].decode())
        self.assertEqual(entries['scripts/3_Game/A.c'], b'class A {};\n')

    def test_no_generated_block_writes_no_replacement(self):
        (self.addon / 'config.cpp').write_text(config(False))
        result = self.ops()
        self.assertEqual(result['inventory']['status'], 'no_generated_block')
        self.assertFalse(self.out.exists())

    def test_gap_without_a_source_and_both_sources_refuse(self):
        with self.assertRaisesRegex(ValueError, 'inventory receipt rollback unavailable'):
            overlay_remove.remove(self.mission, ('inventory',), stopped=True)
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            overlay_remove.remove(self.mission, ('inventory',), stopped=True, addon_source=self.addon,
                                  addon_pbo=self.root / 'x.pbo', pbo_out=self.out)
        with self.assertRaisesRegex(ValueError, 'pbo.out'):
            overlay_remove.remove(self.mission, ('inventory',), stopped=True, addon_source=self.addon)


class FailureModes(Base):
    def test_failed_build_writes_nothing_and_keeps_mission(self):
        (self.addon / 'stray.exe').write_bytes(b'MZ')
        before = self.snapshot(self.mission)
        with self.assertRaises(ValueError):
            self.ops()
        self.assertFalse(self.out.exists())
        self.assertEqual(self.snapshot(self.mission), before)

    def test_foreign_text_inside_block_refuses_without_output(self):
        text = config().replace('{8, 12};', '{8, 12}; foreign = 1;')
        (self.addon / 'config.cpp').write_text(text)
        with self.assertRaises(ValueError):
            self.ops()
        self.assertFalse(self.out.exists())

    def test_existing_output_is_never_overwritten(self):
        self.out.mkdir()
        (self.out / 'hollowcountry.no-inventory.pbo').write_bytes(b'operator file')
        with self.assertRaisesRegex(ValueError, 'exists'):
            self.ops()
        self.assertEqual((self.out / 'hollowcountry.no-inventory.pbo').read_bytes(), b'operator file')
        self.assertFalse((self.out / 'hollowcountry.no-inventory.receipt.json').exists())

    def test_live_removal_needs_stopped_server(self):
        with self.assertRaisesRegex(ValueError, 'stopped'):
            overlay_remove.remove(self.mission, ('inventory',), addon_source=self.addon, pbo_out=self.out)
        self.assertFalse(self.out.exists())


class Coordinated(Base):
    def install_receipts(self):
        folder = self.mission / travel.MANAGED
        (folder / 'ce').mkdir(parents=True)
        before, after = b'<economycore/>', b'<economycore><!--travel--></economycore>'
        (self.mission / 'cfgeconomycore.xml').write_bytes(after)
        receipt = {'schema': 1, 'before': economy.sha(before), 'after': economy.sha(after)}
        (folder / 'core.backup').write_bytes(before)
        for name in travel.CE_FILES:
            (folder / name).write_bytes(b'<types/>')
            receipt[name] = economy.sha(b'<types/>')
        (folder / 'receipt.json').write_bytes(economy.encode(receipt))

    def test_all_three_overlays_roll_back_together_with_a_replacement_pbo(self):
        self.install_receipts()
        result = overlay_remove.remove(self.mission, stopped=True, addon_source=self.addon,
                                       pbo_out=self.out)
        self.assertEqual(result['removed'], ['vehicles'])
        self.assertEqual(result['inventory']['status'], 'rebuilt')
        self.assertEqual((self.mission / 'cfgeconomycore.xml').read_bytes(), b'<economycore/>')
        self.assertTrue((self.out / 'hollowcountry.no-inventory.pbo').exists())

    def test_mission_drift_refuses_before_any_replacement_is_published(self):
        self.install_receipts()
        (self.mission / 'cfgeconomycore.xml').write_bytes(b'operator drift')
        before = self.snapshot(self.mission)
        with self.assertRaisesRegex(ValueError, 'core drift'):
            overlay_remove.remove(self.mission, stopped=True, addon_source=self.addon, pbo_out=self.out)
        self.assertEqual(self.snapshot(self.mission), before)
        self.assertFalse(self.out.exists())

    def test_dry_run_rehearses_everything_without_mutation(self):
        self.install_receipts()
        before = self.snapshot(self.mission)
        result = overlay_remove.remove(self.mission, dry_run=True, addon_source=self.addon, pbo_out=self.out)
        self.assertEqual(result['planned'], ['vehicles'])
        self.assertEqual(self.snapshot(self.mission), before)
        self.assertFalse(self.out.exists())

    def test_cli_reports_pending_and_signing_needed(self):
        result = subprocess.run([sys.executable, '-B', str(Path(overlay_remove.__file__)),
                                 '--mission', str(self.mission), '--overlays', 'inventory',
                                 '--addon-source', str(self.addon), '--pbo-out', str(self.out),
                                 '--server-stopped'], cwd=self.tmp.name, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('runtime=PENDING', result.stdout)
        self.assertIn('unsigned', result.stdout)
        self.assertTrue((self.out / 'hollowcountry.no-inventory.pbo').exists())


if __name__ == '__main__':
    unittest.main()


class RealSourceBlock(unittest.TestCase):
    """The shipped generated block must satisfy the removal grammar (reads the repo config.cpp)."""

    def test_shipped_config_block_strips_to_a_marker_and_one_authored_row(self):
        text = (Path(inventory_sizes.ROOT) / 'mods/HollowCountry/config.cpp').read_text()
        new, report = overlay_remove.strip_inventory_block(text)
        self.assertEqual(report['status'], 'rebuilt')
        self.assertEqual(report['retained_authored'], ['TortillaBag'])
        self.assertGreater(len(report['removed_classes']), 100)
        self.assertNotIn(inventory_sizes.BEGIN, new)
        self.assertEqual(new.count('class TortillaBag:'), 1)
        self.assertIn('class UniversalLight: Switchable_Base', new)
        self.assertEqual(new.count('class Clothing;'), 1)
