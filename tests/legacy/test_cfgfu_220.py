"""#220 spec/plan/tasks: exercise joint validation, durable grid, native timing
and configured weather/radio consumers.
Fix-round specification: missing vanilla frequency config must retain chatter;
legacy heat without grid metadata expires explicitly; radio count is registered.
Plan/tasks: regress startup and migration, remove unsupported startup dependency,
validate before expiry and persist configured empty grid, register count, verify.
The requested spec files are absent in this confined worktree. All native ports below are synthetic;
these checks never establish DayZ behavior or network acceptance.
"""
import json
import re
import unittest
from types import SimpleNamespace as N
from tests.legacy.test_c1_infectedcfg import config_fixture as infected
from tests.legacy.test_c2_atmoscfg import config_fixture as atmosphere, ROOT
from tests.legacy.test_c3_survivalcfg import fixture_config
from tests.legacy.test_event_runtime import translate
from tests.legacy.test_group_server import EArray


class Followups(unittest.TestCase):
    def test_vault_quartet_falls_back_together(self):
        for values in ({'VaultMin': 1.9, 'VaultLow': 1.2, 'VaultHigh': 1.3, 'VaultMax': 1.4},
                       {'VaultMin': .1, 'VaultLow': .2, 'VaultHigh': .3, 'VaultMax': .2}):
            cfg, _ = infected(json.dumps({'Reach': values}))
            self.assertEqual((.8, 1.1, 1.6, 2), tuple(getattr(cfg.Reach, k) for k in
                             ('VaultMin','VaultLow','VaultHigh','VaultMax')))
        cfg, _ = infected('{"Reach":{"VaultMin":0.4,"VaultLow":0.8,"VaultHigh":1.2,"VaultMax":1.8}}')
        self.assertEqual(.4, cfg.Reach.VaultMin)

    def test_heartbeat_pair_rejects_equal_inverted_and_partial_overrides(self):
        for ttl, heartbeat in ((30,30),(20,40),(90,120)):
            cfg, logs = atmosphere('HCc2SeasonTuning', image=json.dumps(
                {'SNAPSHOT_TTL_SECONDS':ttl,'SNAPSHOT_HEARTBEAT_SECONDS':heartbeat}))
            self.assertEqual((90,30),(cfg.SNAPSHOT_TTL_SECONDS,cfg.SNAPSHOT_HEARTBEAT_SECONDS))
            self.assertEqual(1,len(logs))
        cfg, logs = atmosphere('HCc2SeasonTuning', image='{"SNAPSHOT_TTL_SECONDS":60,"SNAPSHOT_HEARTBEAT_SECONDS":20}')
        self.assertEqual((60,20),(cfg.SNAPSHOT_TTL_SECONDS,cfg.SNAPSHOT_HEARTBEAT_SECONDS))
        self.assertFalse(logs)

    def test_grade_default_stays_on_slider_steps(self):
        for percent in (1, 59, 99):
            cfg, logs = atmosphere('HCc2PresentationConfig', image=json.dumps({'GradeDefaultPercent':percent}))
            self.assertEqual(60,cfg.GradeDefaultPercent)
            self.assertEqual(1,len(logs))
        for percent in (0,10,60,100):
            cfg, logs = atmosphere('HCc2PresentationConfig', image=json.dumps({'GradeDefaultPercent':percent}))
            self.assertEqual(percent,cfg.GradeDefaultPercent)
            self.assertFalse(logs)

    def test_memory_keeps_saved_grid_when_profile_changes(self):
        from tests.legacy.test_infected_memory_clock import MemoryFixture
        f = MemoryFixture()
        f.memory.m_State.CellMetres = 500
        f.scope['HCInfectedTuning'] = N(Get=lambda:N(Memory=N(CellMetres=1000,DecaySeconds=259200,LoudnessGain=.35)))
        self.assertEqual(.7,f.api.Heat([510,0,10]))
        f.api.Record([510,0,10],.1)
        self.assertEqual(2,len(f.memory.m_State.Cells))
        self.assertAlmostEqual(.735,f.memory.m_State.Cells[1].Value)

    def test_memory_legacy_unknown_grid_expires_heat_instead_of_rekeying(self):
        from tests.legacy.test_infected_memory_clock import MemoryFixture
        source = (ROOT/'4_World/Infected/HCInfectedMemory.c').read_text()
        f = MemoryFixture()
        # Explicit synthetic legacy store authored with a 1000 m operator grid;
        # no grid metadata exists in its JSON, so that history is unknowable.
        f.memory.m_State.CellMetres = 1000
        f.scope['HCInfectedTuning'] = N(Get=lambda:N(Memory=N(CellMetres=1000,DecaySeconds=259200)))
        migrate = translate(source, 'HCResolveGrid', dict(Print=f.logs.append,
            HCJsonFields=N(Has=lambda text,key:key in json.loads(text))), member=True)
        migrate(f.memory, '{"Version":1}')
        self.assertEqual([], list(f.memory.m_State.Cells), 'unknown legacy grid must expire heat')
        self.assertEqual(1000, f.memory.m_State.CellMetres)
        self.assertTrue(f.memory.m_Dirty)
        self.assertEqual(0, f.api.Heat([1010,0,10]))
        self.assertTrue(any('legacy_heat_expired_unknown_grid' in line and 'runtime=PENDING' in line
                            for line in f.logs))
        # Explicit metadata is authoritative, even if tuning changes later.
        f = MemoryFixture()
        migrate(f.memory, '{"Version":1,"CellMetres":500}')
        self.assertEqual(2, len(f.memory.m_State.Cells))
        self.assertEqual(.7, f.api.Heat([510,0,10]))
        self.assertFalse(f.memory.m_Dirty)

    def test_memory_legacy_start_validates_then_persists_empty_configured_grid(self):
        from tests.legacy.test_infected_memory_clock import MemoryFixture
        source = (ROOT/'4_World/Infected/HCInfectedMemory.c').read_text()
        # Explicit synthetic native JSON out-parameter seam, not migration policy.
        source = source.replace('s_Instance', 'm_StaticInstance')
        source = source.replace('HCV2ThreatStore<HCInfectedMemoryState>', 'SyntheticStore')
        source = source.replace('HCInfectedMemoryState', 'HCEventMemoryState')
        source = source.replace('HCInfectedMemoryCell', 'HCEventMemoryCell')
        source = source.replace('string image;', 'string image = SyntheticImage();')
        source = source.replace('JsonFileLoader<HCEventMemoryState>.LoadData(image, m_State, error)',
                                'SyntheticLoad(this)')
        source = re.sub(r'for \(int (\w+) = ([^;]+); \1 < ([^;]+); \1\+\+\)',
                        r'foreach (int \1 : range(\2, \3))', source)
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt):
                f = MemoryFixture()
                state = f.memory.m_State
                state.CellMetres = 0  # native zero-fill for absent metadata
                if corrupt: state.Cells[0].Value = 2
                image = json.dumps({'Version':1, 'Cells':[{'X':0,'Z':0}]})
                persisted = []
                def load(memory):
                    memory.m_State = state
                    return True
                env = dict(Print=f.logs.append, range=range, PATH='synthetic-memory.json',
                    HCGroupClock=N(SampleUtc=lambda:f.last),
                    HCGroupIO=N(Read=lambda *args:True), FileExist=lambda path:True,
                    HCJsonFields=N(Has=lambda text,key:key in json.loads(text)),
                    HCFieldsPresent=lambda text:True,  # coordinates explicitly present above
                    HCInfectedTuning=N(Get=lambda:N(Memory=N(CellMetres=1000))),
                    GetGame=lambda:N(IsServer=lambda:True,GetWorldName=lambda:'synthetic_world'),
                    SyntheticStore=N(CanOpen=lambda path:True, Save=lambda path,state,cap:
                        persisted.append(json.dumps(state,default=vars)) or True),
                    SyntheticImage=lambda:image, SyntheticLoad=load)
                f.memory.m_StaticInstance = None
                f.memory.HCFieldsPresent = env['HCFieldsPresent']
                f.memory.Tick = lambda: f.memory.Save(f.last)  # existing synchronous startup save seam
                for name in ('Valid','HCResolveGrid','Save','Start'):
                    fn = translate(source,name,env,'Memory',member=True)
                    setattr(f.memory,name,fn.__get__(f.memory))
                result = f.memory.Start()
                self.assertEqual(not corrupt,result)
                if corrupt:
                    self.assertEqual([],persisted)
                    self.assertEqual(2,len(state.Cells), 'invalid legacy state must be preserved')
                else:
                    saved = json.loads(persisted[0])
                    self.assertEqual(1000,saved['CellMetres'])
                    self.assertEqual([],saved['Cells'])
                    self.assertFalse(f.memory.m_Dirty)

    def test_admin_bucket_matches_configured_partition(self):
        source=(ROOT/'4_World/Weather/HCWeatherDaysModule.c').read_text()
        for bad,fog in ((1,3),(2,4),(0,0),(5,5)):
            cfg=N(BadDayBuckets=bad,FogMorningBuckets=fog)
            match=translate(source,'HCAdminBucket',dict(HCWeatherConfig=N(HCGet=lambda:cfg)))
            for bucket in range(5):
                self.assertEqual(bucket < bad,match(4,bucket))
                self.assertEqual(bad <= bucket < fog,match(3,bucket))
                self.assertEqual(bucket >= max(bad,fog),match(1,bucket))
                self.assertEqual(bucket >= max(bad,fog),match(2,bucket))

    def test_salvage_callback_uses_server_replicated_duration(self):
        source=(ROOT/'4_World/Actions/HCActionSalvageWreck.c').read_text()
        source=source.replace('new CAContinuousTime(', 'SyntheticTime(').replace('m_ActionComponent', 'Component').replace('m_Player', 'Actor')
        callback=translate(source,'CreateActionComponent',dict(SyntheticTime=lambda seconds:seconds,
            HCWreckSalvageConfig=N(Get=lambda:N(ActionSeconds=1))),member=True)
        action=N(Actor=N(HCWreckActionSeconds=lambda:15),Component=None)
        callback(N(m_ActionData=action))
        self.assertEqual(15,action.Component)
        self.assertIn('RegisterNetSyncVariableFloat("m_HCWreckActionSeconds"',source)

    def test_radio_qualifies_native_list_count_range_and_membership(self):
        source=(ROOT/'4_World/Leads/HCRadioChatter.c').read_text()
        cfg=fixture_config('HCRadioDefaults',{'LocalsMHz':99.9})
        env=dict(Print=lambda line:None,EArray=EArray,HCRadioDefaults=N(),Math=N(AbsFloat=abs))
        valid=translate(source,'HCQualifyChannels',env,member=True)
        native=EArray([87.8,89.5,91.3,94.6,96.6,99.7,102.5])
        self.assertTrue(valid(cfg,native))
        self.assertEqual(87.8,cfg.LocalsMHz)  # in-range but untunable override falls back
        for bad in (EArray(),EArray([87.8]*65),EArray([87.8,200]),EArray([87.8,87.8])):
            self.assertFalse(valid(cfg,bad))
        self.assertFalse(valid(cfg,EArray([87.8]))) # missing canonical channels

    def test_saved_grid_survives_json_roundtrip_and_invalid_metadata_refuses(self):
        from tests.legacy.test_infected_memory_clock import MemoryFixture
        f=MemoryFixture()
        f.memory.m_Dirty=True
        captured=[]
        source=(ROOT/'4_World/Infected/HCInfectedMemory.c').read_text()
        source=source.replace('HCV2ThreatStore<HCInfectedMemoryState>','SyntheticStore')
        def persist(path,state,cap):
            captured.append(json.dumps(state,default=lambda value:vars(value)))
            return True
        save=translate(source,'Save',dict(PATH='synthetic-memory.json',
            SyntheticStore=N(Save=persist)),member=True)
        self.assertTrue(save(f.memory,f.last))
        state=json.loads(captured[0])
        self.assertEqual(500,state['CellMetres'])
        restarted=MemoryFixture()
        restarted.memory.m_State=N(**state)
        restarted.memory.m_State.Cells=EArray(N(**cell) for cell in state['Cells'])
        restarted.scope['HCInfectedTuning']=N(Get=lambda:N(Memory=N(CellMetres=1000,DecaySeconds=259200)))
        self.assertEqual(.7,restarted.api.Heat([510,0,10]))
        # Execute real state validation, adapting only native type/loop syntax.
        source=source.replace('HCInfectedMemoryCell','HCEventMemoryCell')
        source=re.sub(r'for \(int (\w+) = ([^;]+); \1 < ([^;]+); \1\+\+\)',
                      r'foreach (int \1 : range(\2, \3))',source)
        valid=translate(source,'Valid',dict(range=range,
            GetGame=lambda:N(GetWorldName=lambda:'synthetic_world')),member=True)
        self.assertTrue(valid(restarted.memory,f.last))
        for value in (0,49,2001,float('nan')):
            restarted.memory.m_State.CellMetres=value
            self.assertFalse(valid(restarted.memory,f.last))

    def test_salvage_duration_is_published_only_by_server(self):
        source=(ROOT/'4_World/Actions/HCActionSalvageWreck.c').read_text().split('modded class PlayerBase')[1]
        source=source.replace('super.EEInit();','NativeInit();')
        dirty=[]
        actor=N(m_HCWreckActionSeconds=0,SetSynchDirty=lambda:dirty.append(True))
        for server in (False,True):
            init=translate(source,'EEInit',dict(NativeInit=lambda:None,
                GetGame=lambda:N(IsServer=lambda:server), SetSynchDirty=actor.SetSynchDirty,
                HCWreckSalvageConfig=N(Get=lambda:N(ActionSeconds=15))),member=True)
            init(actor)
            self.assertEqual(15 if server else 0,actor.m_HCWreckActionSeconds)
        self.assertEqual([True],dirty)

    def test_radio_count_limit_is_an_operator_tunable(self):
        source=(ROOT/'4_World/Leads/HCRadioChatter.c').read_text()
        cfg=fixture_config('HCRadioDefaults',{'ChannelCountLimit':5})
        valid=translate(source,'HCQualifyChannels',dict(Print=lambda line:None,EArray=EArray),member=True)
        self.assertFalse(valid(cfg,EArray([87.8,89.5,91.3,94.6,96.6,99.7,102.5])))
        self.assertTrue(valid(cfg,EArray([87.8,89.5,91.3,94.6,96.6])))

    def test_radio_count_registry_enforces_declared_bounds(self):
        from tests.legacy.settings_registry_fixture import install_registry
        registry = install_registry({})
        rule = registry.HCFind('Radio.ChannelCountLimit')
        self.assertEqual(('int',64,1,64,'HCRadioDefaults'),
                         (rule.ValueKind,rule.DefaultValue,rule.Minimum,rule.Maximum,rule.Owner))
        for value in (1,5,64):
            self.assertTrue(registry.HCValid('Radio.ChannelCountLimit',value))
        for value in (0,65,float('nan')):
            self.assertFalse(registry.HCValid('Radio.ChannelCountLimit',value))

    def test_existing_team_ping_and_camp_theft_registry_rows_are_present(self):
        rows=json.loads((ROOT.parents[2]/'tools/validate/shared_settings.json').read_text())
        by_key={row['key']:row for row in rows}
        for key,kind,default,lower,upper,owner in (
            ('Radio.ChannelCountLimit','int',64,1,64,'HCRadioDefaults'),
            ('EnableTeamPing','bool',True,0,1,'HCSettings'),
            ('CampTheft.Version','int',1,1,1,'HCTheftConfig'),
            ('CampTheft.MaxAttemptsPerDay','int',1,1,6,'HCTheftConfig'),
            ('CampTheft.MaxAttendancePlayers','int',32,1,32,'HCTheftConfig'),
            ('CampTheft.AttendanceRangeMeters','float',500,500,1000,'HCTheftConfig'),
            ('CampTheft.ObserverRangeMeters','float',500,500,1000,'HCTheftConfig')):
            self.assertEqual(dict(key=key,type=kind,default=default,min=lower,max=upper,owner=owner),by_key[key])
