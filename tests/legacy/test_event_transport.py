"""Authored event RPC bodies, synthetic native transport only; no network proof."""
import copy
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from tests.legacy import test_event_runtime as event_runtime
from tests.legacy.test_group_server import EArray
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
        self.rpc.m_GlobalCount = 0; self.rpc.m_Started = True; self.rpc.m_Refusal = ""
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

    def test_first_browse_is_empty_disabled_and_natively_targeted(self):
        view = self.handshake()
        self.assertFalse(view.Enabled)
        self.assertEqual([], view.Rows)
        self.assertEqual(self.e["HCEventWireCode"].DISABLED, view.Code)
        self.assertEqual((0, 0), (view.Ticket, view.LastRequest))
        self.assertIs(self.player, self.sent[-1][0])
        self.assertIs(self.sender, self.sent[-1][2])
        self.assertEqual(4853802, self.sent[-1][1])

    def test_sender_player_identity_mismatch_drops_before_read(self):
        forged=Sender("alice",Handle())
        self.receive(self.request(),forged); self.assertEqual([],self.sent)
        self.receive(self.request(),target=self.player); self.assertEqual([],self.sent)

    def test_join_leave_and_repeats_are_refused_without_runtime_writes(self):
        before = copy.deepcopy(self.runtime.m_State)
        writes = self.helper.store.calls
        self.handshake()
        for op in (1, 1, 2, 2):
            self.now += 3
            view = self.mutate(op=op)
            self.assertFalse(view.Enabled)
            self.assertEqual([], view.Rows)
            self.assertEqual(11, view.Code)
            self.assertEqual((0, 0, 0), (view.LastRequest, view.ReceiptId, view.ReceiptOp))
        self.assertEqual(before, self.runtime.m_State)
        self.assertEqual(writes, self.helper.store.calls)

    def test_any_session_or_request_id_is_refused_without_consumption(self):
        self.handshake()
        for session, request_id in (("old", 1), ("", 2), (self.rpc.m_Peers[0].Session, 100)):
            self.now += 3
            view = self.receive(self.request(1, request_id, 1, session, 0))
            self.assertEqual(11, view.Code)
            self.assertEqual(0, view.LastRequest)
            self.assertFalse(self.rpc.RequestValid(self.request(1, request_id, 1, session, 0)))
        self.assertFalse(self.rpc.RequestValid(None))
        self.assertEqual([], self.runtime.m_State.Director.Records[0].Participants)

    def test_same_id_different_payload_never_replays_success(self):
        self.handshake(); self.mutate(); self.now += 1
        view = self.mutate(op=2, request_id=1)
        self.assertEqual(11, view.Code)
        self.assertEqual([], view.Rows)
        self.assertEqual((0, 0), (view.ReceiptId, view.ReceiptOp))

    def test_refusals_sequence_replies_without_acknowledging_quest_intent(self):
        first = self.handshake()
        second = self.mutate()
        view = self.receive(self.request(ticket=2))
        self.assertEqual([1, 2, 3], [first.Sequence, second.Sequence, view.Sequence])
        self.assertEqual(first.Session, view.Session)
        self.assertEqual((0, 0, 0), (view.LastRequest, view.ReceiptId, view.Ticket))

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
        self.assertFalse(view.Enabled); self.assertEqual(0,view.Ticket)
        self.assertEqual(6, len(self.sent))

    def test_new_peer_during_nonfinite_clock_recovers_after_multiple_rate_windows(self):
        self.now = float("nan"); self.handshake()
        self.assertEqual([], self.sent); self.assertTrue(self.rpc.m_Started)
        for tick in range(100, 110):
            self.now = float(tick)
            before = len(self.sent)
            self.receive(self.request(ticket=tick))
            self.assertEqual(before + 1, len(self.sent), tick)

    def test_clock_rollback_resets_tracked_admission_baselines(self):
        self.handshake()
        peer = self.rpc.m_Peers[0]
        peer.NextMutation = 103.  # Explicit synthetic pre-retirement peer state.
        writes = self.helper.store.calls
        self.now = 99.
        refused = self.mutate(2, 2)
        self.assertEqual(11, refused.Code)
        self.assertEqual((99., 99., 102.),
                         (self.rpc.m_GlobalWindow, peer.RateWindow, peer.NextMutation))
        self.assertEqual((1, 1), (self.rpc.m_GlobalCount, peer.RateCount))
        self.assertTrue(self.rpc.m_Started)
        self.assertEqual(writes, self.helper.store.calls)

    def test_reconnect_discards_old_peer_admission_state(self):
        first = self.handshake()
        self.rpc.m_Peers[0].NextMutation = 200.
        replacement = Handle(); sender = Sender("alice", replacement)
        replacement.GetIdentity = lambda: sender
        replacement.IsPlayerDisconnected = lambda: False
        view = self.receive(self.request(), sender)
        self.assertEqual(1, len(self.rpc.m_Peers))
        self.assertIs(replacement, self.rpc.m_Peers[0].Player)
        self.assertNotEqual(first.Session, view.Session)
        self.assertEqual(0, self.rpc.m_Peers[0].NextMutation)
        self.assertEqual(11, view.Code)

    def test_refusal_rate_limit_bounds_replies_without_any_quest_writes(self):
        before = copy.deepcopy(self.runtime.m_State)
        writes = self.helper.store.calls
        self.handshake()
        for _ in range(20): self.mutate()
        self.assertEqual(4, len(self.sent))
        self.now += 1
        self.assertEqual(11, self.mutate(2, 2).Code)
        self.assertEqual(5, len(self.sent))
        self.assertEqual(before, self.runtime.m_State)
        self.assertEqual(writes, self.helper.store.calls)

    def test_refusal_projection_never_reads_runtime_snapshot(self):
        self.runtime.Snapshot = lambda: self.fail("retired projection queried runtime")
        for _ in range(3):
            self.now += 2
            view = self.handshake()
            self.assertFalse(view.Enabled)
            self.assertEqual([], view.Rows)
            self.assertEqual("", self.rpc.Title(1))
        self.assertIsNone(self.rpc.m_ProjectionState)

    def test_durable_ids_beyond_32_are_never_projected_as_quest_slots(self):
        for boot in range(40):
            self.context.Session = "wire-boot-" + str(boot); self.context.Now = 0
            self.assertTrue(self.runtime.Start(self.helper.cfg, self.context, self.helper.store,
                                              self.helper.observer, self.helper.ai))
            self.runtime.Tick(self.context)
            self.assertEqual(0, self.runtime.Announce(self.helper.mission, self.context))
        durable_id = self.runtime.m_State.Director.Records[-1].Id
        self.assertGreater(durable_id, 32)
        view = self.handshake()
        self.assertEqual([], view.Rows)
        before = copy.deepcopy(self.runtime.m_State)
        self.assertEqual(11, self.mutate(event=1).Code)
        self.assertEqual(before, self.runtime.m_State)
        self.assertEqual(0, self.sent[-1][3].ReceiptEventId)

    def test_retired_payload_unread_and_other_rpc_or_missing_context_ignored(self):
        context = SimpleNamespace(Read=lambda: self.fail("retired payload deserialized"))
        before = copy.deepcopy(self.runtime.m_State)
        self.rpc.OnRPC(self.sender, None, 4853801, context)
        self.assertEqual(1, len(self.sent))
        self.assertEqual(11, self.sent[-1][3].Code)
        self.rpc.OnRPC(self.sender, None, 4853802, context)
        self.rpc.OnRPC(self.sender, None, 4853801, None)
        self.assertEqual(1, len(self.sent))
        self.assertEqual(before, self.runtime.m_State)

    def test_public_projection_has_no_accounts_private_positions_items_or_internal_refs(self):
        view = self.handshake()
        self.assertEqual([], view.Rows)
        self.assertNotIn("alice", repr(vars(view)))
        self.assertFalse(view.Enabled)
        view.Rows.Insert(SimpleNamespace(Progress=999))
        self.assertEqual([], self.handshake().Rows)
        self.assertEqual(0, self.runtime.m_State.Director.Records[0].Progress)

    def test_reconnect_new_handle_gets_new_wire_session_but_cannot_rejoin(self):
        original=self.handshake(); self.mutate(); self.now+=1
        replacement=Handle(); new_sender=Sender("alice",replacement)
        replacement.GetIdentity=lambda:new_sender; replacement.IsPlayerDisconnected=lambda:False
        replacement.IsUnconscious=lambda:False
        view=self.receive(self.request(),new_sender)
        self.assertNotEqual(original.Session,view.Session); self.assertEqual(0,view.LastRequest)
        self.assertEqual([], view.Rows)
        self.receive(self.request(1,2,1,original.Session,0),new_sender)
        self.assertEqual([],self.runtime.m_State.Director.Records[0].Participants)

    def test_disabled_or_faulted_runtime_returns_empty_disabled_view(self):
        self.handshake(); self.runtime.m_Ready=False; self.now+=1
        view=self.receive(self.request(ticket=2)); self.assertFalse(view.Enabled); self.assertEqual([],view.Rows)

    def test_disconnect_tick_releases_peer_and_membership(self):
        self.handshake()
        self.assertEqual(0, self.runtime.Join(1, self.player, self.context))
        self.assertEqual(["alice"], self.runtime.m_State.Director.Records[0].Participants)
        self.player.IsPlayerDisconnected=lambda:True
        self.rpc.Tick(); self.assertEqual([],self.rpc.m_Peers)
        self.assertEqual([],self.runtime.m_State.Director.Records[0].Participants)

    def test_unconscious_join_refused_without_side_effect(self):
        self.handshake(); self.player.IsUnconscious = lambda: True
        view = self.mutate()
        self.assertEqual(11, view.Code)
        self.assertEqual(0, view.ReceiptId)
        self.assertEqual([], self.runtime.m_State.Director.Records[0].Participants)

    def test_deleted_native_identity_is_pruned_before_next_authentication(self):
        self.handshake();self.mutate();self.rpc.m_Peers[0].Identity=None;self.now+=1
        view=self.receive(self.request(ticket=2))
        self.assertIsNotNone(view);self.assertEqual(1,len(self.rpc.m_Peers))
        self.assertEqual([], view.Rows)

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
