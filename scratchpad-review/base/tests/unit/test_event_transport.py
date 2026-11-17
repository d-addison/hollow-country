"""Authored event RPC bodies, synthetic native transport only; no network proof."""
import copy
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from tests.unit import test_event_runtime as event_runtime
from tests.unit.test_group_server import EArray
Handle, ROOT, translate = event_runtime.Handle, event_runtime.ROOT, event_runtime.translate


def methods(path, env, names=None):
    source = path.read_text()
    # Native deserialization out parameter and native types, no policy rewrite.
    source = source.replace("ScriptRPC", "HCEventSyntheticRPC")
    source = source.replace("if (!ctx.Read(request) || !request)", "request = ctx.Read(); if (!request)")
    source = source.replace("if (!ctx.Read(view) || !view)", "view = ctx.Read(); if (!view)")
    source = source.replace(".Remove(OnRPC)", ".Remove(self.OnRPC)").replace(".Insert(OnRPC)", ".Insert(self.OnRPC)")
    cls = type("Authored" + path.stem, (), {})
    selected = names or re.findall(r"^    (?:override )?(?:bool|int|float|string|void|HCEvent\w+) (\w+)\(", source, re.M)
    for name in selected:
        setattr(cls, name, translate(source, name, env, path.stem, True))
    return cls


class Sender:
    def __init__(self, identity, player): self.identity = identity; self.player = player
    def GetId(self): return self.identity
    def GetPlayer(self): return self.player


class EventTransportTests(unittest.TestCase):
    def setUp(self):
        self.helper = event_runtime.EventRuntimeTests(); self.helper.setUp(); self.runtime = self.helper.runtime()
        self.e = self.helper.e; self.context = self.helper.ctx
        self.assertEqual(0, self.runtime.Announce(self.helper.mission, self.context))
        self.player = self.helper.player; self.sender = Sender("alice", self.player)
        self.player.GetIdentity = lambda:self.sender
        self.player.IsPlayerDisconnected = lambda:False
        self.player.IsUnconscious = lambda:False
        self.now = 100.; self.sent = []
        self.e["GetGame"] = lambda: SimpleNamespace(IsServer=lambda:True, GetTickTime=lambda:self.now)
        self.e["PlayerBase"] = SimpleNamespace(Cast=lambda obj:obj if isinstance(obj,Handle) else None)
        self.e["DayZGame"] = SimpleNamespace(Event_OnRPC=SimpleNamespace(Remove=lambda fn:None,Insert=lambda fn:None))
        self.e["HCEventPeer"] = lambda:SimpleNamespace(Identity=None,Player=None,Session="",LastRequest=0,
            LastOp=0,LastEventId=0,LastCode=0,Sequence=0,RateWindow=0.,RateCount=0,NextMutation=0.)
        test = self
        class NativeRPC:
            def Write(self, value): self.value = copy.deepcopy(value)
            def Send(self, target, kind, guaranteed, recipient): test.sent.append((target,kind,recipient,self.value))
        self.e["HCEventSyntheticRPC"] = NativeRPC
        cls = methods(ROOT / "4_World/Events/HCEventRPC.c", self.e)
        self.rpc = cls(); self.rpc.m_Module = SimpleNamespace(Runtime=lambda:self.runtime,Context=lambda:copy.deepcopy(self.context))
        self.rpc.m_Peers = EArray(); self.rpc.m_Serial = 0; self.rpc.m_GlobalWindow = 0.
        self.rpc.m_GlobalCount = 0; self.rpc.m_Started = True
        self.rpc.m_Boot = "synthetic-transport"; self.rpc.m_LastTime = 100.
        self.rpc.m_ProjectionState = None

    def request(self, op=0, request_id=0, event=0, session="", ticket=1):
        r = self.e["HCEventWireRequest"](); r.Op=op; r.RequestId=request_id
        r.EventId=event; r.Session=session; r.Ticket=ticket; return r

    def receive(self, request, sender=None, target=None, readable=True):
        self.rpc.OnRPC(sender or self.sender,target,4853801,SimpleNamespace(Read=lambda:request if readable else None))
        return self.sent[-1][3] if self.sent else None

    def handshake(self):
        return self.receive(self.request())

    def mutate(self, op=1, request_id=1, event=1):
        peer=self.rpc.m_Peers[0]
        return self.receive(self.request(op,request_id,event,peer.Session,0))

    def test_first_browse_authenticated_and_targeted(self):
        view = self.handshake(); self.assertTrue(view.Enabled); self.assertEqual(1,len(view.Rows))
        self.assertEqual(1,view.Ticket); self.assertEqual(0,view.LastRequest)
        self.assertIs(self.player,self.sent[-1][0]); self.assertIs(self.sender,self.sent[-1][2])

    def test_sender_player_identity_mismatch_drops_before_read(self):
        forged=Sender("alice",Handle())
        self.receive(self.request(),forged); self.assertEqual([],self.sent)
        self.receive(self.request(),target=self.player); self.assertEqual([],self.sent)

    def test_join_leave_native_attribution_and_repeat_no_double_mutation(self):
        self.handshake(); joined=self.mutate()
        self.assertEqual(0,joined.Code); self.assertTrue(joined.Rows[0].Joined)
        before=copy.deepcopy(self.runtime.m_State); self.now+=1
        repeat=self.mutate(); self.assertEqual(before,self.runtime.m_State)
        self.assertEqual(1,repeat.ReceiptId); self.assertEqual(1,repeat.ReceiptOp)
        self.now += 3
        left=self.mutate(2,2); self.assertFalse(left.Rows[0].Joined)

    def test_wrong_session_and_skipped_id_do_not_consume(self):
        self.handshake()
        view=self.receive(self.request(1,1,1,"old",0)); self.assertEqual(9,view.Code)
        self.assertEqual(0,view.LastRequest)
        view=self.mutate(request_id=2); self.assertEqual(10,view.Code); self.assertEqual(0,view.LastRequest)
        self.assertEqual([],self.runtime.m_State.Director.Records[0].Participants)

    def test_same_id_different_payload_never_replays_success(self):
        self.handshake(); self.mutate(); self.now+=1
        view=self.mutate(op=2,request_id=1)
        self.assertEqual(10,view.Code); self.assertTrue(view.Rows[0].Joined)
        self.assertEqual(1,view.ReceiptOp)

    def test_browse_preserves_counter_and_receipt(self):
        self.handshake(); self.mutate(); view=self.receive(self.request(ticket=2))
        self.assertEqual(1,view.LastRequest); self.assertEqual(1,view.ReceiptId)
        self.assertEqual(2,view.Ticket); self.assertEqual(0,view.ReceiptCode)

    def test_malformed_fields_bounded_before_consumption(self):
        self.handshake()
        for key,value in (("Version",2),("Session","x"*129),("Op",3),("RequestId",1000000001),
                          ("EventId",33),("Ticket",-1)):
            self.now+=1; request=self.request(1,1,1,self.rpc.m_Peers[0].Session,0)
            setattr(request,key,value); self.receive(request)
            self.assertEqual(0,self.rpc.m_Peers[0].LastRequest,key)
        self.assertEqual([],self.runtime.m_State.Director.Records[0].Participants)

    def test_rate_limits_reject_without_consuming_and_clock_rollback_recovers(self):
        self.handshake()
        for ticket in range(2,6): self.receive(self.request(ticket=ticket))
        self.assertEqual(4,len(self.sent)); self.assertEqual(0,self.rpc.m_Peers[0].LastRequest)
        self.now=99.; self.receive(self.request()); self.assertTrue(self.rpc.m_Started)
        self.now=100.; view=self.receive(self.request(ticket=9))
        self.assertTrue(view.Enabled); self.assertEqual(9,view.Ticket)

    def test_new_peer_during_nonfinite_clock_recovers_after_multiple_rate_windows(self):
        self.now = float("nan"); self.handshake()
        self.assertEqual([], self.sent); self.assertTrue(self.rpc.m_Started)
        for tick in range(100, 110):
            self.now = float(tick)
            before = len(self.sent)
            self.receive(self.request(ticket=tick))
            self.assertEqual(before + 1, len(self.sent), tick)

    def test_clock_rollback_cannot_bypass_mutation_cooldown(self):
        self.handshake(); self.mutate()
        writes = self.helper.store.calls
        self.now = 99.
        refused = self.mutate(2, 2)
        self.assertEqual(4, refused.Code); self.assertEqual(writes, self.helper.store.calls)
        self.now = 102.
        self.assertEqual(0, self.mutate(2, 3).Code)

    def test_reconnect_discards_old_peer_cooldown(self):
        self.handshake(); self.mutate()
        replacement = Handle(); sender = Sender("alice", replacement)
        replacement.GetIdentity = lambda: sender
        replacement.IsPlayerDisconnected = lambda: False
        replacement.IsUnconscious = lambda: False
        view = self.receive(self.request(), sender)
        self.assertEqual(1, len(self.rpc.m_Peers))
        joined = self.receive(self.request(1, 1, 1, view.Session, 0), sender)
        self.assertEqual(0, joined.Code)

    def test_join_leave_cooldown_bounds_writes_and_replays_receipts(self):
        self.handshake(); self.mutate()
        writes = self.helper.store.calls
        self.now += 1
        view = self.mutate(2,2)
        self.assertNotEqual(0, view.Code)
        self.assertTrue(view.Rows[0].Joined)
        self.assertEqual(writes, self.helper.store.calls)
        self.now += 3
        replay = self.mutate(2,2)
        self.assertEqual(view.ReceiptCode, replay.ReceiptCode)
        self.assertEqual(writes, self.helper.store.calls)
        left = self.mutate(2,3)
        self.assertEqual(0, left.Code); self.assertFalse(left.Rows[0].Joined)
        self.assertEqual(writes + 1, self.helper.store.calls)

    def test_unchanged_revision_browse_reuses_snapshot_and_refreshes_time(self):
        snapshots = []
        original = self.runtime.Snapshot
        def snapshot():
            snapshots.append(1); return original()
        self.runtime.Snapshot = snapshot
        first = self.handshake(); self.now += 2; self.context.Now += 2
        second = self.receive(self.request(ticket=2))
        self.assertEqual(1, len(snapshots))
        self.assertEqual(first.Rows[0].RemainingSeconds - 2, second.Rows[0].RemainingSeconds)
        self.mutate()
        self.assertEqual(2, len(snapshots))

    def test_wire_slots_remain_client_compatible_after_durable_ids_exceed_32(self):
        for boot in range(40):
            self.context.Session = "wire-boot-" + str(boot); self.context.Now = 0
            self.assertTrue(self.runtime.Start(self.helper.cfg, self.context, self.helper.store,
                                              self.helper.observer, self.helper.ai))
            self.runtime.Tick(self.context)
            self.assertEqual(0, self.runtime.Announce(self.helper.mission, self.context))
        durable_id = self.runtime.m_State.Director.Records[-1].Id
        self.assertGreater(durable_id, 32)
        view = self.handshake()
        self.assertEqual([1], [row.EventId for row in view.Rows])
        self.assertEqual(0, self.mutate(event=1).Code)
        self.assertEqual(["alice"], self.runtime.m_State.Director.Records[-1].Participants)
        self.assertEqual(1, self.sent[-1][3].ReceiptEventId)

    def test_invalid_deserialization_and_other_rpc_do_not_mutate(self):
        self.receive(self.request(),readable=False); self.assertEqual([],self.sent)
        self.rpc.OnRPC(self.sender,None,4853802,SimpleNamespace(Read=lambda:self.request()))
        self.assertEqual([],self.sent)

    def test_public_projection_has_no_accounts_positions_items_or_internal_refs(self):
        view=self.handshake()
        self.assertEqual({"EventId","Revision","Family","Title","Status","Progress","Goal",
            "Participants","MaxParticipants","RemainingSeconds","Joined"},set(vars(view.Rows[0])))
        self.assertNotIn("alice",repr(vars(view)))
        view.Rows[0].Progress=999
        self.assertEqual(0,self.runtime.m_State.Director.Records[0].Progress)

    def test_reconnect_new_handle_gets_new_wire_session_and_explicit_rejoin(self):
        original=self.handshake(); self.mutate(); self.now+=1
        replacement=Handle(); new_sender=Sender("alice",replacement)
        replacement.GetIdentity=lambda:new_sender; replacement.IsPlayerDisconnected=lambda:False
        replacement.IsUnconscious=lambda:False
        view=self.receive(self.request(),new_sender)
        self.assertNotEqual(original.Session,view.Session); self.assertEqual(0,view.LastRequest)
        self.assertFalse(view.Rows[0].Joined)
        self.receive(self.request(1,2,1,original.Session,0),new_sender)
        self.assertEqual([],self.runtime.m_State.Director.Records[0].Participants)

    def test_disabled_or_faulted_runtime_returns_empty_disabled_view(self):
        self.handshake(); self.runtime.m_Ready=False; self.now+=1
        view=self.receive(self.request(ticket=2)); self.assertFalse(view.Enabled); self.assertEqual([],view.Rows)

    def test_disconnect_tick_releases_peer_and_membership(self):
        self.handshake(); self.mutate(); self.player.IsPlayerDisconnected=lambda:True
        self.rpc.Tick(); self.assertEqual([],self.rpc.m_Peers)
        self.assertEqual([],self.runtime.m_State.Director.Records[0].Participants)

    def test_unconscious_join_refused_without_side_effect(self):
        self.handshake(); self.player.IsUnconscious=lambda:True
        view=self.mutate(); self.assertEqual(2,view.ReceiptCode)
        self.assertEqual([],self.runtime.m_State.Director.Records[0].Participants)

    def test_deleted_native_identity_is_pruned_before_next_authentication(self):
        self.handshake();self.mutate();self.rpc.m_Peers[0].Identity=None;self.now+=1
        view=self.receive(self.request(ticket=2))
        self.assertIsNotNone(view);self.assertEqual(1,len(self.rpc.m_Peers))
        self.assertFalse(view.Rows[0].Joined)

    def test_global_budget_and_peer_capacity_are_independently_bounded(self):
        self.handshake();self.rpc.m_GlobalCount=128
        self.assertFalse(self.rpc.Admit(self.rpc.m_Peers[0]))
        self.rpc.m_Peers.Clear()
        for index in range(90):
            player=Handle(identity=str(index));sender=Sender(str(index),player)
            player.GetIdentity=lambda sender=sender:sender
            player.IsPlayerDisconnected=lambda:False
            peer=self.e["HCEventPeer"]();peer.Identity=sender;peer.Player=player
            self.rpc.m_Peers.Insert(peer)
        self.assertIsNone(self.rpc.Authenticate(self.sender));self.assertEqual(90,len(self.rpc.m_Peers))

    def test_start_stop_register_exact_native_callback_once(self):
        inserted=[];removed=[]
        self.e["DayZGame"].Event_OnRPC.Insert=lambda callback:inserted.append(callback)
        self.e["DayZGame"].Event_OnRPC.Remove=lambda callback:removed.append(callback)
        self.e["Math"].RandomIntInclusive=lambda low,high:1234
        self.rpc.m_Started=False
        self.assertTrue(self.rpc.Start(self.rpc.m_Module));self.assertFalse(self.rpc.Start(self.rpc.m_Module))
        self.rpc.Stop();self.rpc.Stop()
        self.assertEqual(1,len(inserted));self.assertEqual(inserted,removed)


if __name__ == "__main__": unittest.main()
