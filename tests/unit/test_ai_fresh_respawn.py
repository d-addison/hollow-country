"""Respawn spec/plan/tasks: short policy timers, durable death epoch, fresh native
loadouts, corpse preservation, safe whole-group replacement (private SpawnAI).
Explicit synthetic groups/clocks; no DayZ behavior is established here.
"""
import json
from types import SimpleNamespace as N
import unittest
from tests.unit import test_ai_ops_168 as ops
from tests.unit.test_expansion_ai_adapter import Authored, A
from tests.unit.test_expansion_ai_sites import SCRIPTS, AI
from tests.unit.test_hc_ai_camps import authored_camp_api, synthetic_camp


class FreshRespawnTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ops.OperationsTests()
        self.fixture.setUp()

    def test_no_hidden_military_or_holdout_floor(self):
        for kind, name in [('patrol', 'mil-synthetic'), ('holdout', 'holdout-synthetic')]:
            site = N(Id=name, Kind=kind, RespawnSeconds=900)
            self.assertEqual(900, self.fixture.call('RaidCooldown', site))
            self.assertEqual(1800, self.fixture.call('RaidCooldown', site, 1800))

    def test_policy_authority_and_transient_never_respawns(self):
        policy = N(AIRespawnSeconds=900, PatrolRespawnSeconds=120, HoldoutRespawnSeconds=180,
                   MilitaryRespawnSeconds=240, MemberReplaceSeconds=600, RaidCooldownFloorSeconds=0)
        env = self.fixture.env
        env['HCXAISiteDirector'].HCRespawnDelay = lambda *args: self.fixture.call('HCRespawnDelay', *args)
        for kind, name, delay in [('patrol', 'road', 120), ('holdout', 'home', 180),
                                  ('patrol', 'mil-base', 240), ('scavenger', 'scav', 900)]:
            site = N(Id=name, Kind=kind, RespawnSeconds=86400)
            self.assertEqual(delay, self.fixture.call('HCRespawnDelay', site, policy))

    def test_shipped_sites_use_short_timers_and_mirrors_match(self):
        defaults = self.fixture.env['HCXAISitePolicy']()
        self.assertEqual(900, defaults.AIRespawnSeconds)
        self.assertEqual(600, defaults.MemberReplaceSeconds)
        data = json.loads((AI / 'sites.json').read_text())
        self.assertEqual(900, data.get('AIRespawnSeconds'))
        self.assertEqual(600, data.get('MemberReplaceSeconds'))
        self.assertTrue(all(row['RespawnSeconds'] == 900 for row in data['Sites']))
        shipped = SCRIPTS.parents[1] / 'data/defaults/expansion-ai-sites.json'
        self.assertEqual((AI / 'sites.json').read_bytes(), shipped.read_bytes())

    def test_timer_validation_is_bounded_and_zero_inherits(self):
        fixture = ops.PolicyTests()
        fixture.setUp()
        for field in ('AIRespawnSeconds', 'PatrolRespawnSeconds', 'HoldoutRespawnSeconds',
                      'MilitaryRespawnSeconds', 'MemberReplaceSeconds'):
            prior = getattr(fixture.policy, field)
            for seconds in (0, 60, 900, 604800):
                setattr(fixture.policy, field, seconds)
                self.assertEqual('', fixture.rules.PolicyProblem(fixture.policy))
            for seconds in (-1, 1, 59, 604801):
                setattr(fixture.policy, field, seconds)
                self.assertIn('timer', fixture.rules.PolicyProblem(fixture.policy))
            setattr(fixture.policy, field, prior)

    def test_interrupted_raid_journal_never_becomes_a_fresh_epoch(self):
        fixture = self.fixture
        fixture.env['FileExist'] = lambda path: False  # Lost primary, retained intent.
        fixture.env['HCRespawnStore'] = N(CanOpen=lambda path: False)
        fixture.env['HCXAISiteDirector'].OWNED = 'synthetic-owned.json'
        authored = Authored(fixture.source.replace('HCV2ThreatStore<HCXAIOwnership>',
                                                   'HCRespawnStore').replace('JsonFileLoader<HCXAIOwnership>',
                                                                             'HCRespawnJson'), fixture.env)
        self.assertIsNone(authored.call('LoadOwned', None))

    def test_latest_kill_is_durable_but_retirement_never_restarts_clock(self):
        fixture = self.fixture
        now = [1000]
        fixture.env['ExpansionStatic'] = N(GetTimestamp=lambda utc: now[0])
        row = N(ClearedAt=0, PartialRaid=False)
        owner = fixture.director
        owner.m_Owned = N(Rows=A([row]))
        owner.OwnershipRow = lambda key: row
        images = []
        owner.SaveOwned = lambda: images.append(dict(vars(row)))
        living = [2]
        patrol = N(m_HCTransient=False, m_HCSiteId='synthetic', m_Group=N(Count=lambda: living[0]))
        fixture.call('RecordCleared', patrol, True)
        self.assertEqual({'ClearedAt': 1000, 'PartialRaid': True}, images[-1])
        now[0] = 1100
        fixture.call('RecordCleared', patrol)
        self.assertEqual(1, len(images))
        self.assertEqual(1000, row.ClearedAt)
        living[0] = 1  # Native pre-cleanup callback still includes the dying member.
        fixture.call('RecordCleared', patrol, True)
        self.assertEqual({'ClearedAt': 1100, 'PartialRaid': False}, images[-1])
        self.assertEqual(images[-1], json.loads(json.dumps(vars(row))))

    def test_detach_deceased_records_without_touching_bodies_or_inventory(self):
        corpses = A([N(gear=['rifle']), N(gear=['coat'])])
        records = A(corpses)
        patrol = N(m_Group=N(DeceasedCount=records.Count, RemoveDeceased=lambda i: records.RemoveOrdered(i)))
        authored = Authored((SCRIPTS / 'HCXAISites.c').read_text(), self.fixture.env)
        authored.call('HCPreserveBodies', patrol)
        self.assertEqual([], records)
        self.assertEqual([['rifle'], ['coat']], [body.gear for body in corpses])

    def test_depleted_group_waits_for_durable_clock_combat_and_every_observer(self):
        fixture = self.fixture
        # Syntax-only port for a native type outside the shared translator list.
        fixture.authored = Authored(fixture.source.replace('DayZPlayerImplement liveMember',
                                                         'PlayerBase liveMember').replace(
                        'array<ref HCXAISiteState> freshStates', 'HCXAISiteState freshStates'), fixture.env)
        now = [1599]
        disabled = [False]
        fixture.env['FileExist'] = lambda path: disabled[0]
        fixture.env['ExpansionStatic'] = N(GetTimestamp=lambda utc: now[0])
        death = N(ClearedAt=1000, PartialRaid=True)
        policy = N(AIRespawnSeconds=900, PatrolRespawnSeconds=900, HoldoutRespawnSeconds=900,
                   MilitaryRespawnSeconds=900, MemberReplaceSeconds=600, RaidCooldownFloorSeconds=0)
        owner = fixture.director
        owner.m_Policy = policy
        owner.OwnershipRow = lambda key: death
        owner.HCDeathDelay = lambda *args: fixture.call('HCDeathDelay', *args)
        fixture.env['HCXAISiteDirector'].HCRespawnDelay = lambda *args: fixture.call('HCRespawnDelay', *args)
        blocked = [False]
        combat = [False]
        living = [2]
        members = A([N(GetPosition=lambda: 1), N(GetPosition=lambda: 2)])
        owner.MemberProblemFor = lambda position: 'observer' if blocked[0] and position == 2 else ''
        patrol = N(m_HCSiteId='synthetic', m_HCTransient=False, m_HCPendingMembers=0,
                   m_NumberOfAI=4, m_RespawnTime=900, m_TimeSinceLastSpawn=0,
                   m_Group=N(Count=lambda: living[0], IsInCombat=lambda: combat[0],
                             GetMember=lambda index: members[index]))
        group = patrol.m_Group
        retired = []
        def retire():
            retired.append(now[0])
            patrol.m_Group = None
        patrol.Despawn = retire
        site = N(Id='synthetic', Kind='patrol', RespawnSeconds=900)
        owner.m_States = A([N(Patrol=patrol, Site=site)])
        fixture.call('HCRefreshDepleted', patrol)
        self.assertEqual([], retired)
        now[0] = 1600
        for state in ('disabled', 'combat', 'observer', 'unsaved'):
            disabled[0] = state == 'disabled'
            combat[0] = state == 'combat'
            blocked[0] = state == 'observer'
            owner.m_OwnedSaved = state != 'unsaved'
            fixture.call('HCRefreshDepleted', patrol)
            self.assertEqual([], retired, state)
        disabled[0] = combat[0] = blocked[0] = False
        owner.m_OwnedSaved = True
        fixture.call('HCRefreshDepleted', patrol)
        self.assertEqual([1600], retired)
        self.assertEqual(900, patrol.m_TimeSinceLastSpawn)
        self.assertEqual(1000, death.ClearedAt)
        # Restored wiped state serves the full-group delay, no weekly floor.
        patrol.m_Group = group
        living[0] = 0
        death.PartialRaid = False
        combat[0] = True  # Empty native group may retain its final combat flag.
        now[0] = 1899
        fixture.call('HCRefreshDepleted', patrol)
        self.assertEqual([1600], retired)
        now[0] = 1900
        fixture.call('HCRefreshDepleted', patrol)
        self.assertEqual([1600, 1900], retired)
        # Transient sites remain single-use even at/after the deadline.
        patrol.m_Group = group
        patrol.m_HCTransient = True
        fixture.call('HCRefreshDepleted', patrol)
        self.assertEqual([1600, 1900], retired)

    def test_short_camp_lockout_survives_restart_boundary(self):
        cfg, api = authored_camp_api()
        self.assertEqual(1800, cfg.RaidLockoutSeconds)
        camp = synthetic_camp(Allocated=True, Population=2, Supply=4)
        api.HCRaid(camp, 10000, cfg)
        restored = N(**json.loads(json.dumps(vars(camp))))
        self.assertEqual(11800, restored.ReoccupyAfter)
        self.assertFalse(api.HCGrow(restored, 11799, cfg))
