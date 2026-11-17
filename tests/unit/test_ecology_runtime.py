"""Authored ecology decisions executed with explicit synthetic native/storage ports.
No native movement, sensory eligibility, replication or durability is qualified.
"""
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from tests.unit.test_event_runtime import translate as event_translate
from tests.unit.test_group_server import EArray, body

ROOT = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts"


def translated(text, name, env, owner, member=False):
    # Reuse the established syntax-only translator; no ecology decisions here.
    renamed = text.replace("HCEcology", "HCEvent")
    if member:
        renamed = re.sub(r"\bthis\b", "self", renamed)
    renamed = re.sub(r"new array<([^>]+)>(?!\s*\()", r"new array<\1>()", renamed)
    renamed = re.sub(r"(\b[\w.]+)\+\+;", r"\1 += 1;", renamed)
    renamed = re.sub(r"(\b[\w.]+)--;", r"\1 -= 1;", renamed)
    renamed_env = {k.replace("HCEcology", "HCEvent"): v for k, v in env.items()}
    f = event_translate(renamed, name, renamed_env, owner.replace("HCEcology", "HCEvent"), member)
    return f


def environment():
    data = (ROOT / "3_Game/Ecology/HCEcologyRuntimeData.c").read_text()
    env = dict(EArray=EArray, len=len, str=str, Print=lambda s: None)
    env["Math"] = SimpleNamespace(AbsFloat=abs, Min=min, Max=max)
    env["vector"] = SimpleNamespace(DistanceSq=lambda a, b: sum((x-y)**2 for x,y in zip(a,b)))
    for m in re.finditer(r"class (\w+)\s*\{", data):
        fields = re.findall(r"^\s*(?:ref )?([\w<> ]+?) (\w+)(?:\s*=\s*([^;]+))?;", body(data,m.end()), re.M)
        def factory(fields=fields):
            item = SimpleNamespace()
            for typ,key,default in fields:
                if "array<" in typ: value=EArray()
                elif typ == "vector": value=[0.,0.,0.]
                elif default: value=json.loads(default)
                else: value={"string":"","bool":False,"int":0,"float":0.}.get(typ)
                setattr(item,key,value)
            return item
        env[m[1]]=factory
    text=(ROOT/"4_World/Ecology/HCEcologyRuntimeRules.c").read_text()
    rules=SimpleNamespace(); env["HCEcologyRuntimeRules"]=rules
    for name in re.findall(r"static (?:bool|int|float|string|HCEcology\w+) (\w+)\(",text):
        setattr(rules,name,translated(text,name,env,"HCEcologyRuntimeRules"))
    return env


class EcologyRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.e=environment(); self.r=self.e["HCEcologyRuntimeRules"]
        self.cfg=self.e["HCEcologyRuntimeSettings"]()
        self.state=self.e["HCEcologyCheckpoint"]()
        self.state.WorldName="synthetic-world"; self.state.SessionId="session-a"
        self.state.Version=1;self.state.Revision=1
        self.state.Samples=self.state.PathQueries=0
    def test_enabled_preference_template_and_bounded_defaults(self):
        self.assertTrue(self.cfg.Enabled)
        self.assertTrue(self.r.SettingsValid(self.cfg))
        for field,value in (("MaxActors",33),("MaxResources",33),("MaxPathQueries",9),
                            ("TickMs",0),("FreshMs",60001),("IntentMs",0),
                            ("Radius",float("nan")),("Radius",float("inf")),("Radius",121.)):
            old=getattr(self.cfg,field); setattr(self.cfg,field,value)
            self.assertFalse(self.r.SettingsValid(self.cfg),(field,value))
            setattr(self.cfg,field,old)
    def test_explicit_disable_is_valid(self):
        self.cfg.Enabled=False
        self.assertTrue(self.r.SettingsValid(self.cfg))
    def test_clock_rejects_rollback_overflow_and_same_tick(self):
        for now,last in ((99,100),(100,100),(-1,0),(2147483647,100)):
            self.assertFalse(self.r.TickDue(now,last,1000))
        self.assertTrue(self.r.TickDue(1100,100,1000))
    def test_freshness_expiry_and_future(self):
        self.assertTrue(self.r.Fresh(100,200,100))
        for observed,now,age in ((201,200,100),(99,200,100),(-1,200,100)):
            self.assertFalse(self.r.Fresh(observed,now,age))
    def test_food_and_water_are_presence_not_consumption(self):
        for qty in (0.,-1.,float("nan"),float("inf")):
            self.assertEqual(0,self.r.ResourceKind(True,False,True,qty,False,False,False))
        self.assertEqual(1,self.r.ResourceKind(True,False,True,2.,False,False,False))
        self.assertEqual(2,self.r.ResourceKind(False,True,True,2.,False,False,False))
        self.assertEqual(2,self.r.ResourceKind(False,False,False,0.,True,False,False))
        for parent,ruined in ((True,False),(False,True)):
            self.assertEqual(0,self.r.ResourceKind(True,False,True,2.,False,parent,ruined))
    def test_quantityless_food_presence_is_not_infinite_stock(self):
        self.assertEqual(1,self.r.ResourceKind(True,False,False,0.,False,False,False))
        source=(ROOT/"4_World/Ecology/HCEcologyNative.c").read_text()
        self.assertNotIn("SetQuantity(",source)
        self.assertNotIn("SetHealth(",source)
    def test_position_finite_without_invented_map_boundary(self):
        self.assertTrue(self.r.PositionValid([-500.,0.,90000.]))
        for p in ([float("nan"),0.,0.],[0.,float("inf"),0.],[0.,0.,-float("inf")]):
            self.assertFalse(self.r.PositionValid(p))
    def test_session_entity_serial_not_durable_identity(self):
        self.assertEqual("session-a:7",self.r.LocalId("session-a",7))
        for session,n in (("",1),("a/b",1),("x",0),("x",2147483647)):
            self.assertEqual("",self.r.LocalId(session,n))
    def test_checkpoint_world_schema_and_counts(self):
        self.assertTrue(self.r.CheckpointValid(self.state,"synthetic-world"))
        for field,value in (("Version",2),("WorldName","other"),("Revision",0),
                             ("Samples",-1),("PathQueries",1000000001),("SessionId","")):
            old=getattr(self.state,field); setattr(self.state,field,value)
            self.assertFalse(self.r.CheckpointValid(self.state,"synthetic-world"))
            setattr(self.state,field,old)
    def test_checkpoint_never_restores_actor_handles_assignments_or_ms_clock(self):
        text=(ROOT/"3_Game/Ecology/HCEcologyRuntimeData.c").read_text()
        start=re.search(r"class HCEcologyCheckpoint\s*\{",text).end()
        fields=body(text,start)
        for forbidden in ("ActorId","EntityAI","Assignments","NextTick","LastNowMs"):
            self.assertNotIn(forbidden,fields)
    def test_missing_checkpoint_fields_cannot_reset_diagnostics(self):
        incomplete=self.e["HCEcologyCheckpoint"]()
        incomplete.WorldName="synthetic-world";incomplete.SessionId="session-a"
        incomplete.Revision=1
        self.assertFalse(self.r.CheckpointValid(incomplete,"synthetic-world"))
    def test_cross_tick_zone_and_actor_capacity(self):
        intents=EArray()
        first=self.e["HCEcologyRouteIntent"]()
        first.ActorId="a"; first.ResourceId="water"; first.IssuedAtMs=100;first.ExpiresAtMs=200
        intents.Insert(first)
        self.assertFalse(self.r.Capacity(intents,"b","water",150,8))
        self.assertFalse(self.r.Capacity(intents,"a","food",150,8))
        self.assertTrue(self.r.Capacity(intents,"b","food",150,8))
        self.assertTrue(self.r.Capacity(intents,"a","water",200,8))
        self.assertFalse(self.r.Capacity(intents,"b","food",150,1))
    def test_route_refuses_stale_context_nonfinite_and_unbounded_path(self):
        route=self.e["HCEcologyRouteIntent"]()
        route.WorldName="synthetic-world";route.SessionId="session-a"
        route.ActorId="a";route.ResourceId="r";route.IssuedAtMs=100;route.ExpiresAtMs=200
        route.PathPoints=2;route.PathLength=3.;route.NativePath=True
        self.assertTrue(self.r.IntentValid(route,"synthetic-world","session-a",150,120.))
        for field,value in (("NativePath",False),("PathPoints",65),("PathLength",float("nan")),
                             ("ExpiresAtMs",100),("SessionId","old")):
            old=getattr(route,field);setattr(route,field,value)
            self.assertFalse(self.r.IntentValid(route,"synthetic-world","session-a",150,120.))
            setattr(route,field,old)
    def test_persistence_never_falls_back_when_pending_or_missing_image(self):
        self.assertFalse(self.r.CheckpointAdmission(True,True,True))
        self.assertFalse(self.r.CheckpointAdmission(False,True,False))
        self.assertTrue(self.r.CheckpointAdmission(False,True,True))
        self.assertTrue(self.r.CheckpointAdmission(False,False,False))
    def test_all_counter_increments_guarded(self):
        self.assertTrue(self.r.CountersFit(self.state,32,8))
        self.state.Samples=1000000000
        self.assertFalse(self.r.CountersFit(self.state,1,0))
        self.state.Samples=0;self.state.PathQueries=1000000000
        self.assertFalse(self.r.CountersFit(self.state,0,1))
    def test_settings_no_eligibility_or_feeding_capability_assumption(self):
        text=(ROOT/"3_Game/Ecology/HCEcologyRuntimeData.c").read_text()
        self.assertNotIn("SupportsAnimalNavigation = true",text)
        self.assertNotIn("FeedingAccepted",text)
    def test_store_write_intent_precedes_replace_and_clear_follows_readback(self):
        source=(ROOT/"4_World/Ecology/HCEcologyRuntimeStore.c").read_text()
        method=body(source,re.search(r"bool Save\([^)]*\)\s*\{",source).end())
        intent=method.index('WriteNew(m_Root + "/pending.json"')
        image=method.index('Write(m_Root + "/state.json"')
        readback=method.index('Read(m_Root + "/state.json"')
        clear=method.index('DeleteFile(m_Root + "/pending.json"')
        self.assertLess(intent,image);self.assertLess(image,readback);self.assertLess(readback,clear)
        self.assertNotIn("CopyFile(",source)
        self.assertIn("limit + 1",source)
    def test_lifecycle_is_bounded_fail_closed_without_registration_edit(self):
        source=(ROOT/"4_World/Ecology/HCEcologyRuntime.c").read_text()
        for required in ("bool Start(","void Tick(","void Stop(","MaxPathQueries",
                         "MaxActors","MaxResources","m_NextSerial","HCEcologyNative.ProbePath",
                         "HCEcologyRules.Schedule","HCEcologyRules.Commit"):
            self.assertIn(required,source)
        self.assertNotIn("HCModuleRegistry",source)
        self.assertNotIn("CreateObject",source)
        self.assertNotIn("SetPosition",source)


class EcologyStoreBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.e=environment();self.files={};self.trace=[];self.fail=""
        self.state=self.e["HCEcologyCheckpoint"]()
        self.state.WorldName="synthetic-world";self.state.SessionId="session-a";self.state.Revision=1
        self.state.Version=1;self.state.Samples=self.state.PathQueries=0
        self.store=SimpleNamespace(m_Root="owned",m_World="synthetic-world",m_Session="session-a",m_Revision=0,m_Fault=False)
        def write(path,text,limit):
            self.trace.append(("write",path))
            if self.fail=="image" and path.endswith("state.json"):
                self.files[path]="torn";return False
            self.files[path]=text;return True
        def new(path,text,limit):
            self.trace.append(("new",path))
            if path in self.files or self.fail=="intent":return False
            self.files[path]=text;return True
        def read(path,limit):
            self.trace.append(("read",path))
            return "corrupt" if self.fail=="readback" else self.files.get(path,"")
        def delete(path):
            self.trace.append(("delete",path))
            if self.fail=="clear":return False
            del self.files[path];return True
        self.e["HCEcologyRuntimeIO"]=SimpleNamespace(
            Encode=lambda s:json.dumps(vars(s),sort_keys=True),Write=write,WriteNew=new,Read=read)
        self.e["DeleteFile"]=delete
        source=(ROOT/"4_World/Ecology/HCEcologyRuntimeStore.c").read_text()
        self.save=translated(source,"Save",self.e,"HCEcologyRuntimeStore",True)
    def test_success_advances_only_after_readback_and_removes_intent(self):
        self.assertTrue(self.save(self.store,self.state))
        self.assertEqual(1,self.store.m_Revision)
        self.assertFalse(self.store.m_Fault)
        self.assertNotIn("owned/pending.json",self.files)
        self.assertEqual(["new","write","read","delete"],[op for op,path in self.trace])
    def test_each_native_write_or_readback_failure_poisoned_no_retry(self):
        for mode in ("intent","image","readback","clear"):
            self.setUp();self.fail=mode
            self.assertFalse(self.save(self.store,self.state),mode)
            self.assertEqual(0,self.store.m_Revision)
            self.assertTrue(self.store.m_Fault)
            before=list(self.trace);self.fail=""
            self.assertFalse(self.save(self.store,self.state))
            self.assertEqual(before,self.trace)
            if mode!="intent":self.assertIn("owned/pending.json",self.files)
    def test_revision_replay_and_world_mismatch_perform_no_io(self):
        for revision,world in ((0,"synthetic-world"),(2,"synthetic-world"),(1,"other")):
            self.state.Revision=revision;self.state.WorldName=world
            self.assertFalse(self.save(self.store,self.state))
            self.assertEqual([],self.trace)
    def test_foreign_session_save_performs_no_io(self):
        self.state.SessionId="session-b"
        self.assertFalse(self.save(self.store,self.state))
        self.assertEqual([],self.trace)


class EcologyStoreRestartBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.e=environment();self.files={};self.saved=[];self.trace=[]
        self.store=SimpleNamespace(m_Root="owned",m_World="",m_Session="",m_Revision=0,m_Fault=False)
        def decode(text):
            try:
                fields=json.loads(text)
                if not isinstance(fields,dict):return None
                value=self.e["HCEcologyCheckpoint"]()
                for key,field in fields.items():setattr(value,key,field)
                return value
            except (ValueError,TypeError):return None
        def read(path,limit):
            self.trace.append(("read",path))
            text=self.files.get(path,"")
            return text if len(text)<=limit else ""
        self.e["FileExist"]=lambda p:p in self.files or p in ("owned","$profile:HollowCountry")
        self.e["MakeDirectory"]=lambda p:True
        self.e["HCEcologyRuntimeIO"]=SimpleNamespace(Decode=decode,Read=read)
        self.store.Save=lambda s:self.saved.append(s) or True
        source=(ROOT/"4_World/Ecology/HCEcologyRuntimeStore.c").read_text()
        self.open=translated(source,"Open",self.e,"HCEcologyRuntimeStore",True)
        self.prior=dict(Version=1,WorldName="synthetic-world",SessionId="session-a",Revision=7,Samples=12,PathQueries=5)
    def test_fresh_session_carries_only_diagnostic_counters(self):
        self.files["owned/state.json"]=json.dumps(self.prior)
        state=self.open(self.store,"synthetic-world","session-b")
        self.assertIsNotNone(state)
        self.assertEqual((1,"session-b",8,12,5),(state.Version,state.SessionId,state.Revision,state.Samples,state.PathQueries))
        self.assertEqual("session-b",self.store.m_Session)
        self.assertEqual([state],self.saved)
        self.assertEqual(set(self.prior),set(vars(state)))
    def test_pending_corrupt_oversized_wrong_world_and_replayed_session_are_preserved(self):
        for mode in ("pending","corrupt","oversized","world","session","missing-counts","missing-version"):
            with self.subTest(mode=mode):
                self.setUp()
                data=dict(self.prior)
                session="session-b"
                if mode=="world":data["WorldName"]="other"
                if mode=="session":session="session-a"
                if mode=="missing-counts":del data["Samples"]
                if mode=="missing-version":del data["Version"]
                text=json.dumps(data)
                if mode=="corrupt":text="torn"
                if mode=="oversized":text=" "*2049
                self.files["owned/state.json"]=text
                if mode=="pending":self.files["owned/pending.json"]="interrupted"
                before=dict(self.files)
                self.assertIsNone(self.open(self.store,"synthetic-world",session))
                self.assertEqual(before,self.files)
                self.assertEqual([],self.saved)
    def test_empty_store_initializes_all_required_fields(self):
        state=self.open(self.store,"synthetic-world","session-a")
        self.assertTrue(self.e["HCEcologyRuntimeRules"].CheckpointValid(state,"synthetic-world"))
        self.assertEqual((1,0,0),(state.Revision,state.Samples,state.PathQueries))


class EcologyCohortBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.e=environment();self.calls=[]
        self.cfg=self.e["HCEcologyRuntimeSettings"]();self.cfg.MaxPathQueries=2
        self.runtime=SimpleNamespace(m_Actors=EArray(),m_Resources=EArray(),m_Intents=EArray(),
              m_ActorCursor=0,m_ResourceCursor=0,m_Session="session-a",m_Settings=self.cfg,
              m_Policy=SimpleNamespace(WorldName="synthetic-world"))
        class Handle:
            def __init__(self,point,kind):self.point=point;self.kind=kind;self.alive=True
            def GetPosition(self):return self.point
            def IsAlive(self):return self.alive
        for serial in range(1,4):
            self.runtime.m_Actors.Insert(SimpleNamespace(Entity=Handle([0.,0.,0.],0),Serial=serial))
        for serial in range(4,7):
            self.runtime.m_Resources.Insert(SimpleNamespace(Entity=Handle([1.,0.,0.],1),Serial=serial))
        def probe(actor,resource,aid,rid,kind,cfg,world,session,now):
            self.calls.append((aid,rid))
            result=self.e["HCEcologyRouteIntent"]()
            result.ActorId=aid;result.ResourceId=rid;result.ExpiresAtMs=now+cfg.IntentMs
            return result
        self.e["HCEcologyNative"]=SimpleNamespace(SampleResource=lambda r:r.kind,ProbePath=probe)
        text=(ROOT/"4_World/Ecology/HCEcologyRuntime.c").read_text()
        self.probe=translated(text,"ProbeCohort",self.e,"HCEcologyRuntime",True)
    def test_queries_bounded_and_zones_reserved_across_ticks(self):
        self.assertEqual(2,self.probe(self.runtime,100))
        self.assertEqual(2,len(self.calls))
        self.assertEqual(2,len({rid for aid,rid in self.calls}))
        self.assertEqual(2,len({aid for aid,rid in self.calls}))
        self.assertEqual(1,self.probe(self.runtime,101))
        self.assertEqual(3,len(self.runtime.m_Intents))
        self.assertEqual(0,self.probe(self.runtime,102))
    def test_invalid_empty_distant_or_dead_entries_cannot_issue_path(self):
        self.runtime.m_Actors[0].Entity.alive=False
        self.runtime.m_Actors[1].Entity.point=[float("nan"),0.,0.]
        self.runtime.m_Actors[2].Entity.point=[1000.,0.,0.]
        self.assertEqual(0,self.probe(self.runtime,100))
        self.assertEqual([],self.calls)
    def test_failed_queries_still_spend_the_per_tick_budget(self):
        def fail(*args):self.calls.append(args);return None
        self.e["HCEcologyNative"].ProbePath=fail
        self.assertEqual(2,self.probe(self.runtime,100))
        self.assertEqual(2,len(self.calls))
        self.assertEqual([],self.runtime.m_Intents)


class EcologyLifecycleBehaviorTests(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace
        from tests.unit.test_ecology_rules import translated_rules
        self.e=environment();self.e.update({k:v for k,v in translated_rules().items()
            if k in ("HCEcologyObservationBatch","HCEcologyDirective","HCEcologyReceipt","HCEcologyCode","HCEcologyZoneObservation","HCEcologyResource","HCEcologyPopulation")})
        self.stops=[];self.queries=[];self.writes=[]
        self.runtime=SimpleNamespace(m_Running=True,m_Collecting=True,m_LastTick=100,m_LastNow=100,m_LastSave=100,m_Intents=EArray(),
            m_Actors=EArray(),m_Resources=EArray(),m_Session="session-a",m_Settings=self.e["HCEcologyRuntimeSettings"](),
            m_Policy=SimpleNamespace(WorldName="synthetic-world"),m_State=SimpleNamespace(),
            m_Checkpoint=self.e["HCEcologyCheckpoint"](),m_Dirty=False)
        self.runtime.m_Checkpoint.Version=1
        self.runtime.m_Checkpoint.Samples=self.runtime.m_Checkpoint.PathQueries=0
        self.authority=True;self.world="synthetic-world"
        self.runtime.Finish=lambda:self.stops.append("stop")
        self.runtime.RemoveFrom=lambda *args:None
        self.runtime.ProbeCohort=lambda now:self.queries.append(now) or 0
        self.runtime.Checkpoint=lambda:self.writes.append("save") or True
        self.e["HCEcologyNative"]=SimpleNamespace(Authority=lambda:self.authority,Capabilities=lambda:SimpleNamespace(ProviderAvailable=False))
        self.e["GetGame"]=lambda:SimpleNamespace(GetWorldName=lambda:self.world)
        self.commits=[];self.schedules=[]
        def schedule(*args):
            self.schedules.append(args);return 0
        self.e["HCEcologyRules"]=SimpleNamespace(Schedule=schedule,Commit=lambda *args:self.commits.append(args) or 0)
        source=(ROOT/"4_World/Ecology/HCEcologyRuntime.c").read_text()
        self.pump=translated(source,"Pump",self.e,"HCEcologyRuntime",True)
        self.finish=translated(source,"Finish",self.e,"HCEcologyRuntime",True)
    def test_stopped_service_never_probes_or_saves(self):
        self.runtime.m_Running=False
        self.pump(self.runtime,10000)
        self.assertEqual([],self.queries+self.writes+self.schedules)
    def test_clock_world_or_authority_failure_stops_before_native_work(self):
        for world,authority,now in (("other",True,10000),("synthetic-world",False,10000),
                                     ("synthetic-world",True,99),("synthetic-world",True,2147483647)):
            self.world=world;self.authority=authority
            self.pump(self.runtime,now)
        self.assertEqual(["stop"]*4,self.stops)
        self.assertEqual([],self.queries)
    def test_empty_live_tick_consumes_policy_but_never_commits_unsupported_provider(self):
        self.pump(self.runtime,5100)
        self.assertEqual([5100],self.queries)
        self.assertEqual(1,len(self.schedules));self.assertEqual([],self.commits)
        self.assertTrue(self.runtime.m_Dirty)
        self.assertEqual([],self.writes)
    def test_periodic_failed_checkpoint_stops_future_work(self):
        self.runtime.Checkpoint=lambda:False
        self.pump(self.runtime,60100)
        self.assertFalse(self.runtime.m_Running)
        self.pump(self.runtime,65100)
        self.assertEqual([60100],self.queries)
    def test_subinterval_clock_rollback_stops_before_work(self):
        self.pump(self.runtime,1100)
        self.pump(self.runtime,1000)
        self.assertEqual(["stop"],self.stops)
        self.assertEqual([],self.queries+self.writes+self.schedules)
    def test_shutdown_closes_registration_and_flushes_once(self):
        self.runtime.m_Dirty=True
        self.runtime.m_Actors.Insert(object());self.runtime.m_Resources.Insert(object())
        self.runtime.m_Intents.Insert(object())
        self.finish(self.runtime);self.finish(self.runtime)
        self.assertFalse(self.runtime.m_Collecting)
        self.assertFalse(self.runtime.m_Running)
        self.assertFalse(self.runtime.m_Dirty)
        self.assertEqual(["save"],self.writes)
        self.assertEqual(0,len(self.runtime.m_Actors)+len(self.runtime.m_Resources)+len(self.runtime.m_Intents))
    def test_periodic_store_fault_releases_all_live_bindings(self):
        self.runtime.m_Intents.Insert(None)
        self.runtime.m_Actors.Insert(SimpleNamespace(Entity=object(),Serial=1))
        self.runtime.m_Resources.Insert(SimpleNamespace(Entity=object(),Serial=2))
        self.e["HCEcologyNative"].SampleActor=lambda *args:None
        self.e["HCEcologyNative"].SampleResource=lambda *args:0
        self.runtime.Checkpoint=lambda:False
        self.runtime.Finish=lambda:self.finish(self.runtime)
        self.pump(self.runtime,60100)
        self.assertFalse(self.runtime.m_Collecting)
        self.assertFalse(self.runtime.m_Dirty)
        self.assertEqual([],self.runtime.m_Intents)
        self.assertEqual([],self.runtime.m_Actors)
        self.assertEqual([],self.runtime.m_Resources)
    def test_startup_clock_admission_precedes_store_and_settings_io(self):
        source=(ROOT/"4_World/Ecology/HCEcologyRuntime.c").read_text()
        begin=body(source,re.search(r"bool Begin\([^)]*\)\s*\{",source).end())
        self.assertIn("HCEcologyRuntimeRules.ClockValid(nowMs)",begin)
        guard=begin.index("HCEcologyRuntimeRules.ClockValid(nowMs)")
        self.assertLess(guard,begin.index("HCEcologyRuntimeIO.Settings()"))
        self.assertLess(guard,begin.index("m_Store.Open("))
    def test_invalid_start_closes_prestart_cohort_without_stopping_live_duplicate(self):
        source=(ROOT/"4_World/Ecology/HCEcologyRuntime.c").read_text()
        for running in (False,True):
            runtime=SimpleNamespace(m_Running=running,Begin=lambda *args:False,Finish=lambda:self.stops.append("stop"))
            self.e["HCEcologyRuntime"]=SimpleNamespace(Instance=lambda:runtime)
            start=translated(source,"Start",self.e,"HCEcologyRuntime")
            self.assertFalse(start(None,"synthetic-world","session-b"))
            self.assertEqual([] if running else ["stop"],self.stops)
            self.stops.clear()


class EcologyRegistryBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.e=environment()
        self.e["HCEcologyNative"]=SimpleNamespace(Authority=lambda:True)
        self.e["HCEcologyLiveBinding"]=lambda:SimpleNamespace(Entity=None,Serial=0)
        self.runtime=SimpleNamespace(m_Collecting=True,m_Actors=EArray(),m_Resources=EArray(),m_Intents=EArray(),
            m_Settings=self.e["HCEcologyRuntimeSettings"](),m_Overflow=False,m_NextSerial=1,m_Session="session-a")
        source=(ROOT/"4_World/Ecology/HCEcologyRuntime.c").read_text()
        self.add=translated(source,"Add",self.e,"HCEcologyRuntime",True)
        self.remove=translated(source,"RemoveFrom",self.e,"HCEcologyRuntime",True)
        self.runtime.ForgetIntents=lambda id:None
        self.actor=SimpleNamespace(IsPendingDeletion=lambda:False)
    def test_closed_cohort_drops_late_hooks_and_null_registration(self):
        self.runtime.m_Collecting=False
        self.add(self.runtime,self.actor,True)
        self.assertEqual([],self.runtime.m_Actors)
        self.runtime.m_Collecting=True
        self.add(self.runtime,None,True)
        self.assertEqual([],self.runtime.m_Actors)
    def test_duplicates_budgets_and_retirement_never_reuse_identity(self):
        self.runtime.m_Settings.MaxActors=1
        self.add(self.runtime,self.actor,True)
        self.add(self.runtime,self.actor,True)
        self.add(self.runtime,SimpleNamespace(IsPendingDeletion=lambda:False),True)
        self.assertEqual([1],[b.Serial for b in self.runtime.m_Actors])
        self.assertTrue(self.runtime.m_Overflow)
        self.remove(self.runtime,self.runtime.m_Actors,self.actor)
        self.add(self.runtime,self.actor,True)
        self.assertEqual([2],[b.Serial for b in self.runtime.m_Actors])
