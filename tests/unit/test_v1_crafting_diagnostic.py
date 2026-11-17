"""Authored diagnostic control flow, with explicit SYNTHETIC engine adapters.

These tests neither compile Enforce nor qualify native inventory/actions.
"""
from types import SimpleNamespace as NS
import re
import unittest

from tests.unit.test_crafting_completion import body
from tests.unit.test_core_lifecycle import tokens
from tests.unit.test_salvage_tools import NativeArray

FILE = 'HCItemUtilityDiagnostic.c'


def diagnostic(method, params, state, **context):
    code = re.sub(r'//[^\n]*', '', body(FILE, method))
    methods = ('BudgetAllows', 'PollCleanup', 'Stop', 'EnsureActor', 'ObserveMetadata',
               'ObserveObjects', 'RowFits', 'DeletePair', 'DeleteFixtures', 'ValidRequest')
    def expr(value):
        value = value.replace('array<Man> players = new array<Man>', 'players = NativeArray()')
        value = re.sub(r'\b(?:int|float|bool|string|ItemBase|EntityAI|Object|RecipeBase|PluginRepairing)\s+(?=\w+\s*=)', '', value)
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


if __name__ == '__main__': unittest.main()
