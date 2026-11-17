"""Explicit synthetic DTO/native fixtures; no engine or replication claims."""
import copy
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from tests.unit import test_group_server as group_tests
from tests.unit.test_group_server import EArray, translated_rules, execute_member

ROOT = Path(__file__).resolve().parents[2]

class V1GroupsBehavior(unittest.TestCase):
    setUp = group_tests.GroupServerTests.setUp
    create = group_tests.GroupServerTests.create
    joined = group_tests.GroupServerTests.joined
    apply = group_tests.GroupServerTests.apply
    request = group_tests.GroupServerTests.request

    def test_officer_matrix_and_owner_only_role_assignment(self):
        g = self.joined()
        self.assertEqual(0, self.apply('alice', 13, TargetId='bob', Role=1))
        self.assertEqual(1, self.e['Role'](g, 'bob'))
        self.assertEqual(0, self.apply('bob', self.op.RENAME, Name='Scouts'))
        self.assertEqual(0, self.apply('bob', self.op.INVITE, TargetId='charlie'))
        self.assertTrue(self.e['StateValid'](self.state, self.cfg, self.state.WorldName))
        self.assertEqual(0, self.apply('charlie', self.op.ACCEPT, EntityId=self.state.Invitations[0].Id))
        self.assertEqual(self.code.DENIED, self.apply('bob', 13, TargetId='charlie', Role=1))
        self.assertEqual(self.code.DENIED, self.apply('bob', self.op.KICK, TargetId='alice'))
        self.assertEqual(0, self.apply('alice', self.op.MARKER_CREATE, Name='Rally'))
        self.assertEqual(0, self.apply('bob', self.op.MARKER_UPDATE, EntityId=g.Markers[0].Id, Name='Shared'))
        self.assertEqual(0, self.apply('bob', self.op.KICK, TargetId='charlie'))
        self.assertEqual(0, self.apply('alice', 13, TargetId='bob', Role=0))
        self.assertEqual(self.code.DENIED, self.apply('bob', self.op.RENAME, Name='No'))

    def test_additive_legacy_roles_and_transfer_cleanup(self):
        g = self.joined()
        self.assertEqual((2, 0, -1), tuple(self.e['Role'](g, x) for x in ('alice','bob','outsider')))
        self.assertEqual(0, self.apply('alice', 13, TargetId='bob', Role=1))
        restored = copy.deepcopy(self.state)  # synthetic JSON default/copy semantics
        self.assertTrue(self.e['StateValid'](restored, self.cfg, self.state.WorldName))
        self.assertEqual(1, self.e['Role'](restored.Groups[0], 'bob'))
        self.assertEqual(0, self.apply('alice', self.op.TRANSFER, TargetId='bob'))
        self.assertEqual([], g.Officers)
        self.assertEqual(0, self.e['Role'](g,'alice'))

    def test_visit_requires_actual_proximity_and_is_bounded_persistent_private(self):
        self.joined()
        p = self.e['HCGroupPlace'](); p.Id='synthetic-well'; p.Name='Synthetic well'; p.Position=[100,0,200]; p.Radius=25
        visit = self.e['RecordVisit']
        self.assertFalse(visit(self.state,self.cfg,'alice',p,[126,0,200]))
        self.assertTrue(visit(self.state,self.cfg,'alice',p,[125,0,200]))
        self.assertFalse(visit(self.state,self.cfg,'alice',p,[100,0,200]))
        self.assertEqual(1,len(self.state.Explorers))
        known = lambda state,cfg,uid:self.e['KnownPlaces'](state,cfg,uid,NS(Places=EArray([p])))
        self.assertEqual([],known(self.state,self.cfg,'bob'))
        self.cfg.ShareDiscovery=True
        self.assertEqual(['synthetic-well'],[p.Id for p in known(self.state,self.cfg,'bob')])
        self.assertEqual([],known(self.state,self.cfg,'outsider'))
        self.apply('alice',self.op.KICK,TargetId='bob')
        self.assertEqual([],known(self.state,self.cfg,'bob'))
        self.assertTrue(self.e['StateValid'](copy.deepcopy(self.state),self.cfg,self.state.WorldName))
        self.cfg.MaxDiscoveries=1
        p2=copy.deepcopy(p);p2.Id='second'
        self.assertFalse(visit(self.state,self.cfg,'alice',p2,[100,0,200]))

    def test_visibility_settings_are_supported_and_bounded(self):
        self.cfg.RequireLOS=True; self.cfg.RequireRadio=True
        self.assertTrue(self.e['SettingsValid'](self.cfg))
        for field,value in [('MaxLOSRaysPerTick',0),('MaxLOSRaysPerTick',257),('IconScale',0.1),('LabelScale',3),('MaxDiscoveries',257),('DiscoveryIntervalSeconds',0)]:
            c=copy.deepcopy(self.cfg);setattr(c,field,value)
            self.assertFalse(self.e['SettingsValid'](c),field)

    def test_radio_matching_requires_a_shared_actual_frequency(self):
        source=(ROOT/'mods/HollowCountry/scripts/4_World/Groups/HCGroupVisibility.c').read_text()
        for left,right,expected in [([],[],False),([87.8],[87.9],False),([87.8,89.1],[89.1],True)]:
            result=execute_member(source,'RadioMatches',{},NS(),NS(Frequencies=EArray(left)),NS(Frequencies=EArray(right)))
            self.assertEqual(expected,result)

    def test_required_native_and_privacy_wiring(self):
        base=ROOT/'mods/HollowCountry/scripts'
        service=(base/'4_World/Groups/HCGroupService.c').read_text()
        native=(base/'4_World/Groups/HCGroupVisibility.c').read_text()
        layers=(base/'5_Mission/Groups/HCGroupMapLayers.c').read_text()
        self.assertIn('VisibilityAllows(source, recipient)',service)
        self.assertIn('m_LOSRays >= m_Config.MaxLOSRaysPerTick',service)
        self.assertIn('DayZPhysics.RaycastRV',native)
        self.assertIn('PersonalRadio.Cast',native)
        self.assertIn('GetCompEM().IsWorking()',native)
        self.assertIn('GetTunedFrequency()',native)
        self.assertIn('CountInventory()',native)
        self.assertIn('RecordVisit(candidate',service)
        self.assertIn('KnownPlaces(m_State',service)
        self.assertIn('HCEventClient.Get()',layers)
        self.assertIn('events.Fresh()',layers)
        self.assertNotIn('mission.Source',layers)
        self.assertIn('CanvasWidget',layers)
        self.assertIn('HasMap',layers)

class V1GroupsTransportBehavior(unittest.TestCase):
    def test_client_can_send_role_assignment_without_changing_retry_payload(self):
        from tests.unit.test_group_client import ClientTests
        fixture=ClientTests();fixture.setUp()
        q=fixture.e['HCGroupRequest']();q.Op=13;q.Role=1;q.TargetId='bob'
        self.assertTrue(fixture.run_method('Send',q))
        before=fixture.sent[-1];q.Role=0
        fixture.now+=3;fixture.run_method('Retry',fixture.now)
        self.assertEqual(before,fixture.sent[-1])

    def test_visibility_budget_and_radio_are_fail_closed_before_projection(self):
        source=(ROOT/'mods/HollowCountry/scripts/4_World/Groups/HCGroupService.c').read_text()
        cfg=NS(RequireRadio=True,RequireLOS=True,MaxLOSRaysPerTick=1)
        native_calls=[]
        left=NS(Id='a',Player=NS(IsUnconscious=lambda:False))
        right=NS(Id='b',Player=NS(IsUnconscious=lambda:False))
        matching=[False];visible=[True]
        env={'HCGroupEquipment':NS(Read=lambda p:NS()),
             'HCGroupVisibility':NS(RadioMatches=lambda *a:matching[0],HasLOS=lambda *a:native_calls.append('ray') or visible[0])}
        state=NS(m_Config=cfg,m_LOSRays=0,m_LOSCache=EArray())
        now=[100.]
        env.update(GetGame=lambda:NS(GetTickTime=lambda:now[0]),HCGroupLOSResult=lambda:NS())
        left.Session='a';right.Session='b';left.Gear=None;right.Gear=None
        run=lambda:execute_member(source,'VisibilityAllows',dict(env),state,left,right)
        self.assertFalse(run());self.assertEqual([],native_calls)
        matching[0]=True;visible[0]=False
        self.assertFalse(run());self.assertEqual(['ray'],native_calls)
        visible[0]=True
        self.assertFalse(run());self.assertEqual(['ray'],native_calls)
        state.m_LOSRays=0;now[0]+=1.01
        self.assertTrue(run());self.assertEqual(['ray','ray'],native_calls)
        right.Player.IsUnconscious=lambda:True
        self.assertFalse(run())

    def test_equipment_requires_owned_working_handheld_and_bounded_inventory(self):
        source=(ROOT/'mods/HollowCountry/scripts/4_World/Groups/HCGroupVisibility.c').read_text()
        source=source.replace('HCGroupEquipment Read(', 'HCGroupMember Read(')
        source=source.replace('array<EntityAI> items = new array<EntityAI>()', 'HCGroupItems items = Items()')
        source=source.replace('ItemBase item =','HCGroupItem item =').replace('PersonalRadio handheld =','HCGroupRadio handheld =').replace('ItemGPS gps =','HCGroupGPS gps =')
        scanned=[];items=EArray()
        count=[0]
        inventory=NS(CountInventory=lambda:count[0],EnumerateInventory=lambda mode,out:scanned.append(mode) or out.extend(items))
        player=NS(IsAlive=lambda:True,GetInventory=lambda:inventory)
        def item(kind='radio',working=True,owner=player,frequency=87.8,ruined=False):
            return NS(kind=kind,IsRuined=lambda:ruined,GetHierarchyRootPlayer=lambda:owner,
                IsTransmitter=lambda:True,GetCompEM=lambda:NS(IsWorking=lambda:working),GetTunedFrequency=lambda:frequency,IsTurnedOn=lambda:working)
        items.extend([item('map'),item('gps'),item(working=False),item(owner=object()),item(ruined=True),item('static'),item(frequency=89.1)])
        env={'HCGroupEquipment':lambda:NS(HasMap=False,HasGPS=False,Frequencies=EArray()),
             'CfgGameplayHandler':NS(GetMapIgnoreMapOwnership=lambda:False),'Items':EArray,'InventoryTraversalType':NS(PREORDER=1),
             'ItemBase':NS(Cast=lambda p:p),'PersonalRadio':NS(Cast=lambda p:p if p.kind=='radio' else None),
             'ItemMap':NS(Cast=lambda p:p.kind=='map'),'ItemGPS':NS(Cast=lambda p:p if p.kind=='gps' else None)}
        gear=execute_member(source,'Read',dict(env),NS(),player)
        self.assertTrue(gear.HasMap);self.assertTrue(gear.HasGPS)
        self.assertEqual([89.1],gear.Frequencies)
        items[:]=[item('gps',working=False)]
        gear=execute_member(source,'Read',dict(env),NS(),player)
        self.assertFalse(gear.HasGPS)
        count[0]=513
        gear=execute_member(source,'Read',dict(env),NS(),player)
        self.assertFalse(gear.HasMap);self.assertEqual([],gear.Frequencies)
        self.assertEqual([1,1],scanned)

    def test_mission_list_consumes_only_fresh_public_rows(self):
        from tests.unit.test_group_ui import ui_member, SyntheticList
        source=(ROOT/'mods/HollowCountry/scripts/5_Mission/Groups/HCGroupMapLayers.c').read_text()
        source=source.replace('HCEventClient events =','HCGroupClient events =').replace('HCEventPublicView known =','HCGroupView known =')
        source=source.replace('row.RemainingSeconds.ToString()','str(row.RemainingSeconds)')
        widget=SyntheticList();state=NS(mHCEvents=widget)
        fresh=[False];reads=[]
        rows=EArray([NS(Title='Public synthetic',RemainingSeconds=10,Status=1,Joined=False),NS(Title='Expired synthetic',RemainingSeconds=0,Status=4,Joined=True)])
        env={'HCEventClient':NS(Get=lambda:NS(Fresh=lambda:fresh[0],GetView=lambda:reads.append('view') or NS(Enabled=True,Rows=rows))),
             'HCEventStatus':NS(ANNOUNCED=1,ACTIVE=2),'str':str}
        ui_member(source,'Missions',state,dict(env),NS(MissionLayer=True))
        self.assertEqual([],reads)
        fresh[0]=True
        ui_member(source,'Missions',state,dict(env),NS(MissionLayer=True))
        self.assertEqual(['[Known] Public synthetic (10s)'],widget.items)
        ui_member(source,'Missions',state,dict(env),NS(MissionLayer=False))
        self.assertEqual([],widget.items)

class V1GroupsJournalBehavior(unittest.TestCase):
    def test_roles_visits_and_legacy_defaults_reopen_through_actual_journal(self):
        import json
        from tests.unit.test_group_persistence import StoreHarness, NativeText
        rules=V1GroupsBehavior();rules.setUp();g=rules.joined()
        self.assertEqual(0,rules.apply('alice',13,TargetId='bob',Role=1))
        place=rules.e['HCGroupPlace']();place.Id='synthetic';place.Name='Visited';place.Position=[10,0,10]
        self.assertTrue(rules.e['RecordVisit'](rules.state,rules.cfg,'alice',place,[10,0,10]))
        rules.state.WorldName='synthetic_world';rules.state.Revision=2
        h=StoreHarness();store=h.store(rules.cfg)
        self.assertTrue(store.Open(rules.cfg,None)[0])
        self.assertTrue(store.Save(rules.state))
        ok,loaded=h.store(rules.cfg).Open(rules.cfg,None)
        self.assertTrue(ok);self.assertEqual(['bob'],loaded.Groups[0].Officers)
        self.assertEqual('synthetic',loaded.Explorers[0].PlaceIds[0])
        image=store.PathFor('state_',2)
        legacy=json.loads(h.files[image]);legacy.pop('Explorers')
        for group in legacy['Groups']:group.pop('Officers')
        h.files[image]=NativeText(json.dumps(legacy))
        for prefix in ('intent_','commit_'):
            receipt=store.PathFor(prefix,2);data=json.loads(h.files[receipt])
            data['Hash']=h.files[image].Hash();data['Length']=len(h.files[image])
            h.files[receipt]=NativeText(json.dumps(data))
        ok,loaded=h.store(rules.cfg).Open(rules.cfg,None)
        self.assertTrue(ok);self.assertEqual([],loaded.Groups[0].Officers)
        self.assertEqual([],loaded.Explorers)

class V1GroupsLOSBehavior(unittest.TestCase):
    def test_los_uses_current_head_bones_and_fails_closed_on_unknown_skeleton(self):
        source=(ROOT/'mods/HollowCountry/scripts/4_World/Groups/HCGroupVisibility.c').read_text()
        source=source.replace('Object ignored =','HCGroupNative ignored =').replace('Object parent =','HCGroupNative parent =')
        source=source.replace('vector contact;', 'HCGroupVector contact;').replace('vector normal;', 'HCGroupVector normal;')
        source=source.replace('set<Object> hits = new set<Object>()', 'HCGroupHits hits = Hits()')
        class Vec(list):
            def __add__(self,other):return Vec(a+b for a,b in zip(self,other))
        bones=[1];calls=[];obstruction=[False];hit=EArray()
        left=NS(GetParent=lambda:None,GetPosition=lambda:Vec([100,0,200]),GetBoneIndexByName=lambda name:bones[0],GetBonePositionWS=lambda idx:Vec([100,0.3,200]))
        right=NS(GetParent=lambda:None,GetPosition=lambda:Vec([110,0,200]),GetBoneIndexByName=lambda name:bones[0],GetBonePositionWS=lambda idx:Vec([110,1.6,200]))
        def ray(start,end,contact,normal,component,hits,*args):
            calls.append((start,end,args));hits.extend(hit);return obstruction[0]
        env={'Vector':lambda *a:Vec(a),'Hits':EArray,'DayZPhysics':NS(RaycastRV=ray),
             'ObjIntersectView':7,'CollisionFlags':NS(NEARESTCONTACT=1),
             'Object':NS(Cast=lambda p:p),'PositionValid':lambda v:len(v)==3 and all(0<=x<=50000 for x in v)}
        run=lambda:execute_member(source,'HasLOS',dict(env),NS(),left,right)
        self.assertTrue(run())
        self.assertEqual(([100,0.3,200],[110,1.6,200]),calls[-1][:2])
        obstruction[0]=True;hit.append(object());self.assertFalse(run())
        hit[:]=[right];self.assertTrue(run())
        bones[0]=-1;before=len(calls);self.assertFalse(run());self.assertEqual(before,len(calls))

class V1GroupsDiscoveryScheduleBehavior(unittest.TestCase):
    def test_one_bounded_discovery_pass_observes_six_players_with_one_commit(self):
        source=(ROOT/'mods/HollowCountry/scripts/4_World/Groups/HCGroupService.c').read_text()
        source=source.replace('Clone(candidate)','((candidate := self.Clone()) != null)')
        for method in ('Stop','Commit','Broadcast'):
            import re
            source=re.sub(r'(?<![\w.])'+method+r'\(', 'self.'+method+'(',source)
        env=translated_rules();env['GetGame']=lambda:NS(GetTickTime=lambda:100.);cfg=env['HCGroupSettings']()
        place=env['HCGroupPlace']();place.Id='synthetic';place.Name='Synthetic place';place.Position=[100,0,200]
        peers=EArray(NS(Id=str(i),Player=NS(IsAlive=lambda:True,IsUnconscious=lambda:False,GetPosition=lambda:[100,0,200])) for i in range(6))
        writes=[];broadcasts=[]
        state=NS(m_Config=cfg,m_State=env['HCGroupState'](),m_Places=NS(Places=EArray([place])),m_Peers=peers,m_DiscoveryCursor=0,m_DiscoveryBlockedUntil=0.,m_LastUtc=1000,
                 Peer=lambda uid:next((p for p in peers if p.Id==uid),None),Live=lambda p:True,Commit=lambda s:writes.append(s) or 0,Broadcast=lambda:broadcasts.append(1),Stop=lambda:self.fail('unexpected stop'))
        state.Clone=lambda:copy.deepcopy(state.m_State)
        state.EvictExplorers=lambda *args:False  # No offline journals in this six-live-peer fixture.
        execute_member(source,'Discover',env,state)
        self.assertEqual(1,len(writes));self.assertEqual(6,len(writes[0].Explorers));self.assertEqual([1],broadcasts)
