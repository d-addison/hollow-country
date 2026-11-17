"""Execute authored salvage bodies with synthetic native boundaries, not DayZ.

Tool identities come from the inspected native cloth/net cutting recipe slots;
the explicit expected list is independent of the authored policy implementation.
"""
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest

try:
    from .test_crafting_completion import body, execute_flat, recipe, PILOTS
    from .test_core_lifecycle import tokens
except ImportError:
    from test_crafting_completion import body, execute_flat, recipe, PILOTS
    from test_core_lifecycle import tokens

SOURCE='HCSalvageRecipe.c'
CUTTING=tuple(sorted(('AK_Bayonet Akinaka BoneKnife BrickTrowel Cleaver CombatKnife '
    'Crowbar CrudeMachete DonerKnife FangeKnife FarmingHoe FieldShovel FirefighterAxe '
    'Hacksaw HandSaw Hatchet HayHook HuntingKnife Iceaxe Jambiya KitchenKnife KukriKnife '
    'M9A1_Bayonet Machete Mosin_Bayonet OrientalMachete Pickaxe SKS_Bayonet Scimitar '
    'Screwdriver Shovel Sickle SteakKnife StoneKnife Sword WoodAxe').split()))


class NativeArray(list):
    def __bool__(self): return True
    def Count(self): return len(self)
    def Insert(self,value): self.append(value)
    def Clear(self): self.clear()


class SyntheticItem:
    def __init__(self,kind,owner,health=6):
        self.kind,self.owner,self.health=kind,owner,health
        self.deleted,self.ruined=False,False
        self.inventory=NS(IsAttachment=lambda:False,AttachmentCount=lambda:0,GetCargo=lambda:None)
    def GetType(self):return self.kind
    def GetHealth(self,*args):return self.health
    def GetHealth01(self,*args):return self.health/100
    def IsKindOf(self,kind):return self.kind==kind
    def IsRuined(self):return self.ruined
    def IsSetForDeletion(self):return self.deleted
    def GetInventory(self):return self.inventory
    def GetHierarchyRootPlayer(self):return self.owner


def authored(name,params,context,filename=SOURCE,owner=None):
    """Translate control syntax only; native operations remain explicit adapters."""
    code=re.sub(r'//[^\n]*','',body(filename,name,owner))
    def expr(value):
        value=re.sub(r'array<ItemBase>\s+(\w+)\s*=\s*new array<ItemBase>', r'\1 = NativeArray()',value)
        value=re.sub(r'\b(?:int|float|bool|string|CargoBase|ItemBase|EntityAI|TrapBase)\s+(?=\w+\s*=)','',value)
        value=re.sub(r'(?<![\w.])m_\w+\b',lambda m:'self.'+m[0],value)
        value=value.replace('super.','self.native.')
        value=re.sub(r'(?<![\w.])IsOwnedEmptyLooseItem\(', 'self.IsOwnedEmptyLooseItem(',value)
        for name in ('InsertIngredient','AddResult','Configure','AddRecoveryResult','IsSourceConditionValid','OutputsMatch','DiscardOutputs','HCValidDrysack','ClassName','HCIsScoped','CheckRecipe','SpawnItems','ApplyModificationsResults','ApplyModificationsIngredients','Do','DeleleIngredientsPass'):
            value=re.sub(r'(?<![\w.])'+name+r'\(','self.'+name+'(',value)
        value=value.replace('&&',' and ').replace('||',' or ')
        value=re.sub(r'!(?!=)','not ',value)
        for old,new in (('true','True'),('false','False'),('null','None')):
            value=re.sub(r'\b'+old+r'\b',new,value)
        return value
    lines=[];indent=1
    for token in tokens(code):
        if token=='{':indent+=1;continue
        if token=='}':indent-=1;continue
        loop=re.fullmatch(r'for \(int (\w+) = 0; \1 < (.*); \1\+\+\)',token,re.S)
        if loop: line='for '+loop[1]+' in range('+expr(loop[2])+'):'
        elif token.startswith('if ('):
            depth=1;end=4
            while depth:
                depth+=(token[end]=='(')-(token[end]==')');end+=1
            line='if '+expr(token[4:end-1])+': '+expr(token[end:].strip())
        elif token=='else':line='else:'
        else:line=expr(token)
        lines.append('    '*indent+line.replace('\n',' '))
    exec(compile('def actual(self,'+params+'):\n'+'\n'.join(lines),
                 'authored-salvage:'+name,'exec'),context)
    return context['actual']


def tool_policy(game=None):
    policy=NS();context={'HCSalvageTools':policy,'GetGame':lambda:game}
    for name,params in (('ToolCount','seed'),('ToolAt','seed,index'),
                        ('Allows','seed,actualType'),('CheckRegistered','tools,seed')):
        method=authored(name,params,context)
        setattr(policy,name,lambda *a,fn=method:fn(None,*a))
        context[name]=getattr(policy,name)
    return policy


def configured(seed='KitchenKnife'):
    fields=('MinDamageIngredient MaxDamageIngredient MinQuantityIngredient MaxQuantityIngredient '
            'IngredientAddHealth IngredientSetHealth IngredientAddQuantity IngredientDestroy '
            'IngredientUseSoftSkills ResultSetFullQuantity ResultSetQuantity ResultSetHealth '
            'ResultInheritsHealth ResultInheritsColor ResultToInventory ResultUseSoftSkills '
            'ResultReplacesIngredient').split()
    state=NS(**{'m_'+name:[None,None] for name in fields})
    state.m_Ingredients=[NativeArray(),NativeArray()];state.results=[]
    state.InsertIngredient=lambda slot,kind:state.m_Ingredients[slot].Insert(kind)
    state.AddResult=state.results.append
    # No policy implementation is supplied before it exists: the RED executes
    # the original Configure rather than testing for source text or a new symbol.
    try: policy=tool_policy()
    except AssertionError: policy=None
    from tests.unit.test_crafting_families import source_policy
    env={'MAX_NUMBER_OF_INGREDIENTS':2,'HCSalvageTools':policy,'HCSalvageSources':source_policy()}
    authored('Configure','label,inputType,toolType,outputType,quantity,wear,animationUnits',env)(
        state,'synthetic','CamoNet',seed,'Netting',2,5,2)
    return state


class SalvageToolsTests(unittest.TestCase):
    def test_registration_contains_every_proven_native_cutting_type_once(self):
        state=configured()
        self.assertEqual(set(state.m_Ingredients[1]),set(CUTTING))
        self.assertEqual(len(state.m_Ingredients[1]),len(CUTTING))
        self.assertEqual(state.m_Ingredients[0],['CamoNet'])

    def test_wire_salvage_keeps_pliers_and_no_cutting_substitution(self):
        self.assertEqual(configured('Pliers').m_Ingredients[1],['Pliers'])
        policy=tool_policy()
        self.assertEqual(policy.ToolCount('Pliers'),1)
        for kind in CUTTING:self.assertFalse(policy.Allows('Pliers',kind))
        self.assertTrue(policy.Allows('Pliers','Pliers'))

    def test_unsupported_seed_and_tool_names_never_expand_acceptance(self):
        policy=tool_policy()
        for seed in ('','Inventory_Base','Unknown','kitchenknife'):
            self.assertEqual(policy.ToolCount(seed),0)
            self.assertFalse(policy.Allows(seed,'KitchenKnife'))
        for kind in ('Pliers','Rag','Jambiya;','KitchenKnife_Mod','kitchenknife',''):
            self.assertFalse(policy.Allows('KitchenKnife',kind))
        for index in (-1,36,2147483647):self.assertEqual(policy.ToolAt('KitchenKnife',index),'')

    def test_cached_native_registration_requires_exact_complete_validated_tool_set(self):
        game=NS(ConfigIsExisting=lambda path:True)
        policy=tool_policy(game)
        valid=NativeArray(policy.ToolAt('KitchenKnife',i) for i in range(36))
        self.assertTrue(policy.CheckRegistered(valid,'KitchenKnife'))
        for bad in (None,NativeArray(),NativeArray(['KitchenKnife']),
                    NativeArray(valid+['Pliers']),NativeArray(reversed(valid)),
                    NativeArray([valid[0]]*36)):
            self.assertFalse(policy.CheckRegistered(bad,'KitchenKnife'))
        game.ConfigIsExisting=lambda path:not path.endswith(' BoneKnife')
        self.assertFalse(policy.CheckRegistered(valid,'KitchenKnife'))

    def test_configure_preserves_tool_entity_mutation_and_material_output_contract(self):
        state=configured()
        self.assertEqual(state.m_IngredientDestroy,[True,False])
        self.assertEqual(state.m_IngredientAddHealth,[0,-5])
        self.assertEqual(state.m_IngredientAddQuantity,[0,0])
        self.assertEqual(state.m_ResultInheritsHealth[0],0)
        self.assertEqual(state.m_ResultReplacesIngredient[0],-1)
        self.assertEqual(state.results,['Netting'])
        self.assertEqual(state.m_ResultSetQuantity[0],2)

    def test_completion_checks_original_tool_identity_type_health_and_ownership(self):
        policy=None
        try:policy=tool_policy()
        except AssertionError:pass
        player=NS(IsAlive=lambda:True,IsUnconscious=lambda:False)
        from tests.unit.test_crafting_families import source_policy
        env={'HCSalvageTools':policy,'HCSalvageSources':source_policy(),'HCCraftingGate':NS(CanPreviewOrCraft=lambda:True)}
        state=configured();state.native=NS(CanDo=lambda items,who:True)
        owned=authored('IsOwnedEmptyLooseItem','item,player',env)
        state.IsOwnedEmptyLooseItem=lambda item,who:owned(state,item,who)
        state.IsSourceConditionValid=lambda item:not item.IsRuined()
        call=authored('CanDo','ingredients,player',env)
        material=SyntheticItem('CamoNet',player,50)
        for kind in CUTTING:
            tool=SyntheticItem(kind,player)
            pair=[material,tool]
            self.assertTrue(call(state,pair,player),kind)
            self.assertIs(pair[1],tool)
            tool.health=5
            self.assertFalse(call(state,pair,player))
            tool.health=6;tool.owner=object()
            self.assertFalse(call(state,pair,player))
            tool.owner=player;tool.deleted=True
            self.assertFalse(call(state,pair,player))

    def test_native_completion_delegates_original_handles_only_after_output_exists(self):
        player=object(); state=configured(); calls=[]
        state.native=NS(ApplyModificationsIngredients=lambda pair,who:calls.append((pair,who)))
        call=authored('ApplyModificationsIngredients','sorted,player',{})
        for kind in CUTTING:
            pair=[SyntheticItem('CamoNet',player,50),SyntheticItem(kind,player)]
            state.m_HCOutputReady=False;before=len(calls)
            call(state,pair,player);self.assertEqual(len(calls),before)
            state.m_HCOutputReady=True;call(state,pair,player)
            self.assertIs(calls[-1][0],pair)
            self.assertIs(calls[-1][0][1],pair[1])
            self.assertIs(calls[-1][1],player)

    def test_actual_startup_audit_rejects_missing_extra_duplicate_or_reordered_cached_tools(self):
        try: from .test_crafting_completion import audit_context
        except ImportError: from test_crafting_completion import audit_context
        for mutation in ('missing','extra','duplicate','reordered'):
            cached,_,_,context=audit_context()
            self.assertTrue(context['run']())
            tools=cached[0].m_Ingredients[1]
            if mutation=='missing':tools.pop()
            if mutation=='extra':tools.append('Pliers')
            if mutation=='duplicate':tools[-1]=tools[0]
            if mutation=='reordered':tools.reverse()
            self.assertFalse(context['run'](),mutation)


if __name__=='__main__':unittest.main()
