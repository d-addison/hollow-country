"""W68 spec/plan/tasks: shared configured ring, site adapter, materializer floor.
Synthetic execution of authored policy; no native perception/spawn evidence.
"""
import json
from pathlib import Path
from types import SimpleNamespace as N
import unittest
from tests.unit.test_expansion_ai_adapter import Authored
from tests.unit.settings_registry_fixture import install_registry

ROOT = Path(__file__).resolve().parents[2]
RING = ROOT / 'mods/HollowCountry/scripts/3_Game/World/HCPerceptionRing.c'
SITES = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAISites.c'
MATERIAL = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCWorldMaterializer.c'


def ring_fixture(view=1000, hearing=1000, margin=100, band=400):
    env = dict(Print=lambda line: None)
    install_registry(env)
    authored = Authored(RING.read_text(), env)
    config = N(ViewRangeMeters=view, HearingRangeMeters=hearing,
               SpawnMarginMeters=margin, SpawnBandMeters=band)
    api = N(HCGet=lambda: config)
    env['HCPerceptionRing'] = api
    for method in ('HCSpawnMin', 'HCSpawnMax', 'HCSeenRange', 'HCHeardRange',
                   'HCClampActivation', 'HCOutside', 'HCValue', 'HCCeiling'):
        setattr(api, method, lambda *args, name=method: authored.call(name, None, *args))
    return api, env


class SpawnRingTests(unittest.TestCase):
    def test_readiness_refreshes_when_qualified_count_changes(self):
        source = (SITES.parent / 'HCXAIAdapter.c').read_text()
        count = [0]
        logs = []
        authored = Authored(source, dict(Print=logs.append,
                           GetGame=lambda: N(GetWorldName=lambda: 'synthetic-world')))
        owner = N(m_ReadinessLogged=True, m_LastQualifiedPatrolCount=0,
                  m_Sites=N(HCLocalitySummary=lambda: 'synthetic-localities', Phase=lambda: 'run'),
                  m_Encounters=N(QualifiedCount=lambda: count[0], Settled=lambda: True,
                                 Ready=lambda world: True, State=lambda: 'armed'),
                  ExpansionAISettingsLoaded=lambda: True, GlobalsProblem=lambda: '')
        owner.LogReadiness = lambda trigger: authored.call('LogReadiness', owner, trigger)
        authored.call('HCRefreshReadiness', owner)
        count[0] = 2
        authored.call('HCRefreshReadiness', owner)
        authored.call('HCRefreshReadiness', owner)
        count[0] = 0
        authored.call('HCRefreshReadiness', owner)
        readiness = [line for line in logs if 'qualified_patrols=' in line]
        self.assertEqual(2, len(readiness))
        self.assertIn('qualified_patrols=2;', readiness[0])
        self.assertIn('qualified_patrols=0;', readiness[1])
        self.assertEqual(0, owner.m_LastQualifiedPatrolCount)
        owner.m_ReadinessLogged = False
        authored.call('HCRefreshReadiness', owner)
        self.assertTrue(owner.m_ReadinessLogged)
        self.assertEqual(3, sum('qualified_patrols=' in line for line in logs))
        self.assertIn('this.HCRefreshReadiness();', source.split('override void OnTick', 1)[1])

    def test_ring_math_and_event_ranges(self):
        self.assertTrue(RING.exists(), 'missing shared HCPerceptionRing policy')
        ring, _ = ring_fixture()
        self.assertEqual((1100, 1500, 1000, 1000),
                         (ring.HCSpawnMin(), ring.HCSpawnMax(), ring.HCSeenRange(), ring.HCHeardRange()))
        ring, _ = ring_fixture(1100, 1800, 75, 250)
        self.assertEqual((1875, 2125), (ring.HCSpawnMin(), ring.HCSpawnMax()))

    def test_configured_clamp_and_validation(self):
        ring, _ = ring_fixture()
        self.assertEqual(1500, ring.HCClampActivation(650))
        self.assertEqual(2000, ring.HCClampActivation(2000))
        self.assertEqual(7500, ring.HCClampActivation(100000))
        for bad in (0, -1, float('nan'), float('inf')):
            self.assertEqual(1000, ring.HCValue('ViewRangeMeters', bad))
        self.assertEqual(2500, ring.HCValue('ViewRangeMeters', 2500))

    def test_site_adapter_uses_ring_even_when_scaled_down(self):
        ring, env = ring_fixture()
        env.update(HCXAISiteRules=N(EncounterRadius=lambda x: max(600, x)))
        adapter = Authored(SITES.read_text(), env)
        owner = N(m_Policy=N(ActivationRadiusScale=.5, MinPlayerDistance=200), m_RadiusClampLogged=False)
        self.assertEqual(1500, adapter.call('HCActivationRadius', owner, N(ActivationRadius=650), False))
        self.assertIn('config.MinDistRadius = HCPerceptionRing.HCSpawnMin();', SITES.read_text())

    def test_materializer_refuses_inside_ring(self):
        ring, env = ring_fixture()
        policy = Authored(MATERIAL.read_text(), env)
        self.assertFalse(policy.call('HCSpawnDistanceAllowed', None, 1099.99 ** 2))
        self.assertTrue(policy.call('HCSpawnDistanceAllowed', None, 1100 ** 2))
        self.assertFalse(ring.HCOutside(float('nan')))
        self.assertIn('HCSpawnDistanceAllowed', MATERIAL.read_text().split('protected void InterestRing()', 1)[1])

    def test_native_patrol_config_output_uses_custom_ring(self):
        from tests.unit.test_expansion_ai_adapter import A
        from tests.unit.test_expansion_ai_sites import api
        ring, env = ring_fixture(1100, 1800, 75, 250)
        configs = []
        env.update(A=A, HCXAISiteSpawnConfig=lambda: N(), TVectorArray=A,
                   HCAILimits=N(Get=lambda: N(WorldSeed=42), GroupSize=lambda *args: 2),
                   HCXFactions=N(SiteFaction=lambda site: 'Guards'),
                   HCXAISiteDirector=N(RaidCooldown=lambda *args: 3600),
                   HCXAIQualification=N(ProviderProblem=lambda: ''),
                   HCXAIRules=N(PatrolProblem=lambda *args: ''), vector=N(Zero=(0, 0, 0)),
                   HCXAITestProvider=N(CreateEx=lambda config, origin: configs.append(config) or N()))
        env['HCXAISiteRules'] = api((SITES.parent / 'HCXAISiteRules.c').read_text(), env)
        # Template and native config type syntax only; no provider code copied.
        source = SITES.read_text().replace('ExpansionAIDynamicSpawnBase config', 'HCXAITestConfig config')
        source = source.replace('eAIDynamicPatrolT<HCXAISitePatrol>', 'HCXAITestProvider')
        authored = Authored(source, env)
        owner = N(m_Policy=N(ActivationRadiusScale=1, RaidCooldownFloorSeconds=0), m_RadiusClampLogged=False)
        owner.HCActivationRadius = lambda *args: authored.call('HCActivationRadius', owner, *args)
        site = N(Id='synthetic-w68', Kind='patrol', Speed='WALK', Behaviour='LOOP',
                 Loadout='HollowCountry_Patrol', ActivationRadius=650, DespawnSeconds=600)
        state = N(Site=site, Transient=False, OpenRoute=False, PatrolPoints=A([(0, 0, 0), (10, 0, 0)]))
        authored.call('Create', owner, state)
        self.assertEqual(1, len(configs))
        self.assertEqual((1875, 2125, 'WALK'),
                         (configs[0].MinDistRadius, configs[0].MaxDistRadius, configs[0].Speed))
        self.assertEqual(state.PatrolPoints, configs[0].Waypoints)

    def test_member_spawn_keeps_sight_and_configured_legacy_floor(self):
        ring, env = ring_fixture()
        rules = Authored((SITES.parent / 'HCXAISiteRules.c').read_text(), env)
        policy = N(MinPlayerDistance=200)
        self.assertNotEqual('', rules.call('MemberSpawnProblem', None, policy, 1099, False))
        self.assertEqual('', rules.call('MemberSpawnProblem', None, policy, 1100, False))
        self.assertNotEqual('', rules.call('MemberSpawnProblem', None, policy, 1500, True))
        policy.MinPlayerDistance = 2000
        self.assertNotEqual('', rules.call('MemberSpawnProblem', None, policy, 1900, False))

    def test_materializer_checks_every_observer_before_reserving(self):
        from tests.unit.custody_fixture import CustodyFixture
        from tests.unit.test_expansion_ai_adapter import A
        fixture = CustodyFixture()
        ring, _ = ring_fixture()
        # Override the explicit shared synthetic ring for this observer scenario.
        fixture.env['HCPerceptionRing'] = ring
        fixture.api.HCSpawnDistanceAllowed = lambda distance: fixture.policy.call(
            'HCSpawnDistanceAllowed', None, distance)
        original = fixture.proposal
        def proposal():
            result = original()
            result.Position = [1300., 0., 100.]
            return result
        fixture.proposal = proposal
        observer = lambda x: N(GetIdentity=lambda: True, IsAlive=lambda: True,
                               GetPosition=lambda: [x, 0., 100.])
        fixture.env['HCPerfPlayers'].HCGet = lambda: A([observer(100), observer(1250)])
        self.assertIsNone(fixture.offer())  # second observer is inside ring
        self.assertEqual(0, fixture.runtime.m_Proposals)
        fixture.env['HCPerfPlayers'].HCGet = lambda: A([observer(100)])
        self.assertIsNotNone(fixture.offer())  # 1200 m: outside min, within band
        self.assertEqual(1, fixture.runtime.m_Proposals)

    def test_shared_validator_accepts_optional_ring_and_rejects_invalid_fields(self):
        import copy
        from tools.validate.runtime import validate_settings as validate
        shipped = json.loads((ROOT / 'config/hollow-country-settings.json').read_text())
        self.assertEqual([], validate(shipped))
        for invalid in (None, True, {'Unknown': 1}, {'ViewRangeMeters': True},
                        {'HearingRangeMeters': 0}, {'SpawnMarginMeters': float('nan')},
                        {'SpawnBandMeters': float('inf')}):
            image = copy.deepcopy(shipped)
            image['PerceptionRing'] = invalid
            self.assertTrue(validate(image), invalid)
        image = copy.deepcopy(shipped)
        image['PerceptionRing'] = {'ViewRangeMeters': 2500}
        self.assertEqual([], validate(image))  # other fields restore native defaults

    def test_registry_shipped_nested_defaults(self):
        ring, _ = ring_fixture()
        for path in ('config/hollow-country-settings.json', 'mission/hollow-country/operator/settings.json'):
            self.assertEqual(dict(ViewRangeMeters=1000, HearingRangeMeters=1000,
                                  SpawnMarginMeters=100, SpawnBandMeters=400),
                             json.loads((ROOT / path).read_text())['PerceptionRing'])
