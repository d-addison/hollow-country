"""Execute authored client methods with synthetic native adapters."""
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from tests.unit.json_loader_port import json_fields_port
from tests.unit.test_group_server import execute_member, translated_rules

class ClientTests(unittest.TestCase):
    def setUp(self):
        self.src=(Path(__file__).resolve().parents[2]/'mods/HollowCountry/scripts/5_Mission/Groups/HCGroupClient.c').read_text()
        self.e=translated_rules()
        self.c=N(**{n:0 for n in re.findall(r'protected (?:ref )?\w+ (m_\w+)',self.src)})
        self.now=100.
        self.sent=[]
        self.e.update(GetGame=lambda:N(GetTickTime=lambda:self.now),
            HCGroupProtocol=N(VERSION=3,RPC_REQUEST=4853701),
            Math=N(RandomIntInclusive=lambda a,b:900001),
            ContentsValid=lambda f:True,Make=self.make,Load=self.load,
            Transmit=self.tx,str=str,Print=lambda *a:None,
            HCJsonFields=json_fields_port())
        for n in ('ClearView','ResetSession','SnapshotValid','FrameOrder','Sync',
                  'Recover','Retry'):
            self.e[n]=lambda *a,n=n:self.run_method(n,*a)
        self.run_method('ResetSession')
        self.c.m_Session='S'
        self.c.m_View=N(Enabled=True)

    def tx(self,q):
        self.sent.append(json.dumps(vars(q),sort_keys=True))
        self.c.m_LastSend=self.now

    def make(self,q):
        # Native MakeData serializes every declared member, so Color is always present.
        self.c.m_PendingPayload=json.dumps({'Color':-1,**vars(q)},sort_keys=True)
        return True

    def load(self):
        from tests.unit.json_loader_port import decode_json
        self.c.m_Pending=decode_json(self.c.m_PendingPayload, "HCGroupRequest")
        return True

    def run_method(self,n,*a):
        s=re.sub(r'JsonFileLoader<HCGroupRequest>\.MakeData\((\w+), [^,]+, \w+\)',r'Make(\1)',self.src)
        s=re.sub(r'JsonFileLoader<HCGroupRequest>\.LoadData\([^)]+\)','Load()',s)
        s=re.sub(r'(\bm_\w+)\+\+',r'\1 += 1',s)
        s=s.replace('reply.Code.ToString()','str(reply.Code)')
        # Syntax adapters only; Update still executes its authored branches.
        s=re.sub(r'\bPlayerBase (?=\w+\s*=)','',s)
        s=re.sub(r'foreach \(\w+ (\w+) : ([^)]+)\)',r'for \1 in \2:',s)
        # Preserve string contents across the shared translator's statement
        # splitting, including semicolons, braces and escaped characters.
        literals=[]
        def literal(match):
            name='_client_literal_'+str(len(literals))
            literals.append(json.loads(match[0]))
            self.e[name]=literals[-1]
            return name
        s=re.sub(r'"(?:\\.|[^"\\])*"',literal,s)
        return execute_member(s,n,self.e,self.c,*a)

    def frame(self,floor=5,**kw):
        f=self.e['HCGroupSnapshot']()
        f.Version=3;f.Session='S';f.Sequence=20
        f.RequestId=self.c.m_SyncTicket or 900001
        f.LastMutationId=floor;f.Enabled=True
        f.Settings=self.e['HCGroupSettings']()
        f.Settings.Enabled=True
        for k,v in kw.items():setattr(f,k,v)
        return f

    def sync(self):
        # Transmit records the send time. A SYNC immediately after Send is
        # intentionally throttled; advance the synthetic native clock so these
        # scenarios actually transmit SYNC and establish its matching ticket.
        self.now+=1.
        self.run_method('Sync',self.now)

    def send(self):
        q=self.e['HCGroupRequest']()
        q.Op=1;q.Name='Original'
        self.assertTrue(self.run_method('Send',q))
        return q

    def test_recovery_counter(self):
        self.run_method('ResetSession');self.sync()
        self.assertTrue(self.run_method('ReceiveSnapshot',self.frame()))
        self.send()
        self.assertEqual(6,self.c.m_Pending.RequestId)

    def test_old_sync_after_completed_mutation(self):
        self.c.m_RequestId=5;self.sync();self.send()
        r=self.e['HCGroupReply']()
        r.Version=3;r.Session='S';r.RequestId=6;r.LastMutationId=6;r.Code=0
        self.run_method('ReceiveReply',r)
        self.run_method('ReceiveSnapshot',self.frame())
        self.assertEqual(6,self.c.m_RequestId)

    def test_pending_survives_sync(self):
        self.send();p=self.c.m_Pending;self.sync()
        self.run_method('ReceiveSnapshot',self.frame(0))
        self.assertIs(p,self.c.m_Pending)
        self.assertEqual(1,self.c.m_RequestId)

    def test_private_frozen_retry(self):
        q=self.send();first=self.sent[-1];q.Name='Changed'
        self.now+=3;self.run_method('Retry',self.now)
        self.assertIsNot(q,self.c.m_Pending)
        self.assertEqual(2,len(self.sent))
        self.assertEqual(first,self.sent[-1])

    def test_invalid_handshakes(self):
        for kw in ({'RequestId':9},{'Sequence':0},
                   {'LastMutationId':-1},{'LastMutationId':1000001}):
            self.run_method('ResetSession');self.sync()
            self.assertFalse(self.run_method('ReceiveSnapshot',self.frame(**kw)))
            self.assertEqual(0,self.c.m_RequestId)

    def test_changed_session_never_replays(self):
        self.send();self.sync()
        self.run_method('ReceiveSnapshot',self.frame(0,Session='NEW'))
        self.assertIsNone(self.c.m_Pending)
        count=len(self.sent);self.now+=3
        self.run_method('Retry',self.now)
        self.assertEqual(count,len(self.sent))

    def test_retry_budget_retains_uncertainty(self):
        self.send();p=self.c.m_Pending
        for _ in range(4):
            self.now+=3;self.run_method('Retry',self.now)
        self.assertEqual(4,len(self.sent))
        self.sync()
        self.run_method('ReceiveSnapshot',self.frame(1))
        self.assertIs(p,self.c.m_Pending)

    def test_unknown_session_quarantines_later_old_session_frames(self):
        self.c.m_RequestId=5
        self.assertTrue(self.run_method('ReceiveSnapshot',
            self.frame(5,Sequence=10,RequestId=0)))
        self.assertFalse(self.run_method('ReceiveSnapshot',
            self.frame(0,Session='NEW',Sequence=1,RequestId=0)))
        self.assertIsNone(self.c.m_View)
        self.assertFalse(self.run_method('ReceiveSnapshot',
            self.frame(5,Sequence=11,RequestId=0)))
        self.assertIsNone(self.c.m_View)
        self.assertEqual(5,self.c.m_RequestId)
        # Only a newly transmitted, correlated handshake ends quarantine.
        self.sync()
        self.assertTrue(self.run_method('ReceiveSnapshot',
            self.frame(0,Session='NEW',Sequence=2)))
        self.assertEqual('NEW',self.c.m_Session)

    def test_recovery_rejects_colliding_ticket_and_confirmed_floor_rollback(self):
        self.c.m_RequestId=5
        self.sync()
        old_ticket=self.c.m_SyncTicket
        held=self.frame(5)
        self.send()
        r=self.e['HCGroupReply']()
        r.Version=3;r.Session='S';r.RequestId=6;r.LastMutationId=6;r.Code=0
        self.run_method('ReceiveReply',r)
        self.run_method('Recover')
        self.sync()
        new_ticket=self.c.m_SyncTicket
        accepted=self.run_method('ReceiveSnapshot',held)
        self.assertEqual(6,self.c.m_RequestId)
        self.assertNotEqual(old_ticket,new_ticket)
        self.assertFalse(accepted)
        self.assertIsNone(self.c.m_View)
        # Even a matching new ticket cannot erase a confirmed consumption.
        self.assertFalse(self.run_method('ReceiveSnapshot',
            self.frame(5,Sequence=21,RequestId=new_ticket)))
        self.assertEqual(6,self.c.m_RequestId)
        self.assertTrue(self.run_method('ReceiveSnapshot',
            self.frame(6,Sequence=22,RequestId=new_ticket)))

    def test_recovery_can_lower_unconfirmed_client_counter(self):
        self.c.m_RequestId=8
        self.sync()
        self.assertTrue(self.run_method('ReceiveSnapshot',self.frame(5)))
        self.assertEqual(5,self.c.m_RequestId)

    def test_rate_reply_and_zero_floor_do_not_acknowledge_pending(self):
        self.send()
        pending=self.c.m_Pending
        r=self.e['HCGroupReply']()
        r.Version=3;r.Session='S';r.RequestId=0
        r.LastMutationId=0;r.Code=8
        self.run_method('ReceiveReply',r)
        self.assertIs(pending,self.c.m_Pending)
        self.sync()
        self.assertTrue(self.run_method('ReceiveSnapshot',self.frame(0)))
        self.assertIs(pending,self.c.m_Pending)
        self.assertEqual(1,self.c.m_RequestId)
        self.assertEqual(0,self.c.m_ConfirmedMutationId)

    def test_tick_rollback_executes_recover_without_losing_uncertainty(self):
        # Explicit synthetic player and native clock; no engine invocation.
        player=N(GetIdentity=lambda:object(),IsAlive=lambda:True)
        self.e['PlayerBase']=N(Cast=lambda p:p)
        self.e['GetGame']=lambda:N(GetTickTime=lambda:self.now,
                                   GetPlayer=lambda:player)
        self.c.m_LocalPlayer=player
        self.send()
        self.sync()
        pending=self.c.m_Pending
        payload=self.c.m_PendingPayload
        generation=self.c.m_MutationGeneration
        self.c.m_Retries=2
        count=len(self.sent)
        self.now=self.c.m_LastSend-1.
        self.run_method('Update')
        self.assertIs(pending,self.c.m_Pending)
        self.assertEqual(payload,self.c.m_PendingPayload)
        self.assertEqual(generation,self.c.m_MutationGeneration)
        self.assertEqual(1,self.c.m_RequestId)
        self.assertEqual(2,self.c.m_Retries)
        self.assertEqual(0,self.c.m_SyncTicket)
        self.assertIsNone(self.c.m_View)
        self.assertTrue(self.c.m_Quarantined)
        self.assertEqual(count,len(self.sent))

    def test_ticket_exhaustion_fails_closed_without_resetting_budget(self):
        # Temporary limit: 100000 tickets, about 11.6 days at ten-second
        # polling. Exhaustion requires reconnect; it never wraps locally.
        self.send()
        pending=self.c.m_Pending
        self.c.m_LastSyncTicket=999999
        self.sync()
        self.assertEqual(1000000,self.c.m_SyncTicket)
        self.assertTrue(self.run_method('ReceiveSnapshot',self.frame(0)))
        count=len(self.sent)
        self.sync()
        self.assertEqual(count,len(self.sent))
        self.assertEqual(0,self.c.m_SyncTicket)
        self.assertEqual(1000000,self.c.m_LastSyncTicket)
        self.assertIs(pending,self.c.m_Pending)
        self.assertIsNone(self.c.m_View)
        self.assertTrue(self.c.m_Quarantined)
        self.assertGreater(self.c.m_NextSync,self.now)
        self.run_method('ResetSession')
        self.sync()
        self.assertEqual(count,len(self.sent))
        self.assertEqual(1000000,self.c.m_LastSyncTicket)

    def test_unticketed_session_frames_cannot_replace_pending(self):
        self.send()
        pending=self.c.m_Pending
        self.assertFalse(self.run_method('ReceiveSnapshot',
            self.frame(0,Session='NEW',Sequence=1,RequestId=0)))
        self.sync()
        ticket=self.c.m_SyncTicket
        for session in ('S','NEW'):
            self.assertFalse(self.run_method('ReceiveSnapshot',
                self.frame(0,Session=session,Sequence=30,RequestId=0)))
            self.assertIsNone(self.c.m_View)
            self.assertIs(pending,self.c.m_Pending)
            self.assertEqual(ticket,self.c.m_SyncTicket)
        self.assertTrue(self.run_method('ReceiveSnapshot',
            self.frame(0,Session='NEW',Sequence=2,RequestId=ticket)))
        self.assertIsNone(self.c.m_Pending)
