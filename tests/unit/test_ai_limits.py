"""Owner AI limits: authored decisions with explicit synthetic fixtures only."""
import json
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest
from tests.unit.test_map_layers import EStr, translate
from tests.unit.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
LIMITS = ROOT/'mods/HollowCountry/scripts/3_Game/World/HCAILimits.c'
DEFAULTS = dict(MaxLiveGroups=15, MaxLiveAI=72, OccupationMin=3, OccupationMax=8,
                HoldoutMin=3, HoldoutMax=6, PartyMin=2, PartyMax=6,
                PatrolMin=2, PatrolMax=5, CampMin=2, CampMax=6,
                MaxOccupiedPlaces=15, MaxParties=24, MaxMaterialized=15,
                FactionStrengthMax=24, MaxActiveSites=15, MaxActiveAI=72,
                MaxEncounters=15, MaxObservedAI=1024, MaxHoldouts=48, MaxCamps=32, MaxCampItems=64, WorldSeed=18473)


def fixture():
    """Read authored integer initializers; no engine JSON behavior is inferred."""
    text = LIMITS.read_text()
    return N(**{key: int(value) for key, value in re.findall(
        r'^    int (\w+) = (\d+);', text, re.M)})


def authored(owner=None):
    settings = owner or fixture()
    logs = []
    api = N(Get=lambda: settings, GROUP_CEILING=24, AI_CEILING=128,
            SIZE_CEILING=12, WORLD_CEILING=128)
    env = dict(HCAILimits=api, Print=logs.append, EArray=EArray,
               indices=range, Math=N(Min=min, Max=max), HCAIReservation=N, str=str)
    translate(re.sub(r'(\w+)\.ToString\(\)', r'str(\1)', LIMITS.read_text()), 'HCAILimits', env, settings, only=('Value','Validate','Minimum','Maximum','GroupSize'))
    env['Get'] = lambda: settings
    for key, value in env.items():
        if callable(value) and key not in ('Print', 'EArray', 'indices', 'HCAIReservation'):
            setattr(api, key, value)
    return settings, api, env, logs


class AILimitsBehavior(unittest.TestCase):
    def test_owner_defaults_and_staging(self):
        self.assertEqual(DEFAULTS, vars(fixture()))
        self.assertEqual(DEFAULTS, json.loads((ROOT/'config/hollow-country-settings.json').read_text())['AILimits'])
        settings = (ROOT/'mods/HollowCountry/scripts/3_Game/HCSettings.c').read_text()
        self.assertIn('AILimits.Validate()', settings)
        self.assertIn('HCAILimits.Use(AILimits)', settings)

    def test_invalid_key_falls_back_and_names_key_once(self):
        for key, default in DEFAULTS.items():
            cfg, api, env, logs = authored()
            setattr(cfg, key, 99999999)
            env['Validate'](cfg)
            self.assertEqual(default, getattr(cfg, key), key)
            self.assertEqual(1, sum('AILimits.' + key + ' ' in line for line in logs), logs)
        cfg, api, env, logs = authored()
        cfg.OccupationMin = 9
        cfg.OccupationMax = 4
        env['Validate'](cfg)
        self.assertEqual((3, 8), (cfg.OccupationMin, cfg.OccupationMax))
        self.assertTrue(any('OccupationMin' in line for line in logs))

    def test_sizes_are_stable_and_spread(self):
        cfg, api, env, logs = authored()
        for kind, low, high in [('occupation',3,8),('holdout',3,6),('party',2,6),('patrol',2,5),('camp',2,6)]:
            sizes = [env['GroupSize'](198347, EStr('synthetic-row-' + str(i)), EStr(kind)) for i in range(300)]
            self.assertEqual(set(range(low, high + 1)), set(sizes), kind)
            self.assertEqual(sizes, [env['GroupSize'](198347, EStr('synthetic-row-' + str(i)), EStr(kind)) for i in range(300)])

    def test_combined_reservations_and_restart_debt(self):
        cfg, api, env, logs = authored()
        budget = N(s_Rows=EArray(), s_Blocked=False)
        env['HCAIBudget'] = budget
        translate(LIMITS.read_text().replace('s_Rows', 'HCAIBudget.s_Rows').replace('s_Blocked', 'HCAIBudget.s_Blocked'), 'HCAIBudget', env, budget)
        for name in ('Actors','Groups','TryReserve','Restore','Release','Fits'):
            setattr(budget, name, env[name])
        for i in range(9):
            self.assertTrue(budget.TryReserve('materializer:' + str(i), 6))
        for i in range(3):
            self.assertTrue(budget.TryReserve('site:' + str(i), 6))
        self.assertEqual(72, budget.Actors())
        self.assertFalse(budget.TryReserve('adapter:over', 1))
        self.assertTrue(budget.TryReserve('materializer:0', 6))  # bridge reuses ID
        self.assertEqual(12, budget.Groups())
        budget.Release('site:0')
        self.assertTrue(budget.TryReserve('adapter:one', 3))
        self.assertLessEqual(budget.Actors(), cfg.MaxLiveAI)
        cfg.MaxLiveAI = 10  # explicit synthetic restart with a lowered operator budget
        budget.s_Rows.Clear()
        budget.Restore('old-claim', 12)
        self.assertEqual(12, budget.Actors())  # unknown bodies cannot be forgotten
        self.assertFalse(budget.TryReserve('new', 1))
        self.assertTrue(any('custody' in line for line in logs))

    def test_holdout_body_binding_reads_configured_total_instead_of_eighteen(self):
        # Explicit synthetic bodies/positions/arrays; execute the real binding gate.
        from tests.unit.ai_limits_fixture import install
        env = dict(HCHoldoutBody=N, PlayerBase=N(Cast=lambda body: None),
                   vector=N(DistanceSq=lambda left, right: 0))
        limits = install(env, MaxLiveAI=20)
        module = N(m_Ready=True, m_Bodies=EArray(), m_State=N(Rows=EArray()))
        for index in range(2):
            module.m_State.Rows.append(N(Ledger=N(Id=str(index), State='OCCUPIED',
                                                Occupants=12, HousePos=[0, 0, 0])))
        source = (ROOT/'mods/HollowCountry/scripts/4_World/World/HCHoldouts.c').read_text()
        # Syntax-only braces around Enforce's single-statement if bodies.
        source = re.sub(r'(?m)^(\s*)if \((.+)\) (return false;|return true;|continue;|boundCount\+\+;)$',
                        r'\1if (\2) { \3 }', source)
        env['m_Bodies'] = module.m_Bodies  # explicit nested generic field port
        translate(source, 'HCHoldouts', env, only=('BindOccupant',))
        def bind(index):
            body = N(IsMan=lambda: True, IsAlive=lambda: True,
                     GetPosition=lambda: [0, 0, 0])
            return env['BindOccupant'](module, str(index // 12), body)
        self.assertTrue(all(bind(index) for index in range(20)))
        self.assertFalse(bind(20))
        limits.MaxLiveAI = 21
        self.assertTrue(bind(20))

    def test_typed_custody_result_accepts_larger_survivor_count(self):
        # Synthetic immutable result factory port; execute the authored validation.
        env = dict(HCAIPartyIdentity=N(HCValid=lambda identity: True),
                   HCWorldLimits=N(Token=lambda text: bool(text)), HCAIPartyResult=N)
        from tests.unit.ai_limits_fixture import install
        install(env)
        source = (ROOT/'mods/HollowCountry/scripts/3_Game/World/HCAIPartyIdentity.c').read_text()
        translate(source, 'HCAIPartyResult', env, only=('HCCreateResult',))
        self.assertIsNotNone(env['HCCreateResult'](N(), 'synthetic-lease', True, 8))
        self.assertIsNone(env['HCCreateResult'](N(), 'synthetic-lease', True, 13))

    def test_scan_no_numeric_human_ai_population_caps(self):
        # Semantic scan: population variables only. Distances, route work, item
        # quotas, journal history, player teams and animal/infected CE are distinct.
        roots = [ROOT/'mods/HollowCountry/scripts/3_Game/World',
                 ROOT/'mods/HollowCountry/scripts/4_World/World',
                 ROOT/'mods/HollowCountry/scripts/4_World/Camps',
                 ROOT/'mods/HollowCountryExpansionAI/scripts']
        # The policy class is the sole numeric population-ceiling allowlist.
        ceiling_allowlist = {LIMITS}
        population = r'(?:m_State\.NextHouse|survivors|m_Bodies\.Count\(\)|actorCap|ActorCap|reservedSites|activeSites|actors|members|row\.Ledger\.Occupants|row\.Occupants|row\.Size|camp\.Neighbours|s\.NumberOfAI(?:Max)?|(?:route\.)?Spawns\.Count\(\)|Occupied\(\)|MaxActiveAI|MaxActiveSites|MaxGroups|MaxActors)'
        pattern = re.compile(r'\b' + population + r'\s*(?:>=|>|<=)\s*([2-9]\d*|1[0-9]+)\b|(?:MAX_PROPOSALS|MAX_PER_PROPOSAL|MAX_ACTORS|MAX_OPEN|MAX_UNITS)\s*=\s*\d+|reservedActors\s*\+\s*actorCap\s*>\s*\d+|activeAI\s*\+\s*patrol.m_HCGroupMax\s*>\s*\d+')
        findings = []
        for root in roots:
            for path in root.rglob('*.c'):
                if path in ceiling_allowlist:
                    continue
                for n, line in enumerate(path.read_text().splitlines(), 1):
                    if not line.lstrip().startswith('//') and pattern.search(line):
                        findings.append(f'{path.relative_to(ROOT)}:{n}: {line.strip()}')
        self.assertEqual([], findings)

    def test_old_save_structural_caps_not_reduced(self):
        text = (ROOT/'mods/HollowCountry/scripts/3_Game/World/HCWorldData.c').read_text()
        # Old-save counts 24/12/32/64 stay within the shipped defaults. Actual
        # loader/insert validation is covered by the world suite.
        cfg = fixture()
        for key, previous in [('MaxHoldouts',24),('MaxParties',12),('MaxCamps',32),('MaxCampItems',64)]:
            self.assertGreaterEqual(getattr(cfg,key), previous)
        self.assertIn('HCAILimits.Get().MaxParties', text)
        self.assertIn('saved world exceeds AILimits', text)


class OldWorldCompatibility(unittest.TestCase):
    def test_null_holdout_row_is_safe_before_saved_image_validation(self):
        # Malformed explicit synthetic row must not crash the preflight count.
        env = {}
        source = (ROOT/'mods/HollowCountry/scripts/3_Game/World/HCWorldData.c').read_text()
        translate(source, 'HCWorldData', env, only=('OccupiedCount',))
        owner = N(Holdouts=EArray([None, N(Occupants=3)]))
        env['Holdouts'] = owner.Holdouts  # explicit native nested-generic array port
        self.assertEqual(1, env['OccupiedCount'](owner))

    def test_previous_counts_pass_authored_load_migration_and_lowering_refuses(self):
        # Explicit synthetic DTO/native-array ports and row-admission sinks.
        # Execute the real whole-image validator and loader migration; field
        # geometry/JSON decoding remain the existing world suites' responsibility.
        from tests.unit.ai_limits_fixture import install
        env = dict(Print=lambda line: logs.append(line), str=str)
        cfg = install(env)
        logs = []
        source = (ROOT/'mods/HollowCountry/scripts/3_Game/World/HCWorldData.c').read_text()
        constants = {key: int(value) for key, value in re.findall(r'static const int (\w+) = (\d+);', source)}
        env['HCWorldLimits'] = N(**constants)
        data = N(Meta=N(SchemaVersion=1, Epoch=1, LastTick=1, BuildId=EStr('synthetic')),
                 FactHead=0, MemoryHead=0, Escalation=N(Day=0, PressureCaps=EArray()))
        for key, count in dict(Places=1, Facts=0, Factions=5, Holdouts=24, Parties=12,
                               SiteMemory=0, Leads=0, Scenes=0, Notes=0, Camps=32,
                               TheftRows=0, Salvage=0).items():
            setattr(data, key, EArray(N() for _ in range(count)))
        data.OccupiedCount = lambda: 6
        insertions = []
        def checker():
            check = N()
            for kind in ('Place','Faction','Fact','Holdout','Party','Memory','Lead',
                         'Scene','Note','Camp','Theft','Salvage','PressureCap'):
                setattr(check, 'Insert' + kind, lambda row, k=kind: insertions.append(k) or True)
            return check
        env['HCWorldData'] = checker
        translate(source, 'HCWorldData', env, only=('Valid',))
        checker.Valid = env['Valid']
        checker.ExtendPlaces = lambda value: None
        store = (ROOT/'mods/HollowCountry/scripts/4_World/World/HCWorldStore.c').read_text()
        translate(store, 'HCWorldStore', env, only=('Migrate',))
        self.assertTrue(env['Migrate'](data))
        self.assertEqual(24, insertions.count('Holdout'))
        self.assertEqual(12, insertions.count('Party'))
        self.assertEqual(32, insertions.count('Camp'))
        cfg.MaxParties = 11
        insertions.clear()
        self.assertFalse(env['Migrate'](data))
        self.assertEqual([], insertions)
        self.assertTrue(any('saved world exceeds AILimits' in line for line in logs))

    def test_shipped_site_kinds_and_generator_match_owner_ranges(self):
        from tools.package.ai_patrols import KIND_DEFAULTS
        for relative in ('mission/hollow-country/ai/sites.json',
                         'mods/HollowCountryExpansionAI/data/defaults/expansion-ai-sites.json'):
            document = json.loads((ROOT/relative).read_text())
            self.assertEqual((72, 15), (document['MaxActiveAI'],document['MaxActiveSites']))
            for site in document['Sites']:
                expected = dict(holdout=(3,8), patrol=(2,5), scavenger=(2,6))[site['Kind']]
                self.assertEqual(expected, (site['NumberOfAI'],site['NumberOfAIMax']))
                template = KIND_DEFAULTS[site['Kind']]
                self.assertEqual(expected, (template['NumberOfAI'],template['NumberOfAIMax']))


class SharedSpawnPaths(unittest.TestCase):
    def test_surveyed_adapter_uses_configured_stable_size_without_inventing_positions(self):
        from tests.unit.test_expansion_ai_adapter import ExpansionAdapterTests
        adapter = ExpansionAdapterTests()
        adapter.setUp()
        adapter.ai_limits.PatrolMin = 3
        adapter.ai_limits.PatrolMax = 3
        adapter.profile.MaxActors = 1  # retired compatibility field cannot cap admission
        adapter.route.Spawns.extend([(102., 0., 100.), (103., 0., 100.)])
        adapter.route.GroupSize = 4  # four surveyed positions; choose three unchanged
        self.assertTrue(adapter.install())
        self.assertTrue(adapter.start())
        lease = adapter.mod.m_Leases[0]
        self.assertEqual(3, lease.ActorReservation)
        self.assertEqual(3, len(lease.Slots))
        adapter.ai_limits.PatrolMin = 5
        adapter.ai_limits.PatrolMax = 5
        adapter.ai_limits.MaxLiveAI = 8
        self.assertTrue(adapter.start(lease='short-survey'))
        self.assertEqual(4, adapter.mod.m_Leases[-1].ActorReservation)
        self.assertEqual(4, len(adapter.mod.m_Leases[-1].Slots))

    def test_actual_site_and_adapter_admission_share_materializer_reservation(self):
        from tests.unit.test_expansion_ai_adapter import ExpansionAdapterTests, Authored
        adapter = ExpansionAdapterTests()
        adapter.setUp()  # explicit synthetic native/provider ports from adapter suite
        adapter.ai_limits.MaxLiveAI = 15
        adapter.ai_limits.MaxLiveGroups = 3
        budget = adapter.env['HCAIBudget']
        from tests.unit.custody_fixture import CustodyFixture
        materializer = CustodyFixture()
        materializer.env.update(HCAIBudget=budget, HCAILimits=adapter.env['HCAILimits'])
        proposal = materializer.proposal()
        proposal.ActorCap = 6
        materializer.world.MaterializerRow = lambda index: proposal if index == 0 else None
        lease = materializer.offer()
        self.assertIsNotNone(lease)
        self.assertEqual((1, 6), (budget.Groups(), budget.Actors()))
        self.assertTrue(adapter.install())
        self.assertTrue(adapter.start())  # exact surveyed adapter route reserves two
        self.assertEqual((2, 8), (budget.Groups(), budget.Actors()))
        spawned = []
        source = (ROOT/'mods/HollowCountryExpansionAI/scripts/4_World/HCXAISites.c').read_text()
        # Only the external native call is replaced by a named synthetic port.
        # The actual Spawn body's reservation, refusal and callback policy runs.
        source = source.replace('super.Spawn();', 'synthetic_spawn(this);')
        # Native Substring port: the syntax adapter cannot parse nested Length().
        source = source.replace('m_HCSiteId.Substring(10, m_HCSiteId.Length() - 10)',
                                'synthetic_suffix(m_HCSiteId)')
        env = dict(adapter.env)
        env['HCXAISiteDirector'] = N(Active=lambda: N(SpawnProblemFor=lambda p: '',
                                                    Spawned=lambda p: spawned.append(p)))
        env['synthetic_spawn'] = lambda patrol: setattr(patrol, 'm_Group', N())
        env['synthetic_suffix'] = lambda key: key[10:]
        policy = Authored(source, env)
        def attempt(key, size, transient=False):
            patrol = N(m_Group=None, m_HCFinished=False, m_HCLive=False,
                       m_HCSiteId=key, m_HCTransient=transient, m_HCGroupMax=size,
                       m_HCNextBudgetLogMs=0)
            patrol.HCRefuseBudget = lambda: policy.call('HCRefuseBudget', patrol)
            policy.call('Spawn', patrol)
            return patrol
        transient = attempt('transient:' + lease.Proposal.Id, 6, True)
        self.assertIsNotNone(transient.m_Group)
        self.assertEqual((2, 8), (budget.Groups(), budget.Actors()))
        occupation = attempt('synthetic-occupation', 7)
        self.assertIsNotNone(occupation.m_Group)
        self.assertEqual((3, 15), (budget.Groups(), budget.Actors()))
        self.assertIsNone(attempt('synthetic-over-budget', 1).m_Group)
        self.assertFalse(adapter.start(lease='over-budget'))
        self.assertEqual(2, len(spawned))
        self.assertEqual((3, 15), (budget.Groups(), budget.Actors()))


class ReviewAdmissionRegression(unittest.TestCase):
    def test_shared_site_budget_refusal_logs_once_per_minute(self):
        from tests.unit.test_expansion_ai_adapter import A, Authored
        from tests.unit.ai_limits_fixture import install
        now, logs = [1000], []
        env = dict(A=A, Print=logs.append, GetGame=lambda: N(GetTime=lambda: now[0]),
                   HCXAISiteDirector=N(Active=lambda: N(SpawnProblemFor=lambda patrol: '')))
        install(env, MaxLiveGroups=1)
        self.assertTrue(env['HCAIBudget'].TryReserve('synthetic-full', 1))
        source = (ROOT/'mods/HollowCountryExpansionAI/scripts/4_World/HCXAISites.c').read_text()
        source = source.replace('super.Spawn();', 'synthetic_spawn(this);')
        source = source.replace('m_HCSiteId.Substring(10, m_HCSiteId.Length() - 10)',
                                'synthetic_suffix(m_HCSiteId)')
        policy = Authored(source, env)
        patrol = N(m_Group=None, m_HCFinished=False, m_HCSiteId='synthetic-site',
                   m_HCTransient=False, m_HCGroupMax=2, m_HCNextBudgetLogMs=0)
        patrol.HCRefuseBudget = lambda: policy.call('HCRefuseBudget', patrol)
        for _ in range(50): policy.call('Spawn', patrol)
        self.assertEqual(1, len(logs))
        now[0] = 60999
        policy.call('Spawn', patrol)
        self.assertEqual(1, len(logs))
        now[0] = 61000
        policy.call('Spawn', patrol)
        self.assertEqual(2, len(logs))
