"""Audit #199 equipment supply routes: the twelve leather and one water ledger decisions are resolved, not parked.

Fixtures are SYNTHETIC or read the committed ledger and floor policy as data. Nothing here observes DayZ: whether the
CE spawns the admitted rows, and what a spawned bottle holds, stay pending a native server session (runtime=PENDING).
"""
import json
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / 'config/loot-dispositions.json'
GLOVES = ['LeatherGloves_' + c for c in ('Beige', 'Black', 'Brown', 'Natural')]
CRAFT_ONLY = [f + '_' + c for f in ('LeatherPants', 'LeatherStorageVest') for c in ('Beige', 'Black', 'Brown', 'Natural')]
RETIRED_REFUSALS = ('HC22_LEATHER_RECIPE_UNESTABLISHED', 'HC22_WATER_CONTENTS_UNOBSERVED')


def entries():
    return {e['class']: e for e in json.loads(LEDGER.read_bytes())['entries']}


class LeatherRoutes(unittest.TestCase):
    def test_no_decision_is_left_unresolved_or_carries_a_retired_refusal(self):
        for name, entry in entries().items():
            self.assertNotEqual(entry['route'], 'unresolved', name)
            self.assertNotIn(entry['refusal'], RETIRED_REFUSALS, name)

    def test_leather_gloves_join_the_reviewed_finite_floor_route(self):
        table = entries()
        for name in GLOVES:
            entry = table[name]
            self.assertEqual((entry['route'], entry['floor_admitted'], entry['refusal']), ('native-floor', True, None), name)
            self.assertEqual(entry['eligibility'], 'pending-native', name)
            self.assertTrue(any('lootCategory' in e for e in entry['evidence']), name)

    def test_pants_and_vests_stay_craft_only_with_the_installed_config_as_evidence(self):
        table = entries()
        for name in CRAFT_ONLY:
            entry = table[name]
            self.assertEqual((entry['route'], entry['floor_admitted']), ('excluded', False), name)
            self.assertEqual(entry['refusal'], 'HC22_CRAFTED_CATEGORY_NO_RECIPE', name)
            text = ' '.join(entry['evidence'])
            self.assertIn('lootCategory=Crafted', text, name)
            self.assertIn('no native recipe', text, name)

    def test_water_bottle_contents_come_from_the_stock_quantity_range_and_the_native_creation_hook(self):
        entry = entries()['WaterBottle']
        self.assertEqual((entry['route'], entry['floor_admitted'], entry['refusal']), ('native-carrier', False, None))
        text = ' '.join(entry['evidence'])
        self.assertIn('quantmin=20', text)
        self.assertIn('quantmax=70', text)
        self.assertIn('WaterBottle.c:60-79', text)
        self.assertIn('pending', text.lower())

    def test_the_ledger_still_loads_and_only_floor_rows_are_admitted(self):
        from tools.package import datamined_items as items
        doc = items.load_supply_dispositions()
        admitted = [e for e in doc['entries'] if e['floor_admitted']]
        self.assertEqual(len(admitted), 59)
        self.assertEqual({e['route'] for e in admitted}, {'native-floor'})
        self.assertTrue(set(GLOVES) <= {e['class'] for e in admitted})
        self.assertFalse(set(CRAFT_ONLY) & {e['class'] for e in admitted})


class FloorPolicyIsPreserved(unittest.TestCase):
    """The owner's rule (clothes and garbage only on floors) is untouched by resolving these rows."""
    def setUp(self):
        from tools.package import loot_floor_policy as policy
        self.policy = policy
        self.doc = policy.parse_policy((REPO / policy.FLOOR_POLICY).read_bytes())

    def test_admitted_gloves_are_floor_eligible_clothes_and_water_is_not(self):
        for name in GLOVES:
            self.assertTrue(self.policy.floor_eligible(name, 'clothes', self.doc), name)
        self.assertFalse(self.policy.floor_eligible('WaterBottle', 'food', self.doc))

    def test_retag_keeps_glove_rows_and_still_moves_a_synthetic_tool_to_shelves(self):
        types = ('<types>'
                 '<type name="LeatherGloves_Beige"><nominal>2</nominal><min>1</min><category name="clothes"/>'
                 '<tag name="floor"/></type>'
                 '<type name="SyntheticTool"><nominal>6</nominal><min>2</min><category name="tools"/>'
                 '<tag name="floor"/></type></types>').encode()
        out, _rows = self.policy.retag_types(types, self.doc)
        text = out.decode()
        glove = text.split('LeatherGloves_Beige', 1)[1].split('</type>', 1)[0]
        tool = text.split('SyntheticTool', 1)[1].split('</type>', 1)[0]
        self.assertIn('name="floor"', glove)
        self.assertNotIn('name="floor"', tool)
        self.assertIn('name="shelves"', tool)


if __name__ == '__main__':
    unittest.main()
