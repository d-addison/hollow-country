"""HC-34/LC-T409 walk port: authored Enforce over explicit SYNTHETIC fixtures.

No engine execution, pathfinding, replication or arrival is established here.
Spec/plan/task: use the existing HC-10 group and HC-34 survey, request each leg
in order, retain position-only arrival and restore patrol on terminal custody.
"""
import unittest
from types import SimpleNamespace as N
from tests.legacy.test_debug_map_layers import compile_authored
from tests.legacy.test_admin_test_kit import base_scope
from tests.legacy.test_group_server import EArray
from tests.legacy.test_hc_pickers_survey import PICKERS, ROOT, method

WALK = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIPickerWalk.c'
ADAPTER = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIScavengeAdapter.c'


def runner(path, cls, name, **extra):
    return compile_authored(path, cls, name, base_scope(array=EArray, **extra), modded=False,
                            fields=("Actor", "Survey", "LeaseId"), members=("HCLive", "HCFinishWalk"))


class PickerWalk(unittest.TestCase):
    def fixture(self, group_present=True):
        calls = []
        patrol = [(4, 0, 5), (8, 0, 9)]
        group = N(points=EArray(patrol), behavior=7)
        def clear():
            calls.append(('clear',))
            group.points.clear()
        group.ClearWaypoints = clear
        group.AddWaypoint = lambda p: (calls.append(('add', p)), group.points.append(p))
        group.GetWaypoints = lambda: group.points
        group.GetWaypointBehaviour = lambda: group.behavior
        def behavior(value):
            calls.append(('behavior', value))
            group.behavior = value
        group.SetWaypointBehaviour = behavior
        actor = N(GetGroup=lambda: group if group_present else None, GetIdentity=lambda: None)
        route = N(HomeIndex=0, SourceIndex=2, Waypoints=EArray())
        raw = [(10, 0, 10), (20, 0, 10), (20, 0, 20), (10, 0, 20)]
        route.Waypoints.extend(N(HCPosition=lambda p=p: p) for p in raw)
        legs = method('HCPickerRoute', 'HCLegPoints', fields=('Waypoints','HomeIndex','SourceIndex'))
        route.HCLegPoints = lambda returning, points: legs(route, returning, points)
        identity = N(HCRouteId=lambda: 'route:synthetic')
        port = N(Defaults=N(PartyCooldownSeconds=900), Actor=actor, Survey=N(MaxWaypoints=4, HCFind=lambda key: route), LeaseId='lease',
                 m_Group=None, m_PreviousPoints=EArray(), m_PreviousBehavior=0,
                 m_WalkRefusal='', HCLive=lambda: True)
        scope = dict(eAIBase=N(Cast=lambda value: value), eAIWaypointBehavior=N(ONCE=3),
                     HCWorldMaterializer=N(HCIdentity=lambda lease: identity),
                     HCAIPartyIdentity=N(HCValid=lambda value: value is identity),
                     HCServer=N(HCTickWork=lambda: N(HCTake=lambda cost: True)))
        self.assertTrue(WALK.exists(), 'HC-34 Expansion picker walk port is missing')
        for name in ('HCWalkRefusal', 'HCWalk', 'HCFinishWalk'):
            fn = runner(WALK, 'HCXAIPickerWalk', name, **scope)
            setattr(port, name, lambda *a, fn=fn: fn(port, *a))
        return port, group, calls, raw, patrol

    def test_exact_outbound_and_return_legs_then_restore_patrol(self):
        port, group, calls, raw, patrol = self.fixture()
        self.assertTrue(port.HCWalk(False))
        self.assertEqual(raw[1:3], group.points)
        self.assertEqual([('clear',), ('add',raw[1]), ('add',raw[2]), ('behavior',3)], calls)
        calls.clear()
        self.assertTrue(port.HCWalk(True))
        self.assertEqual([raw[3],raw[0]], group.points)
        self.assertEqual([('clear',), ('add',raw[3]), ('add',raw[0]), ('behavior',3)], calls)
        port.HCFinishWalk()
        self.assertEqual(patrol, group.points)
        self.assertEqual(7, group.behavior)
        calls.clear()
        port.HCFinishWalk()
        self.assertEqual([], calls, 'terminal cleanup must be idempotent')

    def test_terminal_checkpoint_restores_patrol_but_active_checkpoint_does_not(self):
        for phase, saved in (("leaving", True), ("returning", True), ("returned", True),
                             ("lost", True), ("quarantined", True), ("leaving", False)):
            with self.subTest(phase=phase, saved=saved):
                port, group, calls, raw, patrol = self.fixture()
                self.assertTrue(port.HCWalk(False))
                calls.clear()
                receipts = []
                trip = N(m_IO=port, m_Ready=True, HCLogTripBoundary=lambda saved: None,
                         m_State=N(Phase=phase, CargoOwner='source', NextTripAt=0),
                         m_Store=N(Save=lambda row: (receipts.append(row.NextTripAt), saved)[1]), HCLog=lambda: None)
                checkpoint = method('HCScavengeTrip', 'HCCheckpoint', members=('HCLog',))
                run = compile_authored(WALK, 'HCScavengeTrip', 'HCCheckpoint',
                                       base_scope(HCXAIPickerWalk=N(Cast=lambda io: io),
                                                  ExpansionStatic=N(GetTimestamp=lambda utc: 1000),
                                                  **{'super': N(HCCheckpoint=lambda: checkpoint(trip))}),
                                       modded=True, members=('HCLogTripBoundary',))
                self.assertEqual(saved, run(trip))
                self.assertEqual([1900 if phase in ('returned', 'lost', 'quarantined') else 0], receipts,
                                 'cooldown must be in the durable terminal image before save')
                terminal = phase in ('returned', 'lost', 'quarantined') or not saved
                self.assertEqual(patrol if terminal else raw[1:3], group.points)
                self.assertEqual(7 if terminal else 3, group.behavior)

    def test_clear_restores_patrol_before_releasing_inventory_handles(self):
        port, group, calls, _, patrol = self.fixture()
        self.assertTrue(port.HCWalk(False))
        released = []
        def base_clear():
            self.assertEqual(patrol, group.points)
            released.append(True)
        run = runner(WALK, 'HCXAIPickerWalk', 'HCClear',
                     **{'super': N(HCClear=base_clear)})
        run(port)
        self.assertEqual([True], released)
        self.assertIsNone(port.m_Group)

    def test_missing_group_names_refusal_and_never_commands_any_group(self):
        port, group, calls, _, _ = self.fixture(False)
        self.assertEqual('PICKER_ACTOR_GROUP_MISSING', port.HCWalkRefusal())
        self.assertFalse(port.HCWalk(False))
        self.assertEqual([], calls)

    def test_oversize_patrol_snapshot_declines_without_mutation(self):
        port, group, calls, _, _ = self.fixture()
        group.points.extend([(1,0,1)] * 4)
        self.assertFalse(port.HCWalk(False))
        self.assertEqual('PICKER_PATROL_WAYPOINT_CAP', port.HCWalkRefusal())
        self.assertEqual([], calls)

    def test_group_change_does_not_command_a_replacement_party(self):
        port, group, calls, _, patrol = self.fixture()
        self.assertTrue(port.HCWalk(False))
        port.Actor.GetGroup = lambda: N()
        calls.clear()
        self.assertFalse(port.HCWalk(True))
        self.assertEqual('PICKER_ACTOR_GROUP_CHANGED', port.HCWalkRefusal())
        self.assertEqual([], calls)
        port.HCFinishWalk()
        self.assertEqual(patrol, group.points)

    def test_arrival_is_real_position_with_survey_range_not_request_or_elapsed_time(self):
        positions = [(0,0,0)]
        port = N(HCLive=lambda: True, Actor=N(GetPosition=lambda: positions[0]),
                 Source=N(GetPosition=lambda: (8,0,0)), Home=N(GetPosition=lambda: (0,0,0)),
                 Survey=N(ArrivalRangeMeters=1), Defaults=N(TransferRangeMeters=2.5))
        vector = N(DistanceSq=lambda a,b: sum((x-y)**2 for x,y in zip(a,b)))
        at_source = method('HCScavengeInventory','HCAtSource', members=('HCLive',),
                           fields=('Actor','Source','Survey','Defaults'), vector=vector)
        at_home = method('HCScavengeInventory','HCAtHome', members=('HCLive',),
                         fields=('Actor','Home','Survey','Defaults'), vector=vector)
        self.assertFalse(at_source(port))
        positions[0] = (6,0,0)
        self.assertFalse(at_source(port))
        positions[0] = (7,0,0)
        self.assertTrue(at_source(port))
        self.assertFalse(at_home(port))
        positions[0] = (1,0,0)
        self.assertTrue(at_home(port))


class PickerBinding(unittest.TestCase):
    def test_provider_binds_once_and_waits_for_idle_without_replacing_active_port(self):
        calls, logs = [], []
        trip = N(m_Ready=True, m_Busy=False, m_State=N(Phase='leaving'), m_IO=object())
        module = N(m_Trip=trip, m_Survey=object(), HCLogProvider=lambda: None, m_ProviderLogged=True,
                   m_Danger=None, m_Houses=None)  # #144: the provider also receives danger memory + house port
        bind_port = method('HCPickers','HCBindProvider', members=('HCLogProvider',))
        module.HCBindProvider = lambda port: (calls.append(port), bind_port(module,port))[1]
        provider = N(Survey=None)
        worker = N(m_Enabled=True,m_Reported=False,m_Bound=False,m_Port=provider)
        run = runner(ADAPTER,'HCXAIScavengeAdapter','Step', HCPickers=N(Get=lambda: module),
                     Print=logs.append, HCServer=N(HCTickWork=lambda: N(HCTake=lambda cost: True)))
        original = trip.m_IO
        run(worker)
        self.assertIs(original, trip.m_IO)
        trip.m_State.Phase='idle'
        trip.m_Busy=True
        run(worker)
        self.assertIs(original, trip.m_IO)
        trip.m_Busy=False
        run(worker)
        self.assertIs(provider, trip.m_IO)
        self.assertIs(module.m_Survey, provider.Survey)
        count = len(calls)
        run(worker)
        self.assertEqual(count,len(calls))
        self.assertTrue(worker.m_Bound)
        self.assertTrue(any('walk=bound' in line for line in logs))

    def test_lifecycle_installs_and_closes_only_for_the_accepted_server_owner(self):
        effects = []
        adjunct = N(Open=lambda settings: effects.append('open'),
                    Step=lambda: effects.append('step'), Close=lambda: effects.append('close'))
        owner = N(m_HCPickerAdapter=None)
        active = [owner]
        scope = base_scope(this=owner, GetGame=lambda: N(IsServer=lambda: True),
                           HCXAIService=N(Adapter=lambda: active[0]),
                           HCXAIScavengeAdapter=lambda: adjunct,
                           **{'super': N(OnStart=lambda settings: effects.append('base_start'),
                                         OnTick=lambda delta: effects.append('base_tick'),
                                         OnStop=lambda: effects.append('base_stop'))})
        functions = {name: compile_authored(ADAPTER,'HCXAIAdapter',name,scope,modded=True)
                     for name in ('OnStart','OnTick','OnStop')}
        functions['OnStart'](owner,N(EnableEncounters=True))
        functions['OnTick'](owner,1.0)
        functions['OnStop'](owner)
        self.assertEqual(['base_start','open','step','base_tick','step','close','base_stop'],effects)
        self.assertIsNone(owner.m_HCPickerAdapter)
        effects.clear()
        active[0] = object()
        functions['OnStart'](owner,N(EnableEncounters=True))
        functions['OnTick'](owner,1.0)
        functions['OnStop'](owner)
        self.assertEqual(['base_start','base_tick','base_stop'],effects)

    def test_missing_group_refuses_before_journal_leave(self):
        effects=[]
        port=N(HCBindSurveyed=lambda *a: True, HCWalkRefusal=lambda: 'PICKER_ACTOR_GROUP_MISSING',
               HCClear=lambda: effects.append('clear'))
        module=N(m_Trip=N(m_IO=port,m_Ready=True,m_Busy=False,m_State=N(Phase='idle'),
                         HCLeave=lambda *a: effects.append('leave')),
                 m_Survey=N(HCFind=lambda key: object()), HCPublishReadiness=lambda: None,
                 m_Units=N(HCReset=lambda n: None,HCTake=lambda n: True), m_RunsOn=False)
        run=method('HCPickers','HCBeginSurveyed',members=('HCPublishReadiness',),
                   HCAIPartyIdentity=N(HCValid=lambda i: True))
        self.assertEqual('PICKER_ACTOR_GROUP_MISSING',run(module,N(HCRouteId=lambda:'route'),'lease',object()))
        self.assertEqual(['clear'],effects)

    def test_stale_refusal_is_gone_and_lifecycle_is_owner_guarded(self):
        text=ADAPTER.read_text()
        self.assertNotIn('PROVIDER_SOURCE_MISSING_ROUTE_UNSURVEYED',text)
        self.assertIn('modded class HCXAIAdapter',text)
        self.assertIn('super.OnStart(settings)',text)
        self.assertIn('HCXAIService.Adapter() == this',text)
        self.assertNotIn('SetPosition(', WALK.read_text() if WALK.exists() else '')


if __name__ == '__main__':
    unittest.main()
