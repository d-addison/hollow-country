"""#147 spec/plan/tasks: hold leased survivors, road threats, physical signals.
Synthetic translator ports only; native/two-client acceptance remains pending.
Audit at 2ac40d9: lifecycle/leases/caps/spoils/admission done; pinned hold,
road-only threat placement and situation->shared-fact signals partial/missing.
Camp raid: live leased hostile walk exists; separate owner, runtime pending.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest
from tests.unit.test_map_layers import translate
from tests.unit.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT/'mods/HollowCountryExpansionAI/scripts/4_World/HCW38SituationRuntime.c'
SIGNALS = ROOT/'mods/HollowCountry/scripts/4_World/Events/HCSituationSignals.c'


class PinnedSituations(unittest.TestCase):
    def test_pinned_survivors_hold_current_shelter_and_transit_keeps_its_leg(self):
        calls = []
        group = N(ClearWaypoints=lambda: calls.append('clear'),
                  AddWaypoint=lambda p: calls.append(('hold', p)),
                  SetWaypointBehaviour=lambda b: calls.append(('mode', b)),
                  GetMember=lambda index: N(GetPosition=lambda: 'shelter'))
        env = dict(eAIBase=N(Cast=lambda actor: actor), eAIWaypointBehavior=N(HALT=3))
        translate(RUNTIME.read_text().replace('eAIBase sheltered', 'HCActor sheltered'),
                  'HCW38SituationRuntime', env, only=('HCHold',))
        self.assertIn('HCHold', env, 'pinned survivors must request a native hold before observation')
        env['HCHold'](N(Profile='survivor', Group=group))
        self.assertEqual(['clear', ('hold', 'shelter'), ('mode', 3)], calls)
        calls.clear()
        env['HCHold'](N(Profile='threatened-exodus', Group=group))
        self.assertEqual([], calls, 'caravan continues its existing walking leg')

    def test_situation_signals_publish_only_a_place_fact_to_existing_lead_services(self):
        self.assertTrue(SIGNALS.exists(), 'situation starts must enter the shared world fact path')
        calls = []
        world = N(NearestPlace=lambda at: 'authored-place',
                  AddFact=lambda kind,place,severity: calls.append((kind,place,severity)) or True)
        env = dict(HCWorldModule=N(Get=lambda: world))
        translate(SIGNALS.read_text(), 'HCSituationSignals', env, only=('HCPublish',))
        self.assertTrue(env['HCPublish']('native-position'))
        self.assertEqual([('scene_started', 'authored-place', 0)], calls)
        world.NearestPlace = lambda at: ''
        self.assertFalse(env['HCPublish']('unnamed-area'))
        self.assertEqual(1, len(calls))
        env['HCWorldModule'].Get = lambda: None
        self.assertFalse(env['HCPublish']('native-position'))

    def test_only_finite_ground_smoke_can_be_activated(self):
        self.assertTrue(SIGNALS.exists(), 'native finite smoke stock needs a source adapter')
        calls = []
        smoke = N(IsPendingDeletion=lambda: False, IsRuined=lambda: False,
                  GetHierarchyParent=lambda: None, IsPinned=lambda: True,
                  GetCompEM=lambda: N(CanWork=lambda: True), Unpin=lambda: calls.append('unpin'))
        env = dict(SmokeGrenadeBase=N(Cast=lambda actor: actor))
        translate(SIGNALS.read_text(), 'HCSituationSignals', env, only=('HCSmoke',))
        self.assertTrue(env['HCSmoke'](smoke))
        self.assertEqual(['unpin'], calls)
        for field, value in [('IsPinned', False), ('IsRuined', True),
                             ('IsPendingDeletion', True), ('GetHierarchyParent', object())]:
            bad = N(**vars(smoke)); setattr(bad, field, lambda value=value: value)
            self.assertFalse(env['HCSmoke'](bad), field)
        self.assertEqual(['unpin'], calls)

    def test_begin_holds_and_signals_only_after_successful_physical_threats(self):
        source = RUNTIME.read_text().replace('array<vector> ', 'EArray ')
        source = source.replace('eAIBase member', 'HCActor member').replace('s_Active', 'runtime.active')
        runtime = N(active=None, started=False)
        calls = []
        group = N(Count=lambda: 1, GetMember=lambda index: N(IsAlive=lambda: True),
                  GetWaypointBehaviour=lambda: 7, GetWaypoints=lambda: EArray([10, 20]))
        env = dict(EArray=EArray, runtime=runtime, s_Policy=N(MaxRouteNodes=32),
            HCProfileOn=lambda profile: True, HCReady=lambda: True,
            HCFind=lambda lease: N(Patrol=N(m_Group=group)), HCProfileFits=lambda party,profile: True,
            HCW38SituationBinding=lambda: N(Members=EArray(), Original=EArray()),
            eAIBase=N(Cast=lambda actor: actor),
            HCThreaten=lambda party,binding: calls.append('threats') or runtime.started,
            HCHold=lambda binding: calls.append('hold'), HCSignals=lambda binding: calls.append('signals'),
            HCXConvoyRuntime=N(HCOffer=lambda binding: calls.append('convoy')),
            Print=lambda line: calls.append('log'))
        translate(source, 'HCW38SituationRuntime', env, only=('HCBegin',))
        row = N(Profile='survivor', Phase='intent', Lease='funded', Id='saved-intent')
        self.assertFalse(env['HCBegin'](row))
        self.assertEqual(['threats'], calls)
        self.assertIsNone(runtime.active)
        calls.clear(); runtime.started = True
        self.assertTrue(env['HCBegin'](row))
        self.assertEqual(['threats', 'hold', 'convoy', 'signals', 'log'], calls)
        self.assertEqual([10, 20], runtime.active.Original)
        calls.clear()
        self.assertFalse(env['HCBegin'](row), 'one concurrent shared lease across profiles')
        self.assertEqual([], calls)

    def test_road_threats_use_only_nearby_road_nodes_and_never_change_route(self):
        source = RUNTIME.read_text().replace('array<vector> ', 'EArray ')
        source = source.replace('eAIBase leader', 'HCLeader leader').replace('ZombieBase existingThreat', 'HCThreat existingThreat').replace('ZombieBase infected', 'HCThreat infected')
        points = EArray([(1, 0, 0), (2, 0, 0), (3, 0, 0), (40, 0, 0)])
        made, checked, surfaces = [], [], []
        # Enforce out-string is supplied explicitly by the synthetic adapter.
        source = source.replace('GetGame().SurfaceGetType(position[0], position[2], threatSurface);',
                                'threatSurface = SurfaceAt(position);')
        env = dict(EArray=EArray, s_Threats=EArray(),
            s_Policy=N(MaxThreats=3, MaxRouteNodes=32, ShelterMeters=20, RoadSurface='road', InfectedClass='infected'),
            eAIBase=N(Cast=lambda actor: actor), ZombieBase=N(Cast=lambda actor: actor),
            SurfaceAt=lambda at: surfaces.append(at) or ('road' if at[0] != 1 else 'grass'),
            HCXAISiteDirector=N(Active=lambda: N(MemberProblemFor=lambda at: checked.append(at) or ('seen' if at[0] == 2 else ''))),
            HCServer=N(HCTickWork=lambda: N(HCTakeFor=lambda consumer,cost: True)),
            HCUnitBudget=N(HC_WORK_SITUATIONS=11),
            GetGame=lambda: N(CreateObjectEx=lambda kind,at,flags: made.append(at) or N()),
            vector=N(DistanceSq=lambda a,b: (a[0]-b[0])**2),
            ECE_INITAI=1, ECE_PLACE_ON_SURFACE=2, HCRefuse=lambda reason: False)
        translate(source, 'HCW38SituationRuntime', env, only=('HCThreaten',))
        leader = N(GetPosition=lambda: (0, 0, 0))
        binding = N(Profile='threatened-exodus', Threats=EArray(), Group=N(GetMember=lambda index: leader))
        self.assertTrue(env['HCThreaten'](N(PatrolPoints=points), binding))
        self.assertEqual(points[:3], surfaces)
        self.assertEqual(points[1:3], checked)
        self.assertEqual([points[2]], made)

    def test_signal_scan_does_not_activate_visible_or_owned_smoke(self):
        source = RUNTIME.read_text().replace('eAIBase witness', 'HCWitness witness')
        for kind in ('array<Object>', 'array<CargoBase>'):
            source = source.replace(kind, 'EArray')
        smoke = N(GetPosition=lambda: 4)
        calls, logs = [], []
        scene = N(seen=True, grant=True)
        pending = N(fact=False, smoke=False)
        source = source.replace('s_FactPending', 'pending.fact').replace('s_SmokePending', 'pending.smoke')
        env = dict(EArray=EArray, eAIBase=N(Cast=lambda actor: actor),
            SmokeGrenadeBase=N(Cast=lambda actor: actor),
            s_Policy=N(ShelterMeters=20, PhysicalScanObjects=64),
            pending=pending,
            HCSituationSignals=N(HCPublish=lambda at: True, HCSmoke=lambda actor: calls.append(actor) or True),
            HCServer=N(HCTickWork=lambda: N(HCTakeFor=lambda consumer,cost: scene.grant)),
            HCUnitBudget=N(HC_WORK_SITUATIONS=11),
            HCXAISiteDirector=N(Active=lambda: N(MemberProblemFor=lambda at: 'seen' if scene.seen else '')),
            GetGame=lambda: N(GetObjectsAtPosition3D=lambda at,radius,nearby,proxies: nearby.append(smoke)), Print=logs.append)
        translate(source, 'HCW38SituationRuntime', env, only=('HCSignals',))
        binding = N(Group=N(GetMember=lambda index: N(GetPosition=lambda: 0)))
        env['HCSignals'](binding)
        self.assertEqual([], calls)
        self.assertIn('SITUATION_SMOKE_STOCK_PENDING', logs[0])
        scene.seen = False
        scene.grant = False
        env['HCSignals'](binding)
        self.assertEqual([], calls)
        scene.grant = True
        env['HCSignals'](binding)
        self.assertEqual([smoke], calls)

if __name__ == '__main__': unittest.main()
