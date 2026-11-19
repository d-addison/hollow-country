"""Issue #213: execute authored methods on explicit synthetic native ports.
Spec: shared fresh-body cap, opt-out isolation/restart, honest dependency status.
Plan/tasks: extend existing queue, never reverse injury crawl or revive corpses.
Offline tests establish no DayZ posture, perception, route or spawning behavior.
"""
from types import SimpleNamespace as N
import unittest
import tempfile
from pathlib import Path
from tests.unit.test_infected_variety_w56 import AREA, ROOT
from tests.unit.test_infected_admission import Array, translate
from tests.unit.test_hc_postures import bind


class VarietyW60(unittest.TestCase):
    def test_standing_fresh_body_holds_once_then_native_wake_releases_once(self):
        idle = []
        actor = N(m_HCVarietyTriedDormant=False, m_HCVarietyDormant=False,
                  m_CrawlTransition=-1, IsAlive=lambda: True, IsCrawling=lambda: False,
                  IsBeingBackstabbed=lambda: False,
                  GetInputController=lambda: N(GetMindState=lambda: 0),
                  GetAIAgent=lambda: N(SetKeepInIdle=idle.append),
                  HCVarietyAssign=lambda *args: None, m_HCVarietyPosed=False,
                  HCVarietyPoseWake=lambda: self.fail('standing body woke a pose'))
        bind(AREA / 'HCInfectedVarietyNative.c', actor,
             ('HCVarietyFreshStanding', 'HCVarietyWake'),
             dict(GetGame=lambda: N(IsServer=lambda: True),
                  HCInfectedVarietyModule=N(VarietyActive=lambda: True),
                  DayZInfectedConstants=N(MINDSTATE_CALM=0)),
             bound=('IsAlive', 'IsCrawling', 'IsBeingBackstabbed',
                    'GetInputController', 'GetAIAgent', 'HCVarietyAssign'))
        self.assertTrue(actor.HCVarietyFreshStanding(1., 'synthetic-site', 0))
        self.assertEqual(-1, actor.m_CrawlTransition, 'standing body forced injury crawl')
        self.assertFalse(actor.HCVarietyFreshStanding(2., 'synthetic-site', 0))
        self.assertTrue(actor.HCVarietyWake())
        self.assertFalse(actor.HCVarietyWake())
        self.assertEqual([True, False], idle)

    def test_marker_start_has_no_load_or_tick_work_and_recovers_on_restart(self):
        disabled, loaded, logs = [True], [], []
        state = N(s_Running=False, s_Pending=True, s_Fault='', s_Config=None)
        enabled = translate(str(AREA / 'HCInfectedVariety.c'), 'static bool HCOperatorEnabled(', (),
                            FileExist=lambda path: disabled[0])
        start = translate(str(AREA / 'HCInfectedVariety.c'), 'static void HCStart(',
                          ('HCOperatorEnabled', 'HCLoadConfig'), statics=tuple(vars(state)),
                          STATICS=state, FileExist=lambda path: disabled[0], Print=logs.append,
                          HCV2Admission=N(Line=lambda *a: 'synthetic-admission'),
                          HCInfectedVarietyPolicy=N(HCPoseClass=lambda: 'HC_ZmbM_Sitter'))
        owner = N(HCOperatorEnabled=lambda p: enabled(None, p),
                  HCLoadConfig=lambda: loaded.append(True) or True)
        start(owner, True)
        self.assertEqual('infected_variety_disabled', state.s_Fault)
        self.assertFalse(state.s_Running)
        self.assertFalse(state.s_Pending)
        step = translate(str(AREA / 'HCInfectedVariety.c'), 'static void HCStep(', (),
                         statics=tuple(vars(state)), STATICS=state)
        step(None, 1., 1.)  # No native/environment stubs: any work here fails.
        self.assertEqual([], loaded)
        disabled[0] = False
        start(owner, True)  # Synthetic next server lifecycle; admission re-observed.
        self.assertTrue(state.s_Running)
        self.assertEqual('', state.s_Fault)
        self.assertEqual([True], loaded)
        self.assertTrue(all('runtime=PENDING' in line for line in logs))
        module = (AREA / 'HCInfectedVarietyModule.c').read_text()
        self.assertIn('m_Variety = HCInfectedVariety.HCOperatorEnabled(settings.EnableInfectedVariety);', module)

    def test_module_marker_blocks_existing_body_mutations_and_recovers_next_start(self):
        disabled, mutations = [True], []
        enabled = translate(str(AREA / 'HCInfectedVariety.c'), 'static bool HCOperatorEnabled(', (),
                            FileExist=lambda path: disabled[0])
        variety = N(HCOperatorEnabled=lambda p: enabled(None, p), HCStart=lambda p: None,
                    HCStep=lambda *a: None)
        infected = N(HCVarietyTick=lambda *a: mutations.append('tick') or 0)
        registry = N(s_Instance=None)
        env = dict(GetGame=lambda: N(IsServer=lambda: True,
                     GetPlayers=lambda players: None, GetDayTime=lambda: 12., GetWeather=lambda: None),
                   HCInfectedVariety=variety, HCInfectedModule=N(Instance=infected),
                   HCInfectedVarietyPolicy=N(GroupScale=lambda n: 1.),
                   HCInfectedVisionPolicy=N(Nightness=lambda hour: 0.),
                   HCV2Admission=N(Line=lambda *a: 'synthetic', OnOff=lambda p: 'synthetic'),
                   Print=lambda *a: None)

        # Existing restricted translator misreads nested calls in one-line ifs.
        # Fixture changes whitespace only; decisions remain shipped source.
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / 'HCInfectedVarietyModule.c'
            fixture.write_text((AREA / 'HCInfectedVarietyModule.c').read_text().replace(' { ', ' {\n ').replace('= this;', '= self;'))
            startup = translate(str(fixture), 'override void OnStart(',
                                ('IsEnabled',), statics=('s_Instance',), STATICS=registry, **env)
            tick = translate(str(fixture), 'override void OnTick(', (), **env)
        settings = N(EnableInfectedVariety=True, EnableGroupScaling=True, EnableDebugSnapshot=False)
        def boot():
            owner = N(m_Running=False, m_Printed=False, m_Clock=0., m_LogAt=600.,
                      m_Shot=False, m_Woken=0, IsEnabled=lambda s: True)
            startup(owner, settings)
            tick(owner, 1.)
            return owner
        self.assertFalse(boot().m_Variety)
        self.assertEqual([], mutations)
        disabled[0] = False
        self.assertTrue(boot().m_Variety)
        self.assertEqual(['tick'], mutations)

    def test_status_off_invalid_data_and_dependency_recovery_are_observed(self):
        # Execute startup, the actual cached-status refresh and public getter.
        # Every engine/admission/storage collaborator is an explicit synthetic port.
        rows, logs, disabled, valid = [], [], [True], [True]
        primary = N(Instance=None)
        route_fault = ['']
        state = N(s_Running=False, s_Pending=False, s_Fault='', s_Config=None)
        enabled = translate(str(AREA / 'HCInfectedVariety.c'), 'static bool HCOperatorEnabled(', (),
                            FileExist=lambda path: disabled[0])
        start = translate(str(AREA / 'HCInfectedVariety.c'), 'static void HCStart(',
                          ('HCOperatorEnabled', 'HCLoadConfig'), statics=tuple(vars(state)),
                          STATICS=state, Print=logs.append,
                          HCV2Admission=N(Line=lambda *a: 'synthetic runtime=PENDING'),
                          HCInfectedVarietyPolicy=N(HCPoseClass=lambda: 'HC_ZmbM_Sitter'))
        def load():
            if not valid[0]: state.s_Fault = 'variety_data_invalid'
            return valid[0]
        source = N(HCOperatorEnabled=lambda p: enabled(None, p), HCLoadConfig=load)
        cached = N(state='off', reason='not_started')
        def publish(status, reason):
            cached.state, cached.reason = status, reason
            rows.append((status, reason))
        cached.HCPublish = publish
        cached.HCState = lambda: cached.state
        cached.HCReason = lambda: cached.reason
        postures = N(HCStatus=lambda: N(HCState=lambda: 'ready',
                         HCReason=lambda: 'native_crawler_idle_admitted_rest_wake_unverified_runtime_pending'))
        owner = N(m_Running=False, m_Variety=False, m_HCVarietyStatus=cached,
                  m_HCPostures=postures)
        refresh = translate(str(AREA / 'HCInfectedVarietyNative.c'),
                            'void HCRefreshVarietyStatus(', ('VarietyActive',))
        owner.VarietyActive = lambda: owner.m_Running and owner.m_Variety and primary.Instance is not None
        owner.HCRefreshVarietyStatus = lambda: refresh(owner)
        getter = translate(str(AREA / 'HCInfectedVarietyStatus.c'),
                           'HCOperationalStatus HCGetOperationalStatus(', ('HCRefreshVarietyStatus',),
                           super=N(HCGetOperationalStatus=lambda: cached),
                           HCInfectedVariety=N(HCFault=lambda: state.s_Fault),
                           HCInfectedVarietyRoutes=N(HCFault=lambda: route_fault[0]),
                           HCInfectedModule=primary)
        def boot():
            owner.m_Running = False
            start(source, True)
            owner.m_Variety = enabled(None, True)
            owner.m_Running = True
            return observe()
        def observe():
            getter(owner)
            return cached.state, cached.reason
        sequence = [boot()]
        disabled[0], valid[0] = False, False
        sequence.append(boot())
        valid[0] = True
        sequence.append(boot())
        self.assertTrue(state.s_Running, 'successful source startup was not executed')
        primary.Instance = N()
        sequence.append(observe())
        primary.Instance = None
        sequence.append(observe())
        primary.Instance = N()
        sequence.append(observe())
        disabled[0] = True
        sequence.append(boot())
        disabled[0] = False
        sequence.append(boot())  # Restart after marker removal with dependency available.
        route_fault[0] = 'variety_route_document_unavailable'
        self.assertEqual(('degraded', route_fault[0]), observe())
        route_fault[0] = ''
        sequence.append(observe())
        ready = ('ready', 'native_crawler_idle_admitted_rest_wake_unverified_runtime_pending')
        missing = ('degraded', 'infected_owner_unavailable')
        self.assertEqual([('off', 'infected_variety_disabled'),
                          ('degraded', 'variety_data_invalid'), missing, ready,
                          missing, ready, ('off', 'infected_variety_disabled'), ready, ready], sequence)
        self.assertTrue(all('runtime=PENDING' in line for line in logs))

    def test_mixed_group_shares_corpse_cap_and_rechecks_visibility(self):
        created, entries, refused = [], [], []
        site = N(Id='synthetic-place', Context='wreck', Position=[1000., 0., 1000.])
        state = N(s_Running=True, s_Pending=True, s_Admin=True, s_NextAutomatic=0.,
                  s_Config=N(MaxFreshBodies=3, GroupMembers=3, StandingRiserEvery=2, PosedFreshEvery=0,
                    Sites=Array([site]), ContextRange=40., GroupSpacing=4., InterestRange=1000.),
                  s_Bodies=Array([N(IsAlive=lambda: False)]), s_Selected=0, s_Made=0,
                  s_Tried=Array(), s_Used=Array(), s_LastRefusal='')
        hidden = [True]
        def spawn(kind, pos):
            created.append(list(pos))
            return N(HCVarietyFreshCrawler=lambda *a: entries.append('crawler') or True,
                     HCVarietyFreshStanding=lambda *a: entries.append('standing') or True)
        cadence = translate(str(AREA / 'HCInfectedVarietyPolicy.c'), 'static bool HCStandingFresh(', ())
        method = translate(str(AREA / 'HCInfectedVariety.c'), 'static void HCStep(',
            ('HCNearestCandidate', 'HCHidden', 'HCRefuse'), statics=tuple(vars(state)), STATICS=state,
            HCInfectedVarietyModule=N(VarietyActive=lambda: True),
            HCInfectedModule=N(Instance=N(HCVarietyFreshRoom=lambda s: True, HCLODMaterialize=spawn)),
            HCServer=N(HCTickWork=lambda: N(HCTakeFor=lambda *a: True)),
            HCUnitBudget=N(HC_WORK_INFECTED=0), HCPerfPlayers=N(HCGet=lambda: Array()),
            GetGame=lambda: N(SurfaceY=lambda *a: 0., ConfigIsExisting=lambda c: False),
            HCInfectedLOD=N(NearestDistance=lambda *a: 500.),
            HCAdminPlacement=N(HCClear=lambda p: True),
            HCInfectedVarietyPolicy=N(HCContextRole=lambda *a: 0,
                                     HCPoseClass=lambda: 'HC_ZmbM_Sitter',
                                     HCPoseFresh=lambda *a: 0,
                                     HCStandingFresh=lambda *a: cadence(None, *a)), Print=lambda *a: None)
        owner = N(HCNearestCandidate=lambda: 0, HCHidden=lambda *a: hidden[0], HCRefuse=refused.append)
        method(owner, 1., 1.)
        self.assertEqual(['crawler'], entries)
        hidden[0] = False
        method(owner, 2., 1.)
        self.assertEqual(1, len(created), 'observed standing body was spawned')
        state.s_Pending, state.s_Selected = True, 0
        hidden[0] = True
        method(owner, 3., 1.)
        self.assertEqual(['crawler', 'standing'], entries)
        self.assertEqual(3, len(state.s_Bodies))
        method(owner, 4., 1.)
        self.assertEqual(2, len(created), 'corpse failed to charge shared fresh cap')
        self.assertIn('fresh_body_cap_including_corpses', refused)

    def test_config_validates_standing_cadence_and_accepts_zero_opt_out(self):
        import json
        data = json.loads((ROOT / 'mission/hollow-country/infected/variety-runtime.json').read_text())
        data['Sites'] = Array([N(Id='synthetic-site', Context='wreck',
                                 SourceClass='synthetic-class', Position=[1000., 0., 1000.])])
        owner = N(**data)
        # This fixture tests the original site/cadence limits with default tuning.
        owner.HCNormalizeTunables = lambda: None
        owner.PosedFreshEvery = 3
        owner.HCPosedCadenceValid = lambda: translate(
            str(AREA / 'HCInfectedVariety.c'), 'bool HCPosedCadenceValid(', (),
            fields=('PosedFreshEvery', 'MaxFreshBodies'))(owner)
        valid = translate(str(AREA / 'HCInfectedVariety.c'), 'bool HCValid(',
                          ('HCNormalizeTunables', 'HCPosedCadenceValid'),
                          fields=tuple(data) + ('PosedFreshEvery',),
                          HCInfectedStore=N(ValidPosition=lambda p: True))
        for cadence, expected in ((2, True), (0, True), (-1, False), (4, False)):
            owner.StandingRiserEvery = cadence
            self.assertEqual(expected, valid(owner))

    def test_standing_selection_has_named_opt_out_and_bounded_cadence(self):
        fn = translate(str(AREA / 'HCInfectedVarietyPolicy.c'), 'static bool HCStandingFresh(', ())
        self.assertEqual([False, True, False], [fn(None, i, 2) for i in range(3)])
        self.assertFalse(fn(None, 1, 0))

if __name__ == '__main__':
    unittest.main()
