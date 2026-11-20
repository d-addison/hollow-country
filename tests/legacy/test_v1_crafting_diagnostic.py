"""Authored diagnostic control flow, with explicit SYNTHETIC engine adapters.

These tests neither compile Enforce nor qualify native inventory/actions.
"""
from types import SimpleNamespace as NS
import re
import unittest

from tests.legacy.test_crafting_completion import body
from tests.legacy.test_core_lifecycle import tokens
from tests.legacy.test_salvage_tools import NativeArray

FILE = 'HCItemUtilityDiagnostic.c'


def diagnostic(method, params, state, **context):
    code = re.sub(r'//[^\n]*', '', body(FILE, method))
    methods = ('BudgetAllows', 'PollCleanup', 'Stop', 'EnsureActor', 'ObserveMetadata',
               'ObserveObjects', 'RowFits', 'DeletePair', 'DeleteFixtures', 'ValidRequest',
               'SafeConcrete', 'Snapshot', 'ObserveRepairEligibility', 'ObserveAction', 'CanExecute')
    def expr(value):
        value = re.sub(r'\bnew (HCItemUtility\w+)\b', r'\1()', value)
        value = re.sub(r'\b(?:string|RecipeBase) (\w+)$', r'\1 = None', value)
        value = value.replace('.Length()', '.__len__()').replace('.Contains(', '.__contains__(')
        value = re.sub(r'([\w.]+)\.Substring\((\w+), 1\)', r'\1[\2:\2+1]', value)
        value = value.replace('GetGame().ConfigGetBaseName(request.ConfigRoot + " " + current, ancestor)',
                              '(ancestor := GetGame().ConfigGetBaseName(request.ConfigRoot + " " + current))')
        value = value.replace('JsonFileLoader<HCItemUtilityObservation>.MakeData(row, payload, error, false)',
                              '((payload := Serialize(row)) is not None)')
        value = value.replace('array<Man> players = new array<Man>', 'players = NativeArray()')
        value = re.sub(r'\b(?:int|float|bool|string|ItemBase|EntityAI|Object|RecipeBase|PluginRepairing|CargoBase|Magazine|PlayerBase|PluginRecipesManager|typename|HCItemUtilityState|HCItemUtilitySummary)\s+(?=\w+\s*=)', '', value)
        value = re.sub(r'(?<![\w.])m_\w+', lambda m: 'self.' + m[0], value)
        value = re.sub(r'(?<![\w.])s_Active\b', 'self.s_Active', value)
        for name in methods:
            value = re.sub(r'(?<![\w.])' + name + r'\(', 'self.' + name + '(', value)
        value = re.sub(r'([\w.]+)\+\+', r'\1 += 1', value)
        value = value.replace('&&', ' and ').replace('||', ' or ')
        value = re.sub(r'!(?!=)', 'not ', value)
        for old, new in (('true', 'True'), ('false', 'False'), ('null', 'None')):
            value = re.sub(r'\b' + old + r'\b', new, value)
        return value
    lines, indent = [], 1
    for token in tokens(code):
        if token == '{': indent += 1; continue
        if token == '}': indent -= 1; continue
        loop = re.fullmatch(r'for \(int (\w+) = 0; \1 < (.*); \1\+\+\)', token, re.S)
        if loop: line = 'for ' + loop[1] + ' in range(' + expr(loop[2]) + '):'
        elif token.startswith('if ('):
            depth, end = 1, 4
            while depth:
                depth += (token[end] == '(') - (token[end] == ')'); end += 1
            line = 'if ' + expr(token[4:end-1]) + ': ' + expr(token[end:].strip())
        elif token == 'else': line = 'else:'
        else: line = expr(token)
        lines.append('    ' * indent + line.replace('\n', ' '))
    exec(compile('def actual(self,' + params + '):\n' + '\n'.join(lines),
                 'authored-utility-diagnostic:' + method, 'exec'), context)
    return lambda *args: context['actual'](state, *args)


class UtilityDiagnosticTests(unittest.TestCase):
    def test_begin_requires_opt_in_isolation_empty_server_and_bounded_queue(self):
        def start(total=7389, opt_in=True, isolated=True, server=True,
                  players=(), active=False, millis=60000, size=16777216):
            state = NS(s_Active=active, m_Running=False, m_Stopped=False)
            game = NS(IsServer=lambda: server, GetTime=lambda: 42,
                      GetPlayers=lambda result: result.extend(players))
            begin = diagnostic('Begin', 'totalRows,explicitOptIn,isolatedExternalProfileConfirmed,'
                               'fixturePosition,executeRepairs,maxMillis,maxBytes', state,
                               GetGame=lambda: game, NativeArray=NativeArray)
            return begin(total, opt_in, isolated, 'synthetic-position', False, millis, size), state
        accepted, state = start()
        self.assertTrue(accepted)
        self.assertTrue(state.s_Active)
        self.assertEqual(7389, state.m_Total)
        self.assertFalse(state.m_Execute)
        for args in ({'opt_in': False}, {'isolated': False}, {'server': False},
                     {'players': [object()]}, {'active': True}, {'total': 0},
                     {'total': 262145}, {'millis': 60001}, {'size': 131071}):
            with self.subTest(args=args):
                self.assertFalse(start(**args)[0])

    def test_budgets_include_exact_boundaries_and_clock_wrap(self):
        state = NS(m_StartedMs=100, m_MaxMillis=1000, m_Bytes=400, m_MaxBytes=2000)
        allows = diagnostic('BudgetAllows', 'now,rowBytes', state)
        self.assertTrue(allows(1099, 575))
        for now, size in ((1100, 0), (99, 0), (100, 577), (100, -1)):
            self.assertFalse(allows(now, size))

    def test_missing_repair_manager_and_special_routes_are_unknown_not_negative(self):
        state = NS(m_Target=NS(CanBeRepairedByCrafting=lambda: True,
                               CanBeRepairedToPristine=lambda: False), m_Tool=object())
        plugin_type = NS(Cast=lambda value: value)
        for available, kit, allowed in ((False, 0, False), (True, 9, False),
                                        (True, 0, True), (True, 0, False)):
            plugin = NS(CanRepair=lambda tool, target: allowed) if available else None
            row = NS(CanRepairObserved=False, CanRepair=False)
            call = diagnostic('ObserveRepairEligibility', 'kitIndex,row', state,
                              PluginRepairing=plugin_type, GetPlugin=lambda kind: plugin)
            call(kit, row)
            self.assertEqual(available and kit < 9, row.CanRepairObserved)
            self.assertEqual(available and kit < 9 and allowed, row.CanRepair)
            self.assertTrue(row.CanBeRepairedByCrafting)

    def test_complete_kit_and_recipe_family_and_no_fabric_recipe(self):
        kit = diagnostic('KitAt', 'index', None)
        recipe = diagnostic('RecipeAt', 'index', None)
        self.assertEqual(['WeaponCleaningKit', 'SewingKit', 'LeatherSewingKit', 'Whetstone',
                          'DuctTape', 'TireRepairKit', 'ElectronicRepairKit', 'EpoxyPutty',
                          'Blowtorch', 'WoodenPlank', 'Pliers', 'Fabric'], [kit(i) for i in range(12)])
        self.assertEqual({'CleanWeapon', 'RepairWithSewingKit', 'RepairWithLeatherSewingKit',
                          'SharpenMelee', 'RepairWithTape', 'RepairWithTireKit', 'RepairElectric',
                          'RepairEpoxy', 'RepairPlanks', 'RepairWithPliers'},
                         {recipe(i) for i in range(12)} - {''})
        self.assertEqual('', recipe(8))  # fuel/action route, not generic repair
        self.assertEqual('', recipe(11))
        self.assertEqual('', kit(-1)); self.assertEqual('', kit(12))

    def test_only_discovered_zero_result_maintenance_can_execute_on_owned_handles(self):
        actor = NS(IsAlive=lambda: True, IsUnconscious=lambda: False,
                   IsSetForDeletion=lambda: False)
        item = lambda: NS(IsSetForDeletion=lambda: False, GetHierarchyRootPlayer=lambda: actor)
        state = NS(m_Execute=True, m_Actor=actor, m_Target=item(), m_Tool=item())
        call = diagnostic('CanExecute', 'recipe,selected', state)
        recipe = NS(m_NumberOfResults=0)
        self.assertTrue(call(recipe, True))
        state.m_Execute = False
        self.assertFalse(call(recipe, True))
        state.m_Execute = True
        self.assertFalse(call(recipe, False))
        recipe.m_NumberOfResults=1; self.assertFalse(call(recipe, True)); recipe.m_NumberOfResults=0
        state.m_Tool.GetHierarchyRootPlayer=lambda: None; self.assertFalse(call(recipe, True))
        state.m_Tool=item(); state.m_Target.IsSetForDeletion=lambda: True
        self.assertFalse(call(recipe, True))

    def test_dead_unconscious_or_deleting_diagnostic_actor_cannot_execute(self):
        for alive, unconscious, deleting in ((False, False, False), (True, True, False),
                                             (True, False, True)):
            actor = NS(IsAlive=lambda: alive, IsUnconscious=lambda: unconscious,
                       IsSetForDeletion=lambda: deleting)
            item = lambda: NS(IsSetForDeletion=lambda: False, GetHierarchyRootPlayer=lambda: actor)
            state = NS(m_Execute=True, m_Actor=actor, m_Target=item(), m_Tool=item())
            call = diagnostic('CanExecute', 'recipe,selected', state)
            with self.subTest(alive=alive, unconscious=unconscious, deleting=deleting):
                self.assertFalse(call(NS(m_NumberOfResults=0), True))

    def test_cleanup_keeps_exclusivity_until_all_raw_handles_are_invalidated(self):
        state = NS(m_TargetObject=object(), m_ToolObject=object(), m_Target=object(),
                   m_Tool=object(), m_PairDeleting=True, m_Stopped=True, m_Bag=object(),
                   m_ActorObject=object(), m_Actor=object(), m_Running=True, s_Active=True)
        # s_Active is static in Enforce; this adapter supplies its shared slot.
        code = body(FILE, 'PollCleanup').replace('s_Active = false', 'm_StaticActive = false')
        from unittest.mock import patch
        state.m_StaticActive = True
        with patch(__name__ + '.body', return_value=code):
            poll = diagnostic('PollCleanup', '', state)
        self.assertFalse(poll())
        state.m_TargetObject = state.m_ToolObject = None
        self.assertFalse(poll())
        self.assertTrue(state.m_Running)
        self.assertTrue(state.m_StaticActive)
        state.m_Bag = state.m_ActorObject = None
        self.assertTrue(poll())
        self.assertFalse(state.m_Running)
        self.assertFalse(state.m_StaticActive)
        self.assertIsNone(state.m_Target)
        self.assertIsNone(state.m_Tool)

    def test_actions_use_actual_registry_and_report_absence_without_executing(self):
        registered = NS(GetInputType=lambda: 'synthetic-input')
        registry = NS(GetAction=lambda kind: registered)
        state = NS()
        # Translate the Enforce out parameter into a mutable synthetic array.
        code = body(FILE, 'ObserveAction').replace('ActionBase action', 'Object action')
        code = code.replace('array<ActionBase_Basic> actions;', 'Object actions = NativeArray();')
        from unittest.mock import patch
        class ActionArray(NativeArray):
            def Find(self, value):
                return self.index(value) if value in self else -1
        with patch(__name__ + '.body', return_value=code):
            call = diagnostic('ObserveAction', 'item,actionType', state,
                              ActionManagerBase=registry, NativeArray=ActionArray)
        item = NS(GetActions=lambda kind, result: result.Insert(registered))
        self.assertEqual('present-condition-unexecuted', call(item, 'observed-action'))
        item.GetActions=lambda kind, result: None
        self.assertEqual('absent-in-observed-input-map', call(item, 'observed-action'))
        registry.GetAction=lambda kind: None
        self.assertEqual('registry-unavailable-pending', call(item, 'observed-action'))

    def test_replay_row_and_partial_cleanup_cannot_advance_queue(self):
        state = NS(m_Running=True, m_Stopped=False, m_Cursor=0, m_Total=7389,
                   m_Bytes=0, m_PairDeleting=False, m_Emitted=0)
        state.BudgetAllows=lambda now,size: True
        state.PollCleanup=lambda: False
        state.ValidRequest=lambda req: req.Index == state.m_Cursor
        state.ObserveMetadata=lambda req,row: setattr(row, 'Status', 'metadata')
        state.ObserveObjects=lambda req,row: setattr(row, 'Observed', True)
        state.RowFits=lambda row: True
        state.DeletePair=lambda: setattr(state, 'm_PairDeleting', True)
        state.Stop=lambda reason: setattr(state, 'm_Stopped', True)
        row=NS(Captured=False, ByteBound=100)
        step=diagnostic('ObserveNext', 'request,row', state, GetGame=lambda: NS(GetTime=lambda: 0))
        self.assertTrue(step(NS(Index=0),row))
        self.assertEqual(1,state.m_Cursor)
        self.assertFalse(step(NS(Index=0),row))
        self.assertEqual(1,state.m_Cursor)
        self.assertFalse(step(NS(Index=1),NS(Captured=False)))
        self.assertEqual(1,state.m_Cursor)
        self.assertEqual(7389-state.m_Cursor,7388)  # pending is conserved, no sampling

    def test_budget_stop_retains_unobserved_row_and_requests_cleanup(self):
        state = NS(m_Running=True, m_Stopped=False, m_Cursor=5, m_Total=7389,
                   m_PairDeleting=False, BudgetAllows=lambda now,size: False)
        reasons=[];state.Stop=reasons.append
        step=diagnostic('ObserveNext','request,row',state,GetGame=lambda:NS(GetTime=lambda: 10))
        self.assertFalse(step(NS(Index=5),NS(Captured=False)))
        self.assertEqual(['budget-partial'],reasons)
        self.assertEqual(5,state.m_Cursor)

    def test_deletion_request_is_once_and_never_confirmation(self):
        target,tool=object(),object();deleted=[]
        state=NS(m_PairDeleting=False,m_TargetObject=target,m_ToolObject=tool,m_DeleteRequests=0)
        call=diagnostic('DeletePair','',state,GetGame=lambda:NS(ObjectDelete=deleted.append))
        call();call()
        self.assertEqual([target,tool],deleted)
        self.assertEqual(2,state.m_DeleteRequests)
        self.assertIs(target,state.m_TargetObject)
        self.assertTrue(state.m_PairDeleting)



class UtilityDiagnosticGateTests(unittest.TestCase):
    def test_request_identity_charset_size_queue_roots_and_kit_bounds(self):
        state = NS(m_Cursor=2, m_Total=3)
        check = diagnostic('ValidRequest', 'request', state)
        good = dict(Index=2, ItemClass='LeatherHat_Black', KitIndex=0, ConfigRoot='CfgVehicles')
        self.assertTrue(check(NS(**good)))
        self.assertFalse(check(None))
        for field, values in {'Index': (1, 3), 'ItemClass': ('', 'x'*129, 'A B', 'A;B', 'A/B', 'A.B'),
                              'KitIndex': (-2, 12), 'ConfigRoot': ('Other', 'CfgVehicles x')}.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    self.assertFalse(check(NS(**dict(good, **{field:value}))))
        for root in ('CfgVehicles', 'CfgWeapons', 'CfgMagazines', 'CfgAmmo'):
            self.assertTrue(check(NS(**dict(good, ConfigRoot=root, ItemClass='A'*128, KitIndex=11))))
        state.m_Cursor=state.m_Total
        self.assertFalse(check(NS(**dict(good, Index=state.m_Cursor))))

    def test_safe_concrete_is_exact_and_unknown_definitions_stay_pending(self):
        from tests.legacy.test_crafting_families import source_policy
        from tests.legacy.test_salvage_tools import tool_policy
        kit = diagnostic('KitAt', 'index', None)
        check = diagnostic('SafeConcrete', 'root,name', None, KitAt=kit,
                           HCSalvageSources=source_policy(), HCSalvageTools=tool_policy())
        for root, name in [('CfgWeapons','AKM'), ('CfgVehicles','LeatherHat_Black'),
                           ('CfgVehicles','KitchenKnife'), ('CfgVehicles','SewingKit')]:
            self.assertTrue(check(root, name))
        for root, name in [('Other','AKM'), ('CfgAmmo','Bullet_Base'),
                           ('CfgVehicles','Unknown'), ('CfgVehicles','LeatherHat_Black_Mod'),
                           ('CfgWeapons','Unknown'), ('CfgVehicles','LandMineTrap')]:
            with self.subTest(root=root, name=name):self.assertFalse(check(root,name))

    def object_case(self, *, status='metadata-only', ancestry=True, scope=2, kit=0,
                    reviewed=True, safe=True, stale_target=None, stale_tool=None):
        events=[]
        state=NS(m_TargetObject=stale_target, m_ToolObject=stale_tool, m_CreatedObjects=0,
                 SafeConcrete=lambda root,name:safe, EnsureActor=lambda:events.append('actor') or True,
                 Stop=lambda reason:events.append(reason))
        state.m_Actor=NS(GetHumanInventory=lambda:NS(CreateInHands=lambda name:events.append('target') or object()))
        state.m_Bag=NS(GetInventory=lambda:NS(CreateInInventory=lambda name:events.append('tool') or object()))
        row=NS(Status=status, AncestryComplete=ancestry, Scope=scope)
        request=NS(ConfigRoot='CfgVehicles', ItemClass='LeatherHat_Black', KitIndex=kit, CreationReviewed=reviewed)
        call=diagnostic('ObserveObjects','request,row',state,
                        KitAt=diagnostic('KitAt','index',None), RecipeAt=diagnostic('RecipeAt','index',None),
                        ItemBase=NS(Cast=lambda raw:None))
        call(request,row)
        return state,row,events

    def test_object_creation_requires_review_scope_ancestry_and_safe_concrete(self):
        for args in ({'status':'config-missing-pending'}, {'ancestry':False}, {'scope':0},
                     {'scope':1}, {'kit':-1}, {'reviewed':False}, {'safe':False}):
            with self.subTest(args=args):
                state,row,events=self.object_case(**args)
                self.assertEqual([],events)
                self.assertEqual(0,state.m_CreatedObjects)
                self.assertIsNone(state.m_TargetObject)
                self.assertIsNone(state.m_ToolObject)
        state,row,events=self.object_case()
        self.assertEqual(['actor','target','tool'],events)
        self.assertEqual(2,state.m_CreatedObjects)
        self.assertTrue(row.Created)
        self.assertFalse(row.CastSucceeded)  # explicit failed-cast synthetic adapter

    def test_stale_fixture_stops_before_overwriting_either_raw_handle(self):
        for target,tool in ((object(),None),(None,object()),(object(),object())):
            state,row,events=self.object_case(stale_target=target,stale_tool=tool)
            self.assertEqual(['stale-fixture-partial'],events)
            self.assertIs(target,state.m_TargetObject)
            self.assertIs(tool,state.m_ToolObject)
            self.assertEqual(0,state.m_CreatedObjects)

    def test_bag_alone_blocks_cleanup_and_releases_no_exclusivity(self):
        state=NS(m_TargetObject=None,m_ToolObject=None,m_Target=None,m_Tool=None,
                 m_PairDeleting=True,m_Stopped=True,m_Bag=object(),m_ActorObject=None,
                 m_Actor=object(),m_Running=True,s_Active=True)
        poll=diagnostic('PollCleanup','',state)
        self.assertFalse(poll())
        self.assertTrue(state.m_Running)
        self.assertTrue(state.s_Active)
        state.m_Bag=None
        self.assertTrue(poll())
        self.assertFalse(state.m_Running)
        self.assertFalse(state.s_Active)

    def test_summary_completion_requires_full_queue_and_confirmed_cleanup(self):
        for stopped,running,partial,total,complete in ((True,False,False,3,True),
                (True,False,True,3,False),(True,True,False,3,False),
                (False,False,False,3,False),(True,False,False,0,False)):
            state=NS(m_Total=total,m_Emitted=2,m_Cursor=2,m_Bytes=10,m_CreatedObjects=4,
                     m_DeleteRequests=4,m_Stopped=stopped,m_Running=running,
                     m_Partial=partial,m_Reason='synthetic')
            result=diagnostic('Summary','',state,HCItemUtilitySummary=NS)()
            self.assertEqual(complete,result.Complete)
            self.assertEqual(not complete,result.Partial)
            self.assertEqual(total-2,result.Remaining)
            self.assertEqual((2,1034,4,4,'synthetic'),
                             (result.Emitted,result.ByteBound,result.CreatedObjects,result.DeleteRequests,result.Reason))

    def test_stop_records_partial_and_deletes_fixtures_once(self):
        for cursor,partial in ((2,True),(3,False)):
            events=[]
            state=NS(m_Running=True,m_Stopped=False,m_Cursor=cursor,m_Total=3,
                     DeleteFixtures=lambda:events.append('delete'))
            stop=diagnostic('Stop','reason',state)
            stop('synthetic-stop');stop('replay')
            self.assertTrue(state.m_Stopped)
            self.assertEqual(partial,state.m_Partial)
            self.assertEqual('synthetic-stop',state.m_Reason)
            self.assertEqual(['delete'],events)

    def test_final_row_stops_and_replay_cannot_emit(self):
        reasons=[]
        state=NS(m_Running=True,m_Stopped=False,m_Cursor=0,m_Total=1,m_Bytes=0,m_Emitted=0,
                 m_PairDeleting=False,BudgetAllows=lambda *args:True,ValidRequest=lambda req:True,
                 ObserveMetadata=lambda *args:None,ObserveObjects=lambda *args:None,
                 RowFits=lambda row:True,DeletePair=lambda:None)
        def stop(reason):reasons.append(reason);state.m_Stopped=True
        state.Stop=stop
        call=diagnostic('ObserveNext','request,row',state,GetGame=lambda:NS(GetTime=lambda:0))
        self.assertTrue(call(NS(),NS(Captured=False,ByteBound=100)))
        self.assertEqual(['supplied-queue-emitted'],reasons)
        self.assertFalse(call(NS(),NS(Captured=False,ByteBound=100)))
        self.assertEqual(1,state.m_Emitted)

    def test_actor_with_identity_is_rejected_before_bag_creation(self):
        events=[]
        actor=NS(GetIdentity=lambda:object(),IsAlive=lambda:True,
                 GetInventory=lambda:NS(CreateAttachment=lambda kind:events.append('bag') or object()))
        state=NS(m_Actor=None,m_ActorObject=None,m_CreatedObjects=0,m_Position='synthetic')
        call=diagnostic('EnsureActor','',state,PlayerBase=NS(Cast=lambda raw:raw),
                        GetGame=lambda:NS(CreatePlayer=lambda *args:actor))
        self.assertFalse(call())
        self.assertIs(actor,state.m_ActorObject)
        self.assertEqual(1,state.m_CreatedObjects)
        self.assertEqual([],events)
        self.assertFalse(call())  # retained connected actor remains forbidden

    def test_metadata_ancestry_limit_reports_incomplete_without_unbounded_walk(self):
        calls=[]
        def base(path):
            calls.append(path)
            if len(calls)>65:raise AssertionError('unbounded ancestry')
            return 'Parent'+str(len(calls))
        row=NS(Ancestors=FindArray(),RepairableWithKits=NativeArray(),RepairCosts=NativeArray(),
               AncestryComplete=False)
        request=NS(ConfigRoot='CfgVehicles',ItemClass='Synthetic',Index=0)
        game=NS(ConfigIsExisting=lambda path:path=='CfgVehicles Synthetic',ConfigGetBaseName=base)
        diagnostic('ObserveMetadata','request,row',NS(),GetGame=lambda:game)(request,row)
        self.assertEqual(64,len(calls))
        self.assertEqual(64,len(row.Ancestors))
        self.assertFalse(row.AncestryComplete)

    def test_snapshot_zone_limit_is_exact_and_never_claims_truncated_complete(self):
        for count,complete in ((32,True),(33,False)):
            item=NS(IsSetForDeletion=lambda:False,GetHealth01=lambda *args:0.4,
                    HasQuantity=lambda:False,GetQuantity=lambda:0,GetWet=lambda:0,GetAgents=lambda:0,
                    GetInventory=lambda:NS(AttachmentCount=lambda:0,GetCargo=lambda:None),GetCompEM=lambda:None,
                    GetDamageZones=lambda dest:dest.extend('Zone'+str(i) for i in range(count)))
            new_state=lambda:NS(Zones=NativeArray(),ZoneHealth=NativeArray(),ZonesComplete=False)
            result=diagnostic('Snapshot','item',NS(),HCItemUtilityState=new_state,
                              Magazine=NS(Cast=lambda raw:None))(item)
            self.assertEqual(complete,result.ZonesComplete)
            self.assertEqual(count if complete else 0,len(result.Zones))
            self.assertEqual(count if complete else 0,len(result.ZoneHealth))

    def test_serialized_row_limit_includes_boundary_and_failed_serialization(self):
        state=NS(BudgetAllows=lambda now,size:True)
        for payload,accepted in (('x'*16000,True),('x'*16001,False),(None,False)):
            row=NS(ByteBound=0)
            call=diagnostic('RowFits','row',state,Serialize=lambda row:payload,
                            GetGame=lambda:NS(GetTime=lambda:0))
            self.assertEqual(accepted,call(row))
            self.assertEqual(64128 if accepted else 0,row.ByteBound)

    def test_diagnostic_uses_native_config_constants_local_charset_and_diag_gate(self):
        from tests.legacy.test_crafting_completion import SRC
        text=(SRC/FILE).read_text()
        self.assertRegex(text,r'(?m)^#ifdef DIAG_DEVELOPER\s*\nclass HCItemUtilityRequest')
        self.assertTrue(text.rstrip().endswith('#endif'))
        metadata=body(FILE,'ObserveMetadata')
        self.assertIn('== CT_INT',metadata)
        self.assertIn('== CT_ARRAY',metadata)
        self.assertNotRegex(metadata,r'FieldType == [03]|ScopeType == 0')
        self.assertNotRegex(body(FILE,'ValidRequest'),r'"[^"\n]+"\.Contains\(')


class FindArray(NativeArray):
    def Find(self,value):return self.index(value) if value in self else -1


if __name__ == '__main__':
    unittest.main()
