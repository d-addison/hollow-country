"""Wave 16 (w32-cellevents): Cellars, CellarSampler and Events report an honest `ready`.

Owner decision 2026-11-19: evidence gates that only wait for a native verdict are
admitted unverified; deferred source binding stays pending until validated.
Restricted Enforce translation executes the authored bodies on explicit synthetic
fixtures. It is a test port, never DayZ evidence: runtime acceptance stays PENDING.

Fix round 1 / P1 readiness + P2 startup binding (2026-11-19):
  RED command: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_wave16_cellevents.EventsReadyAtBoot -v
  Actual RED: AssertionError: 'ready' != 'started' : unopened director must not announce readiness
  Ran 5 tests; FAILED (failures=4), including bound/unavailable/invalid sequences.
  The first implementation exposed that HCOperationalStatus rejects "started";
  use its supported "requested" pending state (no shared status API change).
  GREEN command: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_wave16_cellevents.EventsReadyAtBoot -v
  Ran 5 tests; OK. Replaced the old premature-ready assertion and removed the
  string-only EnableStories check in favor of authored Scenes startup/binding.
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
    state = {'source': None, 'store': None}
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
               HCSituationSource=N(HCState=lambda: state['source'], HCStore=lambda: state['store']),
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
    def test_director_defers_to_first_tick_and_reports_pending_at_boot(self):
        module, run, state, receipts, _ = events_module()
        before = sum('HC-38' in line for line in run.logs)
        module.HCStartSituations(N(EnableEncounters=True))
        status = module.HCGetOperationalStatus()
        self.assertEqual(status.HCState(), 'requested', 'unopened director must not announce readiness')
        self.assertEqual(status.HCReason(), 'situation_source_pending')
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
        state['store'] = N(Save=lambda value: True)
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

    def test_scenes_startup_binding_drives_events_status_sequence(self):
        from tests.unit.test_hc_story_module import StoryModuleBehavior

        # Explicit synthetic HC-19 admission/store/native fixtures. Execute the
        # authored Scenes startup and source accessors, then the real director's
        # validation. These fixtures establish no shipped/native data acceptance.
        for case in ('bound', 'unavailable', 'invalid'):
            with self.subTest(source=case):
                module, run, state, receipts, _ = events_module()
                ports = dict(HCSituationSource=N(s_State=None, s_Store=None))
                source = DIRECTOR.read_text().replace('s_State', 'HCSituationSource.s_State')
                source = source.replace('s_Store', 'HCSituationSource.s_Store')
                class_translate(source, 'HCSituationSource', ports, only=('HCBind', 'HCState', 'HCStore'))
                # Reuse the module translation's explicit binding port; the
                # store below is the exact instance owned by Scenes.
                fixture = StoryModuleBehavior()
                scenes = fixture.owner()
                scenes.m_Running = False
                scenes.m_AdmissionPrinted = True
                scenes.m_SummaryPrinted = True
                scenes.IsEnabled = lambda settings: True
                scenes.m_SaveJob = None
                live = run.state
                if case == 'invalid':
                    # Explicit native-shaped version-0 row that still carries an identity.
                    live.Stories.HCFirstSurvivor = N(Version=0, Profile=EStr(''), Id=EStr('hc-story-5-survivor'),
                        StorySequence=0, DueAt=0, EndsAt=0, Phase=EStr(''), Outcome=EStr(''), Lease=EStr(''), Refusal=EStr(''))
                store = N(Open=lambda now: None if case == 'unavailable' else live,
                          Save=lambda value: True)
                bindings = []

                def bind_source(value, owner_store):
                    ports['HCBind'](value, owner_store)
                    bindings.append((value, owner_store))
                    state['source'] = ports['HCState']()
                    state['store'] = ports['HCStore']()

                fixture.env.update(
                    GetGame=lambda: N(IsServer=lambda: True, GetWorldName=lambda: 'chernarusplus'),
                    HCSceneChainStore=lambda: store,
                    HCStoryPolicy=N(HCLoadConfig=lambda: N(EnableStories=True)),
                    HCStorySchedule=lambda: N(HCStart=lambda *args: True, HCReason=lambda: ''),
                    HCSituationSource=N(HCBind=bind_source),
                    HCSceneSaveJob=lambda: N(), HCSaveScheduler=N(HCRegister=lambda job: None))
                fixture.bind(scenes, 'OnStart')
                module.HCStartSituations(N(EnableEncounters=True))
                status = module.HCGetOperationalStatus()
                sequence = [(status.HCState(), status.HCReason())]
                self.assertFalse(run.owner.m_Enabled)
                self.assertIsNone(run.owner.m_State)
                self.assertIsNone(run.owner.m_Store)
                scenes.OnStart(N(EnableEncounters=True))
                if case != 'unavailable':
                    self.assertEqual(bindings, [(live, store)])
                    self.assertIs(ports['HCStore'](), scenes.m_Store)
                else:
                    self.assertEqual(bindings, [])
                before = len(run.logs)
                module.HCStepSituations()
                sequence.append((status.HCState(), status.HCReason()))
                expected = {
                    'bound': ('ready', 'situation_director_running_actor_provider_pending'),
                    'unavailable': ('refused', 'SITUATION_SOURCE_UNAVAILABLE'),
                    'invalid': ('refused', 'SITUATION_STATE_INVALID'),
                }
                self.assertEqual(sequence, [('requested', 'situation_source_pending'), expected[case]])
                self.assertEqual(run.owner.m_Enabled, case == 'bound')
                if case == 'bound':
                    self.assertIs(run.owner.m_State, scenes.m_State)
                    self.assertIs(run.owner.m_Store, scenes.m_Store)
                else:
                    self.assertIsNone(run.owner.m_State)
                    self.assertIsNone(run.owner.m_Store)
                module.HCStepSituations()
                self.assertEqual(len(run.logs) - before, 1, 'one bind/refusal receipt; no retry loop')


if __name__ == '__main__':
    unittest.main()
