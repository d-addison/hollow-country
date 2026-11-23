"""Infected role kits, visible worn gear and HC child parity (#339); offline data checks only.

Synthetic missions exercise the generator and the receipt path. The stock-file tests read the pinned
stock mission when the host has it and skip otherwise. Nothing here establishes CE or DayZ behaviour.
"""
import contextlib
import copy
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from tools.package import economy, infected_variety as iv

ROOT = Path(__file__).resolve().parents[2]
POLICY = json.loads(iv.POLICY.read_text())
STOCK = Path.home() / '.cache/hollow-country/wine-server-20261116/mpmissions/dayzOffline.chernarusplus'

PRESETS = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<randompresets>
\t\t<cargo chance="0.10" name="foodArmy">
\t\t\t\t<item name="TunaCan" chance="0.10" />
\t\t</cargo>
</randompresets>'''
SPAWNABLE = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<spawnabletypes>
\t<type name="ZmbM_PatrolNormal_Autumn">
\t\t<cargo preset="foodArmy" />
\t\t<attachments preset="foodArmy" />
\t</type>
\t<type name="ZmbM_usSoldier_normal_Desert">
\t\t<cargo preset="foodArmy" />
\t</type>
\t<type name="ZmbM_PolicemanFat">
\t\t<cargo preset="toolsPolice" />
\t\t<cargo chance="0.10">
\t\t\t<item name="Mag_SSG82_5rnd" chance="1.0" />
\t\t</cargo>
\t</type>
\t<type name="ZmbF_NurseFat">
\t\t<cargo preset="toolsMedic" />
\t</type>
\t<type name="ZmbM_HunterOld_Autumn">
\t\t<attachments preset="foodArmy" />
\t</type>
\t<type name="ZmbF_Clerk_Normal_Blue">
\t\t<cargo preset="foodCity" />
\t</type>
\t<type name="ZmbF_PatientOld">
\t</type>
\t<type name="Other">
\t\t<cargo preset="foodCity" />
\t</type>
</spawnabletypes>'''
CLASSES = {
    'HC_ZmbF_Crawler_ZmbF_NurseFat': 'ZmbF_NurseFat',
    'HC_ZmbM_Riser_ZmbM_PolicemanFat': 'ZmbM_PolicemanFat',
    'HC_ZmbM_Crawler_ZmbM_usSoldier_normal_Woodland': 'ZmbM_usSoldier_normal_Woodland',
    'HC_ZmbF_Sitter_ZmbF_Clerk_Normal_Blue': 'ZmbF_Clerk_Normal_Blue',
    'HC_ZmbF_Crawler_ZmbF_PatientOld': 'ZmbF_PatientOld',
}


def synthetic_policy():
    policy = copy.deepcopy(POLICY)
    policy['substitutions'] = []
    policy['palette_rebalance'] = {'transfers': []}
    policy['mix_policy']['EnableComposition'] = False
    policy['ce_pose_coverage'] = {}
    acc = policy['accessories']
    acc.update(probability_transfers=[], item_transfers={}, explicit_classes=dict(CLASSES),
               stock_presets_sha256=economy.sha(PRESETS))
    acc['parent_fallbacks'] = {'ZmbM_usSoldier_normal_Woodland': 'ZmbM_usSoldier_normal_Desert'}
    policy['infected_kits']['worn_gear'] = {'slot_transfers': [], 'item_transfers': {}}
    return policy


def rows(data):
    return {n.get('name'): n for n in ET.fromstring(data).findall('type')}


def body(node):
    return tuple(iv._signature(c) for c in node)


def kit_presets(node):
    return [c.get('preset') for c in node.findall('cargo') if (c.get('preset') or '').startswith('hc_kit_')]


class SyntheticKitTests(unittest.TestCase):
    def setUp(self):
        self.policy = synthetic_policy()
        self.kits = iv._kits(self.policy)
        self.built = iv.build(SPAWNABLE, PRESETS, self.policy['accessories'], self.kits)
        self.rows = rows(self.built['spawn'])

    def test_hc_child_copies_parent_cargo_and_attachments(self):
        self.assertEqual(body(self.rows['HC_ZmbF_Crawler_ZmbF_NurseFat']), body(self.rows['ZmbF_NurseFat']))
        self.assertEqual(self.rows['HC_ZmbF_Crawler_ZmbF_NurseFat'].find('cargo').get('preset'), 'toolsMedic')
        self.assertEqual(body(self.rows['HC_ZmbF_Sitter_ZmbF_Clerk_Normal_Blue']), body(self.rows['ZmbF_Clerk_Normal_Blue']))

    def test_parent_without_row_uses_the_family_sibling(self):
        child = self.rows['HC_ZmbM_Crawler_ZmbM_usSoldier_normal_Woodland']
        self.assertEqual(body(child), body(self.rows['ZmbM_usSoldier_normal_Desert']))
        self.assertEqual(kit_presets(child), ['hc_kit_soldier_ammo', 'hc_kit_soldier_aid'])

    def test_no_parent_row_and_no_sibling_is_refused(self):
        overlay = copy.deepcopy(self.policy['accessories'])
        overlay['parent_fallbacks'] = {}
        with self.assertRaisesRegex(ValueError, 'no parent row'):
            iv.build(SPAWNABLE, PRESETS, overlay, self.kits)

    def test_empty_parent_gives_an_empty_child_and_nothing_else_is_empty(self):
        self.assertEqual(len(self.rows['ZmbF_PatientOld']), 0)
        self.assertEqual(len(self.rows['HC_ZmbF_Crawler_ZmbF_PatientOld']), 0)
        for name, node in self.rows.items():
            if name.startswith('HC_') and name != 'HC_ZmbF_Crawler_ZmbF_PatientOld':
                self.assertTrue(len(node), name)

    def test_report_counts_parity_and_kits(self):
        report = self.built['report']
        self.assertEqual((report['hc_total'], report['hc_parity'], report['hc_missing']), (5, 5, 0))
        # Patrol, Desert soldier, police, nurse and hunter, plus the HC nurse, police and Woodland children
        self.assertEqual(report['kit_rows'], 8)
        self.assertEqual(report['kit_presets'], 8)
        self.assertEqual(iv.plan_lines(report, {}, self.kits)[1], 'hc_children parity=5/5 missing=0')
        self.assertRegex(iv.plan_lines(report, {}, self.kits)[0],
                         r'^infected kits rows=8 presets=8 expected_extra_items~0$')

    def test_roles_follow_the_class_name_family(self):
        expected = {'ZmbM_PatrolNormal_Autumn': 'soldier', 'ZmbF_usSoldier_normal_Desert': 'soldier',
                    'ZmbM_takiSoldier_Officer': 'soldier', 'ZmbM_PolicemanSpecForce': 'police',
                    'ZmbF_takiPoliceWoman_Heavy': 'police', 'ZmbM_HunterOld_Winter': 'hunter',
                    'ZmbF_DoctorSkinny': 'medic', 'ZmbF_NurseFat': 'medic', 'ZmbM_ParamedicNormal_Red': 'medic',
                    'ZmbF_Clerk_Normal_Blue': None, 'ZmbM_PatientSkinny': None, 'ZmbM_FirefighterNormal': None,
                    'ZmbM_Mummy': None, 'ZmbM_NBC_Grey': None, 'ZmbM_HermitSkinny_Beige': None}
        for name, role in expected.items():
            self.assertEqual(iv._role(name, self.kits), role, name)

    def test_vanilla_rows_get_kits_after_their_cargo_and_civilians_stay_untouched(self):
        patrol = self.rows['ZmbM_PatrolNormal_Autumn']
        self.assertEqual([c.tag for c in patrol], ['cargo', 'cargo', 'cargo', 'attachments'])
        self.assertEqual(kit_presets(patrol), ['hc_kit_soldier_ammo', 'hc_kit_soldier_aid'])
        self.assertEqual(kit_presets(self.rows['ZmbM_HunterOld_Autumn']), ['hc_kit_hunter_ammo', 'hc_kit_hunter_knife'])
        stock = rows(SPAWNABLE)
        for name in ('ZmbF_Clerk_Normal_Blue', 'Other', 'ZmbF_PatientOld'):
            self.assertEqual(body(self.rows[name]), body(stock[name]), name)
        for name, node in self.rows.items():
            self.assertLessEqual(len(kit_presets(node)), 2, name)

    def test_preset_file_only_gains_the_used_kit_presets(self):
        presets = self.built['presets']
        end = PRESETS.rfind(b'</randompresets>')
        self.assertTrue(presets.startswith(PRESETS[:end]))
        self.assertTrue(presets.endswith(b'</randompresets>'))
        self.assertIn(iv.KIT_MARKER, presets)
        nodes = ET.fromstring(presets).findall('cargo')
        names = [n.get('name') for n in nodes]
        self.assertEqual(names[0], 'foodArmy')
        used = {p for r in self.kits['roles'].values() for p in r['presets']}
        self.assertEqual(sorted(names[1:]), sorted(used))
        for node in nodes[1:]:
            self.assertTrue(Decimal_ok(node.get('chance')), node.get('name'))

    def test_preset_block_keeps_crlf(self):
        crlf = PRESETS.replace(b'\n', b'\r\n')
        data, emitted = iv._kit_preset_bytes(crlf, self.kits, {'hc_kit_soldier_aid'})
        self.assertEqual(emitted, ['hc_kit_soldier_aid'])
        self.assertNotIn(b'\n', data.replace(b'\r\n', b''))

    def test_existing_kit_preset_name_is_refused(self):
        clash = PRESETS.replace(b'foodArmy', b'hc_kit_soldier_aid')
        with self.assertRaisesRegex(ValueError, 'already present'):
            iv._kit_preset_bytes(clash, self.kits, {'hc_kit_soldier_aid'})

    def test_second_build_over_built_rows_adds_no_second_kit(self):
        node = ET.fromstring(b'<type name="ZmbM_SoldierNormal"><cargo preset="hc_kit_soldier_ammo"/></type>')
        self.assertEqual(iv._add_kits(node, 'ZmbM_SoldierNormal', self.kits), [])
        self.assertEqual(kit_presets(node), ['hc_kit_soldier_ammo'])


def Decimal_ok(value):
    return iv.Decimal('0.10') <= iv.Decimal(value) <= iv.Decimal('0.25')


class KitPolicyTests(unittest.TestCase):
    def mutate(self, change):
        policy = copy.deepcopy(POLICY)
        change(policy['infected_kits'])
        return policy

    def test_authored_policy_is_valid_and_bounded(self):
        kits = iv._kits(POLICY)
        self.assertEqual(sorted(kits['roles']), ['hunter', 'medic', 'police', 'soldier'])
        self.assertEqual(len(kits['presets']), 8)
        for name, row in kits['presets'].items():
            self.assertTrue(name.startswith('hc_kit_'))
            self.assertTrue(Decimal_ok(row['chance']), name)
        for role in kits['roles'].values():
            self.assertLessEqual(len(role['presets']), 2)

    def test_refused_shapes(self):
        cases = {
            'chance too high': lambda k: k['presets']['hc_kit_soldier_aid'].update(chance='0.30'),
            'chance too low': lambda k: k['presets']['hc_kit_soldier_aid'].update(chance='0.05'),
            'unprefixed name': lambda k: k['presets'].update(plain=k['presets']['hc_kit_soldier_aid']),
            'unknown preset in role': lambda k: k['roles']['police'].update(presets=['hc_kit_missing']),
            'three presets': lambda k: k['roles']['soldier'].update(presets=list(k['presets'])[:3]),
            'empty items': lambda k: k['presets']['hc_kit_soldier_aid'].update(items=[]),
            'item chance zero': lambda k: k['presets']['hc_kit_soldier_aid']['items'][0].update(chance='0'),
            'no roles': lambda k: k.update(roles={}),
        }
        for label, change in cases.items():
            with self.subTest(label), self.assertRaises(ValueError):
                iv._kits(self.mutate(change))

    def test_kits_need_both_levers(self):
        self.assertTrue(iv.kits_enabled(POLICY))
        off = copy.deepcopy(POLICY)
        off['mix_policy']['EnableKits'] = False
        self.assertFalse(iv.kits_enabled(off))
        off = copy.deepcopy(POLICY)
        off['mix_policy']['EnableAccessories'] = False
        self.assertFalse(iv.kits_enabled(off))

    def test_every_hc_class_in_the_addon_config_has_a_parent_mapping(self):
        config = (ROOT / 'mods/HollowCountryAnims/config.cpp').read_text(encoding='utf-8')
        classes = dict(re.findall(r'class\s+(HC_Zmb\w+)\s*:\s*(\w+)', config))
        self.assertEqual(len(classes), 146)
        self.assertEqual(set(POLICY['accessories']['explicit_classes']), set(classes))
        for name, parent in classes.items():
            # The addon config and the vanilla class table differ in case for a few names.
            self.assertEqual(POLICY['accessories']['explicit_classes'][name].lower(), parent.lower(), name)


@unittest.skipUnless((STOCK / 'cfgspawnabletypes.xml').is_file(), 'pinned stock mission not on this host')
class StockMissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spawn = (STOCK / 'cfgspawnabletypes.xml').read_bytes()
        cls.presets = (STOCK / 'cfgrandompresets.xml').read_bytes()
        cls.kits = iv._kits(POLICY)
        cls.plain = iv.build(cls.spawn, cls.presets, POLICY['accessories'])
        cls.built = iv.build(cls.spawn, cls.presets, POLICY['accessories'], cls.kits)
        cls.rows = rows(cls.built['spawn'])
        cls.stock = rows(cls.spawn)

    def test_all_146_hc_classes_end_with_a_row_equal_to_their_source(self):
        report = self.built['report']
        self.assertEqual((report['hc_total'], report['hc_parity'], report['hc_missing']), (146, 146, 0))
        for name, parent in POLICY['accessories']['explicit_classes'].items():
            source = parent if parent in self.rows else POLICY['accessories']['parent_fallbacks'][parent]
            self.assertEqual(body(self.rows[name]), body(self.rows[source]), name)
            self.assertTrue(len(self.rows[name]), name)

    def test_kits_do_not_change_hc_parity_or_slot_sets(self):
        plain = rows(self.plain['spawn'])
        self.assertEqual(plain.keys(), self.rows.keys())
        for name, node in self.rows.items():
            self.assertEqual(len(node.findall('attachments')), len(plain[name].findall('attachments')), name)
            self.assertEqual(len(plain[name].findall('cargo')) + len(kit_presets(node)), len(node.findall('cargo')), name)

    def slot_total(self, node, presets):
        total = iv.Decimal(0)
        for a in node.findall('attachments'):
            chance = a.get('chance') if a.get('preset') is None else presets[a.get('preset')].get('chance')
            total += iv.Decimal(chance or '1')
        return total

    def test_worn_gear_moves_probability_without_changing_a_rows_total(self):
        presets = {n.get('name'): n for n in ET.fromstring(self.presets).findall('attachments')}
        explicit = POLICY['accessories']['explicit_classes']
        fallbacks = POLICY['accessories']['parent_fallbacks']
        moved = 0
        for name, node in self.rows.items():
            if not name.startswith(('ZmbM_', 'ZmbF_', 'HC_Zmb')):
                continue
            source = explicit.get(name, name)
            if source not in self.stock:
                source = fallbacks[source]
            self.assertEqual(self.slot_total(node, presets), self.slot_total(self.stock[source], presets), name)
            moved += any(a.get('preset') is None for a in node.findall('attachments'))
        self.assertTrue(moved)

    def test_only_role_rows_get_kits_and_no_row_has_more_than_two(self):
        explicit = POLICY['accessories']['explicit_classes']
        fallbacks = POLICY['accessories']['parent_fallbacks']
        for name, node in self.rows.items():
            if not name.startswith(('ZmbM_', 'ZmbF_', 'HC_Zmb')):
                self.assertEqual(kit_presets(node), [], name)
                continue
            source = explicit.get(name, name)
            if source not in self.stock:
                source = fallbacks[source]
            role = iv._role(source, self.kits)
            self.assertEqual(bool(kit_presets(node)), role is not None, name)
            self.assertLessEqual(len(kit_presets(node)), 2, name)

    def test_civilian_rows_are_unchanged_apart_from_the_authored_accessories(self):
        plain = rows(self.plain['spawn'])
        for name, node in self.rows.items():
            if not kit_presets(node):
                self.assertEqual(body(node), body(plain[name]), name)

    def test_kit_items_are_vanilla_stock_types(self):
        types = set(re.findall(r'<type name="([^"]+)"', (STOCK / 'db/types.xml').read_text(encoding='utf-8')))
        for name, row in self.kits['presets'].items():
            for item in row['items']:
                self.assertIn(item['name'], types, name)

    def test_worn_gear_items_exist_in_the_stock_presets(self):
        names = {n.get('name'): {i.get('name') for i in n} for n in ET.fromstring(self.presets)}
        for preset, items in self.kits['worn_gear']['item_transfers'].items():
            for row in items:
                self.assertLessEqual({row['from'], row['to']}, names[preset], preset)

    def test_plan_lines_on_the_stock_events(self):
        events = (STOCK / 'db/events.xml').read_bytes()
        result = iv.substitute(events, events, POLICY)
        lines = iv.plan_lines(self.built['report'], iv._events(result), self.kits)
        self.assertRegex(lines[0], r'^infected kits rows=\d+ presets=8 expected_extra_items~\d+$')
        self.assertEqual(lines[1], 'hc_children parity=146/146 missing=0')


class ReceiptLifecycleTests(unittest.TestCase):
    EVENTS = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<events>\n'
              b'    <event name="InfectedCity">\n        <nominal>50</nominal>\n        <active>1</active>\n'
              b'        <children>\n'
              b'            <child lootmax="5" lootmin="0" max="0" min="60" type="ZmbM_PatrolNormal_Autumn"/>\n'
              b'            <child lootmax="5" lootmin="0" max="0" min="40" type="ZmbF_Clerk_Normal_Blue"/>\n'
              b'        </children>\n    </event>\n</events>\n')

    def setUp(self):
        quiet = contextlib.redirect_stdout(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.mission = base / 'mission'
        (self.mission / 'db').mkdir(parents=True)
        self.files = {'db/events.xml': self.EVENTS, 'cfgspawnabletypes.xml': SPAWNABLE, 'cfgrandompresets.xml': PRESETS}
        for name, data in self.files.items():
            (self.mission / name).write_bytes(data)
        self.policy = synthetic_policy()
        self.policy['evidence']['stock_events_sha256'] = economy.sha(self.EVENTS)
        self.path = base / 'variants.json'
        self.set_policy(self.policy)

    def set_policy(self, policy):
        self.path.write_text(json.dumps(policy, indent=2) + '\n')
        patch = mock.patch.object(iv, 'POLICY', self.path)
        patch.start()
        self.addCleanup(patch.stop)

    def current(self):
        return {name: (self.mission / name).read_bytes() for name in self.files}

    def receipt(self):
        return json.loads((self.mission / iv.MANAGED / 'receipt.json').read_text())

    def test_install_records_three_files_policy_and_generator(self):
        iv.install(self.mission)
        receipt = self.receipt()
        self.assertEqual(set(receipt['files']), {iv.TARGET, iv.SPAWNABLE, iv.PRESETS})
        self.assertEqual(receipt['generator'], iv.GENERATOR_VERSION)
        self.assertEqual(receipt['kits_policy_sha256'], economy.sha(economy.encode(iv._kits(self.policy))))
        self.assertIn(iv.KIT_MARKER, self.current()['cfgrandompresets.xml'])

    def test_second_install_is_a_no_op_and_rollback_restores_stock_bytes(self):
        iv.install(self.mission)
        first = self.current()
        iv.install(self.mission)
        self.assertEqual(self.current(), first)
        iv.rollback(self.mission)
        self.assertEqual(self.current(), self.files)
        self.assertFalse((self.mission / iv.MANAGED).exists())

    def test_receipt_from_before_kits_is_refused_then_rolled_back_and_reapplied(self):
        legacy = copy.deepcopy(self.policy)
        legacy['mix_policy']['EnableKits'] = False
        self.set_policy(legacy)
        iv.install(self.mission)
        self.assertEqual(set(self.receipt()['files']), {iv.TARGET, iv.SPAWNABLE})
        self.assertEqual(self.current()['cfgrandompresets.xml'], PRESETS)
        # An older generator also lacks the generator and kit fields.
        path = self.mission / iv.MANAGED / 'receipt.json'
        data = json.loads(path.read_text())
        for key in ('generator', 'kits_policy_sha256'):
            data.pop(key)
        path.write_text(json.dumps(data))
        self.set_policy(self.policy)
        with self.assertRaisesRegex(ValueError, 'rollback first'):
            iv.install(self.mission)
        iv.rollback(self.mission)
        self.assertEqual(self.current(), self.files)
        iv.install(self.mission)
        self.assertEqual(set(self.receipt()['files']), {iv.TARGET, iv.SPAWNABLE, iv.PRESETS})
        self.assertIn(b'hc_kit_', self.current()['cfgspawnabletypes.xml'])

    def test_interrupted_install_still_rolls_back(self):
        iv.install(self.mission)
        (self.mission / 'cfgrandompresets.xml').write_bytes(PRESETS)
        iv.rollback(self.mission)
        self.assertEqual(self.current(), self.files)

    def test_drifted_preset_file_is_refused(self):
        iv.install(self.mission)
        (self.mission / 'cfgrandompresets.xml').write_bytes(PRESETS + b'\n')
        with self.assertRaisesRegex(ValueError, 'drift'):
            iv.install(self.mission)

    def test_kits_off_leaves_the_preset_file_alone(self):
        off = copy.deepcopy(self.policy)
        off['mix_policy']['EnableKits'] = False
        self.set_policy(off)
        iv.install(self.mission)
        self.assertEqual(self.current()['cfgrandompresets.xml'], PRESETS)
        self.assertNotIn(b'hc_kit_', self.current()['cfgspawnabletypes.xml'])
        # parity is not a kit feature: the children still copy their parents
        built = rows(self.current()['cfgspawnabletypes.xml'])
        self.assertEqual(body(built['HC_ZmbF_Crawler_ZmbF_NurseFat']), body(built['ZmbF_NurseFat']))


if __name__ == '__main__':
    unittest.main()
