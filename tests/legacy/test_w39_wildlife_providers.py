"""#149 source behavior with explicit synthetic handles, visibility, ledger and disk.
No native perception, feeding, corpse replication or CE behavior is established.
"""
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from tests.legacy.test_ecology_runtime import translated, environment
from tests.legacy.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/Ecology/HCWildlifeProviders.c'

class WildlifeProviders(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.exists(), 'bounded native wildlife provider missing')
        self.source = SOURCE.read_text()
        self.e = environment()

    def call(self, name, owner, *args):
        # Syntax-only aliases let the existing translator accept these return/local types.
        source = self.source.replace('HCWildlife', 'HCEventWildlife').replace('AnimalBase', 'HCEventAnimal').replace('HCUnitBudget', 'HCEventUnitBudget')
        env = {key.replace('HCWildlife', 'HCEventWildlife').replace('AnimalBase', 'HCEventAnimal').replace('HCUnitBudget', 'HCEventUnitBudget'): value for key, value in self.e.items()}
        return translated(source, name, env, 'HCEventWildlifeProviders', True)(owner, *args)

    def test_durable_site_claim_precedes_economy_and_creation_and_never_replays(self):
        trace = []
        state = N(Version=1, SpentSites=EArray())
        owner = N(m_State=state, m_Fault=False, m_Config=N(MaxCarcasses=2),
                  m_Store=N(Save=lambda s: trace.append('save') or True))
        self.assertTrue(self.call('HCClaim', owner, 'synthetic-site'))
        self.assertEqual(['save'], trace)
        self.assertEqual(['synthetic-site'], state.SpentSites)
        self.assertFalse(self.call('HCClaim', owner, 'synthetic-site'))
        self.assertEqual(['save'], trace)
        owner.m_Store.Save = lambda s: False
        self.assertFalse(self.call('HCClaim', owner, 'synthetic-other'))
        self.assertTrue(owner.m_Fault)
        self.assertFalse(self.call('HCClaim', owner, 'synthetic-third'))

    def test_carcass_creation_checks_authority_hidden_and_journal_before_spawning(self):
        trace = []
        body = N(SetHealth=lambda *a: trace.append('kill'), IsAlive=lambda: False)
        self.e['AnimalBase'] = N(Cast=lambda value: value)
        self.e['ECE_PLACE_ON_SURFACE'] = 1
        self.e['ECE_NOPERSISTENCY_WORLD'] = 2
        self.e['ECE_INITAI'] = 4
        self.e['GetGame'] = lambda: N(CreateObjectEx=lambda *a: trace.append('create') or body)
        self.e['HCEcologyNative'] = N(Authority=lambda: True)
        site = N(Id='synthetic', Position=[1., 0., 1.])
        owner = N(m_Fault=False, m_Running=True,
                  HCHidden=lambda p: trace.append('hidden') or True,
                  HCClaim=lambda s: trace.append('claim') or True,
                  m_Ledger=N(Commit=lambda s: trace.append('economy') or N(Items=EArray(['Animal_CervusElaphus']))),
                  HCRefuse=lambda reason: trace.append(reason) or False)
        self.assertIs(body, self.call('HCCreate', owner, site))
        self.assertEqual(['hidden', 'claim', 'economy', 'create', 'kill'], trace)
        trace.clear()
        owner.HCHidden = lambda p: False
        self.assertIsNone(self.call('HCCreate', owner, site))
        self.assertEqual([], trace)
        owner.HCHidden = lambda p: True
        owner.HCClaim = lambda s: False
        self.assertIsNone(self.call('HCCreate', owner, site))
        self.assertEqual([], trace)
        owner.HCClaim = lambda s: True
        owner.m_Ledger.Commit = lambda s: None
        self.assertIsNone(self.call('HCCreate', owner, site))
        self.assertNotIn('create', trace)
        trace.clear()
        self.e['HCEcologyNative'].Authority = lambda: False
        self.assertIsNone(self.call('HCCreate', owner, site))
        self.assertEqual([], trace)

    def test_native_feeding_states_are_read_without_consuming_or_overriding(self):
        enum = N(EATING=12, DRINKING=6, CALM_GRAZING=4, CALM_TRAVELLING=5)
        self.e['DayZAnimalBehaviourSlot'] = enum
        self.e['HCWildlifeProviders'] = N()
        activity = translated(self.source, 'HCActivity', self.e, 'HCWildlifeProviders')
        self.assertEqual('feeding', activity(enum.EATING))
        self.assertEqual('drinking', activity(enum.DRINKING))
        self.assertEqual('grazing', activity(enum.CALM_GRAZING))
        self.assertEqual('resource_seeking_unknown', activity(enum.CALM_TRAVELLING))
        self.assertEqual('native', activity(-1))
        for forbidden in ('OverrideMovement', 'OverrideBehaviour', 'AddAgent(', 'SetQuantity(', 'AddNoise'):
            self.assertNotIn(forbidden, self.source)

    def eligibility_fixture(self, actor_class, native=True):
        # Explicit synthetic native result, attacker/prey handles and service clock.
        attacker = N(IsAlive=lambda: True, IsPendingDeletion=lambda: False,
                     IsKindOf=lambda kind: kind == 'Animal_CanisLupus')
        owner = N(m_Running=True, m_LastNow=0, m_Pairs=EArray(), m_PairChecks=0,
                  m_Config=N(TargetPairsEnabled=True, MaxPairs=8, PairLifetimeMs=10000,
                             PairCooldownMs=30000, MaxPairChecksPerTick=32))
        self.e['HCEcologyNative'] = N(Authority=lambda: True)
        self.e['HCWildlifePairLease'] = lambda: N()
        owner.HCPermit = lambda *args: self.call('HCPermit', owner, *args)
        self.e['s_Owner'] = owner
        self.e['GetGame'] = lambda: N(GetTime=lambda: 100)
        permit = translated(self.source, 'HCNativePermit', self.e, 'HCWildlifeProviders')
        env = dict(HCWildlifeProviders=N(HCNativePermit=permit),
                   ZombieBase=N(Cast=lambda ai: ai), NativeResult=lambda ai: native,
                   GetIdentity=lambda: None)
        section = self.source.split('modded class ' + actor_class, 1)[1]
        section = section.replace('super.CanBeTargetedByAI(ai)', 'NativeResult(ai)')
        query = translated(section, 'CanBeTargetedByAI', env, actor_class, True)
        return query, owner, attacker

    def test_many_prey_in_one_frame_preserve_native_eligibility(self):
        for actor_class in ('AnimalBase', 'PlayerBase'):
            with self.subTest(actor_class=actor_class):
                query, owner, attacker = self.eligibility_fixture(actor_class)
                prey = [N(IsAlive=lambda: True, IsPendingDeletion=lambda: False, index=i)
                        for i in range(64)]
                self.assertTrue(all(query(animal, attacker) for animal in prey))

    def test_repeated_eligibility_queries_never_mutate_provider_state(self):
        for actor_class in ('AnimalBase', 'PlayerBase'):
            with self.subTest(actor_class=actor_class):
                query, owner, attacker = self.eligibility_fixture(actor_class)
                before = (list(owner.m_Pairs), owner.m_PairChecks, owner.m_LastNow)
                for _ in range(64):
                    query(attacker, attacker)
                self.assertEqual(before, (list(owner.m_Pairs), owner.m_PairChecks, owner.m_LastNow))

    def test_more_than_32_queries_keep_native_true_and_false_results(self):
        for actor_class in ('AnimalBase', 'PlayerBase'):
            for native in (True, False):
                with self.subTest(actor_class=actor_class, native=native):
                    query, owner, attacker = self.eligibility_fixture(actor_class, native)
                    self.assertEqual([native] * 96, [query(attacker, attacker) for _ in range(96)])

    def test_hidden_check_refuses_overflow_or_any_visible_observer(self):
        players = EArray([N(GetPosition=lambda: [0., 0., 0.])])
        self.e['HCPerfPlayers'] = N(HCGet=lambda: players)
        self.e['PlayerBase'] = N(Cast=lambda value: value)
        self.e['HCEcologyMigrationNative'] = N(PointHidden=lambda *args: True)
        owner = N(m_Config=N(MaxPlayerChecks=1, MinPlayerDistanceM=200.))
        self.assertFalse(self.call('HCHidden', owner, [0., 0., 20.]))
        self.assertTrue(self.call('HCHidden', owner, [1000., 0., 1000.]))
        self.e['HCEcologyMigrationNative'].PointHidden = lambda *args: False
        self.assertFalse(self.call('HCHidden', owner, [1000., 0., 1000.]))
        self.e['HCEcologyMigrationNative'].PointHidden = lambda *args: True
        players.append(players[0])
        self.assertFalse(self.call('HCHidden', owner, [1000., 0., 1000.]))

    def test_config_bounds_and_explicit_default_preferences(self):
        import json
        config = json.loads((ROOT / 'mission/hollow-country/ecology/HCWildlife-providers.json').read_text())
        for flag in ('Enabled', 'CarcassesEnabled', 'TargetPairsEnabled'):
            self.assertIs(True, config[flag])
        config['Sites'] = EArray(N(**site) for site in config['Sites'])
        cfg = N(**config)
        self.e['HCEcologyRuntimeRules'] = N(PositionValid=lambda p: len(p) == 3 and all(v == v for v in p))
        self.e['HCEventDirector'] = N(TextValid=lambda text, cap: bool(text) and len(text) <= cap)
        # Shared registry edit is NOT applied to the repository: augment a local
        # fixture COPY only, as required by the worker ownership contract.
        rules = {r['key']: r for r in json.loads((ROOT / 'tools/validate/shared_settings.json').read_text())}
        bounds = dict(Version=(1, 1), TickMs=(1, 60000), WorkUnits=(1, 64),
                      MaxCarcasses=(1, 8), MaxPairs=(1, 16), MaxPairChecksPerTick=(1, 64),
                      PairLifetimeMs=(1, 60000), PairCooldownMs=(1, 60000),
                      MaxPlayerChecks=(1, 64), MinPlayerDistanceM=(100, 1000))
        for key, (low, high) in bounds.items():
            rules['WildlifeProviders.' + key] = dict(min=low, max=high)
        self.e['HCOperatorSettingsRegistry'] = N(HCValid=lambda key, value: key in rules and rules[key]['min'] <= value <= rules[key]['max'])
        source = self.source.replace('HCWildlife', 'HCEventWildlife')
        valid = translated(source, 'HCValid', self.e, 'HCEventWildlifeProviders')
        self.assertTrue(valid(cfg))
        for field in ('Version', 'TickMs', 'WorkUnits', 'MaxCarcasses', 'MaxPairs',
                      'MaxPairChecksPerTick', 'PairLifetimeMs', 'PairCooldownMs', 'MaxPlayerChecks',
                      'MinPlayerDistanceM'):
            original = getattr(cfg, field)
            setattr(cfg, field, 0)  # Explicit simulation of native missing-field zero-fill.
            self.assertFalse(valid(cfg), field)
            setattr(cfg, field, original)
        cfg.WorldName = 'enoch'
        self.assertFalse(valid(cfg))

    def test_stopped_or_throttled_tick_is_a_cheap_noop(self):
        self.e['HCEcologyNative'] = N(Authority=lambda: True)
        self.call('HCStep', N(m_Running=False), 1000)
        owner = N(m_Running=True, m_Fault=False, m_LastNow=1000, m_LastTick=1000,
                  m_Config=N(TickMs=5000))
        self.call('HCStep', owner, 1100)
        self.assertEqual(1000, owner.m_LastTick)

    def test_service_is_wired_and_every_new_mission_file_is_named_for_integration(self):
        observer = (SOURCE.parent / 'HCWildlifeObservation.c').read_text()
        for hook in ('HCWildlifeProviders.HCStart(started)', 'HCWildlifeProviders.HCTick(nowMs)',
                     'HCWildlifeProviders.HCStop()'):
            self.assertIn(hook, observer)
        self.assertIn('HCServer.HCTickWork()', self.source)
        self.assertIn('HCModuleReadiness.HCDerive', self.source)
        self.assertIn('HCOperatorSettingsRegistry.HCValid("WildlifeProviders.TickMs", config.TickMs)', self.source)
        self.assertIn('runtime=PENDING', self.source)
        self.assertIn('acceptance/wildlife_providers.disable', self.source)

if __name__ == '__main__':
    unittest.main()
