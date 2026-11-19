"""Datamined unused-but-finished vanilla NON-weapon items: Chernarus CE rows (offline, synthetic).

Synthetic fixtures only establish the module's own rules. What the engine does with the
rows is unobserved: every row stays acceptance pending-local.
"""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from tools.package import datamined_items as dm
from tools.package import economy

CACHE = Path(os.environ.get('HC_CACHE', Path.home() / '.cache/hollow-country'))
ADDONS = CACHE / 'wine-server-20261116/addons'
MISSIONS = CACHE / 'wine-server-20261116/mpmissions'

SHORTLIST = (
    ['LeatherJacket_' + c for c in ('Natural', 'Beige', 'Brown', 'Black')]
    + ['LeatherShoes_' + c for c in ('Natural', 'Beige', 'Brown', 'Black')]
    + ['LeatherHat_' + c for c in ('Natural', 'Beige', 'Brown', 'Black')]
    + ['LeatherShirt_Natural', 'HuntingJacket_Spring', 'HunterPants_Spring',
       'WinterMilitaryCoat_Brown', 'WinterMilitaryCoat_DarkGrey', 'WinterMilitaryCoat_Grey',
       'HuntingBag_Hannah', 'DrysackBag_Green', 'DrysackBag_Orange', 'DrysackBag_Yellow',
       'Iceaxe', 'FilteringBottle', 'CrabCan'])
EXTRAS = (
    ['GorkaEJacket_Winter', 'GorkaPants_Winter', 'HuntingVest_Winter', 'BoonieHat_Winter',
     'BudenovkaHat_Gray']
    + ['ColdOperationBoots_' + c for c in ('Camo', 'Green', 'Grey')]
    + ['PilotJacket_' + c for c in ('Black', 'Brown', 'Yellow')]
    + ['DownJacket_' + c for c in ('Blue', 'Red', 'Orange', 'Green')]
    + ['SkiGloves_' + c for c in ('90s', 'Blue', 'Red')]
    + ['LeatherGloves_' + c for c in ('Beige', 'Black', 'Brown', 'Natural')]
    + ['SkiGoggles_' + c for c in ('BlackYellow', 'WhiteClear', 'WhiteDark')]
    + ['Bandana_Blue', 'Bandana_Pink', 'Bandana_Yellow']
    + ['Attack2Bag_Black', 'Attack2Bag_Yeger', 'AssaultBag_Winter', 'CoyoteBag_Winter',
       'TortillaBag_Winter', 'TortillaBag_Desert'])
CRAFT = ['LeatherPants_' + c for c in ('Natural', 'Beige', 'Brown', 'Black')] \
    + ['LeatherStorageVest_' + c for c in ('Natural', 'Beige', 'Brown', 'Black')]
VOCAB = {'Military', 'Police', 'Medic', 'Firefighter', 'Industrial', 'Farm', 'Coast', 'Town', 'Village',
         'Hunting', 'Office', 'School', 'Prison', 'Lunapark', 'SeasonalEvent', 'ContaminatedArea', 'Historical'}


def catalog_for(rows, **overrides):
    """Synthetic resolved config: every row class is a finished scope-2 vanilla item."""
    catalog = {r['class'].lower(): {'scope': 2, 'lootCategory': None, 'displayName': 'Synthetic ' + r['class'],
                                    'source': 'characters_tops.pbo'} for r in rows}
    for name, patch in overrides.items():
        catalog[name.lower()].update(patch)
    return catalog


def stock_for(rows, nominal='0'):
    """Synthetic stock types: unspawned entries that already carry every retained field."""
    stock = {}
    for r in rows:
        if r['stock'] != 'present':
            continue
        t = ET.Element('type', {'name': r['class']})
        for tag, text in (('nominal', nominal), ('lifetime', str(r['lifetime'])), ('restock', '0'), ('min', '0'),
                          ('quantmin', str(r['quantmin'])), ('quantmax', str(r['quantmax'])), ('cost', str(r['cost']))):
            ET.SubElement(t, tag).text = text
        ET.SubElement(t, 'flags', dict(zip(dm.FLAG_ORDER, r['flags'])))
        if r['category'] is not None and r['class'] != 'FilteringBottle':
            ET.SubElement(t, 'category', {'name': r['category']})
        stock[r['class']] = t
    return stock


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = dm.load_rows()
        cls.by_name = {r['class']: r for r in cls.rows}


class SchemaAndCoverage(Base):
    def test_rows_use_the_exact_schema_and_stay_pending_local(self):
        for r in self.rows:
            with self.subTest(r['class']):
                self.assertEqual(set(r), set(dm.ROW_KEYS))
                self.assertEqual(r['acceptance'], 'pending-local')
                self.assertIn(r['stock'], {'present', 'absent'})
                self.assertRegex(r['flags'], r'^[01]{6}$')
                self.assertTrue(r['source_map_note'].strip())
                self.assertTrue(r['placement'].strip())
        names = [r['class'].lower() for r in self.rows]
        self.assertEqual(len(names), len(set(names)))

    def test_owner_shortlist_and_extras_are_all_present(self):
        self.assertFalse(set(SHORTLIST + EXTRAS) - set(self.by_name))
        self.assertEqual(set(self.by_name) - set(SHORTLIST + EXTRAS), set())

    def test_excluded_and_craft_classes_are_not_rows(self):
        for name in CRAFT + ['EngineOil', 'BrakeFluid', 'ChelatingTablets', 'AssaultBag_Desert',
                             'CoyoteBag_Desert', 'BoonieHat_Desert', 'HuntingVest_Desert',
                             'Bandana_RedPattern', 'Bandana_BlackPattern', 'Bandana_PolkaPattern',
                             'Bandana_CamoPattern', 'ShippingContainerKeys_Blue']:
            self.assertNotIn(name, self.by_name)

    def test_craft_output_candidates_are_listed_not_spawned(self):
        self.assertEqual(sorted(dm.craft_output_candidates()), sorted(CRAFT))
        self.assertFalse(set(dm.craft_output_candidates()) & set(self.by_name))

    def test_malformed_rows_are_refused(self):
        catalog = catalog_for(self.rows)
        mutations = {
            'missing key': lambda r: r.pop('lifetime'),
            'extra key': lambda r: r.update(extra=1),
            'min above nominal': lambda r: r.update(min=r['nominal'] + 1),
            'negative nominal': lambda r: r.update(nominal=-1, min=-1),
            'bool nominal': lambda r: r.update(nominal=True),
            'bad flags': lambda r: r.update(flags='00100'),
            'bad quant': lambda r: r.update(quantmin=5, quantmax=2),
            'accepted': lambda r: r.update(acceptance='accepted'),
            'no usage': lambda r: r.update(usage=[]),
            'duplicate usage': lambda r: r.update(usage=['Town', 'Town']),
            'unknown usage': lambda r: r.update(usage=['Invented']),
            'unknown tier': lambda r: r.update(value=['Tier9']),
            'bad stock': lambda r: r.update(stock='maybe'),
            'empty note': lambda r: r.update(source_map_note=' '),
        }
        for label, mutate in mutations.items():
            rows = copy.deepcopy(self.rows)
            mutate(rows[0])
            with self.subTest(label), self.assertRaises(ValueError):
                dm.validate_rows(rows, catalog, vocabulary=VOCAB)
        rows = copy.deepcopy(self.rows) + [copy.deepcopy(self.rows[0])]
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            dm.validate_rows(rows, catalog, vocabulary=VOCAB)

    def test_the_shipped_rows_validate_against_synthetic_config(self):
        dm.validate_rows(self.rows, catalog_for(self.rows), vocabulary=VOCAB)


class PlacementPolicy(Base):
    def usage(self, name):
        return set(self.by_name[name]['usage'])

    def test_grounded_placements(self):
        for n in SHORTLIST[:13] + ['HuntingJacket_Spring', 'HunterPants_Spring', 'HuntingBag_Hannah']:
            self.assertTrue(self.usage(n) & {'Hunting', 'Village'}, n)
        for n in ('WinterMilitaryCoat_Brown', 'WinterMilitaryCoat_DarkGrey', 'WinterMilitaryCoat_Grey',
                  'GorkaEJacket_Winter', 'GorkaPants_Winter', 'ColdOperationBoots_Camo',
                  'ColdOperationBoots_Green', 'ColdOperationBoots_Grey', 'PilotJacket_Black',
                  'PilotJacket_Brown', 'PilotJacket_Yellow', 'Attack2Bag_Black', 'Attack2Bag_Yeger',
                  'AssaultBag_Winter', 'CoyoteBag_Winter', 'TortillaBag_Winter', 'TortillaBag_Desert'):
            self.assertIn('Military', self.usage(n), n)
        for n in [x for x in EXTRAS if x.startswith(('DownJacket_', 'SkiGloves_', 'SkiGoggles_'))]:
            self.assertTrue(self.usage(n) <= {'Town', 'Village'} and self.usage(n), n)
        for n in ('Bandana_Blue', 'Bandana_Pink', 'Bandana_Yellow'):
            self.assertEqual(self.usage(n), {'Town', 'Village'})
        for n in ('DrysackBag_Green', 'DrysackBag_Orange', 'DrysackBag_Yellow'):
            self.assertEqual(self.usage(n), {'Coast', 'Village'})
        self.assertEqual(self.usage('Iceaxe'), {'Industrial', 'Farm'})
        self.assertTrue(self.usage('FilteringBottle') <= {'Medic', 'Hunting'})
        self.assertEqual(self.usage('CrabCan'), {'Coast', 'Village'})

    def test_every_row_stays_at_or_below_its_vanilla_equivalent(self):
        for r in self.rows:
            with self.subTest(r['class']):
                self.assertGreater(r['equivalent']['nominal'], 0)
                self.assertLessEqual(r['nominal'], r['equivalent']['nominal'])

    def test_winter_only_gear_is_rarer_than_native_winter_gear(self):
        # Native Chernarus winter gear (HuntingJacket_Winter/HunterPants_Winter) is nominal 4.
        winter = [r for r in self.rows if r['winter_only']]
        self.assertGreaterEqual(len(winter), 20)
        for r in winter:
            self.assertLessEqual(r['nominal'], dm.WINTER_CEILING, r['class'])
        self.assertLess(dm.WINTER_CEILING, 4)

    def test_rare_items_are_rare_and_the_total_is_modest(self):
        for n in ('Iceaxe', 'FilteringBottle', 'HuntingBag_Hannah'):
            self.assertLessEqual(self.by_name[n]['nominal'], 3)
        total = dm.total_nominal(self.rows)
        self.assertLessEqual(total, 140)
        self.assertGreaterEqual(total, 50)

    def test_every_row_has_a_source_map_note_for_other_map_spawns(self):
        for n in ('WinterMilitaryCoat_Grey', 'HunterPants_Spring', 'CrabCan', 'Iceaxe'):
            self.assertTrue(self.by_name[n]['source_maps'], n)
        for n in ('LeatherJacket_Black', 'DrysackBag_Green', 'Bandana_Blue'):
            self.assertEqual(self.by_name[n]['source_maps'], {}, n)


class ConfigRefusals(Base):
    def refuse(self, name, patch, pattern):
        catalog = catalog_for(self.rows, **{name: patch})
        with self.assertRaisesRegex(ValueError, pattern):
            dm.validate_rows(self.rows, catalog, vocabulary=VOCAB)

    def test_every_class_must_exist_with_scope_two(self):
        for r in self.rows:
            with self.subTest(r['class']):
                self.refuse(r['class'], {'scope': 1}, 'scope')
                self.refuse(r['class'], {'scope': 0}, 'scope')
        catalog = catalog_for(self.rows)
        del catalog['iceaxe']
        with self.assertRaisesRegex(ValueError, 'Iceaxe.*not in the installed config'):
            dm.validate_rows(self.rows, catalog, vocabulary=VOCAB)

    def test_scope_must_be_the_integer_two(self):
        self.refuse('Iceaxe', {'scope': '2'}, 'scope')
        self.refuse('Iceaxe', {'scope': None}, 'scope')

    def test_unfinished_names_nasdara_and_crafted_config_are_refused(self):
        self.refuse('CrabCan', {'displayName': '$UNT$Crab'}, r'\$UNT\$')
        self.refuse('CrabCan', {'source': 'characters_nasdara.pbo'}, 'Nasdara')
        self.refuse('CrabCan', {'source': 'weapons_NASDARA.pbo'}, 'Nasdara')
        self.refuse('CrabCan', {'lootCategory': 'Crafted'}, 'Crafted')
        self.refuse('CrabCan', {'lootCategory': 'crafted'}, 'Crafted')

    def row(self, name, **extra):
        r = copy.deepcopy(self.by_name['CrabCan'])
        r.update(extra, **{'class': name})
        return r

    def test_excluded_classes_are_refused_even_with_clean_config(self):
        for name in ('EngineOil', 'BrakeFluid', 'ChelatingTablets', 'EngineOil_Test',
                     'ShippingContainerKeys_Blue', 'ScientificBriefcaseKeys', 'TestItem', 'Dev_Crate',
                     'AssaultBag_Debug'):
            rows = [self.row(name)]
            with self.subTest(name), self.assertRaisesRegex(ValueError, 'excluded'):
                dm.validate_rows(rows, catalog_for(rows), vocabulary=VOCAB)

    def test_crafted_classes_are_refused_as_spawns(self):
        for name in CRAFT:
            rows = [self.row(name)]
            with self.subTest(name), self.assertRaisesRegex(ValueError, 'craft'):
                dm.validate_rows(rows, catalog_for(rows), vocabulary=VOCAB)
        rows = [self.row('SomeOtherSewnThing')]
        catalog = catalog_for(rows, SomeOtherSewnThing={'lootCategory': 'Crafted'})
        with self.assertRaisesRegex(ValueError, 'Crafted'):
            dm.validate_rows(rows, catalog, vocabulary=VOCAB)


class StockAndOtherMapChecks(Base):
    def test_stock_presence_must_match_and_case_variants_are_duplicates(self):
        rows = copy.deepcopy(self.rows)
        stock = stock_for(rows)
        bandana = next(r for r in rows if r['class'] == 'Bandana_Blue')
        stock['Bandana_BLUE'] = ET.Element('type', {'name': 'Bandana_BLUE'})  # case-insensitive duplicate
        with self.assertRaisesRegex(ValueError, 'already in stock'):
            dm.validate_rows(rows, catalog_for(rows), stock=stock, vocabulary=VOCAB)
        stock = stock_for(rows)
        del stock['Iceaxe']
        with self.assertRaisesRegex(ValueError, 'Iceaxe.*stock'):
            dm.validate_rows(rows, catalog_for(rows), stock=stock, vocabulary=VOCAB)
        self.assertEqual(bandana['stock'], 'absent')

    def test_stock_equivalent_nominal_and_retained_fields_are_checked(self):
        rows = copy.deepcopy(self.rows)
        stock = stock_for(rows)
        eq_stock = {'BomberJacket_Brown': 7}
        for r in rows:  # make every equivalent resolvable and consistent
            eq_stock[r['equivalent']['class']] = r['equivalent']['nominal']
        dm.validate_rows(rows, catalog_for(rows), stock=stock, vocabulary=VOCAB, equivalents=eq_stock)
        bad = dict(eq_stock, **{rows[0]['equivalent']['class']: rows[0]['equivalent']['nominal'] + 1})
        with self.assertRaisesRegex(ValueError, 'equivalent'):
            dm.validate_rows(rows, catalog_for(rows), stock=stock, vocabulary=VOCAB, equivalents=bad)
        stock = stock_for(rows)
        stock['CrabCan'].find('cost').text = '250'
        with self.assertRaisesRegex(ValueError, 'CrabCan.*cost'):
            dm.validate_rows(rows, catalog_for(rows), stock=stock, vocabulary=VOCAB)
        stock = stock_for(rows)
        stock['PilotJacket_Black'].append(ET.Element('usage', {'name': 'Police'}))
        with self.assertRaisesRegex(ValueError, 'PilotJacket_Black.*usage'):
            dm.validate_rows(rows, catalog_for(rows), stock=stock, vocabulary=VOCAB)

    def test_other_map_hints_must_match_and_cap_the_nominal(self):
        rows = copy.deepcopy(self.rows)
        other = {'sakhal': {}, 'enoch': {}}
        for r in rows:
            for m, n in r['source_maps'].items():
                other[m][r['class'].lower()] = n
        dm.validate_rows(rows, catalog_for(rows), vocabulary=VOCAB, other_maps=other)
        wrong = copy.deepcopy(other)
        wrong['sakhal']['wintermilitarycoat_grey'] += 1
        with self.assertRaisesRegex(ValueError, 'source map'):
            dm.validate_rows(rows, catalog_for(rows), vocabulary=VOCAB, other_maps=wrong)
        missing = copy.deepcopy(other)
        missing['sakhal']['leatherjacket_black'] = 5  # spawns elsewhere but the row carries no note
        with self.assertRaisesRegex(ValueError, 'LeatherJacket_Black.*source map'):
            dm.validate_rows(rows, catalog_for(rows), vocabulary=VOCAB, other_maps=missing)
        capped = copy.deepcopy(rows)
        row = next(r for r in capped if r['class'] == 'CrabCan')
        row['nominal'], row['min'] = 21, 1
        row['equivalent']['nominal'] = 99
        other2 = copy.deepcopy(other)
        with self.assertRaisesRegex(ValueError, 'CrabCan.*other-map'):
            dm.validate_rows(capped, catalog_for(capped), vocabulary=VOCAB, other_maps=other2)

    def test_winter_flag_cap_is_enforced(self):
        rows = copy.deepcopy(self.rows)
        row = next(r for r in rows if r['winter_only'])
        row['nominal'] = dm.WINTER_CEILING + 1
        row['equivalent']['nominal'] = 99
        for m in row['source_maps']:
            row['source_maps'][m] = 99
        with self.assertRaisesRegex(ValueError, 'winter'):
            dm.validate_rows(rows, catalog_for(rows), vocabulary=VOCAB)


class EconomyShape(Base):
    def setUp(self):
        self.rows = copy.deepcopy(self.__class__.rows)
        self.stock = stock_for(self.rows)

    def out(self, **kw):
        return dm.type_rows(self.stock, vocabulary=VOCAB, rows=self.rows, **kw)

    def test_rows_are_type_elements_that_pass_the_economy_budget_check(self):
        out = self.out()
        present = [r['class'] for r in self.rows if r['stock'] == 'present']
        self.assertEqual([e.get('name') for e in out], sorted(present))
        for e in out:
            self.assertEqual(e.tag, 'type')
            self.assertEqual(set(e.attrib), {'name'})
            economy._validate_budget(e)
            usages = e.findall('usage')
            economy._unique(usages)
            self.assertTrue(usages)

    def test_output_keeps_stock_fields_except_the_declared_mutable_set(self):
        for e in self.out():
            s = self.stock[e.get('name')]
            r = next(x for x in self.rows if x['class'] == e.get('name'))
            for tag in ('quantmin', 'quantmax', 'cost'):
                self.assertEqual(e.findtext(tag), s.findtext(tag))
            self.assertEqual(e.find('flags').attrib, s.find('flags').attrib)
            self.assertEqual(e.findtext('nominal'), str(r['nominal']))
            self.assertEqual(e.findtext('min'), str(r['min']))
            self.assertEqual(e.findtext('lifetime'), str(r['lifetime']))
            self.assertEqual(e.findtext('restock'), str(r['restock']))
            self.assertEqual([u.get('name') for u in e.findall('usage')], sorted(r['usage']))
            self.assertEqual([v.get('name') for v in e.findall('value')], sorted(r['value']))
            self.assertEqual(self.stock[e.get('name')].findtext('nominal'), '0')  # stock not mutated
        changed = dm.retention_changes(self.out(), self.stock)
        # The synthetic stock already carries each row's lifetime, so lifetime may not differ here.
        self.assertLessEqual(changed, {'nominal', 'min', 'lifetime', 'restock', 'usage', 'value', 'category'})
        self.assertLessEqual({'nominal', 'min', 'restock', 'usage', 'value', 'category'}, changed)

    def test_children_follow_the_stock_order(self):
        order = ['nominal', 'lifetime', 'restock', 'min', 'quantmin', 'quantmax', 'cost', 'flags',
                 'category', 'usage', 'value']
        for e in self.out():
            tags = [c.tag for c in e]
            self.assertEqual(tags, sorted(tags, key=order.index))

    def test_only_filtering_bottle_needs_a_category_the_stock_lacks(self):
        added = [e.get('name') for e in self.out()
                 if self.stock[e.get('name')].find('category') is None]
        self.assertEqual(added, ['FilteringBottle'])
        self.assertEqual(self.out()[[e.get('name') for e in self.out()].index('FilteringBottle')]
                         .find('category').get('name'), 'tools')

    def test_stock_absent_rows_need_include_new(self):
        out = self.out()
        names = {e.get('name') for e in out}
        self.assertFalse({'Bandana_Blue', 'Bandana_Pink', 'Bandana_Yellow'} & names)
        new = {e.get('name'): e for e in self.out(include_new=True) if e.get('name') not in names}
        self.assertEqual(set(new), {'Bandana_Blue', 'Bandana_Pink', 'Bandana_Yellow'})
        for e in new.values():
            economy._validate_budget(e)
            self.assertEqual(e.find('category').get('name'), 'clothes')

    def test_output_is_deterministic_and_does_not_alias_the_stock(self):
        a = [ET.tostring(e) for e in self.out()]
        b = [ET.tostring(e) for e in self.out()]
        self.assertEqual(a, b)
        self.out()[0].set('name', 'Changed')
        self.assertEqual([ET.tostring(e) for e in self.out()], a)

    def test_a_usage_dropped_from_stock_is_refused(self):
        self.stock['PilotJacket_Black'].append(ET.Element('usage', {'name': 'Police'}))
        with self.assertRaisesRegex(ValueError, 'PilotJacket_Black.*usage'):
            self.out()

    def test_default_rows_work_with_a_real_economy_generate_stock_dictionary(self):
        with tempfile.TemporaryDirectory() as t:
            root = ET.Element('types')
            root.extend(self.stock.values())
            path = Path(t) / 'types.xml'
            path.write_bytes(ET.tostring(root))
            stock = economy._unique(economy.xml(path.read_bytes(), 'types').findall('type'))
            out = dm.type_rows(stock, vocabulary=VOCAB)
            self.assertEqual(len(out), len([r for r in self.rows if r['stock'] == 'present']))


def cint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def rap_body(node, start):
    classes = [(k, v) for k, v in node.items() if isinstance(v, dict) and not k.startswith('__')]
    scalars = [(k, v) for k, v in node.items() if not isinstance(v, dict) and not k.startswith('__')]

    def entries(offsets):
        out = bytearray()
        for k, v in scalars:
            if isinstance(v, str):
                out += b'\x01\x00' + k.encode() + b'\0' + v.encode() + b'\0'
            else:
                out += b'\x01\x02' + k.encode() + b'\0' + struct.pack('<i', v)
        for (k, _), off in zip(classes, offsets):
            out += b'\x00' + k.encode() + b'\0' + struct.pack('<I', off)
        return bytes(out)
    head = node.get('__parent__', '').encode() + b'\0' + cint(len(scalars) + len(classes))
    size = len(head) + len(entries([0] * len(classes)))
    pos, offs, blobs = start + size, [], []
    for _, child in classes:
        blob = rap_body(child, pos)
        offs.append(pos)
        blobs.append(blob)
        pos += len(blob)
    return head + entries(offs) + b''.join(blobs)


def config_bin(tree):
    return b'\0raP' + struct.pack('<III', 0, 8, 0) + rap_body(tree, 16)


def pbo(path, config, prefix='x'):
    header = b'\0' + struct.pack('<5I', 0x56657273, 0, 0, 0, 0) + b'prefix\0' + prefix.encode() + b'\0\0'
    header += b'config.bin\0' + struct.pack('<5I', 0, 0, 0, 0, len(config)) + b'\0' + struct.pack('<5I', 0, 0, 0, 0, 0)
    Path(path).write_bytes(header + config)


class InstalledConfigReader(unittest.TestCase):
    def test_catalog_reads_nested_weapon_config_members(self):
        """SYNTHETIC nested config.bin models the installed firearms PBO layout."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'weapons_firearms.pbo'
            pbo(path, config_bin({'CfgWeapons': {
                'CZ527': {'__parent__': '', 'scope': 2},
                'CZ527_Camo': {'__parent__': 'CZ527'}}}))
            path.write_bytes(path.read_bytes().replace(b'config.bin\0', b'cz527\\config.bin\0', 1))
            self.assertEqual(dm.load_catalog(directory)['cz527_camo']['scope'], 2)

    def test_catalog_resolves_inherited_scope_loot_category_and_source(self):
        with tempfile.TemporaryDirectory() as t:
            tops = {'CfgVehicles': {
                'Clothing': {'__parent__': '', 'scope': 0, 'lootCategory': 'Crafted'},
                'Base': {'__parent__': 'Clothing', 'scope': 0, 'displayName': 'Base'},
                'Jacket': {'__parent__': 'Base', 'scope': 2, 'displayName': 'Jacket', 'lootCategory': 'Tools',
                           'DamageSystem': {'__parent__': '', 'scope': 9}},
                'Inherits': {'__parent__': 'Jacket'}}}
            pbo(Path(t) / 'characters_tops.pbo', config_bin(tops))
            nas = {'CfgVehicles': {'Desert': {'__parent__': 'Jacket', 'scope': 2, 'displayName': '$UNT$Desert'}}}
            pbo(Path(t) / 'characters_nasdara.pbo', config_bin(nas))
            catalog = dm.load_catalog(t)
        self.assertEqual(catalog['jacket'], {'scope': 2, 'lootCategory': 'Tools', 'displayName': 'Jacket',
                                             'source': 'characters_tops.pbo'})
        self.assertEqual(catalog['inherits']['scope'], 2)
        self.assertEqual(catalog['inherits']['lootCategory'], 'Tools')
        self.assertEqual(catalog['base']['lootCategory'], 'Crafted')  # inherited from Clothing
        self.assertEqual(catalog['desert']['source'], 'characters_nasdara.pbo')
        self.assertEqual(catalog['desert']['displayName'], '$UNT$Desert')
        self.assertNotIn('damagesystem', catalog)  # nested classes are not catalogued

    def test_truncated_or_unrapified_config_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            pbo(Path(t) / 'a.pbo', b'not a rap file at all, just text')
            with self.assertRaises(ValueError):
                dm.load_catalog(t)
        with tempfile.TemporaryDirectory() as t:
            blob = config_bin({'CfgVehicles': {'A': {'__parent__': '', 'scope': 2}}})
            pbo(Path(t) / 'a.pbo', blob[:-6])
            with self.assertRaises(ValueError):
                dm.load_catalog(t)

    def test_missing_directory_is_refused(self):
        with self.assertRaises(ValueError):
            dm.load_catalog('/nonexistent-addons-directory')


@unittest.skipUnless((ADDONS / 'characters_tops.pbo').is_file()
                     and (MISSIONS / 'dayzOffline.chernarusplus/db/types.xml').is_file(),
                     'installed addon/mission cache absent')
class AgainstInstalledVanilla(unittest.TestCase):
    """Static evidence from the local server install. It is not proof of CE behaviour."""

    @classmethod
    def setUpClass(cls):
        cls.rows = dm.load_rows()
        cls.catalog = dm.load_catalog(ADDONS)
        cls.stock = dm.read_types(MISSIONS / 'dayzOffline.chernarusplus/db/types.xml')
        cls.other = {m: {n.lower(): int(e.findtext('nominal')) for n, e in
                         dm.read_types(MISSIONS / f'dayzOffline.{m}/db/types.xml').items()
                         if int(e.findtext('nominal') or 0) > 0}
                     for m in ('enoch', 'sakhal', 'nasdara')}
        lim = ET.parse(MISSIONS / 'dayzOffline.chernarusplus/cfglimitsdefinition.xml').getroot()
        cls.vocab = {u.get('name') for u in lim.findall('./usageflags/usage')}

    def test_rows_validate_against_the_installed_config_stock_and_other_maps(self):
        equivalents = {n: int(e.findtext('nominal')) for n, e in self.stock.items()}
        dm.validate_rows(self.rows, self.catalog, stock=self.stock, vocabulary=self.vocab,
                         other_maps={m: v for m, v in self.other.items() if m != 'nasdara'},
                         equivalents=equivalents)

    def test_reviewed_new_classes_exist_in_installed_config(self):
        from tests.unit.test_firearms_roster import NEW_PARENTS
        for class_name in NEW_PARENTS:
            with self.subTest(class_name=class_name):
                self.assertIn(class_name.lower(), self.catalog)
                self.assertEqual(self.catalog[class_name.lower()]['scope'], 2)
                if class_name in ('CZ527_desert', 'CZ527_winter'):
                    stock_name = next(name for name in self.stock if name.lower() == class_name.lower())
                    self.assertEqual(self.stock[stock_name].findtext('nominal'), '0')
                else:
                    self.assertNotIn(class_name.lower(), {name.lower() for name in self.stock})

    def test_installed_config_marks_the_excluded_and_crafted_classes(self):
        for name in CRAFT:
            self.assertEqual(self.catalog[name.lower()]['lootCategory'].lower(), 'crafted')
        # The Nasdara DLC pbos are not in the server addons, so the DLC-gated desert packs are not
        # resolvable here and validate_rows refuses them as absent from the installed config.
        self.assertNotIn('assaultbag_desert', self.catalog)
        row_set = {r['class'] for r in self.rows}
        self.assertFalse(row_set & set(CRAFT))

    def test_real_rows_build_valid_type_elements(self):
        out = dm.type_rows(self.stock, vocabulary=self.vocab, include_new=False)
        self.assertGreaterEqual(len(out), 50)
        for e in out:
            economy._validate_budget(e)

    def test_the_four_census_bandana_patterns_already_spawn_under_another_case(self):
        for name in ('Bandana_RedPattern', 'Bandana_BlackPattern', 'Bandana_PolkaPattern', 'Bandana_CamoPattern'):
            self.assertIn(name.lower(), {k.lower() for k in self.stock})


def stock_mission(root, rows, profile_names=('SynthTool',)):
    """Synthetic CE mission: datamined stock rows (nominal 0) plus profile-eligible synthetic types."""
    (root / 'db').mkdir(parents=True)
    types = ET.Element('types')
    types.extend(stock_for(rows).values())
    for name in profile_names:
        extra = ET.fromstring(
            f'<type name="{name}"><nominal>10</nominal><lifetime>1000</lifetime><restock>100</restock>'
            '<min>5</min><quantmin>-1</quantmin><quantmax>-1</quantmax><cost>100</cost>'
            '<flags count_in_cargo="0" count_in_hoarder="1" count_in_map="1" count_in_player="0" '
            'crafted="0" deloot="0"/><category name="tools"/><usage name="Village"/><value name="Tier2"/></type>')
        types.append(extra)
    (root / 'db/types.xml').write_bytes(ET.tostring(types))
    (root / 'cfgeconomycore.xml').write_bytes(
        b'<?xml version="1.0"?><economycore><!--keep exactly--><defaults/></economycore>')
    (root / 'cfglimitsdefinition.xml').write_text(
        '<lists><usageflags>' + ''.join(f'<usage name="{u}"/>' for u in sorted(VOCAB)) + '</usageflags>'
        '<valueflags><value name="Tier1"/><value name="Tier2"/><value name="Tier3"/><value name="Tier4"/>'
        '</valueflags></lists>')
    (root / 'mapgroupproto.xml').write_text('<prototype><group name="G" lootmax="0"/></prototype>')
    (root / 'mapgrouppos.xml').write_text('<map><group name="G" pos="1 2 3"/></map>')


def profile(**add_usage):
    return {'schema': 1, 'name': 'synthetic-datamined', 'add_usage': add_usage or {'SynthTool': ['Town']},
            'diagnostics': []}


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


class UsefulSupply(Base):
    """HC-22 behavior on an explicitly SYNTHETIC mission; no native CE evidence."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'source'
        stock_mission(self.root, self.rows)
        self.pilot = profile() | {'name': 'contextual-pilot'}
        self.before = tree(self.root)

    def generate(self, **kwargs):
        return economy.generate(self.root, self.pilot, **kwargs)

    def stage(self, files):
        stage = Path(self.tmp.name) / 'delta'
        manifest = json.loads(files['delta-manifest.json'])
        manifest['files'] = {n: economy.sha(b) for n, b in files.items() if n != 'delta-manifest.json'}
        files['delta-manifest.json'] = economy.encode(manifest)
        economy.write_delta(stage, files)
        return stage

    def refuse_install(self, files, code):
        with self.assertRaisesRegex(ValueError, code):
            economy.install_delta(self.stage(files), self.root)
        self.assertEqual(self.before, tree(self.root))

    def test_pilot_emits_all_fifty_nine_finite_supply_rows(self):
        files = self.generate()
        emitted = economy._unique(ET.fromstring(files['ce/types.xml']))
        expected = {
            **{family + '_' + colour: ('unresolved', 'HC22_CRAFTED_FLOOR_UNPROVEN')
               for family in ('LeatherJacket', 'LeatherShoes', 'LeatherHat')
               for colour in ('Natural', 'Beige', 'Brown', 'Black')},
            'LeatherShirt_Natural': ('unresolved', 'HC22_CRAFTED_FLOOR_UNPROVEN'),
            **{'LeatherGloves_' + c: ('native-floor', None) for c in ('Beige', 'Black', 'Brown', 'Natural')},
            **{'DrysackBag_' + c: ('native-craft', 'HC22_CRAFTED_FLOOR_UNPROVEN')
               for c in ('Green', 'Orange', 'Yellow')},
            'TortillaBag_Desert': ('native-carrier', 'HC22_EVENT_CARRIER_UNQUALIFIED')}
        report = json.loads(files['economy-report.json'])['supply']
        self.assertEqual(report['refusals'], [])
        self.assertTrue(set(expected) <= set(emitted))
        for name in ('Bandana_Blue', 'Bandana_Pink', 'Bandana_Yellow'):
            self.assertEqual(emitted[name].findtext('nominal'), '5')
            self.assertEqual({n.get('name') for n in emitted[name].findall('usage')}, {'Town', 'Village'})
        self.assertEqual((report['authored'], report['admitted'], report['observed']), (59, 59, 0))
        self.assertEqual(report['runtime_acceptance'], 'pending')
        self.assertEqual(report['dispositions_sha256'], economy.sha(dm.SUPPLY_DATA.read_bytes()))
        self.assertEqual(json.loads(files['delta-manifest.json'])['supply_new_type_classes'],
                         ['Bandana_Blue', 'Bandana_Pink', 'Bandana_Yellow'])

    def test_report_counts_floor_refusals_by_route_and_reason(self):
        report = json.loads(self.generate()['economy-report.json'])['supply']
        self.assertNotIn('unresolved', report)
        self.assertEqual(report['floor_refused'], 0)
        self.assertEqual(report['refused_by_route'], {})
        self.assertEqual(report['refused_by_reason'],
                         {})
        off = self.generate(include_datamined=False)
        report = json.loads(off['economy-report.json'])['supply']
        self.assertEqual((report['state'], report['admitted'], report['floor_refused']), ('off', 0, 0))
        self.assertEqual(report['refused_by_route'], {})
        self.assertEqual(report['refused_by_reason'], {})
        self.assertEqual(json.loads(off['delta-manifest.json'])['supply_new_type_classes'], [])

    def test_install_refuses_rehashed_bandana_nominal_drift(self):
        files = self.generate()
        types = ET.fromstring(files['ce/types.xml'])
        types.find("type[@name='Bandana_Blue']/nominal").text = '2'
        files['ce/types.xml'] = ET.tostring(types)
        self.refuse_install(files, 'HC22_NEW_TYPE_DRIFT')

    def test_install_refuses_bandana_already_in_stock_in_any_case(self):
        for spelling in ('Bandana_Blue', 'BANDANA_BLUE', 'bandana_blue'):
            with self.subTest(spelling=spelling):
                (self.root / 'db/types.xml').write_bytes(self.before['db/types.xml'])
                files = self.generate()
                stock = ET.fromstring(self.before['db/types.xml'])
                row = dm.reviewed_supply_type('Bandana_Blue')
                row.set('name', spelling)
                stock.append(row)
                (self.root / 'db/types.xml').write_bytes(ET.tostring(stock))
                # SYNTHETIC manifest is rehashed to exercise the row guard beyond source-drift refusal.
                manifest = json.loads(files['delta-manifest.json'])
                manifest['sources'] = {n: economy.sha(b) for n, b in economy.snapshot(self.root).items()}
                files['delta-manifest.json'] = economy.encode(manifest)
                before = tree(self.root)
                with self.assertRaisesRegex(ValueError, 'HC22_NEW_TYPE_ALREADY_IN_STOCK'):
                    economy.install_delta(self.stage(files), self.root)
                self.assertEqual(before, tree(self.root))
                shutil.rmtree(Path(self.tmp.name) / 'delta')
        (self.root / 'db/types.xml').write_bytes(self.before['db/types.xml'])

    def test_install_refuses_unreviewed_supply_permission(self):
        files = self.generate()
        manifest = json.loads(files['delta-manifest.json'])
        manifest['supply_new_type_classes'].append('Iceaxe')
        files['delta-manifest.json'] = economy.encode(manifest)
        self.refuse_install(files, 'HC22_NEW_TYPE_NOT_REVIEWED')

    def test_generate_refuses_row_without_disposition(self):
        ledger = dm.load_supply_dispositions()
        ledger['entries'] = [e for e in ledger['entries'] if e['class'] != 'Bandana_Blue']
        with mock.patch.object(dm, 'load_supply_dispositions', return_value=ledger):
            with self.assertRaisesRegex(ValueError, 'HC22_MISSING_DISPOSITION: Bandana_Blue'):
                self.generate()
        self.assertEqual(self.before, tree(self.root))

    def test_generate_refuses_floor_admission_with_crafted_or_deloot_flags(self):
        for flags in ('001010', '001001'):
            rows = copy.deepcopy(self.rows)
            next(r for r in rows if r['class'] == 'Bandana_Blue')['flags'] = flags
            with self.subTest(flags=flags), mock.patch.object(dm, 'load_rows', return_value=rows):
                with self.assertRaisesRegex(ValueError, 'HC22_UNQUALIFIED_FLOOR_FLAGS: Bandana_Blue'):
                    self.generate()
        self.assertEqual(self.before, tree(self.root))

    def test_install_floor_flag_exception_is_exact_and_does_not_widen_other_fields(self):
        cases = (
            ('DrysackBag_Green', 'crafted', '1'),
            ('TortillaBag_Desert', 'deloot', '1'),
            ('LeatherHat_Beige', 'deloot', '1'),
            ('DrysackBag_Green', 'count_in_player', '1'),
            ('DrysackBag_Green', 'unexpected', '0'),
            ('Bandana_Blue', 'crafted', '1'),
            ('Iceaxe', 'crafted', '1'),
        )
        for name, flag, value in cases:
            with self.subTest(name=name, flag=flag):
                files = self.generate()
                types = ET.fromstring(files['ce/types.xml'])
                types.find("type[@name='%s']/flags" % name).set(flag, value)
                files['ce/types.xml'] = ET.tostring(types)
                self.refuse_install(files, 'FLOOR_FLAGS_DRIFT|NEW_TYPE_DRIFT|retain')
                shutil.rmtree(Path(self.tmp.name) / 'delta')
        files = self.generate()
        types = ET.fromstring(files['ce/types.xml'])
        types.find("type[@name='DrysackBag_Green']/cost").text = '999'
        files['ce/types.xml'] = ET.tostring(types)
        self.refuse_install(files, 'retain')

    def test_route_audit_uses_emitted_flags_without_class_name_exceptions(self):
        from tools.audit import loot_routes
        # Explicit synthetic mission containing only the generated rows, to avoid
        # assuming CE precedence between stock and overlay definitions.
        mission = Path(self.tmp.name) / 'audit'
        (mission / 'db').mkdir(parents=True)
        types_path = mission / 'db/types.xml'
        files = self.generate()
        types_path.write_bytes(files['ce/types.xml'])
        names = ['DrysackBag_Green', 'TortillaBag_Desert']
        rows = loot_routes.report_rows(mission, essentials=names)
        self.assertEqual([(r[0], r[1]) for r in rows], [('TortillaBag_Desert', 1)])
        types = ET.fromstring(files['ce/types.xml'])
        types.find("type[@name='DrysackBag_Green']/flags").set('crafted', '1')
        types.find("type[@name='TortillaBag_Desert']/flags").set('deloot', '1')
        types_path.write_bytes(ET.tostring(types))
        rows = loot_routes.report_rows(mission, essentials=names)
        self.assertEqual([(r[0], r[1]) for r in rows], [(name, 0) for name in names])

    def test_other_profile_retains_legacy_rows_without_reading_supply_ledger(self):
        with mock.patch.object(dm, 'SUPPLY_DATA', Path(self.tmp.name) / 'absent-ledger.json'):
            files = economy.generate(self.root, profile())
            report = json.loads(files['economy-report.json'])
            self.assertNotIn('supply', report)
            self.assertEqual(report['datamined']['classes'], sorted(
                r['class'] for r in self.rows if r['stock'] == 'present'))
            self.assertEqual(json.loads(files['delta-manifest.json'])['supply_new_type_classes'], [])
            economy.install_delta(self.stage(files), self.root)
            economy.rollback(self.root)
        self.assertEqual(self.before, tree(self.root))

    def test_install_checks_only_named_new_type_not_unrelated_proposals(self):
        stage = self.stage(self.generate())
        # SYNTHETIC unrelated proposal has no ledger decision; it must not affect named bandana checks.
        rows = copy.deepcopy(self.rows)
        rows.append(dict(rows[0], **{'class': 'SyntheticUnrelatedProposal'}))
        with mock.patch.object(dm, 'load_rows', return_value=rows):
            economy.install_delta(stage, self.root)
            economy.rollback(self.root)
        self.assertEqual(self.before, tree(self.root))

    def test_install_refuses_rehashed_report_with_wrong_or_missing_ledger_digest(self):
        for digest in ('0' * 64, None, 'missing digest', 'missing supply'):
            with self.subTest(digest=digest):
                files = self.generate()
                report = json.loads(files['economy-report.json'])
                if digest == 'missing digest':
                    report['supply'].pop('dispositions_sha256')
                elif digest == 'missing supply':
                    report.pop('supply')
                else:
                    report['supply']['dispositions_sha256'] = digest
                files['economy-report.json'] = economy.encode(report)
                self.refuse_install(files, 'HC22_DISPOSITIONS_HASH_MISMATCH')
                shutil.rmtree(Path(self.tmp.name) / 'delta')

    def test_install_refuses_changed_ledger_even_when_decisions_are_unchanged(self):
        files = self.generate()
        ledger = Path(self.tmp.name) / 'ledger.json'
        ledger.write_bytes(dm.SUPPLY_DATA.read_bytes() + b'\n')
        with mock.patch.object(dm, 'SUPPLY_DATA', ledger):
            self.refuse_install(files, 'HC22_DISPOSITIONS_HASH_MISMATCH')

    def test_missing_ledger_refuses_generate_and_install_with_named_error(self):
        files = self.generate()
        with mock.patch.object(dm, 'SUPPLY_DATA', Path(self.tmp.name) / 'absent-ledger.json'):
            for enabled in (True, False):
                with self.subTest(enabled=enabled), self.assertRaisesRegex(ValueError, 'HC22_DISPOSITIONS_MISSING'):
                    self.generate(include_datamined=enabled)
            self.refuse_install(files, 'HC22_DISPOSITIONS_MISSING')


class EconomyIntegration(Base):
    """economy.generate emits the rows; economy.install accepts exactly their mutable fields."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'source'
        self.root.mkdir()
        self.rows = self.__class__.rows
        stock_mission(self.root, self.rows)
        self.present = sorted(r['class'] for r in self.rows if r['stock'] == 'present')

    def delta_types(self, delta):
        return {t.get('name'): t for t in ET.fromstring(delta['ce/types.xml'])}

    def stage(self, **kw):
        stage = Path(tempfile.mkdtemp(dir=self.tmp.name)) / 'delta'
        economy.write_delta(stage, economy.generate(self.root, profile(), **kw))
        return stage

    def private_copy(self):
        target = Path(tempfile.mkdtemp(dir=self.tmp.name)) / 'copy'
        shutil.copytree(self.root, target)
        return target

    def test_generate_emits_every_stock_present_row_beside_the_profile_usage_rows(self):
        delta = economy.generate(self.root, profile())
        out = self.delta_types(delta)
        self.assertEqual(sorted(out), sorted(self.present + ['SynthTool']))
        jacket = out['LeatherJacket_Natural']
        r = self.by_name['LeatherJacket_Natural']
        self.assertEqual((jacket.findtext('nominal'), jacket.findtext('min')), (str(r['nominal']), str(r['min'])))
        self.assertEqual([u.get('name') for u in jacket.findall('usage')], sorted(r['usage']))
        self.assertIn(b'folder="hollow-country/ce"', delta['cfgeconomycore.append.xml'])
        report = json.loads(delta['economy-report.json'])
        self.assertEqual(report['datamined']['enabled'], True)
        self.assertEqual(report['datamined']['classes'], self.present)
        self.assertEqual(report['datamined']['stock_absent_not_emitted'],
                         sorted(r['class'] for r in self.rows if r['stock'] == 'absent'))
        manifest = json.loads(delta['delta-manifest.json'])
        self.assertEqual(manifest['datamined_classes'], self.present)
        self.assertEqual(manifest['runtime_acceptance'], 'pending')

    def test_every_row_still_carries_pending_local_in_the_json_and_the_report(self):
        doc = json.loads(dm.DATA.read_bytes())
        self.assertEqual({r['acceptance'] for r in doc['rows']}, {'pending-local'})
        report = json.loads(economy.generate(self.root, profile())['economy-report.json'])
        self.assertEqual(report['datamined']['acceptance'], 'pending-local')
        self.assertEqual({r['acceptance'] for r in report['datamined']['rows']}, {'pending-local'})
        self.assertEqual(len(report['datamined']['rows']), len(self.present))

    def test_the_switch_leaves_the_rows_out(self):
        delta = economy.generate(self.root, profile(), include_datamined=False)
        self.assertEqual(sorted(self.delta_types(delta)), ['SynthTool'])
        report = json.loads(delta['economy-report.json'])
        self.assertEqual(report['datamined'], {'enabled': False, 'classes': []})
        self.assertEqual(json.loads(delta['delta-manifest.json'])['datamined_classes'], [])

    def test_switch_with_an_empty_profile_emits_no_registration(self):
        delta = economy.generate(self.root, profile(**{}) | {'add_usage': {}}, include_datamined=False)
        self.assertEqual(self.delta_types(delta), {})
        self.assertNotIn(b'<ce', delta['cfgeconomycore.append.xml'])

    def test_cli_no_datamined_switch_reaches_the_delta(self):
        profile_path = Path(self.tmp.name) / 'profile.json'
        profile_path.write_text(json.dumps(profile()))
        for flag, expect in (([], self.present + ['SynthTool']), (['--no-datamined'], ['SynthTool'])):
            out = Path(self.tmp.name) / ('cli' + str(len(flag)))
            with mock.patch('sys.argv', ['economy', 'generate', '--source', str(self.root), '--profile',
                                         str(profile_path), '--out', str(out)] + flag), \
                    contextlib.redirect_stdout(io.StringIO()):
                economy.main()
            self.assertEqual(sorted(t.get('name') for t in ET.parse(out / 'ce/types.xml').getroot()),
                             sorted(expect))

    def test_a_class_the_profile_also_changes_is_refused_case_insensitively(self):
        for spelling in ('LeatherJacket_Natural', 'leatherjacket_natural'):
            root = Path(self.tmp.name) / ('dup-' + spelling)
            root.mkdir()
            stock_mission(root, self.rows)
            types = ET.parse(root / 'db/types.xml').getroot()
            node = types.find("type[@name='LeatherJacket_Natural']")
            node.set('name', spelling)
            ET.SubElement(node, 'usage', {'name': 'Village'})  # a stock usage the profile could extend
            (root / 'db/types.xml').write_bytes(ET.tostring(types))
            with self.subTest(spelling):
                with self.assertRaisesRegex(ValueError, 'datamined.*profile add_usage'):
                    economy.generate(root, profile(**{spelling: ['Town']}))
                # the switch removes the overlap: the profile alone is valid
                out = self.delta_types(economy.generate(root, profile(**{spelling: ['Town']}),
                                                        include_datamined=False))
                self.assertEqual(sorted(out), [spelling])

    def test_install_accepts_the_rows_and_rollback_is_byte_exact(self):
        stage = self.stage()
        target = self.private_copy()
        before = tree(target)
        receipt = economy.install_delta(stage, target)
        core = (target / 'cfgeconomycore.xml').read_bytes()
        self.assertIn(b'<!--keep exactly-->', core)
        self.assertIn(b'folder="hollow-country/ce"', core)
        self.assertEqual((target / 'db/types.xml').read_bytes(), before['db/types.xml'])
        installed = {t.get('name') for t in ET.parse(target / 'hollow-country/ce/types.xml').getroot()}
        self.assertEqual(installed, set(self.present) | {'SynthTool'})
        self.assertEqual(receipt['types_sha256'], economy.sha((target / 'hollow-country/ce/types.xml').read_bytes()))
        economy.rollback(target)
        self.assertEqual(tree(target), before)

    def test_default_install_still_refuses_the_budget_changes(self):
        stage = self.stage()
        target = self.private_copy()
        with self.assertRaises(ValueError):
            economy.install(stage, target)
        self.assertFalse((target / 'hollow-country').exists())

    def test_cli_install_and_rollback_round_trip(self):
        stage = self.stage()
        target = self.private_copy()
        before = tree(target)
        for argv in (['install', '--delta', str(stage), '--target', str(target)],
                     ['rollback', '--target', str(target)]):
            with mock.patch('sys.argv', ['economy'] + argv), contextlib.redirect_stdout(io.StringIO()):
                economy.main()
        self.assertEqual(tree(target), before)

    def tamper(self, stage, mutate):
        """Rewrite the staged types and keep the manifest checksum honest so only install's rules refuse."""
        path = stage / 'ce/types.xml'
        root = ET.fromstring(path.read_bytes())
        mutate({t.get('name'): t for t in root})
        data = ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'
        path.write_bytes(data)
        manifest = json.loads((stage / 'delta-manifest.json').read_bytes())
        manifest['files']['ce/types.xml'] = economy.sha(data)
        (stage / 'delta-manifest.json').write_bytes(economy.encode(manifest))

    def refused_and_untouched(self, stage, mutate, message):
        target = self.private_copy()
        before = tree(target)
        self.tamper(stage, mutate)
        with self.assertRaisesRegex(ValueError, message):
            economy.install_delta(stage, target)
        self.assertEqual(tree(target), before)

    def test_filtering_bottle_is_the_only_category_exception(self):
        stage = self.stage()
        self.assertIsNone(stock_for(self.rows)['FilteringBottle'].find('category'))
        self.assertEqual(economy.CATEGORY_ADDED, {'FilteringBottle': 'tools'})
        out = self.delta_types(economy.generate(self.root, profile()))
        self.assertEqual(out['FilteringBottle'].find('category').get('name'), 'tools')
        target = self.private_copy()
        economy.install_delta(stage, target)  # accepted
        economy.rollback(target)

    def test_a_category_change_on_any_other_row_is_refused(self):
        def change(types):
            types['LeatherJacket_Natural'].find('category').set('name', 'tools')
        self.refused_and_untouched(self.stage(), change, 'category|retain')

    def test_a_category_added_to_a_row_that_stock_lacks_it_on_is_refused_unless_filtering_bottle(self):
        def add(types):
            ET.SubElement(types['Iceaxe'], 'category', {'name': 'tools'})
        self.refused_and_untouched(self.stage(), add, 'category|retain')

    def test_filtering_bottle_may_not_change_to_a_second_or_different_category_shape(self):
        def two(types):
            ET.SubElement(types['FilteringBottle'], 'category', {'name': 'clothes'})
        self.refused_and_untouched(self.stage(), two, 'category')

    def test_flags_cost_and_quantities_stay_stock_identical(self):
        for tag, value in (('cost', '999'), ('quantmin', '5'), ('quantmax', '7')):
            def change(types, tag=tag, value=value):
                types['LeatherJacket_Natural'].find(tag).text = value
            with self.subTest(tag):
                self.refused_and_untouched(self.stage(), change, 'retain')

        def flags(types):
            types['LeatherJacket_Natural'].find('flags').set('count_in_cargo', '1')
        self.refused_and_untouched(self.stage(), flags, 'retain')

    def test_a_nested_field_inside_a_retained_tag_cannot_hide_a_change(self):
        def nested(types):
            ET.SubElement(types['LeatherJacket_Natural'].find('flags'), 'nominal').text = '999'
        self.refused_and_untouched(self.stage(), nested, 'retain')

    def test_filtering_bottle_category_must_be_its_declared_tools(self):
        for bad in ('INVALID_CATEGORY', 'clothes'):
            def change(types, bad=bad):
                types['FilteringBottle'].find('category').set('name', bad)
            with self.subTest(bad):
                self.refused_and_untouched(self.stage(), change, 'category')

    def test_a_class_outside_the_shipped_rows_does_not_get_the_widened_fields(self):
        def widen(types):
            types['SynthTool'].find('nominal').text = '99'
        self.refused_and_untouched(self.stage(), widen, 'retain')

    def test_a_manifest_naming_an_unshipped_class_cannot_widen_the_install(self):
        stage = self.stage()
        manifest = json.loads((stage / 'delta-manifest.json').read_bytes())
        manifest['datamined_classes'].append('SynthTool')
        (stage / 'delta-manifest.json').write_bytes(economy.encode(manifest))
        target = self.private_copy()
        with self.assertRaisesRegex(ValueError, 'datamined'):
            economy.install_delta(stage, target)
        self.assertFalse((target / 'hollow-country').exists())

    def test_install_refuses_widened_row_flags_even_for_a_listed_class(self):
        def crafted(types):
            types['DrysackBag_Green'].find('flags').set('crafted', '0')
        self.refused_and_untouched(self.stage(), crafted, 'retain')

    def test_hardlink_and_outside_path_safety_still_apply_to_the_datamined_install(self):
        stage = self.stage()
        target = self.private_copy()
        economy.install_delta(stage, target)
        outside = Path(self.tmp.name) / 'operator-file.txt'
        outside.write_bytes(b'operator data\n')
        managed = target / economy.MANAGED
        os.link(outside, managed / 'core.next')
        with self.assertRaises(ValueError):
            economy.rollback(target)
        self.assertEqual(outside.read_bytes(), b'operator data\n')
        os.unlink(managed / 'core.next')
        os.link(managed / 'core.backup', Path(self.tmp.name) / 'second-name')
        with self.assertRaises(ValueError):
            economy.rollback(target)
        self.assertTrue(managed.is_dir())

    def test_rows_do_not_collide_with_the_firearms_roster_or_the_snafu_allowlist(self):
        rows = {r['class'].lower() for r in self.rows}
        roster = json.loads((Path(dm.__file__).with_name('firearms_roster.json')).read_bytes())
        taken = {e['class'].lower() for e in roster['entries']} | {d['class'].lower() for d in roster['deferred_datamined']}
        allow = json.loads(Path(dm.__file__).with_name('snafu_allowlist.json').read_bytes())
        names = set()

        def walk(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k in {'class', 'classname', 'name'} and isinstance(v, str):
                        names.add(v.lower())
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
            elif isinstance(node, str):
                names.add(node.lower())
        walk(allow)
        self.assertFalse(rows & taken)
        self.assertFalse(rows & names)


def weapon_type(name, nominal, minimum, usage, value, category='weapons', extra=''):
    return ET.fromstring(
        f'<type name="{name}"><nominal>{nominal}</nominal><lifetime>14400</lifetime><restock>0</restock>'
        f'<min>{minimum}</min><quantmin>-1</quantmin><quantmax>-1</quantmax><cost>100</cost>'
        '<flags count_in_cargo="0" count_in_hoarder="0" count_in_map="1" count_in_player="0" '
        f'crafted="0" deloot="0"/><category name="{category}"/>{extra}'
        + ''.join(f'<usage name="{u}"/>' for u in usage) + ''.join(f'<value name="{v}"/>' for v in value)
        + '</type>')


def roster_doc():
    def e(name, kind, role, nominal, minimum, **kw):
        base = {'class': name, 'kind': kind, 'role': role, 'tier': 'common',
                'set': {'nominal': nominal, 'min': minimum}, 'justification': 'synthetic'}
        base.update(kw)
        return base
    return {'schema': 1, 'name': 'synthetic-roster', 'players': '3-6', 'deferred_datamined': [],
            'entries': [
                e('SynthWoodRifle', 'weapon', 'wood', 12, 9, add_usage=['Village'], ammo=['SynthAmmo'], magazines=[]),
                e('SynthAmmo', 'ammo', 'support', 30, 20),
                e('SynthZeroRifle', 'weapon', 'wood', 5, 3, ammo=['SynthAmmo'], magazines=['SynthZeroMag'],
                  datamined=True, acceptance='pending-local'),
                e('SynthZeroMag', 'magazine', 'support', 2, 1, datamined=True, acceptance='pending-local')]}


def combined_mission(root, rows):
    """Datamined stock rows + one profile type + the synthetic roster's stock types."""
    stock_mission(root, rows)
    types = ET.parse(root / 'db/types.xml').getroot()
    types.extend([weapon_type('SynthWoodRifle', 40, 30, ['Town'], ['Tier2']),
                  weapon_type('SynthAmmo', 100, 70, ['Town'], [], extra='<tag name="shelves"/>'),
                  weapon_type('SynthZeroRifle', 0, 0, ['Hunting'], []),
                  weapon_type('SynthZeroMag', 0, 0, ['Hunting'], [])])
    (root / 'db/types.xml').write_bytes(ET.tostring(types))


class CombinedDelta(Base):
    """Profile + firearms roster + datamined items are ONE delta, installed and rolled back once."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        from tools.package import firearms
        shipped = Path(self.tmp.name) / 'SYNTHETIC-shipped-roster.json'
        shipped.write_bytes(economy.encode(roster_doc()))
        patcher = mock.patch.object(firearms, 'ROSTER_PATH', shipped)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.root = Path(self.tmp.name) / 'source'
        self.root.mkdir()
        self.rows = self.__class__.rows
        combined_mission(self.root, self.rows)
        self.present = sorted(r['class'] for r in self.rows if r['stock'] == 'present')
        self.roster_all = ['SynthAmmo', 'SynthWoodRifle', 'SynthZeroMag', 'SynthZeroRifle']

    def delta(self, **kw):
        return economy.generate(self.root, profile(), roster=roster_doc(), **kw)

    def names(self, delta):
        return sorted(t.get('name') for t in ET.fromstring(delta['ce/types.xml']))

    def stage(self, **kw):
        stage = Path(tempfile.mkdtemp(dir=self.tmp.name)) / 'delta'
        economy.write_delta(stage, self.delta(**kw))
        return stage

    def private_copy(self):
        target = Path(tempfile.mkdtemp(dir=self.tmp.name)) / 'copy'
        shutil.copytree(self.root, target)
        return target

    def tamper(self, stage, mutate):
        path = stage / 'ce/types.xml'
        root = ET.fromstring(path.read_bytes())
        mutate({t.get('name'): t for t in root})
        data = ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'
        path.write_bytes(data)
        manifest = json.loads((stage / 'delta-manifest.json').read_bytes())
        manifest['files']['ce/types.xml'] = economy.sha(data)
        (stage / 'delta-manifest.json').write_bytes(economy.encode(manifest))

    def refused(self, mutate, message='retain|category|plain value'):
        stage = self.stage()
        target = self.private_copy()
        before = tree(target)
        self.tamper(stage, mutate)
        with self.assertRaisesRegex(ValueError, message):
            economy.install_delta(stage, target)
        self.assertEqual(tree(target), before)
        self.assertFalse((target / 'hollow-country').exists())

    def test_one_delta_carries_the_profile_the_roster_and_the_items(self):
        delta = self.delta()
        self.assertEqual(self.names(delta), sorted(self.present + self.roster_all + ['SynthTool']))
        manifest = json.loads(delta['delta-manifest.json'])
        self.assertEqual(manifest['firearms_classes'], self.roster_all)
        self.assertEqual(manifest['datamined_classes'], self.present)
        report = json.loads(delta['economy-report.json'])
        self.assertEqual(report['firearms']['datamined']['classes'], ['SynthZeroMag', 'SynthZeroRifle'])
        self.assertEqual({e['acceptance'] for e in report['firearms']['entries'] if 'acceptance' in e},
                         {'pending-local'})
        self.assertEqual(delta['delta-manifest.json'], self.delta()['delta-manifest.json'])

    def test_both_deltas_install_together_once_and_roll_back_byte_exact(self):
        stage = self.stage()
        target = self.private_copy()
        before = tree(target)
        economy.install_delta(stage, target)
        installed = {t.get('name') for t in ET.parse(target / 'hollow-country/ce/types.xml').getroot()}
        self.assertEqual(installed, set(self.present) | set(self.roster_all) | {'SynthTool'})
        self.assertEqual((target / 'cfgeconomycore.xml').read_bytes().count(b'folder="hollow-country/ce"'), 1)
        with self.assertRaises(ValueError):
            economy.install_delta(stage, target)
        economy.rollback(target)
        self.assertEqual(tree(target), before)

    def test_the_switches_remove_only_their_own_rows(self):
        no_items = self.names(self.delta(include_datamined=False))
        self.assertEqual(no_items, sorted(self.roster_all + ['SynthTool']))
        no_weapons = self.names(self.delta(include_roster_datamined=False))
        self.assertEqual(no_weapons, sorted(self.present + ['SynthAmmo', 'SynthWoodRifle', 'SynthTool']))
        manifest = json.loads(self.delta(include_roster_datamined=False)['delta-manifest.json'])
        self.assertEqual(manifest['firearms_classes'], ['SynthAmmo', 'SynthWoodRifle'])

    def test_class_collisions_across_all_three_sources_are_refused_case_insensitively(self):
        def entry(name):
            return {'class': name, 'kind': 'ammo', 'role': 'support', 'tier': 'common',
                    'set': {'nominal': 5, 'min': 2}, 'add_usage': ['Town'], 'justification': 'synthetic'}
        for label, spelling, profile_class, roster_extra, regex in (
                ('profile-roster', 'SynthWoodRifle', 'SynthWoodRifle', None, 'roster.*profile add_usage'),
                ('profile-items', 'LeatherJacket_Natural', 'LeatherJacket_Natural', None,
                 'datamined.*profile add_usage'),
                ('roster-items', 'LeatherJacket_Natural', None, 'LeatherJacket_Natural', 'roster.*datamined'),
                ('profile-roster-lower', 'SynthWoodRifle', 'synthwoodrifle', None, 'roster.*profile add_usage'),
                ('roster-items-lower', 'leatherjacket_natural', None, 'leatherjacket_natural',
                 'roster.*datamined')):
            root = Path(self.tmp.name) / ('c-' + label)
            root.mkdir()
            combined_mission(root, self.rows)
            types = ET.parse(root / 'db/types.xml').getroot()
            if profile_class == 'LeatherJacket_Natural':
                ET.SubElement(types.find("type[@name='LeatherJacket_Natural']"), 'usage', {'name': 'Village'})
            if profile_class == 'synthwoodrifle':
                types.find("type[@name='SynthWoodRifle']").set('name', 'synthwoodrifle')
            if roster_extra:
                types.find("type[@name='LeatherJacket_Natural']").set('name', roster_extra)
            (root / 'db/types.xml').write_bytes(ET.tostring(types))
            doc = roster_doc()
            if profile_class == 'synthwoodrifle':
                doc['entries'][0]['class'] = 'SynthWoodRifle'  # roster spelling differs from the profile's
            if roster_extra:
                doc['entries'].append(entry(roster_extra))
            prof = profile(**{profile_class: ['Village']}) if profile_class else profile()
            with self.subTest(label), self.assertRaisesRegex(ValueError, regex):
                economy.generate(root, prof, roster=doc)

    def test_permissions_stay_per_class(self):
        def set_text(name, tag, text):
            def mutate(types):
                types[name].find(tag).text = text
            return mutate
        # accepted: each source changes only its own allowed fields (round trip proves it)
        stage = self.stage()
        target = self.private_copy()
        economy.install_delta(stage, target)
        economy.rollback(target)
        # refused: profile rows stay usage-only
        self.refused(set_text('SynthTool', 'nominal', '99'))
        # refused: flags/cost/quantities stay stock on roster and datamined rows
        self.refused(set_text('SynthWoodRifle', 'cost', '5'))
        self.refused(set_text('LeatherJacket_Natural', 'quantmax', '9'))

        def flags(types):
            types['SynthWoodRifle'].find('flags').set('count_in_cargo', '1')
        self.refused(flags)

        # refused: a roster row may not change a category (only the named datamined exception may add one)
        def category(types):
            types['SynthWoodRifle'].find('category').set('name', 'tools')
        self.refused(category)

        def add_category(types):
            ET.SubElement(types['SynthZeroMag'], 'category', {'name': 'tools'})
        self.refused(add_category)

    def test_a_manifest_cannot_make_one_source_borrow_anothers_permissions(self):
        stage = self.stage()
        manifest = json.loads((stage / 'delta-manifest.json').read_bytes())
        manifest['firearms_classes'].append('LeatherJacket_Natural')  # overlaps the datamined list
        (stage / 'delta-manifest.json').write_bytes(economy.encode(manifest))
        target = self.private_copy()
        with self.assertRaisesRegex(ValueError, 'firearms'):
            economy.install_delta(stage, target)
        self.assertFalse((target / 'hollow-country').exists())

    def test_nested_fields_inside_a_retained_tag_cannot_hide_a_change(self):
        def nested(name):
            def mutate(types):
                ET.SubElement(types[name].find('flags'), 'nominal').text = '999'
            return mutate
        self.refused(nested('LeatherJacket_Natural'))
        self.refused(nested('SynthWoodRifle'))

        def numeric_child(types):
            ET.SubElement(types['LeatherJacket_Natural'].find('nominal'), 'cost').text = '1'
        self.refused(numeric_child)

        def category_child(types):
            ET.SubElement(types['SynthWoodRifle'].find('category'), 'nominal').text = '1'
        self.refused(category_child)

    def test_filtering_bottle_category_must_be_its_declared_tools(self):
        def bad(types):
            types['FilteringBottle'].find('category').set('name', 'INVALID_CATEGORY')
        self.refused(bad, 'category')

        def other_valid_name(types):
            types['FilteringBottle'].find('category').set('name', 'clothes')
        self.refused(other_valid_name, 'category')
        stage = self.stage()
        target = self.private_copy()
        economy.install_delta(stage, target)  # the declared tools category installs
        economy.rollback(target)

    def test_cli_composes_installs_and_rolls_back_once(self):
        profile_path = Path(self.tmp.name) / 'profile.json'
        profile_path.write_text(json.dumps(profile()))
        roster_path = Path(self.tmp.name) / 'roster.json'
        roster_path.write_text(json.dumps(roster_doc()))
        out = Path(self.tmp.name) / 'cli-delta'
        target = self.private_copy()
        before = tree(target)
        runs = [['generate', '--source', str(self.root), '--profile', str(profile_path),
                 '--roster', str(roster_path), '--out', str(out)],
                ['install', '--delta', str(out), '--target', str(target)],
                ['rollback', '--target', str(target)]]
        for argv in runs:
            with mock.patch('sys.argv', ['economy'] + argv), contextlib.redirect_stdout(io.StringIO()):
                economy.main()
            if argv[0] == 'install':
                installed = {t.get('name') for t in ET.parse(target / 'hollow-country/ce/types.xml').getroot()}
                self.assertEqual(installed, set(self.present) | set(self.roster_all) | {'SynthTool'})
        self.assertEqual(tree(target), before)
        out2 = Path(self.tmp.name) / 'cli-delta2'
        argv = ['generate', '--source', str(self.root), '--profile', str(profile_path),
                '--roster', str(roster_path), '--no-datamined', '--no-roster-datamined', '--out', str(out2)]
        with mock.patch('sys.argv', ['economy'] + argv), contextlib.redirect_stdout(io.StringIO()):
            economy.main()
        self.assertEqual(sorted(t.get('name') for t in ET.parse(out2 / 'ce/types.xml').getroot()),
                         ['SynthAmmo', 'SynthTool', 'SynthWoodRifle'])

    def test_the_firearms_cli_delegates_to_the_combined_path_and_the_single_installer(self):
        from tools.package import firearms
        roster_path = Path(self.tmp.name) / 'roster.json'
        roster_path.write_text(json.dumps(roster_doc()))
        out = Path(self.tmp.name) / 'fa-delta'
        target = self.private_copy()
        before = tree(target)
        runs = [['generate', '--source', str(self.root), '--roster', str(roster_path), '--with-items',
                 '--out', str(out)],
                ['install', '--delta', str(out), '--target', str(target)],
                ['rollback', '--target', str(target)]]
        for argv in runs:
            with contextlib.redirect_stdout(io.StringIO()):
                firearms.main(argv)
            if argv[0] == 'install':
                installed = {t.get('name') for t in ET.parse(target / 'hollow-country/ce/types.xml').getroot()}
                self.assertEqual(installed, set(self.present) | set(self.roster_all))
        self.assertEqual(tree(target), before)
        self.assertIs(firearms.rollback, economy.rollback)


if __name__ == '__main__':
    unittest.main()
