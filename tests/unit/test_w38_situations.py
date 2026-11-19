"""#147 spec/plan/tasks: live leased parties, reversible walking, finite physical stock.
Synthetic Enforce collaborators only; never DayZ runtime evidence.
"""
from pathlib import Path
from types import SimpleNamespace as N, MethodType
import unittest
from tests.unit.test_map_layers import translate, methods, EStr
from tests.unit.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
AI = ROOT/'mods/HollowCountryExpansionAI/scripts/4_World'

class Situations(unittest.TestCase):
    def test_route_release_restores_original_waypoints_without_moving_actors(self):
        source = (AI/'HCW38SituationRuntime.c').read_text().replace('    protected ', '    ').replace('array<vector> ', 'EArray ')
        calls = []
        group = N(ClearWaypoints=lambda: calls.append('clear'),
                  AddWaypoint=lambda p: calls.append(('point', p)),
                  SetWaypointBehaviour=lambda b: calls.append(('behaviour', b)))
        env = dict(EArray=EArray)
        translate(source, 'HCW38SituationRuntime', env, only=('HCRestore',))
        row = N(Group=group, Original=EArray(['a', 'b']), Behaviour=7)
        env['HCRestore'](row)
        self.assertEqual(['clear', ('point', 'a'), ('point', 'b'), ('behaviour', 7)], calls)
        env['HCRestore'](N(Group=None))

    def test_profiles_default_on_and_empty_selection_retries(self):
        from tests.unit.test_hc_situations import director_fixture
        run = director_fixture()
        self.assertTrue(all(slot.Enabled for slot in run.owner.m_Rows))
        run.owner.HCOffer(run.state.Chains[0])
        run.actors.HCSelect = lambda row: EStr('')
        run.owner.HCStep(100)
        self.assertFalse(run.owner.HCFind('survivor').Attempted)
        run.actors.HCSelect = lambda row: EStr('synthetic-owned-lease')
        run.owner.HCStep(101)
        self.assertEqual('active', run.state.Stories.HCFirstSurvivor.Phase)

    def test_candidate_must_be_live_qualified_funded_and_unclaimed(self):
        source = (AI/'HCW38SituationRuntime.c').read_text()
        env = dict(HCWorldMaterializer=N(HCIdentity=lambda lease: lease == 'owned'))
        translate(source, 'HCW38SituationRuntime', env, only=('HCCandidate',))
        row = N(Transient=True, Materialized=True, Qualified=True, Completed=False,
                ProposalId='owned', Patrol=N(m_Group=N(Count=lambda: 2), m_HCPendingMembers=0))
        self.assertTrue(env['HCCandidate'](row))
        for field, value in [('Transient', False), ('Materialized', False),
                             ('Qualified', False), ('Completed', True), ('ProposalId', 'forged')]:
            bad = N(**vars(row)); setattr(bad, field, value)
            self.assertFalse(env['HCCandidate'](bad), field)

    def test_policy_refuses_zero_nan_or_unbounded_override(self):
        source = (ROOT/'mods/HollowCountry/scripts/4_World/Events/HCW38SituationPolicy.c').read_text()
        env = dict(HCOperatorSettingsRegistry=N(HCFind=lambda key: None))
        translate(source, 'HCW38SituationPolicy', env, only=('HCValid',))
        policy = N(Version=1, ScanRows=8, MaxConcurrent=1, MaxThreats=3, MaxMembers=6,
                   MaxRouteNodes=32, MaxIncidents=64, MaxIncidentItems=16,
                   PhysicalScanObjects=64, PhysicalScanCargo=16, MaxRaidMeters=600,
                   ShelterMeters=20, InfectedClass='ZmbM_CitizenASkinny_Brown', RoadSurface='cp_asphalt1')
        self.assertTrue(env['HCValid'](policy))
        for field, value in [('ScanRows', 0), ('MaxConcurrent', 2), ('MaxThreats', 7),
                             ('MaxRaidMeters', float('nan')), ('ShelterMeters', 0),
                             ('PhysicalScanCargo', 65), ('MaxIncidents', 0)]:
            bad = N(**vars(policy)); setattr(bad, field, value)
            self.assertFalse(env['HCValid'](bad), field)

    def test_raid_walks_existing_group_to_funded_target_and_missing_target_does_nothing(self):
        source = (AI/'HCW38SituationRuntime.c').read_text()
        calls = []
        group = N(ClearWaypoints=lambda: calls.append('clear'),
                  AddWaypoint=lambda p: calls.append(('walk', p)),
                  SetWaypointBehaviour=lambda b: calls.append(('behaviour', b)))
        target = N(PatrolPoints=EArray([50]))
        env = dict(HCTarget=lambda party: target, HCRefuse=lambda reason: False, eAIWaypointBehavior=N(HALT=3))
        translate(source, 'HCW38SituationRuntime', env, only=('HCRaid',))
        party = N(PatrolPoints=EArray([10, 20]))
        self.assertTrue(env['HCRaid'](party, N(Group=group)))
        self.assertEqual(['clear', ('walk', 10), ('walk', 50), ('behaviour', 3)], calls)
        calls.clear(); env['HCTarget'] = lambda party: None
        self.assertFalse(env['HCRaid'](party, N(Group=group)))
        self.assertEqual([], calls)

    def test_threat_creation_checks_visibility_and_shared_budget_before_each_body(self):
        source = (AI/'HCW38SituationRuntime.c').read_text().replace('array<vector> ', 'EArray ')
        source = source.replace('eAIBase leader', 'HCLeader leader').replace('ZombieBase existingThreat', 'HCThreat existingThreat').replace('ZombieBase infected', 'HCThreat infected')
        made, checked = [], []
        leader = N(GetPosition=lambda: 0)
        director = N(MemberProblemFor=lambda p: checked.append(p) or ('visible' if p == 2 else ''))
        env = dict(EArray=EArray, s_Threats=EArray(),
                   s_Policy=N(MaxThreats=2, MaxRouteNodes=32, ShelterMeters=20, InfectedClass='native-infected'),
                   eAIBase=N(Cast=lambda actor: actor), ZombieBase=N(Cast=lambda actor: actor),
                   HCXAISiteDirector=N(Active=lambda: director),
                   HCServer=N(HCTickWork=lambda: N(HCTakeFor=lambda consumer, cost: consumer == 11)), HCUnitBudget=N(HC_WORK_SITUATIONS=11),
                   GetGame=lambda: N(CreateObjectEx=lambda kind,p,flags: made.append((kind,p,flags)) or N()),
                   vector=N(DistanceSq=lambda a,b: (a-b)**2),
                   ECE_INITAI=1, ECE_PLACE_ON_SURFACE=2, HCRefuse=lambda reason: False)
        translate(source, 'HCW38SituationRuntime', env, only=('HCThreaten',))
        binding = N(Group=N(GetMember=lambda index: leader), Threats=EArray())
        self.assertTrue(env['HCThreaten'](N(PatrolPoints=EArray([2,4,6,8])), binding))
        self.assertEqual([2,4,6], checked)
        self.assertEqual([('native-infected',4,3), ('native-infected',6,3)], made)
        self.assertEqual(2, len(env['s_Threats']))

    def test_group_cleanup_or_deleted_handles_never_invent_deaths(self):
        source = (AI/'HCW38SituationRuntime.c').read_text().replace('array<eAIBase> ', 'EArray ').replace('s_Active', 'active')
        actor = N(IsAlive=lambda: True, IsPendingDeletion=lambda: False)
        env = dict(active=N(Id='event', Members=EArray([actor])))
        translate(source, 'HCW38SituationRuntime', env, only=('HCObserve',))
        opportunity = N(Id='event')
        self.assertEqual('', env['HCObserve'](opportunity))
        actor.IsAlive = lambda: False
        self.assertEqual('dead', env['HCObserve'](opportunity))
        actor.IsPendingDeletion = lambda: True
        self.assertEqual('', env['HCObserve'](opportunity))
        env['active'].Members = EArray([None])
        self.assertEqual('', env['HCObserve'](opportunity))

    def test_raid_cooldown_uses_durable_upper_bound_after_restart(self):
        source = (AI/'HCW38SituationRuntime.c').read_text().replace('array<ref HCSituationState> ', 'EArray ')
        clock = N(now=159)
        history = EArray([N(Profile='raid', Phase='closed', EndsAt=100)])
        env = dict(HCCampRaidSituation=N(HCCooldown=lambda profile: 60),
                   HCSituationSource=N(HCState=lambda: N(Stories=N(HCSituations=history))),
                   HCGroupClock=N(Utc=lambda: 1577836800+clock.now), HCRefuse=lambda reason: False)
        translate(source, 'HCW38SituationRuntime', env, only=('HCRaidCooled',))
        self.assertFalse(env['HCRaidCooled']('column'))
        clock.now=160
        self.assertTrue(env['HCRaidCooled']('column'))
        self.assertTrue(env['HCRaidCooled']('survivor'))

    def test_reward_cache_exposes_real_stock_without_creating_inventory(self):
        source = (ROOT/'mods/HollowCountry/scripts/4_World/Events/HCEventRewardCache.c').read_text()
        self.assertNotIn('CreateObjectEx(', source)
        self.assertNotIn('CreateEntityInCargo(', source)
        self.assertIn('GetCargo()', source)
        self.assertIn('GetItemCount()', source)

    def test_physical_stock_is_the_same_handle_and_empty_stock_is_not_refilled(self):
        source = (ROOT/'mods/HollowCountry/scripts/4_World/Events/HCEventRewardCache.c').read_text()
        for kind in ('array<Object>', 'array<CargoBase>', 'array<ref HCEventTarget>'):
            source = source.replace(kind, 'EArray')
        cargo = N(GetItemCount=lambda: 1)
        cache = N(IsPendingDeletion=lambda: False, IsRuined=lambda: False,
                  GetHierarchyRootPlayer=lambda: None, GetHierarchyParent=lambda: None,
                  GetInventory=lambda: N(GetCargo=lambda: cargo),
                  GetType=lambda: 'SmallProtectorCase', GetPosition=lambda: 10)
        pending = []
        source = source.replace('CargoBase cargo', 'HCCargo cargo').replace('family.ToString()', 'str(family)')
        env = dict(EArray=EArray, FileExist=lambda path: False, HCPhysicalEnabled=lambda: True,
            GetGame=lambda: N(IsServer=lambda: True,
                GetObjectsAtPosition3D=lambda at, radius, nearby, proxies: nearby.append(cache)),
            HCServer=N(HCTickWork=lambda: N(HCTakeFor=lambda consumer, cost: consumer == 11)), HCUnitBudget=N(HC_WORK_SITUATIONS=11),
            HCEventSitesGate=N(Admitted=lambda: True), ItemBase=N(Cast=lambda item: item),
            HCW38SituationPolicy=N(HCGet=lambda: N(PhysicalScanObjects=64, PhysicalScanCargo=16)),
            vector=N(DistanceSq=lambda a,b: (a-b)**2),
            HCPhysicalPending=lambda: pending.append('waiting'), HCEventTarget=lambda: N())
        translate(source, 'HCEventCacheSpawner', env, only=('HCPhysicalStock', 'Spawn'))
        mission = N(Source=10, Radius=20, Id='physical-site')
        for attempt in range(2):
            result = env['Spawn'](mission, 10, 'SmallProtectorCase', False)
            self.assertIs(cache, result.Item)
        cargo.GetItemCount = lambda: 0
        self.assertIsNone(env['Spawn'](mission, 10, 'SmallProtectorCase', False))
        self.assertEqual(['waiting'], pending)

    def test_empty_incident_never_spends_its_durable_stock_lease(self):
        from tests.unit.test_hc_native_incidents import fixture
        run = fixture()
        run.receipt.Stock = EArray()
        self.assertFalse(run.owner.HCBorrow('synthetic-party-lease'),
                         'empty CE observation must not consume funded-incident history')
        self.assertEqual([], run.images)
        run.receipt.Stock = EArray([run.item])
        self.assertTrue(run.owner.HCBorrow('synthetic-party-lease'))

    def test_native_incident_never_claims_nearby_loose_loot(self):
        source = (ROOT/'mods/HollowCountry/scripts/4_World/Events/HCNativeIncidentLease.c').read_text()
        env = {}
        translate(source, 'HCNativeIncidentSource', env, only=('HCContains',))
        anchor = object()
        item = N(IsPendingDeletion=lambda: False, IsRuined=lambda: False,
                 GetHierarchyRootPlayer=lambda: None, GetHierarchyParent=lambda: anchor)
        self.assertTrue(env['HCContains'](N(), anchor, item))
        item.GetHierarchyParent = lambda: None
        self.assertFalse(env['HCContains'](N(), anchor, item))

if __name__ == '__main__': unittest.main()
