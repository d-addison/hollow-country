"""Issue 229: authored recipe behavior, using explicit synthetic native adapters.
These tests do not establish DayZ execution or inventory replication.
"""
from pathlib import Path
from types import SimpleNamespace as NS
import re
import unittest
from tests.unit.test_salvage_tools import authored, configured, NativeArray, SyntheticItem, tool_policy

FILE = 'auditleather_recipes.c'
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/Crafting' / FILE
OUTPUTS = tuple(f'{family}_{color}' for family in ('LeatherPants', 'LeatherStorageVest')
                for color in ('Beige', 'Black', 'Brown', 'Natural'))
POLICY = NS(PANTS_PANELS=3, VEST_PANELS=4, KIT_UNITS=10, ANIMATION_UNITS=2)


def tailoring(kind='LeatherPants_Natural', panels=3):
    state = configured()
    from tests.unit.test_crafting_families import source_policy
    configure = authored('Configure', 'label,inputType,toolType,outputType,quantity,wear,animationUnits',
                         {'MAX_NUMBER_OF_INGREDIENTS': 2, 'HCSalvageTools': tool_policy(),
                          'HCSalvageSources': source_policy()})
    state.Configure = lambda *args: configure(state, *args)
    state.m_Ingredients = [NativeArray(), NativeArray()]
    state.m_HCWear = 0
    state.m_HCInputType = ''
    state.results = []
    state.AddResult = state.results.append
    authored('HCConfigureTailoring', 'label,outputType,panels',
             {'HCAuditLeatherPolicy': POLICY}, FILE)(state, 'synthetic tailoring', kind, panels)
    return state


class LeatherRecipeTests(unittest.TestCase):
    def test_all_crafted_only_variants_have_registered_native_recipes(self):
        text = SOURCE.read_text() if SOURCE.exists() else ''
        results = re.findall(r'HCConfigureTailoring\("[^"]+", "([^"]+)"', text)
        self.assertEqual(set(OUTPUTS), set(results), 'crafted-only pants and vests need tailoring recipes')
        names = re.findall(r'class (HCAuditLeather\w+) extends HCAuditLeatherRecipe', text)
        self.assertEqual(8, len(names))
        for name in names:
            self.assertEqual(1, text.count('RegisterRecipe(new ' + name + ')'))

    def test_finite_panels_and_native_kit_wear_without_whole_stack_destruction(self):
        for kind in OUTPUTS:
            panels = 3 if kind.startswith('LeatherPants') else 4
            state = tailoring(kind, panels)
            self.assertEqual([['TannedLeather'], ['SewingKit', 'LeatherSewingKit']], state.m_Ingredients)
            self.assertEqual([panels, 10], state.m_MinQuantityIngredient)
            self.assertEqual([-panels, -10], state.m_IngredientAddQuantity)
            self.assertEqual([False, False], state.m_IngredientDestroy)
            self.assertEqual(0, state.m_IngredientAddHealth[1])

    def test_startup_audit_rejects_cached_debit_drift_and_missing_config(self):
        available = [True]
        game = NS(ConfigIsExisting=lambda path: available[0], ConfigGetInt=lambda path: 2,
                  ConfigGetFloat=lambda path: 100)
        check = authored('HCCheckDefinition', 'recipe,output,panels',
                         {'HCAuditLeatherPolicy': POLICY, 'GetGame': lambda: game}, FILE)
        state = tailoring()
        state.m_NumberOfResults = 1
        state.m_ItemsToCreate = state.results
        self.assertTrue(check(None, state, 'LeatherPants_Natural', 3))
        for field, index, value in [('m_IngredientDestroy', 0, True),
                                    ('m_IngredientAddQuantity', 0, 0),
                                    ('m_IngredientAddQuantity', 1, 0),
                                    ('m_MinQuantityIngredient', 1, 0),
                                    ('m_ResultSetQuantity', 0, 2),
                                    ('m_ResultReplacesIngredient', 0, 0)]:
            before = getattr(state, field)[index]
            getattr(state, field)[index] = value
            self.assertFalse(check(None, state, 'LeatherPants_Natural', 3))
            getattr(state, field)[index] = before
        available[0] = False
        self.assertFalse(check(None, state, 'LeatherPants_Natural', 3))
        self.assertFalse(check(None, None, 'LeatherPants_Natural', 3))

    def test_client_preview_does_not_depend_on_server_startup_state(self):
        policy = NS(m_Ready=False)
        game = NS(IsServer=lambda: False)
        preview = authored('HCPreviewReady', '',
                           {'HCAuditLeatherPolicy': policy, 'GetGame': lambda: game}, FILE)
        self.assertTrue(preview(None))
        game.IsServer = lambda: True
        self.assertFalse(preview(None))
        policy.m_Ready = True
        self.assertTrue(preview(None))

    def test_preview_rejects_short_materials_ruined_tools_foreign_and_deleting_items(self):
        gate = NS(CanPreviewOrCraft=lambda: True)
        policy = NS(m_Ready=True)
        policy.HCPreviewReady = lambda: policy.m_Ready
        call = authored('CanDo', 'ingredients,player',
                        {'HCCraftingGate': gate, 'HCAuditLeatherPolicy': policy}, FILE)
        actor = NS(IsAlive=lambda: True, IsUnconscious=lambda: False)
        state = tailoring()
        custody = authored('IsOwnedEmptyLooseItem', 'item,player', {})
        state.IsOwnedEmptyLooseItem = lambda item, player: custody(None, item, player)
        state.native = NS(CanDo=lambda pair, player: True)
        leather = SyntheticItem('TannedLeather', actor)
        kit = SyntheticItem('SewingKit', actor)
        leather.HasQuantity = kit.HasQuantity = lambda: True
        leather.quantity, kit.quantity = 3, 10
        leather.GetQuantity = lambda: leather.quantity
        kit.GetQuantity = lambda: kit.quantity
        self.assertTrue(call(state, [leather, kit], actor))
        for field, value in [('quantity', 2.99), ('deleted', True), ('owner', object()), ('ruined', True)]:
            old = getattr(leather, field)
            setattr(leather, field, value)
            self.assertFalse(call(state, [leather, kit], actor))
            setattr(leather, field, old)
        kit.quantity = 9.99
        self.assertFalse(call(state, [leather, kit], actor))
        kit.quantity = 10
        policy.m_Ready = False
        self.assertFalse(call(state, [leather, kit], actor))
        policy.m_Ready = True
        gate.CanPreviewOrCraft = lambda: False
        self.assertFalse(call(state, [leather, kit], actor))


if __name__ == '__main__':
    unittest.main()
