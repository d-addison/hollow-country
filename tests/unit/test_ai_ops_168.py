"""#168 spec/plan/tasks: release wiped reservations without changing raid custody;
operator cooldown/radius policy; one spawn diagnostic; bounded checkpoint retries.
Execute authored decisions with explicit synthetic clocks/groups/factories. These
tests never establish DayZ spawning, collision, perception or runtime acceptance.
Native/PBO/Diag and two-client perception checks remain pending.

RED (before source edits): PYTHONDONTWRITEBYTECODE=1 python3 -m unittest
tests.unit.test_ai_ops_168 -v; Ran 13 tests; FAILED (failures=23, errors=2).
Actual lines: AssertionError: '' != 'global AI budget reached';
TypeError: run() takes 2 positional arguments but 3 were given (operator floor);
AssertionError: Lists differ: ['[HC Expansion AI] Spawning 4 AI HC:mil-nwaf at 4622 10595'] != [];
AssertionError: missing authored method HCActivationRadius;
AssertionError: 8 != 25; AssertionError: True is not false (factory retry);
AssertionError: Lists differ: [(5000, 'Land_Roadblock_Table_DE')] != [(5000, 'Land_Roadblock_Table')].
Native validation also returned '' for invalid floors/scales; all five generated
policy defaults were absent. Config citation: installed structures_military.pbo
config.bin CfgVehicles/Land_Roadblock_Table_DE scope=2, parent Land_Roadblock_Table
(scope=1). This binary has no text lines; local resolved excerpt is
/tmp/hc-w11-aiops-checkpoint.config.cpp:10. No provider code copied.
Reader follow-up RED: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest
tests.unit.test_ai_ops_168.PolicyTests.test_reader_rejects_bad_operator_policy_and_accepts_legacy_absence -v
Ran 1 test; FAILED (failures=2); AssertionError: ValueError not raised.
Single-line follow-up RED: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest
tests.unit.test_ai_ops_168.OperationsTests.test_spawn_log_is_exact_one_rounded_xz_line -v
Ran 1 test; FAILED (failures=1); AssertionError: 1 != 2.
Enforce trap RED: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest
tests.unit.test_ai_ops_168.EnforceConstraintsTests -v; Ran 1 test;
FAILED (failures=1); AssertionError: Lists differ: [] != [23, 13].
GREEN: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_ai_ops_168 -v
Ran 16 tests; OK. Enforce lint: python3 -B -m tools.validate.enforce_lint --no-native;
pass findings=126 new=0 stale=0 native=no.
"""
import json
import math
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace as N
import unittest

from tools.package import ai_patrols
from tests.unit.test_expansion_ai_adapter import A, Authored, declarations
from tests.unit.test_expansion_ai_sites import AI, SCRIPTS, api, dto


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.env = dict(A=A, Print=self.logs.append, Math=N(Round=lambda n: math.floor(n + .5)))
        declarations(self.env)
        self.source = (SCRIPTS / 'HCXAISites.c').read_text()
        self.authored = Authored(self.source, self.env)
        self.director = N(m_States=A(), m_Policy=N(ActivationRadiusScale=0,
                          RaidCooldownFloorSeconds=0, MinPlayerDistance=200),
                          m_RadiusClampLogged=False, m_Phase='run', m_OwnedSaved=True)
        self.env['HCXAISiteDirector'] = N(Active=lambda: self.director)
        self.env['HCXAISiteDirector'].RaidCooldown = lambda *a: self.call('RaidCooldown', *a)

    def call(self, method, *args):
        if method == 'HCActivationRadius':
            args = (N(ActivationRadius=args[0]), args[1])
        return self.authored.call(method, self.director, *args)

    def patrol(self, living, pending=0):
        patrol = N(m_Group=N(Count=lambda: living), m_HCPendingMembers=pending,
                   m_HCSiteId='mil-nwaf', m_NumberOfAI=4)
        return patrol

    def state(self, patrol, transient=False):
        return N(Patrol=patrol, Transient=transient, Completed=False,
                 Materialized=bool(patrol), Site=N(Id='mil-nwaf', NumberOfAIMax=4))

    def test_wiped_group_releases_both_budget_checks_and_shared_lease(self):
        from tests.unit.ai_limits_fixture import install
        install(self.env, MaxLiveGroups=1, MaxLiveAI=4)
        wiped = self.patrol(0)
        self.director.m_States = A([self.state(wiped)])
        self.assertTrue(self.env['HCAIBudget'].TryReserve('site:mil-nwaf', 4))
        self.assertEqual('', self.call('BudgetProblem', 4, None))
        self.assertEqual(0, self.env['HCAIBudget'].Groups())
        self.director.BudgetProblem = lambda *a: self.call('BudgetProblem', *a)
        self.env['HCXAIQualification'] = N(ProviderProblem=lambda: '')
        self.env['HCXAISiteRules'] = N(SpawnProblem=lambda p, ai, sites, cap, gap, seen:
                                      '' if ai == 0 and sites == 0 else 'occupied')
        self.director.NearestPlayer = lambda p: 500
        self.director.SeenByPlayer = lambda p: False
        candidate = N(m_HCFinished=False, m_HCGroupMax=4, m_Position=(100, 0, 100))
        # Transient bypasses raid lookup only; the wiped authored reservation remains.
        self.director.m_States[0].Transient = True
        self.assertEqual('', self.call('SpawnProblemFor', candidate))

    def test_living_and_pending_members_hold_full_cap_but_dead_group_does_not(self):
        from tests.unit.ai_limits_fixture import install
        install(self.env, MaxLiveGroups=1, MaxLiveAI=4)
        for living, pending in ((1, 0), (0, 2), (1, 3)):
            with self.subTest(living=living, pending=pending):
                patrol = self.patrol(living, pending)
                self.director.m_States = A([self.state(patrol)])
                self.assertNotEqual('', self.call('BudgetProblem', 1, None))
        self.director.m_States = A([self.state(self.patrol(0))])
        self.assertEqual('', self.call('BudgetProblem', 1, None))
        self.director.m_States = A([self.state(None, True)])
        self.assertNotEqual('', self.call('BudgetProblem', 1, None))
        self.director.m_States[0].Completed = True
        self.assertEqual('', self.call('BudgetProblem', 1, None))

    def test_deferred_callbacks_drain_pending_count_and_refusal_cancels_rest(self):
        living, spawned, problem = [1], [], ['']
        patrol = self.patrol(1, 3)
        patrol.m_Group.Count = lambda: living[0]
        patrol.m_Group.SetWaypointBehaviour = lambda b: None
        patrol.m_Formation = N(ToWorld=lambda p: p, GetPosition=lambda i: (100 + i, 0, 200))
        patrol.m_HCFinished = False
        patrol.m_HCTransient = False
        patrol.m_WaypointBehaviour = 'LOOP'
        self.director.MemberProblemFor = lambda p: problem[0]
        self.director.SaveOwned = lambda: True
        self.env['ExpansionAISpawnBase'] = N(GetPlacementPosition=lambda p, safe: p)
        def deferred(patrol, index):
            living[0] += 1
            spawned.append(index)
        self.env['synthetic_deferred'] = deferred
        authored = Authored(self.source.replace('super.SpawnAI_Deferred(i);',
                                               'synthetic_deferred(this, i);'), self.env)
        for index, remaining in ((1, 2), (2, 1), (3, 0)):
            authored.call('SpawnAI_Deferred', patrol, index)
            self.assertEqual(remaining, patrol.m_HCPendingMembers)
        self.assertEqual([1, 2, 3], spawned)
        problem[0] = 'synthetic observer veto'
        patrol.m_HCPendingMembers = 3
        authored.call('SpawnAI_Deferred', patrol, 1)
        self.assertEqual(0, patrol.m_HCPendingMembers)
        self.assertEqual(4, patrol.m_NumberOfAI)
        self.assertEqual([1, 2, 3], spawned)
        patrol.m_HCTransient = True
        patrol.m_HCPendingMembers = 2
        living[0] = 0
        reasons = []
        patrol.HCRefuseBudget = lambda *reason: reasons.append(reason)
        authored.call('SpawnAI_Deferred', patrol, 1)
        self.assertEqual(0, patrol.m_HCPendingMembers)
        self.assertEqual([('transient group emptied before member spawn',)], reasons)

    def test_raid_floor_defaults_override_respawn_and_lock_boundary(self):
        site = N(Id='mil-nwaf', Kind='patrol', RespawnSeconds=900)
        self.assertEqual(604800, self.call('RaidCooldown', site))
        self.assertEqual(1800, self.call('RaidCooldown', site, 1800))
        site.RespawnSeconds = 7200
        self.assertEqual(7200, self.call('RaidCooldown', site, 1800))
        site.Id = 'police-synthetic'
        self.assertEqual(21600, self.call('RaidCooldown', site))
        site.Kind = 'holdout'
        self.assertEqual(604800, self.call('RaidCooldown', site))
        self.director.m_Owned = N(Rows=A([N(SiteId=site.Id, ClearedAt=100)]))
        self.director.m_Policy.RaidCooldownFloorSeconds = 1800
        site.RespawnSeconds = 900
        self.assertTrue(self.call('RaidLocked', site, 1899))
        self.assertFalse(self.call('RaidLocked', site, 1900))
        self.assertEqual(100, self.director.m_Owned.Rows[0].ClearedAt)
        self.assertIn('raid cooldown floor ', self.source)
        self.assertIn('HCXAISiteDirector.RaidCooldown(site, m_Policy.RaidCooldownFloorSeconds)', self.source)

    def test_spawn_log_is_exact_one_rounded_xz_line(self):
        patrol = self.patrol(1, 3)
        patrol.m_Position = (4621.51, 339.74, 10595.41)
        patrol.m_HCKind = 'patrol'
        self.director.SaveOwned = lambda: True
        self.call('Spawned', patrol)
        lines = [s for s in self.logs if 'Spawning ' in s]
        self.assertEqual(['[HC Expansion AI] Spawning 4 AI HC:mil-nwaf at 4622 10595'], lines)
        self.assertEqual(1, len(self.logs))
        self.assertEqual(1, self.source.count('"[HC Expansion AI] Spawning '))

    def test_activation_scale_zero_defaults_clamps_and_logs_once(self):
        self.env['HCXAISiteRules'] = N(EncounterRadius=lambda r: max(r, 600))
        self.assertEqual(650, self.call('HCActivationRadius', 650, False))
        self.assertEqual(600, self.call('HCActivationRadius', 300, False))
        self.director.m_Policy.ActivationRadiusScale = .5
        self.assertEqual(325, self.call('HCActivationRadius', 650, False))
        self.assertEqual(250, self.call('HCActivationRadius', 300, True))
        self.director.m_Policy.ActivationRadiusScale = 2
        self.assertEqual(1200, self.call('HCActivationRadius', 650, False))
        self.assertEqual(1200, self.call('HCActivationRadius', 650, False))
        self.assertEqual(1, sum('activation radius clamped' in line for line in self.logs))
        self.assertIn('config.MaxDistRadius = this.HCActivationRadius(site, state.Transient);', self.source)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.env = dict(A=A, Math=N(AbsFloat=abs), vector=N(Distance=math.dist))
        declarations(self.env)
        self.env['HCXAIRules'] = api((SCRIPTS / 'HCXAIRules.c').read_text(), self.env)
        self.rules = api((SCRIPTS / 'HCXAISiteRules.c').read_text(), self.env)
        self.env['HCXAISiteRules'] = self.rules
        self.data = json.loads((AI / 'sites.json').read_text())
        self.policy = dto(self.env, 'HCXAISitePolicy', self.data)

    def test_new_policy_keys_defaults_and_generated_profiles(self):
        expected = dict(RaidCooldownFloorSeconds=0, ActivationRadiusScale=0.0,
                        MaxSignalWorkPerSecond=8, MaxBetrayalRows=128,
                        BetrayalRetentionSeconds=172800)
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(value, ai_patrols.POLICY_DEFAULTS.get(key))
                self.assertEqual(value, self.data.get(key))
        self.assertEqual('', self.rules.PolicyProblem(self.policy))

    def test_native_validation_rejects_bad_floors_and_scales(self):
        for key, values in (('RaidCooldownFloorSeconds', (-1, 1, 1799, 604801)),
                            ('ActivationRadiusScale', (-1, .49, 2.01, float('nan'), float('inf')))):
            for value in values:
                with self.subTest(key=key, value=value):
                    setattr(self.policy, key, value)
                    self.assertIn(key, self.rules.PolicyProblem(self.policy))
            setattr(self.policy, key, 0)
        for floor in (0, 1800, 604800):
            for scale in (0, .5, 1., 2.):
                self.policy.RaidCooldownFloorSeconds = floor
                self.policy.ActivationRadiusScale = scale
                self.assertEqual('', self.rules.PolicyProblem(self.policy))

    def test_python_policy_validation_types_ranges_and_absence(self):
        for policy in ({}, dict(RaidCooldownFloorSeconds=0, ActivationRadiusScale=0),
                       dict(RaidCooldownFloorSeconds=1800, ActivationRadiusScale=.5),
                       dict(RaidCooldownFloorSeconds=604800, ActivationRadiusScale=2)):
            ai_patrols.validate_policy(policy)
        for key, values in (('RaidCooldownFloorSeconds', (True, 1800., '1800', -1, 1799, 604801)),
                            ('ActivationRadiusScale', (True, '1', -.1, .49, 2.01, float('nan'), float('inf')))):
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, key):
                    ai_patrols.validate_policy({key: value})

    def test_reader_rejects_bad_operator_policy_and_accepts_legacy_absence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'synthetic-policy.json'
            for key, value in (('RaidCooldownFloorSeconds', 1799), ('ActivationRadiusScale', 3)):
                path.write_text(json.dumps({key: value}))
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, key):
                    ai_patrols.read_json(path)
            path.write_text('{}')
            self.assertEqual({}, ai_patrols.read_json(path))


class EnforceConstraintsTests(unittest.TestCase):
    def test_site_statements_have_at_most_nine_additions(self):
        source = (SCRIPTS / 'HCXAISites.c').read_text()
        source = re.sub(r'"(?:[^"\\]|\\.)*"', '""', source)
        source = re.sub(r'//[^\n]*', '', source)
        additions = [statement.count('+') for statement in source.split(';')]
        self.assertEqual([], [count for count in additions if count > 9])


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.now, self.logs, self.calls, self.nearby = 0, [], [], A()
        self.factory_ok = False
        self.director = N(NearestPlayer=lambda p: 500, SeenByPlayer=lambda p: False)
        self.game = N(GetTime=lambda: self.now, SurfaceY=lambda x, z: 0,
                      GetObjectsAtPosition=self.query, CreateObjectEx=self.create)
        self.env = dict(Print=self.logs.append, GetGame=lambda: self.game,
                        HCXAIQualification=N(EncountersEnabled=lambda: True),
                        HCXAISiteDirector=N(Active=lambda: self.director),
                        Vector=lambda *a: a, vector=N(Distance=math.dist),
                        House=N(Cast=lambda o: o.house),
                        ECE_SETUP=1, ECE_KEEPHEIGHT=2, ECE_NOLIFETIME=4)
        self.row = N(Site=N(Id='checkpoint-synthetic', CheckpointProp=(100, 0, 200)),
                     Table=None, QuietSince=-1, Finished=False, Attempts=0, LastAttempt=-1)
        self.owner = N(m_Props=A([self.row]), m_Cursor=0)
        # Annotation spelling only; the adapter supplies arrays and ignores types.
        source = (SCRIPTS / 'HCXAISites.c').read_text().split('class HCXCheckpointProps\n', 1)[1]
        source = source.replace('array<Object> objects', 'Object objects')
        source = source.replace('array<CargoBase> cargos', 'Object cargos')
        source = source.replace('HCXCheckpointProp row', 'HCXAICheckpointProp row')
        self.authored = Authored(source, dict(self.env, A=A))
        self.owner.HCRetry = lambda *a: self.authored.call('HCRetry', self.owner, *a)

    def query(self, at, radius, objects, cargos):
        self.query_radius = radius
        objects.extend(self.nearby)

    def create(self, classname, at, flags):
        self.calls.append((self.now, classname))
        return N() if self.factory_ok else None

    def step(self, now):
        self.now = now
        self.authored.call('Step', self.owner)

    def attempt(self, now):
        self.step(now)
        self.step(now + 5000)

    def test_scope_two_table_factory_and_success_finishes_once(self):
        self.factory_ok = True
        self.attempt(0)
        self.assertEqual([(5000, 'Land_Roadblock_Table_DE')], self.calls)
        self.assertTrue(self.row.Finished)
        self.step(1000000)
        self.assertEqual(1, len(self.calls))

    def test_factory_failure_retries_three_attempts_ten_minutes_apart(self):
        self.attempt(0)
        self.assertFalse(self.row.Finished)
        self.step(604999)
        self.assertEqual(1, len(self.calls))
        self.attempt(605000)
        self.assertFalse(self.row.Finished)
        self.attempt(1210000)
        self.assertTrue(self.row.Finished)
        self.step(2000000)
        self.assertEqual(3, len(self.calls))
        self.assertTrue(all(b[0] - a[0] >= 600000 for a, b in zip(self.calls, self.calls[1:])))
        self.assertEqual(1, len(self.logs))
        self.assertIn('attempts=3', self.logs[0])

    def test_house_refusal_uses_eight_meters_and_retries_without_factory(self):
        self.nearby.append(N(GetType=lambda: 'Land_Wall', house=True))
        self.attempt(0)
        self.assertEqual(8, self.query_radius)
        self.assertFalse(self.row.Finished)
        self.attempt(605000)
        self.attempt(1210000)
        self.assertTrue(self.row.Finished)
        self.assertEqual([], self.calls)
        self.assertEqual(1, len(self.logs))

    def test_existing_table_adopted_even_when_house_cast_succeeds(self):
        table = N(GetType=lambda: 'Land_Roadblock_Table_DE',
                  GetPosition=lambda: (100, 0, 200), house=True)
        # Adoption wins independently of query order, including House scenery.
        self.nearby.extend([None, N(GetType=lambda: 'Land_Wall', house=True), table])
        self.attempt(0)
        self.assertIs(table, self.row.Table)
        self.assertTrue(self.row.Finished)
        self.assertEqual([], self.calls)

    def test_refused_factory_can_succeed_later_and_rollback_does_not_hammer(self):
        self.attempt(0)
        self.assertFalse(self.row.Finished)
        self.factory_ok = True
        self.step(1000)
        self.attempt(605000)
        self.assertTrue(self.row.Finished)
        self.assertEqual(2, len(self.calls))


if __name__ == '__main__':
    unittest.main()


REPO = Path(__file__).resolve().parents[2]


class ShippedPolicyMirror(unittest.TestCase):
    """The profile-provisioning mirror must ship the same policy keys as the mission copy."""
    def test_packaged_default_matches_mission_policy(self):
        import json
        mission = json.loads((REPO / 'mission/hollow-country/ai/sites.json').read_text())
        mirror = json.loads((REPO / 'mods/HollowCountryExpansionAI/data/defaults/expansion-ai-sites.json').read_text())
        self.assertEqual(mission, mirror)

    def test_encounter_binding_uses_the_scaled_provider_radius(self):
        text = (REPO / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIEncounters.c').read_text()
        self.assertIn('director.HCActivationRadius(state.Site, false)', text)
        self.assertNotIn('HCXAISiteRules.EncounterRadius(state.Site.ActivationRadius))', text)
