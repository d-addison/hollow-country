"""HC site rules (patrols, scavenger parties, holdouts with a cache) on Expansion AI.

The authored Enforce bodies run through the syntax adapter with explicit synthetic inputs; nothing here
establishes DayZ behavior. Spawning, line of sight, despawn and cache persistence stay pending native
observation with a client.
"""
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_expansion_ai_adapter import A, Authored, declarations

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


if __name__ == '__main__':
    unittest.main()
