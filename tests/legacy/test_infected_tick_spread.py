"""Infected tick spreading on explicit synthetic fixtures.

Runs translated authored bodies (OnTick, SaveAdoptionBoundary) with mocked
store/clock collaborators. It never measures DayZ tick time, native AI paths
or native persistence behaviour.
"""
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from tests.legacy import test_infected_admission as admission_tests
from tests.legacy.test_infected_contract import policy_functions

SOURCE = admission_tests.SOURCE
module_call = admission_tests.module_call
Recorder = admission_tests.Recorder


def onstart_schedule(interval):
    """Evaluate the authored OnStart first-save/first-adopt assignments."""
    module = (SOURCE / "HCInfectedModule.c").read_text()
    start = module.split("override void OnStart(", 1)[1].split("protected void Quarantine(", 1)[0]
    values = {}
    for name in ("m_NextSave", "m_NextAdopt"):
        expression = re.findall(r"\b" + name + r" = ([^;]+);", start)[-1]
        expression = expression.replace("m_Config.SaveIntervalSeconds", str(interval)).replace(" / ", " // ")
        values[name] = eval(expression, {})
    return values


class InfectedSaveAdoptStagger(unittest.TestCase):
    def context(self, rec, interval=60):
        fixtures = admission_tests.UnqualifiedPathsPerformNoMutation("test_adoption_tick_still_defers_to_admission_inside_try_adopt")
        ctx = fixtures.tick_context(rec)
        ctx.m_Config.SaveIntervalSeconds = interval
        ctx.m_MemberCap = 24
        ctx.m_GroupCap = 2
        ctx.m_Dirty = True
        ctx.m_NextSave, ctx.m_NextAdopt = (lambda s: (s["m_NextSave"], s["m_NextAdopt"]))(onstart_schedule(interval))
        self.store = NS(Save=lambda *a: rec.events.append(("save", ctx.m_Now)) or True)

        def adopt(nowUtc):
            # Only the first adoption finds candidates and writes a boundary.
            rec.events.append(("adopt", ctx.m_Now))
            if [kind for kind, _ in rec.events].count("adopt") > 1:
                return
            module_call("protected bool SaveAdoptionBoundary(", ctx, "prepare", HCInfectedStore=NS(
                Save=lambda *a: rec.events.append(("boundary", ctx.m_Now)) or True))
        ctx.TryAdopt = adopt
        return ctx

    def tick(self, ctx, rec, utc):
        module_call("override void OnTick(", ctx, 1.0,
            GetGame=lambda: NS(IsServer=lambda: True), HCInfectedClock=NS(UtcSeconds=lambda: utc),
            HCNativeInfectedPack=NS(RetryPendingReleases=lambda: None), HCInfectedRoomCatalog=NS(BeginTick=lambda: None),
            HCHordeRecovery=NS(Reconcile=lambda *a: False),
            HCInfectedPolicy=NS(NextAdoptionCursor=lambda i, n: (i + 1) % n),
            HCInfectedStore=self.store)

    def test_onstart_offsets_first_save_by_half_the_interval(self):
        for interval in (30, 60, 61, 300):
            with self.subTest(interval=interval):
                schedule = onstart_schedule(interval)
                self.assertEqual(interval, schedule["m_NextAdopt"])
                self.assertEqual(interval + interval // 2, schedule["m_NextSave"])

    def test_periodic_save_never_shares_a_tick_with_adoption(self):
        rec = Recorder()
        ctx = self.context(rec)
        for utc in range(1, 400):
            ctx.m_Dirty = True
            self.tick(ctx, rec, utc)
        adopts = [t for kind, t in rec.events if kind == "adopt"]
        saves = [t for kind, t in rec.events if kind == "save"]
        self.assertEqual([60, 120, 180, 240, 300, 360], adopts)
        self.assertEqual([60], [t for kind, t in rec.events if kind == "boundary"])
        self.assertEqual([150, 210, 270, 330, 390], saves)
        self.assertEqual(set(), set(adopts) & set(saves))
        for save in saves:
            self.assertEqual(30, save % 60, saves)

    def test_due_save_on_an_adoption_tick_moves_to_the_next_tick(self):
        rec = Recorder()
        ctx = self.context(rec)
        ctx.m_NextAdopt = 0
        ctx.m_NextSave = 0
        ctx.TryAdopt = lambda nowUtc: rec.events.append(("adopt", ctx.m_Now))
        self.tick(ctx, rec, 10)
        self.assertEqual([("adopt", 10)], rec.events)
        self.assertTrue(ctx.m_Dirty)
        self.tick(ctx, rec, 11)
        self.assertEqual([("adopt", 10), ("save", 11)], rec.events)
        self.assertFalse(ctx.m_Dirty)

    def test_adoption_boundary_rearms_the_save_half_an_interval_off(self):
        rec = Recorder()
        ctx = self.context(rec)
        ctx.m_Now = 120
        self.assertTrue(module_call("protected bool SaveAdoptionBoundary(", ctx, "outcome",
            HCInfectedStore=NS(Save=lambda *a: True)))
        self.assertEqual(210, ctx.m_NextSave)
        self.assertFalse(ctx.m_Dirty)


# Enforce `out` arguments have no Python equivalent; rewrite those calls to an
# assignment expression so the mocked native returns the sampled value or None.
OUT_CALL = re.compile(r"((?:\w+(?:\(\))?\.)?(?:Reachable|SampleNavmeshPosition|BuildOrder))\(([^\n]*?), (\w+)\)(?=[);])")
PACK_BOUND = ("Reachable", "InitFilter", "GetAIWorld", "ActivateWaypoint", "Release", "ExtendRoute")
PACK_FIELDS = ("Group", "RouteEnd", "RoutePurpose", "RouteResult", "RoutePlanned", "RouteCompleted")


class Rooms(admission_tests.Array):
    def RemoveOrdered(self, index): del self[index]


def pack_method(signature, **namespace):
    text = OUT_CALL.sub(r"HCOut(\3 := \1(\2))", (SOURCE / "HCInfectedNavigation.c").read_text())
    saved = admission_tests.SOURCE
    with tempfile.TemporaryDirectory() as folder:
        Path(folder, "HCInfectedNavigation.c").write_text(text)
        admission_tests.SOURCE = Path(folder)
        try:
            return admission_tests.translate("HCInfectedNavigation.c", signature, PACK_BOUND, fields=PACK_FIELDS,
                HCOut=lambda value: value is not None,
                BehaviourGroupInfectedPackWaypointParams=lambda: (lambda c, r: NS(m_CenterPosition=c, m_Radius=r)),
                vector=NS(DistanceSq=lambda a, b: sum((x - y) ** 2 for x, y in zip(a, b))),
                **namespace)
        finally:
            admission_tests.SOURCE = saved


class InfectedRouteBudget(unittest.TestCase):
    """At most one route FindPath per module tick; queued rooms wait a tick."""

    def pack(self):
        paths = []
        pack = NS(m_Releasing=False, m_Members=admission_tests.Array(), m_Filter=None, m_RoutePlan=None,
            m_Search=False, m_Expires=0, m_LastProgress=0, m_LastPosition=None, m_BestRouteDistanceSq=-1,
            Group=None, RouteEnd=None, RoutePurpose=0, RouteResult=0, RoutePlanned=0, RouteCompleted=0,
            m_PendingRooms=None, m_PendingFrom=None, paths=paths, released=[], activated=[])
        unreachable = []

        def reachable(start, desired, segment):
            paths.append(desired)
            if desired in unreachable:
                return None
            return desired
        pack.unreachable = unreachable
        pack.Reachable = reachable
        pack.InitFilter = lambda: None
        pack.ActivateWaypoint = lambda now: pack.activated.append(pack.RouteCompleted) or True
        pack.Release = lambda: pack.released.append(True) or True
        group = NS(AddAgent=lambda agent: setattr(agent, "group", group), RemoveAgent=lambda agent: None,
            GetBehaviour=lambda: "behaviour")
        pack.GetAIWorld = lambda: NS(SampleNavmeshPosition=lambda position, radius, nav_filter: position,
            CreateGroup=lambda name: group)
        pack.ExtendRoute = lambda: pack_method("bool ExtendRoute(")(pack)
        return pack

    def actor(self):
        agent = NS(group=None)
        agent.GetGroup = lambda: agent.group
        entity = NS(IsAlive=lambda: True, GetAIAgent=lambda: agent, GetMindStateSynced=lambda: 0,
            GetPosition=lambda: (0.0, 0.0, 0.0), GetHealth=lambda zone, kind: 100)
        return NS(InfectedEntity=entity, SearchAnchorLimit=3, Profile="native")

    def start(self, pack, rooms):
        start = pack_method("bool Start(", s_PendingRelease=admission_tests.Array(),
            GetGame=lambda: NS(IsServer=lambda: True, ConfigIsExisting=lambda path: True),
            HCInfectedRoomCatalog=NS(BuildOrder=lambda destination, budget: Rooms(rooms)),
            BehaviourGroupInfectedPack=NS(Cast=lambda behaviour: behaviour),
            DayZInfectedConstants=NS(MINDSTATE_CHASE=3, MINDSTATE_FIGHT=4))
        return start(pack, admission_tests.Array([self.actor()]), (4.0, 0.0, 0.0), True, 10.0, 25.0)

    def test_search_start_spends_one_path_and_queues_surveyed_rooms(self):
        pack = self.pack()
        self.assertTrue(self.start(pack, [(4.0, 0.0, 6.0), (4.0, 0.0, 9.0)]))
        self.assertEqual([(4.0, 0.0, 0.0)], pack.paths)
        self.assertEqual(1, pack.RoutePlanned)
        self.assertEqual([(4.0, 0.0, 6.0), (4.0, 0.0, 9.0)], list(pack.m_PendingRooms))

    def test_extend_route_spends_at_most_one_path_per_call(self):
        pack = self.pack()
        self.assertTrue(self.start(pack, [(4.0, 0.0, 0.5), (4.0, 0.0, 6.0), (4.0, 0.0, 9.0)]))
        del pack.paths[:]
        pack.unreachable.append((4.0, 0.0, 9.0))
        self.assertTrue(pack.ExtendRoute())
        self.assertEqual([(4.0, 0.0, 6.0)], pack.paths)
        self.assertEqual(2, pack.RoutePlanned)
        self.assertEqual(2, pack.RoutePurpose)
        self.assertEqual((4.0, 0.0, 6.0), pack.RouteEnd)
        self.assertTrue(pack.ExtendRoute())
        self.assertEqual([(4.0, 0.0, 6.0), (4.0, 0.0, 9.0)], pack.paths)
        self.assertEqual(2, pack.RoutePlanned)
        self.assertFalse(pack.ExtendRoute())
        self.assertEqual(2, len(pack.paths))
        pack.m_Releasing = True
        pack.m_PendingRooms.Insert((4.0, 0.0, 12.0))
        self.assertFalse(pack.ExtendRoute())
        self.assertEqual(2, len(pack.paths))

    def test_reached_point_holds_while_rooms_wait_for_their_path(self):
        pack = self.pack()
        self.assertTrue(self.start(pack, [(4.0, 0.0, 6.0)]))
        member = NS(IsAlive=lambda: True, GetMindStateSynced=lambda: 0, GetHealth=lambda zone, kind: 100,
            GetPosition=lambda: (4.0, 0.0, 0.0))
        member.GetAIAgent = lambda: NS(GetGroup=lambda: pack.Group)
        pack.m_Members = admission_tests.Array([member])
        tick = pack_method("bool Tick(float now)", HCInfectedPolicy=NS(**policy_functions()),
            HCInfectedStore=NS(ValidPosition=lambda position: True), DayZInfectedConstants=NS(MINDSTATE_CHASE=3, MINDSTATE_FIGHT=4))
        self.assertTrue(tick(pack, 12.0))
        self.assertEqual((1, 0), (pack.RouteResult, pack.RouteCompleted))
        self.assertEqual([], pack.released)
        self.assertTrue(pack.ExtendRoute())
        self.assertTrue(tick(pack, 13.0))
        self.assertEqual((1, 1), (pack.RouteResult, pack.RouteCompleted))
        self.assertEqual([0, 1], pack.activated)

    def test_reached_final_point_releases_when_no_room_is_queued(self):
        pack = self.pack()
        self.assertTrue(self.start(pack, []))
        member = NS(IsAlive=lambda: True, GetMindStateSynced=lambda: 0, GetHealth=lambda zone, kind: 100,
            GetPosition=lambda: (4.0, 0.0, 0.0))
        member.GetAIAgent = lambda: NS(GetGroup=lambda: pack.Group)
        pack.m_Members = admission_tests.Array([member])
        tick = pack_method("bool Tick(float now)", HCInfectedPolicy=NS(**policy_functions()),
            HCInfectedStore=NS(ValidPosition=lambda position: True), DayZInfectedConstants=NS(MINDSTATE_CHASE=3, MINDSTATE_FIGHT=4))
        self.assertFalse(tick(pack, 12.0))
        self.assertEqual([True], pack.released)

    def investigator_tick(self, adoption_due):
        rec = Recorder()
        fixtures = admission_tests.UnqualifiedPathsPerformNoMutation("test_adoption_tick_still_defers_to_admission_inside_try_adopt")
        ctx = fixtures.tick_context(rec)
        extended = []
        investigators = admission_tests.Array()
        for index in range(2):
            pack = NS(Tick=lambda now: True, ExtendRoute=lambda index=index: extended.append(index) or True)
            investigators.Insert(NS(SearchPack=pack))
        ctx.m_Investigators = investigators
        if adoption_due:
            ctx.m_NextAdopt = 0
        module_call("override void OnTick(", ctx, 1.0,
            GetGame=lambda: NS(IsServer=lambda: True), HCInfectedClock=NS(UtcSeconds=lambda: 100),
            HCNativeInfectedPack=NS(RetryPendingReleases=lambda: None), HCInfectedRoomCatalog=NS(BeginTick=lambda: None),
            HCHordeRecovery=NS(Reconcile=lambda *a: False),
            HCInfectedPolicy=NS(NextAdoptionCursor=lambda i, n: (i + 1) % n),
            HCInfectedStore=NS(Save=lambda *a: True))
        return ctx, rec, extended

    def test_one_queued_room_path_per_module_tick_spends_the_route_token(self):
        ctx, rec, extended = self.investigator_tick(False)
        self.assertEqual(1, len(extended))
        self.assertEqual(0, ctx.m_RoutesRemaining)

    def test_adoption_tick_defers_queued_room_paths(self):
        ctx, rec, extended = self.investigator_tick(True)
        self.assertEqual([], extended)
        self.assertEqual(["adopt"], rec.events)


if __name__ == '__main__':
    unittest.main()
