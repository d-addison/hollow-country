"""#160 burn-down for the crafting, wreck-salvage and ecology-start refusals.

Authored bodies run through the established syntax-only translators with explicit
synthetic ports. Offline tests never establish DayZ behaviour; runtime acceptance
stays pending.

RED: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_craft_burn -v
GREEN: same command (recorded in the commit body).
"""
from pathlib import Path
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
             SESSION='session_changed')


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
                    Purge=lambda: None, **kw)
        for name in ('HCRefuseStart', 'HCRefuseBegin'):
            try:
                fn = event_translate(self.text, name, self.env, 'HCWreckSalvageModule', True)
            except AssertionError:
                fn = (lambda self_, reason: self.fail('missing ' + name))
            setattr(module, name, (lambda f: lambda reason: f(module, reason))(fn))
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
