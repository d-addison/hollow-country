"""HC-20 / #148: one synthetic behavioral slice of authored radio delivery.

Restricted translator and explicit native/store ports only. Offline checks do not
establish DayZ radio propagation, persistence, compilation or client presentation.

Actual RED/GREEN command:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_environmental_radio -v
RED: AssertionError: separate Morse delivery still bypasses environmental radio
     Ran 1 test; FAILED (failures=1).
GREEN: Ran 1 test; OK. runtime=PENDING.
Round 2 spec/plan/task: .banso-writer/inputs/task-r2.md HC-20 (active review);
.banso-writer/inputs/task.md; HC-11 owns shared trace edits. The two AGENTS.md
spec paths are absent in this checkout; runtime acceptance stays PENDING.

Actual round 2 RED command (before source edits):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_environmental_radio.RadioReviewFixes -v
P1-a: AssertionError: 1 != 3 : held place+TextId must not notify again
P1-b: AssertionError: 1 != 0 : new in-range fact must bypass undelivered far fact
P2-a: AssertionError: False is not true : 900m horizontal remains in range at 600m altitude
P2-b: AssertionError: False is not true : legacy fault must not refuse radio: tmp
      Same failure also observed for bak, empty, future. Ran 4 tests; FAILED (failures=7).
Each corresponding test was then run alone with the same command prefix and
its full RadioReviewFixes.test_p* name: Ran 1 test; OK for each item.
Final focused GREEN command:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_environmental_radio test_v2_morse test_v2_leads -v
Ran 9 tests; OK. All fixtures below are synthetic; runtime=PENDING.
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
                 'HCMorseReceipt', 'PersonalRadio', 'HCGroupService', 'HCWorldFact',
                 'HCWorldModule', 'HCLeadStore', 'HCMorseRateStore', 'HCMorseRateData'):
        source = re.sub(r'\b' + name + r'\b', 'HCEvent' + name, source)
    # Enforce vectors have value semantics; Python lists need a native copy port.
    source = re.sub(r'vector (\w+) = (player.GetPosition\(\)|place.Position);',
                    r'vector \1 = VectorCopy(\2);', source)
    source = source.replace('s_Instance', 'm_StaticInstance')
    source = source.replace('count++;', 'count = count + 1;')
    # Native JSON out-parameter loader is an explicit port, not a policy model.
    source = source.replace('JsonFileLoader<HCEventHCMorseRateData>.LoadData(text, m_Data, error)',
                            'LegacyLoad(this)')
    source = source.replace('array<string> factions = {"locals", "volunteers", "scavengers", "raiders", "travellers"};',
                            'array<string> factions = FactionArray();')
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
        lead_module = N(ReceiveResult=lambda lead, group, origin: retained.append((lead.Id, group, origin)) or 2)
        historical = N(PlaceId='synthetic', At=8000, Expires=12000, Kind='morse_lead')
        facts = EArray([historical])
        game = N(IsServer=lambda: True, GetTickTime=lambda: 10.)
        env = dict(EArray=EArray, VectorCopy=list, Print=logs.append, GetGame=lambda: game,
                   HCWorldClock=N(UTC=lambda: now[0]), HCLeadPolicy=policy,
                   HCEventHCLeadModule=N(Get=lambda: lead_module),
                   HCLeadReceiveResult=N(REFUSED=0, HELD=1, RETAINED=2),
                   HCEventHCWorldLead=N,
                   HCEventHCWorldModule=N(Get=lambda: N(GetRecentFacts=lambda age, output: (output.clear(), output.extend(facts)))),
                   HCEventHCGroupService=N(Get=lambda: None),
                   PlayerBase=N(Cast=lambda value: value),
                   HCEventPersonalRadio=N(Cast=lambda value: value),
                   vector=N(DistanceSq=lambda a, b: sum((x-y)**2 for x, y in zip(a, b))),
                   NotificationSystem=N(SendNotificationToPlayerIdentityExtended=lambda *args: sent.append(args)))
        shared = syntax_port((RADIO.parent / 'HCLeadModule.c').read_text())
        policy.Build = translate(shared, 'Build', env, 'HCLeadPolicy')
        policy.Kind = translate(shared, 'Kind', env, 'HCLeadPolicy')
        methods = ('HasListener', 'LatestInRange', 'Receiving', 'InReportRange', 'BeginChannel', 'RetainReport', 'HCRefuse', 'OnTick', 'OnStop')
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
            r.m_Facts = EArray()
            r.m_FromFallback = False
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
            facts[:] = [] if mode == 'no-fact' else [historical]
            if mode == 'cap':
                roster[:] = [held] * 33
            else:
                roster[:] = [held, other]
            if mode == 'receipt-fault':
                lead_module.ReceiveResult = lambda *args: 0
            elif mode == 'disconnect-after-save':
                def disconnect(*args):
                    held.IsPlayerDisconnected = lambda: True
                    other.IsPlayerDisconnected = lambda: True
                    return 2
                lead_module.ReceiveResult = disconnect
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
        self.assertTrue(rates.Allowed(17, 20000))
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


class RadioFixture:
    """Synthetic native handles/clock/storage; authored radio and lead decisions."""
    def __init__(self):
        self.now = 10000
        self.sent, self.logs, self.saves = [], [], []
        self.facts, self.roster = EArray(), EArray()
        self.places = {'near': N(Name='Near', Position=[0., 0., 0.]),
                       'far': N(Name='Far', Position=[5000., 0., 0.])}
        self.rows = EArray()
        self.healthy = True
        self.channels = EArray([N(Frequency=96.6, LastSent=0, Sequence=0) for _ in range(5)])
        self.store = N(Data=N(Channels=self.channels, Leads=self.rows),
                       Healthy=lambda: self.healthy, Save=self.save,
                       NextId=lambda prefix: prefix + str(len(self.rows)))
        self.policy = N(Place=self.places.get, SoloGroup=lambda uid: 'solo:' + uid)
        self.world = N(GetRecentFacts=lambda age, output: (output.clear(), output.extend(self.facts)))
        self.env = dict(EArray=EArray, VectorCopy=list, Print=self.logs.append, GetGame=lambda: N(IsServer=lambda: True),
            HCWorldClock=N(UTC=lambda: self.now), HCLeadPolicy=self.policy,
            HCWorldLimits=N(Token=lambda value: bool(value)),
            HCEventHCWorldModule=N(Get=lambda: self.world),
            HCEventHCWorldLead=lambda: N(Id='', Kind='', TargetPlaceId='', Source='', GroupId='', Expires=0, TextId=''), HCEventHCLeadStore=N(Get=lambda: self.store),
            HCEventHCGroupService=N(Get=lambda: None),
            HCLeadReceiveResult=N(REFUSED=0, HELD=1, RETAINED=2),
            PlayerBase=N(Cast=lambda value: value), HCEventPersonalRadio=N(Cast=lambda value: value),
            HCPerfPlayers=N(HCGet=lambda: self.roster),
            vector=N(DistanceSq=lambda a, b: sum((x-y)**2 for x, y in zip(a, b))),
            NotificationSystem=N(SendNotificationToPlayerIdentityExtended=lambda *args: self.sent.append(args)))
        shared = syntax_port((RADIO.parent / 'HCLeadModule.c').read_text())
        for name in ('Valid', 'KnownPlace', 'Build', 'Kind', 'Copy', 'Text', 'LegacyText', 'FactionName'):
            setattr(self.policy, name, translate(shared, name, self.env, 'HCLeadPolicy'))
        lead_cls = type('AuthoredLead', (), {})
        for name in ('Latest', 'Receive', 'ReceiveResult'):
            if re.search(r'\b' + name + r'\(', shared):
                setattr(lead_cls, name, translate(shared, name, self.env, 'HCEventHCLeadModule', member=True))
        self.leads = lead_cls()
        self.leads.m_Store, self.leads.m_Facts = self.store, EArray()
        self.leads.Get = lambda: self.leads
        self.env['HCEventHCLeadModule'] = N(Get=lambda: self.leads)
        radio_cls = type('AuthoredRadio', (), {})
        source = syntax_port(RADIO.read_text())
        for name in ('Receiving', 'InReportRange', 'BeginChannel', 'RetainReport', 'HCRefuse',
                     'OnTick', 'OnStop', 'Fallback', 'LatestInRange', 'HasListener', 'OnStart'):
            if re.search(r'\b' + name + r'\(', source):
                setattr(radio_cls, name, translate(source, name, self.env, 'HCRadioChatter', member=True))
        self.radio = radio_cls()
        r = self.radio
        r.m_StaticInstance = None
        r.m_Store = self.store
        r.m_Defaults = N(ReportRangeMetres=1000., MaxListeners=32)
        r.m_LegacyRates = N(Allowed=lambda *args: True)
        r.m_Status = N(HCPublish=lambda *args: None)
        r.m_UnitBudget = N(HCReset=lambda count: None, HCTake=lambda cost: True)
        r.m_WorkBudget = N(HCReset=lambda count: None, HCContinue=lambda: True)
        r.m_Listeners, r.m_Fallback, r.m_Facts = EArray(), EArray(), EArray()
        r.m_Report = r.m_Channel = None
        r.m_ChannelCursor = r.m_ListenerCursor = r.m_Reports = r.m_Recipients = 0
        r.m_Committed = r.m_FromFallback = False
        r.m_Ready, r.m_Elapsed, r.m_Text = True, 60., ''

    def save(self):
        self.saves.append(1)
        return self.healthy

    def fact(self, place='near', at=8000, kind='morse_lead'):
        return N(PlaceId=place, At=at, Expires=100000, Kind=kind)

    def player(self, distance=20., altitude=0.):
        class Identity(str):
            def Hash(self): return 17
            def Length(self): return len(self)
        p = Handle(identity=Identity('listener'), position=[distance, altitude, 0.])
        p.IsPlayerDisconnected = lambda: False
        radio = Handle()
        radio.owner = p
        radio.GetCompEM = lambda: N(IsSwitchedOn=lambda: True, IsWorking=lambda: True)
        radio.IsReceiving = lambda: True
        radio.GetTunedFrequency = lambda: 96.6
        p.GetItemInHands = lambda: radio
        self.roster.append(p)
        return p

    def cycle(self):
        # Force the same channel after its actual 600-second cooldown.
        self.radio.m_ChannelCursor = 0
        self.radio.OnTick(60.)
        for _ in range(len(self.roster) + 1):
            self.radio.OnTick(1.)
        self.now += 600


class RadioReviewFixes(unittest.TestCase):
    def test_p1a_same_listener_three_channel_cycles_notified_once(self):
        f = RadioFixture()
        f.player()
        f.facts.append(f.fact())
        for _ in range(3):
            f.cycle()
        self.assertEqual(1, len(f.sent), 'held place+TextId must not notify again')
        self.assertEqual(1, len(f.rows))
        self.assertTrue(f.leads.Receive(f.rows[0], 'solo:listener', 'note'))
        self.assertEqual(1, len(f.rows), 'existing callers keep idempotent success')
        # A failed durable lead receipt still cannot display text.
        f = RadioFixture()
        f.player()
        f.facts.append(f.fact())
        def fail_lead_save():
            if f.rows: f.healthy = False
            return f.healthy
        f.store.Save = fail_lead_save
        f.cycle()
        self.assertEqual([], f.sent)

    def test_p1b_far_fact_does_not_starve_newer_near_fact(self):
        f = RadioFixture()
        f.player()
        f.facts.append(f.fact('far', 7900))
        f.cycle()
        self.assertEqual([], f.sent)
        f.facts.insert(0, f.fact('near', 8000))
        f.cycle()
        self.assertEqual(1, len(f.sent), 'new in-range fact must bypass undelivered far fact')
        self.assertEqual('near', f.rows[0].TargetPlaceId)
        self.assertEqual([], f.radio.m_Fallback, 'Latest facts never enter fallback queue')
        # A newer distant fact must also be skipped within the same start.
        f = RadioFixture()
        f.player()
        f.facts.extend([f.fact('far', 8100), f.fact('near', 8000)])
        f.cycle()
        self.assertEqual(1, len(f.sent))
        self.assertEqual('near', f.rows[0].TargetPlaceId)
        # Explicit 33-fact fixture: only the first 32 candidates are examined.
        f = RadioFixture()
        f.player()
        f.facts.extend([f.fact('far', 8199 - i) for i in range(32)] + [f.fact('near', 8000)])
        builds = []
        build = f.policy.Build
        f.policy.Build = lambda *args: builds.append(1) or build(*args)
        f.cycle()
        self.assertEqual([], f.sent)
        self.assertEqual(32, len(builds))
        # Note fallback stays bounded at four, retries without duplication, and
        # cannot hide an eligible shared fact when all its notes are distant.
        f = RadioFixture()
        f.player()
        offer = N(Id='synthetic-note', Kind='EVENT', TargetPlaceId='near',
                  TextId='morse_lead', GroupId='', Source='world', Expires=100000)
        for _ in range(4): self.assertTrue(f.radio.Fallback(offer))
        self.assertFalse(f.radio.Fallback(offer))
        f.radio.m_LegacyRates.Allowed = lambda *args: False
        for _ in range(3):
            f.cycle()
            self.assertEqual(4, len(f.radio.m_Fallback))
        for note in f.radio.m_Fallback: note.TargetPlaceId = 'far'
        f.radio.m_LegacyRates.Allowed = lambda *args: True
        f.facts.append(f.fact())
        f.cycle()
        self.assertEqual(1, len(f.sent))
        self.assertEqual(4, len(f.radio.m_Fallback))

    def test_p2a_range_is_horizontal_at_600m_altitude(self):
        f = RadioFixture()
        p = f.player(distance=900., altitude=600.)
        report = N(Kind='EVENT', Source='world', TargetPlaceId='near', TextId='morse_lead', Expires=12000)
        self.assertTrue(f.radio.InReportRange(p, report), '900m horizontal remains in range at 600m altitude')
        self.assertEqual([0., 0., 0.], f.places['near'].Position)
        p.position[0] = 1000.1
        self.assertFalse(f.radio.InReportRange(p, report))

    def test_p2b_faulty_legacy_files_allow_radio_without_legacy_cooldown(self):
        for mode in ('tmp', 'bak', 'bak-with-main', 'empty', 'future'):
            with self.subTest(mode=mode):
                f = RadioFixture()
                f.player()
                f.facts.append(f.fact())
                data = N(Version=1, LastUTC=9900, Receipts=EArray([N(Fingerprint=17, At=9900)]))
                if mode == 'empty': data.Receipts.clear()
                if mode == 'future': data.LastUTC = 10001
                def load(rates):
                    rates.m_Data = data
                    return True
                f.env.update(FileExist=lambda path: path.endswith('HollowCountry') or
                    (mode != 'bak' and path.endswith('.json')) or path.endswith('.' + mode.split('-')[0]),
                    MakeDirectory=lambda path: True, HCGroupIO=N(Read=lambda *args: True),
                    LegacyLoad=load, HCEventHCMorseRateData=lambda: N(LastUTC=0, Receipts=EArray()))
                cls = type('AuthoredLegacyRates', (), {})
                source = syntax_port(MORSE.read_text())
                for name in ('Fail', 'Open', 'RateAllowed', 'Allowed'):
                    setattr(cls, name, translate(source, name, f.env, 'HCMorseRateStore', member=True))
                rates = cls()
                rates.m_Path, rates.m_Temp, rates.m_Backup = 'rates.json', 'rates.json.tmp', 'rates.json.bak'
                rates.m_Data, rates.m_Fault = None, False
                f.env.update(HCEventHCMorseRateStore=lambda: rates,
                    HCV2Admission=N(Line=lambda *args: 'admission'), HCV2Gates=N(Qualified=lambda gate: False),
                    s_Instance=None)
                f.radio.m_AdmissionPrinted = True
                f.radio.m_Ready = False
                f.radio.OnStart(N(EnableLeads=True))
                self.assertTrue(f.radio.m_Ready, 'legacy fault must not refuse radio: ' + mode)
                f.cycle()
                self.assertEqual(1, len(f.sent))
                self.assertTrue(rates.Allowed(17, f.now))
                rates.Fail()  # Repeated probes must not repeat the diagnostic.
                self.assertEqual(1, sum('legacy_rate_store_fault' in line for line in f.logs))


if __name__ == '__main__':
    unittest.main()
