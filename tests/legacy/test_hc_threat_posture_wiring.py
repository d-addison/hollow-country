"""HC-47 / HC-45 integration behavior on explicit synthetic native ports.

Task contract: .banso-writer/inputs/task.md; shared trace remains lead-owned.
Uses the existing threat/posture translators, not a Python gameplay model.
Offline execution establishes no DayZ compile, geometry, animation or wake proof.
Runtime acceptance remains PENDING.

Actual RED/GREEN command:
python3 -B -m unittest tests.legacy.test_hc_threat_posture_wiring -v
RED: Ran 8 tests; FAILED (failures=10). Examples: "refused crawler idle
entered posed room", "reach start did not reset before native setup", "sitter
reported pose ownership despite refused sit admission", and "startup did not
close stale vision admission before modules". No production edits preceded RED.
GREEN: same command -> Ran 8 tests; OK. Synthetic execution only.
"""
import math
from types import SimpleNamespace as N
import unittest

from tests.legacy.test_admin_test_kit import Cell, compile_authored
from tests.legacy.test_core_lifecycle import fixture as server_fixture
from tests.legacy.test_event_runtime import translate as scalar
from tests.legacy.test_hc_threat_matrix import Vec, WORLD, POLICY, MINDS
from tests.legacy.test_infected_admission import Array, StartedModule, translate
from tests.legacy.test_infected_reach import policy
from tests.legacy.test_v1_native_noise_vision import VisionWorld

REACH = POLICY.with_name('HCInfectedReachModule.c')
ADMISSION = WORLD / 'Infected/Variety/HCPostureAdmission.c'
VARIETY = ADMISSION.with_name('HCInfectedVarietyPolicy.c')
ADMIN = WORLD / 'Admin/HCAdminDirectors.c'


def posture_policy():
    owner = N()
    for name in ('HCCanEnter', 'HCPostureRefusal'):
        setattr(owner, name, scalar(ADMISSION.read_text(), name, {}, 'HCPostureAdmission'))
    return owner


def vision_ports(events, healthy=lambda: True):
    """Authored vision gate; synthetic marker/clock supplied by VisionWorld."""
    world = VisionWorld()
    gate = world.ns['HCInfectedVisionQualification']
    reset, admit = gate.HCThreatReset, gate.Admitted
    def observed_reset(enabled):
        events.append(('reset', enabled, healthy()))
        reset(enabled)
    def observed_admit():
        events.append(('admit', gate.HCThreatState(), healthy()))
        return admit()
    return gate, N(HCThreatReset=observed_reset, Admitted=observed_admit)


class ThreatLifecycleWiring(unittest.TestCase):
    def test_server_resets_before_modules_and_prints_effective_summary_once_per_start(self):
        for enabled, healthy in ((True, True), (True, False), (False, False)):
            with self.subTest(enabled=enabled, healthy=healthy):
                events, logs = [], []
                gate, ports = vision_ports(events)
                gate.HCThreatReset(True)
                gate.Admitted()  # explicit stale prior-session admission
                summary = scalar(POLICY.read_text(), 'HCThreatSummary', dict(
                    HCInfectedReachPolicy=policy(),
                    HCInfectedVisionQualification=gate,
                    HCInfectedRoomCatalog=N(HCThreatRoomReason=lambda: 'room_path_receipts_pending')),
                    'HCInfectedReachPolicy')
                def start(settings):
                    events.append(('module-start', gate.HCThreatState()))
                    if healthy:
                        ports.HCThreatReset(True)
                        ports.Admitted()
                module = N(GetName=lambda: 'synthetic-infected',
                           IsEnabled=lambda settings: settings.EnableInfected,
                           OnStart=start, HCGetOperationalStatus=lambda: None,
                           OnStop=lambda: ports.HCThreatReset(False))
                def printed(line):
                    logs.append(line)
                    if '[HC Plan] HC-47 ' in line:
                        events.append(('summary', gate.HCThreatState()))
                state, _ = server_fixture(modules=[module], ports=dict(
                    HCInfectedVisionQualification=ports,
                    HCInfectedReachPolicy=N(HCThreatSummary=summary), Print=printed))
                state.m_Settings.EnableInfected = enabled
                state.Start()
                self.assertEqual([('reset', False, True)], events[:1],
                                 'startup did not close stale vision admission before modules')
                if enabled:
                    self.assertEqual(('module-start', 'off'), events[1])
                lines = [line for line in logs if '[HC Plan] HC-47 ' in line]
                self.assertEqual(1, len(lines), 'startup must print exactly one threat summary')
                effective = 'on' if healthy else 'off'
                self.assertIn('vision=' + effective, lines[0])
                self.assertIn('reach=' + ('refused' if enabled else 'off'), lines[0])
                self.assertIn('runtime=PENDING', lines[0])
                self.assertEqual(('summary', effective), events[-1])
                state.Start()  # already-started guard must suppress a second summary
                self.assertEqual(1, sum('[HC Plan] HC-47 ' in line for line in logs))
                state.Stop()
                state.Start()
                self.assertEqual(2, sum('[HC Plan] HC-47 ' in line for line in logs))

    def infected_fixture(self, **options):
        fixture = StartedModule(**options)
        events = []
        gate, ports = vision_ports(events, lambda: fixture.ctx.m_Healthy)
        namespace = fixture.namespace
        fixture.namespace = lambda: namespace(HCInfectedVisionQualification=ports,
            HCInfectedSelfTests=N(Run=lambda: False))
        fixture.ctx.ReleasePacks = lambda: events.append(('release', gate.HCThreatState()))
        quarantine = fixture.module_function('protected void Quarantine(')
        fixture.ctx.Quarantine = lambda reason: quarantine(fixture.ctx, reason)
        return fixture, gate, events

    def test_healthy_infected_start_resets_then_observes_admission_and_stop_closes_first(self):
        fixture, gate, events = self.infected_fixture()
        fixture.start()
        self.assertTrue(fixture.ctx.m_Healthy)
        self.assertEqual([('reset', True, True), ('admit', 'pending', True)], events,
                         'healthy startup must reset then observe vision admission')
        self.assertEqual('on', gate.HCThreatState())
        fixture.ctx.ReleasePacks = lambda: events.append(('release', gate.HCThreatState()))
        fixture.stop()
        self.assertEqual(('reset', False, True), events[2], 'stop must close vision before cleanup')
        self.assertEqual(('release', 'off'), events[3])
        self.assertEqual('off', gate.HCThreatState())

    def test_quarantine_closes_vision_before_cleanup_and_unhealthy_start_never_admits(self):
        fixture, gate, events = self.infected_fixture(work=3)
        gate.HCThreatReset(True)
        gate.Admitted()
        fixture.start()
        self.assertEqual(('reset', False, False), events[0], 'quarantine must reset stale vision')
        self.assertEqual(('release', 'off'), events[1])
        self.assertFalse(fixture.ctx.m_Healthy)
        self.assertEqual('off', gate.HCThreatState())
        self.assertFalse(any(event[0] == 'admit' for event in events))

    def test_diag_policy_failure_cannot_reopen_vision(self):
        fixture, gate, events = self.infected_fixture(RunPolicySelfTests=True)
        gate.HCThreatReset(True)
        gate.Admitted()  # explicit stale prior-session admission
        fixture.module_function('override void OnStart(', diag=True)(fixture.ctx, fixture.settings)
        self.assertFalse(fixture.ctx.m_Healthy)
        self.assertEqual('off', gate.HCThreatState(), 'DIAG quarantine reopened vision admission')
        self.assertFalse(any(event[0] == 'admit' for event in events))


class ReachWiring(unittest.TestCase):
    def test_start_stop_reset_real_contact_budget_and_repeated_start_does_not_refill(self):
        p = policy()
        p.s_HCThreatBudget, p.s_HCThreatBudgetAfter = object(), 100.
        events = []
        reset = translate(str(POLICY), 'static void HCThreatResetBudget(', (),
                          statics=('s_HCThreatBudget', 's_HCThreatBudgetAfter'), STATICS=p)
        def observed_reset():
            events.append('reset')
            reset(None)
        p.HCThreatResetBudget = observed_reset
        owner = N(m_Running=False, m_States=Array(), m_Vehicles=Array(), m_Live=0,
                  m_VaultActive=0, IsEnabled=lambda settings: settings.EnableInfected)
        statics = N(s_Instance=None, SLOTS=16)
        env = dict(STATICS=statics, this=owner, HCInfectedReachPolicy=p,
                   GetGame=lambda: N(IsServer=lambda: True, GetTickTime=lambda: 10.),
                   PGFilter=lambda: N(SetFlags=lambda *a: events.append('filter'), SetCost=lambda *a: None),
                   PGPolyFlags=N(**{name: 0 for name in ('WALK', 'DOOR', 'INSIDE', 'DISABLED',
                       'UNREACHABLE', 'SWIM', 'SWIM_SEA', 'LADDER', 'JUMP', 'CLIMB', 'CRAWL', 'CROUCH', 'NONE')}),
                   PGAreaType=N(DOOR_CLOSED=0), HCV2Admission=N(Line=lambda *a: 'synthetic'), Print=lambda line: None)
        start = translate(str(REACH), 'override void OnStart(', ('IsEnabled',),
                          statics=('s_Instance', 'SLOTS'), **env)
        stop = translate(str(REACH), 'override void OnStop(', (), statics=('s_Instance',), **env)
        settings = N(EnableInfected=True)
        start(owner, settings)
        self.assertEqual(['reset', 'filter'], events, 'reach start did not reset before native setup')
        self.assertIsNone(p.s_HCThreatBudget)
        self.assertEqual(0, p.s_HCThreatBudgetAfter)
        p.s_HCThreatBudget, p.s_HCThreatBudgetAfter = object(), 42.
        start(owner, settings)
        self.assertEqual(42., p.s_HCThreatBudgetAfter, 'repeated start refilled a running budget')
        stop(owner)
        self.assertEqual(['reset', 'filter', 'reset'], events)
        self.assertIsNone(p.s_HCThreatBudget)
        self.assertEqual(0, p.s_HCThreatBudgetAfter)
        self.assertIsNone(statics.s_Instance)
        self.assertFalse(owner.m_Running)

    def test_forced_movement_refusal_skips_vault_backoff_and_navmesh_work(self):
        p = policy()
        supported = [False]
        p.HCForcedMovementSupported = lambda: supported[0]  # explicit hypothetical qualification
        calls = []
        target = N(IsAlive=lambda: True, GetPosition=lambda: Vec([0., 1., 1.]),
                   GetCommand_Vehicle=lambda: None)
        infected = N(IsAlive=lambda: True, GetPosition=lambda: Vec([0., 0., 0.]),
                     GetInputController=lambda: N(GetMindState=lambda: 4, GetTargetEntity=lambda: target))
        owner = N(m_VaultActive=0, m_VaultRetired=False, m_Backoffs=0, m_FirstBackoff=False,
                  FloorVehicle=lambda target: None, LineCheck=lambda *a: calls.append('line') or True,
                  OnWalkableNavmesh=lambda pos: calls.append('navmesh') or False,
                  VaultOutcome=lambda *a: calls.append('vault-outcome'),
                  FacingDegrees=lambda *a: calls.append('facing') or 0,
                  ContactDistance=lambda *a: calls.append('contact') or 1,
                  Release=lambda *a: self.fail('valid synthetic slot released'))
        evaluate = translate(str(REACH), 'protected void Evaluate(',
            ('FloorVehicle', 'LineCheck', 'OnWalkableNavmesh', 'VaultOutcome',
             'FacingDegrees', 'ContactDistance', 'Release'), HCInfectedReachPolicy=p,
            DayZInfectedConstants=MINDS, vector=N(Distance=math.dist), Print=lambda line: None)
        evaluate.__globals__['Math'].Sqrt = math.sqrt
        evaluate.__globals__['Math'].RandomInt = lambda low, high: low
        def fresh():
            return N(Infected=infected, Target=target, Expires=30., Admitted=0.,
                     Phase=0, VaultType=-1, NextVault=100., BackoffAfter=0., LastReachHit=0.)
        state = fresh()
        evaluate(owner, 0, state, 10.)
        self.assertEqual(['line'], calls, 'refused forced movement still evaluated vault/backoff geometry')
        self.assertEqual(0, state.Phase)
        self.assertEqual(-1, state.VaultType)
        supported[0] = True
        calls.clear()
        state = fresh()
        evaluate(owner, 0, state, 10.)
        self.assertIn('vault-outcome', calls, 'hypothetical positive control never reached vault evaluation')
        self.assertEqual(1, state.Phase, 'hypothetical positive control never reached backoff evaluation')
        self.assertEqual(1, owner.m_Backoffs)


class PostureWiring(unittest.TestCase):
    def test_posed_room_refuses_before_capacity_when_crawler_idle_is_not_admitted(self):
        p = posture_policy()
        requested = []
        admitted = [False]
        real = p.HCCanEnter
        p.HCCanEnter = lambda mode: requested.append(mode) or (admitted[0] and real(mode))
        room = scalar(VARIETY.read_text(), 'PosedRoom', dict(HCPostureAdmission=p))
        for near in (True, False):
            self.assertFalse(room(near, 0, 0, 4, 12), 'refused crawler idle entered posed room')
        self.assertEqual(['native_crawler_idle'] * 2, requested)
        admitted[0] = True
        self.assertTrue(room(True, 3, 9, 4, 0))
        self.assertFalse(room(True, 4, 0, 4, 12))
        self.assertTrue(room(False, 4, 0, 4, 12))
        self.assertFalse(room(False, 0, 2, 12, 2))

    def test_sitter_spawn_tracks_one_body_and_reports_actual_pose_refusal(self):
        p = posture_policy()
        created, tracked, deleted = [], [], []
        body = N()
        def create(*args):
            created.append(args)
            return body
        class SitterVec(Vec):
            def __mul__(self, value): return SitterVec(x * value for x in self)
            def __add__(self, other): return SitterVec(a + b for a, b in zip(self, other))
        player = N(GetDirection=lambda: SitterVec([0., 0., 1.]),
                   GetPosition=lambda: SitterVec([10., 0., 10.]))
        env = dict(HCPostureAdmission=p, HCAdminPlacement=N(HCClear=lambda pos: True),
                   ZombieBase=N(Cast=lambda value: value), ECE_INITAI=1, ECE_PLACE_ON_SURFACE=2,
                   GetGame=lambda: N(SurfaceY=lambda *a: 0., CreateObjectEx=create, ObjectDelete=deleted.append),
                   Math=N(Min=min, Sqrt=math.sqrt))
        fn = compile_authored(ADMIN, 'HCInfectedModule', 'HCAdminSitter', env, ('FindActor', 'Track'))
        owner = N(m_Healthy=True, m_Config=N(MaxTracked=24), m_State=N(), m_HCAdminSitter=None,
                  m_Actors=Array(), m_MemberCap=24, m_RegistrationAttempts=0, m_WorkCap=32,
                  FindActor=lambda actor: None, Track=lambda actor: tracked.append(actor) or True)
        reason = Cell()
        self.assertTrue(fn(owner, player, reason), 'body spawning must remain available')
        # Audit #121: the sit pair ships, so admission is granted (unverified) and the
        # addon owns the pose. A refusing policy still reports the actual refusal.
        self.assertIn('addon-owns-pose', reason.value)
        self.assertNotIn('pose-refused', reason.value)
        self.assertIs(body, owner.m_HCAdminSitter)
        self.assertEqual([body], tracked)
        self.assertEqual([('HC_ZmbM_Sitter', [10., 0., 18.], 3)], created)
        self.assertEqual([], deleted)
        self.assertFalse(fn(owner, player, reason))
        self.assertEqual('sitter-body-cap=1; includes-corpse', reason.value)
        self.assertEqual(1, len(created))

        refusing = N(HCCanEnter=lambda mode: False, HCPostureRefusal=p.HCPostureRefusal)
        env['HCPostureAdmission'] = refusing
        fn = compile_authored(ADMIN, 'HCInfectedModule', 'HCAdminSitter', env, ('FindActor', 'Track'))
        owner.m_HCAdminSitter = None
        reason = Cell()
        self.assertTrue(fn(owner, player, reason))
        self.assertIn('pose-refused:none_graph_admitted_unverified', reason.value)
        self.assertNotIn('addon-owns-pose', reason.value)


if __name__ == '__main__':
    unittest.main()
