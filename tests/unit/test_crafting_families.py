"""Execute authored recovery policy against synthetic native adapters, never DayZ."""
import re
import unittest
from types import SimpleNamespace as NS
from tests.unit.test_salvage_tools import authored, configured, tool_policy, SyntheticItem, NativeArray
from tests.unit.test_crafting_completion import SRC

LARGE = ['LeatherJacket_'+c for c in ('Beige','Black','Brown','Natural')] + ['LeatherStorageVest_'+c for c in ('Beige','Black','Brown','Natural')]
MEDIUM = ['LeatherPants_'+c for c in ('Beige','Black','Brown','Natural')] + ['LeatherShirt_Natural', 'LeatherGloves_Beige', 'LeatherHat_Beige'] + [item+'_'+c for item in ('LeatherGloves','LeatherHat') for c in ('Black','Brown','Natural')]
FAMILIES = {
    'HCRecoverLargeLeather':(LARGE,'KitchenKnife',[('TannedLeather',2)],5,2,False),
    'HCRecoverMediumLeather':(MEDIUM,'KitchenKnife',[('TannedLeather',1)],5,2,False),
    'HCRecoverBatWood':(['BaseballBat','XmasBaseballBat'],'Hacksaw',[('WoodenStick',2)],5,2,False),
    'HCRecoverNailedBat':(['NailedBaseballBat'],'Hacksaw',[('WoodenStick',1),('Nail',4)],8,3,False),
    'HCRecoverBarbedBat':(['BarbedBaseballBat'],'Pliers',[('MetalWire',1)],8,3,False),
    'HCRecoverRuinedLargeLeather':(LARGE,'KitchenKnife',[('TannedLeather',1)],5,2,True),
    'HCRecoverRuinedBatWood':(['BaseballBat','XmasBaseballBat'],'Hacksaw',[('WoodenStick',1)],5,2,True),
    'HCRecoverRuinedNailedBat':(['NailedBaseballBat'],'Hacksaw',[('Nail',1)],8,3,True),
    'HCRecoverRuinedCrate':(['WoodenCrate'],'Crowbar',[('WoodenPlank',1),('Nail',2)],20,3,True),
}


def source_policy():
    policy=NS();env={'HCSalvageSources':policy}
    for name,params in [('SourceCount','seed'),('SourceAt','seed,index'),('AllowsSource','seed,actualType')]:
        call=authored(name,params,env)
        setattr(policy,name,lambda *args,fn=call:fn(None,*args));env[name]=getattr(policy,name)
    return policy


class Result(SyntheticItem):
    def __init__(self,kind,quantity=0):
        super().__init__(kind,None,100);self.quantity=quantity;self.wet=0
    def Delete(self): self.deleted=True
    def HasQuantity(self): return True
    def GetQuantity(self): return self.quantity
    def SetHealth(self,zone,kind,value): self.health=value
    def GetMaxHealth(self,*args):return 100
    def SetWet(self,value):self.wet=value
    def TransferAgents(self,value):self.agents=value


def state_for(family):
    sources,seed,outputs,wear,animation,ruined=FAMILIES[family]
    state=configured(seed)
    state.m_HCInputType=family;state.m_HCRuinedOnly=ruined
    state.m_HCWear=wear;state.m_HCOutputReady=False
    state.m_NumberOfResults=len(outputs);state.m_ItemsToCreate=[n for n,q in outputs]
    state.m_ResultSetQuantity=[q for n,q in outputs]
    state.native=NS(CanDo=lambda pair,actor:True)
    env={'HCSalvageTools':tool_policy(),'HCSalvageSources':source_policy(),
         'HCCraftingGate':NS(CanPreviewOrCraft=lambda:True,RecordCraft=lambda:None)}
    for name,params in [('IsOwnedEmptyLooseItem','item,player'),('IsSourceConditionValid','item'),
                         ('CanDo','ingredients,player'),('DiscardOutputs','spawned_objects'),
                         ('OutputsMatch','spawned_objects,checkQuantity'),
                         ('SpawnItems','ingredients,player,spawned_objects'),
                         ('ApplyModificationsResults','sorted,results,result,player'),
                         ('Do','ingredients,player,results,specialty_weight')]:
        call=authored(name,params,env)
        setattr(state,name,lambda *args,fn=call:fn(state,*args))
    return state


class CraftingFamiliesTests(unittest.TestCase):
    def test_exact_source_families_exclude_children_belts_and_other_melee(self):
        policy=source_policy()
        for name,(sources,*_) in FAMILIES.items():
            actual=[policy.SourceAt(name,i) for i in range(policy.SourceCount(name))]
            self.assertEqual(sources,actual)
            for source in sources:
                self.assertTrue(policy.AllowsSource(name,source))
                self.assertFalse(policy.AllowsSource(name,source+'_Mod'))
            for source in ['LeatherBelt_Lizard','LeatherShirt_Black','Mace','Pipe','MetalBaseballBat']:
                self.assertFalse(policy.AllowsSource(name,source))

    def test_completion_health_custody_and_same_tool_for_every_alternative(self):
        actor=NS(IsAlive=lambda:True,IsUnconscious=lambda:False)
        for name,(sources,seed,outputs,wear,animation,ruined) in FAMILIES.items():
            state=state_for(name);policy=tool_policy()
            for kind in sources:
                source=SyntheticItem(kind,actor,50);source.ruined=ruined
                source.GetHealthLevel=lambda:4 if source.ruined else 2
                for index in range(policy.ToolCount(seed)):
                    tool=SyntheticItem(policy.ToolAt(seed,index),actor,wear+1)
                    pair=[source,tool]
                    self.assertTrue(state.CanDo(pair,actor),(name,kind,tool.kind))
                    self.assertIs(pair[1],tool)
                    for change,undo in [(lambda:setattr(tool,'health',wear),lambda:setattr(tool,'health',wear+1)),
                                        (lambda:setattr(source,'deleted',True),lambda:setattr(source,'deleted',False)),
                                        (lambda:setattr(source,'owner',None),lambda:setattr(source,'owner',actor)),
                                        (lambda:setattr(source,'inventory',NS(IsAttachment=lambda:True)),lambda:setattr(source,'inventory',NS(IsAttachment=lambda:False,AttachmentCount=lambda:0,GetCargo=lambda:None)))]:
                        change();self.assertFalse(state.CanDo(pair,actor));undo()
                source.ruined=not ruined
                self.assertFalse(state.CanDo([source,tool],actor))

    def test_ruined_siblings_recover_strictly_less_of_pristine_materials(self):
        from collections import Counter
        for ruined, ordinary in [('HCRecoverRuinedLargeLeather','HCRecoverLargeLeather'),
                                 ('HCRecoverRuinedBatWood','HCRecoverBatWood'),
                                 ('HCRecoverRuinedNailedBat','HCRecoverNailedBat')]:
            after = Counter(dict(FAMILIES[ruined][2]))
            before = Counter(dict(FAMILIES[ordinary][2]))
            self.assertTrue(all(after[k] <= before[k] for k in after))
            self.assertTrue(any(after[k] < before[k] for k in before))
            self.assertEqual(FAMILIES[ordinary][0], FAMILIES[ruined][0])

    def test_partial_allocations_clean_only_provisional_outputs_and_never_consume(self):
        for name in ('HCRecoverNailedBat','HCRecoverRuinedCrate'):
            for missing in (0,1):
                state=state_for(name);outputs=NativeArray(Result(n) for n in state.m_ItemsToCreate)
                survivor=outputs[1-missing];outputs[missing]=None
                source=Result('source');source.GetWet=lambda:0.6;source.GetAgents=lambda:7
                untouched=Result('unrelated')
                state.native.SpawnItems=lambda pair,actor,dest:dest.extend(outputs)
                dest=NativeArray();state.SpawnItems([source,object()],object(),dest)
                self.assertFalse(state.m_HCOutputReady)
                self.assertTrue(survivor.deleted);self.assertFalse(untouched.deleted)
                self.assertFalse(source.deleted)
                self.assertEqual([],dest)

    def test_fixed_quantities_checked_after_native_mutations_and_condition_uses_snapshot(self):
        for name in FAMILIES:
            state=state_for(name);source=Result('source');source.health=40
            source.GetWet=lambda:0.6;source.GetAgents=lambda:7
            outputs=NativeArray(Result(n,q) for n,q in zip(state.m_ItemsToCreate,state.m_ResultSetQuantity))
            state.native.SpawnItems=lambda pair,actor,dest:dest.extend(outputs)
            state.native.ApplyModificationsResults=lambda *args:None
            dest=NativeArray();state.SpawnItems([source,object()],object(),dest)
            state.ApplyModificationsResults([source,object()],dest,None,object())
            self.assertTrue(state.m_HCOutputReady)
            source.health=100
            state.Do([source,object()],object(),dest,0)
            for result in dest:
                self.assertAlmostEqual(10 if FAMILIES[name][5] else 30,result.health)
            if 'Leather' in name:
                self.assertEqual(0.6,dest[0].wet);self.assertEqual(7,dest[0].agents)
            dest[0].quantity=999
            state.ApplyModificationsResults([source,object()],dest,None,object())
            self.assertFalse(state.m_HCOutputReady);self.assertTrue(outputs[0].deleted)

    def test_all_definitions_registered_once_and_belt_retired(self):
        source=(SRC/'HCRecipeRegistration.c').read_text()
        for name in FAMILIES:self.assertEqual(1,source.count('RegisterRecipe(new '+name+');'))
        self.assertNotIn('HCSalvageLeatherBelt',source)

    def test_actual_family_initializers_register_exact_sources_tools_yields_and_costs(self):
        tools=tool_policy();sources=source_policy()
        env={'HCSalvageTools':tools,'HCSalvageSources':sources,'MAX_NUMBER_OF_INGREDIENTS':2}
        configure=authored('Configure','label,inputType,toolType,outputType,quantity,wear,animationUnits',env)
        extra=authored('AddRecoveryResult','outputType,quantity',env)
        for name,(expected_sources,seed,outputs,wear,animation,ruined) in FAMILIES.items():
            state=configured(seed);state.m_Ingredients=[NativeArray(),NativeArray()]
            state.m_NumberOfResults=0;state.m_ItemsToCreate=[];state.m_HCRuinedOnly=False
            def add_result(kind):
                state.m_ItemsToCreate.append(kind);state.m_NumberOfResults+=1
            state.AddResult=add_result
            state.Configure=lambda *args:configure(state,*args)
            state.AddRecoveryResult=lambda *args:extra(state,*args)
            init=authored('Init','',env,owner=name);init(state)
            self.assertEqual(expected_sources,state.m_Ingredients[0])
            self.assertEqual([tools.ToolAt(seed,i) for i in range(tools.ToolCount(seed))],state.m_Ingredients[1])
            self.assertEqual(outputs,list(zip(state.m_ItemsToCreate,state.m_ResultSetQuantity[:state.m_NumberOfResults])))
            self.assertEqual([True,False],state.m_IngredientDestroy)
            self.assertEqual([0,-wear],state.m_IngredientAddHealth)
            self.assertEqual(animation,state.m_AnimationLength)
            self.assertEqual(ruined,state.m_HCRuinedOnly)
            self.assertEqual(4 if ruined else 3,state.m_MaxDamageIngredient[0])

    def test_each_cached_recovery_is_validated_without_constructing_a_fresh_recipe(self):
        from tests.unit.test_crafting_completion import audit_context
        for name in FAMILIES:
            for field,index,value in [('m_ResultSetQuantity',0,999),('m_IngredientDestroy',1,True),
                                      ('m_ResultSetFullQuantity',0,True),('m_ResultReplacesIngredient',0,0),
                                      ('m_ResultInheritsColor',0,0),('m_ResultUseSoftSkills',0,True),
                                      ('m_IngredientAddQuantity',1,1)]:
                with self.subTest(name=name,field=field):
                    cached,names,manager,env=audit_context();self.assertTrue(env['run']())
                    getattr(cached[names[name]],field)[index]=value
                    self.assertFalse(env['run']())
            cached,names,manager,env=audit_context()
            cached[names[name]].m_Ingredients[0][0]+='_Mod'
            self.assertFalse(env['run']())
