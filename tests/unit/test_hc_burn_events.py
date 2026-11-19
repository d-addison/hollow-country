"""#160 HC-S001/S002 burn-down for events, groups, camp respawn, leads and radio.

Each refused Start/Admit/Ensure/OnStart path now names a stable reason (logged once
per reason change, or published to the module's HC-1 status). The tests execute the
authored bodies through the existing restricted translators against EXPLICIT SYNTHETIC
ports (fake filesystem, tick clock, stores). They establish no DayZ behaviour; runtime
acceptance stays PENDING.

Command: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_burn_events -v
RED (before the source edits, 2026-11-19): see the w26-burn-events commit message.
"""
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit import test_event_runtime as er
from tests.unit import test_event_sites as es
from tests.unit import test_event_transport as et
from tests.unit.test_group_server import EArray
from tests.unit.test_hc_environmental_radio import syntax_port

ROOT = er.ROOT
translate = er.translate


def authored(source, owner, env, names):
    """Translate the named members that exist in the authored class (absent ones stay absent)."""
    cls = type('Authored' + owner, (), {})
    for name in names:
        if re.search(r'\b(?:bool|int|float|string|void|vector|HCEvent\w+) ' + name + r'\(', source):
            setattr(cls, name, translate(source, name, env, owner, True))
    return cls


class JournalDirectory(unittest.TestCase):
    ROOT_DIR = 'synthetic-root'

    def io(self, fail):
        source = (ROOT / '4_World/Events/HCEventJournal.c').read_text().split('class HCEventCodec')[0]
        logs = []
        env = dict(EArray=EArray, len=len, str=str, Print=logs.append,
                   FileExist=lambda path: path != fail and path != self.ROOT_DIR and False,
                   MakeDirectory=lambda path: path != fail)
        cls = authored(source, 'HCEventJournalIO', env, ('Ensure', 'HCRefuse', 'Refusal'))
        io = cls()
        io.m_Root = self.ROOT_DIR
        io.m_Refusal = ''
        return io, logs

    def test_each_directory_refusal_names_its_reason_once(self):
        for fail, reason in (('$profile:HollowCountry', 'profile_directory_unavailable'),
                             ('$profile:HollowCountry/Events', 'events_directory_unavailable'),
                             (self.ROOT_DIR, 'state_directory_unavailable')):
            io, logs = self.io(fail)
            self.assertFalse(io.Ensure(), reason)
            self.assertFalse(io.Ensure(), reason)
            self.assertEqual(['[HC Events] journal directory refused reason=' + reason], logs)


class TransportRefusals(unittest.TestCase):
    def setUp(self):
        self.t = et.EventTransportTests()
        self.t.setUp()
        self.logs = []
        self.t.e['Print'] = self.logs.append
        self.t.e['Math'].RandomIntInclusive = lambda low, high: low
        self.rpc = self.t.rpc
        self.rpc.m_Refusal = ''

    def game(self, server=True, tick=100.):
        self.t.e['GetGame'] = lambda: N(IsServer=lambda: server, GetTickTime=lambda: tick)

    def test_start_refusals_are_named_and_not_repeated(self):
        self.assertFalse(self.rpc.Start(N()))
        self.assertFalse(self.rpc.Start(N()))
        self.rpc.m_Started = False
        self.game(server=False)
        self.assertFalse(self.rpc.Start(N()))
        self.game()
        self.assertFalse(self.rpc.Start(None))
        self.game(tick=float('nan'))
        self.assertFalse(self.rpc.Start(N()))
        self.assertEqual(['[HC Events] opt-in transport refused reason=' + reason for reason in
                          ('already_started', 'not_server', 'module_missing', 'tick_clock_invalid')], self.logs)

    def test_request_flood_logs_one_rate_line_and_bad_clock_its_own(self):
        peer = N(RateWindow=100., RateCount=0)
        self.rpc.m_LastTime = 100.
        self.game(tick=100.)
        self.assertEqual([True] * 4 + [False] * 3, [self.rpc.Admit(peer) for _ in range(7)])
        self.assertEqual(['[HC Events] opt-in transport refused reason=rate_limited'], self.logs)
        self.game(tick=float('nan'))
        self.assertFalse(self.rpc.Admit(peer))
        self.assertFalse(self.rpc.Admit(peer))
        self.assertEqual(['[HC Events] opt-in transport refused reason=rate_limited',
                          '[HC Events] opt-in transport refused reason=clock_invalid'], self.logs)


class RuntimeRefusals(unittest.TestCase):
    def test_start_refusals_carry_a_reason(self):
        helper = er.EventRuntimeTests()
        helper.setUp()
        runtime = helper.runtime()
        helper.ai.ready = True
        helper.mission.Family = 5
        helper.mission.ActorBudget = 2
        self.assertEqual(0, runtime.Announce(helper.mission, helper.ctx))
        logs = []
        helper.e['Print'] = logs.append
        helper.ctx.Session = 'x' * 97
        self.assertFalse(runtime.Start(helper.cfg, helper.ctx, helper.store, helper.observer, helper.ai))
        self.assertEqual('session_restart_rejected', runtime.m_Refusal)
        self.assertEqual(['[HC Events] runtime start refused reason=session_restart_rejected'], logs)
        helper.ctx.Session = 'session-a'
        self.assertFalse(runtime.Start(helper.cfg, helper.ctx, None, helper.observer, helper.ai))
        self.assertEqual('dependency_missing_or_clock_range', runtime.m_Refusal)


class RewardRefusals(es.Fixture):
    def refusal_lines(self):
        return [line for line in self.logs if 'reward ledger refused' in line]

    def test_sticky_journal_fault_and_unconfigured_start_name_a_reason_once(self):
        ledger = self.ledger()
        self.io.names_broken = True
        for _ in range(3):
            self.assertFalse(ledger.Start())
        self.assertEqual(['[HC Events] reward ledger refused reason=journal_fault'], self.refusal_lines())
        bare = es.load('HCEventRewards.c', 'HCEventRewardLedger', self.e)()
        bare.m_IO = bare.m_Pool = None
        bare.m_Fault = bare.m_Ready = False
        bare.m_Refusal = ''
        self.assertFalse(bare.Start())
        self.assertFalse(bare.Start())
        self.assertEqual(['[HC Events] reward ledger refused reason=journal_fault',
                          '[HC Events] reward ledger refused reason=not_configured'], self.refusal_lines())


class GroupRefusals(unittest.TestCase):
    def service(self, tick=100.):
        source = (ROOT / '4_World/Groups/HCGroupService.c').read_text()
        source = source.replace('peer.RateCount++;', 'peer.RateCount = peer.RateCount + 1;')
        source = source.replace('m_GlobalCount++;', 'm_GlobalCount = m_GlobalCount + 1;')
        source = source.replace('s_Instance', 'm_StaticInstance')
        self.logs, self.tick, self.server = [], tick, True
        env = dict(EArray=EArray, len=len, str=str, Print=self.logs.append,
                   GetGame=lambda: N(IsServer=lambda: self.server, GetTickTime=lambda: self.tick),
                   HCGroupRules=N(SettingsValid=lambda config: bool(config and config.valid)))
        service = authored(source, 'HCGroupService', env, ('Admit', 'HCRefuse', 'HCStartBlock', 'Refusal'))()
        service.m_Refusal = ''
        service.m_StaticInstance = None
        service.m_Config = N(MaxRequestsPerSecond=2)
        service.m_GlobalWindow = 100.
        service.m_GlobalCount = 0
        return service

    def test_request_admission_names_clock_and_rate_refusals_once(self):
        service = self.service()
        peer = N(RateWindow=100., RateCount=0)
        self.assertEqual([True, True, False, False], [service.Admit(peer) for _ in range(4)])
        self.tick = 99.
        self.assertFalse(service.Admit(peer))
        self.tick = float('nan')
        self.assertFalse(service.Admit(peer))
        self.assertFalse(service.Admit(peer))
        self.assertEqual(['[HC Groups] refused reason=' + reason for reason in
                          ('rate_limited', 'clock_rollback', 'clock_invalid')], self.logs)

    def test_start_block_reports_why_the_service_will_not_start(self):
        service = self.service()
        good = N(valid=True, Enabled=True)
        self.assertEqual('', service.HCStartBlock(good))
        self.assertEqual('settings_invalid', service.HCStartBlock(N(valid=False, Enabled=True)))
        self.assertEqual('settings_invalid', service.HCStartBlock(None))
        self.assertEqual('disabled', service.HCStartBlock(N(valid=True, Enabled=False)))
        service.m_StaticInstance = object()
        self.assertEqual('already_started', service.HCStartBlock(good))
        service.m_StaticInstance = None
        self.server = False
        self.assertEqual('not_server', service.HCStartBlock(good))


class CampRespawnRefusals(unittest.TestCase):
    def module(self, utc=2000000000, can_open=True, loads=True, valid=True):
        source = (ROOT / '4_World/Camps/HCCampRespawn.c').read_text()
        source = source.replace('HCV2ThreatStore<HCCampRespawnState>', 'HCV2ThreatStore')
        source = source.replace('s_Instance', 'm_StaticInstance')
        self.logs, self.status = [], []
        env = dict(EArray=EArray, len=len, str=str, Print=self.logs.append, PATH='synthetic-path',
                   GetGame=lambda: N(IsServer=lambda: True, GetWorldName=lambda: 'synthetic'),
                   HCV2Admission=N(Line=lambda *args: 'synthetic admission line'),
                   HCGroupClock=N(Utc=lambda: utc), FileExist=lambda path: True,
                   HCV2ThreatStore=N(CanOpen=lambda path: can_open, Load=lambda path, limit, state: loads),
                   HCCampRespawnState=lambda: N(WorldName='', SavedUtc=0))
        module = authored(source, 'HCCampRespawnModule', env, ('OnStart', 'HCStartRefused'))()
        module.m_StaticInstance = None
        module.m_AdmissionPrinted = True
        module.m_State = N()
        module.m_Status = N(HCPublish=lambda state, reason: self.status.append((state, reason)))
        module.IsEnabled = lambda settings: True
        module.HCValid = lambda now: valid
        return module

    def test_each_start_refusal_publishes_status_and_logs_its_reason(self):
        for reason, options in (('clock_unavailable', dict(utc=0)), ('store_unavailable', dict(can_open=False)),
                                ('state_unreadable', dict(loads=False)), ('state_invalid', dict(valid=False))):
            module = self.module(**options)
            module.OnStart(N())
            self.assertIsNone(module.m_StaticInstance, reason)
            self.assertEqual([('refused', reason)], self.status, reason)
            self.assertIn('[HollowCountry] W5 camp-respawn start refused reason=' + reason + '; vanilla fallback',
                          self.logs)

    def test_valid_start_publishes_ready(self):
        module = self.module()
        module.OnStart(N())
        self.assertIsNotNone(module.m_StaticInstance)
        self.assertEqual('ready', self.status[-1][0])


class LeadRefusals(unittest.TestCase):
    def test_store_open_failure_is_published_and_logged(self):
        source = (ROOT / '4_World/Leads/HCLeadModule.c').read_text()
        source = source.replace('s_Instance', 'm_StaticInstance')
        logs, status = [], []
        env = dict(EArray=EArray, len=len, str=str, Print=logs.append,
                   HCV2Admission=N(Line=lambda *args: 'synthetic admission line'),
                   HCV2Gates=N(Qualified=lambda gate: False),
                   HCLeadStore=lambda: N(Open=lambda: False))
        module = authored(source, 'HCLeadModule', env, ('OnStart', 'HCStartRefused'))()
        module.m_StaticInstance = None
        module.m_AdmissionPrinted = True
        module.m_Status = N(HCPublish=lambda state, reason: status.append((state, reason)))
        module.IsEnabled = lambda settings: True
        module.OnStart(N())
        self.assertIsNone(module.m_StaticInstance)
        self.assertEqual([('refused', 'lead_store_unavailable')], status)
        self.assertEqual(['[HC Leads] start refused reason=lead_store_unavailable'], logs)


class RadioRefusals(unittest.TestCase):
    def radio(self, channels, save=True):
        source = syntax_port((ROOT / '4_World/Leads/HCRadioChatter.c').read_text())
        logs, status = [], []
        env = dict(EArray=EArray, len=len, str=str, Print=logs.append,
                   GetGame=lambda: N(IsServer=lambda: True),
                   HCEventHCLeadStore=N(Get=lambda: store),
                   HCEventHCMorseRateStore=lambda: N(Open=lambda: None),
                   HCV2Admission=N(Line=lambda *args: 'synthetic admission line'),
                   HCV2Gates=N(Qualified=lambda gate: False),
                   FactionArray=lambda: EArray(['locals']),
                   HCEventHCRadioChannel=lambda: N(Faction='', Frequency=0.),
                   Frequency=lambda faction: 87.8)
        store = N(Healthy=lambda: True, Data=N(Channels=channels), Save=lambda: save)
        radio = authored(source, 'HCRadioChatter', env, ('OnStart', 'BeginChannel', 'HCRefuse', 'HCRefuseAs', 'Frequency'))()
        radio.m_StaticInstance = None
        radio.m_AdmissionPrinted = True
        radio.m_Store = store
        radio.m_Refusal = ''
        radio.m_Reports = 0
        radio.m_Ready = False
        radio.m_Channel = radio.m_Report = None
        radio.m_Listeners = EArray()
        radio.m_Fallback = EArray()
        radio.m_Facts = EArray()
        radio.m_FromFallback = False
        radio.m_Status = N(HCPublish=lambda state, reason: status.append((state, reason)))
        return radio, logs, status

    def test_bad_channel_roster_publishes_degraded_and_logs_once_per_minute_retry(self):
        radio, logs, status = self.radio(EArray([N(Faction='locals')]))
        for _ in range(3):
            radio.BeginChannel()
        self.assertEqual([('degraded', 'channel_roster_invalid')] * 3, status)
        self.assertEqual(['[HC Plan] HC-20 radio=degraded morse=folded reports=0 reason=channel_roster_invalid runtime=PENDING'],
                         logs)

    def test_channel_store_save_failure_refuses_start_with_its_own_reason(self):
        radio, logs, status = self.radio(EArray(), save=False)
        settings = N(EnableLeads=True)
        radio.OnStart(settings)
        self.assertEqual(('refused', 'channel_store_save_failed'), status[-1])
        self.assertIn('[HC Plan] HC-20 radio=refused morse=folded reports=0 reason=channel_store_save_failed runtime=PENDING',
                      logs)
        self.assertFalse(radio.m_Ready)


class EventModuleStartRefusals(unittest.TestCase):
    def module(self, enabled, admitted):
        source = (ROOT / '4_World/Events/HCEventModule.c').read_text()
        source = re.sub(r'GetGame\(\)\.GetWorldName\((\w[\w.]*)\);', r'\1 = GetGame().GetWorldName();', source)
        source = re.sub(r'\bs_(Instance|CleanupOwner)\b', r'HCEventModule.s_\1', source)
        env = er.environment()
        logs = []
        env['Print'] = logs.append
        env['GetGame'] = lambda: N(IsServer=lambda: True, GetTickTime=lambda: 1.)
        env['HCEventQualification'] = N(Admitted=lambda: admitted)
        cls = type('AuthoredModule', (), {'s_Instance': None, 's_CleanupOwner': None})
        env['HCEventModule'] = cls
        for name in ('OnStart', 'HCStartRefused', 'HCStartRefusal'):
            if re.search(r'\b(?:bool|int|float|string|void|vector|HCEvent\w+) ' + name + r'\(', source):
                setattr(cls, name, translate(source, name, env, 'HCEventModule', True))
        module = cls()
        module.m_Config = N(Enabled=enabled)
        module.m_StartRefusal = ''
        module.OnStop = lambda: None
        module.HCStartSituations = lambda settings: None
        return module, logs

    def test_operator_off_and_local_opt_out_each_log_a_reason(self):
        for enabled, admitted, reason in ((False, True, 'operator_off'), (True, False, 'local_acceptance_opt_out')):
            module, logs = self.module(enabled, admitted)
            module.OnStart(N())
            self.assertEqual(['[HC Events] legacy events not started reason=' + reason], logs)
            self.assertEqual(reason, module.m_StartRefusal)


if __name__ == '__main__':
    unittest.main()
