"""#160 burn-down for the crafting, wreck-salvage and ecology-start refusals.

Authored bodies run through the established syntax-only translators with explicit
synthetic ports. Offline tests never establish DayZ behaviour; runtime acceptance
stays pending.

RED: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_craft_burn -v
GREEN: same command (recorded in the commit body).
"""
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_ecology_runtime import environment as ecology_environment, translated
from tests.unit.test_event_runtime import EArray, translate as event_translate
from tests.unit.test_salvage_tools import authored

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'mods/HollowCountry/scripts/4_World'
WRECK = SCRIPTS / 'Vehicles/HCWreckSalvage.c'
ECOLOGY = SCRIPTS / 'Ecology/HCEcologyRuntime.c'
REFUSAL = NS(BUSY='busy', SERVICE='service', SALVAGE='salvage_unavailable', CAPACITY='capacity',
             SESSION='session_changed', STORAGE='storage_unavailable', NOTHING='nothing')
ACTION = SCRIPTS / 'Actions/HCActionSalvageWreck.c'


def selfref(**fields):
    # The syntax-only translator rewrites `data.m_Player` to `data.self.m_Player`.
    item = NS(**fields)
    item.self = item
    return item


class CraftRefusalVocabulary(unittest.TestCase):
    def test_refuse_names_the_reason_to_the_bounded_player_reporter(self):
        told = []
        env = dict(HCRefusal=REFUSAL, HCRefusalReport=NS(
            RefusalMessage=lambda player, reason, subject, text: told.append((reason, text)) or True,
            ActionRefusalMessage=lambda data, reason, text: told.append((reason, text))))
        env['HCCraftRefusal'] = NS(INPUTS='craft_inputs_invalid', OUTPUT='craft_output_unavailable')
        message = authored('Message', 'reason', env, 'HCNativeCraftingSafety.c', 'HCCraftRefusal')
        env['HCCraftRefusal'].Message = lambda reason: message(None, reason)
        refuse = authored('Refuse', 'player,subject,reason', env, 'HCNativeCraftingSafety.c', 'HCCraftRefusal')
        refuse(None, object(), object(), 'busy')
        refuse(None, object(), object(), 'craft_output_unavailable')
        action = authored('ActionRefuse', 'data,reason', env, 'HCNativeCraftingSafety.c', 'HCCraftRefusal')
        action(None, object(), 'craft_inputs_invalid')
        self.assertEqual(['busy', 'craft_output_unavailable', 'craft_inputs_invalid'], [r for r, _ in told])
        self.assertTrue(all(text for _, text in told))


    def test_wreck_message_is_specific_per_module_reason_and_never_empty(self):
        env = dict(HCRefusal=REFUSAL, HCCraftRefusal=NS(),
                   HCWreckSalvageModule=NS(HC_TABLE_FULL='wreck_table_full',
                                           HC_SAVE_FAILED='wreck_journal_save_failed'))
        message = authored('WreckMessage', 'reason', env, 'HCNativeCraftingSafety.c', 'HCCraftRefusal')
        texts = {r: message(None, r) for r in ('busy', 'capacity', 'service', 'session_changed', 'nothing',
                                               'storage_unavailable', 'salvage_unavailable', 'unknown',
                                               'wreck_table_full', 'wreck_journal_save_failed')}
        self.assertEqual(texts['busy'], texts['capacity'])
        self.assertEqual(8, len(set(texts.values())))  # busy/capacity share; salvage/unknown share
        self.assertEqual(texts['salvage_unavailable'], texts['unknown'])
        self.assertTrue(all(texts.values()))


class DrysackRefusals(unittest.TestCase):
    def run_finish(self, finishing, valid):
        told = []
        env = dict(GetGame=lambda: NS(IsServer=lambda: True), HCRefusal=REFUSAL,
                   HCCraftRefusal=NS(INPUTS='craft_inputs_invalid',
                                     ActionRefuse=lambda data, reason: told.append(reason)))
        call = authored('OnFinishProgressServer', 'action_data', env, 'HCDrysackSafety.c')
        state = NS(m_HCFinishing=finishing, HCValidDrysack=lambda item, player: valid)
        call(state, NS(m_MainItem=object(), m_Player=object()))
        return told

    def test_reentry_and_invalid_source_are_named(self):
        self.assertEqual(['busy'], self.run_finish(True, True))
        self.assertEqual(['craft_inputs_invalid'], self.run_finish(False, False))


class DrysackOutputRefusal(unittest.TestCase):
    def run_finish(self, bag_state, rope_state):
        """Each state is None (allocation failed), 'fresh' or 'deleting' (deferred delete)."""
        told, events = [], []

        def result(label, mode):
            if mode is None:
                return None
            return NS(IsSetForDeletion=lambda: mode == 'deleting',
                      Delete=lambda: events.append(label + '_deleted'),
                      SetWet=lambda wet: events.append(label + '_wet'))
        spawned = {'WaterproofBag_Green': result('bag', bag_state), 'Rope': result('rope', rope_state)}
        player = NS(SpawnEntityOnGroundRaycastDispersed=lambda kind: spawned[kind])
        source = NS(ConfigGetString=lambda key: 'Green', Delete=lambda: events.append('source_deleted'),
                    GetWet=lambda: 0.0)
        env = dict(GetGame=lambda: NS(IsServer=lambda: True), HCRefusal=REFUSAL,
                   MiscGameplayFunctions=NS(TransferItemProperties=lambda *a: events.append('transfer')),
                   HCCraftRefusal=NS(INPUTS='craft_inputs_invalid', OUTPUT='craft_output_unavailable',
                                     ActionRefuse=lambda data, reason: told.append(reason)))
        call = authored('OnFinishProgressServer', 'action_data', env, 'HCDrysackSafety.c')
        state = NS(m_HCFinishing=False, HCValidDrysack=lambda item, player_: True)
        call(state, NS(m_MainItem=source, m_Player=player))
        return told, events, state

    def test_failed_allocation_deletes_only_fresh_results_and_keeps_the_source(self):
        # Spawn order is bag then rope; a missing rope must clean the fresh bag only.
        told, events, state = self.run_finish('fresh', None)
        self.assertEqual(['craft_output_unavailable'], told)
        self.assertEqual(['bag_deleted'], events)
        self.assertFalse(state.m_HCFinishing)

    def test_deferred_deleting_results_are_refused_and_both_deleted(self):
        told, events, state = self.run_finish('fresh', 'deleting')
        self.assertEqual(['craft_output_unavailable'], told)
        self.assertEqual(['bag_deleted', 'rope_deleted'], events)
        self.assertFalse(state.m_HCFinishing)

    def test_fresh_results_commit_without_a_refusal(self):
        told, events, state = self.run_finish('fresh', 'fresh')
        self.assertEqual([], told)
        self.assertEqual(['transfer', 'transfer', 'bag_wet', 'rope_wet', 'source_deleted'], events)
        self.assertFalse(state.m_HCFinishing)


class NativeRecipeRefusals(unittest.TestCase):
    def run_perform(self, guard):
        told = []
        env = dict(HCRefusal=REFUSAL, GetGame=lambda: NS(IsServer=lambda: True),
                   HCCraftRefusal=NS(Refuse=lambda player, subject, reason: told.append(reason)))
        state = NS(HCIsScoped=lambda: True, m_HCNativeCommitGuard=guard)
        authored('PerformRecipe', 'item1,item2,player', env, 'HCNativeCraftingSafety.c', 'RecipeBase')(
            state, object(), object(), object())
        return told

    def test_missing_guard_and_reentry_are_named(self):
        self.assertEqual(['service'], self.run_perform(None))
        self.assertEqual(['busy'], self.run_perform(NS(TryEnter=lambda: False, Release=lambda: None)))


class SalvageRecipeRefusals(unittest.TestCase):
    def env(self, told):
        return dict(HCRefusal=REFUSAL, GetGame=lambda: NS(IsServer=lambda: True),
                    HCCraftRefusal=NS(Refuse=lambda player, subject, reason: told.append(reason)))

    def test_busy_commit_is_named_and_native_is_not_called(self):
        told, events = [], []
        state = NS(m_HCOutputReady=True, native=NS(PerformRecipe=lambda *a: events.append('native')),
                   m_HCCommitGuard=NS(TryEnter=lambda: False, Release=lambda: events.append('release')))
        authored('PerformRecipe', 'item1,item2,player', self.env(told))(state, object(), object(), object())
        self.assertEqual(['busy'], told)
        self.assertEqual([], events)

    def test_unavailable_output_stops_both_mutations_with_one_reason_that_is_reported(self):
        for method, params in (('ApplyModificationsResults', 'sorted,results,result,player'),
                               ('ApplyModificationsIngredients', 'sorted,player')):
            state = NS(m_HCOutputReady=False, m_HCRefusal='', native=NS(
                ApplyModificationsResults=lambda *a: self.fail('mutated'),
                ApplyModificationsIngredients=lambda *a: self.fail('mutated')))
            call = authored(method, params, self.env([]))
            call(state, *([None] * len(params.split(','))))
            self.assertEqual('salvage_unavailable', state.m_HCRefusal, method)
        told = []
        state = NS(m_HCOutputReady=True, m_HCRefusal='stale', m_HCCommitGuard=NS(
            TryEnter=lambda: True, Release=lambda: None))
        state.native = NS(PerformRecipe=lambda *a: setattr(state, 'm_HCRefusal', 'salvage_unavailable'))
        authored('PerformRecipe', 'item1,item2,player', self.env(told))(state, object(), object(), object())
        self.assertEqual(['salvage_unavailable'], told)
        told.clear()
        state.native = NS(PerformRecipe=lambda *a: None)
        authored('PerformRecipe', 'item1,item2,player', self.env(told))(state, object(), object(), object())
        self.assertEqual([], told, 'a completed or CheckRecipe-refused recipe adds no output refusal')


class WreckSalvageRefusals(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.env = dict(Print=self.logs.append, HCRefusal=REFUSAL, GetGame=lambda: NS(
            IsServer=lambda: True, GetTime=lambda: 1000), HCWreckSalvage=NS(
                Allowed=lambda *a: True, Key=lambda *a: 'key'))
        self.text = WRECK.read_text()

    def module(self, **kw):
        module = NS(m_Active=True, m_Busy=False, m_HCStartRefusal='', m_HCBeginRefusal='',
                    m_Sessions=EArray(), m_State=NS(Rows=[NS(Left=2)]), Enroll=lambda target: 0,
                    m_HCEnrollRefusal='', Purge=lambda: None, **kw)
        for name in ('HCRefuseStart', 'HCRefuseBegin', 'HCEnrollReason'):
            try:
                fn = event_translate(self.text, name, self.env, 'HCWreckSalvageModule', True)
            except AssertionError:
                fn = (lambda self_, reason: self.fail('missing ' + name))
            setattr(module, name, (lambda f: lambda *args: f(module, *args))(fn))
        return module

    def can_start(self, module, player):
        call = event_translate(self.text, 'CanStart', self.env, 'HCWreckSalvageModule', True)
        return call(module, player, NS(GetObject=lambda: object()), object())

    def test_start_refusals_log_each_reason_once_until_it_changes_or_clears(self):
        player = NS(GetIdentity=lambda: object())
        module = self.module()
        module.m_Active = False
        self.assertFalse(self.can_start(module, player))
        self.assertFalse(self.can_start(module, player))
        self.assertEqual(1, len([l for l in self.logs if 'reason=service' in l]), self.logs)
        module.m_Active, module.m_Busy = True, True
        self.assertFalse(self.can_start(module, player))
        self.assertEqual(1, len([l for l in self.logs if 'reason=busy' in l]), self.logs)
        module.m_Busy = False
        self.assertFalse(self.can_start(module, NS(GetIdentity=lambda: None)))
        self.assertEqual(1, len([l for l in self.logs if 'reason=session_changed' in l]), self.logs)
        self.env['HCWreckSalvage'].Allowed = lambda *a: False
        self.assertFalse(self.can_start(module, player))
        self.assertEqual(1, len([l for l in self.logs if 'reason=salvage_unavailable' in l]), self.logs)
        self.env['HCWreckSalvage'].Allowed = lambda *a: True
        self.assertTrue(self.can_start(module, player))
        self.assertEqual('', module.m_HCStartRefusal)

    def test_begin_names_capacity_and_duplicate_sessions(self):
        def begin(module, data):
            return event_translate(self.text, 'Begin', self.env, 'HCWreckSalvageModule', True)(module, data)
        player = NS(GetIdentity=lambda: object())
        data = selfref(Completed=False, m_Player=player, m_Target=NS(GetObject=lambda: NS(
            GetType=lambda: 'Wreck', GetPosition=lambda: [0, 0, 0])), m_MainItem=object(), Key='', Index=-1)
        module = self.module()
        module.CanStart = lambda p, t, i: True
        module.m_Sessions = EArray([selfref(Key='other', m_Player=object())] * 16)
        begin(module, data)
        self.assertEqual('capacity', module.m_HCBeginRefusal)
        module.m_Sessions = EArray([selfref(Key='key', m_Player=object())])
        begin(module, data)
        self.assertEqual('busy', module.m_HCBeginRefusal)
        module.CanStart = lambda p, t, i: False
        begin(module, data)
        self.assertEqual('salvage_unavailable', module.m_HCBeginRefusal)
        self.assertEqual(3, len([l for l in self.logs if 'begin refused reason=' in l]), self.logs)
        begin(module, data)
        self.assertEqual(3, len([l for l in self.logs if 'begin refused reason=' in l]), 'once per change')


    def test_enroll_failure_after_admission_is_named_and_adds_no_session(self):
        player = NS(GetIdentity=lambda: object())
        data = selfref(Completed=False, m_Player=player, m_Target=NS(GetObject=lambda: NS(
            GetType=lambda: 'Wreck', GetPosition=lambda: [0, 0, 0])), m_MainItem=object(), Key='', Index=-1)
        module = self.module()
        module.CanStart = lambda p, t, i: True
        module.Enroll = lambda target: -1
        event_translate(self.text, 'Begin', self.env, 'HCWreckSalvageModule', True)(module, data)
        self.assertEqual('storage_unavailable', module.m_HCBeginRefusal)
        self.assertEqual(0, len(module.m_Sessions))
        self.assertEqual(1, len([l for l in self.logs if 'reason=storage_unavailable' in l]), self.logs)

    def test_can_start_names_an_exhausted_or_unenrollable_wreck(self):
        player = NS(GetIdentity=lambda: object())
        module = self.module()
        module.m_State = NS(Rows=[NS(Left=0)])
        self.assertFalse(self.can_start(module, player))
        self.assertEqual('nothing', module.m_HCStartRefusal)
        module.Enroll = lambda target: -1
        self.assertFalse(self.can_start(module, player))
        self.assertEqual('storage_unavailable', module.m_HCStartRefusal)

    def test_last_refusal_prefers_the_specific_begin_reason_then_the_start_reason(self):
        module = self.module()
        getter = event_translate(self.text, 'LastRefusal', self.env, 'HCWreckSalvageModule', True)
        start = event_translate(self.text, 'StartRefusal', self.env, 'HCWreckSalvageModule', True)
        self.assertEqual('salvage_unavailable', getter(module))
        module.m_HCStartRefusal = 'busy'
        self.assertEqual('busy', start(module))
        self.assertEqual('busy', getter(module))
        module.m_HCBeginRefusal = 'salvage_unavailable'
        self.assertEqual('busy', getter(module), 'the generic begin marker defers to the start cause')
        module.m_HCBeginRefusal = 'capacity'
        self.assertEqual('capacity', getter(module))


class WreckActionReports(unittest.TestCase):
    def setUp(self):
        self.told = []
        self.module = NS(Begin=lambda data: None, Continuing=lambda data: False,
                         LastRefusal=lambda: 'capacity', StartRefusal=lambda: 'busy',
                         CanStart=lambda p, t, i: False)
        data = NS(Completed=False)
        self.data = data
        wreck_data = NS(Cast=lambda action: data)
        self.env = dict(GetGame=lambda: NS(IsServer=lambda: True), HCRefusal=REFUSAL,
                        HCWreckSalvageModule=NS(Get=lambda: self.module), HCWreckSalvageActionData=wreck_data,
                        HCCraftRefusal=NS(WreckAction=lambda d, reason: self.told.append(('action', reason)),
                                          WreckTarget=lambda p, t, i, reason: self.told.append(('target', reason))))
        # Syntax-only adapter: the translator has no typed-local support for HC classes.
        self.text = re.sub(r'\bHCWreckSalvage(?:Module|ActionData) (\w+) =', r'\1 =', ACTION.read_text()).replace('super.', 'self.native.')

    def call(self, name, params, *args):
        fn = event_translate(self.text, name, self.env, 'HCActionSalvageWreck', True)
        return fn(NS(native=NS(OnStartServer=lambda a: None)), *args)

    def test_start_refusal_reports_the_modules_specific_reason(self):
        self.call('OnStartServer', 'action_data', object())
        self.assertEqual([('action', 'capacity')], self.told)

    def test_missing_module_keeps_the_generic_reason_and_condition_reports_start_reason(self):
        self.module = None
        self.env['HCWreckSalvageModule'] = NS(Get=lambda: None)
        self.call('OnStartServer', 'action_data', object())
        self.assertEqual([('action', 'salvage_unavailable')], self.told)
        self.told.clear()
        self.module = NS(CanStart=lambda p, t, i: False, StartRefusal=lambda: 'busy')
        self.env['HCWreckSalvageModule'] = NS(Get=lambda: self.module)
        self.assertFalse(self.call('ActionCondition', 'player,target,item', object(), object(), object()))
        self.assertEqual([('target', 'busy')], self.told)


class EcologyStartRefusals(unittest.TestCase):
    def setUp(self):
        self.e = ecology_environment()
        self.logs = []
        self.e['Print'] = self.logs.append
        self.e['GetGame'] = lambda: NS(GetWorldName=lambda: 'chernarusplus', GetTime=lambda: 5000)
        self.authority = True
        self.e['HCEcologyNative'] = NS(Authority=lambda: self.authority)
        self.source = ECOLOGY.read_text().replace(
            'JsonFileLoader<HCEcologyRuntimeSettings>', 'HCEcologySettingsCodec')

    def runtime(self, **kw):
        fields = dict(m_Running=False, m_Session='session-a', m_SaveMaxTicks=0, m_StartRefusal='')
        fields.update(kw)
        return NS(**fields)

    def begin(self, runtime, world='chernarusplus', session='session-b'):
        call = translated(self.source, 'Begin', self.e, 'HCEcologyRuntime', True)
        return call(runtime, None, world, session)

    def test_every_admission_gate_sets_one_stable_reason(self):
        for kwargs, world, session, expected in (
                (dict(m_Running=True), 'chernarusplus', 'session-b', 'already_running'),
                ({}, 'chernarusplus', 'session-a', 'session_reused'),
                ({}, 'otherworld', 'session-b', 'world_mismatch')):
            runtime = self.runtime(**kwargs)
            self.assertFalse(self.begin(runtime, world, session))
            self.assertEqual(expected, runtime.m_StartRefusal)
        self.authority = False
        runtime = self.runtime()
        self.assertFalse(self.begin(runtime))
        self.assertEqual('authority_required', runtime.m_StartRefusal)
        self.authority = True
        rules = self.e['HCEcologyRuntimeRules']
        rules.Token = lambda value: False
        runtime = self.runtime()
        self.assertFalse(self.begin(runtime))
        self.assertEqual('invalid_token', runtime.m_StartRefusal)
        rules.Token = lambda value: True
        rules.ClockValid = lambda now: False
        runtime = self.runtime()
        self.assertFalse(self.begin(runtime))
        self.assertEqual('clock_invalid', runtime.m_StartRefusal)

    def test_start_reports_the_begin_reason_instead_of_a_generic_one(self):
        runtime = self.runtime(m_StartupMaxTicks=0, Begin=lambda *a: False, Finish=lambda: None)
        runtime.m_StartRefusal = 'world_mismatch'
        self.e['HCEcologyRuntime'] = NS(Instance=lambda: runtime)
        start = translated(self.source, 'Start', self.e, 'HCEcologyRuntime')
        self.assertFalse(start(None, 'chernarusplus', 'session-b'))
        self.assertEqual(1, len([l for l in self.logs if 'reason=world_mismatch' in l]), self.logs)
        self.assertFalse([l for l in self.logs if 'reason=start_admission' in l])


if __name__ == '__main__':
    unittest.main()
