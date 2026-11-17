"""Native hardening executes authored guards with synthetic engine adapters."""
import unittest
from types import SimpleNamespace as NS
from tests.unit.test_salvage_tools import authored, NativeArray
from tests.unit.test_crafting_families import Result

FILE='HCNativeCraftingSafety.c'

# Derived facts only. The cache is optional additional evidence, never a CI prerequisite.
from pathlib import Path
import json
import os
import re
from tests.unit.test_crafting_contract import FIXTURE


def native_cache():
    return Path(os.environ.get('HC_NATIVE_SCRIPTS_ROOT',
                str(Path.home()/'.cache/hollow-country/native-scripts/scripts-1.30.164289')))


def native_recipe_facts(text):
    """Project native Init into classes and literal quantity policy; no script text."""
    text = re.sub(r'//[^\n]*|/\*.*?\*/', '', text, flags=re.S)
    name = re.search(r'class (\w+)\s*(?:extends|:)\s*RecipeBase', text)[1]
    start = re.search(r'void Init\(\)\s*\{', text).end()
    depth, end = 1, start
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    init = text[start:end-1]
    def value(field, slot):
        values = re.findall(r'\b'+field+r'\['+str(slot)+r'\]\s*=\s*(-?[\d.]+|true|false)\s*;', init)
        if not values:
            raise ValueError('missing quantity fact: '+name+':'+field+':'+str(slot))
        normalized = [True if v == 'true' else False if v == 'false' else float(v) for v in values]
        if len(set(normalized)) != 1:
            raise ValueError('contradictory quantity fact: '+name+':'+field)
        return normalized[0]
    ingredients = []
    for slot in range(2):
        classes = re.findall(r'InsertIngredient\(\s*'+str(slot)+r'\s*,\s*"([^"]+)"', init)
        ingredients.append(dict(slot=slot, classes=classes,
            minimum=value('m_MinQuantityIngredient',slot),
            maximum=value('m_MaxQuantityIngredient',slot),
            quantity_delta=value('m_IngredientAddQuantity',slot),
            destroy=bool(value('m_IngredientDestroy',slot))))
    results = [dict(item=kind, quantity=value('m_ResultSetQuantity',i),
                    full_quantity=bool(value('m_ResultSetFullQuantity',i)))
               for i, kind in enumerate(re.findall(r'AddResult\("([^"]+)"\)',init))]
    return dict(name=name, ingredients=ingredients, results=results)


def native_fixture_sources(records):
    """SYNTHETIC recipes exercising only the committed derived quantity facts."""
    files = {}
    for record in records:
        lines = ['class '+record['name']+' extends RecipeBase { override void Init() {']
        for slot in record['ingredients']:
            index = slot['slot']
            lines += ['InsertIngredient(%d,"%s");' % (index,kind) for kind in slot['classes']]
            for field,key in [('m_MinQuantityIngredient','minimum'),('m_MaxQuantityIngredient','maximum'),
                              ('m_IngredientAddQuantity','quantity_delta'),('m_IngredientDestroy','destroy')]:
                val = slot[key]
                literal = str(val).lower() if isinstance(val,bool) else str(val)
                lines.append('%s[%d] = %s;' % (field,index,literal))
        for index,result in enumerate(record['results']):
            lines += ['AddResult("%s");' % result['item'],
                      'm_ResultSetQuantity[%d] = %s;' % (index,result['quantity']),
                      'm_ResultSetFullQuantity[%d] = %s;' % (index,str(result['full_quantity']).lower()),
                      'm_ResultInheritsColor[%d] = -1;' % index]
        lines += ['} override bool CanDo(ItemBase ingredients[], PlayerBase player) { return true; } }',
                  'class Registry { void Register() { RegisterRecipe(new '+record['name']+'); } }']
        files[record['name']+'.c'] = '\n'.join(lines).encode()
    return files


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
        call=authored('OnFinishProgressServer','action_data',{'GetGame':lambda:NS(IsServer=lambda:True)},'HCDrysackSafety.c')
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
            state=NS(ClassName=lambda:'DeCraftWoodenCrate',HCIsScoped=lambda:True,
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


class NativeReviewRoundTwoTests(unittest.TestCase):
    def test_native_derived_fixture_covers_every_condition_source_in_slot_one(self):
        from tests.unit.test_crafting_contract import FIXTURE
        import json
        from tests.unit.test_salvage_tools import body
        import re
        facts = {r['name']:r for r in json.loads(FIXTURE.read_text())['derived_native_recipes']}
        scoped = set(re.findall(r'recipeName == "([^"]+)"', body(FILE,'NeedsConditionCap')))
        source_classes = {'TannedLeather','LizardPelt','FoxPelt','LeatherSack_ColorBase',
                          'Waterskin_ColorBase','WoodenCrate','Truck_01_WheelDouble'}
        for name in scoped:
            with self.subTest(recipe=name):
                slots = facts[name]['ingredients']
                self.assertTrue(slots[0]['classes'])
                self.assertEqual(0,slots[0]['slot'])
                self.assertEqual(1,slots[1]['slot'])
                self.assertTrue(set(slots[0]['classes']) <= source_classes)
                self.assertTrue(set(slots[1]['classes']).isdisjoint(source_classes))

    def test_null_boundaries_fail_closed(self):
        discard = authored('DiscardNativeOutputs','results',{},FILE)
        cap = authored('CapNativeRecovery','results,sourceHealth',{},FILE)
        discard(None,None); cap(None,None,0.5)
        quantity = authored('HasRequiredQuantity','ingredient,debit',{'Magazine':NS(Cast=lambda x:None)},FILE)
        fake = Result('fake'); fake.IsMagazine=lambda:True
        self.assertFalse(quantity(None,fake,1))

    def test_empty_source_rejects_missing_inventory(self):
        safety=NS(NeedsEmptySource=lambda name:True,HasRequiredQuantity=lambda *args:True)
        call=authored('HCValidateNativeInputs','item1,item2,player',
                      {'HCNativeCraftingSafety':safety,'TrapBase':NS(Cast=lambda item:None)},FILE)
        state=NS(m_IngredientDestroy=[True,False],m_IngredientAddQuantity=[0,0],ClassName=lambda:'DeCraftWoodenCrate')
        source=Result('WoodenCrate'); source.IsEmpty=lambda:True; source.inventory=None
        tool=Result('Crowbar'); tool.IsEmpty=lambda:True
        self.assertFalse(call(state,source,tool,NS(IsAlive=lambda:True,IsUnconscious=lambda:False)))

    def test_drysack_null_finish_and_inventory_fail_closed(self):
        call=authored('OnFinishProgressServer','action_data',{'GetGame':lambda:NS(IsServer=lambda:True)},'HCDrysackSafety.c')
        call(NS(m_HCFinishing=False,HCValidDrysack=lambda *args:True),None)
        validate=authored('HCValidDrysack','item,player',{},'HCDrysackSafety.c')
        actor=NS(IsAlive=lambda:True,IsUnconscious=lambda:False)
        source=Result('DrysackBag_Green');source.owner=actor;source.IsEmpty=lambda:True;source.inventory=None
        self.assertFalse(validate(None,source,actor))

    def test_jambiya_correction_preserves_one_animation_and_sound_entry(self):
        state=NS(native=NS(Init=lambda:None),
                 m_Ingredients=[NativeArray(['LongWoodenStick']),NativeArray(['Jambiya;'])],
                 m_AnimationInfos=NativeArray([NS(m_IngredientName='Jambiya;')]),
                 m_SoundCategories=[NativeArray(['']),NativeArray([''])])
        def insert(slot, kind, *args):
            state.m_Ingredients[slot].append(kind)
            state.m_AnimationInfos.append(NS(m_IngredientName=kind))
        state.InsertIngredient=insert
        env={'RemoveIngredient':lambda slot,kind:state.m_Ingredients[slot].remove(kind),
             'DayZPlayerConstants':NS(CMD_ACTIONFB_SPLITTING_FIREWOOD=1)}
        call=authored('Init','',env,FILE,owner='SplitLongWoodenStick')
        call(state)
        self.assertEqual(['Jambiya'],state.m_Ingredients[1])
        self.assertEqual(['Jambiya'],[r.m_IngredientName for r in state.m_AnimationInfos])
        self.assertEqual([''],state.m_SoundCategories[1])


class DerivedNativeFixtureTests(unittest.TestCase):
    def test_derived_facts_match_cache_when_present(self):
        facts = json.loads(FIXTURE.read_text())['derived_native_recipes']
        self.assertEqual(14,len(facts))
        self.assertEqual(14,len({r['name'] for r in facts}))
        for record in facts:
            self.assertEqual({'name','ingredients','results'},set(record))
            path = native_cache()/'4_World/Classes/Recipes/Recipes'/(record['name']+'.c')
            if native_cache().exists():
                with self.subTest(recipe=record['name']):
                    self.assertEqual(record,native_recipe_facts(path.read_text()))

    def test_every_native_minimum_change_matches_a_required_literal_debit(self):
        from tests.unit.test_salvage_tools import body
        facts={r['name']:r for r in json.loads(FIXTURE.read_text())['derived_native_recipes']}
        for name,expected in [('CraftLeatherSack',[(0,2),(1,10)]),
                              ('CraftWaterskin',[(0,2),(1,10)]),('CraftWoodenHook',[(0,1)])]:
            init=body(FILE,'Init',name)
            actual=[(int(i),int(q)) for i,q in re.findall(r'm_MinQuantityIngredient\[(\d)\] = (\d+);',init)]
            self.assertEqual(expected,actual)
            for slot,quantity in actual:
                self.assertEqual(-1,facts[name]['ingredients'][slot]['minimum'])
                self.assertEqual(-quantity,facts[name]['ingredients'][slot]['quantity_delta'])
