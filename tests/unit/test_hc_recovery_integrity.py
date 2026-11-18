"""HC-4: authored handlers with explicit SYNTHETIC native boundaries.

Restricted execution reuses the crafting test port. No DayZ transaction,
inventory replication, persistence, or engine acceptance is established here.

TDD receipt (same focused command throughout):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_recovery_integrity -v
RED: FAILED (failures=4); actual property tuples (55, 0, 0, 1, 7) versus
     expected (20, 0.8, 6, 1, 7); drysack quantities (0, 0) versus (0, 1).
     A deleting allocation also reached ['results', 'debit', 'native-do'].
RED extension: FAILED (failures=2); filled waterskin: True is not false;
     invalidated result reached ['results', 'debit', 'native-do'].
RED diagnostic: FAILED (failures=1); expected startup receipt versus [].
GREEN: Ran 9 tests; OK. Native runtime acceptance remains pending.
"""
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_crafting_completion import execute_flat
from tests.unit.test_crafting_families import Result, state_for
from tests.unit.test_salvage_tools import authored, NativeArray

NATIVE = 'HCNativeCraftingSafety.c'


class Item(Result):
    def __init__(self, kind, health=40, quantity=1, wet=0.6, agents=2):
        super().__init__(kind, quantity)
        self.health, self.wet, self.agents = health, wet, agents
        self.energy = 0
        self.delete_calls = 0
        self.IsEmpty = lambda: True
        self.ConfigGetString = lambda key: 'Green'

    def GetWet(self): return self.wet
    def GetAgents(self): return self.agents
    def TransferAgents(self, agents): self.agents |= agents
    def Delete(self):
        self.delete_calls += 1
        self.deleted = True  # SYNTHETIC deferred-delete admission boundary.


def guard():
    state = NS(m_Busy=False)
    for name in ('TryEnter', 'Release'):
        call = authored(name, '', {}, owner='HCCraftingCommitGuard')
        setattr(state, name, lambda fn=call: fn(state))
    return state


def safety_policy():
    policy = NS()
    env = dict(HCNativeCraftingSafety=policy)
    for name, params in (
        ('IsScoped', 'recipeName'), ('NeedsConditionCap', 'recipeName'),
        ('NeedsEmptySource', 'recipeName'),
        ('CapNativeRecovery', 'results,sourceHealth'),
        ('DiscardNativeOutputs', 'results'),
        ('NeedsRecoveryState', 'recipeName'),
        ('InheritRecoveryState', 'source,results'),
    ):
        # Before an override exists, execute the original handler with the
        # explicit native boundary below, rather than failing on a new symbol.
        try:
            call = authored(name, params, env, NATIVE)
        except AssertionError:
            continue
        setattr(policy, name, lambda *args, fn=call: fn(None, *args))
    return policy


def native_completion(name, source, material, outputs, destroyed=(True, False), deltas=(0, 0), invalidate=False):
    """Native methods are stubs; HC PerformRecipe/result policy actually execute.

    The explicit average is the inspected native bag upgrade inheritance seam;
    the test does not implement recipes or native inventory in Python.
    """
    events = []
    policy = safety_policy()
    env = dict(HCNativeCraftingSafety=policy, NativeArray=NativeArray,
               MAX_NUMBER_OF_INGREDIENTS=2,
               GetGame=lambda: NS(IsServer=lambda: True))
    state = NS(ClassName=lambda: name, HCIsScoped=lambda: policy.IsScoped(name),
               m_HCNativeCommitGuard=guard(), m_IngredientsSorted=[source, material],
               m_NumberOfResults=len(outputs), m_Specialty=0,
               m_IngredientDestroy=destroyed, m_IngredientAddQuantity=deltas)
    state.CheckRecipe = lambda *args: not source.deleted and not material.deleted
    state.SpawnItems = lambda pair, actor, dest: dest.extend(outputs)
    def native_results(*args):
        events.append('results')
        if invalidate: outputs[0].Delete()
    state.native = NS(ApplyModificationsResults=native_results)
    try:
        apply = authored('ApplyModificationsResults', 'sorted,results,result,player', env, NATIVE)
        state.ApplyModificationsResults = lambda *args: apply(state, *args)
    except AssertionError:
        state.ApplyModificationsResults = state.native.ApplyModificationsResults

    def debit(pair, actor):
        events.append('debit')
        # Allocator callback reentry must fail before creating another output.
        perform(state, source, material, actor)

    state.ApplyModificationsIngredients = debit
    state.Do = lambda *args: events.append('native-do')
    state.DeleleIngredientsPass = lambda: source.Delete()
    perform = authored('PerformRecipe', 'item1,item2,player', env, NATIVE)
    perform(state, source, material, object())
    perform(state, source, material, object())
    return events


class RecoveryIntegrityTests(unittest.TestCase):
    def test_startup_receipt_distinguishes_authored_definitions_from_runtime_acceptance(self):
        lines = []
        check = execute_flat('HCCraftingNativeChecks.c', 'CheckCompletionGuard', '',
                             dict(HCCraftingCommitGuard=guard, Print=lines.append))
        self.assertTrue(check())
        self.assertEqual([
            '[HC Plan] HC-4 recovery definitions=11 native_safety=active '
            'state=checking observed=0 runtime=PENDING'
        ], lines)

    def test_native_upgrade_and_recovery_cannot_launder_material_properties(self):
        source = Item('WaterproofBag_Green', health=20, agents=2)
        rope = Item('Rope', health=90, wet=0.8, agents=4)
        upgraded = Item('DrysackBag_Green', health=55, wet=0, agents=0)
        upgraded.energy = 7  # Sentinel: selective inheritance must not copy energy.
        events = native_completion('CraftDrysackBag', source, rope, NativeArray([upgraded]), (True, True))
        self.assertEqual(['results', 'debit', 'native-do'], events)
        self.assertEqual(1, source.delete_calls)
        self.assertEqual((20, 0.8, 6, 1, 7),
                         (upgraded.health, upgraded.wet, upgraded.agents, upgraded.quantity, upgraded.energy))
        bag, recovered_rope = Item('BurlapSack', health=100, agents=0, wet=0), Item('Rope', health=100, agents=0, wet=0)
        tool = Item('KitchenKnife', health=90, agents=8, wet=1)
        native_completion('DeCraftCourierBag', upgraded, tool, NativeArray([bag, recovered_rope]))
        for output in (bag, recovered_rope):
            self.assertEqual((20, 0.8, 6), (output.health, output.wet, output.agents))

    def test_native_quantity_materials_contribute_but_unconsumed_tools_do_not(self):
        leather = Item('TannedLeather', health=40, quantity=2, agents=2)
        kit = Item('LeatherSewingKit', health=80, quantity=10, agents=4)
        output = Item('LeatherSack_Natural', health=60, wet=0, agents=0)
        native_completion('CraftLeatherSack', leather, kit, NativeArray([output]), (False, False), (-2, -10))
        self.assertEqual((40, 0.6, 6), (output.health, output.wet, output.agents))

    def test_failed_or_deleting_native_output_never_debits_and_cleans_provisionals(self):
        for failure in ('missing', 'deleting'):
            with self.subTest(failure=failure):
                source, tool = Item('CourierBag'), Item('KitchenKnife')
                survivor = Item('BurlapSack')
                bad = None if failure == 'missing' else Item('Rope')
                if bad: bad.deleted = True
                events = native_completion('DeCraftCourierBag', source, tool, NativeArray([survivor, bad]))
                self.assertEqual([], events)
                self.assertEqual(0, source.delete_calls)
                self.assertTrue(survivor.deleted)

    def test_native_result_mutation_failure_is_rechecked_before_debit(self):
        source, tool = Item('CourierBag'), Item('KitchenKnife')
        outputs = NativeArray([Item('BurlapSack'), Item('Rope')])
        events = native_completion('DeCraftCourierBag', source, tool, outputs, invalidate=True)
        self.assertEqual(['results'], events)
        self.assertEqual(0, source.delete_calls)
        self.assertTrue(all(item.deleted for item in outputs))

    def test_filled_waterskin_is_not_an_empty_recovery_source(self):
        env = dict(HCNativeCraftingSafety=safety_policy(), TrapBase=NS(Cast=lambda item: None))
        validate = authored('HCValidateNativeInputs', 'item1,item2,player', env, NATIVE)
        state = NS(ClassName=lambda: 'DeCraftWaterskin', m_IngredientDestroy=[True, False],
                   m_IngredientAddQuantity=[0, 0])
        source, tool = Item('Waterskin_Natural', quantity=1), Item('KitchenKnife')
        actor = NS(IsAlive=lambda: True, IsUnconscious=lambda: False)
        self.assertFalse(validate(state, source, tool, actor))
        source.quantity = 0
        self.assertTrue(validate(state, source, tool, actor))

    def test_all_eleven_hc_recoveries_use_the_same_selective_snapshot_policy(self):
        from tests.unit.test_crafting_families import FAMILIES
        from tests.unit.test_crafting_completion import PILOTS
        families = list(FAMILIES) + [p[0] for p in PILOTS]
        self.assertEqual(11, len(families))
        for name in families:
            with self.subTest(recipe=name):
                state = state_for(name if name in FAMILIES else 'HCRecoverBatWood')
                if name not in FAMILIES:
                    pilot = next(p for p in PILOTS if p[0] == name)
                    state.m_ItemsToCreate, state.m_ResultSetQuantity = [pilot[3]], [pilot[4]]
                    state.m_NumberOfResults = 1
                source = Item('synthetic-source', health=40)
                outputs = NativeArray(Item(kind, health=100, quantity=quantity, wet=0, agents=0)
                                      for kind, quantity in zip(state.m_ItemsToCreate, state.m_ResultSetQuantity))
                state.native.SpawnItems = lambda pair, actor, dest: dest.extend(outputs)
                state.native.ApplyModificationsResults = lambda *args: None
                dest = NativeArray()
                state.SpawnItems([source, object()], object(), dest)
                state.ApplyModificationsResults([source, object()], dest, None, object())
                state.Do([source, object()], object(), dest, 0)
                for result in dest:
                    self.assertAlmostEqual(10 if state.m_HCRuinedOnly else 30, result.health)
                    self.assertEqual((0.6, 2, 0), (result.wet, result.agents, result.energy))

    def test_drysack_selects_health_agents_wetness_and_preserves_output_quantity(self):
        source = Item('DrysackBag_Green', health=20, quantity=0)
        bag, rope = Item('WaterproofBag_Green', health=100, quantity=0), Item('Rope', health=100, quantity=1)
        actor = NS(IsAlive=lambda: True, IsUnconscious=lambda: False)
        source.owner = actor
        outcomes = iter([bag, rope])
        actor.SpawnEntityOnGroundRaycastDispersed = lambda kind: next(outcomes)

        def transfer(old, new, agents=True, variables=True, health=True, exclude_quantity=False):
            # Explicit native TransferItemProperties seam, not HC policy.
            if agents: new.agents |= old.agents
            if health: new.health = old.health
            if variables:
                new.energy = old.energy
                new.wet = old.wet
                if not exclude_quantity: new.quantity = old.quantity

        env = dict(GetGame=lambda: NS(IsServer=lambda: True),
                   MiscGameplayFunctions=NS(TransferItemProperties=transfer))
        validate = authored('HCValidDrysack', 'item,player', env, 'HCDrysackSafety.c')
        state = NS(m_HCFinishing=False, HCValidDrysack=lambda *args: validate(None, *args))
        finish = authored('OnFinishProgressServer', 'action_data', env, 'HCDrysackSafety.c')
        finish(state, NS(m_MainItem=source, m_Player=actor))
        finish(state, NS(m_MainItem=source, m_Player=actor))
        self.assertEqual(1, source.delete_calls)
        self.assertEqual((0, 1), (bag.quantity, rope.quantity))
        for output in (bag, rope):
            self.assertEqual((20, 0.6, 2), (output.health, output.wet, output.agents))

    def test_occupied_source_is_refused_before_native_drysack_allocation(self):
        source = Item('DrysackBag_Green')
        actor = NS(IsAlive=lambda: True, IsUnconscious=lambda: False)
        source.owner, source.IsEmpty = actor, lambda: False
        validate = authored('HCValidDrysack', 'item,player', {}, 'HCDrysackSafety.c')
        state = NS(m_HCFinishing=False, HCValidDrysack=lambda *args: validate(None, *args))
        finish = authored('OnFinishProgressServer', 'action_data',
                          {'GetGame': lambda: NS(IsServer=lambda: True)}, 'HCDrysackSafety.c')
        finish(state, NS(m_MainItem=source, m_Player=actor))
        self.assertEqual(0, source.delete_calls)


if __name__ == '__main__':
    unittest.main()
