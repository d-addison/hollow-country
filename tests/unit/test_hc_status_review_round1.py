"""Execute authored lifecycle/status methods with explicit synthetic collaborators.
Offline transitions only; these fixtures establish no DayZ behavior.
"""
import re
import unittest
from types import SimpleNamespace as N

from tests.unit.test_event_runtime import translate, EArray
from tests.unit.test_hc_module_readiness_wave16 import S, FakeStatus, derive, class_text


def method(path, cls, name, env):
    source = class_text(path.read_text(), cls)
    source = re.sub(r'HCV2ThreatStore<HCSettlementState>', 'HCThreatStoreFixture', source)
    source = source.replace('JsonFileLoader<HCSettlementState>', 'SyntheticJson')
    source = re.sub(r'new array<ref \w+>;', 'new array<ref SyntheticRow>();', source)
    source = source.replace('m_Config.Herds.Count().ToString()', 'str(m_Config.Herds.Count())')
    # The tiny translator recognizes HCEvent* data types. Only names change.
    methods = set(re.findall(r'\b(HC\w+)\(', source)) | {'HCDirty', 'HCInFlight', 'HCDue'}
    source = re.sub(r'\bHC(?!Event)(\w+)',
                    lambda m: m[0] if m[0] in methods else 'HCEvent' + m[1], source)
    adapted = {re.sub(r'^HC(?!Event)', 'HCEvent', key): value for key, value in env.items()}
    return translate(source, name, adapted, 'FixtureOwner', True)


def bind(owner, path, cls, names, env=None):
    ports = dict(HCModuleReadiness=N(HCDerive=derive()), Print=lambda line: None,
                 str=str, EArray=EArray, Math=N(Min=min, Max=max))
    ports.update(env or {})
    for name in names:
        fn = method(path, cls, name, ports)
        setattr(owner, name, lambda *args, fn=fn: fn(owner, *args))
    return owner


class StatusReviewTests(unittest.TestCase):
    def status(self, owner, state, reason):
        row = owner.HCGetOperationalStatus()
        self.assertEqual((state, reason), (row.state, row.reason))

    def decay(self, can_open=True):
        world = [None]
        writes = []
        owner = N(m_Started=False, m_Initialized=False, m_Fault=False, m_State=None,
                  m_Catalog=None, m_Operational=FakeStatus(), m_Elapsed=0,
                  m_HistoryPending=False, m_Clear=EArray(), m_PropSlots=EArray(),
                  m_WorkBudget=N(HCReset=lambda n: None, HCContinue=lambda: False,
                                 HCDeferred=lambda *a: None))
        env = dict(HCV2Admission=N(Line=lambda *a: 'synthetic admission'),
                   HCV2Gates=N(Qualified=lambda gate: False),
                   HCSettlementDecayStore=lambda: N(Save=lambda state: writes.append(state) or True),
                   HCSettlementSaveJob=lambda: N(Owner=None),
                   HCSaveScheduler=N(HCRegister=lambda job: None),
                   HCWorldModule=N(Get=lambda: world[0]), HCWorldClock=N(UTC=lambda: 100),
                   HCWorldData=N(Fresh=lambda epoch: N(Places=EArray([N(Id='synthetic-town')]))),
                   HCThreatStoreFixture=N(CanOpen=lambda path: can_open),
                   FileExist=lambda path: False, GetGame=lambda: N(GetWorldName=lambda: 'synthetic-world'),
                   HCSettlementState=lambda: N(Towns=EArray()), HCSettlementTown=lambda: N())
        # PATH is authored policy, IO itself is synthetic.
        env['HCSettlementDecayStore'].PATH = 'synthetic-settlement.json'
        bind(owner, S / 'World/HCSettlementDecay.c', 'HCSettlementDecay',
             ['OnStart', 'Initialize', 'Persist', 'Fail', 'OnTick', 'HCFlushRoutine',
              'GetName', 'HCGetOperationalStatus'], env)
        return owner, world, writes

    def test_decay_start_wait_world_initialize_then_runtime_fault(self):
        owner, world, writes = self.decay()
        owner.OnStart(N())
        self.status(owner, 'requested', 'world_unavailable')
        owner.OnTick(10)
        self.status(owner, 'requested', 'world_unavailable')
        world[0] = N(Epoch=lambda: 1)
        self.status(owner, 'requested', 'settlement_state_loading')
        owner.OnTick(10)
        self.assertEqual(1, len(writes))
        self.status(owner, 'ready', 'settlement_state_catalogue_loaded')
        owner.m_Store.Save = lambda state: False
        self.assertFalse(owner.HCFlushRoutine())
        self.status(owner, 'degraded', 'persistence_clock_or_schema_fault')

    def test_decay_initialization_failure_never_reports_ready(self):
        owner, world, writes = self.decay(can_open=False)
        owner.OnStart(N())
        world[0] = N(Epoch=lambda: 1)
        owner.OnTick(10)
        self.assertEqual([], writes)
        self.status(owner, 'degraded', 'persistence_clock_or_schema_fault')

    def test_failed_herd_start_is_degraded_and_operator_opt_out_stays_ready(self):
        for opted_out in (False, True):
            with self.subTest(operator_herd_opt_out=opted_out):
                starts, logs = [], []
                config = N(EnableLOD=True, EnableVirtualHerds=not opted_out,
                           Herds=EArray([N(Id='synthetic-herd')]), MemberTypes=EArray(['synthetic-class']),
                           PosedBudget=1, PosedFullBudget=1, PosedIdleBudget=1, FullRange=1,
                           IdleRange=1, MaterializeRange=1, FoldRange=1, VisibilityRange=1, ClassifyPerTick=1)
                store = N(Start=lambda cfg: starts.append(cfg) or False, Healthy=lambda: False)
                owner = N(m_Running=False, m_Herds=False, m_Store=None,
                          m_Refusal='', m_Operational=FakeStatus())
                bind(owner, S / 'Infected/LOD/HCInfectedLOD.c', 'HCInfectedLODModule',
                     ['OnStart', 'IsEnabled', 'HCGetOperationalStatus'], dict(
                         Print=logs.append, GetGame=lambda: N(IsServer=lambda: True, GetTickTime=lambda: 10),
                         HCInfectedLODConfig=N(Load=lambda reason: config),
                         HCV2Admission=N(Line=lambda *a: 'synthetic admission',
                                         Admitted=lambda preference: preference, OnOff=lambda enabled: 'off'),
                         HCV2Gates=N(Qualified=lambda gate: False),
                         HCInfectedLOD=N(HCSet=lambda cfg: None), HCLODSightBudget=lambda: N(),
                         HCInfectedLODStore=lambda: store,
                         HCInfectedLODExperiment=lambda: N(HCArm=lambda: False)))
                owner.OnStart(N(EnableInfected=True, EnableDebugSnapshot=False))
                self.assertTrue(owner.m_Running)
                self.assertFalse(owner.m_Herds)
                if opted_out:
                    self.assertEqual([], starts)
                    self.assertTrue(any('herds=off' in line for line in logs))
                    self.status(owner, 'ready', 'lod_config_loaded_tick_running')
                else:
                    self.assertEqual([config], starts)
                    self.status(owner, 'degraded', 'herd_store_unhealthy')

    def test_dead_drop_runtime_save_failure_retains_fault(self):
        owner = N(m_Ready=True, m_Refusal='', m_Fault='', m_Operational=FakeStatus(),
                  m_Dirty=True, m_State=N(), m_Store=N(Save=lambda state: False))
        bind(owner, S / 'World/HCDeadDrops.c', 'HCDeadDrops',
             ['SaveChanged', 'HCGetOperationalStatus'])
        self.assertFalse(owner.SaveChanged())
        self.assertFalse(owner.m_Ready)
        self.status(owner, 'degraded', 'dead_drop_save_failed')

    def scene(self):
        owner = N(m_Running=True, m_Refusal='', m_Fault='', m_Operational=FakeStatus(),
                  m_State=N(LastNow=10, Stories=None), m_Store=N(Save=lambda state: False,
                      SaveInFlight=lambda: False, SaveStep=lambda state: -1),
                  m_LastNow=20, m_SaveJob=N(HCDirty=True, HCInFlight=True))
        owner.OnStop = lambda: setattr(owner, 'm_Running', False)
        bind(owner, S / 'Scenes/HCScenesModule.c', 'HCScenesModule',
             ['Commit', 'HCStepRoutine', 'StoryStep', 'HCGetOperationalStatus'],
             dict(HCSaveJob=N(STEP_FAILED=-1)))
        return owner

    def test_scene_barrier_save_failure_retains_fault_after_stop(self):
        owner = self.scene()
        self.assertFalse(owner.Commit(20))
        self.assertFalse(owner.m_Running)
        self.status(owner, 'degraded', 'scene_save_failed')

    def test_scene_heartbeat_save_failure_retains_fault_after_stop(self):
        owner = self.scene()
        self.assertEqual(-1, owner.HCStepRoutine())
        self.assertFalse(owner.m_Running)
        self.assertFalse(owner.m_SaveJob.HCDirty)
        self.assertFalse(owner.m_SaveJob.HCInFlight)
        self.status(owner, 'degraded', 'scene_heartbeat_save_failed')

    def test_scene_story_save_failure_retains_fault_after_stop(self):
        owner = self.scene()
        ready = [True]
        def step(now, released):
            ready[0] = False
            return False
        owner.m_Stories = N(HCCandidate=lambda: None, HCStep=step,
                            HCReady=lambda: ready[0], HCReason=lambda: 'save-failed')
        owner.SaveBarrierDone = lambda: None
        owner.StoryStep(20)
        self.assertFalse(owner.m_Running)
        self.status(owner, 'degraded', 'scene_story_save_failed')
