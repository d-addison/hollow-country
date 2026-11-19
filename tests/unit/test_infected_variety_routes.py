"""#213 spec/plan/tasks: HC-46 corridors, native pack segments, bounded wake routes.
All ports below are synthetic; no native survey, motion or visibility evidence.
"""
from types import SimpleNamespace as N
import unittest
import tempfile
from pathlib import Path
from tests.unit.test_infected_variety_w56 import AREA
from tests.unit.test_infected_admission import Array, translate


class Vec(list):
    """Explicit synthetic vector operators; no native physics simulation."""
    def __add__(self, rhs): return Vec(a+b for a,b in zip(self, rhs))
    def __sub__(self, rhs): return Vec(a-b for a,b in zip(self, rhs))
    def __mul__(self, rhs): return Vec(a*rhs for a in self)


class VarietyRoutes(unittest.TestCase):
    def test_nearest_corridor_segment_is_selected_inside_range_only(self):
        path = AREA / 'HCInfectedVarietyRoutes.c'
        self.assertTrue(path.exists(), 'variety corridor consumer missing')
        fn = translate(str(path), 'static float HCSegmentFraction(', ())
        self.assertEqual(.5, fn(None, [5., 0., 2.], [0., 0., 0.], [10., 0., 0.]))
        self.assertEqual(0., fn(None, [-5., 0., 2.], [0., 0., 0.], [10., 0., 0.]))
        self.assertEqual(1., fn(None, [15., 0., 2.], [0., 0., 0.], [10., 0., 0.]))

    def test_select_clips_nearest_segment_and_enforces_range_length_and_opt_out(self):
        path = AREA / 'HCInfectedVarietyRoutes.c'
        fraction = translate(str(path), 'static float HCSegmentFraction(', ())
        route = N(Id='synthetic-corridor', Surveyed=True,
                  Nodes=Array([Vec([0.,0.,0.]), Vec([10.,0.,0.]), Vec([20.,0.,0.])]))
        state = N(s_Config=N(CorridorRangeMetres=3., MaxMigrationMetres=8.),
                  s_Routes=N(Enabled=True, Routes=Array([route]), Defaults=N()))
        dist = lambda a,b: sum((x-y)**2 for x,y in zip(a,b))
        select = translate(str(path), 'static HCHordeRouteSurvey HCSelect(',
                           ('HCSegmentFraction',), statics=tuple(vars(state)), STATICS=state,
                           vector=N(DistanceSq=dist, Distance=lambda a,b: dist(a,b)**.5),
                           HCHordeRouteSurvey=lambda: N(Id='', Nodes=Array()),
                           HCHordeRoutes=N(ValidSurvey=lambda r,c: r.Surveyed))
        owner = N(HCSegmentFraction=lambda *a: fraction(None, *a))
        picked = select(owner, Vec([5.,0.,2.]))
        self.assertEqual('synthetic-corridor', picked.Id)
        self.assertEqual([[5.,0.,0.], [10.,0.,0.]], picked.Nodes)
        self.assertIsNone(select(owner, Vec([5.,0.,4.])))
        state.s_Routes.Enabled = False
        self.assertIsNone(select(owner, Vec([5.,0.,2.])))
        state.s_Routes.Enabled, route.Surveyed = True, False
        self.assertIsNone(select(owner, Vec([5.,0.,2.])))

    def test_initial_segment_checks_native_reachability_before_group_start(self):
        path = AREA / 'HCInfectedVarietyRoutes.c'
        calls, reachable = [], [False]
        owner = N(InitFilter=lambda: None, Reachable=lambda *a: reachable[0],
                  Start=lambda *a: calls.append('native_start') or True)
        begin = translate(str(path), 'bool HCBegin(', ('InitFilter', 'Reachable', 'Start'))
        roster = Array([N(InfectedEntity=N(GetPosition=lambda: [0.,0.,0.]))])
        route = N(Nodes=Array([[10.,0.,0.]]))
        defaults = N(NativeSegmentMetres=120.)
        self.assertFalse(begin(owner, roster, route, defaults, 1., 60.))
        self.assertEqual([], calls)
        reachable[0] = True
        self.assertTrue(begin(owner, roster, route, defaults, 2., 60.))
        self.assertEqual(['native_start'], calls)
        self.assertEqual(1, owner.m_V2MemberCount)
        self.assertIs(route, owner.m_VarietyRoute)

    def test_segment_commit_requires_hidden_and_native_reachability_every_time(self):
        path = AREA / 'HCInfectedVarietyRoutes.c'
        self.assertTrue(path.exists(), 'variety corridor consumer missing')
        commits = []
        hidden, reachable = [False], [True]
        owner = N(m_VarietyRoute=N(Nodes=Array([[0.,0.,0.], [10.,0.,0.]])),
                  m_VarietyNode=0, m_V2MemberCount=1, m_VarietyDefaults=N(NativeSegmentMetres=120),
                  m_Members=Array([N(GetPosition=lambda: [0.,0.,0.])]),
                  Reachable=lambda *a: reachable[0],
                  V2CommitSegment=lambda *a: commits.append(a) or True)
        fn = translate(str(path), 'bool HCVarietyNextSegment(', ('Reachable', 'V2CommitSegment'),
                       HCInfectedVariety=N(HCHidden=lambda *a: hidden[0]),
                       HCHordeRoutes=N(Defaults=lambda: N(NativeSegmentMetres=120)),
                       HCPerfPlayers=N(HCGet=lambda: Array()))
        self.assertFalse(fn(owner, 1.))
        hidden[0], reachable[0] = True, False
        self.assertFalse(fn(owner, 2.))
        self.assertEqual([], commits)
        reachable[0] = True
        self.assertTrue(fn(owner, 3.))
        self.assertEqual(1, len(commits))
        self.assertEqual(1, owner.m_VarietyNode)

    def test_off_is_a_cheap_no_op_and_fallback_is_named_once(self):
        path = AREA / 'HCInfectedVarietyRoutes.c'
        state = N(s_Config=N(EnableMigration=False))
        # Syntax-only fixture: expand one-line braces for the restricted translator.
        with tempfile.TemporaryDirectory() as folder:
            fixture = Path(folder) / path.name
            fixture.write_text(path.read_text().replace(' { ', ' {\n '))
            step = translate(str(fixture), 'static void HCStep(', (), statics=tuple(vars(state)), STATICS=state)
        step(None, 1.)  # No server/native stubs: work would fail immediately.
        logs = []
        class SyntheticSite:
            Id = 'synthetic-authored'
            @property
            def Position(self):  # Enforce vectors copy by value on assignment.
                return Vec([10.,0.,0.])
        state = N(s_FallbackPrinted=False,
                  s_Config=N(MaxMigrationMetres=80., CorridorRangeMetres=80., ContextRange=4.,
                             Sites=Array([SyntheticSite()])))
        distance = lambda a,b: sum((x-y)**2 for x,y in zip(a,b))
        fallback = translate(str(path), 'static HCHordeRouteSurvey HCFallback(', (),
                             statics=tuple(vars(state)), STATICS=state, Print=logs.append,
                             HCHordeRouteSurvey=lambda: N(Id='', Nodes=Array()),
                             vector=N(DistanceSq=distance))
        for _ in range(2):
            result = fallback(None, Vec([0.,0.,0.]))
            self.assertEqual('synthetic-authored', result.Id)
            self.assertEqual([[14.,0.,0.]], result.Nodes)
        self.assertEqual(1, len(logs))
        self.assertIn('reason=no_corridor_in_range runtime=PENDING', logs[0])

    def test_roster_waits_for_group_wake_and_never_steals_native_owned_actors(self):
        path = AREA / 'HCInfectedVarietyRoutes.c'
        def actor(place='synthetic-place'):
            return N(GroupId=0, SearchPack=None, EverAssigned=False,
                     InfectedEntity=N(IsAlive=lambda: True, HCVarietyTriedDormant=lambda: True,
                       HCVarietyRouteTried=lambda: False, HCVarietyPlace=lambda: place,
                       HCVarietyDormant=lambda: False, GetMindStateSynced=lambda: 0,
                       GetPosition=lambda: [0., 0., 0.]))
        first, second = actor(), actor()
        owner = N(m_Healthy=True, m_Config=N(MaxTracked=24),
                  m_HCVarietyRouteCursor=0, m_Actors=Array([first, second]))
        roster = translate(str(path), 'array<HCInfectedActor> HCVarietyRouteRoster(', (),
                           HCInfectedVariety=N(HCConfig=lambda: N(GroupMembers=3, EnableMigration=True),
                             HCHidden=lambda *a: True),
                           HCPerfPlayers=N(HCGet=lambda: Array()),
                           DayZInfectedConstants=N(MINDSTATE_CALM=0))
        self.assertEqual([first, second], roster(owner))
        second.InfectedEntity.HCVarietyDormant = lambda: True
        self.assertIsNone(roster(owner))
        second.SearchPack = N()  # Existing investigator's native ownership wins.
        self.assertEqual([first], roster(owner))
        first.EverAssigned = True
        self.assertIsNone(roster(owner))  # No eligible group remains.

    def test_scan_skips_blocked_places_and_rotates_over_eligible_actors(self):
        """#213: real accessor on synthetic bodies; visibility is only a stub."""
        path = AREA / 'HCInfectedVarietyRoutes.c'
        for blocked in ('dormant', 'combat', 'visible'):
            with self.subTest(blocked=blocked):
                def actor(place, block=False):
                    return N(GroupId=0, SearchPack=None, EverAssigned=False,
                             InfectedEntity=N(IsAlive=lambda: True,
                               HCVarietyTriedDormant=lambda: True,
                               HCVarietyRouteTried=lambda: False,
                               HCVarietyPlace=lambda: place,
                               HCVarietyDormant=lambda: block and blocked == 'dormant',
                               GetMindStateSynced=lambda: int(block and blocked == 'combat'),
                               GetPosition=lambda: (place, block)))
                first = actor('blocked', True)
                second, third = actor('second'), actor('third')
                owner = N(m_Healthy=True, m_Config=N(MaxTracked=24),
                          m_HCVarietyRouteCursor=0, m_Actors=Array([first, second]))
                roster = translate(str(path), 'array<HCInfectedActor> HCVarietyRouteRoster(', (),
                                   HCInfectedVariety=N(HCConfig=lambda: N(GroupMembers=3, EnableMigration=True),
                                     HCHidden=lambda pos, players: not (pos[1] and blocked == 'visible')),
                                   HCPerfPlayers=N(HCGet=lambda: Array()),
                                   DayZInfectedConstants=N(MINDSTATE_CALM=0))
                self.assertEqual([second], roster(owner))  # Two places, one scan.
                owner.m_Actors.Insert(third)
                self.assertEqual([second], roster(owner))
                self.assertEqual([third], roster(owner))
                self.assertEqual([second], roster(owner))
                # Cursor remains valid after the tracked actor list shrinks.
                owner.m_Actors = Array([third])
                self.assertEqual([third], roster(owner))

    def test_blocked_place_is_checked_once_and_scan_respects_actor_cap_and_opt_out(self):
        path = AREA / 'HCInfectedVarietyRoutes.c'
        checks = []
        def body():
            return N(IsAlive=lambda: True, HCVarietyTriedDormant=lambda: True,
                     HCVarietyRouteTried=lambda: False, HCVarietyPlace=lambda: 'same-place',
                     HCVarietyDormant=lambda: checks.append('blocked') or True)
        actors = Array([N(GroupId=0, SearchPack=None, EverAssigned=False,
                          InfectedEntity=body()) for _ in range(3)])
        owner = N(m_Healthy=True, m_Config=N(MaxTracked=3),
                  m_HCVarietyRouteCursor=0, m_Actors=actors)
        config = N(GroupMembers=3, EnableMigration=True)
        roster = translate(str(path), 'array<HCInfectedActor> HCVarietyRouteRoster(', (),
                           HCInfectedVariety=N(HCConfig=lambda: config),
                           HCPerfPlayers=N(HCGet=lambda: checks.append('players') or Array()))
        self.assertIsNone(roster(owner))
        self.assertEqual(['players', 'blocked'], checks)
        self.assertEqual(0, owner.m_HCVarietyRouteCursor)  # Exactly one bounded sweep.
        checks.clear()
        config.EnableMigration = False
        self.assertIsNone(roster(owner))
        config.EnableMigration = True
        owner.m_Config.MaxTracked = 2  # Never build a partial, truncated group.
        self.assertIsNone(roster(owner))
        self.assertEqual([], checks)

    def test_tick_releases_on_visibility_and_commits_one_next_segment_on_arrival(self):
        path = AREA / 'HCInfectedVarietyRoutes.c'
        calls, hidden = [], [True]
        group = N()
        member = N(IsAlive=lambda: True, HCVarietyDormant=lambda: False,
                   GetMindStateSynced=lambda: 0, GetAIAgent=lambda: N(GetGroup=lambda: group),
                   GetPosition=lambda: [0.,0.,0.])
        owner = N(m_Releasing=False, m_Expires=99., m_VarietyRoute=N(Nodes=Array([0,1])),
                  m_VarietyNode=1, m_VarietyDefaults=N(ArrivalMetres=1.),
                  m_Members=Array([member]), Group=group, RouteEnd=[0.,0.,0.],
                  Release=lambda: calls.append('release') or True,
                  HCVarietyNextSegment=lambda now: calls.append('next') or True)
        scope = dict(HCInfectedVarietyModule=N(VarietyActive=lambda: True),
                     HCInfectedVariety=N(HCHidden=lambda *a: hidden[0]),
                     HCPerfPlayers=N(HCGet=lambda: Array()),
                     DayZInfectedConstants=N(MINDSTATE_CALM=0),
                     vector=N(DistanceSq=lambda a,b: sum((x-y)**2 for x,y in zip(a,b))),
                     super=N(Tick=lambda now: calls.append('native_tick') or True))
        maintain = translate(str(path), 'bool HCMaintain(', ('Release',), fields=('Group', 'RouteEnd'), **scope)
        owner.HCMaintain = lambda now: maintain(owner, now)
        tick = translate(str(path), 'override bool Tick(', ('HCMaintain', 'Release', 'HCVarietyNextSegment'),
                         fields=('Group', 'RouteEnd'), **scope)
        self.assertTrue(tick(owner, 1.))
        self.assertEqual(['next', 'native_tick'], calls)
        calls.clear()
        hidden[0] = False
        self.assertFalse(tick(owner, 2.))
        self.assertEqual(['release'], calls)
        calls.clear()
        hidden[0] = True
        self.assertFalse(tick(owner, 99.))
        self.assertEqual(['release'], calls)

    def test_refused_budget_still_runs_the_active_pack_safety_release(self):
        """Review P1: expiry/sight release must not wait for the shared infected budget."""
        path = AREA / 'HCInfectedVarietyRoutes.c'
        calls = []
        pack = N(Tick=lambda now: calls.append('tick') or True,
                 HCMaintain=lambda now: calls.append('maintain') or now < 50.)
        state = N(s_Config=N(EnableMigration=True), s_Routes=None, s_Pack=pack, s_NextScan=0.)
        grant = [False]
        cleared = []
        with tempfile.TemporaryDirectory() as folder:
            fixture = Path(folder) / path.name
            fixture.write_text(path.read_text().replace(' { ', ' {\n '))
            step = translate(str(fixture), 'static void HCStep(', (), statics=tuple(vars(state)), STATICS=state,
                             HCInfectedVarietyModule=N(VarietyActive=lambda: True),
                             HCServer=N(HCTickWork=lambda: N(HCTakeFor=lambda consumer, cost: grant[0])),
                             HCUnitBudget=N(HC_WORK_INFECTED=0),
                             HCClearRoster=lambda: cleared.append(True))
        step(None, 10.)
        self.assertEqual(['maintain'], calls)
        self.assertIs(pack, state.s_Pack)
        grant[0] = True
        step(None, 11.)
        self.assertEqual(['maintain', 'tick'], calls)
        grant[0] = False
        step(None, 60.)
        self.assertEqual(['maintain', 'tick', 'maintain'], calls)
        self.assertIsNone(state.s_Pack)
        self.assertEqual([True], cleared)

if __name__ == '__main__': unittest.main()
