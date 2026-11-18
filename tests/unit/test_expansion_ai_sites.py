"""HC site rules (patrols, scavenger parties, holdouts with a cache) on Expansion AI.

The authored Enforce bodies run through the syntax adapter with explicit synthetic inputs; nothing here
establishes DayZ behavior. Spawning, line of sight, despawn and cache persistence stay pending native
observation with a client.

Route-chain task / NFR-003, NFR-006 (2026-11-17): given synthetic long-leg partial
paths, continue from actual ends, walk those same endpoints, and refuse a stalled,
over-budget or exhausted chain. Holdouts retain the original single-call rule.
RED before implementation, actual output from
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_expansion_ai_sites.SiteChainGlueTests.test_partial_calls_chain_from_actual_end_and_preserve_patrol_points -v:
    AssertionError: True is not false : leg 0: path ends short of the waypoint
    Ran 1 test in 0.007s
    FAILED (failures=1)
GREEN: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_expansion_ai_sites -v
    Ran 49 tests in 0.193s
    OK

Read-only API evidence: native scripts-1.30.164289/3_Game/AI/AIWorld.c:59-68,
98,122 (PGFilter, FindPath, SampleNavmeshPosition). The supplied xp directory
was absent; inspected installed 2792982069/addons/ai_scripts.pbo members instead:
3_Game/DayZExpansion_AI/Settings/Patrols/ExpansionAIPatrolBase.c:126-153,346-414
(placement and GetWaypoints); 4_World/DayZExpansion_AI/Classes/Patrols/
eAIDynamicPatrol.c:111,653-655 (config to group); Classes/PathFinding/
ExpansionPathFilters.c:58-68 (matching flags), ExpansionPathPoint.c:93-136
(native call and partial-end handling). No exposed native node/length limit was
found. Source inspection and these synthetic tests do not prove server routes.
"""
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_expansion_ai_adapter import A, Authored, block, declarations

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World'
AI = ROOT / 'mission/hollow-country/ai'


def api(source, env):
    authored = Authored(source, env)
    out = N()
    for name in re.findall(r'static \w+ (\w+)\(', source):
        setattr(out, name, lambda *a, n=name: authored.call(n, None, *a))
    return out


def dto(env, name, data):
    """Fill a declared HCXAIData.c DTO from JSON-like data (vectors become tuples)."""
    result = env[name]()
    nested = {'Sites': 'HCXAISite', 'CacheLoot': 'HCXAISiteLoot', 'Rows': None}
    for key, value in data.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            value = A(dto(env, nested[key], row) for row in value)
        elif isinstance(value, list) and value and isinstance(value[0], list):
            value = A(tuple(float(x) for x in row) for row in value)
        elif isinstance(value, list) and len(value) == 3 and all(isinstance(x, (int, float)) for x in value):
            value = tuple(float(x) for x in value)
        elif isinstance(value, list):
            value = A(value)
        setattr(result, key, value)
    return result


class SiteRulesTests(unittest.TestCase):
    def setUp(self):
        self.env = dict(A=A, Print=lambda *a: None)
        declarations(self.env)
        self.env['vector'] = N(Distance=lambda a, b: math.dist(a, b))
        self.env['Math'] = N(AbsFloat=abs)
        self.env['HCXAIRules'] = api((SCRIPTS / 'HCXAIRules.c').read_text(), self.env)
        self.source = (SCRIPTS / 'HCXAISiteRules.c').read_text()
        self.rules = api(self.source, self.env)
        self.env['HCXAISiteRules'] = self.rules
        self.policy = dto(self.env, 'HCXAISitePolicy', json.loads((AI / 'sites.json').read_text()))

    def site(self, kind):
        return next(s for s in self.policy.Sites if s.Kind == kind)

    # Expansion's stock AI aims at 35-95%, notices threats to 1000 m, investigates noise to 500 m and
    # flanks up to 200 m (ExpansionAISettings.Defaults). The owner asked for worse aim and less smarts.
    # A value <= 0 makes eAIDynamicPatrol fall back to the global setting, so every value must be > 0.
    def test_site_ai_aims_worse_and_notices_less_than_stock_expansion(self):
        for kind in ('patrol', 'scavenger', 'holdout'):
            low = self.rules.AccuracyMin(kind)
            high = self.rules.AccuracyMax(kind)
            self.assertTrue(0 < low <= high <= 0.5, (kind, low, high))
            self.assertTrue(0 < self.rules.ThreatDistance(kind) <= 350, kind)
            self.assertTrue(0 < self.rules.NoiseDistance(kind) <= 200, kind)
            self.assertTrue(0 < self.rules.FlankDistance(kind) <= 60, kind)
        self.assertLess(self.rules.AccuracyMax('scavenger'), self.rules.AccuracyMax('patrol'))

    def test_shipped_policy_is_admissible_and_has_every_kind(self):
        self.assertEqual(self.rules.PolicyProblem(self.policy), '')
        kinds = {s.Kind for s in self.policy.Sites}
        self.assertEqual(kinds, {'patrol', 'scavenger', 'holdout'})
        self.assertLessEqual(self.policy.MaxActiveAI, 24)
        self.assertEqual(self.policy.ObserverPolicy, 'native-eai')

    def test_policy_refuses_budgets_above_the_ceiling_and_a_non_native_observer(self):
        self.policy.MaxActiveAI = 25
        self.assertIn('MaxActiveAI', self.rules.PolicyProblem(self.policy))
        self.policy.MaxActiveAI = 24
        self.policy.MinPlayerDistance = 150
        self.assertIn('MinPlayerDistance', self.rules.PolicyProblem(self.policy))
        self.policy.MinPlayerDistance = 200
        self.policy.ObserverPolicy = 'omniscient'
        self.assertIn('observer', self.rules.PolicyProblem(self.policy))

    def test_site_refuses_unknown_kind_faction_size_and_foreign_loadout(self):
        site = self.site('scavenger')
        site.Kind = 'convoy'
        self.assertIn('kind', self.rules.SiteProblem(self.policy, site))
        site.Kind = 'scavenger'
        site.Faction = 'InvincibleGuards'
        self.assertIn('faction', self.rules.SiteProblem(self.policy, site))
        site.Faction = 'Raiders'
        site.NumberOfAIMax = 4
        self.assertIn('size', self.rules.SiteProblem(self.policy, site))
        site.NumberOfAIMax = 3
        site.Loadout = 'BanditLoadout'
        self.assertIn('loadout', self.rules.SiteProblem(self.policy, site))

    def test_site_refuses_activation_inside_the_no_spawn_ring_and_long_legs(self):
        site = self.site('patrol')
        site.ActivationRadius = 240
        self.assertIn('ActivationRadius', self.rules.SiteProblem(self.policy, site))
        site.ActivationRadius = 600
        a = site.Waypoints[0]
        site.Waypoints[1] = (a[0] + 900., a[1], a[2])
        self.assertIn('leg', self.rules.SiteProblem(self.policy, site))

    def test_holdout_needs_a_vanilla_cache_with_a_small_finite_table(self):
        site = self.site('holdout')
        self.assertEqual(site.Faction, 'Guards')
        self.assertIn(site.CacheClass, ('WoodenCrate', 'SeaChest'))
        site.CacheClass = 'ExpansionSafe'
        self.assertIn('cache class', self.rules.SiteProblem(self.policy, site))
        site.CacheClass = 'WoodenCrate'
        site.CacheLoot = A(N(ClassName='Rag', Quantity=1) for _ in range(9))
        self.assertIn('cache loot', self.rules.SiteProblem(self.policy, site))
        site.CacheLoot = A([N(ClassName='Rag', Quantity=50)])
        self.assertIn('cache loot', self.rules.SiteProblem(self.policy, site))
        site.CacheLoot = A([N(ClassName='Rag', Quantity=2)])
        site.CacheCooldownSeconds = 60
        self.assertIn('cooldown', self.rules.SiteProblem(self.policy, site))

    def test_duplicate_site_ids_are_refused(self):
        self.policy.Sites.append(self.policy.Sites[0])
        self.assertIn('duplicate', self.rules.PolicyProblem(self.policy))

    def test_spawn_needs_budget_distance_and_no_line_of_sight(self):
        p = self.policy
        self.assertEqual(self.rules.SpawnProblem(p, 0, 0, 3, 250., False), '')
        self.assertIn('player within', self.rules.SpawnProblem(p, 0, 0, 3, 199.9, False))
        self.assertIn('line of sight', self.rules.SpawnProblem(p, 0, 0, 3, 600., True))
        self.assertIn('AI budget', self.rules.SpawnProblem(p, 22, 1, 3, 600., False))
        self.assertEqual(self.rules.SpawnProblem(p, 21, 1, 3, 600., False), '')
        self.assertIn('site budget', self.rules.SpawnProblem(p, 0, p.MaxActiveSites, 2, 600., False))

    def test_every_member_spawn_point_needs_the_same_distance_and_sight_rules(self):
        p = self.policy
        self.assertEqual(self.rules.MemberSpawnProblem(p, 201., False), '')
        self.assertIn('player within', self.rules.MemberSpawnProblem(p, 197., False))
        self.assertIn('line of sight', self.rules.MemberSpawnProblem(p, 900., True))

    def test_despawn_waits_for_combat_to_end(self):
        self.assertFalse(self.rules.DespawnAllowed(True, False))
        self.assertTrue(self.rules.DespawnAllowed(False, False))
        self.assertTrue(self.rules.DespawnAllowed(True, True))

    def row(self, state, refill=0):
        return N(SiteId='h', Lifecycle=1, ClassName='WoodenCrate', State=state, SeededAt=10, LootedAt=0,
                 NextRefillAt=refill)

    def test_cache_seeds_once_and_a_restart_never_reseeds(self):
        action = self.rules.CacheAction
        self.assertEqual(action(None, False, 0, 100, False), 'seed')
        self.assertEqual(action(None, False, 0, 100, True), 'wait')
        # Killed while seeding: adopt what exists, otherwise count it as looted. Never seed again.
        self.assertEqual(action(self.row('seeding'), True, 3, 100, False), 'adopt')
        self.assertEqual(action(self.row('seeding'), False, 0, 100, False), 'mark-looted')
        self.assertEqual(action(self.row('seeded'), True, 2, 100, False), 'none')

    def test_cache_refills_only_after_looting_and_the_cooldown_with_nobody_near(self):
        action = self.rules.CacheAction
        self.assertEqual(action(self.row('seeded'), True, 0, 100, False), 'mark-looted')
        self.assertEqual(action(self.row('seeded'), False, 0, 100, False), 'mark-looted')
        self.assertEqual(action(self.row('looted', 500), False, 0, 499, False), 'wait')
        self.assertEqual(action(self.row('looted', 500), False, 0, 500, True), 'wait')
        self.assertEqual(action(self.row('looted', 500), True, 0, 500, False), 'refill')
        self.assertEqual(action(self.row('bogus'), True, 3, 100, False), 'refuse')
        self.assertEqual(self.rules.RefillAt(1000, 7200), 8200)

    def test_route_legs_must_be_navmesh_paths_that_reach_the_waypoint(self):
        leg = self.rules.LegProblem
        self.assertIn('navmesh', leg(False, True, 5, 0.5, 120., 100.))
        self.assertIn('no path', leg(True, True, 1, 0.5, 120., 100.))
        self.assertIn('short', leg(True, True, 6, 8., 120., 100.))
        self.assertIn('detour', leg(True, True, 6, 1., 900., 100.))
        self.assertEqual(leg(True, True, 6, 1., 180., 100.), '')

    def test_outdoor_partial_path_continues_but_holdout_stays_strict(self):
        action = self.rules.ChainAction
        self.assertEqual(action('patrol', 1, 3, 80., 40., 40., 120.), 'continue')
        self.assertEqual(action('scavenger', 2, 3, 0., 80., 120., 120.), '')
        self.assertEqual(action('holdout', 1, 3, 8., 4., 4., 12.),
                         'path ends short of the waypoint')
        self.assertEqual(action('holdout', 1, 3, 2.5, 4., 4., 12.), '')

    def test_chain_refuses_disconnected_stalled_and_exhausted_paths(self):
        action = self.rules.ChainAction
        self.assertEqual(action('patrol', 1, 1, 90., 0., 0., 100.), 'no path')
        self.assertEqual(action('patrol', 2, 2, 90., 0.49, 10., 100.), 'path chain stalled')
        self.assertEqual(action('patrol', 16, 2, 4., 2., 96., 100.), 'path chain step limit')
        self.assertEqual(action('patrol', 16, 2, 2.5, 2., 98., 100.), '')
        self.assertEqual(action('patrol', 15, 2, 4., 2., 96., 100.), 'continue')

    def test_chain_detour_budget_is_for_the_entire_original_leg(self):
        # Explicit synthetic lengths: individual calls fit; their sum must fit too.
        action = self.rules.ChainAction
        self.assertEqual(action('scavenger', 2, 3, 1., 5., 351., 100.), 'detour too long')
        self.assertEqual(action('scavenger', 2, 3, 10., 5., 351., 100.), 'detour too long')
        self.assertEqual(action('scavenger', 2, 3, 1., 5., 350., 100.), '')

    def test_route_version_invalidates_all_old_successes_and_refusals(self):
        for kind in ('patrol', 'scavenger', 'holdout'):
            with self.subTest(kind=kind):
                site = self.site(kind)
                text = self.rules.RouteText(site, '1.30.164289')
                self.assertTrue(text.startswith('chain-v2|1.30.164289|'), text)

    def test_only_holdouts_can_reuse_success_without_regenerating_walk_points(self):
        self.assertTrue(self.rules.ReuseQualifiedRoute('holdout'))
        self.assertFalse(self.rules.ReuseQualifiedRoute('patrol'))
        self.assertFalse(self.rules.ReuseQualifiedRoute('scavenger'))

    def test_route_text_changes_with_build_and_points(self):
        site = self.site('scavenger')
        one = self.rules.RouteText(site, '1.30.164289')
        self.assertNotEqual(one, self.rules.RouteText(site, '1.31.0'))
        site.Waypoints[0] = (site.Waypoints[0][0] + 1., site.Waypoints[0][1], site.Waypoints[0][2])
        self.assertNotEqual(one, self.rules.RouteText(site, '1.30.164289'))

    def test_holdout_route_text_covers_the_house_and_its_points(self):
        site = self.site('holdout')
        one = self.rules.RouteText(site, '1.30.164289')
        site.LocalPoints[0] = (site.LocalPoints[0][0] + 1., site.LocalPoints[0][1], site.LocalPoints[0][2])
        two = self.rules.RouteText(site, '1.30.164289')
        self.assertNotEqual(one, two)
        site.HouseClass = 'Land_House_Other'
        self.assertNotEqual(two, self.rules.RouteText(site, '1.30.164289'))

    def admission(self, **over):
        a = self.env['HCXAISiteAdmission']()
        vars(a).update(BuildVersion='1.30.164289', WorldName='chernarusplus', MissingAddons='',
                       SettingsLoaded=True, Globals='', UnfairFaction='', MissingLoadout='',
                       ObserverPolicy='native-eai', Marker=True, OwnershipReconciled=True)
        vars(a).update(over)
        return a

    def test_admission_reports_the_first_unmet_live_check(self):
        problem = lambda **o: self.rules.AdmissionProblem(self.policy, self.admission(**o))
        self.assertEqual(problem(), '')
        self.assertIn('build', problem(BuildVersion='1.29.1'))
        self.assertIn('world', problem(WorldName='enoch'))
        self.assertIn('DayZExpansion_AI_Scripts', problem(MissingAddons='DayZExpansion_AI_Scripts'))
        self.assertIn('settings', problem(SettingsLoaded=False))
        self.assertIn('recruit', problem(Globals='CanRecruitFriendly/CanRecruitGuards must be false'))
        self.assertIn('Guards', problem(UnfairFaction='Guards'))
        self.assertIn('HollowCountry_Patrol', problem(MissingLoadout='HollowCountry_Patrol'))
        self.assertIn('observer', problem(ObserverPolicy='scripted'))
        self.assertIn('pve_patrols', problem(Marker=False))
        self.assertIn('ownership', problem(OwnershipReconciled=False))


class SiteChainGlueTests(unittest.TestCase):
    """Run the authored qualifier with explicit synthetic FindPath results.

    Sampled points are supplied directly: these fixtures claim no native sampling,
    connectivity, node limit, terrain or Expansion movement evidence.
    """
    def setUp(self):
        self.calls = []
        self.logs = []
        self.paths = []
        self.rows = []
        self.cached = None
        self.env = dict(A=A, Print=self.logs.append, HCXAITestArray=A,
                        HCXAIRouteRow=lambda: N(),
                        vector=N(Distance=math.dist, Zero=(0., 0., 0.)),
                        eAIWaypointBehavior=N(HALT=0))
        rules_source = (SCRIPTS / 'HCXAISiteRules.c').read_text()
        self.rules = api(rules_source, self.env)
        self.env['HCXAISiteRules'] = self.rules
        self.world = N(FindPath=self.find_path, SampleNavmeshPosition=lambda *args: True)
        self.env['GetGame'] = lambda: N(GetWorld=lambda: N(GetAIWorld=lambda: self.world))
        # Authored's existing type adapter handles HCXAI* names and constructors.
        source = (SCRIPTS / 'HCXAISites.c').read_text().replace('TVectorArray', 'HCXAITestArray').replace('AIWorld world', 'HCXAITestWorld world')
        source = re.sub(r'([\w.]+\.Count\(\))\.ToString\(\)', r'str(\1)', source)
        self.authored = Authored(source, self.env)
        self.owner = N(m_Filter=object(), RouteRow=lambda key: self.cached,
                       Remember=self.rows.append)
        self.owner.Refuse = lambda *args: self.authored.call('Refuse', self.owner, *args)
        self.state = N(Site=N(Id='synthetic-town', Kind='patrol', Behaviour='ALTERNATE'),
                       Key='synthetic-key', Points=A(), Sampled=A([(100., 0., 100.), (220., 0., 100.)]),
                       PatrolPoints=A([(100., 0., 100.)]), Leg=0, Qualified=False, Cached=False,
                       Failed=False, Reason='', ChainSteps=0, ChainLength=0.,
                       ChainFrom=(0., 0., 0.), ClosestEnd=(0., 0., 0.), ClosestGap=0.,
                       PathCalls=0, Continuations=0)

    def find_path(self, start, goal, filter_used, output):
        self.calls.append((start, goal, filter_used))
        result, points = self.paths.pop(0)
        output.extend(points)
        return result

    def step(self):
        previous = len(self.calls)
        self.authored.call('QualifyStep', self.owner, self.state)
        self.assertLessEqual(len(self.calls) - previous, 1)

    def test_expansion_config_returns_exact_qualified_points_without_replacement_or_interpolation(self):
        wanted = A([(100., 0., 100.), (140., 0., 100.), (220., 0., 100.)])
        config = N(Waypoints=wanted)
        actual = self.authored.call('GetWaypoints', config)
        self.assertEqual(actual, wanted)
        self.assertIsNot(actual, wanted)

    def test_partial_calls_chain_from_actual_end_and_preserve_patrol_points(self):
        self.paths = [(True, [(100., 0., 100.), (140., 0., 100.)]),
                      (True, [(140., 0., 100.), (180., 0., 100.)]),
                      (True, [(180., 0., 100.), (220., 0., 100.)])]
        self.step()
        self.assertFalse(self.state.Failed, self.state.Reason)
        self.assertEqual(self.state.Leg, 0)
        self.step()
        self.step()
        self.step()  # finish and remember only after all legs
        self.assertTrue(self.state.Qualified)
        self.assertEqual([c[0] for c in self.calls],
                         [(100., 0., 100.), (140., 0., 100.), (180., 0., 100.)])
        self.assertEqual(self.state.PatrolPoints,
                         [(100., 0., 100.), (140., 0., 100.), (180., 0., 100.), (220., 0., 100.)])
        self.assertTrue(self.rows[-1].Qualified)

    def test_disconnected_route_refusal_reports_original_leg_and_closest_end(self):
        self.paths = [(True, [(100., 0., 100.), (140., 0., 100.)]),
                      (True, [(140., 0., 100.), (140., 0., 100.)])]
        self.step()
        self.step()
        self.assertTrue(self.state.Failed)
        for part in ('leg 0', 'stalled', 'from=|100.0,0.0,100.0',
                     'to=|220.0,0.0,100.0', 'closest=|140.0,0.0,100.0'):
            self.assertIn(part, self.state.Reason)
        self.assertFalse(self.rows[-1].Qualified)

    def test_closest_diagnostic_uses_a_returned_end_even_when_it_retreats(self):
        self.paths = [(True, [(100., 0., 100.), (80., 0., 100.)]),
                      (True, [(80., 0., 100.), (80., 0., 100.)])]
        self.step()
        self.step()
        self.assertTrue(self.state.Failed)
        self.assertIn('closest=|80.0,0.0,100.0', self.state.Reason)

    def test_closest_diagnostic_survives_a_later_retreat_and_stall(self):
        self.paths = [(True, [(100., 0., 100.), (140., 0., 100.)]),
                      (True, [(140., 0., 100.), (130., 0., 100.)]),
                      (True, [(130., 0., 100.), (130., 0., 100.)])]
        for _ in range(3):
            self.step()
        self.assertTrue(self.state.Failed)
        self.assertIn('closest=|140.0,0.0,100.0', self.state.Reason)

    def test_holdout_partial_path_is_refused_on_first_call(self):
        self.state.Site.Kind = 'holdout'
        self.paths = [(True, [(100., 0., 100.), (140., 0., 100.)])]
        self.step()
        self.assertTrue(self.state.Failed)
        self.assertIn('path ends short', self.state.Reason)
        self.assertEqual(len(self.calls), 1)

    def test_false_findpath_result_cannot_qualify_even_with_output_points(self):
        self.paths = [(False, [(100., 0., 100.), (220., 0., 100.)])]
        self.step()
        self.assertTrue(self.state.Failed)
        self.assertIn('no path', self.state.Reason)

    def test_loop_closure_is_qualified_without_duplicate_first_patrol_point(self):
        self.state.Site.Behaviour = 'LOOP'
        self.paths = [(True, [(100., 0., 100.), (220., 0., 100.)]),
                      (True, [(220., 0., 100.), (160., 0., 100.)]),
                      (True, [(160., 0., 100.), (100., 0., 100.)])]
        for _ in range(4):
            self.step()
        self.assertTrue(self.state.Qualified)
        self.assertEqual(self.state.PatrolPoints,
                         [(100., 0., 100.), (220., 0., 100.), (160., 0., 100.)])
        self.assertEqual(self.calls[-1][1], self.state.PatrolPoints[0])

    def test_cached_outdoor_success_rebuilds_intermediate_points_after_sampling(self):
        self.cached = N(Qualified=True)
        self.state.Points = A(self.state.Sampled)
        self.state.Sampled = A()
        self.state.PatrolPoints = A()
        self.step()
        self.assertFalse(self.state.Qualified)
        self.assertEqual(self.state.PatrolPoints, [(100., 0., 100.)])
        self.paths = [(True, [(100., 0., 100.), (160., 0., 100.)]),
                      (True, [(160., 0., 100.), (220., 0., 100.)])]
        for _ in range(3):
            self.step()
        self.assertTrue(self.state.Qualified)
        self.assertIn((160., 0., 100.), self.state.PatrolPoints)

    def test_cached_holdout_success_preserves_original_sampled_points(self):
        self.cached = N(Qualified=True)
        self.state.Site.Kind = 'holdout'
        self.state.Points = A(self.state.Sampled)
        self.state.Sampled = A()
        self.state.PatrolPoints = A()
        self.step()
        self.assertTrue(self.state.Qualified)
        self.assertTrue(self.state.Cached)
        self.assertEqual(self.state.PatrolPoints, self.state.Sampled)
        self.assertEqual(self.calls, [])

    def test_new_version_cached_refusal_still_prevents_retry(self):
        self.cached = N(Qualified=False, Reason='synthetic disconnected island')
        self.step()
        self.assertTrue(self.state.Failed)
        self.assertIn('cached refusal', self.state.Reason)
        self.assertEqual(self.calls, [])

    def test_chain_budget_refuses_moving_forever(self):
        # Synthetic path: moves on each call but cannot reach the target within the cap.
        self.state.Sampled[1] = (700., 0., 100.)
        for i in range(16):
            start = (100. + i, 0., 100.)
            end = (101. + i, 0., 100.)
            self.paths.append((True, [start, end]))
        for _ in range(16):
            self.step()
        self.assertTrue(self.state.Failed)
        self.assertIn('step limit', self.state.Reason)
        self.assertEqual(len(self.calls), 16)

    def test_summed_detour_refuses_short_final_call(self):
        # 120 m direct gives 410 m budget: 320 m first path + 120 m final path.
        self.paths = [(True, [(100., 0., 100.), (100., 0., 240.), (140., 0., 240.), (140., 0., 100.)]),
                      (True, [(140., 0., 100.), (140., 0., 120.), (220., 0., 120.), (220., 0., 100.)])]
        self.step()
        self.assertFalse(self.state.Failed)
        self.step()
        self.assertTrue(self.state.Failed)
        self.assertIn('detour too long', self.state.Reason)


class SiteSourceTests(unittest.TestCase):
    """Static guards on the native glue; behavior is pending native observation."""
    def setUp(self):
        self.sites = (SCRIPTS / 'HCXAISites.c').read_text()
        self.all = '\n'.join(p.read_text() for p in sorted(SCRIPTS.glob('HCXAISite*.c')))

    def code(self, text):
        text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
        return re.sub(r'//[^\n]*', '', text)

    def test_enforce_rules_no_ternary_no_local_identifier(self):
        code = self.code(self.all)
        self.assertNotIn('?', code)
        self.assertIsNone(re.search(r'\blocal\b', code))

    def test_no_enforce_keyword_is_used_as_a_variable_name(self):
        # Native compile of compile-xai4-01 refused `HCXAIOwnedRow owned = ...` (owned is a modifier keyword).
        code = self.code('\n'.join(p.read_text() for p in sorted(SCRIPTS.glob('*.c'))))
        words = ('owned', 'out', 'inout', 'notnull', 'autoptr', 'reference', 'volatile', 'external', 'event',
                 'thread', 'sealed', 'local')
        pattern = r'\b[A-Za-z_][A-Za-z0-9_<>]*\s+(%s)\s*(=|;|,|\))' % '|'.join(words)
        self.assertEqual([m.group(0) for m in re.finditer(pattern, code)
                          if not m.group(0).split()[0] in ('ref', 'out', 'inout', 'notnull', 'autoptr')], [])

    def test_no_engine_type_name_is_used_as_a_member_or_variable_name(self):
        # compile-xai4-03 refused `Object House;` ("Variable name 'House' already used as type name").
        code = self.code('\n'.join(p.read_text() for p in sorted(SCRIPTS.glob('*.c'))))
        types = ('House', 'Object', 'File', 'Slot', 'Man', 'Building', 'Car', 'Weapon', 'Entity', 'Container',
                 'Camera', 'Param', 'Class', 'Transport', 'Boat', 'Hologram', 'Magazine', 'Clothing', 'Inventory',
                 'Land', 'Grenade', 'Fireplace', 'Edible', 'Bottle', 'Mission', 'Timer', 'Material', 'Shape',
                 'Plant', 'Animal', 'Trigger')
        pattern = r'\b[A-Za-z_][A-Za-z0-9_<>]*\s+(%s)\s*(=|;|,|\))' % '|'.join(types)
        self.assertEqual([m.group(0) for m in re.finditer(pattern, code) if not m.group(0).startswith('return ')], [])

    def test_patrol_subclass_keeps_native_spawning_and_finite_fair_actors(self):
        code = self.code(self.sites)
        self.assertIn('class HCXAISitePatrol : eAIDynamicPatrol', code)
        self.assertIn('eAIDynamicPatrolT<HCXAISitePatrol>.CreateEx(', code)
        for name in ('override bool CanSpawn()', 'override void Spawn()',
                     'override void Despawn(bool deferDespawnUntilLoosingAggro = false)',
                     'override void SetupAI(eAIBase ai)'):
            self.assertIn(name, code)
        self.assertIn('ai.eAI_SetUnlimitedReload(0)', code)
        self.assertIn('config.UnlimitedReload = 0', code)
        self.assertIn('config.Persist = false', code)
        self.assertIn('config.CanBeLooted = true', code)
        # No teleports: the director never moves actors; Expansion places each one once at spawn.
        self.assertNotIn('SetPosition(', code)
        self.assertNotIn('SetOrigin(', code)

    def test_each_deferred_member_is_checked_at_its_own_position_before_it_exists(self):
        # Expansion spawns members 2..N later, at formation offsets, through SpawnAI_Deferred(i) (see the
        # installed eAIDynamicPatrol.c); the anchor check alone would let a member appear inside 200 m or in sight.
        code = self.code(self.sites)
        start = code.index('override void SpawnAI_Deferred(int i)')
        body = code[start:code.index('override void Despawn(', start)]
        self.assertIn('m_Formation.ToWorld(m_Formation.GetPosition(i))', body)
        self.assertIn('GetPlacementPosition(', body)
        check = body.index('MemberProblemFor(')
        self.assertLess(check, body.index('super.SpawnAI_Deferred(i)'))
        refused = body[check:body.index('super.SpawnAI_Deferred(i)')]
        self.assertIn('m_NumberOfAI = m_Group.Count()', refused)  # refused members never join the budget
        self.assertIn('m_Group.SetWaypointBehaviour(m_WaypointBehaviour)', refused)  # no group left halted
        director = code[code.index('string MemberProblemFor('):]
        self.assertIn('HCXAISiteRules.MemberSpawnProblem(', director[:director.index('\n    }')])

    def test_no_function_assigns_new_to_one_of_its_parameters(self):
        # Native compile on main: "hcxaisites.c,685: Variable 'row' is not strong ref" (SeedCache parameter).
        found = []
        for path in sorted(SCRIPTS.parent.rglob('*.c')):
            code = self.code(path.read_text())
            for match in re.finditer(r'\n    (?:[\w<>, ]+\s+)?\w+\s*\(([^()]*)\)\s*\n    \{(.*?)\n    \}', code, re.S):
                params = [part.split('=')[0].split()[-1] for part in match.group(1).split(',') if part.strip()]
                for name in params:
                    if re.search(r'(?<![\w.])%s\s*=\s*new\b' % re.escape(name), match.group(2)):
                        found.append('%s: %s' % (path.name, name))
        self.assertEqual(found, [])

    def test_each_site_patrol_carries_its_own_toned_down_tuning(self):
        code = self.code(self.sites)
        body = code[code.index('protected void Create('):]
        body = body[:body.index('config.Waypoints')]
        for field, rule in (('AccuracyMin', 'AccuracyMin'), ('AccuracyMax', 'AccuracyMax'),
                            ('ThreatDistanceLimit', 'ThreatDistance'),
                            ('NoiseInvestigationDistanceLimit', 'NoiseDistance'),
                            ('MaxFlankingDistance', 'FlankDistance')):
            self.assertRegex(body, r'config\.%s = HCXAISiteRules\.%s\(site\.Kind\);' % (field, rule))

    def test_patrol_receives_the_same_generated_points_and_cached_outdoors_requalify(self):
        code = self.code(self.sites)
        create = code[code.index('protected void Create('):]
        self.assertIn('foreach (vector point : state.PatrolPoints)', create)
        qualify = code[code.index('protected void QualifyStep('):code.index('protected void Refuse(')]
        self.assertEqual(qualify.count('world.FindPath('), 1)
        self.assertIn('HCXAISiteRules.ReuseQualifiedRoute(state.Site.Kind)', qualify)
        self.assertIn('if (state.Site.Kind == "") { radius = 2; }', qualify)

    def test_create_uses_qualified_config_override_to_preserve_engine_path_endpoints(self):
        code = self.code(self.sites)
        self.assertIn('class HCXAISiteSpawnConfig : ExpansionAIDynamicSpawnBase', code)
        self.assertIn('override TVectorArray GetWaypoints(', code)
        create = code[code.index('protected void Create('):]
        self.assertIn('new HCXAISiteSpawnConfig()', create)
        for field in ('Speed', 'UnderThreatSpeed', 'Behaviour', 'Faction', 'Loadout'):
            self.assertIn('config.' + field + ' = ', create)

    def test_no_function_redeclares_a_local_even_in_sibling_blocks(self):
        found = []
        for filename in ('HCXAISites.c', 'HCXAISiteRules.c'):
            source = self.code((SCRIPTS / filename).read_text())
            for match in re.finditer(r'\n    (?:[\w<>, ]+\s+)?(\w+)\s*\(([^()]*)\)\s*\n    \{', source):
                names = [p.split('=')[0].split()[-1] for p in match[2].split(',') if p.strip()]
                body = block(source, match.end())
                names += re.findall(r'\b(?:bool|int|float|string|vector|Object|TVectorArray|HCXAI\w+)\s+(\w+)\s*(?=[=;:)])', body)
                duplicates = sorted({name for name in names if names.count(name) > 1})
                if duplicates:
                    found.append((filename, match[1], duplicates))
        self.assertEqual(found, [])

    def test_cache_intent_is_journaled_before_the_container_exists(self):
        code = self.code(self.sites)
        body = code[code.index('void SeedCache('):]
        self.assertLess(body.index('SaveCaches()'), body.index('CreateObjectEx('))


class ShippedContentTests(unittest.TestCase):
    def test_loadouts_are_finite(self):
        names = {s['Loadout'] for s in json.loads((AI / 'sites.json').read_text())['Sites']}
        self.assertTrue(names)
        for name in names:
            data = json.loads((AI / 'loadouts' / (name + '.json')).read_text())
            text = json.dumps(data)
            self.assertNotIn('Unlimited', text)
            mags = re.findall(r'"ClassName": "(Mag_[^"]+)"', text)
            self.assertTrue(mags, name)
            self.assertLessEqual(len(mags), 6, name)  # one loaded + spare per weapon set, never a stockpile

    # The merge into Expansion's AISettings.json also lowers the global fallbacks (stock 0.35..0.95,
    # 1000 m, 500 m, 200 m), so any Expansion AI that does not come from our sites is toned down too.
    def test_global_expansion_ai_fallbacks_are_toned_down(self):
        merge = json.loads((AI / 'AISettings.merge.json').read_text())
        self.assertTrue(0 < merge['AccuracyMin'] <= merge['AccuracyMax'] <= 0.5)
        self.assertTrue(0 < merge['ThreatDistanceLimit'] <= 350)
        self.assertTrue(0 < merge['NoiseInvestigationDistanceLimit'] <= 200)
        self.assertTrue(0 < merge['MaxFlankingDistance'] <= 60)
        self.assertEqual((merge['DamageMultiplier'], merge['DamageReceivedMultiplier']), (1.0, 1.0))

    # Expansion arms an AI with a hand item only if Expansion_IsMeleeWeapon accepts it (inventorySlot
    # Shoulder/Melee/Knife, itemInfo Knife/Axe or suicideAnim woodaxe; ItemBase.c). Otherwise the AI
    # falls back to its knife. These have vanilla inventorySlot Shoulder+Melee (CfgVehicles, read
    # from the installed 1.30 configs on 2026-11-17); Pipe, Machete, Hatchet, Crowbar, PipeWrench and
    # Cleaver do not, so they are left out.
    MELEE = {'FirefighterAxe', 'BaseballBat', 'NailedBaseballBat', 'Shovel', 'WoodAxe', 'Pitchfork',
             'Pickaxe', 'Mace', 'Broom'}

    def weapon_sets(self, name):
        data = json.loads((AI / 'loadouts' / (name + '.json')).read_text())
        return [s for s in data['Sets'] if s.get('ClassName') == 'WEAPON']

    def melee_only(self, weapon_set):
        hands = [i['ClassName'] for a in weapon_set.get('InventoryAttachments', [])
                 if a.get('SlotName') == 'Hands' for i in a.get('Items', [])]
        text = json.dumps(weapon_set)
        return bool(hands) and set(hands) <= self.MELEE and 'Mag_' not in text and 'Ammo_' not in text

    # Expansion spawns one WEAPON set per AI, picked at random among the sets whose Chance passed
    # (ExpansionPrefabObject.Spawn), so equal-chance sets give each AI an even pick.
    def test_some_ai_of_every_kind_fight_with_melee_only(self):
        shares = {}
        for name in ('HollowCountry_Patrol', 'HollowCountry_Scavenger', 'HollowCountry_Holdout'):
            sets = self.weapon_sets(name)
            self.assertTrue(all(s.get('Chance') == 1.0 for s in sets), name)
            shares[name] = sum(self.melee_only(s) for s in sets) / len(sets)
            self.assertTrue(0 < shares[name] < 1, (name, shares[name]))
        self.assertGreaterEqual(shares['HollowCountry_Scavenger'], 0.5)
        self.assertGreater(shares['HollowCountry_Scavenger'], shares['HollowCountry_Patrol'])

    def test_every_hand_item_without_ammo_is_a_melee_weapon_expansion_accepts(self):
        for name in ('HollowCountry_Patrol', 'HollowCountry_Scavenger', 'HollowCountry_Holdout'):
            for weapon_set in self.weapon_sets(name):
                text = json.dumps(weapon_set)
                if 'Mag_' in text or 'Ammo_' in text:
                    continue
                hands = [i['ClassName'] for a in weapon_set.get('InventoryAttachments', [])
                         if a.get('SlotName') == 'Hands' for i in a.get('Items', [])]
                self.assertTrue(hands, name)
                self.assertLessEqual(set(hands), self.MELEE, name)


if __name__ == '__main__':
    unittest.main()
