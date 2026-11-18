"""Explicit synthetic config fixtures; these checks do not establish DayZ behavior."""
import re
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.package import inventory_sizes as inv, pbo
from test_pbo_config import klass, rap, pbo as synthetic_pbo

ROOT = Path(__file__).resolve().parents[2]


def synthetic(name, size=(1, 2), *, parent='Inventory_Base', addon='DZ_Gear_Tools', **fields):
    return {'name': name, 'parent': parent, 'addon': addon, 'pbo': 'synthetic.pbo',
            'member': 'config.bin', 'fields': {'scope': 2, 'itemSize': list(size), **fields}}


class InventorySizes(unittest.TestCase):
    def setUp(self):
        self.rules = json.loads((ROOT / 'config/inventory-sizes.json').read_text())

    def changes(self, *rows):
        changes, _ = inv.select_changes({r['name']: r for r in rows}, self.rules)
        return {r['name']: r for r in changes}

    def test_backpacks_keep_width_and_round_rows_up_without_shrinking_shell(self):
        changes = self.changes(synthetic('TestPack', (4, 5), inventorySlot=['Back'],
                                       itemsCargoSize=[7, 5]))
        self.assertEqual(changes['TestPack']['new'], [7, 8])
        self.assertEqual(changes['TestPack']['property'], 'itemsCargoSize')

    def test_medical_explicit_rag_and_sewing_kit_and_small_bottles(self):
        changes = self.changes(synthetic('Rag', (1, 3), addon='DZ_Gear_Consumables'),
                               synthetic('SewingKit'),
                               synthetic('SyntheticMedicine', addon='DZ_Gear_Medical'))
        self.assertEqual(set(changes), {'Rag', 'SewingKit', 'SyntheticMedicine'})
        self.assertTrue(all(r['new'] == [1, 1] and r['category'] == 'medical'
                            for r in changes.values()))

    def test_long_side_and_square_tie_are_shrunk_once(self):
        changes = self.changes(synthetic('Long', (1, 3)), synthetic('Wide', (4, 1)),
                               synthetic('Square', (2, 2)))
        self.assertEqual({n: r['new'] for n, r in changes.items()},
                         {'Long': [1, 2], 'Wide': [3, 1], 'Square': [1, 2]})

    def test_two_cells_only_selected_categories_and_tools_strictly_below_500g(self):
        changes = self.changes(synthetic('Light', weight=499), synthetic('Heavy', weight=500),
                               synthetic('Unknown'), synthetic('Food', addon='DZ_Gear_Food'),
                               synthetic('Matchbox', addon='DZ_Gear_Consumables'))
        self.assertEqual(set(changes), {'Light', 'Food', 'Matchbox'})

    def test_firearm_attachment_container_cargo_clothing_and_large_items_never_shrink(self):
        rows = [synthetic('Gun', (2, 2), parent='Rifle_Base'),
                synthetic('Optic', (2, 2), addon='DZ_Weapons_Optics'),
                synthetic('Box', (2, 2), itemsCargoSize=[2, 2]),
                synthetic('Shirt', (2, 2), parent='Clothing', itemsCargoSize=[2, 2]),
                synthetic('Large', (1, 5)), synthetic('Hat', (2, 2),
                                                        inventorySlot=['Headgear'])]
        self.assertEqual(self.changes(*rows), {'Hat': self.changes(rows[-1])['Hat']})

    def test_melee_tools_are_not_misclassified_as_firearms(self):
        changes = self.changes(synthetic('HuntingKnife', (1, 3), addon='DZ_Weapons_Melee_Blade'))
        self.assertEqual(changes['HuntingKnife']['new'], [1, 2])

    def test_explicit_medical_include_cannot_shrink_area_five_or_more(self):
        self.assertEqual(self.changes(synthetic('Rag', (1, 5))), {})

    def test_inherited_cargo_and_inherited_weapon_ancestry_are_protected(self):
        rows = [synthetic('BoxBase', (2, 2), scope=0, itemsCargoSize=[2, 2]),
                synthetic('BoxChild', (2, 2), parent='BoxBase'),
                synthetic('GunBase', (2, 2), parent='Rifle_Base', scope=0),
                synthetic('GunChild', (2, 2), parent='GunBase')]
        self.assertEqual(self.changes(*rows), {})

    def test_excluded_descendant_does_not_shrink_through_parent_override(self):
        base = synthetic('SmallBase', (2, 2))
        child = synthetic('CargoChild', parent='SmallBase', itemsCargoSize=[2, 2])
        del child['fields']['itemSize']
        self.assertEqual(self.changes(base, child), {})

    def test_non_back_descendant_cannot_inherit_enlarged_cargo(self):
        base = synthetic('Backpack', inventorySlot=['Back'], itemsCargoSize=[3, 3])
        child = synthetic('BeltBag', parent='Backpack', inventorySlot=['Hips'])
        self.assertEqual(self.changes(base, child), {})

    def test_backpack_cargo_override_does_not_protect_its_inherited_shell(self):
        base = synthetic('SmallItem', (2, 2))
        backpack = synthetic('Backpack', parent='SmallItem', inventorySlot=['Back'],
                             itemsCargoSize=[3, 3])
        del backpack['fields']['itemSize']
        changes = self.changes(base, backpack)
        self.assertEqual(set(changes), {'Backpack'})
        self.assertEqual(changes['Backpack']['property'], 'itemsCargoSize')

    def test_weapon_attachment_slot_protects_even_an_unlisted_addon(self):
        self.assertEqual(self.changes(synthetic('Attachment', (1, 3),
                                               inventorySlot=['weaponHandguard'])), {})

    def test_handheld_optics_are_tools_and_not_firearm_attachments(self):
        changes = self.changes(synthetic('ItemOptics', (2, 2), scope=0),
                               synthetic('Rangefinder', parent='ItemOptics',
                                         addon='DZ_Gear_Optics', weight=270))
        self.assertEqual(changes['Rangefinder']['new'], [1, 1])

    def test_deterministic_order_parents_once_and_only_size_properties(self):
        rows = [synthetic('Zulu', (2, 2)), synthetic('Alpha', (1, 3))]
        a, _ = inv.select_changes({r['name']: r for r in rows}, self.rules)
        b, _ = inv.select_changes({r['name']: r for r in reversed(rows)}, self.rules)
        block = inv.render_block(a)
        self.assertEqual(block, inv.render_block(b))
        self.assertEqual(block.count('class Inventory_Base;'), 1)
        self.assertIn('class Alpha: Inventory_Base', block)
        self.assertNotIn('class CfgVehicles', block)
        self.assertNotIn('weight =', block)

    def test_overridden_parents_are_defined_not_also_forward_declared(self):
        # A class must not appear both as "class X;" and "class X: P {...}" in one CfgVehicles.
        rows = [synthetic('Bag_ColorBase', (2, 2)), synthetic('Bag_Green', (2, 2), parent='Bag_ColorBase')]
        changes, _ = inv.select_changes({r['name']: r for r in rows}, self.rules)
        block = inv.render_block(changes)
        self.assertNotIn('class Bag_ColorBase;', block)
        self.assertEqual(block.count('class Inventory_Base;'), 1)
        self.assertLess(block.index('class Bag_ColorBase: Inventory_Base'), block.index('class Bag_Green: Bag_ColorBase'))

    def test_committed_block_never_forward_declares_an_overridden_class(self):
        config = (ROOT / 'mods/HollowCountry/config.cpp').read_text()
        block = config[config.index(inv.BEGIN):config.index(inv.END)]
        declared = set(re.findall(r'^\s*class (\w+);', block, re.M))
        defined = set(re.findall(r'^\s*class (\w+):', block, re.M))
        self.assertEqual(set(), declared & defined)

    def test_missing_parent_and_cycles_are_rejected(self):
        bad = synthetic('NoParent', (2, 2), parent='')
        with self.assertRaisesRegex(ValueError, 'parent'):
            self.changes(bad)
        with self.assertRaisesRegex(ValueError, 'cycl'):
            self.changes(synthetic('A', parent='B'), synthetic('B', parent='A'))

    def test_merge_is_scoped_addons_cover_definitions_and_check_detects_stale(self):
        config = (ROOT / 'mods/HollowCountry/config.cpp').read_text()
        changes = list(self.changes(synthetic('Example', (2, 2))).values())
        merged = inv.update_config(config, changes)
        self.assertEqual(merged.count('class CfgVehicles'), 1)
        self.assertEqual(merged.count('class ZombieBase:'), 1)
        self.assertIn('"DZ_Gear_Tools"', merged.split('requiredAddons[]')[1].split(';')[0])
        self.assertEqual(inv.update_config(merged, changes), merged)
        inv.check_config(merged, changes)
        with self.assertRaisesRegex(ValueError, 'stale'):
            inv.check_config(merged.replace('itemSize[] = {1, 2}', 'itemSize[] = {2, 2}'), changes)
        with self.assertRaisesRegex(ValueError, 'stale'):
            inv.check_config(merged.replace('"DZ_Gear_Tools"', '"SyntheticMissing"'), changes)

    def test_override_evidence_matches_review_and_parent_is_mandatory(self):
        changes = list(self.changes(synthetic('Example', (2, 2))).values())
        inv.verify_review(changes, copy.deepcopy(changes))
        bad = copy.deepcopy(changes)
        bad[0]['vanilla'] = [3, 3]
        with self.assertRaisesRegex(ValueError, 'review'):
            inv.verify_review(changes, bad)

    def test_committed_overrides_have_parents_addons_and_package_keeps_text(self):
        changes = self.rules['reviewed_overrides']
        self.assertTrue(changes)
        self.assertTrue(all(r['parent'] and r['addon'] and len(r['vanilla']) == 2 for r in changes))
        config = (ROOT / 'mods/HollowCountry/config.cpp').read_text()
        inv.check_config(config, changes)
        blob = pbo.pack(pbo.collect_addon(ROOT / 'mods/HollowCountry'))
        _, files = pbo.parse(blob)
        self.assertEqual(files['config.cpp'], config.encode())

    def test_cli_check_returns_nonzero_for_stale_block_without_writing(self):
        # Synthetic reviewed data lets this CLI test run without installed game files.
        with tempfile.TemporaryDirectory(prefix='hc-inventory-synthetic-') as tmp:
            path = Path(tmp) / 'config.cpp'
            path.write_text('class CfgVehicles {};\n')
            result = subprocess.run([sys.executable, '-m', 'tools.package.inventory_sizes',
                                     '--check', '--config', str(path), '--review-only'],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn('stale', result.stderr)
            self.assertEqual(path.read_text(), 'class CfgVehicles {};\n')

    def test_reader_keeps_numeric_arrays_case_insensitive_roots_and_addon_ownership(self):
        # Explicit synthetic RAP/PBO, encoded by the existing reader test helpers.
        document = klass(CfgPatches=klass(SyntheticPatch=klass(units=['TestPack'])),
                         cfgVehicles=klass(TestPack=klass('Clothing', scope=2,
                            itemSize=[4, 5], itemsCargoSize=[7, 5], inventorySlot=['Back'])))
        with tempfile.TemporaryDirectory(prefix='hc-inventory-synthetic-') as tmp:
            path = Path(tmp) / 'characters_backpacks.pbo'
            original = synthetic_pbo({'config.bin': rap(document)})
            path.write_bytes(original)
            definitions, patches = inv.load_vanilla(tmp)
            changes, _ = inv.select_changes(definitions, self.rules)
            self.assertEqual(patches, {'SyntheticPatch'})
            self.assertEqual(changes[0]['addon'], 'SyntheticPatch')
            self.assertEqual(changes[0]['parent'], 'Clothing')
            self.assertEqual(changes[0]['vanilla'], [7, 5])
            self.assertEqual(changes[0]['new'], [7, 8])
            self.assertEqual(path.read_bytes(), original)

    def test_reader_orders_addon_dependencies_before_merging_reopenings(self):
        base = klass(CfgPatches=klass(ZBase=klass()), cfgVehicles=klass(
            Example=klass('Inventory_Base', scope=2, itemSize=[1, 3])))
        reopening = klass(CfgPatches=klass(AReopen=klass(requiredAddons=['ZBase'])),
                          CfgVehicles=klass(Example=klass('Inventory_Base')))
        with tempfile.TemporaryDirectory(prefix='hc-inventory-synthetic-') as tmp:
            (Path(tmp) / 'gear_tools.pbo').write_bytes(synthetic_pbo({
                'a/config.bin': rap(reopening), 'z/config.bin': rap(base)}))
            definitions, _ = inv.load_vanilla(tmp)
            changes, _ = inv.select_changes(definitions, self.rules)
            self.assertEqual(changes[0]['addon'], 'ZBase')
            self.assertEqual(changes[0]['vanilla'], [1, 3])

    def test_reader_refuses_ambiguous_defining_patch(self):
        document = klass(CfgPatches=klass(PatchA=klass(), PatchB=klass()),
                         CfgVehicles=klass(Example=klass('Inventory_Base', scope=2, itemSize=[1, 3])))
        with tempfile.TemporaryDirectory(prefix='hc-inventory-synthetic-') as tmp:
            (Path(tmp) / 'gear_tools.pbo').write_bytes(synthetic_pbo({'config.bin': rap(document)}))
            definitions, _ = inv.load_vanilla(tmp)
            with self.assertRaisesRegex(ValueError, 'ambiguous'):
                inv.select_changes(definitions, self.rules)
