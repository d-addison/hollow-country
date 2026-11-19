"""HC-20 / #148: one synthetic behavioral slice of authored radio delivery.

Restricted translator and explicit native/store ports only. Offline checks do not
establish DayZ radio propagation, persistence, compilation or client presentation.

Actual RED/GREEN command:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_environmental_radio -v
RED: AssertionError: separate Morse delivery still bypasses environmental radio
     Ran 1 test; FAILED (failures=1).
GREEN: Ran 1 test; OK. runtime=PENDING.
Spec/plan/task: .banso-writer/inputs/task.md HC-20; HC-11 owns shared trace edits.
"""
from pathlib import Path
from types import SimpleNamespace as N
import re
import unittest

from tests.unit.test_event_runtime import EArray, Handle, translate

ROOT = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts'
RADIO = ROOT / '4_World/Leads/HCRadioChatter.c'
MORSE = RADIO.with_name('HCMorseClues.c')


def syntax_port(source):
    # Only adapt DTO/native type spellings accepted by the existing translator.
    for name in ('HCWorldLead', 'HCRadioChannel', 'HCLeadModule', 'HCWorldPlace',
                 'HCMorseReceipt', 'PersonalRadio', 'HCGroupService', 'HCWorldFact'):
        source = re.sub(r'\b' + name + r'\b', 'HCEvent' + name, source)
    return source


class EnvironmentalRadio(unittest.TestCase):
    def test_folded_report_has_one_durable_channel_receipt_and_finite_factual_recipients(self):
        morse = MORSE.read_text()
        self.assertNotIn('rpc.Send(', morse,
                         'separate Morse delivery still bypasses environmental radio')
        source = syntax_port(RADIO.read_text())
        now, sent, retained, saves, logs = [10000], [], [], [], []
        fact = N(Id='morse_lead-synthetic-8000', Kind='EVENT', Source='world',
                 TargetPlaceId='synthetic', TextId='morse_lead', Expires=12000)
        place = N(Name='Synthetic', Position=[0., 0., 0.])
        policy = N(Valid=lambda lead: bool(lead and lead.TargetPlaceId == 'synthetic'),
                   Copy=lambda lead: N(**vars(lead)), Place=lambda name: place,
                   Text=lambda lead: 'An earlier event was reported near Synthetic. Old news.',
                   SoloGroup=lambda identity: 'solo:' + identity)
        lead_module = N(Latest=lambda: fact,
                        Receive=lambda lead, group, origin: retained.append((lead.Id, group, origin)) or True)
        game = N(IsServer=lambda: True, GetTickTime=lambda: 10.)
        env = dict(EArray=EArray, Print=logs.append, GetGame=lambda: game,
                   HCWorldClock=N(UTC=lambda: now[0]), HCLeadPolicy=policy,
                   HCEventHCLeadModule=N(Get=lambda: lead_module),
                   HCEventHCGroupService=N(Get=lambda: None),
                   PlayerBase=N(Cast=lambda value: value),
                   HCEventPersonalRadio=N(Cast=lambda value: value),
                   vector=N(DistanceSq=lambda a, b: sum((x-y)**2 for x, y in zip(a, b))),
                   NotificationSystem=N(SendNotificationToPlayerIdentityExtended=lambda *args: sent.append(args)))
        methods = ('Receiving', 'InReportRange', 'BeginChannel', 'RetainReport', 'HCRefuse', 'OnTick', 'OnStop')
        cls = type('AuthoredRadio', (), {})
        for name in methods:
            setattr(cls, name, translate(source, name, env, 'HCRadioChatter', member=True))
        def player(uid, *, powered=True, frequency=96.6, stored=False, distance=20.):
            p = Handle(identity=uid, position=[distance, 0., 0.])
            p.IsPlayerDisconnected = lambda: False
            radio = Handle(identity='', kind='synthetic-radio')
            radio.owner = p
            radio.GetCompEM = lambda: N(IsSwitchedOn=lambda: True, IsWorking=lambda: powered)
            radio.IsReceiving = lambda: True
            radio.GetTunedFrequency = lambda: frequency
            p.GetItemInHands = lambda: None if stored else radio
            return p
        held = player('held')
        other = player('other')
        dark = player('dark', powered=False)
        wrong = player('wrong', frequency=94.6)
        stored = player('stored', stored=True)
        far = player('far', distance=1000.1)
        edge = player('edge', distance=1000.)
        roster = EArray([held, dark, wrong, stored, far, edge, other])
        env['HCPerfPlayers'] = N(HCGet=lambda: roster)
        channels = EArray([N(Faction='travellers', Frequency=96.6, LastSent=0, Sequence=0)
                           for _ in range(5)])
        durable = []
        healthy = [True]
        def save():
            saves.append(1)
            if healthy[0]:
                durable[:] = [(c.LastSent, c.Sequence) for c in channels]
            return healthy[0]
        def state():
            r = cls()
            r.m_Store = N(Healthy=lambda: healthy[0], Data=N(Channels=channels), Save=save)
            r.m_Defaults = N(ReportRangeMetres=1000., MaxListeners=32)
            r.m_LegacyRates = N(Allowed=lambda fingerprint, at: True)
            r.m_UnitBudget = N(HCReset=lambda count: None, HCTake=lambda cost: True)
            r.m_WorkBudget = N(HCReset=lambda count: None, HCContinue=lambda: True)
            r.m_Status = N(HCPublish=lambda *args: None)
            r.m_Ready = True
            r.m_Listeners = EArray()
            r.m_Fallback = EArray()
            r.m_Report = r.m_Channel = None
            r.m_ChannelCursor = r.m_ListenerCursor = r.m_Reports = r.m_Recipients = 0
            r.m_Committed = False
            r.m_Elapsed = 60.
            r.m_Text = ''
            return r
        radio = state()
        # Native identity Hash port only; the report handler decides eligibility.
        class IdentityString(str):
            def Hash(self): return sum(map(ord, self))
            def Length(self): return len(self)
        for p in roster:
            p.GetId = lambda p=p: IdentityString(p.identity)
        self.assertTrue(radio.Receiving(held, 96.6))
        for p in (dark, wrong, stored):
            self.assertFalse(radio.Receiving(p, 96.6))
        self.assertTrue(radio.InReportRange(edge, fact))
        self.assertFalse(radio.InReportRange(far, fact))
        radio.OnTick(1.)
        self.assertEqual(1, len(sent))
        self.assertEqual(1, radio.m_ListenerCursor)
        # Explicit late join during the active roster, before other recipients.
        late = player('late')
        roster.append(late)
        for _ in range(len(roster) + 2):
            radio.OnTick(1.)
        self.assertEqual(['held', 'edge', 'other'], [args[0].identity for args in sent])
        self.assertEqual(1, len(saves), 'one reservation per report, shared across recipients')
        self.assertEqual(1, channels[0].Sequence)
        self.assertEqual([fact.Id] * 3, [entry[0] for entry in retained])
        self.assertTrue(all(entry[2] == 'radio' for entry in retained))
        # Late join and restart do not replay a reserved batch.
        channels = EArray([N(Faction='travellers', Frequency=96.6, LastSent=at, Sequence=sequence)
                           for at, sequence in durable])
        restarted = state()
        restarted.OnTick(1.)
        self.assertEqual(3, len(sent))
        self.assertEqual([(10000, 1)] + [(0, 0)] * 4, durable)
        radio.OnStop()
        radio.OnTick(100.)
        self.assertEqual(3, len(sent))
        self.assertEqual([], radio.m_Listeners)
        # No fact, cap overflow and failed reservation each emit no report.
        for mode in ('no-fact', 'cap', 'legacy-denied', 'save-fault', 'receipt-fault', 'disconnect-after-save'):
            sent.clear(); retained.clear(); saves.clear()
            healthy[0] = True
            for channel in channels:
                channel.LastSent = channel.Sequence = 0
            lead_module.Latest = lambda: None if mode == 'no-fact' else fact
            if mode == 'cap':
                roster[:] = [held] * 33
            else:
                roster[:] = [held, other]
            if mode == 'receipt-fault':
                lead_module.Receive = lambda *args: False
            elif mode == 'disconnect-after-save':
                def disconnect(*args):
                    held.IsPlayerDisconnected = lambda: True
                    other.IsPlayerDisconnected = lambda: True
                    return True
                lead_module.Receive = disconnect
            if mode == 'save-fault':
                healthy[0] = False
                # Initially healthy, fault at the actual channel reservation.
                current = state()
                current.m_Store.Healthy = lambda: not saves
            else:
                current = state()
            if mode == 'legacy-denied':
                current.m_LegacyRates.Allowed = lambda *args: False
            for _ in range(5):
                current.OnTick(60.)
            self.assertEqual([], sent, mode)
            self.assertEqual([], retained, mode)
        # Execute the retained legacy migration policy, including future clock
        # and previous recipient cooldowns. No profile files are changed here.
        rates_source = syntax_port(morse)
        rate_env = dict(EArray=EArray)
        rates_cls = type('AuthoredLegacyRates', (), {})
        for name in ('RateAllowed', 'Allowed'):
            setattr(rates_cls, name, translate(rates_source, name, rate_env, 'HCMorseRateStore', member=True))
        rates = rates_cls()
        rates.m_Fault = False
        rates.m_Data = N(LastUTC=9900, Receipts=EArray([N(Fingerprint=17, At=9900)]))
        self.assertFalse(rates.Allowed(17, 10000))
        self.assertFalse(rates.Allowed(17, 9800))
        self.assertFalse(rates.Allowed(17, 10500))
        self.assertTrue(rates.Allowed(18, 10500))
        self.assertTrue(rates.Allowed(17, 11700))
        rates.m_Fault = True
        self.assertFalse(rates.Allowed(17, 20000))
        # Reuse authored shared fact-age policy: the producer port is explicitly
        # synthetic, and a live/future/expired fact is never eligible.
        shared = syntax_port((RADIO.parent / 'HCLeadModule.c').read_text())
        build = translate(shared, 'Build', env, 'HCLeadPolicy')
        historical = N(PlaceId='synthetic', At=8200, Expires=12000, Kind='morse_lead')
        target = N()
        self.assertTrue(build(historical, target, 'synthetic', 'EVENT', 10000))
        historical.At = 8201
        self.assertFalse(build(historical, N(), 'synthetic', 'EVENT', 10000))
        historical.At = 10001
        self.assertFalse(build(historical, N(), 'synthetic', 'EVENT', 10000))
        historical.At, historical.Expires = 8000, 10000
        self.assertFalse(build(historical, N(), 'synthetic', 'EVENT', 10000))
        client = (ROOT / '5_Mission/Leads/HCMorseClient.c').read_text()
        self.assertNotIn('Event_OnRPC.Insert', client)
        self.assertNotIn('PlaySoundOnObject', client)
        self.assertNotIn('Symbols(', (ROOT / '3_Game/Leads/HCMorseRpc.c').read_text())


if __name__ == '__main__':
    unittest.main()
