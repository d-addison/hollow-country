"""#226 spec/plan/tasks: autumn snapshot -> bounded tree presentation -> cleanup.
Explicit synthetic particle/query ports execute authored decisions; no DayZ proof.
"""
from pathlib import Path
from types import SimpleNamespace as N
import functools
import unittest
from tests.unit.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/5_Mission/Weather/auditleaves_Client.c'


class LeavesBehavior(unittest.TestCase):
    def harness(self):
        text = SOURCE.read_text() if SOURCE.exists() else ''
        self.queries = 0
        self.stops = 0
        self.count = 4
        self.receipts = []
        self.owner = N(m_Enabled=True, m_Draining=False, m_Emitter=None,
                       m_StopAt=0, m_NextQuery=0, m_LastNow=0,
                       m_Config=N(QuerySeconds=10, LifetimeSeconds=3),
                       m_Status=N(HCPublish=lambda *args: self.receipts.append(args)))
        self.particle = N(StopParticle=self.stop, GetParticleCount=lambda: self.count)
        self.owner.HCFindAndStart = self.spawn
        self.owner.HCReport = lambda state, reason: self.receipts.append((state, reason))
        self.owner.HCRefuse = lambda reason: self.receipts.append(('refused', reason))
        env = {}
        for name in ('HCStopEmitter', 'HCDrain', 'HCStep'):
            method = translate(text, name, env, 'auditleaves_Client', member=True)
            setattr(self.owner, name, functools.partial(method, self.owner))
        return self.owner

    def spawn(self, now):
        self.queries += 1
        self.owner.m_Emitter = self.particle
        self.owner.m_StopAt = now + 3

    def stop(self):
        self.stops += 1

    def test_lifetime_stops_once_and_no_respawn_until_drain_finishes(self):
        owner = self.harness()
        owner.HCStep(1, True)
        self.assertEqual(1, self.queries)
        owner.HCStep(4, True)
        self.assertEqual(1, self.stops)
        owner.HCStep(30, True)
        self.assertEqual(1, self.queries)
        self.count = 0
        owner.HCStep(31, True)
        self.assertEqual(2, self.queries)

    def test_every_ineligible_transition_stops_without_replacing_draining_emitter(self):
        # Caller derives these from the real cache/viewer/GRADE, never a local clock.
        for reason in ('spring', 'summer', 'winter', 'stale', 'conflict', 'death',
                       'grade_off', 'indoors', 'underground', 'cellar', 'mission_end'):
            with self.subTest(reason=reason):
                owner = self.harness()
                owner.HCStep(1, True)
                owner.HCStep(2, False)
                owner.HCStep(20, True)
                self.assertEqual(1, self.stops)
                self.assertEqual(1, self.queries)
                self.count = 0
                owner.HCStep(21, True)
                self.assertEqual(2, self.queries)

    def test_opt_out_is_cheap_and_clock_rollback_stops_emission(self):
        owner = self.harness()
        owner.m_Enabled = False
        owner.HCStep(1, True)
        self.assertEqual(0, self.queries)
        owner.m_Enabled = True
        owner.HCStep(20, True)
        owner.HCStep(19, True)
        self.assertEqual(1, self.stops)
        self.assertEqual(1, self.queries)

    def test_queries_are_infrequent_even_when_no_tree_is_found(self):
        owner = self.harness()
        owner.HCFindAndStart = lambda now: setattr(self, 'queries', self.queries + 1)
        for now in (1, 2, 3, 10):
            owner.HCStep(now, True)
        self.assertEqual(1, self.queries)
        owner.HCStep(11, True)
        self.assertEqual(2, self.queries)


class LeavesNativePorts(unittest.TestCase):
    def test_real_eligibility_body_uses_snapshot_and_all_viewer_guards(self):
        phase = ['autumn']
        flags = dict(alive=True, unconscious=False, indoors=False, underground=0,
                     cellar=False, requester=False)
        viewer = N(IsAlive=lambda: flags['alive'], IsUnconscious=lambda: flags['unconscious'],
                   IsSoundInsideBuilding=lambda: flags['indoors'],
                   GetUndergroundPresence=lambda: flags['underground'])
        env = dict(GetGame=lambda: N(GetPlayer=lambda: viewer), PlayerBase=N(Cast=lambda p: p),
                   HCSeasonVisualClient=N(HCGetPhase=lambda: phase[0]),
                   EUndergroundPresence=N(NONE=0),
                   HCCellarsClient=N(HCVisualActive=lambda: flags['cellar']),
                   PPERequesterBank=N(REQ_UNDERGROUND=42, IsRequesterRunning=lambda _: flags['requester']))
        eligible = translate(SOURCE.read_text(), 'HCEligible', env, 'auditleaves_Client', member=True)
        self.assertTrue(eligible(N(), True))
        self.assertFalse(eligible(N(), False))
        for value in ('spring', 'summer', 'winter', 'unavailable'):
            phase[0] = value
            self.assertFalse(eligible(N(), True))
        phase[0] = 'autumn'
        for key in flags:
            previous = flags[key]
            flags[key] = not previous
            self.assertFalse(eligible(N(), True), key)
            flags[key] = previous

    def test_config_apply_preserves_missing_defaults_and_enforces_registered_bounds(self):
        import json
        import re
        source = (ROOT / 'mods/HollowCountry/scripts/3_Game/Weather/auditleaves_Config.c').read_text()
        defaults = json.loads((ROOT / 'mission/hollow-country/auditleaves_settings.json').read_text())
        rows = {key: (float(low), float(high)) for key, low, high in re.findall(
            r'HCAdd\("SeasonLeaves\.(\w+)", "\w+", [\d.]+, ([\d.]+), ([\d.]+),', source)}
        self.assertEqual(defaults.keys(), rows.keys())
        env = dict(HCJsonFields=N(Has=lambda text, key: key in json.loads(text)),
                   HCOperatorSettingsRegistry=N(HCValid=lambda key, value:
                       rows[key.split('.')[1]][0] <= value <= rows[key.split('.')[1]][1]))
        # Syntax adapter makes implicit DTO members explicit for the translator.
        source = re.sub(r'(?<![\w.])(' + '|'.join(defaults) + r')(?= =)', r'this.\1', source)
        apply = translate(source, 'HCApply', env, 'auditleaves_Config', member=True)
        config = N(**defaults)
        zero_filled = N(**{key: 0 for key in defaults})
        apply(config, zero_filled, '{}')
        self.assertEqual(defaults, vars(config))
        apply(config, zero_filled, '{"Enabled":false,"QuerySeconds":0}')
        self.assertFalse(config.Enabled)
        self.assertEqual(10, config.QuerySeconds)
        for key, (low, high) in rows.items():
            if key == 'Enabled':
                continue
            for value in (low, high):
                apply(config, N(**{key: value}), json.dumps({key: value}))
                self.assertEqual(value, getattr(config, key))
            apply(config, N(**{key: high + 1}), json.dumps({key: high + 1}))
            self.assertEqual(high, getattr(config, key))

    def test_tree_query_has_bounded_inspection_and_attaches_to_real_canopy(self):
        from tests.unit.test_group_server import EArray
        text = SOURCE.read_text().replace('vector bounds[2];', 'HCEventBounds bounds = new HCEventBounds;')
        captures = []
        def tree(kind, position, is_tree=True, height=12):
            return N(GetType=lambda: kind, GetPosition=lambda: position, IsTree=lambda: is_tree,
                     GetCollisionBox=lambda bounds: bounds.__setitem__(1, [0, height, 0]) is None)
        objects = [tree('TreeHard_t_PiceaAbies_3s', [1, 0, 0]),
                   tree('SyntheticBuilding_FagusSylvatica', [1, 0, 0], False),
                   tree('TreeHard_t_FagusSylvatica_2f', [3, 0, 0]),
                   tree('TreeSoft_t_BetulaPendula_1f', [2, 0, 0])]
        query_calls = []
        budget = N(left=0)
        def take(_):
            budget.left -= 1
            return budget.left >= 0
        def query(origin, radius, nearby, cargos):
            query_calls.append((origin, radius))
            nearby.extend(objects)
        emitter = N()
        env = dict(EArray=EArray, HCEventBounds=lambda: [[0, 0, 0], [0, 0, 0]],
                   GetGame=lambda: N(GetPlayer=lambda: N(GetPosition=lambda: [0, 0, 0]),
                                     GetObjectsAtPosition3D=query), PlayerBase=N(Cast=lambda p: p),
                   vector=N(DistanceSq=lambda a,b: sum((x-y)**2 for x,y in zip(a,b))),
                   Vector=lambda x,y,z: [x,y,z], ParticleList=N(TREE_FALLING_LEAF=399),
                   Particle=N(PlayOnObject=lambda *args: captures.append(args) or emitter),
                   Print=lambda line: None)
        owner = N(m_Config=N(QueryRadius=12, MaxObjects=4, MinTreeHeight=3,
                             MaxTreeHeight=40, CanopyFraction=0.75, LifetimeSeconds=3),
                  m_Units=N(HCReset=lambda count: setattr(budget, 'left', count), HCTake=take),
                  m_Work=N(HCReset=lambda count: None, HCContinue=lambda: True),
                  m_FirstStarted=False, HCReport=lambda *args: None,
                  HCRefuse=lambda reason: captures.append(reason))
        owner.HCDeciduous = translate(text, 'HCDeciduous', env, 'auditleaves_Client')
        find = translate(text, 'HCFindAndStart', env, 'auditleaves_Client', member=True)
        find(owner, 10)
        self.assertIs(objects[3], captures[0][1])
        self.assertEqual([0, 9, 0], captures[0][2])
        self.assertIs(owner.m_Emitter, emitter)
        self.assertEqual(13, owner.m_StopAt)
        self.assertEqual([([0, 0, 0], 12)], query_calls)
        captures.clear()
        owner.m_Config.MaxObjects = 2
        find(owner, 20)
        self.assertFalse(captures, 'do not inspect beyond MaxObjects')
        owner.m_Config.MaxObjects = 4
        objects[3] = tree('TreeSoft_t_BetulaPendula_1f', [2, 0, 0], height=100)
        find(owner, 30)
        self.assertEqual(['tree_bounds_range'], captures)

    def test_start_defaults_on_and_honors_file_config_and_existing_profile_pattern(self):
        config = N(Enabled=True)
        disable_file = [False]
        profile_value = ['']
        admissions = []
        env = dict(auditleaves_Config=N(HCLoad=lambda: config),
                   FileExist=lambda path: disable_file[0],
                   GetGame=lambda: N(GetProfileString=lambda key, saved: bool(profile_value[0])),
                   HCV2Admission=N(Line=lambda *args: admissions.append(args) or 'admission'),
                   Print=lambda line: None)
        # Native out string binding is a fixture-only syntax adapter.
        text = SOURCE.read_text().replace('string saved;', 'string saved = auditleaves_Saved();')
        env['auditleaves_Saved'] = lambda: profile_value[0]
        start = translate(text, 'HCStart', env, 'auditleaves_Client', member=True)
        owner = N(HCReport=lambda *args: None)
        start(owner)
        self.assertTrue(owner.m_Enabled)
        self.assertEqual(('SeasonLeaves', True, 'HC-226', False), admissions[-1])
        disable_file[0] = True
        start(owner)
        self.assertFalse(owner.m_Enabled)
        disable_file[0] = False
        profile_value[0] = '0'
        start(owner)
        self.assertFalse(owner.m_Enabled)
        profile_value[0] = ''
        config.Enabled = False
        start(owner)
        self.assertFalse(owner.m_Enabled)


def audit_fixture_source():
    """Exact lead-owned test edits, applied ONLY to an in-memory fixture copy."""
    path = ROOT / 'tests/unit/test_auditseason_phase.py'
    original = path.read_text()
    proposed = original.replace(
        'HC-150 leaves=unavailable reason=emitter_asset_contract_uninspected runtime=PENDING',
        'synthetic admission runtime=PENDING')
    proposed = proposed.replace("ROOT / 'docs/auditseason_leaf-feasibility.md'", "ROOT / 'mods/HollowCountry/scripts/5_Mission/Weather/auditleaves_Client.c'")
    proposed = proposed.replace("'falling-leaf feasibility record missing'", "'falling-leaf implementation missing'")
    proposed = proposed.replace("('ParticleList.c:399', 'Particle.c:158', 'Particle.c:174',\n                         'Particle.c:245', 'MiscEffects.c:7', 'runtime=PENDING',\n                         'HCReadPhase', 'forage', 'spec', 'plan', 'tasks')",
        "('ParticleList.c:399', 'Particle.c:158', ':245 StopParticle',\n                         ':340 GetParticleCount', 'runtime=PENDING',\n                         'HCSeasonVisualClient.HCGetPhase', 'HCStopEmitter', 'HCDrain')")
    return original, proposed


class LeavesIntegrationFixture(unittest.TestCase):
    def test_existing_audit_expectations_updated_in_local_fixture_only(self):
        original, proposed = audit_fixture_source()
        self.assertNotEqual(original, proposed)
        namespace = dict(__file__=str(ROOT / 'tests/unit/test_auditseason_phase.py'),
                         __name__='auditleaves_synthetic_audit_fixture')
        exec(compile(proposed, 'auditleaves_synthetic_audit_fixture', 'exec'), namespace)
        result = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(namespace['ConsumerPhase']).run(result)
        self.assertEqual([], result.errors)
        self.assertEqual([], result.failures)
