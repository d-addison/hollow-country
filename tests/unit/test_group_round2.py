"""Round 2: explicit synthetic native fixtures, never DayZ acceptance."""
import copy
from functools import lru_cache
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from tests.unit.test_group_server import EArray, translated_rules, execute_member
from tests.unit import test_v1_groups
V1GroupsBehavior = test_v1_groups.V1GroupsBehavior

ROOT=Path(__file__).resolve().parents[2]
S=ROOT/'mods/HollowCountry/scripts'

def src(name):
    return next(S.glob('*/Groups/'+name+'.c')).read_text()

@lru_cache(maxsize=64)
def adapted(text, method):
    text=re.sub(r'\bs_Instance\b', 'self.s_Instance',text)
    text=text.replace('= this;', '= self;')
    text=text.replace('array<Man> players = new array<Man>()', 'HCGroupItems players = EArray()')
    text=text.replace('Man man', 'HCGroupNative man')
    text=text.replace('Math.RandomIntInclusive(1, 1000000000).ToString()', 'str(123)')
    text=text.replace('m_LastUtc.ToString()', 'str(m_LastUtc)')
    # Syntax-only adaptations of native types, out parameters and for loops.
    text=re.sub(r'\b(?:HCGroupEquipment|HCGroupLOSResult|HCGroupPlaceCatalog) (\w+)\(',r'HCGroupMember \1(',text)
    text=re.sub(r'\b(?:PlayerBase|Object) (?=\w+\s*[=;])','HCGroupNative ',text)
    text=text.replace('Clone(candidate)','((candidate := self.Clone()) != null)').replace('Clone(expired)','((expired := self.Clone()) != null)')
    text=re.sub(r'for \(int (\w+) = ([^;]+); \1 >= 0; \1--\)',r'foreach (int \1 : reverse_indices(\2))',text)
    text=re.sub(r'for \(int (\w+) = ([^;]+); \1 < ([^;]+); \1\+\+\)',r'foreach (int \1 : indices(\2, \3))',text)
    for m in re.findall(r'^    (?:bool|int|void|HCGroup\w+) (\w+)\(',text,re.M):
        text=re.sub(r'(?<![\w.])'+m+r'\(', 'self.'+m+'(',text) if m != method else text
    return text

def run(name, method, state, env, *args):
    text=adapted(src(name),method)
    env=dict(env, EArray=EArray, str=str, reverse_indices=lambda n:range(n,-1,-1),indices=range)
    return execute_member(text,method,env,state,*args)

class RulesRound2(unittest.TestCase):
    setUp=V1GroupsBehavior.setUp
    create=V1GroupsBehavior.create
    joined=V1GroupsBehavior.joined
    apply=V1GroupsBehavior.apply
    request=V1GroupsBehavior.request
    def place(self,uid='p'):
        p=self.e['HCGroupPlace']();p.Id=uid;p.Name='Synthetic';p.Position=[100,0,100];return p
    def record(self,uid='alice',place=None):
        return self.e['RecordVisit'](self.state,self.cfg,uid,place or self.place(),[100,0,100])
    def known(self,uid):
        # Old signatures are supported only for the initial failing-first run.
        f=self.e['KnownPlaces']
        args=[self.state,self.cfg,uid]
        if f.__code__.co_argcount==4:args.append(N(Places=EArray([self.place(),self.place('q')])))
        return f(*args)
    def test_M03_officer_cannot_transfer(self):
        self.joined();self.apply('alice',13,TargetId='bob',Role=1)
        self.assertEqual(self.code.DENIED,self.apply('bob',self.op.TRANSFER,TargetId='alice'))
    def test_M04_officer_cannot_disband(self):
        self.joined();self.apply('alice',13,TargetId='bob',Role=1)
        self.assertEqual(self.code.DENIED,self.apply('bob',self.op.DISBAND))
    def cleanup(self,op,actor):
        g=self.joined();self.apply('alice',13,TargetId='bob',Role=1)
        self.assertEqual(0,self.apply(actor,op,TargetId='bob'))
        self.assertEqual([],g.Officers)
        self.apply('alice',self.op.INVITE,TargetId='bob');self.apply('bob',self.op.ACCEPT,EntityId=self.state.Invitations[0].Id)
        self.assertEqual(0,self.e['Role'](g,'bob'));self.assertTrue(self.e['StateValid'](self.state,self.cfg,self.state.WorldName))
    def test_M05_kicked_officer_rejoins_as_member(self):self.cleanup(self.op.KICK,'alice')
    def test_M06_departed_officer_rejoins_as_member(self):self.cleanup(self.op.LEAVE,'bob')
    def test_M13_nonmember_officer_journal_rejected(self):
        g=self.joined();g.Officers.Insert('outsider');self.assertFalse(self.e['StateValid'](self.state,self.cfg,self.state.WorldName))
    def test_M14_owner_officer_journal_rejected(self):
        g=self.joined();g.Officers.Insert('alice');self.assertFalse(self.e['StateValid'](self.state,self.cfg,self.state.WorldName))
    def test_M15_member_inviter_journal_rejected(self):
        self.joined();self.apply('alice',self.op.INVITE,TargetId='charlie');self.state.Invitations[0].InviterId='bob'
        self.assertFalse(self.e['StateValid'](self.state,self.cfg,self.state.WorldName))
    def test_M18_explorer_admission_limit(self):
        self.cfg.MaxExplorers=1;self.assertTrue(self.record());self.assertFalse(self.record('bob'))
    def test_M19_disabled_discovery_records_nothing(self):
        self.cfg.DiscoveryLayer=False;self.assertFalse(self.record());self.assertEqual([],self.state.Explorers)
    def test_M21_discovery_never_shares_other_group(self):
        self.joined();self.create('outsider');self.record('outsider');self.cfg.ShareDiscovery=True
        self.assertEqual([],self.known('bob'))
    def test_M23_union_of_member_discoveries_is_bounded(self):
        self.joined();self.cfg.MaxDiscoveries=1;self.cfg.ShareDiscovery=True
        self.record();self.record('bob',self.place('q'));self.assertEqual(1,len(self.known('alice')))
    def test_M24_disabled_discovery_lists_nothing(self):
        self.record();self.cfg.DiscoveryLayer=False;self.assertEqual([],self.known('alice'))
    def test_M56_radius_validation(self):
        for radius in (4,501,float('nan')):
            p=self.place();p.Radius=radius;self.assertFalse(self.e['PlaceValid'](p))
    def test_M57_overfull_explorer_journal_rejected(self):
        self.record();self.record('bob');self.cfg.MaxExplorers=1;self.assertFalse(self.e['ExplorersValid'](self.state,self.cfg))
    def test_M58_duplicate_journal_visit_rejected(self):
        self.record();e=self.state.Explorers[0]
        visits=getattr(e,'PlaceIds',e.Visits);visits.Insert(visits[0]);self.assertFalse(self.e['ExplorersValid'](self.state,self.cfg))
    def test_journal_stores_ids_and_resolves_current_catalog(self):
        self.record();e=self.state.Explorers[0]
        self.assertEqual(['p'],getattr(e,'PlaceIds',[]));self.assertEqual([],e.Visits)
        catalog=N(Places=EArray([self.place()]));catalog.Places[0].Name='Renamed'
        self.assertEqual('Renamed',self.e['KnownPlaces'](self.state,self.cfg,'alice',catalog)[0].Name)
    def test_default_ray_budget_covers_eight(self):self.assertGreaterEqual(self.cfg.MaxLOSRaysPerTick,8*7)
    def test_wire_three(self):
        self.assertEqual(3,self.e['HCGroupProtocol'].VERSION)
        for name in ('HCGroupRequest','HCGroupSnapshot','HCGroupReply'):self.assertEqual(3,self.e[name]().Version)

    def test_M12_owner_role_request_is_invalid(self):
        self.joined()
        self.assertEqual(self.code.INVALID,self.apply('alice',13,TargetId='bob',Role=2))
    def test_M58_duplicate_legacy_visit_rejected(self):
        explorer=self.e['HCGroupExplorer']();explorer.Id='legacy';explorer.Visits=EArray([self.place(),self.place()])
        self.state.Explorers.Insert(explorer);self.assertFalse(self.e['ExplorersValid'](self.state,self.cfg))

class ServiceRound2(unittest.TestCase):
    def setUp(self):
        self.e=translated_rules();self.cfg=self.e['HCGroupSettings']();self.now=100.
        self.calls=[];self.writes=[];self.clones=[];self.broadcasts=[]
        self.place=self.e['HCGroupPlace']();self.place.Id='p';self.place.Name='Synthetic';self.place.Position=[100,0,100]
        self.peers=EArray(self.peer(str(i)) for i in range(8))
        self.s=N(m_Config=self.cfg,m_State=self.e['HCGroupState'](),m_Places=N(Places=EArray([self.place])),m_Peers=self.peers,
            m_Healthy=True,m_LastUtc=1000,m_LOSRays=0,m_DiscoveryTime=0.,m_DiscoveryCursor=0,m_PositionTime=0.,
            m_PeerCursor=0,m_RoundCursor=0,m_FullSent=False,m_DiscoveryBlockedUntil=0.,m_LOSCache=EArray(),m_EquipmentTime=-1.,
            Live=lambda p:p is not None,Stop=lambda:self.fail('unexpected Stop'),
            Commit=lambda c:self.writes.append(c) or 0,Broadcast=lambda:self.broadcasts.append(1),
            SendSnapshot=lambda p,k,r:self.calls.append((p.Id,k)),Peer=lambda uid:next((p for p in self.peers if p.Id==uid),None))
        self.s.Clone=lambda:self.clones.append(1) or copy.deepcopy(self.s.m_State)
        self.e.update(GetGame=lambda:N(GetTickTime=lambda:self.now),HCGroupClock=N(Utc=lambda:1000),Print=lambda s:None,HCGroupLOSResult=lambda:N())
        for m in ('Equipment','LOSAllows','BeginVisibilityTick','SendRound','Discover','EvictExplorers'):
            setattr(self.s,m,lambda *args,m=m:run('HCGroupService',m,self.s,self.e,*args))
    def peer(self,uid):
        return N(Id=uid,Session='s',Gear=None,Equipment=None,Player=N(IsAlive=lambda:True,IsUnconscious=lambda:False,GetPosition=lambda:[100,0,100]))
    def discover(self):run('HCGroupService','Discover',self.s,self.e)
    def test_far_discovery_does_no_clone_or_record(self):
        for p in self.peers:p.Player.GetPosition=lambda:[10000,0,10000]
        self.e['RecordVisit']=lambda *a:self.fail('distance rejection must precede RecordVisit')
        self.discover();self.assertEqual([],self.clones)
    def test_already_known_discovery_does_not_clone(self):
        for p in self.peers:self.e['RecordVisit'](self.s.m_State,self.cfg,p.Id,self.place,[100,0,100])
        self.discover();self.assertEqual([],self.clones)
    def test_limit_discovery_backs_off_sixty_seconds(self):
        self.s.Commit=lambda c:self.writes.append(c) or self.e['HCGroupCode'].LIMIT
        self.discover();self.discover();self.assertEqual(1,len(self.writes))
        self.now+=60;self.discover();self.assertEqual(2,len(self.writes))
    def test_M43_discovery_skips_dead_and_unconscious(self):
        for p in self.peers:p.Player.IsAlive=lambda:False
        self.peers[0].Player.IsAlive=lambda:True;self.peers[0].Player.IsUnconscious=lambda:True
        self.discover();self.assertEqual([],self.writes)
    def test_M44_discovery_examined_bound(self):
        self.peers.extend(self.peer(str(i)) for i in range(8,20));self.discover()
        self.assertEqual(6,len(self.writes[0].Explorers))
    def visibility(self,left=None,right=None):
        return run('HCGroupService','VisibilityAllows',self.s,self.e,left or self.peers[0],right or self.peers[1])
    def native(self):
        self.rays=[];self.reads=[];self.verdict=True
        self.e.update(HCGroupEquipment=lambda:N(),HCGroupVisibility=N(RadioMatches=lambda *a:True,HasLOS=lambda a,b:self.rays.append((a,b)) or self.verdict))
        self.e['HCGroupEquipment']=N(Read=lambda p:self.reads.append(p) or N())
        self.s.Equipment=lambda p:self.e['HCGroupEquipment'].Read(p.Player)
    def test_M30_unconscious_source_never_visible(self):
        self.native();self.peers[0].Player.IsUnconscious=lambda:True;self.assertFalse(self.visibility())
    def test_pair_los_cache_expires_and_is_bounded(self):
        self.native();self.cfg.RequireLOS=True
        self.assertTrue(self.visibility());self.assertTrue(self.visibility());self.assertEqual(1,len(self.rays))
        self.now+=1.01;self.s.m_LOSRays=0;self.verdict=False;self.assertFalse(self.visibility());self.assertEqual(2,len(self.rays))
        self.assertLessEqual(len(self.s.m_LOSCache),256)
    def test_M31_tick_resets_budget_and_rotates_start(self):
        self.cfg.DiscoveryLayer=False;self.s.m_LOSRays=56
        for i in range(8):
            self.s.m_State.Groups=EArray([N(Members=EArray(p.Id for p in self.peers),Markers=EArray())])
            run('HCGroupService','Tick',self.s,self.e,2.)
            self.assertEqual(0,self.s.m_LOSRays)
        self.assertEqual(set(p.Id for p in self.peers),set(self.calls[i*8][0] for i in range(8)))
    def test_full_round_prevents_duplicate_positions(self):
        self.cfg.DiscoveryIntervalSeconds=5;self.s.m_DiscoveryTime=5
        def broadcast():self.s.m_FullSent=True
        self.s.Broadcast=broadcast
        run('HCGroupService','Tick',self.s,self.e,2.)
        self.assertEqual([],self.calls)
    def test_equipment_once_per_peer_each_tick(self):
        self.native();self.s.Equipment=lambda p:run('HCGroupService','Equipment',self.s,self.e,p)
        for p in self.peers:self.s.Equipment(p);self.s.Equipment(p)
        self.assertEqual(8,len(self.reads))
        run('HCGroupService','BeginVisibilityTick',self.s,self.e)
        for p in self.peers:self.s.Equipment(p)
        self.assertEqual(16,len(self.reads))
    def test_eviction_preserves_grouped_and_online_explorers(self):
        for uid in ('old','grouped','0'):self.e['RecordVisit'](self.s.m_State,self.cfg,uid,self.place,[100,0,100])
        self.s.m_State.Groups=EArray([N(Members=EArray(['grouped']))])
        self.s.m_LastUtc=4000000
        run('HCGroupService','EvictExplorers',self.s,self.e,self.s.m_State,False)
        self.assertEqual(['grouped','0'],[e.Id for e in self.s.m_State.Explorers])
    def test_M41_dead_peer_receives_no_places(self):self.snapshot(False,0,False)
    def test_M42_positions_never_include_places(self):self.snapshot(True,1,False)
    def test_M61_snapshot_roster_roles(self):self.snapshot(True,0,True)
    def snapshot(self,alive,kind,places):
        rules=RulesRound2();rules.setUp();rules.joined();rules.apply('alice',13,TargetId='bob',Role=1);rules.record()
        self.s.m_State=rules.state;p=self.peers[0];p.Id='alice';p.Player.IsAlive=lambda:alive
        p.Sequence=0;p.LastRequest=0;p.LastGroup=0;p.Identity=object()
        sent=[]
        class RPC:
            def Write(self,v):sent.append(v)
            def Send(self,*a):pass
        self.s.Member=lambda uid,*a:N(Id=uid,Role=0)
        self.e['ScriptRPC']=RPC
        run('HCGroupService','SendSnapshot',self.s,self.e,p,kind,0)
        self.assertEqual([2,1],[m.Role for m in sent[0].Members])
        self.assertEqual(places,bool(len(sent[0].Places)))
    def test_M62_start_refuses_bad_catalog(self):
        self.s.s_Instance=None
        self.e.update(GetGame=lambda:N(IsServer=lambda:True,GetWorld=lambda:N(GetWorldSize=lambda:10000),GetPlayers=lambda a:None),s_Instance=None,HCGroupPlaces=N(Load=lambda:None),HCGroupStore=lambda:N(Open=lambda *args:True))
        self.assertFalse(run('HCGroupService','Start',self.s,self.e,self.cfg))

class NativeRound2(unittest.TestCase):
    def equipment(self,count,items):
        text=src('HCGroupVisibility').replace('HCGroupEquipment Read(', 'HCGroupMember Read(')
        text=text.replace('array<EntityAI> items = new array<EntityAI>()','HCGroupItems items = Items()')
        for typ in ('ItemBase','PersonalRadio','ItemGPS'):text=re.sub(r'\b'+typ+r' (?=\w+ =)','HCGroupNative ',text)
        player=N(IsAlive=lambda:True,GetInventory=lambda:N(CountInventory=lambda:count,EnumerateInventory=lambda mode,out:out.extend(items)))
        env=dict(HCGroupEquipment=lambda:N(HasMap=False,HasGPS=False,Frequencies=EArray()),Items=EArray,InventoryTraversalType=N(PREORDER=1),
            ItemBase=N(Cast=lambda x:x),ItemMap=N(Cast=lambda x:True),ItemGPS=N(Cast=lambda x:None),PersonalRadio=N(Cast=lambda x:x),
            CfgGameplayHandler=N(GetMapIgnoreMapOwnership=lambda:False,GetMapIgnoreNavItemsOwnership=lambda:False))
        for item in items:item.GetHierarchyRootPlayer=lambda:player
        return execute_member(text,'Read',env,N(),player)
    def item(self,transmitter=True):
        return N(IsRuined=lambda:False,IsTransmitter=lambda:transmitter,GetCompEM=lambda:N(IsWorking=lambda:True),GetTunedFrequency=lambda:87.8)
    def test_M39_enumerated_inventory_over_budget_fails_closed(self):
        # CountInventory deliberately underreports, EnumerateInventory is authoritative.
        g=self.equipment(1,[self.item() for _ in range(513)])
        self.assertFalse(g.HasMap);self.assertEqual([],g.Frequencies)
    def test_M40_nontransmitter_handheld_fails_closed(self):self.assertEqual([],self.equipment(1,[self.item(False)]).Frequencies)
    def test_M45_expired_announced_mission_is_not_listed(self):
        from tests.unit.test_group_ui import ui_member,SyntheticList
        text=src('HCGroupMapLayers').replace('HCEventClient events =','HCGroupClient events =').replace('HCEventPublicView known =','HCGroupView known =').replace('row.RemainingSeconds.ToString()','str(row.RemainingSeconds)')
        widget=SyntheticList();rows=EArray([N(Title='Expired',RemainingSeconds=0,Status=1,Joined=False)])
        env=dict(HCEventClient=N(Get=lambda:N(Fresh=lambda:True,GetView=lambda:N(Enabled=True,Rows=rows))),HCEventStatus=N(ANNOUNCED=1,ACTIVE=2),str=str)
        ui_member(text,'Missions',N(mHCEvents=widget),env,N(MissionLayer=True));self.assertEqual(['No active known missions'],widget.items)
    def navigation(self,enabled=True,gps=False):
        text=src('HCGroupMapLayers')
        text=text.replace('for (int cell = 0; cell <= 50; cell++)','foreach (int cell : cells)')
        text=text.replace('Math.Round(actual[0])','int(actual[0])').replace('Math.Round(actual[2])','int(actual[2])')
        text=text.replace('eastMeters.ToString()','str(eastMeters)').replace('northMeters.ToString()','str(northMeters)')
        lines=[];viewer=N(GetPosition=lambda:[123,0,456]);equipment=N(HasMap=True,HasGPS=gps)
        state=N(mHCGrid=None,mHCNavigation=N(SetText=lines.append,SetTextExactSize=lambda x:None),mHCEquipment=equipment,mHCEquipmentTime=100.,mHCViewer=viewer)
        env=dict(HCGroupEquipment=N(Read=lambda p:equipment),GetGame=lambda:N(GetTickTime=lambda:100.,GetWorld=lambda:N(GetWorldSize=lambda:10000)),
            Math=N(Round=round),int=int,str=str,cells=range(51))
        from tests.unit.test_group_ui import ui_member
        ui_member(text,'Navigation',state,env,None,viewer,N(NavigationLayer=enabled,LabelScale=1))
        return lines
    def test_M49_own_coordinates_require_powered_gps(self):self.assertFalse(any('Own coordinates' in s for s in self.navigation()))
    def test_M50_disabled_navigation_does_not_render(self):self.assertEqual([''],self.navigation(False,True))
    def test_unpowered_gps_instructions(self):self.assertIn('powered GPS',self.navigation()[-1])
    def test_M51_client_rejects_overfull_places(self):
        from tests.unit.test_group_client import ClientTests
        f=ClientTests();f.setUp();frame=f.frame();frame.Settings.MaxDiscoveries=1
        frame.Places=EArray([N(Id='p',Name='P',Position=[1,0,1],Radius=10)]*2)
        self.assertFalse(f.run_method('SnapshotValid',frame))
    def test_M52_client_rejects_invalid_role(self):
        from tests.unit.test_group_client import ClientTests
        f=ClientTests();f.setUp();member=f.e['HCGroupMember']();member.Id='a';member.Name='A'
        for role in (-1,3):member.Role=role;self.assertFalse(f.run_method('MemberValid',member))
    def test_shared_parent_vehicle_is_ignored_in_ray(self):
        text=src('HCGroupVisibility').replace('vector contact;','HCGroupVector contact;').replace('vector normal;','HCGroupVector normal;')
        text=text.replace('set<Object> hits = new set<Object>()','HCGroupHits hits = Hits()').replace('Object parent =','HCGroupNative parent =').replace('Object ignored =','HCGroupNative ignored =')
        car=object();left=N(GetParent=lambda:car,GetBoneIndexByName=lambda n:1,GetBonePositionWS=lambda b:[1,1,1]);right=N(**vars(left))
        calls=[]
        env=dict(Object=N(Cast=lambda p:p),PositionValid=lambda p:True,Hits=EArray,DayZPhysics=N(RaycastRV=lambda *args:calls.append(args) or False),ObjIntersectView=7,CollisionFlags=N(NEARESTCONTACT=1))
        self.assertTrue(execute_member(text,'HasLOS',env,N(),left,right));self.assertIs(car,calls[0][6]);self.assertIs(left,calls[0][7])

del V1GroupsBehavior

class AdditionalRound2(unittest.TestCase):
    setUp=ServiceRound2.setUp
    native=ServiceRound2.native
    peer=ServiceRound2.peer
    discover=ServiceRound2.discover
    visibility=ServiceRound2.visibility
    # BDD: 8-member group, intentionally undersized operator quota. Every
    # recipient eventually receives all seven directed ray opportunities.
    def test_eight_members_eventually_get_rays_with_budget_seven(self):
        self.native();self.cfg.RequireLOS=True;self.cfg.MaxLOSRaysPerTick=7;self.cfg.DiscoveryLayer=False
        self.s.m_State.Groups=EArray([N(Members=EArray(p.Id for p in self.peers),Markers=EArray())])
        recipients=set()
        def snapshot(peer,kind,request):
            passed=0
            for source in self.peers:
                if source!=peer and self.visibility(source,peer):passed+=1
            if passed==7:recipients.add(peer.Id)
        self.s.SendSnapshot=snapshot
        for i in range(8):
            self.now+=2;run('HCGroupService','Tick',self.s,self.e,2.)
            self.assertEqual(7,self.s.m_LOSRays)
        self.assertEqual(set(p.Id for p in self.peers),recipients)
    def test_discovery_evicts_inactive_when_explorer_slots_full(self):
        self.cfg.MaxExplorers=1;self.e['RecordVisit'](self.s.m_State,self.cfg,'gone',self.place,[100,0,100])
        self.s.m_LastUtc=4000000;self.peers[:]=self.peers[:1]
        self.discover();self.assertEqual(1,len(self.writes));self.assertEqual(['0'],[e.Id for e in self.writes[0].Explorers])
    def test_rotation_does_not_alias_two_second_position_cadence(self):
        self.native();self.cfg.RequireLOS=True;self.cfg.MaxLOSRaysPerTick=7;self.cfg.DiscoveryLayer=False
        self.s.m_State.Groups=EArray([N(Members=EArray(p.Id for p in self.peers),Markers=EArray())])
        recipients=set()
        def snapshot(peer,kind,request):
            passed=sum(1 for source in self.peers if source!=peer and self.visibility(source,peer))
            if passed==7:recipients.add(peer.Id)
        self.s.SendSnapshot=snapshot
        for i in range(16):
            self.now+=1;run('HCGroupService','Tick',self.s,self.e,1.)
        self.assertEqual(set(p.Id for p in self.peers),recipients)
    def test_los_cache_is_bounded_under_many_sessions(self):
        self.native();self.cfg.RequireLOS=True
        for i in range(300):
            self.peers[1].Session=str(i);self.s.m_LOSRays=0;self.visibility()
        self.assertEqual(256,len(self.s.m_LOSCache));self.assertEqual(300,len(self.rays))
    def test_negative_cache_expires_and_reconnect_invalidates_verdict(self):
        self.native();self.cfg.RequireLOS=True;self.verdict=False
        self.assertFalse(self.visibility());self.verdict=True;self.assertFalse(self.visibility());self.assertEqual(1,len(self.rays))
        self.now+=1.01;self.assertTrue(self.visibility());self.assertEqual(2,len(self.rays))
        self.verdict=False;self.peers[1].Session='reconnect';self.assertFalse(self.visibility());self.assertEqual(3,len(self.rays))
    def test_commit_evicts_offline_journal_before_byte_cap_write(self):
        self.e['RecordVisit'](self.s.m_State,self.cfg,'gone',self.place,[100,0,100]);self.s.m_State.WorldName='synthetic'
        self.s.m_Store=N(Save=lambda c:self.writes.append(c) or True)
        self.cfg.MaxStoreBytes=16384
        self.e.update(GetGame=lambda:N(GetWorldName=lambda:'synthetic'),serialize=lambda c:(True,'x'*(20000 if c.Explorers else 1),''))
        # EArray references are truthy even empty, as native arrays are.
        self.e['serialize']=lambda c:(True,'x'*(20000 if len(c.Explorers) else 1),'')
        self.assertEqual(0,run('HCGroupService','Commit',self.s,self.e,copy.deepcopy(self.s.m_State)))
        self.assertEqual([],self.writes[0].Explorers)

class PresentationRound2(unittest.TestCase):
    def test_pin_reuses_texture_until_texture_changes(self):
        from tests.unit.test_group_ui import ui_member
        text=src('HCGroupMapLayers').replace('float left, top, width, height;','float left = 0; float top = 0; float width = 100; float height = 100;')
        text=text.replace('mHCOverlay.GetScreenPos(left, top);','').replace('mHCOverlay.GetScreenSize(width, height);','')
        loads=[];image=N(LoadImageFile=lambda *args:loads.append(args),SetImage=lambda *a:None,SetColor=lambda *a:None)
        label=N(SetText=lambda *a:None);root=N(FindAnyWidget=lambda n:image if n=='HCMark' else label,SetPos=lambda *a:None,Show=lambda *a:None)
        class Textures(EArray):
            def Set(self,i,x):self[i]=x
        state=N(mHCOverlay=object(),mHCUsed=0,mHCPool=EArray([root]),mHCTextures=Textures(['']))
        env=dict(TextWidget=N(Cast=lambda w:w),ImageWidget=N(Cast=lambda w:w),HCGroupWorldIcons=N(Scale=lambda *a:None))
        for texture in ('first','first','second','second'):
            state.mHCUsed=0;ui_member(text,'Pin',state,dict(env),N(MapToScreen=lambda v:[20,20,0]),[1,0,1],'Synthetic',0,texture,N())
        self.assertEqual([(0,'first'),(0,'second')],loads)
    def test_native_names_truncates_with_log_and_bounded_reads(self):
        text=src('HCGroupPlaces').replace('HCGroupPlaceCatalog NativeNames(', 'HCGroupMember NativeNames(')
        text=text.replace('array<float> coords = new array<float>()','HCGroupCoords coords = EArray()')
        text=text.replace('for (int i = 0; i < count; i++)','foreach (int i : indices(count))')
        text=text.replace('GetGame().ConfigGetChildName(root, i, child)','((child := child_name(root, i)) != null)')
        text=text.replace('GetGame().ConfigGetText(entry + " name", title)','title = "Synthetic"')
        calls=[];logs=[]
        game=N(GetWorldName=lambda:'synthetic',ConfigGetChildrenCount=lambda r:1000000,ConfigGetFloatArray=lambda p,a:a.extend([100,100]))
        env=dict(translated_rules(),GetGame=lambda:game,EArray=EArray,indices=range,Vector=lambda *v:list(v),Print=logs.append,child_name=lambda r,i:calls.append(i) or str(i))
        catalog=execute_member(text,'NativeNames',env,N())
        self.assertEqual(256,len(catalog.Places));self.assertLessEqual(len(calls),512);self.assertTrue(any('truncated' in s for s in logs))
    def test_native_map_ownership_override_requires_no_item(self):
        text=src('HCGroupVisibility').replace('HCGroupEquipment Read(', 'HCGroupMember Read(').replace('array<EntityAI> items = new array<EntityAI>()','HCGroupItems items = EArray()')
        for typ in ('ItemBase','PersonalRadio','ItemGPS'):text=re.sub(r'\b'+typ+r' (?=\w+ =)','HCGroupNative ',text)
        player=N(IsAlive=lambda:True,GetInventory=lambda:N(CountInventory=lambda:0,EnumerateInventory=lambda *a:None))
        env=dict(HCGroupEquipment=lambda:N(HasMap=False,HasGPS=False,Frequencies=EArray()),CfgGameplayHandler=N(GetMapIgnoreMapOwnership=lambda:True,GetMapIgnoreNavItemsOwnership=lambda:False),EArray=EArray,InventoryTraversalType=N(PREORDER=1))
        self.assertTrue(execute_member(text,'Read',env,N(),player).HasMap)
    def test_legacy_explorer_migrates_ids_and_clears_metadata(self):
        e=translated_rules();state=e['HCGroupState']();cfg=e['HCGroupSettings']();explorer=e['HCGroupExplorer']();explorer.Id='legacy'
        place=e['HCGroupPlace']();place.Id='p';place.Name='Old name';place.Position=[1,0,1];explorer.Visits.Insert(place);state.Explorers.Insert(explorer)
        self.assertTrue(e['ExplorersValid'](state,cfg));e['MigrateExplorers'](state)
        self.assertEqual(['p'],explorer.PlaceIds);self.assertEqual([],explorer.Visits);self.assertTrue(e['ExplorersValid'](state,cfg))
