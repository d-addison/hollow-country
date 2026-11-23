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
from tests.unit.test_pbo_config import klass, rap, pbo as synthetic_pbo

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

    def test_regeneration_preserves_authored_taped_pack_slots(self):
        # Synthetic regeneration over reviewed source data; no DayZ claim.
        from tools.audit.pbo_config import parse_text_config
        config = (ROOT / 'mods/HollowCountry/config.cpp').read_text()
        regenerated = inv.update_config(config, self.rules['reviewed_overrides'])
        classes = parse_text_config(regenerated, ('CfgVehicles',))['CfgVehicles']
        self.assertEqual(['Chemlight', 'WalkieTalkie', 'Backpack_1', 'NBCBag', 'helmetFlashlight'],
                         classes['TortillaBag'].get('attachments'))
        self.assertEqual(['weaponFlashlight', 'helmetFlashlight', 'pistolFlashlight', 'Chemlight'],
                         classes['UniversalLight']['inventorySlot'])
        self.assertEqual(['pistolFlashlight', 'weaponFlashlight'], classes['TLRLight']['inventorySlot'])
        self.assertEqual(config, regenerated)

    def test_committed_overrides_have_parents_addons_and_package_keeps_text(self):
        changes = self.rules['reviewed_overrides']
        self.assertTrue(changes)
        self.assertTrue(all(r['parent'] and r['addon'] and len(r['vanilla']) == 2 for r in changes))
        config = (ROOT / 'mods/HollowCountry/config.cpp').read_text()
        inv.check_config(config, changes)
        blob = pbo.pack(pbo.collect_addon(ROOT / 'mods/HollowCountry'))
        _, files = pbo.parse(blob)
        self.assertEqual(files['config.cpp'], config.encode())

    # Source-consistency audit of the committed configs (W4-03). These read only the committed
    # text and reviewed rows; they cannot show what the DayZ engine loads.
    @staticmethod
    def members(config, root):
        """Depth-1 class statements of one root as (name, parent, defined), in file order."""
        text = re.sub(r'"(?:[^"]|"")*"|//[^\n]*|/\*.*?\*/', ' ', config, flags=re.S)
        match = re.search(r'\bclass\s+' + root + r'\s*\{', text)
        if not match:
            return []
        depth, found = 1, []
        for token in re.finditer(r'[{}]|\bclass\s+(\w+)\s*(?::\s*(\w+))?\s*(;|(?=\{))', text[match.end():]):
            if token.group() == '{':
                depth += 1
            elif token.group() == '}':
                depth -= 1
                if depth == 0:
                    break
            elif token.group(1) and depth == 1:
                found.append((token.group(1), token.group(2), token.group(3) != ';'))
        return found

    def committed_configs(self):
        return {'HollowCountry': (ROOT / 'mods/HollowCountry/config.cpp').read_text(),
                'HollowCountryExpansionAI': (ROOT / 'mods/HollowCountryExpansionAI/config.cpp').read_text()}

    def test_committed_roots_name_each_member_once_and_every_reopening_inherits(self):
        for addon, config in self.committed_configs().items():
            for root in ('CfgVehicles', 'CfgMagazines', 'CfgWeapons', 'CfgAmmo'):
                found = self.members(config, root)
                names = [n.lower() for n, _, _ in found]
                duplicated = sorted({n for n in names if names.count(n) > 1})
                self.assertEqual([], duplicated, addon + ' ' + root + ' names a member twice')
                if root != 'CfgVehicles':
                    continue
                # Parent first: a class is declared or defined above every class that inherits it, and
                # no definition lacks a parent (a bare reopening would drop the inherited config).
                seen = set()
                for name, parent, defined in found:
                    if defined:
                        self.assertTrue(parent, addon + ' ' + name + ' reopens without a parent')
                    if parent:
                        self.assertIn(parent.lower(), seen, addon + ' ' + name + ' precedes its parent')
                    seen.add(name.lower())

    def test_committed_forward_declarations_are_all_used_as_parents(self):
        for addon, config in self.committed_configs().items():
            found = self.members(config, 'CfgVehicles')
            parents = {p.lower() for _, p, _ in found if p}
            stale = sorted(n for n, _, defined in found if not defined and n.lower() not in parents)
            self.assertEqual([], stale, addon + ' forward-declares classes nothing inherits')

    def test_committed_stack_reopenings_keep_the_base_parent_and_rows_never_zero_a_class(self):
        configs = self.committed_configs()
        base = {n.lower(): p for n, p, d in self.members(configs['HollowCountry'], 'CfgVehicles') if d}
        for name, parent, defined in self.members(configs['HollowCountryExpansionAI'], 'CfgVehicles'):
            if defined and name.lower() in base:
                self.assertEqual(base[name.lower()].lower(), parent.lower(), name)
        for key in ('reviewed_overrides', 'reviewed_stack_overrides'):
            rows = self.rules.get(key, [])
            identities = [inv.identity(r) for r in rows]
            self.assertEqual(len(identities), len(set(identities)), key + ' repeats a class')
            for row in rows:
                self.assertTrue(all(type(v) is int and v > 0 for v in row['new']), row['name'])
                if row['category'] != 'preserve-original':
                    self.assertNotEqual(row['vanilla'], row['new'], row['name'] + ' is a stale no-op row')

    def test_committed_inventory_output_names_no_restricted_provider(self):
        for addon, config in self.committed_configs().items():
            self.assertTrue(inv.inventory_sources.safe_text(config), addon)
        self.assertTrue(inv.inventory_sources.safe_text((ROOT / 'config/inventory-sizes.json').read_text()))

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


class BufferedPboReading(unittest.TestCase):
    """inventory_sources.read_index/iter_members must stay byte-for-byte equal to the audit reader."""

    def test_index_and_members_match_the_audit_reader(self):
        from tools.audit import pbo_config
        raw = synthetic_pbo({'config.bin': b'\0raPdata', 'Sub/Config.cpp': b'class A {};', 'x.paa': b'12'})
        with tempfile.TemporaryDirectory(prefix='hc-inventory-synthetic-') as tmp:
            path = Path(tmp) / 'gear_tools.pbo'
            path.write_bytes(raw)
            self.assertEqual(inv.inventory_sources.read_index(path), pbo_config.read_pbo_index(path))
            index = pbo_config.read_pbo_index(path)
            names = ['sub/config.cpp', 'config.bin', 'missing.bin']
            self.assertEqual(dict(inv.inventory_sources.iter_members(path, index, names)),
                             {n: pbo_config.read_member(path, index, n) for n in names})
            with self.assertRaises(ValueError):
                list(inv.inventory_sources.iter_members(path, index, ['config.bin'], max_bytes=3))
            with self.assertRaises(ValueError):
                inv.inventory_sources.read_index(path, max_entries=2)
            with self.assertRaises(ValueError):
                inv.inventory_sources.read_index(path, max_header_bytes=30)
            path.write_bytes(raw[:25])
            with self.assertRaises(ValueError):
                inv.inventory_sources.read_index(path)

    def test_documents_are_memoised_only_while_the_files_are_unchanged(self):
        first = klass(CfgPatches=klass(P=klass()), CfgVehicles=klass(A=klass('Inventory_Base', scope=2)))
        second = klass(CfgPatches=klass(P=klass()), CfgVehicles=klass(
            A=klass('Inventory_Base', scope=2), B=klass('Inventory_Base', scope=2)))
        with tempfile.TemporaryDirectory(prefix='hc-inventory-synthetic-') as tmp:
            path = Path(tmp) / 'gear_tools.pbo'
            path.write_bytes(synthetic_pbo({'config.bin': rap(first)}))
            args = (tmp, 'vanilla', inv.FIELDS, inv._config_rows)
            one = inv.inventory_sources.documents(*args, vanilla=True)
            self.assertEqual(inv.inventory_sources.documents(*args, vanilla=True), one)
            path.write_bytes(synthetic_pbo({'config.bin': rap(second)}))
            rows = inv.inventory_sources.documents(*args, vanilla=True)[0][0]['rows']
            self.assertEqual(sorted(rows), ['A', 'B'])
