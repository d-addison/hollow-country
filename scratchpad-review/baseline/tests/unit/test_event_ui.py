"""Authored event client/menu decisions with explicit synthetic native widgets."""
import copy
import json
import re
from types import SimpleNamespace
import unittest
from tests.unit import test_event_runtime as event_runtime
from tests.unit.test_event_transport import methods, Handle, ROOT, translate
from tests.unit.test_group_server import EArray
from tests.unit import test_event_transport as event_transport


class EventClientTests(unittest.TestCase):
    def setUp(self):
        self.e=event_runtime.environment(); self.now=100.; self.sent=[]; self.player=Handle()
        self.e["GetGame"]=lambda:SimpleNamespace(IsServer=lambda:False,GetTickTime=lambda:self.now,GetPlayer=lambda:self.player)
        self.e["PlayerBase"]=SimpleNamespace(Cast=lambda value:value)
        self.e["HCEventWireCodec"]=SimpleNamespace(CloneView=copy.deepcopy,CloneRequest=copy.deepcopy)
        self.e["DayZGame"]=SimpleNamespace(Event_OnRPC=SimpleNamespace(Insert=lambda fn:None,Remove=lambda fn:None))
        test=self
        class NativeRPC:
            def Write(self,value): self.value=copy.deepcopy(value)
            def Send(self,target,kind,guaranteed): test.sent.append(self.value)
        self.e["HCEventSyntheticRPC"]=NativeRPC
        cls=methods(ROOT/"5_Mission/Events/HCEventClient.c",self.e)
        self.client=cls()
        defaults=dict(m_View=None,m_Pending=None,m_LocalPlayer=self.player,m_Session="",m_Sequence=0,
            m_Floor=0,m_TicketCounter=0,m_BrowseTicket=0,m_ReceivedAt=0.,m_LastSend=0.,m_NextBrowse=0.,
            m_Retries=0,m_Listening=True,m_Browsing=True,m_Notice="",m_LastClock=100.)
        for key,value in defaults.items():setattr(self.client,key,value)

    def frame(self,session="wire-a",seq=1,floor=0,ticket=None):
        view=self.e["HCEventPublicView"](); view.Session=session; view.Sequence=seq; view.Enabled=True
        view.Ticket=self.client.m_BrowseTicket if ticket is None else ticket; view.LastRequest=floor
        if floor: view.ReceiptId=floor; view.ReceiptOp=1; view.ReceiptEventId=1
        row=self.e["HCEventPublicRow"](); row.EventId=1; row.Revision=2; row.Family=1
        row.Title="Supply recovery"; row.Status=1; row.Goal=1; row.MaxParticipants=6; row.RemainingSeconds=300
        view.Rows.Insert(row); return view

    def ready(self):
        self.assertTrue(self.client.Browse()); self.assertTrue(self.client.Receive(self.frame()))

    def test_browse_ticket_and_snapshot_floor_not_mutation_ack(self):
        self.ready(); self.assertTrue(self.client.Send(1,1)); pending=copy.deepcopy(self.client.m_Pending)
        self.now+=7; self.client.Update(); self.now+=3; self.client.Update(); self.now+=3; self.client.Update()
        self.assertNotEqual(0,self.client.m_BrowseTicket)
        self.assertTrue(self.client.Receive(self.frame(seq=2,floor=0)))
        self.assertEqual(pending,self.client.m_Pending)

    def test_exact_receipt_ack_and_immutable_pending_wire_request(self):
        self.ready(); self.assertTrue(self.client.Send(1,1))
        self.sent[-1].EventId=32; self.assertEqual(1,self.client.m_Pending.EventId)
        frame=self.frame(seq=2,floor=1,ticket=0); frame.Rows[0].Joined=True;frame.Rows[0].Participants=1
        self.assertTrue(self.client.Receive(frame)); self.assertIsNone(self.client.m_Pending)
        self.assertEqual(1,self.client.m_Floor); self.assertTrue(self.client.GetView().Rows[0].Joined)

    def test_browse_blocks_mutation_until_handshake_finishes(self):
        self.ready(); self.assertTrue(self.client.Browse()); self.assertFalse(self.client.Send(1,1))

    def test_retries_reuse_exact_mutation_and_stop_after_bound(self):
        self.ready(); self.assertTrue(self.client.Send(1,1)); original=copy.deepcopy(self.client.m_Pending)
        for now in (103.,106.,109.,112.,115.):self.now=now;self.client.Update()
        mutations=[r for r in self.sent if r.Op==1]
        self.assertEqual(3,len(mutations)); self.assertTrue(all(r==original for r in mutations))
        self.assertTrue(self.client.IsBusy())

    def test_late_browse_or_reply_cannot_rewind_floor_or_clear_new_pending(self):
        self.ready(); self.client.Send(1,1)
        self.assertTrue(self.client.Receive(self.frame(seq=2,floor=1,ticket=0)))
        self.client.m_View.Rows[0].Joined=True; self.assertTrue(self.client.Send(2,1))
        pending=copy.deepcopy(self.client.m_Pending)
        self.assertFalse(self.client.Receive(self.frame(seq=1,floor=0,ticket=1)))
        self.assertFalse(self.client.Receive(self.frame(seq=3,floor=0,ticket=0)))
        self.assertEqual(pending,self.client.m_Pending); self.assertEqual(1,self.client.m_Floor)

    def test_session_change_requires_current_browse_and_never_replays_old_intent(self):
        self.ready(); self.client.Send(1,1)
        self.assertFalse(self.client.Receive(self.frame("wire-b",seq=1,floor=0,ticket=0)))
        self.client.m_Retries=2; self.now=110.; self.client.Update()
        self.assertTrue(self.client.Receive(self.frame("wire-b",seq=1,floor=0)))
        self.assertIsNone(self.client.m_Pending); self.assertEqual("wire-b",self.client.m_Session)
        self.assertIn("unconfirmed",self.client.GetNotice().lower())

    def test_new_player_clears_view_pending_without_reusing_browse_ticket(self):
        self.ready(); old_ticket=self.client.m_TicketCounter; self.client.Send(1,1)
        self.player=Handle(); self.client.Update()
        self.assertIsNone(self.client.m_View); self.assertIsNone(self.client.m_Pending)
        self.assertGreater(self.client.m_TicketCounter,old_ticket)

    def test_malformed_views_never_publish(self):
        self.ready()
        for key,value in (("Version",2),("Session","x"*129),("Sequence",1000000001),
                          ("LastRequest",-1),("ReceiptId",1),("Code",12)):
            frame=self.frame(seq=2,ticket=0); setattr(frame,key,value)
            self.assertFalse(self.client.Receive(frame),key)
        frame=self.frame(seq=2,ticket=0); frame.Rows.Insert(copy.deepcopy(frame.Rows[0]))
        self.assertFalse(self.client.Receive(frame))

    def test_disabled_empty_snapshot_purges_stale_joinable_rows(self):
        self.ready(); frame=self.frame(seq=2,ticket=0); frame.Enabled=False; frame.Rows.Clear();frame.Code=11
        self.assertTrue(self.client.Receive(frame)); self.assertFalse(self.client.Send(1,1))
        self.assertEqual([],self.client.GetView().Rows)

    def test_snapshots_detached_and_stale_view_disables_new_mutations(self):
        self.ready(); view=self.client.GetView(); view.Rows[0].EventId=32
        self.assertEqual(1,self.client.GetView().Rows[0].EventId)
        self.now=116.; self.assertFalse(self.client.Send(1,1));self.assertFalse(self.client.Fresh())

    def test_wrong_native_sender_or_target_rejected(self):
        self.client.Browse(); frame=self.frame()
        context=SimpleNamespace(Read=lambda:frame)
        self.client.OnRPC(SimpleNamespace(),self.player,4853802,context)
        self.client.OnRPC(None,Handle(),4853802,context)
        self.assertIsNone(self.client.m_View)
        self.client.OnRPC(None,self.player,4853802,context);self.assertIsNotNone(self.client.m_View)

    def test_receipt_counter_ahead_cannot_leave_client_permanently_busy(self):
        self.ready();self.client.Send(1,1)
        frame=self.frame(seq=2,floor=2,ticket=0);frame.ReceiptEventId=2
        self.assertTrue(self.client.Receive(frame));self.assertFalse(self.client.IsBusy())
        self.assertIn("unconfirmed",self.client.GetNotice().lower());self.assertEqual(2,self.client.m_Floor)

    def test_closing_browser_cancels_unneeded_polling_but_preserves_pending_intent(self):
        self.ready();self.client.Browse();before=len(self.sent);self.client.SetBrowsing(False)
        self.now=110.;self.client.Update();self.assertEqual(before,len(self.sent))
        self.assertEqual(0,self.client.m_BrowseTicket)
        self.client.Send(1,1);pending=copy.deepcopy(self.client.m_Pending)
        self.client.SetBrowsing(False);self.assertEqual(pending,self.client.m_Pending)

    def test_inconsistent_membership_and_completion_projection_refused(self):
        self.ready()
        for updates in ({"Joined":True,"Participants":0},{"Status":4,"Progress":0,"RemainingSeconds":0},
                        {"Status":2,"Progress":1}):
            frame=self.frame(seq=2,ticket=0)
            for key,value in updates.items():setattr(frame.Rows[0],key,value)
            self.assertFalse(self.client.Receive(frame),updates)

    def test_equal_counter_different_receipt_clears_as_unconfirmed_not_success(self):
        self.ready();self.client.Send(1,1)
        frame=self.frame(seq=2,floor=1,ticket=0);frame.ReceiptOp=2
        self.assertTrue(self.client.Receive(frame));self.assertFalse(self.client.IsBusy())
        self.assertIn("unconfirmed",self.client.GetNotice().lower())
        self.assertEqual(1,self.client.m_Floor)


class NativeWidget:
    def __init__(self):self.rows=[];self.selected=-1;self.enabled=True;self.text="";self.destroyed=False;self.children={}
    def FindAnyWidget(self,name):return self.children.get(name)
    def ClearItems(self):self.rows.clear();self.selected=-1
    def AddItem(self,text,data,column):self.rows.append(text);return len(self.rows)-1
    def GetSelectedRow(self):return self.selected
    def SelectRow(self,row):self.selected=row
    def SetText(self,text):self.text=text
    def Enable(self,value):self.enabled=value
    def Unlink(self):self.destroyed=True


def menu_source(path):
    source=path.read_text()
    for typ in ("TextListboxWidget","ButtonWidget","TextWidget","Widget","UAInput","UIScriptedMenu"):
        source=re.sub(r"\b"+typ+r"\b","HCEventNative"+typ,source)
    source=re.sub(r"\blayoutRoot\b","m_Layout",source)
    source=source.replace("super.","native_super_")
    return SimpleNamespace(read_text=lambda:source,stem=path.stem)


class EventMenuTests(unittest.TestCase):
    def setUp(self):
        helper=EventClientTests();helper.setUp();helper.ready()
        self.helper=helper;self.e=helper.e;self.client=helper.client;self.calls=[]
        self.root=NativeWidget()
        for name in ("HCEventRows","HCEventStatus","HCEventDetail","HCEventJoin","HCEventLeave","HCEventRefresh","HCEventClose"):
            self.root.children[name]=NativeWidget()
        self.client.m_Browsing=False
        self.e["HCEventClient"]=SimpleNamespace(Get=lambda:self.client)
        self.e["GetGame"]=lambda:SimpleNamespace(GetWorkspace=lambda:SimpleNamespace(CreateWidgets=lambda path:self.root),
            GetPlayer=lambda:helper.player,IsServer=lambda:False,GetTickTime=lambda:helper.now)
        helper.player.IsUnconscious=lambda:False
        for typ in ("TextListboxWidget","ButtonWidget","TextWidget","Widget"):
            self.e["HCEventNative"+typ]=SimpleNamespace(Cast=lambda value:value)
        self.e["GetUApi"]=lambda:SimpleNamespace(GetInputByName=lambda name:SimpleNamespace(LocalPress=lambda:False))
        self.e["native_super_OnShow"]=lambda:self.calls.append("show")
        self.e["native_super_OnHide"]=lambda:self.calls.append("hide")
        self.e["native_super_Update"]=lambda dt:self.calls.append("update")
        self.e["native_super_OnClick"]=lambda *args:False
        self.e["Close"]=lambda:self.calls.append("close")
        path=ROOT/"5_Mission/Events/HCEventMenu.c"
        cls=methods(menu_source(path),self.e)
        self.menu=cls()
        for key,value in dict(m_Layout=None,m_Rows=EArray(),m_Elapsed=0.,m_Opening=True,
            m_Sequence=0,m_Session="",m_List=None,m_Status=None,m_Detail=None,m_Join=None,
            m_Leave=None,m_Refresh=None,m_Close=None).items():setattr(self.menu,key,value)
        self.assertIs(self.root,self.menu.Init())

    def test_missing_required_widget_refuses_and_unlinks_layout(self):
        del self.root.children["HCEventRows"]
        self.assertIsNone(self.menu.Init());self.assertTrue(self.root.destroyed)

    def test_render_preserves_selection_by_event_id_and_bounds_indices(self):
        view=self.client.GetView();second=copy.deepcopy(view.Rows[0]);second.EventId=2;view.Rows.Insert(second)
        self.menu.Render(view);self.menu.m_List.selected=1
        view.Rows.reverse();self.menu.Render(view)
        self.assertEqual(2,self.menu.SelectedId());self.assertEqual(0,self.menu.m_List.selected)
        self.menu.m_List.selected=99;self.assertEqual(0,self.menu.SelectedId())

    def test_buttons_follow_authoritative_membership_and_terminal_state(self):
        self.menu.Render(self.client.GetView());self.menu.m_List.selected=0;self.menu.Controls()
        self.assertTrue(self.menu.m_Join.enabled);self.assertFalse(self.menu.m_Leave.enabled)
        self.client.m_View.Rows[0].Joined=True;self.menu.Controls()
        self.assertFalse(self.menu.m_Join.enabled);self.assertTrue(self.menu.m_Leave.enabled)
        self.client.m_View.Rows[0].Status=4;self.menu.Controls()
        self.assertFalse(self.menu.m_Join.enabled);self.assertFalse(self.menu.m_Leave.enabled)

    def test_click_sends_selected_event_only_and_never_autojoin_on_open_close(self):
        self.menu.OnShow();self.menu.OnHide()
        self.assertEqual([], [r for r in self.helper.sent if r.Op != 0])
        self.assertEqual(["show","hide"],self.calls)
        self.client.m_BrowseTicket=0;self.menu.Render(self.client.GetView());self.menu.m_List.selected=0
        self.assertTrue(self.menu.OnClick(self.menu.m_Join,0,0,0))
        self.assertEqual(1,self.helper.sent[-1].Op);self.assertEqual(1,self.helper.sent[-1].EventId)

    def test_cache_cadence_stale_view_and_dead_player_close(self):
        self.menu.Update(.1);self.assertEqual([],self.menu.m_List.rows)
        self.menu.Update(.15);self.assertEqual(1,len(self.menu.m_List.rows))
        self.menu.m_List.selected=0;self.helper.now=116.;self.menu.Controls()
        self.assertFalse(self.menu.m_Join.enabled);self.assertIn("stale",self.menu.m_Status.text.lower())
        self.helper.player.alive=False;self.menu.Update(.25);self.assertIn("close",self.calls)

    def test_hide_clears_cached_rows_and_stops_browsing(self):
        self.menu.Render(self.client.GetView());self.menu.OnHide()
        self.assertEqual([],self.menu.m_Rows);self.assertEqual([],self.menu.m_List.rows)
        self.assertFalse(self.client.m_Browsing);self.assertEqual("hide",self.calls[-1])

    def test_actual_layout_binds_required_widgets_and_normalized_bounds(self):
        source=(ROOT.parent/"gui/layouts/hc_events.layout").read_text()
        names=[];root=NativeWidget()
        for match in re.finditer(r"\b\w+WidgetClass (\w+)\s*\{",source):
            names.append(match[1]);root.children[match[1]]=NativeWidget()
            content=event_runtime.body(source,match.end()).split("{",1)[0]
            position=re.search(r"\bposition ([0-9.]+) ([0-9.]+)",content)
            size=re.search(r"\bsize ([0-9.]+) ([0-9.]+)",content)
            self.assertIsNotNone(position);self.assertIsNotNone(size)
            x,y=map(float,position.groups());w,h=map(float,size.groups())
            self.assertGreater(w,0);self.assertGreater(h,0)
            self.assertLessEqual(x+w,1.000001);self.assertLessEqual(y+h,1.000001)
        self.assertEqual(len(names),len(set(names)))
        self.root=root;self.assertIs(root,self.menu.Init())


class EventAuthoredRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.server=event_transport.EventTransportTests();self.server.setUp()
        self.client=EventClientTests();self.client.setUp()

    def deliver(self,view):
        self.client.client.OnRPC(None,self.client.player,4853802,SimpleNamespace(Read=lambda:copy.deepcopy(view)))

    def browse(self):
        self.client.client.Browse();view=self.server.receive(self.client.sent[-1]);self.deliver(view)

    def test_lost_reply_retry_receipt_completes_without_double_join_then_leave(self):
        self.browse();self.assertTrue(self.client.client.Send(1,1))
        self.server.receive(self.client.sent[-1]) # Deliberately drop acknowledgement.
        before=copy.deepcopy(self.server.runtime.m_State)
        self.client.now=103.;self.server.now=103.;self.client.client.Update()
        self.deliver(self.server.receive(self.client.sent[-1]))
        self.assertEqual(before,self.server.runtime.m_State)
        self.assertFalse(self.client.client.IsBusy());self.assertTrue(self.client.client.GetView().Rows[0].Joined)
        self.assertTrue(self.client.client.Send(2,1))
        self.deliver(self.server.receive(self.client.sent[-1]))
        self.assertEqual([],self.server.runtime.m_State.Director.Records[0].Participants)
        self.assertFalse(self.client.client.GetView().Rows[0].Joined)

    def test_delayed_initial_browse_does_not_rewind_after_mutation(self):
        self.client.client.Browse();old=self.server.receive(self.client.sent[-1]);self.deliver(old)
        self.client.client.Send(1,1);self.deliver(self.server.receive(self.client.sent[-1]))
        self.client.client.Send(2,1);pending=copy.deepcopy(self.client.client.m_Pending)
        self.deliver(old)
        self.assertEqual(pending,self.client.client.m_Pending);self.assertEqual(1,self.client.client.m_Floor)


class EventInputLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.e=event_runtime.environment();self.calls=[];self.server=False;self.blocked=False
        self.player=Handle();self.player.IsUnconscious=lambda:False
        self.current_menu=None;self.key=True;self.declared=True
        self.ui=SimpleNamespace(GetMenu=lambda:self.current_menu,
            EnterScriptedMenu=lambda menu,parent:self.calls.append(("enter",menu)),
            FindMenu=lambda menu:self.current_menu)
        self.e["GetGame"]=lambda:SimpleNamespace(IsServer=lambda:self.server,GetPlayer=lambda:self.player,GetUIManager=lambda:self.ui)
        self.e["GetUApi"]=lambda:SimpleNamespace(GetInputByName=lambda name:SimpleNamespace(LocalPress=lambda:self.key) if self.declared else None)
        self.e["IsControlDisabled"]=lambda:self.blocked
        self.client=SimpleNamespace(Start=lambda:self.calls.append(("start",)),
            Update=lambda:self.calls.append(("client-update",)),Stop=lambda:self.calls.append(("stop",)))
        self.e["HCEventClient"]=SimpleNamespace(Get=lambda:self.client)
        self.e["PlayerBase"]=SimpleNamespace(Cast=lambda obj:obj)
        self.e["native_super_OnInit"]=lambda:self.calls.append(("init",))
        self.e["native_super_OnUpdate"]=lambda dt:self.calls.append(("native-update",))
        self.e["native_super_OnMissionFinish"]=lambda:self.calls.append(("finish",))
        cls=methods(menu_source(ROOT/"5_Mission/Events/HCEventGameplay.c"),self.e)
        self.hook=cls();self.hook.m_HCEventClient=None;self.hook.OnInit()

    def test_declared_input_opens_own_menu_and_preserves_native_chain(self):
        self.hook.OnUpdate(.1)
        self.assertIn(("enter",48538),self.calls);self.assertEqual(1,self.calls.count(("native-update",)))
        self.assertEqual([("init",),("start",)],self.calls[:2])

    def test_existing_menu_blocked_controls_missing_input_and_dead_player_never_open(self):
        for key,value in (("current_menu",SimpleNamespace()),("blocked",True),("declared",False)):
            original=getattr(self,key);setattr(self,key,value);self.calls.clear();self.hook.OnUpdate(.1)
            self.assertFalse(any(call[0]=="enter" for call in self.calls));setattr(self,key,original)
        self.player.alive=False;self.calls.clear();self.hook.OnUpdate(.1)
        self.assertNotIn(("enter",48538),self.calls)

    def test_mission_finish_closes_own_menu_and_unsubscribes_before_native_finish(self):
        self.current_menu=SimpleNamespace(Close=lambda:self.calls.append(("close",)))
        self.hook.OnMissionFinish()
        self.assertEqual([("close",),("stop",),("finish",)],self.calls[-3:])

    def test_menu_factory_sets_own_id_and_preserves_unknown_menu_dispatch(self):
        source=menu_source(ROOT/"5_Mission/Events/HCEventMenuFactory.c")
        self.e["HCEventMenu"]=lambda:SimpleNamespace(SetID=lambda id:self.calls.append(("id",id)))
        self.e["native_super_CreateScriptedMenu"]=lambda id:("native",id)
        cls=methods(source,self.e);factory=cls()
        self.assertIsNotNone(factory.CreateScriptedMenu(48538));self.assertIn(("id",48538),self.calls)
        self.assertEqual(("native",42),factory.CreateScriptedMenu(42))


if __name__ == "__main__":unittest.main()
