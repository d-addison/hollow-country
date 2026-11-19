"""Wave 16 (w32-cellevents): Cellars, CellarSampler and Events report an honest `ready`.

Owner decision 2026-11-19: evidence gates that only wait for a native verdict are
admitted unverified; a module whose idle/deferred state is by design reports ready.
Restricted Enforce translation executes the authored bodies on explicit synthetic
fixtures. It is a test port, never DayZ evidence: runtime acceptance stays PENDING.
"""
from pathlib import Path
from types import MethodType, SimpleNamespace as N
import unittest

from tests.unit.test_infected_admission import translate as body_translate
from tests.unit.test_hc_operational_status import authored_status
from tests.unit.test_hc_situations import cached_status, director_fixture
from tests.unit.test_map_layers import EStr, translate as class_translate
from tests.unit.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'mods/HollowCountry/scripts'
ADMISSION = SCRIPTS / '3_Game/Atmosphere/HCCellarAdmission.c'
CELLARS = SCRIPTS / '4_World/Atmosphere/HCCellarsModule.c'
SAMPLER = SCRIPTS / '4_World/Interiors/HCCellarSampler.c'
DIRECTOR = SCRIPTS / '4_World/Events/HCSituationDirector.c'
EVENTS = SCRIPTS / '4_World/Events/HCEventModule.c'
MARKER = '$profile:HollowCountry/measure-cellars'
UNVERIFIED = 'admitted_unverified_native_cellar_qualification_pending'


class CellarAdmission(unittest.TestCase):
    def test_admission_is_admitted_unverified_not_closed(self):
        admitted = body_translate(str(ADMISSION), 'static bool HCAdmitted(', ())(None)
        reason = body_translate(str(ADMISSION), 'static string HCReason(', ())(None)
        self.assertTrue(admitted, 'native cellar qualification only waits for a verdict')
        self.assertEqual(reason, UNVERIFIED)

    def test_module_starts_ready_and_prints_one_unverified_receipt(self):
        logs = []
        make_status, _ = authored_status(logs)
        module = N(m_HC31Status=make_status(), m_HC31Started=False, m_MeasuredClasses=0, m_PendingClasses=28,
                   m_Survey=None, m_Measurement=None)
        module.HCReadCounts = lambda: True
        gate = N(HCAdmitted=lambda: True, HCReason=lambda: UNVERIFIED)
        module.HCReceipt = MethodType(body_translate(str(CELLARS), 'protected void HCReceipt(', (), Print=logs.append), module)
        lines = []
        start = body_translate(str(CELLARS), 'override void OnStart(', ('HCReadCounts', 'HCReceipt'),
                               Print=logs.append, HCCellarAdmission=gate,
                               HCV2Admission=N(Line=lambda *args: lines.append(args) or 'synthetic V2 line'),
                               HCV2Gates=N(Qualified=lambda *args: False))
        start(module, N(EnableAmbientLife=True))
        start(module, N(EnableAmbientLife=True))
        self.assertEqual((module.m_HC31Status.HCState(), module.m_HC31Status.HCReason()), ('ready', UNVERIFIED))
        receipts = [line for line in logs if line.startswith('[HC Plan] HC-31 cellar_measured=')]
        self.assertEqual(len(receipts), 1)
        self.assertIn('state=ready', receipts[0])
        self.assertNotIn('refused=', receipts[0])
        self.assertIn('runtime=PENDING', receipts[0])
        self.assertEqual(lines, [('Cellars', True, 'EXP-A3', False)], 'V2 admission line carries the real preference')

    def test_unreadable_counts_degrade_with_a_named_reason(self):
        logs = []
        make_status, _ = authored_status(logs)
        module = N(m_HC31Status=make_status(), m_HC31Started=False, m_MeasuredClasses=0, m_PendingClasses=0,
                   m_Survey=None, m_Measurement=None)
        module.HCReadCounts = lambda: False
        gate = N(HCAdmitted=lambda: True, HCReason=lambda: UNVERIFIED)
        module.HCReceipt = MethodType(body_translate(str(CELLARS), 'protected void HCReceipt(', (), Print=logs.append), module)
        start = body_translate(str(CELLARS), 'override void OnStart(', ('HCReadCounts', 'HCReceipt'),
                               Print=logs.append, HCCellarAdmission=gate,
                               HCV2Admission=N(Line=lambda *args: 'synthetic V2 line'),
                               HCV2Gates=N(Qualified=lambda *args: False))
        start(module, N(EnableAmbientLife=True))
        self.assertEqual((module.m_HC31Status.HCState(), module.m_HC31Status.HCReason()),
                         ('degraded', 'measurement_counts_unavailable'))


class SamplerIdle(unittest.TestCase):
    def sampler(self, server=True, marker=False):
        logs = []
        make_status, _ = authored_status(logs)
        started = []
        owner = N(m_Status=make_status(), m_Data=None, m_MeasuredClasses=0, m_Running=False)
        owner.HCStart = lambda: started.append('start') or True
        game = N(IsServer=lambda: server)
        env = dict(Print=logs.append, GetGame=lambda: game, FileExist=lambda path: marker and path == MARKER,
                   MARKER=MARKER)
        owner.HCReceipt = MethodType(body_translate(str(SAMPLER), 'protected void HCReceipt(', (), **env), owner)
        owner.IsEnabled = MethodType(body_translate(str(SAMPLER), 'override bool IsEnabled(', ('HCReceipt',), **env), owner)
        owner.OnStart = MethodType(body_translate(str(SAMPLER), 'override void OnStart(', ('HCStart', 'HCReceipt', 'IsEnabled'), **env), owner)
        return owner, logs, started

    def test_server_without_marker_is_ready_idle_and_does_nothing(self):
        owner, logs, started = self.sampler()
        self.assertTrue(owner.IsEnabled(N()))
        owner.OnStart(N())
        self.assertEqual((owner.m_Status.HCState(), owner.m_Status.HCReason()), ('ready', 'idle_waiting_for_measure_marker'))
        self.assertEqual(started, [], 'no marker: no store, scan or allocation')
        self.assertFalse(owner.m_Running)
        self.assertTrue(any('runtime=PENDING' in line for line in logs))

    def test_marker_present_still_starts_the_measurement(self):
        owner, logs, started = self.sampler(marker=True)
        self.assertTrue(owner.IsEnabled(N()))
        owner.OnStart(N())
        self.assertEqual(started, ['start'])

    def test_non_server_stays_off(self):
        owner, logs, started = self.sampler(server=False)
        self.assertFalse(owner.IsEnabled(N()))
        self.assertEqual((owner.m_Status.HCState(), owner.m_Status.HCReason()), ('off', 'not_server'))


def events_module(enabled=True, config_enabled=True, bind=None, provider_ready=False):
    """Real HCEventModule situation bodies over a real director and stub sibling owners."""
    receipts = []
    state = {'source': None}
    run = director_fixture(enabled=False, ready=provider_ready)
    run.owner.HCClose()  # reopen as a fresh, unopened director
    director_fixture_owner = run.owner
    ports = N(HCReady=lambda: provider_ready, HCRefusal=lambda: EStr('SURVIVOR_PROVIDER_UNAVAILABLE'))
    native = N(game=N(IsServer=lambda: True, GetTickTime=lambda: 200))
    published = []
    source_text = EVENTS.read_text().replace('    protected ', '    ').replace('    override ', '    ')
    for field in ('s_SituationOwner', 's_Instance', 's_CleanupOwner'):
        source_text = source_text.replace(field, 'HCEventModule.' + field)
    source_text = source_text.replace('this', 'self').replace('array<ref HCEventMission> ', 'Roster ')
    raid = N(HCOpen=lambda cfg, flag: None, HCProfilesEnabled=lambda: False, HCStatus=lambda: cached_status(),
             HCClose=lambda: None)
    transit = N(HCOpen=lambda flag: None, HCFind=lambda ident: None, HCStatus=lambda: cached_status(),
                HCClose=lambda: None)
    raid_factory = lambda: raid
    raid_factory.HCLoad = lambda: None
    env = dict(GetGame=lambda: native.game, HCV2Admission=N(Admitted=lambda preference: preference),
               Print=receipts.append, HCEventModule=N(s_SituationOwner=None, s_Instance=None, s_CleanupOwner=None),
               HCSituationDirector=lambda: director_fixture_owner, HCCampRaidSituation=raid_factory,
               HCTransitSituation=lambda: transit,
               HCSituationActors=N(HCForProfile=lambda profile: ports),
               HCSituationSource=N(HCState=lambda: state['source'], HCStore=lambda: state['source'] and N(Save=lambda value: True)),
               HCGroupClock=N(Utc=lambda: 1577836900),
               HCOperationalContributors=N(HCRegisterOwner=lambda name: N(
                   HCObserve=lambda requested, status, now: published.append((name, status.HCState())))))
    names = ('HCStartSituations', 'HCStepSituations', 'HCPublishSituations', 'HCCloseSituations',
             'HCGetOperationalStatus')
    class_translate(source_text, 'HCEventModule', env, only=names)
    module = N(m_SituationStatus=cached_status(), m_Situations=None, m_Raids=None, m_Transit=None,
               m_Config=N(Enabled=config_enabled), m_SourceAttempted=False, m_SituationEnabled=False,
               m_ProviderNoted=EStr(''))
    for name in names:
        setattr(module, name, MethodType(env[name], module))
    return module, run, state, receipts, published


class EventsReadyAtBoot(unittest.TestCase):
    def test_director_defers_to_first_tick_and_reports_ready_at_boot(self):
        module, run, state, receipts, _ = events_module()
        before = sum('HC-38' in line for line in run.logs)
        module.HCStartSituations(N(EnableEncounters=True))
        status = module.HCGetOperationalStatus()
        self.assertEqual(status.HCState(), 'ready', 'scene source binds after Events starts (registry order)')
        self.assertEqual(status.HCReason(), 'situation_source_binds_on_first_tick')
        self.assertEqual(sum('HC-38' in line for line in run.logs) - before, 1, 'one HC-38 receipt at start')

    def test_first_tick_without_a_bound_source_is_refused_by_name(self):
        module, run, state, receipts, _ = events_module()
        module.HCStartSituations(N(EnableEncounters=True))
        before = sum('HC-38' in line for line in run.logs)
        module.HCStepSituations()
        status = module.HCGetOperationalStatus()
        self.assertEqual((status.HCState(), status.HCReason()), ('refused', 'SITUATION_SOURCE_UNAVAILABLE'))
        module.HCStepSituations()
        self.assertEqual(sum('HC-38' in line for line in run.logs) - before, 1, 'no retry loop: refused receipt printed once')

    def test_bound_source_with_missing_provider_stays_ready_with_one_named_line(self):
        module, run, state, receipts, _ = events_module()
        module.HCStartSituations(N(EnableEncounters=True))
        state['source'] = run.state
        module.HCStepSituations()
        status = module.HCGetOperationalStatus()
        self.assertEqual(status.HCState(), 'ready')
        self.assertEqual(status.HCReason(), 'situation_director_running_actor_provider_pending')
        module.HCStepSituations()
        pending = [line for line in receipts if line.startswith('[HC Events] situation actor provider pending')]
        self.assertEqual(len(pending), 1)
        self.assertIn('reason=NO_OBSERVED_SURVIVOR', pending[0], 'the port refusal text is named')
        self.assertIn('runtime=PENDING', pending[0])

    def test_operator_off_stays_off(self):
        module, run, state, receipts, _ = events_module()
        module.HCStartSituations(N(EnableEncounters=False))
        status = module.HCGetOperationalStatus()
        self.assertEqual((status.HCState(), status.HCReason()), ('off', 'operator_off'))

    def test_shipped_stories_source_is_the_default_enabled_schedule(self):
        # The source Events waits for is bound by HCScenesModule when HC-19 starts; its
        # default config enables stories, so shipped data needs no new mission file.
        text = (SCRIPTS / '4_World/Scenes/HCStorySchedule.c').read_text()
        self.assertIn('bool EnableStories = true;', text)


if __name__ == '__main__':
    unittest.main()
