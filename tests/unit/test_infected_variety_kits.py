"""Infected cargo replacements, worn gear and legacy receipt checks (#339).

Synthetic missions exercise the generator and the receipt path. The stock-file tests read the pinned
stock mission when the host has it and skip otherwise. Nothing here establishes CE or DayZ behaviour.
"""
import base64
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
    policy['infected_kits']['worn_gear'] = {'slot_transfers': [], 'item_transfers': {}}
    groups = economy._unique(ET.fromstring(PRESETS).findall('cargo'))
    row = rows(SPAWNABLE)['ZmbM_PatrolNormal_Autumn']
    policy['infected_kits']['cargo_replacements'] = {
        'ZmbM_PatrolNormal_Autumn': {
            'preset': 'foodArmy', 'from': 'TunaCan', 'to': 'Mag_STANAG_30Rnd',
            'cargo_sha256': iv._cargo_sha256(iv._resolved_cargo(row, groups)),
        },
    }
    return policy


def rows(data):
    return {n.get('name'): n for n in ET.fromstring(data).findall('type')}


def body(node):
    return tuple(iv._signature(c) for c in node)


def body_cargo(node):
    return tuple(iv._signature(c) for c in node.findall('cargo'))


def cargo_draws(node, presets):
    return tuple((group.get('chance'), tuple(i.get('chance') for i in group.findall('item')))
                 for _, group in iv._resolved_cargo(node, presets))


class SyntheticKitTests(unittest.TestCase):
    def setUp(self):
        self.policy = synthetic_policy()
        self.kits = iv._kits(self.policy)
        self.built = iv.build(SPAWNABLE, PRESETS, self.policy['accessories'], self.kits)
        self.rows = rows(self.built['spawn'])

    def test_hc_children_keep_attachment_only_rows_and_bare_parent_is_omitted(self):
        for name, parent in CLASSES.items():
            if parent not in self.rows:
                self.assertNotIn(name, self.rows)
                continue
            attachments = tuple(iv._signature(c) for c in self.rows[parent].findall('attachments'))
            self.assertEqual(body(self.rows[name]), attachments, name)

    def test_empty_parent_gives_an_empty_child(self):
        self.assertEqual(len(self.rows['ZmbF_PatientOld']), 0)
        self.assertEqual(len(self.rows['HC_ZmbF_Crawler_ZmbF_PatientOld']), 0)

    def test_preexisting_hc_rows_only_conflict_with_owned_names(self):
        operator = b'<type name="HC_ZmbM_Sitter"><attachments preset="foodArmy" /></type>'
        original = SPAWNABLE.replace(b'</spawnabletypes>', operator + b'\n</spawnabletypes>')
        overlay = self.policy['accessories']
        self.assertIn(operator, iv.build(original, PRESETS, overlay, self.kits)['spawn'])

        owned_name = next(iter(CLASSES))
        original = original.replace(b'HC_ZmbM_Sitter', owned_name.encode())
        with self.assertRaisesRegex(ValueError, 'explicit accessory class already present: ' + owned_name):
            iv.build(original, PRESETS, overlay, self.kits)

    def test_report_distinguishes_draw_conservation_from_native_nominal(self):
        report = self.built['report']
        self.assertEqual(report['kit_chance'], {'ZmbM_PatrolNormal_Autumn': iv.Decimal('0.01')})
        self.assertEqual(iv.plan_lines(report, {}, self.kits), [
            'infected kits rows=1 configured_draw_delta=0 modeled_added_items~0.000000 '
            'modeled_removed_items~0.000000 native_nominal=unverified',
            'hc_children attachment_rows=4 omitted=1 cargo_rows=0',
        ])

    def test_roles_follow_the_class_name_family(self):
        expected = {'ZmbM_PatrolNormal_Autumn': 'soldier', 'ZmbF_usSoldier_normal_Desert': 'soldier',
                    'ZmbM_takiSoldier_Officer': 'soldier', 'ZmbM_PolicemanSpecForce': 'police',
                    'ZmbF_takiPoliceWoman_Heavy': 'police', 'ZmbM_HunterOld_Winter': 'hunter',
                    'ZmbF_DoctorSkinny': 'medic', 'ZmbF_NurseFat': 'medic', 'ZmbM_ParamedicNormal_Red': 'medic',
                    'ZmbF_Clerk_Normal_Blue': None, 'ZmbM_PatientSkinny': None, 'ZmbM_FirefighterNormal': None,
                    'ZmbM_Mummy': None, 'ZmbM_NBC_Grey': None, 'ZmbM_HermitSkinny_Beige': None}
        for name, role in expected.items():
            self.assertEqual(iv._role(name, self.kits), role, name)

    def test_role_row_changes_one_item_and_unrelated_rows_keep_their_bytes(self):
        name = 'ZmbM_PatrolNormal_Autumn'
        stock = rows(SPAWNABLE)
        presets = economy._unique(ET.fromstring(PRESETS).findall('cargo'))
        patrol = self.rows[name]
        self.assertEqual([c.tag for c in patrol], ['cargo', 'attachments'])
        self.assertEqual(cargo_draws(patrol, presets), cargo_draws(stock[name], presets))
        self.assertEqual(patrol.find('cargo/item').get('name'), 'Mag_STANAG_30Rnd')
        stock_spans = iv._type_spans(SPAWNABLE)
        built_spans = iv._type_spans(self.built['spawn'])
        for other in stock.keys() - {name}:
            start, end = stock_spans[other]
            built_start, built_end = built_spans[other]
            self.assertEqual(self.built['spawn'][built_start:built_end], SPAWNABLE[start:end], other)

    def test_stale_donor_row_is_refused(self):
        original = SPAWNABLE.replace(b'<cargo preset="foodArmy" />', b'<cargo preset="foodArmy" />\n'
                                     b'<cargo chance="0.10"><item name="OtherItem" chance="1.0"/></cargo>', 1)
        with self.assertRaisesRegex(ValueError, 'donor signature changed'):
            iv.build(original, PRESETS, self.policy['accessories'], self.kits)

    def test_duplicate_target_in_other_gate_is_refused(self):
        original = SPAWNABLE.replace(b'<cargo preset="foodArmy" />', b'<cargo preset="foodArmy" />\n'
                                     b'<cargo chance="0.10"><item name="Mag_STANAG_30Rnd" chance="1.0"/></cargo>', 1)
        with self.assertRaisesRegex(ValueError, 'duplicate kit cargo target'):
            iv.build(original, PRESETS, self.policy['accessories'], self.kits)

    def test_missing_donor_row_is_refused(self):
        original = SPAWNABLE.replace(b'ZmbM_PatrolNormal_Autumn', b'ZmbM_PatrolNormal_Summer')
        with self.assertRaisesRegex(ValueError, 'kit cargo donor row is absent'):
            iv.build(original, PRESETS, self.policy['accessories'], self.kits)


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
            'no replacements': lambda k: k.update(cargo_replacements={}),
            'unknown role target': lambda k: next(iter(k['cargo_replacements'].values())).update(to='Roadflare'),
            'invalid donor digest': lambda k: next(iter(k['cargo_replacements'].values())).update(cargo_sha256='unknown'),
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

    def test_hc_parent_mapping_preserves_the_standalone_sitter_omission(self):
        config = (ROOT / 'mods/HollowCountryAnims/config.cpp').read_text(encoding='utf-8')
        classes = dict(re.findall(r'class\s+(HC_Zmb\w+)\s*:\s*(\w+)', config))
        self.assertEqual(len(classes), 146)
        # The shipped standalone sitter did not have an explicit spawnable row.
        classes.pop('HC_ZmbM_Sitter')
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

    def test_hc_children_keep_the_shipped_attachment_only_projection(self):
        report = self.built['report']
        self.assertEqual((report['hc_attachment_rows'], report['hc_omitted']), (143, 2))
        self.assertNotIn('HC_ZmbM_Sitter', self.rows)
        plain = rows(self.plain['spawn'])
        for name, parent in POLICY['accessories']['explicit_classes'].items():
            if parent not in self.stock:
                self.assertNotIn(name, self.rows)
            else:
                self.assertEqual(body(self.rows[name]), body(plain[name]), name)
                self.assertFalse(self.rows[name].findall('cargo'), name)

    def test_kits_keep_the_cargo_draws_and_attachment_slot_counts(self):
        plain = rows(self.plain['spawn'])
        presets = economy._unique(ET.fromstring(self.presets).findall('cargo'))
        self.assertEqual(plain.keys(), self.rows.keys())
        for name, node in self.rows.items():
            self.assertEqual(len(node.findall('attachments')), len(plain[name].findall('attachments')), name)
            if name in self.kits['cargo_replacements']:
                self.assertEqual(cargo_draws(node, presets), cargo_draws(plain[name], presets), name)
            else:
                self.assertEqual(body_cargo(node), body_cargo(plain[name]), name)

    def slot_total(self, node, presets):
        total = iv.Decimal(0)
        for a in node.findall('attachments'):
            chance = a.get('chance') if a.get('preset') is None else presets[a.get('preset')].get('chance')
            total += iv.Decimal(chance or '1')
        return total

    def test_worn_gear_moves_probability_without_changing_a_rows_total(self):
        presets = {n.get('name'): n for n in ET.fromstring(self.presets).findall('attachments')}
        explicit = POLICY['accessories']['explicit_classes']
        moved = 0
        for name, node in self.rows.items():
            if not name.startswith(('ZmbM_', 'ZmbF_', 'HC_Zmb')):
                continue
            source = explicit.get(name, name)
            self.assertEqual(self.slot_total(node, presets), self.slot_total(self.stock[source], presets), name)
            moved += any(a.get('preset') is None for a in node.findall('attachments'))
        self.assertTrue(moved)

    def test_only_authored_role_rows_get_new_cargo_items(self):
        expected = self.kits['cargo_replacements']
        self.assertEqual(len(expected), 15)
        self.assertEqual(set(self.built['report']['kit_chance']), set(expected))
        for name, replacement in expected.items():
            self.assertIsNotNone(iv._role(name, self.kits), name)
            targets = [i.get('name') for gate in self.rows[name].findall('cargo') for i in gate.findall('item')]
            self.assertEqual(targets.count(replacement['to']), 1, name)

    def test_civilian_rows_are_unchanged_apart_from_the_authored_accessories(self):
        for name, node in self.rows.items():
            if name in self.stock and iv._role(name, self.kits) is None:
                self.assertEqual(body_cargo(node), body_cargo(self.stock[name]), name)

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
        self.assertEqual(lines, ['infected kits rows=15 configured_draw_delta=0 modeled_added_items~5.649934 '
                                 'modeled_removed_items~5.649934 native_nominal=unverified',
                                 'hc_children attachment_rows=143 omitted=2 cargo_rows=0'])


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

    def test_duplicate_authored_row_is_refused_before_install_writes(self):
        authored = self.path.read_text()
        name, row = next(iter(self.policy['infected_kits']['cargo_replacements'].items()))
        duplicate = json.dumps(name) + ': ' + json.dumps(row) + ','
        authored = authored.replace('"cargo_replacements": {', '"cargo_replacements": {' + duplicate, 1)
        self.path.write_text(authored)
        with self.assertRaisesRegex(ValueError, 'duplicate infected variety policy key'):
            iv.install(self.mission)
        self.assertEqual(self.current(), self.files)
        self.assertFalse((self.mission / iv.MANAGED).exists())

    def test_install_records_owned_files_policy_and_generator(self):
        iv.install(self.mission)
        receipt = self.receipt()
        self.assertEqual(set(receipt['files']), {iv.TARGET, iv.SPAWNABLE})
        self.assertEqual(receipt['generator'], iv.GENERATOR_VERSION)
        self.assertEqual(receipt['kits_policy_sha256'], economy.sha(economy.encode(iv._kits(self.policy))))
        self.assertEqual(self.current()[iv.PRESETS], PRESETS)

    def test_second_install_is_a_no_op_and_rollback_restores_stock_bytes(self):
        iv.install(self.mission)
        first = self.current()
        iv.install(self.mission)
        self.assertEqual(self.current(), first)
        iv.rollback(self.mission)
        self.assertEqual(self.current(), self.files)
        self.assertFalse((self.mission / iv.MANAGED).exists())

    def test_changed_season_reinstalls_and_keeps_the_original_backups(self):
        for season in (None, 'winter', 'summer', None):
            receipt = iv.install(self.mission, season=season)
            self.assertEqual(receipt['season'], season)
            first = self.current()
            self.assertEqual(iv.install(self.mission, season=season), receipt)
            self.assertEqual(self.current(), first)
            for name, row in receipt['files'].items():
                self.assertEqual(row['before_sha256'], economy.sha(self.files[name]))
        iv.rollback(self.mission)
        self.assertEqual(self.current(), self.files)

    def test_changed_season_refuses_drift_and_invalid_season_without_writing(self):
        iv.install(self.mission, season='winter')
        first = self.current()
        with self.assertRaisesRegex(ValueError, 'unknown season'):
            iv.install(self.mission, season='monsoon')
        self.assertEqual(self.current(), first)
        (self.mission / iv.PRESETS).write_bytes(PRESETS + b'\n')
        drifted = self.current()
        receipt = self.receipt()
        with self.assertRaisesRegex(ValueError, 'drift'):
            iv.install(self.mission, season='summer')
        self.assertEqual(self.current(), drifted)
        self.assertEqual(self.receipt(), receipt)

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
        self.assertEqual(set(self.receipt()['files']), {iv.TARGET, iv.SPAWNABLE})
        self.assertIn(b'Mag_STANAG_30Rnd', self.current()[iv.SPAWNABLE])

    def test_three_file_additive_receipt_rolls_back_then_reapplies_as_two_files(self):
        iv.install(self.mission)
        data = self.receipt()
        data['generator'] = 'HC-339-kits-1'
        legacy_presets = PRESETS.replace(b'</randompresets>', iv.KIT_MARKER + b'\n</randompresets>')
        data['files'][iv.PRESETS] = {'before': base64.b64encode(PRESETS).decode(),
                                     'before_sha256': economy.sha(PRESETS), 'after': economy.sha(legacy_presets)}
        (self.mission / iv.PRESETS).write_bytes(legacy_presets)
        (self.mission / iv.MANAGED / 'receipt.json').write_bytes(economy.encode(data))
        with self.assertRaisesRegex(ValueError, 'rollback first'):
            iv.install(self.mission)
        iv.rollback(self.mission)
        self.assertEqual(self.current(), self.files)
        iv.install(self.mission)
        self.assertEqual(set(self.receipt()['files']), {iv.TARGET, iv.SPAWNABLE})
        self.assertEqual(self.current()[iv.PRESETS], PRESETS)

    def test_interrupted_install_still_rolls_back(self):
        iv.install(self.mission)
        (self.mission / iv.SPAWNABLE).write_bytes(SPAWNABLE)
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
        built = rows(self.current()['cfgspawnabletypes.xml'])
        self.assertEqual(body_cargo(built['ZmbM_PatrolNormal_Autumn']),
                         body_cargo(rows(SPAWNABLE)['ZmbM_PatrolNormal_Autumn']))
        self.assertFalse(built['HC_ZmbF_Crawler_ZmbF_NurseFat'].findall('cargo'))


if __name__ == '__main__':
    unittest.main()
