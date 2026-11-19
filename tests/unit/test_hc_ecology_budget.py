"""HC-29: authored Enforce with synthetic clocks, cohorts and file ports only.
Offline execution does not establish native timing, IO durability or wildlife behavior.
"""
import functools
import json
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_ecology_runtime import ROOT, environment, translated, unit_budget
from tests.unit.test_group_server import EArray


def bind(source, names, obj, env, owner):
    for name in names:
        setattr(obj, name, functools.partial(translated(source, name, env, owner, True), obj))
    return obj


def runtime_fixture():
    env = environment()
    # Explicit synthetic shared budget port: time can be exhausted after the first row.
    clock = NS(allow=True, ticks=0)
    work = NS(HCReset=lambda *a: None, HCContinue=lambda: clock.allow)
    obj = NS(m_Running=True, m_Collecting=True, m_Actors=EArray(), m_Resources=EArray(),
             m_Intents=EArray(), m_Stage=1, m_PruneKind=0, m_PruneCursor=-1,
             m_Units=unit_budget(), m_Work=work, m_Visited=0, m_Deferred=0,
             m_Settings=env['HCEcologyRuntimeSettings'](), m_Policy=NS(WorldName='synthetic-world'),
             m_Session='session-a', m_SaveJob=None, m_Dirty=False)
    source = (ROOT/'4_World/Ecology/HCEcologyRuntime.c').read_text()
    bind(source, ('StagePrune', 'RemoveFrom', 'ForgetIntents', 'Checkpoint'), obj, env, 'HCEcologyRuntime')
    return obj, env, clock


class EcologyBudgetBehavior(unittest.TestCase):
    def test_overflow_save_resume_refusal_off_and_cost_attribution(self):
        runtime, env, clock = runtime_fixture()
        # Explicit synthetic overfull cohorts; no native objects or census claims.
        total = 310
        runtime.m_Resources.extend(NS(Live=None, LocalId='dead-%d'%i) for i in range(total))
        runtime.m_PruneCursor = total - 1
        runtime.StagePrune(100)
        limit = 32  # requested fixed row ceiling; deliberately overfull fixture
        self.assertEqual(total-limit, len(runtime.m_Resources))
        self.assertEqual(1, runtime.m_Stage)
        for _ in range(32):
            if runtime.m_Stage != 1: break
            runtime.StagePrune(100)
        self.assertEqual([], runtime.m_Resources)
        self.assertEqual(2, runtime.m_Stage, 'cleanup must yield and eventually reach sampling')
        # Time exhaustion admits one row, then yields, so expensive work cannot starve.
        runtime.m_Stage=1; runtime.m_PruneKind=0; runtime.m_PruneCursor=2
        runtime.m_Resources.extend(NS(Live=None, LocalId='x') for _ in range(3))
        clock.allow=False
        runtime.StagePrune(101)
        self.assertEqual(2, len(runtime.m_Resources))
        # Routine save must queue, never perform synchronous IO inside the ecology tick.
        runtime.m_Dirty=True
        runtime.m_SaveJob=NS(HCDirty=False, HCFailed=lambda:False)
        self.assertTrue(runtime.Checkpoint())
        self.assertTrue(runtime.m_SaveJob.HCDirty)
        runtime.m_SaveJob=None
        self.assertFalse(runtime.Checkpoint(), 'missing scheduler job must refuse')
        self.check_staged_save(env)
        self.check_job_shutdown()
        self.check_sampling_fairness()
        self.check_sampler()
        with self.subTest(scenario='invalid_calibration_keeps_raw_cost_evidence'):
            self.check_uncalibrated_cost()
        with self.subTest(scenario='calibration_expires_at_window_and_stop'):
            self.check_calibration_lifecycle()
        with self.subTest(scenario='synchronous_save_success_and_failure_are_attributed'):
            self.check_barrier_cost()
        with self.subTest(scenario='startup_store_failure_is_attributed'):
            self.check_startup_save_cost()
        runtime.m_Running=False
        source=(ROOT/'4_World/Ecology/HCEcologyRuntime.c').read_text()
        pump=translated(source,'Pump',{},'HCEcologyRuntime',True)
        before=list(runtime.m_Resources)
        pump(runtime,100000)
        self.assertEqual(before,runtime.m_Resources)

    def check_staged_save(self, env):
        files={}; trace=[]
        def write(path,text,limit):
            trace.append(('write',path)); files[path]=text; return True
        def new(path,text,limit):
            trace.append(('intent',path))
            if path in files: return False
            files[path]=text; return True
        def read(path,limit):
            trace.append(('read',path)); return files.get(path,'')
        def delete(path):
            trace.append(('delete',path)); del files[path]; return True
        env['HCEcologyRuntimeIO']=NS(Encode=lambda s:json.dumps(vars(s)), Write=write,
                                    WriteNew=new, Read=read)
        env['DeleteFile']=delete
        store=NS(m_Root='synthetic-owned',m_World='synthetic-world',m_Session='session-a',
                 m_Revision=1,m_Fault=False,m_SavePhase=0,m_SaveText='',m_SaveRevision=0)
        source=(ROOT/'4_World/Ecology/HCEcologyRuntimeStore.c').read_text()
        bind(source,('HCBeginSave','HCStepSave','HCPhase'),store,env,'HCEcologyRuntimeStore')
        snapshot=env['HCEcologyCheckpoint']()
        snapshot.Version=1; snapshot.WorldName='synthetic-world'; snapshot.SessionId='session-a'
        snapshot.Revision=2; snapshot.Samples=10; snapshot.PathQueries=0
        self.assertTrue(store.HCBeginSave(snapshot))
        snapshot.Samples=99  # encoded bounded snapshot must remain frozen
        self.assertEqual([],trace)
        for phase in range(1,5):
            self.assertEqual(phase,store.HCPhase())
            self.assertEqual(0 if phase==4 else 1,store.HCStepSave())
            self.assertEqual(phase,len(trace), 'one verified file operation per stage')
        self.assertEqual(2,store.m_Revision)
        self.assertEqual(10,json.loads(files['synthetic-owned/state-synthetic-world.json'])['Samples'])
        self.assertNotIn('synthetic-owned/pending-synthetic-world.json',files)
        # Interrupt after intent: fresh admission must reject, preserving the journal.
        snapshot.Revision=3
        self.assertTrue(store.HCBeginSave(snapshot)); self.assertEqual(1,store.HCStepSave())
        self.assertFalse(env['HCEcologyRuntimeRules'].CheckpointAdmission(True,True,True))
        env['HCEcologyRuntimeIO'].Write=lambda *a:False
        self.assertEqual(2,store.HCStepSave())
        before=list(trace)
        self.assertEqual(2,store.HCStepSave())
        self.assertEqual(before,trace)
        self.assertTrue(store.m_Fault)
        self.assertIn('synthetic-owned/pending-synthetic-world.json',files)

    def check_job_shutdown(self):
        owner,env,clock=runtime_fixture()
        env.update(STEP_DONE=0, STEP_MORE=1, STEP_FAILED=2)
        env['HCSaveJob']=NS(STEP_DONE=0,STEP_MORE=1,STEP_FAILED=2)
        env['GetGame']=lambda:NS(GetTickTime=lambda:1.)
        files={}; trace=[]
        def write(path,text,limit):
            trace.append(path); files[path]=text; return True
        env['HCEcologyRuntimeIO']=NS(Encode=lambda s:json.dumps(vars(s)), Write=write,
            WriteNew=lambda p,t,n:p not in files and write(p,t,n), Read=lambda p,n:files.get(p,''))
        env['DeleteFile']=lambda path:files.pop(path,None) is not None
        store=NS(m_Root='synthetic-owned',m_World='synthetic-world',m_Session='session-a',
                 m_Revision=1,m_Fault=False,m_SavePhase=0,m_SaveText='',m_SaveRevision=0)
        source=(ROOT/'4_World/Ecology/HCEcologyRuntimeStore.c').read_text()
        bind(source,('HCBeginSave','HCStepSave','HCPhase','Save'),store,env,'HCEcologyRuntimeStore')
        owner.m_Checkpoint=env['HCEcologyCheckpoint']()
        for key,value in dict(Version=1,WorldName='synthetic-world',SessionId='session-a',
                              Revision=1,Samples=10,PathQueries=0).items():
            setattr(owner.m_Checkpoint,key,value)
        owner.m_Dirty=True; owner.m_Store=store; owner.m_SaveMaxTicks=0
        source=(ROOT/'4_World/Ecology/HCEcologyRuntime.c').read_text()
        bind(source,('HCSnapshot','HCSaved','HCRecordSaveTicks','HCWriteCheckpoint'),
             owner,env,'HCEcologyRuntime')
        job=NS(m_Owner=owner,m_Store=store,m_Snapshot=None,m_Failed=False,
               HCDirty=True,HCInFlight=False)
        source=(ROOT/'4_World/Ecology/HCEcologySaveJob.c').read_text()
        bind(source,('HCStep','HCAdvance','HCFailed','HCDetach'),job,env,'HCEcologySaveJob')
        # Explicit global fixture for this new class; source methods above execute the job.
        env['HCEcologySaveJob']=lambda:job
        owner.m_SaveJob=job
        self.assertEqual(1,job.HCStep())
        self.assertEqual([],trace, 'first stage only freezes/encodes the bounded snapshot')
        self.assertTrue(job.HCInFlight)
        self.assertEqual(1,job.HCStep())  # intent durable before image
        owner.m_Checkpoint.Samples=12  # newer mutations must survive frozen snapshot completion
        scheduler=(ROOT/'4_World/World/HCWorkBudget.c').read_text()
        flush=translated(scheduler,'HCFlush',env,'HCSaveScheduler')
        env['HCSaveScheduler']=NS(HCFlush=flush, HCRegister=lambda job: None, HCUnregister=lambda job: None)  # explicit synthetic registry port
        source=(ROOT/'4_World/Ecology/HCEcologyRuntime.c').read_text()
        bind(source,('Finish',),owner,env,'HCEcologyRuntime')
        # Authored Finish resumes the in-flight job, then writes the remaining scalar delta.
        owner.Finish()
        state=json.loads(files['synthetic-owned/state-synthetic-world.json'])
        self.assertEqual((3,12),(state['Revision'],state['Samples']))
        self.assertFalse(owner.m_Running)
        self.assertFalse(owner.m_Dirty)
        self.assertIsNone(owner.m_SaveJob)
        self.assertIsNone(job.m_Owner)
        self.assertFalse(job.HCInFlight)
        before=list(trace);owner.Finish()
        self.assertEqual(before,trace, 'repeated stop is a no-op')

    def check_sampling_fairness(self):
        from tests.unit.test_ecology_rules import translated_rules
        runtime,env,clock=runtime_fixture()
        env.update({k:v for k,v in translated_rules().items() if k in (
            'HCEcologyObservationBatch','HCEcologyDirective','HCEcologyReceipt',
            'HCEcologyCode','HCEcologyZoneObservation','HCEcologyResource','HCEcologyPopulation')})
        calls=[]
        env['HCEcologyNative']=NS(SampleActor=lambda *a:calls.append('actor'),
            SampleResource=lambda *a:calls.append('resource') or 0,
            Capabilities=lambda:NS(ProviderAvailable=False))
        env['HCEcologyRules']=NS(Schedule=lambda *a:0)
        runtime.m_ActorSample=0;runtime.m_ResourceSample=0;runtime.m_SampleActorTurn=True
        runtime.m_State=NS()
        runtime.m_Actors.append(NS(Live=object(),LocalId='synthetic-actor'))
        runtime.m_Resources.append(NS(Live=object(),LocalId='synthetic-resource'))
        source=(ROOT/'4_World/Ecology/HCEcologyRuntime.c').read_text()
        bind(source,('StageSample',),runtime,env,'HCEcologyRuntime')
        clock.allow=False
        for _ in range(4): runtime.StageSample(100)
        self.assertEqual(['actor','resource','actor','resource'],calls)
        # Shared fixed cap also applies when the operator selects the largest valid windows.
        clock.allow=True;runtime.m_Settings.SampleSlice=32
        runtime.m_Actors.extend(NS(Live=object(),LocalId='a') for _ in range(40))
        runtime.m_Resources.extend(NS(Live=object(),LocalId='r') for _ in range(40))
        before=len(calls);runtime.StageSample(100)
        self.assertEqual(32,len(calls)-before)

    def check_sampler(self):
        from tests.unit.test_perf_capture import sampler_fixture
        runtime,env,_=runtime_fixture()
        runtime.m_StartupMaxTicks=1000;runtime.m_CallbackMaxTicks=2000
        runtime.m_SaveMaxTicks=3000;runtime.m_AdmissionMaxTicks=4000
        source=(ROOT/'4_World/Ecology/HCEcologyRuntime.c').read_text()
        bind(source,('HCStartupTicks','HCCallbackTicks','HCSaveTicks','HCAdmissionTicks',
                     'HCSetCalibration','HCResetCostTicks'),runtime,env,'HCEcologyRuntime')
        sampler,clock,logs=sampler_fixture(runtime)
        sampler.Start(1); sampler.RegisterModule('Ecology')
        sampler.SampleModule(0,20)
        self.assertEqual(-1,runtime.m_CallbackMaxTicks)
        sampler.SampleCost(-1,0,999999); sampler.SampleCost(0,4,999999)
        sampler.SampleCost(0,1,-1)
        clock.now=1.; clock.ticks=1000000
        sampler.Sample(1.,0)
        self.assertTrue(any('startup_ms=1.00 callback_ms=2.00 save_ms=3.00 admission_ms=4.00' in line for line in logs))
        sampler.SampleModule(0,0)
        self.assertEqual(1000,runtime.m_TicksPerMs)
        sampler.SampleCost(0,0,5000)
        sampler.Sample(1.,0)  # frozen clocks: invalid calibration, no converted cost
        self.assertIn('calibration=invalid',logs[-1])
        self.assertEqual(0,sampler.HCTicksPerMs())
        self.assertNotIn('[HC Cost]',logs[-1])
        sampler.SampleModule(0,0)
        self.assertEqual(0,runtime.m_TicksPerMs)
        rules=environment()['HCEcologyRuntimeRules']
        self.assertEqual(-1,rules.ElapsedUs(1000,0))
        self.assertEqual(-1,rules.ElapsedUs(1000,float('nan')))
        self.assertEqual(-1,rules.ElapsedUs(-1,1000))
        self.assertEqual(1000,rules.ElapsedUs(1000,1000))

    def cost_runtime(self):
        runtime,env,_=runtime_fixture()
        runtime.m_StartupMaxTicks=1000;runtime.m_CallbackMaxTicks=2000
        runtime.m_SaveMaxTicks=3000;runtime.m_AdmissionMaxTicks=4000
        runtime.m_TicksPerMs=0
        source=(ROOT/'4_World/Ecology/HCEcologyRuntime.c').read_text()
        bind(source,('HCStartupTicks','HCCallbackTicks','HCSaveTicks','HCAdmissionTicks',
                     'HCSetCalibration','HCResetCostTicks'),runtime,env,'HCEcologyRuntime')
        return runtime

    def check_uncalibrated_cost(self):
        from tests.unit.test_perf_capture import sampler_fixture
        runtime=self.cost_runtime()
        sampler,clock,logs=sampler_fixture(runtime)
        sampler.Start(1);sampler.RegisterModule('Ecology');sampler.SampleModule(0,0)
        # Explicit frozen synthetic clock: conversion MUST refuse, but startup
        # is a once-only observation and must remain visible in raw units.
        sampler.Sample(1.,0)
        costs=[line for line in logs if '[HC Cost]' in line]
        self.assertEqual(1,len(costs), 'invalid calibration must publish raw costs before reset')
        self.assertIn('startup_ticks=1000 callback_ticks=2000 save_ticks=3000 admission_ticks=4000',costs[0])
        self.assertIn('reason=invalid_calibration',costs[0])
        self.assertNotIn('_ms=',costs[0])
        # A later window cannot relabel earlier raw costs with another rate.
        clock.now=1.;clock.ticks=1000000
        sampler.Sample(1.,0)
        costs=[line for line in logs if '[HC Cost]' in line]
        self.assertIn('startup_ms=unobserved',costs[-1])

    def check_calibration_lifecycle(self):
        from tests.unit.test_perf_capture import sampler_fixture
        runtime=self.cost_runtime()
        sampler,clock,_=sampler_fixture(runtime)
        sampler.Start(1);sampler.RegisterModule('Ecology');sampler.SampleModule(0,0)
        clock.now=1.;clock.ticks=1000000
        sampler.Sample(1.,0)
        self.assertEqual(1000,runtime.m_TicksPerMs, 'publish calibration on the completed window')
        sampler.Sample(1.,0)  # frozen clock invalidates the previous window
        self.assertEqual(0,runtime.m_TicksPerMs, 'invalid calibration must revoke cached conversion immediately')
        clock.now=2.;clock.ticks=2000000
        sampler.Sample(1.,0)
        self.assertEqual(1000,runtime.m_TicksPerMs)
        sampler.Stop()
        self.assertEqual(0,runtime.m_TicksPerMs, 'stop cannot leave a valid conversion cached')

    def check_barrier_cost(self):
        owner,env,clock=runtime_fixture()
        owner.m_Checkpoint=env['HCEcologyCheckpoint']()
        owner.m_Checkpoint.Revision=1
        owner.m_Dirty=True;owner.m_SaveMaxTicks=-1
        env['TickCount']=lambda prior:clock.ticks-prior
        outcome=NS(ok=True,duration=17)
        def save(snapshot):
            clock.ticks+=outcome.duration
            return outcome.ok
        owner.m_Store=NS(Save=save)
        source=(ROOT/'4_World/Ecology/HCEcologyRuntime.c').read_text()
        bind(source,('HCWriteCheckpoint','HCRecordSaveTicks'),owner,env,'HCEcologyRuntime')
        self.assertTrue(owner.HCWriteCheckpoint())
        self.assertEqual(17,owner.m_SaveMaxTicks, 'shutdown barrier belongs to save cost')
        owner.m_Dirty=True;outcome.ok=False;outcome.duration=29
        self.assertFalse(owner.HCWriteCheckpoint())
        self.assertEqual(29,owner.m_SaveMaxTicks, 'failed IO also consumes save time')
        owner.m_Dirty=False
        before=clock.ticks
        self.assertTrue(owner.HCWriteCheckpoint())
        self.assertEqual(before,clock.ticks, 'clean/off checkpoint has no hidden IO')

    def check_startup_save_cost(self):
        owner,env,clock=runtime_fixture()
        owner.m_Running=False;owner.m_AdmissionMaxTicks=-1;owner.m_SaveMaxTicks=-1
        env['TickCount']=lambda prior:clock.ticks-prior
        env['HCEcologyNative']=NS(Authority=lambda:True)
        env['GetGame']=lambda:NS(GetTime=lambda:100,GetWorldName=lambda:'synthetic-world')
        # Explicit codec port: frozen settings are already on the owner. This
        # scenario exercises the admission-to-store timing path, not JSON IO.
        env['HCEcologySettingsCodec']=NS(MakeData=lambda *args:True,LoadData=lambda *args:True)
        def unavailable(world,session):
            clock.ticks+=41
            return None
        env['HCEcologyRuntimeStore']=lambda:NS(Open=unavailable)
        source=(ROOT/'4_World/Ecology/HCEcologyRuntime.c').read_text()
        source=source.replace('JsonFileLoader<HCEcologyRuntimeSettings>','HCEcologySettingsCodec')
        bind(source,('Begin','HCRecordSaveTicks'),owner,env,'HCEcologyRuntime')
        self.assertFalse(owner.Begin(owner.m_Settings,'synthetic-world','session-b'))
        self.assertEqual(41,owner.m_SaveMaxTicks, 'failed startup store IO belongs to save cost')


if __name__ == '__main__':
    unittest.main()


class EcologySaveJobWiring(unittest.TestCase):
    """Static source contract for the HC-29 lead wiring; native scheduling stays unobserved."""

    def setUp(self):
        self.source = (ROOT/'4_World/Ecology/HCEcologyRuntime.c').read_text()

    def method(self, name):
        start = self.source.index('\t' + name + '(') if ('\t' + name + '(') in self.source else self.source.index(name + '(')
        return self.source[start:self.source.index('\n\t}', start)]

    def test_the_routine_save_job_is_registered_once_bound_and_unregistered_on_every_finish(self):
        start = self.source.index('m_SaveJob.HCBind(this, m_Store);')
        self.assertIn('HCSaveScheduler.HCRegister(m_SaveJob);', self.source[start:start + 300])
        finish = self.method('void Finish')
        self.assertLess(finish.index('HCSaveScheduler.HCFlush(m_SaveJob)'),
                        finish.index('HCSaveScheduler.HCUnregister(m_SaveJob);'))
        self.assertLess(finish.index('HCSaveScheduler.HCUnregister(m_SaveJob);'), finish.index('m_SaveJob.HCDetach();'))
        self.assertEqual(1, self.source.count('HCSaveScheduler.HCRegister('))

    def test_no_statement_carries_more_than_nine_plus_operators(self):
        import re
        for number, line in enumerate(self.source.splitlines(), 1):
            code = re.sub(r'"(?:\\.|[^"\\])*"', '""', line.split('//')[0])
            self.assertLessEqual(code.count('+') - 2 * code.count('++'), 9, 'HCEcologyRuntime.c:%d' % number)
