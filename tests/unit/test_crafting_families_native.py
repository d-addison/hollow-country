"""Native hardening executes authored guards with synthetic engine adapters."""
import unittest
from types import SimpleNamespace as NS
from tests.unit.test_salvage_tools import authored, NativeArray
from tests.unit.test_crafting_families import Result

FILE='HCNativeCraftingSafety.c'

class NativeFamilySafetyTests(unittest.TestCase):
    def test_quantity_debits_reject_empty_fractional_and_deleting_inputs(self):
        call=authored('HasRequiredQuantity','ingredient,debit',{'Magazine':NS(Cast=lambda x:x)},FILE)
        for debit in (1,2,10,12,16):
            ingredient=Result('material');ingredient.IsMagazine=lambda:False
            for quantity in (0,0.5,debit-0.01):
                ingredient.quantity=quantity;self.assertFalse(call(None,ingredient,debit))
            ingredient.quantity=debit;self.assertTrue(call(None,ingredient,debit))
            ingredient.deleted=True;self.assertFalse(call(None,ingredient,debit))
        self.assertFalse(call(None,None,1))

    def test_failed_native_allocation_destroys_only_its_own_results(self):
        call=authored('DiscardNativeOutputs','results',{},FILE)
        for hole in (0,1):
            outputs=NativeArray([Result('one'),Result('two')]);survivor=outputs[1-hole];outputs[hole]=None
            unrelated=Result('keep');call(None,outputs)
            self.assertTrue(survivor.deleted);self.assertFalse(unrelated.deleted)
            self.assertEqual([],outputs)

    def test_recovered_condition_never_exceeds_snapshot(self):
        call=authored('CapNativeRecovery','results,sourceHealth',{},FILE)
        for source in (0.1,0.25,0.5,0.75,1):
            low=Result('low');low.health=5;high=Result('high');high.health=100
            outputs=NativeArray([low,high]);call(None,outputs,source)
            self.assertEqual(5,low.health);self.assertEqual(source*100,high.health)

    def test_drysack_partial_failure_orders_retain_source_and_original_tool_state(self):
        call=authored('OnFinishProgressServer','action_data',{},'HCDrysackSafety.c')
        for hole in (0,1):
            source=Result('DrysackBag_Green');source.ConfigGetString=lambda key:'Green'
            actor=NS(IsAlive=lambda:True,IsUnconscious=lambda:False)
            source.owner=actor
            outcomes=[Result('WaterproofBag_Green'),Result('Rope')]
            survivor=outcomes[1-hole];outcomes[hole]=None
            actor.SpawnEntityOnGroundRaycastDispersed=lambda name:outcomes.pop(0)
            state=NS(m_HCFinishing=False,HCValidDrysack=lambda item,player:True)
            call(state,NS(m_MainItem=source,m_Player=actor))
            self.assertTrue(survivor.deleted);self.assertFalse(source.deleted)
            self.assertFalse(state.m_HCFinishing)

    def test_native_completion_allocates_all_before_debit_and_keeps_custom_do(self):
        discard=authored('DiscardNativeOutputs','results',{},FILE)
        cap=authored('CapNativeRecovery','results,sourceHealth',{},FILE)
        safety=NS(IsScoped=lambda name:True, NeedsConditionCap=lambda name:True,
                  DiscardNativeOutputs=lambda outputs:discard(None,outputs),
                  CapNativeRecovery=lambda outputs,health:cap(None,outputs,health))
        env={'HCNativeCraftingSafety':safety,'GetGame':lambda:NS(IsServer=lambda:True),'NativeArray':NativeArray}
        call=authored('PerformRecipe','item1,item2,player',env,FILE)
        for hole in (None,0,1):
            source=Result('WoodenCrate');source.health=40;tool=Result('Crowbar')
            outputs=NativeArray([Result('WoodenPlank'),Result('Nail')]);events=[]
            if hole is not None:outputs[hole]=None
            def debit(pair,actor):
                events.append('debit');source.health=100
            state=NS(ClassName=lambda:'DeCraftWoodenCrate',
                     m_HCNativeCommitGuard=NS(TryEnter=lambda:True,Release=lambda:events.append('release')),
                     CheckRecipe=lambda *args:True,m_IngredientsSorted=[source,tool],m_NumberOfResults=2,m_Specialty=0.02,
                     SpawnItems=lambda pair,actor,dest:dest.extend(outputs),
                     ApplyModificationsResults=lambda *args:events.append('result-policy'),
                     ApplyModificationsIngredients=debit,
                     Do=lambda *args:events.append('native-do'),DeleleIngredientsPass=lambda:events.append('delete'))
            call(state,source,tool,object())
            if hole is None:
                self.assertEqual(['result-policy','debit','native-do','delete','release'],events)
                self.assertEqual([40,40],[r.health for r in outputs])
            else:
                self.assertEqual(['release'],events)
                self.assertTrue(outputs[1-hole].deleted)
            self.assertEqual(100,tool.health)

    def test_native_destroy_precedence_does_not_require_quantity_on_whole_pelts(self):
        quantity=authored('HasRequiredQuantity','ingredient,debit',{'Magazine':NS(Cast=lambda x:x)},FILE)
        safety=NS(NeedsEmptySource=lambda name:False,
                  HasRequiredQuantity=lambda item,debit:quantity(None,item,debit))
        env={'HCNativeCraftingSafety':safety,'TrapBase':NS(Cast=lambda item:None)}
        call=authored('HCValidateNativeInputs','item1,item2,player',env,FILE)
        state=NS(m_IngredientDestroy=[True,False],m_IngredientAddQuantity=[-1,0],ClassName=lambda:'CraftTannedLeather')
        pelt=Result('Pelt_Base');pelt.IsMagazine=lambda:False;pelt.HasQuantity=lambda:False
        lime=Result('GardenLime');actor=NS(IsAlive=lambda:True,IsUnconscious=lambda:False)
        self.assertTrue(call(state,pelt,lime,actor))
        state.m_IngredientDestroy[0]=False
        self.assertFalse(call(state,pelt,lime,actor))
