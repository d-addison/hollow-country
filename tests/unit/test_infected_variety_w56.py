"""#121 spec/plan/tasks: native crawler clusters; explicit synthetic ports only.
Plan: reuse tracked bodies, LOD caps/sight, shared infected work, authored CE
anchors, one candidate/body per tick; #213 adds native standing idle bodies.
No offline result establishes DayZ animation, perception or placement behavior.
"""
import json
from pathlib import Path
from types import SimpleNamespace as N
import unittest
from tests.unit.test_event_runtime import translate
from tests.unit.test_infected_admission import Array, translate as native
from tests.unit.test_hc_postures import bind

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT / 'mods/HollowCountry/scripts/4_World/Infected/Variety'

class VarietyW56(unittest.TestCase):
    def test_context_roles_are_deterministic_and_runner_cap_wins(self):
        text = (AREA / 'HCInfectedVarietyPolicy.c').read_text()
        role = translate(text, 'HCContextRole', {})
        self.assertEqual([0, 1, 1, 0, 1], [role(k, False) for k in
                         ('wreck', 'church', 'gas_station', 'roadside', 'building')])
        self.assertEqual(2, role('roadside', True))
        self.assertEqual(1, role('building', True))

    def test_dormancy_wakes_on_native_perception_or_cap_not_elapsed_time(self):
        text = (AREA / 'HCInfectedVarietyPolicy.c').read_text()
        wake = translate(text, 'HCShouldWakeDormant', {})
        self.assertFalse(wake(False, False))
        self.assertTrue(wake(False, True))
        self.assertTrue(wake(True, False))
        module = (AREA / 'HCInfectedVarietyModule.c').read_text()
        self.assertNotIn('bool expired = now >=', module)

    def test_nearest_candidate_excludes_spent_and_failed_sites(self):
        sites = Array([N(Position=[10., 0., 0.]), N(Position=[20., 0., 0.]),
                       N(Position=[30., 0., 0.])])
        state = N(s_Config=N(RequestRange=100., Sites=sites), s_Request=[0., 0., 0.],
                  s_Used=Array([0]), s_Tried=Array())
        fn = native(str(AREA / 'HCInfectedVariety.c'), 'static int HCNearestCandidate(', (),
                    statics=tuple(vars(state)), STATICS=state,
                    vector=N(DistanceSq=lambda a,b: sum((x-y)**2 for x,y in zip(a,b))))
        self.assertEqual(1, fn(None))
        state.s_Tried.Insert(1)
        self.assertEqual(2, fn(None))
        state.s_Tried.Insert(2)
        self.assertEqual(-1, fn(None))

    def test_fresh_entry_requests_native_transition_once_without_health_mutation(self):
        idle = []
        actor = N(m_HCVarietyTriedDormant=False, m_CrawlTransition=-1,
                  IsAlive=lambda: True, IsBeingBackstabbed=lambda: False,
                  GetInputController=lambda: N(GetMindState=lambda: 0),
                  GetAIAgent=lambda: N(SetKeepInIdle=idle.append),
                  HCVarietyAssign=lambda *args: None)
        env = dict(GetGame=lambda: N(IsServer=lambda: True),
                   HCInfectedVarietyModule=N(VarietyActive=lambda: True),
                   DayZInfectedConstants=N(MINDSTATE_CALM=0))
        bind(AREA / 'HCInfectedVarietyNative.c', actor, ('HCVarietyFreshCrawler',), env,
             bound=('IsAlive', 'IsBeingBackstabbed', 'GetInputController',
                    'GetAIAgent', 'HCVarietyAssign'))
        self.assertTrue(actor.HCVarietyFreshCrawler(50., 'synthetic-site', 0))
        self.assertEqual(0, actor.m_CrawlTransition)
        self.assertTrue(actor.m_HCVarietyDormant)
        self.assertFalse(actor.HCVarietyFreshCrawler(51., 'synthetic-site', 0))
        self.assertEqual([True], idle)

    def test_group_tick_creates_one_body_rechecks_sight_and_retains_failed_entry(self):
        bodies, created, refusals = Array(), [], []
        site = N(Id='synthetic-wreck', Context='wreck', Position=[1000., 0., 1000.])
        state = N(s_Running=True, s_Pending=True, s_Admin=True,
                  s_NextAutomatic=0., s_Config=N(MaxFreshBodies=3, GroupMembers=3,
                    Sites=Array([site]), ContextRange=40., GroupSpacing=4., InterestRange=1000., StandingRiserEvery=0),
                  s_Bodies=bodies, s_Selected=0, s_Made=0, s_Tried=Array(),
                  s_Used=Array(), s_LastRefusal='')
        visible = [False]
        def spawn(kind, pos):
            created.append((kind, list(pos)))
            return N(HCVarietyFreshCrawler=lambda *args: len(created) < 2)
        infected = N(HCVarietyFreshRoom=lambda scale: True, HCLODMaterialize=spawn)
        method = native(str(AREA / 'HCInfectedVariety.c'), 'static void HCStep(',
            ('HCNearestCandidate', 'HCHidden', 'HCRefuse'), statics=tuple(vars(state)),
            STATICS=state, HCNearestCandidate=lambda: 0,
            HCInfectedVarietyModule=N(VarietyActive=lambda: True),
            HCInfectedModule=N(Instance=infected),
            HCServer=N(HCTickWork=lambda: N(HCTakeFor=lambda *args: True)),
            HCUnitBudget=N(HC_WORK_INFECTED=0), HCPerfPlayers=N(HCGet=lambda: Array()),
            GetGame=lambda: N(SurfaceY=lambda *args: 0.),
            HCInfectedLOD=N(NearestDistance=lambda *args: 500.),
            HCAdminPlacement=N(HCClear=lambda pos: True),
            HCInfectedVarietyPolicy=N(HCContextRole=lambda *args: 0,
                HCStandingFresh=lambda *args: False), Print=lambda *args: None)
        owner = N(HCHidden=lambda *args: not visible[0], HCRefuse=refusals.append)
        method(owner, 1., 1.)
        self.assertEqual(1, len(created))
        self.assertTrue(state.s_Pending)
        visible[0] = True
        method(owner, 2., 1.)
        self.assertEqual(1, len(created), 'visible group point created a body')
        self.assertFalse(state.s_Pending)
        # A distinct synthetic request: entry failure retains the newly created
        # ordinary tracked actor, never deleting/replacing it to force a pose.
        state.s_Pending, state.s_Selected, state.s_Made = True, 0, 0
        visible[0] = False
        method(owner, 3., 1.)
        self.assertEqual(2, len(bodies))
        self.assertFalse(state.s_Pending)
        self.assertIn('fresh_native_entry_refused_body_retained', refusals)

    def test_body_cap_refusal_advances_the_automatic_deadline(self):
        # Review P2: a full body cap must not spend shared infected work every tick.
        taken, refusals = [], []
        state = N(s_Running=True, s_Pending=False, s_Admin=False, s_NextAutomatic=0.,
                  s_Config=N(MaxFreshBodies=1, AutomaticIntervalSeconds=60.),
                  s_Bodies=Array([N()]), s_Selected=-1, s_Made=0, s_Tried=Array(),
                  s_Used=Array(), s_LastRefusal='', s_PlayerCursor=0)
        method = native(str(AREA / 'HCInfectedVariety.c'), 'static void HCStep(',
            ('HCNearestCandidate', 'HCHidden', 'HCRefuse'), statics=tuple(vars(state)),
            STATICS=state, HCInfectedVarietyModule=N(VarietyActive=lambda: True),
            HCInfectedModule=N(Instance=N()),
            HCServer=N(HCTickWork=lambda: N(HCTakeFor=lambda *args: taken.append(args) or True)),
            HCUnitBudget=N(HC_WORK_INFECTED=0), HCPerfPlayers=N(HCGet=lambda: Array()),
            Print=lambda *args: None)
        owner = N(HCRefuse=refusals.append, HCNearestCandidate=lambda: -1, HCHidden=lambda *a: True)
        for now in (1., 2., 3., 30.):
            method(owner, now, 1.)
        self.assertEqual(1, len(taken), 'cap refusal spent shared work on every tick')
        self.assertEqual(61., state.s_NextAutomatic)
        self.assertEqual(['fresh_body_cap_including_corpses'], refusals)

    def test_status_preserves_dependency_observation_and_surfaces_missing_data(self):
        publications = []
        observed = N(HCPublish=lambda *args: publications.append(args))
        fault = ['']
        fn = native(str(AREA / 'HCInfectedVarietyStatus.c'),
                    'HCOperationalStatus HCGetOperationalStatus(', (),
                    super=N(HCGetOperationalStatus=lambda: observed),
                    HCInfectedVariety=N(HCFault=lambda: fault[0]),
                    HCInfectedModule=N(Instance=N()))
        owner = N(m_Running=True, m_Variety=True)
        self.assertIs(observed, fn(owner))
        self.assertEqual([], publications, 'getter invented a ready result')
        fault[0] = 'variety_data_invalid'
        self.assertIs(observed, fn(owner))
        self.assertEqual([('degraded', 'variety_data_invalid')], publications)

    def test_runtime_catalog_is_consumed_and_admin_uses_same_queue(self):
        path = AREA / 'HCInfectedVariety.c'
        self.assertTrue(path.exists(), 'fresh dormant owner and admin hook missing')
        text = path.read_text()
        for seam in ('static bool HCAdminFreshDormant(vector pos, out string reason)',
                     'HCServer.HCTickWork()', 'HC_WORK_INFECTED',
                     'HCObserverTransitionGate.CanTransition', 'HCInfectedLOD.Observers',
                     'HCLODMaterialize', 'HCVarietyFreshCrawler', 'HCRefuse',
                     'acceptance/infected_variety.disable', 'HCJsonFields.Has'):
            self.assertIn(seam, text)
        data = json.loads((ROOT / 'mission/hollow-country/infected/variety-runtime.json').read_text())
        self.assertEqual({'wreck', 'church', 'gas_station', 'roadside', 'building'},
                         {s['Context'] for s in data['Sites']})
        self.assertTrue(0 < len(data['Sites']) <= data['MaxSites'])
        self.assertTrue(all(s['SourceClass'] and len(s['Position']) == 3 for s in data['Sites']))
        self.assertEqual('PENDING', data['Runtime'])

if __name__ == '__main__': unittest.main()
