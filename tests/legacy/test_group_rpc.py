"""Authored RPC admission/commit/replay with synthetic authenticated native IO.

No sockets, clients, native restart, renderer or network acceptance is claimed.
"""
import copy
import re
import unittest
from types import SimpleNamespace as N

from tests.legacy.test_group_server import ROOT, body, execute_member
from tests.legacy.test_group_persistence import StoreHarness


class GroupRpcTests(unittest.TestCase):
    def setUp(self):
        self.h=StoreHarness();self.e=dict(self.h.rules)
        self.cfg=self.e['HCGroupSettings']()
        self.store=self.h.store(self.cfg)
        ok,state=self.store.Open(self.cfg,None);self.assertTrue(ok)
        self.now=2000000001;self.sent=[];self.frames=[]
        self.peer=N(Id='alice',Session='synthetic-session',LastRequest=0,
                    LastPayload='',LastReply=None)
        self.identity=N(GetId=lambda:self.peer.Id)
        self.peer.Identity=self.identity
        self.service=N(m_Config=self.cfg,m_State=state,m_Store=self.store,
                       m_Healthy=True,m_LastUtc=1000)
        self.source=(ROOT/'4_World/Groups/HCGroupService.c').read_text()
        test=self
        class RPC:
            def Write(self,value):self.value=value
            def Send(self,*args):test.sent.append((copy.deepcopy(self.value),args[-1]))
        game=N(IsServer=lambda:True,GetWorldName=lambda:'synthetic_world',
               GetWorld=lambda:N(GetWorldSize=lambda:15360.))
        self.e.update(GetGame=lambda:game,HCGroupClock=N(Utc=lambda:self.now),
                      encode=self.h.encode,ScriptRPC=RPC,
                      serialize=lambda value:(True,self.h.encode(value),''))
        self.service.Live=lambda p:p is self.peer
        self.service.Peer=lambda uid:self.peer if uid==self.peer.Id else None
        self.service.Admit=lambda p:True  # Admission clock/rate tested separately.
        self.service.Clone=lambda:copy.deepcopy(self.service.m_State)
        self.service.Commit=lambda candidate:execute_member(self.source,'Commit',self.e,self.service,candidate)
        self.service.Reply=lambda p,r,c,cache=False:execute_member(self.source,'Reply',self.e,self.service,p,r,c,cache)
        self.service.SendSnapshot=lambda *args:self.frames.append((args,self.service.m_LastUtc))
        self.service.Broadcast=lambda:self.frames.append(('broadcast',self.service.m_LastUtc))
        self.service.Stop=lambda:setattr(self.service,'m_Healthy',False)

    def request(self,op,number=1,**kw):
        q=self.e['HCGroupRequest']();q.Op=op;q.RequestId=number
        q.Session=self.peer.Session;q.Name='Synthetic'
        for key,value in kw.items():setattr(q,key,value)
        return q

    def dispatch(self,request):
        match=re.search(r'void OnRPC\(([^)]*)\)\s*\{',self.source)
        text=body(self.source,match.end())
        text=text.replace('ctx.Read(request)','((request := ctx.Read()) != null)')
        text=re.sub(r'JsonFileLoader<HCGroupRequest>.MakeData\(request, payload, error\)',
                    '((payload := encode(request)) != null)',text)
        text=text.replace('Clone(candidate)','((candidate := self.Clone()) != null)')
        for name in ('Connected','Admit','Reply','Stop','Commit','Broadcast'):
            text=re.sub(r'(?<![\w.])'+name+r'\(', 'self.'+name+'(',text)
        wrapper='void OnRPC('+match[1]+') {'+text+'}'
        return execute_member(wrapper,'OnRPC',self.e,self.service,self.identity,None,
                              self.e['HCGroupProtocol'].RPC_REQUEST,N(Read=lambda:request))

    def test_commit_reply_replay_and_disk_watermark_share_fresh_server_clock(self):
        q=self.request(self.e['HCGroupOp'].CREATE)
        self.dispatch(q)
        self.assertEqual(self.e['HCGroupCode'].OK,self.sent[-1][0].Code)
        self.assertIs(self.identity,self.sent[-1][1])
        self.assertEqual(self.now,self.service.m_LastUtc)
        self.assertEqual(self.now,self.service.m_State.LastMutationUtc)
        writes=len(self.h.writes)
        self.dispatch(q)
        self.assertEqual(writes,len(self.h.writes))
        self.assertEqual(1,len(self.service.m_State.Groups))
        ok,loaded=self.h.store(self.cfg).Open(self.cfg,None)
        self.assertTrue(ok)
        self.assertEqual(self.now,loaded.LastMutationUtc)
        self.assertEqual(['alice'],loaded.Groups[0].Members)

    def test_mismatched_replay_and_prior_session_never_recommit_or_poison_receipt(self):
        q=self.request(self.e['HCGroupOp'].CREATE);self.dispatch(q)
        cached=self.peer.LastReply;writes=len(self.h.writes)
        changed=copy.deepcopy(q);changed.Name='Changed'
        self.dispatch(changed)
        self.assertEqual(self.e['HCGroupCode'].CONFLICT,self.sent[-1][0].Code)
        self.assertIs(cached,self.peer.LastReply)
        self.peer.Session='replacement-session'
        self.dispatch(q)
        self.assertEqual(self.e['HCGroupCode'].SESSION,self.sent[-1][0].Code)
        self.assertEqual(writes,len(self.h.writes))

    def test_clock_rollback_stops_before_mutation_or_disk_write(self):
        q=self.request(self.e['HCGroupOp'].CREATE)
        self.now=999;writes=len(self.h.writes)
        self.dispatch(q)
        self.assertFalse(self.service.m_Healthy)
        self.assertEqual([],self.service.m_State.Groups)
        self.assertEqual(writes,len(self.h.writes))
        self.assertEqual([],self.sent)

    def test_client_accepts_full_range_member_timestamp(self):
        source=(ROOT/'5_Mission/Groups/HCGroupClient.c').read_text()
        member=self.e['HCGroupMember']();member.Id='alice';member.Name='Synthetic'
        member.Online=True;member.Alive=True;member.HasPosition=True
        for stamp,expected in [(2000000001,True),(2147483647,True),(0,False),(-1,False),
                               (2147483648,False)]:
            member.SampleUtc=stamp
            self.assertEqual(expected,execute_member(source,'MemberValid',self.e,N(),member))


if __name__ == '__main__':
    unittest.main()
