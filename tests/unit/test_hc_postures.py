"""HC-45 / #121: one behavioral scenario on explicit synthetic native ports.

Spec FR-008/011, plan AC-007, task HC-45; HC-11 owns shared trace edits.
Restricted translation executes shipped Enforce methods, not a Python gameplay
model. No DayZ compile, animation, observer, wake or two-client proof.

Actual RED command (before implementation):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_postures -v
AssertionError: True is not false : unsupported posture 2 was admitted
GREEN: same command -> Ran 1 test; OK (offline only).

Wave 8 #173 spec: assigned task -> failed-roll cooldown + HC-1 posture state.
Plan/tasks: retain HC-14 cursor; cache per-body retry time; consume admission
status; test real owner availability; leave native rest/wake proof PENDING.
Actual RED (same focused command before each corresponding change):
  AssertionError: Tuples differ: ('degraded', 'native_crawler_idle_only_rest_wake_unverified') != ('refused', 'rest_wake_native_proof_pending')
  AssertionError: True is not false : failed roll rerolled before cooldown
  primary infected owner has no posture status hook
  startup claimed readiness before requested posture owner reported
GREEN:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_postures test_infected_sentinel_reads -v
Ran 3 tests; OK. The unavailable-owner reason was already wired in this base;
its strengthened regression now executes actual VarietyActive with Instance
missing/present/missing, rather than substituting the boolean predicate.
No new RED is claimed for that already-passing path. Cooldown default: 600 s.
No distances added; no runtime acceptance or production promotion.
"""
import json
from pathlib import Path
from types import MethodType, SimpleNamespace as N
import re
import unittest

from tests.unit.test_infected_admission import Array, translate
from tests.unit.test_event_runtime import translate as scalar
from tests.unit.test_hc_infected_doors import shared_budget
from tests.unit.test_hc_operational_status import authored_status
from tests.unit.test_infected_admission import StartedModule
from tests.unit.test_infected_lod import variety as variety_policy

ROOT = Path(__file__).resolve().parents[2]
POSE = ROOT / 'mods/HollowCountryAnims/scripts/4_World/HCPoseInfected.c'
NATIVE = ROOT / 'mods/HollowCountry/scripts/4_World/Infected/Variety/HCInfectedVarietyNative.c'
ADMISSION = NATIVE.with_name('HCPostureAdmission.c')


def bind(path, obj, names, env, statics=(), bound=()):
    for name in names:
        match = re.search(r'\b(?:bool|void|int|string) ' + name + r'\(', path.read_text())
        fn = translate(str(path), match[0], names + bound, statics=statics, **env)
        setattr(obj, name, MethodType(fn, obj))
    return obj


class PostureAdmission(unittest.TestCase):
    def test_primary_owner_exposes_cached_degraded_posture_and_closes_on_stop(self):
        fixture = StartedModule(hordes=False)
        make_row, _ = authored_status([])
        fixture.ctx.m_HCOwnerStatus = make_row()
        posture = make_row()
        posture.HCPublish('degraded', 'native_crawler_idle_only_rest_wake_unverified')
        observed = [None]
        namespace = fixture.namespace
        variety_owner = N(m_Running=True, HCGetOperationalStatus=lambda: observed[0])
        observed_getter = translate(str(NATIVE.with_name('HCInfectedVarietyModule.c')),
            'static HCOperationalStatus HCObservedStatus(', (), statics=('s_Instance',),
            STATICS=N(s_Instance=variety_owner))
        fixture.namespace = lambda: namespace(HCInfectedVarietyModule=N(
            HCObservedStatus=lambda: observed_getter(None)))
        source = NATIVE.parents[1] / 'HCInfectedModule.c'
        self.assertTrue('override HCOperationalStatus HCGetOperationalStatus()' in source.read_text(),
                      'primary infected owner has no posture status hook')
        getter = fixture.module_function('override HCOperationalStatus HCGetOperationalStatus(')
        fixture.start()
        self.assertEqual('degraded', getter(fixture.ctx).HCState(),
                         'startup claimed readiness before requested posture owner reported')
        self.assertEqual('posture_owner_start_pending', getter(fixture.ctx).HCReason())
        observed[0] = posture
        self.assertIs(posture, getter(fixture.ctx))
        self.assertEqual('degraded', getter(fixture.ctx).HCState())
        variety_owner.m_Running = False
        self.assertEqual('degraded', getter(fixture.ctx).HCState())
        variety_owner.m_Running = True
        observed[0] = None  # requested posture owner has not supplied a report
        self.assertEqual('degraded', getter(fixture.ctx).HCState())
        # #187: once the posture owner reports a non-degraded row the start
        # placeholder is cleared; a later degraded posture still surfaces.
        settled = make_row()
        settled.HCPublish('ready', 'posture_owner_running')
        observed[0] = settled
        self.assertEqual('ready', getter(fixture.ctx).HCState(),
                         'start-pending placeholder outlived the posture owner report')
        self.assertEqual('infected_owner_running_runtime_pending', getter(fixture.ctx).HCReason())
        observed[0] = None
        self.assertEqual('ready', getter(fixture.ctx).HCState())
        observed[0] = posture
        self.assertIs(posture, getter(fixture.ctx))
        fixture.stop()
        self.assertEqual('off', getter(fixture.ctx).HCState())
        self.assertEqual('infected_owner_stopped', getter(fixture.ctx).HCReason())
        fixture.ctx.ReleasePacks = lambda: None
        fixture.module_function('protected void Quarantine(')(fixture.ctx, 'synthetic_fault')
        self.assertEqual('refused', getter(fixture.ctx).HCState())
        self.assertEqual('synthetic_fault', getter(fixture.ctx).HCReason())
        # An explicit posture disable leaves native infected owner readiness.
        fixture.settings.EnableInfectedVariety = False
        fixture.start()
        observed[0] = None
        self.assertEqual('ready', getter(fixture.ctx).HCState())
        fixture.stop()

    def test_unsupported_transition_refuses_then_native_hold_wakes_once_and_queue_is_bounded(self):
        logs = []
        retry_seconds = float(re.search(r'HC_VARIETY_RETRY_SECONDS = ([0-9.]+);',
                                        NATIVE.read_text())[1])
        game = N(IsServer=lambda: True, GetTickTime=lambda: 0.)
        sitter = N(m_HCPose=0, m_HCHolding=False, m_HCStarted=False,
                   IsAlive=lambda: True)
        # Explicit synthetic body/authority and empty server-wide pose budget.
        env = dict(g_Game=game, GetGame=lambda: game, Print=logs.append,
                   STATICS=N(s_HCPosed=0, MAX_POSED=12))
        if ADMISSION.exists():
            policy = N()
            for name in ('HCCanEnter', 'HCPostureRefusal', 'HCPoseMode', 'HCLine'):
                setattr(policy, name, scalar(ADMISSION.read_text(), name,
                        dict(HCPostureAdmission=policy), 'HCPostureAdmission'))
            env['HCPostureAdmission'] = policy
        fn = translate(str(POSE), 'bool HCRequestPose(',
                       ('IsAlive',), statics=('s_HCPosed', 'MAX_POSED'), **env)
        self.assertFalse(fn(sitter, 2), 'unsupported posture 2 was admitted')
        for pose in (-1, 1, 3, 99):
            self.assertFalse(fn(sitter, pose))
        self.assertEqual(0, env['STATICS'].s_HCPosed)
        self.assertEqual(0, sitter.m_HCPose)
        self.assertTrue(fn(sitter, 0), 'cleanup request remains valid')
        self.assertEqual('POSTURE_MODE_UNSUPPORTED', policy.HCPostureRefusal('invented'))

        # A fixed support queue executes the authored shared budgets and keeps
        # its cursor on time exhaustion. It stores modes, never entity handles.
        world = NATIVE.parents[2]
        units = shared_budget(world / 'Core/HCUnitBudget.c', 'HCUnitBudget', {},
                              ('HCReset', 'HCTake', 'HCUsed'), game)
        work = shared_budget(world / 'World/HCWorkBudget.c', 'HCWorkBudget',
                             dict(m_LogAfter=0.),
                             ('HCReset', 'HCMayContinue', 'HCContinue'), game)
        statuses = []
        queue = N(m_Queue=Array(), m_Units=units, m_Work=work,
                  m_Status=N(HCPublish=lambda *args: statuses.append(args),
                             HCState=lambda: statuses[-1][0], HCReason=lambda: statuses[-1][1]),
                  m_Running=False, m_Cursor=0)
        queue_env = dict(env, HCPostureAdmission=policy,
                        HCV2Admission=N(Line=lambda *args: 'synthetic admission'))
        queue_env['HCLine'] = policy.HCLine
        bind(ADMISSION, queue, ('HCStart', 'HCSlice', 'HCStop'), queue_env)
        queue.HCStart(True)
        self.assertEqual(1, queue.m_Cursor)
        queue.HCStart(True)  # repeated start cannot refill the queue
        self.assertEqual(1, queue.m_Cursor)
        game.GetTickTime = lambda: .01  # synthetic clock advances beyond 4 ms
        # Force the shared clock guard to see elapsed time within this slice.
        clock = iter((0., .01))
        game.GetTickTime = lambda: next(clock)
        queue.HCSlice()
        self.assertEqual(1, queue.m_Cursor)
        game.GetTickTime = lambda: 0.
        for checked in (2, 3, 4):
            queue.HCSlice()
            self.assertEqual(checked, queue.m_Cursor)
            self.assertEqual(1, units.HCUsed())
        lines = [line for line in logs if '[HC Plan] HC-45 posture=' in line]
        self.assertEqual(4, len(lines))
        for mode in ('sit_wall', 'prone_sleep', 'riser'):
            line = next(line for line in lines if 'posture=' + mode + ' ' in line)
            self.assertIn('support=refused wake=refused state=refused', line)
            self.assertIn(policy.HCPostureRefusal(mode), line)
            self.assertIn('runtime=PENDING', line)
        # Drained and off queues must return before clocks/budgets/logging.
        game.GetTickTime = lambda: self.fail('drained/off queue sampled a clock')
        for _ in range(10): queue.HCSlice()
        queue.HCStop()
        self.assertEqual([], queue.m_Queue)
        queue.HCStart(False)
        queue.HCSlice()
        self.assertEqual(('off', 'operator_preference'), statuses[-1])
        game.GetTickTime = lambda: 0.
        queue.HCStart(True)
        self.assertEqual(1, queue.m_Cursor)
        queue.HCStop()

        # Execute HC-14 lifecycle extension. The inherited owner callbacks are
        # explicit synthetic ports; the extension's start/off/stop/status logic
        # is authored Enforce. No policy is reimplemented in Python.
        owner_statuses = []
        owner_report = N(HCPublish=lambda *args: owner_statuses.append(args))
        owner = N(m_HCPostures=None, m_Running=False, m_Variety=True,
                  m_HCVarietyStatus=owner_report, VarietyActive=lambda: False)
        owner_report.HCState = lambda: owner_statuses[-1][0] if owner_statuses else 'unknown'
        owner_report.HCReason = lambda: owner_statuses[-1][1] if owner_statuses else 'owner_state_unknown'
        # Execute the real availability predicate: quarantine/stop clears the
        # primary Instance; a missing owner must produce the named refusal.
        infected_port = N(Instance=None)
        active = translate(str(NATIVE.with_name('HCInfectedVarietyModule.c')),
            'static bool VarietyActive(', (), statics=('s_Instance',),
            STATICS=N(s_Instance=owner), HCInfectedModule=infected_port)
        owner.VarietyActive = lambda: active(None)
        owner_calls = []
        def inherited_start(settings):
            owner_calls.append('start')
            owner.m_Running = settings.synthetic_original_module_enabled
        def inherited_stop():
            owner_calls.append('stop')
            owner.m_Running = False
        inherited = N(IsEnabled=lambda settings: settings.synthetic_original_module_enabled,
                      OnStart=inherited_start, OnTick=lambda dt: owner_calls.append('tick'),
                      OnStop=inherited_stop)
        lifecycle = dict(env, super=inherited, HCPostureAdmission=lambda: queue)
        bind(NATIVE, owner, ('HCRefreshVarietyStatus',), lifecycle, bound=('VarietyActive',))
        for name in ('IsEnabled', 'OnStart', 'OnTick', 'OnStop'):
            fn_owner = translate(str(NATIVE), ('bool ' if name == 'IsEnabled' else 'void ') + name + '(',
                                 ('VarietyActive', 'HCRefreshVarietyStatus'), **lifecycle)
            setattr(owner, name, MethodType(fn_owner, owner))
        status_source = NATIVE.read_text().split('modded class HCInfectedVarietyModule', 1)[1]
        status_source = status_source.replace('HCOperationalStatus HCGetOperationalStatus',
                                              'string HCGetOperationalStatus')
        queue.HCStatus = lambda: queue.m_Status
        owner.HCGetOperationalStatus = MethodType(scalar(status_source,
            'HCGetOperationalStatus', {}, member=True), owner)
        disabled = N(synthetic_original_module_enabled=False)
        self.assertFalse(owner.IsEnabled(disabled))
        self.assertIs(owner_report, owner.HCGetOperationalStatus())
        self.assertEqual(('off', 'operator_preference'), statuses[-1])
        owner.OnTick(1.)
        self.assertEqual(0, queue.m_Cursor)
        owner.OnStop()
        self.assertIsNone(owner.m_HCPostures)
        enabled_owner = N(synthetic_original_module_enabled=True)
        self.assertTrue(owner.IsEnabled(enabled_owner))
        owner.OnStart(enabled_owner)
        self.assertEqual(1, queue.m_Cursor)
        self.assertEqual(('refused', 'infected_owner_unavailable_rest_wake_unverified'), owner_statuses[-1])
        owner.OnStart(enabled_owner)
        self.assertEqual(1, queue.m_Cursor)
        # Synthetic dependency starts later in the same lifecycle; no restart
        # or getter-side experiment may be needed to refresh the cached row.
        before_late_start = len(owner_statuses)
        infected_port.Instance = N()
        owner.OnTick(1.)
        self.assertEqual(2, queue.m_Cursor)
        self.assertEqual(before_late_start + 1, len(owner_statuses),
                         'late infected start left cached posture status stale')
        self.assertEqual(('degraded', 'native_crawler_idle_only_rest_wake_unverified'), owner_statuses[-1])
        for _ in range(10): owner.OnTick(1.)
        self.assertEqual(before_late_start + 1, len(owner_statuses), 'unchanged status republished')
        self.assertEqual('degraded', statuses[-1][0])
        # The inherited module's scaling service may run while posture is off.
        owner.m_Variety = False
        owner.OnTick(1.)
        self.assertEqual('ready', owner_statuses[-1][0])
        owner.m_Variety = True
        infected_port.Instance = None
        owner.OnTick(1.)
        self.assertEqual(('refused', 'infected_owner_unavailable_rest_wake_unverified'), owner_statuses[-1])
        before_loss = len(owner_statuses)
        owner.OnTick(1.)
        self.assertEqual(before_loss, len(owner_statuses))
        owner.OnStop()
        self.assertEqual([], queue.m_Queue)
        self.assertEqual(('off', 'posture_queue_stopped'), statuses[-1])
        self.assertIs(owner_report, owner.HCGetOperationalStatus())
        self.assertEqual(('off', 'variety_owner_stopped'), owner_statuses[-1])
        owner.OnTick(1.)
        self.assertEqual(before_loss + 1, len(owner_statuses), 'stopped tick republished status')

        # Synthetic existing crawler + actual native hold/release bodies. A
        # successful idle latch is not animation, pathfinding or wake proof.
        latches = []
        speed = []
        native_calls = []
        enabled = [True]
        actor = N(m_HCVarietyTriedDormant=False, m_HCVarietyDormant=False,
                  m_HCVarietyNextTry=0., m_HCVarietySleepUntil=0., m_HCVarietySpeed=False,
                  m_HCVarietyRole=0, m_HCVarietyPlace='synthetic-place',
                  IsAlive=lambda: True, IsCrawling=lambda: True,
                  IsBeingBackstabbed=lambda: False,
                  GetAIAgent=lambda: N(SetKeepInIdle=latches.append),
                  GetInputController=lambda: N(GetMindState=lambda: 0,
                     OverrideMovementSpeed=lambda *args: speed.append(args)))
        native_env = dict(env, DayZInfectedConstants=N(MINDSTATE_CALM=0),
                          HCInfectedVarietyModule=N(VarietyActive=lambda: enabled[0]),
                          super=N(EEDelete=lambda parent: native_calls.append(parent)))
        names = ('HCVarietyCanTry', 'HCVarietySleep', 'HCVarietyWake', 'HCVarietyRelease', 'EEDelete')
        externals = ('IsAlive', 'IsCrawling', 'IsBeingBackstabbed',
                     'GetAIAgent', 'GetInputController')
        for name in names:
            fn_native = translate(str(NATIVE), ('override void ' if name == 'EEDelete' else
                                  'void ' if name == 'HCVarietyRelease' else 'bool ') + name + '(',
                                  names + externals, statics=('HC_VARIETY_RETRY_SECONDS',),
                                  **dict(native_env, STATICS=N(HC_VARIETY_RETRY_SECONDS=retry_seconds)))
            setattr(actor, name, MethodType(fn_native, actor))
        self.assertTrue(actor.HCVarietySleep(100., True))
        self.assertEqual([True], latches)
        until = actor.m_HCVarietySleepUntil
        self.assertFalse(actor.HCVarietySleep(110., True))
        self.assertEqual(until, actor.m_HCVarietySleepUntil, 'repeat extended hold')
        self.assertTrue(actor.HCVarietyWake())
        self.assertFalse(actor.HCVarietyWake())
        self.assertEqual([True, False], latches)
        self.assertEqual(0, actor.m_HCVarietySleepUntil)
        actor.m_HCVarietySpeed = True
        actor.HCVarietyRelease()
        actor.EEDelete('synthetic-parent')
        self.assertEqual([(False, 0)], speed)
        self.assertEqual(['synthetic-parent'], native_calls)
        self.assertEqual('', actor.m_HCVarietyPlace)
        self.assertFalse(actor.HCVarietySleep(200., True), 'released entity was reactivated')

        for guard in ('dead', 'standing', 'finisher', 'missing_agent', 'combat', 'off', 'client'):
            actor.m_HCVarietyTriedDormant = False  # distinct synthetic entity
            actor.IsAlive = lambda: guard != 'dead'
            actor.IsCrawling = lambda: guard != 'standing'
            actor.IsBeingBackstabbed = lambda: guard == 'finisher'
            actor.GetAIAgent = lambda: None if guard == 'missing_agent' else N(SetKeepInIdle=latches.append)
            actor.GetInputController = lambda: N(GetMindState=lambda: 4 if guard == 'combat' else 0)
            enabled[0] = guard != 'off'
            game.IsServer = lambda: guard != 'client'
            self.assertFalse(actor.HCVarietySleep(300., True), guard)
        self.assertEqual([True, False], latches)
        # Releasing ownership after death/finisher clears HC state, but never
        # clears a native finisher's latch or wakes a dead actor's FSM.
        for alive, finisher in ((False, False), (True, True)):
            actor.m_HCVarietyDormant = True
            actor.IsAlive = lambda: alive
            actor.IsBeingBackstabbed = lambda: finisher
            self.assertTrue(actor.HCVarietyWake())
        self.assertEqual([True, False], latches)

        manifest = json.loads((ROOT / 'mission/hollow-country/infected/variety-sites.json').read_text())
        self.assertEqual(['native_crawler_idle', 'sit_wall', 'prone_sleep', 'riser'],
                         [row['mode'] for row in manifest['support_queue']])
        self.assertEqual(4, manifest['bounds']['support_modes'])
        self.assertEqual([], manifest['bounds']['distances_added'])
        self.assertFalse(manifest['production_enabled'])
        self.assertEqual('PENDING', manifest['runtime_acceptance'])
        self.assertEqual([], manifest['sites'])
        for row in manifest['support_queue']:
            self.assertEqual(row['refusal'], policy.HCPostureRefusal(row['mode']))
        # Guard the dependency/load order and lack of delayed callback lifetime.
        config = (ROOT / 'mods/HollowCountryAnims/config.cpp').read_text()
        self.assertRegex(config, r'requiredAddons\[\]\s*=\s*\{[^}]*"HollowCountry"')
        self.assertIn('scope = 1;', config)
        self.assertNotIn('CallLater(', POSE.read_text())

        # Explicit synthetic native ports. Repeated calls represent the
        # existing four-actor retained-cursor sample, not a new retry loop.
        latches = []
        mind = [0]
        actor = N(m_HCVarietyTriedDormant=False, m_HCVarietyDormant=False,
                  m_HCVarietyNextTry=0., m_HCVarietySleepUntil=0., IsAlive=lambda: True,
                  IsCrawling=lambda: True, IsBeingBackstabbed=lambda: False,
                  GetInputController=lambda: N(GetMindState=lambda: mind[0]),
                  GetAIAgent=lambda: N(SetKeepInIdle=latches.append))
        env = dict(GetGame=lambda: N(IsServer=lambda: True),
                   HCInfectedVarietyModule=N(VarietyActive=lambda: True),
                   HCPostureAdmission=N(HCCanEnter=lambda mode: True),
                   DayZInfectedConstants=N(MINDSTATE_CALM=0),
                   STATICS=N(HC_VARIETY_RETRY_SECONDS=retry_seconds))
        bind(NATIVE, actor, ('HCVarietyCanTry', 'HCVarietySleep'), env, statics=('HC_VARIETY_RETRY_SECONDS',), bound=('IsAlive', 'IsCrawling',
             'IsBeingBackstabbed', 'GetInputController', 'GetAIAgent'))
        self.assertFalse(actor.HCVarietySleep(100., False))
        self.assertFalse(actor.m_HCVarietyTriedDormant, 'failed roll consumed the only rest')
        mind[0] = 4
        self.assertFalse(actor.HCVarietySleep(101., True))
        self.assertFalse(actor.m_HCVarietyTriedDormant, 'non-calm sample consumed the only rest')
        self.assertEqual([], latches)
        mind[0] = 0
        self.assertFalse(actor.HCVarietySleep(102., True), 'failed roll rerolled before cooldown')
        self.assertEqual(700., actor.m_HCVarietyNextTry)
        self.assertFalse(actor.HCVarietySleep(699., True))
        self.assertEqual([], latches)
        self.assertTrue(actor.HCVarietySleep(700., True))
        self.assertTrue(actor.m_HCVarietyTriedDormant)
        self.assertFalse(actor.HCVarietySleep(701., True))
        self.assertEqual([True], latches)
        self.assertEqual(760., actor.m_HCVarietySleepUntil)

        # Execute the real retained cursor too: a revisit during cooldown must
        # skip both the random draw and corpse/proximity work, not just deny
        # entry after re-rolling. Geometry/native observations are synthetic.
        crawler = N(m_HCVarietyTriedDormant=False, m_HCVarietyDormant=False,
                    m_HCVarietyNextTry=0., m_HCVarietySleepUntil=0.,
                    IsAlive=lambda: True, IsCrawling=lambda: True,
                    IsBeingBackstabbed=lambda: False, GetPosition=lambda: [0., 0., 0.],
                    GetInputController=lambda: N(GetMindState=lambda: 0),
                    GetAIAgent=lambda: N(SetKeepInIdle=self.fail),
                    GetMindStateSynced=lambda: 0, HCVarietyRole=lambda: 1,
                    HCVarietyPlace=lambda: 'synthetic-place', HCVarietyAssign=lambda *args: None)
        crawler.HCVarietyDormant = lambda: crawler.m_HCVarietyDormant
        bind(NATIVE, crawler, ('HCVarietyCanTry', 'HCVarietySleep'), env,
             statics=('HC_VARIETY_RETRY_SECONDS',), bound=('IsAlive', 'IsCrawling',
             'IsBeingBackstabbed', 'GetInputController', 'GetAIAgent'))
        scans, draws = [], []
        cursor_owner = N(m_Healthy=True, m_HCVarietyCursor=0,
            m_Actors=Array([N(InfectedEntity=crawler, LODTier=2,
                             GroupId=0, SearchPack=False, EverAssigned=False)]),
            HCVarietyPlaceAt=lambda pos: 'synthetic-place', HCVarietyInPlace=lambda place: 0,
            HCVarietyNearStanding=lambda *args: False,
            HCVarietyNearCorpse=lambda entity: scans.append(entity) or True)
        tick = translate(str(NATIVE.with_name('HCInfectedVarietyModule.c')), 'int HCVarietyTick(',
            ('HCVarietyPlaceAt', 'HCVarietyInPlace', 'HCVarietyNearStanding', 'HCVarietyNearCorpse'),
            HCInfectedVarietyModule=env['HCInfectedVarietyModule'],
            HCInfectedVarietyPolicy=N(**variety_policy()),
            HCInfectedLOD=N(PosedBudget=lambda: 12, PosedFullBudget=lambda: 12,
                            PosedIdleBudget=lambda: 12), HCLODPolicy=N(TIER_FULL=2),
            DayZInfectedConstants=N(MINDSTATE_CALM=0))
        tick.__globals__['Math'].RandomFloat01 = lambda: draws.append('synthetic-failed-roll') or .99
        for revisit in (100., 101., 699.):
            self.assertEqual(0, tick(cursor_owner, Array(), revisit, 0., 0., 1.))
        self.assertEqual(1, len(draws))
        self.assertEqual(1, len(scans))
        self.assertEqual(0, tick(cursor_owner, Array(), 700., 0., 0., 1.))
        self.assertEqual(2, len(draws))
        self.assertEqual(2, len(scans))


if __name__ == '__main__':
    unittest.main()
