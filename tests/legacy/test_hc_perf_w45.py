"""w45 synthetic clocks/files; executes authored slices, never DayZ evidence."""
import functools
import json
import re
import tempfile
from pathlib import Path
from types import SimpleNamespace as N
import unittest
from tests.legacy.test_hc_unit_budget import translated, SchedulerHarness, FakeJob

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / 'mods/HollowCountry/scripts/4_World/World'
DEBUG = ROOT / 'mods/HollowCountry/scripts/4_World/Debug'

class PerfSlices(unittest.TestCase):
    def test_profile_caps_count_and_keeps_explicit_shorter_deadline(self):
        source = (WORLD / 'HCPerfSlices.c').read_text()
        calls = []
        cfg = N(EcologyRowsPerTick=4, InteriorStepsPerTick=1, HoldoutRowsPerTick=1,
                SliceMs=4, SaveStageTargetMs=10)
        env = dict(HCPerfConfig=N(HCGet=lambda:cfg), Math=N(Min=min),
                   HCBaseReset=lambda limit, ms:calls.append((limit, ms)))
        source = source.replace('super.HCReset(', 'HCBaseReset(').replace('HCPerfConfig config', 'HCEventConfig config')
        for kind, expected in (('Ecology',3), ('Interiors',1), ('Holdouts',1)):
            obj = N(m_Profile=kind)
            translated(source, 'HCReset', env, 'HCPerfSlices')(obj, 32, 2)
            self.assertEqual((expected, 2), calls[-1])
        translated(source, 'HCReset', env, 'HCPerfSlices')(N(m_Profile='Ecology'), 2, 4)
        self.assertEqual((1,4), calls[-1])

    def test_real_ecology_prune_uses_the_configured_cap_and_eventually_finishes(self):
        from tests.legacy.test_hc_ecology_budget import runtime_fixture
        from tests.legacy.test_group_server import EArray
        base=(WORLD/'HCWorkBudget.c').read_text()
        source=(WORLD/'HCPerfSlices.c').read_text().replace('super.HCReset(', 'HCBaseReset(').replace('HCPerfConfig config','HCEventConfig config')
        for cap in (1,4,32):
            runtime, _, _ = runtime_fixture()
            work=N(m_Profile='Ecology')
            env=dict(GetGame=lambda:N(GetTickTime=lambda:100.),Math=N(Min=min),
                     HCPerfConfig=N(HCGet=lambda:N(EcologyRowsPerTick=cap,SliceMs=4)))
            reset=translated(base,'HCReset',env,'HCWorkBudget')
            env['HCBaseReset']=lambda limit,ms:reset(work,limit,ms)
            work.HCReset=functools.partial(translated(source,'HCReset',env,'HCPerfSlices'),work)
            guard=translated(base,'HCMayContinue',{},'HCWorkBudget')
            work.HCContinue=lambda:guard(work,0.)
            runtime.m_Work=work
            runtime.m_Resources=EArray(N(Live=None,LocalId='dead-'+str(i)) for i in range(70))
            runtime.m_PruneCursor=69
            for tick in range(72):
                before=len(runtime.m_Resources)
                runtime.StagePrune(100)
                self.assertLessEqual(before-len(runtime.m_Resources),cap)
                if runtime.m_Stage != 1: break
            self.assertEqual([],runtime.m_Resources)
            self.assertEqual(2,runtime.m_Stage)

    def test_snapshot_encoding_and_file_promotion_are_separate_ticks(self):
        source = (DEBUG / 'HCPerfSnapshotSave.c').read_text()
        calls = []
        env = dict(STEP_MORE=1, STEP_DONE=0, STEP_FAILED=2,
                   JsonFileLoader=N(), HCGroupIO=N(), FileExist=lambda p:False,
                   DeleteFile=lambda p:True, CopyFile=lambda a,b:True)
        obj = N(m_Phase=0, m_Text='', m_Bytes=0,
                HCEncode=lambda phase:calls.append(('encode',phase)) or True,
                HCWriteIntent=lambda:calls.append(('intent',)) or True,
                HCBackup=lambda:calls.append(('backup',)) or True,
                HCPromote=lambda:calls.append(('promote',)) or True,
                HCClean=lambda:calls.append(('clean',)) or True)
        step = translated(source, 'HCStep', env, 'HCPerfSnapshotSave')
        for phase in range(8):
            before = len(calls)
            self.assertEqual(0 if phase == 7 else 1, step(obj))
            self.assertEqual(1, len(calls)-before)
        self.assertEqual([('encode',i) for i in range(4)] +
                         [('intent',),('backup',),('promote',),('clean',)], calls)

    def test_failed_snapshot_stage_is_not_advanced(self):
        source = (DEBUG / 'HCPerfSnapshotSave.c').read_text()
        obj = N(m_Phase=4, HCWriteIntent=lambda:False)
        step = translated(source,'HCStep',dict(STEP_MORE=1,STEP_DONE=0,STEP_FAILED=2),'HCPerfSnapshotSave')
        self.assertEqual(2,step(obj))
        self.assertEqual(4,obj.m_Phase)

    def test_shared_save_off_does_not_disable_explicit_owner_flush(self):
        source = (WORLD / 'HCWorkBudget.c').read_text()
        env = dict(HCPerfConfig=N(HCGet=lambda:N(EnableSharedSaves=False)))
        enabled = translated(source, 'IsEnabled', env, 'HCSaveScheduler')
        self.assertFalse(enabled(N(), N()))
        h = SchedulerHarness(); h.setUp()
        a = FakeJob('synthetic', [h.consts['STEP_MORE'],h.consts['STEP_DONE']],h.env)
        self.assertTrue(h.sched.HCFlush(a))
        self.assertFalse(a.HCDirty)
        self.assertEqual(2,a.calls)

class IntegrationSlices(unittest.TestCase):
    def test_final_interior_link_replaces_the_retained_pack_budget(self):
        source=(ROOT/'mods/HollowCountry/scripts/4_World/Interiors/HCPerfInteriorSlices.c').read_text()
        source=source.replace('super.OnStart(settings)','self.LegacyStart(settings)').replace('new HCPerfSlices(', 'HCMakeSlices(')
        events=[]
        env=dict(HCMakeSlices=lambda profile:N(profile=profile),Print=events.append)
        owner=N(LegacyStart=lambda settings:events.append('legacy'))
        translated(source,'OnStart',env,'HCInteriorsModule')(owner,N())
        self.assertEqual('legacy',events[0])
        self.assertEqual('Interiors',owner.m_PackBudget.profile)

    def test_holdout_catalog_progresses_before_the_ten_second_simulation_deadline(self):
        source=(WORLD/'HCHoldouts.c').read_text()
        for cls in ('HCHoldoutRow','HCHoldoutBody','HCSearchHouses','HCWorldModule'):
            source=source.replace(cls,'HCEvent'+cls[2:])
        # Syntax-only adapter for the native descending for loop. Its start,
        # stop and decrement are unchanged, even if the array shrinks.
        source=source.replace('for (int bodyIndex = m_Bodies.Count() - 1; bodyIndex >= 0; bodyIndex--)',
                              'for bodyIndex in range(m_Bodies.Count() - 1, -1, -1):')
        seen=[]
        owner=N(m_Ready=True,m_Elapsed=0,m_State=N(TemplatePin=''),m_CatalogDirty=False,
                m_WorkBudget=N(HCDeferred=lambda *args:None),GetName=lambda:'Holdouts')
        def fill():
            seen.append('catalog')
            owner.m_CatalogDirty=True  # synthetic new row awaits durability
        owner.FillCatalog=fill
        env=dict(HCEventWorldModule=N(Get=lambda:N()),
                 HCInteriorTemplates=N(Loaded=lambda:True),Print=lambda line:None)
        tick=translated(source,'OnTick',env,'HCHoldouts')
        tick(owner,1.)
        self.assertEqual(['catalog'],seen)
        self.assertEqual(1.,owner.m_Elapsed)

    def test_scheduler_reports_only_new_peaks_over_the_configured_target(self):
        source=(WORLD/'HCPerfSaveSlices.c').read_text().replace('super.OnTick(deltaTime)','self.LegacyTick(deltaTime)')
        clock=[100.0]; logs=[]
        env=dict(GetGame=lambda:N(GetTickTime=lambda:clock[0]),
                 HCPerfConfig=N(HCGet=lambda:N(SaveStageTargetMs=10)),Print=logs.append)
        owner=N(m_PeakStageMs=0,LegacyTick=lambda dt:clock.__setitem__(0,clock[0]+0.020))
        tick=translated(source,'OnTick',env,'HCSaveScheduler')
        tick(owner,1); tick(owner,1)
        self.assertEqual(1,len(logs))
        self.assertIn('stage_over_target_ms=',logs[0])
        self.assertIn('runtime=PENDING',logs[0])

class ConfigAndStore(unittest.TestCase):
    def test_missing_keys_keep_defaults_and_explicit_false_is_kept(self):
        source = (WORLD / 'HCPerfSlices.c').read_text()
        defaults = {k:json.loads(v) for k,v in re.findall(r'^    (?:int|bool) (\w+) = (\w+);',source,re.M)}
        registry=(ROOT/'mods/HollowCountry/scripts/3_Game/HCPerfSettingsRegistry.c').read_text()
        bounds = {k:(int(lo),int(hi)) for k,lo,hi in re.findall(
            r'HCAdd\("Performance\.(\w+)", "(?:bool|int)", \d+, (\d+), (\d+),',registry)}
        self.assertEqual(set(defaults), set(bounds))
        scope = dict(HCJsonFields=N(Has=lambda text,key:key in json.loads(text)),
                     HCOperatorSettingsRegistry=N(HCValid=lambda key,val: bounds[key.split('.')[-1]][0] <= val <= bounds[key.split('.')[-1]][1]))
        # Syntax adapter: the DTO's public fields are instance members too.
        for key in defaults:
            source = re.sub(r'(?<![\w.])' + key + r' = decoded\.', 'self.'+key+' = decoded.',source)
        apply = translated(source,'HCApply',scope,'HCPerfConfig')
        actual=N(**defaults)
        zero=N(**dict.fromkeys(defaults,0))  # explicit synthetic loader zero-fill
        apply(actual,zero,'{}')
        self.assertEqual(defaults,vars(actual))
        apply(actual,zero,'{"EnableSharedSaves":false,"SliceMs":0}')
        self.assertEqual(actual.EnableSharedSaves,0)  # fixture value, explicit key preserved
        self.assertEqual(4,actual.SliceMs)  # invalid integer retains default

    def test_staged_file_ports_preserve_verified_primary_and_retain_failed_intent(self):
        # Real authored backup/promote/clean bodies; only native disk ports synthetic.
        from tests.legacy.test_admin_test_kit import base_scope
        from tests.legacy.test_debug_map_layers import compile_authored
        source=DEBUG/'HCPerfSnapshotSave.c'
        files={'snapshot':'old','snapshot.tmp':'new'}
        calls=[]
        io=N()
        def read(path,limit):
            calls.append(('read',path))
            return files.get(path,'')
        def copy(a,b):
            calls.append(('copy',a,b)); files[b]=files[a]; return True
        def delete(p):
            calls.append(('delete',p)); return files.pop(p,None) is not None
        scope=base_scope(HCGroupIO=io,FileExist=lambda p:p in files,
                         CopyFile=copy,DeleteFile=delete)
        scope['NativeRead']=read
        # Explicit fixture copy adapts native out-string syntax only. Empty
        # native reads fail in HCGroupIO; no store decisions are supplied here.
        adapted=source.read_text().replace(
            'if (!HCGroupIO.Read(m_Path, m_Limit, previous))',
            'previous = NativeRead(m_Path, m_Limit); if (previous == "")').replace(
            'return HCGroupIO.Read(backup, m_Limit, backedUp) && backedUp == previous;',
            'backedUp = NativeRead(backup, m_Limit); return backedUp != "" && backedUp == previous;').replace(
            'return HCGroupIO.Read(m_Path, m_Limit, actual) && actual == m_Text;',
            'actual = NativeRead(m_Path, m_Limit); return actual != "" && actual == m_Text;')
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        source=Path(temp.name)/'HCPerfSnapshotSave.c'; source.write_text(adapted)
        obj=N(m_Path='snapshot',m_Limit=1024,m_Text='new')
        backup=compile_authored(source,'HCPerfSnapshotSave','HCBackup',scope,
                                modded=False,fields=('m_Path','m_Limit','m_Text'))
        promote=compile_authored(source,'HCPerfSnapshotSave','HCPromote',scope,
                                 modded=False,fields=('m_Path','m_Limit','m_Text'))
        clean=compile_authored(source,'HCPerfSnapshotSave','HCClean',scope,
                               modded=False,fields=('m_Path','m_Limit','m_Text'))
        self.assertTrue(backup(obj))
        self.assertEqual('old',files['snapshot.bak'])
        self.assertEqual('old',files['snapshot'])
        self.assertTrue(promote(obj))
        self.assertEqual('new',files['snapshot'])
        self.assertIn('snapshot.tmp',files)
        self.assertTrue(clean(obj))
        self.assertNotIn('snapshot.tmp',files)
        files['snapshot.tmp']='next'
        scope['CopyFile']=lambda a,b:False
        # compile_authored captures its scope, so compile against the failing
        # synthetic copy port to prove the primary and intent are retained.
        backup_fail=compile_authored(source,'HCPerfSnapshotSave','HCBackup',scope,
                                     modded=False,fields=('m_Path','m_Limit','m_Text'))
        self.assertFalse(backup_fail(obj))
        self.assertEqual('new',files['snapshot'])
        self.assertEqual('next',files['snapshot.tmp'])

if __name__ == '__main__': unittest.main()
