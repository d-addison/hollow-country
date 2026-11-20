"""#198 spec/plan/tasks: retain the existing bounded inventory traversal;
exercise greeting policy, add trade world-owner status derivation, compare receipts.
RED: python3 -B -m unittest tests.legacy.test_w61_trade -v
First differing element 1: (degraded, world_owner_unavailable) vs
(ready, provider_absent_base_only); FAILED (failures=1).
GREEN: same command, Ran 3 tests, OK.
Synthetic handles/flags only; no DayZ inventory, emotes or readiness observed.
Missing provider/pair remains an admitted wait; a lost world owner is a real fault.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.legacy.test_event_runtime import translate
from tests.legacy.test_hc_scavenge import bind
from tests.legacy.test_hc_module_readiness_wave16 import derive, renamed

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / 'mods/HollowCountry/scripts/4_World/World'
ADDON = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World'


def status_port():
    """Execute the authored status publisher too, recording its resulting receipt."""
    source = (ROOT / 'mods/HollowCountry/scripts/3_Game/HCOperationalStatus.c').read_text()
    status = N(m_State='unknown', m_Reason='owner_state_unknown', m_Readiness='unknown')
    for name in ('HCPublish', 'HCState', 'HCReason'):
        method = translate(source, name, {}, member=True)
        setattr(status, name, lambda *args, fn=method: fn(status, *args))
    return status


class TradeReadiness(unittest.TestCase):
    def test_published_off_degraded_ready_fault_and_stop_sequence(self):
        source = renamed((WORLD / 'HCAITrade.c').read_text())
        source = source.replace('JsonFileLoader<HCTradeRecipe>', 'SyntheticJson')
        source = source.replace('HCEncounterStore<HCTradeState>', 'SyntheticStore')
        # Translator maps the native static singleton slot onto this fixture owner.
        source = source.replace('s_Instance', 'm_SyntheticInstance')
        source = source.replace('static HCAITrade m_SyntheticInstance', 'HCAITrade m_SyntheticInstance')
        status = status_port()
        world = [None]
        owner = N(m_Status=status, m_Trade=None, m_StatusReason='',
                  IsEnabled=lambda settings: False, m_SyntheticInstance=None)
        env = dict(HCModuleReadiness=N(HCDerive=derive()),
                   HCWorldModule=N(Get=lambda: world[0]), Print=lambda line: None,
                   s_Provider=None, this=owner,
                   HCTradeReadiness=N(HCTradeReadinessReason=translate(source,
                       'HCTradeReadinessReason', {}, 'HCTradeReadiness')))
        bind(source, 'HCAITrade', owner,
             ('OnStart', 'HCRefreshStatus', 'HCGetOperationalStatus', 'OnStop'), env)
        receipts = []
        def poll():
            reported = owner.HCGetOperationalStatus()
            receipts.append((reported.HCState(), reported.HCReason()))
        owner.OnStart(N())  # Explicit operator opt-out: no native startup/I/O.
        poll()
        # Synthetic successful recipe/journal admission, then world-owner loss.
        state = N(Phase='idle', Refusal='')
        transaction = N(m_Enabled=True, m_Ready=True, m_State=state, m_LogRefusal='')
        transaction.HCClose = lambda: setattr(transaction, 'm_Enabled', False)
        owner.m_Trade = transaction
        owner.HCRefreshStatus()
        poll()
        world[0] = N()  # Existing owner recovers; no verdict is fabricated.
        poll()
        env['s_Provider'] = N(HCReady=lambda: True, HCOperationalFault=lambda: '')
        owner.HCRefreshStatus()
        poll()
        transaction.m_Ready = False
        state.Refusal = 'TRADE_JOURNAL_UNCERTAIN'
        owner.HCRefreshStatus()
        poll()
        world[0] = None  # Real journal refusal must survive world loss too.
        poll()
        owner.OnStop()
        poll()
        self.assertEqual([
            ('off', 'operator_disabled'),
            ('degraded', 'world_owner_unavailable'),
            ('ready', 'provider_absent_base_only'),
            ('ready', 'provider_bound_awaiting_funded_pair'),
            ('refused', 'TRADE_JOURNAL_UNCERTAIN'),
            ('refused', 'TRADE_JOURNAL_UNCERTAIN'),
            ('off', 'stopped'),
        ], receipts)


class ConflictReadiness(unittest.TestCase):
    def test_published_off_degraded_ready_pair_fault_and_stop_sequence(self):
        source = renamed((WORLD / 'HCFactionConflict.c').read_text())
        status = status_port()
        world = [None]
        owner = N(m_Operational=status, m_Healthy=False, m_Refusal='',
                  m_StatusReason='', m_Current=None, m_ProviderLogged=False,
                  HCServiceWorld=lambda: None, HCLog=lambda *args: None)
        env = dict(s_Active=False, s_CombatPort=None,
                   HCWorldModule=N(Get=lambda: world[0]),
                   HCModuleReadiness=N(HCDerive=derive()), Print=lambda line: None,
                   HCConflictReadiness=N(HCConflictReadinessReason=translate(source,
                       'HCConflictReadinessReason', {}, 'HCConflictReadiness')))
        bind(source, 'HCFactionConflict', owner,
             ('HCGetOperationalStatus', 'HCRefreshStatus'), env)
        receipts = []
        def poll():
            reported = owner.HCGetOperationalStatus()
            receipts.append((reported.HCState(), reported.HCReason()))
        poll()
        owner.m_Healthy = True  # Explicit synthetic loaded outcome journal.
        env['s_Active'] = True
        owner.HCRefreshStatus()
        poll()
        world[0] = N()
        poll()
        env['s_CombatPort'] = N()
        owner.HCRefreshStatus()
        poll()
        owner.m_Current = N(Id='synthetic-surveyed-encounter')
        owner.HCRefreshStatus()
        poll()
        owner.m_Healthy, owner.m_Refusal = False, 'OUTCOME_STORE_UNCERTAIN'
        poll()
        owner.m_Refusal, env['s_Active'] = '', False
        poll()
        self.assertEqual([
            ('off', 'not_started_or_disabled'),
            ('degraded', 'world_owner_unavailable'),
            ('ready', 'provider_absent_base_only'),
            ('ready', 'awaiting_surveyed_opposed_pair'),
            ('ready', 'surveyed_pair_bound_observation_only'),
            ('refused', 'OUTCOME_STORE_UNCERTAIN'),
            ('off', 'not_started_or_disabled'),
        ], receipts)


class GreetingAcknowledgement(unittest.TestCase):
    def test_generic_emote_or_old_greeting_cannot_acknowledge_a_rendezvous(self):
        source = (WORLD / 'HCAITrade.c').read_text()
        gate = N(m_Trade='', m_LeftSerial=0, m_RightSerial=0, m_Requests=0, m_MaxRequests=0)
        bind(source, 'HCTradeGestureGate', gate, ('HCArm', 'HCObserved'), {})
        gate.HCArm('synthetic-trade:1', 4, 8, 3)
        left, right = N(gesture=1, greeting=4, serial=40), N(gesture=1, greeting=8, serial=80)
        def actor(signal):
            return N(GetEmoteManager=lambda: N(
                HCSignalGesture=lambda: signal.gesture,
                HCSignalGreetingSerial=lambda: signal.greeting,
                HCSignalSerial=lambda: signal.serial))
        port = N(m_Gestures=gate)
        # Native constants.c:368 GREETING=1; :371 TAUNT=4, inspected snapshot.
        bind((ADDON / 'HCXAITradeAdapter.c').read_text().replace('eAIBase', 'PlayerBase'),
             'HCXAITradeAdapter', port, ('HCNewGreetings',),
             dict(EmoteConstants=N(ID_EMOTE_GREETING=1)))
        a, b = actor(left), actor(right)
        self.assertFalse(port.HCNewGreetings(a, b), 'generic callback serials do not count')
        left.greeting = 5
        self.assertFalse(port.HCNewGreetings(a, b), 'both must acknowledge')
        right.greeting, right.gesture = 9, 4
        self.assertFalse(port.HCNewGreetings(a, b), 'a taunt is not a greeting')
        right.gesture = 0
        self.assertFalse(port.HCNewGreetings(a, b), 'an ended greeting is not current')
        right.gesture = 1
        self.assertTrue(port.HCNewGreetings(a, b))
        right.greeting = 0
        self.assertFalse(port.HCNewGreetings(a, b), 'saturated callback serial fails closed')


if __name__ == '__main__':
    unittest.main()
