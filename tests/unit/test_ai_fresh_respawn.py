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


class RespawnRoundTwoTests(unittest.TestCase):
    def test_replacement_advances_once_when_shared_pool_is_exhausted(self):
        from tests.unit.tick_budget_fixture import install, new_budget
        fixture = ops.OperationsTests()
        fixture.setUp()
        budget = new_budget()
        budget.HCReset(1)
        budget.HCTake(1)
        install(fixture.env, state=N(m_TickWork=budget))
        fixture.env['HCServer'].HCTickWork = lambda: budget
        fixture.env['HCXAISiteDirector'].WORK_PER_TICK = 4
        fixture.env['FileExist'] = lambda path: False
        patrol = N(m_HCGroupMax=4)
        fixture.director.m_RespawnCursor = 0
        fixture.director.m_States = A([N(Patrol=patrol), N(Patrol=patrol)])
        refreshed = []
        fixture.director.HCRefreshDepleted = refreshed.append
        fixture.call('HCStepRespawns')
        self.assertEqual([patrol], refreshed)
        self.assertEqual(1, fixture.director.m_RespawnCursor)
        self.assertEqual(1, budget.HCStarved())

    def test_generator_owns_short_defaults_and_validates_all_timers(self):
        from tools.package import ai_patrols
        expected = dict(AIRespawnSeconds=900, MemberReplaceSeconds=600,
                        PatrolRespawnSeconds=0, HoldoutRespawnSeconds=0,
                        MilitaryRespawnSeconds=0)
        for key, value in expected.items():
            self.assertEqual(value, ai_patrols.POLICY_DEFAULTS.get(key), key)
            for invalid in (-1, True, 1, 59, 604801, 60.5):
                with self.assertRaises(ValueError, msg=key):
                    ai_patrols.validate_policy({key: invalid})
            for valid in (0, 60, 604800):
                ai_patrols.validate_policy({key: valid})
        self.assertTrue(all(row['RespawnSeconds'] == 900
                            for row in ai_patrols.KIND_DEFAULTS.values()))

    def test_persisted_weekly_holdout_policy_adopts_current_lockout_once(self):
        from tests.unit.test_hc_ai_camps import synthetic_state, authored_holdouts, synthetic_image
        state = synthetic_state()
        cfg, _ = authored_camp_api()
        state.CampPolicy.RaidLockoutSeconds = 604800
        row = state.Rows[0]
        row.Ledger.State = 'RAIDED'
        row.Ledger.Occupants = 0
        row.Ledger.Since = 999000
        row.Camp.Level = -1
        row.Camp.Refunded = True
        row.Camp.Supply = 0
        row.Camp.ReoccupyAfter = row.Ledger.ReoccupyAfter = 1603800
        module, logs, writes, status, clock = authored_holdouts(state, synthetic_image(state))
        module.OnStart(N(EnableDebugSnapshot=False))
        self.assertTrue(module.m_Ready)
        self.assertEqual(cfg.RaidLockoutSeconds, state.CampPolicy.RaidLockoutSeconds)
        self.assertEqual(clock[0] + cfg.RaidLockoutSeconds, row.Camp.ReoccupyAfter)
        self.assertEqual(row.Camp.ReoccupyAfter, row.Ledger.ReoccupyAfter)
        self.assertTrue(module.m_Dirty)
        self.assertTrue(any('respawn policy migrated' in line for line in logs))

class RespawnTimingTests(unittest.TestCase):
    def test_publish_started_from_phase_zero_is_charged_to_publish(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[2] /
                  'mods/HollowCountry/scripts/4_World/World/HCHoldouts.c').read_text()
        source = source.split('modded class HCHoldouts\n{', 1)[1]
        source = source.replace('super.OnTick(deltaTime)', 'this.HCTestTick(deltaTime)')
        added = []
        owner = N(m_TickPhase=0, m_TickMeasuredStage=0, m_CatalogCursor=0,
                  m_TickSteps=N(HCAdd=lambda *args: added.append(args),
                                HCItem=lambda *args: None, HCEndTick=lambda *args: None))
        def publish(delta):
            owner.m_TickMeasuredStage = 1
            owner.m_TickPhase = 2
        owner.HCTestTick = publish
        Authored(source, dict(TickCount=lambda start: 17, Math=N(Min=min),
                             HCStepTimer=N(MAX_STEPS=8))).call('OnTick', owner, 1)
        self.assertEqual([(1, 17)], added)

class RespawnCoastalAdapterTests(unittest.TestCase):
    def test_coastal_adapter_finds_land_and_retains_every_observer_gate(self):
        import math
        from tests.unit.test_w68_spawnring import coastal_fixture
        ring, probes, array = coastal_fixture(sea=lambda x, z: z > 5000)
        env = dict(A=A, HCPerceptionRing=ring, Math=N(Min=min),
                   vector=N(Zero=[0, 0, 0], Distance=math.dist),
                   HCServer=N(HCTickWork=lambda: N(HCTake=lambda cost: True, HCCharge=lambda n: None)),
                   GetGame=lambda: N(SurfaceIsSea=lambda x, z: z > 5000,
                                     SurfaceIsPond=lambda x, z: False))
        source = (SCRIPTS / 'HCXAISites.c').read_text()
        source = source.replace('HCPerceptionRingPick pick', 'HCXAIRingPick pick')
        source = source.replace('array<Man> ringPlayers', 'HCXAIPlayers ringPlayers')
        source = source.replace('array<vector> ringObservers', 'HCXAIVectors ringObservers')
        authored = Authored(source, env)
        seen = [False]
        owner = N(m_Policy=N(MinPlayerDistance=200), m_Phase='run', m_RingCandidates=8,
                  m_Players=A([N(GetIdentity=lambda: True, IsAlive=lambda: True,
                                 GetPosition=lambda: [5000, 0, 5000])]),
                  HCRefreshPlayers=lambda: None, NearestPlayer=lambda pos: 1,
                  GroundSample=lambda point, radius: point,
                  HCRingRouteProblem=lambda start, end: '',
                  MemberProblemFor=lambda point: 'observer' if seen[0] else '')
        patrol = N(m_HCTransient=False, m_HCKind='patrol', m_Group=None,
                   m_Position=[5000, 0, 5100])
        self.assertEqual('', authored.call('HCPrepareRingSpawn', owner, patrol))
        self.assertLessEqual(patrol.m_Position[2], 5000)
        self.assertGreater(len(probes), 1)
        self.assertGreaterEqual(math.dist(patrol.m_Position, [5000, 0, 5000]), 1100)
        original = [5000, 0, 5100]
        patrol.m_Position = original
        seen[0] = True
        self.assertEqual('observer', authored.call('HCPrepareRingSpawn', owner, patrol))
        self.assertEqual(original, patrol.m_Position)
        seen[0] = False
        owner.HCRingRouteProblem = lambda start, end: 'spawn_ring_route_unreachable'
        self.assertEqual('spawn_ring_route_unreachable', authored.call('HCPrepareRingSpawn', owner, patrol))
        self.assertEqual(original, patrol.m_Position)
        self.assertIn('director.HCPrepareRingSpawn(this)', source.split('override bool CanSpawn()', 1)[1])

class RespawnRegistryTests(unittest.TestCase):
    def test_every_respawn_timer_has_one_checked_registry_row(self):
        from tools.validate.settings_consistency import load_registry, check_consistency
        rows = {row['key']: row for row in load_registry()}
        for key in ('AIRespawnSeconds', 'PatrolRespawnSeconds', 'HoldoutRespawnSeconds',
                    'MilitaryRespawnSeconds', 'MemberReplaceSeconds'):
            self.assertIn('AISites.' + key, rows)
        self.assertIn('AICamps.RaidLockoutSeconds', rows)
        self.assertEqual([], check_consistency())


class RespawnCampOperatorTests(unittest.TestCase):
    def test_current_operator_lockout_is_loaded_and_invalid_input_refuses(self):
        for seconds in (60, 1800, 604800):
            cfg, api = authored_camp_api(config_text=json.dumps({'RaidLockoutSeconds': seconds}))
            self.assertEqual(seconds, api.HCConfiguredLockout())
        for text in ('{}', '{"RaidLockoutSeconds":0}', '{"RaidLockoutSeconds":604801}', 'broken'):
            cfg, api = authored_camp_api(config_text=text)
            self.assertEqual(-1, api.HCConfiguredLockout())

    def test_current_operator_weekly_value_is_not_remigrated_and_expired_stays_expired(self):
        from tests.unit.test_hc_ai_camps import synthetic_state, authored_holdouts, synthetic_image
        for seconds in (180, 604800):
            state = synthetic_state()
            state.CampPolicy.RaidLockoutSeconds = 604800
            module, logs, writes, status, clock = authored_holdouts(
                state, synthetic_image(state), config_text=json.dumps({'RaidLockoutSeconds': seconds}))
            module.OnStart(N(EnableDebugSnapshot=False))
            self.assertTrue(module.m_Ready)
            self.assertEqual(seconds, state.CampPolicy.RaidLockoutSeconds)
            self.assertEqual(0, state.Rows[0].Camp.ReoccupyAfter)
        state = synthetic_state()
        module, logs, writes, status, clock = authored_holdouts(state, config_text='{}')
        module.OnStart(N(EnableDebugSnapshot=False))
        self.assertFalse(module.m_Ready)
        self.assertEqual('HC16_respawn_config_invalid', status[-1][1])

class RespawnActualHoldoutStageTests(unittest.TestCase):
    def test_actual_publish_stage_and_catalog_yield_record_their_own_cost_owner(self):
        from pathlib import Path
        from tests.unit.test_hc_unit_budget import translated
        from tests.unit.test_group_server import EArray
        source = (Path(__file__).resolve().parents[2] /
                  'mods/HollowCountry/scripts/4_World/World/HCHoldouts.c').read_text()
        for cls in ('HCHoldoutRow', 'HCHoldoutBody', 'HCSearchHouses', 'HCWorldModule'):
            source = source.replace(cls, 'HCEvent' + cls[2:])
        published = []
        row = N(Ledger=N(Since=1), Published=False)
        owner = N(m_Ready=True, m_Elapsed=10, m_State=N(TemplatePin='', Rows=EArray([row])),
                  m_CatalogDirty=False, m_CatalogWorked=False, m_TickPhase=0, m_Next=0,
                  m_CampUnits=N(HCReset=lambda n: None, HCTake=lambda n: True),
                  m_WorkBudget=N(HCReset=lambda n: None, HCContinue=lambda: True),
                  FillCatalog=lambda: None, Count=lambda: 1,
                  PublishState=published.append, SaveChanged=lambda: True)
        env = dict(HCEventWorldModule=N(Get=lambda: N()),
                   HCInteriorTemplates=N(Loaded=lambda: True), HCWorldClock=N(UTC=lambda: 100))
        tick = translated(source, 'OnTick', env, 'HCHoldouts')
        tick(owner, 1.)
        self.assertEqual([row], published)
        self.assertEqual((1, 2), (owner.m_TickMeasuredStage, owner.m_TickPhase))
        owner.m_CatalogWorked = True
        tick(owner, 1.)
        self.assertEqual((0, 2), (owner.m_TickMeasuredStage, owner.m_TickPhase))

class RespawnRingPathBudgetTests(unittest.TestCase):
    def test_spawn_connector_checks_only_endpoint_and_rejects_partial_path(self):
        import math
        accesses = []
        endpoint = [(100, 0, 100)]
        class PathPoints(A):
            def __getitem__(self, index):
                accesses.append(index)
                return super().__getitem__(index)
        def find_path(start, target, filter_value, path):
            path.extend([(0, 0, 0), (10, 0, 10), (20, 0, 20), endpoint[0]])
            return True
        env = dict(HCXAIPathPoints=PathPoints,
                   GetGame=lambda: N(GetWorld=lambda: N(GetAIWorld=lambda: N(FindPath=find_path))),
                   HCServer=N(HCTickWork=lambda: N(HCCharge=lambda units: None)),
                   vector=N(Distance=math.dist),
                   HCXAISiteRules=N(LegProblem=lambda *args: ''))
        source = (SCRIPTS / 'HCXAISites.c').read_text().replace('AIWorld ringWorld', 'HCXAIWorld ringWorld')
        source = source.replace('TVectorArray ringPath = new TVectorArray()',
                                'HCXAIPathPoints ringPath = new HCXAIPathPoints()')
        authored = Authored(source, env)
        owner = N(m_Filter=object())
        self.assertEqual('', authored.call('HCRingRouteProblem', owner, (0, 0, 0), (100, 0, 100)))
        self.assertEqual([3], accesses)
        endpoint[0] = (90, 0, 90)
        self.assertEqual('spawn_ring_route_incomplete', authored.call(
            'HCRingRouteProblem', owner, (0, 0, 0), (100, 0, 100)))
