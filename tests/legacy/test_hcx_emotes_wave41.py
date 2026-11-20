"""#148/#198 spec -> bounded faction receipts and perceived greeting API.
Explicit synthetic ports execute authored bodies; no engine observation.
Plan/tasks: preserve generic serial API; add greeting serial + LOS acknowledgement;
reuse durable capped betrayal ledger for faction receipts; surface store degradation.
"""
import re
import unittest
from types import SimpleNamespace as N
from tests.legacy import test_hc_ai_signals as signals
HCX = signals.HCX
from tests.legacy.test_expansion_ai_adapter import Authored


class EmotesWave41(unittest.TestCase):
    def test_stance_never_passes_new_as_an_argument(self):
        text = (HCX / 'HCXStance.c').read_text()
        self.assertNotRegex(text, r'\(\s*new\s+',
                            'construct an owned local before passing an argument')

    def test_startup_status_reflects_failed_store_or_provider_before_any_tick(self):
        from tests.legacy.test_hc_module_readiness_wave16 import FakeStatus, derive
        text = (HCX / 'HCXStance.c').read_text().split('class HCXLivingModule', 1)[1]
        # Declaration syntax only; the lifecycle/status bodies remain authored.
        for typename in ('HCXNativeSignalProvider', 'HCXCheckpointProps'):
            text = text.replace(typename + ' ', 'Object ')
        for store_failed, provider_failed, expected in (
                (True, False, 'degraded'), (False, True, 'degraded'),
                (False, False, 'ready')):
            with self.subTest(store_failed=store_failed, provider_failed=provider_failed):
                fixture = signals.Signals()
                observer = fixture.observation()
                store = fixture.store()
                fixture.disk.blocked = store_failed  # Explicit synthetic IO failure.
                fixture.provider_ready = not provider_failed
                observer.m_Store = store
                observer.Start = lambda:store.Open(100)
                observer.Install = lambda provider:setattr(observer, 'm_Provider', provider)
                provider = observer.m_Provider
                logs = []
                owner = N(m_Checkpoints=None, m_Refusal='', m_Started=False,
                          m_Operational=FakeStatus())
                api = Authored(text, dict(
                    Print=logs.append, HCV2Admission=N(Line=lambda *a:''),
                    HCV2Gates=N(Qualified=lambda *a:False),
                    HCXAIQualification=N(SetEncountersEnabled=lambda *a:None),
                    HCAskForNews=N(Configure=lambda *a:None),
                    HCXEmoteObservation=observer,
                    HCXNativeSignalProvider=lambda:provider,
                    HCXCheckpointProps=lambda:N(Start=lambda:None),
                    HCModuleReadiness=N(HCDerive=derive())))
                api.call('OnStart', owner, N())
                self.assertEqual(not store_failed, store.Healthy())
                status = api.call('HCGetOperationalStatus', owner)
                self.assertEqual(expected, status.state,
                                 'startup status must reflect store/provider failure before OnTick')
                if expected == 'degraded':
                    self.assertEqual('emote_provider_or_betrayal_store_unavailable', status.reason)

    def test_greeting_serial_ignores_other_callbacks_and_keeps_generic_api(self):
        text = (HCX / 'HCXEmoteObservation.c').read_text()
        text = text.split('modded class EmoteManager', 1)[1].split('class HCXSignalProvider', 1)[0]
        text = text.replace('EmoteCB previous', 'Object previous')
        owner = N(m_HCSignalSerial=0, m_HCGreetingSerial=0, m_Callback=None,
                  m_bEmoteIsPlaying=False, m_CurrentGestureID=47)
        def callback(*args):
            owner.m_Callback = object()
            owner.m_bEmoteIsPlaying = True
        api = Authored(text, dict(GetGame=lambda:N(IsServer=lambda:True),
                        super=N(CreateEmoteCallback=callback),
                        EmoteConstants=N(ID_EMOTE_GREETING=1)))
        api.call('CreateEmoteCallback', owner, None, 47, 0, False)
        self.assertEqual(1, api.call('HCSignalSerial', owner))
        self.assertEqual(0, api.call('HCSignalGreetingSerial', owner))
        owner.m_CurrentGestureID = 1
        api.call('CreateEmoteCallback', owner, None, 1, 0, False)
        self.assertEqual(2, api.call('HCSignalGreetingSerial', owner))
        owner.m_CurrentGestureID = 47
        api.call('CreateEmoteCallback', owner, None, 47, 0, False)
        self.assertEqual(3, api.call('HCSignalSerial', owner))
        self.assertEqual(2, api.call('HCSignalGreetingSerial', owner))
        owner.m_HCSignalSerial = 2147483647
        self.assertEqual(0, api.call('HCSignalGreetingSerial', owner))

    def test_acknowledgement_requires_server_perception_and_new_active_greeting(self):
        fixture = signals.Signals()
        observer = fixture.observation()
        text = re.sub(r'\bs_(\w+)', r'm_\1', (HCX / 'HCXEmoteObservation.c').read_text().split('class HCXEmoteObservation', 1)[1])
        api = Authored(text, dict(HCXEmoteObservation=observer, EmoteConstants=N(ID_EMOTE_GREETING=9)))
        call = lambda observed, baseline:api.call('HCObservedGreeting', observer, N(), fixture.player, observed, baseline)
        self.assertFalse(call(False, 0))
        self.assertFalse(call(True, -1))
        self.assertTrue(call(True, 0))
        self.assertFalse(call(True, 1))
        fixture.gesture = 10
        self.assertFalse(call(True, 0))
        fixture.gesture = 9; fixture.server = False
        self.assertFalse(call(True, 0))

    def test_faction_memory_uses_existing_bounded_durable_store_and_expires(self):
        fixture = signals.Signals(); store = fixture.store()
        self.assertTrue(store.Open(100)); store.m_TtlSeconds = 10
        api = Authored((HCX / 'HCXBetrayalStore.c').read_text(), {})
        remember = lambda faction, uid, now:api.call('RememberFaction', store, faction, uid, now)
        has = lambda faction, uid:api.call('HasFaction', store, faction, uid)
        self.assertTrue(remember('Locals', 'p', 100))
        self.assertTrue(has('Locals', 'p'))
        self.assertFalse(has('Volunteers', 'p'))
        self.assertFalse(has('Locals', 'q'))
        self.assertFalse(remember('', 'p', 100))
        saved = fixture.disk.image
        store = fixture.store(saved); store.m_TtlSeconds = 10
        self.assertTrue(store.Open(105)); self.assertTrue(has('Locals', 'p'))
        fixture.utc = 110
        self.assertFalse(has('Locals', 'p'))

    def test_faction_receipt_is_written_by_observed_aggression_and_seen_by_other_group(self):
        fixture = signals.Signals(); observer, store, actor = fixture.event_fixture()
        api = Authored((HCX / 'HCXBetrayalStore.c').read_text(), {})
        store.RememberFaction = lambda *args:api.call('RememberFaction', store, *args)
        store.HasFaction = lambda *args:api.call('HasFaction', store, *args)
        observer.Remember(actor, fixture.player, 'Locals')
        self.assertTrue(store.Has('synthetic-group', 'synthetic-player'))
        self.assertTrue(store.HasFaction('Locals', 'synthetic-player'))
        observer.EventWork = lambda:self.fail('replayed callback consumed a work slot')
        observer.Remember(actor, fixture.player, 'Locals')
        self.assertEqual(2, fixture.disk.writes)
        text = re.sub(r'\bs_(\w+)', r'm_\1', (HCX / 'HCXEmoteObservation.c').read_text().split('class HCXEmoteObservation', 1)[1])
        read = Authored(text, dict(HCXFactions=N(Id=lambda faction:faction)))
        neighbor = N(GetGroup=lambda:N(GetName=lambda:'other-group', GetFaction=lambda:'Locals'))
        self.assertTrue(read.call('Grudge', observer, neighbor, fixture.player))
        enemy = N(GetGroup=lambda:N(GetName=lambda:'other-group', GetFaction=lambda:'Raiders'))
        self.assertFalse(read.call('Grudge', observer, enemy, fixture.player))

    def test_no_actor_store_fault_degrades_status_and_recovers_without_combat_changes(self):
        from tests.legacy.test_hc_module_readiness_wave16 import FakeStatus, derive
        from tests.legacy.test_expansion_ai_adapter import A
        text = (HCX / 'HCXStance.c').read_text().split('class HCXLivingModule', 1)[1]
        text = text.replace('array<eAIBase> actors', 'Object actors')
        ready = [True]; logs = []
        owner = N(m_Checkpoints=None, m_Refusal='', m_Started=True, m_Operational=FakeStatus())
        api = Authored(text, dict(HCXEmoteObservation=N(Ready=lambda:ready[0]),
                       eAIBase=N(eAI_GetAll=lambda:A()), Print=logs.append,
                       HCModuleReadiness=N(HCDerive=derive())))
        for healthy, expected in ((True, 'ready'), (False, 'degraded'), (False, 'degraded'), (True, 'ready')):
            ready[0] = healthy
            api.call('OnTick', owner, 1)
            api.call('HCGetOperationalStatus', owner)
            self.assertEqual(expected, owner.m_Operational.state)
        self.assertEqual(1, len(logs))


if __name__ == '__main__':
    unittest.main()
