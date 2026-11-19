"""HC site rules (patrols, scavenger parties, holdouts with a cache) on Expansion AI.

W5 #125/#122/review (2026-11-18): spec = scale authored counts by online
identity players, retain shared 8-body/2-site reservations, expose bounded live
debug state, zero unseen threat, bind nearest qualified route within 600 m.
Plan/tasks = inspect installed native/provider interfaces; one scaling smoke
RED; update native spawn config and existing ledger, snapshot lifecycle and
stance/event glue; smoke GREEN plus all existing source readers. Native Windows
compile, normal PBO/server and two-client perception/debug checks remain pending.
Smoke command: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest
tests.unit.test_expansion_ai_sites.SiteRulesTests.test_w5_group_scaling_rounds_and_caps_authored_counts -v
RED: AttributeError: 'types.SimpleNamespace' object has no attribute 'HCGroupFactor'
Ran 1 test in 0.010s; FAILED (errors=1).
GREEN: Ran 1 test in 0.011s; OK.

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


Round 2 / chain-v3 task contract A-D; NFR-001/003/006:
Spec: bounded skips and reached-end snapping, authored minimum 3 outdoors/2 holdouts.
Plan/tasks: stage attempt endpoints; retry next target from kept start; restart an
isolated first point; qualify closure or use native ONCE; cap all calls at 96;
rebuild successes since the journal stores neither snaps nor skips. Runtime gates
remain pending. Required spec/plan/tasks were read from /code/dayzsa_mods/docs
because they are absent in this confined worktree; those files were not changed.
RED command: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_expansion_ai_sites -v
Actual observed-case failures (verbatim; rounded log coordinates give slightly different gaps):
FAIL: test_observed_holdout_mogilevka_near_miss_snaps_target_one (tests.unit.test_expansion_ai_sites.SiteChainGlueTests.test_observed_holdout_mogilevka_near_miss_snaps_target_one)
AssertionError: False is not true : leg 0: path ends short of the waypoint; from=|7556.67,214.573,5148.83; to=|7559.6,214.0,5142.52; closest=|7562.5,215.0,5143.2; gap=3.1420375554720934; steps=1

FAIL: test_observed_mil_tisy_stall_skips_target_one (tests.unit.test_expansion_ai_sites.SiteChainGlueTests.test_observed_mil_tisy_stall_skips_target_one)
AssertionError: False is not true : leg 0: path chain stalled; from=|1684.98,447.921,14219.3; to=|1710.85,451.82,14279.3; closest=|1694.9,449.68,14224.7; gap=56.92224609060886; steps=2

FAIL: test_observed_police_berezino_stall_skips_target_two (tests.unit.test_expansion_ai_sites.SiteChainGlueTests.test_observed_police_berezino_stall_skips_target_two)
AssertionError: False is not true : leg 1: path chain stalled; from=|11994.5,54.1155,9023.1; to=|12067.3,54.01,9145.8; closest=|11995.9,54.0451,9026.3; gap=139.20564367873146; steps=2

FAIL: test_observed_police_chernogorsk_stall_skips_target_two (tests.unit.test_expansion_ai_sites.SiteChainGlueTests.test_observed_police_chernogorsk_stall_skips_target_two)
AssertionError: False is not true : leg 1: path chain stalled; from=|6571.17,6.41307,2533.65; to=|6631.42,6.30214,2504.04; closest=|6571.7,6.45731,2533.3; gap=66.50300803519299; steps=2

FAIL: test_observed_police_elektrozavodsk_stall_skips_target_one (tests.unit.test_expansion_ai_sites.SiteChainGlueTests.test_observed_police_elektrozavodsk_stall_skips_target_one)
AssertionError: False is not true : leg 0: path chain stalled; from=|10403.4,5.97355,2209.93; to=|10538.6,6.23878,2271.77; closest=|10405.0,5.97355,2210.3; gap=147.06322193856957; steps=2

FAIL: test_observed_scav_novodmitrovsk_stall_skips_target_two (tests.unit.test_expansion_ai_sites.SiteChainGlueTests.test_observed_scav_novodmitrovsk_stall_skips_target_two)
AssertionError: False is not true : leg 1: path chain stalled; from=|11589.8,43.1465,14453.1; to=|11702.5,36.733,14356.1; closest=|11592.7,43.2328,14453.4; gap=146.8522298095596; steps=2

FAIL: test_observed_scav_vybor_near_miss_snaps_target_two (tests.unit.test_expansion_ai_sites.SiteChainGlueTests.test_observed_scav_vybor_near_miss_snaps_target_two)
AssertionError: False is not true : leg 1: path chain stalled; from=|3878.33,310.988,8939.24; to=|3784.31,313.466,9047.0; closest=|3783.6,315.973,9048.0; gap=2.7909046920308973; steps=2
Ran 64 tests in 0.375s
FAILED (failures=18, errors=1)
The other RED failures cover closure fallback, route minimum, restart, cache,
version, snap boundaries and site budget; the error is the old code attempting FindPath for a nine-point
array instead of rejecting it before any call (empty synthetic result queue).

GREEN command: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_expansion_ai_sites -v
Ran 67 tests in 0.501s
OK

Full discover command (run once):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit
Ran 5039 tests in 357.616s

OK (skipped=1, expected failures=3)

Exact synthetic fixture logs (all unobserved legs explicitly fake success;
these counts/coordinates are not predictions of native server results):
[HC Expansion AI] site holdout-mogilevka route qualified: chain-v3 legs=2 FindPath=2 continuations=0 patrol waypoints=3 skipped=0 snapped=1 behaviour=ALTERNATE skipped-points=
[HC Expansion AI] site mil-tisy route qualified: chain-v3 legs=4 FindPath=6 continuations=1 patrol waypoints=4 skipped=1 snapped=0 behaviour=LOOP skipped-points= 1|1710.85,451.82,14279.3
[HC Expansion AI] site police-berezino route qualified: chain-v3 legs=4 FindPath=6 continuations=1 patrol waypoints=4 skipped=1 snapped=0 behaviour=LOOP skipped-points= 2|12067.3,54.01,9145.8
[HC Expansion AI] site police-chernogorsk route qualified: chain-v3 legs=4 FindPath=6 continuations=1 patrol waypoints=4 skipped=1 snapped=0 behaviour=LOOP skipped-points= 2|6631.42,6.30214,2504.04
[HC Expansion AI] site police-elektrozavodsk route qualified: chain-v3 legs=4 FindPath=6 continuations=1 patrol waypoints=4 skipped=1 snapped=0 behaviour=LOOP skipped-points= 1|10538.6,6.23878,2271.77
[HC Expansion AI] site scav-novodmitrovsk route qualified: chain-v3 legs=3 FindPath=5 continuations=1 patrol waypoints=3 skipped=1 snapped=0 behaviour=LOOP skipped-points= 2|11702.5,36.733,14356.1
[HC Expansion AI] site scav-vybor route qualified: chain-v3 legs=4 FindPath=4 continuations=0 patrol waypoints=4 skipped=0 snapped=1 behaviour=LOOP skipped-points=

Round 2 installed reference inspection (no copied provider code):
/mnt/g/SteamLibrary/steamapps/workshop/content/221100/2792982069/addons/ai_scripts.pbo:
3_Game/DayZExpansion_AI/Enums/AIenums.c:1-6 exposes ONCE;
3_Game/DayZExpansion_AI/Settings/Patrols/ExpansionAIPatrolBase.c:25,86-88
maps config Behaviour via StringToEnum. Failed LOOP closure selects ONCE, since
ALTERNATE would introduce unqualified reverse legs. The supplied xp path is absent.

Read-only API evidence: native scripts-1.30.164289/3_Game/AI/AIWorld.c:59-68,
98,122 (PGFilter, FindPath, SampleNavmeshPosition). The supplied xp directory
was absent; inspected installed 2792982069/addons/ai_scripts.pbo members instead:
3_Game/DayZExpansion_AI/Settings/Patrols/ExpansionAIPatrolBase.c:126-153,346-414
(placement and GetWaypoints); 4_World/DayZExpansion_AI/Classes/Patrols/
eAIDynamicPatrol.c:111,653-655 (config to group); Classes/PathFinding/
ExpansionPathFilters.c:58-68 (matching flags), ExpansionPathPoint.c:93-136
(native call and partial-end handling). No exposed native node/length limit was
found. Source inspection and these synthetic tests do not prove server routes.

Round 3 / chain-v4 (#36): four routes were still refused on the local server
(police-chernogorsk, police-elektrozavodsk, police-berezino, scav-novodmitrovsk).
Each logged route minimum kept=1 or 2: a kept group was isolated from every
later point. The cause is sampling with the Expansion FindPath filter, which
admits INSIDE/DOOR/LADDER polygons, at building model origins. The restart only
handled Kept == 1, and the early refusal fired whenever Kept > 1. Fix: restart
whenever Kept < minimum while enough later points remain. Then, once, retry a
refused outdoor route on outdoor-ground samples: WALK only, INSIDE/DOOR/LADDER
excluded, within 2 m of SurfaceY, the centre at radius 16 and then four 12 m
probes at radius 8. FindPath keeps the Expansion filter and the shared 96-call
budget. Holdouts never sample outdoors. The navmesh fixtures below
(isolated_navmesh) are EXPLICIT SYNTHETIC islands. The from/to/closest values on
the refused legs are the server's logged coordinates; everything else is fake.
RED command (old HCXAISites.c/HCXAISiteRules.c, new tests):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_expansion_ai_sites
Actual observed-case failures (verbatim; they reproduce the server's refusal text):
FAIL: test_observed_police_berezino_isolated_kept_pair_requalifies_on_outdoor_ground
AssertionError: False is not true : route minimum: kept=2 required=3; leg 3: path chain stalled; from=|11994.5,54.1155,9023.1; to=|11995.8,54.0662,9109.17; closest=|11995.9,54.0451,9026.3; gap=82.87006302163726; steps=2
FAIL: test_observed_police_chernogorsk_isolated_kept_pair_requalifies_on_outdoor_ground
AssertionError: False is not true : route minimum: kept=2 required=3; leg 3: path chain stalled; from=|6571.17,6.41307,2533.65; to=|6708.72,3.06291,2555.77; closest=|6571.7,6.45731,2533.3; gap=138.89169612097086; steps=2
FAIL: test_observed_police_elektrozavodsk_isolated_kept_pair_requalifies_on_outdoor_ground
AssertionError: False is not true : route minimum: kept=2 required=3; leg 3: path chain stalled; from=|10517.8,6.09771,2327.14; to=|10457.1,6.0694,2355.9; closest=|10516.6,6.09771,2327.6; gap=65.8873341504732; steps=2
FAIL: test_observed_scav_novodmitrovsk_isolated_kept_pair_requalifies_on_outdoor_ground
AssertionError: False is not true : route minimum: kept=2 required=3; leg 2: path chain stalled; from=|11589.8,43.1465,14453.1; to=|11559.1,33.297,14272.0; closest=|11588.1,43.0328,14450.1; gap=180.70804022411434; steps=2
FAIL: test_isolated_kept_pair_restarts_from_a_later_point_before_any_outdoor_retry
AssertionError: False is not true : route minimum: kept=2 required=3; leg 3: path chain stalled; from=|140.0,0.0,100.0; to=|260.0,0.0,100.0; closest=|140.6,0.0,100.0; gap=119.4; steps=2
Ran 81 tests in 0.676s
FAILED (failures=21, errors=2)
The other RED failures and errors cover the outdoor sampler (missing authored
OutdoorSample), the zero-ground refusal, mixed samples, a single retry, the
shared budget, holdouts, the filter source, and chain-v4 in the route key and logs.
GREEN command:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_expansion_ai_sites tests.unit.test_expansion_ai_adapter tests.unit.test_expansion_ai_lifecycle -v
Ran 141 tests in 1.836s
OK
Exact synthetic fixture logs (not predictions of native server results):
[HC Expansion AI] site police-chernogorsk route retry with outdoor ground samples (outdoor=5/5) after: route minimum: kept=1 required=3; leg 3: path chain stalled; from=|6631.42,6.30214,2504.04; to=|6708.72,3.06291,2555.77; closest=|6632.02,6.30214,2504.04; gap=92.57092151962664; steps=2
[HC Expansion AI] site police-chernogorsk route qualified: chain-v4 legs=5 FindPath=22 continuations=8 patrol waypoints=5 skipped=0 snapped=0 behaviour=LOOP sampling=outdoor outdoor=5/5 skipped-points=
[HC Expansion AI] site scav-novodmitrovsk route qualified: chain-v4 legs=4 FindPath=13 continuations=4 patrol waypoints=4 skipped=0 snapped=0 behaviour=LOOP sampling=outdoor outdoor=4/4 skipped-points=
Round 3 API evidence (read-only): scripts-1.30.164289/3_Game/AI/AIWorld.c:1-26
PGPolyFlags, :65 PGFilter.SetFlags, :98 FindPath, :122 SampleNavmeshPosition;
3_Game/Global/Game.c:1176 SurfaceY; 1_Core/proto/EnMath.c:225 Math.AbsFloat.
The outdoor flag set matches HCEventPoliceNav (HCEventRewardCache.c:27-40), with
DOOR added. PGPolyFlags bit values, the 2 m ground tolerance and the radii are
unobserved in DayZ.

Round 4 (#36 AI_ENCOUNTER, route P2s): AI_ENCOUNTER binds an already-owned
qualified site patrol (HCXAIEncounters.c, tests in test_expansion_ai_encounters).
Snap merges within 0.5 m of the last kept point are skipped (SnapKeeps on the
current pathEnd), Create allocates one spawn config, and once orphan reconciliation
passes, prior-process journal rows become prunable.
RED command (old sources, new tests):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_expansion_ai_sites tests.unit.test_expansion_ai_adapter tests.unit.test_expansion_ai_lifecycle tests.unit.test_expansion_ai_encounters -v
Ran 167 tests; FAILED (failures=5, errors=32): missing SnapKeeps/RouteGap/
EncounterProblem/EncounterToken, the duplicated snap point [A, A, ...] in the glue
test, Reconcile(True) TypeError, FileNotFoundError HCXAIEncounters.c, and the adapter
still installing the receipt port and reading expansion-ai.json.
GREEN: the same command gave Ran 167 tests, OK.
Round 4 API evidence (read-only reference, nothing copied):
core_scripts/3_Game/DayZExpansion_Core/ExpansionStatic.c:1748 GetTimestamp(bool useUTC);
ai_scripts/4_World/DayZExpansion_AI/Classes/Patrols/eAIDynamicPatrol.c:45 public
eAIGroup m_Group (set :618, cleared :715); Entities/DayZPlayerImplement.c:234
GetGroup() and :431-438, where EEKilled defers eAI_Cleanup to the next frame;
native 3_Game/Global/Game.c:934 GetWorldName. Kill attribution through the group
has not been observed in DayZ.
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
    from tests.unit.json_loader_port import zero_scalars
    result = zero_scalars(env[name]())
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

    def test_w5_group_scaling_rounds_and_caps_authored_counts(self):
        # Synthetic player counts only; no native spawning or runtime evidence.
        self.env['Math'].Round = lambda value: math.floor(value + 0.5)
        for players, factor, expected in ((1, .6, [1, 2, 2]),
                                           (3, 1., [2, 3, 4]),
                                           (6, 1.3, [3, 4, 5])):
            self.assertAlmostEqual(factor, self.rules.HCGroupFactor(players))
            self.assertEqual(expected, [self.rules.HCGroupMembers(n, factor)
                                        for n in (2, 3, 4)])
        self.assertEqual(1, self.rules.HCGroupMembers(1, .6))
        self.assertEqual(12, self.rules.HCGroupMembers(20, 1.3))
        self.assertEqual(.6, self.rules.HCGroupFactor(0))
        self.assertEqual(1.3, self.rules.HCGroupFactor(90))

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
        self.assertEqual(self.policy.MaxActiveAI, 72)
        self.assertEqual(self.policy.ObserverPolicy, 'native-eai')

    def test_policy_refuses_budgets_above_the_ceiling_and_a_non_native_observer(self):
        self.policy.MaxActiveAI = 129
        self.assertIn('MaxActiveAI', self.rules.PolicyProblem(self.policy))
        self.policy.MaxActiveAI = 72
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
        site.NumberOfAIMax = 13
        self.assertIn('size', self.rules.SiteProblem(self.policy, site))
        site.NumberOfAIMax = 6
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
        self.assertIn('AI budget', self.rules.SpawnProblem(p, 70, 1, 3, 600., False))
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
        self.assertEqual(action('patrol', 16, 2, 4.01, 2., 96., 100.), 'path chain step limit')
        self.assertEqual(action('patrol', 16, 2, 2.5, 2., 98., 100.), '')
        self.assertEqual(action('patrol', 15, 2, 4.01, 2., 96., 100.), 'continue')

    def test_snap_boundaries_preserve_original_tolerance_and_holdout_strictness(self):
        action = self.rules.ChainAction
        for kind, cap in (('patrol', 4.), ('scavenger', 4.), ('holdout', 3.5)):
            self.assertEqual(action(kind, 1, 2, 2.5, 0., 1., 10.), '')
            self.assertEqual(action(kind, 1, 2, 2.501, 0., 1., 10.), 'snap')
            self.assertEqual(action(kind, 16, 2, cap, 0., 1., 10.), 'snap')
            self.assertNotEqual(action(kind, 1, 2, cap + .001, 0., 1., 10.), 'snap')
            self.assertEqual(action(kind, 1, 1, 3., 0., 1., 10.), 'no path')
            self.assertEqual(action(kind, 1, 2, 3., 0., 81., 10.), 'detour too long')

    def test_snap_keeps_a_point_only_beyond_half_a_metre_of_the_last_kept_point(self):
        keeps = self.rules.SnapKeeps
        last = (100., 0., 100.)
        self.assertFalse(keeps(last, last))
        self.assertFalse(keeps(last, (100.4, 0., 100.)))
        self.assertFalse(keeps(last, (100.5, 0., 100.)))
        self.assertTrue(keeps(last, (100.6, 0., 100.)))
        self.assertTrue(keeps(last, (100., 0.6, 100.)))

    def test_route_gap_is_the_nearest_qualified_patrol_point_to_the_anchor(self):
        gap = self.rules.RouteGap
        self.assertEqual(100000, gap(A(), (0., 0., 0.)))
        self.assertAlmostEqual(5., gap(A([(30., 0., 0.), (3., 0., 4.)]), (0., 0., 0.)))

    def test_encounter_binds_only_a_qualified_owned_unbound_patrol_inside_its_activation_radius(self):
        problem = self.rules.EncounterProblem
        self.assertEqual('', problem(True, True, False, 650., 650.))
        self.assertIn('qualified', problem(False, True, False, 1., 650.))
        self.assertIn('patrol', problem(True, False, False, 1., 650.))
        self.assertIn('bound', problem(True, True, True, 1., 650.))
        self.assertIn('ActivationRadius', problem(True, True, False, 650.01, 650.))
        self.assertIn('ActivationRadius', problem(True, True, False, 0., 0.))

    def test_encounter_session_token_is_per_process_and_refuses_unreconciled_sessions(self):
        token = self.rules.EncounterToken
        self.assertEqual('xai-7-1763400000', token(7, 1763400000))
        self.assertNotEqual(token(7, 1763400000), token(8, 1763400000))
        self.assertNotEqual(token(7, 1763400000), token(7, 1763400001))
        self.assertEqual('', token(0, 1763400000))
        self.assertEqual('', token(7, 0))

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
                self.assertTrue(text.startswith('chain-v4|1.30.164289|'), text)

    def test_no_kind_can_reuse_success_without_regenerating_snaps_and_skips(self):
        self.assertFalse(self.rules.ReuseQualifiedRoute('holdout'))
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
        self.path_fake = None
        self.rows = []
        self.cached = None
        self.samples = []
        self.terrain = lambda x, z: 0.
        self.env = dict(A=A, Print=self.logs.append, HCXAITestArray=A,
                        HCXAIRouteRow=lambda: N(),
                        vector=N(Distance=math.dist, Zero=(0., 0., 0.)),
                        Vector=lambda x, y, z: (float(x), float(y), float(z)),
                        Math=N(AbsFloat=abs),
                        eAIWaypointBehavior=N(HALT=0))
        rules_source = (SCRIPTS / 'HCXAISiteRules.c').read_text()
        self.rules = api(rules_source, self.env)
        self.env['HCXAISiteRules'] = self.rules
        self.world = N(FindPath=self.find_path, SampleNavmeshPosition=lambda *args: True)
        self.env['GetGame'] = lambda: N(GetWorld=lambda: N(GetAIWorld=lambda: self.world),
                                        SurfaceY=lambda x, z: self.terrain(x, z))
        # Authored's existing type adapter handles HCXAI* names and constructors.
        source = (SCRIPTS / 'HCXAISites.c').read_text().replace('TVectorArray', 'HCXAITestArray').replace('AIWorld world', 'HCXAITestWorld world')
        source = re.sub(r'([\w.]+\.Count\(\))\.ToString\(\)', r'str(\1)', source)
        self.authored = Authored(source, self.env)
        # Two distinct synthetic filter identities: the Expansion-matching navmesh
        # filter (INSIDE allowed) and the outdoor-ground filter (INSIDE excluded).
        self.navmesh_filter = object()
        self.outdoor_filter = object()
        self.owner = N(m_Filter=self.navmesh_filter, m_OutdoorFilter=self.outdoor_filter,
                       RouteRow=lambda key: self.cached, Remember=self.rows.append,
                       NavSample=self.nav_sample)
        for method in ('Refuse', 'RefuseOrRetry', 'OutdoorSample', 'GroundSample'):
            setattr(self.owner, method, lambda *args, m=method: self.authored.call(m, self.owner, *args))
        # Default synthetic sampler: the navmesh filter keeps the wanted point,
        # the outdoor filter finds nothing (so no outdoor retry geometry exists).
        self.sample_fake = lambda wanted, radius, used: wanted if used is self.navmesh_filter else (0., 0., 0.)
        self.state = N(Site=N(Id='synthetic-town', Kind='patrol', Behaviour='ALTERNATE'),
                       Key='synthetic-key', Points=A([(100., 0., 100.), (220., 0., 100.)]),
                       Sampled=A([(100., 0., 100.), (220., 0., 100.)]),
                       PatrolPoints=A([(100., 0., 100.)]), Leg=0, Qualified=False, Cached=False,
                       Failed=False, Reason='', ChainSteps=0, ChainLength=0.,
                       ChainFrom=(0., 0., 0.), ClosestEnd=(0., 0., 0.), ClosestGap=0.,
                       PathCalls=0, Continuations=0, AttemptPoints=A(), StartIndex=0, Kept=1,
                       Skipped=0, Snapped=0, SkippedPoints='', Closed=False, OpenRoute=False,
                       OutdoorPass=False, Outdoor=0)

    def nav_sample(self, wanted, radius, used):
        self.samples.append((wanted, radius, used))
        return self.sample_fake(wanted, radius, used)

    def find_path(self, start, goal, filter_used, output):
        self.calls.append((start, goal, filter_used))
        if self.path_fake:
            result, points = self.path_fake(start, goal)
        else:
            result, points = self.paths.pop(0)
        output.extend(points)
        return result

    def step(self):
        previous = len(self.calls)
        self.authored.call('QualifyStep', self.owner, self.state)
        self.assertLessEqual(len(self.calls) - previous, 1)

    def finish(self):
        for _ in range(180):
            if self.state.Qualified or self.state.Failed:
                return
            self.step()
        self.fail('qualifier did not terminate within its bounded synthetic schedule')

    def observed(self, site_id, leg, start, target, closest, snap=False):
        # The refused leg uses the observed coordinates. All other connectivity
        # is an EXPLICIT SYNTHETIC SUCCESS, not a prediction of the DayZ server.
        data = next(s for s in json.loads((AI / 'sites.json').read_text())['Sites']
                    if s['Id'] == site_id)
        self.state.Site = N(Id=site_id, Kind=data['Kind'], Behaviour=data['Behaviour'])
        if data['Kind'] == 'holdout':
            points = [start, target, (start[0] + 12., start[1], start[2] + 12.)]
        else:
            points = [tuple(p) for p in data['Waypoints']]
            points[leg], points[leg + 1] = start, target
        self.state.Sampled = A(points)
        self.state.Points = A(points)
        self.state.PatrolPoints = A([points[0]])
        def fake(origin, goal):
            if goal == target:
                return True, [origin, closest]
            return True, [origin, goal]
        self.path_fake = fake
        self.finish()
        self.assertTrue(self.state.Qualified, self.state.Reason)
        self.assertEqual((self.state.Skipped, self.state.Snapped), (int(not snap), int(snap)))
        self.assertNotIn(target, self.state.PatrolPoints)
        self.assertEqual(self.state.Kept, len(points) - int(not snap))
        next_calls = [c for c in self.calls if c[1] == points[leg + 2]]
        self.assertEqual(next_calls[0][0], closest if snap else start)
        if not snap:
            self.assertNotIn(closest, self.state.PatrolPoints)  # failed attempt rolled back
        else:
            self.assertIn(closest, self.state.PatrolPoints)
        self.assertEqual(len(self.logs), 1)
        self.assertIn('skipped=%d snapped=%d' % (int(not snap), int(snap)), self.logs[0])
        self.assertIn('chain-v4', self.logs[0])
        self.assertIn('sampling=navmesh outdoor=0/%d' % len(points), self.logs[0])

    def test_observed_police_chernogorsk_stall_skips_target_two(self):
        self.observed('police-chernogorsk', 1, (6571.17, 6.41307, 2533.65),
                      (6631.42, 6.30214, 2504.04), (6571.7, 6.45731, 2533.3))

    def test_observed_police_elektrozavodsk_stall_skips_target_one(self):
        self.observed('police-elektrozavodsk', 0, (10403.4, 5.97355, 2209.93),
                      (10538.6, 6.23878, 2271.77), (10405., 5.97355, 2210.3))

    def test_observed_police_berezino_stall_skips_target_two(self):
        self.observed('police-berezino', 1, (11994.5, 54.1155, 9023.1),
                      (12067.3, 54.01, 9145.8), (11995.9, 54.0451, 9026.3))

    def test_observed_mil_tisy_stall_skips_target_one(self):
        self.observed('mil-tisy', 0, (1684.98, 447.921, 14219.3),
                      (1710.85, 451.82, 14279.3), (1694.9, 449.68, 14224.7))

    def test_observed_scav_vybor_near_miss_snaps_target_two(self):
        self.observed('scav-vybor', 1, (3878.33, 310.988, 8939.24),
                      (3784.31, 313.466, 9047.), (3783.6, 315.973, 9048.), snap=True)

    def test_observed_scav_novodmitrovsk_stall_skips_target_two(self):
        self.observed('scav-novodmitrovsk', 1, (11589.8, 43.1465, 14453.1),
                      (11702.5, 36.733, 14356.1), (11592.7, 43.2328, 14453.4))

    def test_observed_holdout_mogilevka_near_miss_snaps_target_one(self):
        self.observed('holdout-mogilevka', 0, (7556.67, 214.573, 5148.83),
                      (7559.6, 214., 5142.52), (7562.5, 215., 5143.2), snap=True)

    def test_snap_that_never_left_the_last_kept_point_is_skipped_not_duplicated(self):
        # SYNTHETIC: the next waypoint is 3 m away and FindPath stalls on the
        # last kept point, so the near miss is that same point.
        a, b, c, d = (100., 0., 100.), (103., 0., 100.), (160., 0., 100.), (220., 0., 100.)
        self.state.Sampled = A([a, b, c, d])
        self.state.Points = A([a, b, c, d])
        self.state.PatrolPoints = A([a])
        self.path_fake = lambda origin, goal: (True, [origin, origin]) if goal == b else (True, [origin, goal])
        self.finish()
        self.assertTrue(self.state.Qualified, self.state.Reason)
        self.assertEqual([a, c, d], list(self.state.PatrolPoints))
        self.assertEqual((1, 0, 3), (self.state.Skipped, self.state.Snapped, self.state.Kept))
        self.assertIn(' 1|', self.state.SkippedPoints)

    def test_snap_keeps_the_current_path_end_not_an_earlier_closer_attempt(self):
        # SYNTHETIC: a continuation step, then a near miss. The kept point is the
        # end of the path that qualified the snap, after the committed step.
        a, c, d = (100., 0., 100.), (160., 0., 100.), (220., 0., 100.)
        step = (130., 0., 100.)
        near = (157., 0., 100.)
        self.state.Sampled = A([a, c, d])
        self.state.Points = A([a, c, d])
        self.state.PatrolPoints = A([a])
        def fake(origin, goal):
            if goal == c and origin == a:
                return True, [origin, step]
            if goal == c:
                return True, [origin, near]
            return True, [origin, goal]
        self.path_fake = fake
        self.finish()
        self.assertTrue(self.state.Qualified, self.state.Reason)
        self.assertEqual([a, step, near, d], list(self.state.PatrolPoints))
        self.assertEqual(1, self.state.Snapped)

    def isolated_navmesh(self, site_id, legacy, islands, closest, outdoor):
        """Round 3 fixture: explicit SYNTHETIC navmesh, not DayZ evidence.

        legacy: the navmesh-filter (INSIDE allowed) samples; observed refusal
        coordinates where the server logged them, synthetic otherwise.
        islands: index groups that connect to each other; every other leg ends
        at a dead end next to its start (closest given where observed) and
        then stalls, which is the shape of all four observed refusals.
        outdoor: per index, the outdoor-ground sample (INSIDE excluded) or None;
        all outdoor samples connect (explicit synthetic success)."""
        data = next(s for s in json.loads((AI / 'sites.json').read_text())['Sites']
                    if s['Id'] == site_id)
        self.assertEqual(len(data['Waypoints']), len(legacy))
        for authored, sampled in zip(data['Waypoints'], legacy):
            self.assertLess(math.dist((authored[0], authored[2]), (sampled[0], sampled[2])), 12.)
        self.state.Site = N(Id=site_id, Kind=data['Kind'], Behaviour=data['Behaviour'])
        self.state.Points = A(legacy)
        self.state.Sampled = A()
        self.state.PatrolPoints = A()
        island_of = {legacy[i]: k for k, group in enumerate(islands) for i in group}
        index_of = {point: i for i, point in enumerate(legacy)}
        ground = set(o for o in outdoor if o)
        heights = {(o[0], o[2]): o[1] for o in ground}
        dead = set()
        def sample(wanted, radius, used):
            if used is self.navmesh_filter:
                return wanted
            if wanted in index_of and outdoor[index_of[wanted]]:
                return outdoor[index_of[wanted]]
            return (0., 0., 0.)
        self.sample_fake = sample
        self.terrain = lambda x, z: heights.get((x, z), 0.)
        def path(origin, goal):
            if origin in ground and goal in ground:
                return True, [origin, goal]
            if origin in dead:
                return True, [origin, origin]
            if origin in island_of and island_of.get(goal) == island_of[origin]:
                return True, [origin, goal]
            end = closest.get((index_of.get(origin), index_of.get(goal)), (origin[0] + .6, origin[1], origin[2]))
            dead.add(end)
            return True, [origin, end]
        self.path_fake = path
        self.finish()

    def assert_outdoor_rescue(self, outdoor):
        self.assertTrue(self.state.Qualified, self.state.Reason)
        self.assertTrue(self.state.OutdoorPass)
        count = len(outdoor)
        self.assertEqual(self.state.Outdoor, count)
        # The patrol walks only reached outdoor points, in order.
        self.assertEqual(self.state.PatrolPoints, outdoor)
        self.assertEqual(self.state.Kept, count)
        self.assertEqual(len(self.calls), self.state.PathCalls)
        self.assertLessEqual(self.state.PathCalls, 96)
        self.assertEqual(len(self.logs), 2, self.logs)
        self.assertIn('route retry with outdoor ground samples (outdoor=%d/%d) after: route minimum' % (count, count),
                      self.logs[0])
        self.assertIn('chain-v4', self.logs[1])
        self.assertIn('sampling=outdoor outdoor=%d/%d' % (count, count), self.logs[1])
        self.assertIn('behaviour=LOOP', self.logs[1])
        # Every FindPath after the retry runs between outdoor samples on the
        # unchanged Expansion-matching filter.
        retry_calls = self.calls[-count:]
        self.assertEqual([c[1] for c in retry_calls], outdoor[1:] + outdoor[:1])
        self.assertTrue(all(c[2] is self.navmesh_filter for c in self.calls))

    def shifted(self, legacy):
        # Explicit synthetic outdoor ground points 9 m east and 9 m north.
        return [(p[0] + 9., p[1], p[2] + 9.) for p in legacy]

    # Observed refusal (release with chain-v3, verbatim): leg 3: path chain stalled;
    # from=|6571.17,6.41307,2533.65; to=|6708.72,3.06291,2555.77; closest=|6571.7,6.45731,2533.3; gap=138.892; steps=2
    def test_observed_police_chernogorsk_isolated_kept_pair_requalifies_on_outdoor_ground(self):
        legacy = [(6564.47, 6.4, 2551.96), (6571.17, 6.41307, 2533.65), (6631.42, 6.30214, 2504.04),
                  (6652.29, 5.0, 2508.92), (6708.72, 3.06291, 2555.77)]
        closest = {(1, 2): (6571.7, 6.45731, 2533.3), (1, 4): (6571.7, 6.45731, 2533.3)}
        outdoor = self.shifted(legacy)
        self.isolated_navmesh('police-chernogorsk', legacy, [{0, 1}, {2}, {3}, {4}], closest, outdoor)
        self.assert_outdoor_rescue(outdoor)

    # Observed: leg 3: path chain stalled; from=|10517.8,6.09771,2327.14; to=|10457.1,6.0694,2355.9;
    # closest=|10516.6,6.09771,2327.6; gap=65.8873; steps=2 (earlier: point 0 stalled at 10405.0,5.97355,2210.3).
    def test_observed_police_elektrozavodsk_isolated_kept_pair_requalifies_on_outdoor_ground(self):
        legacy = [(10403.4, 5.97355, 2209.93), (10538.6, 6.23878, 2271.77), (10517.8, 6.09771, 2327.14),
                  (10494.88, 6.1, 2346.99), (10457.1, 6.0694, 2355.9)]
        closest = {(0, 1): (10405., 5.97355, 2210.3), (2, 4): (10516.6, 6.09771, 2327.6)}
        outdoor = self.shifted(legacy)
        self.isolated_navmesh('police-elektrozavodsk', legacy, [{0}, {1, 2}, {3}, {4}], closest, outdoor)
        self.assert_outdoor_rescue(outdoor)

    # Observed: leg 3: path chain stalled; from=|11994.5,54.1155,9023.1; to=|11995.8,54.0662,9109.17;
    # closest=|11995.9,54.0451,9026.3; gap=82.8702; steps=2
    def test_observed_police_berezino_isolated_kept_pair_requalifies_on_outdoor_ground(self):
        legacy = [(11983.84, 54.2, 9040.77), (11994.5, 54.1155, 9023.1), (12067.3, 54.01, 9145.8),
                  (12039.64, 54.0, 9132.38), (11995.8, 54.0662, 9109.17)]
        closest = {(1, 2): (11995.9, 54.0451, 9026.3), (1, 4): (11995.9, 54.0451, 9026.3)}
        outdoor = self.shifted(legacy)
        self.isolated_navmesh('police-berezino', legacy, [{0, 1}, {2}, {3}, {4}], closest, outdoor)
        self.assert_outdoor_rescue(outdoor)

    # Observed: leg 2: path chain stalled; from=|11589.8,43.1465,14453.1; to=|11559.1,33.297,14272;
    # closest=|11588.1,43.0328,14450.1; gap=180.664; steps=2
    def test_observed_scav_novodmitrovsk_isolated_kept_pair_requalifies_on_outdoor_ground(self):
        legacy = [(11579.02, 50., 14599.06), (11589.8, 43.1465, 14453.1), (11702.5, 36.733, 14356.1),
                  (11559.1, 33.297, 14272.)]
        closest = {(1, 2): (11592.7, 43.2328, 14453.4), (1, 3): (11588.1, 43.0328, 14450.1)}
        outdoor = self.shifted(legacy)
        self.isolated_navmesh('scav-novodmitrovsk', legacy, [{0, 1}, {2}, {3}], closest, outdoor)
        self.assert_outdoor_rescue(outdoor)

    def test_isolated_kept_pair_restarts_from_a_later_point_before_any_outdoor_retry(self):
        # Synthetic: points 0 and 1 share an island, 2..4 connect. A kept pair
        # that cannot reach the minimum no longer ends the first pass.
        legacy = [(100. + i * 40., 0., 100.) for i in range(5)]
        self.state.Site = N(Id='synthetic-town', Kind='patrol', Behaviour='LOOP')
        self.state.Points = A(legacy)
        self.state.Sampled = A()
        self.state.PatrolPoints = A()
        group = {legacy[0]: 0, legacy[1]: 0, legacy[2]: 1, legacy[3]: 1, legacy[4]: 1}
        dead = set()
        def path(a, b):
            if a in dead: return True, [a, a]
            if a in group and group.get(b) == group[a]: return True, [a, b]
            end = (a[0] + .6, a[1], a[2])
            dead.add(end)
            return True, [a, end]
        self.path_fake = path
        self.finish()
        self.assertTrue(self.state.Qualified, self.state.Reason)
        self.assertFalse(self.state.OutdoorPass)
        self.assertEqual((self.state.Kept, self.state.Skipped, self.state.StartIndex), (3, 2, 2))
        self.assertEqual(self.state.PatrolPoints, legacy[2:])
        self.assertTrue(self.state.Closed)
        self.assertEqual(len(self.logs), 1)
        self.assertIn('sampling=navmesh outdoor=0/5', self.logs[0])
        self.assertIn('skipped-points= 0|100.0,0.0,100.0 1|140.0,0.0,100.0', self.logs[0])
        self.assertFalse([s for s in self.samples if s[2] is self.outdoor_filter])

    def test_outdoor_sample_takes_ground_at_the_terrain_point_first(self):
        wanted = (500., 10., 500.)
        ground = (506., 10.4, 503.)
        self.terrain = lambda x, z: 10.
        self.sample_fake = lambda w, r, f: ground if f is self.outdoor_filter else w
        self.assertEqual(self.owner.OutdoorSample(wanted), ground)
        self.assertEqual(self.samples, [(wanted, 16, self.outdoor_filter)])

    def test_outdoor_sample_refuses_roofs_and_takes_the_nearest_ground_probe(self):
        wanted = (500., 10., 500.)
        roof = (501., 17., 501.)  # synthetic flat roof 7 m above the terrain
        near = (510., 10., 501.)
        far = (500., 10.5, 486.)
        def sample(w, r, f):
            if w == wanted: return roof
            if w == (512., 10., 500.): return near
            if w == (500., 10., 488.): return far
            return (0., 0., 0.)
        self.terrain = lambda x, z: 10.
        self.sample_fake = sample
        self.assertEqual(self.owner.OutdoorSample(wanted), near)
        self.assertEqual([(s[0], s[1]) for s in self.samples],
                         [(wanted, 16), ((512., 10., 500.), 8), ((488., 10., 500.), 8),
                          ((500., 10., 512.), 8), ((500., 10., 488.), 8)])
        self.assertTrue(all(s[2] is self.outdoor_filter for s in self.samples))
        self.sample_fake = lambda w, r, f: roof
        self.assertEqual(self.owner.OutdoorSample(wanted), (0., 0., 0.))

    def test_no_outdoor_ground_refuses_at_once_without_a_retry_chain(self):
        self.isolated_navmesh('scav-novodmitrovsk', [(11579.02, 50., 14599.06), (11589.8, 43.1465, 14453.1),
                                                     (11702.5, 36.733, 14356.1), (11559.1, 33.297, 14272.)],
                              [{0}, {1}, {2}, {3}], {}, [None, None, None, None])
        self.assertTrue(self.state.Failed)
        self.assertTrue(self.state.Reason.startswith('outdoor=0/4; route minimum'), self.state.Reason)
        self.assertEqual(len(self.logs), 1)
        self.assertIn('route refused: outdoor=0/4; route minimum', self.logs[0])
        self.assertFalse(self.state.Qualified)

    def test_points_without_outdoor_ground_keep_their_navmesh_sample_in_the_retry(self):
        legacy = [(100. + i * 40., 0., 100.) for i in range(4)]
        outdoor = [(110., 0., 110.), None, (190., 0., 110.), (230., 0., 110.)]
        self.state.Site = N(Id='synthetic-town', Kind='scavenger', Behaviour='LOOP')
        self.state.Points = A(legacy)
        self.state.Sampled = A()
        self.state.PatrolPoints = A()
        good = set(o for o in outdoor if o)
        def sample(w, r, f):
            if f is self.navmesh_filter: return w
            if w in legacy and outdoor[legacy.index(w)]: return outdoor[legacy.index(w)]
            return (0., 0., 0.)
        self.sample_fake = sample
        self.path_fake = lambda a, b: (True, [a, b if (a in good and b in good) else a])
        self.finish()
        self.assertTrue(self.state.Qualified, self.state.Reason)
        self.assertEqual(self.state.Outdoor, 3)
        self.assertEqual(self.state.PatrolPoints, [outdoor[0], outdoor[2], outdoor[3]])
        self.assertEqual(self.state.Skipped, 1)
        self.assertIn('sampling=outdoor outdoor=3/4', self.logs[-1])
        self.assertIn(' 1|140.0,0.0,100.0', self.logs[-1])

    def test_outdoor_retry_happens_once_and_its_refusal_is_final(self):
        self.synthetic_route(4)
        self.state.Sampled = A()
        self.state.PatrolPoints = A()
        self.sample_fake = lambda w, r, f: w if f is self.navmesh_filter else (w[0], w[1], w[2] + 9.)
        self.path_fake = lambda a, b: (True, [a, a])  # synthetic: nothing connects
        self.finish()
        self.assertTrue(self.state.Failed)
        self.assertTrue(self.state.Reason.startswith('outdoor=4/4; route minimum'), self.state.Reason)
        self.assertEqual(sum('route retry' in line for line in self.logs), 1)
        self.assertIn('route refused: outdoor=4/4; route minimum', self.logs[-1])
        self.assertFalse(self.rows[-1].Qualified)
        self.assertEqual(len(self.calls), self.state.PathCalls)
        self.assertLessEqual(self.state.PathCalls, 96)

    def test_outdoor_retry_shares_the_site_budget(self):
        self.synthetic_route(3)
        self.state.PathCalls = 94  # explicit synthetic previously consumed work
        self.sample_fake = lambda w, r, f: w if f is self.navmesh_filter else (w[0], w[1], w[2] + 9.)
        self.path_fake = lambda a, b: (True, [a, a])
        self.finish()
        self.assertTrue(self.state.Failed)
        self.assertEqual(self.state.PathCalls, 96)
        self.assertTrue(self.state.Reason.startswith('route minimum'), self.state.Reason)
        self.assertFalse(self.state.OutdoorPass)
        self.assertFalse([s for s in self.samples if s[2] is self.outdoor_filter])

    def test_holdout_refusal_never_samples_outdoors(self):
        self.synthetic_route(3, 'holdout', 'ALTERNATE')
        self.state.Sampled = A()
        self.state.PatrolPoints = A()
        self.sample_fake = lambda w, r, f: w if f is self.navmesh_filter else (w[0], w[1], w[2] + 9.)
        self.path_fake = lambda a, b: (True, [a, a])
        self.finish()
        self.assertTrue(self.state.Failed)
        self.assertTrue(self.state.Reason.startswith('route minimum'), self.state.Reason)
        self.assertFalse(self.state.OutdoorPass)
        self.assertEqual({(s[1], s[2]) for s in self.samples}, {(2, self.navmesh_filter)})
        self.assertFalse([line for line in self.logs if 'retry' in line])

    def synthetic_route(self, count=4, kind='patrol', behaviour='LOOP'):
        self.state.Site.Kind = kind
        self.state.Site.Behaviour = behaviour
        self.state.Sampled = A((100. + i * 30., 0., 100.) for i in range(count))
        self.state.Points = A(self.state.Sampled)
        self.state.PatrolPoints = A([self.state.Sampled[0]])

    def test_unreachable_first_point_is_dropped_and_later_points_are_retried(self):
        self.synthetic_route()
        first = self.state.Sampled[0]
        self.path_fake = lambda a, b: (True, [a, a if a == first else b])
        self.finish()
        self.assertTrue(self.state.Qualified, self.state.Reason)
        self.assertEqual((self.state.Kept, self.state.Skipped), (3, 1))
        self.assertEqual(self.state.PatrolPoints, self.state.Sampled[1:])
        self.assertIn('0|100.0,0.0,100.0', self.logs[-1])

    def test_closing_refusal_uses_once_and_discards_partial_closing_geometry(self):
        self.synthetic_route()
        first = self.state.Sampled[0]
        partial = (110., 0., 101.)
        self.path_fake = lambda a, b: (True, [a, partial if b == first else b])
        self.finish()
        self.assertTrue(self.state.Qualified, self.state.Reason)
        self.assertTrue(self.state.OpenRoute)
        self.assertEqual(self.state.PatrolPoints, self.state.Sampled)
        self.assertIn('behaviour=ONCE', self.logs[-1])
        self.assertEqual(self.rules.PatrolBehaviour('LOOP', True), 'ONCE')

    def test_closing_near_miss_never_moves_the_qualified_first_point(self):
        self.synthetic_route()
        first = self.state.Sampled[0]
        self.path_fake = lambda a, b: (True, [a, (103., 0., 100.) if b == first else b])
        self.finish()
        self.assertTrue(self.state.Qualified, self.state.Reason)
        self.assertTrue(self.state.OpenRoute)
        self.assertEqual(self.state.PatrolPoints, self.state.Sampled)
        self.assertEqual(self.state.Snapped, 0)

    def test_closing_near_miss_keeps_stepping_and_closes_the_loop(self):
        self.synthetic_route()
        first = self.state.Sampled[0]
        near = (103., 0., 100.)
        def path(a, b):
            if b == first and a != near: return (True, [a, near])
            return (True, [a, b])
        self.path_fake = path
        self.finish()
        self.assertTrue(self.state.Qualified, self.state.Reason)
        self.assertFalse(self.state.OpenRoute)
        self.assertTrue(self.state.Closed)
        self.assertIn('behaviour=LOOP', self.logs[-1])

    def test_site_budget_refuses_before_findpath_call_97_even_for_closure(self):
        self.synthetic_route(3)
        self.state.PathCalls = 95  # explicit synthetic previously consumed work
        self.path_fake = lambda a, b: (True, [a, b])
        self.finish()
        self.assertTrue(self.state.Failed)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.state.PathCalls, 96)
        self.assertIn('route search budget', self.state.Reason)

    def test_accumulated_site_budget_bounds_retries_on_all_unreachable_targets(self):
        self.synthetic_route(8)
        self.state.Sampled = A((1000. + i * 100., 0., 100.) for i in range(8))
        self.state.PatrolPoints = A([self.state.Sampled[0]])
        # Each attempt advances 1 m per call and exhausts its 16-call cap;
        # skipped targets are retried from the same kept start, never that end.
        self.path_fake = lambda a, b: (True, [a, (a[0] + 1., a[1], a[2])])
        self.finish()
        self.assertTrue(self.state.Failed)
        self.assertIn('route search budget', self.state.Reason)
        self.assertEqual(len(self.calls), 96)
        self.assertEqual(self.state.PathCalls, 96)
        self.assertEqual(self.state.Skipped, 6)
        self.assertEqual(self.state.PatrolPoints, [self.state.Sampled[0]])
        self.assertEqual([self.calls[i][0] for i in range(0, 96, 16)],
                         [self.state.Sampled[0]] * 6)

    def test_no_path_and_detour_refusals_skip_without_leaking_tentative_points(self):
        for failure in ('no path', 'detour too long'):
            with self.subTest(failure=failure):
                self.setUp()
                self.synthetic_route(4)
                bad = self.state.Sampled[1]
                def fake(a, b):
                    if b == bad:
                        if failure == 'no path':
                            return False, [a, b]  # false output must be ignored
                        return True, [a, (a[0], 0., 1000.), b]
                    return True, [a, b]
                self.path_fake = fake
                self.finish()
                self.assertTrue(self.state.Qualified, self.state.Reason)
                self.assertEqual(self.state.Skipped, 1)
                self.assertEqual(self.state.PatrolPoints, [self.state.Sampled[0]] + self.state.Sampled[2:])

    def test_unsnapped_tolerance_keeps_authored_target_and_next_start(self):
        self.synthetic_route(3, behaviour='ALTERNATE')
        target = self.state.Sampled[1]
        self.path_fake = lambda a, b: (True, [a, (b[0] - 2.5, b[1], b[2])])
        self.finish()
        self.assertTrue(self.state.Qualified, self.state.Reason)
        self.assertEqual(self.state.Snapped, 0)
        self.assertEqual(self.calls[1][0], target)
        self.assertEqual(self.state.PatrolPoints, self.state.Sampled)

    def test_minimum_counts_authored_points_not_continuation_endpoints(self):
        self.synthetic_route(3)
        self.paths = [(True, [(100., 0., 100.), (110., 0., 100.)]),
                      (True, [(110., 0., 100.), (130., 0., 100.)]),
                      (False, [])]
        self.finish()
        self.assertTrue(self.state.Failed)
        self.assertIn('route minimum', self.state.Reason)
        self.assertEqual(self.state.Kept, 2)

    def test_holdout_skip_keeps_two_and_never_chains_a_far_partial_path(self):
        self.synthetic_route(3, 'holdout', 'ALTERNATE')
        bad = self.state.Sampled[1]
        self.path_fake = lambda a, b: (True, [a, a if b == bad else b])
        self.finish()
        self.assertTrue(self.state.Qualified, self.state.Reason)
        self.assertEqual((self.state.Kept, self.state.Skipped), (2, 1))
        self.assertEqual(len(self.calls), 2)

    def test_oversized_authored_array_is_refused_before_any_path_call(self):
        self.synthetic_route(9)
        self.step()
        self.assertTrue(self.state.Failed)
        self.assertIn('2..8', self.state.Reason)
        self.assertEqual(self.calls, [])

    def test_expansion_config_returns_exact_qualified_points_without_replacement_or_interpolation(self):
        wanted = A([(100., 0., 100.), (140., 0., 100.), (220., 0., 100.)])
        config = N(Waypoints=wanted)
        actual = self.authored.call('GetWaypoints', config)
        self.assertEqual(actual, wanted)
        self.assertIsNot(actual, wanted)

    def test_partial_calls_chain_from_actual_end_and_preserve_patrol_points(self):
        self.state.Sampled.append((250., 0., 100.))
        self.paths = [(True, [(100., 0., 100.), (140., 0., 100.)]),
                      (True, [(140., 0., 100.), (180., 0., 100.)]),
                      (True, [(180., 0., 100.), (220., 0., 100.)]),
                      (True, [(220., 0., 100.), (250., 0., 100.)])]
        self.step()
        self.assertFalse(self.state.Failed, self.state.Reason)
        self.assertEqual(self.state.Leg, 0)
        self.step()
        self.step()
        self.step()  # qualify the third authored waypoint
        self.step()  # finish and remember only after all legs
        self.assertTrue(self.state.Qualified)
        self.assertEqual([c[0] for c in self.calls],
                         [(100., 0., 100.), (140., 0., 100.), (180., 0., 100.), (220., 0., 100.)])
        self.assertEqual(self.state.PatrolPoints,
                         [(100., 0., 100.), (140., 0., 100.), (180., 0., 100.), (220., 0., 100.), (250., 0., 100.)])
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
        self.state.Sampled.append((250., 0., 100.))
        self.paths = [(True, [(100., 0., 100.), (220., 0., 100.)]),
                      (True, [(220., 0., 100.), (250., 0., 100.)]),
                      (True, [(250., 0., 100.), (160., 0., 100.)]),
                      (True, [(160., 0., 100.), (100., 0., 100.)])]
        for _ in range(5):
            self.step()
        self.assertTrue(self.state.Qualified)
        self.assertEqual(self.state.PatrolPoints,
                         [(100., 0., 100.), (220., 0., 100.), (250., 0., 100.), (160., 0., 100.)])
        self.assertEqual(self.calls[-1][1], self.state.PatrolPoints[0])

    def test_cached_outdoor_success_rebuilds_intermediate_points_after_sampling(self):
        self.state.Sampled.append((250., 0., 100.))
        self.cached = N(Qualified=True)
        self.state.Points = A(self.state.Sampled)
        self.state.Sampled = A()
        self.state.PatrolPoints = A()
        self.step()
        self.assertFalse(self.state.Qualified)
        self.assertEqual(self.state.PatrolPoints, [(100., 0., 100.)])
        self.paths = [(True, [(100., 0., 100.), (160., 0., 100.)]),
                      (True, [(160., 0., 100.), (220., 0., 100.)]),
                      (True, [(220., 0., 100.), (250., 0., 100.)])]
        for _ in range(4):
            self.step()
        self.assertTrue(self.state.Qualified)
        self.assertIn((160., 0., 100.), self.state.PatrolPoints)

    def test_cached_holdout_success_rebuilds_the_snapped_patrol_points(self):
        self.cached = N(Qualified=True)
        self.state.Site.Kind = 'holdout'
        self.state.Points = A(self.state.Sampled)
        self.state.Sampled = A()
        self.state.PatrolPoints = A()
        self.step()
        self.assertFalse(self.state.Qualified)
        reached = (217., 0., 100.)
        self.paths = [(True, [(100., 0., 100.), reached])]
        self.finish()
        self.assertTrue(self.state.Qualified)
        self.assertFalse(self.state.Cached)
        self.assertEqual(self.state.PatrolPoints, [self.state.Sampled[0], reached])
        self.assertEqual(self.state.Snapped, 1)
        self.assertEqual(len(self.calls), 1)

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
        self.all = '\n'.join(p.read_text() for p in sorted(SCRIPTS.glob('HCXAISite*.c')) + [SCRIPTS / 'HCXAIEncounters.c'])

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
        qualify = code[code.index('protected void QualifyStep('):code.index('protected vector NavSample(')]
        self.assertEqual(qualify.count('world.FindPath('), 1)
        self.assertIn('HCXAISiteRules.ReuseQualifiedRoute(state.Site.Kind)', qualify)
        self.assertIn('if (state.Site.Kind == "") { radius = 2; }', qualify)

    def test_outdoor_ground_filter_excludes_interiors_and_findpath_keeps_the_expansion_filter(self):
        code = self.code(self.sites)
        wait = code[code.index('protected void StepWait()'):code.index('protected HCXAISiteAdmission Observe()')]
        flags = wait[wait.index('m_OutdoorFilter.SetFlags('):]
        flags = flags[:flags.index(';')]
        include, exclude, exclusive = [part.strip() for part in flags[len('m_OutdoorFilter.SetFlags('):-1].split(',')]
        self.assertEqual(include, 'PGPolyFlags.WALK')
        self.assertEqual(exclusive, 'PGPolyFlags.NONE')
        for flag in ('INSIDE', 'DOOR', 'LADDER', 'DISABLED', 'UNREACHABLE', 'SWIM', 'SWIM_SEA',
                     'JUMP', 'CLIMB', 'CRAWL', 'CROUCH'):
            self.assertIn('PGPolyFlags.' + flag + ' ', exclude + ' ')
        qualify = code[code.index('protected void QualifyStep('):code.index('protected vector NavSample(')]
        self.assertIn('world.FindPath(state.ChainFrom, legTo, m_Filter, path)', qualify)
        self.assertEqual(code.count('SampleNavmeshPosition('), 1)
        self.assertNotIn('m_OutdoorFilter', qualify)

    def test_create_uses_qualified_config_override_to_preserve_engine_path_endpoints(self):
        code = self.code(self.sites)
        self.assertIn('class HCXAISiteSpawnConfig : ExpansionAIDynamicSpawnBase', code)
        self.assertIn('override TVectorArray GetWaypoints(', code)
        create = code[code.index('protected void Create('):]
        self.assertIn('new HCXAISiteSpawnConfig()', create)
        self.assertIn('config.Behaviour = HCXAISiteRules.PatrolBehaviour(site.Behaviour, state.OpenRoute);', create)
        self.assertNotIn('if (site.Kind != "holdout") { config =', create)
        for field in ('Speed', 'UnderThreatSpeed', 'Behaviour', 'Faction', 'Loadout'):
            self.assertIn('config.' + field + ' = ', create)

    def test_create_builds_exactly_one_spawn_config(self):
        code = self.code(self.sites)
        found = re.search(r'protected void Create\(HCXAISiteState state\)\s*\{', code)
        create = block(code, found.end())
        self.assertNotIn('new ExpansionAIDynamicSpawnBase(', create)
        self.assertEqual(1, create.count(' = new HCXAISiteSpawnConfig()'))

    def test_director_exposes_states_and_owned_session_read_only_for_encounters(self):
        code = self.code(self.sites)
        self.assertIn('array<ref HCXAISiteState> States() { return m_States; }', code)
        self.assertIn('int OwnedSession()', code)

    def test_no_function_redeclares_a_local_even_in_sibling_blocks(self):
        found = []
        for filename in ('HCXAISites.c', 'HCXAISiteRules.c', 'HCXAIEncounters.c', 'HCXAIJournal.c'):
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



class ShippedDefaultsTests(unittest.TestCase):
    """Workshop-route self-provisioning (owner report 2026-11-18). Synthetic file system only;
    nothing here shows DayZ reading the PBO path, creating files or binding encounters.
    RED: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_expansion_ai_sites.ShippedDefaultsTests -v
    FileNotFoundError: ... mods/HollowCountryExpansionAI/scripts/4_World/HCXAIDefaults.c; Ran 5 tests; FAILED (errors=5).
    GREEN: same command, Ran 5 tests; OK."""
    DEFAULTS = ROOT / 'mods/HollowCountryExpansionAI/data/defaults'
    FOLDER = '$profile:ExpansionMod\\Loadouts\\'

    def setUp(self):
        self.files, self.printed = {}, []
        env = dict(A=A, Print=self.printed.append, EXPANSION_LOADOUT_FOLDER=self.FOLDER)
        env['FileExist'] = lambda path: path in self.files or path == self.FOLDER
        env['CopyFile'] = self.copy
        env['DeleteFile'] = lambda path: self.files.pop(path, None) is not None
        env['HCProfileDefaults'] = N(ReadText=lambda path: self.files.get(path, ''), WriteText=self.write)
        self.env = env
        self.defaults = api((SCRIPTS / 'HCXAIDefaults.c').read_text(), env)
        env['HCXAIDefaults'] = self.defaults
        env['HCXAISiteRules'] = N(HCMaxCatalogRows=lambda: 1024)
        declarations(env)

    def copy(self, source, target):
        self.files[target] = self.files[source]
        return True

    def write(self, path, text):
        self.files[path] = text
        return True

    def test_shipped_legacy_policy_fixture_upgrades_new_fields_and_loadouts_match(self):
        # #168 worker owns mission policy only. Upgrade the read-only legacy
        # fixture with the new defaults; lead must regenerate the packaged mirror.
        from tools.package.ai_patrols import POLICY_DEFAULTS
        shipped = json.loads((self.DEFAULTS / 'expansion-ai-sites.json').read_text())
        for key in ('RaidCooldownFloorSeconds', 'ActivationRadiusScale',
                    'MaxSignalWorkPerSecond', 'MaxBetrayalRows', 'BetrayalRetentionSeconds'):
            shipped.setdefault(key, POLICY_DEFAULTS[key])
        self.assertEqual(json.loads((AI / 'sites.json').read_text()), shipped)
        names = {s['Loadout'] for s in json.loads((AI / 'sites.json').read_text())['Sites']}
        self.assertTrue(names)
        for name in names:
            self.assertEqual((AI / 'loadouts' / (name + '.json')).read_bytes(),
                             (self.DEFAULTS / 'loadouts' / (name + '.json')).read_bytes(), name)
        for path in self.DEFAULTS.rglob('*'):
            if path.is_file():
                self.assertEqual('.json', path.suffix, path)
                self.assertLess(path.stat().st_size, 65536, path)  # HCXAISiteDirector.ReadBounded cap

    def test_missing_loadouts_are_provisioned_once_and_operator_files_are_never_overwritten(self):
        shipped = self.defaults.SHIPPED if hasattr(self.defaults, 'SHIPPED') else 'HollowCountryExpansionAI/data/defaults/'
        self.files['HollowCountryExpansionAI/data/defaults/loadouts/HollowCountry_Patrol.json'] = 'patrol'
        self.files['HollowCountryExpansionAI/data/defaults/loadouts/HollowCountry_Holdout.json'] = 'holdout'
        self.files[self.FOLDER + 'HollowCountry_Holdout.json'] = 'operator edit'
        policy = N(Sites=A([N(Loadout='HollowCountry_Patrol'), N(Loadout='HollowCountry_Patrol'),
                            N(Loadout='HollowCountry_Holdout'), N(Loadout='..\\escape'),
                            N(Loadout='HollowCountry_Missing')]))
        self.assertEqual(1, self.defaults.ProvisionLoadouts(policy))
        self.assertEqual('patrol', self.files[self.FOLDER + 'HollowCountry_Patrol.json'])
        self.assertEqual('operator edit', self.files[self.FOLDER + 'HollowCountry_Holdout.json'])
        self.assertNotIn(self.FOLDER + '..\\escape.json', self.files)
        self.assertFalse([p for p in self.files if p.endswith('.tmp')])
        self.assertEqual(1, sum('loadout default provisioned' in line for line in self.printed))
        self.assertTrue(any('HollowCountry_Missing' in line for line in self.printed))
        self.assertEqual(0, self.defaults.ProvisionLoadouts(policy))

    def test_localities_mirror_is_byte_identical_and_provisioned_without_overwrite(self):
        self.assertTrue((self.DEFAULTS / 'expansion-ai-localities.json').exists())
        self.assertEqual((AI / 'localities.json').read_bytes(),
                         (self.DEFAULTS / 'expansion-ai-localities.json').read_bytes())
        calls = []
        def ensure(name, shipped):
            calls.append((name, shipped))
            target = '$profile:HollowCountry/' + name
            if target in self.files:
                return False
            self.files[target] = self.files[shipped + name]
            return True
        self.env['HCProfileDefaults'].Ensure = ensure
        self.files[self.defaults.Shipped() + 'expansion-ai-localities.json'] = 'synthetic catalog'
        self.assertTrue(self.defaults.ProvisionLocalities())
        target = '$profile:HollowCountry/expansion-ai-localities.json'
        self.files[target] = 'operator catalog'
        self.assertFalse(self.defaults.ProvisionLocalities())
        self.assertEqual('operator catalog', self.files[target])
        self.assertEqual(2, len(calls))
        sites = (SCRIPTS / 'HCXAISites.c').read_text()
        self.assertLess(sites.index('HCXAIDefaults.ProvisionLocalities()'),
                        sites.index('m_Policy = HCXAISiteDirector.LoadPolicy()'))

    def test_loadout_provisioning_visits_beyond_64_catalog_rows(self):
        self.env['HCXAISiteRules'] = N(HCMaxCatalogRows=lambda: 1024)
        self.files[self.defaults.Shipped() + 'loadouts/HollowCountry_Last.json'] = 'last'
        policy = N(Sites=A([N(Loadout='HollowCountry_Missing')] * 64 + [N(Loadout='HollowCountry_Last')]))
        self.assertEqual(1, self.defaults.ProvisionLoadouts(policy))

    def test_shipped_policy_comparison_uses_policy_sized_reader(self):
        reads = []
        self.env['HCWorldStore'] = N(Read=lambda path: reads.append(path) or ('x' * 70000))
        self.env['HCXAISiteDirector'] = N(POLICY='operator', ReadBounded=lambda path: '')
        self.assertTrue(self.defaults.MatchesShipped())
        self.assertEqual(2, len(reads))
        source = (SCRIPTS / 'HCXAIDefaults.c').read_text()
        self.assertIn('HCWorldStore.Read(', source[source.index('static int ShippedSiteCount()'):])

    def test_readiness_reports_locality_after_null_guard(self):
        code = (SCRIPTS / 'HCXAIAdapter.c').read_text()
        method = code[code.index('    void LogReadiness('):code.index('    void LogAddonChecks()')]
        self.assertIn('Print(m_Sites.HCLocalitySummary())', method)
        self.assertLess(method.index('if (!m_Encounters || !m_Sites)'),
                        method.index('Print(m_Sites.HCLocalitySummary())'))

    def test_policy_drift_names_a_stale_operator_policy_without_replacing_it(self):
        drift = self.defaults.PolicyDrift
        self.assertEqual('', drift(True, 21, 21))
        self.assertIn('profile sites=17 shipped sites=21', drift(False, 17, 21))
        self.assertIn('operator file kept', drift(False, 17, 21))

    def test_encounter_radius_is_the_patrol_trigger_radius_and_covers_the_shipped_event_anchors(self):
        env = dict(A=A, Print=lambda *a: None)
        declarations(env)
        env['vector'] = N(Distance=lambda a, b: math.dist(a, b))
        env['Math'] = N(AbsFloat=abs)
        rules = api((SCRIPTS / 'HCXAISiteRules.c').read_text(), env)
        self.assertEqual(650., rules.EncounterRadius(650.))
        self.assertEqual(600., rules.EncounterRadius(300.))
        self.assertEqual(0., rules.EncounterRadius(0.))
        policy = json.loads((self.DEFAULTS / 'expansion-ai-sites.json').read_text())
        for anchor in json.loads((AI / 'event-sites.contract.json').read_text())['Sites']:
            fits = [s['Id'] for s in policy['Sites'] if not s.get('Checkpoint') and s['Kind'] != 'holdout'
                    and rules.RouteGap(A(tuple(w) for w in s['Waypoints']), tuple(anchor['Position']))
                    <= rules.EncounterRadius(s['ActivationRadius'])]
            self.assertTrue(fits, anchor['Id'])

    def test_director_provisions_before_reading_and_encounters_use_the_trigger_radius(self):
        sites = (SCRIPTS / 'HCXAISites.c').read_text()
        start = sites[sites.index('    void Start()'):sites.index('    void Stop()')]
        self.assertLess(start.index('HCXAIDefaults.ProvisionSites()'), start.index('LoadPolicy()'))
        self.assertIn('HCXAIDefaults.PolicyDrift(', start)
        wait = sites[sites.index('    protected void StepWait()'):sites.index('    protected HCXAISiteAdmission Observe()')]
        self.assertLess(wait.index('HCXAIDefaults.ProvisionLoadouts(m_Policy)'), wait.index('this.Observe()'))
        encounters = (SCRIPTS / 'HCXAIEncounters.c').read_text()
        # Encounters bind with the same (operator-scaled) radius the provider triggers at.
        self.assertIn('director.HCActivationRadius(state.Site, false)', encounters)
        self.assertNotIn('this.SiteBound(state.Site.Id), gap, 600)', encounters)
        self.assertIn('HCXAISiteRules.EncounterRadius(site.ActivationRadius)', sites)


if __name__ == '__main__':
    unittest.main()
